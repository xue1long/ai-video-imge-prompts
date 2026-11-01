# -*- coding: utf-8 -*-
"""data/prompts.json → manifest.json（+ manifest.csv）。

manifest 契约（见 docs/ADDING_A_SITE.md 与 shared/assets.py）：
每条记录对 sites.json 里声明的每个 tier 都要有 <tier>_url 与 <tier>_path。

本站三档：
    thumb  640.webp   衍生图，img.prompthero.com
    mid   1080.webp   衍生图，img.prompthero.com
    full  原图 PNG    cdn.prompthero.com

上游两个缺口及处理：
    · 26 条完全没有衍生图  → thumb 与 mid 回落原图 URL，打 thumbFallback / midFallback
    · 650 条没有 1080 档   → mid 回落 640，打 midFallback
回落的条目在页面上仍能正常显示，只是清晰度低一档。

路径一律用正斜杠、站点相对（thumbs/ mid/ img/），与 tools/fetch.py 的约定一致。
"""
import collections, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, SITE)

TIERS = ["thumb", "mid", "full"]


def main():
    src = os.path.join(SITE, "data", "prompts.json")
    if not os.path.exists(src):
        sys.exit("找不到 data/prompts.json，先运行 python scripts/extract.py")
    rows = json.load(open(src, encoding="utf-8"))

    out = []
    for r in rows:
        sk = r["storageKey"]
        copies = r.get("copies") or {}
        full_url = "https://cdn.prompthero.com/" + sk

        thumb_url = copies.get("640")
        thumb_fb = 0
        if not thumb_url:
            thumb_url = full_url
            thumb_fb = 1

        mid_url = copies.get("1080")
        mid_fb = 0
        if not mid_url:
            mid_url = copies.get("640") or thumb_url
            mid_fb = 1

        cat = r.get("category") or "uncategorized"
        text = (r.get("prompt") or "").strip()
        out.append({
            "id": r["slug"],
            "slug": r["slug"],
            "prompt": text,
            "title": text[:80] + ("…" if len(text) > 80 else ""),
            "description": (r.get("description") or "").strip(),
            "category": cat,
            "modelVersion": r.get("modelVersion") or "",
            "isNsfw": r.get("isNsfw") or 0,
            "favCount": r.get("favCount") or 0,
            "viewCount": r.get("viewCount") or 0,
            "createdAt": r.get("createdAt") or "",
            "width": r.get("width") or 0,
            "height": r.get("height") or 0,
            "sourceUrl": "https://prompthero.com/prompt/" + r["slug"],
            "thumb_url": thumb_url,
            "thumb_path": "thumbs/%s.webp" % sk,
            "mid_url": mid_url,
            "mid_path": "mid/%s.webp" % sk,
            "full_url": full_url,
            "full_path": "img/%s.png" % sk,
            "thumbFallback": thumb_fb,
            "midFallback": mid_fb,
        })

    # 排序：收藏多的在前，同收藏按 slug 保证构建可复现
    out.sort(key=lambda x: (-x["favCount"], -x["viewCount"], x["slug"]))

    with open(os.path.join(SITE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    cols = ["id", "category", "modelVersion", "isNsfw", "favCount", "viewCount",
            "createdAt", "prompt", "thumb_path", "mid_path", "full_path", "sourceUrl"]
    with open(os.path.join(SITE, "manifest.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            w.writerow({k: r.get(k, "") for k in cols})

    print("manifest: %d 条" % len(out))
    print("  NSFW %d 条" % sum(r["isNsfw"] for r in out))
    print("  分类 %s" % collections.Counter(r["category"] for r in out).most_common())
    print("  版本 %s" % collections.Counter(r["modelVersion"] for r in out).most_common())
    print("  thumb 回落原图 %d 条 · mid 回落 640 %d 条"
          % (sum(r["thumbFallback"] for r in out), sum(r["midFallback"] for r in out)))
    for t in TIERS:
        paths = [r[t + "_path"] for r in out]
        assert len(paths) == len(set(paths)), "%s 路径重复" % t
        assert not [p for p in paths if "\\" in p or p.startswith("/") or ".." in p]
    print("  路径唯一性与可移植性检查通过")


if __name__ == "__main__":
    main()
