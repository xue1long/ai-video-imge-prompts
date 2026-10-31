# -*- coding: utf-8 -*-
"""从 awesome-gpt-image-2 的 README 导入案例到提示词生图素材库

用法:
  python import_gpt2.py                                    # 默认读相邻仓库 README_zh.md，全量
  python import_gpt2.py --limit 1                          # 只导前 1 个案例（试点）
  python import_gpt2.py --readme <其他README路径> --limit 5

做什么:
  1. 同时解析中文版 README_zh.md（标题/描述/标签）与英文版 README.md（提示词原文），
     按「No. N」编号合并——上游 CMS 会把提示词机翻进各语言版，只有英文版接近作者原文
  2. 下载生成图到 img/gpt2/（幂等：已存在且 >1KB 跳过；一张图一条记录）
  3. 产出 extract.py 可直接消费的 JSON
     prompt 列 = 中文版提示词、Raycast 占位符已替换为其自带 default 值（卡片展示/中文搜索）
     promptRaw = 英文版提示词原文，占位符原样保留（灯箱复制用）

之后运行:
  python extract.py --source sample_prompts.csv --source data/gpt2_prompts.json
  python build_gallery.py

数据来源: github.com/YouMind-OpenLab/awesome-gpt-image-2 （CC BY 4.0，作者/来源逐条保留）
"""
import argparse, json, os, re, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, "..", "..", "awesome-gpt-image-2-main")
DEFAULT_README = os.path.join(SRC_DIR, "README_zh.md")     # 中文版：标题/描述/标签
DEFAULT_README_EN = os.path.join(SRC_DIR, "README.md")     # 英文版：提示词原文
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"}
MIN_BYTES = 1024
IMG_SUBDIR = "img/gpt2"

# Raycast 占位符：{argument name="x" default="y"}（markdown 里引号可能带 \" 转义）
RAYCAST_ESC = re.compile(r'\{argument name=\\"[^"\\]+\\" default=\\"([^"\\]*)\\"\}')
RAYCAST_PLAIN = re.compile(r'\{argument name="[^"]+" default="([^"]*)"\}')

IMG_RE = re.compile(r'<img src="(https://cms-assets[^"]+)"', re.I)
AUTHOR_RE = re.compile(r'\*\*作者:\*\* \[([^\]]+)\]\(([^)]+)\)')
SOURCE_RE = re.compile(r'\*\*来源:\*\* \[([^\]]+)\]\(([^)]+)\)')
PUB_RE = re.compile(r'\*\*发布时间:\*\* ([^\n]+)')
CODE_RE = re.compile(r"```\n(.*?)\n```", re.S)


def raycast_clean(text):
    text = RAYCAST_ESC.sub(r"\1", text)
    return RAYCAST_PLAIN.sub(r"\1", text)


def section(secs, emoji):
    """按 emoji 前缀取章节正文（中英版标题不同：📝 提示词 / 📝 Prompt）。"""
    for k, v in secs.items():
        if k.startswith(emoji):
            return v
    return ""


def parse_cases(md):
    """按 '### No. N:' 切块，返回结构化案例列表（中英版通用）。"""
    cases = []
    for block in re.split(r"(?m)^### No\. ", md)[1:]:
        head = block.splitlines()[0]
        m = re.match(r"(\d+):\s*(.+)", head)
        if not m:
            continue
        no, title = m.group(1), m.group(2).strip()

        secs = {}
        for part in re.split(r"(?m)^#### ", block)[1:]:
            nl = part.find("\n")
            secs[part[:nl].strip()] = part[nl + 1:]

        code = CODE_RE.search(section(secs, "📝"))
        prompt = code.group(1).strip() if code else ""

        detail = section(secs, "📌")
        author = AUTHOR_RE.search(detail)
        source = SOURCE_RE.search(detail)
        pub = PUB_RE.search(detail)
        images = IMG_RE.findall(block)

        tags = []
        if "Featured-gold" in block:
            tags.append("精选")
        if "Raycast_Friendly" in block:
            tags.append("Raycast")

        cases.append({
            "no": int(no),
            "title": title,
            "prompt": prompt,
            "images": images,
            "tags": tags,
            "author": author.group(1) if author else "",
            "sourceUrl": source.group(2) if source else "",
            "published": pub.group(1).strip() if pub else "",
        })
    cases.sort(key=lambda c: c["no"])
    return cases


def download(url, path, proxy=""):
    if os.path.exists(path) and os.path.getsize(path) > MIN_BYTES:
        return "skip"
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        opener = urllib.request.build_opener()
    req = urllib.request.Request(url, headers=UA)
    with opener.open(req, timeout=30) as r:
        data = r.read()
    if len(data) <= MIN_BYTES:
        raise IOError(f"响应过小 {len(data)}B")
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--readme", default=DEFAULT_README,
                    help="中文版 README（标题/描述/标签/展示用提示词）")
    ap.add_argument("--readme-en", default=DEFAULT_README_EN,
                    help="英文版 README（提示词原文，复制用）；找不到对应案例时回退中文版")
    ap.add_argument("--limit", type=int, default=0, help="只导前 N 个案例（0=全部）")
    ap.add_argument("--out", default="data/gpt2_prompts.json")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--proxy", default="",
                    help="本机代理，如 http://127.0.0.1:7890（youmind 域被 DNS 污染时需要）")
    args = ap.parse_args()

    def resolve(p):
        return p if os.path.isabs(p) else os.path.join(HERE, p)

    with open(resolve(args.readme), encoding="utf-8") as f:
        cases = parse_cases(f.read())
    with open(resolve(args.readme_en), encoding="utf-8") as f:
        en_cases = parse_cases(f.read())
    # 合并：英文版 README 有多个系列各自从 No.1 重新编号，按编号会错配；
    # 生成图 URL 在两语言版完全一致 → 优先按首图 URL 匹配，编号做兜底
    en_by_img, en_by_no = {}, {}
    for e in en_cases:
        if e["images"] and e["images"][0] not in en_by_img:
            en_by_img[e["images"][0]] = e
        if e["no"] not in en_by_no:
            en_by_no[e["no"]] = e
    fallback = 0
    for c in cases:
        e = en_by_img.get(c["images"][0]) if c["images"] else None
        if e is None:
            e = en_by_no.get(c["no"])
        if e and e["prompt"]:
            c["prompt_en"] = e["prompt"]
        else:
            c["prompt_en"] = c["prompt"]
            fallback += 1
    if args.limit:
        cases = cases[:args.limit]
    if fallback:
        print(f"⚠ {fallback} 个案例无英文版提示词，回退用中文版\n")
    total_imgs = sum(len(c["images"]) for c in cases)
    print(f"解析 {len(cases)} 个案例 · {total_imgs} 张生成图\n")

    # 展平：一张图一条记录
    jobs, records = [], []
    out_dir = os.path.join(HERE, IMG_SUBDIR)
    os.makedirs(out_dir, exist_ok=True)
    for c in cases:
        for n, url in enumerate(c["images"], 1):
            name = f"n{c['no']:03d}_{n}.jpg"
            jobs.append((c, url, os.path.join(out_dir, name), name))

    def fetch(job):
        c, url, path, name = job
        try:
            return name, download(url, path, args.proxy), ""
        except Exception as e:
            return name, "fail", str(e)

    stats = {"ok": 0, "skip": 0, "fail": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for name, status, err in pool.map(fetch, jobs):
            stats[status] += 1
            if status == "fail":
                print(f"  ✗ {name}: {err}")
    print(f"下载: ✓{stats['ok']}  跳过{stats['skip']}  失败{stats['fail']}\n")

    for c, url, path, name in jobs:
        if not (os.path.exists(path) and os.path.getsize(path) > MIN_BYTES):
            continue
        records.append({
            "file": f"{IMG_SUBDIR}/{name}",
            "model": "imge-2",
            "title": c["title"],
            "prompt": raycast_clean(c["prompt"]),          # 中文展示版（Raycast 占位符→default）
            "tags": ",".join(c["tags"]),
            "promptRaw": c["prompt_en"],                   # 英文版原文，占位符原样保留
            "author": c["author"],
            "sourceUrl": c["sourceUrl"],
            "published": c["published"],
            "originId": f"gpt2-{c['no']}",
        })

    out_path = os.path.join(HERE, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    print(f"✓ {len(records)} 条记录 → {args.out}")
    print("下一步: python extract.py --source sample_prompts.csv --source data/gpt2_prompts.json")


if __name__ == "__main__":
    main()
