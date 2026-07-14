"""Main window: image stage + control rail. Analysis lives in its own window.

Model: a Group is a category; ROIs belong to a group. Add ROIs on the image
(click to drop, drag to size, or Grid via two corner clicks), then compare
metric distributions between or within groups in the Analysis window.
"""

from __future__ import annotations

import csv
import os
from typing import List, Optional

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from pear.core.analysis import (GROUP_PALETTE, SNR_MARGIN, ROI, Group,
                                compute_analysis, group_rois, load_image,
                                roi_metric, snapshot, summarize)
from pear.core.attributes import metric_label
from pear.ui import theme
from pear.ui.image_view import ImageView
from pear.ui.widgets import AnalysisPanel, RailPanel

_FILTER = "Images (*.png *.tif *.tiff *.jpg *.jpeg *.bmp)"


class _AnalysisSignals(QObject):
    done = Signal(int, object)


class _AnalysisJob(QRunnable):
    def __init__(self, token, args, signals):
        super().__init__()
        self._token = token
        self._args = args
        self._signals = signals

    def run(self):
        try:
            result = compute_analysis(*self._args)
        except Exception:  # noqa: BLE001
            result = None
        self._signals.done.emit(self._token, result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PEAR — group & ROI analysis")
        self.resize(1180, 820)

        self._image: Optional[np.ndarray] = None
        self._groups: List[Group] = []
        self._rois: List[ROI] = []
        self._active_gid: Optional[str] = None
        self._active_rid: Optional[int] = None
        self._next_rid = 1
        self._metrics: List[str] = ["glv_mean", "glv_median"]
        self._show_metric = ""            # single metric drawn live on ROIs
        self._cmp_mode = "between"
        self._within_gid: Optional[str] = None

        self._pool = QThreadPool.globalInstance()
        self._sig = _AnalysisSignals()
        self._sig.done.connect(self._on_analysis_done)
        self._analysis_token = 0
        self._analysis_timer = QTimer(self)
        self._analysis_timer.setSingleShot(True)
        self._analysis_timer.setInterval(90)
        self._analysis_timer.timeout.connect(self._run_analysis)

        self._build_topbar()
        self._build_docks()
        self._build_status()
        self._build_analysis_window()
        self._wire()
        self.rail.set_ready(False)

    # ------------------------------------------------------------------ #
    def _build_topbar(self) -> None:
        bar = QWidget()
        bar.setObjectName("TopBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(8)
        brand = QLabel('PE<span style="color:%s">A</span>R' % theme.AMBER)
        brand.setObjectName("BrandTitle")
        brand.setTextFormat(Qt.RichText)
        sub = QLabel("group & ROI analysis")
        sub.setObjectName("BrandSub")
        self.dataset_lbl = QLabel("no image")
        self.dataset_lbl.setObjectName("DatasetTag")
        self.load_btn = QPushButton("Load…")
        self.load_btn.setObjectName("Primary")
        lay.addWidget(brand, 0, Qt.AlignVCenter)
        lay.addSpacing(8)
        lay.addWidget(sub)
        lay.addStretch(1)
        lay.addWidget(self.dataset_lbl)
        lay.addWidget(self.load_btn)
        self.setMenuWidget(bar)

    def _build_docks(self) -> None:
        self.image_view = ImageView()
        self.setCentralWidget(self.image_view)
        self.rail = RailPanel()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.rail)
        self.rail_dock = QDockWidget("Workspace", self)
        self.rail_dock.setObjectName("dock_rail")
        self.rail_dock.setWidget(scroll)
        self.rail_dock.setFeatures(QDockWidget.DockWidgetMovable |
                                   QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, self.rail_dock)
        self.resizeDocks([self.rail_dock], [400], Qt.Horizontal)

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

    def _build_analysis_window(self) -> None:
        self.analysis = AnalysisPanel()
        self.analysis_window = QWidget()
        self.analysis_window.setWindowTitle("PEAR — Analysis")
        self.analysis_window.resize(920, 580)
        lay = QVBoxLayout(self.analysis_window)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.analysis)

    def _wire(self) -> None:
        self.load_btn.clicked.connect(self.on_load)
        self.rail.group_add.connect(self.add_group)
        self.rail.group_pick.connect(self.select_group)
        self.rail.group_del.connect(self.delete_group)
        self.rail.group_color.connect(self.set_group_color)
        self.rail.group_rename.connect(self.rename_group)
        self.rail.group_clear.connect(self.clear_group)
        self.rail.grid_mode_toggled.connect(self.set_grid_mode)
        self.rail.grid_commit.connect(self.image_view.commit_grid)
        self.rail.grid_shape_changed.connect(self.image_view.set_grid_shape)
        self.rail.roi_size_changed.connect(self.image_view.set_roi_size)
        self.rail.roi_del.connect(self.delete_roi)
        self.rail.metrics_changed.connect(self.set_metrics)
        self.rail.show_metric_changed.connect(self.on_show_metric)
        self.rail.open_analysis.connect(self.open_analysis)

        self.image_view.roi_created.connect(self.on_roi_created)
        self.image_view.grid_committed.connect(self.on_grid_committed)
        self.image_view.grid_ready.connect(self.rail.set_grid_ready)
        self.image_view.roi_modified.connect(self.on_roi_modified)
        self.image_view.roi_selected.connect(self.select_roi)
        self.image_view.roi_delete_requested.connect(self.delete_roi)
        self.image_view.cursor_info.connect(self.cursor_lbl.setText)
        self.image_view.zoom_changed.connect(
            lambda s: self.zoom_lbl.setText(f"{int(round(s * 100))}%"))

        self.analysis.mode_changed.connect(self.on_cmp_mode)
        self.analysis.within_group_changed.connect(self.on_within_group)
        self.analysis.export_requested.connect(self.export_csv)

    # ------------------------------------------------------------------ #
    # image
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
        self._within_gid = None
        self.dataset_lbl.setText(f"{name} · {img.shape[1]}×{img.shape[0]}")
        self.image_view.set_image(img)
        self.add_group()          # start with one group so adding ROIs works
        self._refresh()

    # ------------------------------------------------------------------ #
    # groups
    # ------------------------------------------------------------------ #
    def add_group(self) -> None:
        if self._image is None:
            return
        used = {g.gid for g in self._groups}
        letter = next((chr(ord("A") + i) for i in range(26)
                       if chr(ord("A") + i) not in used), None)
        if letter is None:
            letter = f"G{len(self._groups)}"
        ci = (ord(letter) - ord("A")) if len(letter) == 1 else len(self._groups)
        self._groups.append(Group(gid=letter, name=f"Group {letter}",
                                  color=GROUP_PALETTE[ci % len(GROUP_PALETTE)]))
        self._active_gid = letter
        self._refresh()

    def select_group(self, gid: str) -> None:
        self._active_gid = gid
        self._refresh()

    def delete_group(self, gid: str) -> None:
        self._groups = [g for g in self._groups if g.gid != gid]
        self._rois = [r for r in self._rois if r.gid != gid]
        if self._active_gid == gid:
            self._active_gid = self._groups[-1].gid if self._groups else None
        if self._within_gid == gid:
            self._within_gid = self._groups[0].gid if self._groups else None
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
            self._refresh()

    def clear_group(self, gid: str) -> None:
        self._rois = [r for r in self._rois if r.gid != gid]
        self._refresh()

    # ------------------------------------------------------------------ #
    # rois
    # ------------------------------------------------------------------ #
    def set_grid_mode(self, on: bool) -> None:
        self.image_view.set_grid_mode(on)
        if on:
            self.statusBar().showMessage(
                "Grid: click the top-left, then the bottom-right corner.", 6000)

    def _add_roi(self, rect, refresh=True) -> ROI:
        gid = self._active_gid or (self._groups[0].gid if self._groups else "A")
        roi = ROI(rid=self._next_rid, gid=gid, rect=tuple(rect),
                  label=f"ROI {self._next_rid}")
        self._next_rid += 1
        self._rois.append(roi)
        self._active_rid = roi.rid
        if refresh:
            self._refresh()
        return roi

    def on_roi_created(self, rect) -> None:
        if not self._groups:
            self.add_group()
        self._add_roi(rect)

    def on_grid_committed(self, rects) -> None:
        if not self._groups:
            self.add_group()
        for rect in rects:
            self._add_roi(rect, refresh=False)
        self.rail.grid_btn.setChecked(False)     # exit grid mode
        self.statusBar().showMessage(f"Added {len(rects)} ROIs.", 3000)
        self._refresh()

    def on_roi_modified(self, rid: int, rect) -> None:
        roi = self._roi(rid)
        if roi is not None:
            roi.rect = tuple(rect)
            self._refresh()

    def select_roi(self, rid: int) -> None:
        self._active_rid = rid
        roi = self._roi(rid)
        if roi is not None and roi.gid != self._active_gid:
            self._active_gid = roi.gid
        self._refresh()

    def delete_roi(self, rid: int) -> None:
        self._rois = [r for r in self._rois if r.rid != rid]
        if self._active_rid == rid:
            self._active_rid = None
        self._refresh()

    # ------------------------------------------------------------------ #
    # metrics / comparison
    # ------------------------------------------------------------------ #
    def set_metrics(self, metrics: List[str]) -> None:
        self._metrics = list(metrics)
        self._render_analysis()

    def on_show_metric(self, mid: str) -> None:
        self._show_metric = mid or ""
        self._update_roi_values()

    def _update_roi_values(self) -> None:
        if not self._show_metric or self._image is None:
            self.image_view.set_roi_values({})
            return
        vals = {}
        for r in self._rois:
            v = roi_metric(self._image, r, self._show_metric, SNR_MARGIN)
            vals[r.rid] = f"{v:.3g}"
        self.image_view.set_roi_values(vals)

    def on_cmp_mode(self, mode: str) -> None:
        self._cmp_mode = mode
        self._render_analysis()

    def on_within_group(self, gid: str) -> None:
        self._within_gid = gid
        self._render_analysis()

    def open_analysis(self) -> None:
        self.analysis_window.show()
        self.analysis_window.raise_()
        self.analysis_window.activateWindow()
        self._render_analysis()

    # ------------------------------------------------------------------ #
    # refresh
    # ------------------------------------------------------------------ #
    def _refresh(self) -> None:
        has_img = self._image is not None
        self.rail.set_ready(has_img)
        counts = {g.gid: len(group_rois(self._rois, g.gid)) for g in self._groups}
        self.rail.set_groups(self._groups, self._active_gid, counts)
        self.rail.set_rois(group_rois(self._rois, self._active_gid), self._active_rid)
        self.image_view.set_groups(self._groups, self._active_gid)
        self.image_view.set_rois(self._rois, self._active_rid)
        self._update_roi_values()
        if self._within_gid is None and self._groups:
            self._within_gid = self._groups[0].gid
        self._render_analysis()

    def _render_analysis(self) -> None:
        enabled = (self._image is not None and bool(self._metrics)
                   and any(group_rois(self._rois, g.gid) for g in self._groups))
        self.analysis.set_controls(self._cmp_mode, self._groups,
                                   self._within_gid, enabled)
        self._analysis_timer.start()

    def _run_analysis(self) -> None:
        self._analysis_token += 1
        token = self._analysis_token
        gs, rs = snapshot(self._groups, self._rois)
        args = (self._image, gs, rs, list(self._metrics), self._cmp_mode,
                self._within_gid, SNR_MARGIN)
        self.analysis.set_computing(True)
        self._pool.start(_AnalysisJob(token, args, self._sig))

    def _on_analysis_done(self, token: int, result) -> None:
        if token != self._analysis_token or result is None:
            return
        self.analysis.set_computing(False)
        self.analysis.show_result(result)

    def render_analysis_sync(self) -> None:
        self._analysis_timer.stop()
        gs, rs = snapshot(self._groups, self._rois)
        result = compute_analysis(self._image, gs, rs, list(self._metrics),
                                  self._cmp_mode, self._within_gid, SNR_MARGIN)
        enabled = result.empty is None
        self.analysis.set_controls(self._cmp_mode, self._groups,
                                   self._within_gid, enabled)
        self.analysis.set_computing(False)
        self.analysis.show_result(result)

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

    # ------------------------------------------------------------------ #
    # export
    # ------------------------------------------------------------------ #
    def export_csv(self, path: Optional[str] = None) -> Optional[str]:
        if self._image is None or not self._rois:
            return None
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export CSV", "group_analysis.csv", "CSV (*.csv)")
            if not path:
                return None
        self._write_csv(path)
        return path

    def _write_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["PEAR group & ROI analysis"])
            w.writerow([])
            header = ["group", "roi", "x", "y", "w", "h"] + \
                     [metric_label(m) for m in self._metrics]
            w.writerow(header)
            for g in self._groups:
                for roi in group_rois(self._rois, g.gid):
                    x, y, wid, hei = roi.rect
                    row = [g.name, roi.label, x, y, wid, hei]
                    for mid in self._metrics:
                        row.append(f"{roi_metric(self._image, roi, mid, SNR_MARGIN):.6g}")
                    w.writerow(row)
            w.writerow([])
            w.writerow(["summary"])
            w.writerow(["group", "ROIs"] + [metric_label(m) for m in self._metrics])
            for g in self._groups:
                grois = group_rois(self._rois, g.gid)
                if not grois:
                    continue
                line = [g.name, len(grois)]
                for mid in self._metrics:
                    vals = np.array([roi_metric(self._image, r, mid, SNR_MARGIN)
                                     for r in grois])
                    line.append(f"{summarize(vals)['mean']:.6g}")
                w.writerow(line)
