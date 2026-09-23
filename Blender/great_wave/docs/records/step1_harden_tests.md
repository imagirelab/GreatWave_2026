# 第 1 步记录：测试框架加固（针对 `results/step1_prepare/verify_tests/` 的审查）

- 日期：2026-09-20　环境：Blender 5.2.2 LTS 无界面，自带 Python 3.13 + numpy。没有安装或下载任何东西；没有写到 `G:/research/Wave Simulation` 和会话临时目录之外；没有改 PYTHONPATH；没有 git，本记录代替 commit。
- 我负责并改动的文件：`tests/common_test.py`、`tests/test_shape.py`、`tests/test_motion.py`、`tests/test_mesh.py`、`tests/run_all.py`、`tests/selfcheck_tests.py`、`tests/thresholds.json`（**只增不改**，见 1.5）、`docs/tests_readme.md`、本文件。改前的副本在会话临时目录 `scratchpad/harden_tests/orig/`。
- **没有动**：`src/gw/*`、`tests/selftest_measure.py`、`tests/fixtures/*`、`target/*`、`params.json`、相机取景、轮廓几何、其他人的记录和结果目录（概念验证的重跑写在我自己的 `results/step1_prepare/harden_tests/runs/` 里，没有覆盖 `proof_swept_contour/`）。
- 前提：测量层刚加固过（`docs/records/step1_harden_measure.md`），本任务只是让测试层**用上**那些新键，并堵住审查指出的框架漏洞。

## 0. 结论（先说）

1. 审查指出的框架漏洞现在都有对应的结论或提示：0 项检查 → `INCOMPLETE`；脚本崩溃 → `ERROR`／退出码 2／旧结果改名；NaN 顶点、空洞里的孤岛、海面抬高 → `INVALID`；`--set` 改容差 → 结论带 ` (NON-DEFAULT SETTINGS)`、退出码 1；`--only`／`--skip`／`--cases` 的笔误 → 错误。S3 同时按模型自己的谷再判一次（解释・待用户确认）。
2. **判定用的阈值、运算符、档位、相机、轮廓一项没改；原有 17 对自检用例的期望、容差一项没改**，它们的不通过集合与加固前逐项相同，唯一的差别是新判定项 `S3.from_model_trough.height_err_pct_h` 出现在本来就该出现的两处（波頂抬高 3％、纯拉伸）；关键数值的最大差为 0（逐位相同）。
3. 新增 21 个加固用例，期望都写在各自第一次运行之前（副本见第 3 节），**全部第一次运行即符合**。最终代码：`selftest_measure` **88 项，0 项失败，退出码 0**；`selfcheck_tests` **38 对（原有 17 对＋加固 21 个），0 对不符，退出码 0**（`results/20260920_110019_selfcheck/`）。
4. 概念验证重跑（正式轮廓、`lift_clip`、全分辨率）：与原运行共有的 55 项形状检查、7 项网格检查的实测值和两档状态**全部相同（最大差 0）**，结论仍是 FAIL／FAIL——形状只因为目标自己也不过的 `S4.flattens_towards_crest`，网格只因为 `G3` = 14.84％ H；新增的只有 46＋6 个新键。
5. **仍然看不见、需要用户知情的三件事**（第 6 节）：宽 5％＋矮 1.9％ 在判定项里仍然一项不报（只报告的量读 +8.1％，要不要设阈值待用户定）；落在采样相位之间的 17° 折角判定值仍是 13.96°（只报告的窗口转角读 16.61°）；没有写进 `--object` 的物体任何检查都看不见（现在会被点名，但不改变结论）。

## 1. 做了什么（对应任务 1–7）

| # | 内容 | 位置 |
|---|---|---|
| 1 结论的词汇 | `summarize()`：`PASS` 需要「至少一项被判定」且「该测试应判的每一项都被判定过」（应判项＝`thresholds.json` 里 S1–S8／M1–M6／G1–G5 下所有有限值的检查，按测试取；`run_all` 取三者全部），否则 `INCOMPLETE`；`FAIL`、`INVALID` 的含义不变；新增 `ERROR`。只有一字不差的 `PASS` 退出码为 0（`exit_code()`）。`validate_names()`：`--only`／`--skip`／`--cases` 里不认识的名字 → 错误。量不出来的检查一律 `NOT_MEASURABLE`：`M5.post_stop_max_disp_H`（没有保持帧时；以前记 0＝通过）、`M3.o_monotonic_violation_H`（張り出す区間不足 2 帧时；以前记 0）。`params.json: motion_phase_frames` 只在「这一项不存在」时才忽略，写坏了会抛异常。 | `common_test.py`、`test_motion.py`、`test_mesh.py`、`run_all.py`、`selfcheck_tests.py` |
| 2 崩溃保护 | `guarded_main()`：定结果目录 → `begin_run()`（旧的 `metrics.json`／`summary.md`／已知输出图改名 `stale_<时间戳>_*`，写 `RUNNING`）→ 测试本体 → `finish()`（删 `RUNNING`，按结论退出）。任何异常：traceback 写进日志和 `metrics.json`／`summary.md`，结论 `ERROR`，退出码 2。结果目录在建模脚本运行**之前**就确定，所以建模脚本崩溃也有结果文件。`run_all` 的子测试崩溃时其余照常运行。G5 的内部子进程（`--dump-verts`）不碰结果目录。所有文件头和 README 里的直接调用示例都带 `--python-exit-code 1`。 | `common_test.py`、各 `main()` |
| 3 新的有效性条件 | 形状：NaN／inf 顶点或被丢的三角形；大于碎屑界限的被去掉的轮廓分量（备注写出面积、H 范围、原画像素范围，`overlay_full_1600.png` 上红框标出）；`reached_still_water` 为假；某段 `in_S7=false` 占比 > 35％（目标一侧按弧长、模型一侧按采样点，两者每次都作为 `T.<段>.*` 报告）。动态：任一被检查帧上的 NaN／孤岛，终幕帧够不到静水面。网格：G1 循环里任一帧的 NaN 顶点，G3 用的轮廓丢了三角形。`T.*` 计数每次都报告。 | 三个测试 |
| 4 S3 | 新判定项 `S3.from_model_trough.height_err_pct_h`（用 S3 同一个阈值条目；没有新增或改动任何阈值），与原来的 `S3.height_err_pct_h` 并排打印；两项都判，所以结论取较差者。文档里写明是「解释・待用户确认」。S3 的备注措辞按测量层的建议改了。 | `test_shape.judge_profile` |
| 5 设置的后门 | `tests/thresholds.json` 新增顶层块 `interpretations`：20 项测试设置＋21 项测量参数＋1 个库常量，每项 `{value, unit, used_by, provenance: 'orchestrator interpretation, pending user confirmation', comment}`。`settings_audit()` 每次运行比较生效值与文件值；不同／代码默认值与文件不同／有会影响判定的设置没登记 → 结论加后缀、列进 `metrics.json` 和 `summary.md`、退出码非 0。`--res-scale`、`--hold-frames`、`--frame-step` 也算。`get_settings()` 不再吞异常，名字不认识就抛。`_meta.backlog_access_note` 按要求改写（见 1.5）。 | `thresholds.json`、`common_test.py` |
| 6 只报告的补充 | 形状：`W.own_h.*`（含 `aspect_ratio_h75`）、`S7.<段>.signed_*`、`S7.underside`／`S7.belly`、`S1.crest_inside_painted_plateau`／`S1.crest_outside_plateau_pct_h`／`S1.height_on_x0_plumb_pct_h`、`S8.max_vertex_window_turn_deg`／`S8.<段>.vertex_window_turn_deg`／`S8.tip_junction_deg`；截面线、腋部和两张表画在 `overlay_widths_1600.png` 上。动态：`M5.decel_is_monotonic`、`M2.theta_max_step_deg`（原来就有，现在量不出来时也出现）。网格：UV 方向三项、`G1.n_vertices`（对 85,120）、`G1.max_vertex_step_H`（原来就有）。另外：`T.n_untested_mesh_objects`、所用轮廓文件的 sha1。 | 三个测试 |
| 7 自检 | `HARDEN_CASES` 21 个用例（第 2.2 节）；原有用例的循环加了崩溃保护（某一对崩溃只算这一对不符）；一个用例都没跑时不算成功。 | `selfcheck_tests.py` |

### 1.5 `tests/thresholds.json` 的改动（只增不改的证明）

用脚本做的文本级修改（`scratchpad/harden_tests/patch_thresholds.py`）：原文件除 `_meta.backlog_access_note` 一句外逐字保留，末尾追加 `interpretations` 块；脚本最后把新旧两份解析后逐项比较——**S1–S8、M1–M6、G1–G5、`tiers`、`tier_names` 以及 `_meta` 的其余各项完全相同**，新增的顶层键只有 `interpretations`。`interpretations` 里的 42 个值都取自代码里**已有**的默认值（加固没有改其中任何一个）；新加的两个设置是 `in_s7_false_max_share_pct` = 35 和 `motion_frame_step` = 1。
`backlog_access_note` 的新内容（依据只有 `docs/backlog_crosscheck.md`，我自己没有读バックログ）：核对的是 2026-09-17 22:42 的那份「定義」；**在那里找到且一致**：原画文件与「％＝画面高」、3D 参考不是形状正解、轮廓测试用去掉爪和飞沫的轮廓、S7 的 1％／2％、S1／S3 的 2％、固定视点、巻き始め的定义；**找到但与说明书不同**：S7 双向、M6 的「前後の中央値・停止への移行を除く」、静止保持 10 s／0.2％；**没找到**：大きさの設定（H 10.4–13 m）、船上視点、初期时长 4／3／2.5 s；**那份核对没有提到的** `backlog` 值（S2、S5、S6、S8 的 15°、G3 的 3％ H）仍然只是说明书的转述。

## 2. 实测到的事实

### 2.1 原有自检用例：加固前后对比

加固前的报告 `results/20260920_101014_selfcheck/` 对 加固后的完整运行 `results/20260920_104334_selfcheck/`，以及最终运行 `results/20260920_110019_selfcheck/`（`results/step1_prepare/harden_tests/scripts/compare_selfcheck_reports.py`，输出在同目录的 `selfcheck_comparison_stdout.txt`）（结论如下）：17 对（用例，测试）键相同；`must_fail`、方式、结论词全部相同；不通过集合的差别只有 `S3.from_model_trough.height_err_pct_h` 多出现在 `crest_raise_z_3pct／形状`（spec 档）和 `taper_none／形状`（两档）；表里所有关键数值的最大差 = **0**；放宽扫描 1.02–1.20 每一行的不通过集合相同。

### 2.2 加固用例（期望写在第一次运行之前；下表是**第一次运行**的读数，最终运行的读数相同，见 2.4）

正式基準輪郭用 `lift_clip` 扫成网格（25,251 顶点），全分辨率；「继承」＝目标自己也不过的 `S4.flattens_towards_crest`。攻击的做法照搬审查的 `attack_common.py`（移植进 `selfcheck_tests.py`，免得 `tests/` 依赖 `results/` 里的脚本）；读数与审查表、与测量层的记录逐位一致，说明移植没有走样。

| 用例 | 期望 | 第一次运行的结果 | 符合 |
|---|---|---|---|
| `official_clean`（对照） | 只有继承项不过；无孤岛／NaN；够得到静水面；S3 两种读法相同 | FAIL／FAIL，不过：继承项；`S3` = `S3.from_model_trough` = +0.034；`W.own_h` 纵横比 h75 −0.02％、o/h +0.19％、空洞深/h −0.04％ | 是 |
| `wide_low_5_1p9` | 判定项可以照旧；`W.own_h.*` +7…+9.2％；带符号 S7 背、波頭 −0.2…−1.5，内側の弧 +0.2…+1.5；S3 −1.7…−2.0 | FAIL／FAIL，**不过的仍只有继承项**；`aspect_ratio_h75` **+8.09％**、o/h +8.33％、空洞深/h +8.07％、h75 宽/h +8.09％（同一次运行里绝对高度的 `W.z75.width_full_H` 读 −5.22％）；带符号 S7 −0.508／−0.628／+0.630；S3 = S3.from_model_trough = −1.866；记录：S7 背 0.802／1.859、波頭 0.922／1.853、S5 位置 1.977 | 是 |
| `floor_raised_3pct` | `INVALID`，且 `S3.from_model_trough` 在 spec 档不过（−2.8…−3.15），`S3` 不变 | INVALID／INVALID；`S3.from_model_trough` = **−2.966**（spec 不过、5％ 档通过），`S3` = +0.034；`T.reached_still_water` = 0；备注：「lowest point … 3 % of image height above Z = 0」 | 是 |
| `island_in_cavity` | `INVALID`，备注写出范围 X 0.17…、Z 0.22… | INVALID／INVALID；「1 component(s) of 57311 px … bbox X 0.170..0.300 H, Z 0.220..0.370 H (painting px x 1765..1988, y 1304..1561)」；其余读数与对照相同 | 是 |
| `nan_vertex`／`nan_vertex_mesh` | 两个测试都 `INVALID` | 形状：INVALID，`T.n_nonfinite_vertices` = 1、`T.n_dropped_triangles` = 6（顶点号 12514）；网格：INVALID，`T.n_frames_nonfinite_geometry` = 1 | 是 |
| `back_kink_17_worst` | 判定 S8 在 12–15°（不报——按说明书的采样定义必然存在的盲点，如实记录）；只报告的窗口转角（背）≥ 15.5° 且比对照大 ≥ 2.5° | 判定 **13.96°**（通过）；`S8.back.vertex_window_turn_deg` **16.61°**（对照 13.11°，差 +3.50°）；S7 背 p95 0.360 | 是 |
| `nan_vertex_motion`、`island_motion`（2 帧扫掠＋3 个保持帧，只看有效性） | 动态测试 `INVALID`，`T.n_frames_*` 计数 | INVALID／INVALID；NaN：第 2–5 帧各 1 个顶点、6 个三角形；孤岛：第 1–5 帧，每帧 3,640 px（1/4 分辨率，碎屑界限 1.563 px），范围 X 0.169..0.300 H、Z 0.219..0.371 H | 是 |
| `island_not_listed`（已知限制） | 结论同对照；`T.n_untested_mesh_objects` = 1，备注点名 | FAIL／FAIL（只有继承项）；备注「1 mesh object(s) that are NOT tested: Island」 | 是 |
| `settings_backdoor_frame_jump` | 结论带后缀；该设置被列出；`--exit-tier spec` 的退出码 1；不带后缀的结论是 PASS（这正是后门） | `PASS (NON-DEFAULT SETTINGS)` ×2；列出 `test_settings.jump_floor_frac_of_vmax` = 1.0（文件值 0.05，来源 `--set`）；退出码 1 | 是 |
| `no_hold_frames` | `M5.post_stop_max_disp_H` 为 `NOT_MEASURABLE`；结论 FAIL 并带后缀 | `FAIL (NON-DEFAULT SETTINGS)` ×2；不过：`M5.post_stop_max_disp_H`（量不出来）、`M6.jump_ratio`（31 帧的已知现象） | 是 |
| `unit_verdict_vocabulary` | 11 种组合的结论词和退出码（见用例代码里的表） | 全部符合 | 是 |
| `unit_settings_audit`、`unit_settings_from_params_json` | 名字不认识抛 `ValueError`；**代码默认值与 `interpretations` 一致、没有漏登记**；`--set`／`params.json`／测量参数覆盖／命令行替换各自列出并带来源；只影响只报告量的设置单独列出、不加后缀；`test_settings` 不是对象抛 `TypeError` | 全部符合 | 是 |
| `zero_checks_mesh_skip_all`（另起进程） | `INCOMPLETE`，退出码 1 | INCOMPLETE／INCOMPLETE，0 项被判定，退出码 1 | 是 |
| `run_all_only_typo`、`mesh_skip_unknown_name`（另起进程） | `ERROR`，退出码 2 | 退出码 2；`ValueError: unknown name(s) 'shpae' given to --only (allowed: shape, motion, mesh)`；`… 'G9' given to --skip …` | 是 |
| `run_all_subtest_crash`（另起进程） | shape＝`ERROR`，其余子测试照常，总结论 `ERROR`，退出码 2，没有留下 `RUNNING` | 符合；shape 的 `FileNotFoundError`（`--contour` 不存在）写在 shape／根目录两份 `summary.md` 里，motion、mesh 有完整输出 | 是 |
| `crashing_build_script` ×2（带／不带 `--python-exit-code 1`；结果目录里预先放了一份旧 PASS） | 退出码 2；`metrics.json`＝`ERROR` 且含 traceback；旧文件改名；没有 `RUNNING` | 两次都是退出码 **2**；`RuntimeError: deliberate crash …`；目录里是 `metrics.json`、`summary.md`、`stale_<时间戳>_metrics.json`、`stale_<时间戳>_summary.md`、子进程日志 | 是 |

同一批运行里顺带看到的（只报告的量，都是实测）：

- 宽 5％＋矮 1.9％ 时，内側の弧整段 mean 0.637％（过 1％），但按腋部拆开后 **`S7.underside` mean 1.159％、p95 1.744％**，`S7.belly` 0.261％／0.989％——偏差集中在波頭下面，被整段平均稀释了。
- 正式轮廓的扫掠：腋部 模型 (0.0895, 0.5908) H、基準輪郭 (0.0888, 0.5904) H；`S1.crest_inside_painted_plateau` = 1（平台 X −0.0487…+0.0085 H，取自 json 的 `plateau_x_px`）；`S1.height_on_x0_plumb_pct_h` = 66.01（宽＋矮时 64.12）；`T.inner_arc.in_s7_false_share_pct` = 20.8％、模型一侧 17.4％。
- 海面抬高时 `S8.inner_arc.vertex_window_turn_deg` 读 38.5°（内側の弧碰到抬高的海面处的折角；判定的 S8 不变，11.26°）。
- 合成浪的动态测试：**前 16 帧（121 帧版）前面够不到静水面**——平缓的涌很宽，浪脚在画面右边框之外。所以动态测试里这一条只对终幕帧判 `INVALID`，其余帧只报告（这是看到实测之后定的，不是事先想到的）。
- 合成浪的 UV：`G1.uv_u_abs_cos_to_crest_line` 0、`G1.uv_v_abs_cos_to_crest_line` 0.851、`G1.uv_u_starts_at_back_hem` 1；`G1.n_vertices` 25,251（85,120 的 0.30 倍）。
- 被杀掉的进程确实会留下 `RUNNING`：我中途停掉过一次完整自检（`results/20260920_105048_selfcheck/`），`frame_jump/motion/` 里只有 `RUNNING`、没有 `metrics.json`。
- `run_all` 在不加缺陷的合成浪（121 帧）上：三个子测试和总结论都是 PASS，退出码 0，没有留下 `RUNNING`（`results/step1_prepare/harden_tests/runs/run_all_synthetic_121/`）。

### 2.3 概念验证的重跑（最终代码）

命令＝`docs/records/step1_proof.md` 第 1 节的第 3、5 条，只把 `--out-dir` 换成 `results/step1_prepare/harden_tests/runs/proof_none_shape_final`、`…/proof_none_mesh_static2_final`。与原运行 `proof_swept_contour/runs/none_shape`、`none_mesh_static2` 的逐项比较（`results/step1_prepare/harden_tests/scripts/compare_proof.py` → `proof_rerun_comparison.json`）：

| 项目 | 原运行（`step1_proof.md` 2.2／2.4） | 重跑（最终代码） |
|---|---|---|
| 形状：结论／有效性／不过的项 | FAIL／FAIL；OK；`S4.flattens_towards_crest` | **相同**（退出码 1；19 项被判定，应判的项无一遗漏，没有非默认设置） |
| 共有的 55 个检查项 | — | 实测值、两档状态全部相同，最大差 **0** |
| S1 dx／dz | −0.844／+0.034 | −0.8441／+0.03407 |
| S2 | 0.642 | 0.6424 |
| S3 | +0.034 | +0.03407；**新** `S3.from_model_trough` = +0.03407（通过） |
| S4 三个角（只报告） | 19.79／53.75／9.44 | 19.79／53.75／9.436 |
| S5 位置／朝向 | 0.136／−1.00° | 0.136／−0.9993° |
| S6 | 56.82 | 56.82 |
| S7 背／波頭／内側の弧（mean／p95） | 0.0056／0.0174、0.0062／0.0131、0.0068／0.0136 | 0.005625／0.01736、0.00621／0.01314、0.006831／0.0136 |
| S8 | 11.25° | 11.25°；`max_unexcluded_deg` 11.25°（先端采样点 −9.36°，不超过原值） |
| T 接缝 vs 检测 | 0.123／0.0005／0 | 0.1234／0.0005384／0 |
| 网格：结论／不过的项 | FAIL／FAIL；`G3` 14.84 | **相同**；G1 0、G2 0、G3 14.84、G4 0、G5 0；7 个共有检查项最大差 **0** |

重跑里新出现的键（只列读数；完整清单在 `proof_rerun_numbers.txt`）：`S1.crest_inside_painted_plateau` = 1，`S1.height_on_x0_plumb_pct_h` = 66.01；带符号 S7 三段 +0.0002／−0.0023／+0.0004；`S7.underside` 0.0083／0.0138，`S7.belly` 0.0058／0.0128；`S8.max_vertex_window_turn_deg` 16.51°（基準輪郭自己 19.15°；分段 13.11／15.92／16.51，基準輪郭 19.15／10.12／11.06），`S8.tip_junction_deg` −9.36°（基準輪郭 −9.71°）；`W.own_h`：`aspect_ratio_h75` −0.02％、`o_over_h` +0.19％、`cavity_depth_over_h` −0.04％；`T.inner_arc.in_s7_false_share_pct` 20.82％／模型一侧 17.43％，其余 `T.*` 计数全为 0，`T.reached_still_water` = 1；网格：`G1.n_vertices` 25,251，UV 0／0.840／1。
中途在 CRLF 状态下跑的那一次（`runs/proof_none_shape/`、`runs/proof_none_mesh_static2/`）与最终重跑的全部读数逐字相同。

### 2.4 最终运行（最终代码；`results/step1_prepare/harden_tests/final_runs_stdout.txt`）

| 脚本 | 结果 | 退出码 | 输出 |
|---|---|---|---|
| `tests/selftest_measure.py` | 88 项检查，0 项失败，60.5 s | **0** | 日志 `results/logs/selftest_measure_20260920_105918.log`；报告 `results/step1_prepare/measure/selftest_measure_report.json` |
| `tests/selfcheck_tests.py` | 38 对，0 对不符；约 3 分 50 秒 | **0** | `results/20260920_110019_selfcheck/`（`selfcheck_table.md`、`selfcheck_report.json`）；日志 `results/logs/selfcheck_tests_20260920_110019.log` |
| `tests/test_shape.py`（概念验证第 3 条命令） | FAIL／FAIL（只有 `S4.flattens_towards_crest`） | 1（与原运行相同） | `results/step1_prepare/harden_tests/runs/proof_none_shape_final/`；日志 `results/logs/test_shape_20260920_110412.log` |
| `tests/test_mesh.py`（第 5 条命令） | FAIL／FAIL（只有 `G3`） | 1（与原运行相同） | `…/runs/proof_none_mesh_static2_final/`；日志 `results/logs/test_mesh_20260920_110419.log` |

最终自检里 21 个加固用例的全部读数与各自第一次运行**逐位相同**（最大差 0），原有 17 对与加固前的报告相比见 2.1（`selfcheck_comparison_stdout.txt`）。

## 3. 运行经过（没有隐去的部分）

- 期望文件的副本（`results/step1_prepare/harden_tests/expectations_before_first_run/`，`COPIED_AT.txt` 里有时间）：第 1 份 10:38:35（前 14 个加固用例第一次运行之前）；第 2 份 10:47:35（两个 unit 用例之前）；第 3 份 10:48:54（`unit_settings_from_params_json` 之前）；第 4 份 10:52:34（`island_not_listed`、`run_all_subtest_crash` 之前）；第 5 份 10:58:42（`nan_vertex_motion`、`island_motion` 之前）。第 1 份与最终文件的 diff（去掉行尾差异后）**只有新增的行**（后加的 7 个用例和它们的函数），没有任何一行被改或删——即没有一条期望在运行之后被改过。
- **我犯过的一个错（已改回，只涉及行尾）**：我用 Git Bash 的 `grep -c $'
'` 去看行尾，它对每个文件都返回「全部行数」，我据此误以为工程文件是 CRLF，于是在中途把我的 6 个脚本转成了 CRLF；后来按字节数核对才发现工程里所有文件（包括我这 6 个的原件）都是 LF，随即转回 LF。第 4 份期望副本和 `runs_stdout_2_crlf_state.txt` 那一次完整运行（88／0、36 对 0 不符、概念验证读数与最终相同）是在 CRLF 状态下做的；最终运行（2.4）用的是 LF 的最终文件。`thresholds.json` 和文档没有受影响（一直是 LF）。
- 加固用例第一次运行的目录：`results/20260920_103945_selfcheck/`（14 个，14／14）、`…_104743_selfcheck/`（2 个 unit）、`…_104905_selfcheck/`（params.json 的 unit）、`…_105242_selfcheck/`（`island_not_listed`、`run_all_subtest_crash`）、`…_105850_selfcheck/`（动态的 2 个）。没有一个用例在第一次运行时不符。
- 期望里引用的数值来源：`wide_low` 的 +8.1％ 是闭式（1.05 ÷ (1 − 1.9 × 0.0151515 ÷ 1.0006)），符号来自几何上的先验推理（写在用例注释里）；但我在写期望之前**已经读过**测量层记录里的同一组读数（−0.508／−0.628／+0.630、13.96°／16.61°、−2.966、57,311 px、1／6），所以这些期望不是「盲」的。它们仍然是有效的回归基准：测量层的数是不经过测试脚本量的，这里是经过 `test_shape`／`test_mesh` 的完整路径量的，两条路径读数一致。
- 完整自检一共启动了 4 次：`…_104334_selfcheck/`（31 对，0 不符；那时还没有后加的 7 个用例）；`…_105048_selfcheck/` 跑到一半被我停掉（为了再加用例，不是因为出错）；`…_105411_selfcheck/`（36 对，0 不符；CRLF 状态）；最终 `…_110019_selfcheck/`（38 对，0 不符）。另有 1 次只跑 `baseline`（冒烟，`…_103842_selfcheck/`）和 1 次故意写错 `--cases` 的运行（退出码 2，没有生成结果目录）。`selftest_measure` 跑了 3 次（10:42、10:53、10:59），都是 88／0。**没有任何一次运行出现过不符或失败的项**，也没有为了通过而改过任何期望。
- 看图之后改过的地方（数值不受影响）：「armpit」标签原来离标记点太远，改到标记点右侧；孤岛在 `overlay_full_1600.png` 上原来只是一块淡蓝色，没有任何标注，加了红框和文字。
- 写代码过程中自己发现并改掉的：`T.*` 占比项的 id 在文档里写反了顺序（实际是 `T.<段>.in_s7_false_share_pct`）；错误结果的 `summary.md` 里单个测试也写着「sub-test」。

## 4. 推测（不是实测）

- 第 2 步的真实模型如果把海面、浪体做成两个对象，必须用 `--object a,b` 都列出来，否则海面抬高、物体挡空洞都测不到；我没有见过真实的建模脚本，这只是从接口推出来的。
- `in_S7=false` 占比 35％ 这个界限对现有两条轮廓（20.8％、27.5％）都留有余量；以后如果轮廓组把补全区间延长，可能碰线。
- `INCOMPLETE` 会让「只有 .blend、没有建模脚本」的 `test_mesh`／`run_all` 永远拿不到退出码 0；第 4 步交付时应当总是走 `--build-script`。

## 5. 建议

1. 请用户决定 S3 的两种读法哪个算数（或两个都要）；在此之前两项都判。
2. 「太宽／不够高」：给 `W.own_h.aspect_ratio_h75`、`W.own_h.o_over_h`、`W.own_h.cavity_depth_over_h`（相对基準輪郭的 ％ 差）定阈值；读数的分辨力是实测过的（对照 ±0.2％，宽 5％＋矮 1.9％ 读 +8.1％）。同时考虑对 `S7.underside` 单独判（宽＋矮时它是唯一超过 1％ 的平均偏差）。
3. S8：若要抓住相位之间的折角，可以对 `S8.<段>.vertex_window_turn_deg` 设「不超过基準輪郭自身读数 + 若干度」的相对限值；不要用固定的 15°（目标自己 19.1°）。
4. `params.json` 里 `blender_exe` 的注释写的直接调用没有 `--python-exit-code 1`（不是我的文件，没有改）；请它的负责人补上。
5. 第 2 步每次交付请同时附 `summary.md`：新的提示（未测对象、非正式轮廓、非默认设置、未判定项）都在它的开头几行。

## 6. 没有做／已知限制

- **宽 5％＋矮 1.9％ 在判定项里仍然不报**；这需要用户给阈值，测试脚本不能自己定。
- **17° 折角落在相位之间时判定的 S8 仍读 13.96°**；判定定义是说明书的，没有改。20° 逆曲率折角在 443 点截面上任何 15° 规则都抓不到（测量层记录 0.3(b)）。
- 没有写进 `--object` 的对象：只点名，不改变结论。与主体在投影里相连的附加物体、只在浪附近抬高的海面：测量层已说明看不见，这里也一样。
- `--exit-tier none` 时退出码恒为 0（`ERROR` 除外）；`--H`、`--water-z`、`--contour`、`--final-frame` 是对场景的描述而不是容差，改了不会带后缀（都记录在 `metrics.json: context` 里；非正式轮廓会在备注里写明）。
- 真实的浪还不存在；以上都只在合成浪和正式轮廓的扫掠网格上验证过。新的有效性条件只在合成数据上触发过（NaN：形状、动态、网格；孤岛：形状、动态；海面抬高：形状。动态测试里「终幕帧够不到静水面」这一支**没有**专门的用例，只有代码走查；`in_S7=false` 占比超限这一支也没有专门的用例）。
- 没有读バックログ；`backlog_access_note` 完全依据 `docs/backlog_crosscheck.md`。

## 7. 接口变化（给其他模块）

- `common_test.summarize(checks, validity_ok, validity_notes, skipped, expected=None, audit=None, errors=None)`：每档新增 `verdict_base`、`n_judged`、`expected_not_judged`；顶层新增 `expected_ids`、`errors`、`non_default_settings`、`report_only_non_default_settings`。`verdict` 取值：`PASS`｜`FAIL`｜`INVALID`｜`INCOMPLETE`｜`ERROR`，可带后缀 `common_test.NON_DEFAULT_SUFFIX`。旧的调用方式（前四个参数）仍然有效，但不传 `expected` 时只检查「至少一项被判定」。
- 新函数：`common_test.guarded_main(test_name, args, body)`、`begin_run`／`end_run`、`error_result`、`exit_code`、`validate_names`、`expected_checks`、`settings_audit`、`get_settings(..., with_sources=True)`、`run_dir_from_args`、`untested_objects_report`、`file_sha1`；常量 `EXPECTED_IDS`、`REPORT_ONLY_SETTINGS`、`REPORT_ONLY_MEASURE_PARAMS`、`EXIT_CODE_ERROR`、`RUNNING_MARKER`。`setup_context(args, test_name, run_dir=None)` 不再自己管理结果目录的清理（由 `guarded_main`／调用方的 `begin_run` 负责）。`eval_mesh_arrays` 多返回 `tri_loops`、`n_nonfinite_vertices`、`nonfinite_vertex_indices`。
- `test_shape.judge_profile(...)` 返回新增 `shape_rows`、`s7_split`、`in_s7_shares`、`validity_fail`；新函数 `armpit_of`、`height_on_plumb`、`in_s7_shares`、`shape_table_lines`、`shape_overlay_items`；`save_images(..., shape_rows=None, split=None)`。`test_mesh.uv_orientation(arr)`、`test_mesh.G_IDS`。`test_motion`：`--frame-step` 的默认值改为「取设置 `motion_frame_step`」（=1，行为不变）。
- 新的检查项 id：`S3.from_model_trough.height_err_pct_h`（**判定**）；只报告：`S1.crest_inside_painted_plateau`、`S1.crest_outside_plateau_pct_h`、`S1.height_on_x0_plumb_pct_h`、`S7.<段>.signed_mean_dev_pct_h`／`signed_p05_pct_h`／`signed_p95_pct_h`、`S7.underside.*`、`S7.belly.*`（或 `S7.underside_belly_split` = 空）、`S8.tip_junction_deg`、`S8.max_vertex_window_turn_deg`、`S8.<段>.vertex_window_turn_deg`、`W.own_h.<名字>`、`T.n_nonfinite_vertices`、`T.n_dropped_triangles`、`T.n_removed_islands`、`T.n_removed_specks`、`T.reached_still_water`、`T.<段>.in_s7_false_share_pct`、`T.<段>.model_samples_not_counted_share_pct`、`T.n_untested_mesh_objects`、`T.n_frames_nonfinite_geometry`、`T.n_frames_with_islands`、`T.n_frames_not_reaching_still_water`、`G1.n_vertices`、`G1.uv_u_abs_cos_to_crest_line`、`G1.uv_v_abs_cos_to_crest_line`、`G1.uv_u_starts_at_back_hem`。
- `metrics.json` 新增：`settings_audit`、`summary.non_default_settings`、`error`（ERROR 时）、`context.command_line`／`settings_sources`／`contour_sha1`／`contour_is_official_target`／`untested_mesh_objects`；形状：`measurements.shape_compare`、`S7_underside_belly`、`in_S7_false_shares_pct`、`geometry_dropped`；动态：`frames.per_frame`、`frames.nonfinite_geometry`／`with_islands`／`not_reaching_still_water`、`series.trough_level_H`／`reached_still_water`；`run_all`：`tests_not_run`。
- 日志的 `RESULT` 行：`GW RESULT <PASS|FAIL|ERROR|NONE> <测试> spec=… user_relaxed_5pct=… (exit tier: …, exit code N) -> 目录`。

## 8. 图和数据

- 加固用例第一次运行：`results/20260920_103945_selfcheck/`（`selfcheck_table.md` 末尾的「hardening cases」表）。我看过的图：`harden_wide_low_5_1p9/overlay_widths_1600.png`（绝对高度的 W75 −5.2％ 与自身 h 的 +8.09％ 并排；紫色截面线、腋部标记、两张表，文字是 ASCII、没有被裁）、`harden_island_in_cavity/overlay_full_1600.png`（第一版里孤岛只是一块淡蓝色 → 已加红框，最终版见 2.4 的运行目录）、`harden_floor_raised_3pct/crop_trough.png`（模型轮廓停在抬高的海面上，基準輪郭的黄虚线在下面继续走到 Z＝0）、`baseline/shape/overlay_widths_1600.png`（合成浪，腋部位置合理）。
- 期望副本：`results/step1_prepare/harden_tests/expectations_before_first_run/`。
- 概念验证重跑：`results/step1_prepare/harden_tests/runs/proof_none_shape_final/`、`proof_none_mesh_static2_final/`（不带 `_final` 的两个目录是 CRLF 状态下的那一次）、`proof_rerun_comparison.json`、`proof_rerun_numbers.txt`、`scripts/compare_proof.py`、`scripts/print_proof_numbers.py`；我看过 `proof_none_shape/overlay_widths_1600.png`（模型与基準輪郭重合，两张表的差都在 ±0.2％ 以内，腋部标在空洞左上角）。
- 自检前后对比：`scripts/compare_selfcheck_reports.py`、`selfcheck_comparison_stdout.txt`。最终自检：`results/20260920_110019_selfcheck/`（`harden_island_in_cavity/overlay_full_1600.png` 上孤岛有红框和「DETACHED 57311 px: removed before tracing -> INVALID」，看过，没有被裁）。
- 其它：`results/step1_prepare/harden_tests/runs/run_all_synthetic_121/`、`full_runs_stdout_1.txt` 和 `runs_stdout_2_crlf_state.txt`（中间的两次完整运行）、`final_runs_stdout.txt`（最终）。
- 临时脚本（不属于工程）：会话临时目录 `scratchpad/harden_tests/`（各个补丁脚本、`probe_in_s7.py`）。
