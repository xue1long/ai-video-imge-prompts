# 深度姿势集 · 中文版

**1439 张人体姿势深度图 · 288 个姿势 × 5 视角 · ControlNet 深度控制参考**

零依赖静态画廊 · 中日双语 · 双击即开

[中文](#中文) · [日本語](#日本語) · [English](#english)

> ⚠️ **授权提示**：本站素材**不是 CC0**。原站允许商用与编辑，但
> **禁止再分发图片数据，并明确禁止批量下载与自动化抓取**。
> 本仓库的下载脚本属于被禁止的行为，详见 [NOTICE.md](NOTICE.md)。

---

# 中文

## 📖 项目简介

> **深度姿势集**是 [ai-pose-depth-gallery.pages.dev](https://ai-pose-depth-gallery.pages.dev/)
> （depthポーズ集 POSE-DB-02）的中文版复刻。
>
> 原站是同作者 POSE-DB-01 姿势集的**深度图版本**——同样的 288 个姿势、1439 张图，
> 但把线稿换成了灰度深度图：**越白表示越靠近镜头**。
>
> 用途是给 ControlNet 的 depth 预处理器、3D 建模与布光提供前后遮挡关系参考。

原作者：ギア（[@giaaibusi](https://x.com/giaaibusi)）

## ✨ 核心特性

- 🌫️ **1439 张深度图**：灰度表示远近，白色为近景
- 🎯 **288 个姿势**：每个姿势提供正面・俯视・仰视・侧面・斜角 5 个视角
- 🗂️ **4 个系列**：全身单人・性感系 399 / 全身单人・标准系 365 / 上半身单人 400 / 双人交缠 275
- 🏷️ **26 个分类**：站立、坐姿、跪姿、卧姿、特殊姿势等
- 📄 **分页加载**：每页 60 组，滚动预取 800px 自动追加
- 🖼️ **灯箱**：先显示清晰缩略图，再淡入中图（约 10 KB，WebP），悬停卡片时预取；`←` `→` 翻页，`Esc` 关闭
- ⬇️ **下载原图**：卡片与灯箱都可直接下载原尺寸 PNG
- 🌗 **主题切换**：浅色（默认）／深色
- 🌐 **中日双语**：界面、系列名、分类名、姿势名全部双语，偏好本地记忆
- 📦 **零依赖**：单个 HTML，数据内嵌，`file://` 双击即开

## 📊 数据规模

| 系列 | 姿势数 | 图片数 |
|---|---:|---:|
| 全身单人・性感系 | 80 | 399 |
| 全身单人・标准系 | 73 | 365 |
| 上半身单人 | 80 | 400 |
| 双人交缠 | 55 | 275 |
| **合计** | **288** | **1439** |

| 视角 | 正面 | 俯视 | 仰视 | 侧面 | 斜角 |
|---|---:|---:|---:|---:|---:|
| 张数 | 288 | 288 | 287 | 288 | 288 |

| 规格 | 缩略图 | 中图（灯箱） | 原图（下载） |
|---|---|---|---|
| 格式 | JPEG（灰度） | WebP（灰度） | PNG（灰度） |
| 尺寸 | 300×400 | 900×1200 | 900×1200 |
| 体积 | 12.2 MB | 约 14 MB | 133.0 MB |

> 中图不由本站脚本下载，在单仓根目录用 `python tools/mid.py` 从原图生成（最长边 1600px，WebP 质量 82）。
> 没有中图时灯箱退回加载原图。

## 🛠️ 技术栈

原生 HTML / CSS / JS，无框架、无构建、无 npm 依赖。用到的浏览器能力：

`CSS 自定义属性` · `IntersectionObserver`（分页预取）· `localStorage`（主题与语言偏好）· `aspect-ratio`（防布局抖动）

**刻意不使用**：React / Vue、打包工具、CDN、外部字体、任何第三方库。

## 📁 项目结构

```
.
├── index.html              # 单页画廊（数据内嵌，file:// 可直开）
├── config.py               # 本站文案、SEO 与原站域名
├── robots.txt / sitemap.xml / 404.html
├── og-cover.jpg            # 1200×630 社交分享封面
├── manifest.json / .csv    # 全量清单（含原站 URL 与本地路径）
├── data/
│   ├── pose.json           # 原始日文数据（1439 条）
│   ├── pose-zh.json        # 中文数据（含日中对照字段）
│   ├── meta.json           # 系列 / 分类 / 视角元数据
│   └── translations.csv    # 日⇄中对照表
├── scripts/
│   ├── extract.py          # 从原站存档解析数据（逻辑在 shared/pose_source.py）
│   ├── manifest.py         # 生成清单（同上，域名取 config.py）
│   └── build_gallery.py    # 构建入口，页面由 shared/pose_gallery.py 生成
├── thumbs/                 # 缩略图（gitignored）
├── mid/                    # 中图，由 tools/mid.py 生成（gitignored）
├── img/                    # 原图（gitignored）
└── raw/                    # 原站存档（gitignored）
```

## 🚀 快速开始

本站是 [ai-image-gallery](../../README.md) 单仓的一部分，下载、构建、发布都在仓库根目录用统一工具完成：

```bash
git clone https://github.com/xue1long/ai-video-imge-prompts.git
cd ai-image-gallery

python tools/fetch.py --site pose-depth --tier thumb    # 缩略图 300×400，约 12 MB
python tools/fetch.py --site pose-depth --tier full     # 原图 PNG，约 133 MB
python tools/mid.py --site pose-depth                   # 灯箱中图（需要 Pillow）
python tools/verify.py --site pose-depth                # 校验图片完整性
python tools/build.py --site pose-depth
python tools/serve.py --root sites/pose-depth           # 本地预览
```

## ⚙️ 环境要求

| 环境 | 版本 |
|---|---|
| Python | 3.8+（运行脚本） |
| 浏览器 | 任意现代浏览器 |
| 磁盘 | 12 MB（仅缩略图）/ 145 MB（含原图） |
| 网络 | 仅首次下载需要 |

## 📦 生产部署

各站一起发布到同一个 `dist/`，部署、nginx、原子切换与回滚见单仓的 [deploy/DEPLOY.md](../../deploy/DEPLOY.md)。

```bash
python tools/build.py --base https://your-domain.com   # canonical / og:url / sitemap 使用正式域名
python tools/release.py --out dist-stage               # 发布前会自动校验图片
```

## 🗄️ 数据结构

`data/pose-zh.json` 每条记录：

| 字段 | 说明 | 示例 |
|---|---|---|
| `id` | 唯一标识 | `full_sexy_P001_front` |
| `系列` / `系列_zh` | 系列名 | 全身1人・セクシー系 / 全身单人・性感系 |
| `分类` / `分类_zh` | 分类 | 立ち / 站立 |
| `编号` | 姿势编号 | P001 |
| `姿势名` / `姿势名_zh` | 姿势描述 | S字立ち・腰を横に突き出す / S 形站姿・胯部侧顶 |
| `视角` / `视角_zh` | 视角 | 正面 / 正面 |
| `缩略图` / `原图` | 相对路径 | `thumbs/.../正面.jpg` |

## 🔒 版权与许可

| 内容 | 许可 |
|---|---|
| 代码 | **MIT** |
| 图片素材 | **有条件的免费使用**（商用/编辑 OK，**禁止再分发与批量下载**） |
| 中文译文 | **CC BY 4.0** |

详见 [NOTICE.md](NOTICE.md)。

## 🐛 常见问题

| 问题 | 原因 | 解决 |
|---|---|---|
| 打开是空白卡片 | 图片未下载 | 先跑 `download.py` |
| 图片看起来全灰 | 这是深度图，白=近、黑=远 | 正常现象 |
| 手指/交叠处边界模糊 | 深度图只表达前后遮挡 | 原站已注明该局限 |
| 主题不跟随 | 已改为手动切换，默认浅色 | 点右上角 ☀/☾ |

## 📝 更新日志

| 日期 | 变更 |
|---|---|
| 2026-10-30 | 初版：1439 条元数据镜像、分页画廊、中日双语、浅深主题 |

## 📄 开源协议

代码 [MIT](LICENSE) · 素材按原站条件使用（非 CC0）· 译文 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.zh)

## 💡 致谢

- 原始素材与数据：ギア（[@giaaibusi](https://x.com/giaaibusi)）
- 同系列：POSE-DB-01 姿势集（线稿版）、COSTUME-DB-01 服装集

---

# 日本語

## 📖 概要

> [ai-pose-depth-gallery.pages.dev](https://ai-pose-depth-gallery.pages.dev/) の中国語版です。
> 同作者の POSE-DB-01 ポーズ集の**深度マップ版**で、同じ 288 ポーズ・1439 枚を
> グレースケールの depth に置き換えたものです。白いほど手前を表します。

原作者：ギア（[@giaaibusi](https://x.com/giaaibusi)）

## ✨ 主な機能

- 🌫️ **1439 枚の深度マップ**（白＝手前）
- 🎯 **288 ポーズ** × 5 アングル（正面・上から・下から・横・斜め）
- 🗂️ **4 シリーズ** / 🏷️ **26 分類**
- 📄 **ページング**：60 枚ずつ、800px 手前で自動追加
- 🖼️ **ライトボックス**：鮮明なサムネを先に表示し、中サイズ WebP をフェードイン（ホバーで先読み）
- ⬇️ **原寸ダウンロード**：カードからもライトボックスからも
- 🌗 **テーマ切替**（ライト既定）／🌐 **中日 2 言語**

## 📊 データ規模

| シリーズ | ポーズ | 画像 |
|---|---:|---:|
| 全身1人・セクシー系 | 80 | 399 |
| 全身1人・標準系 | 73 | 365 |
| 上半身1人 | 80 | 400 |
| 2人絡み | 55 | 275 |
| **合計** | **288** | **1439** |

## 🔒 ライセンス

| 内容 | ライセンス |
|---|---|
| コード | MIT |
| 画像 | 条件付き無償利用（商用・編集 OK、**再配布と一括ダウンロードは禁止**） |
| 中国語訳 | CC BY 4.0 |

> 原站は「画像データそのものの再配布・転載・再販」と
> 「一括ダウンロード（ツール等による自動取得を含む）」を明確に禁止しています。
> 本リポジトリのダウンロードスクリプトはこれに該当します。詳細は [NOTICE.md](NOTICE.md)。

---

# English

## 📖 Overview

> A Chinese localization of [ai-pose-depth-gallery.pages.dev](https://ai-pose-depth-gallery.pages.dev/)
> — the **depth-map edition** of the same author's POSE-DB-01 pose collection.
> Same 288 poses / 1439 images, rendered as grayscale depth maps where **brighter = closer**.
>
> Intended for ControlNet depth preprocessing, 3D modeling and lighting reference.

Original author: ギア（[@giaaibusi](https://x.com/giaaibusi)）

## ✨ Features

- 🌫️ **1439 depth maps** (white = near)
- 🎯 **288 poses** × 5 angles (front / high / low / side / diagonal)
- 🗂️ 4 series · 🏷️ 26 categories
- 📄 Pagination: 60 per page, auto-loads 800px early
- 🖼️ Lightbox shows the sharp thumbnail first, then a small WebP preview (prefetched on hover)
- ⬇️ Original PNG download from card or lightbox
- 🌗 Theme toggle (light default) · 🌐 Chinese / Japanese UI
- 📦 Zero dependencies, single HTML file

## 📊 Scale

| Series | Poses | Images |
|---|---:|---:|
| Full body · sexy | 80 | 399 |
| Full body · standard | 73 | 365 |
| Upper body | 80 | 400 |
| Two figures | 55 | 275 |
| **Total** | **288** | **1439** |

Thumbnails 300×400 JPEG (12.2 MB) · originals 900×1200 PNG (133 MB).

## 🔒 License

| Content | License |
|---|---|
| Code | MIT |
| Images | Conditional free use — commercial/edit OK, **redistribution and bulk download prohibited** |
| Chinese translations | CC BY 4.0 |

> The source site explicitly prohibits redistributing the image data and bulk downloading
> (including automated acquisition). This repository's download script falls under that
> prohibition. See [NOTICE.md](NOTICE.md).

---

## ⚠️ 内容说明

素材为**无脸部灰色人偶**的深度图，不含真实人物。
原站要求：不得用于表现真实人物或未成年人，不得用于违反公序良俗的用途。
