"""Data model, geometry, and analysis orchestration.

Pure NumPy/OpenCV — no Qt.

Model
-----
* **Group** — a *category* of features (e.g. "round holes", "square holes").
* **ROI**   — a rectangle placed on the image that belongs to one group. A
  group holds many ROIs. Each ROI is measured independently.

Analysis compares the distribution of a metric across every ROI in a group,
either *between* groups or *within* a single group.

Metrics
-------
GLV statistics come from each ROI patch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from pear.core.attributes import glv_value

Rect = Tuple[int, int, int, int]      # (x, y, w, h) in image pixels

# Categorical palette for groups (cycles).
# No amber in here: amber is the brand accent (trend lines) and the midpoint
# of the heat ramp, so a group wearing it reads as a value off the scale.
GROUP_PALETTE: List[str] = [
    "#0D9488", "#2563EB", "#16A34A", "#DB2777", "#7C3AED",
    "#0891B2", "#B45309", "#4B5563",
]

# Sequential ramp for the metric heatmap: cool → amber → warm.
_HEAT_STOPS = [(0.0, (37, 99, 235)), (0.5, (245, 158, 11)), (1.0, (220, 38, 38))]


def heat_color(t: float) -> str:
    """Map ``t`` in [0, 1] to a hex colour on the blue → amber → red ramp."""
    if not np.isfinite(t):
        return "#4B5563"
    t = 0.0 if t < 0 else (1.0 if t > 1 else float(t))
    for i in range(len(_HEAT_STOPS) - 1):
        t0, c0 = _HEAT_STOPS[i]
        t1, c1 = _HEAT_STOPS[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            r, g, b = (round(a + (b - a) * f) for a, b in zip(c0, c1))
            return f"#{r:02X}{g:02X}{b:02X}"
    return "#DC2626"


@dataclass
class ROI:
    """A measurement rectangle belonging to one group."""

    rid: int
    gid: str
    rect: Rect
    label: str = ""


@dataclass
class Group:
    """A category of ROIs — "round holes", "square holes"."""

    gid: str
    name: str
    color: str


# --------------------------------------------------------------------------- #
# Image IO (CJK-path safe)
# --------------------------------------------------------------------------- #
def load_image(path: str) -> np.ndarray:
    """Load an image as 8-bit single-channel grayscale (CJK-path safe)."""
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        raise IOError(f"could not read file: {path}")
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise IOError(f"could not decode image: {path}")
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype != np.uint8:
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return img


# --------------------------------------------------------------------------- #
# ROI patch + metrics
# --------------------------------------------------------------------------- #
def roi_patch(image: np.ndarray, rect: Rect) -> Optional[np.ndarray]:
    """Clipped ROI patch, or None if it lies fully outside the image."""
    x, y, w, h = rect
    ih, iw = image.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(iw, x + w), min(ih, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    return image[y0:y1, x0:x1]


def roi_metric(image: np.ndarray, roi: ROI, mid: str) -> float:
    """One GLV statistic of one ROI."""
    p = roi_patch(image, roi.rect)
    return glv_value(p, mid) if p is not None else 0.0


def group_rois(rois: List[ROI], gid: str) -> List[ROI]:
    return [r for r in rois if r.gid == gid]


def group_values(image: np.ndarray, rois: List[ROI], mid: str) -> np.ndarray:
    return np.asarray([roi_metric(image, r, mid) for r in rois],
                      dtype=np.float64)


def group_outliers(image: np.ndarray, rois: List[ROI], mid: str,
                   k: float = 1.5) -> set:
    """rids that are Tukey outliers of ``mid`` *within their own group*.

    A value outside ``[Q1 − k·IQR, Q3 + k·IQR]`` is an outlier. Groups with
    fewer than 4 ROIs (too few for a stable IQR) are skipped.
    """
    out: set = set()
    by_gid: Dict[str, List[ROI]] = {}
    for r in rois:
        by_gid.setdefault(r.gid, []).append(r)
    for grs in by_gid.values():
        if len(grs) < 4:
            continue
        vals = np.array([roi_metric(image, r, mid) for r in grs],
                        dtype=np.float64)
        q1, q3 = float(np.percentile(vals, 25)), float(np.percentile(vals, 75))
        iqr = q3 - q1
        if iqr <= 1e-12:
            continue
        lo, hi = q1 - k * iqr, q3 + k * iqr
        for r, v in zip(grs, vals):
            if v < lo or v > hi:
                out.add(r.rid)
    return out


def cohens_d(a, b) -> Optional[float]:
    """Standardized mean difference (a − b) / pooled_sd. None if degenerate."""
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    b = np.asarray(b, dtype=np.float64)
    b = b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return None
    na, nb = a.size, b.size
    sp2 = ((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)
    sp = float(np.sqrt(sp2))
    if sp < 1e-12:
        return None
    return float((a.mean() - b.mean()) / sp)


def attribute_separability(groups_vals) -> Optional[float]:
    """η² (variance of a metric explained by group) in [0, 1]; higher = better
    separation between groups. Needs 2+ non-empty groups with spread."""
    arrs = [np.asarray(v, dtype=np.float64) for v in groups_vals]
    arrs = [a[np.isfinite(a)] for a in arrs]
    arrs = [a for a in arrs if a.size]
    if len(arrs) < 2:
        return None
    allv = np.concatenate(arrs)
    if allv.size < 2:
        return None
    grand = float(allv.mean())
    ss_total = float(((allv - grand) ** 2).sum())
    if ss_total < 1e-12:
        return 0.0
    ss_between = float(sum(a.size * (float(a.mean()) - grand) ** 2 for a in arrs))
    return max(0.0, min(1.0, ss_between / ss_total))


def pixel_hist(patch, bins: int = 32):
    """Grey-level histogram of a patch over the full 0–255 range."""
    p = np.asarray(patch).ravel()
    if p.size == 0:
        return np.zeros(bins, dtype=int), np.linspace(0, 255, bins + 1)
    return np.histogram(p, bins=bins, range=(0, 255))


def summarize(values: np.ndarray) -> Dict[str, float]:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"n": 0, "mean": 0.0, "std": 0.0, "median": 0.0,
                "q25": 0.0, "q75": 0.0, "min": 0.0, "max": 0.0}
    return {"n": int(v.size), "mean": float(v.mean()), "std": float(v.std()),
            "median": float(np.median(v)), "q25": float(np.percentile(v, 25)),
            "q75": float(np.percentile(v, 75)), "min": float(v.min()),
            "max": float(v.max())}


# --------------------------------------------------------------------------- #
# Position profile — GLV against where the ROI sits on the image
# --------------------------------------------------------------------------- #
def roi_center(rect: Rect) -> Tuple[float, float]:
    """Centre of an ROI rectangle, in image pixels."""
    x, y, w, h = rect
    return (x + w / 2.0, y + h / 2.0)


def group_positions(rois: List[ROI], axis: str = "x") -> np.ndarray:
    """Each ROI's centre coordinate along ``axis`` ("x" or "y"), in pixels.

    Ordering matches :func:`group_values`, so a value and its position share
    an index.
    """
    i = 1 if str(axis).lower() == "y" else 0
    return np.asarray([roi_center(r.rect)[i] for r in rois], dtype=np.float64)


def linear_trend(x, y) -> Optional[Tuple[float, float]]:
    """Least-squares ``(slope, intercept)`` of y on x, or None if degenerate.

    The slope is the tilt of a GLV-vs-position profile: 0 means flat.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if x.size < 2 or float(x.std()) < 1e-12:
        return None
    sx, sy = float(x.mean()), float(y.mean())
    dx = x - sx
    denom = float((dx * dx).sum())
    if denom < 1e-12:
        return None
    slope = float((dx * (y - sy)).sum() / denom)
    return slope, float(sy - slope * sx)


def uniformity(values) -> Dict[str, float]:
    """How flat a metric is across ROIs — the numbers, no verdict.

    ``range`` is peak-to-peak (0 for a perfectly flat profile); ``range_pct``
    and ``cv_pct`` express spread as a percentage of the mean, which is how
    grey-level uniformity is usually quoted.
    """
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"n": 0, "mean": 0.0, "range": 0.0, "range_pct": 0.0,
                "std": 0.0, "cv_pct": 0.0}
    mean = float(v.mean())
    rng = float(v.max() - v.min())
    sd = float(v.std())
    den = abs(mean)
    return {"n": int(v.size), "mean": mean, "range": rng,
            "range_pct": (rng / den * 100.0) if den > 1e-12 else 0.0,
            "std": sd,
            "cv_pct": (sd / den * 100.0) if den > 1e-12 else 0.0}


def jitter_tolerance(sorted_unique) -> float:
    """How far apart two centres can be and still be the same row or column.

    Hand-placed ROIs land a few pixels off each other, so a row of eight is
    really eight tight knots of positions, not eight positions. Sort the gaps
    between neighbouring centres and there is a step change between the
    within-knot gaps (a few px) and the pitch between knots (tens of px); the
    tolerance sits in that step. Returns 0 when the gaps have no such split —
    a genuine scatter is not jitter and must not be merged.
    """
    a = np.asarray(sorted_unique, dtype=np.float64)
    if a.size < 3:
        return 0.0
    gaps = np.sort(np.diff(a))
    gaps = gaps[gaps > 0]
    if gaps.size < 2:
        return 0.0
    ratios = gaps[1:] / np.maximum(gaps[:-1], 1e-9)
    i = int(np.argmax(ratios))
    # Evidence for jitter, not a sparse layout: the step has to be a real
    # step (4x), and there has to be a population of small gaps below it —
    # one small gap among large ones is a missing ROI, not a wobble.
    if i < 1 or ratios[i] < 4.0:
        return 0.0
    # the log-middle of the step: comfortably above every jitter gap, and
    # never far enough to swallow a whole pitch
    return float(np.sqrt(gaps[i] * gaps[i + 1]))


def cluster_positions(positions, tol: float):
    """Collapse centres within ``tol`` of their neighbour into one position.

    The representative is the cluster's mean, so a row that wobbles by a pixel
    or two lands on the row it was meant to be.
    """
    a = np.sort(np.asarray(positions, dtype=np.float64))
    if a.size == 0:
        return np.empty(0)
    if tol <= 0:
        return np.unique(a)
    out, start = [], 0
    for i in range(1, a.size + 1):
        if i == a.size or a[i] - a[i - 1] > tol:
            out.append(float(a[start:i].mean()))
            start = i
    return np.asarray(out, dtype=np.float64)


def cell_edges(positions, decimals: int = 3, tol: Optional[float] = None):
    """Tiling boundaries for ROI centres along one axis.

    Returns ``(centres, edges)``: the distinct centres, sorted, and the
    ``len(centres) + 1`` boundaries midway between neighbours, the outermost
    pair mirrored outward by half of the adjacent gap. Drawing each ROI from
    its lower to its upper edge tiles the axis exactly — no hairline gaps
    where centres landed on rounded pixels, no overlap where the spacing is
    uneven; a lone gap in the layout simply gives that ROI a wider cell.

    Centres within ``tol`` of each other count as one row or column, so a grid
    placed by hand tiles as the grid it is rather than shattering into a
    sliver per stray pixel. ``tol=None`` measures it from the data
    (:func:`jitter_tolerance`); pass 0 to keep every distinct centre.

    A single distinct centre has no neighbour to measure against and gets a
    one-pixel cell; the caller substitutes a size of its own.
    """
    a = np.asarray(positions, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return np.empty(0), np.empty(0)
    a = np.round(a, decimals)
    if tol is None:
        tol = jitter_tolerance(np.unique(a))
    c = cluster_positions(a, tol)
    if c.size == 1:
        return c, np.asarray([c[0] - 0.5, c[0] + 0.5])
    mid = (c[:-1] + c[1:]) / 2.0
    return c, np.concatenate(([2.0 * c[0] - mid[0]], mid,
                              [2.0 * c[-1] - mid[-1]]))


def heat_cells(rois: List[ROI], bounds=None) -> Dict[int, Tuple[float, float,
                                                             float, float]]:
    """``rid -> (x0, y0, x1, y1)``: the patch of image each ROI speaks for.

    The ROI boxes are the measurements; between them the field is unmeasured.
    Painting each ROI's value across the rectangle bounded by the midlines to
    its neighbours (:func:`cell_edges` on each axis) fills that gap with the
    nearest actual measurement, so a gradient across the field shows up as a
    gradient instead of a row of small tinted boxes. ``bounds = (w, h)`` clips
    the tiling to the image.
    """
    if not rois:
        return {}
    cx = np.asarray([roi_center(r.rect)[0] for r in rois], dtype=np.float64)
    cy = np.asarray([roi_center(r.rect)[1] for r in rois], dtype=np.float64)
    xc, xe = cell_edges(cx)
    yc, ye = cell_edges(cy)
    # a single row (or column) has no pitch of its own — it borrows the other
    # axis's, and with neither the ROI's own box is all the extent there is
    def step(e, fallback):
        return float(np.median(np.diff(e))) if e.size > 2 else fallback

    sx = step(xe, 0.0)
    sy = step(ye, 0.0)
    out: Dict[int, Tuple[float, float, float, float]] = {}
    for r, x, y in zip(rois, cx, cy):
        w, h = float(r.rect[2]), float(r.rect[3])
        if xe.size > 2:
            i = int(np.abs(xc - x).argmin())
            x0, x1 = float(xe[i]), float(xe[i + 1])
        else:
            half = (sy if sy > 0 else w) / 2.0
            x0, x1 = float(x - half), float(x + half)
        if ye.size > 2:
            j = int(np.abs(yc - y).argmin())
            y0, y1 = float(ye[j]), float(ye[j + 1])
        else:
            half = (sx if sx > 0 else h) / 2.0
            y0, y1 = float(y - half), float(y + half)
        if bounds:
            bw, bh = float(bounds[0]), float(bounds[1])
            x0, x1 = max(0.0, x0), min(bw, x1)
            y0, y1 = max(0.0, y0), min(bh, y1)
        out[r.rid] = (x0, y0, x1, y1)
    return out


def profile_by_position(positions, values, decimals: int = 0,
                        tol: Optional[float] = None):
    """Collapse ROIs that share a position into one mean value.

    A grid of ROIs puts several boxes at the same X; averaging them gives the
    single profile line you read flatness off. Boxes placed by hand miss that
    shared X by a pixel or two, which splits one column into several and puts
    a kink in the line for every one of them — so centres within ``tol`` count
    as the same position. ``tol=None`` measures it from the data
    (:func:`jitter_tolerance`); pass 0 to group only exact matches.

    Returns ``(pos, mean)`` sorted by position.
    """
    px = np.asarray(positions, dtype=np.float64)
    v = np.asarray(values, dtype=np.float64)
    m = np.isfinite(px) & np.isfinite(v)
    px, v = px[m], v[m]
    if px.size == 0:
        return np.empty(0), np.empty(0)
    keys = np.round(px, decimals)
    if tol is None:
        tol = jitter_tolerance(np.unique(keys))
    slots = cluster_positions(keys, tol)
    if slots.size == 0:
        return np.empty(0), np.empty(0)
    # each ROI joins the slot it is nearest to
    idx = np.abs(keys[:, None] - slots[None, :]).argmin(axis=1)
    centers, means = [], []
    for k in range(slots.size):
        sel = idx == k
        if not sel.any():
            continue
        centers.append(float(px[sel].mean()))
        means.append(float(v[sel].mean()))
    return (np.asarray(centers, dtype=np.float64),
            np.asarray(means, dtype=np.float64))


# --------------------------------------------------------------------------- #
# Tidying a selection — alignment and spacing
# --------------------------------------------------------------------------- #
ALIGN_MODES = ("left", "hcenter", "right", "top", "vcenter", "bottom")


def align_rects(rects: List[Rect], mode: str) -> List[Rect]:
    """Pull rectangles onto one edge (or one centre line) of their bounding box.

    ROIs dropped by hand sit a few pixels off each other, which is invisible
    until the field heat map tiles them: the cell boundaries fall midway
    between centres, so a stray pixel of offset turns a clean grid into a
    staircase. Order is preserved and anything under two rects is returned
    unchanged.
    """
    if len(rects) < 2 or mode not in ALIGN_MODES:
        return list(rects)
    xs = [r[0] for r in rects]
    ys = [r[1] for r in rects]
    rights = [r[0] + r[2] for r in rects]
    bottoms = [r[1] + r[3] for r in rects]
    out: List[Rect] = []
    for x, y, w, h in rects:
        if mode == "left":
            x = min(xs)
        elif mode == "right":
            x = max(rights) - w
        elif mode == "hcenter":
            x = int(round((min(xs) + max(rights)) / 2.0 - w / 2.0))
        elif mode == "top":
            y = min(ys)
        elif mode == "bottom":
            y = max(bottoms) - h
        elif mode == "vcenter":
            y = int(round((min(ys) + max(bottoms)) / 2.0 - h / 2.0))
        out.append((int(x), int(y), int(w), int(h)))
    return out


def distribute_rects(rects: List[Rect], axis: str = "x") -> List[Rect]:
    """Even the spacing of rect centres between the two outermost ones.

    The heat map's cells are as wide as the gap to the next ROI, so uneven
    spacing reads as cells of uneven size — a pattern in the picture that is
    not in the measurement. Fewer than three rects have no gap to even out.
    """
    if len(rects) < 3:
        return list(rects)
    i = 1 if str(axis).lower() == "y" else 0
    centers = [roi_center(r)[i] for r in rects]
    order = sorted(range(len(rects)), key=lambda k: centers[k])
    lo, hi = centers[order[0]], centers[order[-1]]
    step = (hi - lo) / (len(rects) - 1)
    out = list(rects)
    for slot, k in enumerate(order):
        x, y, w, h = rects[k]
        want = lo + step * slot
        if i == 0:
            x = int(round(want - w / 2.0))
        else:
            y = int(round(want - h / 2.0))
        out[k] = (int(x), int(y), int(w), int(h))
    return out


# --------------------------------------------------------------------------- #
# Multi-add helpers
# --------------------------------------------------------------------------- #
def grid_between(tl_center: Tuple[float, float], br_center: Tuple[float, float],
                 rows: int, cols: int, w: int, h: int) -> List[Rect]:
    """Grid of same-size ROIs whose *centers* interpolate between two anchors.

    ``tl_center`` is the centre of the top-left corner ROI (grid[0,0]) and
    ``br_center`` the centre of the bottom-right one (grid[rows-1,cols-1]);
    the ``rows × cols`` centres are spaced evenly between them (matching the
    sibling tool's ``generate_grid``). Every ROI is ``w × h``.
    """
    tlx, tly = tl_center
    brx, bry = br_center
    rows, cols = max(1, int(rows)), max(1, int(cols))
    step_x = (brx - tlx) / (cols - 1) if cols > 1 else 0.0
    step_y = (bry - tly) / (rows - 1) if rows > 1 else 0.0
    out: List[Rect] = []
    for i in range(rows):
        for j in range(cols):
            cx = tlx + j * step_x
            cy = tly + i * step_y
            out.append((int(round(cx - w / 2)), int(round(cy - h / 2)),
                        int(w), int(h)))
    return out


# --------------------------------------------------------------------------- #
# Comparison — pure, cached, thread-safe
# --------------------------------------------------------------------------- #
@dataclass
class Series:
    label: str
    color: str
    values: np.ndarray
    # Centre of each ROI, index-aligned with ``values``.
    pos_x: Optional[np.ndarray] = None
    pos_y: Optional[np.ndarray] = None


@dataclass
class Chart:
    title: str
    series: List["Series"] = field(default_factory=list)


@dataclass
class AnalysisResult:
    subtitle: str = ""
    empty: Optional[str] = None
    charts: List["Chart"] = field(default_factory=list)
    table_headers: List[str] = field(default_factory=list)
    table_rows: List[tuple] = field(default_factory=list)
    # between-mode extras
    ranking: List[tuple] = field(default_factory=list)   # (label, η², cohen_d)
    heat: Optional[dict] = None                          # group × metric matrix


def snapshot(groups: List[Group], rois: List[ROI]):
    """Copy the mutable model for safe use on a worker thread."""
    gs = [Group(g.gid, g.name, g.color) for g in groups]
    rs = [ROI(r.rid, r.gid, tuple(r.rect), r.label) for r in rois]
    return gs, rs


# --------------------------------------------------------------------------- #
# Project (de)serialization — plain JSON-friendly dicts
# --------------------------------------------------------------------------- #
def groups_to_json(groups: List[Group]) -> List[dict]:
    return [{"gid": g.gid, "name": g.name, "color": g.color}
            for g in groups]


def rois_to_json(rois: List[ROI]) -> List[dict]:
    return [{"rid": r.rid, "gid": r.gid, "rect": list(r.rect),
             "label": r.label} for r in rois]


def groups_from_json(items) -> List[Group]:
    # ``target_rid`` may still be in an older project file; it is ignored.
    return [Group(g["gid"], g["name"], g["color"]) for g in (items or [])]


def rois_from_json(items) -> List[ROI]:
    return [ROI(r["rid"], r["gid"], tuple(r["rect"]), r.get("label", ""))
            for r in (items or [])]


def _cell(mean: float, std: float) -> str:
    return f"{mean:.3g} ±{std:.2g}"


def compute_analysis(image, groups: List[Group], rois: List[ROI],
                     metrics: List[str], mode: str, within_gid) -> AnalysisResult:
    from pear.core.attributes import metric_label

    if image is None or not metrics:
        return AnalysisResult(empty="Load an image and add ROIs to some groups.")

    cache: Dict[tuple, np.ndarray] = {}
    pcache: Dict[str, tuple] = {}

    def positions(g: Group) -> tuple:
        """(x, y) centres of the group's ROIs, index-aligned with vals()."""
        if g.gid not in pcache:
            grois = group_rois(rois, g.gid)
            pcache[g.gid] = (group_positions(grois, "x"),
                             group_positions(grois, "y"))
        return pcache[g.gid]

    def series_of(g: Group, mid: str) -> Series:
        px, py = positions(g)
        return Series(g.name, g.color, vals(g, mid), px, py)

    def vals(g: Group, mid: str) -> np.ndarray:
        key = (g.gid, mid)
        if key not in cache:
            cache[key] = group_values(image, group_rois(rois, g.gid), mid)
        return cache[key]

    if mode == "between":
        used = [g for g in groups if group_rois(rois, g.gid)]
        if len(used) < 2:
            return AnalysisResult(
                empty="Add ROIs to two or more groups to compare.")
        res = AnalysisResult(subtitle=f"{len(used)} groups")
        for mid in metrics:
            res.charts.append(Chart(metric_label(mid),
                                    [series_of(g, mid) for g in used]))
        res.table_headers = ["Group", "ROIs"] + [metric_label(m) for m in metrics]
        for g in used:
            n = len(group_rois(rois, g.gid))
            cells = [_summ(vals(g, m)) for m in metrics]
            res.table_rows.append((g.name, g.color, [str(n)] + cells))
        # group × metric heatmap + attribute ranking
        res.heat = {
            "groups": [g.name for g in used],
            "colors": [g.color for g in used],
            "metrics": [metric_label(m) for m in metrics],
            "values": [[_mean_or_nan(vals(g, m)) for m in metrics] for g in used],
        }
        ranking = []
        for mid in metrics:
            eta = attribute_separability([vals(g, mid) for g in used])
            d = (cohens_d(vals(used[0], mid), vals(used[1], mid))
                 if len(used) == 2 else None)
            ranking.append((metric_label(mid), eta, d))
        ranking.sort(key=lambda r: (r[1] is None, -(r[1] or 0.0)))
        res.ranking = ranking
        return res

    # within a group
    g = _by_gid(groups, within_gid) or (groups[0] if groups else None)
    if g is None or not group_rois(rois, g.gid):
        return AnalysisResult(empty="Add ROIs to this group first.")
    res = AnalysisResult(
        subtitle=f"{g.name} · {len(group_rois(rois, g.gid))} ROIs")
    for mid in metrics:
        res.charts.append(Chart(metric_label(mid), [series_of(g, mid)]))
    res.table_headers = ["", "ROIs"] + [metric_label(m) for m in metrics]
    res.table_rows.append((g.name, g.color,
                           [str(len(group_rois(rois, g.gid)))]
                           + [_summ(vals(g, m)) for m in metrics]))
    return res


def _summ(values: np.ndarray) -> str:
    s = summarize(values)
    if s["n"] == 0:
        return "—"
    if s["n"] == 1:
        return f"{s['mean']:.3g}"
    return _cell(s["mean"], s["std"])


def _mean_or_nan(v) -> float:
    v = np.asarray(v, dtype=np.float64)
    v = v[np.isfinite(v)]
    return float(v.mean()) if v.size else float("nan")


def _by_gid(groups, gid):
    for g in groups:
        if g.gid == gid:
            return g
    return None
