# -*- coding: utf-8 -*-
"""Midjourney Explore（官方探索榜）站点配置。

站点 id：midjourney-explore
数据源：Midjourney 官网 Explore 榜（https://www.midjourney.com/explore?tab=styles_top）
授权：restricted —— 官网 Explore 展示的是社区公开作品，版权归各作者；
      Midjourney 服务条款未授予第三方再分发权。本站为个人学习用途的中文索引镜像，
      禁止再分发图片文件本身，引用须回链原站。

采集端点与代理配置放在这里，scripts/extract.py 与 scripts/manifest.py 共用。

关于「内容类型」与 tab（2026-11-02 更正）：
    Explore 页是**两个维度的组合**，不是一个扁平的 tab 列表：
      · 排序（左侧 / 顶部）：For You / Random / Hot / Top day|week|month / Likes
      · 内容类型（右上角）：Images / Videos / **Styles**
    本站的 feed=top 只覆盖「Images 内容类型 + Top day 排序」这一格。

    **Styles 是一个独立的内容类型，没有被本站在采集**（已确认，见下）：
    它是 Style Explorer，展示的是 Style Reference code（风格码，如 2918660786）
    以及每个码对应的一组示例图，与「作业 + 4 格成图」的数据结构完全不同。
    官方文档《Website Overview》原文：「Open the Explore page and click the
    Styles tab in the top-right corner」，可按 Random / Popular 排序、按词模糊搜索。

    ⚠️ 旧结论已作废：本文件此前记载「tab 全部走同一个接口，官网没有独立于热门榜的
    风格榜数据源」。该结论**不成立** —— 当初的实测是把 URL 里的 `?tab=` 换成
    styles_* 看 HTML 字节是否一致，但 `?tab=` 是前端路由参数，SPA 返回同一份 shell
    是正常行为，推不出「没有独立数据源」。

    ✅ 2026-11-02 22:50 登录态实测（WorkBuddy 浏览器扩展，账号 u9468435175）：
    `https://www.midjourney.com/explore?tab=styles_top` 确实是一个可用的数据页 ——
    右上角 Styles 开关高亮，顶部排序只有 Top day / Likes，内容区是风格卡片：
    每卡 = `/styles/0_<code>` 链接 + 文案 `sref <code>` + 3 张示例图。
    点开浮层只有 `sref <code>` 与 Try style / Copy / Search / Style Creator / Like
    五个操作，**没有作者、没有提示词、没有标签**。

    ⚠️ 第二个作废结论：此前本文件记载「`?tab=styles_top` 已返回普通图片网格，该 tab
    值已被上游当默认图片流处理」。错因是**未登录**——上游对匿名请求把 styles 流降级
    成图片流（返回 /jobs/<uuid> 列表，顶部只有 Top day / Images / Videos），登录后
    即正常。所以用 WebFetch（无登录态）抓这个 URL，看到的永远是降级结果。

    ✅ 2026-11-02 23:40 端点与可行性已定案（结论：**不做**）：
      · 端点不是 `/api/explore` 换 `feed` —— 实测 5 个 feed 取值返回**逐字节相同**
        （77943 字节、同一 id MD5），证明 `/api/explore` 根本不认 feed。
      · 真实端点是 **`/api/explore-srefs`**（bundle 里两个独立取数函数：
        `explore-srefs` 给 Styles、`explore` 给 Images）。
        feed 合法取值：`styles_random` / `styles_hot` / `styles_top` /
        `styles_top_week` / `styles_top_month`。
      · **硬门槛：必须登录态**。前端代码里 `if (auth.status === "authenticated")`
        才把 styles tab 映射到 `type:"styles"`，匿名分支直接是 `type:"explore"`
        （图片流），不看 tab。匿名调 `explore-srefs` 一律 500，
        `explore-styles-likes` / `styles-vector-search` 一律 401；
        `/styles/<code>` 详情页是纯 shell，无 SSR 数据 —— 三条旁路全封。
      · ⇒ 匿名定时任务拿不到 Styles。做它就得维护会过期的登录 cookie，
        失败是无声的，比不做更糟；且该数据只有码 + 示例图，无提示词/作者/标签。
      · 风格码不需要这条线也有：图片流每条作业的 `prompt.styleRef` 自带
        （`t=="seed"` 的 content 即码），`style_refs()` 已正确提取。
      详见 docs/STYLES_FEASIBILITY.md（含三重证据与两轮误判复盘）。
"""
import os

# ── 采集 ────────────────────────────────────────────
# Explore 榜的匿名只读接口。page 从 0 开始；feed 固定为 top。
API = "https://www.midjourney.com/api/explore"
FEED = "top"
PAGE_START = 0
# 实测公开榜单在 page=4 处返回空数组，即 4 页 × 50 条 = 200 条作业。
PAGE_COUNT = 4
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
# 图源与接口需要出口 IP 时设 FETCH_PROXY / PROXY
PROXY = os.environ.get("FETCH_PROXY", "")

# ── 站点身份 ─────────────────────────────────────────
CODE = "MJ-EXPLORE-01"
SOURCE = "https://www.midjourney.com/explore?tab=top"
ORIGIN = "https://www.midjourney.com"

# 图片 CDN：每条作业的每一格图，路径为 {job_id}/{index}_{size}_N.webp
IMAGE_BASES = [
    "https://cdn.midjourney.com/",
]

# ── 分面中文名 ───────────────────────────────────────
# 官网 Explore 榜不提供官方分类，改为按「提示词里的 --ar 宽高比」与「画幅」分面，
# 这是 Explore 榜上唯一稳定可枚举的结构化维度。
ASPECT_ZH = {
    "1:1": "正方形 1:1",
    "2:3": "竖版 2:3",
    "3:2": "横版 3:2",
    "4:5": "竖版 4:5",
    "5:4": "横版 5:4",
    "9:16": "竖版 9:16",
    "16:9": "横版 16:9",
    "3:4": "竖版 3:4",
    "4:3": "横版 4:3",
    "21:9": "超宽 21:9",
}

# ── SEO ──────────────────────────────────────────────
# 数量不再写死：站点每天累积一批，成图数/作业数每天都在涨。
# 下面的文案用 {n_images} / {n_jobs} 占位符，由 build_gallery.py 按实际数据填充
# （见 build_gallery.py 的 with_counts）。
SEO = {
    "title": "Midjourney 探索榜参考图集：{n_images} 张社区精选成图 · Midjourney Explore 镜像",
    "desc": "Midjourney 官网 Explore 榜的中文镜像：收录 {n_jobs} 条社区作业、{n_images} 张成图，"
            f"每条附原始英文提示词，可按宽高比与作者筛选，灯箱内可复制提示词原文。",
    "ogSite": f"Midjourney Explore {CODE}",
    "ogTitle": "Midjourney 探索榜 · {n_images} 张社区精选成图",
    "ogDesc": "Midjourney 官网 Explore 热门榜镜像，含英文提示词原文与宽高比分面。",
    "twTitle": "Midjourney 探索榜 · {n_images} 张",
    "twDesc": "Midjourney 官网 Explore 榜中文镜像，含提示词原文。",
    "schemaName": f"Midjourney Explore {CODE}",
    "schemaAlt": "Midjourney Explore community gallery",
    "schemaAbout": "AI 绘画・Midjourney 社区精选成图参考",
}

# ── 界面文案（中 / 日双语）───────────────────────────
UI = {
    "zh": {
        "title": SEO["title"],
        "home": "参考素材库", "homeAria": "返回参考素材库首页",
        "eyebrow": f"{CODE} · MIDJOURNEY 探索榜 · 本地镜像",
        "brand1": "Midjourney",
        "brand2": "探索榜",
        "sub1": "Midjourney 官网 Explore 热门榜的镜像：{n_jobs} 条社区作业、{n_images} 张成图，"
                "每条都附原始英文提示词，可按宽高比筛选。",
        "sub2": "榜单由官网按热度生成，与 PromptHero 提示词集不是同一批数据。",
        "statPrompt": "提示词", "statImg": "成图", "statAspect": "宽高比", "statJob": "作业",
        "all": "全部",
        "search": "搜索提示词或作者",
        "filter": "筛选",
        "aspAll": "全部宽高比",
        "batchAll": "全部日期",
        "sortHot": "按热度", "sortNew": "按最新", "sortAspect": "按宽高比",
        "countImg": "{n} 张图",
        "emptyTitle": "没有匹配的成图",
        "emptyDesc": "换个关键词，或把筛选条件放宽一些。",
        "kAspect": "宽高比", "kJob": "作业",
        "copyPrompt": "复制提示词", "copied": "已复制", "copyFail": "复制失败",
        "openOrigin": "打开原站", "dlFull": "下载原图",
        "close": "关闭", "more": "加载更多",
        "hint": "<kbd>←</kbd><kbd>→</kbd> 翻页　<kbd>Esc</kbd> 关闭",
        "footer": f"素材来源：<a href=\"{ORIGIN}/explore?tab=styles_top\" target=\"_blank\" rel=\"noopener noreferrer\">"
                  f"Midjourney Explore</a>（{CODE}）。成图由社区用户生成，版权归各原作者；"
                  "本站为个人学习用途的中文索引镜像，请勿再分发图片文件本身，引用请回链原站。",
        "themeLight": "浅色", "themeDark": "深色",
        "langJa": "日本語", "langZh": "中文",
        "themeAria": "主题", "langAria": "语言",
    },
    "ja": {
        "title": "Midjourney 探索榜：{n_images} 枚のコミュニティ精选画像 · ミラー",
        "home": "参照素材集", "homeAria": "参照素材集のトップへ",
        "eyebrow": f"{CODE} · MIDJOURNEY 探索榜 · ミラー",
        "brand1": "Midjourney",
        "brand2": "探索榜",
        "sub1": "Midjourney 公式 Explore 人気ランキングのミラー：{n_jobs} 件のコミュニティ作品、{n_images} 枚の生成画像。"
                "元 english プロンプト付き、アスペクト比で絞り込めます。",
        "sub2": "ランキングは公式が人気度から生成したもので、PromptHero のプロンプト集とは別のデータです。",
        "statPrompt": "プロンプト", "statImg": "画像", "statAspect": "アスペクト比", "statJob": "作品",
        "all": "すべて",
        "search": "プロンプト・作者を検索",
        "filter": "絞り込み",
        "aspAll": "すべてのアスペクト比",
        "batchAll": "すべての日付",
        "sortHot": "人気順", "sortNew": "新着順", "sortAspect": "アスペクト比順",
        "countImg": "{n} 枚",
        "emptyTitle": "条件に合う画像がありません",
        "emptyDesc": "キーワードを変えるか、絞り込みを緩めてください。",
        "kAspect": "アスペクト比", "kJob": "作品",
        "copyPrompt": "プロンプトをコピー", "copied": "コピーしました", "copyFail": "コピー失敗",
        "openOrigin": "元サイトを開く", "dlFull": "原寸画像をダウンロード",
        "close": "閉じる", "more": "さらに読み込む",
        "hint": "<kbd>←</kbd><kbd>→</kbd> ページ　<kbd>Esc</kbd> 閉じる",
        "footer": f"素材元：<a href=\"{ORIGIN}/explore?tab=styles_top\" target=\"_blank\" rel=\"noopener noreferrer\">"
                  f"Midjourney Explore</a>（{CODE}）。画像はコミュニティ投稿で著作権は各作者に帰属します。"
                  "本サイトは個人学習用の中国語ミラーであり、画像の再配布はご遠慮ください。引用時は元サイトへリンクしてください。",
        "themeLight": "ライト", "themeDark": "ダーク",
        "langJa": "日本語", "langZh": "中文",
        "themeAria": "表示テーマ", "langAria": "言語",
    },
}

FAQ = [
    ("这些图和 PromptHero 提示词集是同一批吗？",
     "不是。PromptHero 集是用户上传的提示词库；本站取的是 Midjourney 官网 Explore 热门榜，"
     "由官网按社区热度生成，作业与提示词都来自 Midjourney 本身。"),
    ("提示词为什么是英文的？",
     "Midjourney 的提示词原文就是英文，本站保持原样不做改写，只补中文界面与宽高比分面。"
     "灯箱里可以直接复制整条提示词。"),
    ("可以商用吗？",
     "成图版权归各创作者所有。Midjourney 服务条款未授予第三方再分发权，"
     "因此本站仅供个人学习与参考；公开引用请回链原站。"),
    ("榜单多久更新一次？",
     "Explore 榜由官网按实时热度排序，内容会随社区活动变化。本站的数据是采集当天的快照，"
     "重新运行 scripts/extract.py 即可拿到最新榜单。"),
    ("每条作业有几张图？",
     "每条作业 4 格，共 {n_images} 张。其中一部分格子被上游标记为不适合展示，"
     "这类格子不下载、不显示，页面上只会看到实际可用的格子。"),
]

# ── SEO 落地页配置 ───────────────────────────────────
SEO_PAGES = {
    "id": "midjourney-explore",
    "name": "Midjourney 探索榜",
    "short": "探索榜",
    "kind": "社区精选成图",
    "tagline": "Midjourney 官网 Explore 热门榜镜像",
    "licenseNote": "成图版权归各创作者；本站为个人学习用途的镜像，禁止再分发图片文件本身。",
    "descTail": "适合作为 Midjourney 出图时的风格与构图参考。",
    "accent": "#0f766e",
    "author": "Midjourney 社区",
    "authorUrl": ORIGIN,
    "dlFormat": "PNG",
    "factSource": "AI 生成，发布于 Midjourney 官网 Explore",
    "expandSeries": [],
    "skipSeries": [],
    "introParas": lambda n, m: [
        f"这是 Midjourney 官网 Explore 热门榜的中文镜像：收录 {n} 条社区作业、共 {m} 张成图，"
        "每条作业都附原始英文提示词，可按画面宽高比筛选。",
        "榜单内容由官网按社区热度实时排序，本站是采集当天的快照；"
        "提示词保持英文原样，灯箱内可直接复制。"],
    "faq": FAQ,
}

CONFIG = {
    "code": CODE,
    "source": SOURCE,
    **SEO,
    "ui": UI,
    "seoPages": SEO_PAGES,
    "aspectZh": ASPECT_ZH,
    "storageKey": "mje",
}
