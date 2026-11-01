# -*- coding: utf-8 -*-
"""PromptHero Midjourney 站配置。

站点 id：prompthero-midjourney
数据源：PromptHero 的 Midjourney 提示词集（prompthero.com/midjourney-prompts）
授权：restricted —— 上游素材由用户众包上传，TOS 只授予 PromptHero 永久分发权，
      未授予第三方再分发权。本站为个人学习用途的中文索引镜像，禁止再分发，
      引用须回链原站。

采集端点与代理配置放在这里，scripts/extract.py 与 scripts/manifest.py 共用。
"""
import os

# ── 采集 ────────────────────────────────────────────
API = "https://prompthero.com/api/trpc/prompt.search"
MODEL = "Midjourney"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
X_HEADERS = {"User-Agent": UA, "x-trpc-source": "nextjs-react"}
# 图源与接口在国内需要出口 IP 时设 FETCH_PROXY / PROXY
PROXY = os.environ.get("FETCH_PROXY", "")

# ── 站点身份 ─────────────────────────────────────────
CODE = "PROMPTHERO-MJ-01"
SOURCE = "https://prompthero.com/midjourney-prompts"
ORIGIN = "https://prompthero.com"

# 图片分两个域名：衍生图在 img（原图 CDN），原图在 cdn
IMAGE_BASES = [
    "https://img.prompthero.com/",
    "https://cdn.prompthero.com/",
]

# ── 分面中文名 ───────────────────────────────────────
CATEGORY_ZH = {
    "portraits": "人像",
    "photography": "摄影",
    "concept-art": "概念艺术",
    "character-design": "角色设计",
    "anime": "动漫",
    "fashion": "时尚",
    "landscapes": "风景",
    "interior-design": "室内设计",
    "architecture": "建筑",
    "3d-renders": "3D 渲染",
    "logo-icon-design": "标志与图标",
    "uncategorized": "未分类",
    "nsfw": "成人内容",
    "nsfw-good": "成人内容（精选）",
}

VERSION_ZH = {
    "1": "v1", "2": "v2", "3": "v3", "4": "v4", "5": "v5",
    "5.1": "v5.1", "5.2": "v5.2", "6": "v6", "6.1": "v6.1", "7": "v7",
    "Niji Mode": "Niji 模式", "Niji V6": "Niji v6",
}

# ── SEO ──────────────────────────────────────────────
SEO = {
    "title": "AI 绘画 Midjourney 提示词参考集：12,998 条提示词与成图 · PromptHero 镜像",
    "desc": "Midjourney 提示词与成图对照集：12,998 条提示词，覆盖 v1–v7 与 Niji，"
            "按人像、摄影、概念艺术、角色设计等 14 个分类筛选，含成人内容分区（默认模糊）。",
    "ogSite": "PromptHero Midjourney PROMPTHERO-MJ-01",
    "ogTitle": "Midjourney 提示词参考集 · 12,998 条提示词与成图",
    "ogDesc": "Midjourney 提示词与成图对照，可按分类、版本筛选；成人内容分区默认模糊。",
    "twTitle": "Midjourney 提示词参考集 · 12,998 条",
    "twDesc": "Midjourney 提示词与成图对照集，按分类与版本筛选。",
    "schemaName": "PromptHero Midjourney 提示词集 PROMPTHERO-MJ-01",
    "schemaAlt": "PromptHero Midjourney prompts 中文索引",
    "schemaAbout": "AI 绘画・Midjourney 提示词与参考成图",
}

# ── 界面文案（中 / 日双语）───────────────────────────
UI = {
    "zh": {
        "title": SEO["title"],
        "home": "参考素材库", "homeAria": "返回参考素材库首页",
        "eyebrow": "PROMPTHERO-MJ-01 · MIDJOURNEY 提示词与成图 · 本地镜像",
        "brand1": "PromptHero",
        "brand2": "Midjourney 提示词",
        "sub1": "12,998 条 Midjourney 提示词与对应成图，按分类与版本筛选，灯箱内可复制提示词原文。",
        "sub2": "成人内容分区默认模糊，点开单张或用页头开关查看清晰图。",
        "statPrompt": "提示词", "statImg": "成图", "statCat": "分类", "statVer": "版本",
        "all": "全部",
        "search": "搜索提示词内容",
        "filter": "筛选",
        "catAll": "全部分类",
        "verAll": "全部版本",
        "sortFav": "按收藏", "sortNew": "按最新", "sortView": "按浏览",
        "countImg": "{n} 条提示词",
        "emptyTitle": "没有匹配的提示词",
        "emptyDesc": "换个关键词，或把筛选条件放宽一些。",
        "kCat": "分类", "kVer": "版本", "kFav": "收藏", "kView": "浏览",
        "copyPrompt": "复制提示词", "copied": "已复制", "copyFail": "复制失败",
        "openOrigin": "打开原站", "dlFull": "下载原图",
        "hint": "<kbd>←</kbd><kbd>→</kbd> 翻页　<kbd>Esc</kbd> 关闭",
        "footer": "素材来源：<a href=\"https://prompthero.com/midjourney-prompts\" target=\"_blank\" rel=\"noopener noreferrer\">PromptHero</a>（PROMPTHERO-MJ-01）。"
                  "素材由用户上传，版权归各原作者；本站为个人学习用途的中文索引镜像，请勿再分发图片文件本身，引用请回链原站。",
        "themeLight": "浅色", "themeDark": "深色",
        "langJa": "日本語", "langZh": "中文",
        "themeAria": "主题", "langAria": "语言",
        "blurOff": "取消模糊", "blurOn": "恢复模糊", "blurTap": "点开查看",
        "nsfwBadge": "成人内容",
    },
    "ja": {
        "title": "Midjourney プロンプト参考集：12,998 件のプロンプトと生成画像 · PromptHero ミラー",
        "home": "参照素材集", "homeAria": "参照素材集のトップへ",
        "eyebrow": "PROMPTHERO-MJ-01 · MIDJOURNEY プロンプトと生成画像 · ミラー",
        "brand1": "PromptHero",
        "brand2": "Midjourney プロンプト",
        "sub1": "Midjourney のプロンプト 12,998 件と生成画像の対照集。カテゴリとバージョンで絞り込め、ライトボックスで原文をコピーできます。",
        "sub2": "成人向けカテゴリは初期状態でぼかし表示。個別にタップするかヘッダーのスイッチで解除できます。",
        "statPrompt": "プロンプト", "statImg": "画像", "statCat": "カテゴリ", "statVer": "バージョン",
        "all": "すべて",
        "search": "プロンプト本文を検索",
        "filter": "絞り込み",
        "catAll": "すべてのカテゴリ",
        "verAll": "すべてのバージョン",
        "sortFav": "お気に入り順", "sortNew": "新着順", "sortView": "閲覧順",
        "countImg": "{n} 件のプロンプト",
        "emptyTitle": "条件に合うプロンプトがありません",
        "emptyDesc": "キーワードを変えるか、絞り込みを緩めてください。",
        "kCat": "カテゴリ", "kVer": "バージョン", "kFav": "お気に入り", "kView": "閲覧",
        "copyPrompt": "プロンプトをコピー", "copied": "コピーしました", "copyFail": "コピー失敗",
        "openOrigin": "元サイトを開く", "dlFull": "原寸画像をダウンロード",
        "hint": "<kbd>←</kbd><kbd>→</kbd> ページ　<kbd>Esc</kbd> 閉じる",
        "footer": "素材元：<a href=\"https://prompthero.com/midjourney-prompts\" target=\"_blank\" rel=\"noopener noreferrer\">PromptHero</a>（PROMPTHERO-MJ-01）。"
                  "素材はユーザー投稿で著作権は各作者に帰属します。本サイトは個人学習用の中国語ミラーであり、画像の再配布はご遠慮ください。引用時は元サイトへリンクしてください。",
        "themeLight": "ライト", "themeDark": "ダーク",
        "langJa": "日本語", "langZh": "中文",
        "themeAria": "表示テーマ", "langAria": "言語",
        "blurOff": "ぼかしを解除", "blurOn": "ぼかす", "blurTap": "タップで表示",
        "nsfwBadge": "成人向け",
    },
}

FAQ = [
    ("这些提示词是真人写的吗？",
     "不是。提示词由 PromptHero 社区用户上传，多为 Midjourney 生成时使用的英文提示词，"
     "本站未做改写，只做索引与中文化界面。"),
    ("可以商用吗？",
     "本站素材版权归各上传者所有。上游服务条款只把分发权授予 PromptHero 平台，"
     "未授予第三方再分发权，因此本站仅供个人学习与参考；公开引用请回链原站。"),
    ("怎么用这些提示词？",
     "灯箱里可以直接复制提示词原文（含 --ar、--stylize 等参数），"
     "粘贴进 Midjourney 的提示词框即可。成图只是效果参考，不是唯一答案。"),
    ("成人内容为什么是模糊的？",
     "带「成人内容」标记的条目默认模糊，点开单张或用页头开关可以查看清晰图。"
     "这些条目不生成静态落地页，也不出现在 sitemap 里。"),
    ("和原站是什么关系？",
     "原站是英文站，条目按模型与热度分页。本站把它整理成可按分类、版本筛选的画廊，"
     "并补齐中文界面与主题切换；提示词原文保持不变。"),
]

# ── SEO 落地页配置 ───────────────────────────────────
# adult 为真：这些分类不生成静态落地页，也不进 sitemap（避免被搜索引擎直接收录）
ADULT_CATEGORIES = {"nsfw", "nsfw-good"}

SEO_PAGES = {
    "id": "prompthero-midjourney",
    "name": "Midjourney 提示词集",
    "short": "提示词",
    "kind": "提示词与成图",
    "tagline": "Midjourney 提示词与成图参考集",
    "licenseNote": "素材由用户上传，版权归各原作者；本站为个人学习用途的镜像，禁止再分发图片文件本身。",
    "descTail": "适合作为 Midjourney 出图时的提示词参考。",
    "accent": "#c2410c",
    "author": "PromptHero 社区",
    "authorUrl": ORIGIN,
    "dlFormat": "PNG",
    "factSource": "AI 生成，用户上传至 PromptHero",
    "expandSeries": [],
    "skipSeries": [],
    "introParas": lambda n, m: [
        f"这是一个 Midjourney 提示词与成图对照集：收录 {n} 条提示词，每条都配有对应的生成图，"
        "覆盖 v1 到 v7 以及 Niji 模式，可按分类与版本筛选。",
        "提示词原文保持英文原样（含 --ar、--stylize 等参数），灯箱内可直接复制；"
        "带「成人内容」标记的条目默认模糊，且不生成可被搜索引擎收录的页面。"],
    "faq": FAQ,
}

CONFIG = {
    "code": CODE,
    "source": SOURCE,
    **SEO,
    "ui": UI,
    "seoPages": SEO_PAGES,
    "categoryZh": CATEGORY_ZH,
    "versionZh": VERSION_ZH,
    "adultCategories": sorted(ADULT_CATEGORIES),
    "storageKey": "ph",
}
