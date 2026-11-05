# NOTICE — Midlibrary 风格库（MIDLIB-01）

## 来源

- 素材集：Midlibrary（<https://midlibrary.io/library>）
- 运营方：**JB Nina, Inc.**（美国特拉华州）；创办人 Andrei Kovalev。
  是一个**非营利教育项目**，由 Patreon 资助。
- 采集方式：只抓**公开 HTML 页面**。上游是 Next.js App Router，数据在服务端渲染进
  RSC flight payload，**没有公开 JSON 接口**；`robots.txt` 只禁 `/api/`，
  本站不碰任何接口，只读公开列表页。
- 收录范围：**10,140 条** = 5,502 个风格名 + 4,638 个风格参考码（SREF）；
  **16 个分类**、**7 种 kind**。
  （上游共 10,142 条，其中 2 条上游自己就没有 v8.2 样例表 —— 详情页只有旧版本的
  单图，没有可裁的四宫格。本站不伪造图，这 2 条未收录。）
- 采集日期：2026-11-05（首轮快照）
- 上游列表页形态：`/library?page=N`，每页 48 条，共 212 页。

## 每条收录了什么

一条 = 名称、slug、类型（kind）、分类、**可复制的一行提示词**、一张样例表、三个徽章。

- 提示词原样保留：风格名形如 `by Puuung --v 8.2`，SREF 形如 `--sref 3383230063 --v 8.2`。
- 样例表是上游的整张 **2048×2048 JPEG**，含该风格的 4 张样例。
- 三个徽章逐条保留：**站方精选**（`isPick`）/ **公有领域**（`isPublicDomain`）/ **已实测**（`testedMark`）。

条目文本（名称、提示词）原样保留，未翻译、未改写；本站只做索引与展示。

## 授权

### 上游条款（2026-11-02 生效）

上游 Terms of Use（<https://midlibrary.io/midlibrary/terms-of-use>）关键原文：

> "Unless noted otherwise, all images on this website are created by the Midlibrary
> team using Midjourney AI and are not representative of real artists' works or
> real-world prototypes of the Midjourney styles used. Please respect the copyright —
> kindly ask us before re-using any materials published on Midlibrary.io."

中文解释：站内图片由 Midlibrary 团队用 Midjourney 生成，**不代表真实艺术家的作品**，
也不是所用 Midjourney 风格的真实原型；复用站内材料前请先征得站方同意。
⇒ 本站要镜像图片，就落在「re-using any materials」这一侧，必须有站方许可。

> "You may — browse the site and save styles to your collections; copy style names,
> SREF codes and prompts, and use them in your own creative work, including work you
> sell; share links to Midlibrary pages."

中文解释：**风格名、SREF 码与提示词可以复制**，用在自己的创作里（包括卖出去的作品）
也行；可以分享指向 Midlibrary 页面的链接。
⇒ 本站收录的「文本层」（名称 / 分类 / 提示词 / SREF 码）本身是被上游明确允许使用的。

> "You may not — copy, scrape or download the library in bulk, by hand or by machine;
> republish our pictures, pages or guides, or build a copy of the library or a dataset
> from it, without our written permission; use our pictures or pages to train AI models
> without our written permission; break, overload or get around the site's limits or
> security…"

中文解释：**未经书面许可**，不得批量抓取或下载、不得再发布其图片 / 页面 / 指南、
不得据此复制出这个库或建成数据集、不得用其图片与页面训练 AI 模型、
不得破坏或绕过站点的限额与安全措施。
⇒ 「镜像整个库 + 把图存一份」正好落在被禁止的一侧，**必须先有书面许可**才成立。

> "We may limit or block automated access to protect the site."

中文解释：上游可以限制或封禁自动化访问。
⇒ 采集必须低速、遵守 `robots.txt`（只禁 `/api/`，其余路径可读）。

同一页的短版摘要：

> "Use our codes and prompts in your own work. Don't copy or scrape the library itself."

中文解释：一句话版本 —— 码和提示词随便用，别把库本身抄走。

上游条款另有一条关于**被点名艺术家**的权利（此处为中文转述，未留英文原文）：艺术家保留
其姓名与风格的权利，可要求撤下其姓名与页面，站方在 30 天内处理。

### 站方书面许可

- **站方已就本站镜像出具书面许可，出具时间记作 2026-11-05。**
- 许可范围：**个人学习用途**的镜像，共两层：
  - **文本层**：名称 / 分类 / 提示词 / SREF 码；
  - **图片层**：**缩略图与中图两档**。
- 许可条件：**署名 + 回链原站**，且**仅限个人学习用途**。
- 授权徽章取 `conditional` —— 入口页该站显示「**有条件**」。
- 许可原件由站方与本站维护者保存，详情可向上游或本站维护者索取。
  本文档**不记录**签署人姓名、合同编号与往来邮件细节 —— 这些未记录，不做推测。

许可到位**之前**的那一阶段只跑「站方精选」的 554 条小切片，用来先验证
抓取 → 清单 → 取图 → 构建 → 发布这条链路。**这是为了先验证全链路，
不是为了规避条款** —— 条款禁止的是未经许可的批量抓取。

### 本站做什么、不做什么

做：

- 镜像公开列表页上的**文本层**与**图片层（thumb / mid 两档）**；
- 每条保留名称、分类、类型、提示词 / SREF 码与原站链接，页面上逐条可回链；
- 在页面页脚与 NOTICE 写明来源、许可条件与署名要求；
- 入口页授权徽章标「有条件」。

不做：

- 不对外提供整库导出，不建数据集；
- 不用本站的图片或页面训练 AI 模型；
- 不镜像上游的页面版式与指南正文 —— 只收录条目级数据；
- 不做商业用途 —— 许可只覆盖**个人学习用途**；
- 不绕过上游的限额与安全措施。

### 素材著作权

- 素材著作权归 **Midlibrary 团队 / JB Nina, Inc.**；被点名的艺术家保留其姓名与风格的权利。
- 本仓库**代码为 MIT**，与本站素材许可**互相独立**：素材不随代码的 MIT 授权。

## 数据来源的可达性

- 列表页：`https://midlibrary.io/library?page=N`（N = 1 … 212，每页 48 条）。
  数据在服务端渲染进 RSC flight payload，没有可直接调用的 JSON 接口。
- 图片：`https://midlibrary.io/img/midjourney-styles/…` —— **没有独立 CDN 域名**，
  图片与页面同域。裁剪由上游做，参数也是上游自己的：

  | 档位 | 上游参数 |
  | --- | --- |
  | 缩略图 | `?crop=1024,1024&crop_gravity=<方位>&width=320` |
  | 中图 | `?width=960` |

### 本地留存的档位

| 档位 | 内容 | 落盘 | 体积 |
| --- | --- | --- | --- |
| `thumb` | 320px 象限（样例表的一角，方位由条目的 `sheetQuadrant` 决定） | `thumbs/` | 约 28 KB/张 |
| `mid` | 960px 整张样例表 | `mid/` | — |

**没有 full 档。** 上游原图是 2048×2048，太大，且上游大图断流严重（见下）；
页面上的「打开原站 ↗」链接回上游看全尺寸。

## 上游数据特征

| 现象 | 处理 |
| --- | --- |
| 单页 20–60 秒 | 低并发（4）+ 长超时 + 请求间隔 0.35 秒，不打疼一个非营利站 |
| 列表页响应会截断 | 校验 `</html>` 结尾，不完整就重抓 |
| 大图经常传到一半断流（实测 960 / 1440 / 2048 三档都遇到过 180 秒超时只收到部分字节） | 取图钩子自带长超时（240 秒）与重试（4 次） |
| Referer 门：不带 Referer 一律 403（Cloudflare 挑战页） | 钩子按条目页拼 Referer |
| Referer 必须是 https 且 host 为 `midlibrary.io`；外站热链被 Worker 挡掉，返回 `Pictures are shown on midlibrary.io.` | **图片必须存一份**，页面不能直连上游（两档都是 `local-only`） |
| `robots.txt` 只禁 `/api/` | 只抓公开 HTML 页面，不碰接口 |
| 样例表内部版式不统一（有的有白边分格、有的连续） | **每条只按上游自己的裁剪参数取图**，不自己猜版式、不自己切图 |
| 上游可限制或封禁自动化访问 | 采集低速、遵守 `robots.txt`，不绕过站点的限额与安全措施 |
