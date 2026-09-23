# 第 1 步（准备）— 基础库与工程骨架 记录

日期：2026-09-20　范围：工程骨架、`params.json`、`tests/thresholds.json`、基础库 `src/gw/`、运行脚本、自测。
（基準輪郭、测试脚本、Houdini 运动读取、方法说明由其它记录负责。）

## 1. 做了什么

| 文件 | 内容 |
|---|---|
| `params.json` | H=11 m（允许 10.4–13）、原画路径与尺寸、画框的三个定义值（38.2 / 8.7 / 66.0，其余在代码里导出）、30 fps、285 帧、バックログ区间 [4, 3, 2.5] s、S8 采样间距 1％、Blender 与 Houdini 缓存路径、允许写入的根目录等。每一项都有 `provenance` 和 `comment` |
| `tests/thresholds.json` | S1–S8、M1–M6、G1–G5 共 35 个检查项，每项 `{value, unit, op, provenance, tiers}`；两档：`spec` 与 `user_relaxed_5pct` |
| `src/gw/bootstrap.py` | `add_src_to_path`、`script_args`、`parse_args`、`log`（前缀 `GW`）、`Timer`、`reset_scene`、`finish` |
| `src/gw/paths.py` | 全部路径、`load_params/param`、`load_thresholds/threshold/check_threshold/format_check`、写入保护 `assert_writable/ensure_dir/ensure_parent`、`results_run_dir`、`write_json` |
| `src/gw/frame.py` | `Frame`：px ↔ pct ↔ H ↔ m、长度单位 pct_h、`cam_print()` 数值、`make_cam_print()`（bpy） |
| `src/gw/imgio.py` | `load_image_rgb/rgba`（bpy）、`save_png`（纯 python 编码器，无色彩管理）、`read_png`（纯 python 解码器）、`roundtrip_max_abs_diff`、`to_gray`、`rgb_to_hsv` |
| `src/gw/draw.py` | 粗线、折线（开/闭/虚线/NaN 断开）、圆、十字、各种标记、矩形、多边形填充与掩膜、掩膜/图像半透明叠加、掩膜轮廓、裁剪、缩放（box / nearest / bilinear）、`View`（放大局部图 + 坐标映射）、hstack / vstack / grid、ASCII 位图字体 |
| `src/gw/plot.py` | `line_plot`（坐标轴、刻度、网格、图例、竖线/横线标记、区间底色、NaN 断开、等比例）、`multi_plot`（多图叠放并对齐 x 轴） |
| `tools/run_blender.ps1` | 无界面运行 + 完整日志 + 只显示前缀行 + 退出码 |
| `tests/selftest_foundation.py` | 本记录的自测 |
| `src/contour/__init__.py`、`src/ref/__init__.py` | 空包，供后续 agent 使用 |
| 空目录 | `target/`、`target/candidates/a`、`target/candidates/b`、`results/step1_prepare/`、`docs/records/`、`tests/fixtures/` |

## 2. 自测结果

运行：`tools/run_blender.ps1 tests/selftest_foundation.py`（Blender 5.2.2 LTS，Python 3.13.13，numpy 2.3.4）。
**87 项检查，0 项失败**，退出码 0。完整结果：`results/step1_prepare/foundation/selftest_report.json`，日志：`results/logs/selftest_foundation_*.log`。

| 组 | 检查 | 结果 |
|---|---|---|
| frame | 导出常数对比说明书 §4 的四舍五入值（1.5152 / 2.2540 / −0.861 / 1.393 / 1.132 / −0.383、1％=0.01515 H=0.167 m、2％=0.0303 H=0.333 m） | 全部一致 |
| frame | S1 38.2％/8.7％ → (0.000000, 1.000000)；上から 74.7％ → Z=0；S2 39.5％/46.3％ → (+0.029302, 0.430303)；S6 59.2％/33.0％ → (+0.473348, 0.631818) | 通过 |
| frame | 由 S6 算出：张出 47.33％ H（说明书 47％），方向 水平向下 37.88°（说明书 38°） | 一致 |
| frame | px→H→px、px→m→px 往返（1000 个随机点）最大误差 4.5e−13 px | 通过 |
| params / thresholds | 每项都有 value/provenance/comment；35 个阈值格式正确；`check_threshold` 同时给出两档判定 | 通过 |
| imgio | 0..255 灰阶 PNG（纯 python 写）经 bpy 读回完全相等，`max|v·255 − round| = 1.5e−5` → **bpy 的 `.pixels` 就是存储字节 / 255，没有经过色彩管理** | 通过 |
| imgio | gray / RGB / RGBA × 4 种滤波：纯 python 读回差 0，bpy 读回差 0 | 通过 |
| imgio | 原画 3859×2594：读入 0.24 s；全分辨率存 PNG 0.91 s（17.4 MB），`read_png` 读回差 0（0.22 s），bpy 读回差 0（0.41 s） | 通过 |
| imgio | 用户的两张 WebP 参考图可解码：1257×606、1200×591 | 通过 |
| paths | 往允许目录之外写 → `PermissionError`；把原画当写入目标 → `PermissionError` | 通过 |
| draw | 线宽、抗锯齿线的墨量（141.9 vs 理想 141.8 px²）、多边形掩膜面积（矩形 800/800，圆 31428 vs πr² 31416）、box 缩小 = 块平均、nearest = `np.repeat`、`View` 坐标往返、半透明叠加、灰度图 / 越界裁剪 / NaN 断开 / 画进 numpy 切片 | 通过 |
| plot | 曲线确实画出、空 / 单点 / 全 NaN 不报错、`multi_plot` 对齐图例宽度、等比例下单位圆宽高比 1.000 | 通过 |
| CAM_print | `world_to_camera_view` 与 `Frame.H_to_px` 的最大差 0.0015 px；视线方向 (0, 1, 0) | 通过 |
| CAM_print | **真实的无界面渲染**（Workbench，3859×2594，1.6 s）：X∈[0, X_S6]、Z∈[0, H] 的黑色矩形，边缘实测 (1474.10, 2284.60, 225.53, 1937.70) px，理论 (1474.14, 2284.53, 225.68, 1937.72) px，最大差 0.14 px | 通过 |

另外用 Windows 自带的 .NET `System.Drawing` 解码同一张 JPG，抽查 5 个像素 (100,100)、(1474,225)、(1524,1201)、(2284,856)、(3000,500)，RGB 与 bpy 读到的**完全相同**（同时确认了行的上下方向）。

## 3. 说明书地标的目视确认（任务第 8 条）

图：`landmarks_overlay.png`（全分辨率）、`landmarks_overlay_1600.png`、三张 3 倍放大局部图。红圈半径 = 画面高的 1％ 和 2％，灰色网格 = 1％。青色 × 是**粗略**像素探针（简单的颜色阈值，只作为目视之外的一个参考数；S1–S6 的正式复测属于基準輪郭那一项）。

### 实测到的事实

| 地标 | 说明书位置 (px) | 目视 | 粗略探针 | 与说明书之差（画面高的 ％） |
|---|---|---|---|---|
| S1 波頂 38.2％/8.7％ | (1474.1, 225.7) | 标记落在大浪顶部的轮廓线上；Z=H 的黄线与轮廓线上缘相切 | 轮廓线上缘最高行 y=224 px；说明书那一列的上缘也是 y=224，线粗 5 px | dy = −0.06％；x 见下 |
| S2 内側の弧の最深点 39.5％/46.3％ | (1524.3, 1201.0) | 标记落在波腹（蓝）与天空的分界线上，且在该分界线最靠左的一段 | 最靠左的分界 x=1527.0，y=1217.5；分界线在 y=1188..1247 这 59 行内都在 2 px 之内（近似竖直） | dx = +0.10％，dy = +0.64％ |
| S6 含爪最右点 59.2％/33.0％ | (2284.5, 856.0) | 标记落在最右那根爪尖的轮廓线上 | 轮廓线右缘 (2288.0, 856.7) | dx = +0.13％，dy = +0.02％ |

- **S1 的水平位置无法唯一确定**：大浪的顶部是一段平台。轮廓线上缘在最高行 2 px 之内的列是 x = 1365..1504 px，宽 139 px = 画面高的 5.36％。说明书的 x = 1474.1 px 位于这段平台**之内**，靠右端（距右端 30 px）；平台的中点是 x = 1435.9 px（37.21％），比说明书的位置靠左 38 px = 画面高的 1.47％。竖直方向没有问题。这里只报告，不改说明书的数值。
- S2、S6 与说明书之差都小于画面高的 1％。
- 谷的水面线（上から 74.7％）没有对应的探针，只是画了线；S3 由基準輪郭那一项复测。

### 推测

- S1 的「左 38.2％」很可能是之前的像素分析在平台上取的某一个点（例如平台右段或背的曲率开始变化处）；按「最高点」的字面定义，平台内任何一点都同样成立，所以 S1 的左右容许误差（2％）实际上比平台宽度（5.36％）还小，测试时波頂的 x 需要一个明确的取法（例如沿用说明书的 38.2％ 作为铅垂线的定义，而不是从网格上找最高点）。
- S2 的分界线在最深点附近接近竖直（约 2.3％ 高的范围内 x 变化 ≤ 2 px），所以「最深点」的 y 同样不敏感；dy = +0.64％ 属于这种不确定性。

### 建议

- 测试里 S1 的水平误差建议这样量：网格轮廓在 Z 最大处如果也是平台，取平台与说明书铅垂线 X=0 的关系来判定，并把平台范围一起报告；具体取法请用户确认。
- 基準輪郭那一项复测 S1 时，把平台的左右端点一并列出。

## 4. 需要用户知道 / 决定的事项

1. **「5％」的解释尚未确认。** `tests/thresholds.json` 的 `user_relaxed_5pct` 档按「位置类容许误差 = 画面高的 5％、S3 = ±5％、其余不变」实现，测试两档都报告。
2. **バックログ主表没有读。** `provenance: "backlog"` 只是转述说明书的说法，没有与表格核对。S8 的 15°、M1–M6 的出处说明书没有明说，分别标为 backlog（依据 §5 表头与 §10.4 推断）和 spec initial value，并在 `comment` 里写明。
3. **S2、S3 的阈值写法有歧义**：S2「≤ 画面高的 2％」按欧氏距离实现（同时报告 dx、dz）；S3「±2％」按图高的百分点实现（64–68），若指相对 2％ 则是 66 ± 1.32。测试输出原始数值，两种读法都能判断。
4. 编排脚本给出的小数 `frame_w = 2.254066`、`x_left = −0.861053`、`x_right = 1.393013` 与它自己的公式算出来的 2.254036 / −0.861042 / 1.392994 不一致（差 3e−5 H ≈ 0.05 px，四舍五入到说明书的位数后相同）。代码以公式为准。
5. 机器上没有 git，「每完成一项一个 commit」目前做不到。
6. 大文件目录改为 `blender/great_wave/blend/`（见 README §2）。

## 5. 结果图路径

`G:/research/Wave Simulation/blender/great_wave/results/step1_prepare/foundation/`

- `landmarks_overlay.png`（3859×2594）、`landmarks_overlay_1600.png`
- `crop_S1_crest.png`（1557×1167）、`crop_S2_inner_arc.png`（1557×1170）、`crop_S6_claw_tip.png`（1557×1170），均为 3 倍放大、范围 ±10％ × ±7.5％ 图高
- `cam_print_render_check.png`（CAM_print 的真实渲染）
- `demo_draw.png`、`font_sheet.png`、`demo_plot.png`（曲线是合成的演示数据，不是实测）、`demo_plot_equal_aspect.png`
- `selftest_report.json`
