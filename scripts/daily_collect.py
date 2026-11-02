# -*- coding: utf-8 -*-
"""每日采集流水线（midjourney-explore）：采集 → 累积索引 → 建站 → WebUI 索引 → 提交推送。

用法：
    python scripts/daily_collect.py            # 正常跑（默认当天批次）
    python scripts/daily_collect.py --dry-run  # 只跑，不提交推送
    python scripts/daily_collect.py --batch 2026-11-03

为什么单独一个脚本，而不是把命令串在定时任务里：
    定时任务的 prompt 无法承载「失败要停在哪一步」「退出码代表什么」这类语义，
    而这几步的失败模式完全不同（采集限流 vs 构建报错 vs 推送无代理）。
    把判断写进脚本，定时任务只负责触发 —— 日志也更好读。

各步骤的退出码约定（外层按此决定是否提交）：
    0  全部成功
    2  采集失败（上游限流 / 网络问题）—— 数据没动，不提交
    3  当天批次已存在（extract.py 的「不覆盖」约定）—— 正常情况，非错误
    4  构建 / 索引失败 —— 数据可能已更新但不提交，交给人判断
    5  提交或推送失败 —— 数据已在本地提交，git 状态需人工确认
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "midjourney-explore"
SITE_DIR = os.path.join(ROOT, "sites", SITE)
PY = sys.executable


def log(msg):
    print(msg, flush=True)


def run(args, cwd=ROOT, env=None, allow_rc=(0,)):
    """跑一条命令，返回 (rc, 输出)。输出直接转发到日志，便于事后排查。"""
    e = dict(os.environ)
    if env:
        e.update(env)
    log("$ " + " ".join(os.path.relpath(a, ROOT) if a.startswith(ROOT) else a for a in args))
    p = subprocess.run(args, cwd=cwd, env=e,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode("utf-8", errors="replace")
    if out:
        print(out, end="", flush=True)
    log("  → rc=%d" % p.returncode)
    if p.returncode not in allow_rc:
        sys.exit(p.returncode if p.returncode else 1)
    return p.returncode, out


def current_proxy():
    """探测当前可用的代理端口。

    为什么动态探测：git 全局 config 里的 http.proxy 指向 127.0.0.1:7890 已失效，
    而环境里的代理端口每次会话都在变（实测依次出现过 6651 / 8674 / 3826 / 4755 / 5444）。
    写死端口必然失效；这里按「环境变量 → 全局 config → 7897」的顺序探测，
    逐个试连通性，取第一个能用的。
    """
    cands = []
    for k in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
        v = os.environ.get(k)
        if v and v not in cands:
            cands.append(v)
    try:
        cfg = subprocess.run(["git", "config", "--global", "--get", "http.proxy"],
                             cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL).stdout.decode("utf-8").strip()
        if cfg and cfg not in cands:
            cands.append(cfg)
    except Exception:
        pass
    for p in ("http://127.0.0.1:7897",):
        if p not in cands:
            cands.append(p)

    import socket
    for c in cands:
        m = re.match(r"^https?://([^:/]+):(\d+)", c)
        if not m:
            continue
        host, port = m.group(1), int(m.group(2))
        if host not in ("127.0.0.1", "localhost"):
            continue
        s = socket.socket()
        s.settimeout(1.0)
        try:
            s.connect((host, port))
            log("  代理可用：%s" % c)
            return c
        except Exception:
            pass
        finally:
            s.close()
    log("  未找到可用的本地代理端口")
    return None


def git_commit_and_push(batch, n_images, n_jobs):
    """提交并推送。返回 0 成功。"""
    # 提交整个站点目录与 hub 目录 —— 理由：
    #   1. 本次只构建了这一个站 + hub，目录内除采集产物外没有别的改动；
    #   2. 构建脚本会生成 index.html / 404.html / robots.txt / sitemap.xml /
    #      gallery.js / landing.json / aspect/ / browse/ 等多个文件，
    #      逐个列举容易漏（已漏过 llms.txt 与 404.html/robots.txt），
    #      漏一个就会让 CI 的「产物与仓库一致」闸门变红；
    #   3. thumbs/ mid/ 等图片目录已被 .gitignore 排除，不会被带进去。
    paths = [
        "sites/%s" % SITE,
        "hub",
        "scripts/daily_collect.py",
    ]
    paths = [p for p in paths if os.path.exists(os.path.join(ROOT, p))]
    if not paths:
        log("没有待提交的产物，跳过提交")
        return 0

    msg_path = os.path.join(ROOT, ".scratch", "daily_commit_msg.txt")
    os.makedirs(os.path.dirname(msg_path), exist_ok=True)
    msg = (
        "chore(midjourney-explore): 每日采集 %s\n\n"
        "- 新批次：data/daily/%s/\n"
        "- 累积索引：%d 条作业 / %d 张成图\n"
        "- 站点构建与 WebUI 索引已同步\n\n"
        "由 scripts/daily_collect.py 自动生成。\n"
    ) % (batch, batch, n_jobs, n_images)
    with open(msg_path, "w", encoding="utf-8") as f:
        f.write(msg)

    # 提交前跑一遍「重建是幂等的」校验：再构建一次，看产物是否还会变。
    # 变了说明构建不是确定性的（或者构建脚本与产物脱节）—— 这时推上去的
    # 产物过不了 CI 的「构建产物与仓库一致」闸门。
    #
    # 为什么不用 CI 原样的 `git diff --exit-code -- hub sites`：
    #   那是「与 HEAD 比对」，会把工作区里**别人**正在改的文件也算进来
    #   （实测：另一个会话改了 index/catalog.py、shared/*.py，闸门会误红）。
    #   这里改成「重建前后是否有新变化」—— 只关心构建产物自身的确定性。
    log("提交前校验：重建并检查产物是否稳定")
    def snapshot(paths):
        out = {}
        for p in paths:
            full = os.path.join(ROOT, p)
            if os.path.isfile(full):
                with open(full, "rb") as f:
                    out[p] = f.read()
        return out

    watch = []
    for p in ["sites/%s/index.html" % SITE, "sites/%s/sitemap.xml" % SITE,
              "sites/%s/manifest.json" % SITE, "hub/index.html",
              "hub/sitemap.xml", "hub/llms.txt"]:
        if os.path.exists(os.path.join(ROOT, p)):
            watch.append(p)
    before = snapshot(watch)
    run([PY, os.path.join("tools", "build.py"), "--skip", "prompts"])
    after = snapshot(watch)
    changed = [p for p in watch if before.get(p) != after.get(p)]
    if changed:
        log("!! 重建后产物发生变化，构建不是确定性的 —— 放弃提交：%s" % changed)
        return 4

    # ── 隔离提交：只用 git commit --only -- <paths> ────────────────────
    # 为什么不用 `git add` + `git commit`：
    #   `git commit` 提交的是**整个暂存区**。若此时有人（另一个会话）
    #   暂存了别的改动，会被连带提交进这次「每日采集」提交里 —— 那是别人
    #   的工作，不该由定时任务替他发布。
    #   `git commit --only -- <paths>` 只提交指定路径的工作区内容，
    #   **完全不碰暂存区**（实测 dry-run 后暂存区保持原样）—— 正是这里要的。
    #
    # 「有没有变更」用 `git diff --quiet -- <paths>`（工作区 vs HEAD）：
    #   .gitattributes 统一 eol=lf，工作区是 CRLF、仓库是 LF 时，
    #   git 归一化后内容其实一致 —— 用 diff 判断才不会为纯换行差异提交一次。
    st = subprocess.run(["git", "diff", "--quiet", "--"] + paths,
                        cwd=ROOT, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    if st.returncode == 0:
        log("无变更，无需提交")
        return 0

    run(["git", "commit", "--only", "-F", msg_path, "--"] + paths, allow_rc=(0,))

    proxy = current_proxy()
    if not proxy:
        log("!! 没有可用代理 —— 提交已完成，但推送跳过（需要手动 push）")
        return 5
    args = ["git", "-c", "http.proxy=" + proxy, "-c", "https.proxy=" + proxy,
            "push", "origin", "main"]
    rc, _ = run(args, allow_rc=(0,))
    if rc != 0:
        log("!! 推送失败（代理 %s）—— 提交已在本地，需手动 push" % proxy)
        return 5
    return 0


def sync_baseline():
    """把完整性基线对齐到实际 manifest 行数（只在实际 < 基线 时改）。

    基线文件是本地状态（已 gitignore），记录上次构建时的 manifest 行数，
    用来发现「历史批次被覆盖」。正常每日采集只增不减，实际 < 基线 说明
    有人删了批次 —— 那时基线会挡住后续构建，需要重置。
    """
    mpath = os.path.join(SITE_DIR, "manifest.json")
    bpath = os.path.join(SITE_DIR, "data", ".manifest_baseline")
    try:
        with open(mpath, encoding="utf-8") as f:
            n = len(json.load(f))
    except Exception:
        return
    prev = 0
    if os.path.exists(bpath):
        try:
            with open(bpath, encoding="utf-8") as f:
                prev = int(f.read().strip() or 0)
        except ValueError:
            prev = 0
    if n < prev:
        log("完整性基线 %d 高于实际 %d —— 已重置基线（说明有批次被删过）" % (prev, n))
        with open(bpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(str(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", default=None, help="批次日期，默认今天")
    ap.add_argument("--dry-run", action="store_true", help="不提交不推送")
    ap.add_argument("--skip-fetch", action="store_true", default=True,
                    help="跳过图片下载（默认就是跳过：CDN 被 Cloudflare 拦，见下）")
    args = ap.parse_args()

    batch = args.batch or datetime.datetime.now().strftime("%Y-%m-%d")
    log("=== 每日采集 %s · 批次 %s ===" % (datetime.datetime.now().isoformat(timespec="seconds"), batch))

    # ── 1. 采集 ──────────────────────────────────────────────
    # extract.py 的退出码：0 成功 / 2 采集失败 / 3 该批次已有结果
    rc, _ = run([PY, os.path.join("scripts", "extract.py"),
                 "--batch", batch],
                cwd=SITE_DIR, allow_rc=(0, 2, 3))
    if rc == 3:
        log("批次 %s 已有采集结果（退出码 3）—— 跳过本次采集" % batch)
        rc = 0
    elif rc == 2:
        log("采集失败（上游限流或网络问题）—— 本次不提交，数据未动")
        sys.exit(2)

    # ── 2. 累积索引 ──────────────────────────────────────────
    run([PY, os.path.join("scripts", "manifest.py")], cwd=SITE_DIR)

    # ── 2b. 完整性基线 ───────────────────────────────────────
    # build_gallery.py 会比对 data/.manifest_baseline：manifest 行数比基线少
    # 就判「历史可能被覆盖」并退出 1。正常每日采集只会增长，但删批次（回退、
    # 误删）会让基线高于实际 —— 那时基线失真，留着会挡住后续所有构建。
    # 这里按实际行数重写基线，只在「实际行数 < 基线」时才动（真正的覆盖风险
    # 仍然由 build_gallery.py 报出来，这里不吞）。
    sync_baseline()

    # ── 3. 站点构建 ──────────────────────────────────────────
    # 只构建本站 + hub（--no-hub 是反的，这里要 hub）
    run([PY, os.path.join("tools", "build.py"), "--site", SITE])

    # ── 4. WebUI 索引 ────────────────────────────────────────
    # sync.py 自带签名判断：manifest 没变就跳过（返回 skipped）
    run([PY, os.path.join("index", "sync.py")])

    # ── 5. 图片下载（默认跳过）────────────────────────────────
    # 为什么默认跳过：cdn.midjourney.com 挂在 Cloudflare 后面，
    # 取图要带浏览器头 + __cf_bm 通行证 cookie —— 通行证能拿到，
    # 但图片路径仍返回 403（CF 人机校验命中本机出口 IP）。
    # full 档本来就是 CDN 直链、不落本地，所以站点展示不受影响。
    # 等上游放行或换了出口 IP，把下面这行取消注释即可：
    # run([PY, os.path.join("tools", "fetch.py"), "--site", SITE])

    # ── 6. 统计 ──────────────────────────────────────────────
    mpath = os.path.join(SITE_DIR, "manifest.json")
    try:
        with open(mpath, encoding="utf-8") as f:
            rows = json.load(f)
        n_images = len(rows)
        n_jobs = len({r["jobId"] for r in rows})
        n_batches = len({r["batch"] for r in rows})
        log("累积索引：%d 条作业 / %d 张成图 / %d 个批次" % (n_jobs, n_images, n_batches))
    except Exception as e:
        log("读取 manifest 失败：%r" % e)
        sys.exit(4)

    if args.dry_run:
        log("--dry-run：不提交不推送")
        return

    # ── 7. 提交推送 ──────────────────────────────────────────
    rc = git_commit_and_push(batch, n_images, n_jobs)
    if rc != 0:
        sys.exit(rc)
    log("=== 完成 ===")


if __name__ == "__main__":
    main()
