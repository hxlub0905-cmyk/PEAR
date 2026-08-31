# 在沒有 git、也下載不了東西的機器上安裝 PEAR

適用情境：**公司機不能用 git，而且下載被擋** —— `.zip` 這個類別過不了，proxy
也不讓 Python 逐檔抓，但**看得到 GitHub 上的檔案而且可以按複製鈕**。

整個 PEAR repo 只有純文字檔（`.py` / `.md` / `.toml` / `.txt` / `.spec`），
沒有任何執行檔或二進位檔，所以不需要 git 也能跑。

---

## 1. 用剪貼簿搬整包（一個檔案）

`bundle/pear_bundle.py` —— **一次複製就搬完整個 repo**（目前約 215 KB、19 個
檔案）。它是純文字，記事本打開就讀得到內容，沒有壓縮也沒有編碼。

1. 瀏覽器打開
   <https://github.com/hxlub0905-cmyk/PEAR/blob/main/bundle/pear_bundle.py>
2. 按檔案右上角的**複製鈕**（或直接複製 raw：把網址的 `blob` 換成 `raw`）
3. 貼進記事本，存成 `pear_bundle.py`
4. `python pear_bundle.py --list` ← 先看它會寫哪些檔案，**不寫任何東西**
5. `python pear_bundle.py` ← 真的解開

> ### ⚠ 記事本另存的時候會偷加 `.txt`
>
> 它的「存檔類型」預設是「文字文件 (\*.txt)」，所以你打 `pear_bundle.py` 會被
> 存成 `pear_bundle.py.txt` —— 而檔案總管預設**把已知副檔名藏起來**，看起來完
> 全正常，只有 Python 會說「No such file or directory」。
>
> 避開的方式：另存對話框裡把**存檔類型改成「所有檔案 (\*.\*)」**，或是**檔名
> 前後加引號**：`"pear_bundle.py"`。
>
> 已經存錯了也不用改名 —— Python 不在乎副檔名，直接
> `python pear_bundle.py.txt` 就會動。

每個檔案都帶 **git blob SHA-1**，解開時逐檔驗過才落地。傳輸途中被動到（編輯器
另存、郵件過濾器改寫）會當場報出來，不會讓你拿到一份安靜壞掉的程式碼。

**行尾被換成 CRLF 不影響**：這個格式用「行數」而不是「位元組數」框住每個檔案，
正是為了這件事。

---

## 2. 裝相依套件

```
cd pear
pip install -r requirements.txt
```

需要 `PySide6`、`opencv-python`、`numpy`。

pip 也被擋的話，走離線 wheels：在有網路的機器上
`pip download -r requirements.txt -d wheels`，把 `wheels/` 搬過去（這些是二進位
檔，如果連 wheel 都搬不進去，就只能請 IT 開放），然後
`pip install --no-index --find-links wheels -r requirements.txt`。

---

## 3. 跑起來

```
python -m pear
```

沒有真實資料想先試用的話：

```
python examples/make_sample.py     # 產 examples/sample_field.png
python -m pear                     # 然後 Load… 那張圖
```

---

## 4. 確認解出來的東西是完整的

```
python -m pytest tests/test_core.py -q
```

這一支不需要圖形環境。全部測試（含 UI）要 `QT_QPA_PLATFORM=offscreen`，
Linux 上另外需要 `libegl1` / `libgl1` 等系統函式庫。

---

## 5. 之後要更新程式碼

重複第 1 節就好 —— 重新複製一次 `bundle/pear_bundle.py`，解到同一個資料夾會直
接覆蓋。解包是 atomic 的（先寫 `.tmp` 再 `os.replace`），中途失敗不會在磁碟上
留下半個檔案。

> 在**有 git 的那台機器**改完程式碼之後，記得重產這個包：
>
> ```
> git add -A && python tools/make_text_bundle.py && git add -A
> ```
>
> 忘了的話公司機拿到的會是舊的程式碼，而且**在開發機上完全沒有症狀**。
> `tests/test_bundle.py` 會在包過期時變紅。
