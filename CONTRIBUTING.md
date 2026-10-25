# Contributing

欢迎 issue 和 PR，尤其是：

- **新的静默失败案例。** 症状、根因、修法三段式，进
  `references/ae-extendscript-pitfalls.md` 的速查表和正文。这类内容是本仓库的核心，
  比新增功能有价值得多。
- **其它 AE 版本的行为差异。** 目前只在 After Effects 2023 (23.5) / Windows 实测过。
  如果你在 2024 / 2025 或 macOS 上验证过某条坑不成立（或成立），标注版本提 PR。
- **脚本的跨平台修正。** PATH、编码、路径分隔符。

## 提交前

```bash
python selftest.py
```

它不需要 After Effects，但需要 `ffmpeg` 才会跑扫描和编码两组用例（没有则自动跳过）。

## 约定

1. **脚本必须接收显式路径参数**，不允许出现某个项目专属的硬编码路径。
2. **检查类脚本绝不调用 `app.project.save()`。** 只读就是只读。
3. **中文输出统一走 UTF-8。** 新脚本按现有写法在开头 reconfigure stdout/stderr，
   否则非中文 locale 的 Windows 上会直接崩。
4. **改 `ae_bridge.py` 要说明原因。** 它是所有 AE 脚本的共用层，改坏了是全套失效。
