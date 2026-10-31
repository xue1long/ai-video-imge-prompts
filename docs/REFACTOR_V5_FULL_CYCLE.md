# 重构方案 v5（已被取代）：四段一条循环，先薄后深

> ⛔ **本文已被 [`REFACTOR_V6_LOCKED.md`](REFACTOR_V6_LOCKED.md) 取代。**
> 经三轮 grill 质询，本文有 6 处事实或设计错误被推翻（ComfyUI 前提不成立、M1 验收标准实测只有 6 条、"8 个只读端点"从未定义且数量错、分面未真正统一、端口冲突未处理、50 条 title 含换行）。方向（四段一条循环、先薄后深）保留，具体数字与契约一律以 v6 为准。
>
> 本文取代 [`REFACTOR_V4_CREATION_FLOW.md`](REFACTOR_V4_CREATION_FLOW.md)。v4 按「创作取素材」单点排序是错的——你要的四件事不是四个优先级，而是**一条循环的四个段**。
> 前置：[`REFACTOR_V2.md`](REFACTOR_V2.md)（架构）、[`REFACTOR_V3_WRITE_OPS.md`](REFACTOR_V3_WRITE_OPS.md)（写操作）。它们的架构结论全部保留。
> 状态：**M0 已完成**（见第七节实测数据）。日期：2026-10-31

## 一、修正：这不是四件事，是一条循环

| 你的四个需求 | 在循环里的位置 |
| --- | --- |
| 沉淀自己生成的图 | 入口（素材进来） |
| 浏览 | 中间（找到它） |
| 打标 | 中间（组织它） |
| 取素材 | 出口（送出去） |

出去之后你会生成新的图，新图又进来。**这是一个闭环，不是四条流水线。**

v4 的错误是把它们当成「争夺开发时间的功能」，按重心排先后（先把「取」做到极致，管理功能全部后置）。但如果只做「取」，取的范围锁死在采集素材上，你自己生成的图进不来，循环就断在第一步。

**正确的顺序不是「按优先级串行」，而是「先铺一条能跑通的薄闭环，再按实测加深」。**

## 二、为什么是薄闭环而不是深单点

三个理由：

1. **你现在不知道哪段最痛。** 我按推测排优先级，但你真正用起来可能发现「打标最痛」（22k 张图要分类）或「沉淀最痛」（ComfyUI 输出目录一堆文件要整理）。只有跑通循环才知道。
2. **四段的底座是同一个东西**：一个 item 能被创建、被标注、被找到、被送出。这个底座先立起来，四段各自长大都便宜。
3. **薄闭环 1.5 天，深单点是 3 天。** 薄版能让你第二天就用起来，深版要等一周。

「薄」的标准是：**能做，不追求好用**。每段只实现主路径，砍掉所有增强。

| 段 | 薄版做什么 | 薄版明确不做 |
| --- | --- | --- |
| 沉淀 | 拖一个文件或文件夹进来 → 落 `library/` → 生成缩略图 → 读 PNG 里的生成参数 | 进度条、断点续传、去重、监视目录 |
| 浏览 | 网格 + 搜索框 + 集合切换 | 键盘操作、最近用过、无限滚动、分面联动计数 |
| 打标 | 单条加/删标签、收藏 | 批量、标签重命名/合并、标签树 |
| 取素材 | 复制 prompt 原文、送到配置的目录 | 拖拽出去、批量送、变量填写 |

薄闭环跑通后，你用一周，然后告诉我哪里最烦，我们再集中火力。

## 三、四段各自的加深路径（按需要挑）

### 沉淀：从「拖文件」到「自动回流」

薄：拖一个进来。
加深：
- **读 ComfyUI / MJ 的 PNG 元数据**（见第四节，这是沉淀段最有价值的部分）
- 扫描文件夹批量导入，保持目录结构
- 监视 `ComfyUI/output/`，生成完自动入库
- 按「文件名 + 字节 + 尺寸」判重，重复时提示合并

### 浏览：从「网格」到「创作态」

薄：网格 + 搜索。
加深：
- 键盘优先：`/` 搜索、`j/k` 切换、`Enter` 全屏、`C` 复制、`S` 送出
- 首页第一屏是「最近用过」，不是集合树
- 无限滚动（每批 60 张）
- 分面 chips 联动计数

### 打标：从「单条」到「批量」

薄：单条加/删标签、收藏。
加深：
- **批量打标（条件来自当前筛选）**——这是 22k 规模下唯一可行的方式
- 标签重命名 / 合并 / 删除
- 区分 `builtin` / `manual` / `ai` 三种来源
- 可选：AI 辅助打标

> 注意：打标的真实工作量比想象小。你不用给 22k 张图打描述性标签（那是上游已经做过的：costume 86 个、prompts 41 类、pose 系列/视角）。你要打的是**自己的判断**（「可用/待定/废图」这类），量不大，但价值极高。

### 取素材：从「复制/送目录」到「拖拽/批量」

薄：复制 prompt 原文、送到配置目录。
加深：
- 拖拽出去（`DownloadURL`，到桌面/PS）
- 批量送（按筛选）
- prompt 变量占位符填写（`{{style}}` 这类）
- 最近送过的记录

## 四、一个被忽略的大杀器：PNG 里的生成参数

**ComfyUI 和 Midjourney 生成的 PNG，文件里嵌着完整生成参数。**

- ComfyUI：`tEXt` chunk，key 是 `prompt`（API 格式的完整节点图）和 `workflow`（UI 格式），JSON
- Midjourney：`tEXt` chunk 的 `Description` 字段含完整 prompt 与参数

Pillow 的 `Image.open(p).info` 直接能读到，零额外依赖。

这意味着：**「沉淀自己生成的图」不是「存一个文件」，而是「连生成参数一起入库」**——正向/负向 prompt、模型、采样器、种子、步数，全部自动提取。

价值：你自己生成的图，和采集来的 22k 条 prompt 进入**同一个语义层**（都有 prompt、都能搜索、都能复制）。循环就此闭合——你取出去的 prompt，生成完回流，带着参数又成了可复用的素材。

薄闭环阶段可以先只读 `prompt` 这一个 chunk（一次 `Image.open` 就有），加深时再解析 workflow 结构。

## 五、数据模型（最终，9 张表）

```sql
collection(slug, name, sort)

asset(id, path, volume, bytes, width, height, mime, source_kind, status)
-- source_kind: collected | own     ← 决定能否物理删除
-- status:      ok | missing | superseded

derivative(asset_id, kind, path, width, height)
-- kind: thumb | mid | full | img | png   ← 六站的档位本来就不一致

item(id, collection, ext_id, title, title_alt,
     prompt, prompt_raw,               -- 中文/展示 · 原文/复制
     author, source_url, published_at, model,
     generator_meta,                   -- 新增：PNG 里读到的生成参数（JSON）
     last_used_at, use_count,
     meta, deleted_at)

item_asset(item_id, asset_id, role, ordinal)
tag(id, ns, name)
item_tag(item_id, tag_id, source)      -- builtin | manual | ai
fav(item_id, at)
job(id, kind, total, done, status, error, started_at, ended_at)
```

比 v4 只加了一个 `generator_meta`（承接第四节）。

## 六、库的边界（v3 结论，不变）

```
sites/        只读区    11.63 GB 采集素材    永不物理删除
library/      可写区    你自己导入的素材     允许物理删除，按 YYYY/MM 分目录
gallery.db    唯一真相
backups/      批量操作前的 DB 快照
```

## 七、M0 已完成：实测数据与三处事实修正

`index/catalog.py` 已写好并跑通，产出 `exports/catalog.csv`（17.6 MB / 22,020 行 / 20 列）。这份清单本身就是 M1 的字段映射验证。

```
集合              item   asset     未匹配  未映射字段
portrait        1499    1499       0  —
costume         1407    1407       0  —
pose            1439    1439       0  —
pose-depth      1439    1439       0  —
shisei          1133    1133       0  —
prompts        15103   22268       0  —
合计           22020   29185
```

**未映射字段为空**——六份 manifest 里的每一个键都有去处，没有静默丢数据。

### 三处修正（前四版文档里的数字是错的）

| 项 | 前四版写的 | 实测 | 原因 |
| --- | --- | --- | --- |
| prompts 提示词数 | 15,118 | **15,103** | 15,118 是 API 探测到的总数；实际落盘 22,268 张图归属 15,103 条（`originId` 去重） |
| item 总数 | 22,035 | **22,020** | 由上一条连带 |
| prompts 带分类数 | 22,122 | **15,030 / 15,103** | 73 条无 tags（前四版按图计数，口径错） |

### 跑通过程中踩到的三个坑（写进代码注释了）

1. **costume 用 `img_path` / `png_path`，不是 `full_path`**——照 `full_path` 取会静默得到空字符串
2. **prompts 的 `tags` 是逗号分隔字符串，不是 list**——直接 `for t in tags` 会逐字符展开（第一次跑就是这样，分面变成「分类:精|分类:选|…」）
3. **prompts 的宽高不在 manifest**，在 `data/dims.json`（22,268 条，白捡的）——已接上

### 剩余缺口（都是设计如此，不是漏了）

| 缺口 | 数量 | 说明 |
| --- | --- | --- |
| 缺原图路径 | costume 1,407 | 它用 `img` + `png` 两档，没有 `full` |
| 缺宽高 | pose 1,439 / pose-depth 1,439 / shisei 1,133 / costume 1,407 | 上游 manifest 没有。网格用等高 + `object-fit: cover`，不需要宽高 |
| 缺原文 prompt | 除 prompts 外的 6,917 条 | 图库类素材本来就没有 prompt |
| 缺分面 | prompts 73 | 上游无 tags |

**pose 站的中文标题还缺**：manifest 里 `姿势名` 是日文，中文翻译在 `shared/pose_i18n.py`（288 条）。薄闭环阶段先用日文，加深时接上翻译表。

## 八、实施计划

| 步 | 内容 | 投入 | 验收 |
| --- | --- | --- | --- |
| **M0** ✅ | `index/catalog.py`：6 份 manifest → 统一 CSV，验证映射 | 已完成 | 22,020 行，未映射字段为空 |
| **M1** | `index/store.py` + `sync.py` + `serve.py`：SQLite 建库、同步、只读端点 | 0.5 d | item 22,020 / asset 29,185；`q=坐姿&facet=视角:正面` <50ms |
| **M2** | **薄闭环**：一个页面，四段各最薄一版（见第二节表格） | 1.5 d | 拖一张图进来 → 能搜到 → 能打标 → 能复制 prompt / 送目录 |
| **M2.5** | **你自己用一周** | — | 告诉我哪段最烦 |
| **M3** | 按实测痛点加深（从第三节里挑） | 2 d+ | 你指定的那一段到位 |

**M2 结束就能用。** 之后的所有工作都由你的实际体验决定，不由我的推测决定。

## 九、不做什么

| 不做 | 理由 |
| --- | --- |
| 内置图像编辑器 | 外面有 PS 和 ComfyUI |
| 版本链 UI / 撤销栈 / 操作日志 | 留字段 + `cp gallery.db` 快照 |
| sha256 去重 | 文件名 + 字节 + 尺寸足够 |
| 跨设备同步 / 多用户 / 鉴权 | 单机自用 |
| 与同族项目统一素材语义 | CSV 就是对外接口 |
| 静态站重写 | `tools/release.py` 原样保留 |
| 瀑布流布局 | 等高网格够用，省掉一次 22k 文件的宽高扫描 |
| Node / 前端框架 / 打包工具 | 原生 JS；遇到具体痛点再换（只换前端，API 不变） |

## 十、开工

下一步是 M1：把 `catalog.py` 的映射表直接变成 `sync.py`（同一张表，不重写），建 `gallery.db`，起 8 个只读端点。

如果你机器上 ComfyUI 的 input 目录不是 `D:/ComfyUI/input`，告诉我实际路径，我写进 `config.json` 默认值。
