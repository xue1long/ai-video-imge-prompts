# -*- coding: utf-8 -*-
"""构建风格码库站点（mj-styles）。

产物
----
    index.html              首页（码库网格 + 灯箱 + SEO + FAQPage + 关于本站卡片）
    browse/index.html       分面索引页
    browse/<类型>/index.html  按示例图类型的落地页
    data/landing.json       落地页清单（release.py 据此复制）
    sitemap.xml  robots.txt  404.html  og-cover.jpg

用法（一般由 tools/build.py 调度，环境变量 SITE_URL 写进 canonical/og/sitemap）:
    SITE_URL=https://photoai.life/mj-styles python build_gallery.py

页面主体在 build_styles_page.py 里（码表 + 网格 + 灯箱）；本脚本只管**站点协议**
那一层，两边共用 data/styles.json 这份码表，不各读一份。

分面
----
风格码本身没有可枚举的分类（原站只有搜索框），唯一稳定的分组维度是
「这张示例图属于哪种构图」——人像 / 风景 / 静物，各 329 张，够 landing.py 的
最小分面数（6 张），三个类型都成页。
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(SITE))
sys.path.insert(0, HERE)
sys.path.insert(0, SITE)
sys.path.insert(0, os.path.join(ROOT, "shared"))

import landing as landing_mod                                   # noqa: E402
from config import (CODE, FACET_GROUP, FAQ, IMAGE_BASES, KIND_SLUG,  # noqa: E402
                    KIND_ZH, KINDS, SEO, SOURCE, UI)
import build_styles_page as page_mod                            # noqa: E402

SITE_URL = os.environ.get("SITE_URL", "https://example.com").rstrip("/")
# 图片在 styles/<码>/ 下，页面在站点根：落地页引用时要带前缀
IMG_PREFIX = page_mod.IMG_PREFIX


def load_codes():
    """返回 (items, latest, meta)。items = [(码, added_at)]，按首次收录时间倒序。"""
    return page_mod.load_items()


def count_stats(items):
    """站点要展示的统计数字：码数、示例图数、构图类型数。"""
    n_codes = len(items)
    n_shots = n_codes * len(KINDS)
    return {"n_codes": n_codes, "n_shots": n_shots, "n_kinds": len(KINDS)}


def fill(text, stats):
    """把 {n_codes} / {n_shots} 之类的占位符填上。"""
    return (text.replace("{n_codes}", str(stats["n_codes"]))
                .replace("{n_shots}", str(stats["n_shots"]))
                .replace("{n_kinds}", str(stats["n_kinds"])))


def build_facets(items):
    """按示例图类型分面：人像 / 风景 / 静物，各一张示例图一个码。"""
    by_kind = {k: [] for k in KINDS}
    for code, added in items:
        for k in KINDS:
            by_kind[k].append((code, added))

    facets = []
    for k in KINDS:
        codes = by_kind[k]
        if not codes:
            continue
        zh = KIND_ZH[k]
        facets.append(landing_mod.Facet(
            slug="kind/%s" % KIND_SLUG[k],
            title=f"{zh}示例图的 Midjourney 风格码 · {len(codes)} 个",
            h1=f"{zh} · Midjourney 风格码库",
            description=(f"Midjourney 风格码库中以{zh}构图展示的 {len(codes)} 个风格码，"
                         f"每个码附一张{zh}示例图，可一键复制 --sref 参数。"),
            intro=[f"这一页收录 Midjourney 风格码库里以{zh}构图展示的 {len(codes)} 个风格码。",
                   "同一个码在库里有三张示例图（人像 / 风景 / 静物），这里按构图拆开看。",
                   "码可以直接复制成 --sref 参数贴进提示词。"],
            items=[landing_mod.Item(
                thumb="%s%s/s/%s.webp" % (IMG_PREFIX, code, k),
                alt="风格码 %s 的%s示例图" % (code, zh),
                caption=code,
                w=384, h=576) for code, _ in codes],
            # 落地页回到首页时带上 #kind=<类型>，首页据此筛出该构图
            gallery_hash="kind=" + KIND_SLUG[k],
            facts=[("构图类型", zh), ("风格码", "%d 个" % len(codes)),
                   ("授权", "禁止再分发")],
            related=[("kind/%s" % KIND_SLUG[o], KIND_ZH[o], len(by_kind[o]))
                     for o in KINDS if o != k],
            group=FACET_GROUP,
            label=zh))

    site = landing_mod.Site(
        id=os.path.basename(SITE), root=SITE, site_url=SITE_URL,
        name=UI["zh"]["name"], tagline=UI["zh"]["tagline"],
        license_note=UI["zh"]["licenseNote"],
        author=UI["zh"]["author"], author_url=UI["zh"]["authorUrl"], source=SOURCE,
        faq=FAQ, accent="#0f766e",
        index_title=UI["zh"]["name"] + " · 全部示例图类型",
        index_intro="按示例图的构图类型浏览风格码：每个码在库里有三张示例图，"
                    "这里按人像 / 风景 / 静物拆开。")
    return site, facets


def build_index(items, latest, meta, stats):
    """首页：页面主体来自 build_styles_page.py，这里注入站点协议内容。"""
    zh = UI["zh"]
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "name": SEO["schemaName"], "url": SITE_URL + "/",
             "inLanguage": ["zh-CN", "ja"]},
            {"@type": "ImageGallery", "name": SEO["schemaName"],
             "alternateName": SEO["schemaAlt"], "url": SITE_URL + "/",
             "numberOfItems": stats["n_shots"], "about": SEO["schemaAbout"],
             "isAccessibleForFree": True,
             "creator": {"@type": "Organization", "name": zh["author"],
                         "url": zh["authorUrl"]}},
        ],
    }
    facts = [(k, fill(v, stats)) for k, v in zh["facts"]]
    links = [("browse/", "按示例图类型浏览")]
    paras = [fill(zh["lead"], stats), fill(zh["lead2"], stats)]
    seointro = landing_mod.static_intro(paras, facts, links, FAQ)

    extra = {
        "title": fill(SEO["title"], stats),
        "desc": fill(SEO["desc"], stats),
        "ogsite": fill(SEO["ogSite"], stats),
        "ogtitle": fill(SEO["ogTitle"], stats),
        "ogdesc": fill(SEO["ogDesc"], stats),
        "twtitle": fill(SEO["twTitle"], stats),
        "twdesc": fill(SEO["twDesc"], stats),
        "schema": json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
        "faqld": landing_mod.faq_ld_script(FAQ),
        "seointro": seointro,
        "eyebrow": zh["eyebrow"],
        "h1": "Midjourney 风格码库",
        "back": zh["backHome"],
        "lead": fill(zh["lead"], stats),
        "search": zh["searchPlaceholder"],
        "onlynew": zh["onlyNew"],
        "copyall": zh["copyAll"],
        "empty": zh["empty"],
    }
    return page_mod.build_html(items, latest, meta, site_url=SITE_URL, extra=extra)


def write_404():
    zh = UI["zh"]
    body = ("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>404 · %s</title>"
            "<link rel=\"icon\" href=\"/favicon.ico\" sizes=\"48x48\">"
            "<link rel=\"stylesheet\" href=\"/favicon.svg\" type=\"image/svg+xml\">"
            "<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;"
            "font:15px/1.7 system-ui,-apple-system,\"Segoe UI\",\"Noto Sans SC\",sans-serif;"
            "background:#fafaf9;color:#1c1917}main{text-align:center;padding:24px}"
            "h1{font-size:56px;margin:0 0 8px;letter-spacing:-.03em}"
            "p{color:#57534e;margin:0 0 18px}a{color:#0f766e;text-decoration:none;font-weight:600}"
            "@media(prefers-color-scheme:dark){body{background:#0c0a09;color:#f5f5f4}p{color:#a8a29e}"
            "a{color:#2dd4bf}}</style></head><body><main><h1>404</h1>"
            "<p>%s</p><a href=\"./\">%s</a></main></body></html>"
            % (zh["name"], zh["notFound"], zh["backSite"]))
    with open(os.path.join(SITE, "404.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(body)


def write_robots():
    with open(os.path.join(SITE, "robots.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)


def copy_og_cover():
    """用第一张示例图当 og-cover（没有独立封面资源时）。"""
    src = os.path.join(SITE, "og-cover.jpg")
    if os.path.exists(src):
        return
    items, _latest, _meta = load_codes()
    if not items:
        return
    cand = os.path.join(SITE, IMG_PREFIX, items[0][0], "portrait.webp")
    if not os.path.exists(cand):
        return
    try:
        from PIL import Image
    except ImportError:
        shutil.copyfile(cand, src)
        return
    with Image.open(cand) as im:
        if im.mode != "RGB":
            im = im.convert("RGB")
        w, h = im.size
        tw, th = 1200, 630
        scale = max(tw / w, th / h)
        nw, nh = int(w * scale + 1), int(h * scale + 1)
        im = im.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - tw) // 2, (nh - th) // 2
        im.crop((left, top, left + tw, top + th)).save(src, "JPEG", quality=88)
    print("og-cover.jpg 已生成")


def main():
    items, latest, meta = load_codes()
    stats = count_stats(items)

    # 缺图是硬失败：不生成一个图片全 404 的页面（详见 build_styles_page.py）
    missing = page_mod.check_images(items)
    if missing:
        print("缺图 %d 个，未生成页面：" % len(missing), file=sys.stderr)
        for rel in missing[:15]:
            print("  " + rel, file=sys.stderr)
        if len(missing) > 15:
            print("  …还有 %d 个" % (len(missing) - 15), file=sys.stderr)
        print("\n先补齐：python scripts/fetch_styles.py", file=sys.stderr)
        return 1

    page = build_index(items, latest, meta, stats)
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    # 静态落地页
    site, facets = build_facets(items)
    urls = landing_mod.write_site(site, facets)
    landing_mod.sitemap(SITE_URL, urls, os.path.join(SITE, "sitemap.xml"))

    write_404()
    write_robots()
    copy_og_cover()

    size = os.path.getsize(os.path.join(SITE, "index.html")) / 1024
    print("index.html %.1f KB（%d 个码 / %d 张示例图）"
          % (size, stats["n_codes"], stats["n_shots"]))
    print("落地页 %d 个" % len(urls))


if __name__ == "__main__":
    main()
