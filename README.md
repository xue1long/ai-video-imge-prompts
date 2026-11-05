<div align="center">

# AI 图片素材库 · 单仓多站

**八个 AI 绘画参考图库，一个仓库构建，一个目录部署**

人像 · 姿势 · 深度姿势 · 服装 · CC0 姿势线稿 · 提示词生图集 · Midjourney 探索榜 · 提示词集 · 114,709 个图片文件 · 中日双语 · 浅色 / 深色

[![CI](https://github.com/xue1long/ai-video-imge-prompts/actions/workflows/ci.yml/badge.svg)](https://github.com/xue1long/ai-video-imge-prompts/actions/workflows/ci.yml)
[![online](https://img.shields.io/badge/online-photoai.life-2563eb?style=flat-square)](https://photoai.life/)
[![sites](https://img.shields.io/badge/sites-8-0ea5e9?style=flat-square)](#八个站点)
[![images](https://img.shields.io/badge/images-113%2C957-8b5cf6?style=flat-square)](#八个站点)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#快速开始)
[![License](https://img.shields.io/badge/code-MIT-22c55e?style=flat-square)](#许可与致谢)

### [在线浏览 · photoai.life →](https://photoai.life/)

**简体中文** · [English](README_en.md) · [日本語](README_ja.md)

[八个站点](#八个站点) · [快速开始](#快速开始) · [图片加载](#图片加载) · [部署](#部署) · [文档](#文档)

</div>

![入口页](docs/screenshots/hub-light.jpg)

<details>
<summary>📷 更多截图：人像、姿势、深度姿势、服装</summary>

![人像集 · 网格](docs/screenshots/portrait-grid.jpg)

![人像集 · 灯箱](docs/screenshots/portrait-lightbox.jpg)

![姿势集 · 深色](docs/screenshots/pose-grid.jpg)

![姿势集 · 灯箱](docs/screenshots/pose-lightbox.jpg)

![深度姿势集](docs/screenshots/pose-depth-grid.jpg)

![服装集 · 分面筛选](docs/screenshots/costume-filter.jpg)

![服装集 · 灯箱](docs/screenshots/costume-lightbox.jpg)

截图来自线上页面，用于演示界面。素材著作权归各原作者所有，不能从截图中裁取素材另作他用。

</details>

## 八个站点

| 站点 | 内容 | 规模 | 素材授权 |
| --- | --- | --- | :---: |
| [人像集](https://photoai.life/portrait/) | 保持角色脸部一致性的人脸参考，按发型筛选 | 1,499 张 | **CC0** |
| [姿势集](https://photoai.life/pose/) | 无脸灰色人偶线稿，每个姿势 5 个视角 | 1,439 张 | 禁止再分发 |
| [深度姿势集](https://photoai.life/pose-depth/) | 同批姿势的灰度深度图，适合 ControlNet | 1,439 张 | 禁止再分发 |
| [服装集](https://photoai.life/costume/) | 不含真人的服装图，86 个标签分面筛选 | 1,407 件 / 4,221 张 | 禁止再分发 |
| [Shisei 姿势线稿](https://photoai.life/shisei/) | 无脸人偶线稿，四个系列、每个姿势 5 个视角，偏性感的默认模糊 | 280 个姿势 / 1,133 张 | **CC0** |
| [提示词生图集](https://photoai.life/prompts/) | AI 生图成图与提示词对照，两个模型（Imge-2 / Nano Banana）、可按模型与 41 个官方分类筛选，一条提示词的多张成图归为一条素材 | 26,458 条 / 41,261 张 | **CC BY 4.0** |
| [Midjourney 探索榜](https://photoai.life/midjourney-explore/) | Midjourney 官网 Explore 热门榜的镜像，每条社区作业附原始英文提示词，按采集日与画面宽高比筛选 | 987 条作业 / 3,948 张 | 禁止再分发 |
| [Midjourney 提示词集](https://photoai.life/prompthero-midjourney/) | Midjourney 提示词与成图对照，v1–v7 与 Niji 共 13 个版本、14 个分类，含成人内容分区（默认模糊） | 12,998 条 | 禁止再分发 |

每个站都有：网格分页加载、筛选与搜索、灯箱（`←` `→` 翻页，`Esc` 关闭，手机可滑动）、原图下载、主题与语言切换。页面是单个 `index.html`，数据内嵌，没有框架、CDN 和外部字体。

> **人像集和 Shisei 是 CC0**，姿势、深度姿势、服装、Midjourney 探索榜、Midjourney 提示词集五站的素材禁止再分发，**提示词生图集为 CC BY 4.0（可商用、须署名，作者与来源逐条保留）**。Shisei 的姿势目录沿用 ai-pose-gallery，只注明出处。Midjourney 提示词集的素材由 PromptHero 用户上传、Midjourney 探索榜的成图由社区用户生成，引用须回链原站。详见各站的 `sites/<id>/NOTICE.md`。

## 快速开始

本仓库不含图片文件，由 `tools/fetch.py` 从各原站下载。需要 **Python 3.8+**。生成中图的 `tools/mid.py` 另需 Pillow（`pip install pillow`），其余脚本只用标准库。

```bash
git clone https://github.com/xue1long/ai-video-imge-prompts.git
cd ai-video-imge-prompts

python tools/fetch.py      # 下载全部图片（首次约 86 GB，之后只补缺失）
python tools/mid.py        # 生成灯箱中图（约 290 MB）
python tools/build.py      # 构建八个站 + 入口页
python tools/release.py    # 组装 dist/（图片硬链接，不额外占盘）
python tools/serve.py      # 预览 http://127.0.0.1:8080/
```

只想看页面效果，用 `python tools/fetch.py --tier thumb` 只下缩略图（约 90 MB）。

验收请用 `serve.py`，不要直接双击 `dist/index.html`：`file://` 和 `http://` 在相对路径、Content-Type、缓存上都有差异。

<details>
<summary>常用命令</summary>

| 命令 | 作用 |
| --- | --- |
| `python tools/fetch.py --site pose` | 只下载一个站 |
| `python tools/mid.py --site portrait` | 只生成一个站的中图 |
| `python tools/verify.py` | 校验图片：存在、体积、可读宽高、中图是否齐全 |
| `python tools/build.py --site pose` | 只重建一个站 |
| `python tools/build.py --base https://x.com` | 指定正式域名，写入 canonical / og / sitemap |
| `python tools/release.py --out <目录>` | 发布到指定目录 |
| `python tools/serve.py --root sites/pose` | 预览单个站点 |
| `python tests/run.py` | 不依赖图片的检查：构建产物是否最新、重复 id、内联 JS 语法、manifest、文档链接（CI 每次推送都跑） |

`release.py` 发布前会先校验图片，缺图就中止（只下了部分档位时加 `--skip-verify`）。它会先删除再重建目标站点目录。`--no-images` 只放站点文件、不放图片，不能用来保留线上旧图。

</details>

## 图片加载

每张图有三档：网格用缩略图，灯箱用中图，原图只在下载时用到。

| 档位 | 人像 | 姿势 | 深度姿势 | 服装 |
| --- | ---: | ---: | ---: | ---: |
| 缩略图 | 约 20 KB | 约 17 KB | 约 11 KB | 约 10 KB |
| 中图 | 约 150 KB | 约 33 KB | 约 10 KB | 约 90 KB |
| 原图 | 约 3.2 MB | 约 450 KB | 约 95 KB | 约 1 MB |

- 灯箱打开时先显示清晰的缩略图，中图到达后淡入；换图时上一张立即隐藏。
- 鼠标在卡片上停留 120 ms、手指按下或键盘选中时开始预取中图；打开后再预取前后各一张。
- 服装集与 Shisei、两站 Midjourney 的中图来自上游；人像集、姿势集、深度姿势集三站由 `tools/mid.py` 从原图生成（最长边 1600px，WebP 质量 82）。中图缺失时灯箱退回原图。

在 1.5 MB/s、150 ms 延迟下实测人像集：直接点击约 0.6 秒换成中图；悬停约 1 秒后再点，打开就是中图。

## 部署

站点根指向 `dist/`。`dist/` 是扁平结构（`index.html` + `portrait/` + `pose/` + …），入口页的相对链接直接命中，nginx 不需要 `alias`。

```bash
# 服务器更新：丢弃构建产物；有手改文件时中止并列出，不会悄悄覆盖
python3 tools/update.py
python3 tools/mid.py
python3 tools/build.py --base https://你的域名
python3 tools/release.py --out dist-stage   # 先发到暂存目录，检查后逐站原子换入 dist/
```

首次部署、nginx 配置、原子切换和回滚见 [deploy/DEPLOY.md](deploy/DEPLOY.md)。

## 项目结构

```
ai-video-imge-prompts/
├── sites.json          # 唯一清单：站点、顺序、授权、图片档位
├── sites/<id>/         # 各站：脚本、数据、构建产物、NOTICE
├── shared/             # 各站共用的下载与校验；姿势 / 深度姿势共用的页面生成器、原站解析、日中词典
├── hub/                # 入口页生成器（同时生成根 sitemap / robots）
├── tools/              # fetch / mid / verify / build / release / serve / update
├── deploy/             # 部署手册与 nginx 模板
├── tests/              # 不依赖图片的检查（python tests/run.py）
└── docs/               # 文档与截图
```

图片不进 git：约 86 GB 二进制放进仓库，每次 clone 都要拉一遍，各站授权也不允许。`release.py` 把图片文件硬链接进 `dist/`，同一文件系统下不额外占盘。

## 素材管理器（本地 WebUI）

静态站是「发布」，素材管理器是「日常用」。同一个仓库两种形态，图片不搬、不复制。

双击 `启动.bat`（或 `python index/serve.py`）打开 `http://127.0.0.1:8787/`。

界面与静态站同一套设计语言：相同的颜色变量（浅色 `#2563eb`／深色 `#8fb4ff`）、胶囊 tab 与 chip、2:3 不裁切的卡片、淡光晕背景。右上角切换浅色/深色，选择记在浏览器里。

布局是四块：顶部一排集合胶囊 tab（带条目数）、左栏分面筛选（值超过 48 项的如「编号」默认折叠）与添加素材、中间网格每页 120 条、右栏详情。卡片只显示标题，编号留在详情里 —— 否则长 id 会把「S形站姿・胯部向侧顶出」挤成两个字。

| 命令 | 作用 |
| --- | --- |
| `python index/sync.py` | 把八个站点的 manifest 同步进 `gallery.db`；manifest 没变就跳过 |
| `python index/verify.py` | 探缺图：把盘上已不存在的资产标成 `missing` |
| `python index/snapshot.py` | 给数据库留一个可回滚的快照，写到 `backups/` |

边界只有一句：**`sites/` 只读、`library/` 可写**。采集来的素材永不物理删除（只做视图隐藏），自己导入的素材才允许删。数据库、导入素材、快照、配置都不进 git。

一张图有四个入口，都落在同一个导入函数上：

| 入口 | 位置 | 结果 |
| --- | --- | --- |
| 拖文件/文件夹到页面 | 全局 | 新增素材（`own` 集合） |
| 左栏「添加素材」三个按钮：选本地图片 / 粘贴图片 / 粘贴链接 | 左栏 | 新增素材 |
| `Ctrl+V` 直接贴图 | 全局 | 新增素材 |
| 详情面板「给这条素材加图」同样的三个按钮 | 右侧详情 | **追加**图片到这条素材，可多选，主图不动 |
| 详情面板「替换这张图」同样的三个按钮 | 右侧详情 | **替换当前素材的展示图**，原图留在盘上不删 |

「替换」不是覆盖文件：新图进 `library/YYYY/MM/`、排到主图位，原图变成第二版本。所以对 `sites/` 只读区也成立，随时可以反悔。链接只接受 `http`/`https`，单张上限 40 MB。

「加图」和「替换」是两件事：一条提示词的上游成图保持原样，自己用别的模型跑出来的图接在图条**末尾**（详情里虚线缩略图），主图与复制出来的 prompt 都不变。图为 `library/` 内的文件，因此重跑 `sync.py` 也不会丢；同一条素材下重复传同一张会被内容哈希挡掉。

接口契约见 [SPEC](docs/SPEC_MATERIAL_MANAGER.md)，方案推演见 [v6](docs/REFACTOR_V6_LOCKED.md)。

## 文档

[部署手册](deploy/DEPLOY.md) · [加第 N 个站](docs/ADDING_A_SITE.md) · [nginx 模板](deploy/nginx.conf) · 各站说明：[人像](sites/portrait/README.md) · [姿势](sites/pose/README.md) · [深度姿势](sites/pose-depth/README.md) · [服装](sites/costume/README.md) · [Shisei](sites/shisei/README.md) · [提示词生图集](sites/prompts/README.md)

## 许可与致谢

| 范围 | 许可 |
| --- | --- |
| 代码：`tools/`、`hub/`、`shared/`、各站 `scripts/`，以及 `index.html` 里的 HTML/CSS/JS | [MIT](LICENSE) |
| 图片素材 | 各站不同，见 `sites/<id>/NOTICE.md` |
| `data/` 中的中文译文 | CC BY 4.0 |

素材来自各原站：人像集作者 [あぎ](https://x.com/agi_aibusi)（[原站](https://ai-portrait-gallery.pages.dev/)），姿势集、深度姿势集、服装集作者 [ギア](https://x.com/giaaibusi)（[姿势](https://ai-pose-gallery.pages.dev/) · [深度姿势](https://ai-pose-depth-gallery.pages.dev/) · [服装](https://ai-costume-gallery.pages.dev/)）。Shisei 线稿来自 [wquguru/shisei](https://github.com/wquguru/shisei)（CC0）。提示词生图集来自 YouMind 社区（[GPT Image 2 Prompts](https://youmind.com/gpt-image-2-prompts/explore) · [Nano Banana Pro Prompts](https://youmind.com/nano-banana-pro-prompts/explore) · [开源镜像](https://github.com/YouMind-OpenLab/awesome-gpt-image-2)，CC BY 4.0）。本项目是个人学习用途的中文镜像。
