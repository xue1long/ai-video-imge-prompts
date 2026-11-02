# NOTICE — Midjourney 探索榜（MJ-EXPLORE-01）

## 来源

- 素材集：Midjourney 官网 Explore 榜（<https://www.midjourney.com/explore?tab=styles_top>）
- 采集方式：通过站点前端的公开只读接口 `GET /api/explore?page=N&feed=top` 分页抓取，
  只取元数据与图片地址；提示词原文与成图均未做改动、未做翻译。
- 收录范围：公开榜单全部 4 页，**每批次** 200 条社区作业、800 张成图（每条作业 4 格）。
  本站按天累积采集，当前共 2 个批次（2026-11-01、2026-11-02），计 **400 条作业 / 1600 张成图**。
- 采集日期：2026-11-01、2026-11-02（批次目录 `data/daily/<YYYY-MM-DD>/`，历史批次不覆盖）
- 模型版本：当前批次全部为 Midjourney v8.2。

## 关于 `tab=styles_top`

站点的 tab 标签（`styles_top` / `styles_hot` / `styles_random` / `top` / `hot` …）在前端
**全部调用同一个接口** `/api/explore?page=N&feed=top`——`feed` 永远是 `top`，
tab 只是界面上的叫法。实测把 tab 换成任何 `styles_*` 值，返回内容的 MD5 完全相同。

也就是说，官网并没有一个独立于「热门榜」的「风格榜」数据源；`styles_top` 展示的就是
Explore 的热门作品流。本站据此只取 `feed=top` 这一份榜单，不做多 tab 区分。

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
| `feed` 参数对 `styles_*` 无效 | 只取 `feed=top`（见上文「关于 tab=styles_top」） |
