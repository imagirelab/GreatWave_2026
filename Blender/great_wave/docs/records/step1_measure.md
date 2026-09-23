# 结果记录：第 1 步（准备）— 轮廓遮罩与截面轮廓指标库

日期：2026-09-20　环境：Blender 5.2.2 LTS（无界面）、Python 3.13.13、numpy 2.3.4
定义的详细说明见 `docs/measurement_definitions.md`。机器上没有 git，本记录代替 commit。

## 1. 做了什么

| 文件 | 内容 |
|---|---|
| `src/gw/raster.py` | 精确、确定性的 numpy 光栅化（像素中心覆盖、闭三角形、向量化扫描线）；`rasterize_exact` 另外记录轮廓边界与像素中心网格线的精确交点（`EdgeData`）；水体填充；基于游程的连通分量（向量化并查集）、最大分量、洞的填充与报告；暴力参考实现（只用于测试）。 |
| `src/gw/silhouette.py` | `ViewRect`（`CAM_print` 取景或任意矩形、可镜像、H 归一化）；求值网格 → 世界三角形；`silhouette_mask` / `mask_from_triangles`；`extract_profile`（沿像素缝追踪 + 精确交点）；`profile_of_objects`、`profiles_over_frames`；`setup_cam_print`；`render_mask_cycles` + `compare_masks`；`draw_overlay`。 |
| `src/gw/profile_metrics.py` | `measure_profile`（波頂／波頭の先／最深点／分段／h／x_c／θ／o／φ／S4／S8）、`s7_deviation`、`position_checks`（S1 S2 S3 S5 S6）、`measure_sequence`（逐帧 + 轮廓位移）、基準輪郭 json 的读取与同定义测量。 |
| `tests/fixtures/make_synthetic_wave.py` | 解析的合成测试浪（固定拓扑网格、UV、`crest_rim`、31 个 Shape Key、三种收束、`--profile-json`）。输出 `tests/fixtures/synthetic_contour.json`。 |
| `tests/selftest_measure.py` | 自测（52 项）。 |
| `docs/measurement_definitions.md` | 全部定义、示意图、待用户确认的解释清单。 |

运行：

```powershell
& "G:/research/Wave Simulation/blender/great_wave/tools/run_blender.ps1" tests/selftest_measure.py
# 可选：-ScriptArgs '--quick' | '--skip-cycles' | '--skip-perf'
& ".../tools/run_blender.ps1" tests/fixtures/make_synthetic_wave.py -ScriptArgs '--taper','clip','--out-blend','<路径>'
```

## 2. 测试结果（`results/step1_prepare/measure/selftest_measure_report.json`）

52 项检查，0 项失败，总耗时约 45 s，Blender 退出码 0。

| 组 | 检查内容 | 结果 |
|---|---|---|
| A 光栅化 | 7 类三角形（随机／整数顶点／顶点在像素中心／退化与重复顶点／细条／超大／极小）对照暴力边函数实现 | 差 0 px |
| A | 共享边无缝（混合绕向、随机内部顶点） | 差 0 px |
| A | 非有限值被忽略；空输入；正侧面三角形 skip = 0 px、line = 111 px；结果与顺序／绕向／分块无关 | 通过 |
| A | `rasterize_exact`：圆盘边界的精确交点对照解析圆 | 最大误差 1.0e-3 px（float32 存储 + 1440 边形的弦误差），244 个交点 |
| A | 不覆盖任何像素中心的细条能接到边界上 | 交点 20.9000（应为 20.9） |
| B 遮罩工具 | 4／8 连通分量对照 flood fill；最大分量去碎片；洞的检测 | 通过 |
| C 解析曲线上的指标 | 三角波：θ = 50.0000、背 30.0000、无张出、o = 0；波頂的折角被 S8 抓到（78.2°） | 通过 |
| C | 圆弧上 S8 = 间距 ÷ R | 2.1705° 对 2.1703° |
| C | 终幕解析轮廓：波頂／波頭の先／最深点对照闭式解；φ = −40.000000、θ = 175.000000、o 误差 < 0.05％ | 通过 |
| C | S7 对自身 json ≈ 0（p95 0.0001％）；整体上移 1％ 时背／波頭 mean = 0.808／0.813％（≈ 1％×cos 斜率）；`in_S7=false` 的 284 个点被排除 | 通过 |
| C | 同一 φ 定义用于 json：用 json 的分界点 −40.0000，重新检测 −40.0000 | 通过 |
| D 合成浪（经 Blender 求值） | 443×57 = 25,251 顶点、24,752 四边形、1 个 UV 层、`crest_rim`、31 个 Shape Key | 通过 |
| D | `setup_cam_print` 与像素网格的最大偏差 | 0.0016 px |
| D | 求值后的 Shape Key 网格与解析顶点的最大差 | 1.9e-6 m |
| D | 裾（网格外缘）在抽查帧上 \|Z\| 的最大值 | 0 m |
| D | **exact，全分辨率：位置误差** | **最大 0.0155％ 画面高**（要求 0.2％） |
| D | **exact，全分辨率：θ／φ 误差** | **最大 0.096°**（要求 1°） |
| D | exact，1/2 和 1/4 分辨率 | 0.0158％／0.101° 与 0.0135％／0.104° |
| D | pixel（无精确交点），全／半／四分之一分辨率 | 0.192％／0.41°；0.261％／0.50°；1.169％／1.05° |
| D | 全部轮廓完整（左边框→右边框）、无洞、所有像素缝都有精确交点 | 通过 |
| D | 终幕对自身解析轮廓的 S7 | 三段 mean ≤ 0.0009％，p95 ≤ 0.0015％ |
| D | 终幕 S8 判定值 4.38°（在波頭段），不排除先端时 48.5°，先端转角 135.0°（解析 135°） | 通过 |
| D | Blender 路径与纯 numpy 路径的遮罩 | 差 0 px |
| D | 镜像矩形（向 −X 行进的浪）；自定义矩形（40 px/m，960×540） | 指标差 0；1.8e-5 |
| I 运动序列 | 31 帧、965×649、exact：h ≤ 1.2e-5 H、x_c ≤ 1.5e-4 H、o ≤ 1.5e-4 H、θ ≤ 0.13°、φ ≤ 0.07°；0.15 s／帧 | 通过 |
| I | h(t) 的「假下降」（解析 h 不下降） | 5.1e-6 H；o 为 0 |
| E 失败示范 | `zscale` 收束：真实空洞中 568,193 px 被挡；测得 `overhanging=False`、θ = 90°、o = 0 | 如预期 |
| E | 无收束：skip 0 px；line 5,281 px，1 个洞 = 填充后轮廓的 46.0％ | 如预期 |
| F Cycles | 10,010,246 px 中 4 px 不一致，全在边界圈上；渲染 1.1–1.3 s | 通过 |
| G 性能 | 742,560 顶点／247,520 三角形的三角形汤：exact 全分辨率 2.1–2.6 s；204k 胖三角形随机汤 1.5 s | 通过 |
| H `--profile-json` | 扫 `synthetic_contour.json`，半分辨率：S7 最差 p95 0.0029％，无洞 | 通过 |

没有通过不了的项。`target/base_contour.json` 在自测运行时还不存在，所以「把真实基準輪郭扫成网格再量回来」那一项只记了「文件不存在」（存在时会自动运行，只报告、不影响通过与否）。

## 3. 结果图（都在 `results/step1_prepare/measure/`，都已逐张看过）

- `definitions_overview.png`、`definitions_head_zoom.png`：定义示意图。
- `overlay_frame_001/007/013/019/025/031.png`：合成浪 6 帧的遮罩 + 轮廓线 + 地标。
- `crop_final_crest.png`、`crop_final_tip.png`、`crop_final_deepest.png`、`crop_final_head.png`：终幕局部放大（绿色虚线 = 解析轮廓）。
- `fixture_motion_curves.png`：h／x_c／θ／o／φ 的实测与解析曲线。
- `failure_zscale_taper.png`、`failure_zscale_taper_crop.png`：端部截面挡住空洞的样子。
- `failure_no_taper_holes.png`：无收束（非实心）的样子与洞的报告。
- `cycles_vs_numpy.png`、`cycles_mask_final.png`：Cycles 交叉核对。
- `profile_json_mode_final.png`：`--profile-json` 模式的终幕。
- `houdini_api_smoke_test.png`：在 `1.abc` 上的 API 冒烟测试（第 20／35／45／50／55／60 帧），**不是**运动读取。

## 4. 实测到的事实

1. 精确交点（exact）模式下，测量精度与遮罩分辨率基本无关：965×649 与 3859×2594 的最大位置误差分别是 0.0135％ 和 0.0155％ 画面高。不用精确交点时，二值遮罩的 ±0.5 px 量化在极值点附近被放大：1/4 分辨率下最深点的误差到 1.17％。
2. 按说明书的定义 o = 波頭の先超出波頂铅垂线的水平距离，o(t) 在张出刚出现的那一帧不连续：合成浪第 16→17 帧 o 从 0 跳到 0.2255 H（解析值同样跳变，不是测量误差）。
3. 縁厚 2.5％ H 的合成浪终幕：不排除波頭の先附近时 S8 的最大切线差是 48.5°（阈值 15°），排除先端前后 2％ 画面高之后是 4.4°；跨过先端的转角 135°。
4. 只缩放 Z 的收束会让端部截面完全挡住空洞；纯拉伸（无收束）的薄片投影面积为 0。
5. `1.abc`：闭合的流体块网格（有底面，不是开口薄片），顶点 611,874／三角形 203,958，Blender 导入 0.3 s、每帧取网格 0.2 s；第 1 帧顶面 Z 的第 95–99 百分位是 0.089–0.095 m，底面约 −1.14 m；X 范围 −27.8…+5.26 m，第 50 帧波頂在 X ≈ −0.5 m、向 +X 张出；第 60 帧在我试的矩形里轮廓是平的（h = 0.002）。
6. Git Bash 里能找到一个 `python3`（3.12.10），与「机器上没有系统 Python」的环境说明不一致。我只在一次文本替换里用过它（没有安装任何东西，也没有写到工程目录之外），库和测试的全部计算都只用 Blender 自带的 Python。

## 5. 推测

1. 真实大浪的 o(t) 在张出开始时也会有一个跳变，但幅度应当比合成浪小（真实的浪先变竖直的位置紧挨着波頂）。幅度要等 Houdini 参考读出来才知道。
2. 原画波頂是宽 5.36％ 的平台（基础库的记录），所以 S1 的横向误差对「波頂 x 怎么定义」很敏感；用稳健极值时，模型和基準輪郭用的是同一个定义，两者的偏差大部分会抵消。
3. 第 60 帧轮廓变平，与 orchestrator 记录的「第 75、100 帧的包围盒与第 1 帧相同」一致，可能是模拟在 55–60 帧之间结束或回到初始状态；需要参考读取的 agent 确认。

## 6. 建议

1. 所有 S／M／G 测试和 Houdini 读取都用 `exact=True`；运动曲线用 `scale=0.25–0.5` 就够（0.15–0.35 s／帧），终幕的叠加图再用全分辨率。
2. M2／M3／M4 的单调性阈值是 0：测量噪声底约 5e-6 H（h）。测试里不要改阈值，但建议同时报告「违反量」的数值，方便区分真实的回退和 1e-5 H 量级的数值噪声。
3. 请用户确认 `docs/measurement_definitions.md` §4 的 11 条解释，尤其是：波頂 x 的稳健定义（与 S1 平台问题相关）、S8 把波頭の先当作段边界并排除前后 2％、o 的不连续以及是否并用 `cavity_depth`、φ 的窗口。
4. 做真实浪体的两端收束（§7a）时，每个方案都要用 `profile['holes']` 和 S2／S7 检查「端部截面是否挡住空洞」；合成浪的 `clip` 收束（先水平缩回波頭、再压低）是一种不挡空洞的构造，可以作为候选之一，但它在端部会留下一道竖直的崖，外观未必可接受。
5. Houdini 参考：取景矩形的左右边都要落在网格的 X 范围以内（例如 X −22…5.2 m），水体取静水面（约 0.09 m），不需要 `mirror_x`；波頭在第 55 帧前后就到了网格的右端，矩形右边放不下更多余量，这一点读运动时要留意。
6. 如果以后要把测量参数给用户看，建议在 `params.json` 里加一项 `measure_params`（`profile_metrics.get_params()` 已经会读它），现在的默认值和说明写在 `profile_metrics.DEFAULT_PARAMS` 里。
