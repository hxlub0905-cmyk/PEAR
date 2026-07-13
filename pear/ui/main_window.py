"""Main window: image stage + control rail + a floatable analysis dock.

Wires user intent (paint groups, draw ROIs, pick metrics, compare) to the
headless group/ROI analysis core.
"""

from __future__ import annotations

import csv
import os
from typing import List, Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QWidget)

from pear.core import analysis
from pear.core.analysis import (GROUP_PALETTE, REFERENCE, REFERENCE_COLOR, ROI,
                                TARGET, TARGET_COLOR, Group, PeriodInfo,
                                build_golden_cell, cell_patch,
                                group_metric_values, load_image,
                                set_role, summarize)
from pear.core import stacking
from pear.core.attributes import SNR_ID, metric_label
from pear.core.period_core import estimate_period
from pear.ui import theme
from pear.ui.image_view import ImageView
from pear.ui.widgets import AnalysisPanel, RailPanel

_FILTER = "Images (*.png *.tif *.tiff *.jpg *.jpeg *.bmp)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PEAR — group & ROI analysis")
        self.resize(1280, 860)

        self._image: Optional[np.ndarray] = None
        self._period: Optional[PeriodInfo] = None
        self._groups: List[Group] = []
        self._rois: List[ROI] = []
        self._active_gid: Optional[str] = None
        self._active_rid: Optional[int] = None
        self._next_rid = 1
        self._metrics: List[str] = ["glv_mean", "glv_median"]
        self._mode = "group"
        self._split = False
        self._cmp_mode = "between"
        self._between_rid: Optional[int] = None
        self._within_gid: Optional[str] = None

        self._build_topbar()
        self._build_docks()
        self._build_status()
        self._wire()

    # ------------------------------------------------------------------ #
    # construction
    # ------------------------------------------------------------------ #
    def _build_topbar(self) -> None:
        bar = QWidget()
        bar.setObjectName("TopBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(10)
        pe = QLabel("PE")
        pe.setObjectName("BrandTitle")
        a = QLabel("A")
        a.setObjectName("BrandAccent")
        r = QLabel("R")
        r.setObjectName("BrandTitle")
        sub = QLabel("group & ROI analysis")
        sub.setObjectName("BrandSub")
        self.dataset_lbl = QLabel("no image")
        self.dataset_lbl.setObjectName("DatasetTag")
        self.mode_group_btn = QPushButton("Paint groups")
        self.mode_roi_btn = QPushButton("Draw ROI")
        for b, m in ((self.mode_group_btn, "group"), (self.mode_roi_btn, "roi")):
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, mm=m: self.set_mode(mm))
        self.mode_group_btn.setChecked(True)
        self.load_btn = QPushButton("Load…")
        self.load_btn.setObjectName("Primary")
        for w in (pe, a, r):
            lay.addWidget(w, 0, Qt.AlignVCenter)
        lay.addSpacing(6)
        lay.addWidget(sub)
        lay.addStretch(1)
        lay.addWidget(self.mode_group_btn)
        lay.addWidget(self.mode_roi_btn)
        lay.addSpacing(8)
        lay.addWidget(self.dataset_lbl)
        lay.addWidget(self.load_btn)
        self.setMenuWidget(bar)

    def _build_docks(self) -> None:
        self.image_view = ImageView()
        self.setCentralWidget(self.image_view)

        self.rail = RailPanel()
        rail_scroll = QScrollArea()
        rail_scroll.setWidgetResizable(True)
        rail_scroll.setFrameShape(QScrollArea.NoFrame)
        rail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rail_scroll.setWidget(self.rail)
        self.rail_dock = QDockWidget("Workspace", self)
        self.rail_dock.setObjectName("dock_rail")
        self.rail_dock.setWidget(rail_scroll)
        self.rail_dock.setFeatures(QDockWidget.DockWidgetMovable |
                                   QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, self.rail_dock)

        self.analysis = AnalysisPanel()
        self.analysis_dock = QDockWidget("Analysis", self)
        self.analysis_dock.setObjectName("dock_analysis")
        self.analysis_dock.setWidget(self.analysis)
        self.analysis_dock.setFeatures(QDockWidget.DockWidgetMovable |
                                       QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.analysis_dock)
        self.resizeDocks([self.rail_dock], [390], Qt.Horizontal)
        self.resizeDocks([self.analysis_dock], [340], Qt.Vertical)

    def _build_status(self) -> None:
        bar = self.statusBar()
        self.cursor_lbl = QLabel("")
        self.cursor_lbl.setObjectName("Mono")
        self.cursor_lbl.setFont(theme.mono_font(9))
        bar.addPermanentWidget(self.cursor_lbl)
        zoom = QWidget()
        zl = QHBoxLayout(zoom)
        zl.setContentsMargins(0, 0, 0, 0)
        zl.setSpacing(4)
        fit = QPushButton("Fit")
        minus = QPushButton("−")
        plus = QPushButton("+")
        for b in (fit, minus, plus):
            b.setFixedHeight(22)
        minus.setFixedWidth(26)
        plus.setFixedWidth(26)
        self.zoom_lbl = QLabel("100%")
        self.zoom_lbl.setObjectName("Mono")
        self.zoom_lbl.setFont(theme.mono_font(9))
        fit.clicked.connect(self.image_view.fit)
        minus.clicked.connect(self.image_view.zoom_out)
        plus.clicked.connect(self.image_view.zoom_in)
        for w in (fit, minus, self.zoom_lbl, plus):
            zl.addWidget(w)
        bar.addPermanentWidget(zoom)

    def _wire(self) -> None:
        self.load_btn.clicked.connect(self.on_load)
        self.rail.detect_requested.connect(self.detect_period)
        self.rail.refine_requested.connect(self.refine_period)
        self.rail.group_add.connect(self.add_group)
        self.rail.group_pick.connect(self.select_group)
        self.rail.group_del.connect(self.delete_group)
        self.rail.group_role.connect(self.set_group_role)
        self.rail.group_color.connect(self.set_group_color)
        self.rail.group_rename.connect(self.rename_group)
        self.rail.roi_add.connect(self.add_roi)
        self.rail.roi_grid.connect(self.add_roi_grid)
        self.rail.roi_pick.connect(self.select_roi)
        self.rail.roi_del.connect(self.delete_roi)
        self.rail.roi_role.connect(self.set_roi_role)
        self.rail.roi_color.connect(self.set_roi_color)
        self.rail.split_toggled.connect(self.set_split)
        self.rail.metrics_changed.connect(self.set_metrics)

        self.image_view.cell_paint.connect(self.on_cell_paint)
        self.image_view.roi_created.connect(self.on_roi_created)
        self.image_view.roi_modified.connect(self.on_roi_modified)
        self.image_view.roi_selected.connect(self.select_roi)
        self.image_view.cursor_info.connect(self.cursor_lbl.setText)
        self.image_view.zoom_changed.connect(
            lambda s: self.zoom_lbl.setText(f"{int(round(s * 100))}%"))

        self.analysis.mode_changed.connect(self.on_cmp_mode)
        self.analysis.between_roi_changed.connect(self.on_between_roi)
        self.analysis.within_group_changed.connect(self.on_within_group)
        self.analysis.export_requested.connect(self.export_csv)

    # ------------------------------------------------------------------ #
    # image / period
    # ------------------------------------------------------------------ #
    def on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load image", "", _FILTER)
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
        self._groups = []
        self._rois = []
        self._active_gid = None
        self._active_rid = None
        self._period = None
        self.dataset_lbl.setText(f"{name} · {img.shape[1]}×{img.shape[0]}")
        self.image_view.set_image(img)
        self.detect_period()

    def detect_period(self) -> None:
        if self._image is None:
            return
        res = estimate_period(self._image)
        if res.px is None or res.py is None:
            QMessageBox.information(
                self, "No lattice",
                "No repeating structure was detected on both axes.")
            self._period = None
            self._refresh()
            return
        conf = (res.confidence_x + res.confidence_y) / 2.0
        self._set_period(res.px, res.py, res.axis_mode, conf)

    def refine_period(self) -> None:
        if self._image is None or self._period is None:
            return
        bpx, bpy, _lv = stacking.refine_period(
            self._image, self._period.px, self._period.py, method="median")
        self._set_period(bpx, bpy, self._period.axis_mode, self._period.confidence)

    def _set_period(self, px, py, axis_mode, confidence) -> None:
        golden = build_golden_cell(self._image, px, py)
        self._period = PeriodInfo(px=px, py=py, axis_mode=axis_mode,
                                  confidence=confidence, golden_cell=golden)
        # Seed a default ROI (a centred window in one cell) if none exist.
        if not self._rois:
            w, h = max(6, px // 3), max(6, py // 3)
            self._add_roi_rect(((px - w) // 2, (py - h) // 2, w, h), "Center")
        # Ensure at least one group exists.
        if not self._groups:
            self.add_group()
        self._refresh()

    # ------------------------------------------------------------------ #
    # mode
    # ------------------------------------------------------------------ #
    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.mode_group_btn.setChecked(mode == "group")
        self.mode_roi_btn.setChecked(mode == "roi")
        self.image_view.set_mode(mode)

    # ------------------------------------------------------------------ #
    # groups
    # ------------------------------------------------------------------ #
    def add_group(self) -> None:
        if self._image is None or self._period is None:
            self.statusBar().showMessage("Load an image and detect a lattice first.", 4000)
            return
        idx = len(self._groups)
        gid = chr(ord("A") + idx) if idx < 26 else f"G{idx}"
        color = GROUP_PALETTE[idx % len(GROUP_PALETTE)]
        self._groups.append(Group(gid=gid, name=f"Group {gid}", color=color))
        self._active_gid = gid
        self.set_mode("group")
        self._refresh()

    def select_group(self, gid: str) -> None:
        self._active_gid = gid
        self._refresh()

    def delete_group(self, gid: str) -> None:
        self._groups = [g for g in self._groups if g.gid != gid]
        if self._active_gid == gid:
            self._active_gid = self._groups[-1].gid if self._groups else None
        self._refresh()

    def set_group_role(self, gid: str, role: str) -> None:
        g = self._group(gid)
        if g is not None:
            set_role(self._groups, g, role)
            self._refresh()

    def set_group_color(self, gid: str, color: str) -> None:
        g = self._group(gid)
        if g is not None:
            g.color = color
            self._refresh()

    def rename_group(self, gid: str, name: str) -> None:
        g = self._group(gid)
        if g is not None and name:
            g.name = name

    def on_cell_paint(self, row: int, col: int, is_drag: bool) -> None:
        g = self._group(self._active_gid)
        if g is None:
            self.statusBar().showMessage("Add a group first.", 3000)
            return
        cell = (row, col)
        if not is_drag and cell in g.cells:
            g.cells.discard(cell)
        else:
            for other in self._groups:
                other.cells.discard(cell)
            g.cells.add(cell)
        self._refresh()

    # ------------------------------------------------------------------ #
    # rois
    # ------------------------------------------------------------------ #
    def add_roi(self) -> None:
        if self._period is None:
            return
        px, py = self._period.px, self._period.py
        w, h = max(6, px // 4), max(6, py // 4)
        self._add_roi_rect((px // 2, py // 2, w, h), f"ROI {len(self._rois) + 1}")
        self.set_mode("roi")
        self._refresh()

    def add_roi_grid(self) -> None:
        if self._period is None:
            return
        px, py = self._period.px, self._period.py
        w, h = max(5, px // 5), max(5, py // 5)
        n = 0
        for gy in range(2):
            for gx in range(2):
                n += 1
                x = int(px * (0.12 + gx * 0.44))
                y = int(py * (0.12 + gy * 0.44))
                self._add_roi_rect((x, y, w, h), f"Grid {n}", refresh=False)
        self.set_mode("roi")
        self._refresh()

    def _add_roi_rect(self, rect, label, refresh=False) -> None:
        role = REFERENCE if self._split else analysis.NONE
        color = REFERENCE_COLOR if self._split else GROUP_PALETTE[
            (self._next_rid) % len(GROUP_PALETTE)]
        roi = ROI(rid=self._next_rid, label=label, color=color, rect=tuple(rect),
                  role=role)
        self._next_rid += 1
        self._rois.append(roi)
        self._active_rid = roi.rid
        if self._between_rid is None:
            self._between_rid = roi.rid
        if refresh:
            self._refresh()

    def on_roi_created(self, rect) -> None:
        self._add_roi_rect(tuple(rect), f"ROI {len(self._rois) + 1}")
        self._refresh()

    def on_roi_modified(self, rid: int, rect) -> None:
        roi = self._roi(rid)
        if roi is not None:
            roi.rect = tuple(rect)
            self._refresh()

    def select_roi(self, rid: int) -> None:
        self._active_rid = rid
        self._refresh()

    def delete_roi(self, rid: int) -> None:
        self._rois = [r for r in self._rois if r.rid != rid]
        if self._active_rid == rid:
            self._active_rid = self._rois[-1].rid if self._rois else None
        if self._between_rid == rid:
            self._between_rid = self._rois[0].rid if self._rois else None
        self._refresh()

    def set_roi_role(self, rid: int, role: str) -> None:
        roi = self._roi(rid)
        if roi is not None:
            set_role(self._rois, roi, role)
            self._refresh()

    def set_roi_color(self, rid: int, color: str) -> None:
        roi = self._roi(rid)
        if roi is not None:
            roi.color = color
            self._refresh()

    # ------------------------------------------------------------------ #
    # split / metrics / comparison
    # ------------------------------------------------------------------ #
    def set_split(self, on: bool) -> None:
        self._split = on
        self.rail.metrics.set_split(on)
        if on:
            # auto-assign target/reference if unset
            if analysis.find_role(self._rois, TARGET) is None and self._rois:
                set_role(self._rois, self._rois[0], TARGET)
                self._rois[0].color = TARGET_COLOR
            if analysis.find_role(self._rois, REFERENCE) is None and len(self._rois) > 1:
                set_role(self._rois, self._rois[1], REFERENCE)
                self._rois[1].color = REFERENCE_COLOR
        self.image_view.set_split_tr(on)
        self._metrics = self.rail.metrics.selected()
        self._refresh()

    def set_metrics(self, metrics: List[str]) -> None:
        self._metrics = list(metrics)
        self._render_analysis()

    def on_cmp_mode(self, mode: str) -> None:
        self._cmp_mode = mode
        self._render_analysis()

    def on_between_roi(self, rid: int) -> None:
        self._between_rid = rid
        self._render_analysis()

    def on_within_group(self, gid: str) -> None:
        self._within_gid = gid
        self._render_analysis()

    # ------------------------------------------------------------------ #
    # refresh
    # ------------------------------------------------------------------ #
    def _refresh(self) -> None:
        self.rail.set_period(self._period)
        self.rail.set_groups(self._groups, self._active_gid, self._split)
        self.rail.set_rois(self._rois, self._active_rid, self._split)
        self.image_view.set_period(self._period)
        self.image_view.set_groups(self._groups, self._active_gid)
        self.image_view.set_rois(self._rois, self._active_rid)
        self.image_view.set_split_tr(self._split)
        if self._within_gid is None and self._groups:
            self._within_gid = self._groups[0].gid
        self._render_analysis()

    def _render_analysis(self) -> None:
        self.analysis.render_state(
            self._image, self._period, self._groups, self._rois, self._metrics,
            self._cmp_mode, self._between_rid, self._within_gid, self._split)

    # ------------------------------------------------------------------ #
    # lookups
    # ------------------------------------------------------------------ #
    def _group(self, gid) -> Optional[Group]:
        for g in self._groups:
            if g.gid == gid:
                return g
        return None

    def _roi(self, rid) -> Optional[ROI]:
        for r in self._rois:
            if r.rid == rid:
                return r
        return None

    def _active_group(self) -> Optional[Group]:
        return self._group(self._active_gid)

    # ------------------------------------------------------------------ #
    # export
    # ------------------------------------------------------------------ #
    def export_csv(self, path: Optional[str] = None) -> Optional[str]:
        if self._image is None or self._period is None or not self._groups:
            return None
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export CSV", "group_analysis.csv", "CSV (*.csv)")
            if not path:
                return None
        self._write_csv(path)
        return path

    def _write_csv(self, path: str) -> None:
        tgt = analysis.find_role(self._rois, TARGET) if self._split else None
        ref = analysis.find_role(self._rois, REFERENCE) if self._split else None
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["PEAR group & ROI analysis"])
            w.writerow(["split_target_reference", str(self._split)])
            w.writerow([])
            # per-cell rows: group, cell, roi, metrics
            header = ["group", "row", "col", "roi"] + [metric_label(m) for m in self._metrics]
            w.writerow(header)
            for g in self._groups:
                for (r, c) in sorted(g.cells):
                    for roi in self._rois:
                        row = [g.name, r, c, roi.label]
                        for mid in self._metrics:
                            if mid == SNR_ID:
                                if tgt is not None and ref is not None:
                                    v = group_metric_values(
                                        self._image, Group("t", "t", "#000", {(r, c)}),
                                        roi, self._period, SNR_ID,
                                        target_roi=tgt, reference_roi=ref)
                                    row.append(f"{v[0]:.6g}" if v.size else "")
                                else:
                                    row.append("")
                            else:
                                patch = cell_patch(self._image, roi.rect, self._period, r, c)
                                from pear.core.attributes import glv_value
                                row.append(f"{glv_value(patch, mid):.6g}" if patch is not None else "")
                        w.writerow(row)
            w.writerow([])
            # per-group summary (for the active between-ROI)
            roi = self._roi(self._between_rid) or (self._rois[0] if self._rois else None)
            if roi is not None:
                w.writerow([f"summary · ROI {roi.label}"])
                w.writerow(["group", "n"] + [metric_label(m) for m in self._metrics])
                for g in self._groups:
                    if not g.cells:
                        continue
                    cells_n = len(g.cells)
                    line = [g.name, cells_n]
                    for mid in self._metrics:
                        vals = group_metric_values(self._image, g, roi, self._period,
                                                   mid, target_roi=tgt, reference_roi=ref)
                        s = summarize(vals)
                        line.append(f"{s['mean']:.6g}")
                    w.writerow(line)
