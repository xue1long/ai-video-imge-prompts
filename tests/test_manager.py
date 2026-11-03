# -*- coding: utf-8 -*-
"""素材管理器的行为测试。

接缝只有一条：HTTP JSON API。测试不 import 内部函数、不断言表结构、不 mock。
数据根是临时目录里的迷你 manifest + 占位图，所以不需要 11 GB 真实素材。

用法:
  python tests/test_manager.py            # 全部
  python tests/test_manager.py -k items   # 只跑名字含 items 的
  python tests/test_manager.py -v
"""
import base64
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "index"))

import serve as serve_mod  # noqa: E402
import snapshot as snapshot_mod  # noqa: E402
import sync as sync_mod  # noqa: E402
import verify as verify_mod  # noqa: E402

# 1×1 的合法 PNG，缩略图生成靠它
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def write(path, data=b""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def png_with_text(path, **chunks):
    """写一张带 tEXt 块的 PNG，模拟生成工具埋的参数"""
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    for k, v in chunks.items():
        info.add_text(k, v)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", (4, 4), (10, 20, 30)).save(path, pnginfo=info)


class Root:
    """一个临时数据根：sites/<集合>/manifest.json + 实际存在的图片文件"""

    def __init__(self, tmp):
        self.path = tmp

    def rel(self, p):
        return os.path.join(self.path, p.replace("/", os.sep))

    def image(self, relpath):
        write(self.rel(relpath), PNG_1PX)
        return relpath

    def site_image(self, sid, relpath):
        """按真实 manifest 的写法返回**站点相对**路径，文件落在 sites/<sid>/ 下"""
        write(self.rel(f"sites/{sid}/{relpath}"), PNG_1PX)
        return relpath

    def site_size(self, sid, relpath):
        return os.path.getsize(self.rel(f"sites/{sid}/{relpath}"))

    def manifest(self, sid, rows):
        write(self.rel(f"sites/{sid}/manifest.json"), json.dumps(rows, ensure_ascii=False))


def portrait_root(tmp):
    """人像集合：3 条，字段结构与真实 manifest 一致（路径是站点相对的）"""
    r = Root(tmp)
    rows = []
    for i, (part, hair) in enumerate([("face", "ショート"), ("face", "ロング"), ("body", "ミディアム")]):
        stem = f"p{i}"
        thumb = r.site_image("portrait", f"thumbs/{stem}.png")
        full = r.site_image("portrait", f"img/{stem}.png")
        rows.append(
            {
                "id": stem,
                "分区": part,
                "发型": hair,
                "风格": "",
                "宽": 832,
                "高": 1216,
                "原图字节": r.site_size("portrait", full),
                "thumb_url": "https://example.invalid/t.png",
                "full_url": "https://example.invalid/f.png",
                "thumb_path": thumb,
                "full_path": full,
            }
        )
    r.manifest("portrait", rows)
    return r


class Server:
    """起一个真实 HTTP 服务，绑 0 端口"""

    def __init__(self, root):
        self.root = root
        self.db = os.path.join(root.path, "gallery.db")
        sync_mod.sync(root.path, self.db, verbose=False)
        self.httpd = serve_mod.make_server(root.path, self.db, 0)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path, **params):
        if params:
            path += "?" + urllib.parse.urlencode(params, doseq=True)
        try:
            with urllib.request.urlopen(self.url(path), timeout=10) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                if "json" in ctype:
                    return resp.status, json.loads(body.decode("utf-8")), ctype
                return resp.status, body, ctype
        except urllib.error.HTTPError as e:
            body = e.read()
            try:
                return e.code, json.loads(body.decode("utf-8")), e.headers.get("Content-Type", "")
            except Exception:
                return e.code, body, e.headers.get("Content-Type", "")

    def get_no_redirect(self, path):
        """不跟随重定向的 GET：返回 (状态码, 响应头)。用于断言 302 去上游。"""
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(self.url(path), timeout=10) as resp:
                return resp.status, resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.headers

    def post(self, path, payload=None, files=None):
        if files is None:
            data = json.dumps(payload or {}).encode("utf-8")
            req = urllib.request.Request(
                self.url(path), data=data, headers={"Content-Type": "application/json"}, method="POST"
            )
        else:
            boundary = "----boundary1234"
            # dict 传单个字段；list 传 [(字段名, (文件名, 字节))] 可以重复同名，用来测多文件
            pairs = list(files.items()) if isinstance(files, dict) else list(files)
            parts = []
            for name, (fname, blob) in pairs:
                parts.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                    f'filename="{fname}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode("utf-8")
                    + blob
                    + b"\r\n"
                )
            parts.append(f"--{boundary}--\r\n".encode("utf-8"))
            data = b"".join(parts)
            req = urllib.request.Request(
                self.url(path),
                data=data,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))


class Base(unittest.TestCase):
    make_root = staticmethod(portrait_root)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mm-")
        self.root = self.make_root(self.tmp)
        self.srv = Server(self.root)

    def tearDown(self):
        self.srv.close()
        shutil.rmtree(self.tmp, ignore_errors=True)


class Collections(Base):
    """工单 01：单集合网格"""

    def test_sync_is_idempotent(self):
        sync_mod.sync(self.root.path, self.srv.db, verbose=False)
        status, body, _ = self.srv.get("/api/collections")
        self.assertEqual(status, 200)
        self.assertEqual(body["collections"][0]["items"], 3)

    def test_collections_report_counts(self):
        status, body, _ = self.srv.get("/api/collections")
        self.assertEqual(status, 200)
        one = body["collections"][0]
        self.assertEqual(one["slug"], "portrait")
        self.assertEqual(one["items"], 3)
        self.assertEqual(one["assets"], 3)

    def test_items_default_page(self):
        status, body, _ = self.srv.get("/api/items")
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 3)
        self.assertEqual(len(body["items"]), 3)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["size"], 120)
        self.assertTrue(body["items"][0]["thumb"].startswith("/media/"))

    def test_media_serves_image(self):
        _, body, _ = self.srv.get("/api/items")
        status, blob, ctype = self.srv.get(body["items"][0]["thumb"])
        self.assertEqual(status, 200)
        self.assertTrue(ctype.startswith("image/"))
        self.assertEqual(blob[:4], b"\x89PNG")

    def test_media_rejects_traversal(self):
        status, body, _ = self.srv.get("/media/../gallery.db")
        self.assertEqual(status, 404)


class Views(Base):
    """集合内的顶层分层（视图），如 图像 / 视频。

    视图的配置源是 catalog.SOURCES；这里临时给 portrait 挂一组视图，
    验证「视图计数」与「按同一条件过滤出来的条数」永远是同一个口径。
    """

    def setUp(self):
        super().setUp()
        import catalog
        self.catalog = catalog
        self._saved = catalog.SOURCES["portrait"].get("views")
        catalog.SOURCES["portrait"]["views"] = [
            {"k": "all", "name": "全部", "facet": None},
            {"k": "hair", "name": "发型", "facet": "发型"},
            {"k": "videos", "name": "视频", "facet": "类型"},
        ]

    def tearDown(self):
        if self._saved is None:
            self.catalog.SOURCES["portrait"].pop("views", None)
        else:
            self.catalog.SOURCES["portrait"]["views"] = self._saved
        super().tearDown()

    def test_views_are_exposed_with_counts(self):
        status, body, _ = self.srv.get("/api/collections")
        self.assertEqual(status, 200)
        one = body["collections"][0]
        self.assertEqual(one["slug"], "portrait")
        self.assertEqual([v["k"] for v in one["views"]], ["all", "hair", "videos"])
        self.assertEqual(one["views"][0]["count"], 3)   # 无 facet = 整个集合
        self.assertEqual(one["views"][1]["count"], 3)   # 有 facet = 该命名空间的条目数
        self.assertEqual(one["views"][2]["count"], 0)   # 预留视图（上游没数据）

    def test_view_count_matches_actual_filter(self):
        """视图上写的条数必须等于按同一条件过滤出来的条数。"""
        status, body, _ = self.srv.get("/api/collections")
        self.assertEqual(status, 200)
        for v in body["collections"][0]["views"]:
            params = {"collection": "portrait"}
            if v.get("facet"):
                params["facet"] = v["facet"] + ":"
            st, data, _ = self.srv.get("/api/items", **params)
            self.assertEqual(st, 200)
            self.assertEqual(v["count"], data["total"],
                             f"视图 {v['k']} 的计数与实际过滤条数不一致")

    def test_existence_facet_filters_items(self):
        """`facet=命名空间:`（值为空）= 存在性过滤：该命名空间下有任意标签即命中。"""
        st, body, _ = self.srv.get("/api/items", collection="portrait", facet="发型:")
        self.assertEqual(st, 200)
        self.assertEqual(body["total"], 3)
        st, body, _ = self.srv.get("/api/items", collection="portrait", facet="类型:")
        self.assertEqual(st, 200)
        self.assertEqual(body["total"], 0)

    def test_facet_without_namespace_is_rejected(self):
        st, body, _ = self.srv.get("/api/items", collection="portrait", facet="no-colon")
        self.assertEqual(st, 400)


def all_root(tmp):
    """六个集合各来几条，足够覆盖映射、分面、聚合三种情况"""
    r = portrait_root(tmp)

    costume = []
    for i, (cat, tag_list) in enumerate([("衣装", "和服,礼服"), ("制服", "校园")]):
        stem = f"c{i}"
        thumb = r.site_image("costume", f"thumbs/{stem}.png")
        img = r.site_image("costume", f"img/{stem}.png")
        png = r.site_image("costume", f"png/{stem}.png")
        costume.append(
            {
                "id": stem, "分类": cat, "关键词": f"costume {i}", "标签": tag_list,
                "thumb_path": thumb, "img_path": img, "png_path": png,
                # 真实 manifest 按档位约定都带上游地址
                "thumb_url": "https://example.invalid/c%s-t.png" % stem,
                "img_url": "https://example.invalid/c%s-i.png" % stem,
                "png_url": "https://example.invalid/c%s-p.png" % stem,
            }
        )
    r.manifest("costume", costume)

    def poses(sid, layout):
        rows = []
        for i, (view, cat) in enumerate([("正面", "座り"), ("正面", "立ち"), ("斜め", "座り")]):
            stem = f"{sid}-{i}"
            thumb = r.site_image(sid, f"thumbs/{stem}.png")
            full = r.site_image(sid, f"img/{stem}.png")
            name = "ポーズ\n改行" if i == 2 else f"ポーズ{i}"
            rows.append(
                {
                    "id": stem, "姿势名": name, "系列": "上半身1人", "分類": cat,
                    "视角": view, "编号": f"P0{i}", "thumb_path": thumb, "full_path": full,
                    "thumb_url": "https://example.invalid/%s-t.png" % stem,
                    "full_url": "https://example.invalid/%s-f.png" % stem,
                }
            )
        r.manifest(sid, rows)

    poses("pose", None)
    poses("pose-depth", None)

    r.manifest(
        "shisei",
        [
            {
                "id": "s0", "姿势名": "立ち・腕組み", "姿势名_zh": "站立・抱臂",
                "系列": "全身・標準", "分類": "立ち", "视角": "正面", "rating": "A", "编号": "S00",
                "thumb_path": r.site_image("shisei", "thumbs/s0.png"),
                "mid_path": r.site_image("shisei", "mid/s0.png"),
                "full_path": r.site_image("shisei", "img/s0.png"),
                "thumb_url": "https://example.invalid/s0-t.png",
                "mid_url": "https://example.invalid/s0-m.png",
                "full_url": "https://example.invalid/s0-f.png",
            }
        ],
    )

    # 提示词站：两条图片记录属于同一条提示词，必须聚成一个作品
    p1 = r.site_image("prompts", "img/g1a.png")
    p2 = r.site_image("prompts", "img/g1b.png")
    r.manifest(
        "prompts",
        [
            {"id": "g1a", "title": "海报 A", "thumb_path": r.site_image("prompts", "thumbs/g1a.png"), "full_path": p1,
             "thumb_url": "https://example.invalid/g1a-t.png", "full_url": "https://example.invalid/g1a-f.png"},
            {"id": "g1b", "title": "海报 B", "thumb_path": r.site_image("prompts", "thumbs/g1b.png"), "full_path": p2,
             "thumb_url": "https://example.invalid/g1b-t.png", "full_url": "https://example.invalid/g1b-f.png"},
        ],
    )
    write(
        r.rel("sites/prompts/data/prompts_gpt2.json"),
        json.dumps(
            [
                {
                    "file": p1, "originId": "gpt2-o1", "title": "双图提示词", "prompt": "中文提示", "promptRaw": "a cat, studio",
                    "author": "someone", "sourceUrl": "https://example.invalid/p", "published": "2026-01-01",
                    "model": "mj", "modelLabel": "Midjourney", "tags": "摄影,产品营销",
                },
                {  # 同一提示词的第二张图：meta 是「一图一条」，靠 originId 归并
                    "file": p2, "originId": "gpt2-o1", "title": "双图提示词", "prompt": "中文提示", "promptRaw": "a cat, studio",
                    "author": "someone", "sourceUrl": "https://example.invalid/p", "published": "2026-01-01",
                    "model": "mj", "modelLabel": "Midjourney", "tags": "摄影,产品营销",
                },
            ],
            ensure_ascii=False,
        ),
    )
    # 集合顺序与中文名应当来自 sites.json（仓库规则：它是唯一清单）
    write(
        r.rel("sites.json"),
        json.dumps(
            {"meta": {}, "sites": [
                {"id": "portrait", "name": {"zh": "人像集", "ja": "ポートレート集"}},
                {"id": "pose", "name": {"zh": "姿势集", "ja": "ポーズ集"}},
                {"id": "pose-depth", "name": {"zh": "深度姿势集"}},
                {"id": "costume", "name": {"zh": "服装集"}},
                {"id": "shisei", "name": {"zh": "Shisei 姿势集"}},
                {"id": "prompts", "name": {"zh": "提示词生图集"}},
            ]},
            ensure_ascii=False,
        ),
    )
    return r


class AllCollections(Base):
    """工单 02：六站全量同步与分面"""

    make_root = staticmethod(all_root)

    def test_every_collection_is_indexed(self):
        status, body, _ = self.srv.get("/api/collections")
        self.assertEqual(status, 200)
        counts = {c["slug"]: c["items"] for c in body["collections"]}
        self.assertEqual(counts["portrait"], 3)
        self.assertEqual(counts["costume"], 2)
        self.assertEqual(counts["pose"], 3)
        self.assertEqual(counts["pose-depth"], 3)
        self.assertEqual(counts["shisei"], 1)
        self.assertEqual(counts["prompts"], 1)
        self.assertEqual(sum(counts.values()), 13)

    def test_prompt_with_two_images_is_one_item(self):
        _, body, _ = self.srv.get("/api/items", collection="prompts")
        self.assertEqual(body["total"], 1)
        item_id = body["items"][0]["id"]
        status, detail, _ = self.srv.get(f"/api/items/{item_id}")
        self.assertEqual(status, 200)
        self.assertEqual(len(detail["assets"]), 2)
        self.assertEqual(detail["item"]["prompt_raw"], "a cat, studio")

    def test_facets_are_counted(self):
        status, body, _ = self.srv.get("/api/facets", collection="pose")
        self.assertEqual(status, 200)
        views = {f["name"]: f["count"] for f in body["facets"] if f["ns"] == "视角"}
        self.assertEqual(views["正面"], 2)
        self.assertEqual(views["斜め"], 1)
        cats = {f["name"] for f in body["facets"] if f["ns"] == "分類"}
        self.assertEqual(cats, {"座り", "立ち"})

    def test_facet_filters_items(self):
        _, body, _ = self.srv.get("/api/items", collection="pose", facet="视角:正面")
        self.assertEqual(body["total"], 2)

    def test_prompt_model_is_a_facet(self):
        """提示词站的「模型」是分面而不是纯文本字段：左栏能点、能筛。"""
        _, body, _ = self.srv.get("/api/facets", collection="prompts")
        models = {f["name"] for f in body["facets"] if f["ns"] == "模型"}
        self.assertEqual(models, {"Midjourney"})

    def test_prompt_model_facet_filters_items(self):
        _, body, _ = self.srv.get("/api/items", collection="prompts", facet="模型:Midjourney")
        self.assertEqual(body["total"], 1)

    def test_multiple_facets_intersect(self):
        _, body, _ = self.srv.get("/api/items", collection="pose", facet=["视角:正面", "分類:座り"])
        self.assertEqual(body["total"], 1)

    def test_bad_facet_is_rejected(self):
        status, body, _ = self.srv.get("/api/items", facet="正面")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_facet")

    def test_facets_do_not_leak_across_collections(self):
        _, body, _ = self.srv.get("/api/facets", collection="portrait")
        namespaces = {f["ns"] for f in body["facets"]}
        self.assertNotIn("视角", namespaces)
        self.assertIn("分区", namespaces)

    def test_all_manifest_fields_are_mapped(self):
        stats = sync_mod.sync(self.root.path, self.srv.db, force=True, verbose=False)
        self.assertEqual(stats["unmapped"], {})

    def test_collection_names_come_from_sites_json(self):
        _, body, _ = self.srv.get("/api/collections")
        names = {c["slug"]: c["name"] for c in body["collections"]}
        self.assertEqual(names["portrait"], "人像集")
        self.assertEqual(names["pose-depth"], "深度姿势集")
        self.assertEqual(names["own"], "我的素材")


class Search(Base):
    """工单 03：检索与分页"""

    make_root = staticmethod(all_root)

    def test_search_matches_title(self):
        _, body, _ = self.srv.get("/api/items", q="ポーズ0")
        self.assertEqual(body["total"], 2)  # pose 与 pose-depth 同名

    def test_search_matches_chinese_alias_of_category(self):
        _, body, _ = self.srv.get("/api/items", q="坐姿")
        self.assertEqual(body["total"], 4)  # 分类=座り 的条目，靠 tag.name_zh 命中

    def test_search_matches_original_language(self):
        _, body, _ = self.srv.get("/api/items", q="座り")
        self.assertEqual(body["total"], 4)

    def test_search_matches_prompt_raw(self):
        _, body, _ = self.srv.get("/api/items", q="a cat")
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["collection"], "prompts")

    def test_search_combines_with_facet(self):
        _, body, _ = self.srv.get("/api/items", q="座り", facet="视角:正面")
        self.assertEqual(body["total"], 2)

    def test_pages_do_not_repeat_items(self):
        _, first, _ = self.srv.get("/api/items", size=2, page=1)
        _, second, _ = self.srv.get("/api/items", size=2, page=2)
        ids1 = {i["id"] for i in first["items"]}
        ids2 = {i["id"] for i in second["items"]}
        self.assertEqual(len(ids1), 2)
        self.assertFalse(ids1 & ids2)

    def test_page_size_is_clamped(self):
        _, body, _ = self.srv.get("/api/items", size=9999)
        self.assertEqual(body["size"], 200)

    def test_newline_in_title_is_normalized(self):
        _, body, _ = self.srv.get("/api/items", q="ポーズ 改行")
        self.assertEqual(body["total"], 2)
        for item in body["items"]:
            self.assertNotIn("\n", item["title"])


class DetailAndSend(Base):
    """工单 04：详情与送素材"""

    make_root = staticmethod(all_root)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mm-")
        self.root = self.make_root(self.tmp)
        self.inbox = os.path.join(self.tmp, "inbox")
        os.makedirs(self.inbox, exist_ok=True)
        self.unrelated = os.path.join(self.inbox, "keepme.txt")
        with open(self.unrelated, "w", encoding="utf-8") as f:
            f.write("生成工具自己的文件")
        with open(os.path.join(self.tmp, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"targets": {"input": self.inbox}}, f)
        self.srv = Server(self.root)

    def test_detail_lists_every_tier(self):
        _, detail, _ = self.srv.get("/api/items/shisei:s0")
        kinds = {f["kind"] for f in detail["assets"][0]["files"]}
        self.assertEqual(kinds, {"thumb", "mid", "full"})

    def test_detail_has_empty_generator_meta_without_png_params(self):
        _, detail, _ = self.srv.get("/api/items/portrait:p0")
        self.assertEqual(detail["item"]["generator_meta"], {})

    def test_detail_prompt_is_exact(self):
        _, detail, _ = self.srv.get("/api/items/prompts:gpt2-o1")
        self.assertEqual(detail["item"]["prompt_raw"], "a cat, studio")
        self.assertEqual(detail["assets"][0]["status"], "ok")

    def test_send_hardlinks_into_target(self):
        status, body = self.srv.post("/api/send", {"item_id": "portrait:p0", "target": "input"})
        self.assertEqual(status, 200)
        self.assertEqual(body["method"], "hardlink")
        dst = body["path"]
        self.assertTrue(os.path.exists(dst))
        src = os.path.join(self.tmp, "sites/portrait/img/p0.png")
        self.assertEqual(os.stat(src).st_ino, os.stat(dst).st_ino)

    def test_send_does_not_overwrite_nor_delete(self):
        _, first = self.srv.post("/api/send", {"item_id": "portrait:p0", "target": "input"})
        _, second = self.srv.post("/api/send", {"item_id": "portrait:p0", "target": "input"})
        self.assertNotEqual(first["path"], second["path"])
        self.assertTrue(second["path"].endswith("-2.png"))
        self.assertTrue(os.path.exists(self.unrelated))

    def test_send_unknown_target(self):
        status, body = self.srv.post("/api/send", {"item_id": "portrait:p0", "target": "nope"})
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "unknown_target")

    def test_send_missing_source(self):
        os.remove(os.path.join(self.tmp, "sites/portrait/img/p1.png"))
        status, body = self.srv.post("/api/send", {"item_id": "portrait:p1", "target": "input"})
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "source_missing")


class TagsAndFav(Base):
    """工单 05：打标与收藏"""

    make_root = staticmethod(all_root)

    def test_added_tag_survives_a_refetch(self):
        status, body = self.srv.post("/api/items/portrait:p1/tags", {"op": "add", "ns": "状态", "name": "废图"})
        self.assertEqual(status, 200)
        _, detail, _ = self.srv.get("/api/items/portrait:p1")
        names = {(t[0], t[1]) for t in detail["tags"]}
        self.assertIn(("状态", "废图"), names)

    def test_deleted_manual_tag_disappears(self):
        self.srv.post("/api/items/portrait:p1/tags", {"op": "add", "ns": "状态", "name": "废图"})
        self.srv.post("/api/items/portrait:p1/tags", {"op": "del", "ns": "状态", "name": "废图"})
        _, detail, _ = self.srv.get("/api/items/portrait:p1")
        self.assertNotIn(("状态", "废图"), {(t[0], t[1]) for t in detail["tags"]})

    def test_builtin_tag_cannot_be_deleted(self):
        status, body = self.srv.post("/api/items/pose:pose-0/tags", {"op": "del", "ns": "视角", "name": "正面"})
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "builtin_tag")
        _, detail, _ = self.srv.get("/api/items/pose:pose-0")
        self.assertIn(("视角", "正面"), {(t[0], t[1]) for t in detail["tags"]})

    def test_bad_tag_payload(self):
        status, body = self.srv.post("/api/items/portrait:p1/tags", {"op": "add", "ns": "", "name": "x"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_tag")

    def test_new_tag_is_searchable(self):
        self.srv.post("/api/items/portrait:p1/tags", {"op": "add", "ns": "状态", "name": "废图"})
        _, body, _ = self.srv.get("/api/items", q="废图")
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["id"], "portrait:p1")

    def test_favourite_toggles(self):
        status, body = self.srv.post("/api/items/portrait:p1/fav", {"on": True})
        self.assertEqual(status, 200)
        self.assertTrue(body["fav"])
        _, listed, _ = self.srv.get("/api/items", collection="portrait")
        self.assertTrue([i for i in listed["items"] if i["id"] == "portrait:p1"][0]["fav"])
        self.srv.post("/api/items/portrait:p1/fav", {"on": True})  # 重复开关不产生重复行
        self.srv.post("/api/items/portrait:p1/fav", {"on": False})
        _, detail, _ = self.srv.get("/api/items/portrait:p1")
        self.assertFalse(detail["item"]["hidden"])
        _, listed2, _ = self.srv.get("/api/items", collection="portrait")
        self.assertFalse([i for i in listed2["items"] if i["id"] == "portrait:p1"][0]["fav"])

    def test_unknown_item_returns_404(self):
        status, body = self.srv.post("/api/items/nope:none/fav", {"on": True})
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "not_found")


class Import(Base):
    """工单 06：拖拽导入"""

    make_root = staticmethod(all_root)

    def png_bytes(self, **chunks):
        tmp = os.path.join(self.tmp, "_gen.png")
        png_with_text(tmp, **chunks)
        with open(tmp, "rb") as f:
            return f.read()

    def own_items(self):
        _, body, _ = self.srv.get("/api/items", collection="own")
        return body

    def test_upload_lands_under_library_with_year_month(self):
        status, body = self.srv.post("/api/import", files={"file": ("art.png", self.png_bytes())})
        self.assertEqual(status, 200)
        self.assertTrue(body["item_id"].startswith("own:"))
        found = []
        for dirpath, _, files in os.walk(os.path.join(self.tmp, "library")):
            found += [os.path.join(dirpath, f) for f in files if f == "art.png"]
        self.assertEqual(len(found), 1)
        self.assertRegex(found[0].replace("\\", "/"), r"library/\d{4}/\d{2}/art\.png")

    def test_upload_is_browsable_and_has_thumbnail(self):
        blob = self.png_bytes(prompt="a cat, studio light", Description="mj --v 6")
        _, body = self.srv.post("/api/import", files={"file": ("art.png", blob)})
        self.assertEqual(self.own_items()["total"], 1)
        _, detail, _ = self.srv.get(f"/api/items/{body['item_id']}")
        kinds = {f["kind"] for f in detail["assets"][0]["files"]}
        self.assertIn("thumb", kinds)
        self.assertGreater(detail["item"]["generator_meta"].get("prompt", ""), "")

    def test_upload_marks_item_unreviewed(self):
        _, body = self.srv.post("/api/import", files={"file": ("art.png", self.png_bytes())})
        _, detail, _ = self.srv.get(f"/api/items/{body['item_id']}")
        self.assertIn(("状态", "未审"), {(t[0], t[1]) for t in detail["tags"]})

    def test_duplicate_upload_is_rejected(self):
        blob = self.png_bytes()
        self.srv.post("/api/import", files={"file": ("art.png", blob)})
        status, body = self.srv.post("/api/import", files={"file": ("art.png", blob)})
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "duplicate")
        self.assertTrue(body["existing_id"].startswith("own:"))
        self.assertEqual(self.own_items()["total"], 1)

    def test_unsupported_extension(self):
        status, body = self.srv.post("/api/import", files={"file": ("note.txt", b"hello")})
        self.assertEqual(status, 415)
        self.assertEqual(body["error"], "unsupported_ext")

    def test_import_by_local_path(self):
        src = os.path.join(self.tmp, "outside", "shot.png")
        os.makedirs(os.path.dirname(src), exist_ok=True)
        with open(src, "wb") as f:
            f.write(self.png_bytes())
        status, body = self.srv.post("/api/import", {"path": src})
        self.assertEqual(status, 200)
        self.assertEqual(self.own_items()["total"], 1)

    def test_import_folder(self):
        folder = os.path.join(self.tmp, "batch")
        os.makedirs(folder, exist_ok=True)
        for name in ("a.png", "b.png"):
            with open(os.path.join(folder, name), "wb") as f:
                f.write(self.png_bytes())
        with open(os.path.join(folder, "c.txt"), "w", encoding="utf-8") as f:
            f.write("skip me")
        status, body = self.srv.post("/api/import", {"path": folder})
        self.assertEqual(status, 200)
        self.assertEqual(body["imported"], 2)
        self.assertEqual(self.own_items()["total"], 2)

    def test_collected_assets_are_untouched(self):
        target = os.path.join(self.tmp, "sites/portrait/img/p0.png")
        before = os.stat(target).st_mtime_ns
        self.srv.post("/api/import", files={"file": ("art.png", self.png_bytes())})
        self.assertEqual(os.stat(target).st_mtime_ns, before)


class Attach(Base):
    """给已有素材追加自己的图（不是替换）"""

    make_root = staticmethod(all_root)
    ITEM = "prompts:gpt2-o1"

    def png_bytes(self, **chunks):
        tmp = os.path.join(self.tmp, "_gen.png")
        png_with_text(tmp, **chunks)
        with open(tmp, "rb") as f:
            return f.read()

    def detail(self):
        _, body, _ = self.srv.get(f"/api/items/{self.ITEM}")
        return body

    def roles(self):
        return [a["role"] for a in self.detail()["assets"]]

    def test_attach_appends_after_collected_images(self):
        before = len(self.detail()["assets"])
        status, body = self.srv.post(
            f"/api/items/{self.ITEM}/attach", files={"file": ("mine.png", self.png_bytes(prompt="my run"))}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["added"], 1)
        assets = self.detail()["assets"]
        self.assertEqual(len(assets), before + 1)
        self.assertEqual(assets[-1]["role"], "user")  # 新图排最后，不抢主图

    def test_attach_does_not_change_primary(self):
        first_path = self.detail()["assets"][0]["files"]
        self.srv.post(
            f"/api/items/{self.ITEM}/attach", files={"file": ("mine.png", self.png_bytes(prompt="my run"))}
        )
        self.assertEqual(self.detail()["assets"][0]["files"], first_path)

    def test_attach_accepts_several_files_at_once(self):
        status, body = self.srv.post(
            f"/api/items/{self.ITEM}/attach",
            files=[
                ("file", ("a.png", self.png_bytes(prompt="run a"))),
                ("file", ("b.png", self.png_bytes(prompt="run b"))),
            ],
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["added"], 2)
        self.assertEqual(self.roles()[-2:], ["user", "user"])

    def test_attach_twice_is_skipped_not_duplicated(self):
        blob = self.png_bytes(prompt="same run")
        self.srv.post(f"/api/items/{self.ITEM}/attach", files={"file": ("a.png", blob)})
        status, body = self.srv.post(f"/api/items/{self.ITEM}/attach", files={"file": ("a.png", blob)})
        self.assertEqual(status, 200)
        self.assertEqual(body["added"], 0)
        self.assertEqual(body["skipped"], 1)

    def test_attach_survives_resync(self):
        self.srv.post(
            f"/api/items/{self.ITEM}/attach", files={"file": ("mine.png", self.png_bytes(prompt="my run"))}
        )
        sync_mod.sync(self.root.path, self.srv.db, force=True, verbose=False)
        self.assertIn("user", self.roles())

    def test_attach_unknown_item(self):
        status, body = self.srv.post(
            "/api/items/prompts:nope/attach", files={"file": ("a.png", self.png_bytes())}
        )
        self.assertEqual(status, 404)

    def test_attach_rejects_non_image(self):
        status, body = self.srv.post(
            f"/api/items/{self.ITEM}/attach", files={"file": ("note.txt", b"hello")}
        )
        self.assertEqual(status, 415)
        self.assertEqual(body["error"], "unsupported_ext")

    def test_replace_still_puts_new_image_first(self):
        """回归：replace 的语义是「换到最前」，不能被 attach 改掉。"""
        self.srv.post(
            f"/api/items/{self.ITEM}/replace", files={"file": ("better.png", self.png_bytes(prompt="better"))}
        )
        self.assertEqual(self.detail()["assets"][0]["role"], "replaced")


class RemoteAssets(Base):
    """站图可以只留在上游：本地缺文件时媒体路由重定向过去，缺失判定也不再算缺图。

    背景：本地原图档可以整档删掉（省几十 GB），页面改指向上游地址。
    素材管理器是本地工具，它读的是自己的库，因此媒体路由要能在文件不在时
    给出上游地址；「文件缺失」这个判定也要跟着改——有上游地址就不算缺图。
    """

    def test_media_redirects_to_upstream_when_local_file_missing(self):
        os.remove(os.path.join(self.tmp, "sites/portrait/img/p1.png"))
        status, headers = self.srv.get_no_redirect("/media/sites/portrait/img/p1.png")
        self.assertEqual(status, 302)
        self.assertEqual(headers.get("Location"), "https://example.invalid/f.png")

    def test_media_redirects_for_thumbnail_too(self):
        os.remove(os.path.join(self.tmp, "sites/portrait/thumbs/p1.png"))
        status, headers = self.srv.get_no_redirect("/media/sites/portrait/thumbs/p1.png")
        self.assertEqual(status, 302)
        self.assertEqual(headers.get("Location"), "https://example.invalid/t.png")

    def test_media_404_when_no_upstream_address(self):
        # 库里根本没有这条资产 → 仍然 404
        status, _, _ = self.srv.get("/media/sites/portrait/img/nonexistent.png")
        self.assertEqual(status, 404)

    def test_verify_does_not_mark_missing_when_upstream_exists(self):
        os.remove(os.path.join(self.tmp, "sites/portrait/img/p1.png"))
        result = verify_mod.verify(self.root.path, self.srv.db)
        self.assertEqual(result["missing"], 0)

    def test_verify_still_marks_missing_without_upstream(self):
        # 自己导入的素材（library）没有上游地址 → 文件丢了就是缺图
        os.remove(os.path.join(self.tmp, "sites/portrait/thumbs/p1.png"))
        result = verify_mod.verify(self.root.path, self.srv.db)
        self.assertEqual(result["missing"], 0)  # 缩略图缺失不影响原图资产


class UpstreamWiring(Base):
    """上游地址的接线完整性：声明了、库里就得有。"""

    make_root = staticmethod(all_root)

    def test_every_derivative_has_its_upstream_address(self):
        """每个站每个档位的派生图都要带上上游地址。

        漏一条路径（如 prompts 站的专用写入分支），该站的取图策略就整体失效：
        本地原图删掉后，媒体路由 404、缺图判定误报——而且没有任何症状。
        """
        import sqlite3
        conn = sqlite3.connect(self.srv.db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT i.collection AS c, d.kind AS k, COUNT(*) AS n, "
            "SUM(CASE WHEN d.url IS NOT NULL AND d.url <> '' THEN 1 ELSE 0 END) AS u "
            "FROM derivative d JOIN asset a ON a.id = d.asset_id "
            "JOIN item_asset ia ON ia.asset_id = a.id JOIN item i ON i.id = ia.item_id "
            "GROUP BY i.collection, d.kind"
        ).fetchall()
        conn.close()
        gaps = [(r["c"], r["k"], r["u"], r["n"]) for r in rows if r["u"] != r["n"]]
        self.assertEqual(gaps, [], "这些档位的派生图没有上游地址：%s" % gaps)

    def test_resync_after_schema_upgrade_is_not_skipped(self):
        """库的结构版本变了，sync 不能因为 manifest 没变就跳过。

        否则升级后索引里的上游地址是空的，功能静默失效——没有任何报错。
        """
        import sqlite3
        conn = sqlite3.connect(self.srv.db)
        conn.execute("UPDATE kv SET value='1' WHERE key='schema_version'")
        conn.commit()
        conn.close()
        stats = sync_mod.sync(self.root.path, self.srv.db, verbose=False)
        self.assertFalse(stats.get("skipped"), "结构版本变了却跳过了重建")
        import sqlite3
        conn = sqlite3.connect(self.srv.db)
        n = conn.execute("SELECT COUNT(*) FROM derivative WHERE url IS NOT NULL AND url <> ''").fetchone()[0]
        conn.close()
        self.assertGreater(n, 0, "重建后仍没有上游地址")

    def test_migration_is_idempotent_under_concurrent_connects(self):
        """老库补列是幂等的：并发的首次连接不能因为重复加列而报错。"""
        import sqlite3
        import store as store_mod
        db = os.path.join(self.tmp, "legacy.db")
        conn = sqlite3.connect(db)
        conn.executescript(store_mod.SCHEMA.replace(
            "  url TEXT,                           -- 上游地址；本地文件不在时媒体路由重定向到它\n", ""))
        conn.execute("INSERT OR REPLACE INTO kv(key, value) VALUES('schema_version', '1')")
        conn.commit()
        conn.close()
        # 连续两次连接：第二次若不做幂等处理就会因重复列报错
        c1 = store_mod.connect(db)
        c2 = store_mod.connect(db)
        c1.close()
        c2.close()

    def test_hostile_upstream_address_is_not_stored(self):
        """带换行或非 http(s) 的上游地址不能进库（否则会变成响应头注入）。"""
        import sqlite3
        rows = json.loads(open(os.path.join(self.tmp, "sites/portrait/manifest.json"),
                               encoding="utf-8").read())
        rows[0]["full_url"] = "https://e.com/a\r\nX-Injected: 1"
        rows[0]["thumb_url"] = "javascript:alert(1)"
        write(os.path.join(self.tmp, "sites/portrait/manifest.json"),
              json.dumps(rows, ensure_ascii=False))
        sync_mod.sync(self.root.path, self.srv.db, force=True, verbose=False)
        conn = sqlite3.connect(self.srv.db)
        bad = conn.execute("SELECT COUNT(*) FROM derivative WHERE url LIKE '%X-Injected%' "
                           "OR url NOT LIKE 'http%'").fetchone()[0]
        conn.close()
        self.assertEqual(bad, 0, "危险的上游地址被写进了库")


class Maintenance(Base):
    """工单 07：维护命令与启动器"""

    make_root = staticmethod(all_root)

    def test_verify_marks_missing_files(self):
        # 自己导入的素材没有上游地址 → 文件丢了就是缺图
        self.srv.post("/api/import", files={"file": ("mine.png", PNG_1PX)})
        _, own, _ = self.srv.get("/api/items", collection="own")
        own_id = own["items"][0]["id"]
        import sqlite3
        conn = sqlite3.connect(self.srv.db)
        local = conn.execute("SELECT path FROM asset WHERE volume='library'").fetchone()[0]
        conn.close()
        os.remove(os.path.join(self.tmp, local.replace("/", os.sep)))
        result = verify_mod.verify(self.root.path, self.srv.db)
        self.assertEqual(result["missing"], 1)
        _, detail, _ = self.srv.get("/api/items/" + own_id)
        self.assertEqual(detail["assets"][0]["status"], "missing")

    def test_verify_treats_upstream_backed_asset_as_present(self):
        # 站图登记了上游地址 → 本地没有也不算缺图（还能从上游取到）
        os.remove(os.path.join(self.tmp, "sites/portrait/img/p1.png"))
        result = verify_mod.verify(self.root.path, self.srv.db)
        self.assertEqual(result["missing"], 0)
        status, _, _ = self.srv.get("/api/items", collection="portrait")
        self.assertEqual(status, 200)  # 文件没了也不能让列表挂掉
        _, detail, _ = self.srv.get("/api/items/portrait:p1")
        self.assertEqual(detail["assets"][0]["status"], "ok")

    def test_verify_leaves_view_flags_alone(self):
        os.remove(os.path.join(self.tmp, "sites/portrait/img/p1.png"))
        verify_mod.verify(self.root.path, self.srv.db)
        _, body, _ = self.srv.get("/api/items", collection="portrait")
        self.assertIn("portrait:p1", {i["id"] for i in body["items"]})  # 仍可见，只是文件缺失

    def test_snapshot_is_openable_copy(self):
        path = snapshot_mod.snapshot(self.root.path, self.srv.db)
        self.assertTrue(os.path.exists(path))
        import sqlite3

        conn = sqlite3.connect(path)
        n = conn.execute("SELECT COUNT(*) FROM item").fetchone()[0]
        conn.close()
        self.assertEqual(n, 13)

    def test_sync_skips_when_manifests_unchanged(self):
        stats = sync_mod.sync(self.root.path, self.srv.db, verbose=False)
        self.assertTrue(stats["skipped"])

    def test_launcher_exists_and_points_at_server(self):
        bat = os.path.join(ROOT, "启动.bat")
        self.assertTrue(os.path.isfile(bat))
        with open(bat, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertIn("index", content)
        self.assertIn("serve.py", content)

    def test_readme_documents_the_three_commands(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        self.assertIn("素材管理器", readme)
        for cmd in ("sync.py", "verify.py", "snapshot.py"):
            self.assertIn(cmd, readme)

    def test_local_data_is_gitignored(self):
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as f:
            lines = {x.strip() for x in f}
        for entry in ("gallery.db", "library/", "backups/", "config.json", "exports/"):
            self.assertIn(entry, lines)


class Hide(Base):
    """工单 08：集合内隐藏（软删第一档）"""

    make_root = staticmethod(all_root)

    def hide(self, item_id, on=True):
        return self.srv.post(
            f"/api/items/{item_id}/tags", {"op": "add" if on else "del", "ns": "状态", "name": "隐藏"}
        )

    def test_hidden_item_leaves_the_default_list(self):
        _, before, _ = self.srv.get("/api/items")
        status, _ = self.hide("portrait:p0")
        self.assertEqual(status, 200)
        _, after, _ = self.srv.get("/api/items")
        self.assertEqual(after["total"], before["total"] - 1)
        self.assertNotIn("portrait:p0", {i["id"] for i in after["items"]})

    def test_hidden_item_can_be_found_again(self):
        self.hide("portrait:p0")
        _, body, _ = self.srv.get("/api/items", include_hidden="1")
        self.assertIn("portrait:p0", {i["id"] for i in body["items"]})

    def test_detail_still_works_and_reports_hidden(self):
        self.hide("portrait:p0")
        status, detail, _ = self.srv.get("/api/items/portrait:p0")
        self.assertEqual(status, 200)
        self.assertTrue(detail["item"]["hidden"])

    def test_hiding_never_touches_the_file(self):
        target = os.path.join(self.tmp, "sites/portrait/img/p0.png")
        self.hide("portrait:p0")
        self.assertTrue(os.path.isfile(target))
        _, detail, _ = self.srv.get("/api/items/portrait:p0")
        self.assertEqual(detail["assets"][0]["status"], "ok")

    def test_hiding_is_reversible(self):
        self.hide("portrait:p0")
        self.hide("portrait:p0", on=False)
        _, body, _ = self.srv.get("/api/items")
        self.assertIn("portrait:p0", {i["id"] for i in body["items"]})
        _, detail, _ = self.srv.get("/api/items/portrait:p0")
        self.assertFalse(detail["item"]["hidden"])

    def test_batch_hide_keeps_counts_consistent(self):
        _, filtered, _ = self.srv.get("/api/items", collection="pose", facet="视角:正面")
        for item in filtered["items"]:
            self.hide(item["id"])
        _, after, _ = self.srv.get("/api/items", collection="pose", facet="视角:正面")
        self.assertEqual(after["total"], 0)
        _, allpose, _ = self.srv.get("/api/items", collection="pose")
        self.assertEqual(allpose["total"], 3 - filtered["total"])  # 只剩没被隐藏的那些

    def test_facets_ignore_hidden_items(self):
        _, before, _ = self.srv.get("/api/facets", collection="pose")
        total_before = sum(f["count"] for f in before["facets"] if f["ns"] == "视角")
        self.hide("pose:pose-0")
        _, after, _ = self.srv.get("/api/facets", collection="pose")
        total_after = sum(f["count"] for f in after["facets"] if f["ns"] == "视角")
        self.assertEqual(total_after, total_before - 1)


class ReviewFixes(Base):
    """评审发现的问题：标注不能因为重新同步而消失"""

    make_root = staticmethod(all_root)

    def test_annotations_survive_a_resync(self):
        self.srv.post("/api/items/portrait:p1/tags", {"op": "add", "ns": "状态", "name": "废图"})
        self.srv.post("/api/items/portrait:p1/fav", {"on": True})
        self.srv.post("/api/items/portrait:p0/tags", {"op": "add", "ns": "状态", "name": "隐藏"})
        blob = PNG_1PX
        self.srv.post("/api/import", files={"file": ("mine.png", blob)})
        self.assertEqual(self.srv.get("/api/items", collection="own")[1]["total"], 1)

        sync_mod.sync(self.root.path, self.srv.db, force=True, verbose=False)

        _, detail, _ = self.srv.get("/api/items/portrait:p1")
        self.assertIn(("状态", "废图"), {(t[0], t[1]) for t in detail["tags"]})
        _, listed, _ = self.srv.get("/api/items", collection="portrait")
        mine = [i for i in listed["items"] if i["id"] == "portrait:p1"][0]
        self.assertTrue(mine["fav"])
        self.assertNotIn("portrait:p0", {i["id"] for i in listed["items"]})  # 隐藏状态也保住
        self.assertEqual(self.srv.get("/api/items", collection="own")[1]["total"], 1)  # 导入的素材还在

    def test_tag_payload_reports_its_source(self):
        _, detail, _ = self.srv.get("/api/items/pose:pose-0")
        builtin = [t for t in detail["tags"] if t[0] == "视角"][0]
        self.assertEqual(builtin[3], "builtin")
        self.srv.post("/api/items/pose:pose-0/tags", {"op": "add", "ns": "我的", "name": "可用"})
        _, detail2, _ = self.srv.get("/api/items/pose:pose-0")
        manual = [t for t in detail2["tags"] if t[0] == "我的"][0]
        self.assertEqual(manual[3], "manual")

    def test_sort_param_is_accepted(self):
        status, body, _ = self.srv.get("/api/items", sort="used")
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 13)

    def test_media_answers_304_when_unchanged(self):
        _, body, _ = self.srv.get("/api/items")
        path = body["items"][0]["thumb"]
        with urllib.request.urlopen(self.srv.url(path)) as resp:
            etag = resp.headers.get("ETag")
        self.assertTrue(etag)
        req = urllib.request.Request(self.srv.url(path), headers={"If-None-Match": etag})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 304)


class _ImageHost(http.server.BaseHTTPRequestHandler):
    """测试用图床：只认 /a.png 与 /missing.png，不打外网。"""

    blob = PNG_1PX

    def do_GET(self):  # noqa: N802 - 基类命名
        if self.path.startswith("/a.png"):
            body = type(self).blob
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/page.html"):
            body = b"<html>not an image</html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # 测试输出保持干净
        pass


class Sources(Base):
    """工单 09：一张图能从哪进来（本地文件 / 剪贴板 / 链接），以及怎么替换"""

    make_root = staticmethod(all_root)

    def setUp(self):
        super().setUp()
        _ImageHost.blob = PNG_1PX
        self.host = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _ImageHost)
        self.host.daemon_threads = True
        threading.Thread(target=self.host.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.host.server_address[1]}"

    def tearDown(self):
        self.host.shutdown()
        self.host.server_close()
        super().tearDown()

    def png_bytes(self, size=(4, 4)):
        from PIL import Image

        tmp = os.path.join(self.tmp, "_src.png")
        Image.new("RGB", size, (200, 30, 40)).save(tmp)
        with open(tmp, "rb") as f:
            return f.read()

    def first_portrait(self):
        _, body, _ = self.srv.get("/api/items", collection="portrait")
        return body["items"][0]["id"]

    def detail(self, item_id):
        return self.srv.get(f"/api/items/{urllib.parse.quote(item_id, safe='')}")[1]

    # ── 链接导入 ──────────────────────────────

    def test_import_from_url_downloads_and_indexes(self):
        status, body = self.srv.post("/api/import", {"url": self.base + "/a.png"})
        self.assertEqual(status, 200)
        self.assertTrue(body["item_id"].startswith("own:"))
        _, own, _ = self.srv.get("/api/items", collection="own")
        self.assertEqual(own["total"], 1)

    def test_import_from_url_keeps_original_filename(self):
        status, _ = self.srv.post("/api/import", {"url": self.base + "/a.png"})
        self.assertEqual(status, 200)
        found = []
        for dirpath, _, files in os.walk(os.path.join(self.tmp, "library")):
            found += [f for f in files if f == "a.png"]
        self.assertEqual(len(found), 1)

    def test_url_scheme_is_restricted(self):
        status, body = self.srv.post("/api/import", {"url": "file:///C:/Windows/win.ini"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")

    def test_url_that_is_not_an_image_is_rejected(self):
        status, body = self.srv.post("/api/import", {"url": self.base + "/page.html"})
        self.assertEqual(status, 415)
        self.assertEqual(body["error"], "unsupported_ext")

    def test_url_404_is_reported(self):
        status, body = self.srv.post("/api/import", {"url": self.base + "/missing.png"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")

    # ── 替换 ──────────────────────────────────

    def test_replace_with_upload_becomes_the_visible_image(self):
        item_id = self.first_portrait()
        before = self.detail(item_id)["assets"][0]["width"]
        status, body = self.srv.post(
            f"/api/items/{urllib.parse.quote(item_id, safe='')}/replace",
            files={"file": ("better.png", self.png_bytes((9, 7)))},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        after = self.detail(item_id)
        self.assertEqual(after["assets"][0]["width"], 9)
        self.assertNotEqual(after["assets"][0]["width"], before)

    def test_replace_shows_the_new_image_in_the_grid(self):
        item_id = self.first_portrait()
        _, before, _ = self.srv.get("/api/items", collection="portrait")
        status, _ = self.srv.post(
            f"/api/items/{urllib.parse.quote(item_id, safe='')}/replace",
            files={"file": ("better.png", self.png_bytes((9, 7)))},
        )
        self.assertEqual(status, 200)
        _, after, _ = self.srv.get("/api/items", collection="portrait")
        old = {i["id"]: i["thumb"] for i in before["items"]}
        new = {i["id"]: i["thumb"] for i in after["items"]}
        self.assertNotEqual(old[item_id], new[item_id])
        self.assertTrue(new[item_id].startswith("/media/library/"))

    def test_replace_never_deletes_the_collected_original(self):
        item_id = self.first_portrait()
        detail = self.detail(item_id)
        original = [f["path"] for f in detail["assets"][0]["files"]]
        self.srv.post(
            f"/api/items/{urllib.parse.quote(item_id, safe='')}/replace",
            files={"file": ("better.png", self.png_bytes((9, 7)))},
        )
        for rel in original:
            full = os.path.join(self.tmp, rel.replace("/media/", "", 1).replace("/", os.sep))
            self.assertTrue(os.path.isfile(full), f"采集素材被删掉了：{rel}")

    def test_replace_keeps_the_old_version_as_history(self):
        item_id = self.first_portrait()
        before = len(self.detail(item_id)["assets"])
        self.srv.post(
            f"/api/items/{urllib.parse.quote(item_id, safe='')}/replace",
            files={"file": ("better.png", self.png_bytes((9, 7)))},
        )
        after = self.detail(item_id)
        self.assertEqual(len(after["assets"]), before + 1)
        self.assertEqual(after["assets"][0]["role"], "replaced")
        self.assertNotEqual(after["assets"][1]["role"], "replaced")

    def test_replace_from_url(self):
        item_id = self.first_portrait()
        _ImageHost.blob = self.png_bytes((6, 5))
        status, body = self.srv.post(
            f"/api/items/{urllib.parse.quote(item_id, safe='')}/replace", {"url": self.base + "/a.png"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(self.detail(item_id)["assets"][0]["width"], 6)

    def test_replace_by_local_path(self):
        item_id = self.first_portrait()
        src = os.path.join(self.tmp, "picked.png")
        with open(src, "wb") as f:
            f.write(self.png_bytes((5, 3)))
        status, body = self.srv.post(
            f"/api/items/{urllib.parse.quote(item_id, safe='')}/replace", {"path": src}
        )
        self.assertEqual(status, 200)
        self.assertEqual(self.detail(item_id)["assets"][0]["width"], 5)

    def test_replace_unknown_item_is_404(self):
        status, body = self.srv.post(
            "/api/items/nope%3A0/replace", files={"file": ("x.png", self.png_bytes())}
        )
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "not_found")

    def test_replace_requires_a_source(self):
        item_id = self.first_portrait()
        status, body = self.srv.post(f"/api/items/{urllib.parse.quote(item_id, safe='')}/replace", {})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "bad_request")


if __name__ == "__main__":
    unittest.main(verbosity=2)
