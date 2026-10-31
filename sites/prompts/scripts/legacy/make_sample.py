# -*- coding: utf-8 -*-
"""生成演示用占位图 + 样例提示词表（纯标准库，无需 Pillow）

用法:
  python make_sample.py

产物:
  img/sample_01.png ... sample_06.png   纯色渐变占位图（真实尺寸按各画幅比例）
  sample_prompts.csv                    样例输入，extract.py 的演示数据
                                        覆盖三个模型：mj / imge-2 / nanobanana

真实素材就绪后：把图片放进 img/、用自己的提示词文件跑 extract.py 即可，
本脚本生成的样例文件可随时删除。
"""
import csv, os, struct, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(HERE, "img")

# (文件名, 模型, 标题, 提示词, 标签列表, 画幅, 宽, 高, 渐变起色, 渐变止色)
SAMPLES = [
    ("sample_01.png", "mj", "极光雪山",
     "aurora borealis over snow-capped mountains, cinematic lighting, volumetric fog, ultra detailed, 8k --ar 16:9 --v 6.1 --s 750",
     "风景,电影感,自然", "16:9", 640, 360, (24, 44, 84), (120, 200, 160)),
    ("sample_02.png", "mj", "赛博朋克街景",
     "neon-lit cyberpunk street at night, rain reflections, holographic signs, blade runner style --ar 21:9 --v 6.1 --s 800",
     "城市,赛博朋克,夜景", "21:9", 672, 288, (30, 16, 60), (230, 80, 180)),
    ("sample_03.png", "imge-2", "水彩睡猫",
     "watercolor painting of a sleeping cat, soft pastel colors, hand-drawn texture --ar 1:1",
     "动物,插画,水彩", "1:1", 480, 480, (240, 220, 200), (200, 150, 140)),
    ("sample_04.png", "imge-2", "古风仕女",
     "chinese traditional painting of an elegant lady in hanfu, ink wash style, delicate brushwork --ar 2:3",
     "人物,古风,插画", "2:3", 400, 600, (120, 100, 90), (235, 225, 210)),
    ("sample_05.png", "nanobanana", "荒漠机甲",
     "giant mecha in a desert battlefield, dramatic sunset, sci-fi concept art --ar 3:2",
     "机甲,科幻,概念设计", "3:2", 600, 400, (90, 50, 30), (250, 170, 90)),
    ("sample_06.png", "nanobanana", "晨光静物",
     "flat lay of coffee and books, warm morning light, cozy aesthetic, product photography --ar 4:5",
     "静物,生活,摄影", "4:5", 480, 600, (70, 55, 45), (225, 200, 170)),
]


def write_png(path, w, h, c1, c2):
    """最小 PNG 编码器：8-bit RGB、逐行 filter 0、垂直双色渐变。"""
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0
        t = y / max(h - 1, 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        raw += bytes((r, g, b)) * w
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", comp))
        f.write(chunk(b"IEND", b""))


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    rows = []
    for name, model, title, prompt, tags, ar, w, h, c1, c2 in SAMPLES:
        path = os.path.join(IMG_DIR, name)
        write_png(path, w, h, c1, c2)
        print(f"  ✓ {name:18s} {model:10s} {w}x{h}  {ar}")
        rows.append({
            "file": f"img/{name}", "model": model, "title": title, "prompt": prompt,
            "tags": tags, "ar": ar, "v": "6.1" if "6.1" in prompt else ("6" if model == "mj" else ""),
            "s": prompt.split("--s ")[1].split()[0] if "--s " in prompt else "",
            "style": "raw" if "--style raw" in prompt else "",
        })

    csv_path = os.path.join(HERE, "sample_prompts.csv")
    cols = ["file", "model", "title", "prompt", "tags", "ar", "v", "s", "style"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n✓ 占位图 {len(rows)} 张 → img/，样例表 → sample_prompts.csv（mj / imge-2 / nanobanana 各 2 张）")


if __name__ == "__main__":
    main()
