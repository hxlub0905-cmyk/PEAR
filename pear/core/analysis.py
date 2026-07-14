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
GLV statistics come from each ROI patch. SNR is a *within-group* measurement:
one ROI in the group is tagged the *target* (T) and the remaining ROIs are the
*reference* (R); SNR = ``(mean_target - mean_reference) / std_reference``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from pear.core.attributes import SNR_ID, glv_value

Rect = Tuple[int, int, int, int]      # (x, y, w, h) in image pixels

# Categorical palette for groups (cycles).
GROUP_PALETTE: List[str] = [
    "#F59E0B", "#2563EB", "#16A34A", "#DB2777", "#7C3AED",
    "#0891B2", "#EA580C", "#4B5563",
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
    """A category of ROIs. One ROI may be tagged the SNR *target*; the rest
    of the group's ROIs are the SNR *reference*."""

    gid: str
    name: str
    color: str
    target_rid: Optional[int] = None


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
    """A per-ROI GLV statistic (SNR is a per-group metric, not per ROI)."""
    p = roi_patch(image, roi.rect)
    return glv_value(p, mid) if p is not None else 0.0


def group_snr(image: np.ndarray, rois: List[ROI],
              target_rid: Optional[int]) -> Optional[float]:
    """Within-group SNR = (mean_target - mean_reference) / std_reference.

    ``target_rid`` selects the target ROI; every other ROI in the group is
    the reference (their pixels are pooled). Returns None when there is no
    target, no reference, or the reference has no spread.
    """
    tgt = next((r for r in rois if r.rid == target_rid), None)
    refs = [r for r in rois if r.rid != target_rid]
    if tgt is None or not refs:
        return None
    tp = roi_patch(image, tgt.rect)
    if tp is None or tp.size == 0:
        return None
    ref_pix = [roi_patch(image, r.rect).astype(np.float64).ravel()
               for r in refs if roi_patch(image, r.rect) is not None]
    ref_pix = [a for a in ref_pix if a.size]
    if not ref_pix:
        return None
    ref = np.concatenate(ref_pix)
    sd = float(ref.std())
    if sd < 1e-9:
        return None
    return (float(tp.astype(np.float64).mean()) - float(ref.mean())) / sd


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


def snapshot(groups: List[Group], rois: List[ROI]):
    """Copy the mutable model for safe use on a worker thread."""
    gs = [Group(g.gid, g.name, g.color, g.target_rid) for g in groups]
    rs = [ROI(r.rid, r.gid, tuple(r.rect), r.label) for r in rois]
    return gs, rs


# --------------------------------------------------------------------------- #
# Project (de)serialization — plain JSON-friendly dicts
# --------------------------------------------------------------------------- #
def groups_to_json(groups: List[Group]) -> List[dict]:
    return [{"gid": g.gid, "name": g.name, "color": g.color,
             "target_rid": g.target_rid} for g in groups]


def rois_to_json(rois: List[ROI]) -> List[dict]:
    return [{"rid": r.rid, "gid": r.gid, "rect": list(r.rect),
             "label": r.label} for r in rois]


def groups_from_json(items) -> List[Group]:
    return [Group(g["gid"], g["name"], g["color"], g.get("target_rid"))
            for g in (items or [])]


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

    def vals(g: Group, mid: str) -> np.ndarray:
        key = (g.gid, mid)
        if key not in cache:
            grois = group_rois(rois, g.gid)
            if mid == SNR_ID:
                s = group_snr(image, grois, g.target_rid)
                cache[key] = np.asarray(
                    [] if s is None else [s], dtype=np.float64)
            else:
                cache[key] = group_values(image, grois, mid)
        return cache[key]

    if mode == "between":
        used = [g for g in groups if group_rois(rois, g.gid)]
        if len(used) < 2:
            return AnalysisResult(
                empty="Add ROIs to two or more groups to compare.")
        res = AnalysisResult(subtitle=f"{len(used)} groups")
        for mid in metrics:
            res.charts.append(Chart(metric_label(mid), [
                Series(g.name, g.color, vals(g, mid)) for g in used]))
        res.table_headers = ["Group", "ROIs"] + [metric_label(m) for m in metrics]
        for g in used:
            n = len(group_rois(rois, g.gid))
            cells = [_summ(vals(g, m)) for m in metrics]
            res.table_rows.append((g.name, g.color, [str(n)] + cells))
        return res

    # within a group
    g = _by_gid(groups, within_gid) or (groups[0] if groups else None)
    if g is None or not group_rois(rois, g.gid):
        return AnalysisResult(empty="Add ROIs to this group first.")
    res = AnalysisResult(
        subtitle=f"{g.name} · {len(group_rois(rois, g.gid))} ROIs")
    for mid in metrics:
        res.charts.append(Chart(metric_label(mid),
                                [Series(g.name, g.color, vals(g, mid))]))
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


def _by_gid(groups, gid):
    for g in groups:
        if g.gid == gid:
            return g
    return None
