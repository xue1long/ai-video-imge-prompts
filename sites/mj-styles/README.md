# Midjourney 风格码库（MJ-STYLES-01）

Midjourney 官网 Explore → Styles 榜单的风格码（`--sref`）中文镜像。
每个码附**人像 / 风景 / 静物**三张示例图，用来判断这套视觉语言长什么样；
点一下就能复制 `--sref <码>`，直接贴进 Midjourney 提示词。

- 线上：<https://photoai.life/mj-styles/>
- 原站：<https://www.midjourney.com/explore?tab=styles_top>
- 授权：**禁止再分发**（详见 [NOTICE.md](NOTICE.md)）

与 [Midjourney 探索榜](../midjourney-explore/README.md) 不是同一批数据：
探索榜收录的是社区**作业**（一条作业四格成图，带提示词与作者），
本站收录的是**风格码**（一个码三张示例图，没有提示词也没有作者）。
两者的码表实测**完全不相交**（329 vs 45，交集 0），所以拆成两个站而不是同一站的两个视图。

## 目录

```
sites/mj-styles/
├── config.py               # 文案、构图中文名表、采集配置
├── scripts/
│   ├── dump_styles.py      # 抓风格码清单 → data/styles.json（**必须登录态**）
│   ├── capture_session.py  # 人工登录一次 → 导出 storage_state 会话文件
│   ├── fetch_styles.py     # 下载三张示例图 → styles/<码>/（1024 + 本地缩放 384）
│   ├── manifest.py         # data/styles.json → manifest.json
│   ├── build_gallery.py    # 站点协议层：SEO + robots/sitemap/404
│   └── build_styles_page.py  # 页面主体（码表网格 + 灯箱 + 构图切换），被 build_gallery.py 调用
├── data/
│   ├── styles.json         # 码表（入库）：329 码 + 快照历史 + added_at
│   ├── styles_images.json  # 每码每类的命中状态（入库）
│   ├── styles_probe.json   # 探测批留档（入库）：不并入码表的 35 个码
│   └── landing.json        # 落地页清单（入库）—— **当前为空**：本站不生成落地页
├── manifest.json           # 索引清单（987 行 = 329 码 × 3 张，入库）
├── styles/<码>/            # 图片（不入库，用 scripts/fetch_styles.py 下载）
│   ├── portrait.webp       #   1024 大图（灯箱用）
│   └── s/portrait.webp     #   384 缩略（网格用，本地从 1024 缩出）
└── index.html              # 构建产物（入库）
```

> `scripts/fetch_hook.py` **不在这里**：它是 `midjourney-explore` 站的
> Cloudflare 通行证钩子，`shared/assets.py` 会自动发现 `sites/<id>/scripts/fetch_hook.py`。
> 曾经把它一起搬过来，结果 MJ 站的 `tools/fetch.py` 拿不到通行证、CDN 全 403。
> **钩子是站级共享件，不是站级私产。**

## 重新采集

### 清单（需要登录态）

```bash
# 会话过期时先重走一次人工登录，导出到仓库外
python scripts/capture_session.py --cdp http://127.0.0.1:9333

# 抓清单（默认合并累积，不覆盖历史码）
python scripts/dump_styles.py --state "%USERPROFILE%\.workbuddy\secrets\midjourney-session.json"
```

> 清单接口 `/api/explore-srefs` **必须登录态**，且**只能在浏览器页面上下文里调用**
> （把 cookie 拿出来用 Python 直连会稳定 500 —— `cf_clearance` 绑定 Chrome 的 TLS 指纹）。
> 脚本用 Playwright 在页面里执行 fetch。三种运行模式见 `dump_styles.py --help`。

### 图片

```bash
python scripts/fetch_styles.py            # 全量，1024 档（缩略由本地缩放生成）
python scripts/fetch_styles.py --size 640 # 换档
python scripts/fetch_styles.py --codes 3441803824,4212271874
```

图片在 CDN 上匿名可下，但要带 Cloudflare 下发的 `__cf_bm` 通行证 ——
裸 urllib 直连必定 403。

### 构建

```bash
python scripts/manifest.py     # styles.json → manifest.json
python scripts/build_gallery.py
```

构建产物：`index.html`（首页）、`data/landing.json`（**空清单**）、
`sitemap.xml`、`robots.txt`、`404.html`、`og-cover.jpg`。

**本站不生成落地页**（2026-11-04 起）。`sites.json` 里声明 `"landing": false`，
hub 与 sitemap 据此不再链到 `browse/`。原因：风格码本身没有可枚举的分类
（原站只有搜索框），唯一稳定的分组维度「这张示例图属于哪种构图」已经由
首页顶部的全站构图切换器覆盖了，再单独开三个落地页只是重复内容。

**缺图不阻断构建**（2026-11-04 起）：缺图会打到 stderr 列出清单，但构建照常
生成页面、退出码 0。两个原因：图片不入库，CI 的干净检出上必然「缺图 1974 个」，
硬失败意味着 CI 永远红；更要紧的是「构建产物只取决于配置」这条约定 ——
同一份代码在有图与无图的环境里必须产出同一份页面。

## 排序与筛选

| 能力 | 判据 |
|---|---|
| 默认排序 | `added_at` 倒序（新码在前）——榜单顺序每轮都在变，只有首次收录时间稳定 |
| 只看最近新增 | `added_at` 等于最近一次快照时间的码 |
| 搜索 | 码的任意子串（前缀是它的子集） |
| 复制 | `--sref <码>`，可复制单个或全部（当前筛选结果） |
| 切构图 | 顶部三态切换器（人像 / 风景 / 静物）——**全站** 329 张卡一起换 |

### 构图的两种语义（别混）

构图（人像 / 风景 / 静物）是**图级**属性：329 个码**全部**三张齐备
（实测 `('landscape','portrait','still_life') × 329`）。因此：

| 位置 | 语义 | 行为 |
|---|---|---|
| 顶部 seg 切换器 | **全站显示哪种构图** | 329 张卡一起换；与 `#kind=<slug>` 双向同步（点它会写回 hash） |
| 卡内 `.kinds` 三态按钮 | **这一码看哪张图** | 只改这一张卡，不动 seg |

**不能**做成「筛选出该构图的码」——那是恒等筛选（点了还是全部 329 条）。
`#kind=<slug>` 的语义是「全站切到该构图」：用户在地址栏直接敲
`#kind=still-life`，或从别处带 hash 进来，首页会切到该构图。

slug 取值：`portrait` / `landscape` / `still-life`（`still_life` 的连字符形式，
与 `config.KIND_SLUG` 一致）。

> 落地页 `kind/<slug>/` 已于 2026-11-04 删除，原先放在那里的 CTA
> （「在画廊中查看全部」，带 `#kind=<slug>`）随之取消。首页自己读
> `location.hash` 的能力保留 —— 那段 JS 是给「带 hash 进来」用的，
> 与落地页在不在无关。

## 相关文档

- 采集与取图的实测依据：<../midjourney-explore/docs/STYLES_FEASIBILITY.md>（§11 采集、§13 拆分）
- 加站约定：<../../../docs/ADDING_A_SITE.md>
