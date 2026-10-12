# 原画と同じ物差し（STUDY52 の道具の写し）

元は `Unity/Build/STUDY52/tools/`（リポジトリに入らない置き場所）。どの計算機でも動くように、置き場所の書き方だけ相対に直して写した。量の定義は変えていない。

- `s52_shape.py`：形の量を、水の 2 値の格子から読む。`measure_mask(M, X, Z)`
  - `M[行 = z（下から上）, 列 = x]`：水なら真。底につながる水だけにしておく（飛んだ滴を除く）。
  - `X`・`Z`：列・行の座標（m）。`Z` は静かな水面から上が正。間隔は 0.05 m（`FINE`）で作る。
  - 長さはどれも頂の高さ η_c で割った値で出る。
- `print_mask()`：原画の輪郭（`Tools/PaintingTruth/targets/main_wave_outline_envelope.json`）から水の格子を作る。縦の伸び 1.3（Cartwright & Nakamura 2009）を戻した読みが `shape_measures.json` の `print.cn`、描かれたままが `print.drawn`。
- `shape_measures.json`：原画の量と、FLIP42（平らな海底の 2D）の量。
- `s52_common.py`：共に使う小さな関数（FLIP42 の記録を読む関数は、ほかの計算では使わない）。

主な量（`print.cn`、原画）：前の面の弦（0.1〜0.5 η_c）約 64°、前の足（0.1 η_c の所、頂から）0.25、唇の下の空気 0.54 以上、唇の厚み 0.35、覆いの面積 0.14〜0.19、後ろの角（0.7〜0.9 η_c）31°、0.7 η_c の幅 1.32。

要る物：Python 3、numpy、Pillow、scikit-image。
