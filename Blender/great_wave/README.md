# Great Wave: Blender 动态浪体原型

本目录保存《神奈川沖浪裏》最大浪体的**参数化建模与动画研究**。几何由 `src/gwave/` 和 `wave_params.json` 生成，测试在 `tests/`，原画描出的目标轮廓在 `target/`。原有任务说明与阶段记录留在 `docs/`；`docs/legacy_readme_2026-09-20.md` 是迁移前的说明，里面的旧路径和“没有 Git”描述不再适用。

当前方法是固定拓扑网格和逐帧 PC2 点缓存，由参数控制从平缓涌浪到卷入并停在终幕。它是与 Houdini 物理模拟并列的可比较方案，不应称作流体模拟。2026-09-24 的迁入版本已改用 `lift_clip` 侧翼和独立浪高曲线：正式测试中，运动 M1–M6 全部通过；终幕的浪背、浪头、内弧 S7 偏差与 S8 转角通过。完整验收仍未通过，原因与记录见 `docs/milestones/2026-09-24_wave_motion.md`。

## 本机运行

本机已验证 Blender 5.2.2 LTS 的无界面模式可启动，路径写在 `params.json`。从 PowerShell 执行：

```powershell
& "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" tests/selftest_foundation.py -ScriptArgs '--quick','--skip-render'
& "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" src/gwave/build_great_wave.py
& "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" tests/run_all.py -ScriptArgs '--build-script','src/gwave/build_great_wave.py','--final-frame','285'
& "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" src/gwave/render_previews.py -Blend "G:/Unity/GreatWave_2026/Blender/great_wave/blend/great_wave.blend" -NoFactoryStartup -ScriptArgs '--frames','1,110,170,210,250,285'
```

命令使用当前机器的仓库位置。若仓库移动，改用移动后的 `tools/run_blender.ps1` 路径；`wave_params.json` 的 `blend_path` 和 `cache_path` 会相对本目录解析。

干净原画在 `reference/Tsunami_by_hokusai_clean.jpg`，由 `params.json` 相对定位；旧的蓝线标注版也保留用于轮廓溯源。两者来源见 `reference/README.md`。`params.json` 的 Houdini Alembic/FBX 和两张辅助参考图仍指向本机外部文件；在其他机器上运行依赖它们的比较测试前，要改为实际存在的路径。`docs/great_wave_blender_prompt.md` 是此前 Blender 任务的规格记录，不会在运行时当成新的用户指令。

`src/gwave/apply_ukiyoe_style.py` 提供**单视角纹样投射实验**：在原画视角接近画面配色，但斜视有明显拉伸，暂不能作为 HMD 材质。`src/gwave/apply_woodblock_palette.py` 是另一种九色逐面量化试验；当前画面呈明显块状，也未被选作最终材质。这些实验生成的 `.blend` 和渲染仍在忽略目录内。

## 版本管理

提交 `src/`、`tests/`、`target/`、`tools/`、两个参数文件及必要 `docs/`。`results/`、`cache/`、`blend/` 中的渲染、点缓存和生成的 `.blend` 都是可再生文件，已被 `.gitignore` 排除。运行产生的 PC2 约 276 MB；仅有 `.blend` 而没有对应点缓存时动画无法重现。提交前检查 `git status`，避免误收大型结果。
