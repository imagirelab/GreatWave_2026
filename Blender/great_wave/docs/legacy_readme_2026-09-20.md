# great_wave — 《神奈川沖浪裏》大浪（Blender，固定拓扑动画网格）

任务说明书：`G:/research/Wave Simulation/great_wave_blender_prompt.md`（下称「说明书」）。
本目录存放全部脚本、参数、测试、目标数据和结果记录。**同一份参数 → 同一个结果**，任何状态都不允许只留在 .blend 里；不做手工雕刻、不逐点手调。

## 1. 目录结构

```
blender/great_wave/
├─ params.json              唯一的参数文件；每一项都带 provenance / comment
├─ README.md
├─ src/
│  ├─ gw/                   基础库（只依赖 numpy + bpy）
│  │  ├─ bootstrap.py       sys.path、'--' 之后的参数、带前缀的日志
│  │  ├─ paths.py           所有路径、params/thresholds 读取、写入保护、双档阈值判定
│  │  ├─ frame.py           px ↔ ％ ↔ H ↔ m 换算、CAM_print 数值与创建
│  │  ├─ imgio.py           读图（bpy）、无损 PNG 读写（纯 python）
│  │  ├─ draw.py            numpy 光栅绘图（线、标记、叠加、缩放、拼图、5x7 字体）
│  │  └─ plot.py            numpy 折线图
│  ├─ contour/              基準輪郭的提取与轮廓指标（由轮廓 / 测试 agent 填充）
│  └─ ref/                  Houdini 运动参考的读取（由参考 agent 填充）
├─ tests/
│  ├─ thresholds.json       S1–S8、M1–M6、G1–G5 的全部阈值（两档，见 §5）
│  ├─ selftest_foundation.py
│  └─ fixtures/
├─ target/                  base_contour.json、candidates/a、candidates/b
├─ results/
│  ├─ step1_prepare/        第 1 步（准备）的输出；foundation/ 是基础库自测的图
│  ├─ logs/                 tools/run_blender.ps1 写的完整日志
│  └─ <日期时间>/            之后每次测试运行：metrics.json、叠加图、曲线图（说明书 §9）
├─ docs/records/            每完成一项写一份结果记录（中文）
├─ tools/run_blender.ps1    无界面运行脚本的包装
└─ blend/                   大文件（.blend、缓存、导出），按需创建，不进版本管理
```

## 2. 环境约束（务必遵守）

- Blender 5.2.2 LTS：`G:/SteamLibrary/steamapps/common/Blender/blender.exe`。本次会话**没有 Blender MCP**，一律无界面（headless）运行。
- 可用的 Python 只有 Blender 自带的 Python 3.13 + numpy 2.3.4。**没有** scipy / PIL / cv2 / matplotlib / skimage / imageio，没有系统 python，没有 git。
- **不安装、不下载任何东西**（pip、winget、插件都不行）。
- **只允许写入** `G:/research/Wave Simulation` 和本次会话的 scratch 目录（见 `params.json` 的 `allowed_write_roots`）。`gw.paths.assert_writable()` / `gw.imgio.save_png()` 会对其它位置抛 `PermissionError`；输入文件缺失时抛 `FileNotFoundError`——**不会静默回退到 C 盘**。
- **不改 PYTHONPATH**（也不读它）。脚本里用 `sys.path.insert` 指向 `src/`（见 §4）。
- 输入文件只读：原画、`1.abc`、`1.fbx`、两张参考图、说明书。`assert_writable()` 拒绝把它们当作写入目标。
- 说明书 §3 的大文件目录 `G:\research\model\great_wave\` 在本次工作里改为 `blender/great_wave/blend/`（`params.json: blend_dir`），原因：用户要求工程建在 `G:\research\Wave Simulation`，且禁止写到该目录之外。
- 机器上没有 git，说明书要求的「每完成一项一个 commit」目前做不到；用 `docs/records/` 的结果记录代替，等用户决定。

## 3. 怎样运行

推荐用包装脚本（完整日志进 `results/logs/<脚本名>_<日期时间>.log`，屏幕只显示以前缀 `GW` 开头的行；Blender 退出码原样返回，Python 未捕获异常 → 1，并自动打印日志末 30 行）：

```powershell
& "G:/research/Wave Simulation/blender/great_wave/tools/run_blender.ps1" tests/selftest_foundation.py
& ".../tools/run_blender.ps1" tests/selftest_foundation.py -ScriptArgs '--quick','--skip-render'
& ".../tools/run_blender.ps1" src/ref/some_script.py -Prefix REF -ScriptArgs '--frame','50'
& ".../tools/run_blender.ps1" tests/xxx.py -Blend "G:/research/Wave Simulation/blender/great_wave/blend/final.blend"
```

参数：`-Script`（相对路径按工程根目录解析）、`-Prefix`（默认 `GW`）、`-ScriptArgs`（传给脚本、位于 `--` 之后）、`-Blend`、`-BlenderExe`（默认取 `params.json`）、`-ShowAll`、`-NoFactoryStartup`。

如果本机 PowerShell 执行策略禁止运行 .ps1：`powershell -ExecutionPolicy Bypass -File ".../tools/run_blender.ps1" <脚本> ...`（只影响这一个进程，不改系统设置），或者直接调用 Blender：

```powershell
& "G:/SteamLibrary/steamapps/common/Blender/blender.exe" --background --factory-startup --python-exit-code 1 --python "G:/research/Wave Simulation/blender/great_wave/tests/selftest_foundation.py" -- --quick
```

注意工程路径里有空格，路径一律加引号。Blender 的 stdout 很吵，脚本用 `bootstrap.log()` 输出带前缀的行，再用 `Select-String` 过滤。

## 4. 脚本模板

```python
import os, sys
_SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)          # 不改环境变量
from gw import bootstrap, paths, frame, imgio, draw, plot

args = bootstrap.script_args()        # '--' 之后的参数；或 bootstrap.parse_args(argparse_parser)
F = frame.get_frame()                 # 由 params.json 构造
painting = imgio.load_painting_rgb()  # uint8 (2594, 3859, 3)，行自上而下
...
bootstrap.finish(ok, "my_test")       # 打印 'GW RESULT PASS/FAIL ...' 并以 0/1 退出
```

（`src/<包>/` 下的脚本把 `".."` 换成到 `src` 的相对路径即可。）

## 5. 坐标、单位、阈值

坐标（说明书 §4；公式是唯一依据，实现见 `src/gw/frame.py`）：

| 名称 | 含义 |
|---|---|
| px | 原点左上，x 向右、y 向下，**连续坐标**；像素 (i, j) 的中心是 (i+0.5, j+0.5)；x∈[0,3859]，y∈[0,2594] |
| pct | 左から ％（相对图宽）、上から ％（相对图高）——说明书 §5 的写法 |
| H | (X_H, Z_H)，以浪高 H 为单位；波頂 = (0, 1)，谷的水面 Z_H = 0，+X = 船の側 |
| m | H 坐标 × `WAVE_HEIGHT_M`（默认 11 m） |
| pct_h | **长度**单位「画面高的 ％」：1％ = 25.94 px = 0.0151515 H；**水平方向的差也用图高的 ％ 表示** |

由 `crest_left_pct=38.2`、`crest_top_pct=8.7`、`height_pct=66.0` 和图像尺寸导出：
`frame_h = 1.515152 H`，`frame_w = 2.254036 H`，`x_left = -0.861042 H`，`x_right = +1.392994 H`，`z_top = +1.131818 H`，`z_bottom = -0.383333 H`。

`CAM_print`：正交相机，视线沿 +Y，`rotation_euler = (π/2, 0, 0)`，`ortho_scale = frame_w × H`（H=11 m 时 24.794397 m），位置 `((x_left+x_right)/2·H, -200, (z_top+z_bottom)/2·H)`，渲染分辨率 3859×2594。用 `frame.get_frame().make_cam_print(scene)` 创建，大家用同一个实现。

阈值 `tests/thresholds.json` 有**两档**，测试必须**两档都报告** pass/fail，不得默默只选一档：

- `spec`：说明书原文的阈值；
- `user_relaxed_5pct`：出处是用户 2026-09-20 的消息「各个误差率可以允许在5%以内」。目前的工作解释：位置类容许误差 → 画面高的 5％，S3 → ±5％，其余（角度、运动比率、网格检查、S6 外边界）与 `spec` 相同。**这个解释尚待用户确认。**

用 `paths.check_threshold("S7", "mean_dev_pct_h", measured)` 一次得到两档的判定。**不允许**为了通过测试去改阈值、改基準輪郭或挪相机。

## 6. 汇报规范

- 分开写三类内容：实测到的事实 / 推测 / 建议；测不到、读不到的直接说明，不补数值。
- 给用户看的文档（`docs/*.md`、记录）用中文并保留说明书里的日文术语；代码标识符和注释用英文；画进图片里的文字只能是 ASCII。
- 大图查看时会被缩小，判断细节一定要另存放大的局部图（宽 ≤ 1600 px，`draw.View`）。

## 7. 基础库自测

```powershell
& "G:/research/Wave Simulation/blender/great_wave/tools/run_blender.ps1" tests/selftest_foundation.py
```

输出在 `results/step1_prepare/foundation/`，记录见 `docs/records/step1_foundation.md`。
