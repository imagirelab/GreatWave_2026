# 第 1 步记录：测量层加固（针对 `results/step1_prepare/verify_tests/` 的审查）

- 日期：2026-09-20　环境：Blender 5.2.2 LTS 无界面，自带 Python 3.13 + numpy。没有安装或下载任何东西；没有写到 `G:/research/Wave Simulation` 和会话临时目录之外；没有改 PYTHONPATH；没有 git，本记录代替 commit。
- 我负责并改动的文件：`src/gw/profile_metrics.py`、`src/gw/silhouette.py`、`src/gw/raster.py`、`src/gw/frame.py`（**只改了模块说明里的三个小数**）、`tests/selftest_measure.py`、`docs/measurement_definitions.md`、本文件。
- **没有动**：`tests/thresholds.json`（值、运算符、档位都没碰）、`tests/test_*.py`、`tests/common_test.py`、`tests/selfcheck_tests.py`、`tests/fixtures/*`、`target/*`、`params.json`、相机取景、轮廓几何、`src/contour/*`、`src/ref/*`。
- 改前的副本在会话临时目录 `scratchpad/harden_measure/orig/`。

## 0. 结论（先说）

1. 审查指出的六类「测量层看不见／悄悄处理」的情况，现在**全部被数出来并写进返回值**；S1–S8 的**判定值和判定定义一项没改**，新增的都是只报告的量，是否判定留给测试层和用户。
2. `tests/selftest_measure.py`：**88 项，0 项失败，退出码 0**（原有 63 项的名称、顺序、期望、容差都没改，全部仍然通过；新增 25 项）。`tests/selfcheck_tests.py`：**17 对，0 对不符，退出码 0**（见第 5 节）。
3. 三件需要编排者／用户知道的实测事实：
   (a) **正式基準輪郭自己在新的「折线自身转角」上读 19.1°**（背，(944, 376) px 附近；判定用的 S8 读 10.3°）。这个量只能报告，不能直接拿 15° 当阈值。
   (b) 审查里的「20° 逆曲率折角」在 443 点的扫掠截面上，折线上真实存在的角只有 12.5°（20° 减去该顶点本来就要转的 7.5°），任何 15° 的规则都抓不到；短窗口读 11.6°（干净时 8.3°）。在细折线上同样的缺陷读 18°（自测）。
   (c) 目标在 0.5 h 高度被画面左边框裁掉，所以任务里指定的纵横比（0.5 h 处宽度 ÷ h）对正式目标是「从边框量的」，放宽＋压低时只读 +3.3％；我另外给了 0.75 h 处的纵横比，读 +8.1％。

## 1. 做了什么（对应任务 1–8）

| # | 内容 | 位置 |
|---|---|---|
| 1 | 非有限顶点：`mesh_world_triangles` 和 `mask_from_triangles` 显式去掉用到 NaN／inf 顶点的三角形并计数，`info['n_nonfinite_vertices']`、`info['n_dropped_triangles']`、`info['nonfinite_vertex_indices']`；`mesh_world_triangles` 在 `y_range` 过滤**之前**数（否则 NaN 的 Y 会被那个过滤悄悄吃掉），并给每个对象的分项；`silhouette_mask`／`profile_of_objects` 的 `info` 顶层合并两级计数；`profiles_over_frames` 每帧带这两个数。新函数 `silhouette.drop_nonfinite_triangles`。 | `silhouette.py` |
| 2 | 脱离的分量：`raster.largest_component(mask, connectivity, speck_max_area_px, max_listed)` 返回 `n_removed`、`removed`（面积、`bbox_px`、`kind`）、碎屑／孤岛的个数和面积；`extract_profile` 按分辨率算界限（`SPECK_AREA_PX_FULL_RES` = 25 px，`speck_area_limit_px(rect)`），并给每个被去掉的分量加 `bbox_H`、`centre_H`。 | `raster.py`、`silhouette.py` |
| 3 | 谷水位：`metrics['trough_level_H']` 改为「最深点（无张出时为波頂）到轮廓末端之间的最低 Z」，`metrics['reached_still_water']`（容差 = `trough_tol_pct_h` = 0.3％ 画面高），地标 `trough_lowest`，`trough_level_above_still_pct_h`、`h_from_model_trough`；旧定义保留为 `trough_run_median_H`。`position_checks` 新增顶层键 **`S3_from_model_trough`**，`S3` 里也放了对应的数。`measure_sequence` 多两列。 | `profile_metrics.py` |
| 4 | 不抵消的形状描述量 `metrics['shape']`（各自 h 的 0.25／0.5／0.75 处的截面、全部 ÷ h、o/h、空洞深/h、纵横比）＋ `compare_shape_descriptors`；S7 每段加带符号的法向偏差（正 = 模型在目标浪体之外）。都只报告。 | `profile_metrics.py` |
| 5 | S8 盲点：`S8['max_vertex_window_turn_deg']`、`S8['vertex_window_turn']`（分段／先端区／跨先端／短窗口）；`max_unexcluded_deg` 里加一个放在先端上的采样点（`tip_junction_deg`；旧值 `max_unexcluded_without_tip_junction_deg`）。判定用的 `max_tangent_diff_deg`、`_junction_s`／`_junction_diff`、S4 的波頂折角判断都没变。 | `profile_metrics.py` |
| 6 | `get_params`：只捕获「这一项不存在」；`params.json` 写坏、`measure_params` 不是对象、参数名不认识、间距不是数都抛异常；返回值和 `measure_profile` 结果里都有 `non_default_params`。`_frame_h()` 的静默回退也去掉了。 | `profile_metrics.py` |
| 7 | `frame.py` 模块说明：2.254066 → **2.254036**，−0.861053 → **−0.861042**，+1.393013 → **+1.392994**（代码一个字没动；`Frame.__init__` 里这三个量本来就是由 100/66 × 3859/2594 和 38.2％ 算出来的，不是写死的，所以只有说明文字是错的）。 | `frame.py` |
| 8 | 自测新增 K 组（17 项，纯 numpy）和 J 组（8 项，经网格和遮罩＋一次经 Blender 的 Shape Key）。 | `tests/selftest_measure.py` |

命令：

```powershell
$p = "G:/research/Wave Simulation/blender/great_wave"
& "$p/tools/run_blender.ps1" tests/selftest_measure.py      # 约 60–75 s
& "$p/tools/run_blender.ps1" tests/selfcheck_tests.py       # 约 3 分钟
# 审查里的缺陷用新键重新量（不经过 test_shape，只看测量层）
& "$p/tools/run_blender.ps1" "$p/results/step1_prepare/harden_measure/scripts/mesh_attacks_new_keys.py"
& "G:/SteamLibrary/steamapps/common/Blender/5.2/python/bin/python.exe" "$p/results/step1_prepare/harden_measure/scripts/polyline_attacks_new_keys.py"
& "G:/SteamLibrary/steamapps/common/Blender/5.2/python/bin/python.exe" "$p/results/step1_prepare/harden_measure/scripts/pointed_tip_new_keys.py"
```

## 2. 实测到的事实

### 2.1 审查里的缺陷，用新键重新量（正式轮廓扫成网格，`lift_clip`，全分辨率；`results/step1_prepare/harden_measure/mesh_attacks_new_keys.json`）

| 缺陷（审查的名字） | 以前 | 现在测量层给出的 |
|---|---|---|
| NaN 顶点（`nan_vertex=1`） | 判定表与干净运行逐位相同，没有任何提示 | `n_nonfinite_vertices` = **1**，`n_dropped_triangles` = **6**；指标仍与干净运行相同（所以必须看计数） |
| 空洞里的孤岛（`island=1`） | 只有一个总数 `removed_area_px` = 57,311，没有位置、没有分类 | `n_removed` = 1，`n_removed_islands` = **1**，面积 57,311 px，`bbox_H` = [0.17, 0.22, 0.30, 0.37]（与构造的 0.17–0.30 H × 0.22–0.37 H 一致）；指标不变 |
| 海面抬高 3％（`floor_pct=3`） | S3 = +0.034（通过），没有任何一项报 | `trough_level_H` = 0.04545，`reached_still_water` = **False**，S3 = +0.034，**`S3_from_model_trough` = −2.966** |
| 宽 5％＋矮 1.9％（`wide_low:5:1.9`） | spec 档不报；W.z75 宽度读 **−5.22％**（方向反了） | o/h **+8.33％**、空洞深/h **+8.07％**、`aspect_ratio_h75` **+8.09％**、h75 后距/h +7.90％、h75 宽/h +8.09％（不加缺陷时：+0.19／−0.04／−0.02／−0.19／−0.02）；`aspect_ratio`（0.5 h，被画面裁）+3.28，`comparable = false`。带符号 S7：背 −0.508（无符号 0.802；p05 −1.85，p95 +0.60）、波頭 −0.628（0.922）、内側の弧 +0.630（0.637） |
| 只放宽 5％（`widen_x:5`） | spec 档不报 | 同一组量读 +5.21／+4.96／+4.98／+4.80／+4.98；带符号 S7 三段全正：+0.777／+0.536／+0.258 |
| 背上 17° 折角、落在相位之间（`back_kink:17:worst`） | 判定 13.96°（通过） | 判定 13.96°（没改）；折线自身转角：背 **16.61°**（干净时 13.11°），短窗口 15.34°（干净 8.30°） |
| 背上 20° 逆曲率折角（`back_kink:20:against`） | 判定 11.26°（通过） | 1％ 窗口 13.11°（与干净时相同），短窗口 **11.64°**（干净 8.30°）——见 0.3(b)：折线上真实的角是 12.5° |
| 背上 20° 折角（`back_kink:20:worst`） | 判定 16.34°（不过） | 判定 16.34°；窗口 19.29°，短窗口 18.17° |
| 先端尖角（截掉先端 ±2.0％ 弧长换成两端切线的交点，折角 38.3°；折线层，1769 点截面；`pointed_tip_new_keys_stdout.txt`） | 判定 10.31°，`max_unexcluded_deg` 10.31° | 判定 10.31°（没改）；**`max_unexcluded_deg` = 38.25°**（`tip_junction_deg` −38.25°，不含先端采样点的旧值 10.31°）；窗口：先端区／跨先端 38.25°，排除区之外 14.93° |
| 先端排除区里的鼓包（`inner_bulge:2.5:1.5:tipzone`，折线层） | 判定 46.5°，不排除 46.5° | 不排除 **93.3°**，跨先端窗口 93.3° |

干净的扫掠（443 点截面）上：判定 11.25°，`max_unexcluded_deg` 11.25°（先端采样点 −9.36°），`max_vertex_window_turn_deg` 16.51°（背 13.11／波頭 15.92／内側の弧 16.51）。窗口读数比判定值大，是因为顶点间距 0.80％ < 窗口 1％，一个闭窗口里能装两个顶点（每个约 8.3°）；1769 点截面上读 14.93°。

### 2.2 正式基準輪郭自己（`target/base_contour.json`，折线层，json 接缝分段）

| 量 | 值 |
|---|---|
| `trough_level_H`／`reached_still_water` | 0.0／True |
| `shape`：o/h、空洞深/h | 0.4315、0.3881 |
| `aspect_ratio`（0.5 h）／是否被裁 | 0.9017／**是**（背在 Z = 0.509 H 碰左边框） |
| `aspect_ratio_h75`／是否被裁 | 0.8909／否 |
| S8 判定／`max_unexcluded_deg`／`tip_junction_deg` | 10.31°／10.31°／−9.71° |
| `max_vertex_window_turn_deg`（1％ 窗口） | **19.15°**，在背上 (944, 376) px；分段：背 19.15／波頭 10.12／内側の弧 11.06；先端区 9.99，跨先端 9.80 |
| 短窗口 0.5％／0.25％ | 14.16°／**19.91°**（(930, 383) px：三个相邻顶点 −3.2°、−7.5°、−7.0°、−2.2°，随后反向 +2.8°、+4.6°——手绘的背上的一个小 S 弯，曲率半径约 19 px；这一点也是此前 S7 背的最差点） |
| `non_default_params` | {} |

### 2.3 `get_params`

- 改前：`params.json` 写坏（多一个逗号）时，`get_params()` 不报错、返回全默认值；`_frame_h()` 返回 100/66。（改前的模块放在一个没有 `params.json` 的目录里就能跑，计时脚本正是这样用的。）
- 改后（自测 K 组）：写坏 → `JSONDecodeError`；`measure_params` 不是对象 → `TypeError`；名字不认识（`s8_tip_exclusion_pct` 少了 `_h`）→ `ValueError`；间距 `"one"` → `ValueError`；两项都不存在 → 间距 1.0、其余默认、`non_default_params == {}`；`params.json` 里改了间距 1.5 和 `trough_tol_pct_h` 0.5 → 两项都列出、`source = 'params.json'`；调用时覆盖 `s8_tip_exclusion_pct_h = 3` → 列出、`source = 'override'`，与默认值相同的覆盖不列。
- 工程里现有的调用（`test_shape` 把 `get_params()` 的结果原样传回、`read_houdini_motion` 传 `{"theta_window_pct_h": …}`、自测传 `{"tip_rule": …}`）都合法，不受名字检查影响。

### 2.4 自测（最终代码，日志 `results/logs/selftest_measure_20260920_100906.log`，报告 `results/step1_prepare/measure/selftest_measure_report.json`）

**88 项，0 项失败，57 s，退出码 0。** 与改前的报告逐项比较：前 63 项名称和顺序完全相同、全部通过；「详情」文字有变化的 6 项——3 项只是耗时（机器上同时有别的 Blender 进程）、1 项是 `largest_component` 的返回字典多了键、2 项是 `max_unexcluded_deg` 从 48.54° 变成 66.82°（合成浪薄縁上多出的那个先端采样点，属于设计内的变化；这两项检查判的是判定值 4.34°／4.38° 和 `tip_turn_deg`，都没变）。

新增 25 项的要点（期望都写在第一次运行之前，见代码里的注释；第一次完整运行即全部通过）：

| 检查 | 期望 | 实测 |
|---|---|---|
| 宽 1.05＋矮 1.9％ 的折线：`shape` 各项 | 每项 +8.112％（= 1.05 ÷ (1 − 1.9 × 0.0151515) − 1） | 11 项，最大偏差 0.0072 个百分点；绝对高度的 W.z75 宽度 **−4.34％**（闭式 −4.3％）；S3 −1.900 |
| 同上，经合成浪的网格和遮罩（半分辨率） | +8.11 ± 0.3 | 9 项，最大偏差 0.009；W.z75 宽度 −0.68％；S1.dz、S3 −1.900；带符号 S7 背／波頭／内側の弧 −0.348／−0.910／+0.649（无符号 0.519／1.062／0.666） |
| 带符号 S7 的符号 | 只放宽：三段全正、背 = 无符号值；只压低：背、波頭为负；同时：背 p05 < 0 < p95 且 \|带符号\| ≪ 无符号 | +0.880／+0.465／+0.434；−0.930／−1.209／（内側の弧 +0.144）；背 −0.040 对 0.709，p05 −1.293，p95 +1.172 |
| 符号与「点在多边形内」的独立判断 | 一致 | 9 组最大差 4.5e-5％ |
| 抬高 3％（折线／网格） | S3 不变，`S3_from_model_trough` = S3 − 3 | 折线：−3.0000（差 < 1e-9）；网格：−3.000，谷水位 3.000％ |
| 容差 | 0.29％ 算到达，0.31％ 不算 | 符合 |
| 光滑钝头路径（每 1％ 最多转 8°） | 判定 = 窗口 = 8° | 8.000／8.200 |
| 先端 40° 尖角 | 判定和旧的不排除值仍为 8°，新的 > 40° | 8.00／8.00 → 43.07，跨先端 43.83 |
| 17° 折角在相位之间／在采样点上 | 判定 < 15／= 17；窗口都是 17 | 14.895／17.000；17.000／17.000 |
| 20° 逆 8°/％ 的弯 | 判定、1％ 窗口 ≈ 12；0.5％ ≈ 16；0.25％ ≈ 18 | 9.52、11.80、15.80、17.80（光滑路径 8.20／4.20／2.20） |
| NaN 顶点（numpy／Blender Shape Key） | 1 个顶点；三角形数 = 用到它的个数 | 6／6（Blender 路径：49,504 个三角形里去掉 6 个）；遮罩 0 px 变化、指标差 0 |
| 孤岛＋碎屑（全／半分辨率） | 1 孤岛 1 碎屑；界限 25／6.25 px；`bbox_H` 准到 1 px | 孤岛 20,349 px（期望 20,518），`bbox_H` [0.2003, 0.2498, 0.2698, 0.3497]；碎屑 16 px；半分辨率 5,074 px／4 px，界限 6.253 |

看过的图：`results/step1_prepare/measure/hardening_island_floor.png`（孤岛的红框正好套住空洞里那块、碎屑的橙框在波頭右侧的天空里、沿水面的青色线在绿色虚线 Z = 0 之上 3％；文字是 ASCII、没有被裁）。第一次出的图上碎屑的标签超出右边界、也看不出海面抬高（没有 Z = 0 参考线），改了两次画图代码，数值没有变。

### 2.5 耗时

6,482 点（1 px 间距）的轮廓：`measure_profile` 4 ms → 6 ms，`s7_deviation` 0.151 s → 0.148 s（`scripts/timing_old_vs_new.py`，各 5 次平均）。光栅化路径只多了一次 `np.isfinite`。

## 3. 推测（不是实测）

- 真实的第 2 步模型（样条截面、顶点间距远小于 1％）上，`max_vertex_window_turn_deg` 应当接近判定值；它在 443 点夹具上偏大只是顶点间距的缘故。没有真实模型，无法验证。
- 基準輪郭背上那处 19.9° 的小 S 弯多半来自手绘轮廓的追踪，而不是原画的浪形；如果轮廓组之后再做一次平滑，它会消失。我没有改轮廓。
- 孤岛「与主体在投影里相连」的情形（贴着浪体的第二个对象）这一层看不到；我没有构造这种例子去量它会怎样影响 S7。

## 4. 建议

1. 测试层（下一位）：把 `info['n_nonfinite_vertices'] > 0`、`components['n_removed_islands'] > 0`、`reached_still_water == False`、`non_default_params != {}` 做成有效性（INVALID）或至少显眼的警告；碎屑只报告。
2. `S3_from_model_trough.height_err_pct_h` 值得按 S3 同样的 ±2％ 判（需要用户同意；阈值文件不归我改）。
3. 「太宽／不够高」：用 `shape` 的 `aspect_ratio_h75`、`o_over_h`、`cavity_depth_over_h`、`h75.back_from_crest_over_h`（相对目标的 ％ 差）来判，比绝对高度的 W 可靠；阈值待用户定。0.5 h 的纵横比对正式目标不可比，不要用它判。
4. S8：`max_unexcluded_deg` 现在包含先端上的一个采样点，测试里如果要对先端设上限，用 `tip_junction_deg` 或 `vertex_window_turn['across_tip_deg']`；大形钝头约 10°，薄縁合成浪 67°。不要直接给 `max_vertex_window_turn_deg` 设 15°（目标自己 19.1°）。
5. `test_shape` 里 S3 的备注文字「above the measured water run」现在对应的是「最深点之后的最低点」，请顺手改一下措辞。

## 5. 下游检查（`tests/selfcheck_tests.py`）

| 运行 | 代码状态 | 结果 | 输出 |
|---|---|---|---|
| 第 1 次 | 库的全部改动已完成；之后只改了 `_vertex_window_report` 里分段最大值的算法（Python 循环 → numpy，数值相同）和自测的画图代码 | **17 对，0 对不符，退出码 0** | `results/20260920_100235_selfcheck/`，日志 `results/logs/selfcheck_tests_20260920_100234.log` |
| 第 2 次（**最终代码**，在最后一次 `selftest_measure` 之后跑的） | 本记录描述的全部改动 | **17 对，0 对不符，退出码 0**；不通过集合与第 1 次、与 `step1_libfix.md`／`step1_proof.md` 记录的相同 | `results/20260920_101014_selfcheck/`，日志 `results/logs/selfcheck_tests_20260920_101014.log` |

`selftest_measure` 一共完整跑了 3 次（`100009`：88／0；`100715`：88／0；`100906`：88／0，最终代码），另有一次不经 Blender、只跑 K 组的运行（17／0）。三次之间改的只有：分段最大值的 numpy 化、示意图的画法、一处检查名称里的 `%%`。没有任何一次出现不过的项，也没有为了通过而改过期望。

## 6. 接口（给测试层；键名照任务书）

见 `docs/measurement_definitions.md` §1、§2、§3（谷水位行）、§3.2、§3.3、§3.4、§3.9、§3.10。摘要：

- `info['n_nonfinite_vertices']`、`info['n_dropped_triangles']`（`mesh_world_triangles` 的第三个返回值、`mask_from_triangles`／`silhouette_mask`／`profile_of_objects` 的 `info` 顶层；`profiles_over_frames` 每帧的字典）。
- `profile['components']`：`removed_area_px`、`n_removed`、`n_removed_specks`、`removed_specks_area_px`、`n_removed_islands`、`removed_islands_area_px`、`speck_max_area_px`、`speck_area_px_full_res`、`removed[]`（`area_px`、`kind`、`bbox_px`、`bbox_H`、`centre_H`）、`removed_list_truncated`；原有的 `n_components`、`largest_area_px`、`second_largest_area_px`、`largest_bbox` 不变。
- `metrics['trough_level_H']`（**语义变了**）、`metrics['reached_still_water']`、`metrics['trough_level_above_still_pct_h']`、`metrics['h_from_model_trough']`、`metrics['trough_run_median_H']`（旧语义）、`metrics['reached_still_water_tol_pct_h']`、`landmarks['trough_lowest']`。
- `position_checks(...)['S3_from_model_trough']`（顶层，字段同 S3：`height_pct_h`、`height_err_pct_h` …）；`['S3']` 里新增 `height_err_from_model_trough_pct_h`、`reached_still_water`。
- `metrics['shape']`、`pm.shape_descriptors()`、`pm.compare_shape_descriptors(model_shape, target_shape)`（行的格式同 `compare_width_metrics`，另有 `frac_of_h`）。
- `s7[段]['signed_mean_dev_pct_h']`，以及 `model_to_base`／`base_to_model` 里的 `signed_mean_pct_h`、`signed_median_pct_h`、`signed_p05_pct_h`、`signed_p95_pct_h`、`frac_model_outside`；`pm.signed_point_polyline_distance()`。
- `S8['max_vertex_window_turn_deg']`（标量，什么都不排除）、`S8['vertex_window_turn']`、`S8['tip_junction_deg']`、`S8['max_unexcluded_without_tip_junction_deg']`；`pm.vertex_window_turns(C, lo, hi, window)`。
- `pm.get_params()['non_default_params']`、`metrics['non_default_params']`、`pm.non_default_params()`；新参数 `shape_levels_frac_h`、`s8_vertex_short_windows_pct_h`；常量 `pm.S8_SPACING_DEFAULT_PCT_H`、`pm.SHAPE_LABEL`、`silhouette.SPECK_AREA_PX_FULL_RES`。

## 7. 没有做／没有验证

- 没有改任何测试脚本，所以 `test_shape`／`test_motion`／`test_mesh` 目前还**不会**因为上面这些新键而判 FAIL／INVALID——那是下一位的工作。
- 没有重跑 `src/ref/read_houdini_motion.py`（810 MB 的 Alembic）和 `src/contour/*`；它们调用的函数签名没有变，传入的覆盖参数名都在 `DEFAULT_PARAMS` 里。
- 真实的浪还不存在；以上只在合成浪、正式轮廓的扫掠网格和手工折线上验证过。
- `max_vertex_window_turn_deg` 在像素模式（`exact=False`）的轮廓上没有单独评估噪声。
