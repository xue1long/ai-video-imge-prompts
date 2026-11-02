# -*- coding: utf-8 -*-
"""下载风格示例图（Styles 数据线）。

每个风格码在原站 CDN 上有三张示例图，命名是固定的：

    styles/0_<码>/portrait_<尺寸>_N.webp
    styles/0_<码>/landscape_<尺寸>_N.webp
    styles/0_<码>/still_life_<尺寸>_N.webp

可用尺寸只有 128 / 384 / 640 / 1024（256、512、2048 均 404）。
这些图**不需要登录**，走 fetch_hook 的 Cloudflare 通行证即可下载；
需要登录的只有「风格清单」接口（见 dump_styles.py）。

用法：
    python scripts/fetch_styles.py                  # 全量，1024 档
    python scripts/fetch_styles.py --size 640       # 换档
    python scripts/fetch_styles.py --limit 5        # 只跑前 5 个（试跑）
    python scripts/fetch_styles.py --codes 3441803824,4212271874
    python scripts/fetch_styles.py --force          # 重下已存在的

输入：data/styles.json（由 dump_styles.py 产生）
输出：styles/<码>/<kind>.webp + data/styles_images.json（每码每类的命中情况）

幂等：目标文件已存在且非空即跳过，可用 --force 覆盖。
"""
import argparse
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, SITE)
sys.path.insert(0, HERE)

import fetch_hook  # noqa: E402
from config import UA  # noqa: E402

KINDS = ("portrait", "landscape", "still_life")
SIZES = (128, 384, 640, 1024)
DEFAULT_SIZE = 1024

MANIFEST = os.path.join(SITE, "data", "styles.json")
OUT_DIR = os.path.join(SITE, "styles")
STATUS = os.path.join(SITE, "data", "styles_images.json")

IMG_HEADERS = {
    "User-Agent": UA,
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Origin": "https://www.midjourney.com",
    "Referer": "https://www.midjourney.com/",
    "Sec-Fetch-Dest": "image",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "same-site",
}


def load_codes(args):
    if args.codes:
        return [c.strip() for c in args.codes.split(",") if c.strip()]
    with open(MANIFEST, encoding="utf-8") as f:
        data = json.load(f)
    codes = [it["code"] for it in data.get("items", [])]
    if args.limit:
        codes = codes[: args.limit]
    return codes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=DEFAULT_SIZE, choices=SIZES)
    ap.add_argument("--codes", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()

    codes = load_codes(args)
    if not codes:
        print("没有待下载的码，检查 %s" % MANIFEST)
        return 2

    opener = fetch_hook.prepare(
        fetch_hook._make_opener(http.cookiejar.CookieJar()),
        log=lambda m: None,
    )
    os.makedirs(OUT_DIR, exist_ok=True)

    status = {}
    if os.path.exists(STATUS):
        try:
            status = json.load(open(STATUS, encoding="utf-8"))
        except Exception:
            status = {}

    print("目标 %d 个码 × %d 类，尺寸 %d" % (len(codes), len(KINDS), args.size), flush=True)
    hit = miss = skip = err = 0
    for i, code in enumerate(codes, 1):
        rec = status.setdefault(code, {})
        for kind in KINDS:
            dest_dir = os.path.join(OUT_DIR, code)
            dest = os.path.join(dest_dir, "%s.webp" % kind)
            if not args.force and os.path.exists(dest) and os.path.getsize(dest) > 1024:
                rec[kind] = "ok"
                skip += 1
                continue
            url = "https://cdn.midjourney.com/styles/0_%s/%s_%d_N.webp" % (code, kind, args.size)
            try:
                with opener.open(urllib.request.Request(url, headers=IMG_HEADERS), timeout=40) as r:
                    body = r.read()
                if len(body) < 1024:
                    raise ValueError("body too small: %d" % len(body))
                os.makedirs(dest_dir, exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(body)
                rec[kind] = "ok"
                hit += 1
            except urllib.error.HTTPError as e:
                rec[kind] = "http_%d" % e.code
                if e.code == 404:
                    miss += 1
                else:
                    err += 1
            except Exception as e:  # noqa: BLE001
                rec[kind] = "err_%s" % type(e).__name__
                err += 1
            time.sleep(args.sleep)
        rec["size"] = args.size
        if i % 20 == 0 or i == len(codes):
            print("  [%3d/%3d] 新下 %d  跳过 %d  404 %d  错误 %d"
                  % (i, len(codes), hit, skip, miss, err), flush=True)
            json.dump(status, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    json.dump(status, open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 只保留最近一档尺寸的统计口径
    ok_codes = sum(1 for v in status.values() if sum(1 for k in KINDS if v.get(k) == "ok") == len(KINDS))
    partial = sum(1 for v in status.values() if 0 < sum(1 for k in KINDS if v.get(k) == "ok") < len(KINDS))
    print("\n汇总：新下载 %d，跳过 %d，404 %d，错误 %d" % (hit, skip, miss, err))
    print("完整 %d 个码（三类齐全），部分缺图 %d 个，状态写入 %s" % (ok_codes, partial, STATUS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
