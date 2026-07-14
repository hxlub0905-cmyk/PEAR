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
