# -*- coding: utf-8 -*-
"""探缺图：把盘上已经不存在的资产标成 missing。

只改 asset.status，绝不碰 item.deleted_at —— 文件丢了和「我不想看它」是两件事。

用法:
  python index/verify.py
  python index/verify.py --root <dir>
"""
from __future__ import annotations

import argparse
import os
import sys

import store


def verify(root, db_path):
    root = os.path.abspath(root)
    conn = store.connect(db_path)
    missing, ok = [], 0
    for asset_id, path, status in store.asset_paths(conn):
        if os.path.isfile(os.path.join(root, path)):
            ok += 1
            if status != "ok":
                store.set_asset_status(conn, asset_id, "ok")
        else:
            missing.append(path)
            store.set_asset_status(conn, asset_id, "missing")
    conn.commit()
    conn.close()
    return {"checked": ok + len(missing), "ok": ok, "missing": len(missing), "missing_paths": missing[:20]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db = args.db or os.path.join(args.root, "gallery.db")
    result = verify(args.root, db)
    print(f"检查 {result['checked']} 个资产：{result['ok']} 个在盘，{result['missing']} 个缺失")
    for path in result["missing_paths"]:
        print(f"  缺失 {path}")


if __name__ == "__main__":
    main()
