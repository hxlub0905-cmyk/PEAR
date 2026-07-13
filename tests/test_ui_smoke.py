"""Offscreen UI smoke test for the group/ROI analysis app."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from examples.make_sample import CELL_H, CELL_W, OUTLIERS, make_field

QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def app():
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield application


def _paint_two_groups(win):
    """Group A = normal cells, Group B = injected outliers."""
    from pear.core.analysis import all_cells
    win.add_group()                       # ensures a second group (B)
    gA, gB = win._groups[0].gid, win._groups[1].gid
    outset = set(OUTLIERS)
    win.select_group(gA)
    for (r, c) in all_cells(win._image.shape, win._period):
        if (c, r) not in outset:
            win.on_cell_paint(r, c, True)
    win.select_group(gB)
    for (c, r) in outset:
        win.on_cell_paint(r, c, True)
    return gA, gB


def test_boot_seeds_group_roi_and_period(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "sample_field.png")
    assert win._period is not None
    assert win._period.px == CELL_W and win._period.py == CELL_H
    assert len(win._groups) == 1        # one group seeded
    assert len(win._rois) == 1          # one default ROI seeded


def test_paint_groups_and_membership_is_exclusive(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gA, gB = _paint_two_groups(win)
    a = win._group(gA)
    b = win._group(gB)
    assert len(b.cells) == len(OUTLIERS)
    assert a.cells and not (a.cells & b.cells)     # a cell is in exactly one group


def test_between_groups_export_csv(app, tmp_path):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _paint_two_groups(win)
    win.set_metrics(["glv_mean", "glv_median"])
    win.on_cmp_mode("between")
    out = tmp_path / "ga.csv"
    assert win.export_csv(str(out)) == str(out)
    text = out.read_text(encoding="utf-8-sig")
    assert "Group A" in text and "Group B" in text
    assert "GLV mean" in text and "summary" in text


def test_split_tr_enables_snr_and_within_mode(app):
    from pear.ui.main_window import MainWindow
    from pear.core.analysis import TARGET, REFERENCE, find_role
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    _, gB = _paint_two_groups(win)
    win.add_roi()                              # a second ROI so T/R is possible
    win.set_split(True)
    assert find_role(win._rois, TARGET) is not None
    assert find_role(win._rois, REFERENCE) is not None
    win.set_metrics(["glv_mean", "snr"])
    win.on_cmp_mode("within")
    win.on_within_group(gB)
    # SNR line becomes visible in the analysis panel
    assert win.analysis.snr_lbl.isVisibleTo(win.analysis) or win.analysis.snr_lbl.text()
    assert "SNR" in win.analysis.snr_lbl.text()


def test_add_roi_and_grid(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    n0 = len(win._rois)
    win.add_roi()
    assert len(win._rois) == n0 + 1
    win.add_roi_grid()
    assert len(win._rois) == n0 + 1 + 4        # grid adds 2x2
    assert win._mode == "roi"


def test_mode_toggle(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.set_mode("roi")
    assert win.image_view._mode == "roi"
    win.set_mode("group")
    assert win.image_view._mode == "group"


def test_roi_created_from_stage(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    n0 = len(win._rois)
    win.on_roi_created((20, 15, 24, 20))
    assert len(win._rois) == n0 + 1
    assert win._rois[-1].rect == (20, 15, 24, 20)


def test_delete_group_and_roi(app):
    from pear.ui.main_window import MainWindow
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gA, gB = _paint_two_groups(win)
    win.delete_group(gB)
    assert win._group(gB) is None
    rid = win._rois[0].rid
    win.delete_roi(rid)
    assert win._roi(rid) is None


def test_color_and_role_customization(app):
    from pear.ui.main_window import MainWindow
    from pear.core.analysis import TARGET
    win = MainWindow()
    win.set_image(make_field(), "f.png")
    gA = win._groups[0].gid
    win.set_group_color(gA, "#123456")
    assert win._group(gA).color == "#123456"
    win.set_split(True)
    rid = win._rois[0].rid
    win.set_roi_role(rid, TARGET)
    assert win._roi(rid).role == TARGET
