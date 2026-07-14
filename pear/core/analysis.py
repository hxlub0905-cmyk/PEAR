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
GLV statistics come from the ROI patch. SNR follows the e-beam definition
``(mean_roi - mean_background) / std_background`` where the background is the
ring around the ROI (a self-contained per-ROI measurement, no separate
reference ROI needed).
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

SNR_MARGIN = 8          # default background ring width (px) for ROI SNR


@dataclass
class ROI:
    """A measurement rectangle belonging to one group."""

    rid: int
    gid: str
    rect: Rect
    label: str = ""


@dataclass
class Group:
    """A category of ROIs."""

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


def roi_snr(image: np.ndarray, rect: Rect, margin: int = SNR_MARGIN) -> float:
    """E-beam SNR: (mean_roi - mean_bg) / std_bg over a background ring."""
    sig = roi_patch(image, rect)
    if sig is None or sig.size == 0:
        return 0.0
    x, y, w, h = rect
    ih, iw = image.shape[:2]
    ex0, ey0 = max(0, x - margin), max(0, y - margin)
    ex1, ey1 = min(iw, x + w + margin), min(ih, y + h + margin)
    outer = image[ey0:ey1, ex0:ex1].astype(np.float64)
    mask = np.ones(outer.shape, dtype=bool)
    iy0, ix0 = y - ey0, x - ex0
    mask[max(0, iy0):max(0, iy0) + h, max(0, ix0):max(0, ix0) + w] = False
    bg = outer[mask]
    if bg.size == 0:
        return 0.0
    sd = float(bg.std())
    if sd < 1e-9:
        return 0.0
    return (float(sig.astype(np.float64).mean()) - float(bg.mean())) / sd


def roi_metric(image: np.ndarray, roi: ROI, mid: str,
               margin: int = SNR_MARGIN) -> float:
    if mid == SNR_ID:
        return roi_snr(image, roi.rect, margin)
    p = roi_patch(image, roi.rect)
    return glv_value(p, mid) if p is not None else 0.0


def group_rois(rois: List[ROI], gid: str) -> List[ROI]:
    return [r for r in rois if r.gid == gid]


def group_values(image: np.ndarray, rois: List[ROI], mid: str,
                 margin: int = SNR_MARGIN) -> np.ndarray:
    return np.asarray([roi_metric(image, r, mid, margin) for r in rois],
                      dtype=np.float64)


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
def grid_rois(bounds: Rect, rows: int, cols: int, inset: float = 0.18) -> List[Rect]:
    """Tile ``bounds`` into ``rows × cols`` rectangles (each slightly inset)."""
    x, y, w, h = bounds
    rows, cols = max(1, int(rows)), max(1, int(cols))
    cw, ch = w / cols, h / rows
    ix, iy = cw * inset, ch * inset
    out: List[Rect] = []
    for r in range(rows):
        for c in range(cols):
            out.append((int(round(x + c * cw + ix)), int(round(y + r * ch + iy)),
                        max(2, int(round(cw * (1 - 2 * inset)))),
                        max(2, int(round(ch * (1 - 2 * inset))))))
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
    gs = [Group(g.gid, g.name, g.color) for g in groups]
    rs = [ROI(r.rid, r.gid, tuple(r.rect), r.label) for r in rois]
    return gs, rs


def _cell(mean: float, std: float) -> str:
    return f"{mean:.3g} ±{std:.2g}"


def compute_analysis(image, groups: List[Group], rois: List[ROI],
                     metrics: List[str], mode: str, within_gid,
                     margin: int = SNR_MARGIN) -> AnalysisResult:
    from pear.core.attributes import metric_label

    if image is None or not metrics:
        return AnalysisResult(empty="Load an image and add ROIs to some groups.")

    cache: Dict[tuple, np.ndarray] = {}

    def vals(g: Group, mid: str) -> np.ndarray:
        key = (g.gid, mid)
        if key not in cache:
            cache[key] = group_values(image, group_rois(rois, g.gid), mid, margin)
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
    return _cell(s["mean"], s["std"])


def _by_gid(groups, gid):
    for g in groups:
        if g.gid == gid:
            return g
    return None
