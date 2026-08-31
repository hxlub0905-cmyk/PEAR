"""Headless core tests (no Qt) for the group/ROI analysis model."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from examples.make_sample import CELL_H, CELL_W, make_field
from pear.core.analysis import (ROI, Group, attribute_separability, cell_edges,
                                cohens_d, heat_cells,
                                compute_analysis, grid_between, group_outliers,
                                group_rois, group_snr, group_values,
                                groups_from_json, groups_to_json, heat_color,
                                group_positions, linear_trend, pixel_hist,
                                profile_by_position, roi_center, roi_metric,
                                roi_patch, rois_from_json, rois_to_json,
                                snapshot, summarize, uniformity)
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


def test_separability_and_cohens_d():
    # well-separated groups → high η² and large |d|
    a = np.array([10.0, 11, 9, 10, 12])
    b = np.array([50.0, 51, 49, 52, 48])
    eta = attribute_separability([a, b])
    assert eta is not None and eta > 0.9
    assert abs(cohens_d(a, b)) > 5
    # identical groups → ~0 separability, d ≈ 0
    assert attribute_separability([a, a.copy()]) < 0.05
    assert abs(cohens_d(a, a.copy())) < 1e-9
    # degenerate inputs
    assert attribute_separability([a]) is None
    assert cohens_d([1.0], [2.0, 3.0]) is None


def test_pixel_hist_shape_and_counts():
    counts, edges = pixel_hist(np.full((4, 5), 100, np.uint8), bins=16)
    assert counts.sum() == 20 and len(edges) == 17
    assert counts[np.digitize(100, edges) - 1] == 20      # all in one bin


def test_compute_analysis_ranking_and_heat():
    img = make_field()
    groups, rois = _bright_dark(img)
    res = compute_analysis(img, groups, rois, ["glv_mean", "glv_std", SNR_ID],
                           "between", None)
    # heatmap: 2 groups × 3 metrics
    assert res.heat is not None
    assert len(res.heat["values"]) == 2 and len(res.heat["values"][0]) == 3
    # ranking excludes SNR and is sorted by η² desc
    labels = [r[0] for r in res.ranking]
    assert "SNR" not in labels and len(res.ranking) == 2
    etas = [r[1] for r in res.ranking if r[1] is not None]
    assert etas == sorted(etas, reverse=True)


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


def test_roi_center_and_group_positions():
    rois = [ROI(1, "g", (10, 20, 10, 10)), ROI(2, "g", (30, 20, 10, 10))]
    assert roi_center(rois[0].rect) == (15.0, 25.0)
    assert list(group_positions(rois, "x")) == [15.0, 35.0]
    assert list(group_positions(rois, "y")) == [25.0, 25.0]
    # anything but "y" means the X axis
    assert list(group_positions(rois, "X")) == [15.0, 35.0]


def test_cell_edges_tile_the_axis_without_gaps():
    c, e = cell_edges([10.0, 40.0, 70.0, 10.0])   # duplicates are one centre
    assert list(c) == [10.0, 40.0, 70.0]
    assert list(e) == pytest.approx([-5.0, 25.0, 55.0, 85.0])
    # every centre sits inside its own cell and the cells share their edges
    assert all(e[i] < c[i] < e[i + 1] for i in range(c.size))


def test_cell_edges_absorb_rounded_centres_and_uneven_gaps():
    """Integer ROI rects round the centres — cells must still meet."""
    c, e = cell_edges([12.0, 31.0, 51.0, 70.0])
    assert list(np.diff(e)) == pytest.approx([19.0, 19.5, 19.5, 19.0])
    assert float(e[-1] - e[0]) == pytest.approx(77.0)   # one unbroken span
    # a missing ROI widens that cell instead of opening a hole
    c, e = cell_edges([0.0, 10.0, 40.0])
    assert list(e) == pytest.approx([-5.0, 5.0, 25.0, 55.0])


def test_cell_edges_on_degenerate_input():
    c, e = cell_edges([7.0, 7.0])          # one distinct centre, no neighbour
    assert list(c) == [7.0] and list(e) == [6.5, 7.5]
    c, e = cell_edges([])
    assert c.size == 0 and e.size == 0


def test_heat_cells_tile_the_field_and_clip_to_the_image():
    rois = [ROI(1, "A", (10, 10, 10, 10)), ROI(2, "A", (50, 10, 10, 10)),
            ROI(3, "A", (10, 50, 10, 10)), ROI(4, "A", (50, 50, 10, 10))]
    cells = heat_cells(rois)
    assert set(cells) == {1, 2, 3, 4}
    # neighbours share an edge: no gap, no overlap
    assert cells[1][2] == cells[2][0] == pytest.approx(35.0)
    assert cells[1][3] == cells[3][1] == pytest.approx(35.0)
    for r in rois:
        x0, y0, x1, y1 = cells[r.rid]
        cx, cy = roi_center(r.rect)
        assert x0 < cx < x1 and y0 < cy < y1     # the ROI is inside its cell
    clipped = heat_cells(rois, (60, 60))
    assert clipped[1][:2] == (0.0, 0.0)          # nothing spills off the image
    assert clipped[4][2:] == (60.0, 60.0)


def test_heat_cells_on_a_single_roi_and_a_single_row():
    only = heat_cells([ROI(9, "A", (10, 10, 20, 20))])
    assert only[9] == (10.0, 10.0, 30.0, 30.0)   # no neighbour: its own box
    row = heat_cells([ROI(1, "A", (0, 0, 10, 10)), ROI(2, "A", (40, 0, 10, 10))])
    # one row has no Y pitch — the cells borrow the X one and still tile
    assert row[1][2] == row[2][0] == pytest.approx(25.0)
    assert row[1][3] - row[1][1] == pytest.approx(40.0)
    assert heat_cells([]) == {}


def test_linear_trend_recovers_a_known_slope():
    x = np.arange(10, dtype=np.float64)
    fit = linear_trend(x, 3.0 * x + 7.0)
    assert fit is not None
    slope, intercept = fit
    assert slope == pytest.approx(3.0)
    assert intercept == pytest.approx(7.0)
    # a flat profile is slope 0 — the uniform case the tool is built to show
    flat = linear_trend(x, np.full(10, 5.0))
    assert flat is not None and flat[0] == pytest.approx(0.0)
    # degenerate inputs report nothing rather than a bogus tilt
    assert linear_trend([1.0], [2.0]) is None
    assert linear_trend([4.0, 4.0, 4.0], [1.0, 2.0, 3.0]) is None


def test_uniformity_range_and_cv():
    u = uniformity([100.0, 110.0, 90.0])
    assert u["n"] == 3
    assert u["mean"] == pytest.approx(100.0)
    assert u["range"] == pytest.approx(20.0)
    assert u["range_pct"] == pytest.approx(20.0)
    assert u["cv_pct"] == pytest.approx(np.std([100, 110, 90]) / 100 * 100)
    # perfectly flat -> zero spread, and no divide-by-zero on an empty set
    assert uniformity([7.0, 7.0, 7.0])["range"] == 0.0
    assert uniformity([])["n"] == 0
    assert uniformity([0.0, 0.0])["range_pct"] == 0.0


def test_profile_by_position_averages_shared_positions():
    # a grid puts several ROIs at the same X; they collapse to one point
    pos = np.array([10.0, 10.0, 20.0, 20.0])
    val = np.array([4.0, 6.0, 10.0, 20.0])
    cx, cy = profile_by_position(pos, val)
    assert list(cx) == [10.0, 20.0]
    assert list(cy) == [5.0, 15.0]
    assert profile_by_position([], [])[0].size == 0


def test_compute_analysis_carries_roi_positions():
    img = make_field()
    groups = [Group("g1", "A", "#f00"), Group("g2", "B", "#00f")]
    rois = [ROI(1, "g1", (2, 2, 8, 8)), ROI(2, "g1", (30, 2, 8, 8)),
            ROI(3, "g2", (2, 30, 8, 8)), ROI(4, "g2", (30, 30, 8, 8))]
    res = compute_analysis(img, groups, rois, ["glv_mean"], "between", None)
    s = res.charts[0].series[0]
    assert s.pos_x is not None and s.pos_y is not None
    assert s.pos_x.size == s.values.size == 2
    assert list(s.pos_x) == [6.0, 34.0]
    # SNR is one value for the whole group, so it carries no ROI positions
    for g in groups:
        g.target_rid = group_rois(rois, g.gid)[0].rid
    snr_res = compute_analysis(img, groups, rois, ["snr"], "between", None)
    assert snr_res.charts[0].series[0].pos_x is None
