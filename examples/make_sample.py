"""Synthetic sample generator.

Writes ``sample_field.png``: a field of identical repeating cells, each a
noisy background with a bright feature block, plus a few injected
"outlier" cells whose feature is dimmer and noisier. Real fab imagery
cannot be bundled; this lets PEAR be exercised end-to-end without it.

Run: ``python examples/make_sample.py``
"""

from __future__ import annotations

import os
from typing import List, Tuple

import cv2
import numpy as np

# Field geometry.
N_COLS, N_ROWS = 12, 9
CELL_W, CELL_H = 64, 52
BG_LEVEL = 70
FEATURE_LEVEL = 185
BG_NOISE = 6.0
FEATURE_NOISE = 5.0

# Injected outlier cells (col, row).
OUTLIERS: List[Tuple[int, int]] = [(2, 1), (7, 3), (4, 6), (10, 7)]


def _make_cell(rng: np.random.Generator, outlier: bool) -> np.ndarray:
    """One cell: noisy background + a centered bright feature block."""
    cell = rng.normal(BG_LEVEL, BG_NOISE, size=(CELL_H, CELL_W))
    # Feature block occupies the central region of the cell.
    fy0, fy1 = CELL_H // 4, CELL_H * 3 // 4
    fx0, fx1 = CELL_W // 4, CELL_W * 3 // 4
    if outlier:
        level, noise = FEATURE_LEVEL - 70, FEATURE_NOISE * 3.0
    else:
        level, noise = FEATURE_LEVEL, FEATURE_NOISE
    fh, fw = fy1 - fy0, fx1 - fx0
    cell[fy0:fy1, fx0:fx1] = rng.normal(level, noise, size=(fh, fw))
    return np.clip(cell, 0, 255)


def make_field(seed: int = 7) -> np.ndarray:
    """Build the full synthetic field as a uint8 grayscale image."""
    rng = np.random.default_rng(seed)
    out = np.zeros((N_ROWS * CELL_H, N_COLS * CELL_W), dtype=np.float64)
    outlier_set = set(OUTLIERS)
    for row in range(N_ROWS):
        for col in range(N_COLS):
            cell = _make_cell(rng, (col, row) in outlier_set)
            y0, x0 = row * CELL_H, col * CELL_W
            out[y0:y0 + CELL_H, x0:x0 + CELL_W] = cell
    return np.clip(out, 0, 255).astype(np.uint8)


def main() -> None:
    img = make_field()
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "sample_field.png")
    cv2.imwrite(path, img)
    print(f"wrote {path}  ({img.shape[1]}x{img.shape[0]} px, "
          f"period {CELL_W}x{CELL_H})")
    print("injected outlier cells (col, row):")
    for (c, r) in OUTLIERS:
        print(f"  col={c}, row={r}")


if __name__ == "__main__":
    main()
