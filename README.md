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
  many ROIs. Set the box size (**W × H**), pick a group, then add ROIs three ways:
  - **click** the image to drop a size-W×H box, or **drag** to size one,
  - **Grid** — click the top-left then bottom-right corner, set *row × col*
    (live preview), and place the grid (Add grid / Enter).
  - **Shift+drag** box-selects ROIs of the active group (highlighted in the
    list); **Delete** removes the selection.
  - **Keyboard**: arrow keys nudge the selected ROI (Shift = 10 px), **Ctrl+D**
    duplicates it, **Ctrl+A** selects the whole group, **1–9** switch the active
    group.
- **Metrics** — a customizable set of **GLV statistics** (mean, median, Q25,
  Q75, std, min, max, plus any custom **Q*n***) and **SNR**. SNR is a
  *within-group* measurement: tag one ROI as the **target (T)** and the rest
  become the **reference (R)**, giving the e-beam definition
  **(mean_T − mean_R) / std_R**. Any one metric can be shown live on the ROIs,
  optionally as a **value heatmap** (ROIs coloured by the metric, with a
  colorbar) and with **outlier flagging** (Tukey fences within each group).

## Comparisons (in a separate Analysis window)

- **Between groups** — the distribution of a metric across every ROI in each
  group, overlaid.
- **Within a group** — the distribution across one group's ROIs.

Charts render as **vertical box-and-strip** plots (toggle **whiskers** / strip
**points**) or an overlaid **histogram**, with labelled axes; plus a summary
table. **CSV export** carries every ROI's metrics and a per-group summary.

## Highlights

- Fully **offline** — no network, no telemetry, all computation local.
- **Project save / open (JSON)** — persist groups, ROIs, the SNR target,
  metrics, and view state; reopen to pick up where you left off.
- Open one 8-bit grayscale image (TIFF/PNG/JPG/BMP); 16-bit/RGB inputs are
  normalized to 8-bit grayscale on load (CJK-path safe IO).
- Hover an ROI on the canvas or in the list — the other side highlights in sync.
- Analysis runs **off the UI thread** (debounced), so placing many ROIs stays
  responsive.
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
pyinstaller pear.spec               # -> dist/PEAR/
```

## Tests

```bash
pip install pytest
pytest                              # headless core + offscreen UI smoke
```

- `tests/test_core.py` — headless (no Qt): ROI patch/metrics, within-group SNR,
  grid interpolation, outlier detection, heat colormap, project (de)serialize,
  between/within comparison, snapshot isolation.
- `tests/test_ui_smoke.py` — offscreen: full UI path, three add modes, marquee
  select, target/SNR, ROI re-indexing, heatmap/outliers, hover sync, keyboard
  shortcuts, chart toggles, project save/open, CSV export.

## Repository layout

```
pear/
  pear/
    core/          # pure NumPy/OpenCV, ZERO Qt imports (headless-testable)
      attributes.py                 # GLV statistics + SNR
      analysis.py                   # group/ROI model, geometry, metric collection
    ui/            # all Qt (theme, image_view, widgets, main_window)
  tests/
  examples/        # make_sample.py
```

## Scope (V1)

In scope: single image, ROI groups, additive/editable ROIs (click / drag /
grid / box-select), GLV + within-group SNR metrics, value heatmap + outlier
flagging, between-group and within-group distribution comparison (box or
histogram) in a separate window, project save/open, CSV export.

Out of scope: defect detection/decision, classification, ML; batch processing.
