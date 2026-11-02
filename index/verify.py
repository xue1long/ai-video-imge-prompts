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
    missing, ok, remote = [], 0, 0
    for asset_id, path, status in store.asset_paths(conn):
        if os.path.isfile(os.path.join(root, path)):
            ok += 1
            if status != "ok":
                store.set_asset_status(conn, asset_id, "ok")
            continue
        # 本地没有这个文件：站图可能只留在上游（本地省掉了原图档）。
        # 有登记的上游地址就还能取到，不算缺图；没有才算真的丢了。
        if store.derivative_url(conn, path):
            remote += 1
            if status != "ok":
                store.set_asset_status(conn, asset_id, "ok")
            continue
        missing.append(path)
        store.set_asset_status(conn, asset_id, "missing")

    # 派生图（缩略图 / 中图 / 原图档）也要查：原图档被整档删掉是这次改造的
    # 预期结果，只查 asset 表的话，派生图全没了也报「一切正常」。
    deriv_missing = []
    for path, kind in store.derivative_paths(conn):
        if os.path.isfile(os.path.join(root, path)):
            continue
        if store.derivative_url(conn, path):
            remote += 1
            continue
        deriv_missing.append((kind, path))

    conn.commit()
    conn.close()
    return {"checked": ok + remote + len(missing) + len(deriv_missing), "ok": ok,
            "remote": remote, "missing": len(missing) + len(deriv_missing),
            "missing_paths": missing[:20],
            "missing_derivatives": [f"{k} {p}" for k, p in deriv_missing[:20]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db = args.db or os.path.join(args.root, "gallery.db")
    result = verify(args.root, db)
    print(f"检查 {result['checked']} 个资产：{result['ok']} 个在盘，"
          f"{result['remote']} 个只在上游，{result['missing']} 个缺失")
    for path in result["missing_paths"]:
        print(f"  缺失 {path}")
    for path in result.get("missing_derivatives", []):
        print(f"  缺失派生图 {path}")


if __name__ == "__main__":
    main()
