# Styles 数据线可行性结论

> 状态：**可行并已落地 —— 登录态下单次取到 Top day 全量 200 个风格码；每码三张示例图匿名可下（§11，2026-11-03 定案）；累计 329 码已生成可浏览页面 `/midjourney-explore/styles/`（§12）**
> 日期：2026-11-02（首版 22:30，定案 23:40）；2026-11-03 追加 §10、§11 两次修正
> 方法：前端 bundle 反查 + 生产采集链路实测 + 登录态 Chrome（Playwright/CDP）实测
> 结论前置：**Styles 的「列表 / 排行」只在登录态下存在，匿名无旁路（§4）。
> 登录态下 `/api/explore-srefs` 一次可取 Top day 全量 200 个码（§11.1）；
> 每码有三张语义化示例图 `portrait / landscape / still_life`，CDN 直连匿名可下（§11.3）。
> 接口本身只能在浏览器页面上下文里调用 —— 用 cookie 走 Python 直连会稳定 500（§11.2）。**

---

## 一、结论摘要

| 问题 | 判定 | 依据等级 |
|---|---|---|
| Styles 是不是独立数据线 | **是**，不是 Images 的子集 | 实测（浏览器 DOM + 截图） |
| URL 参数 | `?tab=styles_top` = Styles 内容类型 + Top day 排序 | 实测 |
| **接口端点** | **`/api/explore-srefs`**（**不是** `/api/explore` 换 `feed`） | ✅ **已实测**（bundle + 错误信息分化） |
| feed 可取值 | `styles_random` / `styles_hot` / `styles_top` / `styles_top_week` / `styles_top_month` | ✅ bundle 常量表 |
| **是否需要登录态** | **需要。匿名无旁路。** | ✅ **已实测**（三重证据，见 §4） |
| 匿名调该接口的结果 | `500 {"error":"Internal server error"}` | ✅ 实测 |
| 与现有采集的关系 | 完全不同的数据集，不能塞进 jobs 流程 | 实测（DOM 结构） |
| 示例图能否本地化 | **能，且是单张高清图**：每码三张 `portrait/landscape/still_life`，128/384/640/1024 四档（§11.3 推翻了 §10 的「只有拼图」结论） | ✅ 实测 §11 |
| 榜单 / 列表能否匿名取 | ❌ 不能（需登录，§4）；登录态下 Top day 一次取全 **200** 条（§11.1） | ✅ 实测 |
| 码从哪来（不登录） | 图片流每条作业的 `prompt.styleRef`（`t=="seed"`），已有 | ✅ 实测 §7 |
| 现在能否动手 | ✅ **已落地**：`scripts/dump_styles.py`（取码）+ `scripts/fetch_styles.py`（下图） | §11.4 |

---

## 二、端点是怎么定下来的

### 2.1 先证明 `feed` 不是选择器

用生产链路（`extract.py` 的 opener + CF 通行证 + `API_HEADERS`）请求 `/api/explore`，把 `feed` 换成 5 个候选值：

| feed | 返回字节数 | 首条 id MD5 |
|---|---|---|
| `top` | 77943 | `aab4dd29ba` |
| `styles_top` | 77943 | `aab4dd29ba` |
| `styles` | 77943 | `aab4dd29ba` |
| `styles_likes` | 77943 | `aab4dd29ba` |
| `styles_hot` | 77943 | `aab4dd29ba` |

**逐字节完全相同** ⇒ `/api/explore` 对 `feed` 不做区分（至少在匿名下）。所以问题不是「feed 值猜错了」，而是**端点选错了**。

> 这也解释了仓库里那条曾经的误判：早期实测发现「换成 `styles_*` 返回值不变」，
> 据此推论「官网没有独立的风格数据源」—— **观察是对的，推论是错的**。
> 参数不生效 ≠ 数据不存在，可能是走错了端点。

### 2.2 从 bundle 里挖出真实端点

explore 页是 SPA shell（HTML 仅 5.7 KB，数据全靠 JS 拉）。入口是
`/public/out/clientSideEntry-h0zd935e.js`（6.3 MB，单包全量），里面直接写着：

```js
// 两个取数函数，端点不同
sue = async (e, t, r, o) => {                       // → Styles
    a = { page: t.toString(), user_id: e.userId, _ql: "explore", feed: e.feed }
    i = new A5("https://www.midjourney.com/api/explore-srefs")
    ...
}
lue = async (e, t, r, o) => {                       // → Images
    a = { page: t.toString(), feed: e.feed, user_id: e.userId, _ql: "explore" }
    i = new A5("https://www.midjourney.com/api/explore")
    ...
}
```

同处还确认了两个混淆常量：`M6 = {Label:"_ql", ...}`、`E6 = {..., EXPLORE:"explore"}` ——
即 `_ql=explore`（小写）。这一条纠正了首版探测时误用大写 `EXPLORE` 的问题。

**feed 取值表**（bundle 里的常量，非推断）：

```js
_zt = [{key:"styleCreator.feedType.liked",        value:"liked"},
       {key:"styleCreator.feedType.recentlyUsed", value:"recently_used"},
       {key:"styleCreator.feedType.topDay",       value:"styles_top"},
       {key:"styleCreator.feedType.topWeek",      value:"styles_top_week"},
       {key:"styleCreator.feedType.topMonth",     value:"styles_top_month"}]
Rot = ct(["styles_random","styles_hot","styles_top","styles_top_week","styles_top_month"])
```

URL tab 全集（路由解析器）：`styles_random` / `styles_hot` / `styles_top` /
`styles_top_week` / `styles_top_month` / `styles_likes` / `styles_search`。

### 2.3 端点正确的第二个证据：错误信息分化

同一个 `/api/explore-srefs`，只换 `feed`：

| 请求 | 响应 |
|---|---|
| `feed=top`（图片榜的值） | `500 {"error":"Failed to fetch explore_style feed"}` |
| `feed=styles_top_day`（拼错的值） | `500 {"error":"Failed to fetch explore_style feed"}` |
| **`feed=styles_top`** | `500 {"error":"Internal server error"}` ← **错误类型不同** |

「feed 不认识」和「feed 认了但后续崩了」是两种错误。说明 `styles_top`
确实是这个端点的合法取值 —— 崩在后面那步（登录态校验）。

---

## 三、响应结构（来自 bundle，非实测）

`/api/explore-srefs` 的返回元素最少包含两个字段：

```js
{ id: `0_${code}`, formatted_sref: code }
```

即 `id = "0_2083416840"`、`formatted_sref = "2083416840"`。示例图与其余字段
未能在匿名下取得，**保持未知**（不编造）。

另有两个相关端点，同样需要登录：

| 端点 | 用途 | 匿名实测 |
|---|---|---|
| `/api/explore-styles-likes?page=N` | 我点赞过的风格 | `401 Unauthorized` |
| `/api/styles-vector-search?prompt=<词>&page=1` | 按词模糊搜风格 | `401 Unauthorized` |
| `/api/style-explorer`（POST） | Style Creator 的推荐排序，body 是 `grid_selections` | `405 Method not allowed`（仅 POST；非查询端点） |

---

## 四、登录门槛：三重证据

### 4.1 代码层（最硬）

`clientSideEntry` 里决定数据源的推演逻辑，原文：

```js
if (l.status === "authenticated")
    switch (R.tab) {
        ...
        case "styles_likes":
            I = { type:"styles_likes", userId: l.firebase.id }; break;
        case "styles_random": case "styles_hot": case "styles_top":
        case "styles_top_week": case "styles_top_month":
            I = { type:"styles", feed: R.tab, userId: null }; break;   // → explore-srefs
        ...
    }
else
    I = { type:"explore", feed: R.tab, userId: null };                 // → explore（图片流）
```

**匿名分支不看 tab**：`I` 直接就是 `type:"explore"`。所以匿名用户打开
`?tab=styles_top`，前端根本不会去请求 `/api/explore-srefs`，而是照旧请求图片流。

### 4.2 接口层

| 请求（带 CF 通行证 + `X-CSRF-Protection: 1`） | 结果 |
|---|---|
| `/api/explore-srefs?page=0&feed=styles_top&_ql=explore` | `500 Internal server error` |
| 同上 + `user_id=`（空） | `500` |
| 同上 + `user_id=null`（字面量） | `500` |
| 同上 + 真实 user_id（取自图片流的作业作者） | `500` |
| `/api/explore-styles-likes?page=0` | `401 Unauthorized` |
| `/api/styles-vector-search?prompt=cyberpunk&page=1` | `401 Unauthorized` |

`401` 是明确的「要鉴权」；`500` 是服务端在拿不到当前用户时崩了 —— 两者都不是「参数不对」。

### 4.3 页面层（排除 SSR 旁路）

`/styles/0_2083416840` 详情页返回 **5887 字节纯 shell**，
`initialProps` 里只有 `initialUserInfo: {"status":"anonymous"}` 等框架字段，
**没有任何 style 数据、没有 JSON-LD、正文无 `sref` 字样**。

⇒ 不存在「页面 SSR 里白拿数据」这条旁路。

### 4.4 结论

三条独立证据一致：**Styles 是登录后才有的一条数据线，匿名无旁路。**

---

## 五、数据结构对比

| 维度 | 现有 Images 线（jobs） | Styles 线 |
|---|---|---|
| 主键 | job UUID | style code（`0_<数字>`） |
| 每项图片数 | 4 格（`_0` ~ `_3`） | **8 格拼图（4 列 × 2 行），无单张**（§10.1） |
| 有提示词 | 有（`decodedPrompt`） | **无** |
| 有作者 | 有 | **无**（DOM 层不可见） |
| 有宽高比 | 有（`prompt.ar`） | **无**（拼图整体 853×640） |
| 有 jobType | 有（grid/upscale） | 无 |
| 详情页 | `/jobs/<uuid>` | `/styles/0_<code>` |

⇒ 即使能采，**也无法复用现有 jobs 采集/建站管线**。`manifest.py`、
`build_gallery.py` 的分面模型（宽高比、jobType、sref）对 style 全部失效。

---

## 六、可行性判定

| 层面 | 判定 |
|---|---|
| 数据存在且独立 | ✅ 确定 |
| 端点已定位 | ✅ `/api/explore-srefs`，feed 取值已确认 |
| 数据结构可解析 | 🟡 部分（只知道 `id` + `formatted_sref`，示例图字段未知） |
| **可自动采集（匿名）** | **部分可 —— 单条封面图可以，榜单列表不行**（§10 推翻了本行原结论） |
| 图片可本地化 | ⚠️ 纠正：可（走 `fetch_hook` 通行证，非裸请求）。原判「CDN 403」是**缺 `__cf_bm` 通行证**所致，不是图片本身受限 |
| 站点可展示 | ✅ 可（本地 WebP，或 CDN 直链，与 full 档同策略） |
| 信息量 | 🟡 低（只有码 + 8 格拼图，无提示词/无作者/无标签） |

### 建议（2026-11-03 修正）

原结论「不做」只在**榜单/列表**这个口径上成立。**单条风格封面图可以采**，且不需要登录（§10）。

要不要做，取决于口径：

| 口径 | 可行性 | 规模上限 |
|---|---|---|
| 「原站 Styles 全集」 | ❌ 需要登录才能拿到码清单，不做 | — |
| 「图片流里出现过的码 + 其示例图」 | ✅ 匿名可做，已验证 | 每天约 17 个码 → 14 张图，需按天累积 |
| 「补全某个已知码的示例图」 | ✅ 匿名可做，只需一次请求 | 任意已知码 |

**若仍要「原站 Styles 全集」，理由按权重排序（这四条只针对榜单口径）：**

1. **过不了自动化门槛**。唯一的自动化路径是维护登录 cookie，而它必然过期
   （Firebase ID token 小时级、refresh token 也有限期），意味着定时任务会周期性地
   静默失效 —— 比不做更糟，因为失败是无声的。
2. **信息量低**。一个 style 的可采信息只有码和示例图，没有提示词、没有作者、
   没有标签，站内可做的筛选维度几乎为零。
3. ~~示例图拿不到~~ —— **这条已作废**，§10 实测可下载。
4. **条款风险**。现有站点的 `NOTICE.md` 明确定位是「公开榜单」，加一条要求登录的
   私有视图，性质变了。

---

## 七、免费替代：图片流里本来就有 sref 码

风格码**不需要**走 Styles 线也能拿到 —— 图片流的每条作业都带 `prompt.styleRef`：

```json
"styleRef": [{"t": "seed", "content": "2245733539", "weight": 1},
             {"t": "url",  "content": "https://s.mj.run/sEdWt_pv4Xw", "weight": 1}]
```

实测一页 50 条作业：**7 条带 styleRef，去重 13 个码**（`t` 分布：`seed` 8 个、`url` 5 个）。

现有 `extract.py:style_refs()` 已正确处理（只收 `t=="seed"` 的数字码，跳过 `t=="url"`
的图片型参考）。这批码已经在 `jobs.json` 的 `sref` 字段里，WebUI 的
`facet: 风格参考` 用的就是它。

**结论：不需要新数据线，sref 码已经是免费副产品。**

---

## 八、两轮误判的记录（避免再犯）

| # | 误判 | 错因 | 纠正 |
|---|---|---|---|
| 1 | 「官网没有独立于热门榜的风格榜数据源」 | 把 URL 的 `?tab=` 换成 `styles_*` 看 HTML 字节相同，就推论不存在。但 `?tab=` 是前端路由参数，SPA 返回同一份 shell 属正常 | Styles 是页面右上角的内容类型开关，不是 URL tab |
| 2 | 「`?tab=styles_top` 已被上游当默认图片流处理，该 tab 失效」 | 用 WebFetch（无登录态）抓该 URL 看到图片网格 | 匿名会被**降级**为图片流，不是 tab 失效 |
| 3 | 「端点是 `/api/explore?feed=styles_top`」 | 由 `?tab=top` ↔ `feed=top` 的映射外推 | Styles 有**独立端点** `/api/explore-srefs`，不是换参数 |

三条的共同教训：**同一个 URL / 同一个参数名，在不同登录态、不同端点上语义不同。
用「换个参数值看结果变不变」去证明「数据不存在」，前提是先确认那个参数真的是选择器。**

---

## 九、如果要做：两条路线，别混在一起

| 路线 | 需要什么 | 能否自动化 | 见 |
|---|---|---|---|
| **A 榜单 / 列表**（有哪些风格、排行、点赞、作者） | 登录态 | ❌ 不能（cookie 必然过期） | 本节 |
| **B 码 → 封面图**（这个码长什么样） | 只需要码 | ✅ 能，匿名 | §10 |

### 路线 A 的前置条件

必须先拿到一个**能自动续期的登录态**，否则免谈。可能的路线（按可行性排序）：

1. **放弃定时，改手动导出**：用户登录后，用浏览器扩展在页面里执行一次导出，
   把结果落成本地 JSON。频率低（月级），不做定时任务。
2. **cookie 注入 + 失效告警**：把 `__session` / Firebase token 存本地，
   定时任务用它们请求；一旦 401/500 就发告警提醒续期。**能跑但会周期性静默失败**，
   需配套告警，复杂度高于收益。
3. **不做**（当前建议）。

### 路线 A 真要实施时的最小轮廓（**暂不执行**）

| 层 | 新增内容 |
|---|---|
| 采集 | `scripts/extract_styles.py` → `data/daily/<日期>/styles.json`（独立于 jobs） |
| 索引 | `styles_manifest.json`（code 为键，示例图 URL 列表） |
| 构建 | `build_gallery.py` 加 styles 分支 → `data/styles.js` |
| 站点 | `styles/` 落地页 + 顶部第三个开关 |
| WebUI | `index/catalog.py` 加 styles 集合（**注意**：现有「风格」视图是 `facet: 风格参考`，指带 sref 的 job，与本集合同名不同义，需先改名） |

**明确不做的**：不动 jobs 的 manifest / gallery / 分面模型；不复用 `MidRule` / 宽高比逻辑。

路线 B 复用现有取图链路，不新增数据管线 —— 轮廓见 §10.5。

---

## 十、2026-11-03 修正：封面图匿名可采

> 本节推翻 §1 / §6 里的两条判断：「示例图不能本地化」「必须登录才能拿到任何 style 数据」。
> 原因是当时的探测只看了 SPA 的可见 DOM 和 API，**没查 `<head>` 里的 OpenGraph 元数据**。

### 10.1 通路

`/styles/0_<码>` 是纯 shell（5887 字节），但 `<head>` 里有 `og:image`，指向 CDN 上的封面拼图，
且 URL **完全按码模板化**：

```text
https://cdn.midjourney.com/styles/0_<码>/grid_4x2_<宽度>_N.webp
```

尺寸变体实测（Cookie 用 `fetch_hook` 的 `__cf_bm` 通行证，裸请求一律 CF challenge 403）：

| 宽度 | HTTP | 字节 | 结论 |
|---|---|---|---|
| 128 | 200 | 8,454 | 可用 |
| 256 | 404 | — | 不存在 |
| 384 | 200 | 64,838 | 可用 |
| 640 | 200 | 186,108 | 可用（`og:image` 给的就是这一档） |
| 1024 | 200 | 512,084 | 可用，**最大档** |
| 2048 | 404 | — | 不存在 |

单张图路径（`0.webp` / `0_0.webp` / `item_0.webp` / `thumb.webp` / `grid_2x2_*` / `grid_1x1_*`）
**全部 404** —— 只有整张拼图，**拆不出单张**。

### 10.2 图片内容

640 档实测 853×640，4 列 × 2 行 = 8 张同风格示例图。不同码画风截然不同：

| 码 | 画面 |
|---|---|
| `2245733539` | 洋红丝网印刷线稿（人像 / 山景 / 咖啡杯 / 植物） |
| `1441671616` | 冷调动态模糊、电影感（人像 / 风树 / 屋内花束） |

⇒ 确实是「按码定制的风格展示图」，不是随机图。

### 10.3 404 是免费的有效性校验

`/styles/0_<任意数字>` 页面**永远返回 200**：实测 `0_0`、`0_1111111`、`0_999999999999`
都照样返回同样的 `og:image` 模板。**所以页面不能用来判断码是否真实存在。**

能判断的是 CDN 封面图 —— 存在返回 200，不存在返回 404。17 个码实测（取自 11-02 批次图片流）：

| 结果 | 数量 | 占比 |
|---|---|---|
| 200，下载成功 | 14 | 82% |
| 404，未公开为风格 | 3 | 18% |

404 的三个：`2318651792`、`350785888`、`345549`。
⇒ **图片流里的码不一定都在公开风格库里**，命中率约八成。

### 10.4 合规口径（顺带解决一个隐患）

原站 `robots.txt`（2026-05-14 版，带通行证后可读）：

- `User-agent: *` → `Allow: /`
- `Disallow: /api/`、`Disallow: /auth/`、`Disallow: /jobs/`
- **`/styles/` 既没被 Allow 也没有被 Disallow** → 落在默认 `Allow: /` 内

也就是说：「抓 `/styles/` 页面 + CDN 封面图」在 robots 口径上比「抓 `/api/`」更干净。
`sitemap.xml` 里明确写了不枚举 per-style 详情页，所以**没有码清单可白拿**。

### 10.5 若要做：最小轮廓

| 层 | 改动 |
|---|---|
| 采集 | **无新增**。码已经在 `jobs.json` 的 `sref` 字段里 |
| 新增 | `scripts/fetch_styles.py`：读批次 sref → 去重 → CDN 取 640 档 → 404 记 miss |
| 落盘 | `data/styles/<码>.webp` + `data/styles.json`（码 → 宽度 / 字节 / 来源作业） |
| 站点 | 可选：灯箱里点 sref 标签 → 展开该码的封面图 |
| 定时 | 挂在 `scripts/daily_collect.py` 采集之后，**失败不阻断主流程** |

**规模上限（硬约束，先说清）**：匿名图片流固定 4 页 × 50 = 200 条/天，带码约 6.5%
→ **每天约 17 个码，其中约 14 个能出图**。攒到 500 个风格需 ~36 天连续积累，
且上游没有历史回溯接口，断采就永久缺口。

### 10.6 附带结论：WebUI「风格」视图与原站 Styles 的混淆点

| | WebUI「风格」视图 | 原站 Styles |
|---|---|---|
| 定义 | `facet: 风格参考`，筛出**带 sref 码的作业** | **风格本身**作为一个条目 |
| 一条是什么 | 一张成图 + 提示词 + 作者 + 宽高比 | 一个码 + 8 格示例拼图 |
| 有没有提示词 | 有 | **无** |
| 主键 | job UUID | `0_<码>` |
| 数据来源 | `/api/explore`（已有） | `/styles/0_<码>` 的 og:image（§10.1） |

两者同名不同义。**2026-11-03 处理完毕**：WebUI 里的「风格」视图**已删除**
（集合只剩 图像 / 视频，测试防回归），§10.6 这张对照表里的「8 格示例拼图」
也已被 §11.3 推翻（实际是三张语义化单图）。风格实体只由 `styles/` 页面承载（§12）。

---

## 十一、2026-11-03 定案：登录态取码 + 三张语义图（推翻 §10 的两条判断）

§10 的结论建立在「匿名」这个前提上，因此只能拿到 og:image 的 8 格拼图、且码只能从
图片流旁路攒。**补上登录态之后，这两个限制都消失了。**

### 11.1 Top day 的全量就是 200 条

登录后 `GET /api/explore-srefs?page=N&feed=styles_top&_ql=explore` 分页实测：

| page | 返回条数 | 累计 |
|---|---|---|
| 0 | 50 | 50 |
| 1 | 50 | 100 |
| 2 | 50 | 150 |
| 3 | 50 | 200 |
| 4 | **空数组** | 200（到底） |

- **200 条，码去重后仍是 200**（无重复）；
- 全部 `width=896, height=1344`（2:3 竖图）、`type="style"`；
- 条目字段共 18 个，但**信息极薄**：`{"id":"0_3441803824","formatted_sref":"3441803824",
  "width":896,"height":1344,"display_name":"Midjourney","prompt":"","type":"style",...}`
  —— `prompt` 是空串，**没有作者、没有提示词、没有标签、也没有图片地址**。

结论：**「原站 Styles 全集」在 Top day 这个口径上就是 200 条，一次请求 4 页拿完。**
§6「拿不到全量清单」的判定，只在匿名前提下成立。

**但 200 不是固定集合，榜单是滚动的。** 相隔约 45 分钟的两次抓取，各 200 条：

| 指标 | 数值 |
|---|---|
| 重合 | **139 / 200**（约 30% 换血） |
| 仅本次出现 | 61 |
| 仅上次出现 | 61 |
| 重合项位置平均偏移 | **22 位**（最小 −69，最大 +137） |

两种可能都指向同一处理方式：Top day 是「当前热榜」的实时排名（新风格挤进榜、
老风格掉出），或者是每页采用了不稳定排序。无论哪种，**单次抓取都只是时点快照**。

因此 `dump_styles.py` **默认合并累积**而不是覆盖：每跑一次把新码并入
`data/styles.json`，并在 `snapshots` 里记 `{at, count, new}`。这条线因此不需要
「一次抓全」，重复跑就是在攒库。

### 11.2 接口只能在浏览器页面上下文里调用（四组对照实测）

把登录后的 cookie 导出，用 Python 直连同一接口，四种变体**全部 500**：

| 变体 | 请求头 | 结果 |
|---|---|---|
| A | 全量 midjourney cookie + Origin / Sec-Fetch-* / Referer | `500 {"error":"Internal server error"}` |
| B | 只带 `AuthUserTokenV3_i/_r` | 同上 500 |
| C | 去掉 `cf_clearance` / `__cf_bm` / `_cfuvid` | 同上 500（**且没被 CF 拦**，说明是应用层拒绝） |
| D | 去掉 `_ql=explore` | 同上 500 |
| — | **浏览器内 `page.evaluate(fetch)`** | **200，19931 字节** |

原因：`cf_clearance` 与 Chrome 的 TLS/HTTP2 指纹绑定，Python 的 TLS 栈指纹不同，
应用层拿不到可信上下文。**所以 cookie 有价值，但不能脱离真实浏览器使用。**

已验证可行的用法（`scripts/dump_styles.py --state`）：把登录态导出为
Playwright `storage_state`，在**全新启动的真实 Chrome** 里加载该状态，
再在页面上下文执行 `fetch` —— 实测第 0 页正常返回 50 条。
即：**不需要长期占用某个 profile，也不需要接管你正在用的 Chrome。**

### 11.3 每个码是三张语义化单图，不是拼图（推翻 §10.2）

从已登录页面的卡片 DOM 里直接读 `<img>`，真实路径是**按题材命名**的：

```
cdn.midjourney.com/styles/0_<码>/portrait_<尺寸>_N.webp
cdn.midjourney.com/styles/0_<码>/landscape_<尺寸>_N.webp
cdn.midjourney.com/styles/0_<码>/still_life_<尺寸>_N.webp
```

| 项 | 实测结果 |
|---|---|
| 可用尺寸 | **128 / 384 / 640 / 1024**（256、512、2048 全部 404） |
| 单张体积（1024 档） | portrait ≈ 193 KB / landscape ≈ 167 KB / still_life ≈ 119 KB |
| 是否需要登录 | **不需要**，CDN 直连 + `fetch_hook` 通行证即可（与 §10 一致） |
| 内容 | 三张是**同一风格的三个不同题材**：人像 / 风景 / 静物，色调与笔法一致 |
| 另有 `grid_4x2_*` | 存在（1024 档 ≈ 297 KB），是四宫格拼图；**卡片实际用的是上面三张独立图** |

**§10.2「只有整张拼图、拆不出单张」是错的**，错因很具体：当时是我按
`0.webp` / `0_0.webp` / `item_0.webp` / `thumb.webp` **猜路径**，全部 404 就下了结论，
没有去读 DOM 里的 `<img src>`。真实文件名是语义化的，猜不出来。

### 11.4 已落地的东西

| 文件 | 作用 |
|---|---|
| `scripts/dump_styles.py` | 取码。`--cdp` 接管已开 Chrome / `--state` 用会话文件起全新 Chrome / `--profile --login` 等人工登录 |
| `scripts/capture_session.py` | **取会话**。等人工登录 → 导出 `storage_state` → 自动跑一次接口自检。会话过期后重跑这一个就行 |
| `scripts/fetch_styles.py` | 下图 + 生成 384 缩略。`--size` / `--codes` / `--limit` / `--force`，幂等跳过已存在文件；缩略由大图本地缩放（比源旧才重建） |
| `scripts/build_styles_page.py` | 生成 `styles/index.html`。缺任何一档图即非零退出并列出缺哪个，不产出半成品页 |
| `data/styles.json` | 清单（feed / captured_at / 累计 code / `added_at` / snapshots 快照账本）—— **入库** |
| `data/styles_images.json` | 每个码每类图的命中状态 —— **入库** |
| `styles/index.html` | 风格码库页面（单文件 29 KB，码表内嵌）—— **入库**（`.gitignore` 单独放行） |
| `styles/<码>/{portrait,landscape,still_life}.webp` | 1024 档图片本体，灯箱用，**不入库** |
| `styles/<码>/s/<kind>.webp` | 384 缩略，网格用，**不入库** |

会话文件位置（**必须在仓库外**）：

```text
%USERPROFILE%\.workbuddy\secrets\midjourney-session.json
```

不要放 `.scratch/`：那是 gitignore 的临时区，清理临时文件时会连会话一起删掉（2026-11-03 已实际发生一次，因为排查时看错目录层级又误判成「已丢失」）。

用法：

```bash
cd sites/midjourney-explore
python scripts/dump_styles.py --state "%USERPROFILE%\.workbuddy\secrets\midjourney-session.json"   # 取码
python scripts/fetch_styles.py --size 1024                                                        # 下图 + 384 缩略
python scripts/build_styles_page.py                                                               # 重建页面
```

会话过期时（接口返回 401 / 500）：

```bash
# 1) 起一个独立 profile 的 Chrome（不要用默认目录，见 11.5 第 1 条）
chrome.exe --user-data-dir="%USERPROFILE%\.workbuddy\mj-profile" --remote-debugging-port=9333 \
           "https://www.midjourney.com/auth/signin"
# 2) 人工登录后跑
python scripts/capture_session.py --cdp http://127.0.0.1:9333
```

**实跑结果（2026-11-03，`styles_top`，1024 档，三次快照合并）**：

| 项 | 数值 |
|---|---|
| 码 | **329**（首跑 200 + 41 分钟后 +61 + 1 小时后 +68；`data/styles.json` 与磁盘目录完全一致） |
| 图片 | **987 张**（portrait / landscape / still_life 各 329） |
| 失败 | **0 个 404、0 个错误**（三次合计 987 次请求全部命中） |
| 体积 | 235 MB（单张 14–690 KB；三类平均 251 / 276 / 240 KB） |
| 缩略 | 987 张 384 档，**17.5 MB**（平均 18 KB），本地缩放 0 失败 |
| 页面 | `styles/index.html` 29 KB；首屏实测只拉 **9 张 / 125 KB** |
| 耗时 | 首跑 600 张 10 分 45 秒；补 183 张 3 分 50 秒；补 204 张 3 分 45 秒（`--sleep 0.25~0.3`） |

三次快照的重合度：第 1↔2 次重合 139/200（30% 换血），第 2↔3 次重合 132/200（34% 换血）。
攒库速率稳定在**每轮 60~70 个新码**，想扩到四位数码量需要 10 轮以上。

### 11.5 仍未解决的边界

1. **登录态会过期，且取会话必须人工登录一次**。会话文件在
   `%USERPROFILE%\.workbuddy\secrets\midjourney-session.json`，实测有效期：

   | cookie | 到期 | 说明 |
   |---|---|---|
   | `__Host-Midjourney.AuthUserTokenV3_r` / `_i` | 约 30 天 | 真正的登录凭据 |
   | `cf_clearance` | 约 1 年 | 与 Chrome 的 TLS 指纹绑定 |
   | `__cf_bm` / `_dd_s` | 小时级 | 短期 cookie，浏览器会自动续 |

   过期后必须人工重登（`capture_session.py`），因此**不能挂进每日定时任务**，
   只能按周/月手动刷新。**取会话时绝不要用默认 `user-data-dir` 开调试端口**：
   Chrome 156 禁止这样做，用 junction 映射默认目录会让 ABE v20 cookie 解不开并被
   Chrome 删除，登录态不可恢复（2026-11-02 已实际发生）。一律用独立的空 profile。
2. **只测了 `styles_top`**。`styles_random / styles_hot / styles_top_week /
   styles_top_month` 三个 feed 未实测数据量与重叠度。
3. **数据本身很薄**。一个风格只有「码 + 三张图」，没有提示词、没有作者。
   做「风格速查」够用，做「风格详情页」撑不起来。
4. **WebUI 不再镜像 Styles**（2026-11-03 定案）。此前 `index/catalog.py` 用
   `facet="风格参考"` 近似出来的「风格」视图（筛的是「挂了 sref 的作业」）与原站这个
   tab 同名不同义，已删除；集合只剩「图像 / 视频」两个视图，并有测试守着不让它回来。
   `facets` 里的「风格参考」标签已于 2026-11-03 **撤掉**——一码一条，是标识而不是
   分类，做左栏分面噪声大于信息；「挂了 sref」这个事实改由派生分面「类别 / 有 sref 码」
   承载（见 DATA_STRATEGY_SPEC.md 6.1）。风格实体只由本目录的 `styles/` 页面承载。

---

## 十二、风格码库页面（2026-11-03 落地）

`styles/index.html` 是这批数据唯一的展示面，由 `scripts/build_styles_page.py` 生成。
它不是 `tools/build.py` 的产物——`build.py` 只跑各站的 `build_gallery.py`，
所以**改完码表要单独重跑第 3 步**，否则页面停在上一轮（测试会盯着这一点：
`tests/run.py` 里 `test_styles_page_matches_code_list` 比对页面内嵌码表与
`data/styles.json`）。

### 12.1 页面形态

| 决策 | 选择 | 理由 |
|---|---|---|
| 落点 | 站点内独立静态页 `styles/`，不进导航、不进 sitemap | 走 `shared/landing.py` 那套落地页要动 `landing.json`、sitemap 与三层闸门，代价远超收益 |
| 一卡几图 | 一码一卡，卡内三态切换 | 三张图是同一套视觉语言的三个场景，拆成三卡会被误读成三个风格 |
| 图片档位 | 网格 384 / 灯箱 1024 | 首屏实测 9 张 125 KB；不点灯箱永不拉 1024 |
| 缩略来源 | 1024 本地缩放，不额外下 CDN 的 384 | 原站 384 大概率同源编码，本地 Lanczos 肉眼无差；省一次 987 次网络流程 |
| 排序 | `added_at` 倒序（新码在前） | 榜单顺序每轮都在变，只有首次收录时间稳定；「只看最近新增」也靠它 |
| 缺图 | 硬失败，列出缺哪个码哪一档 | 静默降级会发布出一个慢一倍还看不出问题的页面 |
| 复制 | 主按钮 `--sref <码>` | 唯一「拿来就能贴进 prompt」的形态；码本身另作纯文本展示 |

`added_at` 是合并累积时补的字段：首次收录写入当次快照时间，之后每轮沿用旧值。
历史 329 条由三次快照的 `new`（200 / 61 / 68）按 items 插入顺序反推补齐。

### 12.2 发布链路

`styles/` 不在 `tools/release.py` 的 `SITE_DIRS`（那里只有 `data`），而是加进
`sites.json` 的 `imageDirs`，走 `copy_tree_links` 的硬链接复制。代价：加了
`imageDirs` 会改变 hub 入口页的体量统计，`hub/index.html` 必须跟着重建
（`tests/run.py` 的构建产物一致性测试会拦住这件事）。

已知边界：`release.py --no-images` 不会带 `styles/`，此时页面图片全 404——
与「不发布图片」的本意一致，不额外处理。

---

## 附录：探测脚本与命令

| 文件 | 作用 |
|---|---|
| `.scratch/probe_styles.py` | 探 `/api/explore` 的 feed 取值（已证无效，留作对照） |
| `.scratch/probe_bundle.py` | 抓 explore 页 → 列 script / api 路径 |
| `.scratch/probe_js.py` | 递归抓 `/public/out/` 模块 → 汇总全部 `/api/` 路径 |
| `.scratch/probe_srefs.py` ~ `probe_srefs4.py` | `/api/explore-srefs` 四轮递进验证（含匿名旁路排查） |
| `.scratch/netcheck.py` | 三个出口到 midjourney 的连通性对照 |
| `.scratch/probe_style_head.py` | 抓 `/styles/0_<码>` 的 `<head>` → 发现 `og:image`（§10 的起点） |
| `.scratch/probe_ogimg.py` / `probe_ogimg2.py` | 验证 og:image 按码模板化 + 不存在的码也返回 200 |
| `.scratch/probe_style_img.py` | 用 `fetch_hook` 通行证下载封面图（首次打通） |
| `.scratch/probe_style_batch.py` | 17 个码批量测命中率 → 14 命中 / 3 个 404 |
| `.scratch/probe_style_variants.py` | 尺寸变体（128/384/640/1024）+ 单张路径（全 404） |
| `.scratch/pw_open.py` / `pw_loginbox.py` | Playwright 接管登录态 Chrome，读页面状态与登录入口 |
| `.scratch/pw_watch.py` | 等人工登录 → 导出 `storage_state` → 探接口结构（§11 起点） |
| `.scratch/pw_dump.py` | 翻页抓完 `feed=styles_top` → 200 条（§11.1） |
| `.scratch/pw_img.py` | 从卡片 DOM 读 `<img src>` → 发现三张语义图（§11.3） |
| `.scratch/pw_res.py` | 页面内 fetch 探尺寸（跨域失败，转服务端） |
| `.scratch/probe_style_kinds.py` | 服务端探 portrait/landscape/still_life 的可用尺寸档 |
| `.scratch/test_session2.py` | cookie 直连的四组变体对照（全 500，§11.2） |
| `.scratch/probe_sitemap.py` / `probe_sitemap2.py` / `probe_robots.py` | sitemap 是否枚举 styles、robots.txt 全文 |

全部在 `.scratch/`（已被 gitignore），**未进仓库**。

复现命令（代理端口取系统代理，不要用环境变量里的）：

```bash
cd E:/002-Pr/ai-video-imge-prompts
powershell -c "(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings').ProxyServer"
FETCH_PROXY=http://127.0.0.1:<上面的端口> python -u .scratch/probe_srefs4.py

# §10 的两步复现：先探通路，再批量测命中率
FETCH_PROXY=http://127.0.0.1:<端口> python -u .scratch/probe_style_variants.py
FETCH_PROXY=http://127.0.0.1:<端口> python -u .scratch/probe_style_batch.py
```

> **一个通用坑**：`cdn.midjourney.com` 与 `www.midjourney.com` 都挂 Cloudflare，
> 裸 `urllib` 请求一律 403 challenge。必须复用 `scripts/fetch_hook.py` 的
> `prepare()` 预热拿 `__cf_bm`，否则会把「缺通行证」误判成「资源不存在」——
> 这也是 §10 之前把「示例图拿不到」写错的原因。

> 首版 `probe_styles.py` 自己拼 header，四个 feed 全 SSL EOF；改用 `extract.py` 的
> `API_HEADERS`（含 `Sec-Fetch-*` / `Upgrade-Insecure-Requests`）后错误类型不变 ——
> 证明当时的 EOF 是网络层而非 header 层。这个对照排除了「header 缺失」的误判。
