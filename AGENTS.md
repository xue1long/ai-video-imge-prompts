# AGENTS.md — AI 图片素材库（单仓多站）

> 本文件面向 AI 助手（WorkBuddy / CodeBuddy / Claude Code 等）在本仓库的作业说明。
> 人类贡献者请优先读 [README.md](README.md)（另有 `README_en.md` / `README_ja.md`）。

## 项目是什么

**一个仓库构建、构建六个 AI 绘画参考图库**：人像集 / 姿势集 / 深度姿势集 / 服装集 / Shisei CC0 姿势线稿 / 提示词生图集，共 **56,502 张参考图**，中日双语、浅色 / 深色双主题。

- 线上入口：<https://photoai.life/>
- 仓库：<https://github.com/Brilliant666/ai-image-gallery>
- 许可：代码 MIT；**素材授权逐站不同**（见下表）

## 技术栈

- **Python 3.8+**：`tools/` 全部脚本只用标准库；`tools/mid.py` 生成中图、`index/actions.py` 生成导入缩略图需要 **Pillow**（`pip install pillow`）。
- **输出是纯静态站点**：无框架、无 CDN、无外部字体，单站一个 `index.html` + 数据内嵌（例外：`prompts` 站的 4.1 万张图外置为**按模型分片**的 `data/gallery_<key>.js`，`data/gallery.js` 只是模型索引；进站只加载默认模型，切模型时按需注入，`JSON.parse` 加载 + 每批 240 条增量渲染，index.html 保持约 40KB）。
- 静态站无 Node、无前端构建。**`index/`（本地素材管理器）是唯一的数据库应用**：SQLite 单文件 `gallery.db`（标准库 `sqlite3`），HTTP 用标准库 `http.server`，前端仍是单文件原生 JS。
- **CI**：GitHub Actions（`.github/workflows/ci.yml`），ubuntu-24.04 + Python 3.8/3.13 + Node 22。

## 六个站点（`sites.json` 是唯一清单）

| id | 名称 | 规模 | 素材授权 | imageDirs / tiers |
| --- | --- | --- | :---: | --- |
| `portrait` | 人像集 | 1,499 张（面部 893 / 造型 606） | **CC0** | thumbs, mid, img / thumb, full |
| `pose` | 姿势集 | 288 姿势 / 1,439 张（5 视角，`P018` 缺仰视，故为 1439 而非 1440） | 禁止再分发 | thumbs, mid, img / thumb, full |
| `pose-depth` | 深度姿势集 | 同批 288 姿势的深度图 / 1,439 张 | 禁止再分发 | thumbs, mid, img / thumb, full |
| `costume` | 服装集 | 1,407 件 / 4,221 张 / 86 标签 | 禁止再分发 | thumbs, img, png / thumb, img, png |
| `shisei` | Shisei CC0 姿势线稿 | 280 姿势 / 1,133 张（每姿势**最多** 5 视角，上游质检未过的视角不收录） | **CC0** | thumbs, mid, img / thumb, mid, full |
| `prompts` | 提示词生图集 | 26,458 条提示词 / 41,261 张（两个模型：Imge-2 22,268 张 / Nano Banana 18,993 张，两者都有 41 个官方分类；一条提示词的全部成图归为一条素材；数据按模型分片 `data/gallery_<key>.js`，缩略图来自上游 CDN；另有站主自制图放 `userimg/`、灯箱标「自制」，**不在 CC BY 4.0 内**） | **CC BY 4.0**（须署名） | thumbs, img / thumb, full |

来源：portrait ← ai-portrait-gallery.pages.dev；pose ← ai-pose-gallery.pages.dev；pose-depth ← ai-pose-depth-gallery.pages.dev；costume ← ai-costume-gallery.pages.dev；shisei ← shisei.indaloop.app（GitHub `wquguru/shisei` v0.3.0，raw 源）；prompts ← youmind.com（两条模型线：`gpt-image-2-prompts` / `nano-banana-pro-prompts`，YouMind 官方 API `youmarketing-api/prompts`，`cms-assets.youmind.com` 图源，`imageBase` 已声明；分类靠 `categories` 参数逐类反查，见 `sites/prompts/tag_categories.py`）。

## 目录结构

```
ai-image-gallery/
├── sites.json          # ★ 唯一清单：站点、顺序、授权、档位、封面
├── sites/<id>/         # 各站：scripts/ + data/ + 构建产物 + NOTICE.md + README
├── shared/             # 各站共用逻辑
│   ├── assets.py       #   共用下载与校验（档位→manifest 字段只有一条规则：<tier>_url / <tier>_path）
│   ├── landing.py      #   共用静态落地页生成（不依赖 JS 的分面页）
│   ├── pose_gallery.py #   姿势 / 深度姿势共用页面生成器
│   ├── pose_i18n.py    #   日→中翻译表（系列 / 分类 / 视角 / 288 个姿势名）
│   ├── pose_seo.py     #   姿势两站共用 SEO 落地页
│   └── pose_source.py  #   姿势两站共用的原站解析与 manifest 生成
├── hub/                # 入口页生成器（build_hub.py / make_icons.py）+ 入口页资源
├── tools/
│   ├── fetch.py        #   下载图片（幂等；首次约 6.8 GB）
│   ├── mid.py          #   生成灯箱中图（约 290 MB，需 Pillow）
│   ├── verify.py       #   校验图片存在性、体积、可读宽高、中图齐全
│   ├── build.py        #   构建各站 index.html + 数据导出 + SEO 文件，并重建入口页
│   ├── release.py      #   组装 dist/（图片硬链接，不额外占盘）
│   ├── update.py       #   服务器更新：拉上游但不覆盖手改文件
│   └── serve.py        #   以 dist/ 为站点根起本地 HTTP 服务
├── deploy/             # DEPLOY.md 部署手册 + nginx.conf
├── index/              # 本地素材管理器（唯一用数据库的部分）
│   ├── catalog.py      #   ★ 字段映射表唯一来源：6 份 manifest → 统一 CSV
│   ├── sync.py         #   manifest → gallery.db（复用上表的映射，不重写）
│   ├── store.py        #   唯一碰 SQL 的模块：建表、写入、查询
│   ├── serve.py        #   11 个端点 + 静态页面（单进程同源，端口 8787）
│   ├── actions.py      #   只碰磁盘：送素材（硬链接）、导入（缩略图/PNG 文本块）
│   ├── verify.py       #   探缺图：把不在盘的资产标 missing
│   ├── snapshot.py     #   DB 快照到 backups/
│   └── web/index.html  #   单文件三栏界面（零构建）
├── tests/run.py        # 不依赖图片的检查（CI 每次推送都跑）
├── tests/test_manager.py  # 素材管理器：只走 HTTP 接缝，用临时迷你数据根
└── docs/ADDING_A_SITE.md  # 加第 N 个站的约定
```

## 常用命令

```bash
python tools/fetch.py      # 下载全部图片（首次约 7.4 GB，之后只补缺失）
python tools/mid.py        # 生成灯箱中图（约 290 MB）
python tools/build.py      # 构建六个站 + 入口页
python tools/release.py    # 组装 dist/
python tools/serve.py      # 预览 http://127.0.0.1:8080/
python tests/run.py        # 不依赖图片的检查
python index/sync.py       # 素材管理器：manifest → gallery.db（签名未变则跳过）
python index/serve.py      # 素材管理器：http://127.0.0.1:8787/（或双击 启动.bat）
python index/verify.py     # 素材管理器：探缺图，只改 asset.status
python index/snapshot.py   # 素材管理器：DB 快照到 backups/
python tests/test_manager.py  # 素材管理器测试（需 Pillow），只走 HTTP 接缝
```

自建图导出：`cd sites/prompts && python sync_user_assets.py`（`--dry-run` 只打印、`--prune` 清旧图），再重建 prompts 站。

常用参数：`--site pose` 只处理单站；`--skip prompts` 跳过某站（逗号分隔可多个，CI 用）；`--base https://x.com` 指定正式域名（写入 canonical / og / sitemap）；`--root sites/pose` 预览单站；`--out <目录>` 指定发布目录；`--tier thumb` 只下缩略图（约 90 MB）。

**验收必须用 `serve.py`**，不要直接双击 `dist/index.html` —— `file://` 与 `http://` 在相对路径、Content-Type、缓存上都有差异。

## CI 做什么（`.github/workflows/ci.yml`）

1. `python3.13 tests/run.py` —— 测试。
2. `python3.13 tests/test_manager.py`（先 `pip install pillow`）—— 素材管理器的 HTTP 接口测试。
3. `python3.8 tools/build.py --skip prompts` 后 `git diff --exit-code -- hub sites` —— **最低版本 Python 构建产物必须与仓库一致**，不一致直接失败（这是防「忘记提交构建产物」的闸门）。**跳过 prompts 是因为它的数据源不入库**（`data/prompts_*.json` 132 MB + `data/gallery_*.js` 84 MB 都可由脚本重拉），干净检出上构建它必然失败；其余五站照常逐文件比对。
4. `python3.13 tools/release.py --no-images --out /tmp/dist-ci` —— 图片不入库，CI 只验证发布脚本能跑通。
5. `python3.13 tools/update.py --check --no-fetch --ref HEAD` —— 干净检出下的更新检查。

> **推论：任何改动 `sites/` 或 `hub/` 生成物的提交，都必须同时提交重新构建后的产物。**

## 关键规则

1. **`sites.json` 是唯一清单。** 站点增删、顺序、授权、档位、图片目录全部在这里声明；`tools/` 不为单个站点定制逻辑。
2. **图片不进仓库。** `.gitignore` 排除 `sites/*/{thumbs,mid,img,png,raw}/`；首次部署用 `tools/fetch.py` 拉取，之后幂等跳过。图源被 DNS 污染时设环境变量 `FETCH_PROXY`（如 `http://127.0.0.1:7897`）统一走代理。
3. **档位与 manifest 的约定只有一条**：每条记录对 `sites.json` 里每个 `<tier>` 都要有 `<tier>_url` 与 `<tier>_path`。`fetch.py` / `verify.py` 只靠这条规则工作。
4. **新增站点**按 `docs/ADDING_A_SITE.md`：建 `sites/<id>/`（`scripts/build_gallery.py` 必填、`extract.py`/`manifest.py` 按需、`data/`、`index.html`、`LICENSE`、`NOTICE.md`、`README.md`），在 `sites.json` 追加一条，然后跑 `tools/build.py`。**`tools/` 无需改动。**
5. **构建脚本读环境变量 `SITE_URL`**，站点根用 `dirname(dirname(__file__))` 自算，不依赖当前工作目录。
6. **姿势两站共用生成器**：结构相同直接复用 `shared/pose_gallery.py` + `shared/pose_source.py`，只写一份 `config.py`（参考 `sites/pose/config.py`）；数据来自别的项目、系列名不同时参考 `sites/shisei/config.py`（系列顺序、视角顺序、中文名表、作者、`blurRatings` 默认模糊都在配置里）。
7. **授权逐站不同**，改任何站都要看该站的 `NOTICE.md`：`portrait` 与 `shisei` 是 CC0 可商用可再分发；`pose` / `pose-depth` / `costume` **禁止再分发**；`prompts` 是 **CC BY 4.0**（可商用、**必须署名**——灯箱逐条展示作者与来源，再分发时保留署名）。截图与素材不得从页面裁取另作他用。
8. **部署**：站点根 = `tools/release.py` 产出的 `dist/`（扁平结构：`index.html` + `portrait/` + `pose/` + …），nginx 不需要 `alias`。线上更新先发到暂存目录（`--out dist-stage`），检查后逐站原子换入 `dist/`。**git commit 即版本**，不用 `releases/<版本>/public` + `current` 软链。
9. **`release.py` 发布前会校验图片，缺图就中止**（只下了部分档位时加 `--skip-verify`）；它会先删除再重建目标站点目录。`--no-images` 只放站点文件、不放图片，**不能用来保留线上旧图**。
10. **素材管理器的边界写在目录结构里**：`sites/` 只读（采集素材永不物理删除，只做视图隐藏）；`library/` 可写（导入素材允许删除）。任何代码路径都不得删除 `volume=sites` 的文件。
11. **`index/catalog.py` 的 `SOURCES` 是字段映射的唯一来源**，`sync.py` 复用它，不另写一份。加第 7 个集合时映射表加一条即可。
12. **`sync` 必须保住用户标注**：全量重建前把 `manual`/`auto` 标签、收藏、视图隐藏、`own` 集合存进临时表并在重建后放回（`store.reset` / `restore_user_data`）。否则「加一张图」会把几百小时的打标抹掉。
13. **manifest 里的路径是站点相对的**（`img/...`，不是 `sites/<id>/img/...`）。`sync` 负责加 `sites/<集合>/` 前缀；漏了会让 `pose` 与 `pose-depth` 被当成同一批文件去重。
14. **prompts 站的抓取与构建中间数据不入库**：`data/prompts_*.json`（132 MB）、`data/gallery_*.js`（84 MB）、`data/dims.json`、`data/*_id2cats.json` 合计约 220 MB，都能由 `import_youmind.py` / `scripts/manifest.py` / `build_gallery.py` 重新生成，`.gitignore` 已排除。**入库的只有 `manifest.json`（14 MB，`fetch.py` 与测试都要读它）**、`data/gallery.js`、`data/landing.json`、`data/gpt2_categories.json` 和页面本身。所以 CI 构建带 `--skip prompts`，全新克隆要先把数据拉下来才能本地构建该站 —— 这是有意的取舍，不是漏提交。
15. **给提示词加自己的成图走覆盖层，不改上游数据**：素材管理器「添加图片」（`POST /api/items/{id}/attach`）把图存进 `library/`，`sites/prompts/sync_user_assets.py` 导出成 `userimg/` + `data/user_assets.json`（按 originId 归属，两者都入库），`build_gallery.py` 再把它们追加到该提示词的 `files[]` 末尾。**绝不写进 `data/prompts_<key>.json`** —— 那是 `import_youmind.py` 的产物，每次重抓整份重写。图片放 `userimg/` 而不是 `img/<key>/`：后者目录名就是模型分片键，混进去会被当成新模型，且 `fetch.py` 只认 manifest 里的文件。

## 性能约定（三档图）

| 档位 | 人像 | 姿势 | 深度姿势 | 服装 |
| --- | ---: | ---: | ---: | ---: |
| 缩略图 | ~20 KB | ~17 KB | ~11 KB | ~10 KB |
| 中图 | ~150 KB | ~33 KB | ~10 KB | ~90 KB |
| 原图 | ~3.2 MB | ~450 KB | ~95 KB | ~1 MB |

灯箱打开时先显示清晰缩略图，中图到达后淡入；鼠标悬停 120 ms / 手指按下 / 键盘选中即开始预取中图。服装集的中图来自原站，其余三站由 `tools/mid.py` 从原图生成（最长边 1600px，WebP 质量 82）。

## 边界

- 素材著作权归各原作者，本项目为个人学习用途的镜像；**代码 MIT，素材按各原站条件使用**。
- 仓库**不含素材图片**（thumbs / mid / img / png 全部不入库），克隆后必须先 `fetch.py` 才能看到内容；但仓库**含 25 个 UI 与文档图片**：`hub/` 的 og-cover / favicon / apple-touch-icon / icon-512、各站 `og-cover.jpg`、`docs/screenshots/` 11 张界面截图。
- `sites/portrait/NOTICE.md` 中，原作者对「再分发图片数据本身」另有**请求**（CC0 许可与该请求需并读）；`pose` / `pose-depth` / `costume` 明确禁止再分发；`prompts` 为 CC BY 4.0，署名要求见 `sites/prompts/NOTICE.md`。
- `hub/` 与 `sites/*/index.html` 都是生成产物。
