# -*- coding: utf-8 -*-
"""取图策略：档位 → 图片地址从哪来。

策略声明在 sites.json 里（每站一份，按档位给出），是站点相关声明的唯一来源。
取值三种：

  local-first   页面先请求站内相对路径，加载失败回落到该档位的上游地址（默认）
  online        页面直接用上游地址，站内不再保留该档位的图片
  local-only    只用站内地址，不做上游回落（上游不可直连时）

两个约定：

1. **构建过程不探测本地文件是否存在**。策略是提交进仓库的静态配置，
   构建产物只取决于配置——这样产物在有图与无图的环境里逐字节一致。
2. **通用代码里不出现站点分支**。站点差异只通过声明表达。

构建脚本与索引同步共用这一份，不各写一份。
"""

LOCAL_FIRST = "local-first"
ONLINE = "online"
LOCAL_ONLY = "local-only"

MODES = (LOCAL_FIRST, ONLINE, LOCAL_ONLY)
DEFAULT = LOCAL_FIRST


def tier_mode(site, tier):
    """某站某档位的取图策略；未声明的档位按 local-first。"""
    return (site.get("imagePolicy") or {}).get(tier, DEFAULT)
