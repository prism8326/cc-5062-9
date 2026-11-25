# idxpaint

严格停留在**调色板索引空间**的绘画与导出工具。画布保存整数索引，颜色阶梯 `Ramp`
只选择“第几个色阶索引”，抖色层决定具体索引和误差；任何环节都不会先把作品转成真彩色再量化。

## 图形入口（主要使用方式）

图形窗口是 `viewer/viewer.html`：

```bash
# 方式一：直接用浏览器打开
viewer/viewer.html

# 方式二：启动本地静态服务器
./run_gui.sh
# 然后访问 http://127.0.0.1:8000/viewer/viewer.html
```

窗口支持：

1. 在“色表”下拉框实际选择 `demo / grayscale / sepia / spectrum` 颜色表；
2. 选择 `ordered`（坐标锚定 Bayer）或 `diffusion`（Floyd–Steinberg 误差传播）；
3. 选择 `Ramp(1,2,3,4)`、完整阶梯、当前点选索引或透明索引；
4. 点击“画横向渐变 / ordered + diffusion 对照”，或用渐变工具在画布上从左向右拖出压力变化；
5. 画布逐索引查询色表并实际绘制，因此能看到索引色块和抖色纹理；
6. 点击调色板行选择单色阶梯；使用“反转并重排色表”做前后差分，再点撤销，原索引和等待下一行扩散的残差会一起还原；
7. 导出 `.idx.json`、color-type-3 索引 PNG 和 index→RGBA 映射 JSON。导出只读取索引数组与色表，不读取界面当前 RGB 缓存；
8. 非法尺寸、文件或运算异常显示在窗口的红色提示区，不会静默伪报成功。

浏览器侧的实际运算在 `viewer/paint-core.js`，不依赖远程服务或前端框架。

## 索引画布接口与职责边界

- `idxpaint/index_canvas.py`：`IndexCanvas` / `IndexSnapshot`，只负责尺寸、索引字节、透明索引、锁和前后差分。
- `idxpaint/canvas.py`：兼容旧入口 `IndexedCanvas(width, height, palette, transparent_index=...)`，把调色板映射附在索引画布上。
- `idxpaint/palette.py`：`Palette` 保存颜色项；`PaletteView` / `PaletteDisplay` 负责显示和导出映射。重复 RGBA 项仍是不同索引。
- `idxpaint/brush.py`：`Ramp.indices` 明确颜色阶梯就是一组调色板索引。
- `idxpaint/dither.py`：`OrderedDither` 与 `DitherDecision` 是纯抖色决策。
- `idxpaint/diffusion.py`：`DiffusionCursor` / `ErrorSnapshot` 是独立误差传播游标和残差快照，不把残差塞进索引图。
- `idxpaint/history.py`：`PaintHistory` 组合索引快照、误差快照、调色板快照和重排映射。换色盘后撤销时，原索引与下一行残差一起还原。
- `idxpaint/painting.py`：`IndexPainting` 是给图形/脚本调用方使用的门面；旧的 `IndexedCanvas`、`PaintEngine`、`reorder_palette` 入口保持兼容。

### 等价性口径

调色板 `keep_appearance` 重排返回 old-index → new-index 映射 `m`。前后状态满足：

```text
after[y,x] = m[before[y,x]]
```

并且每个像素经各自色表解析出的 RGBA 不变。`keep_identity` 则要求存储索引逐字节不变。
透明索引也只是一个普通可映射索引，重排时随映射移动。

## 净目录执行与执行证据

检查不需要手改示例数据。推荐在新建临时目录中运行：

```bash
tmpdir="$(mktemp -d)"
python3 run.py verify --out-dir "$tmpdir/evidence"
```

该命令会实际完成：

- 新建索引画并绘制 ordered / diffusion 渐变；
- 保存并重新载入 `.idx.json` + 索引 PNG，逐字节核对索引；
- 制造真实的下一行 FS 残差；
- 做 `keep_appearance` 调色板重排，核对索引值与 old→new 导出映射；
- 撤销并核对原索引字节、透明索引和 `ErrorSnapshot`；
- 在输出目录写入 `evidence.json` 与 `export_mapping.json`。

只有全部断言通过，证据文件才会记录 `"status": "passed"`。

运行全部 Python 旧样例测试：

```bash
python3 -m unittest discover -s tests
node --check viewer/paint-core.js
node --check viewer/paint-app.js
```

## 命令行（辅助入口）

```bash
python3 run.py demo --mode ordered --out "$(mktemp -d)/demo"
python3 run.py demo --mode diffusion --tile 8 --out "$(mktemp -d)/demo-diff"
python3 run.py inspect examples/demo_ordered --rect 0 0 31 15
python3 run.py verify --out-dir ./evidence-out
```

CLI 用于生成样例、检查原始索引和自动化核验；索引绘画的主要操作入口是上面的图形窗口。
