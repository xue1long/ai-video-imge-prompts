# -*- coding: utf-8 -*-
"""把素材管理器里「添加图片」挂上去的成图，导出成提示词站的覆盖层。

素材管理器（index/serve.py）把用户图收在 library/ 里，链接记在 item_asset.role='user'。
本站的数据源 prompts_<key>.json 是 import_youmind.py 的产物、会被整份重写，所以不能往
里面塞用户图；单独一份 data/user_assets.json（按 originId 归属）+ userimg/ 目录的图片，
构建时由 build_gallery.py 合并进对应分片。

用法:
  python sync_user_assets.py                 # 导出到 data/user_assets.json + userimg/
  python sync_user_assets.py --dry-run       # 只打印将要做什么，不动盘
  python sync_user_assets.py --db D:/x.db    # 指定素材管理器的库（默认仓库根 gallery.db）
  python sync_user_assets.py --prune         # 同时删掉覆盖层里已不再引用的旧图

幂等：图已存在且大小一致就跳过复制；覆盖层按 originId + ordinal 稳定排序。
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from config import USER_ASSETS, USER_IMG_DIR, USER_THUMB_DIR  # noqa: E402
from build_gallery import _ratio                              # noqa: E402


def fetch_rows(conn):
    """一条用户图一行：originId + 原图路径 + 缩略图路径 + 尺寸 + 追加顺序。"""
    sql = """
        SELECT i.ext_id            AS origin, i.id AS item_id,
               ia.ordinal          AS ordinal,
               a.path              AS path, a.width AS width, a.height AS height,
               d.path              AS thumb
        FROM item_asset ia
        JOIN item i  ON i.id = ia.item_id
        JOIN asset a ON a.id = ia.asset_id
        LEFT JOIN derivative d ON d.asset_id = a.id AND d.kind = 'thumb'
        WHERE ia.role = 'user' AND i.collection = 'prompts'
        ORDER BY i.ext_id, ia.ordinal, a.id
    """
    return [dict(r) for r in conn.execute(sql)]


def plan(rows):
    """按 originId 分组编号：u-<originId>-1/-2/…，扩展名跟原图走。"""
    out, seen = {}, {}
    for r in rows:
        origin = r["origin"] or ""
        if not origin:
            continue
        seq = seen.get(origin, 0) + 1
        seen[origin] = seq
        ext = os.path.splitext(r["path"])[1].lower() or ".jpg"
        name = f"u-{origin}-{seq}{ext}"
        out.setdefault(origin, []).append({
            "name": name,
            "file": f"{USER_IMG_DIR}/{name}",
            "thumb": f"{USER_THUMB_DIR}/{os.path.splitext(name)[0]}.webp",
            "w": r["width"] or 0,
            "h": r["height"] or 0,
            "ar": _ratio(r["width"], r["height"]) or "",
            "own": 1,
            "_src": r["path"],
            "_thumb_src": r["thumb"],
        })
    return out


def copy_if_needed(src_abs, dst_abs, dry_run):
    if not os.path.exists(src_abs):
        return "missing"
    if os.path.exists(dst_abs) and os.path.getsize(dst_abs) == os.path.getsize(src_abs):
        return "skip"
    if not dry_run:
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        shutil.copy2(src_abs, dst_abs)
    return "copy"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "gallery.db"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true",
                    help="删掉 userimg/ 下不再被覆盖层引用的文件")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"✗ 找不到素材库: {args.db}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    groups = plan(fetch_rows(conn))
    conn.close()

    if not groups:
        print("素材库里没有挂在提示词下的用户图（role=user），"
              f"覆盖层将清空。在素材管理器点「添加图片」后再跑一次。")

    stats = {"copy": 0, "skip": 0, "missing": 0, "thumb_missing": 0}
    payload = {"version": 1,
               "note": "站主自己挂到提示词下的成图。由 sync_user_assets.py 从 gallery.db 导出，"
                       "构建时按 originId 合并进分片；版权归本站，不在 CC BY 4.0 范围内。",
               "items": {}}

    for origin, files in groups.items():
        clean = []
        for f in files:
            src_abs = os.path.join(ROOT, f["_src"].replace("/", os.sep))
            dst_abs = os.path.join(HERE, f["file"].replace("/", os.sep))
            mark = copy_if_needed(src_abs, dst_abs, args.dry_run)
            stats[mark] += 1
            if mark == "missing":
                print(f"  ⚠ 原图缺失，跳过: {f['_src']}")
                continue

            thumb_src = f["_thumb_src"]
            thumb_abs = os.path.join(HERE, f["thumb"].replace("/", os.sep))
            if thumb_src:
                tsrc_abs = os.path.join(ROOT, thumb_src.replace("/", os.sep))
                tmark = copy_if_needed(tsrc_abs, thumb_abs, args.dry_run)
                if tmark == "missing":
                    stats["thumb_missing"] += 1
                    print(f"  ⚠ 缩略图缺失，卡片会退回原图: {thumb_src}")
            else:
                stats["thumb_missing"] += 1
                print(f"  ⚠ 没有缩略图记录，卡片会退回原图: {f['_src']}")

            clean.append({k: v for k, v in f.items() if not k.startswith("_")})
        if clean:
            payload["items"][origin] = clean

    out_path = os.path.join(HERE, USER_ASSETS)
    total = sum(len(v) for v in payload["items"].values())
    if args.dry_run:
        print(f"[dry-run] 将写 {USER_ASSETS}：{len(payload['items'])} 条提示词 / {total} 张图")
    else:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"✓ {USER_ASSETS}：{len(payload['items'])} 条提示词 / {total} 张图")

    if args.prune:
        keep = {f["file"] for v in payload["items"].values() for f in v}
        keep |= {f["thumb"] for v in payload["items"].values() for f in v}
        removed = 0
        base = os.path.join(HERE, USER_IMG_DIR)
        for dirpath, _dirs, names in os.walk(base):
            for n in names:
                rel = os.path.relpath(os.path.join(dirpath, n), HERE).replace(os.sep, "/")
                if rel not in keep:
                    removed += 1
                    if not args.dry_run:
                        os.remove(os.path.join(dirpath, n))
        print(f"{'[dry-run] 将删' if args.dry_run else '✓ 删'}除 {removed} 个不再引用的文件")

    print(f"复制 {stats['copy']} · 跳过 {stats['skip']} · 原图缺失 {stats['missing']} · "
          f"无缩略图 {stats['thumb_missing']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
