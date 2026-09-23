# 大浪本体的生成（第 2、3 步的第一版）— 2026-09-20

> 说明：用户在第 1 步停点之后指出“没有看到任何被执行的海浪”，于是没有等停点的答复，先按推荐默认值把大浪做了出来。
> 所有默认值都是 `wave_params.json` 里的参数，标了 PENDING 的等用户决定后改参数重建即可。

## 做了什么

- `src/gwave/profile_motion.py`（只用 numpy）
  - **终幕截面** = `target/base_contour.json`（大形 r=150）+ 画面左端以外的背的 C¹ 延伸（§7b，默认水平长 3.0 H，端部切线取 3％ 弦 ≈ 14°）+ 被挡住的内側の弧末端重画成水平落到 Z=0 的 Bezier 和 1.2 H 的平谷（§7c）。按曲率自适应重采样成 421 点（U）。
  - **起始截面** = 高 0.05 H 的高斯涌，同一批采样点铺在上面；波頭（波頂→波頭の先→下侧）那一段的弧长起始只有终幕的 25％。
  - **中间帧** = 切线角和线段长度的插值（不是位置插值），每个采样点有滞后：背和前面先动，波頭上侧随后，波頭の先和下侧最后；角度略领先于长度，所以是“前面变陡 → 唇部从波頂长出来 → 向下卷”。所有点在 τ=1 同时到位。
  - **时间律** τ(frame)：单调三次 Hermite，经过 (1, 0)、(152, τ_onset)、(210, τ_curl)、(285, 1)，两端斜率为 0（从静止开始；停止前缓出，M5）。τ_onset 由二分法求“第一次出现张出”的 τ，所以张出确实从第 152 帧开始。
  - **x_c(t)** = 终点 − 2.0 H × (1 − t/T)^1.8（PENDING）。
  - **两翼（§7a，flank_mode = regress）**：离开中央的每一排是同一运动里“发展程度更低”的状态（波頂更低、唇更短、肩部不张出），到两端缩到静水面，并在 X 方向后掠（俯视下的新月形波峰线，§7e）。为了让 `CAM_print` 的侧影在每一帧都等于中央截面、空洞不被挡住，两翼的顶点被约束在中央截面的体内：背面水平推到中央的背上；最深点以下水平拉到内側の弧后面；不张出的肩部整体藏到最深点铅垂线之后；张出的排用“同一材质点、沿中央截面外法线的半平面”裁剪。全部是连续函数，不用最近点投影（会跳）。
- `src/gwave/build_great_wave.py`：固定 421 × 201 = 84,621 顶点的网格；UV = (终幕截面弧长, 沿波峰线位置)；顶点组 `crest_rim` = 波頭の先 ±2％ H 弧长的 U 列；逐帧顶点写成 PC2 点缓存，由 Mesh Cache 修改器读取；场景里有 `CAM_print`（带 50％ 透明的原画背景）、`CAM_view34`、`CAM_front`、`CAM_boat`、参考海面。
- `src/gwave/render_previews.py`：Workbench 无界面渲染连续帧图、终幕与原画的叠加图、MP4。
- `src/gwave/diagnose_motion.py` / `diagnose_steps.py`：二维运动曲线；点缓存里逐帧最大顶点位移的定位。

## 产出

- `G:\research\Wave Simulation\great_wave.blend`（2.6 MB）+ `G:\research\Wave Simulation\cache\great_wave.pc2`（276 MB）
- 预览：`results/wave_build/preview/`（`great_wave_view34_0001-0345.mp4`、`contact_CAM_*.png`、`final_CAM_print_over_painting.png`）
- 二维诊断：`results/wave_build/diagnose/`

重建命令（同一份参数 → 逐位相同的缓存，G5 已验证）：

    & "G:/research/Wave Simulation/blender/great_wave/tools/run_blender.ps1" src/gwave/build_great_wave.py
    & ".../tools/run_blender.ps1" src/gwave/render_previews.py -Blend "G:/research/Wave Simulation/great_wave.blend" -NoFactoryStartup -ScriptArgs '--video'

## 测试结果

见本文件末尾“实测”一节（每次重建后更新）。
