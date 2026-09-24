# 旧 FLIP シーンの読み取り調査

対象は利用者の既存 `wave_flip_2_bak4.hiplc`。元ファイルを保存せず、手動更新モードでユーザー定義ノード 88 個の接続と Python/VEX を読み取った。粒子間隔 0.022 m の旧シミュレーションは実行していない。

読み取り前後の SHA-256 は一致する。

`0a4132ed2d0586c80924cc1eab0ec22ffbe441eeff86690762e569201821b87a`

## 確認した接続

- FLIP は `fliptank_initial/OUT_INITIAL_PARTICLES` と `OUT_INITIAL_SURFACE` を初期状態に使う。Narrow Band、粒子間隔 0.022 m、格子倍率 2。
- `AutoDopNetwork/popvop1` は FLIP Solver の粒子速度入力に接続されている。
- この POP VOP は `op:../../grid_object1/out_sdf` をサンプルする。体積勾配を負にし、100 倍したベクトルを **force** 出力へ書く。位置の直接上書きではないが、固定した 69 フレームの形状から作った外力が毎ステップ働く構成である。
- `out_sdf` の上流は Ocean Spectrum → Ocean Evaluate → Point VOP による巻き形状 → 69 フレーム固定の Time Shift → Extrude Volume → VDB From Polygons。
- OBJ を読み込む別枝には `model_follow_original_motion` がある。旧アニメーション形状と基準形状の差分を参照模型へ 0.72 倍で加え、距離減衰と最大変位制限をかける。その出力を VDB 化する枝もある。
- しかし現在の POP VOP はこの新しい `OUT_dynamic_model_vdb` を参照していない。名前だけを根拠に「新しい模型が既に FLIP を誘導している」とは判断できない。
- 別の Python SOP は入力の 20 点ごとに 1 点を複製し、pscale=0.38 を設定する。`vdb_from_sampled_existing_points` に渡すが、これも現在の POP VOP の参照先ではない。

## 継続制作に利用できる部分

旧シーンには形状由来の外力で FLIP を誘導する既存の経路がある。造形と流体を結び付ける候補として調査価値がある。ただし強度 100 の力を持続適用しているため、自然の自由砕波と同一視しない。次の比較では、誘導力を短時間だけ使う場合と使わない場合の仕事量・圧力・速度・水量変化を区別する必要がある。

既存 `1.abc` とこのバックアップの生成関係は未確認。見た目やファイル日付だけでは同じ生成元と断定できない。

## 制限

セッション原コードは、制作者の個人フォルダにある `restore_points_vdb_only.py` を絶対パスで実行する。外部ファイル依存があり、このままでは他の環境へ移動できない。読み込み時にこの埋め込みコードが `Missing /obj/grid_object1` を報告した。読み込み完了後にはそのノードが存在し、接続を取得できた。これは旧シーンの安全な再計算を保証するものではない。

全接続と原コードのローカル記録は `../results/wave_tank/旧HIP_接続とコード.json`。履歴の原コードは書き換えず、Git への提出資料は本書の日本語要約とする。
