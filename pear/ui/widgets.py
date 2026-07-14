"""Workspace widgets: the control rail (Lattice / Groups / ROIs / Metrics),
a box-and-strip distribution chart, and the Analysis panel (hosted in its own
window).

No charting dependency — every plot is hand-painted with QPainter.
"""

from __future__ import annotations

from typing import Callable, List, Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QColorDialog, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from pear.core.analysis import Group
from pear.core.attributes import (GLV_STATS, SNR_ID, metric_formula,
                                  metric_label)
from pear.ui import theme


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _card(title: str, sub: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(10)
    head = QHBoxLayout()
    head.setSpacing(7)
    t = QLabel(title)
    t.setObjectName("SectionTitle")
    t.setFont(theme.display_font(13, weight=700))
    head.addWidget(t)
    if sub:
        s = QLabel(sub)
        s.setObjectName("Hint")
        head.addWidget(s)
    head.addStretch(1)
    frame._head = head           # type: ignore[attr-defined]
    lay.addLayout(head)
    return frame


def _swatch(color: str, on_pick: Callable[[str], None]) -> QPushButton:
    b = QPushButton()
    b.setFixedSize(16, 16)
    b.setStyleSheet(
        f"background:{color}; border:1px solid rgba(0,0,0,.15); border-radius:4px;")

    def choose():
        c = QColorDialog.getColor(QColor(color))
        if c.isValid():
            on_pick(c.name())
    b.clicked.connect(choose)
    return b


def _clear(layout) -> None:
    while layout.count():
        it = layout.takeAt(0)
        if it.widget():
            it.widget().deleteLater()


# --------------------------------------------------------------------------- #
# Distribution chart (box + jittered strip)
# --------------------------------------------------------------------------- #
class DistributionChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = ""
        self._series: List[dict] = []
        self.setMinimumHeight(96)

    def set_data(self, title: str, series: List[dict]) -> None:
        self._title = title
        clean = []
        for s in series:
            v = np.asarray(s["values"], dtype=np.float64)
            v = v[np.isfinite(v)]
            if v.size:
                clean.append({"label": s["label"], "color": s["color"], "values": v})
        self._series = clean
        n = max(1, len(self._series))
        self.setMinimumHeight(30 + n * 30 + 22)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.CARD))
        p.setPen(QColor(theme.INK))
        p.setFont(theme.display_font(11, weight=700))
        p.drawText(10, 16, self._title)
        if not self._series:
            p.setPen(QColor(theme.INK3))
            p.setFont(theme.mono_font(9))
            p.drawText(self.rect(), Qt.AlignCenter, "no data")
            p.end()
            return

        allv = np.concatenate([s["values"] for s in self._series])
        lo, hi = float(allv.min()), float(allv.max())
        if hi - lo < 1e-9:
            lo -= 0.5
            hi += 0.5
        pad = (hi - lo) * 0.06
        lo -= pad
        hi += pad
        L, R, top = 12, 62, 24
        W = max(10, self.width() - L - R)
        laneH = 30
        n = len(self._series)
        plot_bottom = top + n * laneH

        def X(v):
            return L + (v - lo) / (hi - lo) * W

        p.setFont(theme.mono_font(8))
        for t in range(5):
            gx = L + W * t / 4.0
            p.setPen(QPen(QColor(theme.LINE2), 1))
            p.drawLine(int(gx), top - 4, int(gx), int(plot_bottom + 2))
            p.setPen(QColor(theme.INK3))
            p.drawText(int(gx) - 14, int(plot_bottom + 14),
                       _fmt(lo + (hi - lo) * t / 4.0))

        for i, s in enumerate(self._series):
            v = s["values"]
            col = QColor(s["color"])
            yc = top + i * laneH + laneH / 2
            q25, med, q75 = (float(np.percentile(v, 25)),
                             float(np.median(v)), float(np.percentile(v, 75)))
            bh = laneH * 0.52
            box = QColor(col)
            box.setAlpha(48)
            p.setPen(QPen(col, 1))
            p.setBrush(box)
            p.drawRect(int(X(q25)), int(yc - bh / 2),
                       max(2, int(X(q75) - X(q25))), int(bh))
            dot = QColor(col)
            dot.setAlpha(190)
            p.setPen(Qt.NoPen)
            p.setBrush(dot)
            rngj = laneH * 0.34
            for k, val in enumerate(v):
                jitter = ((k % 7) / 6.0 - 0.5) * rngj
                p.drawEllipse(int(X(val)) - 3, int(yc + jitter) - 3, 6, 6)
            p.setPen(QPen(col, 2.4))
            p.drawLine(int(X(med)), int(yc - bh / 2 - 2),
                       int(X(med)), int(yc + bh / 2 + 2))
            p.setPen(QColor(theme.INK2))
            p.setFont(theme.mono_font(8))
            p.drawText(int(L + 3), int(yc - bh / 2 - 5), f"{s['label']} · n={v.size}")
            p.setPen(col)
            p.setFont(theme.mono_font(9, weight=700))
            p.drawText(self.width() - R + 5, int(yc + 4), _fmt(float(v.mean())))
        p.end()


def _fmt(v: float) -> str:
    a = abs(v)
    if a >= 1000 or (0 < a < 0.01):
        return f"{v:.2e}"
    return f"{v:.3g}"


# --------------------------------------------------------------------------- #
# Metric chips
# --------------------------------------------------------------------------- #
class _Chip(QPushButton):
    def __init__(self, mid: str, on: bool):
        super().__init__(metric_label(mid))
        self.mid = mid
        self.setCheckable(True)
        self.setChecked(on)
        self.setMinimumHeight(32)
        self.setStyleSheet("padding: 4px 10px;")   # avoid vertical text clipping
        self.setToolTip(f"{metric_label(mid)}\n{metric_formula(mid)}")


class MetricPicker(QWidget):
    changed = Signal(list)
    show_changed = Signal(str)          # metric id to draw on ROIs ("" = none)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected: List[str] = ["glv_mean", "glv_median"]
        self._custom: List[str] = []
        self._show = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        self._chip_host = QWidget()
        self._chip_lay = QGridLayout(self._chip_host)
        self._chip_lay.setContentsMargins(0, 0, 0, 0)
        self._chip_lay.setSpacing(6)
        root.addWidget(self._chip_host)
        qn = QHBoxLayout()
        qn.setSpacing(6)
        lab = QLabel("custom Q")
        lab.setObjectName("Hint")
        self.qn_spin = QSpinBox()
        self.qn_spin.setRange(1, 99)
        self.qn_spin.setValue(90)
        self.qn_spin.setFixedWidth(60)
        self.qn_spin.setMinimumHeight(28)
        add = QPushButton("Add")
        add.setMinimumHeight(28)
        add.clicked.connect(self._add_custom)
        qn.addWidget(lab)
        qn.addWidget(self.qn_spin)
        qn.addWidget(add)
        qn.addStretch(1)
        root.addLayout(qn)
        # single metric drawn live on each ROI in the image
        show = QHBoxLayout()
        show.setSpacing(6)
        show_lbl = QLabel("show on ROIs")
        show_lbl.setObjectName("Hint")
        self.show_combo = QComboBox()
        self.show_combo.setMinimumHeight(28)
        self.show_combo.currentIndexChanged.connect(self._on_show)
        show.addWidget(show_lbl)
        show.addWidget(self.show_combo, 1)
        root.addLayout(show)
        self._rebuild()

    def selected(self) -> List[str]:
        return list(self._selected)

    def _add_custom(self) -> None:
        mid = f"glv_q{int(self.qn_spin.value())}"
        if mid not in self._custom and mid not in GLV_STATS:
            self._custom.append(mid)
        if mid not in self._selected:
            self._selected.append(mid)
        self._rebuild()
        self.changed.emit(list(self._selected))

    def _ids(self) -> List[str]:
        return list(GLV_STATS.keys()) + self._custom + [SNR_ID]

    def _rebuild(self) -> None:
        while self._chip_lay.count():
            it = self._chip_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, mid in enumerate(self._ids()):
            chip = _Chip(mid, mid in self._selected)
            chip.clicked.connect(lambda _=False, m=mid: self._toggle(m))
            self._chip_lay.addWidget(chip, i // 3, i % 3)
        # rebuild the "show on ROIs" combo, preserving the selection
        self.show_combo.blockSignals(True)
        self.show_combo.clear()
        self.show_combo.addItem("— none —", "")
        for mid in self._ids():
            self.show_combo.addItem(metric_label(mid), mid)
        idx = self.show_combo.findData(self._show)
        self.show_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.show_combo.blockSignals(False)

    def _toggle(self, mid: str) -> None:
        if mid in self._selected:
            self._selected.remove(mid)
        else:
            self._selected.append(mid)
        self.changed.emit(list(self._selected))

    def _on_show(self, _i: int) -> None:
        self._show = self.show_combo.currentData() or ""
        self.show_changed.emit(self._show)


# --------------------------------------------------------------------------- #
# Control rail
# --------------------------------------------------------------------------- #
class RailPanel(QWidget):
    group_add = Signal()
    group_pick = Signal(str)
    group_del = Signal(str)
    group_color = Signal(str, str)
    group_rename = Signal(str, str)
    group_clear = Signal(str)
    grid_mode_toggled = Signal(bool)
    grid_commit = Signal()
    grid_shape_changed = Signal(int, int)
    roi_size_changed = Signal(int, int)     # ROI W × H for click / grid
    roi_del = Signal(int)
    metrics_changed = Signal(list)
    show_metric_changed = Signal(str)
    open_analysis = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # Groups
        grp = _card("Groups", "categories")
        glay = grp.layout()
        self.grp_add_btn = QPushButton("+ Add group")
        self.grp_add_btn.clicked.connect(self.group_add)
        glay.addLayout(_button_row(self.grp_add_btn))
        self.grp_host = QVBoxLayout()
        self.grp_host.setSpacing(6)
        glay.addLayout(self.grp_host)
        hint = QLabel("Pick a group, then add ROIs to it on the image.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        glay.addWidget(hint)
        root.addWidget(grp)

        # ROIs (of the active group)
        roi = _card("ROIs", "of active group")
        rlay = roi.layout()
        self.grid_btn = QPushButton("▦ Grid")
        self.grid_btn.setCheckable(True)
        self.grid_btn.setToolTip("Click the top-left then bottom-right corner "
                                 "on the image; a row×col preview follows.")
        self.grid_btn.toggled.connect(self.grid_mode_toggled)
        self.add_grid_btn = QPushButton("✓ Add grid")
        self.add_grid_btn.setToolTip("Place the previewed grid (or press Enter).")
        self.add_grid_btn.setEnabled(False)
        self.add_grid_btn.clicked.connect(self.grid_commit)
        rlay.addLayout(_button_row(self.grid_btn, self.add_grid_btn))
        # ROI size (W × H) used by click-to-place and by the grid
        szrow = QHBoxLayout()
        szrow.setSpacing(8)
        szl = QLabel("size")
        szl.setObjectName("Hint")
        szrow.addWidget(szl)
        self.roi_w = QSpinBox()
        self.roi_w.setRange(4, 4000)
        self.roi_w.setValue(28)
        self.roi_h = QSpinBox()
        self.roi_h.setRange(4, 4000)
        self.roi_h.setValue(28)
        for sp in (self.roi_w, self.roi_h):
            sp.setMinimumHeight(28)
            sp.valueChanged.connect(
                lambda _=0: self.roi_size_changed.emit(*self.roi_size()))
        szrow.addWidget(self.roi_w, 1)
        szrow.addWidget(QLabel("×"))
        szrow.addWidget(self.roi_h, 1)
        rlay.addLayout(szrow)
        grow = QHBoxLayout()
        grow.setSpacing(8)
        gl = QLabel("grid")
        gl.setObjectName("Hint")
        grow.addWidget(gl)
        self.grid_rows = QSpinBox()
        self.grid_rows.setRange(1, 100)
        self.grid_rows.setValue(3)
        self.grid_cols = QSpinBox()
        self.grid_cols.setRange(1, 100)
        self.grid_cols.setValue(3)
        for sp in (self.grid_rows, self.grid_cols):
            sp.setMinimumHeight(28)
            sp.valueChanged.connect(
                lambda _=0: self.grid_shape_changed.emit(*self.grid_shape()))
        grow.addWidget(self.grid_rows, 1)
        grow.addWidget(QLabel("×"))
        grow.addWidget(self.grid_cols, 1)
        rlay.addLayout(grow)
        self.roi_host = QVBoxLayout()
        self.roi_host.setSpacing(4)
        rlay.addLayout(self.roi_host)
        self.roi_hint = QLabel(
            "• Click → drop a size-W×H ROI · drag → custom size\n"
            "• Grid → click two corners, set row×col, Add grid")
        self.roi_hint.setObjectName("Hint")
        self.roi_hint.setWordWrap(True)
        rlay.addWidget(self.roi_hint)
        self.clear_btn = QPushButton("Clear group’s ROIs")
        self.clear_btn.clicked.connect(self._clear_active)
        rlay.addLayout(_button_row(self.clear_btn))
        root.addWidget(roi)

        # Metrics
        met = _card("Metrics", "per ROI")
        self.metrics = MetricPicker()
        self.metrics.changed.connect(self.metrics_changed)
        self.metrics.show_changed.connect(self.show_metric_changed)
        met.layout().addWidget(self.metrics)
        root.addWidget(met)

        self.analysis_btn = QPushButton("Open analysis ⤢")
        self.analysis_btn.setObjectName("Primary")
        self.analysis_btn.clicked.connect(self.open_analysis)
        root.addLayout(_button_row(self.analysis_btn))
        root.addStretch(1)

        self._active_gid: Optional[str] = None

    # -- render --------------------------------------------------------- #
    def set_ready(self, has_image: bool) -> None:
        for w in (self.grp_add_btn, self.grid_btn, self.roi_w, self.roi_h,
                  self.clear_btn, self.analysis_btn):
            w.setEnabled(has_image)

    def set_grid_ready(self, on: bool) -> None:
        self.add_grid_btn.setEnabled(on)

    def set_groups(self, groups: List[Group], active_gid, counts: dict) -> None:
        self._active_gid = active_gid
        _clear(self.grp_host)
        for g in groups:
            self.grp_host.addWidget(
                self._group_row(g, g.gid == active_gid, counts.get(g.gid, 0)))

    def set_rois(self, active_group_rois, active_rid) -> None:
        _clear(self.roi_host)
        for r in active_group_rois:
            self.roi_host.addWidget(self._roi_row(r, r.rid == active_rid))

    def grid_shape(self):
        return int(self.grid_rows.value()), int(self.grid_cols.value())

    def roi_size(self):
        return int(self.roi_w.value()), int(self.roi_h.value())

    def _group_row(self, g: Group, active: bool, count: int) -> QWidget:
        row = _ItemRow(active)
        row.add_swatch(g.color, lambda c: self.group_color.emit(g.gid, c))
        row.add_name(g.name, lambda t: self.group_rename.emit(g.gid, t))
        row.add_count(f"{count}")
        row.add_delete(lambda: self.group_del.emit(g.gid))
        row.clicked = lambda: self.group_pick.emit(g.gid)
        return row

    def _roi_row(self, r, active: bool) -> QWidget:
        row = _ItemRow(active, compact=True)
        row.add_name(r.label or f"ROI {r.rid}", None)
        row.add_count(f"{r.rect[2]}×{r.rect[3]}")
        row.add_delete(lambda: self.roi_del.emit(r.rid))
        return row

    def _clear_active(self) -> None:
        if self._active_gid is not None:
            self.group_clear.emit(self._active_gid)


def _button_row(*buttons):
    """A full-width row of equal-stretch buttons — responsive, no cramming."""
    row = QHBoxLayout()
    row.setSpacing(8)
    for b in buttons:
        b.setMinimumHeight(32)
        row.addWidget(b, 1)
    return row


class _ItemRow(QFrame):
    def __init__(self, active: bool, compact: bool = False):
        super().__init__()
        self.clicked: Optional[Callable] = None
        self.setStyleSheet(
            f"background:{theme.AMBER_SOFT if active else theme.CARD};"
            f"border:1px solid {theme.AMBER if active else theme.LINE};"
            "border-radius:9px;")
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(8, 3 if compact else 5, 8, 3 if compact else 5)
        self.lay.setSpacing(8)

    def add_swatch(self, color, on_pick):
        self.lay.addWidget(_swatch(color, on_pick))

    def add_name(self, name, on_rename):
        if on_rename is None:
            lbl = QLabel(name)
            lbl.setStyleSheet("font-weight:600;")
            self.lay.addWidget(lbl)
        else:
            ed = QLineEdit(name)
            ed.setFrame(False)
            ed.setStyleSheet("QLineEdit{background:transparent; border:none; "
                             "font-weight:600; padding:0;} "
                             "QLineEdit:focus{border:none;}")
            ed.editingFinished.connect(lambda: on_rename(ed.text().strip() or name))
            self.lay.addWidget(ed)
        self.lay.addStretch(1)

    def add_count(self, text):
        c = QLabel(text)
        c.setStyleSheet(f"color:{theme.INK2};")
        c.setFont(theme.mono_font(9))
        self.lay.addWidget(c)

    def add_delete(self, on_del):
        b = QPushButton("×")
        b.setFixedSize(20, 20)
        b.setStyleSheet(f"border:none; color:{theme.INK3}; font-size:15px;")
        b.clicked.connect(on_del)
        self.lay.addWidget(b)

    def mousePressEvent(self, e):
        if self.clicked and self.childAt(e.position().toPoint()) is None:
            self.clicked()
        super().mousePressEvent(e)


# --------------------------------------------------------------------------- #
# Analysis panel (hosted in its own window)
# --------------------------------------------------------------------------- #
class AnalysisPanel(QWidget):
    mode_changed = Signal(str)              # "between" | "within"
    within_group_changed = Signal(str)
    export_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(12)
        title = QLabel("Analysis")
        title.setFont(theme.display_font(14, weight=700))
        head.addWidget(title)
        self.busy = QLabel("")
        self.busy.setObjectName("Hint")
        head.addWidget(self.busy)
        self.between_btn = QPushButton("Between groups")
        self.within_btn = QPushButton("Within a group")
        for b, m in ((self.between_btn, "between"), (self.within_btn, "within")):
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.clicked.connect(lambda _=False, mm=m: self._pick_mode(mm))
            head.addWidget(b)
        self.between_btn.setChecked(True)
        self.selector_lbl = QLabel("")
        self.selector_lbl.setObjectName("Hint")
        head.addWidget(self.selector_lbl)
        self.selector = QComboBox()
        self.selector.setMinimumWidth(150)
        self.selector.currentIndexChanged.connect(self._selector_changed)
        head.addWidget(self.selector)
        head.addStretch(1)
        self.sub = QLabel("")
        self.sub.setObjectName("Hint")
        head.addWidget(self.sub)
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setObjectName("Primary")
        self.export_btn.clicked.connect(self.export_requested)
        self.export_btn.setEnabled(False)
        head.addWidget(self.export_btn)
        root.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(10)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)

        self._mode = "between"
        self._suppress = False

    def _pick_mode(self, mode: str) -> None:
        self._mode = mode
        self.between_btn.setChecked(mode == "between")
        self.within_btn.setChecked(mode == "within")
        self.mode_changed.emit(mode)

    def _selector_changed(self, _i: int) -> None:
        if self._suppress:
            return
        data = self.selector.currentData()
        if data is not None and self._mode == "within":
            self.within_group_changed.emit(str(data))

    def set_controls(self, mode, groups, within_gid, enabled) -> None:
        self._mode = mode
        self.between_btn.setChecked(mode == "between")
        self.within_btn.setChecked(mode == "within")
        self._suppress = True
        self.selector.clear()
        if mode == "within":
            self.selector_lbl.setText("Group")
            self.selector.setVisible(True)
            for g in groups:
                self.selector.addItem(g.name, g.gid)
            self.selector.setCurrentIndex(_gindex_of(groups, within_gid))
        else:
            self.selector_lbl.setText("")
            self.selector.setVisible(False)
        self._suppress = False
        self.export_btn.setEnabled(bool(enabled))

    def set_computing(self, on: bool) -> None:
        self.busy.setText("· working…" if on else "")

    def show_result(self, result) -> None:
        _clear(self.body_lay)
        self.sub.setText(result.subtitle)
        if result.empty:
            self._empty(result.empty)
            return
        charts = [(c.title, [{"label": s.label, "color": s.color,
                              "values": s.values} for s in c.series])
                  for c in result.charts]
        self._chart_grid(charts)
        if result.table_rows:
            self._table(result.table_headers, result.table_rows)

    def _chart_grid(self, charts) -> None:
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        for i, (title, series) in enumerate(charts):
            chart = DistributionChart()
            chart.set_data(title, series)
            grid.addWidget(chart, i // 2, i % 2)
        self.body_lay.addWidget(grid_host)

    def _table(self, headers, rows) -> None:
        host = QFrame()
        host.setObjectName("Card")
        lay = QGridLayout(host)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        for c, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(f"color:{theme.INK3}; font-weight:600;")
            lbl.setFont(theme.mono_font(8))
            lay.addWidget(lbl, 0, c)
        for r, (name, color, cells) in enumerate(rows, start=1):
            nm = QLabel((("■ " + name) if color else name))
            nm.setStyleSheet(f"color:{color or theme.INK2}; font-weight:600;")
            lay.addWidget(nm, r, 0)
            for c, val in enumerate(cells, start=1):
                cell = QLabel(val)
                cell.setFont(theme.mono_font(9))
                lay.addWidget(cell, r, c)
        self.body_lay.addWidget(host)

    def _empty(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setObjectName("Hint")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setMinimumHeight(160)
        self.body_lay.addWidget(lbl)


def _gindex_of(groups, gid):
    for i, g in enumerate(groups):
        if g.gid == gid:
            return i
    return 0
