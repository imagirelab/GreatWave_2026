# 19：30 Hz保持による幾何差の独立解析

既存のPython/NumPyだけで実行する。解析スクリプトはHoudini/Unityを起動せず、指定入力を読み取り、指定した出力JSONだけを書く。

`reference60.bytes`は`GW19REF1`・121時刻・60 Hzの正式データに限定する。各試料のPと三角形SHA、実DOP時刻を`19_cache_index.json`と照合してから解析する。

30 Hzはmasterの偶数試料を保持する。60 Hzの奇数時刻60個について、前の偶数形状との距離を計算する。各方向256個の面積比例表面点から、相手の全三角形への最短距離をAABB階層で探索する。頂点番号を跨時刻の対応として使わない。

±X/±Y/±Zの各端から幅5%の帯にある最大16点も別集計する。これは外周・高低部の限定指標で、北斎の波頭や白波の尖端を検証したことにはならない。全点から求めたboundsと表面積も併記する。

結果は標本表面距離であり、厳密Hausdorff距離や物理的真値との誤差ではない。60 Hzと30 Hzの61共通時刻は同じmaster payloadの対応を記録する。Alembic/VATでの実再生や書出ファイルの一致は別途検査が必要。

実行例（本機の既存NumPy環境）：

```powershell
& 'C:\Users\wang6\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ./Houdini/Sampling19/Source/analyze_sampling19.py --self-test
& 'C:\Users\wang6\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ./Houdini/Sampling19/Source/analyze_sampling19.py --reference 'G:\Unity\GreatWave_2026_Fresh\Houdini\Sampling19\Exports\reference60.bytes' --cache-index 'G:\Unity\GreatWave_2026_Fresh\Houdini\Sampling19\Evidence\19_cache_index.json' --output ./Houdini/Sampling19/Evidence/19_hold_geometry_analysis.json
```

解析結果に入力・index・解析scriptのSHAを残す。実行中の入力変更があれば中止する。合格閾値を捏造せず、PC画像/実行検査と合わせて中間結果として読む。

## 今回の実測

- 参照126,970,116 bytes、SHA256 `5b9687f4443d2fc1a155c06cd795f22e92f9078a05fc109506567e5f09393c98`。
- 60個の奇数時刻を全て解析。61共通時刻は同じmaster payloadの対応を記録。
- 各比較の標本距離p95の最大は0.0843402 m（試料111、1.85秒）。
- 全標本中の最大距離は1.0621253 m（保持試料82→実試料83、約1.383秒）。該当点はHoudini座標 `(-0.08287, 0.00490, -6.49929) m` で、±6 mの粒子計算領域を越えた面の端にある。この値を波頭の段差やHMDの知覚値と呼ばない。
- 全点bounds端の最大変化は0.1803842 m（同じ試料83）。
- 解析的3例とランダム32点で距離式/AABB探索を検査した。最大差が出た実面でも18点を全三角形総当たりと比較し、差0 m。

全数値は同じ60 Hz試料を基準にした保持差である。60 Hzの再生が連続時刻で誤差ゼロ、または物理的に正しいことを意味しない。元の面化、領域外流出、形状分離による変化を含む。

追加の再現検査：

```powershell
& 'C:\Users\wang6\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' ./Houdini/Sampling19/Source/verify_analysis.py --report ./Houdini/Sampling19/Evidence/19_hold_geometry_analysis.json --output ./Houdini/Sampling19/Evidence/19_analysis_validation.json
```
