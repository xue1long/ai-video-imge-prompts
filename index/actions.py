# -*- coding: utf-8 -*-
"""文件系统动作：送素材到目标目录、导入新素材。

数据库写入在 store.py，这里只做「碰磁盘」的事——两类操作风险差三个数量级，
代码上也分开，不存在一个函数同时改 DB 和删文件。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request

import store

THUMB_MAX = 400
THUMB_QUALITY = 82
# 生成工具写进 PNG 的文本块里，这些是元数据噪音，不是生成参数
META_NOISE = {"dpi", "gamma", "aspect", "transparency", "icc_profile", "exif", "jfif"}
URL_TIMEOUT = 20
URL_MAX_BYTES = 40 * 1024 * 1024
# 替换进来的新图排在所有原图前面，查询「主图」就是取 ordinal 最小的那条
REPLACED_ORDINAL = -1


class UnsupportedExt(Exception):
    pass


class BadSource(Exception):
    """链接取不回来，或链接指向的不是图片。"""


class Duplicate(Exception):
    def __init__(self, existing_id):
        super().__init__(existing_id)
        self.existing_id = existing_id


def unique_name(dirpath, name):
    """目标目录里已有同名文件时追加 -2/-3，绝不覆盖。"""
    stem, ext = os.path.splitext(name)
    candidate, i = name, 2
    while os.path.exists(os.path.join(dirpath, candidate)):
        candidate = f"{stem}-{i}{ext}"
        i += 1
    return candidate


def send(src, target_dir):
    """把源文件送到目标目录：优先硬链接（同盘零拷贝），失败退回复制。

    返回 (目标路径, 方式)。绝不删除目标目录里的任何东西。
    """
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    os.makedirs(target_dir, exist_ok=True)
    dst = os.path.join(target_dir, unique_name(target_dir, os.path.basename(src)))
    try:
        os.link(src, dst)
        return dst, "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return dst, "copy"


# ── 导入 ────────────────────────────────────────────────────────


def fetch_url(url, dest_dir):
    """把链接里的图片下载到 dest_dir，返回本地路径。

    只认 http/https：`file://` 会变成「读本机任意文件」，不做。
    下载完先用 Pillow 开一次，不开就直接拒绝，免得半张破图进库。
    """
    scheme = (urllib.parse.urlparse(url).scheme or "").lower()
    if scheme not in ("http", "https"):
        raise BadSource("只支持 http/https 链接，收到的是：%s" % (scheme or "空"))

    req = urllib.request.Request(url, headers={"User-Agent": "material-manager/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=URL_TIMEOUT) as resp:
            blob = resp.read(URL_MAX_BYTES + 1)
            ctype = (resp.headers.get_content_type() or "").lower()
    except (OSError, ValueError) as e:  # URLError/HTTPError 都是 OSError 的子类
        raise BadSource("下载失败：%s" % e)

    if len(blob) > URL_MAX_BYTES:
        raise BadSource("文件超过 %d MB" % (URL_MAX_BYTES // 1048576))

    name = os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(url).path)) or ""
    name = name.split("?")[0]
    stem, ext = os.path.splitext(name)
    if ext.lower() not in store.MIME:
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
               "image/gif": ".gif", "image/bmp": ".bmp"}.get(ctype, "")
        stem = stem or "url-%s" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        name = stem + (ext or "")
    if os.path.splitext(name)[1].lower() not in store.MIME:
        raise UnsupportedExt(name or ctype or "(无扩展名)")

    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, name)
    with open(path, "wb") as f:
        f.write(blob)

    try:
        from PIL import Image

        with Image.open(path) as im:
            im.verify()
    except Exception:  # noqa: BLE001 - 任何解析失败都算「这不是图片」
        raise UnsupportedExt(name)
    return path


def text_chunks(info):
    """PNG 里的文本块原样收下。不针对某个工具写解析器，谁写的都留着。"""
    out = {}
    for key, val in (info or {}).items():
        if key in META_NOISE:
            continue
        if isinstance(val, bytes):
            try:
                val = val.decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                continue
        if isinstance(val, str) and val.strip():
            out[key] = val
    return out


def _prompt_from(meta):
    for key in ("prompt", "Description", "parameters", "Prompt"):
        if meta.get(key):
            return " ".join(str(meta[key]).split())
    return ""


def _make_thumb(src, dest_rel_dir, stem, root):
    """生成缩略图。原图可能 2 MB，不缩会让网格卡死。"""
    from PIL import Image

    rel = f"{dest_rel_dir}/{stem}.webp"
    full = os.path.join(root, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB") if im.mode not in ("RGB", "RGBA") else im
        im.thumbnail((THUMB_MAX, THUMB_MAX))
        try:
            im.save(full, "WEBP", quality=THUMB_QUALITY)
        except Exception:  # noqa: BLE001 - 没编 webp 就退 png
            rel = f"{dest_rel_dir}/{stem}.png"
            full = os.path.join(root, rel.replace("/", os.sep))
            im.save(full, "PNG")
    return rel


def probe_image(src):
    """先看一眼再动盘：扩展名、尺寸、生成参数，以及它到底是不是一张图。"""
    ext = os.path.splitext(src)[1].lower()
    if ext not in store.MIME:
        raise UnsupportedExt(ext)
    from PIL import Image

    try:
        with Image.open(src) as im:
            width, height = im.size
            meta = text_chunks(im.info)
    except Exception as e:  # noqa: BLE001 - 坏图不该进库
        raise UnsupportedExt("%s（%s）" % (ext, e))
    return {"size": os.path.getsize(src), "width": width, "height": height, "meta": meta}


def store_image(root, src, info=None):
    """把一张图复制进 library/YYYY/MM 并生成缩略图。只落盘，不建任何记录。"""
    info = info or probe_image(src)
    now = datetime.date.today()
    yyyy, mm = f"{now.year:04d}", f"{now.month:02d}"
    dest_dir = f"library/{yyyy}/{mm}"
    abs_dir = os.path.join(root, dest_dir.replace("/", os.sep))
    os.makedirs(abs_dir, exist_ok=True)
    name = unique_name(abs_dir, os.path.basename(src))
    dest_rel = f"{dest_dir}/{name}"
    shutil.copy2(src, os.path.join(root, dest_rel.replace("/", os.sep)))
    thumb_rel = _make_thumb(src, f"library/_thumbs/{yyyy}/{mm}", os.path.splitext(name)[0], root)
    return dict(info, path=dest_rel, thumb=thumb_rel, name=name)


def import_file(root, conn, src):
    """把一个图片文件收进可写素材区并建索引。返回新作品 id。"""
    info = probe_image(src)
    stem = os.path.splitext(os.path.basename(src))[0]

    dup = store.find_own_duplicate(conn, stem, info["size"], info["width"], info["height"])
    if dup:
        raise Duplicate(dup)

    stored = store_image(root, src, info)
    name = stored["name"]
    prompt = _prompt_from(info["meta"])
    yyyy, mm = stored["path"].split("/")[1:3]

    item_id = f"own:{yyyy}{mm}-{os.path.splitext(name)[0]}"
    suffix = 2
    while store.item_exists(conn, item_id):
        item_id = f"own:{yyyy}{mm}-{os.path.splitext(name)[0]}-{suffix}"
        suffix += 1

    store.add_item(
        conn,
        id=item_id,
        collection="own",
        ext_id=item_id.split(":", 1)[1],
        title=os.path.splitext(name)[0],
        title_alt="",
        prompt_raw=prompt,
        generator_meta=json.dumps(info["meta"], ensure_ascii=False) if info["meta"] else "",
    )
    asset_id, _ = store.add_asset(conn, stored["path"], "library", info["size"], info["width"], info["height"])
    store.add_derivative(conn, asset_id, "thumb", stored["thumb"])
    store.add_derivative(conn, asset_id, "full", stored["path"])
    store.link_asset(conn, item_id, asset_id, role="full", ordinal=0)

    tag_id = store.upsert_tag(conn, "状态", "未审", "未审")
    store.tag_item(conn, item_id, tag_id, "auto")
    store.refresh_blob(conn, item_id)
    return item_id


def replace_image(root, conn, item_id, src):
    """给已有作品换一张图。

    新文件进 `library/` 并排到主图位（ordinal=-1）；采集来的原图一个字节都不动，
    只是不再是「第一张」。所以这个操作对 `sites/` 仍然合法，也可以随时反悔。
    """
    info = probe_image(src)
    stored = store_image(root, src, info)

    asset_id, _ = store.add_asset(conn, stored["path"], "library", info["size"], info["width"], info["height"])
    store.add_derivative(conn, asset_id, "thumb", stored["thumb"])
    store.add_derivative(conn, asset_id, "full", stored["path"])
    store.link_asset(conn, item_id, asset_id, role="replaced", ordinal=REPLACED_ORDINAL)

    prompt = _prompt_from(info["meta"])
    row = conn.execute("SELECT prompt_raw FROM item WHERE id=?", (item_id,)).fetchone()
    if prompt and row and not row["prompt_raw"]:
        conn.execute("UPDATE item SET prompt_raw=? WHERE id=?", (prompt, item_id))
    store.refresh_blob(conn, item_id)
    return {"item_id": item_id, "asset_id": asset_id, "path": stored["path"], "thumb": stored["thumb"]}


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def attach_image(root, conn, item_id, src):
    """给已有素材**追加**一张图，排在所有采集图之后。

    和 `replace_image` 的分工：那边抢主图位（ordinal=-1，用来把某张换成更好的），
    这边只往图条末尾接一张，主图不动，原图一张不少。

    同一条素材下重复传同一张会被挡掉。判定按文件内容哈希，不看字节数和宽高——
    两张 4×4 的图长度可以一模一样，按元数据判会把第二张当成重复。
    判重只在本素材范围内：不同提示词配同一张图是正常用法。
    """
    info = probe_image(src)
    digest = _sha1(src)
    for asset_id, rel in store.user_assets(conn, item_id):
        full = os.path.join(root, rel.replace("/", os.sep))
        if os.path.isfile(full) and _sha1(full) == digest:
            return {"item_id": item_id, "asset_id": asset_id, "skipped": True}

    stored = store_image(root, src, info)
    asset_id, _ = store.add_asset(conn, stored["path"], "library", info["size"], info["width"], info["height"])
    store.add_derivative(conn, asset_id, "thumb", stored["thumb"])
    store.add_derivative(conn, asset_id, "full", stored["path"])
    ordinal = store.next_user_ordinal(conn, item_id)
    store.link_asset(conn, item_id, asset_id, role=store.USER_ROLE, ordinal=ordinal)
    store.refresh_blob(conn, item_id)
    return {
        "item_id": item_id,
        "asset_id": asset_id,
        "ordinal": ordinal,
        "path": stored["path"],
        "thumb": stored["thumb"],
        "skipped": False,
    }


def import_path(root, conn, path):
    """接受单个文件或整个文件夹（递归一层目录里的图片）。返回 (数量, 跳过, 新 id 列表)。"""
    path = os.path.abspath(path)
    if os.path.isdir(path):
        done, skipped, ids = 0, 0, []
        for entry in sorted(os.listdir(path)):
            sub = os.path.join(path, entry)
            if not os.path.isfile(sub):
                continue
            if os.path.splitext(sub)[1].lower() not in store.MIME:
                skipped += 1
                continue
            try:
                ids.append(import_file(root, conn, sub))
                done += 1
            except Duplicate as e:
                ids.append(e.existing_id)
        return done, skipped, ids
    return 1, 0, [import_file(root, conn, path)]
