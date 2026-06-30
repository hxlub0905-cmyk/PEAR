"""Workspace widgets: Settings panel, Region list, Analysis panel, and a
hand-painted histogram. No charting dependency — every plot is QPainter.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFrame, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QScrollArea, QSizePolicy, QSpinBox,
                               QVBoxLayout, QWidget)

from pear.core.analysis import PeriodInfo, Region
from pear.core.attributes import ATTR_FORMULAS, ATTR_LABELS
from pear.ui import theme


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _card(title: Optional[str] = None, number: Optional[str] = None) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 16, 16, 16)
    lay.setSpacing(12)
    if title:
        if number:
            lay.addWidget(_eyebrow(f"{number} — {title}"))
        head = QLabel(title.upper())
        head.setObjectName("SectionTitle")
        head.setFont(theme.display_font(15))
        lay.addWidget(head)
    return frame


def _eyebrow(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Eyebrow")
    lbl.setFont(theme.eyebrow_font(9))
    return lbl


def _mono(text: str = "") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("Mono")
    lbl.setFont(theme.mono_font(10))
    return lbl


# --------------------------------------------------------------------------- #
# Golden-cell preview
# --------------------------------------------------------------------------- #
class GoldenPreview(QWidget):
    """Small canvas rendering the median-stacked golden cell."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self._pixmap: Optional[QPixmap] = None

    def set_cell(self, cell: Optional[np.ndarray]) -> None:
        if cell is None or cell.size == 0:
            self._pixmap = None
        else:
            arr = np.ascontiguousarray(cell.astype(np.uint8))
            h, w = arr.shape
            img = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
            self._pixmap = QPixmap.fromImage(img.copy())
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.STAGE))
        if self._pixmap is None:
            p.setPen(QColor(theme.FAINT))
            p.drawText(self.rect(), Qt.AlignCenter, "golden cell")
            p.end()
            return
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        iw, ih = self._pixmap.width(), self._pixmap.height()
        scale = min(self.width() / iw, self.height() / ih) * 0.9
        tw, th = iw * scale, ih * scale
        x = (self.width() - tw) / 2
        y = (self.height() - th) / 2
        p.drawPixmap(QRectF(x, y, tw, th), self._pixmap,
                     QRectF(self._pixmap.rect()))
        p.end()


# --------------------------------------------------------------------------- #
# Histogram (hand-painted)
# --------------------------------------------------------------------------- #
class Histogram(QWidget):
    """Distribution of one attribute's values across a region's cells."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self._values: np.ndarray = np.array([])
        self._target: Optional[np.ndarray] = None
        self._threshold: Optional[float] = None
        self._title = ""

    def set_values(self, values, title: str = "") -> None:
        self._values = np.asarray(values, dtype=np.float64)
        self._target = None
        self._threshold = None
        self._title = title
        self.update()

    def set_compare(self, ref_values, target_values, title: str = "",
                    threshold: Optional[float] = None) -> None:
        """Two overlaid populations: reference (black) and target (red)."""
        self._values = np.asarray(ref_values, dtype=np.float64)
        self._target = np.asarray(target_values, dtype=np.float64)
        self._threshold = threshold
        self._title = title
        self.update()

    def clear(self) -> None:
        self._values = np.array([])
        self._target = None
        self._threshold = None
        self._title = ""
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.PANEL))

        vals = self._values
        if vals.size == 0:
            p.setPen(QColor(theme.FAINT))
            p.drawText(self.rect(), Qt.AlignCenter, "no distribution")
            p.end()
            return

        margin_l, margin_r, margin_t, margin_b = 8, 8, 22, 22
        plot = QRectF(margin_l, margin_t,
                      self.width() - margin_l - margin_r,
                      self.height() - margin_t - margin_b)

        has_target = self._target is not None and self._target.size > 0
        allv = np.concatenate([vals, self._target]) if has_target else vals
        vmin, vmax = float(allv.min()), float(allv.max())
        if self._title:
            p.setPen(QColor(theme.MUTED))
            p.setFont(theme.mono_font(9))
            p.drawText(int(margin_l), 14, self._title)

        if vmax - vmin < 1e-12:
            p.fillRect(QRectF(plot.center().x() - 12, plot.top(),
                              24, plot.height()), QColor(theme.INK))
        else:
            nbins = min(24, max(6, int(np.sqrt(allv.size)) + 4))
            ref_counts, _ = np.histogram(vals, bins=nbins, range=(vmin, vmax))
            series = [(ref_counts, QColor(theme.INK))]
            if has_target:
                tgt_counts, _ = np.histogram(self._target, bins=nbins,
                                             range=(vmin, vmax))
                series.append((tgt_counts, QColor(theme.ACCENT)))
            cmax = max(int(c.max()) for c, _ in series) or 1
            bw = plot.width() / nbins
            p.setPen(Qt.NoPen)
            for counts, col in series:
                p.setBrush(col)
                for i, c in enumerate(counts):
                    if c == 0:
                        continue
                    bh = (c / cmax) * plot.height()
                    p.drawRect(QRectF(plot.left() + i * bw + 1,
                                      plot.bottom() - bh,
                                      max(1.0, bw - 2), bh))
            if self._threshold is not None and vmax > vmin:
                tx = plot.left() + (self._threshold - vmin) / (vmax - vmin) * plot.width()
                tx = float(np.clip(tx, plot.left(), plot.right()))
                tpen = QPen(QColor(theme.ACCENT), 1.5)
                tpen.setStyle(Qt.DashLine)
                p.setPen(tpen)
                p.drawLine(tx, plot.top(), tx, plot.bottom())

        # baseline + min/max labels (mono)
        p.setPen(QPen(QColor(theme.LINE), 1))
        p.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())
        p.setPen(QColor(theme.MUTED))
        p.setFont(theme.mono_font(9))
        p.drawText(int(plot.left()), self.height() - 6, _fmt(vmin))
        p.drawText(int(plot.right()) - 60, self.height() - 6, _fmt(vmax))
        p.end()


def _fmt(v: float) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1000 or a < 0.01:
        return f"{v:.2e}"
    return f"{v:.3g}"


# --------------------------------------------------------------------------- #
# Ranking list (label · max|z| · bar)
# --------------------------------------------------------------------------- #
class _RankRow(QFrame):
    clicked = Signal(str)

    def __init__(self, attr: str, label: str, value_text: str,
                 frac: float, parent=None):
        super().__init__(parent)
        self.attr = attr
        self._frac = max(0.0, min(1.0, frac))
        self._selected = False
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 8)
        self._name = QLabel(label)
        self._name.setMinimumWidth(120)
        self._name.setFont(theme.display_font(10, weight=700))
        self._val = _mono(value_text)
        self._val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self._name, 1)
        lay.addWidget(self._val, 0)

    def set_selected(self, sel: bool) -> None:
        self._selected = sel
        fg = theme.INVERT_FG if sel else theme.INK
        self._name.setStyleSheet(f"color: {fg};")
        self._val.setStyleSheet(f"color: {fg};")
        self.update()

    def mousePressEvent(self, _e) -> None:
        self.clicked.emit(self.attr)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        # Selected row inverts; others use the panel colour with a hairline.
        if self._selected:
            p.fillRect(self.rect(), QColor(theme.INVERT_BG))
        else:
            p.fillRect(self.rect(), QColor(theme.PANEL))
            p.setPen(QPen(QColor(theme.CHROME), 1))
            p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        # Accent magnitude meter along the bottom edge (functional signal).
        meter_w = self.width() * self._frac
        p.fillRect(QRectF(0, self.height() - 4, meter_w, 4),
                   QColor(theme.ACCENT))
        p.end()


class RankingList(QScrollArea):
    """Scrollable list of attribute rows; selecting one emits its id."""

    attr_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._host = QWidget()
        self._lay = QVBoxLayout(self._host)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(2)
        self._lay.addStretch(1)
        self.setWidget(self._host)
        self._rows: List[_RankRow] = []
        self._selected: Optional[str] = None

    def set_ranking(self, ranking, selected: Optional[str],
                    value_fn=None, fmt=None, tooltip_fn=None) -> None:
        """Populate rows. ``value_fn(score)`` gives the numeric magnitude
        (drives the meter); ``fmt(value)`` renders the right-hand text;
        ``tooltip_fn(score)`` an optional hover string."""
        value_fn = value_fn or (lambda s: s.max_abs_z)
        fmt = fmt or (lambda v: f"{v:.2f}σ")
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        self._selected = selected
        maxv = max((value_fn(s) for s in ranking), default=1.0) or 1.0
        for score in ranking:
            label = ATTR_LABELS.get(score.attr, score.attr)
            v = value_fn(score)
            row = _RankRow(score.attr, label, fmt(v),
                           (v / maxv) if maxv > 0 else 0.0)
            if tooltip_fn is not None:
                row.setToolTip(tooltip_fn(score))
            row.clicked.connect(self.attr_selected)
            row.set_selected(score.attr == selected)
            self._lay.insertWidget(self._lay.count() - 1, row)
            self._rows.append(row)

    def set_selected(self, attr: Optional[str]) -> None:
        self._selected = attr
        for row in self._rows:
            row.set_selected(row.attr == attr)

    def count(self) -> int:
        return len(self._rows)


# --------------------------------------------------------------------------- #
# Settings panel
# --------------------------------------------------------------------------- #
class SettingsPanel(QWidget):
    detect_requested = Signal()
    refine_requested = Signal()
    manual_changed = Signal(int, int, float)   # px, py, nm_per_px (0 = unset)
    region_add_requested = Signal()
    region_selected = Signal(int)
    region_deleted = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # --- Lattice card ------------------------------------------------ #
        lattice = _card("Lattice", number="01")
        llay = lattice.layout()
        self.period_lbl = _mono("period: —")
        self.axis_lbl = _mono("axis: —")
        self.align_pill = QLabel("—")
        self.align_pill.setObjectName("Mono")
        self.align_pill.setFont(theme.mono_font(10))
        llay.addWidget(self.period_lbl)
        llay.addWidget(self.axis_lbl)
        llay.addWidget(self.align_pill)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.detect_btn = QPushButton("Detect")
        self.detect_btn.setObjectName("Primary")
        self.refine_btn = QPushButton("Refine")
        for b in (self.detect_btn, self.refine_btn):
            b.setMinimumHeight(34)
        self.detect_btn.clicked.connect(self.detect_requested)
        self.refine_btn.clicked.connect(self.refine_requested)
        btns.addWidget(self.detect_btn, 1)
        btns.addWidget(self.refine_btn, 1)
        llay.addLayout(btns)

        llay.addWidget(_eyebrow("Golden cell"))
        self.golden = GoldenPreview()
        llay.addWidget(self.golden)

        # --- Manual (collapsible) --------------------------------------- #
        self.manual_toggle = QCheckBox("Set period / pixel size manually")
        llay.addWidget(self.manual_toggle)
        self.manual_box = QWidget()
        mlay = QVBoxLayout(self.manual_box)
        mlay.setContentsMargins(0, 6, 0, 0)
        mlay.setSpacing(8)
        self.px_spin = self._spin("px", 2, 100000)
        self.py_spin = self._spin("py", 2, 100000)
        self.nm_spin = self._dspin("nm/px", 0.0, 100000.0)
        for w in (self.px_spin[0], self.py_spin[0], self.nm_spin[0]):
            mlay.addWidget(w)
        apply_btn = QPushButton("Apply")
        apply_btn.setMinimumHeight(32)
        apply_btn.clicked.connect(self._emit_manual)
        mlay.addWidget(apply_btn)
        self.manual_box.setVisible(False)
        self.manual_toggle.toggled.connect(self.manual_box.setVisible)
        llay.addWidget(self.manual_box)
        root.addWidget(lattice)

        # --- Regions card ----------------------------------------------- #
        regions = _card("Regions", number="02")
        rlay = regions.layout()
        hint = QLabel("Add a region, then drag on the image to set its ROI.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        rlay.addWidget(hint)
        self.add_btn = QPushButton("+ Add region")
        self.add_btn.setObjectName("Primary")
        self.add_btn.setMinimumHeight(34)
        self.add_btn.clicked.connect(self.region_add_requested)
        rlay.addWidget(self.add_btn)
        self.region_list = QListWidget()
        self.region_list.setMinimumHeight(120)
        self.region_list.itemClicked.connect(self._on_region_clicked)
        rlay.addWidget(self.region_list)
        self.delete_btn = QPushButton("Delete selected region")
        self.delete_btn.setMinimumHeight(32)
        self.delete_btn.clicked.connect(self._on_delete)
        rlay.addWidget(self.delete_btn)
        root.addWidget(regions)
        root.addStretch(1)

    # widget builders ---------------------------------------------------- #
    def _spin(self, label, lo, hi):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        lbl = QLabel(label)
        lbl.setFont(theme.eyebrow_font(9))
        lbl.setMinimumWidth(56)
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setMinimumHeight(30)
        h.addWidget(lbl)
        h.addWidget(sp, 1)
        return row, sp

    def _dspin(self, label, lo, hi):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        lbl = QLabel(label)
        lbl.setFont(theme.eyebrow_font(9))
        lbl.setMinimumWidth(56)
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setDecimals(3)
        sp.setMinimumHeight(30)
        h.addWidget(lbl)
        h.addWidget(sp, 1)
        return row, sp

    # API ---------------------------------------------------------------- #
    def set_period(self, period: Optional[PeriodInfo]) -> None:
        if period is None:
            self.period_lbl.setText("period: —")
            self.axis_lbl.setText("axis: —")
            self.align_pill.setText("—")
            self.golden.set_cell(None)
            return
        self.period_lbl.setText(f"period: {period.px} x {period.py} px")
        self.axis_lbl.setText(f"axis: {period.axis_mode}  "
                              f"conf: {period.confidence:.0f}%")
        self.golden.set_cell(period.golden_cell)
        # sync manual spinboxes without re-emitting
        self.px_spin[1].blockSignals(True)
        self.py_spin[1].blockSignals(True)
        self.px_spin[1].setValue(period.px)
        self.py_spin[1].setValue(period.py)
        self.px_spin[1].blockSignals(False)
        self.py_spin[1].blockSignals(False)

    def set_alignment(self, lap_var: float) -> None:
        if lap_var > 80:
            text, col = "aligned", theme.OK
        elif lap_var > 25:
            text, col = "marginal", theme.FLAG
        else:
            text, col = "check alignment", theme.ACCENT
        self.align_pill.setText(f"alignment: {text}")
        self.align_pill.setStyleSheet(f"color: {col}; font-weight: 700;")

    def set_regions(self, regions: List[Region], active_rid: Optional[int]) -> None:
        self.region_list.blockSignals(True)
        self.region_list.clear()
        for r in regions:
            item = QListWidgetItem(f"  {r.name} · {len(r.instances)} cells")
            item.setData(Qt.UserRole, r.rid)
            item.setForeground(QColor(r.color))
            self.region_list.addItem(item)
            if r.rid == active_rid:
                self.region_list.setCurrentItem(item)
        self.region_list.blockSignals(False)

    def nm_per_px(self) -> float:
        return float(self.nm_spin[1].value())

    # handlers ----------------------------------------------------------- #
    def _emit_manual(self) -> None:
        self.manual_changed.emit(int(self.px_spin[1].value()),
                                 int(self.py_spin[1].value()),
                                 float(self.nm_spin[1].value()))

    def _on_region_clicked(self, item: QListWidgetItem) -> None:
        rid = item.data(Qt.UserRole)
        if rid is not None:
            self.region_selected.emit(int(rid))

    def _on_delete(self) -> None:
        item = self.region_list.currentItem()
        if item is not None:
            rid = item.data(Qt.UserRole)
            if rid is not None:
                self.region_deleted.emit(int(rid))


# --------------------------------------------------------------------------- #
# Analysis panel
# --------------------------------------------------------------------------- #
class AnalysisPanel(QWidget):
    attr_selected = Signal(str)
    export_requested = Signal()
    mode_changed = Signal(str)          # "unsupervised" | "labelled"
    tag_mode_toggled = Signal(bool)

    _CAP_UNSUP = ""
    _CAP_LABEL = "Tag target cells; the rest are reference."
    _EMPTY_UNSUP = "Add a region to rank attributes."
    _EMPTY_LABEL = "Tag target cells on the image."

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "unsupervised"
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        card = _card("Analysis", number="03")
        clay = card.layout()

        # mode selector
        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self.unsup_btn = QPushButton("Unsupervised")
        self.label_btn = QPushButton("Labelled compare")
        for b, m in ((self.unsup_btn, "unsupervised"), (self.label_btn, "labelled")):
            b.setCheckable(True)
            b.setMinimumHeight(32)
            b.clicked.connect(lambda _=False, mm=m: self._select_mode(mm))
            mode_row.addWidget(b, 1)
        self.unsup_btn.setChecked(True)
        clay.addLayout(mode_row)

        self.caption = QLabel(self._CAP_UNSUP)
        self.caption.setObjectName("Caption")
        self.caption.setWordWrap(True)
        self.caption.setVisible(bool(self._CAP_UNSUP))
        clay.addWidget(self.caption)

        # tag toggle (labelled mode only)
        self.tag_btn = QPushButton("Tag target cells")
        self.tag_btn.setCheckable(True)
        self.tag_btn.setMinimumHeight(32)
        self.tag_btn.toggled.connect(self.tag_mode_toggled)
        self.tag_btn.setVisible(False)
        clay.addWidget(self.tag_btn)

        self.empty_lbl = QLabel(self._EMPTY_UNSUP)
        self.empty_lbl.setObjectName("Hint")
        self.empty_lbl.setWordWrap(True)
        clay.addWidget(self.empty_lbl)

        clay.addWidget(_eyebrow("Ranking"))
        self.ranking = RankingList()
        self.ranking.setMinimumHeight(180)
        self.ranking.attr_selected.connect(self.attr_selected)
        clay.addWidget(self.ranking, 1)

        clay.addWidget(_eyebrow("Distribution"))
        self.hist = Histogram()
        clay.addWidget(self.hist)

        self.measured = QLabel("")
        self.measured.setObjectName("MeasuredLine")
        self.measured.setFont(theme.mono_font(9))
        self.measured.setWordWrap(True)
        clay.addWidget(self.measured)

        self.export_btn = QPushButton("Export CSV")
        self.export_btn.setObjectName("Primary")
        self.export_btn.clicked.connect(self.export_requested)
        self.export_btn.setEnabled(False)
        self.export_btn.setMinimumHeight(36)
        clay.addWidget(self.export_btn)

        root.addWidget(card)
        self._region: Optional[Region] = None
        self._set_results_visible(False)

    # mode -------------------------------------------------------------- #
    def set_mode(self, mode: str) -> None:
        """Set the display mode and sync the controls (no signal emitted)."""
        self._mode = mode
        self.unsup_btn.setChecked(mode == "unsupervised")
        self.label_btn.setChecked(mode == "labelled")
        labelled = mode == "labelled"
        cap = self._CAP_LABEL if labelled else self._CAP_UNSUP
        self.caption.setText(cap)
        self.caption.setVisible(bool(cap))
        self.tag_btn.setVisible(labelled)
        if not labelled and self.tag_btn.isChecked():
            self.tag_btn.setChecked(False)

    def _select_mode(self, mode: str) -> None:
        self.set_mode(mode)
        self.mode_changed.emit(mode)

    def mode(self) -> str:
        return self._mode

    def set_tag_active(self, on: bool) -> None:
        self.tag_btn.setChecked(on)

    def _set_results_visible(self, on: bool) -> None:
        self.empty_lbl.setVisible(not on)
        self.export_btn.setEnabled(on)

    # rendering --------------------------------------------------------- #
    def show_region(self, region: Optional[Region]) -> None:
        self._region = region
        if self._mode == "labelled":
            self._show_labelled(region)
        else:
            self._show_unsupervised(region)

    def _show_unsupervised(self, region: Optional[Region]) -> None:
        self.empty_lbl.setText(self._EMPTY_UNSUP)
        if region is None or not region.ranking:
            self.ranking.set_ranking([], None)
            self.hist.clear()
            self.measured.setText("")
            self._set_results_visible(False)
            return
        self._set_results_visible(True)
        self.ranking.set_ranking(
            region.ranking, region.sel_attr,
            value_fn=lambda s: s.max_abs_z,
            fmt=lambda v: f"{v:.2f}σ",
            tooltip_fn=lambda s: (
                f"{ATTR_LABELS.get(s.attr, s.attr)}\n"
                f"formula:  {ATTR_FORMULAS.get(s.attr, '—')}\n"
                f"max|z| = 0.6745·(x − median)/MAD\n"
                f"{s.n_outliers} cell(s) beyond 3.5σ"))
        self.update_attr(region, region.sel_attr)

    def _show_labelled(self, region: Optional[Region]) -> None:
        self.empty_lbl.setText(self._EMPTY_LABEL)
        if region is None or not region.sep_ranking:
            self.ranking.set_ranking([], None)
            self.hist.clear()
            if region is not None and region.target_idx:
                self.measured.setText("Tag at least one reference and one "
                                      "target cell to compare.")
            else:
                self.measured.setText("")
            self._set_results_visible(False)
            return
        self._set_results_visible(True)
        self.ranking.set_ranking(
            region.sep_ranking, region.sep_sel_attr,
            value_fn=lambda s: s.separation_score,
            fmt=lambda v: f"{v:.0f}/100",
            tooltip_fn=lambda s: (
                f"{ATTR_LABELS.get(s.attr, s.attr)}\n"
                f"formula:  {ATTR_FORMULAS.get(s.attr, '—')}\n"
                f"separation = clip((AUC−0.5)·200, 0, 100)\n"
                f"AUC {s.auc:.3f} · CNR {s.cnr:.2f} · d {s.cohens_d:.2f}"))
        self.update_attr(region, region.sep_sel_attr)

    def update_attr(self, region: Region, attr: Optional[str]) -> None:
        if region is None or attr is None:
            return
        self.ranking.set_selected(attr)
        if self._mode == "labelled":
            self._update_labelled_attr(region, attr)
        else:
            values = [rec.get(attr, 0.0) for rec in region.records]
            self.hist.set_values(values, ATTR_LABELS.get(attr, attr))
            score = next((s for s in region.ranking if s.attr == attr), None)
            if score is not None:
                self.measured.setText(
                    f"max|z| {score.max_abs_z:.1f}σ  ·  "
                    f"{score.n_outliers} cell(s) > 3.5σ")

    def _update_labelled_attr(self, region: Region, attr: str) -> None:
        score = next((s for s in region.sep_ranking if s.attr == attr), None)
        vals = np.array([rec.get(attr, 0.0) for rec in region.records],
                        dtype=np.float64)
        mask = np.zeros(len(region.records), dtype=bool)
        for i in region.target_idx:
            if 0 <= i < mask.size:
                mask[i] = True
        ref = vals[~mask]
        tgt = vals[mask]
        thr = score.threshold if score is not None else None
        self.hist.set_compare(ref, tgt, ATTR_LABELS.get(attr, attr), thr)
        if score is not None:
            catch = score.catch_rate * 100.0
            fa = score.false_alarm * 100.0
            self.measured.setText(
                f"sep {score.separation_score:.0f}/100  ·  AUC {score.auc:.3f}  ·  "
                f"thr {score.threshold:.4g} ({score.direction})  ·  "
                f"catch {catch:.0f}%  ·  FA {fa:.0f}%")
