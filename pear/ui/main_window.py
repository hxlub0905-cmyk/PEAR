"""Main window: image stage + control rail. Analysis lives in its own window.

Model: a Group is a category; ROIs belong to a group. Add ROIs on the image
(click to drop, drag to size, or Grid via two corner clicks), then compare
metric distributions between or within groups in the Analysis window.
"""

from __future__ import annotations

import csv
import json
import os
from typing import List, Optional

import numpy as np
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QHBoxLayout, QLabel,
                               QMainWindow, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QToolButton, QVBoxLayout, QWidget)

from pear.core.analysis import (GROUP_PALETTE, ROI, Group, compute_analysis,
                                group_outliers, group_rois, group_snr,
                                groups_from_json, groups_to_json, heat_cells,
                                heat_color, load_image, roi_center, roi_metric,
                                roi_patch, rois_from_json, rois_to_json,
                                snapshot, summarize, uniformity)
from pear.core.attributes import SNR_ID, metric_label
from pear.ui import theme
from pear.ui.image_view import ImageView
from pear.ui.widgets import (AnalysisPanel, RailPanel, RoiInspector,
                             StageBar)

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
        self._selected_rids: set = set()   # rids marquee-selected on the canvas
        self._next_rid = 1
        self._metrics: List[str] = ["glv_mean", "glv_median"]
        self._show_metric = ""            # single metric drawn live on ROIs
        self._show_values = True          # print the shown metric on each ROI
        self._heatmap = False             # colour ROIs by the shown metric
        self._heat_field = False          # spread the heat over each ROI's cell
        self._flag_outliers = False       # flag Tukey outliers of the shown metric
        self._heat_alpha = 70             # heat fill opacity, percent
        self._roi_order = "placed"        # ROI list order: placed | asc | desc
        self._values: dict = {}           # rid -> shown metric, one pass per refresh
        self._outlier_rids: set = set()
        self._image_path: Optional[str] = None
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
        self._build_inspector_window()
        self._wire()
        self.rail.set_ready(False)
        self.stage_bar.setEnabled(False)

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
        self.project_btn = QToolButton()
        self.project_btn.setText("Project ▾")
        self.project_btn.setPopupMode(QToolButton.InstantPopup)
        pmenu = QMenu(self.project_btn)
        pmenu.addAction("Open project…", self.on_open_project)
        self._save_action = pmenu.addAction("Save project…", self.on_save_project)
        self.project_btn.setMenu(pmenu)
        self.analysis_btn_top = QPushButton("Analysis ⤢")
        self.analysis_btn_top.setToolTip("Open the analysis window.")
        self.analysis_btn_top.setEnabled(False)
        self.load_btn = QPushButton("Load…")
        self.load_btn.setObjectName("Primary")
        lay.addWidget(brand, 0, Qt.AlignVCenter)
        lay.addSpacing(8)
        lay.addWidget(sub)
        lay.addStretch(1)
        lay.addWidget(self.dataset_lbl)
        lay.addWidget(self.project_btn)
        lay.addWidget(self.analysis_btn_top)
        lay.addWidget(self.load_btn)
        self.setMenuWidget(bar)

    def _build_docks(self) -> None:
        self.image_view = ImageView()
        # The overlay controls sit on the stage, not at the bottom of the rail:
        # every one of them changes what the image looks like.
        self.stage_bar = StageBar()
        stage = QWidget()
        slay = QVBoxLayout(stage)
        slay.setContentsMargins(0, 0, 0, 0)
        slay.setSpacing(0)
        slay.addWidget(self.stage_bar)
        slay.addWidget(self.image_view, 1)
        self.setCentralWidget(stage)
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
        # the headline numbers, so the one figure you keep glancing at does
        # not need the Analysis window opened for it
        self.summary_lbl = QLabel("")
        self.summary_lbl.setObjectName("Mono")
        self.summary_lbl.setFont(theme.mono_font(9))
        bar.addPermanentWidget(self.summary_lbl)
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

    def _build_inspector_window(self) -> None:
        self.inspector = RoiInspector()
        self.inspector_window = QWidget()
        self.inspector_window.setWindowTitle("PEAR — ROI inspector")
        self.inspector_window.resize(600, 440)
        lay = QVBoxLayout(self.inspector_window)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.inspector)

    def _wire(self) -> None:
        self.load_btn.clicked.connect(self.on_load)
        self.analysis_btn_top.clicked.connect(self.open_analysis)
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
        self.rail.roi_pick.connect(self.select_roi)
        self.rail.roi_set_target.connect(self.set_target_roi)
        self.rail.roi_del.connect(self.delete_roi)
        self.rail.roi_hovered.connect(self.image_view.set_hover)
        self.rail.metrics_changed.connect(self.set_metrics)
        self.rail.metric_ids_changed.connect(self.stage_bar.set_metrics)
        self.rail.roi_order_changed.connect(self.on_roi_order)
        self.stage_bar.show_changed.connect(self.on_show_metric)
        self.stage_bar.values_changed.connect(self.on_show_values)
        self.stage_bar.heatmap_changed.connect(self.on_heatmap)
        self.stage_bar.cells_changed.connect(self.on_heat_field)
        self.stage_bar.outliers_changed.connect(self.on_flag_outliers)
        self.stage_bar.heat_alpha_changed.connect(self.on_heat_alpha)
        self.rail.open_analysis.connect(self.open_analysis)

        self.image_view.roi_created.connect(self.on_roi_created)
        self.image_view.grid_committed.connect(self.on_grid_committed)
        self.image_view.grid_ready.connect(self.rail.set_grid_ready)
        self.image_view.roi_modified.connect(self.on_roi_modified)
        self.image_view.roi_selected.connect(self.select_roi)
        self.image_view.roi_delete_requested.connect(self.delete_roi)
        self.image_view.rois_selected.connect(self.on_marquee_selected)
        self.image_view.rois_delete_requested.connect(self.delete_rois)
        self.image_view.roi_hovered.connect(self.rail.set_hovered_roi)
        self.image_view.roi_duplicate_requested.connect(self.duplicate_roi)
        self.image_view.roi_inspect_requested.connect(self.open_inspector)
        self.image_view.group_index_requested.connect(self.select_group_by_index)
        self.image_view.cursor_info.connect(self.cursor_lbl.setText)
        self.image_view.zoom_changed.connect(
            lambda s: self.zoom_lbl.setText(f"{int(round(s * 100))}%"))

        self.analysis.mode_changed.connect(self.on_cmp_mode)
        self.analysis.within_group_changed.connect(self.on_within_group)
        self.analysis.export_requested.connect(self.export_csv)
        self.analysis.export_image_requested.connect(self.export_chart_image)

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
        self._image_path = path

    def set_image(self, img: np.ndarray, name: str = "image") -> None:
        self._image = img
        self._image_path = None
        self._groups = []
        self._rois = []
        self._active_gid = None
        self._active_rid = None
        self._selected_rids = set()
        self._outlier_rids = set()
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
        self._selected_rids = set()          # a single pick clears the marquee set
        roi = self._roi(rid)
        if roi is not None and roi.gid != self._active_gid:
            self._active_gid = roi.gid
        self._refresh()

    def set_target_roi(self, rid: int) -> None:
        """Tag an ROI as its group's SNR target (toggle off if already target)."""
        roi = self._roi(rid)
        if roi is None:
            return
        g = self._group(roi.gid)
        if g is not None:
            g.target_rid = None if g.target_rid == rid else rid
            self._refresh()

    def on_marquee_selected(self, rids) -> None:
        self._selected_rids = set(rids or [])
        self._refresh()
        if self._selected_rids:
            self.statusBar().showMessage(
                f"{len(self._selected_rids)} ROIs selected · Delete to remove.",
                4000)

    def duplicate_roi(self, rid: int) -> None:
        src = self._roi(rid)
        if src is None:
            return
        x, y, w, h = src.rect
        nx, ny = x + 8, y + 8
        if self._image is not None:
            ih, iw = self._image.shape[:2]
            nx, ny = max(0, min(nx, iw - w)), max(0, min(ny, ih - h))
        roi = ROI(rid=self._next_rid, gid=src.gid, rect=(nx, ny, w, h), label="")
        self._next_rid += 1
        self._rois.append(roi)
        self._active_gid = src.gid
        self._active_rid = roi.rid
        self._selected_rids = set()
        self._refresh()

    def select_group_by_index(self, i: int) -> None:
        if 0 <= i < len(self._groups):
            self.select_group(self._groups[i].gid)

    def delete_roi(self, rid: int) -> None:
        self._rois = [r for r in self._rois if r.rid != rid]
        if self._active_rid == rid:
            self._active_rid = None
        self._selected_rids.discard(rid)
        self._drop_targets({rid})
        self._refresh()

    def delete_rois(self, rids) -> None:
        rid_set = set(rids or [])
        if not rid_set:
            return
        self._rois = [r for r in self._rois if r.rid not in rid_set]
        if self._active_rid in rid_set:
            self._active_rid = None
        self._selected_rids -= rid_set
        self._drop_targets(rid_set)
        self.statusBar().showMessage(f"Deleted {len(rid_set)} ROIs.", 3000)
        self._refresh()

    def _drop_targets(self, rid_set: set) -> None:
        for g in self._groups:
            if g.target_rid in rid_set:
                g.target_rid = None

    def _target_of_active(self) -> Optional[int]:
        g = self._group(self._active_gid)
        return g.target_rid if g is not None else None

    # ------------------------------------------------------------------ #
    # metrics / comparison
    # ------------------------------------------------------------------ #
    def set_metrics(self, metrics: List[str]) -> None:
        self._metrics = list(metrics)
        self._render_analysis()

    def on_show_metric(self, mid: str) -> None:
        self._show_metric = mid or ""
        self._refresh()

    def on_show_values(self, on: bool) -> None:
        self._show_values = bool(on)
        self._refresh()

    def on_heat_field(self, on: bool) -> None:
        self._heat_field = bool(on)
        self._update_heatmap()

    def on_roi_order(self, order: str) -> None:
        self._roi_order = order if order in ("placed", "asc", "desc") else "placed"
        self._refresh()

    def on_heat_alpha(self, pct: int) -> None:
        self._heat_alpha = int(max(0, min(100, int(pct))))
        self._update_heatmap()

    def on_heatmap(self, on: bool) -> None:
        self._heatmap = bool(on)
        if on and not self._is_glv_show():
            self.statusBar().showMessage(
                "Pick a GLV metric in “show on ROIs” to colour the heatmap.", 4000)
        self._refresh()

    def on_flag_outliers(self, on: bool) -> None:
        self._flag_outliers = bool(on)
        if on and not self._is_glv_show():
            self.statusBar().showMessage(
                "Pick a GLV metric in “show on ROIs” to flag outliers.", 4000)
        self._refresh()

    def _is_glv_show(self) -> bool:
        return bool(self._show_metric) and self._show_metric != SNR_ID

    def _update_heatmap(self) -> None:
        if self._heatmap and self._image is not None and self._is_glv_show():
            vals = self._values
            finite = [v for v in vals.values() if np.isfinite(v)]
            if finite:
                vmin, vmax = min(finite), max(finite)
                span = (vmax - vmin) or 1.0
                colors = {rid: heat_color((v - vmin) / span)
                          for rid, v in vals.items() if np.isfinite(v)}
                self.image_view.set_heatmap(
                    colors, (vmin, vmax, metric_label(self._show_metric)),
                    round(self._heat_alpha * 2.55))
                shape = self._image.shape[:2]
                self.image_view.set_heat_cells(
                    heat_cells(self._rois, (shape[1], shape[0]))
                    if self._heat_field else {})
                return
        self.image_view.set_heatmap({}, None)
        self.image_view.set_heat_cells({})

    def _compute_values(self) -> None:
        """``rid -> shown metric``, once per refresh.

        The canvas labels, the heatmap, the ROI list and the status readout
        all want the same numbers; computing them here keeps one pass over the
        pixels instead of four.
        """
        vals: dict = {}
        if self._image is not None and self._show_metric:
            if self._show_metric == SNR_ID:
                # SNR is a per-group value; it belongs to the target (T) ROI.
                for g in self._groups:
                    v = group_snr(self._image, group_rois(self._rois, g.gid),
                                  g.target_rid)
                    if v is not None and g.target_rid is not None:
                        vals[g.target_rid] = float(v)
            else:
                for r in self._rois:
                    vals[r.rid] = roi_metric(self._image, r, self._show_metric)
        self._values = vals

    def _update_roi_values(self) -> None:
        if not self._show_values or not self._values:
            self.image_view.set_roi_values({})
            return
        self.image_view.set_roi_values(
            {rid: f"{v:.3g}" for rid, v in self._values.items()})

    def _update_summary(self) -> None:
        """Headline numbers in the status bar — counts, then the shown metric."""
        if self._image is None:
            self.summary_lbl.setText("")
            return
        parts = [f"{len(self._groups)} groups · {len(self._rois)} ROIs"]
        vals = np.asarray([v for v in self._values.values() if np.isfinite(v)],
                          dtype=np.float64)
        if vals.size:
            u = uniformity(vals)
            parts.append(f"{metric_label(self._show_metric)}: "
                         f"mean {u['mean']:.4g} · range {u['range']:.3g} "
                         f"· CV {u['cv_pct']:.2f}%")
        self.summary_lbl.setText("   ".join(parts))

    def _ordered_rois(self, rois):
        """The active group's ROIs in list order — as placed, or by value."""
        if self._roi_order == "placed" or not self._values:
            return rois
        rev = self._roi_order == "desc"

        def key(r):
            v = self._values.get(r.rid)
            if v is None or not np.isfinite(v):
                return (1, 0.0)      # no value (SNR reference) — keep it last
            return (0, -v if rev else v)

        return sorted(rois, key=key)

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

    def open_inspector(self, rid: int) -> None:
        self.select_roi(rid)
        self.inspector_window.show()
        self.inspector_window.raise_()
        self.inspector_window.activateWindow()
        self._update_inspector()

    def _update_inspector(self) -> None:
        if not self.inspector_window.isVisible():
            return
        roi = self._roi(self._active_rid)
        if roi is None or self._image is None:
            self.inspector.set_roi(None, "")
            return
        g = self._group(roi.gid)
        title = (f"{roi.label or ('ROI ' + str(roi.rid))} · "
                 f"{roi.rect[2]}×{roi.rect[3]}"
                 + (f" · {g.name}" if g is not None else ""))
        self.inspector.set_roi(roi_patch(self._image, roi.rect), title)

    # ------------------------------------------------------------------ #
    # refresh
    # ------------------------------------------------------------------ #
    def _renumber(self) -> None:
        """Re-index each group's ROI display labels 1..n (rids stay unique)."""
        for g in self._groups:
            for i, r in enumerate(group_rois(self._rois, g.gid), 1):
                r.label = f"ROI {i}"

    def _refresh(self) -> None:
        self._renumber()
        has_img = self._image is not None
        self.rail.set_ready(has_img)
        self.stage_bar.setEnabled(has_img)   # nothing to overlay without one
        self.analysis_btn_top.setEnabled(has_img)
        self._save_action.setEnabled(has_img)
        self._outlier_rids = (
            group_outliers(self._image, self._rois, self._show_metric)
            if (self._flag_outliers and has_img and self._is_glv_show())
            else set())
        self._compute_values()
        counts = {g.gid: len(group_rois(self._rois, g.gid)) for g in self._groups}
        self.rail.set_groups(self._groups, self._active_gid, counts)
        self.rail.set_rois(
            self._ordered_rois(group_rois(self._rois, self._active_gid)),
            self._active_rid, self._target_of_active(),
            self._selected_rids, self._outlier_rids, self._values)
        self.image_view.set_groups(self._groups, self._active_gid)
        self.image_view.set_rois(self._rois, self._active_rid)
        self.image_view.set_selection(self._selected_rids)
        self.image_view.set_outliers(self._outlier_rids)
        self._update_roi_values()
        self._update_heatmap()
        self._update_summary()
        self._update_inspector()
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
                self._within_gid)
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
                                  self._cmp_mode, self._within_gid)
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
    # project save / open (JSON)
    # ------------------------------------------------------------------ #
    def on_open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open project", "", "PEAR project (*.pear.json *.json)")
        if path:
            self.open_project(path)

    def on_save_project(self) -> None:
        if self._image is None:
            QMessageBox.information(self, "Save project", "Load an image first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save project", "project.pear.json",
            "PEAR project (*.pear.json *.json)")
        if path:
            self.save_project(path)
            self.statusBar().showMessage(
                f"Saved project → {os.path.basename(path)}", 3000)

    def _project_dict(self) -> dict:
        shape = list(self._image.shape[:2]) if self._image is not None else None
        return {
            "app": "PEAR", "version": 1,
            "image_path": self._image_path,
            "image_shape": shape,
            "groups": groups_to_json(self._groups),
            "rois": rois_to_json(self._rois),
            "next_rid": self._next_rid,
            "metrics": list(self._metrics),
            "show_metric": self._show_metric,
            "show_values": self._show_values,
            "heatmap": self._heatmap,
            "heat_field": self._heat_field,
            "flag_outliers": self._flag_outliers,
            "heat_alpha": self._heat_alpha,
            "roi_order": self._roi_order,
            "cmp_mode": self._cmp_mode,
            "within_gid": self._within_gid,
            "active_gid": self._active_gid,
            "chart_type": self.analysis.chart_state()[0],
            "pos_axis": self.analysis.chart_state()[1],
        }

    def save_project(self, path: str) -> str:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self._project_dict(), fh, indent=2, ensure_ascii=False)
        return path

    def open_project(self, path: str) -> Optional[str]:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        ipath = data.get("image_path")
        if ipath and os.path.exists(ipath):
            try:
                self.set_image(load_image(ipath), os.path.basename(ipath))
                self._image_path = ipath
            except Exception:  # noqa: BLE001
                pass
        if self._image is None:
            QMessageBox.warning(
                self, "Open project",
                "The project's image was not found. Load the image first, "
                "then open the project again.")
            return None
        self._restore_project(data)
        return path

    def _restore_project(self, data: dict) -> None:
        self._groups = groups_from_json(data.get("groups"))
        self._rois = rois_from_json(data.get("rois"))
        self._next_rid = int(data.get("next_rid")
                             or (max((r.rid for r in self._rois), default=0) + 1))
        self._metrics = list(data.get("metrics") or ["glv_mean", "glv_median"])
        self._show_metric = data.get("show_metric") or ""
        self._show_values = bool(data.get("show_values", True))
        self._heatmap = bool(data.get("heatmap", False))
        self._heat_field = bool(data.get("heat_field", False))
        self._flag_outliers = bool(data.get("flag_outliers", False))
        self._heat_alpha = int(data.get("heat_alpha", 70))
        order = data.get("roi_order", "placed")
        self._roi_order = order if order in ("placed", "asc", "desc") else "placed"
        self._cmp_mode = data.get("cmp_mode", "between")
        self._within_gid = data.get("within_gid")
        self._active_gid = (data.get("active_gid")
                            or (self._groups[0].gid if self._groups else None))
        self._active_rid = None
        self._selected_rids = set()
        self.rail.set_metric_state(self._metrics, [self._show_metric])
        self.rail.set_roi_order(self._roi_order)
        self.stage_bar.set_metrics(self.rail.metrics.ids())
        self.stage_bar.set_state(self._show_metric, self._show_values,
                                 self._heatmap, self._heat_field,
                                 self._flag_outliers, self._heat_alpha)
        self.analysis.set_chart_state(data.get("chart_type", "box"),
                                      data.get("pos_axis", "x"))
        self._refresh()

    # ------------------------------------------------------------------ #
    # export
    # ------------------------------------------------------------------ #
    def export_chart_image(self, path: Optional[str] = None) -> Optional[str]:
        """Save the chart sheet for a report — PNG at 3×, or SVG for print."""
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self.analysis_window, "Export chart image", "pear_chart.png",
                "PNG image (*.png);;SVG vector (*.svg)")
            if not path:
                return None
        out = self.analysis.save_charts_image(path)
        if out is None:
            QMessageBox.warning(
                self, "Export chart image",
                "Nothing to export — open a chart first. SVG also needs "
                "PySide6's QtSvg module.")
            return None
        self.statusBar().showMessage(f"Chart image written to {out}", 4000)
        return out

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
            header = ["group", "roi", "role", "x", "y", "w", "h",
                      "center_x", "center_y"] + \
                     [metric_label(m) for m in self._metrics]
            w.writerow(header)
            for g in self._groups:
                grois = group_rois(self._rois, g.gid)
                gsnr = group_snr(self._image, grois, g.target_rid)
                for roi in grois:
                    x, y, wid, hei = roi.rect
                    role = ("T" if roi.rid == g.target_rid
                            else ("R" if g.target_rid is not None else ""))
                    cx, cy = roi_center(roi.rect)
                    row = [g.name, roi.label, role, x, y, wid, hei,
                           f"{cx:g}", f"{cy:g}"]
                    for mid in self._metrics:
                        if mid == SNR_ID:
                            # SNR is per group; report it on the target row only
                            row.append(f"{gsnr:.6g}" if (roi.rid == g.target_rid
                                       and gsnr is not None) else "")
                        else:
                            row.append(f"{roi_metric(self._image, roi, mid):.6g}")
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
                    if mid == SNR_ID:
                        s = group_snr(self._image, grois, g.target_rid)
                        line.append(f"{s:.6g}" if s is not None else "")
                    else:
                        vals = np.array([roi_metric(self._image, r, mid)
                                         for r in grois])
                        line.append(f"{summarize(vals)['mean']:.6g}")
                w.writerow(line)
