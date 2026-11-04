# 重构方案 v7（锁定）：口径收口与重复消除

> **状态**：设计已锁定 · 未改动任何代码 · 待实施
> 修订：2026-11-02 **第三版** —— 第二版并入三角度评审的 15 条修正（§零之三）；第三版补 **D35 提交与推送规约**，并**实测更正 R11**（改 README 不会让闸门变红，真问题是「产物」有三份漂移的定义）
> 前置：[`REFACTOR_V6_LOCKED.md`](REFACTOR_V6_LOCKED.md)（v6 管的是素材管理器 `index/` 的建库与写操作；两者互补，不重叠）、[`ADDING_A_SITE.md`](ADDING_A_SITE.md)
> 术语：[`../CONTEXT.md`](../CONTEXT.md) —— **四个「唯一来源」的唯一定义处**。本文与 `AGENTS.md` 只引用、不复述。
> 驱动数据：codebase-memory-MCP 全量索引 **3,005 节点 / 11,533 边**（含 midjourney-explore 单分片改造后的工作区）
> 实施基线：**`cd4813a`** —— W6 已完成（MJ-13/14/15 ✅），字节比对的基线条件已满足
> 质询：三轮 15 问全部收敛

## 零、问题陈述与被推翻的判断

### 零之一、问题陈述

本仓库的第一性成本不是"代码重复"，而是**同一件事在几处各写一遍，其中一处改了、另一处没改**。这个成本已经以故障的形式出现过：`tools/update.py` 的产物清单过期 → **服务器更新被中止**；同一份 `BUILD_OUTPUT` 在 `tools/update.py` 与 `tests/run.py` 各写一遍；`shared/pose_source.py` 的 `to_json` **静默改写数据**。

本轮的目标只有一个：**让"改一处"变成"改一处就够"**。减行数是副产品，不是目的。

### 零之二、第一轮质询推翻的 10 条

这 10 条不是风格问题，是**会让人按错方向施工的硬错误**。每条都附实测证据。

| # | 原判断 | 实测 | 修正 |
| --- | --- | --- | --- |
| 1 | 「`_addr` 收敛成 `tier_fields`」 | `tests/run.py:319` 已有 `Manifests.test_tier_fields_present`，`docs/ADDING_A_SITE.md:100` 也引它 | 改名 **`tier_addr_fields`**（D19） |
| 2 | 「`tier_addr` 是待被取代的旧 API」 | `index/catalog.py:41,60` 要的是**标量/元组**，站点脚本要的是**摊平 dict**——dict 版永远取代不了 | 两层 API，**不是新旧关系**（D07、§二.3） |
| 3 | 「`tier_addr` 有 6 个调用点」 | 实为 **8 个调用点 / 7 个消费方**（多出 `index/catalog.py` 这一族，契约不同） | 第 7 族**不动**（D07、§四.9） |
| 4 | 「分片 JS 写出 3 份」 | 漏了 `write_index`；且重新索引后 `midjourney-explore:write_data` 的 docstring 已是「写出 data/gallery.js（**唯一数据文件**），并清掉旧的多分片残留」 | JS 载荷写出是 **3 种写法**（mj 全量 / prompthero 分片+索引 / prompts 分片+索引），旋钮按此设计（D21） |
| 5 | 「`load_config` 读到的 `cfg["port"]` 是死代码，函数可删」 | `port` 键确实无人读，但 `load_config()` **承重**：删了 → `Handler.config` 变 `{}` → `POST /api/send` 恒 `404 unknown_target`（前端 `web/index.html:736` 硬编码 `target:"input"`） | **禁删函数，只删死键**（D16） |
| 6 | 「opener 3 份」 | 实为 **5 份**（多 `prompthero/scripts/extract.py:41`、`sites/prompts/import_youmind.py:108`、`legacy/import_gpt2.py:103`） | 收敛面更大（D22） |
| 7 | 「图谱 `SIMILAR_TO`/`bt` 相似度 = 真实重复」 | `bt` 是 **token 级**，系统性高估：`curl_json`/`curl_page` 实测 J=**0.308**（图谱报 0.690）、`fetch_page` J=**0.312**（图谱报 0.707）；`fp` 相等 **≠ 逐字节相同**（`download` 两份差 2 行） | 一切相似度结论**必须行级复核**（D00） |
| 8 | 「图谱的跨模块调用边可信」 | 跨模块边**几乎全是名字碰撞假阳性**：`json.load(f)`→`catalog.py:load`；`esc` 在 `pose_source.py:38` 是**布尔局部变量**；`parse_args`→`tools/_common.py`；`write`/`read` 同名 | 裁决原则：**图谱与 grep/git 冲突，以 grep/AST/git 为准**（D00） |
| 9 | 「图谱可直接用于施工」 | 原索引**落后 72 个文件**（mj-explore 单分片改造进行中）；`main → write_data` 调用边**缺失** | 已重新索引（3,025/11,570 → **3,005/11,533**），补齐调用边 |
| 10 | 「`docs/REFACTOR_TO_WEBUI.md:256` 是 legacy 目录的引用，删了要改」 | 该段主语是**早已删除、从未被 git 跟踪的 `mj-gallery/`** | 删 legacy **不必改它**（但已补现状说明，D29） |

**一个反向的好消息**：`shared/pose_source.py:64` 的 `to_json` 实测有三种失败形态，其中 `'it\'s'` 被**静默改成 `it"s`**——数据被改坏且不报错。这是本轮唯一「静默数据损坏」级缺陷，D23 必修。

### 零之三、三角度评审推翻的 15 条

第二版评审从第一性原理、批判性思维、终局思维三个角度重审本文，推翻 15 条并补 5 条实测数据。

| # | 角度 | 原方案 | 评审结论 | 修正落点 |
| --- | --- | --- | --- | --- |
| R1 | 第一性 | §二.1 把 AGENTS.md 第 19 条的转述当「唯一编码约定」 | 该转述**在 `online` 模式下是错的**：prompts 的 `file` 被覆写成 CDN 绝对 URL。真话在 `shared/image_policy.py:17-21` | AGENTS.md 第 19 条逐字对齐；§二.2 补三模式字段形态表 |
| R2 | 第一性 | §三.B2 的逐站表只记「字段名 + 后缀」 | 字节还取决于**原字段的值形态**与**键的增删顺序**，两列缺失 → 按原表实现极可能第一次跑就红 | B2 表扩为两张表（§三.B2） |
| R3 | 第一性 | D13（服务器更新被中止）排在 A2，前面压着 A1 | 优先级与方案自述的「先清障」**相反**；且 D03 让它等无关的 W6 | D13 提为**批次 0 热修**，不等 W6 |
| R4 | 第一性 | §四 9 条「不做」无限期延期 | 没有触发条件 = 被祝福的技术债 | 每条补「重新评估的触发条件」 |
| R5 | 第一性 | 全文只说「改什么」 | 缺根问题陈述；§六的成功判据是**活动量**不是结果量 | §零之一 补问题陈述；§六 加结果量指标 |
| R6 | 批判 | 候选集由图谱按分数排序 | 只校准了分数，没质疑过「选出来的东西」。唯一的反向证据支持图谱：`BUILD_OUTPUT` 重复**已经造成一个真 bug** | D32 优先级原则 + 每条决策标证据等级 |
| R7 | 批判 | B1 验收 =「新增函数零调用点」 | 这恰好等于**「未测试」**；字节闸门挡不住不进产物的语义变化 | B1 验收改为对真实数据的**等价断言 + 黄金基线** |
| R8 | 批判 | §零 记录了 10 条错误 | 是历史，不是协议；§一 里没有规则阻止再犯 | 新增 **D00 证据规则** |
| R9 | 批判 | 「prompts 的 `Fb` 是死键」 | 本轮**补强**：不是「写了没人读」，是**压根没写**（`if fallback:` 在 prompts 现有策略下恒假）。但 `<字段>Url` 在页面的读取路径未逐站核 | 列为 B1 前置检查项（§三.B1） |
| R10 | 批判 | 3 种字段写法 | 实测是 **6 种写入形态**（不是 3 种），且 `<字段>Path` 的守卫条件不一致：prompts 无 `and path`，另两站有 | 写入形态进 B2 表；新 API 用显式开关承载差异 |
| R11 | 终局 | CI 闸门 = `git diff --exit-code -- hub sites` | **实测更正**：改 `sites/*/README.md` **不会**让闸门变红——build 不生成 README，闸门只对 **build 会重写的文件**敏感。真问题是「产物」这个概念在**三处**各写一遍且**已经漂移**：CI 用路径前缀、`tools/update.py` 用目录正则、`tests/run.py` 用文件清单。实测漂移：`update.py` 缺 `data/gallery.js`（→ D13 的真 bug）与 `data/translations.csv`、`data/*-zh.json`；`tests/run.py` 缺 `data/meta.json` | D33 产物清单单一化 |
| R12 | 终局 | `shared/` 终局 10 个模块 | 无准入门槛，共享层会变收纳层 | AGENTS.md 新增**规则 20**（≥2 个站） |
| R13 | 终局 | 四个「唯一来源」在 3 处各存一份 | 无「以谁为准」 | CONTEXT.md 为唯一定义处，本文与 AGENTS.md 只引用 |
| R14 | 终局 | `__GALLERY__` 双语义只「登记」 | 登记挡不住下一个站作者继续写 | `shared/site_build.py` 加**必填** `semantics` 参数（D21） |
| R15 | 终局 | 方案文档没有生命周期 | 实施完变过期快照，无人知它是计划还是记录 | 头部状态字段约定（D34） |

**评审过程中新增的 5 条实测数据**（原方案里没有，本版才补）：

1. `local-first` **全仓只出现 1 次**——shisei 的 thumb 档。其余 7 站不写任何回落字段，prompts 的 `Fb` 后缀是彻底的空转。
2. 8 站的展示档位里，**7 站有 `online` 档**（只有 portrait 没有），只有 shisei 有 `local-first`。
3. 字段写入是 **6 种形态**（§三.B2 表 B），不是原以为的 3 种。
4. `shisei` 声明的 `mid` 档**没有专属展示字段**——`shared/pose_gallery.py:67` 的循环只覆盖 thumb/full，mid 图由页面从 `<字段>Path` 推导（`midOf()`）。文件照常落地，只是没有 `<字段>` 产出它。**B2 前必须现场确认**。
5. `tier_addr` 返回的第三个值在文档里叫 `path_kept`、在所有调用点叫 `keep_path`——同一件事两个名字。

## 一、36 条决策

> 每条标**证据等级**：`实测`（本次会话跑过命令或读过源码并可复现）/ `图谱`（仅 MCP 索引得出）/ `推断`。

### A 组：目标与边界

| # | 决策 | 证据 |
| --- | --- | --- |
| **D00** | **证据规则**：图谱只用于**发现候选**，不用于**判定重复**。相似度分数与跨模块同名边一律视为**待排除的假阳性**，判定必须行级复核（diff / AST / 实跑）。裁决顺序：**grep / AST / git diff > 实跑 > 图谱**。 | 实测 |
| D01 | 本轮目标排序：**先清障（真实故障）→ 再收口（口径唯一）**；减行数是副产品；清死代码并入 A1 | 推断 |
| D02 | 两条轨道：**Track A（`index/`+`tools/`）先、Track B（`shared/`+`sites/`）后**。Track A 不碰产物字节；**Track B 只允许字节不变**的改动 | 实测 |
| D03 | 本轮**只出文档与术语，不改任何代码**；实施基线 = **`cd4813a`**（W6 已完成：MJ-13/14/15 ✅、`img/` 4.33 GiB 已删、spec 升 v1.3），工作区除本轮文档改动外干净 —— **基线条件已满足，可直接进入批次 0** | 实测 |
| D04 | 字节闸门**只管入库产物**（与 CI 同口径）；**prompts 站单列人工验收清单，单独一批、单独评审**（CI `--skip prompts`，无闸门） | 实测 |
| D05 | 「唯一来源」拆成**四个不重叠**的说法：唯一**配置源** / 唯一**字段映射** / 唯一**读取入口** / 唯一**编码约定**。**定义处唯一** = `CONTEXT.md`；本文与 AGENTS.md 只引用 | 实测 |
| D06 | `__GALLERY__` 的双语义**登记不改**；`shared/site_build.py` 用**必填** `semantics` 参数强制调用点自证语义；**重命名另立工单** | 实测 |
| D07 | `tier_addr` 固化为「**档位判定**」层，`tier_addr_fields` 为「**档位字段**」层；两层共存（§二.3）。`index/catalog.py:41,60` **不动** | 实测 |
| D08 | `sites/prompts/scripts/legacy/` **归档**到 `docs/legacy/prompts-legacy-scaffold/`（`git mv`，保留 blame），**不物理删**；下轮再议 | 实测 |
| D09 | 代码文件里的**过时注释算文档**，本轮一并修（纯文本、零行为变更、零产物影响）——这个仓的主要读者是 AI 助手 | 推断 |
| **D32** | **优先级原则**：同一批候选按「**已造成过故障的重复** > 高频重复 > 结构性重复**」排序。（唯一实证：`BUILD_OUTPUT` 重复 → D13 的真 bug） | 实测 |
| **D33** | **产物清单单一化**：「产物」目前有**三份**互相漂移的定义——CI 的路径前缀 `hub sites`、`tools/update.py` 的目录正则 `BUILD_OUTPUT`、`tests/run.py` 的文件清单 `BUILD_OUTPUT`。实测漂移：`update.py` 缺 `data/gallery.js`（→ D13 的真 bug）与 `data/translations.csv`、`data/*-zh.json`；`tests/run.py` 缺 `data/meta.json`。三者合为**一份**清单（由各站 `landing.json` 的 dirs + 固定文件名推导），CI / update.py / tests 三处引用它 | 实测 |
| **D34** | **文档生命周期**：每份 `docs/REFACTOR_*.md` 头部带 `状态：设计已锁定 / 实施中 / 已实施（commit 范围）`；实施完**就地更新**，不新建文档 | 推断 |

### B 组：Track A（`index/` + `tools/`）

| # | 决策 | 证据 |
| --- | --- | --- |
| D10 | 切 3 批（A1 零风险清理 / A2 真 bug 修复 / A3 结构收敛），每批一个提交、可独立回滚、自带验收命令 | 推断 |
| D11 | `index/serve.py` 的 `Handler.db()` 改 `@contextlib.contextmanager`（11 处 4 行→1 行）；**`store.connect()` 返回形态不动**（`tests/test_manager.py:903-904` 直接用裸 Connection 并自行 close） | 实测 |
| D12 | 新建 `index/cli.py`（`ROOT` / `utf8_stdout` / `base_parser` / `db_path`）。**禁止命名 `_common.py`**——与 `tools/_common.py` 同名，而 `tests/run.py:13-14,521` 把 `tools/`、`shared/`、`index/` 同时放进 `sys.path`，会命中错的那个。**`catalog.py` 的 `--out`（CSV 文件）与 `snapshot.py` 的 `--out`（目录）同名异义，不进统一模板** | 实测 |
| D13 | `tools/update.py` 的 `BUILD_OUTPUT` **目录白名单已过期**：`(browse\|tag\|category\|series\|section\|style)`，实际 `landing.json` 用 `browse/cat/ver/aspect`。**实跑复现**：脏工作区下 `update.py --check` 报「其他改动 25 个」，其中 **12 个是纯构建产物**（11 个 `aspect/*/index.html` + `data/gallery.js`）被当手改文件 → `sys.exit(1)`（check 模式）或「已中止，什么都没改」（正式模式）→ **服务器更新被中止**。改为**从各站 `landing.json` 的 `dirs` 推导 + 显式补 `data/gallery.js`**，并与 D33 的产物清单合为一份。**提为批次 0 热修，不等 W6**。⚠️ **`changed_files()` 看的是工作区脏不脏（`git status --porcelain`），不是提交区间 diff** —— 所以这个 bug 只在**服务器端**（工作区有本地重建产物）显现；**CI 永远抓不到它**（CI 的脏工作区只可能来自 build，且已被第 3 步的 `hub sites` 覆盖）。修复时**必须补一条单测**：造一个脏工作区，断言产物被归类为「可丢弃」而非「其他改动」 | 实测 |
| D14 | `index/sync.py:34-42` 的 `COLLECTION_NAMES` 兜底清单只有 7 项，**漏 `prompthero-midjourney`、`midjourney-explore`**——与「sites.json 是唯一配置源」抵触。兜底清单必须与 `sites.json` 一致（生成或加断言） | 实测 |
| D15 | `index/serve.py` 的 `--no-reload`：全仓仅 1 处命中（定义处自身），但属**公开 CLI 契约** → 保留参数名 + help 标「已废弃」+ 传了给提示，**下个版本再删** | 实测 |
| D16 | `index/serve.py` 的 `load_config()` **禁删**（承重，见 §零之二.5）；只删 `config.json` 里无人读的 `"port"` 死键 + 修 docstring（docstring 与实现不符） | 实测 |
| D17 | `index/check_wiring.py` 补 `utf8_stdout()`（6 个 index 脚本里唯一缺它的，中文 Windows 下会抛 `UnicodeEncodeError`）；`tools/update.py` 补 `sys.stdout.reconfigure` | 实测 |

### C 组：Track B（`shared/` + `sites/`）

| # | 决策 | 证据 |
| --- | --- | --- |
| D18 | 先做 **5 项纯新增/零字节**：`shared/site_config.py`、`shared/http_client.py`、`shared/site_build.py`、`tier_addr_fields`、`download_urls`，外加修 `to_json` | 实测 |
| D19 | `tier_addr_fields(site, tier, path, url, key, *, fallback_suffix="Url", path_suffix="Path", path_if_empty=False)` —— **必须支持显式传 path/url**（prompts 的源字段名不跟档位走）；**`path_if_empty` 承载 W4/W5 的守卫差异**（默认取 W5/W6 行为，prompts 调用点显式传 `True`）。每站确切取值见 §三.B2 | 实测 |
| D20 | UI 词典**只抽 pose×pose-depth**（键序完全一致，46 键 7 值不同）。基座**必须按语言拆平**（`POSE_UI_ZH`/`POSE_UI_JA` 两个独立字典）——若基座是外层 `{"ja":…, "zh":…}`，`overlay()` 会整块替换子 dict → 子键序错 → 产物字节变 | 实测 |
| D21 | `shared/site_build.py` 的分片写出必须**由调用点显式给旋钮**：`assign` / `prelude` / 内层 `separators` / 外层 `ensure_ascii` / **`semantics`（必填，`"index"` 或 `"full"`）**。写死任一个都改字节（实测 naive 合并：prompthero 分片 −39 B、索引 −238 B） | 实测 |
| D22 | HTTP 客户端收敛为**薄包装**（`proxy_url` / `build_opener` / `warmup` / `retry_fetch`），覆盖 **5 份** opener。钩子契约 `headers(url, referer)` / `prepare(opener, log)` **签名与返回约定不变**；**`__cf_bm` 同 jar 是必须保持的不变量**（现状已共享，不是 bug） | 实测 |
| D23 | `shared/pose_source.py` 的 `to_json` 换实现体：**自写递归下降 JS 字面量解析器**（裸键/单引号/尾逗号/true-false-null/JS 转义）。`json.loads` 与 `ast.literal_eval` **都不能用**（输入是 JS 字面量）。**函数名与签名不变**；新实现须对真实 `pose.json` 回归 `old == new == original` | 实测 |
| D24 | `shared/assets.py` 加 `download_urls(jobs, ...)` 是**纯新增**；`download()` 的签名与返回格式**一律不动**（唯一消费者 `tools/fetch.py:51`）。prompts 改调须**显式传其硬编码代理**（`127.0.0.1:7897`，不是 `FETCH_PROXY`）并补 skip 计数 | 实测 |
| D25 | 逐站切换顺序：`shared/pose_gallery.py` → `portrait` → `costume` → `midjourney-explore` → `prompthero`；**每站一个提交**，每步 `git diff --exit-code -- hub sites` 必须为空 | 推断 |
| D26 | prompts 站**人工验收 4 步**（§三.B3）。它被 CI `--skip`，**没有任何闸门**，是本轮唯一会静默改线上站点的洞 | 实测 |

### D 组：文档与术语

| # | 决策 | 证据 |
| --- | --- | --- |
| D27 | 新建 `CONTEXT.md`（**术语活文档**，也是四个「唯一来源」的**唯一定义处**）。只收本轮会碰的词 | 推断 |
| D28 | `AGENTS.md` 第 3 条与第 19 条**自相矛盾**（第 3 条称「约定只有一条」，第 19 条又立了编码约定）→ 拆成两条明确约定；规则 1/11/19 分别标注四种「唯一来源」；**第 19 条的编码约定逐字对齐 `shared/image_policy.py:17-21`**；新增**规则 20**（`shared/` 准入门槛：≥2 个站） | 实测 |
| D29 | `README.md:159`「六个集合」→ 8；`sites/prompts/README.md:87` legacy 口径 → 改为归档口径（与 D08 同提交）；`docs/REFACTOR_TO_WEBUI.md:256` 追加一句现状说明（它讲的是 `mj-gallery/`，不失效但易误读） | 实测 |
| D30 | 5 处过时 docstring 修正：`index/catalog.py:2`「六份」→8；`shared/assets.py:2`「四站」→8（并补全档位清单）；`shared/landing.py:2`「四站」→8；`index/serve.py:2`「10 个端点」→11；`README.md:159` 同 D29 | 实测 |
| D31 | ADR **候选 2 条**（§五），本轮**不写**；方案被采纳后单独落 | 推断 |

### E 组：提交与推送（本轮补遗）

这一组是实施流程本身的规约。**没有它，前面的批次划分落不了地**——批次的意义就是「一个可独立验证、可独立回滚的提交」。

| # | 决策 | 证据 |
| --- | --- | --- |
| **D35** | **提交与推送规约**：<br>(1) **一批 = 一提交**，提交信息用仓内既有风格 `type(scope): 描述`（`docs`/`fix`/`feat`/`chore`/`data`/`refactor`），**并带方案编号**——如 `refactor(shared): 抽出 tier_addr_fields（D19）`，使 commit 与本文可双向追溯；<br>(2) **push 前必须本地跑完 CI 的 5 步等价物**（§三.Push 前检查），全绿才 push；<br>(3) ⚠️ **闸门那步 CI 用 Python 3.8**（最低版本），而本地只有 3.14 / 3.11 / 3.12 —— **本地 build 绿 ≠ CI 绿**。改了构建脚本的批次，要么本地补一个 3.8 复跑闸门，要么接受首轮 CI 可能红并预备补提交；<br>(4) **默认直推 main**（与仓内既有实践一致：无 merge 提交，采集脚本自动提交推送）；**唯独改了 `shared/` / `sites/` 构建脚本的批次建议走 PR** —— 因为闸门那步 CI 用 Python 3.8，本地复现不了，PR 能让 CI 在合并前拦一次；<br>(5) **回滚粒度 = 批次粒度**：revert 也必须带上重建后的产物（否则 revert 后闸门红）；<br>(6) **文档类改动不受「必须带产物」约束**——README / NOTICE 不是 build 的产物，闸门也不比对它们 | 实测 |

**关于 CI 闸门的真实语义**（本轮实测更正，供实施时参考）：

`git diff --exit-code -- hub sites` 比的是**工作区 vs index**，不是「产物语义是否正确」。因此：

- ✅ 它精确捕获「改了构建逻辑但没提交重建后的产物」——这是它的设计目的，**不要削弱它**。
- ❌ 它**不会**因改 `sites/*/README.md`、`sites/*/NOTICE.md`、`sites/*/scripts/*.py` 而变红（build 不重写这些文件）。
- ⚠️ 它**捕获不到** build 产物中不在 `hub`/`sites/` 前缀下的部分——这是 D33 要收敛的缺口。


## 二、契约

### 1. 四个「唯一来源」——判别方法

> **定义与边界以 [`../CONTEXT.md`](../CONTEXT.md) 为准。** 本表只用于判别某段文字在说哪一个。

| 名称 | 唯一的东西 | 归属 | **不**覆盖 |
| --- | --- | --- | --- |
| **唯一配置源** | 站点、顺序、授权、落地档位、图片目录、取图策略、图片源前缀 | `sites.json` | 字段映射、读取逻辑、产物内嵌约定 |
| **唯一字段映射** | 9 份 manifest → 统一 CSV 的字段对应 | `index/catalog.py` 的 `SOURCES` | 站点清单、策略语义、读取逻辑 |
| **唯一读取入口** | 读取代图策略并判定展示档位如何显示 | `shared/image_policy.py` | 站点清单、字段映射、产物编码 |
| **唯一编码约定** | 产物内嵌字段的后缀与语义 | `shared/image_policy.py` 的模块注释 | 站点清单、字段映射、策略取值 |

口诀：**改站点行为 → 配置源；改字段对应 → 字段映射；改取图判定 → 读取入口；改产物里的字段名与形态 → 编码约定。**

> 落败的旧说法：「档位与 manifest 的约定**只有一条**」（`AGENTS.md` 第 3 条）。它被第 19 条的编码约定打破，两条并存却只有一条被承认。已修正。

### 2. 编码约定：三种策略下的字段形态（R1 的核心）

真话在 `shared/image_policy.py:17-21`，AGENTS.md 第 19 条曾把它转述错（已在 D28 修正）。

| 策略 | `<字段>` | `<字段>Url` | `<字段>Path` | 保留站内路径 |
| --- | --- | --- | --- | :---: |
| `local-first` | 站内相对路径 | **上游地址**（回落目标） | 不写 | False |
| `online` | **上游地址** | 不写 | **站内相对路径** | True |
| `local-only`（默认） | 站内相对路径 | 不写 | 不写 | False |

未声明的档位按 `local-only`（`shared/image_policy.py:42-44`）。

> ⚠️ **「原字段永远是站内相对路径」是错的**——`online` 档下它就是上游绝对地址（实测：prompts 的 `file` 被覆写成 CDN URL，站内路径挪到 `filePath`）。
> ⚠️ `tier_addr` 第三个返回值在模块注释里叫 `path_kept`、在所有调用点叫 `keep_path`——同一件事，两个名字。归一为 `keep_path`，注释同步改。

**实测：`local-first` 全仓只出现 1 次**——shisei 的 thumb 档。其余 7 站不写任何回落字段；prompts 的 `thumbFb`/`fileFb` 因 `if fallback:` 恒假而**从未被写出**。

### 3. 两层档位 API

| 层 | 回答什么 | 谁用 | 形态 |
| --- | --- | --- | --- |
| **档位判定** | 这个展示档位这次显示哪个地址？要不要给上游回落？要不要保留站内相对路径？ | `index/catalog.py` | **标量/元组** |
| **档位字段** | 把判定结果摊平成页面直接可用的字段集合 | 站点构建脚本 | **dict** |

`index/catalog.py:41,60` 要标量，站点脚本要 dict——**两者永不可合并**。不要试图统一。

### 4. 产物字节不变协议（Track B）

```bash
# 每一步切换后必须全绿
python tools/build.py --skip prompts
git diff --exit-code -- hub sites      # 入库产物：零差异
python tests/run.py
python tests/test_manager.py           # 需 Pillow
```

`.gitattributes` 的 `* text=auto eol=lf` 意味着 **CRLF/LF 差异不算差异**（git 比对前会归一），**内容差异一定红**。实测确认：工作区 CRLF 文件 `git diff` 为空。

> ⚠️ 这个闸门是**路径级全量比对**，不区分产物与产物旁的说明文档——改一行 `sites/*/README.md` 也会让它变红。D33 会把它改成**只比产物清单**；在此之前，改 `sites/` 下的非产物文件时必须同提交带上重建产物。

## 三、批次与验收

### Push 前检查（每个批次提交前，缺一不可）

CI 的 5 步在本地有等价物。**本地全绿才 push**（D35.2）：

```bash
# 1-2：测试（CI 用 3.13；本地 3.14 亦可，失败才需要降版本复跑）
python tests/run.py
python tests/test_manager.py                 # 需 Pillow

# 3：闸门 —— ⚠️ CI 用 Python 3.8，本地无 3.8 时这步只能近似
python tools/build.py --skip prompts
git diff --exit-code -- hub sites            # 必须为空

# 4：发布脚本
python tools/release.py --no-images --out "$TEMP/dist-local"

# 5：更新检查
python tools/update.py --check --no-fetch --ref HEAD
```

**正确的提交姿势**（闸门要在提交之后验，因为 `git diff` 比的是工作区 vs index）：

```bash
# 改完 → 先 build → 再看差异 → 把产物一起提交
python tools/build.py --skip prompts
git status --short hub sites
git add -A
git commit -m "refactor(shared): ...（D19）"
git diff --exit-code -- hub sites             # 提交后工作区应当干净
```

**Push 之后 CI 红了怎么办**：优先 `git commit --amend` 补产物（未被别人拉取时）；已被拉取则走 `git revert`（并**同时 revert 产物**）。

### 批次 0：热修（不等 W6）

| 批 | 内容 | 验收 |
| --- | --- | --- |
| **0** | `tools/update.py` 白名单（D13）· 产物清单单一化（D33，CI 与 `update.py` 共用一份） | `update.py --check --no-fetch --ref HEAD` **不再报构建产物为「其他改动」**；CI 绿；`tests/run.py` 绿 |

> 理由：这是全方案唯一**当前正在造成生产故障**的项，与其它工作无依赖关系，不该排在零价值的清理之后。W6 已于本轮完成，基线条件已满足（见 D03）。

### Track A（`index/` + `tools/`）—— 不碰产物字节

| 批 | 内容 | 验收 |
| --- | --- | --- |
| **A1** 零风险清理 | legacy 归档（D08）· mj-explore `esc`+`import html` 同提交删 · costume 重复 import · `--no-reload` 标废弃 · `load_config` 删死键 `port` · 5 处过时注释（D30） | `tests/run.py` + `tests/test_manager.py` 绿；`git diff --exit-code -- hub sites` 仍绿 |
| **A2** 真 bug 修复 | `tools/update.py` `stdout.reconfigure`（D17）· `index/check_wiring.py` `utf8_stdout`（D17）· `index/sync.py` 兜底清单补 2 站（D14） | 两个测试入口绿；`update.py --check` 绿 |
| **A3** 结构收敛 | `Handler.db()` → contextmanager（D11）· 新建 `index/cli.py`（D12） | 11 处调用点 4 行→1 行；`store.connect()` 返回形态未变；`tests/test_manager.py` 绿 |

### Track B（`shared/` + `sites/`）—— 必须字节不变

| 批 | 内容 | 验收 |
| --- | --- | --- |
| **B1** 纯新增 | `site_config.py`（D20）· `http_client.py`（D22）· `site_build.py`（D21）· `tier_addr_fields`（D19）· `download_urls`（D24）· 修 `to_json`（D23） | **每个新函数对真实数据与旧内联实现做逐键逐值逐顺序的等价断言**（不是「零调用点」）；另存 5 站产物 JSON **黄金基线**；`git diff --exit-code -- hub sites` 为空；`to_json` 回归 `old==new==original` |
| **B2** 逐站切换 | `pose_gallery` → `portrait` → `costume` → `midjourney-explore` → `prompthero`（D25） | 每站一提交；每步 `git diff --exit-code -- hub sites` **必须为空**；与 B1 黄金基线**逐键逐序**比对 |
| **B3** prompts 单批 | prompts 站的 `_addr` 与分片写出切换 | **人工验收 4 步**（见下），单独评审 |
| **B4** 收口 | `__GALLERY__` 歧义登记（D06）· AGENTS.md/CONTEXT.md 口径（D27–D30）· prompts `Fb` 死键处置（**不动**） | 两个测试入口绿；`git diff --exit-code -- hub sites` 为空 |

**B1 的前置检查**（不做就开始写，会踩坑）：

1. `<字段>Url` 在页面的读取路径逐站 grep 确认——目前只有 shisei 写这个字段，其余站不写；页面若读了不存在的字段，行为不变，但要确认。
2. `shisei` 的 `mid` 档**没有专属展示字段**（`shared/pose_gallery.py:67` 的循环只覆盖 thumb/full）——现场确认 mid 图的取用路径（页面 `midOf()` 从 `<字段>Path` 推导），再决定要不要给它一个字段。

**B3 人工验收 4 步**（prompts 无 CI 闸门，这 4 步就是它的闸门）：

1. `python tools/build.py --site prompts` 本地重建
2. 与当前 `sites/prompts/data/` 逐字节 diff（`gallery.js` / `gallery_<key>.js` / `landing.json` / `gpt2_categories.json`）
3. `manifest.json` 行数不变（**41,261**）
4. 页面实测：默认模型加载、切模型分片加载、灯箱开合、分类筛选

### B2 的逐站规格（R2、R10）

#### 表 A：字段与值形态

| 站点 | 档位 → 字段 | 该档策略 | `<字段>` 的值 | `<字段>Url` | `<字段>Path` | 路径归一 |
| --- | --- | --- | --- | :---: | :---: | :---: |
| portrait | thumb → `t` | local-only | 站内相对路径 | — | — | 无 |
| portrait | full → `f` | local-only | 站内相对路径 | — | — | 无 |
| costume | thumb → `th` | local-only | 站内相对路径 | — | — | 无 |
| costume | img → `im` | local-only | 站内相对路径 | — | — | 无 |
| costume | png → `pg` | online | **上游 URL** | — | 站内相对路径 | 无 |
| pose / pose-depth | thumb → `t` | local-only | 站内相对路径 | — | — | ✅ |
| pose / pose-depth | full → `f` | online | **上游 URL** | — | 站内相对路径 | ✅ |
| shisei | thumb → `t` | **local-first** | 站内相对路径 | ✅ 上游地址 | — | ✅ |
| shisei | mid → — | local-only | **不经 `tier_addr`**（无专属字段，页面从 `<字段>Path` 推导） | — | — | ✅ |
| shisei | full → `f` | online | **上游 URL** | — | 站内相对路径 | ✅ |
| prompts | thumb → `thumb` | local-only | 站内相对路径 | — | — | 无 |
| prompts | full → `file` | online | **上游 URL** | — | 站内相对路径 | 无 |
| midjourney-explore | thumb → `t` | local-only | 站内相对路径 | — | — | 无 |
| midjourney-explore | mid → `m` | local-only | 站内相对路径 | — | — | 无 |
| midjourney-explore | full → `g` | online | **上游 URL** | — | 站内相对路径 | 无 |
| prompthero | thumb → `s` | local-only | 站内相对路径 | — | — | 无 |
| prompthero | mid → `m` | local-only | 站内相对路径 | — | — | 无 |
| prompthero | full → `g` | online | **上游 URL** | — | 站内相对路径 | 无 |

> **portrait 是唯一没有 `online` 档的站**——它的产物里没有任何 `*Url` / `*Path` 字段。
> **`local-first` 全仓只出现 1 次**（shisei/thumb）——`<字段>Url` 只在这一处被写出。

#### 表 B：写入形态（6 种，字节相关）

| # | 站点 | 容器 | 键的位置 | `<字段>Path` 的守卫 | 取 path 的方式 | 被 pop 的键 |
| --- | --- | --- | --- | --- | --- | --- |
| W1 | portrait | `item[fkey]` | 原地 update | `if keep_path:` | `r[tier+"_path"]` | — |
| W2 | costume | `item[fkey]` | 原地 update | `if keep_path:` | `r[tier+"_path"]` | — |
| W3 | pose / pose-depth / shisei | `view[fkey]` | 原地 update | `if keep_path:` | `r[tier+"_path"].replace("\\","/")` | — |
| W4 | prompts | `r[fkey]` | 原地 update | `if keep_path:`（**无 `and path`**） | `r[fkey]` | `url`、`thumbUrl`（另 rawPrompt / promptRaw / params / originId） |
| W5 | midjourney-explore | `**_addr(...)` | **dict 展开 → 追加到末尾** | `if keep_path and path:` | `rec.get(tier+"_path") or ""` | — |
| W6 | prompthero | `**_addr(...)` | **dict 展开 → 追加到末尾** | `if keep_path and path:` | `rec.get(tier+"_path") or ""` | — |

> ⚠️ **W4 与 W5/W6 的差异必须在新 API 里可表达**：prompts 在 path 为空串时仍写 `<字段>Path: ""`，另两站不写该键。D19 的 `path_if_empty` 承载它——**默认取 W5/W6 行为**（更安全），prompts 调用点显式传 `True`。
> ⚠️ **键的位置不同 = 字节不同**：W1–W4 原地 update 保留原键位置，W5/W6 的 `**` 展开把新键追加到末尾。这不是风格问题，是 JSON 序列化的顺序。

## 四、不做什么

每条都带**重新评估的触发条件**——否则它就只是被祝福的技术债（R4）。

| # | 不做 | 理由 | 重新评估的触发条件 |
| --- | --- | --- | --- |
| 1 | 不合并 8 站 UI 词典（只做 pose×pose-depth） | 键序=字节；shisei 尾部另有 3 键 | 出现第 3 个与 pose 键序一致的站 |
| 2 | 不抽 `build_facets` / SEO build 三件套 | 分面拓扑 3 层/2 层/2 层、业务字段零交集，硬抽必然长出 `if site ==`（违反 AGENTS.md 第 19 条） | 出现第 3 个与 pose 拓扑一致的站 |
| 3 | 不做 `__GALLERY__` 重命名 | 要动页面 JS → 改产物字节 | 另立工单时；或 `shared/site_build.py` 的 `semantics` 参数落地满 3 个调用点后 |
| 4 | 不让 `index/` 依赖 `shared/` 或 `tools/` | `index/sync.py:27-30` 明写「单独拷走 index/ 时仍然能跑」 | 出现必须跨层复用的真实需求（先证明 `index/_common.py` 不够） |
| 5 | 不建 `index/_common.py` | 与 `tools/_common.py` 同名，`tests/run.py` 的 `sys.path` 会命中错的那个 | `tests/run.py` 的 `sys.path` 顺序改为显式包路径 |
| 6 | 不做 `index.html` 骨架模板化 | 改字节就红 | 出现第 3 种页面骨架（且已能逐字节复现） |
| 7 | 不碰 `copy_og_cover` | `shared/` 禁 Pillow；两版不是同一件事 | 引入独立构建产物清单机制后 |
| 8 | 不合并 `tests/run.py` 与 `test_manager.py` | 交集仅 `unittest.main`；合并会让免 Pillow 的 `run.py` 依赖需 Pillow 的 `test_manager.py`，破坏 CI 双入口 | CI 引入 pytest 且两套都能免 Pillow 跑 |
| 9 | 不动 `index/catalog.py:41,60` 的 `tier_addr` 调用 | 契约不同（标量 vs dict），统一会破 | `index/catalog.py` 的消费方从 1 个涨到 2 个以上 |

## 五、开放项

| # | 开放项 | 建议 |
| --- | --- | --- |
| 1 | **ADR 候选 2 条**（满足全部三条门槛）：①「静态站构建产物必须与仓库逐字节一致」②「四个『唯一来源』各司其职，互不越界」 | 方案被采纳后写 `docs/adr/0001-…`、`0002-…`。第三条候选「`index/` 可整目录拷走」因**已是既有约束**，写成 AGENTS.md 的一条明确规则而非 ADR |
| 2 | `__GALLERY__` 双语义重命名工单 | 单独排期；允许产物变化，须同提交重建 |
| 3 | prompts 的 `thumbFb`/`fileFb` 死键 | 本轮**不动**；若将来把 prompts 转 local-first，必须同时给页面 JS 加回落读取 |
| 4 | `to_json` 解析器的单测 | B1 批内补：8 个边界用例（含 `'it\'s'` 静默改值这条）+ 真实 `pose.json` 回归 |
| 5 | ADR 存仓库还是存 MCP | codebase-memory-MCP 自带 `manage_adr`（跨会话留存、不进版本库）。建议**存仓库**（人可读、进 git、能 review），MCP 那份可作索引副本 |
| 6 | `tools/update.py` 与 `tests/run.py` 的 `BUILD_OUTPUT` 仍是两套 | **由 D33 一并消灭**（不再是待办）——CI 与 `update.py` 共用一份产物清单 |
| 7 | `shisei` 的 `mid` 档没有专属展示字段 | B1 前置检查确认：要么给 mid 一个专属字段，要么在 `sites.json` 里注明 mid 靠路径推导、不参与策略判定 |
| 8 | `tier_addr` 的 `path_kept` / `keep_path` 两个名字 | 归一为 `keep_path`，改 `shared/image_policy.py` 的注释 |

## 六、什么算做完了

**活动量**（改了多少，可机械核对）：

| 判据 | 怎么验 |
| --- | --- |
| 收敛到位 | `tier_addr` 的调用点从 8 降到 2（`index/catalog.py` 那 2 个按设计保留）；站点构建脚本里不再有内联 `_addr` |
| 口径统一 | 4 个「唯一来源」在 AGENTS.md、CONTEXT.md、代码注释三处措辞一致 |
| 零回归 | 两个测试入口绿；`git diff --exit-code -- hub sites` 绿（Track B 每步） |
| 留痕 | 每个批次一个提交，提交信息写明「字节不变」或「字节变化及原因」，并**带方案编号**（D35.1） |

**结果量**（变好了多少，这才是目的）：

| 判据 | 怎么验 |
| --- | --- |
| 故障已清 | `update.py --check` 不再把构建产物当手改文件；`to_json` 不再静默改数据；`sync.py` 兜底清单与 `sites.json` 一致 |
| **改一处就够** | 改任一站的展示档位策略，**不需要**改第二个站的文件 |
| **新增第 9 个站** | 不需要改 `shared/` 以外的任何代码（`tools/` 零改动，`index/` 不变） |
| **闸门不再被绕过** | 改 `sites/` 下的说明文档不会让 CI 变红（实测已如此，D33 要补的是「产物清单」口径而非闸门范围） |
| **可追溯** | `git log --grep=D19` 能找到该条决策的全部实施提交；任一提交都能反查回本文的决策编号（D35.1） |
