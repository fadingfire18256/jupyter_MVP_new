"""從來源 Notebook 重建教材；--check 只比較，不寫檔、不執行儲存格。"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def generated_sources(root=ROOT):
    root = Path(root).resolve()
    notebooks = root / "notebooks"
    seen = set()
    for notebook in sorted(notebooks.glob("*.ipynb")):
        data = json.loads(notebook.read_text(encoding="utf-8"))
        for cell in data.get("cells", []):
            source = "".join(cell.get("source", []))
            if cell.get("cell_type") != "code" or not source.startswith("%%writefile"):
                continue
            header, _, body = source.partition("\n")
            parts = header.split()
            if len(parts) != 2 or parts[0] != "%%writefile":
                raise ValueError(f"{notebook.name}：請使用 %%writefile 相對路徑，不使用追加選項")
            target = (notebooks / parts[1]).resolve()
            if not target.is_relative_to(root) or target == root or target.is_relative_to(notebooks):
                raise ValueError(f"{notebook.name}：產出路徑超出教材允許範圍")
            if target in seen:
                raise ValueError(f"重複的產出路徑：{target.relative_to(root)}")
            seen.add(target)
            yield notebook, target, body.rstrip("\n") + "\n"


def build(check=False, root=ROOT):
    root = Path(root).resolve()
    sources = list(generated_sources(root))
    if not sources:
        raise ValueError("沒有找到 %%writefile 儲存格")
    mismatches = []
    for notebook, target, content in sources:
        same = target.is_file() and target.read_text(encoding="utf-8") == content
        if check:
            if not same:
                mismatches.append(target)
                print(f"不同步：{target.relative_to(root)} ← {notebook.name}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
            print(f"{notebook.name} → {target.relative_to(root)}")
    if check:
        print(f"比較 {len(sources)} 個產出檔案；不同步 {len(mismatches)} 個。")
    else:
        print(f"已重建 {len(sources)} 個檔案；來源 Notebook 未執行，也不會呼叫外部 API。")
    return 1 if mismatches else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="檢查產出是否與 Notebook 一致，不寫入")
    args = parser.parse_args()
    raise SystemExit(build(check=args.check))
