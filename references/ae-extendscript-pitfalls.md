# AE ExtendScript / 构建器静默失败清单

每一条都是实际踩过的：**API 报成功、AE 不报错、画面是错的**。写 JSX 前先过一遍。

## 速查表

| # | 症状 | 根因 | 修法 |
|---|---|---|---|
| 1 | AE 崩溃 / 报 `0::42` | 用 `addShape()` 或探测形状属性 matchName | 弃用形状图层，图形全部 PIL 预渲染 PNG |
| 2 | 位移变成 `[x,x,0]` | Position 是 3 维，用 `dim===2` 判断分支永不成立 | 用 `matchName` 判断，缺维时用当前值补齐 |
| 3 | 图层从 0 秒线性爬升可见 | `setValueAtTime` 默认线性插值；4 ms 保持键被 `round(...,2)` 舍回主键同帧 | 保持键必须 `round(...,3)` |
| 4 | 首帧之前图层一直可见 | 只给了 `[t0,100]` 一个键，AE 向左无限延展 | 显式以 `[0,0]` 开头 |
| 5 | 矩形跑到画面正中 | `addSolid()` 不设 position，默认居中 | `solid()` 必须接 x,y 并 `POS().setValue()` |
| 6 | 图标被放大成原始像素尺寸 | 弹入函数用绝对缩放覆盖了 `png()` 设的基础缩放 | 读 `SCA.value` 作基准按比例弹 |
| 7 | 输出格式不对（PSD/TIFF） | AE 2023 输出模板里**没有 PNG** | 选「多机序列」(PSD) 或 TIFF，ffmpeg 前转 PNG |
| 8 | 只导出第一帧 | `saveFrameToPng` 是异步的，脚本结束即回收实例 | 每帧后 busy-wait 1.5 s，末尾再等 2.5 s |
| 9 | 预合成层整体错位 | `inPoint` 与 `startTime` 绑定，设 inPoint 会推移内容 | 段内保留绝对时间，不裁剪，靠透明度控制显隐 |
| 10 | 打字机把文字擦没了 | Linear Wipe「过渡完成」0=全显示、100=全擦完 | `wipeSet(l,t0,t1,from,to) ` 显式传方向 |
| 11 | 段落边界 0.15–0.25 s 全空 | 前后段元素各自淡尽/未入，背景交叉混成灰 | 让背景层跨过边界，或加转场元素垫过 |
| 12 | 动画整段错位、时间减半 | 时间映射函数被调了两次（`vis2` 里一次、`kf` 里又一次） | 时间点只在 `kf` 里映射一次 |
| 13 | 图标全透明 | Lucide SVG 用 `stroke="currentColor"`，svglib 解析成空白页 | 栅格化前把 `currentColor` 换成 `#000000` |
| 14 | 项目面板一个 PNG 导入 18 遍 | `importFile` 每次新建素材项 | `imp()` 先按路径查已有 footage 再复用 |
| 15 | 某层消失、结束点变成 136 s | 用户在 AE 里拖动过该层，`startTime` 被改 | 探针 dump `startTime/inPoint/outPoint` 排查；只能重建 |
| 16 | 同名效果互相覆盖 | 同一层 `addProperty` 两次 Linear Wipe | 每层只加一次，用多组关键帧 |
| 17 | 每次调用脚本 AE 都开关一次 | `AfterFX.exe -r` 是一次性执行模式 | 合并成一次执行；或启动后把窗口移到屏外 |
| 18 | `函数 indexOf 未定义` | ExtendScript 是 ES3 | 手写 `has(arr,x)` 循环 |
| 19 | `fauxBold` 赋值报只读 | 文字属性只读 | 用字体变体（Bold 字体名）代替 |
| 20 | `-i f_%04d.psd` 报找不到文件 | ffmpeg image2 序列不认 `.psd`（单帧能读） | 用 PIL 批量转 PNG 再编码 |
| 21 | 归档后素材全丢链 | 工程存的是绝对路径，素材挪盘后 `footageMissing` | `it.replace(new File(新路径))` 批量重链（见下） |

## 21. 归档移动素材后必须重链

工程存的是构建时的绝对路径。素材挪到别的盘，打开就是 119 个丢链。三种 API 里只有一种可用：

```javascript
it.replaceSource(...)      // ❌ 函数未定义（这个版本没有此方法）
it.mainSource.file = f     // ❌ 报"它是 readOnly 属性"
it.replace(new File(np))   // ✅ 可用，FootageItem 上的 replace
```

先探测再动手（`for (var k in it)` 列出全部成员），能省一轮试错。批量脚本：

```javascript
for (var i = 1; i <= proj.numItems; i++){
  var it = proj.item(i);
  if (!(it instanceof FootageItem)) continue;
  var p = it.mainSource.file.fsName.split("\\").join("/");
  var np = newPath(p);           // 前缀映射表，注意长前缀在前（audio/v45/ 先于 audio/）
  if (np && np !== p) it.replace(new File(np));
}
app.project.save(...);
```

两个细节：

- **映射表顺序**：`audio/v45/` 必须排在 `audio/` 前面，否则子目录里的文件会被映射到错误的兄弟目录。
- **路径写正斜杠**：JSX 注入中文反斜杠路径时，`"\文"` 会被 JS 当成转义而丢掉反斜杠。一律 `AEP.replace("\\", "/")` 再注入。

重链后必须验：`footageMissing` 计数为 0、所有 `mainSource.file` 都在目标盘、图层数不变。

## 1. 不要用形状图层

AE 的形状图层属性 API 在这个版本里不稳定：探测候选 matchName 会直接让 AE 崩溃（报 `0::42`），
而崩溃后 AE 会弹「上次未正常退出」对话框，点不动会卡死整个自动化。

**结论：所有图形用 PIL 预渲染成 PNG，AE 只做 `layers.add(footage)` + 变换。**
这样 API 面全部落在这个技能已验证安全的调用集内：

```
importFile / layers.add / layer.name / startTime / inPoint / outPoint
property("ADBE Transform Group").property(...)   // Position/Scale/Rotation/Opacity/Anchor
property("ADBE Effect Parade").addProperty(...)  // 只加一次
setValueAtTime / setValue / ease / workAreaStart / saveFrameToPng
```

## 2. 3 维属性判定

```javascript
// 错：AE 的 Position 返回 [x,y,0]，dim 永远是 3
if (dim === 2 && arr[i].length === 3) { v = [arr[i][1], arr[i][2]]; }

// 对：按 matchName 判断，缺维用当前值补
var mn = prop.matchName;
var isPos = (mn === "ADBE Position" || mn === "ADBE Anchor Point");
if (isPos && arr[i].length === 3) { v = [arr[i][1], arr[i][2], 0]; }
```

退化成「把 x 复制三份」时，`[t, 1560, 800]` 会变成 `[1560,1560,0]` —— 图层跑到画布外，
表现为「这个元素从来没出现过」，很容易被误判成配色或层级问题。

## 3+4. 阶梯式可见性

```javascript
// 出现：前 4 ms 保持 0，再跳到目标值 —— 才是硬切
a.push([round(t0 - 0.004, 3), 0]);
a.push([t0, o]);

// 消失：到点保持，之后才归零
a.push([t1, o]);
a.push([t1 + 0.004, 0]);
```

两个必踩的点：

- `round(t0-0.004, 2)` 把 `30.996` 舍回 `31.0`，与主键同帧被 AE 合并 → 斜坡回来了。**必须 3 位小数。**
- 覆盖式关键帧（替代语义）必须从 `[0, 0]` 开始，否则 AE 把第一个键向左无限延展，图层在 t0 之前就一直可见。

「替代式」和「追加式」要分成两个函数：`kfR()` 先 `removeKey` 清空再写，`kf()` 只追加。
把所有透明度覆盖点当成追加写，会出现「淡出后又爬升复活」。

## 11. 分段后最常见的画面缺陷

拆成 shot comp 之后，每段内部元素都是「淡入 … 淡出」，两段在总合成里首尾相接，
边界处就是**前段已淡尽 + 后段未淡入** → 0.15–0.25 s 纯背景，异色背景还会混成灰。

判定标准（`scripts/blank_scan.py`）：内容占比 < 1% 连续 ≥ 0.15 s 即视为空窗。

三种修法，按侵入性排序：

1. 让每段的背景层**跨过段边界**（不淡出），保证永远有底色 + 前段元素余晖。
2. 在边界加一个 0.4 s 的转场元素（扫描光/圆点/色带），成本最低，风格统一。
3. 只在**同色背景**的相邻段之间做重叠（深蓝接深蓝、浅色接浅色）；异色段重叠会变灰，会更糟。

## 12. 时间重映射只能在一个地方做

把旧时间轴压到新时长时，`T(t) = S + (t - B) * K`。这个函数如果在 `vis2()` 里调一次、
而 `vis2()` 内部又走 `kf()`（也调 `T`），就是 `T(T(t))`。

诊断特征非常干净：同一层的**缩放键**（走 `popIn → kf`，单次映射）落在正确时间，
**透明度键**（走 `vis2 → kfR → kf`，双次映射）落在错的位置，两者比值正好是 `K`。

**淡入淡出时长不要乘 `K`。** 0.2 s 的淡入被压成 0.13 s，元素会像「啪」地跳出来。
时间点压缩，感知时长保持。

## 17. AE 反复开关

`AfterFX.exe -r script.jsx` 是一次性执行：跑完 AE 立即退出。建 12 个段落就是开 12 次。

- **减少次数**：把所有 stage 的 JSX 拼成一个大脚本，一次执行（保留单段入口给调试）。
- **隐藏窗口**：`STARTUPINFO` 设 `SW_HIDE` 只能压掉一部分，AE 会自己 `ShowWindow` 顶出来。
  可靠做法是启动后轮询 `EnumWindows` + `GetWindowThreadProcessId`，对本进程的可见窗口
  `SetWindowPos(-32000,-32000)` 移出屏幕。
- 渲染走 `aerender`，本来就无界面，不闪。
