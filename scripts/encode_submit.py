# -*- coding: utf-8 -*-
"""按交付规格编码 + 核验。

扁平 MG 画面吃不满 VBR 目标码率（-b:v 3000k 两遍实测只出 1.1 Mbps），
必须用 CBR：minrate=maxrate 且 nal-hrd=cbr，才锁得住 ~3 Mbps。

用法:
    python encode_submit.py <帧目录> <音频文件> <输出.mp4>
        [--fps 50] [--size 1280x720] [--vbitrate 3000k]
        [--abitrate 192k] [--gain -2.5dB] [--max-dur 45]

帧目录里需有 f_%04d.png（可用 psd2png.py 从 PSD 转来）。
--gain 用于修 AE 内混音常见的削波（峰值 0.0 dB 时给 -2.5dB）。
"""
import argparse
import os
import re
import subprocess
import sys

# 中文输出在非中文 locale 的 Windows 上会因 cp1252 编码抛 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


ap = argparse.ArgumentParser()
ap.add_argument("frames")
ap.add_argument("audio")
ap.add_argument("out")
ap.add_argument("--fps", default="50")
ap.add_argument("--size", default="1280x720")
ap.add_argument("--vbitrate", default="3000k")
ap.add_argument("--abitrate", default="192k")
ap.add_argument("--gain", default="0dB")
ap.add_argument("--max-dur", default=None)
ap.add_argument("--first", default="f_%04d.png")
a = ap.parse_args()

# 帧数自检
nums = [int(re.search(r"(\d+)", f).group(1)) for f in os.listdir(a.frames)
        if re.fullmatch(r"f_\d+\.png", f)]
if not nums:
    print("帧目录里没有 f_0000.png 形式的文件:", a.frames)
    sys.exit(1)
n = max(nums) + 1
print("帧数 %d，按 %s fps 约 %.2fs" % (n, a.fps, n / float(a.fps)))

cmd = ["ffmpeg", "-loglevel", "error", "-y",
       "-framerate", a.fps, "-i", os.path.join(a.frames, a.first),
       "-i", a.audio,
       "-vf", "scale=%s:flags=lanczos" % a.size.replace("x", ":"),
       "-af", "volume=%s" % a.gain,
       "-c:v", "libx264", "-preset", "slow",
       "-b:v", a.vbitrate, "-minrate", a.vbitrate, "-maxrate", a.vbitrate,
       "-bufsize", str(int(a.vbitrate.rstrip("k")) * 2) + "k",
       "-x264-params", "nal-hrd=cbr:force-cfr=1",
       "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", a.abitrate, "-ar", "48000", "-ac", "2",
       "-shortest", "-movflags", "+faststart"]
if a.max_dur:
    cmd += ["-t", str(a.max_dur)]
cmd.append(a.out)

print("编码中…", flush=True)
r = run(cmd)
if r.returncode != 0:
    print("编码失败:\n", r.stderr[-2000:])
    sys.exit(1)
print("完成:", a.out)

# ---- 核验 ----
p = run(["ffprobe", "-v", "error",
         "-show_entries", "stream=codec_name,width,height,r_frame_rate,bit_rate,sample_rate,channels",
         "-show_entries", "format=duration,bit_rate,size",
         "-of", "default=nw=1", a.out])
info = {}
for line in p.stdout.strip().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        info.setdefault(k, v)

v = run(["ffmpeg", "-i", a.out, "-map", "0:a", "-af", "volumedetect", "-f", "null", "-"])
peak = re.search(r"max_volume:\s*(-?[\d.]+) dB", v.stderr)
mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", v.stderr)

print("\n=== 交付核验 ===")
print("  编码      ", info.get("codec_name"))
print("  分辨率    ", "%sx%s" % (info.get("width"), info.get("height")))
print("  帧率      ", info.get("r_frame_rate"))
print("  时长      ", info.get("duration"), "s")
print("  视频码率  ", round(int(info.get("bit_rate", 0)) / 1000), "kbps"
      if info.get("bit_rate") else "-")
print("  音频      ", info.get("sample_rate"), "Hz", info.get("channels"), "ch")
print("  峰值      ", (peak.group(1) + " dB") if peak else "-",
      " 均值", (mean.group(1) + " dB") if mean else "-")
print("  文件大小  ", round(int(info.get("size", 0)) / 1048576, 2), "MB")

warn = []
if peak and float(peak.group(1)) >= -0.1:
    warn.append("峰值触顶，有削波风险 → 加 --gain -2.5dB 重跑")
if a.max_dur and info.get("duration") and float(info["duration"]) > float(a.max_dur):
    warn.append("时长超标：%s > %s" % (info["duration"], a.max_dur))
if warn:
    print("\n⚠  " + "\n⚠  ".join(warn))
else:
    print("\n✅ 未发现硬性问题")
