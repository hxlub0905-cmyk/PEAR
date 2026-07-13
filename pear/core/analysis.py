"""Data model, geometry, and analysis orchestration.

Pure NumPy/OpenCV — no Qt. The model has two orthogonal concepts:

* **Group** — a user-painted set of *cells* (the populations to compare).
* **ROI** — a measurement rectangle *inside a cell*, phase-invariant so it
  repeats in every cell. When target/reference splitting is on, one ROI is
  the *target* and one is the *reference*, which enables SNR.

Analysis is on demand: only the selected metric(s) for the chosen ROI(s)
are computed, and only over the cells that belong to a group.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import cv2
import numpy as np

from pear.core import stacking
from pear.core.attributes import SNR_ID, glv_value, snr

Rect = Tuple[int, int, int, int]      # (x, y, w, h) in image pixels
Cell = Tuple[int, int]                # (row, col)

# Categorical palette for groups (cycles). Distinct hues that read on the
# black stage and on the light panels.
GROUP_PALETTE: List[str] = [
    "#F59E0B", "#2563EB", "#16A34A", "#DB2777", "#7C3AED",
    "#0891B2", "#EA580C", "#4B5563",
]
# Target / reference default colours (used when T/R splitting is on).
TARGET_COLOR = "#DC2626"
REFERENCE_COLOR = "#0891B2"

TARGET = "target"
REFERENCE = "reference"
NONE = "none"


@dataclass
class ROI:
    """A measurement rectangle defined in one cell, repeated in every cell."""

    rid: int
    label: str
    color: str
    rect: Rect                       # reference rect in image pixels
    role: str = NONE                 # "target" | "reference" | "none"


@dataclass
class Group:
    """A user-painted set of cells."""

    gid: str
    name: str
    color: str
    cells: Set[Cell] = field(default_factory=set)
    role: str = NONE                 # "target" | "reference" | "none"


@dataclass
class PeriodInfo:
    px: int
    py: int
    axis_mode: str
    confidence: float
    origin: Tuple[int, int] = (0, 0)
    golden_cell: Optional[np.ndarray] = None


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
# Geometry
# --------------------------------------------------------------------------- #
def grid_dims(shape: Tuple[int, ...], period: PeriodInfo) -> Tuple[int, int]:
    """Number of complete ``(rows, cols)`` in the lattice."""
    h, w = shape[:2]
    ox, oy = period.origin
    px, py = period.px, period.py
    if px < 1 or py < 1:
        return 0, 0
    cols = max(0, (w - ox) // px)
    rows = max(0, (h - oy) // py)
    return int(rows), int(cols)


def all_cells(shape: Tuple[int, ...], period: PeriodInfo) -> List[Cell]:
    rows, cols = grid_dims(shape, period)
    return [(r, c) for r in range(rows) for c in range(cols)]


def cell_rect(period: PeriodInfo, row: int, col: int) -> Rect:
    """Full footprint rect of one cell."""
    ox, oy = period.origin
    return (ox + col * period.px, oy + row * period.py, period.px, period.py)


def cell_patch(image: np.ndarray, roi_rect: Rect, period: PeriodInfo,
               row: int, col: int) -> Optional[np.ndarray]:
    """The ROI sub-patch for one cell (phase-invariant), or None if it would
    fall outside the image."""
    px, py = period.px, period.py
    x, y, w, h = roi_rect
    ox, oy = period.origin
    dx, dy = (x - ox) % px, (y - oy) % py
    ix = ox + col * px + dx
    iy = oy + row * py + dy
    ih, iw = image.shape[:2]
    if ix < 0 or iy < 0 or ix + w > iw or iy + h > ih:
        return None
    return image[iy:iy + h, ix:ix + w]


def cell_at_point(period: PeriodInfo, x: int, y: int,
                  shape: Tuple[int, ...]) -> Optional[Cell]:
    """Which cell contains image point ``(x, y)`` (or None)."""
    ox, oy = period.origin
    px, py = period.px, period.py
    if px < 1 or py < 1 or x < ox or y < oy:
        return None
    col = (x - ox) // px
    row = (y - oy) // py
    rows, cols = grid_dims(shape, period)
    if 0 <= row < rows and 0 <= col < cols:
        return (int(row), int(col))
    return None


def build_golden_cell(image: np.ndarray, px: int, py: int,
                      origin: Tuple[int, int] = (0, 0)) -> np.ndarray:
    """Median-stacked reference cell ``(py, px)``."""
    return stacking.stack_cells(image, px, py, method="median", origin=origin)


# --------------------------------------------------------------------------- #
# Metric collection
# --------------------------------------------------------------------------- #
def group_metric_values(image: np.ndarray, group: Group, roi: ROI,
                        period: PeriodInfo, mid: str,
                        target_roi: Optional[ROI] = None,
                        reference_roi: Optional[ROI] = None) -> np.ndarray:
    """Per-cell metric values over a group's cells.

    For SNR, ``target_roi`` and ``reference_roi`` are required; otherwise the
    metric is read from ``roi``.
    """
    vals: List[float] = []
    for (r, c) in sorted(group.cells):
        if mid == SNR_ID:
            if target_roi is None or reference_roi is None:
                continue
            t = cell_patch(image, target_roi.rect, period, r, c)
            ref = cell_patch(image, reference_roi.rect, period, r, c)
            if t is None or ref is None:
                continue
            vals.append(snr(t, ref))
        else:
            p = cell_patch(image, roi.rect, period, r, c)
            if p is None:
                continue
            vals.append(glv_value(p, mid))
    return np.asarray(vals, dtype=np.float64)


def roi_metric_values(image: np.ndarray, group: Group, roi: ROI,
                      period: PeriodInfo, mid: str) -> np.ndarray:
    """Per-cell values of a single ROI's GLV metric over a group's cells."""
    vals: List[float] = []
    for (r, c) in sorted(group.cells):
        p = cell_patch(image, roi.rect, period, r, c)
        if p is None:
            continue
        vals.append(glv_value(p, mid))
    return np.asarray(vals, dtype=np.float64)


def summarize(values: np.ndarray) -> Dict[str, float]:
    """n / mean / std / median / q25 / q75 / min / max of a value array."""
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"n": 0, "mean": 0.0, "std": 0.0, "median": 0.0,
                "q25": 0.0, "q75": 0.0, "min": 0.0, "max": 0.0}
    return {
        "n": int(v.size),
        "mean": float(v.mean()),
        "std": float(v.std()),
        "median": float(np.median(v)),
        "q25": float(np.percentile(v, 25)),
        "q75": float(np.percentile(v, 75)),
        "min": float(v.min()),
        "max": float(v.max()),
    }


# --------------------------------------------------------------------------- #
# Comparison — a pure, cached compute step (headless-testable, thread-safe)
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
    table_rows: List[tuple] = field(default_factory=list)   # (name, color, [str])
    snr_text: Optional[str] = None


def snapshot(groups: List[Group], rois: List[ROI]):
    """Deep-ish copy of the mutable model for safe use on a worker thread."""
    gs = [Group(g.gid, g.name, g.color, set(g.cells), g.role) for g in groups]
    rs = [ROI(r.rid, r.label, r.color, tuple(r.rect), r.role) for r in rois]
    return gs, rs


def _cell(mean: float, std: float) -> str:
    return f"{mean:.3g} ±{std:.2g}"


def compute_analysis(image, period, groups: List[Group], rois: List[ROI],
                     metrics: List[str], mode: str, between_rid, within_gid,
                     split: bool) -> AnalysisResult:
    """Compute the comparison for the Analysis panel. Pure; no Qt.

    ``mode`` is ``"between"`` or ``"within"``. Values are cached per
    (group, roi, metric) so a metric is never measured twice per call.
    """
    from pear.core.attributes import metric_label   # local: avoid cycle churn

    if image is None or period is None or not metrics:
        return AnalysisResult(empty="Load an image, detect the lattice, then paint groups.")

    tgt = find_role(rois, TARGET) if split else None
    ref = find_role(rois, REFERENCE) if split else None
    cache: Dict[tuple, np.ndarray] = {}

    def vals(group: Group, roi: Optional[ROI], mid: str) -> np.ndarray:
        rid = None if mid == SNR_ID else (roi.rid if roi else None)
        key = (group.gid, rid, mid)
        if key not in cache:
            cache[key] = group_metric_values(
                image, group, roi, period, mid, target_roi=tgt, reference_roi=ref)
        return cache[key]

    if mode == "between":
        used = [g for g in groups if g.cells]
        if len(used) < 2:
            return AnalysisResult(empty="Assign cells to two or more groups (Paint mode).")
        roi = _by_rid(rois, between_rid) or (rois[0] if rois else None)
        if roi is None:
            return AnalysisResult(empty="Add an ROI to measure.")
        res = AnalysisResult(subtitle=f"{len(used)} groups · ROI {roi.label}")
        for mid in metrics:
            res.charts.append(Chart(metric_label(mid), [
                Series(g.name, g.color, vals(g, roi, mid)) for g in used]))
        res.table_headers = ["Group", "n"] + [metric_label(m) for m in metrics]
        for g in used:
            row_vals = [_summ_cell(vals(g, roi, m)) for m in metrics]
            res.table_rows.append((g.name, g.color, [str(len(g.cells))] + row_vals))
        # Target − Reference delta row (group-level T/R), when tagged.
        gt = find_role(used, TARGET)
        gr = find_role(used, REFERENCE)
        if gt is not None and gr is not None:
            deltas = []
            for m in metrics:
                dt = float(vals(gt, roi, m).mean()) if vals(gt, roi, m).size else 0.0
                dr = float(vals(gr, roi, m).mean()) if vals(gr, roi, m).size else 0.0
                deltas.append(f"{dt - dr:+.3g}")
            res.table_rows.append(("Δ (T − R)", None, [""] + deltas))
        return res

    # within a group
    g = _by_gid(groups, within_gid) or (groups[0] if groups else None)
    if g is None or not g.cells:
        return AnalysisResult(empty="Paint cells into a group first.")
    if split:
        if tgt is None or ref is None:
            return AnalysisResult(empty="Tag one ROI as T and one as R (ROIs card).")
        snr_v = vals(g, tgt, SNR_ID)
        s = summarize(snr_v)
        tm = summarize(vals(g, tgt, "glv_mean"))
        rm = summarize(vals(g, ref, "glv_mean"))
        res = AnalysisResult(
            subtitle=f"{g.name} · {len(g.cells)} cells · {tgt.label} (T) vs {ref.label} (R)",
            snr_text=(f"SNR = (μT − μR)/σR   →   μT {tm['mean']:.1f} · "
                      f"μR {rm['mean']:.1f}   ⇒   SNR {s['mean']:.2f} ± {s['std']:.2f} "
                      f"over {s['n']} cells"))
        for mid in metrics:
            if mid == SNR_ID:
                continue
            res.charts.append(Chart(metric_label(mid), [
                Series(tgt.label, tgt.color, vals(g, tgt, mid)),
                Series(ref.label, ref.color, vals(g, ref, mid))]))
        return res
    roi = _by_rid(rois, between_rid) or (rois[0] if rois else None)
    if roi is None:
        return AnalysisResult(empty="Add an ROI to measure.")
    res = AnalysisResult(subtitle=f"{g.name} · {len(g.cells)} cells · ROI {roi.label}")
    for mid in metrics:
        if mid == SNR_ID:
            continue
        res.charts.append(Chart(metric_label(mid), [
            Series(g.name, g.color, vals(g, roi, mid))]))
    return res


def _summ_cell(values: np.ndarray) -> str:
    s = summarize(values)
    return _cell(s["mean"], s["std"])


def _by_rid(rois, rid):
    for r in rois:
        if r.rid == rid:
            return r
    return None


def _by_gid(groups, gid):
    for g in groups:
        if g.gid == gid:
            return g
    return None


# --------------------------------------------------------------------------- #
# Role helpers (target / reference)
# --------------------------------------------------------------------------- #
def set_role(items: List, item, role: str) -> None:
    """Set ``item.role``, enforcing at most one holder of each role.

    Assigning ``target`` or ``reference`` clears that same role from every
    other item (to ``none``) so ``find_role`` is never ambiguous and the SNR
    target/reference can't silently switch when an unrelated item is retagged.
    """
    if role in (TARGET, REFERENCE):
        for other in items:
            if other is not item and other.role == role:
                other.role = NONE
    item.role = role


def find_role(items: List, role: str):
    for it in items:
        if it.role == role:
            return it
    return None
