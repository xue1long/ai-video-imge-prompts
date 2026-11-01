# -*- coding: utf-8 -*-
"""data/jobs.json → manifest.json（+ manifest.csv）。

manifest 契约（见 docs/ADDING_A_SITE.md 与 shared/assets.py）：
每条记录对 sites.json 里声明的每个 tier 都要有 <tier>_url 与 <tier>_path。

本站三档（图源 cdn.midjourney.com，每条作业 4 格，每格一个 id）：
    thumb  0_{i}_640_N.webp     缩略图，约 120–150 KB
    mid    0_{i}_1024_N.webp    灯箱中图，约 240–310 KB
    full   0_{i}.png             原图，约 2 MB

图源说明：
    CDN 要求带上 Cloudflare 下发的 __cf_bm cookie，否则一律 403。
    tools/fetch.py 与 tools/verify.py 走的是 shared/assets.py 的 urllib，
    本身不带 cookie —— 这部分由 tools/mid.py 无关，需要在 fetch 前先取得通行证。
    为此本站在 manifest 里额外记了 _ck_url：先访问它拿到 cookie，再下图。

路径一律用正斜杠、站点相对（thumbs/ mid/ img/），与 tools/fetch.py 的约定一致。
"""
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, SITE)

from config import IMAGE_BASES  # noqa: E402

TIERS = ["thumb", "mid", "full"]
CDN = IMAGE_BASES[0]
# 先访问这个页面拿 Cloudflare 通行证（__cf_bm），再下载 CDN 上的图
CLEARANCE_URL = "https://www.midjourney.com/explore?tab=styles_top"


def main():
    src = os.path.join(SITE, "data", "jobs.json")
    if not os.path.exists(src):
        sys.exit("找不到 data/jobs.json，先运行 python scripts/extract.py")
    jobs = json.load(open(src, encoding="utf-8"))

    out = []
    for j in jobs:
        job_id = j["id"]
        for i in j["indices"]:
            base = "%s%s/0_%d" % (CDN, job_id, i)
            out.append({
                "id": "%s_%d" % (job_id, i),
                "jobId": job_id,
                "index": i,
                "prompt": j["prompt"],
                "title": j["prompt"][:80] + ("…" if len(j["prompt"]) > 80 else ""),
                "aspect": j["ar"],
                "version": j["version"],
                "username": j["username"],
                "displayName": j["displayName"],
                "enqueueTime": j["enqueueTime"],
                "width": j["width"],
                "height": j["height"],
                "hasStyleRef": j["hasStyleRef"],
                # p 值：风格参考码，逗号分隔（同一条作业的 4 格共用）
                "sref": ",".join(j.get("sref") or []),
                "sourceUrl": j["sourceUrl"],
                "thumb_url": base + "_640_N.webp",
                "thumb_path": "thumbs/%s_%d.webp" % (job_id, i),
                "mid_url": base + "_1024_N.webp",
                "mid_path": "mid/%s_%d.webp" % (job_id, i),
                "full_url": base + ".png",
                "full_path": "img/%s_%d.png" % (job_id, i),
                "_ck_url": CLEARANCE_URL,
            })

    # 排序：先按作业入榜顺序（enqueueTime），同作业内按格子序号。
    # 榜单本身按热度排序，这里用入榜序近似热度序；同值按 id 保证构建可复现。
    out.sort(key=lambda x: (x["enqueueTime"], x["jobId"], x["index"]))

    with open(os.path.join(SITE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    cols = ["id", "jobId", "index", "aspect", "version", "username",
            "enqueueTime", "width", "height", "prompt", "sref", "sourceUrl",
            "thumb_path", "mid_path", "full_path"]
    with open(os.path.join(SITE, "manifest.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in cols})

    print("manifest: %d 张图 / %d 条作业"
          % (len(out), len({r["jobId"] for r in out})))
    print("  宽高比 %s"
          % collections.Counter(r["aspect"] or "-" for r in out).most_common())
    print("  版本 %s"
          % collections.Counter(r["version"] or "-" for r in out).most_common())
    print("  作者 %d 位" % len({r["username"] for r in out}))
    for t in TIERS:
        paths = [r[t + "_path"] for r in out]
        assert len(paths) == len(set(paths)), "%s 路径重复" % t
        assert not [p for p in paths if "\\" in p or p.startswith("/") or ".." in p]
        assert all(r[t + "_url"].startswith(CDN) for r in out), "%s URL 不在图源下" % t
    print("  路径唯一性、可移植性与图源检查通过")


if __name__ == "__main__":
    main()
