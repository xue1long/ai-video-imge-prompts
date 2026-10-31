# MEMORY — ai-image-gallery

> 项目长期记忆。只记录**经源码核实**的结论；不记流水账。
> 首次初始化：2026-10-31

## 项目定位

**单仓多站**的 AI 绘画参考素材库：一个仓库构建、构建五个图库，人像 / 姿势 / 深度姿势 / 服装 / Shisei CC0 姿势线稿，共 15,241 张参考图，中日双语、浅色 / 深色双主题。
线上入口：photoai.life ｜ 远程 `origin`：github.com/Brilliant666/ai-image-gallery
　另有一个远程 `target`：github.com/xue1long/ai-video-imge-prompts（2026-11-01 由本机首次推送，内容同源）
许可：代码 MIT；素材逐站授权不同。

## 技术栈与运行

| 项 | 值 |
| --- | --- |
| 语言 | **Python 3.8+**，`tools/` 全部脚本只用标准库 |
| 唯一第三方依赖 | `tools/mid.py` 生成中图需要 **Pillow**（`pip install pillow`） |
| 输出 | 纯静态站点，单站一个 `index.html` + 数据内嵌；无框架、无 CDN、无外部字体 |
| 前端 | 原生 JS，无前端构建、无 Node（CI 里的 Node 22 仅用于检查内联 JS 语法） |
| CI | `.github/workflows/ci.yml`：ubuntu-24.04、Python 3.8 + 3.13、Node 22 |
| .gitignore | `sites/*/{thumbs,mid,img,png,raw}/`、`dist/`、`sites/*/dist/`、`*.zip`、`__pycache__/`、`.venv/` |

## 目录

- `sites.json` — **唯一清单**（站点、顺序、授权、档位、图片目录、封面、统计）
- `sites/<id>/` — 5 个子站：`scripts/`（build_gallery.py / extract.py / manifest.py）+ `data/` + 构建产物（index.html、404.html、robots.txt、sitemap.xml）+ `manifest.json` / `manifest.csv` + `NOTICE.md` + `README.md` + `LICENSE`
- `shared/` — `assets.py`（下载与校验）、`landing.py`（静态落地页）、`pose_gallery.py`（姿势两站生成器）、`pose_i18n.py`（日→中翻译，含 288 个姿势名）、`pose_seo.py`、`pose_source.py`
- `hub/` — 入口页生成器 `build_hub.py` + `make_icons.py` + 入口页资源（index.html / robots.txt / sitemap.xml / llms.txt / 图标 / og-cover）
- `tools/` — `fetch.py` `mid.py` `verify.py` `build.py` `release.py` `update.py` `serve.py` `_common.py`
- `deploy/` — `DEPLOY.md` + `nginx.conf`
- `tests/run.py` — 不依赖图片的检查
- `docs/ADDING_A_SITE.md` + `docs/screenshots/`

## 命令

```bash
python tools/fetch.py      # 下载图片，首次约 6.8 GB，之后只补缺失
python tools/mid.py        # 生成中图，约 290 MB
python tools/build.py      # 构建五站 + 入口页
python tools/release.py    # 组装 dist/（图片硬链接）
python tools/serve.py      # 预览 http://127.0.0.1:8080/
python tests/run.py        # 不依赖图片的检查
```

参数：`--site <id>`、`--base <url>`（写入 canonical / og / sitemap，默认 `https://example.com`）、`--no-hub`、`--tier thumb`（仅缩略图约 90 MB）、`--out <dir>`、`--skip-verify`、`--no-images`、`--root <dir>`、`--check --no-fetch --ref HEAD`。

**验收必须走 `tools/serve.py`**（`file://` 与 `http://` 在相对路径、Content-Type、缓存上行为不同）。

## 五个站点（`sites.json`）

| id | code | 规模 | license | tiers / imageDirs |
| --- | --- | --- | --- | --- |
| `portrait` | PORTRAIT-DB-01 | 1499 张（面部 893 / 造型 606） | **cc0** | thumb, full / thumbs, mid, img |
| `pose` | POSE-DB-01 | 288 姿势 / 1439 张（5 视角，P018 缺仰视） | restricted | thumb, full / thumbs, mid, img |
| `pose-depth` | POSE-DB-02 | 同批 288 姿势深度图 / 1439 张 | restricted | thumb, full / thumbs, mid, img |
| `costume` | COSTUME-DB-01 | 1407 件 / 4221 张 / 86 标签 | restricted | thumb, img, png / thumbs, img, png |
| `shisei` | SHISEI-v0.3.0 | 280 姿势 / 1133 张（每姿势最多 5 视角，上游质检未过的不收录） | **cc0** | thumb, mid, full / thumbs, mid, img |

来源域名：portrait ← `ai-portrait-gallery.pages.dev`；pose ← `ai-pose-gallery.pages.dev`；pose-depth ← `ai-pose-depth-gallery.pages.dev`；costume ← `ai-costume-gallery.pages.dev`；shisei ← `shisei.indaloop.app`（raw 源 `raw.githubusercontent.com/wquguru/shisei/v0.3.0/`）。
作者：portrait あぎ（@agi_aibusi）；pose / pose-depth / costume ギア（@giaaibusi）；shisei Shisei（github.com/wquguru）。

## 关键规则

1. **`sites.json` 是唯一清单**，`tools/` 不为单站定制逻辑。
2. **图片不入库**，首次部署用 `fetch.py` 拉取。
3. **档位与 manifest 只有一条规则**：每条记录对每个 `<tier>` 都要有 `<tier>_url` 与 `<tier>_path`；`fetch.py` / `verify.py` 只靠这条工作。
4. **构建脚本读环境变量 `SITE_URL`**；站点根用 `dirname(dirname(__file__))` 自算。
5. **新增站点**按 `docs/ADDING_A_SITE.md`；姿势两站复用 `shared/pose_gallery.py` + `shared/pose_source.py`，只写 `config.py`（参考 `sites/pose/config.py`；跨来源站参考 `sites/shisei/config.py`，含系列顺序、视角顺序、中文名表、作者、`blurRatings` 默认模糊）。
6. **授权逐站不同**：`portrait` / `shisei` 为 CC0；`pose` / `pose-depth` / `costume` 禁止再分发。
7. **部署**：站点根 = `release.py` 产出的扁平 `dist/`（`index.html` + `portrait/` + `pose/` + …），nginx 不需要 `alias`；**git commit 即版本**；更新先发 `--out dist-stage` 再逐站原子换入。
8. `release.py` 发布前校验图片，缺图中止；会先删后建目标站点目录。`--no-images` 不保留线上旧图。
9. **prompts 站的自制图走覆盖层**：素材管理器 attach → `sites/prompts/sync_user_assets.py` 导出 `userimg/` + `data/user_assets.json`（按 originId 归属，**两者都入库**）→ `build_gallery.py` 追加到分片 `files[]` 末尾并标「自制」。**不写进 `data/prompts_<key>.json`**（导入器会整份重写），**不放 `img/<key>/`**（目录名即分片键）。授权上 `img/` 全 CC BY 4.0、`userimg/` 归本站，NOTICE 已分开写明。

## CI 闸门（`ci.yml`）

1. `python3.13 tests/run.py`
2. `python3.8 tools/build.py --skip prompts` + `git diff --exit-code -- hub sites` → **最低版本 Python 的构建产物必须与仓库一致**（跳过 prompts 是因为它的数据源不入库，干净检出上构建必然失败；其余五站照常逐文件比对）
3. `python3.13 tools/release.py --no-images --out /tmp/dist-ci`
4. `python3.13 tools/update.py --check --no-fetch --ref HEAD`

**推论：改 `sites/` 或 `hub/` 的生成物必须同提交重新构建的结果。**

## prompts 站的数据边界（2026-10-31 定）

| 类别 | 文件 | 体积 | git |
| --- | --- | ---: | --- |
| 抓取中间数据 | `data/prompts_<key>.json` | 132 MB | **忽略**（`import_youmind.py` 重拉） |
| 构建产物 | `data/gallery_<key>.js` | 84 MB | **忽略**（`build_gallery.py` 重建） |
| 映射/缓存 | `data/<key>_id2cats.json`、`data/dims.json` | 4 MB | **忽略** |
| 抓取缓存 | `data/<key>_site_meta.json`、`*_site_categories.json` | 103 MB | **忽略** |
| 图片清单 | `manifest.json` | 14 MB | **入库**（`fetch.py` 与 `tests/run.py` 都要读） |
| 分片索引 | `data/gallery.js`（275 B）、`data/landing.json`、`data/gpt2_categories.json` | <5 KB | **入库** |

做完忽略后 `sites/prompts/` 只有 35 个文件 13.6 MB 入库（其中 13.1 MB 是 manifest）。
`tests/run.py::GitIgnore` 两项就是守这条线的：大文件必须被忽略、manifest 与 gallery.js 必须入库。
`build.py` 的 `--skip <id>` 只给「数据源不在仓库」的站用，别拿它绕过构建校验。

## Windows 上的行尾漂移（提交前必查）

构建脚本 `open(...,"w")` 在 Windows 上把 LF 写成 CRLF，构建后 `git status` 会冒出
30 个 `M sites/*/index.html`。**这类改动只有行尾、没有内容，提交就是 bug**
——CI 在 Linux 上产出 LF，会和仓库里的 CRLF 打架，`git diff --exit-code -- hub sites` 必挂。

判定：`git diff --stat -- <path>` 为空但 `git status` 显示 `M`。
处理：`git checkout -- <path>` 丢弃。这是跨平台常态，不打算改构建脚本的换行策略。

## 性能约定

三档：缩略图 ~10–20 KB；中图 ~10–150 KB；原图 ~95 KB–3.2 MB。
中图：服装集来自原站，其余三站由 `tools/mid.py` 生成（最长边 1600px，WebP 质量 82）。中图缺失时灯箱退回原图。
交互：悬停 120 ms / 按下 / 键盘选中即预取中图。

## 与其他项目的关系

- 同系列的独立镜像仓库：`ai-portrait-gallery-cn`、`ai-pose-gallery-cn`、`ai-pose-depth-gallery-cn`、`ai-costume-gallery-cn`（本仓已包含其 `sites/costume/`）。
- **本仓是主仓**：多站联动改动在此进行。

## 待办 / 注意事项

- 克隆后必须先 `fetch.py` 才能看到图片内容（**素材**图片不入库；但仓库含 25 个 UI / og 封面 / 界面截图图片文件）。
- `sites/portrait/NOTICE.md` 记载原作者对「再分发图片数据本身」的请求，与 CC0 许可需并读。
- `tests/run.py` 是唯一的自动化回归，不依赖图片，适合本地快速跑。
- `tools/release.py` 的 `--no-images` 仅用于 CI 验证，**线上更新不可使用**。
