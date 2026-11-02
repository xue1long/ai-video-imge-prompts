# Styles 数据线可行性结论

> 状态：**已定案 —— 不可自动化，建议不做**
> 日期：2026-11-02（首版 22:30，定案 23:40）
> 方法：前端 bundle 反查 + 生产采集链路实测（登录态 Chrome 对照）
> 结论前置：**Styles 只在登录态下存在。匿名无论 tab 传什么，前端与后端都会回退成图片流。
> 因此每日定时采集（匿名 + CF 通行证）拿不到 Styles 数据。除非接受 cookie 方案，否则不做。**

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
| 示例图能否本地化 | **不能**（CDN 403，与现有 thumb/mid 同一困境） | 前轮实测 |
| 现在能否动手 | **不建议** | 硬门槛已验证为「不可过」 |

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
| 每项图片数 | 4 格（`_0` ~ `_3`） | 3 张示例图 |
| 有提示词 | 有（`decodedPrompt`） | **无** |
| 有作者 | 有 | **无**（DOM 层不可见） |
| 有宽高比 | 有（`prompt.ar`） | **无**（3 图横向排列，非网格） |
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
| **可自动采集（匿名）** | ❌ **不可 —— 需登录态，已验证无旁路** |
| 图片可本地化 | ❌ 不可（CDN 403，与现有困境相同） |
| 站点可展示 | ✅ 可（若数据到手，走 CDN 直链，与 full 档同策略） |
| 信息量 | 🟡 低（只有码 + 图，无提示词/无作者/无标签） |

### 建议：不做

理由按权重排序：

1. **过不了自动化门槛**。唯一的自动化路径是维护登录 cookie，而它必然过期
   （Firebase ID token 小时级、refresh token 也有限期），意味着定时任务会周期性地
   静默失效 —— 比不做更糟，因为失败是无声的。
2. **信息量低**。一个 style 的可采信息只有码和示例图，没有提示词、没有作者、
   没有标签，站内可做的筛选维度几乎为零。
3. **示例图拿不到**。CDN 403 是既有困境，Styles 只是同一个坑。
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

## 九、如果将来仍要做：前置条件

必须先拿到一个**能自动续期的登录态**，否则免谈。可能的路线（按可行性排序）：

1. **放弃定时，改手动导出**：用户登录后，用浏览器扩展在页面里执行一次导出，
   把结果落成本地 JSON。频率低（月级），不做定时任务。
2. **cookie 注入 + 失效告警**：把 `__session` / Firebase token 存本地，
   定时任务用它们请求；一旦 401/500 就发告警提醒续期。**能跑但会周期性静默失败**，
   需配套告警，复杂度高于收益。
3. **不做**（当前建议）。

真要实施时，最小方案轮廓（**暂不执行**）：

| 层 | 新增内容 |
|---|---|
| 采集 | `scripts/extract_styles.py` → `data/daily/<日期>/styles.json`（独立于 jobs） |
| 索引 | `styles_manifest.json`（code 为键，示例图 URL 列表） |
| 构建 | `build_gallery.py` 加 styles 分支 → `data/styles.js` |
| 站点 | `styles/` 落地页 + 顶部第三个开关 |
| WebUI | `index/catalog.py` 加 styles 集合（**注意**：现有「风格」视图是 `facet: 风格参考`，指带 sref 的 job，与本集合同名不同义，需先改名） |

**明确不做的**：不动 jobs 的 manifest / gallery / 分面模型；不复用 `MidRule` / 宽高比逻辑。

---

## 十、附：探测脚本与命令

| 文件 | 作用 |
|---|---|
| `.scratch/probe_styles.py` | 探 `/api/explore` 的 feed 取值（已证无效，留作对照） |
| `.scratch/probe_bundle.py` | 抓 explore 页 → 列 script / api 路径 |
| `.scratch/probe_js.py` | 递归抓 `/public/out/` 模块 → 汇总全部 `/api/` 路径 |
| `.scratch/probe_srefs.py` ~ `probe_srefs4.py` | `/api/explore-srefs` 四轮递进验证（含匿名旁路排查） |
| `.scratch/netcheck.py` | 三个出口到 midjourney 的连通性对照 |

全部在 `.scratch/`（已被 gitignore），**未进仓库**。

复现命令（代理端口取系统代理，不要用环境变量里的）：

```bash
cd E:/002-Pr/ai-video-imge-prompts
powershell -c "(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings').ProxyServer"
FETCH_PROXY=http://127.0.0.1:<上面的端口> python -u .scratch/probe_srefs4.py
```

> 首版 `probe_styles.py` 自己拼 header，四个 feed 全 SSL EOF；改用 `extract.py` 的
> `API_HEADERS`（含 `Sec-Fetch-*` / `Upgrade-Insecure-Requests`）后错误类型不变 ——
> 证明当时的 EOF 是网络层而非 header 层。这个对照排除了「header 缺失」的误判。
