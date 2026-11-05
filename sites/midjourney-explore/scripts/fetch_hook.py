# -*- coding: utf-8 -*-
"""Midjourney Explore 站的取图钩子（供 shared/assets.py 调用）。

为什么需要它：
    cdn.midjourney.com 挂在 Cloudflare 后面，而 Cloudflare 按**客户端指纹**放行：
      1. 请求要像浏览器发起的图片请求（Accept / Sec-Fetch-* / Origin / Referer）；
      2. 客户端的 TLS 指纹也要像浏览器 —— **Python urllib 一律 403**（挑战页），
         请求头再全、哪怕带着 www.midjourney.com 下发的 __cf_bm 通行证也一样；
      3. 带着通行证 cookie 才稳定 —— 不带 cookie 的 curl 约有 1/4 的请求被挑战成 403。

    2026-11-05 实测（同一台机器、同一出口 IP、同一时刻）：
        Python urllib（浏览器头 + __cf_bm 通行证） → 403（5892 字节挑战页）
        curl.exe（浏览器头，不带 cookie）           → 200/200/403/403……（约 3/4 成功）
        curl.exe（浏览器头 + __cf_bm 通行证）       → 200 ×12（全部成功）
        curl.exe 取 .png 原图                       → 403（原图直链仍拿不到；full 档
                                                    本来就是 online 直链、不落本地）
    ⇒ 403 的成因是**客户端指纹 + 缺通行证**，不是「出口 IP 被 Cloudflare 挑战」。

    这个模块提供 shared/assets.py 约定的三个可选接口：
        headers(url, referer) -> dict          追加请求头
        prepare(opener, log) -> opener         预热：先访问 explore 页拿 cookie
        fetch_bytes(url, headers, timeout)     自带取图通道（curl），失败回落 urllib

    前两个供接口调用与回落通道用；第三个是取图的主通道 —— 没有它，
    shared/assets.py 的 urllib 路径会被 Cloudflare 拦成 403，图永远下不下来。
"""
import http.cookiejar
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
sys.path.insert(0, SITE)

from config import PROXY, UA  # noqa: E402

# 先访问这个页面拿 Cloudflare 通行证
CLEARANCE_URL = "https://www.midjourney.com/explore?tab=styles_top"

PAGE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# CDN 取图要像浏览器发起的图片请求
IMAGE_HEADERS = {
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.midjourney.com",
    "Sec-Fetch-Dest": "image",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "same-site",
}

# 浏览器味的取图通道：curl（Windows 自带 curl.exe 走 Schannel，TLS 指纹像浏览器）
CURL_NAMES = ("curl.exe", "curl")
COOKIE_NAMES = ("__cf_bm", "GAESA")
MIN_BLOB = 512          # 低于这个大小当成失败（挑战页/错误页都是几十 KB 的 HTML）

_lock = threading.Lock()
_curl_path = None        # None=还没找过；""=找过但系统里没有
_jar = None              # CookieJar：通行证 cookie
_opener = None           # urllib opener（带 cookie jar），回落通道用


def headers(url, referer):
    """追加 CDN 需要的请求头。"""
    h = dict(IMAGE_HEADERS)
    h["Referer"] = "https://www.midjourney.com/"
    return h


def _make_opener(jar):
    handlers = []
    if PROXY:
        handlers.append(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    handlers.append(urllib.request.HTTPCookieProcessor(jar))
    return urllib.request.build_opener(*handlers)


def _warm_up(log=None):
    """访问 explore 页拿 __cf_bm 通行证。返回是否拿到。"""
    jar = http.cookiejar.CookieJar()
    opener = _make_opener(jar)
    ok = False
    for attempt in range(3):
        try:
            req = urllib.request.Request(CLEARANCE_URL, headers=PAGE_HEADERS)
            with opener.open(req, timeout=45) as resp:
                resp.read()
            names = sorted({c.name for c in jar})
            if log:
                log("    Cloudflare 通行证就绪：%s" % ", ".join(names))
            ok = True
            break
        except Exception as e:
            wait = 4 * (attempt + 1)
            if log:
                log("    取通行证失败(%s)，%ds 后重试" % (type(e).__name__, wait))
            time.sleep(wait)
    with _lock:
        globals()["_jar"] = jar
        globals()["_opener"] = opener
    if not ok and log:
        log("    取通行证失败，将直接尝试下载")
    return ok


def prepare(opener, log=print):
    """预热：访问 explore 页拿 __cf_bm 通行证，返回带 cookie 的 opener。

    opener 是 assets.py 造好的（可能带代理），这里沿用它的代理设置，
    但换成带 CookieJar 的版本 —— cookie 是通行证的关键。
    拿到的 cookie 同时供 fetch_bytes 的 curl 通道使用（-b）。
    """
    _warm_up(log)
    with _lock:
        return _opener or opener


# ── 取图通道 ──────────────────────────────────────────

def _find_curl():
    """找系统里的 curl（Windows 自带 curl.exe；Linux 一般是 curl）。"""
    global _curl_path
    with _lock:
        if _curl_path is None:
            found = ""
            for name in CURL_NAMES:
                p = shutil.which(name)
                if p:
                    found = p
                    break
            _curl_path = found
        return _curl_path or None


def _cookie_string():
    """把通行证 cookie 拼成 curl 的 -b 参数（不带 cookie 约 1/4 请求会被挑战）。"""
    with _lock:
        jar = _jar
    if jar is None:
        return ""
    parts = []
    for c in jar:
        if c.name in COOKIE_NAMES and c.value:
            parts.append("%s=%s" % (c.name, c.value))
    return "; ".join(parts)


def _curl_get(url, headers, timeout, cookie=""):
    """用 curl 取一张图，返回字节。

    为什么走 curl 而不是 urllib：Cloudflare 判客户端指纹（TLS JA3）。
    同一出口 IP 上 urllib 403、curl 200 —— 见模块注释里的实测。
    """
    curl = _find_curl()
    if not curl:
        raise IOError("系统里找不到 curl")
    cmd = [curl, "-sS", "--fail", "--max-time", str(int(timeout))]
    proxy = PROXY or os.environ.get("FETCH_PROXY", "")
    if proxy:
        cmd += ["--proxy", proxy]
    for k, v in (headers or {}).items():
        cmd += ["-H", "%s: %s" % (k, v)]
    if cookie:
        cmd += ["-b", cookie]
    cmd += ["-o", "-", url]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout + 15)
    if p.returncode != 0:
        raise IOError("curl rc=%d: %s" % (
            p.returncode, p.stderr.decode("utf-8", "replace").strip()[:160]))
    if len(p.stdout) < MIN_BLOB:
        raise IOError("curl 响应过小: %d bytes" % len(p.stdout))
    return p.stdout


def _urllib_get(url, headers, timeout):
    """回落通道：urllib + __cf_bm 通行证（curl 不可用时用；多数情况也会被 403）。"""
    with _lock:
        opener = _opener
    if opener is None:
        _warm_up()
        with _lock:
            opener = _opener
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=timeout) as resp:
        return resp.read()


def fetch_bytes(url, headers, timeout=60):
    """shared/assets.py 的取图通道：curl 优先，失败则换新通行证再试，最后回落 urllib。

    返回图片字节；取不到就抛异常（由 assets.py 统一重试与记账）。
    """
    try:
        return _curl_get(url, headers, timeout, _cookie_string())
    except Exception:
        pass
    # 通行证约 30 分钟过期 —— 换一份新的再试一次
    try:
        _warm_up()
        return _curl_get(url, headers, timeout, _cookie_string())
    except Exception:
        return _urllib_get(url, headers, timeout)
