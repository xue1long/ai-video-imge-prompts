# -*- coding: utf-8 -*-
"""构建 Midjourney 探索榜（MJ-EXPLORE-01）

页面逻辑在本文件内；文案与分面名表在 config.py。

产出：
  index.html              单文件画廊（数据内嵌，800 张图约 200 KB）
  data/landing.json       落地页清单
  browse/ aspect/         静态落地页
  robots.txt sitemap.xml 404.html og-cover.jpg

数据量说明：800 张图、每条 ~160 字节的精简记录，内嵌后页面约 200 KB，
在 450 KB 上限内，因此不分片（分片是 prompthero-midjourney 那种万级数据的做法）。

用法（一般由 tools/build.py 调度，环境变量 SITE_URL 写进 canonical/og/sitemap）：
  SITE_URL=https://photoai.life/midjourney-explore python build_gallery.py
"""
import html
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
from config import ASPECT_ZH, CONFIG, ORIGIN, SOURCE, UI        # noqa: E402
from image_policy import site_entry, tier_addr                  # noqa: E402

SITE_URL = os.environ.get("SITE_URL",
                          "https://example.com/midjourney-explore").rstrip("/")
PAGE_SIZE = 120          # 增量渲染：每批渲染多少张
SITE_CFG = site_entry("midjourney-explore")


def load_manifest():
    p = os.path.join(SITE, "manifest.json")
    if not os.path.exists(p):
        sys.exit("找不到 manifest.json，先运行 python scripts/manifest.py")
    return json.load(open(p, encoding="utf-8"))


def assert_manifest_integrity(rows, site=None, baseline=None):
    """采集静默失败会让站点悄悄少数据 —— 构建期硬失败，别等上线后才发现。

    检查三件事：
      1. manifest 非空；
      2. 每个 data/daily/<日期>/jobs.json 非空，且其行都进了 manifest；
      3. manifest 行数不比上次少（防止历史批次被覆盖）。
    """
    site = site or SITE
    baseline = baseline or os.path.join(site, "data", ".manifest_baseline")
    ddir = os.path.join(site, "data", "daily")
    # daily 的 jobs.json 存的是「作业」，其 id 对应 manifest 的 jobId（作业级）
    job_ids = {r["jobId"] for r in rows if r.get("jobId")}
    problems = []
    if not rows:
        problems.append("manifest 为空")

    if os.path.isdir(ddir):
        for name in sorted(os.listdir(ddir)):
            p = os.path.join(ddir, name, "jobs.json")
            if not os.path.isfile(p):
                continue
            with open(p, encoding="utf-8") as f:
                batch = json.load(f)
            if not batch:
                problems.append("%s 批次为空（采集失败？）" % name)
                continue
            miss = sum(1 for r in batch if r.get("id") not in job_ids)
            if miss:
                problems.append("%s 有 %d 条作业未进 manifest" % (name, miss))

    prev = 0
    if os.path.exists(baseline):
        try:
            with open(baseline, encoding="utf-8") as f:
                prev = int(f.read().strip() or 0)
        except ValueError:
            prev = 0
    if len(rows) < prev:
        problems.append("manifest 从 %d 行缩到 %d 行（历史可能被覆盖）" % (prev, len(rows)))

    if problems:
        sys.exit("数据完整性检查失败：\n  - " + "\n  - ".join(problems))

    with open(baseline, "w", encoding="utf-8", newline="\n") as f:
        f.write(str(len(rows)))
    return len(rows)


def aspect_slug(aspect):
    """宽高比 → URL 安全的分片键与目录名。"""
    return (aspect or "other").replace(":", "-").lower()


def build_data(rows, cfg):
    """全站单一数据体：作业表 + 条目 + 分面值域。

    整改后站点只用一份 data/gallery.js，不再按采集日切分片：当前量级
    （千条级）单文件完全够用；按日规模浏览由检索端 WebUI 承担，
    静态站只做「近期预览」。批次降为条目上的 b 字段，供前端筛选。
    """
    jobs = {}
    job_index = {}
    job_list = []
    items = []
    for r in rows:
        jid = r["jobId"]
        if jid not in jobs:
            jobs[jid] = {"p": r["prompt"], "u": r["username"], "o": r["sourceUrl"],
                         "v": r["version"] or "", "s": r.get("sref") or ""}
            job_index[jid] = len(job_list)
            job_list.append(jid)
        items.append({
            "i": r["id"],
            "j": job_index[jid],
            "b": r.get("batch") or "-",
            # 取图策略要求的编码（见 shared/image_policy.py 的约定）：
            #   <字段>     展示地址（直连上游时是上游 URL，否则是站内相对路径）
            #   <字段>Url  上游地址，仅本地优先时写出，作为加载失败的回落目标
            #   <字段>Path 站内相对路径，仅直连上游时写出，供按路径推导的规则使用
            **_addr(SITE_CFG, "thumb", r, "t"),
            **_addr(SITE_CFG, "mid", r, "m"),
            **_addr(SITE_CFG, "full", r, "g"),
            "a": r["aspect"] or "-",
            "w": r["width"],
            "h": r["height"],
            "n": r["enqueueTime"],
        })

    counts = {}
    batch_counts = {}
    batch_jobs = {}
    for r in rows:
        a = r["aspect"] or "-"
        counts[a] = counts.get(a, 0) + 1
        b = r.get("batch") or "-"
        batch_counts[b] = batch_counts.get(b, 0) + 1
        batch_jobs.setdefault(b, set()).add(r["jobId"])

    return {
        "aspects": [{"k": aspect_slug(k), "n": ASPECT_ZH.get(k, k), "c": v, "r": k}
                    for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))],
        # 批次（采集日）：新的在前。c = 该批次图片数，j = 该批次作业数
        "batches": [{"k": b, "n": (b[5:] if len(b) > 5 else b), "c": batch_counts[b],
                     "j": len(batch_jobs[b])}
                    for b in sorted(batch_counts, reverse=True)],
        "total": len(rows),
        "nJobs": len(job_list),
        "jobs": [jobs[j] for j in job_list],
        "items": items,
        "ui": cfg["ui"],
        "desc": cfg["desc"],
    }


def _addr(site, tier, rec, fkey):
    """该档位的展示地址与伴随字段（见 shared/image_policy.py 的编码约定）。

    online 档（如本站的 full）：地址就是上游 URL，本地没有副本 —— 此时
    **不写 <字段>Path**：那个路径指向不存在的文件，留着只会误导下游
    （页面按路径推导图片时会算出必然 404 的地址）。
    """
    path = rec.get(tier + "_path") or ""
    url = rec.get(tier + "_url") or ""
    display, fallback, keep_path = tier_addr(site, tier, path, url)
    out = {fkey: display}
    if fallback:
        out[fkey + "Url"] = fallback
    if keep_path and path:
        out[fkey + "Path"] = path
    return out


def write_data(data):
    """写出 data/gallery.js（唯一数据文件），并清掉旧的多分片残留。"""
    data_dir = os.path.join(SITE, "data")
    os.makedirs(data_dir, exist_ok=True)
    for fn in os.listdir(data_dir):
        if fn.startswith("gallery_") and fn.endswith(".js"):
            os.remove(os.path.join(data_dir, fn))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(data_dir, "gallery.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write("window.__GALLERY__=JSON.parse(%s);\n"
                % json.dumps(payload, ensure_ascii=False))


def esc(s):
    return html.escape(str(s), quote=True)


def alt_of(r):
    """落地页图片的 alt。要求 ≥6 字符（测试硬性检查），且要能描述画面。

    上游提示词最短的只有 1 个字符（"1"、"cat"），直接拿来做 alt 会太短；
    太短时补上宽高比与作者，保证可读且仍然具体。
    """
    text = (r["prompt"] or "").strip()
    if len(text) < 6:
        text = "%s · Midjourney 探索榜 · %s" % (text or "无标题", r["username"])
    if len(text) > 90:
        text = text[:90] + "…"
    return text


def build_facets(rows, cfg):
    """按宽高比分面。分面不足 6 张的不单独成页（landing.write_site 会过滤）。"""
    sp = cfg["seoPages"]
    by_aspect = {}
    for r in rows:
        by_aspect.setdefault(r["aspect"] or "-", []).append(r)

    facets = []
    for aspect, items in by_aspect.items():
        label = ASPECT_ZH.get(aspect, aspect)
        facets.append(landing_mod.Facet(
            slug="aspect/%s" % aspect.replace(":", "-"),
            title=f"{label}的 Midjourney 探索榜成图 · {len(items)} 张",
            h1=f"{label} · Midjourney 探索榜",
            description=(f"Midjourney 官网 Explore 榜里画面宽高比为 {aspect}（{label}）的 {len(items)} 张社区成图，"
                         f"每条附原始英文提示词，可直接复制使用。"),
            intro=[f"这一页收录 Midjourney 官网 Explore 热门榜里宽高比为 {aspect}（{label}）的 {len(items)} 张成图。",
                   "提示词保持英文原样，灯箱内可直接复制；图片来自社区作者，版权归各原作者。"],
            items=[landing_mod.Item(
                thumb=r["thumb_path"],
                alt=alt_of(r),
                caption=r["username"],
                w=r["width"], h=r["height"]) for r in items],
            gallery_hash="asp=" + aspect.replace(":", "-"),
            facts=[("宽高比", aspect), ("成图数", "%d 张" % len(items)),
                   ("模型版本", items[0]["version"] or "-")],
            related=[("aspect/%s" % a.replace(":", "-"),
                      ASPECT_ZH.get(a, a), len(v))
                     for a, v in sorted(by_aspect.items(), key=lambda kv: -len(kv[1]))
                     if a != aspect],
            group="按宽高比",
            label=label))

    site = landing_mod.Site(
        id=sp["id"], root=SITE, site_url=SITE_URL, name=sp["name"],
        tagline=sp["tagline"], license_note=sp["licenseNote"],
        author=sp["author"], author_url=sp["authorUrl"], source=SOURCE,
        faq=sp["faq"], accent=sp["accent"],
        index_title=sp["name"] + " · 全部宽高比",
        index_intro=sp["introParas"](len({r["jobId"] for r in rows}), len(rows))[0])
    return site, facets


def page_template():
    return r"""<!doctype html>
<html lang="zh-CN" data-theme="light" data-lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<meta name="keywords" content="Midjourney参考,AI绘画参考,探索榜,Midjourney提示词,AI art reference">
<meta name="author" content="Midjourney 社区">
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
/* 首帧前套用已存偏好，避免闪白/闪日文 */
(function(){
  try{
    var t=localStorage.getItem('mje.theme'); if(t==='light'||t==='dark') document.documentElement.dataset.theme=t;
    var l=localStorage.getItem('mje.lang');  if(l==='ja'||l==='zh')      document.documentElement.dataset.lang=l;
  }catch(e){}
})();
</script>
<style>
:root{
  --bg:#fafaf9;--bg2:#fff;--tx:#1c1917;--tx2:#57534e;--tx3:#a8a29e;
  --line:#e7e5e4;--ac:#0f766e;--ac2:#14b8a6;--panel:#fff;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0c0a09;--bg2:#1c1917;--tx:#f5f5f4;--tx2:#a8a29e;--tx3:#78716c;
  --line:#292524;--ac:#2dd4bf;--ac2:#5eead4;--panel:#1c1917;
}}
html[data-theme=light]{--bg:#fafaf9;--bg2:#fff;--tx:#1c1917;--tx2:#57534e;--tx3:#a8a29e;--line:#e7e5e4;--ac:#0f766e;--ac2:#14b8a6;--panel:#fff}
html[data-theme=dark]{--bg:#0c0a09;--bg2:#1c1917;--tx:#f5f5f4;--tx2:#a8a29e;--tx3:#78716c;--line:#292524;--ac:#2dd4bf;--ac2:#5eead4;--panel:#1c1917}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.7 system-ui,-apple-system,"Segoe UI","Hiragino Sans","Noto Sans SC","Microsoft YaHei",sans-serif}
a{color:inherit}
.wrap{max-width:1180px;margin:0 auto;padding:0 clamp(14px,3vw,28px)}
header.top{border-bottom:1px solid var(--line);background:var(--bg2);position:sticky;top:0;z-index:20}
header.top .wrap{display:flex;align-items:center;gap:12px;padding-top:12px;padding-bottom:12px;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:-.01em;margin-right:auto;display:flex;align-items:baseline;gap:8px}
.brand small{font-weight:500;color:var(--tx3);font-size:12px}
.btn{border:1px solid var(--line);background:var(--bg2);color:var(--tx2);border-radius:999px;
  padding:5px 12px;font-size:12.5px;cursor:pointer;font-family:inherit;line-height:1.5}
.btn:hover{border-color:var(--ac);color:var(--ac)}
.btn.on{background:var(--ac);border-color:var(--ac);color:#fff}
html[data-theme=dark] .btn.on{color:#06201d}
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
.toolbar select{border:1px solid var(--line);background:var(--bg2);color:var(--tx);border-radius:999px;
  padding:8px 12px;font:inherit;font-size:13px}
.chips{display:flex;gap:6px;flex-wrap:wrap;padding:12px 0 0}
.chips a,.chips button{border:1px solid var(--line);background:var(--bg2);color:var(--tx2);border-radius:999px;
  padding:4px 12px;font-size:12.5px;cursor:pointer;text-decoration:none;font-family:inherit;line-height:1.6}
.chips a:hover,.chips button:hover{border-color:var(--ac);color:var(--ac)}
.chips button.on{background:var(--ac);border-color:var(--ac);color:#fff}
html[data-theme=dark] .chips button.on{color:#06201d}
.chips small{color:var(--tx3);margin-left:5px}
.grid{list-style:none;margin:20px 0 0;padding:0;display:grid;gap:14px;
  grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}
.grid li{position:relative}
.card{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:var(--bg2);cursor:zoom-in;
  display:block;position:relative;transition:transform .12s ease}
.card:hover{transform:translateY(-2px)}
.card img{display:block;width:100%;height:auto;aspect-ratio:var(--ar,1/1);object-fit:cover;background:var(--line)}
.card .cap{padding:7px 9px;font-size:11.5px;color:var(--tx3);line-height:1.45;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card .ar{position:absolute;left:7px;top:7px;background:rgba(0,0,0,.55);color:#fff;border-radius:999px;
  padding:1px 7px;font-size:10.5px;letter-spacing:.02em}
#more{display:block;margin:30px auto 0;border:1px solid var(--line);background:var(--bg2);color:var(--tx2);
  border-radius:999px;padding:9px 24px;font:inherit;font-size:13.5px;cursor:pointer}
#more[hidden]{display:none}
.empty{padding:60px 0;text-align:center;color:var(--tx3)}
.empty h2{color:var(--tx2);font-size:16px;margin:0 0 6px}
footer{border-top:1px solid var(--line);margin-top:44px;padding:22px 0 44px;color:var(--tx3);font-size:12.5px}
footer a{color:var(--tx2)}
.lb{position:fixed;inset:0;background:rgba(8,8,10,.94);display:none;z-index:100;
  grid-template-rows:auto 1fr auto;grid-template-columns:minmax(0,1fr);padding:14px}
.lb.on{display:grid}
.lb .bar{display:flex;gap:10px;align-items:center;color:#e8e8ea;font-size:13px}
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
/* p 值（风格参考码）：单独配色，点击即复制，方便粘回 Midjourney 用 */
.lb .foot #lbSref{color:#e8c98a;border-color:#4a4028;cursor:copy}
.lb .foot #lbSref:hover{background:#2a2418}
html[lang=ja] .zh{display:none}
html[lang=zh] .ja{display:none}
__LANDING_CSS__
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <div class="brand"><span>__BRAND1__</span><small>__BRAND2__</small></div>
  <a class="btn" href="/">__HOME__</a>
  <button class="btn" id="themeBtn" type="button" aria-label="__THEMEA__">__THEMEL__</button>
  <button class="btn" id="langBtn" type="button" aria-label="__LANGA__">__LANGJA__</button>
</div></header>

<div class="wrap">
  <section class="hero">
    <p class="eyebrow">__EYEBROW__</p>
    <h1>__H1__</h1>
    <p class="sub">__SUB1__</p>
    <p class="sub">__SUB2__</p>
    <ul class="stats">
      <li><b>__N_IMG__</b><span class="zh">成图</span><span class="ja">画像</span></li>
      <li><b>__N_JOB__</b><span class="zh">作业</span><span class="ja">作品</span></li>
      <li><b>__N_AUTHOR__</b><span class="zh">作者</span><span class="ja">作者</span></li>
      <li><b>__N_ASP__</b><span class="zh">宽高比</span><span class="ja">アスペクト</span></li>
    </ul>
  </section>

  <div class="toolbar">
    <input type="search" id="q" placeholder="__SEARCH__" aria-label="__SEARCH__">
    <select id="sortSel" aria-label="__SORTLABEL__">
      <option value="hot">__SORTHOT__</option>
      <option value="new">__SORTNEW__</option>
      <option value="asp">__SORTASP__</option>
    </select>
    <button class="btn" id="clearBtn" type="button">__CLEAR__</button>
  </div>
  <div class="chips" id="batchChips"></div>
  <div class="chips" id="aspChips"></div>

  <ul class="grid" id="grid"></ul>
  <p class="empty" id="empty" hidden><h2>__EMPTYTITLE__</h2><div>__EMPTYDESC__</div></p>
  <button id="more" type="button" hidden>__MORE__</button>
</div>

<footer><div class="wrap">__FOOTER__</div></footer>

<div class="lb" id="lb" role="dialog" aria-modal="true" aria-label="图片查看">
  <div class="bar">
    <b id="lbTitle"></b>
    <button id="lbCopy" type="button">__COPYP__</button>
    <button id="lbDl" type="button">__DLFULL__</button>
    <button id="lbOrigin" type="button">__OPENORIGIN__</button>
    <button id="lbClose" type="button">__CLOSE__</button>
  </div>
  <div class="stage">
    <img id="lbImg" alt="">
    <img id="lbMid" class="mid" alt="">
  </div>
  <div class="foot">
    <span id="lbMeta"></span>
    <code id="lbSref" hidden></code>
    <code id="lbPrompt"></code>
  </div>
</div>

<script src="data/gallery.js"></script>
<script>
const IDX = window.__GALLERY__;
/* 分面键是 slug（文件名安全，如 2-3），分片条目里存的是原始宽高比（如 2:3）。
   两者不在一个空间，直接比较永远不相等 —— 点任意分面都会得到空网格。
   索引里 aspects[].r 就是原始值，这里建 slug → 原始值 的映射供过滤时还原。 */
const ASP_RAW = {};
IDX.aspects.forEach(a => { ASP_RAW[a.k] = a.r; });
const T = IDX.ui.zh, J = IDX.ui.ja;
const PAGE_SIZE = __PAGE_SIZE__;

const $ = s => document.querySelector(s);
/* 数据只有一份（IDX.items / IDX.jobs）：批次与宽高比都只是前端筛选条件。
   规模浏览交给检索端 WebUI，静态站只做近期预览，所以不再按批次切分片。 */
let state = { q: "", asp: null, batch: null, sort: "hot", shown: 0 };

function Txt(k, vars){
  var t = (document.documentElement.dataset.lang === "ja" ? J : T)[k] || "";
  for (var key in (vars || {})) t = t.replace(new RegExp("\\{" + key + "\\}", "g"), vars[key]);
  return t;
}
function esc(s){ return String(s).replace(/[&<>"']/g, function(c){
  return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]; }); }

/* 作业表随数据一起来：条目里的 j 是全站作业下标。 */
function jobOf(it){
  return IDX.jobs[it.j] || {};
}

/* ── 筛选 ─────────────────────────────────────── */
function filtered(){
  var q = state.q.trim().toLowerCase();
  var out = IDX.items.filter(function(it){
    var job = jobOf(it);
    if (state.batch && it.b !== state.batch) return false;
    if (state.asp && it.a !== ASP_RAW[state.asp]) return false;
    if (!q) return true;
    return (job.p || "").toLowerCase().indexOf(q) >= 0
        || (job.u || "").toLowerCase().indexOf(q) >= 0;
  });
  if (state.sort === "asp") out.sort(function(a,b){ return (a.a||"").localeCompare(b.a||"") || (a.n - b.n); });
  else if (state.sort === "new") out.sort(function(a,b){ return b.n - a.n; });
  else out.sort(function(a,b){ return a.n - b.n; });
  return out;
}
function renderChips(){
  /* 宽高比计数按**当前批次内的条目**实时算 —— 索引里是累计数，
     切到某一批后对不上（页面写 1600 张、实际只出 800 张那种误导）。 */
  var pool = IDX.items.filter(function(it){ return !state.batch || it.b === state.batch; });
  var aspCount = {};
  for (var i = 0; i < pool.length; i++){
    var k = pool[i].a;
    if (k) aspCount[k] = (aspCount[k] || 0) + 1;
  }
  var el = $("#aspChips");
  var html = '<button type="button" class="' + (state.asp === null ? "on" : "") + '" data-asp="">'
           + Txt("aspAll") + "<small>" + pool.length + "</small></button>";
  IDX.aspects.forEach(function(a){
    var c = aspCount[ASP_RAW[a.k]] || 0;
    if (!c) return;
    html += '<button type="button" class="' + (state.asp === a.k ? "on" : "") + '" data-asp="'
         + esc(a.k) + '">' + esc(a.n) + "<small>" + c + "</small></button>";
  });
  el.innerHTML = html;
  el.querySelectorAll("button").forEach(function(b){
    b.onclick = function(){
      state.asp = b.dataset.asp || null;
      resetGrid();
    };
  });

  /* 采集日（批次）：普通筛选条件，不再触发分片加载 */
  var bl = $("#batchChips");
  var bh = '<button type="button" class="' + (state.batch === null ? "on" : "") + '" data-batch="">'
         + Txt("batchAll") + "<small>" + IDX.total + "</small></button>";
  IDX.batches.forEach(function(b){
    bh += '<button type="button" class="' + (state.batch === b.k ? "on" : "") + '" data-batch="'
        + esc(b.k) + '">' + esc(b.n) + "<small>" + b.c + "</small></button>";
  });
  bl.innerHTML = bh;
  bl.querySelectorAll("button").forEach(function(b){
    b.onclick = function(){
      state.batch = b.dataset.batch || null;
      /* 换批次后原来的宽高比可能已无对应项，一并复位，避免空网格 */
      state.asp = null;
      resetGrid();
    };
  });
}

/* 筛选条件变化后的统一复位：重画 chips + 清网格 + 重渲染 */
function resetGrid(){
  renderChips();
  refresh();
}

/* ── 渲染 ─────────────────────────────────────── */
function card(it){
  var job = jobOf(it);
  var ar = (it.w && it.h) ? it.w + "/" + it.h : "1/1";
  var alt = (job.p || "").trim();
  if (alt.length < 6) alt = alt + " · Midjourney 探索榜 · " + (job.u || "");
  if (alt.length > 90) alt = alt.slice(0, 90) + "…";
  return '<li><div class="card" tabindex="0" data-key="' + it.i + '">'
       + '<img src="' + it.t + '" alt="' + esc(alt) + '" loading="lazy" decoding="async"'
       + ' style="--ar:' + ar + '">'
       + '<span class="ar">' + esc(it.a) + '</span>'
       + '<div class="cap">' + esc(job.u || "") + "</div></div></li>";
}
function render(){
  var list = filtered();
  var grid = $("#grid");
  var more = $("#more");
  if (!list.length){
    grid.innerHTML = "";
    $("#empty").hidden = false;
    more.hidden = true;
    return;
  }
  $("#empty").hidden = true;
  var slice = list.slice(state.shown, state.shown + PAGE_SIZE);
  if (!slice.length){ more.hidden = true; return; }
  var html = "";
  for (var i = 0; i < slice.length; i++) html += card(slice[i]);
  grid.insertAdjacentHTML("beforeend", html);
  state.shown += slice.length;
  more.hidden = state.shown >= list.length;
  more.textContent = Txt("more") + " (" + Math.max(0, list.length - state.shown) + ")";
  bindCards();
}
function bindCards(){
  $("#grid").querySelectorAll(".card").forEach(function(c){
    c.onclick = function(){ openLightbox(c.dataset.key); };
    c.onkeydown = function(e){ if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openLightbox(c.dataset.key); } };
  });
}
function refresh(){
  state.shown = 0;
  $("#grid").innerHTML = "";
  render();
}

/* ── 灯箱 ─────────────────────────────────────── */
var lbKey = null, lbList = [];
function openLightbox(key){
  var it = null;
  lbList = filtered();
  for (var i = 0; i < lbList.length; i++) if (lbList[i].i === key) { it = lbList[i]; break; }
  if (!it) return;
  var job = jobOf(it);
  lbKey = key;
  $("#lb").classList.add("on");
  document.body.style.overflow = "hidden";
  var img = $("#lbImg"), mid = $("#lbMid");
  mid.removeAttribute("src");
  img.src = it.t;
  img.alt = job.p || "";
  $("#lbTitle").textContent = (job.u || "") + " · " + it.a;
  $("#lbMeta").textContent = it.a + " · " + (it.w||"?") + "×" + (it.h||"?");
  // p 值：风格参考码，显示在提示词上方（与原站一致：sref 2918660786）
  var sref = $("#lbSref");
  if (job.s) { sref.textContent = "sref " + job.s; sref.hidden = false; }
  else { sref.textContent = ""; sref.hidden = true; }
  // 点 sref 码即复制（方便直接粘回 Midjourney 的 --sref 参数）
  sref.onclick = function(){
    if (!job.s) return;
    var el = this;
    navigator.clipboard.writeText(job.s).then(function(){
      var old = el.textContent;
      el.textContent = "已复制 " + job.s;
      setTimeout(function(){ el.textContent = old; }, 1400);
    }).catch(function(){});
  };
  $("#lbPrompt").textContent = job.p || "";
  $("#lbOrigin").onclick = function(){ window.open(job.o, "_blank", "noopener"); };
  $("#lbDl").onclick = function(){
    var a = document.createElement("a");
    a.href = it.g; a.download = ""; a.target = "_blank";
    document.body.appendChild(a); a.click(); a.remove();
  };
  var pre = new Image();
  pre.onload = function(){
    mid.src = it.m;
    requestAnimationFrame(function(){ mid.style.opacity = "1"; });
  };
  pre.onerror = function(){ mid.style.opacity = "0"; };
  pre.src = it.m;
  $("#lbCopy").onclick = function(){
    var btn = this;
    navigator.clipboard.writeText(job.p || "").then(function(){
      btn.textContent = Txt("copied");
      setTimeout(function(){ btn.textContent = Txt("copyPrompt"); }, 1400);
    }).catch(function(){ btn.textContent = Txt("copyFail"); });
  };
}
function closeLightbox(){
  lbKey = null;
  $("#lb").classList.remove("on");
  document.body.style.overflow = "";
  $("#lbImg").removeAttribute("src");
  $("#lbMid").removeAttribute("src");
}
function step(d){
  var pos = -1;
  for (var i = 0; i < lbList.length; i++) if (lbList[i].i === lbKey) { pos = i; break; }
  if (pos < 0) return;
  var next = (pos + d + lbList.length) % lbList.length;
  openLightbox(lbList[next].i);
}
$("#lbClose").onclick = closeLightbox;
$("#lb").addEventListener("click", function(e){ if (e.target.id === "lb") closeLightbox(); });
document.addEventListener("keydown", function(e){
  if (e.key === "Escape") closeLightbox();
  else if (lbKey && e.key === "ArrowRight") step(1);
  else if (lbKey && e.key === "ArrowLeft") step(-1);
});

/* ── 交互 ─────────────────────────────────────── */
$("#q").addEventListener("input", function(e){
  state.q = e.target.value; state.shown = 0; $("#grid").innerHTML = ""; render();
});
$("#sortSel").addEventListener("change", function(e){
  state.sort = e.target.value; state.shown = 0; $("#grid").innerHTML = ""; render();
});
$("#clearBtn").addEventListener("click", function(){
  state.q = ""; state.asp = null; state.batch = null; state.sort = "hot";
  $("#q").value = ""; $("#sortSel").value = "hot";
  resetGrid();
});
$("#more").addEventListener("click", render);
$("#themeBtn").addEventListener("click", function(){
  var cur = document.documentElement.dataset.theme;
  var next = cur === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("mje.theme", next); } catch(e){}
  this.textContent = next === "dark" ? Txt("themeDark") : Txt("themeLight");
});
$("#langBtn").addEventListener("click", function(){
  var cur = document.documentElement.dataset.lang;
  var next = cur === "ja" ? "zh" : "ja";
  document.documentElement.dataset.lang = next;
  try { localStorage.setItem("mje.lang", next); } catch(e){}
  this.textContent = next === "ja" ? Txt("langZh") : Txt("langJa");
  applyLang();
});
function applyLang(){
  var lang = document.documentElement.dataset.lang;
  document.documentElement.lang = lang === "ja" ? "ja-JP" : "zh-CN";
  document.title = Txt("title");
  document.querySelector('meta[name="description"]').content = IDX.desc;
  $("#q").placeholder = Txt("search");
  $("#sortSel").options[0].textContent = Txt("sortHot");
  $("#sortSel").options[1].textContent = Txt("sortNew");
  $("#sortSel").options[2].textContent = Txt("sortAspect");
  $("#clearBtn").textContent = Txt("all");
  $("#lbCopy").textContent = Txt("copyPrompt");
  $("#lbDl").textContent = Txt("dlFull");
  $("#lbOrigin").textContent = Txt("openOrigin");
  $("#lbClose").textContent = Txt("close");
  $("#lbTitle").textContent = "";
  renderChips();
}

/* 从落地页带 #asp=… 进来时直接定位到对应宽高比 */
function readHash(){
  var h = (location.hash || "").replace(/^#/, "");
  if(!h) return;
  h.split("&").forEach(function(kv){
    var i = kv.indexOf("=");
    if(i < 0) return;
    var k = kv.slice(0, i), v = decodeURIComponent(kv.slice(i + 1));
    if(k === "asp") state.asp = v;
  });
}
readHash();

/* 首屏渲染 */
applyLang();
refresh();
</script>
</body>
</html>
"""


def manifest_stats(rows):
    """统计数字只从 manifest 现算 —— 唯一来源，不回写任何配置文件。"""
    return {
        "n_images": len(rows),
        "n_jobs": len({r["jobId"] for r in rows}),
        "n_authors": len({r["username"] for r in rows}),
        "n_aspects": len({r["aspect"] for r in rows}),
        "n_batches": len({r.get("batch") for r in rows}),
    }


def with_counts(cfg, counts):
    """返回填好数量占位符的**副本**，不改动传入的 cfg。

    配置是构建的输入，不能被就地改写 —— 就地改会让模块级 UI/SEO 与 CONFIG
    分叉（页面会漏出 {n_images} 这种字面量）。一次性构建也不该影响其它读取方。
    """
    def fmt(v):
        if isinstance(v, str):
            try:
                return v.format(**counts)
            except (KeyError, IndexError, ValueError):
                return v      # 不是模板字符串，原样保留
        if isinstance(v, dict):
            return {k: fmt(x) for k, x in v.items()}
        if isinstance(v, tuple):
            return tuple(fmt(x) for x in v)
        if isinstance(v, list):
            return [fmt(x) for x in v]
        return v

    return {k: fmt(v) for k, v in cfg.items()}


def write_404():
    body = ("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>404 · Midjourney 探索榜</title>"
            "<link rel=\"icon\" href=\"/favicon.ico\" sizes=\"48x48\">"
            "<link rel=\"stylesheet\" href=\"/favicon.svg\" type=\"image/svg+xml\">"
            "<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;"
            "font:15px/1.7 system-ui,-apple-system,\"Segoe UI\",\"Noto Sans SC\",sans-serif;"
            "background:#fafaf9;color:#1c1917}main{text-align:center;padding:24px}"
            "h1{font-size:56px;margin:0 0 8px;letter-spacing:-.03em}"
            "p{color:#57534e;margin:0 0 18px}a{color:#0f766e;text-decoration:none;font-weight:600}"
            "@media(prefers-color-scheme:dark){body{background:#0c0a09;color:#f5f5f4}p{color:#a8a29e}"
            "a{color:#2dd4bf}}</style></head><body><main><h1>404</h1>"
            "<p>这个页面不存在。</p><a href=\"./\">← 回到 Midjourney 探索榜</a></main></body></html>")
    with open(os.path.join(SITE, "404.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(body)


def write_robots():
    with open(os.path.join(SITE, "robots.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)


def copy_og_cover():
    """用 manifest 里第一张图当 og-cover（没有独立封面资源时）。"""
    src = os.path.join(SITE, "og-cover.jpg")
    if os.path.exists(src):
        return
    rows = load_manifest()
    if not rows:
        return
    cand = os.path.join(SITE, rows[0]["mid_path"])
    if not os.path.exists(cand):
        cand = os.path.join(SITE, rows[0]["thumb_path"])
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
        # 1200×630 社交分享图
        w, h = im.size
        tw, th = 1200, 630
        scale = max(tw / w, th / h)
        nw, nh = int(w * scale + 1), int(h * scale + 1)
        im = im.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - tw) // 2, (nh - th) // 2
        im.crop((left, top, left + tw, top + th)).save(src, "JPEG", quality=88)
    print("og-cover.jpg 已生成")


def main():
    rows = load_manifest()
    assert_manifest_integrity(rows)
    stats = manifest_stats(rows)
    n_images, n_jobs = stats["n_images"], stats["n_jobs"]
    n_authors, n_aspects = stats["n_authors"], stats["n_aspects"]

    # 文案数量按实际数据填进**副本**；模块级 CONFIG 保持只读（配置是输入）
    cfg = with_counts(CONFIG, stats)

    write_data(build_data(rows, cfg))

    page = page_template()
    page = page.replace("__LANDING_CSS__", landing_mod.SEO_INTRO_CSS)
    page = page.replace("__PAGE_SIZE__", str(PAGE_SIZE))
    page = page.replace("__SITE__", SITE_URL)
    zh = cfg["ui"]["zh"]
    page = page.replace("__TITLE__", cfg["title"])
    page = page.replace("__DESC__", cfg["desc"])
    page = page.replace("__OGSITE__", cfg["ogSite"])
    page = page.replace("__OGTITLE__", cfg["ogTitle"])
    page = page.replace("__OGDESC__", cfg["ogDesc"])
    page = page.replace("__TWTITLE__", cfg["twTitle"])
    page = page.replace("__TWDESC__", cfg["twDesc"])
    page = page.replace("__N_IMG__", str(n_images))
    page = page.replace("__N_JOB__", str(n_jobs))
    page = page.replace("__N_AUTHOR__", str(n_authors))
    page = page.replace("__N_ASP__", str(n_aspects))
    page = page.replace("__H1__", "Midjourney 探索榜：社区精选成图与提示词")
    page = page.replace("__BRAND1__", "Midjourney")
    page = page.replace("__BRAND2__", "探索榜")
    page = page.replace("__EYEBROW__", zh["eyebrow"])
    page = page.replace("__SUB1__", zh["sub1"])
    page = page.replace("__SUB2__", zh["sub2"])
    page = page.replace("__HOME__", zh["home"])
    page = page.replace("__THEMEA__", zh["themeAria"])
    page = page.replace("__THEMEL__", zh["themeLight"])
    page = page.replace("__LANGA__", zh["langAria"])
    page = page.replace("__LANGJA__", zh["langJa"])
    page = page.replace("__SEARCH__", zh["search"])
    page = page.replace("__SORTLABEL__", "排序")
    page = page.replace("__SORTHOT__", zh["sortHot"])
    page = page.replace("__SORTNEW__", zh["sortNew"])
    page = page.replace("__SORTASP__", zh["sortAspect"])
    page = page.replace("__CLEAR__", zh["all"])
    page = page.replace("__EMPTYTITLE__", zh["emptyTitle"])
    page = page.replace("__EMPTYDESC__", zh["emptyDesc"])
    page = page.replace("__MORE__", "加载更多")
    page = page.replace("__COPYP__", zh["copyPrompt"])
    page = page.replace("__DLFULL__", zh["dlFull"])
    page = page.replace("__OPENORIGIN__", zh["openOrigin"])
    page = page.replace("__CLOSE__", "关闭")
    page = page.replace("__FOOTER__", zh["footer"])

    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "name": CONFIG["seoPages"]["name"],
             "url": SITE_URL + "/", "inLanguage": ["zh-CN", "ja"]},
            {"@type": "ImageGallery", "name": CONFIG["schemaName"],
             "alternateName": CONFIG["schemaAlt"], "url": SITE_URL + "/",
             "numberOfItems": n_images, "about": CONFIG["schemaAbout"],
             "isAccessibleForFree": True,
             "creator": {"@type": "Organization", "name": CONFIG["seoPages"]["author"],
                         "url": CONFIG["seoPages"]["authorUrl"]}},
        ],
    }
    page = page.replace("__SCHEMA__", json.dumps(schema, ensure_ascii=False, separators=(",", ":")))
    # FAQPage 结构化数据：独立一段 ld+json（shared/landing.py 统一生成）
    page = page.replace("__FAQ_LD__", landing_mod.faq_ld_script(cfg["seoPages"]["faq"]))

    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    # 静态落地页
    site, facets = build_facets(rows, cfg)
    urls = landing_mod.write_site(site, facets)
    landing_mod.sitemap(SITE_URL, urls, os.path.join(SITE, "sitemap.xml"))

    # 主画廊页底部的「关于本站」卡片（不依赖 JS，搜索引擎和 AI 直接可读）
    inject_seo_intro(rows, urls, cfg)

    write_404()
    write_robots()
    copy_og_cover()

    size = os.path.getsize(os.path.join(SITE, "index.html")) / 1024
    print("index.html %.1f KB（%d 张图 / %d 条作业）" % (size, n_images, n_jobs))
    print("数据单文件 gallery.js · 作业 %d 条 · 批次 %d 个"
          % (n_jobs, stats["n_batches"]))
    print("落地页 %d 个" % len(urls))


def inject_seo_intro(rows, urls, cfg):
    """把「关于本站」卡片插进主画廊页（不依赖 JS）。"""
    path = os.path.join(SITE, "index.html")
    html = open(path, encoding="utf-8").read()
    sp = cfg["seoPages"]
    n_images = len(rows)
    n_jobs = len({r["jobId"] for r in rows})
    facts = [("成图", "%d 张" % n_images), ("作业", "%d 条" % n_jobs),
             ("作者", "%d 位" % len({r["username"] for r in rows})),
             ("授权", "禁止再分发")]
    # 「风格码库」已拆成兄弟站 mj-styles（原站 Styles 是独立内容类型，
    # 与本集的「一条作业四格成图」不同源，两边码表交集为 0）。
    # 链接用站点间相对路径 ../mj-styles/。
    links = [("browse/", "按宽高比浏览"), ("../mj-styles/", "风格码库")]
    card = landing_mod.static_intro(sp["introParas"](n_jobs, n_images), facts, links, sp["faq"])
    # 插到 </footer> 之前
    marker = "</footer>"
    if marker in html:
        html = html.replace(marker, card + "\n" + marker, 1)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)


if __name__ == "__main__":
    main()
