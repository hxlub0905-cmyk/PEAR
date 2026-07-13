"""Image stage: zoom/pan, paint cells into groups, draw/move/resize ROIs.

A hand-painted canvas. It owns no analysis logic; it emits intent signals
and renders whatever groups, ROIs, period grid, and mode it is given.

Two interaction modes:
  * ``"group"`` — click / drag cells to paint them into the active group.
  * ``"roi"``   — drag on empty space to draw an ROI; drag a handle to
                  resize; drag the body to move. ROIs are drawn crisply in
                  their home cell and faintly echoed in every other cell.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap,
                           QWheelEvent)
from PySide6.QtWidgets import QWidget

from pear.core.analysis import (ROI, Group, PeriodInfo, TARGET, cell_at_point,
                                grid_dims)
from pear.ui import theme

Rect = Tuple[int, int, int, int]

_HANDLE = 8
_MIN_ROI = 4


class ImageView(QWidget):
    """Interactive SEM image stage."""

    cell_paint = Signal(int, int, bool)     # row, col, is_drag
    roi_created = Signal(object)            # rect
    roi_modified = Signal(int, object)      # rid, rect
    roi_selected = Signal(int)              # rid
    cursor_info = Signal(str)
    zoom_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._image: Optional[np.ndarray] = None
        self._pixmap: Optional[QPixmap] = None
        self._scale = 1.0
        self._offset = QPointF(0, 0)

        self._period: Optional[PeriodInfo] = None
        self._groups: List[Group] = []
        self._active_gid: Optional[str] = None
        self._rois: List[ROI] = []
        self._active_rid: Optional[int] = None
        self._mode = "group"        # "group" | "roi"
        self._split_tr = False

        self._hover_cell: Optional[Tuple[int, int]] = None
        self._interact: Optional[str] = None    # draw|move|resize|pan|paint
        self._drag_start = QPointF()
        self._draw_rect: Optional[QRectF] = None
        self._resize_handle: Optional[int] = None
        self._roi_at_press: Optional[Rect] = None
        self._pan_at_press = QPointF()
        self._last_paint: Optional[Tuple[int, int]] = None

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def set_image(self, image: np.ndarray) -> None:
        self._image = np.ascontiguousarray(image)
        h, w = image.shape[:2]
        qimg = QImage(self._image.data, w, h, w, QImage.Format_Grayscale8)
        self._pixmap = QPixmap.fromImage(qimg.copy())
        self._period = None
        self.fit()

    def set_period(self, period: Optional[PeriodInfo]) -> None:
        self._period = period
        self.update()

    def set_groups(self, groups, active_gid) -> None:
        self._groups = groups
        self._active_gid = active_gid
        self.update()

    def set_rois(self, rois, active_rid) -> None:
        self._rois = rois
        self._active_rid = active_rid
        self.update()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.update()

    def set_split_tr(self, on: bool) -> None:
        self._split_tr = bool(on)
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
        self.update()
        self.zoom_changed.emit(self._scale)

    def zoom_by(self, factor: float, anchor: Optional[QPointF] = None) -> None:
        if self._image is None:
            return
        if anchor is None:
            anchor = QPointF(self.width() / 2.0, self.height() / 2.0)
        ia = self._to_image(anchor)
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
        self._paint_grid(p)
        self._paint_groups(p)
        self._paint_rois(p)
        self._paint_hover(p)
        self._paint_rubberband(p)
        p.end()

    def _paint_grid(self, p: QPainter) -> None:
        if self._period is None or self._image is None:
            return
        px, py = self._period.px, self._period.py
        if px < 1 or py < 1:
            return
        h, w = self._image.shape[:2]
        ox, oy = self._period.origin
        pen = QPen(QColor(*theme.GRID_RGBA), 1)
        pen.setCosmetic(True)
        p.setPen(pen)
        x = ox
        while x <= w:
            a, b = self._to_widget(x, 0), self._to_widget(x, h)
            p.drawLine(a, b)
            x += px
        y = oy
        while y <= h:
            a, b = self._to_widget(0, y), self._to_widget(w, y)
            p.drawLine(a, b)
            y += py

    def _paint_groups(self, p: QPainter) -> None:
        if self._period is None:
            return
        px, py = self._period.px, self._period.py
        ox, oy = self._period.origin
        for g in self._groups:
            active = g.gid == self._active_gid
            base = QColor(g.color)
            fill = QColor(base)
            fill.setAlpha(60 if active else 34)
            stroke = QColor(base)
            stroke.setAlpha(255 if active else 150)
            pen = QPen(stroke, 2 if active else 1.4)
            pen.setCosmetic(True)
            for (r, c) in g.cells:
                rect = self._rect_to_widget((ox + c * px, oy + r * py, px, py))
                p.setPen(Qt.NoPen)
                p.setBrush(fill)
                p.drawRect(rect.adjusted(1, 1, -1, -1))
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawRect(rect.adjusted(1, 1, -1, -1))
            # badge on the first (top-left) painted cell
            if g.cells:
                r0, c0 = min(g.cells)
                br = self._rect_to_widget((ox + c0 * px, oy + r0 * py, px, py))
                self._badge(p, br.topLeft(), g.gid, base)

    def _badge(self, p: QPainter, tl: QPointF, text: str, color: QColor) -> None:
        box = QRectF(tl.x() + 2, tl.y() + 2, 15, 13)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRect(box)
        p.setPen(QColor("#FFFFFF"))
        p.setFont(theme.mono_font(7, weight=700))
        p.drawText(box, Qt.AlignCenter, text)

    def _roi_home(self, roi: ROI) -> Tuple[int, int, int, int, int, int]:
        """(dx, dy, w, h, home_col, home_row) for an ROI's reference rect."""
        px, py = self._period.px, self._period.py
        ox, oy = self._period.origin
        x, y, w, h = roi.rect
        dx, dy = (x - ox) % px, (y - oy) % py
        return dx, dy, w, h, (x - ox) // px, (y - oy) // py

    def _paint_rois(self, p: QPainter) -> None:
        if self._period is None or self._image is None:
            return
        px, py = self._period.px, self._period.py
        ox, oy = self._period.origin
        rows, cols = grid_dims(self._image.shape, self._period)
        for roi in self._rois:
            color = self._roi_color(roi)
            dx, dy, w, h, hc, hr = self._roi_home(roi)
            # faint echoes in every cell
            echo = QColor(color)
            echo.setAlpha(46)
            epen = QPen(echo, 1)
            epen.setCosmetic(True)
            p.setPen(epen)
            p.setBrush(Qt.NoBrush)
            for r in range(rows):
                for c in range(cols):
                    if r == hr and c == hc:
                        continue
                    p.drawRect(self._rect_to_widget(
                        (ox + c * px + dx, oy + r * py + dy, w, h)))
            # crisp home rect
            active = roi.rid == self._active_rid
            home = self._rect_to_widget(roi.rect)
            pen = QPen(color, 2.4 if active else 1.6)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(home)
            if self._split_tr and roi.role in (TARGET, "reference"):
                self._badge(p, home.topLeft(),
                            "T" if roi.role == TARGET else "R", color)
            if self._mode == "roi" and active:
                self._paint_handles(p, home, color)

    def _roi_color(self, roi: ROI) -> QColor:
        return QColor(roi.color)

    def _paint_handles(self, p: QPainter, rect: QRectF, color: QColor) -> None:
        p.setPen(QPen(QColor("#FFFFFF"), 1.4))
        p.setBrush(color)
        for c in self._handle_centers(rect):
            p.drawRect(QRectF(c.x() - _HANDLE / 2, c.y() - _HANDLE / 2,
                              _HANDLE, _HANDLE))

    def _paint_hover(self, p: QPainter) -> None:
        if self._hover_cell is None or self._period is None:
            return
        r, c = self._hover_cell
        px, py = self._period.px, self._period.py
        ox, oy = self._period.origin
        rect = self._rect_to_widget((ox + c * px, oy + r * py, px, py))
        pen = QPen(QColor(255, 255, 255, 200), 1.4)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect.adjusted(1, 1, -1, -1))

    def _paint_rubberband(self, p: QPainter) -> None:
        if self._draw_rect is None:
            return
        pen = QPen(QColor(theme.AMBER), 2)
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        r = self._draw_rect.normalized()
        tl = self._to_widget(r.left(), r.top())
        p.drawRect(QRectF(tl.x(), tl.y(), r.width() * self._scale,
                          r.height() * self._scale))

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
        ordered = sorted(self._rois, key=lambda r: r.rid != self._active_rid)
        for r in ordered:
            if self._rect_to_widget(r.rect).contains(pos):
                return r.rid
        return None

    def _cell_at(self, pos: QPointF) -> Optional[Tuple[int, int]]:
        if self._period is None or self._image is None:
            return None
        ip = self._to_image(pos)
        return cell_at_point(self._period, int(np.floor(ip.x())),
                             int(np.floor(ip.y())), self._image.shape)

    # ------------------------------------------------------------------ #
    # mouse / wheel
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

        if self._mode == "group":
            cell = self._cell_at(pos)
            if cell is not None:
                self._interact = "paint"
                self._last_paint = cell
                self.cell_paint.emit(cell[0], cell[1], False)
            return

        # ROI mode
        handle = self._handle_at(pos)
        if handle is not None:
            roi = self._active_roi()
            self._interact = "resize"
            self._resize_handle = handle
            self._roi_at_press = roi.rect
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
        self._draw_rect = QRectF(ip, ip)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        pos = QPointF(e.position())
        self._emit_cursor(pos)
        if self._interact == "pan":
            self._offset = self._pan_at_press + (pos - self._drag_start)
            self.update()
            return
        if self._interact == "paint":
            cell = self._cell_at(pos)
            if cell is not None and cell != self._last_paint:
                self._last_paint = cell
                self.cell_paint.emit(cell[0], cell[1], True)
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
        # idle hover
        self._hover_cell = self._cell_at(pos)
        self._update_cursor(pos)
        self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._interact == "pan":
            self._interact = None
            self.unsetCursor()
            return
        if self._interact == "paint":
            self._interact = None
            self._last_paint = None
            return
        if self._interact == "draw" and self._draw_rect is not None:
            roi = self._finalize_draw()
            self._draw_rect = None
            self._interact = None
            if roi is not None:
                self.roi_created.emit(roi)
            self.update()
            return
        if self._interact in ("move", "resize"):
            roi = self._active_roi()
            self._interact = None
            self._resize_handle = None
            if roi is not None:
                self.roi_modified.emit(roi.rid, roi.rect)
        self._interact = None

    def wheelEvent(self, e: QWheelEvent) -> None:
        if self._image is None:
            return
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_by(factor, QPointF(e.position()))

    def leaveEvent(self, _e) -> None:
        self._hover_cell = None
        self.cursor_info.emit("")
        self.update()

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _emit_cursor(self, pos: QPointF) -> None:
        if self._image is None:
            self.cursor_info.emit("")
            return
        ip = self._to_image(pos)
        x, y = int(np.floor(ip.x())), int(np.floor(ip.y()))
        h, w = self._image.shape[:2]
        if 0 <= x < w and 0 <= y < h:
            s = f"x {x}  y {y}  ·  gray {int(self._image[y, x])}"
            cell = self._cell_at(pos)
            if cell is not None:
                s += f"  ·  cell (r{cell[0]}, c{cell[1]})"
            self.cursor_info.emit(s)
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
        x, y, w, h = (int(round(r.x())), int(round(r.y())),
                      int(round(r.width())), int(round(r.height())))
        if w < _MIN_ROI or h < _MIN_ROI:
            return None
        return self._clamp((x, y, w, h))

    def _clamp(self, roi: Rect) -> Rect:
        x, y, w, h = roi
        if self._image is None:
            return roi
        ih, iw = self._image.shape[:2]
        cpx, cpy = (self._period.px, self._period.py) if self._period else (iw, ih)
        w = max(_MIN_ROI, min(w, cpx, iw))
        h = max(_MIN_ROI, min(h, cpy, ih))
        x = max(0, min(x, iw - w))
        y = max(0, min(y, ih - h))
        return (x, y, w, h)

    def _update_cursor(self, pos: QPointF) -> None:
        if self._image is None:
            self.unsetCursor()
            return
        if self._mode == "group":
            self.setCursor(Qt.PointingHandCursor
                           if self._cell_at(pos) is not None else Qt.ArrowCursor)
            return
        if self._handle_at(pos) is not None:
            self.setCursor(Qt.SizeFDiagCursor)
        elif self._roi_body_at(pos) is not None:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def resizeEvent(self, _e) -> None:
        if self._pixmap is not None and self._interact is None:
            self.update()
