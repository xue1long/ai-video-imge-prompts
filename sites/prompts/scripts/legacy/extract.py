# -*- coding: utf-8 -*-
"""从提示词文件 + img/ 目录生成 manifest.json

用法:
  python extract.py                                  # 默认读 sample_prompts.csv
  python extract.py --source my_prompts.csv          # 指定 CSV / JSON
  python extract.py --source prompts.json --img-dir img

支持的输入:
  CSV  列（列名可改，见下方 COLUMN 映射）:
       file/image/filename  图片文件名或路径（相对本目录，一般放 img/ 下）
       prompt               MJ 提示词（可含 --ar --v --s 等参数）
       model                模型：mj / imge-2 / nanobanana 等（可选，缺省用 --model）
       tags                 标签，逗号或顿号分隔（可选）
       title                标题（可选）
       其余任意列（ar / v / s / style ...）一律作为参数收录
  JSON 数组，字段同上

manifest 记录结构:
  { id, file, title, prompt, params{...}, tags[...], w, h }
  w/h 从 PNG 头解析（非 PNG 留空，前端用 --ar 推导 aspect-ratio）。
"""
import argparse, csv, json, os, re, struct

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 列名映射：你的表头叫什么就改这里 ─────────────────
COLUMN = {
    "file": ["file", "image", "filename", "文件", "图片", "图片文件"],
    "prompt": ["prompt", "提示词", "mj提示词", "MJ提示词"],
    "model": ["model", "模型", "来源", "engine", "tool", "工具"],
    "tags": ["tags", "tag", "标签"],
    "title": ["title", "name", "标题", "名称"],
}

IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
PARAM_RE = re.compile(r"--([a-z]+)\s+(\S+)")


def pick(row_keys, kind):
    for k in COLUMN[kind]:
        if k in row_keys:
            return k
    return None


def parse_params(prompt):
    """从提示词尾部提取 --key value 参数；返回 (params, 纯净提示词)。"""
    params = {m.group(1): m.group(2).rstrip(",") for m in PARAM_RE.finditer(prompt)}
    clean = PARAM_RE.sub("", prompt).replace("  ", " ").strip().rstrip("-").strip()
    return params, clean


def png_size(path):
    try:
        with open(path, "rb") as f:
            head = f.read(24)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", head[16:24])
            return w, h
    except OSError:
        pass
    return None, None


SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
               0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def jpeg_size(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        if data[:2] != b"\xff\xd8":
            return None, None
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            if data[i + 1] in SOF_MARKERS:
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + max(seg, 2)
    except OSError:
        pass
    return None, None


def image_size(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".png":
        return png_size(path)
    if ext in (".jpg", ".jpeg"):
        return jpeg_size(path)
    return None, None


def normalize(rec, img_dir, idx, model_default=""):
    keys = set(rec.keys())
    k_file, k_prompt = pick(keys, "file"), pick(keys, "prompt")
    if not k_file or not k_prompt:
        raise ValueError(f"第 {idx} 条记录缺少 file / prompt 列: {list(rec.keys())}")
    file_val = (rec[k_file] or "").strip().replace("\\", "/")
    base = os.path.basename(file_val)
    # 只给文件名时自动落到 img/；img/ 下能唯一匹配时也自动补全
    if not os.path.splitext(file_val)[1]:
        hits = [f for f in os.listdir(img_dir) if os.path.splitext(f)[0] == base] if os.path.isdir(img_dir) else []
        if len(hits) == 1:
            base = hits[0]
    rel = file_val if file_val.startswith("img/") else f"img/{base}"
    disk = os.path.join(HERE, rel)
    if not os.path.exists(disk):
        print(f"  ⚠ 第 {idx} 条: 图片不存在 {rel}（先跳过，图片可后补）")

    params, clean = parse_params(rec[k_prompt] or "")
    tags_raw = (rec[pick(keys, "tags")] or "") if pick(keys, "tags") else ""
    tags = [t.strip() for t in re.split(r"[,，、;；/]", tags_raw) if t.strip()]
    title = (rec[pick(keys, "title")] or "").strip() if pick(keys, "title") else ""
    k_model = pick(keys, "model")
    model = (rec[k_model] or "").strip() if k_model else ""
    if not model:
        model = model_default
    w, h = image_size(disk) if os.path.exists(disk) else (None, None)
    if "ar" not in params and w and h:
        from math import gcd
        g = gcd(w, h)
        params["ar"] = f"{w // g}:{h // g}"

    return {
        "id": f"m{idx:04d}",
        "file": rel,
        "title": title or os.path.splitext(base)[0],
        "prompt": clean,
        "rawPrompt": rec[k_prompt],
        "params": params,
        "tags": tags,
        "model": model,
        "w": w, "h": h,
        **extra_fields(rec),
    }


def extra_fields(rec):
    """透传未消费的列（author / sourceUrl / promptRaw ...），空值丢弃。"""
    consumed = {k for aliases in COLUMN.values() for k in aliases}
    return {k: v for k, v in rec.items()
            if k not in consumed and v not in (None, "")}


def load_rows(source):
    ext = os.path.splitext(source)[1].lower()
    if ext == ".json":
        with open(source, encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON 需要是记录数组")
        return data
    with open(source, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", nargs="+", action="append", default=None,
                    help="CSV 或 JSON 提示词文件，可多次传入或一次传多个，合并导入")
    ap.add_argument("--img-dir", default="img", help="图片目录（相对本目录）")
    ap.add_argument("--out", default="data/manifest.json")
    ap.add_argument("--model", default="",
                    help="记录缺 model 列时的默认模型，如 mj / imge-2 / nanobanana")
    args = ap.parse_args()

    rows = []
    groups = args.source or [["sample_prompts.csv"]]
    for s in [x for g in groups for x in g]:
        src = s if os.path.isabs(s) else os.path.join(HERE, s)
        loaded = load_rows(src)
        print(f"输入 {src} · {len(loaded)} 条记录")
        rows.extend(loaded)
    print(f"合计 {len(rows)} 条记录\n")

    img_dir = os.path.join(HERE, args.img_dir)
    out, missing = [], 0
    for i, rec in enumerate(rows, 1):
        item = normalize(rec, img_dir, i, args.model)
        if not os.path.exists(os.path.join(HERE, item["file"])):
            missing += 1
        out.append(item)

    out_path = os.path.join(HERE, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"✓ manifest {len(out)} 条 → {args.out}" + (f"（{missing} 张图片暂缺）" if missing else ""))


if __name__ == "__main__":
    main()
