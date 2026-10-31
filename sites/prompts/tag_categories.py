# -*- coding: utf-8 -*-
"""按 41 个官方分类逐个翻页，建立 提示词id → 分类slug 映射（逐模型）

上游的记录字段里 promptCategories 常常是空的（Nano Banana 全空、gpt-image-2 也靠这张表），
但 API 支持 `categories` 过滤参数 —— 逐类查询再反查 id，就能还原每个提示词属于哪些分类。

产出（每模型一份）：
  data/<key>_site_categories.json   {"<slug>": [id, ...], ...}   断点续抓用
  data/<key>_id2cats.json           {"<id>": ["slug", ...], ...}  导入器消费

用法: python tag_categories.py --model nano-banana-pro [--workers 6] [--proxy http://127.0.0.1:7897]
"""
import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from import_youmind import SPECS, API_URL, ORIGIN, UA  # noqa: E402

CATS = os.path.join(HERE, "data", "gpt2_categories.json")
# 上游服务端把单页钉在 85 条（limit 传 100/200/500 都返回 85），分页按 page+1 递增即可
MAX_PAGES = 400


def curl_page(slug, page, model, proxy, referer):
    body = json.dumps({"model": model, "page": page, "limit": 100,
                       "locale": "zh-CN", "categories": slug})
    cmd = ["curl", "-x", proxy, "-s", "--max-time", "90", "-X", "POST", API_URL,
           "-H", "Content-Type: application/json",
           "-H", f"Origin: {ORIGIN}",
           "-H", f"Referer: {referer}",
           "-H", f"User-Agent: {UA['User-Agent']}", "-d", body]
    for attempt in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        try:
            d = json.loads(r.stdout)
            if d.get("error"):
                raise IOError(d["error"])
            return d
        except Exception:
            if attempt == 2:
                raise IOError(f"{slug} p{page} 失败: {r.stdout[:120]}")
            time.sleep(2 * (attempt + 1))


def fetch_ids(slug, spec, upstream, proxy):
    """拉取某分类下全部提示词 id（分页直到 hasMore=False）

    上游深分页会随机返回空页（hasMore 仍为 True），此时不能当成到底 —— 重试同一页，
    连续 2 次空才算真结束，否则大分类会少抓两三成。
    """
    ids, page, empty = [], 1, 0
    while page <= MAX_PAGES:
        d = curl_page(slug, page, upstream, proxy, spec["referer"])
        ps = d.get("prompts", [])
        if not ps:
            # 第一页就空说明是上游限流/抖动（正常分类不可能 0 条），无条件下重试；
            # 深分页空页时，hasMore=True 才重试，连续 2 次空才算真到底。
            if page == 1 and empty < 3:
                empty += 1
                time.sleep(2 * empty)
                continue
            if d.get("hasMore") and empty < 2:
                empty += 1
                time.sleep(1 + empty)
                continue
            break
        empty = 0
        ids.extend(p["id"] for p in ps)
        if not d.get("hasMore"):
            break
        page += 1
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-image-2", choices=sorted(SPECS),
                    help="上游模型名（gpt-image-2 / nano-banana-pro）")
    ap.add_argument("--proxy", default="http://127.0.0.1:7897")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default="", help="只重抓这些分类（逗号分隔 slug），会覆盖已有结果")
    args = ap.parse_args()

    spec = SPECS[args.model]
    key = spec["key"]
    out = os.path.join(HERE, "data", f"{key}_site_categories.json")
    summary = os.path.join(HERE, "data", f"{key}_id2cats.json")

    with open(CATS, encoding="utf-8") as f:
        cats = json.load(f)
    slugs = sorted(cats)
    print(f"[{args.model} → {key}] 分类 {len(slugs)} 个，{args.workers} 并发…", flush=True)

    mapping = {}
    if os.path.exists(out):   # 断点续抓：已有结果的分类跳过
        with open(out, encoding="utf-8") as f:
            mapping = json.load(f)
    if args.only:
        for slug in (s.strip() for s in args.only.split(",") if s.strip()):
            mapping.pop(slug, None)
    todo = [s for s in slugs if s not in mapping]
    print(f"已完成 {len(slugs) - len(todo)}，待抓 {len(todo)}", flush=True)

    def work(slug):
        t0 = time.time()
        try:
            return slug, fetch_ids(slug, spec, args.model, args.proxy), time.time() - t0, ""
        except Exception as e:
            return slug, None, time.time() - t0, str(e)

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for slug, ids, dt, err in pool.map(work, todo):
            done += 1
            if ids is None:
                print(f"  [{done}/{len(todo)}] ✗ {slug:32s} {err}", flush=True)
                continue
            if not ids:   # 抓空绝不能写入，否则下次续跑会当成「已完成」
                print(f"  [{done}/{len(todo)}] ✗ {slug:32s} 抓空，跳过不写入", flush=True)
                continue
            mapping[slug] = ids
            print(f"  [{done}/{len(todo)}] {slug:32s} {len(ids):5d} 条 ({dt:.0f}s)", flush=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False)

    id2cats = {}
    for slug, ids in mapping.items():
        for i in ids:
            id2cats.setdefault(str(i), []).append(slug)
    with open(summary, "w", encoding="utf-8") as f:
        json.dump(id2cats, f, ensure_ascii=False)
    multi = sum(1 for v in id2cats.values() if len(v) > 1)
    avg = sum(len(v) for v in id2cats.values()) / len(id2cats) if id2cats else 0
    print(f"\n✓ {key}: 覆盖 {len(id2cats)} 个提示词（多分类 {multi}，均 {avg:.1f} 类）→ {summary}")


if __name__ == "__main__":
    main()
