# -*- coding: utf-8 -*-
"""Midjourney 风格码库（Styles）站点配置。

站点 id：mj-styles
数据源：Midjourney 官网 Explore 的 Styles 内容类型
      （https://www.midjourney.com/explore?tab=styles_top）
授权：restricted —— 风格码与示例图是 Midjourney 社区创作者的作品，版权归各原作者；
      Midjourney 服务条款未授予第三方再分发权。本站为个人学习用途的中文索引镜像，
      禁止再分发图片文件本身，引用须回链原站。

这个站与 midjourney-explore 站是**两种不同的内容类型**，不是同一份数据的两种视图：

    midjourney-explore   一条社区作业 → 四格成图 + 提示词 + 作者 + 宽高比
    mj-styles（本站）    一个风格码 → 三张语义图（人像 / 风景 / 静物），没有提示词、没有作者

两者的码表**完全不相交**（实测 329 vs 45，交集 0），所以拆成两个站而不是同一站的两个视图。
详见 docs/STYLES_FEASIBILITY.md §11–§13。

采集链路（三步，见 scripts/ 各文件头部）：
    1. dump_styles.py    抓清单（**必须登录态**，只能在页面上下文里调，见该文件头）
    2. fetch_styles.py   下图（CDN 匿名可下，但要先拿 Cloudflare 通行证）
    3. build_gallery.py  构建页面（robots / sitemap / 404 / 落地页 / og-cover）
"""
import os

# ── 站点身份 ─────────────────────────────────────────
CODE = "MJ-STYLES-01"
SOURCE = "https://www.midjourney.com/explore?tab=styles_top"
ORIGIN = "https://www.midjourney.com"

# 图片 CDN：风格示例图，路径为 styles/0_<码>/<类型>_<尺寸>_N.webp
IMAGE_BASES = [
    "https://cdn.midjourney.com/",
]

# ── 采集 ──────────────────────────────────────────────
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
# 图源需要出口 IP 时设 FETCH_PROXY / PROXY
PROXY = os.environ.get("FETCH_PROXY", "")

# ── 风格码的三种语义图 ────────────────────────────────
# 原站每个风格码固定给三张示例图，用来展示这套视觉语言在不同构图下的样子。
# 顺序即网格与灯箱里的顺序（人像 → 风景 → 静物）。
KINDS = ("portrait", "landscape", "still_life")
KIND_ZH = {"portrait": "人像", "landscape": "风景", "still_life": "静物"}
KIND_SLUG = {"portrait": "portrait", "landscape": "landscape", "still_life": "still-life"}

# ── 落地页分面 ────────────────────────────────────────
# 风格码本身没有可枚举的分类（原站只有搜索框，没有分类标签）。
# 唯一稳定的分组维度是「这张示例图属于哪种构图」——按它分三组落地页。
FACET_GROUP = "按示例图类型"

# ── SEO ──────────────────────────────────────────────
# 数量用 {n_codes} / {n_shots} 占位符，由 build_gallery.py 按实际数据填充。
SEO = {
    "title": "Midjourney 风格码库：{n_codes} 个 --sref 风格码，附人像 / 风景 / 静物三张示例图",
    "desc": "Midjourney 官网 Explore Styles 榜单的风格码索引：{n_codes} 个码，"
            "每个码附人像 / 风景 / 静物三张示例图，可一键复制 --sref 参数。",
    "ogSite": f"Midjourney Styles {CODE}",
    "ogTitle": "Midjourney 风格码库 · {n_codes} 个 --sref 码",
    "ogDesc": "Midjourney 官网 Explore Styles 榜单镜像：一码三张语义示例图，可复制 --sref。",
    "twTitle": "Midjourney 风格码库 · {n_codes} 个码",
    "twDesc": "Midjourney 风格码（--sref）索引，附三种构图的示例图。",
    "schemaName": f"Midjourney Styles {CODE}",
    "schemaAlt": "Midjourney style reference codes gallery",
    "schemaAbout": "AI 绘画・Midjourney 风格参考码",
}

# ── 界面文案 ─────────────────────────────────────────
UI = {
    "zh": {
        "name": "Midjourney 风格码库",
        "eyebrow": f"{CODE} · MIDJOURNEY STYLES · 本地镜像",
        "tagline": "Midjourney 风格码（--sref）索引，一码三张示例图",
        "licenseNote": "风格码与示例图版权归各原作者，Midjourney 服务条款未授予第三方再分发权；"
                       "本站仅供个人学习与参考。",
        "author": "Midjourney 社区",
        "authorUrl": "https://www.midjourney.com/explore?tab=styles_top",
        "lead": "原站 Styles 榜单里的风格码，即提示词里 --sref 后面那串数字。"
                "每个码附人像 / 风景 / 静物三张示例图，用来判断这套视觉语言长什么样。",
        "lead2": "这些条目在原站本身就不带提示词，也没有作者——它不是一条作业，"
                 "而是一套可复用的视觉语言。",
        "codeLabel": "风格码",
        "shotLabel": "示例图",
        "kindLabel": "构图",
        "copyAll": "复制全部码",
        "searchPlaceholder": "搜码（任意几位数字）",
        "onlyNew": "只看最近新增",
        "empty": "没有匹配的码。",
        "backHome": "← 参考素材库",
        "notFound": "这个页面不存在。",
        "backSite": "← 回到风格码库",
        "facts": [
            ("风格码", "{n_codes} 个"),
            ("示例图", "{n_shots} 张"),
            ("构图类型", "3 种"),
            ("授权", "禁止再分发"),
        ],
    },
}

# ── 落地页与 FAQ ─────────────────────────────────────
FAQ = [
    ("什么是风格码（--sref）？",
     "风格码是 Midjourney 的一串数字标识，写作 --sref 1234567890，"
     "贴进提示词即可套用该作者的视觉语言。原站 Styles 榜单把公开的风格码列了出来，"
     "本站把这份清单镜像下来。"),
    ("每个码为什么是三张图？",
     "原站给每个风格码固定配三张示例图：人像、风景、静物。"
     "这三张不是三次不同的创作，而是同一套风格在不同构图下的样子——"
     "看人像看光影，看风景看空间，看静物看材质。"),
    ("怎么使用这些码？",
     "复制页面上的 --sref <码>，贴到 Midjourney 提示词末尾即可。"
     "例如 --sref 3441803824，也可以叠加权重 --sref 3441803824::2。"),
    ("这些风格码是谁做的？",
     "风格码由 Midjourney 社区创作者创作并公开在 Styles 榜单上，著作权归各原作者。"
     "本站只做索引与展示，不重新分发图片文件。"),
    ("和 Explore 热门榜是同一批东西吗？",
     "不是。热门榜收录的是社区作业（一条作业四格成图、带提示词与作者），"
     "Styles 榜单收录的是风格码（一个码三张示例图、没有提示词也没有作者）。"
     "两者的码表完全不相交，本站只镜像后者。"),
]
