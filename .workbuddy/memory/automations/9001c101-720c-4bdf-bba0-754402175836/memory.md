# 每日采集自动化执行记录

任务：执行 `python scripts/daily_collect.py`（midjourney-explore 站每日采集流水线）
自动化 ID：9001c101-720c-4bdf-bba0-754402175836

## 2026-11-03（首次执行）

**结果**：退出码 0，采集 + 构建 + 提交 + 推送全部完成。累计 600 条作业 / 2400 张成图 / 3 个批次。

**但发现并修复了一个真实缺陷**（详见下）。修复前后共产生 2 个提交，均已推送到 origin/main。

### 缺陷：`git commit --only` 静默跳过未跟踪的新文件

- **现象**：首跑退出码 0、日志显示「已完成」，但 `data/daily/2026-11-03/` 与两个新 aspect 页
  （`3-5`、`70-99`）没进仓库 —— `git status` 显示它们仍是 `??`。
- **根因**：`git commit --only -- <paths>` 只提交**已被 git 跟踪**的路径；未跟踪的新文件被静默跳过，
  **退出码仍是 0**。该缺陷来自 `1effd23`（提交隔离改造）：改用 `--only` 时没考虑新文件。
  新批次目录每天新建，必然踩到。
- **为什么危险**：manifest.json 里已有该批次的作业数，批次源文件却没入库 →
  干净检出上 `tests/run.py::test_manifest_covers_all_daily` 断言失败（600 != 400），**CI 变红**。
  而脚本自己报成功、退出码 0 —— 定时任务看不出问题。
- **修复**：`scripts/daily_collect.py` 在变更检测**之前**用
  `git add --intent-to-add`（-N）登记新文件，再走 `git commit --only`。
  - `-N` 只登记路径不写入内容 → 保住「不碰暂存区」的隔离承诺（实测：别人已暂存的文件提交后仍留在暂存区）。
  - 必须在变更检测之前：`git diff --quiet` 看不见未跟踪文件，否则「本次只有新增文件」会被误判成「无变更」整批漏掉。
  - 变更检测改用 `git diff --quiet` 后仍能覆盖新文件（intent-to-add 后 diff 可见）。

### 已知遗留问题（与本次采集无关，pre-existing）

`tests/run.py` 有 2 项断言在干净检出上失败，**在 2026-11-02 之前就已存在**，非本次引入：

| 失败项 | 涉及站 | 原因 |
| --- | --- | --- |
| `test_declared_tiers_emit_their_upstream_address` | prompthero-midjourney | `full` 档声明 `online`，但产物里查不到上游地址 |
| `test_online_tier_keeps_the_local_path` | prompthero-midjourney | `full` 档直连上游，站内相对路径没留在产物里 |

根因：`sites/prompthero-midjourney/data/gallery_*.js`（分片）被 `.gitignore` 排除，
干净检出里只有 `gallery.js`（索引），地址只在分片里 → 断言查不到。
**归属**：另一个会话的 prompthero 站改动，不在本自动化范围内，未擅自修改。

### 验证记录（干净检出 `/tmp/ci-sim2`）

| CI 闸门 | 结果 |
| --- | --- |
| `tests/run.py` | manifest 覆盖断言已通过；余 2 项 pre-existing 失败 |
| `index/sync.py --force` + `check_wiring.py` | 通过（7 站核对一致） |
| `tools/build.py --skip prompts` + `git diff --exit-code -- hub sites` | 通过（退出码 0） |
| `tools/release.py --no-images` | 通过（78.6 MB） |
| `tools/update.py --check --no-fetch --ref HEAD` | 通过 |

## 后续运行注意

1. **必须校验「批次源文件是否入库」**，不能只看退出码：
   `git ls-files sites/midjourney-explore/data/daily/<日期>/` 应有输出。
2. `git diff --quiet` 变更检测看不见未跟踪文件 —— 修复已把 `-N` 登记前移，但若再改此处需重测。
3. 采集当天批次已存在时 `extract.py` 返回 3 → 脚本转 0，属正常跳过，不要用 `--force`。
4. 图片下载默认跳过（cdn.midjourney.com 被 Cloudflare 人机校验拦），full 档走 CDN 直链，站点展示不受影响。
