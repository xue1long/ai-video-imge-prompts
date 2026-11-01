# -*- coding: utf-8 -*-
"""取图策略：档位 → 图片地址从哪来。

策略声明在 sites.json 里（每站一份，按档位给出），是站点相关声明的唯一来源。
取值三种：

  local-first   页面先请求站内相对路径，加载失败回落到该档位的上游地址
  online        页面直接用上游地址，站内不再保留该档位的图片
  local-only    只用站内地址，不做上游回落（默认）

两个约定：

1. **构建过程不探测本地文件是否存在**。策略是提交进仓库的静态配置，
   构建产物只取决于配置——这样产物在有图与无图的环境里逐字节一致。
2. **通用代码里不出现站点分支**。站点差异只通过声明表达。

编码约定（构建脚本与页面共用）：

  <字段>     展示地址。online 时是上游 URL，否则是站内相对路径
  <字段>Url  上游地址。仅 local-first 时写出，作为加载失败的回落目标
  <字段>Path 站内相对路径。仅 online 时写出，供中图等按路径推导的规则使用

字段名各站不同（t/f、th/im/pg、s/m/g…），但后缀约定一致，
因此页面里的通用回落逻辑不需要知道每个站的具体字段名。

构建脚本与索引同步共用这一份，不各写一份。
"""

import json
import os

LOCAL_FIRST = "local-first"
ONLINE = "online"
LOCAL_ONLY = "local-only"

MODES = (LOCAL_FIRST, ONLINE, LOCAL_ONLY)
DEFAULT = LOCAL_ONLY

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tier_mode(site, tier):
    """某站某档位的取图策略；未声明的档位按 local-only。"""
    return (site.get("imagePolicy") or {}).get(tier, DEFAULT)


def site_entry(site_id, repo=REPO):
    """从站点清单里取出某个站的条目。"""
    with open(os.path.join(repo, "sites.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    for s in cfg["sites"]:
        if s["id"] == site_id:
            return s
    raise KeyError("清单里没有这个站：" + site_id)


def tier_addr(site, tier, path, url):
    """该档位该条素材的展示地址与回落地址。

    返回 (display, fallback, path_kept)：
      display    页面放进 src 的地址
      fallback   加载失败时的回落地址，没有则为空串
      path_kept  是否需要保留站内相对路径（online 时中图等推导要用）
    """
    mode = tier_mode(site, tier)
    if mode == ONLINE:
        return url or "", "", True
    if mode == LOCAL_FIRST:
        return path, url or "", False
    return path, "", False


# 页面里的通用回落逻辑：图片加载失败时换成上游地址，只重试一次。
# 用捕获阶段的 error 监听，任何 <img> 只要带 data-fb 就自动生效，
# 各站页面不需要各写一遍。
FB_JS = """<script>(function(){
document.addEventListener('error',function(e){
  var el=e.target;
  if(!el||el.tagName!=='IMG'||!el.dataset||!el.dataset.fb||el.dataset.fbUsed)return;
  el.dataset.fbUsed='1';
  el.src=el.dataset.fb;
},true);
})();</script>"""
