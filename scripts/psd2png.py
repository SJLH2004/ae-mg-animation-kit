# -*- coding: utf-8 -*-
"""PSD 序列 -> PNG 序列。

AE 的输出模板里没有 PNG，只能选「多机序列」（分帧 PSD）。PSD 比 TIFF 小一个数量级
（1080p 2250 帧：PSD ≈ 660 MB / TIFF ≈ 18 GB），转成 PNG 后再编码约 377 MB。
ffmpeg 的 image2 序列不认 .psd 扩展名（单帧能读，序列报找不到），所以必须转。

用法:
    python psd2png.py <源目录> <目标目录>
"""
import os
import sys
import glob
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

# 中文输出在非中文 locale 的 Windows 上会因 cp1252 编码抛 UnicodeEncodeError
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SRC = sys.argv[1] if len(sys.argv) > 1 else "out"
DST = sys.argv[2] if len(sys.argv) > 2 else "out_png"
os.makedirs(DST, exist_ok=True)


def conv(p):
    name = os.path.splitext(os.path.basename(p))[0] + ".png"
    out = os.path.join(DST, name)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return 1
    try:
        im = Image.open(p)
        im.load()
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        im.save(out, "PNG", compress_level=1)
        return 1
    except Exception as e:
        print("  失败 %s: %s" % (p, e))
        return 0


files = sorted(glob.glob(os.path.join(SRC, "f_*.psd")))
print("待转换 %d 帧" % len(files), flush=True)
if not files:
    sys.exit(0)

t0 = time.time()
# 用线程池而非进程池：multiprocessing 在 stdin/heredoc 脚本里无法 spawn
with ThreadPoolExecutor(max_workers=8) as ex:
    res = list(ex.map(conv, files))
print("转换成功 %d/%d，用时 %.0fs" % (sum(res), len(files), time.time() - t0))
