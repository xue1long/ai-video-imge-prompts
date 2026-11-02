# -*- coding: utf-8 -*-
"""数据库层：建表、写入、查询。

只有这一个模块碰 SQL。上层（sync / serve / verify）只调用这里的函数，
不自己拼 SQL —— 契约在文档里是端点，在代码里就是这些函数签名。
"""
from __future__ import annotations

import json
import os
import sqlite3

SCHEMA_VERSION = 2

MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS collection(
  slug TEXT PRIMARY KEY, name TEXT NOT NULL, sort INTEGER NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS asset(
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,          -- 相对数据根、正斜杠
  volume TEXT NOT NULL,               -- sites | library
  bytes INTEGER NOT NULL DEFAULT 0,
  width INTEGER, height INTEGER,
  mime TEXT,
  status TEXT NOT NULL DEFAULT 'ok'); -- ok | missing，只由 verify 改写

CREATE TABLE IF NOT EXISTS derivative(
  asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                 -- thumb | mid | full | img | png
  path TEXT NOT NULL,
  bytes INTEGER NOT NULL DEFAULT 0,
  width INTEGER, height INTEGER,
  url TEXT,                           -- 上游地址；本地文件不在时媒体路由重定向到它
  PRIMARY KEY(asset_id, kind));

CREATE INDEX IF NOT EXISTS idx_derivative_path ON derivative(path);

CREATE TABLE IF NOT EXISTS item(
  id TEXT PRIMARY KEY,                -- 集合:外部ID
  collection TEXT NOT NULL REFERENCES collection(slug),
  ext_id TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  title_alt TEXT NOT NULL DEFAULT '',
  prompt TEXT NOT NULL DEFAULT '',
  prompt_raw TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  published_at TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  generator_meta TEXT NOT NULL DEFAULT '',
  search_blob TEXT NOT NULL DEFAULT '',
  last_used_at TEXT,
  use_count INTEGER NOT NULL DEFAULT 0,
  meta TEXT NOT NULL DEFAULT '',
  deleted_at TEXT);                   -- 只表示视图隐藏

CREATE TABLE IF NOT EXISTS item_asset(
  item_id TEXT NOT NULL REFERENCES item(id) ON DELETE CASCADE,
  asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT '',
  ordinal INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(item_id, asset_id));

CREATE TABLE IF NOT EXISTS tag(
  id INTEGER PRIMARY KEY,
  ns TEXT NOT NULL, name TEXT NOT NULL, name_zh TEXT NOT NULL DEFAULT '',
  UNIQUE(ns, name));

CREATE TABLE IF NOT EXISTS item_tag(
  item_id TEXT NOT NULL REFERENCES item(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  source TEXT NOT NULL DEFAULT 'builtin',   -- builtin | manual | auto
  PRIMARY KEY(item_id, tag_id));

CREATE TABLE IF NOT EXISTS fav(
  item_id TEXT PRIMARY KEY REFERENCES item(id) ON DELETE CASCADE,
  at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE INDEX IF NOT EXISTS idx_item_collection ON item(collection);
CREATE INDEX IF NOT EXISTS idx_item_tag_tag ON item_tag(tag_id);
CREATE INDEX IF NOT EXISTS idx_asset_volume ON asset(volume);
"""

DERIVATIVE_ORDER = ("thumb", "mid", "full", "img", "png")

# 用户手动挂到某个素材下的图。采集图 ordinal 从 0 起，这里用一个远大于采集数量的
# 基数，保证「追加的图永远排在采集图之后」，两批 ordinal 不可能撞在一起。
USER_ROLE = "user"
USER_ORDINAL_BASE = 10000


def mime_of(path):
    return MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")


def connect(db_path):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init(conn)
    return conn


def init(conn):
    conn.executescript(SCHEMA)
    _migrate(conn)
    # schema_version 记的是**这份数据是哪个版本建的**，不是代码的版本：
    # 老库升级后这里要保持旧值，sync 才知道该重建（否则数据里的新列是空的，
    # 功能静默失效）。重建完成后由 sync 把它更新成当前版本。
    if not kv_get(conn, "schema_version"):
        conn.execute("INSERT OR REPLACE INTO kv(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
    conn.commit()


def _migrate(conn):
    """老库补列：新增列用 ALTER TABLE 补，不重建表（重建会丢用户标注）。

    补列是幂等的：并发首访时两个连接可能都看到「列不存在」，
    后到的那个会撞上 duplicate column name——那说明列已经加好了，忽略即可。
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(derivative)")}
    if "url" in cols:
        return
    try:
        conn.execute("ALTER TABLE derivative ADD COLUMN url TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise


def kv_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def kv_set(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO kv(key, value) VALUES(?,?)", (key, value))


def set_asset_status(conn, asset_id, status):
    conn.execute("UPDATE asset SET status=? WHERE id=?", (status, asset_id))


def asset_paths(conn):
    return [(r["id"], r["path"], r["status"]) for r in conn.execute("SELECT id, path, status FROM asset")]


def derivative_paths(conn):
    """全部派生图的 (路径, 档位)。用户自己的素材在 library/ 下，不查。"""
    return [(r["path"], r["kind"]) for r in conn.execute(
        "SELECT DISTINCT path, kind FROM derivative WHERE path NOT LIKE 'library/%'")]


def find_own_duplicate(conn, title, bytes_, width, height):
    """判重口径：同一标题 + 同字节数 + 同尺寸。够用，且不需要算哈希。"""
    row = conn.execute(
        "SELECT i.id FROM item i JOIN item_asset ia ON ia.item_id=i.id JOIN asset a ON a.id=ia.asset_id "
        "WHERE i.collection='own' AND i.title=? AND a.bytes=? AND a.width=? AND a.height=? LIMIT 1",
        (title, bytes_, width, height),
    ).fetchone()
    return row["id"] if row else None


PRESERVE_SQL = """
DROP TABLE IF EXISTS _keep_tag;
DROP TABLE IF EXISTS _keep_fav;
DROP TABLE IF EXISTS _keep_hidden;
DROP TABLE IF EXISTS _keep_link;
CREATE TEMP TABLE _keep_tag AS
  SELECT it.item_id AS item_id, t.ns AS ns, t.name AS name, t.name_zh AS name_zh, it.source AS source
  FROM item_tag it JOIN tag t ON t.id=it.tag_id WHERE it.source IN ('manual','auto');
CREATE TEMP TABLE _keep_fav AS SELECT item_id, at FROM fav;
CREATE TEMP TABLE _keep_hidden AS SELECT id, deleted_at FROM item WHERE deleted_at IS NOT NULL;
-- 用户手动挂上去的图：item 会被删掉重建，asset（volume=library）不会，
-- 所以按 path 存，等 item 重建完再按 path 找回 asset id 挂回去。
CREATE TEMP TABLE _keep_link AS
  SELECT ia.item_id AS item_id, a.path AS path, ia.role AS role, ia.ordinal AS ordinal
  FROM item_asset ia JOIN asset a ON a.id=ia.asset_id
  WHERE a.volume='library' AND ia.role='user';
"""


def reset(conn):
    """全量重建前清空生成数据，但**保住用户的标注**。

    采集素材的作品和资产会被删掉重建（它们的真相是 manifest），
    手工标签、收藏、视图隐藏、以及导入素材（volume=library / collection=own）
    必须先存进临时表再放回来——否则每次加一张图都会把几百小时的打标抹掉。
    """
    conn.executescript(PRESERVE_SQL)
    conn.execute("DELETE FROM item WHERE collection <> 'own'")
    conn.execute("DELETE FROM asset WHERE volume <> 'library'")
    conn.execute("DELETE FROM tag WHERE id NOT IN (SELECT tag_id FROM item_tag)")
    conn.commit()


def restore_user_data(conn):
    conn.execute("INSERT OR IGNORE INTO tag(ns, name, name_zh) SELECT DISTINCT ns, name, name_zh FROM _keep_tag")
    conn.execute(
        "INSERT OR IGNORE INTO item_tag(item_id, tag_id, source) "
        "SELECT k.item_id, t.id, k.source FROM _keep_tag k JOIN tag t ON t.ns=k.ns AND t.name=k.name "
        "WHERE k.item_id IN (SELECT id FROM item)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO fav(item_id, at) SELECT item_id, at FROM _keep_fav WHERE item_id IN (SELECT id FROM item)"
    )
    conn.execute(
        "UPDATE item SET deleted_at=(SELECT h.deleted_at FROM _keep_hidden h WHERE h.id=item.id) "
        "WHERE id IN (SELECT id FROM _keep_hidden)"
    )
    # 手工挂上去的图：item 重建完、asset 还在，按 path 重新接上
    conn.execute(
        "INSERT OR IGNORE INTO item_asset(item_id, asset_id, role, ordinal) "
        "SELECT k.item_id, a.id, k.role, k.ordinal FROM _keep_link k JOIN asset a ON a.path=k.path "
        "WHERE k.item_id IN (SELECT id FROM item)"
    )
    conn.executescript(
        "DROP TABLE IF EXISTS _keep_tag; DROP TABLE IF EXISTS _keep_fav; "
        "DROP TABLE IF EXISTS _keep_hidden; DROP TABLE IF EXISTS _keep_link;"
    )
    conn.commit()


def upsert_collection(conn, slug, name, sort=0):
    conn.execute(
        "INSERT INTO collection(slug, name, sort) VALUES(?,?,?) "
        "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, sort=excluded.sort",
        (slug, name, sort),
    )


def add_asset(conn, path, volume, bytes_=0, width=None, height=None):
    conn.execute(
        "INSERT OR IGNORE INTO asset(path, volume, bytes, width, height, mime) VALUES(?,?,?,?,?,?)",
        (path, volume, bytes_ or 0, width, height, mime_of(path)),
    )
    row = conn.execute("SELECT id, status FROM asset WHERE path=?", (path,)).fetchone()
    return row["id"], row["status"] == "missing"


def safe_url(url):
    """上游地址的写入前过滤：只留 http(s)，并剥掉控制字符。

    地址最终会出现在 Location 响应头里，带换行的地址会变成响应头注入。
    收在写入这一处，比在每个读取方各查一遍可靠。
    """
    if not url:
        return None
    u = str(url)
    if any(ch < " " or ch == "\x7f" for ch in u):
        return None
    if not u.lower().startswith(("http://", "https://")):
        return None
    return u


def add_derivative(conn, asset_id, kind, path, bytes_=0, width=None, height=None, url=""):
    conn.execute(
        "INSERT OR REPLACE INTO derivative(asset_id, kind, path, bytes, width, height, url) "
        "VALUES(?,?,?,?,?,?,?)",
        (asset_id, kind, path, bytes_ or 0, width, height, safe_url(url)),
    )


def derivative_url(conn, path):
    """某个本地路径对应的上游地址；没有则空串。"""
    row = conn.execute("SELECT url FROM derivative WHERE path=? AND url IS NOT NULL LIMIT 1",
                       (path,)).fetchone()
    return (row["url"] if row else "") or ""


def add_item(conn, **f):
    cols = ("id", "collection", "ext_id", "title", "title_alt", "prompt", "prompt_raw",
            "author", "source_url", "published_at", "model", "generator_meta", "search_blob", "meta")
    vals = [f.get(c, "") for c in cols]
    conn.execute(f"INSERT OR REPLACE INTO item({','.join(cols)}) VALUES({','.join('?' * len(cols))})", vals)


def link_asset(conn, item_id, asset_id, role="", ordinal=0):
    conn.execute(
        "INSERT OR IGNORE INTO item_asset(item_id, asset_id, role, ordinal) VALUES(?,?,?,?)",
        (item_id, asset_id, role, ordinal),
    )


def upsert_tag(conn, ns, name, name_zh=""):
    conn.execute(
        "INSERT OR IGNORE INTO tag(ns, name, name_zh) VALUES(?,?,?)", (ns, name, name_zh or name)
    )
    row = conn.execute("SELECT id FROM tag WHERE ns=? AND name=?", (ns, name)).fetchone()
    return row["id"]


def tag_item(conn, item_id, tag_id, source="builtin"):
    conn.execute(
        "INSERT OR REPLACE INTO item_tag(item_id, tag_id, source) VALUES(?,?,?)",
        (item_id, tag_id, source),
    )


def item_tags(conn, item_id):
    rows = conn.execute(
        "SELECT t.ns, t.name, t.name_zh, it.source FROM item_tag it JOIN tag t ON t.id = it.tag_id "
        "WHERE it.item_id=? ORDER BY t.ns, t.name",
        (item_id,),
    ).fetchall()
    return [[r["ns"], r["name"], r["name_zh"], r["source"]] for r in rows]


class BuiltinTagError(Exception):
    """上游分面不允许被手工删除：删了就再也同步不回来了。"""


def add_tag(conn, item_id, ns, name, source="manual"):
    tag_id = upsert_tag(conn, ns, name)
    conn.execute(
        "INSERT OR REPLACE INTO item_tag(item_id, tag_id, source) VALUES(?,?,?)", (item_id, tag_id, source)
    )
    refresh_blob(conn, item_id)
    return item_tags(conn, item_id)


def del_tag(conn, item_id, ns, name):
    row = conn.execute(
        "SELECT it.rowid AS rid, it.source AS source FROM item_tag it JOIN tag t ON t.id=it.tag_id "
        "WHERE it.item_id=? AND t.ns=? AND t.name=?",
        (item_id, ns, name),
    ).fetchone()
    if row is None:
        return item_tags(conn, item_id)
    if row["source"] == "builtin":
        raise BuiltinTagError(f"{ns}:{name}")
    conn.execute("DELETE FROM item_tag WHERE rowid=?", (row["rid"],))
    refresh_blob(conn, item_id)
    return item_tags(conn, item_id)


def set_fav(conn, item_id, on):
    if on:
        conn.execute("INSERT OR IGNORE INTO fav(item_id, at) VALUES(?, datetime('now'))", (item_id,))
    else:
        conn.execute("DELETE FROM fav WHERE item_id=?", (item_id,))
    return on


def item_exists(conn, item_id):
    return conn.execute("SELECT 1 FROM item WHERE id=?", (item_id,)).fetchone() is not None


def collections(conn):
    rows = conn.execute(
        "SELECT c.slug, c.name, "
        " (SELECT COUNT(*) FROM item i WHERE i.collection=c.slug) AS items, "
        " (SELECT COUNT(*) FROM item_asset ia JOIN item i ON i.id=ia.item_id WHERE i.collection=c.slug) AS assets "
        "FROM collection c ORDER BY c.sort, c.slug"
    ).fetchall()
    return [dict(r) for r in rows]


def _item_row(conn, row):
    item_id = row["id"]
    thumb = conn.execute(
        "SELECT COALESCE(d.path, a.path) AS p FROM item_asset ia JOIN asset a ON a.id=ia.asset_id "
        "LEFT JOIN derivative d ON d.asset_id=a.id AND d.kind='thumb' "
        "WHERE ia.item_id=? ORDER BY ia.ordinal, a.id LIMIT 1",
        (item_id,),
    ).fetchone()
    fav = conn.execute("SELECT 1 FROM fav WHERE item_id=?", (item_id,)).fetchone()
    return {
        "id": item_id,
        "collection": row["collection"],
        "title": row["title"],
        "title_alt": row["title_alt"],
        "prompt_raw": row["prompt_raw"],
        "thumb": "/media/" + thumb["p"] if thumb else "",
        "fav": bool(fav),
        "hidden": bool(row["deleted_at"]),
        "tags": item_tags(conn, item_id),
    }


def refresh_blob(conn, item_id=None):
    """重算检索列。冗余一列换来「搜索只 LIKE 一列、不 join」。

    内容是 title + title_alt + prompt + prompt_raw + 全部分面名（原语言与中文），
    打标之后必须调用，否则新标签搜不到。
    """
    sql = (
        "UPDATE item SET search_blob = trim(title || ' ' || title_alt || ' ' || prompt || ' ' || prompt_raw || ' ' || "
        "COALESCE((SELECT group_concat(t.ns || ' ' || t.name || ' ' || t.name_zh, ' ') "
        "FROM item_tag it JOIN tag t ON t.id=it.tag_id WHERE it.item_id=item.id), ''))"
    )
    if item_id:
        conn.execute(sql + " WHERE id=?", (item_id,))
    else:
        conn.execute(sql)


HIDDEN_NS, HIDDEN_NAME = "状态", "隐藏"


def set_hidden(conn, item_id, on):
    """视图隐藏：写 deleted_at 并同步那个标签。只有这一处写 deleted_at。

    物理文件一个字节都不动——采集素材永远不删。
    """
    import datetime as _dt

    if on:
        conn.execute(
            "UPDATE item SET deleted_at=? WHERE id=?", (_dt.datetime.now().isoformat(timespec="seconds"), item_id)
        )
        add_tag(conn, item_id, HIDDEN_NS, HIDDEN_NAME, "manual")
    else:
        conn.execute("UPDATE item SET deleted_at=NULL WHERE id=?", (item_id,))
        row = conn.execute(
            "SELECT it.rowid AS rid FROM item_tag it JOIN tag t ON t.id=it.tag_id "
            "WHERE it.item_id=? AND t.ns=? AND t.name=?",
            (item_id, HIDDEN_NS, HIDDEN_NAME),
        ).fetchone()
        if row:
            conn.execute("DELETE FROM item_tag WHERE rowid=?", (row["rid"],))
        refresh_blob(conn, item_id)
    return on


def is_hidden_request(ns, name):
    return ns == HIDDEN_NS and name == HIDDEN_NAME


def list_items(conn, collection=None, page=1, size=120, facets=None, q=None, include_hidden=False, sort="id"):
    where, args = ["1=1"], []
    if not include_hidden:
        where.append("deleted_at IS NULL")
    if collection:
        where.append("collection=?")
        args.append(collection)
    for ns, name in facets or []:
        if name:
            where.append(
                "EXISTS (SELECT 1 FROM item_tag it JOIN tag t ON t.id=it.tag_id "
                "WHERE it.item_id=item.id AND t.ns=? AND t.name=?)"
            )
            args.extend([ns, name])
        else:
            # 只要命名空间、不要值：存在性过滤（该命名空间下有任意标签即命中）。
            # 用途是集合内的「视图」——如「风格」= 带 sref 码的条目 = 有「风格参考」标签。
            where.append(
                "EXISTS (SELECT 1 FROM item_tag it JOIN tag t ON t.id=it.tag_id "
                "WHERE it.item_id=item.id AND t.ns=?)"
            )
            args.append(ns)
    if q:
        where.append("search_blob LIKE ?")
        args.append(f"%{q}%")
    clause = " AND ".join(where)
    order = "last_used_at DESC NULLS LAST, collection, ext_id" if sort == "used" else "collection, ext_id"
    total = conn.execute(f"SELECT COUNT(*) AS n FROM item WHERE {clause}", args).fetchone()["n"]
    rows = conn.execute(
        f"SELECT * FROM item WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?",
        args + [size, (page - 1) * size],
    ).fetchall()
    return total, [_item_row(conn, r) for r in rows]


def count_ns(conn, collection=None, ns=None):
    """某命名空间下的**去重条目数**（与 list_items 的存在性过滤同口径）。

    不能用「该命名空间的标签数之和」：一个条目在同一命名空间下可能有多个
    标签（如一条作业带多个 sref 码），相加会把条目数算多。
    """
    where, args = ["i.deleted_at IS NULL"], []
    if collection:
        where.append("i.collection=?")
        args.append(collection)
    if ns:
        where.append(
            "EXISTS (SELECT 1 FROM item_tag it JOIN tag t ON t.id=it.tag_id "
            "WHERE it.item_id=i.id AND t.ns=?)"
        )
        args.append(ns)
    clause = " AND ".join(where)
    row = conn.execute(f"SELECT COUNT(*) AS n FROM item i WHERE {clause}", args).fetchone()
    return row["n"]


def list_facets(conn, collection=None, include_hidden=False):
    """分面与计数。按集合隔离：A 集合不会出现 B 集合的分面值。"""
    where, args = [], []
    if collection:
        where.append("i.collection=?")
        args.append(collection)
    if not include_hidden:
        where.append("i.deleted_at IS NULL")
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        "SELECT t.ns AS ns, t.name AS name, t.name_zh AS name_zh, COUNT(*) AS count "
        "FROM item_tag it JOIN tag t ON t.id=it.tag_id JOIN item i ON i.id=it.item_id "
        f"{clause} GROUP BY t.ns, t.name ORDER BY t.ns, count DESC, t.name",
        args,
    ).fetchall()
    return [dict(r) for r in rows]


def primary_asset_path(conn, item_id):
    """作品的原始文件路径（相对数据根）。送素材、取 prompt 都从这里出发。"""
    row = conn.execute(
        "SELECT a.path FROM item_asset ia JOIN asset a ON a.id=ia.asset_id "
        "WHERE ia.item_id=? ORDER BY ia.ordinal, a.id LIMIT 1",
        (item_id,),
    ).fetchone()
    return row["path"] if row else None


def next_user_ordinal(conn, item_id):
    """给「追加一张图」分配序号，接在已有用户图后面。"""
    row = conn.execute(
        "SELECT MAX(ordinal) AS m FROM item_asset WHERE item_id=? AND role=?",
        (item_id, USER_ROLE),
    ).fetchone()
    if not row or row["m"] is None:
        return USER_ORDINAL_BASE
    return max(int(row["m"]) + 1, USER_ORDINAL_BASE + 1)


def user_assets(conn, item_id):
    """这条素材下用户自己挂的图，按序号返回 [(asset_id, 相对路径)]。

    判重不能只看字节数和宽高——两张同尺寸的图很容易撞在一起。
    这里只负责取路径，真正的比对在 actions 里按文件内容算哈希。
    """
    rows = conn.execute(
        "SELECT ia.asset_id AS id, a.path AS path FROM item_asset ia JOIN asset a ON a.id=ia.asset_id "
        "WHERE ia.item_id=? AND ia.role=? ORDER BY ia.ordinal",
        (item_id, USER_ROLE),
    ).fetchall()
    return [(r["id"], r["path"]) for r in rows]


def get_item(conn, item_id):
    row = conn.execute("SELECT * FROM item WHERE id=?", (item_id,)).fetchone()
    if not row:
        return None
    assets = conn.execute(
        "SELECT a.id, a.path, a.status, a.width, a.height, ia.role FROM item_asset ia "
        "JOIN asset a ON a.id=ia.asset_id WHERE ia.item_id=? ORDER BY ia.ordinal, a.id",
        (item_id,),
    ).fetchall()
    out_assets = []
    for a in assets:
        derivs = conn.execute(
            "SELECT kind, path, width, height FROM derivative WHERE asset_id=?", (a["id"],)
        ).fetchall()
        kinds = {d["kind"]: d["path"] for d in derivs}
        files = [
            {"kind": k, "path": "/media/" + kinds[k]} for k in DERIVATIVE_ORDER if k in kinds
        ]
        out_assets.append(
            {
                "id": a["id"],
                "role": a["role"],
                "status": a["status"],
                "width": a["width"],
                "height": a["height"],
                "files": files,
                "primary": files[0]["path"] if files else "/media/" + a["path"],
            }
        )
    meta = {}
    if row["generator_meta"]:
        try:
            meta = json.loads(row["generator_meta"])
        except ValueError:
            meta = {}
    return {
        "item": {
            "id": row["id"],
            "collection": row["collection"],
            "title": row["title"],
            "title_alt": row["title_alt"],
            "prompt": row["prompt"],
            "prompt_raw": row["prompt_raw"],
            "author": row["author"],
            "source_url": row["source_url"],
            "published_at": row["published_at"],
            "model": row["model"],
            "generator_meta": meta,
            "hidden": bool(row["deleted_at"]),
            "fav": bool(conn.execute("SELECT 1 FROM fav WHERE item_id=?", (item_id,)).fetchone()),
        },
        "assets": out_assets,
        "tags": item_tags(conn, item_id),
    }
