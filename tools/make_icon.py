#!/usr/bin/env python3
"""Draw PEAR's icon and write a multi-size Windows ``.ico``.

Why generated instead of committed
----------------------------------
The whole repo travels to the offline machine as **one plain-text file**
(``bundle/pear_bundle.py``), and that bundle refuses anything that is not
LF + UTF-8 text — a binary ``.ico`` in ``git ls-files`` would break it. So the
icon ships as the few dozen lines of QPainter below and is drawn on the
machine that installs PEAR, where PySide6 already exists.

The mark
--------
A measurement grid: nine cells across the heat ramp the app uses (blue →
amber → red), one of them ringed in white — a ROI on a field. That is what
PEAR does, and it survives being shrunk to 16 px, which a pear silhouette or
a wordmark would not.

    python tools/make_icon.py                 # -> pear.ico (+ pear_icon.png)
    python tools/make_icon.py --out D:\\x.ico
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: The sizes Windows actually asks for: 16 in the tray and small list views,
#: 32 on the desktop, 48 in medium icons, 256 in the extra-large view.
SIZES = (16, 24, 32, 48, 64, 128, 256)

INK = "#111827"          # tile: the image stage's own black, softened
RAMP = ("#2563EB", "#4B72C8", "#8E8AA0", "#F59E0B", "#EA7A0B", "#DC2626")


def _cell_colors(n: int) -> List[str]:
    """Nine cells sampled across the ramp — a field with a gradient in it."""
    order = (0, 1, 3, 1, 3, 4, 2, 4, 5)
    return [RAMP[order[i % len(order)]] for i in range(n)]


def draw(size: int):
    """The icon at one size, as a QImage."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen

    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)

    pad = max(1.0, size * 0.06)
    tile = QRectF(pad, pad, size - 2 * pad, size - 2 * pad)
    radius = size * 0.18
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(INK))
    p.drawRoundedRect(tile, radius, radius)

    # the grid of measured cells
    inset = size * 0.13
    grid = tile.adjusted(inset, inset, -inset, -inset)
    gap = 0.0 if size < 32 else max(1.0, size * 0.02)
    cw = (grid.width() - gap * 2) / 3.0
    ch = (grid.height() - gap * 2) / 3.0
    colors = _cell_colors(9)
    cell_r = 0.0 if size < 32 else size * 0.04
    for i, color in enumerate(colors):
        r, c = divmod(i, 3)
        rect = QRectF(grid.left() + c * (cw + gap), grid.top() + r * (ch + gap),
                      cw, ch)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        if cell_r:
            p.drawRoundedRect(rect, cell_r, cell_r)
        else:
            p.drawRect(rect)

    # the ROI: one cell picked out. Below 24 px a ring is mud, so the cell is
    # simply left brighter than its neighbours by the ramp itself.
    if size >= 24:
        r, c = 1, 1
        rect = QRectF(grid.left() + c * (cw + gap), grid.top() + r * (ch + gap),
                      cw, ch)
        pen = QPen(QColor("#FFFFFF"), max(1.0, size * 0.028))
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        grow = size * 0.012
        p.drawRect(rect.adjusted(-grow, -grow, grow, grow))
    p.end()
    return img


def _png_bytes(img) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    if not img.save(buf, "PNG"):
        raise RuntimeError("Qt could not encode the icon as PNG")
    buf.close()
    return bytes(ba)


def build_ico(sizes=SIZES) -> bytes:
    """Assemble a Windows ``.ico`` from PNG-compressed entries.

    Qt writes PNG but not ICO, and ICO is a header plus payloads — so the
    container is written here rather than dragging in a second imaging
    library that the offline machine would then have to install.
    """
    payloads = [_png_bytes(draw(s)) for s in sizes]
    out = bytearray(struct.pack("<HHH", 0, 1, len(sizes)))
    offset = 6 + 16 * len(sizes)
    for size, data in zip(sizes, payloads):
        dim = 0 if size >= 256 else size          # 0 means 256 in an ICO
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                           len(data), offset)
        offset += len(data)
    for data in payloads:
        out += data
    return bytes(out)


def write_icon(path: str, png_path: str = "") -> str:
    """Write the ``.ico`` (and optionally a PNG preview). Returns the path."""
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QGuiApplication([])                       # QPainter needs a GUI app
    data = build_ico()
    with open(path, "wb") as fh:
        fh.write(data)
    if png_path:
        draw(256).save(png_path, "PNG")
    return path


def main(argv=None) -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description="Draw PEAR's Windows icon.")
    ap.add_argument("--out", default=os.path.join(root, "pear.ico"))
    ap.add_argument("--png", default="", help="also write a PNG preview here")
    args = ap.parse_args(argv)
    path = write_icon(args.out, args.png)
    print(f"{path}  ({os.path.getsize(path)} bytes, "
          f"{len(SIZES)} sizes: {', '.join(str(s) for s in SIZES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
