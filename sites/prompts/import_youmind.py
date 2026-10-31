# -*- coding: utf-8 -*-
"""从 youmind.com 官方内部 API 按模型全量导入提示词案例

数据源: POST https://youmind.com/youmarketing-api/prompts
        (awesome-gpt-image-2 GitHub 仓库的上游 CMS，比仓库 README 多 ~20 倍案例)

一个模型一份产出，互不覆盖：
  gpt-image-2       → img/gpt2/  + data/prompts_gpt2.json   (~22k 图)
  nano-banana-pro   → img/nbpro/ + data/prompts_nbpro.json  (~40k 图)

用法:
  python import_youmind.py                          # 默认导入 gpt-image-2
  python import_youmind.py --model nano-banana-pro   # 导入 Nano Banana Pro
  python import_youmind.py --model all               # 两个模型都导
  python import_youmind.py --meta-only               # 只拉元数据缓存，不下载图
  python import_youmind.py --limit 50                # 只导前 50 条（试点）

字段映射（双语双轨）:
  prompt    = translatedContent（中文展示，Raycast 占位符替换为 default 值）
  promptRaw = content（英文原文，占位符原样保留，灯箱复制用）
  标签: featured → 精选; needReferenceImages → 需参考图;
        promptCategories（或 gpt2 的 id→cats 映射）→ 官方分类中文标题
  model      = config.MODELS 的键（imge-2 / nanobanana），页面按它做筛选
  modelLabel = config.MODELS 的展示名

产出后:
  python scripts/manifest.py && python ../tools/build.py --site prompts
"""
import argparse, json, os, re, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from config import MODELS  # noqa: E402

API_URL = "https://youmind.com/youmarketing-api/prompts"
ORIGIN = "https://youmind.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"}
DEFAULT_PROXY = "http://127.0.0.1:7897"   # youmind 域族被 DNS 污染，必须走本机代理
MIN_BYTES = 1024

# 上游模型 → 本站的目录 / 模型键 / 缓存 / 分类来源。
# key 同时决定 originId 前缀（gpt2-123 / nbpro-123），两站 id 空间互不干扰。
SPECS = {
    "gpt-image-2": {
        "key": "gpt2",
        "model": "imge-2",
        "img": "img/gpt2",
        "cache": "data/gpt2_site_meta.json",
        "referer": "https://youmind.com/gpt-image-2-prompts/explore",
        "id2cats": True,     # 记录不带 promptCategories，靠 id→slug 映射表补齐（tag_categories.py）
    },
    "nano-banana-pro": {
        "key": "nbpro",
        "model": "nanobanana",
        "img": "img/nbpro",
        "cache": "data/nbpro_site_meta.json",
        "referer": "https://youmind.com/nano-banana-pro-prompts/explore",
        "id2cats": True,     # promptCategories 全为空，同样靠 categories 过滤反查
    },
}

RAYCAST_ESC = re.compile(r'\{argument name=\\"[^"\\]+\\" default=\\"([^"\\]*)\\"\}')
RAYCAST_PLAIN = re.compile(r'\{argument name="[^"]+" default="([^"]*)"\}')


def raycast_clean(text):
    text = RAYCAST_ESC.sub(r"\1", text)
    return RAYCAST_PLAIN.sub(r"\1", text)


def curl_json(body, proxy, referer):
    """curl 走代理 POST API（urllib 对该站点会被代理策略干扰，curl 实测稳定）"""
    cmd = ["curl", "-x", proxy, "-s", "--max-time", "90", "-X", "POST", API_URL,
           "-H", "Content-Type: application/json",
           "-H", f"Origin: {ORIGIN}",
           "-H", f"Referer: {referer}",
           "-H", f"User-Agent: {UA['User-Agent']}",
           "-d", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise IOError(f"curl 失败 rc={r.returncode}")
    d = json.loads(r.stdout)
    if d.get("error"):
        raise IOError(f"上游返回错误: {d['error']}")
    return d


def fetch_all_meta(upstream, proxy, referer, locale="zh-CN"):
    """分页拉全量元数据，直到 hasMore=False"""
    page, seen, total = 1, {}, None
    while True:
        d = curl_json({"model": upstream, "page": page, "limit": 100,
                       "locale": locale}, proxy, referer)
        total = d.get("total") or total
        ps = d.get("prompts", [])
        for p in ps:
            seen[p["id"]] = p
        print(f"  page{page}/{d.get('totalPages', '?')}: +{len(ps)} "
              f"(累计 {len(seen)}{'/' + str(total) if total else ''})", flush=True)
        if not d.get("hasMore") or not ps:
            break
        page += 1
    return list(seen.values())


def download(url, path, proxy):
    if os.path.exists(path) and os.path.getsize(path) > MIN_BYTES:
        return "skip"
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        opener = urllib.request.build_opener()
    req = urllib.request.Request(url, headers=UA)
    with opener.open(req, timeout=40) as r:
        data = r.read()
    if len(data) <= MIN_BYTES:
        raise IOError(f"响应过小 {len(data)}B")
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)
    return "ok"


def ext_of(url):
    m = re.search(r"\.(jpe?g|png|webp|gif)(?:[?#]|$)", url, re.I)
    return (m.group(1).lower() if m else "jpg").replace("jpeg", "jpg")


def load_category_maps(key):
    """官方分类映射：{id: [slug,...]} + {slug: 中文名}。文件缺失时返回空（分类标签跳过）。

    id→slug 按模型分开（<key>_id2cats.json，由 tag_categories.py 生成）；
    slug→中文名两个模型共用同一份 41 个官方分类表。
    """
    id2cats, titles = {}, {}
    p1 = os.path.join(HERE, "data", f"{key}_id2cats.json")
    p2 = os.path.join(HERE, "data", "gpt2_categories.json")
    if os.path.exists(p1):
        with open(p1, encoding="utf-8") as f:
            id2cats = json.load(f)
    if os.path.exists(p2):
        with open(p2, encoding="utf-8") as f:
            # 标题里的 " / " 换成 "·"：extract.py 把 / 当标签分隔符，避免「人像 / 自拍」被拆成两条
            titles = {slug: v.get("zh", slug).replace(" / ", "·")
                      for slug, v in json.load(f).items()}
    return id2cats, titles


def import_model(upstream, spec, args):
    key = spec["key"]
    print(f"\n=== {upstream} → {spec['img']} / model={spec['model']} ===", flush=True)
    cache = os.path.join(HERE, spec["cache"])
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            prompts = json.load(f)
        print(f"元数据缓存: {len(prompts)} 条（{spec['cache']}）")
    else:
        print(f"拉取元数据（locale=zh-CN，走 {args.proxy}）…", flush=True)
        prompts = fetch_all_meta(upstream, args.proxy, spec["referer"])
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(prompts, f, ensure_ascii=False)
        print(f"✓ 元数据 {len(prompts)} 条 → {spec['cache']}")
    if args.limit:
        prompts = prompts[:args.limit]

    # 展平：一张图一条记录
    jobs = []
    out_dir = os.path.join(HERE, spec["img"])
    os.makedirs(out_dir, exist_ok=True)
    for p in prompts:
        media = p.get("media") or []
        thumbs = p.get("mediaThumbnails") or []
        for n, url in enumerate(media, 1):
            name = f"i{p['id']}_{n}.{ext_of(url)}"
            # 缩略图：上游 mediaThumbnails 与 media 按下标一一对应；缺失时回退原图 URL
            thumb_url = thumbs[n - 1] if n - 1 < len(thumbs) else url
            jobs.append((p, url, thumb_url, os.path.join(out_dir, name), name))

    if args.meta_only:
        print(f"--meta-only：跳过 {len(jobs)} 张图下载")
        return None

    print(f"下载 {len(jobs)} 张生成图（{args.workers} 并发，幂等）…", flush=True)
    def fetch(job):
        p, url, thumb_url, path, name = job
        try:
            return name, download(url, path, args.proxy), ""
        except Exception as e:
            return name, "fail", str(e)

    stats = {"ok": 0, "skip": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, (name, status, err) in enumerate(pool.map(fetch, jobs), 1):
            stats[status] += 1
            if status == "fail":
                print(f"  ✗ {name}: {err}", flush=True)
            if i % 1000 == 0:
                print(f"  … {i}/{len(jobs)}  ✓{stats['ok']} 跳过{stats['skip']} 失败{stats['fail']}",
                      flush=True)
    print(f"下载: ✓{stats['ok']}  跳过{stats['skip']}  失败{stats['fail']}\n")

    records = []
    id2cats, cat_titles = load_category_maps(key)
    for p, url, thumb_url, path, name in jobs:
        if not (os.path.exists(path) and os.path.getsize(path) > MIN_BYTES):
            continue
        zh = (p.get("translatedContent") or p.get("content") or "").strip()
        tags = []
        if p.get("featured"):
            tags.append("精选")
        if p.get("needReferenceImages"):
            tags.append("需参考图")
        slugs = (id2cats.get(str(p["id"]), []) if spec["id2cats"] else []) + \
                list(p.get("promptCategories") or [])
        for slug in slugs:
            t = cat_titles.get(slug, slug)
            if t and t not in tags:
                tags.append(t)
        author = (p.get("author") or {}).get("name", "")
        records.append({
            "file": f"{spec['img']}/{name}",
            "url": url,
            "thumbUrl": thumb_url,
            "model": spec["model"],
            "modelLabel": MODELS.get(spec["model"], spec["model"]),
            "title": (p.get("title") or "").strip(),
            "prompt": raycast_clean(zh),
            "tags": ",".join(tags),
            "promptRaw": (p.get("content") or "").strip(),
            "author": author,
            "sourceUrl": p.get("sourceLink") or "",
            "published": (p.get("sourcePublishedAt") or "")[:10],
            "originId": f"{key}-{p['id']}",
        })

    out_path = os.path.join(HERE, "data", f"prompts_{key}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    print(f"✓ {len(records)} 条记录 → data/prompts_{key}.json")
    return len(records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-image-2",
                    help="gpt-image-2 / nano-banana-pro / all")
    ap.add_argument("--proxy", default=DEFAULT_PROXY,
                    help="本机代理（youmind 域被 DNS 污染时必需）")
    ap.add_argument("--limit", type=int, default=0, help="只导前 N 条（0=全部）")
    ap.add_argument("--meta-only", action="store_true", help="只拉元数据缓存")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    targets = list(SPECS) if args.model == "all" else [args.model]
    unknown = [m for m in targets if m not in SPECS]
    if unknown:
        raise SystemExit(f"✗ 未知模型 {unknown}，可选：{', '.join(SPECS)} / all")

    for upstream in targets:
        import_model(upstream, SPECS[upstream], args)

    print("\n下一步: python scripts/manifest.py && python ../tools/build.py --site prompts")


if __name__ == "__main__":
    main()
