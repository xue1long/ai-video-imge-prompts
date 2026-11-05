# MEMORY — ai-image-gallery

> 只记经源码核实的结论与硬约束。

## 定位

单仓多站 AI 绘画素材库，一仓构建九站图库，中日双语浅深双主题。线上 photoai.life；唯一远程 origin：github.com/xue1long/ai-video-imge-prompts。代码 MIT，素材逐站授权不同。

## 栈 / 目录 / 命令

Py3.8+ 纯标准库，唯一第三方依赖 Pillow（仅 `tools/mid.py` 生成中图）。纯静态站点，单站一 `index.html` + 数据内嵌，无框架/CDN/前端构建。CI：ubuntu-24.04 + Py3.8/3.13 + Node22。

- `sites.json` 唯一清单；`sites/<id>/` 九站 `scripts/`(build_gallery/extract/manifest)+`data/`+产物+`manifest.json`+NOTICE/LICENSE
- `shared/`(landing、image_policy、pose_*)、`hub/`(build_hub.py)、`index/`(sync/catalog/check_wiring)、`tools/`(fetch/mid/verify/build/release/update/serve)
- `tests/run.py`（唯一回归，不依赖图片）、`docs/ADDING_A_SITE.md`、`docs/adr/`（决策记录须含替代方案与后果）、`CONTEXT.md`（唯一术语表）、`AGENTS.md`（命令与闸门）

命令链 `fetch.py`(首 6.8 GB)→`mid.py`→`build.py`→`release.py`(dist/)→`serve.py`(127.0.0.1:8080)→`tests/run.py`。**验收必须走 `tools/serve.py`**（file:// 与 http:// 行为不同）。

## 九站（`sites.json`）

|id|code|规模|license|tiers / imageDirs|落地页|
|---|---|---|---|---|---|
|portrait|PORTRAIT-DB-01|1499|cc0|thumb,full / thumbs,mid,img|有|
|costume|COSTUME-DB-01|1407|restricted|thumb,img,png / thumbs,img,png|有|
|pose|POSE-DB-01|288|restricted|thumb,full / thumbs,mid,img|有|
|pose-depth|POSE-DB-02|288|restricted|thumb,full / thumbs,mid,img|有|
|shisei|SHISEI-v0.3.0|280|cc0|thumb,mid,full / thumbs,mid,img|有|
|prompts|PROMPTS-DB-01|26458|conditional|thumb,full / thumbs,img|有|
|midjourney-explore|MJ-EXPLORE-01|400|restricted|thumb,mid / thumbs,mid|有|
|mj-styles|MJ-STYLES-01|329|restricted|thumb,full / styles|**无**（`"landing": false`）|
|prompthero-midjourney|PROMPTHERO-MJ-01|12998|restricted|thumb,mid / thumbs,mid|有|

## 规则

1. `sites.json` 唯一清单，tools/ 不为单站定制；图片不入库，首部署 `fetch.py`。
2. 取图策略三态（`shared/image_policy.py`，`imagePolicy` 声明）：local-first（站内优先，失败回上游）/online（直连上游）/local-only（默认）。`<字段>`=展示地址，`<字段>Url`=上游地址（仅 local-first），`<字段>Path`=站内路径（仅 online）。`tier_addr()` 只看 imagePolicy。online 档 manifest 不写 `<tier>_path`；取路径 `rec.get(tier+"_path") or ""`。`index/catalog.py` 的 file_specs 双键 `"full_path|full_url"` 必需。
3. `"landing": false` 是站能力声明 → `shared/landing.py` 的 `write_site()` 写空 `landing.json` → release/sitemap 收敛 → hub 不链 `browse/`；`tests/run.py` 双向校验（false 必须无落地页且磁盘无残留，true/未声明必须有）。
4. 产物与配置自洽：改 tiers/imageDirs/imagePolicy 须同步 `manifest.py`、`build_gallery.py` 的 `_addr()`、hub 产物；入库产物必须由已入库配置算出（hub `total_images()` 读 sites.json 的 tiers → 改档位即改总数，hub 产物跨主题）。
5. 隔离提交须 `git add -N` 登记新文件：`git commit --only` 只提交已跟踪路径，未跟踪新文件静默跳过且退出码 0。`-N` 须前移到变更检测前（否则 `git diff --quiet` 看不见新文件，整批漏）；`-N` 后普通 commit 那些文件不入库，真入库须普通 `git add -- <path>`。提交后 `git show --stat HEAD` 核文件数、`git ls-tree HEAD <dir>` 核目录内容。
6. 拆提交须逐提交重建产物（用该提交的中间态配置），否则闸门 4 必红；拆多主题文件用整块替换，勿 `git apply` 单 hunk。
7. 落地页清理只删孤儿，不 rmtree 整目录：safe-delete 按 tool call 累计文件数（阈值 50），逐文件删也累计；正解是正常构建删 0 个文件——读上次 landing.json 的 pages 只删差集。
8. `midOf` 必须真被调用，否则删掉。
9. prompts 自制图覆盖层：attach → `sites/prompts/sync_user_assets.py` 导出 `userimg/`+`data/user_assets.json`（originId 归属，入库）→ `build_gallery.py` 追加到分片 `files[]` 末尾标自制；不写进 `data/prompts_<key>.json`（导入器整份重写），不放 `img/<key>/`。
10. prompts 数据边界：`prompts_*.json`、`gallery_*.js`、抓取缓存忽略；仅 `manifest.json`、`gallery.js`、`landing.json`、`gpt2_categories.json` 入库。`tests/run.py` 不读不入库分片，判据用入库 manifest；`build.py --skip` 只给数据源不入库的站用。
11. Windows 行尾：`git diff --stat` 空但 `git status` 显示 M = CRLF 漂移，`git checkout --` 丢弃；入库清单 manifest.json 必须 `newline="\n"`，构建产物靠 `.gitattributes`+`core.autocrlf=true` 归一化。
12. 新增站按 `docs/ADDING_A_SITE.md`；姿势两站复用 `shared/pose_gallery.py`+`pose_source.py` 只写 `config.py`。

## CI 闸门（`.github/workflows/ci.yml`）

1 tests/run.py；2 tests/test_manager.py（需 Pillow）；3 `index/sync.py --force --db <tmp>`+`index/check_wiring.py`；4 `tools/build.py --skip prompts`（Py3.8）+`git diff --exit-code -- hub sites`；5 `tools/release.py --no-images`；6 `tools/update.py --check --no-fetch --ref HEAD`。**推论：改 sites/ 或 hub/ 的生成物必须同提交重建的结果。**

本地验闸门 4：clone 要 `--no-hardlinks`（`--local` 在 Windows 报 Improper link）；补丁须先提交（否则 diff 把本轮改动全算差异必红，与行尾漂移无关）；git diff 抓不到未跟踪新文件，须额外复制 `git ls-files --others --exclude-standard`；空目录加 `.gitkeep`；勿用 `git checkout-index`（检出 HEAD，必假红）。

## 平台坑（跨项目，完整版见用户级 MEMORY.md）

PowerShell stdout 不回流、git commit -m 多行截断、Edit 幻影成功须回查、PowerShell 不展开通配符、Remove-Item 静默失败改用 node fs.rmSync、git 代理端口每次变（用 env 端口单次覆盖）。

## 待办

`fetch.py` 后才见图片；`sites/portrait/NOTICE.md` 记原作者对再分发图片数据的要求，与 CC0 需并读；`tools/release.py --no-images` 仅供 CI，线上更新不可用。
