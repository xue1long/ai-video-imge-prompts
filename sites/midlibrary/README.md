# Midlibrary 风格库（MIDLIB-01）

Midlibrary 的中文索引：**Midjourney 风格名 + 风格参考码（SREF）**。每条附一行
可复制的提示词和一张示例图 —— 先看图，再决定要不要把这个码粘进自己的提示词。

- 站 id：`midlibrary` · 编号 `MIDLIB-01`
- URL 路径：`/midlibrary/`（发布后为 <https://photoai.life/midlibrary/>）
- 原站：<https://midlibrary.io/library>
- 授权：**有条件** —— 站方 2026-11-05 书面许可：允许**个人学习用途**的镜像
  （文本层 + 图片层），条件是**署名 + 回链原站**（详见 [NOTICE.md](NOTICE.md)）

## 规模

| | |
| --- | --- |
| 条目 | **10,140** = 5,502 个风格名 + 4,638 个风格参考码（SREF） |
| 分类 | 16 |
| 类型（kind） | 7（艺术家 / 流派 / 艺术运动 / 作品标题 / 技法 / 风格修饰 / SREF 码） |
| 上游分页 | 每页 48 条，共 **212** 页 |

每条收录：名称、slug、类型、分类、**可复制的一行提示词**（风格形如 `by Puuung --v 8.2`，
SREF 形如 `--sref 3383230063 --v 8.2`）、一张样例表、三个徽章（站方精选 / 公有领域 / 已实测）。

## 数据来源

- 上游列表页：`https://midlibrary.io/library?page=N`（N = 1 … 212）
- 上游是 Next.js App Router，数据在服务端渲染进 RSC flight payload，**没有公开 JSON 接口**；
  `robots.txt` 只禁 `/api/` —— 本站只抓公开 HTML 页面，**不碰接口**。
- 图片全部在 `https://midlibrary.io/img/midjourney-styles/…`，**没有独立 CDN 域名**。
- 运营方：JB Nina, Inc.（美国特拉华州），创办人 Andrei Kovalev；非营利教育项目，Patreon 资助。

## 目录

```
sites/midlibrary/
├── scripts/
│   ├── config.py             # 唯一契约：常量、16 个分类与 7 种 kind 的中文名、文案
│   ├── extract.py            # 抓公开列表页 → data/items.json + data/meta.json
│   ├── extract_details.py    # 抓详情页 → data/details.json（描述 / 分面词 / 主色）
│   ├── manifest.py           # → manifest.json + manifest.csv（fetch/verify 契约，入库）
│   ├── fetch_hook.py         # 取图钩子：Referer 门 + 长超时重试 + 限流
│   └── build_gallery.py      # → index.html + data/gallery.js + 富文本分片 + 落地页 + SEO 文件
├── data/
│   ├── items.json            # 采集段产物：条目原样存（manifest.py 的输入，不入库）
│   ├── meta.json             # 统计信息与断点续抓的 resume 段
│   ├── details.json          # 详情层文本（入库，全量约 13.6 MB）
│   ├── gallery.js            # 站点主数据（入库）
│   ├── detail-<NN>.js        # 富文本分片（构建产物，不入库，灯箱按需加载）
│   └── landing.json          # 落地页清单（入库）
├── manifest.json             # 图片清单（入库；fetch.py / verify.py 的契约）
├── manifest.csv              # manifest.json 的可读导出
├── browse/ cat/              # 静态落地页（构建产物）
├── thumbs/ mid/              # 图片（不入库，用 tools/fetch.py 下载）
└── index.html                # 构建产物（入库）
```

## 采集与构建

```bash
cd sites/midlibrary
python scripts/extract.py           # 默认抓「站方精选」→ data/items.json + data/meta.json
python scripts/extract.py --all     # 全量：212 页 / 10,142 条
python scripts/extract_details.py   # 详情页富文本层 → data/details.json（断点续跑）
python scripts/manifest.py          # → manifest.json + manifest.csv
python scripts/build_gallery.py     # → index.html + data/gallery.js + 富文本分片 + 落地页 + SEO 文件
```

采集支持**断点续抓**（断点信息记在 `data/meta.json` 的 `resume` 段）：
`--force` 忽略断点全部重抓，`--pages N` 只抓前 N 页（调试用）。

### 详情页富文本层（`extract_details.py`）

列表页的 flight payload 固定 13 个字段，**没有**描述、分面词与配色 —— 这三样只在详情页
（`/library/<slug>`）的 SSR HTML 里，按 section 的 id 切出来：

| section | 抽取内容 | 键 |
| --- | --- | --- |
| `#sp-about` | 简介 / 艺术家小传 | `a` |
| `#sp-observations` | 站方对风格的观察描述 | `o` |
| `#sp-terms` | Look terms：按上游分组 + 全站计数 + `/feature/<slug>` | `t` |
| `#sp-colours` | 主色：hex + 色名 + 占比 + 颜色 slug | `c` |

- 详情页 10,142 个，实测约 2.8 条/秒（4 并发），**约 1 小时**跑完；断点续跑，重跑只补缺的。
- 完整性判据两条都要过：响应以 `</html>` 收尾 **且**页面里至少有一个 `sp-` section ——
  上游会中途断流，只看其一都会把截断页当成正常页。
- 站点体积：`data/details.json` 约 13.6 MB（入库）。构建时按 250 条一片切成
  `data/detail-<NN>.js`（约 330 KB/片，**不入库**），灯箱打开时才注入那一片，
  所以首屏不变（`index.html` 约 37 KB，主数据 2.2 MB）。

全仓库的构建与发布（`tools/build.py` 会带上 `SITE_URL` 环境变量）：

```bash
cd ../..
python tools/build.py --site midlibrary
python tools/release.py --site midlibrary
python tools/serve.py            # 预览 http://127.0.0.1:8080/
```

上游单页实测 20–60 秒，抓取很慢，图源被 DNS 污染时设代理：

```bash
FETCH_PROXY=http://127.0.0.1:7897 python scripts/extract.py
```

### 先跑 554 条

许可到位之前的那一阶段只做「**站方精选**」的 **554 条**小切片，用来先验证
抓取 → 清单 → 取图 → 构建 → 发布这条链路能跑通。**这是为了先验证全链路，
不是为了规避条款** —— 上游条款禁止的是未经许可的批量抓取；
许可到手后（2026-11-05）才按许可范围做全量。

`extract.py` **默认就抓站方精选**（`--pick`），全量要显式加 `--all`：

```bash
python scripts/extract.py          # 默认：站方精选 554 条
python scripts/extract.py --all    # 全量：212 页 / 10,142 条（清单收 10,140 条）
```

## 下载图片

图片不进仓库，用仓库通用的脚本：

```bash
cd ../..
python tools/fetch.py --site midlibrary
```

两档约 **2.5 GB**：

| 档位 | 上游参数 | 内容 | 落盘 |
| --- | --- | --- | --- |
| `thumb` | `?crop=1024,1024&crop_gravity=<方位>&width=320` | 样例表的一角（320px 象限，约 28 KB/张） | `thumbs/` |
| `mid` | `?width=960` | 整张样例表（960px） | `mid/` |

**没有 full 档**：上游原图是 2048×2048，太大且断流严重；页面上的「打开原站 ↗」
链接回上游看全尺寸。

**图片不入 git**：仓库根 `.gitignore` 排除 `sites/*/thumbs/`、`sites/*/mid/`，
克隆后必须先跑 `fetch.py` 才能看到内容；`tools/fetch.py` 幂等，已有的文件会跳过。

### 取图钩子：为什么必须带 Referer

上游图片有两道门，都由 `scripts/fetch_hook.py` 处理（`shared/assets.py` 的站点级钩子，
**不改 `tools/`**）：

- **Referer 门**：不带 Referer 一律 403（Cloudflare 挑战页）；Referer 必须是 https
  且 host 为 `midlibrary.io`。外站热链会被上游的 Worker 挡掉，返回
  `Pictures are shown on midlibrary.io.` ⇒ **页面不能直连上游**，图必须存一份，
  两档在 `sites.json` 里都是 `local-only`。
- **大图断流**：单张大图经常传到一半就没了（960 / 1440 / 2048 三档都遇到过 180 秒超时
  只收到部分字节）。钩子自带 `fetch_bytes` 通道，用 240 秒长超时、重试 4 次。

并发压到 4、两次请求间隔 0.35 秒 —— 上游是非营利站，不打疼它。

## 授权与署名

- 站方**书面许可（2026-11-05）**：允许**个人学习用途**的镜像，范围 =
  **文本层**（名称 / 分类 / 提示词 / SREF 码）+ **图片层**（缩略图与中图两档）。
- 条件：**署名 + 回链原站 + 仅个人学习用途**。页面每条都带「打开原站 ↗」链接，
  页脚写明来源与许可条件；入口页授权徽章显示「**有条件**」。
- 码与提示词本身按上游条款可自由使用（包括用于自己卖出去的作品）。
- 素材著作权归 Midlibrary 团队 / JB Nina, Inc. 与各艺术家；
  本仓库**代码 MIT**，与素材许可互相独立 —— 素材不随代码的 MIT 授权。
- 许可原件由站方与本站维护者保存，详情可向上游或本站维护者索取。

## 上游的坑（采集前先知道）

| 现象 | 处理 |
| --- | --- |
| 单页 20–60 秒 | 低并发 + 长超时 |
| 列表页响应会截断 | 校验 `</html>` 结尾，不完整就重抓 |
| 大图经常传到一半断流 | 取图钩子长超时重试 |
| 不带 Referer 一律 403；外站热链被挡 | 图存本地，页面不直连上游 |
| 没有公开 JSON 接口 | 只抓公开 HTML 页面 |
| 样例表内部版式不统一（有的有白边分格、有的连续） | **只按上游自己的裁剪参数取图**，不自己猜版式、不自己切图 |
