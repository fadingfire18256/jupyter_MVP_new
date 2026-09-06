"""執行環境設定：金鑰載入、環境自我檢查、表格排版。

這個檔案是整包教材的地基，00~05 每一本 notebook 開頭都會呼叫 setup()。

本檔案由 notebooks/00_環境設定.ipynb 的 %%writefile 產生。
要修改請回去改那一格，不要直接編輯這裡。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unicodedata
from pathlib import Path

# 專案根目錄（jupyter_MVP/）
PKG_DIR = Path(__file__).resolve().parent
ROOT = PKG_DIR.parent

# 金鑰的環境變數名稱
TMDB_KEY_NAME = "TMDB_READ_ACCESS_TOKEN"
GEMINI_KEY_NAME = "GEMINI_API_KEY"

# 哪個模組是哪一本 notebook 產生的（用來給出有用的錯誤訊息）
_MODULE_OWNER = {
    "sources": "01_影城API.ipynb",
    "tmdb": "02_TMDB.ipynb",
    "merge": "03_資料整合.ipynb",
    "gemini": "04_Gemini對話.ipynb",
}


# --------------------------------------------------------------------------
# 金鑰
# --------------------------------------------------------------------------
def env_path() -> Path:
    """.env 的位置。整個專案只有這裡決定它在哪。"""
    return ROOT / ".env"


def load_env(path: str | Path | None = None, override: bool = False) -> dict:
    """讀取 .env 檔並寫進 os.environ。

    極簡實作，不依賴 python-dotenv —— 只認 KEY=VALUE，# 開頭是註解。
    .env 不存在也沒關係，get_key() 會在需要時當場詢問。
    """
    target = Path(path) if path else env_path()
    if not target.exists():
        return {}

    loaded = {}
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or not os.environ.get(key):
            os.environ[key] = value
        loaded[key] = value
    return loaded


def _ask_key(name: str) -> str:
    """.env 沒有金鑰時，當場請使用者輸入（輸入內容不會留在 notebook 輸出裡）。"""
    try:
        import getpass

        value = getpass.getpass(f"請貼上 {name}（輸入不會顯示）：").strip()
    except Exception:
        return ""
    if value:
        os.environ[name] = value
    return value


# getpass 的提示只有「坐在 notebook 前面的人」看得到。
# 網頁服務跳這個提示，等於讓那個 HTTP 請求一直卡著等一個
# 沒有人看得到的輸入框 —— 所以服務啟動時會把它關掉。
_INTERACTIVE = True


def set_interactive(on: bool) -> None:
    """開關「找不到金鑰時當場詢問」。server/cinema/apps.py 會關掉它。"""
    global _INTERACTIVE
    _INTERACTIVE = bool(on)


def get_key(name: str, required: bool = True) -> str:
    """取得金鑰。順序：環境變數 -> .env -> 當場輸入。"""
    load_env()
    value = os.environ.get(name, "").strip()
    if value:
        return value
    if _INTERACTIVE:
        value = _ask_key(name)
    if not value and required:
        raise RuntimeError(
            f"缺少 {name}。兩種解法擇一：\n"
            f"  1. 在專案根目錄的 .env 填入 {name}=...\n"
            f"  2. 重跑這一格，在提示視窗貼上金鑰"
        )
    return value


def tmdb_token(required: bool = True) -> str:
    return get_key(TMDB_KEY_NAME, required=required)


def gemini_key(required: bool = True) -> str:
    return get_key(GEMINI_KEY_NAME, required=required)


# --------------------------------------------------------------------------
# 讓使用者換成自己的金鑰
# --------------------------------------------------------------------------
def has_key(name: str) -> bool:
    """這把金鑰現在有沒有值？不會跳出任何提示，純粹查詢。"""
    load_env()
    return bool(os.environ.get(name, "").strip())


def key_status() -> dict:
    """哪幾把金鑰已經設定好了。

    **只回布林值。** 金鑰本身絕不往外送 —— 網頁前端只需要知道
    「有沒有設定」，不需要也不應該拿到值。
    """
    return {"tmdb": has_key(TMDB_KEY_NAME), "gemini": has_key(GEMINI_KEY_NAME)}


_ENV_HEADER = [
    "# 這個檔案放金鑰，內容不會顯示在 notebook 的輸出裡。",
    "#",
    "# 可以直接編輯，也可以在網頁右上角的「API 金鑰」按鈕裡填 ——",
    "# 兩條路寫的是同一個檔案。",
    "",
]


def save_keys(**values) -> Path:
    """把金鑰寫回 .env，並立刻在目前這個行程生效。

    只換掉指定的那幾行，其他內容原封不動 —— 直接整份蓋掉的話，
    檔案裡的說明註解會在學員存第一次金鑰時就消失。

    值給空字串代表清掉那一把。回傳寫入的檔案路徑。
    """
    target = env_path()
    if target.exists():
        lines = target.read_text(encoding="utf-8").splitlines()
    else:
        # 檔案不存在時順手補上抬頭，不然學員存完金鑰打開來會是光禿禿兩行
        lines = list(_ENV_HEADER)

    for name, value in values.items():
        value = str(value or "").strip()
        for index, raw in enumerate(lines):
            line = raw.strip()
            if line.startswith("#") or "=" not in line:
                continue
            if line.partition("=")[0].strip() == name:
                lines[index] = f"{name}={value}"
                break
        else:
            lines.append(f"{name}={value}")
        # 同時更新環境變數，這樣不必重啟服務就生效
        os.environ[name] = value

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


# --------------------------------------------------------------------------
# 每本 notebook 的開場
# --------------------------------------------------------------------------
def setup(requires=()) -> None:
    """每本 notebook 第一格呼叫：確認 sys.path、載入 .env、檢查前置模組。

    requires 列出這本 notebook 需要、但由前面 notebook 產生的模組。
    例如 03 需要 setup(requires=["sources", "tmdb"])，
    學員若跳著執行會得到明確的指示，而不是看不懂的 ImportError。
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    load_env()

    missing = [m for m in requires if not (PKG_DIR / f"{m}.py").exists()]
    if missing:
        lines = [
            f"  - movieapp/{m}.py  ->  請先完整執行 {_MODULE_OWNER.get(m, '前面的 notebook')}"
            for m in missing
        ]
        raise RuntimeError("缺少前置模組，這本 notebook 還不能跑：\n" + "\n".join(lines))

    print(f"環境就緒｜根目錄：{ROOT}")


# --------------------------------------------------------------------------
# 表格排版小工具
# --------------------------------------------------------------------------
def display_width(text) -> int:
    """字串在終端機／notebook 裡佔幾格。

    中文字是全形，一個字佔兩格，但 len() 只算一個字元。
    直接用 ljust() 排版中英混雜的表格會歪掉，所以要另外算。
    """
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(text))


def pad(text, width: int, align: str = "left") -> str:
    """把字串補到指定的顯示寬度（中文字算兩格）。"""
    text = str(text)
    space = " " * max(0, width - display_width(text))
    return space + text if align == "right" else text + space


# --------------------------------------------------------------------------
# 環境自我檢查
# --------------------------------------------------------------------------
def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def doctor() -> bool:
    """印出環境檢查清單。全部通過回傳 True。

    課堂上先跑這一格，就知道自己的環境有沒有問題，
    不用等到第三本 notebook 才發現套件沒裝。
    """
    rows = []

    ok_py = sys.version_info >= (3, 9)
    rows.append((ok_py, "Python 版本", f"{sys.version.split()[0]}（需要 3.9 以上）"))

    for pkg, label in [
        ("requests", "requests 套件"),
        ("django", "Django 套件"),
        ("corsheaders", "django-cors-headers"),
        ("pandas", "pandas 套件"),
    ]:
        rows.append((_has_module(pkg), label,
                     "已安裝" if _has_module(pkg) else "缺少，請執行 %pip install -r ../requirements.txt"))

    for mod in ("config", "http"):
        exists = (PKG_DIR / f"{mod}.py").exists()
        rows.append((exists, f"movieapp/{mod}.py",
                     "已產生" if exists else "尚未產生（由 00_環境設定.ipynb 寫出）"))

    for mod, owner in _MODULE_OWNER.items():
        exists = (PKG_DIR / f"{mod}.py").exists()
        rows.append((exists, f"movieapp/{mod}.py", "已產生" if exists else f"尚未產生（由 {owner} 寫出）"))

    load_env()
    for label, key in [("TMDB 金鑰", TMDB_KEY_NAME), ("Gemini 金鑰", GEMINI_KEY_NAME)]:
        val = os.environ.get(key, "").strip()
        rows.append((bool(val), label, f"已設定（{val[:6]}…）" if val else "未設定，需要時會提示輸入"))

    page = ROOT / "server" / "static" / "index.html"
    rows.append((page.exists(), "前端 index.html",
                 "已產生" if page.exists() else "尚未產生（由 05_接成服務.ipynb 寫出）"))

    width = max(display_width(label) for _, label, _ in rows)
    print("環境檢查")
    print("=" * (width + 40))
    for ok, label, detail in rows:
        print(f"  {'[OK]' if ok else '[--]'}  {pad(label, width)}  {detail}")
    print("=" * (width + 40))

    hard_fail = not ok_py or not _has_module("requests")
    print("結論：" + ("環境沒問題，可以開始。" if not hard_fail
                    else "有必要項目未通過，請先處理上面標示 [--] 的項目。"))
    return not hard_fail
