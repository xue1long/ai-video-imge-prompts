# -*- coding: utf-8 -*-
"""四站共用的图片下载与校验

档位 → manifest 字段的对应只有一条规则：<tier>_url / <tier>_path。
  portrait / pose / pose-depth：thumb、full
  costume：thumb、img、png
各站只需在 sites.json 里写 tiers 和 source（下载时作为 Referer）。

下载幂等：已存在且大于 1 KB 的文件跳过；先写 .part 再改名，中断不会留下半个文件。
"""
import json, os, struct, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
MIN_BYTES = 1024
RETRIES = 4


def load_manifest(site_dir):
    with open(os.path.join(site_dir, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def tier_keys(rows, tier):
    url_key, path_key = tier + "_url", tier + "_path"
    if rows and (url_key not in rows[0] or path_key not in rows[0]):
        raise KeyError(f"manifest 里没有 {url_key} / {path_key}")
    return url_key, path_key


def rel_path(p):
    # manifest 里的路径一律当作 / 分隔，Windows 上 os.path.join 也能正确处理
    return p.replace("\\", "/")


# ── 下载 ────────────────────────────────────────────

def download(site_dir, tier, referer, workers=12, log=print):
    """下载一档图片，返回失败列表 [(id, 原因)]。

    环境变量 FETCH_PROXY（如 http://127.0.0.1:7897）可为下载统一挂代理，
    用于图源被 DNS 污染 / 需要出口 IP 的站点；不设置时行为不变。
    """
    rows = load_manifest(site_dir)
    url_key, path_key = tier_keys(rows, tier)
    proxy = os.environ.get("FETCH_PROXY", "")
    if proxy:
        log(f"  FETCH_PROXY = {proxy}")
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        opener = urllib.request.build_opener()
    total = len(rows)
    lock = threading.Lock()
    state = {"done": 0, "bytes": 0}
    failed = []
    t0 = time.time()

    def tick(n_bytes):
        with lock:
            state["done"] += 1
            state["bytes"] += n_bytes
            n = state["done"]
        if n % 200 == 0 or n == total:
            el = max(time.time() - t0, 0.001)
            log("  %d/%d  %.1f MB  %.1f files/s" % (n, total, state["bytes"] / 1048576, n / el))

    def fetch(r):
        dst = os.path.join(site_dir, rel_path(r[path_key]))
        if os.path.exists(dst) and os.path.getsize(dst) > MIN_BYTES:
            tick(os.path.getsize(dst))
            return
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".part"
        last = None
        for attempt in range(RETRIES):
            try:
                req = urllib.request.Request(r[url_key], headers={"User-Agent": UA, "Referer": referer})
                with opener.open(req, timeout=60) as resp:
                    blob = resp.read()
                if len(blob) < MIN_BYTES // 2:
                    raise IOError("响应过小: %d bytes" % len(blob))
                with open(tmp, "wb") as f:
                    f.write(blob)
                os.replace(tmp, dst)
                tick(len(blob))
                return
            except Exception as e:  # 网络错误、HTTP 错误、写盘错误都重试
                last = e
                time.sleep(1.2 * (attempt + 1))
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError: pass
        with lock:
            failed.append((r.get("id"), "%s: %s" % (type(last).__name__, last)))

    log("tier=%s workers=%d total=%d" % (tier, workers, total))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(fetch, rows))
    log("完成 %d/%d, %.1f MB, 用时 %.0fs" % (state["done"], total, state["bytes"] / 1048576, time.time() - t0))
    if failed:
        with open(os.path.join(site_dir, "failed_%s.json" % tier), "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=1)
    return failed


# ── 校验 ────────────────────────────────────────────

def image_dims(path):
    """从文件头读宽高，支持 JPEG / PNG / WebP；读不出返回 None。"""
    with open(path, "rb") as f:
        head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", head[16:24])
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            fmt = head[12:16]
            if fmt == b"VP8 ":
                w, h = struct.unpack("<HH", head[26:30])
                return (w & 0x3FFF, h & 0x3FFF)
            if fmt == b"VP8L":
                v = int.from_bytes(head[21:25], "little")
                return ((v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1)
            if fmt == b"VP8X":
                return (int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1)
            return None
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                b = f.read(1)
                if not b:
                    return None
                if b != b"\xff":
                    continue
                m = f.read(1)
                while m == b"\xff":
                    m = f.read(1)
                if not m:
                    return None
                m = m[0]
                if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                    continue
                seg = f.read(2)
                if len(seg) < 2:
                    return None
                n = struct.unpack(">H", seg)[0]
                if m in (0xC0, 0xC1, 0xC2):
                    d = f.read(5)
                    h, w = struct.unpack(">HH", d[1:5])
                    return (w, h)
                f.seek(n - 2, 1)
    return None


def verify(site_dir, tiers):
    """逐档检查存在、体积、可读宽高。返回 {tier: {ok, bytes, dims, missing, broken}}。"""
    rows = load_manifest(site_dir)
    report = {}
    for tier in tiers:
        _, path_key = tier_keys(rows, tier)
        t = {"ok": 0, "bytes": 0, "dims": {}, "missing": [], "broken": []}
        for r in rows:
            rel = rel_path(r[path_key])
            p = os.path.join(site_dir, rel)
            if not os.path.exists(p):
                t["missing"].append(rel); continue
            sz = os.path.getsize(p)
            if sz < MIN_BYTES:
                t["broken"].append((rel, "size %d" % sz)); continue
            d = image_dims(p)
            if not d:
                t["broken"].append((rel, "not an image")); continue
            t["ok"] += 1
            t["bytes"] += sz
            k = "%dx%d" % tuple(d)
            t["dims"][k] = t["dims"].get(k, 0) + 1
        report[tier] = t
    return len(rows), report
