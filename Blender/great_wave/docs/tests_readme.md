# 测试说明：S1–S8（形状）、M1–M6（动态）、G1–G5（网格）

适用脚本：`tests/test_shape.py`、`tests/test_motion.py`、`tests/test_mesh.py`、`tests/run_all.py`、`tests/common_test.py`，自检 `tests/selfcheck_tests.py`。
测量库（不是本文件的内容）：`src/gw/silhouette.py`、`src/gw/profile_metrics.py`，定义见 `docs/measurement_definitions.md`。

**原则**

- 阈值**只**来自 `tests/thresholds.json`。每一项检查都同时报告两档：`spec`（说明书原值）和 `user_relaxed_5pct`（对「误差率 5％ 以内」的暂定解释，**待用户确认**）。脚本从不替用户选一档；进程退出码默认看 `spec` 档（`--exit-tier` 可改）。
- 测试不改阈值、不改基準輪郭、不挪相机。不过就报告：实测值、目标、差、在轮廓的哪一段（段名＋弧长范围＋原画像素位置）。
- 数值通过之后仍然要看叠加图；每次运行都会输出图。
- 凡是说明书没有写死、由测试自己选定的做法，下面都标了「**解释・待确认**」，同样的文字也写进每次运行的 `metrics.json`（`interpretation_notes`）。
- **2026-09-20 加固（针对 `results/step1_prepare/verify_tests/` 的审查，记录见 `docs/records/step1_harden_tests.md`）**：结论多了 `INCOMPLETE`、`ERROR` 两种和后缀 ` (NON-DEFAULT SETTINGS)`；脚本崩溃不再留下旧结果或退出码 0；NaN 顶点、脱离的轮廓分量、前面够不到静水面、`in_S7=false` 占比过大都判 `INVALID`；S3 同时按「模型自己的谷」再判一次；会影响判定的测试设置都登记在 `tests/thresholds.json` 的 `interpretations` 块里。细节见 1.3、第 2–4、6 节。

---

## 1. 怎么运行

推荐用工程自带的启动器（完整日志在 `results/logs/`，屏幕只显示 `GW` 开头的行）：

```powershell
$p = "G:/research/Wave Simulation/blender/great_wave"

# A. 对已保存的 .blend
& "$p/tools/run_blender.ps1" tests/run_all.py -ScriptArgs '--blend',"$p/blend/xxx.blend",'--object','GreatWave'

# B. 对「现场用脚本建出来的场景」（同一份参数 → 同一个网格；G5 需要这种方式）
& "$p/tools/run_blender.ps1" tests/run_all.py -ScriptArgs '--build-script','src/wave/build.py','--build-arg','params=params.json'

# 单独跑某一个
& "$p/tools/run_blender.ps1" tests/test_shape.py  -ScriptArgs '--blend',"...",'--object','GreatWave'
& "$p/tools/run_blender.ps1" tests/test_motion.py -ScriptArgs '--blend',"...",'--object','GreatWave','--final-frame','285'
& "$p/tools/run_blender.ps1" tests/test_mesh.py   -ScriptArgs '--build-script','...','--skip','G5'
```

等价的直接调用：`blender --background --factory-startup --python-exit-code 1 [file.blend] --python tests/test_X.py -- <参数>`。
**直接调用时必须带 `--python-exit-code 1`**（启动器总是带）：不带的话，脚本在 import 阶段出错时 Blender 的退出码是 0。`main()` 里面的异常由 `common_test.guarded_main` 接住（结论 `ERROR`、退出码 2），与这个开关无关——自检里两种都试过。

### 1.1 公共参数

| 参数 | 含义 | 默认 |
|---|---|---|
| `--object` | 浪的网格对象名；逗号分隔可以给多个（一起构成轮廓，第一个是 G 测试检查的网格） | 建模脚本返回的对象，或场景里唯一的网格 |
| `--blend` | 要打开的 .blend（也可以写在 `--python` 之前） | — |
| `--build-script` / `--build-func` / `--build-arg k=v` | 建模脚本协议，见 1.2 | — |
| `--contour` | 基準輪郭 json | `target/base_contour.json` |
| `--frame-start` / `--final-frame` | 起始帧 / 终幕帧 | 场景的 `frame_start` / `frame_end` |
| `--fps` | 帧率（M5 的 1 秒窗口用） | 场景渲染帧率 |
| `--H` / `--water-z` | 浪高 m / 静水面 Z | `params.json` 的 `WAVE_HEIGHT_M` / 0 |
| `--res-scale` | 遮罩分辨率系数 | 形状 1.0（3859×2594），动态 0.25，网格 0.5 |
| `--out-dir` / `--tag` | 结果目录 / 目录名后缀 | `results/<YYYYMMDD_HHMMSS>_<测试名>/` |
| `--exit-tier` | 决定退出码的档：`spec` / `user_relaxed_5pct` / `none` | `spec` |
| `--set key=value` | 覆盖测试设置（`common_test.TEST_SETTINGS`，**不是阈值**）。名字不认识 → 报错（`ERROR`）。只要改到会影响判定的设置，结论就带后缀 ` (NON-DEFAULT SETTINGS)`、退出码非 0（第 6 节） | — |

动态专用：`--phase-frames A,B`（張り出す区間的第一帧、巻き込む区間的第一帧；也读 `params.json` 的 `motion_phase_frames`）、`--hold-frames`（终幕之后求值的帧数；默认评估场景在终幕之后的全部帧，至 `scene.frame_end`）、`--backlog-hold-s`（只报告的「静止保持 10 秒」检查的保持时长，默认 10；0 = 不做）、`--frame-step`（>1 时 M5／M6 不能用于验收）、`--houdini-json`。
网格专用：`--skip G5`、`--g5-mode both|inprocess|subprocess`。
`--only`（`run_all`）、`--skip`、`--cases`（自检）里出现不认识的名字一律是错误（`ERROR`，退出码 2）；以前 `--only shpae` 这样的笔误会选中 0 个测试并得到 PASS。`--frame-step`、`--hold-frames`、`--res-scale` 与登记值不同时同样带后缀。

### 1.2 建模脚本协议（`--build-script`）

脚本作为模块被导入（`if __name__ == "__main__"` 不会执行），在**空的出厂场景**（或已打开的 `--blend`）上调用 `func(scene, **build_args)`。`func` 取 `--build-func`，否则依次找 `build_for_tests`、`build`、`build_object`。它必须在场景里建出浪的对象，可以返回对象、第一项是对象的元组、或 `None`（此时用 `--object` 指名）。`--build-arg` 的值能按 json 解码就解码。

### 1.3 输出（每次运行一个带时间戳的目录）

| 测试 | 文件 |
|---|---|
| 全部 | `metrics.json`（每项检查：实测、目标、差、单位、两档的限值／判定／余量、位置、备注；以及全部测量细节）、`summary.md`（表格） |
| 形状 | `overlay_full_1600.png`（叠在原画上：遮罩淡蓝、模型轮廓 红=背／橙=波頭／品红=内側の弧、基準輪郭 黄绿=计入 S7／黄虚线=`in_S7=false`、`+` 模型地标、`O` 基準輪郭地标、`x` 说明书数值；**深蓝横线=模型在 Z=0.25／0.5／0.75 H 的截面宽度，绿虚线=基準輪郭的，只报告**）、`overlay_widths_1600.png`（同样的截面线＋W 数值表）、`crop_*.png`（波頂、波頭の先、最深点、左端、谷、背最陡处、S7 最差点、波頭整体）、`plot_S7_deviation.png`（偏差—弧长，双向）、`plot_S8_turn.png`、`plot_S4_back_slope.png` |
| 动态 | `plot_motion_curves.png`（h、x_c、θ、o＋空洞深度、φ，带区间底色）、`plot_speed_jump.png`（M5 轮廓速度、M6 突跳比〔判定〕、M6_backlog〔只报告，灰色 × = 被排除的停止前窗口〕）、`contact_sheet.png`（每 15 帧）、`plot_vs_houdini.png`（`target/houdini_motion.json` 存在时） |
| 网格 | `g2_hem.png`、`g3_sections.png`（各截面的縁与内切圆）、`g4_intersections.png`（有自交时）、`g5_subprocess.log` |
| `run_all` | 根目录的合并 `metrics.json`／`summary.md`，下面 `shape/`、`motion/`、`mesh/` 三个子目录 |

**判定规则（每档一个结论；2026-09-20 加固后共五种）**

| 结论 | 条件 | 退出码 |
|---|---|---|
| `PASS` | 有效性 OK；没有 `FAIL`、没有 `NOT_MEASURABLE`；**至少有一项被判定，并且该测试应判的每一项都被判定过**——「应判的项」＝ `thresholds.json` 里该测试的编号（形状 S1–S8、动态 M1–M6、网格 G1–G5、`run_all` 三者全部）下所有有限值的检查 | 0 |
| `INCOMPLETE` | 没有任何一项不过，但有应判的项没被判定（`--skip`、没有 `--build-script` 所以 G5 没跑、`run_all --only` 只跑了一部分、0 项检查）。`summary.md` 列出缺了哪些 | 1 |
| `FAIL` | 有效性 OK，但有不过的项，或有限值却量不出来（`NOT_MEASURABLE` 永远按不通过算，从不默默当作通过；例：`--hold-frames 0` 时的 `M5.post_stop_max_disp_H`、張り出す区間只有 1 帧时的 `M3.o_monotonic_violation_H`） | 1 |
| `INVALID` | 有效性不 OK（数值不可信，既不算过也不算不过；条件见第 2–4 节） | 1 |
| `ERROR` | 脚本抛了异常（建模脚本崩溃、参数名不认识、测试自身的 bug）。`metrics.json`／`summary.md` 里有完整的 traceback，日志里也有 | **2** |

- 后缀 **` (NON-DEFAULT SETTINGS)`**：任何会影响判定的设置与 `tests/thresholds.json` 的 `interpretations` 块不一致时，加在结论后面（例如 `PASS (NON-DEFAULT SETTINGS)`），不一致的项列在 `metrics.json: summary.non_default_settings` 和 `summary.md` 里。**只有一字不差的 `PASS` 才是退出码 0。** `summary.<档>.verdict_base` 是不带后缀的结论。
- `--exit-tier none`：退出码恒为 0（`ERROR` 仍是 2），日志的 `RESULT` 行写 `NONE` 而不再写 `PASS`。
- 各项检查的状态：`REPORT`＝阈值文件里没有限值，只报告；`INFO`＝参考信息，不计入判定。`W.*`、`T.*`、`S7.<段>.<方向>.*`、`S7.<段>.signed_*`、`S7.underside.*`、`S7.belly.*`、`S5.crest_to_tip_*`、`S1.crest_inside_painted_plateau`、`S1.height_on_x0_plumb_*`、`S8.*vertex_window*`、`S8.tip_junction_deg`、`M6.backlog_*`、`M5.backlog_hold_*`、`G1.uv_*`、`G1.n_vertices` 都属于这两类，**永远不进入 PASS／FAIL 的判定**。（注意：`T.*` 里有几项是有效性条件背后的数——NaN 顶点数、被去掉的孤岛数、是否够到静水面、`in_S7=false` 占比、接缝与检测的距离——它们自己不是检查项，但对应的条件不满足时整次运行是 `INVALID`，见第 2–4 节。）

**崩溃保护**：每个测试的 `main()` 都包在 `common_test.guarded_main` 里。运行一开始，结果目录里已有的 `metrics.json`、`summary.md` 和已知的输出图（`overlay_*`／`crop_*`／`plot_*`／`contact_sheet`／`g2_hem`／`g3_sections`／`g4_intersections`／`g5_*`）会被改名为 `stale_<时间戳>_<原名>`，并写入一个 `RUNNING` 标记文件；正常结束和 `ERROR` 结束时都会删掉它。**目录里如果还留着 `RUNNING`，说明进程是被杀掉的，旁边即使有 `metrics.json` 也不属于一次完成的运行。** `run_all` 里某个子测试崩溃时，其余子测试照常运行，总结论是 `ERROR`。

---

## 2. 形状 S1–S8（`test_shape.py`，终幕一帧）

流程：`CAM_print` 下的轮廓遮罩（精确亚像素交点）→ 有序轮廓线 → `profile_metrics` → 与基準輪郭比较。

**有效性（2026-09-20 加固新增的四条，解释・待确认）**：
(1) 终幕帧的求值网格里有 NaN／inf 顶点，或轮廓遮罩因此丢掉了三角形（`T.n_nonfinite_vertices`、`T.n_dropped_triangles`；审查实测：一个 NaN 顶点时所有指标与干净的运行逐位相同，只有计数能看出来）；
(2) 有比碎屑界限（全分辨率 25 px，`gw.silhouette.SPECK_AREA_PX_FULL_RES`）大的轮廓分量因为不与主体相连而在描轮廓之前被去掉（`T.n_removed_islands`）——备注里写出它的面积和范围（H 坐标和原画像素），`overlay_full_1600.png` 上用红框标出。说明书 §5 注 2：空洞被东西挡住必须让 S2／S7 不过；被去掉的分量不会影响任何 S 值，所以只能判 `INVALID`。小于界限的碎屑只报告（`T.n_removed_specks`）；
(3) 前面始终够不到静水面（`T.reached_still_water` = 0；容差 = `trough_tol_pct_h` = 画面高的 0.3％）；
(4) 某一段被 `in_S7=false` 排除的比例 > 35％（`T.<段>.in_s7_false_share_pct`＝基準輪郭上该段弧长里不计入的比例；`T.<段>.model_samples_not_counted_share_pct`＝模型采样点里因最近的基準輪郭区间不计入而被跳过的比例；两者**每次都报告**）。实测：正式基準輪郭 内側の弧 20.8％、背／波頭 0％；合成浪 27.5％。35％ 这个数是编排者的解释，登记在 `thresholds.json: interpretations.test_settings.in_s7_false_max_share_pct`。

**只提示、不改变结论的两条（同日新增）**：`T.n_untested_mesh_objects`＝场景里**没有被测到**的网格对象个数——只有建模脚本返回的对象（或 `--object` 点名的对象）构成轮廓，另外的对象即使正好立在空洞里，任何一项检查都看不见；测试无从知道它属不属于浪，所以只在有效性备注里写出名字（自检用例 `island_not_listed`）。属于浪的对象请用 `--object a,b` 全部列出。另外，`--contour` 不是 `target/base_contour.json` 时备注里会写明，`metrics.json: context` 记录所用轮廓文件的 sha1（`contour_sha1`、`contour_is_official_target`）。

**原有的有效性条件**（任一项不满足，整个测试判 `INVALID`，因为数值不可信）：轮廓线没有走到右边框；遮罩里有未填充的洞（薄片没有被扫成实心）；对象在静水面以上的投影面积为 0（开口薄片正侧面看过去没有面积——这一条是自检发现漏洞后补上的）；**基準輪郭的 json 接缝与测量库在同一条折线上检测到的 波頂／波頭の先／最深点 相差超过画面高的 0.2％**（2026-09-20 新增，见下面「T：目标与模型是否同样分段」）。

| 编号 | 量什么 | 判定值 | 说明 |
|---|---|---|---|
| S1 | 波頂位置 | `dx_pct_h`、`dz_pct_h`：模型波頂 − (38.2％, 8.7％)，单位：画面高的 ％ | **解释・待确认**：波頂的横向位置用 `profile_metrics` 的「稳健极值」，不是最高像素。相对基準輪郭波頂的差作为 `INFO` 另报。 |
| S2 | 内側の弧最深点 | 到 (39.5％, 46.3％) 的欧氏距离 | dx、dz 另报；相对基準輪郭最深点的差作为 `INFO`。 |
| S3 | 谷から波頂の高さ | 实测高度（画面高 ％）− 66.0，**判两次** | 按「百分点」理解（spec 档 64–68）。若用户指的是相对 ±2％（66±1.32），可由原始数值自行判断。**解释・待用户确认（2026-09-20）**：`S3.height_err_pct_h`＝波頂到 Z＝0（取景定义里的谷水面）；`S3.from_model_trough.height_err_pct_h`＝波頂到**模型自己的谷**（最深点之后轮廓的最低点，`profile_metrics` 的 `S3_from_model_trough`）。两项用同一个阈值条目、都打印、都判定，所以结论取决于较差的一个。理由：说明书写的是「谷から波頂の高さ」；审查实测海面抬高 3％ 时前者读 +0.03（通过）、后者读 −2.97。谷在原画里量不出来（被手前の浪挡住），所以哪一种读法算数请用户决定。 |
| S4 | 背の傾き | 三个角度只报告；三个布尔量判定（中段最陡、向波頂渐缓、顶部圆无折角） | 窗口位置与容差是 `profile_metrics` 的**解释・待确认**。同时报告说明书的「约 25°／47°／8°」和基準輪郭自身的值。 |
| S5 | 波頭の先（不含爪） | 位置：到基準輪郭波頭の先的距离；朝向：φ_模型 − φ_基準輪郭 | 波頭の先＝整个悬空波頭上最靠右的点（测量库 2026-09-20 修订的检测规则，`docs/measurement_definitions.md` §3.6）。朝向**就用 φ**（上表面距先端 2％–8％ H 一段的弦），模型和基準輪郭用同一个函数，M4 也用它——**解释・待确认**。另外并排报告「波頂→先端」直线方向的差 `S5.crest_to_tip_dir_diff_deg`（只报告）和模型波頭的瓣数 `S5.model_head_lobes`。 |
| S6 | 含爪最右点（只作外边界） | 浪体最右点的「左から ％」< 59.2 | 两档相同（是边界不是容差）。「浪体」不含前面下部的浪脚（解释）。 |
| S7 | 轮廓一致 | 背／波頭／内側の弧三段，各自的平均偏差与 95％ 分位 | 双向最近距离（バックログ「定義」写的就是「両方向」）：模型→基準、基準→模型 **两个方向分别打印**（`S7.<段>.model_to_base.*`、`S7.<段>.base_to_model.*`，`INFO`），**判定取较差的一个**（`S7.<段>.mean_dev_pct_h`／`p95_dev_pct_h`）；分段比较时向邻段延伸 3％；`in_S7=false` 的补全区间不计。失败时列出超限的弧长区间和像素位置。**解释・待确认**。 |
| S8 | 轮廓平滑 | 相邻采样点（间距 1％）的切线方向差的最大值 < 15° | **解释・待确认**：在段内评价；距波頭の先弧长 2％ 以内不判定（縁厚 ≤3％H 的圆头必然在约 3％ 内转 ~180°）；先端总转角 `tip_turn_deg` 和不排除时的最大值 `max_unexcluded_deg` 单独报告。 |

**目标自检（每次运行都做）**：把基準輪郭**对它自己**判一遍 S1–S8。如果基準輪郭自己都不过，结果会在有效性备注里用大写写明，并且在每一项受影响的检查旁边给出 `target_self_check`（基準輪郭对自己的得分）。这样「模型 S5／S7 不过」就不会被误读成模型形状的问题。——这一条是在 `target/base_contour.json` 上发现问题后加的，详见 `docs/records/step1_tests.md` 第 4 节。2026-09-20 库修订之后，指状尺度的 `target/base_contour.json` 对自己不过的只剩 S8 和 S4 的两个布尔量（轮廓自身不光滑）；S5、S7 已经对自己通过（`docs/records/step1_libfix.md`）。

**T：目标与模型是否同样分段（2026-09-20 新增，只报告＋有效性）**。模型轮廓的 波頂／波頭の先／最深点 总是由测量库**检测**出来，基準輪郭用的是 **json 的接缝**。所以每次运行都在基準輪郭的同一条折线上再跑一遍检测，报告三个距离 `T.seg_crest_dist_pct_h`、`T.seg_head_tip_dist_pct_h`、`T.seg_deepest_dist_pct_h` 和基準輪郭波頭的瓣数 `T.base_head_lobes`。任何一个 > 0.2％ 画面高（`profile_metrics.DEFAULT_PARAMS['segmentation_check_tol_pct_h']`），或两边对「有没有张出」判断不同 → 这次运行 **INVALID**（不是 FAIL），备注里写明哪个点差多少。做轮廓的脚本可以用 `pm.detect_landmarks()` 把接缝放在检测点上，从构造上保证一致。

**只报告的补充量（2026-09-20 加固新增，全部没有阈值、不下结论；数值在 `metrics.json` 的检查项和 `measurements.shape_compare`／`S7_underside_belly`／`in_S7_false_shares_pct` 里，表和截面线画在 `overlay_widths_1600.png` 上）**

| 检查项 | 含义 |
|---|---|
| `W.own_h.*` | `profile_metrics` 的形状描述量：每条轮廓在**自己的** h 的 0.25／0.5／0.75 处取截面，长度全部 ÷ h；`o_over_h`、`cavity_depth_over_h`、`aspect_ratio`（0.5 h 处宽 ÷ h）、`aspect_ratio_h75`。模型值、基準輪郭值、差占基準輪郭值的 ％。「又宽又矮」时绝对高度的 W 会互相抵消甚至反号（宽 5％＋矮 1.9％：`W.z75.width_full_H` −5.22％），这一组读 +8.1％。正式基準輪郭的背在 0.509 H 处出了画面，所以 `aspect_ratio`（0.5 h）标为 not comparable，请看 `aspect_ratio_h75`。图上：紫色＝模型、深绿虚线＝基準輪郭。 |
| `S7.<段>.signed_mean_dev_pct_h`、`signed_p05_pct_h`、`signed_p95_pct_h` | 带符号的法向偏差，**正＝模型在目标浪体之外**。只看平均会抵消，要和 p05／p95 一起看。 |
| `S7.underside.*`、`S7.belly.*` | 把内側の弧在**腋部**分成「波頭下面」（先端→腋部）和「波腹」（腋部→谷）两部分分别给出 mean／p95（两个方向取较差者；`INFO`，限值只作参考）。腋部＝先端与最深点之间离「先端→最深点」直线最远的点（浪体一侧）；这个距离 < 0.5％ 画面高时认为没有明显的腋部，不分。说明书规定的判定段仍是整条内側の弧。图上用紫色／深绿的 × 标出。 |
| `S1.crest_inside_painted_plateau`、`S1.crest_outside_plateau_pct_h` | 模型波頂的 X 是否落在原画波頂平台的 X 范围内（取基準輪郭 json 的 `landmarks.crest.plateau_x_px`；没有这一项时用测量库在基準輪郭上检测到的平台），以及在范围外多远。 |
| `S1.height_on_x0_plumb_pct_h` | 轮廓上表面在铅垂线 X＝0 上的高度（画面高 ％，目标 66；说明书 §4：终幕时波頂位于 X＝0 的铅垂线上）。 |
| `S8.max_vertex_window_turn_deg`、`S8.<段>.vertex_window_turn_deg`、`S8.tip_junction_deg` | 折线自身顶点在 1％ 闭窗口里的净转角（什么都不排除）和恰好放在先端上的那个采样点的转角。**不能直接拿 15° 判**：正式基準輪郭自己读 19.1°（目标值一栏给出基準輪郭自己的读数）。用途：落在 S8 采样相位之间的折角（17° 读成 13.96°）和尖的先端在判定值里看不到，在这里看得到。 |

**W：只报告的尺寸指标（2026-09-20 新增，`report only - pending user decision`，没有阈值）**。Z = 0.25／0.5／0.75 H 三个高度上的截面宽度（`W.z75.width_full_H` 等）、悬空截面上「背→内側の弧」的宽度（`width_body_H`）、各点到波頂铅垂线的距离、张出 o、空洞深度、静水面以上的轮廓面积（H²）；模型值、基準輪郭值、差、**差占基準輪郭值的 ％**。定义见 `docs/measurement_definitions.md` §3.7。日志里打印成一张表，画在 `overlay_full_1600.png` 和 `overlay_widths_1600.png` 上，数值在 `metrics.json: measurements.W_compare`。注意原画的背在 Z = 0.509 H 处出了画面左边，所以 z25、z50 的宽度是从左边框量起的（表和图上都有标注），只有 z75 是完整的「背到前面」。

---

## 3. 动态 M1–M6（`test_motion.py`，全部帧）

每帧：降分辨率遮罩（精确交点，精度与分辨率无关）→ h、x_c、θ、o、φ，以及与上一帧的轮廓位移。

**有效性（2026-09-20 加固新增）**：任何一个被检查的帧上有 NaN／inf 顶点或被丢掉的三角形、或有大于碎屑界限的脱离分量（备注写出帧号和最大那块的范围）→ `INVALID`；**终幕帧**的前面够不到静水面 → `INVALID`。其余帧够不到静水面只报告（`T.n_frames_not_reaching_still_water`）：实测合成浪的前 16 帧就是这样——平缓的涌很宽，前面的浪脚在画面右边框之外，这是合法的。三个计数 `T.n_frames_nonfinite_geometry`、`T.n_frames_with_islands`、`T.n_frames_not_reaching_still_water` 每次都报告。只报告的 `M5.decel_is_monotonic`、`M2.theta_max_step_deg` 现在总会出现（量不出来时为空）。

**区间边界（解释・待确认）**：从数据里检测——張り出す区間从「此后一直保持张出」的第一帧开始；巻き込む区間从 φ(t) 最大的那一帧开始（波頭不再伸平、开始向下转）；运动结束帧＝终幕帧及以前最后一个轮廓还在动的帧。`--phase-frames A,B` 或 `params.json: motion_phase_frames` 给定时用给定值判定，检测值照样报告。各区间的秒数与バックログ的 4／3／2.5 s 一并写在 `metrics.json: phases`。

| 编号 | 判定值 | 说明 |
|---|---|---|
| M1 | 起始帧的 θ < 30° | |
| M2 | 高まる区間内 h 的最大单帧下降 ≤ 0；θ 起点 ≤ 30°；θ 终点 ≥ 80° | θ 终点取**最后一个未张出的帧**（从缓坡一帧跳成张出会因此不过）。θ 的最大单帧变化只报告（阈值文件里没有连续性的数值）。 |
| M3 | 張り出す区間内 o 的最大单帧下降 ≤ 0；h 下降 ≤ 5％；波頭の先越过波頂铅垂线 | o 在张出刚出现时按定义就是不连续的（`o_onset_jump_H` 只报告）。 |
| M4 | 巻き込む区間内 φ 的最大单帧上翻 ≤ 0 | |
| M5 | 停止瞬间轮廓速度 ÷ 全程最大速度 ≤ 0.20；终幕之后（保持帧）最大位移 ≤ 0（`--hold-frames 0` 时这一项是 `NOT_MEASURABLE`＝不通过，以前是默默记 0＝通过） | 轮廓速度＝与上一帧轮廓的最大最近点距离（双向，忽略沿水面的部分）。**「停止前 1 秒内逐渐减速」在阈值文件里没有数值**：窗口内的速度只报告（`decel_*`），不判定。 |
| M6 | 突跳比 < 3 | **解释・待确认**：第 k 对帧的比 = d(k) ÷ max(min(d(k−1), d(k+1)), 下限)，下限 = 全程最大位移的 5％。即位移必须同时小于前、后两对帧的 3 倍；（几乎）静止的相邻帧不作分母，否则任何「从静止起步」都是 x/0。 |

**バックログ「定義」的另一种读法（只报告，`report only - pending user decision`；`docs/backlog_crosscheck.md` 第 2、3 条）**——与上表的判定并排给出，从不进入判定：

| 报告项 | 定义 | 参考值 |
|---|---|---|
| `M6.backlog_jump_ratio`、`M6.backlog_within_reference` | 「定義」第 4 项：隣接フレームの移動量が前後の**中央値**の 3 倍を超えない（**停止への移行を除く**）。实现：比(k) = d(k) ÷ median(k 之前 2 对帧与之后 2 对帧的位移)，不设下限；「停止への移行」＝停止帧之前 `M5.decel_window_s`（1 s）以内以及停止之后的帧对，不参与取最大。窗口取前后各 **2** 对而不是各 1 对，是因为「单帧的突跳」会产生一去一回两个大位移：只取前后各 1 个时，2 个数的中央値就是平均值，第二个大位移会把第一个盖住——自检实测：第 40 帧突跳 0.3 H，前后各 1 对时比值只有 **1.92（查不出来）**，前后各 2 对时是 **23.3**。 | 3（与 `thresholds.json` 的 M6 是同一个数；不判定） |
| `M5.backlog_hold_max_disp_pct_h`、`M5.backlog_hold_within_reference` | 「定義」第 5 项：静止時に形を 10 秒保持し、輪郭の移動が画面高の 0.2％ 以下。实现：终幕帧之后 `backlog_hold_s`＝10 s（30 fps 下 300 帧；超出 `scene.frame_end` 的帧按 Blender 对动画的外推求值，备注里会写明）里每 30 帧取一帧再加最后一帧，**每一帧都与终幕帧的轮廓比较**（不是与前一帧比，所以慢漂移不会被漏掉），报告最大移动量（画面高 ％）。 | 0.2％（只在「定義」里有，`thresholds.json` 没有这一项；不判定） |

两种读法哪个算数，由用户决定；决定之后把限值写进 `tests/thresholds.json`（不归测试脚本改）。合成浪上的实测：不加缺陷 M6_backlog = 1.015、保持 10 s 的移动 3.7e-15％；第 40 帧突跳 23.3；动画截在 90％ 处 1.014（截断点落在被排除的窗口里）。

**噪声下限（解释・待确认，会改变判定）**：M2／M3／M4 的阈值是 0。实测在解析上严格单调的合成运动上，h 的「假下降」是 5.6e-6 H、φ 的「假上翻」是 0.012°——不设下限的话完美的运动也不过。所以小于 `monotonic_noise_floor_H`＝1e-4 H（H＝11 m 时 1.1 mm）／`monotonic_noise_floor_deg`＝0.2° 的量按 0 判定；**原始值始终写在旁边（`raw`）**。

**与 Houdini 参考的对比（说明书 6.4，不设阈值）**：读 `target/houdini_motion.json`（`gw.houdini_motion.v1`：`per_frame.full`／`per_frame.section` 的逐帧记录）。读不到任何曲线时**不出图**并在日志里写明，不会默默画一张没有参考数据的图。图下方用红字写明：两条时间轴的「1」不是一回事（Houdini 缓存结束时浪还在动，没有巻き込む区間）。

---

## 4. 网格 G1–G5（`test_mesh.py`）

| 编号 | 判定值 | 定义 |
|---|---|---|
| G1 | 拓扑或 UV 发生变化的帧数 = 0 | 每帧求值网格：顶点／边／面／loop 数、面大小、loop→顶点索引、UV 层名、UV 坐标做哈希，与第一帧比较。没有 UV 层 → 量不出来 → 不通过。单个顶点的最大单帧位移只报告。 |
| G2 | 裾的最大 \|Z − 静水面\| < 1％ H | 裾＝边界边（只属于一个面的边）上的顶点；所有帧取最大。报告帧号、顶点号、世界坐标。 |
| G3 | 波頭の縁的厚度 ≤ 3％ H | **解释・待确认**，见下。 |
| G4 | 自交的三角形对数 = 0（终幕＋每 15 帧） | `BVHTree.overlap(tree, tree)` 给候选；共用顶点的不算；只有**真正穿过**才计数（双方都有顶点严格落在对方平面两侧、两平面不平行、交线段长于容差）。重合／相触／退化的对另行报告、不判定（**解释**）。报告面对数、位置、示意图。 |
| G5 | 两次重建的顶点最大差 = 0 m | 需要 `--build-script`。在本进程重置场景重建一次，**再另起一个 Blender 进程**重建一次，按 float32 字节和世界矩阵逐位比较 5 帧。没有建模脚本时记为「跳过」：不算不通过，**但也不算通过——结论是 `INCOMPLETE`**（2026-09-20 起；`--skip` 同理）。 |

**有效性（2026-09-20 加固新增）**：G1 的逐帧循环里，求值网格只要有一帧含 NaN／inf 顶点 → `INVALID`（`T.n_frames_nonfinite_geometry`；G3 用的 `CAM_print` 轮廓丢了三角形也一样）。
**只报告（新增）**：`G1.n_vertices`（旁边给出现有 Unity 缓存的 85,120 和比值）；UV 的方向（终幕帧、第一个 UV 层，按三角形面积加权）：`G1.uv_u_abs_cos_to_crest_line`＝∂P/∂U 与世界 Y 轴夹角余弦的绝对值（0＝U 在截面平面内走）、`G1.uv_v_abs_cos_to_crest_line`＝∂P/∂V 的同一个量（1＝V 沿波峰线）、`G1.uv_u_starts_at_back_hem`（U 最小的 2％ loop 的平均 X < U 最大的 2％ 的平均 X，即 U 从背的裾走向谷）。合成浪实测 0／0.851／1（两端收束段把 V 方向带偏，所以不到 1）。`G1.max_vertex_step_H`（单个顶点的最大单帧位移）原来就有。

**G3 的定义（解释・待确认）**：终幕帧；在顶点组 `crest_rim` 的 Y 范围（10–90 百分位）内取 9 个 Y＝常数的截面（网格与平面求交，得到有序折线）；截面穿过「两个端点都在 `crest_rim` 里的网格边」的地方就是縁点（顶点组是一圈顶点或一条带都适用）；縁的厚度＝在縁点处与截面相切、从浪体一侧放进去而不穿出截面的**最大内切圆的直径**（对圆头的縁就是 2r）。只判定「截面自己的波頭の先与 `CAM_print` 看到的波頭の先相距 ≤ 1％ 画面高」的截面（也就是构成可见縁的那些）；两端收束的截面只报告。判定值＝被判定截面中的最大值。合成浪：实测 2.483％ H，解析 2.5％ H。

---

## 5. 自检（`tests/selfcheck_tests.py`）

```powershell
& "$p/tools/run_blender.ps1" tests/selfcheck_tests.py            # 全部 38 对（含 6 个另起进程的用例），约 4 分钟；--quick 跳过另起进程的用例、G5 的新进程重建和放宽扫描
& "$p/tools/run_blender.ps1" tests/selfcheck_tests.py -ScriptArgs '--cases','back_kink,self_fold','--quick'
```

（补充，来自 `docs/records/step1_proof.md` 的提醒：用夹具把**原画的**基準輪郭扫成网格时必须用 `--build-arg taper=lift_clip`；默认的 `clip` 收束会把空洞顶部填平。加固用例 `build_attack_case` 用的就是 `lift_clip`。）

用合成测试浪（目标＝它自己的解析轮廓 `tests/fixtures/synthetic_contour.json`）：不加缺陷的必须全过；故意加缺陷的必须**恰好**让该不过的指标不过。期望是在第一次运行之前写下的（`CASES` 的注释里有推理）；形状类缺陷另有一层独立预测（同一缺陷直接加在截面折线上、不经过网格和遮罩），两层的不通过集合必须相同，两层的**数值差**也写进表里。结果表见 `docs/records/step1_tests.md`。

2026-09-20 库修订时增加的内容（原有用例的期望和阈值一项没改；最新结果表见 `docs/records/step1_libfix.md`）：

- 新用例 `widen_x_8pct`（X 放宽 8％）和 `target_joint_shifted`（模型不动，把**目标 json** 的波頭／内側の弧接缝沿波頭往回挪 3.1％ → 必须判 `INVALID`）。
- 只报告的数也有期望（`expect_W`、`expect_report`、`expect_verdict`，同样在第一次运行前写下）：放宽 k 倍的合成浪，W 的 z75 宽度、到波頂铅垂线的距离、o、空洞深度必须读出 (k−1)×100％ ± 0.3 个百分点（经网格＋遮罩，和直接在截面折线上，两层都要），面积的增幅必须在 0 与 (k−1)×100％ 之间；不加缺陷时全部在 ±0.3 以内。动态：不加缺陷 M6_backlog ≤ 3、保持 10 s 的移动 ≤ 0.2％；突跳用例 M6_backlog > 3。不加缺陷的形状结论必须是 `PASS`，纯拉伸和接缝被挪动的必须是 `INVALID`。
- 放宽扫描表增加了 W 的四列。

2026-09-20 加固时增加的用例（`HARDEN_CASES`；期望写在第一次运行之前，那时的文件副本在 `results/step1_prepare/harden_tests/expectations_before_first_run/`；原有 17 对的期望、容差、阈值一项没改；结果表见 `docs/records/step1_harden_tests.md`）：

| 用例 | 内容 | 期望 |
|---|---|---|
| `official_clean` | 正式基準輪郭用 `lift_clip` 扫成网格（攻击用例的对照） | 只有继承自目标的 `S4.flattens_towards_crest` 不过；没有孤岛、没有 NaN、够得到静水面 |
| `wide_low_5_1p9` | 宽 5％＋矮 1.9％（用户原来的抱怨） | 判定项可以照旧通过，但 `W.own_h.*` 必须读 +8.1％ 左右，带符号 S7：背、波頭为负，内側の弧为正 |
| `floor_raised_3pct` | 浪前的海面抬高 3％ | `INVALID`，并且 `S3.from_model_trough` 不过（−2.97），`S3` 不变 |
| `island_in_cavity` | 空洞里有一块脱离的物体 | `INVALID`，备注写出它的范围 |
| `nan_vertex`、`nan_vertex_mesh` | 终幕的一个顶点是 NaN | 形状测试和网格测试都 `INVALID` |
| `back_kink_17_worst` | 背上 17° 折角，落在 S8 的采样相位之间 | 判定值 < 15°（这是按说明书的采样定义必然存在的盲点，如实记录），只报告的折线窗口转角（背）≥ 15.5° 且比干净时大 2.5° 以上 |
| `settings_backdoor_frame_jump` | `--set jump_floor_frac_of_vmax=1.0` 把 0.3 H 的突跳藏起来 | 结论带后缀、退出码 1、该项列出 |
| `no_hold_frames` | `--hold-frames 0` | `M5.post_stop_max_disp_H` 是 `NOT_MEASURABLE`，结论带后缀 |
| `zero_checks_mesh_skip_all` | 另起进程：`test_mesh --skip G1,…,G5` | `INCOMPLETE`，退出码 1 |
| `run_all_only_typo`、`mesh_skip_unknown_name` | 另起进程：`--only shpae`、`--skip G9` | `ERROR`，退出码 2 |
| `island_not_listed` | 同一块脱离的物体，但没有写进 `--object`（已知限制） | 结论与干净时相同，但 `T.n_untested_mesh_objects` = 1，备注点出它的名字 |
| `run_all_subtest_crash` | 另起进程：`run_all` 里 `test_shape` 抛异常（`--contour` 文件不存在） | 其余子测试照常运行；shape＝`ERROR`，总结论 `ERROR`，退出码 2 |
| `unit_verdict_vocabulary`、`unit_settings_audit`、`unit_settings_from_params_json` | 纯 Python：`summarize`／`exit_code` 的 11 种组合；`get_settings`／`settings_audit`（含「代码默认值与 `interpretations` 一致、没有漏登记」） | 见用例注释 |
| `crashing_build_script`（带／不带 `--python-exit-code 1` 各一次） | 另起进程：建模脚本抛异常，结果目录里预先放了一份旧的 PASS | 退出码 2；`metrics.json` 是 `ERROR` 且含 traceback；旧文件改名为 `stale_*`；没有留下 `RUNNING` |

## 6. 测试设置（不是阈值）

**设置的「后门」已经封上（2026-09-20）**：凡是会影响判定、却放在 `common_test.TEST_SETTINGS` 或 `profile_metrics.DEFAULT_PARAMS` 里的容差／设置，都在 `tests/thresholds.json` 新增的顶层块 **`interpretations`** 里登记了 `{value, unit, used_by, provenance: 'orchestrator interpretation, pending user confirmation', comment}`（24 项测试设置、21 项测量参数、1 个库常量 `silhouette.SPECK_AREA_PX_FULL_RES`；原有的阈值、运算符、档位一项没动）。每次运行 `common_test.settings_audit()` 把**实际生效的设置值**（经过 `params.json` 的 `test_settings`／`measure_params`、`--set`、`--res-scale`、`--hold-frames`、`--frame-step` 之后）与这个块比较：有不同、代码默认值与文件不同、或有会影响判定的设置没登记 → 结论带 ` (NON-DEFAULT SETTINGS)`、`metrics.json: summary.non_default_settings`／`settings_audit` 和 `summary.md` 列出每一项（名字、生效值、文件值、来源）、退出码非 0。`hold_frames = null` 表示使用场景在终幕之后的全部帧；审计比较的是这个设置值，实际帧数另记于 `metrics.json: frames.hold`。只影响「只报告」项的设置（`REPORT_ONLY_SETTINGS`／`REPORT_ONLY_MEASURE_PARAMS`）改了只列出、不加后缀。S8 的采样间距由它自己的检查项 `S8.sample_spacing_pct_h`（`eq 1.0`）判。`params.json` 写坏、`test_settings` 不是对象、名字不认识都会抛异常（以前被整个吞掉）。
**给改代码的人**：以后在 `TEST_SETTINGS` 或 `DEFAULT_PARAMS` 里新增一项时，必须同时把它登记进 `interpretations`（或者，如果它确实只影响只报告的量，加进 `REPORT_ONLY_SETTINGS`／`REPORT_ONLY_MEASURE_PARAMS`）；否则每一次运行都会带 ` (NON-DEFAULT SETTINGS)`。自检的 `unit_settings_audit` 用例专门检查「代码默认值与登记值一致、没有漏登记」。

`common_test.TEST_SETTINGS`，每项带注释；可被 `params.json` 的 `test_settings` 项或 `--set` 覆盖。会影响判定的只有标了 INTERPRETATION 的几项：单调性噪声下限、静止判定的位移下限（1e-6 H）、M6 的分母下限（5％）、G3 的截面匹配距离（1％）、G4 的几何容差（1e-6 H、0.1°）。

只影响「只报告」项的设置（2026-09-20 新增）：`m6_backlog_half_window`（2）、`m6_backlog_exclude_window_s`（空 = 用 `M5.decel_window_s` = 1 s）、`backlog_hold_s`（10）、`backlog_hold_step_frames`（30）、`backlog_hold_reference_pct_h`（0.2，引自「定義」，**不是本工程的阈值**）。测量库一侧的参数在 `profile_metrics.DEFAULT_PARAMS`：`tip_rule`、`tip_min_reversal_pct_h`、`head_lobe_reversal_pct_h`、`segmentation_check_tol_pct_h`、`width_levels_H`（可被 `params.json` 的 `measure_params` 覆盖）。

## 7. 待用户确认的解释（汇总）

1. `user_relaxed_5pct` 这一档本身的含义（基础库的暂定解释）。
2. S1 用稳健极值定波頂的横向位置；S5 的朝向用 φ；S6 的「浪体」不含浪脚。
3. S7：分段＋3％ 延伸、双向取较差者（两个方向也分别打印）、`in_S7` 的处理。
4. S8：段内评价、波頭の先前后 2％ 不判定、先端转角单独报告。
5. 动态区间边界的检测规则（尤其「巻き込む从 φ 最大处开始」）。
6. M2／M3／M4 的噪声下限（不设的话完美的运动也不过）。
7. M5「逐渐减速」没有数值阈值，目前只报告——要不要给一个阈值。
8. M6 突跳比的公式（取前后较小者、5％ 下限）——这是按说明书文字的读法，用于判定；「定義」的读法（前后中央値、排除向停止的过渡）并排报告，见第 3 节和本节第 13 条。
9. G3 的厚度定义（縁点处的最大内切圆直径、只判可见縁的截面）。
10. G4 不把重合／相触／退化的三角形对算作自交。
11. **模型轮廓按检测分段、基準輪郭按 json 接缝分段**——2026-09-20 的处理：检测规则改成「整个悬空波頭上最靠右的点」（最大回撤），同一检测也在基準輪郭上跑一遍，相差 > 0.2％ 画面高判 `INVALID`。规则本身、0.2％ 这个值、以及「判 INVALID 而不是 FAIL」，都待用户确认。
12. S5／M4 的朝向就用 φ（不是「波頂→先端」的方向；后者并排报告）。
13. **只报告、等用户决定要不要变成判定的三组数**：(a) 尺寸指标 W（截面宽度、o、空洞深度、面积）——现在的阈值对「宽 5–8％」几乎不报；(b) M6 的「定義」读法（前后中央値、排除停止前 1 s、窗口前后各 2 对）；(c) 静止保持 10 s、移动 ≤ 0.2％。三组都没有写进 `thresholds.json`。
14. **（2026-09-20 加固）S3 判两次**：从 Z＝0 和从模型自己的谷，取较差者——待用户确认哪一种读法算数（第 2 节）。
15. **新增的四条有效性条件**（NaN／丢三角形、脱离的分量 > 25 px、够不到静水面〔容差 0.3％〕、`in_S7=false` 占比 > 35％）以及「这些情况判 `INVALID` 而不是 `FAIL`」。
16. **`INCOMPLETE`**：跳过 G5（没有建模脚本）或 `run_all --only` 只跑一部分时，结论不再是 PASS。
17. `tests/thresholds.json` 的 `interpretations` 块里登记的 42 个值本身（都是此前已经在代码里的默认值，加固没有改其中任何一个；新加的只有 `in_s7_false_max_share_pct` = 35 和 `motion_frame_step` = 1）。
18. **只报告、还没有阈值的新量**：`W.own_h.*`（建议用 `aspect_ratio_h75`、`o_over_h`、`cavity_depth_over_h` 对应「太宽／不够高」）、带符号的 S7、`S7.underside`／`S7.belly`、S1 的两个伴随量、`S8.max_vertex_window_turn_deg`、UV 方向。
