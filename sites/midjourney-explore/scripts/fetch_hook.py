# -*- coding: utf-8 -*-
"""Midjourney Explore 站的取图钩子（供 shared/assets.py 调用）。

为什么需要它：
    cdn.midjourney.com 挂在 Cloudflare 后面，只带 User-Agent / Referer
    一律 403 —— 必须同时满足两点：
      1. 请求头像浏览器（Accept / Sec-Fetch-* / Origin）；
      2. 带着 Cloudflare 在 www.midjourney.com 下发的 __cf_bm 通行证 cookie。

    这个模块提供 shared/assets.py 约定的两个可选接口：
        headers(url, referer) -> dict   追加请求头
        prepare(opener, log) -> opener  预热：先访问 explore 页拿 cookie

    通行证一般有效 30 分钟；一次 prepare 足够覆盖一档图片的下载，
    过期时 assets.py 的重试会重新触发 403 —— 所以 prepare 里也做了
    「失败就换一个新的 opener 重来一次」的兜底。
"""
import http.cookiejar
import os
import sys
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


def prepare(opener, log=print):
    """预热：访问 explore 页拿 __cf_bm 通行证，返回带 cookie 的 opener。

    opener 是 assets.py 造好的（可能带代理），这里沿用它的代理设置，
    但换成带 CookieJar 的版本 —— cookie 是通行证的关键。
    """
    jar = http.cookiejar.CookieJar()
    new_opener = _make_opener(jar)
    for attempt in range(3):
        try:
            req = urllib.request.Request(CLEARANCE_URL, headers=PAGE_HEADERS)
            with new_opener.open(req, timeout=45) as resp:
                resp.read()
            names = sorted({c.name for c in jar})
            log("    Cloudflare 通行证就绪：%s" % ", ".join(names))
            return new_opener
        except Exception as e:
            wait = 4 * (attempt + 1)
            log("    取通行证失败(%s)，%ds 后重试" % (type(e).__name__, wait))
            time.sleep(wait)
    log("    取通行证失败，将直接尝试下载")
    return new_opener
