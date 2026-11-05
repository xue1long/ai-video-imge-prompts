# -*- coding: utf-8 -*-
"""Midlibrary 详情页富文本层：About / Observations / Look terms / Colours

采集段（extract.py）只抓列表页 —— 列表页的 flight payload 里固定 13 个字段，
没有描述、没有分面词、没有配色。这三样只在**详情页**的 SSR HTML 里：

  <section id="sp-about">        <p class="sp-prose">一段简介（艺术家是小传，风格条目是描述）
  <section id="sp-observations"> <p class="sp-prose">一段观察（这个风格长什么样）
  <section id="sp-terms">        <div class="sp-group">… 分面词 + 全站计数 + /feature/<slug>
  <section id="sp-colours">      <a class="sp-colour" style="--c:#hex">… 颜色名 + 占比

用法：
    python scripts/extract_details.py                  # 抓全部（断点续跑，已抓过的跳过）
    python scripts/extract_details.py --limit 20       # 只抓 20 条（试跑）
    python scripts/extract_details.py --workers 4      # 并发数（默认 4）
    python scripts/extract_details.py --dry-run        # 不联网，只解析本地 HTML（开发用）
    python scripts/extract_details.py --out X.json     # 换输出文件

产物：data/details.json
    {slug: {"a": 简介, "o": 观察, "t": [[组名, [[词, 计数, featureSlug], …]], …],
            "c": [[hex, 颜色名, 占比, 颜色slug], …]}}
    -- 缺某个 section 就是空串 / 空数组，不编造。
    -- 按 slug 排序写出（可复现：同样的上游内容 → 逐字节相同的文件）。

只读公开页面：robots.txt 明令禁止的 /api/ 一律不碰。
"""
import argparse
import html as html_lib
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from config import ORIGIN, PROXY, REQUEST_TIMEOUT, RETRY, UA  # noqa: E402
from extract import HEADERS, _throttle, build_opener  # noqa: E402

ITEMS = os.path.join(SITE, "data", "items.json")
DEFAULT_OUT = os.path.join(SITE, "data", "details.json")

# 详情页多数 6~15 秒返回；慢的那些基本是断流，等 240 秒只是白等。
TIMEOUT = 90
WORKERS = 4
# 落盘节流：每攒够这么多条就整体重写一次（原子替换），中途崩了不丢已抓的
FLUSH_EVERY = 200

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()


# ── HTML → 结构化 ──────────────────────────────────────
def _section(html, sid):
    """按 section 的 id 切出整段 HTML。

    不能用正则切到下一个 </section>：section 之间会嵌套，
    这里按 <section 标签的深度配平，取到与开头那个闭合为止。
    """
    i = html.find('id="%s"' % sid)
    if i < 0:
        return ""
    start = html.rfind("<section", 0, i)
    if start < 0:
        return ""
    depth = 0
    for m in re.finditer(r"</?section\b", html[start:]):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            return html[start:start + m.end()]
    return ""


_TAG_RE = re.compile(r"<[^>]+>")


def _text(fragment):
    """去标签、解实体、把连续空白压成一个空格。"""
    return re.sub(r"\s+", " ", html_lib.unescape(_TAG_RE.sub(" ", fragment))).strip()


def _prose(section):
    """section 里的第一段 <p class="sp-prose">。"""
    m = re.search(r'<p class="sp-prose">(.*?)</p>', section, re.S)
    return _text(m.group(1)) if m else ""


_TERM_GROUP_RE = re.compile(
    r'<div class="sp-group"><span class="sp-group-label">(.*?)</span>'
    r'<span class="sp-group-terms">(.*?)</span></div>', re.S)
_TERM_RE = re.compile(
    r'<a class="sp-term" href="/feature/([^"]*)">\s*<span>(.*?)</span>'
    r'<span class="sp-count">(.*?)</span>', re.S)


def _terms(text):
    """Look terms：[[组名, [[词, 全站计数, featureSlug], …]], …]，保持页面顺序。"""
    out = []
    for g in _TERM_GROUP_RE.finditer(text):
        label = _text(g.group(1))
        items = [[_text(m.group(2)), _text(m.group(3)), m.group(1)]
                 for m in _TERM_RE.finditer(g.group(2))]
        if items:
            out.append([label, items])
    return out


_COLOUR_RE = re.compile(
    r'<a class="sp-colour" style="--c:(#[0-9a-fA-F]{3,8})"[^>]*'
    r'href="/library\?colour=([^"]*)">\s*<span class="sp-swatch"></span>'
    r'<span>(.*?)</span><span class="sp-count">(.*?)</span>', re.S)


def _colours(text):
    """Colours：[[hex, 颜色名, 占比, 颜色slug], …]，保持页面顺序（上游按占比降序）。"""
    return [[m.group(1), _text(m.group(3)), _text(m.group(4)), m.group(2)]
            for m in _COLOUR_RE.finditer(text)]


def parse_detail(html):
    """详情页 HTML → {a, o, t, c}。缺的段就是空值，绝不补写。"""
    return {
        "a": _prose(_section(html, "sp-about")),
        "o": _prose(_section(html, "sp-observations")),
        "t": _terms(_section(html, "sp-terms")),
        "c": _colours(_section(html, "sp-colours")),
    }


def detail_url(slug):
    """详情页地址。只允许 /library/<slug>，robots 禁的 /api/ 一律拒绝。"""
    if not slug or "/" in slug:
        raise ValueError("slug 非法：%r" % (slug,))
    url = "%s/library/%s" % (ORIGIN, urllib.parse.quote(slug))
    if "/api/" in url:
        raise ValueError("拒绝请求 /api/ 路径：%s" % url)
    return url


# 页面完整性判据：必须以 </html> 收尾，且至少带一个 sp- section。
# 只判 </html> 不够 —— 上游实测有截断页仍带结尾标签；只判 section 也不够 ——
# 截断可能正好切在 section 之前。两条都过才算这一页拿到了。
_MARKERS = ('id="sp-about"', 'id="sp-observations"', 'id="sp-terms"', 'id="sp-colours"')


def fetch_detail(opener, slug, logf):
    """抓一页详情页，返回 {a,o,t,c}；彻底失败返回 None。"""
    url = detail_url(slug)
    headers = dict(HEADERS)
    # 详情页和图片是同一道 Referer 门：实测不带 Referer 直接挂死（不是 403），
    # 带上 midlibrary.io 的 Referer 才放行 —— 这里按站内来源带。
    headers["Referer"] = ORIGIN + "/library"
    last = None
    for attempt in range(RETRY):
        try:
            _throttle()
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
            if not raw.rstrip().endswith(b"</html>"):
                raise IOError("响应被截断（%d 字节，没以 </html> 结尾）" % len(raw))
            html = raw.decode("utf-8", "replace")
            if not any(m in html for m in _MARKERS):
                # 页面完整、但确实一个 sp- section 都没有 —— 实测 jan-saudek 就是这样
                # （它也是没有 v8.2 样例表的两条之一）。这不是失败，是「这一页本来
                # 就没有那些段」。记一条空记录，让重跑能收敛；不当成截断去重试。
                logf("   %s 页面完整但没有 sp- section（%d 字节），记空" % (slug, len(raw)))
                return {"a": "", "o": "", "t": [], "c": []}
            return parse_detail(html)
        except Exception as e:
            last = e
            wait = 3 * (attempt + 1)
            if attempt + 1 < RETRY:
                logf("   %s 第 %d 次失败（%s：%s），%d 秒后重试"
                     % (slug, attempt + 1, type(e).__name__, e, wait))
                time.sleep(wait)
    logf("   %s 重试 %d 次仍失败：%s: %s"
         % (slug, RETRY, type(last).__name__, last))
    return None


# ── 落盘 ───────────────────────────────────────────────
def save(details, out_path):
    """整体重写（临时文件 + 原子替换），按 slug 排序保证可复现。"""
    data = dict((k, details[k]) for k in sorted(details))
    text = json.dumps(data, ensure_ascii=False, indent=None,
                      separators=(",", ":"), sort_keys=False)
    tmp = out_path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    os.replace(tmp, out_path)


def load_existing(out_path):
    if not os.path.exists(out_path):
        return {}
    try:
        with io.open(out_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def slugs():
    """待抓的 slug 列表（来自采集段的 items.json，保持上游顺序）。"""
    if not os.path.exists(ITEMS):
        sys.exit("找不到 data/items.json，先运行 python scripts/extract.py --all")
    with io.open(ITEMS, encoding="utf-8") as f:
        items = json.load(f).get("items") or []
    seen, out = set(), []
    for it in items:
        s = it.get("slug")
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser(description="抓详情页的富文本层（描述 / 分面词 / 配色）")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出文件（默认 data/details.json）")
    ap.add_argument("--workers", type=int, default=WORKERS, help="并发数（默认 4）")
    ap.add_argument("--limit", type=int, default=0, help="只抓前 N 条（试跑）")
    ap.add_argument("--dry-run", action="store_true",
                    help="不联网：只解析 --html 给的本地文件（开发用）")
    ap.add_argument("--html", action="append", default=[],
                    help="--dry-run 时要解析的本地详情页（可多次）")
    args = ap.parse_args()

    if args.dry_run:
        for path in args.html:
            with io.open(path, encoding="utf-8", errors="replace") as f:
                html = f.read()
            rec = parse_detail(html)
            print("=" * 20, os.path.basename(path))
            print(json.dumps(rec, ensure_ascii=False, indent=1)[:1400])
        return 0

    todo = slugs()
    if args.limit:
        todo = todo[:args.limit]
    details = load_existing(args.out)
    pending = [s for s in todo if s not in details]
    log("详情页 %d 条：已抓 %d，本轮要做 %d，并发 %d"
        % (len(todo), len(details), len(pending), args.workers))
    if not pending:
        log("没有待抓的，收工")
        return 0

    opener = build_opener()
    failed = []
    done = 0
    t0 = time.time()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = dict((pool.submit(fetch_detail, opener, s, log), s)
                           for s in pending)
            for fut in as_completed(futures):
                slug = futures[fut]
                try:
                    rec = fut.result()
                except Exception as e:                      # 兜底：不让单个异常带走整轮
                    log("   %s 线程异常：%s: %s" % (slug, type(e).__name__, e))
                    rec = None
                if rec is None:
                    failed.append(slug)
                else:
                    details[slug] = rec
                    done += 1
                if done and done % FLUSH_EVERY == 0:
                    save(details, args.out)
                    rate = done / max(time.time() - t0, 1e-9)
                    log("   进度 %d/%d（%.2f 条/秒，已落盘）"
                        % (len(details), len(todo), rate))
    except KeyboardInterrupt:
        log("中断：已抓的先落盘")
    finally:
        save(details, args.out)
        size = os.path.getsize(args.out)
        log("写出 %s：%d 条，%.1f KB" % (args.out, len(details), size / 1024.0))

    if failed:
        log("本轮失败 %d 条（重跑同一条命令会只补这些）：" % len(failed))
        for s in failed[:30]:
            log("   " + s)
        if len(failed) > 30:
            log("   …还有 %d 条" % (len(failed) - 30))
        return 2

    # 自检：抽 3 条打印，确认三样东西不是空的
    sample = [s for s in list(details)[:400] if details[s].get("o")][:3]
    for s in sample:
        rec = details[s]
        log("   样例 %s：描述 %d 字 · 分面 %d 组 · 主色 %d 个"
            % (s, len(rec.get("o") or ""), len(rec.get("t") or []), len(rec.get("c") or [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
