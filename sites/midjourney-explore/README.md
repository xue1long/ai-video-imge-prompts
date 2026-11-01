# Midjourney 探索榜（MJ-EXPLORE-01）

Midjourney 官网 Explore 热门榜的中文镜像。收录 200 条社区作业、800 张成图，
每条附原始英文提示词（可直接复制），按画面宽高比筛选。

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
│   ├── extract.py          # 从官网接口采集元数据 → data/jobs.json
│   ├── manifest.py         # data/jobs.json → manifest.json（另出 manifest.csv，不入库）
│   ├── fetch_hook.py       # 取图钩子：Cloudflare 通行证 + 浏览器化请求头
│   └── build_gallery.py    # 生成 index.html + 宽高比分片 + 落地页 + SEO 文件
├── data/
│   ├── jobs.json           # 采集到的元数据（入库）
│   ├── meta.json           # 采集统计
│   ├── gallery.js          # 宽高比索引 + 作业表（入库）
│   └── gallery_<asp>.js    # 宽高比数据分片（不入库，由脚本重建）
├── browse/ aspect/         # 静态落地页（由 shared/landing.py 生成）
├── thumbs/ mid/ img/       # 图片（不入库，用 tools/fetch.py 下载）
└── index.html              # 构建产物（入库）
```

## 重新采集

```bash
cd sites/midjourney-explore
python scripts/extract.py        # 采集 4 页（约 5 秒）
python scripts/manifest.py       # 生成 manifest
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

`tools/fetch.py` 走的是共用的 `shared/assets.py`，它会自动发现本站的
`scripts/fetch_hook.py` 并调用它——钩子负责带上浏览器化请求头与通行证 cookie。
没有这个钩子，CDN 会对所有请求返回 403。

## 构建

```bash
cd ../..
python tools/build.py --site midjourney-explore
python tools/release.py --site midjourney-explore
python tools/serve.py
```

数据量大，页面按宽高比分片懒加载：`index.html` 只内嵌索引与作业表（约 124 KB），
每个宽高比的数据在 `data/gallery_<asp>.js`，切换分面时才拉取。

## 设计要点

- **提示词按作业去重**：同一条作业的 4 格共用一段提示词，
  作业表（`data/gallery.js` 内）存一次，分片里只存作业下标。
  800 张图全部内嵌会让页面到 1091 KB，超出 450 KB 上限。
- **分片不入库**：`data/gallery_*.js` 由脚本重建，`.gitignore` 已排除；
  但它们**可由入库的 `manifest.json` 一键重建**，所以 CI 构建该站**不需要** `--skip`
  （与 `prompts` 站不同：那个站的数据源本身不入库）。
- **中图为上游档位**：`sites.json` 的 `tiers` 已含 `mid`，
  `tools/mid.py` 会跳过本站（不覆盖上游提供的文件）。
- **宽高比分面**：官网 Explore 榜不提供官方分类，宽高比是唯一稳定可枚举的维度。
