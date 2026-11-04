# prompthero-midjourney 的原图档位不落地本地

这个站的原图（PNG，`cdn.prompthero.com`）曾在本地存了 36.3 GB，但页面上的「下载原图」本来就是直连上游（`imagePolicy.full = online`），本地那份从未被页面读到 —— 纯占磁盘，还让 `tools/fetch.py` 每次都要校验 12998 个文件。2026-11-04 决定删掉本地原图，并把 `full` 档从 `sites.json` 的 `tiers` 与 `imageDirs` 里去掉，让配置与磁盘现实对齐。

## 考虑过的替代方案

| 方案 | 否决理由 |
| --- | --- |
| 保留 `full` 档声明，只删文件 | `fetch.py` 会把它当本地档位反复校验，永远「缺一个就重下一个」；`verify.py` 每天报 12998 个缺失 |
| 改成 `local-first` | 页面会先请求站内路径（本地无副本）→ 每次都 404 再回落上游，白白多一次请求 |
| 改成 `local-only` | 页面只认站内路径，而本地无副本 → 永久裂图。绝对不行 |

## 后果

- **manifest 不再写 `full_path`**，只写 `full_url`。没有本地文件却写一个站内路径就是谎报 —— 索引会拿它当本地文件去找，永远找不到。
- 构建脚本取路径必须用 `rec.get(tier + "_path") or ""`；严格索引 `rec[tier + "_path"]` 遇到 online 档会直接 KeyError。
- `index/catalog.py` 的 `file_specs` 必须保持**双键** `"full_path|full_url"` —— 兜底推导要求键以 `_path` 结尾，单键会让该档被静默跳过。
- 对外公布的参考图总数从 128,929 降到 **115,931**（少 12998 个原图文件）。这个数字是「文件数」口径，原图不落地就不计入。
- `tools/verify.py` 不再检查 full 档。将来若看到「full 档缺失 12998」，那是 `tiers` / `imageDirs` 被改回去了，是配置与现实脱节，不是磁盘故障。
