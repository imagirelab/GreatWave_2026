# 保存した FLIP 場からの独立白波

参照水体の自由発展で保存した実際の `surface`・`vel.x/y/z` を読み、公式の Whitewater Solver で第 2～24 フレームを計算した。主 FLIP の粒子や速度は変更していない。白波の第 96 フレームまでの延長は実施していない。

**独立粒子の出生・移動・加齢・消失と、独立メッシュへの出力を確認した段階。** 北斎の分岐した白い爪の完成、気液二相の巻込み量の実測再現、主波の形成の解決を意味しない。

## 接続

`FLIP の体積場 → Whitewater Source 3.0 → Whitewater Solver SOP → Whitewater Post-Process の Mesh`

- Source の第 4 出力は放出の可視化用なので使用しない。第 1～3 出力を Solver の対応する入力へ接続する。
- 元の計算領域と同じ 24×8×6 m の箱を Container とする。元 FLIP に追加の固体衝突模型はない。第 17 フレーム以降の側壁接近という主計算の制約を白波でも引き継ぐ。
- 実際の液体 SDF は dense volume のため、Source の `enableactivate` と Solver の `sdfactivate` を無効にする。`vel.x/y/z` の密な三つの速度体積を使う。[公式の入力仕様](https://www.sidefx.com/docs/houdini/nodes/sop/whitewatersolver.html)
- Source は元の流体場も出力し、その場を変更しない。圧力・Splash・加速度・渦度・変形からの放出は無効にした。[Whitewater Source](https://www.sidefx.com/docs/houdini/nodes/sop/whitewatersource.html)

## 実行した条件

| 条件 | 値 |
| --- | --- |
| Houdini | Steam 版 Indie 22.0.429 |
| 元の FLIP | `../../results/reference_release/本計算01/fields/` |
| 白波開始 | 第 2 フレーム、24 fps |
| Whitewater Scale | 0.08 m |
| 密度用ボクセル | 0.20 m |
| 放出用ボクセル | 0.12 m |
| 放出深度範囲 | −0.18～+0.12 m |
| 速度範囲 | 0.7～3.5 m/s |
| 曲率範囲 | 0.8～3.0 m⁻¹ |
| 速度角の上限 | 90° |
| 放出倍率・平均寿命 | 1.0・2.0 秒 |
| サブステップ・乱数シード | 2・17 |
| 表示メッシュのボクセル | 0.06 m |

密度制御、表面への付着、浮力・移流は公式ソルバの機構を用いる。Repellants、追加速度ノイズ、OpenCL は無効。表示では Post-Process の Mesh を使い、年齢・深度による表示密度の抑制を無効にした。表示メッシュの設定と粒子の運動は区別する。[Post-Process](https://www.sidefx.com/docs/houdini/nodes/sop/whitewaterpostprocess.html)

## 実際の結果

- 第 2 フレームは空、第 3 フレームに 1570 粒子が生まれ、第 24 フレームで 17,395 粒子になった。累計出生 ID は 17,679、消失は 284。
- `P`・`v`・`id`・`age`・`life`・`pscale`・`depth`・`bubble`・`foam`・`spray` が実際に存在する。第 3～24 フレームの属性の有限値と ID の一意性を確認した。
- 前フレームから生存する同じ ID は位置が動き、`age` は約 1/24 秒ずつ増える。Source の放出プレビューをそのまま書き出したものではない。
- 今回の全区間では `bubble` と `foam` が非零、`spray` は 0。独立した飛沫ができたとは記載しない。これらは排他的な分類番号ではなく、状態の重みである。
- 処理合計 20.21 秒、最大採取メモリ 1741.26 MiB。粒子上限 20 万、採取メモリ上限 12000 MiB、処理上限 20 分以内で終了した。
- `../../results/reference_release/whitewater/本計算01/白波_2から24フレーム.abc` は 11,797,620 バイト。第 2・3・12・24 フレームの再読込は、空の第 2 フレームも含めて頂点数と座標が一致した。

[計測結果](結果.json)、[保存した HIP と実粒子の照合](ソース照合.json)。Unity・HMD は未検証。

## Blender での表示

[主流体と重ねた色面の斜視動画](../previews/自由発展01_白波と色面_斜視.mp4) ／ [同じ時刻の側面動画](../previews/自由発展01_白波と色面_側面.mp4)。各 24 フレーム・24 fps・1 秒で、公式 Blender MCP から実 Alembic を読み込んだ。

主流体の高い部分を白く塗る処理ではなく、上記の独立メッシュを重ねている。実際の画面は広い塊状の覆いとなり、分岐する白い爪や飛沫の形には達していない。

Blender では Alembic の先頭の空形状が最初の非空形状へ丸められたため、第 1・2 フレームは白波を明示的に非表示にした。実際に生まれた第 3 フレームから表示する。[表示開始の実測](../白波表示の開始.json)、[全フレームの動画復号確認](../動画確認.json)、[主流体を含む画面の判定](../../../Blender/great_wave/docs/milestones/2026-09-24_reference_release.md) を参照。

## 再現

先に主 FLIP の体積場を生成する。Windows の有効な Houdini Indie `hython` を使い、このディレクトリから実行する。メモリ採取は Windows API を使用する。

```powershell
hython "白波を計算.py" --last-frame 12 --output-dir "../../results/reference_release/whitewater/再現_短区間"
hython "白波を計算.py" --last-frame 24 --output-dir "../../results/reference_release/whitewater/再現_24"
hython "メッシュを書き出す.py" --cache-dir "../../results/reference_release/whitewater/再現_24"
```

短区間の結果を先に確認する。計算結果は同名で上書きしない。HIP は再生成するため、手作業で編集する場合は別名で保存する。`--verify-only` は既存の Alembic を書き直さず再読込だけ検証する。キャッシュは Git 対象外、設定と制作元・記録は Git 対象。
