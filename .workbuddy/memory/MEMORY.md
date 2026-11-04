# MEMORY — ai-image-gallery

> 项目长期记忆。只记录**经源码核实**的结论；不记流水账。
> 首次初始化：2026-10-31

## 项目定位

**单仓多站**的 AI 绘画参考素材库：一个仓库构建、构建**九个**图库，人像 / 姿势 / 深度姿势 / 服装 / Shisei CC0 姿势线稿 / 提示词生图 / Midjourney 探索榜 / Midjourney 风格码库 / Midjourney 提示词集，中日双语、浅色 / 深色双主题。
线上入口：photoai.life ｜ 远程 `origin`：github.com/xue1long/ai-video-imge-prompts（唯一远程）
　2026-11-01 从 `github.com/Brilliant666/ai-image-gallery` 迁出，旧远程已删除
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

- `sites.json` — **唯一清单**（站点、顺序、授权、档位、图片目录、封面、统计、取图策略、站能力声明）
- `sites/<id>/` — 9 个子站：`scripts/`（build_gallery.py / extract.py / manifest.py）+ `data/` + 构建产物（index.html、404.html、robots.txt、sitemap.xml）+ `manifest.json` / `manifest.csv` + `NOTICE.md` + `README.md` + `LICENSE`
- `shared/` — `assets.py`（下载与校验）、`landing.py`（静态落地页）、`pose_gallery.py`（姿势两站生成器）、`pose_i18n.py`（日→中翻译，含 288 个姿势名）、`pose_seo.py`、`pose_source.py`
- `hub/` — 入口页生成器 `build_hub.py` + `make_icons.py` + 入口页资源（index.html / robots.txt / sitemap.xml / llms.txt / 图标 / og-cover）
- `tools/` — `fetch.py` `mid.py` `verify.py` `build.py` `release.py` `update.py` `serve.py` `_common.py`
- `deploy/` — `DEPLOY.md` + `nginx.conf`
- `tests/run.py` — 不依赖图片的检查
- `docs/ADDING_A_SITE.md` + `docs/screenshots/`
- `docs/adr/` — **架构决策记录**（NNNN-slug.md；每篇必须含「考虑过的替代方案」与「后果」，有测试守）
- `CONTEXT.md` — **唯一术语表**（只定义「是什么」，不定义「为什么」；`AGENTS.md` 与 `docs/REFACTOR_V7_LOCKED.md` 只引用不复述）

### 文档的三层分工

| 层 | 文件 | 写什么 | 不写什么 |
| --- | --- | --- | --- |
| 术语 | `CONTEXT.md` | 词义（「落地页」是什么） | 实现、决策 |
| 决策 | `docs/adr/` | 为什么这么做、替代方案、后果 | 词义 |
| 作业说明 | `AGENTS.md` | 命令、约束、闸门 | 术语定义（引用 CONTEXT.md） |

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

## 九个站点（`sites.json`）

| id | code | 规模 | license | tiers / imageDirs | 落地页 |
| --- | --- | --- | --- | --- | --- |
| `portrait` | PORTRAIT-DB-01 | 1499 张（面部 893 / 造型 606） | **cc0** | thumb, full / thumbs, mid, img | 有 |
| `costume` | COSTUME-DB-01 | 1407 件 / 4221 张 / 86 标签 | restricted | thumb, img, png / thumbs, img, png | 有 |
| `pose` | POSE-DB-01 | 288 姿势 / 1439 张（5 视角，P018 缺仰视） | restricted | thumb, full / thumbs, mid, img | 有 |
| `pose-depth` | POSE-DB-02 | 同批 288 姿势深度图 / 1439 张 | restricted | thumb, full / thumbs, mid, img | 有 |
| `shisei` | SHISEI-v0.3.0 | 280 姿势 / 1133 张（每姿势最多 5 视角，上游质检未过的不收录） | **cc0** | thumb, mid, full / thumbs, mid, img | 有 |
| `prompts` | PROMPTS-DB-01 | 26,458 条提示词 / 41,261 张 | CC BY 4.0 | thumb, full / thumbs, img | 有 |
| `midjourney-explore` | MJE-DB-01 | 799 作业 / 3196 张（按天累积） | restricted | thumb, mid / thumbs, mid | 有 |
| `mj-styles` | MJS-DB-01 | 329 码 × 3 张语义示例图 | restricted | thumb, full / styles | **无**（`"landing": false`） |
| `prompthero-midjourney` | PROMPTHERO-MJ-01 | 12,998 条提示词与成图 | restricted | thumb, mid / thumbs, mid | 有 |

来源域名：portrait ← `ai-portrait-gallery.pages.dev`；pose ← `ai-pose-gallery.pages.dev`；pose-depth ← `ai-pose-depth-gallery.pages.dev`；costume ← `ai-costume-gallery.pages.dev`；shisei ← `shisei.indaloop.app`（raw 源 `raw.githubusercontent.com/wquguru/shisei/v0.3.0/`）；prompts ← youmind.com；midjourney-explore ← midjourney.com/explore；mj-styles ← midjourney.com/explore（风格码，需登录态）；prompthero-midjourney ← prompthero.com/midjourney-prompts。
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
10. **隔离提交必须用 `git add --intent-to-add` 登记新文件**（2026-11-03 定）：`git commit --only -- <paths>` 只提交**已被 git 跟踪**的路径，未跟踪的新文件被**静默跳过且退出码仍是 0** —— 看着像成功，实际漏文件。新批次目录 `data/daily/<日期>/` 每天新建，必然踩到。`-N` 只登记路径不写内容，保住「不碰暂存区」的隔离承诺；**必须前移到变更检测之前**，否则 `git diff --quiet` 看不见新文件，「本次只有新增文件」会被误判成「无变更」整批漏掉。
    ⚠️ **`-N` 的另一面（2026-11-04 实测）**：`-N` 之后再跑**普通** `git commit`（不带 `--only`），那些文件**不会进提交** —— `-N` 只在索引里登记路径与空 blob，内容没写进去。`git show --stat` 里看不到它们，提交看起来成功。**`-N` 只用于「不碰暂存区的隔离提交」**；要真正入库必须用普通 `git add -- <path>`（写入内容）。每次提交后用 `git show --stat HEAD` 核验文件数与 `git ls-tree HEAD <dir>` 核验目录内容。
11a. **拆提交时构建产物要逐提交重建**（2026-11-04）：`hub/build_hub.py` 的 `total_images()` 读 `sites.json` 的 `tiers` —— 改某站的档位会让对外公布的总数变化，hub 产物因此**跨主题**。若某个提交只改了一部分配置却不重建 hub，该提交的产物与配置不自洽，CI 闸门 4（`build.py` + `git diff --exit-code -- hub sites`）必红。做法：**每个提交前用该提交对应的中间态配置重建一次**。
    拆 `tests/run.py` 这类多主题文件时，用**整块替换**而不是 `git apply` 单个 hunk —— patch 的 hunk 头带行号，单独 apply 会 "patch does not apply"；且 hunk 内的删除行可能**分散在上下文之间**，必须按「旧块 = 非 `+` 行」「新块 = 非 `-` 行」整块替换，每步断言命中次数为 1。
11. **取图策略三态**（`shared/image_policy.py`，`sites.json` 的 `imagePolicy` 声明）：
    `local-first`（站内路径优先，失败回上游）/ `online`（直连上游，本地不留副本）/ `local-only`（只用站内路径，默认）。
    编码约定：`<字段>`=展示地址；`<字段>Url`=上游地址（仅 local-first 写）；`<字段>Path`=站内路径（仅 online 写）。
    **`tier_addr()` 只看 `imagePolicy`**，不看 `tiers`/`imageDirs` —— 后两者只影响 `total_images()` 计数与 `fetch.py`/`verify.py` 的范围。
    **online 档的 manifest 不写 `<tier>_path`**：没有本地文件，写站内路径就是谎报，索引会拿它当本地文件去找、永远找不到。
    构建脚本取路径一律用 `rec.get(tier + "_path") or ""`（**严格索引遇到 online 档会 KeyError**）。
    `index/catalog.py` 的 `file_specs` **双键 `"full_path|full_url"` 是必需的** —— 单键的兜底推导要求 `_path` 形状，单键会让该档被静默跳过。
12. **`sites.json` 的 `"landing": false`** 是站能力声明（2026-11-04 新增，唯一配置源）：
    该站不生成落地页 → `shared/landing.py` 的 `write_site()` 写空 `landing.json` → release.py 与 sitemap 收敛 → hub 不链它的 `browse/`。
    `tests/run.py` **双向**校验：声明 false 必须没有落地页且磁盘不留目录，声明 true/未声明必须有。
13. **构建产物必须与配置自洽**：改了 `sites.json` 的 `tiers`/`imageDirs`，要同步改 `manifest.py`（写不写 `<tier>_path`）、`build_gallery.py`（`_addr()` 的取法）、`hub` 产物与文档。
    典型症状：配置说两档、入库 hub 按三档算 → CI 闸门 3（产物一致性）红。**入库的产物必须由已入库的配置算出。**
14. **`midOf` 必须真被调用**：定义了一份却没人用的路径规则等于没有规则，而且它会漂移（2026-11-04 发现 prompthero 的 `midOf` 描述的是别的站的 `img/` 布局，本站根本没有 `img/` 目录，算出来的路径必然 404）。
    `MidRule` 测试会跳过没有调用点的 `midOf`；更好的做法是直接删掉 —— 该站的中图若由上游直给（数据里的 `m` 字段），就没有「按路径复算」这回事。
15. **落地页清理只删孤儿，不做整目录 rmtree**（2026-11-04）：WorkBuddy 运行时的 safe-delete 闸门按 tool call **累计文件数**（阈值 50），`shutil.rmtree` 一次删几十个必然触发；**「逐文件删」也不能规避**（50 次单文件删照样累计到 50）。
    正解是**正常构建删 0 个文件** —— 读上次构建的 `data/landing.json` 的 `pages`，只删「上次有、这次没有」的差集。

## CI 闸门（`ci.yml`）

1. `python3.13 tests/run.py`
2. `python3.13 tests/test_manager.py`（需 Pillow）
3. `python3.13 index/sync.py --force --db <tmp>` + `python3.13 index/check_wiring.py --db <tmp>`
4. `python3.8 tools/build.py --skip prompts` + `git diff --exit-code -- hub sites` → **最低版本 Python 的构建产物必须与仓库一致**（跳过 prompts 是因为它的数据源不入库，干净检出上构建必然失败；其余八站照常逐文件比对）
5. `python3.13 tools/release.py --no-images --out /tmp/dist-ci`
6. `python3.13 tools/update.py --check --no-fetch --ref HEAD`

**推论：改 `sites/` 或 `hub/` 的生成物必须同提交重新构建的结果。**

**本地模拟干净检出**（改动未提交时验证闸门 4 的正确做法 —— 2026-11-04 修正过两次）：
```bash
TEMP=$(mktemp -d)
git clone --no-hardlinks --no-checkout <repo> "$TEMP/ci-clean-check"
git -C "$TEMP/ci-clean-check" checkout HEAD
git diff --binary HEAD > "$TEMP/ci.patch"                    # 含删除
git -C "$TEMP/ci-clean-check" apply --binary "$TEMP/ci.patch"
# 补未跟踪的新文件（git diff 抓不到，见下）
python - <<'PY'
import os, shutil, subprocess
SRC = r"E:/002-Pr/ai-video-imge-prompts"
DST = os.path.join(os.environ["TEMP"], "ci-clean-check")
for rel in subprocess.run(["git","-C",SRC,"ls-files","--others","--exclude-standard"],
        capture_output=True, text=True).stdout.split():
    if rel.startswith((".workbuddy",".scratch")): continue
    d = os.path.join(DST, rel); os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(os.path.join(SRC, rel), d)
PY
git -C "$TEMP/ci-clean-check" -c user.name=ci -c user.email=ci@local add -A
git -C "$TEMP/ci-clean-check" -c user.name=ci -c user.email=ci@local commit -q -m wip
cd "$TEMP/ci-clean-check" && python tools/build.py --skip prompts
git diff --exit-code -- hub sites                             # 必须为空
# 补一道 CI 没有的：构建后多出未跟踪文件也算失败（diff 抓不到新增文件）
test -z "$(git ls-files --others --exclude-standard -- hub sites)"
```
⚠️ **`git diff` 抓不到未跟踪的新文件** —— 新建的目录/文件（如 `docs/adr/`）会整个丢失，
验证会得出「绿」的假结论。必须**额外复制未跟踪文件**：
`git ls-files --others --exclude-standard` 逐个 `shutil.copy2` 过去。
⚠️ **git 不跟踪空目录** —— 只有目录没有文件的路径，链接在干净检出上必然失效。加 `.gitkeep` 占位。
⚠️ **测试不要读不入库的分片**（`data/gallery_<key>.js`）—— 干净检出上 FileNotFoundError。判据用入库的 manifest。
⚠️ **`git checkout-index` 检出的也是 HEAD** —— 工作区改动一个都进不去，验的是「旧代码 + 新测试」，
必然假红。别用它构造检出副本。
⚠️ **补丁必须提交，否则 `git diff --exit-code` 必红** —— 闸门比的是「构建产物 vs 仓库」，
前提是改动已提交。补丁以未暂存形式留着时，diff 会把本轮全部改动都算作差异
（实测 21 文件 / 13548 行删除），且 `--ignore-cr-at-eol` 前后完全一样 —— **不是行尾漂移，是方法错**。
⚠️ **`git clone --local`（默认）在 Windows 上失败** —— 走硬链接，报 `Improper link`。必须加 `--no-hardlinks`。

删除临时目录用 `node -e "fs.rmSync(dir,{recursive:true,force:true})"` —— `shutil.rmtree` 在有只读文件时会失败。

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

**入库文件例外**：`manifest.json` 这类**入库**的产物必须用 `newline="\n"` 写死行尾
（2026-11-04 给 prompthero 的 `manifest.py` 补上）。构建产物可以容忍（`.gitattributes`
的 `eol=lf` + `core.autocrlf=true` 会归一化），入库清单不行 —— 它要当数据源被别的脚本读。

**注意**：`git status` 里的 CRLF warning 与 `git diff --exit-code` 的结论无关。
`.gitattributes` 已声明 `* text=auto eol=lf`，`git diff --exit-code` 返回 0 就是真的无差异。

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
