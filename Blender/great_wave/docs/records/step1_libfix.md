# 第 1 步记录：测量库与测试的修订（目标与模型用同一种量法；只报告的补充指标）

日期：2026-09-20。环境：Blender 5.2.2 LTS（无界面）、自带 Python 3.13 + numpy；没有安装或下载任何东西，没有写到 `G:/research/Wave Simulation` 和会话临时目录之外，没有改 PYTHONPATH。没有 git，本记录代替 commit。

负责的文件：`src/gw/profile_metrics.py`、`tests/common_test.py`、`tests/test_shape.py`、`tests/test_motion.py`、`tests/run_all.py`、`tests/selfcheck_tests.py`、`tests/selftest_measure.py`（`tests/test_mesh.py` 不需要改）、`docs/measurement_definitions.md`、`docs/tests_readme.md`、本文件。
**没有动**：`tests/thresholds.json`、`gw/frame`、`gw/raster`、`gw/silhouette`、合成浪的解析定义（`tests/fixtures/*`）、`src/contour/*`、`target/*`、`params.json`。

## 0. 结论（三行）

1. 波頭の先 的检测改成「整个悬空波頭上最靠右的点」（最大回撤）。在单瓣波頭上与旧规则**逐位相同**；在指状尺度的 `target/base_contour.json` 上，检测点与 json 接缝的距离从 15.9％ 降到 0.008％，基準輪郭对自己的 S5／S7 现在通过。
2. 新增三组**只报告**的数：尺寸指标 W（放宽 5％／8％ 的合成浪读数恰为 +5.00％／+8.00％，而 spec 档只在 8％ 时报一项）、M6 和「静止保持」的バックログ「定義」读法、S7 两个方向分别打印。都没有阈值，待用户决定。
3. `selftest_measure`（63 项）和 `selfcheck_tests`（17 对）全部通过；**原有的期望、容差、阈值一项都没有改。**

## 1. 做了什么

| 任务 | 做法 | 位置 |
|---|---|---|
| 1 先端规则 | `tip_rule = max_reversal`：在「波頂 → 第一次碰到静水面」这一段里取水平回退量 X(T) − X(D) 最大的一对点（T 在前），T = 波頭の先，D = 最深点。张出的判定仍是「回退 > 0.3％」。旧规则保留为 `tip_rule = first_reversal`，并且每次都算，作为地标 `overhang_onset` 报告。参数都在 `DEFAULT_PARAMS` 里并带说明：`tip_rule`、`tip_min_reversal_pct_h`、`head_lobe_reversal_pct_h`（只用来数瓣）、`segmentation_check_tol_pct_h`。 | `profile_metrics.measure_profile`、`_tip_max_reversal`、`_tip_first_reversal`、`_front_stretch_end`、`count_x_reversals` |
| 1(d) 基準輪郭一致性 | `measure_base_contour` 仍用 json 接缝，同时在同一条折线上跑检测，结果里多一项 `segmentation_check`（三个点各自的距离、最大值、`consistent`）。`test_shape` 报告 `T.seg_*`，距离 > 0.2％ 时把运行标成 **INVALID**。`common_test.summarize` 的结论从两种变成三种：PASS／FAIL／INVALID（有效性不成立 → INVALID；退出码仍非 0）。另给做轮廓的脚本提供 `pm.detect_landmarks()`。 | `profile_metrics.segmentation_check`、`test_shape.segmentation_validity`、`common_test.summarize` |
| 2 尺寸指标 W | 每次 `measure_profile` 都算 `W`：Z = 0.25／0.5／0.75 H 的 `x_back`／`x_inner`／`x_front`、`width_full`、`width_body`（悬空截面）、到波頂铅垂线的距离、o、空洞深度、静水面以上面积；`compare_width_metrics` 给出模型／目标／差／差 ％。`test_shape` 打印成表、写进 `metrics.json`（`W.*` 检查项和 `measurements.W_compare`）、把截面线画在 `overlay_full_1600.png` 上，截面线＋数值表画在新的 `overlay_widths_1600.png` 上。全部标注 `report only - pending user decision`。 | `profile_metrics._width_metrics`、`width_metrics`、`compare_width_metrics`；`test_shape.width_overlay_items`、`width_table_lines` |
| 3 「定義」读法 | `M6.backlog_jump_ratio`：d(k) ÷ 前后各 2 对帧位移的中央値，停止帧前 1 s（= `M5.decel_window_s`）及之后不算；`M5.backlog_hold_max_disp_pct_h`：终幕之后 10 s（300 帧，每 30 帧取样，每个样本都与**终幕帧**比较）的最大轮廓移动量，参考值 0.2％。S7：两个方向各加一组 `INFO` 检查项。 | `test_motion.backlog_jump_ratios`、`measure_backlog_hold`；`test_shape.judge_profile` |
| 4 S5 朝向 | φ 仍是唯一的定义（模型、基準輪郭、M4 都用它）；`crest_to_tip_deg` 进了 `measure_profile`、`measure_sequence`、`position_checks`，`test_shape` 报告 `S5.crest_to_tip_dir_diff_deg`。选择的理由写在 `docs/measurement_definitions.md` §3.4。 | 同上 |
| 5 自测／自检 | `selftest_measure` 新增 C2 组 11 项；`selfcheck_tests` 新增 2 个用例（`widen_x_8pct`、`target_joint_shifted`）和只报告项的期望（`expect_W`、`expect_report`、`expect_verdict`）、放宽扫描表的 W 列。 | 两个脚本 |

## 2. 命令

```powershell
$p = "G:/research/Wave Simulation/blender/great_wave"
& "$p/tools/run_blender.ps1" tests/selftest_measure.py            # 约 70 s
& "$p/tools/run_blender.ps1" tests/selfcheck_tests.py             # 约 3.5 分钟
# 把真实基準輪郭扫成网格再量回来（只为看库的行为；合成浪的 clip 收束会填平扇贝状的下表面，这是夹具的已知限制）
& "$p/tools/run_blender.ps1" tests/test_shape.py -ScriptArgs '--build-script','tests/fixtures/make_synthetic_wave.py','--build-func','build_object','--build-arg',"profile_json=$p/target/base_contour.json",'--tag','swept_base_contour_libfix','--exit-tier','none'
```

## 3. 实测到的事实

### 3.1 先端规则

| 项目 | 结果 |
|---|---|
| 单瓣波頭：新旧规则 | 合成浪解析轮廓 241 个时刻（114 个有张出）：先端、最深点、o、φ 的差 **0**（逐位相同）；第一次张出都在 t = 0.529（o = 0.2226 H）。自测里固定为 61 个时刻。 |
| Houdini 参考 | 已存的 110 条轮廓（`results/step1_prepare/houdini_ref/profiles_H.npz`，full／section 各 55 帧）：新旧规则 0 条不同 → `target/houdini_motion.json` 不受这次修订影响（我没有重跑、也没有改那个文件）。 |
| 波纹／小瓣 | 终幕解析轮廓，波頭上下表面加法向正弦波纹，振幅 0.3／1／2／3％ 画面高：新规则先端位移 0.0000％；旧规则 0.00／3.12／3.54／16.35％。 |
| 浪脚、沿水面的部分 | 合成浪终幕：先端 X 0.3628，谷端 X 0.3895，轮廓末端 X 1.393 → 检测到的先端 X 0.3628。 |
| `target/base_contour.json`（指状尺度） | json：波頂 (1474.9, 223.5)、先端 (2226.5, 785.1)、最深点 (1526.5, 1219.4) px；检测：(1468.7, 223.5)、(2226.5, 784.9)、(1526.5, 1219.4)。距离 **0.240％**／0.008％／0.000％。旧规则的先端在 (1887.5, 550.1)，离 json 先端 15.93％。瓣数：按 1％ 数 2，按 0.3％ 数 4；最大回退量 26.98％ 画面高。 |
| 其它轮廓 | `base_contour_alt_sky_silhouette.json` 0.228／0.001／0.000％；候选 A 的 `base_contour_smooth_r100.json` 0.009／0.012／0.000％（一致）；`_r120` 0.149／0.002／0.000％（一致）；`synthetic_contour.json` 0.0003／0.0001／0.0000％。 |

### 3.2 扫出的真实基準輪郭（`results/20260920_080513_shape_swept_base_contour_libfix/`）

| 检查 | 修订前（`step1_tests.md` 第 4 节） | 修订后 |
|---|---|---|
| S5 位置 | 16.2％ | **0.035％** |
| S7 波頭 mean／p95 | 3.56／12.56 | **0.106／0.671** |
| S7 内側の弧 mean／p95 | 2.32／10.91 | 2.08／7.64（夹具的 clip 收束把扇贝状下表面填平，见图里的品红水平线；不是测量问题） |
| S5 朝向 | −76.4° | −11.5°（φ 落在带瓣的上表面上；「波頂→先端」方向差只有 0.23°） |
| S8 | 125.3° | 128°（基準輪郭对自己 86.4°） |
| 基準輪郭对自己不过的项 | 9 项（含 S5×2、S7×4） | **3 项：S4 向波頂渐缓、S4 顶部无折角、S8**（都是轮廓自身不光滑，属于问题 1，不归本任务） |
| 结论 | FAIL | **INVALID**（原因：波頂接缝与检测相差 0.240％ > 0.2％） |

### 3.3 自测与自检（最终代码）

- `tests/selftest_measure.py`：**63 项，0 项失败**（修订前 52 项；原有 52 项的文字、期望、容差未改，数值与 `step1_measure.md` 的记录相同：exact 全分辨率 0.0155％／0.096°，31 帧序列 h 1.2e-5 H、x_c 1.5e-4 H、o 1.5e-4 H、θ 0.13°、φ 0.064°）。「把真实基準輪郭扫成网格」那一条只报告的日志现在是 S7 p95 背／波頭／内弧 = 0.022／0.67／7.64（修订前波頭 12.56）。
- `tests/selfcheck_tests.py`：**17 对（用例 × 测试）全部符合**。原有 15 对的不通过集合与 `step1_tests.md` 的表完全相同（包括放宽扫描 1.02–1.20 每一行的不通过集合）。

新增部分的结果：

| 用例 | 期望（运行前写下） | 实测 |
|---|---|---|
| 不加缺陷／形状 | W 各量 ±0.3 个百分点以内；结论 PASS | 最大 0.003％；PASS／PASS |
| X 放宽 5％ | z75 宽度、z75 前／后到波頂铅垂线、z50 后、o、空洞深度 = +5 ± 0.3；面积在 (0, 5) | +5.00、+5.00、+5.00、+5.00、+5.00、+5.00；面积 +2.54。spec 档不通过：无 |
| X 放宽 8％（新用例） | 同上 +8；spec 档必须包含 S7 背 mean（来自上次扫描的实测 1.19） | +8.00 ×6；面积 +4.01；spec 档不通过：S7 背 mean = 1.192（与独立预测一致） |
| X 放宽 10％ | +10 | +10.00 ×6；面积 +4.98 |
| 不加缺陷／动态 | M6_backlog ≤ 3；保持 10 s 的移动 ≤ 0.2％ | 1.015；3.7e-15％ |
| 第 40 帧突跳 0.3 H | M6_backlog > 3 | **23.29**（帧 40、41）。〔信息〕前后只取各 1 对时只有 **1.918**，查不出来——这是窗口取 2 的理由 |
| 动画截在 90％ | M6_backlog ≤ 3（截断点在被排除的窗口内）；保持 ≤ 0.2％ | 1.014；3.7e-15％ |
| 目标 json 接缝挪 3.1％（新用例） | 必须含 VALIDITY；结论 INVALID／INVALID | S5 位置 3.008％＋VALIDITY；INVALID／INVALID（`T.seg_head_tip_dist_pct_h` = 3.008） |
| 纯拉伸 | 结论 INVALID／INVALID | INVALID／INVALID |

放宽扫描（截面折线一层）里新加的 W 列：1.02 → +2.00％，1.05 → +5.00％，1.08 → +8.00％，1.10 → +10.00％（z75 宽度、o、空洞深度相同），面积 +1.03／+2.54／+4.02／+4.98％。

- `tests/run_all.py`：在不加缺陷的合成浪上跑通（`results/20260920_075516_all_libfix_run_all_check/`，三个测试两档都 PASS）。

### 3.4 期望有没有改

- **原有的期望、容差、阈值：没有改。** 先端规则的改变没有使任何一项原有期望需要调整（单瓣波頭上新旧规则逐位相同）。
- 新增的期望都是新检查项／新用例，运行前写下，第一次运行即符合。唯一的例外如实记录：我新写的自测项「三角波的面积 = 闭式解」第一次没过（库 1.034795，我的期望 1.034798）。原因是我的期望写错了：面积按定义只算到**谷端**（第一个 Z ≤ 0.3％ 的采样点），不到浪脚尖，差的正是那一小条三角形。改的是这条新期望（减去那条三角形），库没有改；这一项从未以错误的形式进入过任何一次通过的运行。

## 4. 推测（不是实测）

1. 大形轮廓（按 S8 限曲率得到的）应当是单瓣的；候选 A 的光滑轮廓（r100、r120）就是这样（瓣数 1、新旧规则一致、φ ≈ −56°…−58°）。在那种轮廓上，问题 2 会自然消失，S5 的 ±5° 也才有意义。
2. 真实模型如果波頭上表面有比真正空洞还大的凹兜，最大回撤规则会选错；目前看到的轮廓里没有这种情况。
3. W 里 z25、z50 两个高度因为原画的背出了画面，只能反映前面一侧；真正对「太宽」敏感的是 z75 宽度、到波頂铅垂线的距离、o、空洞深度。面积对放宽的反应只有一半左右（左侧被画面裁掉）。

## 5. 建议

1. **正式的大形基準輪郭请用 `pm.detect_landmarks()` 放接缝**（尤其是波頂：平顶宽约 5％，现在的构建脚本和测量库取的位置差 0.24％，刚好超过 0.2％）。否则每次 `test_shape` 都会是 INVALID。
2. 请用户决定：(a) W 要不要设阈值（例如 z75 宽度、o 的相对差），(b) M6 用说明书的读法还是「定義」的读法，(c) 静止保持 10 s／0.2％ 要不要进 `thresholds.json`，(d) 「json 与检测差 > 0.2％ 判 INVALID」是否接受。
3. 第 2 步交付时请同时看 `overlay_widths_1600.png`：数值全过也可能宽 5％。

## 6. 没有做／没有验证

- 真实的浪还不存在；以上都只在合成浪、扫出的基準輪郭和已存的 Houdini 轮廓上验证过。
- 没有重跑 `src/ref/read_houdini_motion.py` 和 `src/contour/build_base_contour.py`（不是我的文件）；它们调用的函数签名没有变（只增加了可选参数和返回字典里的键）。
- 「保持 10 s」在超出 `scene.frame_end` 的帧上依赖 Blender 对动画的外推；导出成 Alembic 之后的保持由播放端决定，这里量不到。

## 7. 图和数据

- `results/20260920_080513_shape_swept_base_contour_libfix/`：`overlay_full_1600.png`、`overlay_widths_1600.png`、`crop_head_region.png`（检测到的先端与 json 先端重合在 (2226, 785) px）、`metrics.json`、`summary.md`。
- 自检（最终代码）：`results/20260920_080108_selfcheck/`（17／17，`selfcheck_table.md`；放宽 8％ 的图：`widen_x_8pct/shape/overlay_widths_1600.png`；突跳的图：`frame_jump/motion/plot_speed_jump.png`，第三栏是 M6_backlog，灰色 × 是被排除的停止前 1 s）。此前的完整运行 `results/20260920_075125_selfcheck/` 数值相同。
- 自测：`results/step1_prepare/measure/selftest_measure_report.json`（63 项；`tip_rule_ripples` 是波纹试验的数值）。
- 我看过的图：扫出的基準輪郭的 `overlay_full_1600.png`、`overlay_widths_1600.png`、`crop_head_region.png`；放宽 8％ 的 `overlay_widths_1600.png`、`overlay_full_1600.png`、`crop_head_tip.png`；突跳用例的 `plot_speed_jump.png`（标题改短前后各一次）。图与数值一致。看图时发现并改掉的两处：M6_backlog 那一栏的标题太长被裁；W 的数值标签在合成浪上盖住了「tip」「deepest」标签（现在 `overlay_full_1600.png` 只画截面线，数值在 `overlay_widths_1600.png`）。
- 临时脚本（不属于工程）：会话临时目录 `scratchpad/libfix/probe1–3.py`（各轮廓上的 json↔检测距离、241 个时刻的新旧规则比较、Houdini 已存轮廓的新旧规则比较）；日志在 `results/logs/probe*_20260920_07*.log`。

## 7b. 最终运行（最终代码；日志 `results/logs/selftest_measure_20260920_080017.log`、`selfcheck_tests_20260920_080108.log`）

| 脚本 | 结果 | 输出 |
|---|---|---|
| `tests/selftest_measure.py` | 63 项，0 项失败，50 s，退出码 0 | `results/step1_prepare/measure/selftest_measure_report.json` |
| `tests/selfcheck_tests.py` | 17 对，0 对不符合，退出码 0 | `results/20260920_080108_selfcheck/`（`selfcheck_table.md`、`selfcheck_report.json`） |

运行经过（没有隐去的部分）：自检一共完整跑了 2 次（`075125`、`080108`，都是 17／17），另有 4 次只跑部分用例（`074438` 6／6、`075913` 2／2、`080429` 1／1、`080521` 4／4）；`selftest_measure` 完整跑了 3 次、`--quick` 1 次，其中 `--quick` 那次有 1 项不过（§3.4 写的那条我自己新加的面积期望），其余全过。两次完整自检之间只改了 `plot_speed_jump.png` 第三栏的标题（原标题太长，左端被裁掉）。最后一次完整自检（`080108`）之后只改了**画图**：W 的数值标签在合成浪上会盖住「tip」「deepest」的标签，所以 `overlay_full_1600.png` 上只画截面线，数值放在 `overlay_widths_1600.png`（`080521` 和 `results/20260920_080513_shape_swept_base_contour_libfix/` 是用最终画图代码出的，数值与之前逐位相同）。

## 8. 接口变化（给其他模块）

函数签名（原有调用方式都仍然有效）：

- `measure_profile(pts_H, params=None, crest_index=None, tip_index=None)`：签名不变。返回字典新增 `tip_source`、`crest_to_tip_deg`、`head_lobes`、`W`、`landmarks['overhang_onset']`；`params` 新增可用键 `tip_rule`（`max_reversal`｜`first_reversal`）、`head_lobe_reversal_pct_h`、`segmentation_check_tol_pct_h`、`width_levels_H`。
- `measure_base_contour(bc, params=None, use_json_segmentation=True, check_detection=True)`：新增 `check_detection`；返回字典新增 `segmentation_check`。
- `measure_sequence(...)`：返回新增 `crest_to_tip_deg` 列。
- `position_checks(...)['S5']`：新增 `dir_definition`、`model_crest_to_tip_deg`、`base_crest_to_tip_deg`、`crest_to_tip_diff_deg`。
- 新函数：`detect_landmarks(pts_H, params=None)`、`segmentation_check(poly, json_metrics, params=None, bc=None)`、`width_metrics(pts_H, metrics=None, params=None)`、`compare_width_metrics(model_W, target_W)`、`count_x_reversals(x, rev)`；常量 `WIDTH_LABEL`。
- `common_test.report_value(..., difference=None, label=None)`；`common_test.summarize` 的 `verdict` 取值 `PASS`｜`FAIL`｜`INVALID`；`TEST_SETTINGS` 新增 `m6_backlog_half_window`、`m6_backlog_exclude_window_s`、`backlog_hold_s`、`backlog_hold_step_frames`、`backlog_hold_reference_pct_h`。
- `test_shape.judge_profile(...)` 返回新增 `w_rows`、`segmentation_check`；`save_images(..., w_rows=None)`；新函数 `segmentation_validity`、`width_overlay_items`、`width_table_lines`、`log_width_table`。`test_motion`：新参数 `--backlog-hold-s`，新函数 `backlog_jump_ratios`、`measure_backlog_hold`；`metrics.json` 新增 `backlog_variants`、`series.backlog_jump_ratio`、`series.backlog_jump_ratio_judged`、`series.crest_to_tip_deg`。
- 新的检查项 id：`S5.crest_to_tip_dir_diff_deg`、`S5.model_head_lobes`、`S7.<段>.model_to_base.{mean,p95}_dev_pct_h`、`S7.<段>.base_to_model.{…}`、`W.<z25|z50|z75>.{width_full_H,width_body_H,front_from_crest_H,inner_from_crest_H,back_from_crest_H,cavity_gap_H}`、`W.o_H`、`W.cavity_depth_H`、`W.area_above_still_water_H2`、`T.seg_crest_dist_pct_h`、`T.seg_head_tip_dist_pct_h`、`T.seg_deepest_dist_pct_h`、`T.base_head_lobes`、`M6.backlog_jump_ratio`、`M6.backlog_within_reference`、`M5.backlog_hold_max_disp_pct_h`、`M5.backlog_hold_within_reference`。
