# 加第 N 个站

新站点只要满足下面的约定，`tools/` 下的 fetch / mid / verify / build / release 都不用改。
下载和校验是共用的（`shared/assets.py`），各站不需要自己的下载或校验脚本。

## 1. 建目录

```
sites/<新站id>/
├── scripts/
│   ├── build_gallery.py    # 必填
│   ├── extract.py          # 按需：从原站存档解析 data/
│   ├── manifest.py         # 按需：data/ → manifest.json
│   └── fetch_hook.py       # 按需：图源要浏览器化请求头、cookie 或自带取图通道时提供
├── data/                   # 结构化数据（入库）
├── index.html              # 构建产物（入库，便于直接预览）
├── LICENSE
├── NOTICE.md               # 该站单独的授权说明
└── README.md
```

| 文件 | 约定 |
|---|---|
| `scripts/build_gallery.py` | 读环境变量 `SITE_URL`，输出 `index.html`、`data/`、`robots.txt`、`sitemap.xml`、`404.html`。站点根用 `dirname(dirname(__file__))` 自己算，不依赖当前目录 |
| `manifest.json` | 每条记录对 `sites.json` 里的每个档位 `<tier>` 都有 `<tier>_url` 和 `<tier>_path`（例如 `thumb_url` / `thumb_path`）。`tools/fetch.py` 和 `tools/verify.py` 只靠这条规则工作 |
| `scripts/fetch_hook.py` | 图源要浏览器化请求头、cookie 或自带取图通道时提供（见下）。没有这个文件的站点行为完全不变 |

结构和姿势集相同的站，直接复用 `shared/pose_gallery.py` 与 `shared/pose_source.py`，只写一份 `config.py`（参考 `sites/pose/config.py`）。
数据来自别的项目、系列和名称不同的，参考 `sites/shisei/config.py`：系列与视角顺序、中文名表、作者、`blurRatings`（默认模糊）都在配置里。

### 图源要 cookie 或特殊请求头时

`shared/assets.py` 默认只发 `User-Agent` 与 `Referer`。有些图源（挂在 Cloudflare 后、
要做 JS 挑战的）光这样不够。**不要为此改 `tools/`**，而是在本站放一个取图钩子：

```python
# sites/<新站id>/scripts/fetch_hook.py
def headers(url, referer):
    """追加到默认请求头之后。"""
    return {"Accept": "image/webp,*/*", "Referer": "https://example.com/"}

def prepare(opener, log):
    """可选：预热。先访问页面拿 cookie，返回带 cookie 的 opener。"""
    ...

def fetch_bytes(url, headers, timeout):
    """可选：站点自带取图通道。返回图片字节，失败抛异常。"""
    ...
```

三个函数**都是可选的**，按需实现：

| 钩子 | 什么时候需要 | `shared/assets.py` 怎么用 |
|---|---|---|
| `headers(url, referer)` | 图源要浏览器化的请求头 | 追加到默认请求头之后 |
| `prepare(opener, log)` | 图源要先拿 cookie / 通行证 | 下载前调用一次，用返回的 opener |
| `fetch_bytes(url, headers, timeout)` | **默认的 urllib 通道被上游按客户端指纹拦掉**，站点要自带一条浏览器味的取图通道 | **优先调用**它取图；没有这个函数就照旧走 urllib |

`shared/assets.py` 会自动发现并调用它们；没有这个文件的站点走默认路径，行为不变。

实例：`sites/midjourney-explore/scripts/fetch_hook.py` —— `cdn.midjourney.com`
要浏览器化的请求头与 Cloudflare 下发的 `__cf_bm` 通行证 cookie；
2026-11-05 实测：Python urllib 这两样都带仍然被按 **TLS 指纹**（JA3）403，
换 curl/浏览器通道同一出口 IP 却能取到 640/1024 两档 —— 这种站就该用第三个钩子
`fetch_bytes` 自带一条浏览器味的取图通道，而不是改 `tools/`。

## 2. 在 `sites.json` 追加一条

```json
{
  "id": "new-site",
  "code": "NEW-DB-01",
  "name": { "zh": "新站名", "ja": "新サイト名" },
  "desc": { "zh": "一句话说明。", "ja": "一文で説明。" },
  "stats": [{ "v": "1234", "l": { "zh": "图片", "ja": "画像" } }],
  "license": "cc0",
  "source": "https://new-site.pages.dev/",
  "cover": "thumbs/cover.webp",
  "coverPos": "center 30%",
  "tiers": ["thumb", "full"],
  "imageDirs": ["thumbs", "mid", "img"]
}
```

| 字段 | 说明 |
|---|---|
| `id` | 唯一标识，同时是目录名和 URL 路径 |
| `source` | 原站地址，下载时作为 Referer |
| `imageBase` | 可选。图片不在原站域名下时填写（如 Shisei 的图片在上游 GitHub 固定标签里），测试据此核对 manifest 的 URL |
| `imageBases` | 可选。图片分散在多个 CDN 域名时填列表（如 PromptHero：衍生图在 `img.prompthero.com`、原图在 `cdn.prompthero.com`），取代 `imageBase` |
| `code` | 入口页封面左下角的编号 |
| `cover` | 相对站点目录的封面路径 |
| `coverPos` | 封面框是 16:10，竖图必然裁切：脸部特写用 `25%`–`35%`，全身图用 `0%`–`10%`，主体居中用 `50%` |
| `tiers` | 下载与校验的档位，对应 manifest 里的 `<tier>_url` / `<tier>_path` |
| `imageDirs` | `release.py` 硬链接的目录；含 `mid` 时 `mid.py` 会为该站生成中图（`tiers` 里已有 `mid` 的站点由上游提供，不生成） |
| `license` | `cc0` / `conditional` / `restricted`，决定入口页卡片上的授权徽章 |
| `landing` | 可选，站能力声明。默认 `true`（生成落地页）；`false` 表示这个站**不生成落地页**，hub 与 sitemap 据此不再链到它的 `browse/` |

站点在入口页的顺序 = `sites.json` 数组顺序。

> **`landing: false` 意味着什么。** 该站的 `scripts/build_gallery.py` 要让
> `build_facets()` 返回空分面列表，`shared/landing.py` 的 `write_site()` 会据此
> 清掉上次的落地页并写一份空 `landing.json`；hub 的 `browse/` 链接与
> `llms.txt` 的分类索引按这个字段条件生成。`tests/run.py` 双向校验：
> 声明 `false` 的站必须**没有**落地页，声明 `true` / 未声明的站必须**有**。
>
> 典型场景：新站的内容没有可枚举的分类（上游只有一个搜索框），落地页只能是
> 首页的子集视图 —— 那就声明 `false`，别硬造分面。
> 2026-11-04：唯一用过它的站是 `mj-styles`（Midjourney 风格码库），同日该站
> 因价值不足被整站删除；**机制本身保留**，但当前没有使用者。

## 3. 测试会强制的隐含约束

`tests/run.py` 自动覆盖 `sites.json` 里的新站。下面每条不满足都会直接 fail，
写新站时先对照一遍：

| 约束 | 检查项 |
|---|---|
| canonical 必须是 `https://example.com/<id>/`，head 里不得写死正式域名 | `Pages.test_canonical_and_no_placeholder_leak` |
| `index.html` ≤ 450 KB | `Pages.test_page_size_budget` |
| 去掉 JS 与样式后可读文字 ≥ 500 字 | `Landing.test_static_intro_on_gallery_pages` |
| 恰好 1 个 `<h1>`，含 `"@type":"FAQPage"`，含 `class="seo-intro"` 与 `<details class="seo-more">` | 同上 |
| 至少 1 个静态落地页（`browse/`），分面不足 6 张不成页 | `Landing.test_every_site_has_landing_pages`（`landing: false` 的站除外） |
| 声明 `landing: false` 的站必须没有落地页，且磁盘上不留落地页目录 | `Landing.test_no_landing_site_has_no_landing_dir` |
| 落地页只用缩略图，不得出现 `/mid/` `/img/` `/png/` | `Landing.test_only_thumbnails_exposed` |
| 落地页每张 `<img>` 必须有 `alt` 且 ≥6 字符 | `Landing.test_head_and_body_basics` |
| 落地页引用的图必须在 manifest 的 `thumb_path` 里，路径层级要对 | `Landing.test_thumbs_are_in_manifest` |
| 每个 tier 都要有 `<tier>_url` / `<tier>_path`，路径用 `/`、不含 `..`、不重复 | `Manifests.test_tier_fields_present` / `test_paths_portable_and_unique` |
| 所有 URL 必须落在 `source` / `imageBase` / `imageBases` 之下 | `Manifests.test_urls_point_to_source` |
| manifest 路径顶层目录必须在 `imageDirs` 里 | `Manifests.test_image_dirs_match_paths` |
| 封面必须在 manifest 的 `thumb_path` 里 | `Manifests.test_cover_in_manifest` |
| `imageDirs` 含 `mid` 时，页面里必须有 `midOf` 函数，且与 `tools/mid.py` 的 `mid_rel` 逐条一致 | `MidRule.test_python_and_js_agree` |
| 新站的 `README.md` 与 `NOTICE.md` 必须存在，其中的相对链接不能失效 | `Docs.test_relative_links_and_anchors` |

> **`midOf` 必须真被调用。** 定义了一份却没人用的规则等于没有规则，而且它会
> 漂移 —— 2026-11-04 就发现 `prompthero-midjourney` 的 `midOf` 描述的是别的站的
> `img/` 布局（本站根本没有 `img/` 目录），算出来的路径必然 404。
> `MidRule` 现在会跳过没有调用点的 `midOf`；但更好的做法是**直接删掉**它 ——
> 本站的中图是上游直给的衍生图（数据里的 `m` 字段），没有「按路径复算」这回事。

> **数据量大的站要分片。** 单页内嵌全部数据会撞上 450 KB 上限。
> 参考 `sites/prompts/`：把数据写成 `data/gallery_<key>.js`（`JSON.parse` 赋值），
> 页面只内嵌一份小索引，进站按需加载分片。分片不入库时，CI 构建该站要加 `--skip`
> （干净检出上分片不存在，构建必然失败）——`prompts` 站就是这么处理的。
> 但如果分片**可由入库的源头数据**（如 manifest.json）一键重建，优先不 skip：
> CI 构建比对照常校验该站，闸门不缩水——`prompthero-midjourney` 站就是这么处理的。

## 4. 构建

```bash
python tools/fetch.py --site new-site
python tools/mid.py --site new-site      # imageDirs 含 mid 时
python tools/verify.py --site new-site
python tools/build.py
python tools/release.py
python tools/serve.py
python tests/run.py                      # 提交前跑一遍；CI 也会跑
```

`tests/run.py` 会自动覆盖 `sites.json` 里的新站：构建产物是否最新、重复 id、JS 引用的 id 是否存在、
内联数据是否都被页面使用、页面体积上限、manifest 的档位字段与路径、封面是否在 manifest 里。

## 5. 接入素材管理器（index/）

站点页面建好了，**不等于它进了 WebUI**。索引侧是三个独立的地方，漏改任何一处，
站点页面照样正常、CI 照样全绿，只有用户在素材管理器里查不到素材时才发现：

| 位置 | 作用 | 漏了会怎样 |
|---|---|---|
| `sites.json` | 站点清单 | 站点根本不存在 |
| `index/catalog.py` 的 `SOURCES` | 索引哪些站、字段怎么映射 | **WebUI 里查不到这个站** |
| `index/sync.py` | 索引实现 | 同步不出条目 |

```python
# index/catalog.py 的 SOURCES 里加一条
"new-site": {
    "manifest": "sites/new-site/manifest.json",
    "title": "title",
    "title_alt": None,
    "facets": {"分类": "category"},
    "files": [("thumb", "thumb_path"), ("full", "full_path")],
    "size": None,
    "bytes": None,
    "prompt": "prompt",       # 有提示词就配上；没有就留空
    "keywords": "prompt",
    "extra": {"author": "username", "source_url": "sourceUrl"},
    # 一条内容多张图的站必须声明聚合键（见下）
    # "group_by": "jobId",
    # "group_order": "index",
},
```

### 多图站：同一提示词的 N 张图要在一个灯箱里

上游一次作业出 4 格、共用一段提示词时，manifest 是 4 行、id 各不相同。
**不声明聚合键，这 4 行会变成 4 条独立素材**，WebUI 灯箱里翻不到一起。

- 声明 `group_by`：按该字段聚合成**一条**素材，组内多张图挂成它的多个 asset，
  `ordinal` = 组内顺序（灯箱翻页顺序），由 `group_order` 指定。
- 确实是「一条记录一张图、不该聚合」（如同姿势的 5 个视角在站内是独立条目）：
  声明 `split_by_design` 并写明理由。两者都不写，测试会拦下。

### 接入后必做的验证

```bash
python index/sync.py --force          # 重建索引
python index/check_wiring.py           # 核对各站条目数（CI 也跑这一步）
python tests/run.py                    # 含索引接线测试
```

`check_wiring.py` 逐站核对「实际条目数 == 按配置推算的条目数」，
`tests/run.py` 的 `IndexMapping` 核对清单、聚合声明、字段映射是否自洽。

**⚠ 一定要对**真实库**跑，别只验临时库。**

索引是**一份文件**（`gallery.db`），站点页面和 WebUI 各读一份数据：
页面读 `manifest.json`，WebUI 读库。两者不同步时，
**站点页面一切正常，但 WebUI 里那条集合永远是空的**——零报错。

更隐蔽的一种：拿临时库（`--db /tmp/x.db`）验完就说「全部核对通过」，
但真实库根本没重建。拆 `mj-styles` 那次就是这么交的，
交付前只验了临时库，真实库停留在加站之前的状态，
用户在 WebUI 里根本看不到新站。

规矩：

- `check_wiring.py` 的 `--db` **默认就是真实库**（`gallery.db`），
  不要为了省事传临时库路径，那等于没验。
- 跑完 `sync.py` 后，**确认 serve 进程是新的**：
  改了 `catalog.py` 之后，旧 serve 进程不会自动加载新代码，必须杀掉重启。
- 现在 serve 会**自动重同步**（读接口前按 manifest 签名判断，见 §9），
  但自动重同步只覆盖「进程还活着」的情况；
  改完 `catalog.py` 之后**旧的进程里跑的还是旧代码**，照样看不到新站。


## 6. 声明取图策略（这一站的图片从哪来）

站点清单 `sites.json` 里每站要声明 `imagePolicy`，按档位给出，三种取值：

| 取值 | 含义 | 什么时候选它 |
|---|---|---|
| `local-first` | 站内相对路径优先，图片加载失败时回落到该档位的上游地址 | 缩略图这类**留在本地**、但偶尔会缺文件的档位（回落是保险） |
| `online` | 直接用上游地址，站内不再保留该档的图片 | 原图档——占了绝大部分空间，切走后本地能省几十 GB |
| `local-only` | 只用站内地址，不做上游回落（默认） | 上游对直连有防护（如 `cdn.midjourney.com` 要 Cloudflare 通行证、裸请求过不去）、或这一档本来就不从上游取 |

```json
"midjourney-explore": {
  "tiers": ["thumb", "mid", "full"],
  "imagePolicy": {"thumb": "local-only", "mid": "local-only", "full": "online"}
}
```

几个要注意的地方：

- **声明与实现必须一致**：声明了 `local-first` / `online` 的档位，构建产物里必须带得上游地址，否则页面既没有回落目标也不知道该直连哪里。`tests/run.py` 的 `ImageArtifacts` 守这条。
- **构建过程不探测本地文件是否存在**。策略是提交进仓库的静态配置，构建产物只取决于配置——这样产物在有图与无图的环境里逐字节一致，`Build` 那个一致性闸门才成立。
- **页面体积有上限（450 KB）**。把原图档切成 `online` 会让每条记录多带一段 URL，页面因此变大。页面本来就接近上限的站（如 `portrait` 353 KB）切完会超限，要么先把该站分片化，要么这一轮先不切。
- **中图等按路径推导的规则只吃站内相对路径**。展示地址换成上游 URL 之后，推导就没有输入了，因此要保留一份相对路径（`<字段>Path`）。
- **通用代码里不出现站点分支**。站点差异只通过这份声明表达；上游不可直连的站也用 `local-only` 声明，不在代码里写 `if`。

切完之后本地的原图档可以整档删掉：

```bash
python index/sync.py --force     # 重建索引（含上游地址）
python index/verify.py           # 有上游地址的资产不再报缺图
```

### 删本地原图之前：先确认「页面确实不请求它」

`online` 档位**声明了**不等于**页面没用本地文件**。删之前逐项核实，
否则删完才发现页面裂图，而且上游往往下不回来（不可逆）。

**判据（按这个顺序查）**：

| 查什么 | 怎么看 | 结论 |
|---|---|---|
| 页面/分片里的展示地址是什么 | 搜数据里的 `<字段>`（full 档是 `g`）| 指向 `https://` = 页面用上游；指向 `img/` = 页面用本地 |
| 页面 JS 里有没有引用本地路径 | 搜 `<字段>Path`（如 `gPath`）| **没人引用**才安全——它只是给「按路径推导的规则」留的备用字段 |
| 索引里这一档记的是什么 | `SELECT path, url FROM derivative WHERE kind='full'` | `path` 是上游 URL = 索引不依赖本地文件 |
| 上游现在能不能访问 | 浏览器里 `new Image().src = 上游URL` | **浏览器能加载**才算数 |

⚠️ **用浏览器验，别用 Python 裸请求。** Python 直连会被代理策略、
或被 Cloudflare 按 **TLS 指纹（JA3）** 判成非浏览器客户端挡住，得出「上游不通」的假结论；
浏览器走系统代理、指纹也像浏览器，上游可能其实通着。实测：
`cdn.prompthero.com` 用 Python 直连 TCP 超时（判「不通」），
但浏览器里 `new Image()` **加载成功 3300×4200**；
`cdn.midjourney.com` 同样是**客户端指纹**问题（2026-11-05）——同一出口 IP、同一时刻，
Python urllib（带浏览器化请求头 + `__cf_bm` 通行证 cookie）取 `0_0_640_N.webp` /
`0_0_1024_N.webp` 是 **403**，Windows 自带 `curl.exe`（Schannel TLS、**不带 cookie**）
取同样两个地址是 **200**。
所以「上游不通」多半是**本机通道**的问题（代理策略 / 客户端指纹），先换通道再下结论。

**静态站没有服务端回落。** WebUI 的媒体路由（`serve.py` 的 `serve_media`）
会在本地文件缺失时 302 到上游，静态站（部署到 nginx 的那些）没有这层 ——
只有 `local-first` 才会给 `<img>` 写 `data-fb` 回落属性。
所以「WebUI 里还能看」不等于「部署出去还能看」。

**当前各站的情况（2026-11-04 实测）**：

| 站 | 档位 | 策略 | 本地体积 | 能不能删 |
|---|---|---|---|---|
| ~~prompthero-midjourney~~ | `img/`（full） | online | ~~36.3 GB~~ | ✅ **已删**（2026-11-04） |
| prompts | `img/`（full） | online | 7.2 GB | ✅（本地只剩 2 个文件，已删过） |
| costume | `png/` | online | 1.3 GB | ✅（本地只剩 8 个） |
| portrait | `img/`（full） | local-only | 4.6 GB | ❌ 删了永久裂图 |
| prompthero-midjourney | `mid/`、`thumbs/` | local-only | 2.1 GB | ❌ |
| midjourney-explore | `mid/`、`thumbs/` | local-only | 571 MB | ❌ 无上游回落，删了裂图；上游只是对 Python 通道按 TLS 指纹拦截（curl/浏览器通道可通 640/1024 两档），裸请求过不去 |

（此表只列还在的站。`mj-styles` 曾以 `styles/` 占 252 MB，2026-11-04 随整站删除一并清空。）

`prompthero-midjourney` 原先是「策略说 online、磁盘上却留着全量」的状态 ——
**37 GB 白占着**，页面行为零影响。2026-11-04 已删，并做了配套的三处改动：

1. `sites.json` 的 `tiers` 去掉 `full`、`imageDirs` 去掉 `img`
   —— 声明与磁盘现实对齐，`fetch.py` / `verify.py` 不再把 full 档当成本地档位。
2. `scripts/manifest.py` **不写 `full_path`** —— 没有本地文件，写一个站内路径
   就是谎报，索引会拿它当本地文件去找、永远找不到。
   （`full_url` 照写，页面直连上游靠它。）
3. `scripts/build_gallery.py` 的 `_addr()` 用 `rec.get(tier + "_path") or ""`
   —— 严格索引遇到 online 档（没有本地路径）会 KeyError。
   对照 `sites/midjourney-explore/scripts/build_gallery.py` 的同名函数。

删完记得同步索引（路径没变，但 `verify.py` 的缺图数会变）：

```bash
python index/sync.py --force
python tools/verify.py
```

`verify.py` 只检查 `sites.json` 声明的 `imageDirs` —— full 档已从 `imageDirs`
里去掉，所以它**不再报 full 档缺失**。如果哪天看到「full 档缺失 12998」，
说明 `tiers` / `imageDirs` 又被改回去了，是配置与现实脱节，不是磁盘故障。

## 7. 从原站接口采集数据（prompthero-midjourney 的经验）

数据没有现成交档、要从上游接口抓时，按这几条走，能少走弯路：

- **先抓前端 bundle 定位接口**：在 DevTools 里翻前端的 JS chunk，挖出真实的
  tRPC / GraphQL procedure 与参数形状，不要硬猜 URL 查询参数——页面上看到的
  `?page=2` 这类参数可能是摆设。
- **探测分页上限与排序稳定性**：接口往往有隐藏的 pageSize 上限（如 48）；
  凡是按排序分页，两次采集之间可能因并列漂移产生重复或丢条目——
  采集侧必须按稳定键（如 slug）做确定性去重。
- **限流退行**：批量请求先低速小批试跑，触发 429 就指数退避、后台分批补抓；
  采集统计（总条数、NSFW 数、缺失回落数）写进 `data/meta.json` 留档。
- **图片缺口的回落链**：多档位（原图 / 中图 / 缩略图）不必逐档都存在，
  manifest 里缺失的档位回落到下一档并记 fallback 标记，
  `verify.py` 保证最终每条每档都有可用文件。

### prompthero-midjourney：full 档是 online，本地那 37 GB 是白占的

这一站是全仓最大的一个（`sites/prompthero-midjourney/`，36.3 GB 原图 + 2.1 GB 中图/缩略）。
但它的 `imagePolicy` 是：

```json
{"thumb": "local-only", "mid": "local-only", "full": "online"}
```

**`full` 档本来就是直连上游的** —— 页面的展示地址是
`https://cdn.prompthero.com/<slug>`（分片里的 `g` 字段），
本地 `img/` 里的 12998 个 PNG **页面一个都不请求**。

删之前已逐项核实（2026-11-03）：

| 查什么 | 结果 |
|---|---|
| 分片里 `g` 指向 | 12998/12998 都是上游 URL（**0 个**指向 `img/`）|
| 页面 JS 里 `gPath`（本地路径字段）| **零引用** —— 只在数据里，页面不读 |
| 索引里 full 档 | `path` 和 `url` **都是上游 URL**，不依赖本地文件 |
| 浏览器实测（删掉 5 个后）| `new Image(src=g)` **加载成功 3300×4200**；`m`（本地中图）正常；`gPath` 失效（预期，无人用）|

**结论：`sites/prompthero-midjourney/img/` 可以整目录删掉，省 36.3 GB，页面行为零影响。**
删完 `tools/verify.py` 会报 full 档「缺失 12998」—— 这是预期信号，不是故障。

教训写在这里：**「策略声明成 online」和「磁盘上还留着全量」是两件事。**
这个站策略早就切了，本地副本却一直没人清，37 GB 白占了很久。
以后切完 online 策略，顺手把对应目录清掉。

⚠️ 上游直连要**用浏览器验**。Python 裸请求 `cdn.prompthero.com` 会 TCP 超时
（**误判为「上游不通」**），但浏览器走系统代理实际能加载。别被 Python 的假结论误导。
——「上游不通」多半是**本机通道**的问题（代理策略 / 客户端指纹），先换通道再下结论。

上线到已有服务器的步骤见 [DEPLOY.md](../deploy/DEPLOY.md) §6。

## 9. 索引什么时候重建（serve 的自动重同步）

`index/serve.py` 在**读接口进来之前**会判断索引是否过期：
`sync.signature()` 算出「各站 manifest 的 mtime+size + 字段映射表的摘要」，
跟库里存的 `manifest_signature` 比。一样就什么都不做；不一样就重建。

- 判定成本约 **1 ms**（`signature()` 实测），放在请求路径上不心疼。
- **加站自动生效**：往 `catalog.SOURCES` 和 `sites.json` 里各加一行之后，
  manifest 的 mtime 变了 → 签名变了 → 下一次读接口就重建 → 新站立刻出现在 WebUI。
- `--no-reload` 可以关掉这个行为（以前这个参数声明了但从没被读过，是个死参数）。
- 重建**保留用户标注**：`store.reset()` 先把标签 / 收藏 / 隐藏 / 手工挂图
  存进 `_keep_*` 临时表，`restore_user_data()` 再放回来。

**但自动重同步只覆盖「进程还活着」的情况。**
改了 `catalog.py`（比如加了分面、改了视图）之后，
**旧 serve 进程里跑的还是旧代码**——它启动时加载过一次模块，
不会自动重新 import。这时候必须杀掉重启。

判断「serve 跑的是新代码」有个现成的探针：

```bash
# 打这个接口，如果返回的 URL 是纯 CDN 地址（没有多余的 /media/ 前缀），
# 说明进程加载的是新代码
curl -s "http://127.0.0.1:8788/api/items?collection=midjourney-explore&size=1"
```

## 设计约定

新站点请保持一致：

- 主题切换 `[☀ Light][☾ Dark]`，默认浅色
- 语言切换 `[中文][日本語]`，默认中文，中文在左
- `<head>` 内用同步脚本应用已存偏好，避免刷新闪白
- 单文件 `index.html`，数据内嵌，零外部依赖（数据量大到撑破 450 KB 上限时改为分片外置，见上文第 3 节）
- 分页加 `IntersectionObserver` 预取，不一次渲染全部卡片
- 灯箱底图用清晰缩略图，不加模糊；中图到达后淡入
- 有成人内容的站：默认模糊 + 点开单张才清晰 + 不生成落地页（参考 `sites/shisei/` 的 `blurRatings` 机制）
