#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ae_bridge.py — Python <-> After Effects 2023 桥接层（本机实测通过）

三条已验证的能力线：
  1) 驱动正在运行的 AE：AfterFX.exe -r script.jsx   -> 脚本内操作合成/图层/素材
  2) 结果回传：脚本写 JSON 到磁盘 -> Python 读回（用内置 __str，不依赖 JSON）
  3) 批量渲染：aerender.exe（无界面）-> 出图像序列 -> ffmpeg 编码成片

关键约束（踩过的坑都写在里头，别改掉）：
  * .jsx 文件必须是纯 ASCII。中文一律转成 \\uXXXX 再写盘（cjk_escape 自动做）。
  * ExtendScript 读文件按系统编码（GBK），写 JSON 也默认 GBK -> 必须 f.encoding="UTF-8"。
  * 【重要】AE 2023 (23.5) 实测 ExtendScript 里没有 JSON 对象，JSON.stringify 会抛
    '"JSON"未定义'。早期版本这里用了 JSON.stringify，结果写盘被 catch 吞掉、文件为空，
    Python 侧表现为"等不到结果"超时。现在统一用模板内置的 __str() 手工序列化。
  * aerender 的参数是 -s / -e（起始帧/结束帧，含端点），没有 -sframe。
  * aerender 的 -v 5 会报 "Bad value for -verbose"，别加。
  * H.264 输出模块在本机 aerender 下恒失败（-1610153423，错误代码 \\1），
    出片必须走「序列 -> ffmpeg/PR 编码」。
"""
import json
import os
import re
import subprocess
import tempfile
import time

# Windows 控制台/管道默认非 UTF-8（常见 cp1252），直接 print 中文会抛
# UnicodeEncodeError 使脚本以退出码 1 结束；Linux/macOS 默认 UTF-8 不受影响。
# 统一在处理前改掉，保证跨平台输出一致。
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ---------------------------------------------------------------- 环境探测

def find_ae():
    """返回 (afterfx_path, aerender_path)，找不到返回 (None, None)。"""
    roots = [r"C:\Program Files\Adobe", r"C:\Program Files (x86)\Adobe"]
    best = None
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in os.listdir(root):
            if not name.startswith("Adobe After Effects"):
                continue
            exe = os.path.join(root, name, "Support Files", "AfterFX.exe")
            if os.path.exists(exe):
                ver = re.findall(r"\d+", name)
                v = int(ver[0]) if ver else 0
                if best is None or v > best[0]:
                    best = (v, exe)
    if not best:
        return None, None
    d = os.path.dirname(best[1])
    return best[1], os.path.join(d, "aerender.exe")


AFTERFX, AERENDER = find_ae()


def _pick_work():
    """挑一个**纯 ASCII** 的工作目录。

    铁律：AE 的 -r 投放和 ExtendScript 的 File API 都对中文路径不友好。
    曾经把这里改成 tempfile.gettempdir()，结果在中文用户名机器上得到
    C:\\Users\\中文\\AppData\\...，Jsx 写结果文件被 catch 静默吞掉
    -> Python 侧只看到"超时无结果"，极难排查（脚本其实是执行成功的）。
    """
    cands = [os.environ.get("AEBRIDGE_WORK"),
             os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp", "ae_bridge_work"),
             os.path.join(tempfile.gettempdir(), "ae_bridge_work")]
    for c in cands:
        if c and all(ord(ch) < 128 for ch in c):
            return c
    return r"C:\ae_bridge_work"


WORK = _pick_work()


def _win_process_names():
    """Windows 进程名列表。用 Toolhelp32 API，不依赖 tasklist/wmic（两者常被
    安全策略或精简系统禁用，早期版本因调用 tasklist 在受限环境下直接被拦）。"""
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_char * 260)]

    k32 = ctypes.windll.kernel32
    snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snap == -1:
        return []
    names = []
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        ok = k32.Process32First(snap, ctypes.byref(pe))
        while ok:
            names.append(pe.szExeFile.decode("gbk", "replace"))
            ok = k32.Process32Next(snap, ctypes.byref(pe))
    finally:
        k32.CloseHandle(snap)
    return names


def ae_running():
    """AE 主程序是否在跑（-r 驱动运行中的实例需要它）。"""
    try:
        if os.name != "nt":
            return False
        return any(n.lower() == "afterfx.exe" for n in _win_process_names())
    except Exception:
        return False


# ---------------------------------------------------------------- jsx 模板

def cjk_escape(s):
    """把字符串里的非 ASCII 字符转成 \\uXXXX，保证写出的 .jsx 是纯 ASCII。"""
    out = []
    for ch in s:
        o = ord(ch)
        if o > 126:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    return "".join(out)


# 内置序列化：ExtendScript 是 ES3，没有 JSON 对象（AE 2023 实测 JSON 未定义）。
# 支持 string / number / boolean / null / Array / 普通 Object 嵌套，跳过 function/undefined。
TEMPLATE = """(function () {
    var RESULT = {};
    function __esc(s) {
        s = String(s);
        s = s.replace(/\\\\/g, "\\\\\\\\").replace(/"/g, "\\\\\\"");
        s = s.replace(/\\n/g, "\\\\n").replace(/\\r/g, "\\\\r").replace(/\\t/g, "\\\\t");
        return s;
    }
    function __str(v) {
        var t = typeof v, i, a, k;
        if (v === null || v === undefined) { return "null"; }
        if (t === "string") { return "\\"" + __esc(v) + "\\""; }
        if (t === "number" || t === "boolean") { return String(v); }
        if (v instanceof Array) {
            a = [];
            for (i = 0; i < v.length; i++) { a.push(__str(v[i])); }
            return "[" + a.join(",") + "]";
        }
        if (t === "object") {
            a = [];
            for (k in v) {
                if (typeof v[k] !== "function" && v[k] !== undefined) {
                    a.push(__str(k) + ":" + __str(v[k]));
                }
            }
            return "{" + a.join(",") + "}";
        }
        return "\\"" + __esc(v) + "\\"";
    }
    try {
__BODY__
    } catch (e) {
        RESULT.__error = String(e);
    }
    try {
        var f = new File("__OUT__");
        f.encoding = "UTF-8";
        f.open("w");
        f.write(__str(RESULT));
        f.close();
    } catch (e2) { }
})();
"""


def run(body, result_name="ae_result.json", timeout=180, work=WORK, noui=True):
    """
    在 AE 里执行一段 jsx 正文，返回 dict。
    正文里给 RESULT 赋值即可，例如：
        RESULT.layers = comp.numLayers;

    注意事项：
      * 正文里可以直接写中文（会自动转义成 \\uXXXX），但仅限字符串字面量内。
      * 不要写 return / 不要写顶层 function 声明包不住的东西。
      * 大文件导入（几百 MB）会让 AE 主线程卡住 1-2 分钟，timeout 给足。
      * noui=True 时，若 AE 没在运行，会用 -noui 无界面模式拉起它执行，
        避免弹出主界面/崩溃恢复框；AE 已在运行则直接投给现有实例（此时不加 -noui）。
    """
    if not AFTERFX:
        raise RuntimeError("找不到 AfterFX.exe")
    os.makedirs(work, exist_ok=True)
    out_path = os.path.join(work, result_name).replace("\\", "/")
    local_out = os.path.join(work, result_name)

    if os.path.exists(local_out):
        os.remove(local_out)

    jsx = TEMPLATE.replace("__BODY__", cjk_escape(body)).replace("__OUT__", out_path)
    jsx_path = os.path.join(work, "_ae_run.jsx")
    with open(jsx_path, "w", encoding="ascii", errors="ignore") as f:
        f.write(jsx)

    cmd = [AFTERFX]
    if noui and not ae_running():
        cmd.append("-noui")      # headless: no splash, no UI, no crash-recovery dialog
    cmd += ["-r", jsx_path]
    subprocess.run(cmd, capture_output=True)

    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(local_out) and os.path.getsize(local_out) > 0:
            time.sleep(0.3)
            break
        time.sleep(0.3)
    else:
        raise TimeoutError("AE %ss 内没回写结果：%s（AE 弹模态框会卡死，去点掉）"
                           % (timeout, local_out))

    raw = open(local_out, "rb").read()
    for enc in ("utf-8", "gbk", "utf-8-sig"):
        try:
            return json.loads(raw.decode(enc))
        except Exception:
            continue
    return {"__error": "结果 JSON 无法解码", "__raw_head": raw[:200].decode("latin-1")}


# ---------------------------------------------------------------- 渲染

def set_output_module(comp_name, om_keyword="TIFF", out_file=None,
                      rs_keyword="最佳设置", save_as=None, work=WORK):
    """
    在 aep 里给指定合成挂好输出模块并存盘。
    aerender 不带 -output 时会用 aep 里存的路径，这是最稳的落盘方式。
    om_keyword: "TIFF" / "多机序列"（PSD）/ "H.264"（本机恒失败，别用）
    """
    out_file = out_file or os.path.join(work, "out", "frame_[####].tif").replace("\\", "/")
    body = """
    var proj = app.project, comp = null, i, it;
    for (i = 1; i <= proj.numItems; i++) {
        it = proj.item(i);
        if (it instanceof CompItem && it.name === "__COMP__") { comp = it; break; }
    }
    if (!comp) { throw new Error("合成不存在: __COMP__"); }
    var rq = proj.renderQueue;
    while (rq.numItems > 0) { rq.item(rq.numItems).remove(); }
    var rqi = rq.items.add(comp);
    var om = rqi.outputModule(1);
    var names = om.templates, picked = "", t;
    for (t = 0; t < names.length; t++) {
        if (names[t].indexOf("__OMK__") >= 0 && names[t].indexOf("_HIDDEN") < 0) { picked = names[t]; break; }
    }
    if (picked === "") { picked = names[0]; }
    om.applyTemplate(picked);
    RESULT.om = picked;
    var rsN = rqi.templates, s2;
    for (s2 = 0; s2 < rsN.length; s2++) {
        if (rsN[s2].indexOf("__RSK__") >= 0) { rqi.applyTemplate(rsN[s2]); RESULT.rs = rsN[s2]; break; }
    }
    om.file = new File("__OUT__");
    rqi.render = true;
    RESULT.out = om.file.fsName;
    proj.save(new File("__SAVE__"));
    RESULT.saved = true;
    """.replace("__COMP__", comp_name) \
       .replace("__OMK__", cjk_escape(om_keyword)) \
       .replace("__RSK__", cjk_escape(rs_keyword)) \
       .replace("__OUT__", out_file) \
       .replace("__SAVE__", (save_as or os.path.join(work, "ae_render.aep")).replace("\\", "/"))
    return run(body, "ae_om_result.json", work=work)


def render(project, comp=None, start=None, end=None, output=None,
           om_template=None, rs_template=None, timeout=7200):
    """
    调 aerender 渲染。返回 (ok, log_text)。
    推荐：先用 set_output_module 在 aep 里设好 OM，这里就不传 output/om_template。
    """
    if not AERENDER:
        raise RuntimeError("找不到 aerender.exe")
    cmd = [AERENDER, "-project", project]
    if comp:
        cmd += ["-comp", comp]
    if om_template:
        cmd += ["-OMtemplate", om_template]
    if rs_template:
        cmd += ["-RStemplate", rs_template]
    if output:
        cmd += ["-output", output]
    if start is not None:
        cmd += ["-s", str(start)]
    if end is not None:
        cmd += ["-e", str(end)]

    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    log = (p.stdout or b"").decode("gbk", errors="replace")
    ok = ("-1610153423" not in log) and ("错误代码" not in log)
    return ok, log


def encode_seq(pattern, out_mp4, fps=25, crf=20, ffmpeg="ffmpeg"):
    """把 AE 出的图像序列编成 H.264 mp4（H.264 直出失败时的标准兜底）。"""
    cmd = [ffmpeg, "-y", "-framerate", str(fps), "-i", pattern,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf), out_mp4]
    p = subprocess.run(cmd, capture_output=True)
    return p.returncode == 0, (p.stdout or b"").decode("utf-8", errors="replace")[-800:]


# ---------------------------------------------------------------- 自检

if __name__ == "__main__":
    print("AfterFX :", AFTERFX)
    print("aerender:", AERENDER)
    print("AE 运行中:", ae_running())
    if not ae_running():
        print("!! AE 没启动，-r 驱动会失败（AE 必须已经在跑）")
        raise SystemExit(1)

    r = run("""
    var proj = app.project;
    var comp = proj.items.addComp("AEBRIDGE_SELFTEST", 1920, 1080, 1.0, 2, 25);
    comp.layers.addSolid([0.9, 0.2, 0.3], "selftest", 1920, 1080, 1.0, 2);
    RESULT.comp = comp.name;
    RESULT.layers = comp.numLayers;
    RESULT.version = app.version;
    RESULT.hasJSON = (typeof JSON !== "undefined");
    """)
    print("自检结果:", json.dumps(r, ensure_ascii=False))
    ok = r.get("comp") == "AEBRIDGE_SELFTEST" and r.get("layers") == 1
    print("SELFTEST:", "PASS" if ok else "FAIL")
