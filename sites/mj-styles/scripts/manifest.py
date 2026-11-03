# -*- coding: utf-8 -*-
"""data/styles.json（风格码表）→ manifest.json。

manifest 契约（见 docs/ADDING_A_SITE.md 与 shared/assets.py）：
每条记录对 sites.json 里声明的每个 tier 都要有 <tier>_url 与 <tier>_path。

本站的记录形状
--------------
**一行 = 一个风格码的一张示例图**。一个码有三张（人像 / 风景 / 静物），
在 WebUI 里它们是**同一条素材的三个资产**（同一种视觉语言的三个场景），
所以 catalog.SOURCES 里声明 group_by="code"、group_order="index"：

    id         <码>_<kind>      唯一（一个码一张图）
    code       风格码           聚合键：一个码 = 一条素材
    index      0 / 1 / 2        组内顺序 = 灯箱翻页顺序（人像 → 风景 → 静物）
    kind       portrait|landscape|still_life
    kindZh     人像|风景|静物    分面值（中文）
    addedAt    首次收录时间      榜单是滚动的，这个时间稳定
    thumb_*    384 缩略         网格用
    full_*     1024 大图         灯箱用

档位只有两档：原站 CDN 只提供 128 / 384 / 640 / 1024 四档，本站用 384 做缩略、
1024 做灯箱（1024 由 fetch_styles.py 从 CDN 直接下，缩略是本地从 1024 缩出来的）。

图源说明：
    CDN 要求带上 Cloudflare 下发的 __cf_bm cookie，否则一律 403。
    取图走 scripts/fetch_styles.py（自己带 fetch_hook 的通行证），
    不走 tools/fetch.py —— 后者按 manifest 的 url 逐条下，这里是三种图 × N 个码。

路径一律用正斜杠、站点相对（styles/），与 tools/fetch.py 的约定一致。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, SITE)

from config import IMAGE_BASES, KIND_ZH, KINDS  # noqa: E402

CDN = IMAGE_BASES[0]
STYLES_JSON = os.path.join(SITE, "data", "styles.json")
MANIFEST = os.path.join(SITE, "manifest.json")

# 本地有的两档
LOCAL_TIERS = ["thumb", "full"]
TIERS = LOCAL_TIERS


def cdn_url(code, kind, size):
    return "%sstyles/0_%s/%s_%d_N.webp" % (CDN, code, kind, size)


def main():
    if not os.path.exists(STYLES_JSON):
        sys.exit("找不到 %s，先运行 python scripts/dump_styles.py" % STYLES_JSON)
    with open(STYLES_JSON, encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items") or []
    if not items:
        sys.exit("%s 里没有有效的风格码" % STYLES_JSON)

    rows = []
    for it in items:
        code = it.get("code") or (it.get("id", "").split("_")[-1])
        if not code or not code.isdigit():
            continue
        for index, kind in enumerate(KINDS):
            stem = "%s_%s" % (code, kind)
            rows.append({
                "id": stem,
                "code": code,
                "index": index,
                "kind": kind,
                "kindZh": KIND_ZH[kind],
                "addedAt": it.get("added_at") or "",
                "sourceUrl": "https://www.midjourney.com/styles/0_%s" % code,
                "width": it.get("width") or 0,
                "height": it.get("height") or 0,
                "thumb_url": cdn_url(code, kind, 384),
                "thumb_path": "styles/%s/s/%s.webp" % (code, kind),
                "full_url": cdn_url(code, kind, 1024),
                "full_path": "styles/%s/%s.webp" % (code, kind),
            })

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    n_codes = len({r["code"] for r in rows})
    print("写入 %s：%d 个码 × %d 张 = %d 行"
          % (MANIFEST, n_codes, len(KINDS), len(rows)))


if __name__ == "__main__":
    main()
