# 部署手册 · 单仓多站

> 站点根 = `tools/release.py` 生成的 `dist/`。
> 与旧方案的区别：不再用 `releases/<版本>/public` + `current` 软链，改为 **git commit 即版本**。
> 线上更新时先发布到暂存目录，检查后再逐个站点原子换入 `dist/`（见 §4），旧版留作回滚。

---

## 0. 前置条件

| 项 | 要求 |
|---|---|
| 系统 | Ubuntu 20.04+ / Debian 11+ |
| git | 任意版本（更新用 `tools/update.py`，见 §4） |
| Python | 3.8+；`tools/mid.py` 需要 Pillow（`apt install python3-pil`），其余只用标准库 |
| 磁盘 | ≥ 100 GB 可用（图片约 86 GB + 中图约 290 MB；硬链接不额外占盘） |
| 内存 | ≥ 512 MB |
| 域名 | 已解析到本机 IP |

```bash
git --version
python3 --version
df -h /
free -m | head -2
```

---

## 1. 首次部署

```bash
apt update
apt install -y git python3 python3-pil nginx

git clone https://github.com/xue1long/ai-video-imge-prompts.git /srv/ai-image-gallery
cd /srv/ai-image-gallery

# ① 下载图片（约 86 GB，只需一次）
python3 tools/fetch.py

# ② 生成灯箱中图（约 290 MB，几分钟；之后只补缺失）
python3 tools/mid.py

# ③ 用正式域名构建
#    注意：prompts 站的数据不在仓库里，服务器上首次构建它会失败（见下方说明）
python3 tools/build.py --base https://你的域名.com

# ④ 组装发布目录
python3 tools/release.py
```

**prompts 站的数据怎么办（首次部署必读）**

`sites/prompts/data/` 下只有 `manifest.json`、`gallery.js`、`landing.json` 入库；`prompts_<key>.json`、`gallery_<key>.js`、`dims.json`、`<key>_id2cats.json` 合计约 220 MB 都靠本地生成（理由见 `sites/prompts/README.md`）。所以全新服务器上 `tools/build.py` 会在这一站报「找不到 data/prompts_*.json」。两条路：

```bash
# 路 A：在服务器上补齐数据（一次性，约 30 分钟；--meta-only 不重下图片）
cd sites/prompts
for m in gpt-image-2 nano-banana-pro; do
  python3 import_youmind.py --model $m --meta-only
  python3 tag_categories.py --model $m
done
python3 scripts/manifest.py
cd ../.. && python3 tools/build.py --base https://你的域名.com

# 路 B：在构建机上构建好，把这些文件 rsync 到服务器，再只构建其余站
rsync -av sites/prompts/data/ 服务器:/srv/ai-image-gallery/sites/prompts/data/
python3 tools/build.py --skip prompts --base https://你的域名.com
```

路 B 依赖构建机与服务器数据一致；只改了其他站时用它最省事。

**预期输出**（release 阶段，格式示例；实际站数与体积以当前 `sites.json` 为准）：

```
发布 · 8 个站点 → /srv/ai-image-gallery/dist
  图片校验通过
  [portrait] 74 个站点文件  图片 4497 链接  → 4.8 GB
  [costume] 106 个站点文件  图片 4221 链接  → 1.4 GB
  [pose] 23 个站点文件  图片 4317 链接  → 710.3 MB
  [pose-depth] 23 个站点文件  图片 4317 链接  → 162.5 MB
  [shisei] 23 个站点文件  图片 3399 链接  → 59.1 MB
  [hub] 9 个根级文件已复制（index.html, sitemap.xml, robots.txt, og-cover.jpg, llms.txt, favicon.ico, …）
其中 20751 个图片文件为硬链接，不额外占盘
```

> 站数以 `sites.json` 的站数为准（当前 8 站），`release.py` 每次发布都会打印实际值。
> 上面的文件数与体积是历史快照，仅用于说明输出格式。

> `dist/` 报告 7.0 GB，但因为是硬链接，**实际磁盘增量接近 0**。
> 若出现「退化为复制」警告，说明 `dist/` 与 `sites/` 不在同一文件系统。

---

## 2. nginx（单域名路径式）

目标拓扑：**全部站点挂在 `photoai.life` 一个域名下**，按路径区分。

```
https://photoai.life/            入口页
https://photoai.life/portrait/   人像集
https://photoai.life/costume/    服装集
https://photoai.life/pose/       姿势集
https://photoai.life/pose-depth/ 深度姿势集
```

### 2.1 前置：DNS 与证书

```bash
# 确认解析到本机
getent hosts photoai.life www.photoai.life

# 签发证书（首次）
certbot --nginx -d photoai.life -d www.photoai.life
```

### 2.2 启用站点配置

```bash
cp deploy/nginx.conf /etc/nginx/sites-available/photoai
ln -sf /etc/nginx/sites-available/photoai /etc/nginx/sites-enabled/
nginx -t
```

**`nginx -t` 必须通过再 reload。**

### 2.3 迁移旧子域名

服务器上原有的 `pose.photoai.life` / `costume.photoai.life` 已在运行，
新配置里为它们保留 301 跳转到新路径，证书沿用。

确认跳转生效后，停用旧配置：

```bash
rm -f /etc/nginx/sites-enabled/refsite-pose /etc/nginx/sites-enabled/refsite-costume
nginx -t && systemctl reload nginx
```

> 旧配置停用前，新旧两套同时启用会因 `server_name` 冲突导致不确定行为。
> **先加新配置并验证路径站可用，再删旧配置。**

### 2.4 为什么不用 alias

`dist/` 是扁平结构（`index.html` + `portrait/` + `pose/` + …），
`root` 直接指过去即可，入口页的 `./portrait/` 相对链接天然命中，**不需要任何 alias**。

---

## 3. 验收

```bash
# 图片完整性（release.py 发布前也会自动跑一遍）
python3 tools/verify.py

# 文件与体积
du -sh /srv/ai-image-gallery/dist
find /srv/ai-image-gallery/dist -name '*.jpg' -o -name '*.webp' -o -name '*.png' | wc -l
# 期望 20751 张图片（含 4377 张生成的中图与 Shisei 的 1133 张上游中图）

# HTTP
for p in / /portrait/ /pose/ /pose-depth/ /costume/; do
  printf "%-14s " "$p"; curl -s -o /dev/null -w "%{http_code}\n" "https://实际域名.com$p"
done

# 缓存头
curl -sI "https://实际域名.com/pose/thumbs/全身1人・セクシー系/立ち/P001/正面.jpg" | grep -i cache-control
# 期望 public, max-age=604800（7 天；图片 URL 不带内容哈希，所以不用一年 immutable）

curl -sI "https://实际域名.com/pose/" | grep -i cache-control
# 期望 no-cache, must-revalidate

# 域名替换是否生效
curl -s https://实际域名.com/pose/ | grep -o 'rel="canonical" href="[^"]*"'
# 不应出现 example.com
```

浏览器逐站确认：

- [ ] 入口页四张卡封面正常显示
- [ ] 点击进入各站，图片能加载
- [ ] 主题切换 ☀/☾ 有效，默认浅色
- [ ] 语言切换 中文/日本語 有效，默认中文
- [ ] 卡片点开灯箱：立即显示清晰缩略图，随后换成中图（开发者工具 Network 里应是 `mid/*.webp`，不是 `img/*.png`）
- [ ] 灯箱 `←` `→` 翻页，`Esc` 关闭；连续翻页时不会闪出上一张图
- [ ] 滚到底部能自动加载下一页

---

## 4. 更新

服务器上的 `sites/*/index.html`、`hub/index.html`、`robots.txt`、`sitemap.xml`
都是**构建产物**，每次 `build.py --base` 都会按正式域名重写。
也就是说：**构建完，工作区必然是「脏」的。**

所以**不要用 `git pull`**——它会在这些文件上报本地改动冲突而中止。
也**不要直接 `git reset --hard`**——它会连手改过的源码一起覆盖，且不留痕迹
（2026-10-30 只打在服务器上的分页补丁就是这样丢的）。用 `tools/update.py`：

```bash
cd /srv/ai-image-gallery
python3 tools/update.py           # fetch，丢弃构建产物；发现手改文件就中止并列出
python3 tools/mid.py              # 只补新增的中图
python3 tools/build.py --base https://实际域名.com
python3 tools/release.py --out dist-stage
```

**不要直接 `release.py` 到线上 `dist/`。** 它会先删除再重建站点目录，重建期间该站会 404。
先发布到暂存目录，检查 canonical、图片数量和页面后，再逐个站点原子对调：

```bash
test ! -e dist-prev || exit 1
for x in index.html portrait costume pose pose-depth; do
  mv -T --exchange "dist-stage/$x" "dist/$x" || break
done
mv -T dist-stage dist-prev        # 对调后暂存目录里是旧版，留作回滚
```

`mv --exchange` 需要 GNU coreutils 9.5+（Debian 13 自带 9.7），而且**必须带 `-T`**，
否则目标会被当成父目录，命令报错退出。只更新了部分站点时，循环里只写那几个。
对调完成后不需要 reload nginx。

`update.py` 把改动分两类：`build.py` 会重写的构建产物直接丢弃；其他文件（源码、配置）
默认**中止并列出**，什么都不改。确认要丢弃时加 `--force`，脚本会先把 diff 和原文件备份到
`../ai-video-imge-prompts-update-backups/<时间>-<旧提交>/` 再对齐。`--check` 只检查不改动。

服务器上需要的修改，**一律提交进仓库**再部署，不要只改服务器上的文件。

`update.py` 底层仍是 `git reset --hard`，只作用于仓库跟踪的文件，
**不会碰图片目录**——`sites/*/{thumbs,mid,img,png,raw}` 都在 `.gitignore` 里，`dist-*/` 也不受影响。

**图片不需要重新下载** —— `fetch.py` 幂等，已存在文件跳过。
新增站点时才需要再跑一次 `python3 tools/fetch.py --site <新站id>`。

漏跑 `mid.py` 也不会坏：灯箱会在中图 404 后退回加载原图，只是慢。

只改了一个站时：

```bash
python3 tools/build.py --site pose --base https://实际域名.com --no-hub
python3 tools/release.py --site pose --out dist-stage
# 然后按上面的方法只对调 pose
```

---

## 5. 回滚

上一次更新留下的 `dist-prev` 就是回滚源，对调回去即可，秒级、不用重建：

```bash
cd /srv/ai-image-gallery
for x in index.html portrait costume pose pose-depth; do
  mv -T --exchange "dist-prev/$x" "dist/$x" || break
done
```

需要回到更早的版本时，按提交重建再对调：

```bash
python3 tools/update.py --ref <目标提交>
python3 tools/build.py --base https://实际域名.com
python3 tools/release.py --out dist-stage
# 检查后按 §4 对调
```

---

## 6. 加新站之后

```bash
python3 tools/update.py
python3 tools/fetch.py --site <新站id>      # 只下新站的图
python3 tools/mid.py --site <新站id>        # imageDirs 含 mid 时
python3 tools/build.py --base https://实际域名.com
python3 tools/release.py --out dist-stage
```

新站在线上 `dist/` 里还不存在，直接 `mv -T dist-stage/<新站id> dist/<新站id>` 即可；入口页 `index.html` 和根级 `sitemap.xml` 也要对调，否则首页不显示新卡片。

---

## 7. 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| `dist/` 里有「退化为复制」 | 跨文件系统 | 把 `dist/` 放到 `sites/` 同盘。不要用 `--no-images` 代替：它不会保留旧图，站点目录会先被删掉 |
| 入口页封面空白 | 对应站的图片没下载 | `python3 tools/fetch.py --site <id> --tier thumb` |
| 子站 404 | `dist/` 未生成对应目录 | 重跑 `tools/release.py` |
| canonical 还是 example.com | 构建时没传 `--base` | 带 `--base` 重跑 `tools/build.py` |
| 磁盘暴涨 | 图片被复制而非硬链接 | `df -h` 对比 `du -sh dist`；确认同盘 |
| `fetch.py` 大量失败 | 原站不可达或被限速 | 降并发 `--workers 4`；失败条目写在 `sites/<id>/failed_<档位>.json`，重跑只补失败的 |
| `release.py` 报「图片校验未通过」 | 有图片缺失或损坏 | `python3 tools/verify.py` 看具体文件；中图缺失跑 `tools/mid.py`，其余跑 `tools/fetch.py` |
| `detected dubious ownership` | 目录属主与执行用户不一致（常见于从别处 rsync 过来的目录） | `git config --global --add safe.directory /srv/ai-image-gallery` |
| `git pull` 报本地改动冲突 | 构建产物被 `--base` 重写过 | 改用 `python3 tools/update.py`（见 §4） |
| `update.py` 中止并列出文件 | 服务器上有手改的源码或配置 | 需要保留就提交进仓库；确认可丢弃再加 `--force`（会先备份） |
| `git: command not found` | 服务器没装 git | `apt-get update && apt-get install -y git` |
| `Connecting to … port 22` 后立刻 `kex_exchange_identification: Connection closed` | ① 连的不是当前源站 IP；② 本机开着 Clash 等 TUN 模式，SSH 被代理断开 | ① 核对 `~/.ssh/config` 的 `HostName`；② 临时关闭 TUN，或让 SSH 直连物理网卡 |
| 灯箱一直显示缩略图、Network 里 `mid/*.webp` 404 | 没跑 `mid.py`，或 `sites.json` 的 `imageDirs` 没有 `mid` | 跑 `python3 tools/mid.py` 后重新 release |

---

## 8. 授权提醒

各站授权不同，**公开部署前务必确认**：

| 站点 | 授权 | 可否公开 |
|---|---|---|
| 人像集 | CC0 1.0 | ✅ 可自由分发 |
| 姿势集 | 禁止再分发 | ⚠️ 公开可访问在性质上接近再分发 |
| 深度姿势集 | 禁止再分发 + **禁止批量下载** | ⚠️ 同上，且 `fetch.py` 属被禁止行为 |
| 服装集 | 禁止再分发 | ⚠️ 同姿势集 |
| Shisei 姿势线稿 | 图片 CC0 1.0；姿势目录仅注明出处 | ✅ 图片可自由分发；suggestive 姿势默认模糊，不进落地页与 sitemap |
| 提示词生图集 | 图片与提示词文本 CC BY 4.0（可商用、须署名）；站自制图归本站 | ⚠️ 须逐条保留作者与来源；成人内容分区默认模糊，不进落地页与 sitemap |
| Midjourney 探索榜 | 禁止再分发（成图由社区用户生成） | ⚠️ 同姿势集；引用须回链原站 |
| Midjourney 提示词集 | 素材由 PromptHero 用户上传，版权归各原作者 | ⚠️ 同姿势集；成人内容分区默认模糊，不进落地页与 sitemap |

> 表的 `sites.json` `license` 取值只有三种：`cc0`（2 站）、`conditional`（1 站）、
> `restricted`（5 站）。具体措辞以各站 `sites/<id>/NOTICE.md` 为准。

建议：如需公开，至少加访问控制（`nginx.conf` 末尾有配置示例）。
