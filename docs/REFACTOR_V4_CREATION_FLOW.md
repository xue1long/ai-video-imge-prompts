# 重构方案 v4：创作取素材优先

> ⚠️ **已被 [`REFACTOR_V5_FULL_CYCLE.md`](REFACTOR_V5_FULL_CYCLE.md) 取代。**
> v4 的错误是把你确认的四件事当成「争夺开发时间的功能」按优先级串行；它们实际是**一条循环的四个段**，应当先铺薄闭环再按实测加深。v4 的出口层设计（三条路径、文件名规则）被 v5 原样继承。
>
> 本文是**最终方案**，可据此直接开工。它整合了 [`REFACTOR_V2.md`](REFACTOR_V2.md)（架构）与 [`REFACTOR_V3_WRITE_OPS.md`](REFACTOR_V3_WRITE_OPS.md)（写操作）的正确结论，并按你确认的两个前提重排：
> **① 重心是「创作时取素材」　② 接受 Pillow 依赖**
> 状态：待开工。日期：2026-10-31

## 一、重心变了，方案的重心跟着变

「创作时取素材」拆到原子只有三步：**找到 → 确认 → 送出去**。

v2/v3 花了全部篇幅设计前两步怎么管，**第三步完全没设计**。而恰恰是第三步，决定了这个库是「一个可以浏览的图库」还是「一个能用的创作工具」。

创作场景的真实瞬间：

| 瞬间 | 你要的操作 | 时间预算 |
| --- | --- | --- |
| 做 ControlNet，需要「坐姿 + 正面」 | 筛 → 拖进 load image 节点 | 5 秒 |
| 看到一张好图，想要它的 prompt | 打开 → 复制原文 → 粘到 MJ | 3 秒 |
| 想起刚才那张，但忘了在哪 | 最近用过 → 找回 | 2 秒 |
| 准备一批参考做参考板 | 筛 50 张 → 送目录 | 10 秒 |

**每一个瞬间都是「把东西送到正在用的工具里」，而不是「在库里看得爽」。** 这是本文与前三版的根本区别。

## 二、从 v2/v3 继承的结论（不再重新论证）

| 结论 | 出处 |
| --- | --- |
| SQLite 是唯一真相，页面是它的视图 | v2 |
| 三档图已在盘上，直接复用，不重新生成 | v2 |
| `asset` 独立 + `item_asset` 多对多 + `derivative` 表 | v2（终局视角发现） |
| `sites/` 只读、`library/` 可写、物理删除只作用于后者 | v3（库边界） |
| 标准库 `http.server` + `sqlite3`，零框架 | v2 |
| 撤销 = DB 快照，不做撤销栈 | v3（奥卡姆） |
| 批量操作条件来自筛选，不传 5000 个 id | v3 |
| manifest 降级为快照，单向 DB → manifest | v3 |
| 「修改」= 元数据 / 派生 / 版本三件事，不内置编辑器 | v3 |

## 三、新重心带来的三个变化

### 变化 1：出口层成为核心，不是附属

v3 把「导出文件」放在 S5（倒数第二步），且是批量的。但创作时**单张即时送出**才是主场景。

新增配置概念「出口」：

```json
{
  "port": 8765,
  "exports": [
    {"name": "ComfyUI",  "path": "D:/ComfyUI/input", "tier": "full"},
    {"name": "参考板",   "path": "E:/refs",          "tier": "mid"}
  ]
}
```

三条出口路径，按可靠性排序（见上图）：

| 路径 | 目标 | 实现 | 可靠性 |
| --- | --- | --- | --- |
| 送到目录 | ComfyUI 的 input | 后端 `shutil.copy2` 到配置路径 | **100%**，可批量 |
| 拖拽出去 | 桌面 / PS / 资源管理器 | `<img draggable>` + `dataTransfer.setData('DownloadURL', ...)` | 高（Chrome/Edge 原生） |
| 复制文本 | MJ / 网页生图 / 聊天框 | `navigator.clipboard.writeText()` | 100%（localhost 是安全上下文） |

**为什么拖拽不能直接拖到 ComfyUI**：ComfyUI 是网页，跨页面拖拽依赖它自己处理 `dragover`，读的是 `dataTransfer.files`，而浏览器出于安全不会给出真实文件对象。所以 ComfyUI 走「送目录」这条硬路径——这也顺带解决了批量送的问题。

**文件名必须可辨识**。直接送原文件名会全撞（pose 站每张都叫 `正面.jpg`）：

```
{collection}_{ext_id}_{原名}.{ext}
pose_P001_正面.png
costume_SPR-0001.jpg
prompts_gpt2-13983_1.jpg
```

同名冲突时默认加 `-2` 后缀，不覆盖（避免盖掉你刚生成的结果）。

### 变化 2：prompt 升为一等公民

**这个库对创作场景最大的价值不是 29,185 张图，是 22,268 条 prompt。** 图只能参考，prompt 能直接生成。

但 v2/v3 里 prompt 只是 `item` 的一个列，详情里显示一下。这在创作场景是严重低估。prompt 需要：

| 能力 | 为什么 |
| --- | --- |
| 一键复制**原文**（英文） | 粘进 MJ/ComfyUI 用的就是它，译文没用 |
| 一键复制**译文**（中文） | 理解 + 给中文模型用 |
| 全文检索（中英双语） | 「找那种赛博朋克霓虹的」 |
| 变量占位符原样保留 | Raycast 的 `{{style}}` 这类，复制出来要能自己填 |
| 「我用过这条」 | 好 prompt 会反复用，需要最近列表 |

字段上 `prompt`（中文/展示）与 `prompt_raw`（原文/复制）必须分开——这个 v2 已有，现在提升为**核心字段**。

### 变化 3：管理功能整体降级

| 功能 | v3 位置 | v4 位置 | 理由 |
| --- | --- | --- | --- |
| 修改元数据 | S2（第 3 步） | T5（最后） | 创作时不会去改参考图的标题 |
| 批量打标 | S2 | T5 | 准备训练集才用，不是日常 |
| 删除三档 | S4 | T5 | 创作时不删东西 |
| 导入 | S3（第 4 步） | T4 | 是「生成完之后」的下游动作 |
| **出口** | S5（倒数第 2） | **T2（第 3 步）** | 主场景 |
| **创作态 UI** | S6（最后） | **T3（第 4 步）** | 主场景 |

## 四、创作态 UI 的设计约束

不是「管理器的界面」，是「取素材的界面」。三条硬约束：

**1. 键盘优先，鼠标可选**

| 键 | 动作 |
| --- | --- |
| `/` | 聚焦搜索 |
| `j` / `k` | 下 / 上一张 |
| `Enter` | 全屏详情 |
| `C` | 复制 prompt 原文 |
| `Shift+C` | 复制译文 |
| `S` | 送到默认出口 |
| `Esc` | 退出 |

**2. 详情是全屏，不是侧边抽屉。** 创作时要看清图（姿势细节、深度图层次），抽屉太窄。

**3. 首页第一屏是「最近用过」，不是集合树。** 创作心流里最先要找的是「我刚才那张」，不是「浏览某个分类」。集合筛选退到第二层。

## 五、数据模型（最终版，9 张表）

```sql
collection(slug, name, sort)

asset(id, path, volume, bytes, width, height, mime,
      source_kind, status)
-- source_kind: collected | own      ← 决定能否物理删除
-- status:      ok | missing | superseded

derivative(asset_id, kind, path, width, height)
-- kind: thumb | mid | full | png    ← 替代写死三列

item(id, collection, ext_id, title,
     prompt,          -- 中文/展示
     prompt_raw,      -- 原文/复制（创作场景的核心字段）
     author, source_url, published_at, model,
     last_used_at, use_count,        -- 新增：最近用过的依据
     meta, deleted_at)

item_asset(item_id, asset_id, role, ordinal)
tag(id, ns, name)
item_tag(item_id, tag_id, source)
fav(item_id, at)
job(id, kind, total, done, status, error, started_at, ended_at)
```

两处针对新重心的调整：

- **`item.last_used_at` + `use_count`** 替代独立的 `usage` 表（奥卡姆）。「最近用过」只需 `ORDER BY last_used_at DESC LIMIT 20`，区分不了「复制」和「送出」——但创作时你只关心「我刚才看了哪张」，不关心用了什么方式。
- **无 `export_log` 表**。送出去的文件不追踪（要清理 ComfyUI 的 input 目录，用资源管理器比写功能快）。

## 六、API（14 个，够用）

```
读
  GET  /api/items?collection=&facet=&q=&sort=&cursor=&limit=
  GET  /api/items/{id}
  GET  /api/facets?collection=&q=
  GET  /api/recent?limit=20
  GET  /media/{size}/{asset_id}

取出去（核心）
  GET  /api/prompt/{id}?lang=raw|zh          → text/plain，直接给复制
  POST /api/send {item_ids, target, tier}    → 复制到出口目录，返回文件名与体积

写
  PATCH  /api/items/{id}
  POST   /api/items/{id}/hide
  POST   /api/trash/{id}/restore
  POST   /api/bulk {filter, action}

导入与任务
  POST /api/import {paths}
  GET  /api/jobs/{id}
  POST /api/scan                             → 孤儿扫描
```

## 七、实施计划

| 步 | 内容 | 投入 | 验收标准 |
| --- | --- | --- | --- |
| **T0** | 6 份 manifest → 统一 `catalog.csv`（验证字段映射） | 1 h | 22,035 行；Excel 能开；随机 20 条与 manifest 逐字段一致 |
| **T1** | `index/`：SQLite + 数据驱动同步 + 只读端点 | 0.5 d | `q=坐姿&facet=视角:正面` <50ms；item 22,035 / asset 29,185；80 MB `gallery.js` 可删 |
| **T2** | **出口层**：`config.json` + `/api/send` + `/api/prompt` + 最小页面（网格 + 全屏 + 三个按钮） | 1 d | 点「送到 ComfyUI」→ `input/` 出现 `pose_P001_正面.png`，ComfyUI 刷新后能选到；「复制 prompt」出英文原文；拖图到桌面文件落地 |
| **T3** | **创作态 UI**：键盘操作 + 最近用过 + 无限滚动 | 1.5 d | `/` 聚焦、`j/k` 切换、`C` 复制、`S` 送出；22k 下筛选 <200ms；首屏 <1s |
| **T4** | 回流：导入（扫描目录 → `library/` + 缩略图 + job 进度） | 1 d | 拖入 100 张图，1 分钟内入库、生成缩略图、可搜索；重复导入不产生重复 |
| **T5** | 管理：修改元数据、批量打标、删除三档、孤儿扫描 | 1.5 d | 批量前返回影响行数 + 自动快照；`sites/` 素材物理删除被代码断言拒绝 |

**T0 + T1 + T2 = 2 天，就能完成「找到 → 复制 prompt / 送进 ComfyUI」的完整闭环。** 这是可用的最小版本，后面全是增值。

## 八、不做什么（明确写下来）

| 不做 | 理由 |
| --- | --- |
| 内置图像编辑器 | 外面有 PS 和 ComfyUI |
| 版本链 UI | 留 `superseded` 字段就够 |
| 撤销栈 / 操作日志 | 用 `cp gallery.db` 快照替代 |
| sha256 去重 | 文件名 + 字节数 + 尺寸判重够用 |
| 跨设备同步 | 单机自用 |
| 与 `awesome-ai-video-prompts` / `PromptDirector-Curated` 统一语义 | 提前抽象代价三倍；CSV 就是对外接口 |
| 静态站重写 | `tools/release.py` 原样保留，需要时从 DB 生成 manifest 喂它 |
| Node / 打包工具 / 前端框架 | 原生 JS 足够；遇到具体痛点再换（只换前端，API 不变） |

## 九、风险

| 风险 | 缓解 |
| --- | --- |
| ComfyUI 的 input 目录文件堆积 | 不追踪；用资源管理器手清（比写清理功能快） |
| ComfyUI 不刷新新文件 | 送完后页面上提示「在 ComfyUI 里点一下刷新」 |
| `DownloadURL` 是 Chrome/Edge 非标准扩展 | 提供「下载」按钮兜底（`<a download>`） |
| 22k 条 prompt 的中文检索慢 | 先 `LIKE`（实测 22k 足够快），不够再上 FTS5 trigram |
| 导入 5000 张时 UI 卡死 | 后台 job + 轮询；每张独立事务可中断 |
| 批量操作写错条件 | 返回影响行数 → 确认 → 自动快照 |
| SQLite 写锁冲突 | WAL 模式 + 单写线程 |
| 采集素材被误删 | `store.py` 里断言 `source_kind='collected'` 禁止物理删除，不靠 UI 约束 |

## 十、开工顺序

按 T0 → T1 → T2 连续做，T2 结束时你先试用一次真实的 ComfyUI 工作流，再决定 T3 之后要不要按这个顺序走。

如果你机器上 ComfyUI 的 input 路径不是 `D:/ComfyUI/input`，告诉我实际路径，我写进 `config.json` 的默认值。
