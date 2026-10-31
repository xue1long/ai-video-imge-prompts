# -*- coding: utf-8 -*-
"""数据库快照：批量操作前留一个可回滚的点。

比任何撤销栈都可靠——要恢复就是把文件拷回去。

用法:
  python index/snapshot.py
  python index/snapshot.py --root <dir>
"""
from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys


def snapshot(root, db_path, out_dir=None):
    root = os.path.abspath(root)
    out_dir = out_dir or os.path.join(root, "backups")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(out_dir, f"gallery-{stamp}.db")

    src_conn = sqlite3.connect(db_path)
    dst_conn = sqlite3.connect(dest)
    try:
        src_conn.backup(dst_conn)  # 用 SQLite 自己的备份接口，WAL 状态下也安全
    finally:
        dst_conn.close()
        src_conn.close()
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db = args.db or os.path.join(args.root, "gallery.db")
    dest = snapshot(args.root, db, args.out)
    size = os.path.getsize(dest) / 1024 / 1024
    print(f"快照已写入 {dest}（{size:.1f} MB）")


if __name__ == "__main__":
    main()
