# -*- coding: utf-8 -*-
"""抓取 Midjourney Styles 清单（风格码）。

背景与实测结论（详见 docs/STYLES_FEASIBILITY.md）：
- 清单接口 `/api/explore-srefs?page=N&feed=styles_top&_ql=explore` **必须登录态**；
- 匿名访问会被降级成图片流，接口返回 401/500；
- **该接口只能在浏览器页面上下文里调用**：把 cookie 拿出来用 Python 直连会稳定返回
  `500 {"error":"Internal server error"}`（cf_clearance 与 Chrome 的 TLS 指纹绑定，
  四组请求变体全部失败）。因此本脚本用 Playwright 在页面里执行 fetch。

两种运行模式：
    # 1) 接管一个已登录的 Chrome（调试端口）
    python scripts/dump_styles.py --cdp http://127.0.0.1:9333

    # 2) 用会话文件在全新 Chrome 里跑（不依赖已打开的窗口）
    python scripts/dump_styles.py --state ../../.scratch/mj_session.json

    # 3) 都没有时：起一个 Chrome 并等待人工登录
    python scripts/dump_styles.py --profile ../../.scratch/cprof3 --login

输出：data/styles.json（feed / captured_at / count / items[code,id,width,height,type]）

登录态来源：人工在 Chrome 里登录 midjourney.com 后，用
    context.storage_state(path="mj_session.json")
导出；脚本不含任何凭证，也不会打印 cookie 值。
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
OUT = os.path.join(SITE, "data", "styles.json")
PAGE_URL = "https://www.midjourney.com/explore?tab=styles_top"

FETCH_JS = """async (u) => {
  const r = await fetch(u, {headers: {'X-CSRF-Protection': '1'}, credentials: 'include'});
  const t = await r.text();
  return {status: r.status, body: t};
}"""


def have_login(ctx):
    try:
        names = [c["name"] for c in ctx.cookies("https://www.midjourney.com")]
    except Exception:
        return False, []
    return any("AuthUserToken" in n for n in names), names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdp", default="", help="接管已打开的 Chrome，例如 http://127.0.0.1:9333")
    ap.add_argument("--state", default="", help="storage_state.json 路径（全新 Chrome 用）")
    ap.add_argument("--profile", default="", help="持久化 profile 目录（配合 --login）")
    ap.add_argument("--login", action="store_true", help="未登录时等待人工登录")
    ap.add_argument("--feed", default="styles_top")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--no-merge", action="store_true",
                    help="覆盖输出文件，不合并历史码（默认合并累积）")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        closer = None
        if args.cdp:
            browser = p.chromium.connect_over_cdp(args.cdp)
            ctx = browser.contexts[0]
        elif args.profile or args.state:
            kwargs = dict(channel="chrome", headless=False,
                          viewport={"width": 1440, "height": 900},
                          args=["--no-first-run", "--no-default-browser-check",
                                "--disable-blink-features=AutomationControlled"])
            if args.profile:
                ctx = p.chromium.launch_persistent_context(args.profile, **kwargs)
            else:
                browser = p.chromium.launch(**{k: v for k, v in kwargs.items() if k != "viewport"})
                ctx = browser.new_context(storage_state=args.state,
                                          viewport={"width": 1440, "height": 900})
            closer = ctx
        else:
            print("需要 --cdp / --state / --profile 之一")
            return 2

        logged, names = have_login(ctx)
        if not logged:
            print("未检测到登录态（AuthUserToken 缺失）")
            if not args.login:
                print("加 --login 可起窗口等待人工登录")
                return 3
            print("请在弹出的 Chrome 窗口里登录，最长等 15 分钟…", flush=True)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(PAGE_URL, wait_until="domcontentloaded")
            import time
            t0 = time.time()
            while time.time() - t0 < 900:
                logged, names = have_login(ctx)
                if logged:
                    break
                time.sleep(3)
            if not logged:
                print("超时未登录")
                return 3
            print("登录成功，用时 %ds" % int(time.time() - t0))

        page = next((pg for pg in ctx.pages if "midjourney.com" in pg.url), None)
        if page is None:
            page = ctx.new_page()
        page.goto(PAGE_URL, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(5000)

        items, seen = [], set()
        for pageno in range(args.max_pages):
            res = page.evaluate(
                FETCH_JS,
                "/api/explore-srefs?page=%d&feed=%s&_ql=explore" % (pageno, args.feed),
            )
            if res["status"] != 200:
                print("page %d -> HTTP %s，停止（%s）"
                      % (pageno, res["status"], res["body"][:120]), flush=True)
                if pageno == 0:
                    return 4
                break
            try:
                arr = json.loads(res["body"])
            except Exception:
                print("page %d 非 JSON，停止" % pageno)
                break
            if not arr:
                print("page %d 空数组，到底（共 %d 页）" % (pageno, pageno), flush=True)
                break
            new = 0
            for it in arr:
                key = it.get("id") or it.get("formatted_sref")
                if key and key not in seen:
                    seen.add(key)
                    items.append(it)
                    new += 1
            print("page %2d: +%-3d 新增 %-3d 累计 %d" % (pageno, len(arr), new, len(items)),
                  flush=True)
            if new == 0:
                break
            page.wait_for_timeout(450)

        now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        fresh = [
            {
                "code": it.get("formatted_sref") or it["id"].split("_", 1)[1],
                "id": it["id"],
                "width": it.get("width"),
                "height": it.get("height"),
                "type": it.get("type"),
            }
            for it in items
        ]

        # 榜单是**滚动**的：实测相隔约 45 分钟的两次抓取重合 139/200（约 30% 换血），
        # 重合项位置平均偏移 22 位。所以默认合并累积，不覆盖已有码。
        merged, snapshots = {}, []
        if not args.no_merge and os.path.exists(args.out):
            try:
                old = json.load(open(args.out, encoding="utf-8"))
                merged = {i["code"]: i for i in old.get("items", [])}
                snapshots = old.get("snapshots", [])
            except Exception:
                merged, snapshots = {}, []
        added = [it["code"] for it in fresh if it["code"] not in merged]
        for it in fresh:
            merged[it["code"]] = it
        snapshots.append({"at": now, "feed": args.feed, "count": len(fresh), "new": len(added)})

        out = {
            "feed": args.feed,
            "source": PAGE_URL,
            "captured_at": now,
            "count": len(merged),
            "last_run_count": len(fresh),
            "snapshots": snapshots[-30:],
            "items": list(merged.values()),
        }
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print("写入 %s：本次 %d 条，新增 %d，累计 %d"
              % (args.out, len(fresh), len(added), len(merged)))
        if added:
            print("新增码：%s" % ", ".join(added[:12]) + (" …" if len(added) > 12 else ""))
        if closer is not None:
            closer.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
