#!/usr/bin/env python3
# PEAR 單檔純文字打包 — 沿用 d4t 的 tools/make_text_bundle.py 慣例。
"""把整個 repo 打成**一個純文字 .py 檔**，那個檔案自己解得開。

什麼時候需要這個
----------------
公司環境擋掉下載：`.zip` 這個類別被擋（不只 GitHub 的 `codeload`，換來源也一
樣），proxy 也不讓 Python 逐檔抓。剩下唯一能過的通道是「在 GitHub 上看得到檔
案、按複製鈕、貼進記事本」—— 所以要能用**一個純文字檔**搬完整包程式碼。

所以這支產出的東西**沒有任何壓縮、也不用 base64**：每個檔案的內容原封不動地
一行一行躺在裡面，記事本打開就讀得到。base64 對 DLP 來說是「看不懂的東西」，
而看不懂通常等於擋掉；PEAR 本來就全部是純文字，沒有編碼的必要。

（d4t 的同名工具有 ``--compress``，因為那個 repo 長到 900 KB 以上、超過 GitHub
檔案瀏覽頁 1 MB 的顯示上限。PEAR 目前約 250 KB，一個純文字檔綽綽有餘，所以這
裡不做壓縮 —— 真的長大了再加，`--split` 已經備好。）

怎麼用
------
    python tools/make_text_bundle.py            # 產 bundle/pear_bundle.py
    python tools/make_text_bundle.py --out X.py
    python tools/make_text_bundle.py --split 400   # 每批最多 400 KB

拿到 `pear_bundle.py` 的人：

    python pear_bundle.py                      # 解到 .\\pear\\
    python pear_bundle.py --dest D:\\tools
    python pear_bundle.py --list               # 只列出裡面有什麼，不寫檔

格式為什麼是「行數」而不是「位元組數」
--------------------------------------
這個檔案會經過瀏覽器複製、記事本另存、郵件附件…… 任何一步都可能把 LF 換成
CRLF。用位元組數的話那一換整包就對不起來，而且錯誤會發生在**第一個檔案之後的
全部檔案**上，看起來像整包壞掉。用行數則對換行符號免疫 —— 解開時用 Python 的
文字模式讀（它把 CRLF 讀成 LF），所以來回一趟仍然逐位元組相同。前提是 repo 裡
全部是 LF + UTF-8，這支會在打包前檢查，不合就拒絕產出。

每個檔案都帶 **git blob SHA-1**，解開時逐檔驗 —— 傳輸途中被動到要當場講出來，
而不是讓使用者拿到一份安靜壞掉的程式碼。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from typing import List, Optional, Tuple

#: 不進包的目錄。`bundle/` 是產出物自己 —— 不排掉的話每打一次包，repo 就多裝
#: 一份上一次的包，而且是指數成長。
EXCLUDE_DIRS = ("bundle", ".github")

#: 資料區的分隔行。解包時找的是**整行剛好等於它**的那一行 —— 而資料區的每一行
#: 都被加了 '#'，所以就算某個檔案的內容裡出現這個字串（這支自己就在 repo 裡，
#: 源碼中當然有），也永遠不會剛好相等。加 '#' 因此同時解決兩個問題：整個檔案
#: 仍然是合法的 Python，而分隔行不會被誤認。
SENTINEL = "# ==== PEAR-BUNDLE-DATA ==== 以下是資料，不要編輯 ===="

#: 解包程式（放在產出檔案的最前面）。它自己也是這份 bundle 的一部分，所以刻意
#: 寫短、只用標準函式庫、而且看得完 —— 使用者要能在跑之前先讀一遍。
EXTRACTOR = '''#!/usr/bin/env python3
# PEAR 單檔純文字包（由 tools/make_text_bundle.py 產生）。
"""整個 PEAR repo 就在這個檔案裡，一行一行的純文字，沒有壓縮、沒有編碼。

為什麼是這種形式：公司政策擋掉 .zip 這個類別，proxy 也不讓 Python 逐檔抓 ——
能過的只剩「一個純文字檔」。你可以用記事本打開它，往下捲就看得到每個檔案。

    python %(name)s              # 解到 .\\\\pear\\\\
    python %(name)s --dest D:\\\\tools
    python %(name)s --list       # 只看裡面有什麼，不寫任何檔案

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

SENTINEL = "%(sentinel)s"
PART, N_PARTS = %(part)d, %(n_parts)d   # 這是第幾批 / 共幾批（1/1 = 沒有分批）
TOTAL = %(total)d                       # 整個 repo 有幾個檔案，不是這一批有幾個


def blob_sha(data: bytes) -> str:
    """git 算 blob SHA 的方式："blob <長度>\\\\0" + 內容。"""
    h = hashlib.sha1()
    h.update(b"blob %%d\\0" %% len(data))
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
        yield sha, path, "\\n".join(body).encode("utf-8")
        i += 1 + n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Unpack the PEAR text bundle.")
    ap.add_argument("--dest", default="pear", help="解到哪個資料夾（預設 .\\\\pear）")
    ap.add_argument("--list", action="store_true", help="只列出內容，不寫檔")
    a = ap.parse_args(argv)

    # 用文字模式讀自己：Python 把 CRLF 讀成 LF，所以這個檔案就算在傳輸途中被換
    # 過行尾也解得開（格式用「行數」而不是「位元組數」正是為了這件事）。
    with open(os.path.abspath(__file__), "r", encoding="utf-8") as f:
        lines = f.read().split("\\n")
    try:
        start = lines.index(SENTINEL) + 1
    except ValueError:
        print("X 找不到資料區 —— 這個檔案被截斷了，或不是完整的 bundle。")
        return 2

    items = list(entries(lines[start:]))
    if not items:
        print("X 資料區是空的 —— 這個檔案被截斷了。")
        return 2
    print("這個包裡有 %%d 個檔案。" %% len(items))
    if a.list:
        for _sha, path, data in items:
            print("  %%8d  %%s" %% (len(data), path))
        return 0

    dest = os.path.abspath(a.dest)
    print("解到  : %%s" %% dest)
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
        print("X %%d 個檔案的內容跟它自己的 SHA 對不上：" %% len(bad))
        for path in bad[:12]:
            print("    %%s" %% path)
        print("")
        print("  這個檔案在傳輸途中被動過（編輯器另存、郵件過濾器改寫都會這樣）。")
        print("  請重新取得一份，不要用編輯器打開後另存。這份程式碼不完整，不要用。")
        return 1

    print("OK %%d 個檔案都解開了，SHA 全部對得上。" %% done)

    if N_PARTS > 1:
        print("")
        print("這是第 %%d 批 / 共 %%d 批，整個 repo 有 %%d 個檔案。"
              %% (PART, N_PARTS, TOTAL))
        print("把其他批也貼進來執行（順序不重要，重複執行也沒關係）。")
        return 0

    print("")
    print("下一步：")
    print("  cd %%s" %% dest)
    print("  pip install -r requirements.txt")
    print("  python -m pear")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blob_sha(data: bytes) -> str:
    h = hashlib.sha1()                                # noqa: S324 — git 的格式
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def collect(root: str = "") -> List[Tuple[str, bytes]]:
    """``git ls-files`` 的每個檔案（路徑, 位元組）。

    順便擋掉兩種會讓「用行數打包」失效的東西：CRLF 與非 UTF-8。拒絕產出比產出
    一個解不開的包好 —— 後者要等收到的人才會發現。
    """
    root = root or repo_root()
    out = subprocess.run(["git", "ls-files"], cwd=root, check=True,
                         stdout=subprocess.PIPE).stdout.decode("utf-8")
    items = []
    for rel in sorted(p for p in out.split("\n") if p.strip()):
        if any(rel.startswith(d + "/") for d in EXCLUDE_DIRS):
            continue
        with open(os.path.join(root, rel.replace("/", os.sep)), "rb") as f:
            data = f.read()
        if b"\r" in data:
            raise SystemExit(
                "%s 含 CR（CRLF 或裸 CR）—— 以行數為單位的打包會弄壞它。"
                "先把它轉成 LF。" % rel)
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise SystemExit("%s 不是 UTF-8 —— 這個格式只裝純文字。" % rel)
        items.append((rel, data))
    return items


def _data_lines(items: List[Tuple[str, bytes]]) -> List[str]:
    """資料區。"""
    out: List[str] = []
    for rel, data in items:
        body = data.decode("utf-8").split("\n")
        out.append("#F %s %d %s" % (blob_sha(data), len(body), rel))
        # **每一行都要變成註解。** Python 在跑任何東西之前會先編譯整個檔案，所以
        # 資料區不能是裸的文字 —— 不然它會去解析別的檔案的內容然後語法錯誤。加
        # 一個 '#' 比塞進三引號字串安全：檔案內容裡本來就可能有三個引號。
        out.extend("#" + line for line in body)
    return out


def build(out_name: str = "pear_bundle.py", root: str = "",
          items: Optional[List[Tuple[str, bytes]]] = None,
          part: int = 1, n_parts: int = 1, total_files: int = 0) -> str:
    items = collect(root) if items is None else items
    parts = [EXTRACTOR % {"name": out_name, "sentinel": SENTINEL,
                          "part": part, "n_parts": n_parts,
                          "total": total_files or len(items)}, SENTINEL]
    parts.extend(_data_lines(items))
    return "\n".join(parts) + "\n"


def _slice(items: List[Tuple[str, bytes]], limit: int
           ) -> List[List[Tuple[str, bytes]]]:
    """依大小切成幾批。``limit`` 是每批的內容上限（位元組）。"""
    out: List[List[Tuple[str, bytes]]] = [[]]
    size = 0
    for rel, data in items:
        if size + len(data) > limit and out[-1]:
            out.append([])
            size = 0
        out[-1].append((rel, data))
        size += len(data)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Pack the repo into one plain-text self-extracting .py")
    ap.add_argument("--out", default=os.path.join("bundle", "pear_bundle.py"),
                    help="輸出檔名（分批時會變成 ..._part1of3.py）")
    ap.add_argument("--split", type=int, default=0, metavar="KB",
                    help=("每批最多幾 KB（0 = 不分批）。**GitHub 的檔案瀏覽頁在 "
                          "1 MB 以上不顯示內容**，那顆複製鈕也跟著消失；剪貼簿"
                          "是唯一通道時就必須分批。"))
    a = ap.parse_args(argv)

    items = collect()
    groups = _slice(items, a.split * 1024) if a.split else [items]
    out_dir = os.path.dirname(os.path.abspath(a.out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    stem, ext = os.path.splitext(a.out)
    n_parts = len(groups)

    for i, group in enumerate(groups, 1):
        name = a.out if n_parts == 1 else "%s_part%dof%d%s" % (stem, i, n_parts, ext)
        text = build(os.path.basename(name), items=group, part=i,
                     n_parts=n_parts, total_files=len(items))
        tmp = name + ".tmp"                           # atomic
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, name)
        print("%s：%d 個檔案、%.0f KB"
              % (name, len(group), len(text.encode("utf-8")) / 1024))
    if n_parts > 1:
        print("\n共 %d 批、%d 個檔案。每一批都可以單獨執行，順序不重要，"
              "重複執行也沒關係。" % (n_parts, len(items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
