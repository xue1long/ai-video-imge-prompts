# -*- coding: utf-8 -*-
"""data/items.json（采集段产物）→ manifest.json + manifest.csv。

清单契约（见 config.MANIFEST_FIELDS 与 docs/ADDING_A_SITE.md）：
每条记录对每个档位都要有 <tier>_url 与 <tier>_path —— tools/fetch.py 与
tools/verify.py 只靠这一条规则工作。本站两档：

    thumb  样例表的一角（裁剪交给上游做）   约 28 KB
    mid    整张样例表（灯箱一次看全 4 张）   约 200 KB

字段口径：
    id        = slug（本站用 slug 当主键，不用上游的 ULID）
    category  = 上游的 categorySlug（分类 slug，如 titles / sref-styles），
                **不是**英文标签（"Titles"）；页面按 slug 查中文名表
    sref      = 从 prompt 里正则抽出的纯码（--sref 3383230063 → "3383230063"），
                非 SREF 条目为空串
    sourceUrl = 原站条目页
    thumb_url = img_url(样例表路径) + "?crop=1024,1024&crop_gravity=<方位>&width=320"
    mid_url   = img_url(样例表路径) + "?width=960"

    注意：上游的 sheetUrl 本身就带 img/ 这一层（/img/midjourney-styles/v82/xxx.jpg），
    所以拼地址的基准是站点根（config.img_url），不是 IMG_BASE —— 直接相加会得到
    …/img/img/…，实测 404。

象限映射（config.QUAD_GRAVITY）：上游给的是 1..4 的序号，Cloudflare 裁剪要的是
方位名（northwest / northeast / southwest / southeast）。上游一张 2048×2048 的
样例表里摆了 4 张图，卡片取哪一角由这个字段决定 —— 映射错了不会报错，
只会让缩略图显示成相邻的那张图，所以这里显式查表，查不到就报错而不是猜。

裁剪尺寸（config.CROP_SIZE）：上游自己也是先裁 1024×1024 再缩到 320 发卡片，
这里跟上游同口径。

输出：
    manifest.json   ensure_ascii=False、indent=1、换行 \n
                    （入库文件：CI 在 Linux 上比对构建产物，必须逐字节一致，
                     Windows 上默认换行是 CRLF，所以显式指定 newline="\n"）
    manifest.csv    utf-8-sig + newline=""（CSV 写出 CRLF）
                    三个徽章列写成 1/0（与本仓其它站的标记字段一致，方便表格筛选）；
                    manifest.json 里保持布尔值
"""
import collections
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)                      # sites/midlibrary
sys.path.insert(0, HERE)

from config import (CROP_SIZE, IMAGE_EXT, IMG_BASE, LIST_PATH,  # noqa: E402
                    MANIFEST_FIELDS, MID_WIDTH, ORIGIN, QUAD_GRAVITY,
                    THUMB_WIDTH, img_url)

# 两档（与 config.IMAGE_BASES / sites.json 的 tiers 声明对应）
TIERS = ["thumb", "mid"]

# CSV 的列：清单字段的一个子集（不写 url 列 —— 那是给下载器用的，表格里没意义）
CSV_COLS = ["id", "slug", "name", "kind", "category", "prompt", "sref",
            "isPick", "isPublicDomain", "testedMark", "sourceUrl",
            "thumb_path", "mid_path"]

# 徽章列（CSV 里写成 1/0）
FLAG_COLS = ["isPick", "isPublicDomain", "testedMark"]

# 风格参考码：prompt 形如 "--sref 3383230063 --v 8.2"，只取纯码
SREF_RE = re.compile(r"--sref\s+(\d+)")

# 裁剪参数：上游按 crop + crop_gravity 从整张样例表里切一角，
# 切多大在 config.CROP_SIZE（与上游卡片同口径：先裁 1024 再缩到 320）
CROP = "%d,%d" % (CROP_SIZE, CROP_SIZE)


def load_items():
    """读采集段的产物 data/items.json。"""
    path = os.path.join(SITE, "data", "items.json")
    if not os.path.exists(path):
        sys.exit("找不到 data/items.json，先运行 python scripts/extract.py")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items") or []
    if not items:
        sys.exit("data/items.json 里没有条目，先运行 python scripts/extract.py")
    return data, items


def image_url(sheet_path, query=""):
    """样例表的图源地址。

    口径全在 config.img_url（契约，2026-11-05 由站方契约维护者统一加的）：
    sheet_path 是站内路径（"img/midjourney-styles/v82/xxx.jpg"），基准是站点根，
    不是 IMG_BASE —— 用 IMG_BASE 拼会得到 …/img/img/… 的废地址（上游 404）。
    这里只做一次转调，不另写一份拼 URL 的规则。
    """
    return img_url(sheet_path, query)


def gravity_of(item):
    """象限序号 → 裁剪方位名；查不到就报错（不猜：猜错只是缩略图显示成邻图）。"""
    q = item.get("sheetQuadrant")
    g = QUAD_GRAVITY.get(q)
    if not g:
        raise ValueError("未知的 sheetQuadrant：%r（条目 %s）" % (q, item.get("slug")))
    return g


def sref_of(prompt):
    """从可复制的那行提示词里抽纯码；没有 --sref 就空串。"""
    m = SREF_RE.search(prompt or "")
    return m.group(1) if m else ""


def build_row(item):
    """一条上游记录 → 一条清单记录（字段顺序 = config.MANIFEST_FIELDS）。"""
    slug = item.get("slug") or ""
    if not slug:
        return None
    sheet_path = item.get("sheetPath") or ""
    if not sheet_path:
        # 没有样例表就没有缩略图 —— 这种条目没法做卡片，只能不收
        return None
    prompt = item.get("prompt") or ""
    row = {
        "id": slug,
        "slug": slug,
        "name": item.get("name") or "",
        "kind": item.get("kind") or "",
        "category": item.get("categorySlug") or "",
        "prompt": prompt,
        "sref": sref_of(prompt),
        "isPick": bool(item.get("isPick")),
        "isPublicDomain": bool(item.get("isPublicDomain")),
        "testedMark": bool(item.get("testedMark")),
        "sourceUrl": "%s%s/%s" % (ORIGIN, LIST_PATH, slug),
        "thumb_url": image_url(sheet_path,
                               "?crop=%s&crop_gravity=%s&width=%d"
                               % (CROP, gravity_of(item), THUMB_WIDTH)),
        "thumb_path": "thumbs/%s%s" % (slug, IMAGE_EXT),
        "mid_url": image_url(sheet_path, "?width=%d" % MID_WIDTH),
        "mid_path": "mid/%s%s" % (slug, IMAGE_EXT),
    }
    # 契约是封闭的：字段多了少了都是 bug，在这里就报出来
    missing = [k for k in MANIFEST_FIELDS if k not in row]
    extra = [k for k in row if k not in MANIFEST_FIELDS]
    if missing or extra:
        raise ValueError("清单字段与 config.MANIFEST_FIELDS 不一致：缺 %s，多 %s"
                         % (missing, extra))
    return row


def main():
    data, items = load_items()
    scope = data.get("scope") or "?"
    pages = data.get("pages") or 0

    rows = []
    seen = set()
    dup = 0
    no_sheet = 0
    for item in items:
        row = build_row(item)
        if row is None:
            no_sheet += 1
            continue
        if row["id"] in seen:
            dup += 1
            continue
        seen.add(row["id"])
        rows.append(row)

    if not rows:
        sys.exit("一条清单都没生成：%d 条采集记录里没有可用的样例表" % len(items))

    # 顺序：沿用采集顺序（上游按热度排），不另外排序 ——
    # 页面默认展示的就是上游认为最值得看的那些。
    with open(os.path.join(SITE, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    with open(os.path.join(SITE, "manifest.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        for r in rows:
            out = dict((k, r.get(k, "")) for k in CSV_COLS)
            for k in FLAG_COLS:
                out[k] = 1 if r.get(k) else 0
            w.writerow(out)

    # ── 自检 ───────────────────────────────────────
    assert len(rows) > 0, "清单是空的"
    for t in TIERS:
        paths = [r[t + "_path"] for r in rows]
        assert len(paths) == len(set(paths)), "%s_path 重复" % t
        bad = [p for p in paths if "\\" in p or p.startswith("/") or ".." in p]
        assert not bad, "%s_path 不可移植：%s" % (t, bad[:3])
        assert all(r[t + "_url"].startswith(IMG_BASE) for r in rows), \
            "%s_url 不在图源 %s 下" % (t, IMG_BASE)
        assert all(r.get(t + "_url") and r.get(t + "_path") for r in rows), \
            "%s 档位有记录缺 url 或 path" % t
        # 图源地址里不能出现重复的 img/ 层：拼错时上游直接 404，
        # 而且清单本身不报错 —— 不专门查一遍就会一路错到下载阶段。
        assert not [r for r in rows if "/img/img/" in r[t + "_url"]], \
            "%s_url 里有重复的 img/" % t
    assert len({r["id"] for r in rows}) == len(rows), "id 重复"

    print("manifest: %d 条（scope=%s，%d 页）" % (len(rows), scope, pages))
    if dup:
        print("  跳过重复 slug %d 条" % dup)
    if no_sheet:
        print("  跳过没有样例表的条目 %d 条" % no_sheet)
    print("  kind 分布 %s"
          % collections.Counter(r["kind"] for r in rows).most_common())
    print("  category 分布 %s"
          % collections.Counter(r["category"] for r in rows).most_common())
    print("  带 SREF 码 %d 条 · 精选 %d · 公有领域 %d · 已实测 %d"
          % (sum(1 for r in rows if r["sref"]),
             sum(1 for r in rows if r["isPick"]),
             sum(1 for r in rows if r["isPublicDomain"]),
             sum(1 for r in rows if r["testedMark"])))
    size = os.path.getsize(os.path.join(SITE, "manifest.json"))
    print("  manifest.json %d 字节（%.1f KB）" % (size, size / 1024.0))
    print("  路径唯一性、可移植性与图源检查通过")


if __name__ == "__main__":
    main()
