# -*- coding: utf-8 -*-
"""生成 prompts 站的数据契约文件

1. manifest.json（站点根）—— fetch/verify 契约：每条记录 full_url / full_path
2. data/dims.json —— 图片宽高缓存 {file: [w, h]}，构建时无需读图片文件
   （CI 与全新克隆环境没有图片，构建必须能仅凭入库数据完成）

输入: data/prompts_<key>.json（import_youmind.py 产出，每模型一份，已入库；
      本地需已有图片才能算宽高）
产出: manifest.json（轻量，入库）+ data/dims.json（入库）
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sites/prompts
ROOT = os.path.dirname(os.path.dirname(HERE))                       # 仓库根
sys.path.insert(0, os.path.join(ROOT, "shared"))
from assets import image_dims  # noqa: E402

OUT = os.path.join(HERE, "manifest.json")
DIMS = os.path.join(HERE, "data", "dims.json")


def thumb_of(path):
    """img/<key>/x.jpg → thumbs/<key>/x.jpg（缩略图与原图同名同层）"""
    parts = path.split("/")
    return "/".join(["thumbs"] + parts[1:])


def load_rows():
    """合并所有模型的数据文件；按 file 去重，重复时保留先出现的。"""
    files = sorted(glob.glob(os.path.join(HERE, "data", "prompts_*.json")))
    if not files:
        raise SystemExit("✗ 找不到 data/prompts_*.json，先运行 import_youmind.py")
    rows, seen = [], set()
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        add = 0
        for r in data:
            key = r.get("file")
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(r)
            add += 1
        print(f"  {os.path.basename(path):<24}{add:>7} 条")
    return rows


def main():
    rows = load_rows()
    bad = [r.get("file") for r in rows if not r.get("url") or not r.get("file")]
    if bad:
        raise SystemExit(f"✗ {len(bad)} 条记录缺 url/file，例如 {bad[:3]}")
    manifest = []
    for r in rows:
        manifest.append({
            "id": r["originId"], "title": r.get("title", ""),
            "full_url": r["url"], "full_path": r["file"],
            "thumb_url": r.get("thumbUrl") or r["url"],
            "thumb_path": thumb_of(r["file"]),
        })
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ manifest.json {len(manifest)} 条 · {os.path.getsize(OUT) / 1048576:.1f} MB")

    # 宽高缓存：已有结果直接复用，只补缺失的（幂等，重跑只读新增图片的文件头）
    dims = {}
    if os.path.exists(DIMS):
        with open(DIMS, encoding="utf-8") as f:
            dims = json.load(f)
    todo = [r for r in rows if r["file"] not in dims]
    miss = 0
    for i, r in enumerate(todo):
        p = os.path.join(HERE, r["file"])
        d = image_dims(p) if os.path.exists(p) else None
        if d:
            dims[r["file"]] = list(d)
        else:
            miss += 1
        if (i + 1) % 5000 == 0:
            print(f"  dims {i + 1}/{len(todo)}")
    with open(DIMS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dims, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ dims.json {len(dims)} 条（本次新增 {len(todo)}，缺失 {miss}）· "
          f"{os.path.getsize(DIMS) / 1048576:.2f} MB")


if __name__ == "__main__":
    main()
