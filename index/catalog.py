#!/usr/bin/env python3
"""把九份互不相同的 manifest 合并成一张统一清单。

只读现有文件，不修改任何东西。产出一份 CSV，顺带做三件事：
  1. 验证字段映射表是否覆盖所有字段（未映射字段必须报告，不能静默丢）
  2. 按「提示词」聚合 prompts 站的多图记录（否则 item 数会虚高到 22268）
  3. 输出各集合的条目数与缺口统计（缺宽高、缺字节、缺 prompt）

用法：
    python index/catalog.py                 # 产出 exports/catalog.csv
    python index/catalog.py --out x.csv     # 指定输出
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "shared"))

from image_policy import site_entry, tier_addr  # noqa: E402


def file_addr(sid, kind, rec, key):
    """该档位的展示地址：本地档用站内相对路径，直连上游的档用上游 URL。

    key 写成 "路径键" 或 "路径键|上游地址键"；只有后者才可能走直连。
    取图策略的唯一依据是 sites.json 的 imagePolicy（见 shared/image_policy.py），
    这里与站点构建（sites/*/scripts/build_gallery.py）用同一套判断，口径不能两样。
    """
    path_key, _, url_key = key.partition("|")
    path = rec.get(path_key) or ""
    if not url_key:
        return path
    url = rec.get(url_key) or ""
    display, _fallback, _keep = tier_addr(site_entry(sid), kind, path, url)
    return display


def file_specs(sid, cfg, rec):
    """该记录各档位的 (地址, 回落地址)。

    地址按 sites.json 的 imagePolicy 决定（与 file_addr 同一套判断）：
    本地档是站内相对路径，直连上游的档是上游 URL —— 外链由 sync 原样入库，
    不拼 sites/<集合>/ 前缀（拼了就是垃圾路径）。
    """
    site = site_entry(sid)
    out = {}
    for kind, key in cfg["files"]:
        path_key, _, url_key = key.partition("|")
        if not url_key:
            url_key = (path_key[:-len("_path")] + "_url") if path_key.endswith("_path") else ""
        path = rec.get(path_key) or ""
        url = (rec.get(url_key) or "") if url_key else ""
        display, fallback, _keep = tier_addr(site, kind, path, url)
        if not display:
            continue
        # 本地档也要保留上游地址作备用：本地文件缺失时媒体路由可 302 回落
        out[kind] = (display, fallback or url)
    return out


# 每个集合的字段映射。键是目标语义，值是 manifest 里的原始键。
# facets 是 OrderedDict 的语义：ns（分面名）→ manifest 键。
# derived_facets：manifest 里没有该字段，按判定键非空写固定值：ns → [(判定键, 显示值)]。
# ignored：索引明确不用的 manifest 字段（站点页面要用），声明了才不算「未映射」。
# files 里每一项 (kind, key)，kind 对应 derivative 表的 kind。
SOURCES = {
    "portrait": {
        "manifest": "sites/portrait/manifest.json",
        "title": "风格",
        "facets": {"分区": "分区", "发型": "发型", "风格": "风格"},
        "files": [("thumb", "thumb_path"), ("full", "full_path")],
        "size": ("宽", "高"),
        "bytes": "原图字节",
    },
    "costume": {
        "manifest": "sites/costume/manifest.json",
        "title": None,  # 无标题，退回 id
        "title_alt": "关键词",
        "facets": {"分类": "分类", "标签": "标签"},
        "files": [
            ("thumb", "thumb_path"),
            ("img", "img_path"),
            ("png", "png_path"),
        ],
        "size": None,
        "bytes": None,
        "keywords": "关键词",
        "tags_field": "标签",
    },
    "pose": {
        "manifest": "sites/pose/manifest.json",
        "title": "姿势名",
        "title_alt": None,
        "split_by_design": "同一姿势的 5 个视角在站内是独立条目（browse 按视角筛选），刻意不聚合",
        "facets": {"系列": "系列", "分類": "分類", "视角": "视角", "编号": "编号"},
        "files": [("thumb", "thumb_path"), ("full", "full_path")],
        "size": None,
        "bytes": None,
    },
    "pose-depth": {
        "manifest": "sites/pose-depth/manifest.json",
        "title": "姿势名",
        "split_by_design": "同一姿势的 5 个视角在站内是独立条目（browse 按视角筛选），刻意不聚合",
        "facets": {"系列": "系列", "分類": "分類", "视角": "视角", "编号": "编号"},
        "files": [("thumb", "thumb_path"), ("full", "full_path")],
        "size": None,
        "bytes": None,
    },
    "shisei": {
        "manifest": "sites/shisei/manifest.json",
        "title": "姿势名_zh",
        "title_alt": "姿势名",
        "facets": {
            "系列": "系列",
            "分類": "分類",
            "视角": "视角",
            "rating": "rating",
            "编号": "编号",
        },
        "files": [
            ("thumb", "thumb_path"),
            ("mid", "mid_path"),
            ("full", "full_path"),
        ],
        "size": None,
        "bytes": None,
    },
    "prompts": {
        "manifest": "sites/prompts/manifest.json",
        # 每个模型一份文本数据；提示词站是多来源集合，路径用通配
        "meta_glob": "sites/prompts/data/prompts_*.json",
        "title": "title",
        # 分类来自 tags（逗号串）；模型用导入器写好的展示名，便于直接当分面值
        "facets": {"分类": "tags", "模型": "modelLabel"},
        "files": [("thumb", "thumb_path"), ("full", "full_path")],
        "size": None,
        "bytes": None,
    },
    "midjourney-explore": {
        "manifest": "sites/midjourney-explore/manifest.json",
        # title 是提示词原文的前 80 字；title_alt 用完整提示词
        "title": "title",
        "title_alt": "prompt",
        # 分面只留能真正分组的两维：宽高比 29 种（长尾每个只有 4 张）、风格参考
        # 是「一码一条」的标识而不是分类，两者做左栏分面噪声大于信息，已撤掉
        # （宽高比/风格参考仍留在 manifest 里：站点页面的徽标与灯箱复制要用）。
        # 版本目前只有 8.2 一种值、批次按采集日，留着有信息量。
        "facets": {"版本": "version", "批次": "batch"},
        # 派生分面：manifest 里没有对应字段，按「判定键非空」写一条固定值。
        # 用 sref 而不是 hasStyleRef —— 后者 108 条里有 74 条是图片型风格参考，
        # 没有码；「有 sref 码」= 真的能复制出一串 --sref 参数的作业（34 条）。
        "derived_facets": {"类别": [("sref", "有 sref 码")]},
        # 宽高比不进索引（站点页面要用，索引里宽高已有 width/height 列）。
        # 不声明这一条，unmapped_report 会把 aspect 一直报成「未映射字段」。
        "ignored": ["aspect"],
        # 「视图」= 集合内的顶层分层。facet 只给命名空间 = 存在性过滤
        # （该命名空间下有任意标签即命中）。本集合只有两个视图：
        #   图像 → 不加过滤，本集合的全部条目
        #   视频 → 命名空间「类型」；上游 explore 的 video feed 尚未采集，
        #          采集入库后给视频条目打「类型/视频」标签，这里自动生效
        #
        # 原站 Explore 的三个 tab 里还有一个 Styles，但**本站不镜像它**：
        # 原站「风格」（2026-11-03 实测）是独立内容类型——一个 sref 码 + 三张
        # 语义图（portrait / landscape / still_life），没有 prompt、没有作者，
        # 与本集合「一条作业四格成图」的素材结构不同源。此前用
        # facet="风格参考" 近似出来的「风格」视图，实际筛的是「挂了 sref 的
        # 作业」，与原站那个 tab 同名不同义，已删除。
        # 2026-11-04：Styles 曾经拆成兄弟站 mj-styles，因价值不足已整站删除
        # （见 docs/adr/0005-remove-mj-styles-site.md）。原站那个 tab 至今未镜像。
        "views": [
            {"k": "images", "name": "图像", "facet": None},
            {"k": "videos", "name": "视频", "facet": "类型"},
        ],
        # full 档直连上游（imagePolicy.full=online）：原图 2.3 GB/天，
        # 本地不留；thumb + mid 仍在本地。
        "files": [("thumb", "thumb_path"), ("mid", "mid_path"), ("full", "full_path|full_url")],
        "size": ("width", "height"),
        "bytes": None,
        "keywords": "prompt",
        "prompt": "prompt",
        # 同一次作业出 4 格、共用一段提示词：按 jobId 聚合成一条素材，
        # 4 张图作为它的 4 个 asset（ordinal = index，灯箱里的翻页顺序）。
        # 不声明 group_by 的话，4 格会散成 4 条独立素材，灯箱里翻不到一起。
        "group_by": "jobId",
        "group_order": "index",
        "extra": {
            "source_url": "sourceUrl",
            "published_at": "enqueueTime",
            "model": "version",
            "author": "username",
            "author_display": "displayName",
            "style_ref": "sref",
            "grid_index": "index",
            "job_id": "jobId",
        },
    },
"prompthero-midjourney": {
        "manifest": "sites/prompthero-midjourney/manifest.json",
        # title 是提示词原文的前 80 字；title_alt 用上游的描述（含浏览/收藏数）
        "title": "title",
        "title_alt": "description",
        # 上游分类是英文原文；版本是 Midjourney 的版本号
        "facets": {"分类": "category", "版本": "modelVersion"},
        # full 档直连上游（imagePolicy.full=online）：原图 36.3 GB，本地不留。
        # 双键写法「full_path|full_url」：manifest 里**没有** full_path
        # （online 档不写本地路径，写了就是谎报），path 取空、地址取 full_url。
        # 双键是必需的 —— file_specs 靠它区分「站内路径键」与「上游地址键」。
        "files": [("thumb", "thumb_path"), ("mid", "mid_path"), ("full", "full_path|full_url")],
        "size": ("width", "height"),
        "bytes": None,
        "keywords": "prompt",
        "prompt": "prompt",
        # NSFW 条目在 manifest 里 isNsfw=1
        "nsfw_field": "isNsfw",
        "extra": {
            "source_url": "sourceUrl",
            "published_at": "createdAt",
            "model": "modelVersion",
            "fav_count": "favCount",
            "view_count": "viewCount",
        },
    },
}

CSV_COLS = [
    "collection",
    "item_id",
    "ext_id",
    "title",
    "title_alt",
    "prompt",
    "prompt_raw",
    "author",
    "source_url",
    "published_at",
    "model",
    "facets",
    "thumb",
    "mid",
    "full",
    "img",
    "png",
    "bytes",
    "width",
    "height",
    "fav_count",
    "view_count",
    "author_display",
    "style_ref",
    "grid_index",
    "job_id",
]

# 预留命名空间：视图可以用它做「还没有数据」的视图。
# 目前只有「类型」——上游 explore 的 video feed 尚未采集，
# 采集入库后给视频条目打「类型/视频」标签，「视频」视图自动生效。
RESERVED_NS = {"类型"}

# 每个 manifest 里允许出现但不需要入库的键（纯 URL，本地已有副本）
IGNORABLE = {"thumb_url", "full_url", "mid_url", "img_url", "png_url", "id", "原图字节",
             # 派生档位的回落标记：只用于下载时选档，不是素材属性
             "thumbFallback", "midFallback",
             # 与 id 重复的完整 slug（id 已是它）
             "slug",
             # 0/1 标记：这条作业挂了风格参考（可能是图片型，没有码）。
             # 真实信息在 sref 列里，标记位本身不入库
             "hasStyleRef"}

# CSV 里 prompt 的截断长度。完整内容走 SQLite（Step 1），不进 CSV。
# 22k 条 prompt 平均上千字符，不截断会让 CSV 涨到 57 MB，Excel 打不开。
TRUNC = 200
FULL = False


def cut(s: str) -> str:
    s = (s or "").replace("\n", " ").replace("\r", " ")
    if FULL or len(s) <= TRUNC:
        return s
    return s[:TRUNC] + "…"


def load(rel: str):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def fmt_facets(pairs):
    return "|".join(f"{ns}:{v}" for ns, v in pairs if v not in (None, "", []))


def fmt_tags(vals):
    return "|".join(vals) if isinstance(vals, list) else ""


def build_portrait_like(sid, cfg):
    """通用处理：一行一条；或按 cfg["group_by"] 声明的键聚合成一条。"""
    manifest = load(cfg["manifest"])
    seen_keys = set()
    for rec in manifest:
        seen_keys.update(rec.keys())

    rows = []
    if cfg.get("group_by"):
        order_key = cfg.get("group_order") or "index"
        groups = {}
        for rec in manifest:
            gid = rec.get(cfg["group_by"]) or rec.get("id", "")
            groups.setdefault(gid, []).append(rec)
        for gid, grp in groups.items():
            rows.append(_row_for(sid, cfg, gid, sorted(grp, key=lambda r: r.get(order_key) or 0)))
    else:
        for rec in manifest:
            rows.append(_row_for(sid, cfg, rec.get("id", ""), [rec]))
    return rows, seen_keys


def derived_facet_pairs(cfg, rec):
    """派生分面 → [(命名空间, 值)]：manifest 里没有这个字段，按「判定键非空」写固定值。

    声明在 SOURCES 的 derived_facets 里：{命名空间: [(manifest 键, 显示值), ...]}。
    典型用途是「存在性」类别（如本站的「有 sref 码」）。CSV 导出与数据库同步
    都调这一份，两边的分面口径不会有第二份实现。
    """
    out = []
    for ns, rules in (cfg.get("derived_facets") or {}).items():
        for key, value in rules:
            if rec.get(key):
                out.append((ns, value))
    return out


def _row_for(sid, cfg, gid, grp):
    """把一组记录（组内第一条即 head）写成一行 CSV。"""
    head = grp[0]
    title_key = cfg.get("title")
    title = head.get(title_key) if title_key else None
    title_alt = None
    if cfg.get("title_alt"):
        title_alt = cut(head.get(cfg["title_alt"]) or "")

    facets = []
    for ns, key in cfg["facets"].items():
        val = head.get(key)
        if isinstance(val, list):
            facets.extend((ns, v) for v in val)
        elif val:
            facets.append((ns, val))
    facets.extend(derived_facet_pairs(cfg, head))

    row = {c: "" for c in CSV_COLS}
    row["collection"] = sid
    row["ext_id"] = gid
    row["item_id"] = gid
    row["title"] = title or gid
    row["title_alt"] = title_alt or ""
    row["facets"] = fmt_facets(facets)

    # costume 没有 prompt，但有关键词，作为 prompt 的弱替代（便于英文检索）
    if cfg.get("keywords"):
        row["prompt_raw"] = head.get(cfg["keywords"]) or ""
    # prompt 列：展示用正文。配置了就填，没配就留空
    if cfg.get("prompt"):
        row["prompt"] = cut(head.get(cfg["prompt"]) or "")

    for kind, key in cfg["files"]:
        row[kind] = file_addr(sid, kind, head, key)

    if cfg.get("size"):
        w, h = cfg["size"]
        row["width"] = head.get(w) or ""
        row["height"] = head.get(h) or ""
    if cfg.get("bytes"):
        row["bytes"] = head.get(cfg["bytes"]) or ""

    # extra：把 manifest 的额外字段接到 CSV 的固定列上。
    # {"source_url": "sourceUrl", "published_at": "createdAt", ...}
    for col, key in (cfg.get("extra") or {}).items():
        row[col] = head.get(key, "")
    return row


def build_prompts(cfg):
    """prompts 站：manifest 一行一张图，meta 一行一条提示词，按图片路径关联并聚合。"""
    manifest = load(cfg["manifest"])
    meta = []
    for path in sorted(glob.glob(os.path.join(ROOT, cfg["meta_glob"]))):
        with open(path, encoding="utf-8") as f:
            meta.extend(json.load(f))

    # dims.json 有 22268 条宽高，manifest 里没有，白捡的
    dims = {}
    dims_rel = "sites/prompts/data/dims.json"
    if os.path.exists(os.path.join(ROOT, dims_rel)):
        dims = load(dims_rel)

    by_file = {}
    for m in meta:
        by_file[m.get("file", "")] = m

    groups = {}
    unmatched = 0
    for rec in manifest:
        path = rec.get("full_path", "")
        m = by_file.get(path)
        if not m:
            unmatched += 1
            m = {}

        # 同一提示词的多张图聚成一个 item。originId 已带模型前缀（gpt2- / nbpro-），
        # 跨模型的 id 空间天然隔离，不要再补前缀（补了会把 nbpro 挤进 gpt2 命名空间）。
        gid = m.get("originId") or rec.get("id", "")
        g = groups.setdefault(gid, {"meta": m, "files": []})
        g["files"].append(rec)

    # 这两个是导入器打的标记，不是内容分类
    FLAGS = {"精选", "需参考图"}

    rows = []
    for gid, g in groups.items():
        m = g["meta"]
        row = {c: "" for c in CSV_COLS}
        row["collection"] = "prompts"
        row["ext_id"] = gid
        row["item_id"] = gid
        row["title"] = m.get("title") or gid
        # prompt 是中文/展示版，prompt_raw 是英文原文（创作时复制的就是它）
        row["prompt"] = cut(m.get("prompt"))
        row["prompt_raw"] = cut(m.get("promptRaw"))
        row["author"] = m.get("author") or ""
        row["source_url"] = m.get("sourceUrl") or m.get("url") or ""
        row["published_at"] = m.get("published") or ""
        row["model"] = m.get("model") or ""

        # tags 是逗号分隔的字符串，不是 list（踩过：逐字符展开过一次）
        raw_tags = m.get("tags") or ""
        if isinstance(raw_tags, str):
            tag_list = [t.strip() for t in raw_tags.split(",") if t.strip()]
        else:
            tag_list = list(raw_tags)
        facets = []
        for t in tag_list:
            facets.append(("标记" if t in FLAGS else "分类", t))
        if m.get("modelLabel"):
            facets.append(("模型", m["modelLabel"]))
        row["facets"] = fmt_facets(facets)

        # 第一张图填 thumb/full，宽高取第一张
        first = g["files"][0] if g["files"] else {}
        row["thumb"] = first.get("thumb_path", "")
        row["full"] = first.get("full_path", "")
        wh = dims.get(first.get("full_path", ""))
        if wh:
            row["width"], row["height"] = wh[0], wh[1]

        rows.append(row)

    seen_keys = set()
    for rec in manifest[:2000]:
        seen_keys.update(rec.keys())
    return rows, seen_keys, unmatched, sum(len(g["files"]) for g in groups.values())


def unmapped_report(sid, seen, cfg):
    """报告 manifest 里出现、但映射表没消费的字段。"""
    consumed = set(IGNORABLE)
    for k in ("title", "title_alt", "bytes", "keywords", "prompt", "tags_field", "nsfw_field"):
        if cfg.get(k):
            consumed.add(cfg[k])
    if cfg.get("size"):
        consumed.update(cfg["size"])
    consumed.update(k for _, key in cfg["files"] for k in key.split("|"))
    consumed.update((cfg.get("extra") or {}).values())
    consumed.update(cfg["facets"].values())
    consumed.update(cfg.get("facets", {}).keys())
    # 派生分面的判定键也是「已消费」：它被拿去算标签了，不是漏映射
    for rules in (cfg.get("derived_facets") or {}).values():
        consumed.update(key for key, _value in rules)
    # 显式声明「这个字段索引不用」：站内页面用、索引不用（如宽高比）
    consumed.update(cfg.get("ignored") or [])
    missing = sorted(k for k in seen if k not in consumed and not k.endswith("_url"))
    return missing


def main():
    global FULL
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="exports/catalog.csv")
    ap.add_argument("--full", action="store_true", help="prompt 不截断（CSV 会涨到 50 MB+）")
    args = ap.parse_args()
    FULL = args.full

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    all_rows = []
    report = []
    for sid, cfg in SOURCES.items():
        if sid == "prompts":
            rows, seen, unmatched, file_count = build_prompts(cfg)
            report.append((sid, len(rows), file_count, unmatched, unmapped_report(sid, seen, cfg)))
        else:
            rows, seen = build_portrait_like(sid, cfg)
            # 分组站（group_by）一行素材对应多张图，文件数按图算，不是按行算
            file_count = len(load(cfg["manifest"])) if cfg.get("group_by") else len(rows)
            report.append((sid, len(rows), file_count, 0, unmapped_report(sid, seen, cfg)))
        all_rows.extend(rows)

    out = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        w.writerows(all_rows)

    print(f"=== 写入 {args.out} ===")
    print(f"{'集合':<12}{'item':>8}{'asset':>8}{'未匹配':>8}  未映射字段")
    print("-" * 72)
    ti = ta = 0
    for sid, items, assets, unmatched, missing in report:
        ti += items
        ta += assets
        flag = ",".join(missing) if missing else "—"
        print(f"{sid:<12}{items:>8}{assets:>8}{unmatched:>8}  {flag}")
    print("-" * 72)
    print(f"{'合计':<12}{ti:>8}{ta:>8}")

    # 缺口统计：按集合列出，便于区分「该有却没有」和「设计上就没有」
    print("\n=== 缺口（按集合）===")
    for col, name in (
        ("thumb", "缩略图"),
        ("full", "原图"),
        ("width", "宽高"),
        ("prompt_raw", "原文 prompt"),
        ("facets", "分面"),
    ):
        parts = []
        for sid in SOURCES:
            n = sum(
                1
                for r in all_rows
                if r["collection"] == sid and not str(r.get(col, "")).strip()
            )
            if n:
                parts.append(f"{sid} {n}")
        if parts:
            print(f"  缺 {name:<12}{'  '.join(parts)}")

    size = os.path.getsize(out)
    print(f"\n文件 {size / 1024:.0f} KB，{len(all_rows)} 行，{len(CSV_COLS)} 列")
    if not FULL:
        print(f"（prompt 已截断到 {TRUNC} 字符；需要全量加 --full）")


if __name__ == "__main__":
    main()
