# -*- coding: utf-8 -*-
"""扫描成片的「内容密度」，找出空窗 / 死镜头。

扁平 MG 最常见的缺陷不是画错，是**段边界处前后元素都淡尽**，画面只剩底色 0.15~0.25 s。
眼睛容易漏掉，但观众一眼就看到「闪了一下」。

判据：内容占比 < 1% 连续 ≥ 0.15 s 视为空窗。
内容占比 = 与该帧四角中位背景色差异 > 30 的像素比例。

用法:
    python blank_scan.py <video.mp4> [步长=10(帧/秒)] [阈值=1.0]
"""
import sys
import os
import glob
import shutil
import subprocess
import tempfile

import numpy as np
from PIL import Image

# 中文输出在非中文 locale 的 Windows 上会因 cp1252 编码抛 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SRC = sys.argv[1] if len(sys.argv) > 1 else "out.mp4"
FPS = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
THRESH = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
MIN_GAP = 0.15          # 秒

tmp = tempfile.mkdtemp(prefix="blankscan_")
try:
    print("抽帧中（%.0f 帧/秒）…" % FPS, flush=True)
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", SRC,
         "-vf", "fps=%g,scale=480:270" % FPS,
         os.path.join(tmp, "f_%05d.png")],
        check=True, capture_output=True)

    files = sorted(glob.glob(os.path.join(tmp, "f_*.png")))
    if not files:
        print("抽帧失败")
        sys.exit(1)

    ratios = []
    for i, f in enumerate(files):
        a = np.asarray(Image.open(f).convert("RGB")).astype(np.int16)
        corners = np.concatenate([
            a[:6, :6].reshape(-1, 3), a[:6, -6:].reshape(-1, 3),
            a[-6:, :6].reshape(-1, 3), a[-6:, -6:].reshape(-1, 3)])
        bg = np.median(corners, axis=0)
        ratios.append(float((np.abs(a - bg).sum(axis=2) > 30).mean()) * 100)
        if (i + 1) % 50 == 0:
            print("  %d/%d" % (i + 1, len(files)), flush=True)

    n = len(ratios)
    dur = n / FPS
    print("\n共 %d 帧，时长 %.2fs，平均内容占比 %.1f%%" % (n, dur, sum(ratios) / n))

    # 连续低密度区间
    gaps, start = [], None
    for i, v in enumerate(ratios):
        if v < THRESH:
            if start is None:
                start = i
        else:
            if start is not None:
                gaps.append((start, i - 1))
                start = None
    if start is not None:
        gaps.append((start, n - 1))

    gaps = [(s, e) for s, e in gaps if (e - s + 1) / FPS >= MIN_GAP]
    if gaps:
        print("\n=== 空窗（内容占比 < %.1f%%，持续 ≥ %.2fs）===" % (THRESH, MIN_GAP))
        for s, e in gaps:
            print("  %.2fs – %.2fs   持续 %.2fs（%d 帧）" % (
                s / FPS, (e + 1) / FPS, (e - s + 1) / FPS, e - s + 1))
        print("\n修法：① 背景层跨过段边界不淡出 ② 边界加 0.4s 转场元素 "
              "③ 只在同色背景的相邻段之间做重叠")
    else:
        print("\n未发现空窗 ✅")

    # 最空的若干时刻，便于抽查
    order = sorted(range(n), key=lambda i: ratios[i])[:6]
    print("\n=== 密度最低的 6 个时刻 ===")
    for i in sorted(order):
        print("  %6.2fs  内容占比 %5.2f%%" % (i / FPS, ratios[i]))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
