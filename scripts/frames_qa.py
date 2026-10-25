# -*- coding: utf-8 -*-
"""单帧批量导出（QA 只抽关键帧，不导整段序列）。

要点：comp.saveFrameToPng 是异步的，脚本结束实例就被回收 —— 每帧后必须 busy-wait，
末尾再等一会儿，否则只会写出第一张。

用法:
    python frames_qa.py <project.aep> 3,20,40.5,55 [输出目录] [合成名]
"""
import sys
import os
from pathlib import Path


def _load_bridge():
    """Locate ae_bridge.py: vendored beside this script, or via AEBRIDGE_SCRIPTS."""
    cands = [Path(__file__).resolve().parent]
    env = os.environ.get("AEBRIDGE_SCRIPTS")
    if env:
        cands.append(Path(env))
    for c in cands:
        if (c / "ae_bridge.py").is_file():
            sys.path.insert(0, str(c))
            return
    sys.exit("ae_bridge.py not found: put it next to this script, "
             "or set AEBRIDGE_SCRIPTS to its directory")


_load_bridge()
from ae_bridge import run  # noqa: E402

AEP = sys.argv[1] if len(sys.argv) > 1 else "MG.aep"
TS = [float(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else "3,20,40")]
OUT = sys.argv[3] if len(sys.argv) > 3 else "_qa_frames"
COMP = sys.argv[4] if len(sys.argv) > 4 else "总合成"
os.makedirs(OUT, exist_ok=True)

JSX = r"""
app.open(new File("__AEP__"));
var proj = app.project, comp = null;
for (var i = 1; i <= proj.numItems; i++){
  var it = proj.item(i);
  if (it instanceof CompItem && it.name === "__COMP__") { comp = it; break; }
}
if (!comp) throw new Error("找不到合成: __COMP__");
function wait(ms){ var t = (new Date()).getTime(); while ((new Date()).getTime() - t < ms) {} }
var ts = __TS__, ok = 0, err = "";
for (var k = 0; k < ts.length; k++){
  try{
    comp.saveFrameToPng(ts[k], new File("__OUT__/t" + Math.round(ts[k]*10) + ".png"));
    wait(1500);
    ok++;
  }catch(e){ err += ("t=" + ts[k] + ":" + e.message + " "); }
}
wait(2500);
RESULT.ok = ok;
RESULT.err = err || "none";
RESULT.comp = comp.name;
"""

jsx = (JSX.replace("__AEP__", AEP).replace("__COMP__", COMP)
          .replace("__OUT__", OUT)
          .replace("__TS__", "[" + ",".join(str(t) for t in TS) + "]"))
r = run(jsx, timeout=600)
print("合成 %s | 请求 %d 帧 | 调用成功 %s | err: %s" % (
    r.get("comp"), len(TS), r.get("ok"), r.get("err")))

files = sorted(os.listdir(OUT))
print("实际写出 %d 个" % len(files))
for f in files:
    print("   %-14s %7.0f KB" % (f, os.path.getsize(os.path.join(OUT, f)) / 1024))
