# -*- coding: utf-8 -*-
"""构建 PromptHero Midjourney 提示词集（PROMPTHERO-MJ-01）

页面逻辑在本文件内；文案与分面名表在 config.py。

产出：
  index.html              单文件画廊（数据外置为分片，页面本身约 45 KB）
  data/gallery.js         分类与版本索引（入库）
  data/gallery_<cat>.js   各分类数据分片（不入库，由脚本重建）
  data/landing.json       落地页清单
  browse/ cat/ ver/       静态落地页（成人分类不生成）
  robots.txt sitemap.xml 404.html og-cover.jpg

用法（一般由 tools/build.py 调度，环境变量 SITE_URL 写进 canonical/og/sitemap）：
  SITE_URL=https://photoai.life/prompthero-midjourney python build_gallery.py
"""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(SITE))
sys.path.insert(0, HERE)
sys.path.insert(0, SITE)
sys.path.insert(0, os.path.join(ROOT, "shared"))

import landing as landing_mod                                   # noqa: E402
from image_policy import FB_JS, site_entry, tier_addr  # noqa: E402
from config import (ADULT_CATEGORIES, CATEGORY_ZH, CONFIG, ORIGIN,  # noqa: E402
                    SOURCE, UI, VERSION_ZH)

# 取图策略：按档位声明在站点清单里，决定展示地址与回落地址
SITE_CFG = site_entry("prompthero-midjourney")

SITE_URL = os.environ.get("SITE_URL",
                          "https://example.com/prompthero-midjourney").rstrip("/")
PAGE_SIZE = 240          # 增量渲染：每批渲染多少张
ADULT_KEY = "adult"      # 成人内容在分片里的键


def load_manifest():
    p = os.path.join(SITE, "manifest.json")
    if not os.path.exists(p):
        sys.exit("找不到 manifest.json，先运行 python scripts/manifest.py")
    return json.load(open(p, encoding="utf-8"))


def slug_of(cat):
    """分类 → URL 安全的分片键与目录名。"""
    return (cat or "uncategorized").replace(" ", "-").replace("/", "-").lower()


def build_shards(rows):
    """按分类分片。成人内容单独一片（默认模糊，且不生成落地页）。"""
    shards = {}
    for r in rows:
        cat = r["category"] or "uncategorized"
        key = slug_of(cat)
        shards.setdefault(key, []).append(r)

    out = {}
    for key, items in shards.items():
        data = []
        for r in items:
            data.append({
                "i": r["id"],
                "t": r["title"],
                "p": r["prompt"],
                "c": r["category"],
                "v": r["modelVersion"],
                "n": r["isNsfw"],
                "f": r["favCount"],
                "w": r["viewCount"],
                "d": r["createdAt"],
                # 取图策略要求的编码（见 shared/image_policy.py）：
                #   <字段>     展示地址（直连上游时是上游 URL，否则是站内相对路径）
                #   <字段>Url  上游地址，仅本地优先时写出，作为加载失败的回落目标
                #   <字段>Path 站内相对路径，仅直连上游时写出，供按路径推导的规则使用
                **_addr(SITE_CFG, "thumb", r, "s"),
                **_addr(SITE_CFG, "mid", r, "m"),
                **_addr(SITE_CFG, "full", r, "g"),
                "u": r["sourceUrl"],
                "W": r["width"],
                "H": r["height"],
            })
        out[key] = data
    return out


def _addr(site, tier, rec, fkey):
    """该档位的展示地址与伴随字段（见 shared/image_policy.py 的编码约定）。"""
    path = rec[tier + "_path"]
    url = rec.get(tier + "_url") or ""
    display, fallback, keep_path = tier_addr(site, tier, path, url)
    out = {fkey: display}
    if fallback:
        out[fkey + "Url"] = fallback
    if keep_path:
        out[fkey + "Path"] = path
    return out

def write_shards(shards):
    """写出 data/gallery_<cat>.js。每个分片一个 JSON.parse 赋值。"""
    data_dir = os.path.join(SITE, "data")
    os.makedirs(data_dir, exist_ok=True)
    # 清理旧分片
    for fn in os.listdir(data_dir):
        if fn.startswith("gallery_") and fn.endswith(".js"):
            os.remove(os.path.join(data_dir, fn))
    for key, data in shards.items():
        path = os.path.join(data_dir, "gallery_%s.js" % key)
        payload = json.dumps({"items": data}, ensure_ascii=False, separators=(",", ":"))
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("window.__SHARDS__=window.__SHARDS__||{};window.__SHARDS__[%s]=JSON.parse(%s);\n"
                    % (json.dumps(key), json.dumps(payload)))
    return len(shards)


def write_index(rows, shards):
    """data/gallery.js：分类与版本索引 + 计数。"""
    cats = {}
    vers = {}
    for r in rows:
        c = r["category"] or "uncategorized"
        cats[c] = cats.get(c, 0) + 1
        v = r["modelVersion"] or "-"
        vers[v] = vers.get(v, 0) + 1
    idx = {
        "cats": [{"k": slug_of(k), "c": k, "n": n, "z": CATEGORY_ZH.get(k, k),
                  "a": 1 if k in ADULT_CATEGORIES else 0}
                 for k, n in sorted(cats.items(), key=lambda kv: -kv[1])],
        "vers": [{"k": k, "n": n, "z": VERSION_ZH.get(k, k or "-")}
                 for k, n in sorted(vers.items(), key=lambda kv: -kv[1])],
        "total": len(rows),
        "nsfw": sum(1 for r in rows if r["isNsfw"]),
        "shards": sorted(shards.keys()),
    }
    with open(os.path.join(SITE, "data", "gallery.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("window.__GALLERY__=JSON.parse(%s);\n" % json.dumps(json.dumps(idx, ensure_ascii=False),
                                                                  ensure_ascii=False))
    return idx


# ── 页面模板 ──────────────────────────────────────
PAGE = r"""<!doctype html>
<html lang="zh-CN" data-theme="light" data-lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<meta name="keywords" content="Midjourney提示词,Midjourney prompt,AI绘画提示词,提示词参考,PromptHero,提示词大全">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="__SITE__/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="参考素材库">
<meta property="og:title" content="__OGTITLE__">
<meta property="og:description" content="__OGDESC__">
<meta property="og:url" content="__SITE__/">
<meta property="og:image" content="__SITE__/og-cover.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TWTITLE__">
<meta name="twitter:description" content="__TWDESC__">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>__CSS__</style>
<script>
/* 主题与语言：先读本地偏好，避免刷新闪白 */
(function(){
  try{
    var t = localStorage.getItem("ph.theme");
    if(t) document.documentElement.setAttribute("data-theme", t);
    var l = localStorage.getItem("ph.lang");
    if(l) document.documentElement.setAttribute("data-lang", l);
  }catch(e){}
})();
</script>
__FB_JS__
</head>
<body>
<header class="top">
  <div class="wrap">
    <a class="home" href="../"><span class="h1">__BRAND1__</span><span class="h2">__BRAND2__</span></a>
    <div class="topright">
      <button id="themeBtn" class="sw" type="button" aria-label="__THEME_ARIA__"></button>
      <button id="langBtn" class="sw" type="button"></button>
    </div>
  </div>
</header>

<main class="wrap">
  <p class="eyebrow">__EYEBROW__</p>
  <h1 id="pagetitle">__TITLE__</h1>
  <p class="lead">__SUB1__</p>
  <p class="lead2">__SUB2__</p>

  <div class="stats" id="stats"></div>

  <section class="tools" aria-label="__FILTER__">
    <input id="q" type="search" autocomplete="off" placeholder="__SEARCH__">
    <div class="sel">
      <button class="chip" id="catBtn" type="button" aria-haspopup="true" aria-expanded="false">__CAT_ALL__</button>
      <button class="chip" id="verBtn" type="button" aria-haspopup="true" aria-expanded="false">__VER_ALL__</button>
      <button class="chip" id="sortBtn" type="button" aria-haspopup="true" aria-expanded="false">__SORT_FAV__</button>
      <div class="switch blursw" role="group"><button id="blurBtn" type="button"></button></div>
    </div>
    <div class="menus" id="catMenu" hidden></div>
    <div class="menus" id="verMenu" hidden></div>
    <div class="menus" id="sortMenu" hidden>
      <button type="button" data-sort="fav">__SORT_FAV__</button>
      <button type="button" data-sort="new">__SORT_NEW__</button>
      <button type="button" data-sort="view">__SORT_VIEW__</button>
    </div>
  </section>

  <p class="count" id="count"></p>
  <div class="grid" id="grid"></div>
  <p class="empty" id="empty" hidden>__EMPTY_TITLE__<br><span>__EMPTY_DESC__</span></p>
  <div class="more"><button id="more" type="button" hidden>加载更多</button></div>
</main>

<section class="seo-intro" aria-label="关于本站">__SEO_INTRO__</section>

<footer class="wrap" id="foot"></footer>

<div class="modal" id="modal" hidden>
  <button class="close" id="close" type="button" aria-label="关闭">×</button>
  <button class="nav prev" id="prev" type="button" aria-label="上一张">‹</button>
  <button class="nav next" id="next" type="button" aria-label="下一张">›</button>
  <div class="stage" id="stage">
    <img id="big" alt="">
    <div class="spin" id="spin"></div>
  </div>
  <div class="panel" id="panel">
    <p class="ptxt" id="ptxt"></p>
    <div class="prow">
      <button id="copyBtn" class="btn" type="button">__COPY__</button>
      <a id="originBtn" class="btn" target="_blank" rel="noopener noreferrer">__ORIGIN__</a>
      <a id="dlBtn" class="btn" download>__DLFULL__</a>
    </div>
    <p class="pmeta" id="pmeta"></p>
  </div>
</div>

<script src="data/gallery.js"></script>
<script>__JS__</script>
</body>
</html>
"""


CSS = """
*{box-sizing:border-box}
:root{
  --bg:#f7f6f3;--panel:#fff;--tx:#191b1f;--tx2:#525b6a;--tx3:#8a93a3;
  --line:#e3e7ed;--ac:#c2410c;--scrim:rgba(12,14,18,.72);
}
html[data-theme="dark"]{
  --bg:#0e1014;--panel:#161a21;--tx:#e8ebf0;--tx2:#a6b0c0;--tx3:#6d7787;
  --line:#252b35;--ac:#fb923c;--scrim:rgba(0,0,0,.82);
}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--tx);
  font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
  font-size:14px;line-height:1.65;-webkit-font-smoothing:antialiased}
.wrap{max-width:1280px;margin:0 auto;padding:0 clamp(16px,4vw,40px)}
a{color:var(--ac)}
.top{position:sticky;top:0;z-index:30;background:var(--bg);border-bottom:1px solid var(--line)}
.top .wrap{display:flex;align-items:center;justify-content:space-between;height:58px}
.home{display:flex;align-items:baseline;gap:8px;text-decoration:none;color:var(--tx)}
.home .h1{font-weight:500;font-size:16px}
.home .h2{font-size:13px;color:var(--tx2)}
.topright{display:flex;gap:8px}
.sw{border:1px solid var(--line);background:var(--panel);color:var(--tx2);
  border-radius:999px;padding:6px 13px;font-size:12.5px;cursor:pointer;font-family:inherit}
.sw:hover{border-color:var(--tx3)}
.eyebrow{font-size:11.5px;letter-spacing:.08em;color:var(--tx3);margin:22px 0 6px}
h1{font-size:clamp(20px,3.4vw,28px);font-weight:500;margin:0 0 10px;line-height:1.35}
.lead{color:var(--tx2);margin:0 0 6px;max-width:74ch}
.lead2{color:var(--tx3);margin:0 0 16px;max-width:74ch;font-size:13px}
.stats{display:flex;gap:22px;flex-wrap:wrap;margin:0 0 18px;padding:12px 0;
  border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.stats div{display:flex;flex-direction:column}
.stats b{font-size:19px;font-weight:500;font-variant-numeric:tabular-nums}
.stats span{font-size:11.5px;color:var(--tx3)}
.tools{position:relative;display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
#q{flex:1;min-width:200px;padding:9px 14px;border:1px solid var(--line);border-radius:10px;
  background:var(--panel);color:var(--tx);font-size:13.5px;font-family:inherit}
#q:focus{outline:none;border-color:var(--ac)}
.sel{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.chip{border:1px solid var(--line);background:var(--panel);color:var(--tx2);border-radius:999px;
  padding:8px 14px;font-size:12.5px;cursor:pointer;font-family:inherit}
.chip:hover{border-color:var(--tx3);color:var(--tx)}
.chip.on{border-color:var(--ac);color:var(--ac)}
.menus{position:absolute;top:100%;left:0;z-index:20;margin-top:6px;background:var(--panel);
  border:1px solid var(--line);border-radius:12px;padding:8px;max-height:60vh;overflow:auto;
  min-width:220px;box-shadow:0 8px 28px rgba(0,0,0,.12)}
.menus button{display:block;width:100%;text-align:left;padding:7px 11px;border:0;border-radius:8px;
  background:none;color:var(--tx2);font-size:13px;cursor:pointer;font-family:inherit}
.menus button:hover{background:var(--bg);color:var(--tx)}
.menus button.on{color:var(--ac)}
.count{font-size:12.5px;color:var(--tx3);margin:0 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px}
.card{position:relative;margin:0;cursor:pointer;background:var(--panel);
  border:1px solid var(--line);border-radius:12px;overflow:hidden}
.card:hover{border-color:var(--tx3)}
.ph{position:relative;aspect-ratio:3/4;background:var(--bg);overflow:hidden}
.ph img{width:100%;height:100%;object-fit:cover;display:block}
.card .cap{padding:8px 10px 10px;font-size:12px;color:var(--tx2);line-height:1.45;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card .meta{display:flex;gap:8px;align-items:center;padding:0 10px 9px;font-size:11px;color:var(--tx3)}
.badge{font-size:10px;padding:1px 6px;border-radius:999px;border:1px solid var(--ac);color:var(--ac)}
/* 成人内容默认模糊：点开单张或开全局开关才清晰 */
html.blur-on .card[data-n="1"]:not(.unblur) .ph img{filter:blur(16px)}
html.blur-on .card[data-n="1"]:not(.unblur) .ph::after{
  content:attr(data-blur);position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
  font-size:11.5px;color:#fff;background:rgba(12,14,18,.66);padding:5px 11px;border-radius:999px;
  white-space:nowrap;pointer-events:none}
.switch.blursw button{width:auto;padding:7px 12px;font-size:12px;border:1px solid var(--line);
  background:var(--panel);color:var(--tx2);border-radius:999px;cursor:pointer;font-family:inherit}
.empty{text-align:center;color:var(--tx2);padding:60px 0;font-size:14px}
.empty span{color:var(--tx3);font-size:12.5px}
.more{display:flex;justify-content:center;padding:26px 0 10px}
.more button{border:1px solid var(--line);background:var(--panel);color:var(--tx2);
  border-radius:999px;padding:10px 22px;font-size:13px;cursor:pointer;font-family:inherit}
.more button:hover{border-color:var(--tx3)}
.seo-intro{margin-top:10px}
footer{color:var(--tx3);font-size:12px;padding:26px 0 40px;border-top:1px solid var(--line);margin-top:26px}
footer a{color:var(--tx2)}
.modal{position:fixed;inset:0;z-index:60;background:var(--scrim);display:flex;
  align-items:center;justify-content:center;gap:18px;padding:20px}
.modal[hidden]{display:none}
.stage{position:relative;flex:1;min-width:0;height:88vh;display:flex;align-items:center;justify-content:center}
.stage img{max-width:100%;max-height:100%;object-fit:contain;border-radius:6px;
  background:var(--panel);opacity:0;transition:opacity .22s ease}
.stage img.on{opacity:1}
.spin{position:absolute;width:26px;height:26px;border:2px solid rgba(255,255,255,.28);
  border-top-color:#fff;border-radius:50%;animation:sp .8s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.panel{flex:0 0 min(430px,38vw);color:#fff;max-height:88vh;overflow:auto}
.ptxt{font-size:13px;line-height:1.7;background:rgba(255,255,255,.08);padding:13px;
  border-radius:10px;white-space:pre-wrap;word-break:break-word;margin:0 0 12px}
.prow{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.btn{display:inline-block;border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.08);
  color:#fff;border-radius:999px;padding:8px 14px;font-size:12.5px;cursor:pointer;
  text-decoration:none;font-family:inherit}
.btn:hover{background:rgba(255,255,255,.16)}
.close,.nav{position:absolute;z-index:5;background:rgba(255,255,255,.1);border:0;color:#fff;
  width:38px;height:38px;border-radius:50%;font-size:22px;cursor:pointer;line-height:1}
.close{top:16px;right:16px}
.nav{top:50%;margin-top:-19px}
.prev{left:16px}.next{right:16px}
.pmeta{font-size:11.5px;color:rgba(255,255,255,.72);margin:0}
@media(max-width:860px){
  .modal{flex-direction:column;justify-content:flex-start;padding:52px 14px 14px}
  .stage{height:46vh;flex:none;width:100%}
  .panel{flex:none;width:100%;max-height:44vh}
}
"""


def build_facets(rows):
    """生成落地页分面：分类 + 版本。成人分类不生成（不进 sitemap，不被搜索引擎收录）。"""
    site = landing_mod.Site(
        id=CONFIG["seoPages"]["id"],
        root=SITE,
        site_url=SITE_URL,
        name=CONFIG["seoPages"]["name"],
        tagline=CONFIG["seoPages"]["tagline"],
        license_note=CONFIG["seoPages"]["licenseNote"],
        author=CONFIG["seoPages"]["author"],
        author_url=CONFIG["seoPages"]["authorUrl"],
        source=SOURCE,
        faq=CONFIG["seoPages"]["faq"],
        accent=CONFIG["seoPages"]["accent"],
        index_title=CONFIG["seoPages"]["name"] + " · 全部分类与版本",
        index_intro="按分类与 Midjourney 版本浏览 %d 条提示词与成图：人像、摄影、概念艺术、角色设计、动漫、时尚等 14 个分类，v1 至 v7 与 Niji 共 13 个版本；每条都附生成图与提示词原文，灯箱内可直接复制。" % len(rows),
    )

    by_cat = {}
    by_ver = {}
    for r in rows:
        by_cat.setdefault(r["category"] or "uncategorized", []).append(r)
        by_ver.setdefault(r["modelVersion"] or "-", []).append(r)

    facets = []

    def mk_item(r):
        # alt 至少 6 个字符：提示词可能很短（甚至以符号开头），
        # 用「分类 · 版本 · 提示词摘要」兜底，保证可读且长度达标。
        summary = (r["prompt"] or "").strip()
        if len(summary) > 60:
            summary = summary[:60] + "…"
        alt = "%s · %s · %s" % (CATEGORY_ZH.get(r["category"], r["category"]),
                                VERSION_ZH.get(r["modelVersion"], r["modelVersion"] or "-"),
                                summary or "Midjourney 生成图")
        return landing_mod.Item(
            thumb=r["thumb_path"],
            alt=alt,
            caption=r["modelVersion"] or "",
            w=r["width"], h=r["height"])

    for cat, items in by_cat.items():
        if cat in ADULT_CATEGORIES:
            continue
        zh = CATEGORY_ZH.get(cat, cat)
        n = len(items)
        facets.append(landing_mod.Facet(
            slug="cat/" + slug_of(cat),
            title="%s · Midjourney 提示词与成图 · %d 条" % (zh, n),
            h1="%s（Midjourney 提示词与成图）" % zh,
            description="Midjourney %s 分类的 %d 条提示词与对应生成图，可按版本筛选，提示词原文可直接复制到 Midjourney 使用。" % (zh, n),
            intro=["这一页是 Midjourney 提示词集「%s」分类的静态索引，共 %d 条。"
                   "每条都附了生成图与提示词原文（含 --ar、--stylize 等参数）。"
                   % (zh, n),
                   "提示词由 PromptHero 社区用户上传，版权归各原作者。本站为个人学习用途的中文索引镜像，"
                   "图片文件本身不再分发；需要原图请回链原站。"],
            items=[mk_item(r) for r in items],
            gallery_hash="cat=" + cat,
            facts=[("分类", zh), ("提示词", "%d 条" % n)],
            group="分类",
            label=zh,
        ))

    for ver, items in by_ver.items():
        zh = VERSION_ZH.get(ver, ver or "-")
        n = len(items)
        facets.append(landing_mod.Facet(
            slug="ver/" + slug_of(ver),
            title="Midjourney %s · 提示词与成图 · %d 条" % (zh, n),
            h1="Midjourney %s（提示词与成图）" % zh,
            description="Midjourney %s 的 %d 条提示词与对应生成图，含该版本常用的参数写法与构图思路，可按分类继续筛选。" % (zh, n),
            intro=["这一页汇总 Midjourney %s 版本的 %d 条提示词与生成图。" % (zh, n),
                   "不同版本的参数语法有差异（例如 --v 6 与 --v 6.1 的写法和画面倾向），"
                   "照抄原版本号能更接近原图效果。"],
            items=[mk_item(r) for r in items],
            gallery_hash="ver=" + ver,
            facts=[("版本", zh), ("提示词", "%d 条" % n)],
            group="版本",
            label=zh,
        ))

    return site, facets


def main():
    rows = load_manifest()
    print("manifest: %d 条" % len(rows))

    shards = build_shards(rows)
    n_shards = write_shards(shards)
    idx = write_index(rows, shards)
    print("分片: %d 个，索引: %d 分类 / %d 版本" % (n_shards, len(idx["cats"]), len(idx["vers"])))

    site, facets = build_facets(rows)
    urls = landing_mod.write_site(site, facets)
    print("落地页: %d 个" % (len(urls) - 1))

    # 页面
    ui = UI["zh"]
    html = (PAGE
            .replace("__TITLE__", ui["title"])
            .replace("__DESC__", CONFIG["desc"])
            .replace("__OGTITLE__", CONFIG["ogTitle"])
            .replace("__OGDESC__", CONFIG["ogDesc"])
            .replace("__TWTITLE__", CONFIG["twTitle"])
            .replace("__TWDESC__", CONFIG["twDesc"])
            .replace("__SITE__", SITE_URL)
            .replace("__FB_JS__", FB_JS)
            .replace("__BRAND1__", ui["brand1"])
            .replace("__BRAND2__", ui["brand2"])
            .replace("__EYEBROW__", ui["eyebrow"])
            .replace("__SUB1__", ui["sub1"])
            .replace("__SUB2__", ui["sub2"])
            .replace("__FILTER__", ui["filter"])
            .replace("__SEARCH__", ui["search"])
            .replace("__CAT_ALL__", ui["catAll"])
            .replace("__VER_ALL__", ui["verAll"])
            .replace("__SORT_FAV__", ui["sortFav"])
            .replace("__SORT_NEW__", ui["sortNew"])
            .replace("__SORT_VIEW__", ui["sortView"])
            .replace("__EMPTY_TITLE__", ui["emptyTitle"])
            .replace("__EMPTY_DESC__", ui["emptyDesc"])
            .replace("__COPY__", ui["copyPrompt"])
            .replace("__ORIGIN__", ui["openOrigin"])
            .replace("__DLFULL__", ui["dlFull"])
            .replace("__THEME_ARIA__", ui["themeAria"])
            .replace("__CSS__", CSS)
            .replace("__SEO_INTRO__", "")
            .replace("__JS__", build_js(idx)))
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    # 静态介绍与 FAQ（补进页面，供搜索引擎与 AI 读取）
    inject_seo_intro(html_path=os.path.join(SITE, "index.html"), rows=rows, urls=urls)
    print("index.html %.1f KB"
          % (os.path.getsize(os.path.join(SITE, "index.html")) / 1024))

    # robots / sitemap / 404
    with open(os.path.join(SITE, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)
    landing_mod.sitemap(SITE_URL, urls, os.path.join(SITE, "sitemap.xml"))
    write_404()

    # 社交分享图（取第一张缩略图；缺失时用占位）
    copy_og_cover()


def build_js(idx):
    """页面脚本。数据来自 data/gallery.js（索引）与按需加载的分类分片。

    文案中英日三语里的中日双语部分内嵌成两个对象，切换语言时只换 UI 引用。
    """
    ui_zh = {k: v for k, v in UI["zh"].items()}
    ui_ja = {k: v for k, v in UI["ja"].items()}
    js = r"""
var IDX = window.__GALLERY__;
var $ = function(s){ return document.querySelector(s); };
var lang = document.documentElement.getAttribute("data-lang") || "zh";
var UI = __UI_ZH__;
var PAGE_SIZE = __PAGESIZE__;var KEY = "ph";

var state = { q:"", cat:"", ver:"", sort:"fav", shown:0, rows:[] };
var _loaded = {}, _loading = {};

/* —— 分类分片：进站只加载默认分类，切分类时才拉另一份 —— */
function loadShard(key){
  if(_loaded[key]) return Promise.resolve();
  if(_loading[key]) return _loading[key];
  _loading[key] = new Promise(function(res, rej){
    var s = document.createElement("script");
    s.src = "data/gallery_" + key + ".js";
    s.async = true;
    s.onload = function(){
      var sh = (window.__SHARDS__||{})[key];
      if(!sh) return rej(new Error("分片为空: " + key));
      _loaded[key] = sh.items || [];
      res();
    };
    s.onerror = function(){ rej(new Error("分片加载失败: " + key)); };
    document.head.appendChild(s);
  });
  return _loading[key];
}

function catList(){
  return IDX.cats.map(function(c){ return { v:c.c, z:c.z, n:c.n, k:c.k, a:c.a }; });
}
function verList(){
  return IDX.vers.map(function(v){ return { v:v.k, z:v.z, n:v.n }; });
}
function catLabel(v){
  var l = catList(); for(var i=0;i<l.length;i++) if(l[i].v===v) return l[i].z;
  return v;
}
function verLabel(v){
  var l = verList(); for(var i=0;i<l.length;i++) if(l[i].v===v) return l[i].z;
  return v;
}
function isAdultCat(c){
  var l = catList(); for(var i=0;i<l.length;i++) if(l[i].v===c) return !!l[i].a;
  return false;
}

/* 默认分类：条目最多的非成人分类；成人分类不进落地页，但画廊里可筛 */
function defaultCat(){
  var l = catList(), best = "";
  for(var i=0;i<l.length;i++){ if(!l[i].a && !best) best = l[i].v; }
  return best;
}

function applyStatic(){
  document.title = UI.title;
  $("#pagetitle").textContent = UI.title;
  $("#q").placeholder = UI.search;
  $("#langBtn").textContent = lang === "zh" ? "日本語" : "中文";
  themeLabel();
  blurLabel();
}
function tx(key){ return UI[key]; }

function t(key, zh, ja){
  if(lang === "zh") return zh;
  return ja;
}

/* —— 主题与语言 —— */
function themeLabel(){
  var dark = document.documentElement.getAttribute("data-theme") === "dark";
  $("#themeBtn").textContent = dark ? t("themeLight","浅色","ライト") : t("themeDark","深色","ダーク");
  $("#themeBtn").setAttribute("aria-label", t("themeAria","主题","表示テーマ"));
}
$("#themeBtn").addEventListener("click", function(){
  var cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", cur);
  try{ localStorage.setItem(KEY+".theme", cur); }catch(e){}
  themeLabel();
});
$("#langBtn").addEventListener("click", function(){
  lang = lang === "zh" ? "ja" : "zh";
  document.documentElement.setAttribute("data-lang", lang);
  try{ localStorage.setItem(KEY+".lang", lang); }catch(e){}
  UI = lang === "zh" ? __UI_ZH__ : __UI_JA__;
  applyStatic(); syncChips(); render();
});

/* —— 成人内容默认模糊 —— */
var SHOW_ALL = false;
try{ SHOW_ALL = localStorage.getItem(KEY+".unblur") === "1"; }catch(e){}
var unblurred = {};
function blurLabel(){
  $("#blurBtn").textContent = SHOW_ALL ? t("blurOn","恢复模糊","ぼかす") : t("blurOff","取消模糊","ぼかしを解除");
  $("#blurBtn").setAttribute("aria-pressed", SHOW_ALL ? "true" : "false");
}
function applyBlur(){
  document.documentElement.classList.toggle("blur-on", !SHOW_ALL);
}
$("#blurBtn").addEventListener("click", function(){
  SHOW_ALL = !SHOW_ALL;
  try{ localStorage.setItem(KEY+".unblur", SHOW_ALL ? "1" : "0"); }catch(e){}
  applyBlur(); blurLabel();
});
applyBlur();

/* —— 筛选与排序 —— */
function buildMenus(){
  var cm = $("#catMenu"), vm = $("#verMenu");
  cm.innerHTML = catList().map(function(c){
    return '<button type="button" data-cat="'+esc(c.v)+'">'+esc(c.z)+' <small>'+c.n+'</small></button>';
  }).join("");
  vm.innerHTML = verList().map(function(v){
    return '<button type="button" data-ver="'+esc(v.v)+'">'+esc(v.z)+' <small>'+v.n+'</small></button>';
  }).join("");
}
function esc(s){
  return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
function openMenu(which){
  ["catMenu","verMenu","sortMenu"].forEach(function(id){
    var el = $("#"+id);
    if(id === which){ el.hidden = !el.hidden; }
    else el.hidden = true;
  });
  $("#catBtn").setAttribute("aria-expanded", which==="catMenu" && !$("#catMenu").hidden ? "true":"false");
}
$("#catBtn").addEventListener("click", function(){ openMenu("catMenu"); });
$("#verBtn").addEventListener("click", function(){ openMenu("verMenu"); });
$("#sortBtn").addEventListener("click", function(){ openMenu("sortMenu"); });
document.addEventListener("click", function(e){
  if(!e.target.closest(".tools")){
    ["catMenu","verMenu","sortMenu"].forEach(function(id){ $("#"+id).hidden = true; });
  }
  var b = e.target.closest("[data-cat]");
  if(b){ state.cat = b.getAttribute("data-cat"); state.ver=""; syncChips(); ensure(); return; }
  var v = e.target.closest("[data-ver]");
  if(v){ state.ver = v.getAttribute("data-ver"); state.cat=""; syncChips(); ensure(); return; }
  var s = e.target.closest("[data-sort]");
  if(s){ state.sort = s.getAttribute("data-sort"); syncChips(); render(); return; }
});
function syncChips(){
  $("#catBtn").textContent = state.cat ? catLabel(state.cat) : tx("catAll","全部分类","すべてのカテゴリ");
  $("#catBtn").classList.toggle("on", !!state.cat);
  $("#verBtn").textContent = state.ver ? verLabel(state.ver) : tx("verAll","全部版本","すべてのバージョン");
  $("#verBtn").classList.toggle("on", !!state.ver);
  var sl = { fav: tx("sortFav","按收藏","お気に入り順"), new: tx("sortNew","按最新","新着順"), view: tx("sortView","按浏览","閲覧順") };
  $("#sortBtn").textContent = sl[state.sort] || sl.fav;
}
$("#q").addEventListener("input", function(){ state.q = this.value.trim().toLowerCase(); state.shown = 0; render(); });

/* —— 数据装载 —— */
function ensure(){
  var need = [];
  if(state.cat){ need.push(catKey(state.cat)); }
  else if(state.ver){ need.push(catKey(state.ver)); }
  else { need = catList().map(function(c){ return c.k; }); }
  var todo = need.filter(function(k){ return !_loaded[k]; });
  if(!todo.length){ rebuild(); render(); return; }
  Promise.all(todo.map(loadShard)).then(function(){ rebuild(); render(); })
    .catch(function(e){ $("#foot").textContent = String((e&&e.message)||e); });
}
/* 版本筛选：版本不是独立的分片维度，落在各分类分片里，取出后再按版本过滤 */
function catKey(c){
  var l = catList();
  for(var i=0;i<l.length;i++) if(l[i].v===c) return l[i].k;
  return c;
}
function rebuild(){
  var rows = [];
  if(state.cat){
    rows = (_loaded[catKey(state.cat)] || []).slice();
  } else if(state.ver){
    var vs = state.ver;
    catList().forEach(function(c){
      (_loaded[c.k] || []).forEach(function(r){ if(r.v === vs) rows.push(r); });
    });
  } else {
    catList().forEach(function(c){ rows = rows.concat(_loaded[c.k] || []); });
  }
  if(state.q){
    rows = rows.filter(function(r){ return (r.p||"").toLowerCase().indexOf(state.q) >= 0; });
  }
  if(state.sort === "fav") rows.sort(function(a,b){ return (b.f||0)-(a.f||0); });
  else if(state.sort === "new") rows.sort(function(a,b){ return (b.d||"").localeCompare(a.d||""); });
  else rows.sort(function(a,b){ return (b.w||0)-(a.w||0); });
  state.rows = rows;
}

/* —— 渲染 —— */
function cardHTML(r, i){
  var adult = r.n ? ' data-n="1"' : "";
  var blurTxt = r.n ? ' data-blur="'+esc(tx("blurTap","点开查看","タップで表示"))+'"' : "";
  var un = unblurred[r.i] ? " unblur" : "";
  var badge = r.n ? '<span class="badge">'+esc(tx("nsfwBadge","成人内容","成人向け"))+'</span>' : "";
  return '<article class="card'+un+'" tabindex="0" data-i="'+i+'"'+adult+'>'
    + '<div class="ph"'+blurTxt+'><img src="'+esc(r.s)+'"'+(r.sUrl?' data-fb="'+esc(r.sUrl)+'"':'')+' alt="'+esc(r.t||r.p||"Midjourney 提示词成图")+'" loading="lazy" decoding="async"></div>'
    + '<div class="cap">'+esc(r.t||r.p||"")+'</div>'
    + '<div class="meta">'+badge+'<span>'+esc(r.v||"-")+'</span><span>♥ '+(r.f||0)+'</span></div>'
    + '</article>';
}
function render(){
  var grid = $("#grid");
  var rows = state.rows;
  $("#empty").hidden = rows.length > 0;
  $("#count").innerHTML = UI.countImg.replace("{n}", "<b>" + rows.length + "</b>");
  var slice = rows.slice(state.shown, state.shown + PAGE_SIZE);
  grid.insertAdjacentHTML("beforeend", slice.map(cardHTML).join(""));
  state.shown += slice.length;
  $("#more").hidden = state.shown >= rows.length;
}
$("#more").addEventListener("click", function(){ render(); });
gridReset();
function gridReset(){ $("#grid").innerHTML = ""; state.shown = 0; }

/* 滚动到底自动加载 */
var io = new IntersectionObserver(function(es){
  es.forEach(function(en){ if(en.isIntersecting && !$("#more").hidden) render(); });
}, { rootMargin: "400px" });
io.observe($("#more"));

/* —— 灯箱 —— */
var cur = -1;
/* 中图路径规则：img/x.png → mid/x.webp（与 tools/mid.py 的 mid_rel 一致）。
   manifest 的 m 字段是上游实际提供的档位（1080，或上游只有 640 时回落到 640）；
   上游没生成衍生图的条目 m 字段是缩略图 URL，此时 midOf 给出的路径不存在，
   灯箱用 m 字段，midOf 作为规则参考与兜底。 */
const midOf = function(p){ return "mid/" + String(p).replace(/\\/g, "/").replace(/^img\//, "").replace(/\.[^./]+$/, "") + ".webp" };
function open(i){
  cur = i;
  var r = state.rows[i];
  if(!r) return;
  if(r.n){ unblurred[r.i] = true; document.querySelectorAll('.card[data-i="'+i+'"]').forEach(function(c){ c.classList.add("unblur"); }); }
  $("#ptxt").textContent = r.p || "";
  $("#pmeta").textContent = [catLabel(r.c), r.v, "♥ " + (r.f||0), (r.w||0) + " views"].filter(Boolean).join(" · ");
  $("#originBtn").href = r.u;
  $("#dlBtn").href = r.g;
  // 直连上游时 download 属性跨源无效，改为新标签打开
  $("#dlBtn").target = /^https?:/.test(r.g) ? '_blank' : '';
  // 直连上游时 download 属性跨源无效，改为新标签打开
  $("#dlBtn").target = /^https?:/.test(r.g) ? '_blank' : '';
  var big = $("#big");
  big.classList.remove("on");
  $("#spin").style.display = "block";
  big.src = r.m;                      /* 先显示中图 */
  big.onload = function(){ big.classList.add("on"); $("#spin").style.display = "none"; };
  $("#modal").hidden = false;
}
function close(){ $("#modal").hidden = true; cur = -1; }
$("#close").addEventListener("click", close);
$("#modal").addEventListener("click", function(e){ if(e.target === $("#modal")) close(); });
$("#prev").addEventListener("click", function(){ if(cur>0) open(cur-1); });
$("#next").addEventListener("click", function(){ if(cur < state.rows.length-1) open(cur+1); });
document.addEventListener("keydown", function(e){
  if($("#modal").hidden) return;
  if(e.key === "Escape") close();
  else if(e.key === "ArrowLeft") { if(cur>0) open(cur-1); }
  else if(e.key === "ArrowRight") { if(cur < state.rows.length-1) open(cur+1); }
});
$("#grid").addEventListener("click", function(e){
  var c = e.target.closest(".card");
  if(c) open(parseInt(c.getAttribute("data-i"), 10));
});
$("#copyBtn").addEventListener("click", function(){
  var r = state.rows[cur]; if(!r) return;
  var btn = this;
  function ok(){ btn.textContent = tx("copied","已复制","コピーしました"); setTimeout(function(){ btn.textContent = UI.copyPrompt; }, 1600); }
  function bad(){ btn.textContent = tx("copyFail","复制失败","コピー失敗"); setTimeout(function(){ btn.textContent = UI.copyPrompt; }, 1600); }
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(r.p||"").then(ok, bad);
  } else {
    var ta = document.createElement("textarea");
    ta.value = r.p||""; document.body.appendChild(ta); ta.select();
    try{ document.execCommand("copy"); ok(); }catch(err){ bad(); }
    document.body.removeChild(ta);
  }
});

/* —— 启动 —— */
buildMenus();
syncChips();
applyStatic();

/* 从落地页带 #cat=… / #ver=… 进来时直接定位到对应筛选 */
function readHash(){
  var h = (location.hash || "").replace(/^#/, "");
  if(!h) return;
  h.split("&").forEach(function(kv){
    var i = kv.indexOf("=");
    if(i < 0) return;
    var k = kv.slice(0, i), v = decodeURIComponent(kv.slice(i + 1));
    if(k === "cat") state.cat = v;
    else if(k === "ver") state.ver = v;
  });
}
readHash();
syncChips();

ensure().then(function(){
  var st = $("#stats");
  st.innerHTML = '<div><b>'+IDX.total.toLocaleString()+'</b><span>'+tx("statPrompt","提示词","プロンプト")+'</span></div>'
    + '<div><b>'+IDX.cats.length+'</b><span>'+tx("statCat","分类","カテゴリ")+'</span></div>'
    + '<div><b>'+IDX.vers.length+'</b><span>'+tx("statVer","版本","バージョン")+'</span></div>'
    + '<div><b>'+IDX.nsfw.toLocaleString()+'</b><span>'+tx("nsfwBadge","成人内容","成人向け")+'</span></div>';
  var f = $("#foot");
  f.innerHTML = UI.footer + ' · <a href="browse/">' + tx("filter","分类与版本","カテゴリとバージョン") + '</a>';
});
"""
    js = js.replace("__UI_ZH__", json.dumps(ui_zh, ensure_ascii=False))
    js = js.replace("__UI_JA__", json.dumps(ui_ja, ensure_ascii=False))
    js = js.replace("__PAGESIZE__", str(PAGE_SIZE))
    return js


def inject_seo_intro(html_path, rows, urls):
    """把静态介绍与 FAQ 注入页面（搜索引擎与 AI 需要不依赖 JS 的可读内容）。"""
    html = open(html_path, encoding="utf-8").read()
    site, facets = build_facets(rows)
    n = len(rows)
    m = n
    intro = landing_mod.static_intro(
        CONFIG["seoPages"]["introParas"](n, m),
        [("提示词", "%d 条" % n), ("分类", "%d 个" % len(set(r["category"] for r in rows))),
         ("语言", "中文 / 日本語"), ("来源", "PromptHero")],
        [(f"{s.slug}/", f"{s.label} · {len(s.items)}") for s in facets[:12]],
        CONFIG["seoPages"]["faq"],
        more_href="browse/", more_label="全部分类与版本")
    faq_ld = landing_mod.faq_ld_script(CONFIG["seoPages"]["faq"])
    css = landing_mod.SEO_INTRO_CSS
    html = html.replace('<section class="seo-intro" aria-label="关于本站"></section>', intro)
    html = html.replace("</head>", '<script type="application/ld+json">%s</script>\n</head>' %
                        landing_mod._ld({"@context": "https://schema.org", "@type": "FAQPage",
                                         "mainEntity": [{"@type": "Question", "name": q,
                                                         "acceptedAnswer": {"@type": "Answer", "text": a}}
                                                        for q, a in CONFIG["seoPages"]["faq"]]}))
    html = html.replace("</style>", css + "\n</style>")
    with open(html_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)


def write_404():
    with open(os.path.join(SITE, "404.html"), "w", encoding="utf-8") as f:
        f.write("""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>404 · 页面不存在</title>
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>
html,body{margin:0;height:100%}
body{background:#f7f6f3;color:#191b1f;font-family:system-ui,"PingFang SC","Microsoft YaHei",sans-serif;
  display:flex;align-items:center;justify-content:center;text-align:center}
.box{padding:24px}
h1{margin:0 0 10px;font-size:56px;font-weight:500;color:#c2410c}
p{margin:0 0 22px;color:#525b6a;font-size:14px;line-height:1.9}
a{display:inline-flex;align-items:center;height:42px;padding:0 24px;border-radius:999px;
  background:#191b1f;color:#fff;text-decoration:none;font-size:13.5px}
</style></head>
<body><div class="box">
<h1>404</h1>
<p>页面不存在，或链接已失效。<br>Page not found.</p>
<a href="/">返回首页</a>
</div></body></html>
""")


def copy_og_cover():
    """社交分享图：取第一张可用缩略图，拷成 og-cover.jpg（缩略图是 webp，浏览器能显示）。"""
    src = None
    for fn in ("thumbs", "mid"):
        d = os.path.join(SITE, fn)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".webp"):
                    src = os.path.join(d, f)
                    break
        if src:
            break
    dst = os.path.join(SITE, "og-cover.jpg")
    if src and os.path.exists(src):
        shutil.copyfile(src, dst)
        print("og-cover.jpg <- %s" % os.path.relpath(src, SITE))
    else:
        print("og-cover.jpg 跳过（没有可用缩略图）")


if __name__ == "__main__":
    main()
