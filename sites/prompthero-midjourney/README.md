# PromptHero Midjourney 提示词集（PROMPTHERO-MJ-01）

Midjourney 提示词与成图对照集。收录 12,998 条提示词（含成人内容 2,841 条），
覆盖 v1–v7 与 Niji 模式，按 14 个分类与 13 个版本筛选，提示词原文可直接复制。

- 线上：<https://photoai.life/prompthero-midjourney/>
- 原站：<https://prompthero.com/midjourney-prompts>
- 授权：**禁止再分发**（详见 [NOTICE.md](NOTICE.md)）

## 目录

```
sites/prompthero-midjourney/
├── config.py               # 文案、分类中文名表、NSFW 策略、采集端点配置
├── scripts/
│   ├── extract.py          # 从上游 tRPC 接口采集元数据 → data/prompts.json
│   ├── manifest.py         # data/prompts.json → manifest.json（另出 manifest.csv，不入库）
│   └── build_gallery.py    # 生成 index.html + 分类分片 + 落地页 + SEO 文件
├── data/
│   ├── prompts.json        # 采集到的元数据（入库）
│   ├── meta.json           # 采集统计
│   ├── gallery.js          # 分类与版本索引（入库）
│   └── gallery_<cat>.js    # 分类数据分片（不入库，由脚本重建）
├── browse/ cat/ ver/       # 静态落地页（由 shared/landing.py 生成）
├── thumbs/ mid/ img/       # 图片（不入库，用 tools/fetch.py 下载）
└── index.html              # 构建产物（入库）
```

## 重新采集

```bash
cd sites/prompthero-midjourney
python scripts/extract.py        # 采集全部（约 7 分钟，含退避重试）
python scripts/manifest.py       # 生成 manifest
```

需要出口 IP 时设代理：

```bash
FETCH_PROXY=http://127.0.0.1:7897 python scripts/extract.py
```

`extract.py` 串行抓取：上游在并发 6 时会返回 429，串行 + 指数退避可稳定跑完全量。
它采集两趟——SFW（默认过滤掉 `isNsfw`）与 NSFW（`nsfwOnly: true`）——两趟无交集。

## 下载图片

图片不进仓库，用仓库通用的脚本：

```bash
cd ../..
FETCH_PROXY=http://127.0.0.1:7897 python tools/fetch.py --site prompthero-midjourney
```

本地两档约 2.0 GB：缩略图 640 档 0.64 GB、中图 1080 档 1.34 GB。
原图（full，38.1 GB）**不在本地落地** —— 页面上的「下载原图」直连
cdn.prompthero.com（`sites.json` 的 `imagePolicy.full = online`），
所以 `fetch.py` 不会去下它，本地也不留副本。

## 构建

```bash
cd ../..
python tools/build.py --site prompthero-midjourney
python tools/release.py --site prompthero-midjourney
python tools/serve.py
```

数据量大，页面按分类分片懒加载：`index.html` 只内嵌索引（约 30 KB），
每个分类的数据在 `data/gallery_<cat>.js`，切换分类时才拉取。

## 设计要点

- **NSFW 默认模糊**：网格里成人条目默认 `blur(16px)`，点开单张或用页头开关才清晰；
  偏好记在 `localStorage`。
- **NSFW 不进落地页**：成人分类不生成静态页，也不出现在 `sitemap.xml` 与根 sitemap。
- **分片不入库**：`data/gallery_*.js` 由脚本重建，`.gitignore` 已排除；
  CI 构建该站时需 `--skip`（与 `prompts` 站同因：干净检出上分片不存在）。
- **两档回落**：上游有 26 条未生成衍生图、650 条没有 1080 档，
  manifest 里分别标 `thumbFallback` / `midFallback`，取图时回落。
- **多域名**：衍生图在 `img.prompthero.com`，原图在 `cdn.prompthero.com`，
  `sites.json` 用 `imageBases` 列出两个前缀。
