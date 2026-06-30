"""Image stage: load, zoom/pan, draw/move/resize ROIs, and overlays.

A hand-painted canvas (QWidget + QPainter). It owns no analysis logic; it
emits intent signals (region created / modified / selected) and renders
whatever regions, period grid, and outlier markers it is given.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap,
                           QWheelEvent)
from PySide6.QtWidgets import QWidget

from pear.core.analysis import PeriodInfo, Region, outlier_instances
from pear.ui import theme

Rect = Tuple[int, int, int, int]

_HANDLE = 8           # corner-handle size in widget pixels
_MIN_ROI = 4          # minimum ROI edge in image pixels


class ImageView(QWidget):
    """Interactive SEM image stage."""

    region_created = Signal(object)            # roi Rect
    region_modified = Signal(int, object)      # rid, roi Rect
    region_selected = Signal(int)              # rid
    cell_tag_toggled = Signal(int)             # active-region instance index
    draw_without_region = Signal()             # dragged with no active region

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._image: Optional[np.ndarray] = None
        self._qimage: Optional[QImage] = None
        self._pixmap: Optional[QPixmap] = None
        self._scale = 1.0
        self._offset = QPointF(0, 0)

        self._period: Optional[PeriodInfo] = None
        self._regions: List[Region] = []
        self._active_rid: Optional[int] = None
        self._labelled = False     # display mode: labelled compare vs unsup.
        self._tag_mode = False     # clicking a cell toggles its target tag

        # interaction state
        self._mode: Optional[str] = None   # "draw" | "move" | "resize" | "pan"
        self._drag_start = QPointF()
        self._draw_rect: Optional[QRectF] = None  # in image coords
        self._resize_handle: Optional[int] = None
        self._roi_at_press: Optional[Rect] = None
        self._pan_at_press = QPointF()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def set_image(self, image: np.ndarray) -> None:
        """Set the grayscale image (uint8 2-D) and fit it to the view."""
        self._image = np.ascontiguousarray(image)
        h, w = image.shape[:2]
        self._qimage = QImage(self._image.data, w, h, w, QImage.Format_Grayscale8)
        self._pixmap = QPixmap.fromImage(self._qimage)
        self._period = None
        self.fit()

    def set_period(self, period: Optional[PeriodInfo]) -> None:
        self._period = period
        self.update()

    def set_regions(self, regions: List[Region], active_rid: Optional[int]) -> None:
        self._regions = regions
        self._active_rid = active_rid
        self.update()

    def set_display_mode(self, labelled: bool) -> None:
        self._labelled = labelled
        if not labelled:
            self._tag_mode = False
        self.update()

    def set_tag_mode(self, on: bool) -> None:
        self._tag_mode = bool(on)
        self.update()

    def has_image(self) -> bool:
        return self._image is not None

    def fit(self) -> None:
        """Scale the image to fit the viewport, centered."""
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

    # ------------------------------------------------------------------ #
    # coordinate transforms
    # ------------------------------------------------------------------ #
    def _to_widget(self, x: float, y: float) -> QPointF:
        return QPointF(self._offset.x() + x * self._scale,
                       self._offset.y() + y * self._scale)

    def _to_image(self, p: QPointF) -> QPointF:
        return QPointF((p.x() - self._offset.x()) / self._scale,
                       (p.y() - self._offset.y()) / self._scale)

    def _rect_to_widget(self, r: Rect) -> QRectF:
        x, y, w, h = r
        tl = self._to_widget(x, y)
        return QRectF(tl.x(), tl.y(), w * self._scale, h * self._scale)

    def _qrectf_to_widget(self, qr: QRectF) -> QRectF:
        """Map a QRectF given in image coordinates to widget coordinates."""
        tl = self._to_widget(qr.left(), qr.top())
        return QRectF(tl.x(), tl.y(),
                      qr.width() * self._scale, qr.height() * self._scale)

    # ------------------------------------------------------------------ #
    # painting
    # ------------------------------------------------------------------ #
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.STAGE))

        if self._pixmap is None:
            self._paint_placeholder(p)
            p.end()
            return

        target = QRectF(self._offset.x(), self._offset.y(),
                        self._pixmap.width() * self._scale,
                        self._pixmap.height() * self._scale)
        p.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))

        self._paint_grid(p)
        self._paint_regions(p)
        self._paint_draw_rubberband(p)
        p.end()

    def _paint_placeholder(self, p: QPainter) -> None:
        p.setPen(QColor(theme.FAINT))
        p.drawText(self.rect(), Qt.AlignCenter,
                   "Load an 8-bit grayscale image to begin.")

    def _paint_grid(self, p: QPainter) -> None:
        # The cell grid is always drawn once a period exists.
        if self._period is None or self._image is None:
            return
        px, py = self._period.px, self._period.py
        if px < 1 or py < 1:
            return
        h, w = self._image.shape[:2]
        ox, oy = self._period.origin
        grid = QColor(*theme.GRID_RGBA)
        pen = QPen(grid, 1)
        pen.setCosmetic(True)
        p.setPen(pen)
        x = ox
        while x <= w:
            a = self._to_widget(x, 0)
            b = self._to_widget(x, h)
            p.drawLine(a, b)
            x += px
        y = oy
        while y <= h:
            a = self._to_widget(0, y)
            b = self._to_widget(w, y)
            p.drawLine(a, b)
            y += py

    def _paint_regions(self, p: QPainter) -> None:
        for region in self._regions:
            active = region.rid == self._active_rid
            base = QColor(region.color)

            # Instances: a soft glow underlay + a crisp stroke, with a
            # faint tint fill so the cells read clearly on the dark stage.
            glow = QColor(base)
            glow.setAlpha(70 if active else 30)
            stroke = QColor(base)
            stroke.setAlpha(255 if active else 120)
            fill = QColor(base)
            fill.setAlpha(40 if active else 16)

            glow_pen = QPen(glow, 5 if active else 3)
            glow_pen.setCosmetic(True)
            crisp_pen = QPen(stroke, 2 if active else 1)
            crisp_pen.setCosmetic(True)

            for inst in region.instances:
                r = self._rect_to_widget(inst)
                p.setPen(glow_pen)
                p.setBrush(Qt.NoBrush)
                p.drawRect(r)
                p.setPen(crisp_pen)
                p.setBrush(fill)
                p.drawRect(r)

            # The reference ROI itself, emphasized with a bright dashed edge.
            ref_rect = self._rect_to_widget(region.roi)
            ref_pen = QPen(QColor(base), 2.4)
            ref_pen.setCosmetic(True)
            ref_pen.setStyle(Qt.SolidLine if active else Qt.DashLine)
            p.setPen(ref_pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(ref_rect)

            if self._labelled:
                self._paint_targets(p, region, active)
            elif active:
                self._paint_markers(p, region)

            if active and not self._tag_mode:
                self._paint_handles(p, ref_rect, QColor(base))

    def _paint_handles(self, p: QPainter, rect: QRectF, color: QColor) -> None:
        p.setPen(QPen(QColor(theme.PANEL), 1.5))
        p.setBrush(color)
        for c in self._handle_centers(rect):
            p.drawRect(QRectF(c.x() - _HANDLE / 2, c.y() - _HANDLE / 2,
                              _HANDLE, _HANDLE))

    def _paint_markers(self, p: QPainter, region: Region) -> None:
        # Amber outlier markers for the active region + selected attribute.
        # A glow + bright stroke + corner ticks make them read as "look
        # here" without implying a verdict.
        bright = QColor("#FFC44D")
        glow = QColor(theme.FLAG)
        glow.setAlpha(90)
        fill = QColor(theme.FLAG)
        fill.setAlpha(55)
        for inst in outlier_instances(region):
            r = self._rect_to_widget(inst)
            gpen = QPen(glow, 6)
            gpen.setCosmetic(True)
            p.setPen(gpen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(r)
            spen = QPen(bright, 2.4)
            spen.setCosmetic(True)
            p.setPen(spen)
            p.setBrush(fill)
            p.drawRect(r)
            self._paint_corner_ticks(p, r, bright)

    def _paint_targets(self, p: QPainter, region: Region, active: bool) -> None:
        # Labelled compare: tagged target cells get a bold filled overlay;
        # the rest of the region's instances read as reference (the outline
        # already drawn). Target uses the region colour, brightened.
        target = QColor("#FF3B30") if active else QColor("#FF7A70")
        fill = QColor(target)
        fill.setAlpha(70)
        pen = QPen(target, 2.6 if active else 1.6)
        pen.setCosmetic(True)
        for i in sorted(region.target_idx):
            if 0 <= i < len(region.instances):
                r = self._rect_to_widget(region.instances[i])
                p.setPen(pen)
                p.setBrush(fill)
                p.drawRect(r)
                if active:
                    self._paint_corner_ticks(p, r, target)

    @staticmethod
    def _paint_corner_ticks(p: QPainter, r: QRectF, color: QColor) -> None:
        t = max(4.0, min(10.0, r.width() * 0.22))
        pen = QPen(color, 2.6)
        pen.setCosmetic(True)
        p.setPen(pen)
        for cx, cy, sx, sy in (
            (r.left(), r.top(), 1, 1), (r.right(), r.top(), -1, 1),
            (r.left(), r.bottom(), 1, -1), (r.right(), r.bottom(), -1, -1),
        ):
            p.drawLine(cx, cy, cx + sx * t, cy)
            p.drawLine(cx, cy, cx, cy + sy * t)

    def _paint_draw_rubberband(self, p: QPainter) -> None:
        if self._draw_rect is None:
            return
        pen = QPen(QColor(theme.ACCENT_BRIGHT), 2)
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(self._qrectf_to_widget(self._norm_rect(self._draw_rect)))

    # ------------------------------------------------------------------ #
    # hit testing
    # ------------------------------------------------------------------ #
    @staticmethod
    def _handle_centers(rect: QRectF) -> List[QPointF]:
        return [QPointF(rect.left(), rect.top()),
                QPointF(rect.right(), rect.top()),
                QPointF(rect.right(), rect.bottom()),
                QPointF(rect.left(), rect.bottom())]

    def _active_region(self) -> Optional[Region]:
        for r in self._regions:
            if r.rid == self._active_rid:
                return r
        return None

    def _handle_at(self, pos: QPointF) -> Optional[int]:
        region = self._active_region()
        if region is None:
            return None
        rect = self._rect_to_widget(region.roi)
        for i, c in enumerate(self._handle_centers(rect)):
            if abs(pos.x() - c.x()) <= _HANDLE and abs(pos.y() - c.y()) <= _HANDLE:
                return i
        return None

    def _region_body_at(self, pos: QPointF) -> Optional[int]:
        # Topmost region whose reference ROI contains pos (active first).
        ordered = sorted(self._regions,
                         key=lambda r: r.rid != self._active_rid)
        for r in ordered:
            if self._rect_to_widget(r.roi).contains(pos):
                return r.rid
        return None

    def _instance_at(self, pos: QPointF) -> Optional[int]:
        """Index of the active region's instance under ``pos`` (or None)."""
        region = self._active_region()
        if region is None:
            return None
        for i, inst in enumerate(region.instances):
            if self._rect_to_widget(inst).contains(pos):
                return i
        return None

    # ------------------------------------------------------------------ #
    # mouse / wheel
    # ------------------------------------------------------------------ #
    def mousePressEvent(self, e: QMouseEvent) -> None:
        pos = QPointF(e.position())
        if e.button() in (Qt.MiddleButton, Qt.RightButton):
            self._mode = "pan"
            self._drag_start = pos
            self._pan_at_press = QPointF(self._offset)
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton or self._image is None:
            return

        # Tag mode: a click on an active-region cell toggles its target tag.
        if self._tag_mode:
            idx = self._instance_at(pos)
            if idx is not None:
                self.cell_tag_toggled.emit(idx)
            return

        handle = self._handle_at(pos)
        if handle is not None:
            region = self._active_region()
            self._mode = "resize"
            self._resize_handle = handle
            self._roi_at_press = region.roi
            self._drag_start = pos
            return

        body_rid = self._region_body_at(pos)
        if body_rid is not None:
            if body_rid != self._active_rid:
                self._active_rid = body_rid
                self.region_selected.emit(body_rid)
                self.update()
                return
            region = self._active_region()
            self._mode = "move"
            self._roi_at_press = region.roi
            self._drag_start = pos
            return

        # Empty space -> draw / redraw the ACTIVE region's ROI. New regions
        # are created with the "+ Add region" button, not by drawing.
        if self._active_rid is None:
            self.draw_without_region.emit()
            return
        ip = self._to_image(pos)
        self._mode = "draw"
        self._draw_rect = QRectF(ip, ip)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        pos = QPointF(e.position())
        if self._mode == "pan":
            delta = pos - self._drag_start
            self._offset = self._pan_at_press + delta
            self.update()
            return
        if self._mode == "draw" and self._draw_rect is not None:
            self._draw_rect.setBottomRight(self._to_image(pos))
            self.update()
            return
        if self._mode == "move":
            self._do_move(pos)
            return
        if self._mode == "resize":
            self._do_resize(pos)
            return
        self._update_cursor(pos)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._mode == "pan":
            self._mode = None
            self.unsetCursor()
            return
        if self._mode == "draw" and self._draw_rect is not None:
            roi = self._finalize_draw()
            self._draw_rect = None
            self._mode = None
            if roi is not None and self._active_rid is not None:
                # The drawn rectangle (re)defines the active region's ROI.
                self.region_modified.emit(self._active_rid, roi)
            self.update()
            return
        if self._mode in ("move", "resize"):
            region = self._active_region()
            self._mode = None
            self._resize_handle = None
            if region is not None:
                self.region_modified.emit(region.rid, region.roi)
        self._mode = None

    def wheelEvent(self, e: QWheelEvent) -> None:
        if self._image is None:
            return
        anchor = QPointF(e.position())
        img_anchor = self._to_image(anchor)
        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self._scale = float(np.clip(self._scale * factor, 0.05, 40.0))
        # Keep the point under the cursor stationary.
        self._offset = QPointF(anchor.x() - img_anchor.x() * self._scale,
                               anchor.y() - img_anchor.y() * self._scale)
        self.update()

    # ------------------------------------------------------------------ #
    # interaction helpers
    # ------------------------------------------------------------------ #
    def _cell_footprint(self) -> Tuple[int, int]:
        if self._period is not None:
            return self._period.px, self._period.py
        if self._image is not None:
            h, w = self._image.shape[:2]
            return w, h
        return 1, 1

    def _do_move(self, pos: QPointF) -> None:
        region = self._active_region()
        if region is None or self._roi_at_press is None:
            return
        delta = self._to_image(pos) - self._to_image(self._drag_start)
        x0, y0, w, h = self._roi_at_press
        nx = int(round(x0 + delta.x()))
        ny = int(round(y0 + delta.y()))
        region.roi = self._clamp_roi((nx, ny, w, h))
        self.update()

    def _do_resize(self, pos: QPointF) -> None:
        region = self._active_region()
        if region is None or self._roi_at_press is None:
            return
        x, y, w, h = self._roi_at_press
        ip = self._to_image(pos)
        left, top, right, bottom = x, y, x + w, y + h
        if self._resize_handle in (0, 3):       # left edge
            left = ip.x()
        if self._resize_handle in (1, 2):       # right edge
            right = ip.x()
        if self._resize_handle in (0, 1):       # top edge
            top = ip.y()
        if self._resize_handle in (2, 3):       # bottom edge
            bottom = ip.y()
        nx, ny = int(round(min(left, right))), int(round(min(top, bottom)))
        nw = max(_MIN_ROI, int(round(abs(right - left))))
        nh = max(_MIN_ROI, int(round(abs(bottom - top))))
        region.roi = self._clamp_roi((nx, ny, nw, nh))
        self.update()

    def _finalize_draw(self) -> Optional[Rect]:
        r = self._norm_rect(self._draw_rect)
        x, y, w, h = (int(round(r.x())), int(round(r.y())),
                      int(round(r.width())), int(round(r.height())))
        if w < _MIN_ROI or h < _MIN_ROI:
            return None
        return self._clamp_roi((x, y, w, h))

    def _clamp_roi(self, roi: Rect) -> Rect:
        """Clamp so the ROI stays within one cell footprint and the image."""
        x, y, w, h = roi
        if self._image is None:
            return roi
        ih, iw = self._image.shape[:2]
        cpx, cpy = self._cell_footprint()
        w = max(_MIN_ROI, min(w, cpx, iw))
        h = max(_MIN_ROI, min(h, cpy, ih))
        x = max(0, min(x, iw - w))
        y = max(0, min(y, ih - h))
        # Keep the ROI inside a single cell: it must not straddle a cell
        # boundary, or every instance would sample neighbouring-cell content
        # and the golden sub-cell (and C2C attributes) would drop out.
        if self._period is not None:
            ox, oy = self._period.origin
            x = self._contain_in_cell(x, w, cpx, ox, iw)
            y = self._contain_in_cell(y, h, cpy, oy, ih)
        return (x, y, w, h)

    @staticmethod
    def _contain_in_cell(pos: int, size: int, period: int,
                         origin: int, limit: int) -> int:
        """Shift ``pos`` so a ``size``-wide ROI fits within its cell."""
        if size >= period:
            return pos
        local = (pos - origin) % period
        if local + size > period:
            pos -= (local + size - period)   # slide left to the cell edge
        return max(0, min(pos, limit - size))

    @staticmethod
    def _norm_rect(r: QRectF) -> QRectF:
        return r.normalized()

    def _update_cursor(self, pos: QPointF) -> None:
        if self._image is None:
            self.unsetCursor()
            return
        if self._tag_mode:
            self.setCursor(Qt.PointingHandCursor
                           if self._instance_at(pos) is not None
                           else Qt.ArrowCursor)
            return
        if self._handle_at(pos) is not None:
            self.setCursor(Qt.SizeFDiagCursor)
        elif self._region_body_at(pos) == self._active_rid and \
                self._active_rid is not None:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def resizeEvent(self, _e) -> None:
        # Keep a freshly loaded image fitted until the user interacts.
        if self._pixmap is not None and self._mode is None:
            self.update()
