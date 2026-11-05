# -*- coding: utf-8 -*-
"""构建 Midlibrary 风格库（MIDLIB-01）

页面逻辑在本文件内；文案、分类与 kind 名表在 config.py（**只读契约**）。

产出：
  index.html              单文件画廊（数据外置，页面本身约 40 KB）
  data/gallery.js         唯一数据文件：分类 / kind 索引 + 条目表
  data/landing.json       落地页清单
  browse/ cat/            静态落地页（16 个分类分面 + 索引页）
  robots.txt sitemap.xml 404.html og-cover.jpg

数据规模：10,142 条（5,504 个风格名 + 4,638 个 SREF 码），单文件 data/gallery.js
约 2.3 MB；页面只加载它，不内嵌任何全量数据（index.html 必须 < 450 KB）。

用法（一般由 tools/build.py 调度，环境变量 SITE_URL 写进 canonical/og/sitemap）：
  SITE_URL=https://photoai.life/midlibrary python build_gallery.py

manifest 路径可用 MIDLIB_MANIFEST 覆盖（默认 sites/midlibrary/manifest.json）。

纪律（AGENTS.md 规则 19 与本任务硬约束）：
  · 构建过程不探测本地图片是否存在 —— 产物只取决于 manifest；
  · 产物可复现：不写时间戳、不写随机数；
  · 只用标准库 + 仓库内 shared/ 模块；
  · Python 3.8 兼容（CI 用 3.8 构建）：无 3.9+ 语法。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)                                  # sites/midlibrary
ROOT = os.path.dirname(os.path.dirname(SITE))                  # 仓库根
sys.path.insert(0, HERE)                                      # config.py 在 scripts/ 下
sys.path.insert(0, os.path.join(ROOT, "shared"))

import landing as landing_mod                                   # noqa: E402
from image_policy import LOCAL_ONLY, FB_JS, tier_addr            # noqa: E402
from config import (CATEGORIES, CATEGORY_JA, CATEGORY_LABEL,     # noqa: E402
                    CATEGORY_ZH, CODE, CONFIG, FAQ, KINDS, KIND_JA,
                    KIND_ZH, ORIGIN, SOURCE, UI)

SITE_URL = os.environ.get("SITE_URL", "https://example.com/midlibrary").rstrip("/")
MANIFEST = os.environ.get("MIDLIB_MANIFEST", os.path.join(SITE, "manifest.json"))
PAGE_SIZE = 240          # 增量渲染：每批渲染多少条
SREF_KIND = "style_code"  # SREF 条目的 kind（config.KINDS 里的键）


# ── 取图策略 ──────────────────────────────────────────
def policy_entry():
    """sites.json 里本站的条目（含 imagePolicy）。

    清单里还没登记本站时按契约（thumb/mid 都是 local-only）兜底 ——
    两种情况下产出的地址完全一致：站内相对路径，没有上游回落地址。
    """
    try:
        from image_policy import site_entry
        return site_entry(CONFIG["site"])
    except Exception:
        return {"id": CONFIG["site"],
                "imagePolicy": {"thumb": LOCAL_ONLY, "mid": LOCAL_ONLY}}


SITE_CFG = policy_entry()


def _addr(tier, rec, fkey):
    """该档位的展示地址（见 shared/image_policy.py 的编码约定）。

    local-only：展示地址就是站内相对路径，不写上游地址（没有回落目标）。
    """
    path = rec.get(tier + "_path") or ""
    url = rec.get(tier + "_url") or ""
    display, fallback, keep_path = tier_addr(SITE_CFG, tier, path, url)
    out = {fkey: display}
    if fallback:
        out[fkey + "Url"] = fallback
    if keep_path and path:
        out[fkey + "Path"] = path
    return out


# ── manifest ─────────────────────────────────────────
def load_manifest():
    if not os.path.exists(MANIFEST):
        sys.exit("找不到 manifest.json（%s），先运行 python scripts/manifest.py" % MANIFEST)
    with open(MANIFEST, encoding="utf-8") as f:
        rows = json.load(f)
    if not rows:
        sys.exit("manifest 是空的：%s" % MANIFEST)
    return rows


def fmt(n):
    """千分位数字（10,142 这样）。"""
    return "{:,}".format(n)


def flags_of(r):
    """位掩码：1=站方精选 2=公有领域 4=已实测。"""
    return ((1 if r.get("isPick") else 0)
            | (2 if r.get("isPublicDomain") else 0)
            | (4 if r.get("testedMark") else 0))


def build_data(rows):
    """全站单一数据体：分类索引 + kind 索引 + 条目表。

    记录键名刻意取短（i/n/p/k/c/t/m/u/s/f）—— 一万条要压进 2 MB 上下。
    kind 与分类的显示名**不进每条记录**，页面按 id 到索引里查表。
    """
    cat_count = {}
    kind_count = {}
    items = []
    for r in rows:
        cat = r.get("category") or ""
        kind = r.get("kind") or ""
        cat_count[cat] = cat_count.get(cat, 0) + 1
        kind_count[kind] = kind_count.get(kind, 0) + 1
        rec = {
            "i": r.get("slug") or r.get("id") or "",
            "n": r.get("name") or "",
            "p": r.get("prompt") or "",
            "k": kind,
            "c": cat,
            **_addr("thumb", r, "t"),
            **_addr("mid", r, "m"),
            "u": r.get("sourceUrl") or "",
            "s": r.get("sref") or "",
            "f": flags_of(r),
        }
        items.append(rec)

    cats = []
    for slug, label, _n, zh, ja in CATEGORIES:
        cats.append({"k": slug, "l": label, "zh": zh, "ja": ja,
                     "c": cat_count.get(slug, 0)})
    # 清单里出现的、但契约没列的分类（上游改了分类也要显示得出来）
    for slug in sorted(cat_count):
        if slug in CATEGORY_ZH:
            continue
        cats.append({"k": slug, "l": slug, "zh": slug, "ja": slug,
                     "c": cat_count[slug]})

    kinds = []
    for kind, zh, ja in KINDS:
        kinds.append({"k": kind, "zh": zh, "ja": ja,
                      "c": kind_count.get(kind, 0)})
    for kind in sorted(kind_count):
        if kind in KIND_ZH:
            continue
        kinds.append({"k": kind, "zh": kind, "ja": kind, "c": kind_count[kind]})

    n_sref = kind_count.get(SREF_KIND, 0)
    data = {
        "total": len(items),
        "nStyle": len(items) - n_sref,
        "nSref": n_sref,
        "cats": cats,
        "kinds": kinds,
        "items": items,
    }
    return data


def write_data(data):
    """写出 data/gallery.js（唯一数据文件）。"""
    data_dir = os.path.join(SITE, "data")
    os.makedirs(data_dir, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(data_dir, "gallery.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("window.__GALLERY__=JSON.parse(%s);\n"
                % json.dumps(payload, ensure_ascii=False))
    return len(payload)


# ── 落地页 ───────────────────────────────────────────
def item_alt(r):
    """落地页图片的 alt：条目名。测试要求 ≥6 字符，过短时补上分类名。"""
    name = (r.get("name") or "").strip()
    alt = name
    if len(alt) < 6:
        alt = "%s · %s" % (name or "未命名", CATEGORY_ZH.get(r.get("category"), "Midlibrary"))
    if len(alt) > 120:
        alt = alt[:120] + "…"
    return alt


def item_caption(r):
    """卡片下的小字：提示词。"""
    cap = (r.get("prompt") or "").strip()
    if len(cap) > 90:
        cap = cap[:90] + "…"
    return cap


def build_facets(rows):
    """按 16 个分类分面。条目不足 shared/landing.MIN_ITEMS 的由 write_site 跳过。"""
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r.get("category") or "", []).append(r)

    facets = []
    for slug, label, _n, zh, ja in CATEGORIES:
        items = by_cat.get(slug, [])
        n = len(items)
        facets.append(landing_mod.Facet(
            slug="cat/" + slug,
            title="%s · Midjourney 风格与 SREF 码 · %d 条" % (zh, n),
            h1="%s（Midjourney 风格与 SREF 码）" % zh,
            description=("Midlibrary %s 分类收录 %d 条 Midjourney 风格条目与风格参考码，"
                         "每条附可复制的一行提示词与示例图，可按类型筛选，"
                         "灯箱内直接复制 --sref 码。" % (label, n)),
            intro=["这一页是 Midlibrary「%s（%s）」分类的静态索引，共 %d 条。"
                   "每条都附了示例图与一行可复制的提示词。" % (zh, label, n),
                   "风格名与 SREF 码由 Midlibrary 团队整理，样例图由他们用 Midjourney 生成；"
                   "经站方书面许可，本站以署名加回链的方式镜像，供个人学习与检索使用。"],
            items=[landing_mod.Item(thumb=r.get("thumb_path") or "",
                                    alt=item_alt(r),
                                    caption=item_caption(r))
                   for r in items],
            gallery_hash="cat=" + slug,
            facts=[("分类", zh), ("条目", "%d 条" % n), ("来源", "Midlibrary")],
            related=[("cat/" + s, CATEGORY_ZH.get(s, s), len(by_cat.get(s, [])))
                     for s, _l, _c, _zh, _ja in CATEGORIES if s != slug],
            group="按分类",
            label=zh))

    n_total = len(rows)
    site = landing_mod.Site(
        id=CONFIG["site"], root=SITE, site_url=SITE_URL,
        name=CONFIG["name"], tagline=CONFIG["tagline"],
        license_note=CONFIG["licenseNote"], author=CONFIG["author"],
        author_url=CONFIG["authorUrl"], source=SOURCE, faq=FAQ,
        accent=CONFIG["accent"],
        index_title=CONFIG["name"] + " · 全部分类",
        index_intro=("按 %d 个分类浏览 Midlibrary 的 Midjourney 风格名与风格参考码（SREF）："
                     "画家、插画师、摄影师、流派与艺术运动……每一类都附可复制的一行提示词与示例图。"
                     % len(CATEGORIES)))
    return site, facets


# ── 页面模板 ─────────────────────────────────────────
PAGE = r"""<!doctype html>
<html lang="zh-CN" data-theme="light" data-lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<meta name="keywords" content="Midjourney风格,SREF,风格参考码,Midlibrary,AI绘画提示词,AI art reference">
<meta name="author" content="__AUTHOR__">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="__SITE__/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="__OGSITE__">
<meta property="og:title" content="__OGTITLE__">
<meta property="og:description" content="__OGDESC__">
<meta property="og:url" content="__SITE__/">
<meta property="og:image" content="__SITE__/og-cover.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="zh_CN">
<meta property="og:locale:alternate" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TWTITLE__">
<meta name="twitter:description" content="__TWDESC__">
<meta name="twitter:image" content="__SITE__/og-cover.jpg">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<script type="application/ld+json">__SCHEMA__</script>
__FAQ_LD__
<script>
/* 首帧前套用已存偏好，避免刷新闪白 / 闪日文 */
(function(){
  try{
    var t=localStorage.getItem('__KEY__.theme'); if(t==='light'||t==='dark') document.documentElement.dataset.theme=t;
    var l=localStorage.getItem('__KEY__.lang');  if(l==='ja'||l==='zh')      document.documentElement.dataset.lang=l;
  }catch(e){}
})();
</script>
__FB_JS__
<style>
:root{
  --bg:#fafaf9;--bg2:#fff;--tx:#1c1917;--tx2:#57534e;--tx3:#a8a29e;
  --line:#e7e5e4;--ac:#b45309;--ac2:#d97706;--panel:#fff;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0c0a09;--bg2:#1c1917;--tx:#f5f5f4;--tx2:#a8a29e;--tx3:#78716c;
  --line:#292524;--ac:#f59e0b;--ac2:#fbbf24;--panel:#1c1917;
}}
html[data-theme=light]{--bg:#fafaf9;--bg2:#fff;--tx:#1c1917;--tx2:#57534e;--tx3:#a8a29e;--line:#e7e5e4;--ac:#b45309;--ac2:#d97706;--panel:#fff}
html[data-theme=dark]{--bg:#0c0a09;--bg2:#1c1917;--tx:#f5f5f4;--tx2:#a8a29e;--tx3:#78716c;--line:#292524;--ac:#f59e0b;--ac2:#fbbf24;--panel:#1c1917}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.7 system-ui,-apple-system,"Segoe UI","Hiragino Sans","Noto Sans SC","Microsoft YaHei",sans-serif}
a{color:inherit}
.wrap{max-width:1180px;margin:0 auto;padding:0 clamp(14px,3vw,28px)}
header.top{border-bottom:1px solid var(--line);background:var(--bg2);position:sticky;top:0;z-index:20}
header.top .wrap{display:flex;align-items:center;gap:10px;padding-top:12px;padding-bottom:12px;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:-.01em;margin-right:auto;display:flex;align-items:baseline;gap:8px}
.brand small{font-weight:500;color:var(--tx3);font-size:12px}
.btn{border:1px solid var(--line);background:var(--bg2);color:var(--tx2);border-radius:999px;
  padding:5px 12px;font-size:12.5px;cursor:pointer;font-family:inherit;line-height:1.5}
.btn:hover{border-color:var(--ac);color:var(--ac)}
.btn.on{background:var(--ac);border-color:var(--ac);color:#fff}
html[data-theme=dark] .btn.on{color:#1c1207}
.seg{display:inline-flex;gap:4px}
.hero{padding:26px 0 18px}
.eyebrow{font-size:11px;letter-spacing:.14em;color:var(--tx3);font-weight:600;margin:0 0 8px}
h1{font-size:clamp(21px,3.4vw,30px);margin:0 0 10px;letter-spacing:-.02em;line-height:1.25}
.sub{color:var(--tx2);margin:0;max-width:76ch;font-size:14px}
.stats{display:flex;gap:18px;flex-wrap:wrap;margin:16px 0 0;padding:0;list-style:none}
.stats li{font-size:12px;color:var(--tx3)}
.stats b{color:var(--tx);font-size:17px;font-weight:700;margin-right:5px}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px 0;border-bottom:1px solid var(--line)}
.toolbar input[type=search]{flex:1 1 220px;min-width:180px;border:1px solid var(--line);background:var(--bg2);
  color:var(--tx);border-radius:999px;padding:8px 14px;font:inherit;font-size:13.5px}
.toolbar input[type=search]:focus{outline:none;border-color:var(--ac)}
.countline{font-size:12.5px;color:var(--tx3);margin:10px 0 0}
.chips{display:flex;gap:6px;flex-wrap:wrap;padding:12px 0 0}
.chips button{border:1px solid var(--line);background:var(--bg2);color:var(--tx2);border-radius:999px;
  padding:4px 12px;font-size:12.5px;cursor:pointer;font-family:inherit;line-height:1.6}
.chips button:hover{border-color:var(--ac);color:var(--ac)}
.chips button.on{background:var(--ac);border-color:var(--ac);color:#fff}
html[data-theme=dark] .chips button.on{color:#1c1207}
.chips small{color:var(--tx3);margin-left:5px}
.chips button.on small{color:inherit;opacity:.85}
.grid{list-style:none;margin:18px 0 0;padding:0;display:grid;gap:14px;
  grid-template-columns:repeat(auto-fill,minmax(210px,1fr))}
.card{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--bg2);
  cursor:zoom-in;display:block;position:relative;transition:transform .12s ease;height:100%}
.card:hover{transform:translateY(-2px)}
.card .ph{position:relative;aspect-ratio:1/1;background:var(--line)}
.card .ph img{display:block;width:100%;height:100%;object-fit:cover}
.card .ph img.broken{opacity:.25}
.card .info{padding:8px 10px 10px}
.card .l1{display:flex;align-items:center;gap:6px}
.card .nm{font-size:13px;font-weight:600;color:var(--tx);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card .kd{font-size:10.5px;border:1px solid var(--line);border-radius:999px;padding:0 6px;color:var(--tx2);
  white-space:nowrap;margin-left:auto}
.card .fl{font-size:10px;color:var(--ac);white-space:nowrap}
.card .ct{font-size:11px;color:var(--tx3);margin-top:3px}
.card .pr{display:flex;align-items:center;gap:6px;margin-top:6px}
.card .tx{flex:1 1 auto;min-width:0;font-size:11.5px;color:var(--tx2);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card .cp{border:1px solid var(--line);background:transparent;color:var(--tx2);border-radius:999px;
  padding:1px 8px;font-size:11px;cursor:pointer;font-family:inherit;line-height:1.6;flex:0 0 auto}
.card .cp:hover{border-color:var(--ac);color:var(--ac)}
.card .sr{font-size:11px;color:var(--ac);margin-top:4px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
#more{display:block;margin:26px auto 0;border:1px solid var(--line);background:var(--bg2);color:var(--tx2);
  border-radius:999px;padding:9px 24px;font:inherit;font-size:13.5px;cursor:pointer}
#more[hidden]{display:none}
.empty{padding:60px 0;text-align:center;color:var(--tx3)}
.empty h2{color:var(--tx2);font-size:16px;margin:0 0 6px}
footer{border-top:1px solid var(--line);margin-top:44px;padding:22px 0 44px;color:var(--tx3);font-size:12.5px}
footer a{color:var(--tx2)}
.lb{position:fixed;inset:0;background:rgba(8,8,10,.94);display:none;z-index:100;
  grid-template-rows:auto 1fr auto;grid-template-columns:minmax(0,1fr);padding:14px}
.lb.on{display:grid}
.lb .bar{display:flex;gap:10px;align-items:center;color:#e8e8ea;font-size:13px;flex-wrap:wrap}
.lb .bar b{font-weight:600;margin-right:auto}
.lb .bar button{border:1px solid #3a3a3e;background:#1c1c20;color:#e8e8ea;border-radius:999px;
  padding:5px 12px;font:inherit;font-size:12.5px;cursor:pointer}
.lb .stage{display:flex;align-items:center;justify-content:center;min-height:0;min-width:0;
  position:relative;overflow:hidden}
.lb .stage img{max-width:100%;max-height:100%;object-fit:contain;transition:opacity .18s}
.lb .stage img.mid{position:absolute;inset:0;margin:auto}
.lb .foot{color:#a1a1aa;font-size:12px;text-align:center;padding-top:8px;min-width:0;
  display:flex;gap:14px;justify-content:center;flex-wrap:wrap}
.lb .foot code{background:#1c1c20;border:1px solid #2a2a2e;border-radius:6px;padding:2px 8px;
  max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* SREF 码单独配色，方便一眼认出、点一下就复制 */
.lb .foot #lbSref{color:#e8c98a;border-color:#4a4028;cursor:copy}
.lb .foot #lbSref:hover{background:#2a2418}
.lb .foot .note{width:100%;font-size:11px;color:#7c7c85}
html[data-lang=ja] .zh{display:none}
html[data-lang=zh] .ja{display:none}
__LANDING_CSS__
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <div class="brand"><span>Midlibrary</span><small>__SHORT__</small></div>
  <a class="btn" href="/">__HOME__</a>
  <div class="seg" role="group" aria-label="__THEMEA__">
    <button class="btn" id="themeLight" type="button" data-theme-set="light">☀ Light</button>
    <button class="btn" id="themeDark" type="button" data-theme-set="dark">☾ Dark</button>
  </div>
  <div class="seg" role="group" aria-label="__LANGA__">
    <button class="btn" id="langZh" type="button" data-lang-set="zh">中文</button>
    <button class="btn" id="langJa" type="button" data-lang-set="ja">日本語</button>
  </div>
</div></header>

<div class="wrap">
  <section class="hero">
    <p class="eyebrow">__EYEBROW__</p>
    <h1>__H1__</h1>
    <p class="sub">__LEAD__</p>
    <ul class="stats">
      <li><b>__N_TOTAL__</b><span class="zh">条目</span><span class="ja">項目</span></li>
      <li><b>__N_STYLE__</b><span class="zh">风格名</span><span class="ja">スタイル名</span></li>
      <li><b>__N_SREF__</b><span class="zh">SREF 码</span><span class="ja">SREF コード</span></li>
      <li><b>__N_CAT__</b><span class="zh">分类</span><span class="ja">カテゴリ</span></li>
    </ul>
  </section>

  <div class="toolbar">
    <input type="search" id="q" placeholder="__SEARCH__" aria-label="__SEARCH__">
    <button class="btn" id="clearBtn" type="button"><span class="zh">清除筛选</span><span class="ja">絞り込み解除</span></button>
  </div>
  <div class="chips" id="kindChips"></div>
  <div class="chips" id="catChips"></div>
  <p class="countline" id="count"></p>

  <ul class="grid" id="grid"></ul>
  <p class="empty" id="empty" hidden><h2>__EMPTYTITLE__</h2><div>__EMPTYHINT__</div></p>
  <button id="more" type="button" hidden>__LOADMORE__</button>
</div>

__SEO_INTRO__

<footer><div class="wrap">__FOOTER__</div></footer>

<div class="lb" id="lb" role="dialog" aria-modal="true" aria-label="图片查看">
  <div class="bar">
    <b id="lbTitle"></b>
    <button id="lbCopy" type="button">__COPYP__</button>
    <button id="lbCopySref" type="button">__COPIESREF__</button>
    <button id="lbOrigin" type="button">__OPENORIGIN__</button>
    <button id="lbClose" type="button"><span class="zh">关闭</span><span class="ja">閉じる</span></button>
  </div>
  <div class="stage">
    <img id="lbImg" alt="">
    <img id="lbMid" class="mid" alt="">
  </div>
  <div class="foot">
    <span id="lbMeta"></span>
    <code id="lbSref" hidden></code>
    <code id="lbPrompt"></code>
    <span class="note"><span class="zh">__NOTE_ZH__</span><span class="ja">__NOTE_JA__</span></span>
  </div>
</div>

<script src="data/gallery.js"></script>
<script>
const IDX = window.__GALLERY__;
/* 界面文案来自 config.UI（数据文件只放条目与索引，不塞文案） */
const T = __UI_ZH__, J = __UI_JA__;
const PAGE_SIZE = __PAGE_SIZE__;
const KEY = "__KEY__";

const $ = s => document.querySelector(s);
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

/* kind / 分类的显示名不进每条记录：按 id 到索引里查表 */
const KIND_LABEL = {};
(IDX.kinds || []).forEach(k => { KIND_LABEL[k.k] = k; });
const CAT_LABEL = {};
(IDX.cats || []).forEach(c => { CAT_LABEL[c.k] = c; });

const isJa = () => document.documentElement.dataset.lang === "ja";
function Txt(key, vars){
  const src = (isJa() ? J : T) || {};
  let t = src[key] || "";
  const v = vars || {};
  for (const k in v) t = t.replace(new RegExp("\\{" + k + "\\}", "g"), v[k]);
  return t.replace("%s", String(v.n == null ? "" : v.n));
}
function kindLabel(k){
  const o = KIND_LABEL[k];
  if (!o) return k || "-";
  return isJa() ? (o.ja || o.k) : (o.zh || o.k);
}
function catLabel(c){
  const o = CAT_LABEL[c];
  if (!o) return c || "-";
  return isJa() ? (o.ja || o.k) : (o.zh || o.k);
}

let state = { q:"", kind:null, cat:null, shown:0 };

/* ── 筛选 ─────────────────────────────────────── */
function filtered(){
  const q = state.q.trim().toLowerCase();
  return IDX.items.filter(it => {
    if (state.kind && it.k !== state.kind) return false;
    if (state.cat && it.c !== state.cat) return false;
    if (!q) return true;
    return (it.n || "").toLowerCase().indexOf(q) >= 0
        || (it.p || "").toLowerCase().indexOf(q) >= 0
        || (it.s || "").toLowerCase().indexOf(q) >= 0;
  });
}

/* ── 分面按钮（计数按当前另一个维度的筛选实时算）──── */
function renderChips(){
  const kindPool = [], catPool = [];
  for (let i = 0; i < IDX.items.length; i++){
    const it = IDX.items[i];
    if (!state.cat || it.c === state.cat) kindPool.push(it);
    if (!state.kind || it.k === state.kind) catPool.push(it);
  }
  const kc = {}, cc = {};
  for (let i = 0; i < kindPool.length; i++){ const k = kindPool[i].k; kc[k] = (kc[k] || 0) + 1; }
  for (let i = 0; i < catPool.length; i++){ const c = catPool[i].c; cc[c] = (cc[c] || 0) + 1; }

  let kh = '<button type="button" class="' + (state.kind === null ? "on" : "") + '" data-kind="">'
         + esc(Txt("allKinds")) + "<small>" + kindPool.length + "</small></button>";
  (IDX.kinds || []).forEach(k => {
    const n = kc[k.k] || 0;
    if (!n) return;
    kh += '<button type="button" class="' + (state.kind === k.k ? "on" : "") + '" data-kind="'
        + esc(k.k) + '">' + esc(kindLabel(k.k)) + "<small>" + n + "</small></button>";
  });
  $('#kindChips').innerHTML = kh;

  let ch = '<button type="button" class="' + (state.cat === null ? "on" : "") + '" data-cat="">'
         + esc(Txt("allCats")) + "<small>" + catPool.length + "</small></button>";
  (IDX.cats || []).forEach(c => {
    const n = cc[c.k] || 0;
    if (!n) return;
    ch += '<button type="button" class="' + (state.cat === c.k ? "on" : "") + '" data-cat="'
        + esc(c.k) + '">' + esc(catLabel(c.k)) + "<small>" + n + "</small></button>";
  });
  $('#catChips').innerHTML = ch;
}

/* ── 渲染 ─────────────────────────────────────── */
function card(it){
  let flags = "";
  if (it.f & 1) flags += '<span class="fl" title="' + esc(Txt("badgePick")) + '">★</span>';
  if (it.f & 2) flags += '<span class="fl" title="' + esc(Txt("badgePublic")) + '">PD</span>';
  if (it.f & 4) flags += '<span class="fl" title="' + esc(Txt("badgeTested")) + '">✓</span>';
  const sref = it.s ? '<div class="sr">--sref ' + esc(it.s) + "</div>" : "";
  return '<li><div class="card" tabindex="0" data-key="' + esc(it.i) + '">'
       + '<div class="ph"><img src="' + esc(it.t) + '" alt="' + esc(it.n || it.p || "Midlibrary") + '"'
       + ' loading="lazy" decoding="async"></div>'
       + '<div class="info">'
       + '<div class="l1"><span class="nm">' + esc(it.n || "") + "</span>"
       + flags
       + '<span class="kd">' + esc(kindLabel(it.k)) + "</span></div>"
       + '<div class="ct">' + esc(catLabel(it.c)) + "</div>"
       + '<div class="pr"><span class="tx">' + esc(it.p || "") + "</span>"
       + '<button class="cp" type="button" data-copy="' + esc(it.i) + '">'
       + esc(Txt("copy")) + "</button></div>"
       + sref
       + "</div></div></li>";
}

function render(){
  const list = filtered();
  const grid = $('#grid');
  const more = $('#more');
  $('#count').textContent = Txt("count", { n: list.length });
  if (!list.length){
    grid.innerHTML = "";
    $('#empty').hidden = false;
    more.hidden = true;
    return;
  }
  $('#empty').hidden = true;
  const slice = list.slice(state.shown, state.shown + PAGE_SIZE);
  if (!slice.length){ more.hidden = true; return; }
  let html = "";
  for (let i = 0; i < slice.length; i++) html += card(slice[i]);
  grid.insertAdjacentHTML("beforeend", html);
  state.shown += slice.length;
  more.hidden = state.shown >= list.length;
  more.textContent = Txt("loadMore") + " (" + Math.max(0, list.length - state.shown) + ")";
  grid.querySelectorAll("img").forEach(img => {
    img.addEventListener("error", () => { img.classList.add("broken"); });
  });
}

function refresh(){
  state.shown = 0;
  $('#grid').innerHTML = "";
  renderChips();
  render();
}

/* ── 灯箱 ─────────────────────────────────────── */
let lbKey = null, lbList = [];
function findItem(key){
  for (let i = 0; i < lbList.length; i++) if (lbList[i].i === key) return lbList[i];
  return null;
}
function openLightbox(key){
  lbList = filtered();
  const it = findItem(key);
  if (!it) return;
  lbKey = key;
  $('#lb').classList.add("on");
  document.body.style.overflow = "hidden";
  const img = $('#lbImg'), mid = $('#lbMid');
  mid.removeAttribute("src");
  mid.style.opacity = "0";
  img.src = it.t;
  img.alt = it.n || it.p || "";
  $('#lbTitle').textContent = it.n || it.i;
  $('#lbMeta').textContent = [kindLabel(it.k), catLabel(it.c)].join(" · ");
  const sref = $('#lbSref');
  if (it.s){
    sref.textContent = "--sref " + it.s;
    sref.hidden = false;
    $('#lbCopySref').hidden = false;
  } else {
    sref.textContent = "";
    sref.hidden = true;
    $('#lbCopySref').hidden = true;
  }
  $('#lbPrompt').textContent = it.p || "";
  $('#lbOrigin').onclick = () => { window.open(it.u, "_blank", "noopener"); };
  /* 先显示缩略图，中图到达后淡入 */
  const pre = new Image();
  pre.onload = () => {
    mid.src = it.m;
    requestAnimationFrame(() => { mid.style.opacity = "1"; });
  };
  pre.onerror = () => { mid.style.opacity = "0"; };
  pre.src = it.m;
}
function closeLightbox(){
  lbKey = null;
  $('#lb').classList.remove("on");
  document.body.style.overflow = "";
  $('#lbImg').removeAttribute("src");
  $('#lbMid').removeAttribute("src");
}
function step(d){
  const pos = lbList.findIndex(it => it.i === lbKey);
  if (pos < 0 || !lbList.length) return;
  openLightbox(lbList[(pos + d + lbList.length) % lbList.length].i);
}

/* ── 复制 ─────────────────────────────────────── */
function copyText(text, btn, label){
  if (!text) return;
  const done = () => {
    const old = btn.dataset.old || btn.textContent;
    btn.dataset.old = old;
    btn.textContent = Txt("copied");
    setTimeout(() => { btn.textContent = old; }, 1400);
  };
  const fail = () => { btn.textContent = label; };
  if (navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done, fail);
  } else {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); done(); } catch (e) { fail(); }
    document.body.removeChild(ta);
  }
}

/* ── 交互 ─────────────────────────────────────── */
$('#kindChips').addEventListener("click", e => {
  const b = e.target.closest("button[data-kind]");
  if (!b) return;
  state.kind = b.dataset.kind || null;
  refresh();
});
$('#catChips').addEventListener("click", e => {
  const b = e.target.closest("button[data-cat]");
  if (!b) return;
  state.cat = b.dataset.cat || null;
  refresh();
});
$('#grid').addEventListener("click", e => {
  const cp = e.target.closest(".cp");
  if (cp){
    e.stopPropagation();
    const it = IDX.items.find(x => x.i === cp.dataset.copy);
    if (it) copyText(it.p || "", cp, Txt("copy"));
    return;
  }
  const card = e.target.closest(".card");
  if (card) openLightbox(card.dataset.key);
});
$('#grid').addEventListener("keydown", e => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const card = e.target.closest(".card");
  if (!card) return;
  e.preventDefault();
  openLightbox(card.dataset.key);
});
$('#q').addEventListener("input", e => {
  state.q = e.target.value;
  refresh();
});
$('#clearBtn').addEventListener("click", () => {
  state.q = ""; state.kind = null; state.cat = null;
  $('#q').value = "";
  refresh();
});
$('#more').addEventListener("click", render);
$('#lbClose').addEventListener("click", closeLightbox);
$('#lb').addEventListener("click", e => { if (e.target.id === "lb") closeLightbox(); });
$('#lbCopy').addEventListener("click", function(){
  const it = findItem(lbKey);
  if (it) copyText(it.p || "", this, Txt("copyPrompt"));
});
$('#lbCopySref').addEventListener("click", function(){
  const it = findItem(lbKey);
  if (it) copyText(it.s || "", this, Txt("copySref"));
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeLightbox();
  else if (lbKey && e.key === "ArrowRight") step(1);
  else if (lbKey && e.key === "ArrowLeft") step(-1);
});

/* ── 主题与语言 ─────────────────────────────────── */
function setTheme(t){
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem(KEY + ".theme", t); } catch (e) {}
  $('#themeLight').classList.toggle("on", t === "light");
  $('#themeDark').classList.toggle("on", t === "dark");
}
function setLang(l){
  document.documentElement.dataset.lang = l;
  document.documentElement.lang = (l === "ja") ? "ja-JP" : "zh-CN";
  try { localStorage.setItem(KEY + ".lang", l); } catch (e) {}
  $('#langZh').classList.toggle("on", l === "zh");
  $('#langJa').classList.toggle("on", l === "ja");
  applyLang();
}
function applyLang(){
  $('#q').placeholder = Txt("search");
  $('#q').setAttribute("aria-label", Txt("search"));
  $('#lbCopy').textContent = Txt("copyPrompt");
  $('#lbCopySref').textContent = Txt("copySref");
  $('#lbOrigin').textContent = Txt("openOrigin");
  renderChips();
  refresh();
}
$('#themeLight').addEventListener("click", () => setTheme("light"));
$('#themeDark').addEventListener("click", () => setTheme("dark"));
$('#langZh').addEventListener("click", () => setLang("zh"));
$('#langJa').addEventListener("click", () => setLang("ja"));

/* ── 落地页带 #cat=… 进来时直接定位 ─────────────── */
function readHash(){
  const h = (location.hash || "").replace(/^#/, "");
  if (!h) return;
  h.split("&").forEach(kv => {
    const i = kv.indexOf("=");
    if (i < 0) return;
    const k = kv.slice(0, i), v = decodeURIComponent(kv.slice(i + 1));
    if (k === "cat") state.cat = v;
    if (k === "kind") state.kind = v;
  });
}
window.addEventListener("hashchange", () => { readHash(); refresh(); });

/* ── 启动 ─────────────────────────────────────── */
setTheme(document.documentElement.dataset.theme || "light");
setLang(document.documentElement.dataset.lang || "zh");
readHash();
refresh();

/* 滚动到底自动预取下一批 */
const io = new IntersectionObserver(entries => {
  entries.forEach(en => {
    if (en.isIntersecting && !$('#more').hidden) render();
  });
}, { rootMargin: "600px" });
io.observe($('#more'));
</script>
</body>
</html>
"""


def page_html(data, cfg, facets, intro_html):
    """把模板里的占位符换成实际内容。"""
    n_total = data["total"]
    n_style = data["nStyle"]
    n_sref = data["nSref"]
    n_cats = len([c for c in data["cats"] if c["c"]])

    title = "Midlibrary 风格库：%s 条 Midjourney 风格名与 SREF 码 · 原站镜像" % fmt(n_total)
    desc = ("Midlibrary（midlibrary.io）的中文索引：收录 %s 条 Midjourney 风格条目与风格参考码（SREF），"
            "每条附可复制的一行提示词与示例图，可按类型与分类筛选，灯箱内直接复制 --sref 码。%s"
            % (fmt(n_total), CONFIG["descTail"]))
    og_title = "Midlibrary 风格库 · %s 条风格名与 SREF 码" % fmt(n_total)
    og_desc = "Midjourney 风格名与风格参考码（SREF）的中文索引，每条附可复制的一行提示词与示例图。"

    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "name": CONFIG["name"], "url": SITE_URL + "/",
             "inLanguage": ["zh-CN", "ja"]},
            {"@type": "ImageGallery", "name": "Midlibrary %s" % CODE,
             "alternateName": "Midlibrary Midjourney styles and SREF codes",
             "url": SITE_URL + "/", "numberOfItems": n_total,
             "about": CONFIG["kind"], "isAccessibleForFree": True,
             "creator": {"@type": "Organization", "name": CONFIG["author"],
                         "url": CONFIG["authorUrl"]}},
        ],
    }

    zh = UI["zh"]
    ja = UI["ja"]
    footer = ('素材来源：<a href="%s" target="_blank" rel="noopener noreferrer">Midlibrary</a>（%s）。'
              "%s 素材作者：<a href=\"%s\" rel=\"noopener\">%s</a>。"
              '<a href="browse/">按分类浏览</a> · <a href="https://midlibrary.io/library" '
              'target="_blank" rel="noopener noreferrer">原站</a>'
              % (SOURCE, CODE, CONFIG["licenseNote"], CONFIG["authorUrl"], CONFIG["author"]))

    page = PAGE
    for key, val in (
        ("__TITLE__", title),
        ("__DESC__", desc),
        ("__AUTHOR__", CONFIG["author"]),
        ("__OGSITE__", "Midlibrary %s" % CODE),
        ("__OGTITLE__", og_title),
        ("__OGDESC__", og_desc),
        ("__TWTITLE__", og_title),
        ("__TWDESC__", og_desc),
        ("__SITE__", SITE_URL),
        ("__SCHEMA__", json.dumps(schema, ensure_ascii=False, separators=(",", ":"))),
        ("__FAQ_LD__", landing_mod.faq_ld_script(FAQ)),
        ("__FB_JS__", FB_JS),
        ("__LANDING_CSS__", landing_mod.SEO_INTRO_CSS),
        ("__PAGE_SIZE__", str(PAGE_SIZE)),
        ("__UI_ZH__", json.dumps(UI["zh"], ensure_ascii=False, separators=(",", ":"))),
        ("__UI_JA__", json.dumps(UI["ja"], ensure_ascii=False, separators=(",", ":"))),
        ("__KEY__", cfg["storageKey"]),
        ("__SHORT__", CONFIG["short"]),
        ("__HOME__", "参考素材库"),
        ("__THEMEA__", "主题"),
        ("__LANGA__", "语言"),
        ("__EYEBROW__", zh["eyebrow"]),
        ("__H1__", "Midlibrary 风格库：Midjourney 风格名与 SREF 码索引"),
        ("__LEAD__", zh["lead"]),
        ("__N_TOTAL__", fmt(n_total)),
        ("__N_STYLE__", fmt(n_style)),
        ("__N_SREF__", fmt(n_sref)),
        ("__N_CAT__", str(n_cats)),
        ("__SEARCH__", zh["search"]),
        ("__EMPTYTITLE__", zh["emptyTitle"]),
        ("__EMPTYHINT__", zh["searchEmpty"]),
        ("__LOADMORE__", zh["loadMore"]),
        ("__COPYP__", zh["copyPrompt"]),
        ("__COPIESREF__", zh["copySref"]),
        ("__OPENORIGIN__", zh["openOrigin"]),
        ("__NOTE_ZH__", zh["noImageNote"]),
        ("__NOTE_JA__", ja["noImageNote"]),
        ("__SEO_INTRO__", intro_html),
        ("__FOOTER__", footer),
    ):
        page = page.replace(key, val)
    return page


# ── 介绍卡片 ───────────────────────────────────────
def intro_html(data, facets):
    """主画廊页底部的「关于本站」卡片（不依赖 JS，搜索引擎与 AI 直接可读）。"""
    n_total = data["total"]
    n_style = data["nStyle"]
    n_sref = data["nSref"]
    n_cats = len([c for c in data["cats"] if c["c"]])
    facts = [("条目数", "%s 条" % fmt(n_total)),
             ("风格名", fmt(n_style)),
             ("风格参考码", fmt(n_sref)),
             ("分类", str(n_cats))]
    # 只链到真正会生成的落地页（不足 MIN_ITEMS 的分面没有页面，链过去会 404）
    keep = [f for f in facets if len(f.items) >= landing_mod.MIN_ITEMS]
    links = [("%s/" % f.slug, "%s · %d" % (f.label, len(f.items))) for f in keep]
    return landing_mod.static_intro(
        CONFIG["seoPages"]["introParas"](n_total, n_total),
        facts, links, FAQ,
        more_href="browse/" if keep else "",
        more_label="全部分类")


# ── 其它产物 ───────────────────────────────────────
def write_404():
    body = ("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>404 · Midlibrary 风格库</title>"
            "<link rel=\"icon\" href=\"/favicon.ico\" sizes=\"48x48\">"
            "<link rel=\"icon\" href=\"/favicon.svg\" type=\"image/svg+xml\">"
            "<link rel=\"apple-touch-icon\" href=\"/apple-touch-icon.png\">"
            "<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;"
            "font:15px/1.7 system-ui,-apple-system,\"Noto Sans SC\",sans-serif;"
            "background:#fafaf9;color:#1c1917}main{text-align:center;padding:24px}"
            "h1{font-size:56px;margin:0 0 8px;letter-spacing:-.03em}"
            "p{color:#57534e;margin:0 0 18px}a{color:#b45309;text-decoration:none;font-weight:600}"
            "@media(prefers-color-scheme:dark){body{background:#0c0a09;color:#f5f5f4}p{color:#a8a29e}"
            "a{color:#f59e0b}}</style></head><body><main><h1>404</h1>"
            "<p>这个页面不存在。</p><a href=\"./\">← 回到 Midlibrary 风格库</a></main></body></html>")
    with open(os.path.join(SITE, "404.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(body)


def write_robots():
    with open(os.path.join(SITE, "robots.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)


def make_og_cover(rows):
    """社交分享图：用本站第一张缩略图生成 1200×630。

    · 已经有 og-cover.jpg 就不动它 —— 产物要可复现，也免得重新压缩带来字节差异；
    · 没有 Pillow 就跳过（本地环境不装包，CI 才装）；
    · 本地没有图（图片不进仓库）就跳过，同样不崩。
    """
    dst = os.path.join(SITE, "og-cover.jpg")
    if os.path.exists(dst):
        return "已有，跳过"
    try:
        from PIL import Image
    except ImportError:
        return "没有 Pillow，跳过"
    for r in rows:
        rel = r.get("thumb_path") or ""
        if not rel:
            continue
        src = os.path.join(SITE, rel.replace("/", os.sep))
        if not os.path.exists(src):
            continue
        try:
            with Image.open(src) as im:
                if im.mode != "RGB":
                    im = im.convert("RGB")
                w, h = im.size
                tw, th = 1200, 630
                scale = max(tw / w, th / h)
                nw, nh = int(w * scale + 1), int(h * scale + 1)
                im = im.resize((nw, nh), Image.LANCZOS)
                left, top = (nw - tw) // 2, (nh - th) // 2
                im.crop((left, top, left + tw, top + th)).save(dst, "JPEG", quality=88)
            return "已生成（取自 %s）" % rel
        except Exception as e:                      # 读不出来的图就跳过，不中断构建
            print("og-cover.jpg 生成失败（%s）：%s" % (rel, e))
            return "生成失败，跳过"
    return "本地没有缩略图，跳过"


def main():
    rows = load_manifest()
    print("manifest: %d 条（%s）" % (len(rows), MANIFEST))

    data = build_data(rows)
    payload_len = write_data(data)
    print("数据文件 gallery.js：%d 条 · 分类 %d · kind %d · 约 %.1f MB"
          % (data["total"], len(data["cats"]), len(data["kinds"]), payload_len / 1048576.0))

    site, facets = build_facets(rows)
    page = page_html(data, CONFIG, facets, intro_html(data, facets))
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    urls = landing_mod.write_site(site, facets)
    landing_mod.sitemap(SITE_URL, urls, os.path.join(SITE, "sitemap.xml"))

    write_404()
    write_robots()
    print("og-cover.jpg：%s" % make_og_cover(rows))

    size = os.path.getsize(os.path.join(SITE, "index.html"))
    print("index.html %.1f KB（上限 450 KB）" % (size / 1024.0))
    print("落地页 %d 个（16 个分类分面 + 索引页）" % len(urls))


if __name__ == "__main__":
    main()
