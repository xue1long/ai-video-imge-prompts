# -*- coding: utf-8 -*-
"""Midlibrary（Midjourney 风格库）站点配置。

站点 id：midlibrary
数据源：https://midlibrary.io/library（JB Nina, Inc. 运营的 Midjourney 风格与
        风格参考码库。Next.js App Router，数据在服务端渲染进 RSC flight payload，
        没有公开 JSON 接口；robots.txt 只禁 /api/。）
授权：conditional —— 站方已书面许可：允许个人学习用途的镜像（文本层 + 图片层），
        要求署名与回链原站。详见 sites/midlibrary/NOTICE.md。

本文件是本站的**唯一契约**：采集脚本（extract.py）、清单脚本（manifest.py）、
构建脚本（build_gallery.py）都从这里取常量与文案。改口径只改这里。

数据规模（2026-11-05 实测）：
    上游 10,142 条 = 5,504 个风格名 + 4,638 个风格参考码（SREF）
    清单实收 10,140 条 —— 少的那 2 条（jan-saudek / super-mario）上游自己就没有
    v8.2 样例表（sheetUrl 为 null，只有旧版本单图），不伪造图，直接跳过。
    列表页每页 48 条，共 212 页；16 个分类、7 种 kind。

条目结构（上游列表页 flight payload 里的 tiles 数组）：
    id             ULID，上游主键（本站不用）
    slug           URL 段；风格是 kebab-case 名字，SREF 是 6 位十六进制
    name           人类可读名（SREF 条目也有名字，如 "Hillside Letterform"）
    kind           artist | genre | movement | title | technique | style_quality | style_code
    category       分类的英文标签，如 "Illustrators"
    categorySlug   分类的键，如 "illustrators"（16 个，见 CATEGORIES）
    isPick         站方精选徽章
    isPublicDomain 公有领域徽章
    testedMark     已实测徽章
    prompt         **可复制的一行**：风格是 "by Puuung --v 8.2"，
                   SREF 是 "--sref 3383230063 --v 8.2"
    sheetUrl       该条目的整张样例表（一张 2048×2048 的 JPEG，含该风格的 4 张样例）
    sheetQuadrant  卡片取 sheet 的哪一角（1..4）→ 见 QUAD_GRAVITY
"""
import os

# ── 采集 ────────────────────────────────────────────
ORIGIN = "https://midlibrary.io"
SOURCE = "https://midlibrary.io/library"
# 列表页：/library?page=N（page 从 1 开始，212 页）
LIST_PATH = "/library"
PAGE_SIZE_UPSTREAM = 48
TOTAL_PAGES = 212
# 站方精选（实测 554 条）：先跑它验证全链路，再补全量。
# ⚠️ 精选**只是全量的一个子集**：实测 ?pick=1 回来的 554 条全是
# kind=style_code / category=sref-styles，上游自己其余 15 个分类的 count 也是 0。
# 拿精选清单建站会以为本站只有 1 个分类 —— 16 个分类落地页要等全量清单。
PICK_TOTAL = 554
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
# 图源与列表页被 DNS 污染时设 FETCH_PROXY（如 http://127.0.0.1:7897）
PROXY = os.environ.get("FETCH_PROXY", "")
# 礼貌抓取：上游单页最慢实测 20–60 秒（也有 0.6 秒的时候），且大图经常中途断流
FETCH_WORKERS = 4
REQUEST_TIMEOUT = 240
RETRY = 4

# ── 站点身份 ─────────────────────────────────────────
ID = "midlibrary"
CODE = "MIDLIB-01"
NAME_ZH = "Midlibrary 风格库"
NAME_JA = "Midlibrary スタイル集"
LICENSE = "conditional"

# ── 图源 ────────────────────────────────────────────
# 图片全在 https://midlibrary.io/img/ 下，没有独立 CDN 域名。
# **Referer 门**：不带 Referer 一律 403（Cloudflare 挑战页）；
# Referer 的 host 必须是 midlibrary.io（外站热链会被 Worker 挡掉：
# "Pictures are shown on midlibrary.io."）。取图钩子见 scripts/fetch_hook.py。
#
# ⚠️ IMG_BASE 只是**URL 前缀**（catalog 校验地址前缀用），**不是拼地址的基准**：
# 上游 tile 的 sheetUrl 本身就带 img/ 这一段，拼地址要用下面的 img_url()。
IMG_BASE = ORIGIN + "/img/"
IMAGE_BASES = [IMG_BASE]


def img_url(sheet_path, params=""):
    """拼一条图片的完整地址。

    sheet_path 形如 `img/midjourney-styles/v82/xxx.jpg`（上游 tile 的 sheetUrl
    去掉开头斜杠后的样子，**已经含 img/ 这一段**）。所以基准是站点根 ORIGIN，
    不是 IMG_BASE —— 用 IMG_BASE 拼会得到 /img/img/ 的废地址（上游 404）。
    """
    return ORIGIN + "/" + sheet_path + params


# 卡片缩略图 = sheet 的一角（与上游显示完全一致，裁剪交给上游做）
#   thumb: ?crop=1024,1024&crop_gravity=<方位>&width=320   → 约 28 KB (jpeg) / 更小 (webp)
#   mid  : ?width=960                                        → 整张样例表，灯箱一次看全 4 张
# 上游的样例表是 2048×2048 装 4 张样例：先裁成 1024×1024 再缩到 THUMB_WIDTH，
# 与上游卡片的裁法一致（上游自己也发这个地址）。
CROP_SIZE = 1024
THUMB_WIDTH = 320
MID_WIDTH = 960
# sheetQuadrant → Cloudflare 裁剪方位（实测：q=1→nw、q=2→ne、q=3→sw、q=4→se）
QUAD_GRAVITY = {
    1: "northwest",
    2: "northeast",
    3: "southwest",
    4: "southeast",
}
# 取图时用 webp（同体积下比 jpeg 小三成，上游按 Accept 协商）
IMAGE_ACCEPT = "image/webp,image/apng,image/*,*/*;q=0.8"
IMAGE_EXT = ".webp"

# ── 数据文件 ─────────────────────────────────────────
# 单文件 data/gallery.js（与 midjourney-explore 同形）：
# 10,142 条 ≈ 2.3 MB，比 prompts 站的一个分片小一个量级，不必再切分片。
DATA_FILE = "gallery.js"

# ── 分类（上游的 16 个分类，标签与计数取自列表页的 categories 分面）────
# (slug, 上游标签, 计数, 中文, 日文)
# ⚠️ 这里的计数是**上游自己报的**数字，只作参照；构建产物里的分类计数
# 一律按 manifest 实算（上游那 2 条没有样例表的条目会让 photographers 少 1）。
CATEGORIES = [
    ("painters", "Painters", 1546, "画家", "画家"),
    ("illustrators", "Illustrators", 919, "插画师", "イラストレーター"),
    ("photographers", "Photographers", 685, "摄影师", "写真家"),
    ("various-artists", "Various", 309, "其他艺术家", "その他のアーティスト"),
    ("sculpture-installation", "Sculptors", 236, "雕塑与装置", "彫刻・インスタレーション"),
    ("designers", "Designers", 165, "设计师", "デザイナー"),
    ("fashion-designers", "Fashion designers", 135, "时装设计师", "ファッションデザイナー"),
    ("filmmakers", "Filmmakers", 118, "电影人", "映画監督"),
    ("architects", "Architects", 107, "建筑师", "建築家"),
    ("street-artists", "Street artists", 60, "街头艺术家", "ストリートアーティスト"),
    ("printmakers", "Printmakers", 43, "版画家", "版の画家"),
    ("genres-art-movements", "Genres", 312, "流派与艺术运动", "ジャンル・芸術運動"),
    ("general-modifiers", "Modifiers", 175, "通用修饰词", "汎用モディファイア"),
    ("techniques", "Techniques", 393, "技法", "テクニック"),
    ("titles", "Titles", 301, "作品标题", "タイトル"),
    ("sref-styles", "SREF codes", 4638, "风格参考码", "SREF コード"),
]
CATEGORY_ZH = dict((c[0], c[3]) for c in CATEGORIES)
CATEGORY_JA = dict((c[0], c[4]) for c in CATEGORIES)
CATEGORY_LABEL = dict((c[0], c[1]) for c in CATEGORIES)

# ── kind（7 种）─────────────────────────────────────
# (kind, 中文, 日文)
KINDS = [
    ("style_code", "风格参考码", "SREF コード"),
    ("artist", "艺术家", "アーティスト"),
    ("technique", "技法", "テクニック"),
    ("title", "作品标题", "タイトル"),
    ("genre", "流派", "ジャンル"),
    ("movement", "艺术运动", "芸術運動"),
    ("style_quality", "风格修饰", "スタイルの性質"),
]
KIND_ZH = dict((k[0], k[1]) for k in KINDS)
KIND_JA = dict((k[0], k[2]) for k in KINDS)

# ── manifest 契约 ────────────────────────────────────
# scripts/manifest.py 产出、scripts/build_gallery.py 消费。
# 每行一条上游条目；档位字段遵守 <tier>_url / <tier>_path 约定。
MANIFEST_FIELDS = [
    "id",              # = slug（本站用 slug 当主键，不用上游 ULID）
    "slug",
    "name",
    "kind",
    "category",        # 分类 slug
    "prompt",          # 可复制的一行
    "sref",            # 仅 style_code 条目有：纯码，如 "3383230063"
    "isPick",
    "isPublicDomain",
    "testedMark",
    "sourceUrl",       # 原站条目页
    "thumb_url",
    "thumb_path",
    "mid_url",
    "mid_path",
]

# ── 界面文案 ─────────────────────────────────────────
UI = {
    "zh": {
        "eyebrow": "MIDJOURNEY STYLES · SREF CODES",
        "lead": "Midjourney 风格名与风格参考码（SREF）的中文索引。每条都附一行可复制的提示词"
                "与示例图——先看图，再决定要不要把码粘进 Midjourney。",
        "search": "搜索风格名、提示词或 SREF 码",
        "searchEmpty": "没有匹配的条目",
        "allKinds": "全部",
        "allCats": "全部分类",
        "count": "%s 条",
        "copy": "复制",
        "copied": "已复制",
        "copyPrompt": "复制提示词",
        "copySref": "复制 SREF 码",
        "openOrigin": "打开原站 ↗",
        "kind": "类型",
        "cat": "分类",
        "sref": "SREF 码",
        "noImageNote": "示例图与提示词来自 Midlibrary（原站）。本站是个人学习用途的索引镜像，"
                       "署名并回链原站。",
        "emptyTitle": "这一类还没有条目",
        "loadMore": "载入更多",
        "end": "到底了",
        "badgePick": "站方精选",
        "badgePublic": "公有领域",
        "badgeTested": "已实测",
    },
    "ja": {
        "eyebrow": "MIDJOURNEY STYLES · SREF CODES",
        "lead": "Midjourney のスタイル名とスタイル参照コード（SREF）の日本語索引。"
                "各項目にそのままコピーできる一命令とサンプル画像を掲載。",
        "search": "スタイル名・プロンプト・SREF コードを検索",
        "searchEmpty": "一致する項目がありません",
        "allKinds": "すべて",
        "allCats": "すべてのカテゴリ",
        "count": "%s 件",
        "copy": "コピー",
        "copied": "コピーしました",
        "copyPrompt": "プロンプトをコピー",
        "copySref": "SREF コードをコピー",
        "openOrigin": "元サイトを開く ↗",
        "kind": "種類",
        "cat": "カテゴリ",
        "sref": "SREF コード",
        "noImageNote": "サンプル画像とプロンプトは Midlibrary（元サイト）由来です。"
                       "本サイトは学習目的のインデックスミラーで、クレジットとリンクを併記します。",
        "emptyTitle": "このカテゴリにはまだ項目がありません",
        "loadMore": "さらに読み込む",
        "end": "ここまで",
        "badgePick": "公式セレクト",
        "badgePublic": "パブリックドメイン",
        "badgeTested": "テスト済み",
    },
}

# ── SEO ─────────────────────────────────────────────
SEO = {
    "site": "midlibrary",
    "name": NAME_ZH,
    "short": "风格库",
    "kind": "Midjourney 风格与 SREF 码",
    "tagline": "Midjourney 风格名与风格参考码索引镜像",
    "licenseNote": "已获站方书面许可：允许个人学习用途的镜像（含图片），"
                   "要求署名并回链原站。素材著作权归 Midlibrary 团队与各原作者。",
    "descTail": "适合在写 Midjourney 提示词时查风格名、查 SREF 码。",
    "accent": "#b45309",
    "author": "Midlibrary 团队（JB Nina, Inc.）",
    "authorUrl": ORIGIN,
    "dlFormat": "WebP",
    "factSource": "样例图由 Midlibrary 团队用 Midjourney 生成",
    "expandSeries": [],
    "skipSeries": [],
}

FAQ = [
    ("这个站是做什么的？",
     "它是 Midjourney 风格名与风格参考码（SREF）的索引：每条给出可复制的一行提示词、"
     "所属分类与示例图，方便先看图再决定要不要用这个码。"),
    ("SREF 码怎么用？",
     "复制条目上的 --sref 数字码，粘在自己提示词的末尾即可，例如 "
     "--sref 3383230063 --v 8.2。码与提示词都可以用于你自己的作品，包括商业用途。"),
    ("示例图是谁的？",
     "示例图由 Midlibrary 团队用 Midjourney 生成，版权归他们所有；"
     "经站方书面许可，本站以署名加回链的方式镜像，供个人学习与检索使用。"),
    ("数据是实时的吗？",
     "不是。数据是采集当天的快照，站方新增的条目不会自动出现在本站，"
     "需要重跑采集脚本才会更新。"),
]

SEO_PAGES = {
    "introParas": lambda n, m: [
        "这是 Midlibrary 的中文索引：收录 {:,} 条 Midjourney 风格条目与风格参考码，"
        "每条附可复制的一行提示词与示例图。".format(n),
        "数据来自站方在许可范围内的公开页面，采集当天的快照。"
        "码与提示词可以自由使用；示例图请配合署名与回链原站。",
    ],
    "faq": FAQ,
}

CONFIG = {
    "code": CODE,
    "source": SOURCE,
    "origin": ORIGIN,
    # 构建脚本读环境变量 SITE_URL；这里给仓库内的默认（CI 用 example.com 口径）
    "siteUrl": os.environ.get("SITE_URL", "https://example.com/midlibrary"),
    **SEO,
    "ui": UI,
    "seoPages": SEO_PAGES,
    "categoryZh": CATEGORY_ZH,
    "categoryJa": CATEGORY_JA,
    "kindZh": KIND_ZH,
    "kindJa": KIND_JA,
    "storageKey": "mld",
}
