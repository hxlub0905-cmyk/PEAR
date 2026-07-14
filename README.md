# PEAR — Pre-EBI Attribute Ranker

PEAR is a **pre-inspection measurement tool** for electron-beam-inspection (EBI)
of repeating-cell structures. It runs *before* you set up an inspection recipe.

## The one idea

Sort the features you care about into **groups** (say, *round holes* vs
*square holes*), drop a **measurement box (ROI)** on each instance, and
**compare the distribution** of a grey-level statistic (GLV) or the
signal-to-noise ratio (SNR) between the groups — or within one group. The
numbers are what feed the inspection recipe.

## The "no verdict" principle

**PEAR measures and reports — it does not detect, classify, or decide.** It
surfaces measured numbers and distributions; the engineer draws the conclusion.

## Model

- **Group** — a *category* of features (e.g. "round holes", "square holes").
  Custom colour, rename inline. You create groups first.
- **ROI** — a measurement rectangle that **belongs to a group**. A group holds
  many ROIs. Pick a group, then add ROIs three ways:
  - **click** the image to drop a default box, or **drag** to size one,
  - **Grid** — click the top-left then bottom-right corner, set *row × col*
    (live preview), and place the grid (Add grid / Enter).
- **Metrics** — a customizable set of **GLV statistics** (mean, median, Q25,
  Q75, std, min, max, plus any custom **Q*n***) and **SNR** — the e-beam
  definition **(mean_ROI − mean_background) / std_background**, measured against
  the ring around each ROI (self-contained per ROI).

## Comparisons (in a separate Analysis window)

- **Between groups** — the distribution of a metric across every ROI in each
  group, overlaid.
- **Within a group** — the distribution across one group's ROIs.

Box + jittered-strip charts plus a summary table; **CSV export** carries every
ROI's metrics and a per-group summary.

## Highlights

- Fully **offline** — no network, no telemetry, all computation local.
- Open one 8-bit grayscale image (TIFF/PNG/JPG/BMP); 16-bit/RGB inputs are
  normalized to 8-bit grayscale on load (CJK-path safe IO).
- Analysis runs **off the UI thread** (debounced), so placing many ROIs stays
  responsive.
- Calm **light instrument theme** with a single amber accent and system-safe fonts.
- Optional **pixel size (nm/px)** adds physical cell size and an area column to CSV.

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
pyinstaller pear.spec               # -> dist/PEAR/
```

## Tests

```bash
pip install pytest
pytest                              # headless core + offscreen UI smoke
```

- `tests/test_core.py` — headless (no Qt): period, ROI metrics, SNR, grid /
  per-cell, between/within comparison.
- `tests/test_ui_smoke.py` — offscreen: full UI path, multi-add, CSV export.

## Repository layout

```
pear/
  pear/
    core/          # pure NumPy/OpenCV, ZERO Qt imports (headless-testable)
      period_core.py, stacking.py   # VENDORED (see below)
      attributes.py                 # GLV statistics + SNR
      analysis.py                   # group/ROI model, geometry, metric collection
    ui/            # all Qt (theme, image_view, widgets, main_window)
  tests/
  examples/        # make_sample.py
```

## Vendored period core (provenance)

`pear/core/period_core.py` and `pear/core/stacking.py` are vendored **verbatim**
from [`hxlub0905-cmyk/cell-period-estimator`](https://github.com/hxlub0905-cmyk/cell-period-estimator)
(`main` branch, Qt-free core). They are **not modified**; call sites adapt to
their API.

## Scope (V1)

In scope: single image, ROI groups, additive/editable ROIs (click / drag /
grid), GLV + SNR metrics, between-group and within-group distribution comparison
in a separate window, CSV export, optional nm/px.

Out of scope: defect detection/decision, classification, ML; batch processing.
