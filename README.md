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
  - The ROI list carries each ROI's shown metric and sorts by it (**order**:
    as placed / value ↑ / value ↓), so the odd one out is one glance away.
- **Metrics** — a customizable set of **GLV statistics** (mean, median, Q25,
  Q75, std, min, max, plus any custom **Q*n***) and **SNR**. SNR is a
  *within-group* measurement: tag one ROI as the **target (T)** and the rest
  become the **reference (R)**, giving the e-beam definition
  **(mean_T − mean_R) / std_R**. Any one metric can be shown live on the ROIs.
- **ROI overlay** — one strip sits above the image, where what it changes is:
  pick the metric under **show on ROIs**, then switch each reading of it on
  its own.
  - **values** — the number printed on the box, where the box is big enough
    to hold it; the ROI under the cursor always shows its own, floated above.
  - **heatmap** — the box filled with the metric's colour, with a colorbar.
    **opacity** turns the fill down until the image underneath shows through.
  - **fill field** — spread each ROI's colour over the patch of image it
    speaks for (midway to its neighbours), so a gradient across the field
    reads as one surface instead of a row of small tinted boxes. The measured
    box stays outlined on top.
  - **flag outliers** — Tukey fences within each group.

## Comparisons (in a separate Analysis window)

- **Between groups** — the distribution of a metric across every ROI in each
  group, overlaid.
- **Within a group** — the distribution across one group's ROIs.

Charts render four ways, switched by one toggle: **vertical box-and-strip**
plots (toggle **whiskers** / strip **points**, and **own scale** to give each
group its own value range — printed under the lane — when one group's spread
is too small to see on the shared axis), an overlaid **histogram** (framed and
ticked axes, a legend carrying each group's *n*, a **bins** count, and **%**
to plot each group's share of its own *n* so groups of different size
compare), a **position profile**, or a **heat map**. Between-group mode
also gives an **attribute-ranking** table — which metric best separates the
groups, scored by η² (variance explained) and Cohen's d — and a **group ×
metric heatmap** for an at-a-glance overview, plus a summary table.

Charts are laid out as figures — a printable shape, capped in width and
centred, rather than stretched across the window. **Export image** saves the
chart sheet alone (no window chrome, no layout margin) as **PNG at 3×** for
slides or **SVG** for a paper — the plots are hand-painted with QPainter, so
the SVG comes out as real curves and text, not a bitmap in a wrapper. **CSV export** carries every ROI's metrics and a
per-group summary.

## Uniformity — is the GLV flat across the field?

Two views answer "are all these ROIs measuring the same thing?" — the question
you ask when every box sits on the same layer (all on EPI, say) and you expect
one number everywhere.

- **Position profile** — the metric on Y against the ROI's **centre X or Y** on
  X (switchable). Three lines, keyed in the chart's top-right corner:
  - **dots** — one per ROI, at its own position.
  - **profile** (solid, the group's colour darkened) — the **mean of the ROIs
    at each position**; a column of ROIs sharing an X collapses into one point
    of it. This is the line you read flatness off.
  - **trend** (dashed, amber) — the **least-squares fit** through every ROI.
    Its slope is quoted as *slope per 100 px*; 0 means no tilt.
  - **group mean** (dashed, faint, the group's colour) — where a perfectly
    flat profile would sit, for the profile to be compared against.

  **A uniform field reads as a flat line.**
- **Heat map** — the ROIs at their own **(x, y)**, each coloured by the
  metric, with a colour bar. As **cells** (the default) every ROI is a block
  reaching the boundary it shares with its neighbour, so the field tiles with
  no gaps and a block reads against the one beside it; **values** prints the
  number inside each block, and unticking **cells** falls back to separate
  dots. **A uniform field is one flat colour**; a gradient or a hot corner is
  the non-uniformity, and you can see *where* it is.

Both print the numbers rather than a verdict: **range** (peak-to-peak),
**range %** and **CV %** of the mean, and the trend **slope per 100 px**. CSV
export carries each ROI's `center_x` / `center_y`, so the same profile replots
anywhere.

**Double-click any ROI** for a **pixel inspector** in its own window: a
false-colour view of the patch, its grey-level histogram, and horizontal /
vertical intensity profiles.

## Highlights

- Fully **offline** — no network, no telemetry, all computation local.
- **Project save / open (JSON)** — persist groups, ROIs, the SNR target,
  metrics, and view state (overlay toggles, heat opacity, ROI list order, the
  chart type and position axis);
  reopen to pick up where you left off.
- Open one 8-bit grayscale image (TIFF/PNG/JPG/BMP); 16-bit/RGB inputs are
  normalized to 8-bit grayscale on load (CJK-path safe IO).
- Hover an ROI on the canvas or in the list — the other side highlights in sync.
- The status bar keeps the headline numbers — groups, ROIs, and the shown
  metric's mean, range and CV — so the figure you keep glancing at does not
  need the Analysis window opened for it.
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
  grid interpolation, outlier detection, heat colormap, heat-map cell edges,
  per-ROI field cells,
  attribute separability / ranking, pixel histogram, ROI positions / linear
  trend / uniformity, project (de)serialize, between/within comparison,
  snapshot isolation.
- `tests/test_bundle.py` — the single-file text bundle round-trips byte for
  byte, survives CRLF, catches tampering, and is not stale.
- `tests/test_ui_smoke.py` — offscreen: full UI path, three add modes, marquee
  select, target/SNR, ROI re-indexing, heatmap/outliers, hover sync, keyboard
  shortcuts, chart toggles, ranking/heatmap render, ROI inspector, project
  save/open, CSV + chart-image export, histogram bins / percent / tick steps,
  chart aspect, position profile + heat map (cells / dots / values),
  independent ROI overlay toggles, field fill, value-label fitting, fit across
  a resize, ROI list values / ordering, status headline, per-lane box scale,
  list rebuilds leaving no stale rows.

## Repository layout

```
pear/
  pear/
    core/          # pure NumPy/OpenCV, ZERO Qt imports (headless-testable)
      attributes.py                 # GLV statistics + SNR
      analysis.py                   # group/ROI model, geometry, metric collection
    ui/            # all Qt (theme, image_view, widgets, main_window)
                   #   widgets.py: rail, stage bar, charts, inspector
  tests/
  examples/        # make_sample.py
  tools/           # make_text_bundle.py — pack the repo into one text file
  bundle/          # pear_bundle.py — that pack (regenerate after every change)
  docs/            # NO-GIT-SETUP.md — install where downloads are blocked
```

## Offline install (no git, downloads blocked)

Where the machine cannot download anything but can copy from GitHub, the whole
repo travels as **one plain-text `.py`** that unpacks itself — see
[`docs/NO-GIT-SETUP.md`](docs/NO-GIT-SETUP.md). Regenerate it after every
change, or the other machine silently gets old code:

```bash
git add -A && python tools/make_text_bundle.py && git add -A
```

## Scope (V1)

In scope: single image, ROI groups, additive/editable ROIs (click / drag /
grid / box-select), GLV + within-group SNR metrics, value heatmap + outlier
flagging with per-overlay toggles and a field fill, attribute ranking +
group×metric heatmap, chart image export (PNG / SVG),
per-ROI pixel inspector,
between-group and within-group comparison in a separate window (box, histogram,
position profile, or spatial heat map), project save/open, CSV export.

Out of scope: defect detection/decision, classification, ML; batch processing.
