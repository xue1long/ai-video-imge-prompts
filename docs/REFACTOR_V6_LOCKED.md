# 重构方案 v6（锁定）：质询收敛后的实施契约

> 本文取代 [`REFACTOR_V5_FULL_CYCLE.md`](REFACTOR_V5_FULL_CYCLE.md)。v5 的方向正确（四段一条循环、先薄后深），但经三轮 grill 质询后，**6 处事实或设计错误被推翻**，22 条决策全部落定。
> 前置：[`REFACTOR_V2.md`](REFACTOR_V2.md)（架构）、[`REFACTOR_V3_WRITE_OPS.md`](REFACTOR_V3_WRITE_OPS.md)（写操作边界）。
> 状态：**设计已锁定，未改动任何代码**。日期：2026-10-31

## 零、质询推翻了什么

这 6 处不是风格问题，是**会导致返工的硬错误**。每条都附实测证据。

| # | v5 的说法 | 实测 | 修正 |
| --- | --- | --- | --- |
| 1 | §4「ComfyUI / MJ 的 PNG 里有完整生成参数」是本轮最大价值 | `D:/`、`E:/` 深度 3 内无任何 `*comfy*` 目录；只有 `E:/000/Midjourney-win-v2.5.2` 客户端 | 不做 ComfyUI 专用解析，只读 PNG 的**全部** `tEXt`/`iTXt` 块原样存 JSON（D01） |
| 2 | M1 验收：`q=坐姿&facet=视角:正面` | 实测 **6 条**（全部来自 shisei）。pose / pose-depth 的标题与分类是日文（`座り`） | 验收改为 `q=座り&视角:正面`=**116**、`q=cyberpunk`=**160**、`视角:正面` 全集=**809**（D03） |
| 3 | "8 个只读端点"（出现 3 次，从未列举） | 且数量本身错——M2 必须有写接口 | 锁定 **9 个端点**，3 个是写（D19） |
| 4 | §5「把 6 套零散字段收敛成分面」 | 实测 **11 个命名空间**，三套「分类」并存：`分类`(prompts 41 类) / `分類`(姿势 26 类) / `标签`(costume 86 类)；另有 `分区/发型/风格/系列/编号/标记/rating` | 不合并语义，**按集合展示分面**（D02） |
| 5 | 启动端口未定 | 8080 被 PID 15200 占用（`netstat` LISTENING） | 固定 **8787**（`tools/serve.py` 本有 `free_port` 避让逻辑，只是没定值） |
| 6 | 未提及 | CSV 物理 22,126 行 / 逻辑 22,020 行——**50 条 title 含换行符** | sync 时把 `\n`/`\r` 规范化为空格（进 `title` 与 `search_blob`） |

**一个反向的好消息**：`shared/pose_i18n.py` 不止 288 个姿势名，还有 `CAT_ZH`（26 分类全覆盖）、`SERIES_ZH`（4 系列）、`ANG_ZH`（视角）。接入后中文检索能命中分类，不只命中标题。另外 shisei 的 manifest 里**本来就有** `姿势名_zh` 字段——那 6 条命中就是它。

## 一、22 条决策

### A 组：边界与形态

| # | 决策 |
| --- | --- |
| D01 | 沉淀段只读 PNG 全部文本块，原样存 `generator_meta`；不做 ComfyUI 字段级解析 |
| D02 | 分面不合并语义，打开哪个集合只显示该集合的分面；跨集合搜索不显示分面栏 |
| D04 | 端口 **8787**，`python index/serve.py` + 根目录 `启动.bat` 双击；页面三栏（左集合与分面／中网格／右详情），四段全落这一页、不切路由 |
| D11 | 导入入口：拖单个文件 + 拖文件夹（递归一层）。不做目录监视、不做扫描 |
| D12 | 落盘 `library/YYYY/MM/<原始文件名>`，重名追加 `-2`，**不改名成 hash**；DB 存相对路径 |
| D13 | `config.json` 的 `targets` 字典，M2 只配一个 `input`，UI 一个「送到 input」按钮 |
| D15 | 静态站冻结＝不再构建和发布；`sites/*/index.html` 与 `hub/` **保留不删**，CI 一致性闸门不动 |
| D17 | `gallery.db` 放**仓库根**（`.gitignore` 已按根写好）；启动时比对 6 个 manifest 的 `mtime+size`，变化才全量重建（22k 行约 2–3 s） |
| D18 | 前端**单文件** `index/web/index.html`，CSS+JS 内嵌，零构建 |
| D22 | 根目录 `启动.bat`：起 serve → 等端口就绪 → 自动开 `http://127.0.0.1:8787/`；README 只加三条命令和一句边界说明 |

### B 组：数据与检索

| # | 决策 |
| --- | --- |
| D03 | 验收标准用实测口径（见第四节），外加中文检索一条：`q=坐姿` 得 148 条 |
| D05 | 导入图 `title` = 文件名去扩展名；PNG 有 prompt 就写进 `prompt_raw`；自动打 `状态:未审` |
| D16 | M1 就接入 `pose_i18n`：`NAME_ZH`(288) → `title_alt`，`CAT_ZH`/`SERIES_ZH`/`ANG_ZH` → `tag.name_zh` |
| D20 | `item` 上冗余一列 `search_blob`（title + title_alt + prompt_raw + 全部 tag 的 `name` 与 `name_zh`），搜索只 `LIKE` 一列，不 join |

### C 组：四段闭环

| # | 决策 |
| --- | --- |
| D06 | 送素材用**硬链接**（同盘零拷贝），跨盘自动退回复制；重名追加 `-2`；**绝不清空**目标目录 |
| D09 | 默认「全部」混排，每页 120 条 + 底部「加载更多」按钮（不用自动滚动）；集合切换或搜索变化重置到第一页 |
| D10 | 四段「薄」的停止线见第四节，达不到就修，不加功能 |
| D14 | 缺图探测与快照都是手动命令：`index/verify.py`、`index/snapshot.py`；serve 启动时绝不全盘扫描 |
| D21 | 打标**即写即报**（单条写入 <5 ms）；不做前端暂存批量提交 |

### D 组：schema 与契约

| # | 决策 |
| --- | --- |
| D07 | **砍掉 `job` 表**（M2 无异步任务）；保留 `fav`；`item.deleted_at` 只表示「视图隐藏」，`asset.status` 只表示「文件在不在盘」，两者永不互相改写 |
| D08 | 冻结构建即不再跑 `release.py`；线上保持最后一次发布的快照 |
| D19 | 9 个端点定成契约（见第二节），之后只增不改，前端换框架也不动接口 |

## 二、9 个端点契约

统一约定：

- 所有响应 `Content-Type: application/json; charset=utf-8`
- 错误统一 `{"error": "<code>", "detail": "..."}`，HTTP `400 / 404 / 409 / 415 / 500`
- item id 形如 `pose:P018`（`collection:ext_id`），导入的素材是 `own:2026/10/文件名`
- 图片一律走 `/media/`，不用 `file://`

### 1. `GET /api/collections`

```json
{"collections":[{"slug":"portrait","name":"人像","items":1499,"assets":1499}]}
```

### 2. `GET /api/items`

参数：`collection`（可省＝全部）、`q`、`facet`（`命名空间:值`，可重复）、`page`（默认 1）、`size`（默认 120，上限 200）、`sort`（`id|used`）

```json
{"total":809,"page":1,"size":120,
 "items":[{"id":"pose:P018","title":"立ち・両腕を頭上に伸ばす","title_alt":"站立・双臂上举",
           "collection":"pose","thumb":"/media/sites/pose/thumbs/pose-P018-front.webp",
           "prompt_raw":null,"fav":false,"tags":[["视角","正面","正面"]]}]}
```

`facet` 格式不合法 → `400 bad_facet`。

### 3. `GET /api/items/{id}`

```json
{"item":{"id":"...","title":"...","prompt":"...","prompt_raw":"...","generator_meta":{}},
 "assets":[{"id":12,"kind":"full","path":"/media/sites/pose/img/x.webp","width":832,"height":1216}],
 "tags":[["状态","废图","废图"]]}
```

### 4. `GET /api/facets?collection=pose`

```json
{"facets":[{"ns":"视角","name":"正面","name_zh":"正面","count":285},
           {"ns":"分類","name":"座り","name_zh":"坐姿","count":31}]}
```

### 5. `POST /api/items/{id}/tags`

请求 `{"op":"add","ns":"状态","name":"废图"}`（`op` 为 `add`/`del`）；响应 `{"ok":true,"tags":[...]}`。
`add` 时同步重算 `search_blob`。`ns`/`name` 为空 → `400 bad_tag`。

### 6. `POST /api/items/{id}/fav`

请求 `{"on":true}`；响应 `{"ok":true,"fav":true}`。

### 7. `POST /api/import`

二选一：`multipart/form-data` 的 `file`，或 `{"path":"E:/a/b.png"}`（本机路径）。

```json
{"ok":true,"item_id":"own:2026/10/b","assets":1,"thumb":true,"prompt_raw":"a cat, ..."}
```

不支持扩展名 → `415 unsupported_ext`；同「文件名+字节+尺寸」已存在 → `409 duplicate`（带 `existing_id`）。

### 8. `POST /api/send`

请求 `{"item_id":"pose:P018","target":"input"}`；响应 `{"ok":true,"path":"D:/.../input/x.webp","method":"hardlink"}`。
`target` 不存在 → `404 unknown_target`；源文件缺失 → `404 source_missing`。

### 9. `GET /media/<相对路径>`

直接返回文件，带 `Last-Modified` / `ETag`，靠浏览器缓存；越界路径（`..`）→ `404`。

## 三、数据模型（9 张表）

```sql
collection(slug PK, name, sort)                    -- 6 站 + own，共 7 行

asset(id PK, path UNIQUE, volume, bytes, width, height, mime, status)
-- volume: sites | library        ← 决定能否物理删除
-- status: ok | missing            ← 只由 verify.py 改写
-- path:   相对仓库根、统一正斜杠

derivative(asset_id, kind, path, bytes, width, height, PK(asset_id, kind))
-- kind: thumb | mid | full | img | png   ← 六站档位本来就不一致

item(id PK, collection, ext_id, title, title_alt,
     prompt, prompt_raw,
     author, source_url, published_at, model,
     generator_meta,                -- PNG 文本块原样 JSON（D01）
     search_blob,                   -- 冗余检索列（D20）
     last_used_at, use_count,
     meta, deleted_at)              -- deleted_at 只表示视图隐藏（D07）

item_asset(item_id, asset_id, role, ordinal, PK(item_id, asset_id))
tag(id PK, ns, name, name_zh, UNIQUE(ns, name))     -- name_zh 来自 pose_i18n（D16）
item_tag(item_id, tag_id, source, PK(item_id, tag_id))  -- builtin | manual | auto
fav(item_id PK, at)
kv(key PK, value)                  -- schema 版本 + 6 个 manifest 签名（D17）
```

比 v5：**砍 `job`、加 `kv`、`tag` 加 `name_zh`、`item` 加 `search_blob`**。表数仍是 9。

## 四、可判定验收

### M1（半天）：建库 + 同步 + 只读端点

| 指标 | 目标 |
| --- | --- |
| item 数 | **22,020** |
| asset 数 | **29,185** |
| derivative 数 | **60,910**（实测：portrait 2998 / costume 4221 / pose 2878 / pose-depth 2878 / shisei 3399 / prompts 44536） |
| `q=座り&facet=视角:正面` | **116 条**，<50 ms |
| `q=cyberpunk` | **160 条** |
| `facet=视角:正面` 全集 | **809 条** |
| `q=坐姿` | **148 条**（接入 D16 后应显著增加，数值写进实测记录） |
| `facets?collection=pose` | 26 分类 + 5 视角 + 4 系列 |
| 未映射字段报告 | 空 |

### M2（1.5 天）：薄闭环

四段各一条停止线，**达标即停，不加功能**：

| 段 | 停止线 |
| --- | --- |
| 沉淀 | 拖入 1 个 PNG 后 3 秒内出现在网格首行，缩略图非空 |
| 浏览 | 选中集合后 1 秒内看到网格 |
| 打标 | 点标签后刷新页面，标签仍在 |
| 取素材 | 点「复制」后剪贴板内容与 `prompt_raw` **逐字符一致** |

外加：9 个端点全部通过（含 2 个错误码路径：`415 unsupported_ext`、`409 duplicate`）。

## 五、实施顺序

| 步 | 内容 | 投入 | 验收 |
| --- | --- | --- | --- |
| **M0** ✅ | `index/catalog.py`：6 份 manifest → 统一 CSV | 已完成 | 22,020 行，未映射字段为空 |
| **M1** | `index/store.py` + `sync.py` + `serve.py`：建库、同步、只读端点 | 0.5 d | 上表 M1 全部指标 |
| **M2** | `index/web/index.html` 单文件 + 三个写端点 + `启动.bat` | 1.5 d | 上表四条停止线 |
| **M2.5** | **你自己用一周** | — | 告诉我哪段最烦 |
| **M3** | 按实测痛点加深（批量打标／键盘操作／自动回流／多 target） | 2 d+ | 你指定的那一段 |

`index/` 下最终形态：`catalog.py`（已有）、`store.py`、`sync.py`、`serve.py`、`verify.py`、`snapshot.py`、`web/index.html`。

## 六、不做什么

| 不做 | 理由 |
| --- | --- |
| 内置图像编辑器 | 外面有 PS 和 ComfyUI |
| 版本链 / 撤销栈 / 操作日志 | 留字段 + `snapshot.py` 拷 DB |
| sha256 去重 | 「文件名 + 字节 + 尺寸」足够（D07 的 `409 duplicate` 就靠这个） |
| 跨设备同步 / 多用户 / 鉴权 | 单机自用 |
| 与同族项目统一素材语义 | CSV 就是对外接口 |
| 静态站重写 / 删除 | D08 + D15：冻结，代码与产物都留着 |
| 瀑布流布局 | 等高网格够用，省掉 22k 文件宽高扫描 |
| Node / 前端框架 / 打包工具 | 原生 JS；换框架只换前端，接口不动 |
| 目录监视 / 自动扫描导入 | 你没有稳定观察目录，扫描等于猜（D11） |
| FTS5 全文索引 | 22k 行 `LIKE` 扫描 <30 ms；慢了再上 trigram |

## 七、M1/M2 已完成：实测校准（2026-10-31 晚）

M1–M2 的 8 张工单已实现并通过 57 项接口测试，真实 22k 数据已建库。以下数字**覆盖**本文第四节的预估：

| 指标 | 本文原定 | 实测 | 判定 |
| --- | --- | --- | --- |
| item / asset / derivative | 22,020 / 29,185 / 60,910 | **22,020 / 29,185 / 60,910** | ✅ 三项全中 |
| 全量同步耗时 | 2–3 s | **14.2 s** | ⚠ 原估过低（签名未变会跳过，日常无感） |
| `q=座り&facet=视角:正面` | 116 | **116** | ✅ |
| `facet=视角:正面` | 809 | **809** | ✅ |
| `q=cyberpunk` | 160 | **368** | ⚠ 原值基于截断 CSV，真实库不截断 |
| `q=座り` | 592 | **606** | ⚠ 同上 |
| `q=坐姿` | 148（接中文化前） | **778** | ✅ 中文别名生效 |
| 列表首屏 / 分面 / 检索延迟 | 未定 / 未定 / <50 ms | **139 / 32 / 360–700 ms** | ❌ `<50 ms` 不成立 |

**两个实现期才暴露的硬约束**（已写进 SPEC）：

1. manifest 里的路径是**站点相对**的。`pose` 与 `pose-depth` 字段一字不差，不加 `sites/<集合>/` 前缀会被去重合并（资产数 29,185 → 27,746，且图片全部 404）。
2. 作品 id 不能带 `/`，导入素材的 id 是 `own:202610-文件名`。

**检索延迟为何不修**：FTS5 的 trigram 分词要求查询至少 3 个字符，中文两字词（「坐姿」）直接查不到，而这正是最常用的检索形态。所以保留 `LIKE`，把「截短 blob」列为 M3 可选项（体积 33 MB → 约 8 MB），不上全文索引。

## 八、唯一仍开放的一条

**你的生图工具和图片落盘目录**（D01 只做到「谁都能读」，做不到「读得懂」）。

拿到以下任一条信息，M3 的沉淀段就能从「存下来」升级为「连参数一起存」：

- 本机 ComfyUI 的 `output/` 路径（当前深度 3 未搜到）
- MJ 客户端下载图的存放目录
- 或者：你根本不本地生图，那 §沉淀段的加深方向改为「手动整理 + 打标优先」
