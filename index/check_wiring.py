# -*- coding: utf-8 -*-
"""索引接线核对：站点清单 ↔ 索引配置 ↔ 索引实现，三者必须一致。

抓的是这一类漏改：**站点页面一切正常，但素材管理器（WebUI）里没有这条素材**。
站点清单（sites.json）、索引配置（catalog.SOURCES）、索引实现（sync.py）分散在
三个地方，加站时漏改其中任意一处，页面侧的测试全都照常通过——这一层此前没有闸门。

用法:
  python index/sync.py --force --db /tmp/gallery.db
  python index/check_wiring.py --db /tmp/gallery.db

退出码 0 = 一致；1 = 有不一致（逐条打印原因）。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import catalog  # noqa: E402


def site_ids(root):
    cfg = json.load(open(os.path.join(root, "sites.json"), encoding="utf-8"))
    sites = cfg["sites"] if isinstance(cfg, dict) else cfg
    return [s["id"] for s in sites]


def expected_items(cfg, root):
    """按配置推出该站应有的条目数。

    - 声明了 group_by：按分组数（一条内容多张图的站）
    - 有 meta_glob：按 meta 里的内容 id 去重数（prompts 站：meta 一条提示词多张成图）
    - 其余：一行一条
    """
    path = os.path.join(root, cfg["manifest"])
    rows = json.load(open(path, encoding="utf-8"))
    if cfg.get("group_by"):
        return len({r.get(cfg["group_by"]) for r in rows})
    if cfg.get("meta_glob"):
        import glob
        ids = set()
        for p in sorted(glob.glob(os.path.join(root, cfg["meta_glob"]))):
            for m in json.load(open(p, encoding="utf-8")):
                ids.add(m.get("originId") or m.get("id") or "")
        return len(ids)
    return len(rows)


def data_available(cfg, root):
    """该站的数据源在当前检出里是否齐全。

    prompts 站的 data/prompts_*.json 不入库（可由 import_youmind.py 重拉），
    干净检出上既不能同步也不能核对条目数——这类站跳过，不算失败。
    """
    if not os.path.exists(os.path.join(root, cfg["manifest"])):
        return False
    if cfg.get("meta_glob"):
        import glob
        if not glob.glob(os.path.join(root, cfg["meta_glob"])):
            return False
    return True


def check(root, db_path):
    problems = []
    skipped = []
    ids = site_ids(root)
    src = catalog.SOURCES
    db = sqlite3.connect(db_path)

    for sid in ids:
        cfg = src.get(sid)
        if not cfg:
            problems.append(f"{sid}: 没进 catalog.SOURCES，WebUI 里查不到这条素材")
            continue
        if not data_available(cfg, root):
            skipped.append(sid)
            continue
        n = db.execute("SELECT COUNT(*) FROM item WHERE collection=?", (sid,)).fetchone()[0]
        if n == 0:
            problems.append(f"{sid}: 同步后条目数为 0")
            continue
        want = expected_items(cfg, root)
        if n != want:
            problems.append(
                f"{sid}: 条目数 {n} ≠ 期望 {want}（聚合声明与索引实现不一致）"
            )

    # 反向：索引里不该有已从站点清单里删掉的站
    for (slug,) in db.execute("SELECT DISTINCT collection FROM item"):
        if slug not in ids and slug != "own":
            problems.append(f"{slug}: 索引里有这个集合，但 sites.json 里没有")

    db.close()
    return problems, skipped, len(ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--db", default=os.path.join(ROOT, "gallery.db"))
    args = ap.parse_args()

    problems, skipped, total = check(os.path.abspath(args.root), os.path.abspath(args.db))
    if problems:
        print("索引接线不一致：")
        for p in problems:
            print("  " + p)
        sys.exit(1)
    if skipped:
        print(f"（跳过：数据源不在仓库里，无法核对 —— {', '.join(skipped)}）")
    print(f"索引接线一致：{total - len(skipped)} 个站全部核对通过")


if __name__ == "__main__":
    main()
