legacy：独立本地页时期的脚手架，未接入构建管线。
- extract.py：CSV/JSON 提示词表 → 旧版 manifest（新管线用 import_youmind.py + scripts/manifest.py）
- make_sample.py / sample_prompts.csv：演示数据
- import_gpt2.py：从 awesome-gpt-image-2 README 导入（已被 import_youmind.py 的 API 全量导入取代）
