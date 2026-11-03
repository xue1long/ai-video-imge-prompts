# NOTICE — Midjourney 风格码库（MJ-STYLES-01）

## 来源

- 素材集：Midjourney 官网 Explore 页的 **Styles 内容类型**
  （<https://www.midjourney.com/explore?tab=styles_top>）
- 采集方式：在**已登录**的浏览器页面上下文里调用站点前端的公开只读接口
  `GET /api/explore-srefs?page=N&feed=styles_top`，分 4 页取完，
  只取元数据（风格码、尺寸、收录时间）；示例图地址由 CDN 直接取。
- 收录范围：Styles 榜单（`feed=styles_top`）**全部 200 个码 / 每次快照**，
  按批次累积，当前共 **329 个风格码 / 987 张示例图**（每码三张：人像 / 风景 / 静物）。
- 采集日期：2026-11-03，共 3 个快照批次
  （00:50 首批 200 码 / 01:10 新增 61 / 02:31 新增 68），清单见 `data/styles.json` 的 `snapshots`。
- 榜是**滚动榜**：相隔 45 分钟两次快照仅重合 139 条，因此脚本默认**合并累积**而非覆盖。

## 与 midjourney-explore 站的关系

两个站是**两种不同的内容类型**，不是同一份数据的两种视图：

| | midjourney-explore（MJ-EXPLORE-01） | mj-styles（本站） |
|---|---|---|
| 采集源 | `/api/explore?feed=top`（Images 类型） | `/api/explore-srefs?feed=styles_top`（Styles 类型） |
| 一条内容 = | 一条社区作业 | 一个风格码 |
| 附带信息 | 4 格成图 + 提示词 + 作者 + 宽高比 | 三张语义示例图，**无提示词、无作者、无标签** |
| 码表规模 | 600 条作业 | 329 个风格码 |

**两边的码表完全不相交**（实测 329 vs 45，交集 0）：作业里引用的 `prompt.styleRef`
与 Styles 榜单的码是两套东西。因此拆成两个独立站点，而不是同一站的两个视图。

## 认证与登录态

- 取码接口**必须登录态**，匿名请求返回 401 / 500，**无旁路**。
- 接口**只能在页面上下文里调**：把 cookie 导出后用 Python 直连，四组请求变体全部 500
  （含去掉 `cf_clearance` 的对照，证明是应用层拒绝，不是 Cloudflare 拦截）。
  取码脚本用 Playwright 在页面内 `fetch`。
- 示例图在 CDN 上**匿名可下**，但要先过 Cloudflare 的 `__cf_bm` 通行证
  （`fetch_hook.prepare()` 预热 + 浏览器化请求头），裸 urllib 直连必定 403。
- 会话文件存在**仓库外**：`C:\Users\HP\.workbuddy\secrets\midjourney-session.json`。
  过期后跑 `scripts/capture_session.py`（起独立空 profile 的 Chrome 人工登录一次）。

## 授权

风格码与示例图由 Midjourney 社区创作者创作并公开在 Styles 榜单上，
**著作权归各原作者**。Midjourney 服务条款未授予第三方再分发权，
因此本站为个人学习用途的索引镜像，**禁止再分发图片文件本身**，引用请回链原站。

## 探测批（不入库）

2026-11-03 另做了一次探测：把 midjourney-explore 站作业里引用的 45 个 `sref` 码
逐个探测 CDN，**35 个有风格图、10 个 404**。这 35 个码**不属于 Styles 榜单**，
未并入码表，图片放在 `.probe/`（不入库），清单见 `data/styles_probe.json`。

不并入的理由：榜单成员才有 `added_at`（排序与「只看最近新增」依赖它），
且探测批只有 384 档，与码表的 1024 档不同。

## 文件

| 路径 | 内容 |
|---|---|
| `data/styles.json` | 码表 + 快照历史 + `added_at`（**入库**） |
| `data/styles_images.json` | 每个码每档图的下载状态（**入库**） |
| `data/styles_probe.json` | 探测批留档（**入库**） |
| `manifest.json` | 987 行（329 码 × 3 张），给 WebUI 索引用（**入库**） |
| `styles/<码>/*.webp` | 1024 档示例图（**不入库**） |
| `styles/<码>/s/*.webp` | 384 缩略（**不入库**） |
| `.probe/<码>/` | 探测批的 35 个码（**不入库**） |
