"""Offscreen UI smoke test for the group/ROI analysis app."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest

from examples.make_sample import CELL_H, CELL_W, make_field

QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def app():
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield application


def _two_groups(win):
    """Group A on bright centers, Group B on dark corners."""
    gA = win._active_gid
    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
        win.on_roi_created((c * CELL_W + 22, r * CELL_H + 18, 20, 16))
    win.add_group()
    gB = win._active_gid
    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
        win.on_roi_created((c * CELL_W + 3, r * CELL_H + 3, 10, 8))
    return gA, gB


def test_boot_seeds_group(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "sample_field.png")
    assert len(win._groups) == 1 and win._active_gid == "A"
    assert win._rois == []


def test_controls_disabled_before_image(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    assert not win.rail.grp_add_btn.isEnabled()
    assert not win.rail.grid_btn.isEnabled()
    assert not win.rail.analysis_btn.isEnabled()
    assert not win.stage_bar.isEnabled()
    win.set_image(make_field(), "f.png")
    assert win.rail.grp_add_btn.isEnabled() and win.rail.grid_btn.isEnabled()
    assert win.stage_bar.isEnabled()


def test_add_rois_to_groups(app):
    from pear.ui.main_window import MainWindow
    from pear.core.analysis import group_rois
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gA, gB = _two_groups(win)
    assert len(group_rois(win._rois, gA)) == 4
    assert len(group_rois(win._rois, gB)) == 4


def test_grid_multi_add(app):
    from pear.ui.main_window import MainWindow
    from pear.core.analysis import grid_between, group_rois
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    rects = grid_between((30, 30), (200, 160), 2, 3, 28, 28)   # 2×3 grid
    win.on_grid_committed(rects)
    assert len(group_rois(win._rois, win._active_gid)) == 6


def test_grid_interaction_two_clicks(app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QMouseEvent
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    iv = win.image_view
    iv.resize(500, 400)
    win.set_grid_mode(True)
    # two corner clicks define the bounds, then commit
    p1 = iv._to_widget(30, 30)
    p2 = iv._to_widget(200, 160)
    iv.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, p1,
                                   Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    iv.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, p2,
                                   Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    assert iv._grid_stage == 2
    iv.commit_grid()
    from pear.core.analysis import group_rois
    assert len(group_rois(win._rois, win._active_gid)) == win.rail.grid_shape()[0] * \
        win.rail.grid_shape()[1]


def test_between_analysis_and_export(app, tmp_path):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean", "glv_std"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    from pear.ui.widgets import DistributionChart
    assert win.analysis.body.findChildren(DistributionChart)
    out = tmp_path / "g.csv"
    assert win.export_csv(str(out)) == str(out)
    text = out.read_text(encoding="utf-8-sig")
    assert "Group A" in text and "GLV mean" in text and "summary" in text


def test_within_analysis(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gA, _ = _two_groups(win)
    win.on_cmp_mode("within")
    win.on_within_group(gA)
    win.render_analysis_sync()
    assert gA in win.analysis.sub.text() or "ROIs" in win.analysis.sub.text()


def test_delete_group_removes_its_rois(app):
    from pear.ui.main_window import MainWindow
    from pear.core.analysis import group_rois
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gA, gB = _two_groups(win)
    win.delete_group(gB)
    assert win._group(gB) is None
    assert group_rois(win._rois, gB) == []
    assert len(group_rois(win._rois, gA)) == 4


def test_group_gids_unique_after_delete(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.add_group()
    win.add_group()                       # A, B, C
    assert [g.gid for g in win._groups] == ["A", "B", "C"]
    win.delete_group("B")
    win.add_group()                       # reuses freed "B"
    gids = [g.gid for g in win._groups]
    assert len(gids) == len(set(gids)) and set(gids) == {"A", "B", "C"}


def test_delete_individual_roi(app):
    from pear.ui.main_window import MainWindow
    from pear.core.analysis import group_rois
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((20, 20, 20, 20))
    win.on_roi_created((60, 60, 20, 20))
    gid = win._active_gid
    assert len(group_rois(win._rois, gid)) == 2
    rid = win._rois[0].rid
    win.delete_roi(rid)
    assert len(group_rois(win._rois, gid)) == 1 and win._roi(rid) is None


def test_roi_size_setting_reaches_image_view(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.rail.roi_w.setValue(40)
    win.rail.roi_h.setValue(30)
    assert win.image_view._roi_w == 40 and win.image_view._roi_h == 30
    # a plain click (no drag) drops a box of that size
    from pear.core.analysis import grid_between
    # grid also uses the configured size
    rects = grid_between((30, 30), (200, 160), 2, 2, *win.rail.roi_size())
    assert rects[0][2] == 40 and rects[0][3] == 30


def test_show_metric_on_rois(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((22, 18, 20, 16))
    win.on_show_metric("glv_mean")
    assert win.image_view._roi_values           # one value per ROI
    win.on_show_metric("")
    assert win.image_view._roi_values == {}


def test_color_and_rename(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gA = win._active_gid
    win.set_group_color(gA, "#123456")
    win.rename_group(gA, "round holes")
    assert win._group(gA).color == "#123456"
    assert win._group(gA).name == "round holes"


def test_roi_labels_reindex_after_delete(app):
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((20, 20, 16, 16))
    win.on_roi_created((60, 20, 16, 16))
    win.on_roi_created((100, 20, 16, 16))
    gid = win._active_gid
    mid_rid = group_rois(win._rois, gid)[1].rid
    win.delete_roi(mid_rid)
    assert [r.label for r in group_rois(win._rois, gid)] == ["ROI 1", "ROI 2"]


def test_marquee_select_and_batch_delete(app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QMouseEvent
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    iv = win.image_view
    iv.resize(500, 400)
    win.on_roi_created((20, 20, 16, 16))
    win.on_roi_created((60, 20, 16, 16))
    win.on_roi_created((120, 20, 16, 16))
    gid = win._active_gid
    p1 = iv._to_widget(10, 10)
    p2 = iv._to_widget(90, 60)                    # covers the first two only
    iv.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, p1,
                                   Qt.LeftButton, Qt.LeftButton, Qt.ShiftModifier))
    iv.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, p2,
                                  Qt.NoButton, Qt.LeftButton, Qt.ShiftModifier))
    iv.mouseReleaseEvent(QMouseEvent(QMouseEvent.Type.MouseButtonRelease, p2,
                                     Qt.LeftButton, Qt.NoButton, Qt.ShiftModifier))
    assert len(win._selected_rids) == 2
    win.delete_rois(list(win._selected_rids))
    assert len(group_rois(win._rois, gid)) == 1


def test_heatmap_and_outliers_state(app):
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:      # bright features
        win.on_roi_created((c * CELL_W + 22, r * CELL_H + 18, 20, 16))
    win.on_roi_created((3, 3, 10, 8))                    # dark → outlier
    gid = win._active_gid
    dark_rid = group_rois(win._rois, gid)[-1].rid
    win.on_show_metric("glv_mean")
    win.on_heatmap(True)
    win.on_flag_outliers(True)
    assert win.image_view._heat and win.image_view._heat_legend is not None
    assert dark_rid in win.image_view._outliers
    win.on_heatmap(False)
    win.on_flag_outliers(False)
    assert win.image_view._heat == {} and win.image_view._outliers == set()


def test_keyboard_nudge_duplicate_group_switch(app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((40, 40, 20, 20))
    iv = win.image_view
    rid = win._active_rid
    x0 = win._roi(rid).rect[0]
    iv.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Right, Qt.NoModifier))
    assert win._roi(rid).rect[0] == x0 + 1
    iv.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Right,
                              Qt.ShiftModifier))
    assert win._roi(rid).rect[0] == x0 + 11
    n = len(group_rois(win._rois, win._active_gid))
    win.duplicate_roi(rid)
    assert len(group_rois(win._rois, win._active_gid)) == n + 1
    win.add_group()                                   # A, B (active B)
    win.select_group_by_index(0)
    assert win._active_gid == "A"


def test_hover_sync_state(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((40, 40, 20, 20))
    rid = win._active_rid
    win.image_view.set_hover(rid)
    assert win.image_view._hover_rid == rid
    win.image_view.set_hover(-1)
    assert win.image_view._hover_rid == -1
    win.rail.set_hovered_roi(rid)                     # canvas → list, no crash


def test_chart_option_toggles(app):
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    ap = win.analysis
    ap._pick_ctype("hist")
    ap._pick_ctype("box")
    ap.points_chk.setChecked(False)
    ap.whiskers_chk.setChecked(False)
    app.processEvents()          # flush deleteLater so stale charts are gone
    charts = ap.body.findChildren(DistributionChart)
    assert any(not c._opts["points"] and not c._opts["whiskers"]
               for c in charts)


def test_ranking_and_heatmap_render(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean", "glv_std"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    res = win.analysis._last_result
    assert res.ranking and res.heat is not None
    assert len(res.heat["values"]) == 2


def test_roi_inspector_shows_patch(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((22, 18, 20, 16))
    win.open_inspector(win._active_rid)
    assert win.inspector_window.isVisible()
    assert win.inspector._patch is not None
    assert win.inspector._patch.shape == (16, 20)
    win.on_roi_created((3, 3, 10, 8))                 # inspector tracks active ROI
    win.select_roi(win._active_rid)
    assert win.inspector._patch.shape == (8, 10)


def test_project_save_open_roundtrip(app, tmp_path):
    import cv2
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    ipath = tmp_path / "field.png"
    cv2.imwrite(str(ipath), make_field())
    win = MainWindow()
    win.load_path(str(ipath))
    win.rename_group(win._active_gid, "round holes")
    win.on_roi_created((22, 18, 20, 16))
    win.on_roi_created((3, 3, 10, 8))
    win.set_metrics(["glv_mean", "glv_std"])
    proj = tmp_path / "p.pear.json"
    assert win.save_project(str(proj)) == str(proj)

    win2 = MainWindow()
    assert win2.open_project(str(proj)) == str(proj)
    assert win2._image is not None
    assert win2._group("A").name == "round holes"
    a_rois = group_rois(win2._rois, "A")
    assert len(a_rois) == 2
    assert win2._metrics == ["glv_mean", "glv_std"]


def _grid_group(win, rows=3, cols=4):
    """A group whose ROIs tile the field, so positions vary on both axes."""
    from pear.core.analysis import grid_between
    win.add_group()
    for r in grid_between((14, 12), (110, 70), rows, cols, 8, 8):
        win.on_roi_created(r)
    return win._active_gid


def test_position_profile_and_heatmap_render(app):
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gid = _grid_group(win)
    win.set_metrics(["glv_mean"])
    win.on_cmp_mode("within")
    win.on_within_group(gid)
    win.render_analysis_sync()
    ap = win.analysis

    for ctype in ("position", "map"):
        ap._pick_ctype(ctype)
        app.processEvents()
        charts = [c for c in ap.body.findChildren(DistributionChart)
                  if c._ctype == ctype]
        assert charts, f"no {ctype} chart rendered"
        c = charts[0]
        assert c._series and c._series[0]["pos_x"].size == len(win._rois)
        assert c._series[0]["pos_y"].size == len(win._rois)
        c.grab()                       # exercises the painter
    # the axis toggle is render-only: no recompute, positions are already there
    ap._pick_ctype("position")
    ap.axis_box.setCurrentIndex(1)
    app.processEvents()
    assert ap.chart_state() == ("position", "y")
    for c in ap.body.findChildren(DistributionChart):
        c.grab()


def test_rebuilt_lists_leave_no_stale_rows(app):
    """A rebuilt list must not keep painting its old rows over the card.

    ``deleteLater`` alone leaves them visible until the event loop runs, and
    they cover the Groups card's title and Add button while they linger. They
    must be *hidden*, not reparented: these lists are rebuilt from their own
    rows' signals, and a widget reparented to None mid-event becomes a stray
    top-level window and then a crash.
    """
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import _ItemRow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.add_group()
    win.on_roi_created((10, 10, 12, 12))
    win.on_roi_created((40, 10, 12, 12))
    for _ in range(3):
        win._refresh()                       # no processEvents in between
    grp_card = win.rail.grp_add_btn.parentWidget()

    def live(host):
        return [r for r in host.findChildren(_ItemRow) if not r.isHidden()]

    assert len(live(grp_card)) == len(win._groups)
    roi_rows = len(group_rois(win._rois, win._active_gid))
    assert len(live(win.rail.roi_host.parentWidget())) == roi_rows
    # nothing was turned into a window on the way out
    assert all(r.parentWidget() is not None
               for r in grp_card.findChildren(_ItemRow))

    # a row's own click rebuilds the list it lives in — the path that used to
    # flash a blank window per click and then take the app down
    rid = group_rois(win._rois, win._active_gid)[0].rid
    for _ in range(5):
        win.select_roi(rid)
        win.rail.set_hovered_roi(rid)
    app.processEvents()
    assert len(live(win.rail.roi_host.parentWidget())) == roi_rows


def test_value_labels_only_where_they_fit(app):
    """A label wider than its ROI is dropped — unless that ROI is hovered."""
    from PySide6.QtCore import QRectF
    from pear.ui.image_view import label_rect
    big, small = QRectF(0, 40, 60, 20), QRectF(0, 40, 8, 6)
    inside = label_rect(big, 30, 12, False)
    assert inside is not None and big.contains(inside)
    assert label_rect(small, 30, 12, False) is None      # would bury the box
    floated = label_rect(small, 30, 12, True)            # hovered: float it
    assert floated is not None and floated.bottom() <= small.top()
    # an ROI at the very top has no room above — the label goes below instead
    at_top = label_rect(QRectF(0, 0, 8, 6), 30, 12, True)
    assert at_top is not None and at_top.top() >= 6


def test_fit_survives_a_resize_until_the_user_zooms(app):
    """set_image() fits against the layout's first guess at the widget size."""
    from pear.ui.image_view import ImageView
    iv = ImageView()
    iv.resize(320, 240)                       # the "first guess"
    iv.show()                                 # hidden widgets defer resizes
    app.processEvents()
    iv.set_image(make_field())
    small = iv._scale
    iv.resize(900, 700)                       # …then the real one
    app.processEvents()
    assert iv._fitted and iv._scale > small
    pm = iv._pixmap
    assert iv._offset.x() == pytest.approx(
        (iv.width() - pm.width() * iv._scale) / 2.0, abs=1.0)
    assert iv._offset.y() == pytest.approx(
        (iv.height() - pm.height() * iv._scale) / 2.0, abs=1.0)
    iv.zoom_in()
    assert not iv._fitted
    scale, off = iv._scale, iv._offset
    iv.resize(700, 500)
    app.processEvents()
    assert iv._scale == scale and iv._offset == off       # a zoom is not undone


def test_stage_bar_drives_the_overlays_and_the_field_fill(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _grid_group(win, 3, 3)
    sb = win.stage_bar
    assert not sb.alpha_spin.isEnabled()             # nothing painted yet
    sb.show_combo.setCurrentIndex(sb.show_combo.findData("glv_mean"))
    assert win._show_metric == "glv_mean" and win.image_view._roi_values

    # the field paints on its own — it does not wait for "heat boxes"
    sb.cells_chk.setChecked(True)
    assert sb.alpha_spin.isEnabled() and win.image_view._heat
    cells = win.image_view._heat_cells
    assert len(cells) == len(win._rois)
    h, w = make_field().shape[:2]
    for x0, y0, x1, y1 in cells.values():            # clipped to the image
        assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h

    sb.cells_chk.setChecked(False)                   # …and boxes on their own
    assert win.image_view._heat == {} and win.image_view._heat_cells == {}
    sb.heatmap_chk.setChecked(True)
    assert win.image_view._heat and win.image_view._heat_cells == {}
    sb.heatmap_chk.setChecked(False)
    assert win.image_view._heat == {} and not sb.alpha_spin.isEnabled()


def test_roi_list_shows_and_sorts_by_the_shown_metric(app):
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gid = _grid_group(win, 2, 3)
    win.stage_bar.show_combo.setCurrentIndex(
        win.stage_bar.show_combo.findData("glv_mean"))
    rois = group_rois(win._rois, gid)
    assert len(win._values) == len(rois)

    def order(mode):
        win.on_roi_order(mode)
        return [r.rid for r in win._ordered_rois(rois)]

    assert order("placed") == [r.rid for r in rois]
    asc = order("asc")
    assert [win._values[r] for r in asc] == sorted(win._values[r] for r in asc)
    assert order("desc") == asc[::-1]


def test_status_bar_carries_the_headline_numbers(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _grid_group(win, 2, 3)
    text = win.summary_lbl.text()
    assert f"{len(win._groups)} groups" in text and "6 ROIs" in text
    win.stage_bar.show_combo.setCurrentIndex(
        win.stage_bar.show_combo.findData("glv_mean"))
    text = win.summary_lbl.text()
    assert "GLV mean" in text and "CV" in text and "range" in text


def test_box_chart_can_give_each_group_its_own_scale(app):
    """A group with a tiny spread beside a distant one is flat on one axis."""
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    ap = win.analysis
    ap._pick_ctype("box")
    app.processEvents()
    assert not ap.ownscale_chk.isHidden()
    ap.ownscale_chk.setChecked(True)
    app.processEvents()
    charts = [c for c in ap.body.findChildren(DistributionChart)
              if c._opts.get("own_scale")]
    assert charts
    for c in charts:
        c.grab()                       # exercises the per-lane painter
    ap._pick_ctype("map")              # only the box plot offers it
    assert ap.ownscale_chk.isHidden()


def test_align_buttons_tidy_the_selection_then_the_group(app):
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.add_group()
    for rect in ((10, 10, 10, 10), (13, 40, 10, 10), (9, 100, 10, 10)):
        win.on_roi_created(rect)
    rois = group_rois(win._rois, win._active_gid)

    win._selected_rids = {rois[0].rid, rois[1].rid}   # only the selection moves
    win.rail.align_btns["left"].click()
    assert [r.rect[0] for r in rois] == [10, 10, 9]

    win._selected_rids = set()                        # …then the whole group
    win.rail.align_btns["left"].click()
    assert [r.rect[0] for r in rois] == [9, 9, 9]
    win.rail.align_btns["disty"].click()
    assert [r.rect[1] for r in rois] == [10, 55, 100]  # gaps evened out
    before = [r.rect for r in rois]
    win.rail.align_btns["left"].click()                # already aligned: no-op
    assert [r.rect for r in rois] == before


def test_map_draws_touching_cells_and_optional_values(app):
    """Cell mode tiles the field; the dot fallback and labels still paint."""
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gid = _grid_group(win)
    win.set_metrics(["glv_mean"])
    win.on_cmp_mode("within")
    win.on_within_group(gid)
    win.render_analysis_sync()
    ap = win.analysis
    ap._pick_ctype("map")
    app.processEvents()
    assert not ap.cells_chk.isHidden() and not ap.mapval_chk.isHidden()

    def maps():
        # a re-render leaves the previous charts pending deleteLater, so match
        # any live one rather than assuming which comes first
        return [c for c in ap.body.findChildren(DistributionChart)
                if c._ctype == "map"]

    assert any(c._opts["cells"] for c in maps())
    ap.mapval_chk.setChecked(True)             # values printed inside the cells
    app.processEvents()
    assert any(c._opts["map_values"] for c in maps())
    for c in maps():
        c.grab()
    ap.cells_chk.setChecked(False)             # back to separate dots
    app.processEvents()
    assert not ap.mapval_chk.isEnabled()
    dots = [c for c in maps() if not c._opts["cells"]]
    assert dots
    for c in dots:
        c.grab()
        # the toggles are render-only — the position data is untouched
        assert c._series[0]["pos_x"].size == len(win._rois)


def test_heat_map_lattice_gives_every_cell_the_same_size(app):
    """Uneven pitch must not hand neighbouring cells different areas."""
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.add_group()
    gid = win._active_gid
    for row, y in enumerate((20, 90, 200)):          # deliberately uneven rows
        for col, x in enumerate((20, 60, 200, 260)): # …and uneven columns
            win.on_roi_created((x, y, 16, 14))
    win.set_metrics(["glv_mean"])
    win.on_cmp_mode("within")
    win.on_within_group(gid)
    win.render_analysis_sync()
    ap = win.analysis
    ap._pick_ctype("map")
    app.processEvents()
    assert not ap.equal_chk.isHidden() and ap.equal_chk.isChecked()

    def maps():
        return [c for c in ap.body.findChildren(DistributionChart)
                if c._ctype == "map"]

    assert any(c._opts["equal_cells"] for c in maps())
    for c in maps():
        c.grab()                       # exercises the lattice painter
    ap.equal_chk.setChecked(False)     # back to true midline tiling
    app.processEvents()
    assert any(not c._opts["equal_cells"] for c in maps())
    for c in maps():
        c.grab()
    ap.cells_chk.setChecked(False)     # dots have no area to equalise
    assert not ap.equal_chk.isEnabled()


def test_overlay_toggles_are_independent(app, tmp_path):
    """Value text, heat fill and its opacity switch one at a time."""
    import json
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _grid_group(win, 2, 3)
    win.on_show_metric("glv_mean")
    assert win.image_view._roi_values                 # numbers on by default
    win.on_heatmap(True)
    win.on_show_values(False)                         # colour only, no numbers
    assert win.image_view._heat and win.image_view._roi_values == {}
    win.on_heat_alpha(30)
    assert win.image_view._heat_alpha == round(30 * 2.55)
    win.on_show_values(True)
    assert win.image_view._roi_values

    win.on_show_values(False)
    win.on_heat_field(True)
    win.on_roi_order("desc")
    out = tmp_path / "p.pear.json"
    win.save_project(str(out))
    win2 = MainWindow()
    win2.set_image(make_field(), "f.png")
    win2._restore_project(json.loads(out.read_text(encoding="utf-8")))
    assert win2._show_values is False and win2._heat_alpha == 30
    assert win2._heat_field is True and win2._roi_order == "desc"
    assert win2.stage_bar.cells_chk.isChecked()
    assert win2.rail.order_box.currentData() == "desc"
    assert win2.stage_bar.alpha_spin.value() == 30
    assert win2.image_view._roi_values == {}
    assert win2.image_view._heat_alpha == round(30 * 2.55)


def test_nice_step_lands_on_round_numbers():
    from pear.ui.widgets import _nice_step
    assert _nice_step(30, 4) == 10.0            # 0 · 10 · 20 · 30, not 7.5
    assert _nice_step(100, 4) == 25.0
    assert _nice_step(8, 4) == 2.0
    assert _nice_step(0.4, 4) == 0.1
    assert _nice_step(0, 4) == 1.0              # degenerate input never breaks
    assert _nice_step(float("nan"), 4) == 1.0


def test_histogram_bins_and_percent_are_render_only(app):
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    ap = win.analysis
    ap._pick_ctype("hist")
    app.processEvents()
    assert not ap.bins_spin.isHidden() and not ap.pct_chk.isHidden()
    ap.bins_spin.setValue(12)
    ap.pct_chk.setChecked(True)
    app.processEvents()
    hists = [c for c in ap.body.findChildren(DistributionChart)
             if c._ctype == "hist" and c._opts.get("bins") == 12]
    assert hists and hists[-1]._opts["hist_pct"] is True
    for c in hists:
        c.grab()                       # exercises the percent painter
    ap._pick_ctype("box")              # bins/% belong to the histogram alone
    assert ap.bins_spin.isHidden() and ap.pct_chk.isHidden()


def test_distribution_charts_keep_a_printable_shape(app):
    """A figure at 4:3-ish, not a banner stretched across the window."""
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    win.analysis_window.resize(1400, 900)
    win.analysis_window.show()
    win.analysis._pick_ctype("hist")
    app.processEvents()
    app.processEvents()
    charts = [c for c in win.analysis.body.findChildren(DistributionChart)
              if c._ctype == "hist" and c.isVisible()]
    assert charts
    c = charts[-1]
    assert 340 <= c.width() <= 720                     # capped, not stretched
    assert c.height() == pytest.approx(c.heightForWidth(c.width()), abs=2)
    # a profile runs the full width, so it needs a ratio of its own or it
    # comes out as a letterbox where a tilt and a flat line look alike
    win.analysis._pick_ctype("position")
    app.processEvents()
    app.processEvents()
    prof = [c for c in win.analysis.body.findChildren(DistributionChart)
            if c._ctype == "position" and c.isVisible()]
    assert prof
    c = prof[-1]
    assert c.hasHeightForWidth()
    assert c.height() >= 300 and c.height() >= c.width() * 0.5


def test_chart_settings_rename_relabel_and_lock_the_scales(app, tmp_path):
    """Titles, axis names, tick counts and locked ranges — and they persist."""
    import json
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import ChartSettingsDialog, DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean", "glv_median"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    ap = win.analysis
    ap._pick_ctype("hist")
    app.processEvents()

    dlg = ChartSettingsDialog(None, ["GLV mean", "GLV median"], ap.chart_style())
    dlg._title_edits["GLV mean"].setText("Figure 1 — layer brightness")
    dlg.x_edit.setText("grey level (DN)")
    dlg.y_edit.setText("ROIs")
    dlg.xt_spin.setValue(7)
    dlg.yt_spin.setValue(4)
    dlg.v_auto.setChecked(False)
    dlg.v_lo.setValue(50.0)
    dlg.v_hi.setValue(200.0)
    style = dlg.result_style()
    assert style["titles"] == {"GLV mean": "Figure 1 — layer brightness"}
    assert style["xticks"] == 7 and style["yticks"] == 4
    assert (style["vmin"], style["vmax"]) == (50.0, 200.0)

    ap.set_chart_style(style)
    app.processEvents()
    charts = [c for c in ap.body.findChildren(DistributionChart)
              if c._ctype == "hist" and c._title == "GLV mean"]
    assert charts
    c = charts[-1]
    assert c.title_text() == "Figure 1 — layer brightness"
    # the other chart keeps its own name; only the axes are shared
    other = [x for x in ap._chart_widgets if x._title == "GLV median"][0]
    assert other.title_text() == "GLV median"
    assert c._st("xlabel") == "grey level (DN)"
    assert c._range() == (50.0, 200.0)          # locked, not the data's range
    assert c._nticks("xticks", 5) == 7
    c.grab()                                     # the painter honours all of it
    # the export menu follows the new name
    assert any("Figure 1" in a.text() for a in ap._image_menu.actions())

    out = tmp_path / "p.pear.json"
    win.save_project(str(out))
    win2 = MainWindow()
    win2.set_image(make_field(), "f.png")
    win2._restore_project(json.loads(out.read_text(encoding="utf-8")))
    assert win2.analysis.chart_style()["titles"]["GLV mean"].startswith("Figure 1")
    assert win2.analysis.chart_style()["vmax"] == 200.0

    dlg._reset()                                 # Reset clears every override
    assert dlg.result_style() == {"xticks": 5, "yticks": 5, "font_pt": 8.0,
                                  "point_size": 3.2, "line_width": 2.2}


def test_heat_scale_locks_the_image_overlay(app, tmp_path):
    """A locked range makes the same colour mean the same grey level."""
    import json
    from pear.core.analysis import heat_color
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _grid_group(win, 2, 3)
    sb = win.stage_bar
    sb.show_combo.setCurrentIndex(sb.show_combo.findData("glv_mean"))
    sb.heatmap_chk.setChecked(True)
    auto = dict(win.image_view._heat)
    assert set(auto.values()) & {heat_color(0.0)}      # auto stretches to min

    win.on_heat_range((0.0, 255.0))
    locked = win.image_view._heat
    assert locked != auto
    rid, v = next(iter(win._values.items()))
    assert locked[rid] == heat_color(v / 255.0)        # the value's own place
    assert win.image_view._heat_legend[:2] == (0.0, 255.0)

    out = tmp_path / "p.pear.json"
    win.save_project(str(out))
    win2 = MainWindow()
    win2.set_image(make_field(), "f.png")
    win2._restore_project(json.loads(out.read_text(encoding="utf-8")))
    assert win2._heat_range == (0.0, 255.0)
    assert win2.stage_bar.heat_range() == (0.0, 255.0)
    assert "255" in win2.stage_bar.scale_btn.text()    # the button says so

    win.on_heat_range(None)                            # back to auto
    assert win.image_view._heat == auto


def test_chart_text_and_marks_are_adjustable(app):
    """Axis ink, text size, point size and line width all come from the style."""
    from PySide6.QtGui import QColor
    from pear.ui import theme
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import ChartSettingsDialog, DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    ap = win.analysis
    ap._pick_ctype("box")
    app.processEvents()
    c = [x for x in ap._chart_widgets if x._ctype == "box"][-1]
    # dark by default: a light grey tick label is not there on a projector
    assert c._axis_ink() == QColor(theme.INK)
    assert c._font().pointSizeF() == pytest.approx(8.0, abs=0.5)

    dlg = ChartSettingsDialog(None, ["GLV mean"], {})
    dlg.font_spin.setValue(12.0)
    dlg.point_spin.setValue(6.0)
    dlg.line_spin.setValue(4.0)
    state = dlg._colors["point_color"]
    state["color"] = "#123456"
    state["box"].setChecked(False)
    style = dlg.result_style()
    assert style["font_pt"] == 12.0 and style["point_size"] == 6.0
    assert style["line_width"] == 4.0 and style["point_color"] == "#123456"

    ap.set_chart_style(style)
    app.processEvents()
    c = [x for x in ap._chart_widgets if x._ctype == "box"][-1]
    assert c._font().pointSizeF() == pytest.approx(12.0, abs=0.5)
    assert c._line_w(2.2) == 4.0
    assert c._mark_color("point_color", "#FF0000") == QColor("#123456")
    assert c._mark_color("line_color", "#FF0000") == QColor("#FF0000")  # auto
    c.grab()                                   # the painter reads all of it

    dlg._reset()
    back = dlg.result_style()
    assert back["font_pt"] == 8.0 and "point_color" not in back


def test_right_drag_pans_while_placing_a_grid(app):
    """Reaching the far corner is exactly when panning matters."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.set_grid_mode(True)
    iv = win.image_view
    before = QPointF(iv._offset)
    start, end = QPointF(120.0, 90.0), QPointF(180.0, 130.0)
    iv.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, start,
                                   Qt.RightButton, Qt.RightButton,
                                   Qt.NoModifier))
    iv.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, end,
                                  Qt.NoButton, Qt.RightButton, Qt.NoModifier))
    iv.mouseReleaseEvent(QMouseEvent(QMouseEvent.Type.MouseButtonRelease, end,
                                     Qt.RightButton, Qt.NoButton,
                                     Qt.NoModifier))
    assert iv._offset.x() == pytest.approx(before.x() + 60.0)
    assert iv._offset.y() == pytest.approx(before.y() + 40.0)
    assert iv._grid_stage == 0        # panning placed no grid anchor
    assert win._rois == []


def test_export_chart_image_writes_png_and_svg(app, tmp_path):
    from pear.ui.main_window import MainWindow
    from pear.ui.widgets import DistributionChart
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    ap = win.analysis
    win.analysis_window.resize(1200, 800)
    win.analysis_window.show()
    ap._pick_ctype("hist")
    app.processEvents()
    app.processEvents()
    assert ap.image_btn.isEnabled()

    png = tmp_path / "fig.png"
    assert win.export_chart_image("charts", str(png)) == str(png)
    from PySide6.QtGui import QImage
    img = QImage(str(png))
    chart = [c for c in ap.body.findChildren(DistributionChart)
             if c._ctype == "hist" and c.isVisible()][-1]
    # only the figure travels, at 3× — no dead margin from the layout's slack
    assert img.width() == chart.width() * 3
    assert img.height() == chart.height() * 3

    svg = tmp_path / "fig.svg"
    if win.export_chart_image("charts", str(svg)) is not None:  # QtSvg optional
        text = svg.read_text(encoding="utf-8")
        assert "<svg" in text and f"{chart.width()} {chart.height()}" in text


def test_every_results_section_exports(app, tmp_path):
    """Between-groups has four sections; each is offered and each writes."""
    from PySide6.QtGui import QImage
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.set_metrics(["glv_mean", "glv_median"])
    win.on_cmp_mode("between")
    win.render_analysis_sync()
    ap = win.analysis
    win.analysis_window.resize(1200, 900)
    win.analysis_window.show()
    app.processEvents()
    app.processEvents()
    scopes = ap.scopes_available()
    assert set(scopes) == {"charts", "ranking", "heat", "table", "all"}
    assert ap.image_btn.isEnabled()
    # two metrics → two figures, each offered on its own under Charts
    assert [a.text() for a in ap._image_menu.actions()] == [
        "Charts…", "    GLV mean…", "    GLV median…", "Attribute ranking…",
        "Group × metric heatmap…", "Summary table…", "Everything…"]
    one = tmp_path / "one.png"
    assert win.export_chart_image("chart:1", str(one)) == str(one)
    single = QImage(str(one))
    assert single.width() == ap._chart_widgets[1].width() * 3
    assert ap.save_image(str(one), "chart:9") is None          # out of range
    for scope in scopes:
        out = tmp_path / f"{scope}.png"
        assert win.export_chart_image(scope, str(out)) == str(out)
        img = QImage(str(out))
        assert img.width() > 60 and img.height() > 40
    # within a group there is no ranking or group heatmap to offer
    win.on_cmp_mode("within")
    win.on_within_group(win._groups[0].gid)
    win.render_analysis_sync()
    app.processEvents()
    assert "ranking" not in ap.scopes_available()


def test_stage_and_inspector_export_images(app, tmp_path):
    """The annotated field exports at the image's own resolution, not the view's."""
    from PySide6.QtGui import QImage
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    field = make_field()
    win.set_image(field, "f.png")
    _grid_group(win, 2, 3)
    sb = win.stage_bar
    sb.show_combo.setCurrentIndex(sb.show_combo.findData("glv_mean"))
    sb.heatmap_chk.setChecked(True)
    sb.cells_chk.setChecked(True)
    win.image_view.resize(300, 200)          # a small, zoomed-out view…
    app.processEvents()

    out = tmp_path / "field.png"
    assert win.export_stage_image(str(out), 2.0) == str(out)
    img = QImage(str(out))
    h, w = field.shape[:2]
    from pear.ui.image_view import _LEGEND_H
    assert img.width() == w * 2                            # …exports full size
    # the colour key gets a strip of its own under the field
    assert img.height() == h * 2 + _LEGEND_H
    assert win.image_view._scale != 2.0                    # the view is untouched
    assert not win.image_view._exporting                   # flag always restored

    sb.heatmap_chk.setChecked(False)                       # no key, no strip
    sb.cells_chk.setChecked(False)
    plain = tmp_path / "plain.png"
    assert win.export_stage_image(str(plain), 1.0) == str(plain)
    assert (QImage(str(plain)).width(), QImage(str(plain)).height()) == (w, h)
    sb.heatmap_chk.setChecked(True)

    svg = tmp_path / "field.svg"
    if win.export_stage_image(str(svg), 1.0) is not None:
        assert "<svg" in svg.read_text(encoding="utf-8")

    rid = group_rois(win._rois, win._active_gid)[0].rid
    win.open_inspector(rid)
    win.inspector_window.resize(600, 470)
    win.inspector_window.show()
    app.processEvents()
    roi_png = tmp_path / "roi.png"
    assert win.export_inspector_image(str(roi_png)) == str(roi_png)
    assert QImage(str(roi_png)).width() == win.inspector.width() * 3


def test_position_chart_without_positions_is_safe(app):
    """A series with no per-ROI position says so instead of crashing.

    Nothing in the app produces one today, but the guard is what keeps a
    future per-group metric from taking the window down.
    """
    from pear.ui.widgets import DistributionChart
    chart = DistributionChart()
    chart.resize(420, 300)
    chart.set_data("GLV mean", [{"label": "A", "color": "#2563EB",
                                 "values": np.array([1.0, 2.0, 3.0])}],
                   "position")
    assert all("pos_x" not in s for s in chart._series)
    chart.grab()                       # draws the "no position" hint
    chart.set_data("GLV mean", [{"label": "A", "color": "#2563EB",
                                 "values": np.array([1.0, 2.0])}], "map")
    chart.grab()


def test_chart_state_round_trips_through_a_project(app, tmp_path):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _grid_group(win, 2, 3)
    win.analysis.set_chart_state("map", "y")
    out = tmp_path / "p.pear.json"
    win.save_project(str(out))

    win2 = MainWindow()
    win2.set_image(make_field(), "f.png")
    assert win2.analysis.chart_state() == ("box", "x")
    import json
    win2._restore_project(json.loads(out.read_text(encoding="utf-8")))
    assert win2.analysis.chart_state() == ("map", "y")


def test_csv_carries_the_roi_centre(app, tmp_path):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.add_group()
    win.on_roi_created((10, 20, 10, 10))
    win.set_metrics(["glv_mean"])
    out = tmp_path / "c.csv"
    assert win.export_csv(str(out)) == str(out)
    text = out.read_text(encoding="utf-8-sig")
    assert "center_x" in text and "center_y" in text
    assert "15,25" in text.replace(", ", ",")     # centre of (10,20,10,10)


def test_icon_carries_every_windows_size(app, tmp_path):
    """The .ico is assembled by hand — so check Windows could read it back."""
    import struct
    import sys as _sys
    from PySide6.QtGui import QImage
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tools.make_icon import SIZES, build_ico, draw, write_icon

    data = build_ico()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind, count) == (0, 1, len(SIZES))
    for i, size in enumerate(SIZES):
        w, h, colors, res, planes, bits, length, offset = struct.unpack(
            "<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        assert (w, h) == (size % 256, size % 256)     # 256 is stored as 0
        assert (planes, bits) == (1, 32)
        payload = data[offset:offset + length]
        assert payload[:4] == b"\x89PNG"              # Vista+ compressed entry
        img = QImage.fromData(payload, "PNG")
        assert (img.width(), img.height()) == (size, size)

    # it draws something: the tile is not blank, and the mark is not the tile
    big = draw(64)
    assert big.pixelColor(2, 2).alpha() == 0           # rounded corner is clear
    assert big.pixelColor(32, 32) != big.pixelColor(6, 32)

    out = tmp_path / "x.ico"
    assert write_icon(str(out)) == str(out)
    from PySide6.QtGui import QIcon
    assert sorted(s.width() for s in QIcon(str(out)).availableSizes()) == \
        sorted(SIZES)
