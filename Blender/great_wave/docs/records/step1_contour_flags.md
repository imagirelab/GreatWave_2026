# 第 1 步记录：基準輪郭 的标记更正（背左端＝构造；只改标记，几何逐位不变）

- 日期：2026-09-20　环境：Blender 5.2.2 LTS 无界面运行，自带 Python 3.13 + numpy（没有安装或下载任何东西；没有写到 `G:/research/Wave Simulation` 之外；没有改 PYTHONPATH；没有调用裸 `python`；没有 git，本记录代替 commit）。
- 负责范围：`src/contour/build_base_contour.py`、`base_contour_params.json`、`build_large_form.py`、`large_form_params.json`、`target/base_contour.json`、`target/base_contour_finger_scale.json`、`target/large_form_variants/*.json`、`docs/base_contour_report.md`（追加第 12 章）、本文件。重跑两个构建脚本的副作用：`target/base_contour_overlay.png`、`results/step1_prepare/contour_final/`、`results/step1_prepare/contour_large_form/` 下的图和 `metrics.json` 被重新生成。
- **没有改**：`src/gw/*`、`tests/*`（含 `thresholds.json`）、相机取景、任何轮廓点。
- 新建的核对用目录：`results/step1_prepare/contour_flags/`（脚本、改动前备份、哈希、核对结果）。

## 1. 起因（两位独立复核者的发现，实测事实）

1. 背在 x < 约 338 px 的一段（`origin_runs` 为 `B_alt_inner_edge+offset`）是**构造**的：画面上那里没有墨线，线＝看得见的白色浪体边缘向外平移实测墨线宽度 8.84 px；却标成了 `traced`。
2. 指状尺度文件里的 `claw_root_bridge` 标的是「滚球改动过轮廓的所有地方」，不只是爪根。
3. 大形文件说明文字的两处小问题：「0.02％ 以内」的说法有 1 个点超出（0.531 px > 0.519 px）；`source_flags` 里写了实际上没有任何点使用的 `claw_root_bridge`。

## 2. 做了什么

1. **改动前**：把 10 个相关 JSON、两个 `metrics.json`、4 个源文件、`base_contour_overlay.png` 备份到 `results/step1_prepare/contour_flags/before/`；对每个 JSON 的每一段的 `points_px` / `points_H` 算 SHA-256（float64 字节和 JSON 文本两种算法），另记 `source`、`in_S7`、`dev_from_finger_scale_px`、地标 px 的哈希 → `hashes_before.json`。
2. `build_base_contour.py`：构造段的标记由 `traced` 改为 **`offset_from_visible_edge`**（只改 `white_body_left_end()` 里的一行标记赋值）；新增 JSON 键 `pending_user_confirmation`、`pending_stretches`、`source_flags`；`contour_definition` 文字按读法区分并写明新标记；独立墨线外缘检查的选点改为「`traced` 或新标记」，保证选到的点与改动前完全相同；画图时这一段用**段色短虚线**，图例加一项。
3. `base_contour_params.json`：新增参数 `pending_user_confirmation`（值 `["back_left_variant"]`）；`white_body_outward_offset` 的说明补一句标记的事。用户确认读法后删掉这一项、重跑两个脚本即可（只影响标记 / 元数据）。
4. `build_large_form.py`：新标记自动继承（规则不变：点在指状尺度线上 → 继承该处标记；被正则化移动过 → `large_form_bridge`，**`large_form_bridge` 优先**）；从指状尺度文件继承 `pending_user_confirmation` 和区间，按本文件的点重算 `index_range` / `flag_counts`；`source_flags` 改为**只写本文件里出现的标记**，`traced` 的说明改成「在 1 px 折线上按 ≤ 0.02％（0.519 px）判定，之后才做 2 px 重采样和 0.001 px 取整，所以可以超出一个很小的 ε」，并把**本文件实测的最大值**写进去；图例 / 决策图说明加「红色短虚线＝构造段」。`large_form_params.json` 只改了 `label_tol_pct_h` 的说明文字。
5. 无界面重跑 `build_base_contour.py` → `build_large_form.py`（共跑了 5 轮；最后三轮之间只动了图例位置、把 `pending_user_confirmation` 做成参数、说明文字按参数取词，10 个 JSON 的文件 SHA-256 三轮完全相同＝同一份参数可重建）。
6. **改动后**：同一脚本再算哈希 → `hashes_after.json`，逐项比较 → `hashes_compare.json`；逐键比较新旧 JSON → `json_key_diff.json`。
7. 核对共享代码还能不能读：`check_loaders.py` 对 9 个轮廓文件（新文件和备份）各跑 `pm.load_base_contour`、`pm.base_contour_polyline`、`pm.measure_base_contour`（JSON 接缝和检测两种）、`test_shape.target_self_check` → `loader_check.json`；另外用夹具把正式轮廓扫成网格完整跑了一次 `tests/test_shape.py`。
8. 逐张看了重新生成的图：`target/base_contour_overlay.png`、`f_decision_sheet.png`（3 次）、`e_left_end_readings.png`、`contour_final/crop_01_back_left_end.png`、`contour_final/base_contour_finger_scale_overlay.png`。看图后改了 2 处：决策图 C 的图例文字太长被裁掉 → 缩短；图例框左移 34 px，让原来就被裁掉半个括号的一项也完整显示。

## 3. 命令

```powershell
$p = "G:/research/Wave Simulation/blender/great_wave"; $o = "$p/results/step1_prepare/contour_flags"
& "$p/tools/run_blender.ps1" results/step1_prepare/contour_flags/scripts/hash_contours.py -ScriptArgs '--out',"$o/hashes_before.json"   # 改动前
& "$p/tools/run_blender.ps1" src/contour/build_base_contour.py      # 约 20 s
& "$p/tools/run_blender.ps1" src/contour/build_large_form.py        # 约 2 分钟
& "$p/tools/run_blender.ps1" results/step1_prepare/contour_flags/scripts/hash_contours.py -ScriptArgs '--out',"$o/hashes_after.json"
& "$p/tools/run_blender.ps1" results/step1_prepare/contour_flags/scripts/hash_contours.py -ScriptArgs '--compare',"$o/hashes_before.json","$o/hashes_after.json",'--out',"$o/hashes_compare.json"
& "$p/tools/run_blender.ps1" results/step1_prepare/contour_flags/scripts/diff_json_keys.py -ScriptArgs '--out',"$o/json_key_diff.json"
& "$p/tools/run_blender.ps1" results/step1_prepare/contour_flags/scripts/check_loaders.py -ScriptArgs '--before','--out',"$o/loader_check.json"
& "$p/tools/run_blender.ps1" tests/test_shape.py -ScriptArgs '--build-script','tests/fixtures/make_synthetic_wave.py','--build-func','build_object','--build-arg',"profile_json=$p/target/base_contour.json",'--build-arg','taper=lift_clip','--build-arg','n_frames=2','--out-dir',"$o/runs/shape_official_large_form"
```

## 4. 结果（实测事实）

### 4.1 几何：60 / 60 个数组逐位相同

10 个 JSON × 3 段 ×（`points_px`、`points_H`）＝60 个数组，改动前后 SHA-256（float64 字节、JSON 文本两种）**全部相同**；`in_S7` 列表、`dev_from_finger_scale_px`、地标 px 也全部相同（`hashes_compare.json`：`geometry_arrays_identical = 60`，`problems = []`）。没有需要回退的东西。下表是 float64 字节哈希的前 16 位（改动前＝改动后）：

| 文件 | 背 n / px / H | 波頭 n / px / H | 内側の弧 n / px / H |
|---|---|---|---|
| `target/base_contour.json`（＝`large_form_r150.json`） | 868 / FB937FEA30B6B2AD / CB1AED0D5F4A8BEF | 511 / 5612369AC6DA898D / DDDEA82615B4F09E | 1030 / 4C82B01241CD2262 / 8396E982123A17BC |
| `target/base_contour_finger_scale.json` | 880 / 2455B06783E20BA4 / 8E32A7CD40EE792C | 594 / 71BF79562A9BB7AC / A24808D8B729C9A8 | 1213 / 466B8BD91A4C30DB / 9F54C309F3E4D485 |
| `large_form_r100.json` | 871 / 19E484F1A4982541 / 4B035EB62D4E934A | 510 / CBEEA12BDF3D1301 / 04F59CCDFD313F4C | 1059 / 4F4F75DB2A652DB4 / CABC516831BE92A9 |
| `large_form_r120.json` | 870 / 4EC9B9E3B7C54B0A / 5ED9D19DB7174334 | 509 / 5D0E80E7A31335E2 / 428303AF207CE672 | 1045 / 09469982CAC61C12 / E2C6F4600D88C88B |
| `large_form_r135.json` | 869 / 0A7A9DDF64B36D09 / 7CD1DCEA101D3382 | 510 / 8055F697C66AF457 / C20406603FE5888E | 1038 / 9975CDEF01D13297 / 4A0327F337741FEC |
| `large_form_r150_alt_sky_silhouette.json` | 850 / D15D81D3750196A5 / 8BB3122A5535D82E | 511 / 6745E71B018C025F / FE192CF64DB5C547 | 1030 / 181632AD8D2E32E0 / 036CC9C084A9A982 |
| `large_form_r150_open_close.json` | 864 / 7F26E5006C451A44 / 7FA68AA7A0C1589C | 386 / 74AC06094EB8B95D / 8429B3362C897975 | 885 / E918BAD4D3AD29E1 / 0D0445E74574E5A4 |
| `contour_final/base_contour_alt_sky_silhouette.json` | 863 / 8C625613B48C8896 / E3E259583CE38F6F | 594 / 0F4073F4A1211B6D / 76791036A290F665 | 1213 / 1080A6E49DA56DFA / 9A08323B2A8C679F |
| `contour_large_form/compare_lowpass_sigma2pct.json` | 854 / 6196084B6DF2E749 / DB1B83C776F70925 | 534 / A3C3D6436EECE8EA / 2B02CB5355AF4FB3 | 1112 / 2D2900D68BAA9BDD / 0F7E44ECA035855F |

文件级 SHA-256（内容变了，因为标记和元数据变了；前 16 位，改动前 → 改动后）：

| 文件 | 改动前 | 改动后 |
|---|---|---|
| `target/base_contour.json`、`large_form_r150.json` | 4004DB43248F7F9B | **4D670EACFA1E1DAB**（全值 `4D670EACFA1E1DABCCAA870AF1EEEB41AEC6A1037B35E6256FDB9E3B5B0DB91B`） |
| `target/base_contour_finger_scale.json`（带说明键） | C7E3DD8E2D3D4B06 | **94B5A01814DB2E3A**（全值 `94B5A01814DB2E3A044A81D273ECC9F07761254200F861C61423A0071760FE47`；`build_base_contour.py` 刚写出、还没加说明键时是 2B78E6726345B8DB，原来是 85215972AF4CAC6D） |
| `large_form_r100` / `r120` / `r135` | FBB3BA1868ECA34A / CB52D1CE0279870A / 2B57B0D482313287 | 63DC87F4FA08BAD5 / C58BD196F0E21F88 / 2356B8223BA04A5D |
| `large_form_r150_alt_sky_silhouette` / `_open_close` | CCB510FC3586B10B / B51D73D03F601743 | D63B586153DDE2BD / E970E7B9AC5F7B47 |
| `contour_final/base_contour_alt_sky_silhouette.json` | B4C9313B1ABEE2F0 | B26F3B3F9CD235B2 |
| `contour_large_form/compare_lowpass_sigma2pct.json` | 296FD34C96CA06DD | 7515D0A110B59951 |

### 4.2 标记的变化（只有背段变了）

| 文件 | 背段标记，改动前 → 改动后 | `pending_stretches.back_left_variant`：x 区间 px；点数；区间内的标记 |
|---|---|---|
| 指状尺度 | traced 880 → traced 689 ＋ **offset_from_visible_edge 191**（第 0–190 点，最后一点 (333.301, 895.419)） | 0 … 333.301；191；offset 191 |
| **正式大形 r＝150** | traced 739 ＋ bridge 129 → traced 631 ＋ **offset 108**（第 83–190 点）＋ bridge 129 | 0 … 334.093；191；bridge 83 ＋ offset 108 |
| r＝100 | traced 828 ＋ bridge 43 → traced 637 ＋ offset 191 ＋ bridge 43 | 0 … 333.339；191；offset 191 |
| r＝120 | traced 789 ＋ bridge 81 → traced 634 ＋ offset 155 ＋ bridge 81 | 0 … 333.679；191；bridge 36 ＋ offset 155 |
| r＝135 | traced 756 ＋ bridge 113 → traced 602 ＋ offset 154 ＋ bridge 113 | 0 … 333.778；191；bridge 37 ＋ offset 154 |
| r＝150 先开后闭（仅对照） | traced 739 ＋ bridge 125 → traced 602 ＋ offset 137 ＋ bridge 125 | 0 … 334.047；191；bridge 54 ＋ offset 137 |
| 左端另一种读法（指状 / 大形 r＝150） | 不变（那条线是描的） | 0 … 333.301；173 / 174；traced 173 / bridge 94 ＋ traced 80 |

- 构造段的终点在轮廓上是 x＝333.3 px（白边上的汇合点 (338.2, 901.6) 向外平移 8.84 px 之后）。任务书说的「约 338 px」指的是白边上的那一点；两者是同一处。
- 大形文件的 x 区间上限取「指状尺度区间上限」与「本文件最后一个带新标记的点」两者的较大值（两份文件的 2 px 采样相位不同，差 < 1 px）；指状尺度的原值另存在 `x_range_px_of_finger_scale_file`。
- 接缝平滑区（接缝两侧各约 60 px 弧长）里属于主背的点仍是 `traced`：那些是描出来的点，被平滑移动了 ≤ 0.87 px（`provenance.build_info.left_end.seam.max_shift_by_smoothing_px`）。
- 其它段（波頭、内側の弧）的标记、所有 `in_S7` 都没有变。`json_key_diff.json` 列出了每个文件里变化的键：`segments[back].source`、`source_flags`、`pending_*`、`contour_definition`（仅指状尺度）、`derived_from.sha256`、标记计数；没有任何数值型测量变化。
- 大形各变体里带继承标记的点到指状尺度线的最大距离（写在各自的 `source_flags.traced` 里）：r＝150：937 点，最大 0.531 px，1 点 > 0.519 px；r＝100：1210 点，0.504 px，0 点；r＝120：1093 点，0.509 px，0 点；r＝135：1009 点，0.509 px，0 点；先开后闭 r＝150：914 点，0.540 px，2 点；另一种读法 r＝150：855 点，0.531 px，1 点。
- 没有任何大形变体含 `claw_root_bridge` 点（改动前后都是 0），所以大形文件的 `source_flags` 不再列它。

### 4.3 共享代码还能读吗

| 检查 | 结果 |
|---|---|
| `gw.profile_metrics.load_base_contour` / `base_contour_polyline` / `measure_base_contour`（两种分段），9 个文件 | 全部正常；数字与读备份文件**完全相同**（`loader_check.json`：`numbers_equal_to_before` 全为 true） |
| `tests/test_shape.target_self_check`，9 个文件 | 全部正常；不过的项与改动前相同（正式文件只有 `S4.flattens_towards_crest`） |
| 完整跑 `tests/test_shape.py`（夹具把正式轮廓扫成网格） | 正常跑完；S1 dx −0.844 / dz +0.034，S5 0.136％ / −1.00°，S7 背 0.005625 / 0.01736、波頭 0.00621 / 0.01314、内側の弧 0.006831 / 0.0136，S8 11.25°——与复核者的基线 `verify_tests/runs/none_fixture_builder` 逐位相同。退出码 1 来自早已知道的 `S4.flattens_towards_crest`（目标自己也不过），与标记无关 |

原因：`gw.profile_metrics` 和 `tests/*.py` 只读 `in_S7`，不看 `source` 的取值（`tests/selfcheck_tests.py` 只是把 `source` 列表整体搬动）。未知的 `source` 值不会让它们出错。

## 5. 需要别人知道的事

- **给测试侧的接口**（本次没有改测试）：顶层 `pending_user_confirmation`（字符串列表，现在是 `["back_left_variant"]`）；`pending_stretches["back_left_variant"]` 含 `segment`（"back"）、`x_range_px`、`x_range_H`（同一区间换成 H 单位的 X）、`index_range`（本文件背段的点序号，闭区间）、`n_points`、`index_range_is_contiguous`、`flag_counts`、`in_S7`（true）、`selector`、`what`。背段 x 单调，用 x 区间选点与用序号选点等价。
- `src/gw/profile_metrics.py` 在我工作期间（09:50）被别人改过；`results/step1_prepare/contour_final/metrics.json` 里因此多了几个测试库的键（`S8.tip_junction_deg` 等），不是我的改动造成的。目标 JSON 里的测量块没有受影响。
- `docs/records/step1_large_form.md`、`step1_base_contour.md` 和报告第 9、11 章里写的「背 traced 739＋bridge 129」「`source` 只有四种取值」等说法以本记录和报告第 12 章为准（那些文件不归我，没有改）。
- 指状尺度文件的 `variant.note` 里写的是「见报告第 1 节」，实际内容在第 2 节；没有动（不在任务范围内）。

## 6. 推测 / 建议（与事实分开）

- 推测：背的 S7 里约 22％ 的点（191 / 868）落在这段待确认的构造线上；如果用户改判为另一种读法，这一段的目标会移动最多 7.1％（裁决者的数字），背的 S7 结论会变，其余两段不受影响。
- 建议：测试报告里对背段分「区间内 / 区间外」各给一组 S7；整段的判定照旧。用户确认读法后，删掉 `base_contour_params.json` 里 `pending_user_confirmation` 的这一项并重跑两个脚本。

## 7. 文件

- 改动的源文件：`src/contour/build_base_contour.py`、`build_large_form.py`、`base_contour_params.json`、`large_form_params.json`（改动前的副本在 `results/step1_prepare/contour_flags/before/src_contour/`）
- 重新生成的目标：`target/base_contour.json`、`target/base_contour_finger_scale.json`、`target/large_form_variants/*.json`、`target/base_contour_overlay.png`
- 核对：`results/step1_prepare/contour_flags/hashes_before.json`、`hashes_after.json`、`hashes_compare.json`、`json_key_diff.json`、`loader_check.json`、`runs/shape_official_large_form/`、`scripts/hash_contours.py`、`scripts/diff_json_keys.py`、`scripts/check_loaders.py`、`before/`（备份）
- 看过的图：`target/base_contour_overlay.png`、`results/step1_prepare/contour_large_form/f_decision_sheet.png`、`e_left_end_readings.png`、`results/step1_prepare/contour_final/crop_01_back_left_end.png`、`base_contour_finger_scale_overlay.png`
- 运行日志：`results/logs/build_base_contour_20260920_09*.log`、`build_large_form_20260920_09*.log`、`hash_contours_*.log`、`check_loaders_*.log`、`diff_json_keys_*.log`
