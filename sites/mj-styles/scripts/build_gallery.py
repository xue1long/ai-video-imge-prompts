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
from config import CODE, FAQ, IMAGE_BASES, KINDS, SEO, SOURCE, UI  # noqa: E402
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
    """返回 (site, facets)。facets 为空 → 本站不生成落地页。

    2026-11-04：这个站**不再生成落地页**（用户裁决）。
    风格码本身没有可枚举的分类，唯一稳定的分组维度是「这张示例图属于
    哪种构图」——而这个维度已经由首页顶部的全站构图切换器（#kind=…）
    覆盖了，再单独开三个落地页只是重复内容、还多一份维护成本。
    仍然返回 site，是为了让 shared/landing.py 的 write_site 能照常把上次的
    落地页清掉（写一份空 landing.json），release.py 与 sitemap 随之收敛。
    """
    site = landing_mod.Site(
        id=os.path.basename(SITE), root=SITE, site_url=SITE_URL,
        name=UI["zh"]["name"], tagline=UI["zh"]["tagline"],
        license_note=UI["zh"]["licenseNote"],
        author=UI["zh"]["author"], author_url=UI["zh"]["authorUrl"], source=SOURCE,
        faq=FAQ, accent="#0f766e",
        index_title=UI["zh"]["name"] + " · 全部示例图类型",
        index_intro="按示例图的构图类型浏览风格码：每个码在库里有三张示例图，"
                    "这里按人像 / 风景 / 静物拆开。")
    return site, []


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
    # 2026-11-04：落地页已删除，首页不再链到 browse/（会 404）
    links = []
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

    # 缺图：本地有图时才检查，缺了报出来但不阻断构建。
    #
    # 为什么不再硬失败（2026-11-04）：
    #   1. 这个站的图片不入库（.gitignore: sites/*/styles/*），CI 的干净检出
    #      上必然「缺图 1974 个」。硬失败意味着 CI 永远红。
    #   2. 更要紧的是「构建产物只取决于配置」这条约定（shared/image_policy.py）：
    #      同一份代码在有图与无图的环境里必须产出同一份页面。硬失败会让本地
    #      与 CI 产出不同结果 —— 那正是这个 bug 的根源。
    #   3. 本地仍然保留告警：缺图时把清单打到 stderr，人能看见。
    missing = page_mod.check_images(items)
    if missing:
        print("缺图 %d 个（页面仍会生成，部署后需要补图）：" % len(missing), file=sys.stderr)
        for rel in missing[:15]:
            print("  " + rel, file=sys.stderr)
        if len(missing) > 15:
            print("  …还有 %d 个" % (len(missing) - 15), file=sys.stderr)
        print("先补齐：python scripts/fetch_styles.py", file=sys.stderr)

    page = build_index(items, latest, meta, stats)
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    # 落地页：2026-11-04 起本站不生成落地页（用户裁决）。
    # 仍然调用 write_site —— 它会把上次生成的落地页清掉（写一份空 landing.json），
    # 这样 release.py 与 sitemap 都自动跟着收敛，不需要各处单独改。
    site, facets = build_facets(items)
    urls = landing_mod.write_site(site, facets)
    landing_mod.sitemap(SITE_URL, urls, os.path.join(SITE, "sitemap.xml"))

    write_404()
    write_robots()
    copy_og_cover()

    size = os.path.getsize(os.path.join(SITE, "index.html")) / 1024
    print("index.html %.1f KB（%d 个码 / %d 张示例图）"
          % (size, stats["n_codes"], stats["n_shots"]))
    print("落地页 %d 个（本站不生成落地页）" % len(urls))
    return 0


if __name__ == "__main__":
    sys.exit(main())
