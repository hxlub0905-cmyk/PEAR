"""Workspace widgets: the control rail (Lattice / Groups / ROIs / Metrics),
a clean box-and-strip distribution chart, and the Analysis panel.

No charting dependency — every plot is hand-painted with QPainter. The
distribution chart uses a box + jittered strip (robust for the small,
well-separated samples this tool produces) instead of a histogram.
"""

from __future__ import annotations

from typing import Callable, List, Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QColorDialog, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from pear.core.analysis import ROI, Group, PeriodInfo, REFERENCE, TARGET
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


def _tr_toggle(role: str, on_set: Callable[[str], None]) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(3)
    for letter, this_role, col in (("T", TARGET, theme.TARGET),
                                   ("R", REFERENCE, theme.REFERENCE)):
        b = QPushButton(letter)
        b.setFixedSize(22, 20)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(_tr_style(col, role == this_role))
        b.clicked.connect(lambda _=False, rr=this_role: on_set(rr))
        lay.addWidget(b)
    return w


def _tr_style(color: str, on: bool) -> str:
    if on:
        return (f"QPushButton{{background:{color}; color:#fff; border:1px solid {color};"
                " border-radius:5px; padding:0; font-weight:800; font-size:11px;}")
    return (f"QPushButton{{background:{theme.PANEL}; color:{theme.INK3};"
            f" border:1px solid {theme.LINE}; border-radius:5px; padding:0;"
            " font-weight:800; font-size:11px;}")


# --------------------------------------------------------------------------- #
# Distribution chart (box + jittered strip)
# --------------------------------------------------------------------------- #
class DistributionChart(QWidget):
    """One metric, several series (groups or ROIs) as stacked box+strip lanes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = ""
        self._series: List[dict] = []      # {label,color,values}
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

        # vertical gridlines + axis ticks
        p.setFont(theme.mono_font(8))
        for t in range(5):
            gx = L + W * t / 4.0
            p.setPen(QPen(QColor(theme.LINE2), 1))
            p.drawLine(int(gx), top - 4, int(gx), int(plot_bottom + 2))
            p.setPen(QColor(theme.INK3))
            val = lo + (hi - lo) * t / 4.0
            p.drawText(int(gx) - 14, int(plot_bottom + 14), _fmt(val))

        for i, s in enumerate(self._series):
            v = s["values"]
            col = QColor(s["color"])
            yc = top + i * laneH + laneH / 2
            q25, med, q75 = (float(np.percentile(v, 25)),
                             float(np.median(v)), float(np.percentile(v, 75)))
            bh = laneH * 0.52
            # box Q25..Q75
            box = QColor(col)
            box.setAlpha(48)
            p.setPen(QPen(col, 1))
            p.setBrush(box)
            p.drawRect(int(X(q25)), int(yc - bh / 2),
                       max(2, int(X(q75) - X(q25))), int(bh))
            # jittered dots
            dot = QColor(col)
            dot.setAlpha(190)
            p.setPen(Qt.NoPen)
            p.setBrush(dot)
            rngj = laneH * 0.34
            for k, val in enumerate(v):
                jitter = ((k % 7) / 6.0 - 0.5) * rngj
                p.drawEllipse(int(X(val)) - 3, int(yc + jitter) - 3, 6, 6)
            # median tick
            p.setPen(QPen(col, 2.4))
            p.drawLine(int(X(med)), int(yc - bh / 2 - 2),
                       int(X(med)), int(yc + bh / 2 + 2))
            # left label + right mean value
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
        self.setFixedHeight(24)
        self.setToolTip(f"{metric_label(mid)}\n{metric_formula(mid)}")


class MetricPicker(QWidget):
    """GLV stat chips + custom Qn + SNR (SNR shown only when T/R split is on)."""

    changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected: List[str] = ["glv_mean", "glv_median"]
        self._custom: List[str] = []
        self._split = False
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
        add = QPushButton("Add")
        add.setFixedHeight(26)
        add.clicked.connect(self._add_custom)
        qn.addWidget(lab)
        qn.addWidget(self.qn_spin)
        qn.addWidget(add)
        qn.addStretch(1)
        root.addLayout(qn)
        self._rebuild()

    def set_split(self, on: bool) -> None:
        self._split = on
        if not on and SNR_ID in self._selected:
            self._selected.remove(SNR_ID)
            self.changed.emit(list(self._selected))
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
        ids = list(GLV_STATS.keys()) + self._custom
        if self._split:
            ids.append(SNR_ID)
        return ids

    def _rebuild(self) -> None:
        while self._chip_lay.count():
            it = self._chip_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, mid in enumerate(self._ids()):
            chip = _Chip(mid, mid in self._selected)
            chip.clicked.connect(lambda _=False, m=mid: self._toggle(m))
            self._chip_lay.addWidget(chip, i // 3, i % 3)

    def _toggle(self, mid: str) -> None:
        if mid in self._selected:
            self._selected.remove(mid)
        else:
            self._selected.append(mid)
        self.changed.emit(list(self._selected))


# --------------------------------------------------------------------------- #
# Control rail
# --------------------------------------------------------------------------- #
class RailPanel(QWidget):
    detect_requested = Signal()
    refine_requested = Signal()
    manual_changed = Signal(int, int, float)
    group_add = Signal()
    group_pick = Signal(str)
    group_del = Signal(str)
    group_role = Signal(str, str)
    group_color = Signal(str, str)
    group_rename = Signal(str, str)
    roi_add = Signal()
    roi_grid = Signal()
    roi_pick = Signal(int)
    roi_del = Signal(int)
    roi_role = Signal(int, str)
    roi_color = Signal(int, str)
    split_toggled = Signal(bool)
    metrics_changed = Signal(list)
    mode_changed = Signal(str)              # "group" | "roi"

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # Lattice
        lat = _card("Lattice", "cell grid")
        llay = lat.layout()
        self.period_lbl = QLabel("period —")
        self.period_lbl.setObjectName("Mono")
        self.period_lbl.setFont(theme.mono_font(10))
        llay.addWidget(self.period_lbl)
        row = QHBoxLayout()
        self.detect_btn = QPushButton("Detect")
        self.detect_btn.setObjectName("Primary")
        self.refine_btn = QPushButton("Refine")
        self.detect_btn.clicked.connect(self.detect_requested)
        self.refine_btn.clicked.connect(self.refine_requested)
        row.addWidget(self.detect_btn)
        row.addWidget(self.refine_btn)
        llay.addLayout(row)
        root.addWidget(lat)

        # Groups
        grp = _card("Groups", "sets of cells")
        self.grp_add_btn = QPushButton("+ Add")
        self.grp_add_btn.setFixedHeight(26)
        self.grp_add_btn.clicked.connect(self.group_add)
        grp._head.addWidget(self.grp_add_btn)      # type: ignore[attr-defined]
        glay = grp.layout()
        self.grp_host = QVBoxLayout()
        self.grp_host.setSpacing(6)
        glay.addLayout(self.grp_host)
        hint = QLabel("Paint mode: click / drag cells into the active group.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        glay.addWidget(hint)
        root.addWidget(grp)

        # ROIs
        roi = _card("ROIs", "measure window")
        self.roi_add_btn = QPushButton("+ Add")
        self.roi_grid_btn = QPushButton("Grid")
        for b in (self.roi_add_btn, self.roi_grid_btn):
            b.setFixedHeight(26)
        self.roi_add_btn.clicked.connect(self.roi_add)
        self.roi_grid_btn.clicked.connect(self.roi_grid)
        roi._head.addWidget(self.roi_add_btn)      # type: ignore[attr-defined]
        roi._head.addWidget(self.roi_grid_btn)     # type: ignore[attr-defined]
        rlay = roi.layout()
        from PySide6.QtWidgets import QCheckBox
        self.split_chk = QCheckBox("Split into Target / Reference (enables SNR)")
        self.split_chk.toggled.connect(self.split_toggled)
        rlay.addWidget(self.split_chk)
        self.roi_host = QVBoxLayout()
        self.roi_host.setSpacing(6)
        rlay.addLayout(self.roi_host)
        rhint = QLabel("Draw ROI mode: drag on the image. Each ROI repeats in "
                       "every cell.")
        rhint.setObjectName("Hint")
        rhint.setWordWrap(True)
        rlay.addWidget(rhint)
        root.addWidget(roi)

        # Metrics
        met = _card("Metrics", "per cell · per ROI")
        self.metrics = MetricPicker()
        self.metrics.changed.connect(self.metrics_changed)
        met.layout().addWidget(self.metrics)
        root.addWidget(met)
        root.addStretch(1)

    # -- render --------------------------------------------------------- #
    def set_period(self, period: Optional[PeriodInfo]) -> None:
        if period is None:
            self.period_lbl.setText("period —")
        else:
            self.period_lbl.setText(
                f"period {period.px} × {period.py} px · {period.axis_mode} · "
                f"{period.confidence:.0f}%")

    def set_groups(self, groups: List[Group], active_gid, split: bool) -> None:
        _clear(self.grp_host)
        for g in groups:
            self.grp_host.addWidget(self._group_row(g, g.gid == active_gid, split))

    def set_rois(self, rois: List[ROI], active_rid, split: bool) -> None:
        _clear(self.roi_host)
        for r in rois:
            self.roi_host.addWidget(self._roi_row(r, r.rid == active_rid, split))

    def _group_row(self, g: Group, active: bool, split: bool) -> QWidget:
        row = _ItemRow(active)
        row.add_swatch(g.color, lambda c: self.group_color.emit(g.gid, c))
        row.add_name(g.name, lambda t: self.group_rename.emit(g.gid, t))
        row.add_count(str(len(g.cells)))
        if split:
            row.add_tr(g.role, lambda role: self.group_role.emit(g.gid, role))
        row.add_delete(lambda: self.group_del.emit(g.gid))
        row.clicked = lambda: self.group_pick.emit(g.gid)
        return row

    def _roi_row(self, r: ROI, active: bool, split: bool) -> QWidget:
        row = _ItemRow(active)
        row.add_swatch(r.color, lambda c: self.roi_color.emit(r.rid, c))
        row.add_name(r.label, None)
        if split:
            row.add_tr(r.role, lambda role: self.roi_role.emit(r.rid, role))
        row.add_delete(lambda: self.roi_del.emit(r.rid))
        row.clicked = lambda: self.roi_pick.emit(r.rid)
        return row


class _ItemRow(QFrame):
    def __init__(self, active: bool):
        super().__init__()
        self.clicked: Optional[Callable] = None
        self.setStyleSheet(
            f"background:{theme.AMBER_SOFT if active else theme.CARD};"
            f"border:1px solid {theme.AMBER if active else theme.LINE};"
            "border-radius:9px;")
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(8, 5, 8, 5)
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
            ed.setStyleSheet("background:transparent; font-weight:600; padding:0;")
            ed.editingFinished.connect(lambda: on_rename(ed.text().strip() or name))
            self.lay.addWidget(ed)
        self.lay.addStretch(1)

    def add_count(self, text):
        c = QLabel(text)
        c.setStyleSheet(f"color:{theme.INK2};")
        c.setFont(theme.mono_font(10))
        self.lay.addWidget(c)

    def add_tr(self, role, on_set):
        self.lay.addWidget(_tr_toggle(role, on_set))

    def add_delete(self, on_del):
        b = QPushButton("×")
        b.setFixedSize(20, 20)
        b.setStyleSheet(f"border:none; color:{theme.INK3}; font-size:15px;")
        b.clicked.connect(on_del)
        self.lay.addWidget(b)

    def mousePressEvent(self, e):
        # ignore clicks on child controls (they handle their own)
        if self.clicked and self.childAt(e.position().toPoint()) in (None,):
            self.clicked()
        super().mousePressEvent(e)


def _clear(layout) -> None:
    while layout.count():
        it = layout.takeAt(0)
        if it.widget():
            it.widget().deleteLater()


# --------------------------------------------------------------------------- #
# Analysis panel (bottom dock / floatable window)
# --------------------------------------------------------------------------- #
class AnalysisPanel(QWidget):
    """Between-groups and within-group comparison with box+strip charts."""

    mode_changed = Signal(str)          # "between" | "within"
    between_roi_changed = Signal(int)
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
        head.addWidget(self.export_btn)
        root.addLayout(head)

        self.snr_lbl = QLabel("")
        self.snr_lbl.setObjectName("Measured")
        self.snr_lbl.setFont(theme.mono_font(10))
        self.snr_lbl.setVisible(False)
        root.addWidget(self.snr_lbl)

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
        self._between_rid: Optional[int] = None
        self._within_gid: Optional[str] = None
        self._suppress = False

    # -- controls ------------------------------------------------------- #
    def _pick_mode(self, mode: str) -> None:
        self._mode = mode
        self.between_btn.setChecked(mode == "between")
        self.within_btn.setChecked(mode == "within")
        self.mode_changed.emit(mode)

    def _selector_changed(self, _i: int) -> None:
        if self._suppress:
            return
        data = self.selector.currentData()
        if data is None:
            return
        if self._mode == "between":
            self.between_roi_changed.emit(int(data))
        else:
            self.within_group_changed.emit(str(data))

    # -- controls (sync, cheap) ---------------------------------------- #
    def set_controls(self, mode, rois, groups, between_rid, within_gid,
                     split, enabled) -> None:
        self._mode = mode
        self.between_btn.setChecked(mode == "between")
        self.within_btn.setChecked(mode == "within")
        self._suppress = True
        self.selector.clear()
        if mode == "between":
            self.selector_lbl.setText("ROI")
            for r in rois:
                tag = " (T)" if r.role == TARGET else \
                    " (R)" if (split and r.role == REFERENCE) else ""
                self.selector.addItem(r.label + tag, r.rid)
            self.selector.setCurrentIndex(_index_of(rois, between_rid))
        else:
            self.selector_lbl.setText("Group")
            for g in groups:
                self.selector.addItem(g.name, g.gid)
            self.selector.setCurrentIndex(_gindex_of(groups, within_gid))
        self._suppress = False
        self.export_btn.setEnabled(bool(enabled))

    # -- body (render a pre-computed result) --------------------------- #
    def show_result(self, result) -> None:
        _clear(self.body_lay)
        self.snr_lbl.setVisible(bool(result.snr_text))
        if result.snr_text:
            self.snr_lbl.setText(result.snr_text)
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
            grid.addWidget(chart, i // 3, i % 3)
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
        lbl.setMinimumHeight(120)
        self.body_lay.addWidget(lbl)


# small lookup helpers
def _index_of(rois, rid):
    for i, r in enumerate(rois):
        if r.rid == rid:
            return i
    return 0


def _gindex_of(groups, gid):
    for i, g in enumerate(groups):
        if g.gid == gid:
            return i
    return 0
