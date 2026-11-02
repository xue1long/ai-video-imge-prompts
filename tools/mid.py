# -*- coding: utf-8 -*-
"""从原图生成灯箱用的中图档（WebP，幂等）

用法:
  python tools/mid.py                  # 所有 imageDirs 含 mid 的站点
  python tools/mid.py --site portrait  # 只处理人像集
  python tools/mid.py --workers 4      # 限制进程数（默认 CPU 核数）

说明:
  灯箱原先直接加载原图 PNG（人像集平均 3 MB），未缓存时要等好几秒，
  期间只能看到模糊的缩略图。中图最长边 1600px、WebP q82，人像约 100 KB。

  路径规则：manifest 的 full_path 把开头的 img/ 换成 mid/、扩展名换成 .webp。
  已存在且不旧于原图的文件跳过。

  需要 Pillow（pip install pillow 或 apt install python3-pil）。
  这一步是可选的：中图缺失时灯箱会在 404 后退回加载原图，只是慢。
"""
import json, os, sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load_cfg, select, site_dir, dir_size, human, parse_args

MAX_EDGE = 1600
QUALITY = 82


def mid_rel(full_rel):
    """img/a/b.png → mid/a/b.webp（与灯箱 JS 里的 midOf() 一致）"""
    p = full_rel.replace("\\", "/")
    if p.startswith("img/"):
        p = p[4:]
    return "mid/" + os.path.splitext(p)[0] + ".webp"


def convert(job):
    src, dst = job
    from PIL import Image
    with Image.open(src) as im:
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        s = min(1.0, MAX_EDGE / max(im.size))
        if s < 1:
            im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".tmp"
        im.save(tmp, "WEBP", quality=QUALITY, method=6)
    os.replace(tmp, dst)


def main():
    args = parse_args(sys.argv[1:], {"site": "value", "workers": "value"})
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.exit("需要 Pillow：pip install pillow（或 apt install python3-pil）")

    cfg = load_cfg()
    # tiers 里已有 mid 的站点（如 Shisei）中图由上游直接提供、fetch.py 下载，这里不再生成，否则会覆盖上游文件
    sites = [s for s in select(cfg, args.get("site"))
             if "mid" in s.get("imageDirs", []) and "mid" not in s.get("tiers", [])]
    workers = int(args["workers"]) if "workers" in args else None

    print(f"中图生成 · {len(sites)} 个站点 · 最长边 {MAX_EDGE}px · WebP q{QUALITY}\n")

    for s in sites:
        sid = s["id"]
        sd = site_dir(sid)
        rows = json.load(open(os.path.join(sd, "manifest.json"), encoding="utf-8"))

        jobs, missing = [], 0
        for r in rows:
            # full 档走 online 的站没有 full_path（本地不留原图），
            # 没有原图就无从生成中图 —— 跳过，不算缺失。
            full_path = r.get("full_path")
            if not full_path:
                missing += 1
                continue
            src = os.path.join(sd, full_path)
            dst = os.path.join(sd, mid_rel(full_path))
            if not os.path.exists(src):
                missing += 1
                continue
            if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
                continue
            jobs.append((src, dst))

        print(f"  [{sid}] {len(rows)} 张 · 待生成 {len(jobs)}"
              + (f" · 原图缺失 {missing}" if missing else ""))
        if jobs:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                for n, _ in enumerate(ex.map(convert, jobs, chunksize=8), 1):
                    if n % 200 == 0 or n == len(jobs):
                        print(f"    {n}/{len(jobs)}")
        print(f"    → mid/ {human(dir_size(os.path.join(sd, 'mid')))}\n")

    print("完成")


if __name__ == "__main__":
    main()
