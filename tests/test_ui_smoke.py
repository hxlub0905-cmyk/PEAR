"""Offscreen UI smoke test.

Drives the full UI path with ``QT_QPA_PLATFORM=offscreen``: build the
window, set an image, detect the period, add a region, auto-analyze, and
assert the ranking / distribution populate, then export CSV.
"""

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


def test_full_ui_path(app, tmp_path):
    from pear.ui.main_window import MainWindow

    win = MainWindow()
    img = make_field()
    win.set_image(img, "sample_field.png")

    # Period auto-detected on set_image.
    assert win._period is not None
    assert win._period.px == CELL_W
    assert win._period.py == CELL_H

    # Add a region programmatically over the feature block; auto-analyzes.
    win.create_region((16, 13, 30, 26))
    region = win._active_region()
    assert region is not None
    assert region.instances, "region must expand to instances"
    assert region.ranking, "ranking must populate"
    assert region.sel_attr is not None

    # Ranking list and distribution populated in the Analysis panel.
    assert win.analysis.ranking.count() > 0
    assert win.analysis.hist._values.size == len(region.instances)

    # Selecting a different attribute updates the panel without error.
    second = region.ranking[min(1, len(region.ranking) - 1)].attr
    win.on_attr_selected(second)
    assert region.sel_attr == second

    # The top attribute flags the injected outlier cells.
    win.on_attr_selected(region.ranking[0].attr)
    top = region.ranking[0]
    flagged = {(region.records[i]["col"], region.records[i]["row"])
               for i in top.outlier_indices}
    for cell in OUTLIERS:
        assert cell in flagged

    # Export CSV to a temp path; assert non-empty.
    out = tmp_path / "out.csv"
    result = win.export_csv(str(out))
    assert result == str(out)
    assert out.exists()
    assert out.stat().st_size > 0
    content = out.read_text(encoding="utf-8-sig")
    assert "region 1" in content
    assert "attribute" in content


def test_labelled_compare_mode_flow(app, tmp_path):
    from pear.ui.main_window import MainWindow

    win = MainWindow()
    win.set_image(make_field(), "sample_field.png")
    win.create_region((16, 13, 30, 26))
    region = win._active_region()

    # Switch to labelled compare mode.
    win.on_mode_changed("labelled")
    assert win._mode == "labelled"
    assert win.image_view._labelled is True

    # Tag the injected outlier cells as targets (as if clicked).
    for i, rec in enumerate(region.records):
        if (rec["col"], rec["row"]) in set(OUTLIERS):
            win.on_cell_tag_toggled(i)
    assert len(region.target_idx) == len(OUTLIERS)
    assert region.sep_ranking, "separability ranking must populate"
    assert region.sep_sel_attr is not None
    assert win.analysis.ranking.count() > 0

    # The histogram now shows two populations.
    assert win.analysis.hist._target is not None

    # Selecting another attribute updates sep selection, not sel_attr.
    second = region.sep_ranking[min(1, len(region.sep_ranking) - 1)].attr
    win.on_attr_selected(second)
    assert region.sep_sel_attr == second

    # Export carries the labelled ranking + is_target column.
    out = tmp_path / "labelled.csv"
    assert win.export_csv(str(out)) == str(out)
    text = out.read_text(encoding="utf-8-sig")
    assert "mode: labelled" in text
    assert "separation_score" in text
    assert "is_target" in text

    # Re-editing the ROI clears target tags.
    win.modify_region(region.rid, (18, 14, 28, 24))
    assert region.target_idx == set()


def test_additive_regions_do_not_wipe(app):
    from pear.ui.main_window import MainWindow

    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.create_region((16, 13, 20, 20))
    win.create_region((30, 20, 18, 18))
    assert len(win._regions) == 2, "second draw must not wipe the first"


def test_roi_clamped_within_single_cell(app):
    from pear.ui.main_window import MainWindow

    win = MainWindow()
    win.set_image(make_field(), "f.png")
    iv = win.image_view
    # A box at x=50, w=30 with px=64 would straddle the cell boundary.
    x, y, w, h = iv._clamp_roi((50, 10, 30, 20))
    assert (x % CELL_W) + w <= CELL_W
    assert (y % CELL_H) + h <= CELL_H


def test_draw_rubberband_does_not_crash(app):
    from PySide6.QtCore import QPointF, QPoint, Qt
    from PySide6.QtGui import QMouseEvent
    from pear.ui.main_window import MainWindow

    win = MainWindow()
    win.set_image(make_field(), "f.png")
    iv = win.image_view
    iv.resize(400, 300)

    def evt(kind, pos):
        return QMouseEvent(kind, QPointF(pos), Qt.LeftButton,
                           Qt.LeftButton, Qt.NoModifier)

    iv.mousePressEvent(evt(QMouseEvent.Type.MouseButtonPress, QPoint(60, 60)))
    iv.mouseMoveEvent(evt(QMouseEvent.Type.MouseMove, QPoint(110, 100)))
    # A paint while the rubber-band is active must not raise.
    iv.repaint()
    iv.mouseReleaseEvent(evt(QMouseEvent.Type.MouseButtonRelease,
                             QPoint(110, 100)))


def test_grid_persists_when_regions_change(app):
    from pear.ui.main_window import MainWindow

    win = MainWindow()
    win.set_image(make_field(), "f.png")
    assert win.image_view._period is not None
    win.create_region((16, 13, 20, 20))
    # Period (and therefore the grid) is still present after adding a region.
    assert win.image_view._period is not None
