# 提示词生图集（PROMPTS-DB-01）

AI 生图成图与提示词对照集：**26,458 条提示词 / 41,261 张图**，来自 YouMind 社区的两条模型线（官方 API 全量抓取）。

| 模型 | 上游 | 提示词 | 图片 | 分类 |
| --- | --- | --- | --- | --- |
| **Imge-2** | `youmind.com/gpt-image-2-prompts` | 15,103 | 22,268 | 41 个官方分类（`tag_categories.py` 映射） |
| **Nano Banana** | `youmind.com/nano-banana-pro-prompts` | 11,355 | 18,993 | 41 个官方分类（同上，同一份分类表） |

- 授权：**CC BY 4.0**（可商用、须署名；每条记录的作者、来源推文、发布时间逐条保留，灯箱内展示「查看来源」链接）——详见 [NOTICE.md](NOTICE.md)
- **一条素材 = 一条提示词 + 它的全部成图**：卡片右下角有 `1 2 3` 按钮切换，灯箱里是缩略图条（`←` `→` 也能切）
- 筛选：模型 / 41 个分类 / 标签 / 画幅 / 关键词；收藏、手动标签、回收站存 localStorage（按素材 id）
- 页面形态：`index.html`（约 40 KB）+ `data/gallery.js`（模型索引，几 KB）+ `data/gallery_<key>.js`（每个模型一份数据分片）

## 数据管线

```
import_youmind.py        YouMind API → img/<key>/ 图片 + data/prompts_<key>.json（文本数据，不入库）
tag_categories.py        按 41 个官方分类逐类翻页 → data/<key>_id2cats.json（id → 分类映射，不入库）
scripts/manifest.py      各模型文本数据 → manifest.json（fetch/verify 契约，入库）+ data/dims.json（宽高缓存，不入库）
scripts/build_gallery.py → index.html + data/gallery.js + data/gallery_<key>.js + robots/sitemap/404 + cat/*/
```

站主自己挂的图（素材管理器「添加图片」→ 本站）走另一条线，与上游数据彻底解耦：

```
素材管理器 attach  →  library/ + gallery.db（role=user）
sync_user_assets.py → userimg/ 图片 + data/user_assets.json（按 originId 归属，入库）
build_gallery.py    → 按 originId 合并进分片，追加到该提示词的成图末尾（标「自制」）
```

同步上游新增（元数据有缓存，只下新图）：

```bash
python import_youmind.py --model gpt-image-2        # 或 nano-banana-pro
python tag_categories.py --model gpt-image-2        # 分类映射（断点续抓；--only slug 可重抓指定分类）
python scripts/manifest.py
python ../../tools/build.py --site prompts
```

两个模型都要跑：站点记录的 `promptCategories` 字段上游常常是空的（Nano Banana 全空），
分类只能靠 `categories` 参数逐类反查，所以每个模型各有一份 `<key>_id2cats.json`。

图源被 DNS 污染时，`import_youmind.py` 默认走 `--proxy http://127.0.0.1:7897`。

**全新克隆**（只有代码、没有数据）按上面四步跑一遍即可。`data/prompts_*.json`、`data/gallery_*.js`、`data/dims.json`、`data/*_id2cats.json` 都不在仓库里，`git status` 看不到它们，这是预期行为，不是漏提交。

## 给提示词加自己的成图

同一条提示词，你可能会自己再跑几版。这些图**不塞进上游数据**（`prompts_<key>.json` 是
`import_youmind.py` 的产物，会被整份重写），而是走一层覆盖：

```bash
# ① 素材管理器（python index/serve.py）里点开某条提示词 → 右栏「添加图片」
# ② 导出成覆盖层
cd sites/prompts && python sync_user_assets.py
# ③ 重建
cd ../.. && python tools/build.py --site prompts
```

- **落地位置**：图在 `userimg/`（与上游 `img/` 平级、物理分开），归属写 `data/user_assets.json`。
  两者都**入库**——自己的图不可再生，丢了没法从上游重下。
- **排序**：追加在成图列表末尾，上游图永远在前，主图（`cover=0`）不受影响。
- **标识**：灯箱缩略图条上画虚线框，标签行标「自制」，提示「版权归本站，不在 CC BY 4.0 范围内」。
- **授权边界**：`img/` 全部是 CC BY 4.0 上游素材，`userimg/` 是自己的，NOTICE.md 分开写明。
- **上游换批**：如果某条提示词整条从上游消失，构建会打印警告并跳过它的自制图（不会静默丢）。
- **部署**：`userimg/` 随仓库走，不需要 `fetch.py`；`manifest.json` 里也没有它们（那是上游下载清单）。
- **幂等**：重复跑 `sync_user_assets.py` 只补差异；`--prune` 会清掉覆盖层里已不再引用的旧图。

## 为什么按模型分片

两个模型合起来 4.1 万张图。如果沿用「一图一条 + 每张都带完整提示词」的单文件格式，`gallery.js` 会涨到 **约 170 MB**，首屏直接不可用。现在的做法是两层压缩：

1. **一条提示词只存一份**（图片是提示词的 1.5~2.5 倍，重复存是纯浪费），图片退化成 `[文件名, 宽, 高, 比例]`；
2. **按模型分片**：进站只加载 `DEFAULT_MODEL`（`imge-2`）那一份，切模型或点「全部」时才按需 `<script>` 注入其余分片。

两个分片合计约 70 MB，比原来的单模型 79 MB 还小。

## 与其他站的差异

- **数据外置且分片**：`data/gallery_<key>.js` 是构建产物，**不入库**（54 MB + 30 MB；每次重抓都会变，入库会让 git 历史反复存两份几十 MB 的 blob）。构建时本地生成。
- **宽高来自 `data/dims.json`**：构建不读图片文件，所以没有图片也能构建；**但必须有 `data/prompts_<key>.json`**，那是从上游抓来的文本数据，同样不入库。全新克隆要先跑 `import_youmind.py` + `scripts/manifest.py` 才能构建本站，因此 CI 的构建步骤带 `--skip prompts`，其余八站照常校验。
- **入库的只有小文件**：`manifest.json`（14 MB，图片清单，`fetch.py` 与测试都要读它）、`data/gallery.js`（275 B 索引）、`data/landing.json`、`data/gpt2_categories.json`（41 个分类的静态清单）以及页面本身。忽略规则见仓库根 `.gitignore` 的「prompts 站的抓取与构建中间数据」段。
- **缩略图来自上游 CDN**（`mediaThumbnails`，约 20~25 KB/张），`fetch.py` 按 manifest 的 `thumb_path` 下载到 `thumbs/<key>/`。
- **分类靠 `categories` 参数反查**：上游记录里的 `promptCategories` 字段对两个模型都不返回数据（Nano Banana 是 0/11,783），但 API 支持按 `categories` 过滤。`tag_categories.py` 逐类翻页把 id 收回，再反查成 id → 分类表。
- **分类覆盖不完整，这是上游限制**：单页固定 85 条，深分页到 100~140 页后上游返回 `total=0`，所以大分类拿不全（Nano Banana 的 `photography` 12,021 条只取到 8,113，`social-media-post` 10,079 取到 6,625）。`sort` 参数对结果集没有影响，换排序也取不到另一批。实际覆盖 11,325/11,783 条提示词（96%），平均 4.8 个分类，398 条无任何分类。
- `scripts/legacy/` 是独立本地页时期的脚手架（CSV 导入、演示数据），未接入构建管线；计划归档到 `docs/legacy/prompts-legacy-scaffold/`（见 `docs/REFACTOR_V7_LOCKED.md` 的 D08）。
