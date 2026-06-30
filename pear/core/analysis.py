"""Data model, geometry, and analysis orchestration.

Pure NumPy/OpenCV — no Qt. This module ties the vendored period core,
the attribute bank, and the outlier ranking together into per-region
analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from pear.core import stacking
from pear.core.attributes import (ATTR_LABELS, SIZE_ATTRS, compute_attributes)
from pear.core.separability import (AttrOutlierScore, AttrSeparabilityScore,
                                    rank_outlier_attributes,
                                    rank_separability_attributes)

Rect = Tuple[int, int, int, int]  # (x, y, w, h) in image pixels

# A fixed palette for regions; cycles when exhausted. Bright, saturated
# hues that pop on the dark stage. Amber and red are reserved (markers /
# Swiss accent), so they are excluded here.
REGION_PALETTE: List[str] = [
    "#2DD4BF", "#60A5FA", "#C084FC", "#F472B6",
    "#34D399", "#38BDF8", "#A3E635", "#818CF8",
]


@dataclass
class Region:
    """A reference ROI drawn in one cell, expanded to every complete cell."""

    rid: int
    name: str
    color: str
    roi: Rect
    instances: List[Rect] = field(default_factory=list)
    records: List[dict] = field(default_factory=list)
    # Unsupervised outlier ranking.
    ranking: List[AttrOutlierScore] = field(default_factory=list)
    sel_attr: Optional[str] = None
    # Labelled compare: instance indices tagged as "target" (the rest are
    # reference), and the resulting separability ranking.
    target_idx: set = field(default_factory=set)
    sep_ranking: List[AttrSeparabilityScore] = field(default_factory=list)
    sep_sel_attr: Optional[str] = None


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
    """Load an image as 8-bit single-channel grayscale.

    Uses ``cv2.imdecode`` on raw bytes (safe for CJK paths). 16-bit / RGB
    inputs are normalized to 8-bit grayscale.
    """
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
def expand_reference_roi(roi: Rect, px: int, py: int,
                         shape: Tuple[int, ...],
                         origin: Tuple[int, int] = (0, 0)) -> List[Rect]:
    """Expand a reference ROI to one Rect per complete cell.

    Phase-invariant: the reference offset and every target cell share the
    same origin, so the origin cancels. Cells whose instance would fall
    outside the image are dropped.
    """
    x, y, w, h = roi
    ox, oy = origin
    dx, dy = (x - ox) % px, (y - oy) % py
    out: List[Rect] = []
    for (cx, cy) in stacking.tile_coords(shape, px, py, origin):
        ix, iy = cx + dx, cy + dy
        if ix >= 0 and iy >= 0 and ix + w <= shape[1] and iy + h <= shape[0]:
            out.append((ix, iy, w, h))
    return out


def golden_subcell(golden: Optional[np.ndarray], roi: Rect,
                   px: int, py: int) -> Optional[np.ndarray]:
    """The Golden-Cell sub-region matching a region's ROI offset.

    Returns ``None`` (degrade gracefully) if no golden cell exists or the
    sub-region would fall outside the cell.
    """
    if golden is None:
        return None
    x, y, w, h = roi
    dx, dy = x % px, y % py
    if dx + w > golden.shape[1] or dy + h > golden.shape[0]:
        return None
    return golden[dy:dy + h, dx:dx + w]


def build_golden_cell(image: np.ndarray, px: int, py: int,
                      origin: Tuple[int, int] = (0, 0)) -> np.ndarray:
    """Median-stacked reference cell ``(py, px)``."""
    return stacking.stack_cells(image, px, py, method="median", origin=origin)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_region_analysis(image: np.ndarray, region: Region, period: PeriodInfo,
                        nm_per_px: Optional[float] = None,
                        k_sigma: float = 3.5) -> Region:
    """Compute attributes for every instance of a region and rank them.

    Mutates and returns ``region`` (records, ranking, sel_attr). Re-expanding
    invalidates any target tags (instance indices change), so they are
    cleared.
    """
    px, py = period.px, period.py
    region.instances = expand_reference_roi(
        region.roi, px, py, image.shape, period.origin)
    region.target_idx = set()
    region.sep_ranking = []
    region.sep_sel_attr = None

    g_sub = golden_subcell(period.golden_cell, region.roi, px, py)

    records: List[dict] = []
    for (ix, iy, w, h) in region.instances:
        patch = image[iy:iy + h, ix:ix + w]
        attrs = compute_attributes(patch, golden_sub=g_sub, nm_per_px=nm_per_px)
        col = ix // px
        row = iy // py
        rec = {"row": int(row), "col": int(col),
               "x": int(ix), "y": int(iy), "w": int(w), "h": int(h)}
        rec.update(attrs)
        records.append(rec)
    region.records = records

    table = attribute_table(records)
    region.ranking = rank_outlier_attributes(table, k_sigma=k_sigma, skip=SIZE_ATTRS)
    if region.ranking:
        region.sel_attr = region.ranking[0].attr
    else:
        region.sel_attr = None
    return region


def run_region_separability(region: Region) -> Region:
    """Rank attributes by how well they separate tagged target cells from
    the reference cells. Mutates and returns ``region`` (sep_ranking,
    sep_sel_attr). Needs at least one target and one reference instance.
    """
    n = len(region.instances)
    mask = np.zeros(n, dtype=bool)
    for i in region.target_idx:
        if 0 <= i < n:
            mask[i] = True
    table = attribute_table(region.records)
    region.sep_ranking = rank_separability_attributes(
        table, mask, skip=SIZE_ATTRS)
    region.sep_sel_attr = region.sep_ranking[0].attr if region.sep_ranking else None
    return region


def toggle_target(region: Region, idx: int) -> None:
    """Toggle whether instance ``idx`` is tagged as a target cell."""
    if idx in region.target_idx:
        region.target_idx.discard(idx)
    else:
        region.target_idx.add(idx)


def target_mask(region: Region) -> np.ndarray:
    """Boolean array over instances: True where tagged as target."""
    n = len(region.instances)
    mask = np.zeros(n, dtype=bool)
    for i in region.target_idx:
        if 0 <= i < n:
            mask[i] = True
    return mask


def attribute_table(records: List[dict]) -> Dict[str, np.ndarray]:
    """Pivot per-instance records into ``{attr_id: values_per_instance}``.

    Only keys present in ``ATTR_LABELS`` (and present in every record) are
    included.
    """
    if not records:
        return {}
    keys = [k for k in ATTR_LABELS if all(k in r for r in records)]
    return {k: np.array([r[k] for r in records], dtype=np.float64) for k in keys}


def outlier_instances(region: Region, attr: Optional[str] = None) -> List[Rect]:
    """Instance Rects flagged as outliers for the given (or selected) attribute."""
    attr = attr or region.sel_attr
    if attr is None:
        return []
    for score in region.ranking:
        if score.attr == attr:
            return [region.instances[i] for i in score.outlier_indices
                    if 0 <= i < len(region.instances)]
    return []
