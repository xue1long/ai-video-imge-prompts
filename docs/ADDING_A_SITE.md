# 加第 N 个站

新站点只要满足下面的约定，`tools/` 下的 fetch / mid / verify / build / release 都不用改。
下载和校验是共用的（`shared/assets.py`），各站不需要自己的下载或校验脚本。

## 1. 建目录

```
sites/<新站id>/
├── scripts/
│   ├── build_gallery.py    # 必填
│   ├── extract.py          # 按需：从原站存档解析 data/
│   ├── manifest.py         # 按需：data/ → manifest.json
│   └── fetch_hook.py       # 按需：图源要浏览器化请求头或 cookie 时提供
├── data/                   # 结构化数据（入库）
├── index.html              # 构建产物（入库，便于直接预览）
├── LICENSE
├── NOTICE.md               # 该站单独的授权说明
└── README.md
```

| 文件 | 约定 |
|---|---|
| `scripts/build_gallery.py` | 读环境变量 `SITE_URL`，输出 `index.html`、`data/`、`robots.txt`、`sitemap.xml`、`404.html`。站点根用 `dirname(dirname(__file__))` 自己算，不依赖当前目录 |
| `manifest.json` | 每条记录对 `sites.json` 里的每个档位 `<tier>` 都有 `<tier>_url` 和 `<tier>_path`（例如 `thumb_url` / `thumb_path`）。`tools/fetch.py` 和 `tools/verify.py` 只靠这条规则工作 |
| `scripts/fetch_hook.py` | 图源要浏览器化请求头或 cookie 时提供（见下）。没有这个文件的站点行为完全不变 |

结构和姿势集相同的站，直接复用 `shared/pose_gallery.py` 与 `shared/pose_source.py`，只写一份 `config.py`（参考 `sites/pose/config.py`）。
数据来自别的项目、系列和名称不同的，参考 `sites/shisei/config.py`：系列与视角顺序、中文名表、作者、`blurRatings`（默认模糊）都在配置里。

### 图源要 cookie 或特殊请求头时

`shared/assets.py` 默认只发 `User-Agent` 与 `Referer`。有些图源（挂在 Cloudflare 后、
要做 JS 挑战的）光这样不够。**不要为此改 `tools/`**，而是在本站放一个取图钩子：

```python
# sites/<新站id>/scripts/fetch_hook.py
def headers(url, referer):
    """追加到默认请求头之后。"""
    return {"Accept": "image/webp,*/*", "Referer": "https://example.com/"}

def prepare(opener, log):
    """可选：预热。先访问页面拿 cookie，返回带 cookie 的 opener。"""
    ...
```

`shared/assets.py` 会自动发现并调用它；没有这个文件的站点走默认路径，行为不变。

实例：`sites/midjourney-explore/scripts/fetch_hook.py` —— `cdn.midjourney.com`
必须带 Cloudflare 下发的 `__cf_bm` 通行证 cookie，否则一律 403。

## 2. 在 `sites.json` 追加一条

```json
{
  "id": "new-site",
  "code": "NEW-DB-01",
  "name": { "zh": "新站名", "ja": "新サイト名" },
  "desc": { "zh": "一句话说明。", "ja": "一文で説明。" },
  "stats": [{ "v": "1234", "l": { "zh": "图片", "ja": "画像" } }],
  "license": "cc0",
  "source": "https://new-site.pages.dev/",
  "cover": "thumbs/cover.webp",
  "coverPos": "center 30%",
  "tiers": ["thumb", "full"],
  "imageDirs": ["thumbs", "mid", "img"]
}
```

| 字段 | 说明 |
|---|---|
| `id` | 唯一标识，同时是目录名和 URL 路径 |
| `source` | 原站地址，下载时作为 Referer |
| `imageBase` | 可选。图片不在原站域名下时填写（如 Shisei 的图片在上游 GitHub 固定标签里），测试据此核对 manifest 的 URL |
| `imageBases` | 可选。图片分散在多个 CDN 域名时填列表（如 PromptHero：衍生图在 `img.prompthero.com`、原图在 `cdn.prompthero.com`），取代 `imageBase` |
| `code` | 入口页封面左下角的编号 |
| `cover` | 相对站点目录的封面路径 |
| `coverPos` | 封面框是 16:10，竖图必然裁切：脸部特写用 `25%`–`35%`，全身图用 `0%`–`10%`，主体居中用 `50%` |
| `tiers` | 下载与校验的档位，对应 manifest 里的 `<tier>_url` / `<tier>_path` |
| `imageDirs` | `release.py` 硬链接的目录；含 `mid` 时 `mid.py` 会为该站生成中图（`tiers` 里已有 `mid` 的站点由上游提供，不生成） |
| `license` | `cc0` / `conditional` / `restricted`，决定入口页卡片上的授权徽章 |

站点在入口页的顺序 = `sites.json` 数组顺序。

## 3. 测试会强制的隐含约束

`tests/run.py` 自动覆盖 `sites.json` 里的新站。下面每条不满足都会直接 fail，
写新站时先对照一遍：

| 约束 | 检查项 |
|---|---|
| canonical 必须是 `https://example.com/<id>/`，head 里不得写死正式域名 | `Pages.test_canonical_and_no_placeholder_leak` |
| `index.html` ≤ 450 KB | `Pages.test_page_size_budget` |
| 去掉 JS 与样式后可读文字 ≥ 500 字 | `Landing.test_static_intro_on_gallery_pages` |
| 恰好 1 个 `<h1>`，含 `"@type":"FAQPage"`，含 `class="seo-intro"` 与 `<details class="seo-more">` | 同上 |
| 至少 1 个静态落地页（`browse/`），分面不足 6 张不成页 | `Landing.test_every_site_has_landing_pages` |
| 落地页只用缩略图，不得出现 `/mid/` `/img/` `/png/` | `Landing.test_only_thumbnails_exposed` |
| 落地页每张 `<img>` 必须有 `alt` 且 ≥6 字符 | `Landing.test_head_and_body_basics` |
| 落地页引用的图必须在 manifest 的 `thumb_path` 里，路径层级要对 | `Landing.test_thumbs_are_in_manifest` |
| 每个 tier 都要有 `<tier>_url` / `<tier>_path`，路径用 `/`、不含 `..`、不重复 | `Manifests.test_tier_fields_present` / `test_paths_portable_and_unique` |
| 所有 URL 必须落在 `source` / `imageBase` / `imageBases` 之下 | `Manifests.test_urls_point_to_source` |
| manifest 路径顶层目录必须在 `imageDirs` 里 | `Manifests.test_image_dirs_match_paths` |
| 封面必须在 manifest 的 `thumb_path` 里 | `Manifests.test_cover_in_manifest` |
| `imageDirs` 含 `mid` 时，页面里必须有 `midOf` 函数，且与 `tools/mid.py` 的 `mid_rel` 逐条一致 | `MidRule.test_python_and_js_agree` |
| 新站的 `README.md` 与 `NOTICE.md` 必须存在，其中的相对链接不能失效 | `Docs.test_relative_links_and_anchors` |

> **数据量大的站要分片。** 单页内嵌全部数据会撞上 450 KB 上限。
> 参考 `sites/prompts/`：把数据写成 `data/gallery_<key>.js`（`JSON.parse` 赋值），
> 页面只内嵌一份小索引，进站按需加载分片。分片不入库时，CI 构建该站要加 `--skip`
> （干净检出上分片不存在，构建必然失败）——`prompts` 站就是这么处理的。
> 但如果分片**可由入库的源头数据**（如 manifest.json）一键重建，优先不 skip：
> CI 构建比对照常校验该站，闸门不缩水——`prompthero-midjourney` 站就是这么处理的。

## 4. 构建

```bash
python tools/fetch.py --site new-site
python tools/mid.py --site new-site      # imageDirs 含 mid 时
python tools/verify.py --site new-site
python tools/build.py
python tools/release.py
python tools/serve.py
python tests/run.py                      # 提交前跑一遍；CI 也会跑
```

`tests/run.py` 会自动覆盖 `sites.json` 里的新站：构建产物是否最新、重复 id、JS 引用的 id 是否存在、
内联数据是否都被页面使用、页面体积上限、manifest 的档位字段与路径、封面是否在 manifest 里。

## 5. 接入素材管理器（index/）

站点页面建好了，**不等于它进了 WebUI**。索引侧是三个独立的地方，漏改任何一处，
站点页面照样正常、CI 照样全绿，只有用户在素材管理器里查不到素材时才发现：

| 位置 | 作用 | 漏了会怎样 |
|---|---|---|
| `sites.json` | 站点清单 | 站点根本不存在 |
| `index/catalog.py` 的 `SOURCES` | 索引哪些站、字段怎么映射 | **WebUI 里查不到这个站** |
| `index/sync.py` | 索引实现 | 同步不出条目 |

```python
# index/catalog.py 的 SOURCES 里加一条
"new-site": {
    "manifest": "sites/new-site/manifest.json",
    "title": "title",
    "title_alt": None,
    "facets": {"分类": "category"},
    "files": [("thumb", "thumb_path"), ("full", "full_path")],
    "size": None,
    "bytes": None,
    "prompt": "prompt",       # 有提示词就配上；没有就留空
    "keywords": "prompt",
    "extra": {"author": "username", "source_url": "sourceUrl"},
    # 一条内容多张图的站必须声明聚合键（见下）
    # "group_by": "jobId",
    # "group_order": "index",
},
```

### 多图站：同一提示词的 N 张图要在一个灯箱里

上游一次作业出 4 格、共用一段提示词时，manifest 是 4 行、id 各不相同。
**不声明聚合键，这 4 行会变成 4 条独立素材**，WebUI 灯箱里翻不到一起。

- 声明 `group_by`：按该字段聚合成**一条**素材，组内多张图挂成它的多个 asset，
  `ordinal` = 组内顺序（灯箱翻页顺序），由 `group_order` 指定。
- 确实是「一条记录一张图、不该聚合」（如同姿势的 5 个视角在站内是独立条目）：
  声明 `split_by_design` 并写明理由。两者都不写，测试会拦下。

### 接入后必做的验证

```bash
python index/sync.py --force          # 重建索引
python index/check_wiring.py           # 核对各站条目数（CI 也跑这一步）
python tests/run.py                    # 含索引接线测试
```

`check_wiring.py` 逐站核对「实际条目数 == 按配置推算的条目数」，
`tests/run.py` 的 `IndexMapping` 核对清单、聚合声明、字段映射是否自洽。

## 6. 从原站接口采集数据（prompthero-midjourney 的经验）

数据没有现成交档、要从上游接口抓时，按这几条走，能少走弯路：

- **先抓前端 bundle 定位接口**：在 DevTools 里翻前端的 JS chunk，挖出真实的
  tRPC / GraphQL procedure 与参数形状，不要硬猜 URL 查询参数——页面上看到的
  `?page=2` 这类参数可能是摆设。
- **探测分页上限与排序稳定性**：接口往往有隐藏的 pageSize 上限（如 48）；
  凡是按排序分页，两次采集之间可能因并列漂移产生重复或丢条目——
  采集侧必须按稳定键（如 slug）做确定性去重。
- **限流退行**：批量请求先低速小批试跑，触发 429 就指数退避、后台分批补抓；
  采集统计（总条数、NSFW 数、缺失回落数）写进 `data/meta.json` 留档。
- **图片缺口的回落链**：多档位（原图 / 中图 / 缩略图）不必逐档都存在，
  manifest 里缺失的档位回落到下一档并记 fallback 标记，
  `verify.py` 保证最终每条每档都有可用文件。

上线到已有服务器的步骤见 [DEPLOY.md](../deploy/DEPLOY.md) §6。

## 设计约定

新站点请保持一致：

- 主题切换 `[☀ Light][☾ Dark]`，默认浅色
- 语言切换 `[中文][日本語]`，默认中文，中文在左
- `<head>` 内用同步脚本应用已存偏好，避免刷新闪白
- 单文件 `index.html`，数据内嵌，零外部依赖（数据量大到撑破 450 KB 上限时改为分片外置，见上文第 3 节）
- 分页加 `IntersectionObserver` 预取，不一次渲染全部卡片
- 灯箱底图用清晰缩略图，不加模糊；中图到达后淡入
- 有成人内容的站：默认模糊 + 点开单张才清晰 + 不生成落地页（参考 `sites/shisei/` 的 `blurRatings` 机制）
