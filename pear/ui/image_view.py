"""Image stage: zoom/pan and place / move / resize ROIs.

ROIs belong to groups and are drawn in their group's colour.

Adding ROIs (à la the sibling Perspective-Combination tool):
  * **single** — click to drop a default box (or drag to size it).
  * **grid**   — click the top-left, then the bottom-right anchor; a live
                 row×col preview follows; press Enter / Add grid to commit.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QImage, QKeyEvent, QLinearGradient,
                           QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent)
from PySide6.QtWidgets import QWidget

from pear.core.analysis import ROI, Group, grid_between, heat_color
from pear.ui import theme

Rect = Tuple[int, int, int, int]
_HANDLE = 8
_MIN_ROI = 4
_DEFAULT = 28          # default single-ROI size (px) for a plain click
_LEGEND_H = 58         # colour-key strip added under an exported field


def label_rect(r: QRectF, bw: float, bh: float,
               hovered: bool) -> Optional[QRectF]:
    """Where a ``bw × bh`` value label goes on ROI ``r``, or None: don't draw.

    Zoomed out, a label is wider than its box: printed anyway they collide
    with each other and bury the boxes they belong to. One that does not fit
    is dropped and comes back on zoom — except on the ROI under the cursor,
    which floats its label above the box (below it, at the top edge of the
    image) so a value is always one hover away.
    """
    cx, cy = r.center().x(), r.center().y()
    if bw <= r.width() and bh <= r.height():
        return QRectF(cx - bw / 2, cy - bh / 2, bw, bh)
    if not hovered:
        return None
    top = r.top() - bh - 2
    return QRectF(cx - bw / 2, top if top >= 0 else r.bottom() + 2, bw, bh)


class ImageView(QWidget):
    roi_created = Signal(object)            # rect (single ROI into active group)
    grid_committed = Signal(object)         # list[rect] (a row×col grid)
    grid_ready = Signal(bool)               # both grid anchors placed
    roi_modified = Signal(int, object)      # rid, rect
    roi_selected = Signal(int)              # rid
    roi_delete_requested = Signal(int)      # rid (Delete key on selected ROI)
    rois_selected = Signal(object)          # list[rid] (marquee multi-select)
    rois_delete_requested = Signal(object)  # list[rid] (Delete on a selection)
    roi_hovered = Signal(int)               # rid under the cursor (-1 = none)
    roi_duplicate_requested = Signal(int)   # rid (Ctrl+D)
    roi_inspect_requested = Signal(int)     # rid (double-click → pixel inspector)
    group_index_requested = Signal(int)     # switch active group by index (1–9)
    cursor_info = Signal(str)
    zoom_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)   # the rail's width wins
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._image: Optional[np.ndarray] = None
        self._pixmap: Optional[QPixmap] = None
        self._scale = 1.0
        self._offset = QPointF(0, 0)
        self._fitted = True     # still showing the fit; a zoom or pan ends it

        self._groups: List[Group] = []
        self._active_gid: Optional[str] = None
        self._rois: List[ROI] = []
        self._active_rid: Optional[int] = None
        self._selection: set = set()           # rids marquee-selected
        self._marquee: Optional[QRectF] = None  # selection rect (image coords)
        self._heat: dict = {}                  # rid -> hex colour (heatmap)
        self._heat_legend: Optional[tuple] = None  # (vmin, vmax, label)
        self._heat_alpha = 178                 # heat fill opacity (0-255)
        self._heat_cells: dict = {}            # rid -> (x0,y0,x1,y1) image px
        self._outliers: set = set()            # rids flagged as outliers
        self._hover_rid: int = -1              # rid under the cursor
        self._exporting = False                # drop the in-progress marks

        self._grid_mode = False
        self._grid_stage = 0               # 0 none · 1 have TL · 2 have TL+BR
        self._grid_tl: Optional[QPointF] = None   # centre of top-left ROI
        self._grid_br: Optional[QPointF] = None   # centre of bottom-right ROI
        self._grid_rows, self._grid_cols = 3, 3
        self._roi_w, self._roi_h = _DEFAULT, _DEFAULT   # size for click / grid
        self._cursor_img = QPointF()
        self._roi_values: dict = {}        # rid -> short text drawn on the ROI

        self._interact: Optional[str] = None   # draw|move|resize|pan
        self._drag_start = QPointF()
        self._draw_rect: Optional[QRectF] = None
        self._resize_handle: Optional[int] = None
        self._roi_at_press: Optional[Rect] = None
        self._pan_at_press = QPointF()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def set_image(self, image: np.ndarray) -> None:
        self._image = np.ascontiguousarray(image)
        h, w = image.shape[:2]
        qimg = QImage(self._image.data, w, h, w, QImage.Format_Grayscale8)
        self._pixmap = QPixmap.fromImage(qimg.copy())
        self.fit()

    def set_groups(self, groups, active_gid) -> None:
        self._groups = groups
        self._active_gid = active_gid
        self.update()

    def set_rois(self, rois, active_rid) -> None:
        self._rois = rois
        self._active_rid = active_rid
        self.update()

    def set_roi_values(self, values: dict) -> None:
        """Map of rid -> short text drawn centred on each ROI (live metric)."""
        self._roi_values = values or {}
        self.update()

    def set_selection(self, rids) -> None:
        """Highlight a set of ROIs (kept in sync with the rail's selection)."""
        self._selection = set(rids or [])
        self.update()

    def set_heatmap(self, colors: dict, legend=None, alpha: int = 178) -> None:
        """Colour ROI fills by value: rid -> hex. legend = (vmin, vmax, label).

        ``alpha`` (0-255) is how opaque the fill is — turn it down to read the
        image under the box.
        """
        self._heat = colors or {}
        self._heat_legend = legend
        self._heat_alpha = int(np.clip(int(alpha), 0, 255))
        self.update()

    def export_image(self, path: str, scale: float = 2.0) -> Optional[str]:
        """Save the annotated field: the image at its own resolution × ``scale``.

        Not a screenshot of the stage — the view's zoom, pan and black
        surround have nothing to do with the figure someone wants in a
        report. The pixels are drawn at their own size and the overlays (heat,
        cells, ROI boxes, values, flags, the colour key) on top of them, so
        the export is as sharp as the data allows whatever the window shows.
        """
        if self._pixmap is None:
            return None
        scale = float(np.clip(scale, 0.25, 8.0))
        w = max(1, int(round(self._pixmap.width() * scale)))
        h = max(1, int(round(self._pixmap.height() * scale)))
        # the colour key gets a strip of its own rather than sitting on top of
        # the ROIs it is the key for
        legend_h = _LEGEND_H if (self._heat_legend and self._heat) else 0
        keep = (self._scale, self._offset)
        self._scale, self._offset = scale, QPointF(0.0, 0.0)
        self._exporting = True
        try:
            if str(path).lower().endswith(".svg"):
                try:
                    from PySide6.QtSvg import QSvgGenerator
                except ImportError:
                    return None
                gen = QSvgGenerator()
                gen.setFileName(path)
                gen.setSize(QSize(w, h + legend_h))
                gen.setViewBox(QRect(0, 0, w, h + legend_h))
                painter = QPainter()
                if not painter.begin(gen):
                    return None
                painter.fillRect(QRectF(0, 0, w, h + legend_h),
                                 QColor(theme.STAGE))
                self._paint_export(painter, w, h, legend_h)
                painter.end()
                return path
            pm = QPixmap(w, h + legend_h)
            pm.fill(QColor(theme.STAGE))
            painter = QPainter(pm)
            self._paint_export(painter, w, h, legend_h)
            painter.end()
            return path if pm.save(path) else None
        finally:
            self._scale, self._offset = keep
            self._exporting = False

    def _paint_export(self, p: QPainter, w: int, h: int,
                      legend_h: int = 0) -> None:
        """The field and its overlays — no cursor HUD, no marquee, no grid
        preview: those are things you are doing, not things you measured."""
        p.setRenderHint(QPainter.Antialiasing, True)
        p.drawPixmap(QRectF(0, 0, w, h), self._pixmap,
                     QRectF(self._pixmap.rect()))
        self._paint_heat_cells(p)
        self._paint_rois(p)
        if legend_h:
            self._paint_colorbar(p, QRectF(0, h, w, legend_h))

    def set_heat_cells(self, cells: dict) -> None:
        """Tile the heat across the field: rid -> (x0, y0, x1, y1) in image px.

        Empty = paint the heat inside the ROI boxes only.
        """
        self._heat_cells = cells or {}
        self.update()

    def set_outliers(self, rids) -> None:
        self._outliers = set(rids or [])
        self.update()

    def set_hover(self, rid: int) -> None:
        """Highlight the hovered ROI (list → canvas hover sync)."""
        rid = -1 if rid is None else int(rid)
        if rid != self._hover_rid:
            self._hover_rid = rid
            self.update()

    def set_grid_mode(self, on: bool) -> None:
        self._grid_mode = bool(on)
        self._reset_grid()
        self.setFocus()
        self.update()

    def set_grid_shape(self, rows: int, cols: int) -> None:
        self._grid_rows, self._grid_cols = max(1, rows), max(1, cols)
        self.update()

    def set_roi_size(self, w: int, h: int) -> None:
        self._roi_w, self._roi_h = max(_MIN_ROI, int(w)), max(_MIN_ROI, int(h))
        self.update()

    def commit_grid(self) -> None:
        if self._grid_stage == 2:
            rects = self._grid_rects()
            if rects:
                self.grid_committed.emit(rects)
        self._reset_grid()
        self.update()

    def cancel_grid(self) -> None:
        self._reset_grid()
        self.update()

    def has_image(self) -> bool:
        return self._image is not None

    def fit(self) -> None:
        if self._pixmap is None:
            return
        vw, vh = self.width(), self.height()
        iw, ih = self._pixmap.width(), self._pixmap.height()
        if iw == 0 or ih == 0:
            return
        self._scale = min(vw / iw, vh / ih) * 0.96
        self._offset = QPointF((vw - iw * self._scale) / 2.0,
                               (vh - ih * self._scale) / 2.0)
        self._fitted = True
        self.update()
        self.zoom_changed.emit(self._scale)

    def zoom_by(self, factor: float, anchor: Optional[QPointF] = None) -> None:
        if self._image is None:
            return
        if anchor is None:
            anchor = QPointF(self.width() / 2.0, self.height() / 2.0)
        ia = self._to_image(anchor)
        self._fitted = False
        self._scale = float(np.clip(self._scale * factor, 0.05, 40.0))
        self._offset = QPointF(anchor.x() - ia.x() * self._scale,
                               anchor.y() - ia.y() * self._scale)
        self.update()
        self.zoom_changed.emit(self._scale)

    def zoom_in(self):
        self.zoom_by(1.25)

    def zoom_out(self):
        self.zoom_by(0.8)

    def zoom_percent(self) -> int:
        return int(round(self._scale * 100))

    # ------------------------------------------------------------------ #
    # transforms
    # ------------------------------------------------------------------ #
    def _to_widget(self, x, y) -> QPointF:
        return QPointF(self._offset.x() + x * self._scale,
                       self._offset.y() + y * self._scale)

    def _to_image(self, p: QPointF) -> QPointF:
        return QPointF((p.x() - self._offset.x()) / self._scale,
                       (p.y() - self._offset.y()) / self._scale)

    def _rect_to_widget(self, r: Rect) -> QRectF:
        x, y, w, h = r
        tl = self._to_widget(x, y)
        return QRectF(tl.x(), tl.y(), w * self._scale, h * self._scale)

    def _gcolor(self, gid: str) -> QColor:
        for g in self._groups:
            if g.gid == gid:
                return QColor(g.color)
        return QColor(theme.INK3)

    # ------------------------------------------------------------------ #
    # painting
    # ------------------------------------------------------------------ #
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.STAGE))
        if self._pixmap is None:
            p.setPen(QColor(theme.INK3))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Load an 8-bit grayscale image to begin.")
            p.end()
            return
        target = QRectF(self._offset.x(), self._offset.y(),
                        self._pixmap.width() * self._scale,
                        self._pixmap.height() * self._scale)
        p.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        self._paint_heat_cells(p)
        self._paint_rois(p)
        self._paint_rubberband(p)
        self._paint_marquee(p)
        self._paint_grid_preview(p)
        self._paint_colorbar(p)
        self._paint_hud(p)
        p.end()

    def _paint_heat_cells(self, p: QPainter) -> None:
        """Heat spread over each ROI's cell, under the ROI outlines.

        The ROI keeps its own box on top, so it stays visible which rectangle
        was actually measured and which area merely carries its colour.
        """
        if not self._heat_cells or not self._heat:
            return
        p.setPen(Qt.NoPen)
        for roi in self._rois:
            cell = self._heat_cells.get(roi.rid)
            heat = self._heat.get(roi.rid)
            if cell is None or heat is None:
                continue
            x0, y0, x1, y1 = cell
            tl = self._to_widget(x0, y0)
            br = self._to_widget(x1, y1)
            fill = QColor(heat)
            fill.setAlpha(self._heat_alpha)
            p.setBrush(fill)
            p.drawRect(QRectF(tl, br))

    def _paint_rois(self, p: QPainter) -> None:
        for roi in self._rois:
            active_grp = roi.gid == self._active_gid
            selected = roi.rid == self._active_rid
            in_sel = roi.rid in self._selection
            color = self._gcolor(roi.gid)
            r = self._rect_to_widget(roi.rect)
            heat = self._heat.get(roi.rid)
            if heat is not None and roi.rid in self._heat_cells:
                fill = Qt.NoBrush                    # the cell under it is the fill
            elif heat is not None:                   # value heatmap fill
                fill = QColor(heat)
                fill.setAlpha(self._heat_alpha)
            else:
                fill = QColor(color)
                fill.setAlpha(90 if active_grp else 45)   # the group's tag
            # The outline is always neutral ink over a white halo. Colour on
            # this stage means a value — the heat ramp — so a box wearing its
            # group's colour reads as a reading off the scale; and a neutral
            # rule is legible on a black stage, on a bright feature and on any
            # colour of the ramp alike. The group shows in the fill tint.
            width = 2.4 if selected else (1.8 if active_grp else 1.2)
            p.setBrush(fill)
            p.setPen(Qt.NoPen)
            p.drawRect(r)
            self._stroke_neutral(p, r, width, dashed=False, strong=active_grp)
            if roi.rid == self._hover_rid and not self._exporting:
                self._paint_hover_ring(p, r)
            if in_sel and not self._exporting:
                self._paint_selection_ring(p, r)
            if roi.rid in self._outliers:
                self._paint_outlier(p, r)
            val = self._roi_values.get(roi.rid)
            if val is not None:
                self._paint_value(p, r, val, roi.rid == self._hover_rid)
            if selected and not self._grid_mode and not self._exporting:
                self._paint_handles(p, r, color)

    def _stroke_neutral(self, p: QPainter, r: QRectF, width: float,
                        dashed: bool = False, strong: bool = True) -> None:
        """Outline that stays legible on any fill: white halo, dark ink on top."""
        p.setBrush(Qt.NoBrush)
        halo = QPen(QColor(255, 255, 255, 190), width + 2.0)
        halo.setCosmetic(True)
        p.setPen(halo)
        p.drawRect(r)
        ink = QPen(QColor(17, 24, 39, 255 if strong else 150), width)
        ink.setCosmetic(True)
        if dashed:
            ink.setStyle(Qt.DashLine)
        p.setPen(ink)
        p.drawRect(r)

    def _paint_hover_ring(self, p: QPainter, r: QRectF) -> None:
        pen = QPen(QColor(255, 255, 255, 210), 1.4)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(-3, -3, 3, 3))

    def _paint_outlier(self, p: QPainter, r: QRectF) -> None:
        pen = QPen(QColor(theme.WARNING), 2.0)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(-1, -1, 1, 1))
        self._paint_badge(p, r, "!", QColor(theme.WARNING), corner="tr")

    def _paint_colorbar(self, p: QPainter, frame: Optional[QRectF] = None) -> None:
        if not self._heat_legend or not self._heat:
            return
        vmin, vmax, label = self._heat_legend
        frame = frame if frame is not None else QRectF(self.rect())
        x, y, w, h = frame.left() + 14, frame.bottom() - 42, 150, 12
        grad = QLinearGradient(float(x), 0.0, float(x + w), 0.0)
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            grad.setColorAt(t, QColor(heat_color(t)))
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(QRectF(x, y, w, h), 3, 3)
        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(x, y, w, h), 3, 3)
        p.setPen(QColor("#FFFFFF"))
        p.setFont(theme.mono_font(8, weight=700))
        p.drawText(int(x), int(y - 4), label)
        p.setFont(theme.mono_font(8))
        p.drawText(QRectF(x, y + h + 1, w, 12), Qt.AlignLeft, f"{vmin:.3g}")
        p.drawText(QRectF(x, y + h + 1, w, 12), Qt.AlignRight, f"{vmax:.3g}")

    def _paint_selection_ring(self, p: QPainter, r: QRectF) -> None:
        pen = QPen(QColor("#FFFFFF"), 1.6)
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(-2, -2, 2, 2))

    def _paint_badge(self, p: QPainter, r: QRectF, text: str,
                     color: QColor, corner: str = "tl") -> None:
        p.setFont(theme.mono_font(8, weight=700))
        fm = p.fontMetrics()
        bw = fm.horizontalAdvance(text) + 8
        bh = fm.height() + 2
        by = r.top() - bh if r.top() - bh >= 0 else r.top()
        bx = r.left() if corner == "tl" else r.right() - bw
        bg = QRectF(bx, by, bw, bh)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawRoundedRect(bg, 3, 3)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(bg, Qt.AlignCenter, text)

    def _paint_value(self, p: QPainter, r: QRectF, text: str,
                     hovered: bool = False) -> None:
        """The metric, centred on the ROI — but only where it fits.

        Zoomed out, a label is wider than its box: printed anyway they collide
        with each other and bury the boxes they belong to. A label that does
        not fit is dropped and comes back on zoom; the ROI under the cursor
        keeps its label whatever the zoom, floated above the box, so a value
        is always one hover away.
        """
        p.setFont(theme.mono_font(9, weight=700))
        fm = p.fontMetrics()
        # the *text* has to fit the box; its pill may overhang a little, which
        # keeps a 4-digit label from vanishing on a box a 3-digit one fits
        bg = label_rect(r, float(fm.horizontalAdvance(text)), float(fm.height()),
                        hovered)
        if bg is None:
            return
        pill = bg.adjusted(-3, 0, 3, 0)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(17, 24, 39, 200))
        p.drawRoundedRect(pill, 3, 3)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(pill, Qt.AlignCenter, text)

    def _paint_handles(self, p: QPainter, rect: QRectF, color: QColor) -> None:
        p.setPen(QPen(QColor("#FFFFFF"), 1.4))
        p.setBrush(QColor(17, 24, 39))          # neutral, like the outline
        for c in self._handle_centers(rect):
            p.drawRect(QRectF(c.x() - _HANDLE / 2, c.y() - _HANDLE / 2,
                              _HANDLE, _HANDLE))

    def _paint_rubberband(self, p: QPainter) -> None:
        if self._draw_rect is None:
            return
        rn = self._draw_rect.normalized()
        tl = self._to_widget(rn.left(), rn.top())
        self._stroke_neutral(p, QRectF(tl.x(), tl.y(), rn.width() * self._scale,
                                       rn.height() * self._scale),
                             2.0, dashed=True)

    def _paint_marquee(self, p: QPainter) -> None:
        if self._marquee is None:
            return
        rn = self._marquee.normalized()
        tl = self._to_widget(rn.left(), rn.top())
        rect = QRectF(tl.x(), tl.y(), rn.width() * self._scale,
                      rn.height() * self._scale)
        fill = QColor(theme.INFO)
        fill.setAlpha(28)
        pen = QPen(QColor(theme.INFO), 1.5)
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(fill)
        p.drawRect(rect)

    def _grid_rects(self) -> List[Rect]:
        if self._grid_tl is None:
            return []
        br = self._grid_br if self._grid_stage >= 2 else self._cursor_img
        return grid_between((self._grid_tl.x(), self._grid_tl.y()),
                            (br.x(), br.y()), self._grid_rows, self._grid_cols,
                            self._roi_w, self._roi_h)

    def _paint_grid_preview(self, p: QPainter) -> None:
        if not self._grid_mode or self._grid_stage == 0:
            return
        rects = self._grid_rects()
        if not rects:
            return
        prev = QColor(255, 255, 255, 60)
        for rect in rects:
            r = self._rect_to_widget(rect)
            p.setPen(Qt.NoPen)
            p.setBrush(prev)
            p.drawRect(r)
            self._stroke_neutral(p, r, 1.4, dashed=True, strong=False)
        # emphasise the two corner anchors
        apen = QPen(QColor(theme.INFO), 2.2)
        apen.setCosmetic(True)
        p.setPen(apen)
        p.setBrush(Qt.NoBrush)
        for rect in (rects[0], rects[-1]):
            p.drawRect(self._rect_to_widget(rect))

    def _paint_hud(self, p: QPainter) -> None:
        if self._grid_mode:
            if self._grid_stage == 0:
                msg = "▦ GRID — click the top-left corner"
            elif self._grid_stage == 1:
                msg = "▦ GRID — click the bottom-right corner"
            else:
                msg = (f"▦ GRID {self._grid_rows}×{self._grid_cols} — "
                       "Enter / Add grid to place · Esc to cancel")
            self._banner(p, msg, QColor(theme.INFO))
            return
        if not self._rois:
            name = next((g.name for g in self._groups
                         if g.gid == self._active_gid), None)
            if name:
                self._banner(p, f"Click on the image to add an ROI to “{name}”"
                             " (or drag to size it)", QColor(theme.AMBER))

    def _banner(self, p: QPainter, text: str, accent: QColor) -> None:
        p.setFont(theme.display_font(10, weight=700))
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(text) + 24
        h = fm.height() + 10
        x = (self.width() - w) / 2
        p.setPen(QPen(accent, 1.5))
        p.setBrush(QColor(17, 24, 39, 210))
        p.drawRoundedRect(QRectF(x, 12, w, h), 8, 8)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QRectF(x, 12, w, h), Qt.AlignCenter, text)

    # ------------------------------------------------------------------ #
    # hit testing
    # ------------------------------------------------------------------ #
    @staticmethod
    def _handle_centers(rect: QRectF) -> List[QPointF]:
        return [QPointF(rect.left(), rect.top()),
                QPointF(rect.right(), rect.top()),
                QPointF(rect.right(), rect.bottom()),
                QPointF(rect.left(), rect.bottom())]

    def _active_roi(self) -> Optional[ROI]:
        for r in self._rois:
            if r.rid == self._active_rid:
                return r
        return None

    def _handle_at(self, pos: QPointF) -> Optional[int]:
        roi = self._active_roi()
        if roi is None:
            return None
        rect = self._rect_to_widget(roi.rect)
        for i, c in enumerate(self._handle_centers(rect)):
            if abs(pos.x() - c.x()) <= _HANDLE and abs(pos.y() - c.y()) <= _HANDLE:
                return i
        return None

    def _roi_body_at(self, pos: QPointF) -> Optional[int]:
        ordered = sorted(self._rois, key=lambda r: (r.rid != self._active_rid,
                                                    r.gid != self._active_gid))
        for r in ordered:
            if self._rect_to_widget(r.rect).contains(pos):
                return r.rid
        return None

    def _marquee_hits(self) -> List[int]:
        """rids of active-group ROIs intersecting the marquee rectangle."""
        if self._marquee is None:
            return []
        sel = self._marquee.normalized()
        hits = []
        for r in self._rois:
            if r.gid != self._active_gid:
                continue
            x, y, w, h = r.rect
            if sel.intersects(QRectF(x, y, w, h)):
                hits.append(r.rid)
        return hits

    # ------------------------------------------------------------------ #
    # mouse / key / wheel
    # ------------------------------------------------------------------ #
    def mousePressEvent(self, e: QMouseEvent) -> None:
        pos = QPointF(e.position())
        if e.button() in (Qt.MiddleButton, Qt.RightButton):
            self._interact = "pan"
            self._drag_start = pos
            self._pan_at_press = QPointF(self._offset)
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton or self._image is None:
            return
        if self._grid_mode:
            ip = self._to_image(pos)
            if self._grid_stage == 0:
                self._grid_tl = ip
                self._grid_stage = 1
            elif self._grid_stage == 1:
                self._grid_br = ip
                self._grid_stage = 2
                self.grid_ready.emit(True)
            else:
                self.commit_grid()
            self.update()
            return
        if e.modifiers() & Qt.ShiftModifier:
            # Shift+drag → marquee select ROIs of the active group
            ip = self._to_image(pos)
            self._interact = "marquee"
            self._drag_start = pos
            self._marquee = QRectF(ip, ip)
            self.update()
            return
        if self._selection:                       # a plain click clears a marquee
            self._selection = set()
            self.rois_selected.emit([])
        handle = self._handle_at(pos)
        if handle is not None:
            self._interact = "resize"
            self._resize_handle = handle
            self._roi_at_press = self._active_roi().rect
            self._drag_start = pos
            return
        body = self._roi_body_at(pos)
        if body is not None:
            if body != self._active_rid:
                self._active_rid = body
                self.roi_selected.emit(body)
                self.update()
                return
            self._interact = "move"
            self._roi_at_press = self._active_roi().rect
            self._drag_start = pos
            return
        ip = self._to_image(pos)
        self._interact = "draw"
        self._drag_start = pos
        self._draw_rect = QRectF(ip, ip)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        pos = QPointF(e.position())
        self._cursor_img = self._to_image(pos)
        self._emit_cursor(pos)
        # Panning outranks the mode: the right button drags the picture around
        # whether or not a grid is being placed, and grid placement is exactly
        # when you need to reach the far corner.
        if self._interact == "pan":
            self._offset = self._pan_at_press + (pos - self._drag_start)
            self._fitted = False        # panned away from the fit
            self.update()
            return
        if self._grid_mode:
            if self._grid_stage == 1:
                self.update()
            return
        if self._interact == "marquee" and self._marquee is not None:
            self._marquee.setBottomRight(self._to_image(pos))
            self.update()
            return
        if self._interact == "draw" and self._draw_rect is not None:
            self._draw_rect.setBottomRight(self._to_image(pos))
            self.update()
            return
        if self._interact == "move":
            self._do_move(pos)
            return
        if self._interact == "resize":
            self._do_resize(pos)
            return
        self._update_hover(pos)
        self._update_cursor(pos)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._interact == "pan":
            self._interact = None
            self.unsetCursor()
            return
        if self._interact == "marquee":
            self._interact = None
            rids = self._marquee_hits()
            self._marquee = None
            self._selection = set(rids)
            self.rois_selected.emit(list(rids))
            self.update()
            return
        if self._grid_mode:
            self._interact = None
            return
        if self._interact == "draw" and self._draw_rect is not None:
            rect = self._finalize_draw()
            self._draw_rect = None
            self._interact = None
            if rect is not None:
                self.roi_created.emit(rect)
            self.update()
            return
        if self._interact in ("move", "resize"):
            roi = self._active_roi()
            self._interact = None
            self._resize_handle = None
            if roi is not None:
                self.roi_modified.emit(roi.rid, roi.rect)
        self._interact = None

    _ARROWS = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0),
               Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}

    def keyPressEvent(self, e: QKeyEvent) -> None:
        key, mods = e.key(), e.modifiers()
        is_del = key in (Qt.Key_Delete, Qt.Key_Backspace)
        ctrl = bool(mods & Qt.ControlModifier)
        if self._grid_mode and key in (Qt.Key_Return, Qt.Key_Enter):
            self.commit_grid()
        elif self._grid_mode and key == Qt.Key_Escape:
            self.cancel_grid()
        elif self._grid_mode:
            super().keyPressEvent(e)
        elif self._selection and is_del:
            self.rois_delete_requested.emit(list(self._selection))
        elif self._active_rid is not None and is_del:
            self.roi_delete_requested.emit(self._active_rid)
        elif self._selection and key == Qt.Key_Escape:
            self._selection = set()
            self.rois_selected.emit([])
            self.update()
        elif key in self._ARROWS and self._active_rid is not None:
            dx, dy = self._ARROWS[key]
            step = 10 if (mods & Qt.ShiftModifier) else 1
            self._nudge_active(dx * step, dy * step)
        elif ctrl and key == Qt.Key_D and self._active_rid is not None:
            self.roi_duplicate_requested.emit(self._active_rid)
        elif ctrl and key == Qt.Key_A:
            rids = [r.rid for r in self._rois if r.gid == self._active_gid]
            self._selection = set(rids)
            self.rois_selected.emit(rids)
            self.update()
        elif Qt.Key_1 <= key <= Qt.Key_9 and not ctrl:
            self.group_index_requested.emit(key - Qt.Key_1)
        else:
            super().keyPressEvent(e)

    def _nudge_active(self, dx: int, dy: int) -> None:
        roi = self._active_roi()
        if roi is None:
            return
        x, y, w, h = roi.rect
        roi.rect = self._clamp((x + dx, y + dy, w, h))
        self.roi_modified.emit(roi.rid, roi.rect)
        self.update()

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        if self._image is None or e.button() != Qt.LeftButton or self._grid_mode:
            return
        rid = self._roi_body_at(QPointF(e.position()))
        if rid is not None:
            if rid != self._active_rid:
                self._active_rid = rid
                self.roi_selected.emit(rid)
            self.roi_inspect_requested.emit(rid)

    def wheelEvent(self, e: QWheelEvent) -> None:
        if self._image is None:
            return
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_by(factor, QPointF(e.position()))

    def leaveEvent(self, _e) -> None:
        self.cursor_info.emit("")
        if self._hover_rid != -1:
            self._hover_rid = -1
            self.roi_hovered.emit(-1)
            self.update()

    def _update_hover(self, pos: QPointF) -> None:
        rid = self._roi_body_at(pos)
        rid = rid if rid is not None else -1
        if rid != self._hover_rid:
            self._hover_rid = rid
            self.roi_hovered.emit(rid)
            self.update()

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _reset_grid(self) -> None:
        self._grid_stage = 0
        self._grid_tl = None
        self._grid_br = None
        self.grid_ready.emit(False)

    def _emit_cursor(self, pos: QPointF) -> None:
        if self._image is None:
            self.cursor_info.emit("")
            return
        ip = self._to_image(pos)
        x, y = int(np.floor(ip.x())), int(np.floor(ip.y()))
        h, w = self._image.shape[:2]
        if 0 <= x < w and 0 <= y < h:
            self.cursor_info.emit(f"x {x}  y {y}  ·  gray {int(self._image[y, x])}")
        else:
            self.cursor_info.emit("")

    def _do_move(self, pos: QPointF) -> None:
        roi = self._active_roi()
        if roi is None or self._roi_at_press is None:
            return
        delta = self._to_image(pos) - self._to_image(self._drag_start)
        x0, y0, w, h = self._roi_at_press
        roi.rect = self._clamp((int(round(x0 + delta.x())),
                                int(round(y0 + delta.y())), w, h))
        self.update()

    def _do_resize(self, pos: QPointF) -> None:
        roi = self._active_roi()
        if roi is None or self._roi_at_press is None:
            return
        x, y, w, h = self._roi_at_press
        ip = self._to_image(pos)
        left, top, right, bottom = x, y, x + w, y + h
        if self._resize_handle in (0, 3):
            left = ip.x()
        if self._resize_handle in (1, 2):
            right = ip.x()
        if self._resize_handle in (0, 1):
            top = ip.y()
        if self._resize_handle in (2, 3):
            bottom = ip.y()
        nx, ny = int(round(min(left, right))), int(round(min(top, bottom)))
        nw = max(_MIN_ROI, int(round(abs(right - left))))
        nh = max(_MIN_ROI, int(round(abs(bottom - top))))
        roi.rect = self._clamp((nx, ny, nw, nh))
        self.update()

    def _finalize_draw(self) -> Optional[Rect]:
        r = self._draw_rect.normalized()
        w, h = int(round(r.width())), int(round(r.height()))
        if w < _MIN_ROI or h < _MIN_ROI:
            # plain click -> place a box of the configured W×H centred on it
            c = self._to_image(self._drag_start)
            return self._clamp((int(round(c.x() - self._roi_w / 2)),
                                int(round(c.y() - self._roi_h / 2)),
                                self._roi_w, self._roi_h))
        return self._clamp((int(round(r.x())), int(round(r.y())), w, h))

    def _clamp(self, roi: Rect) -> Rect:
        x, y, w, h = roi
        if self._image is None:
            return roi
        ih, iw = self._image.shape[:2]
        w = max(_MIN_ROI, min(w, iw))
        h = max(_MIN_ROI, min(h, ih))
        x = max(0, min(x, iw - w))
        y = max(0, min(y, ih - h))
        return (x, y, w, h)

    def _update_cursor(self, pos: QPointF) -> None:
        if self._image is None:
            self.unsetCursor()
            return
        if self._handle_at(pos) is not None:
            self.setCursor(Qt.SizeFDiagCursor)
        elif self._roi_body_at(pos) is not None:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def resizeEvent(self, _e) -> None:
        if self._pixmap is None or self._interact is not None:
            return
        # set_image() fits against whatever size the widget has at load time,
        # which is the layout's first guess, not the final one — without this
        # the image stays pinned wherever that guess put it
        if self._fitted:
            self.fit()
        else:
            self.update()
