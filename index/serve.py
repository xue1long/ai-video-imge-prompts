# -*- coding: utf-8 -*-
"""本地服务：11 个端点的唯一入口。

契约见 docs/SPEC_MATERIAL_MANAGER.md，改动端点前先改那份文档。
同一个进程既发接口又发静态页面，前端不需要跨域，也不需要第二个服务。

读接口之前会按需重同步索引：manifest 或字段映射变了就重建（见 sync_if_stale）。
加站之后 WebUI 里查不到新集合，就是缺了这一步。

用法:
  python index/serve.py                  # http://127.0.0.1:8787/
  python index/serve.py --port 9000
  python index/serve.py --root <dir>     # 指定数据根（测试用）
  python index/serve.py --no-reload      # manifest 变了也不自动同步
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import socket
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import actions
import catalog
import store

DEFAULT_PORT = 8787
MAX_PAGE_SIZE = 200
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class ApiError(Exception):
    def __init__(self, status, code, detail="", extra=None):
        super().__init__(detail or code)
        self.status = status
        self.code = code
        self.detail = detail or code
        self.extra = extra or {}


class Handler(BaseHTTPRequestHandler):
    root = "."
    db_path = "gallery.db"
    config = {}
    server_version = "MaterialManager/1.0"
    # 自动重同步的闸门：manifest 或字段映射变了就重建索引。
    # 以前这里只判断「库在不在」——库在就永远不同步，于是新加的站
    # （加进 catalog.SOURCES + sites.json 之后）在 WebUI 里根本查不到，
    # 而站点页面一切正常，没有任何报错。拆 mj-styles 那次就栽在这里。
    auto_sync = True
    sync_lock = threading.Lock()

    def read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            raise ApiError(400, "bad_request", "请求体不是合法 JSON")

    # ── 响应helper ────────────────────────────────────────────────
    def send_json(self, payload, status=200):
        blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(blob)

    def send_error_json(self, status, code, detail="", extra=None):
        payload = {"error": code, "detail": detail or code}
        payload.update(extra or {})
        self.send_json(payload, status)

    def db(self):
        return store.connect(self.db_path)

    # ── 路由 ─────────────────────────────────────────────────────
    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = urllib.parse.unquote(parsed.path)
            query = urllib.parse.parse_qs(parsed.query)
            if path.startswith("/api/"):
                # 读接口前按需重同步：manifest 变了（采集更新 / 加站）时
                # 索引跟着变。否则库里还是旧内容，页面看着正常但数据是陈的。
                maybe_sync()
                return self.route_api(path, query)
            if path == "/" or path == "/index.html":
                return self.serve_web("index.html")
            if path.startswith("/media/"):
                return self.serve_media(path[len("/media/"):])
            return self.serve_web(path.lstrip("/"))
        except ApiError as e:
            self.send_error_json(e.status, e.code, e.detail, e.extra)
        except BrokenPipeError:
            pass
        except Exception as e:  # noqa: BLE001 - 单机工具，任何异常都变 500 而不是断连
            self.send_error_json(500, "internal", str(e))

    def do_POST(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            return self.route_api(urllib.parse.unquote(parsed.path), urllib.parse.parse_qs(parsed.query), post=True)
        except ApiError as e:
            self.send_error_json(e.status, e.code, e.detail, e.extra)
        except Exception as e:  # noqa: BLE001
            self.send_error_json(500, "internal", str(e))

    def route_api(self, path, query, post=False):
        parts = [p for p in path.split("/") if p]
        # ["api", ...]
        if parts[:1] != ["api"]:
            raise ApiError(404, "not_found", path)
        rest = parts[1:]

        if rest == ["collections"] and not post:
            conn = self.db()
            try:
                return self.send_json({"collections": _with_views(conn, store.collections(conn))})
            finally:
                conn.close()

        if rest == ["items"] and not post:
            conn = self.db()
            try:
                collection = (query.get("collection") or [None])[0]
                page = max(1, int((query.get("page") or ["1"])[0]))
                size = int((query.get("size") or ["120"])[0])
                size = max(1, min(size, MAX_PAGE_SIZE))
                facets = parse_facets(query.get("facet") or [])
                q = ((query.get("q") or [""])[0] or "").strip()
                include_hidden = (query.get("include_hidden") or ["0"])[0] not in ("0", "", "false", "False")
                sort = (query.get("sort") or ["id"])[0]
                total, items = store.list_items(
                    conn, collection, page, size, facets, q or None, include_hidden, sort
                )
                return self.send_json({"total": total, "page": page, "size": size, "items": items})
            finally:
                conn.close()

        if rest == ["facets"] and not post:
            conn = self.db()
            try:
                collection = (query.get("collection") or [None])[0]
                include_hidden = (query.get("include_hidden") or ["0"])[0] not in ("0", "", "false", "False")
                return self.send_json(
                    {"facets": store.list_facets(conn, collection, include_hidden)}
                )
            finally:
                conn.close()

        if len(rest) == 2 and rest[0] == "items" and not post:
            conn = self.db()
            try:
                got = store.get_item(conn, rest[1])
            finally:
                conn.close()
            if not got:
                raise ApiError(404, "not_found", rest[1])
            return self.send_json(got)

        if rest == ["send"] and post:
            return self.handle_send()

        if rest == ["import"] and post:
            return self.handle_import()

        if len(rest) == 3 and rest[0] == "items" and rest[2] == "replace" and post:
            return self.handle_replace(rest[1])

        if len(rest) == 3 and rest[0] == "items" and rest[2] == "attach" and post:
            return self.handle_attach(rest[1])

        if len(rest) == 3 and rest[0] == "items" and rest[2] == "tags" and post:
            return self.handle_tags(rest[1])

        if len(rest) == 3 and rest[0] == "items" and rest[2] == "fav" and post:
            return self.handle_fav(rest[1])

        raise ApiError(404, "not_found", path)

    def incoming_sources(self):
        """把这次请求摊平成「一组待处理图片的本地路径」。

        三个来源在这里合流：multipart 上传（浏览器选文件/剪贴板贴图，可一次多个）、
        `url`（链接）、`path`（本机路径，脚本用）。返回 (路径列表, 用完要删的临时目录列表)。
        """
        ctype = self.headers.get("Content-Type") or ""
        if ctype.startswith("multipart/form-data"):
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b""
            parts = [p for p in parse_multipart_parts(ctype, body) if p[0] == "file" and p[2]]
            if not parts:
                raise ApiError(400, "bad_request", "缺少 file 字段")
            tmpdir = tempfile.mkdtemp(prefix="mm-upload-")
            paths, used = [], set()
            for _, fname, blob in parts:
                # 一次传多张时文件名可能撞车，撞了才加 -2/-3，单张时名字原样不动
                base = os.path.basename(fname or "") or "upload.bin"
                stem, ext = os.path.splitext(base)
                cand, i = base, 2
                while cand in used:
                    cand = f"{stem}-{i}{ext}"
                    i += 1
                used.add(cand)
                src = os.path.join(tmpdir, cand)
                with open(src, "wb") as f:
                    f.write(blob)
                paths.append(src)
            return paths, [tmpdir]

        payload = self.read_json()
        url = (payload.get("url") or "").strip()
        if url:
            tmpdir = tempfile.mkdtemp(prefix="mm-url-")
            try:
                return [actions.fetch_url(url, tmpdir)], [tmpdir]
            except actions.BadSource as e:
                shutil.rmtree(tmpdir, ignore_errors=True)
                raise ApiError(400, "bad_request", str(e))
            except actions.UnsupportedExt as e:
                shutil.rmtree(tmpdir, ignore_errors=True)
                raise ApiError(415, "unsupported_ext", str(e))
        path = (payload.get("path") or "").strip()
        if not path:
            raise ApiError(400, "bad_request", "需要 file 上传、url 链接或 path 路径")
        if not os.path.exists(path):
            raise ApiError(404, "not_found", path)
        return [path], []

    def incoming_source(self):
        """单个来源（import / replace 用）：只取第一个。"""
        paths, tmpdirs = self.incoming_sources()
        return paths[0], (tmpdirs[0] if tmpdirs else None)

    def handle_import(self):
        """收一张新素材：multipart 上传、`url` 链接、`path` 本机路径。"""
        tmpdir = None
        try:
            src, tmpdir = self.incoming_source()
            is_dir = os.path.isdir(src)
            conn = self.db()
            try:
                count, skipped, ids = actions.import_path(self.root, conn, src)
                conn.commit()
                first = store.get_item(conn, ids[0]) if ids else None
            except actions.UnsupportedExt as e:
                raise ApiError(415, "unsupported_ext", str(e))
            except actions.Duplicate as e:
                raise ApiError(409, "duplicate", e.existing_id, {"existing_id": e.existing_id})
            finally:
                conn.close()
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)

        if is_dir:
            return self.send_json({"ok": True, "imported": count, "skipped": skipped, "item_ids": ids})
        return self.send_json(
            {
                "ok": True,
                "item_id": ids[0],
                "assets": 1,
                "thumb": True,
                "prompt_raw": (first or {}).get("item", {}).get("prompt_raw", ""),
            }
        )

    def handle_replace(self, item_id):
        """替换一张素材的展示图。三个来源同上，原图保留。"""
        conn = self.db()
        try:
            if not store.item_exists(conn, item_id):
                raise ApiError(404, "not_found", item_id)
            tmpdir = None
            try:
                src, tmpdir = self.incoming_source()
                try:
                    result = actions.replace_image(self.root, conn, item_id, src)
                    conn.commit()
                except actions.UnsupportedExt as e:
                    raise ApiError(415, "unsupported_ext", str(e))
            finally:
                if tmpdir:
                    shutil.rmtree(tmpdir, ignore_errors=True)
        finally:
            conn.close()
        return self.send_json(dict(result, ok=True))

    def handle_attach(self, item_id):
        """给已有素材**追加**图片：一次可以传多张，主图不动。

        和 `/replace` 的区别就在这儿：replace 是「换掉第一张」（新图排到最前），
        attach 是「在提示词下面再接一张自己的图」（排在最后）。原图永远不删。
        """
        conn = self.db()
        tmpdirs = []
        try:
            if not store.item_exists(conn, item_id):
                raise ApiError(404, "not_found", item_id)
            paths, tmpdirs = self.incoming_sources()

            # path 传目录时展开一层，和 import 的行为保持一致
            srcs = []
            for p in paths:
                if os.path.isdir(p):
                    for entry in sorted(os.listdir(p)):
                        sub = os.path.join(p, entry)
                        if os.path.isfile(sub) and os.path.splitext(sub)[1].lower() in store.MIME:
                            srcs.append(sub)
                else:
                    srcs.append(p)

            added, skipped, failed = [], [], []
            for src in srcs:
                try:
                    got = actions.attach_image(self.root, conn, item_id, src)
                except actions.UnsupportedExt as e:
                    failed.append({"file": os.path.basename(src), "reason": str(e)})
                    continue
                (skipped if got["skipped"] else added).append(got)
            conn.commit()
        finally:
            for d in tmpdirs:
                shutil.rmtree(d, ignore_errors=True)
            conn.close()

        # 一张都没成，且全是格式问题：直接报 415，不用让前端去翻 failed 数组
        if not added and not skipped and failed:
            raise ApiError(415, "unsupported_ext", failed[0]["reason"])

        return self.send_json(
            {
                "ok": True,
                "item_id": item_id,
                "added": len(added),
                "skipped": len(skipped),
                "failed": failed,
                "assets": added,
            }
        )

    def handle_tags(self, item_id):
        payload = self.read_json()
        op = (payload.get("op") or "add").strip()
        ns = (payload.get("ns") or "").strip()
        name = (payload.get("name") or "").strip()
        if op not in ("add", "del") or not ns or not name:
            raise ApiError(400, "bad_tag", "需要 op(add|del) + ns + name")

        conn = self.db()
        try:
            if not store.item_exists(conn, item_id):
                raise ApiError(404, "not_found", item_id)
            if store.is_hidden_request(ns, name):
                store.set_hidden(conn, item_id, op == "add")
            elif op == "add":
                store.add_tag(conn, item_id, ns, name, "manual")
            else:
                store.del_tag(conn, item_id, ns, name)
            conn.commit()
            tags = store.item_tags(conn, item_id)
        except store.BuiltinTagError as e:
            raise ApiError(409, "builtin_tag", str(e))
        finally:
            conn.close()
        return self.send_json({"ok": True, "tags": tags})

    def handle_fav(self, item_id):
        payload = self.read_json()
        on = bool(payload.get("on"))
        conn = self.db()
        try:
            if not store.item_exists(conn, item_id):
                raise ApiError(404, "not_found", item_id)
            store.set_fav(conn, item_id, on)
            conn.commit()
        finally:
            conn.close()
        return self.send_json({"ok": True, "fav": on})

    def handle_send(self):
        payload = self.read_json()
        item_id = (payload.get("item_id") or "").strip()
        target = (payload.get("target") or "").strip()
        if not item_id:
            raise ApiError(400, "bad_request", "item_id 不能为空")
        targets = (self.config.get("targets") or {})
        if target not in targets:
            raise ApiError(404, "unknown_target", target or "(空)")

        conn = self.db()
        try:
            rel = store.primary_asset_path(conn, item_id)
        finally:
            conn.close()
        if not rel:
            raise ApiError(404, "not_found", item_id)

        src = os.path.join(self.root, rel)
        if not os.path.isfile(src):
            raise ApiError(404, "source_missing", rel)
        dst, method = actions.send(src, targets[target])
        return self.send_json({"ok": True, "path": dst, "method": method})

    # ── 静态与图片 ───────────────────────────────────────────────
    def serve_web(self, rel):
        base = os.path.realpath(WEB_DIR)
        full = os.path.realpath(os.path.join(base, rel))
        if not full.startswith(base + os.sep) and full != base:
            return self.send_error_json(404, "not_found", rel)
        if not os.path.isfile(full):
            return self.send_error_json(404, "not_found", rel)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            blob = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(blob)

    def upstream_url(self, rel):
        """某个站内路径登记的上游地址；没有则空串。"""
        conn = self.db()
        try:
            return store.derivative_url(conn, rel)
        finally:
            conn.close()

    def serve_media(self, rel):
        # 已经是外链（full=online 入库的就是 CDN 地址）：直接 302，不当本地路径处理
        if rel.startswith("http://") or rel.startswith("https://"):
            self.send_response(302)
            self.send_header("Location", rel)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return
        base = os.path.realpath(self.root)
        full = os.path.realpath(os.path.join(base, rel))
        if not (full == base or full.startswith(base + os.sep)):
            raise ApiError(404, "not_found", rel)
        if not os.path.isfile(full):
            # 本地没有这个文件：站图可能只留在上游（本地省掉了原图档），
            # 有登记的上游地址就重定向过去，没有才是真的 404。
            url = self.upstream_url(rel)
            if url:
                self.send_response(302)
                self.send_header("Location", url)
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                return
            raise ApiError(404, "not_found", rel)
        stat = os.stat(full)
        etag = f'"{stat.st_mtime_ns}-{stat.st_size}"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return
        ctype = store.mime_of(full)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(stat.st_size))
        self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        with open(full, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def log_message(self, fmt, *args):  # 静音：单机工具，终端不用刷每张图
        pass


def _with_views(conn, cols):
    """给集合挂上「视图」定义与各视图的条目数。

    视图的配置源是 catalog.SOURCES（唯一一处）；这里是把它翻译成前端要的形状。
    facet 为空的视图 = 整个集合；facet 非空 = 该命名空间下的去重条目数
    （与前端实际请求的存在性过滤同口径）。
    """
    for c in cols:
        cfg = catalog.SOURCES.get(c["slug"])
        views = (cfg or {}).get("views")
        if not views:
            continue
        c["views"] = [
            {**v, "count": c["items"] if not v.get("facet")
             else store.count_ns(conn, c["slug"], v["facet"])}
            for v in views
        ]
    return cols


def parse_facets(raw):
    """`facet=视角:正面` → [("视角", "正面")]。格式不对就 400，不静默忽略。

    值为空（`facet=风格参考:`）是**存在性过滤**：该命名空间下有任意标签即命中。
    集合内的「视图」用它（如「视频」= 「类型」命名空间下有任意标签的条目）。
    """
    out = []
    for one in raw:
        if ":" not in one:
            raise ApiError(400, "bad_facet", f"期望 命名空间:值，收到 {one!r}")
        ns, name = one.split(":", 1)
        if not ns:
            raise ApiError(400, "bad_facet", f"期望 命名空间:值，收到 {one!r}")
        if not name:
            out.append((ns, ""))
            continue
        out.append((ns, name))
    return out


def parse_multipart(ctype, body):
    """极简 multipart 解析（Python 3.13 起没有 cgi 模块了）。

    只需要拿到「字段名 → (文件名, 字节)」，不追求完整 RFC 实现。
    同名字段出现多次时取最后一个；要全部拿到用 `parse_multipart_parts`。
    """
    out = {}
    for field, fname, data in parse_multipart_parts(ctype, body):
        out[field] = (fname, data)
    return out


def parse_multipart_parts(ctype, body):
    """按出现顺序返回 [(字段名, 文件名, 字节)]，同名字段不合并。

    「一次传多张图」靠的就是这个：浏览器给每个文件发一个同名的 `file` 字段，
    用 dict 收会把前 N-1 张直接吞掉。
    """
    m = re.search(r"boundary=([^\s;]+)", ctype)
    if not m:
        raise ApiError(400, "bad_request", "缺少 boundary")
    boundary = m.group(1).strip('"')
    delim = b"--" + boundary.encode("utf-8")
    out = []
    for chunk in body.split(delim):
        if not chunk.strip(b"\r\n-"):
            continue
        head, sep, data = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = head.decode("utf-8", "replace")
        name = re.search(r'name="([^"]*)"', headers)
        if not name:
            continue
        fname = re.search(r'filename="([^"]*)"', headers)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        out.append((name.group(1), fname.group(1) if fname else None, data))
    return out


def load_config(root):
    """可选配置：端口与送素材的目标目录。没有配置文件时给一个可用的默认值。"""
    cfg = {"port": DEFAULT_PORT, "targets": {}}
    path = os.path.join(root, "config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cfg.update(json.load(f))
    if not cfg.get("targets"):
        cfg["targets"] = {"input": os.path.join(root, "library", "_inbox")}
    return cfg


def make_server(root, db_path, port=DEFAULT_PORT):
    Handler.root = os.path.abspath(root)
    Handler.db_path = os.path.abspath(db_path)
    Handler.config = load_config(Handler.root)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    return httpd


def sync_if_stale(root, db_path, force=False):
    """manifest / 字段映射变了就重建索引；没变就什么都不做。

    返回 True 表示这次真的重建了。

    为什么要有这个函数：以前 serve 只在「库文件不存在」时同步一次。
    于是加站（往 catalog.SOURCES 和 sites.json 里各加一行）之后，
    站点页面一切正常，但 WebUI 里那条集合永远是空的——
    静默失效，没有任何报错。拆 mj-styles 那次就栽在这里，
    交付时只验了临时库，真实库没同步。

    判定用 sync.signature()：各站 manifest 的 mtime+size + 字段映射表的摘要，
    算一次约 1 ms，放在请求路径上也不算负担。
    """
    if not os.path.exists(db_path):
        import sync as sync_mod

        sync_mod.sync(root, db_path)
        return True
    try:
        import sync as sync_mod
        import store as store_mod

        conn = store_mod.connect(db_path)
        try:
            same = (
                not force
                and store_mod.kv_get(conn, "manifest_signature") == sync_mod.signature(root)
                and store_mod.kv_get(conn, "schema_version") == str(store_mod.SCHEMA_VERSION)
            )
        finally:
            conn.close()
        if same:
            return False
        sync_mod.sync(root, db_path, force=force)
        return True
    except Exception as e:  # noqa: BLE001 - 同步失败不能拖垮整个服务
        print(f"[同步] 失败：{e}")
        return False


def maybe_sync():
    """在请求进来时按需重同步。用锁避免并发请求同时触发重建。"""
    if not Handler.auto_sync:
        return
    if not Handler.sync_lock.acquire(blocking=False):
        return  # 另一个请求正在同步，等它
    try:
        sync_if_stale(Handler.root, Handler.db_path)
    finally:
        Handler.sync_lock.release()


def free_port(start=DEFAULT_PORT):
    for port in range(start, start + 40):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--db", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--no-reload", action="store_true", help="即使 manifest 变了也不同步")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    root = os.path.abspath(args.root)
    db = args.db or os.path.join(root, "gallery.db")
    # 启动时先同步一次：库不存在就建；库存在但 manifest/字段映射变过就重建。
    # 以前只在「库不存在」时同步，于是加站后 WebUI 里那条集合永远是空的。
    Handler.auto_sync = not args.no_reload
    sync_if_stale(root, db)

    port = args.port or free_port(DEFAULT_PORT)
    httpd = make_server(root, db, port)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"素材管理器  {url}")
    print("Ctrl+C 停止")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
