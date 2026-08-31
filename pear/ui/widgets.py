"""Workspace widgets: the control rail (Groups / ROIs / Metrics), a
box-and-strip distribution chart, and the Analysis panel (hosted in its own
window).

No charting dependency — every plot is hand-painted with QPainter.
"""

from __future__ import annotations

from typing import Callable, List, Optional

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QImage, QPainter, QPen, QPixmap,
                           QRegion)
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMenu, QPushButton, QRadioButton, QScrollArea,
                               QSpinBox, QToolButton, QVBoxLayout, QWidget)

from pear.core.analysis import (Group, cell_edges, heat_color,
                               linear_trend, pixel_hist,
                               profile_by_position, uniformity)
from pear.core.attributes import GLV_STATS, metric_formula, metric_label
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


def _icon_button(kind: str, tooltip: str) -> QToolButton:
    """A small icon-only button, drawn rather than shipped."""
    b = QToolButton()
    b.setIcon(theme.glyph_icon(kind))
    b.setIconSize(QSize(18, 18))
    b.setFixedSize(28, 26)
    b.setAutoRaise(True)
    b.setToolTip(tooltip)
    return b


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


def save_widget_image(widget, path: str, scale: float = 3.0,
                      crop=None, background=None) -> Optional[str]:
    """Save a painted widget as a picture: SVG if the name says so, else PNG.

    Every view in PEAR is hand-painted with QPainter, so the same two lines
    serve all of them — SVG keeps real curves and text for print, PNG is
    rendered at ``scale`` × the on-screen size because a 1× screenshot of a
    chart is unreadable once a projector or a journal column has it. ``crop``
    (widget coordinates) trims to the part worth keeping.
    """
    if widget is None:
        return None
    area = QRect(crop) if crop is not None else widget.rect()
    w, h = max(1, area.width()), max(1, area.height())
    bg = QColor(background or theme.CARD)
    if str(path).lower().endswith(".svg"):
        try:
            from PySide6.QtSvg import QSvgGenerator
        except ImportError:
            return None
        gen = QSvgGenerator()
        gen.setFileName(path)
        gen.setSize(QSize(w, h))
        gen.setViewBox(area)              # the viewBox does the cropping
        painter = QPainter()
        if not painter.begin(gen):
            return None
        painter.fillRect(QRectF(area), bg)
        widget.render(painter, QPoint(0, 0), QRegion(area))
        painter.end()
        return path
    scale = float(np.clip(scale, 1.0, 8.0))
    full = QPixmap(int(widget.width() * scale), int(widget.height() * scale))
    full.setDevicePixelRatio(scale)
    full.fill(bg)
    widget.render(full)
    pm = full.copy(QRect(int(area.x() * scale), int(area.y() * scale),
                         int(w * scale), int(h * scale)))
    pm.setDevicePixelRatio(scale)
    return path if pm.save(path) else None


def _clear(layout) -> None:
    """Empty a layout, hiding each widget *now*.

    ``deleteLater`` only schedules the removal: until the event loop runs, a
    widget taken out of a layout keeps its parent and its last geometry, so a
    rebuilt list paints its stale rows over whatever sits under them (the
    Groups card's own title and Add button, for one). Hiding ends that on the
    spot.

    It has to be ``hide()`` and not ``setParent(None)``: these lists are
    rebuilt *from* the rows' own signals — click a ROI row and the refresh it
    triggers clears the list that row is in — and a widget reparented to None
    becomes a top-level window while its own event is still on the stack. That
    is a blank window flashing up per click, and then a crash.
    """
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w is not None:
            w.hide()
            w.deleteLater()


# --------------------------------------------------------------------------- #
# Distribution chart (box + jittered strip)
# --------------------------------------------------------------------------- #
class DistributionChart(QWidget):
    """Vertical box-and-strip plot, an overlaid histogram, a position
    profile (the metric against where each ROI sits on the image), or a
    spatial heat map of the ROIs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = ""
        self._series: List[dict] = []
        self._ctype = "box"
        self._opts = {"points": True, "whiskers": True, "cells": True}
        self._axis = "x"
        self._trend = True
        self._xlabel = ""
        self._style: dict = {}
        self.setMinimumHeight(212)
        # a distribution reads as a figure at roughly 4:3; letterboxed across
        # a wide window it flattens and the page looks lopsided
        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def set_data(self, title: str, series: List[dict], ctype: str = "box",
                 opts=None, axis: str = "x", trend: bool = True,
                 xlabel: str = "", style=None) -> None:
        self._title = title
        self._xlabel = xlabel or title
        self._style = dict(style or {})
        self._ctype = ctype
        self._opts = {"points": True, "whiskers": True, "cells": True,
                      **(opts or {})}
        self._axis = "y" if str(axis).lower() == "y" else "x"
        self._trend = bool(trend)
        clean = []
        for s in series:
            v = np.asarray(s["values"], dtype=np.float64)
            keep = np.isfinite(v)
            if not keep.any():
                continue
            item = {"label": s["label"], "color": s["color"], "values": v[keep]}
            # positions are index-aligned with values, so they take the same mask
            for key in ("pos_x", "pos_y"):
                arr = s.get(key)
                if arr is None:
                    continue
                arr = np.asarray(arr, dtype=np.float64)
                if arr.size == v.size:
                    item[key] = arr[keep]
            clean.append(item)
        self._series = clean
        if ctype == "position":
            self.setMinimumHeight(300)
        elif ctype == "map":
            self.setMinimumHeight(320)
        else:
            self.setMinimumHeight(212)
        self.update()

    def sizeHint(self) -> QSize:
        # without one, a layout column with no stretch falls back to the
        # minimum and the figure comes out as narrow as it is allowed to be
        w = 720
        return QSize(w, self.heightForWidth(w))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        """Every chart keeps a shape you can read.

        A distribution wants roughly 4:3. A profile or a map runs the width of
        the column, and at a fixed height that turns into a letterbox: the
        values are squeezed into a band a few pixels tall, where a real tilt
        and a flat line look the same.
        """
        if self._ctype in ("box", "hist"):
            h = min(w * 0.78, 560)
        else:
            h = min(w * 0.58, 640)
        return int(max(self.minimumHeight(), h))

    # -- style overrides (title, axis names, tick counts, ranges) ------ #
    def _st(self, key: str, default=None):
        v = self._style.get(key)
        return default if v is None or v == "" else v

    def _font(self, delta: int = 0, weight=None):
        """Tick-value text: the size the user asked for (8 pt by default),
        bold if they asked for that too."""
        size = self._st("font_pt", 8)
        try:
            size = float(size)
        except (TypeError, ValueError):
            size = 8.0
        size = float(np.clip(size + delta, 5.0, 24.0))
        if weight is None and self._st("tick_bold", False):
            weight = 700
        return (theme.mono_font(size, weight=weight) if weight
                else theme.mono_font(size))

    def _label_font(self):
        """Axis-name text — its own size and weight, so the names can carry
        the figure while the tick values stay small (or the other way round)."""
        size = self._st("label_pt", self._st("font_pt", 8))
        try:
            size = float(size)
        except (TypeError, ValueError):
            size = 8.0
        size = float(np.clip(size, 5.0, 24.0))
        bold = self._st("label_bold", True)
        return theme.mono_font(size, weight=700 if bold else 500)

    def _axis_ink(self) -> "QColor":
        """Tick and axis-name ink. Dark by default — a chart that ends up in a
        report is read on paper and on a projector, where a light grey tick
        label is simply not there."""
        return QColor(self._st("axis_ink", theme.INK))

    def _mark_color(self, key: str, series_color) -> "QColor":
        return QColor(self._st(key, series_color))

    def _nticks(self, key: str, default: int) -> int:
        try:
            return int(np.clip(int(self._st(key, default)), 2, 12))
        except (TypeError, ValueError):
            return default

    def title_text(self) -> str:
        """What the chart is called — the override, or the metric it plots."""
        return str(self._st("title", self._title))

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.CARD))
        p.setPen(QColor(theme.INK))
        p.setFont(theme.display_font(12, weight=700))
        # centred over the plot, where a figure caption goes
        p.drawText(QRectF(8, 5, self.width() - 16, 19),
                   Qt.AlignHCenter | Qt.AlignVCenter, self.title_text())
        if not self._series:
            p.setPen(self._axis_ink())
            p.setFont(self._font(1))
            p.drawText(self.rect(), Qt.AlignCenter, "no data")
            p.end()
            return
        if self._ctype == "hist":
            self._paint_hist(p)
        elif self._ctype == "position":
            self._paint_position(p)
        elif self._ctype == "map":
            self._paint_map(p)
        else:
            self._paint_box(p)
        p.end()

    # -- shared figure furniture -------------------------------------- #
    def _frame(self, p: QPainter, left, top, right, bottom,
               xticks=(), yticks=()) -> None:
        """A boxed plot area with inward tick marks — the plain conventions a
        figure in a report follows, so the chart reads the same on a slide as
        it does on screen."""
        p.setPen(QPen(self._axis_ink(), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(left, top, right - left, bottom - top))
        for gx in xticks:
            p.drawLine(QPointF(gx, bottom), QPointF(gx, bottom - 4))
            p.drawLine(QPointF(gx, top), QPointF(gx, top + 4))
        for gy in yticks:
            p.drawLine(QPointF(left, gy), QPointF(left + 4, gy))
            p.drawLine(QPointF(right, gy), QPointF(right - 4, gy))

    def _marker(self, p: QPainter, x, y, color, rad=None) -> None:
        """One observation. Open — white centre, coloured rim — so a scatter
        never merges into the lines drawn in the same colour beside it."""
        if rad is None:
            try:
                rad = float(np.clip(float(self._st("point_size", 3.2)),
                                    0.5, 20.0))
            except (TypeError, ValueError):
                rad = 3.2
        col = self._mark_color("point_color", color)
        p.setBrush(QColor(255, 255, 255, 230))
        p.setPen(QPen(col, max(0.6, rad * 0.4)))
        p.drawEllipse(QPointF(x, y), rad, rad)

    def _line_w(self, default: float) -> float:
        try:
            return float(np.clip(float(self._st("line_width", default)),
                                 0.3, 12.0))
        except (TypeError, ValueError):
            return default

    def _locked(self, lo, hi, kmin: str, kmax: str):
        """The range the user pinned, or the one the data suggested."""
        vmin, vmax = self._st(kmin), self._st(kmax)
        try:
            if vmin is not None and vmax is not None and float(vmax) > float(vmin):
                return float(vmin), float(vmax)
        except (TypeError, ValueError):
            pass
        return lo, hi

    def _range(self):
        vmin, vmax = self._st("vmin"), self._st("vmax")
        if vmin is not None and vmax is not None and float(vmax) > float(vmin):
            return float(vmin), float(vmax)     # locked: comparable between runs
        allv = np.concatenate([s["values"] for s in self._series])
        lo, hi = float(allv.min()), float(allv.max())
        if hi - lo < 1e-9:
            lo -= 0.5
            hi += 0.5
        pad = (hi - lo) * 0.08
        return lo - pad, hi + pad

    def _ytitle(self, p: QPainter, text: str) -> None:
        p.save()
        p.setFont(self._label_font())
        p.setPen(self._axis_ink())
        tw = p.fontMetrics().horizontalAdvance(text)
        p.translate(11, self.height() / 2.0)
        p.rotate(-90)
        p.drawText(int(-tw / 2), 0, text)
        p.restore()

    # -- vertical box + jittered strip -------------------------------- #
    def _paint_box(self, p: QPainter) -> None:
        """Box-and-strip per group, on a shared value axis by default.

        A shared axis is the comparison — it is what makes one group sitting
        above another visible. But a group whose spread is a hundredth of the
        gap between groups collapses to a line on it, and its shape is exactly
        what a within-group reader is after; ``own_scale`` gives every lane
        its own range, printed above and below the lane so nothing is implied
        about how the lanes relate.
        """
        own = bool(self._opts.get("own_scale", False))
        glo, ghi = self._range()
        top, left = 34, 54
        bottom = self.height() - (54 if own else 42)
        right = self.width() - 12
        H = max(10, bottom - top)
        W = max(10, right - left)
        n = len(self._series)

        def lane_range(v):
            lo, hi = float(v.min()), float(v.max())
            if hi - lo < 1e-9:
                lo, hi = lo - 0.5, hi + 0.5
            pad = (hi - lo) * 0.08
            return lo - pad, hi + pad

        p.setFont(self._font())
        ny = self._nticks("yticks", 5)
        gridys = [top + H * t / (ny - 1.0) for t in range(ny)]
        for t, gy in enumerate(gridys):
            p.setPen(QPen(QColor(theme.LINE2), 1))
            p.drawLine(left, int(gy), right, int(gy))
            if own:                     # one label per lane instead, below
                continue
            p.setPen(self._axis_ink())
            p.drawText(QRectF(16, gy - 6, left - 20, 12),
                       Qt.AlignRight | Qt.AlignVCenter,
                       _fmt(ghi - (ghi - glo) * t / (ny - 1.0)))
        self._frame(p, left, top, right, bottom, yticks=() if own else gridys)
        self._ytitle(p, self._st("ylabel", "value · own scale per group"
                                 if own else "value"))
        xlab = self._st("xlabel", "")
        if xlab:
            p.setPen(self._axis_ink())
            p.setFont(self._label_font())
            p.drawText(QRectF(left, self.height() - 16, W, 13),
                       Qt.AlignHCenter, str(xlab))

        lane = W / n
        for i, s in enumerate(self._series):
            v = s["values"]
            col = QColor(s["color"])
            cx = left + lane * (i + 0.5)
            bw = min(48.0, lane * 0.5)
            lo, hi = lane_range(v) if own else (glo, ghi)

            def Y(val, lo=lo, hi=hi):
                return bottom - (val - lo) / (hi - lo) * H

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
                for k, val in enumerate(v):
                    jitter = ((k % 7) / 6.0 - 0.5) * bw * 0.72
                    self._marker(p, cx + jitter, Y(val), col)
            # median
            p.setPen(QPen(self._mark_color("line_color", col),
                          self._line_w(2.2)))
            p.drawLine(int(cx - bw / 2), int(Y(med)), int(cx + bw / 2), int(Y(med)))
            # mean value, placed just above the column's own data
            p.setPen(col)
            p.setFont(self._font(weight=700))
            my = max(top - 15, Y(vmax) - 16)
            p.drawText(QRectF(cx - lane / 2, my, lane, 13),
                       Qt.AlignHCenter | Qt.AlignVCenter, _fmt(float(v.mean())))
            # label below the column
            p.setPen(self._axis_ink())
            p.setFont(self._font())
            lab = p.fontMetrics().elidedText(str(s["label"]), Qt.ElideRight,
                                             int(lane))
            p.drawText(QRectF(cx - lane / 2, bottom + 4, lane, 14),
                       Qt.AlignHCenter | Qt.AlignVCenter, lab)
            if not own:
                continue
            # this lane's own range, so a stretched lane still says what it
            # spans and is never mistaken for the one beside it
            span = hi - lo
            p.setPen(self._axis_ink())
            p.drawText(QRectF(cx - lane / 2, bottom + 18, lane, 13),
                       Qt.AlignHCenter | Qt.AlignVCenter,
                       f"{_fmt_span(vmin, span)} … {_fmt_span(vmax, span)}")
        if self._legend_on():
            self._legend(p, left, top, right,
                         [(s["label"], s["color"], f"n={s['values'].size}")
                          for s in self._series])

    # -- position profile (metric vs. where the ROI sits) -------------- #
    def _paint_position(self, p: QPainter) -> None:
        """Metric on Y against ROI centre position on X.

        A uniform field reads as a flat line; a tilt or a bow is the
        non-uniformity. Every ROI is a dot, ROIs sharing a position collapse
        into the profile line, and the dashed line is the least-squares fit.
        """
        key = "pos_y" if self._axis == "y" else "pos_x"
        series = [s for s in self._series
                  if s.get(key) is not None and s[key].size]
        if not series:
            p.setPen(self._axis_ink())
            p.setFont(self._font(1))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "no per-ROI position for this metric")
            return

        allv = np.concatenate([s["values"] for s in series])
        allx = np.concatenate([s[key] for s in series])
        lo, hi = float(allv.min()), float(allv.max())
        if hi - lo < 1e-9:
            lo, hi = lo - 0.5, hi + 0.5
        pad = (hi - lo) * 0.12
        lo, hi = lo - pad, hi + pad
        lo, hi = self._locked(lo, hi, "vmin", "vmax")
        xlo, xhi = float(allx.min()), float(allx.max())
        if xhi - xlo < 1e-9:
            xlo, xhi = xlo - 1.0, xhi + 1.0
        xpad = (xhi - xlo) * 0.04
        xlo, xhi = xlo - xpad, xhi + xpad
        # the position axis locks too: two runs of the same field only line up
        # if both are drawn across the same span of the image
        xlo, xhi = self._locked(xlo, xhi, "xmin", "xmax")

        # value labels can need many decimals on a near-flat profile, so size
        # the gutter from the widest one rather than a fixed guess
        p.setFont(self._font())
        fm = p.fontMetrics()
        ny = self._nticks("yticks", 5)
        ticks = [_fmt_span(hi - (hi - lo) * t / (ny - 1.0), hi - lo)
                 for t in range(ny)]
        top = 34
        left = int(np.clip(max(fm.horizontalAdvance(t) for t in ticks) + 26,
                           46, 120))
        bottom = max(top + 40, self.height() - 40)
        right = self.width() - 12
        H = max(10, bottom - top)
        W = max(10, right - left)

        def X(v):
            return left + (v - xlo) / (xhi - xlo) * W

        def Y(v):
            return bottom - (v - lo) / (hi - lo) * H

        # grid + value axis
        gridys = [top + H * t / (ny - 1.0) for t in range(ny)]
        for gy, lab in zip(gridys, ticks):
            p.setPen(QPen(QColor(theme.LINE2), 1))
            p.drawLine(left, int(gy), right, int(gy))
            p.setPen(self._axis_ink())
            p.drawText(QRectF(18, gy - 6, left - 24, 12),
                       Qt.AlignRight | Qt.AlignVCenter, lab)
        self._ytitle(p, self._st("ylabel", "value"))

        # position axis
        nx = self._nticks("xticks", 5)
        xs = [left + W * t / (nx - 1.0) for t in range(nx)]
        self._frame(p, left, top, right, bottom, xticks=xs, yticks=gridys)
        p.setPen(self._axis_ink())
        for t, gx in enumerate(xs):
            p.drawText(QRectF(gx - 28, bottom + 2, 56, 12), Qt.AlignHCenter,
                       f"{xlo + (xhi - xlo) * t / (nx - 1.0):.0f}")
        p.setFont(self._label_font())
        p.drawText(QRectF(left, bottom + 16, W, 14), Qt.AlignHCenter,
                   str(self._st("xlabel",
                                f"ROI centre {self._axis.upper()} (px)")))

        rows = []
        for s in series:
            col = QColor(s["color"])
            px_, v = s[key], s["values"]

            # Drawn back to front: the two reference lines first, then the
            # data on top of them. The other way round the amber trend hides
            # the profile it is meant to be compared against.
            fit = linear_trend(px_, v)

            # group mean — where a perfectly flat profile would sit
            mean = float(v.mean())
            ref = QColor(col)
            ref.setAlpha(70)
            pen = QPen(ref, 1)
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawLine(left, int(Y(mean)), right, int(Y(mean)))

            # least-squares tilt — the brand accent, so it never reads as data
            if self._trend and fit is not None:
                slope, inter = fit
                pen = QPen(QColor(theme.AMBER), self._line_w(2.2) * 0.75)
                pen.setStyle(Qt.DashLine)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                y0 = min(hi, max(lo, slope * xlo + inter))
                y1 = min(hi, max(lo, slope * xhi + inter))
                p.drawLine(QPointF(X(xlo), Y(y0)), QPointF(X(xhi), Y(y1)))

            # every ROI as an open marker — the profile line runs through
            # them in the same hue, and filled dots would fuse with it
            for a, b in zip(px_, v):
                self._marker(p, X(a), Y(b), col)

            # profile line through the mean of the ROIs at each position.
            # Deliberately a darker shade than the dots: same colour at the
            # same weight and the line disappears into its own scatter.
            cx, cy = profile_by_position(px_, v)
            if cx.size >= 2:
                p.setPen(QPen(self._mark_color("line_color", col.darker(190)),
                              self._line_w(2.2)))
                p.setBrush(Qt.NoBrush)
                pts = [QPointF(X(a), Y(b)) for a, b in zip(cx, cy)]
                for a, b in zip(pts, pts[1:]):
                    p.drawLine(a, b)

            # the flatness numbers ride in the legend, not under the axis:
            # below the plot they crowd the axis name and get clipped
            u = uniformity(v)
            txt = (f"n={u['n']}"
                   f" · mean {_fmt_span(u['mean'], u['range'] or 1.0)}"
                   f" · range {_fmt(u['range'])} ({_pct(u['range_pct'])})"
                   f" · CV {_pct(u['cv_pct'])}")
            if fit is not None:
                txt += f" · slope {fit[0] * 100:+.3g}/100px"
            rows.append((s["label"], s["color"], txt))
        if self._legend_on():
            self._legend(p, left, top, right, rows,
                         keys=self._line_key_rows())

    def _line_key_rows(self):
        """What each line in the profile means — three of them look alike."""
        return [("profile — mean at each position",
                 QColor(theme.INK2), Qt.SolidLine),
                ("trend — least squares fit",
                 QColor(theme.AMBER), Qt.DashLine),
                ("group mean — where flat would sit",
                 QColor(theme.INK3), Qt.DashLine)]

    # -- spatial heat map (ROI layout coloured by the metric) ---------- #
    def _paint_map(self, p: QPainter) -> None:
        """Every ROI drawn where it sits, coloured by its metric value.

        As **cells** (the default) each ROI spans the gap to its neighbour, so
        the field reads as one surface and a cell can be compared against the
        one beside it; as **dots** the ROIs stay separate marks. Y runs
        downward to match the image. A uniform field is one flat colour; a
        gradient or a hot corner is the non-uniformity.
        """
        series = [s for s in self._series
                  if s.get("pos_x") is not None and s.get("pos_y") is not None
                  and s["pos_x"].size]
        if not series:
            p.setPen(self._axis_ink())
            p.setFont(self._font(1))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "no per-ROI position for this metric")
            return

        allv = np.concatenate([s["values"] for s in series])
        allx = np.concatenate([s["pos_x"] for s in series])
        ally = np.concatenate([s["pos_y"] for s in series])
        lo, hi = float(allv.min()), float(allv.max())
        hmin, hmax = self._st("heat_vmin"), self._st("heat_vmax")
        if hmin is not None and hmax is not None and float(hmax) > float(hmin):
            lo, hi = float(hmin), float(hmax)   # locked: comparable between runs
        flat = (hi - lo) < 1e-9
        vspan = 1.0 if flat else hi - lo

        cells = bool(self._opts.get("cells", True))
        equal = bool(self._opts.get("equal_cells", True))
        show_val = bool(self._opts.get("map_values", False))
        xc, xe = cell_edges(allx)
        yc, ye = cell_edges(ally)

        def median_step(e):
            return float(np.median(np.diff(e))) if e.size > 2 else 0.0

        cw, ch = median_step(xe), median_step(ye)
        if cells:
            # a single column (or row) has no pitch of its own — it borrows
            # the other axis's, so the cells stay square instead of hairlines
            if xc.size == 1 and ch > 0:
                xe, cw = np.asarray([xc[0] - ch / 2, xc[0] + ch / 2]), ch
            if yc.size == 1 and cw > 0:
                ye, ch = np.asarray([yc[0] - cw / 2, yc[0] + cw / 2]), cw
            xlo, xhi = float(xe[0]), float(xe[-1])   # cells fill the plot box
            ylo, yhi = float(ye[0]), float(ye[-1])
            xlo, xhi = self._locked(xlo, xhi, "xmin", "xmax")
            ylo, yhi = self._locked(ylo, yhi, "ymin", "ymax")
            if xhi - xlo < 1e-9:
                xlo, xhi = xlo - 1.0, xhi + 1.0
            if yhi - ylo < 1e-9:
                ylo, yhi = ylo - 1.0, yhi + 1.0
        else:
            def span(a):
                v0, v1 = float(a.min()), float(a.max())
                pad = max((v1 - v0) * 0.08, 0.5)
                v0, v1 = v0 - pad, v1 + pad
                if v1 - v0 < 1e-9:
                    v0, v1 = v0 - 1.0, v1 + 1.0
                return v0, v1

            xlo, xhi = self._locked(*span(allx), "xmin", "xmax")
            ylo, yhi = self._locked(*span(ally), "ymin", "ymax")

        top, left = 34, 52
        cbar_w = 54
        bottom = max(top + 40, self.height() - 46)
        right = self.width() - 12 - cbar_w
        H = max(10, bottom - top)
        W = max(10, right - left)
        sx = W / (xhi - xlo)
        sy = H / (yhi - ylo)

        def X(v):
            return left + (v - xlo) * sx

        def Y(v):                       # image Y grows downward
            return top + (v - ylo) * sy

        p.setPen(QPen(QColor(theme.LINE2), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(int(left), int(top), int(W), int(H))
        p.setFont(self._font())
        p.setPen(self._axis_ink())
        nx, ny = self._nticks("xticks", 3), self._nticks("yticks", 3)
        grid_mode = cells and equal and xc.size > 0 and yc.size > 0
        if grid_mode:
            # every column is one slot wide, so the tick belongs to the slot,
            # not to a linear axis — label the ones that fit
            for t in range(min(nx, int(xc.size))):
                i = int(round(t * (xc.size - 1) / max(1, min(nx, xc.size) - 1)))
                gx = left + W * (i + 0.5) / xc.size
                p.drawText(QRectF(gx - 28, bottom + 2, 56, 12), Qt.AlignHCenter,
                           f"{xc[i]:.0f}")
            for t in range(min(ny, int(yc.size))):
                j = int(round(t * (yc.size - 1) / max(1, min(ny, yc.size) - 1)))
                gy = top + H * (j + 0.5) / yc.size
                p.drawText(QRectF(6, gy - 6, left - 10, 12),
                           Qt.AlignRight | Qt.AlignVCenter, f"{yc[j]:.0f}")
        else:
            for t in range(nx):         # X ticks
                gx = left + W * t / (nx - 1.0)
                p.drawText(QRectF(gx - 28, bottom + 2, 56, 12), Qt.AlignHCenter,
                           f"{xlo + (xhi - xlo) * t / (nx - 1.0):.0f}")
            for t in range(ny):         # Y ticks (top = small y, like the image)
                gy = top + H * t / (ny - 1.0)
                p.drawText(QRectF(6, gy - 6, left - 10, 12),
                           Qt.AlignRight | Qt.AlignVCenter,
                           f"{ylo + (yhi - ylo) * t / (ny - 1.0):.0f}")
        p.drawText(QRectF(left, bottom + 15, W, 12), Qt.AlignHCenter,
                   str(self._st("xlabel", "ROI centre X (px)")))
        self._ytitle(p, self._st("ylabel", "ROI centre Y (px)"))

        ring = len(series) > 1        # only needed to tell groups apart
        if cells and equal and xc.size and yc.size:
            self._paint_map_grid(p, series, xc, yc, left, top, W, H,
                                 lo, hi, flat, vspan, show_val, ring)
        elif cells:
            # One filled cell per ROI, spanning to the boundary it shares with
            # its neighbour: the difference against the cell next door is the
            # point of the view, and touching blocks show it where dots cannot.
            p.setFont(self._font(weight=700))
            fm = p.fontMetrics()
            for s in series:
                edge = QColor(s["color"])
                for cx, cy, v in zip(s["pos_x"], s["pos_y"], s["values"]):
                    t = 0.5 if flat else (float(v) - lo) / (hi - lo)
                    col = heat_color(t)
                    i = int(np.abs(xc - cx).argmin()) if xe.size > 2 else 0
                    j = int(np.abs(yc - cy).argmin()) if ye.size > 2 else 0
                    x0, x1 = X(xe[i]), X(xe[i + 1])
                    y0, y1 = Y(ye[j]), Y(ye[j + 1])
                    r = QRectF(x0, y0, x1 - x0, y1 - y0)
                    p.setBrush(QColor(col))
                    # a hairline edge separates touching cells without
                    # opening a gap between them
                    p.setPen(QPen(edge, 1.2) if ring
                             else QPen(QColor(0, 0, 0, 45), 0.8))
                    p.drawRect(r)
                    if not show_val:
                        continue
                    txt = _fmt_span(float(v), vspan)
                    if (fm.horizontalAdvance(txt) + 6 <= r.width()
                            and fm.height() <= r.height()):
                        p.setPen(QColor("#FFFFFF") if _is_dark(col)
                                 else QColor(theme.INK))
                        p.drawText(r, Qt.AlignCenter, txt)
            p.setPen(QPen(QColor(theme.LINE2), 1))   # cells cover the frame
            p.setBrush(Qt.NoBrush)
            p.drawRect(int(left), int(top), int(W), int(H))
        else:
            # A scatter: one dot per ROI. Size follows the tightest neighbour
            # spacing only so that dense layouts stay readable.
            rad = 7.0
            if allx.size > 1:
                for arr, sc in ((allx, sx), (ally, sy)):
                    u = np.unique(np.round(arr, 0))
                    if u.size > 1:
                        rad = min(rad, float(np.min(np.diff(u))) * sc * 0.34)
            rad = float(np.clip(rad, 2.5, 9.0))
            for s in series:
                edge = QColor(s["color"])
                for cx, cy, v in zip(s["pos_x"], s["pos_y"], s["values"]):
                    t = 0.5 if flat else (float(v) - lo) / (hi - lo)
                    p.setBrush(QColor(heat_color(t)))
                    p.setPen(QPen(edge, 1.2) if ring
                             else QPen(QColor(theme.LINE), 0.8))
                    p.drawEllipse(QPointF(X(cx), Y(cy)), rad, rad)

        # colour bar
        bx = right + 16
        bw, bh = 12, H
        for i in range(int(bh)):
            t = 1.0 - i / max(1.0, bh - 1)
            p.setPen(QColor(heat_color(t)))
            p.drawLine(int(bx), int(top + i), int(bx + bw), int(top + i))
        p.setPen(QPen(QColor(theme.LINE2), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(int(bx), int(top), bw, int(bh))
        p.setPen(self._axis_ink())
        p.setFont(self._font())
        p.drawText(QRectF(bx + bw + 2, top - 2, cbar_w - bw - 4, 12),
                   Qt.AlignLeft, _fmt_span(hi, hi - lo))
        p.drawText(QRectF(bx + bw + 2, top + bh - 10, cbar_w - bw - 4, 12),
                   Qt.AlignLeft, _fmt_span(lo, hi - lo))
        if hmin is not None and hmax is not None:
            p.drawText(QRectF(bx - 2, top - 15, cbar_w, 12), Qt.AlignLeft,
                       "locked")

        u = uniformity(allv)
        txt = (f"n={u['n']} · mean {_fmt_span(u['mean'], u['range'] or 1.0)}"
               f" · range {_fmt(u['range'])} ({_pct(u['range_pct'])})"
               f" · CV {_pct(u['cv_pct'])}")
        if cells and cw > 0 and ch > 0:
            txt += f" · cell {cw:.0f}×{ch:.0f} px"
        if cells and equal:
            txt += " · equal cells"
        p.setPen(self._axis_ink())
        p.setFont(self._font())
        p.drawText(QRectF(left, bottom + 28, W + cbar_w, 13),
                   Qt.AlignLeft | Qt.AlignVCenter, txt)

    def _paint_map_grid(self, p: QPainter, series, xc, yc, left, top, W, H,
                        lo, hi, flat, vspan, show_val, ring) -> None:
        """Every cell the same size, one slot per row and column.

        Cell edges taken literally sit midway between neighbours, so an uneven
        pitch — or one missing ROI — gives neighbouring cells visibly
        different areas, and area is not something this chart is measuring.
        On the lattice every ROI gets an identical tile, which is what a die
        map looks like and what makes two cells comparable at a glance; the
        axis still labels each slot with the position it stands for.
        """
        cw, ch = W / float(xc.size), H / float(yc.size)
        p.setFont(self._font(weight=700))
        fm = p.fontMetrics()
        for s in series:
            edge = QColor(s["color"])
            for px_, py_, v in zip(s["pos_x"], s["pos_y"], s["values"]):
                i = int(np.abs(xc - px_).argmin())
                j = int(np.abs(yc - py_).argmin())
                t = 0.5 if flat else (float(v) - lo) / (hi - lo)
                col = heat_color(t)
                r = QRectF(left + cw * i, top + ch * j, cw, ch)
                p.setBrush(QColor(col))
                p.setPen(QPen(edge, 1.2) if ring
                         else QPen(QColor(0, 0, 0, 45), 0.8))
                p.drawRect(r)
                if not show_val:
                    continue
                txt = _fmt_span(float(v), vspan)
                if (fm.horizontalAdvance(txt) + 6 <= r.width()
                        and fm.height() <= r.height()):
                    p.setPen(QColor("#FFFFFF") if _is_dark(col)
                             else QColor(theme.INK))
                    p.drawText(r, Qt.AlignCenter, txt)
        p.setPen(QPen(QColor(theme.LINE2), 1))       # cells cover the frame
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(left, top, W, H))

    # -- overlaid histogram ------------------------------------------- #
    def _paint_hist(self, p: QPainter) -> None:
        """Overlaid histogram, drawn as a figure rather than a sketch.

        This is the chart that ends up in a report, so it is built like a
        published one: a framed plot box, both axes labelled and ticked, a
        legend carrying each group's n, and counts or per-group percent (which
        is what makes groups of different size comparable at all).
        """
        pct = bool(self._opts.get("hist_pct", False))
        lo, hi = self._range()
        allv = np.concatenate([s["values"] for s in self._series])
        nbins = int(self._opts.get("bins", 0) or 0)
        if nbins <= 0:                          # auto: √n, bounded
            nbins = int(np.clip(int(np.sqrt(allv.size)) + 1, 6, 22))
        nbins = int(np.clip(nbins, 2, 80))
        edges = np.linspace(lo, hi, nbins + 1)
        counts = [np.histogram(s["values"], bins=edges)[0] for s in self._series]
        if pct:
            bars = [c / max(1.0, float(c.sum())) * 100.0 for c in counts]
        else:
            bars = [c.astype(np.float64) for c in counts]
        peak = max([float(b.max()) for b in bars] + [0.0])
        ny = self._nticks("yticks", 5)
        step = _nice_step(peak if peak > 0 else 1.0, ny - 1)
        if not pct:
            step = max(1.0, round(step))        # counts are whole numbers
        ymax = max(step, float(np.ceil(peak / step) * step))
        # ticks land on the step, not on ymax/4 — 0 · 10 · 20 · 30 rather than
        # 0 · 7.5 · 15 · 22.5 rounded to "8" and "22" in the label
        yticks = [step * k for k in range(int(round(ymax / step)) + 1)]

        p.setFont(self._font())
        fm = p.fontMetrics()
        ylabs = [(f"{v:.0f}%" if pct else f"{v:.0f}") for v in yticks]
        left = int(np.clip(max(fm.horizontalAdvance(t) for t in ylabs) + 26,
                           44, 120))
        top = 38
        bottom = self.height() - 44
        right = self.width() - 14
        H = max(10, bottom - top)
        W = max(10, right - left)

        def X(v):
            return left + (v - lo) / (hi - lo) * W

        def Y(c):
            return bottom - c / ymax * H

        # grid + value axis
        for v, lab in zip(yticks, ylabs):
            gy = Y(v)
            p.setPen(QPen(QColor(theme.LINE2), 1))
            p.drawLine(left, int(gy), right, int(gy))
            p.setPen(self._axis_ink())
            p.drawText(QRectF(8, gy - 6, left - 12, 12),
                       Qt.AlignRight | Qt.AlignVCenter, lab)
        # bars, back to front so a thin group is never buried
        order = sorted(range(len(self._series)),
                       key=lambda i: -float(bars[i].sum()))
        for i in order:
            s, b = self._series[i], bars[i]
            col = QColor(s["color"])
            fill = QColor(col)
            fill.setAlpha(70 if len(self._series) > 1 else 120)
            p.setBrush(fill)
            p.setPen(QPen(self._mark_color("line_color", col),
                          self._line_w(1.4)))
            for k in range(nbins):
                if b[k] <= 0:
                    continue
                x0, x1 = X(edges[k]), X(edges[k + 1])
                y = Y(float(b[k]))
                p.drawRect(QRectF(x0, y, max(1.0, x1 - x0), bottom - y))
        span = hi - lo
        nx = self._nticks("xticks", 5)
        xs = [left + W * t / (nx - 1.0) for t in range(nx)]
        self._frame(p, left, top, right, bottom, xticks=xs,
                    yticks=[Y(v) for v in yticks])
        p.setFont(self._font())
        p.setPen(self._axis_ink())
        for t, gx in enumerate(xs):
            p.drawText(QRectF(gx - 30, bottom + 5, 60, 12), Qt.AlignHCenter,
                       _fmt_span(lo + span * t / (nx - 1.0), span))
        p.setPen(self._axis_ink())
        p.setFont(self._label_font())
        p.drawText(QRectF(left, bottom + 19, W, 13), Qt.AlignHCenter,
                   str(self._st("xlabel", self._xlabel or "value")))
        self._ytitle(p, self._st("ylabel", "share of group (%)" if pct
                                 else "count (ROIs)"))
        if self._legend_on():
            self._legend(p, left, top, right,
                         [(s["label"], s["color"], f"n={s['values'].size}")
                          for s in self._series])

    def _legend_on(self) -> bool:
        """Legends are opt-in: on a figure with two series it is furniture,
        and it sits on top of the data."""
        return bool(self._opts.get("legend", False))

    def _legend(self, p: QPainter, left, top, right, rows, keys=()) -> None:
        """Keyed legend, boxed at the top right of the plot area.

        ``rows`` are ``(label, colour, extra)`` swatch entries; ``keys`` are
        ``(text, colour, pen style)`` line samples, drawn above them.
        """
        if not rows and not keys:
            return
        p.setFont(self._font(weight=700))
        fm = p.fontMetrics()
        texts = [f"{lab}  {extra}" if extra else lab for lab, _c, extra in rows]
        widest = max([fm.horizontalAdvance(t) for t in texts] +
                     [fm.horizontalAdvance(t) + 16 for t, _c, _s in keys])
        line_h = fm.height() + 3
        wid = widest + 26
        hgt = 6 + line_h * (len(rows) + len(keys))
        x = max(left + 4, right - wid - 4)
        box = QRectF(x, top + 4, wid, hgt)
        bg = QColor(theme.CARD)
        bg.setAlpha(225)
        p.setPen(QPen(QColor(theme.LINE), 1))
        p.setBrush(bg)
        p.drawRect(box)
        y = box.top() + 3
        for text, color, style in keys:
            pen = QPen(QColor(color), 1.8)
            pen.setStyle(style)
            p.setPen(pen)
            p.drawLine(QPointF(box.left() + 6, y + line_h / 2),
                       QPointF(box.left() + 24, y + line_h / 2))
            p.setPen(self._axis_ink())
            p.drawText(QRectF(box.left() + 30, y, wid - 34, line_h),
                       Qt.AlignLeft | Qt.AlignVCenter, text)
            y += line_h
        for (lab, color, _extra), txt in zip(rows, texts):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawRect(QRectF(box.left() + 6, y + line_h / 2 - 4, 9, 8))
            p.setPen(self._axis_ink())
            p.drawText(QRectF(box.left() + 20, y, wid - 24, line_h),
                       Qt.AlignLeft | Qt.AlignVCenter, txt)
            y += line_h


def _nice_step(span: float, target: int = 4) -> float:
    """A round tick step (1 / 2 / 2.5 / 5 × 10ⁿ) near ``span / target``."""
    if not np.isfinite(span) or span <= 0:
        return 1.0
    raw = span / max(1, target)
    mag = 10.0 ** np.floor(np.log10(raw))
    for m in (1.0, 2.0, 2.5, 5.0):
        if raw <= m * mag:
            return float(m * mag)
    return float(10.0 * mag)


def _fmt(v: float) -> str:
    a = abs(v)
    if a >= 1000 or (0 < a < 0.01):
        return f"{v:.2e}"
    return f"{v:.3g}"


def _fmt_span(v: float, span: float) -> str:
    """Label with enough decimals to tell neighbouring ticks apart.

    A near-flat profile spans a fraction of a grey level, where ``_fmt``'s
    3 significant digits would print every tick the same.
    """
    step = float(span) / 4.0
    if not np.isfinite(step) or step <= 0:
        return _fmt(v)
    if abs(v) >= 1e5 or (0 < abs(v) < 1e-3):
        return f"{v:.2e}"
    dec = int(np.clip(np.ceil(-np.log10(step)) + 1, 0, 6))
    return f"{v:.{dec}f}"


def _pct(v: float) -> str:
    return f"{v:.2f}%" if abs(v) < 1.0 else f"{v:.1f}%"


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
    """Which metrics the analysis reports. The overlay lives on StageBar."""

    changed = Signal(list)
    ids_changed = Signal(list)          # every metric id on offer (incl. Q*n)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected: List[str] = ["glv_mean", "glv_median"]
        self._custom: List[str] = []
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
        self._rebuild()

    def selected(self) -> List[str]:
        return list(self._selected)

    def ids(self) -> List[str]:
        return list(GLV_STATS.keys()) + self._custom

    def set_state(self, metrics, extra_ids=()) -> None:
        """Restore the picker (used when opening a project).

        ``extra_ids`` re-registers custom quantiles that the project used only
        for the overlay, so they stay on offer after reopening.
        """
        self._selected = list(metrics or [])
        for m in list(self._selected) + list(extra_ids):
            if (m and m.startswith("glv_q") and m not in GLV_STATS
                    and m not in self._custom):
                self._custom.append(m)
        self._rebuild()

    def _add_custom(self) -> None:
        mid = f"glv_q{int(self.qn_spin.value())}"
        if mid not in self._custom and mid not in GLV_STATS:
            self._custom.append(mid)
        if mid not in self._selected:
            self._selected.append(mid)
        self._rebuild()
        self.changed.emit(list(self._selected))

    def _ids(self) -> List[str]:
        return self.ids()

    def _rebuild(self) -> None:
        _clear(self._chip_lay)
        for i, mid in enumerate(self._ids()):
            chip = _Chip(mid, mid in self._selected)
            chip.clicked.connect(lambda _=False, m=mid: self._toggle(m))
            self._chip_lay.addWidget(chip, i // 3, i % 3)
        self.ids_changed.emit(self.ids())

    def _toggle(self, mid: str) -> None:
        if mid in self._selected:
            self._selected.remove(mid)
        else:
            self._selected.append(mid)
        self.changed.emit(list(self._selected))


# --------------------------------------------------------------------------- #
# Stage bar — the ROI overlay controls, sitting over the image they act on
# --------------------------------------------------------------------------- #
class StageBar(QWidget):
    """One strip above the image: which metric to overlay, and how to read it.

    These controls belong next to the image, not at the bottom of a long rail
    — every one of them changes what the picture looks like, and each is a
    separate reading of the same metric, so they switch one at a time.
    """

    show_changed = Signal(str)          # metric id drawn on the ROIs ("" = none)
    values_changed = Signal(bool)
    heatmap_changed = Signal(bool)
    cells_changed = Signal(bool)        # spread the heat over the ROI's cell
    outliers_changed = Signal(bool)
    heat_alpha_changed = Signal(int)    # percent
    heat_range_changed = Signal(object)  # (vmin, vmax) or None for auto
    export_image_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StageBar")
        self._show = ""
        self._heat_range = None         # locked colour range, or None for auto
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 7, 12, 7)
        lay.setSpacing(10)
        lbl = QLabel("show on ROIs")
        lbl.setObjectName("Hint")
        self.show_combo = QComboBox()
        self.show_combo.setMinimumWidth(150)
        self.show_combo.setMinimumHeight(26)
        self.show_combo.setToolTip("The metric every overlay below reads.")
        self.show_combo.currentIndexChanged.connect(self._on_show)
        lay.addWidget(lbl)
        lay.addWidget(self.show_combo)
        lay.addSpacing(6)
        self.values_chk = QCheckBox("values")
        self.values_chk.setChecked(True)
        self.values_chk.setToolTip(
            "Print the metric on each ROI (where the box is big enough; the "
            "hovered ROI always shows its own). Off with heatmap on = colour "
            "only.")
        self.values_chk.toggled.connect(self.values_changed)
        self.heatmap_chk = QCheckBox("heat boxes")
        self.heatmap_chk.setToolTip(
            "Fill each ROI box with its value's colour.")
        self.heatmap_chk.toggled.connect(self._on_heatmap)
        self.cells_chk = QCheckBox("heat field")
        self.cells_chk.setToolTip(
            "Spread each ROI's colour over the patch of image it speaks for "
            "(midway to its neighbours), so a gradient across the field reads "
            "as one surface. The measured box stays outlined on top. Works on "
            "its own — boxes and field are two ways to paint the same values.")
        self.cells_chk.toggled.connect(self._on_cells)
        self.outliers_chk = QCheckBox("outliers")
        self.outliers_chk.setToolTip("Mark ROIs outside Q1−1.5·IQR … Q3+1.5·IQR "
                                     "within their group.")
        self.outliers_chk.toggled.connect(self.outliers_changed)
        for chk in (self.values_chk, self.heatmap_chk, self.cells_chk,
                    self.outliers_chk):
            lay.addWidget(chk)
        op = QLabel("opacity")
        op.setObjectName("Hint")
        self.alpha_spin = QSpinBox()
        self.alpha_spin.setRange(10, 100)
        self.alpha_spin.setSingleStep(5)
        self.alpha_spin.setValue(70)
        self.alpha_spin.setSuffix(" %")
        self.alpha_spin.setFixedWidth(72)
        self.alpha_spin.setMinimumHeight(26)
        self.alpha_spin.setToolTip(
            "Opacity of the heat fill — lower it to read the image underneath.")
        self.alpha_spin.valueChanged.connect(self.heat_alpha_changed)
        lay.addWidget(op)
        lay.addWidget(self.alpha_spin)
        lay.addStretch(1)
        self.scale_btn = QPushButton("scale…")
        self.scale_btn.setFixedHeight(26)
        self.scale_btn.setToolTip(
            "Lock the heat colours to a fixed range, so the same colour means "
            "the same grey level on every image you open.")
        self.scale_btn.clicked.connect(self.edit_heat_range)
        lay.addWidget(self.scale_btn)
        self.image_btn = QPushButton("Export image")
        self.image_btn.setFixedHeight(26)
        self.image_btn.setToolTip(
            "Save the annotated field as a picture — the image at its own "
            "resolution with the overlays on top, not a screenshot of the "
            "stage.")
        self.image_btn.clicked.connect(self.export_image_requested)
        lay.addWidget(self.image_btn)
        self.set_metrics(list(GLV_STATS.keys()))
        self._gate()

    # -- state -------------------------------------------------------- #
    def set_metrics(self, ids) -> None:
        """Rebuild the metric list, keeping the current pick if it survives."""
        self.show_combo.blockSignals(True)
        self.show_combo.clear()
        self.show_combo.addItem("— none —", "")
        for mid in ids:
            self.show_combo.addItem(metric_label(mid), mid)
        idx = self.show_combo.findData(self._show)
        self.show_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._show = self.show_combo.currentData() or ""
        self.show_combo.blockSignals(False)

    def set_state(self, show, values, heatmap, cells, outliers, alpha) -> None:
        self._show = show or ""
        self.show_combo.blockSignals(True)
        idx = self.show_combo.findData(self._show)
        self.show_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.show_combo.blockSignals(False)
        for chk, val in ((self.values_chk, values), (self.heatmap_chk, heatmap),
                         (self.cells_chk, cells), (self.outliers_chk, outliers)):
            chk.blockSignals(True)
            chk.setChecked(bool(val))
            chk.blockSignals(False)
        self.alpha_spin.blockSignals(True)
        self.alpha_spin.setValue(int(alpha))
        self.alpha_spin.blockSignals(False)
        self._gate()

    def _gate(self) -> None:
        # Either mode paints the values; the opacity and the colour scale
        # belong to whichever is on. Neither gates the other — ticking the
        # field alone used to leave the image untouched, which read as a
        # broken checkbox.
        on = self.heatmap_chk.isChecked() or self.cells_chk.isChecked()
        for w in (self.alpha_spin, self.scale_btn):
            w.setEnabled(on)

    def set_heat_range(self, rng) -> None:
        """Restore the locked colour range (or None for auto)."""
        self._heat_range = tuple(rng) if rng else None
        self._label_scale()

    def heat_range(self):
        return self._heat_range

    def _label_scale(self) -> None:
        r = self._heat_range
        self.scale_btn.setText("scale…" if not r
                               else f"{r[0]:.4g} – {r[1]:.4g}")

    def edit_heat_range(self) -> None:
        style = ({} if not self._heat_range
                 else {"heat_vmin": self._heat_range[0],
                       "heat_vmax": self._heat_range[1]})
        dlg = QDialog(self)
        dlg.setWindowTitle("Heat colour scale")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        row, auto, lo, hi = _num_row("grey level", style,
                                     "heat_vmin", "heat_vmax")
        lay.addLayout(row)
        hint = QLabel("With auto, the colours span this image's own min and "
                      "max — the same colour means a different value on the "
                      "next image. Lock the range to compare across images.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            return
        rng = (None if auto.isChecked() or hi.value() <= lo.value()
               else (lo.value(), hi.value()))
        self.set_heat_range(rng)
        self.heat_range_changed.emit(rng)

    def _on_heatmap(self, on: bool) -> None:
        self._gate()
        self.heatmap_changed.emit(bool(on))

    def _on_cells(self, on: bool) -> None:
        self._gate()
        self.cells_changed.emit(bool(on))

    def _on_show(self, _i: int) -> None:
        self._show = self.show_combo.currentData() or ""
        self.show_changed.emit(self._show)


# --------------------------------------------------------------------------- #
# Chart settings — what a figure is called and how its axes are scaled
# --------------------------------------------------------------------------- #
def _num_row(label: str, style: dict, kmin: str, kmax: str, unit: str = ""):
    """An "auto / from … to …" range row. Returns (layout, auto, lo, hi)."""
    row = QHBoxLayout()
    row.setSpacing(6)
    lab = QLabel(label)
    lab.setObjectName("Hint")
    lab.setMinimumWidth(96)
    auto = QCheckBox("auto")
    lo, hi = QDoubleSpinBox(), QDoubleSpinBox()
    for sp in (lo, hi):
        sp.setRange(-1e9, 1e9)
        sp.setDecimals(3)
        sp.setMinimumWidth(96)
        if unit:
            sp.setSuffix(unit)
    have = style.get(kmin) is not None and style.get(kmax) is not None
    auto.setChecked(not have)
    if have:
        lo.setValue(float(style[kmin]))
        hi.setValue(float(style[kmax]))
    for sp in (lo, hi):
        sp.setEnabled(have)
    auto.toggled.connect(lambda on: [sp.setEnabled(not on) for sp in (lo, hi)])
    row.addWidget(lab)
    row.addWidget(auto)
    row.addWidget(QLabel("from"))
    row.addWidget(lo)
    row.addWidget(QLabel("to"))
    row.addWidget(hi)
    row.addStretch(1)
    return row, auto, lo, hi


class RoiSizeDialog(QDialog):
    """How big the boxes are, on the way in or out.

    The interchange list says where each ROI goes; how big it is can come
    from three places — the file itself, the rail's size fields, or a size
    typed here for the whole set. Rather than guess, ask, and let the export
    leave ``w`` / ``h`` out entirely for a tool that does not expect them.
    """

    def __init__(self, parent, mode: str, w: int, h: int, count: int = 0):
        super().__init__(parent)
        importing = mode == "import"
        self.setWindowTitle("Import ROIs" if importing else "Export ROIs")
        self.setMinimumWidth(380)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)
        if count:
            head = QLabel(f"{count} ROIs")
            head.setObjectName("SectionTitle")
            head.setFont(theme.display_font(12, weight=700))
            root.addWidget(head)

        self.include_chk = QCheckBox("write w / h for every box")
        self.include_chk.setChecked(True)
        self.include_chk.setToolTip(
            "Off: only colour, x, y and target are written — the shape a tool "
            "that has its own box size expects.")
        if not importing:
            root.addWidget(self.include_chk)

        self.own_radio = QRadioButton(
            "keep each box's own size" if not importing
            else "take the size from the file (or the size fields, if it has "
                 "none)")
        self.own_radio.setChecked(True)
        self.custom_radio = QRadioButton("use this size for every box")
        root.addWidget(self.own_radio)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.custom_radio)
        self.w_spin, self.h_spin = QSpinBox(), QSpinBox()
        for sp, val in ((self.w_spin, w), (self.h_spin, h)):
            sp.setRange(1, 4000)
            sp.setValue(int(val))
            sp.setMinimumHeight(28)
            sp.setFixedWidth(80)
            sp.setEnabled(False)
        row.addWidget(self.w_spin)
        row.addWidget(QLabel("×"))
        row.addWidget(self.h_spin)
        row.addStretch(1)
        root.addLayout(row)
        self.custom_radio.toggled.connect(
            lambda on: [sp.setEnabled(on) for sp in (self.w_spin, self.h_spin)])
        if not importing:
            self.include_chk.toggled.connect(self._gate)
            self._gate(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _gate(self, on: bool) -> None:
        for w in (self.own_radio, self.custom_radio):
            w.setEnabled(on)
        for sp in (self.w_spin, self.h_spin):
            sp.setEnabled(on and self.custom_radio.isChecked())

    def options(self) -> dict:
        """``{"size": (w, h) or None, "include_size": bool}``."""
        size = ((int(self.w_spin.value()), int(self.h_spin.value()))
                if self.custom_radio.isChecked() else None)
        return {"size": size, "include_size": self.include_chk.isChecked()}


class ChartSettingsDialog(QDialog):
    """Rename the figures and set their axes by hand.

    Auto scaling is right while you are looking; it is wrong the moment you
    put two runs side by side, because each picks its own range. Everything
    here is an override — leave a field blank or on *auto* and the chart goes
    back to deciding for itself.
    """

    def __init__(self, parent, chart_titles: List[str], style: dict):
        super().__init__(parent)
        self.setWindowTitle("Chart settings")
        self.setMinimumWidth(460)
        style = dict(style or {})
        titles = dict(style.get("titles") or {})
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        head = QLabel("Titles")
        head.setObjectName("SectionTitle")
        head.setFont(theme.display_font(12, weight=700))
        root.addWidget(head)
        self._title_edits = {}
        for name in chart_titles:
            row = QHBoxLayout()
            row.setSpacing(6)
            lab = QLabel(name)
            lab.setObjectName("Hint")
            lab.setMinimumWidth(96)
            ed = QLineEdit(titles.get(name, ""))
            ed.setPlaceholderText(name)
            ed.setMinimumHeight(28)
            self._title_edits[name] = ed
            row.addWidget(lab)
            row.addWidget(ed, 1)
            root.addLayout(row)

        head = QLabel("Axes")
        head.setObjectName("SectionTitle")
        head.setFont(theme.display_font(12, weight=700))
        root.addWidget(head)
        self.x_edit = QLineEdit(style.get("xlabel") or "")
        self.x_edit.setPlaceholderText("(default for this chart type)")
        self.y_edit = QLineEdit(style.get("ylabel") or "")
        self.y_edit.setPlaceholderText("(default for this chart type)")
        for lab, ed in (("X axis name", self.x_edit), ("Y axis name", self.y_edit)):
            row = QHBoxLayout()
            row.setSpacing(6)
            l = QLabel(lab)
            l.setObjectName("Hint")
            l.setMinimumWidth(96)
            ed.setMinimumHeight(28)
            row.addWidget(l)
            row.addWidget(ed, 1)
            root.addLayout(row)
        trow = QHBoxLayout()
        trow.setSpacing(6)
        tl = QLabel("ticks")
        tl.setObjectName("Hint")
        tl.setMinimumWidth(96)
        self.xt_spin, self.yt_spin = QSpinBox(), QSpinBox()
        for sp, key, default in ((self.xt_spin, "xticks", 5),
                                 (self.yt_spin, "yticks", 5)):
            sp.setRange(2, 12)
            sp.setValue(int(style.get(key) or default))
            sp.setMinimumHeight(28)
            sp.setFixedWidth(70)
        trow.addWidget(tl)
        trow.addWidget(QLabel("X"))
        trow.addWidget(self.xt_spin)
        trow.addWidget(QLabel("Y"))
        trow.addWidget(self.yt_spin)
        trow.addStretch(1)
        root.addLayout(trow)
        tip = QLabel("A count axis rounds to whole steps, so it lands near "
                     "that number rather than exactly on it.")
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        root.addWidget(tip)

        head = QLabel("Text and marks")
        head.setObjectName("SectionTitle")
        head.setFont(theme.display_font(12, weight=700))
        root.addWidget(head)
        mrow = QHBoxLayout()
        mrow.setSpacing(6)
        ml = QLabel("size")
        ml.setObjectName("Hint")
        ml.setMinimumWidth(96)
        self.font_spin = QDoubleSpinBox()
        self.font_spin.setRange(5, 24)
        self.font_spin.setDecimals(1)
        self.font_spin.setSingleStep(0.5)
        self.font_spin.setSuffix(" pt")
        self.font_spin.setValue(float(style.get("font_pt") or 8))
        self.point_spin = QDoubleSpinBox()
        self.point_spin.setRange(0.5, 20)
        self.point_spin.setDecimals(1)
        self.point_spin.setSingleStep(0.5)
        self.point_spin.setSuffix(" px")
        self.point_spin.setValue(float(style.get("point_size") or 3.2))
        self.line_spin = QDoubleSpinBox()
        self.line_spin.setRange(0.3, 12)
        self.line_spin.setDecimals(1)
        self.line_spin.setSingleStep(0.2)
        self.line_spin.setSuffix(" px")
        self.line_spin.setValue(float(style.get("line_width") or 2.2))
        self.label_spin = QDoubleSpinBox()
        self.label_spin.setRange(5, 24)
        self.label_spin.setDecimals(1)
        self.label_spin.setSingleStep(0.5)
        self.label_spin.setSuffix(" pt")
        self.label_spin.setValue(float(style.get("label_pt")
                                       or style.get("font_pt") or 8))
        self.tick_bold_chk = QCheckBox("bold")
        self.tick_bold_chk.setChecked(bool(style.get("tick_bold", False)))
        self.label_bold_chk = QCheckBox("bold")
        self.label_bold_chk.setChecked(bool(style.get("label_bold", True)))
        for sp in (self.font_spin, self.label_spin, self.point_spin,
                   self.line_spin):
            sp.setMinimumHeight(28)
            sp.setFixedWidth(84)
        mrow.addWidget(ml)
        mrow.addWidget(QLabel("ticks"))
        mrow.addWidget(self.font_spin)
        mrow.addWidget(self.tick_bold_chk)
        mrow.addWidget(QLabel("axis names"))
        mrow.addWidget(self.label_spin)
        mrow.addWidget(self.label_bold_chk)
        mrow.addStretch(1)
        root.addLayout(mrow)
        mrow2 = QHBoxLayout()
        mrow2.setSpacing(6)
        ml2 = QLabel("marks")
        ml2.setObjectName("Hint")
        ml2.setMinimumWidth(96)
        mrow2.addWidget(ml2)
        mrow2.addWidget(QLabel("point"))
        mrow2.addWidget(self.point_spin)
        mrow2.addWidget(QLabel("line"))
        mrow2.addWidget(self.line_spin)
        mrow2.addStretch(1)
        root.addLayout(mrow2)

        crow = QHBoxLayout()
        crow.setSpacing(6)
        cl = QLabel("colour")
        cl.setObjectName("Hint")
        cl.setMinimumWidth(96)
        crow.addWidget(cl)
        self._colors = {}
        for key, label, default in (("axis_ink", "axis", theme.INK),
                                    ("point_color", "points", ""),
                                    ("line_color", "lines", "")):
            crow.addWidget(QLabel(label))
            crow.addLayout(self._color_pick(key, style.get(key) or "", default))
        crow.addStretch(1)
        root.addLayout(crow)
        note = QLabel("Points and lines follow their group's colour until you "
                      "pick one here. Axis text is dark by default — light "
                      "grey ticks vanish on a projector.")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        root.addWidget(note)

        head = QLabel("Scales")
        head.setObjectName("SectionTitle")
        head.setFont(theme.display_font(12, weight=700))
        root.addWidget(head)
        vrow, self.v_auto, self.v_lo, self.v_hi = _num_row(
            "value axis", style, "vmin", "vmax")
        xrow, self.x_auto, self.x_lo, self.x_hi = _num_row(
            "position X", style, "xmin", "xmax", " px")
        yrow, self.y_auto, self.y_lo, self.y_hi = _num_row(
            "position Y", style, "ymin", "ymax", " px")
        hrow, self.h_auto, self.h_lo, self.h_hi = _num_row(
            "heat colours", style, "heat_vmin", "heat_vmax")
        root.addLayout(vrow)
        root.addLayout(xrow)
        root.addLayout(yrow)
        root.addLayout(hrow)
        hint = QLabel("The value axis is the metric — the box plot's Y, the "
                      "histogram's X, the profile's Y. Position X / Y are the "
                      "image coordinates the profile and the heat map are "
                      "drawn across. Locked scales are what make two images, "
                      "two lots or two days comparable — with auto, each picks "
                      "its own range.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        reset = buttons.addButton("Reset", QDialogButtonBox.ResetRole)
        reset.clicked.connect(self._reset)
        root.addWidget(buttons)

    def _color_pick(self, key: str, current: str, default: str):
        """A swatch plus an *auto* box — auto hands the choice back."""
        row = QHBoxLayout()
        row.setSpacing(4)
        state = {"color": current or default}
        self._colors[key] = state
        btn = QPushButton()
        btn.setFixedSize(22, 22)

        def paint():
            btn.setStyleSheet(f"background:{state['color']}; "
                              "border:1px solid rgba(0,0,0,.25); "
                              "border-radius:4px;")
        paint()

        def choose():
            c = QColorDialog.getColor(QColor(state["color"]), self)
            if c.isValid():
                state["color"] = c.name()
                state["auto"] = False
                auto.setChecked(False)
                paint()
        btn.clicked.connect(choose)
        auto = QCheckBox("auto")
        auto.setChecked(not current)
        state["box"] = auto
        row.addWidget(btn)
        row.addWidget(auto)
        return row

    def _reset(self) -> None:
        for ed in list(self._title_edits.values()) + [self.x_edit, self.y_edit]:
            ed.clear()
        self.xt_spin.setValue(5)
        self.yt_spin.setValue(5)
        for auto in (self.v_auto, self.x_auto, self.y_auto, self.h_auto):
            auto.setChecked(True)
        self.font_spin.setValue(8.0)
        self.label_spin.setValue(8.0)
        self.tick_bold_chk.setChecked(False)
        self.label_bold_chk.setChecked(True)
        self.point_spin.setValue(3.2)
        self.line_spin.setValue(2.2)
        for state in self._colors.values():
            state["box"].setChecked(True)

    def result_style(self) -> dict:
        """The overrides, with anything left at its default omitted."""
        out: dict = {}
        titles = {k: ed.text().strip() for k, ed in self._title_edits.items()
                  if ed.text().strip()}
        if titles:
            out["titles"] = titles
        for key, ed in (("xlabel", self.x_edit), ("ylabel", self.y_edit)):
            if ed.text().strip():
                out[key] = ed.text().strip()
        out["xticks"] = int(self.xt_spin.value())
        out["yticks"] = int(self.yt_spin.value())
        out["font_pt"] = round(float(self.font_spin.value()), 1)
        out["label_pt"] = round(float(self.label_spin.value()), 1)
        out["tick_bold"] = bool(self.tick_bold_chk.isChecked())
        out["label_bold"] = bool(self.label_bold_chk.isChecked())
        out["point_size"] = round(float(self.point_spin.value()), 1)
        out["line_width"] = round(float(self.line_spin.value()), 1)
        for key, state in self._colors.items():
            if not state["box"].isChecked():
                out[key] = state["color"]
        for auto, lo, hi, kmin, kmax in (
                (self.v_auto, self.v_lo, self.v_hi, "vmin", "vmax"),
                (self.x_auto, self.x_lo, self.x_hi, "xmin", "xmax"),
                (self.y_auto, self.y_lo, self.y_hi, "ymin", "ymax"),
                (self.h_auto, self.h_lo, self.h_hi, "heat_vmin", "heat_vmax")):
            if not auto.isChecked() and hi.value() > lo.value():
                out[kmin], out[kmax] = lo.value(), hi.value()
        return out


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
    roi_del = Signal(int)
    roi_hovered = Signal(int)                # rid under the cursor (-1 = none)
    metrics_changed = Signal(list)
    metric_ids_changed = Signal(list)       # every metric on offer (incl. Q*n)
    roi_order_changed = Signal(str)         # "placed" | "asc" | "desc"
    roi_align = Signal(str)                 # align/distribute the selection
    roi_import = Signal()                   # read a flat ROI list
    roi_export = Signal()                   # write one
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
        # The ROI set travels on its own — a flat {color, x, y, w, h} list, so
        # a layout worked out somewhere else can be dropped straight in. Both
        # live in the card's own header, where they cost no height.
        self.roi_import_btn = _icon_button(
            "import", "Import ROIs — a JSON list of boxes, one object each "
            "with a colour and a top-left x / y. Each colour becomes a group.")
        self.roi_import_btn.clicked.connect(self.roi_import)
        self.roi_export_btn = _icon_button(
            "export", "Export ROIs — write every box as that same JSON list.")
        self.roi_export_btn.clicked.connect(self.roi_export)
        roi._head.addWidget(self.roi_import_btn)
        roi._head.addWidget(self.roi_export_btn)
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
        # Tidy: hand-placed ROIs sit a few pixels off each other, which only
        # shows up once the field fill tiles them into a staircase. Spelt out
        # rather than iconified — six unlabelled arrow glyphs at 30 px is a
        # puzzle, and this is a button you press once and want to press right.
        alab = QLabel("align")
        alab.setObjectName("Hint")
        alab.setToolTip("Acts on the ROIs selected with Shift+drag; with none "
                        "selected, on the whole active group.")
        rlay.addWidget(alab)
        self.align_btns = {}
        rows = (("left", "⇤ Left"), ("hcenter", "⇔ Centre"), ("right", "Right ⇥"),
                ("top", "⤒ Top"), ("vcenter", "⇕ Middle"), ("bottom", "Bottom ⤓"),
                ("distx", "⇹ Even across"), ("disty", "⇳ Even down"))
        tips = {
            "left": "Move them onto the leftmost left edge",
            "hcenter": "Line their centres up on one vertical axis",
            "right": "Move them onto the rightmost right edge",
            "top": "Move them onto the topmost top edge",
            "vcenter": "Line their centres up on one horizontal axis",
            "bottom": "Move them onto the bottommost bottom edge",
            "distx": "Space them evenly left to right (needs 3+)",
            "disty": "Space them evenly top to bottom (needs 3+)"}
        made = []
        for mode, text in rows:
            b = QPushButton(text)
            b.setMinimumHeight(30)
            b.setToolTip(f"{tips[mode]}. Shift+drag selects ROIs on the image; "
                         "with none selected the whole active group is used.")
            b.clicked.connect(lambda _=False, m=mode: self.roi_align.emit(m))
            self.align_btns[mode] = b
            made.append(b)
        for i in range(0, len(made), 3):
            rlay.addLayout(_button_row(*made[i:i + 3]))
        # Order: the list is where you scan for the odd one out, so it sorts
        # by the shown metric as well as by the order the ROIs were placed.
        orow = QHBoxLayout()
        orow.setSpacing(6)
        ol = QLabel("order")
        ol.setObjectName("Hint")
        self.order_box = QComboBox()
        self.order_box.setMinimumHeight(28)
        self.order_box.addItem("as placed", "placed")
        self.order_box.addItem("value ↑", "asc")
        self.order_box.addItem("value ↓", "desc")
        self.order_box.setToolTip("Sort the list by the metric shown on the "
                                  "ROIs. Labels stay with their ROI.")
        self.order_box.currentIndexChanged.connect(
            lambda _=0: self.roi_order_changed.emit(
                str(self.order_box.currentData() or "placed")))
        orow.addWidget(ol)
        orow.addWidget(self.order_box, 1)
        rlay.addLayout(orow)
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
            "• Double-click an ROI → pixel inspector")
        self.roi_hint.setObjectName("Hint")
        self.roi_hint.setWordWrap(True)
        rlay.addWidget(self.roi_hint)
        self.clear_btn = QPushButton("Clear group’s ROIs")
        self.clear_btn.clicked.connect(self._clear_active)
        rlay.addLayout(_button_row(self.clear_btn))
        root.addWidget(roi)

        # Metrics
        met = _card("Metrics", "grey-level statistics")
        self.metrics = MetricPicker()
        self.metrics.changed.connect(self.metrics_changed)
        self.metrics.ids_changed.connect(self.metric_ids_changed)
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
                  self.clear_btn, self.analysis_btn, self.roi_import_btn,
                  self.roi_export_btn, *self.align_btns.values()):
            w.setEnabled(has_image)

    def set_grid_ready(self, on: bool) -> None:
        self.add_grid_btn.setEnabled(on)

    def set_groups(self, groups: List[Group], active_gid, counts: dict) -> None:
        self._active_gid = active_gid
        sig = (tuple((g.gid, g.name, g.color) for g in groups), active_gid,
               tuple(sorted(counts.items())))
        if sig == getattr(self, "_grp_sig", None):
            return          # a refresh that changes nothing costs nothing
        self._grp_sig = sig
        _clear(self.grp_host)
        for g in groups:
            self.grp_host.addWidget(
                self._group_row(g, g.gid == active_gid, counts.get(g.gid, 0)))

    def set_rois(self, active_group_rois, active_rid,
                 selected_rids=None, outlier_rids=None, values=None) -> None:
        selected = set(selected_rids or [])
        outliers = set(outlier_rids or [])
        values = values or {}
        sig = (tuple((r.rid, tuple(r.rect), r.label) for r in active_group_rois),
               active_rid, tuple(sorted(selected)), tuple(sorted(outliers)),
               tuple(sorted((k, round(float(v), 6))
                            for k, v in values.items())))
        if sig == getattr(self, "_roi_sig", None):
            return          # rebuilding a hundred rows for nothing is the jank
        self._roi_sig = sig
        _clear(self.roi_host)
        self._roi_rows = {}
        for r in active_group_rois:
            row = self._roi_row(r, r.rid == active_rid, r.rid in selected,
                                r.rid in outliers, values.get(r.rid))
            self._roi_rows[r.rid] = row
            self.roi_host.addWidget(row)
        # size the list to its content, capped so it never buries the buttons
        n = len(active_group_rois)
        self.roi_scroll.setFixedHeight(min(176, n * 30 + 6) if n else 6)

    def set_hovered_roi(self, rid: int) -> None:
        """Highlight the row for `rid` (canvas → list hover sync)."""
        for r, row in getattr(self, "_roi_rows", {}).items():
            row.set_hover(r == rid)

    def set_metric_state(self, metrics, extra_ids=()) -> None:
        self.metrics.set_state(metrics, extra_ids)

    def set_roi_order(self, order: str) -> None:
        idx = self.order_box.findData(order)
        self.order_box.blockSignals(True)
        self.order_box.setCurrentIndex(idx if idx >= 0 else 0)
        self.order_box.blockSignals(False)

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

    def _roi_row(self, r, active: bool, selected: bool,
                 outlier: bool = False, value=None) -> QWidget:
        row = _ItemRow(active, compact=True, boxed=False, selected=selected)
        row.add_name(r.label or f"ROI {r.rid}", None,
                     color=(theme.WARNING if outlier else None))
        if outlier:
            row.add_flag("!", theme.WARNING,
                         "Outlier of the shown metric within this group")
        if value is not None:
            row.add_count(_fmt(float(value)))
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
    export_image_requested = Signal(str)    # which section: see SCOPES

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
        self.pos_btn = QPushButton("↗ Position")
        self.map_btn = QPushButton("▦ Heat map")
        for b, t in ((self.box_btn, "box"), (self.hist_btn, "hist"),
                     (self.pos_btn, "position"), (self.map_btn, "map")):
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.clicked.connect(lambda _=False, tt=t: self._pick_ctype(tt))
            head.addWidget(b)
        self.box_btn.setToolTip("Distribution as a box-and-strip plot.")
        self.hist_btn.setToolTip("Distribution as an overlaid histogram.")
        self.pos_btn.setToolTip(
            "Metric against ROI position — a uniform field reads flat.")
        self.map_btn.setToolTip(
            "Spatial heat map: each ROI drawn where it sits, coloured by the "
            "metric.")
        self.box_btn.setChecked(True)
        head.addSpacing(8)
        self.points_chk = QCheckBox("points")
        self.whiskers_chk = QCheckBox("whiskers")
        for chk in (self.points_chk, self.whiskers_chk):
            chk.setChecked(True)
            chk.toggled.connect(self._on_chart_opts)
            head.addWidget(chk)
        self.bins_spin = QSpinBox()
        self.bins_spin.setRange(0, 80)
        self.bins_spin.setValue(0)
        self.bins_spin.setPrefix("bins ")
        self.bins_spin.setSpecialValueText("bins auto")
        self.bins_spin.setFixedWidth(88)
        self.bins_spin.setFixedHeight(28)
        self.bins_spin.setToolTip("Histogram bin count. 0 = √n, bounded.")
        self.bins_spin.valueChanged.connect(self._on_chart_opts)
        self.bins_spin.setVisible(False)
        head.addWidget(self.bins_spin)
        self.pct_chk = QCheckBox("%")
        self.pct_chk.setToolTip(
            "Plot each group's share of its own n instead of raw counts — the "
            "only way two groups of different size compare.")
        self.pct_chk.toggled.connect(self._on_chart_opts)
        self.pct_chk.setVisible(False)
        head.addWidget(self.pct_chk)
        self.legend_chk = QCheckBox("legend")
        self.legend_chk.setToolTip(
            "Show the key in the plot's top-right corner — the groups with "
            "their n, and for a profile what each line means. Off by default: "
            "on a figure with two series it is furniture, and it sits on top "
            "of the data.")
        self.legend_chk.toggled.connect(self._on_chart_opts)
        head.addWidget(self.legend_chk)
        self.ownscale_chk = QCheckBox("own scale")
        self.ownscale_chk.setToolTip(
            "Give every group its own value range, printed under the lane. "
            "Off = one shared axis, where a group with a tiny spread beside a "
            "distant one flattens to a line.")
        self.ownscale_chk.toggled.connect(self._on_chart_opts)
        head.addWidget(self.ownscale_chk)
        self.axis_box = QComboBox()
        self.axis_box.addItem("X position", "x")
        self.axis_box.addItem("Y position", "y")
        self.axis_box.setToolTip("Plot against the ROI centre's X or Y coordinate.")
        self.axis_box.currentIndexChanged.connect(self._on_axis)
        self.axis_box.setVisible(False)
        head.addWidget(self.axis_box)
        self.trend_chk = QCheckBox("trend")
        self.trend_chk.setChecked(True)
        self.trend_chk.setToolTip("Overlay the least-squares tilt of the profile.")
        self.trend_chk.toggled.connect(self._on_chart_opts)
        self.trend_chk.setVisible(False)
        head.addWidget(self.trend_chk)
        self.cells_chk = QCheckBox("cells")
        self.cells_chk.setChecked(True)
        self.cells_chk.setToolTip(
            "Draw each ROI as a filled cell that meets its neighbours, so a "
            "cell can be read against the one beside it. Off = separate dots.")
        self.cells_chk.toggled.connect(self._on_cells)
        self.cells_chk.setVisible(False)
        head.addWidget(self.cells_chk)
        self.equal_chk = QCheckBox("equal cells")
        self.equal_chk.setChecked(True)
        self.equal_chk.setToolTip(
            "Draw every cell the same size, one slot per row and column — a "
            "die map. Off: each cell spans to the midline with its neighbour, "
            "so an uneven pitch gives cells of uneven area.")
        self.equal_chk.toggled.connect(self._on_chart_opts)
        self.equal_chk.setVisible(False)
        head.addWidget(self.equal_chk)
        self.mapval_chk = QCheckBox("values")
        self.mapval_chk.setToolTip(
            "Print the metric inside each cell (cells wide enough to hold it).")
        self.mapval_chk.toggled.connect(self._on_chart_opts)
        self.mapval_chk.setVisible(False)
        head.addWidget(self.mapval_chk)
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
        self.axes_btn = QPushButton("Chart settings…")
        self.axes_btn.setToolTip(
            "Rename the figures, name the axes, set the tick counts and lock "
            "the value and heat scales.")
        self.axes_btn.clicked.connect(self.edit_chart_settings)
        head.addWidget(self.axes_btn)
        self.image_btn = QToolButton()
        self.image_btn.setText("Export image ▾")
        self.image_btn.setPopupMode(QToolButton.InstantPopup)
        self.image_btn.setToolTip(
            "Save any part of the results as a picture — PNG at 3× for "
            "slides, or SVG for a paper.")
        self._image_menu = QMenu(self.image_btn)
        self.image_btn.setMenu(self._image_menu)
        self.image_btn.setEnabled(False)
        head.addWidget(self.image_btn)
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
        self._pos_axis = "x"
        self._last_result = None
        self._suppress = False
        self._cards: dict = {}          # scope -> the widget to export
        self._chart_widgets: List[DistributionChart] = []
        self._style: dict = {}          # title / axis / tick / scale overrides
        self._main = self.body_lay      # figures column
        self._side = self.body_lay      # annotations column

    def _pick_mode(self, mode: str) -> None:
        self._mode = mode
        self.between_btn.setChecked(mode == "between")
        self.within_btn.setChecked(mode == "within")
        self.mode_changed.emit(mode)

    def _pick_ctype(self, t: str) -> None:
        self._chart_type = t
        self.box_btn.setChecked(t == "box")
        self.hist_btn.setChecked(t == "hist")
        self.pos_btn.setChecked(t == "position")
        self.map_btn.setChecked(t == "map")
        for chk in (self.points_chk, self.whiskers_chk):
            chk.setEnabled(t == "box")
            chk.setVisible(t not in ("position", "map"))
        self.ownscale_chk.setVisible(t == "box")
        self.legend_chk.setVisible(t in ("box", "hist", "position"))
        for w in (self.bins_spin, self.pct_chk):
            w.setVisible(t == "hist")
        self.axis_box.setVisible(t == "position")
        self.trend_chk.setVisible(t == "position")
        for chk in (self.cells_chk, self.equal_chk, self.mapval_chk):
            chk.setVisible(t == "map")
        for chk in (self.equal_chk, self.mapval_chk):
            chk.setEnabled(self.cells_chk.isChecked())
        if self._last_result is not None:
            self._render_body(self._last_result)   # re-render, no recompute

    def _on_axis(self, _i: int) -> None:
        if self._suppress:
            return
        self._pos_axis = str(self.axis_box.currentData() or "x")
        if self._last_result is not None:
            self._render_body(self._last_result)   # positions are already there

    def _on_cells(self, on: bool) -> None:
        # both only mean anything for cells: values are printed inside one,
        # and dots have no area to equalise
        for chk in (self.equal_chk, self.mapval_chk):
            chk.setEnabled(bool(on))
        self._on_chart_opts()

    def _on_chart_opts(self, _=False) -> None:
        if self._last_result is not None:
            self._render_body(self._last_result)

    # -- chart settings ------------------------------------------------ #
    def chart_style(self) -> dict:
        """The title / axis / tick / scale overrides — saved with the project."""
        return dict(self._style)

    def set_chart_style(self, style) -> None:
        self._style = dict(style or {})
        if self._last_result is not None:
            self._render_body(self._last_result)

    def edit_chart_settings(self) -> None:
        names = [c._title for c in self._chart_widgets] or ["chart"]
        dlg = ChartSettingsDialog(self, names, self._style)
        if dlg.exec() == QDialog.Accepted:
            self.set_chart_style(dlg.result_style())

    def _style_for(self, title: str) -> dict:
        """The shared overrides plus this chart's own title, if it has one."""
        st = {k: v for k, v in self._style.items() if k != "titles"}
        custom = (self._style.get("titles") or {}).get(title)
        if custom:
            st["title"] = custom
        return st

    def chart_state(self) -> tuple:
        """(chart type, position axis) — persisted with the project."""
        return self._chart_type, self._pos_axis

    def set_chart_state(self, ctype, axis) -> None:
        self._suppress = True
        self._pos_axis = "y" if str(axis).lower() == "y" else "x"
        self.axis_box.setCurrentIndex(1 if self._pos_axis == "y" else 0)
        self._suppress = False
        self._pick_ctype(ctype if ctype in ("box", "hist", "position", "map")
                         else "box")

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
        self._cards = {}
        self._chart_widgets = []
        self.sub.setText(result.subtitle)
        if result.empty:
            self._main = self.body_lay
            self._side = self.body_lay
            self._empty(result.empty)
            return
        # Two columns: the figures on the left, where the eye starts and where
        # they get the room to be figures; the numbers that annotate them
        # down the right. One column put every chart in a wide band at the top
        # with the tables stacked underneath, which reads as two unrelated
        # pages rather than one result.
        row = QWidget()
        rlay = QHBoxLayout(row)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(14)
        main_host, side_host = QWidget(), QWidget()
        self._main = QVBoxLayout(main_host)
        self._side = QVBoxLayout(side_host)
        for lay in (self._main, self._side):
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(10)
        side_host.setMinimumWidth(300)
        rlay.addWidget(main_host, 3)
        rlay.addWidget(side_host, 2)
        self.body_lay.addWidget(row)

        charts = [(c.title, [{"label": s.label, "color": s.color,
                              "values": s.values,
                              "pos_x": s.pos_x, "pos_y": s.pos_y}
                             for s in c.series])
                  for c in result.charts]
        self._main.addStretch(1)        # the figures sit mid-height…
        self._chart_grid(charts)
        self._main.addStretch(1)
        if result.ranking:
            self._ranking_card(result.ranking)
        if result.heat:
            self._heatmap_card(result.heat)
        if result.table_rows:
            self._table(result.table_headers, result.table_rows)
        self._side.addStretch(1)        # …the annotations stack from the top
        if not any(self._cards.get(k) for k in ("ranking", "heat", "table")):
            side_host.hide()            # nothing to annotate with: all figure
            rlay.setStretch(1, 0)
        self._rebuild_image_menu()

    def _rebuild_image_menu(self) -> None:
        """Offer exactly the sections this result has, each chart included."""
        self._image_menu.clear()
        labels = dict(self.SCOPES)
        scopes = self.scopes_available()
        for key in scopes:
            self._image_menu.addAction(
                f"{labels[key]}…",
                lambda _=False, k=key: self.export_image_requested.emit(k))
            if key == "charts" and len(self._chart_widgets) > 1:
                # one figure per file is what a document actually takes
                for i, c in enumerate(self._chart_widgets):
                    self._image_menu.addAction(
                        f"    {c.title_text()}…",
                        lambda _=False, k=f"chart:{i}":
                        self.export_image_requested.emit(k))
        self.image_btn.setEnabled(bool(scopes))

    # -- image export --------------------------------------------------- #
    SCOPES = (("charts", "Charts"), ("ranking", "Attribute ranking"),
              ("heat", "Group × metric heatmap"), ("table", "Summary table"),
              ("all", "Everything"))

    def scopes_available(self) -> List[str]:
        """Which sections the current result actually has to export."""
        out = [k for k, _lab in self.SCOPES
               if k not in ("all",) and self._cards.get(k) is not None]
        return out + (["all"] if len(out) > 1 else [])

    def save_image(self, path: str, scope: str = "charts",
                   scale: float = 3.0) -> Optional[str]:
        """Save one section of the results — or all of it — as a picture."""
        if scope == "all":
            widgets = [w for _k, w in self._cards.items() if w is not None]
            if not widgets:
                return None
            area = widgets[0].geometry()
            for w in widgets[1:]:
                area = area.united(w.geometry())
            return save_widget_image(self.body, path, scale, crop=area,
                                     background=theme.WINDOW)
        if scope.startswith("chart:"):          # one figure on its own
            i = int(scope.split(":", 1)[1])
            if not 0 <= i < len(self._chart_widgets):
                return None
            return save_widget_image(self._chart_widgets[i], path, scale)
        host = self._cards.get(scope)
        if host is None:
            return None
        crop = None
        if scope == "charts":
            # only the figures travel — the layout's slack either side of them
            # is margin on screen and dead white space in a document
            charts = host.findChildren(DistributionChart)
            if not charts:
                return None
            crop = charts[0].geometry()
            for c in charts[1:]:
                crop = crop.united(c.geometry())
        return save_widget_image(host, path, scale, crop=crop)

    def save_charts_image(self, path: str, scale: float = 3.0) -> Optional[str]:
        return self.save_image(path, "charts", scale)

    def _ranking_card(self, ranking) -> None:
        host = QFrame()
        host.setObjectName("Card")
        self._cards["ranking"] = host
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
        self._side.addWidget(host)

    def _heatmap_card(self, heat) -> None:
        host = QFrame()
        host.setObjectName("Card")
        self._cards["heat"] = host
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
        self._side.addWidget(host)

    def _chart_grid(self, charts) -> None:
        grid_host = QWidget()
        grid_host.setObjectName("ChartSheet")
        self._cards["charts"] = grid_host
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        opts = {"points": self.points_chk.isChecked(),
                "whiskers": self.whiskers_chk.isChecked(),
                "own_scale": self.ownscale_chk.isChecked(),
                "legend": self.legend_chk.isChecked(),
                "bins": int(self.bins_spin.value()),
                "hist_pct": self.pct_chk.isChecked(),
                "cells": self.cells_chk.isChecked(),
                "equal_cells": self.equal_chk.isChecked(),
                "map_values": (self.mapval_chk.isChecked()
                               and self.cells_chk.isChecked())}
        wide = self._chart_type in ("position", "map")   # these need the width
        for i, (title, series) in enumerate(charts):
            chart = DistributionChart()
            chart.set_data(title, series, self._chart_type, opts,
                           axis=self._pos_axis, trend=self.trend_chk.isChecked(),
                           xlabel=title, style=self._style_for(title))
            self._chart_widgets.append(chart)
            if wide:
                grid.addWidget(chart, i, 0, 1, 3)
                continue
            # One figure per row, as large as the column allows up to a
            # printable width — a distribution squeezed two-up is a thumbnail,
            # and a thumbnail is what nobody can read on a slide.
            chart.setMinimumWidth(340)
            chart.setMaximumWidth(720)
            grid.addWidget(chart, i, 1)
        if not wide:
            grid.setColumnStretch(0, 1)      # slack either side: a plate on a
            grid.setColumnStretch(2, 1)      # page, not a banner on a margin
        self._main.addWidget(grid_host)

    def _table(self, headers, rows) -> None:
        host = QFrame()
        host.setObjectName("Card")
        self._cards["table"] = host
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
        self._side.addWidget(host)

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

    export_image_requested = Signal()

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
