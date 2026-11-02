# -*- coding: utf-8 -*-
"""构建 AI 模特脸库（中文版）

产出：
  index.html                单文件画廊（数据内嵌，file:// 可直接打开）
  data/portrait-zh.json     中文记录
  data/meta.json            分区 / 发型 / 风格元数据
  data/translations.csv     日⇄中对照表
  robots.txt / sitemap.xml / 404.html

用法：
  SITE_URL=https://your-domain.com python build_gallery.py
"""
import json, os, sys, csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "shared"))
from translations import (HAIR_ZH, HAIR_ORDER, SECTION_ZH, SECTION_NOTE_ZH, SECTION_NOTE_JA,
                          STYLE_ZH, UI, TIPS, RULES, RULES_NOTE, hair_zh, style_zh)
import landing  # noqa: E402
from image_policy import FB_JS, site_entry, tier_addr  # noqa: E402

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rows = json.load(open(os.path.join(root, "manifest.json"), encoding="utf-8"))
ranking = json.load(open(os.path.join(root, "data", "ranking.json"), encoding="utf-8"))

SITE_URL = os.environ.get("SITE_URL", "https://example.com").rstrip("/")

# 取图策略：按档位声明在站点清单里，决定展示地址与回落地址
SITE_CFG = site_entry("portrait")

# ── 组装内嵌数据 ──────────────────────────────────────
items = []
for r in rows:
    item = {
        "i": r["id"],
        "s": r["分区"],
        "hj": r["发型"],
        "hz": hair_zh(r["发型"]),
        "sj": r["风格"],
        "sz": style_zh(r["风格"]),
        "w": r["宽"],
        "h": r["高"],
        "b": r["原图字节"],
    }
    # 取图策略要求的编码（见 shared/image_policy.py）：
    #   <字段>     展示地址（直连上游时是上游 URL，否则是站内相对路径）
    #   <字段>Url  上游地址，仅本地优先时写出，作为加载失败的回落目标
    #   <字段>Path 站内相对路径，仅直连上游时写出，供中图等按路径推导的规则使用
    for tier, fkey in (("thumb", "t"), ("full", "f")):
        path = r[tier + "_path"]
        url = r.get(tier + "_url") or ""
        display, fallback, keep_path = tier_addr(SITE_CFG, tier, path, url)
        item[fkey] = display
        if fallback:
            item[fkey + "Url"] = fallback
        if keep_path:
            item[fkey + "Path"] = path
    items.append(item)

payload = json.dumps({
    "items": items,
    "ui": UI,
    "secNote": {"zh": SECTION_NOTE_ZH, "ja": SECTION_NOTE_JA},
    "hairOrder": HAIR_ORDER,
}, ensure_ascii=False, separators=(",", ":"))

html = r"""<!doctype html>
<html lang="zh-CN" data-theme="light" data-lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>AI 绘画角色脸部一致性参考图库：1499 张 AI 人像，CC0 免费商用 · 人像集</title>
<meta name="description" content="AI 绘画与视频创作的角色脸部一致性参考图库：893 张正面对齐的面部参考 + 606 张完整造型原图，按发型筛选，CC0 协议免费使用。">
<meta name="keywords" content="AI绘画人脸参考,角色脸部一致性,AI人像参考图,发型参考,免费商用人像,CC0人像,face reference,character consistency">
<meta name="author" content="Brilliant666">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="__SITE__/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI 模特脸库">
<meta property="og:title" content="AI 绘画角色脸部参考 · 1499 张 AI 人像，CC0 免费商用">
<meta property="og:description" content="让 AI 生成的角色保持同一张脸。893 张面部参考 + 606 张造型原图，按发型筛选，CC0 免费。">
<meta property="og:url" content="__SITE__/">
<meta property="og:image" content="__SITE__/og-cover.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="zh_CN">
<meta property="og:locale:alternate" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="AI 绘画角色脸部参考 · 1499 张 AI 人像，CC0">
<meta name="twitter:description" content="让 AI 生成的角色保持同一张脸。CC0 免费使用。">
<meta name="twitter:image" content="__SITE__/og-cover.jpg">
<script>
(function(){try{
  var t=localStorage.getItem('pt.theme'); if(t==='light'||t==='dark') document.documentElement.dataset.theme=t;
  var l=localStorage.getItem('pt.lang');  if(l==='zh'||l==='ja')      document.documentElement.dataset.lang=l;
}catch(e){}})();
</script>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='16' fill='%23f6f3ee'/%3E%3Ctext x='16' y='23' font-size='18' font-family='Georgia,serif' font-style='italic' text-anchor='middle' fill='%231d1b19'%3EF%3C/text%3E%3C/svg%3E">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"ImageGallery","name":"AI 模特脸库","alternateName":"AI Model Face Reference","url":"__SITE__/","inLanguage":["zh-CN","ja"],"numberOfItems":1499,"about":"AI 绘画与视频的角色脸部一致性参考","isAccessibleForFree":true,"license":"https://creativecommons.org/publicdomain/zero/1.0/"}
</script>
<style>
:root{
  --bg:#f6f3ee; --paper:#fffdf9; --fg:#1d1b19; --muted:#7a736b; --line:#e6e0d6;
  --accent:#1d1b19; --accent-fg:#fffdf9; --rose:#c98b7f; --radius:14px;
  --serif:"Noto Serif SC","Songti SC","Source Han Serif SC","SimSun",serif;
  --latin:"Cormorant Garamond",Georgia,"Times New Roman",serif;
  --sans:system-ui,-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
}
html[data-theme="dark"]{
  --bg:#151412; --paper:#1d1c1a; --fg:#efe9e1; --muted:#a39b91;
  --line:#2f2c28; --accent:#efe9e1; --accent-fg:#151412; --rose:#d9a294;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--sans);
  line-height:1.7;letter-spacing:.02em;-webkit-font-smoothing:antialiased}
a{color:inherit}
img{max-width:100%}
.wrap{max-width:1280px;margin:0 auto;padding:0 clamp(16px,4vw,48px)}

/* ── 顶栏 ── */
.site-header{position:relative;overflow:hidden}
.site-header::before{content:"";position:absolute;inset:-20% -10% auto auto;width:60vw;height:60vw;
  max-width:760px;max-height:760px;pointer-events:none;
  background:radial-gradient(closest-side,rgba(201,139,127,.18),transparent 70%)}
.topbar{position:relative;display:flex;align-items:center;justify-content:space-between;gap:16px;
  padding-top:22px;padding-bottom:22px}
.brand-wrap{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{display:inline-flex;align-items:center;gap:10px;text-decoration:none}
.brand-mark{width:30px;height:30px;border-radius:50%;border:1px solid var(--fg);
  display:grid;place-items:center;font-family:var(--latin);font-style:italic;font-size:1.05rem;line-height:1}
.brand-text{font-family:var(--latin);font-size:.95rem;letter-spacing:.28em}
.home{display:inline-flex;align-items:center;gap:4px;flex:none;
  font-size:11px;letter-spacing:.06em;color:var(--muted);text-decoration:none;
  border:1px solid var(--line);border-radius:999px;padding:3px 10px 3px 7px;
  transition:color .15s,border-color .15s;white-space:nowrap}
.home:hover{color:var(--fg);border-color:var(--muted)}
.home svg{width:11px;height:11px;display:block}
.nav{display:flex;align-items:center;gap:clamp(12px,2.2vw,26px);font-size:.86rem}
.nav a{text-decoration:none;position:relative;padding:4px 0;background:none;border:0;
  color:inherit;font:inherit;cursor:pointer}
.nav a::after{content:"";position:absolute;left:0;right:0;bottom:0;height:1px;background:currentColor;
  transform:scaleX(0);transform-origin:right;transition:transform .3s ease}
.nav a:hover::after{transform:scaleX(1);transform-origin:left}
.switches{display:flex;gap:8px;align-items:center}
.switch{display:flex;border:1px solid var(--line);border-radius:999px;overflow:hidden;background:var(--paper)}
.switch button{height:32px;min-width:32px;padding:0 11px;border:0;background:transparent;color:var(--muted);
  font:inherit;font-size:12px;cursor:pointer;display:flex;align-items:center;justify-content:center;
  transition:.15s;white-space:nowrap;letter-spacing:.04em}
.switch button+button{border-left:1px solid var(--line)}
.switch button:hover{background:var(--line);color:var(--fg)}
.switch button[aria-pressed="true"]{background:var(--accent);color:var(--accent-fg);font-weight:600}
.switch svg{width:14px;height:14px;display:block}

/* ── Hero ── */
.hero{position:relative;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.05fr);
  gap:clamp(24px,5vw,72px);align-items:center;
  padding-top:clamp(16px,4vw,48px);padding-bottom:clamp(40px,6vw,80px)}
.eyebrow{margin:0 0 18px;display:flex;align-items:center;gap:12px}
.eyebrow span{font-family:var(--latin);font-style:italic;font-size:1.05rem;letter-spacing:.08em;color:var(--rose)}
.eyebrow::before{content:"";width:40px;height:1px;background:var(--rose)}
.hero h1{margin:0 0 20px;font-family:var(--serif);font-weight:500;
  font-size:clamp(2.2rem,5.2vw,3.9rem);line-height:1.16;letter-spacing:.01em}
.lead{margin:0;max-width:32em;color:var(--muted);font-size:clamp(.92rem,1.2vw,1rem);line-height:1.95}
.stats{display:flex;gap:clamp(20px,4vw,44px);margin:30px 0 0;padding:18px 0 0;
  border-top:1px solid var(--line);max-width:30em}
.stats div{margin:0}
.stats dt{font-size:.72rem;color:var(--muted);letter-spacing:.14em}
.stats dd{margin:2px 0 0;font-family:var(--serif);font-size:clamp(1.3rem,2.2vw,1.7rem);font-weight:500}
.cta-row{margin-top:28px;display:flex;flex-wrap:wrap;gap:12px}
.cta{display:inline-flex;align-items:center;gap:10px;text-decoration:none;
  background:var(--accent);color:var(--accent-fg);border-radius:999px;
  padding:13px 28px;font-size:.9rem;letter-spacing:.08em;transition:opacity .2s}
.cta:hover{opacity:.86}
.hero-faces{position:relative;display:grid;grid-template-columns:1.25fr 1fr;
  grid-template-rows:auto auto;gap:clamp(10px,1.4vw,18px);max-width:520px}
.hero-faces img{display:block;width:100%;height:100%;object-fit:cover;
  border-radius:12px;background:var(--line)}
.hero-faces img:nth-child(1){grid-row:span 2;aspect-ratio:3/4.6}
.hero-faces img:nth-child(2){aspect-ratio:4/3.1}
.hero-faces img:nth-child(3){aspect-ratio:4/3.1}

/* 卡片下载按钮 */
.dl{display:inline-flex;align-items:center;gap:4px;text-decoration:none;font-size:.72rem;
  letter-spacing:.08em;color:var(--fg);border:1px solid var(--line);border-radius:999px;
  padding:3px 10px 3px 8px;transition:all .2s ease;flex:none}
.dl:hover{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.dl svg{display:block}

/* ── 通用标题 ── */
.section-title{margin:0;font-family:var(--latin);font-size:clamp(1.4rem,2.4vw,1.9rem);
  letter-spacing:.04em;font-weight:500;display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.section-title span{font-family:var(--sans);font-size:.8rem;letter-spacing:.14em;color:var(--muted)}


/* ── 工具栏 ── */
.toolbar{margin:clamp(32px,5vw,56px) 0 0}
.toolbar-head{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap}
.count{margin:0;font-size:.84rem;color:var(--muted);letter-spacing:.06em;font-variant-numeric:tabular-nums}
.sections{display:inline-flex;align-self:flex-start;gap:4px;padding:4px;margin:18px 0 0;
  background:var(--paper);border:1px solid var(--line);border-radius:999px;max-width:100%}
.seg{flex:1 1 auto;display:inline-flex;align-items:baseline;gap:8px;cursor:pointer;
  font:inherit;color:var(--muted);background:transparent;border:0;border-radius:999px;
  padding:9px 20px;transition:.18s;white-space:nowrap}
.seg:hover{color:var(--fg)}
.seg[aria-selected="true"]{background:var(--accent);color:var(--accent-fg)}
.seg-en{font-family:var(--latin);font-style:italic;font-size:1.15rem;letter-spacing:.03em;line-height:1}
.seg-ja{font-size:.8rem;letter-spacing:.1em}
.seg small{font-size:.72rem;opacity:.65;font-variant-numeric:tabular-nums}
.sec-note{margin:14px 0 0;font-size:.84rem;color:var(--muted);line-height:1.8}
.filters{display:flex;gap:8px;overflow-x:auto;margin:16px 0 0;padding-bottom:2px;scrollbar-width:none}
.filters::-webkit-scrollbar{display:none}
.chip{flex:none;font:inherit;font-size:.86rem;cursor:pointer;letter-spacing:.06em;
  background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:999px;
  padding:6px 16px;transition:.18s}
.chip:hover{border-color:var(--fg)}
.chip[aria-pressed="true"]{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
.chip small{font-size:.72rem;opacity:.6;margin-left:6px;font-variant-numeric:tabular-nums}

/* ── 网格 ── */
.grid{list-style:none;margin:22px 0 0;padding:0;display:grid;
  grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:clamp(12px,1.6vw,22px)}
.card{display:flex;flex-direction:column;gap:8px}
.thumb-btn{padding:0;border:0;background:var(--line);cursor:zoom-in;display:block;width:100%;
  border-radius:var(--radius);overflow:hidden;position:relative;line-height:0}
.card img{display:block;width:100%;height:auto;transition:transform .6s cubic-bezier(.2,.7,.2,1),
  opacity .35s ease;opacity:0}
.card img.ld{opacity:1}
.thumb-btn::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(to top,rgba(0,0,0,.18),transparent 40%);
  opacity:0;transition:opacity .3s ease}
.card:hover img{transform:scale(1.04)}
.card:hover .thumb-btn::after{opacity:1}
.card .meta{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:0 2px}
.card .label{font-size:.74rem;color:var(--muted);letter-spacing:.1em;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.empty{margin:40px 0;text-align:center;color:var(--muted);font-size:.9rem}
.empty[hidden]{display:none}
.more-wrap{display:flex;justify-content:center;margin:34px 0 0}
.btn{font:inherit;font-size:.88rem;letter-spacing:.08em;cursor:pointer;
  background:transparent;color:var(--fg);border:1px solid var(--fg);
  border-radius:999px;padding:12px 32px;transition:.2s}
.btn:hover{background:var(--fg);color:var(--bg)}
.btn[hidden]{display:none}
#sentinel{height:1px}

/* ── 页脚 ── */
.site-footer{margin:clamp(48px,7vw,84px) 0 0;padding:26px 0 40px;border-top:1px solid var(--line);
  font-size:.8rem;color:var(--muted);letter-spacing:.06em}
.site-footer .wrap{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.site-footer a{text-decoration:none;border-bottom:1px solid var(--line)}
.site-footer a:hover{border-color:var(--fg)}

/* ── 灯箱 ── */
.lightbox{position:fixed;inset:0;z-index:100;background:rgba(18,16,14,.94);
  display:flex;align-items:center;justify-content:center}
.lightbox[hidden]{display:none}
.lb-figure{margin:0;max-width:92vw;max-height:94vh;display:flex;flex-direction:column;
  align-items:center;gap:14px}
/* 舞台按原图比例精确贴合画面，两层都铺满它：
   底层 blur 溢出的部分会被舞台裁掉，淡入结束隐藏底层时边缘不会跳 */
.lb-stage{position:relative;overflow:hidden;border-radius:10px;
  max-width:92vw;max-height:calc(94vh - 72px)}
.lb-stage img{position:absolute;inset:0;width:100%;height:100%;
  object-fit:contain;display:block}
/* 底层清晰缩略图垫底，中图加载完淡入（不加 blur：缩略图放大 1.5 倍仍可辨认，糊成一片反而像没加载） */
/* transform 会创建层叠上下文，会盖住未定位的 .hi —— 必须显式定层序 */
.lb-stage .lo{z-index:1}
.lb-stage .hi{opacity:0;transition:opacity .32s ease;z-index:2}
.lb-stage .hi.rd{opacity:1}
/* 换图时瞬间隐藏上一张，不走淡出 */
.lb-stage .hi.nt{transition:none}
.lb-figure figcaption{display:flex;align-items:center;gap:16px;color:#eee;
  font-size:.86rem;letter-spacing:.06em;flex-wrap:wrap;justify-content:center}
.lb-btn{position:absolute;background:rgba(255,255,255,.1);border:0;color:#fff;
  width:46px;height:46px;border-radius:50%;cursor:pointer;font-size:1.3rem;
  display:grid;place-items:center;transition:.18s}
.lb-btn:hover{background:rgba(255,255,255,.22)}
.lb-close{top:18px;right:18px}
.lb-prev{left:18px;top:50%;transform:translateY(-50%)}
.lb-next{right:18px;top:50%;transform:translateY(-50%)}
.btn-primary{background:#fff;color:#151412;border:0;border-radius:999px;
  padding:8px 20px;font-size:.82rem;text-decoration:none;letter-spacing:.06em}
.btn-primary:hover{opacity:.86}
.btn-ghost{background:transparent;color:#e6e2dc;border:1px solid rgba(255,255,255,.28);
  border-radius:999px;padding:8px 18px;font-size:.82rem;text-decoration:none;
  letter-spacing:.06em;cursor:pointer;font-family:inherit;transition:.18s}
.btn-ghost:hover{border-color:#fff;color:#fff}
.lb-note{color:#9a9a9a;font-size:.76rem}

@media (max-width:860px){
  .hero{grid-template-columns:1fr}
  .hero-faces{order:-1;grid-template-columns:repeat(4,1fr)}
  .hero-faces img:nth-child(n+5){display:none}
}
@media (max-width:560px){
  .grid{grid-template-columns:repeat(2,1fr)}
  .rank-list{grid-template-columns:repeat(3,1fr)}
  .lb-prev{left:8px}.lb-next{right:8px}
}
/* 320~400px：品牌行 + 开关挤在一行会溢出，改为换行；分区切换允许横向滚动 */
@media (max-width:520px){
  .topbar{flex-wrap:wrap;row-gap:12px}
  .nav{margin-left:auto}
  .sections{overflow-x:auto;scrollbar-width:none}
  .sections::-webkit-scrollbar{display:none}
  .seg{padding:9px 14px}
}
</style>
<style>__SEO_CSS__.seo-intro{--si-max:1280px}</style>
__FAQ_LD__
__FB_JS__
</head>
<body>

<header class="site-header">
  <div class="wrap topbar">
    <div class="brand-wrap">
      <a class="brand" href="../" aria-label="返回参考素材库首页">
        <span class="brand-mark">F</span><span class="brand-text">FACE&nbsp;REFERENCE</span>
      </a>
      <a class="home" href="../"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg><span data-t="home">参考素材库</span></a>
    </div>
    <nav class="nav" aria-label="菜单">
      <div class="switches">
        <div class="switch" id="themeSw" role="group" aria-label="主题">
          <button type="button" data-t="light" title="Light" aria-label="Light"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></svg></button>
          <button type="button" data-t="dark" title="Dark" aria-label="Dark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
        </div>
        <div class="switch" id="langSw" role="group" aria-label="语言">
          <button type="button" data-l="zh">中文</button>
          <button type="button" data-l="ja">日本語</button>
        </div>
      </div>
    </nav>
  </div>

  <section class="wrap hero">
    <div class="hero-copy">
      <p class="eyebrow"><span data-t="eyebrow">免费人脸参考图库</span></p>
      <h1><span data-t="h1a">AI 模特</span><br><span data-t="h1b">脸库</span></h1>
      <p class="lead" data-t="lead"></p>
      <dl class="stats">
        <div><dt data-t="statFace">面部</dt><dd id="stat-face">—</dd></div>
        <div><dt data-t="statStyling">造型</dt><dd id="stat-styling">—</dd></div>
        <div><dt data-t="statLicense">许可</dt><dd>CC0</dd></div>
      </dl>
      <div class="cta-row">
        <a class="cta" href="#gallery"><span data-t="cta">查看图库</span><span aria-hidden="true">→</span></a>
      </div>
    </div>
    <div id="hero-faces" class="hero-faces" aria-hidden="true"></div>
  </section>
</header>

<main class="wrap" id="gallery">
  <div class="toolbar">
    <div class="toolbar-head">
      <h2 class="section-title"><span data-t="galleryTitle">图库</span><span data-t="gallerySub">按发型筛选</span></h2>
      <p id="count" class="count" aria-live="polite"></p>
    </div>
    <div id="sections" class="sections" role="tablist" aria-label="分区">
      <button type="button" class="seg" role="tab" data-sec="face" aria-controls="grid">
        <span class="seg-en">Face</span><span class="seg-ja" id="seg-face">面部</span><small id="n-face"></small>
      </button>
      <button type="button" class="seg" role="tab" data-sec="styling" aria-controls="grid">
        <span class="seg-en">Styling</span><span class="seg-ja" id="seg-styling">造型</span><small id="n-styling"></small>
      </button>
    </div>
    <p id="sec-note" class="sec-note"></p>
    <div id="filters" class="filters" role="group" aria-label="按发型筛选"></div>
  </div>

  <ul id="grid" class="grid"></ul>
  <p id="empty" class="empty" hidden></p>
  <div class="more-wrap"><button id="more" class="btn" type="button" hidden></button></div>
  <div id="sentinel" aria-hidden="true"></div>
</main>

<footer class="site-footer">
  <div class="wrap">
    <span>原站：<a href="https://ai-portrait-gallery.pages.dev/" target="_blank" rel="noopener">AIモデル顔データベース</a></span>
    <span>／</span>
    <span>作者：<a href="https://x.com/agi_aibusi" target="_blank" rel="noopener">あぎ</a></span>
    <span>／</span>
    <span>CC0 1.0</span>
  </div>
</footer>
__SEO_INTRO__

<div id="lightbox" class="lightbox" role="dialog" aria-modal="true" aria-label="图片预览" hidden>
  <button id="lb-close" class="lb-btn lb-close" type="button" aria-label="关闭">×</button>
  <button id="lb-prev" class="lb-btn lb-prev" type="button" aria-label="上一张">‹</button>
  <button id="lb-next" class="lb-btn lb-next" type="button" aria-label="下一张">›</button>
  <figure class="lb-figure">
    <div class="lb-stage" id="lb-stage">
      <img id="lb-img-lo" class="lo" alt="" aria-hidden="true">
      <img id="lb-img" class="hi" alt="">
    </div>
    <figcaption>
      <span id="lb-label"></span>
      <a id="lb-dl" class="btn-primary" href="#" download>下载原图</a>
      <a id="lb-full" class="btn-ghost" href="#" target="_blank" rel="noopener">打开原寸 PNG</a>
      <button id="lb-copy" class="btn-ghost" type="button">复制图片链接</button>
      <span class="lb-note" id="lb-note"></span>
    </figcaption>
  </figure>
</div>

<script>
const DB = __PAYLOAD__;
const ITEMS = DB.items;
const UI = DB.ui;
const HAIRS = DB.hairOrder;
const PAGE = 60;

let LANG  = document.documentElement.dataset.lang  || 'zh';
let THEME = document.documentElement.dataset.theme || 'light';
const S = { sec: 'face', hair: 'all', n: PAGE };

const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const t = k => UI[LANG][k] || k;
const hairName = it => LANG === 'ja' ? it.hj : it.hz;
const styleName = it => LANG === 'ja' ? it.sj : it.sz;
const labelOf = it => { const s = styleName(it); return s ? hairName(it) + '・' + s : hairName(it); };
const fmt = n => Number(n).toLocaleString('zh-CN');
const mb = b => (b / 1048576).toFixed(1) + ' MB';
const dlName = it => (it.s === 'face' ? 'ai-face-' : 'ai-styling-') + it.i + '.png';

const grid = $('#grid'), countEl = $('#count'), moreEl = $('#more'), emptyEl = $('#empty');

/* ── 语言 ── */
function applyStatic(){
  document.documentElement.lang = LANG === 'ja' ? 'ja' : 'zh-CN';
  document.documentElement.dataset.lang = LANG;
  document.title = UI[LANG].title;
  document.querySelectorAll('[data-t]').forEach(el => {
    const k = el.dataset.t;
    if (UI[LANG][k] !== undefined) el.textContent = UI[LANG][k];
  });
  $('#seg-face').textContent = LANG === 'ja' ? 'フェイス' : '面部';
  $('#seg-styling').textContent = LANG === 'ja' ? 'スタイリング' : '造型';
  document.querySelectorAll('#themeSw button').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.t === THEME ? 'true' : 'false'));
  document.querySelectorAll('#langSw button').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.l === LANG ? 'true' : 'false'));
  $('#lb-dl').textContent = t('download');
  $('#lb-full').textContent = t('openFull');
  $('#lb-copy').textContent = t('copyLink');
  $('#lb-close').setAttribute('aria-label', t('close'));
  $('#lb-prev').setAttribute('aria-label', t('prev'));
  $('#lb-next').setAttribute('aria-label', t('next'));
}

/* ── 筛选 ── */
function pool(){ return ITEMS.filter(it => it.s === S.sec); }
function view(){
  const p = pool();
  return S.hair === 'all' ? p : p.filter(it => it.hj === S.hair);
}
function counts(){
  const c = { all: pool().length };
  HAIRS.forEach(h => c[h] = 0);
  pool().forEach(it => { if (c[it.hj] !== undefined) c[it.hj]++; });
  return c;
}

function drawSections(){
  document.querySelectorAll('.seg').forEach(b => {
    const on = b.dataset.sec === S.sec;
    b.setAttribute('aria-selected', on ? 'true' : 'false');
    b.setAttribute('tabindex', on ? '0' : '-1');
  });
  $('#n-face').textContent = ITEMS.filter(i => i.s === 'face').length;
  $('#n-styling').textContent = ITEMS.filter(i => i.s === 'styling').length;
  $('#sec-note').textContent = DB.secNote[LANG][S.sec] || '';
}

function drawFilters(){
  const c = counts();
  const list = [['all', c.all]].concat(
    HAIRS.filter(h => c[h] > 0).map(h => [h, c[h]])
  );
  $('#filters').innerHTML = list.map(([v, n]) =>
    '<button type="button" class="chip" data-hair="' + esc(v) + '" aria-pressed="' + (S.hair === v) + '">' +
    esc(v === 'all' ? t('all') : (LANG === 'ja' ? v : hairZhOf(v))) +
    '<small>' + fmt(n) + '</small></button>'
  ).join('');
}
function hairZhOf(h){
  const it = ITEMS.find(i => i.hj === h);
  return it ? it.hz : h;
}

/* ── 卡片 ── */
const DL_ICON = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">' +
  '<path d="M12 4v11m0 0l-4.5-4.5M12 15l4.5-4.5M5 19.5h14" fill="none" stroke="currentColor" ' +
  'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function card(it, i){
  const hair = LANG === 'ja' ? it.hj : it.hz;
  return '<li class="card" data-i="' + i + '">' +
    '<button class="thumb-btn" type="button" aria-label="' + esc(labelOf(it)) + '">' +
      '<img loading="lazy" decoding="async" src="' + esc(it.t) + '"' + (it.tUrl ? ' data-fb="' + esc(it.tUrl) + '"' : '') + ' alt="' + esc(labelOf(it)) + '">' +
    '</button>' +
    '<div class="meta"><span class="label">' + esc(hair) + '</span>' +
      '<a class="dl" href="' + esc(it.f) + '" download="' + esc(dlName(it)) + '"' +
        ' title="PNG ' + mb(it.b) + '" aria-label="下载 PNG（' + mb(it.b) + '）">' +
        DL_ICON + '<span>PNG</span></a></div></li>';
}

let VIEW = [];
function draw(){
  VIEW = view();
  countEl.textContent = fmt(VIEW.length) + ' ' + t('countUnit');
  if (!VIEW.length){
    grid.innerHTML = '';
    emptyEl.hidden = false;
    emptyEl.textContent = t('empty');
    moreEl.hidden = true;
    return;
  }
  emptyEl.hidden = true;
  S.n = PAGE;
  grid.innerHTML = VIEW.slice(0, S.n).map(card).join('');
  sweep(); syncMore();
}
function addMore(){
  if (S.n >= VIEW.length) return;
  const from = S.n;
  S.n = Math.min(S.n + PAGE, VIEW.length);
  grid.insertAdjacentHTML('beforeend', VIEW.slice(from, S.n).map((it, k) => card(it, from + k)).join(''));
  sweep(); syncMore();
}
function sweep(){ grid.querySelectorAll('img').forEach(im => { if (im.complete) im.classList.add('ld'); }); }
function syncMore(){
  const rest = VIEW.length - S.n;
  moreEl.hidden = rest <= 0;
  moreEl.textContent = t('more') + '（' + fmt(rest) + '）';
}

/* ── 灯箱 ── */
let LB = { list: [], idx: 0, last: null };
let loT = 0;   // 底层模糊图隐藏定时器，连翻时需可取消
// img/x.png → mid/x.webp，规则与 tools/mid.py 的 mid_rel() 一致
const midOf = f => (f||'').replace(/^img\//, 'mid/').replace(/\.[^./]+$/, '.webp');
// 预取中图：悬停/按下卡片时先下载，打开灯箱后预取前后各一张。
// 只留最近几个 Image 引用，下载完的字节留在 HTTP 缓存里，不长期占解码内存。
const warmed = new Set(), warmRefs = [];
function warm(u){
  if (!u || warmed.has(u)) return;
  warmed.add(u);
  const im = new Image(); im.decoding = 'async'; im.src = u;
  warmRefs.push(im); if (warmRefs.length > 6) warmRefs.shift();
}

// 把舞台缩到原图 contain 后的真实矩形：两层完全重合，底层 blur 的外溢被舞台裁掉。
// 上限沿用 CSS 的 max-width / max-height，避免两处数字各写一遍。
function fitLbStage(){
  const stage = $('#lb-stage'), lo = $('#lb-img-lo');
  const cs = getComputedStyle(stage);
  const availW = parseFloat(cs.maxWidth), availH = parseFloat(cs.maxHeight);
  if (!availW || !availH) return;
  const nw = lo.naturalWidth || 400, nh = lo.naturalHeight || 500;   // 本站缩略图 400x500
  const s = Math.min(availW / nw, availH / nh);
  stage.style.width = Math.round(nw * s) + 'px';
  stage.style.height = Math.round(nh * s) + 'px';
}
addEventListener('resize', () => { if (!$('#lightbox').hidden) fitLbStage(); });
function openLb(it, list){
  LB.list = list && list.length ? list : VIEW;
  LB.idx = Math.max(0, LB.list.indexOf(it));
  LB.last = document.activeElement;
  $('#lightbox').hidden = false;
  document.body.style.overflow = 'hidden';
  showLb();
}
function showLb(){
  const it = LB.list[LB.idx];
  if (!it) return;
  const img = $('#lb-img'), lo = $('#lb-img-lo');
  // 先瞬间隐藏上一张高清层，否则它会在新图上淡出 0.32 秒
  img.onload = img.onerror = null;
  img.classList.add('nt'); img.classList.remove('rd'); void img.offsetWidth; img.classList.remove('nt');
  // 双层：缩略图垫底，中图加载完淡入
  lo.src = it.t;
  // 舞台尺寸跟着缩略图比例走（缩略图与原图同比例，误差 <0.1%）
  fitLbStage();
  lo.onload = fitLbStage;
  img.alt = labelOf(it);
  $('#lb-label').textContent = labelOf(it) + '　' + it.w + '×' + it.h;
  const dl = $('#lb-dl');
  dl.href = it.f;
  // 直连上游时 download 属性跨源无效，改为新标签打开
  dl.target = /^https?:/.test(it.f) ? '_blank' : '';
  // 直连上游时 download 属性跨源无效，改为新标签打开
  dl.target = /^https?:/.test(it.f) ? '_blank' : '';
  dl.setAttribute('download', it.i + '.png');
  $('#lb-full').href = it.f;
  $('#lb-note').textContent = '';
  lo.style.opacity = '1';
  const settle = () => {
    img.classList.add('rd');
    // 淡入完成后收起底层。舞台已把 blur 外溢裁掉，这一步在视觉上无变化
    clearTimeout(loT);
    loT = setTimeout(() => { lo.style.opacity = '0'; }, 340);
  };
  img.onload = settle;
  // 灯箱用中图（tools/mid.py 生成，约为原图的 1/30）；没有中图时退回原图
  img.onerror = () => {
    img.onerror = () => { $('#lb-note').textContent = LANG === 'ja' ? '（原寸未取得）' : '（原图未下载）'; };
    img.src = it.f;
  };
  img.src = midOf(it.fPath || it.f);
  if (img.complete && img.naturalWidth) settle();
  [LB.list[LB.idx + 1], LB.list[LB.idx - 1]].forEach(n => n && warm(midOf(n.fPath || n.f)));
  $('#lb-prev').style.visibility = LB.idx > 0 ? 'visible' : 'hidden';
  $('#lb-next').style.visibility = LB.idx < LB.list.length - 1 ? 'visible' : 'hidden';
}
function closeLb(){
  $('#lightbox').hidden = true;
  document.body.style.overflow = '';
  if (LB.last) LB.last.focus();
}
function stepLb(d){
  const n = LB.idx + d;
  if (n < 0 || n >= LB.list.length) return;
  LB.idx = n; showLb();
}

/* ── 事件 ── */
document.addEventListener('load', e => {
  if (e.target.tagName === 'IMG') e.target.classList.add('ld');
}, true);
document.addEventListener('error', e => {
  if (e.target.tagName === 'IMG') e.target.classList.add('ld');
}, true);

grid.addEventListener('click', e => {
  const b = e.target.closest('.thumb-btn'); if (!b) return;
  const li = b.closest('.card');
  const it = VIEW[+li.dataset.i];
  if (it) openLb(it, VIEW);
});
// 悬停 120ms 后预取（划过网格不触发），按下立即预取（触屏比 click 早约 100ms）
let hoverT = 0;
const cardItem = e => { const li = e.target.closest('.card'); return li && VIEW[+li.dataset.i]; };
grid.addEventListener('pointerover', e => {
  const it = cardItem(e); clearTimeout(hoverT);
  if (it) hoverT = setTimeout(() => warm(midOf(it.fPath || it.f)), 120);
});
grid.addEventListener('pointerout', () => clearTimeout(hoverT));
grid.addEventListener('pointerdown', e => { const it = cardItem(e); if (it) warm(midOf(it.fPath || it.f)); });
grid.addEventListener('focusin', e => { const it = cardItem(e); if (it) warm(midOf(it.fPath || it.f)); });
$('#more').addEventListener('click', addMore);
if ('IntersectionObserver' in window){
  new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) addMore(); },
    { rootMargin: '800px' }).observe($('#sentinel'));
}

$('#sections').addEventListener('click', e => {
  const b = e.target.closest('[data-sec]'); if (!b) return;
  S.sec = b.dataset.sec; S.hair = 'all';
  drawSections(); drawFilters(); draw(); writeHash();
});
$('#filters').addEventListener('click', e => {
  const b = e.target.closest('[data-hair]'); if (!b) return;
  S.hair = b.dataset.hair;
  drawFilters(); draw(); writeHash();
});
$('#langSw').addEventListener('click', e => {
  const b = e.target.closest('[data-l]'); if (!b || b.dataset.l === LANG) return;
  LANG = b.dataset.l;
  try { localStorage.setItem('pt.lang', LANG); } catch(_){}
  document.documentElement.dataset.lang = LANG;
  applyStatic(); drawSections(); drawFilters(); draw();
  if (!$('#lightbox').hidden) showLb();
});

$('#themeSw').addEventListener('click', e => {
  const b = e.target.closest('[data-t]'); if (!b || b.dataset.t === THEME) return;
  THEME = b.dataset.t;
  try { localStorage.setItem('pt.theme', THEME); } catch(_){}
  document.documentElement.dataset.theme = THEME;
  applyStatic();
});

$('#lb-close').addEventListener('click', closeLb);
$('#lb-copy').addEventListener('click', function(){
  const it = LB.list[LB.idx]; if (!it) return;
  // 复制完整 URL（相对路径粘到浏览器/聊天窗口都用不了）
  const url = new URL(it.f, location.href).href;
  const btn = this;
  const done = ok => {
    btn.textContent = ok ? t('copied') : t('copyFail');
    setTimeout(() => { btn.textContent = t('copyLink'); }, 1400);
  };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(() => done(true)).catch(() => done(false));
  } else { done(false); }
});
$('#lb-prev').addEventListener('click', () => stepLb(-1));
$('#lb-next').addEventListener('click', () => stepLb(1));
$('#lightbox').addEventListener('click', e => { if (e.target.id === 'lightbox') closeLb(); });
document.addEventListener('keydown', e => {
  if ($('#lightbox').hidden) return;
  if (e.key === 'Escape') closeLb();
  else if (e.key === 'ArrowLeft') stepLb(-1);
  else if (e.key === 'ArrowRight') stepLb(1);
});

/* ── hash 路由 ── */
function writeHash(){
  const p = [];
  if (S.sec !== 'face') p.push('sec=' + S.sec);
  if (S.hair !== 'all') p.push('hair=' + encodeURIComponent(S.hair));
  const h = p.length ? '#' + p.join('&') : '';
  history.replaceState(null, '', h || location.pathname + location.search);
}
function readHash(){
  const m = /(?:^#|&)sec=([^&]*)/.exec(location.hash);
  if (m && ['face','styling'].includes(m[1])) S.sec = m[1];
  const h = /(?:^#|&)hair=([^&]*)/.exec(location.hash);
  if (h){
    try { const v = decodeURIComponent(h[1]); if (HAIRS.includes(v)) S.hair = v; } catch(_){}
  }
}

/* ── 首屏 ── */
// 首屏配图：人工挑选的三张，左侧竖图 + 右侧两张横图
const HERO_IDS = ['f054e7f9079', 'f02920397d9', 'f16f760d705'];

function drawHero(){
  const byId = id => ITEMS.find(i => i.i === id);
  let pick = HERO_IDS.map(byId).filter(Boolean);
  // 兜底：ID 缺失时按比例取样，保证首屏永远有三张
  if (pick.length < 3){
    const face = ITEMS.filter(i => i.s === 'face');
    const at = p => face[Math.floor(face.length * p)] || face[0];
    pick = pick.concat([at(0.3), at(0.6), at(0.8)]).filter(Boolean).slice(0, 3);
  }
  $('#hero-faces').innerHTML = pick.slice(0, 3).map(it =>
    '<img loading="eager" decoding="async" src="' + esc(it.t) + '"' + (it.tUrl ? ' data-fb="' + esc(it.tUrl) + '"' : '') + ' alt="">').join('');
  const face = ITEMS.filter(i => i.s === 'face');
  const sty  = ITEMS.filter(i => i.s === 'styling');
  $('#stat-face').textContent = fmt(face.length);
  $('#stat-styling').textContent = fmt(sty.length);
}

applyStatic();
readHash();
drawHero();
drawSections();
drawFilters();
draw();
</script>
</body>
</html>"""

# 静态落地页（分区、分区 × 发型、发型风格）与主页里不依赖 JS 的介绍、FAQ
import seo  # noqa: E402
landing_urls, seo_intro, FAQ = seo.build(root, SITE_URL, items)
html = (html.replace("__SEO_INTRO__", seo_intro).replace("__SEO_CSS__", landing.SEO_INTRO_CSS)
            .replace("__FAQ_LD__", landing.faq_ld_script(FAQ)))

html = html.replace("__FB_JS__", FB_JS).replace("__PAYLOAD__", payload).replace("__SITE__", SITE_URL)
out = os.path.join(root, "index.html")
open(out, "w", encoding="utf-8").write(html)
print("wrote index.html %.1f KB" % (os.path.getsize(out) / 1024))
print("items:", len(items), "| face:", sum(1 for i in items if i["s"] == "face"),
      "| styling:", sum(1 for i in items if i["s"] == "styling"))
print("SITE_URL =", SITE_URL)

# ── 导出数据 ──────────────────────────────────────────
data_dir = os.path.join(root, "data")
zh = []
for it in items:
    zh.append({
        "id": it["i"], "分区": it["s"], "分区_zh": SECTION_ZH.get(it["s"], it["s"]),
        "发型": it["hj"], "发型_zh": it["hz"],
        "风格": it["sj"], "风格_zh": it["sz"],
        "宽": it["w"], "高": it["h"],
        "缩略图": it["t"], "原图": it["f"],
    })
json.dump(zh, open(os.path.join(data_dir, "portrait-zh.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

meta = {
    "site": "AI PORTRAIT / FACE REFERENCE",
    "source": "https://ai-portrait-gallery.pages.dev/",
    "author": "あぎ (@agi_aibusi)",
    "license": "CC0 1.0",
    "items": len(items),
    "face": sum(1 for i in items if i["s"] == "face"),
    "styling": sum(1 for i in items if i["s"] == "styling"),
    "分区": [{"key": k, "zh": v} for k, v in SECTION_ZH.items()],
    "发型": [{"ja": h, "zh": HAIR_ZH[h], "count": sum(1 for i in items if i["hj"] == h)}
             for h in HAIR_ORDER if any(i["hj"] == h for i in items)],
    "风格数": len({i["sj"] for i in items if i["sj"]}),
}
json.dump(meta, open(os.path.join(data_dir, "meta.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

with open(os.path.join(data_dir, "translations.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["字段", "日文原文", "中文译文"])
    for k, v in SECTION_ZH.items():
        w.writerow(["section", k, v])
    for k, v in HAIR_ZH.items():
        w.writerow(["hair", k, v])
    for k, v in STYLE_ZH.items():
        w.writerow(["style", k, v])
print("wrote data/portrait-zh.json, data/meta.json, data/translations.csv")

# ── SEO 附属 ──────────────────────────────────────────
with open(os.path.join(root, "robots.txt"), "w", encoding="utf-8") as f:
    f.write("User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE_URL)
landing.sitemap(SITE_URL, landing_urls, os.path.join(root, "sitemap.xml"))
with open(os.path.join(root, "404.html"), "w", encoding="utf-8") as f:
    f.write("""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>404 · 页面不存在</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='16' fill='%23f6f3ee'/%3E%3Ctext x='16' y='23' font-size='18' font-family='Georgia,serif' font-style='italic' text-anchor='middle' fill='%231d1b19'%3EF%3C/text%3E%3C/svg%3E">
<style>
html,body{margin:0;height:100%%}
body{background:#f6f3ee;color:#1d1b19;font-family:system-ui,"PingFang SC","Microsoft YaHei",sans-serif;
  display:flex;align-items:center;justify-content:center;text-align:center}
.box{padding:24px}
h1{margin:0 0 10px;font-family:Georgia,serif;font-style:italic;font-size:64px;font-weight:500;color:#c98b7f}
p{margin:0 0 22px;color:#7a736b;font-size:14px;line-height:1.9}
a{display:inline-flex;align-items:center;height:42px;padding:0 24px;border-radius:999px;
  background:#1d1b19;color:#fffdf9;font-size:13.5px;text-decoration:none}
</style></head>
<body><div class="box">
<h1>404</h1>
<p>页面不存在，或链接已失效。<br>Page not found.</p>
<a href="/">返回首页</a>
</div></body></html>
""")
print("wrote robots.txt, sitemap.xml, 404.html")
