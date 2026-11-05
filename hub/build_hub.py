# -*- coding: utf-8 -*-
"""生成资源站入口页

用法:
  python build_hub.py                # 读取 sites.json → index.html
  python build_hub.py --check        # 仅检查封面图是否存在

新增站点：在 sites.json 的 sites 数组里追加一条，重跑本脚本即可。
"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared"))
import landing  # noqa: E402

HUB  = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HUB)
CFG  = os.path.join(ROOT, "sites.json")
OUT  = os.path.join(HUB, "index.html")

LICENSE_LABEL = {
    "cc0":        {"zh": "CC0", "ja": "CC0", "cls": "ok"},
    "conditional": {"zh": "有条件", "ja": "条件付き", "cls": "warn"},
    "restricted": {"zh": "禁止再分发", "ja": "再配布禁止", "cls": "no"},
}


def load():
    with open(CFG, encoding="utf-8") as f:
        return json.load(f)


def check(cfg):
    """封面图存在性检查。缺失时给出警告但不中断。"""
    bad = 0
    for s in cfg["sites"]:
        p = os.path.join(ROOT, "sites", s["id"], s["cover"])
        if not os.path.exists(p):
            print(f"  ✗ {s['code']:16s} 封面缺失: {s['cover']}")
            bad += 1
        else:
            kb = os.path.getsize(p) / 1024
            print(f"  ✓ {s['code']:16s} {kb:6.1f} KB  {s['cover']}")
    return bad


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN" data-theme="light" data-lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="description" content="__DESC__">
<meta name="color-scheme" content="light dark">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="__BASE__/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="参考素材库">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__BASE__/">
<meta property="og:image" content="__BASE__/og-cover.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="zh_CN">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITLE__">
<meta name="twitter:description" content="__DESC__">
<meta name="twitter:image" content="__BASE__/og-cover.jpg">
<script type="application/ld+json">__LD__</script>
<script>
(function(){try{
  var t=localStorage.getItem('hub.theme'); if(t==='light'||t==='dark') document.documentElement.dataset.theme=t;
  var l=localStorage.getItem('hub.lang');  if(l==='zh'||l==='ja')      document.documentElement.dataset.lang=l;
}catch(e){}})();
</script>
<style>
:root{
  --r:18px;
  --f:system-ui,-apple-system,"Segoe UI","PingFang SC","Hiragino Sans","Noto Sans SC","Microsoft YaHei",sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --bg:#f4f6f9;--panel:#ffffff;--line:#e3e7ed;--line2:#ccd4e0;
  --tx:#16191f;--tx2:#525b6a;--tx3:#8a93a3;--ac:#2563eb;--on-ac:#fff;
  --hover:#eef1f6;--hb:#b9c3d2;
  --sh:0 8px 24px rgba(16,24,40,.10);--g1:#e6eefc;--g2:#f0e9fb;
  --grad:linear-gradient(90deg,#2563eb,#7c3aed);
  --ok-bg:#e7f6ec;--ok-tx:#186b3a;--warn-bg:#fdf2e0;--warn-tx:#8a5a12;--no-bg:#fdeaea;--no-tx:#a02020;
}
html[data-theme="dark"]{
  --bg:#0d0f12;--panel:#1a1e24;--line:#272c34;--line2:#343a44;
  --tx:#e9ecf1;--tx2:#a3abb8;--tx3:#6c7482;--ac:#8fb4ff;--on-ac:#0b1220;
  --hover:#232831;--hb:#3b4350;
  --sh:0 10px 30px rgba(0,0,0,.45);--g1:#1b2433;--g2:#211a2b;
  --grad:linear-gradient(90deg,#c3d5ff,#e3c8ff);
  --ok-bg:#12291c;--ok-tx:#7ee2a8;--warn-bg:#2b2213;--warn-tx:#f0c274;--no-bg:#2b1616;--no-tx:#f19a9a;
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);color:var(--tx);font-family:var(--f);min-height:100vh;
  -webkit-font-smoothing:antialiased;transition:background-color .22s,color .22s;
  background-image:radial-gradient(1200px 500px at 15% -10%,var(--g1) 0,transparent 60%),
                   radial-gradient(900px 400px at 100% 0,var(--g2) 0,transparent 55%)}
a{color:inherit}
button{font:inherit;color:inherit}

.wrap{max-width:1180px;margin:0 auto;padding:52px clamp(18px,5vw,40px) 72px}

/* 顶栏 */
.top{display:flex;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:10px}
.eyebrow{font-size:11.5px;letter-spacing:.24em;color:var(--tx3);text-transform:uppercase;padding-top:6px}
.switches{display:flex;gap:8px;margin-left:auto}
.switch{display:flex;border:1px solid var(--line2);border-radius:10px;overflow:hidden;background:var(--panel)}
.switch button{height:34px;min-width:34px;padding:0 9px;border:0;background:transparent;color:var(--tx2);
  font-size:12px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:.13s;white-space:nowrap}
.switch button+button{border-left:1px solid var(--line2)}
.switch button:hover{background:var(--hover);color:var(--tx)}
.switch button[aria-pressed="true"]{background:var(--ac);color:var(--on-ac);font-weight:700}
.switch svg{width:14px;height:14px;display:block}

h1{margin:10px 0 10px;font-size:clamp(26px,4vw,40px);font-weight:700;letter-spacing:.02em;line-height:1.25}
h1 span{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.lead{color:var(--tx2);font-size:14px;line-height:1.8;margin:0 0 12px;max-width:680px}
.count-line{display:flex;align-items:center;gap:10px;color:var(--tx3);font-size:12.5px;
  letter-spacing:.06em;margin:0 0 34px}
.count-line b{font-family:var(--mono);color:var(--tx2);font-weight:600}

/* 卡片：左图右文。图片框 3:4 贴合素材比例，竖构图基本不裁切 */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:18px}
.card{display:grid;grid-template-columns:156px 1fr;background:var(--panel);
  border:1px solid var(--line);border-radius:var(--r);overflow:hidden;text-decoration:none;
  transition:transform .18s ease,box-shadow .18s ease,border-color .18s}
.card:hover{transform:translateY(-3px);box-shadow:var(--sh);border-color:var(--hb)}
.thumb{position:relative;aspect-ratio:3/4;background:var(--line);overflow:hidden}
.thumb img{width:100%;height:100%;object-fit:cover;display:block;
  transition:transform .5s cubic-bezier(.2,.7,.2,1)}
.card:hover .thumb img{transform:scale(1.05)}
.info{padding:17px 19px 16px;display:flex;flex-direction:column;gap:7px;min-width:0}
.head{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}
.head h2{margin:0;font-size:17px;font-weight:700;letter-spacing:.01em}
.code{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;color:var(--tx3)}
.desc{margin:0;font-size:12.5px;color:var(--tx2);line-height:1.65;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.nums{display:flex;gap:16px;margin-top:auto;padding-top:11px;border-top:1px solid var(--line)}
.nums div{display:flex;flex-direction:column;gap:0}
.nums b{font-size:15px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1.35}
.nums span{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--tx3)}
.foot{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px}
.go{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--ac);font-weight:600}
.go svg{width:15px;height:15px;transition:transform .18s}
.card:hover .go svg{transform:translateX(3px)}
.lic{font-size:10.5px;letter-spacing:.1em;padding:3px 9px;border-radius:999px;font-weight:600;white-space:nowrap}
.lic.ok{background:var(--ok-bg);color:var(--ok-tx)}
.lic.warn{background:var(--warn-bg);color:var(--warn-tx)}
.lic.no{background:var(--no-bg);color:var(--no-tx)}

footer{margin-top:38px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--tx3);font-size:11.5px;line-height:1.8}
.ft{margin:0 0 6px;font-size:10.5px;font-weight:600;letter-spacing:.16em;
  text-transform:uppercase;color:var(--tx3);opacity:.8}
.credits{list-style:none;margin:0 0 6px;padding:0;max-width:940px;
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2px 34px}
.credits li{display:flex;align-items:baseline;gap:9px;padding:2px 0}
.c-site{min-width:78px;font-size:12px;font-weight:600;color:var(--tx2);
  text-decoration:none;border-bottom:1px solid transparent}
.c-site:hover{color:var(--ac);border-color:var(--ac)}
.c-author{color:var(--tx3);white-space:nowrap}
.c-author a{color:var(--tx3);text-decoration:none;border-bottom:1px solid transparent}
.c-author a:hover{color:var(--ac);border-color:var(--ac)}
.credits .lic{margin-left:auto;font-size:9.5px;padding:1px 7px}
footer .note{margin:0;color:var(--tx3);opacity:.85}

@media(max-width:820px){ .cards{grid-template-columns:1fr} }
@media(max-width:720px){ .credits{grid-template-columns:1fr} }
@media(max-width:520px){
  .card{grid-template-columns:112px 1fr}
  .info{padding:14px 15px 13px;gap:6px}
  .head h2{font-size:15.5px}
  .desc{-webkit-line-clamp:2}
  .nums{gap:12px}
  .nums b{font-size:14px}
}
@media(max-width:600px){ .wrap{padding-top:32px} .switches{width:100%;margin-left:0} }
</style>
</head>
<body>
<div class="wrap">

  <div class="top">
    <div class="eyebrow" id="eyebrow"></div>
    <div class="switches">
      <div class="switch" id="themeSw" role="group" aria-label="Theme">
        <button type="button" data-t="light" title="Light" aria-label="Light"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></svg></button>
        <button type="button" data-t="dark" title="Dark" aria-label="Dark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
      </div>
      <div class="switch" id="langSw" role="group" aria-label="Language">
        <button type="button" data-l="zh">中文</button>
        <button type="button" data-l="ja">日本語</button>
      </div>
    </div>
  </div>

  <h1><span id="h1"></span></h1>
  <p class="lead" id="lead"></p>
  <p class="count-line"><b id="cnt"></b><span id="cntLbl"></span></p>

  <div class="cards" id="cards"></div>

  <footer>
    <h2 class="ft" id="ftitle"></h2>
    <ul class="credits" id="credits"></ul>
    <p class="note" id="fnote"></p>
  </footer>
  __SEO_INTRO__
</div>

<script>
const DATA = __DATA__;
const LIC = __LIC__;
const LIC_NAME = {
  zh: { ok: 'CC0', warn: '有条件', no: '禁止再分发' },
  ja: { ok: 'CC0', warn: '条件付き', no: '再配布禁止' }
};

let LANG  = document.documentElement.dataset.lang  || 'zh';
let THEME = document.documentElement.dataset.theme || 'light';

const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tx = o => (o && typeof o === 'object') ? (o[LANG] || o.zh || '') : (o || '');

function render(){
  const M = DATA.meta;

  $('#eyebrow').textContent = M.eyebrow;
  $('#h1').textContent = tx(M.title);
  $('#lead').textContent = tx(M.lead);
  $('#cnt').textContent = String(DATA.sites.length).padStart(2, '0');
  $('#cntLbl').textContent = LANG === 'zh' ? '个站点' : 'サイト';
  document.title = LANG === 'zh' ? __TITLE_JS__ : tx(M.title) + ' · ' + DATA.sites.length + ' サイト';

  $('#cards').innerHTML = DATA.sites.map(s => {
    const lic = LIC[s.license] || LIC.restricted;
    return '<a class="card" href="./' + esc(s.id) + '/">' +
      '<div class="thumb">' +
        '<img src="' + esc('./' + s.id + '/' + s.cover) + '" alt="' + esc(s.code) + '" loading="lazy"' +
          (s.coverPos ? ' style="object-position:' + esc(s.coverPos) + '"' : '') + '>' +
      '</div>' +
      '<div class="info">' +
        '<div class="head"><h2>' + esc(tx(s.name)) + '</h2>' +
          '<span class="code">' + esc(s.code) + '</span></div>' +
        '<p class="desc">' + esc(tx(s.desc)) + '</p>' +
        '<div class="nums">' + s.stats.map(st =>
          '<div><b>' + esc(st.v) + '</b><span>' + esc(tx(st.l)) + '</span></div>').join('') + '</div>' +
        '<div class="foot">' +
          '<span class="go">' + (LANG === 'zh' ? '进入' : '開く') +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13M13 6l6 6-6 6"/></svg></span>' +
          '<span class="lic ' + esc(lic.cls) + '">' + esc(LIC_NAME[LANG][lic.cls]) + '</span>' +
        '</div>' +
      '</div></a>';
  }).join('');

  $('#ftitle').textContent = tx(M.creditTitle);
  $('#fnote').textContent = tx(M.licenseNote);

  // 素材来源与版权：链接原站、标注原作者、标出各站授权
  $('#credits').innerHTML = DATA.sites.map(s => {
    const lic = LIC[s.license] || LIC.restricted;
    const host = String(s.source || '').replace(/^https?:\/\//, '').replace(/\/$/, '');
    const handle = String(s.author.url || '').split('/').pop();
    return '<li>' +
      '<a class="c-site" href="' + esc(s.source) + '" target="_blank" rel="noopener noreferrer"' +
        ' title="' + esc(host) + '">' + esc(tx(s.name)) + '</a>' +
      '<span class="c-author">' + esc(s.author.name) + ' <a href="' + esc(s.author.url) +
        '" target="_blank" rel="noopener noreferrer">@' + esc(handle) + '</a></span>' +
      '<span class="lic ' + esc(lic.cls) + '">' + esc(LIC_NAME[LANG][lic.cls]) + '</span>' +
    '</li>';
  }).join('');

  document.querySelectorAll('#themeSw button').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.t === THEME ? 'true' : 'false'));
  document.querySelectorAll('#langSw button').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.l === LANG ? 'true' : 'false'));
  document.documentElement.lang = LANG === 'zh' ? 'zh-CN' : 'ja';
}

$('#themeSw').addEventListener('click', e => {
  const b = e.target.closest('[data-t]'); if (!b || b.dataset.t === THEME) return;
  THEME = b.dataset.t;
  document.documentElement.dataset.theme = THEME;
  try { localStorage.setItem('hub.theme', THEME); } catch(_){}
  render();
});
$('#langSw').addEventListener('click', e => {
  const b = e.target.closest('[data-l]'); if (!b || b.dataset.l === LANG) return;
  LANG = b.dataset.l;
  document.documentElement.dataset.lang = LANG;
  try { localStorage.setItem('hub.lang', LANG); } catch(_){}
  render();
});

render();
</script>
</body>
</html>
"""


def total_images(cfg):
    """对外公布的「参考图」总数，沿用最初 12,975 的口径：原站提供的图片文件数，
    即 manifest 条数 × 档位数，不含 mid 档（中图是本仓库生成或补的）。
    这是文件数，不是不同画面数：人像、姿势、深度姿势、Shisei 每张图按缩略图 + 原图算两个文件，服装按三档算三个。"""
    n = 0
    for s in cfg["sites"]:
        p = os.path.join(ROOT, "sites", s["id"], "manifest.json")
        with open(p, encoding="utf-8") as f:
            rows = len(json.load(f))
        n += rows * len([t for t in s.get("tiers", []) if t != "mid"])
    return n


def hub_seo(cfg, base):
    """入口页静态介绍、FAQ 与 llms.txt。事实只取自 sites.json 与固定的授权说明。"""
    sites = {s["id"]: s for s in cfg["sites"]}
    stat = lambda sid, i: sites[sid]["stats"][i]["v"]
    N = f"{total_images(cfg):,}"
    K = len(cfg["sites"])
    faq = [
        ("photoai.life 是什么？",
         "一组面向 AI 绘画的参考图库：人像集（角色脸部一致性参考）、姿势集（人体姿势线稿）、"
         "深度姿势集（ControlNet 深度图）、服装集（服装与穿搭参考）、Shisei（CC0 姿势线稿）"
         f"提示词生图集（{stat('prompts', 1)} 条 AI 生图提示词与对照成图）"
         f"与 Midjourney 提示词集（{stat('prompthero-midjourney', 0)} 条 Midjourney 提示词）、"
         f"Midlibrary 风格库（{stat('midlibrary', 0)} 条风格名与风格参考码），"
         f"共 {N} 张，全部为 AI 生成，中日双语。"),
        ("图片可以商用吗？",
         "要看图库。人像集与 Shisei 姿势线稿为 CC0 1.0 公有领域，可以免费商用和再分发。"
         "提示词生图集的图片与提示词文本为 CC BY 4.0，可商用与转载但必须署名，其中标注为「自制」的图不在该授权内。"
         "姿势集、深度姿势集、服装集、Midjourney 提示词集的原作者"
         "允许免费用于作品制作（包括商用与参考），但禁止再分发、转载或转售图片文件本身；深度姿势集另禁止批量下载。"
         "Midlibrary 风格库已获站方书面许可，可用于个人学习用途的镜像（含图片），条件是署名并回链原站。"),
        ("这些图是真人吗？",
         "不是。人像是 AI 生成的虚构人物，姿势是无脸人偶，服装图由文字生成图像制作，都不对应真实人物或商品。"),
        ("和原站是什么关系？",
         "这里是各原站的中文索引镜像：把日文分类、标签和姿势名译成中文，加了组合筛选、搜索和中日切换。"
         "图片著作权归原作者，每个图库页脚都有原站和作者链接。"),
    ]
    # 入口页上方的卡片已经链到各图库首页，这里链到各图库的分类索引。
    # 只有声明了落地页的站才有 browse/ —— 不声明的站链过去就是 404。
    links = [(f"{s['id']}/browse/", f"{s['name']['zh']} · 分类")
             for s in cfg["sites"] if s.get("landing", True)]
    intro = landing.static_intro(
        [f"photoai.life 收录 {K} 个 AI 绘画参考图库，共 {N} 张 AI 生成的参考图，可在线浏览、按标签筛选和下载。",
         f"人像集 {stat('portrait', 0)} 张，用来让 AI 生成的角色保持同一张脸，CC0 可商用；"
         f"姿势集与深度姿势集各 {stat('pose', 0)} 个姿势、{stat('pose', 1)} 张，每个姿势 5 个视角，深度图可直接用于 ControlNet；"
         f"服装集 {stat('costume', 0)} 套服装、{stat('costume', 2)} 个标签，标签保留英文关键词，可直接作提示词；"
         f"Shisei {stat('shisei', 0)} 个姿势、{stat('shisei', 1)} 张 CC0 线稿，可商用、可再分发；"
         f"提示词生图集收录 {stat('prompts', 1)} 条提示词与 {stat('prompts', 0)} 张对照成图，覆盖 {stat('prompts', 2)} 个模型、"
         f"{stat('prompts', 3)} 个分类，可按模型与标签筛选；"
         f"Midjourney 提示词集收录 {stat('prompthero-midjourney', 0)} 条提示词与成图，覆盖 v1 到 v7 与 Niji 模式，"
         f"按分类与版本筛选，提示词原文可直接复制；"
         f"Midlibrary 风格库收录 {stat('midlibrary', 0)} 条风格条目与风格参考码，每条附一行可复制的提示词与示例图。"],
        [("图库", f"{K} 个"), ("图片", f"{N} 张"), ("语言", "中文 / 日本語"), ("素材", "全部 AI 生成")],
        links, faq, more_href=None)

    lic = {"portrait": "CC0 1.0 公有领域，可商用、可再分发。",
           "pose": "允许免费用于作品制作（含商用与参考）；禁止再分发、转载、转售图片文件本身。",
           "pose-depth": "同姿势集；原站另禁止批量下载或用工具自动获取。",
           "costume": "允许免费用于作品制作（含商用与参考）；禁止再分发、转载、转售图片文件本身。",
           "shisei": "图片 CC0 1.0，可商用、可再分发；姿势目录沿用 ai-pose-gallery，仅注明出处。",
           "prompts": "图片与提示词文本 CC BY 4.0，共享、改编与商用均可，须署名；标注为「自制」的图不在该授权内。",
           "prompthero-midjourney": "素材由 PromptHero 用户上传，版权归各原作者；允许免费用于作品制作与参考，禁止再分发、转载、转售图片文件本身，引用须回链原站。",
           "midlibrary": "已获站方书面许可：允许个人学习用途的镜像（含图片），条件是署名并回链原站；素材著作权归 Midlibrary 团队与各艺术家。"}
    what = {"portrait": f"{stat('portrait', 0)} 张 AI 生成人像：面部 {stat('portrait', 1)} 张（正面、纯色背景），造型 {stat('portrait', 2)} 张。用于 AI 绘画中保持角色脸部一致，按发型分类。",
            "pose": f"{stat('pose', 0)} 个人体姿势、{stat('pose', 1)} 张无脸灰色人偶线稿，每个姿势正面、侧面、斜角、俯视、仰视 5 个视角。",
            "pose-depth": f"同一批 {stat('pose-depth', 0)} 个姿势的 {stat('pose-depth', 1)} 张灰度深度图，可直接作为 ControlNet depth 控制图。",
            "costume": f"{stat('costume', 0)} 套 AI 生成服装、{stat('costume', 1)} 张图，8 个分类、{stat('costume', 2)} 个标签；标签为英文关键词，可直接用作提示词。",
            "shisei": f"{stat('shisei', 0)} 个姿势、{stat('shisei', 1)} 张无脸人偶线稿（全身・标准、上半身、全身・性感、双人），每个姿势最多 5 个视角；偏性感的姿势默认模糊。",
            "prompts": f"{stat('prompts', 1)} 条 AI 生图提示词与 {stat('prompts', 0)} 张对照成图，覆盖 {stat('prompts', 2)} 个模型、"
                       f"{stat('prompts', 3)} 个分类；展示中文提示词、复制英文原文。此外还可将自己跑出的图挂到提示词下。",
            "prompthero-midjourney": f"{stat('prompthero-midjourney', 0)} 条 Midjourney 提示词与成图，覆盖 {stat('prompthero-midjourney', 3)} 个版本、"
                       f"{stat('prompthero-midjourney', 2)} 个分类；提示词原文可直接复制，含成人内容分区（默认模糊）。",
            "midlibrary": f"{stat('midlibrary', 0)} 条 Midjourney 风格条目（含 {stat('midlibrary', 2)} 个风格参考码）、"
                      f"{stat('midlibrary', 3)} 个分类；每条附一行可复制的提示词与示例图，先看图再决定用不用这个码。"}
    lines = ["# photoai.life", "",
             f"> AI 绘画参考图库合集：人像、人体姿势、ControlNet 姿势深度图、服装、CC0 姿势线稿、提示词生图集、Midjourney 提示词集、Midlibrary 风格库，共 {N} 张，全部为 AI 生成。"
             "中文索引镜像，界面支持中文与日本語。", "",
             "每个图库都是一个可筛选的画廊页，另有按分类 / 标签 / 发型生成的静态落地页（见各图库的 browse/ 目录与 sitemap）。"
             "图片著作权归各原作者，授权各不相同，引用时请注明对应图库的授权。", "",
             "## 图库", ""]
    for s in cfg["sites"]:
        lines.append(f"- [{s['name']['zh']}]({base}/{s['id']}/)：{what.get(s['id'], s['desc']['zh'])}"
                     f" 授权：{lic.get(s['id'], '')} 原站：{s['source']}")
    lines += ["", "## 分类与标签索引", ""]
    lines += [f"- [{s['name']['zh']} · 全部分类]({base}/{s['id']}/browse/)"
              for s in cfg["sites"] if s.get("landing", True)]
    lines += ["", "## 常见问题", ""] + [f"- **{q}** {a}" for q, a in faq]
    lines += ["", "## 其他", "",
              f"- [站点地图]({base}/sitemap.xml)",
              "- [源代码（MIT）](https://github.com/xue1long/ai-video-imge-prompts)", ""]
    return {"intro": intro, "faq": faq, "llms": "\n".join(lines)}


def apply_manifest_stats(cfg):
    """站点有 manifest 时，把能由它推导的统计数字改成现算值。

    sites.json 的 stats 是人工维护的，累积型站点（每天新增）必然过期。
    只覆盖可由 manifest 直接推导的中文标签，其余标签原样保留。
    """
    rules = {
        "成图": lambda rows: len(rows),
        "作业": lambda rows: len({r.get("jobId") for r in rows if r.get("jobId")}),
        "作者": lambda rows: len({r.get("username") for r in rows if r.get("username")}),
        "宽高比": lambda rows: len({r.get("aspect") for r in rows if r.get("aspect")}),
    }
    for s in cfg["sites"]:
        p = os.path.join(ROOT, "sites", s["id"], "manifest.json")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            rows = json.load(f)
        for st in s.get("stats") or []:
            label = (st.get("l") or {}).get("zh")
            fn = rules.get(label)
            if fn:
                st["v"] = str(fn(rows))
    return cfg


def main():
    cfg = load()
    apply_manifest_stats(cfg)
    only_check = "--check" in sys.argv

    base = "https://example.com"
    for i, a in enumerate(sys.argv):
        if a == "--base" and i + 1 < len(sys.argv):
            base = sys.argv[i + 1]
        elif a.startswith("--base="):
            base = a.split("=", 1)[1]
    base = base.rstrip("/")

    print(f"读取 sites.json：{len(cfg['sites'])} 个站点")
    bad = check(cfg)
    if bad:
        print(f"\n⚠️  {bad} 张封面缺失，生成的页面会出现空图。")

    if only_check:
        print("\n仅校验模式，未生成 index.html")
        return 1 if bad else 0

    lic = {k: {"cls": v["cls"]} for k, v in LICENSE_LABEL.items()}
    data = json.dumps(cfg, ensure_ascii=False, separators=(",", ":"))
    lic_js = json.dumps(lic, ensure_ascii=False, separators=(",", ":"))

    title = f"photoai.life · AI 绘画参考图库：人像、姿势、ControlNet 深度图、服装、Midjourney 提示词，共 {total_images(cfg):,} 张"
    desc = (f"{len(cfg['sites'])} 个 AI 绘画参考图库合集：1499 张 CC0 人像（角色脸部一致性参考）、288 个人体姿势线稿与深度图"
            "（各 1439 张，五视角，适合 ControlNet）、1407 套服装（86 个标签）、280 个 CC0 姿势线稿、"
            "12998 条 Midjourney 提示词与成图。中日双语，全部可在线浏览。")
    seo = hub_seo(cfg, base)

    # 结构化数据：告诉搜索引擎/AI 引擎这是一组并列的子站点
    ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "description": desc,
        "url": base + "/",
        "inLanguage": "zh-CN",
        "hasPart": [
            {"@type": "WebSite", "name": s["name"]["zh"], "url": f"{base}/{s['id']}/"}
            for s in cfg["sites"]
        ],
    }, ensure_ascii=False, separators=(",", ":"))

    html = (TEMPLATE
            .replace("__TITLE__", title)
            .replace("__TITLE_JS__", json.dumps(title, ensure_ascii=False))
            .replace("__SEO_INTRO__", seo["intro"])
            .replace("</style>", "</style><style>" + landing.SEO_INTRO_CSS
                     + ".seo-intro{padding:0;margin-top:34px}</style>" + landing.faq_ld_script(seo["faq"]), 1)
            .replace("__DESC__", desc)
            .replace("__LIC__", lic_js)
            .replace("__LD__", ld)
            .replace("__BASE__", base)
            .replace("__DATA__", data))

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    print(f"\n写出 index.html  {os.path.getsize(OUT)/1024:.1f} KB")

    # 根 sitemap：入口页 + 各子站首页 + 各子站落地页（读各站 data/landing.json）
    urls = [base + "/"]
    for s in cfg["sites"]:
        urls.append(f"{base}/{s['id']}/")
        p = os.path.join(ROOT, "sites", s["id"], "data", "landing.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                urls += [f"{base}/{s['id']}/{pg}/" for pg in json.load(f)["pages"]]
    urls = [landing.esc(u) for u in urls]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sm.append(f"  <url><loc>{u}</loc><changefreq>weekly</changefreq></url>")
    sm.append("</urlset>")
    with open(os.path.join(HUB, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sm) + "\n")

    # 根 robots：显式允许抓取并指向 sitemap
    with open(os.path.join(HUB, "robots.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("User-agent: *\nAllow: /\n\n"
                f"Sitemap: {base}/sitemap.xml\n")

    print(f"写出 sitemap.xml（{len(urls)} 条）与 robots.txt  base = {base}")

    # llms.txt：给 AI 爬虫与助手的站点说明（https://llmstxt.org/）
    with open(os.path.join(HUB, "llms.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(seo["llms"])
    print("写出 llms.txt")

    if bad:
        # 封面缺失不阻断生成：新克隆的仓库还没下图片，先出页面，
        # 下载素材后重跑即可。只有 --check 模式才以非零退出提示。
        print("提示：封面缺失的卡片会显示空图，运行 tools/fetch.py 后重新生成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
