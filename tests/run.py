# -*- coding: utf-8 -*-
"""不依赖图片的检查：CI 和本地都能跑（图片不进仓库，CI 拿不到）

用法:
  python tests/run.py           # 全部
  python tests/run.py -k ids    # 只跑名字含 ids 的

只用标准库 + 可选的 node（检查内联 JS 语法；没有 node 时跳过这一项）。
"""
import collections, html, json, os, re, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "shared"))

from _common import load_cfg  # noqa: E402
from mid import mid_rel  # noqa: E402

CFG = load_cfg()
SITES = [s["id"] for s in CFG["sites"]]
# 数据源不入库的站：干净检出上构建必然失败，CI 用 --skip 跳过。
# prompts 站的 data/prompts_*.json 约 220 MB，.gitignore 已排除。
SKIP_BUILD = ["prompts"]
# 数据分片外置的站：data/gallery.js 是索引（入库），data/gallery_<key>.js 是分片（不入库）
SHARD_INDEX = ["prompts", "prompthero-midjourney"]
PAGES = ["hub/index.html"] + [f"sites/{s}/{f}" for s in SITES for f in ("index.html", "404.html")] + [
    # 风格码库：独立静态页，由 scripts/build_styles_page.py 生成（不是 tools/build.py 的产物）
    "sites/midjourney-explore/styles/index.html",
    # 素材管理器前端：本地服务直接发这份文件，之前没纳入闸门（重复 id / 选择器 / JS 语法都没管）
    "index/web/index.html"]
BUILD_OUTPUT = ["hub/index.html", "hub/robots.txt", "hub/sitemap.xml", "hub/llms.txt"] + [
    f"sites/{s}/{f}" for s in SITES for f in ("index.html", "404.html", "robots.txt", "sitemap.xml")] + [
    f"sites/{s}/data/landing.json" for s in SITES] + [
    # 数据外置的站：索引文件同样入库，构建产物也要校验一致性
    f"sites/{s}/data/gallery.js" for s in SHARD_INDEX if s not in SKIP_BUILD]


def landing_meta(root, sid):
    p = os.path.join(root, "sites", sid, "data", "landing.json")
    if not os.path.exists(p):
        return {"dirs": [], "pages": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def landing_pages(root=ROOT):
    """各站 data/landing.json 记录的静态落地页（相对仓库根的路径）"""
    return [f"sites/{s}/{pg}/index.html" for s in SITES for pg in landing_meta(root, s)["pages"]]

def generated_files(root):
    """落地页目录里实际存在的全部文件，用来发现多出或缺少的页面。

    SKIP_BUILD 里的站不参与：它们的构建在干净检出上跑不起来，
    落地页不会被重新生成，比对会误报。"""
    out = set()
    for s in SITES:
        if s in SKIP_BUILD:
            continue
        for d in landing_meta(root, s)["dirs"]:
            for dp, _, fns in os.walk(os.path.join(root, "sites", s, d)):
                out |= {os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, "/") for fn in fns}
    return out


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def scripts(html):
    return re.findall(r"<script>(.*?)</script>", html, re.S)


def page_db(html):
    """取出页面里内联的 const DB = {...}；无内联 DB 的页面（如 prompts 站数据外置）返回空"""
    k = "const DB = "
    if k not in html:
        return {}
    i = html.index(k) + len(k)
    obj, _ = json.JSONDecoder().raw_decode(html, i)
    return obj


class Build(unittest.TestCase):
    """仓库里提交的构建产物，必须等于用当前源码重新构建的结果。
    防止改了模板 / 数据却忘了重新构建、提交。"""

    def test_committed_output_matches_fresh_build(self):
        tmp = tempfile.mkdtemp(prefix="gallery-build-")
        try:
            # 复制源码到临时目录构建，不碰工作区；图片目录不需要
            ignore = shutil.ignore_patterns("thumbs", "mid", "img", "png", "raw", "dist*", ".git",
                                            "__pycache__", "failed_*.json")
            dst = os.path.join(tmp, "repo")
            shutil.copytree(ROOT, dst, ignore=ignore)
            # 删掉复制过去的落地页，确认它们完全由构建重新生成
            for f in generated_files(dst):
                os.remove(os.path.join(dst, f))
            r = subprocess.run([sys.executable, os.path.join("tools", "build.py"),
                                "--skip", ",".join(SKIP_BUILD)], cwd=dst,
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
            committed, fresh = generated_files(ROOT), generated_files(dst)
            self.assertEqual(sorted(committed - fresh), [], "这些落地页已不再生成，请重新构建并删掉旧文件")
            self.assertEqual(sorted(fresh - committed), [], "这些落地页还没提交，请运行 python tools/build.py")
            stale = []
            for rel in BUILD_OUTPUT + sorted(fresh):
                with open(os.path.join(ROOT, rel), encoding="utf-8") as a, \
                        open(os.path.join(dst, rel), encoding="utf-8") as b:
                    if a.read().replace("\r\n", "\n") != b.read().replace("\r\n", "\n"):
                        stale.append(rel)
            self.assertEqual(stale, [], "这些文件和重新构建的结果不同，请运行 python tools/build.py 并提交")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class Pages(unittest.TestCase):

    def test_ids_unique(self):
        # 2026-10-30：姿势集筛选区和分页按钮都叫 id="more"，分页停在 60 组
        for rel in PAGES:
            ids = re.findall(r'\sid="([^"]+)"', read(rel))
            dup = [k for k, v in collections.Counter(ids).items() if v > 1]
            self.assertEqual(dup, [], f"{rel} 有重复 id")

    def test_js_selectors_exist(self):
        for rel in PAGES:
            h = read(rel)
            js = "".join(scripts(h))
            refs = set(re.findall(r"\$\('#([\w-]+)'\)", js)) | set(re.findall(r"getElementById\('([\w-]+)'\)", js))
            ids = set(re.findall(r'\sid="([^"]+)"', h))
            self.assertEqual(sorted(refs - ids), [], f"{rel} 的 JS 引用了不存在的 id")

    def test_canonical_and_no_placeholder_leak(self):
        # 仓库里的构建产物约定用 example.com；正式域名只在服务器上 --base 构建
        for s in SITES:
            h = read(f"sites/{s}/index.html")
            self.assertIn(f'rel="canonical" href="https://example.com/{s}/"', h)
            self.assertNotIn("photoai.life/" + s + "/\"", h.split("<body")[0].replace("og:", ""),
                             "head 里不应写死正式域名")
        self.assertIn('rel="canonical" href="https://example.com/"', read("hub/index.html"))

    def test_sitemaps_list_every_site(self):
        sm = read("hub/sitemap.xml")
        for s in SITES:
            self.assertIn(f"https://example.com/{s}/", sm)

    def test_no_unused_inline_data(self):
        # 2026-10-30：pose 页面内联了 390 KB 从未被读取的 flat 数组
        for s in SITES:
            h = read(f"sites/{s}/index.html")
            js = "".join(scripts(h))
            for key in page_db(h):
                self.assertRegex(js, r"DB\." + re.escape(key) + r"\b", f"{s} 的 DB.{key} 内联了但页面没用")

    def test_page_size_budget(self):
        for s in SITES:
            size = os.path.getsize(os.path.join(ROOT, f"sites/{s}/index.html"))
            self.assertLess(size, 450 * 1024, f"{s}/index.html {size // 1024} KB，超出 450 KB")

    def test_styles_page_matches_code_list(self):
        """风格码库页面与 data/styles.json 必须同口径。

        页面是生成物（scripts/build_styles_page.py），码表以 `var DB=` 内嵌。
        少一个码等于发布一个看不见的残缺页，所以两边做集合比对。
        """
        sid = "midjourney-explore"
        data = json.loads(read(f"sites/{sid}/data/styles.json"))
        h = read(f"sites/{sid}/styles/index.html")
        m = re.search(r"var DB=(\{.*?\});", h, re.S)
        self.assertIsNotNone(m, "页面里找不到内嵌的 DB= 数据块")
        db = json.loads(m.group(1))
        want = {str(it["code"]) for it in data["items"]}
        self.assertEqual({str(c) for c, _ in db["codes"]}, want,
                         "页面里的码与 data/styles.json 不一致，重跑 scripts/build_styles_page.py")
        self.assertTrue(db.get("latest"), "页面缺 latest，「只看最近新增」会失效")

    def test_collection_switch_loads_facets(self):
        # 2026-11-03：带「视图」的集合（midjourney-explore）走 selectView 分支，
        # 那条路只刷网格不取分面，左栏永远停在「选一个集合后显示它自己的分面」。
        # 分面只跟集合有关、与视图无关，所以加载点必须在 selectCollection 里。
        h = read("index/web/index.html")
        body = h.split("function selectCollection")[1].split("\nfunction ")[0]
        self.assertIn("loadFacets()", body,
                      "selectCollection 必须重取分面，否则带视图的集合左栏是空的")

    def test_inline_js_syntax(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("没有 node")
        for rel in PAGES:
            for i, js in enumerate(scripts(read(rel))):
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
                    f.write(js)
                try:
                    r = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, f"{rel} 第 {i + 1} 段脚本语法错误:\n{r.stderr[-800:]}")
                finally:
                    os.remove(f.name)


class Landing(unittest.TestCase):
    """shared/landing.py 生成的静态落地页"""

    def setUp(self):
        self.pages = landing_pages()

    def site_pages(self, sid):
        return [p for p in self.pages if p.startswith(f"sites/{sid}/")]

    def test_every_site_has_landing_pages(self):
        for s in SITES:
            self.assertTrue(self.site_pages(s), f"{s} 没有落地页")

    def test_head_and_body_basics(self):
        titles = collections.Counter()
        for rel in self.pages:
            h = read(rel)
            sid, path = rel.split("/")[1], "/".join(rel.split("/")[2:-1])
            t = re.search(r"<title>(.*?)</title>", h)
            self.assertTrue(t and 10 <= len(t.group(1)) <= 80, f"{rel} title 缺失或长度异常")
            titles[t.group(1)] += 1
            d = re.search(r'name="description" content="([^"]*)"', h)
            self.assertTrue(d and 40 <= len(d.group(1)) <= 220, f"{rel} description 缺失或长度异常")
            self.assertIn(f'rel="canonical" href="https://example.com/{sid}/{path}/"', h, rel)
            self.assertEqual(h.count("<h1>"), 1, f"{rel} 应有且只有一个 h1")
            for img in re.findall(r"<img[^>]*>", h):
                self.assertRegex(img, r'alt="[^"]{6,}"', f"{rel} 有缺 alt 的图片")
        self.assertEqual([t for t, n in titles.items() if n > 1], [], "落地页 title 重复")

    def test_links_resolve(self):
        # 页面里的相对链接都要指向仓库里存在的页面；sites/ 之上就是 photoai.life 根，对应仓库的 hub/
        problems = []
        sites_dir = os.path.normpath(os.path.join(ROOT, "sites"))
        for rel in self.pages:
            base = os.path.dirname(os.path.join(ROOT, rel))
            for href in re.findall(r'href="([^"#]+)', read(rel)):
                if re.match(r"[a-z]+:", href):
                    continue
                if href.startswith("/"):
                    # 站点根的绝对路径（图标等）：photoai.life 根对应仓库的 hub/
                    target = os.path.join(ROOT, "hub", html.unescape(href).lstrip("/"))
                    if not os.path.exists(target):
                        problems.append(f"{rel} → {href}")
                    continue
                target = os.path.normpath(os.path.join(base, html.unescape(href)))
                if target == sites_dir:
                    target = os.path.join(ROOT, "hub")
                if href.endswith("/"):
                    target = os.path.join(target, "index.html")
                if not os.path.exists(target):
                    problems.append(f"{rel} → {href}")
        self.assertEqual(problems, [])

    def test_thumbs_are_in_manifest(self):
        for s in SITES:
            thumbs = {r["thumb_path"] for r in json.loads(read(f"sites/{s}/manifest.json"))}
            for rel in self.site_pages(s):
                up = "../" * (rel.count("/") - 2)
                for src in re.findall(r'<img src="([^"]+)"', read(rel)):
                    self.assertTrue(src.startswith(up), f"{rel} 图片路径层级不对: {src}")
                    self.assertIn(src[len(up):], thumbs, f"{rel} 引用了不在 manifest 的图: {src}")

    def test_only_thumbnails_exposed(self):
        # 落地页只用缩略图，不暴露中图和原图（三站禁止再分发）
        for rel in self.pages:
            self.assertFalse(re.findall(r'<img src="[^"]*/(mid|img|png)/', read(rel)), rel)

    def test_gallery_hash_params_known(self):
        # 「在画廊中查看」带的 #参数必须是画廊能识别的
        # 各站的分面维度不同：cat（分类）、tag（标签）、series（系列）、
        # sec（分区）、hair（发型）、ver（版本）、asp（宽高比）
        for rel in self.pages:
            for hsh in re.findall(r'class="cta" href="[^"]*#([^"]+)"', read(rel)):
                for kv in html.unescape(hsh).split("&"):
                    self.assertIn(kv.split("=")[0],
                                  {"cat", "tag", "series", "sec", "hair", "ver", "asp"}, f"{rel}: {hsh}")

    def test_adult_series_not_expanded(self):
        # 姿势两站：双人系列不生成落地页，性感系与上半身不展开到分类
        for s in ("pose", "pose-depth"):
            pages = self.site_pages(s)
            self.assertFalse([p for p in pages if "2人絡み" in p], f"{s} 不应有双人系列落地页")
            for series in ("全身1人・セクシー系", "上半身1人"):
                deep = [p for p in pages if f"/series/{series}/" in p and not p.endswith(f"/series/{series}/index.html")]
                self.assertFalse(deep, f"{s} 的 {series} 不应展开到分类页")

    def test_shisei_suggestive(self):
        # Shisei：上游标为 suggestive 的姿势在画廊里带模糊标记，不出现在任何落地页
        if "shisei" not in SITES:
            self.skipTest("没有 shisei")
        rows = json.loads(read("sites/shisei/manifest.json"))
        sugg = {r["编号"] for r in rows if r["rating"] == "suggestive"}
        db = page_db(read("sites/shisei/index.html"))
        self.assertEqual({p["p"] for p in db["poses"] if p.get("r")}, sugg)
        self.assertIn("const BLUR = true;", read("sites/shisei/index.html"))
        for rel in self.site_pages("shisei"):
            shown = set(re.findall(r"<figcaption>([A-Z]\d+) ", read(rel)))
            self.assertFalse(shown & sugg, f"{rel} 出现了 suggestive 姿势: {sorted(shown & sugg)[:5]}")
            self.assertFalse(re.search(r"ふたり|セクシー", rel), f"{rel} 不应为双人或性感系列生成落地页")
        for s in ("pose", "pose-depth"):
            self.assertIn("const BLUR = false;", read(f"sites/{s}/index.html"))

    def test_sitemaps_cover_landing_pages(self):
        root_sm = read("hub/sitemap.xml")
        for s in SITES:
            sm = read(f"sites/{s}/sitemap.xml")
            for rel in self.site_pages(s):
                url = "https://example.com/" + rel[len("sites/"):-len("index.html")]
                self.assertIn(url, sm, f"{s}/sitemap.xml 缺 {url}")
                self.assertIn(url, root_sm, f"根 sitemap 缺 {url}")

    def test_llms_txt(self):
        t = read("hub/llms.txt")
        self.assertTrue(t.startswith("# photoai.life\n"))
        for s in SITES:
            self.assertIn(f"https://example.com/{s}/", t)
        self.assertIn("CC0", t)
        self.assertIn("禁止再分发", t)

    def test_static_intro_on_gallery_pages(self):
        # 主画廊页在不执行 JS 时也要有可读内容和 FAQ 结构化数据
        for rel in ["hub/index.html"] + [f"sites/{s}/index.html" for s in SITES]:
            h = read(rel)
            body = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
            self.assertGreater(len(text), 500, f"{rel} 去掉 JS 后可读文字太少")
            self.assertIn('"@type":"FAQPage"', h, f"{rel} 缺 FAQPage")
            # 介绍卡片：FAQ 收在折叠里，不直接铺满页面底部
            self.assertEqual(h.count('class="seo-intro"'), 1, rel)
            self.assertIn('<details class="seo-more">', h, rel)

    def test_icons(self):
        # 入口页与落地页引用根级图标，文件都在 hub/ 里且会被 release.py 发布
        icons = ["favicon.ico", "favicon.svg", "apple-touch-icon.png"]
        for fn in icons + ["icon-512.png"]:
            self.assertGreater(os.path.getsize(os.path.join(ROOT, "hub", fn)), 300, fn)
        rel_src = read("tools/release.py")
        for fn in icons:
            self.assertIn(f'"{fn}"', rel_src, f"release.py 没发布 {fn}")
        for rel in ["hub/index.html"] + self.pages:
            h = read(rel)
            for fn in icons:
                self.assertIn(f'href="/{fn}"', h, f"{rel} 没引用 {fn}")


class Manifests(unittest.TestCase):

    def test_tier_fields_present(self):
        # tools/fetch.py / verify.py 只靠 <tier>_url / <tier>_path 工作
        for s in CFG["sites"]:
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))
            self.assertTrue(rows, s["id"])
            for t in s["tiers"]:
                for k in (t + "_url", t + "_path"):
                    bad = [r.get("id") for r in rows if not r.get(k)]
                    self.assertEqual(bad, [], f"{s['id']} 缺 {k}")

    def test_paths_portable_and_unique(self):
        for s in CFG["sites"]:
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))
            for t in s["tiers"]:
                paths = [r[t + "_path"] for r in rows]
                self.assertFalse([p for p in paths if "\\" in p or p.startswith("/") or ".." in p],
                                 f"{s['id']} {t} 有反斜杠、绝对路径或 ..")
                self.assertEqual(len(paths), len(set(paths)), f"{s['id']} {t} 路径重复")

    def test_urls_point_to_source(self):
        # 图片地址要在原站下；图片另有出处的站点（如 Shisei 用上游 GitHub 固定标签）写 imageBase。
        # 图片分散在多个 CDN 域名的站点（如 PromptHero 衍生图在 img、原图在 cdn）写 imageBases 列表。
        for s in CFG["sites"]:
            bases = s.get("imageBases") or [s.get("imageBase", s["source"])]
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))
            for t in s["tiers"]:
                off = [r[t + "_url"] for r in rows
                       if not any(r[t + "_url"].startswith(b) for b in bases)]
                self.assertEqual(off, [], f"{s['id']} {t} 的 URL 不在 {bases} 下")

    def test_image_dirs_match_paths(self):
        # release.py 只硬链接 imageDirs；manifest 里的图片都应落在这些目录里
        for s in CFG["sites"]:
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))
            dirs = set(s["imageDirs"])
            for t in s["tiers"]:
                tops = {r[t + "_path"].split("/")[0] for r in rows}
                self.assertTrue(tops <= dirs, f"{s['id']} {t} 用到 {tops - dirs}，不在 imageDirs 里")

    def test_cover_in_manifest(self):
        for s in CFG["sites"]:
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))
            thumbs = {r["thumb_path"] for r in rows}
            self.assertIn(s["cover"], thumbs, f"{s['id']} 的封面 {s['cover']} 不在 manifest 里")


class ImagePolicy(unittest.TestCase):
    """取图策略声明的闸门。

    策略声明在 sites.json 里（每站一份，按档位给出），决定这个档位的图片
    地址从哪来：站内相对路径、上游地址、还是「先本地、失败再回落上游」。

    这里守的是**声明本身**：取值合法、档位齐全、读取器与清单一致。
    声明有没有真的传导到构建产物，由 Pages 层的断言负责。
    """

    @staticmethod
    def policy_mods():
        from image_policy import MODES
        return MODES

    def test_every_site_declares_policy_for_every_tier(self):
        for s in CFG["sites"]:
            pol = s.get("imagePolicy")
            self.assertTrue(pol, f"{s['id']} 没有声明 imagePolicy")
            missing = [t for t in s["tiers"] if t not in pol]
            self.assertEqual(missing, [], f"{s['id']} 缺这些档位的取图策略：{missing}")

    def test_policy_values_are_known_modes(self):
        mods = self.policy_mods()
        for s in CFG["sites"]:
            for tier, mode in (s.get("imagePolicy") or {}).items():
                self.assertIn(mode, mods,
                              f"{s['id']} 的 imagePolicy.{tier} 取值非法：{mode}")

    def test_reader_returns_declared_mode(self):
        # 读取器与清单必须一致：清单怎么写就读出什么
        from image_policy import tier_mode
        for s in CFG["sites"]:
            for tier in s["tiers"]:
                self.assertEqual(tier_mode(s, tier), s["imagePolicy"][tier],
                                 f"{s['id']} 的 {tier} 档：读取器读出的策略与清单不符")

    def test_reader_defaults_to_local_first(self):
        # 未声明的档位按「本地优先」处理，即与改造前的行为一致
        from image_policy import DEFAULT, tier_mode
        for s in CFG["sites"]:
            self.assertEqual(tier_mode(s, "不存在的档位"), DEFAULT)

    def test_every_tier_has_an_upstream_url(self):
        # 策略要用上游地址回落，前提是 manifest 里那个档位真有上游地址
        for s in CFG["sites"]:
            if s["id"] in SKIP_BUILD:
                continue
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))
            for tier in s["tiers"]:
                key = tier + "_url"
                empty = [r.get("id") for r in rows if not r.get(key)]
                self.assertEqual(empty, [], f"{s['id']} 的 {tier} 档缺 {key}")


class ImageArtifacts(unittest.TestCase):
    """取图策略在构建产物里的传导闸门。

    清单里声明了「本地优先」或「直连上游」的档位，产物里就必须带上该档位的
    上游地址——否则声明是句空话：页面既没有回落目标，也不知道该直连哪里。

    这一层此前完全没有闸门：清单对所有以 url 结尾的字段一律按「可忽略字段」
    处理，字段名拼错也不报「未映射」，页面照常构建、照常运行，只是图片地址
    是错的——属于沉默失败。
    """

    SAMPLE = 5

    @staticmethod
    def artifacts(sid):
        """该站产物的全部文本：页面 + 数据分片。"""
        parts = []
        page = f"sites/{sid}/index.html"
        if os.path.exists(os.path.join(ROOT, page)):
            parts.append(read(page))
        data_dir = os.path.join(ROOT, "sites", sid, "data")
        if os.path.isdir(data_dir):
            for name in sorted(os.listdir(data_dir)):
                if name.startswith("gallery") and name.endswith(".js"):
                    with open(os.path.join(data_dir, name), encoding="utf-8") as f:
                        parts.append(f.read())
        return "\n".join(parts)

    def test_declared_tiers_emit_their_upstream_address(self):
        from image_policy import LOCAL_ONLY, tier_mode
        for s in CFG["sites"]:
            if s["id"] in SKIP_BUILD:
                continue
            art = self.artifacts(s["id"])
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))
            for tier in s["tiers"]:
                if tier_mode(s, tier) == LOCAL_ONLY:
                    continue        # 仅本地：不需要上游地址
                for r in rows[:self.SAMPLE]:
                    url = r.get(tier + "_url")
                    self.assertTrue(url, f"{s['id']} 的 {tier} 档缺上游地址")
                    self.assertTrue(url in art,
                                    f"{s['id']} 的 {tier} 档声明了 "
                                    f"{tier_mode(s, tier)}，但产物里没有它的上游地址")

    def test_local_only_tier_has_no_upstream_address(self):
        """声明仅本地的档位，产物里不该带它的上游地址。

        仅本地 = 没有回落目标（上游不可直连，或这一档本来就不从上游取）。
        产物里若还带着上游地址，说明声明与实现不一致：页面要么会误回落，
        要么是白占体积。
        """
        from image_policy import LOCAL_ONLY, tier_mode
        for s in CFG["sites"]:
            if s["id"] in SKIP_BUILD:
                continue
            art = self.artifacts(s["id"])
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))
            for tier in s["tiers"]:
                if tier_mode(s, tier) != LOCAL_ONLY:
                    continue
                for r in rows[:self.SAMPLE]:
                    url = r.get(tier + "_url")
                    if not url:
                        continue
                    self.assertNotIn(url, art,
                                     f"{s['id']} 的 {tier} 档声明仅本地，"
                                     f"但产物里带着它的上游地址")

    def test_online_tier_keeps_the_local_path(self):
        """直连上游的档位，站内相对路径仍要留在产物里。

        中图等按路径推导的规则依赖它——展示地址换成上游 URL 之后，
        推导就没有输入了。
        """
        from image_policy import ONLINE, tier_mode
        for s in CFG["sites"]:
            if s["id"] in SKIP_BUILD:
                continue
            art = self.artifacts(s["id"])
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))
            for tier in s["tiers"]:
                if tier_mode(s, tier) != ONLINE:
                    continue
                for r in rows[:self.SAMPLE]:
                    self.assertTrue(r.get(tier + "_path") in art,
                                    f"{s['id']} 的 {tier} 档直连上游，"
                                    f"但产物里没有保留站内相对路径（推导会失去输入）")


class IndexMapping(unittest.TestCase):
    """索引侧（素材管理器 WebUI）的接线闸门。

    背景：sites.json 里加一个站，不等于它进了 WebUI。
    catalog.SOURCES 决定「索引哪些站、字段怎么映射」，
    漏了这一步时站点页面一切正常，但 WebUI 里查不到这条素材——
    而这一层此前没有任何测试覆盖，CI 照样全绿。
    """

    @staticmethod
    def sources():
        sys.path.insert(0, os.path.join(ROOT, "index"))
        import catalog
        return catalog.SOURCES

    def test_no_duplicate_source_keys(self):
        """SOURCES 字面量里不能有重复键。

        Python 的字典字面量遇到重复键会**静默取最后一个**——前一份配置看着还在，
        实际完全不生效。改前一份却不报错，是最难查的一类配置漂移。
        """
        import ast
        path = os.path.join(ROOT, "index", "catalog.py")
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if getattr(node.targets[0], "id", "") != "SOURCES":
                continue
            found = True
            keys = [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
            dup = sorted({k for k in keys if keys.count(k) > 1})
            self.assertEqual(dup, [], f"catalog.SOURCES 里有重复键 {dup}："
                                     f"字典字面量会静默取最后一个，前一份配置不生效")
        self.assertTrue(found, "catalog.py 里找不到 SOURCES 字面量")

    def test_every_site_has_a_source_mapping(self):
        # sites.json ↔ catalog.SOURCES 必须双向一一对应：
        # 少一边 = 站点建好了却没进索引（或索引里有个已删的站）。
        src = self.sources()
        missing = [s for s in SITES if s not in src]
        self.assertEqual(missing, [], "这些站没进 catalog.SOURCES，WebUI 里查不到")
        extra = [s for s in src if s not in SITES]
        self.assertEqual(extra, [], "catalog.SOURCES 里有 sites.json 没有的站")

    def test_midjourney_facet_declaration(self):
        """探索榜的分面：宽高比 / 风格参考已撤，「类别」是派生的存在性分面。

        宽高比 29 种、长尾每个只有 4 张；风格参考一码一条，是标识不是分类。
        两者做左栏分面噪声大于信息，改由「类别 / 有 sref 码」筛「真的能复制出一串
        --sref」的作业（hasStyleRef=1 但没有码的图片型风格参考不算）。
        """
        sys.path.insert(0, os.path.join(ROOT, "index"))
        import catalog
        cfg = catalog.SOURCES["midjourney-explore"]
        self.assertEqual(set(cfg["facets"]), {"版本", "批次"})
        self.assertEqual(cfg.get("derived_facets"), {"类别": [("sref", "有 sref 码")]})
        self.assertIn("aspect", cfg.get("ignored") or [],
                      "宽高比不进索引，必须在 ignored 里声明，否则报未映射字段")

    def test_midjourney_derived_facet_fires_only_when_sref_present(self):
        sys.path.insert(0, os.path.join(ROOT, "index"))
        import catalog
        cfg = catalog.SOURCES["midjourney-explore"]
        rows = json.loads(read(cfg["manifest"]))
        with_sref = [r for r in rows if (r.get("sref") or "").strip()]
        hits = [r for r in rows if catalog.derived_facet_pairs(cfg, r)]
        self.assertTrue(with_sref, "manifest 里一条带 sref 码的都没有，测试失去意义")
        self.assertEqual([r["id"] for r in hits], [r["id"] for r in with_sref])

    def test_midjourney_manifest_fields_stay_mapped(self):
        """撤分面不能把字段丢成「未映射」：aspect 归 ignored，sref 归派生分面。"""
        sys.path.insert(0, os.path.join(ROOT, "index"))
        import catalog
        cfg = catalog.SOURCES["midjourney-explore"]
        seen = set()
        for rec in json.loads(read(cfg["manifest"]))[:200]:
            seen.update(rec.keys())
        self.assertEqual(catalog.unmapped_report("midjourney-explore", seen, cfg), [])

    def test_views_declare_top_level_options(self):
        """集合内视图（分层）的配置约定。

        视图是「集合内的顶层分层」——如 midjourney-explore 的 图像/视频。
        约定：
          · 至少两个（一个视图等于没分层）
          · 键 k 不重复、都要有展示名 name
          · facet 是命名空间（存在性过滤），要么是该站 facets 里声明过的，
            要么是 catalog.RESERVED_NS 里的预留命名空间（如尚未采集的视频）
        """
        src = self.sources()
        for sid, cfg in src.items():
            views = cfg.get("views")
            if not views:
                continue
            self.assertGreaterEqual(len(views), 2, f"{sid} 声明了视图但少于 2 个")
            keys = [v["k"] for v in views]
            self.assertEqual(len(keys), len(set(keys)), f"{sid} 的视图键重复：{keys}")
            declared = set(cfg.get("facets", {}).keys())
            for v in views:
                self.assertTrue(v.get("name"), f"{sid} 的视图 {v.get('k')} 缺展示名")
                ns = v.get("facet")
                if not ns:
                    continue
                import catalog
                ok = ns in declared or ns in catalog.RESERVED_NS
                self.assertTrue(ok, f"{sid} 的视图 {v['k']} 用了既没声明也没预留的命名空间 {ns!r}")

    def test_midjourney_explore_has_two_views(self):
        """Midjourney 探索榜的视图：图像 / 视频。

        「风格」视图已于 2026-11-03 删除：原站 Styles 是独立内容类型
        （sref 码 + 三张语义图，无 prompt / 无作者），与集合里「挂了 sref 的作业」
        同名不同义。风格实体改由站点 styles/ 页承载，不进 WebUI 集合。
        这个断言是防回归——防止有人又用 facet="风格参考" 把它近似回来。
        """
        cfg = self.sources().get("midjourney-explore")
        self.assertIsNotNone(cfg, "catalog.SOURCES 里没有 midjourney-explore")
        views = {v["k"]: v for v in cfg.get("views") or []}
        for k in ("images", "videos"):
            self.assertIn(k, views, f"midjourney-explore 缺少视图 {k}")
        self.assertNotIn("styles", views,
                         "「风格」视图已弃用：原站 Styles 与「挂了 sref 的作业」不是一回事，"
                         "不要再用 facet=风格参考 近似")
        self.assertIsNone(views["images"]["facet"], "图像视图应覆盖整个集合")

    def test_grouped_sites_declare_group_by(self):
        """多图站必须声明聚合键（或显式声明刻意不聚合），否则同一提示词的多张图会散成多条素材。

        判据不依赖具体站：扫描 manifest 的字段，若某个字段把记录近乎**均分成等大小**的组
        （组大小 ≥2 且覆盖 ≥80% 的记录，且该字段的值域够宽——去重值数 ≥ 记录数的 5%），
        就说明这站存在「一条内容多张图」。此时必须二选一：
          · 声明 group_by（按该字段聚合成一条素材，多图挂成同一灯箱）
          · 声明 split_by_design（记录刻意不聚合的理由，例如同姿势的 5 个视角）
        否则同一提示词的多张图会散成多条独立素材，WebUI 灯箱里翻不到一起。
        """
        src = self.sources()
        for sid in SITES:
            cfg = src.get(sid)
            if not cfg:
                continue
            path = os.path.join(ROOT, cfg["manifest"])
            if not os.path.exists(path):
                continue
            rows = json.loads(read(cfg["manifest"]))
            if len(rows) < 4:
                continue
            cands = self._group_candidates(cfg, rows)
            if not cands:
                continue
            self.assertTrue(
                cfg.get("group_by") or cfg.get("split_by_design"),
                f"{sid} 的 manifest 存在把记录均分成等大小组的字段 {cands}，"
                f"说明这站是一条内容多张图；必须在 catalog.SOURCES 里声明 "
                f"group_by（聚合成一条素材，多图同灯箱），"
                f"或声明 split_by_design 并写明刻意不聚合的理由"
            )
            if cfg.get("group_by"):
                self.assertIn(cfg["group_by"], [c[0] for c in cands],
                              f"{sid} 的 group_by={cfg['group_by']} 不在候选分组字段 {cands} 里")

    @staticmethod
    def _group_candidates(cfg, rows):
        """找出「把记录均分成等大小组」的字段：返回 [(字段, 组大小, 覆盖率, 去重值数)]。

        排除：id / slug / 各种 *_url *_path（天然唯一）、已声明的分面与内容字段、
        布尔标记、值域过窄的字段（计数器与像素尺寸会偶然重复，不是分组键）。
        """
        n = len(rows)
        skip = {"id", "slug"} | {k for k in rows[0] if k.endswith("_url") or k.endswith("_path")}
        skip |= set(cfg.get("facets", {}).values())
        for k in ("prompt", "keywords", "title", "title_alt"):
            if cfg.get(k):
                skip.add(cfg[k])
        counter = collections.Counter()
        for r in rows:
            for k, v in r.items():
                if k in skip or isinstance(v, bool) or "url" in k.lower():
                    continue
                if not isinstance(v, (str, int, float)) or v in ("", None):
                    continue
                counter[(k, v)] += 1
        # per[k][组大小] = 该大小的组一共覆盖了多少条记录
        per = collections.defaultdict(collections.Counter)
        for (k, _v), c in counter.items():
            if c >= 2:
                per[k][c] += c
        out = []
        for k, dist in per.items():
            size, cover = max(dist.items(), key=lambda kv: kv[1])
            distinct = sum(1 for kk, _ in counter if kk == k)
            if size >= 2 and cover >= 0.8 * n and distinct >= 0.05 * n:
                out.append((k, size, round(cover / n, 2)))
        return sorted(out)

    def test_group_by_field_exists(self):
        """声明了 group_by 就必须在 manifest 里真有这个字段，且分组数合理。"""
        src = self.sources()
        for sid in SITES:
            cfg = src.get(sid)
            if not cfg or not cfg.get("group_by"):
                continue
            path = os.path.join(ROOT, cfg["manifest"])
            if not os.path.exists(path):
                continue
            rows = json.loads(read(cfg["manifest"]))
            key = cfg["group_by"]
            self.assertTrue(all(key in r for r in rows),
                            f"{sid} 声明了 group_by={key}，但 manifest 里没有这个字段")
            groups = {r.get(key) for r in rows}
            self.assertLess(len(groups), len(rows),
                            f"{sid} 声明了 group_by={key}，但每条记录都是独立分组（等于没聚合）")
            self.assertTrue(cfg.get("group_order"),
                            f"{sid} 声明了 group_by，必须同时声明 group_order（组内顺序 = 灯箱翻页顺序）")

    def test_prompt_field_non_empty(self):
        """声明了 prompt 映射的站，manifest 里该字段必须存在且非空。"""
        src = self.sources()
        for sid in SITES:
            cfg = src.get(sid)
            if not cfg or not cfg.get("prompt"):
                continue
            path = os.path.join(ROOT, cfg["manifest"])
            if not os.path.exists(path):
                continue
            rows = json.loads(read(cfg["manifest"]))
            key = cfg["prompt"]
            empty = [r.get("id") for r in rows if not str(r.get(key) or "").strip()]
            self.assertEqual(empty, [], f"{sid} 声明了 prompt={key}，但这些记录该字段是空的")


class MidRule(unittest.TestCase):
    """中图路径规则在 Python（tools/mid.py）和页面 JS（midOf）各写了一份，必须一致。"""

    def test_python_and_js_agree(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("没有 node")
        for s in CFG["sites"]:
            if "mid" not in s["imageDirs"]:
                continue
            h = read(f"sites/{s['id']}/index.html")
            m = re.search(r"const midOf = .*?;", h)
            if not m:
                # 数据里已直接给出 mid 档（m 字段）就不需要在 JS 复算路径规则，
                # 没有第二份实现可比对。midjourney-explore 整改后即属此类。
                data_rel = f"sites/{s['id']}/data/gallery.js"
                self.assertTrue(os.path.exists(os.path.join(ROOT, data_rel)),
                                f"{s['id']} 页面里没有 midOf，也没有 gallery.js")
                raw = read(data_rel)
                mm = re.search(r"JSON\.parse\((.*)\);\s*$", raw, re.S)
                self.assertTrue(mm, f"{s['id']} gallery.js 不是预期的 JSON.parse 形式")
                obj = json.loads(json.loads(mm.group(1)))
                self.assertIn("m", obj["items"][0], f"{s['id']} 数据未提供 mid 档")
                continue
            self.assertIsNotNone(m, f"{s['id']} 页面里没有 midOf")
            rows = json.loads(read(f"sites/{s['id']}/manifest.json"))[:50]
            src = [r["full_path"] for r in rows]
            js = m.group(0) + "\nconsole.log(JSON.stringify(" + json.dumps(src, ensure_ascii=False) + ".map(midOf)));"
            r = subprocess.run([node, "-e", js], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), [mid_rel(p) for p in src], s["id"])


class Docs(unittest.TestCase):

    DOCS = ["README.md", "README_en.md", "README_ja.md", "docs/ADDING_A_SITE.md", "deploy/DEPLOY.md"] + \
           [f"sites/{s}/{f}" for s in SITES for f in ("README.md", "NOTICE.md")]

    @staticmethod
    def slug(h):
        h = re.sub(r"`|\*", "", h.strip().lower())
        return re.sub(r"[^\w\- ]", "", h).replace(" ", "-")

    def test_relative_links_and_anchors(self):
        problems = []
        for rel in self.DOCS:
            text = read(rel)
            base = os.path.dirname(rel)
            body = re.sub(r"```.*?```", "", text, flags=re.S)       # 代码块里的不算链接
            heads = {self.slug(h) for h in re.findall(r"^#{1,6} (.+)$", body, re.M)}
            for target in re.findall(r"\]\(([^)\s]+)\)", body):
                if re.match(r"[a-z]+:", target):
                    continue
                path, _, anchor = target.partition("#")
                if path:
                    if not os.path.exists(os.path.normpath(os.path.join(ROOT, base, path))):
                        problems.append(f"{rel}: 链接不存在 {target}")
                elif anchor and anchor not in heads:
                    problems.append(f"{rel}: 锚点不存在 #{anchor}")
        self.assertEqual(problems, [])

    def test_no_removed_scripts_referenced(self):
        gone = ["scripts/download.py", "scripts/verify.py", "build_dist.sh"]
        hits = [f"{rel}: {g}" for rel in self.DOCS for g in gone if g in read(rel)]
        self.assertEqual(hits, [])


class GitIgnore(unittest.TestCase):
    """prompts 站的大体积中间数据一律不入库，清单与小索引必须入库。

    这条闸门防的是「手滑 git add -f」或者有人顺手删掉忽略规则——
    那 220 MB 一旦进了历史就删不干净了。
    """

    def ignored(self, rel):
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode not in (0, 1):
            self.skipTest("当前目录不是 git 仓库，或没有 git")
        return r.returncode == 0

    def test_large_intermediate_data_is_ignored(self):
        for rel in ("sites/prompts/data/prompts_gpt2.json",
                    "sites/prompts/data/prompts_nbpro.json",
                    "sites/prompts/data/gallery_gpt2.js",
                    "sites/prompts/data/gallery_nbpro.js",
                    "sites/prompts/data/dims.json",
                    "sites/prompts/data/gpt2_id2cats.json",
                    "sites/prompts/data/nbpro_site_meta.json"):
            self.assertTrue(self.ignored(rel), f"{rel} 应当被 .gitignore 排除")

    def test_manifest_and_shard_index_stay_tracked(self):
        # manifest 是 fetch.py 与 tests 的图片清单；gallery.js 是分片索引（275 B）
        for rel in ("sites/prompts/manifest.json",
                    "sites/prompts/data/gallery.js",
                    "sites/prompts/data/landing.json"):
            self.assertFalse(self.ignored(rel), f"{rel} 必须入库")


class UserAssets(unittest.TestCase):
    """自制图覆盖层的契约（sites/prompts/data/user_assets.json + userimg/）。

    覆盖层是把「素材管理器里挂的图」送进静态站的唯一通道，一旦结构跑偏
    （路径写进 img/、漏了 own 标记），页面上会出现来源不明的图或者静默丢图。
    """

    PATH = os.path.join(ROOT, "sites/prompts/data/user_assets.json")

    def load(self):
        if not os.path.exists(self.PATH):
            self.skipTest("没有 user_assets.json（该站可以完全没有自制图）")
        with open(self.PATH, encoding="utf-8") as f:
            return json.load(f)

    def test_shape(self):
        data = self.load()
        self.assertEqual(data.get("version"), 1)
        items = data.get("items")
        self.assertIsInstance(items, dict)
        for gid, files in items.items():
            self.assertIsInstance(files, list, gid)
            for f in files:
                for key in ("name", "file", "thumb", "w", "h", "own"):
                    self.assertIn(key, f, f"{gid} 缺字段 {key}")

    def test_paths_stay_in_userimg(self):
        """自制图必须落在 userimg/，不能混进上游的 img/<key>/。

        img/<key>/ 的目录名就是模型分片键，混进去会被当成新模型；
        fetch.py 也只认 manifest 里的文件，多出来的会被当成噪声。
        """
        for gid, files in self.load().get("items", {}).items():
            for f in files:
                self.assertTrue(f["file"].startswith("userimg/"),
                                f"{gid} 的图不在 userimg/：{f['file']}")
                self.assertTrue(f["thumb"].startswith("userimg/thumbs/"),
                                f"{gid} 的缩略图不在 userimg/thumbs/：{f['thumb']}")
                self.assertEqual(f["own"], 1, f"{gid} 缺 own 标记")

    def test_images_exist(self):
        missing = []
        for gid, files in self.load().get("items", {}).items():
            for f in files:
                for rel in (f["file"], f["thumb"]):
                    if not os.path.exists(os.path.join(ROOT, "sites/prompts", rel)):
                        missing.append(f"{gid}: {rel}")
        self.assertEqual(missing, [], "覆盖层引用的图不存在，重跑 sync_user_assets.py")

    def test_userimg_is_tracked(self):
        rel = "sites/prompts/userimg/README.md"
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode not in (0, 1):
            self.skipTest("当前目录不是 git 仓库，或没有 git")
        self.assertNotEqual(r.returncode, 0,
                            "userimg/ 必须入库：自己的图无法从上游重下")


class MjStrategy(unittest.TestCase):
    """Midjourney 探索榜数据策略整改的回归测试（见 sites/midjourney-explore/docs/TICKETS.md）"""

    def _mod(self):
        import importlib.util
        path = os.path.join(ROOT, "sites", "midjourney-explore", "scripts", "build_gallery.py")
        if not os.path.exists(path):
            self.skipTest("站点脚本不存在")
        spec = importlib.util.spec_from_file_location("mj_build_gallery", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_manifest_stats_counts(self):
        """统计只从 manifest 现算，不依赖配置文件里的写死值。"""
        mod = self._mod()
        rows = [
            {"jobId": "a", "username": "u1", "aspect": "1:1", "batch": "2026-11-01"},
            {"jobId": "a", "username": "u1", "aspect": "1:1", "batch": "2026-11-01"},
            {"jobId": "b", "username": "u2", "aspect": "2:3", "batch": "2026-11-02"},
        ]
        st = mod.manifest_stats(rows)
        self.assertEqual(st["n_images"], 3)
        self.assertEqual(st["n_jobs"], 2)
        self.assertEqual(st["n_authors"], 2)
        self.assertEqual(st["n_aspects"], 2)
        self.assertEqual(st["n_batches"], 2)

    def test_with_counts_is_pure(self):
        """填文案数量不得就地改全局 CONFIG；且各语种占位符都要填掉。"""
        mod = self._mod()
        before_title = mod.CONFIG["title"]
        before_sub = mod.CONFIG["ui"]["zh"]["sub1"]
        out = mod.with_counts(mod.CONFIG, {"n_images": 1, "n_jobs": 2,
                                           "n_authors": 3, "n_aspects": 4})
        self.assertEqual(mod.CONFIG["title"], before_title, "with_counts 不得改动 CONFIG")
        self.assertEqual(mod.CONFIG["ui"]["zh"]["sub1"], before_sub,
                         "with_counts 不得改动 CONFIG['ui']")
        self.assertIn("{n_", mod.CONFIG["title"], "原件应保持模板形态")
        self.assertNotIn("{n_", out["title"], "SEO 文案占位符未填")
        self.assertNotIn("{n_", out["ui"]["zh"]["sub1"], "UI 中文占位符未填")
        self.assertNotIn("{n_", out["ui"]["ja"]["sub1"], "UI 日文占位符未填")

    def test_no_config_rewrite(self):
        """构建脚本不得回写 sites.json —— 配置是输入，不是产物。"""
        mod = self._mod()
        self.assertFalse(hasattr(mod, "update_sites_json"),
                         "构建不得回写 sites.json")

    def test_site_uses_single_shard(self):
        """站点只应有单一 data/gallery.js，不再按采集日切分片。"""
        data_dir = os.path.join(ROOT, "sites", "midjourney-explore", "data")
        if not os.path.exists(os.path.join(data_dir, "gallery.js")):
            self.skipTest("站点尚未构建")
        extras = [f for f in os.listdir(data_dir)
                  if f.startswith("gallery_") and f.endswith(".js")]
        self.assertEqual(extras, [], "只应有单一 gallery.js，不应再有按批次分片")
        payload = read("sites/midjourney-explore/data/gallery.js")
        # 文件形如 window.__GALLERY__=JSON.parse("<json 字符串>"); —— 双层编码
        m = re.search(r"JSON\.parse\((.*)\);\s*$", payload, re.S)
        self.assertTrue(m, "gallery.js 不是预期的 JSON.parse 形式")
        obj = json.loads(json.loads(m.group(1)))
        self.assertIn("items", obj)
        self.assertIn("jobs", obj)
        # 整改后 mid 档由数据直接给出，灯箱不再从 full 路径推导
        self.assertIn("m", obj["items"][0], "条目缺 mid 档地址 m")
        self.assertIn("t", obj["items"][0], "条目缺缩略图地址 t")
        html = read("sites/midjourney-explore/index.html")
        self.assertNotIn("__SHARDS__", html, "页面仍在读多分片")
        self.assertNotIn("gallery_", html, "页面仍在引用按批次分片文件")

    def test_no_placeholder_leak_in_built_page(self):
        """构建产物里不能残留 {n_images} 之类的未填占位符。"""
        html = read("sites/midjourney-explore/index.html")
        for token in ("{n_images}", "{n_jobs}", "{n_authors}", "{n_aspects}"):
            self.assertNotIn(token, html, "页面残留未填占位符 %s" % token)

    def test_lightbox_stage_fits_viewport(self):
        """灯箱舞台不得横向溢出视口（图片会被推到视口外 → 打开一片空白）。

        根因：.lb 是 grid 容器但没定义 grid-template-columns，默认列宽由内容撑开
        （实测 stage 宽 2658px > 视口 900px）。修法是显式给出
        grid-template-columns:minmax(0,1fr) 并给 .stage/.foot 加 min-width:0。
        """
        html = read("sites/midjourney-explore/index.html")
        m = re.search(r"\.lb\{(.*?)\}", html, re.S)
        self.assertTrue(m, "页面里找不到 .lb 样式")
        self.assertIn("grid-template-columns:minmax(0,1fr)", m.group(1),
                      ".lb 必须限定网格列宽，否则灯箱横向溢出视口")
        stage = re.search(r"\.lb \.stage\{(.*?)\}", html, re.S)
        self.assertTrue(stage, "页面里找不到 .lb .stage 样式")
        self.assertIn("min-width:0", stage.group(1),
                      ".lb .stage 需要 min-width:0，否则内容宽度会撑破网格")


    def test_manifest_integrity_rejects_empty_batch(self):
        """某批采集为空时必须硬失败，不能静默少数据。"""
        mod = self._mod()
        with tempfile.TemporaryDirectory() as d:
            b = os.path.join(d, "b.txt")
            os.makedirs(os.path.join(d, "data", "daily", "2026-01-01"))
            with open(os.path.join(d, "data", "daily", "2026-01-01", "jobs.json"),
                      "w", encoding="utf-8") as f:
                f.write("[]")
            with self.assertRaises(SystemExit):
                mod.assert_manifest_integrity([{"id": "x"}], site=d, baseline=b)

    def test_manifest_integrity_rejects_shrink(self):
        """manifest 行数比上次少（历史被覆盖）时必须硬失败。"""
        mod = self._mod()
        with tempfile.TemporaryDirectory() as d:
            b = os.path.join(d, "b.txt")
            with open(b, "w", encoding="utf-8") as f:
                f.write("5")
            with self.assertRaises(SystemExit):
                mod.assert_manifest_integrity([{"id": "x"}], site=d, baseline=b)

    def test_manifest_integrity_accepts_healthy(self):
        mod = self._mod()
        with tempfile.TemporaryDirectory() as d:
            rows = [{"id": "a", "jobId": "a"}, {"id": "b", "jobId": "b"}]
            os.makedirs(os.path.join(d, "data", "daily", "2026-01-01"))
            with open(os.path.join(d, "data", "daily", "2026-01-01", "jobs.json"),
                      "w", encoding="utf-8") as f:
                json.dump(rows, f)
            b = os.path.join(d, "b.txt")
            self.assertEqual(mod.assert_manifest_integrity(rows, site=d, baseline=b), 2)
            self.assertTrue(os.path.exists(b), "成功时应写入基线")

    def test_manifest_covers_all_daily(self):
        """manifest 行数应等于各批次 jobs.json 行数之和（累积不漏批）。"""
        mod = self._mod()
        rows = mod.load_manifest()
        ddir = os.path.join(mod.SITE, "data", "daily")
        total = 0
        if os.path.isdir(ddir):
            for name in os.listdir(ddir):
                p = os.path.join(ddir, name, "jobs.json")
                if os.path.isfile(p):
                    with open(p, encoding="utf-8") as f:
                        total += len(json.load(f))
        self.assertEqual(len({r["jobId"] for r in rows}), total,
                         "manifest 的作业数应与各批次之和一致")


    def test_extract_refuses_overwrite_without_force(self):
        """同日重采不加 --force 必须拒绝（退出码 3），且不动已有文件。"""
        daily = os.path.join(ROOT, "sites", "midjourney-explore", "data", "daily")
        if not os.path.isdir(daily):
            self.skipTest("没有 daily/ 批次")
        names = sorted(n for n in os.listdir(daily)
                       if os.path.isfile(os.path.join(daily, n, "jobs.json")))
        if not names:
            self.skipTest("没有已有批次")
        batch = names[0]
        p = os.path.join(daily, batch, "jobs.json")
        with open(p, "rb") as f:
            before = f.read()
        r = subprocess.run(
            [sys.executable,
             os.path.join(ROOT, "sites", "midjourney-explore", "scripts", "extract.py"),
             "--batch", batch],
            capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 3, "未加 --force 应拒绝覆盖：" + r.stdout[-400:] + r.stderr[-400:])
        with open(p, "rb") as f:
            self.assertEqual(f.read(), before, "已有批次被改动了")


class MjFullOnline(unittest.TestCase):
    """W2：full 档端到端 online —— 直链入库、外链不加站点前缀、前端直通。"""

    def _load(self, rel, name):
        import importlib.util
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            self.skipTest(f"{rel} 不存在")
        # index/ 模块之间互相 import（sync → catalog/store），需要它在搜索路径上
        sys.path.insert(0, os.path.join(ROOT, "index"))
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_file_specs_full_is_url(self):
        """online 档的地址必须是上游直链，不再写本地路径。"""
        cat = self._load("index/catalog.py", "idx_catalog")
        cfg = cat.SOURCES["midjourney-explore"]
        rec = {"thumb_path": "sites/x/thumbs/a.webp", "thumb_url": "https://c/a.webp",
               "mid_path": "sites/x/mid/a.webp", "mid_url": "https://c/a-mid.webp",
               "full_path": "sites/x/img/a.png", "full_url": "https://cdn/a.png"}
        specs = cat.file_specs("midjourney-explore", cfg, rec)
        self.assertTrue(specs["full"][0].startswith("https://"),
                        "full 地址应为直链，实际 %r" % (specs["full"][0],))
        self.assertTrue(specs["thumb"][0].startswith("sites/"),
                        "thumb 仍应为本地相对路径")
        self.assertEqual(specs["thumb"][1], "https://c/a.webp", "thumb 上游地址应作回落保留")

    def test_manifest_has_no_full_path(self):
        """full 档是 online：manifest 里不得再有本地路径字段。

        留着一个指向已删除文件的 full_path，等于给下游埋必然 404 的死值。
        """
        rows = json.loads(read("sites/midjourney-explore/manifest.json"))
        bad = [r["id"] for r in rows if r.get("full_path")]
        self.assertEqual(bad, [], "manifest 里还有 full_path：%r" % (bad[:3],))
        bad_url = [r["id"] for r in rows if not str(r.get("full_url") or "").startswith("https://")]
        self.assertEqual(bad_url, [], "full_url 不是 https 直链：%r" % (bad_url[:3],))

    def test_gallery_has_no_full_path_field(self):
        """站点数据里不得出现指向本地原图的路径字段（gPath 之类）。

        online 档只有展示地址；带一个本地路径字段，下游按它推导图片就会算出
        必然 404 的地址。
        """
        raw = read("sites/midjourney-explore/data/gallery.js")
        m = re.search(r"JSON\.parse\((.*)\);\s*$", raw, re.S)
        self.assertTrue(m, "gallery.js 不是预期的 JSON.parse 形式")
        obj = json.loads(json.loads(m.group(1)))
        bad = [i["i"] for i in obj["items"] if i.get("gPath")]
        self.assertEqual(bad, [], "条目里还有 gPath：%r" % (bad[:3],))
        bad_g = [i["i"] for i in obj["items"]
                 if not str(i.get("g") or "").startswith("https://")]
        self.assertEqual(bad_g, [], "条目的 full 档不是 CDN 直链：%r" % (bad_g[:3],))

    def test_prefix_not_added_for_url(self):
        """外链入库时不得拼 sites/<集合>/ 前缀。"""
        sync = self._load("index/sync.py", "idx_sync")
        self.assertEqual(sync.addr_path("sites/x/", "https://cdn/a.png"),
                         "https://cdn/a.png")
        self.assertEqual(sync.addr_path("sites/x/", "thumbs/a.webp"),
                         "sites/x/thumbs/a.webp")

    def test_no_local_full_dir_declared(self):
        """本站不再保留本地原图目录：img/ 不声明也不该存在。

        imagePolicy.full = online 意味着本地不留 full 副本；
        imageDirs 里还挂着 img/，release.py 就会去链接一个空目录，
        而 manifest 里若有 img/ 路径就是悬空引用。
        """
        site = next(s for s in CFG["sites"] if s["id"] == "midjourney-explore")
        self.assertNotIn("img", site["imageDirs"],
                         "imageDirs 里不该再有 img（full 档走 online）")
        self.assertNotIn("full", site["tiers"],
                         "tiers 里不该再有 full（本地不下载原图）")
        img_dir = os.path.join(ROOT, "sites", "midjourney-explore", "img")
        self.assertFalse(os.path.exists(img_dir),
                         "img/ 目录应已清理（online 档本地不留原图）")

    def test_mapping_change_invalidates_sync_signature(self):
        """改了分面声明而 manifest 一个字节没动：签名必须变，否则 sync 直接跳过。

        跳过时没有任何报错，只是新分面永远不出现——这正是「改了配置像没改」的
        静默失败。签名只摘要声明本身，改注释不触发重建。
        """
        sync = self._load("index/sync.py", "idx_sync_sig")
        before = sync.signature(ROOT)
        cfg = sync.catalog.SOURCES["midjourney-explore"]
        try:
            cfg["facets"]["__probe__"] = "version"
            after = sync.signature(ROOT)
        finally:
            cfg["facets"].pop("__probe__", None)
        self.assertNotEqual(before, after, "映射表变了，签名却没变（sync 会跳过重建）")
        self.assertEqual(sync.signature(ROOT), before, "恢复配置后签名应回到原值")

    def test_media_url_passthrough(self):
        """前端拼地址：本地路径加 /media/，外链原样返回。"""
        st = self._load("index/store.py", "idx_store")
        self.assertEqual(st.media_url("https://cdn/a.png"), "https://cdn/a.png")
        self.assertEqual(st.media_url("sites/x/thumbs/a.webp"),
                         "/media/sites/x/thumbs/a.webp")

    def test_db_full_is_pure_url(self):
        """库里 midjourney 的 full 档必须是纯 CDN URL（不得带 /media/ 或 sites/ 前缀）。

        这是端到端断言：sync 入库 → store 出库两段都要对。
        曾经踩过的坑：serve 进程跑旧代码时，接口吐出 /media/https://cdn.… 这种
        浏览器必然 404 的地址。
        """
        db_path = os.path.join(ROOT, "gallery.db")
        if not os.path.exists(db_path):
            self.skipTest("没有本地索引库")
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "select d.path p from derivative d "
                "join item_asset ia on ia.asset_id=d.asset_id "
                "join item i on i.id=ia.item_id "
                "where i.collection='midjourney-explore' and d.kind='full'"
            ).fetchall()
        finally:
            conn.close()
        if not rows:
            self.skipTest("库里没有 midjourney 的 full 档")
        bad = [r["p"] for r in rows
               if not r["p"].startswith("https://") or "/media/" in r["p"]
               or "/sites/" in r["p"]]
        self.assertEqual(bad, [], "full 档地址被污染了：%r" % (bad[:3],))


if __name__ == "__main__":
    unittest.main(verbosity=2)
