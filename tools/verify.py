# -*- coding: utf-8 -*-
"""校验站点图片：存在、体积、可读宽高；中图另行检查

用法:
  python tools/verify.py                  # 全部站点、全部档位（含中图）
  python tools/verify.py --site pose      # 只校验一个站
  python tools/verify.py --tier thumb     # 只校验缩略图（只下了缩略图时用）

有缺失或损坏时退出码为 1。release.py 发布前会调用同一套检查。
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ROOT, load_cfg, select, site_dir, parse_args

sys.path.insert(0, os.path.join(ROOT, "shared"))
import assets  # noqa: E402
from mid import mid_rel  # noqa: E402


def check_site(s, only_tier=None, log=print):
    """返回 (缺失数, 损坏数)。"""
    sd = site_dir(s["id"])
    tiers = s.get("tiers", ["thumb"])
    if only_tier:
        tiers = [t for t in tiers if t == only_tier]
    total, report = assets.verify(sd, tiers)
    missing = broken = 0
    for tier, t in report.items():
        log("    [%-5s] 完好 %d / %d  |  %.1f MB" % (tier, t["ok"], total, t["bytes"] / 1048576))
        if t["dims"]:
            top = sorted(t["dims"].items(), key=lambda x: -x[1])[:4]
            log("            分辨率: " + ", ".join("%s×%d" % kv for kv in top))
        for label, lst in (("缺失", t["missing"]), ("损坏", t["broken"])):
            if lst:
                log("            %s %d，前 3：%s" % (label, len(lst), lst[:3]))
        missing += len(t["missing"]); broken += len(t["broken"])

    # 中图：imageDirs 含 mid 的站点，每张原图都应有对应的 mid/*.webp
    # 优先用 manifest 直接给的 mid_path；没有这一列的站（中图由上游提供、
    # 或本地只有原图）才从 full_path 推导 —— full 档走 online 的站甚至
    # 没有 full_path，那种站不参与本项检查。
    if "mid" in s.get("imageDirs", []) and only_tier in (None, "mid"):
        rows = assets.load_manifest(sd)
        def mid_of(r):
            if r.get("mid_path"):
                return r["mid_path"]
            if r.get("full_path"):
                return mid_rel(r["full_path"])
            return None
        lost = [p for r in rows
                for p in [mid_of(r)] if p and not os.path.exists(os.path.join(sd, p))]
        log("    [mid  ] 完好 %d / %d" % (len(rows) - len(lost), len(rows)))
        if lost:
            log("            缺失 %d，前 3：%s（运行 python tools/mid.py 补齐）" % (len(lost), lost[:3]))
        missing += len(lost)
    return missing, broken


def main():
    args = parse_args(sys.argv[1:], {"site": "value", "tier": "value"})
    sites = select(load_cfg(), args.get("site"))
    bad = 0
    for s in sites:
        print(f"  [{s['id']}]")
        m, b = check_site(s, args.get("tier"))
        bad += m + b
    print()
    if bad:
        sys.exit(f"校验失败：共 {bad} 项缺失或损坏")
    print("校验通过：全部文件存在且可解码")


if __name__ == "__main__":
    main()
