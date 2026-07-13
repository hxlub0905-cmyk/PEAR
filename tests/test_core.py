"""Headless core tests (no Qt) for the group/ROI analysis model."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.make_sample import (CELL_H, CELL_W, N_COLS, N_ROWS, OUTLIERS,
                                  make_field)
from pear.core.analysis import (ROI, REFERENCE, TARGET, Group, PeriodInfo,
                                all_cells, build_golden_cell, cell_at_point,
                                cell_patch, find_role, grid_dims,
                                group_metric_values, set_role, summarize)
from pear.core.attributes import (GLV_STATS, SNR_ID, glv_value, metric_label,
                                  quantile_of, snr)
from pear.core.period_core import estimate_period


def _period(img) -> PeriodInfo:
    res = estimate_period(img)
    return PeriodInfo(px=res.px, py=res.py, axis_mode=res.axis_mode,
                      confidence=80.0, golden_cell=build_golden_cell(img, res.px, res.py))


def test_estimate_period_recovers_cell_size():
    img = make_field()
    res = estimate_period(img)
    assert res.px == CELL_W and res.py == CELL_H and res.axis_mode == "XY"


def test_grid_and_cell_geometry():
    img = make_field()
    period = _period(img)
    assert grid_dims(img.shape, period) == (N_ROWS, N_COLS)
    assert len(all_cells(img.shape, period)) == N_ROWS * N_COLS
    # cell hit-test lands in the right cell
    assert cell_at_point(period, CELL_W + 3, CELL_H + 3, img.shape) == (1, 1)
    patch = cell_patch(img, (16, 13, 20, 18), period, 0, 0)
    assert patch is not None and patch.shape == (18, 20)


def test_glv_metrics_and_custom_quantile():
    patch = np.array([[10, 20, 30, 40, 50]], dtype=np.uint8)
    assert abs(glv_value(patch, "glv_mean") - 30.0) < 1e-9
    assert glv_value(patch, "glv_min") == 10.0 and glv_value(patch, "glv_max") == 50.0
    assert quantile_of("glv_q90") == 90 and quantile_of("glv_median") is None
    assert metric_label("glv_q90") == "GLV Q90"
    # custom quantile computes a percentile
    assert abs(glv_value(patch, "glv_q50") - 30.0) < 1e-9


def test_snr_definition():
    # target brighter than reference, low reference noise -> high SNR
    tgt = np.full((8, 8), 150.0)
    ref = np.random.default_rng(0).normal(70, 5, (8, 8))
    assert snr(tgt, ref) > 5.0
    # zero-variance reference guarded
    assert snr(tgt, np.full((4, 4), 70.0)) == 0.0


def test_group_metric_between_separates_outliers():
    img = make_field()
    period = _period(img)
    roi = ROI(1, "Center", "#F59E0B", (16, 13, 30, 26))
    outset = set(OUTLIERS)
    gA, gB = Group("A", "A", "#F59E0B"), Group("B", "B", "#2563EB")
    for (r, c) in all_cells(img.shape, period):
        (gB if (c, r) in outset else gA).cells.add((r, c))
    assert len(gB.cells) == len(OUTLIERS)
    mA = summarize(group_metric_values(img, gA, roi, period, "glv_mean"))
    mB = summarize(group_metric_values(img, gB, roi, period, "glv_mean"))
    # outlier group is clearly dimmer and well separated
    assert mA["mean"] - mB["mean"] > 30.0
    assert mA["n"] == N_ROWS * N_COLS - len(OUTLIERS)


def test_within_group_snr_target_vs_reference():
    img = make_field()
    period = _period(img)
    center = ROI(1, "Center", "#DC2626", (16, 13, 30, 26), role=TARGET)
    bg = ROI(2, "Background", "#0891B2", (2, 2, 12, 12), role=REFERENCE)
    outset = set(OUTLIERS)
    gB = Group("B", "B", "#2563EB")
    gA = Group("A", "A", "#F59E0B")
    for (r, c) in all_cells(img.shape, period):
        (gB if (c, r) in outset else gA).cells.add((r, c))
    snrA = group_metric_values(img, gA, center, period, SNR_ID,
                               target_roi=center, reference_roi=bg)
    snrB = group_metric_values(img, gB, center, period, SNR_ID,
                               target_roi=center, reference_roi=bg)
    # normal cells have a stronger feature-vs-background SNR than outliers
    assert snrA.mean() > snrB.mean() > 0


def test_set_role_single_target():
    rois = [ROI(1, "a", "#000", (0, 0, 4, 4)),
            ROI(2, "b", "#000", (0, 0, 4, 4))]
    set_role(rois, rois[0], TARGET)
    set_role(rois, rois[1], TARGET)      # second target demotes the first
    assert rois[0].role == REFERENCE and rois[1].role == TARGET
    assert find_role(rois, TARGET) is rois[1]


def test_metric_labels_complete():
    for mid in GLV_STATS:
        assert metric_label(mid)
    assert metric_label(SNR_ID) == "SNR"
