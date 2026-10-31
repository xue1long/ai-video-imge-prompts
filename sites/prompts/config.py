# -*- coding: utf-8 -*-
"""提示词生图集（PROMPTS-DB-01）· 站点配置

数据源与输出路径、双语 UI 词典、SEO 落地页配置都在这里。
分面（模型 / 标签 / 画幅）由数据自动派生，不在此维护。
"""

META = {
    "title": "提示词生图集",
    "subtitle": "AI 生图提示词与成图对照 · 展示中文、复制英文原文",
    "desc": "4 万+ 张 AI 生图参考与提示词对照，覆盖 Imge-2 与 Nano Banana 两个模型，"
            "可按模型、分类、标签与画幅筛选；一条提示词的全部成图归为一条素材，展示中文提示词，一键复制英文原文。",
    "brand": "AI",
}

META_JA = {
    "title": "プロンプト素材集",
    "subtitle": "AI画像生成プロンプトと成果物の対照 · 表示は中国語、コピーは英文原文",
    "desc": "4万点超のAI生成画像とプロンプトの対照集。Imge-2 と Nano Banana の2モデルに対応し、"
            "モデル・カテゴリ・タグ・比率で絞り込めます。",
}

UI = {
    "search": "搜索提示词 / 标题 / 标签",
    "all": "全部",
    "loading": "加载中…",
    "tags": "标签",
    "aspect": "画幅",
    "model": "模型",
    "prompt": "提示词",
    "params": "参数",
    "copy": "复制提示词",
    "copied": "已复制",
    "copyFail": "复制失败",
    "close": "关闭",
    "emptyTitle": "没有匹配的结果",
    "emptyDesc": "换个关键词，或把标签筛选放宽一些。",
    "count": "<b>{n}</b> 条素材",
    "countImgs": "共 {n} 张图",
    "figure": "图",
    "themeLight": "浅色",
    "themeDark": "深色",
    "hint": "<kbd>Esc</kbd> 关闭",
    "fav": "收藏",
    "favTip": "收藏",
    "addTag": "+ 输入标签，回车添加",
    "del": "删除",
    "restore": "恢复",
    "trash": "回收站",
    "delConfirm": "确定删除这条素材？\n进入回收站，可随时恢复。",
    "remove": "移除",
    "viewSource": "查看来源 ↗",
    "shownMore": "已显示 {a} / {b} · 继续滚动加载",
    "allShown": "共 {n} 条 · 已全部显示",
    "escHint": "关闭",
    "own": "自制",
    "ownTip": "站主自己挂上去的成图，版权归本站，不在 CC BY 4.0 范围内",
    "footer": "静态单页 · 零依赖",
}

UI_JA = {
    "search": "プロンプト / タイトル / タグを検索",
    "all": "すべて",
    "loading": "読み込み中…",
    "tags": "タグ",
    "aspect": "比率",
    "model": "モデル",
    "prompt": "プロンプト",
    "params": "パラメータ",
    "copy": "プロンプトをコピー",
    "copied": "コピーしました",
    "copyFail": "コピー失敗",
    "close": "閉じる",
    "emptyTitle": "該当する結果がありません",
    "emptyDesc": "キーワードを変えるか、タグの絞り込みを緩めてください。",
    "count": "<b>{n}</b> 件",
    "countImgs": "全 {n} 枚",
    "figure": "図",
    "themeLight": "ライト",
    "themeDark": "ダーク",
    "hint": "<kbd>Esc</kbd> で閉じる",
    "fav": "お気に入り",
    "favTip": "お気に入り",
    "addTag": "+ タグを入力して Enter",
    "del": "削除",
    "restore": "復元",
    "trash": "ゴミ箱",
    "delConfirm": "この素材を削除しますか？\nゴミ箱に入るので、いつでも復元できます。",
    "remove": "削除",
    "viewSource": "出典を見る ↗",
    "shownMore": "{a} / {b} 表示 · スクロールで続きを読み込む",
    "allShown": "全 {n} 件 · すべて表示済み",
    "escHint": "閉じる",
    "own": "自作",
    "ownTip": "運営者が追加した画像。著作権は当サイトに帰属し、CC BY 4.0 の対象外です",
    "footer": "静的シングルページ · 依存ゼロ",
}

# 模型显示名（数据里 model 原值 → 页面展示名；未列出的原样显示）
MODELS = {
    "mj": "Midjourney",
    "imge-2": "Imge-2",
    "nanobanana": "Nano Banana",
}

# 进站默认加载的模型（数据里 model 原值）。数据按模型分片，默认只拉这一份。
# 必须是 MODELS 的键；对应分片缺失时退化为数据量最大的模型。
DEFAULT_MODEL = "imge-2"

# 主题色（用于链接、选中态、品牌角标）
ACCENT = "#7c5cff"

# ── 数据与输出 ────────────────────────────────────────
# 每个模型一份文本数据：data/prompts_<key>.json（import_youmind.py 产出，入库）
DATA_GLOB = "data/prompts_*.json"
DIMS = "data/dims.json"               # 图片宽高（manifest.py 生成，入库）
# 页面数据按模型分片：data/gallery_<key>.js + 轻量索引 data/gallery.js
# 分片是必须的——两个模型合起来约 170MB，单文件首屏无法接受
GALLERY_JS = "data/gallery.js"        # 索引（模型清单与计数）
GALLERY_SHARD = "data/gallery_%s.js"  # 每个模型的数据分片
OUTPUT = "index.html"

# ── 站主自己挂的图（覆盖层）──────────────────────────
# 素材管理器里「添加图片」挂到某条提示词下的成图，不属于上游素材，单独放在
# userimg/ 而不是 img/：img/<key>/ 的目录名就是模型分片键，混进去会被当成新模型；
# 而且 fetch.py 只认 manifest.json 里的文件，放进 img/ 会让「图片比清单多」变成噪声。
# 归属关系不写进 prompts_<key>.json（那是 import_youmind.py 的产物，会整份重写），
# 单独一份覆盖层，构建时按 originId 合并进对应的分片。
USER_ASSETS = "data/user_assets.json"  # 覆盖层（sync_user_assets.py 产出，入库）
USER_IMG_DIR = "userimg"               # 用户图目录（与 img/ 平级，随仓库入库）
USER_THUMB_DIR = "userimg/thumbs"      # 用户图缩略图

# ── SEO 落地页（shared/landing.py）────────────────────
SITE = {
    "name": "提示词生图集",
    "tagline": "AI 生图提示词与成图对照集，展示中文提示词、复制英文原文。",
    "license_note": "素材采用 CC BY 4.0（须署名）。",
    "author": "YouMind OpenLab 社区",
    "author_url": "https://github.com/YouMind-OpenLab/awesome-gpt-image-2",
    "source": "https://youmind.com/gpt-image-2-prompts/explore",
    "index_title": "提示词生图集 · 全部分类",
    "index_intro": "按官方分类浏览全部 AI 生图参考。每个分类页展示代表性图片与数据事实，"
                   "点击「在画廊中查看」可带着筛选条件打开完整画廊。",
    "faq": [
        ("这些提示词可以直接用吗？", "可以。每张图附带完整提示词，灯箱里一键复制英文原文；"
         "部分提示词带 Raycast 占位符，复制后把「默认值」替换成你想要的描述即可。"),
        ("提示词是中文还是英文？", "两者都有：页面上展示中文翻译方便浏览，"
         "复制到剪贴板的是英文原文（生图模型对原文的还原度更高）。"),
        ("素材可以商用吗？", "素材采用 CC BY 4.0 授权，允许商用，但必须保留作者署名。"
         "每条素材的作者与来源链接在灯箱内可见。"),
        ("「需参考图」是什么意思？", "该提示词是图生图（image-to-image）工作流，"
         "需要你另外提供参考图（人物、产品或风格图）才能复现效果。"),
    ],
}

# 落地页分类：(上游 slug, 页面标签名)。标签名 = 数据 tags 里的中文名。
# 全部 41 类都有标签分面，这里只为搜索流量最大的类目生成静态落地页。
SEO_CATEGORIES = [
    ("photography", "摄影"),
    ("social-media-post", "社交媒体帖子"),
    ("portrait-selfie", "人像·自拍"),
    ("character", "角色"),
    ("poster-flyer", "海报·传单"),
    ("illustration", "插画"),
    ("product-marketing", "产品营销"),
    ("text-typography", "文本·排版"),
    ("cinematic-film-still", "电影·电影剧照"),
    ("anime-manga", "动漫·漫画"),
    ("influencer-model", "网红·模特"),
    ("minimalism", "极简主义"),
]
