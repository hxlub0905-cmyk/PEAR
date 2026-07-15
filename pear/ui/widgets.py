"""Workspace widgets: the control rail (Groups / ROIs / Metrics), a
box-and-strip distribution chart, and the Analysis panel (hosted in its own
window).

No charting dependency — every plot is hand-painted with QPainter.
"""

from __future__ import annotations

from typing import Callable, List, Optional

import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
                               QWidget)

from pear.core.analysis import Group, heat_color, pixel_hist
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
    """Vertical box-and-strip plot, or an overlaid histogram (toggle)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = ""
        self._series: List[dict] = []
        self._ctype = "box"
        self._opts = {"points": True, "whiskers": True}
        self.setMinimumHeight(212)

    def set_data(self, title: str, series: List[dict], ctype: str = "box",
                 opts=None) -> None:
        self._title = title
        self._ctype = ctype
        self._opts = {"points": True, "whiskers": True, **(opts or {})}
        clean = []
        for s in series:
            v = np.asarray(s["values"], dtype=np.float64)
            v = v[np.isfinite(v)]
            if v.size:
                clean.append({"label": s["label"], "color": s["color"], "values": v})
        self._series = clean
        self.setMinimumHeight(212)
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
        if self._ctype == "hist":
            self._paint_hist(p)
        else:
            self._paint_box(p)
        p.end()

    def _range(self):
        allv = np.concatenate([s["values"] for s in self._series])
        lo, hi = float(allv.min()), float(allv.max())
        if hi - lo < 1e-9:
            lo -= 0.5
            hi += 0.5
        pad = (hi - lo) * 0.08
        return lo - pad, hi + pad

    def _ytitle(self, p: QPainter, text: str) -> None:
        p.save()
        p.setFont(theme.mono_font(8))
        p.setPen(QColor(theme.INK3))
        tw = p.fontMetrics().horizontalAdvance(text)
        p.translate(11, self.height() / 2.0)
        p.rotate(-90)
        p.drawText(int(-tw / 2), 0, text)
        p.restore()

    # -- vertical box + jittered strip -------------------------------- #
    def _paint_box(self, p: QPainter) -> None:
        lo, hi = self._range()
        top, left = 34, 54
        bottom = self.height() - 42
        right = self.width() - 12
        H = max(10, bottom - top)
        W = max(10, right - left)
        n = len(self._series)

        def Y(v):
            return bottom - (v - lo) / (hi - lo) * H

        p.setFont(theme.mono_font(8))
        for t in range(5):
            gy = top + H * t / 4.0
            p.setPen(QPen(QColor(theme.LINE2), 1))
            p.drawLine(left, int(gy), right, int(gy))
            p.setPen(QColor(theme.INK3))
            p.drawText(QRectF(16, gy - 6, left - 20, 12),
                       Qt.AlignRight | Qt.AlignVCenter, _fmt(hi - (hi - lo) * t / 4.0))
        self._ytitle(p, "value")

        lane = W / n
        for i, s in enumerate(self._series):
            v = s["values"]
            col = QColor(s["color"])
            cx = left + lane * (i + 0.5)
            bw = min(48.0, lane * 0.5)
            q25, med, q75 = (float(np.percentile(v, 25)),
                             float(np.median(v)), float(np.percentile(v, 75)))
            vmin, vmax = float(v.min()), float(v.max())
            if self._opts.get("whiskers", True):
                p.setPen(QPen(col, 1))
                p.drawLine(int(cx), int(Y(vmax)), int(cx), int(Y(vmin)))
                for yy in (vmin, vmax):
                    p.drawLine(int(cx - bw * 0.22), int(Y(yy)),
                               int(cx + bw * 0.22), int(Y(yy)))
            # IQR box
            box = QColor(col)
            box.setAlpha(48)
            p.setBrush(box)
            p.setPen(QPen(col, 1))
            p.drawRect(int(cx - bw / 2), int(Y(q75)),
                       int(bw), max(2, int(Y(q25) - Y(q75))))
            if self._opts.get("points", True):
                dot = QColor(col)
                dot.setAlpha(190)
                p.setPen(Qt.NoPen)
                p.setBrush(dot)
                for k, val in enumerate(v):
                    jitter = ((k % 7) / 6.0 - 0.5) * bw * 0.72
                    p.drawEllipse(int(cx + jitter) - 3, int(Y(val)) - 3, 6, 6)
            # median
            p.setPen(QPen(col, 2.4))
            p.drawLine(int(cx - bw / 2), int(Y(med)), int(cx + bw / 2), int(Y(med)))
            # mean value, placed just above the column's own data
            p.setPen(col)
            p.setFont(theme.mono_font(8, weight=700))
            my = max(top - 15, Y(vmax) - 16)
            p.drawText(QRectF(cx - lane / 2, my, lane, 13),
                       Qt.AlignHCenter | Qt.AlignVCenter, _fmt(float(v.mean())))
            # label below the column
            p.setPen(QColor(theme.INK2))
            p.setFont(theme.mono_font(8))
            lab = p.fontMetrics().elidedText(
                f"{s['label']} · n={v.size}", Qt.ElideRight, int(lane))
            p.drawText(QRectF(cx - lane / 2, bottom + 4, lane, 14),
                       Qt.AlignHCenter | Qt.AlignVCenter, lab)

    # -- overlaid histogram ------------------------------------------- #
    def _paint_hist(self, p: QPainter) -> None:
        lo, hi = self._range()
        allv = np.concatenate([s["values"] for s in self._series])
        nbins = int(np.clip(int(np.sqrt(allv.size)) + 1, 6, 22))
        edges = np.linspace(lo, hi, nbins + 1)
        counts = [np.histogram(s["values"], bins=edges)[0] for s in self._series]
        max_c = max(1, max(int(c.max()) for c in counts))
        top, left = 36, 48
        bottom = self.height() - 40
        right = self.width() - 12
        H = max(10, bottom - top)
        W = max(10, right - left)

        def X(v):
            return left + (v - lo) / (hi - lo) * W

        def Yc(c):
            return bottom - c / max_c * H

        p.setPen(QPen(QColor(theme.LINE2), 1))
        p.drawLine(left, bottom, right, bottom)
        p.setFont(theme.mono_font(8))
        p.setPen(QColor(theme.INK3))
        for t in range(5):                      # value axis (X)
            gx = left + W * t / 4.0
            p.drawText(QRectF(gx - 24, bottom + 2, 48, 12),
                       Qt.AlignHCenter, _fmt(lo + (hi - lo) * t / 4.0))
        for t in range(3):                      # count axis (Y)
            gy = bottom - H * t / 2.0
            p.drawText(QRectF(16, gy - 6, left - 20, 12),
                       Qt.AlignRight | Qt.AlignVCenter, str(int(round(max_c * t / 2.0))))
        self._ytitle(p, "count")
        p.setPen(QColor(theme.INK3))
        p.setFont(theme.mono_font(8))
        p.drawText(QRectF(left, bottom + 15, W, 12), Qt.AlignHCenter, "value")

        for s, c in zip(self._series, counts):  # overlaid bars
            col = QColor(s["color"])
            fill = QColor(col)
            fill.setAlpha(90)
            p.setBrush(fill)
            p.setPen(QPen(col, 1.2))
            for b in range(nbins):
                if c[b] == 0:
                    continue
                x0, x1 = X(edges[b]), X(edges[b + 1])
                y = Yc(int(c[b]))
                p.drawRect(int(x0) + 1, int(y),
                           max(1, int(x1 - x0) - 2), int(bottom - y))

        lx = left                               # legend
        p.setFont(theme.mono_font(8, weight=700))
        fm = p.fontMetrics()
        for s in self._series:
            col = QColor(s["color"])
            p.setBrush(col)
            p.setPen(Qt.NoPen)
            p.drawRect(int(lx), 25, 8, 8)
            p.setPen(QColor(theme.INK2))
            p.drawText(int(lx) + 12, 33, s["label"])
            lx += 12 + fm.horizontalAdvance(s["label"]) + 14


def _fmt(v: float) -> str:
    a = abs(v)
    if a >= 1000 or (0 < a < 0.01):
        return f"{v:.2e}"
    return f"{v:.3g}"


def _is_dark(hexcol) -> bool:
    c = QColor(hexcol)
    return (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) < 140


class _Bar(QWidget):
    """A slim horizontal bar showing a fraction in [0, 1] (attribute ranking)."""

    def __init__(self, frac):
        super().__init__()
        self._f = max(0.0, min(1.0, float(frac)))
        self.setMinimumHeight(14)
        self.setMinimumWidth(70)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(0, self.height() / 2 - 4, self.width() - 1, 8)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.LINE2))
        p.drawRoundedRect(r, 4, 4)
        if self._f > 0:
            fr = QRectF(r.left(), r.top(), r.width() * self._f, r.height())
            p.setBrush(QColor(theme.AMBER))
            p.drawRoundedRect(fr, 4, 4)
        p.end()


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
    heatmap_changed = Signal(bool)      # colour ROIs by the shown metric
    outliers_changed = Signal(bool)     # flag Tukey outliers of the shown metric

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
        # value-driven overlays for the shown metric (GLV only)
        ov = QHBoxLayout()
        ov.setSpacing(12)
        self.heatmap_chk = QCheckBox("heatmap")
        self.heatmap_chk.setToolTip("Colour each ROI by its shown metric value.")
        self.heatmap_chk.toggled.connect(self.heatmap_changed)
        self.outliers_chk = QCheckBox("flag outliers")
        self.outliers_chk.setToolTip("Mark ROIs outside Q1−1.5·IQR … Q3+1.5·IQR "
                                     "within their group.")
        self.outliers_chk.toggled.connect(self.outliers_changed)
        ov.addWidget(self.heatmap_chk)
        ov.addWidget(self.outliers_chk)
        ov.addStretch(1)
        root.addLayout(ov)
        self._rebuild()

    def selected(self) -> List[str]:
        return list(self._selected)

    def set_state(self, metrics, show, heatmap, outliers) -> None:
        """Restore the picker (used when opening a project)."""
        self._selected = list(metrics or [])
        self._show = show or ""
        for m in list(self._selected) + [self._show]:
            if (m and m.startswith("glv_q") and m not in GLV_STATS
                    and m not in self._custom):
                self._custom.append(m)
        self._rebuild()
        for chk, val in ((self.heatmap_chk, heatmap), (self.outliers_chk, outliers)):
            chk.blockSignals(True)
            chk.setChecked(bool(val))
            chk.blockSignals(False)

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
    roi_pick = Signal(int)                  # select an ROI from the list
    roi_set_target = Signal(int)            # tag an ROI as its group's SNR target
    roi_del = Signal(int)
    roi_hovered = Signal(int)                # rid under the cursor (-1 = none)
    metrics_changed = Signal(list)
    show_metric_changed = Signal(str)
    heatmap_changed = Signal(bool)
    outliers_changed = Signal(bool)
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
        # ROI list — capped height so a long list never buries the buttons
        self.roi_host = QVBoxLayout()
        self.roi_host.setSpacing(4)
        self.roi_host.setContentsMargins(0, 0, 0, 0)
        roi_list_host = QWidget()
        roi_list_host.setLayout(self.roi_host)
        self.roi_scroll = QScrollArea()
        self.roi_scroll.setWidgetResizable(True)
        self.roi_scroll.setFrameShape(QScrollArea.NoFrame)
        self.roi_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.roi_scroll.setWidget(roi_list_host)
        self.roi_scroll.setFixedHeight(6)        # grows with content up to a cap
        rlay.addWidget(self.roi_scroll)
        self.roi_hint = QLabel(
            "• Click → drop a size-W×H ROI · drag → custom size\n"
            "• Grid → two corners, set row×col, Add grid\n"
            "• Shift+drag → box-select · Del removes them\n"
            "• Double-click an ROI → pixel inspector\n"
            "• T → pick the group’s SNR target (rest are reference)")
        self.roi_hint.setObjectName("Hint")
        self.roi_hint.setWordWrap(True)
        rlay.addWidget(self.roi_hint)
        self.clear_btn = QPushButton("Clear group’s ROIs")
        self.clear_btn.clicked.connect(self._clear_active)
        rlay.addLayout(_button_row(self.clear_btn))
        root.addWidget(roi)

        # Metrics
        met = _card("Metrics", "GLV + SNR")
        self.metrics = MetricPicker()
        self.metrics.changed.connect(self.metrics_changed)
        self.metrics.show_changed.connect(self.show_metric_changed)
        self.metrics.heatmap_changed.connect(self.heatmap_changed)
        self.metrics.outliers_changed.connect(self.outliers_changed)
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

    def set_rois(self, active_group_rois, active_rid, target_rid=None,
                 selected_rids=None, outlier_rids=None) -> None:
        selected = set(selected_rids or [])
        outliers = set(outlier_rids or [])
        _clear(self.roi_host)
        self._roi_rows = {}
        for r in active_group_rois:
            row = self._roi_row(r, r.rid == active_rid, r.rid == target_rid,
                                r.rid in selected, r.rid in outliers)
            self._roi_rows[r.rid] = row
            self.roi_host.addWidget(row)
        # size the list to its content, capped so it never buries the buttons
        n = len(active_group_rois)
        self.roi_scroll.setFixedHeight(min(176, n * 30 + 6) if n else 6)

    def set_hovered_roi(self, rid: int) -> None:
        """Highlight the row for `rid` (canvas → list hover sync)."""
        for r, row in getattr(self, "_roi_rows", {}).items():
            row.set_hover(r == rid)

    def set_metric_state(self, metrics, show, heatmap, outliers) -> None:
        self.metrics.set_state(metrics, show, heatmap, outliers)

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

    def _roi_row(self, r, active: bool, is_target: bool,
                 selected: bool, outlier: bool = False) -> QWidget:
        row = _ItemRow(active, compact=True, boxed=False, selected=selected)
        row.add_name(r.label or f"ROI {r.rid}", None,
                     color=(theme.WARNING if outlier else None))
        if outlier:
            row.add_flag("!", theme.WARNING,
                         "Outlier of the shown metric within this group")
        row.add_target_toggle(is_target, lambda: self.roi_set_target.emit(r.rid))
        row.add_delete(lambda: self.roi_del.emit(r.rid))
        row.clicked = lambda: self.roi_pick.emit(r.rid)
        row.on_hover = lambda on, rid=r.rid: self.roi_hovered.emit(rid if on else -1)
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
    def __init__(self, active: bool, compact: bool = False,
                 boxed: bool = True, selected: bool = False):
        super().__init__()
        self.clicked: Optional[Callable] = None
        self.on_hover: Optional[Callable] = None
        self._boxed = boxed
        self._hl = active or selected
        self._apply_style(False)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(8, 3 if compact else 5, 8, 3 if compact else 5)
        self.lay.setSpacing(8)

    def _apply_style(self, hover: bool) -> None:
        if self._boxed:
            bg = theme.AMBER_SOFT if self._hl else theme.CARD
            border = theme.AMBER if self._hl else theme.LINE
            self.setStyleSheet(f"background:{bg}; border:1px solid {border};"
                               "border-radius:9px;")
        else:                                   # borderless (ROI rows)
            bg = theme.AMBER_SOFT if self._hl else (theme.LINE2 if hover
                                                    else "transparent")
            self.setStyleSheet(f"background:{bg}; border:none; border-radius:7px;")

    def set_hover(self, on: bool) -> None:
        if not self._hl:
            self._apply_style(on)

    def enterEvent(self, e):
        self.set_hover(True)
        if self.on_hover:
            self.on_hover(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.set_hover(False)
        if self.on_hover:
            self.on_hover(False)
        super().leaveEvent(e)

    def add_swatch(self, color, on_pick):
        self.lay.addWidget(_swatch(color, on_pick))

    def add_flag(self, text, color, tooltip=""):
        f = QLabel(text)
        f.setToolTip(tooltip)
        f.setStyleSheet(f"color:{color}; font-weight:800;")
        self.lay.addWidget(f)

    def add_target_toggle(self, is_target: bool, on_toggle):
        b = QPushButton("T")
        b.setCheckable(True)
        b.setChecked(is_target)
        b.setFixedSize(22, 20)
        b.setToolTip("SNR target (T). The group’s other ROIs are the "
                     "reference (R). Click to toggle.")
        if is_target:
            b.setStyleSheet(f"background:{theme.AMBER}; color:#FFFFFF; "
                            "border:none; border-radius:5px; font-weight:700;")
        else:
            b.setStyleSheet(f"background:transparent; color:{theme.INK3}; "
                            f"border:1px solid {theme.LINE}; border-radius:5px; "
                            "font-weight:700;")
        b.clicked.connect(lambda: on_toggle())
        self.lay.addWidget(b)

    def add_name(self, name, on_rename, color=None):
        if on_rename is None:
            lbl = QLabel(name)
            lbl.setStyleSheet("font-weight:600;" + (f"color:{color};" if color else ""))
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
        head.addSpacing(10)
        self.box_btn = QPushButton("◫ Box")
        self.hist_btn = QPushButton("▭ Histogram")
        for b, t in ((self.box_btn, "box"), (self.hist_btn, "hist")):
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.setToolTip("Switch every chart between box-and-strip and histogram.")
            b.clicked.connect(lambda _=False, tt=t: self._pick_ctype(tt))
            head.addWidget(b)
        self.box_btn.setChecked(True)
        head.addSpacing(8)
        self.points_chk = QCheckBox("points")
        self.whiskers_chk = QCheckBox("whiskers")
        for chk in (self.points_chk, self.whiskers_chk):
            chk.setChecked(True)
            chk.toggled.connect(self._on_chart_opts)
            head.addWidget(chk)
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
        self._chart_type = "box"
        self._last_result = None
        self._suppress = False

    def _pick_mode(self, mode: str) -> None:
        self._mode = mode
        self.between_btn.setChecked(mode == "between")
        self.within_btn.setChecked(mode == "within")
        self.mode_changed.emit(mode)

    def _pick_ctype(self, t: str) -> None:
        self._chart_type = t
        self.box_btn.setChecked(t == "box")
        self.hist_btn.setChecked(t == "hist")
        self.points_chk.setEnabled(t == "box")
        self.whiskers_chk.setEnabled(t == "box")
        if self._last_result is not None:
            self._render_body(self._last_result)   # re-render, no recompute

    def _on_chart_opts(self, _=False) -> None:
        if self._last_result is not None:
            self._render_body(self._last_result)

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
        self._last_result = result
        self._render_body(result)

    def _render_body(self, result) -> None:
        _clear(self.body_lay)
        self.sub.setText(result.subtitle)
        if result.empty:
            self._empty(result.empty)
            return
        charts = [(c.title, [{"label": s.label, "color": s.color,
                              "values": s.values} for s in c.series])
                  for c in result.charts]
        self._chart_grid(charts)
        if result.ranking:
            self._ranking_card(result.ranking)
        if result.heat:
            self._heatmap_card(result.heat)
        if result.table_rows:
            self._table(result.table_headers, result.table_rows)

    def _ranking_card(self, ranking) -> None:
        host = QFrame()
        host.setObjectName("Card")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(8)
        head = QLabel("Attribute ranking")
        head.setObjectName("SectionTitle")
        head.setFont(theme.display_font(13, weight=700))
        lay.addWidget(head)
        hint = QLabel("How well each metric separates the groups "
                      "(η² = share of variance explained; d = Cohen's d).")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for i, (label, eta, d) in enumerate(ranking):
            rk = QLabel(f"{i + 1}")
            rk.setFont(theme.mono_font(9, weight=700))
            rk.setStyleSheet(f"color:{theme.INK3};")
            nm = QLabel(label)
            nm.setStyleSheet("font-weight:600;")
            bar = _Bar(eta or 0.0)
            txt = ("—" if eta is None else f"η²={eta:.2f}"
                   + (f" · d={d:.2f}" if d is not None else ""))
            val = QLabel(txt)
            val.setFont(theme.mono_font(8))
            val.setStyleSheet(f"color:{theme.INK2};")
            grid.addWidget(rk, i, 0)
            grid.addWidget(nm, i, 1)
            grid.addWidget(bar, i, 2)
            grid.addWidget(val, i, 3)
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)
        self.body_lay.addWidget(host)

    def _heatmap_card(self, heat) -> None:
        host = QFrame()
        host.setObjectName("Card")
        lay = QVBoxLayout(host)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(8)
        head = QLabel("Group × metric heatmap")
        head.setObjectName("SectionTitle")
        head.setFont(theme.display_font(13, weight=700))
        lay.addWidget(head)
        hint = QLabel("Group mean per metric, colour-normalised down each column.")
        hint.setObjectName("Hint")
        lay.addWidget(hint)
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        metrics, groups = heat["metrics"], heat["groups"]
        colors, values = heat["colors"], heat["values"]
        for c, m in enumerate(metrics):
            h = QLabel(m)
            h.setFont(theme.mono_font(8))
            h.setStyleSheet(f"color:{theme.INK3}; font-weight:600;")
            h.setAlignment(Qt.AlignCenter)
            grid.addWidget(h, 0, c + 1)
        arr = np.asarray(values, dtype=np.float64)
        for c in range(len(metrics)):
            col = arr[:, c] if arr.size else np.array([])
            fin = col[np.isfinite(col)]
            lo, hi = (float(fin.min()), float(fin.max())) if fin.size else (0.0, 1.0)
            for r in range(len(groups)):
                if c == 0:
                    gl = QLabel("■ " + groups[r])
                    gl.setFont(theme.mono_font(8))
                    gl.setStyleSheet(f"color:{colors[r]}; font-weight:600;")
                    grid.addWidget(gl, r + 1, 0)
                v = float(arr[r, c])
                cell = QLabel("—" if not np.isfinite(v) else _fmt(v))
                cell.setAlignment(Qt.AlignCenter)
                cell.setFont(theme.mono_font(8, weight=700))
                cell.setMinimumWidth(64)
                if not np.isfinite(v):
                    cell.setStyleSheet(f"background:{theme.LINE2}; color:{theme.INK3};"
                                       "border-radius:4px; padding:5px;")
                else:
                    t = 0.5 if hi <= lo else (v - lo) / (hi - lo)
                    bg = heat_color(t)
                    fg = "#FFFFFF" if _is_dark(bg) else theme.INK
                    cell.setStyleSheet(f"background:{bg}; color:{fg};"
                                       "border-radius:4px; padding:5px;")
                grid.addWidget(cell, r + 1, c + 1)
        lay.addLayout(grid)
        self.body_lay.addWidget(host)

    def _chart_grid(self, charts) -> None:
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        opts = {"points": self.points_chk.isChecked(),
                "whiskers": self.whiskers_chk.isChecked()}
        for i, (title, series) in enumerate(charts):
            chart = DistributionChart()
            chart.set_data(title, series, self._chart_type, opts)
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


# --------------------------------------------------------------------------- #
# ROI pixel inspector (hosted in its own window)
# --------------------------------------------------------------------------- #
_HEAT_LUT = None


def _heat_lut():
    global _HEAT_LUT
    if _HEAT_LUT is None:
        lut = np.zeros((256, 3), dtype=np.uint8)
        for i in range(256):
            c = QColor(heat_color(i / 255.0))
            lut[i] = (c.red(), c.green(), c.blue())
        _HEAT_LUT = lut
    return _HEAT_LUT


class RoiInspector(QWidget):
    """Pixel-level view of one ROI: false-colour heatmap, grey-level histogram,
    and horizontal / vertical intensity profiles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._patch = None
        self._title = ""
        self.setMinimumSize(560, 420)

    def set_roi(self, patch, title: str) -> None:
        self._patch = None if patch is None else np.asarray(patch)
        self._title = title
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.WINDOW))
        p.setPen(QColor(theme.INK))
        p.setFont(theme.display_font(13, weight=700))
        p.drawText(16, 24, self._title or "ROI inspector")
        patch = self._patch
        if patch is None or patch.size == 0:
            p.setPen(QColor(theme.INK3))
            p.setFont(theme.mono_font(9))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Double-click an ROI on the image to inspect its pixels.")
            p.end()
            return
        pad, top = 16, 44
        heat_w = min(240.0, (self.width() - 3 * pad) * 0.44)
        heat = QRectF(pad, top, heat_w, heat_w * 0.82)
        hist = QRectF(heat.right() + pad, top,
                      self.width() - heat.right() - 2 * pad, heat.height())
        prof = QRectF(pad, heat.bottom() + 30, self.width() - 2 * pad,
                      self.height() - heat.bottom() - 30 - pad)
        self._paint_heat(p, patch, heat)
        self._paint_hist(p, patch, hist)
        self._paint_profiles(p, patch, prof)
        p.end()

    def _cap(self, p, rect, text, color=None):
        p.setPen(QColor(color or theme.INK3))
        p.setFont(theme.mono_font(8, weight=700))
        p.drawText(int(rect.left()), int(rect.top() - 6), text)

    def _paint_heat(self, p, patch, rect):
        self._cap(p, rect, "false-colour pixels")
        h, w = patch.shape
        rgb = np.ascontiguousarray(_heat_lut()[patch.astype(np.uint8)])
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        scaled = img.scaled(int(rect.width()), int(rect.height()),
                            Qt.KeepAspectRatio, Qt.FastTransformation)
        x = rect.left() + (rect.width() - scaled.width()) / 2
        y = rect.top() + (rect.height() - scaled.height()) / 2
        p.drawImage(int(x), int(y), scaled)
        p.setPen(QPen(QColor(theme.LINE), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(x, y, scaled.width(), scaled.height()))

    def _paint_hist(self, p, patch, rect):
        self._cap(p, rect, "grey-level histogram")
        counts, _edges = pixel_hist(patch, 32)
        mx = max(1, int(counts.max()))
        bw = rect.width() / len(counts)
        base = rect.bottom()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.AMBER))
        for i, c in enumerate(counts):
            bh = (c / mx) * (rect.height() - 4)
            p.drawRect(QRectF(rect.left() + i * bw + 1, base - bh,
                              max(1.0, bw - 2), bh))
        p.setPen(QPen(QColor(theme.LINE2), 1))
        p.drawLine(int(rect.left()), int(base), int(rect.right()), int(base))
        p.setPen(QColor(theme.INK3))
        p.setFont(theme.mono_font(8))
        p.drawText(QRectF(rect.left(), base + 2, rect.width(), 12), Qt.AlignLeft, "0")
        p.drawText(QRectF(rect.left(), base + 2, rect.width(), 12),
                   Qt.AlignRight, "255")
        m = float(patch.mean())
        mxx = rect.left() + (m / 255.0) * rect.width()
        p.setPen(QPen(QColor(theme.INFO), 1.5))
        p.drawLine(int(mxx), int(rect.top()), int(mxx), int(base))
        p.setPen(QColor(theme.INFO))
        p.setFont(theme.mono_font(8, weight=700))
        p.drawText(int(mxx) + 3, int(rect.top() + 10), f"μ={m:.0f}")

    def _paint_profiles(self, p, patch, rect):
        p.setFont(theme.mono_font(8, weight=700))
        fm = p.fontMetrics()
        p.setPen(QColor(theme.INK3))
        p.drawText(int(rect.left()), int(rect.top() - 6), "intensity profile")
        x = rect.left() + fm.horizontalAdvance("intensity profile") + 14
        p.setPen(QColor(theme.AMBER))
        p.drawText(int(x), int(rect.top() - 6), "— cols")
        x += fm.horizontalAdvance("— cols") + 10
        p.setPen(QColor(theme.INFO))
        p.drawText(int(x), int(rect.top() - 6), "— rows")
        col = patch.mean(axis=0).astype(float)
        row = patch.mean(axis=1).astype(float)
        vals = np.concatenate([col, row])
        lo, hi = float(vals.min()), float(vals.max())
        if hi - lo < 1e-6:
            lo -= 1.0
            hi += 1.0
        base, H = rect.bottom(), rect.height() - 4

        def Y(v):
            return base - (v - lo) / (hi - lo) * H

        p.setPen(QPen(QColor(theme.LINE2), 1))
        p.drawLine(int(rect.left()), int(base), int(rect.right()), int(base))

        def plot(series, color):
            if len(series) < 2:
                return
            pen = QPen(QColor(color), 1.8)
            pen.setCosmetic(True)
            p.setPen(pen)
            pts = [QPointF(rect.left() + i / (len(series) - 1) * rect.width(), Y(v))
                   for i, v in enumerate(series)]
            for a, b in zip(pts, pts[1:]):
                p.drawLine(a, b)

        plot(col, theme.AMBER)
        plot(row, theme.INFO)
        p.setPen(QColor(theme.INK3))
        p.setFont(theme.mono_font(8))
        p.drawText(int(rect.left()), int(rect.top() + 8), f"{hi:.0f}")
        p.drawText(int(rect.left()), int(base), f"{lo:.0f}")
