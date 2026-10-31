# AGENTS.md — AI 图片素材库（单仓多站）

> 本文件面向 AI 助手（WorkBuddy / CodeBuddy / Claude Code 等）在本仓库的作业说明。
> 人类贡献者请优先读 [README.md](README.md)（另有 `README_en.md` / `README_ja.md`）。

## 项目是什么

**一个仓库构建、构建五个 AI 绘画参考图库**：人像集 / 姿势集 / 深度姿势集 / 服装集 / Shisei CC0 姿势线稿，共 **15,241 张参考图**，中日双语、浅色 / 深色双主题。

- 线上入口：<https://photoai.life/>
- 仓库：<https://github.com/Brilliant666/ai-image-gallery>
- 许可：代码 MIT；**素材授权逐站不同**（见下表）

## 技术栈

- **Python 3.8+**：`tools/` 全部脚本只用标准库；只有 `tools/mid.py` 生成中图需要 **Pillow**（`pip install pillow`）。
- **输出是纯静态站点**：无框架、无 CDN、无外部字体，单站一个 `index.html` + 数据内嵌。
- 无 Node、无前端构建、无数据库。
- **CI**：GitHub Actions（`.github/workflows/ci.yml`），ubuntu-24.04 + Python 3.8/3.13 + Node 22。

## 五个站点（`sites.json` 是唯一清单）

| id | 名称 | 规模 | 素材授权 | imageDirs / tiers |
| --- | --- | --- | :---: | --- |
| `portrait` | 人像集 | 1,499 张（面部 893 / 造型 606） | **CC0** | thumbs, mid, img / thumb, full |
| `pose` | 姿势集 | 288 姿势 / 1,439 张（5 视角，`P018` 缺仰视，故为 1439 而非 1440） | 禁止再分发 | thumbs, mid, img / thumb, full |
| `pose-depth` | 深度姿势集 | 同批 288 姿势的深度图 / 1,439 张 | 禁止再分发 | thumbs, mid, img / thumb, full |
| `costume` | 服装集 | 1,407 件 / 4,221 张 / 86 标签 | 禁止再分发 | thumbs, img, png / thumb, img, png |
| `shisei` | Shisei CC0 姿势线稿 | 280 姿势 / 1,133 张（每姿势**最多** 5 视角，上游质检未过的视角不收录） | **CC0** | thumbs, mid, img / thumb, mid, full |

来源：portrait ← ai-portrait-gallery.pages.dev；pose ← ai-pose-gallery.pages.dev；pose-depth ← ai-pose-depth-gallery.pages.dev；costume ← ai-costume-gallery.pages.dev；shisei ← shisei.indaloop.app（GitHub `wquguru/shisei` v0.3.0，raw 源）。

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
├── tests/run.py        # 不依赖图片的检查（CI 每次推送都跑）
└── docs/ADDING_A_SITE.md  # 加第 N 个站的约定
```

## 常用命令

```bash
python tools/fetch.py      # 下载全部图片（首次约 6.8 GB，之后只补缺失）
python tools/mid.py        # 生成灯箱中图（约 290 MB）
python tools/build.py      # 构建五个站 + 入口页
python tools/release.py    # 组装 dist/
python tools/serve.py      # 预览 http://127.0.0.1:8080/
python tests/run.py        # 不依赖图片的检查
```

常用参数：`--site pose` 只处理单站；`--base https://x.com` 指定正式域名（写入 canonical / og / sitemap）；`--root sites/pose` 预览单站；`--out <目录>` 指定发布目录；`--tier thumb` 只下缩略图（约 90 MB）。

**验收必须用 `serve.py`**，不要直接双击 `dist/index.html` —— `file://` 与 `http://` 在相对路径、Content-Type、缓存上都有差异。

## CI 做什么（`.github/workflows/ci.yml`）

1. `python3.13 tests/run.py` —— 测试。
2. `python3.8 tools/build.py` 后 `git diff --exit-code -- hub sites` —— **最低版本 Python 构建产物必须与仓库一致**，不一致直接失败（这是防「忘记提交构建产物」的闸门）。
3. `python3.13 tools/release.py --no-images --out /tmp/dist-ci` —— 图片不入库，CI 只验证发布脚本能跑通。
4. `python3.13 tools/update.py --check --no-fetch --ref HEAD` —— 干净检出下的更新检查。

> **推论：任何改动 `sites/` 或 `hub/` 生成物的提交，都必须同时提交重新构建后的产物。**

## 关键规则

1. **`sites.json` 是唯一清单。** 站点增删、顺序、授权、档位、图片目录全部在这里声明；`tools/` 不为单个站点定制逻辑。
2. **图片不进仓库。** `.gitignore` 排除 `sites/*/{thumbs,mid,img,png,raw}/`；首次部署用 `tools/fetch.py` 拉取，之后幂等跳过。
3. **档位与 manifest 的约定只有一条**：每条记录对 `sites.json` 里每个 `<tier>` 都要有 `<tier>_url` 与 `<tier>_path`。`fetch.py` / `verify.py` 只靠这条规则工作。
4. **新增站点**按 `docs/ADDING_A_SITE.md`：建 `sites/<id>/`（`scripts/build_gallery.py` 必填、`extract.py`/`manifest.py` 按需、`data/`、`index.html`、`LICENSE`、`NOTICE.md`、`README.md`），在 `sites.json` 追加一条，然后跑 `tools/build.py`。**`tools/` 无需改动。**
5. **构建脚本读环境变量 `SITE_URL`**，站点根用 `dirname(dirname(__file__))` 自算，不依赖当前工作目录。
6. **姿势两站共用生成器**：结构相同直接复用 `shared/pose_gallery.py` + `shared/pose_source.py`，只写一份 `config.py`（参考 `sites/pose/config.py`）；数据来自别的项目、系列名不同时参考 `sites/shisei/config.py`（系列顺序、视角顺序、中文名表、作者、`blurRatings` 默认模糊都在配置里）。
7. **授权逐站不同**，改任何站都要看该站的 `NOTICE.md`：`portrait` 与 `shisei` 是 CC0 可商用可再分发；`pose` / `pose-depth` / `costume` **禁止再分发**。截图与素材不得从页面裁取另作他用。
8. **部署**：站点根 = `tools/release.py` 产出的 `dist/`（扁平结构：`index.html` + `portrait/` + `pose/` + …），nginx 不需要 `alias`。线上更新先发到暂存目录（`--out dist-stage`），检查后逐站原子换入 `dist/`。**git commit 即版本**，不用 `releases/<版本>/public` + `current` 软链。
9. **`release.py` 发布前会校验图片，缺图就中止**（只下了部分档位时加 `--skip-verify`）；它会先删除再重建目标站点目录。`--no-images` 只放站点文件、不放图片，**不能用来保留线上旧图**。

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
- `sites/portrait/NOTICE.md` 中，原作者对「再分发图片数据本身」另有**请求**（CC0 许可与该请求需并读）；`pose` / `pose-depth` / `costume` 明确禁止再分发。
- `hub/` 与 `sites/*/index.html` 都是生成产物。
