# 素材流水线

## 图形：PIL 预渲染，不用 AE 形状图层

AE 形状图层的属性 API 不稳定（会让 AE 崩溃，见 pitfalls #1）。改为 Python 侧出 PNG，
AE 只负责摆放——顺带解决了「AE 无法导出 SVG」「形状描边在预合成里缩放后变粗」等问题。

```python
# 2× 超采样再降采样 = 抗锯齿
def rrect(w, h, r, fill, stroke=None, sw=0):
    S = 2
    im = Image.new("RGBA", (w*S, h*S), (0,0,0,0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0,0,w*S-1,h*S-1], radius=r*S, fill=fill, outline=stroke, width=sw*S)
    return im.resize((w,h), Image.LANCZOS)
```

覆盖的基础件就够拼扁平 MG：`rrect`（圆角矩形）、`ell`（椭圆）、`ring`（环，用 mask 相减）、
`capsule`（胶囊）、`diamond`（菱形）、`solid`（纯色块）。

文件名带参数做缓存键：`rrect_340x4_r2_b2e3f7.png` —— 同一参数只生成一次，
重建工程时直接复用，不会重复导入。

## 图标：SVG 必须先替换 currentColor

Lucide 等图标库用 `stroke="currentColor"`，`svglib` 解析不了 → 画出空白页，
光栅化后 alpha 全 0 → **整批图标等于没画**，而脚本不会报错。

```
Lucide SVG → 替换 currentColor 为 #000000 → svglib.svg2rlg
          → reportlab renderPDF → pypdfium2 渲染 → PIL 按 lum 做 alpha → 上色
```

```python
raw = raw.replace("currentColor", "#000000")   # 关键一步
d = svg2rlg(tmp_svg); d.scale(N, N); d.width *= N; d.height *= N
renderPDF.drawToFile(d, tmp_pdf)
pil = pdfium.PdfDocument(tmp_pdf)[0].render(scale=1).to_pil().convert("RGB")
lum = np.asarray(pil).mean(axis=2)
alpha = 255 - lum                              # 黑线 → 不透明
```

上色时保留 alpha、把 RGB 刷成目标色，输出 8 套配色（white / blue / bluedk / green / red /
yellow / gray / light）。校验一步：`alpha.max() > 0`，否则就是 svglib 又画了空白。

`reportlab` 的 renderPM 后端常缺 `libcairo-2.dll`，不要走那条路，走 PDF → pdfium。

## 配音

```python
import edge_tts
edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural", rate="+15%").save(out)
```

- 逐句生成，生成后 `ffprobe` 量实测时长，写进 `vo_timing.json`；时间轴由实测值累加，不靠估。
- 语速：默认 `+0%`；赶时长最多 `+15%`，再高会显得像机器在念。
- 换行会影响断句，长句手动加中文逗号控制呼吸点。

## 音效

`numpy` 物理合成，零采样、零版权风险。扁平 MG 常用的十个：
铃声、故障 glitch、扫描 whoosh、金币、警报、转场 whoosh、电流 buzz、结束音、消息提示、挂断。

## 配乐

加载 `video-score-composer`。交接要点：

1. **先用画面节奏定 BPM**：`rhythm_scan.py` 扫一遍成片，取 action peaks；段落边界应与峰值对得上，
   对不上说明画面节奏本身有问题。
2. **时长要能整除小节**：45 s @ 112 BPM = 21 小节正好；`BAR = 60/BPM*4`（**不是 `60/BPM`**，
   写错会让底鼓每半秒敲一次）。
3. **引擎报 `rolloff85` 偏低（<900 Hz）不要加 EQ**，那是配器问题：压薄 pad、bass 让位、旋律乐器提亮。
4. 段落边界前 0.4 s 上 riser + 落点 bell，观众能感知到「换段了」。

## 混音

两条路：

- **AE 内混音**（推荐）：音效层分布在各段落合成里，随预合成自动对位；渲音频时 AE 一起混。
  缺点是增益控制在 AE 里，调音量要重渲。
- **ffmpeg/numpy 混**：VO 0 dB、BGM −13 dB、SFX −3~−6 dB，`tanh` 软限幅，峰值留到 0.83。
  适合要反复微调音量的场合。

无论哪条，**交付前必须测峰值**：`ffmpeg -af volumedetect`，`max_volume` 到 `0.0 dB` 就是削波，
用 `-c:v copy -af volume=-2.5dB` 只重编码音频修掉（视频流不重压）。
