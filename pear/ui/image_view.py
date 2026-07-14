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
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPen,
                           QPixmap, QWheelEvent)
from PySide6.QtWidgets import QWidget

from pear.core.analysis import ROI, Group, grid_between
from pear.ui import theme

Rect = Tuple[int, int, int, int]
_HANDLE = 8
_MIN_ROI = 4
_DEFAULT = 28          # default single-ROI size (px) for a plain click


class ImageView(QWidget):
    roi_created = Signal(object)            # rect (single ROI into active group)
    grid_committed = Signal(object)         # list[rect] (a row×col grid)
    grid_ready = Signal(bool)               # both grid anchors placed
    roi_modified = Signal(int, object)      # rid, rect
    roi_selected = Signal(int)              # rid
    roi_delete_requested = Signal(int)      # rid (Delete key on selected ROI)
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

        self._groups: List[Group] = []
        self._active_gid: Optional[str] = None
        self._rois: List[ROI] = []
        self._active_rid: Optional[int] = None

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
        self._paint_rois(p)
        self._paint_rubberband(p)
        self._paint_grid_preview(p)
        self._paint_hud(p)
        p.end()

    def _paint_rois(self, p: QPainter) -> None:
        for roi in self._rois:
            active_grp = roi.gid == self._active_gid
            selected = roi.rid == self._active_rid
            color = self._gcolor(roi.gid)
            r = self._rect_to_widget(roi.rect)
            fill = QColor(color)
            fill.setAlpha(64 if active_grp else 26)
            stroke = QColor(color)
            stroke.setAlpha(255 if active_grp else 130)
            pen = QPen(stroke, 2.4 if selected else (1.8 if active_grp else 1.2))
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(fill)
            p.drawRect(r)
            val = self._roi_values.get(roi.rid)
            if val is not None:
                self._paint_value(p, r, val)
            if selected and not self._grid_mode:
                self._paint_handles(p, r, color)

    def _paint_value(self, p: QPainter, r: QRectF, text: str) -> None:
        p.setFont(theme.mono_font(9, weight=700))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text)
        cx, cy = r.center().x(), r.center().y()
        bg = QRectF(cx - tw / 2 - 3, cy - fm.height() / 2, tw + 6, fm.height())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(17, 24, 39, 200))
        p.drawRoundedRect(bg, 3, 3)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(bg, Qt.AlignCenter, text)

    def _paint_handles(self, p: QPainter, rect: QRectF, color: QColor) -> None:
        p.setPen(QPen(QColor("#FFFFFF"), 1.4))
        p.setBrush(color)
        for c in self._handle_centers(rect):
            p.drawRect(QRectF(c.x() - _HANDLE / 2, c.y() - _HANDLE / 2,
                              _HANDLE, _HANDLE))

    def _paint_rubberband(self, p: QPainter) -> None:
        if self._draw_rect is None:
            return
        pen = QPen(QColor(theme.AMBER), 2)
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        rn = self._draw_rect.normalized()
        tl = self._to_widget(rn.left(), rn.top())
        p.drawRect(QRectF(tl.x(), tl.y(), rn.width() * self._scale,
                          rn.height() * self._scale))

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
        color = self._gcolor(self._active_gid)
        prev = QColor(color)
        prev.setAlpha(70)
        pen = QPen(color, 1.4)
        pen.setCosmetic(True)
        for i, rect in enumerate(rects):
            r = self._rect_to_widget(rect)
            p.setPen(pen)
            p.setBrush(prev)
            p.drawRect(r)
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
        if self._grid_mode:
            if self._grid_stage == 1:
                self.update()
            return
        if self._interact == "pan":
            self._offset = self._pan_at_press + (pos - self._drag_start)
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
        self._update_cursor(pos)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._interact == "pan":
            self._interact = None
            self.unsetCursor()
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

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if self._grid_mode and e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.commit_grid()
        elif self._grid_mode and e.key() == Qt.Key_Escape:
            self.cancel_grid()
        elif (not self._grid_mode and self._active_rid is not None
              and e.key() in (Qt.Key_Delete, Qt.Key_Backspace)):
            self.roi_delete_requested.emit(self._active_rid)
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e: QWheelEvent) -> None:
        if self._image is None:
            return
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_by(factor, QPointF(e.position()))

    def leaveEvent(self, _e) -> None:
        self.cursor_info.emit("")

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
        if self._pixmap is not None and self._interact is None:
            self.update()
