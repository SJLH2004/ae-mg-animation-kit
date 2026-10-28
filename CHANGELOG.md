# Changelog

## v1.0.1 — 2026-10-28

- `references/ae-extendscript-pitfalls.md` — 新增**第 21 条：归档移动素材后必须重链**。
  工程存的是构建时的绝对路径，素材挪盘后打开就是大批丢链；实测三种 API 里只有
  `FootageItem.replace(new File(...))` 可用（`replaceSource()` 未定义、
  `mainSource.file` 是只读属性）。附批量重链脚本、前缀映射的顺序问题
  （`audio/v45/` 必须排在 `audio/` 之前）、JSX 注入路径必须转正斜杠的原因，
  以及重链后的验证标准（`footageMissing` 归零、图层数不变）。
- 速查表同步增加第 21 行。

## v1.0.0 — 2026-10-26

首次公开。

- `SKILL.md` — 七步工作流 + 五条铁律 + 脚本索引，可直接放进 SKILL.md 兼容的
  agent 运行时使用。
- `references/ae-extendscript-pitfalls.md` — 20 条静默失败清单，每条都是
  「API 报成功、AE 不报错、画面是错的」。
- `references/project-organization.md` — 总合成 + 段落合成结构、`T(t)` 时间重映射、
  SHOTS 表驱动、按 TTS 实测时长反推镜头长度。
- `references/asset-pipeline.md` — PIL 2× 超采样出图形、Lucide 图标
  `currentColor` 处理、TTS、numpy 音效、配乐交接。
- `references/render-and-delivery.md` — aerender、PSD → PNG 帧链路、
  CBR 编码到规格、交付核验表。
- `scripts/inspect_aep.py` — 只读 dump 工程结构与总合成时间线（绝不保存）。
- `scripts/frames_qa.py` — 指定秒数导出 PNG，含 `saveFrameToPng` 异步等待。
- `scripts/blank_scan.py` — 按内容占比扫空窗与死镜头，可判定空窗持续时长。
- `scripts/psd2png.py` — PSD 序列转 PNG 序列，8 线程，带断点跳过。
- `scripts/encode_submit.py` — CBR 锁码率编码 + ffprobe 核验表 + 削波告警。
- `scripts/ae_bridge.py` — AE 桥接层：ASCII 工作区自动选择、UTF-8 输出修正、
  ES3 序列化回退。
- `selftest.py` — 不依赖 AE：脚本编译检查、空窗检测的正反用例、编码产物核验。
