# NOTICE — PromptHero Midjourney 提示词集（PROMPTHERO-MJ-01）

## 来源

- 素材集：PromptHero「Midjourney Prompts」（<https://prompthero.com/midjourney-prompts>）
- 采集方式：通过站点前端的公开接口 `prompt.search` 分页抓取，只取元数据与图片地址；
  提示词原文与成图均未做改动、未做翻译。
- 收录范围：Midjourney 模型下的全部 12,998 条，其中成人内容 2,841 条。
- 采集日期：2026-11-01

## 授权

**本站素材禁止再分发。** 依据上游服务条款（<https://prompthero.com/faq>）：

> If you contribute any content or data to the site, including but not limited to uploading
> prompts, metadata, posts on the site and messages on the chat, your profile information,
> profile photos, meetup photos or other photos, you provide us with a perpetual license to
> broadcast, display, distribute, sell and produce derivatives from your contributions
> including on other platforms (including but not limited to Slack, Discord, Twitter,
> Instagram, TikTok, Facebook and YouTube) in the future.

> Copyright in PromptHero's websites, apps, communities and its properties rests with
> PromptHero unless otherwise stated.

即：素材由用户上传，版权归各原作者；用户授予 PromptHero 平台永久的分发与再分发许可，
**但上游未授予第三方（本站）任何再分发权**。因此：

- 本站为**个人学习用途**的中文索引镜像，不对外分发图片文件本身；
- 引用提示词或成图请**回链原站**（上游条款亦要求使用其数据时回链）；
- 图片著作权归各原作者，按各原作者在 PromptHero 上的声明使用；
- 本仓库代码为 MIT，与本站素材许可互相独立。

## 成人内容

- 带「成人内容」标记的条目（`isNsfw`，共 2,841 条）在画廊中**默认模糊**，
  点开单张或用页头开关才显示清晰图；这些条目**不生成静态落地页，也不出现在 sitemap 里**，
  不会被搜索引擎直接收录。
- 上游已对涉未成年内容做过过滤：本次收录的条目中 `possibleMinorNsfw` 标记为真的有 0 条
  （成人集合），另有 24 条标在非成人集合里，但内容经抽查为误标（`isNsfw` 为假、
  内容为普通人物），按上游判定收录。

## 上游数据缺陷与本站的处理

| 缺陷 | 处理 |
|---|---|
| 分页在并列排序值处漂移，同一条会被翻页重复返回（实测 322 页返回 15,456 条，去重后 10,339 条） | 采集时按 slug 去重；重复项数据完全一致（同 id、同计数），去重无损 |
| 26 条条目上游未生成任何衍生图（640/1080 都没有） | 缩略图档回落到原图 URL，manifest 里标 `thumbFallback: 1` |
| 650 条条目上游只生成了 640 与 square，没有 1080 档 | 中图档回落到 640，manifest 里标 `midFallback: 1` |

## 数据来源的可达性

- 提示词与元数据：`https://prompthero.com/api/trpc/prompt.search`（站点前端在用，未要求登录）
- 衍生图：`https://img.prompthero.com/<key>/{640,1080,square}.webp`
- 原图：`https://cdn.prompthero.com/<key>`
- `robots.txt` 对通用爬虫为 `Allow: /`；训练型爬虫（GPTBot、ClaudeBot、Google-Extended 等）
  被 Disallow，用户触发型检索（OAI-SearchBot、Claude-User 等）被 Allow。
