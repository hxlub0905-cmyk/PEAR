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


def test_boot_seeds_group_and_period(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "sample_field.png")
    assert win._period is not None
    assert win._period.px == CELL_W and win._period.py == CELL_H
    assert len(win._groups) == 1 and win._active_gid == "A"
    assert win._rois == []


def test_controls_disabled_before_image(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    assert not win.rail.detect_btn.isEnabled()
    assert not win.rail.grp_add_btn.isEnabled()
    win.set_image(make_field(), "f.png")
    assert win.rail.detect_btn.isEnabled() and win.rail.grp_add_btn.isEnabled()


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
    from pear.core.analysis import group_rois
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.rail.grid_rows.setValue(2)
    win.rail.grid_cols.setValue(3)
    win.on_roi_grid_created((20, 20, 200, 150))
    assert len(group_rois(win._rois, win._active_gid)) == 6


def test_per_cell_replicate(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.on_roi_created((22, 18, 20, 16))
    win.select_roi(win._rois[0].rid)
    win.roi_per_cell()
    ncells = (make_field().shape[0] // CELL_H) * (make_field().shape[1] // CELL_W)
    assert len(win._rois) == ncells


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


def test_nm_per_px_in_csv(app, tmp_path):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _two_groups(win)
    win.on_scale_changed(1.5)
    out = tmp_path / "scaled.csv"
    win.export_csv(str(out))
    text = out.read_text(encoding="utf-8-sig")
    assert "pixel_size_nm_per_px" in text and "1.5" in text and "area_nm2" in text


def test_color_and_rename(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gA = win._active_gid
    win.set_group_color(gA, "#123456")
    win.rename_group(gA, "round holes")
    assert win._group(gA).color == "#123456"
    assert win._group(gA).name == "round holes"
