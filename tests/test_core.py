"""Headless core tests (no Qt) for the group/ROI analysis model."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.make_sample import CELL_H, CELL_W, make_field
from pear.core.analysis import (ROI, Group, compute_analysis, grid_rois,
                                group_rois, group_values, roi_metric,
                                roi_patch, roi_snr, snapshot, summarize)
from pear.core.attributes import SNR_ID, glv_value, metric_label, quantile_of


def _bright_dark(img):
    """Group 'bright' on feature centers, 'dark' on background corners."""
    rid = 1
    rois = []
    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
        rois.append(ROI(rid, "bright", (c * CELL_W + 22, r * CELL_H + 18, 20, 16)))
        rid += 1
    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
        rois.append(ROI(rid, "dark", (c * CELL_W + 3, r * CELL_H + 3, 10, 8)))
        rid += 1
    groups = [Group("bright", "Bright", "#F59E0B"), Group("dark", "Dark", "#2563EB")]
    return groups, rois


def test_roi_patch_and_metrics():
    img = make_field()
    p = roi_patch(img, (22, 18, 20, 16))
    assert p is not None and p.shape == (16, 20)
    assert roi_patch(img, (-100, -100, 4, 4)) is None      # fully outside
    assert abs(glv_value(p, "glv_mean")
               - roi_metric(img, ROI(1, "g", (22, 18, 20, 16)), "glv_mean")) < 1e-9
    assert quantile_of("glv_q90") == 90 and metric_label("glv_q90") == "GLV Q90"


def test_roi_snr_signal_over_background():
    img = make_field()
    assert roi_snr(img, (22, 18, 20, 16), margin=8) > 0            # bright feature
    assert abs(roi_snr(np.full((60, 60), 100, np.uint8), (20, 20, 10, 10))) < 0.5


def test_group_values_distributions_separate():
    img = make_field()
    groups, rois = _bright_dark(img)
    b = summarize(group_values(img, group_rois(rois, "bright"), "glv_mean"))
    d = summarize(group_values(img, group_rois(rois, "dark"), "glv_mean"))
    assert b["mean"] - d["mean"] > 50 and b["n"] == 4 and d["n"] == 4


def test_grid_rois():
    g = grid_rois((10, 10, 120, 90), 2, 3)
    assert len(g) == 6
    for (x, y, w, h) in g:
        assert w >= 2 and h >= 2 and 10 <= x <= 130


def test_compute_analysis_between_and_within():
    img = make_field()
    groups, rois = _bright_dark(img)
    res = compute_analysis(img, groups, rois, ["glv_mean", SNR_ID], "between", None)
    assert res.empty is None
    assert len(res.charts) == 2 and len(res.charts[0].series) == 2
    assert len(res.table_rows) == 2
    within = compute_analysis(img, groups, rois, ["glv_mean"], "within", "bright")
    assert within.empty is None and len(within.charts[0].series) == 1


def test_compute_analysis_empty_paths():
    img = make_field()
    groups, rois = _bright_dark(img)
    only_one = [r for r in rois if r.gid == "bright"]
    assert compute_analysis(img, groups, only_one, ["glv_mean"], "between", None).empty
    assert compute_analysis(None, groups, rois, ["glv_mean"], "between", None).empty
    assert compute_analysis(img, groups, rois, [], "between", None).empty


def test_snapshot_isolates_from_mutation():
    groups, rois = _bright_dark(make_field())
    gs, rs = snapshot(groups, rois)
    rois[0].rect = (0, 0, 1, 1)
    groups[0].name = "changed"
    assert rs[0].rect != (0, 0, 1, 1) and gs[0].name == "Bright"
