# userimg — 站主自制图

放**站主自己跑出来的成图**，由 `../sync_user_assets.py` 从素材管理器导出，不要手工往里塞文件。

## 与 img/ 的区别

| | `../img/<key>/` | `userimg/` |
| --- | --- | --- |
| 来源 | YouMind 上游素材 | 站主自己生成 |
| 授权 | CC BY 4.0（须署名） | 版权归本站，**不在 CC BY 4.0 范围内** |
| git | 忽略（`fetch.py` 下载） | **入库**（无法从上游重下） |
| manifest.json | 有记录 | 无记录（不是下载目标） |
| 页面标识 | 无 | 灯箱缩略图虚线框 + 「自制」徽标 |

## 结构与流程

```
userimg/u-<originId>-<n>.jpg          原图
userimg/thumbs/u-<originId>-<n>.webp  缩略图（卡片用）
../data/user_assets.json              归属关系（originId → 这组图）
```

```bash
cd sites/prompts
python sync_user_assets.py        # 从 gallery.db 的 role=user 链接导出
python ../../tools/build.py --site prompts
```

排序上自制图永远追加在成图列表**末尾**，上游图在前、主图不变。上游换批导致某条提示词整条消失时，
构建会打印警告并跳过它的自制图，不会静默丢掉。
