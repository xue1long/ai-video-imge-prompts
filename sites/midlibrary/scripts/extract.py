# -*- coding: utf-8 -*-
"""Midlibrary（Midjourney 风格库）采集段：列表页 → data/items.json + data/meta.json。

上游列表页：
    https://midlibrary.io/library?page=N         全量（212 页 × 48 条 = 10,142 条）
    https://midlibrary.io/library?page=N&pick=1   站方精选（12 页 = 554 条）

上游是 Next.js App Router，**没有公开的 JSON 接口**：列表页的服务端渲染结果
以 RSC flight payload 的形式塞在 <script>self.__next_f.push([1,"…"])</script> 里，
每页 48 条的 tiles 数组就在其中。这一段要做的事：

    1. 抓一页 HTML；
    2. 还原 flight payload，取出 tiles 数组；
    3. 每条 tiles 记录原样存进 data/items.json（另加一个 sheetPath，方便清单段拼图源）。

抓取必须稳（上游实测特征）：

    · 单页 20–60 秒，慢，且不稳；
    · 会中途截断：实测有两次只回了 82 KB 的 CSS 就断在 </html> 之前。
      截断的响应往往还能解析出「少了十几条」的 tiles —— 静默丢数据最难查，
      所以每次响应都校验结尾，不合格就按失败重试；
    · robots.txt 明令禁止 /api/ —— 本站只读公开页面，绝不碰 /api/。

产出：
    data/items.json  {"version":1,"source":…,"scope":"pick|all","pages":N,"items":[…]}
                     items 是上游记录原样（另加 sheetPath），不做任何裁剪或改写；
    data/meta.json   条数 / kind 分布 / category 分布 / isPick、testedMark 计数 /
                     页数 / 采集时间（epoch）/ scope，外加一段 resume（断点信息，
                     见下面 load_resume 的说明）。

用法：
    python extract.py                 # 默认抓 ?pick=1（精选 554 条，12 页）
    python extract.py --all           # 抓全量（212 页）
    python extract.py --pages 3       # 只抓前 3 页（调试）
    python extract.py --pick          # 显式抓精选
    python extract.py --out data/items.json
    python extract.py --force         # 忽略断点，全部重抓
"""
import argparse
import collections
import concurrent.futures
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)                      # sites/midlibrary
sys.path.insert(0, HERE)

from config import (FETCH_WORKERS, LIST_PATH, ORIGIN, PAGE_SIZE_UPSTREAM,  # noqa: E402
                    PICK_TOTAL, PROXY, REQUEST_TIMEOUT, RETRY, SOURCE,
                    TOTAL_PAGES, UA)

# ── 请求头 ─────────────────────────────────────────────
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── 礼貌抓取 ───────────────────────────────────────────
# 上游是非营利站，实测并发一高就大面积断流。除了限制并发数，请求之间还要留间隔。
_MIN_GAP = 0.35                                   # 两次请求之间的最小间隔（秒）
_gap_lock = threading.Lock()
_last_req = [0.0]


def _throttle():
    """全局限速：任意两次请求之间至少隔 _MIN_GAP 秒。

    锁是必需的：四个工作线程同时进来时，要串行地「看一眼上次请求时间 →
    睡到点 → 更新」，否则大家一起醒来一起发请求，等于没限速。
    """
    with _gap_lock:
        now = time.time()
        wait = _last_req[0] + _MIN_GAP - now
        if wait > 0:
            time.sleep(wait)
        _last_req[0] = time.time()


def build_opener():
    """按 config.PROXY 决定走不走代理（FETCH_PROXY 环境变量）。"""
    if PROXY:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    return urllib.request.build_opener()


def page_url(page, scope):
    """列表页地址。

    只允许打 /library —— 上游 robots.txt 明令禁止 /api/，本站只读公开页面。
    """
    if not LIST_PATH.startswith("/library"):
        raise ValueError("列表页路径必须是 /library，拿到的是 %r" % LIST_PATH)
    query = {"page": str(page)}
    if scope == "pick":
        query["pick"] = "1"                       # 站方精选徽章
    url = "%s%s?%s" % (ORIGIN, LIST_PATH, urllib.parse.urlencode(query))
    if "/api/" in url:
        raise ValueError("拒绝请求 /api/ 路径：%s" % url)
    return url


# ── flight payload 解析 ────────────────────────────────
# flight 行形如：self.__next_f.push([1,"1:…\n2:…"])
# 第一个元素是行类型（1 = 文本行），第二个元素是 JS 字符串字面量 —— 里面
# 带转义引号，必须 json.loads 还原成真正的文本，再按出现顺序拼接。
_FLIGHT_RE = re.compile(r"self\.__next_f\.push\(\[1,(\"(?:[^\"\\]|\\.)*\")\]\)", re.S)


def _slice_array(text):
    """从 text[0] == '[' 开始，按括号配平切出一个完整的 JSON 数组。

    不能用 find("]")：数组里 prompt 文本可能自带 ] 或 "，
    所以逐字符扫描，并跳过字符串字面量内部的括号。
    """
    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[:i + 1]
    raise ValueError("tiles 数组没有闭合")


def parse_flight(html):
    """从 HTML 里取出 flight payload 的 tiles 数组。

    返回 (tiles, payload_text)。tiles 是上游记录原样的 dict 列表。

    拼接后的文本里 `"tiles":[` 后面就是 JSON 数组。数组内部的字符串**没有**
    转义引号（上游在 flight 行里已经解开了），所以能直接 json.loads；
    万一某个条目仍留着转义引号，再退一步做两次兜底（见下）。
    """
    chunks = []
    for m in _FLIGHT_RE.finditer(html):
        chunks.append(json.loads(m.group(1)))
    text = "".join(chunks)
    if not chunks:
        raise ValueError("页面里没有 flight payload（可能被挡了或不是 Next.js 页面）")

    key = '"tiles":['
    i = text.find(key)
    if i < 0:
        raise ValueError("flight payload 里没有 tiles 数组（payload %d 字节）" % len(text))
    arr = _slice_array(text[i + len(key) - 1:])

    try:
        tiles = json.loads(arr)
    except ValueError:
        # 兜底 1：把 " 再转义一次；兜底 2：反过来把 \" 解开一次。
        # 都失败说明这一页的 payload 真的坏了 —— 当失败处理并重试。
        try:
            tiles = json.loads(arr.replace('"', '\\"'))
        except ValueError:
            try:
                tiles = json.loads(arr.replace('\\"', '"'))
            except ValueError as e:
                raise ValueError("tiles 数组解析失败：%s" % e)
    if not isinstance(tiles, list):
        raise ValueError("tiles 不是数组（%r）" % type(tiles).__name__)
    return tiles, text


def upstream_total(text):
    """上游分面里的总条数（tools 状态对象里的 "total"），只用来交叉校验。"""
    m = re.search(r'"total":(\d+)', text)
    return int(m.group(1)) if m else 0


# ── 抓取 ───────────────────────────────────────────────
def fetch_page(opener, page, scope, log):
    """抓一页列表，返回 (tiles, payload_text)；彻底失败返回 None。

    None = 这一页没拿到（已按退避重试过，仍不行）；
    空 tiles = 列表到此为止（正常结束）—— 这两件事必须分开，
    否则一次上游抖动就会让采集提前收工，只拿到一半的条目。
    """
    url = page_url(page, scope)
    last = None
    for attempt in range(RETRY):
        try:
            _throttle()
            req = urllib.request.Request(url, headers=HEADERS)
            with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
                raw = resp.read()
            # 截断校验：上游实测会中途断流，只回 82 KB 的 CSS 就没了。
            # 不校验的话，截断页有时仍能解析出「少几条」的 tiles —— 数据静默变少，
            # 事后根本查不出来，所以这里宁可重试也不放过。
            if not raw.rstrip().endswith(b"</html>"):
                raise IOError("响应被截断（%d 字节，没以 </html> 结尾）" % len(raw))
            html = raw.decode("utf-8", "replace")
            tiles, text = parse_flight(html)
            return tiles, text
        except Exception as e:
            last = e
            wait = 3 * (attempt + 1)              # 3 / 6 / 9 秒退避
            if attempt + 1 < RETRY:
                log("      page %d 第 %d 次失败（%s：%s），%d 秒后重试"
                    % (page, attempt + 1, type(e).__name__, e, wait))
                time.sleep(wait)
            else:
                log("      page %d 第 %d 次失败（%s：%s），不再重试"
                    % (page, attempt + 1, type(e).__name__, e))
    log("      page %d 重试 %d 次仍失败：%s: %s"
        % (page, RETRY, type(last).__name__, last))
    return None


# ── 记录整理 ───────────────────────────────────────────
def normalize(tile):
    """一条 tiles 记录 → 采集段的内部记录。

    上游字段原样保留（清单段需要的都在里面），另加一个 sheetPath：
    sheetUrl 是站内路径（/img/…），去掉开头的 "/" 之后就是站点内相对路径，
    清单段拿它拼图源地址（config.img_url —— 注意基准是站点根 ORIGIN，
    不是 IMG_BASE，拼 IMG_BASE 会得到 …/img/img/… 的废地址）。
    """
    rec = dict(tile)
    sheet_url = rec.get("sheetUrl") or ""
    rec["sheetPath"] = sheet_url[1:] if sheet_url.startswith("/") else sheet_url
    return rec


def flatten(page_items):
    """按页号顺序把每页的条目拼成一条平铺的列表。"""
    out = []
    for p in sorted(page_items):
        out.extend(page_items[p])
    return out


# ── 断点续跑 ───────────────────────────────────────────
# 断点信息放在 data/meta.json 的 resume 段里，而不是 data/items.json：
# items.json 是 build_gallery.py 的输入，契约只有五个字段，往里塞私货容易踩坑；
# meta.json 是统计文件，多几个键没人依赖。
def load_resume(items_path, meta_path, scope):
    """读上一轮的采集进度，返回 (done_pages, page_items)；读不到就返回空。"""
    if not (os.path.exists(items_path) and os.path.exists(meta_path)):
        return [], {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        with open(items_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return [], {}
    if meta.get("scope") != scope or data.get("scope") != scope:
        return [], {}                          # 上次是别的采集范围，不能续
    res = meta.get("resume") or {}
    done = [int(p) for p in (res.get("done") or [])]
    counts = res.get("counts") or {}
    items = data.get("items") or []
    if sum(int(counts.get(str(p), 0)) for p in done) != len(items):
        return [], {}                          # 对不上就不敢续 —— 宁可重抓
    page_items = {}
    pos = 0
    for p in sorted(done):
        n = int(counts.get(str(p), 0))
        page_items[p] = items[pos:pos + n]
        pos += n
    return sorted(done), page_items


def write_outputs(items_path, meta_path, scope, page_items, failed, extra_total):
    """写 data/items.json 与 data/meta.json（原子替换）。

    一页都没抓到时**不写**：抓取失败是最常见的故障，一次全页失败就把上一版
    数据覆盖成空文件是这类脚本最经典的事故（退出码还是 0，数据却没了）。
    这种情况保留原文件，交给人判断。
    """
    items = flatten(page_items)
    if not items and os.path.exists(items_path) and os.path.getsize(items_path) > 0:
        return None
    payload = {
        "version": 1,
        "source": SOURCE,
        "scope": scope,
        "pages": len(page_items),
        "items": items,
    }
    tmp = items_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, items_path)

    kinds = collections.Counter(r.get("kind") or "-" for r in items)
    cats = collections.Counter(r.get("categorySlug") or "-" for r in items)
    meta = {
        "count": len(items),
        "scope": scope,
        "pages": len(page_items),
        "kinds": dict(kinds.most_common()),
        "categories": dict(cats.most_common()),
        "isPick": sum(1 for r in items if r.get("isPick")),
        "testedMark": sum(1 for r in items if r.get("testedMark")),
        "isPublicDomain": sum(1 for r in items if r.get("isPublicDomain")),
        "withSheet": sum(1 for r in items if r.get("sheetPath")),
        "collectedAt": int(time.time()),
        "source": SOURCE,
        # 断点信息：done 是已抓成功的页号，counts 是每页的条数
        "resume": {
            "done": sorted(page_items),
            "counts": dict((str(p), len(page_items[p])) for p in sorted(page_items)),
            "complete": not failed,
        },
    }
    if extra_total:
        meta["upstreamTotal"] = extra_total
    tmp = meta_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    os.replace(tmp, meta_path)
    return meta


def log(msg):
    print(msg, flush=True)


def rel_or_abs(path):
    """相对站点目录的路径；跨盘时 relpath 会抛 ValueError，这时给绝对路径。"""
    try:
        return os.path.relpath(path, SITE)
    except ValueError:
        return path


def main():
    ap = argparse.ArgumentParser(description="Midlibrary 采集段")
    ap.add_argument("--all", action="store_true", help="抓全量（212 页）")
    ap.add_argument("--pick", action="store_true", help="抓站方精选（默认）")
    ap.add_argument("--pages", type=int, default=0, help="只抓前 N 页（调试）")
    ap.add_argument("--out", default="", help="输出路径（相对站点目录）")
    ap.add_argument("--force", action="store_true", help="忽略断点，全部重抓")
    args = ap.parse_args()

    scope = "all" if args.all else "pick"
    # 页数：全量用上游公布的 212 页；精选用 PICK_TOTAL 按每页 48 条折算。
    if scope == "all":
        target = TOTAL_PAGES
    else:
        target = (PICK_TOTAL + PAGE_SIZE_UPSTREAM - 1) // PAGE_SIZE_UPSTREAM
    if args.pages > 0:
        target = min(target, args.pages)

    items_path = os.path.join(SITE, "data", "items.json")
    if args.out:
        items_path = args.out if os.path.isabs(args.out) else os.path.join(SITE, args.out)
    meta_path = os.path.join(os.path.dirname(items_path), "meta.json")
    data_dir = os.path.dirname(items_path)
    if data_dir and not os.path.isdir(data_dir):
        os.makedirs(data_dir)

    log("采集 Midlibrary（scope=%s，目标 %d 页）" % (scope, target))
    log("  输出 %s" % rel_or_abs(items_path))
    if PROXY:
        log("  代理 %s" % PROXY)

    done, page_items = ([], {}) if args.force else load_resume(items_path, meta_path, scope)
    if done:
        log("  断点续跑：已有 %d 页（%s）"
            % (len(done), ("%d–%d" % (min(done), max(done))) if done else "-"))
    # 保护：同一范围已有更完整的采集结果时，一次调试跑不该把它覆盖掉。
    if done and max(done) > target and not args.force:
        log("  已有 %d 页的结果（最多到第 %d 页），本次只抓 %d 页。"
            % (len(done), max(done), target))
        log("  为避免覆盖，用 --out 换个输出文件，或加 --force 重抓。")
        sys.exit(2)

    done_set = set(done)
    pending = [p for p in range(1, target + 1) if p not in done_set]
    failed = []
    extra_total = 0
    end_of_list = False
    t0 = time.time()

    if pending:
        opener = build_opener()
        with concurrent.futures.ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            i = 0
            while i < len(pending) and not end_of_list:
                wave = pending[i:i + FETCH_WORKERS]
                i += len(wave)
                futures = dict((pool.submit(fetch_page, opener, p, scope, log), p)
                               for p in wave)
                results = []
                for fut in concurrent.futures.as_completed(futures):
                    results.append((futures[fut], fut.result()))
                results.sort()
                for p, res in results:
                    if res is None:
                        failed.append(p)
                        log("  [%d/%d] page %-4d 抓取失败（本页无数据）"
                            % (len(page_items) + 1, target, p))
                        continue
                    tiles, text = res
                    if not extra_total:
                        extra_total = upstream_total(text)
                    if not tiles:
                        # 列表到此为止：正常结束，不是失败
                        end_of_list = True
                        log("  [%d/%d] page %-4d 空页，列表到此结束"
                            % (len(page_items) + 1, target, p))
                        break
                    page_items[p] = [normalize(t) for t in tiles]
                    done_set.add(p)
                    total = len(flatten(page_items))
                    log("  [%d/%d] page %-4d +%-3d 条  累计 %d 条  用时 %.1fs"
                        % (len(page_items), target, p, len(tiles), total,
                           time.time() - t0))
                # 每波落一次盘：中断后能接着抓，不用从头再来
                write_outputs(items_path, meta_path, scope, page_items, failed, extra_total)
    else:
        log("  没有待抓的页（已全部抓过）；用 --force 可强制重抓。")

    meta = write_outputs(items_path, meta_path, scope, page_items, failed, extra_total)
    if meta is None:
        # 一页都没抓到：原文件保持不变（write_outputs 里挡住了空覆盖）
        log("")
        log("一页都没抓到，%s 保持原样不动。" % rel_or_abs(items_path))
        if failed:
            log("  有 %d 页没抓到：%s" % (len(failed), failed))
        sys.exit(2)
    log("")
    log("共 %d 条 / %d 页  用时 %.1fs" % (meta["count"], meta["pages"], time.time() - t0))
    log("  kind 分布 %s" % meta["kinds"])
    log("  category 分布 %s" % meta["categories"])
    log("  isPick %d · testedMark %d · isPublicDomain %d · 有 sheet %d"
        % (meta["isPick"], meta["testedMark"], meta["isPublicDomain"], meta["withSheet"]))
    if extra_total:
        log("  上游分面报的总条数 %d（与抓到 %d 条对照）" % (extra_total, meta["count"]))
    if failed:
        log("  有 %d 页没抓到：%s" % (len(failed), failed))
        log("  重跑同一条命令即可续跑（已成功的页不会重复抓）。")
        sys.exit(2)


if __name__ == "__main__":
    main()
