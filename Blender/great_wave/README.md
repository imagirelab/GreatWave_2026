# Great Wave: Blender 动态浪体原型

本目录保存《神奈川沖浪裏》最大浪体的**参数化建模与动画研究**。几何由 `src/gwave/` 和 `wave_params.json` 生成，测试在 `tests/`，原画描出的目标轮廓在 `target/`。原有任务说明与阶段记录留在 `docs/`；`docs/legacy_readme_2026-09-20.md` 是迁移前的说明，里面的旧路径和“没有 Git”描述不再适用。

当前方法是固定拓扑网格和逐帧 PC2 点缓存，由参数控制从平缓涌浪到卷入并停在终幕。它是与 Houdini 物理模拟并列的可比较方案，不应称作流体模拟。2026-09-24 的版本采用 `lift_clip` 侧翼和独立浪高曲线；最新参数把中央浪唇半宽缩至 0.10H。正式测试中，运动 M1–M6 全部通过；终幕的浪背、浪头、内弧 S7 偏差与 S8 转角通过。完整验收仍未通过，原因与记录见 `docs/milestones/2026-09-24_foam_and_review_assets.md`。

## 当前可查看成果

`deliverables/` 中有两份可直接打开的**静态终帧** `.blend` 和两段约 11.5 秒的运动视频：`great_wave_final_print.blend` / `great_wave_motion_print_reference.mp4` 用于原画视角比对，`great_wave_final_3d.blend` / `great_wave_motion_3d.mp4` 用于检查三维斜视。主体之外还有独立动画白波和浪爪。详细测试数据、图像及限制见 [白波与审阅文件记录](docs/milestones/2026-09-24_foam_and_review_assets.md)。

原画视角材质是单相机投射，会把原画的小船也映到浪体；它提供终帧色彩和纹样的参考，不代表 HMD 中可用的三维材质。三维版本使用沿表面 UV 的程序材质，斜视不会产生投射条纹，但目前离原画的细节还有明显距离。两个 `.blend` 不含动态缓存；要修改动画请按下方顺序重建。

## 本机运行

本机已验证 Blender 5.2.2 LTS 的无界面模式可启动，路径写在 `params.json`。从 PowerShell 执行：

```powershell
& "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" tests/selftest_foundation.py -ScriptArgs '--quick','--skip-render'
& "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" src/gwave/build_great_wave.py
& "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" tests/run_all.py -ScriptArgs '--build-script','src/gwave/build_great_wave.py','--final-frame','285'
& "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" src/gwave/render_previews.py -Blend "G:/Unity/GreatWave_2026/Blender/great_wave/blend/great_wave.blend" -NoFactoryStartup -ScriptArgs '--frames','1,110,170,210,250,285'
```

生成原画视角动画时，在主体构建后依次对 `blend/great_wave.blend` 运行 `apply_ukiyoe_style.py`，对输出的 `blend/great_wave_styled.blend` 运行 `add_animated_foam.py`。三维材质版把第一步换为 `apply_procedural_ukiyoe.py`，白波脚本加 `--output blend/great_wave_procedural_foam.blend`。带白波场景再交给 `export_final_pose.py` 与 `render_motion_video.py`。这些脚本都在 `src/gwave/`；可传 `--help` 查看输出参数。白波烘焙和主体正式测试都读取同一主体 PC2，运行时请先后执行。

命令使用当前机器的仓库位置。若仓库移动，改用移动后的 `tools/run_blender.ps1` 路径；`wave_params.json` 的 `blend_path` 和 `cache_path` 会相对本目录解析。

干净原画在 `reference/Tsunami_by_hokusai_clean.jpg`，由 `params.json` 相对定位；旧的蓝线标注版也保留用于轮廓溯源。两者来源见 `reference/README.md`。`params.json` 的 Houdini Alembic/FBX 和两张辅助参考图仍指向本机外部文件；在其他机器上运行依赖它们的比较测试前，要改为实际存在的路径。`docs/great_wave_blender_prompt.md` 是此前 Blender 任务的规格记录，不会在运行时当成新的用户指令。

`src/gwave/apply_ukiyoe_style.py` 提供**单视角纹样投射实验**：在原画视角接近画面配色，但斜视有明显拉伸，暂不能作为 HMD 材质。`src/gwave/apply_woodblock_palette.py` 是另一种九色逐面量化试验；当前画面呈明显块状，也未被选作最终材质。这些实验生成的 `.blend` 和渲染仍在忽略目录内。

## 版本管理

提交 `src/`、`tests/`、`target/`、`tools/`、两个参数文件、必要 `docs/` 与 `deliverables/` 的小型静态审阅文件及视频。`results/`、`cache/`、`blend/` 中的渲染、点缓存和生成的动画 `.blend` 都是可再生文件，已被 `.gitignore` 排除。运行产生的主体 PC2 约 289 MB；仅有动画 `.blend` 而没有对应点缓存时动画无法重现。提交前检查 `git status`，避免误收大型结果。
