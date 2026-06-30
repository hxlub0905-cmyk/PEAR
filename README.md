# PEAR — Pre-EBI Attribute Ranker

PEAR is a **pre-inspection attribute-discovery tool** for electron-beam-inspection
(EBI) of repeating-cell structures. It runs *before* you set up an inspection recipe.

> **On the name.** PEAR = *Pre-EBI Attribute Ranker*: it **ranks** which attribute best
> separates the outlier cells, run *before* EBI so the result can feed the inspection
> recipe.

## The one idea

In a field of identical repeating cells, take the *same sub-region* out of every cell and
ask **"which image attribute makes the abnormal cells stand out the most?"** That
attribute (and a threshold the engineer chooses) is what should go into the inspection
recipe.

Every attribute turns the population of cells into a distribution. A *useless* attribute
leaves the odd cells buried in the bulk; a *good* attribute pushes them out into the tail.
PEAR computes a whole bank of attributes for every cell instance and **ranks them by how
far the outliers separate** (robust modified z-score, median + MAD).

## The "no verdict" principle

**PEAR ranks and reports — it does not detect, classify, or decide.** It surfaces measured
numbers and a ranking; the engineer chooses the attribute and threshold. Outlier markers
are **markers, not a verdict** (amber = "look here", never red "bad"). No attribute is
labelled "best", and no threshold is auto-applied.

## Highlights

- Fully **offline** — no network, no telemetry, all computation local.
- Open one 8-bit grayscale image (TIFF/PNG/JPG/BMP); 16-bit/RGB inputs are normalized to
  8-bit grayscale on load (CJK-path safe IO).
- Detect the repeating **period** `(px, py)`, with manual override and a refine pass; build
  and preview a **Golden Cell** (median-stacked reference).
- Draw additive, editable rectangular **regions** inside a cell; each expands to every
  complete cell (phase-invariant).
- Compute a **29-attribute bank** per cell instance with two analysis modes:
  - **Unsupervised** — ranks attributes by how far the outlier cells separate
    (robust modified z-score), with amber outlier markers on the image.
  - **Labelled compare** — tag the suspect cells as *target*; the rest become
    *reference*. Attributes are ranked by how well they separate target from
    reference (separation score / AUC), with a suggested threshold reporting
    catch% and false-alarm%. Hover any attribute for its formula.
- Distribution view (single population, or reference-vs-target overlay with the
  threshold line) and **CSV export** (carries the active mode's ranking).
- Optional **pixel size (nm/px)** adds physical-area attributes.

## Install & run

```bash
pip install -r requirements.txt
python -m pear
```

Generate a synthetic sample to try the tool without real fab data (real imagery cannot be
bundled):

```bash
python examples/make_sample.py     # writes examples/sample_field.png
python -m pear                     # then Load… the generated image
```

## Build a standalone executable

PyInstaller one-folder, windowed:

```bash
pip install pyinstaller
pyinstaller pear.spec
```

The deployable artifact is `dist/PEAR/` — zip the folder and copy it to a machine that has
no Python.

## Tests

```bash
pip install pytest
pytest                                   # headless core + offscreen UI smoke
```

- `tests/test_core.py` — headless (no Qt): period → expand → attributes → ranking.
- `tests/test_ui_smoke.py` — offscreen (`QT_QPA_PLATFORM=offscreen`): drives the full UI
  path and exports CSV.

## Repository layout

```
pear/
  pear/
    core/          # pure NumPy/OpenCV, ZERO Qt imports (headless-testable)
      period_core.py, stacking.py   # VENDORED (see below)
      attributes.py                 # attribute bank
      separability.py               # outlier ranking (+ dormant Phase-2 metrics)
      analysis.py                   # data model, ROI expand, orchestration
    ui/            # all Qt lives here (theme, image_view, widgets, main_window)
  tests/
  examples/        # make_sample.py
```

## Vendored period core (provenance)

`pear/core/period_core.py` and `pear/core/stacking.py` are vendored **verbatim** from
[`hxlub0905-cmyk/cell-period-estimator`](https://github.com/hxlub0905-cmyk/cell-period-estimator)
(`main` branch, Qt-free core):

- `cell_period_estimator/core/period_core.py` → `pear/core/period_core.py`
- `cell_period_estimator/core/stacking.py`    → `pear/core/stacking.py`

These files are **not modified**. Call sites in `pear/core/analysis.py` and
`pear/ui/main_window.py` adapt to their API (e.g. `PeriodResult.confidence_x/.confidence_y`,
`stack_cells(..., method="median")`).

## Scope (V1)

In scope: single repeating-cell image, period detection + golden cell, additive/editable
regions, unsupervised outlier-attribute ranking, distribution, outlier markers, CSV export,
optional nm/px.

Both the unsupervised outlier ranking and the labelled reference-vs-target compare
mode are available and switchable in the UI.

Out of scope: defect detection/decision, classification, ML; non-repeating modes;
batch processing; recipe/JSON export.
