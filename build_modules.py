# -*- coding: utf-8 -*-
"""從 notebook 抽出所有 %%writefile 的內容，一次生出整套系統。

    python build_modules.py

**這是給講師用的捷徑，不是給學員用的。**

正常上課流程是學員自己執行 00~05，用 %%writefile 一步步把東西寫出來。
但講師想直接示範完成品（例如第一堂課先讓大家看到成果），
或是想確認教材改動後還跑不跑得動時，用這個腳本會快很多。

它產生的檔案包含：
  movieapp/  六個模組（地基兩個 + 學員寫的四個）
  server/    Django 服務與前端網頁
  requirements.txt、.env.example

換句話說，**這包教材只要留下 notebooks/ 就能完整重建**。
腳本只是讀取 notebook 的檔案內容，不會執行 notebook，所以不需要 Jupyter。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTEBOOKS = ROOT / "notebooks"


def extract(notebook_path):
    """回傳這本 notebook 裡所有 %%writefile 產生的檔案。"""
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    written = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", ""))
        if not source.startswith("%%writefile"):
            continue
        header, _, body = source.partition("\n")
        target = header.replace("%%writefile", "").strip()
        # notebook 裡的路徑是相對於 notebooks/ 的
        path = (NOTEBOOKS / target).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
        written.append(path)
    return written


def main():
    if not NOTEBOOKS.exists():
        print(f"找不到 {NOTEBOOKS}")
        return 1

    total = 0
    for notebook_path in sorted(NOTEBOOKS.glob("*.ipynb")):
        for path in extract(notebook_path):
            print(f"  {notebook_path.name:26} -> {path.relative_to(ROOT)}"
                  f"  ({path.stat().st_size / 1024:.1f} KB)")
            total += 1

    if total == 0:
        print("沒有找到任何 %%writefile 的內容")
        return 1

    print(f"\n共產生 {total} 個檔案。接下來：")
    print("  cd server && python manage.py runserver 8008 --noreload")
    print("  然後打開 http://127.0.0.1:8008")
    return 0


if __name__ == "__main__":
    sys.exit(main())
