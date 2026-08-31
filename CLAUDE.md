# CLAUDE.md — PEAR

給在這個 repo 工作的 AI 助手的規則。先讀完再動手。

---

## 0. 這個工具在做什麼（改任何東西之前先懂這件事）

**PEAR = Pre-EBI Attribute Ranker。** EBI（電子束檢測）**建 recipe 之前**用的
量測工具。

### 「不下判斷」原則

**PEAR 只量測與呈現，不偵測、不分類、不下判定。** 它給出數字與分佈，結論由工程
師來下。

這不是一句口號，是**驗收標準**：任何新功能如果會印出「pass / fail」「這是缺陷」
「這片不合格」，就是走錯方向。要加的是**數字**（η²、Cohen's d、range、CV、
slope），讓使用者自己看。加門檻值、加紅綠燈、加自動判定 —— 都不行。

### 兩層模型

- **Group** = 特徵的**類別**（圓孔 vs 方孔），不是一個框
- **ROI** = 屬於某個 group 的量測方框

改動涉及這兩者的關係時要格外小心：`gid` 是群組身分，`rid` 是 ROI 身分，
兩者都必須全域唯一。

---

## 1. 架構鐵則

### `pear/core/` 不准 import Qt

`core/` 是純 NumPy + OpenCV，**零 Qt import**。理由：那是唯一能 headless 測試
的部分，而 UI 測試需要 offscreen 平台外加一堆系統函式庫（`libEGL` 之類）。
一旦 `core/` 沾到 Qt，`tests/test_core.py` 就在沒有圖形環境的機器上跑不了。

計算放 `core/`，畫面放 `ui/`。新的統計量寫進 `core/analysis.py` 或
`core/attributes.py`，並在 `tests/test_core.py` 補測試。

### 分析要跑在 UI thread 之外

`compute_analysis()` 是純函式，透過 `QRunnable` 丟到 thread pool。丟之前一定要
先 `snapshot()` 深拷貝模型 —— worker 拿到的不能是使用者還在編輯的那份物件。

### 所有 reduction 都要防退化輸入

空 patch、單一元素、std ≈ 0 —— 這些在實際操作中天天發生（使用者剛放下第一個
框）。回傳 `None` 或 0，**不要 raise**。既有的函式都是這樣寫的，照做。

### 影像 IO 走 `np.fromfile` + `cv2.imdecode`

**不要用 `cv2.imread`。** 使用者的路徑含中文，`imread` 在那些路徑上會靜靜地回
傳 None。

---

## 2. 每次改完程式碼：重產搬運用的單檔包

**規則：任何進到 `git ls-files` 的檔案改動之後，都要重產 `bundle/pear_bundle.py`
並一起 commit。**

```bash
git add -A && python tools/make_text_bundle.py && git add -A
```

### 為什麼

公司環境**下載不了東西**：`.zip` 這個類別被擋（不只 GitHub 的 `codeload`，換
來源也一樣），proxy 也不讓 Python 逐檔抓。剩下唯一的通道是「在 GitHub 上看得到
檔案 → 按複製鈕 → 貼進記事本」。

所以 `bundle/pear_bundle.py` 是**整個 repo 打包成的一個純文字 `.py`**，它自己解
得開。那台機器拿程式碼只有這一條路。同樣的做法見姊妹 repo
[`d4t`](https://github.com/hxlub0905-cmyk/d4t) 的 `tools/make_text_bundle.py`，
這支是照著它的慣例寫的。

### 忘了重產會怎樣

**在這台機器上沒有任何症狀。** 症狀出現在另一台機器上，而且是「功能沒有生效」
或「解出來的程式碼是舊的」—— 最難查的那種。所以 `tests/test_bundle.py` 有一支
測試會在包過期時變紅，錯誤訊息就是上面那行指令。**不要靠記性，靠測試。**

### 這個包的格式為什麼長這樣（不要「順手優化」掉）

| 決定 | 理由 |
|---|---|
| **不壓縮、不 base64** | base64 對 DLP 來說是「看不懂的東西」，而看不懂通常等於擋掉。repo 全是純文字，本來就不需要編碼 |
| **以「行數」而非「位元組數」框住每個檔案** | 傳輸途中 LF 會被換成 CRLF（記事本、郵件過濾器）。用位元組數的話**第一個檔案之後全部**對不上，看起來像整包壞掉 |
| **資料區每一行前面加 `#`** | Python 執行前會先編譯整個檔案。資料區若是裸文字，它會去解析別人的檔案內容然後 SyntaxError |
| **每個檔案帶 git blob SHA-1** | 被動過要當場講出來，而不是讓人拿到一份安靜壞掉的程式碼 |
| **`bundle/` 自己排除在外** | 不排掉的話每打一次包，repo 就多裝一份上一次的包，指數成長 |

`--split` 已經備好但目前用不到（包約 215 KB，GitHub 檔案瀏覽頁的上限是 1 MB）。
真的長大再說。

---

## 3. 改完要跑的東西

```bash
python -m pytest tests/test_core.py -q          # headless，不需要圖形環境
QT_QPA_PLATFORM=offscreen python -m pytest -q   # 全部（含 UI smoke）
```

UI 測試在沒有圖形環境的機器上需要：
`apt-get install -y libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1`。

**新功能一定要有測試。** 計算的部分進 `tests/test_core.py`（快、無 Qt），畫面
的部分進 `tests/test_ui_smoke.py`（記得呼叫 `chart.grab()` 之類真的去跑
painter —— 只建構 widget 不會執行 `paintEvent`，繪圖的 bug 會整個漏掉）。

---

## 4. 圖表：新增一種圖的時候

`DistributionChart` 全部用 QPainter 手繪，**沒有繪圖函式庫相依**。維持這樣。

- 新的圖表類型 → 在 `set_data` 的 `ctype` 加一個值、在 `paintEvent` 加一個分支、
  寫一個 `_paint_<type>` 方法，然後在 `AnalysisPanel` 加一顆 toggle 按鈕。
- **軸刻度用 `_fmt_span`，不要用 `_fmt`。** `_fmt` 是 3 位有效數字，資料很平的
  時候（正好是均勻性分析最在意的情況）五個刻度會印出一模一樣的字。
- **左側 gutter 要依實際文字寬度算**，不要寫死 —— 不然 `127.735` 會被切掉開頭。
- **同一張圖裡不同意義的線要用不同顏色。** 資料點、profile 線、趨勢線、參考線
  各自一個顏色，而且**參考線畫在底層、資料畫在上層**（反過來的話趨勢線會蓋掉它
  本來要被拿來比較的那條 profile）。

---

## 5. 語言

程式碼、docstring、註解、commit message 用**英文**（跟既有的一致）。
`CLAUDE.md` 與 `docs/` 底下給使用者看的操作說明用**繁體中文**。
跟使用者對話用**繁體中文**。
