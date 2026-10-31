# -*- coding: utf-8 -*-
"""tools 公共模块：读取站点清单、路径解析、子进程执行"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES_DIR = os.path.join(ROOT, "sites")
CFG = os.path.join(ROOT, "sites.json")


def load_cfg():
    with open(CFG, encoding="utf-8") as f:
        return json.load(f)


def site_dir(sid):
    return os.path.join(SITES_DIR, sid)


def select(cfg, only=None):
    """按 --site 过滤，返回站点列表；id 不存在时报错退出。"""
    sites = cfg["sites"]
    if not only:
        return sites
    ids = [s["id"] for s in sites]
    if only not in ids:
        sys.exit(f"未知站点: {only}\n可选: {', '.join(ids)}")
    return [s for s in sites if s["id"] == only]


def exclude(sites, skip=None):
    """按 --skip a,b 排除站点；id 不存在时报错退出。

    拼错的 id 不静默放过——CI 里少排一个站，就等于该站的产物没人校验。
    """
    if not skip:
        return sites
    want = [x.strip() for x in skip.split(",") if x.strip()]
    ids = [s["id"] for s in sites]
    unknown = [x for x in want if x not in ids]
    if unknown:
        sys.exit(f"未知站点: {', '.join(unknown)}\n可选: {', '.join(ids)}")
    return [s for s in sites if s["id"] not in want]


def run(cmd, cwd, env_extra=None, quiet=False):
    """执行子进程，失败即退出。"""
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    if not quiet:
        print("    $ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, env=env, text=True,
                       capture_output=quiet)
    if r.returncode != 0:
        if quiet and r.stderr:
            print(r.stderr[-2000:], file=sys.stderr)
        sys.exit(f"命令失败（exit {r.returncode}）: {' '.join(cmd)}")
    return r


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def dir_size(p):
    total = 0
    for dp, _, fns in os.walk(p):
        for fn in fns:
            try:
                total += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    return total


def parse_args(argv, spec):
    """极简参数解析：--key value / --flag

    spec: {"site": "value", "workers": "value", "check": "flag"}
    """
    out = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if not a.startswith("--"):
            i += 1
            continue
        key = a[2:]
        if key not in spec:
            sys.exit(f"未知参数: {a}")
        if spec[key] == "flag":
            out[key] = True
            i += 1
        else:
            if i + 1 >= len(argv):
                sys.exit(f"参数 {a} 缺少值")
            out[key] = argv[i + 1]
            i += 2
    return out
