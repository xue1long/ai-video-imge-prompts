# Midjourney 探索榜（MJ-EXPLORE-01）

Midjourney 官网 Explore 热门榜的中文镜像。每条社区作业附原始英文提示词（可直接复制），
按采集日与画面宽高比筛选。数据按天累积：每天采集一次写进 `data/daily/<YYYY-MM-DD>/`，
历史批次原样保留，榜单换血不会抹掉前一天。

- 线上：<https://photoai.life/midjourney-explore/>
- 原站：<https://www.midjourney.com/explore?tab=styles_top>
- 授权：**禁止再分发**（详见 [NOTICE.md](NOTICE.md)）

与本站已有的 [PromptHero Midjourney 提示词集](../prompthero-midjourney/README.md) 不是同一批数据：
PromptHero 集是用户上传的提示词库，本站取的是 Midjourney 官网 Explore 热门榜，
作业与提示词都来自 Midjourney 本身。

## 目录

```
sites/midjourney-explore/
├── config.py               # 文案、宽高比中文名表、采集端点配置
├── scripts/
│   ├── extract.py          # 从官网接口采集元数据 → data/daily/<日期>/jobs.json
│   ├── manifest.py         # data/daily/*/jobs.json → manifest.json（另出 manifest.csv，不入库）
│   ├── fetch_hook.py       # 取图钩子：Cloudflare 通行证 + 浏览器化请求头
│   └── build_gallery.py    # 生成 index.html + 单一 gallery.js + 落地页 + SEO 文件
├── data/
│   ├── daily/              # 批次目录（入库）：每天一份，历史批次不覆盖
│   │   ├── 2026-11-01/     #   jobs.json + meta.json
│   │   └── 2026-11-02/
│   ├── manifest.json       # 累积索引（daily 展平；入库）
│   ├── gallery.js          # 站点数据单一分片：作业表 + 条目（入库）
│   └── landing.json        # 落地页清单（入库）
├── browse/ aspect/         # 静态落地页（由 shared/landing.py 生成）
├── thumbs/ mid/            # 图片（不入库，用 tools/fetch.py 下载）
└── index.html              # 构建产物（入库）
```

## 重新采集

### 一条命令跑完（推荐）

```bash
cd <仓库根>
python scripts/daily_collect.py            # 采集 → 索引 → 建站 → WebUI 索引 → 提交推送
python scripts/daily_collect.py --dry-run  # 只跑，不提交不推送
```

这是给每日定时任务用的入口（已配置为每天 07:00 自动跑）。
它把整条链路串起来，并处理掉手工跑最容易踩的几个坑：

- **代理端口动态探测** —— git 全局 config 里的 `http.proxy` 指向的 7890 已失效，
  而环境里的代理端口每次会话都在变，脚本按「环境变量 → 全局 config → 7897」
  逐个试连通性，取第一个能用的。
- **提交隔离** —— 用 `git commit --only -- <paths>`，只提交本站产物，
  不碰暂存区里别人的改动，也不把工作区里别人的修改带进去。
- **提交前校验** —— 重建一次并比对产物是否稳定，不一致就放弃提交
  （避免把过不了 CI 闸门的产物推上去）。
- **完整性基线自动重置** —— `data/.manifest_baseline` 记着上次的 manifest 行数，
  删过批次后它会挡住后续所有构建，脚本会按实际行数对齐。

退出码：`0` 成功 / `2` 采集失败（数据未动，明日重试）/ `3` 当天批次已存在（正常跳过）/
`4` 构建或校验失败 / `5` 推送失败（提交已在本地，需人工 push）。

### 分步手动跑

```bash
cd sites/midjourney-explore
python scripts/extract.py        # 采集 4 页（约 5 秒）→ data/daily/<今天>/
python scripts/manifest.py       # 累积所有批次 → manifest.json
```

采集**每天写一份新批次**（`data/daily/<YYYY-MM-DD>/`），历史批次原样保留——
榜单每天换血，本地数据只增不替。同一天重复采集要显式 `--force`：

```bash
python scripts/extract.py --batch 2026-11-02 --force   # 重采某一批
python scripts/extract.py --batch 2026-11-03            # 换一天
```

需要出口 IP 时设代理：

```bash
FETCH_PROXY=http://127.0.0.1:7897 python scripts/extract.py
```

`extract.py` 会先访问一次 Explore 页面拿 Cloudflare 的 `__cf_bm` 通行证，
再带着它调接口。少了这一步接口会返回 403。

## 下载图片

图片不进仓库，用仓库通用的脚本：

```bash
cd ../..
FETCH_PROXY=http://127.0.0.1:7897 python tools/fetch.py --site midjourney-explore
```

三档约 2.4 GB：缩略图 640 档 93 MB、中图 1024 档 195 MB、原图 PNG 2.1 GB。

**但现在只下两档**（约 288 MB）：`sites.json` 的 `tiers` 已改为 `["thumb", "mid"]`，
`full` 档的取图策略是 `online` —— 原图走 CDN 直链，**本地不存**。
`manifest.json` 里 `full` 只有 `full_url`，没有 `full_path`。

`tools/fetch.py` 走的是共用的 `shared/assets.py`，它会自动发现本站的
`scripts/fetch_hook.py` 并调用它——钩子负责带上浏览器化请求头与通行证 cookie。
没有这个钩子，CDN 会对所有请求返回 403。

## 风格数据线（Styles）

原站右上角的 Styles 是**独立内容类型**，不在 `feed=top` 的返回里。它有两个脚本：

```bash
cd sites/midjourney-explore

# 1) 取码（需要登录态，见下）
python scripts/dump_styles.py --state ../../.scratch/mj_session.json

# 2) 下图（不需要登录，CDN 直连）
python scripts/fetch_styles.py --size 1024
```

产物：

| 路径 | 内容 | 是否入库 |
|---|---|---|
| `data/styles.json` | 清单：feed / captured_at / 累计码表 / 每次抓取快照 | 是 |
| `data/styles_images.json` | 每码每类图的命中状态 | 是 |
| `styles/<码>/portrait.webp` 等 | 三类示例图，每码三张（261 码共 783 张，191 MB） | 否（`.gitignore`） |

**每个码有三张语义化单图**：`portrait` / `landscape` / `still_life`，
同一风格的三个不同题材。CDN 上只有 128 / 384 / 640 / 1024 四档。

**榜单是滚动的**：单次抓取只有 200 条，相隔 45 分钟的两次抓取重合 139 条（约 30% 换血）。
所以 `dump_styles.py` 默认**合并累积**，重复跑就是在攒库 —— 不需要一次抓全。

**登录门槛**：清单接口 `/api/explore-srefs` 必须登录态，且**只能在浏览器页面
上下文里调用** —— 把 cookie 拿出来用 Python 直连会稳定 `500`（`cf_clearance` 与
Chrome 的 TLS 指纹绑定）。所以脚本用 Playwright 在页面里 `fetch`。

登录态用 Playwright 的 `storage_state` 文件传递，含时效，过期后需要人工重登一次
再导出。**因此这条线不能挂进每日定时任务**，只能按周/月手动刷新。
完整证据与边界见 `docs/STYLES_FEASIBILITY.md` §11。

## 构建

```bash
cd ../..
python tools/build.py --site midjourney-explore
python tools/release.py --site midjourney-explore
python tools/serve.py
```

数据量不大，**单一数据文件**：`data/gallery.js` 内嵌全部条目（作业表 + 每格的
thumb/mid/full 地址），`index.html` 约 28 KB。批次与宽高比都是**前端筛选条件**，
切筛选不触发网络请求。规模浏览交给本地素材管理器（`index/`），静态站只做近期预览。

## 设计要点

- **批次化累积**：采集结果按天写进 `data/daily/<YYYY-MM-DD>/`，历史批次不覆盖；
  `manifest.json` 是所有批次的累积展平。源数据只有 `daily/`，其余都是可重建派生。
- **提示词按作业去重**：同一条作业的 4 格共用一段提示词，
  作业表（`data/gallery.js` 内）存一次，条目里只存作业下标。
- **原图走直链**：`full` 档的 `imagePolicy` 是 `online` —— 页面与素材管理器都直接用
  CDN URL，本地不留原图（每天约 2.3 GB）。
- **中图为上游档位**：`sites.json` 的 `tiers` 含 `mid`，
  `tools/mid.py` 会跳过本站（不覆盖上游提供的文件）。
- **宽高比分面**：官网 Explore 榜不提供官方分类，宽高比是唯一稳定可枚举的维度。

