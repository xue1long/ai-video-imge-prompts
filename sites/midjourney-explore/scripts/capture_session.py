# -*- coding: utf-8 -*-
"""等待人工登录 midjourney.com，并把会话导出成 storage_state 文件。

为什么需要这个脚本
------------------
`/api/explore-srefs` 必须登录态，而且只能在浏览器页面上下文里调用（Python 直连
会稳定 500，cf_clearance 绑定 Chrome 的 TLS 指纹）。所以每次会话过期后都要重新
走一遍「人工登录 → 导出会话」。

Chrome 156 起，**默认 user-data-dir 禁止开 --remote-debugging-port**；
用 junction 把默认目录映射到别处会让 ABE v20 cookie 解不开并被 Chrome 删除，
会造成登录态不可恢复丢失。因此这里一律使用**独立的空 profile**，不碰用户目录。

用法
----
    # 1) 先起一个独立 profile 的 Chrome（人工登录用）
    chrome.exe --user-data-dir="C:\\Users\\<你>\\.workbuddy\\mj-profile" \\
               --remote-debugging-port=9333 \\
               "https://www.midjourney.com/explore?tab=styles_top"

    # 2) 运行本脚本，等你在那个窗口里登录
    python scripts/capture_session.py --cdp http://127.0.0.1:9333

    # 3) 之后采集风格码时复用会话
    python scripts/dump_styles.py --state "C:\\Users\\<你>\\.workbuddy\\secrets\\midjourney-session.json"

会话文件默认写到用户目录的持久位置（不在仓库内，不会被清理脚本误删）。
脚本不打印任何 cookie 值，只打印名字和数量。
"""
import argparse
import datetime
import json
import os
import sys
import time

DEFAULT_OUT = os.path.join(
    os.path.expanduser("~"), ".workbuddy", "secrets", "midjourney-session.json"
)
PAGE_URL = "https://www.midjourney.com/explore?tab=styles_top"
PROBE_URL = "/api/explore-srefs?page=0&feed=styles_top&_ql=explore"

FETCH_JS = """async (u) => {
  const r = await fetch(u, {headers: {'X-CSRF-Protection': '1'}, credentials: 'include'});
  const t = await r.text();
  return {status: r.status, len: t.length, head: t.slice(0, 120)};
}"""


def login_names(ctx):
    """返回 (是否已登录, midjourney 域 cookie 名列表)。"""
    try:
        names = [c["name"] for c in ctx.cookies("https://www.midjourney.com")]
    except Exception:
        return False, []
    return any("AuthUserToken" in n for n in names), names


def wait_login(ctx, timeout):
    t0 = time.time()
    last_report = 0
    while time.time() - t0 < timeout:
        ok, names = login_names(ctx)
        if ok:
            return True, names, int(time.time() - t0)
        if time.time() - last_report >= 30:
            last_report = time.time()
            print("  等待登录… 已 %ds，当前 cookie %d 条"
                  % (int(time.time() - t0), len(names)), flush=True)
        time.sleep(2)
    return False, login_names(ctx)[1], int(time.time() - t0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdp", default="http://127.0.0.1:9333")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--timeout", type=int, default=900, help="等待登录的秒数")
    ap.add_argument("--no-verify", action="store_true", help="导出后不验证接口")
    ap.add_argument("--no-nav", action="store_true",
                    help="未登录时不要导航（人工正在走 OAuth 弹窗时用，避免打断回调）")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(args.cdp)
        except Exception as e:
            print("连不上调试端口 %s：%s" % (args.cdp, e))
            print("请先按脚本头部说明起一个独立 profile 的 Chrome。")
            return 2
        ctx = browser.contexts[0]

        ok, names = login_names(ctx)
        if ok:
            print("已检测到登录态（cookie %d 条）" % len(names))
        else:
            print("未登录。请在 Chrome 窗口里登录 midjourney.com，最长等 %ds…" % args.timeout)
            if not args.no_nav:
                page = next((pg for pg in ctx.pages if "midjourney.com" in pg.url), None)
                if page is None:
                    page = ctx.new_page()
                try:
                    page.goto(PAGE_URL, wait_until="domcontentloaded", timeout=90000)
                except Exception:
                    pass
            ok, names, secs = wait_login(ctx, args.timeout)
            if not ok:
                print("超时未登录（%ds），已放弃。" % secs)
                return 3
            print("登录成功，用时 %ds" % secs)

        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        ctx.storage_state(path=args.out)
        size = os.path.getsize(args.out)
        state = json.load(open(args.out, "r", encoding="utf-8"))
        mj = [c for c in state.get("cookies", []) if "midjourney" in c.get("domain", "")]
        print("已写入 %s（%.1f KB，cookie 共 %d 条，midjourney 域 %d 条）"
              % (args.out, size / 1024.0, len(state.get("cookies", [])), len(mj)))
        print("midjourney cookie 名：%s" % ", ".join(sorted(c["name"] for c in mj)))

        if not args.no_verify:
            page = next((pg for pg in ctx.pages if "midjourney.com" in pg.url), None)
            if page is None:
                page = ctx.new_page()
                page.goto(PAGE_URL, wait_until="domcontentloaded", timeout=90000)
            try:
                r = page.evaluate(FETCH_JS, PROBE_URL)
                print("接口自检：HTTP %s，%d 字节，开头 %r"
                      % (r["status"], r["len"], r["head"]))
                if r["status"] != 200 or not r["head"].lstrip().startswith("["):
                    print("警告：接口未返回数组，会话可能不可用。")
            except Exception as e:
                print("接口自检失败（不影响会话文件）：%s" % e)

        print("完成于 %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return 0


if __name__ == "__main__":
    sys.exit(main())
