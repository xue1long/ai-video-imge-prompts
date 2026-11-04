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

契约是**封闭**的：脚本只会以这五个码退出。子进程返回任何其它退出码
（1、137、其它脚本自造的码）时，一律归到 4（构建 / 索引失败）——
那一步失败就是失败，外层需要知道「有东西没做完，需要人看」。
2026-11-04 实测踩中：构建被运行时的删除闸门打断（SystemExit(1)），
退出码 1 逃逸出去，落在契约之外，自动化只能走「未定义」分支。
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


def run(args, cwd=ROOT, env=None, allow_rc=(0,), fail_rc=4):
    """跑一条命令，返回 (rc, 输出)。输出直接转发到日志，便于事后排查。

    fail_rc：子进程返回不在 allow_rc 里的退出码时，本脚本以它退出。
    默认 4（构建 / 索引失败）——这是契约里唯一适合「某一步没做成」的码。
    采集那一步显式传 fail_rc=2（上游限流，语义不同：不重试也没坏）。
    """
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
        # 退出码 0 不可能走到这里（0 恒在 allow_rc 里），但保底不返回 0
        rc = p.returncode or fail_rc
        if rc != fail_rc:
            log("  （子进程退出码 %d → 归入契约码 %d）" % (rc, fail_rc))
        sys.exit(fail_rc)
    return p.returncode, out


def build_with_committed_config():
    """用**仓库里已提交的** sites.json 重建入口页（hub）。

    为什么必须用已提交版本，而不是工作区当前版本：
        hub/build_hub.py 读 sites.json 算总图数（total_images）与站点统计。
        CI 的闸门 3 跑在干净检出上，用的必然是**已提交**的配置。
        若工作区有别人未提交的 sites.json 改动，我们按工作区配置算出的 hub
        就与 CI 重建出的结果对不上 —— 提交上去 CI 必红。
        2026-11-04 实测踩中：另一会话在改 sites.json（prompthero 去掉 full 档），
        改动未提交；我们按工作区配置算出 115,931 提交上去，
        CI 按已提交配置重建得 128,929 → 闸门 3 红。

    做法：构建前把 sites.json 临时换成已提交版本，构建完再换回来。
    工作区那份改动全程不丢（用 try/finally 保证还原）。

    只影响 hub —— 站点自己的产物由各自 build_gallery.py 生成，
    它们不读 sites.json（已核实：midjourney-explore 的 build_gallery.py 不读）。

    返回备份文件路径（构建后需用 restore_working_config 还原），
    工作区本就等于已提交版本时返回 None。
    """
    import shutil
    import tempfile

    p = subprocess.run(["git", "show", "HEAD:sites.json"],
                       cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if p.returncode != 0:
        log("取不到 HEAD 版 sites.json —— 按工作区配置构建（可能有偏差）")
        return False

    cur_path = os.path.join(ROOT, "sites.json")
    with open(cur_path, "rb") as f:
        cur_bytes = f.read()
    if cur_bytes == p.stdout:
        return None   # 工作区就是已提交版本，没什么要换的

    bak = os.path.join(tempfile.mkdtemp(prefix="mj-cfg-"), "sites.json")
    try:
        with open(bak, "wb") as f:
            f.write(cur_bytes)
        with open(cur_path, "wb") as f:
            f.write(p.stdout)
        log("  已临时换用 HEAD 版 sites.json 构建入口页（工作区改动稍后还原）")
        return bak
    except Exception:
        shutil.rmtree(os.path.dirname(bak), ignore_errors=True)
        raise


def restore_working_config(bak):
    """把 build_with_committed_config 换掉的 sites.json 还原回工作区版本。"""
    if not bak:
        return
    import shutil
    try:
        with open(bak, "rb") as f:
            data = f.read()
        with open(os.path.join(ROOT, "sites.json"), "wb") as f:
            f.write(data)
        log("  已还原工作区的 sites.json")
    finally:
        shutil.rmtree(os.path.dirname(bak), ignore_errors=True)


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


def verify_gate3_clean_checkout():
    """在「干净检出」上预演 CI 闸门 3：新提交必须自洽（重建产物 == 提交产物）。

    CI 闸门 3 跑在干净检出上：
        python3.8 tools/build.py --skip prompts
        git diff --exit-code -- hub sites
    它比对的是「**新提交里的产物**」与「**新提交重建出来的产物**」——
    两边都是新提交的内容，所以闸门绿的条件是：
        新提交的产物，必须能用新提交里的输入重建出来。

    这里用 `git worktree` 造一个临时检出，把「将要提交的内容」放进去：
        - 站点与 hub 的产物：工作区版本（即将提交的那份）
        - 配置源 sites.json：**仓库里已提交的版本**
          （CI 跑在干净检出上，用的必然是已提交的配置；
           如果工作区有别人未提交的 sites.json 改动，那份改动不在新提交里，
           CI 就看不到它 —— 而我们本地产物是按那份改动算出来的，必然对不上）
        - 其余输入（其他站的 manifest 等）：已提交版本

    为什么必须这样验：
        「重建前后一致」只保证**确定性**（同输入→同输出），
        不保证**产物与输入自洽**。
        工作区若有别人未提交的配置改动（如 2026-11-04 的 sites.json），
        我们构建出的 hub 会带着那份改动；CI 的干净检出按已提交配置重建 ——
        两边对不上，CI 必红，而本地任何确定性校验都查不出来。

    返回 True=闸门会绿；False=会红（调用方应放弃提交）。
    """
    import shutil
    import tempfile

    log("闸门预演：模拟干净检出，验证新提交自洽")

    def git_in(cwd, *args):
        return subprocess.run(["git", "-C", cwd] + list(args),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    tmp = tempfile.mkdtemp(prefix="mj-gate3-")
    try:
        # 1. 临时检出：内容 = HEAD（含已提交的历史批次与配置）
        r = git_in(ROOT, "worktree", "add", "--detach", tmp, "HEAD")
        if r.returncode != 0:
            log("  无法创建临时检出（%s）—— 跳过闸门预演"
                % r.stderr.decode("utf-8", "replace").strip())
            return True

        # 2. 放入「将要提交的内容」
        for path in ("sites/%s" % SITE, "hub"):
            src = os.path.join(ROOT, path)
            dst = os.path.join(tmp, path)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns(
                                    "thumbs", "mid", "img", "png", "raw",
                                    "__pycache__", "*.pyc"))
        #   配置源必须用**已提交版本**：CI 看不到未提交的改动。
        head_cfg = git_in(ROOT, "show", "HEAD:sites.json")
        if head_cfg.returncode == 0:
            with open(os.path.join(tmp, "sites.json"), "wb") as f:
                f.write(head_cfg.stdout)

        # 3. 干净检出里重建（跳过 prompts：它的数据源不入库，CI 也跳过）
        p = subprocess.run([PY, os.path.join("tools", "build.py"), "--skip", "prompts"],
                           cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if p.returncode != 0:
            log("  干净检出里重建失败 —— 放弃提交：")
            print(p.stdout.decode("utf-8", "replace"), end="")
            return False

        # 4. 比对：重建后的产物 vs 我们将要提交的产物
        #    （不是 vs HEAD —— HEAD 里没有今天的新批次，比那个必然不一致）
        #    只比「会被提交、且 CI 闸门 3 会看」的产物：
        #      - 图片目录（thumbs/ mid/ img/ png/ raw/）不入库，不比
        #      - __pycache__ / .pyc 不入库，不比
        #      - 其余已跟踪的文件逐字节比
        ignored_dirs = ("thumbs", "mid", "img", "png", "raw", "__pycache__")
        names = []
        for path in ("sites/%s" % SITE, "hub"):
            src = os.path.join(ROOT, path)
            dst = os.path.join(tmp, path)
            if not os.path.isdir(src):
                continue
            for dirpath, dirs, files in os.walk(src):
                dirs[:] = [d for d in dirs if d not in ignored_dirs]
                for fn in files:
                    if fn.endswith(".pyc"):
                        continue
                    a = os.path.join(dirpath, fn)
                    rel = os.path.relpath(a, ROOT)
                    b = os.path.join(tmp, rel)
                    if not os.path.isfile(b):
                        names.append(rel)
                        continue
                    with open(a, "rb") as f1, open(b, "rb") as f2:
                        if f1.read() != f2.read():
                            names.append(rel)
        if names:
            log("  !! 干净检出重建后与将要提交的产物不一致 —— 提交上去 CI 闸门 3 会红：")
            for n in sorted(names)[:20]:
                log("     %s" % n)
            if len(names) > 20:
                log("     …… 共 %d 个文件" % len(names))
            log("  常见原因：工作区有别人未提交的配置改动（如 sites.json），")
            log("  产物是用工作区配置算出来的，而 CI 用的是仓库里已提交的配置。")
            log("  请让配置改动先入库，或把本地产物改到与已提交配置一致。")
            return False

        log("  干净检出重建结果与将要提交的产物一致 —— 闸门 3 会绿")
        return True
    finally:
        git_in(ROOT, "worktree", "remove", "--force", tmp)
        shutil.rmtree(tmp, ignore_errors=True)


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

    # ── 闸门预演：用「干净检出」重建，比对是否与仓库产物一致 ──────────
    #
    # 上面那个「重建前后」校验只保证**确定性**（同样输入 → 同样输出），
    # 但保证不了「产物与仓库里已提交的版本对得上」。CI 的闸门 3 是：
    #
    #     python3.8 tools/build.py --skip prompts
    #     git diff --exit-code -- hub sites
    #
    # 它跑在**干净检出**上 —— 输入是**仓库里已提交的配置**。
    # 而我们在工作区构建，输入是**工作区当前的配置**。
    # 两者只要有一处不同（哪怕是别人还没提交的在改改动），产物就会对不上，
    # CI 必红。
    #
    # 2026-11-04 实测踩中：另一个会话正在改 sites.json（prompthero 去掉 full 档），
    # 改动未提交。我们在工作区构建 hub → 算出 115,931；提交上去后，
    # CI 的干净检出按仓库里已提交的 sites.json 重建 → 算出 128,929 → 闸门 3 红。
    # 提交前那套「重建前后」校验完全查不出来（重建是确定的，只是输入不同）。
    #
    # 这里补上缺的那一环：把「将要提交的内容」放进一个临时干净检出里重建，
    # 与仓库里的产物比对 —— 等于在本地把 CI 的闸门 3 先跑一遍。
    if not verify_gate3_clean_checkout():
        return 4

    # ── 隔离提交：只用 git commit --only -- <paths> ────────────────────
    # 为什么不用 `git add` + `git commit`：
    #   `git commit` 提交的是**整个暂存区**。若此时有人（另一个会话）
    #   暂存了别的改动，会被连带提交进这次「每日采集」提交里 —— 那是别人
    #   的工作，不该由定时任务替他发布。
    #   `git commit --only -- <paths>` 只提交指定路径的工作区内容，
    #   **完全不碰暂存区**（实测 dry-run 后暂存区保持原样）—— 正是这里要的。
    #
    # ── 登记新增文件（必须在变更检测之前）──────────────────────────
    # `git commit --only` 只提交**已被 git 跟踪**的路径；未跟踪的新文件会被
    # **静默跳过**，而且退出码仍是 0 —— 不报错、不提示，像是提交成功了。
    #
    # 这个坑在「每日采集」里必然踩到：新批次目录 data/daily/<日期>/ 是
    # 每次新建的，新出现的宽高比落地页 aspect/<比>/ 也是新建的。
    # 2026-11-03 实测：manifest.json 里已经有 2026-11-03 的 200 条作业，
    # 但 data/daily/2026-11-03/ 与两个新 aspect 页都没进仓库 ——
    # 干净检出上 CI 直接断言失败（manifest 作业数 600 != 各批次之和 400）。
    #
    # 解法：`git add --intent-to-add`（-N）把新文件登记进索引，
    # 但**不写入内容**（内容仍留在工作区），于是：
    #   - `git commit --only -- <paths>` 之后能把新文件一起提交；
    #   - 暂存区里别人的改动完全不受影响（--only 只取指定路径的内容）。
    # 实测（gt5）：别人的 other.txt 提交后仍留在暂存区，我们的 3 个文件正常入库。
    #
    # 为什么不是 `git add`：那会把新文件的内容真正写进暂存区，
    # 破坏「不碰暂存区」的承诺（虽然 --only 最终仍只提交指定路径，
    # 但暂存区内容会被我们改动，别人后续提交会带上我们的文件）。
    #
    # 为什么必须放在变更检测**之前**：登记之后 `git diff` 才看得见新文件，
    # 否则「本次只有新增文件、已跟踪文件都没变」的情况会被误判成
    # 「无变更，无需提交」而整批漏掉 —— 那正是新批次首日的典型形态。
    new_files = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--"] + paths,
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    ).stdout.decode("utf-8", errors="replace").split("\n")
    new_files = [f for f in new_files if f.strip()]
    if new_files:
        log("登记 %d 个新增文件（intent-to-add）" % len(new_files))
        subprocess.run(["git", "add", "--intent-to-add", "--"] + new_files,
                       cwd=ROOT, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

    # 「有没有变更」用 `git diff --quiet -- <paths>`（工作区 vs HEAD）：
    #   .gitattributes 统一 eol=lf，工作区是 CRLF、仓库是 LF 时，
    #   git 归一化后内容其实一致 —— 用 diff 判断才不会为纯换行差异提交一次。
    #   新文件已在上面登记为 intent-to-add，diff 也能看见它们。
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
    # 采集失败的语义是「上游限流，明日重试」，与构建失败不同 → fail_rc=2
    rc, _ = run([PY, os.path.join("scripts", "extract.py"),
                 "--batch", batch],
                cwd=SITE_DIR, allow_rc=(0, 2, 3), fail_rc=2)
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
    # 只构建本站 + hub（--no-hub 是反的，这里要 hub）。
    # 构建入口页时临时换用已提交的 sites.json —— CI 的闸门 3 跑在干净检出上，
    # 用的是已提交配置；按工作区配置算出来的产物提交上去必然对不上。
    cfg_bak = None
    try:
        cfg_bak = build_with_committed_config()
        run([PY, os.path.join("tools", "build.py"), "--site", SITE])
    finally:
        restore_working_config(cfg_bak)

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
