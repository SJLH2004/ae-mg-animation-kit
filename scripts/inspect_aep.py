# -*- coding: utf-8 -*-
"""只读检查 AE 工程：合成结构 / 图层数 / workArea / 总合成时间线 / 丢链统计。

绝不保存工程。用于审阅用户手改过的 .aep，或排查「某层为什么不见了」。

用法:
    python inspect_aep.py <project.aep> [总合成名]
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
MASTER = sys.argv[2] if len(sys.argv) > 2 else "总合成"

JSX = r"""
app.open(new File("__AEP__"));
var proj = app.project;
var out = [], comps = [], miss = [], nfoot = 0;

for (var i = 1; i <= proj.numItems; i++){
  var it = proj.item(i);
  if (it instanceof FootageItem){
    nfoot++;
    try{ if (it.footageMissing) miss.push(it.name); }catch(e){}
  }
}
for (var i = 1; i <= proj.numItems; i++){
  var it = proj.item(i);
  if (!(it instanceof CompItem)) continue;
  var box = (it.parentFolder && it.parentFolder.name) ? it.parentFolder.name : "(根)";
  comps.push([it.id, it.name, it.width + "x" + it.height, Math.round(it.frameRate),
              it.duration.toFixed(3), it.numLayers, box,
              it.workAreaStart.toFixed(2), it.workAreaDuration.toFixed(2)].join("|"));
}
var m = null;
for (var i = 1; i <= proj.numItems; i++){
  var it = proj.item(i);
  if (it instanceof CompItem && it.name === "__MASTER__") { m = it; break; }
}
if (m){
  out.push("MASTER|" + m.duration.toFixed(3) + "|" + m.frameRate + "|" + m.numLayers);
  for (var L = 1; L <= m.numLayers; L++){
    var l = m.layer(L), src = "";
    try{ if (l.source) src = l.source.name; }catch(e){}
    out.push("L|" + L + "|" + l.name + "|" + src + "|" + l.startTime.toFixed(2) +
             "|" + l.inPoint.toFixed(2) + "|" + l.outPoint.toFixed(2) +
             "|" + (l.enabled ? 1 : 0) + "|" + (l.locked ? 1 : 0) +
             "|" + (l.parent ? l.parent.name : "-"));
  }
}
RESULT.comps = comps;
RESULT.master = out;
RESULT.ncomp = comps.length;
RESULT.nfoot = nfoot;
RESULT.missing = miss.length;
RESULT.missList = miss.join(", ");
RESULT.items = proj.numItems;
"""

r = run(JSX.replace("__AEP__", AEP).replace("__MASTER__", MASTER), timeout=480)

print("工程项 %s | 素材 %s | 合成 %s | 丢链 %s %s" % (
    r.get("items"), r.get("nfoot"), r.get("ncomp"),
    r.get("missing"), r.get("missList") or ""))

print("\n=== 合成 ===")
for c in (r.get("comps") or []):
    p = c.split("|")
    print("  [%3s] %-16s %9s %3sfps %9ss %3s层  WA %s+%s  [%s]" % (
        p[0], p[1], p[2], p[3], p[4], p[5], p[7], p[8], p[6]))

print("\n=== %s ===" % MASTER)
for l in (r.get("master") or []):
    p = l.split("|")
    if p[0] == "MASTER":
        print("  时长 %ss  %sfps  %s 层" % (p[1], p[2], p[3]))
    else:
        print("  %2s. %-16s src=%-16s start=%7s in=%7s out=%7s  en=%s lk=%s parent=%s" % (
            p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9]))

if "__error" in r:
    print("\nERR:", r["__error"])
