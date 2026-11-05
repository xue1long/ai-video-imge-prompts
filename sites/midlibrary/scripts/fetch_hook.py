# -*- coding: utf-8 -*-
"""Midlibrary 取图钩子（站点级，shared/assets.py 自动发现）。

上游 midlibrary.io 的图片有两道门（2026-11-05 实测）：

1. **Referer 门**：不带 Referer 一律 403（Cloudflare 挑战页）；
   Referer 必须是 https 且 host 为 midlibrary.io 或其子域。
   外站热链（Referer 是别的主机）会被 Worker 挡掉，返回
   "Pictures are shown on midlibrary.io." —— 所以本站必须把图存一份，
   不能在页面上写上游地址（imagePolicy 用 local-only）。
2. **大图断流**：单张大图经常传到一半就没了（实测 960/1440/2048 三档都遇到过
   180 秒超时只收到部分字节）。shared/assets.py 的默认超时是 60 秒，
   对这个图源不够 —— 所以这里自带 fetch_bytes 通道，用更长的超时重试。

另外：
· 上游按 Accept 协商格式：带 image/webp 返回 webp，否则 jpeg。
  本站存 .webp（体积小三成），所以请求头里明确带上 webp。
· 并发压到 4：tools/fetch.py 的默认并发是 16/14，对这个慢源太猛。
  限流放在钩子里，不去改 tools/（AGENTS.md 规则 1：tools/ 不写单站分支）。
"""
import os
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from config import (IMAGE_ACCEPT, IMAGE_EXT, ORIGIN, PROXY, REQUEST_TIMEOUT,  # noqa: E402
                    RETRY, UA)

# 上游同时只放行少量连接（并发太高会大面积断流）
_MAX_PARALLEL = 4
_gate = threading.Semaphore(_MAX_PARALLEL)
# 同一秒内最多发多少个请求，避免把非营利站打疼
_MIN_GAP = 0.35
_last = [0.0]
_lock = threading.Lock()


def _throttle():
    """全局限速：最多 4 个并发，两次请求之间至少隔 0.35 秒。"""
    with _lock:
        now = time.time()
        wait = _last[0] + _MIN_GAP - now
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def _referer(url):
    """按图路径推出该条目页的地址当 Referer（上游只看 host，但这样更诚实）。"""
    name = url.rsplit("/", 1)[-1].split("?")[0]
    slug = name.split("-")[0]
    return "%s/library/%s" % (ORIGIN, slug)


def headers(url, referer):
    """追加到 shared/assets.py 默认请求头之后。"""
    return {
        "Accept": IMAGE_ACCEPT,
        "Referer": _referer(url),
    }


def fetch_bytes(url, headers, timeout):
    """自带取图通道：长超时 + 断流重试。

    shared/assets.py 优先调用本函数；没有它才走默认 urllib 通道。
    """
    hdr = dict(headers or {})
    hdr.setdefault("User-Agent", UA)
    hdr.setdefault("Accept", IMAGE_ACCEPT)
    hdr.setdefault("Referer", _referer(url))
    if PROXY:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    else:
        opener = urllib.request.build_opener()
    last = None
    for attempt in range(RETRY):
        try:
            with _gate:
                _throttle()
                req = urllib.request.Request(url, headers=hdr)
                with opener.open(req, timeout=REQUEST_TIMEOUT) as resp:
                    blob = resp.read()
            if len(blob) < 512:
                raise IOError("响应过小: %d bytes" % len(blob))
            return blob
        except Exception as e:  # 断流 / 超时 / 5xx 都重试
            last = e
            time.sleep(2.0 * (attempt + 1))
    raise IOError("取图失败 %s：%s: %s" % (url, type(last).__name__, last))
