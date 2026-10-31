# -*- coding: utf-8 -*-
"""构建站点页面（每个站点的 index.html + 数据导出 + SEO 文件），并重建入口页

用法:
  python tools/build.py                              # 全部站点 + 入口页
  python tools/build.py --site pose                  # 只重建姿势集
  python tools/build.py --skip prompts               # 跳过某站（CI 用：该站数据不入库）
  python tools/build.py --base https://example.com   # 指定正式域名
  python tools/build.py --no-hub                     # 不重建入口页

说明:
  SITE_URL 会拼成 <base>/<站点id>，写进 canonical / og:url / sitemap。
  本地预览用默认的 https://example.com 即可，正式发布时传 --base。

  --skip 用于「数据源不在仓库里」的站：prompts 站的 data/prompts_*.json 与
  data/gallery_*.js 不入库（体积 200 MB+，可由 import_youmind.py 重拉），
  干净检出上构建它会直接失败。CI 因此跳过该站，其余站照常校验。
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ROOT, load_cfg, select, exclude, site_dir, run, parse_args


def main():
    args = parse_args(sys.argv[1:], {
        "site": "value", "skip": "value", "base": "value", "no-hub": "flag",
    })
    cfg = load_cfg()
    sites = exclude(select(cfg, args.get("site")), args.get("skip"))
    base = args.get("base", "https://example.com").rstrip("/")

    if not sites:
        sys.exit("没有要构建的站点（--site 与 --skip 把范围清空了）")

    print(f"构建 · {len(sites)} 个站点 · base = {base}\n")

    for s in sites:
        sid = s["id"]
        sd = site_dir(sid)
        script = os.path.join(sd, "scripts", "build_gallery.py")
        if not os.path.exists(script):
            print(f"  ✗ {sid}: 缺少 scripts/build_gallery.py，跳过\n")
            continue

        site_url = f"{base}/{sid}"
        print(f"  [{sid}] SITE_URL = {site_url}")
        run([sys.executable, script], cwd=sd, env_extra={"SITE_URL": site_url}, quiet=True)

        idx = os.path.join(sd, "index.html")
        size = os.path.getsize(idx) / 1024 if os.path.exists(idx) else 0
        print(f"    → index.html {size:.1f} KB\n")

    if not args.get("no-hub"):
        print("  [hub] 重建入口页")
        run([sys.executable, os.path.join(ROOT, "hub", "build_hub.py"), "--base", base],
            cwd=ROOT, quiet=True)

    print("完成")


if __name__ == "__main__":
    main()
