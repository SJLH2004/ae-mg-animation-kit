# Changelog

## v1.0.2 — 2026-10-31

- **新增 `references/native-shape-text-layers.md`** —— 原生 Shape/Text 图层工作流。
  交付要求「工程必须可编辑、元素不能是图片」时的零位图做法：常用 `addProperty`
  的 matchName、Trim/Repeater 后必须 `moveTo`（且旧对象引用失效）、环形图/折线图
  正规做法、文本层在 `aerender` 下字体会静默 fallback、`softShadow` 必须在
  `popIn` / `vis2` **之前**调用。
- **坑清单 21 → 30 条**，新增 22–30：WMIC 被安全策略拦截导致整个进程树被杀、
  `workAreaDuration` 浮点边界、JSX 解析期语法错误不报错、多段 build 互相覆盖、
  渲染队列只执行第一项、`ae_bridge.run()` 的 stdout 管道死锁、`-noui` 下
  `app.newProject()` 静默死、`saveFrameToPng()` 假成功。
  速查表重排为连续 1–30 并补齐缺失行（原先「21」重复、27–29 未入表）。
- `references/render-and-delivery.md` — 新增兜底渲染（纯 Python 逐帧）一节及其
  `pscale()` 语义坑（按「显示宽百分比」解释会让元素缩小一半）；配乐来源改为
  只列 CC0 / 已授权渠道。
- `SKILL.md` — 第 2 步拆成「视频优先 / 工程优先（可编辑交付）」两种模式。
- `README.md` — 七步表与真实案例表同步更新。

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
