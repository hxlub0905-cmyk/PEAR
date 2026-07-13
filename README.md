# PEAR — Pre-EBI Attribute Ranker

PEAR is a **pre-inspection measurement tool** for electron-beam-inspection (EBI)
of repeating-cell structures. It runs *before* you set up an inspection recipe.

## The one idea

In a field of identical repeating cells, **group the cells** you care about, take
the **same measurement window (ROI)** out of every cell, and **compare** a small
bank of grey-level statistics (GLV) and the signal-to-noise ratio (SNR) — either
**between groups** or **within a group** (target vs reference). The numbers, and
the split you choose, are what feed the inspection recipe.

## The "no verdict" principle

**PEAR measures and reports — it does not detect, classify, or decide.** It
surfaces measured numbers and distributions; the engineer draws the conclusion.
Nothing is auto-flagged and no threshold is auto-applied.

## Model

- **Group** — a set of cells you paint on the image. Groups are the populations
  you compare. Each has a custom colour and can be tagged **T**arget / **R**eference.
- **ROI** — a measurement rectangle *inside a cell*. It is phase-invariant, so it
  repeats in every cell. ROIs support **drag / + Add / Grid** (batch). When the
  Target/Reference split is on, one ROI is the target and one is the reference,
  which enables SNR.
- **Metrics** — a customizable set of **GLV statistics** (mean, median, Q25, Q75,
  std, min, max, plus any custom **Q*n***) and **SNR = (μ_target − μ_reference) / σ_reference**.

## Comparisons

- **Between groups** — the same ROI + metric across different groups.
- **Within a group** — target-ROI vs reference-ROI over one group's cells (with
  the SNR readout).

The Analysis panel (box + jittered-strip distribution charts + a summary table)
is a dock you can **float into its own window**.

## Highlights

- Fully **offline** — no network, no telemetry, all computation local.
- Open one 8-bit grayscale image (TIFF/PNG/JPG/BMP); 16-bit/RGB inputs are
  normalized to 8-bit grayscale on load (CJK-path safe IO).
- Detect the repeating **period** `(px, py)`, with a refine pass, and build a
  **Golden Cell** (median-stacked reference).
- **Paint cells into groups**; **draw ROIs** that repeat in every cell.
- Compare **between groups** or **within a group**; **CSV export** carries per-cell
  metrics and a per-group summary.
- Live **cursor readout**, **zoom** controls, and inline **colour / T-R** editing.
- Calm **light instrument theme** with a single amber accent and system-safe fonts.

## Install & run

```bash
pip install -r requirements.txt
python -m pear
```

Generate a synthetic sample to try the tool without real fab data:

```bash
python examples/make_sample.py     # writes examples/sample_field.png
python -m pear                     # then Load… the generated image
```

## Build a standalone executable

```bash
pip install pyinstaller
pyinstaller pear.spec
```

The deployable artifact is `dist/PEAR/` — zip the folder and copy it to a machine
that has no Python.

## Tests

```bash
pip install pytest
pytest                                   # headless core + offscreen UI smoke
```

- `tests/test_core.py` — headless (no Qt): period → grid → group/ROI metrics → SNR.
- `tests/test_ui_smoke.py` — offscreen: drives the full UI path and exports CSV.

## Repository layout

```
pear/
  pear/
    core/          # pure NumPy/OpenCV, ZERO Qt imports (headless-testable)
      period_core.py, stacking.py   # VENDORED (see below)
      attributes.py                 # GLV statistics + SNR
      analysis.py                   # group/ROI model, geometry, metric collection
    ui/            # all Qt lives here (theme, image_view, widgets, main_window)
  tests/
  examples/        # make_sample.py
```

## Vendored period core (provenance)

`pear/core/period_core.py` and `pear/core/stacking.py` are vendored **verbatim**
from [`hxlub0905-cmyk/cell-period-estimator`](https://github.com/hxlub0905-cmyk/cell-period-estimator)
(`main` branch, Qt-free core). These files are **not modified**; call sites adapt
to their API.

## Scope (V1)

In scope: single repeating-cell image, period detection + golden cell, cell
grouping, additive/editable ROIs with target/reference split, GLV + SNR metrics,
between-group and within-group comparison, distribution charts, CSV export.

Out of scope: defect detection/decision, classification, ML; non-repeating modes;
batch processing; recipe/JSON export.
