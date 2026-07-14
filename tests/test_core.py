"""Headless core tests (no Qt) for the group/ROI analysis model."""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.make_sample import CELL_H, CELL_W, make_field
from pear.core.analysis import (ROI, Group, compute_analysis, grid_between,
                                group_outliers, group_rois, group_snr,
                                group_values, groups_from_json, groups_to_json,
                                heat_color, roi_metric, roi_patch, rois_from_json,
                                rois_to_json, snapshot, summarize)
from pear.core.attributes import SNR_ID, glv_value, metric_label, quantile_of


def _bright_dark(img):
    """Group 'bright' on feature centers, 'dark' on background corners.

    Each group's first ROI is tagged the SNR target (rids 1 and 5).
    """
    rid = 1
    rois = []
    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
        rois.append(ROI(rid, "bright", (c * CELL_W + 22, r * CELL_H + 18, 20, 16)))
        rid += 1
    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
        rois.append(ROI(rid, "dark", (c * CELL_W + 3, r * CELL_H + 3, 10, 8)))
        rid += 1
    groups = [Group("bright", "Bright", "#F59E0B", target_rid=1),
              Group("dark", "Dark", "#2563EB", target_rid=5)]
    return groups, rois


def test_roi_patch_and_metrics():
    img = make_field()
    p = roi_patch(img, (22, 18, 20, 16))
    assert p is not None and p.shape == (16, 20)
    assert roi_patch(img, (-100, -100, 4, 4)) is None      # fully outside
    assert abs(glv_value(p, "glv_mean")
               - roi_metric(img, ROI(1, "g", (22, 18, 20, 16)), "glv_mean")) < 1e-9
    assert quantile_of("glv_q90") == 90 and metric_label("glv_q90") == "GLV Q90"


def test_group_snr_within_target_vs_reference():
    img = make_field()
    # target on a bright feature, references on dark background
    tgt = ROI(1, "g", (22, 18, 20, 16))
    refs = [ROI(2, "g", (3, 3, 10, 8)), ROI(3, "g", (CELL_W + 3, 3, 10, 8))]
    rois = [tgt] + refs
    snr = group_snr(img, rois, target_rid=1)
    assert snr is not None and snr > 0                    # bright over dark
    assert group_snr(img, rois, target_rid=None) is None  # no target
    assert group_snr(img, [tgt], target_rid=1) is None     # no reference
    flat = np.full((60, 60), 100, np.uint8)                # reference has no spread
    assert group_snr(flat, [ROI(1, "g", (20, 20, 10, 10)),
                            ROI(2, "g", (0, 0, 10, 10))], 1) is None


def test_group_values_distributions_separate():
    img = make_field()
    groups, rois = _bright_dark(img)
    b = summarize(group_values(img, group_rois(rois, "bright"), "glv_mean"))
    d = summarize(group_values(img, group_rois(rois, "dark"), "glv_mean"))
    assert b["mean"] - d["mean"] > 50 and b["n"] == 4 and d["n"] == 4


def test_grid_between_interpolates_anchor_centers():
    g = grid_between((20, 20), (200, 140), 2, 3, 28, 28)
    assert len(g) == 6
    x0, y0, w0, h0 = g[0]
    xl, yl, wl, hl = g[-1]
    assert w0 == 28 and h0 == 28
    # first ROI centred on the top-left anchor, last on the bottom-right anchor
    assert abs((x0 + 14) - 20) <= 1 and abs((y0 + 14) - 20) <= 1
    assert abs((xl + 14) - 200) <= 1 and abs((yl + 14) - 140) <= 1


def test_compute_analysis_between_and_within():
    img = make_field()
    groups, rois = _bright_dark(img)
    res = compute_analysis(img, groups, rois, ["glv_mean", SNR_ID], "between", None)
    assert res.empty is None
    assert len(res.charts) == 2 and len(res.charts[0].series) == 2
    assert len(res.table_rows) == 2
    # SNR is one value per group (targets are set in _bright_dark)
    snr_chart = res.charts[1]
    assert all(s.values.size == 1 for s in snr_chart.series)
    within = compute_analysis(img, groups, rois, ["glv_mean"], "within", "bright")
    assert within.empty is None and len(within.charts[0].series) == 1


def test_compute_analysis_empty_paths():
    img = make_field()
    groups, rois = _bright_dark(img)
    only_one = [r for r in rois if r.gid == "bright"]
    assert compute_analysis(img, groups, only_one, ["glv_mean"], "between", None).empty
    assert compute_analysis(None, groups, rois, ["glv_mean"], "between", None).empty
    assert compute_analysis(img, groups, rois, [], "between", None).empty


def test_group_outliers_flags_within_group():
    img = make_field()
    # four ROIs on bright features + one on dark background (the outlier)
    rois = [ROI(1, "g", (22, 18, 20, 16)),
            ROI(2, "g", (CELL_W + 22, 18, 20, 16)),
            ROI(3, "g", (2 * CELL_W + 22, 18, 20, 16)),
            ROI(4, "g", (22, CELL_H + 18, 20, 16)),
            ROI(5, "g", (3, 3, 10, 8))]           # dark → outlier in glv_mean
    out = group_outliers(img, rois, "glv_mean")
    assert 5 in out and 1 not in out
    # a group too small for a stable IQR is skipped
    assert group_outliers(img, rois[:3], "glv_mean") == set()


def test_heat_color_ramp_and_clamp():
    assert heat_color(0.0) == "#2563EB"       # cool end
    assert heat_color(0.5) == "#F59E0B"       # amber middle
    assert heat_color(1.0) == "#DC2626"       # warm end
    assert heat_color(-5) == "#2563EB" and heat_color(9) == "#DC2626"  # clamped


def test_project_model_roundtrip():
    groups, rois = _bright_dark(make_field())
    g2 = groups_from_json(groups_to_json(groups))
    r2 = rois_from_json(rois_to_json(rois))
    assert [ (g.gid, g.name, g.color, g.target_rid) for g in g2 ] == \
           [ (g.gid, g.name, g.color, g.target_rid) for g in groups ]
    assert r2[0].rect == rois[0].rect and r2[0].rid == rois[0].rid
    assert isinstance(r2[0].rect, tuple)


def test_snapshot_isolates_from_mutation():
    groups, rois = _bright_dark(make_field())
    gs, rs = snapshot(groups, rois)
    rois[0].rect = (0, 0, 1, 1)
    groups[0].name = "changed"
    groups[0].target_rid = 999
    assert rs[0].rect != (0, 0, 1, 1) and gs[0].name == "Bright"
    assert gs[0].target_rid == 1              # snapshot copies the SNR target
