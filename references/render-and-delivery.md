# 渲染与交付

## 帧率与分辨率

- **合成帧率直接设成交付帧率**（如 50 fps）。关键帧按秒存储，改帧率不会改动画节奏，只是采样更密。
  30 → 50 会让运动明显更顺，这一步白拿。
- **按高分辨率渲染、交付时降采样**：渲 1920×1080，`scale=1280:720:flags=lanczos` 出片。
  比直接在 720p 合成里做清晰，文字和细线差得很明显。

## 渲染：走 aerender，不走 GUI

```
aerender -project X.aep -comp "总合成" -output out/f_[#####].psd
```

GUI 版 AE 用 `-r` 调脚本是「跑完即退出」，每调一次屏幕闪一下。渲染用 `aerender`
本来就无界面，不会闪。

### 输出模板里没有 PNG

AE 2023 的 `outputModule.templates` 实际只有：

```
多机序列（= 分帧 PSD） / 带 Alpha 的 TIFF 序列 / AIFF / H.264 ×3 / Photoshop / 高品质 / 无损 / X-Factor
```

用 `indexOf("PNG")` 会落空并退回第一个模板（多机序列），于是一整片渲成 `.psd`。

体积实测（2250 帧 1080p）：TIFF ≈ 18 GB，PSD ≈ 660 MB，转 PNG ≈ 377 MB。
**选「多机序列」，渲完用 `scripts/psd2png.py` 转 PNG**，最快也最省。

### 画面和音频要分两次渲

同一 comp 往渲染队列加两项（PSD + AIFF）时，`aerender -comp` 只执行第一项，
音频不会出来，而脚本报成功。正确做法：

1. 清空队列，只加画面项，渲一遍
2. 清空队列，只加音频项（AIFF），再渲一遍

音频渲出来在 Windows 上扩展名会被截成 `.aif`，ffmpeg 认得出，不用管。

**AE 内混音的价值**：音效层分布在各段落合成里，渲染音频时随预合成自动对位，
不用在 ffmpeg 侧重建整条音效时间轴。

## 编码到规格

交付规格通常长这样：`1280×720 / 50 fps / ≤45 s / H.264 / ~3 Mbps / AAC 48 kHz ≥192 kbps`。

### 目标码率必须用 CBR，不能用两遍 VBR

纯色 / 扁平风 MG 画面极难吃满码率：`-b:v 3000k` 两遍编码实测只出 **1.10 Mbps**。
要压到目标值只能锁死：

```
-c:v libx264 -preset slow \
-b:v 3000k -minrate 3000k -maxrate 3000k -bufsize 6000k \
-x264-params "nal-hrd=cbr:force-cfr=1" \
-pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -ac 2 \
-shortest -movflags +faststart
```

实测出 2.99 Mbps，正好落在 ~3 Mbps。

### 交付前核验表

```
ffprobe -show_entries stream=codec_name,width,height,r_frame_rate,bit_rate,sample_rate,channels \
        -show_entries format=duration,bit_rate,size -of default=nw=1 out.mp4
ffmpeg -i out.mp4 -map 0:a -af volumedetect -f null -
```

| 项 | 判据 |
|---|---|
| 分辨率 | 与规格完全一致 |
| 帧率 | `r_frame_rate` 等于规格（`50/1` 不是 `48.9`） |
| 时长 | ≤ 上限，且**不要贴着上限**（留 0.2 s 余量，编码器会补帧） |
| 视频码率 | 落在目标 ±5%，否则会被判没达标 |
| 音频 | AAC / 48 kHz / ≥192 kbps / 立体声 |
| 峰值 | `max_volume` 必须 < 0 dB，最好 −1 ~ −3 dB |
| 容器 | `+faststart`，MP4 能在网页里直接播 |

`scripts/encode_submit.py` 把这套全做了，一次打印成表。

## 抽检

- 逐帧看整片是浪费。用 `scripts/frames_qa.py` 抽 6–10 个点（每段首、中、尾各一）。
- 再用 `scripts/blank_scan.py` 扫一遍内容占比，专门抓「空窗」和「死镜头」——
  这两个是最容易被自己忽略、观众一眼看到的缺陷。
- 段边界、时间重映射后的首尾、动效峰值点是必抽的位置。

## 常见坑

| 现象 | 原因 | 修法 |
|---|---|---|
| 渲出 660 MB 的 `.psd` | 输出模板没有 PNG，退回了多机序列 | 预期行为，转 PNG 即可 |
| `-i f_%04d.psd` 报找不到 | ffmpeg image2 不认 psd 序列（单帧能读） | PIL 批量转 PNG |
| 只有画面没声音 | 队列两项只执行第一项 | 音频单独渲一次 |
| 码率只有目标的 1/3 | 扁平画面吃不满 VBR | CBR 锁 `minrate=maxrate` |
| 峰值 0.0 dB | 人声+BGM+音效叠加溢出 | `-c:v copy -af volume=-2.5dB` |
| 渲染 30 秒后进程消失 | 沙箱把 `WMIC.exe` 拦了（aerender 收尾会调） | 无害，帧已渲完，直接检查帧数 |

## 配乐来源

只用 **CC0 / 已授权音源**（Freesound、Pixabay Audio、YouTube Audio Library 等），
或使用配套的 [video-score-composer](https://github.com/SJLH2004/video-score-composer)
按画面节奏现场合成——后者零采样、零版权风险，也不存在授权到期的问题。

不要从流媒体平台的非官方接口抓取现成歌曲：既涉及版权，也随时会被封禁。

## 兜底渲染：pyrender（纯 Python 逐帧）

AE 完全不可用时（wmic 黑名单、桥接死锁），可用 PIL 按「图层语义」逐帧合成：
- 图层 = png/solid + pos/sca/rot/opa 关键帧 + in/out + fi/fo + popIn（贝塞尔 smoothstep）
- **坑**：AE 的 `pscale()` 返回的是"导入尺寸百分比"，渲染器若按"显示宽百分比"解释，元素会缩小到一半、底图放大 1.33 倍——所有关键帧必须统一成显示宽百分比语义
- 性能：1100 帧 720p 约 100 秒；帧文件用同名覆盖（批量删除会触发保护）
