"""gw -- great_wave の Blender プロジェクトで使う基本機能。numpy と bpy のみを使用する。

モジュール
----------
bootstrap : sys.path と '--' 以降の引数、画面なし実行用の接頭辞付きログ
paths     : プロジェクトのパス、params.json / thresholds.json の読込、書込先の制限
frame     : 原画の px・高さ比・H 単位・メートル間の変換、CAM_print の設定値（仕様4）
imgio     : bpy による画像読込、Python のみで正確に処理する PNG の書込と読込
draw      : numpy によるラスタ描画（線、記号、重ね画像、縮小、一覧画像、5x7文字）
plot      : numpy による線グラフ

利用側が必要なモジュールだけを読み込む（`from gw import frame, draw`）。
`gw` 自体を読み込んでも重い依存関係は読み込まず、bpy は不要。
"""

__version__ = "0.1.0"
__all__ = ["bootstrap", "paths", "frame", "imgio", "draw", "plot"]
