#!/usr/bin/env python3
# PEAR 單檔純文字包（由 tools/make_text_bundle.py 產生）。
"""整個 PEAR repo 就在這個檔案裡，一行一行的純文字，沒有壓縮、沒有編碼。

為什麼是這種形式：公司政策擋掉 .zip 這個類別，proxy 也不讓 Python 逐檔抓 ——
能過的只剩「一個純文字檔」。你可以用記事本打開它，往下捲就看得到每個檔案。

    python pear_bundle.py              # 解到 .\\pear\\
    python pear_bundle.py --dest D:\\tools
    python pear_bundle.py --list       # 只看裡面有什麼，不寫任何檔案

每個檔案都帶 git blob SHA-1，解開時逐檔驗過才落地 —— 傳輸途中被動到會當場講出
來，不會讓你拿到一份安靜壞掉的程式碼。

解開之後：

    cd pear
    pip install -r requirements.txt
    python -m pear
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

SENTINEL = "# ==== PEAR-BUNDLE-DATA ==== 以下是資料，不要編輯 ===="
PART, N_PARTS = 1, 1   # 這是第幾批 / 共幾批（1/1 = 沒有分批）
TOTAL = 26                       # 整個 repo 有幾個檔案，不是這一批有幾個


def blob_sha(data: bytes) -> str:
    """git 算 blob SHA 的方式："blob <長度>\\0" + 內容。"""
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def entries(lines):
    """走過資料區，一個一個吐出 (sha, 路徑, 內容位元組)。"""
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("#F "):
            i += 1
            continue
        _, sha, count, path = line.split(" ", 3)
        n = int(count)
        # 資料區每一行前面有一個 '#'（那樣整個檔案才仍然是合法的 Python）。
        body = [ln[1:] if ln[:1] == "#" else ln for ln in lines[i + 1:i + 1 + n]]
        yield sha, path, "\n".join(body).encode("utf-8")
        i += 1 + n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Unpack the PEAR text bundle.")
    ap.add_argument("--dest", default="pear", help="解到哪個資料夾（預設 .\\pear）")
    ap.add_argument("--list", action="store_true", help="只列出內容，不寫檔")
    a = ap.parse_args(argv)

    # 用文字模式讀自己：Python 把 CRLF 讀成 LF，所以這個檔案就算在傳輸途中被換
    # 過行尾也解得開（格式用「行數」而不是「位元組數」正是為了這件事）。
    with open(os.path.abspath(__file__), "r", encoding="utf-8") as f:
        lines = f.read().split("\n")
    try:
        start = lines.index(SENTINEL) + 1
    except ValueError:
        print("X 找不到資料區 —— 這個檔案被截斷了，或不是完整的 bundle。")
        return 2

    items = list(entries(lines[start:]))
    if not items:
        print("X 資料區是空的 —— 這個檔案被截斷了。")
        return 2
    print("這個包裡有 %d 個檔案。" % len(items))
    if a.list:
        for _sha, path, data in items:
            print("  %8d  %s" % (len(data), path))
        return 0

    dest = os.path.abspath(a.dest)
    print("解到  : %s" % dest)
    bad, done = [], 0
    for sha, path, data in items:
        if blob_sha(data) != sha:
            bad.append(path)
            continue
        full = os.path.join(dest, path.replace("/", os.sep))
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        tmp = full + ".tmp"                      # atomic：半個檔案不要留在磁碟上
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, full)
        done += 1

    if bad:
        print("")
        print("X %d 個檔案的內容跟它自己的 SHA 對不上：" % len(bad))
        for path in bad[:12]:
            print("    %s" % path)
        print("")
        print("  這個檔案在傳輸途中被動過（編輯器另存、郵件過濾器改寫都會這樣）。")
        print("  請重新取得一份，不要用編輯器打開後另存。這份程式碼不完整，不要用。")
        return 1

    print("OK %d 個檔案都解開了，SHA 全部對得上。" % done)

    if N_PARTS > 1:
        print("")
        print("這是第 %d 批 / 共 %d 批，整個 repo 有 %d 個檔案。"
              % (PART, N_PARTS, TOTAL))
        print("把其他批也貼進來執行（順序不重要，重複執行也沒關係）。")
        return 0

    print("")
    print("下一步：")
    print("  cd %s" % dest)
    print("  pip install -r requirements.txt")
    print("  python -m pear")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ==== PEAR-BUNDLE-DATA ==== 以下是資料，不要編輯 ====
#F 81eb983622588cb29249bf7d0fa727075947d947 17 .gitignore
#__pycache__/
#*.py[cod]
#*.egg-info/
#.eggs/
#build/
#dist/
#.pytest_cache/
#.venv/
#venv/
#examples/sample_field.png
## drawn by tools/make_icon.py at install time — the plain-text
## bundle takes text only, so no binary lives in the repo
#pear.ico
#pear_icon.png
## wheels dropped here for an offline install
#wheels/
#
#F c26e1ad3de08462b65d861e19f6fbec303663ea4 136 CLAUDE.md
## CLAUDE.md — PEAR
#
#給在這個 repo 工作的 AI 助手的規則。先讀完再動手。
#
#---
#
### 0. 這個工具在做什麼（改任何東西之前先懂這件事）
#
#**PEAR = Pre-EBI Attribute Ranker。** EBI（電子束檢測）**建 recipe 之前**用的
#量測工具。
#
#### 「不下判斷」原則
#
#**PEAR 只量測與呈現，不偵測、不分類、不下判定。** 它給出數字與分佈，結論由工程
#師來下。
#
#這不是一句口號，是**驗收標準**：任何新功能如果會印出「pass / fail」「這是缺陷」
#「這片不合格」，就是走錯方向。要加的是**數字**（η²、Cohen's d、range、CV、
#slope），讓使用者自己看。加門檻值、加紅綠燈、加自動判定 —— 都不行。
#
#### 兩層模型
#
#- **Group** = 特徵的**類別**（圓孔 vs 方孔），不是一個框
#- **ROI** = 屬於某個 group 的量測方框
#
#改動涉及這兩者的關係時要格外小心：`gid` 是群組身分，`rid` 是 ROI 身分，
#兩者都必須全域唯一。
#
#---
#
### 1. 架構鐵則
#
#### `pear/core/` 不准 import Qt
#
#`core/` 是純 NumPy + OpenCV，**零 Qt import**。理由：那是唯一能 headless 測試
#的部分，而 UI 測試需要 offscreen 平台外加一堆系統函式庫（`libEGL` 之類）。
#一旦 `core/` 沾到 Qt，`tests/test_core.py` 就在沒有圖形環境的機器上跑不了。
#
#計算放 `core/`，畫面放 `ui/`。新的統計量寫進 `core/analysis.py` 或
#`core/attributes.py`，並在 `tests/test_core.py` 補測試。
#
#### 分析要跑在 UI thread 之外
#
#`compute_analysis()` 是純函式，透過 `QRunnable` 丟到 thread pool。丟之前一定要
#先 `snapshot()` 深拷貝模型 —— worker 拿到的不能是使用者還在編輯的那份物件。
#
#### 所有 reduction 都要防退化輸入
#
#空 patch、單一元素、std ≈ 0 —— 這些在實際操作中天天發生（使用者剛放下第一個
#框）。回傳 `None` 或 0，**不要 raise**。既有的函式都是這樣寫的，照做。
#
#### 影像 IO 走 `np.fromfile` + `cv2.imdecode`
#
#**不要用 `cv2.imread`。** 使用者的路徑含中文，`imread` 在那些路徑上會靜靜地回
#傳 None。
#
#---
#
### 2. 每次改完程式碼：重產搬運用的單檔包
#
#**規則：任何進到 `git ls-files` 的檔案改動之後，都要重產 `bundle/pear_bundle.py`
#並一起 commit。**
#
#```bash
#git add -A && python tools/make_text_bundle.py && git add -A
#```
#
#### 為什麼
#
#公司環境**下載不了東西**：`.zip` 這個類別被擋（不只 GitHub 的 `codeload`，換
#來源也一樣），proxy 也不讓 Python 逐檔抓。剩下唯一的通道是「在 GitHub 上看得到
#檔案 → 按複製鈕 → 貼進記事本」。
#
#所以 `bundle/pear_bundle.py` 是**整個 repo 打包成的一個純文字 `.py`**，它自己解
#得開。那台機器拿程式碼只有這一條路。同樣的做法見姊妹 repo
#[`d4t`](https://github.com/hxlub0905-cmyk/d4t) 的 `tools/make_text_bundle.py`，
#這支是照著它的慣例寫的。
#
#### 忘了重產會怎樣
#
#**在這台機器上沒有任何症狀。** 症狀出現在另一台機器上，而且是「功能沒有生效」
#或「解出來的程式碼是舊的」—— 最難查的那種。所以 `tests/test_bundle.py` 有一支
#測試會在包過期時變紅，錯誤訊息就是上面那行指令。**不要靠記性，靠測試。**
#
#### 這個包的格式為什麼長這樣（不要「順手優化」掉）
#
#| 決定 | 理由 |
#|---|---|
#| **不壓縮、不 base64** | base64 對 DLP 來說是「看不懂的東西」，而看不懂通常等於擋掉。repo 全是純文字，本來就不需要編碼 |
#| **以「行數」而非「位元組數」框住每個檔案** | 傳輸途中 LF 會被換成 CRLF（記事本、郵件過濾器）。用位元組數的話**第一個檔案之後全部**對不上，看起來像整包壞掉 |
#| **資料區每一行前面加 `#`** | Python 執行前會先編譯整個檔案。資料區若是裸文字，它會去解析別人的檔案內容然後 SyntaxError |
#| **每個檔案帶 git blob SHA-1** | 被動過要當場講出來，而不是讓人拿到一份安靜壞掉的程式碼 |
#| **`bundle/` 自己排除在外** | 不排掉的話每打一次包，repo 就多裝一份上一次的包，指數成長 |
#
#`--split` 已經備好但目前用不到（包約 215 KB，GitHub 檔案瀏覽頁的上限是 1 MB）。
#真的長大再說。
#
#---
#
### 3. 改完要跑的東西
#
#```bash
#python -m pytest tests/test_core.py -q          # headless，不需要圖形環境
#QT_QPA_PLATFORM=offscreen python -m pytest -q   # 全部（含 UI smoke）
#```
#
#UI 測試在沒有圖形環境的機器上需要：
#`apt-get install -y libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1`。
#
#**新功能一定要有測試。** 計算的部分進 `tests/test_core.py`（快、無 Qt），畫面
#的部分進 `tests/test_ui_smoke.py`（記得呼叫 `chart.grab()` 之類真的去跑
#painter —— 只建構 widget 不會執行 `paintEvent`，繪圖的 bug 會整個漏掉）。
#
#---
#
### 4. 圖表：新增一種圖的時候
#
#`DistributionChart` 全部用 QPainter 手繪，**沒有繪圖函式庫相依**。維持這樣。
#
#- 新的圖表類型 → 在 `set_data` 的 `ctype` 加一個值、在 `paintEvent` 加一個分支、
#  寫一個 `_paint_<type>` 方法，然後在 `AnalysisPanel` 加一顆 toggle 按鈕。
#- **軸刻度用 `_fmt_span`，不要用 `_fmt`。** `_fmt` 是 3 位有效數字，資料很平的
#  時候（正好是均勻性分析最在意的情況）五個刻度會印出一模一樣的字。
#- **左側 gutter 要依實際文字寬度算**，不要寫死 —— 不然 `127.735` 會被切掉開頭。
#- **同一張圖裡不同意義的線要用不同顏色。** 資料點、profile 線、趨勢線、參考線
#  各自一個顏色，而且**參考線畫在底層、資料畫在上層**（反過來的話趨勢線會蓋掉它
#  本來要被拿來比較的那條 profile）。
#
#---
#
### 5. 語言
#
#程式碼、docstring、註解、commit message 用**英文**（跟既有的一致）。
#`CLAUDE.md` 與 `docs/` 底下給使用者看的操作說明用**繁體中文**。
#跟使用者對話用**繁體中文**。
#
#F 0423de0a4c5fa9404d6ea616a1ff7819344529f9 7 PEAR.bat
#@echo off
#rem Start PEAR. Uses the virtual environment install.bat made, if it is there.
#cd /d "%~dp0"
#if exist "%~dp0.venv\Scripts\pythonw.exe" start "PEAR" "%~dp0.venv\Scripts\pythonw.exe" -m pear
#if exist "%~dp0.venv\Scripts\pythonw.exe" exit /b
#start "PEAR" pythonw -m pear
#
#F bc51e13596d78f57145256c8b7425d5ad725441e 357 README.md
## PEAR — Pre-EBI Attribute Ranker
#
#PEAR is a **pre-inspection measurement tool** for electron-beam-inspection (EBI)
#of repeating-cell structures. It runs *before* you set up an inspection recipe.
#
### The one idea
#
#Sort the features you care about into **groups** (say, *round holes* vs
#*square holes*), drop a **measurement box (ROI)** on each instance, and
#**compare the distribution** of a grey-level statistic (GLV) or the
#value between the groups — or within one group. The
#numbers are what feed the inspection recipe.
#
### The "no verdict" principle
#
#**PEAR measures and reports — it does not detect, classify, or decide.** It
#surfaces measured numbers and distributions; the engineer draws the conclusion.
#
### Model
#
#- **Group** — a *category* of features (e.g. "round holes", "square holes").
#  Custom colour, rename inline. You create groups first.
#- **ROI** — a measurement rectangle that **belongs to a group**. A group holds
#  many ROIs. Set the box size (**W × H**), pick a group, then add ROIs three ways:
#  - **click** the image to drop a size-W×H box, or **drag** to size one,
#  - **Grid** — click the top-left then bottom-right corner, set *row × col*
#    (live preview), and place the grid (Add grid / Enter).
#  - **Shift+drag** box-selects ROIs of the active group (highlighted in the
#    list); **Delete** removes the selection.
#  - **Keyboard**: arrow keys nudge the selected ROI (Shift = 10 px), **Ctrl+D**
#    duplicates it, **Ctrl+A** selects the whole group, **1–9** switch the active
#    group. **Right-drag pans** the image at any time, grid placement included.
#  - **⤓ / ⤒** (the two icons in the ROIs card header) — the ROI set travels
#    on its own as a flat JSON list, so a layout worked out in another tool
#    drops straight in:
#
#    ```json
#    [ { "color": "#00ffff", "x": 32, "y": 68, "w": 30, "h": 24,
#        "target": false } ]
#    ```
#
#    `x` / `y` are the box's **top-left corner**; **each colour becomes a
#    group**. Both ends ask what to do about the box size: **import** takes it
#    from the file (or the **size** fields, for a list that only says where
#    the boxes go) or forces one size on the whole set; **export** keeps each
#    box's own size, writes one size for all of them, or leaves `w` / `h` out
#    entirely — the shape a tool with its own box size expects. `target` is
#    accepted and written for compatibility with the tool the format comes
#    from; PEAR has no target role. Boxes that fall outside the image are
#    moved inside it and the status bar says how many. Importing over existing
#    ROIs asks whether to replace them or add to them.
#  - **align** — pull the selection (or the whole active group, with nothing
#    selected) onto one edge (*Left / Centre / Right*, *Top / Middle /
#    Bottom*) or even out its spacing (*Even across / Even down*).
#  - The ROI list carries each ROI's shown metric and sorts by it (**order**:
#    as placed / value ↑ / value ↓), so the odd one out is one glance away.
#- **Metrics** — a customizable set of **GLV statistics** (mean, median, Q25,
#  Q75, std, min, max, plus any custom **Q*n***). Any one of them can be shown
#  live on the ROIs.
#- **ROI overlay** — one strip sits above the image, where what it changes is:
#  pick the metric under **show on ROIs**, then switch each reading of it on
#  its own.
#  - **values** — the number printed on the box, where the box is big enough
#    to hold it; the ROI under the cursor always shows its own, floated above.
#  - **heat boxes** — each ROI box filled with its value's colour, with a
#    colorbar. **opacity** turns the fill down until the image underneath
#    shows through, and **scale…** locks the colour range.
#  - **heat field** — spread each ROI's colour over the patch of image it
#    speaks for (midway to its neighbours), so a gradient across the field
#    reads as one surface instead of a row of small tinted boxes. The measured
#    box stays outlined on top. Boxes and field are two ways to paint the same
#    values, and **either works on its own**. Hand-placed ROIs land a few pixels off each
#    other, and cell edges fall midway between centres — taken literally, a
#    grid of eight columns shatters into thirty-odd slivers. Centres within a
#    **jitter tolerance measured from the data** count as one row or column, so
#    the field tiles as the grid it is; a genuinely uneven layout is left
#    alone, and *align* is there when you want the ROIs themselves tidied.
#  - **flag outliers** — Tukey fences within each group.
#
#  ROI outlines are **neutral ink over a white halo**, never the group's
#  colour: on this stage colour means a value (the heat ramp), and a neutral
#  rule stays legible on a black surround, on a bright feature and on any
#  colour of the ramp alike. The group shows in the box's **fill tint**
#  instead — and no group is ever amber, since amber is the ramp's midpoint
#  and the accent used for trend lines.
#
### Comparisons (in a separate Analysis window)
#
#- **Between groups** — the distribution of a metric across every ROI in each
#  group, overlaid.
#- **Within a group** — the distribution across one group's ROIs.
#
#Charts render four ways, switched by one toggle: **vertical box-and-strip**
#plots (toggle **whiskers** / strip **points**, and **own scale** to give each
#group its own value range — printed under the lane — when one group's spread
#is too small to see on the shared axis), an overlaid **histogram** (framed and
#ticked axes, a legend carrying each group's *n*, a **bins** count, and **%**
#to plot each group's share of its own *n* so groups of different size
#compare), a **position profile**, or a **heat map**. Between-group mode
#also gives an **attribute-ranking** table — which metric best separates the
#groups, scored by η² (variance explained) and Cohen's d — and a **group ×
#metric heatmap** for an at-a-glance overview, plus a summary table.
#
#Every chart keeps a readable shape — a distribution at roughly 4:3, a profile
#or a map wider but never a letterbox, where a real tilt and a flat line would
#look alike.
#
#The results read as one page, not two: the **figures fill the left column**,
#one per row and as large as the column allows, vertically centred; the numbers
#that annotate them — ranking, group × metric heatmap, summary table — stack
#down the right. Every chart carries the plain furniture a figure in a report
#needs: a boxed plot area with inward tick marks, labelled axes, and
#observations drawn as **open markers** so a scatter never fuses into the lines
#drawn in the same colour beside it.
#
#**Chart settings…** makes each figure yours, one row per thing on the chart so
#it is never a guess which control moves what:
#
#| Row | What it changes |
#|---|---|
#| **Tick values** | the numbers along both axes — size, bold, colour |
#| **Axis names** | the X and Y names and the plot frame — size, bold, colour |
#| **Data points** | every ROI's own marker — radius, colour |
#| **Lines** | the profile line, the median bar, the bar outlines — width, colour |
#
#Each colour has an **auto** box: on auto it follows the group's colour, and the
#two axis rows are dark by default, because a light grey tick label is not there
#on a projector. Above them you can **rename** each figure (the title sits
#centred above the plot, and the export menu follows the new name), give the
#**axes your own names** and set the **tick counts**; below them the **Scales**
#rows say which chart each range acts on (`value (box Y · hist X · profile Y)`,
#`position X (profile · map)`, `position Y (map)`, `heat colours (map)`) and
#**lock it to a fixed range** — auto scaling is right while you are looking at
#one run and wrong the moment you put two side by side, because each picks its
#own range. The image overlay has the same lock under **scale…** on the stage
#bar, so the same colour means the same grey level on every image you open.
#
#Text sizes push the axes outward rather than printing over them: both gutters
#are measured from the font you chose, so a 16 pt tick label is drawn in full
#with the axis name clear beside it.
#
#**All of it saves with the project** — the titles, axis names, tick counts,
#sizes, colours and locked ranges, and the header toggles too (points,
#whiskers, legend, own scale, bins, %, trend, cells, equal cells, values). A
#reopened project draws the chart you left, not the defaults.
#
#**CSV export** carries every ROI's metrics and a per-group summary.
#
### Every view exports as a picture
#
#Anything on screen can go into a report. **PNG is rendered at 3×** (a 1×
#screenshot of a chart is unreadable once a projector or a journal column has
#it) and **SVG stays vector** — every view is hand-painted with QPainter, so
#the SVG is real curves and text, not a bitmap in a wrapper. Nothing carries
#window chrome, and the marks that belong to what you are *doing* (cursor
#readout, selection handles, marquee, grid preview) are left out.
#
#- **The field** — *Export image* on the stage bar. Not a screenshot: the
#  image is redrawn **at its own resolution** (×2 by default) with the
#  overlays on top, whatever the view's zoom and pan happen to be, and the
#  colour key gets a strip of its own under the field instead of sitting on
#  the ROIs it is the key for.
#- **The results** — *Export image ▾* in the Analysis window offers exactly
#  the sections the current result has: **Charts** (the figures alone, cropped
#  out of the layout's slack) and, when there is more than one, **each chart
#  on its own** — one figure per file is what a document actually takes —
#  plus **Attribute ranking**, **Group × metric heatmap**, **Summary table**,
#  or **Everything** as one sheet.
#- **One ROI's pixels** — *Export image* in the ROI inspector window.
#
### Uniformity — is the GLV flat across the field?
#
#Two views answer "are all these ROIs measuring the same thing?" — the question
#you ask when every box sits on the same layer (all on EPI, say) and you expect
#one number everywhere.
#
#- **Position profile** — the metric on Y against the ROI's **centre X or Y** on
#  X (switchable). Three lines, keyed in the chart's top-right corner:
#  - **dots** — one per ROI, at its own position.
#  - **profile** (solid, the group's colour darkened) — the **mean of the ROIs
#    at each position**; a column of ROIs sharing an X collapses into one point
#    of it, and centres that miss each other by a few pixels count as the same
#    column (the same jitter tolerance the field tiling uses), so a hand-placed
#    grid gives one clean vertex per column instead of a kink per ROI. This is
#    the line you read flatness off.
#  - **trend** (dashed, amber) — the **least-squares fit** through every ROI.
#    Its slope is quoted as *slope per 100 px*; 0 means no tilt.
#  - **group mean** (dashed, faint, the group's colour) — where a perfectly
#    flat profile would sit, for the profile to be compared against.
#
#  **A uniform field reads as a flat line.**
#- **Heat map** — the ROIs at their own **(x, y)**, each coloured by the
#  metric, with a colour bar. As **cells** (the default) every ROI is a block;
#  **values** prints the number inside each block, and unticking **cells**
#  falls back to separate dots. **equal cells** (on by default) lays the blocks
#  out one slot per row and column, every tile the same size — a die map. Off,
#  each block reaches the midline it shares with its neighbour, which is
#  faithful to the spacing but hands neighbouring cells visibly different areas
#  when the pitch is uneven or a slot is empty, and area is not something this
#  chart measures. **A uniform field is one flat colour**; a gradient or a hot corner is
#  the non-uniformity, and you can see *where* it is.
#
#Both print the numbers rather than a verdict: **range** (peak-to-peak),
#**range %** and **CV %** of the mean, and the trend **slope per 100 px**. CSV
#export carries each ROI's `center_x` / `center_y`, so the same profile replots
#anywhere.
#
#**Double-click any ROI** for a **pixel inspector** in its own window: a
#false-colour view of the patch, its grey-level histogram, and horizontal /
#vertical intensity profiles.
#
### Highlights
#
#- Fully **offline** — no network, no telemetry, all computation local.
#- **Project save / open (JSON)** — persist groups, ROIs, metrics, and view state (overlay toggles, heat opacity and locked range, ROI
#  list order, chart titles / axis names / ticks / locked scales, the chart type
#  and position axis);
#  reopen to pick up where you left off.
#- Open one 8-bit grayscale image (TIFF/PNG/JPG/BMP); 16-bit/RGB inputs are
#  normalized to 8-bit grayscale on load (CJK-path safe IO).
#- Hover an ROI on the canvas or in the list — the other side highlights in sync.
#- The status bar keeps the headline numbers — groups, ROIs, and the shown
#  metric's mean, range and CV — so the figure you keep glancing at does not
#  need the Analysis window opened for it.
#- Analysis runs **off the UI thread** (debounced), so placing many ROIs stays
#  responsive.
#- Calm **light instrument theme** with a single amber accent and system-safe fonts.
#
### Install & run
#
#**Windows, one click** — double-click **`install.bat`**. It makes a virtual
#environment in `.venv`, installs the three dependencies, checks they import,
#draws the icon, and puts a **PEAR** shortcut on the Desktop and in the Start
#Menu. Afterwards, start it from that shortcut or from **`PEAR.bat`** (no
#console window). If pip cannot reach the network — the usual case on a fab
#PC — drop the wheels into a `wheels\` folder beside `install.bat` and it
#installs from there instead:
#
#```bat
#pip download -r requirements.txt -d wheels     :: on a machine with internet
#install.bat                                    :: on the fab PC
#install.bat --run                              :: …and launch it
#```
#
#The batch files are three lines each; everything that can go wrong lives in
#`tools/install_windows.py`, where it can say what went wrong.
#
#**Anywhere else:**
#
#```bash
#pip install -r requirements.txt
#python -m pear
#```
#
#Generate a synthetic sample to try the tool without real fab data:
#
#```bash
#python examples/make_sample.py     # writes examples/sample_field.png
#python -m pear                     # then Load… the generated image
#```
#
### The icon
#
#`tools/make_icon.py` draws it — a measurement grid of nine cells across the
#app's own heat ramp with one ROI ringed in white — and writes a seven-size
#`pear.ico` (16 … 256 px). `install.bat` runs it; the app and the PyInstaller
#build pick it up when it is there.
#
#It is generated rather than committed on purpose: the repo travels to the
#offline machine as **one plain-text file**, and that bundle takes text only,
#so the icon ships as the QPainter code that draws it.
#
#```bash
#python tools/make_icon.py                      # -> pear.ico
#python tools/make_icon.py --png preview.png    # …and a PNG to look at
#```
#
### Build a standalone executable
#
#```bash
#pip install pyinstaller
#pyinstaller pear.spec               # -> dist/PEAR/  (uses pear.ico if drawn)
#```
#
### Tests
#
#```bash
#pip install pytest
#pytest                              # headless core + offscreen UI smoke
#```
#
#- `tests/test_core.py` — headless (no Qt): ROI patch/metrics,
#  grid interpolation, outlier detection, heat colormap, heat-map cell edges,
#  jitter tolerance (field tiling and profile grouping alike), per-ROI field
#  cells, ROI alignment / spacing, the flat ROI interchange list,
#  attribute separability / ranking, pixel histogram, ROI positions / linear
#  trend / uniformity, project (de)serialize, between/within comparison,
#  snapshot isolation.
#- `tests/test_bundle.py` — the single-file text bundle round-trips byte for
#  byte, survives CRLF, catches tampering, and is not stale; the batch files
#  stay flat enough to run with LF endings.
#- `tests/test_ui_smoke.py` — offscreen: full UI path, three add modes, marquee
#  select, ROI import / export with its size choice, ROI re-indexing, heatmap/outliers, hover sync, keyboard
#  shortcuts, chart toggles, ranking/heatmap render, ROI inspector, project
#  save/open, CSV export, image export of every view (field at native
#  resolution, each results section, the ROI inspector),
#  histogram bins / percent / tick steps,
#  chart aspect, position profile + heat map (cells / dots / values),
#  independent ROI overlay toggles (boxes and field each on their own), the
#  heat-map lattice, value-label fitting, fit across
#  a resize, ROI list values / ordering, align buttons, status headline,
#  per-lane box scale, chart settings (titles, axis names, ticks, locked value
#  and heat scales), the generated icon (every Windows size, readable back),
#  list rebuilds leaving no stale rows.
#
### Repository layout
#
#```
#pear/
#  install.bat      # one-click Windows install (calls tools/install_windows.py)
#  PEAR.bat         # launcher, no console window
#  pear/
#    core/          # pure NumPy/OpenCV, ZERO Qt imports (headless-testable)
#      attributes.py                 # GLV statistics
#      analysis.py                   # group/ROI model, geometry, metric collection
#    ui/            # all Qt (theme, image_view, widgets, main_window)
#                   #   widgets.py: rail, stage bar, charts, inspector
#  tests/
#  examples/        # make_sample.py
#  tools/           # make_text_bundle.py — pack the repo into one text file
#  bundle/          # pear_bundle.py — that pack (regenerate after every change)
#  docs/            # NO-GIT-SETUP.md — install where downloads are blocked
#```
#
### Offline install (no git, downloads blocked)
#
#Where the machine cannot download anything but can copy from GitHub, the whole
#repo travels as **one plain-text `.py`** that unpacks itself — see
#[`docs/NO-GIT-SETUP.md`](docs/NO-GIT-SETUP.md). Regenerate it after every
#change, or the other machine silently gets old code:
#
#```bash
#git add -A && python tools/make_text_bundle.py && git add -A
#```
#
### Scope (V1)
#
#In scope: single image, ROI groups, additive/editable ROIs (click / drag /
#grid / box-select / align / import), GLV metrics, value heatmap + outlier
#flagging with per-overlay toggles and a field fill, attribute ranking +
#group×metric heatmap, image export of every view (PNG / SVG),
#per-ROI pixel inspector,
#between-group and within-group comparison in a separate window (box, histogram,
#position profile, or spatial heat map), project save/open, CSV export.
#
#Out of scope: defect detection/decision, classification, ML; batch processing.
#
#F 1281348ac68aee93d47d2cc19ced138a10504273 125 docs/NO-GIT-SETUP.md
## 在沒有 git、也下載不了東西的機器上安裝 PEAR
#
#適用情境：**公司機不能用 git，而且下載被擋** —— `.zip` 這個類別過不了，proxy
#也不讓 Python 逐檔抓，但**看得到 GitHub 上的檔案而且可以按複製鈕**。
#
#整個 PEAR repo 只有純文字檔（`.py` / `.md` / `.toml` / `.txt` / `.spec`），
#沒有任何執行檔或二進位檔，所以不需要 git 也能跑。
#
#---
#
### 1. 用剪貼簿搬整包（一個檔案）
#
#`bundle/pear_bundle.py` —— **一次複製就搬完整個 repo**（目前約 215 KB、19 個
#檔案）。它是純文字，記事本打開就讀得到內容，沒有壓縮也沒有編碼。
#
#1. 瀏覽器打開
#   <https://github.com/hxlub0905-cmyk/PEAR/blob/main/bundle/pear_bundle.py>
#2. 按檔案右上角的**複製鈕**（或直接複製 raw：把網址的 `blob` 換成 `raw`）
#3. 貼進記事本，存成 `pear_bundle.py`
#4. `python pear_bundle.py --list` ← 先看它會寫哪些檔案，**不寫任何東西**
#5. `python pear_bundle.py` ← 真的解開
#
#> ### ⚠ 記事本另存的時候會偷加 `.txt`
#>
#> 它的「存檔類型」預設是「文字文件 (\*.txt)」，所以你打 `pear_bundle.py` 會被
#> 存成 `pear_bundle.py.txt` —— 而檔案總管預設**把已知副檔名藏起來**，看起來完
#> 全正常，只有 Python 會說「No such file or directory」。
#>
#> 避開的方式：另存對話框裡把**存檔類型改成「所有檔案 (\*.\*)」**，或是**檔名
#> 前後加引號**：`"pear_bundle.py"`。
#>
#> 已經存錯了也不用改名 —— Python 不在乎副檔名，直接
#> `python pear_bundle.py.txt` 就會動。
#
#每個檔案都帶 **git blob SHA-1**，解開時逐檔驗過才落地。傳輸途中被動到（編輯器
#另存、郵件過濾器改寫）會當場報出來，不會讓你拿到一份安靜壞掉的程式碼。
#
#**行尾被換成 CRLF 不影響**：這個格式用「行數」而不是「位元組數」框住每個檔案，
#正是為了這件事。
#
#---
#
### 2. 裝相依套件
#
#```
#cd pear
#pip install -r requirements.txt
#```
#
#需要 `PySide6`、`opencv-python`、`numpy`。
#
#pip 也被擋的話，走離線 wheels：在有網路的機器上
#`pip download -r requirements.txt -d wheels`，把 `wheels/` 搬過去（這些是二進位
#檔，如果連 wheel 都搬不進去，就只能請 IT 開放），然後
#`pip install --no-index --find-links wheels -r requirements.txt`。
#
#---
#
### 3. 跑起來
#
#```
#python -m pear
#```
#
#沒有真實資料想先試用的話：
#
#```
#python examples/make_sample.py     # 產 examples/sample_field.png
#python -m pear                     # 然後 Load… 那張圖
#```
#
#---
#
### 3.5 一鍵安裝（Windows）
#
#解開之後，**點兩下 `install.bat`** 就好。它會：
#
#1. 在 `.venv` 建一個虛擬環境（建不起來就退回裝進現在這個 Python）
#2. 裝三個相依套件 —— **如果旁邊有 `wheels\` 資料夾就從那裡裝**（離線機的重點）
#3. 驗證 `numpy` / `opencv-python` / `PySide6` 真的 import 得起來
#4. 畫出 `pear.ico`
#5. 在桌面與開始功能表建立 **PEAR** 捷徑（用 `cscript`，不需要 PowerShell）
#
#之後從桌面捷徑或 `PEAR.bat` 啟動，不會有黑色主控台視窗。
#
#離線機沒有下載管道時，先在**有網路的機器**上：
#
#```
#pip download -r requirements.txt -d wheels
#```
#
#把 `wheels\` 整個資料夾一起帶過去，放在 `install.bat` 旁邊即可。
#
#> `.bat` 只有三行、而且刻意不用括號區塊與 `goto` —— 因為這個包全部是 LF 換行，
#> 而 `cmd.exe` 對 LF 換行的批次檔在遇到區塊或 `goto` 時會出怪事。真正的邏輯在
#> `tools/install_windows.py` 裡，出錯時它講得出原因。
#
#---
#
### 4. 確認解出來的東西是完整的
#
#```
#python -m pytest tests/test_core.py -q
#```
#
#這一支不需要圖形環境。全部測試（含 UI）要 `QT_QPA_PLATFORM=offscreen`，
#Linux 上另外需要 `libegl1` / `libgl1` 等系統函式庫。
#
#---
#
### 5. 之後要更新程式碼
#
#重複第 1 節就好 —— 重新複製一次 `bundle/pear_bundle.py`，解到同一個資料夾會直
#接覆蓋。解包是 atomic 的（先寫 `.tmp` 再 `os.replace`），中途失敗不會在磁碟上
#留下半個檔案。
#
#> 在**有 git 的那台機器**改完程式碼之後，記得重產這個包：
#>
#> ```
#> git add -A && python tools/make_text_bundle.py && git add -A
#> ```
#>
#> 忘了的話公司機拿到的會是舊的程式碼，而且**在開發機上完全沒有症狀**。
#> `tests/test_bundle.py` 會在包過期時變紅。
#
#F b59f819a7210abc9120045298c7fe4d80cf4e1c6 73 examples/make_sample.py
#"""Synthetic sample generator.
#
#Writes ``sample_field.png``: a field of identical repeating cells, each a
#noisy background with a bright feature block, plus a few injected
#"outlier" cells whose feature is dimmer and noisier. Real fab imagery
#cannot be bundled; this lets PEAR be exercised end-to-end without it.
#
#Run: ``python examples/make_sample.py``
#"""
#
#from __future__ import annotations
#
#import os
#from typing import List, Tuple
#
#import cv2
#import numpy as np
#
## Field geometry.
#N_COLS, N_ROWS = 12, 9
#CELL_W, CELL_H = 64, 52
#BG_LEVEL = 70
#FEATURE_LEVEL = 185
#BG_NOISE = 6.0
#FEATURE_NOISE = 5.0
#
## Injected outlier cells (col, row).
#OUTLIERS: List[Tuple[int, int]] = [(2, 1), (7, 3), (4, 6), (10, 7)]
#
#
#def _make_cell(rng: np.random.Generator, outlier: bool) -> np.ndarray:
#    """One cell: noisy background + a centered bright feature block."""
#    cell = rng.normal(BG_LEVEL, BG_NOISE, size=(CELL_H, CELL_W))
#    # Feature block occupies the central region of the cell.
#    fy0, fy1 = CELL_H // 4, CELL_H * 3 // 4
#    fx0, fx1 = CELL_W // 4, CELL_W * 3 // 4
#    if outlier:
#        level, noise = FEATURE_LEVEL - 70, FEATURE_NOISE * 3.0
#    else:
#        level, noise = FEATURE_LEVEL, FEATURE_NOISE
#    fh, fw = fy1 - fy0, fx1 - fx0
#    cell[fy0:fy1, fx0:fx1] = rng.normal(level, noise, size=(fh, fw))
#    return np.clip(cell, 0, 255)
#
#
#def make_field(seed: int = 7) -> np.ndarray:
#    """Build the full synthetic field as a uint8 grayscale image."""
#    rng = np.random.default_rng(seed)
#    out = np.zeros((N_ROWS * CELL_H, N_COLS * CELL_W), dtype=np.float64)
#    outlier_set = set(OUTLIERS)
#    for row in range(N_ROWS):
#        for col in range(N_COLS):
#            cell = _make_cell(rng, (col, row) in outlier_set)
#            y0, x0 = row * CELL_H, col * CELL_W
#            out[y0:y0 + CELL_H, x0:x0 + CELL_W] = cell
#    return np.clip(out, 0, 255).astype(np.uint8)
#
#
#def main() -> None:
#    img = make_field()
#    here = os.path.dirname(os.path.abspath(__file__))
#    path = os.path.join(here, "sample_field.png")
#    cv2.imwrite(path, img)
#    print(f"wrote {path}  ({img.shape[1]}x{img.shape[0]} px, "
#          f"period {CELL_W}x{CELL_H})")
#    print("injected outlier cells (col, row):")
#    for (c, r) in OUTLIERS:
#        print(f"  col={c}, row={r}")
#
#
#if __name__ == "__main__":
#    main()
#
#F 868f29341078d1e98a9e1e081a9d7521f8465590 7 install.bat
#@echo off
#rem PEAR one-click install. Everything happens in tools\install_windows.py --
#rem this file stays flat (no blocks, no goto) so it works with LF endings,
#rem which the plain-text bundle requires.
#py -3 "%~dp0tools\install_windows.py" %* || python "%~dp0tools\install_windows.py" %*
#pause
#
#F cd6991919b64aeefc870c285a56c23bdc3106ad0 74 pear.spec
## -*- mode: python ; coding: utf-8 -*-
#"""PyInstaller spec — one-folder, windowed build of PEAR.
#
#Build:  pyinstaller pear.spec
#Output: dist/PEAR/   (zip the folder to deploy to a machine without Python)
#"""
#
#import os
#
#from PyInstaller.utils.hooks import collect_submodules
#
#block_cipher = None
#
## Drawn by tools/make_icon.py (install.bat runs it); absent in a fresh clone.
#_icon = os.path.join(os.path.abspath(SPECPATH), "pear.ico")
#icon = _icon if os.path.exists(_icon) else None
#
#hiddenimports = collect_submodules("pear")
#
## Trim heavy Qt modules PEAR never uses, plus unrelated frameworks.
#excludes = [
#    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
#    "PySide6.QtWebEngine", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
#    "PySide6.Qt3DExtras", "PySide6.Qt3DInput", "PySide6.Qt3DAnimation",
#    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
#    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
#    "matplotlib", "tkinter", "PyQt5", "PyQt6", "scipy",
#]
#
#a = Analysis(
#    ["pear/__main__.py"],
#    pathex=[],
#    binaries=[],
#    datas=[],
#    hiddenimports=hiddenimports,
#    hookspath=[],
#    hooksconfig={},
#    runtime_hooks=[],
#    excludes=excludes,
#    win_no_prefer_redirects=False,
#    win_private_assemblies=False,
#    cipher=block_cipher,
#    noarchive=False,
#)
#pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
#
#exe = EXE(
#    pyz,
#    a.scripts,
#    [],
#    exclude_binaries=True,
#    name="PEAR",
#    debug=False,
#    bootloader_ignore_signals=False,
#    strip=False,
#    upx=False,
#    console=False,
#    disable_windowed_traceback=False,
#    target_arch=None,
#    codesign_identity=None,
#    entitlements_file=None,
#    icon=icon,
#)
#coll = COLLECT(
#    exe,
#    a.binaries,
#    a.zipfiles,
#    a.datas,
#    strip=False,
#    upx=False,
#    upx_exclude=[],
#    name="PEAR",
#)
#
#F b0af88ccdd248b922089a2a6a561627d6faff696 9 pear/__init__.py
#"""PEAR — Pre-EBI Attribute Ranker.
#
#A pre-inspection attribute-discovery tool for electron-beam-inspection (EBI)
#of repeating-cell structures. PEAR ranks and reports; it does not detect,
#classify, or decide.
#"""
#
#__version__ = "0.1.0"
#
#F 5d4e8b6fc182ef89efee5d4e19e3fb2c00a8f81d 59 pear/__main__.py
#"""Entry point: ``python -m pear`` (and the ``pear`` console script)."""
#
#from __future__ import annotations
#
#import sys
#
#
#def app_icon():
#    """The icon ``tools/make_icon.py`` drew, if it has been run.
#
#    It is generated rather than committed — the offline machine gets the repo
#    as one plain-text file, which takes no binaries — so its absence is normal
#    and never fatal.
#    """
#    import os
#
#    from PySide6.QtGui import QIcon
#
#    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#    for name in ("pear.ico", "pear_icon.png"):
#        path = os.path.join(root, name)
#        if os.path.exists(path):
#            icon = QIcon(path)
#            if not icon.isNull():
#                return icon
#    return None
#
#
#def main() -> int:
#    """Launch the PEAR desktop application."""
#    # Import lazily so that importing the package (e.g. for ``--version``)
#    # does not require a Qt display.
#    if "--version" in sys.argv:
#        from pear import __version__
#
#        print(f"PEAR {__version__}")
#        return 0
#
#    from PySide6.QtGui import QIcon
#    from PySide6.QtWidgets import QApplication
#
#    from pear.ui.main_window import MainWindow
#    from pear.ui.theme import apply_theme
#
#    app = QApplication.instance() or QApplication(sys.argv)
#    app.setApplicationName("PEAR")
#    apply_theme(app)
#    icon = app_icon()
#    if icon is not None:
#        app.setWindowIcon(icon)
#
#    win = MainWindow()
#    win.show()
#    return app.exec()
#
#
#if __name__ == "__main__":
#    raise SystemExit(main())
#
#F 2efd69f74fc456741a297efd7f7cca343ca2526b 2 pear/core/__init__.py
#"""Pure NumPy/OpenCV core for PEAR — ZERO Qt imports (headless-testable)."""
#
#F ace879293e523188fd812c9bbb2ffe4067783602 777 pear/core/analysis.py
#"""Data model, geometry, and analysis orchestration.
#
#Pure NumPy/OpenCV — no Qt.
#
#Model
#-----
#* **Group** — a *category* of features (e.g. "round holes", "square holes").
#* **ROI**   — a rectangle placed on the image that belongs to one group. A
#  group holds many ROIs. Each ROI is measured independently.
#
#Analysis compares the distribution of a metric across every ROI in a group,
#either *between* groups or *within* a single group.
#
#Metrics
#-------
#GLV statistics come from each ROI patch.
#"""
#
#from __future__ import annotations
#
#from dataclasses import dataclass, field
#from typing import Dict, List, Optional, Tuple
#
#import cv2
#import numpy as np
#
#from pear.core.attributes import glv_value
#
#Rect = Tuple[int, int, int, int]      # (x, y, w, h) in image pixels
#
## Categorical palette for groups (cycles).
## No amber in here: amber is the brand accent (trend lines) and the midpoint
## of the heat ramp, so a group wearing it reads as a value off the scale.
#GROUP_PALETTE: List[str] = [
#    "#0D9488", "#2563EB", "#16A34A", "#DB2777", "#7C3AED",
#    "#0891B2", "#B45309", "#4B5563",
#]
#
## Sequential ramp for the metric heatmap: cool → amber → warm.
#_HEAT_STOPS = [(0.0, (37, 99, 235)), (0.5, (245, 158, 11)), (1.0, (220, 38, 38))]
#
#
#def heat_color(t: float) -> str:
#    """Map ``t`` in [0, 1] to a hex colour on the blue → amber → red ramp."""
#    if not np.isfinite(t):
#        return "#4B5563"
#    t = 0.0 if t < 0 else (1.0 if t > 1 else float(t))
#    for i in range(len(_HEAT_STOPS) - 1):
#        t0, c0 = _HEAT_STOPS[i]
#        t1, c1 = _HEAT_STOPS[i + 1]
#        if t <= t1:
#            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
#            r, g, b = (round(a + (b - a) * f) for a, b in zip(c0, c1))
#            return f"#{r:02X}{g:02X}{b:02X}"
#    return "#DC2626"
#
#
#@dataclass
#class ROI:
#    """A measurement rectangle belonging to one group."""
#
#    rid: int
#    gid: str
#    rect: Rect
#    label: str = ""
#
#
#@dataclass
#class Group:
#    """A category of ROIs — "round holes", "square holes"."""
#
#    gid: str
#    name: str
#    color: str
#
#
## --------------------------------------------------------------------------- #
## Image IO (CJK-path safe)
## --------------------------------------------------------------------------- #
#def load_image(path: str) -> np.ndarray:
#    """Load an image as 8-bit single-channel grayscale (CJK-path safe)."""
#    data = np.fromfile(path, dtype=np.uint8)
#    if data.size == 0:
#        raise IOError(f"could not read file: {path}")
#    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
#    if img is None:
#        raise IOError(f"could not decode image: {path}")
#    if img.ndim == 3:
#        if img.shape[2] == 4:
#            img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
#        else:
#            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#    if img.dtype != np.uint8:
#        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
#    return img
#
#
## --------------------------------------------------------------------------- #
## ROI patch + metrics
## --------------------------------------------------------------------------- #
#def roi_patch(image: np.ndarray, rect: Rect) -> Optional[np.ndarray]:
#    """Clipped ROI patch, or None if it lies fully outside the image."""
#    x, y, w, h = rect
#    ih, iw = image.shape[:2]
#    x0, y0 = max(0, x), max(0, y)
#    x1, y1 = min(iw, x + w), min(ih, y + h)
#    if x1 <= x0 or y1 <= y0:
#        return None
#    return image[y0:y1, x0:x1]
#
#
#def roi_metric(image: np.ndarray, roi: ROI, mid: str) -> float:
#    """One GLV statistic of one ROI."""
#    p = roi_patch(image, roi.rect)
#    return glv_value(p, mid) if p is not None else 0.0
#
#
#def group_rois(rois: List[ROI], gid: str) -> List[ROI]:
#    return [r for r in rois if r.gid == gid]
#
#
#def group_values(image: np.ndarray, rois: List[ROI], mid: str) -> np.ndarray:
#    return np.asarray([roi_metric(image, r, mid) for r in rois],
#                      dtype=np.float64)
#
#
#def group_outliers(image: np.ndarray, rois: List[ROI], mid: str,
#                   k: float = 1.5) -> set:
#    """rids that are Tukey outliers of ``mid`` *within their own group*.
#
#    A value outside ``[Q1 − k·IQR, Q3 + k·IQR]`` is an outlier. Groups with
#    fewer than 4 ROIs (too few for a stable IQR) are skipped.
#    """
#    out: set = set()
#    by_gid: Dict[str, List[ROI]] = {}
#    for r in rois:
#        by_gid.setdefault(r.gid, []).append(r)
#    for grs in by_gid.values():
#        if len(grs) < 4:
#            continue
#        vals = np.array([roi_metric(image, r, mid) for r in grs],
#                        dtype=np.float64)
#        q1, q3 = float(np.percentile(vals, 25)), float(np.percentile(vals, 75))
#        iqr = q3 - q1
#        if iqr <= 1e-12:
#            continue
#        lo, hi = q1 - k * iqr, q3 + k * iqr
#        for r, v in zip(grs, vals):
#            if v < lo or v > hi:
#                out.add(r.rid)
#    return out
#
#
#def cohens_d(a, b) -> Optional[float]:
#    """Standardized mean difference (a − b) / pooled_sd. None if degenerate."""
#    a = np.asarray(a, dtype=np.float64)
#    a = a[np.isfinite(a)]
#    b = np.asarray(b, dtype=np.float64)
#    b = b[np.isfinite(b)]
#    if a.size < 2 or b.size < 2:
#        return None
#    na, nb = a.size, b.size
#    sp2 = ((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)
#    sp = float(np.sqrt(sp2))
#    if sp < 1e-12:
#        return None
#    return float((a.mean() - b.mean()) / sp)
#
#
#def attribute_separability(groups_vals) -> Optional[float]:
#    """η² (variance of a metric explained by group) in [0, 1]; higher = better
#    separation between groups. Needs 2+ non-empty groups with spread."""
#    arrs = [np.asarray(v, dtype=np.float64) for v in groups_vals]
#    arrs = [a[np.isfinite(a)] for a in arrs]
#    arrs = [a for a in arrs if a.size]
#    if len(arrs) < 2:
#        return None
#    allv = np.concatenate(arrs)
#    if allv.size < 2:
#        return None
#    grand = float(allv.mean())
#    ss_total = float(((allv - grand) ** 2).sum())
#    if ss_total < 1e-12:
#        return 0.0
#    ss_between = float(sum(a.size * (float(a.mean()) - grand) ** 2 for a in arrs))
#    return max(0.0, min(1.0, ss_between / ss_total))
#
#
#def pixel_hist(patch, bins: int = 32):
#    """Grey-level histogram of a patch over the full 0–255 range."""
#    p = np.asarray(patch).ravel()
#    if p.size == 0:
#        return np.zeros(bins, dtype=int), np.linspace(0, 255, bins + 1)
#    return np.histogram(p, bins=bins, range=(0, 255))
#
#
#def summarize(values: np.ndarray) -> Dict[str, float]:
#    v = np.asarray(values, dtype=np.float64)
#    v = v[np.isfinite(v)]
#    if v.size == 0:
#        return {"n": 0, "mean": 0.0, "std": 0.0, "median": 0.0,
#                "q25": 0.0, "q75": 0.0, "min": 0.0, "max": 0.0}
#    return {"n": int(v.size), "mean": float(v.mean()), "std": float(v.std()),
#            "median": float(np.median(v)), "q25": float(np.percentile(v, 25)),
#            "q75": float(np.percentile(v, 75)), "min": float(v.min()),
#            "max": float(v.max())}
#
#
## --------------------------------------------------------------------------- #
## Position profile — GLV against where the ROI sits on the image
## --------------------------------------------------------------------------- #
#def roi_center(rect: Rect) -> Tuple[float, float]:
#    """Centre of an ROI rectangle, in image pixels."""
#    x, y, w, h = rect
#    return (x + w / 2.0, y + h / 2.0)
#
#
#def group_positions(rois: List[ROI], axis: str = "x") -> np.ndarray:
#    """Each ROI's centre coordinate along ``axis`` ("x" or "y"), in pixels.
#
#    Ordering matches :func:`group_values`, so a value and its position share
#    an index.
#    """
#    i = 1 if str(axis).lower() == "y" else 0
#    return np.asarray([roi_center(r.rect)[i] for r in rois], dtype=np.float64)
#
#
#def linear_trend(x, y) -> Optional[Tuple[float, float]]:
#    """Least-squares ``(slope, intercept)`` of y on x, or None if degenerate.
#
#    The slope is the tilt of a GLV-vs-position profile: 0 means flat.
#    """
#    x = np.asarray(x, dtype=np.float64)
#    y = np.asarray(y, dtype=np.float64)
#    m = np.isfinite(x) & np.isfinite(y)
#    x, y = x[m], y[m]
#    if x.size < 2 or float(x.std()) < 1e-12:
#        return None
#    sx, sy = float(x.mean()), float(y.mean())
#    dx = x - sx
#    denom = float((dx * dx).sum())
#    if denom < 1e-12:
#        return None
#    slope = float((dx * (y - sy)).sum() / denom)
#    return slope, float(sy - slope * sx)
#
#
#def uniformity(values) -> Dict[str, float]:
#    """How flat a metric is across ROIs — the numbers, no verdict.
#
#    ``range`` is peak-to-peak (0 for a perfectly flat profile); ``range_pct``
#    and ``cv_pct`` express spread as a percentage of the mean, which is how
#    grey-level uniformity is usually quoted.
#    """
#    v = np.asarray(values, dtype=np.float64)
#    v = v[np.isfinite(v)]
#    if v.size == 0:
#        return {"n": 0, "mean": 0.0, "range": 0.0, "range_pct": 0.0,
#                "std": 0.0, "cv_pct": 0.0}
#    mean = float(v.mean())
#    rng = float(v.max() - v.min())
#    sd = float(v.std())
#    den = abs(mean)
#    return {"n": int(v.size), "mean": mean, "range": rng,
#            "range_pct": (rng / den * 100.0) if den > 1e-12 else 0.0,
#            "std": sd,
#            "cv_pct": (sd / den * 100.0) if den > 1e-12 else 0.0}
#
#
#def jitter_tolerance(sorted_unique) -> float:
#    """How far apart two centres can be and still be the same row or column.
#
#    Hand-placed ROIs land a few pixels off each other, so a row of eight is
#    really eight tight knots of positions, not eight positions. Sort the gaps
#    between neighbouring centres and there is a step change between the
#    within-knot gaps (a few px) and the pitch between knots (tens of px); the
#    tolerance sits in that step. Returns 0 when the gaps have no such split —
#    a genuine scatter is not jitter and must not be merged.
#    """
#    a = np.asarray(sorted_unique, dtype=np.float64)
#    if a.size < 3:
#        return 0.0
#    gaps = np.sort(np.diff(a))
#    gaps = gaps[gaps > 0]
#    if gaps.size < 2:
#        return 0.0
#    ratios = gaps[1:] / np.maximum(gaps[:-1], 1e-9)
#    i = int(np.argmax(ratios))
#    # Evidence for jitter, not a sparse layout: the step has to be a real
#    # step (4x), and there has to be a population of small gaps below it —
#    # one small gap among large ones is a missing ROI, not a wobble.
#    if i < 1 or ratios[i] < 4.0:
#        return 0.0
#    # the log-middle of the step: comfortably above every jitter gap, and
#    # never far enough to swallow a whole pitch
#    return float(np.sqrt(gaps[i] * gaps[i + 1]))
#
#
#def cluster_positions(positions, tol: float):
#    """Collapse centres within ``tol`` of their neighbour into one position.
#
#    The representative is the cluster's mean, so a row that wobbles by a pixel
#    or two lands on the row it was meant to be.
#    """
#    a = np.sort(np.asarray(positions, dtype=np.float64))
#    if a.size == 0:
#        return np.empty(0)
#    if tol <= 0:
#        return np.unique(a)
#    out, start = [], 0
#    for i in range(1, a.size + 1):
#        if i == a.size or a[i] - a[i - 1] > tol:
#            out.append(float(a[start:i].mean()))
#            start = i
#    return np.asarray(out, dtype=np.float64)
#
#
#def cell_edges(positions, decimals: int = 3, tol: Optional[float] = None):
#    """Tiling boundaries for ROI centres along one axis.
#
#    Returns ``(centres, edges)``: the distinct centres, sorted, and the
#    ``len(centres) + 1`` boundaries midway between neighbours, the outermost
#    pair mirrored outward by half of the adjacent gap. Drawing each ROI from
#    its lower to its upper edge tiles the axis exactly — no hairline gaps
#    where centres landed on rounded pixels, no overlap where the spacing is
#    uneven; a lone gap in the layout simply gives that ROI a wider cell.
#
#    Centres within ``tol`` of each other count as one row or column, so a grid
#    placed by hand tiles as the grid it is rather than shattering into a
#    sliver per stray pixel. ``tol=None`` measures it from the data
#    (:func:`jitter_tolerance`); pass 0 to keep every distinct centre.
#
#    A single distinct centre has no neighbour to measure against and gets a
#    one-pixel cell; the caller substitutes a size of its own.
#    """
#    a = np.asarray(positions, dtype=np.float64)
#    a = a[np.isfinite(a)]
#    if a.size == 0:
#        return np.empty(0), np.empty(0)
#    a = np.round(a, decimals)
#    if tol is None:
#        tol = jitter_tolerance(np.unique(a))
#    c = cluster_positions(a, tol)
#    if c.size == 1:
#        return c, np.asarray([c[0] - 0.5, c[0] + 0.5])
#    mid = (c[:-1] + c[1:]) / 2.0
#    return c, np.concatenate(([2.0 * c[0] - mid[0]], mid,
#                              [2.0 * c[-1] - mid[-1]]))
#
#
#def heat_cells(rois: List[ROI], bounds=None) -> Dict[int, Tuple[float, float,
#                                                             float, float]]:
#    """``rid -> (x0, y0, x1, y1)``: the patch of image each ROI speaks for.
#
#    The ROI boxes are the measurements; between them the field is unmeasured.
#    Painting each ROI's value across the rectangle bounded by the midlines to
#    its neighbours (:func:`cell_edges` on each axis) fills that gap with the
#    nearest actual measurement, so a gradient across the field shows up as a
#    gradient instead of a row of small tinted boxes. ``bounds = (w, h)`` clips
#    the tiling to the image.
#    """
#    if not rois:
#        return {}
#    cx = np.asarray([roi_center(r.rect)[0] for r in rois], dtype=np.float64)
#    cy = np.asarray([roi_center(r.rect)[1] for r in rois], dtype=np.float64)
#    xc, xe = cell_edges(cx)
#    yc, ye = cell_edges(cy)
#    # a single row (or column) has no pitch of its own — it borrows the other
#    # axis's, and with neither the ROI's own box is all the extent there is
#    def step(e, fallback):
#        return float(np.median(np.diff(e))) if e.size > 2 else fallback
#
#    sx = step(xe, 0.0)
#    sy = step(ye, 0.0)
#    out: Dict[int, Tuple[float, float, float, float]] = {}
#    for r, x, y in zip(rois, cx, cy):
#        w, h = float(r.rect[2]), float(r.rect[3])
#        if xe.size > 2:
#            i = int(np.abs(xc - x).argmin())
#            x0, x1 = float(xe[i]), float(xe[i + 1])
#        else:
#            half = (sy if sy > 0 else w) / 2.0
#            x0, x1 = float(x - half), float(x + half)
#        if ye.size > 2:
#            j = int(np.abs(yc - y).argmin())
#            y0, y1 = float(ye[j]), float(ye[j + 1])
#        else:
#            half = (sx if sx > 0 else h) / 2.0
#            y0, y1 = float(y - half), float(y + half)
#        if bounds:
#            bw, bh = float(bounds[0]), float(bounds[1])
#            x0, x1 = max(0.0, x0), min(bw, x1)
#            y0, y1 = max(0.0, y0), min(bh, y1)
#        out[r.rid] = (x0, y0, x1, y1)
#    return out
#
#
#def profile_by_position(positions, values, decimals: int = 0,
#                        tol: Optional[float] = None):
#    """Collapse ROIs that share a position into one mean value.
#
#    A grid of ROIs puts several boxes at the same X; averaging them gives the
#    single profile line you read flatness off. Boxes placed by hand miss that
#    shared X by a pixel or two, which splits one column into several and puts
#    a kink in the line for every one of them — so centres within ``tol`` count
#    as the same position. ``tol=None`` measures it from the data
#    (:func:`jitter_tolerance`); pass 0 to group only exact matches.
#
#    Returns ``(pos, mean)`` sorted by position.
#    """
#    px = np.asarray(positions, dtype=np.float64)
#    v = np.asarray(values, dtype=np.float64)
#    m = np.isfinite(px) & np.isfinite(v)
#    px, v = px[m], v[m]
#    if px.size == 0:
#        return np.empty(0), np.empty(0)
#    keys = np.round(px, decimals)
#    if tol is None:
#        tol = jitter_tolerance(np.unique(keys))
#    slots = cluster_positions(keys, tol)
#    if slots.size == 0:
#        return np.empty(0), np.empty(0)
#    # each ROI joins the slot it is nearest to
#    idx = np.abs(keys[:, None] - slots[None, :]).argmin(axis=1)
#    centers, means = [], []
#    for k in range(slots.size):
#        sel = idx == k
#        if not sel.any():
#            continue
#        centers.append(float(px[sel].mean()))
#        means.append(float(v[sel].mean()))
#    return (np.asarray(centers, dtype=np.float64),
#            np.asarray(means, dtype=np.float64))
#
#
## --------------------------------------------------------------------------- #
## Tidying a selection — alignment and spacing
## --------------------------------------------------------------------------- #
#ALIGN_MODES = ("left", "hcenter", "right", "top", "vcenter", "bottom")
#
#
#def align_rects(rects: List[Rect], mode: str) -> List[Rect]:
#    """Pull rectangles onto one edge (or one centre line) of their bounding box.
#
#    ROIs dropped by hand sit a few pixels off each other, which is invisible
#    until the field heat map tiles them: the cell boundaries fall midway
#    between centres, so a stray pixel of offset turns a clean grid into a
#    staircase. Order is preserved and anything under two rects is returned
#    unchanged.
#    """
#    if len(rects) < 2 or mode not in ALIGN_MODES:
#        return list(rects)
#    xs = [r[0] for r in rects]
#    ys = [r[1] for r in rects]
#    rights = [r[0] + r[2] for r in rects]
#    bottoms = [r[1] + r[3] for r in rects]
#    out: List[Rect] = []
#    for x, y, w, h in rects:
#        if mode == "left":
#            x = min(xs)
#        elif mode == "right":
#            x = max(rights) - w
#        elif mode == "hcenter":
#            x = int(round((min(xs) + max(rights)) / 2.0 - w / 2.0))
#        elif mode == "top":
#            y = min(ys)
#        elif mode == "bottom":
#            y = max(bottoms) - h
#        elif mode == "vcenter":
#            y = int(round((min(ys) + max(bottoms)) / 2.0 - h / 2.0))
#        out.append((int(x), int(y), int(w), int(h)))
#    return out
#
#
#def distribute_rects(rects: List[Rect], axis: str = "x") -> List[Rect]:
#    """Even the spacing of rect centres between the two outermost ones.
#
#    The heat map's cells are as wide as the gap to the next ROI, so uneven
#    spacing reads as cells of uneven size — a pattern in the picture that is
#    not in the measurement. Fewer than three rects have no gap to even out.
#    """
#    if len(rects) < 3:
#        return list(rects)
#    i = 1 if str(axis).lower() == "y" else 0
#    centers = [roi_center(r)[i] for r in rects]
#    order = sorted(range(len(rects)), key=lambda k: centers[k])
#    lo, hi = centers[order[0]], centers[order[-1]]
#    step = (hi - lo) / (len(rects) - 1)
#    out = list(rects)
#    for slot, k in enumerate(order):
#        x, y, w, h = rects[k]
#        want = lo + step * slot
#        if i == 0:
#            x = int(round(want - w / 2.0))
#        else:
#            y = int(round(want - h / 2.0))
#        out[k] = (int(x), int(y), int(w), int(h))
#    return out
#
#
## --------------------------------------------------------------------------- #
## Multi-add helpers
## --------------------------------------------------------------------------- #
#def grid_between(tl_center: Tuple[float, float], br_center: Tuple[float, float],
#                 rows: int, cols: int, w: int, h: int) -> List[Rect]:
#    """Grid of same-size ROIs whose *centers* interpolate between two anchors.
#
#    ``tl_center`` is the centre of the top-left corner ROI (grid[0,0]) and
#    ``br_center`` the centre of the bottom-right one (grid[rows-1,cols-1]);
#    the ``rows × cols`` centres are spaced evenly between them (matching the
#    sibling tool's ``generate_grid``). Every ROI is ``w × h``.
#    """
#    tlx, tly = tl_center
#    brx, bry = br_center
#    rows, cols = max(1, int(rows)), max(1, int(cols))
#    step_x = (brx - tlx) / (cols - 1) if cols > 1 else 0.0
#    step_y = (bry - tly) / (rows - 1) if rows > 1 else 0.0
#    out: List[Rect] = []
#    for i in range(rows):
#        for j in range(cols):
#            cx = tlx + j * step_x
#            cy = tly + i * step_y
#            out.append((int(round(cx - w / 2)), int(round(cy - h / 2)),
#                        int(w), int(h)))
#    return out
#
#
## --------------------------------------------------------------------------- #
## Comparison — pure, cached, thread-safe
## --------------------------------------------------------------------------- #
#@dataclass
#class Series:
#    label: str
#    color: str
#    values: np.ndarray
#    # Centre of each ROI, index-aligned with ``values``.
#    pos_x: Optional[np.ndarray] = None
#    pos_y: Optional[np.ndarray] = None
#
#
#@dataclass
#class Chart:
#    title: str
#    series: List["Series"] = field(default_factory=list)
#
#
#@dataclass
#class AnalysisResult:
#    subtitle: str = ""
#    empty: Optional[str] = None
#    charts: List["Chart"] = field(default_factory=list)
#    table_headers: List[str] = field(default_factory=list)
#    table_rows: List[tuple] = field(default_factory=list)
#    # between-mode extras
#    ranking: List[tuple] = field(default_factory=list)   # (label, η², cohen_d)
#    heat: Optional[dict] = None                          # group × metric matrix
#
#
#def snapshot(groups: List[Group], rois: List[ROI]):
#    """Copy the mutable model for safe use on a worker thread."""
#    gs = [Group(g.gid, g.name, g.color) for g in groups]
#    rs = [ROI(r.rid, r.gid, tuple(r.rect), r.label) for r in rois]
#    return gs, rs
#
#
## --------------------------------------------------------------------------- #
## ROI interchange — the flat list other tools speak
## --------------------------------------------------------------------------- #
#def rois_to_points(groups: List[Group], rois: List[ROI], size=None,
#                   include_size: bool = True) -> List[dict]:
#    """The ROI set as a flat list of ``{color, x, y, w, h, target}``.
#
#    One dict per ROI, positioned by its **top-left corner**, carrying the
#    colour of the group it belongs to — that colour is what a receiving tool
#    has instead of PEAR's groups, and what :func:`rois_from_points` groups by
#    on the way back.
#
#    ``w``/``h`` are PEAR's addition to the format: without them a round trip
#    silently resizes every box to whatever the size fields happen to say. Pass
#    ``include_size=False`` for a tool that carries its own box size and does
#    not expect them, or ``size=(w, h)`` to write one size for the whole set.
#    ``target`` is written as ``false`` and ignored on the way in — PEAR has no
#    target role — but it is kept so a file passes through unchanged in shape.
#    """
#    color = {g.gid: g.color for g in groups}
#    out = []
#    for r in rois:
#        x, y, w, h = r.rect
#        item = {"color": color.get(r.gid, GROUP_PALETTE[0]),
#                "x": int(x), "y": int(y)}
#        if include_size:
#            item["w"], item["h"] = ((int(size[0]), int(size[1])) if size
#                                    else (int(w), int(h)))
#        item["target"] = False
#        out.append(item)
#    return out
#
#
#def rois_from_points(items, default_w: int, default_h: int, bounds=None,
#                     start_rid: int = 1, force_size: bool = False):
#    """``(groups, rois, clamped)`` from the flat list.
#
#    Each distinct colour becomes a group, in the order the colours first
#    appear. Entries carry ``w``/``h`` when they came from PEAR and take the
#    given defaults when they did not — a list that only says where the boxes
#    go needs to be told how big they are. ``force_size`` ignores the file's
#    sizes and gives every box the defaults, for a file whose boxes are the
#    right places at the wrong size.
#
#    ``bounds = (width, height)`` keeps every box inside the image; the count
#    of boxes that had to move is returned rather than hidden, because a file
#    written against a different image is a thing worth being told about.
#    """
#    if not isinstance(items, list):
#        raise ValueError("expected a list of ROI objects")
#    groups: List[Group] = []
#    by_color: Dict[str, str] = {}
#    rois: List[ROI] = []
#    rid = int(start_rid)
#    clamped = 0
#    for i, it in enumerate(items):
#        if not isinstance(it, dict):
#            raise ValueError(f"entry {i} is not an object")
#        try:
#            x = int(round(float(it["x"])))
#            y = int(round(float(it["y"])))
#        except (KeyError, TypeError, ValueError):
#            raise ValueError(f"entry {i} has no numeric x / y") from None
#        if force_size:
#            w, h = int(default_w), int(default_h)
#        else:
#            w = int(round(float(it.get("w") or default_w)))
#            h = int(round(float(it.get("h") or default_h)))
#        w, h = max(1, w), max(1, h)
#        color = str(it.get("color") or GROUP_PALETTE[0])
#        gid = by_color.get(color)
#        if gid is None:
#            letter = (chr(ord("A") + len(groups)) if len(groups) < 26
#                      else f"G{len(groups)}")
#            gid = letter
#            by_color[color] = gid
#            groups.append(Group(gid=gid, name=f"Group {letter}", color=color))
#        if bounds:
#            bw, bh = int(bounds[0]), int(bounds[1])
#            w, h = min(w, bw), min(h, bh)
#            nx = int(np.clip(x, 0, max(0, bw - w)))
#            ny = int(np.clip(y, 0, max(0, bh - h)))
#            if (nx, ny) != (x, y):
#                clamped += 1
#            x, y = nx, ny
#        rois.append(ROI(rid=rid, gid=gid, rect=(x, y, w, h), label=""))
#        rid += 1
#    return groups, rois, clamped
#
#
## --------------------------------------------------------------------------- #
## Project (de)serialization — plain JSON-friendly dicts
## --------------------------------------------------------------------------- #
#def groups_to_json(groups: List[Group]) -> List[dict]:
#    return [{"gid": g.gid, "name": g.name, "color": g.color}
#            for g in groups]
#
#
#def rois_to_json(rois: List[ROI]) -> List[dict]:
#    return [{"rid": r.rid, "gid": r.gid, "rect": list(r.rect),
#             "label": r.label} for r in rois]
#
#
#def groups_from_json(items) -> List[Group]:
#    # ``target_rid`` may still be in an older project file; it is ignored.
#    return [Group(g["gid"], g["name"], g["color"]) for g in (items or [])]
#
#
#def rois_from_json(items) -> List[ROI]:
#    return [ROI(r["rid"], r["gid"], tuple(r["rect"]), r.get("label", ""))
#            for r in (items or [])]
#
#
#def _cell(mean: float, std: float) -> str:
#    return f"{mean:.3g} ±{std:.2g}"
#
#
#def compute_analysis(image, groups: List[Group], rois: List[ROI],
#                     metrics: List[str], mode: str, within_gid) -> AnalysisResult:
#    from pear.core.attributes import metric_label
#
#    if image is None or not metrics:
#        return AnalysisResult(empty="Load an image and add ROIs to some groups.")
#
#    cache: Dict[tuple, np.ndarray] = {}
#    pcache: Dict[str, tuple] = {}
#
#    def positions(g: Group) -> tuple:
#        """(x, y) centres of the group's ROIs, index-aligned with vals()."""
#        if g.gid not in pcache:
#            grois = group_rois(rois, g.gid)
#            pcache[g.gid] = (group_positions(grois, "x"),
#                             group_positions(grois, "y"))
#        return pcache[g.gid]
#
#    def series_of(g: Group, mid: str) -> Series:
#        px, py = positions(g)
#        return Series(g.name, g.color, vals(g, mid), px, py)
#
#    def vals(g: Group, mid: str) -> np.ndarray:
#        key = (g.gid, mid)
#        if key not in cache:
#            cache[key] = group_values(image, group_rois(rois, g.gid), mid)
#        return cache[key]
#
#    if mode == "between":
#        used = [g for g in groups if group_rois(rois, g.gid)]
#        if len(used) < 2:
#            return AnalysisResult(
#                empty="Add ROIs to two or more groups to compare.")
#        res = AnalysisResult(subtitle=f"{len(used)} groups")
#        for mid in metrics:
#            res.charts.append(Chart(metric_label(mid),
#                                    [series_of(g, mid) for g in used]))
#        res.table_headers = ["Group", "ROIs"] + [metric_label(m) for m in metrics]
#        for g in used:
#            n = len(group_rois(rois, g.gid))
#            cells = [_summ(vals(g, m)) for m in metrics]
#            res.table_rows.append((g.name, g.color, [str(n)] + cells))
#        # group × metric heatmap + attribute ranking
#        res.heat = {
#            "groups": [g.name for g in used],
#            "colors": [g.color for g in used],
#            "metrics": [metric_label(m) for m in metrics],
#            "values": [[_mean_or_nan(vals(g, m)) for m in metrics] for g in used],
#        }
#        ranking = []
#        for mid in metrics:
#            eta = attribute_separability([vals(g, mid) for g in used])
#            d = (cohens_d(vals(used[0], mid), vals(used[1], mid))
#                 if len(used) == 2 else None)
#            ranking.append((metric_label(mid), eta, d))
#        ranking.sort(key=lambda r: (r[1] is None, -(r[1] or 0.0)))
#        res.ranking = ranking
#        return res
#
#    # within a group
#    g = _by_gid(groups, within_gid) or (groups[0] if groups else None)
#    if g is None or not group_rois(rois, g.gid):
#        return AnalysisResult(empty="Add ROIs to this group first.")
#    res = AnalysisResult(
#        subtitle=f"{g.name} · {len(group_rois(rois, g.gid))} ROIs")
#    for mid in metrics:
#        res.charts.append(Chart(metric_label(mid), [series_of(g, mid)]))
#    res.table_headers = ["", "ROIs"] + [metric_label(m) for m in metrics]
#    res.table_rows.append((g.name, g.color,
#                           [str(len(group_rois(rois, g.gid)))]
#                           + [_summ(vals(g, m)) for m in metrics]))
#    return res
#
#
#def _summ(values: np.ndarray) -> str:
#    s = summarize(values)
#    if s["n"] == 0:
#        return "—"
#    if s["n"] == 1:
#        return f"{s['mean']:.3g}"
#    return _cell(s["mean"], s["std"])
#
#
#def _mean_or_nan(v) -> float:
#    v = np.asarray(v, dtype=np.float64)
#    v = v[np.isfinite(v)]
#    return float(v.mean()) if v.size else float("nan")
#
#
#def _by_gid(groups, gid):
#    for g in groups:
#        if g.gid == gid:
#            return g
#    return None
#
#F e7678129fd577f63daf4f9f08fce964a0129d47e 95 pear/core/attributes.py
#"""Metric bank — grey-level-value (GLV) statistics.
#
#Deliberately small: the tool measures **GLV statistics** of a region.
#Everything is plain NumPy and every reduction is guarded so degenerate /
#tiny patches never raise.
#
#The statistics operate on a single ROI patch. Their ids are stable strings;
#custom quantiles use the id form ``glv_q<NN>`` (e.g. ``glv_q90``).
#"""
#
#from __future__ import annotations
#
#from typing import Dict, List, Optional
#
#import numpy as np
#
## Fixed GLV statistics: id -> display label. Q25/Q75 are quantiles too, but
## are shown by default, so they live in the fixed set.
#GLV_STATS: Dict[str, str] = {
#    "glv_mean": "GLV mean",
#    "glv_median": "GLV median",
#    "glv_q25": "GLV Q25",
#    "glv_q75": "GLV Q75",
#    "glv_std": "GLV std",
#    "glv_min": "GLV min",
#    "glv_max": "GLV max",
#}
#
## Short formulas, shown as tooltips.
#GLV_FORMULAS: Dict[str, str] = {
#    "glv_mean": "mean(gray)",
#    "glv_median": "median(gray)",
#    "glv_q25": "25th percentile",
#    "glv_q75": "75th percentile",
#    "glv_std": "std(gray)",
#    "glv_min": "min(gray)",
#    "glv_max": "max(gray)",
#}
#
#def quantile_of(mid: str) -> Optional[int]:
#    """Percentile for a quantile metric id (``glv_q90`` -> 90), else None."""
#    if mid.startswith("glv_q") and mid[5:].isdigit():
#        return int(mid[5:])
#    return None
#
#
#def metric_label(mid: str) -> str:
#    """Human label for any metric id (fixed or custom quantile)."""
#    if mid in GLV_STATS:
#        return GLV_STATS[mid]
#    q = quantile_of(mid)
#    if q is not None:
#        return f"GLV Q{q}"
#    return mid
#
#
#def metric_formula(mid: str) -> str:
#    if mid in GLV_FORMULAS:
#        return GLV_FORMULAS[mid]
#    q = quantile_of(mid)
#    if q is not None:
#        return f"{q}th percentile"
#    return "—"
#
#
#def glv_value(patch: np.ndarray, mid: str) -> float:
#    """One GLV statistic of a patch. Custom quantiles (``glv_q<NN>``) work too."""
#    f = np.asarray(patch, dtype=np.float64).ravel()
#    if f.size == 0:
#        return 0.0
#    if mid == "glv_mean":
#        return float(f.mean())
#    if mid == "glv_std":
#        return float(f.std())
#    if mid == "glv_min":
#        return float(f.min())
#    if mid == "glv_max":
#        return float(f.max())
#    if mid == "glv_median":
#        return float(np.median(f))
#    q = quantile_of(mid)
#    if q is not None:
#        return float(np.percentile(f, q))
#    return 0.0
#
#
#def glv_stats(patch: np.ndarray) -> Dict[str, float]:
#    """The full fixed GLV statistic set for a patch."""
#    return {mid: glv_value(patch, mid) for mid in GLV_STATS}
#
#
#def default_metrics() -> List[str]:
#    """Metrics selected on first run."""
#    return ["glv_mean", "glv_median"]
#
#F afa940644becc78d2d6a262afdec4f08ba635fc2 2 pear/ui/__init__.py
#"""Qt UI for PEAR. All Qt imports live under this package."""
#
#F d13eca6cb50317dfe951360ded4a4ba3375f042e 937 pear/ui/image_view.py
#"""Image stage: zoom/pan and place / move / resize ROIs.
#
#ROIs belong to groups and are drawn in their group's colour.
#
#Adding ROIs (à la the sibling Perspective-Combination tool):
#  * **single** — click to drop a default box (or drag to size it).
#  * **grid**   — click the top-left, then the bottom-right anchor; a live
#                 row×col preview follows; press Enter / Add grid to commit.
#"""
#
#from __future__ import annotations
#
#from typing import List, Optional, Tuple
#
#import numpy as np
#from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
#from PySide6.QtGui import (QColor, QImage, QKeyEvent, QLinearGradient,
#                           QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent)
#from PySide6.QtWidgets import QWidget
#
#from pear.core.analysis import ROI, Group, grid_between, heat_color
#from pear.ui import theme
#
#Rect = Tuple[int, int, int, int]
#_HANDLE = 8
#_MIN_ROI = 4
#_DEFAULT = 28          # default single-ROI size (px) for a plain click
#_LEGEND_H = 58         # colour-key strip added under an exported field
#
#
#def label_rect(r: QRectF, bw: float, bh: float,
#               hovered: bool) -> Optional[QRectF]:
#    """Where a ``bw × bh`` value label goes on ROI ``r``, or None: don't draw.
#
#    Zoomed out, a label is wider than its box: printed anyway they collide
#    with each other and bury the boxes they belong to. One that does not fit
#    is dropped and comes back on zoom — except on the ROI under the cursor,
#    which floats its label above the box (below it, at the top edge of the
#    image) so a value is always one hover away.
#    """
#    cx, cy = r.center().x(), r.center().y()
#    if bw <= r.width() and bh <= r.height():
#        return QRectF(cx - bw / 2, cy - bh / 2, bw, bh)
#    if not hovered:
#        return None
#    top = r.top() - bh - 2
#    return QRectF(cx - bw / 2, top if top >= 0 else r.bottom() + 2, bw, bh)
#
#
#class ImageView(QWidget):
#    roi_created = Signal(object)            # rect (single ROI into active group)
#    grid_committed = Signal(object)         # list[rect] (a row×col grid)
#    grid_ready = Signal(bool)               # both grid anchors placed
#    roi_modified = Signal(int, object)      # rid, rect
#    roi_selected = Signal(int)              # rid
#    roi_delete_requested = Signal(int)      # rid (Delete key on selected ROI)
#    rois_selected = Signal(object)          # list[rid] (marquee multi-select)
#    rois_delete_requested = Signal(object)  # list[rid] (Delete on a selection)
#    roi_hovered = Signal(int)               # rid under the cursor (-1 = none)
#    roi_duplicate_requested = Signal(int)   # rid (Ctrl+D)
#    roi_inspect_requested = Signal(int)     # rid (double-click → pixel inspector)
#    group_index_requested = Signal(int)     # switch active group by index (1–9)
#    cursor_info = Signal(str)
#    zoom_changed = Signal(float)
#
#    def __init__(self, parent=None):
#        super().__init__(parent)
#        self.setMinimumSize(320, 240)   # the rail's width wins
#        self.setMouseTracking(True)
#        self.setFocusPolicy(Qt.StrongFocus)
#
#        self._image: Optional[np.ndarray] = None
#        self._pixmap: Optional[QPixmap] = None
#        self._scale = 1.0
#        self._offset = QPointF(0, 0)
#        self._fitted = True     # still showing the fit; a zoom or pan ends it
#
#        self._groups: List[Group] = []
#        self._active_gid: Optional[str] = None
#        self._rois: List[ROI] = []
#        self._active_rid: Optional[int] = None
#        self._selection: set = set()           # rids marquee-selected
#        self._marquee: Optional[QRectF] = None  # selection rect (image coords)
#        self._heat: dict = {}                  # rid -> hex colour (heatmap)
#        self._heat_legend: Optional[tuple] = None  # (vmin, vmax, label)
#        self._heat_alpha = 178                 # heat fill opacity (0-255)
#        self._heat_cells: dict = {}            # rid -> (x0,y0,x1,y1) image px
#        self._outliers: set = set()            # rids flagged as outliers
#        self._hover_rid: int = -1              # rid under the cursor
#        self._exporting = False                # drop the in-progress marks
#
#        self._grid_mode = False
#        self._grid_stage = 0               # 0 none · 1 have TL · 2 have TL+BR
#        self._grid_tl: Optional[QPointF] = None   # centre of top-left ROI
#        self._grid_br: Optional[QPointF] = None   # centre of bottom-right ROI
#        self._grid_rows, self._grid_cols = 3, 3
#        self._roi_w, self._roi_h = _DEFAULT, _DEFAULT   # size for click / grid
#        self._cursor_img = QPointF()
#        self._roi_values: dict = {}        # rid -> short text drawn on the ROI
#
#        self._interact: Optional[str] = None   # draw|move|resize|pan
#        self._drag_start = QPointF()
#        self._draw_rect: Optional[QRectF] = None
#        self._resize_handle: Optional[int] = None
#        self._roi_at_press: Optional[Rect] = None
#        self._pan_at_press = QPointF()
#
#    # ------------------------------------------------------------------ #
#    # public API
#    # ------------------------------------------------------------------ #
#    def set_image(self, image: np.ndarray) -> None:
#        self._image = np.ascontiguousarray(image)
#        h, w = image.shape[:2]
#        qimg = QImage(self._image.data, w, h, w, QImage.Format_Grayscale8)
#        self._pixmap = QPixmap.fromImage(qimg.copy())
#        self.fit()
#
#    def set_groups(self, groups, active_gid) -> None:
#        self._groups = groups
#        self._active_gid = active_gid
#        self.update()
#
#    def set_rois(self, rois, active_rid) -> None:
#        self._rois = rois
#        self._active_rid = active_rid
#        self.update()
#
#    def set_roi_values(self, values: dict) -> None:
#        """Map of rid -> short text drawn centred on each ROI (live metric)."""
#        self._roi_values = values or {}
#        self.update()
#
#    def set_selection(self, rids) -> None:
#        """Highlight a set of ROIs (kept in sync with the rail's selection)."""
#        self._selection = set(rids or [])
#        self.update()
#
#    def set_heatmap(self, colors: dict, legend=None, alpha: int = 178) -> None:
#        """Colour ROI fills by value: rid -> hex. legend = (vmin, vmax, label).
#
#        ``alpha`` (0-255) is how opaque the fill is — turn it down to read the
#        image under the box.
#        """
#        self._heat = colors or {}
#        self._heat_legend = legend
#        self._heat_alpha = int(np.clip(int(alpha), 0, 255))
#        self.update()
#
#    def export_image(self, path: str, scale: float = 2.0) -> Optional[str]:
#        """Save the annotated field: the image at its own resolution × ``scale``.
#
#        Not a screenshot of the stage — the view's zoom, pan and black
#        surround have nothing to do with the figure someone wants in a
#        report. The pixels are drawn at their own size and the overlays (heat,
#        cells, ROI boxes, values, flags, the colour key) on top of them, so
#        the export is as sharp as the data allows whatever the window shows.
#        """
#        if self._pixmap is None:
#            return None
#        scale = float(np.clip(scale, 0.25, 8.0))
#        w = max(1, int(round(self._pixmap.width() * scale)))
#        h = max(1, int(round(self._pixmap.height() * scale)))
#        # the colour key gets a strip of its own rather than sitting on top of
#        # the ROIs it is the key for
#        legend_h = _LEGEND_H if (self._heat_legend and self._heat) else 0
#        keep = (self._scale, self._offset)
#        self._scale, self._offset = scale, QPointF(0.0, 0.0)
#        self._exporting = True
#        try:
#            if str(path).lower().endswith(".svg"):
#                try:
#                    from PySide6.QtSvg import QSvgGenerator
#                except ImportError:
#                    return None
#                gen = QSvgGenerator()
#                gen.setFileName(path)
#                gen.setSize(QSize(w, h + legend_h))
#                gen.setViewBox(QRect(0, 0, w, h + legend_h))
#                painter = QPainter()
#                if not painter.begin(gen):
#                    return None
#                painter.fillRect(QRectF(0, 0, w, h + legend_h),
#                                 QColor(theme.STAGE))
#                self._paint_export(painter, w, h, legend_h)
#                painter.end()
#                return path
#            pm = QPixmap(w, h + legend_h)
#            pm.fill(QColor(theme.STAGE))
#            painter = QPainter(pm)
#            self._paint_export(painter, w, h, legend_h)
#            painter.end()
#            return path if pm.save(path) else None
#        finally:
#            self._scale, self._offset = keep
#            self._exporting = False
#
#    def _paint_export(self, p: QPainter, w: int, h: int,
#                      legend_h: int = 0) -> None:
#        """The field and its overlays — no cursor HUD, no marquee, no grid
#        preview: those are things you are doing, not things you measured."""
#        p.setRenderHint(QPainter.Antialiasing, True)
#        p.drawPixmap(QRectF(0, 0, w, h), self._pixmap,
#                     QRectF(self._pixmap.rect()))
#        self._paint_heat_cells(p)
#        self._paint_rois(p)
#        if legend_h:
#            self._paint_colorbar(p, QRectF(0, h, w, legend_h))
#
#    def set_heat_cells(self, cells: dict) -> None:
#        """Tile the heat across the field: rid -> (x0, y0, x1, y1) in image px.
#
#        Empty = paint the heat inside the ROI boxes only.
#        """
#        self._heat_cells = cells or {}
#        self.update()
#
#    def set_outliers(self, rids) -> None:
#        self._outliers = set(rids or [])
#        self.update()
#
#    def set_hover(self, rid: int) -> None:
#        """Highlight the hovered ROI (list → canvas hover sync)."""
#        rid = -1 if rid is None else int(rid)
#        if rid != self._hover_rid:
#            self._hover_rid = rid
#            self.update()
#
#    def set_grid_mode(self, on: bool) -> None:
#        self._grid_mode = bool(on)
#        self._reset_grid()
#        self.setFocus()
#        self.update()
#
#    def set_grid_shape(self, rows: int, cols: int) -> None:
#        self._grid_rows, self._grid_cols = max(1, rows), max(1, cols)
#        self.update()
#
#    def set_roi_size(self, w: int, h: int) -> None:
#        self._roi_w, self._roi_h = max(_MIN_ROI, int(w)), max(_MIN_ROI, int(h))
#        self.update()
#
#    def commit_grid(self) -> None:
#        if self._grid_stage == 2:
#            rects = self._grid_rects()
#            if rects:
#                self.grid_committed.emit(rects)
#        self._reset_grid()
#        self.update()
#
#    def cancel_grid(self) -> None:
#        self._reset_grid()
#        self.update()
#
#    def has_image(self) -> bool:
#        return self._image is not None
#
#    def fit(self) -> None:
#        if self._pixmap is None:
#            return
#        vw, vh = self.width(), self.height()
#        iw, ih = self._pixmap.width(), self._pixmap.height()
#        if iw == 0 or ih == 0:
#            return
#        self._scale = min(vw / iw, vh / ih) * 0.96
#        self._offset = QPointF((vw - iw * self._scale) / 2.0,
#                               (vh - ih * self._scale) / 2.0)
#        self._fitted = True
#        self.update()
#        self.zoom_changed.emit(self._scale)
#
#    def zoom_by(self, factor: float, anchor: Optional[QPointF] = None) -> None:
#        if self._image is None:
#            return
#        if anchor is None:
#            anchor = QPointF(self.width() / 2.0, self.height() / 2.0)
#        ia = self._to_image(anchor)
#        self._fitted = False
#        self._scale = float(np.clip(self._scale * factor, 0.05, 40.0))
#        self._offset = QPointF(anchor.x() - ia.x() * self._scale,
#                               anchor.y() - ia.y() * self._scale)
#        self.update()
#        self.zoom_changed.emit(self._scale)
#
#    def zoom_in(self):
#        self.zoom_by(1.25)
#
#    def zoom_out(self):
#        self.zoom_by(0.8)
#
#    def zoom_percent(self) -> int:
#        return int(round(self._scale * 100))
#
#    # ------------------------------------------------------------------ #
#    # transforms
#    # ------------------------------------------------------------------ #
#    def _to_widget(self, x, y) -> QPointF:
#        return QPointF(self._offset.x() + x * self._scale,
#                       self._offset.y() + y * self._scale)
#
#    def _to_image(self, p: QPointF) -> QPointF:
#        return QPointF((p.x() - self._offset.x()) / self._scale,
#                       (p.y() - self._offset.y()) / self._scale)
#
#    def _rect_to_widget(self, r: Rect) -> QRectF:
#        x, y, w, h = r
#        tl = self._to_widget(x, y)
#        return QRectF(tl.x(), tl.y(), w * self._scale, h * self._scale)
#
#    def _gcolor(self, gid: str) -> QColor:
#        for g in self._groups:
#            if g.gid == gid:
#                return QColor(g.color)
#        return QColor(theme.INK3)
#
#    # ------------------------------------------------------------------ #
#    # painting
#    # ------------------------------------------------------------------ #
#    def paintEvent(self, _e) -> None:
#        p = QPainter(self)
#        p.setRenderHint(QPainter.Antialiasing, True)
#        p.fillRect(self.rect(), QColor(theme.STAGE))
#        if self._pixmap is None:
#            p.setPen(QColor(theme.INK3))
#            p.drawText(self.rect(), Qt.AlignCenter,
#                       "Load an 8-bit grayscale image to begin.")
#            p.end()
#            return
#        target = QRectF(self._offset.x(), self._offset.y(),
#                        self._pixmap.width() * self._scale,
#                        self._pixmap.height() * self._scale)
#        p.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
#        self._paint_heat_cells(p)
#        self._paint_rois(p)
#        self._paint_rubberband(p)
#        self._paint_marquee(p)
#        self._paint_grid_preview(p)
#        self._paint_colorbar(p)
#        self._paint_hud(p)
#        p.end()
#
#    def _paint_heat_cells(self, p: QPainter) -> None:
#        """Heat spread over each ROI's cell, under the ROI outlines.
#
#        The ROI keeps its own box on top, so it stays visible which rectangle
#        was actually measured and which area merely carries its colour.
#        """
#        if not self._heat_cells or not self._heat:
#            return
#        p.setPen(Qt.NoPen)
#        for roi in self._rois:
#            cell = self._heat_cells.get(roi.rid)
#            heat = self._heat.get(roi.rid)
#            if cell is None or heat is None:
#                continue
#            x0, y0, x1, y1 = cell
#            tl = self._to_widget(x0, y0)
#            br = self._to_widget(x1, y1)
#            fill = QColor(heat)
#            fill.setAlpha(self._heat_alpha)
#            p.setBrush(fill)
#            p.drawRect(QRectF(tl, br))
#
#    def _paint_rois(self, p: QPainter) -> None:
#        for roi in self._rois:
#            active_grp = roi.gid == self._active_gid
#            selected = roi.rid == self._active_rid
#            in_sel = roi.rid in self._selection
#            color = self._gcolor(roi.gid)
#            r = self._rect_to_widget(roi.rect)
#            heat = self._heat.get(roi.rid)
#            if heat is not None and roi.rid in self._heat_cells:
#                fill = Qt.NoBrush                    # the cell under it is the fill
#            elif heat is not None:                   # value heatmap fill
#                fill = QColor(heat)
#                fill.setAlpha(self._heat_alpha)
#            else:
#                fill = QColor(color)
#                fill.setAlpha(90 if active_grp else 45)   # the group's tag
#            # The outline is always neutral ink over a white halo. Colour on
#            # this stage means a value — the heat ramp — so a box wearing its
#            # group's colour reads as a reading off the scale; and a neutral
#            # rule is legible on a black stage, on a bright feature and on any
#            # colour of the ramp alike. The group shows in the fill tint.
#            width = 2.4 if selected else (1.8 if active_grp else 1.2)
#            p.setBrush(fill)
#            p.setPen(Qt.NoPen)
#            p.drawRect(r)
#            self._stroke_neutral(p, r, width, dashed=False, strong=active_grp)
#            if roi.rid == self._hover_rid and not self._exporting:
#                self._paint_hover_ring(p, r)
#            if in_sel and not self._exporting:
#                self._paint_selection_ring(p, r)
#            if roi.rid in self._outliers:
#                self._paint_outlier(p, r)
#            val = self._roi_values.get(roi.rid)
#            if val is not None:
#                self._paint_value(p, r, val, roi.rid == self._hover_rid)
#            if selected and not self._grid_mode and not self._exporting:
#                self._paint_handles(p, r, color)
#
#    def _stroke_neutral(self, p: QPainter, r: QRectF, width: float,
#                        dashed: bool = False, strong: bool = True) -> None:
#        """Outline that stays legible on any fill: white halo, dark ink on top."""
#        p.setBrush(Qt.NoBrush)
#        halo = QPen(QColor(255, 255, 255, 190), width + 2.0)
#        halo.setCosmetic(True)
#        p.setPen(halo)
#        p.drawRect(r)
#        ink = QPen(QColor(17, 24, 39, 255 if strong else 150), width)
#        ink.setCosmetic(True)
#        if dashed:
#            ink.setStyle(Qt.DashLine)
#        p.setPen(ink)
#        p.drawRect(r)
#
#    def _paint_hover_ring(self, p: QPainter, r: QRectF) -> None:
#        pen = QPen(QColor(255, 255, 255, 210), 1.4)
#        pen.setCosmetic(True)
#        p.setPen(pen)
#        p.setBrush(Qt.NoBrush)
#        p.drawRect(r.adjusted(-3, -3, 3, 3))
#
#    def _paint_outlier(self, p: QPainter, r: QRectF) -> None:
#        pen = QPen(QColor(theme.WARNING), 2.0)
#        pen.setCosmetic(True)
#        p.setPen(pen)
#        p.setBrush(Qt.NoBrush)
#        p.drawRect(r.adjusted(-1, -1, 1, 1))
#        self._paint_badge(p, r, "!", QColor(theme.WARNING), corner="tr")
#
#    def _paint_colorbar(self, p: QPainter, frame: Optional[QRectF] = None) -> None:
#        if not self._heat_legend or not self._heat:
#            return
#        vmin, vmax, label = self._heat_legend
#        frame = frame if frame is not None else QRectF(self.rect())
#        x, y, w, h = frame.left() + 14, frame.bottom() - 42, 150, 12
#        grad = QLinearGradient(float(x), 0.0, float(x + w), 0.0)
#        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
#            grad.setColorAt(t, QColor(heat_color(t)))
#        p.setPen(Qt.NoPen)
#        p.setBrush(grad)
#        p.drawRoundedRect(QRectF(x, y, w, h), 3, 3)
#        p.setPen(QPen(QColor(255, 255, 255, 120), 1))
#        p.setBrush(Qt.NoBrush)
#        p.drawRoundedRect(QRectF(x, y, w, h), 3, 3)
#        p.setPen(QColor("#FFFFFF"))
#        p.setFont(theme.mono_font(8, weight=700))
#        p.drawText(int(x), int(y - 4), label)
#        p.setFont(theme.mono_font(8))
#        p.drawText(QRectF(x, y + h + 1, w, 12), Qt.AlignLeft, f"{vmin:.3g}")
#        p.drawText(QRectF(x, y + h + 1, w, 12), Qt.AlignRight, f"{vmax:.3g}")
#
#    def _paint_selection_ring(self, p: QPainter, r: QRectF) -> None:
#        pen = QPen(QColor("#FFFFFF"), 1.6)
#        pen.setCosmetic(True)
#        pen.setStyle(Qt.DashLine)
#        p.setPen(pen)
#        p.setBrush(Qt.NoBrush)
#        p.drawRect(r.adjusted(-2, -2, 2, 2))
#
#    def _paint_badge(self, p: QPainter, r: QRectF, text: str,
#                     color: QColor, corner: str = "tl") -> None:
#        p.setFont(theme.mono_font(8, weight=700))
#        fm = p.fontMetrics()
#        bw = fm.horizontalAdvance(text) + 8
#        bh = fm.height() + 2
#        by = r.top() - bh if r.top() - bh >= 0 else r.top()
#        bx = r.left() if corner == "tl" else r.right() - bw
#        bg = QRectF(bx, by, bw, bh)
#        p.setPen(Qt.NoPen)
#        p.setBrush(QColor(color))
#        p.drawRoundedRect(bg, 3, 3)
#        p.setPen(QColor("#FFFFFF"))
#        p.drawText(bg, Qt.AlignCenter, text)
#
#    def _paint_value(self, p: QPainter, r: QRectF, text: str,
#                     hovered: bool = False) -> None:
#        """The metric, centred on the ROI — but only where it fits.
#
#        Zoomed out, a label is wider than its box: printed anyway they collide
#        with each other and bury the boxes they belong to. A label that does
#        not fit is dropped and comes back on zoom; the ROI under the cursor
#        keeps its label whatever the zoom, floated above the box, so a value
#        is always one hover away.
#        """
#        p.setFont(theme.mono_font(9, weight=700))
#        fm = p.fontMetrics()
#        # the *text* has to fit the box; its pill may overhang a little, which
#        # keeps a 4-digit label from vanishing on a box a 3-digit one fits
#        bg = label_rect(r, float(fm.horizontalAdvance(text)), float(fm.height()),
#                        hovered)
#        if bg is None:
#            return
#        pill = bg.adjusted(-3, 0, 3, 0)
#        p.setPen(Qt.NoPen)
#        p.setBrush(QColor(17, 24, 39, 200))
#        p.drawRoundedRect(pill, 3, 3)
#        p.setPen(QColor("#FFFFFF"))
#        p.drawText(pill, Qt.AlignCenter, text)
#
#    def _paint_handles(self, p: QPainter, rect: QRectF, color: QColor) -> None:
#        p.setPen(QPen(QColor("#FFFFFF"), 1.4))
#        p.setBrush(QColor(17, 24, 39))          # neutral, like the outline
#        for c in self._handle_centers(rect):
#            p.drawRect(QRectF(c.x() - _HANDLE / 2, c.y() - _HANDLE / 2,
#                              _HANDLE, _HANDLE))
#
#    def _paint_rubberband(self, p: QPainter) -> None:
#        if self._draw_rect is None:
#            return
#        rn = self._draw_rect.normalized()
#        tl = self._to_widget(rn.left(), rn.top())
#        self._stroke_neutral(p, QRectF(tl.x(), tl.y(), rn.width() * self._scale,
#                                       rn.height() * self._scale),
#                             2.0, dashed=True)
#
#    def _paint_marquee(self, p: QPainter) -> None:
#        if self._marquee is None:
#            return
#        rn = self._marquee.normalized()
#        tl = self._to_widget(rn.left(), rn.top())
#        rect = QRectF(tl.x(), tl.y(), rn.width() * self._scale,
#                      rn.height() * self._scale)
#        fill = QColor(theme.INFO)
#        fill.setAlpha(28)
#        pen = QPen(QColor(theme.INFO), 1.5)
#        pen.setCosmetic(True)
#        pen.setStyle(Qt.DashLine)
#        p.setPen(pen)
#        p.setBrush(fill)
#        p.drawRect(rect)
#
#    def _grid_rects(self) -> List[Rect]:
#        if self._grid_tl is None:
#            return []
#        br = self._grid_br if self._grid_stage >= 2 else self._cursor_img
#        return grid_between((self._grid_tl.x(), self._grid_tl.y()),
#                            (br.x(), br.y()), self._grid_rows, self._grid_cols,
#                            self._roi_w, self._roi_h)
#
#    def _paint_grid_preview(self, p: QPainter) -> None:
#        if not self._grid_mode or self._grid_stage == 0:
#            return
#        rects = self._grid_rects()
#        if not rects:
#            return
#        prev = QColor(255, 255, 255, 60)
#        for rect in rects:
#            r = self._rect_to_widget(rect)
#            p.setPen(Qt.NoPen)
#            p.setBrush(prev)
#            p.drawRect(r)
#            self._stroke_neutral(p, r, 1.4, dashed=True, strong=False)
#        # emphasise the two corner anchors
#        apen = QPen(QColor(theme.INFO), 2.2)
#        apen.setCosmetic(True)
#        p.setPen(apen)
#        p.setBrush(Qt.NoBrush)
#        for rect in (rects[0], rects[-1]):
#            p.drawRect(self._rect_to_widget(rect))
#
#    def _paint_hud(self, p: QPainter) -> None:
#        if self._grid_mode:
#            if self._grid_stage == 0:
#                msg = "▦ GRID — click the top-left corner"
#            elif self._grid_stage == 1:
#                msg = "▦ GRID — click the bottom-right corner"
#            else:
#                msg = (f"▦ GRID {self._grid_rows}×{self._grid_cols} — "
#                       "Enter / Add grid to place · Esc to cancel")
#            self._banner(p, msg, QColor(theme.INFO))
#            return
#        if not self._rois:
#            name = next((g.name for g in self._groups
#                         if g.gid == self._active_gid), None)
#            if name:
#                self._banner(p, f"Click on the image to add an ROI to “{name}”"
#                             " (or drag to size it)", QColor(theme.AMBER))
#
#    def _banner(self, p: QPainter, text: str, accent: QColor) -> None:
#        p.setFont(theme.display_font(10, weight=700))
#        fm = p.fontMetrics()
#        w = fm.horizontalAdvance(text) + 24
#        h = fm.height() + 10
#        x = (self.width() - w) / 2
#        p.setPen(QPen(accent, 1.5))
#        p.setBrush(QColor(17, 24, 39, 210))
#        p.drawRoundedRect(QRectF(x, 12, w, h), 8, 8)
#        p.setPen(QColor("#FFFFFF"))
#        p.drawText(QRectF(x, 12, w, h), Qt.AlignCenter, text)
#
#    # ------------------------------------------------------------------ #
#    # hit testing
#    # ------------------------------------------------------------------ #
#    @staticmethod
#    def _handle_centers(rect: QRectF) -> List[QPointF]:
#        return [QPointF(rect.left(), rect.top()),
#                QPointF(rect.right(), rect.top()),
#                QPointF(rect.right(), rect.bottom()),
#                QPointF(rect.left(), rect.bottom())]
#
#    def _active_roi(self) -> Optional[ROI]:
#        for r in self._rois:
#            if r.rid == self._active_rid:
#                return r
#        return None
#
#    def _handle_at(self, pos: QPointF) -> Optional[int]:
#        roi = self._active_roi()
#        if roi is None:
#            return None
#        rect = self._rect_to_widget(roi.rect)
#        for i, c in enumerate(self._handle_centers(rect)):
#            if abs(pos.x() - c.x()) <= _HANDLE and abs(pos.y() - c.y()) <= _HANDLE:
#                return i
#        return None
#
#    def _roi_body_at(self, pos: QPointF) -> Optional[int]:
#        ordered = sorted(self._rois, key=lambda r: (r.rid != self._active_rid,
#                                                    r.gid != self._active_gid))
#        for r in ordered:
#            if self._rect_to_widget(r.rect).contains(pos):
#                return r.rid
#        return None
#
#    def _marquee_hits(self) -> List[int]:
#        """rids of active-group ROIs intersecting the marquee rectangle."""
#        if self._marquee is None:
#            return []
#        sel = self._marquee.normalized()
#        hits = []
#        for r in self._rois:
#            if r.gid != self._active_gid:
#                continue
#            x, y, w, h = r.rect
#            if sel.intersects(QRectF(x, y, w, h)):
#                hits.append(r.rid)
#        return hits
#
#    # ------------------------------------------------------------------ #
#    # mouse / key / wheel
#    # ------------------------------------------------------------------ #
#    def mousePressEvent(self, e: QMouseEvent) -> None:
#        pos = QPointF(e.position())
#        if e.button() in (Qt.MiddleButton, Qt.RightButton):
#            self._interact = "pan"
#            self._drag_start = pos
#            self._pan_at_press = QPointF(self._offset)
#            self.setCursor(Qt.ClosedHandCursor)
#            return
#        if e.button() != Qt.LeftButton or self._image is None:
#            return
#        if self._grid_mode:
#            ip = self._to_image(pos)
#            if self._grid_stage == 0:
#                self._grid_tl = ip
#                self._grid_stage = 1
#            elif self._grid_stage == 1:
#                self._grid_br = ip
#                self._grid_stage = 2
#                self.grid_ready.emit(True)
#            else:
#                self.commit_grid()
#            self.update()
#            return
#        if e.modifiers() & Qt.ShiftModifier:
#            # Shift+drag → marquee select ROIs of the active group
#            ip = self._to_image(pos)
#            self._interact = "marquee"
#            self._drag_start = pos
#            self._marquee = QRectF(ip, ip)
#            self.update()
#            return
#        if self._selection:                       # a plain click clears a marquee
#            self._selection = set()
#            self.rois_selected.emit([])
#        handle = self._handle_at(pos)
#        if handle is not None:
#            self._interact = "resize"
#            self._resize_handle = handle
#            self._roi_at_press = self._active_roi().rect
#            self._drag_start = pos
#            return
#        body = self._roi_body_at(pos)
#        if body is not None:
#            if body != self._active_rid:
#                self._active_rid = body
#                self.roi_selected.emit(body)
#                self.update()
#                return
#            self._interact = "move"
#            self._roi_at_press = self._active_roi().rect
#            self._drag_start = pos
#            return
#        ip = self._to_image(pos)
#        self._interact = "draw"
#        self._drag_start = pos
#        self._draw_rect = QRectF(ip, ip)
#
#    def mouseMoveEvent(self, e: QMouseEvent) -> None:
#        pos = QPointF(e.position())
#        self._cursor_img = self._to_image(pos)
#        self._emit_cursor(pos)
#        # Panning outranks the mode: the right button drags the picture around
#        # whether or not a grid is being placed, and grid placement is exactly
#        # when you need to reach the far corner.
#        if self._interact == "pan":
#            self._offset = self._pan_at_press + (pos - self._drag_start)
#            self._fitted = False        # panned away from the fit
#            self.update()
#            return
#        if self._grid_mode:
#            if self._grid_stage == 1:
#                self.update()
#            return
#        if self._interact == "marquee" and self._marquee is not None:
#            self._marquee.setBottomRight(self._to_image(pos))
#            self.update()
#            return
#        if self._interact == "draw" and self._draw_rect is not None:
#            self._draw_rect.setBottomRight(self._to_image(pos))
#            self.update()
#            return
#        if self._interact == "move":
#            self._do_move(pos)
#            return
#        if self._interact == "resize":
#            self._do_resize(pos)
#            return
#        self._update_hover(pos)
#        self._update_cursor(pos)
#
#    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
#        if self._interact == "pan":
#            self._interact = None
#            self.unsetCursor()
#            return
#        if self._interact == "marquee":
#            self._interact = None
#            rids = self._marquee_hits()
#            self._marquee = None
#            self._selection = set(rids)
#            self.rois_selected.emit(list(rids))
#            self.update()
#            return
#        if self._grid_mode:
#            self._interact = None
#            return
#        if self._interact == "draw" and self._draw_rect is not None:
#            rect = self._finalize_draw()
#            self._draw_rect = None
#            self._interact = None
#            if rect is not None:
#                self.roi_created.emit(rect)
#            self.update()
#            return
#        if self._interact in ("move", "resize"):
#            roi = self._active_roi()
#            self._interact = None
#            self._resize_handle = None
#            if roi is not None:
#                self.roi_modified.emit(roi.rid, roi.rect)
#        self._interact = None
#
#    _ARROWS = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0),
#               Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
#
#    def keyPressEvent(self, e: QKeyEvent) -> None:
#        key, mods = e.key(), e.modifiers()
#        is_del = key in (Qt.Key_Delete, Qt.Key_Backspace)
#        ctrl = bool(mods & Qt.ControlModifier)
#        if self._grid_mode and key in (Qt.Key_Return, Qt.Key_Enter):
#            self.commit_grid()
#        elif self._grid_mode and key == Qt.Key_Escape:
#            self.cancel_grid()
#        elif self._grid_mode:
#            super().keyPressEvent(e)
#        elif self._selection and is_del:
#            self.rois_delete_requested.emit(list(self._selection))
#        elif self._active_rid is not None and is_del:
#            self.roi_delete_requested.emit(self._active_rid)
#        elif self._selection and key == Qt.Key_Escape:
#            self._selection = set()
#            self.rois_selected.emit([])
#            self.update()
#        elif key in self._ARROWS and self._active_rid is not None:
#            dx, dy = self._ARROWS[key]
#            step = 10 if (mods & Qt.ShiftModifier) else 1
#            self._nudge_active(dx * step, dy * step)
#        elif ctrl and key == Qt.Key_D and self._active_rid is not None:
#            self.roi_duplicate_requested.emit(self._active_rid)
#        elif ctrl and key == Qt.Key_A:
#            rids = [r.rid for r in self._rois if r.gid == self._active_gid]
#            self._selection = set(rids)
#            self.rois_selected.emit(rids)
#            self.update()
#        elif Qt.Key_1 <= key <= Qt.Key_9 and not ctrl:
#            self.group_index_requested.emit(key - Qt.Key_1)
#        else:
#            super().keyPressEvent(e)
#
#    def _nudge_active(self, dx: int, dy: int) -> None:
#        roi = self._active_roi()
#        if roi is None:
#            return
#        x, y, w, h = roi.rect
#        roi.rect = self._clamp((x + dx, y + dy, w, h))
#        self.roi_modified.emit(roi.rid, roi.rect)
#        self.update()
#
#    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
#        if self._image is None or e.button() != Qt.LeftButton or self._grid_mode:
#            return
#        rid = self._roi_body_at(QPointF(e.position()))
#        if rid is not None:
#            if rid != self._active_rid:
#                self._active_rid = rid
#                self.roi_selected.emit(rid)
#            self.roi_inspect_requested.emit(rid)
#
#    def wheelEvent(self, e: QWheelEvent) -> None:
#        if self._image is None:
#            return
#        factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
#        self.zoom_by(factor, QPointF(e.position()))
#
#    def leaveEvent(self, _e) -> None:
#        self.cursor_info.emit("")
#        if self._hover_rid != -1:
#            self._hover_rid = -1
#            self.roi_hovered.emit(-1)
#            self.update()
#
#    def _update_hover(self, pos: QPointF) -> None:
#        rid = self._roi_body_at(pos)
#        rid = rid if rid is not None else -1
#        if rid != self._hover_rid:
#            self._hover_rid = rid
#            self.roi_hovered.emit(rid)
#            self.update()
#
#    # ------------------------------------------------------------------ #
#    # helpers
#    # ------------------------------------------------------------------ #
#    def _reset_grid(self) -> None:
#        self._grid_stage = 0
#        self._grid_tl = None
#        self._grid_br = None
#        self.grid_ready.emit(False)
#
#    def _emit_cursor(self, pos: QPointF) -> None:
#        if self._image is None:
#            self.cursor_info.emit("")
#            return
#        ip = self._to_image(pos)
#        x, y = int(np.floor(ip.x())), int(np.floor(ip.y()))
#        h, w = self._image.shape[:2]
#        if 0 <= x < w and 0 <= y < h:
#            self.cursor_info.emit(f"x {x}  y {y}  ·  gray {int(self._image[y, x])}")
#        else:
#            self.cursor_info.emit("")
#
#    def _do_move(self, pos: QPointF) -> None:
#        roi = self._active_roi()
#        if roi is None or self._roi_at_press is None:
#            return
#        delta = self._to_image(pos) - self._to_image(self._drag_start)
#        x0, y0, w, h = self._roi_at_press
#        roi.rect = self._clamp((int(round(x0 + delta.x())),
#                                int(round(y0 + delta.y())), w, h))
#        self.update()
#
#    def _do_resize(self, pos: QPointF) -> None:
#        roi = self._active_roi()
#        if roi is None or self._roi_at_press is None:
#            return
#        x, y, w, h = self._roi_at_press
#        ip = self._to_image(pos)
#        left, top, right, bottom = x, y, x + w, y + h
#        if self._resize_handle in (0, 3):
#            left = ip.x()
#        if self._resize_handle in (1, 2):
#            right = ip.x()
#        if self._resize_handle in (0, 1):
#            top = ip.y()
#        if self._resize_handle in (2, 3):
#            bottom = ip.y()
#        nx, ny = int(round(min(left, right))), int(round(min(top, bottom)))
#        nw = max(_MIN_ROI, int(round(abs(right - left))))
#        nh = max(_MIN_ROI, int(round(abs(bottom - top))))
#        roi.rect = self._clamp((nx, ny, nw, nh))
#        self.update()
#
#    def _finalize_draw(self) -> Optional[Rect]:
#        r = self._draw_rect.normalized()
#        w, h = int(round(r.width())), int(round(r.height()))
#        if w < _MIN_ROI or h < _MIN_ROI:
#            # plain click -> place a box of the configured W×H centred on it
#            c = self._to_image(self._drag_start)
#            return self._clamp((int(round(c.x() - self._roi_w / 2)),
#                                int(round(c.y() - self._roi_h / 2)),
#                                self._roi_w, self._roi_h))
#        return self._clamp((int(round(r.x())), int(round(r.y())), w, h))
#
#    def _clamp(self, roi: Rect) -> Rect:
#        x, y, w, h = roi
#        if self._image is None:
#            return roi
#        ih, iw = self._image.shape[:2]
#        w = max(_MIN_ROI, min(w, iw))
#        h = max(_MIN_ROI, min(h, ih))
#        x = max(0, min(x, iw - w))
#        y = max(0, min(y, ih - h))
#        return (x, y, w, h)
#
#    def _update_cursor(self, pos: QPointF) -> None:
#        if self._image is None:
#            self.unsetCursor()
#            return
#        if self._handle_at(pos) is not None:
#            self.setCursor(Qt.SizeFDiagCursor)
#        elif self._roi_body_at(pos) is not None:
#            self.setCursor(Qt.SizeAllCursor)
#        else:
#            self.setCursor(Qt.CrossCursor)
#
#    def resizeEvent(self, _e) -> None:
#        if self._pixmap is None or self._interact is not None:
#            return
#        # set_image() fits against whatever size the widget has at load time,
#        # which is the layout's first guess, not the final one — without this
#        # the image stays pinned wherever that guess put it
#        if self._fitted:
#            self.fit()
#        else:
#            self.update()
#
#F 91065733d2396b64551a76f1504a7acccdc43d9e 1078 pear/ui/main_window.py
#"""Main window: image stage + control rail. Analysis lives in its own window.
#
#Model: a Group is a category; ROIs belong to a group. Add ROIs on the image
#(click to drop, drag to size, or Grid via two corner clicks), then compare
#metric distributions between or within groups in the Analysis window.
#"""
#
#from __future__ import annotations
#
#import csv
#import json
#import os
#from typing import List, Optional
#
#import numpy as np
#from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
#from PySide6.QtWidgets import (QDialog, QDockWidget, QFileDialog, QHBoxLayout,
#                               QLabel, QMainWindow, QMenu, QMessageBox,
#                               QPushButton, QScrollArea, QSizePolicy,
#                               QToolButton, QVBoxLayout, QWidget)
#
#from pear.core.analysis import (GROUP_PALETTE, ROI, Group, align_rects,
#                                compute_analysis, distribute_rects,
#                                group_outliers, group_rois,
#                                groups_from_json, groups_to_json, heat_cells,
#                                rois_from_points, rois_to_points,
#                                heat_color, load_image, roi_center, roi_metric,
#                                roi_patch, rois_from_json, rois_to_json,
#                                snapshot, summarize, uniformity)
#from pear.core.attributes import metric_label
#from pear.ui import theme
#from pear.ui.image_view import ImageView
#from pear.ui.widgets import (AnalysisPanel, RailPanel, RoiInspector,
#                             RoiSizeDialog, StageBar, save_widget_image)
#
#_FILTER = "Images (*.png *.tif *.tiff *.jpg *.jpeg *.bmp)"
#
#
#class _AnalysisSignals(QObject):
#    done = Signal(int, object)
#
#
#class _AnalysisJob(QRunnable):
#    def __init__(self, token, args, signals):
#        super().__init__()
#        self._token = token
#        self._args = args
#        self._signals = signals
#
#    def run(self):
#        try:
#            result = compute_analysis(*self._args)
#        except Exception:  # noqa: BLE001
#            result = None
#        self._signals.done.emit(self._token, result)
#
#
#class MainWindow(QMainWindow):
#    def __init__(self):
#        super().__init__()
#        self.setWindowTitle("PEAR — group & ROI analysis")
#        self.resize(1320, 860)
#
#        self._image: Optional[np.ndarray] = None
#        self._groups: List[Group] = []
#        self._rois: List[ROI] = []
#        self._active_gid: Optional[str] = None
#        self._active_rid: Optional[int] = None
#        self._selected_rids: set = set()   # rids marquee-selected on the canvas
#        self._next_rid = 1
#        self._metrics: List[str] = ["glv_mean", "glv_median"]
#        self._show_metric = ""            # single metric drawn live on ROIs
#        self._show_values = True          # print the shown metric on each ROI
#        self._heatmap = False             # colour ROIs by the shown metric
#        self._heat_field = False          # spread the heat over each ROI's cell
#        self._flag_outliers = False       # flag Tukey outliers of the shown metric
#        self._heat_alpha = 70             # heat fill opacity, percent
#        self._heat_range = None           # locked heat colours, or None = auto
#        self._roi_order = "placed"        # ROI list order: placed | asc | desc
#        self._values: dict = {}           # rid -> shown metric, one pass per refresh
#        self._value_cache: dict = {}      # (rid, rect, metric) -> value
#        self._outlier_rids: set = set()
#        self._image_path: Optional[str] = None
#        self._cmp_mode = "between"
#        self._within_gid: Optional[str] = None
#
#        self._pool = QThreadPool.globalInstance()
#        self._sig = _AnalysisSignals()
#        self._sig.done.connect(self._on_analysis_done)
#        self._analysis_token = 0
#        self._analysis_timer = QTimer(self)
#        self._analysis_timer.setSingleShot(True)
#        self._analysis_timer.setInterval(90)
#        self._analysis_timer.timeout.connect(self._run_analysis)
#
#        self._build_topbar()
#        self._build_docks()
#        self._build_status()
#        self._build_analysis_window()
#        self._build_inspector_window()
#        self._wire()
#        self.rail.set_ready(False)
#        self.stage_bar.setEnabled(False)
#
#    # ------------------------------------------------------------------ #
#    def _build_topbar(self) -> None:
#        bar = QWidget()
#        bar.setObjectName("TopBar")
#        lay = QHBoxLayout(bar)
#        lay.setContentsMargins(18, 10, 18, 10)
#        lay.setSpacing(8)
#        brand = QLabel('PE<span style="color:%s">A</span>R' % theme.AMBER)
#        brand.setObjectName("BrandTitle")
#        brand.setTextFormat(Qt.RichText)
#        sub = QLabel("group & ROI analysis")
#        sub.setObjectName("BrandSub")
#        self.dataset_lbl = QLabel("no image")
#        self.dataset_lbl.setObjectName("DatasetTag")
#        self.project_btn = QToolButton()
#        self.project_btn.setText("Project ▾")
#        self.project_btn.setPopupMode(QToolButton.InstantPopup)
#        pmenu = QMenu(self.project_btn)
#        pmenu.addAction("Open project…", self.on_open_project)
#        self._save_action = pmenu.addAction("Save project…", self.on_save_project)
#        self.project_btn.setMenu(pmenu)
#        self.analysis_btn_top = QPushButton("Analysis ⤢")
#        self.analysis_btn_top.setToolTip("Open the analysis window.")
#        self.analysis_btn_top.setEnabled(False)
#        self.load_btn = QPushButton("Load…")
#        self.load_btn.setObjectName("Primary")
#        lay.addWidget(brand, 0, Qt.AlignVCenter)
#        lay.addSpacing(8)
#        lay.addWidget(sub)
#        lay.addStretch(1)
#        lay.addWidget(self.dataset_lbl)
#        lay.addWidget(self.project_btn)
#        lay.addWidget(self.analysis_btn_top)
#        lay.addWidget(self.load_btn)
#        self.setMenuWidget(bar)
#
#    def _build_docks(self) -> None:
#        self.image_view = ImageView()
#        # The overlay controls sit on the stage, not at the bottom of the rail:
#        # every one of them changes what the image looks like.
#        self.stage_bar = StageBar()
#        # In a narrow window the bar's controls would otherwise overlap each
#        # other; it scrolls sideways instead, and never grows the window.
#        bar_scroll = QScrollArea()
#        bar_scroll.setWidget(self.stage_bar)
#        bar_scroll.setWidgetResizable(True)
#        bar_scroll.setFrameShape(QScrollArea.NoFrame)
#        bar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
#        bar_scroll.setFixedHeight(self.stage_bar.sizeHint().height() + 2)
#        bar_scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
#        stage = QWidget()
#        slay = QVBoxLayout(stage)
#        slay.setContentsMargins(0, 0, 0, 0)
#        slay.setSpacing(0)
#        slay.addWidget(bar_scroll)
#        slay.addWidget(self.image_view, 1)
#        self.setCentralWidget(stage)
#        self.rail = RailPanel()
#        scroll = QScrollArea()
#        scroll.setWidgetResizable(True)
#        scroll.setFrameShape(QScrollArea.NoFrame)
#        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
#        scroll.setWidget(self.rail)
#        self.rail_dock = QDockWidget("Workspace", self)
#        self.rail_dock.setObjectName("dock_rail")
#        self.rail_dock.setWidget(scroll)
#        self.rail_dock.setFeatures(QDockWidget.DockWidgetMovable |
#                                   QDockWidget.DockWidgetFloatable)
#        # The stage will happily take the whole window and leave the rail too
#        # narrow to show its own labels. The rail's width is a floor; the image
#        # gets what is left.
#        self.rail_dock.setMinimumWidth(390)
#        self.addDockWidget(Qt.RightDockWidgetArea, self.rail_dock)
#        self.resizeDocks([self.rail_dock], [410], Qt.Horizontal)
#
#    def _build_status(self) -> None:
#        bar = self.statusBar()
#        # the headline numbers, so the one figure you keep glancing at does
#        # not need the Analysis window opened for it
#        self.summary_lbl = QLabel("")
#        self.summary_lbl.setObjectName("Mono")
#        self.summary_lbl.setFont(theme.mono_font(9))
#        bar.addPermanentWidget(self.summary_lbl)
#        self.cursor_lbl = QLabel("")
#        self.cursor_lbl.setObjectName("Mono")
#        self.cursor_lbl.setFont(theme.mono_font(9))
#        bar.addPermanentWidget(self.cursor_lbl)
#        zoom = QWidget()
#        zl = QHBoxLayout(zoom)
#        zl.setContentsMargins(0, 0, 0, 0)
#        zl.setSpacing(4)
#        fit = QPushButton("Fit")
#        minus = QPushButton("−")
#        plus = QPushButton("+")
#        for b in (fit, minus, plus):
#            b.setFixedHeight(22)
#        minus.setFixedWidth(26)
#        plus.setFixedWidth(26)
#        self.zoom_lbl = QLabel("100%")
#        self.zoom_lbl.setObjectName("Mono")
#        self.zoom_lbl.setFont(theme.mono_font(9))
#        fit.clicked.connect(self.image_view.fit)
#        minus.clicked.connect(self.image_view.zoom_out)
#        plus.clicked.connect(self.image_view.zoom_in)
#        for w in (fit, minus, self.zoom_lbl, plus):
#            zl.addWidget(w)
#        bar.addPermanentWidget(zoom)
#
#    def _build_analysis_window(self) -> None:
#        self.analysis = AnalysisPanel()
#        self.analysis_window = QWidget()
#        self.analysis_window.setWindowTitle("PEAR — Analysis")
#        self.analysis_window.resize(920, 580)
#        lay = QVBoxLayout(self.analysis_window)
#        lay.setContentsMargins(0, 0, 0, 0)
#        lay.addWidget(self.analysis)
#
#    def _build_inspector_window(self) -> None:
#        self.inspector = RoiInspector()
#        self.inspector_window = QWidget()
#        self.inspector_window.setWindowTitle("PEAR — ROI inspector")
#        self.inspector_window.resize(600, 470)
#        lay = QVBoxLayout(self.inspector_window)
#        lay.setContentsMargins(0, 0, 0, 0)
#        lay.setSpacing(0)
#        bar = QWidget()
#        bar.setObjectName("StageBar")
#        blay = QHBoxLayout(bar)
#        blay.setContentsMargins(12, 6, 12, 6)
#        blay.addStretch(1)
#        self.inspector_image_btn = QPushButton("Export image")
#        self.inspector_image_btn.setFixedHeight(26)
#        self.inspector_image_btn.setToolTip(
#            "Save this ROI's pixel view as a picture.")
#        self.inspector_image_btn.clicked.connect(self.export_inspector_image)
#        blay.addWidget(self.inspector_image_btn)
#        lay.addWidget(bar)
#        lay.addWidget(self.inspector, 1)
#
#    def _wire(self) -> None:
#        self.load_btn.clicked.connect(self.on_load)
#        self.analysis_btn_top.clicked.connect(self.open_analysis)
#        self.rail.group_add.connect(self.add_group)
#        self.rail.group_pick.connect(self.select_group)
#        self.rail.group_del.connect(self.delete_group)
#        self.rail.group_color.connect(self.set_group_color)
#        self.rail.group_rename.connect(self.rename_group)
#        self.rail.group_clear.connect(self.clear_group)
#        self.rail.grid_mode_toggled.connect(self.set_grid_mode)
#        self.rail.grid_commit.connect(self.image_view.commit_grid)
#        self.rail.grid_shape_changed.connect(self.image_view.set_grid_shape)
#        self.rail.roi_size_changed.connect(self.image_view.set_roi_size)
#        self.rail.roi_pick.connect(self.select_roi)
#        self.rail.roi_del.connect(self.delete_roi)
#        self.rail.roi_hovered.connect(self.image_view.set_hover)
#        self.rail.metrics_changed.connect(self.set_metrics)
#        self.rail.metric_ids_changed.connect(self.stage_bar.set_metrics)
#        self.rail.roi_order_changed.connect(self.on_roi_order)
#        self.rail.roi_align.connect(self.align_rois)
#        self.rail.roi_import.connect(self.import_rois)
#        self.rail.roi_export.connect(self.export_rois)
#        self.stage_bar.show_changed.connect(self.on_show_metric)
#        self.stage_bar.values_changed.connect(self.on_show_values)
#        self.stage_bar.heatmap_changed.connect(self.on_heatmap)
#        self.stage_bar.cells_changed.connect(self.on_heat_field)
#        self.stage_bar.outliers_changed.connect(self.on_flag_outliers)
#        self.stage_bar.heat_alpha_changed.connect(self.on_heat_alpha)
#        self.stage_bar.heat_range_changed.connect(self.on_heat_range)
#        self.rail.open_analysis.connect(self.open_analysis)
#
#        self.image_view.roi_created.connect(self.on_roi_created)
#        self.image_view.grid_committed.connect(self.on_grid_committed)
#        self.image_view.grid_ready.connect(self.rail.set_grid_ready)
#        self.image_view.roi_modified.connect(self.on_roi_modified)
#        self.image_view.roi_selected.connect(self.select_roi)
#        self.image_view.roi_delete_requested.connect(self.delete_roi)
#        self.image_view.rois_selected.connect(self.on_marquee_selected)
#        self.image_view.rois_delete_requested.connect(self.delete_rois)
#        self.image_view.roi_hovered.connect(self.rail.set_hovered_roi)
#        self.image_view.roi_duplicate_requested.connect(self.duplicate_roi)
#        self.image_view.roi_inspect_requested.connect(self.open_inspector)
#        self.image_view.group_index_requested.connect(self.select_group_by_index)
#        self.image_view.cursor_info.connect(self.cursor_lbl.setText)
#        self.image_view.zoom_changed.connect(
#            lambda s: self.zoom_lbl.setText(f"{int(round(s * 100))}%"))
#
#        self.analysis.mode_changed.connect(self.on_cmp_mode)
#        self.analysis.within_group_changed.connect(self.on_within_group)
#        self.analysis.export_requested.connect(self.export_csv)
#        self.analysis.export_image_requested.connect(self.export_chart_image)
#        self.stage_bar.export_image_requested.connect(self.export_stage_image)
#
#    # ------------------------------------------------------------------ #
#    # image
#    # ------------------------------------------------------------------ #
#    def on_load(self) -> None:
#        path, _ = QFileDialog.getOpenFileName(self, "Load image", "", _FILTER)
#        if path:
#            self.load_path(path)
#
#    def load_path(self, path: str) -> None:
#        try:
#            img = load_image(path)
#        except Exception as exc:  # noqa: BLE001
#            QMessageBox.warning(self, "Load failed", str(exc))
#            return
#        self.set_image(img, os.path.basename(path))
#        self._image_path = path
#
#    def set_image(self, img: np.ndarray, name: str = "image") -> None:
#        self._image = img
#        self._image_path = None
#        self._groups = []
#        self._rois = []
#        self._active_gid = None
#        self._active_rid = None
#        self._selected_rids = set()
#        self._outlier_rids = set()
#        self._within_gid = None
#        self._value_cache = {}    # a new image invalidates every measurement
#        self.dataset_lbl.setText(f"{name} · {img.shape[1]}×{img.shape[0]}")
#        self.image_view.set_image(img)
#        self.add_group()          # start with one group so adding ROIs works
#        self._refresh()
#
#    # ------------------------------------------------------------------ #
#    # groups
#    # ------------------------------------------------------------------ #
#    def add_group(self) -> None:
#        if self._image is None:
#            return
#        used = {g.gid for g in self._groups}
#        letter = next((chr(ord("A") + i) for i in range(26)
#                       if chr(ord("A") + i) not in used), None)
#        if letter is None:
#            letter = f"G{len(self._groups)}"
#        ci = (ord(letter) - ord("A")) if len(letter) == 1 else len(self._groups)
#        self._groups.append(Group(gid=letter, name=f"Group {letter}",
#                                  color=GROUP_PALETTE[ci % len(GROUP_PALETTE)]))
#        self._active_gid = letter
#        self._refresh()
#
#    def select_group(self, gid: str) -> None:
#        self._active_gid = gid
#        self._refresh()
#
#    def delete_group(self, gid: str) -> None:
#        self._groups = [g for g in self._groups if g.gid != gid]
#        self._rois = [r for r in self._rois if r.gid != gid]
#        if self._active_gid == gid:
#            self._active_gid = self._groups[-1].gid if self._groups else None
#        if self._within_gid == gid:
#            self._within_gid = self._groups[0].gid if self._groups else None
#        self._refresh()
#
#    def set_group_color(self, gid: str, color: str) -> None:
#        g = self._group(gid)
#        if g is not None:
#            g.color = color
#            self._refresh()
#
#    def rename_group(self, gid: str, name: str) -> None:
#        g = self._group(gid)
#        if g is not None and name:
#            g.name = name
#            self._refresh()
#
#    def clear_group(self, gid: str) -> None:
#        self._rois = [r for r in self._rois if r.gid != gid]
#        self._refresh()
#
#    # ------------------------------------------------------------------ #
#    # rois
#    # ------------------------------------------------------------------ #
#    def set_grid_mode(self, on: bool) -> None:
#        self.image_view.set_grid_mode(on)
#        if on:
#            self.statusBar().showMessage(
#                "Grid: click the top-left, then the bottom-right corner.", 6000)
#
#    def _add_roi(self, rect, refresh=True) -> ROI:
#        gid = self._active_gid or (self._groups[0].gid if self._groups else "A")
#        roi = ROI(rid=self._next_rid, gid=gid, rect=tuple(rect),
#                  label=f"ROI {self._next_rid}")
#        self._next_rid += 1
#        self._rois.append(roi)
#        self._active_rid = roi.rid
#        if refresh:
#            self._refresh()
#        return roi
#
#    def on_roi_created(self, rect) -> None:
#        if not self._groups:
#            self.add_group()
#        self._add_roi(rect)
#
#    def on_grid_committed(self, rects) -> None:
#        if not self._groups:
#            self.add_group()
#        for rect in rects:
#            self._add_roi(rect, refresh=False)
#        self.rail.grid_btn.setChecked(False)     # exit grid mode
#        self.statusBar().showMessage(f"Added {len(rects)} ROIs.", 3000)
#        self._refresh()
#
#    def on_roi_modified(self, rid: int, rect) -> None:
#        roi = self._roi(rid)
#        if roi is not None:
#            roi.rect = tuple(rect)
#            self._refresh()
#
#    def select_roi(self, rid: int) -> None:
#        self._active_rid = rid
#        self._selected_rids = set()          # a single pick clears the marquee set
#        roi = self._roi(rid)
#        if roi is not None and roi.gid != self._active_gid:
#            self._active_gid = roi.gid
#        self._refresh()
#
#    def on_marquee_selected(self, rids) -> None:
#        self._selected_rids = set(rids or [])
#        self._refresh()
#        if self._selected_rids:
#            self.statusBar().showMessage(
#                f"{len(self._selected_rids)} ROIs selected · Delete to remove.",
#                4000)
#
#    def duplicate_roi(self, rid: int) -> None:
#        src = self._roi(rid)
#        if src is None:
#            return
#        x, y, w, h = src.rect
#        nx, ny = x + 8, y + 8
#        if self._image is not None:
#            ih, iw = self._image.shape[:2]
#            nx, ny = max(0, min(nx, iw - w)), max(0, min(ny, ih - h))
#        roi = ROI(rid=self._next_rid, gid=src.gid, rect=(nx, ny, w, h), label="")
#        self._next_rid += 1
#        self._rois.append(roi)
#        self._active_gid = src.gid
#        self._active_rid = roi.rid
#        self._selected_rids = set()
#        self._refresh()
#
#    def select_group_by_index(self, i: int) -> None:
#        if 0 <= i < len(self._groups):
#            self.select_group(self._groups[i].gid)
#
#    def delete_roi(self, rid: int) -> None:
#        self._rois = [r for r in self._rois if r.rid != rid]
#        if self._active_rid == rid:
#            self._active_rid = None
#        self._selected_rids.discard(rid)
#        self._refresh()
#
#    def delete_rois(self, rids) -> None:
#        rid_set = set(rids or [])
#        if not rid_set:
#            return
#        self._rois = [r for r in self._rois if r.rid not in rid_set]
#        if self._active_rid in rid_set:
#            self._active_rid = None
#        self._selected_rids -= rid_set
#        self.statusBar().showMessage(f"Deleted {len(rid_set)} ROIs.", 3000)
#        self._refresh()
#
#    def set_metrics(self, metrics: List[str]) -> None:
#        self._metrics = list(metrics)
#        self._render_analysis()
#
#    def on_show_metric(self, mid: str) -> None:
#        self._show_metric = mid or ""
#        self._refresh()
#
#    def on_show_values(self, on: bool) -> None:
#        self._show_values = bool(on)
#        self._refresh()
#
#    def on_heat_field(self, on: bool) -> None:
#        self._heat_field = bool(on)
#        if on and not self._is_glv_show():
#            self.statusBar().showMessage(
#                "Pick a GLV metric in “show on ROIs” to colour the field.", 4000)
#        self._update_heatmap()
#
#    def align_rois(self, mode: str) -> None:
#        """Tidy the marquee selection — or the whole active group if none.
#
#        Hand-placed ROIs are a few pixels off each other, which is invisible
#        until the field fill tiles them: cell edges fall midway between
#        centres, so a stray offset turns a clean grid into a staircase.
#        """
#        rois = [r for r in self._rois if r.rid in self._selected_rids]
#        scope = "selection"
#        if len(rois) < 2:
#            rois = group_rois(self._rois, self._active_gid)
#            scope = "group"
#        if len(rois) < 2:
#            self.statusBar().showMessage(
#                "Add at least two ROIs (Shift+drag selects them).", 4000)
#            return
#        rects = [r.rect for r in rois]
#        if mode in ("distx", "disty"):
#            out = distribute_rects(rects, "x" if mode == "distx" else "y")
#        else:
#            out = align_rects(rects, mode)
#        if out == rects:
#            return
#        for roi, rect in zip(rois, out):
#            roi.rect = tuple(rect)
#        self.statusBar().showMessage(
#            f"{mode} applied to {len(rois)} ROIs in the {scope}.", 3000)
#        self._refresh()
#
#    def on_roi_order(self, order: str) -> None:
#        self._roi_order = order if order in ("placed", "asc", "desc") else "placed"
#        self._refresh()
#
#    def on_heat_range(self, rng) -> None:
#        """Lock the heat colours to a fixed grey-level range (None = auto)."""
#        self._heat_range = tuple(rng) if rng else None
#        self._update_heatmap()
#
#    def on_heat_alpha(self, pct: int) -> None:
#        self._heat_alpha = int(max(0, min(100, int(pct))))
#        self._update_heatmap()
#
#    def on_heatmap(self, on: bool) -> None:
#        self._heatmap = bool(on)
#        if on and not self._is_glv_show():
#            self.statusBar().showMessage(
#                "Pick a GLV metric in “show on ROIs” to colour the heatmap.", 4000)
#        self._refresh()
#
#    def on_flag_outliers(self, on: bool) -> None:
#        self._flag_outliers = bool(on)
#        if on and not self._is_glv_show():
#            self.statusBar().showMessage(
#                "Pick a GLV metric in “show on ROIs” to flag outliers.", 4000)
#        self._refresh()
#
#    def _is_glv_show(self) -> bool:
#        return bool(self._show_metric)
#
#    def _update_heatmap(self) -> None:
#        # Boxes and field are two ways to paint the same values: either one on
#        # its own is a heat overlay.
#        if ((self._heatmap or self._heat_field) and self._image is not None
#                and self._is_glv_show()):
#            vals = self._values
#            finite = [v for v in vals.values() if np.isfinite(v)]
#            if finite:
#                vmin, vmax = min(finite), max(finite)
#                if self._heat_range:      # locked: the same colour every image
#                    vmin, vmax = self._heat_range
#                span = (vmax - vmin) or 1.0
#                colors = {rid: heat_color((v - vmin) / span)
#                          for rid, v in vals.items() if np.isfinite(v)}
#                self.image_view.set_heatmap(
#                    colors, (vmin, vmax, metric_label(self._show_metric)),
#                    round(self._heat_alpha * 2.55))
#                shape = self._image.shape[:2]
#                self.image_view.set_heat_cells(
#                    heat_cells(self._rois, (shape[1], shape[0]))
#                    if self._heat_field else {})
#                return
#        self.image_view.set_heatmap({}, None)
#        self.image_view.set_heat_cells({})
#
#    def _compute_values(self) -> None:
#        """``rid -> shown metric``, once per refresh.
#
#        The canvas labels, the heatmap, the ROI list and the status readout
#        all want the same numbers; computing them here keeps one pass over the
#        pixels instead of four.
#        """
#        vals: dict = {}
#        if self._image is not None and self._show_metric:
#            # Nudging one ROI used to re-measure every other one. The patch
#            # only changes when its rect does, so the answer is cached against
#            # it — this is most of the "sticky" feeling on a field with a few
#            # hundred boxes.
#            for r in self._rois:
#                key = (r.rid, tuple(r.rect), self._show_metric)
#                v = self._value_cache.get(key)
#                if v is None:
#                    v = roi_metric(self._image, r, self._show_metric)
#                    self._value_cache[key] = v
#                vals[r.rid] = v
#            if len(self._value_cache) > 20000:          # a session's worth
#                self._value_cache = dict(
#                    ((r.rid, tuple(r.rect), self._show_metric), vals[r.rid])
#                    for r in self._rois)
#        self._values = vals
#
#    def _update_roi_values(self) -> None:
#        if not self._show_values or not self._values:
#            self.image_view.set_roi_values({})
#            return
#        self.image_view.set_roi_values(
#            {rid: f"{v:.3g}" for rid, v in self._values.items()})
#
#    def _update_summary(self) -> None:
#        """Headline numbers in the status bar — counts, then the shown metric."""
#        if self._image is None:
#            self.summary_lbl.setText("")
#            return
#        parts = [f"{len(self._groups)} groups · {len(self._rois)} ROIs"]
#        vals = np.asarray([v for v in self._values.values() if np.isfinite(v)],
#                          dtype=np.float64)
#        if vals.size:
#            u = uniformity(vals)
#            parts.append(f"{metric_label(self._show_metric)}: "
#                         f"mean {u['mean']:.4g} · range {u['range']:.3g} "
#                         f"· CV {u['cv_pct']:.2f}%")
#        self.summary_lbl.setText("   ".join(parts))
#
#    def _ordered_rois(self, rois):
#        """The active group's ROIs in list order — as placed, or by value."""
#        if self._roi_order == "placed" or not self._values:
#            return rois
#        rev = self._roi_order == "desc"
#
#        def key(r):
#            v = self._values.get(r.rid)
#            if v is None or not np.isfinite(v):
#                return (1, 0.0)      # unmeasurable — keep it last
#            return (0, -v if rev else v)
#
#        return sorted(rois, key=key)
#
#    def on_cmp_mode(self, mode: str) -> None:
#        self._cmp_mode = mode
#        self._render_analysis()
#
#    def on_within_group(self, gid: str) -> None:
#        self._within_gid = gid
#        self._render_analysis()
#
#    def open_analysis(self) -> None:
#        self.analysis_window.show()
#        self.analysis_window.raise_()
#        self.analysis_window.activateWindow()
#        self._render_analysis()
#
#    def open_inspector(self, rid: int) -> None:
#        self.select_roi(rid)
#        self.inspector_window.show()
#        self.inspector_window.raise_()
#        self.inspector_window.activateWindow()
#        self._update_inspector()
#
#    def _update_inspector(self) -> None:
#        if not self.inspector_window.isVisible():
#            return
#        roi = self._roi(self._active_rid)
#        if roi is None or self._image is None:
#            self.inspector.set_roi(None, "")
#            return
#        g = self._group(roi.gid)
#        title = (f"{roi.label or ('ROI ' + str(roi.rid))} · "
#                 f"{roi.rect[2]}×{roi.rect[3]}"
#                 + (f" · {g.name}" if g is not None else ""))
#        self.inspector.set_roi(roi_patch(self._image, roi.rect), title)
#
#    # ------------------------------------------------------------------ #
#    # refresh
#    # ------------------------------------------------------------------ #
#    def _renumber(self) -> None:
#        """Re-index each group's ROI display labels 1..n (rids stay unique)."""
#        for g in self._groups:
#            for i, r in enumerate(group_rois(self._rois, g.gid), 1):
#                r.label = f"ROI {i}"
#
#    def _refresh(self) -> None:
#        self._renumber()
#        has_img = self._image is not None
#        self.rail.set_ready(has_img)
#        self.stage_bar.setEnabled(has_img)   # nothing to overlay without one
#        self.analysis_btn_top.setEnabled(has_img)
#        self._save_action.setEnabled(has_img)
#        self._outlier_rids = (
#            group_outliers(self._image, self._rois, self._show_metric)
#            if (self._flag_outliers and has_img and self._is_glv_show())
#            else set())
#        self._compute_values()
#        counts = {g.gid: len(group_rois(self._rois, g.gid)) for g in self._groups}
#        self.rail.set_groups(self._groups, self._active_gid, counts)
#        self.rail.set_rois(
#            self._ordered_rois(group_rois(self._rois, self._active_gid)),
#            self._active_rid, self._selected_rids, self._outlier_rids,
#            self._values)
#        self.image_view.set_groups(self._groups, self._active_gid)
#        self.image_view.set_rois(self._rois, self._active_rid)
#        self.image_view.set_selection(self._selected_rids)
#        self.image_view.set_outliers(self._outlier_rids)
#        self._update_roi_values()
#        self._update_heatmap()
#        self._update_summary()
#        self._update_inspector()
#        if self._within_gid is None and self._groups:
#            self._within_gid = self._groups[0].gid
#        self._render_analysis()
#
#    def _render_analysis(self) -> None:
#        enabled = (self._image is not None and bool(self._metrics)
#                   and any(group_rois(self._rois, g.gid) for g in self._groups))
#        self.analysis.set_controls(self._cmp_mode, self._groups,
#                                   self._within_gid, enabled)
#        self._analysis_timer.start()
#
#    def _run_analysis(self) -> None:
#        self._analysis_token += 1
#        token = self._analysis_token
#        gs, rs = snapshot(self._groups, self._rois)
#        args = (self._image, gs, rs, list(self._metrics), self._cmp_mode,
#                self._within_gid)
#        self.analysis.set_computing(True)
#        self._pool.start(_AnalysisJob(token, args, self._sig))
#
#    def _on_analysis_done(self, token: int, result) -> None:
#        if token != self._analysis_token or result is None:
#            return
#        self.analysis.set_computing(False)
#        self.analysis.show_result(result)
#
#    def render_analysis_sync(self) -> None:
#        self._analysis_timer.stop()
#        gs, rs = snapshot(self._groups, self._rois)
#        result = compute_analysis(self._image, gs, rs, list(self._metrics),
#                                  self._cmp_mode, self._within_gid)
#        enabled = result.empty is None
#        self.analysis.set_controls(self._cmp_mode, self._groups,
#                                   self._within_gid, enabled)
#        self.analysis.set_computing(False)
#        self.analysis.show_result(result)
#
#    # ------------------------------------------------------------------ #
#    def _group(self, gid) -> Optional[Group]:
#        for g in self._groups:
#            if g.gid == gid:
#                return g
#        return None
#
#    def _roi(self, rid) -> Optional[ROI]:
#        for r in self._rois:
#            if r.rid == rid:
#                return r
#        return None
#
#    # ------------------------------------------------------------------ #
#    # project save / open (JSON)
#    # ------------------------------------------------------------------ #
#    def on_open_project(self) -> None:
#        path, _ = QFileDialog.getOpenFileName(
#            self, "Open project", "", "PEAR project (*.pear.json *.json)")
#        if path:
#            self.open_project(path)
#
#    def on_save_project(self) -> None:
#        if self._image is None:
#            QMessageBox.information(self, "Save project", "Load an image first.")
#            return
#        path, _ = QFileDialog.getSaveFileName(
#            self, "Save project", "project.pear.json",
#            "PEAR project (*.pear.json *.json)")
#        if path:
#            self.save_project(path)
#            self.statusBar().showMessage(
#                f"Saved project → {os.path.basename(path)}", 3000)
#
#    def _project_dict(self) -> dict:
#        shape = list(self._image.shape[:2]) if self._image is not None else None
#        return {
#            "app": "PEAR", "version": 1,
#            "image_path": self._image_path,
#            "image_shape": shape,
#            "groups": groups_to_json(self._groups),
#            "rois": rois_to_json(self._rois),
#            "next_rid": self._next_rid,
#            "metrics": list(self._metrics),
#            "show_metric": self._show_metric,
#            "show_values": self._show_values,
#            "heatmap": self._heatmap,
#            "heat_field": self._heat_field,
#            "flag_outliers": self._flag_outliers,
#            "heat_alpha": self._heat_alpha,
#            "heat_range": list(self._heat_range) if self._heat_range else None,
#            "chart_style": self.analysis.chart_style(),
#            "roi_order": self._roi_order,
#            "cmp_mode": self._cmp_mode,
#            "within_gid": self._within_gid,
#            "active_gid": self._active_gid,
#            "chart_type": self.analysis.chart_state()[0],
#            "pos_axis": self.analysis.chart_state()[1],
#            "chart_opts": self.analysis.chart_options(),
#        }
#
#    def save_project(self, path: str) -> str:
#        with open(path, "w", encoding="utf-8") as fh:
#            json.dump(self._project_dict(), fh, indent=2, ensure_ascii=False)
#        return path
#
#    def open_project(self, path: str) -> Optional[str]:
#        with open(path, encoding="utf-8") as fh:
#            data = json.load(fh)
#        ipath = data.get("image_path")
#        if ipath and os.path.exists(ipath):
#            try:
#                self.set_image(load_image(ipath), os.path.basename(ipath))
#                self._image_path = ipath
#            except Exception:  # noqa: BLE001
#                pass
#        if self._image is None:
#            QMessageBox.warning(
#                self, "Open project",
#                "The project's image was not found. Load the image first, "
#                "then open the project again.")
#            return None
#        self._restore_project(data)
#        return path
#
#    def _restore_project(self, data: dict) -> None:
#        self._groups = groups_from_json(data.get("groups"))
#        self._rois = rois_from_json(data.get("rois"))
#        self._next_rid = int(data.get("next_rid")
#                             or (max((r.rid for r in self._rois), default=0) + 1))
#        self._metrics = list(data.get("metrics") or ["glv_mean", "glv_median"])
#        self._show_metric = data.get("show_metric") or ""
#        self._show_values = bool(data.get("show_values", True))
#        self._heatmap = bool(data.get("heatmap", False))
#        self._heat_field = bool(data.get("heat_field", False))
#        self._flag_outliers = bool(data.get("flag_outliers", False))
#        self._heat_alpha = int(data.get("heat_alpha", 70))
#        rng = data.get("heat_range")
#        self._heat_range = (tuple(rng) if rng and len(rng) == 2 else None)
#        order = data.get("roi_order", "placed")
#        self._roi_order = order if order in ("placed", "asc", "desc") else "placed"
#        self._cmp_mode = data.get("cmp_mode", "between")
#        self._within_gid = data.get("within_gid")
#        self._active_gid = (data.get("active_gid")
#                            or (self._groups[0].gid if self._groups else None))
#        self._active_rid = None
#        self._selected_rids = set()
#        self.rail.set_metric_state(self._metrics, [self._show_metric])
#        self.rail.set_roi_order(self._roi_order)
#        self.stage_bar.set_metrics(self.rail.metrics.ids())
#        self.stage_bar.set_state(self._show_metric, self._show_values,
#                                 self._heatmap, self._heat_field,
#                                 self._flag_outliers, self._heat_alpha)
#        self.analysis.set_chart_state(data.get("chart_type", "box"),
#                                      data.get("pos_axis", "x"))
#        self.analysis.set_chart_options(data.get("chart_opts") or {})
#        self.analysis.set_chart_style(data.get("chart_style") or {})
#        self.stage_bar.set_heat_range(self._heat_range)
#        self._refresh()
#
#    # ------------------------------------------------------------------ #
#    # export
#    # ------------------------------------------------------------------ #
#    # ------------------------------------------------------------------ #
#    # ROI interchange
#    # ------------------------------------------------------------------ #
#    _ROI_FILTER = "ROI list (*.json)"
#
#    def import_rois(self, path: Optional[str] = None, mode: str = "",
#                    size=None, ask_size: bool = True) -> Optional[int]:
#        """Read a flat ROI list. Returns how many ROIs landed, or None.
#
#        The file says where the boxes go and what colour they are; PEAR turns
#        each colour into a group. Sizes come from the file when it carries
#        them and from the size fields when it does not.
#        """
#        if self._image is None:
#            return None
#        if not path:
#            path, _ = QFileDialog.getOpenFileName(
#                self, "Import ROIs", "", self._ROI_FILTER)
#            if not path:
#                return None
#        try:
#            with open(path, encoding="utf-8-sig") as fh:
#                items = json.load(fh)
#            w, h = size or self.rail.roi_size()
#            if size is None and ask_size:
#                dlg = RoiSizeDialog(self, "import", w, h,
#                                    len(items) if isinstance(items, list) else 0)
#                if dlg.exec() != QDialog.Accepted:
#                    return None
#                size = dlg.options()["size"]
#                if size:
#                    w, h = size
#            shape = self._image.shape[:2]
#            groups, rois, clamped = rois_from_points(
#                items, w, h, bounds=(shape[1], shape[0]),
#                start_rid=self._next_rid, force_size=bool(size))
#        except (OSError, ValueError, json.JSONDecodeError) as exc:
#            QMessageBox.warning(self, "Import ROIs",
#                                f"Could not read that file:\n{exc}")
#            return None
#        if not rois:
#            QMessageBox.warning(self, "Import ROIs", "That file has no ROIs.")
#            return None
#        if not mode:
#            mode = "replace"
#            if self._rois:
#                box = QMessageBox(self)
#                box.setWindowTitle("Import ROIs")
#                box.setText(f"{len(rois)} ROIs in {os.path.basename(path)}.")
#                box.setInformativeText("Replace the ROIs already placed, or "
#                                       "add these to them?")
#                replace = box.addButton("Replace", QMessageBox.AcceptRole)
#                add = box.addButton("Add", QMessageBox.ActionRole)
#                box.addButton(QMessageBox.Cancel)
#                box.exec()
#                if box.clickedButton() is None or box.clickedButton() not in (
#                        replace, add):
#                    return None
#                mode = "replace" if box.clickedButton() is replace else "add"
#        if mode == "replace":
#            self._groups, self._rois = [], []
#            self._selected_rids = set()
#        # a colour already on the board keeps its group; the rest come in new
#        by_color = {g.color: g.gid for g in self._groups}
#        used = {g.gid for g in self._groups}
#        remap = {}
#        for g in groups:
#            gid = by_color.get(g.color)
#            if gid is None:
#                gid = next((c for c in (chr(ord("A") + i) for i in range(26))
#                            if c not in used), f"G{len(used)}")
#                used.add(gid)
#                by_color[g.color] = gid
#                self._groups.append(Group(gid=gid, name=f"Group {gid}",
#                                          color=g.color))
#            remap[g.gid] = gid
#        for r in rois:
#            r.gid = remap[r.gid]
#        self._rois.extend(rois)
#        self._next_rid = max((r.rid for r in self._rois), default=0) + 1
#        self._active_gid = self._groups[0].gid if self._groups else None
#        self._active_rid = None
#        note = f"Imported {len(rois)} ROIs from {os.path.basename(path)}"
#        if clamped:
#            note += f" · {clamped} moved to fit the image"
#        self.statusBar().showMessage(note, 5000)
#        self._refresh()
#        return len(rois)
#
#    def export_rois(self, path: Optional[str] = None, size=None,
#                    include_size: bool = True,
#                    ask_size: bool = True) -> Optional[str]:
#        """Write every ROI as that same flat list."""
#        if not self._rois:
#            return None
#        if ask_size and size is None:
#            w, h = self.rail.roi_size()
#            dlg = RoiSizeDialog(self, "export", w, h, len(self._rois))
#            if dlg.exec() != QDialog.Accepted:
#                return None
#            opts = dlg.options()
#            size, include_size = opts["size"], opts["include_size"]
#        if not path:
#            base = os.path.splitext(os.path.basename(self._image_path or
#                                                     "rois"))[0]
#            path, _ = QFileDialog.getSaveFileName(
#                self, "Export ROIs", f"{base}_rois.json", self._ROI_FILTER)
#            if not path:
#                return None
#        items = rois_to_points(self._groups, self._rois, size,
#                               include_size)
#        with open(path, "w", encoding="utf-8") as fh:
#            json.dump(items, fh, indent=2, ensure_ascii=False)
#        self.statusBar().showMessage(
#            f"{len(items)} ROIs written to {path}", 4000)
#        return path
#
#    _IMAGE_FILTER = "PNG image (*.png);;SVG vector (*.svg)"
#
#    def _ask_image_path(self, parent, title: str, default: str) -> Optional[str]:
#        path, _ = QFileDialog.getSaveFileName(parent, title, default,
#                                              self._IMAGE_FILTER)
#        return path or None
#
#    def _report_image(self, out, title: str) -> Optional[str]:
#        if out is None:
#            QMessageBox.warning(
#                self, title,
#                "Nothing to export — SVG also needs PySide6's QtSvg module.")
#            return None
#        self.statusBar().showMessage(f"Image written to {out}", 4000)
#        return out
#
#    def export_chart_image(self, scope: str = "charts",
#                           path: Optional[str] = None) -> Optional[str]:
#        """Save a section of the results for a report — PNG at 3×, or SVG."""
#        scope = scope or "charts"
#        if not path:
#            path = self._ask_image_path(self.analysis_window,
#                                        "Export results image",
#                                        f"pear_{scope}.png")
#            if not path:
#                return None
#        return self._report_image(self.analysis.save_image(path, scope),
#                                  "Export results image")
#
#    def export_stage_image(self, path: Optional[str] = None,
#                           scale: float = 2.0) -> Optional[str]:
#        """Save the annotated field — the image itself, overlays on top."""
#        if self._image is None:
#            return None
#        if not path:
#            base = os.path.splitext(os.path.basename(self._image_path or
#                                                     "field"))[0]
#            path = self._ask_image_path(self, "Export field image",
#                                        f"{base}_pear.png")
#            if not path:
#                return None
#        return self._report_image(self.image_view.export_image(path, scale),
#                                  "Export field image")
#
#    def export_inspector_image(self, path: Optional[str] = None) -> Optional[str]:
#        """Save the ROI pixel view."""
#        if not path:
#            path = self._ask_image_path(self.inspector_window,
#                                        "Export ROI image", "pear_roi.png")
#            if not path:
#                return None
#        return self._report_image(save_widget_image(self.inspector, path),
#                                  "Export ROI image")
#
#    def export_csv(self, path: Optional[str] = None) -> Optional[str]:
#        if self._image is None or not self._rois:
#            return None
#        if not path:
#            path, _ = QFileDialog.getSaveFileName(
#                self, "Export CSV", "group_analysis.csv", "CSV (*.csv)")
#            if not path:
#                return None
#        self._write_csv(path)
#        return path
#
#    def _write_csv(self, path: str) -> None:
#        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
#            w = csv.writer(fh)
#            w.writerow(["PEAR group & ROI analysis"])
#            w.writerow([])
#            header = ["group", "roi", "x", "y", "w", "h",
#                      "center_x", "center_y"] + \
#                     [metric_label(m) for m in self._metrics]
#            w.writerow(header)
#            for g in self._groups:
#                for roi in group_rois(self._rois, g.gid):
#                    x, y, wid, hei = roi.rect
#                    cx, cy = roi_center(roi.rect)
#                    row = [g.name, roi.label, x, y, wid, hei,
#                           f"{cx:g}", f"{cy:g}"]
#                    for mid in self._metrics:
#                        row.append(f"{roi_metric(self._image, roi, mid):.6g}")
#                    w.writerow(row)
#            w.writerow([])
#            w.writerow(["summary"])
#            w.writerow(["group", "ROIs"] + [metric_label(m) for m in self._metrics])
#            for g in self._groups:
#                grois = group_rois(self._rois, g.gid)
#                if not grois:
#                    continue
#                line = [g.name, len(grois)]
#                for mid in self._metrics:
#                    vals = np.array([roi_metric(self._image, r, mid)
#                                     for r in grois])
#                    line.append(f"{summarize(vals)['mean']:.6g}")
#                w.writerow(line)
#
#F 6e52a5cfab38e76b4717d58d36937a9e9afb09d5 238 pear/ui/theme.py
#"""Design tokens and global QSS — a single light instrument theme.
#
#Palette and type are adopted from the sibling project's design system
#(PixelOpt): a calm light ground with a single amber brand accent, black
#image stage, and system-safe fonts (no exotic webfont to miss on a fab PC).
#"""
#
#from __future__ import annotations
#
#from PySide6.QtGui import QColor, QFont, QFontDatabase
#
## --- palette -------------------------------------------------------------- #
#WINDOW = "#F5F6F8"      # app ground
#PANEL = "#FFFFFF"       # panels
#CARD = "#FBFCFE"        # cards / insets
#SUBTLE = "#F3F4F6"      # subtle fills, tracks
#
#INK = "#1F2937"         # primary text
#INK2 = "#4B5563"        # secondary text
#INK3 = "#9CA3AF"        # muted text
#
#LINE = "#E5E7EB"        # borders
#LINE2 = "#EEF1F4"       # hairlines
#
#AMBER = "#F59E0B"       # brand accent
#AMBER_HOVER = "#FBBF24"
#AMBER_PRESS = "#D97706"
#AMBER_SOFT = "#FEF3C7"
#ON_AMBER = "#3D2C05"    # ink on amber fills
#
#STAGE = "#000000"       # image stage
#
#SUCCESS = "#16A34A"
#WARNING = "#DC2626"
#INFO = "#2563EB"
#CYAN = "#0891B2"
#
## Target / reference accents (mirror the core defaults).
#TARGET = "#DC2626"
#REFERENCE = "#0891B2"
#
#GRID_RGBA = (150, 168, 178, 46)     # cell grid on the black stage
#
## --- fonts ---------------------------------------------------------------- #
#_SANS = "'Segoe UI', 'Liberation Sans', Arial, 'Helvetica Neue', sans-serif"
#_MONO = "'Liberation Mono', 'SFMono-Regular', Consolas, Menlo, monospace"
#
#
#def color(token: str) -> QColor:
#    return QColor(token)
#
#
#def _pick(families, default: str) -> str:
#    available = set(QFontDatabase.families())
#    return next((f for f in families if f in available), default)
#
#
#def _weight(value) -> QFont.Weight:
#    return value if isinstance(value, QFont.Weight) else QFont.Weight(int(value))
#
#
#def mono_font(size: int = 10, weight=QFont.Medium) -> QFont:
#    fam = _pick(["Liberation Mono", "Consolas", "Menlo", "Courier New"],
#                "Courier New")
#    f = QFont(fam, size)
#    f.setStyleHint(QFont.Monospace)
#    f.setWeight(_weight(weight))
#    return f
#
#
#def display_font(size: int = 13, weight=QFont.DemiBold) -> QFont:
#    fam = _pick(["Segoe UI", "Liberation Sans", "Helvetica Neue", "Arial"],
#                "Arial")
#    f = QFont(fam, size)
#    f.setWeight(_weight(weight))
#    return f
#
#
#def eyebrow_font(size: int = 9) -> QFont:
#    fam = _pick(["Segoe UI", "Liberation Sans", "Arial"], "Arial")
#    f = QFont(fam, size)
#    f.setWeight(QFont.Bold)
#    f.setCapitalization(QFont.AllUppercase)
#    f.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
#    return f
#
#
#def build_qss() -> str:
#    return f"""
#* {{ font-family: {_SANS}; color: {INK}; outline: none; }}
#QMainWindow, QWidget {{ background: {WINDOW}; }}
#QLabel {{ background: transparent; }}
#
#/* topbar */
##TopBar {{ background: {PANEL}; border-bottom: 1px solid {LINE}; }}
##BrandTitle {{ font-size: 19px; font-weight: 700; letter-spacing: -0.4px; color: {INK}; }}
##BrandAccent {{ font-size: 19px; font-weight: 700; letter-spacing: -0.4px; color: {AMBER}; }}
##BrandSub {{ color: {INK3}; font-size: 11px; font-weight: 600; }}
##DatasetTag {{
#    color: {INK2}; background: {SUBTLE}; border: 1px solid {LINE};
#    border-radius: 8px; padding: 4px 10px; font-family: {_MONO}; font-size: 11px;
#}}
#
#/* dock */
#QDockWidget {{ font-weight: 600; color: {INK}; titlebar-close-icon: none; }}
#QDockWidget::title {{
#    background: {SUBTLE}; color: {INK2}; padding: 7px 12px; font-weight: 700;
#    border-bottom: 1px solid {LINE};
#}}
#QDockWidget::float-button, QDockWidget::close-button {{
#    background: {PANEL}; border: 1px solid {LINE}; border-radius: 4px;
#}}
#
#/* stage bar — the overlay controls, docked over the image */
#QWidget#StageBar {{ background: {PANEL}; border-bottom: 1px solid {LINE}; }}
#
#/* cards */
#QFrame#Card {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 14px; }}
#QLabel#SectionTitle {{ font-weight: 700; font-size: 13px; color: {INK}; }}
#QLabel#Eyebrow {{ color: {INK3}; font-weight: 700; }}
#QLabel#Hint {{ color: {INK3}; font-size: 11px; }}
#QLabel#Mono {{ font-family: {_MONO}; color: {INK2}; }}
#QLabel#Measured {{
#    font-family: {_MONO}; color: {INK}; background: {SUBTLE};
#    border-left: 3px solid {INFO}; padding: 7px 10px; border-radius: 0 6px 6px 0;
#}}
#
#/* buttons */
#QPushButton {{
#    background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px;
#    padding: 7px 13px; font-weight: 600; color: {INK};
#}}
#QPushButton:hover {{ border-color: {AMBER}; color: {AMBER_PRESS}; }}
#QPushButton:pressed {{ background: {SUBTLE}; }}
#QPushButton#Primary {{ background: {AMBER}; border: 1px solid {AMBER}; color: #FFFFFF; }}
#QPushButton#Primary:hover {{ background: {AMBER_HOVER}; border-color: {AMBER_HOVER}; color: {ON_AMBER}; }}
#QPushButton#Primary:disabled {{ background: {SUBTLE}; border-color: {LINE}; color: {INK3}; }}
#QPushButton:checked {{ background: {AMBER}; border-color: {AMBER}; color: {ON_AMBER}; }}
#QPushButton:disabled {{ background: {SUBTLE}; color: {INK3}; border-color: {LINE}; }}
#
#/* inputs */
#QLineEdit, QSpinBox, QDoubleSpinBox {{
#    background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px;
#    padding: 5px 8px; font-family: {_MONO};
#    selection-background-color: {AMBER}; selection-color: #FFFFFF;
#}}
#QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {AMBER}; }}
#QSpinBox::up-button, QSpinBox::down-button,
#QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0px; }}
#QComboBox {{
#    background: {PANEL}; border: 1px solid {LINE}; border-radius: 8px;
#    padding: 5px 8px; color: {INK};
#}}
#QComboBox:focus {{ border-color: {AMBER}; }}
#QComboBox QAbstractItemView {{
#    background: {PANEL}; border: 1px solid {LINE}; selection-background-color: {AMBER_SOFT};
#    selection-color: {INK}; outline: none;
#}}
#
#/* checkbox */
#QCheckBox {{ font-weight: 600; spacing: 8px; }}
#QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {LINE};
#    border-radius: 5px; background: {PANEL}; }}
#QCheckBox::indicator:checked {{ background: {AMBER}; border-color: {AMBER}; }}
#
#/* lists */
#QListWidget {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; outline: none; }}
#QListWidget::item {{ padding: 6px 8px; border-radius: 7px; }}
#QListWidget::item:selected {{ background: {AMBER_SOFT}; color: {INK}; }}
#
#/* tabs (workspace) */
#QTabWidget::pane {{ border: none; background: transparent; }}
#QTabBar::tab {{ background: {SUBTLE}; border: 1px solid {LINE}; border-bottom: none;
#    padding: 7px 16px; font-weight: 600; color: {INK2}; border-radius: 8px 8px 0 0; }}
#QTabBar::tab:selected {{ background: {PANEL}; color: {INK}; }}
#
#/* scroll + status + tooltip */
#QScrollArea {{ border: none; background: transparent; }}
#QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
#QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 5px; min-height: 24px; }}
#QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
#QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
#QScrollBar::handle:horizontal {{ background: {LINE}; border-radius: 5px; min-width: 24px; }}
#QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
#QStatusBar {{ background: {PANEL}; color: {INK2}; border-top: 1px solid {LINE}; }}
#QStatusBar::item {{ border: none; }}
#QToolTip {{ background: {INK}; color: #FFFFFF; border: none; padding: 5px 8px; border-radius: 6px; }}
#"""
#
#
#def glyph_icon(kind: str, color: str = INK2, size: int = 18):
#    """A small hand-drawn icon.
#
#    Drawn rather than shipped: the repo travels to the offline machine as one
#    plain-text file, which carries no binary assets — so every pixel PEAR
#    shows has to come from code. Rendered at 2× and handed to Qt as a pixmap,
#    so it stays sharp on a scaled display.
#
#    ``kind`` is ``"import"`` (an arrow coming down into a tray) or
#    ``"export"`` (one leaving it).
#    """
#    from PySide6.QtCore import QPointF, Qt
#    from PySide6.QtGui import QIcon, QPainter, QPen, QPixmap
#
#    scale = 2
#    pm = QPixmap(size * scale, size * scale)
#    pm.setDevicePixelRatio(scale)
#    pm.fill(Qt.transparent)
#    p = QPainter(pm)
#    p.setRenderHint(QPainter.Antialiasing, True)
#    pen = QPen(QColor(color), max(1.4, size * 0.1))
#    pen.setCapStyle(Qt.RoundCap)
#    pen.setJoinStyle(Qt.RoundJoin)
#    p.setPen(pen)
#    u = size / 18.0                       # the drawing is designed at 18 px
#    # the tray: open at the top, so the arrow reads as going in or coming out
#    p.drawLine(QPointF(3.5 * u, 11.5 * u), QPointF(3.5 * u, 14.5 * u))
#    p.drawLine(QPointF(3.5 * u, 14.5 * u), QPointF(14.5 * u, 14.5 * u))
#    p.drawLine(QPointF(14.5 * u, 14.5 * u), QPointF(14.5 * u, 11.5 * u))
#    # the shaft and its head
#    if kind == "export":
#        p.drawLine(QPointF(9 * u, 11 * u), QPointF(9 * u, 3 * u))
#        p.drawLine(QPointF(5.8 * u, 6.2 * u), QPointF(9 * u, 3 * u))
#        p.drawLine(QPointF(12.2 * u, 6.2 * u), QPointF(9 * u, 3 * u))
#    else:
#        p.drawLine(QPointF(9 * u, 3 * u), QPointF(9 * u, 11 * u))
#        p.drawLine(QPointF(5.8 * u, 7.8 * u), QPointF(9 * u, 11 * u))
#        p.drawLine(QPointF(12.2 * u, 7.8 * u), QPointF(9 * u, 11 * u))
#    p.end()
#    return QIcon(pm)
#
#
#def apply_theme(app, *_ignored) -> None:
#    """Apply the light theme to a QApplication (single theme; args ignored)."""
#    app.setStyleSheet(build_qss())
#    fam = _pick(["Segoe UI", "Liberation Sans", "Helvetica Neue", "Arial"], "Arial")
#    app.setFont(QFont(fam, 10))
#
#F 8b0f01398ca9f38d805504068d50852ea9ed0acc 3014 pear/ui/widgets.py
#"""Workspace widgets: the control rail (Groups / ROIs / Metrics), a
#box-and-strip distribution chart, and the Analysis panel (hosted in its own
#window).
#
#No charting dependency — every plot is hand-painted with QPainter.
#"""
#
#from __future__ import annotations
#
#from typing import Callable, List, Optional
#
#import numpy as np
#from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
#from PySide6.QtGui import (QColor, QImage, QPainter, QPen, QPixmap,
#                           QRegion)
#from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
#                               QDialogButtonBox, QDoubleSpinBox, QFrame,
#                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
#                               QMenu, QPushButton, QRadioButton, QScrollArea,
#                               QSpinBox, QToolButton, QVBoxLayout, QWidget)
#
#from pear.core.analysis import (Group, cell_edges, heat_color,
#                               linear_trend, pixel_hist,
#                               profile_by_position, uniformity)
#from pear.core.attributes import GLV_STATS, metric_formula, metric_label
#from pear.ui import theme
#
#
## --------------------------------------------------------------------------- #
## helpers
## --------------------------------------------------------------------------- #
#def _card(title: str, sub: str = "") -> QFrame:
#    frame = QFrame()
#    frame.setObjectName("Card")
#    lay = QVBoxLayout(frame)
#    lay.setContentsMargins(14, 12, 14, 14)
#    lay.setSpacing(10)
#    head = QHBoxLayout()
#    head.setSpacing(7)
#    t = QLabel(title)
#    t.setObjectName("SectionTitle")
#    t.setFont(theme.display_font(13, weight=700))
#    head.addWidget(t)
#    if sub:
#        s = QLabel(sub)
#        s.setObjectName("Hint")
#        head.addWidget(s)
#    head.addStretch(1)
#    frame._head = head           # type: ignore[attr-defined]
#    lay.addLayout(head)
#    return frame
#
#
#def _icon_button(kind: str, tooltip: str) -> QToolButton:
#    """A small icon-only button, drawn rather than shipped."""
#    b = QToolButton()
#    b.setIcon(theme.glyph_icon(kind))
#    b.setIconSize(QSize(18, 18))
#    b.setFixedSize(28, 26)
#    b.setAutoRaise(True)
#    b.setToolTip(tooltip)
#    return b
#
#
#def _swatch(color: str, on_pick: Callable[[str], None]) -> QPushButton:
#    b = QPushButton()
#    b.setFixedSize(16, 16)
#    b.setStyleSheet(
#        f"background:{color}; border:1px solid rgba(0,0,0,.15); border-radius:4px;")
#
#    def choose():
#        c = QColorDialog.getColor(QColor(color))
#        if c.isValid():
#            on_pick(c.name())
#    b.clicked.connect(choose)
#    return b
#
#
#def save_widget_image(widget, path: str, scale: float = 3.0,
#                      crop=None, background=None) -> Optional[str]:
#    """Save a painted widget as a picture: SVG if the name says so, else PNG.
#
#    Every view in PEAR is hand-painted with QPainter, so the same two lines
#    serve all of them — SVG keeps real curves and text for print, PNG is
#    rendered at ``scale`` × the on-screen size because a 1× screenshot of a
#    chart is unreadable once a projector or a journal column has it. ``crop``
#    (widget coordinates) trims to the part worth keeping.
#    """
#    if widget is None:
#        return None
#    area = QRect(crop) if crop is not None else widget.rect()
#    w, h = max(1, area.width()), max(1, area.height())
#    bg = QColor(background or theme.CARD)
#    if str(path).lower().endswith(".svg"):
#        try:
#            from PySide6.QtSvg import QSvgGenerator
#        except ImportError:
#            return None
#        gen = QSvgGenerator()
#        gen.setFileName(path)
#        gen.setSize(QSize(w, h))
#        gen.setViewBox(area)              # the viewBox does the cropping
#        painter = QPainter()
#        if not painter.begin(gen):
#            return None
#        painter.fillRect(QRectF(area), bg)
#        widget.render(painter, QPoint(0, 0), QRegion(area))
#        painter.end()
#        return path
#    scale = float(np.clip(scale, 1.0, 8.0))
#    full = QPixmap(int(widget.width() * scale), int(widget.height() * scale))
#    full.setDevicePixelRatio(scale)
#    full.fill(bg)
#    widget.render(full)
#    pm = full.copy(QRect(int(area.x() * scale), int(area.y() * scale),
#                         int(w * scale), int(h * scale)))
#    pm.setDevicePixelRatio(scale)
#    return path if pm.save(path) else None
#
#
#def _clear(layout) -> None:
#    """Empty a layout, hiding each widget *now*.
#
#    ``deleteLater`` only schedules the removal: until the event loop runs, a
#    widget taken out of a layout keeps its parent and its last geometry, so a
#    rebuilt list paints its stale rows over whatever sits under them (the
#    Groups card's own title and Add button, for one). Hiding ends that on the
#    spot.
#
#    It has to be ``hide()`` and not ``setParent(None)``: these lists are
#    rebuilt *from* the rows' own signals — click a ROI row and the refresh it
#    triggers clears the list that row is in — and a widget reparented to None
#    becomes a top-level window while its own event is still on the stack. That
#    is a blank window flashing up per click, and then a crash.
#    """
#    while layout.count():
#        it = layout.takeAt(0)
#        w = it.widget()
#        if w is not None:
#            w.hide()
#            w.deleteLater()
#
#
## --------------------------------------------------------------------------- #
## Distribution chart (box + jittered strip)
## --------------------------------------------------------------------------- #
#class DistributionChart(QWidget):
#    """Vertical box-and-strip plot, an overlaid histogram, a position
#    profile (the metric against where each ROI sits on the image), or a
#    spatial heat map of the ROIs."""
#
#    def __init__(self, parent=None):
#        super().__init__(parent)
#        self._title = ""
#        self._series: List[dict] = []
#        self._ctype = "box"
#        self._opts = {"points": True, "whiskers": True, "cells": True}
#        self._axis = "x"
#        self._trend = True
#        self._xlabel = ""
#        self._style: dict = {}
#        self.setMinimumHeight(212)
#        # a distribution reads as a figure at roughly 4:3; letterboxed across
#        # a wide window it flattens and the page looks lopsided
#        sp = self.sizePolicy()
#        sp.setHeightForWidth(True)
#        self.setSizePolicy(sp)
#
#    def set_data(self, title: str, series: List[dict], ctype: str = "box",
#                 opts=None, axis: str = "x", trend: bool = True,
#                 xlabel: str = "", style=None) -> None:
#        self._title = title
#        self._xlabel = xlabel or title
#        self._style = dict(style or {})
#        self._ctype = ctype
#        self._opts = {"points": True, "whiskers": True, "cells": True,
#                      **(opts or {})}
#        self._axis = "y" if str(axis).lower() == "y" else "x"
#        self._trend = bool(trend)
#        clean = []
#        for s in series:
#            v = np.asarray(s["values"], dtype=np.float64)
#            keep = np.isfinite(v)
#            if not keep.any():
#                continue
#            item = {"label": s["label"], "color": s["color"], "values": v[keep]}
#            # positions are index-aligned with values, so they take the same mask
#            for key in ("pos_x", "pos_y"):
#                arr = s.get(key)
#                if arr is None:
#                    continue
#                arr = np.asarray(arr, dtype=np.float64)
#                if arr.size == v.size:
#                    item[key] = arr[keep]
#            clean.append(item)
#        self._series = clean
#        if ctype == "position":
#            self.setMinimumHeight(300)
#        elif ctype == "map":
#            self.setMinimumHeight(320)
#        else:
#            self.setMinimumHeight(212)
#        self.update()
#
#    def sizeHint(self) -> QSize:
#        # without one, a layout column with no stretch falls back to the
#        # minimum and the figure comes out as narrow as it is allowed to be
#        w = 720
#        return QSize(w, self.heightForWidth(w))
#
#    def hasHeightForWidth(self) -> bool:
#        return True
#
#    def heightForWidth(self, w: int) -> int:
#        """Every chart keeps a shape you can read.
#
#        A distribution wants roughly 4:3. A profile or a map runs the width of
#        the column, and at a fixed height that turns into a letterbox: the
#        values are squeezed into a band a few pixels tall, where a real tilt
#        and a flat line look the same.
#        """
#        if self._ctype in ("box", "hist"):
#            h = min(w * 0.78, 560)
#        else:
#            h = min(w * 0.58, 640)
#        return int(max(self.minimumHeight(), h))
#
#    # -- style overrides (title, axis names, tick counts, ranges) ------ #
#    def _st(self, key: str, default=None):
#        v = self._style.get(key)
#        return default if v is None or v == "" else v
#
#    def _font(self, delta: int = 0, weight=None):
#        """Tick-value text: the size the user asked for (8 pt by default),
#        bold if they asked for that too."""
#        size = self._st("font_pt", 8)
#        try:
#            size = float(size)
#        except (TypeError, ValueError):
#            size = 8.0
#        size = float(np.clip(size + delta, 5.0, 24.0))
#        if weight is None and self._st("tick_bold", False):
#            weight = 700
#        return (theme.mono_font(size, weight=weight) if weight
#                else theme.mono_font(size))
#
#    def _label_font(self):
#        """Axis-name text — its own size and weight, so the names can carry
#        the figure while the tick values stay small (or the other way round)."""
#        size = self._st("label_pt", self._st("font_pt", 8))
#        try:
#            size = float(size)
#        except (TypeError, ValueError):
#            size = 8.0
#        size = float(np.clip(size, 5.0, 24.0))
#        bold = self._st("label_bold", True)
#        return theme.mono_font(size, weight=700 if bold else 500)
#
#    def _label_ink(self) -> "QColor":
#        """Axis-name ink — its own, so a name can carry more weight than the
#        numbers beside it (or less)."""
#        return QColor(self._st("label_ink", self._st("axis_ink", theme.INK)))
#
#    def _axis_ink(self) -> "QColor":
#        """Tick and axis-name ink. Dark by default — a chart that ends up in a
#        report is read on paper and on a projector, where a light grey tick
#        label is simply not there."""
#        return QColor(self._st("axis_ink", theme.INK))
#
#    def _mark_color(self, key: str, series_color) -> "QColor":
#        return QColor(self._st(key, series_color))
#
#    def _nticks(self, key: str, default: int) -> int:
#        try:
#            return int(np.clip(int(self._st(key, default)), 2, 12))
#        except (TypeError, ValueError):
#            return default
#
#    def title_text(self) -> str:
#        """What the chart is called — the override, or the metric it plots."""
#        return str(self._st("title", self._title))
#
#    def paintEvent(self, _e) -> None:
#        p = QPainter(self)
#        p.setRenderHint(QPainter.Antialiasing, True)
#        p.fillRect(self.rect(), QColor(theme.CARD))
#        p.setPen(QColor(theme.INK))
#        p.setFont(theme.display_font(12, weight=700))
#        # centred over the plot, where a figure caption goes
#        p.drawText(QRectF(8, 5, self.width() - 16, 19),
#                   Qt.AlignHCenter | Qt.AlignVCenter, self.title_text())
#        if not self._series:
#            p.setPen(self._axis_ink())
#            p.setFont(self._font(1))
#            p.drawText(self.rect(), Qt.AlignCenter, "no data")
#            p.end()
#            return
#        if self._ctype == "hist":
#            self._paint_hist(p)
#        elif self._ctype == "position":
#            self._paint_position(p)
#        elif self._ctype == "map":
#            self._paint_map(p)
#        else:
#            self._paint_box(p)
#        p.end()
#
#    # -- shared figure furniture -------------------------------------- #
#    def _frame(self, p: QPainter, left, top, right, bottom,
#               xticks=(), yticks=()) -> None:
#        """A boxed plot area with inward tick marks — the plain conventions a
#        figure in a report follows, so the chart reads the same on a slide as
#        it does on screen."""
#        p.setPen(QPen(self._axis_ink(), 1.2))
#        p.setBrush(Qt.NoBrush)
#        p.drawRect(QRectF(left, top, right - left, bottom - top))
#        for gx in xticks:
#            p.drawLine(QPointF(gx, bottom), QPointF(gx, bottom - 4))
#            p.drawLine(QPointF(gx, top), QPointF(gx, top + 4))
#        for gy in yticks:
#            p.drawLine(QPointF(left, gy), QPointF(left + 4, gy))
#            p.drawLine(QPointF(right, gy), QPointF(right - 4, gy))
#
#    def _marker(self, p: QPainter, x, y, color, rad=None) -> None:
#        """One observation. Open — white centre, coloured rim — so a scatter
#        never merges into the lines drawn in the same colour beside it."""
#        if rad is None:
#            try:
#                rad = float(np.clip(float(self._st("point_size", 3.2)),
#                                    0.5, 20.0))
#            except (TypeError, ValueError):
#                rad = 3.2
#        col = self._mark_color("point_color", color)
#        p.setBrush(QColor(255, 255, 255, 230))
#        p.setPen(QPen(col, max(0.6, rad * 0.4)))
#        p.drawEllipse(QPointF(x, y), rad, rad)
#
#    def _line_w(self, default: float) -> float:
#        try:
#            return float(np.clip(float(self._st("line_width", default)),
#                                 0.3, 12.0))
#        except (TypeError, ValueError):
#            return default
#
#    def _locked(self, lo, hi, kmin: str, kmax: str):
#        """The range the user pinned, or the one the data suggested."""
#        vmin, vmax = self._st(kmin), self._st(kmax)
#        try:
#            if vmin is not None and vmax is not None and float(vmax) > float(vmin):
#                return float(vmin), float(vmax)
#        except (TypeError, ValueError):
#            pass
#        return lo, hi
#
#    def _range(self):
#        vmin, vmax = self._st("vmin"), self._st("vmax")
#        if vmin is not None and vmax is not None and float(vmax) > float(vmin):
#            return float(vmin), float(vmax)     # locked: comparable between runs
#        allv = np.concatenate([s["values"] for s in self._series])
#        lo, hi = float(allv.min()), float(allv.max())
#        if hi - lo < 1e-9:
#            lo -= 0.5
#            hi += 0.5
#        pad = (hi - lo) * 0.08
#        return lo - pad, hi + pad
#
#    def _left_gutter(self, p: QPainter, texts) -> float:
#        """Room for the widest tick label *and* the rotated axis name.
#
#        Both live to the left of the plot, so the margin has to be measured
#        from the fonts in use — hard-coded, the tick values grow into the axis
#        name the moment either is set larger, and the numbers come out half
#        drawn.
#        """
#        p.setFont(self._font())
#        fm = p.fontMetrics()
#        wide = max([fm.horizontalAdvance(str(t)) for t in texts] + [0])
#        p.setFont(self._label_font())
#        return float(np.clip(p.fontMetrics().height() + 12 + wide + 8,
#                             42, 260))
#
#    def _tick_box(self, gx: float, y: float, h: float) -> QRectF:
#        """A tick label's box, kept inside the card.
#
#        The first and last tick sit on the frame, and centring a wide number
#        there hangs half of it off the edge of the figure.
#        """
#        x = float(np.clip(gx - 40.0, 1.0, max(1.0, self.width() - 81.0)))
#        return QRectF(x, y, 80, h)
#
#    def _bottom_gutter(self, p: QPainter, label_rows: int = 1,
#                       extra: float = 0.0) -> float:
#        """Room under the plot for the tick row, the axis name, and whatever
#        the chart adds below them."""
#        p.setFont(self._font())
#        tick_h = p.fontMetrics().height()
#        p.setFont(self._label_font())
#        name_h = p.fontMetrics().height()
#        return float(tick_h + 8 + label_rows * (name_h + 4) + extra)
#
#    def _ytitle(self, p: QPainter, text: str) -> None:
#        p.save()
#        p.setFont(self._label_font())
#        p.setPen(self._label_ink())
#        fm = p.fontMetrics()
#        tw = fm.horizontalAdvance(text)
#        p.translate(fm.height() * 0.85, self.height() / 2.0)
#        p.rotate(-90)
#        p.drawText(int(-tw / 2), 0, text)
#        p.restore()
#
#    # -- vertical box + jittered strip -------------------------------- #
#    def _paint_box(self, p: QPainter) -> None:
#        """Box-and-strip per group, on a shared value axis by default.
#
#        A shared axis is the comparison — it is what makes one group sitting
#        above another visible. But a group whose spread is a hundredth of the
#        gap between groups collapses to a line on it, and its shape is exactly
#        what a within-group reader is after; ``own_scale`` gives every lane
#        its own range, printed above and below the lane so nothing is implied
#        about how the lanes relate.
#        """
#        own = bool(self._opts.get("own_scale", False))
#        glo, ghi = self._range()
#        ny0 = self._nticks("yticks", 5)
#        tick_texts = ([] if own else
#                      [_fmt(ghi - (ghi - glo) * t / (ny0 - 1.0))
#                       for t in range(ny0)])
#        top = 34
#        left = self._left_gutter(p, tick_texts or ["0"])
#        # a lane label under the axis, a range line under that with own scale,
#        # and an x name when one is set
#        rows = 1 + (1 if own else 0) + (1 if self._st("xlabel", "") else 0)
#        bottom = self.height() - self._bottom_gutter(p, rows)
#        right = self.width() - 12
#        H = max(10, bottom - top)
#        W = max(10, right - left)
#        n = len(self._series)
#
#        def lane_range(v):
#            lo, hi = float(v.min()), float(v.max())
#            if hi - lo < 1e-9:
#                lo, hi = lo - 0.5, hi + 0.5
#            pad = (hi - lo) * 0.08
#            return lo - pad, hi + pad
#
#        p.setFont(self._font())
#        ny = self._nticks("yticks", 5)
#        gridys = [top + H * t / (ny - 1.0) for t in range(ny)]
#        for t, gy in enumerate(gridys):
#            p.setPen(QPen(QColor(theme.LINE2), 1))
#            p.drawLine(left, int(gy), right, int(gy))
#            if own:                     # one label per lane instead, below
#                continue
#            p.setPen(self._axis_ink())
#            p.drawText(QRectF(0, gy - 9, left - 8, 18),
#                       Qt.AlignRight | Qt.AlignVCenter,
#                       _fmt(ghi - (ghi - glo) * t / (ny - 1.0)))
#        self._frame(p, left, top, right, bottom, yticks=() if own else gridys)
#        self._ytitle(p, self._st("ylabel", "value · own scale per group"
#                                 if own else "value"))
#        xlab = self._st("xlabel", "")
#        if xlab:
#            p.setPen(self._label_ink())
#            p.setFont(self._label_font())
#            p.drawText(QRectF(left, self.height() - p.fontMetrics().height() - 3,
#                              W, p.fontMetrics().height()),
#                       Qt.AlignHCenter, str(xlab))
#
#        lane = W / n
#        for i, s in enumerate(self._series):
#            v = s["values"]
#            col = QColor(s["color"])
#            cx = left + lane * (i + 0.5)
#            bw = min(48.0, lane * 0.5)
#            lo, hi = lane_range(v) if own else (glo, ghi)
#
#            def Y(val, lo=lo, hi=hi):
#                return bottom - (val - lo) / (hi - lo) * H
#
#            q25, med, q75 = (float(np.percentile(v, 25)),
#                             float(np.median(v)), float(np.percentile(v, 75)))
#            vmin, vmax = float(v.min()), float(v.max())
#            if self._opts.get("whiskers", True):
#                p.setPen(QPen(col, 1))
#                p.drawLine(int(cx), int(Y(vmax)), int(cx), int(Y(vmin)))
#                for yy in (vmin, vmax):
#                    p.drawLine(int(cx - bw * 0.22), int(Y(yy)),
#                               int(cx + bw * 0.22), int(Y(yy)))
#            # IQR box
#            box = QColor(col)
#            box.setAlpha(48)
#            p.setBrush(box)
#            p.setPen(QPen(col, 1))
#            p.drawRect(int(cx - bw / 2), int(Y(q75)),
#                       int(bw), max(2, int(Y(q25) - Y(q75))))
#            if self._opts.get("points", True):
#                for k, val in enumerate(v):
#                    jitter = ((k % 7) / 6.0 - 0.5) * bw * 0.72
#                    self._marker(p, cx + jitter, Y(val), col)
#            # median
#            p.setPen(QPen(self._mark_color("line_color", col),
#                          self._line_w(2.2)))
#            p.drawLine(int(cx - bw / 2), int(Y(med)), int(cx + bw / 2), int(Y(med)))
#            # mean value, placed just above the column's own data
#            p.setPen(col)
#            p.setFont(self._font(weight=700))
#            my = max(top - 15, Y(vmax) - 16)
#            p.drawText(QRectF(cx - lane / 2, my, lane, 13),
#                       Qt.AlignHCenter | Qt.AlignVCenter, _fmt(float(v.mean())))
#            # label below the column
#            p.setPen(self._axis_ink())
#            p.setFont(self._font())
#            lab = p.fontMetrics().elidedText(str(s["label"]), Qt.ElideRight,
#                                             int(lane))
#            lab_h = p.fontMetrics().height()
#            p.drawText(QRectF(cx - lane / 2, bottom + 4, lane, lab_h + 2),
#                       Qt.AlignHCenter | Qt.AlignVCenter, lab)
#            if not own:
#                continue
#            # this lane's own range, so a stretched lane still says what it
#            # spans and is never mistaken for the one beside it
#            span = hi - lo
#            p.setPen(self._axis_ink())
#            p.drawText(QRectF(cx - lane / 2, bottom + 6 + lab_h, lane,
#                              lab_h + 2),
#                       Qt.AlignHCenter | Qt.AlignVCenter,
#                       f"{_fmt_span(vmin, span)} … {_fmt_span(vmax, span)}")
#        if self._legend_on():
#            self._legend(p, left, top, right,
#                         [(s["label"], s["color"], f"n={s['values'].size}")
#                          for s in self._series])
#
#    # -- position profile (metric vs. where the ROI sits) -------------- #
#    def _paint_position(self, p: QPainter) -> None:
#        """Metric on Y against ROI centre position on X.
#
#        A uniform field reads as a flat line; a tilt or a bow is the
#        non-uniformity. Every ROI is a dot, ROIs sharing a position collapse
#        into the profile line, and the dashed line is the least-squares fit.
#        """
#        key = "pos_y" if self._axis == "y" else "pos_x"
#        series = [s for s in self._series
#                  if s.get(key) is not None and s[key].size]
#        if not series:
#            p.setPen(self._axis_ink())
#            p.setFont(self._font(1))
#            p.drawText(self.rect(), Qt.AlignCenter,
#                       "no per-ROI position for this metric")
#            return
#
#        allv = np.concatenate([s["values"] for s in series])
#        allx = np.concatenate([s[key] for s in series])
#        lo, hi = float(allv.min()), float(allv.max())
#        if hi - lo < 1e-9:
#            lo, hi = lo - 0.5, hi + 0.5
#        pad = (hi - lo) * 0.12
#        lo, hi = lo - pad, hi + pad
#        lo, hi = self._locked(lo, hi, "vmin", "vmax")
#        xlo, xhi = float(allx.min()), float(allx.max())
#        if xhi - xlo < 1e-9:
#            xlo, xhi = xlo - 1.0, xhi + 1.0
#        xpad = (xhi - xlo) * 0.04
#        xlo, xhi = xlo - xpad, xhi + xpad
#        # the position axis locks too: two runs of the same field only line up
#        # if both are drawn across the same span of the image
#        xlo, xhi = self._locked(xlo, xhi, "xmin", "xmax")
#
#        # value labels can need many decimals on a near-flat profile, so size
#        # the gutter from the widest one rather than a fixed guess
#        p.setFont(self._font())
#        fm = p.fontMetrics()
#        ny = self._nticks("yticks", 5)
#        ticks = [_fmt_span(hi - (hi - lo) * t / (ny - 1.0), hi - lo)
#                 for t in range(ny)]
#        top = 34
#        left = self._left_gutter(p, ticks)
#        bottom = max(top + 40, self.height() - self._bottom_gutter(p))
#        right = self.width() - 12
#        H = max(10, bottom - top)
#        W = max(10, right - left)
#
#        def X(v):
#            return left + (v - xlo) / (xhi - xlo) * W
#
#        def Y(v):
#            return bottom - (v - lo) / (hi - lo) * H
#
#        # grid + value axis
#        gridys = [top + H * t / (ny - 1.0) for t in range(ny)]
#        for gy, lab in zip(gridys, ticks):
#            p.setPen(QPen(QColor(theme.LINE2), 1))
#            p.drawLine(left, int(gy), right, int(gy))
#            p.setPen(self._axis_ink())
#            p.drawText(QRectF(0, gy - 9, left - 8, 18),
#                       Qt.AlignRight | Qt.AlignVCenter, lab)
#        self._ytitle(p, self._st("ylabel", "value"))
#
#        # position axis
#        nx = self._nticks("xticks", 5)
#        xs = [left + W * t / (nx - 1.0) for t in range(nx)]
#        self._frame(p, left, top, right, bottom, xticks=xs, yticks=gridys)
#        p.setPen(self._axis_ink())
#        p.setFont(self._font())
#        tick_h = p.fontMetrics().height()
#        for t, gx in enumerate(xs):
#            p.drawText(self._tick_box(gx, bottom + 3, tick_h),
#                       Qt.AlignHCenter,
#                       f"{xlo + (xhi - xlo) * t / (nx - 1.0):.0f}")
#        p.setPen(self._label_ink())
#        p.setFont(self._label_font())
#        p.drawText(QRectF(left, bottom + 5 + tick_h, W,
#                          p.fontMetrics().height()), Qt.AlignHCenter,
#                   str(self._st("xlabel",
#                                f"ROI centre {self._axis.upper()} (px)")))
#
#        rows = []
#        for s in series:
#            col = QColor(s["color"])
#            px_, v = s[key], s["values"]
#
#            # Drawn back to front: the two reference lines first, then the
#            # data on top of them. The other way round the amber trend hides
#            # the profile it is meant to be compared against.
#            fit = linear_trend(px_, v)
#
#            # group mean — where a perfectly flat profile would sit
#            mean = float(v.mean())
#            ref = QColor(col)
#            ref.setAlpha(70)
#            pen = QPen(ref, 1)
#            pen.setStyle(Qt.DashLine)
#            p.setPen(pen)
#            p.setBrush(Qt.NoBrush)
#            p.drawLine(left, int(Y(mean)), right, int(Y(mean)))
#
#            # least-squares tilt — the brand accent, so it never reads as data
#            if self._trend and fit is not None:
#                slope, inter = fit
#                pen = QPen(QColor(theme.AMBER), self._line_w(2.2) * 0.75)
#                pen.setStyle(Qt.DashLine)
#                p.setPen(pen)
#                p.setBrush(Qt.NoBrush)
#                y0 = min(hi, max(lo, slope * xlo + inter))
#                y1 = min(hi, max(lo, slope * xhi + inter))
#                p.drawLine(QPointF(X(xlo), Y(y0)), QPointF(X(xhi), Y(y1)))
#
#            # every ROI as an open marker — the profile line runs through
#            # them in the same hue, and filled dots would fuse with it
#            for a, b in zip(px_, v):
#                self._marker(p, X(a), Y(b), col)
#
#            # profile line through the mean of the ROIs at each position.
#            # Deliberately a darker shade than the dots: same colour at the
#            # same weight and the line disappears into its own scatter.
#            cx, cy = profile_by_position(px_, v)
#            if cx.size >= 2:
#                p.setPen(QPen(self._mark_color("line_color", col.darker(190)),
#                              self._line_w(2.2)))
#                p.setBrush(Qt.NoBrush)
#                pts = [QPointF(X(a), Y(b)) for a, b in zip(cx, cy)]
#                for a, b in zip(pts, pts[1:]):
#                    p.drawLine(a, b)
#
#            # the flatness numbers ride in the legend, not under the axis:
#            # below the plot they crowd the axis name and get clipped
#            u = uniformity(v)
#            txt = (f"n={u['n']}"
#                   f" · mean {_fmt_span(u['mean'], u['range'] or 1.0)}"
#                   f" · range {_fmt(u['range'])} ({_pct(u['range_pct'])})"
#                   f" · CV {_pct(u['cv_pct'])}")
#            if fit is not None:
#                txt += f" · slope {fit[0] * 100:+.3g}/100px"
#            rows.append((s["label"], s["color"], txt))
#        if self._legend_on():
#            self._legend(p, left, top, right, rows,
#                         keys=self._line_key_rows())
#
#    def _line_key_rows(self):
#        """What each line in the profile means — three of them look alike."""
#        return [("profile — mean at each position",
#                 QColor(theme.INK2), Qt.SolidLine),
#                ("trend — least squares fit",
#                 QColor(theme.AMBER), Qt.DashLine),
#                ("group mean — where flat would sit",
#                 QColor(theme.INK3), Qt.DashLine)]
#
#    # -- spatial heat map (ROI layout coloured by the metric) ---------- #
#    def _paint_map(self, p: QPainter) -> None:
#        """Every ROI drawn where it sits, coloured by its metric value.
#
#        As **cells** (the default) each ROI spans the gap to its neighbour, so
#        the field reads as one surface and a cell can be compared against the
#        one beside it; as **dots** the ROIs stay separate marks. Y runs
#        downward to match the image. A uniform field is one flat colour; a
#        gradient or a hot corner is the non-uniformity.
#        """
#        series = [s for s in self._series
#                  if s.get("pos_x") is not None and s.get("pos_y") is not None
#                  and s["pos_x"].size]
#        if not series:
#            p.setPen(self._axis_ink())
#            p.setFont(self._font(1))
#            p.drawText(self.rect(), Qt.AlignCenter,
#                       "no per-ROI position for this metric")
#            return
#
#        allv = np.concatenate([s["values"] for s in series])
#        allx = np.concatenate([s["pos_x"] for s in series])
#        ally = np.concatenate([s["pos_y"] for s in series])
#        lo, hi = float(allv.min()), float(allv.max())
#        hmin, hmax = self._st("heat_vmin"), self._st("heat_vmax")
#        if hmin is not None and hmax is not None and float(hmax) > float(hmin):
#            lo, hi = float(hmin), float(hmax)   # locked: comparable between runs
#        flat = (hi - lo) < 1e-9
#        vspan = 1.0 if flat else hi - lo
#
#        cells = bool(self._opts.get("cells", True))
#        equal = bool(self._opts.get("equal_cells", True))
#        show_val = bool(self._opts.get("map_values", False))
#        xc, xe = cell_edges(allx)
#        yc, ye = cell_edges(ally)
#
#        def median_step(e):
#            return float(np.median(np.diff(e))) if e.size > 2 else 0.0
#
#        cw, ch = median_step(xe), median_step(ye)
#        if cells:
#            # a single column (or row) has no pitch of its own — it borrows
#            # the other axis's, so the cells stay square instead of hairlines
#            if xc.size == 1 and ch > 0:
#                xe, cw = np.asarray([xc[0] - ch / 2, xc[0] + ch / 2]), ch
#            if yc.size == 1 and cw > 0:
#                ye, ch = np.asarray([yc[0] - cw / 2, yc[0] + cw / 2]), cw
#            xlo, xhi = float(xe[0]), float(xe[-1])   # cells fill the plot box
#            ylo, yhi = float(ye[0]), float(ye[-1])
#            xlo, xhi = self._locked(xlo, xhi, "xmin", "xmax")
#            ylo, yhi = self._locked(ylo, yhi, "ymin", "ymax")
#            if xhi - xlo < 1e-9:
#                xlo, xhi = xlo - 1.0, xhi + 1.0
#            if yhi - ylo < 1e-9:
#                ylo, yhi = ylo - 1.0, yhi + 1.0
#        else:
#            def span(a):
#                v0, v1 = float(a.min()), float(a.max())
#                pad = max((v1 - v0) * 0.08, 0.5)
#                v0, v1 = v0 - pad, v1 + pad
#                if v1 - v0 < 1e-9:
#                    v0, v1 = v0 - 1.0, v1 + 1.0
#                return v0, v1
#
#            xlo, xhi = self._locked(*span(allx), "xmin", "xmax")
#            ylo, yhi = self._locked(*span(ally), "ymin", "ymax")
#
#        top = 34
#        left = self._left_gutter(
#            p, [f"{ylo + (yhi - ylo) * t / 2.0:.0f}" for t in range(3)])
#        # the colour bar carries its own end labels, so the strip reserved for
#        # it has to be as wide as the widest of them — at 16 pt "152" no
#        # longer fits the 38 px a fixed width used to leave, and the number
#        # walked off the card
#        p.setFont(self._font())
#        bar_fm = p.fontMetrics()
#        cbar_txt = [_fmt_span(hi, hi - lo), _fmt_span(lo, hi - lo), "locked"]
#        cbar_lab = max(bar_fm.horizontalAdvance(t) for t in cbar_txt)
#        cbar_w = 16 + 12 + 6 + cbar_lab
#        foot_h = bar_fm.height()
#        # the tick row, the axis name, and the summary line under both
#        bottom = max(top + 40, self.height()
#                     - self._bottom_gutter(p, 1, extra=foot_h + 10))
#        right = self.width() - 12 - cbar_w
#        H = max(10, bottom - top)
#        W = max(10, right - left)
#        sx = W / (xhi - xlo)
#        sy = H / (yhi - ylo)
#
#        def X(v):
#            return left + (v - xlo) * sx
#
#        def Y(v):                       # image Y grows downward
#            return top + (v - ylo) * sy
#
#        p.setPen(QPen(QColor(theme.LINE2), 1))
#        p.setBrush(Qt.NoBrush)
#        p.drawRect(int(left), int(top), int(W), int(H))
#        p.setFont(self._font())
#        p.setPen(self._axis_ink())
#        tick_h = p.fontMetrics().height()
#        nx, ny = self._nticks("xticks", 3), self._nticks("yticks", 3)
#        grid_mode = cells and equal and xc.size > 0 and yc.size > 0
#        if grid_mode:
#            # every column is one slot wide, so the tick belongs to the slot,
#            # not to a linear axis — label the ones that fit
#            for t in range(min(nx, int(xc.size))):
#                i = int(round(t * (xc.size - 1) / max(1, min(nx, xc.size) - 1)))
#                gx = left + W * (i + 0.5) / xc.size
#                p.drawText(self._tick_box(gx, bottom + 3, tick_h),
#                           Qt.AlignHCenter, f"{xc[i]:.0f}")
#            for t in range(min(ny, int(yc.size))):
#                j = int(round(t * (yc.size - 1) / max(1, min(ny, yc.size) - 1)))
#                gy = top + H * (j + 0.5) / yc.size
#                p.drawText(QRectF(0, gy - 9, left - 8, 18),
#                           Qt.AlignRight | Qt.AlignVCenter, f"{yc[j]:.0f}")
#        else:
#            for t in range(nx):         # X ticks
#                gx = left + W * t / (nx - 1.0)
#                p.drawText(self._tick_box(gx, bottom + 3, tick_h),
#                           Qt.AlignHCenter,
#                           f"{xlo + (xhi - xlo) * t / (nx - 1.0):.0f}")
#            for t in range(ny):         # Y ticks (top = small y, like the image)
#                gy = top + H * t / (ny - 1.0)
#                p.drawText(QRectF(0, gy - 9, left - 8, 18),
#                           Qt.AlignRight | Qt.AlignVCenter,
#                           f"{ylo + (yhi - ylo) * t / (ny - 1.0):.0f}")
#        p.setPen(self._label_ink())
#        p.setFont(self._label_font())
#        name_h = p.fontMetrics().height()
#        p.drawText(QRectF(left, bottom + 5 + tick_h, W, name_h),
#                   Qt.AlignHCenter,
#                   str(self._st("xlabel", "ROI centre X (px)")))
#        self._ytitle(p, self._st("ylabel", "ROI centre Y (px)"))
#
#        ring = len(series) > 1        # only needed to tell groups apart
#        if cells and equal and xc.size and yc.size:
#            self._paint_map_grid(p, series, xc, yc, left, top, W, H,
#                                 lo, hi, flat, vspan, show_val, ring)
#        elif cells:
#            # One filled cell per ROI, spanning to the boundary it shares with
#            # its neighbour: the difference against the cell next door is the
#            # point of the view, and touching blocks show it where dots cannot.
#            p.setFont(self._font(weight=700))
#            fm = p.fontMetrics()
#            for s in series:
#                edge = QColor(s["color"])
#                for cx, cy, v in zip(s["pos_x"], s["pos_y"], s["values"]):
#                    t = 0.5 if flat else (float(v) - lo) / (hi - lo)
#                    col = heat_color(t)
#                    i = int(np.abs(xc - cx).argmin()) if xe.size > 2 else 0
#                    j = int(np.abs(yc - cy).argmin()) if ye.size > 2 else 0
#                    x0, x1 = X(xe[i]), X(xe[i + 1])
#                    y0, y1 = Y(ye[j]), Y(ye[j + 1])
#                    r = QRectF(x0, y0, x1 - x0, y1 - y0)
#                    p.setBrush(QColor(col))
#                    # a hairline edge separates touching cells without
#                    # opening a gap between them
#                    p.setPen(QPen(edge, 1.2) if ring
#                             else QPen(QColor(0, 0, 0, 45), 0.8))
#                    p.drawRect(r)
#                    if not show_val:
#                        continue
#                    txt = _fmt_span(float(v), vspan)
#                    if (fm.horizontalAdvance(txt) + 6 <= r.width()
#                            and fm.height() <= r.height()):
#                        p.setPen(QColor("#FFFFFF") if _is_dark(col)
#                                 else QColor(theme.INK))
#                        p.drawText(r, Qt.AlignCenter, txt)
#            p.setPen(QPen(QColor(theme.LINE2), 1))   # cells cover the frame
#            p.setBrush(Qt.NoBrush)
#            p.drawRect(int(left), int(top), int(W), int(H))
#        else:
#            # A scatter: one dot per ROI. Size follows the tightest neighbour
#            # spacing only so that dense layouts stay readable.
#            rad = 7.0
#            if allx.size > 1:
#                for arr, sc in ((allx, sx), (ally, sy)):
#                    u = np.unique(np.round(arr, 0))
#                    if u.size > 1:
#                        rad = min(rad, float(np.min(np.diff(u))) * sc * 0.34)
#            rad = float(np.clip(rad, 2.5, 9.0))
#            for s in series:
#                edge = QColor(s["color"])
#                for cx, cy, v in zip(s["pos_x"], s["pos_y"], s["values"]):
#                    t = 0.5 if flat else (float(v) - lo) / (hi - lo)
#                    p.setBrush(QColor(heat_color(t)))
#                    p.setPen(QPen(edge, 1.2) if ring
#                             else QPen(QColor(theme.LINE), 0.8))
#                    p.drawEllipse(QPointF(X(cx), Y(cy)), rad, rad)
#
#        # colour bar
#        bx = right + 16
#        bw, bh = 12, H
#        for i in range(int(bh)):
#            t = 1.0 - i / max(1.0, bh - 1)
#            p.setPen(QColor(heat_color(t)))
#            p.drawLine(int(bx), int(top + i), int(bx + bw), int(top + i))
#        p.setPen(QPen(QColor(theme.LINE2), 1))
#        p.setBrush(Qt.NoBrush)
#        p.drawRect(int(bx), int(top), bw, int(bh))
#        p.setPen(self._axis_ink())
#        p.setFont(self._font())
#        p.drawText(QRectF(bx + bw + 6, top, cbar_lab + 2, foot_h),
#                   Qt.AlignLeft | Qt.AlignVCenter, cbar_txt[0])
#        p.drawText(QRectF(bx + bw + 6, top + bh - foot_h, cbar_lab + 2, foot_h),
#                   Qt.AlignLeft | Qt.AlignVCenter, cbar_txt[1])
#        if hmin is not None and hmax is not None:
#            p.drawText(QRectF(bx - 2, top - foot_h - 3, cbar_w, foot_h),
#                       Qt.AlignLeft | Qt.AlignVCenter, "locked")
#
#        u = uniformity(allv)
#        txt = (f"n={u['n']} · mean {_fmt_span(u['mean'], u['range'] or 1.0)}"
#               f" · range {_fmt(u['range'])} ({_pct(u['range_pct'])})"
#               f" · CV {_pct(u['cv_pct'])}")
#        if cells and cw > 0 and ch > 0:
#            txt += f" · cell {cw:.0f}×{ch:.0f} px"
#        if cells and equal:
#            txt += " · equal cells"
#        p.setPen(self._axis_ink())
#        p.setFont(self._font())
#        p.drawText(QRectF(left, bottom + 9 + tick_h + name_h,
#                          W + cbar_w, foot_h),
#                   Qt.AlignLeft | Qt.AlignVCenter, txt)
#
#    def _paint_map_grid(self, p: QPainter, series, xc, yc, left, top, W, H,
#                        lo, hi, flat, vspan, show_val, ring) -> None:
#        """Every cell the same size, one slot per row and column.
#
#        Cell edges taken literally sit midway between neighbours, so an uneven
#        pitch — or one missing ROI — gives neighbouring cells visibly
#        different areas, and area is not something this chart is measuring.
#        On the lattice every ROI gets an identical tile, which is what a die
#        map looks like and what makes two cells comparable at a glance; the
#        axis still labels each slot with the position it stands for.
#        """
#        cw, ch = W / float(xc.size), H / float(yc.size)
#        p.setFont(self._font(weight=700))
#        fm = p.fontMetrics()
#        for s in series:
#            edge = QColor(s["color"])
#            for px_, py_, v in zip(s["pos_x"], s["pos_y"], s["values"]):
#                i = int(np.abs(xc - px_).argmin())
#                j = int(np.abs(yc - py_).argmin())
#                t = 0.5 if flat else (float(v) - lo) / (hi - lo)
#                col = heat_color(t)
#                r = QRectF(left + cw * i, top + ch * j, cw, ch)
#                p.setBrush(QColor(col))
#                p.setPen(QPen(edge, 1.2) if ring
#                         else QPen(QColor(0, 0, 0, 45), 0.8))
#                p.drawRect(r)
#                if not show_val:
#                    continue
#                txt = _fmt_span(float(v), vspan)
#                if (fm.horizontalAdvance(txt) + 6 <= r.width()
#                        and fm.height() <= r.height()):
#                    p.setPen(QColor("#FFFFFF") if _is_dark(col)
#                             else QColor(theme.INK))
#                    p.drawText(r, Qt.AlignCenter, txt)
#        p.setPen(QPen(QColor(theme.LINE2), 1))       # cells cover the frame
#        p.setBrush(Qt.NoBrush)
#        p.drawRect(QRectF(left, top, W, H))
#
#    # -- overlaid histogram ------------------------------------------- #
#    def _paint_hist(self, p: QPainter) -> None:
#        """Overlaid histogram, drawn as a figure rather than a sketch.
#
#        This is the chart that ends up in a report, so it is built like a
#        published one: a framed plot box, both axes labelled and ticked, a
#        legend carrying each group's n, and counts or per-group percent (which
#        is what makes groups of different size comparable at all).
#        """
#        pct = bool(self._opts.get("hist_pct", False))
#        lo, hi = self._range()
#        allv = np.concatenate([s["values"] for s in self._series])
#        nbins = int(self._opts.get("bins", 0) or 0)
#        if nbins <= 0:                          # auto: √n, bounded
#            nbins = int(np.clip(int(np.sqrt(allv.size)) + 1, 6, 22))
#        nbins = int(np.clip(nbins, 2, 80))
#        edges = np.linspace(lo, hi, nbins + 1)
#        counts = [np.histogram(s["values"], bins=edges)[0] for s in self._series]
#        if pct:
#            bars = [c / max(1.0, float(c.sum())) * 100.0 for c in counts]
#        else:
#            bars = [c.astype(np.float64) for c in counts]
#        peak = max([float(b.max()) for b in bars] + [0.0])
#        ny = self._nticks("yticks", 5)
#        step = _nice_step(peak if peak > 0 else 1.0, ny - 1)
#        if not pct:
#            step = max(1.0, round(step))        # counts are whole numbers
#        ymax = max(step, float(np.ceil(peak / step) * step))
#        # ticks land on the step, not on ymax/4 — 0 · 10 · 20 · 30 rather than
#        # 0 · 7.5 · 15 · 22.5 rounded to "8" and "22" in the label
#        yticks = [step * k for k in range(int(round(ymax / step)) + 1)]
#
#        p.setFont(self._font())
#        fm = p.fontMetrics()
#        ylabs = [(f"{v:.0f}%" if pct else f"{v:.0f}") for v in yticks]
#        left = self._left_gutter(p, ylabs)
#        top = 38
#        bottom = self.height() - self._bottom_gutter(p)
#        right = self.width() - 14
#        H = max(10, bottom - top)
#        W = max(10, right - left)
#
#        def X(v):
#            return left + (v - lo) / (hi - lo) * W
#
#        def Y(c):
#            return bottom - c / ymax * H
#
#        # grid + value axis
#        for v, lab in zip(yticks, ylabs):
#            gy = Y(v)
#            p.setPen(QPen(QColor(theme.LINE2), 1))
#            p.drawLine(left, int(gy), right, int(gy))
#            p.setPen(self._axis_ink())
#            p.drawText(QRectF(0, gy - 9, left - 8, 18),
#                       Qt.AlignRight | Qt.AlignVCenter, lab)
#        # bars, back to front so a thin group is never buried
#        order = sorted(range(len(self._series)),
#                       key=lambda i: -float(bars[i].sum()))
#        for i in order:
#            s, b = self._series[i], bars[i]
#            col = QColor(s["color"])
#            fill = QColor(col)
#            fill.setAlpha(70 if len(self._series) > 1 else 120)
#            p.setBrush(fill)
#            p.setPen(QPen(self._mark_color("line_color", col),
#                          self._line_w(1.4)))
#            for k in range(nbins):
#                if b[k] <= 0:
#                    continue
#                x0, x1 = X(edges[k]), X(edges[k + 1])
#                y = Y(float(b[k]))
#                p.drawRect(QRectF(x0, y, max(1.0, x1 - x0), bottom - y))
#        span = hi - lo
#        nx = self._nticks("xticks", 5)
#        xs = [left + W * t / (nx - 1.0) for t in range(nx)]
#        self._frame(p, left, top, right, bottom, xticks=xs,
#                    yticks=[Y(v) for v in yticks])
#        p.setFont(self._font())
#        p.setPen(self._axis_ink())
#        tick_h = p.fontMetrics().height()
#        for t, gx in enumerate(xs):
#            p.drawText(self._tick_box(gx, bottom + 5, tick_h),
#                       Qt.AlignHCenter, _fmt_span(lo + span * t / (nx - 1.0),
#                                                  span))
#        p.setPen(self._label_ink())
#        p.setFont(self._label_font())
#        p.drawText(QRectF(left, bottom + 7 + tick_h, W,
#                          p.fontMetrics().height()),
#                   Qt.AlignHCenter,
#                   str(self._st("xlabel", self._xlabel or "value")))
#        self._ytitle(p, self._st("ylabel", "share of group (%)" if pct
#                                 else "count (ROIs)"))
#        if self._legend_on():
#            self._legend(p, left, top, right,
#                         [(s["label"], s["color"], f"n={s['values'].size}")
#                          for s in self._series])
#
#    def _legend_on(self) -> bool:
#        """Legends are opt-in: on a figure with two series it is furniture,
#        and it sits on top of the data."""
#        return bool(self._opts.get("legend", False))
#
#    def _legend(self, p: QPainter, left, top, right, rows, keys=()) -> None:
#        """Keyed legend, boxed at the top right of the plot area.
#
#        ``rows`` are ``(label, colour, extra)`` swatch entries; ``keys`` are
#        ``(text, colour, pen style)`` line samples, drawn above them.
#        """
#        if not rows and not keys:
#            return
#        p.setFont(self._font(weight=700))
#        fm = p.fontMetrics()
#        texts = [f"{lab}  {extra}" if extra else lab for lab, _c, extra in rows]
#        widest = max([fm.horizontalAdvance(t) for t in texts] +
#                     [fm.horizontalAdvance(t) + 16 for t, _c, _s in keys])
#        line_h = fm.height() + 3
#        wid = widest + 26
#        hgt = 6 + line_h * (len(rows) + len(keys))
#        x = max(left + 4, right - wid - 4)
#        box = QRectF(x, top + 4, wid, hgt)
#        bg = QColor(theme.CARD)
#        bg.setAlpha(225)
#        p.setPen(QPen(QColor(theme.LINE), 1))
#        p.setBrush(bg)
#        p.drawRect(box)
#        y = box.top() + 3
#        for text, color, style in keys:
#            pen = QPen(QColor(color), 1.8)
#            pen.setStyle(style)
#            p.setPen(pen)
#            p.drawLine(QPointF(box.left() + 6, y + line_h / 2),
#                       QPointF(box.left() + 24, y + line_h / 2))
#            p.setPen(self._axis_ink())
#            p.drawText(QRectF(box.left() + 30, y, wid - 34, line_h),
#                       Qt.AlignLeft | Qt.AlignVCenter, text)
#            y += line_h
#        for (lab, color, _extra), txt in zip(rows, texts):
#            p.setPen(Qt.NoPen)
#            p.setBrush(QColor(color))
#            p.drawRect(QRectF(box.left() + 6, y + line_h / 2 - 4, 9, 8))
#            p.setPen(self._axis_ink())
#            p.drawText(QRectF(box.left() + 20, y, wid - 24, line_h),
#                       Qt.AlignLeft | Qt.AlignVCenter, txt)
#            y += line_h
#
#
#def _nice_step(span: float, target: int = 4) -> float:
#    """A round tick step (1 / 2 / 2.5 / 5 × 10ⁿ) near ``span / target``."""
#    if not np.isfinite(span) or span <= 0:
#        return 1.0
#    raw = span / max(1, target)
#    mag = 10.0 ** np.floor(np.log10(raw))
#    for m in (1.0, 2.0, 2.5, 5.0):
#        if raw <= m * mag:
#            return float(m * mag)
#    return float(10.0 * mag)
#
#
#def _fmt(v: float) -> str:
#    a = abs(v)
#    if a >= 1000 or (0 < a < 0.01):
#        return f"{v:.2e}"
#    return f"{v:.3g}"
#
#
#def _fmt_span(v: float, span: float) -> str:
#    """Label with enough decimals to tell neighbouring ticks apart.
#
#    A near-flat profile spans a fraction of a grey level, where ``_fmt``'s
#    3 significant digits would print every tick the same.
#    """
#    step = float(span) / 4.0
#    if not np.isfinite(step) or step <= 0:
#        return _fmt(v)
#    if abs(v) >= 1e5 or (0 < abs(v) < 1e-3):
#        return f"{v:.2e}"
#    dec = int(np.clip(np.ceil(-np.log10(step)) + 1, 0, 6))
#    return f"{v:.{dec}f}"
#
#
#def _pct(v: float) -> str:
#    return f"{v:.2f}%" if abs(v) < 1.0 else f"{v:.1f}%"
#
#
#def _is_dark(hexcol) -> bool:
#    c = QColor(hexcol)
#    return (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) < 140
#
#
#class _Bar(QWidget):
#    """A slim horizontal bar showing a fraction in [0, 1] (attribute ranking)."""
#
#    def __init__(self, frac):
#        super().__init__()
#        self._f = max(0.0, min(1.0, float(frac)))
#        self.setMinimumHeight(14)
#        self.setMinimumWidth(70)
#
#    def paintEvent(self, _e) -> None:
#        p = QPainter(self)
#        p.setRenderHint(QPainter.Antialiasing, True)
#        r = QRectF(0, self.height() / 2 - 4, self.width() - 1, 8)
#        p.setPen(Qt.NoPen)
#        p.setBrush(QColor(theme.LINE2))
#        p.drawRoundedRect(r, 4, 4)
#        if self._f > 0:
#            fr = QRectF(r.left(), r.top(), r.width() * self._f, r.height())
#            p.setBrush(QColor(theme.AMBER))
#            p.drawRoundedRect(fr, 4, 4)
#        p.end()
#
#
## --------------------------------------------------------------------------- #
## Metric chips
## --------------------------------------------------------------------------- #
#class _Chip(QPushButton):
#    def __init__(self, mid: str, on: bool):
#        super().__init__(metric_label(mid))
#        self.mid = mid
#        self.setCheckable(True)
#        self.setChecked(on)
#        self.setMinimumHeight(32)
#        self.setStyleSheet("padding: 4px 10px;")   # avoid vertical text clipping
#        self.setToolTip(f"{metric_label(mid)}\n{metric_formula(mid)}")
#
#
#class MetricPicker(QWidget):
#    """Which metrics the analysis reports. The overlay lives on StageBar."""
#
#    changed = Signal(list)
#    ids_changed = Signal(list)          # every metric id on offer (incl. Q*n)
#
#    def __init__(self, parent=None):
#        super().__init__(parent)
#        self._selected: List[str] = ["glv_mean", "glv_median"]
#        self._custom: List[str] = []
#        root = QVBoxLayout(self)
#        root.setContentsMargins(0, 0, 0, 0)
#        root.setSpacing(8)
#        self._chip_host = QWidget()
#        self._chip_lay = QGridLayout(self._chip_host)
#        self._chip_lay.setContentsMargins(0, 0, 0, 0)
#        self._chip_lay.setSpacing(6)
#        root.addWidget(self._chip_host)
#        qn = QHBoxLayout()
#        qn.setSpacing(6)
#        lab = QLabel("custom Q")
#        lab.setObjectName("Hint")
#        self.qn_spin = QSpinBox()
#        self.qn_spin.setRange(1, 99)
#        self.qn_spin.setValue(90)
#        self.qn_spin.setFixedWidth(60)
#        self.qn_spin.setMinimumHeight(28)
#        add = QPushButton("Add")
#        add.setMinimumHeight(28)
#        add.clicked.connect(self._add_custom)
#        qn.addWidget(lab)
#        qn.addWidget(self.qn_spin)
#        qn.addWidget(add)
#        qn.addStretch(1)
#        root.addLayout(qn)
#        self._rebuild()
#
#    def selected(self) -> List[str]:
#        return list(self._selected)
#
#    def ids(self) -> List[str]:
#        return list(GLV_STATS.keys()) + self._custom
#
#    def set_state(self, metrics, extra_ids=()) -> None:
#        """Restore the picker (used when opening a project).
#
#        ``extra_ids`` re-registers custom quantiles that the project used only
#        for the overlay, so they stay on offer after reopening.
#        """
#        self._selected = list(metrics or [])
#        for m in list(self._selected) + list(extra_ids):
#            if (m and m.startswith("glv_q") and m not in GLV_STATS
#                    and m not in self._custom):
#                self._custom.append(m)
#        self._rebuild()
#
#    def _add_custom(self) -> None:
#        mid = f"glv_q{int(self.qn_spin.value())}"
#        if mid not in self._custom and mid not in GLV_STATS:
#            self._custom.append(mid)
#        if mid not in self._selected:
#            self._selected.append(mid)
#        self._rebuild()
#        self.changed.emit(list(self._selected))
#
#    def _ids(self) -> List[str]:
#        return self.ids()
#
#    def _rebuild(self) -> None:
#        _clear(self._chip_lay)
#        for i, mid in enumerate(self._ids()):
#            chip = _Chip(mid, mid in self._selected)
#            chip.clicked.connect(lambda _=False, m=mid: self._toggle(m))
#            self._chip_lay.addWidget(chip, i // 3, i % 3)
#        self.ids_changed.emit(self.ids())
#
#    def _toggle(self, mid: str) -> None:
#        if mid in self._selected:
#            self._selected.remove(mid)
#        else:
#            self._selected.append(mid)
#        self.changed.emit(list(self._selected))
#
#
## --------------------------------------------------------------------------- #
## Stage bar — the ROI overlay controls, sitting over the image they act on
## --------------------------------------------------------------------------- #
#class StageBar(QWidget):
#    """One strip above the image: which metric to overlay, and how to read it.
#
#    These controls belong next to the image, not at the bottom of a long rail
#    — every one of them changes what the picture looks like, and each is a
#    separate reading of the same metric, so they switch one at a time.
#    """
#
#    show_changed = Signal(str)          # metric id drawn on the ROIs ("" = none)
#    values_changed = Signal(bool)
#    heatmap_changed = Signal(bool)
#    cells_changed = Signal(bool)        # spread the heat over the ROI's cell
#    outliers_changed = Signal(bool)
#    heat_alpha_changed = Signal(int)    # percent
#    heat_range_changed = Signal(object)  # (vmin, vmax) or None for auto
#    export_image_requested = Signal()
#
#    def __init__(self, parent=None):
#        super().__init__(parent)
#        self.setObjectName("StageBar")
#        self._show = ""
#        self._heat_range = None         # locked colour range, or None for auto
#        lay = QHBoxLayout(self)
#        lay.setContentsMargins(12, 7, 12, 7)
#        lay.setSpacing(10)
#        lbl = QLabel("show on ROIs")
#        lbl.setObjectName("Hint")
#        self.show_combo = QComboBox()
#        self.show_combo.setMinimumWidth(150)
#        self.show_combo.setMinimumHeight(26)
#        self.show_combo.setToolTip("The metric every overlay below reads.")
#        self.show_combo.currentIndexChanged.connect(self._on_show)
#        lay.addWidget(lbl)
#        lay.addWidget(self.show_combo)
#        lay.addSpacing(6)
#        self.values_chk = QCheckBox("values")
#        self.values_chk.setChecked(True)
#        self.values_chk.setToolTip(
#            "Print the metric on each ROI (where the box is big enough; the "
#            "hovered ROI always shows its own). Off with heatmap on = colour "
#            "only.")
#        self.values_chk.toggled.connect(self.values_changed)
#        self.heatmap_chk = QCheckBox("heat boxes")
#        self.heatmap_chk.setToolTip(
#            "Fill each ROI box with its value's colour.")
#        self.heatmap_chk.toggled.connect(self._on_heatmap)
#        self.cells_chk = QCheckBox("heat field")
#        self.cells_chk.setToolTip(
#            "Spread each ROI's colour over the patch of image it speaks for "
#            "(midway to its neighbours), so a gradient across the field reads "
#            "as one surface. The measured box stays outlined on top. Works on "
#            "its own — boxes and field are two ways to paint the same values.")
#        self.cells_chk.toggled.connect(self._on_cells)
#        self.outliers_chk = QCheckBox("outliers")
#        self.outliers_chk.setToolTip("Mark ROIs outside Q1−1.5·IQR … Q3+1.5·IQR "
#                                     "within their group.")
#        self.outliers_chk.toggled.connect(self.outliers_changed)
#        for chk in (self.values_chk, self.heatmap_chk, self.cells_chk,
#                    self.outliers_chk):
#            lay.addWidget(chk)
#        op = QLabel("opacity")
#        op.setObjectName("Hint")
#        self.alpha_spin = QSpinBox()
#        self.alpha_spin.setRange(10, 100)
#        self.alpha_spin.setSingleStep(5)
#        self.alpha_spin.setValue(70)
#        self.alpha_spin.setSuffix(" %")
#        self.alpha_spin.setFixedWidth(72)
#        self.alpha_spin.setMinimumHeight(26)
#        self.alpha_spin.setToolTip(
#            "Opacity of the heat fill — lower it to read the image underneath.")
#        self.alpha_spin.valueChanged.connect(self.heat_alpha_changed)
#        lay.addWidget(op)
#        lay.addWidget(self.alpha_spin)
#        lay.addStretch(1)
#        self.scale_btn = QPushButton("scale…")
#        self.scale_btn.setFixedHeight(26)
#        self.scale_btn.setToolTip(
#            "Lock the heat colours to a fixed range, so the same colour means "
#            "the same grey level on every image you open.")
#        self.scale_btn.clicked.connect(self.edit_heat_range)
#        lay.addWidget(self.scale_btn)
#        self.image_btn = QPushButton("Export image")
#        self.image_btn.setFixedHeight(26)
#        self.image_btn.setToolTip(
#            "Save the annotated field as a picture — the image at its own "
#            "resolution with the overlays on top, not a screenshot of the "
#            "stage.")
#        self.image_btn.clicked.connect(self.export_image_requested)
#        lay.addWidget(self.image_btn)
#        self.set_metrics(list(GLV_STATS.keys()))
#        self._gate()
#
#    # -- state -------------------------------------------------------- #
#    def set_metrics(self, ids) -> None:
#        """Rebuild the metric list, keeping the current pick if it survives."""
#        self.show_combo.blockSignals(True)
#        self.show_combo.clear()
#        self.show_combo.addItem("— none —", "")
#        for mid in ids:
#            self.show_combo.addItem(metric_label(mid), mid)
#        idx = self.show_combo.findData(self._show)
#        self.show_combo.setCurrentIndex(idx if idx >= 0 else 0)
#        self._show = self.show_combo.currentData() or ""
#        self.show_combo.blockSignals(False)
#
#    def set_state(self, show, values, heatmap, cells, outliers, alpha) -> None:
#        self._show = show or ""
#        self.show_combo.blockSignals(True)
#        idx = self.show_combo.findData(self._show)
#        self.show_combo.setCurrentIndex(idx if idx >= 0 else 0)
#        self.show_combo.blockSignals(False)
#        for chk, val in ((self.values_chk, values), (self.heatmap_chk, heatmap),
#                         (self.cells_chk, cells), (self.outliers_chk, outliers)):
#            chk.blockSignals(True)
#            chk.setChecked(bool(val))
#            chk.blockSignals(False)
#        self.alpha_spin.blockSignals(True)
#        self.alpha_spin.setValue(int(alpha))
#        self.alpha_spin.blockSignals(False)
#        self._gate()
#
#    def _gate(self) -> None:
#        # Either mode paints the values; the opacity and the colour scale
#        # belong to whichever is on. Neither gates the other — ticking the
#        # field alone used to leave the image untouched, which read as a
#        # broken checkbox.
#        on = self.heatmap_chk.isChecked() or self.cells_chk.isChecked()
#        for w in (self.alpha_spin, self.scale_btn):
#            w.setEnabled(on)
#
#    def set_heat_range(self, rng) -> None:
#        """Restore the locked colour range (or None for auto)."""
#        self._heat_range = tuple(rng) if rng else None
#        self._label_scale()
#
#    def heat_range(self):
#        return self._heat_range
#
#    def _label_scale(self) -> None:
#        r = self._heat_range
#        self.scale_btn.setText("scale…" if not r
#                               else f"{r[0]:.4g} – {r[1]:.4g}")
#
#    def edit_heat_range(self) -> None:
#        style = ({} if not self._heat_range
#                 else {"heat_vmin": self._heat_range[0],
#                       "heat_vmax": self._heat_range[1]})
#        dlg = QDialog(self)
#        dlg.setWindowTitle("Heat colour scale")
#        lay = QVBoxLayout(dlg)
#        lay.setContentsMargins(16, 14, 16, 14)
#        lay.setSpacing(10)
#        row, auto, lo, hi = _num_row("grey level", style,
#                                     "heat_vmin", "heat_vmax")
#        lay.addLayout(row)
#        hint = QLabel("With auto, the colours span this image's own min and "
#                      "max — the same colour means a different value on the "
#                      "next image. Lock the range to compare across images.")
#        hint.setObjectName("Hint")
#        hint.setWordWrap(True)
#        lay.addWidget(hint)
#        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
#        buttons.accepted.connect(dlg.accept)
#        buttons.rejected.connect(dlg.reject)
#        lay.addWidget(buttons)
#        if dlg.exec() != QDialog.Accepted:
#            return
#        rng = (None if auto.isChecked() or hi.value() <= lo.value()
#               else (lo.value(), hi.value()))
#        self.set_heat_range(rng)
#        self.heat_range_changed.emit(rng)
#
#    def _on_heatmap(self, on: bool) -> None:
#        self._gate()
#        self.heatmap_changed.emit(bool(on))
#
#    def _on_cells(self, on: bool) -> None:
#        self._gate()
#        self.cells_changed.emit(bool(on))
#
#    def _on_show(self, _i: int) -> None:
#        self._show = self.show_combo.currentData() or ""
#        self.show_changed.emit(self._show)
#
#
## --------------------------------------------------------------------------- #
## Chart settings — what a figure is called and how its axes are scaled
## --------------------------------------------------------------------------- #
#def _num_row(label: str, style: dict, kmin: str, kmax: str, unit: str = ""):
#    """An "auto / from … to …" range row. Returns (layout, auto, lo, hi)."""
#    row = QHBoxLayout()
#    row.setSpacing(6)
#    lab = QLabel(label)
#    lab.setMinimumWidth(210)
#    # bold through the font, not a stylesheet: a stylesheet weight is applied
#    # after sizeHint() is asked for, so the caller sizing the label column
#    # would measure the regular width and clip the bold text
#    font = lab.font()
#    font.setBold(True)
#    lab.setFont(font)
#    auto = QCheckBox("auto")
#    lo, hi = QDoubleSpinBox(), QDoubleSpinBox()
#    for sp in (lo, hi):
#        sp.setRange(-1e9, 1e9)
#        sp.setDecimals(3)
#        sp.setMinimumWidth(96)
#        if unit:
#            sp.setSuffix(unit)
#    have = style.get(kmin) is not None and style.get(kmax) is not None
#    auto.setChecked(not have)
#    if have:
#        lo.setValue(float(style[kmin]))
#        hi.setValue(float(style[kmax]))
#    for sp in (lo, hi):
#        sp.setEnabled(have)
#    auto.toggled.connect(lambda on: [sp.setEnabled(not on) for sp in (lo, hi)])
#    row.addWidget(lab)
#    row.addWidget(auto)
#    row.addWidget(QLabel("from"))
#    row.addWidget(lo)
#    row.addWidget(QLabel("to"))
#    row.addWidget(hi)
#    row.addStretch(1)
#    return row, auto, lo, hi
#
#
#class RoiSizeDialog(QDialog):
#    """How big the boxes are, on the way in or out.
#
#    The interchange list says where each ROI goes; how big it is can come
#    from three places — the file itself, the rail's size fields, or a size
#    typed here for the whole set. Rather than guess, ask, and let the export
#    leave ``w`` / ``h`` out entirely for a tool that does not expect them.
#    """
#
#    def __init__(self, parent, mode: str, w: int, h: int, count: int = 0):
#        super().__init__(parent)
#        importing = mode == "import"
#        self.setWindowTitle("Import ROIs" if importing else "Export ROIs")
#        self.setMinimumWidth(380)
#        root = QVBoxLayout(self)
#        root.setContentsMargins(16, 14, 16, 14)
#        root.setSpacing(10)
#        if count:
#            head = QLabel(f"{count} ROIs")
#            head.setObjectName("SectionTitle")
#            head.setFont(theme.display_font(12, weight=700))
#            root.addWidget(head)
#
#        self.include_chk = QCheckBox("write w / h for every box")
#        self.include_chk.setChecked(True)
#        self.include_chk.setToolTip(
#            "Off: only colour, x, y and target are written — the shape a tool "
#            "that has its own box size expects.")
#        if not importing:
#            root.addWidget(self.include_chk)
#
#        self.own_radio = QRadioButton(
#            "keep each box's own size" if not importing
#            else "take the size from the file (or the size fields, if it has "
#                 "none)")
#        self.own_radio.setChecked(True)
#        self.custom_radio = QRadioButton("use this size for every box")
#        root.addWidget(self.own_radio)
#        row = QHBoxLayout()
#        row.setSpacing(6)
#        row.addWidget(self.custom_radio)
#        self.w_spin, self.h_spin = QSpinBox(), QSpinBox()
#        for sp, val in ((self.w_spin, w), (self.h_spin, h)):
#            sp.setRange(1, 4000)
#            sp.setValue(int(val))
#            sp.setMinimumHeight(28)
#            sp.setFixedWidth(80)
#            sp.setEnabled(False)
#        row.addWidget(self.w_spin)
#        row.addWidget(QLabel("×"))
#        row.addWidget(self.h_spin)
#        row.addStretch(1)
#        root.addLayout(row)
#        self.custom_radio.toggled.connect(
#            lambda on: [sp.setEnabled(on) for sp in (self.w_spin, self.h_spin)])
#        if not importing:
#            self.include_chk.toggled.connect(self._gate)
#            self._gate(True)
#
#        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
#        buttons.accepted.connect(self.accept)
#        buttons.rejected.connect(self.reject)
#        root.addWidget(buttons)
#
#    def _gate(self, on: bool) -> None:
#        for w in (self.own_radio, self.custom_radio):
#            w.setEnabled(on)
#        for sp in (self.w_spin, self.h_spin):
#            sp.setEnabled(on and self.custom_radio.isChecked())
#
#    def options(self) -> dict:
#        """``{"size": (w, h) or None, "include_size": bool}``."""
#        size = ((int(self.w_spin.value()), int(self.h_spin.value()))
#                if self.custom_radio.isChecked() else None)
#        return {"size": size, "include_size": self.include_chk.isChecked()}
#
#
#class ChartSettingsDialog(QDialog):
#    """Rename the figures and set their axes by hand.
#
#    Auto scaling is right while you are looking; it is wrong the moment you
#    put two runs side by side, because each picks its own range. Everything
#    here is an override — leave a field blank or on *auto* and the chart goes
#    back to deciding for itself.
#    """
#
#    def __init__(self, parent, chart_titles: List[str], style: dict):
#        super().__init__(parent)
#        self.setWindowTitle("Chart settings")
#        self.setMinimumWidth(460)
#        style = dict(style or {})
#        titles = dict(style.get("titles") or {})
#        root = QVBoxLayout(self)
#        root.setContentsMargins(16, 14, 16, 14)
#        root.setSpacing(10)
#
#        head = QLabel("Titles")
#        head.setObjectName("SectionTitle")
#        head.setFont(theme.display_font(12, weight=700))
#        root.addWidget(head)
#        self._title_edits = {}
#        for name in chart_titles:
#            row = QHBoxLayout()
#            row.setSpacing(6)
#            lab = QLabel(name)
#            lab.setObjectName("Hint")
#            lab.setMinimumWidth(96)
#            ed = QLineEdit(titles.get(name, ""))
#            ed.setPlaceholderText(name)
#            ed.setMinimumHeight(28)
#            self._title_edits[name] = ed
#            row.addWidget(lab)
#            row.addWidget(ed, 1)
#            root.addLayout(row)
#
#        head = QLabel("Axes")
#        head.setObjectName("SectionTitle")
#        head.setFont(theme.display_font(12, weight=700))
#        root.addWidget(head)
#        self.x_edit = QLineEdit(style.get("xlabel") or "")
#        self.x_edit.setPlaceholderText("(default for this chart type)")
#        self.y_edit = QLineEdit(style.get("ylabel") or "")
#        self.y_edit.setPlaceholderText("(default for this chart type)")
#        for lab, ed in (("X axis name", self.x_edit),
#                        ("Y axis name", self.y_edit)):
#            row = QHBoxLayout()
#            row.setSpacing(6)
#            l = QLabel(lab)
#            l.setObjectName("Hint")
#            l.setMinimumWidth(96)
#            ed.setMinimumHeight(28)
#            row.addWidget(l)
#            row.addWidget(ed, 1)
#            root.addLayout(row)
#        trow = QHBoxLayout()
#        trow.setSpacing(6)
#        tl = QLabel("ticks")
#        tl.setObjectName("Hint")
#        tl.setMinimumWidth(96)
#        self.xt_spin, self.yt_spin = QSpinBox(), QSpinBox()
#        for sp, key, default in ((self.xt_spin, "xticks", 5),
#                                 (self.yt_spin, "yticks", 5)):
#            sp.setRange(2, 12)
#            sp.setValue(int(style.get(key) or default))
#            sp.setMinimumHeight(28)
#            sp.setFixedWidth(70)
#        trow.addWidget(tl)
#        trow.addWidget(QLabel("X"))
#        trow.addWidget(self.xt_spin)
#        trow.addWidget(QLabel("Y"))
#        trow.addWidget(self.yt_spin)
#        trow.addStretch(1)
#        root.addLayout(trow)
#        tip = QLabel("A count axis rounds to whole steps, so it lands near "
#                     "that number rather than exactly on it.")
#        tip.setObjectName("Hint")
#        tip.setWordWrap(True)
#        root.addWidget(tip)
#
#        head = QLabel("Text and marks")
#        head.setObjectName("SectionTitle")
#        head.setFont(theme.display_font(12, weight=700))
#        root.addWidget(head)
#        hint = QLabel("One row per thing on the chart. A colour on auto "
#                      "follows the group; the axis rows are dark by default, "
#                      "because light grey vanishes on a projector.")
#        hint.setObjectName("Hint")
#        hint.setWordWrap(True)
#        root.addWidget(hint)
#
#        def spin(lo, hi, step, suffix, value):
#            sp = QDoubleSpinBox()
#            sp.setRange(lo, hi)
#            sp.setDecimals(1)
#            sp.setSingleStep(step)
#            sp.setSuffix(suffix)
#            sp.setValue(float(value))
#            sp.setMinimumHeight(28)
#            sp.setFixedWidth(88)
#            return sp
#
#        self.font_spin = spin(5, 24, 0.5, " pt", style.get("font_pt") or 8)
#        self.label_spin = spin(5, 24, 0.5, " pt",
#                               style.get("label_pt") or style.get("font_pt") or 8)
#        self.point_spin = spin(0.5, 20, 0.5, " px",
#                               style.get("point_size") or 3.2)
#        self.line_spin = spin(0.3, 12, 0.2, " px",
#                              style.get("line_width") or 2.2)
#        self.tick_bold_chk = QCheckBox("bold")
#        self.tick_bold_chk.setChecked(bool(style.get("tick_bold", False)))
#        self.label_bold_chk = QCheckBox("bold")
#        self.label_bold_chk.setChecked(bool(style.get("label_bold", True)))
#        self._colors = {}
#
#        # the two label columns are collected and squared off afterwards, so
#        # the spin boxes and the swatches line up down the block instead of
#        # stepping in and out with the length of each word
#        mark_heads: list = []
#        mark_units: list = []
#
#        def mark_row(title, tip, size_label, size_widget, bold_widget,
#                     color_key, color_default):
#            row = QHBoxLayout()
#            row.setSpacing(6)
#            lab = QLabel(title)
#            lab.setToolTip(tip)
#            font = lab.font()
#            font.setBold(True)
#            lab.setFont(font)
#            unit = QLabel(size_label)
#            unit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
#            mark_heads.append(lab)
#            mark_units.append(unit)
#            row.addWidget(lab)
#            row.addWidget(unit)
#            row.addWidget(size_widget)
#            if bold_widget is not None:
#                row.addWidget(bold_widget)
#            else:                       # keep the colour column in one line
#                row.addSpacing(self.tick_bold_chk.sizeHint().width())
#            row.addSpacing(8)
#            row.addWidget(QLabel("colour"))
#            row.addLayout(self._color_pick(color_key,
#                                           style.get(color_key) or "",
#                                           color_default))
#            row.addStretch(1)
#            root.addLayout(row)
#
#        mark_row("Tick values", "The numbers along both axes.",
#                 "size", self.font_spin, self.tick_bold_chk,
#                 "axis_ink", theme.INK)
#        mark_row("Axis names", "The X and Y names, and the plot frame.",
#                 "size", self.label_spin, self.label_bold_chk,
#                 "label_ink", theme.INK)
#        mark_row("Data points", "Every ROI's own marker.",
#                 "radius", self.point_spin, None,
#                 "point_color", theme.INK2)
#        mark_row("Lines", "The profile line, the median bar, the bar outlines.",
#                 "width", self.line_spin, None,
#                 "line_color", theme.INK2)
#        for column in (mark_heads, mark_units):
#            wide = max(w.sizeHint().width() for w in column) + 6
#            for w in column:
#                w.setFixedWidth(wide)
#
#        head = QLabel("Scales")
#        head.setObjectName("SectionTitle")
#        head.setFont(theme.display_font(12, weight=700))
#        root.addWidget(head)
#        vrow, self.v_auto, self.v_lo, self.v_hi = _num_row(
#            "value  (box Y · hist X · profile Y)", style, "vmin", "vmax")
#        xrow, self.x_auto, self.x_lo, self.x_hi = _num_row(
#            "position X  (profile · map)", style, "xmin", "xmax", " px")
#        yrow, self.y_auto, self.y_lo, self.y_hi = _num_row(
#            "position Y  (map)", style, "ymin", "ymax", " px")
#        hrow, self.h_auto, self.h_lo, self.h_hi = _num_row(
#            "heat colours  (map)", style, "heat_vmin", "heat_vmax")
#        # one label column, as wide as the longest of the four — otherwise
#        # the layout steals the width back from the label and the row reads
#        # "value  (box Y · hist X · profil" with the checkbox on top of it
#        scale_labels = [r.itemAt(0).widget() for r in (vrow, xrow, yrow, hrow)]
#        col = max(w.sizeHint().width() for w in scale_labels) + 10
#        for w in scale_labels:
#            w.setFixedWidth(col)
#        self.setMinimumWidth(col + 330)
#        root.addLayout(vrow)
#        root.addLayout(xrow)
#        root.addLayout(yrow)
#        root.addLayout(hrow)
#        hint = QLabel("Untick auto to type a range. A locked scale is what "
#                      "makes two images, two lots or two days comparable — "
#                      "on auto each chart picks its own.")
#        hint.setObjectName("Hint")
#        hint.setWordWrap(True)
#        root.addWidget(hint)
#
#        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
#        buttons.accepted.connect(self.accept)
#        buttons.rejected.connect(self.reject)
#        reset = buttons.addButton("Reset", QDialogButtonBox.ResetRole)
#        reset.clicked.connect(self._reset)
#        root.addWidget(buttons)
#
#    def _color_pick(self, key: str, current: str, default: str):
#        """A swatch plus an *auto* box — auto hands the choice back."""
#        row = QHBoxLayout()
#        row.setSpacing(4)
#        state = {"color": current or default}
#        self._colors[key] = state
#        btn = QPushButton()
#        btn.setFixedSize(22, 22)
#
#        def paint():
#            btn.setStyleSheet(f"background:{state['color']}; "
#                              "border:1px solid rgba(0,0,0,.25); "
#                              "border-radius:4px;")
#        paint()
#
#        def choose():
#            c = QColorDialog.getColor(QColor(state["color"]), self)
#            if c.isValid():
#                state["color"] = c.name()
#                state["auto"] = False
#                auto.setChecked(False)
#                paint()
#        btn.clicked.connect(choose)
#        auto = QCheckBox("auto")
#        auto.setChecked(not current)
#        state["box"] = auto
#        row.addWidget(btn)
#        row.addWidget(auto)
#        return row
#
#    def _reset(self) -> None:
#        for ed in list(self._title_edits.values()) + [self.x_edit, self.y_edit]:
#            ed.clear()
#        self.xt_spin.setValue(5)
#        self.yt_spin.setValue(5)
#        for auto in (self.v_auto, self.x_auto, self.y_auto, self.h_auto):
#            auto.setChecked(True)
#        self.font_spin.setValue(8.0)
#        self.label_spin.setValue(8.0)
#        self.tick_bold_chk.setChecked(False)
#        self.label_bold_chk.setChecked(True)
#        self.point_spin.setValue(3.2)
#        self.line_spin.setValue(2.2)
#        for state in self._colors.values():
#            state["box"].setChecked(True)
#
#    def result_style(self) -> dict:
#        """The overrides, with anything left at its default omitted."""
#        out: dict = {}
#        titles = {k: ed.text().strip() for k, ed in self._title_edits.items()
#                  if ed.text().strip()}
#        if titles:
#            out["titles"] = titles
#        for key, ed in (("xlabel", self.x_edit), ("ylabel", self.y_edit)):
#            if ed.text().strip():
#                out[key] = ed.text().strip()
#        out["xticks"] = int(self.xt_spin.value())
#        out["yticks"] = int(self.yt_spin.value())
#        out["font_pt"] = round(float(self.font_spin.value()), 1)
#        out["label_pt"] = round(float(self.label_spin.value()), 1)
#        out["tick_bold"] = bool(self.tick_bold_chk.isChecked())
#        out["label_bold"] = bool(self.label_bold_chk.isChecked())
#        out["point_size"] = round(float(self.point_spin.value()), 1)
#        out["line_width"] = round(float(self.line_spin.value()), 1)
#        for key, state in self._colors.items():
#            if not state["box"].isChecked():
#                out[key] = state["color"]
#        for auto, lo, hi, kmin, kmax in (
#                (self.v_auto, self.v_lo, self.v_hi, "vmin", "vmax"),
#                (self.x_auto, self.x_lo, self.x_hi, "xmin", "xmax"),
#                (self.y_auto, self.y_lo, self.y_hi, "ymin", "ymax"),
#                (self.h_auto, self.h_lo, self.h_hi, "heat_vmin", "heat_vmax")):
#            if not auto.isChecked() and hi.value() > lo.value():
#                out[kmin], out[kmax] = lo.value(), hi.value()
#        return out
#
#
## --------------------------------------------------------------------------- #
## Control rail
## --------------------------------------------------------------------------- #
#class RailPanel(QWidget):
#    group_add = Signal()
#    group_pick = Signal(str)
#    group_del = Signal(str)
#    group_color = Signal(str, str)
#    group_rename = Signal(str, str)
#    group_clear = Signal(str)
#    grid_mode_toggled = Signal(bool)
#    grid_commit = Signal()
#    grid_shape_changed = Signal(int, int)
#    roi_size_changed = Signal(int, int)     # ROI W × H for click / grid
#    roi_pick = Signal(int)                  # select an ROI from the list
#    roi_del = Signal(int)
#    roi_hovered = Signal(int)                # rid under the cursor (-1 = none)
#    metrics_changed = Signal(list)
#    metric_ids_changed = Signal(list)       # every metric on offer (incl. Q*n)
#    roi_order_changed = Signal(str)         # "placed" | "asc" | "desc"
#    roi_align = Signal(str)                 # align/distribute the selection
#    roi_import = Signal()                   # read a flat ROI list
#    roi_export = Signal()                   # write one
#    open_analysis = Signal()
#
#    def __init__(self, parent=None):
#        super().__init__(parent)
#        root = QVBoxLayout(self)
#        root.setContentsMargins(14, 14, 14, 14)
#        root.setSpacing(12)
#
#        # Groups
#        grp = _card("Groups", "categories")
#        glay = grp.layout()
#        self.grp_add_btn = QPushButton("+ Add group")
#        self.grp_add_btn.clicked.connect(self.group_add)
#        glay.addLayout(_button_row(self.grp_add_btn))
#        self.grp_host = QVBoxLayout()
#        self.grp_host.setSpacing(6)
#        glay.addLayout(self.grp_host)
#        hint = QLabel("Pick a group, then add ROIs to it on the image.")
#        hint.setObjectName("Hint")
#        hint.setWordWrap(True)
#        glay.addWidget(hint)
#        root.addWidget(grp)
#
#        # ROIs (of the active group)
#        roi = _card("ROIs", "of active group")
#        rlay = roi.layout()
#        # The ROI set travels on its own — a flat {color, x, y, w, h} list, so
#        # a layout worked out somewhere else can be dropped straight in. Both
#        # live in the card's own header, where they cost no height.
#        self.roi_import_btn = _icon_button(
#            "import", "Import ROIs — a JSON list of boxes, one object each "
#            "with a colour and a top-left x / y. Each colour becomes a group.")
#        self.roi_import_btn.clicked.connect(self.roi_import)
#        self.roi_export_btn = _icon_button(
#            "export", "Export ROIs — write every box as that same JSON list.")
#        self.roi_export_btn.clicked.connect(self.roi_export)
#        roi._head.addWidget(self.roi_import_btn)
#        roi._head.addWidget(self.roi_export_btn)
#        self.grid_btn = QPushButton("▦ Grid")
#        self.grid_btn.setCheckable(True)
#        self.grid_btn.setToolTip("Click the top-left then bottom-right corner "
#                                 "on the image; a row×col preview follows.")
#        self.grid_btn.toggled.connect(self.grid_mode_toggled)
#        self.add_grid_btn = QPushButton("✓ Add grid")
#        self.add_grid_btn.setToolTip("Place the previewed grid (or press Enter).")
#        self.add_grid_btn.setEnabled(False)
#        self.add_grid_btn.clicked.connect(self.grid_commit)
#        rlay.addLayout(_button_row(self.grid_btn, self.add_grid_btn))
#        # ROI size (W × H) used by click-to-place and by the grid
#        szrow = QHBoxLayout()
#        szrow.setSpacing(8)
#        szl = QLabel("size")
#        szl.setObjectName("Hint")
#        szrow.addWidget(szl)
#        self.roi_w = QSpinBox()
#        self.roi_w.setRange(4, 4000)
#        self.roi_w.setValue(28)
#        self.roi_h = QSpinBox()
#        self.roi_h.setRange(4, 4000)
#        self.roi_h.setValue(28)
#        for sp in (self.roi_w, self.roi_h):
#            sp.setMinimumHeight(28)
#            sp.valueChanged.connect(
#                lambda _=0: self.roi_size_changed.emit(*self.roi_size()))
#        szrow.addWidget(self.roi_w, 1)
#        szrow.addWidget(QLabel("×"))
#        szrow.addWidget(self.roi_h, 1)
#        rlay.addLayout(szrow)
#        grow = QHBoxLayout()
#        grow.setSpacing(8)
#        gl = QLabel("grid")
#        gl.setObjectName("Hint")
#        grow.addWidget(gl)
#        self.grid_rows = QSpinBox()
#        self.grid_rows.setRange(1, 100)
#        self.grid_rows.setValue(3)
#        self.grid_cols = QSpinBox()
#        self.grid_cols.setRange(1, 100)
#        self.grid_cols.setValue(3)
#        for sp in (self.grid_rows, self.grid_cols):
#            sp.setMinimumHeight(28)
#            sp.valueChanged.connect(
#                lambda _=0: self.grid_shape_changed.emit(*self.grid_shape()))
#        grow.addWidget(self.grid_rows, 1)
#        grow.addWidget(QLabel("×"))
#        grow.addWidget(self.grid_cols, 1)
#        rlay.addLayout(grow)
#        # Tidy: hand-placed ROIs sit a few pixels off each other, which only
#        # shows up once the field fill tiles them into a staircase. Spelt out
#        # rather than iconified — six unlabelled arrow glyphs at 30 px is a
#        # puzzle, and this is a button you press once and want to press right.
#        alab = QLabel("align")
#        alab.setObjectName("Hint")
#        alab.setToolTip("Acts on the ROIs selected with Shift+drag; with none "
#                        "selected, on the whole active group.")
#        rlay.addWidget(alab)
#        self.align_btns = {}
#        rows = (("left", "⇤ Left"), ("hcenter", "⇔ Centre"), ("right", "Right ⇥"),
#                ("top", "⤒ Top"), ("vcenter", "⇕ Middle"), ("bottom", "Bottom ⤓"),
#                ("distx", "⇹ Even across"), ("disty", "⇳ Even down"))
#        tips = {
#            "left": "Move them onto the leftmost left edge",
#            "hcenter": "Line their centres up on one vertical axis",
#            "right": "Move them onto the rightmost right edge",
#            "top": "Move them onto the topmost top edge",
#            "vcenter": "Line their centres up on one horizontal axis",
#            "bottom": "Move them onto the bottommost bottom edge",
#            "distx": "Space them evenly left to right (needs 3+)",
#            "disty": "Space them evenly top to bottom (needs 3+)"}
#        made = []
#        for mode, text in rows:
#            b = QPushButton(text)
#            b.setMinimumHeight(30)
#            b.setToolTip(f"{tips[mode]}. Shift+drag selects ROIs on the image; "
#                         "with none selected the whole active group is used.")
#            b.clicked.connect(lambda _=False, m=mode: self.roi_align.emit(m))
#            self.align_btns[mode] = b
#            made.append(b)
#        for i in range(0, len(made), 3):
#            rlay.addLayout(_button_row(*made[i:i + 3]))
#        # Order: the list is where you scan for the odd one out, so it sorts
#        # by the shown metric as well as by the order the ROIs were placed.
#        orow = QHBoxLayout()
#        orow.setSpacing(6)
#        ol = QLabel("order")
#        ol.setObjectName("Hint")
#        self.order_box = QComboBox()
#        self.order_box.setMinimumHeight(28)
#        self.order_box.addItem("as placed", "placed")
#        self.order_box.addItem("value ↑", "asc")
#        self.order_box.addItem("value ↓", "desc")
#        self.order_box.setToolTip("Sort the list by the metric shown on the "
#                                  "ROIs. Labels stay with their ROI.")
#        self.order_box.currentIndexChanged.connect(
#            lambda _=0: self.roi_order_changed.emit(
#                str(self.order_box.currentData() or "placed")))
#        orow.addWidget(ol)
#        orow.addWidget(self.order_box, 1)
#        rlay.addLayout(orow)
#        # ROI list — capped height so a long list never buries the buttons
#        self.roi_host = QVBoxLayout()
#        self.roi_host.setSpacing(4)
#        self.roi_host.setContentsMargins(0, 0, 0, 0)
#        roi_list_host = QWidget()
#        roi_list_host.setLayout(self.roi_host)
#        self.roi_scroll = QScrollArea()
#        self.roi_scroll.setWidgetResizable(True)
#        self.roi_scroll.setFrameShape(QScrollArea.NoFrame)
#        self.roi_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
#        self.roi_scroll.setWidget(roi_list_host)
#        self.roi_scroll.setFixedHeight(6)        # grows with content up to a cap
#        rlay.addWidget(self.roi_scroll)
#        self.roi_hint = QLabel(
#            "• Click → drop a size-W×H ROI · drag → custom size\n"
#            "• Grid → two corners, set row×col, Add grid\n"
#            "• Shift+drag → box-select · Del removes them\n"
#            "• Double-click an ROI → pixel inspector")
#        self.roi_hint.setObjectName("Hint")
#        self.roi_hint.setWordWrap(True)
#        rlay.addWidget(self.roi_hint)
#        self.clear_btn = QPushButton("Clear group’s ROIs")
#        self.clear_btn.clicked.connect(self._clear_active)
#        rlay.addLayout(_button_row(self.clear_btn))
#        root.addWidget(roi)
#
#        # Metrics
#        met = _card("Metrics", "grey-level statistics")
#        self.metrics = MetricPicker()
#        self.metrics.changed.connect(self.metrics_changed)
#        self.metrics.ids_changed.connect(self.metric_ids_changed)
#        met.layout().addWidget(self.metrics)
#        root.addWidget(met)
#
#        self.analysis_btn = QPushButton("Open analysis ⤢")
#        self.analysis_btn.setObjectName("Primary")
#        self.analysis_btn.clicked.connect(self.open_analysis)
#        root.addLayout(_button_row(self.analysis_btn))
#        root.addStretch(1)
#
#        self._active_gid: Optional[str] = None
#
#    # -- render --------------------------------------------------------- #
#    def set_ready(self, has_image: bool) -> None:
#        for w in (self.grp_add_btn, self.grid_btn, self.roi_w, self.roi_h,
#                  self.clear_btn, self.analysis_btn, self.roi_import_btn,
#                  self.roi_export_btn, *self.align_btns.values()):
#            w.setEnabled(has_image)
#
#    def set_grid_ready(self, on: bool) -> None:
#        self.add_grid_btn.setEnabled(on)
#
#    def set_groups(self, groups: List[Group], active_gid, counts: dict) -> None:
#        self._active_gid = active_gid
#        sig = (tuple((g.gid, g.name, g.color) for g in groups), active_gid,
#               tuple(sorted(counts.items())))
#        if sig == getattr(self, "_grp_sig", None):
#            return          # a refresh that changes nothing costs nothing
#        self._grp_sig = sig
#        _clear(self.grp_host)
#        for g in groups:
#            self.grp_host.addWidget(
#                self._group_row(g, g.gid == active_gid, counts.get(g.gid, 0)))
#
#    def set_rois(self, active_group_rois, active_rid,
#                 selected_rids=None, outlier_rids=None, values=None) -> None:
#        selected = set(selected_rids or [])
#        outliers = set(outlier_rids or [])
#        values = values or {}
#        sig = (tuple((r.rid, tuple(r.rect), r.label) for r in active_group_rois),
#               active_rid, tuple(sorted(selected)), tuple(sorted(outliers)),
#               tuple(sorted((k, round(float(v), 6))
#                            for k, v in values.items())))
#        if sig == getattr(self, "_roi_sig", None):
#            return          # rebuilding a hundred rows for nothing is the jank
#        self._roi_sig = sig
#        _clear(self.roi_host)
#        self._roi_rows = {}
#        for r in active_group_rois:
#            row = self._roi_row(r, r.rid == active_rid, r.rid in selected,
#                                r.rid in outliers, values.get(r.rid))
#            self._roi_rows[r.rid] = row
#            self.roi_host.addWidget(row)
#        # size the list to its content, capped so it never buries the buttons
#        n = len(active_group_rois)
#        self.roi_scroll.setFixedHeight(min(176, n * 30 + 6) if n else 6)
#
#    def set_hovered_roi(self, rid: int) -> None:
#        """Highlight the row for `rid` (canvas → list hover sync)."""
#        for r, row in getattr(self, "_roi_rows", {}).items():
#            row.set_hover(r == rid)
#
#    def set_metric_state(self, metrics, extra_ids=()) -> None:
#        self.metrics.set_state(metrics, extra_ids)
#
#    def set_roi_order(self, order: str) -> None:
#        idx = self.order_box.findData(order)
#        self.order_box.blockSignals(True)
#        self.order_box.setCurrentIndex(idx if idx >= 0 else 0)
#        self.order_box.blockSignals(False)
#
#    def grid_shape(self):
#        return int(self.grid_rows.value()), int(self.grid_cols.value())
#
#    def roi_size(self):
#        return int(self.roi_w.value()), int(self.roi_h.value())
#
#    def _group_row(self, g: Group, active: bool, count: int) -> QWidget:
#        row = _ItemRow(active)
#        row.add_swatch(g.color, lambda c: self.group_color.emit(g.gid, c))
#        row.add_name(g.name, lambda t: self.group_rename.emit(g.gid, t))
#        row.add_count(f"{count}")
#        row.add_delete(lambda: self.group_del.emit(g.gid))
#        row.clicked = lambda: self.group_pick.emit(g.gid)
#        return row
#
#    def _roi_row(self, r, active: bool, selected: bool,
#                 outlier: bool = False, value=None) -> QWidget:
#        row = _ItemRow(active, compact=True, boxed=False, selected=selected)
#        row.add_name(r.label or f"ROI {r.rid}", None,
#                     color=(theme.WARNING if outlier else None))
#        if outlier:
#            row.add_flag("!", theme.WARNING,
#                         "Outlier of the shown metric within this group")
#        if value is not None:
#            row.add_count(_fmt(float(value)))
#        row.add_delete(lambda: self.roi_del.emit(r.rid))
#        row.clicked = lambda: self.roi_pick.emit(r.rid)
#        row.on_hover = lambda on, rid=r.rid: self.roi_hovered.emit(rid if on else -1)
#        return row
#
#    def _clear_active(self) -> None:
#        if self._active_gid is not None:
#            self.group_clear.emit(self._active_gid)
#
#
#def _button_row(*buttons):
#    """A full-width row of equal-stretch buttons — responsive, no cramming."""
#    row = QHBoxLayout()
#    row.setSpacing(8)
#    for b in buttons:
#        b.setMinimumHeight(32)
#        row.addWidget(b, 1)
#    return row
#
#
#class _ItemRow(QFrame):
#    def __init__(self, active: bool, compact: bool = False,
#                 boxed: bool = True, selected: bool = False):
#        super().__init__()
#        self.clicked: Optional[Callable] = None
#        self.on_hover: Optional[Callable] = None
#        self._boxed = boxed
#        self._hl = active or selected
#        self._apply_style(False)
#        self.lay = QHBoxLayout(self)
#        self.lay.setContentsMargins(8, 3 if compact else 5, 8, 3 if compact else 5)
#        self.lay.setSpacing(8)
#
#    def _apply_style(self, hover: bool) -> None:
#        if self._boxed:
#            bg = theme.AMBER_SOFT if self._hl else theme.CARD
#            border = theme.AMBER if self._hl else theme.LINE
#            self.setStyleSheet(f"background:{bg}; border:1px solid {border};"
#                               "border-radius:9px;")
#        else:                                   # borderless (ROI rows)
#            bg = theme.AMBER_SOFT if self._hl else (theme.LINE2 if hover
#                                                    else "transparent")
#            self.setStyleSheet(f"background:{bg}; border:none; border-radius:7px;")
#
#    def set_hover(self, on: bool) -> None:
#        if not self._hl:
#            self._apply_style(on)
#
#    def enterEvent(self, e):
#        self.set_hover(True)
#        if self.on_hover:
#            self.on_hover(True)
#        super().enterEvent(e)
#
#    def leaveEvent(self, e):
#        self.set_hover(False)
#        if self.on_hover:
#            self.on_hover(False)
#        super().leaveEvent(e)
#
#    def add_swatch(self, color, on_pick):
#        self.lay.addWidget(_swatch(color, on_pick))
#
#    def add_flag(self, text, color, tooltip=""):
#        f = QLabel(text)
#        f.setToolTip(tooltip)
#        f.setStyleSheet(f"color:{color}; font-weight:800;")
#        self.lay.addWidget(f)
#
#    def add_name(self, name, on_rename, color=None):
#        if on_rename is None:
#            lbl = QLabel(name)
#            lbl.setStyleSheet("font-weight:600;" + (f"color:{color};" if color else ""))
#            self.lay.addWidget(lbl)
#        else:
#            ed = QLineEdit(name)
#            ed.setFrame(False)
#            ed.setStyleSheet("QLineEdit{background:transparent; border:none; "
#                             "font-weight:600; padding:0;} "
#                             "QLineEdit:focus{border:none;}")
#            ed.editingFinished.connect(lambda: on_rename(ed.text().strip() or name))
#            self.lay.addWidget(ed)
#        self.lay.addStretch(1)
#
#    def add_count(self, text):
#        c = QLabel(text)
#        c.setStyleSheet(f"color:{theme.INK2};")
#        c.setFont(theme.mono_font(9))
#        self.lay.addWidget(c)
#
#    def add_delete(self, on_del):
#        b = QPushButton("×")
#        b.setFixedSize(20, 20)
#        b.setStyleSheet(f"border:none; color:{theme.INK3}; font-size:15px;")
#        b.clicked.connect(on_del)
#        self.lay.addWidget(b)
#
#    def mousePressEvent(self, e):
#        if self.clicked and self.childAt(e.position().toPoint()) is None:
#            self.clicked()
#        super().mousePressEvent(e)
#
#
## --------------------------------------------------------------------------- #
## Analysis panel (hosted in its own window)
## --------------------------------------------------------------------------- #
#class AnalysisPanel(QWidget):
#    mode_changed = Signal(str)              # "between" | "within"
#    within_group_changed = Signal(str)
#    export_requested = Signal()
#    export_image_requested = Signal(str)    # which section: see SCOPES
#
#    def __init__(self, parent=None):
#        super().__init__(parent)
#        root = QVBoxLayout(self)
#        root.setContentsMargins(16, 12, 16, 12)
#        root.setSpacing(10)
#
#        head = QHBoxLayout()
#        head.setSpacing(12)
#        title = QLabel("Analysis")
#        title.setFont(theme.display_font(14, weight=700))
#        head.addWidget(title)
#        self.busy = QLabel("")
#        self.busy.setObjectName("Hint")
#        head.addWidget(self.busy)
#        self.between_btn = QPushButton("Between groups")
#        self.within_btn = QPushButton("Within a group")
#        for b, m in ((self.between_btn, "between"), (self.within_btn, "within")):
#            b.setCheckable(True)
#            b.setFixedHeight(28)
#            b.clicked.connect(lambda _=False, mm=m: self._pick_mode(mm))
#            head.addWidget(b)
#        self.between_btn.setChecked(True)
#        head.addSpacing(10)
#        self.box_btn = QPushButton("◫ Box")
#        self.hist_btn = QPushButton("▭ Histogram")
#        self.pos_btn = QPushButton("↗ Position")
#        self.map_btn = QPushButton("▦ Heat map")
#        for b, t in ((self.box_btn, "box"), (self.hist_btn, "hist"),
#                     (self.pos_btn, "position"), (self.map_btn, "map")):
#            b.setCheckable(True)
#            b.setFixedHeight(28)
#            b.clicked.connect(lambda _=False, tt=t: self._pick_ctype(tt))
#            head.addWidget(b)
#        self.box_btn.setToolTip("Distribution as a box-and-strip plot.")
#        self.hist_btn.setToolTip("Distribution as an overlaid histogram.")
#        self.pos_btn.setToolTip(
#            "Metric against ROI position — a uniform field reads flat.")
#        self.map_btn.setToolTip(
#            "Spatial heat map: each ROI drawn where it sits, coloured by the "
#            "metric.")
#        self.box_btn.setChecked(True)
#        head.addSpacing(8)
#        self.points_chk = QCheckBox("points")
#        self.whiskers_chk = QCheckBox("whiskers")
#        for chk in (self.points_chk, self.whiskers_chk):
#            chk.setChecked(True)
#            chk.toggled.connect(self._on_chart_opts)
#            head.addWidget(chk)
#        self.bins_spin = QSpinBox()
#        self.bins_spin.setRange(0, 80)
#        self.bins_spin.setValue(0)
#        self.bins_spin.setPrefix("bins ")
#        self.bins_spin.setSpecialValueText("bins auto")
#        self.bins_spin.setFixedWidth(88)
#        self.bins_spin.setFixedHeight(28)
#        self.bins_spin.setToolTip("Histogram bin count. 0 = √n, bounded.")
#        self.bins_spin.valueChanged.connect(self._on_chart_opts)
#        self.bins_spin.setVisible(False)
#        head.addWidget(self.bins_spin)
#        self.pct_chk = QCheckBox("%")
#        self.pct_chk.setToolTip(
#            "Plot each group's share of its own n instead of raw counts — the "
#            "only way two groups of different size compare.")
#        self.pct_chk.toggled.connect(self._on_chart_opts)
#        self.pct_chk.setVisible(False)
#        head.addWidget(self.pct_chk)
#        self.legend_chk = QCheckBox("legend")
#        self.legend_chk.setToolTip(
#            "Show the key in the plot's top-right corner — the groups with "
#            "their n, and for a profile what each line means. Off by default: "
#            "on a figure with two series it is furniture, and it sits on top "
#            "of the data.")
#        self.legend_chk.toggled.connect(self._on_chart_opts)
#        head.addWidget(self.legend_chk)
#        self.ownscale_chk = QCheckBox("own scale")
#        self.ownscale_chk.setToolTip(
#            "Give every group its own value range, printed under the lane. "
#            "Off = one shared axis, where a group with a tiny spread beside a "
#            "distant one flattens to a line.")
#        self.ownscale_chk.toggled.connect(self._on_chart_opts)
#        head.addWidget(self.ownscale_chk)
#        self.axis_box = QComboBox()
#        self.axis_box.addItem("X position", "x")
#        self.axis_box.addItem("Y position", "y")
#        self.axis_box.setToolTip("Plot against the ROI centre's X or Y coordinate.")
#        self.axis_box.currentIndexChanged.connect(self._on_axis)
#        self.axis_box.setVisible(False)
#        head.addWidget(self.axis_box)
#        self.trend_chk = QCheckBox("trend")
#        self.trend_chk.setChecked(True)
#        self.trend_chk.setToolTip("Overlay the least-squares tilt of the profile.")
#        self.trend_chk.toggled.connect(self._on_chart_opts)
#        self.trend_chk.setVisible(False)
#        head.addWidget(self.trend_chk)
#        self.cells_chk = QCheckBox("cells")
#        self.cells_chk.setChecked(True)
#        self.cells_chk.setToolTip(
#            "Draw each ROI as a filled cell that meets its neighbours, so a "
#            "cell can be read against the one beside it. Off = separate dots.")
#        self.cells_chk.toggled.connect(self._on_cells)
#        self.cells_chk.setVisible(False)
#        head.addWidget(self.cells_chk)
#        self.equal_chk = QCheckBox("equal cells")
#        self.equal_chk.setChecked(True)
#        self.equal_chk.setToolTip(
#            "Draw every cell the same size, one slot per row and column — a "
#            "die map. Off: each cell spans to the midline with its neighbour, "
#            "so an uneven pitch gives cells of uneven area.")
#        self.equal_chk.toggled.connect(self._on_chart_opts)
#        self.equal_chk.setVisible(False)
#        head.addWidget(self.equal_chk)
#        self.mapval_chk = QCheckBox("values")
#        self.mapval_chk.setToolTip(
#            "Print the metric inside each cell (cells wide enough to hold it).")
#        self.mapval_chk.toggled.connect(self._on_chart_opts)
#        self.mapval_chk.setVisible(False)
#        head.addWidget(self.mapval_chk)
#        self.selector_lbl = QLabel("")
#        self.selector_lbl.setObjectName("Hint")
#        head.addWidget(self.selector_lbl)
#        self.selector = QComboBox()
#        self.selector.setMinimumWidth(150)
#        self.selector.currentIndexChanged.connect(self._selector_changed)
#        head.addWidget(self.selector)
#        head.addStretch(1)
#        self.sub = QLabel("")
#        self.sub.setObjectName("Hint")
#        head.addWidget(self.sub)
#        self.axes_btn = QPushButton("Chart settings…")
#        self.axes_btn.setToolTip(
#            "Rename the figures, name the axes, set the tick counts and lock "
#            "the value and heat scales.")
#        self.axes_btn.clicked.connect(self.edit_chart_settings)
#        head.addWidget(self.axes_btn)
#        self.image_btn = QToolButton()
#        self.image_btn.setText("Export image ▾")
#        self.image_btn.setPopupMode(QToolButton.InstantPopup)
#        self.image_btn.setToolTip(
#            "Save any part of the results as a picture — PNG at 3× for "
#            "slides, or SVG for a paper.")
#        self._image_menu = QMenu(self.image_btn)
#        self.image_btn.setMenu(self._image_menu)
#        self.image_btn.setEnabled(False)
#        head.addWidget(self.image_btn)
#        self.export_btn = QPushButton("Export CSV")
#        self.export_btn.setObjectName("Primary")
#        self.export_btn.clicked.connect(self.export_requested)
#        self.export_btn.setEnabled(False)
#        head.addWidget(self.export_btn)
#        root.addLayout(head)
#
#        self.scroll = QScrollArea()
#        self.scroll.setWidgetResizable(True)
#        self.scroll.setFrameShape(QScrollArea.NoFrame)
#        self.body = QWidget()
#        self.body_lay = QVBoxLayout(self.body)
#        self.body_lay.setContentsMargins(0, 0, 0, 0)
#        self.body_lay.setSpacing(10)
#        self.scroll.setWidget(self.body)
#        root.addWidget(self.scroll, 1)
#
#        self._mode = "between"
#        self._chart_type = "box"
#        self._pos_axis = "x"
#        self._last_result = None
#        self._suppress = False
#        self._cards: dict = {}          # scope -> the widget to export
#        self._chart_widgets: List[DistributionChart] = []
#        self._style: dict = {}          # title / axis / tick / scale overrides
#        self._main = self.body_lay      # figures column
#        self._side = self.body_lay      # annotations column
#
#    def _pick_mode(self, mode: str) -> None:
#        self._mode = mode
#        self.between_btn.setChecked(mode == "between")
#        self.within_btn.setChecked(mode == "within")
#        self.mode_changed.emit(mode)
#
#    def _pick_ctype(self, t: str) -> None:
#        self._chart_type = t
#        self.box_btn.setChecked(t == "box")
#        self.hist_btn.setChecked(t == "hist")
#        self.pos_btn.setChecked(t == "position")
#        self.map_btn.setChecked(t == "map")
#        for chk in (self.points_chk, self.whiskers_chk):
#            chk.setEnabled(t == "box")
#            chk.setVisible(t not in ("position", "map"))
#        self.ownscale_chk.setVisible(t == "box")
#        self.legend_chk.setVisible(t in ("box", "hist", "position"))
#        for w in (self.bins_spin, self.pct_chk):
#            w.setVisible(t == "hist")
#        self.axis_box.setVisible(t == "position")
#        self.trend_chk.setVisible(t == "position")
#        for chk in (self.cells_chk, self.equal_chk, self.mapval_chk):
#            chk.setVisible(t == "map")
#        for chk in (self.equal_chk, self.mapval_chk):
#            chk.setEnabled(self.cells_chk.isChecked())
#        if self._last_result is not None:
#            self._render_body(self._last_result)   # re-render, no recompute
#
#    def _on_axis(self, _i: int) -> None:
#        if self._suppress:
#            return
#        self._pos_axis = str(self.axis_box.currentData() or "x")
#        if self._last_result is not None:
#            self._render_body(self._last_result)   # positions are already there
#
#    def _on_cells(self, on: bool) -> None:
#        # both only mean anything for cells: values are printed inside one,
#        # and dots have no area to equalise
#        for chk in (self.equal_chk, self.mapval_chk):
#            chk.setEnabled(bool(on))
#        self._on_chart_opts()
#
#    def _on_chart_opts(self, _=False) -> None:
#        if self._last_result is not None:
#            self._render_body(self._last_result)
#
#    # -- chart settings ------------------------------------------------ #
#    def chart_style(self) -> dict:
#        """The title / axis / tick / scale overrides — saved with the project."""
#        return dict(self._style)
#
#    def set_chart_style(self, style) -> None:
#        self._style = dict(style or {})
#        if self._last_result is not None:
#            self._render_body(self._last_result)
#
#    def edit_chart_settings(self) -> None:
#        names = [c._title for c in self._chart_widgets] or ["chart"]
#        dlg = ChartSettingsDialog(self, names, self._style)
#        if dlg.exec() == QDialog.Accepted:
#            self.set_chart_style(dlg.result_style())
#
#    def _style_for(self, title: str) -> dict:
#        """The shared overrides plus this chart's own title, if it has one."""
#        st = {k: v for k, v in self._style.items() if k != "titles"}
#        custom = (self._style.get("titles") or {}).get(title)
#        if custom:
#            st["title"] = custom
#        return st
#
#    #: The header toggles, paired with the project key each is stored under.
#    #: ``map_values`` keeps the box's own state rather than the value the
#    #: renderer uses (which is ANDed with *cells*), so turning cells back on
#    #: restores the choice instead of silently clearing it.
#    _OPT_BOXES = (("points", "points_chk"), ("whiskers", "whiskers_chk"),
#                  ("own_scale", "ownscale_chk"), ("legend", "legend_chk"),
#                  ("hist_pct", "pct_chk"), ("trend", "trend_chk"),
#                  ("cells", "cells_chk"), ("equal_cells", "equal_chk"),
#                  ("map_values", "mapval_chk"))
#
#    def chart_options(self) -> dict:
#        """The header toggles — saved with the project.
#
#        Without these a reopened project drew the chart with the defaults
#        back: points on, legend off, bins auto. The style says how a chart
#        looks; this says what is on it.
#        """
#        out = {key: getattr(self, name).isChecked()
#               for key, name in self._OPT_BOXES}
#        out["bins"] = int(self.bins_spin.value())
#        return out
#
#    def set_chart_options(self, opts) -> None:
#        """Restore those toggles, then draw once rather than ten times."""
#        opts = dict(opts or {})
#        widgets = [getattr(self, name) for _, name in self._OPT_BOXES]
#        widgets.append(self.bins_spin)
#        for w in widgets:
#            w.blockSignals(True)
#        try:
#            for key, name in self._OPT_BOXES:
#                if key in opts:
#                    getattr(self, name).setChecked(bool(opts[key]))
#            if opts.get("bins") is not None:
#                self.bins_spin.setValue(int(opts["bins"]))
#        finally:
#            for w in widgets:
#                w.blockSignals(False)
#        # cells gates the two that only mean something inside a cell
#        for chk in (self.equal_chk, self.mapval_chk):
#            chk.setEnabled(self.cells_chk.isChecked())
#        if self._last_result is not None:
#            self._render_body(self._last_result)
#
#    def chart_state(self) -> tuple:
#        """(chart type, position axis) — persisted with the project."""
#        return self._chart_type, self._pos_axis
#
#    def set_chart_state(self, ctype, axis) -> None:
#        self._suppress = True
#        self._pos_axis = "y" if str(axis).lower() == "y" else "x"
#        self.axis_box.setCurrentIndex(1 if self._pos_axis == "y" else 0)
#        self._suppress = False
#        self._pick_ctype(ctype if ctype in ("box", "hist", "position", "map")
#                         else "box")
#
#    def _selector_changed(self, _i: int) -> None:
#        if self._suppress:
#            return
#        data = self.selector.currentData()
#        if data is not None and self._mode == "within":
#            self.within_group_changed.emit(str(data))
#
#    def set_controls(self, mode, groups, within_gid, enabled) -> None:
#        self._mode = mode
#        self.between_btn.setChecked(mode == "between")
#        self.within_btn.setChecked(mode == "within")
#        self._suppress = True
#        self.selector.clear()
#        if mode == "within":
#            self.selector_lbl.setText("Group")
#            self.selector.setVisible(True)
#            for g in groups:
#                self.selector.addItem(g.name, g.gid)
#            self.selector.setCurrentIndex(_gindex_of(groups, within_gid))
#        else:
#            self.selector_lbl.setText("")
#            self.selector.setVisible(False)
#        self._suppress = False
#        self.export_btn.setEnabled(bool(enabled))
#
#    def set_computing(self, on: bool) -> None:
#        self.busy.setText("· working…" if on else "")
#
#    def show_result(self, result) -> None:
#        self._last_result = result
#        self._render_body(result)
#
#    def _render_body(self, result) -> None:
#        _clear(self.body_lay)
#        self._cards = {}
#        self._chart_widgets = []
#        self.sub.setText(result.subtitle)
#        if result.empty:
#            self._main = self.body_lay
#            self._side = self.body_lay
#            self._empty(result.empty)
#            return
#        # Two columns: the figures on the left, where the eye starts and where
#        # they get the room to be figures; the numbers that annotate them
#        # down the right. One column put every chart in a wide band at the top
#        # with the tables stacked underneath, which reads as two unrelated
#        # pages rather than one result.
#        row = QWidget()
#        rlay = QHBoxLayout(row)
#        rlay.setContentsMargins(0, 0, 0, 0)
#        rlay.setSpacing(14)
#        main_host, side_host = QWidget(), QWidget()
#        self._main = QVBoxLayout(main_host)
#        self._side = QVBoxLayout(side_host)
#        for lay in (self._main, self._side):
#            lay.setContentsMargins(0, 0, 0, 0)
#            lay.setSpacing(10)
#        side_host.setMinimumWidth(300)
#        rlay.addWidget(main_host, 3)
#        rlay.addWidget(side_host, 2)
#        self.body_lay.addWidget(row)
#
#        charts = [(c.title, [{"label": s.label, "color": s.color,
#                              "values": s.values,
#                              "pos_x": s.pos_x, "pos_y": s.pos_y}
#                             for s in c.series])
#                  for c in result.charts]
#        self._main.addStretch(1)        # the figures sit mid-height…
#        self._chart_grid(charts)
#        self._main.addStretch(1)
#        if result.ranking:
#            self._ranking_card(result.ranking)
#        if result.heat:
#            self._heatmap_card(result.heat)
#        if result.table_rows:
#            self._table(result.table_headers, result.table_rows)
#        self._side.addStretch(1)        # …the annotations stack from the top
#        if not any(self._cards.get(k) for k in ("ranking", "heat", "table")):
#            side_host.hide()            # nothing to annotate with: all figure
#            rlay.setStretch(1, 0)
#        self._rebuild_image_menu()
#
#    def _rebuild_image_menu(self) -> None:
#        """Offer exactly the sections this result has, each chart included."""
#        self._image_menu.clear()
#        labels = dict(self.SCOPES)
#        scopes = self.scopes_available()
#        for key in scopes:
#            self._image_menu.addAction(
#                f"{labels[key]}…",
#                lambda _=False, k=key: self.export_image_requested.emit(k))
#            if key == "charts" and len(self._chart_widgets) > 1:
#                # one figure per file is what a document actually takes
#                for i, c in enumerate(self._chart_widgets):
#                    self._image_menu.addAction(
#                        f"    {c.title_text()}…",
#                        lambda _=False, k=f"chart:{i}":
#                        self.export_image_requested.emit(k))
#        self.image_btn.setEnabled(bool(scopes))
#
#    # -- image export --------------------------------------------------- #
#    SCOPES = (("charts", "Charts"), ("ranking", "Attribute ranking"),
#              ("heat", "Group × metric heatmap"), ("table", "Summary table"),
#              ("all", "Everything"))
#
#    def scopes_available(self) -> List[str]:
#        """Which sections the current result actually has to export."""
#        out = [k for k, _lab in self.SCOPES
#               if k not in ("all",) and self._cards.get(k) is not None]
#        return out + (["all"] if len(out) > 1 else [])
#
#    def save_image(self, path: str, scope: str = "charts",
#                   scale: float = 3.0) -> Optional[str]:
#        """Save one section of the results — or all of it — as a picture."""
#        if scope == "all":
#            widgets = [w for _k, w in self._cards.items() if w is not None]
#            if not widgets:
#                return None
#            area = widgets[0].geometry()
#            for w in widgets[1:]:
#                area = area.united(w.geometry())
#            return save_widget_image(self.body, path, scale, crop=area,
#                                     background=theme.WINDOW)
#        if scope.startswith("chart:"):          # one figure on its own
#            i = int(scope.split(":", 1)[1])
#            if not 0 <= i < len(self._chart_widgets):
#                return None
#            return save_widget_image(self._chart_widgets[i], path, scale)
#        host = self._cards.get(scope)
#        if host is None:
#            return None
#        crop = None
#        if scope == "charts":
#            # only the figures travel — the layout's slack either side of them
#            # is margin on screen and dead white space in a document
#            charts = host.findChildren(DistributionChart)
#            if not charts:
#                return None
#            crop = charts[0].geometry()
#            for c in charts[1:]:
#                crop = crop.united(c.geometry())
#        return save_widget_image(host, path, scale, crop=crop)
#
#    def save_charts_image(self, path: str, scale: float = 3.0) -> Optional[str]:
#        return self.save_image(path, "charts", scale)
#
#    def _ranking_card(self, ranking) -> None:
#        host = QFrame()
#        host.setObjectName("Card")
#        self._cards["ranking"] = host
#        lay = QVBoxLayout(host)
#        lay.setContentsMargins(14, 12, 14, 14)
#        lay.setSpacing(8)
#        head = QLabel("Attribute ranking")
#        head.setObjectName("SectionTitle")
#        head.setFont(theme.display_font(13, weight=700))
#        lay.addWidget(head)
#        hint = QLabel("How well each metric separates the groups "
#                      "(η² = share of variance explained; d = Cohen's d).")
#        hint.setObjectName("Hint")
#        hint.setWordWrap(True)
#        lay.addWidget(hint)
#        grid = QGridLayout()
#        grid.setHorizontalSpacing(10)
#        grid.setVerticalSpacing(6)
#        for i, (label, eta, d) in enumerate(ranking):
#            rk = QLabel(f"{i + 1}")
#            rk.setFont(theme.mono_font(9, weight=700))
#            rk.setStyleSheet(f"color:{theme.INK3};")
#            nm = QLabel(label)
#            nm.setStyleSheet("font-weight:600;")
#            bar = _Bar(eta or 0.0)
#            txt = ("—" if eta is None else f"η²={eta:.2f}"
#                   + (f" · d={d:.2f}" if d is not None else ""))
#            val = QLabel(txt)
#            val.setFont(theme.mono_font(8))
#            val.setStyleSheet(f"color:{theme.INK2};")
#            grid.addWidget(rk, i, 0)
#            grid.addWidget(nm, i, 1)
#            grid.addWidget(bar, i, 2)
#            grid.addWidget(val, i, 3)
#        grid.setColumnStretch(2, 1)
#        lay.addLayout(grid)
#        self._side.addWidget(host)
#
#    def _heatmap_card(self, heat) -> None:
#        host = QFrame()
#        host.setObjectName("Card")
#        self._cards["heat"] = host
#        lay = QVBoxLayout(host)
#        lay.setContentsMargins(14, 12, 14, 14)
#        lay.setSpacing(8)
#        head = QLabel("Group × metric heatmap")
#        head.setObjectName("SectionTitle")
#        head.setFont(theme.display_font(13, weight=700))
#        lay.addWidget(head)
#        hint = QLabel("Group mean per metric, colour-normalised down each column.")
#        hint.setObjectName("Hint")
#        lay.addWidget(hint)
#        grid = QGridLayout()
#        grid.setHorizontalSpacing(4)
#        grid.setVerticalSpacing(4)
#        metrics, groups = heat["metrics"], heat["groups"]
#        colors, values = heat["colors"], heat["values"]
#        for c, m in enumerate(metrics):
#            h = QLabel(m)
#            h.setFont(theme.mono_font(8))
#            h.setStyleSheet(f"color:{theme.INK3}; font-weight:600;")
#            h.setAlignment(Qt.AlignCenter)
#            grid.addWidget(h, 0, c + 1)
#        arr = np.asarray(values, dtype=np.float64)
#        for c in range(len(metrics)):
#            col = arr[:, c] if arr.size else np.array([])
#            fin = col[np.isfinite(col)]
#            lo, hi = (float(fin.min()), float(fin.max())) if fin.size else (0.0, 1.0)
#            for r in range(len(groups)):
#                if c == 0:
#                    gl = QLabel("■ " + groups[r])
#                    gl.setFont(theme.mono_font(8))
#                    gl.setStyleSheet(f"color:{colors[r]}; font-weight:600;")
#                    grid.addWidget(gl, r + 1, 0)
#                v = float(arr[r, c])
#                cell = QLabel("—" if not np.isfinite(v) else _fmt(v))
#                cell.setAlignment(Qt.AlignCenter)
#                cell.setFont(theme.mono_font(8, weight=700))
#                cell.setMinimumWidth(64)
#                if not np.isfinite(v):
#                    cell.setStyleSheet(f"background:{theme.LINE2}; color:{theme.INK3};"
#                                       "border-radius:4px; padding:5px;")
#                else:
#                    t = 0.5 if hi <= lo else (v - lo) / (hi - lo)
#                    bg = heat_color(t)
#                    fg = "#FFFFFF" if _is_dark(bg) else theme.INK
#                    cell.setStyleSheet(f"background:{bg}; color:{fg};"
#                                       "border-radius:4px; padding:5px;")
#                grid.addWidget(cell, r + 1, c + 1)
#        lay.addLayout(grid)
#        self._side.addWidget(host)
#
#    def _chart_grid(self, charts) -> None:
#        grid_host = QWidget()
#        grid_host.setObjectName("ChartSheet")
#        self._cards["charts"] = grid_host
#        grid = QGridLayout(grid_host)
#        grid.setContentsMargins(0, 0, 0, 0)
#        grid.setSpacing(10)
#        opts = {"points": self.points_chk.isChecked(),
#                "whiskers": self.whiskers_chk.isChecked(),
#                "own_scale": self.ownscale_chk.isChecked(),
#                "legend": self.legend_chk.isChecked(),
#                "bins": int(self.bins_spin.value()),
#                "hist_pct": self.pct_chk.isChecked(),
#                "cells": self.cells_chk.isChecked(),
#                "equal_cells": self.equal_chk.isChecked(),
#                "map_values": (self.mapval_chk.isChecked()
#                               and self.cells_chk.isChecked())}
#        wide = self._chart_type in ("position", "map")   # these need the width
#        for i, (title, series) in enumerate(charts):
#            chart = DistributionChart()
#            chart.set_data(title, series, self._chart_type, opts,
#                           axis=self._pos_axis, trend=self.trend_chk.isChecked(),
#                           xlabel=title, style=self._style_for(title))
#            self._chart_widgets.append(chart)
#            if wide:
#                grid.addWidget(chart, i, 0, 1, 3)
#                continue
#            # One figure per row, as large as the column allows up to a
#            # printable width — a distribution squeezed two-up is a thumbnail,
#            # and a thumbnail is what nobody can read on a slide.
#            chart.setMinimumWidth(340)
#            chart.setMaximumWidth(720)
#            grid.addWidget(chart, i, 1)
#        if not wide:
#            grid.setColumnStretch(0, 1)      # slack either side: a plate on a
#            grid.setColumnStretch(2, 1)      # page, not a banner on a margin
#        self._main.addWidget(grid_host)
#
#    def _table(self, headers, rows) -> None:
#        host = QFrame()
#        host.setObjectName("Card")
#        self._cards["table"] = host
#        lay = QGridLayout(host)
#        lay.setContentsMargins(12, 10, 12, 10)
#        lay.setSpacing(6)
#        for c, h in enumerate(headers):
#            lbl = QLabel(h)
#            lbl.setStyleSheet(f"color:{theme.INK3}; font-weight:600;")
#            lbl.setFont(theme.mono_font(8))
#            lay.addWidget(lbl, 0, c)
#        for r, (name, color, cells) in enumerate(rows, start=1):
#            nm = QLabel((("■ " + name) if color else name))
#            nm.setStyleSheet(f"color:{color or theme.INK2}; font-weight:600;")
#            lay.addWidget(nm, r, 0)
#            for c, val in enumerate(cells, start=1):
#                cell = QLabel(val)
#                cell.setFont(theme.mono_font(9))
#                lay.addWidget(cell, r, c)
#        self._side.addWidget(host)
#
#    def _empty(self, text: str) -> None:
#        lbl = QLabel(text)
#        lbl.setObjectName("Hint")
#        lbl.setAlignment(Qt.AlignCenter)
#        lbl.setMinimumHeight(160)
#        self.body_lay.addWidget(lbl)
#
#
#def _gindex_of(groups, gid):
#    for i, g in enumerate(groups):
#        if g.gid == gid:
#            return i
#    return 0
#
#
## --------------------------------------------------------------------------- #
## ROI pixel inspector (hosted in its own window)
## --------------------------------------------------------------------------- #
#_HEAT_LUT = None
#
#
#def _heat_lut():
#    global _HEAT_LUT
#    if _HEAT_LUT is None:
#        lut = np.zeros((256, 3), dtype=np.uint8)
#        for i in range(256):
#            c = QColor(heat_color(i / 255.0))
#            lut[i] = (c.red(), c.green(), c.blue())
#        _HEAT_LUT = lut
#    return _HEAT_LUT
#
#
#class RoiInspector(QWidget):
#    """Pixel-level view of one ROI: false-colour heatmap, grey-level histogram,
#    and horizontal / vertical intensity profiles."""
#
#    export_image_requested = Signal()
#
#    def __init__(self, parent=None):
#        super().__init__(parent)
#        self._patch = None
#        self._title = ""
#        self.setMinimumSize(560, 420)
#
#    def set_roi(self, patch, title: str) -> None:
#        self._patch = None if patch is None else np.asarray(patch)
#        self._title = title
#        self.update()
#
#    def paintEvent(self, _e) -> None:
#        p = QPainter(self)
#        p.setRenderHint(QPainter.Antialiasing, True)
#        p.fillRect(self.rect(), QColor(theme.WINDOW))
#        p.setPen(QColor(theme.INK))
#        p.setFont(theme.display_font(13, weight=700))
#        p.drawText(16, 24, self._title or "ROI inspector")
#        patch = self._patch
#        if patch is None or patch.size == 0:
#            p.setPen(QColor(theme.INK3))
#            p.setFont(theme.mono_font(9))
#            p.drawText(self.rect(), Qt.AlignCenter,
#                       "Double-click an ROI on the image to inspect its pixels.")
#            p.end()
#            return
#        pad, top = 16, 44
#        heat_w = min(240.0, (self.width() - 3 * pad) * 0.44)
#        heat = QRectF(pad, top, heat_w, heat_w * 0.82)
#        hist = QRectF(heat.right() + pad, top,
#                      self.width() - heat.right() - 2 * pad, heat.height())
#        prof = QRectF(pad, heat.bottom() + 30, self.width() - 2 * pad,
#                      self.height() - heat.bottom() - 30 - pad)
#        self._paint_heat(p, patch, heat)
#        self._paint_hist(p, patch, hist)
#        self._paint_profiles(p, patch, prof)
#        p.end()
#
#    def _cap(self, p, rect, text, color=None):
#        p.setPen(QColor(color or theme.INK3))
#        p.setFont(theme.mono_font(8, weight=700))
#        p.drawText(int(rect.left()), int(rect.top() - 6), text)
#
#    def _paint_heat(self, p, patch, rect):
#        self._cap(p, rect, "false-colour pixels")
#        h, w = patch.shape
#        rgb = np.ascontiguousarray(_heat_lut()[patch.astype(np.uint8)])
#        img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
#        scaled = img.scaled(int(rect.width()), int(rect.height()),
#                            Qt.KeepAspectRatio, Qt.FastTransformation)
#        x = rect.left() + (rect.width() - scaled.width()) / 2
#        y = rect.top() + (rect.height() - scaled.height()) / 2
#        p.drawImage(int(x), int(y), scaled)
#        p.setPen(QPen(QColor(theme.LINE), 1))
#        p.setBrush(Qt.NoBrush)
#        p.drawRect(QRectF(x, y, scaled.width(), scaled.height()))
#
#    def _paint_hist(self, p, patch, rect):
#        self._cap(p, rect, "grey-level histogram")
#        counts, _edges = pixel_hist(patch, 32)
#        mx = max(1, int(counts.max()))
#        bw = rect.width() / len(counts)
#        base = rect.bottom()
#        p.setPen(Qt.NoPen)
#        p.setBrush(QColor(theme.AMBER))
#        for i, c in enumerate(counts):
#            bh = (c / mx) * (rect.height() - 4)
#            p.drawRect(QRectF(rect.left() + i * bw + 1, base - bh,
#                              max(1.0, bw - 2), bh))
#        p.setPen(QPen(QColor(theme.LINE2), 1))
#        p.drawLine(int(rect.left()), int(base), int(rect.right()), int(base))
#        p.setPen(QColor(theme.INK3))
#        p.setFont(theme.mono_font(8))
#        p.drawText(QRectF(rect.left(), base + 2, rect.width(), 12), Qt.AlignLeft, "0")
#        p.drawText(QRectF(rect.left(), base + 2, rect.width(), 12),
#                   Qt.AlignRight, "255")
#        m = float(patch.mean())
#        mxx = rect.left() + (m / 255.0) * rect.width()
#        p.setPen(QPen(QColor(theme.INFO), 1.5))
#        p.drawLine(int(mxx), int(rect.top()), int(mxx), int(base))
#        p.setPen(QColor(theme.INFO))
#        p.setFont(theme.mono_font(8, weight=700))
#        p.drawText(int(mxx) + 3, int(rect.top() + 10), f"μ={m:.0f}")
#
#    def _paint_profiles(self, p, patch, rect):
#        p.setFont(theme.mono_font(8, weight=700))
#        fm = p.fontMetrics()
#        p.setPen(QColor(theme.INK3))
#        p.drawText(int(rect.left()), int(rect.top() - 6), "intensity profile")
#        x = rect.left() + fm.horizontalAdvance("intensity profile") + 14
#        p.setPen(QColor(theme.AMBER))
#        p.drawText(int(x), int(rect.top() - 6), "— cols")
#        x += fm.horizontalAdvance("— cols") + 10
#        p.setPen(QColor(theme.INFO))
#        p.drawText(int(x), int(rect.top() - 6), "— rows")
#        col = patch.mean(axis=0).astype(float)
#        row = patch.mean(axis=1).astype(float)
#        vals = np.concatenate([col, row])
#        lo, hi = float(vals.min()), float(vals.max())
#        if hi - lo < 1e-6:
#            lo -= 1.0
#            hi += 1.0
#        base, H = rect.bottom(), rect.height() - 4
#
#        def Y(v):
#            return base - (v - lo) / (hi - lo) * H
#
#        p.setPen(QPen(QColor(theme.LINE2), 1))
#        p.drawLine(int(rect.left()), int(base), int(rect.right()), int(base))
#
#        def plot(series, color):
#            if len(series) < 2:
#                return
#            pen = QPen(QColor(color), 1.8)
#            pen.setCosmetic(True)
#            p.setPen(pen)
#            pts = [QPointF(rect.left() + i / (len(series) - 1) * rect.width(), Y(v))
#                   for i, v in enumerate(series)]
#            for a, b in zip(pts, pts[1:]):
#                p.drawLine(a, b)
#
#        plot(col, theme.AMBER)
#        plot(row, theme.INFO)
#        p.setPen(QColor(theme.INK3))
#        p.setFont(theme.mono_font(8))
#        p.drawText(int(rect.left()), int(rect.top() + 8), f"{hi:.0f}")
#        p.drawText(int(rect.left()), int(base), f"{lo:.0f}")
#
#F 6704b9aa8aee880ca441c516ed2107947d5efdd3 30 pyproject.toml
#[build-system]
#requires = ["setuptools>=64", "wheel"]
#build-backend = "setuptools.build_meta"
#
#[project]
#name = "pear"
#version = "0.1.0"
#description = "PEAR — Pre-EBI Attribute Ranker: a pre-inspection attribute-discovery tool for EBI of repeating-cell structures."
#readme = "README.md"
#requires-python = ">=3.10"
#license = { text = "Proprietary" }
#authors = [{ name = "HX-FAD" }]
#dependencies = [
#    "PySide6>=6.5",
#    "opencv-python>=4.7",
#    "numpy>=1.23",
#]
#
#[project.optional-dependencies]
#dev = ["pytest>=7.0"]
#
#[project.scripts]
#pear = "pear.__main__:main"
#
#[tool.setuptools]
#packages = ["pear", "pear.core", "pear.ui"]
#
#[tool.pytest.ini_options]
#testpaths = ["tests"]
#
#F b586c228cfdfa1d928f8d6ff864e761d81df1522 4 requirements.txt
#PySide6>=6.5
#opencv-python>=4.7
#numpy>=1.23
#
#F f0a9e81d13a90d1306074ffc0b9093370433428a 182 tests/test_bundle.py
#"""The single-file text bundle: it round-trips, and it is not stale.
#
#The bundle is how the code reaches a machine that cannot download anything
#(see ``docs/NO-GIT-SETUP.md``). A stale bundle has no symptom on this machine —
#it shows up as *missing work* on the other one — so a test has to say so.
#"""
#
#from __future__ import annotations
#
#import os
#import subprocess
#import sys
#
#import pytest
#
#ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#sys.path.insert(0, os.path.join(ROOT, "tools"))
#
#import make_text_bundle as mtb            # noqa: E402
#
#BUNDLE = os.path.join(ROOT, "bundle", "pear_bundle.py")
#REBUILD = "python tools/make_text_bundle.py"
#
#
#def _in_git_repo() -> bool:
#    try:
#        subprocess.run(["git", "rev-parse", "--git-dir"], cwd=ROOT, check=True,
#                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
#    except (OSError, subprocess.CalledProcessError):
#        return False
#    return True
#
#
## Unpacked copies have no .git, and that is a supported way to run the tool —
## so skip rather than fail there.
#needs_git = pytest.mark.skipif(not _in_git_repo(),
#                               reason="needs a git checkout (git ls-files)")
#
#
#@needs_git
#def test_bundle_is_current():
#    assert os.path.isfile(BUNDLE), f"{BUNDLE} is missing — run: {REBUILD}"
#    with open(BUNDLE, encoding="utf-8") as fh:
#        on_disk = fh.read()
#    fresh = mtb.build(os.path.basename(BUNDLE))
#    assert on_disk == fresh, (
#        "bundle/pear_bundle.py is out of date — the copy that reaches the "
#        "offline machine would be missing this change.\n"
#        f"    git add -A && {REBUILD} && git add -A")
#
#
#@needs_git
#def test_bundle_round_trips_byte_for_byte(tmp_path):
#    """Every file comes back out exactly as it went in."""
#    items = mtb.collect()
#    assert items, "git ls-files found nothing"
#    text = mtb.build("pear_bundle.py", items=items)
#
#    out = tmp_path / "pear_bundle.py"
#    out.write_text(text, encoding="utf-8", newline="\n")
#    r = subprocess.run([sys.executable, str(out), "--dest", str(tmp_path / "x")],
#                       cwd=str(tmp_path), stdout=subprocess.PIPE,
#                       stderr=subprocess.STDOUT)
#    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")
#    for rel, data in items:
#        got = (tmp_path / "x" / rel).read_bytes()
#        assert got == data, f"{rel} did not survive the round trip"
#
#
#@needs_git
#def test_bundle_survives_crlf_in_transit(tmp_path):
#    """Notepad and mail filters rewrite LF to CRLF; that must not break it.
#
#    This is why the format frames files by *line count* rather than byte
#    count — a byte count would corrupt every file after the first.
#    """
#    items = mtb.collect()[:4]
#    text = mtb.build("pear_bundle.py", items=items, total_files=len(items))
#    out = tmp_path / "pear_bundle.py"
#    out.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
#    r = subprocess.run([sys.executable, str(out), "--dest", str(tmp_path / "x")],
#                       cwd=str(tmp_path), stdout=subprocess.PIPE,
#                       stderr=subprocess.STDOUT)
#    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")
#    for rel, data in items:
#        assert (tmp_path / "x" / rel).read_bytes() == data
#
#
#@needs_git
#def test_truncated_bundle_is_reported_not_silently_partial(tmp_path):
#    """A cut-off paste must fail loudly — a half-repo is worse than none."""
#    items = mtb.collect()[:4]
#    text = mtb.build("pear_bundle.py", items=items, total_files=len(items))
#    lines = text.split("\n")
#    out = tmp_path / "cut.py"
#    out.write_text("\n".join(lines[:lines.index(mtb.SENTINEL)]) + "\n",
#                   encoding="utf-8", newline="\n")
#    r = subprocess.run([sys.executable, str(out), "--dest", str(tmp_path / "x")],
#                       cwd=str(tmp_path), stdout=subprocess.PIPE,
#                       stderr=subprocess.STDOUT)
#    assert r.returncode == 2
#    assert "截斷" in r.stdout.decode("utf-8", "replace")
#
#
#@needs_git
#def test_tampered_file_is_caught_by_its_sha(tmp_path):
#    items = [("a.txt", b"hello\nworld"), ("b.txt", b"second")]
#    text = mtb.build("pear_bundle.py", items=items, total_files=2)
#    # flip a character inside the data region, leaving the SHA header alone
#    text = text.replace("#hello", "#hellO")
#    out = tmp_path / "bad.py"
#    out.write_text(text, encoding="utf-8", newline="\n")
#    r = subprocess.run([sys.executable, str(out), "--dest", str(tmp_path / "x")],
#                       cwd=str(tmp_path), stdout=subprocess.PIPE,
#                       stderr=subprocess.STDOUT)
#    assert r.returncode == 1
#    assert "a.txt" in r.stdout.decode("utf-8", "replace")
#    # the good file still landed; only the damaged one is withheld
#    assert (tmp_path / "x" / "b.txt").read_bytes() == b"second"
#    assert not (tmp_path / "x" / "a.txt").exists()
#
#
#@needs_git
#def test_bundle_excludes_itself():
#    """Otherwise each build packs the previous build — exponentially."""
#    assert not any(rel.startswith("bundle/") for rel, _d in mtb.collect())
#
#
#def test_data_lines_stay_valid_python():
#    """Every data line is commented out, so the bundle still compiles."""
#    body = mtb._data_lines([("x.py", b"def f(:\n  \xe3\x80\x8c oops")])
#    compile("\n".join(body), "<bundle>", "exec")     # would raise if bare
#
#
## --------------------------------------------------------------------------- #
## The Windows one-click install travels in the same bundle
## --------------------------------------------------------------------------- #
#ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#
#
#@pytest.mark.parametrize("name", ["install.bat", "PEAR.bat"])
#def test_batch_files_survive_lf_line_endings(name):
#    """The bundle only carries LF, and cmd.exe is unreliable with LF blocks.
#
#    So both batch files have to stay flat: no parenthesised blocks, no goto,
#    no labels — the constructs that actually misbehave when a .bat has Unix
#    line endings. Everything else lives in tools/install_windows.py.
#    """
#    raw = open(os.path.join(ROOT, name), "rb").read()
#    assert b"\r\n" not in raw               # the bundle would refuse it
#    text = raw.decode("utf-8")
#    assert text.startswith("@echo off")
#    for line in text.splitlines():
#        bare = line.strip().lower()
#        if bare.startswith("rem "):
#            continue
#        assert "goto" not in bare, line
#        assert not bare.endswith("("), line   # a block start
#        assert not bare.startswith(":"), line  # a label
#
#
#def test_install_bat_delegates_to_the_python_installer():
#    text = open(os.path.join(ROOT, "install.bat"), encoding="utf-8").read()
#    assert "tools\\install_windows.py" in text
#    assert "%~dp0" in text                    # works from any working directory
#    assert "pause" in text                    # the window must not vanish
#    launcher = open(os.path.join(ROOT, "PEAR.bat"), encoding="utf-8").read()
#    assert "pythonw" in launcher              # no console window behind the app
#    assert ".venv" in launcher and "-m pear" in launcher
#
#
#def test_installer_and_icon_are_importable_off_windows():
#    """They are plain modules — a syntax error must not wait for a fab PC."""
#    sys.path.insert(0, ROOT)
#    import tools.install_windows as inst
#    import tools.make_icon as icon
#
#    assert inst.MODULES and os.path.basename(inst.VENV) == ".venv"
#    assert inst.venv_python("/x").endswith("python") or \
#        inst.venv_python("/x").endswith("python.exe")
#    assert icon.SIZES[0] == 16 and icon.SIZES[-1] == 256
#
#F a49ee94bd20d2a8713b762de1a48fed5fc3ede4e 385 tests/test_core.py
#"""Headless core tests (no Qt) for the group/ROI analysis model."""
#
#from __future__ import annotations
#
#import os
#import sys
#
#import numpy as np
#import pytest
#
#sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#
#from examples.make_sample import CELL_H, CELL_W, make_field
#from pear.core.analysis import (ROI, Group, align_rects, attribute_separability,
#                                cell_edges, cohens_d, distribute_rects,
#                                heat_cells, jitter_tolerance,
#                                rois_from_points, rois_to_points,
#                                compute_analysis, grid_between, group_outliers,
#                                group_rois, group_values,
#                                groups_from_json, groups_to_json, heat_color,
#                                group_positions, linear_trend, pixel_hist,
#                                profile_by_position, roi_center, roi_metric,
#                                roi_patch, rois_from_json, rois_to_json,
#                                snapshot, summarize, uniformity)
#from pear.core.attributes import glv_value, metric_label, quantile_of
#
#
#def _bright_dark(img):
#    """Group 'bright' on feature centers, 'dark' on background corners.
#
#    """
#    rid = 1
#    rois = []
#    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
#        rois.append(ROI(rid, "bright", (c * CELL_W + 22, r * CELL_H + 18, 20, 16)))
#        rid += 1
#    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
#        rois.append(ROI(rid, "dark", (c * CELL_W + 3, r * CELL_H + 3, 10, 8)))
#        rid += 1
#    groups = [Group("bright", "Bright", "#0D9488"),
#              Group("dark", "Dark", "#2563EB")]
#    return groups, rois
#
#
#def test_roi_patch_and_metrics():
#    img = make_field()
#    p = roi_patch(img, (22, 18, 20, 16))
#    assert p is not None and p.shape == (16, 20)
#    assert roi_patch(img, (-100, -100, 4, 4)) is None      # fully outside
#    assert abs(glv_value(p, "glv_mean")
#               - roi_metric(img, ROI(1, "g", (22, 18, 20, 16)), "glv_mean")) < 1e-9
#    assert quantile_of("glv_q90") == 90 and metric_label("glv_q90") == "GLV Q90"
#
#
#def test_group_values_distributions_separate():
#    img = make_field()
#    groups, rois = _bright_dark(img)
#    b = summarize(group_values(img, group_rois(rois, "bright"), "glv_mean"))
#    d = summarize(group_values(img, group_rois(rois, "dark"), "glv_mean"))
#    assert b["mean"] - d["mean"] > 50 and b["n"] == 4 and d["n"] == 4
#
#
#def test_profile_by_position_groups_hand_jitter_into_one_point():
#    """A column of ROIs a few pixels apart is one position, not five."""
#    rng = np.random.default_rng(5)
#    px = np.array([40 + c * 90 + int(rng.integers(-3, 4))
#                   for _r in range(5) for c in range(6)], dtype=float)
#    vals = np.array([100.0 + c * 4 for _r in range(5) for c in range(6)])
#    pos, mean = profile_by_position(px, vals)
#    assert pos.size == 6                      # one point per column…
#    assert list(np.diff(pos) > 0) == [True] * 5          # …sorted
#    assert list(mean) == pytest.approx([100, 104, 108, 112, 116, 120])
#    # every ROI still counts: the slot means average their own members
#    assert float(mean.mean()) == pytest.approx(float(vals.mean()))
#    # exact-match grouping is still available, and still sees 23 positions
#    assert profile_by_position(px, vals, tol=0)[0].size == np.unique(px).size
#
#
#def test_grid_between_interpolates_anchor_centers():
#    g = grid_between((20, 20), (200, 140), 2, 3, 28, 28)
#    assert len(g) == 6
#    x0, y0, w0, h0 = g[0]
#    xl, yl, wl, hl = g[-1]
#    assert w0 == 28 and h0 == 28
#    # first ROI centred on the top-left anchor, last on the bottom-right anchor
#    assert abs((x0 + 14) - 20) <= 1 and abs((y0 + 14) - 20) <= 1
#    assert abs((xl + 14) - 200) <= 1 and abs((yl + 14) - 140) <= 1
#
#
#def test_compute_analysis_between_and_within():
#    img = make_field()
#    groups, rois = _bright_dark(img)
#    res = compute_analysis(img, groups, rois, ["glv_mean", "glv_std"],
#                           "between", None)
#    assert res.empty is None
#    assert len(res.charts) == 2 and len(res.charts[0].series) == 2
#    assert len(res.table_rows) == 2
#    second = res.charts[1]
#    assert all(s.values.size == 4 for s in second.series)
#    within = compute_analysis(img, groups, rois, ["glv_mean"], "within", "bright")
#    assert within.empty is None and len(within.charts[0].series) == 1
#
#
#def test_compute_analysis_empty_paths():
#    img = make_field()
#    groups, rois = _bright_dark(img)
#    only_one = [r for r in rois if r.gid == "bright"]
#    assert compute_analysis(img, groups, only_one, ["glv_mean"], "between", None).empty
#    assert compute_analysis(None, groups, rois, ["glv_mean"], "between", None).empty
#    assert compute_analysis(img, groups, rois, [], "between", None).empty
#
#
#def test_group_outliers_flags_within_group():
#    img = make_field()
#    # four ROIs on bright features + one on dark background (the outlier)
#    rois = [ROI(1, "g", (22, 18, 20, 16)),
#            ROI(2, "g", (CELL_W + 22, 18, 20, 16)),
#            ROI(3, "g", (2 * CELL_W + 22, 18, 20, 16)),
#            ROI(4, "g", (22, CELL_H + 18, 20, 16)),
#            ROI(5, "g", (3, 3, 10, 8))]           # dark → outlier in glv_mean
#    out = group_outliers(img, rois, "glv_mean")
#    assert 5 in out and 1 not in out
#    # a group too small for a stable IQR is skipped
#    assert group_outliers(img, rois[:3], "glv_mean") == set()
#
#
#def test_heat_color_ramp_and_clamp():
#    assert heat_color(0.0) == "#2563EB"       # cool end
#    assert heat_color(0.5) == "#F59E0B"       # amber middle
#    assert heat_color(1.0) == "#DC2626"       # warm end
#    assert heat_color(-5) == "#2563EB" and heat_color(9) == "#DC2626"  # clamped
#
#
#def test_separability_and_cohens_d():
#    # well-separated groups → high η² and large |d|
#    a = np.array([10.0, 11, 9, 10, 12])
#    b = np.array([50.0, 51, 49, 52, 48])
#    eta = attribute_separability([a, b])
#    assert eta is not None and eta > 0.9
#    assert abs(cohens_d(a, b)) > 5
#    # identical groups → ~0 separability, d ≈ 0
#    assert attribute_separability([a, a.copy()]) < 0.05
#    assert abs(cohens_d(a, a.copy())) < 1e-9
#    # degenerate inputs
#    assert attribute_separability([a]) is None
#    assert cohens_d([1.0], [2.0, 3.0]) is None
#
#
#def test_pixel_hist_shape_and_counts():
#    counts, edges = pixel_hist(np.full((4, 5), 100, np.uint8), bins=16)
#    assert counts.sum() == 20 and len(edges) == 17
#    assert counts[np.digitize(100, edges) - 1] == 20      # all in one bin
#
#
#def test_compute_analysis_ranking_and_heat():
#    img = make_field()
#    groups, rois = _bright_dark(img)
#    res = compute_analysis(img, groups, rois, ["glv_mean", "glv_std"],
#                           "between", None)
#    # heatmap: 2 groups × 2 metrics
#    assert res.heat is not None
#    assert len(res.heat["values"]) == 2 and len(res.heat["values"][0]) == 2
#    # ranking is sorted by η² desc
#    labels = [r[0] for r in res.ranking]
#    assert len(res.ranking) == 2
#    etas = [r[1] for r in res.ranking if r[1] is not None]
#    assert etas == sorted(etas, reverse=True)
#
#
#def test_roi_points_import_groups_by_colour():
#    """The flat list other tools speak: a colour per box, no groups."""
#    items = [{"color": "#00ffff", "x": 32, "y": 68, "target": True},
#             {"color": "#00ffff", "x": 66, "y": 271, "target": False},
#             {"color": "#ff8800", "x": 100, "y": 68, "target": False}]
#    groups, rois, clamped = rois_from_points(items, 28, 24)
#    assert [(g.gid, g.color) for g in groups] == [("A", "#00ffff"),
#                                                  ("B", "#ff8800")]
#    assert [r.gid for r in rois] == ["A", "A", "B"]
#    assert rois[0].rect == (32, 68, 28, 24)      # x/y is the top-left corner
#    assert [r.rid for r in rois] == [1, 2, 3] and clamped == 0
#    # a file with its own sizes keeps them; ids continue from where asked
#    sized = rois_from_points([{"color": "#00ffff", "x": 5, "y": 6,
#                               "w": 40, "h": 12}], 28, 24, start_rid=7)[1]
#    assert sized[0].rect == (5, 6, 40, 12) and sized[0].rid == 7
#
#
#def test_roi_points_clamp_to_the_image_and_report_it():
#    """A list written against a different image must say so, not drift off."""
#    items = [{"color": "#00ffff", "x": 10, "y": 10},
#             {"color": "#00ffff", "x": 900, "y": 900}]
#    _g, rois, clamped = rois_from_points(items, 28, 24, bounds=(768, 468))
#    assert clamped == 1
#    for x, y, w, h in (r.rect for r in rois):
#        assert 0 <= x and x + w <= 768 and 0 <= y and y + h <= 468
#
#
#def test_roi_points_round_trip_and_reject_rubbish():
#    groups, rois, _c = rois_from_points(
#        [{"color": "#00ffff", "x": 1, "y": 2, "w": 9, "h": 8},
#         {"color": "#ff8800", "x": 3, "y": 4, "w": 5, "h": 6}], 28, 24)
#    out = rois_to_points(groups, rois)
#    assert out == [{"color": "#00ffff", "x": 1, "y": 2, "w": 9, "h": 8,
#                    "target": False},
#                   {"color": "#ff8800", "x": 3, "y": 4, "w": 5, "h": 6,
#                    "target": False}]
#    again = rois_from_points(out, 1, 1)[1]
#    assert [r.rect for r in again] == [r.rect for r in rois]
#
#    with pytest.raises(ValueError):
#        rois_from_points({"x": 1}, 10, 10)               # not a list
#    with pytest.raises(ValueError):
#        rois_from_points([{"color": "#fff"}], 10, 10)    # no position
#    with pytest.raises(ValueError):
#        rois_from_points([{"x": "left", "y": 3}], 10, 10)
#
#
#def test_project_model_roundtrip():
#    groups, rois = _bright_dark(make_field())
#    g2 = groups_from_json(groups_to_json(groups))
#    r2 = rois_from_json(rois_to_json(rois))
#    assert [(g.gid, g.name, g.color) for g in g2] == \
#           [(g.gid, g.name, g.color) for g in groups]
#    assert r2[0].rect == rois[0].rect and r2[0].rid == rois[0].rid
#    assert isinstance(r2[0].rect, tuple)
#
#
#def test_snapshot_isolates_from_mutation():
#    groups, rois = _bright_dark(make_field())
#    gs, rs = snapshot(groups, rois)
#    rois[0].rect = (0, 0, 1, 1)
#    groups[0].name = "changed"
#    assert rs[0].rect != (0, 0, 1, 1) and gs[0].name == "Bright"
#
#
#def test_roi_center_and_group_positions():
#    rois = [ROI(1, "g", (10, 20, 10, 10)), ROI(2, "g", (30, 20, 10, 10))]
#    assert roi_center(rois[0].rect) == (15.0, 25.0)
#    assert list(group_positions(rois, "x")) == [15.0, 35.0]
#    assert list(group_positions(rois, "y")) == [25.0, 25.0]
#    # anything but "y" means the X axis
#    assert list(group_positions(rois, "X")) == [15.0, 35.0]
#
#
#def test_align_rects_pulls_onto_one_edge():
#    r = [(10, 10, 10, 10), (13, 40, 10, 10), (9, 70, 12, 12)]
#    assert [x for x, _y, _w, _h in align_rects(r, "left")] == [9, 9, 9]
#    # right aligns the far edges, so a wider box starts further left
#    assert [x + w for x, _y, w, _h in align_rects(r, "right")] == [23, 23, 23]
#    assert [y for _x, y, _w, _h in align_rects(r, "top")] == [10, 10, 10]
#    assert [y + h for _x, y, _w, h in align_rects(r, "bottom")] == [82, 82, 82]
#    centres = [x + w / 2 for x, _y, w, _h in align_rects(r, "hcenter")]
#    assert centres == pytest.approx([16.0, 16.0, 16.0], abs=0.5)
#    assert align_rects(r, "sideways") == r      # unknown mode changes nothing
#    assert align_rects(r[:1], "left") == r[:1]  # one rect has nothing to align
#
#
#def test_distribute_rects_evens_the_gaps():
#    r = [(0, 0, 10, 10), (0, 30, 10, 10), (0, 100, 10, 10)]
#    out = distribute_rects(r, "y")
#    assert [y for _x, y, _w, _h in out] == [0, 50, 100]
#    # order is preserved even when the input is not sorted along the axis
#    r = [(100, 0, 10, 10), (0, 0, 10, 10), (30, 0, 10, 10)]
#    out = distribute_rects(r, "x")
#    assert [x for x, _y, _w, _h in out] == [100, 0, 50]
#    assert distribute_rects(r[:2], "x") == r[:2]      # two rects: no gap to even
#
#
#def test_cell_edges_tile_the_axis_without_gaps():
#    c, e = cell_edges([10.0, 40.0, 70.0, 10.0])   # duplicates are one centre
#    assert list(c) == [10.0, 40.0, 70.0]
#    assert list(e) == pytest.approx([-5.0, 25.0, 55.0, 85.0])
#    # every centre sits inside its own cell and the cells share their edges
#    assert all(e[i] < c[i] < e[i + 1] for i in range(c.size))
#
#
#def test_cell_edges_absorb_rounded_centres_and_uneven_gaps():
#    """Integer ROI rects round the centres — cells must still meet."""
#    c, e = cell_edges([12.0, 31.0, 51.0, 70.0])
#    assert list(np.diff(e)) == pytest.approx([19.0, 19.5, 19.5, 19.0])
#    assert float(e[-1] - e[0]) == pytest.approx(77.0)   # one unbroken span
#    # a missing ROI widens that cell instead of opening a hole
#    c, e = cell_edges([0.0, 10.0, 40.0])
#    assert list(e) == pytest.approx([-5.0, 5.0, 25.0, 55.0])
#
#
#def test_cell_edges_on_degenerate_input():
#    c, e = cell_edges([7.0, 7.0])          # one distinct centre, no neighbour
#    assert list(c) == [7.0] and list(e) == [6.5, 7.5]
#    c, e = cell_edges([])
#    assert c.size == 0 and e.size == 0
#
#
#def test_cell_edges_treat_hand_jitter_as_one_row():
#    """A grid placed by hand wobbles; it must still tile as the grid it is."""
#    rng = np.random.default_rng(3)
#    xs = np.array([40 + c * 90 + int(rng.integers(-3, 4)) + 15
#                   for _r in range(5) for c in range(8)], dtype=float)
#    c, e = cell_edges(xs)
#    assert c.size == 8                       # eight columns, not thirty-four
#    widths = np.diff(e)
#    assert widths.min() > 60                 # no slivers between the knots
#    assert jitter_tolerance(np.unique(xs)) > 3
#    # …but a genuinely uneven layout is left alone
#    assert cell_edges([0.0, 10.0, 40.0])[0].size == 3
#    assert cell_edges(np.array([0.0, 11, 23, 37, 55, 70, 88]))[0].size == 7
#    assert jitter_tolerance(np.array([0.0, 11, 23, 37, 55, 70, 88])) == 0.0
#
#
#def test_heat_cells_tile_the_field_and_clip_to_the_image():
#    rois = [ROI(1, "A", (10, 10, 10, 10)), ROI(2, "A", (50, 10, 10, 10)),
#            ROI(3, "A", (10, 50, 10, 10)), ROI(4, "A", (50, 50, 10, 10))]
#    cells = heat_cells(rois)
#    assert set(cells) == {1, 2, 3, 4}
#    # neighbours share an edge: no gap, no overlap
#    assert cells[1][2] == cells[2][0] == pytest.approx(35.0)
#    assert cells[1][3] == cells[3][1] == pytest.approx(35.0)
#    for r in rois:
#        x0, y0, x1, y1 = cells[r.rid]
#        cx, cy = roi_center(r.rect)
#        assert x0 < cx < x1 and y0 < cy < y1     # the ROI is inside its cell
#    clipped = heat_cells(rois, (60, 60))
#    assert clipped[1][:2] == (0.0, 0.0)          # nothing spills off the image
#    assert clipped[4][2:] == (60.0, 60.0)
#
#
#def test_heat_cells_on_a_single_roi_and_a_single_row():
#    only = heat_cells([ROI(9, "A", (10, 10, 20, 20))])
#    assert only[9] == (10.0, 10.0, 30.0, 30.0)   # no neighbour: its own box
#    row = heat_cells([ROI(1, "A", (0, 0, 10, 10)), ROI(2, "A", (40, 0, 10, 10))])
#    # one row has no Y pitch — the cells borrow the X one and still tile
#    assert row[1][2] == row[2][0] == pytest.approx(25.0)
#    assert row[1][3] - row[1][1] == pytest.approx(40.0)
#    assert heat_cells([]) == {}
#
#
#def test_linear_trend_recovers_a_known_slope():
#    x = np.arange(10, dtype=np.float64)
#    fit = linear_trend(x, 3.0 * x + 7.0)
#    assert fit is not None
#    slope, intercept = fit
#    assert slope == pytest.approx(3.0)
#    assert intercept == pytest.approx(7.0)
#    # a flat profile is slope 0 — the uniform case the tool is built to show
#    flat = linear_trend(x, np.full(10, 5.0))
#    assert flat is not None and flat[0] == pytest.approx(0.0)
#    # degenerate inputs report nothing rather than a bogus tilt
#    assert linear_trend([1.0], [2.0]) is None
#    assert linear_trend([4.0, 4.0, 4.0], [1.0, 2.0, 3.0]) is None
#
#
#def test_uniformity_range_and_cv():
#    u = uniformity([100.0, 110.0, 90.0])
#    assert u["n"] == 3
#    assert u["mean"] == pytest.approx(100.0)
#    assert u["range"] == pytest.approx(20.0)
#    assert u["range_pct"] == pytest.approx(20.0)
#    assert u["cv_pct"] == pytest.approx(np.std([100, 110, 90]) / 100 * 100)
#    # perfectly flat -> zero spread, and no divide-by-zero on an empty set
#    assert uniformity([7.0, 7.0, 7.0])["range"] == 0.0
#    assert uniformity([])["n"] == 0
#    assert uniformity([0.0, 0.0])["range_pct"] == 0.0
#
#
#def test_profile_by_position_averages_shared_positions():
#    # a grid puts several ROIs at the same X; they collapse to one point
#    pos = np.array([10.0, 10.0, 20.0, 20.0])
#    val = np.array([4.0, 6.0, 10.0, 20.0])
#    cx, cy = profile_by_position(pos, val)
#    assert list(cx) == [10.0, 20.0]
#    assert list(cy) == [5.0, 15.0]
#    assert profile_by_position([], [])[0].size == 0
#
#
#def test_compute_analysis_carries_roi_positions():
#    img = make_field()
#    groups = [Group("g1", "A", "#f00"), Group("g2", "B", "#00f")]
#    rois = [ROI(1, "g1", (2, 2, 8, 8)), ROI(2, "g1", (30, 2, 8, 8)),
#            ROI(3, "g2", (2, 30, 8, 8)), ROI(4, "g2", (30, 30, 8, 8))]
#    res = compute_analysis(img, groups, rois, ["glv_mean"], "between", None)
#    s = res.charts[0].series[0]
#    assert s.pos_x is not None and s.pos_y is not None
#    assert s.pos_x.size == s.values.size == 2
#    assert list(s.pos_x) == [6.0, 34.0]
#
#
#F 8a9e7e23cd3ebd7f4d565eaa8a3e3151a4cc0993 1516 tests/test_ui_smoke.py
#"""Offscreen UI smoke test for the group/ROI analysis app."""
#
#from __future__ import annotations
#
#import os
#import sys
#
#os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
#sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#
#import numpy as np
#import pytest
#
#from examples.make_sample import CELL_H, CELL_W, make_field
#
#QtWidgets = pytest.importorskip("PySide6.QtWidgets")
#
#
#@pytest.fixture(scope="module")
#def app():
#    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
#    yield application
#
#
#def _two_groups(win):
#    """Group A on bright centers, Group B on dark corners."""
#    gA = win._active_gid
#    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
#        win.on_roi_created((c * CELL_W + 22, r * CELL_H + 18, 20, 16))
#    win.add_group()
#    gB = win._active_gid
#    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:
#        win.on_roi_created((c * CELL_W + 3, r * CELL_H + 3, 10, 8))
#    return gA, gB
#
#
#def test_boot_seeds_group(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "sample_field.png")
#    assert len(win._groups) == 1 and win._active_gid == "A"
#    assert win._rois == []
#
#
#def test_controls_disabled_before_image(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    assert not win.rail.grp_add_btn.isEnabled()
#    assert not win.rail.grid_btn.isEnabled()
#    assert not win.rail.analysis_btn.isEnabled()
#    assert not win.stage_bar.isEnabled()
#    win.set_image(make_field(), "f.png")
#    assert win.rail.grp_add_btn.isEnabled() and win.rail.grid_btn.isEnabled()
#    assert win.stage_bar.isEnabled()
#
#
#def test_add_rois_to_groups(app):
#    from pear.ui.main_window import MainWindow
#    from pear.core.analysis import group_rois
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gA, gB = _two_groups(win)
#    assert len(group_rois(win._rois, gA)) == 4
#    assert len(group_rois(win._rois, gB)) == 4
#
#
#def test_grid_multi_add(app):
#    from pear.ui.main_window import MainWindow
#    from pear.core.analysis import grid_between, group_rois
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    rects = grid_between((30, 30), (200, 160), 2, 3, 28, 28)   # 2×3 grid
#    win.on_grid_committed(rects)
#    assert len(group_rois(win._rois, win._active_gid)) == 6
#
#
#def test_grid_interaction_two_clicks(app):
#    from PySide6.QtCore import Qt
#    from PySide6.QtGui import QMouseEvent
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    iv = win.image_view
#    iv.resize(500, 400)
#    win.set_grid_mode(True)
#    # two corner clicks define the bounds, then commit
#    p1 = iv._to_widget(30, 30)
#    p2 = iv._to_widget(200, 160)
#    iv.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, p1,
#                                   Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
#    iv.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, p2,
#                                   Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
#    assert iv._grid_stage == 2
#    iv.commit_grid()
#    from pear.core.analysis import group_rois
#    assert len(group_rois(win._rois, win._active_gid)) == win.rail.grid_shape()[0] * \
#        win.rail.grid_shape()[1]
#
#
#def test_between_analysis_and_export(app, tmp_path):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean", "glv_std"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    from pear.ui.widgets import DistributionChart
#    assert win.analysis.body.findChildren(DistributionChart)
#    out = tmp_path / "g.csv"
#    assert win.export_csv(str(out)) == str(out)
#    text = out.read_text(encoding="utf-8-sig")
#    assert "Group A" in text and "GLV mean" in text and "summary" in text
#
#
#def test_within_analysis(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gA, _ = _two_groups(win)
#    win.on_cmp_mode("within")
#    win.on_within_group(gA)
#    win.render_analysis_sync()
#    assert gA in win.analysis.sub.text() or "ROIs" in win.analysis.sub.text()
#
#
#def test_delete_group_removes_its_rois(app):
#    from pear.ui.main_window import MainWindow
#    from pear.core.analysis import group_rois
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gA, gB = _two_groups(win)
#    win.delete_group(gB)
#    assert win._group(gB) is None
#    assert group_rois(win._rois, gB) == []
#    assert len(group_rois(win._rois, gA)) == 4
#
#
#def test_group_gids_unique_after_delete(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.add_group()
#    win.add_group()                       # A, B, C
#    assert [g.gid for g in win._groups] == ["A", "B", "C"]
#    win.delete_group("B")
#    win.add_group()                       # reuses freed "B"
#    gids = [g.gid for g in win._groups]
#    assert len(gids) == len(set(gids)) and set(gids) == {"A", "B", "C"}
#
#
#def test_delete_individual_roi(app):
#    from pear.ui.main_window import MainWindow
#    from pear.core.analysis import group_rois
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.on_roi_created((20, 20, 20, 20))
#    win.on_roi_created((60, 60, 20, 20))
#    gid = win._active_gid
#    assert len(group_rois(win._rois, gid)) == 2
#    rid = win._rois[0].rid
#    win.delete_roi(rid)
#    assert len(group_rois(win._rois, gid)) == 1 and win._roi(rid) is None
#
#
#def test_roi_size_setting_reaches_image_view(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.rail.roi_w.setValue(40)
#    win.rail.roi_h.setValue(30)
#    assert win.image_view._roi_w == 40 and win.image_view._roi_h == 30
#    # a plain click (no drag) drops a box of that size
#    from pear.core.analysis import grid_between
#    # grid also uses the configured size
#    rects = grid_between((30, 30), (200, 160), 2, 2, *win.rail.roi_size())
#    assert rects[0][2] == 40 and rects[0][3] == 30
#
#
#def test_show_metric_on_rois(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.on_roi_created((22, 18, 20, 16))
#    win.on_show_metric("glv_mean")
#    assert win.image_view._roi_values           # one value per ROI
#    win.on_show_metric("")
#    assert win.image_view._roi_values == {}
#
#
#def test_color_and_rename(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gA = win._active_gid
#    win.set_group_color(gA, "#123456")
#    win.rename_group(gA, "round holes")
#    assert win._group(gA).color == "#123456"
#    assert win._group(gA).name == "round holes"
#
#
#def test_roi_labels_reindex_after_delete(app):
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.on_roi_created((20, 20, 16, 16))
#    win.on_roi_created((60, 20, 16, 16))
#    win.on_roi_created((100, 20, 16, 16))
#    gid = win._active_gid
#    mid_rid = group_rois(win._rois, gid)[1].rid
#    win.delete_roi(mid_rid)
#    assert [r.label for r in group_rois(win._rois, gid)] == ["ROI 1", "ROI 2"]
#
#
#def test_marquee_select_and_batch_delete(app):
#    from PySide6.QtCore import Qt
#    from PySide6.QtGui import QMouseEvent
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    iv = win.image_view
#    iv.resize(500, 400)
#    win.on_roi_created((20, 20, 16, 16))
#    win.on_roi_created((60, 20, 16, 16))
#    win.on_roi_created((120, 20, 16, 16))
#    gid = win._active_gid
#    p1 = iv._to_widget(10, 10)
#    p2 = iv._to_widget(90, 60)                    # covers the first two only
#    iv.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, p1,
#                                   Qt.LeftButton, Qt.LeftButton, Qt.ShiftModifier))
#    iv.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, p2,
#                                  Qt.NoButton, Qt.LeftButton, Qt.ShiftModifier))
#    iv.mouseReleaseEvent(QMouseEvent(QMouseEvent.Type.MouseButtonRelease, p2,
#                                     Qt.LeftButton, Qt.NoButton, Qt.ShiftModifier))
#    assert len(win._selected_rids) == 2
#    win.delete_rois(list(win._selected_rids))
#    assert len(group_rois(win._rois, gid)) == 1
#
#
#def test_heatmap_and_outliers_state(app):
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    for (r, c) in [(0, 0), (1, 1), (2, 2), (3, 3)]:      # bright features
#        win.on_roi_created((c * CELL_W + 22, r * CELL_H + 18, 20, 16))
#    win.on_roi_created((3, 3, 10, 8))                    # dark → outlier
#    gid = win._active_gid
#    dark_rid = group_rois(win._rois, gid)[-1].rid
#    win.on_show_metric("glv_mean")
#    win.on_heatmap(True)
#    win.on_flag_outliers(True)
#    assert win.image_view._heat and win.image_view._heat_legend is not None
#    assert dark_rid in win.image_view._outliers
#    win.on_heatmap(False)
#    win.on_flag_outliers(False)
#    assert win.image_view._heat == {} and win.image_view._outliers == set()
#
#
#def test_keyboard_nudge_duplicate_group_switch(app):
#    from PySide6.QtCore import Qt
#    from PySide6.QtGui import QKeyEvent
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.on_roi_created((40, 40, 20, 20))
#    iv = win.image_view
#    rid = win._active_rid
#    x0 = win._roi(rid).rect[0]
#    iv.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Right, Qt.NoModifier))
#    assert win._roi(rid).rect[0] == x0 + 1
#    iv.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Right,
#                              Qt.ShiftModifier))
#    assert win._roi(rid).rect[0] == x0 + 11
#    n = len(group_rois(win._rois, win._active_gid))
#    win.duplicate_roi(rid)
#    assert len(group_rois(win._rois, win._active_gid)) == n + 1
#    win.add_group()                                   # A, B (active B)
#    win.select_group_by_index(0)
#    assert win._active_gid == "A"
#
#
#def test_hover_sync_state(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.on_roi_created((40, 40, 20, 20))
#    rid = win._active_rid
#    win.image_view.set_hover(rid)
#    assert win.image_view._hover_rid == rid
#    win.image_view.set_hover(-1)
#    assert win.image_view._hover_rid == -1
#    win.rail.set_hovered_roi(rid)                     # canvas → list, no crash
#
#
#def test_chart_option_toggles(app):
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    ap = win.analysis
#    ap._pick_ctype("hist")
#    ap._pick_ctype("box")
#    ap.points_chk.setChecked(False)
#    ap.whiskers_chk.setChecked(False)
#    app.processEvents()          # flush deleteLater so stale charts are gone
#    charts = ap.body.findChildren(DistributionChart)
#    assert any(not c._opts["points"] and not c._opts["whiskers"]
#               for c in charts)
#
#
#def test_ranking_and_heatmap_render(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean", "glv_std"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    res = win.analysis._last_result
#    assert res.ranking and res.heat is not None
#    assert len(res.heat["values"]) == 2
#
#
#def test_roi_inspector_shows_patch(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.on_roi_created((22, 18, 20, 16))
#    win.open_inspector(win._active_rid)
#    assert win.inspector_window.isVisible()
#    assert win.inspector._patch is not None
#    assert win.inspector._patch.shape == (16, 20)
#    win.on_roi_created((3, 3, 10, 8))                 # inspector tracks active ROI
#    win.select_roi(win._active_rid)
#    assert win.inspector._patch.shape == (8, 10)
#
#
#def test_project_save_open_roundtrip(app, tmp_path):
#    import cv2
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    ipath = tmp_path / "field.png"
#    cv2.imwrite(str(ipath), make_field())
#    win = MainWindow()
#    win.load_path(str(ipath))
#    win.rename_group(win._active_gid, "round holes")
#    win.on_roi_created((22, 18, 20, 16))
#    win.on_roi_created((3, 3, 10, 8))
#    win.set_metrics(["glv_mean", "glv_std"])
#    proj = tmp_path / "p.pear.json"
#    assert win.save_project(str(proj)) == str(proj)
#
#    win2 = MainWindow()
#    assert win2.open_project(str(proj)) == str(proj)
#    assert win2._image is not None
#    assert win2._group("A").name == "round holes"
#    a_rois = group_rois(win2._rois, "A")
#    assert len(a_rois) == 2
#    assert win2._metrics == ["glv_mean", "glv_std"]
#
#
#def _grid_group(win, rows=3, cols=4):
#    """A group whose ROIs tile the field, so positions vary on both axes."""
#    from pear.core.analysis import grid_between
#    win.add_group()
#    for r in grid_between((14, 12), (110, 70), rows, cols, 8, 8):
#        win.on_roi_created(r)
#    return win._active_gid
#
#
#def test_position_profile_and_heatmap_render(app):
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gid = _grid_group(win)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("within")
#    win.on_within_group(gid)
#    win.render_analysis_sync()
#    ap = win.analysis
#
#    for ctype in ("position", "map"):
#        ap._pick_ctype(ctype)
#        app.processEvents()
#        charts = [c for c in ap.body.findChildren(DistributionChart)
#                  if c._ctype == ctype]
#        assert charts, f"no {ctype} chart rendered"
#        c = charts[0]
#        assert c._series and c._series[0]["pos_x"].size == len(win._rois)
#        assert c._series[0]["pos_y"].size == len(win._rois)
#        c.grab()                       # exercises the painter
#    # the axis toggle is render-only: no recompute, positions are already there
#    ap._pick_ctype("position")
#    ap.axis_box.setCurrentIndex(1)
#    app.processEvents()
#    assert ap.chart_state() == ("position", "y")
#    for c in ap.body.findChildren(DistributionChart):
#        c.grab()
#
#
#def test_rebuilt_lists_leave_no_stale_rows(app):
#    """A rebuilt list must not keep painting its old rows over the card.
#
#    ``deleteLater`` alone leaves them visible until the event loop runs, and
#    they cover the Groups card's title and Add button while they linger. They
#    must be *hidden*, not reparented: these lists are rebuilt from their own
#    rows' signals, and a widget reparented to None mid-event becomes a stray
#    top-level window and then a crash.
#    """
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import _ItemRow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.add_group()
#    win.on_roi_created((10, 10, 12, 12))
#    win.on_roi_created((40, 10, 12, 12))
#    for _ in range(3):
#        win._refresh()                       # no processEvents in between
#    grp_card = win.rail.grp_add_btn.parentWidget()
#
#    def live(host):
#        return [r for r in host.findChildren(_ItemRow) if not r.isHidden()]
#
#    assert len(live(grp_card)) == len(win._groups)
#    roi_rows = len(group_rois(win._rois, win._active_gid))
#    assert len(live(win.rail.roi_host.parentWidget())) == roi_rows
#    # nothing was turned into a window on the way out
#    assert all(r.parentWidget() is not None
#               for r in grp_card.findChildren(_ItemRow))
#
#    # a row's own click rebuilds the list it lives in — the path that used to
#    # flash a blank window per click and then take the app down
#    rid = group_rois(win._rois, win._active_gid)[0].rid
#    for _ in range(5):
#        win.select_roi(rid)
#        win.rail.set_hovered_roi(rid)
#    app.processEvents()
#    assert len(live(win.rail.roi_host.parentWidget())) == roi_rows
#
#
#def test_value_labels_only_where_they_fit(app):
#    """A label wider than its ROI is dropped — unless that ROI is hovered."""
#    from PySide6.QtCore import QRectF
#    from pear.ui.image_view import label_rect
#    big, small = QRectF(0, 40, 60, 20), QRectF(0, 40, 8, 6)
#    inside = label_rect(big, 30, 12, False)
#    assert inside is not None and big.contains(inside)
#    assert label_rect(small, 30, 12, False) is None      # would bury the box
#    floated = label_rect(small, 30, 12, True)            # hovered: float it
#    assert floated is not None and floated.bottom() <= small.top()
#    # an ROI at the very top has no room above — the label goes below instead
#    at_top = label_rect(QRectF(0, 0, 8, 6), 30, 12, True)
#    assert at_top is not None and at_top.top() >= 6
#
#
#def test_fit_survives_a_resize_until_the_user_zooms(app):
#    """set_image() fits against the layout's first guess at the widget size."""
#    from pear.ui.image_view import ImageView
#    iv = ImageView()
#    iv.resize(320, 240)                       # the "first guess"
#    iv.show()                                 # hidden widgets defer resizes
#    app.processEvents()
#    iv.set_image(make_field())
#    small = iv._scale
#    iv.resize(900, 700)                       # …then the real one
#    app.processEvents()
#    assert iv._fitted and iv._scale > small
#    pm = iv._pixmap
#    assert iv._offset.x() == pytest.approx(
#        (iv.width() - pm.width() * iv._scale) / 2.0, abs=1.0)
#    assert iv._offset.y() == pytest.approx(
#        (iv.height() - pm.height() * iv._scale) / 2.0, abs=1.0)
#    iv.zoom_in()
#    assert not iv._fitted
#    scale, off = iv._scale, iv._offset
#    iv.resize(700, 500)
#    app.processEvents()
#    assert iv._scale == scale and iv._offset == off       # a zoom is not undone
#
#
#def test_stage_bar_drives_the_overlays_and_the_field_fill(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _grid_group(win, 3, 3)
#    sb = win.stage_bar
#    assert not sb.alpha_spin.isEnabled()             # nothing painted yet
#    sb.show_combo.setCurrentIndex(sb.show_combo.findData("glv_mean"))
#    assert win._show_metric == "glv_mean" and win.image_view._roi_values
#
#    # the field paints on its own — it does not wait for "heat boxes"
#    sb.cells_chk.setChecked(True)
#    assert sb.alpha_spin.isEnabled() and win.image_view._heat
#    cells = win.image_view._heat_cells
#    assert len(cells) == len(win._rois)
#    h, w = make_field().shape[:2]
#    for x0, y0, x1, y1 in cells.values():            # clipped to the image
#        assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
#
#    sb.cells_chk.setChecked(False)                   # …and boxes on their own
#    assert win.image_view._heat == {} and win.image_view._heat_cells == {}
#    sb.heatmap_chk.setChecked(True)
#    assert win.image_view._heat and win.image_view._heat_cells == {}
#    sb.heatmap_chk.setChecked(False)
#    assert win.image_view._heat == {} and not sb.alpha_spin.isEnabled()
#
#
#def test_roi_list_shows_and_sorts_by_the_shown_metric(app):
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gid = _grid_group(win, 2, 3)
#    win.stage_bar.show_combo.setCurrentIndex(
#        win.stage_bar.show_combo.findData("glv_mean"))
#    rois = group_rois(win._rois, gid)
#    assert len(win._values) == len(rois)
#
#    def order(mode):
#        win.on_roi_order(mode)
#        return [r.rid for r in win._ordered_rois(rois)]
#
#    assert order("placed") == [r.rid for r in rois]
#    asc = order("asc")
#    assert [win._values[r] for r in asc] == sorted(win._values[r] for r in asc)
#    assert order("desc") == asc[::-1]
#
#
#def test_status_bar_carries_the_headline_numbers(app):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _grid_group(win, 2, 3)
#    text = win.summary_lbl.text()
#    assert f"{len(win._groups)} groups" in text and "6 ROIs" in text
#    win.stage_bar.show_combo.setCurrentIndex(
#        win.stage_bar.show_combo.findData("glv_mean"))
#    text = win.summary_lbl.text()
#    assert "GLV mean" in text and "CV" in text and "range" in text
#
#
#def test_box_chart_can_give_each_group_its_own_scale(app):
#    """A group with a tiny spread beside a distant one is flat on one axis."""
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    ap = win.analysis
#    ap._pick_ctype("box")
#    app.processEvents()
#    assert not ap.ownscale_chk.isHidden()
#    ap.ownscale_chk.setChecked(True)
#    app.processEvents()
#    charts = [c for c in ap.body.findChildren(DistributionChart)
#              if c._opts.get("own_scale")]
#    assert charts
#    for c in charts:
#        c.grab()                       # exercises the per-lane painter
#    ap._pick_ctype("map")              # only the box plot offers it
#    assert ap.ownscale_chk.isHidden()
#
#
#def test_import_and_export_rois(app, tmp_path):
#    """A ROI layout worked out elsewhere drops straight in, and comes back."""
#    import json
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    src = tmp_path / "rois.json"
#    src.write_text(json.dumps(
#        [{"color": "#00ffff", "x": 32, "y": 68, "target": True},
#         {"color": "#00ffff", "x": 66, "y": 271, "target": False},
#         {"color": "#ff8800", "x": 100, "y": 68, "target": False}]),
#        encoding="utf-8")
#
#    assert win.import_rois(str(src), mode="replace", ask_size=False) == 3
#    assert len(win._rois) == 3
#    colors = sorted(g.color for g in win._groups)
#    assert colors == ["#00ffff", "#ff8800"]          # a group per colour
#    cyan = [g for g in win._groups if g.color == "#00ffff"][0]
#    assert len(group_rois(win._rois, cyan.gid)) == 2
#    w, h = win.rail.roi_size()
#    assert win._rois[0].rect == (32, 68, w, h)       # size comes from the rail
#    assert win.image_view._rois == win._rois         # and it is on the canvas
#
#    # adding keeps what is there and reuses the group that already has that
#    # colour, rather than making a second cyan group
#    assert win.import_rois(str(src), mode="add", ask_size=False) == 3
#    assert len(win._rois) == 6 and len(win._groups) == 2
#    assert len({r.rid for r in win._rois}) == 6      # rids stay unique
#
#    out = tmp_path / "out.json"
#    assert win.export_rois(str(out), ask_size=False) == str(out)
#    items = json.loads(out.read_text(encoding="utf-8"))
#    assert len(items) == 6
#    assert set(items[0]) == {"color", "x", "y", "w", "h", "target"}
#    assert items[0]["x"] == 32 and items[0]["color"] == "#00ffff"
#
#    win2 = MainWindow()
#    win2.set_image(make_field(), "f.png")
#    assert win2.import_rois(str(out), mode="replace", ask_size=False) == 6
#    assert [r.rect for r in win2._rois] == [r.rect for r in win._rois]
#
#
#def test_roi_size_dialog_drives_import_and_export(app, tmp_path):
#    """Both ends can override the box size; export can omit it entirely."""
#    import json
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import RoiSizeDialog
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    src = tmp_path / "in.json"
#    src.write_text(json.dumps([{"color": "#00ffff", "x": 10, "y": 12,
#                                "w": 99, "h": 98}]), encoding="utf-8")
#
#    # the icon buttons are what the rail offers now
#    assert win.rail.roi_import_btn.text() == ""
#    assert not win.rail.roi_import_btn.icon().isNull()
#    assert not win.rail.roi_export_btn.icon().isNull()
#
#    dlg = RoiSizeDialog(None, "import", 28, 24)
#    assert dlg.options()["size"] is None           # the file's own size wins
#    dlg.custom_radio.setChecked(True)
#    dlg.w_spin.setValue(40)
#    dlg.h_spin.setValue(30)
#    assert dlg.options()["size"] == (40, 30)
#
#    assert win.import_rois(str(src), mode="replace", size=(40, 30)) == 1
#    assert win._rois[0].rect == (10, 12, 40, 30)   # not the file's 99×98
#    assert win.import_rois(str(src), mode="replace", ask_size=False) == 1
#    assert win._rois[0].rect == (10, 12, 99, 98)   # the file's, when not asked
#
#    out = tmp_path / "out.json"
#    win.export_rois(str(out), size=(7, 8), ask_size=False)
#    assert json.loads(out.read_text(encoding="utf-8"))[0]["w"] == 7
#
#    bare = tmp_path / "bare.json"
#    win.export_rois(str(bare), include_size=False, ask_size=False)
#    item = json.loads(bare.read_text(encoding="utf-8"))[0]
#    assert set(item) == {"color", "x", "y", "target"}   # the other tool's shape
#
#    ex = RoiSizeDialog(None, "export", 28, 24, count=3)
#    ex.include_chk.setChecked(False)                    # gates the size choice
#    assert not ex.own_radio.isEnabled() and not ex.w_spin.isEnabled()
#    assert ex.options()["include_size"] is False
#
#
#def test_import_rois_reports_a_bad_file(app, tmp_path, monkeypatch):
#    from PySide6.QtWidgets import QMessageBox
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    seen = []
#    monkeypatch.setattr(QMessageBox, "warning",
#                        lambda *a, **k: seen.append(a[-1]))
#    bad = tmp_path / "bad.json"
#    bad.write_text("{not json", encoding="utf-8")
#    assert win.import_rois(str(bad), mode="replace", ask_size=False) is None
#    empty = tmp_path / "empty.json"
#    empty.write_text("[]", encoding="utf-8")
#    assert win.import_rois(str(empty), mode="replace", ask_size=False) is None
#    assert len(seen) == 2 and win._rois == []
#    assert win.export_rois(str(tmp_path / "none.json"), ask_size=False) is None
#
#
#def test_align_buttons_tidy_the_selection_then_the_group(app):
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.add_group()
#    for rect in ((10, 10, 10, 10), (13, 40, 10, 10), (9, 100, 10, 10)):
#        win.on_roi_created(rect)
#    rois = group_rois(win._rois, win._active_gid)
#
#    win._selected_rids = {rois[0].rid, rois[1].rid}   # only the selection moves
#    win.rail.align_btns["left"].click()
#    assert [r.rect[0] for r in rois] == [10, 10, 9]
#
#    win._selected_rids = set()                        # …then the whole group
#    win.rail.align_btns["left"].click()
#    assert [r.rect[0] for r in rois] == [9, 9, 9]
#    win.rail.align_btns["disty"].click()
#    assert [r.rect[1] for r in rois] == [10, 55, 100]  # gaps evened out
#    before = [r.rect for r in rois]
#    win.rail.align_btns["left"].click()                # already aligned: no-op
#    assert [r.rect for r in rois] == before
#
#
#def test_map_draws_touching_cells_and_optional_values(app):
#    """Cell mode tiles the field; the dot fallback and labels still paint."""
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gid = _grid_group(win)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("within")
#    win.on_within_group(gid)
#    win.render_analysis_sync()
#    ap = win.analysis
#    ap._pick_ctype("map")
#    app.processEvents()
#    assert not ap.cells_chk.isHidden() and not ap.mapval_chk.isHidden()
#
#    def maps():
#        # a re-render leaves the previous charts pending deleteLater, so match
#        # any live one rather than assuming which comes first
#        return [c for c in ap.body.findChildren(DistributionChart)
#                if c._ctype == "map"]
#
#    assert any(c._opts["cells"] for c in maps())
#    ap.mapval_chk.setChecked(True)             # values printed inside the cells
#    app.processEvents()
#    assert any(c._opts["map_values"] for c in maps())
#    for c in maps():
#        c.grab()
#    ap.cells_chk.setChecked(False)             # back to separate dots
#    app.processEvents()
#    assert not ap.mapval_chk.isEnabled()
#    dots = [c for c in maps() if not c._opts["cells"]]
#    assert dots
#    for c in dots:
#        c.grab()
#        # the toggles are render-only — the position data is untouched
#        assert c._series[0]["pos_x"].size == len(win._rois)
#
#
#def test_heat_map_lattice_gives_every_cell_the_same_size(app):
#    """Uneven pitch must not hand neighbouring cells different areas."""
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.add_group()
#    gid = win._active_gid
#    for row, y in enumerate((20, 90, 200)):          # deliberately uneven rows
#        for col, x in enumerate((20, 60, 200, 260)): # …and uneven columns
#            win.on_roi_created((x, y, 16, 14))
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("within")
#    win.on_within_group(gid)
#    win.render_analysis_sync()
#    ap = win.analysis
#    ap._pick_ctype("map")
#    app.processEvents()
#    assert not ap.equal_chk.isHidden() and ap.equal_chk.isChecked()
#
#    def maps():
#        return [c for c in ap.body.findChildren(DistributionChart)
#                if c._ctype == "map"]
#
#    assert any(c._opts["equal_cells"] for c in maps())
#    for c in maps():
#        c.grab()                       # exercises the lattice painter
#    ap.equal_chk.setChecked(False)     # back to true midline tiling
#    app.processEvents()
#    assert any(not c._opts["equal_cells"] for c in maps())
#    for c in maps():
#        c.grab()
#    ap.cells_chk.setChecked(False)     # dots have no area to equalise
#    assert not ap.equal_chk.isEnabled()
#
#
#def test_overlay_toggles_are_independent(app, tmp_path):
#    """Value text, heat fill and its opacity switch one at a time."""
#    import json
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _grid_group(win, 2, 3)
#    win.on_show_metric("glv_mean")
#    assert win.image_view._roi_values                 # numbers on by default
#    win.on_heatmap(True)
#    win.on_show_values(False)                         # colour only, no numbers
#    assert win.image_view._heat and win.image_view._roi_values == {}
#    win.on_heat_alpha(30)
#    assert win.image_view._heat_alpha == round(30 * 2.55)
#    win.on_show_values(True)
#    assert win.image_view._roi_values
#
#    win.on_show_values(False)
#    win.on_heat_field(True)
#    win.on_roi_order("desc")
#    out = tmp_path / "p.pear.json"
#    win.save_project(str(out))
#    win2 = MainWindow()
#    win2.set_image(make_field(), "f.png")
#    win2._restore_project(json.loads(out.read_text(encoding="utf-8")))
#    assert win2._show_values is False and win2._heat_alpha == 30
#    assert win2._heat_field is True and win2._roi_order == "desc"
#    assert win2.stage_bar.cells_chk.isChecked()
#    assert win2.rail.order_box.currentData() == "desc"
#    assert win2.stage_bar.alpha_spin.value() == 30
#    assert win2.image_view._roi_values == {}
#    assert win2.image_view._heat_alpha == round(30 * 2.55)
#
#
#def test_nice_step_lands_on_round_numbers():
#    from pear.ui.widgets import _nice_step
#    assert _nice_step(30, 4) == 10.0            # 0 · 10 · 20 · 30, not 7.5
#    assert _nice_step(100, 4) == 25.0
#    assert _nice_step(8, 4) == 2.0
#    assert _nice_step(0.4, 4) == 0.1
#    assert _nice_step(0, 4) == 1.0              # degenerate input never breaks
#    assert _nice_step(float("nan"), 4) == 1.0
#
#
#def test_histogram_bins_and_percent_are_render_only(app):
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    ap = win.analysis
#    ap._pick_ctype("hist")
#    app.processEvents()
#    assert not ap.bins_spin.isHidden() and not ap.pct_chk.isHidden()
#    ap.bins_spin.setValue(12)
#    ap.pct_chk.setChecked(True)
#    app.processEvents()
#    hists = [c for c in ap.body.findChildren(DistributionChart)
#             if c._ctype == "hist" and c._opts.get("bins") == 12]
#    assert hists and hists[-1]._opts["hist_pct"] is True
#    for c in hists:
#        c.grab()                       # exercises the percent painter
#    ap._pick_ctype("box")              # bins/% belong to the histogram alone
#    assert ap.bins_spin.isHidden() and ap.pct_chk.isHidden()
#
#
#def test_distribution_charts_keep_a_printable_shape(app):
#    """A figure at 4:3-ish, not a banner stretched across the window."""
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    win.analysis_window.resize(1400, 900)
#    win.analysis_window.show()
#    win.analysis._pick_ctype("hist")
#    app.processEvents()
#    app.processEvents()
#    charts = [c for c in win.analysis.body.findChildren(DistributionChart)
#              if c._ctype == "hist" and c.isVisible()]
#    assert charts
#    c = charts[-1]
#    assert 340 <= c.width() <= 720                     # capped, not stretched
#    assert c.height() == pytest.approx(c.heightForWidth(c.width()), abs=2)
#    # a profile runs the full width, so it needs a ratio of its own or it
#    # comes out as a letterbox where a tilt and a flat line look alike
#    win.analysis._pick_ctype("position")
#    app.processEvents()
#    app.processEvents()
#    prof = [c for c in win.analysis.body.findChildren(DistributionChart)
#            if c._ctype == "position" and c.isVisible()]
#    assert prof
#    c = prof[-1]
#    assert c.hasHeightForWidth()
#    assert c.height() >= 300 and c.height() >= c.width() * 0.5
#
#
#def test_chart_settings_rename_relabel_and_lock_the_scales(app, tmp_path):
#    """Titles, axis names, tick counts and locked ranges — and they persist."""
#    import json
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import ChartSettingsDialog, DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean", "glv_median"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    ap = win.analysis
#    ap._pick_ctype("hist")
#    app.processEvents()
#
#    dlg = ChartSettingsDialog(None, ["GLV mean", "GLV median"], ap.chart_style())
#    dlg._title_edits["GLV mean"].setText("Figure 1 — layer brightness")
#    dlg.x_edit.setText("grey level (DN)")
#    dlg.y_edit.setText("ROIs")
#    dlg.xt_spin.setValue(7)
#    dlg.yt_spin.setValue(4)
#    dlg.v_auto.setChecked(False)
#    dlg.v_lo.setValue(50.0)
#    dlg.v_hi.setValue(200.0)
#    style = dlg.result_style()
#    assert style["titles"] == {"GLV mean": "Figure 1 — layer brightness"}
#    assert style["xticks"] == 7 and style["yticks"] == 4
#    assert (style["vmin"], style["vmax"]) == (50.0, 200.0)
#
#    ap.set_chart_style(style)
#    app.processEvents()
#    charts = [c for c in ap.body.findChildren(DistributionChart)
#              if c._ctype == "hist" and c._title == "GLV mean"]
#    assert charts
#    c = charts[-1]
#    assert c.title_text() == "Figure 1 — layer brightness"
#    # the other chart keeps its own name; only the axes are shared
#    other = [x for x in ap._chart_widgets if x._title == "GLV median"][0]
#    assert other.title_text() == "GLV median"
#    assert c._st("xlabel") == "grey level (DN)"
#    assert c._range() == (50.0, 200.0)          # locked, not the data's range
#    assert c._nticks("xticks", 5) == 7
#    c.grab()                                     # the painter honours all of it
#    # the export menu follows the new name
#    assert any("Figure 1" in a.text() for a in ap._image_menu.actions())
#
#    out = tmp_path / "p.pear.json"
#    win.save_project(str(out))
#    win2 = MainWindow()
#    win2.set_image(make_field(), "f.png")
#    win2._restore_project(json.loads(out.read_text(encoding="utf-8")))
#    assert win2.analysis.chart_style()["titles"]["GLV mean"].startswith("Figure 1")
#    assert win2.analysis.chart_style()["vmax"] == 200.0
#
#    dlg._reset()                                 # Reset clears every override
#    assert dlg.result_style() == {"xticks": 5, "yticks": 5, "font_pt": 8.0,
#                                  "label_pt": 8.0, "tick_bold": False,
#                                  "label_bold": True, "point_size": 3.2,
#                                  "line_width": 2.2}
#
#
#def test_locked_scales_reach_the_profile_and_the_map(app):
#    """The value lock was a histogram-only thing; every chart honours it now."""
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import ChartSettingsDialog
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gid = _grid_group(win, 3, 4)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("within")
#    win.on_within_group(gid)
#    win.render_analysis_sync()
#    ap = win.analysis
#
#    dlg = ChartSettingsDialog(None, ["GLV mean"], {})
#    dlg.v_auto.setChecked(False)
#    dlg.v_lo.setValue(40.0)
#    dlg.v_hi.setValue(210.0)
#    dlg.x_auto.setChecked(False)
#    dlg.x_lo.setValue(0.0)
#    dlg.x_hi.setValue(500.0)
#    dlg.y_auto.setChecked(False)
#    dlg.y_lo.setValue(0.0)
#    dlg.y_hi.setValue(400.0)
#    style = dlg.result_style()
#    assert (style["vmin"], style["vmax"]) == (40.0, 210.0)
#    assert (style["xmin"], style["xmax"]) == (0.0, 500.0)
#    ap.set_chart_style(style)
#
#    for ctype in ("position", "map", "box", "hist"):
#        ap._pick_ctype(ctype)
#        app.processEvents()
#        c = [x for x in ap._chart_widgets if x._ctype == ctype][-1]
#        assert c._locked(1.0, 2.0, "vmin", "vmax") == (40.0, 210.0)
#        assert c._locked(1.0, 2.0, "xmin", "xmax") == (0.0, 500.0)
#        assert c._locked(1.0, 2.0, "ymin", "ymax") == (0.0, 400.0)
#        c.grab()                       # every painter draws with them
#    assert c._range() == (40.0, 210.0)
#    # a nonsense range (hi below lo) is ignored rather than inverting an axis
#    ap.set_chart_style({"vmin": 9.0, "vmax": 1.0})
#    app.processEvents()
#    c = [x for x in ap._chart_widgets if x._ctype == "hist"][-1]
#    assert c._locked(3.0, 4.0, "vmin", "vmax") == (3.0, 4.0)
#
#
#def test_heat_scale_locks_the_image_overlay(app, tmp_path):
#    """A locked range makes the same colour mean the same grey level."""
#    import json
#    from pear.core.analysis import heat_color
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _grid_group(win, 2, 3)
#    sb = win.stage_bar
#    sb.show_combo.setCurrentIndex(sb.show_combo.findData("glv_mean"))
#    sb.heatmap_chk.setChecked(True)
#    auto = dict(win.image_view._heat)
#    assert set(auto.values()) & {heat_color(0.0)}      # auto stretches to min
#
#    win.on_heat_range((0.0, 255.0))
#    locked = win.image_view._heat
#    assert locked != auto
#    rid, v = next(iter(win._values.items()))
#    assert locked[rid] == heat_color(v / 255.0)        # the value's own place
#    assert win.image_view._heat_legend[:2] == (0.0, 255.0)
#
#    out = tmp_path / "p.pear.json"
#    win.save_project(str(out))
#    win2 = MainWindow()
#    win2.set_image(make_field(), "f.png")
#    win2._restore_project(json.loads(out.read_text(encoding="utf-8")))
#    assert win2._heat_range == (0.0, 255.0)
#    assert win2.stage_bar.heat_range() == (0.0, 255.0)
#    assert "255" in win2.stage_bar.scale_btn.text()    # the button says so
#
#    win.on_heat_range(None)                            # back to auto
#    assert win.image_view._heat == auto
#
#
#def test_chart_text_and_marks_are_adjustable(app):
#    """Axis ink, text size, point size and line width all come from the style."""
#    from PySide6.QtGui import QColor
#    from pear.ui import theme
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import ChartSettingsDialog, DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    ap = win.analysis
#    ap._pick_ctype("box")
#    app.processEvents()
#    c = [x for x in ap._chart_widgets if x._ctype == "box"][-1]
#    # dark by default: a light grey tick label is not there on a projector
#    assert c._axis_ink() == QColor(theme.INK)
#    assert c._font().pointSizeF() == pytest.approx(8.0, abs=0.5)
#
#    dlg = ChartSettingsDialog(None, ["GLV mean"], {})
#    dlg.font_spin.setValue(12.0)
#    dlg.point_spin.setValue(6.0)
#    dlg.line_spin.setValue(4.0)
#    state = dlg._colors["point_color"]
#    state["color"] = "#123456"
#    state["box"].setChecked(False)
#    style = dlg.result_style()
#    assert style["font_pt"] == 12.0 and style["point_size"] == 6.0
#    assert style["line_width"] == 4.0 and style["point_color"] == "#123456"
#
#    ap.set_chart_style(style)
#    app.processEvents()
#    c = [x for x in ap._chart_widgets if x._ctype == "box"][-1]
#    assert c._font().pointSizeF() == pytest.approx(12.0, abs=0.5)
#    assert c._line_w(2.2) == 4.0
#    assert c._mark_color("point_color", "#FF0000") == QColor("#123456")
#    assert c._mark_color("line_color", "#FF0000") == QColor("#FF0000")  # auto
#    c.grab()                                   # the painter reads all of it
#
#    dlg._reset()
#    back = dlg.result_style()
#    assert back["font_pt"] == 8.0 and "point_color" not in back
#
#    # the tick values take their own size and weight, the axis names another
#    ap.set_chart_style({"font_pt": 7.0, "tick_bold": True, "label_pt": 14.0,
#                        "label_bold": False})
#    app.processEvents()
#    c = [x for x in ap._chart_widgets if x._ctype == "box"][-1]
#    assert c._font().bold() and c._font().pointSizeF() == pytest.approx(7.0)
#    assert not c._label_font().bold()
#    assert c._label_font().pointSizeF() == pytest.approx(14.0, abs=0.5)
#    c.grab()
#
#
#def test_project_remembers_the_chart_settings(app, tmp_path):
#    """Reopening a project has to draw the chart you left, not the defaults.
#
#    The style (titles, fonts, colours, locked scales) and the header toggles
#    (points, legend, bins, cells…) both travel in the project file — a
#    locked scale that came back on auto would quietly make two lots look
#    comparable when they were not.
#    """
#    import json
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gid = _grid_group(win, 3, 4)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("within")
#    win.on_within_group(gid)
#    win.render_analysis_sync()
#    ap = win.analysis
#
#    ap.set_chart_style({"titles": {"GLV mean": "Figure 2"},
#                        "xlabel": "ROI centre X (px)",
#                        "font_pt": 13.0, "label_pt": 15.0, "tick_bold": True,
#                        "axis_ink": "#123456", "label_ink": "#654321",
#                        "point_color": "#0000FF", "line_color": "#FF00FF",
#                        "point_size": 5.0, "line_width": 3.0,
#                        "xticks": 7, "yticks": 3,
#                        "vmin": 40.0, "vmax": 210.0,
#                        "heat_vmin": 0.0, "heat_vmax": 255.0})
#    ap._pick_ctype("map")
#    ap.legend_chk.setChecked(True)
#    ap.points_chk.setChecked(False)
#    ap.pct_chk.setChecked(True)
#    ap.bins_spin.setValue(24)
#    ap.mapval_chk.setChecked(True)
#    ap.equal_chk.setChecked(False)
#    ap.axis_box.setCurrentIndex(1)
#    app.processEvents()
#    before_style = ap.chart_style()
#    before_opts = ap.chart_options()
#
#    out = tmp_path / "p.pear.json"
#    win.save_project(str(out))
#    data = json.loads(out.read_text(encoding="utf-8"))
#    assert data["chart_opts"]["bins"] == 24
#    assert data["chart_style"]["label_ink"] == "#654321"
#
#    win2 = MainWindow()
#    win2.set_image(make_field(), "f.png")
#    win2._restore_project(data)
#    win2.render_analysis_sync()
#    ap2 = win2.analysis
#    assert ap2.chart_style() == before_style
#    assert ap2.chart_options() == before_opts
#    assert ap2.chart_state() == ("map", "y")
#    assert ap2.legend_chk.isChecked() and not ap2.points_chk.isChecked()
#    assert ap2.bins_spin.value() == 24 and ap2.pct_chk.isChecked()
#    # every chart still draws with them
#    for ctype in ("box", "hist", "position", "map"):
#        ap2._pick_ctype(ctype)
#        app.processEvents()
#        c = [x for x in ap2._chart_widgets if x._ctype == ctype][-1]
#        assert c._locked(1.0, 2.0, "vmin", "vmax") == (40.0, 210.0)
#        c.grab()
#
#    # an older project without the key keeps today's defaults rather than
#    # coming back with every toggle off
#    data.pop("chart_opts")
#    win3 = MainWindow()
#    win3.set_image(make_field(), "f.png")
#    win3._restore_project(data)
#    assert win3.analysis.chart_options()["cells"] is True
#    assert win3.analysis.chart_options()["legend"] is False
#
#
#def test_axis_names_never_cover_the_tick_numbers(app):
#    """Bigger text has to push the axes in, not print on top of them.
#
#    The gutters used to be fixed pixel counts, so at 16 pt the rotated Y name
#    was drawn straight through the Y numbers and only half of each digit
#    showed. Both gutters are measured from the font now, and the ink of the
#    names is its own setting.
#    """
#    from PySide6.QtGui import QColor, QPainter, QPixmap
#    from pear.ui import theme
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gid = _grid_group(win, 3, 4)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("within")
#    win.on_within_group(gid)
#    win.render_analysis_sync()
#    ap = win.analysis
#
#    def gutters(chart):
#        """What the chart reserves for the tick numbers and the axis names."""
#        pm = QPixmap(max(chart.width(), 420), max(chart.height(), 300))
#        p = QPainter(pm)
#        left = chart._left_gutter(p, ["127.735", "62.2"])
#        bottom = chart._bottom_gutter(p, 1)
#        p.end()
#        return left, bottom
#
#    for ctype in ("box", "hist", "position", "map"):
#        ap._pick_ctype(ctype)
#        app.processEvents()
#        c = [x for x in ap._chart_widgets if x._ctype == ctype][-1]
#
#        ap.set_chart_style({"font_pt": 8.0, "label_pt": 8.0})
#        app.processEvents()
#        c = [x for x in ap._chart_widgets if x._ctype == ctype][-1]
#        small = gutters(c)
#
#        ap.set_chart_style({"font_pt": 16.0, "label_pt": 18.0,
#                            "xlabel": "ROI centre X (px)",
#                            "ylabel": "GLV mean (grey level)"})
#        app.processEvents()
#        c = [x for x in ap._chart_widgets if x._ctype == ctype][-1]
#        big = gutters(c)
#
#        assert big[0] > small[0], f"{ctype}: left gutter ignored the tick font"
#        assert big[1] > small[1], f"{ctype}: bottom gutter ignored the names"
#        c.grab()                       # and the painter still draws with them
#
#    # the axis names carry their own colour, falling back to the tick ink
#    ap.set_chart_style({"axis_ink": "#123456"})
#    app.processEvents()
#    c = ap._chart_widgets[-1]
#    assert c._label_ink() == QColor("#123456")
#    ap.set_chart_style({"axis_ink": "#123456", "label_ink": "#654321"})
#    app.processEvents()
#    c = ap._chart_widgets[-1]
#    assert c._axis_ink() == QColor("#123456")
#    assert c._label_ink() == QColor("#654321")
#    ap.set_chart_style({})
#    app.processEvents()
#    assert ap._chart_widgets[-1]._label_ink() == QColor(theme.INK)
#
#
#def test_heat_map_footer_clears_the_axis_name(app):
#    """The map has three things under its plot; none may sit on another."""
#    from PySide6.QtGui import QPainter, QPixmap
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    gid = _grid_group(win, 3, 4)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("within")
#    win.on_within_group(gid)
#    win.render_analysis_sync()
#    ap = win.analysis
#    ap._pick_ctype("map")
#    ap.set_chart_style({"font_pt": 16.0, "label_pt": 18.0})
#    app.processEvents()
#    c = [x for x in ap._chart_widgets if x._ctype == "map"][-1]
#    c.resize(560, 420)
#    app.processEvents()
#
#    pm = QPixmap(c.size())
#    p = QPainter(pm)
#    # tick row + axis name + the n/mean/range line all have to fit below the
#    # plot, which is what the extra row of gutter is for
#    plain = c._bottom_gutter(p, 1)
#    withfoot = c._bottom_gutter(p, 1, extra=p.fontMetrics().height() + 10)
#    p.end()
#    assert withfoot > plain
#    c.grab()                            # painted at that size without clipping
#
#
#def test_right_drag_pans_while_placing_a_grid(app):
#    """Reaching the far corner is exactly when panning matters."""
#    from PySide6.QtCore import QPointF, Qt
#    from PySide6.QtGui import QMouseEvent
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.set_grid_mode(True)
#    iv = win.image_view
#    before = QPointF(iv._offset)
#    start, end = QPointF(120.0, 90.0), QPointF(180.0, 130.0)
#    iv.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, start,
#                                   Qt.RightButton, Qt.RightButton,
#                                   Qt.NoModifier))
#    iv.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, end,
#                                  Qt.NoButton, Qt.RightButton, Qt.NoModifier))
#    iv.mouseReleaseEvent(QMouseEvent(QMouseEvent.Type.MouseButtonRelease, end,
#                                     Qt.RightButton, Qt.NoButton,
#                                     Qt.NoModifier))
#    assert iv._offset.x() == pytest.approx(before.x() + 60.0)
#    assert iv._offset.y() == pytest.approx(before.y() + 40.0)
#    assert iv._grid_stage == 0        # panning placed no grid anchor
#    assert win._rois == []
#
#
#def test_legend_is_opt_in_and_nothing_else_sits_under_the_axis(app):
#    """The key is furniture: off by default, and it holds the numbers that
#    used to crowd the axis."""
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    ap = win.analysis
#
#    for ctype in ("box", "hist"):
#        ap._pick_ctype(ctype)
#        app.processEvents()
#        assert not ap.legend_chk.isHidden() and not ap.legend_chk.isChecked()
#        c = [x for x in ap._chart_widgets if x._ctype == ctype][-1]
#        assert c._opts["legend"] is False and not c._legend_on()
#        c.grab()
#    ap.legend_chk.setChecked(True)
#    app.processEvents()
#    c = [x for x in ap._chart_widgets if x._ctype == "hist"][-1]
#    assert c._legend_on()
#    c.grab()
#
#    ap._pick_ctype("map")                 # a map has no legend to offer
#    assert ap.legend_chk.isHidden()
#
#    # the profile's per-group numbers ride in the key now, not below the axis
#    win.on_cmp_mode("within")
#    win.on_within_group(win._groups[0].gid)
#    win.render_analysis_sync()
#    ap._pick_ctype("position")
#    app.processEvents()
#    prof = [x for x in ap._chart_widgets if x._ctype == "position"][-1]
#    assert len(prof._line_key_rows()) == 3
#    prof.grab()
#    ap.legend_chk.setChecked(False)
#    app.processEvents()
#    [x for x in ap._chart_widgets if x._ctype == "position"][-1].grab()
#
#
#def test_export_chart_image_writes_png_and_svg(app, tmp_path):
#    from pear.ui.main_window import MainWindow
#    from pear.ui.widgets import DistributionChart
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    ap = win.analysis
#    win.analysis_window.resize(1200, 800)
#    win.analysis_window.show()
#    ap._pick_ctype("hist")
#    app.processEvents()
#    app.processEvents()
#    assert ap.image_btn.isEnabled()
#
#    png = tmp_path / "fig.png"
#    assert win.export_chart_image("charts", str(png)) == str(png)
#    from PySide6.QtGui import QImage
#    img = QImage(str(png))
#    chart = [c for c in ap.body.findChildren(DistributionChart)
#             if c._ctype == "hist" and c.isVisible()][-1]
#    # only the figure travels, at 3× — no dead margin from the layout's slack
#    assert img.width() == chart.width() * 3
#    assert img.height() == chart.height() * 3
#
#    svg = tmp_path / "fig.svg"
#    if win.export_chart_image("charts", str(svg)) is not None:  # QtSvg optional
#        text = svg.read_text(encoding="utf-8")
#        assert "<svg" in text and f"{chart.width()} {chart.height()}" in text
#
#
#def test_every_results_section_exports(app, tmp_path):
#    """Between-groups has four sections; each is offered and each writes."""
#    from PySide6.QtGui import QImage
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _two_groups(win)
#    win.set_metrics(["glv_mean", "glv_median"])
#    win.on_cmp_mode("between")
#    win.render_analysis_sync()
#    ap = win.analysis
#    win.analysis_window.resize(1200, 900)
#    win.analysis_window.show()
#    app.processEvents()
#    app.processEvents()
#    scopes = ap.scopes_available()
#    assert set(scopes) == {"charts", "ranking", "heat", "table", "all"}
#    assert ap.image_btn.isEnabled()
#    # two metrics → two figures, each offered on its own under Charts
#    assert [a.text() for a in ap._image_menu.actions()] == [
#        "Charts…", "    GLV mean…", "    GLV median…", "Attribute ranking…",
#        "Group × metric heatmap…", "Summary table…", "Everything…"]
#    one = tmp_path / "one.png"
#    assert win.export_chart_image("chart:1", str(one)) == str(one)
#    single = QImage(str(one))
#    assert single.width() == ap._chart_widgets[1].width() * 3
#    assert ap.save_image(str(one), "chart:9") is None          # out of range
#    for scope in scopes:
#        out = tmp_path / f"{scope}.png"
#        assert win.export_chart_image(scope, str(out)) == str(out)
#        img = QImage(str(out))
#        assert img.width() > 60 and img.height() > 40
#    # within a group there is no ranking or group heatmap to offer
#    win.on_cmp_mode("within")
#    win.on_within_group(win._groups[0].gid)
#    win.render_analysis_sync()
#    app.processEvents()
#    assert "ranking" not in ap.scopes_available()
#
#
#def test_stage_and_inspector_export_images(app, tmp_path):
#    """The annotated field exports at the image's own resolution, not the view's."""
#    from PySide6.QtGui import QImage
#    from pear.core.analysis import group_rois
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    field = make_field()
#    win.set_image(field, "f.png")
#    _grid_group(win, 2, 3)
#    sb = win.stage_bar
#    sb.show_combo.setCurrentIndex(sb.show_combo.findData("glv_mean"))
#    sb.heatmap_chk.setChecked(True)
#    sb.cells_chk.setChecked(True)
#    win.image_view.resize(300, 200)          # a small, zoomed-out view…
#    app.processEvents()
#
#    out = tmp_path / "field.png"
#    assert win.export_stage_image(str(out), 2.0) == str(out)
#    img = QImage(str(out))
#    h, w = field.shape[:2]
#    from pear.ui.image_view import _LEGEND_H
#    assert img.width() == w * 2                            # …exports full size
#    # the colour key gets a strip of its own under the field
#    assert img.height() == h * 2 + _LEGEND_H
#    assert win.image_view._scale != 2.0                    # the view is untouched
#    assert not win.image_view._exporting                   # flag always restored
#
#    sb.heatmap_chk.setChecked(False)                       # no key, no strip
#    sb.cells_chk.setChecked(False)
#    plain = tmp_path / "plain.png"
#    assert win.export_stage_image(str(plain), 1.0) == str(plain)
#    assert (QImage(str(plain)).width(), QImage(str(plain)).height()) == (w, h)
#    sb.heatmap_chk.setChecked(True)
#
#    svg = tmp_path / "field.svg"
#    if win.export_stage_image(str(svg), 1.0) is not None:
#        assert "<svg" in svg.read_text(encoding="utf-8")
#
#    rid = group_rois(win._rois, win._active_gid)[0].rid
#    win.open_inspector(rid)
#    win.inspector_window.resize(600, 470)
#    win.inspector_window.show()
#    app.processEvents()
#    roi_png = tmp_path / "roi.png"
#    assert win.export_inspector_image(str(roi_png)) == str(roi_png)
#    assert QImage(str(roi_png)).width() == win.inspector.width() * 3
#
#
#def test_position_chart_without_positions_is_safe(app):
#    """A series with no per-ROI position says so instead of crashing.
#
#    Nothing in the app produces one today, but the guard is what keeps a
#    future per-group metric from taking the window down.
#    """
#    from pear.ui.widgets import DistributionChart
#    chart = DistributionChart()
#    chart.resize(420, 300)
#    chart.set_data("GLV mean", [{"label": "A", "color": "#2563EB",
#                                 "values": np.array([1.0, 2.0, 3.0])}],
#                   "position")
#    assert all("pos_x" not in s for s in chart._series)
#    chart.grab()                       # draws the "no position" hint
#    chart.set_data("GLV mean", [{"label": "A", "color": "#2563EB",
#                                 "values": np.array([1.0, 2.0])}], "map")
#    chart.grab()
#
#
#def test_chart_state_round_trips_through_a_project(app, tmp_path):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    _grid_group(win, 2, 3)
#    win.analysis.set_chart_state("map", "y")
#    out = tmp_path / "p.pear.json"
#    win.save_project(str(out))
#
#    win2 = MainWindow()
#    win2.set_image(make_field(), "f.png")
#    assert win2.analysis.chart_state() == ("box", "x")
#    import json
#    win2._restore_project(json.loads(out.read_text(encoding="utf-8")))
#    assert win2.analysis.chart_state() == ("map", "y")
#
#
#def test_csv_carries_the_roi_centre(app, tmp_path):
#    from pear.ui.main_window import MainWindow
#    win = MainWindow()
#    win.set_image(make_field(), "f.png")
#    win.add_group()
#    win.on_roi_created((10, 20, 10, 10))
#    win.set_metrics(["glv_mean"])
#    out = tmp_path / "c.csv"
#    assert win.export_csv(str(out)) == str(out)
#    text = out.read_text(encoding="utf-8-sig")
#    assert "center_x" in text and "center_y" in text
#    assert "15,25" in text.replace(", ", ",")     # centre of (10,20,10,10)
#
#
#def test_icon_carries_every_windows_size(app, tmp_path):
#    """The .ico is assembled by hand — so check Windows could read it back."""
#    import struct
#    import sys as _sys
#    from PySide6.QtGui import QImage
#    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#    from tools.make_icon import SIZES, build_ico, draw, write_icon
#
#    data = build_ico()
#    reserved, kind, count = struct.unpack("<HHH", data[:6])
#    assert (reserved, kind, count) == (0, 1, len(SIZES))
#    for i, size in enumerate(SIZES):
#        w, h, colors, res, planes, bits, length, offset = struct.unpack(
#            "<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
#        assert (w, h) == (size % 256, size % 256)     # 256 is stored as 0
#        assert (planes, bits) == (1, 32)
#        payload = data[offset:offset + length]
#        assert payload[:4] == b"\x89PNG"              # Vista+ compressed entry
#        img = QImage.fromData(payload, "PNG")
#        assert (img.width(), img.height()) == (size, size)
#
#    # it draws something: the tile is not blank, and the mark is not the tile
#    big = draw(64)
#    assert big.pixelColor(2, 2).alpha() == 0           # rounded corner is clear
#    assert big.pixelColor(32, 32) != big.pixelColor(6, 32)
#
#    out = tmp_path / "x.ico"
#    assert write_icon(str(out)) == str(out)
#    from PySide6.QtGui import QIcon
#    assert sorted(s.width() for s in QIcon(str(out)).availableSizes()) == \
#        sorted(SIZES)
#
#F 1a5c914e592af6b0b22833d5f05929d8e384ddf3 211 tools/install_windows.py
##!/usr/bin/env python3
#"""One-click Windows install for PEAR — the part ``install.bat`` calls.
#
#Why the work is here and not in the .bat
#----------------------------------------
#The repo travels to the fab machine as one plain-text file and that bundle
#only accepts LF line endings, but ``cmd.exe`` is unreliable with LF-only
#batch files once blocks or ``goto`` appear. So ``install.bat`` is three lines
#with neither, and everything that could go wrong lives here, where it can
#say what went wrong.
#
#What it does
#------------
#1. Makes a virtual environment in ``.venv`` (falls back to a ``--user``
#   install if the machine forbids one).
#2. Installs the three dependencies — **from ``wheels\\`` if that folder
#   exists**, which is the whole point on a machine with no download route,
#   otherwise from the network.
#3. Checks the imports actually work.
#4. Draws ``pear.ico``.
#5. Puts shortcuts on the Desktop and in the Start Menu, pointing at
#   ``PEAR.bat`` with that icon.
#
#    python tools\\install_windows.py            # install
#    python tools\\install_windows.py --run      # …and launch it
#    python tools\\install_windows.py --no-venv  # install into this Python
#    python tools\\install_windows.py --no-shortcuts
#"""
#from __future__ import annotations
#
#import argparse
#import os
#import subprocess
#import sys
#import tempfile
#
#ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#VENV = os.path.join(ROOT, ".venv")
#WHEELS = os.path.join(ROOT, "wheels")
#MODULES = (("numpy", "numpy"), ("cv2", "opencv-python"),
#           ("PySide6.QtWidgets", "PySide6"))
#
#
#def say(step: str, text: str = "") -> None:
#    print(f"\n[{step}] {text}" if text else f"\n[{step}]")
#
#
#def run(cmd, **kw) -> int:
#    """Run a command, showing it first — an install that fails silently is
#    worse than one that fails loudly on a machine you cannot debug."""
#    print("    > " + subprocess.list2cmdline(cmd))
#    return subprocess.call(cmd, cwd=ROOT, **kw)
#
#
#def venv_python(base: str) -> str:
#    exe = "python.exe" if os.name == "nt" else "python"
#    sub = "Scripts" if os.name == "nt" else "bin"
#    return os.path.join(base, sub, exe)
#
#
#def make_venv() -> str:
#    """The interpreter to install into: the venv's, or this one."""
#    if os.path.exists(venv_python(VENV)):
#        print(f"    reusing {VENV}")
#        return venv_python(VENV)
#    if run([sys.executable, "-m", "venv", VENV]) == 0:
#        return venv_python(VENV)
#    print("    ! could not create a virtual environment — installing into\n"
#          "      this Python instead (add --no-venv to skip the attempt)")
#    return sys.executable
#
#
#def install_deps(python: str, user: bool) -> bool:
#    """Dependencies, from the local wheel folder if there is one."""
#    base = [python, "-m", "pip", "install", "--disable-pip-version-check"]
#    if user:
#        base.append("--user")
#    req = os.path.join(ROOT, "requirements.txt")
#    if os.path.isdir(WHEELS):
#        print(f"    found {WHEELS} — installing offline from it")
#        code = run(base + ["--no-index", "--find-links", WHEELS, "-r", req])
#        if code == 0:
#            return True
#        print("    ! the wheels in that folder did not satisfy "
#              "requirements.txt; trying the network")
#    return run(base + ["-r", req]) == 0
#
#
#def check_imports(python: str) -> bool:
#    missing = []
#    for module, package in MODULES:
#        code = subprocess.call([python, "-c", f"import {module}"],
#                               stdout=subprocess.DEVNULL,
#                               stderr=subprocess.DEVNULL)
#        state = "ok" if code == 0 else "MISSING"
#        print(f"    {package:<14} {state}")
#        if code != 0:
#            missing.append(package)
#    return not missing
#
#
#def make_icon(python: str) -> str:
#    icon = os.path.join(ROOT, "pear.ico")
#    if run([python, os.path.join(ROOT, "tools", "make_icon.py"),
#            "--out", icon]) != 0 or not os.path.exists(icon):
#        print("    ! icon not drawn — the shortcuts will use the default one")
#        return ""
#    return icon
#
#
#def make_shortcuts(icon: str) -> None:
#    """Desktop and Start Menu shortcuts, via WScript — no PowerShell.
#
#    Locked-down machines often block PowerShell scripts outright, and
#    ``cscript`` is the one scripting host that has always been there.
#    """
#    if os.name != "nt":
#        print("    (skipped: shortcuts are a Windows thing)")
#        return
#    launcher = os.path.join(ROOT, "PEAR.bat")
#    home = os.path.expanduser("~")
#    targets = [os.path.join(home, "Desktop", "PEAR.lnk"),
#               os.path.join(home, "AppData", "Roaming", "Microsoft",
#                            "Windows", "Start Menu", "Programs", "PEAR.lnk")]
#    lines = ['Set s = WScript.CreateObject("WScript.Shell")']
#    for path in targets:
#        folder = os.path.dirname(path)
#        if not os.path.isdir(folder):
#            print(f"    (skipped: no {folder})")
#            continue
#        lines += [
#            f'Set k = s.CreateShortcut("{path}")',
#            f'k.TargetPath = "{launcher}"',
#            f'k.WorkingDirectory = "{ROOT}"',
#            'k.Description = "PEAR — Pre-EBI Attribute Ranker"',
#        ]
#        if icon:
#            lines.append(f'k.IconLocation = "{icon}"')
#        lines.append("k.Save")
#        print(f"    {path}")
#    if len(lines) == 1:
#        return
#    with tempfile.NamedTemporaryFile("w", suffix=".vbs", delete=False,
#                                     encoding="utf-8") as fh:
#        fh.write("\r\n".join(lines) + "\r\n")
#        script = fh.name
#    try:
#        if subprocess.call(["cscript", "//nologo", script]) != 0:
#            print("    ! could not write the shortcuts — run PEAR.bat directly")
#    except OSError:
#        print("    ! cscript is not available — run PEAR.bat directly")
#    finally:
#        os.unlink(script)
#
#
#def main(argv=None) -> int:
#    ap = argparse.ArgumentParser(description="Install PEAR on Windows.")
#    ap.add_argument("--no-venv", action="store_true",
#                    help="install into the Python running this script")
#    ap.add_argument("--no-shortcuts", action="store_true")
#    ap.add_argument("--run", action="store_true", help="launch when done")
#    args = ap.parse_args(argv)
#
#    print("PEAR — Pre-EBI Attribute Ranker")
#    print(f"repo   : {ROOT}")
#    print(f"python : {sys.version.split()[0]}  ({sys.executable})")
#    if sys.version_info < (3, 9):
#        print("\n! PEAR needs Python 3.9 or newer. Install one, then run "
#              "install.bat again.")
#        return 2
#
#    say("1/5", "virtual environment")
#    python = sys.executable if args.no_venv else make_venv()
#    user_flag = args.no_venv or python == sys.executable
#
#    say("2/5", "dependencies")
#    if not install_deps(python, user_flag):
#        print("\n! pip could not install the dependencies.\n"
#              "  On a machine with no download route, copy the wheels for\n"
#              "  numpy, opencv-python and PySide6 into:\n"
#              f"      {WHEELS}\n"
#              "  (any machine with internet: pip download -r requirements.txt\n"
#              "   -d wheels), then run install.bat again.")
#        return 1
#
#    say("3/5", "checking the imports")
#    if not check_imports(python):
#        print("\n! something did not install cleanly — see the list above.")
#        return 1
#
#    say("4/5", "drawing the icon")
#    icon = make_icon(python)
#
#    say("5/5", "shortcuts")
#    if args.no_shortcuts:
#        print("    (skipped)")
#    else:
#        make_shortcuts(icon)
#
#    print("\nDone. Start PEAR from the Desktop shortcut, or with PEAR.bat.")
#    if args.run:
#        print("\nLaunching…")
#        pyw = python.replace("python.exe", "pythonw.exe")
#        subprocess.Popen([pyw if os.path.exists(pyw) else python, "-m", "pear"],
#                         cwd=ROOT)
#    return 0
#
#
#if __name__ == "__main__":
#    raise SystemExit(main())
#
#F 0d2a20edd273a695c7041c8e27541b639f4ba4a9 158 tools/make_icon.py
##!/usr/bin/env python3
#"""Draw PEAR's icon and write a multi-size Windows ``.ico``.
#
#Why generated instead of committed
#----------------------------------
#The whole repo travels to the offline machine as **one plain-text file**
#(``bundle/pear_bundle.py``), and that bundle refuses anything that is not
#LF + UTF-8 text — a binary ``.ico`` in ``git ls-files`` would break it. So the
#icon ships as the few dozen lines of QPainter below and is drawn on the
#machine that installs PEAR, where PySide6 already exists.
#
#The mark
#--------
#A measurement grid: nine cells across the heat ramp the app uses (blue →
#amber → red), one of them ringed in white — a ROI on a field. That is what
#PEAR does, and it survives being shrunk to 16 px, which a pear silhouette or
#a wordmark would not.
#
#    python tools/make_icon.py                 # -> pear.ico (+ pear_icon.png)
#    python tools/make_icon.py --out D:\\x.ico
#"""
#from __future__ import annotations
#
#import argparse
#import os
#import struct
#import sys
#from typing import List
#
#sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#
##: The sizes Windows actually asks for: 16 in the tray and small list views,
##: 32 on the desktop, 48 in medium icons, 256 in the extra-large view.
#SIZES = (16, 24, 32, 48, 64, 128, 256)
#
#INK = "#111827"          # tile: the image stage's own black, softened
#RAMP = ("#2563EB", "#4B72C8", "#8E8AA0", "#F59E0B", "#EA7A0B", "#DC2626")
#
#
#def _cell_colors(n: int) -> List[str]:
#    """Nine cells sampled across the ramp — a field with a gradient in it."""
#    order = (0, 1, 3, 1, 3, 4, 2, 4, 5)
#    return [RAMP[order[i % len(order)]] for i in range(n)]
#
#
#def draw(size: int):
#    """The icon at one size, as a QImage."""
#    from PySide6.QtCore import QRectF, Qt
#    from PySide6.QtGui import QColor, QImage, QPainter, QPen
#
#    img = QImage(size, size, QImage.Format_ARGB32)
#    img.fill(Qt.transparent)
#    p = QPainter(img)
#    p.setRenderHint(QPainter.Antialiasing, True)
#
#    pad = max(1.0, size * 0.06)
#    tile = QRectF(pad, pad, size - 2 * pad, size - 2 * pad)
#    radius = size * 0.18
#    p.setPen(Qt.NoPen)
#    p.setBrush(QColor(INK))
#    p.drawRoundedRect(tile, radius, radius)
#
#    # the grid of measured cells
#    inset = size * 0.13
#    grid = tile.adjusted(inset, inset, -inset, -inset)
#    gap = 0.0 if size < 32 else max(1.0, size * 0.02)
#    cw = (grid.width() - gap * 2) / 3.0
#    ch = (grid.height() - gap * 2) / 3.0
#    colors = _cell_colors(9)
#    cell_r = 0.0 if size < 32 else size * 0.04
#    for i, color in enumerate(colors):
#        r, c = divmod(i, 3)
#        rect = QRectF(grid.left() + c * (cw + gap), grid.top() + r * (ch + gap),
#                      cw, ch)
#        p.setPen(Qt.NoPen)
#        p.setBrush(QColor(color))
#        if cell_r:
#            p.drawRoundedRect(rect, cell_r, cell_r)
#        else:
#            p.drawRect(rect)
#
#    # the ROI: one cell picked out. Below 24 px a ring is mud, so the cell is
#    # simply left brighter than its neighbours by the ramp itself.
#    if size >= 24:
#        r, c = 1, 1
#        rect = QRectF(grid.left() + c * (cw + gap), grid.top() + r * (ch + gap),
#                      cw, ch)
#        pen = QPen(QColor("#FFFFFF"), max(1.0, size * 0.028))
#        p.setPen(pen)
#        p.setBrush(Qt.NoBrush)
#        grow = size * 0.012
#        p.drawRect(rect.adjusted(-grow, -grow, grow, grow))
#    p.end()
#    return img
#
#
#def _png_bytes(img) -> bytes:
#    from PySide6.QtCore import QBuffer, QByteArray
#
#    ba = QByteArray()
#    buf = QBuffer(ba)
#    buf.open(QBuffer.WriteOnly)
#    if not img.save(buf, "PNG"):
#        raise RuntimeError("Qt could not encode the icon as PNG")
#    buf.close()
#    return bytes(ba)
#
#
#def build_ico(sizes=SIZES) -> bytes:
#    """Assemble a Windows ``.ico`` from PNG-compressed entries.
#
#    Qt writes PNG but not ICO, and ICO is a header plus payloads — so the
#    container is written here rather than dragging in a second imaging
#    library that the offline machine would then have to install.
#    """
#    payloads = [_png_bytes(draw(s)) for s in sizes]
#    out = bytearray(struct.pack("<HHH", 0, 1, len(sizes)))
#    offset = 6 + 16 * len(sizes)
#    for size, data in zip(sizes, payloads):
#        dim = 0 if size >= 256 else size          # 0 means 256 in an ICO
#        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
#                           len(data), offset)
#        offset += len(data)
#    for data in payloads:
#        out += data
#    return bytes(out)
#
#
#def write_icon(path: str, png_path: str = "") -> str:
#    """Write the ``.ico`` (and optionally a PNG preview). Returns the path."""
#    from PySide6.QtGui import QGuiApplication
#
#    if QGuiApplication.instance() is None:
#        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
#        QGuiApplication([])                       # QPainter needs a GUI app
#    data = build_ico()
#    with open(path, "wb") as fh:
#        fh.write(data)
#    if png_path:
#        draw(256).save(png_path, "PNG")
#    return path
#
#
#def main(argv=None) -> int:
#    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#    ap = argparse.ArgumentParser(description="Draw PEAR's Windows icon.")
#    ap.add_argument("--out", default=os.path.join(root, "pear.ico"))
#    ap.add_argument("--png", default="", help="also write a PNG preview here")
#    args = ap.parse_args(argv)
#    path = write_icon(args.out, args.png)
#    print(f"{path}  ({os.path.getsize(path)} bytes, "
#          f"{len(SIZES)} sizes: {', '.join(str(s) for s in SIZES)})")
#    return 0
#
#
#if __name__ == "__main__":
#    raise SystemExit(main())
#
#F dc218e869f9f2f3780472eb526d60eb94d2cbaec 305 tools/make_text_bundle.py
##!/usr/bin/env python3
## PEAR 單檔純文字打包 — 沿用 d4t 的 tools/make_text_bundle.py 慣例。
#"""把整個 repo 打成**一個純文字 .py 檔**，那個檔案自己解得開。
#
#什麼時候需要這個
#----------------
#公司環境擋掉下載：`.zip` 這個類別被擋（不只 GitHub 的 `codeload`，換來源也一
#樣），proxy 也不讓 Python 逐檔抓。剩下唯一能過的通道是「在 GitHub 上看得到檔
#案、按複製鈕、貼進記事本」—— 所以要能用**一個純文字檔**搬完整包程式碼。
#
#所以這支產出的東西**沒有任何壓縮、也不用 base64**：每個檔案的內容原封不動地
#一行一行躺在裡面，記事本打開就讀得到。base64 對 DLP 來說是「看不懂的東西」，
#而看不懂通常等於擋掉；PEAR 本來就全部是純文字，沒有編碼的必要。
#
#（d4t 的同名工具有 ``--compress``，因為那個 repo 長到 900 KB 以上、超過 GitHub
#檔案瀏覽頁 1 MB 的顯示上限。PEAR 目前約 250 KB，一個純文字檔綽綽有餘，所以這
#裡不做壓縮 —— 真的長大了再加，`--split` 已經備好。）
#
#怎麼用
#------
#    python tools/make_text_bundle.py            # 產 bundle/pear_bundle.py
#    python tools/make_text_bundle.py --out X.py
#    python tools/make_text_bundle.py --split 400   # 每批最多 400 KB
#
#拿到 `pear_bundle.py` 的人：
#
#    python pear_bundle.py                      # 解到 .\\pear\\
#    python pear_bundle.py --dest D:\\tools
#    python pear_bundle.py --list               # 只列出裡面有什麼，不寫檔
#
#格式為什麼是「行數」而不是「位元組數」
#--------------------------------------
#這個檔案會經過瀏覽器複製、記事本另存、郵件附件…… 任何一步都可能把 LF 換成
#CRLF。用位元組數的話那一換整包就對不起來，而且錯誤會發生在**第一個檔案之後的
#全部檔案**上，看起來像整包壞掉。用行數則對換行符號免疫 —— 解開時用 Python 的
#文字模式讀（它把 CRLF 讀成 LF），所以來回一趟仍然逐位元組相同。前提是 repo 裡
#全部是 LF + UTF-8，這支會在打包前檢查，不合就拒絕產出。
#
#每個檔案都帶 **git blob SHA-1**，解開時逐檔驗 —— 傳輸途中被動到要當場講出來，
#而不是讓使用者拿到一份安靜壞掉的程式碼。
#"""
#from __future__ import annotations
#
#import argparse
#import hashlib
#import os
#import subprocess
#import sys
#from typing import List, Optional, Tuple
#
##: 不進包的目錄。`bundle/` 是產出物自己 —— 不排掉的話每打一次包，repo 就多裝
##: 一份上一次的包，而且是指數成長。
#EXCLUDE_DIRS = ("bundle", ".github")
#
##: 資料區的分隔行。解包時找的是**整行剛好等於它**的那一行 —— 而資料區的每一行
##: 都被加了 '#'，所以就算某個檔案的內容裡出現這個字串（這支自己就在 repo 裡，
##: 源碼中當然有），也永遠不會剛好相等。加 '#' 因此同時解決兩個問題：整個檔案
##: 仍然是合法的 Python，而分隔行不會被誤認。
#SENTINEL = "# ==== PEAR-BUNDLE-DATA ==== 以下是資料，不要編輯 ===="
#
##: 解包程式（放在產出檔案的最前面）。它自己也是這份 bundle 的一部分，所以刻意
##: 寫短、只用標準函式庫、而且看得完 —— 使用者要能在跑之前先讀一遍。
#EXTRACTOR = '''#!/usr/bin/env python3
## PEAR 單檔純文字包（由 tools/make_text_bundle.py 產生）。
#"""整個 PEAR repo 就在這個檔案裡，一行一行的純文字，沒有壓縮、沒有編碼。
#
#為什麼是這種形式：公司政策擋掉 .zip 這個類別，proxy 也不讓 Python 逐檔抓 ——
#能過的只剩「一個純文字檔」。你可以用記事本打開它，往下捲就看得到每個檔案。
#
#    python %(name)s              # 解到 .\\\\pear\\\\
#    python %(name)s --dest D:\\\\tools
#    python %(name)s --list       # 只看裡面有什麼，不寫任何檔案
#
#每個檔案都帶 git blob SHA-1，解開時逐檔驗過才落地 —— 傳輸途中被動到會當場講出
#來，不會讓你拿到一份安靜壞掉的程式碼。
#
#解開之後：
#
#    cd pear
#    pip install -r requirements.txt
#    python -m pear
#"""
#from __future__ import annotations
#
#import argparse
#import hashlib
#import os
#import sys
#
#SENTINEL = "%(sentinel)s"
#PART, N_PARTS = %(part)d, %(n_parts)d   # 這是第幾批 / 共幾批（1/1 = 沒有分批）
#TOTAL = %(total)d                       # 整個 repo 有幾個檔案，不是這一批有幾個
#
#
#def blob_sha(data: bytes) -> str:
#    """git 算 blob SHA 的方式："blob <長度>\\\\0" + 內容。"""
#    h = hashlib.sha1()
#    h.update(b"blob %%d\\0" %% len(data))
#    h.update(data)
#    return h.hexdigest()
#
#
#def entries(lines):
#    """走過資料區，一個一個吐出 (sha, 路徑, 內容位元組)。"""
#    i = 0
#    while i < len(lines):
#        line = lines[i]
#        if not line.startswith("#F "):
#            i += 1
#            continue
#        _, sha, count, path = line.split(" ", 3)
#        n = int(count)
#        # 資料區每一行前面有一個 '#'（那樣整個檔案才仍然是合法的 Python）。
#        body = [ln[1:] if ln[:1] == "#" else ln for ln in lines[i + 1:i + 1 + n]]
#        yield sha, path, "\\n".join(body).encode("utf-8")
#        i += 1 + n
#
#
#def main(argv=None) -> int:
#    ap = argparse.ArgumentParser(description="Unpack the PEAR text bundle.")
#    ap.add_argument("--dest", default="pear", help="解到哪個資料夾（預設 .\\\\pear）")
#    ap.add_argument("--list", action="store_true", help="只列出內容，不寫檔")
#    a = ap.parse_args(argv)
#
#    # 用文字模式讀自己：Python 把 CRLF 讀成 LF，所以這個檔案就算在傳輸途中被換
#    # 過行尾也解得開（格式用「行數」而不是「位元組數」正是為了這件事）。
#    with open(os.path.abspath(__file__), "r", encoding="utf-8") as f:
#        lines = f.read().split("\\n")
#    try:
#        start = lines.index(SENTINEL) + 1
#    except ValueError:
#        print("X 找不到資料區 —— 這個檔案被截斷了，或不是完整的 bundle。")
#        return 2
#
#    items = list(entries(lines[start:]))
#    if not items:
#        print("X 資料區是空的 —— 這個檔案被截斷了。")
#        return 2
#    print("這個包裡有 %%d 個檔案。" %% len(items))
#    if a.list:
#        for _sha, path, data in items:
#            print("  %%8d  %%s" %% (len(data), path))
#        return 0
#
#    dest = os.path.abspath(a.dest)
#    print("解到  : %%s" %% dest)
#    bad, done = [], 0
#    for sha, path, data in items:
#        if blob_sha(data) != sha:
#            bad.append(path)
#            continue
#        full = os.path.join(dest, path.replace("/", os.sep))
#        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
#        tmp = full + ".tmp"                      # atomic：半個檔案不要留在磁碟上
#        with open(tmp, "wb") as f:
#            f.write(data)
#        os.replace(tmp, full)
#        done += 1
#
#    if bad:
#        print("")
#        print("X %%d 個檔案的內容跟它自己的 SHA 對不上：" %% len(bad))
#        for path in bad[:12]:
#            print("    %%s" %% path)
#        print("")
#        print("  這個檔案在傳輸途中被動過（編輯器另存、郵件過濾器改寫都會這樣）。")
#        print("  請重新取得一份，不要用編輯器打開後另存。這份程式碼不完整，不要用。")
#        return 1
#
#    print("OK %%d 個檔案都解開了，SHA 全部對得上。" %% done)
#
#    if N_PARTS > 1:
#        print("")
#        print("這是第 %%d 批 / 共 %%d 批，整個 repo 有 %%d 個檔案。"
#              %% (PART, N_PARTS, TOTAL))
#        print("把其他批也貼進來執行（順序不重要，重複執行也沒關係）。")
#        return 0
#
#    print("")
#    print("下一步：")
#    print("  cd %%s" %% dest)
#    print("  pip install -r requirements.txt")
#    print("  python -m pear")
#    return 0
#
#
#if __name__ == "__main__":
#    sys.exit(main())
#'''
#
#
#def repo_root() -> str:
#    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#
#
#def blob_sha(data: bytes) -> str:
#    h = hashlib.sha1()                                # noqa: S324 — git 的格式
#    h.update(b"blob %d\0" % len(data))
#    h.update(data)
#    return h.hexdigest()
#
#
#def collect(root: str = "") -> List[Tuple[str, bytes]]:
#    """``git ls-files`` 的每個檔案（路徑, 位元組）。
#
#    順便擋掉兩種會讓「用行數打包」失效的東西：CRLF 與非 UTF-8。拒絕產出比產出
#    一個解不開的包好 —— 後者要等收到的人才會發現。
#    """
#    root = root or repo_root()
#    out = subprocess.run(["git", "ls-files"], cwd=root, check=True,
#                         stdout=subprocess.PIPE).stdout.decode("utf-8")
#    items = []
#    for rel in sorted(p for p in out.split("\n") if p.strip()):
#        if any(rel.startswith(d + "/") for d in EXCLUDE_DIRS):
#            continue
#        with open(os.path.join(root, rel.replace("/", os.sep)), "rb") as f:
#            data = f.read()
#        if b"\r" in data:
#            raise SystemExit(
#                "%s 含 CR（CRLF 或裸 CR）—— 以行數為單位的打包會弄壞它。"
#                "先把它轉成 LF。" % rel)
#        try:
#            data.decode("utf-8")
#        except UnicodeDecodeError:
#            raise SystemExit("%s 不是 UTF-8 —— 這個格式只裝純文字。" % rel)
#        items.append((rel, data))
#    return items
#
#
#def _data_lines(items: List[Tuple[str, bytes]]) -> List[str]:
#    """資料區。"""
#    out: List[str] = []
#    for rel, data in items:
#        body = data.decode("utf-8").split("\n")
#        out.append("#F %s %d %s" % (blob_sha(data), len(body), rel))
#        # **每一行都要變成註解。** Python 在跑任何東西之前會先編譯整個檔案，所以
#        # 資料區不能是裸的文字 —— 不然它會去解析別的檔案的內容然後語法錯誤。加
#        # 一個 '#' 比塞進三引號字串安全：檔案內容裡本來就可能有三個引號。
#        out.extend("#" + line for line in body)
#    return out
#
#
#def build(out_name: str = "pear_bundle.py", root: str = "",
#          items: Optional[List[Tuple[str, bytes]]] = None,
#          part: int = 1, n_parts: int = 1, total_files: int = 0) -> str:
#    items = collect(root) if items is None else items
#    parts = [EXTRACTOR % {"name": out_name, "sentinel": SENTINEL,
#                          "part": part, "n_parts": n_parts,
#                          "total": total_files or len(items)}, SENTINEL]
#    parts.extend(_data_lines(items))
#    return "\n".join(parts) + "\n"
#
#
#def _slice(items: List[Tuple[str, bytes]], limit: int
#           ) -> List[List[Tuple[str, bytes]]]:
#    """依大小切成幾批。``limit`` 是每批的內容上限（位元組）。"""
#    out: List[List[Tuple[str, bytes]]] = [[]]
#    size = 0
#    for rel, data in items:
#        if size + len(data) > limit and out[-1]:
#            out.append([])
#            size = 0
#        out[-1].append((rel, data))
#        size += len(data)
#    return out
#
#
#def main(argv=None) -> int:
#    ap = argparse.ArgumentParser(
#        description="Pack the repo into one plain-text self-extracting .py")
#    ap.add_argument("--out", default=os.path.join("bundle", "pear_bundle.py"),
#                    help="輸出檔名（分批時會變成 ..._part1of3.py）")
#    ap.add_argument("--split", type=int, default=0, metavar="KB",
#                    help=("每批最多幾 KB（0 = 不分批）。**GitHub 的檔案瀏覽頁在 "
#                          "1 MB 以上不顯示內容**，那顆複製鈕也跟著消失；剪貼簿"
#                          "是唯一通道時就必須分批。"))
#    a = ap.parse_args(argv)
#
#    items = collect()
#    groups = _slice(items, a.split * 1024) if a.split else [items]
#    out_dir = os.path.dirname(os.path.abspath(a.out))
#    if out_dir and not os.path.isdir(out_dir):
#        os.makedirs(out_dir, exist_ok=True)
#    stem, ext = os.path.splitext(a.out)
#    n_parts = len(groups)
#
#    for i, group in enumerate(groups, 1):
#        name = a.out if n_parts == 1 else "%s_part%dof%d%s" % (stem, i, n_parts, ext)
#        text = build(os.path.basename(name), items=group, part=i,
#                     n_parts=n_parts, total_files=len(items))
#        tmp = name + ".tmp"                           # atomic
#        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
#            f.write(text)
#        os.replace(tmp, name)
#        print("%s：%d 個檔案、%.0f KB"
#              % (name, len(group), len(text.encode("utf-8")) / 1024))
#    if n_parts > 1:
#        print("\n共 %d 批、%d 個檔案。每一批都可以單獨執行，順序不重要，"
#              "重複執行也沒關係。" % (n_parts, len(items)))
#    return 0
#
#
#if __name__ == "__main__":
#    sys.exit(main())
#
