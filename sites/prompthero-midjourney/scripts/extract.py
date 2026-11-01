# -*- coding: utf-8 -*-
"""从 PromptHero 采集 Midjourney 提示词与成图元数据。

数据源：PromptHero 前端的 tRPC 端点
    GET https://prompthero.com/api/trpc/prompt.search?input={"json":{...}}
匿名可调；网页端的「登录解锁更多」只作用于 UI，接口侧无限制。

采集两趟：
    SFW  ：不传 nsfwOnly —— 上游默认过滤掉 isNsfw 的条目
    NSFW ：nsfwOnly=true —— 只返回 isNsfw 的条目
两趟结果无交集，各自去重后合并。

上游的两个坑（已实测）：
  1. 分页在并列排序值处漂移：翻完 322 页拿到 15,456 条，去重后只有 10,339 条，
     重复项数据完全一致（同 prompt.id、同计数），按 slug 去重即可。
  2. 限流：并发 6 时会返回 429。串行 + 退避重试可稳定跑完全量。

产出：
    data/prompts.json  采集到的原始条目（精简字段），供 manifest.py 使用
    data/meta.json     采集统计（页数、去重数、各分布）

用法：
    python extract.py                    # 全量采集
    python extract.py --pages 322        # 只采 SFW 的前 N 页（调试）
    python extract.py --nsfw-pages 65     # 只采 NSFW 的前 N 页
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)                      # sites/prompthero-midjourney
sys.path.insert(0, SITE)

from config import API, MODEL, PROXY, UA, X_HEADERS  # noqa: E402

SFW_PAGES = 322
NSFW_PAGES = 65
PAGE_SIZE = 48
RETRY = 5


def opener():
    handlers = []
    if PROXY:
        handlers.append(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def fetch_page(page, nsfw_only, log):
    """取一页，返回 items 列表。失败按指数退避重试。"""
    body = {"model": MODEL, "page": page, "pageSize": PAGE_SIZE}
    if nsfw_only:
        body["nsfwOnly"] = True
    url = API + "?" + urllib.parse.urlencode({"input": json.dumps({"json": body})})
    last = None
    for attempt in range(RETRY):
        try:
            req = urllib.request.Request(url, headers=X_HEADERS)
            with opener().open(req, timeout=60) as resp:
                data = json.load(resp)
            return data["result"]["data"]["json"].get("items", [])
        except Exception as e:
            last = e
            wait = 5 * (attempt + 1)
            log("    page %d 第 %d 次失败(%s)，%ds 后重试"
                % (page, attempt + 1, type(e).__name__, wait))
            time.sleep(wait)
    log("    page %d 最终失败：%s" % (page, last))
    return []


def slim(it):
    """只留 manifest.py 需要的字段，避免 data/prompts.json 过大。"""
    p = it.get("prompt") or {}
    a = it.get("asset") or {}
    if not p.get("slug") or not a.get("storageKey"):
        return None
    dc = {c["name"]: c["url"] for c in (a.get("displayCopies") or [])}
    return {
        "slug": p["slug"],
        "id": p.get("id") or "",
        "prompt": p.get("prompt") or "",
        "title": p.get("title") or "",
        "description": p.get("description") or "",
        "category": p.get("category") or "",
        "modelVersion": p.get("modelUsedVersion") or "",
        "isNsfw": 1 if p.get("isNsfw") else 0,
        "favCount": p.get("favCount") or 0,
        "viewCount": p.get("viewCount") or 0,
        "createdAt": p.get("createdAt") or "",
        "width": a.get("width") or 0,
        "height": a.get("height") or 0,
        "storageKey": a["storageKey"],
        "copies": dc,
    }


def collect(pages, nsfw_only, log):
    out = []
    seen = set()
    dup = 0
    t0 = time.time()
    for page in range(1, pages + 1):
        items = fetch_page(page, nsfw_only, log)
        for it in items:
            s = slim(it)
            if s is None:
                continue
            if s["slug"] in seen:
                dup += 1
                continue
            seen.add(s["slug"])
            out.append(s)
        if page % 25 == 0:
            log("  %s page %d/%d  %d 条  %.0fs"
                % ("NSFW" if nsfw_only else "SFW", page, pages, len(out), time.time() - t0))
    log("  %s 完成：%d 条（去重丢弃 %d）"
        % ("NSFW" if nsfw_only else "SFW", len(out), dup))
    return out


def main():
    args = sys.argv[1:]
    sfw_pages = NSFW_PAGES
    nsfw_pages = NSFW_PAGES
    only = None
    i = 0
    while i < len(args):
        if args[i] == "--pages" and i + 1 < len(args):
            sfw_pages = int(args[i + 1]); i += 2
        elif args[i] == "--nsfw-pages" and i + 1 < len(args):
            nsfw_pages = int(args[i + 1]); i += 2
        elif args[i] == "--only" and i + 1 < len(args):
            only = args[i + 1]; i += 2
        else:
            i += 1

    def log(m):
        print(m, flush=True)

    log("采集 PromptHero · %s" % MODEL)
    if PROXY:
        log("  代理 %s" % PROXY)

    rows = []
    if only in (None, "sfw"):
        log("\n[SFW]")
        rows += collect(sfw_pages, False, log)
    if only in (None, "nsfw"):
        log("\n[NSFW]")
        rows += collect(nsfw_pages, True, log)

    # 跨集合去重（SFW 与 NSFW 实测无交集，仍做一次保险）
    seen = set()
    uniq = []
    for r in rows:
        if r["slug"] in seen:
            continue
        seen.add(r["slug"])
        uniq.append(r)

    data_dir = os.path.join(SITE, "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "prompts.json"), "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False)

    import collections
    meta = {
        "model": MODEL,
        "sfwPages": sfw_pages,
        "nsfwPages": nsfw_pages,
        "total": len(uniq),
        "nsfw": sum(1 for r in uniq if r["isNsfw"]),
        "categories": collections.Counter(r["category"] or "uncategorized" for r in uniq).most_common(),
        "versions": collections.Counter(r["modelVersion"] or "-" for r in uniq).most_common(),
        "noCopies": sum(1 for r in uniq if not r["copies"]),
        "no1080": sum(1 for r in uniq if "1080" not in r["copies"]),
    }
    with open(os.path.join(data_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    log("\n共 %d 条（NSFW %d），写入 data/prompts.json"
        % (meta["total"], meta["nsfw"]))
    log("分类：%s" % meta["categories"])
    log("版本：%s" % meta["versions"])


if __name__ == "__main__":
    main()
