# NOTICE — 提示词生图集（PROMPTS-DB-01）

## 来源

- 素材集：YouMind「GPT Image 2 Prompts」（youmind.com/gpt-image-2-prompts/explore）
- 上游开源镜像：github.com/YouMind-OpenLab/awesome-gpt-image-2（CC BY 4.0）
- 数据经 YouMind 官方 API 获取，仅做格式转换与中文化展示，未改动提示词内容。

## 许可

- 本站图片与提示词文本：**CC BY 4.0**（可共享、可改编、可商用，**须署名**）。
- 本仓库代码为 MIT，与本站素材许可互相独立。

## 例外：站主自制图

灯箱缩略图条上带**虚线框**、标签行标「**自制**」的图**不属于 CC BY 4.0 素材**：

- 它们是站主自己用同一条提示词跑出的结果，经素材管理器「添加图片」挂到对应提示词下；
- 版权归本站，**不在 CC BY 4.0 授权范围内**，再分发时请单独联系，不要当作上游素材一并转载；
- 数据上由 `data/user_assets.json` 记录，图片在 `userimg/`（与上游的 `img/` 物理分开），
  构建时追加到该提示词的成图列表末尾，永远不覆盖、不打乱上游图；
- 数量与归属可随时核对：`python sync_user_assets.py --dry-run` 只打印不落盘。

## 署名方式

- 每条记录的原始作者、来源推文链接、发布时间已逐条保留，
  站点灯箱内展示作者并附「查看来源」链接，复制提示词时一并附带出处字段。
- 再分发本站素材时，请保留上述署名信息，并注明：
  「来源 YouMind GPT Image 2 Prompts（CC BY 4.0）」。

## 与其他站点的关系

本站与其他七站（人像 / 服装 / 姿势 / 深度姿势 / CC0 姿势线稿 / Midjourney 探索榜 /
Midjourney 提示词集）来源不同、授权不同，
再分发时请逐站核对 `sites.json` 的 `license` 字段与各站 NOTICE.md。
