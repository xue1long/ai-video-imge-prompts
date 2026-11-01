# 加第 N 个站

新站点只要满足下面的约定，`tools/` 下的 fetch / mid / verify / build / release 都不用改。
下载和校验是共用的（`shared/assets.py`），各站不需要自己的下载或校验脚本。

## 1. 建目录

```
sites/<新站id>/
├── scripts/
│   ├── build_gallery.py    # 必填
│   ├── extract.py          # 按需：从原站存档解析 data/
│   └── manifest.py         # 按需：data/ → manifest.json
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

结构和姿势集相同的站，直接复用 `shared/pose_gallery.py` 与 `shared/pose_source.py`，只写一份 `config.py`（参考 `sites/pose/config.py`）。
数据来自别的项目、系列和名称不同的，参考 `sites/shisei/config.py`：系列与视角顺序、中文名表、作者、`blurRatings`（默认模糊）都在配置里。

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
