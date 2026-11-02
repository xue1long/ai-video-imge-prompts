# -*- coding: utf-8 -*-
"""提示词生图集（PROMPTS-DB-01）· 页面构建

用法（一般通过 tools/build.py 调度，环境变量 SITE_URL 写进 canonical/og/sitemap）:
  SITE_URL=https://photoai.life/prompts python build_gallery.py
  python build_gallery.py --check      # 校验 manifest 与图片，不写页面

输入: data/prompts_<key>.json（每个模型一份，入库）+ data/dims.json（图片宽高，入库）
产出: index.html + data/gallery.js（模型索引）+ data/gallery_<key>.js（各模型数据分片）
      + robots.txt + sitemap.xml + 404.html
      + cat/<slug>/index.html（SEO 落地页，shared/landing.py）+ data/landing.json
纯标准库；图片走相对路径 img/。
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sites/prompts（脚本在 scripts/ 下）
ROOT = os.path.dirname(os.path.dirname(HERE))              # 仓库根
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "shared"))
from config import (META, META_JA, UI, UI_JA, ACCENT, MODELS, DEFAULT_MODEL,  # noqa: E402
                    DATA_GLOB, DIMS, GALLERY_JS, GALLERY_SHARD, OUTPUT,
                    USER_ASSETS, SITE, SEO_CATEGORIES)
import landing as landing_mod                                   # noqa: E402
from image_policy import site_entry, tier_addr  # noqa: E402

SITE_URL = os.environ.get("SITE_URL", "https://example.com").rstrip("/")


def _ratio(w, h):
    """宽高 → 化简比例字符串（如 800x1200 → "2:3"）；无法化简时返回 None。"""
    if not w or not h:
        return None
    from math import gcd
    g = gcd(w, h) or 1
    a, b = w // g, h // g
    return f"{a}:{b}" if a <= 21 and b <= 21 else None


# 取图策略：按档位声明在站点清单里，决定展示地址与回落地址
SITE_CFG = site_entry("prompts")


def load_manifest():
    """各模型的文本数据 + 宽高 → 页面记录。宽高来自 dims.json（不依赖图片在本地）。"""
    paths = sorted(glob.glob(os.path.join(HERE, DATA_GLOB)))
    if not paths:
        sys.exit(f"✗ 找不到 {DATA_GLOB}，先运行 import_youmind.py")
    dims_path = os.path.join(HERE, DIMS)
    dims = {}
    if os.path.exists(dims_path):
        with open(dims_path, encoding="utf-8") as f:
            dims = json.load(f)
    missing_dims = 0
    out = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        if not rows:
            print(f"⚠ {os.path.basename(path)} 为空，跳过")
            continue
        for r in rows:
            r = dict(r)
            # tags 在源数据里是逗号拼接字符串（import 产出的存储格式），解析成列表
            tags = r.get("tags")
            if isinstance(tags, str):
                seen = set()
                parsed = []
                for t in re.split(r"[,，、;；]", tags):
                    t = t.strip()
                    if t and t not in seen:
                        seen.add(t)
                        parsed.append(t)
                r["tags"] = parsed
            # 模型分片键 = img/<key>/ 的 <key>
            parts = r["file"].split("/")
            r["key"] = parts[1] if len(parts) > 2 and parts[0] == "img" else "misc"
            w, h = dims.get(r["file"], (None, None))
            if w:
                r["w"], r["h"] = w, h
            else:
                missing_dims += 1
            ar = _ratio(w, h)
            if ar:
                r["params"] = {"ar": ar}
            # 缩略图档：与原图同名，只是把 img/ 换为 thumbs/
            r["thumb"] = "thumbs/" + r["file"][4:]
            # 取图策略要求的编码（见 shared/image_policy.py）：
            #   <字段>     展示地址（直连上游时是上游 URL，否则是站内相对路径）
            #   <字段>Url  上游地址，仅本地优先时写出，作为加载失败的回落目标
            for tier, fkey, ukey in (("thumb", "thumb", "thumbUrl"), ("full", "file", "url")):
                path = r[fkey]
                url = r.get(ukey) or ""
                display, fallback, keep_path = tier_addr(SITE_CFG, tier, path, url)
                r[fkey] = display
                if fallback:
                    r[fkey + "Fb"] = fallback
                if keep_path:
                    r[fkey + "Path"] = path
            r.pop("url", None)          # 页面数据不需要 CDN 原链（manifest.json 负责）
            r.pop("thumbUrl", None)
            out.append(r)
    if missing_dims:
        print(f"⚠ {missing_dims} 条记录缺宽高（data/dims.json 不全，重跑 scripts/manifest.py）")
    return out


def facets(rows):
    """模型 / 标签 / 画幅分面（按出现次数降序，同数按名称）。"""
    tags, ars, models = {}, {}, {}
    for r in rows:
        for t in r.get("tags", []):
            tags[t] = tags.get(t, 0) + 1
        ar = (r.get("params") or {}).get("ar")
        if ar:
            ars[ar] = ars.get(ar, 0) + 1
        m = (r.get("model") or "").strip()
        if m:
            models[m] = models.get(m, 0) + 1
    return (sorted(tags.items(), key=lambda x: (-x[1], x[0])),
            sorted(ars.items(), key=lambda x: (-x[1], x[0])),
            sorted(models.items(), key=lambda x: (-x[1], x[0])))


def load_user_assets():
    """站主自己挂到提示词下的图（覆盖层）。

    这份文件由 sync_user_assets.py 从素材管理器导出，和 prompts_<key>.json 完全解耦：
    重新 import 上游数据不会碰它，删掉它也只是回到「纯上游素材」。
    """
    path = os.path.join(HERE, USER_ASSETS)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except ValueError as e:
        sys.exit(f"✗ {USER_ASSETS} 不是合法 JSON: {e}")
    return data.get("items") or {}


def group_user_assets(rows, user):
    """覆盖层按分片 key 分组；挂在不存在的 originId 上的单独挑出来。

    上游数据换批之后，之前挂过图的提示词可能整条消失——这时候不能悄悄丢，
    要出声，否则「我明明挂了图，页面上没有」会变成悬案。
    """
    gid2key = {r.get("originId"): r["key"] for r in rows if r.get("originId")}
    by_key, orphan = {}, []
    for gid, files in user.items():
        key = gid2key.get(gid)
        if not key:
            orphan.append(gid)
            continue
        by_key.setdefault(key, {})[gid] = files
    return by_key, orphan


def user_image_count(by_key, key):
    return sum(len(v) for v in by_key.get(key, {}).values())


def check(rows):
    """校验 manifest 记录的图片是否在本地（只报缺失与汇总，不逐条打印）"""
    bad = 0
    for r in rows:
        if not os.path.exists(os.path.join(HERE, r["file"])):
            print(f"  ✗ {r['originId']:12s} 图片缺失: {r['file']}")
            bad += 1
    print(f"check: {len(rows) - bad}/{len(rows)} 张图片在本地")
    # 用户图不在 manifest 里，单独校验：漏同步时会变成 404 的破图
    user_bad = 0
    for gid, files in load_user_assets().items():
        for f in files:
            if not os.path.exists(os.path.join(HERE, f["file"])):
                print(f"  ✗ {gid:12s} 用户图缺失: {f['file']}（重跑 sync_user_assets.py）")
                user_bad += 1
    if user_bad:
        print(f"check: 用户图缺 {user_bad} 张")
    return bad + user_bad


def write_seo_extras(landing_urls):
    """robots.txt / sitemap.xml / 404.html（与 pose 站同构）"""
    with open(os.path.join(HERE, "robots.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)
    landing_mod.sitemap(SITE_URL, landing_urls, os.path.join(HERE, "sitemap.xml"))
    with open(os.path.join(HERE, "404.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write("""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0;url=/">
<title>404 · 提示词生图集</title></head>
<body><p>页面不存在，正在返回<a href="/">首页</a>…</p></body></html>
""")


def build_landing(items, by_tag):
    """官方分类 → 静态落地页（shared/landing.py），返回绝对 URL 列表"""
    site = landing_mod.Site(
        id="prompts", root=HERE, site_url=SITE_URL,
        name=SITE["name"], tagline=SITE["tagline"], license_note=SITE["license_note"],
        author=SITE["author"], author_url=SITE["author_url"], source=SITE["source"],
        faq=SITE["faq"], accent=ACCENT,
        index_title=SITE["index_title"], index_intro=SITE["index_intro"])
    facets = []
    for slug, tag in SEO_CATEGORIES:
        rows = by_tag.get(tag, [])
        if len(rows) < landing_mod.MIN_ITEMS:
            continue
        rows = sorted(rows, key=lambda r: -(r.get("w") or 0) * (r.get("h") or 0))
        n = len(rows)
        facets.append(landing_mod.Facet(
            slug=f"cat/{slug}",
            title=f"{tag} AI 生图提示词 · {SITE['name']}",
            h1=f"{tag} AI 生图提示词",
            description=f"共 {n} 张「{tag}」方向的 AI 生图参考，每张附英文原文提示词与中文翻译，"
                        f"可按标签与画幅筛选，一键复制提示词到生图工具。",
            intro=[f"「{tag}」是 GPT Image 2 提示词库中最受欢迎的方向之一，本页收录其中 {n} 张代表性成图。",
                   "每张图都保留原始作者、来源与发布时间（CC BY 4.0）。展示的提示词为中文翻译，"
                   "在画廊灯箱中可一键复制英文原文，直接粘贴到生图工具使用。"],
            items=[landing_mod.Item(
                       thumb=r["thumb"],
                       alt=(r.get("title") if len(r.get("title") or "") >= 6
                            else f"{r.get('title') or tag} · {tag}AI 生图提示词"),
                       w=r.get("w"), h=r.get("h"))
                   for r in rows[:landing_mod.GRID_MAX]],
            gallery_hash=f"tag={tag}",
            facts=[("图片", str(n)), ("提示词", "双语（展示中文 / 复制英文原文）"), ("授权", "CC BY 4.0")],
            related=[(f"cat/{s2}", t2, len(by_tag.get(t2, []))) for s2, t2 in SEO_CATEGORIES if s2 != slug][:6],
            group="官方分类", label=tag))
    return landing_mod.write_site(site, facets)


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__SITE__/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="photoai.life · __TITLE__">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__SITE__/">
<meta property="og:image" content="__SITE__/og-cover.jpg">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">__FAQ_LD__</script>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='__ACCENT__'/%3E%3Ctext x='16' y='23' font-size='17' font-family='sans-serif' font-weight='700' text-anchor='middle' fill='%23fff'%3E__BRAND__%3C/text%3E%3C/svg%3E">
<script>
(function(){try{
  var t=localStorage.getItem('mj.theme'); if(t==='light'||t==='dark') document.documentElement.dataset.theme=t;
}catch(e){}})();
</script>
<style>
:root{
  --accent:__ACCENT__;
  --bg:#f6f7f9; --fg:#1c1f24; --muted:#6b7280;
  --card:#ffffff; --line:#e4e7ec; --chip:#f0f2f5; --chip-on:#ece7ff;
  --shadow:0 1px 3px rgba(0,0,0,.07);
}
[data-theme=dark]{
  --bg:#14161a; --fg:#e8eaed; --muted:#9aa1ab;
  --card:#1d2026; --line:#2c313a; --chip:#262b33; --chip-on:#37305c;
  --shadow:0 1px 3px rgba(0,0,0,.4);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:15px/1.6 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px 60px}
header{padding:34px 0 10px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:.5px}
.sub{color:var(--muted);font-size:13.5px;margin:0}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:22px 0 10px}
#q{flex:1;min-width:220px;padding:9px 14px;border:1px solid var(--line);border-radius:10px;
  background:var(--card);color:var(--fg);font-size:14px;outline:none}
#q:focus{border-color:var(--accent)}
#arSel{padding:9px 10px;border:1px solid var(--line);border-radius:10px;
  background:var(--card);color:var(--fg);font-size:13.5px}
#count{color:var(--muted);font-size:13px;white-space:nowrap}
.tagbar{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 20px}
.chip{padding:4px 12px;border-radius:999px;border:1px solid var(--line);
  background:var(--chip);color:var(--muted);font-size:12.5px;cursor:pointer;
  user-select:none;transition:.15s}
.chip:hover{color:var(--fg)}
.chip.on{background:var(--chip-on);border-color:var(--accent);color:var(--fg);font-weight:600}
.chip b{opacity:.55;font-weight:400;margin-left:3px}
#langBtn{margin-left:auto;padding:6px 14px;border:1px solid var(--line);border-radius:10px;
  background:var(--card);color:var(--fg);font-size:13px;cursor:pointer}
#langBtn:hover{border-color:var(--accent)}
#themeBtn{padding:6px 14px;border:1px solid var(--line);border-radius:10px;
  background:var(--card);color:var(--fg);font-size:13px;cursor:pointer}
#themeBtn:hover{border-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;
  cursor:pointer;box-shadow:var(--shadow);transition:transform .15s,box-shadow .15s;
  display:flex;flex-direction:column;position:relative}
.card:hover{transform:translateY(-3px);box-shadow:0 6px 18px rgba(0,0,0,.12)}
.favbtn{position:absolute;top:8px;right:8px;width:32px;height:32px;border-radius:50%;
  border:none;background:rgba(15,17,21,.45);color:#fff;font-size:16px;line-height:1;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  opacity:0;transition:.15s;backdrop-filter:blur(2px)}
.card:hover .favbtn{opacity:1}
.favbtn.on{opacity:1;color:#ffd24d}
.favbtn:hover{transform:scale(1.12)}
.delbtn{position:absolute;top:8px;left:8px;width:32px;height:32px;border-radius:50%;
  border:none;background:rgba(15,17,21,.45);color:#fff;font-size:14px;line-height:1;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  opacity:0;transition:.15s;backdrop-filter:blur(2px)}
.card:hover .delbtn{opacity:1}
.delbtn:hover{background:#e5484d;transform:scale(1.12)}
.card.trashed{opacity:.55}
.card.trashed img{filter:grayscale(.7)}
/* 一条素材多张成图：卡片内切换 图1/图2/图3 */
.thumbwrap{position:relative;display:block;line-height:0}
.fnav{position:absolute;left:8px;bottom:8px;display:flex;gap:4px;padding:3px 5px;
  border-radius:999px;background:rgba(15,17,21,.5);backdrop-filter:blur(4px)}
.fnum{min-width:18px;text-align:center;font-size:11px;line-height:1.5;color:#fff;
  border-radius:999px;cursor:pointer;opacity:.7;transition:.12s}
.fnum:hover{opacity:1;background:rgba(255,255,255,.18)}
.fnum.on{background:var(--accent);opacity:1;font-weight:600}
.fcount{font-size:11px;color:#fff;padding:1px 4px;opacity:.85}
.restorebtn{position:absolute;top:8px;right:8px;padding:6px 12px;border-radius:999px;border:none;
  background:rgba(15,17,21,.55);color:#fff;font-size:12px;cursor:pointer;
  opacity:0;transition:.15s;backdrop-filter:blur(2px)}
.card:hover .restorebtn{opacity:1}
.restorebtn:hover{background:var(--accent);transform:scale(1.05)}
#delBtn{padding:6px 14px;border-radius:9px;border:1px solid var(--line);
  background:var(--chip);color:var(--fg);font-size:13px;cursor:pointer}
#delBtn:hover{border-color:#e5484d;color:#e5484d}
.chip.trashchip{color:#b3584e}
.chip.trashchip.on{background:#f5e0dc;border-color:#e5484d;color:#8f2f26;font-weight:600}
[data-theme=dark] .chip.trashchip.on{background:#4a2622;border-color:#e5484d;color:#ffb4a8}
.thumb{width:100%;object-fit:cover;display:block;background:var(--chip)}
.cbody{padding:12px 14px 14px;display:flex;flex-direction:column;gap:8px}
.ctitle{font-weight:600;font-size:14.5px}
.cprompt{color:var(--muted);font-size:12.5px;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.cmeta{display:flex;flex-wrap:wrap;gap:5px}
.mini{padding:2px 8px;border-radius:6px;background:var(--chip);color:var(--muted);font-size:11px}
.mini.acc{background:var(--chip-on);color:var(--fg)}
.mini.mdl{color:var(--accent);font-weight:600}
.mini.srclink{color:var(--accent);text-decoration:none}
.empty{display:none;text-align:center;color:var(--muted);padding:70px 0}
.empty h3{margin:0 0 6px;color:var(--fg)}
footer{margin-top:36px;color:var(--muted);font-size:12px;text-align:center}
kbd{border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:11px;background:var(--chip)}
/* 灯箱 */
#lb{position:fixed;inset:0;background:rgba(10,12,16,.72);display:none;z-index:50;
  align-items:center;justify-content:center;padding:24px}
#lb.open{display:flex}
.lbbox{background:var(--card);border-radius:16px;max-width:960px;width:100%;
  max-height:92vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.45)}
.lbimg{width:100%;object-fit:contain;max-height:56vh;background:#0c0e12;display:block}
.lbbody{padding:16px 20px 20px;overflow:auto}
.lbrow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.lbtitle{font-size:17px;font-weight:700;margin:0}
#copyBtn{margin-left:auto;padding:6px 14px;border-radius:9px;border:1px solid var(--line);
  background:var(--chip);color:var(--fg);font-size:13px;cursor:pointer}
#copyBtn:hover{border-color:var(--accent)}
#copyBtn.ok{background:var(--chip-on);border-color:var(--accent)}
.lbprompt{white-space:pre-wrap;background:var(--chip);border-radius:10px;padding:12px 14px;
  font-size:13.5px;line-height:1.7;margin:0 0 10px}
/* 灯箱里的成图切换条 */
.lbfiles{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 10px}
.lbfiles img{width:62px;height:62px;object-fit:cover;border-radius:8px;cursor:pointer;
  opacity:.55;border:2px solid transparent;transition:.12s}
.lbfiles img:hover{opacity:.85}
.lbfiles img.on{opacity:1;border-color:var(--accent)}
/* 站主自己挂的图：虚线框，和上游素材一眼分开 */
.lbfiles img.own{outline:1.5px dashed var(--muted);outline-offset:1px}
.mini.self{background:transparent;border:1px dashed var(--accent);color:var(--accent)}
.tagedit{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 10px}
.tagedit .mini{display:inline-flex;align-items:center;gap:4px}
.tagedit .mini .rm{cursor:pointer;opacity:.5;font-style:normal}
.tagedit .mini .rm:hover{opacity:1;color:#e5484d}
.tagedit .mini.own{border:1px dashed var(--accent);background:transparent;color:var(--accent)}
#taginput{border:1px dashed var(--line);border-radius:6px;background:transparent;color:var(--fg);
  font-size:11.5px;padding:3px 8px;min-width:150px;outline:none}
#taginput:focus{border-color:var(--accent)}
#favBtn{padding:6px 14px;border-radius:9px;border:1px solid var(--line);
  background:var(--chip);color:var(--fg);font-size:13px;cursor:pointer}
#favBtn:hover{border-color:var(--accent)}
#favBtn.on{background:var(--chip-on);border-color:var(--accent);color:var(--accent);font-weight:600}
#sentinel{height:2px}
#morehint{text-align:center;color:var(--muted);font-size:12.5px;padding:18px 0 0}
#morehint button{border:1px solid var(--line);border-radius:9px;background:var(--card);
  color:var(--fg);font-size:13px;padding:8px 20px;cursor:pointer}
#morehint button:hover{border-color:var(--accent)}
@media (max-width:640px){.grid{grid-template-columns:1fr 1fr}.thumb{height:auto}}
__SEO_CSS__
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1 id="pagetitle">__TITLE__</h1>
  <p class="sub" id="pagesub">__SUBTITLE__</p>
</header>

<div class="toolbar">
  <input id="q" type="search" placeholder="__SEARCH__" autocomplete="off">
  <select id="arSel"></select>
  <span id="count"></span>
  <button id="langBtn"></button>
  <button id="themeBtn" title="切换主题"></button>
</div>
<div class="tagbar" id="modelbar"></div>
<div class="tagbar" id="tagbar"></div>

<div class="grid" id="grid"></div>
<div id="sentinel"></div>
<div id="morehint"></div>
<div class="empty" id="empty">
  <h3>__EMPTY_TITLE__</h3>
  <p>__EMPTY_DESC__</p>
</div>

__SEO_INTRO__
<footer id="foot">__COUNT_HINT__ · <kbd>Esc</kbd> __ESC_HINT__ · __FOOTER__</footer>
</div>

<div id="lb">
  <div class="lbbox">
    <img class="lbimg" id="lbimg" alt="">
    <div class="lbbody">
      <div class="lbrow">
        <h2 class="lbtitle" id="lbtitle"></h2>
        <button id="favBtn"></button>
        <button id="delBtn"></button>
        <button id="copyBtn">__COPY__</button>
      </div>
      <div class="lbfiles" id="lbfiles"></div>
      <pre class="lbprompt" id="lbprompt"></pre>
      <div class="tagedit" id="lbtags"></div>
      <div class="cmeta" id="lbmeta"></div>
    </div>
  </div>
</div>

<script src="data/gallery.js"></script>
<script>
/* 索引只有模型清单与总数；各模型的数据是独立分片，切换模型时才按需加载 */
var IDX = window.__GALLERY__;
var SHARDS = window.__SHARDS__ || {};
var DATA = { items: [], tags: [], ars: [] };
var UISET = { zh: __UI__, ja: __UI_JA__ };
var METASET = { zh: __META_ZH__, ja: __META_JA__ };
var lang = "zh";
try { lang = localStorage.getItem("mj.lang") || "zh"; } catch(e){}
if (!UISET[lang]) lang = "zh";
var UI = UISET[lang];
function setLang(l){
  lang = l; UI = UISET[l];
  try { localStorage.setItem("mj.lang", l); } catch(e){}
  applyStatic(); themeLabel(); render();
}
function applyStatic(){
  var m = METASET[lang];
  document.title = m.title;
  $("#pagetitle").textContent = m.title;
  $("#pagesub").textContent = m.subtitle;
  $("#q").placeholder = UI.search;
  $("#langBtn").textContent = lang === "zh" ? "日本語" : "中文";
  var cnt = UI.count.replace(/<[^>]*>/g, "").replace("{n}", String(IDX.prompts));
  var imgs = UI.countImgs.replace("{n}", String(IDX.total));
  $("#foot").textContent = cnt + " · " + imgs + " · Esc " + UI.escHint + " · " + UI.footer;
}
var state = { q: "", tags: [], ar: "", model: IDX["default"] || "", fav: false, trash: false, shown: 0 };
var PAGE_SIZE = 240;   /* 增量渲染：每次渲染的张数 */
var $ = function(s){ return document.querySelector(s); };

/* —— 模型分片：进站只加载默认模型，切模型时才拉另一份 ——
   一条素材 = 一条提示词 + 它的全部成图（files），卡片与灯箱里可以选图1/图2/图3。
   分片里图片存 [文件名,宽,高,比例]，路径在加载时拼出。 */
var _loaded = {};      /* key → { items, tags, ars } */
var _loading = {};     /* key → Promise */
function normalizeShard(key, sh){
  var label = sh.label || key, out = [];
  (sh.items || []).forEach(function(it){
    var files = (it.f || []).map(function(f){
      /* f[4]/f[5] 只有自制图才有：它在 userimg/ 下，不跟 img/<key>/ 的约定走 */
      var o = { name: f[0], file: f[4] || ("img/" + key + "/" + f[0]),
                thumb: f[5] || ("thumbs/" + key + "/" + f[0]),
                w: f[1] || 0, h: f[2] || 0, ar: f[3] || "" };
      if (f[6]) o.own = 1;
      return o;
    });
    if (!files.length) return;
    var rec = {
      id: it.i || (key + ":" + files[0].name),  /* 素材级 id：收藏/删除/手动标签都按它 */
      key: key, model: sh.m || key, modelLabel: label,
      title: it.t || "", prompt: it.p || "", promptRaw: it.r || it.p || "",
      tags: it.g || [], author: it.a || "", sourceUrl: it.u || "", published: it.d || "",
      files: files, cover: 0
    };
    adoptLegacy(rec);
    out.push(rec);
  });
  if (_legacyDirty) saveLegacy();
  return { items: out, tags: sh.tags || [], ars: sh.ars || [] };
}
function loadShard(key){
  if (_loaded[key]) return Promise.resolve();
  if (_loading[key]) return _loading[key];
  _loading[key] = new Promise(function(resolve, reject){
    var s = document.createElement("script");
    s.src = "data/gallery_" + key + ".js";
    s.async = true;
    s.onload = function(){
      var sh = (window.__SHARDS__ || {})[key];
      if (!sh) return reject(new Error("分片为空: " + key));
      _loaded[key] = normalizeShard(key, sh);
      resolve();
    };
    s.onerror = function(){ reject(new Error("分片加载失败: " + key)); };
    document.head.appendChild(s);
  });
  return _loading[key];
}
function activeKeys(){
  return state.model ? [state.model] : IDX.models.map(function(m){ return m.key; });
}
function rebuild(){
  var items = [], tagN = {}, arN = {};
  activeKeys().forEach(function(k){
    var sh = _loaded[k]; if (!sh) return;
    items = items.concat(sh.items);
    sh.tags.forEach(function(x){ tagN[x.t] = (tagN[x.t] || 0) + x.n; });
    sh.ars.forEach(function(x){ arN[x.a] = (arN[x.a] || 0) + x.n; });
  });
  DATA.items = items;
  DATA.tags = Object.keys(tagN).map(function(t){ return { t: t, n: tagN[t] }; })
                    .sort(function(a, b){ return b.n - a.n || (a.t < b.t ? -1 : 1); });
  DATA.ars = Object.keys(arN).map(function(a){ return { a: a, n: arN[a] }; })
                   .sort(function(a, b){ return b.n - a.n || (a.a < b.a ? -1 : 1); });
}
function setBusy(on, msg){
  document.body.classList.toggle("busy", !!on);
  if (on) $("#count").textContent = msg || UI.loading;
}
function ensureData(){
  var todo = activeKeys().filter(function(k){ return !_loaded[k]; });
  if (!todo.length){ rebuild(); render(); return; }
  setBusy(true);
  Promise.all(todo.map(loadShard)).then(function(){
    setBusy(false);
    rebuild();
    render();
  }).catch(function(e){
    setBusy(false);
    $("#foot").textContent = String((e && e.message) || e);
  });
}
function switchModel(key){
  if (state.model === key) return;
  state.model = key;
  state.tags = [];          /* 各模型的标签体系不同，跨模型保留标签会筛出空集 */
  state.ar = "";
  ensureData();
}

/* —— 收藏 & 手动标签 & 回收站（localStorage 持久化，按图片路径为键，重建页面不丢）—— */
function lsGet(k, d){
  try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch(e){ return d; }
}
function lsSet(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch(e){} }
var favs = lsGet("mj.favs", {});          /* { "<file>": true } */
var userTags = lsGet("mj.usertags", {});  /* { "<file>": ["标签", ...] } */
var trash = lsGet("mj.trash", {});        /* { "<file>": true } */
function keyOf(r){ return r.id || (r.files && r.files[0] ? r.files[0].file : ""); }
/* 旧版是「一图一条」，收藏/标签/回收站都以图片路径为键；现在按素材存。
   加载分片时把旧键迁到素材 id，否则升级后用户的收藏会凭空消失。 */
var _legacyDirty = false;
function adoptLegacy(rec){
  rec.files.forEach(function(f){
    var p = f.file;
    if (trash[p]){ trash[rec.id] = true; delete trash[p]; _legacyDirty = true; }
    if (favs[p]){ favs[rec.id] = true; delete favs[p]; _legacyDirty = true; }
    var t = userTags[p];
    if (t && t.length){
      userTags[rec.id] = (userTags[rec.id] || []).concat(t);
      delete userTags[p];
      _legacyDirty = true;
    }
  });
}
function saveLegacy(){
  lsSet("mj.favs", favs); lsSet("mj.trash", trash); lsSet("mj.usertags", userTags);
  _legacyDirty = false;
}
function isFav(r){ return !!favs[keyOf(r)]; }
function isTrashed(r){ return !!trash[keyOf(r)]; }
function toggleFav(r){
  var k = keyOf(r);
  if (favs[k]) delete favs[k]; else favs[k] = true;
  lsSet("mj.favs", favs);
}
function delItem(r){
  trash[keyOf(r)] = true;
  lsSet("mj.trash", trash);
}
function restoreItem(r){
  delete trash[keyOf(r)];
  lsSet("mj.trash", trash);
}
function tagsOf(r){
  var base = (r.tags || []).slice();
  (userTags[keyOf(r)] || []).forEach(function(t){
    if (base.indexOf(t) < 0) base.push(t);
  });
  return base;
}

function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function curFile(r){
  return r.files[r.cover] || r.files[0] || {};
}
function paramsOf(r){
  var f = curFile(r), out = [];
  if (f && f.ar) out.push({k: "ar", v: f.ar});
  return out;
}
function ratioOf(r){
  var f = curFile(r);
  if (f.ar && /^\d+:\d+$/.test(f.ar)){
    var a = f.ar.split(":"); return a[0] + "/" + a[1];
  }
  if (f.w && f.h) return f.w + "/" + f.h;
  return "4/3";
}
function baseMatch(r){
  /* 基础匹配：画幅 + 标签 + 关键词（不含视图/收藏过滤） */
  if (state.ar && !r.files.some(function(f){ return f.ar === state.ar; })) return false;
  var ts = tagsOf(r);
  for (var i = 0; i < state.tags.length; i++){
    if (ts.indexOf(state.tags[i]) < 0) return false;
  }
  if (state.q){
    var hay = ((r.title||"") + " " + (r.rawPrompt||r.prompt||"") + " " + tagsOf(r).join(" ")
             + " " + (r.modelLabel||"") + " " + (r.model||"") + " " + (r.promptRaw||"")
             + " " + (r.author||"")).toLowerCase();
    if (hay.indexOf(state.q) < 0) return false;
  }
  return true;
}
function coreMatch(r){
  /* 视图感知：正常视图隐藏已删除，回收站视图只显示已删除 */
  if (isTrashed(r) !== state.trash) return false;
  if (state.fav && !isFav(r)) return false;
  return baseMatch(r);
}
function matches(r){
  return coreMatch(r) && (!state.model || (r.key||"") === state.model);
}
function renderFacets(){
  var tb = $("#tagbar");
  tb.innerHTML = "";
  /* 收藏过滤 chip（置顶） */
  var favN = 0;
  DATA.items.forEach(function(r){ if (coreMatchNoFav(r) && isFav(r)) favN++; });
  var favChip = document.createElement("span");
  favChip.className = "chip" + (state.fav ? " on" : "");
  favChip.innerHTML = "★ " + UI.fav + "<b>" + favN + "</b>";
  favChip.onclick = function(){ state.fav = !state.fav; render(); };
  tb.appendChild(favChip);
  /* 回收站 chip（计数与视图无关：当前关键词/标签/画幅下的已删除总数） */
  var trashN = 0;
  DATA.items.forEach(function(r){ if (baseMatch(r) && isTrashed(r)) trashN++; });
  var trashChip = document.createElement("span");
  trashChip.className = "chip trashchip" + (state.trash ? " on" : "");
  trashChip.innerHTML = "🗑 " + UI.trash + "<b>" + trashN + "</b>";
  trashChip.onclick = function(){
    state.trash = !state.trash;
    state.fav = false; state.tags = []; state.ar = ""; state.q = ""; $("#q").value = "";
    render();
  };
  tb.appendChild(trashChip);
  /* 标签计数（含手动标签） */
  var counts = {};
  DATA.items.forEach(function(r){
    if (!coreMatch(r)) return;
    tagsOf(r).forEach(function(t){ counts[t] = (counts[t]||0) + 1; });
  });
  /* 标签全集 = 构建时标签 + 手动新增标签 */
  var seen = {}, universe = [];
  DATA.tags.forEach(function(f){ seen[f.t] = 1; universe.push(f.t); });
  Object.keys(userTags).forEach(function(k){
    (userTags[k] || []).forEach(function(t){
      if (!seen[t]){ seen[t] = 1; universe.push(t); }
    });
  });
  universe.sort(function(a, b){
    var ca = counts[a]||0, cb = counts[b]||0;
    return ca !== cb ? cb - ca : (a < b ? -1 : 1);
  });
  universe.forEach(function(t){
    var n = counts[t] || 0;
    if (!n && state.tags.indexOf(t) < 0) return;
    var el = document.createElement("span");
    el.className = "chip" + (state.tags.indexOf(t) >= 0 ? " on" : "");
    el.innerHTML = esc(t) + "<b>" + n + "</b>";
    el.onclick = function(){
      var i = state.tags.indexOf(t);
      if (i >= 0) state.tags.splice(i, 1); else state.tags.push(t);
      render();
    };
    tb.appendChild(el);
  });
  if (state.tags.length){
    var clear = document.createElement("span");
    clear.className = "chip";
    clear.textContent = "× " + UI.all;
    clear.onclick = function(){ state.tags = []; render(); };
    tb.appendChild(clear);
  }
}
/* 不含收藏过滤的核心匹配（用于统计收藏总数） */
function coreMatchNoFav(r){
  var saved = state.fav; state.fav = false;
  var ok = coreMatch(r); state.fav = saved;
  return ok;
}
function renderModels(){
  var mb = $("#modelbar");
  mb.innerHTML = "";
  /* 计数口径跟卡片列表、标签条一致，都用「素材数」（一条提示词 = 一条素材）；
     shard 里的 p 是素材数、n 是图片数，图片数只放进 title 提示，不混进数字。 */
  function chip(val, label, cnt, figs){
    var el = document.createElement("span");
    el.className = "chip" + (state.model === val ? " on" : "");
    el.innerHTML = esc(label) + "<b>" + cnt + "</b>";
    el.title = label + " · " + UI.countImgs.replace("{n}", figs);
    el.onclick = function(){ switchModel(val); };
    mb.appendChild(el);
  }
  var allCnt = 0, allFigs = 0;
  IDX.models.forEach(function(m){ allCnt += m.p || 0; allFigs += m.n || 0; });
  chip("", UI.model + " · " + UI.all, allCnt, allFigs);
  IDX.models.forEach(function(m){ chip(m.key, m.label, m.p || 0, m.n || 0); });
}
function renderAr(){
  var sel = $("#arSel"), counts = {};
  DATA.items.forEach(function(r){
    if (!matches(r)) return;
    r.files.forEach(function(f){ if (f.ar) counts[f.ar] = (counts[f.ar] || 0) + 1; });
  });
  var html = "<option value=''>" + UI.aspect + " · " + UI.all + "</option>";
  DATA.ars.forEach(function(f){
    var n = counts[f.a] || 0;
    if (!n && f.a !== state.ar) return;
    html += "<option value='" + esc(f.a) + "'" + (state.ar === f.a ? " selected" : "")
         +  ">" + esc(f.a) + " (" + n + ")</option>";
  });
  sel.innerHTML = html;
}
function renderCards(){
  var grid = $("#grid"), html = [];
  var matched = [];
  DATA.items.forEach(function(r, i){ if (matches(r)) matched.push(i); });
  var n = matched.length;
  var upto = Math.min(state.shown, n);
  for (var m = 0; m < upto; m++){
    var i = matched[m], r = DATA.items[i], f = curFile(r);
    var chips = [];
    if (r.modelLabel) chips.push("<span class='mini mdl'>" + esc(r.modelLabel) + "</span>");
    tagsOf(r).forEach(function(t){
      chips.push("<span class='mini acc'>" + esc(t) + "</span>");
    });
    paramsOf(r).forEach(function(p){
      chips.push("<span class='mini'>--" + esc(p.k) + " " + esc(p.v) + "</span>");
    });
    /* 多图切换：<=6 张给数字按钮，更多只给 «当前/总数» 徽标（进灯箱切换） */
    var nf = r.files.length, nav = "";
    if (nf > 1 && nf <= 6){
      var btns = [];
      for (var k = 0; k < nf; k++){
        btns.push("<span class='fnum" + (k === r.cover ? " on" : "") + "' data-f='" + k + "'>" +
                  (k + 1) + "</span>");
      }
      nav = "<div class='fnav'>" + btns.join("") + "</div>";
    } else if (nf > 1){
      nav = "<div class='fnav'><span class='fcount'>" + (r.cover + 1) + "/" + nf + "</span></div>";
    }
    var btnTrash = state.trash
      ? "<button class='restorebtn' data-i='" + i + "'>↩ " + esc(UI.restore) + "</button>"
      : "<button class='delbtn' data-i='" + i + "' title='" + esc(UI.del) + "'>✕</button>";
    html.push(
      "<div class='card" + (state.trash ? " trashed" : "") + "' data-i='" + i + "'>" +
      (state.trash ? "" :
        "<button class='favbtn" + (isFav(r) ? " on" : "") + "' data-i='" + i + "' title='" + esc(UI.favTip) + "'>" +
        (isFav(r) ? "★" : "☆") + "</button>") +
      btnTrash +
      "<div class='thumbwrap'>" +
      "<img class='thumb' loading='lazy' src='" + esc(f.thumb || f.file) + "' " +
      "data-full='" + esc(f.file) + "' " +
      /* 少数记录的缩略图在上游就是 404（原图正常），回退到原图，别让卡片碎掉 */
      "onerror=\"this.onerror=null;this.src=this.dataset.full\" " +
      "style='aspect-ratio:" + ratioOf(r) + "' alt='" + esc(r.title) + "'>" + nav + "</div>" +
      "<div class='cbody'><div class='ctitle'>" + esc(r.title) + "</div>" +
      "<div class='cprompt'>" + esc(r.prompt) + "</div>" +
      "<div class='cmeta'>" + chips.join("") + "</div></div></div>");
  }
  grid.innerHTML = html.join("");
  $("#count").innerHTML = UI.count.replace("{n}", "<b>" + n + "</b>");
  var none = n === 0;
  $("#empty").style.display = none ? "block" : "none";
  grid.style.display = none ? "none" : "";
  Array.prototype.forEach.call(grid.children, function(card){
    card.onclick = function(){ openLb(+card.dataset.i); };
  });
  /* 卡片内切图：只换这张卡的图与按钮态，不整页重绘（240 张重绘会闪） */
  Array.prototype.forEach.call(grid.querySelectorAll(".fnum"), function(btn){
    btn.onclick = function(e){
      e.stopPropagation();
      var card = btn.closest(".card"), r = DATA.items[+card.dataset.i];
      r.cover = +btn.dataset.f;
      var f = curFile(r), img = card.querySelector(".thumb");
      img.src = f.thumb || f.file;
      img.style.aspectRatio = ratioOf(r);
      Array.prototype.forEach.call(card.querySelectorAll(".fnum"),
        function(b){ b.classList.toggle("on", b === btn); });
    };
  });
  Array.prototype.forEach.call(grid.querySelectorAll(".favbtn"), function(btn){
    btn.onclick = function(e){
      e.stopPropagation();
      toggleFav(DATA.items[+btn.dataset.i]);
      render();
    };
  });
  Array.prototype.forEach.call(grid.querySelectorAll(".delbtn"), function(btn){
    btn.onclick = function(e){
      e.stopPropagation();
      if (window.confirm(UI.delConfirm)){
        delItem(DATA.items[+btn.dataset.i]);
        render();
      }
    };
  });
  Array.prototype.forEach.call(grid.querySelectorAll(".restorebtn"), function(btn){
    btn.onclick = function(e){
      e.stopPropagation();
      restoreItem(DATA.items[+btn.dataset.i]);
      render();
    };
  });
  /* 增量加载提示（滚动到底自动加载下一批） */
  canMore = n > upto;
  var hint = $("#morehint");
  if (canMore){
    hint.innerHTML = UI.shownMore.replace("{a}", upto).replace("{b}", n);
  } else {
    hint.innerHTML = n > PAGE_SIZE ? UI.allShown.replace("{n}", n) : "";
  }
}
var canMore = false;
var io = new IntersectionObserver(function(entries){
  if (entries[0].isIntersecting && canMore){
    state.shown += PAGE_SIZE;
    renderCards();
  }
});
io.observe($("#sentinel"));
function render(){ state.shown = PAGE_SIZE; renderModels(); renderFacets(); renderAr(); renderCards(); }

var cur = -1;
/* 灯箱内切换同一素材的不同成图 */
function showLbFile(r, idx){
  r.cover = idx;
  var f = curFile(r);
  $("#lbimg").src = f.file;
  $("#lbimg").style.aspectRatio = "";
  Array.prototype.forEach.call(document.querySelectorAll("#lbfiles img"),
    function(im, i){ im.classList.toggle("on", i === idx); });
  syncOwnChip(r);
}
/* 「自制」徽标跟着当前这张图走：同一条素材里上游图与自制图混排 */
function syncOwnChip(r){
  var ow = document.getElementById("lbown");
  if (!ow) return;
  ow.style.display = curFile(r).own ? "" : "none";
}
function openLb(i){
  cur = i;
  var r = DATA.items[i];
  $("#lbtitle").textContent = r.title || "";
  $("#lbprompt").textContent = r.promptRaw || r.rawPrompt || r.prompt || "";
  /* 同一提示词的成图条：一张素材可以有多个版本，灯箱里直接选图1/图2/图3 */
  var box = $("#lbfiles"), nf = r.files.length;
  box.innerHTML = "";
  if (nf > 1){
    r.files.forEach(function(f, k){
      var im = document.createElement("img");
      im.src = f.thumb || f.file;
      im.onerror = function(){ this.onerror = null; this.src = f.file; };
      im.alt = UI.figure + (k + 1);
      im.title = UI.figure + (k + 1);
      im.className = (k === r.cover ? "on" : "") + (f.own ? " own" : "");
      im.onclick = function(){ showLbFile(r, k); };
      box.appendChild(im);
    });
    box.style.display = "";
  } else {
    box.style.display = "none";
  }
  showLbFile(r, r.cover);
  var meta = [];
  meta.push("<span class='mini self' id='lbown' style='display:none' title='" + esc(UI.ownTip) + "'>" +
            esc(UI.own) + "</span>");
  if (r.modelLabel) meta.push("<span class='mini mdl'>" + esc(r.modelLabel) + "</span>");
  tagsOf(r).forEach(function(t){ meta.push("<span class='mini acc'>" + esc(t) + "</span>"); });
  if (r.author) meta.push("<span class='mini'>👤 " + esc(r.author) + "</span>");
  if (r.published) meta.push("<span class='mini'>🗓 " + esc(r.published) + "</span>");
  if (r.sourceUrl) meta.push("<a class='mini srclink' target='_blank' rel='noopener noreferrer' href='" + esc(r.sourceUrl) + "'>" + esc(UI.viewSource) + "</a>");
  paramsOf(r).forEach(function(p){
    meta.push("<span class='mini'>--" + esc(p.k) + " " + esc(p.v) + "</span>");
  });
  $("#lbmeta").innerHTML = meta.join("");
  syncOwnChip(r);
  /* 收藏按钮（回收站视图隐藏） */
  var fb = $("#favBtn");
  fb.style.display = state.trash ? "none" : "";
  fb.classList.toggle("on", isFav(r));
  fb.textContent = isFav(r) ? "★ " + UI.fav : "☆ " + UI.fav;
  /* 删除 / 恢复按钮 */
  var db = $("#delBtn");
  db.textContent = state.trash ? "↩ " + UI.restore : "✕ " + UI.del;
  /* 标签编辑器 */
  renderTagEditor(r);
  var btn = $("#copyBtn");
  btn.classList.remove("ok"); btn.textContent = UI.copy;
  $("#lb").classList.add("open");
  document.body.style.overflow = "hidden";
}
function closeLb(){
  $("#lb").classList.remove("open");
  document.body.style.overflow = "";
  cur = -1;
}
/* —— 标签编辑器：内置标签只读，手动标签可删 —— */
function renderTagEditor(r){
  var box = $("#lbtags");
  box.innerHTML = "";
  var base = r.tags || [];
  var own = userTags[keyOf(r)] || [];
  base.forEach(function(t){
    var el = document.createElement("span");
    el.className = "mini acc";
    el.textContent = t;
    box.appendChild(el);
  });
  own.forEach(function(t){
    var el = document.createElement("span");
    el.className = "mini own";
    el.innerHTML = esc(t) + " <i class='rm' title='" + esc(UI.remove) + "'>×</i>";
    el.querySelector(".rm").onclick = function(){
      own.splice(own.indexOf(t), 1);
      if (own.length) userTags[keyOf(r)] = own; else delete userTags[keyOf(r)];
      lsSet("mj.usertags", userTags);
      renderTagEditor(r);
      render();
    };
    box.appendChild(el);
  });
  var input = document.createElement("input");
  input.id = "taginput";
  input.placeholder = UI.addTag;
  input.autocomplete = "off";
  input.onkeydown = function(e){
    if (e.key === "Enter" || e.key === ","){
      e.preventDefault();
      var v = input.value.trim().replace(/,+$/, "");
      if (!v) return;
      if (tagsOf(r).indexOf(v) >= 0){ input.value = ""; return; }
      userTags[keyOf(r)] = (userTags[keyOf(r)] || []).concat([v]);
      lsSet("mj.usertags", userTags);
      renderTagEditor(r);
      render();
      var ni = $("#taginput");
      if (ni){ ni.focus(); }
    }
  };
  box.appendChild(input);
}
$("#copyBtn").onclick = function(){
  var r = DATA.items[cur]; if (!r) return;
  var text = r.promptRaw || r.rawPrompt || r.prompt || "";
  function done(ok){
    var btn = $("#copyBtn");
    btn.classList.toggle("ok", ok);
    btn.textContent = ok ? UI.copied : UI.copyFail;
    setTimeout(function(){ btn.classList.remove("ok"); btn.textContent = UI.copy; }, 1400);
  }
  if (navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(function(){ done(true); }, function(){ fallback(); });
  } else fallback();
  function fallback(){
    var ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch(e){}
    document.body.removeChild(ta); done(ok);
  }
};
$("#favBtn").onclick = function(){
  var r = DATA.items[cur]; if (!r) return;
  toggleFav(r);
  this.classList.toggle("on", isFav(r));
  this.textContent = isFav(r) ? "★ " + UI.fav : "☆ " + UI.fav;
  render();
};
$("#delBtn").onclick = function(){
  var r = DATA.items[cur]; if (!r) return;
  if (state.trash){
    restoreItem(r);
  } else {
    if (!window.confirm(UI.delConfirm)) return;
    delItem(r);
  }
  this.textContent = state.trash ? "↩ " + UI.restore : "✕ " + UI.del;
  render();
};
$("#lb").onclick = function(e){ if (e.target === this) closeLb(); };
document.addEventListener("keydown", function(e){
  if (e.key === "Escape") return closeLb();
  /* 灯箱里 ←/→ 切换同一素材的图1/图2/图3 */
  if (cur < 0 || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
  var r = DATA.items[cur];
  if (!r || r.files.length < 2) return;
  var next = (r.cover + (e.key === "ArrowRight" ? 1 : -1) + r.files.length) % r.files.length;
  showLbFile(r, next);
  e.preventDefault();
});
$("#q").addEventListener("input", function(){
  state.q = this.value.trim().toLowerCase(); render();
});
$("#arSel").addEventListener("change", function(){
  state.ar = this.value; render();
});
$("#themeBtn").onclick = function(){
  var el = document.documentElement;
  var t = el.dataset.theme === "dark" ? "light" : "dark";
  el.dataset.theme = t;
  try { localStorage.setItem("mj.theme", t); } catch(e){}
  themeLabel();
};
$("#langBtn").onclick = function(){ setLang(lang === "zh" ? "ja" : "zh"); };
/* 落地页通过 #tag=<标签> 带筛选条件打开画廊 */
function applyHash(){
  var m = (location.hash || "").match(/tag=([^&]+)/);
  if (m){
    try { state.tags = [decodeURIComponent(m[1])]; } catch(e){}
  }
}
function themeLabel(){
  var dark = document.documentElement.dataset.theme === "dark";
  $("#themeBtn").textContent = dark ? UI.themeLight : UI.themeDark;
}
applyStatic();
themeLabel();
applyHash();
ensureData();
</script>
</body>
</html>
"""


def shard_payload(rows, extra=None):
    """一个模型的数据分片。

    同一提示词的多张图聚成一条，提示词只存一份：提示词站图片数是提示词数的
    1.5~2.5 倍，不聚合的话两个模型合起来约 170MB，单文件首屏无法接受。
    图片只存 [文件名, 宽, 高, 比例]，路径由分片的 key 拼出。
    键名用单字母是为了再省一层（40k 条记录下键名本身就有 4~5MB）。

    `extra` 是 {originId: [用户图...]}——素材管理器挂上去的成图，追加到 files 末尾
    （采集图永远在前，主图不受影响）。用户图不在 img/<key>/ 下，所以多带两个字段：
    [名, 宽, 高, 比例, 真实路径, 缩略图路径, 1(自制)]。
    """
    groups = {}
    for r in rows:
        gid = r.get("originId") or r["file"]
        g = groups.setdefault(gid, {"row": r, "files": []})
        name = r["file"].rsplit("/", 1)[-1]
        ar = (r.get("params") or {}).get("ar") or ""
        # f[4] 是原图档的展示地址：直连上游时是上游 URL，否则留空由页面按
        # img/<key>/<名> 拼出。页面已有「缩略图失败 → 退回原图」的 onerror，
        # 因此这里不需要页面侧改动。
        g["files"].append([name, r.get("w") or 0, r.get("h") or 0, ar, r.get("file") or ""])

    extra = extra or {}
    for gid, g in groups.items():
        for f in extra.get(gid, []):
            g["files"].append([f["name"], f.get("w") or 0, f.get("h") or 0, f.get("ar") or "",
                               f["file"], f.get("thumb") or "", 1])

    tag_n, ar_n, items = {}, {}, []
    for gid, g in groups.items():
        r = g["row"]
        tags = r.get("tags") or []
        for t in tags:
            tag_n[t] = tag_n.get(t, 0) + 1
        for f in g["files"]:
            if f[3]:
                ar_n[f[3]] = ar_n.get(f[3], 0) + 1
        item = {"i": gid, "t": r.get("title") or gid, "p": r.get("prompt") or ""}
        raw = r.get("promptRaw") or ""
        if raw and raw != item["p"]:          # 与展示文本相同时不重复存
            item["r"] = raw
        if tags:
            item["g"] = tags
        for src, dst in (("author", "a"), ("sourceUrl", "u"), ("published", "d")):
            if r.get(src):
                item[dst] = r[src]
        item["f"] = g["files"]
        items.append(item)

    # 画幅长尾过滤：只保留出现 >=5 次的（站源数据无 --ar，宽高派生出上千种比例）
    ars = [(a, n) for a, n in ar_n.items() if n >= 5]
    return {
        "items": items,
        "tags": [{"t": t, "n": n}
                 for t, n in sorted(tag_n.items(), key=lambda x: (-x[1], x[0]))],
        "ars": [{"a": a, "n": n}
                for a, n in sorted(ars, key=lambda x: (-x[1], x[0]))],
    }


def write_js(path, var_expr, payload):
    """数据外置为 JS 文件：JSON.parse(...) 方式（比对象字面量解析快 ~10 倍，
    万级记录从 20s+ 降到 2-4s）；file:// 双击与 http 均可用。"""
    body = json.dumps(payload, ensure_ascii=False,
                      separators=(",", ":")).replace("</", "<\\/")
    with open(path, "w", encoding="utf-8") as f:
        f.write(var_expr + "=JSON.parse(")
        json.dump(body, f, ensure_ascii=False)
        f.write(");")


def build():
    rows = load_manifest()
    user = load_user_assets()
    user_by_key, orphan = group_user_assets(rows, user)
    if orphan:
        print(f"⚠ {len(orphan)} 条提示词已不在上游数据里，它们挂的用户图不会出现: "
              f"{', '.join(orphan[:5])}{' …' if len(orphan) > 5 else ''}")
    extra_imgs = sum(len(v) for v in user.values()) - sum(
        len(user[g]) for g in orphan)
    if extra_imgs:
        print(f"自制图 {extra_imgs} 张，挂在 {sum(len(v) for v in user_by_key.values())} 条提示词下")
    tag_f, ar_f, model_f = facets(rows)
    # 画幅长尾过滤：只保留出现 >=5 次的（站源数据无 --ar，宽高派生出上千种比例）
    ar_f = [(a, n) for a, n in ar_f if n >= 5]
    items = []
    for r in rows:
        r = dict(r)
        m = (r.get("model") or "").strip()
        r["model"], r["modelLabel"] = m, MODELS.get(m, m)
        # 冗余裁剪：与展示提示词相同的原始文本、未用字段不进页面数据
        if r.get("rawPrompt") == r.get("prompt"):
            r.pop("rawPrompt", None)
        if r.get("promptRaw") == r.get("prompt"):
            r.pop("promptRaw", None)
        if not r.get("params"):
            r.pop("params", None)
        r.pop("originId", None)
        items.append(r)
    ui_json = json.dumps(UI, ensure_ascii=False)

    # 按模型分片：每个模型一份数据文件，进站只加载一个，切模型时才拉另一份
    groups = {}
    for r in rows:
        groups.setdefault(r["key"], []).append(r)
    order = [DEFAULT_MODEL] + [m for m in MODELS if m != DEFAULT_MODEL]

    def rank(key):
        m = groups[key][0].get("model") or ""
        return (order.index(m) if m in order else len(order), -len(groups[key]))

    index_models = []
    for key in sorted(groups, key=rank):
        grp = groups[key]
        payload = shard_payload(grp, user_by_key.get(key))
        payload["key"] = key
        payload["m"] = grp[0].get("model") or key
        payload["label"] = MODELS.get(payload["m"], key)
        shard_path = os.path.join(HERE, GALLERY_SHARD % key)
        write_js(shard_path, f'window.__SHARDS__=window.__SHARDS__||{{}};'
                             f'window.__SHARDS__["{key}"]', payload)
        n_imgs = len(grp) + user_image_count(user_by_key, key)
        index_models.append({
            "key": key,
            "m": grp[0].get("model") or key,
            "label": payload["label"],
            "n": n_imgs,
            "p": len(payload["items"]),
        })
        print(f"  {GALLERY_SHARD % key:<24}{os.path.getsize(shard_path) / 1048576:>7.1f} MB · "
              f"{n_imgs:,} 图 / {len(payload['items']):,} 提示词")

    total_imgs = len(rows) + extra_imgs
    data_out = os.path.join(HERE, GALLERY_JS)
    write_js(data_out, "window.__GALLERY__",
             {"models": index_models, "total": total_imgs,
              "prompts": sum(m["p"] for m in index_models),
              "default": index_models[0]["key"] if index_models else ""})

    html = (TEMPLATE
            .replace("__TITLE__", META["title"])
            .replace("__SUBTITLE__", META["subtitle"])
            .replace("__DESC__", META["desc"])
            .replace("__BRAND__", META["brand"])
            .replace("__ACCENT__", ACCENT)
            .replace("__SITE__", SITE_URL)
            .replace("__SEARCH__", UI["search"])
            .replace("__EMPTY_TITLE__", UI["emptyTitle"])
            .replace("__EMPTY_DESC__", UI["emptyDesc"])
            .replace("__COPY__", UI["copy"])
            .replace("__COUNT_HINT__", UI["countImgs"].replace("{n}", f"{total_imgs:,}"))
            .replace("__ESC_HINT__", UI["escHint"])
            .replace("__FOOTER__", UI["footer"])
            .replace("__UI__", ui_json)
            .replace("__UI_JA__", json.dumps(UI_JA, ensure_ascii=False))
            .replace("__META_ZH__", json.dumps(META, ensure_ascii=False))
            .replace("__META_JA__", json.dumps(META_JA, ensure_ascii=False)))

    # 静态 SEO 块在写入前注入（写完再替换等于没注入）
    by_tag = {}
    for r in items:
        for t in r.get("tags", []):
            by_tag.setdefault(t, []).append(r)
    n_items = len(rows)
    n_prompts = sum(m["p"] for m in index_models)
    models_desc = "、".join(m["label"] for m in index_models)
    links = [(f"cat/{slug}/", f"{tag} ({len(by_tag.get(tag, []))})")
             for slug, tag in SEO_CATEGORIES if len(by_tag.get(tag, [])) >= landing_mod.MIN_ITEMS]
    intro = landing_mod.static_intro(
        [f"提示词生图集收录 YouMind 社区的 AI 生图参考，覆盖 {models_desc}："
         f"共 {n_items:,} 张成图、{n_prompts:,} 条提示词，每条附英文原文与中文翻译。",
         "可按模型、官方分类、标签、画幅与关键词筛选；灯箱内一键复制英文原文提示词，"
         "并保留原作者与来源链接（CC BY 4.0，使用须署名）。"],
        [("图片", f"{n_items:,}"), ("提示词", f"{n_prompts:,}"), ("模型", str(len(index_models))),
         ("提示词语言", "双语（展示中文 / 复制英文原文）")],
        links, SITE["faq"])
    html = html.replace("__SEO_INTRO__", intro) \
               .replace("__SEO_CSS__", landing_mod.SEO_INTRO_CSS) \
               .replace("__FAQ_LD__", landing_mod.faq_ld_script(SITE["faq"]))

    out = os.path.join(HERE, OUTPUT)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    kb = os.path.getsize(out) / 1024
    dk = sum(os.path.getsize(os.path.join(HERE, GALLERY_SHARD % m["key"]))
             for m in index_models) / 1048576
    print(f"✓ {OUTPUT} {kb:.1f} KB · {total_imgs:,} 图 / {n_prompts:,} 提示词 · "
          f"模型 {len(index_models)} 个 · 数据分片合计 {dk:.1f} MB · "
          f"标签 {len(tag_f)} 个 · 画幅 {len(ar_f)} 种")

    landing_urls = build_landing(items, by_tag)
    write_seo_extras(landing_urls)
    print(f"SITE_URL = {SITE_URL}")


if __name__ == "__main__":
    rows = load_manifest()
    if "--check" in sys.argv:
        sys.exit(1 if check(rows) else 0)
    build()
