"""Offscreen UI smoke test for the group/ROI analysis app."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    win.set_image(make_field(), "f.png")
    assert win.rail.grp_add_btn.isEnabled() and win.rail.grid_btn.isEnabled()


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
    win.set_metrics(["glv_mean", "snr"])
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


def test_set_target_roi_toggles_and_snr(app):
    from pear.core.analysis import group_rois, group_snr
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((22, 18, 20, 16))        # bright feature
    win.on_roi_created((3, 3, 10, 8))           # dark background
    win.on_roi_created((CELL_W + 3, 3, 10, 8))  # dark background
    gid = win._active_gid
    tgt = group_rois(win._rois, gid)[0].rid
    win.set_target_roi(tgt)
    assert win._group(gid).target_rid == tgt
    snr = group_snr(win._image, group_rois(win._rois, gid), tgt)
    assert snr is not None and snr > 0
    win.set_target_roi(tgt)                      # toggles back off
    assert win._group(gid).target_rid is None


def test_show_snr_labels_target_only(app):
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((22, 18, 20, 16))
    win.on_roi_created((3, 3, 10, 8))
    gid = win._active_gid
    tgt = group_rois(win._rois, gid)[0].rid
    win.set_target_roi(tgt)
    win.on_show_metric("snr")
    assert list(win.image_view._roi_values.keys()) == [tgt]


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
    assert any(c._opts == {"points": False, "whiskers": False} for c in charts)


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
    win.set_target_roi(group_rois(win._rois, win._active_gid)[0].rid)
    win.set_metrics(["glv_mean", "snr"])
    proj = tmp_path / "p.pear.json"
    assert win.save_project(str(proj)) == str(proj)

    win2 = MainWindow()
    assert win2.open_project(str(proj)) == str(proj)
    assert win2._image is not None
    assert win2._group("A").name == "round holes"
    a_rois = group_rois(win2._rois, "A")
    assert len(a_rois) == 2 and win2._group("A").target_rid == a_rois[0].rid
    assert win2._metrics == ["glv_mean", "snr"]


def test_export_includes_snr_with_target(app, tmp_path):
    from pear.core.analysis import group_rois
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((22, 18, 20, 16))
    win.on_roi_created((3, 3, 10, 8))
    gid = win._active_gid
    win.set_target_roi(group_rois(win._rois, gid)[0].rid)
    win.set_metrics(["glv_mean", "snr"])
    out = tmp_path / "snr.csv"
    assert win.export_csv(str(out)) == str(out)
    text = out.read_text(encoding="utf-8-sig")
    assert "role" in text and "SNR" in text
