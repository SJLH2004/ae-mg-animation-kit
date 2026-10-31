# ae-mg-animation-kit

[![CI](https://github.com/SJLH2004/ae-mg-animation-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/SJLH2004/ae-mg-animation-kit/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![After Effects](https://img.shields.io/badge/After%20Effects-2023-9999ff)

**用脚本产出一条完整的扁平化 MG 动画科普片：分镜 → 段落合成 → PIL 预渲染图形 → 配音配乐 → 无界面渲染 → 卡规格编码。**

*Script-drives After Effects to build a whole flat-graphics motion-graphics explainer: storyboard, per-shot comps, PIL pre-rendered graphics, TTS voice-over, original score, headless render and spec-compliant H.264 delivery.*

---

## 这个仓库真正在卖什么

不是「怎么让元素动起来」——AE 里拖关键帧谁都会。

它卖的是一份 **「每个 API 都返回成功、画面却是错的」清单**。写 JSX 之前先读
[`references/ae-extendscript-pitfalls.md`](references/ae-extendscript-pitfalls.md)，
导出前跑一遍 `scripts/blank_scan.py`，这两件事能省掉一整轮返工。

几个真实例子：

| 症状 | 根因 |
|---|---|
| 位移变成 `[x,x,0]`，图层消失 | Position 是 3 维，`dim===2` 判断永不成立 |
| 图层在 t0 之前就一直可见 | 覆盖式关键帧没从 `[0,0]` 开始，AE 向左无限延展 |
| 硬切变成 0.29 s 的淡入斜坡 | `round(t0-0.004, 2)` 把保持键舍回主键同帧 |
| 动画整段错位、时间减半 | 时间映射 `T(t)` 被调了两次，变成 `T(T(t))` |
| 整批图标全透明 | Lucide 的 `stroke="currentColor"`，svglib 解析成空白 |
| 一整片渲成 660 MB 的 `.psd` | AE 2023 输出模板里根本没有 PNG |
| 只有画面没有声音 | 渲染队列两项只执行第一项 |
| 素材挪盘后工程打开全是丢链 | 工程存绝对路径；只有 `FootageItem.replace()` 能改，另外两个 API 都不通 |
| 无头渲染时脚本静默死、抽帧文件不落地 | `-noui` 不支持 `app.newProject()`，`saveFrameToPng()` 也会假成功 |
| 桥接脚本随机超时、杀进程也没用 | `subprocess.run(capture_output=True)` 被 AE 日志撑满 64 KB 管道，父子互相等待 |

## 七步工作流

```text
① 台词分句 + 时间码 ──► ② PIL 预渲染图形 ──► ③ TTS 配音 + 合成音效/配乐
                                                  │
        ⑦ 卡规格编码 + 核验表 ◄── ⑥ QA 抽帧/空窗扫描 ◄── ⑤ aerender 渲帧 ◄── ④ 拼 AEP
```

| 步骤 | 做什么 | 详见 |
|---|---|---|
| ① 脚本 + 分镜 | 旁白写成带时间码的句子，一句一镜；时长由 TTS 实测反推，不靠估 | [project-organization.md](references/project-organization.md) |
| ② 素材 | **视频优先**：PIL 2× 超采样出 PNG（不用形状图层）；**工程优先**：交付要求「工程可编辑」时全部用原生 Shape/Text 图层，零位图 | [asset-pipeline.md](references/asset-pipeline.md) · [native-shape-text-layers.md](references/native-shape-text-layers.md) |
| ③ 音轨 | 逐句 TTS + numpy 物理合成音效 + 原创配乐（配乐用 [video-score-composer](https://github.com/SJLH2004/video-score-composer)） | [asset-pipeline.md](references/asset-pipeline.md) |
| ④ 建工程 | 一个镜头一个 JSX，合并成一次 AE 启动注入；总合成只放段落层 | [project-organization.md](references/project-organization.md) |
| ⑤ 渲染 | `aerender` 无界面；输出「多机序列」PSD → 转 PNG | [render-and-delivery.md](references/render-and-delivery.md) |
| ⑥ 质检 | 抽 6–10 帧 + 全片内容密度扫描，专抓空窗和死镜头 | [`scripts/blank_scan.py`](scripts/blank_scan.py) |
| ⑦ 交付 | CBR 锁码率编码，打印 ffprobe 核验表 + 削波检查 | [`scripts/encode_submit.py`](scripts/encode_submit.py) |

## 五条铁律

1. **检查脚本绝不 `app.project.save()`。** 连上一个未命名工程再保存，会把真实 AEP 覆盖成 8 KB 空工程。先查 `app.project.file.fsName`，重建前先复制。
2. **绝不覆盖用户手改过的工程。** 用户说「我手动改了」就渲他的文件，只把改动反写回 `build_*.py`。
3. **每个段落合成必须自带整帧背景。** 单合成改成分段后，原本跨镜头的背景层消失，那些镜头会变全黑。
4. **空窗是第一号观感缺陷。** 相邻两段各自淡出/淡入，边界处 0.15–0.25 s 什么都没有。必须扫、必须补。
5. **工作路径必须是纯 ASCII。** 中文路径会让 JSX 的 `File` 对象和 psd-tools 双双失败。

## 脚本

| 脚本 | 作用 | 依赖 |
|---|---|---|
| `scripts/inspect_aep.py` | 只读 dump：合成结构 / 图层数 / workArea / 总合成时间线 / 丢链 | AE |
| `scripts/frames_qa.py` | 指定秒数导出 PNG（含 `saveFrameToPng` 异步等待） | AE |
| `scripts/blank_scan.py` | 逐 0.1 s 扫内容占比，找空窗和死镜头 | ffmpeg |
| `scripts/psd2png.py` | PSD 序列 → PNG 序列（8 线程，2300 帧约 15 s） | PIL |
| `scripts/encode_submit.py` | CBR 编码到规格 + ffprobe 核验表 + 削波检查 | ffmpeg |
| `scripts/ae_bridge.py` | AE 桥接层（含 ASCII 工作区选择、UTF-8 输出修正） | — |

所有脚本都接收显式路径参数，没有任何项目专属的硬编码。

## 为什么码率必须用 CBR

纯色 / 扁平风画面极难吃满 VBR 目标码率：`-b:v 3000k` 两遍编码实测只出 **1.10 Mbps**。
要压到 `~3 Mbps` 只能锁死：

```bash
ffmpeg -framerate 50 -i f_%04d.png -i mix.wav \
  -vf "scale=1280:720:flags=lanczos" \
  -c:v libx264 -preset slow \
  -b:v 3000k -minrate 3000k -maxrate 3000k -bufsize 6000k \
  -x264-params "nal-hrd=cbr:force-cfr=1" \
  -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -shortest -movflags +faststart out.mp4
```

实测出 2.99 Mbps。`scripts/encode_submit.py` 把这条命令和核验表都封装好了。

## 交付核验表

| 项 | 判据 |
|---|---|
| 分辨率 | 与规格完全一致 |
| 帧率 | `r_frame_rate` 等于规格（`50/1`，不是 `48.9`） |
| 时长 | ≤ 上限，且留 0.2 s 余量（编码器会补帧） |
| 视频码率 | 目标 ±5% |
| 音频 | AAC / 48 kHz / ≥192 kbps / 立体声 |
| 峰值 | `max_volume < 0 dB`，最好 −1 ~ −3 dB |
| 容器 | `+faststart` |

## 安装

```bash
pip install -r requirements.txt      # numpy + pillow
# AE 侧：After Effects 2023 + aerender 在 PATH（渲染/检查脚本需要）
# ffmpeg 在 PATH（扫描/编码/抽检需要）
```

`asset-pipeline.md` 里提到的 TTS 与图标链路（`edge-tts`、`svglib`、`reportlab`、
`pypdfium2`）按需自行安装，核心脚本不依赖它们。

## 局限

- **只在 Windows + After Effects 2023 (23.5) 实测过。** 其它版本的行为未验证，尤其是
  输出模板列表和 ExtendScript 对中文路径的处理。
- **不含成片素材。** 仓库里没有 PSD/PNG 帧或音频，都是你项目自己的产物。
- **构建器不在仓库里。** `build_*.py` 和具体镜头的 JSX 属于项目代码，这里给的是
  组织方式、脚本和坑清单——照着搭比直接跑一个空壳更有用。

## 相关仓库

- [video-score-composer](https://github.com/SJLH2004/video-score-composer) —— 跟画面运动对齐的原创配乐（本套流程第 ③ 步用它）
- [ae-template-retrofit-kit](https://github.com/SJLH2004/ae-template-retrofit-kit) —— 改现成 AE 模板并验收出片（方向相反：那个是改模板，这个是造工程）

## 第三方依赖与许可

本仓库**不包含任何第三方代码或素材**——没有图标、PSD、音频、模板或字体文件，
`scripts/` 和 `references/` 都是本项目的原创内容。文档里提到的库只是推荐链路，
按需自行安装，许可证以各项目官方声明为准：

| 库 | 用途 | 备注 |
|---|---|---|
| `numpy` / `pillow` | 扫描、PSD 转 PNG | BSD 系 / HPND，可商用 |
| `edge-tts` | 逐句配音 | **GPL-3.0**，有传染性，商用前先评估 |
| `svglib` / `reportlab` | SVG 图标栅格化 | LGPL-3.0 / BSD 系 |
| `pypdfium2` | PDF 渲染成 PNG | Apache-2.0 / BSD 系 |
| Lucide 图标 | 图标源 | ISC，可商用 |

`scripts/ae_bridge.py` 与 [ae-template-retrofit-kit](https://github.com/SJLH2004/ae-template-retrofit-kit)
里的同名文件同源，本仓库内联了一份以便脚本直接可用。

## License

MIT — 见 [LICENSE](LICENSE)。
