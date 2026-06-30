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


def test_additive_regions_do_not_wipe(app):
    from pear.ui.main_window import MainWindow

    win = MainWindow()
    win.set_image(make_field(), "f.png")
    win.create_region((16, 13, 20, 20))
    win.create_region((30, 20, 18, 18))
    assert len(win._regions) == 2, "second draw must not wipe the first"


def test_grid_persists_when_regions_change(app):
    from pear.ui.main_window import MainWindow

    win = MainWindow()
    win.set_image(make_field(), "f.png")
    assert win.image_view._period is not None
    win.create_region((16, 13, 20, 20))
    # Period (and therefore the grid) is still present after adding a region.
    assert win.image_view._period is not None
