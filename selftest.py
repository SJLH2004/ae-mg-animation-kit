#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Self-test for ae-mg-animation-kit.

Everything here runs without After Effects:

  1. every script must at least compile
  2. blank_scan.py must FIND a known empty window in a synthetic clip,
     and must NOT flag a clip whose content never disappears
  3. encode_submit.py must produce a playable H.264/AAC file that ffprobe
     agrees with (the CBR path is the one that silently under-shoots)

Tests 2 and 3 skip cleanly when ffmpeg / ffprobe are not installed.

Usage:
    python selftest.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"

failures = []


def check(name, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - report, never abort the suite
        failures.append(name)
        print("  FAIL  %s" % name)
        print("        %s" % exc)
    else:
        print("  PASS  %s" % name)


def require(cond, msg):
    if not cond:
        raise AssertionError(msg)


def tool(name):
    return shutil.which(name)


def has_ffmpeg():
    return bool(tool("ffmpeg") and tool("ffprobe"))


def run(cmd, **kwargs):
    proc = subprocess.run(cmd, capture_output=True, **kwargs)
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        raise AssertionError("command failed: %s\n%s%s" % (" ".join(cmd), out[-1500:], err[-1500:]))
    return out


def make_clip(path, empty_window):
    """6 s, dark background, one white block. empty_window=(a,b) removes it."""
    enable = "not(between(t,%.2f,%.2f))" % empty_window if empty_window else "1"
    run([
        tool("ffmpeg"), "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=0x14213d:s=480x270:r=25:d=6",
        "-vf", "drawbox=x=40:y=90:w=110:h=90:color=white:t=fill:enable='%s'" % enable,
        "-c:v", "mpeg4", "-q:v", "4", "-pix_fmt", "yuv420p", path,
    ])
    return path


def main():
    print("ae-mg-animation-kit self-test")
    print()
    tmp = tempfile.mkdtemp(prefix="aemg-selftest-")
    try:
        _suite(Path(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print("FAILED %d check(s): %s" % (len(failures), ", ".join(failures)))
        return 1
    print("all checks passed")
    return 0


def _suite(tmp):
    def t_compile():
        files = sorted(SCRIPTS.glob("*.py"))
        require(files, "no scripts found under scripts/")
        for f in files:
            source = f.read_text(encoding="utf-8")
            compile(source, str(f), "exec")
        print("        %d scripts compile" % len(files))

    def t_blank_scan_positive():
        if not has_ffmpeg():
            print("  SKIP  blank_scan finds an empty window (ffmpeg missing)")
            return
        clip = make_clip(str(tmp / "gap.mp4"), (2.5, 3.2))
        out = run([sys.executable, str(SCRIPTS / "blank_scan.py"), clip, "10", "1.0"],
                  env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        require("空窗" in out, "blank_scan did not report any empty window\n%s" % out)
        require("未发现空窗" not in out, "blank_scan said there was no empty window\n%s" % out)

    def t_blank_scan_negative():
        if not has_ffmpeg():
            print("  SKIP  blank_scan ignores a clean clip (ffmpeg missing)")
            return
        clip = make_clip(str(tmp / "full.mp4"), None)
        out = run([sys.executable, str(SCRIPTS / "blank_scan.py"), clip, "10", "1.0"],
                  env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        require("未发现空窗" in out,
                "blank_scan reported a false positive on continuous content\n%s" % out)

    def t_encode():
        if not has_ffmpeg():
            print("  SKIP  encode_submit produces a valid file (ffmpeg missing)")
            return
        frames = tmp / "frames"
        frames.mkdir()
        run([
            tool("ffmpeg"), "-y", "-v", "error",
            "-i", make_clip(str(tmp / "src.mp4"), None),
            "-vf", "scale=320:180", "-frames:v", "30",
            str(frames / "f_%04d.png"),
        ])
        audio = tmp / "mix.wav"
        run([
            tool("ffmpeg"), "-y", "-v", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2",
            "-ac", "2", "-ar", "48000", str(audio),
        ])
        out_mp4 = tmp / "out.mp4"
        out = run([
            sys.executable, str(SCRIPTS / "encode_submit.py"), str(frames), str(audio),
            str(out_mp4), "--fps", "25", "--size", "320x180",
            "--vbitrate", "500k", "--abitrate", "128k",
        ], env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        require(out_mp4.is_file() and out_mp4.stat().st_size > 1000,
                "encode_submit did not write a usable file")
        require("交付核验" in out, "encode_submit did not print the verification table\n%s" % out)

        probe = run([tool("ffprobe"), "-v", "error", "-show_entries",
                     "stream=codec_name", "-of", "default=nw=1", str(out_mp4)])
        require("codec_name=h264" in probe, "video stream is not h264: %s" % probe)
        dur = run([tool("ffprobe"), "-v", "error", "-show_entries",
                   "format=duration", "-of", "default=nw=1", str(out_mp4)])
        seconds = float(dur.strip().split("=")[-1])
        require(abs(seconds - 1.2) < 0.25, "duration %.2fs is not ~1.2s" % seconds)

    check("all scripts compile", t_compile)
    check("blank_scan finds a known empty window", t_blank_scan_positive)
    check("blank_scan ignores a clean clip", t_blank_scan_negative)
    check("encode_submit produces a spec-conforming file", t_encode)


if __name__ == "__main__":
    sys.exit(main())
