# -*- coding: utf-8 -*-
"""生成风格码库页面（styles/index.html）。

这个页面是什么
--------------
`data/styles.json` 里是原站 Styles 的**风格码**（`--sref` 后面那串数字）。每个码在
`styles/<码>/` 下有三张语义示例图（portrait / landscape / still_life），另有
`styles/<码>/s/` 下的 384 缩略（由 fetch_styles.py 本地缩放生成）。

它不是 WebUI 集合里的「风格」视图——那个已于 2026-11-03 删除：原站 Styles 是独立
内容类型（一个码 + 三张示例图，无 prompt、无作者），与「一条作业四格成图」不同源。
两边的取舍写在 index/catalog.py 里 midjourney-explore 的注释中。

图片分两档，各司其职
--------------------
    网格  styles/<码>/s/<kind>.webp   384，平均 18 KB，靠 loading="lazy" 按需加载
    灯箱  styles/<码>/<kind>.webp     1024，点开才拉

页面只引用缩略，所以首屏约 12 张 ≈ 220 KB；不点灯箱就永远不会拉 1024。

缺图是硬失败
------------
任何一个码的任何一档缺失，直接非零退出并列出缺什么。不做「降级成 1024」这种
静默兜底——那会发布出一个慢一倍还看不出问题的页面。

产物
----
    styles/index.html    单文件，数据内嵌（329 码约 13 KB JSON）

用法
----
    python scripts/build_styles_page.py
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
STYLES_JSON = os.path.join(SITE, "data", "styles.json")
IMG_DIR = os.path.join(SITE, "styles")
OUT_DEFAULT = os.path.join(IMG_DIR, "index.html")

KINDS = ("portrait", "landscape", "still_life")
KIND_ZH = {"portrait": "人像", "landscape": "风景", "still_life": "静物"}
MIN_BYTES = 512  # 小于这个体积当作坏文件


# ── 数据 ────────────────────────────────────────────────────────────
def load_items():
    """返回 (items, latest, raw)。items = [(码, added_at)]，按首次收录时间倒序。"""
    if not os.path.exists(STYLES_JSON):
        sys.exit("找不到 %s，先运行 python scripts/dump_styles.py" % STYLES_JSON)
    with open(STYLES_JSON, encoding="utf-8") as f:
        data = json.load(f)
    items, seen = [], set()
    for it in data.get("items", []):
        code = it.get("code") or (it.get("id", "").split("_")[-1])
        if not code or not code.isdigit() or code in seen:
            continue
        seen.add(code)
        items.append((code, it.get("added_at") or ""))
    if not items:
        sys.exit("%s 里没有有效的风格码" % STYLES_JSON)
    # 默认顺序：首次收录时间倒序（新码在前）。同批次内保持榜单原顺序（sorted 稳定）。
    items.sort(key=lambda kv: kv[1], reverse=True)
    latest = max((a for _, a in items if a), default="")
    return items, latest, data


def check_images(items):
    """两档图缺一不可。返回缺失的相对路径列表（空 = 齐全）。"""
    missing = []
    for code, _ in items:
        for kind in KINDS:
            for parts in ((code, kind + ".webp"), (code, "s", kind + ".webp")):
                p = os.path.join(IMG_DIR, *parts)
                if not os.path.exists(p) or os.path.getsize(p) <= MIN_BYTES:
                    missing.append("/".join(parts))
    return missing


# ── 页面 ────────────────────────────────────────────────────────────
CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#fafaf9;--bg2:#fff;--tx:#1c1917;--tx2:#57534e;--tx3:#a8a29e;
  --line:#e7e5e4;--ac:#0f766e;--ac2:#14b8a6;--panel:#fff;--shadow:0 1px 2px rgba(28,25,23,.06)
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0c0a09;--bg2:#1c1917;--tx:#f5f5f4;--tx2:#a8a29e;--tx3:#78716c;
  --line:#292524;--ac:#2dd4bf;--ac2:#5eead4;--panel:#1c1917;--shadow:0 1px 2px rgba(0,0,0,.4)
}}
html[data-theme=light]{--bg:#fafaf9;--bg2:#fff;--tx:#1c1917;--tx2:#57534e;--tx3:#a8a29e;
  --line:#e7e5e4;--ac:#0f766e;--ac2:#14b8a6;--panel:#fff;--shadow:0 1px 2px rgba(28,25,23,.06)}
html[data-theme=dark]{--bg:#0c0a09;--bg2:#1c1917;--tx:#f5f5f4;--tx2:#a8a29e;--tx3:#78716c;
  --line:#292524;--ac:#2dd4bf;--ac2:#5eead4;--panel:#1c1917;--shadow:0 1px 2px rgba(0,0,0,.4)}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--tx);
  font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC","Hiragino Sans",sans-serif}
a{color:var(--ac)}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px}
header{border-bottom:1px solid var(--line);background:var(--bg2);padding-bottom:18px}
.hd{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;padding:22px 0 0}
h1{margin:0;font-size:24px;letter-spacing:-.01em}
.eyebrow{margin:0;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--tx3)}
.lead{margin:10px 0 0;color:var(--tx2);max-width:62ch;font-size:14px}
.lead code{font-size:13px;background:var(--bg);padding:1px 5px;border-radius:4px;border:1px solid var(--line)}
.back{margin-left:auto;font-size:13px;text-decoration:none;border:1px solid var(--line);
  border-radius:999px;padding:5px 12px;color:var(--tx2);white-space:nowrap}
.back:hover{border-color:var(--ac);color:var(--ac)}
.bar{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--line)}
.barin{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:12px 0}
#q{flex:1 1 220px;min-width:150px;font:inherit;font-size:14px;padding:8px 12px;color:var(--tx);
  background:var(--bg2);border:1px solid var(--line);border-radius:9px}
#q:focus{outline:2px solid var(--ac2);outline-offset:1px;border-color:var(--ac)}
.chk{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--tx2);
  padding:7px 11px;border:1px solid var(--line);border-radius:9px;background:var(--bg2);cursor:pointer}
.chk input{accent-color:var(--ac);margin:0}
.btn{font:inherit;font-size:13px;padding:8px 13px;border-radius:9px;cursor:pointer;
  color:var(--tx);background:var(--bg2);border:1px solid var(--line)}
.btn:hover{border-color:var(--ac);color:var(--ac)}
#count{margin-left:auto;font-size:13px;color:var(--tx3);font-variant-numeric:tabular-nums}
main{padding:22px 0 8px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
@media(max-width:1020px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.grid{grid-template-columns:minmax(0,1fr)}}
.card{display:flex;flex-direction:column;min-width:0;background:var(--panel);
  border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--shadow)}
.card[hidden]{display:none}
.shot{display:block;cursor:zoom-in;background:var(--bg2);border-bottom:1px solid var(--line)}
.shot img{display:block;width:100%;height:auto;aspect-ratio:2/3;object-fit:cover}
.kinds{display:flex;border-bottom:1px solid var(--line)}
.kinds button{flex:1;font:inherit;font-size:12px;padding:7px 4px;cursor:pointer;
  color:var(--tx2);background:transparent;border:0;border-right:1px solid var(--line)}
.kinds button:last-child{border-right:0}
.kinds button:hover{color:var(--ac)}
.kinds button.on{color:var(--ac);font-weight:600;background:var(--bg)}
html[data-theme=dark] .kinds button.on{background:#0c0a09}
.meta{display:flex;align-items:center;gap:8px;padding:9px 11px}
.meta code{font-size:13px;font-variant-numeric:tabular-nums;color:var(--tx);letter-spacing:.02em}
.tag{font-size:10px;line-height:1;padding:3px 5px;border-radius:4px;
  background:var(--ac);color:#fff;letter-spacing:.06em}
html[data-theme=dark] .tag{color:#06201d}
.cp{margin-left:auto;font:inherit;font-size:12px;padding:5px 10px;cursor:pointer;border-radius:7px;
  color:var(--ac);background:transparent;border:1px solid var(--line)}
.cp:hover{border-color:var(--ac);background:var(--bg)}
.out{font-size:13px;text-decoration:none;color:var(--tx3);padding:0 2px}
.out:hover{color:var(--ac)}
#empty{padding:40px 0;color:var(--tx3);text-align:center}
footer{border-top:1px solid var(--line);margin-top:26px;padding:20px 0 40px;color:var(--tx3);font-size:12.5px}
footer p{margin:6px 0}
footer code{font-size:12px}
.lb{position:fixed;inset:0;z-index:60;display:grid;grid-template-columns:minmax(0,1fr);
  place-items:center;padding:20px;background:rgba(12,10,9,.9)}
.lb[hidden]{display:none}
.lb img{display:block;max-width:min(92vw,720px);max-height:76vh;width:auto;height:auto;
  border-radius:8px;background:var(--bg2)}
.lbclose{position:absolute;top:14px;right:16px;width:38px;height:38px;font-size:20px;line-height:1;
  cursor:pointer;color:#f5f5f4;background:rgba(255,255,255,.12);border:0;border-radius:50%}
.lbnav{position:absolute;top:50%;transform:translateY(-50%);width:42px;height:64px;font-size:24px;
  cursor:pointer;color:#f5f5f4;background:rgba(255,255,255,.12);border:0;border-radius:10px}
#lbPrev{left:14px}
#lbNext{right:14px}
.lbfoot{position:absolute;bottom:18px;left:0;right:0;display:flex;gap:10px;justify-content:center;
  align-items:center;flex-wrap:wrap;padding:0 20px}
.lbfoot code{color:#f5f5f4;font-size:14px;font-variant-numeric:tabular-nums}
.lbfoot button{font:inherit;font-size:12px;padding:6px 11px;cursor:pointer;border-radius:8px;
  color:#f5f5f4;background:rgba(255,255,255,.12);border:0}
.lbfoot button.on{background:#2dd4bf;color:#06201d;font-weight:600}
"""

JS = """
(function(){
  var grid=document.getElementById('grid');
  var q=document.getElementById('q');
  var onlyNew=document.getElementById('onlyNew');
  var copyAll=document.getElementById('copyAll');
  var countEl=document.getElementById('count');
  var emptyEl=document.getElementById('empty');
  var lb=document.getElementById('lb');
  var lbImg=document.getElementById('lbImg');
  var lbCode=document.getElementById('lbCode');
  var lbKinds=document.getElementById('lbKinds');
  var KN=['portrait','landscape','still_life'];
  var ZH={portrait:'人像',landscape:'风景',still_life:'静物'};
  var cards={}, order=[], cur=null;

  function el(tag,attrs){
    var n=document.createElement(tag);
    for(var k in attrs) n.setAttribute(k,attrs[k]);
    return n;
  }

  /* 灯箱里的三态按钮 */
  KN.forEach(function(k){
    var b=el('button',{'type':'button','data-kind':k});
    b.textContent=ZH[k];
    lbKinds.appendChild(b);
  });

  /* 建卡：一次建好，之后只切 class / src，不重建 DOM。
     codes 是全数字字符串，不能拿它当对象键遍历（JS 会把数字键按大小排序），
     所以另存一份 order 数组来保持「新码在前」的顺序。 */
  DB.codes.forEach(function(item){
    var code=item[0];
    var card=el('article',{'class':'card','data-code':code,'data-kind':'portrait'});
    if(item[1]===DB.latest) card.setAttribute('data-fresh','1');
    var shot=el('a',{'class':'shot','href':code+'/portrait.webp','data-open':'1',
                     'aria-label':'放大查看风格码 '+code});
    var img=el('img',{'src':code+'/s/portrait.webp','alt':'风格码 '+code+' 的人像示例',
                      'loading':'lazy','width':'256','height':'384','decoding':'async'});
    shot.appendChild(img);
    var kinds=el('div',{'class':'kinds'});
    KN.forEach(function(k){
      var b=el('button',{'type':'button','data-kind':k});
      b.textContent=ZH[k];
      if(k==='portrait') b.className='on';
      kinds.appendChild(b);
    });
    var meta=el('div',{'class':'meta'});
    var cd=el('code'); cd.textContent=code;
    meta.appendChild(cd);
    if(item[1]===DB.latest){ var t=el('span',{'class':'tag'}); t.textContent='新'; meta.appendChild(t); }
    var cp=el('button',{'type':'button','class':'cp','data-copy':'1','title':'复制 --sref '+code});
    cp.textContent='复制';
    meta.appendChild(cp);
    var out=el('a',{'class':'out','href':'https://www.midjourney.com/styles/0_'+code,
                    'target':'_blank','rel':'noopener noreferrer','title':'在原站打开'});
    out.textContent='\\u2197';
    meta.appendChild(out);
    card.appendChild(shot); card.appendChild(kinds); card.appendChild(meta);
    grid.appendChild(card);
    cards[code]=card; order.push(code);
  });

  /* 筛选：搜索用子串匹配（前缀是它的子集），「只看最近新增」= 最近一轮采集进来的 */
  function apply(){
    var s=q.value.trim();
    var onlyF=onlyNew.checked, n=0;
    order.forEach(function(code){
      var c=cards[code];
      var show=(!s||code.indexOf(s)>-1)&&(!onlyF||c.getAttribute('data-fresh')==='1');
      if(show){ c.removeAttribute('hidden'); n++; } else { c.setAttribute('hidden',''); }
    });
    countEl.textContent='显示 '+n+' / '+DB.codes.length;
    emptyEl.hidden=n>0;
  }
  q.addEventListener('input',apply);
  onlyNew.addEventListener('change',apply);

  function setKind(card,kind){
    var code=card.getAttribute('data-code');
    card.setAttribute('data-kind',kind);
    card.querySelector('.shot').setAttribute('href',code+'/'+kind+'.webp');
    var img=card.querySelector('.shot img');
    img.setAttribute('src',code+'/s/'+kind+'.webp');
    img.setAttribute('alt','风格码 '+code+' 的'+ZH[kind]+'示例');
    var bs=card.querySelectorAll('.kinds button');
    for(var i=0;i<bs.length;i++) bs[i].className=(bs[i].getAttribute('data-kind')===kind?'on':'');
  }

  grid.addEventListener('click',function(e){
    var b=e.target.closest('button[data-kind]');
    if(b){ setKind(b.closest('.card'),b.getAttribute('data-kind')); return; }
    var cp=e.target.closest('button[data-copy]');
    if(cp){ copy('--sref '+cp.closest('.card').getAttribute('data-code'),cp); return; }
    var op=e.target.closest('[data-open]');
    if(op){
      e.preventDefault();
      var card=op.closest('.card');
      openLb(card.getAttribute('data-code'),card.getAttribute('data-kind'));
    }
  });

  /* 复制：非安全上下文（局域网 http）没有 clipboard API，退回 textarea */
  function copy(text,btn){
    function ok(){
      if(!btn) return;
      var t=btn.textContent; btn.textContent='已复制';
      setTimeout(function(){ btn.textContent=t; },1200);
    }
    function fallback(){
      var ta=el('textarea'); ta.value=text;
      ta.style.position='fixed'; ta.style.opacity='0';
      document.body.appendChild(ta); ta.select();
      try{ document.execCommand('copy'); ok(); }catch(err){}
      document.body.removeChild(ta);
    }
    if(navigator.clipboard&&window.isSecureContext) navigator.clipboard.writeText(text).then(ok,fallback);
    else fallback();
  }

  copyAll.addEventListener('click',function(){
    var lines=[];
    order.forEach(function(code){
      if(!cards[code].hasAttribute('hidden')) lines.push('--sref '+code);
    });
    copy(lines.join('\\n'),copyAll);
  });

  /* 灯箱：只在同一个码的三张之间翻，不跨码（跨码会把人拖出上百张大图） */
  function openLb(code,kind){
    cur={code:code,kind:kind};
    lbImg.setAttribute('src',code+'/'+kind+'.webp');
    lbImg.setAttribute('alt','风格码 '+code+' 的'+ZH[kind]+'示例（1024）');
    lbCode.textContent=code;
    var bs=lbKinds.querySelectorAll('button');
    for(var i=0;i<bs.length;i++) bs[i].className=(bs[i].getAttribute('data-kind')===kind?'on':'');
    lb.hidden=false;
    document.body.style.overflow='hidden';
  }
  function closeLb(){
    lb.hidden=true; cur=null;
    lbImg.removeAttribute('src');
    document.body.style.overflow='';
  }
  function step(d){
    if(!cur) return;
    var i=KN.indexOf(cur.kind);
    openLb(cur.code,KN[(i+d+KN.length)%KN.length]);
  }
  document.getElementById('lbClose').addEventListener('click',closeLb);
  document.getElementById('lbPrev').addEventListener('click',function(){ step(-1); });
  document.getElementById('lbNext').addEventListener('click',function(){ step(1); });
  lb.addEventListener('click',function(e){ if(e.target===lb) closeLb(); });
  lbKinds.addEventListener('click',function(e){
    var b=e.target.closest('button[data-kind]');
    if(b&&cur) openLb(cur.code,b.getAttribute('data-kind'));
  });
  document.addEventListener('keydown',function(e){
    if(lb.hidden) return;
    if(e.key==='Escape') closeLb();
    else if(e.key==='ArrowLeft') step(-1);
    else if(e.key==='ArrowRight') step(1);
  });

  apply();
})();
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>风格码库 · Midjourney Styles 参考（__COUNT__ 个码）</title>
<meta name="description" content="Midjourney Styles 榜单的风格码（--sref）索引，共 __COUNT__ 个码，每个码附人像 / 风景 / 静物三张示例图，可一键复制 --sref 参数。">
<meta name="theme-color" content="#fafaf9" media="(prefers-color-scheme:light)">
<meta name="theme-color" content="#0c0a09" media="(prefers-color-scheme:dark)">
<script>
  /* 与主站共用 localStorage 的 mje.theme：在主站切过主题，这里跟着变 */
  try{var t=localStorage.getItem('mje.theme'); if(t==='light'||t==='dark') document.documentElement.dataset.theme=t;}catch(e){}
</script>
<style>__CSS__</style>
</head>
<body>
<header>
  <div class="wrap hd">
    <p class="eyebrow">MJ-EXPLORE-01 · Styles</p>
    <h1>风格码库</h1>
    <a class="back" href="../">&larr; 探索镜像</a>
  </div>
  <div class="wrap">
    <p class="lead">原站 Styles 榜单里的风格码，即提示词里 <code>--sref</code> 后面那串数字。
      每个码附人像 / 风景 / 静物三张示例图，用来判断这套视觉语言长什么样。
      这些条目在原站本身就不带 prompt。</p>
  </div>
</header>
<div class="bar">
  <div class="wrap barin">
    <input id="q" type="search" placeholder="搜码（任意几位数字）" aria-label="按码搜索" autocomplete="off">
    <label class="chk"><input id="onlyNew" type="checkbox"> 只看最近新增</label>
    <button id="copyAll" class="btn" type="button">复制全部码</button>
    <span id="count">__COUNT__ 个码</span>
  </div>
</div>
<main class="wrap">
  <div id="grid" class="grid"></div>
  <p id="empty" hidden>没有匹配的码。</p>
</main>
<footer>
  <div class="wrap">
    <p>共 <strong>__COUNT__</strong> 个风格码、<strong>__SHOTS__</strong> 张示例图（每码三张 × 两档）。最近一次采集：__CAPTURED__。</p>
    <p>码与示例图来自 <a href="https://www.midjourney.com/explore?tab=styles_top" target="_blank" rel="noopener noreferrer">Midjourney Explore · Styles</a>，著作权归各原作者；本站为个人学习用途的索引，请勿再分发图片文件，引用请回链原站。</p>
    <p>复制 <code>--sref &lt;码&gt;</code> 直接贴进 Midjourney 提示词即可套用该风格。</p>
  </div>
</footer>
<div id="lb" class="lb" hidden>
  <button id="lbClose" class="lbclose" type="button" aria-label="关闭">&times;</button>
  <button id="lbPrev" class="lbnav" type="button" aria-label="上一张">&#8249;</button>
  <img id="lbImg" alt="">
  <button id="lbNext" class="lbnav" type="button" aria-label="下一张">&#8250;</button>
  <div class="lbfoot">
    <code id="lbCode"></code>
    <span id="lbKinds"></span>
  </div>
</div>
<script>__DB__</script>
<script>__JS__</script>
</body>
</html>
"""


def build_html(items, latest, meta):
    db = {"latest": latest, "codes": [[code, added] for code, added in items]}
    return (HTML
            .replace("__CSS__", CSS)
            .replace("__JS__", JS)
            .replace("__DB__", "var DB=" + json.dumps(db, ensure_ascii=False, separators=(",", ":")) + ";")
            .replace("__COUNT__", str(len(items)))
            .replace("__SHOTS__", str(len(items) * len(KINDS)))
            .replace("__CAPTURED__", (meta.get("captured_at") or "").replace("T", " ")[:16]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT_DEFAULT)
    args = ap.parse_args()

    items, latest, meta = load_items()
    missing = check_images(items)
    if missing:
        print("缺图 %d 个，未生成页面：" % len(missing), file=sys.stderr)
        for rel in missing[:15]:
            print("  " + rel, file=sys.stderr)
        if len(missing) > 15:
            print("  …还有 %d 个" % (len(missing) - 15), file=sys.stderr)
        print("\n先补齐：python scripts/fetch_styles.py", file=sys.stderr)
        print("（大图或 384 缩略任一缺失都会走到这里；缩略由本地缩放生成，"
              "删掉该码的 s/ 目录重跑即可）", file=sys.stderr)
        return 1

    html = build_html(items, latest, meta)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    fresh = sum(1 for _, a in items if a == latest)
    print("写入 %s：%d 个码，%d 张示例图，最近一轮新增 %d，页面 %.1f KB"
          % (args.out, len(items), len(items) * len(KINDS), fresh,
             os.path.getsize(args.out) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
