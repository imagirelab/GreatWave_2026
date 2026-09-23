# 第 1 步记录：基準輪郭 的裁决与合并（正式版）

- 日期：2026-09-20　环境：Blender 5.2.2 LTS 无界面运行，自带 Python 3.13 + numpy（没有安装或下载任何东西；没有写到 `G:/research/Wave Simulation` 和会话临时目录之外；没有改 PYTHONPATH）。
- 负责范围：`src/contour/build_base_contour.py`、`src/contour/base_contour_params.json`、`target/base_contour.json`、`target/base_contour_overlay.png`、`results/step1_prepare/contour_final/`、`docs/base_contour_report.md`、本文件。没有改动其他人的文件（只 import 了 `gw.*`、`contour.method_a_lib` 和测试库 `gw.profile_metrics`）。
- 详细内容（事实 / 推测 / 建议、不确定区间、人工给出的值）见 **`docs/base_contour_report.md`**。本文件只记「做了什么、结果、没过的项、图在哪」。

## 1. 做了什么

1. 读了说明书全文、基础库、两份候选的代码 / 记录 / 叠加图；看了原画和两份候选的放大图。
2. 把 A、B 画在同一张图上，沿轮廓算 A–B 距离（分段 平均 / p95 / 最大），画出距离–弧长曲线；找出相差 > 0.5％ 的区间（看得见的 4 处 ＋ 补全段 1 处），每处做放大图、**看原画**后裁决（V1–V5），裁决和理由写进 `base_contour_params.json`。
3. 另外检查了任务点名的地方：爪是否真的去掉、连的是不是爪根；有没有切进浪体；波頭右上的泡沫/云；背在画面左端；波頂；波頭下面转入内側の弧 的腋部；内側の弧 进入手前の浪 的地方；补全段及其标记；谷的水位。
4. 写了可重建的构建脚本：最终几何＝候选 B ＋（裁决为 A 的区间拼入 A，当前为 0 处）＋ 背左端的读法（参数）＋ 补全段重新标记；分段、2 px 重采样、地标、重测、自身 S8、厚度、独立的墨线外缘检查、低通诊断（用测试库自己的 S7/S8 定义）、叠加图和 16 张局部图。
5. 逐张看了全部输出图（叠加图、5 张裁决图、16 张局部图、3 张诊断图、曲线图），并用 8–12 倍的临时放大图核对了报告里写到的几处细节（分叉点、先端瓣圆头、(1607,285) 的折角、A 的补全圆弧露出天空处）。

## 2. 命令

```powershell
# 正式构建（约 18 s）
& "G:/research/Wave Simulation/blender/great_wave/tools/run_blender.ps1" src/contour/build_base_contour.py
# 试跑（不碰 target/；输出到 results/step1_prepare/contour_final/variant_<tag>/）
& ".../run_blender.ps1" src/contour/build_base_contour.py -ScriptArgs '--tag','x','--params','<另一份参数.json>'
```

- 输入：原画；`target/candidates/a/base_contour.json`、`target/candidates/b/base_contour.json`、`target/candidates/b/base_contour_alt_white_body_outline.json`（SHA-256 前 8 位 A796F50B / 65F5418D / 4931690E，与候选记录里的一致；不一致时脚本给警告）。
- 确定性：连续两次正式构建，`target/base_contour.json` 的 SHA-256 相同（`85215972AF4CAC6D474E57FBB66145690A276611DC450345B385C2E5DF2A926B`）。
- 保护：发现 A–B 相差 > 0.5％ 而没有裁决覆盖的区间时，脚本照常写出诊断图，但以退出码 1 结束。

## 3. 结果表

| 项目 | 结果 |
|---|---|
| A–B 距离（看得见的部分，画面高 ％，A→B 平均 / p95 / 最大） | 背 0.010 / 0.022 / 0.127；波頭 0.169 / 0.963 / 1.128；内側の弧 0.070 / 0.299 / 0.901 |
| > 0.5％ 的区间与裁决 | V1 (1848,392)→(1873,437) 1.02％；V2＋V3 (2099,648)→(2078,750) 1.13％；V4 (2140,1082)→(2097,1102) 0.90％；V5 补全段 3.79％。**全部采用 B**（理由见报告 §1） |
| 背的左端 | 采用「白色浪体轮廓」（`back_left_variant = white_body_outline`），**待用户确认**；看得见的白边向外平移实测墨线宽度 8.84 px；左端 (0, 1066.8) px＝(−0.861 H, 0.509 H) |
| S1 波頂 | 38.22％ / 8.62％，dx +0.03，dy −0.08；平顶 x 1371–1501（宽 5.00％） |
| S2 最深点 | 39.56％ / 46.92％，dx +0.09，dy +0.62，距离 0.63 |
| S3 | **量不到**（谷被挡住）。可见海面上缘 73.01％ → 若当作谷则 64.40％（−1.60，>1％）；按框架 Z＝0：66.08％ |
| S4（最终） | 左端 +20.2°（5％ 弦；粗尺度 x＝100–200 处 22.5–29.1°）；中段最大 53.9°（2％ 弦）/ 49.0°（粗）；波頂前 10.3°（8→3％ 弦）/ 8.6°（粗，x＝1300）。说明书 25 / 47 / 8 |
| S6 | 59.29％ / 33.06％，dx +0.13，dy +0.06；张出 47.5％ H，方向 −37.9° |
| S5 波頭の先 | (2226.5, 785.1) px＝57.70％ / 30.27％＝(+0.4394 H, 0.6732 H)；朝向（张出面积主轴）−45.8°；其它定义 −36.8°（波頂→先端）、+5.4°（测试库 φ）、−24.5 / −15.6 / −40.4°（上缘末段 5 / 10 / 20％ H 的弦） |
| 去爪后的波頭厚度（先端后 5 / 10 / 20％ H） | 等弧长点对 6.3 / 11.6 / 26.1％ H；最短距离 4.6 / 8.1 / 13.6％ H |
| 自身 S8（最大；≥15° 的采样数） | 背 23.0°（1/66）；波頭 86.3°（26/44）；内側の弧 66.7°（28/75）；先端转角 137°（±2％）/ 73°（±5％） |
| 各段 点数 / 长度 / `in_S7=false` | 背 880 / 1757.8 px / 0％；波頭 594 / 1185.7 px / 0％；内側の弧 1213 / 2422.7 px / 17.7％（214 点：completed_occluded 115 ＋ completed_other 99） |
| 独立的墨线外缘检查（中位，px） | 背 −0.06；波頭 −0.07；内側の弧 −0.08；左端白边 −0.08（p05…p95 都在 ±0.8 px 内） |
| 测试库读取 | `gw.profile_metrics.measure_base_contour()` 正常读取并测量 |

与说明书相差超过画面高 1％ 的项目：**只有 S3，且属于「量不到」**。S4 的角度差（中段最大 +2°（粗）…+6.9°（2％ 弦））无法换算成画面高的 ％，单独列出。

## 4. 没有解决、需要用户决定的事

1. 背的左端取哪一支（报告 §2）。
2. 「爪」的尺度：现在是指状尺度，基準輪郭自身不满足 S8；是否另做一条「大形尺度」的光滑基準輪郭（报告 §0-2、§4 的低通表）。
3. S5 朝向的定义（报告 §4、§8-2）；S1 平顶的左右判定规则（§8-3）。
4. S3 的 74.7％ 的出处。

## 5. 向其他模块报告的问题（共享代码我没有改）

- `gw.profile_metrics.measure_profile` 的自动先端检测（波頂之后第一个 X 局部最大、其后回退 ≥0.3％）在带瓣的轮廓上会停在较早的瓣：把基準輪郭低通 σ＝0.5％、1％ 后送进去，先端被判到离真实先端 4.9–5.1％ 的地方。对基準輪郭用 JSON 给定的分段就没有问题（现在的默认值）。
- 同一库的 φ 定义在基準輪郭上＝+5.4°；S5 的 ±5° 需要先统一定义。
- 同一库的 `S4.top_is_round_no_corner` 在基準輪郭上为 false，原因是 ±6％ 的窗口包进了 (1607, 285) 的真实折角（51°）和平顶左端的小肩。
- `G:\research\爪形分析`：100 个爪形切图的坐标都是切图内部的局部坐标，没有找到对应原画像素的位置信息，没有用于爪根定位。
- 机器上 Git Bash 里有 `python3`（3.12.10）；我只用它查看自己输出的 JSON、对自己的文件做文本替换，构建流程不依赖它。
- 没有 git，未 commit；以本记录代替。
- `results/step1_prepare/contour_final/variant_trial1/`、`variant_splice_test/` 是我的试跑输出，可忽略（没有删除任何文件）。

## 6. 图和数据（都在 `results/step1_prepare/contour_final/`，另有 `target/base_contour_overlay.png`）

- 叠加：`overlay_full_res.png`、`overlay_wave_1600.png`、`overlay_doubt_zones_1600.png`
- 候选比较：`compare_ab_1600.png`、`compare_ab_distance_plot.png`、`judge_V1_hook_claw_1.png`、`judge_V2_lobe3_hook_shoulder.png`、`judge_V3_sky_pocket_between_lobe3_and_lobe4.png`、`judge_V4_lowest_lobe_underside.png`、`judge_V5_completed_part.png`
- 局部：`crop_01_back_left_end` `crop_02_back_fork_zoom` `crop_03_back_mid` `crop_04_crest` `crop_05_head_top_hook_claws` `crop_06_head_step_thin_line` `crop_07_pocket_lobe3_lobe4` `crop_08_head_tip` `crop_09_right_flank` `crop_10_underside_right` `crop_11_underside_left_armpit` `crop_12_inner_deepest` `crop_13_inner_arc_mid` `crop_14_inner_arc_meets_near_wave` `crop_15_completion_trough` `crop_16_cloud_side_of_head`（.png）
- 曲线 / 诊断：`plot_S4_back_slope.png`、`plot_S8_own.png`、`plot_lowpass_diagnostic.png`、`diagnostic_lowpass_head.png`、`diagnostic_S5_direction_and_thickness.png`
- 数值：`metrics.json`；左端另一种读法：`base_contour_alt_sky_silhouette.json`
- 运行日志：`results/logs/build_base_contour_*.log`
