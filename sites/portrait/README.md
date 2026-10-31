# AI 模特脸库 · 中文版

**1499 张人脸参考图 · 893 面部 + 606 造型 · CC0 免费使用**

零依赖静态画廊 · 按发型筛选 · 中日双语 · 双击即开

[中文](#中文) · [日本語](#日本語) · [English](#english)

> ✅ **本站素材为 CC0 1.0 公有领域**，可自由商用、修改、再分发。
> 与同系列另两个图库（pose / costume）的授权性质完全不同。详见 [NOTICE.md](NOTICE.md)。

---

# 中文

## 📖 项目简介

> **AI 模特脸库**是 [ai-portrait-gallery.pages.dev](https://ai-portrait-gallery.pages.dev/) 的中文版复刻。
> 原站是一套让 AI 生成图像与视频中的角色保持同一张脸的参考图库，全站日文。
> 本项目保留其编辑风格的视觉设计与全部交互，译为中文，并移除了原站的社群推广入口。

原作者：あぎ（[@agi_aibusi](https://x.com/agi_aibusi)）

## ✨ 核心特性

- 🎯 **两个分区**：`面部`（893 张，正面、纯色背景）与 `造型`（606 张，含服装与氛围）
- 💇 **按发型筛选**：短发 727 / 中发 376 / 中长发 260 / 长发 136
- 🏷️ **50 条风格描述汉化**：日本美发术语逐条译为中文（如「くびれショート」→「内收短发」）
- 📄 **分页加载**：每页 60 张，滚动预取 800px 自动追加，与原站一致
- 🖼️ **灯箱**：先显示清晰缩略图，再淡入中图（约 115 KB，WebP），悬停卡片时预取；`←` `→` 翻页，`Esc` 关闭
- 🏷️ **卡片信息**：仅显示发型 + PNG 下载按钮，保持图片视觉占比
- ⬇️ **一键下载原图**：卡片上直接下载（带体积提示），灯箱内也可下载
- 🌗 **跟随系统深浅色**：暖纸色 / 深墨色，无需手动切换
- 🌐 **中日双语**：界面、发型名、风格描述全部双语，偏好本地记忆
- 📦 **零依赖**：单个 HTML，数据内嵌，`file://` 双击即开
- 🔗 **可分享链接**：筛选状态写入 URL hash（`#sec=styling&hair=ロング`）

## 📊 数据规模

| 分区 | 短发 | 中发 | 中长发 | 长发 | 合计 |
|---|---:|---:|---:|---:|---:|
| 面部 face | 433 | 229 | 154 | 77 | **893** |
| 造型 styling | 294 | 147 | 106 | 59 | **606** |
| **合计** | **727** | **376** | **260** | **136** | **1499** |

| 规格 | 缩略图 | 中图（灯箱） | 原图（下载） |
|---|---|---|---|
| 格式 | WebP | WebP | PNG |
| 尺寸 | 400×500（少量 400×501 / 400×224） | 最长边 1600 | 1122×1402 ～ 1597×2000 |
| 体积 | 26.7 MB（1499 张） | 约 220 MB（平均约 150 KB） | 4.5 GB（平均 3.1 MB） |

> 中图不由本站脚本下载，在单仓根目录用 `python tools/mid.py` 从原图生成（最长边 1600px，WebP 质量 82）。
> 没有中图时灯箱退回加载原图。

## 🛠️ 技术栈

| 技术 | 用途 |
|---|---|
| 原生 HTML / CSS / JS | 无框架、无构建、无 npm 依赖 |
| CSS 自定义属性 | 深浅色主题 |
| `prefers-color-scheme` | 跟随系统主题 |
| `IntersectionObserver` | 分页预取 |
| `localStorage` | 语言偏好 |
| Python 3 | 抓取、翻译、构建脚本 |

**刻意不使用**：React / Vue、打包工具、CDN、外部字体、任何第三方库。

## 📁 项目结构

```
.
├── index.html              # 单页画廊（数据内嵌，file:// 可直开）
├── robots.txt / sitemap.xml / 404.html
├── og-cover.jpg            # 1200×630 社交分享封面
├── manifest.json           # 全量清单（含原站 URL 与本地路径）
├── manifest.csv            # 同上，Excel 可直接打开
├── data/
│   ├── portrait.json       # 原始日文数据（1499 条）
│   ├── portrait-zh.json    # 中文数据（含日中对照字段）
│   ├── ranking.json        # 原站下载排行快照（页面已不使用，仅存档）
│   ├── meta.json           # 分区 / 发型 / 风格元数据
│   └── translations.csv    # 日⇄中对照表（54 条）
├── scripts/
│   ├── extract.py          # 从原站存档解析 images.js / ranking.js
│   ├── manifest.py         # 生成清单
│   ├── translations.py     # 日→中词典
│   └── build_gallery.py    # 构建 index.html + data/ + SEO 文件
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

python tools/fetch.py --site portrait --tier thumb    # 缩略图 400×500 webp，约 27 MB
python tools/fetch.py --site portrait --tier full     # 原图 PNG，约 4.5 GB（可选）
python tools/mid.py --site portrait                   # 灯箱中图（需要 Pillow）
python tools/verify.py --site portrait                # 校验图片完整性
python tools/build.py --site portrait
python tools/serve.py --root sites/portrait           # 本地预览
```

## ⚙️ 环境要求

| 环境 | 版本 | 说明 |
|---|---|---|
| Python | 3.8+ | 运行脚本需要 |
| 浏览器 | 任意现代浏览器 | 打开 `index.html` |
| 磁盘空间 | 27 MB（仅缩略图）/ 4.5 GB（含原图） | |
| 网络 | 仅首次下载需要 | 下载完成后完全离线 |

## 📦 生产部署

各站一起发布到同一个 `dist/`，部署、nginx、原子切换与回滚见单仓的 [deploy/DEPLOY.md](../../deploy/DEPLOY.md)。

```bash
python tools/build.py --base https://your-domain.com   # canonical / og:url / sitemap 使用正式域名
python tools/release.py --out dist-stage               # 发布前会自动校验图片
```

## 🗄️ 数据结构

`data/portrait-zh.json` 每条记录：

| 字段 | 说明 | 示例 |
|---|---|---|
| `id` | 唯一标识 | `f71f980dde3` |
| `分区` / `分区_zh` | face / styling | face / 面部 |
| `发型` / `发型_zh` | 日文 / 中文发型 | ショート / 短发 |
| `风格` / `风格_zh` | 日文 / 中文风格描述 | くびれショート（襟足長め・シースルーバング） / 内收短发（颈后偏长・空气刘海） |
| `宽` / `高` | 原图尺寸 | 1122 / 1402 |
| `缩略图` / `原图` | 相对路径 | `thumbs/f71f980dde3.webp` |

## 🔒 版权与许可

| 内容 | 权利人 | 许可 |
|---|---|---|
| 代码（`scripts/`、`index.html` 内 HTML/CSS/JS） | Brilliant666 | **MIT** |
| 图片素材 | あぎ | **CC0 1.0（公有领域）** |
| 中文译文（`data/`） | Brilliant666 | **CC BY 4.0** |

CC0 允许商用、修改、再分发，无需署名。

原作者的两点**请求**（非许可限制）：
1. 请勿再分发、转载图片数据本身 —— 本仓库遵守该请求，不包含任何图片
2. 禁止冒充真实人物，或用于违反公序良俗的用途

详见 [NOTICE.md](NOTICE.md)。

## 🐛 常见问题

| 问题 | 原因 | 解决 |
|---|---|---|
| 打开是空白卡片 | 图片还没下载 | 先跑 `download.py` |
| 灯箱提示「原图未下载」 | 只下了 thumb | 补下 `full` |
| 下载按钮 404 | 同上 | 同上 |
| 中文模式看到日文 | 该条缺译 | 正常回退，可提 PR 补译 |
| 主题不跟随系统 | 浏览器固定了浅色 | 浏览器设置里改为「跟随系统」 |

## 📝 更新日志

| 日期 | 变更 |
|---|---|
| 2026-10-30 | 初版：1499 张元数据镜像、54 条汉化、分页画廊、中日双语 |
| 2026-10-30 | 卡片加 PNG 下载按钮、移除下载排行、首屏改为 2×2 三图布局 |

## 🤝 贡献指南

- 译文在 `scripts/translations.py`（`HAIR_ZH` / `STYLE_ZH` / `UI`），改完在仓库根目录跑 `python tools/build.py --site portrait`
- 提交前请在仓库根目录运行 `python tools/build.py` 和 `python tests/run.py`，构建产物要一并提交
- **请勿提交任何图片文件**，`thumbs/` `img/` `raw/` 已在 `.gitignore` 中

## 📄 开源协议

代码 [MIT](LICENSE) · 图片 [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.zh) · 译文 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.zh)

## 💡 致谢

- 原始素材与数据：あぎ（[@agi_aibusi](https://x.com/agi_aibusi)）
- 视觉设计参考原站，中文版移除了社群推广入口

## 📧 联系方式

有问题请开 [Issue](https://github.com/xue1long/ai-video-imge-prompts/issues)。

---

# 日本語

## 📖 概要

> [ai-portrait-gallery.pages.dev](https://ai-portrait-gallery.pages.dev/) の中国語版です。
> 元サイトの編集的なデザインと全機能を保ち、中国語化し、コミュニティ導線を削除しました。

原作者：あぎ（[@agi_aibusi](https://x.com/agi_aibusi)）

## ✨ 主な機能

- 🎯 **2 セクション**：フェイス 893 枚 / スタイリング 606 枚
- 💇 **髪型で絞り込み**：ショート 727 / ミディアム 376 / セミロング 260 / ロング 136
- 📄 **ページング**：60 枚ずつ、800px 手前で自動追加
- 🖼️ **ライトボックス**：鮮明なサムネを先に表示し、中サイズ WebP（約 115 KB）をフェードイン。ホバーで先読み、`←` `→` で移動
- ⬇️ **原寸ダウンロード**：カードからも、ライトボックス内からも直接
- 🌗 **システムの配色に追従**、🌐 **中日 2 言語**
- 📦 **依存ゼロ**：単一 HTML、`file://` でそのまま開ける

## 📊 データ規模

| セクション | ショート | ミディアム | セミロング | ロング | 合計 |
|---|---:|---:|---:|---:|---:|
| フェイス | 433 | 229 | 154 | 77 | **893** |
| スタイリング | 294 | 147 | 106 | 59 | **606** |
| **合計** | **727** | **376** | **260** | **136** | **1499** |

## 🚀 クイックスタート

```bash
git clone https://github.com/xue1long/ai-video-imge-prompts.git
cd ai-image-gallery
# リポジトリ直下で実行
python tools/fetch.py --site portrait --tier thumb   # サムネイル 約 27 MB
python tools/fetch.py --site portrait --tier full    # 原寸 PNG 約 4.5 GB（任意）
python tools/build.py --site portrait
python tools/serve.py --root sites/portrait
```

## 🔒 ライセンス

| 内容 | ライセンス |
|---|---|
| コード | MIT |
| 画像 | **CC0 1.0（パブリックドメイン）** |
| 中国語訳 | CC BY 4.0 |

> 著作者の要望：画像データそのものの再配布・転載はご遠慮ください。
> 本リポジトリはこれに従い画像を含みません。

---

# English

## 📖 Overview

> A Chinese localization of [ai-portrait-gallery.pages.dev](https://ai-portrait-gallery.pages.dev/) —
> a face reference library for keeping character faces consistent across AI image and video generation.
> The original editorial design and all interactions are preserved; community promo links were removed.

Original author: あぎ（[@agi_aibusi](https://x.com/agi_aibusi)）

## ✨ Features

- 🎯 **Two sections**: `face` (893, front-facing on plain background) and `styling` (606, full look with outfit)
- 💇 **Filter by hair**: short 727 / medium 376 / semi-long 260 / long 136
- 📄 **Pagination**: 60 per page, auto-loads 800px before the bottom
- 🖼️ **Lightbox**: sharp thumbnail first, then a ~115 KB WebP preview fades in; prefetched on hover; `←` `→` to step, `Esc` to close
- ⬇️ **One-click original download** from each card, or from the lightbox
- 🌗 **Follows system color scheme**, 🌐 **Chinese / Japanese UI**
- 📦 **Zero dependencies**: single HTML file, opens via `file://`

## 📊 Scale

| Section | Short | Medium | Semi-long | Long | Total |
|---|---:|---:|---:|---:|---:|
| Face | 433 | 229 | 154 | 77 | **893** |
| Styling | 294 | 147 | 106 | 59 | **606** |
| **Total** | **727** | **376** | **260** | **136** | **1499** |

Thumbnails 400×500 WebP (26.7 MB) · originals up to 1597×2000 PNG (4.5 GB).

## 🚀 Quick start

```bash
git clone https://github.com/xue1long/ai-video-imge-prompts.git
cd ai-image-gallery
# run from the repository root
python tools/fetch.py --site portrait --tier thumb   # thumbnails, ~27 MB
python tools/fetch.py --site portrait --tier full    # full-size PNGs, ~4.5 GB (optional)
python tools/build.py --site portrait
python tools/serve.py --root sites/portrait
```

## 🔒 License

| Content | License |
|---|---|
| Code | MIT |
| Images | **CC0 1.0 (public domain)** |
| Chinese translations | CC BY 4.0 |

> The author requests that the raw image data not be redistributed. This repository
> respects that request and contains no image files.

---

## ⚠️ Content notice

素材为 AI 生成的成人向人物肖像，含泳装、内衣等着装。
仅供艺术创作、角色设计与前端技术学习使用。**未成年人请勿访问。**

AI-generated adult-oriented portraits. For art creation, character design and front-end learning only. **Not for minors.**
