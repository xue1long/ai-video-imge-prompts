# NOTICE — Midjourney 探索榜（MJ-EXPLORE-01）

## 来源

- 素材集：Midjourney 官网 Explore 榜（<https://www.midjourney.com/explore?tab=styles_top>）
- 采集方式：通过站点前端的公开只读接口 `GET /api/explore?page=N&feed=top` 分页抓取，
  只取元数据与图片地址；提示词原文与成图均未做改动、未做翻译。
- 收录范围：公开榜单全部 4 页，**每批次** 200 条社区作业、800 张成图（每条作业 4 格）。
  本站按天累积采集，当前共 2 个批次（2026-11-01、2026-11-02），计 **400 条作业 / 1600 张成图**。
- 采集日期：2026-11-01、2026-11-02（批次目录 `data/daily/<YYYY-MM-DD>/`，历史批次不覆盖）
- 模型版本：当前批次全部为 Midjourney v8.2。

## 收录范围：只含 Images 内容类型，不含 Styles

Explore 页是**两个维度的组合**，不是一个扁平的 tab 列表：

- **排序**（左侧 / 顶部）：For You / Random / Hot / Top day|week|month / Likes
- **内容类型**（右上角）：Images / Videos / **Styles**

本站采集的是 **`feed=top`（Top day 排序）+ Images 内容类型**这一格。

**Styles 没有采集。** 它是 Style Explorer：展示 Style Reference code（风格码，如
`2918660786`）以及每个码对应的一组示例图，可按 Random / Popular 排序、按词模糊搜索。
官方文档《Website Overview》：「Open the Explore page and click the Styles tab in the
top-right corner」。它的数据结构是「风格码 + 示例图组」，与本站现用的「作业 + 4 格成图」
完全不同，不能塞进同一个 jobs 流程。

> ⚠️ **2026-11-02 更正**：本节此前写「官网并没有一个独立于热门榜的风格榜数据源；
> `styles_top` 展示的就是 Explore 的热门作品流」。该结论**不成立**，已作废。
> 当初的实测是把 URL 里的 `?tab=` 换成 `styles_*` 看 HTML 字节是否相同 —— 但 `?tab=`
> 是前端路由参数，单页应用返回同一份 shell 属正常行为，推不出「没有独立数据源」；
> 而 Styles 并非 URL tab，而是页面右上角的内容类型开关。复测确认 `?tab=styles_top`
> 现在返回普通图片网格（顶部只有 Top day / Images / Videos）。
>
> **Styles 的接口端点与参数尚未实测**（需要可用出口 IP + CF 通行证）。确认后按独立
> 数据线采集。

## 授权

**本站素材禁止再分发。** 依据 Midjourney 服务条款
（<https://docs.midjourney.com/hc/en-us/articles/32083055291277-Terms-of-Service>）：

> You own the assets you create with Midjourney ... You grant Midjourney and its
> affiliates the right to host, display, distribute and otherwise use your Assets.

即：素材由社区用户生成，版权归各创作者所有；用户授予 Midjourney 平台托管、展示与
分发许可，**但上游未授予第三方（本站）任何再分发权**。因此：

- 本站为**个人学习用途**的中文索引镜像，不对外分发图片文件本身；
- 引用提示词或成图请**回链原站**；
- 图片著作权归各创作者，按各创作者在 Midjourney 上的声明使用；
- 本仓库代码为 MIT，与本站素材许可互相独立。

## 数据来源的可达性

- 元数据：`https://www.midjourney.com/api/explore?page=N&feed=top&_ql=explore`
  （站点前端在用，匿名可调，必带 `X-CSRF-Protection: 1` 头）
- 图片：`https://cdn.midjourney.com/<job_id>/<index>_{size}_N.webp` 与
  `https://cdn.midjourney.com/<job_id>/<index>.png`

### 本地留存的档位

本站只把**缩略图（640）与中图（1024）**下载到本地（`thumbs/`、`mid/`），
**原图（`.png`）不落本地** —— 页面与素材管理器都直接引用 CDN 直链。
原图每天约 2.3 GB，本地副本不产生展示价值；代价是**原图长期可达性取决于上游**
（详见 `docs/DATA_STRATEGY_SPEC.md` §1.2）。

### Cloudflare 的两道坎（实测）

1. **接口与图片都要浏览器化的请求头。** 只带 `User-Agent` / `Referer` 一律 403；
   需要完整的 `Accept` / `Sec-Fetch-*` / `Origin` 组合。
2. **图片必须带 Cloudflare 通行证 cookie。** 访问 `www.midjourney.com` 任一页面会下发
   `__cf_bm`，把它放进 CookieJar 再访问 `cdn.midjourney.com` 才会返回图片；
   路径完全正确但没有 cookie 时同样是 403（返回的是 Cloudflare 的 HTML 错误页，不是图片）。

这两点由 `scripts/fetch_hook.py` 封装，供仓库通用的 `tools/fetch.py` 调用
（`shared/assets.py` 的站点级钩子机制）。

## 上游数据特征

| 现象 | 处理 |
|---|---|
| 公开榜单在 `page=4` 起返回空数组 | 采集 4 页，共 200 条作业 |
| 每条作业固定 4 格，但其中 3 格被上游标记 `server_filtered` | 官网首页只展示 1 格；实测被标记的格子在 CDN 上同样能取到完整图片，故全部收录 |
| 上游 `prompt.ar` 是 `{"w":9,"h":16}` 这样的字典，部分条目为 `null` | 统一归一到最简比例（如 `9:16`）；`ar` 缺失时由 `width/height` 推算 |
| Styles（风格码）是独立内容类型，不在 `feed=top` 的返回里 | **当前未采集**，见上文「收录范围」（待实测接口后按独立数据线接入） |
