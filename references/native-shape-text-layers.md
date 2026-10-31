# 原生可编辑工程：Shape / Text 图层 API 与"零素材"工作流

> 触发场景：交付要求「工程必须可编辑，元素不能是图片」。
> 目标：**全片零位图**，文本层可改字、形状层可改路径，改一个滑块全片联动。
> 本文所有结论都是在 AE 2023 (23.5x52) + Windows 上实测得到的。

---

## 0. 为什么必须这么做

预渲染 PNG + `layers.add(footage)` 是最省事的做法，但交付物在 AE 里**本质是一堆贴图**：
改一个字要重新出图，改一个颜色要重新出图，对方一打开就知道是"图片拼的"。
原生 Shape/Text 图层把整个工程的"可改造成本"降到接近零，这是评分表里
「工程打包与提交规范」那几分真正的分水岭。

实测规模参考（24s / 1280x720 / 6 段）：**75 个文本层 + 86 个形状层 + 1021 个关键帧，0 个位图**。

---

## 1. 创建形状图层的正确姿势

```js
var l = comp.layers.addShape();            // 空形状层
var root = l.property("ADBE Root Vectors Group");
var grp  = root.addProperty("ADBE Vector Group");      // 「组」
var g    = grp.property("ADBE Vectors Group");          // 组内的内容容器
```

所有几何/填充/描边都加在 `g` 里。**顺序决定渲染结果**，AE 的求值顺序是从上到下：

```
路径 (Rect / Ellipse / Path)  →  Trim / Repeater / Offset  →  Fill  →  Stroke
```

### 1.1 常用 addProperty 的 matchName

| 内容 | matchName | 关键子属性 |
|---|---|---|
| 矩形 | `ADBE Vector Shape - Rect` | `ADBE Vector Rect Size` (2D) / `ADBE Vector Rect Position` / `ADBE Vector Rect Roundness` |
| 椭圆 | `ADBE Vector Shape - Ellipse` | `ADBE Vector Ellipse Size` (2D) / `ADBE Vector Ellipse Position` |
| 自由路径 | `ADBE Vector Shape - Group` | `ADBE Vector Shape`（传一个 `new Shape()`） |
| 填充 | `ADBE Vector Graphic - Fill` | `ADBE Vector Fill Color` / `ADBE Vector Fill Opacity` |
| 描边 | `ADBE Vector Graphic - Stroke` | `ADBE Vector Stroke Color` / `ADBE Vector Stroke Width` / `ADBE Vector Stroke Line Cap` / `ADBE Vector Stroke Opacity` |
| 修剪路径 | `ADBE Vector Filter - Trim` | `ADBE Vector Trim Start` / `ADBE Vector Trim End` / `ADBE Vector Trim Offset` |
| 中继器 | `ADBE Vector Filter - Repeater` | `ADBE Vector Repeater Copies` / `ADBE Vector Repeater Offset` / `ADBE Vector Repeater Transform` → 其下 `ADBE Vector Repeater Position` / `ADBE Vector Repeater Rotation` |

> **锚点约定**：`addShape()` 新建图层，图层原点 = anchor。
> 矩形/椭圆的 `Position` 是**相对图层原点**的偏移，所以：
> - 居中图形 → `Rect Position = [0,0]`
> - **从左端生长**的横条 → `Rect Position = [w/2, 0]`，之后 scale X 0→100
> - **从底端生长**的竖条 → `Rect Position = [0, -h/2]`
> - **绕端点旋转**的指针 → `Rect Position = [0, -h/2]`，之后 ROT 0→N
> 把偏移写进 `Position` 而不是去改 anchor，代码更短且不会和 `popIn` 的 scale 打架。

---

## 2. 【必踩】Trim / Repeater 加完必须 moveTo

`addProperty` 永远追加到**最后**。如果组里已经有 Fill/Stroke，
新加的 Trim 会排在它们后面 → **完全不生效**，而 `setValue` 一点错都不报。

```js
// ✗ 静默失效：Ellipse, Stroke, Trim
grp.addProperty("ADBE Vector Filter - Trim");

// ✓ 正确：先算出第一个 Graphic 的索引，把修饰器挪到它前面
function _graphicIndex(grp){
  for (var i = 1; i <= grp.numProperties; i++){
    var mn = grp.property(i).matchName;
    if (mn === "ADBE Vector Graphic - Fill" || mn === "ADBE Vector Graphic - Stroke") return i;
  }
  return grp.numProperties + 1;
}
var t = grp.addProperty("ADBE Vector Filter - Trim");
t.property("ADBE Vector Trim End").setValue(65);
t.moveTo(_graphicIndex(grp));      // 关键这一行
```

### 2.1 【致命】moveTo 之后，原来的对象引用失效

`moveTo()` 之后再用旧的 `t` 去 `.property(...)`，报错是
`在需要数字、数组或属性的位置找到类型为"Error"的对象`。
**不是属性名写错**，是引用过期了。

**修法：函数返回索引号，不要返回属性对象；后续访问用 matchName 重新查。**

```js
function trimP(grp){                 // 重新拿 Trim 对象
  for (var i = 1; i <= grp.numProperties; i++)
    if (grp.property(i).matchName === "ADBE Vector Filter - Trim") return grp.property(i);
  return null;
}
function trimOf(grp, s0, e0){        // 设值 + 挪位置，返回索引
  var t = grp.addProperty("ADBE Vector Filter - Trim");
  t.property("ADBE Vector Trim Start").setValue(s0);
  t.property("ADBE Vector Trim End").setValue(e0);
  var gi = _graphicIndex(grp);
  t.moveTo(gi);
  return gi;                          // ← 返回 int
}
// 之后要做动画，重新查：
kf(trimP(grp).property("ADBE Vector Trim End"), [[t0, 0], [t1, 100]], 34);
```

---

## 3. 环形图 / 饼图（Trim Paths 正统做法）

```js
// 底环
ringS(comp, "底环", 264, 34, LGREY, 384, 412, 100);
// 每一段一条独立图层，靠 Trim Start/End 切
var seg = ringS(comp, "弧睡眠", 264, 34, PURPLE, 384, 412, 100);
ROT(seg).setValue(-90);                       // 起点挪到 12 点
var g = seg.property("ADBE Root Vectors Group").property(1).property("ADBE Vectors Group");
trimOf(g, startPct, startPct);                // 初始长度为 0
kf(trimP(g).property("ADBE Vector Trim End"), [[t0, startPct], [t0+0.55, endPct]], 34);
```

- **起点**：AE 的 Ellipse 路径起点在 3 点方向，`ROT(-90)` 挪到 12 点。
- **段间留缝**：`start = 累计 + 0.5`、`end = 累计 + 本段 - 0.5`（单位 %），视觉上才有分段感。
- 每段一条图层 = 每段可单独改色、单独延时，比"一个形状多段"好维护得多。

## 4. 折线图（贝塞尔 + Trim）

```js
function smoothS(comp, name, pts, col, sw){    // Catmull-Rom → 贝塞尔切线
  var n = pts.length, vs = [], it = [], ot = [], k = 0.34;
  for (var i = 0; i < n; i++){
    vs.push(pts[i]);
    var p0 = pts[i === 0 ? 0 : i - 1], p2 = pts[i === n-1 ? n-1 : i+1];
    var tx = (p2[0]-p0[0])*k, ty = (p2[1]-p0[1])*k;
    ot.push([tx, ty]); it.push([-tx, -ty]);
  }
  var sh = new Shape();
  sh.vertices = vs; sh.inTangents = it; sh.outTangents = ot; sh.closed = false;
  // ... addProperty("ADBE Vector Shape - Group") 后 setValue(sh)
}
```
描边本身**不能带圆角**（Line Join 设 ROUND 即可），再加 Trim 从 0→100 生成"描绘"动画。
顶点圆点单独 `ellS`，按 x 位置错开 0.03s 弹入。

> 折线**不要**用弹性缓动（overshoot 会画出数据里不存在的峰），
> 用 `infl=34` 的普通缓动即可。

---

## 5. 文本图层

```js
var l = comp.layers.addText("我的一天");
var tp = l.property("ADBE Text Properties").property("ADBE Text Document");
var td = tp.value;                 // 必须读出来改，再 setValue 整体写回
td.font = "MicrosoftYaHei-Bold";
td.fontSize = 78;
td.fillColor = [0.106, 0.141, 0.212];
td.applyFill = true;
td.tracking = 18;                  // 单位 1/1000 em
td.justification = ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
```

- `tracking` 是**千分之一 em**：中文标题 8~20，英文小标 300~420 才有"字距感"。
- 右对齐做成「数字 + 单位」的经典版式：数字 `txR` 固定右边界、单位 `txL` 固定左边界，
  计数字符串变长时**向左生长**，单位纹丝不动。

### 5.1 【必踩】aerender 里字体会 fallback，而且不报错

`td.font` 设一个不存在的名字，**读回来还是你设的那个名字**（AE 只是记字符串），
但渲染时静默替换成默认宋体。判断唯一办法是**渲一帧看图**。

实测（Windows 10 中文版，AE 23.5，aerender）：

| 可用 ✓ | 不可用（fallback 宋体）✗ |
|---|---|
| `MicrosoftYaHei` / `MicrosoftYaHei-Bold` | `AlibabaPuHuiTi-Heavy`（otf/CFF 全系列） |
| `DengXian` / `DengXian-Bold` | `DINPro-Bold`（otf） |
| `SimHei` | `Bahnschrift*`（可变字体） |
| `SegoeUI` / `SegoeUI-Bold` | `ArialMT` / `Arial-Bold` |
| `Consolas-Bold` / `Impact` | `HYZhongHeiTi-197` |
| `SourceHanSansJP-Bold` / `Montserrat-*` | 任何 `.otf` 装置在中文字体目录的第三方字体 |

**结论：中文字体只用 Windows 自带的 TTF（雅黑 / 等线 / 黑体），数字用 Segoe UI / Consolas / Impact。**
`.otf` 字体在 GUI 里能正常显示，一经 `aerender` 就废——这条只有肉眼验收能发现。

### 5.2 数值滚动（Slider + 表达式）

```js
var fx = nm.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
fx.name = "val";
fx.property(1).setValueAtTime(t0, 0);
fx.property(1).setValueAtTime(t1, 1825);
nm.property("ADBE Text Properties").property("ADBE Text Document").expression =
   "Math.round(effect(\"val\")(1)).toString()";
```
这是「改一个数全片联动」的入口：被问"这个数字怎么来的"，你指一下滑块。

---

## 6. 投影（不用图层样式）

`layer.property("ADBE Layer Styles")` 在 ExtendScript 里不稳。
最可靠的是**复制形状、偏移、压暗、降透明**：

```js
function softShadow(l, dy, a){
  var s = l.duplicate();
  var p = POS(s).value;
  POS(s).setValue([p[0], p[1] + dy]);         // 只在 s 还没有关键帧时可用
  OPA(s).setValue(a);
  // 遍历组，把 Fill 颜色改成 [0.12,0.14,0.2]
  s.moveAfter(l);
  return s;
}
```

### 6.1 【致命】softShadow 必须在 popIn / vis2 **之前**调用

`setValue()` 在**已有关键帧**的属性上会抛
`无法使用关键帧在属性上调用 setValue()`。
所以顺序是：`rectS()` → `softShadow()`（此时无关键帧，setValue 可用）→ `popIn()` → `vis2()`。
**但复制品不会自动获得之后加的关键帧**，它会永远可见 —— 表现为"某处莫名有个灰块"。
必须手动补：`if (csh) vis2(csh, t0, t1, fi, fo);`

---

## 7. 用脚本搭工程的工程学

1. **报错要带行号**。`ae_bridge.py` 的 catch 只存 `String(e)`，定位全靠猜。
   在模板里加 `RESULT.__line = e.line`，一次就能定位。
2. **格式化占位符要机器校验**。Python 手拼 JSX 时 `%d` 撞上 float 会
   `TypeError: %d format: a real number is required`，漏参数则错位。
   交付前跑一遍 AST 扫描：
   ```python
   for node in ast.walk(ast.parse(src)):
       if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
           n = len(re.findall(r'%(?!%)\d*\.?\d*[dsf]', node.left.value))
           m = len(node.right.elts) if isinstance(node.right, ast.Tuple) else 1
           if n != m: print(node.lineno, n, m)
   ```
3. **段与段之间用"交叉叠化"，不要留空，也不要让两段大字正面重叠**。
   规则：上一段元素在 `t1` 前 0.3s 淡出完，下一段在 `t1 - 0.1s` 开始淡入；
   同时**两段的文字不要落在同一 y 区间**，否则叠化时会读成一行乱字。
4. **交付前必扫空窗**：`ffmpeg -vf fps=5` 抽帧 + 标准差 < 3 判定空白。

---

## 8. 目视验收清单

- [ ] 环/柱/折线是否真的画满（Trim 顺序对不对）
- [ ] 数字与单位是否重叠（右对齐版式）
- [ ] 字体是黑体还是莫名变宋体
- [ ] 有没有"永远亮着的灰块"（阴影层缺 vis2）
- [ ] 段间有没有 1 帧以上的空场
- [ ] 右上角编号/小标有没有被别的元素压住
