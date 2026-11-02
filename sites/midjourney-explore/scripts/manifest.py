# -*- coding: utf-8 -*-
"""data/daily/<批次>/jobs.json（累积）→ manifest.json（+ manifest.csv）。

manifest 契约（见 docs/ADDING_A_SITE.md 与 shared/assets.py）：
每条记录对 sites.json 里声明的每个 tier 都要有 <tier>_url 与 <tier>_path。

本站三档（图源 cdn.midjourney.com，每条作业 4 格，每格一个 id）：
    thumb  0_{i}_640_N.webp     缩略图，约 120–150 KB   本地
    mid    0_{i}_1024_N.webp    灯箱中图，约 240–310 KB  本地
    full   0_{i}.png             原图，约 2 MB           **只给 URL**

full 档是 **online** 取图策略（sites.json 的 imagePolicy.full = online）：
原图不落本地 —— 每天约 2.3 GB，而本地已有副本并不产生任何展示价值。
所以 manifest 里 full **只有 full_url，没有 full_path**：
留一个指向不存在文件的路径字段，等于给下游埋一个必然 404 的死值。
（thumb/mid 仍是 local-only，路径照常写出。）

图源说明：
    CDN 要求带上 Cloudflare 下发的 __cf_bm cookie，否则一律 403。
    tools/fetch.py 与 tools/verify.py 走的是 shared/assets.py 的 urllib，
    本身不带 cookie —— 需要在 fetch 前先取得通行证。
    为此本站在 manifest 里额外记了 _ck_url：先访问它拿到 cookie，再下图。

路径一律用正斜杠、站点相对（thumbs/ mid/），与 tools/fetch.py 的约定一致。
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

# 有本地副本的档位（会写 <tier>_path）；full 不在其中
LOCAL_TIERS = ["thumb", "mid"]
# 全部档位（都会写 <tier>_url）
TIERS = LOCAL_TIERS + ["full"]
CDN = IMAGE_BASES[0]
# 先访问这个页面拿 Cloudflare 通行证（__cf_bm），再下载 CDN 上的图
CLEARANCE_URL = "https://www.midjourney.com/explore?tab=styles_top"


def load_batches():
    """读所有批次的采集结果，按批次日期升序返回 [(批次日期, 作业列表)]。

    批次目录是 data/daily/<YYYY-MM-DD>/jobs.json（extract.py 每天写一份，
    批次之间不覆盖）。这里把所有批次累积起来 —— 站点与素材管理器消费的是
    累积结果，不是「最新一天」。
    """
    daily = os.path.join(SITE, "data", "daily")
    if not os.path.isdir(daily):
        sys.exit("找不到 data/daily/ 目录，先运行 python scripts/extract.py")
    batches = []
    for name in sorted(os.listdir(daily)):
        path = os.path.join(daily, name, "jobs.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            batches.append((name, json.load(f)))
    if not batches:
        sys.exit("data/daily/ 下没有任何批次的 jobs.json，先运行 python scripts/extract.py")
    return batches


def main():
    batches = load_batches()

    # 累积 + 按作业去重：同一作业可能连续多天在榜上，只留一份。
    # 先出现的批次优先（批次按日期升序）—— 保持结果稳定、可复现。
    jobs = []
    seen_jobs = set()
    dup_jobs = 0
    per_batch = []
    for batch, bjobs in batches:
        added = 0
        for j in bjobs:
            if j["id"] in seen_jobs:
                dup_jobs += 1
                continue
            seen_jobs.add(j["id"])
            jobs.append((batch, j))
            added += 1
        per_batch.append((batch, len(bjobs), added))

    out = []
    for batch, j in jobs:
        job_id = j["id"]
        for i in j["indices"]:
            base = "%s%s/0_%d" % (CDN, job_id, i)
            out.append({
                "id": "%s_%d" % (job_id, i),
                "jobId": job_id,
                "index": i,
                # 采集批次（哪一天采到的）—— 累积后用于按天浏览与筛选
                "batch": batch,
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
                # full 只有 URL：本地不留原图（imagePolicy.full = online）
                "full_url": base + ".png",
                "_ck_url": CLEARANCE_URL,
            })

    # 排序：先按作业入榜顺序（enqueueTime），同作业内按格子序号。
    # 榜单本身按热度排序，这里用入榜序近似热度序；同值按 id 保证构建可复现。
    out.sort(key=lambda x: (x["enqueueTime"], x["jobId"], x["index"]))

    with open(os.path.join(SITE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    cols = ["id", "jobId", "index", "batch", "aspect", "version", "username",
            "enqueueTime", "width", "height", "prompt", "sref", "sourceUrl",
            "thumb_path", "mid_path"]
    with open(os.path.join(SITE, "manifest.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in cols})

    print("manifest: %d 张图 / %d 条作业（%d 个批次，去重掉 %d 条重复作业）"
          % (len(out), len({r["jobId"] for r in out}), len(batches), dup_jobs))
    for batch, total, added in per_batch:
        print("  批次 %s：%d 条（新增 %d 条）" % (batch, total, added))
    print("  宽高比 %s"
          % collections.Counter(r["aspect"] or "-" for r in out).most_common())
    print("  版本 %s"
          % collections.Counter(r["version"] or "-" for r in out).most_common())
    print("  作者 %d 位" % len({r["username"] for r in out}))
    for t in LOCAL_TIERS:
        paths = [r[t + "_path"] for r in out]
        assert len(paths) == len(set(paths)), "%s 路径重复" % t
        assert not [p for p in paths if "\\" in p or p.startswith("/") or ".." in p]
    for t in TIERS:
        assert all(r[t + "_url"].startswith(CDN) for r in out), "%s URL 不在图源下" % t
    # full 是 online 档：本地不留原图，manifest 里不得出现指向本地文件的路径
    assert not [r for r in out if "full_path" in r], \
        "full 档不该有本地路径（imagePolicy.full = online）"
    print("  路径唯一性、可移植性与图源检查通过")


if __name__ == "__main__":
    main()
