# -*- coding: utf-8 -*-
"""从 Midjourney 官网 Explore 榜采集社区作业与成图元数据。

数据源：Midjourney 官网 Explore 的匿名只读接口
    GET https://www.midjourney.com/api/explore?page=N&feed=top&_ql=explore
前端 bundle（/public/out/clientSideEntry-*.js）里的实况：
    · 页面所有 tab（styles_top / styles_hot / top / hot …）都调这一个接口，
      feed 永远是 top —— tab 只是界面叫法，实测各 tab 返回字节完全一致。
    · page 从 0 开始；page=4 起返回空数组，公开榜单共 4 页 200 条。
    · 必带请求头 X-CSRF-Protection: 1 与 _ql: explore。

Cloudflare 的两道坎（实测）：
  1. 首页与接口会按 TLS 指纹（JA3）拦掉非浏览器客户端。Python 的 urllib
     指纹会被判 403，必须先取到 Cloudflare 下发的 __cf_bm cookie。
  2. cdn.midjourney.com 的图片必须带着同一个 __cf_bm cookie 才会返回图片，
     否则一律 403（哪怕路径完全正确）。所以脚本用同一个 CookieJar 先访问
     explore 页「拿通行证」，再访问接口与 CDN。

产出：
    data/jobs.json  采集到的作业（精简字段），供 manifest.py 使用
    data/meta.json  采集统计（页数、条数、各分布）

用法：
    python extract.py                  # 全量采集（4 页）
    python extract.py --pages 2        # 只采前 N 页（调试）
"""
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)                      # sites/midjourney-explore
sys.path.insert(0, SITE)

from config import API, FEED, PAGE_COUNT, PAGE_START, PROXY, UA  # noqa: E402

RETRY = 20

# 浏览器化的最小请求头集合。缺 Referer / Sec-Fetch-* 会被 CDN 直接 403。
BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
}

PAGE_HEADERS = dict(BROWSER_HEADERS, **{
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
})

API_HEADERS = dict(BROWSER_HEADERS, **{
    "Accept": "application/json",
    "Referer": "https://www.midjourney.com/explore?tab=styles_top",
    "X-CSRF-Protection": "1",
    "_ql": "explore",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
})

# 放行页面用的 URL：访问一次即可拿到 __cf_bm
CLEARANCE_URL = "https://www.midjourney.com/explore?tab=styles_top"


def build_opener():
    """带 CookieJar 的 opener；同一份 cookie 要同时用于接口与 CDN。"""
    handlers = []
    if PROXY:
        handlers.append(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    jar = http.cookiejar.CookieJar()
    handlers.append(urllib.request.HTTPCookieProcessor(jar))
    return urllib.request.build_opener(*handlers), jar


def clear_cloudflare(opener, jar, log):
    """访问 explore 页拿 __cf_bm。失败重试，成功返回 cookie 名字列表。"""
    for attempt in range(RETRY):
        try:
            req = urllib.request.Request(CLEARANCE_URL, headers=PAGE_HEADERS)
            with opener.open(req, timeout=45) as resp:
                resp.read()
            names = sorted({c.name for c in jar})
            log("  Cloudflare 通行证就绪：%s" % ", ".join(names))
            return names
        except Exception as e:
            wait = 4 * (attempt + 1)
            log("    第 %d 次取通行证失败(%s)，%ds 后重试" % (attempt + 1, type(e).__name__, wait))
            time.sleep(wait)
    log("    取通行证失败，继续尝试接口（可能仍可用）")


def fetch_page(opener, page, log):
    """取一页作业，返回 list；失败按指数退避重试。"""
    url = API + "?" + urllib.parse.urlencode(
        {"page": page, "feed": FEED, "_ql": "explore"})
    last = None
    for attempt in range(RETRY):
        try:
            req = urllib.request.Request(url, headers=API_HEADERS)
            with opener.open(req, timeout=60) as resp:
                data = json.load(resp)
            return data if isinstance(data, list) else []
        except Exception as e:
            last = e
            # 限流窗口可能很长（实测 8 次 75s 间隔仍被拒），退避要够狠
            wait = min(600, 45 * attempt)
            log("    page %d 第 %d 次失败(%s)，%ds 后重试"
                % (page, attempt + 1, type(e).__name__, wait))
            time.sleep(wait)
    log("    page %d 最终失败：%s" % (page, last))
    # None = 这一页抓取失败（区别于 [] = 榜单到此为止，是正常结束）
    return None


def prompt_text(prompt):
    """把 decodedPrompt 拼回可读的提示词原文。"""
    dp = prompt.get("decodedPrompt") or []
    parts = []
    for seg in dp:
        c = (seg.get("content") or "").strip()
        if not c:
            continue
        w = seg.get("weight")
        if w is not None and w != 1:
            parts.append("%s::%s" % (c, w))
        else:
            parts.append(c)
    return " ".join(parts).strip()


def aspect_of(job):
    """从 prompt.ar 或 width/height 推出宽高比，归一到最简比例。

    上游的 ar 字段是 {"w": 9, "h": 16} 这样的字典（部分条目为 null），
    不是 "9:16" 字符串，必须两种形态都处理。
    """
    ar = job.get("prompt", {}).get("ar")
    if isinstance(ar, dict) and ar.get("w") and ar.get("h"):
        w, h = int(ar["w"]), int(ar["h"])
    elif isinstance(ar, str) and ":" in ar:
        return ar.replace("/", ":")
    else:
        w, h = job.get("width") or 0, job.get("height") or 0
    if not w or not h:
        return ""
    from math import gcd
    g = gcd(w, h)
    return "%d:%d" % (w // g, h // g)


def style_refs(prompt):
    """风格参考（sref）码列表 —— 就是原站点显示的 p 值（如 sref 2918660786）。

    上游 prompt.styleRef 是数组，每项形如 {"t": ..., "content": ..., "weight": 1}：
      · t == "seed" → content 是数字码，就是原站的 sref 码
      · t == "url"  → content 是图片短链（https://s.mj.run/...），图片型参考，不是码

    实测（2026-11-02，4 页 200 条）：t 只有 seed / url 两种，
    17 个 seed 码分布在 13 条作业上；带码作业在原站 /styles/0_<码> 页面
    确实渲染成「sref <码>」（已实地核对，非推断）。

    旧实现把 t 当成码本身 —— t == "seed" 时会存下字面量 "seed"，真码全丢。
    """
    out = []
    for item in (prompt.get("styleRef") or []):
        if not isinstance(item, dict):
            continue
        t = item.get("t")
        content = str(item.get("content") or "").strip()
        if t == "url":
            continue                       # 图片型参考，不是码
        if t in ("seed", "sref", "style"):
            code = content                 # 数值码在 content 里
        else:
            code = str(t).strip()          # 兜底：t 本身就是码的老形状
        if not code or code == "url" or code.startswith("http"):
            continue
        if code not in out:
            out.append(code)
    return out


def slim(job):
    """只留 manifest.py 需要的字段，避免 data/jobs.json 过大。"""
    if not job.get("id"):
        return None
    prompt = job.get("prompt") or {}
    text = prompt_text(prompt)
    if not text:
        return None
    items = job.get("items") or []
    # 作业的每一格都是独立成图（0_0、0_1 …）。
    # 上游给格子打了 server_filtered 标记（Explore 榜每 4 格只展示 1 格），
    # 但实测被标记的格子在 cdn.midjourney.com 上同样能取到完整图片，
    # 只是官网首页不展示它们。因此本站全部收录（每条 4 格）。
    idx = list(range(len(items)))
    if not idx:
        return None
    return {
        "id": job["id"],
        "prompt": text,
        "version": prompt.get("version") or "",
        "ar": aspect_of(job),
        "width": job.get("width") or 0,
        "height": job.get("height") or 0,
        "username": job.get("username_v2") or "",
        "displayName": job.get("display_name") or job.get("username_v2") or "",
        "enqueueTime": job.get("enqueue_time") or 0,
        "jobType": job.get("job_type") or "",
        "hasStyleRef": 1 if (prompt.get("styleRef") or []) else 0,
        # p 值：风格参考码（原站点开图片会显示「sref 2918660786」）
        "sref": style_refs(prompt),
        "indices": idx,
        "totalIndices": len(items),
        "sourceUrl": "https://www.midjourney.com/explore?tab=styles_top",
    }


def main():
    args = sys.argv[1:]
    pages = PAGE_COUNT
    raw_path = ""
    i = 0
    while i < len(args):
        if args[i] == "--pages" and i + 1 < len(args):
            pages = int(args[i + 1]); i += 2
        elif args[i] == "--from-raw" and i + 1 < len(args):
            raw_path = args[i + 1]; i += 2
        else:
            i += 1

    def log(m):
        print(m, flush=True)

    data_dir = os.path.join(SITE, "data")
    os.makedirs(data_dir, exist_ok=True)
    main_path = os.path.join(data_dir, "jobs.json")
    draft_path = os.path.join(data_dir, "jobs.new.json")

    def existing_count():
        """磁盘上已有的作业条数（覆盖守卫用）。"""
        if not os.path.exists(main_path):
            return 0
        try:
            with open(main_path, encoding="utf-8") as f:
                return len(json.load(f))
        except Exception:
            return 0

    old_count = existing_count()

    def write_draft(jobs):
        """草稿落盘：限流窗口可能很长，中途失败也要保住已抓到的页。

        草稿写 jobs.new.json，不碰正式文件 —— 正式文件只在本轮结果完整时替换。
        否则一次「所有页面 429」的失败就会把已有数据清空：旧实现末尾无条件
        save(jobs)，而全页失败时 jobs 是空数组，200 条作业当场蒸发，退出码还是 0。
        """
        tmp = draft_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False)
        os.replace(tmp, draft_path)

    opener = jar = None
    raw_pages = None
    if raw_path:
        log("复放本地缓存的原始响应：%s（不请求上游）" % raw_path)
        with open(raw_path, encoding="utf-8") as f:
            raw_pages = json.load(f)
    else:
        log("采集 Midjourney Explore 榜（feed=%s）" % FEED)
        if PROXY:
            log("  代理 %s" % PROXY)
        opener, jar = build_opener()
        clear_cloudflare(opener, jar, log)

    jobs = []
    seen = set()
    dup = 0
    skipped = 0
    failed = False
    t0 = time.time()
    page = PAGE_START

    def absorb(items):
        """把一页原始作业并进结果（去重 + 丢弃没有提示词的条目）。"""
        nonlocal dup, skipped
        for it in items:
            s = slim(it)
            if s is None:
                skipped += 1
                continue
            if s["id"] in seen:
                dup += 1
                continue
            seen.add(s["id"])
            jobs.append(s)

    if raw_pages is not None:
        for idx, items in enumerate(raw_pages):
            if not items:
                continue
            absorb(items)
            log("  缓存 page %d 累计 %d 条作业" % (idx, len(jobs)))
    else:
        while page < PAGE_START + pages:
            items = fetch_page(opener, page, log)
            if items is None:
                failed = True
                log("  page %d 抓取失败，本次结果不完整" % page)
                break
            if not items:
                log("  page %d 为空，榜单到此结束" % page)
                break
            absorb(items)
            log("  page %d 累计 %d 条作业  %.0fs" % (page, len(jobs), time.time() - t0))
            write_draft(jobs)          # 每页存一次（草稿）
            page += 1

    # 榜单按热度排序，抓取顺序即热度序；同热度按 id 保证构建可复现
    jobs.sort(key=lambda j: j["id"])
    write_draft(jobs)

    # 守卫：结果不完整就不替换正式数据。
    # 典型触发场景：上游所有页面 429（IP 级限流），旧实现末尾无条件 save(jobs)，
    # 而全页失败时 jobs 是空数组 —— 200 条作业当场蒸发，退出码还是 0。
    if failed:
        log("  拒绝覆盖 data/jobs.json：有页面抓取失败，本次结果不完整")
        log("  原文件保持不变，新数据留在 data/jobs.new.json")
        sys.exit(2)
    if not jobs and old_count:
        log("  拒绝覆盖 data/jobs.json：本轮一条作业都没解析出来")
        log("  原文件保持不变，新数据留在 data/jobs.new.json")
        sys.exit(2)
    if len(jobs) < old_count:
        log("  注意：本次 %d 条少于磁盘上的 %d 条（上游榜单变了，或有作业字段缺失）"
            % (len(jobs), old_count))
    os.replace(draft_path, main_path)
    log("  已更新 data/jobs.json：%d 条（原 %d 条）" % (len(jobs), old_count))

    import collections
    n_images = sum(len(j["indices"]) for j in jobs)
    meta = {
        "feed": FEED,
        "pages": pages,
        "jobs": len(jobs),
        "images": n_images,
        "dup": dup,
        "skipped": skipped,
        "versions": collections.Counter(j["version"] or "-" for j in jobs).most_common(),
        "aspects": collections.Counter(j["ar"] or "-" for j in jobs).most_common(),
        "authors": len({j["username"] for j in jobs}),
        "withStyleRef": sum(j["hasStyleRef"] for j in jobs),
        # 带 sref 数字码的作业数 / 码总数（与 withStyleRef 不同：
        # 后者只说明这条作业挂了风格参考，可能是图片型（url），没有码）
        "withStyleCode": sum(1 for j in jobs if j.get("sref")),
        "styleRefCodes": sum(len(j.get("sref") or []) for j in jobs),
        "collectedAt": int(time.time()),
    }
    with open(os.path.join(data_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    log("\n共 %d 条作业 / %d 张成图，写入 data/jobs.json"
        % (meta["jobs"], meta["images"]))
    log("版本：%s" % meta["versions"])
    log("宽高比：%s" % meta["aspects"])
    log("作者 %d 位 · 带风格参考 %d 条，其中带 sref 码 %d 条 / 共 %d 个码"
        % (meta["authors"], meta["withStyleRef"],
           meta["withStyleCode"], meta["styleRefCodes"]))


if __name__ == "__main__":
    main()
