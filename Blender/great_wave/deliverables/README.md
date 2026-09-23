# 大浪阶段成果

这两个 `.blend` 是可直接打开、无需动画缓存的**第 285 帧静态网格**；两段 MP4 展示同一主体和独立白波从涌浪到卷入，再停留约 2 秒。两段视频各 173 帧、15 fps、约 11.53 秒。

- `great_wave_final_print.blend`、`great_wave_motion_print_reference.mp4`：原画视角。主体材质直接投射原画，适合对照终幕，但画面里的小船也成为浪体贴图，转动视角会拉伸。
- `great_wave_final_3d.blend`、`great_wave_motion_3d.mp4`：程序化蓝白材质与斜视角，用于检查三维形状；目前浪唇较直，纹样仍不足。

完整可编辑动画由相邻 `src/gwave/` 脚本与 `wave_params.json` 重新生成。点缓存保存在本机忽略目录 `cache/`，没有上传到 GitHub。检查结果和当前未完成项见 [阶段记录](../docs/milestones/2026-09-24_foam_and_review_assets.md)。
