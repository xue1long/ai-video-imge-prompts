# -*- coding: utf-8 -*-
"""同步：把各集合的 manifest 变成 gallery.db 里的一份统一索引。

字段映射表**不在这里**——它只有一份，在 catalog.py 的 SOURCES 里。
本模块只负责「按那张表把记录写进库」，这样 CSV 导出和数据库永远不会映射不一致。

用法:
  python index/sync.py                # 同步仓库根
  python index/sync.py --root <dir>   # 同步指定数据根（测试用）
  python index/sync.py --force        # 忽略签名，强制重建
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import catalog
import store

SHARED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared")
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

try:  # 中文名表：姿势名 / 分类 / 系列 / 视角
    import pose_i18n
except ImportError:  # 单独拷走 index/ 时仍然能跑，只是没有中文别名
    pose_i18n = None

# 兜底用的集合展示名与顺序（数据根缺 sites.json 时，例如测试夹具才用到）。
# 正常情况下顺序与中文名来自 sites.json —— 仓库的规则是「sites.json 是唯一清单」。
COLLECTION_NAMES = [
    ("portrait", "人像"),
    ("pose", "姿势"),
    ("pose-depth", "深度姿势"),
    ("costume", "服装"),
    ("shisei", "Shisei 姿势"),
    ("prompts", "提示词生图"),
    ("own", "我的素材"),
]


def collection_names(root):
    """从 sites.json 取集合顺序与中文展示名，导入素材永远排最后。"""
    names = []
    path = os.path.join(root, "sites.json")
    if os.path.exists(path):
        try:
            data = load(root, "sites.json")
            for site in data.get("sites", []):
                sid = site.get("id")
                if not sid:
                    continue
                label = ((site.get("name") or {}).get("zh")) or sid
                names.append((sid, label))
        except (ValueError, OSError):
            names = []
    if not names:
        names = list(COLLECTION_NAMES)
    if not any(slug == "own" for slug, _ in names):
        names.append(("own", "我的素材"))
    return names

# 每个集合里「哪一档是原始文件」。其余档位都是它的派生图。
ORIGINAL_TIER = {
    "portrait": "full",
    "costume": "img",
    "pose": "full",
    "pose-depth": "full",
    "shisei": "full",
    "prompts": "full",
    "prompthero-midjourney": "full",
}

# 分面命名空间 → 中文名表。没列出的命名空间 name_zh 与 name 相同。
NS_ZH = {
    "分類": "CAT_ZH",
    "系列": "SERIES_ZH",
    "视角": "ANG_ZH",
}

# 提示词站的这两个标签是导入器的标记，不是内容分类
FLAGS = {"精选", "需参考图"}


def load(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        return json.load(f)


def norm(text):
    """把标题里的换行压成空格：上游有 50 条标题自带换行，不清会撑破网格。"""
    return " ".join((text or "").split())


def zh_for(ns, name):
    table = NS_ZH.get(ns)
    if table and pose_i18n is not None:
        return getattr(pose_i18n, table, {}).get(name, "") or name
    return name


def signature(root):
    """各集合 manifest（+ 提示词站的多份文本数据）的 mtime+size 签名，用来判断要不要重建。"""
    parts = []
    for sid, cfg in catalog.SOURCES.items():
        rels = [cfg.get(key) for key in ("manifest", "meta")]
        if cfg.get("meta_glob"):
            rels += [os.path.relpath(p, root)
                     for p in sorted(glob.glob(os.path.join(root, cfg["meta_glob"])))]
        for rel in filter(None, rels):
            p = os.path.join(root, rel)
            if os.path.exists(p):
                st = os.stat(p)
                parts.append(f"{sid}:{rel}:{int(st.st_mtime)}:{st.st_size}")
    return "|".join(parts)


# ── 写入 ────────────────────────────────────────────────────────


def write_files(conn, item_id, present, original_kind, original_path, size, w, h, prefix="", urls=None):
    """一个原始资产 + 它的派生图，再挂到作品上。

    manifest 里的路径是**站点相对**的（pose 与 pose-depth 的字段一字不差），
    必须以 sites/<集合>/ 为前缀，否则两站会被当成同一批文件去重掉。

    urls 是 {档位: 上游地址}：本地文件不在时，媒体路由据此重定向到上游。
    """
    urls = urls or {}
    asset_id, _ = store.add_asset(conn, prefix + original_path, "sites", size, w, h)
    for kind, path in sorted(present.items()):
        store.add_derivative(conn, asset_id, kind, prefix + path,
                             size if kind == original_kind else 0,
                             url=urls.get(kind, ""))
    store.link_asset(conn, item_id, asset_id, role=original_kind, ordinal=0)


def write_tags(conn, item_id, pairs):
    for ns, name in pairs:
        if not name:
            continue
        tag_id = store.upsert_tag(conn, ns, name, zh_for(ns, name))
        store.tag_item(conn, item_id, tag_id, "builtin")


def facet_pairs(facets_cfg, rec, flags=None):
    """把映射表里配置的分面键展开成 (ns, 值) 列表。"""
    out = []
    for ns, key in facets_cfg.items():
        val = rec.get(key)
        if isinstance(val, str) and key == "tags":  # 提示词站的 tags 是逗号串
            for t in (x.strip() for x in val.split(",")):
                if t:
                    out.append(("标记" if flags and t in flags else ns, t))
        elif isinstance(val, list):
            out.extend((ns, v) for v in val if v)
        elif val:
            out.append((ns, val))
    return out


def sync_rows(conn, sid, cfg, recs):
    """通用处理：一行一条；或按 cfg["group_by"] 声明的键聚合成一条。

    多图站（如 midjourney-explore：一次作业出 4 格、共用一段提示词）
    必须在 SOURCES 里声明 group_by，否则这 4 格会散成 4 条独立素材，
    WebUI 灯箱里就翻不到一起。声明后：1 个分组 = 1 个 item，
    分组内的多张图作为它的多个 asset，ordinal = 组内序号（灯箱翻页顺序）。
    """
    if cfg.get("group_by"):
        return sync_grouped(conn, sid, cfg, recs, cfg["group_by"])
    original_kind = ORIGINAL_TIER.get(sid, "full")
    count = 0
    for rec in recs:
        ext_id = rec.get("id", "")
        item_id = f"{sid}:{ext_id}"
        title_key = cfg.get("title")
        title = norm(rec.get(title_key)) if title_key else ""
        title_alt = norm(rec.get(cfg["title_alt"])) if cfg.get("title_alt") else ""
        # 统一口径：title 是展示名（尽量中文），title_alt 是原文。
        # shisei 的 manifest 本来就是「姿势名_zh / 姿势名」这样排的，姿势两站靠翻译表对齐。
        if sid.startswith("pose") and title and pose_i18n is not None:
            zh = pose_i18n.NAME_ZH.get(title)
            if zh:
                title, title_alt = zh, title
        prompt_raw = norm(rec.get(cfg["keywords"])) if cfg.get("keywords") else ""

        store.add_item(
            conn,
            id=item_id,
            collection=sid,
            ext_id=ext_id,
            title=title or ext_id,
            title_alt=title_alt,
            prompt=norm(rec.get("prompt")) if rec.get("prompt") else "",
            prompt_raw=prompt_raw,
            generator_meta="",
        )
        write_tags(conn, item_id, facet_pairs(cfg["facets"], rec))

        present = {kind: rec.get(key) for kind, key in cfg["files"] if rec.get(key)}
        if not present:
            continue
        # 档位 → 上游地址（manifest 里是 <档位>_url）；本地文件不在时媒体路由靠它重定向
        urls = {kind: rec.get(key[:-len("_path")] + "_url") or ""
                for kind, key in cfg["files"] if rec.get(key)}
        original_path = present.get(original_kind) or next(iter(present.values()))
        # 宽高：cfg["size"] 是 (宽键, 高键)；没配就退回旧的中文键
        if cfg.get("size"):
            w_key, h_key = cfg["size"]
            width, height = rec.get(w_key) or None, rec.get(h_key) or None
        else:
            width, height = rec.get("宽") or None, rec.get("高") or None
        write_files(
            conn,
            item_id,
            present,
            original_kind,
            original_path,
            rec.get("原图字节") or 0,
            width,
            height,
            prefix=f"sites/{sid}/",
            urls=urls,
        )
        count += 1
    return count


def sync_grouped(conn, sid, cfg, recs, group_key):
    """按 cfg["group_by"] 指定的字段聚合：1 个分组 = 1 条素材（item），组内多图挂成多个 asset。

    组内排序用 cfg["group_order"]（默认 "index"），它决定 asset 的 ordinal，
    也就是 WebUI 灯箱里的翻页顺序。组级字段（标题 / 提示词 / 作者等）取组内第一条。
    """
    order_key = cfg.get("group_order") or "index"
    groups = {}
    for rec in recs:
        gid = rec.get(group_key) or rec.get("id", "")
        groups.setdefault(gid, []).append(rec)

    prefix = f"sites/{sid}/"
    original_kind = ORIGINAL_TIER.get(sid, "full")
    # 组级字段（作者 / 模型 / 来源 / 时间）在各站叫法不同，统一走 SOURCES 的 extra 映射。
    extra = cfg.get("extra") or {}

    def group_field(rec, col, fallback=""):
        key = extra.get(col)
        if key and rec.get(key) not in (None, ""):
            return rec.get(key)
        return rec.get(fallback) or ""

    for gid, grp in groups.items():
        grp = sorted(grp, key=lambda r: r.get(order_key) or 0)
        head = grp[0]
        item_id = f"{sid}:{gid}"
        title_key = cfg.get("title")
        title = norm(head.get(title_key)) if title_key else ""
        title_alt = norm(head.get(cfg["title_alt"])) if cfg.get("title_alt") else ""
        prompt = norm(head.get("prompt")) if head.get("prompt") else ""
        prompt_raw = norm(head.get(cfg["keywords"])) if cfg.get("keywords") else ""

        store.add_item(
            conn,
            id=item_id,
            collection=sid,
            ext_id=gid,
            title=title or gid,
            title_alt=title_alt,
            prompt=prompt,
            prompt_raw=prompt_raw,
            author=str(group_field(head, "author")),
            source_url=str(group_field(head, "source_url")),
            published_at=str(group_field(head, "published_at")),
            model=str(group_field(head, "model")),
        )
        write_tags(conn, item_id, facet_pairs(cfg["facets"], head))

        for ordinal, rec in enumerate(grp):
            present = {kind: rec.get(key) for kind, key in cfg["files"] if rec.get(key)}
            if not present:
                continue
            urls = {kind: rec.get(key[:-len("_path")] + "_url") or ""
                    for kind, key in cfg["files"] if rec.get(key)}
            original_path = present.get(original_kind) or next(iter(present.values()))
            if cfg.get("size"):
                w_key, h_key = cfg["size"]
                width, height = rec.get(w_key) or None, rec.get(h_key) or None
            else:
                width, height = rec.get("宽") or None, rec.get("高") or None
            asset_id, _ = store.add_asset(
                conn, prefix + original_path, "sites", rec.get("原图字节") or 0, width, height
            )
            for kind, path in sorted(present.items()):
                if kind == original_kind:
                    continue
                store.add_derivative(conn, asset_id, kind, prefix + path,
                                     url=urls.get(kind, ""))
            store.add_derivative(conn, asset_id, original_kind, prefix + original_path,
                                 url=urls.get(original_kind, ""))
            store.link_asset(conn, item_id, asset_id, role=original_kind, ordinal=ordinal)
    return len(groups)


def sync_prompts(conn, cfg, root):
    """prompts 站：manifest 一行一张图，meta 一行一条提示词，按图片路径关联并聚合。"""
    manifest = load(root, cfg["manifest"])
    meta = []
    for path in sorted(glob.glob(os.path.join(root, cfg["meta_glob"]))):
        with open(path, encoding="utf-8") as f:
            meta.extend(json.load(f))
    dims = {}
    dims_rel = "sites/prompts/data/dims.json"
    if os.path.exists(os.path.join(root, dims_rel)):
        dims = load(root, dims_rel)

    by_file = {m.get("file", ""): m for m in meta}
    groups = {}
    for rec in manifest:
        m = by_file.get(rec.get("full_path", "")) or {}
        # originId 已带模型前缀（gpt2- / nbpro-），直接当作品 id，不要再补前缀
        gid = m.get("originId") or rec.get("id", "")
        groups.setdefault(gid, {"meta": m, "files": []})["files"].append(rec)

    for gid, g in groups.items():
        item_id = f"prompts:{gid}"
        m = g["meta"]
        store.add_item(
            conn,
            id=item_id,
            collection="prompts",
            ext_id=gid,
            title=norm(m.get("title")) or gid,
            title_alt="",
            prompt=norm(m.get("prompt")),
            prompt_raw=norm(m.get("promptRaw")),
            author=m.get("author") or "",
            source_url=m.get("sourceUrl") or m.get("url") or "",
            published_at=m.get("published") or "",
            model=m.get("model") or "",
        )
        write_tags(conn, item_id, facet_pairs(cfg["facets"], m, flags=FLAGS))

        for ordinal, rec in enumerate(g["files"]):
            original = rec.get("full_path")
            if not original:
                continue
            wh = dims.get(original) or [None, None]
            asset_id, _ = store.add_asset(conn, "sites/prompts/" + original, "sites", 0, wh[0], wh[1])
            if rec.get("thumb_path"):
                store.add_derivative(conn, asset_id, "thumb", "sites/prompts/" + rec["thumb_path"])
            store.add_derivative(conn, asset_id, "full", "sites/prompts/" + original)
            store.link_asset(conn, item_id, asset_id, role="full", ordinal=ordinal)
    return len(groups)


# ── 主流程 ──────────────────────────────────────────────────────


def sync(root, db_path, force=False, verbose=True):
    """全量重建索引。返回统计字典。"""
    root = os.path.abspath(root)
    conn = store.connect(db_path)
    signature_now = signature(root)
    if not force and store.kv_get(conn, "manifest_signature") == signature_now:
        stats = _stats(conn)
        stats["skipped"] = True
        stats["unmapped"] = {}
        conn.close()
        return stats

    store.reset(conn)
    for sort, (slug, name) in enumerate(collection_names(root)):
        store.upsert_collection(conn, slug, name, sort)

    report = []
    unmapped = {}
    for sid, cfg in catalog.SOURCES.items():
        if not os.path.exists(os.path.join(root, cfg["manifest"])):
            continue
        if sid == "prompts":
            n = sync_prompts(conn, cfg, root)
            seen = set()
            for rec in load(root, cfg["manifest"]):
                seen.update(rec.keys())
        else:
            recs = load(root, cfg["manifest"])
            n = sync_rows(conn, sid, cfg, recs)
            seen = set()
            for rec in recs:
                seen.update(rec.keys())
        matched = catalog.unmapped_report(sid, seen, cfg)
        if matched:
            unmapped[sid] = matched
        report.append((sid, n))

    store.restore_user_data(conn)
    store.refresh_blob(conn)

    store.kv_set(conn, "manifest_signature", signature_now)
    conn.commit()
    stats = _stats(conn)
    stats.update({"skipped": False, "collections": report, "unmapped": unmapped})
    conn.close()
    if verbose:
        print(f"同步完成：{stats['items']} 作品 / {stats['assets']} 资产 / {stats['derivatives']} 派生图")
        for sid, n in report:
            print(f"  {sid:<12}{n:>7}")
        if unmapped:
            print(f"  ⚠ 未映射字段：{unmapped}")
    return stats


def _stats(conn):
    def count(table):
        return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]

    return {"items": count("item"), "assets": count("asset"), "derivatives": count("derivative")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--db", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db = args.db or os.path.join(args.root, "gallery.db")
    sync(args.root, db, force=args.force)


if __name__ == "__main__":
    main()
