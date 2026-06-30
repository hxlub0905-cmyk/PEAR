"""Main window: assembles the image stage and the workspace docks, and
wires user intent to the headless analysis core.
"""

from __future__ import annotations

import csv
import os
from typing import List, Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton, QWidget)

from pear import __version__
from pear.core import stacking
from pear.core.analysis import (REGION_PALETTE, PeriodInfo, Region,
                                attribute_table, build_golden_cell,
                                load_image, run_region_analysis)
from pear.core.attributes import ATTR_LABELS
from pear.core.period_core import estimate_period
from pear.ui import theme
from pear.ui.image_view import ImageView
from pear.ui.widgets import AnalysisPanel, SettingsPanel

_IMAGE_FILTER = ("Images (*.png *.tif *.tiff *.jpg *.jpeg *.bmp)")


class MainWindow(QMainWindow):
    """The PEAR application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PEAR — pre-EBI attribute ranker")
        self.resize(1180, 760)

        self._image: Optional[np.ndarray] = None
        self._period: Optional[PeriodInfo] = None
        self._regions: List[Region] = []
        self._active_rid: Optional[int] = None
        self._next_rid = 1
        self._nm_per_px: float = 0.0

        self._build_topbar()
        self._build_docks()
        self._wire()

    # ------------------------------------------------------------------ #
    # construction
    # ------------------------------------------------------------------ #
    def _build_topbar(self) -> None:
        bar = QWidget()
        bar.setObjectName("TopBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 8, 14, 8)
        title = QLabel("PEAR")
        title.setObjectName("BrandTitle")
        sub = QLabel("· pre-EBI attribute ranker")
        sub.setObjectName("BrandSub")
        self.dataset_lbl = QLabel("no image")
        self.dataset_lbl.setObjectName("BrandSub")
        self.load_btn = QPushButton("Load…")
        self.load_btn.setObjectName("Primary")
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch(1)
        lay.addWidget(self.dataset_lbl)
        lay.addWidget(self.load_btn)
        self.setMenuWidget(bar)

    def _build_docks(self) -> None:
        # A zero-size central widget lets the three docks fill the window.
        spacer = QWidget()
        spacer.setFixedSize(0, 0)
        self.setCentralWidget(spacer)
        self.setDockNestingEnabled(True)

        self.image_view = ImageView()
        self.settings = SettingsPanel()
        self.analysis = AnalysisPanel()

        self.image_dock = self._dock("Image", self.image_view)
        self.settings_dock = self._dock("Settings", self.settings)
        self.analysis_dock = self._dock("Analysis", self.analysis)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.image_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.settings_dock)
        self.splitDockWidget(self.settings_dock, self.analysis_dock, Qt.Vertical)
        self.resizeDocks([self.image_dock, self.settings_dock],
                         [720, 400], Qt.Horizontal)

    def _dock(self, title: str, widget: QWidget) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(f"dock_{title.lower()}")
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)
        return dock

    def _wire(self) -> None:
        self.load_btn.clicked.connect(self.on_load_clicked)
        self.settings.detect_requested.connect(self.detect_period)
        self.settings.refine_requested.connect(self.refine_period)
        self.settings.manual_changed.connect(self.on_manual_changed)
        self.settings.region_selected.connect(self.select_region)
        self.settings.region_deleted.connect(self.delete_region)
        self.image_view.region_created.connect(self.create_region)
        self.image_view.region_modified.connect(self.modify_region)
        self.image_view.region_selected.connect(self.select_region)
        self.analysis.attr_selected.connect(self.on_attr_selected)
        self.analysis.export_requested.connect(self.export_csv)

    # ------------------------------------------------------------------ #
    # image loading
    # ------------------------------------------------------------------ #
    def on_load_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load image", "", _IMAGE_FILTER)
        if path:
            self.load_path(path)

    def load_path(self, path: str) -> None:
        try:
            img = load_image(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Load failed", str(exc))
            return
        self.set_image(img, os.path.basename(path))

    def set_image(self, img: np.ndarray, name: str = "image") -> None:
        self._image = img
        self._regions = []
        self._active_rid = None
        self._period = None
        self.dataset_lbl.setText(f"{name} · {img.shape[1]}x{img.shape[0]}")
        self.image_view.set_image(img)
        self._refresh_views()
        self.detect_period()

    # ------------------------------------------------------------------ #
    # period
    # ------------------------------------------------------------------ #
    def detect_period(self) -> None:
        if self._image is None:
            return
        res = estimate_period(self._image)
        if res.px is None or res.py is None:
            QMessageBox.information(
                self, "No period",
                "No repeating structure was detected. Set the period "
                "manually under Settings.")
            self._period = None
            self.settings.set_period(None)
            self.image_view.set_period(None)
            return
        conf = (res.confidence_x + res.confidence_y) / 2.0
        self._set_period(res.px, res.py, res.axis_mode, conf)

    def refine_period(self) -> None:
        if self._image is None or self._period is None:
            return
        bpx, bpy, _lv = stacking.refine_period(
            self._image, self._period.px, self._period.py, method="median")
        self._set_period(bpx, bpy, self._period.axis_mode,
                         self._period.confidence)

    def on_manual_changed(self, px: int, py: int, nm_per_px: float) -> None:
        if self._image is None:
            return
        self._nm_per_px = nm_per_px
        mode = self._period.axis_mode if self._period else "XY"
        conf = self._period.confidence if self._period else 0.0
        self._set_period(px, py, mode, conf)

    def _set_period(self, px: int, py: int, axis_mode: str,
                    confidence: float) -> None:
        golden = build_golden_cell(self._image, px, py)
        _score, lap_var, _edge = stacking.ghosting_score(golden)
        self._period = PeriodInfo(px=px, py=py, axis_mode=axis_mode,
                                  confidence=confidence, golden_cell=golden)
        self.settings.set_period(self._period)
        self.settings.set_alignment(lap_var)
        self.image_view.set_period(self._period)
        self._reanalyze_all()
        self._refresh_views()

    # ------------------------------------------------------------------ #
    # regions
    # ------------------------------------------------------------------ #
    def create_region(self, roi) -> None:
        if self._image is None or self._period is None:
            return
        color = REGION_PALETTE[(self._next_rid - 1) % len(REGION_PALETTE)]
        region = Region(rid=self._next_rid, name=f"region {self._next_rid}",
                        color=color, roi=tuple(roi))
        self._next_rid += 1
        self._regions.append(region)
        self._active_rid = region.rid
        self._analyze(region)
        self._refresh_views()

    def modify_region(self, rid: int, roi) -> None:
        region = self._region(rid)
        if region is None:
            return
        region.roi = tuple(roi)
        self._analyze(region)
        self._refresh_views()

    def select_region(self, rid: int) -> None:
        if self._region(rid) is None:
            return
        self._active_rid = rid
        self._refresh_views()

    def delete_region(self, rid: int) -> None:
        self._regions = [r for r in self._regions if r.rid != rid]
        if self._active_rid == rid:
            self._active_rid = self._regions[-1].rid if self._regions else None
        self._refresh_views()

    def on_attr_selected(self, attr: str) -> None:
        region = self._active_region()
        if region is None:
            return
        region.sel_attr = attr
        self.analysis.update_attr(region, attr)
        self.image_view.set_regions(self._regions, self._active_rid)

    # ------------------------------------------------------------------ #
    # analysis
    # ------------------------------------------------------------------ #
    def _analyze(self, region: Region) -> None:
        if self._image is None or self._period is None:
            return
        nm = self._nm_per_px if self._nm_per_px > 0 else None
        run_region_analysis(self._image, region, self._period, nm_per_px=nm)

    def _reanalyze_all(self) -> None:
        for region in self._regions:
            self._analyze(region)

    def _active_region(self) -> Optional[Region]:
        return self._region(self._active_rid) if self._active_rid else None

    def _region(self, rid: Optional[int]) -> Optional[Region]:
        for r in self._regions:
            if r.rid == rid:
                return r
        return None

    def _refresh_views(self) -> None:
        self.settings.set_period(self._period)
        self.settings.set_regions(self._regions, self._active_rid)
        self.image_view.set_regions(self._regions, self._active_rid)
        self.analysis.show_region(self._active_region())

    # ------------------------------------------------------------------ #
    # export
    # ------------------------------------------------------------------ #
    def export_csv(self, path: Optional[str] = None) -> Optional[str]:
        region = self._active_region()
        if region is None or not region.records:
            return None
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export CSV", f"{region.name}.csv", "CSV (*.csv)")
            if not path:
                return None
        self._write_csv(path, region)
        return path

    def _write_csv(self, path: str, region: Region) -> None:
        # UTF-8 with BOM for Excel friendliness.
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow([f"region: {region.name}"])
            w.writerow([])
            w.writerow(["attribute", "max_abs_z", "n_outliers"])
            for s in region.ranking:
                w.writerow([ATTR_LABELS.get(s.attr, s.attr),
                            f"{s.max_abs_z:.6g}", s.n_outliers])
            w.writerow([])
            attr_ids = [k for k in ATTR_LABELS
                        if region.records and k in region.records[0]]
            header = ["row", "col", "x", "y", "w", "h"] + attr_ids
            w.writerow(header)
            for rec in region.records:
                row = [rec["row"], rec["col"], rec["x"], rec["y"],
                       rec["w"], rec["h"]]
                row += [f"{rec.get(k, ''):.6g}" if isinstance(rec.get(k), float)
                        else rec.get(k, "") for k in attr_ids]
                w.writerow(row)
