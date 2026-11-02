# 重构方案 v1：静态图库 → 本地 WebUI 素材管理器

> ⚠️ **已被 [`REFACTOR_V2.md`](REFACTOR_V2.md) 取代，请勿按本文实施。**
> v1 的方案在自我复查后被推翻：sha256 去重是伪需求、FastAPI 属「熟悉而非必要」、`asset` 从属 `item` 无法表达 pose/pose-depth 同源、三档图写死三列与 6 站 tiers 不一致冲突。v2 保留了本文的现状诊断（第二、2.1 节实测数据仍然有效），重写了架构与实施路径。本文仅作推演过程留档。
>
> 状态：已废弃
> 编写日期：2026-10-31

## 一、结论先行

当前项目的本质是**一个静态站点编译器**：数据是构建期的输入，页面是构建期的产物，用户操作只能留在浏览器里。
你要的「素材管理器」需要的是**一个数据层是唯一真相的应用**：页面是数据的视图，任何操作即刻入库、可查询、可导出、可备份。

推荐路线：**渐进式重构，不推倒重写**。

- 保留：11.63 GB 图片资产（原位不动）、三档图（thumb/mid/full）现成可复用、6 套解析逻辑、`pose_i18n` 的 288 个姿势名翻译表
- 替换：`manifest.json` → SQLite；`build_gallery.py` 渲染 6 套 HTML → 1 套 SPA + API；`localStorage` → 数据库
- 降级：`hub/`、`landing.py`、`pose_seo.py`、`sitemap` 从「主链路」变成「可选导出器」

## 二、现状诊断（实测数据）

### 2.1 素材规模

| 集合 | 文件数 | 体积 | 记录条目 |
| --- | ---: | ---: | ---: |
| `portrait` | 3,079 | 4,660.0 MB | 1,499 |
| `prompts` | 44,576 | 4,979.6 MB | 15,118 提示词（22,268 图） |
| `costume` | 4,335 | 1,456.8 MB | 1,407 |
| `pose` | 2,906 | 661.0 MB | 1,439 |
| `pose-depth` | 2,905 | 147.7 MB | 1,439 |
| `shisei` | 768 | 6.9 MB | 1,133 |
| **合计** | **58,569** | **11.63 GB** | **约 29,185 个 asset / 22,035 个 item** |

### 2.2 为什么必须动架构

| 问题 | 实测证据 | 后果 |
| --- | --- | --- |
| 数据模型不统一 | 6 份 `manifest.json` 字段互不相同（`分区/发型/风格/宽/高`、`系列/分類/编号/姿势名/视角`、`id/title/prompt/thumb_url`） | 跨集合搜索、统一打标无从谈起 |
| 数据是构建产物 | `sites/*/index.html` 内嵌数据 30–360 KB；`prompts` 站外置 `data/gallery.js` **80 MB** | 改一个标签 = 重跑 extract + build + 重新下发 80 MB |
| 写操作无处落地 | 收藏 / 手动标签 / 回收站均在浏览器本地存储，键是图片路径 | 换浏览器即丢；无法跨设备、无法批量、无法备份 |
| 缺「作品」实体 | `prompts` 站一个提示词带 2 张图（`i13983_1` / `i13983_2`）被记成两条 | 收藏其一，另一条不知情 |
| UI 与数据耦合 | 6,225 行 Python 中，`portrait` 824 行、`prompts` 887 行、`pose_gallery` 1,026 行是三套独立 UI 生成器 | 加一个筛选条件要改三处 |
| 规模已越界 | 29,185 张图、22k 条记录 | 构建期生成的天花板已到 |

## 三、目标架构

```
┌─────────────────────────────────────────────┐
│  单页 WebUI（原生 JS，无框架、无构建）        │
│  collection 树 · 网格 · 分面 · 灯箱 · 批量    │
└───────────────┬─────────────────────────────┘
                │ JSON over HTTP（localhost）
┌───────────────▼─────────────────────────────┐
│  FastAPI                                     │
│  /api/items  /api/facets  /api/import        │
│  /media/{size}/{asset_id}（缩略图与中图）      │
└───────────────┬─────────────────────────────┘
                │
┌───────────────▼─────────────────────────────┐
│  SQLite（gallery.db）                        │
│  item / asset / tag / item_tag / favorite    │
└───────────────┬─────────────────────────────┘
                │ 只存路径，不搬文件
┌───────────────▼─────────────────────────────┐
│  sites/*/{thumbs,mid,img,png}  11.63 GB       │
└─────────────────────────────────────────────┘
```

启动方式：`python run.py`（或双击 `start.bat`）→ 自动打开 `http://127.0.0.1:8765/`。

**关键变化**：三档图已经存在磁盘上（`thumbs` / `mid` / `img`），**不需要重新生成**，服务端只做路径解析与磁盘缓存兜底。

## 四、统一数据模型

### 4.1 表结构

```sql
collection(id, slug, name, kind, sort_order, meta_json)
-- 6 个原有集合 + 用户自建集合

item(id, collection_id, title, prompt, prompt_raw,
     author, source_url, published_at, model,
     width, height, meta_json, created_at, deleted_at)
-- 一个「作品」；deleted_at 非空即回收站

asset(id, item_id, role, ordinal, path, thumb_path, mid_path,
      sha256, bytes, width, height, mime)
-- 物理文件；item : asset = 1 : N，解决「一提示词多图」

tag(id, namespace, name, UNIQUE(namespace, name))
-- namespace: 分区/发型/系列/分類/视角/材质/颜色/单品/分类/模型…
item_tag(item_id, tag_id, source)   -- source: 内置 / 手动

favorite(item_id, created_at)
saved_search(id, name, query_json)
```

### 4.2 关键设计：namespace 而不是扁平 tags

现有 6 个站的属性天然是**分面**，不是散标签：

| 集合 | 分面（namespace: 取值） |
| --- | --- |
| `portrait` | 分区(face/styling) · 发型 · 风格 |
| `costume` | 材质 · 颜色 · 单品（共 86 标签） |
| `pose` / `pose-depth` | 系列 · 分類 · 视角(正面/侧面/斜角/俯视/仰视) · rating |
| `shisei` | 系列 · 分類 · 视角 · rating |
| `prompts` | 分类（41 个官方分类）· 精选/需参考图 |

好处：UI 上「按 视角 筛」是语义化的一次点击；跨集合时同名 namespace 自动合并（`pose` 与 `pose-depth` 的 288 个姿势天然同源）；`meta_json` 仍保留原始字段以备回溯。

### 4.3 字段映射（导入器必须逐站声明的映射表）

| 目标字段 | portrait | costume | pose / pose-depth | shisei | prompts |
| --- | --- | --- | --- | --- | --- |
| `title` | 风格 | 名称 | `姿势名_zh` | `姿势名_zh` | `title` |
| `prompt` | — | — | — | — | `content` 中文 |
| `prompt_raw` | — | — | — | — | 英文原文 |
| `author` | あぎ | ギア | ギア | Shisei | 社区作者 |
| `source_url` | 固定 | 固定 | 固定 | 固定 | `sourceLink` |
| 分面 | 分区/发型/风格 | 标签 | 系列/分類/视角/rating | 系列/分類/视角/rating | 分类 |
| asset 三档 | thumb/full | thumb/img/png | thumb/full | thumb/mid/full | thumb/full |

**验收要求**：导入器必须输出「未映射字段报告」，任何 manifest 里出现却未被映射的键都要列出来，避免静默丢数据。

## 五、技术选型

| 维度 | **A. FastAPI + SQLite + 原生 JS**（推荐） | B. FastAPI + SQLite + Vue 3 / Vite | C. Tauri + React + LanceDB |
| --- | --- | --- | --- |
| 与现有资产贴合 | ★★★ 全 Python，导入器直接复用 | ★★★ | ★ 需重写全部逻辑 |
| 构建链 | 无 Node、无打包 | 需 Node 18+ 与 Vite | 需 Rust 工具链 |
| 启动 | `python run.py` | 先 build 再跑后端 | 双击 exe |
| 交互复杂度上限 | 中（灯箱/批量/拖拽需手写） | 高（组件生态） | 高 |
| 依赖 | `fastapi` `uvicorn` `pillow` | 同上 + `node_modules` | 重 |
| 适用 | 个人本地单机 | 长期演进成产品 | 想当桌面 App 分发 |

**推荐 A**，理由：项目现在就是零构建的纯 Python 风格，A 是它的自然延伸；单机自用，`node_modules` 与 Rust 工具链都是纯负担。若后续 UI 复杂度失控（批量编辑、拖拽排序、多窗口），再迁到 B——**A 的 API 与数据库可直接复用，不浪费**。

> 备选 D：直接上 Eagle / Immich / PhotoPrism，本项目只当导入源。省 5–6 天开发，但标签体系、分面语义、批量操作会被现成软件的模型限制住，且你的 6 套分面（视角/系列/发型）不是标准照片管理器的概念。仅在你不想写前端时考虑。

## 六、分阶段实施

### P0 · 冻结与备份（0.5 天）

- `git tag pre-webui` 打基线；`gallery.db` 与图片目录分别备份
- 记录当前 `sites/*/manifest.json` 的 SHA256，作为导入结果的对照基准
- **不改任何代码**

验收：能随时 `git checkout pre-webui` 回到现状。

### P1 · 数据库与全量导入（1.5 天）

新建 `server/` 目录，与旧 `tools/` 并存互不干扰：

```
server/
├── app.py            # FastAPI 入口 + 静态文件挂载
├── db.py             # schema、迁移、连接池
├── models.py         # Pydantic 模型
├── importer.py       # 6 站 manifest → DB（每站一个 adapter）
├── api/items.py      # 列表/详情/更新
├── api/facets.py     # 分面计数
├── api/import.py     # 扫描目录 / 上传
└── web/              # 前端（index.html + app.js + style.css）
```

任务：
1. 建库 + schema（含索引：`item(collection_id, deleted_at, id)`、`item_tag(tag_id, item_id)`、`asset(item_id)`）
2. 6 个 adapter，按 §4.3 映射表导入
3. 计算 `sha256`（48 个并发读 11.63 GB，预计 10–20 分钟），顺便交出去重报告
4. 抓取 `thumb/mid/full` 实际文件大小，剔除 manifest 里存在但文件缺失的记录（输出缺失清单，不静默跳过）

验收：
- `SELECT COUNT(*) FROM item` ≈ 22,035，`asset` ≈ 29,185
- 未映射字段报告为空（或逐条解释）
- 抽验：每个集合随机 20 条，DB 里 title/prompt/分面/三档路径与原 `manifest.json` 逐字段一致

### P2 · 只读 API + 新 UI 骨架（2 天）

API：

```
GET  /api/collections
GET  /api/items?collection=&facet=&q=&sort=&cursor=&limit=
GET  /api/items/{id}
GET  /api/facets?collection=&q=           # 联动计数
GET  /media/{size}/{asset_id}             # size: thumb|mid|full
```

UI（一套，替代 6 套）：
- 左侧：集合树（6 个 + 自建）+ 收藏 + 回收站
- 顶部：搜索框 + 排序 + 视图密度
- 中部：分面 chips（按 namespace 分组，联动计数）+ 网格（每批 60 张增量渲染，沿用已验证的 IntersectionObserver 方案）
- 右侧：详情抽屉（三档图切换、prompt 全文与复制、分面编辑、来源链接、上一张/下一张）

视觉直接沿用现有站的浅色/深色双主题 CSS —— 已经调好，不要重画。

验收：
- 首屏可交互 < 1s（对比现在 80 MB JSON 解析 3s）
- 22k 条数据下滚动无掉帧；筛选响应 < 200ms

### P3 · 写操作（2 天）

- 收藏 / 取消收藏
- 标签增删（手动 namespace，与内置分面区分显示）
- 软删除 → 回收站 → 恢复 / 彻底删除（彻底删除才动磁盘，且二次确认）
- 批量操作：框选 / Shift 连选 → 批量打标、批量收藏、批量移动集合
- 导入：拖拽文件上传、指定文件夹扫描入库、重复检测（按 sha256，命中则提示合并而非新建）
- 撤销：最近 20 步操作可回滚（写操作日志表）

验收：每个写操作后 DB 立即一致；重开浏览器状态不变；导出 `items.csv` 能还原全部标注。

### P4 · 增强（按需，2 天）

- 相似图：感知哈希（pHash）预计算，详情页「找相似」
- 同 prompt 聚合：`prompts` 站的多图真正合并成一条
- 中文全文检索：先 `LIKE`（22k 条实测够快），不够再上 FTS5 trigram
- AI 自动打标（可选，接本地模型或 API）

### P5 · 静态站降级为导出器（按需，1 天）

若 `photoai.life` 还要继续发布：保留 `tools/release.py`，新增 `python -m server.export --out dist` 从 DB 反向渲染静态站。
不发布则整块删除：`hub/`、`shared/landing.py`、`shared/pose_seo.py`、各站 `scripts/build_gallery.py`、`tests/run.py` 的构建一致性闸门、`.github/workflows/ci.yml`。

## 七、关键实现约束

1. **图片不搬**：DB 存相对路径（相对 `sites/`），避免 11.63 GB 复制，也避免迁移中途磁盘爆掉。需要统一库时再加 `library/` 与新导入走内容寻址。
2. **路径含中文与日文**：`costume/thumbs/春/SPR-0001.webp`、`pose/thumbs/全身1人・セクシー系/立ち/P001/正面.jpg`。URL 用 `urllib.parse.quote` 编码，DB 存原样，Windows 长路径注意 `\\?\` 前缀。
3. **新旧并存**：`server/` 只读 `sites/*/manifest.json` 与图片，不回写；旧 `tools/` 在 P5 前保持可运行，作为回退路径。
4. **Python 版本**：新应用要求 3.11+（FastAPI 生态现状），与旧 CI 的 3.8 闸门解耦——旧构建器退役时一并移除该闸门。
5. **数据库位置**：`data/gallery.db`，加入 `.gitignore`；提供 `python -m server.backup` 一键导出 `db + 标注 CSV`。
6. **端口**：默认 8765，避开 Hyper-V 保留段 7992–8091（本机环境约束）。

## 八、风险与回退

| 风险 | 缓解 |
| --- | --- |
| 字段映射遗漏导致数据丢失 | 未映射字段报告 + 与 `manifest.json` 逐字段比对测试 |
| 导入中途崩溃 | 导入事务按集合分批提交，可断点续跑 |
| 图片缺失静默跳过 | 缺失清单必须落盘并计数，不为 0 就不算通过 |
| 新 UI 不如旧的好用 | P2 完成后并行跑一周，旧站保留可切回 |
| 11.63 GB 哈希耗时 | 后台任务 + 进度条，可中断续算（按已算 sha 跳过） |

**回退**：`git checkout pre-webui`，图片从未被移动，`gallery.db` 独立于仓库，删除即回到当前状态。

## 九、需要你拍板的三件事

1. **技术栈**：A（原生 JS，推荐）/ B（Vue 3 + Vite）/ C（Tauri 桌面）/ D（直接用 Eagle 类现成软件）
2. **静态发布是否保留**：`photoai.life` 继续发 → 需要 P5 导出器；只自用 → 砍掉 `hub/`、SEO、CI 闸门，代码量立减约 3,000 行
3. **图片存储**：原位索引（推荐，零拷贝）/ 搬进统一 `library/` 内容寻址（收益：去重与移动方便；代价：11.63 GB 复制一次 + 路径重写）

## 十、附带发现（需你确认）

`mj-gallery/` 目录当前是**空的**（2026-10-31 17:43 变更）。该目录从未被 git 跟踪（`git ls-files` 无记录），因此：

- 源码（`extract.py` / `import_gpt2.py` / `build_gallery.py` / `make_sample.py`）与 `data/gallery.js`（84 MB）已不在磁盘上（指 `mj-gallery/`；prompts 站现用的另一份同名脚手架在 `sites/prompts/scripts/legacy/`，与本段无关）
- 图片资产无损失：22,268 张 youmind 图在 `sites/prompts/img/gpt2/` 有完整副本；`manifest` 数据在 `sites/prompts/manifest.json`
- 若需要那套「收藏 / 手动标签 / 回收站」的前端实现，可按 `.workbuddy/memory/2026-10-31.md` 的记录重建；但方案 P2/P3 会用数据库方案替代它，建议不重建

请确认是否为你有意清空，以免误判。
