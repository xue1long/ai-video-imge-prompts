# 删除 mj-styles 站

`mj-styles`（Midjourney 风格码库，MJ-STYLES-01）于 2026-11-03 拆站成立，2026-11-04 整站删除。删除动因是**价值不足**——该站的内容撑不起一个独立站点。清单条目、站目录、索引映射、测试夹具、hub 产物、数据库状态全部清理，仓库从 9 站变为 8 站，对外图片文件数从 115,931 降为 113,957。

## 为什么删

四条理由，按重要性排序：

| 理由 | 依据 |
| --- | --- |
| **内容信息量低**：一个风格码 + 三张语义示例图，没有提示词、没有作者、没有标签，用户能做的事就是抄一串 `--sref` 参数 | 站点浮层实测（`sites/midjourney-explore/docs/STYLES_FEASIBILITY.md` §11） |
| **与相邻站的用户价值重叠度高**：都是 Midjourney 提示词参考，拆成两个站对用户没有增量 | 站群整体定位 |
| **登录态是硬门槛且会过期**：码清单端点 `/api/explore-srefs` 匿名一律 500，把 cookie 拿出来走 Python 直连也稳定 500，只能在浏览器页面上下文里取。定期刷新需要人工重登 | §11.2 的四组请求变体对照 |
| **与探索榜不连通**：329 个 Styles 码与探索榜的 45 个 sref 码**交集为 0**，两套码不是一回事 | 2026-11-03 实测比对 |

**删除动因不是技术脆弱，也不是授权或运维问题。** 这决定了将来若要恢复，不需要默认先解决登录态问题——那是恢复这条线的成本，不是删除它的理由。

## 考虑过的替代方案

| 方案 | 否决理由 |
| --- | --- |
| **保留站点，只停更** | 站点是静态构建产物，长期不更新的内容页会持续消耗维护注意力，且 404 的死链比没有这个站更糟 |
| **合并回 midjourney-explore 作为该站的一个 tab** | 两边码表交集为 0，合并只是把两种不同内容类型塞进同一个数据流；此前用分面近似出「风格」视图的做法已经证明是错的（筛的其实是「挂了 sref 的作业」，与原站那个 tab 同名不同义），该视图已删除 |
| **只删页面、留站点配置** | 留下一个空站会让 `sites.json` 与实际产物不自洽，hub 统计与 sitemap 都要为它开特例 |
| **给线上 `/mj-styles/` 加 301 跳转到 hub** | 实测该路径**本来就是 404**——这个站从未真正上线，没有 SEO 权重需要迁移。加跳转规则只会给 nginx 增加一条永不触发的维护负担 |

## 后果

- **`landing: false` 机制保留。** 该站是它的唯一用例。删站后机制零使用者，但字段、`shared/landing.py` 的空分面语义、hub 分支、`tests/run.py` 的双向校验全部保留，给将来的新站用。见 `0001-mj-styles-no-landing-pages.md`（该记录作为历史保留，不因用例消失而删除）。
- **`0004-missing-images-do-not-fail-build.md` 同样保留。** 那条决策的触发源虽然是这个站，但「缺图不阻断构建」是通用原则，与这个站无关。
- **线上无需任何动作。** `https://photoai.life/mj-styles/` 一直是 404；`deploy/nginx.conf` 不加跳转规则。
- **索引必须重建，不能只跑校验。** `index/store.py` 的 `reset()` 会删掉 `collection <> 'own'` 的 item，但**不删 `collection` 表里的行**；`upsert_collection()` 也只 upsert、不清理已消失的 slug。因此删站后必须执行 `python index/sync.py --force` 重建，否则 `collection` 表会留下一个空残留集合。而 `index/check_wiring.py` 的反向检查只查 `item` 表的 distinct collection，**抓不到这个残留**——它必须由重建来消除，不能靠校验发现。
- **`tests/test_manager.py` 的 AutoSync 夹具改用 `midjourney-explore`。** 它同样是 `group_by` 分组站，且 `full` 是 `online` 档，顺带覆盖了「online 档 manifest 不写 `full_path`」这条约定——覆盖面比原来只多不少。
- **`kind` 从 hash 参数白名单移除。** 那是这个站独有的「示例图构图」维度参数，其唯一使用者已消失。
- **CONTEXT.md 删掉「风格码」「示例图」两个词条。** 术语表只定义「是什么」且不写实现历史（该文件此前零日期注记），这两个词描述的是 Midjourney 上游概念、本仓库已不再镜像。历史留在本文与 `sites/midjourney-explore/docs/STYLES_FEASIBILITY.md` §14。

## 若将来要恢复这个站

1. 从 git 历史取回：`c1b36de`（拆站提交）、`786a66e`（更早的提交）。
2. 需要重新准备**登录态**：`/api/explore-srefs` 匿名与 Python 直连都失败，只能用 Playwright 在页面上下文里 `fetch`；cookie 有时效，会过期。
3. 图片目录 `styles/` 必须继续走 `.gitignore` 的通配规则（`sites/*/styles/*` 保留在仓库里，正是为了将来别的站若用这个目录名不会被误入库）。
4. 该站当年声明的是 `"landing": false`（无落地页，首页顶部用三态切换器），重启时可以直接复用这个模式。
