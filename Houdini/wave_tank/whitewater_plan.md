# FLIP 波槽に付加する白波の最小計画

## 確認範囲

2026年9月24日に Houdini 22 の公式資料と、Steam 版インストール内の `houdini/config/Dialogs/SOP/whitewatersource-3.0`、`whitewatersolver`、`whitewaterpostprocess` を読み取り確認した。以下は実装案であり、この調査では `hython` を起動せず、白波の計算・出力・実時間再生は実施していない。

液体表面を白く着色した結果と、独立した白波粒子の計算結果を区別する。まず既存の FLIP キャッシュを読み、短い区間だけ白波を別計算する。

## 接続と入力の条件

対象は **Whitewater Source 3.0 → Whitewater Solver SOP**。古い放出点主体の手順と混在させない。Source の第4出力は放出の可視化用で、時間発展を解いた白波の出力ではない。[Whitewater Source 3.0](https://www.sidefx.com/docs/houdini/nodes/sop/whitewatersource.html)

| 段階 | 入力・出力 |
| --- | --- |
| 液体キャッシュ | 同じフレームの液体 SDF `surface` と速度場 `vel`。速度はベクトル VDB、または `vel.x`・`vel.y`・`vel.z` の組。ポリゴン表面だけでは不足する |
| Source の入力1 | 上記の液体場。最初は曲率と速度・深度の制限で放出を調整する |
| Source の入力2・3 | 元 FLIP と一致する計算領域、衝突形状の表面・速度場。SOP FLIP なら領域・衝突出力を利用する。DOP 由来なら対応する場を別途取り出す |
| Source の出力1 | `Output Fluid Fields` を有効にし、`emit`・`surface`・`vel` を保持する |
| Solver の入力1・2・3 | Source の出力1・2・3を同順で接続する |
| Solver の出力1 | 時間発展した独立の白波粒子。これを先にキャッシュする |

`Splash` 放出には入力1の FLIP 粒子も必要となる。`Pressure` 放出には圧力場と領域・衝突が必要であり、初回は無効にする。後で入力を確認して一種類ずつ追加する。計算開始フレーム、単位、座標系、時間刻みは元 FLIP と合わせる。[Source の放出条件](https://www.sidefx.com/docs/houdini/nodes/sop/whitewatersource.html)、[Solver の入力仕様](https://www.sidefx.com/docs/houdini/nodes/sop/whitewatersolver.html)

## 最小の実施順と合格条件

1. **液体場を確認する。** 砕波前・巻込み・着水後の候補フレームで `surface` のゼロ面、有限な速度場、粒子との位置関係を重ねる。ポリゴンと実際の場が一致しなければ白波へ進まない。
2. **放出だけを確認する。** `emit` を可視化し、壁や水底を含む全域が一様に発光していないか調べる。追加の手動放出は使わず、閾値と深度範囲を記録する。放出の少なさを白色の材質で隠さない。
3. **短区間を順番に解く。** 提案する初回範囲は砕波前後の30～60フレーム。開始点で白波を空にしてよい短区間として扱い、長い履歴を再現したとは主張しない。`Add State Attributes` を有効にし、設定した乱数シードと寿命を記録する。白波の密度用 `Voxel Size` は `Whitewater Scale` の2倍以上を初期条件とする。[Solver SOP](https://www.sidefx.com/docs/houdini/nodes/sop/whitewatersolver.html)
4. **粒子を保存して再読込みする。** `Houdini/results/wave_tank/whitewater/particles/ww.$F4.bgeo.sc` を候補とする。`P`・`v`・`id`・`age` の有無と型を実データで調べ、有限値、点数、出生・消失、同じ `id` の移動を記録する。点番号を粒子の同一性として使わない。`pscale`・`life`・密度属性は存在を確かめてから保持し、未確認の既定属性を仮定しない。`bubble`・`foam`・`spray` は0～1の状態の重みで、排他的な三つの部品番号ではない。[状態属性](https://www.sidefx.com/docs/houdini/nodes/sop/whitewatersolver.html)
5. **表示用の変換を別に作る。** 粒子キャッシュ → Whitewater Post-Process の `Mesh` → 独立メッシュの短い Alembic を試す。元粒子も残し、主水面とは別オブジェクトにする。`pscale`、密度、平滑化は表示用の調整として記録する。Post-Process のメッシュは体積表示にも使われる表現であり、北斎の爪形状が自動的に生成されるものではない。[Whitewater Post-Process](https://www.sidefx.com/docs/houdini/nodes/sop/whitewaterpostprocess.html)

`emit` を単独でキャッシュする場合は、Solver の直前で同時刻の `surface`・`vel` を再び合わせる。初回は分離せず、接続を確認しやすくする。全ての生成キャッシュは `Houdini/results/` 以下に置き、計画・設定・検証記録と分ける。

## 計算から得る運動と造形の境界

- **液体計算に基づく部分：** 液体場に基づく放出位置と移流、重力、浮力、衝突などを白波ソルバが時間発展させる。放出閾値や平均寿命は調整可能なモデルであり、気液二相の空気巻込み量を実測どおり再現した証明にはならない。[Whitewater Solver DOP](https://www.sidefx.com/docs/houdini/nodes/dop/whitewatersolver.html)
- **美術的に残る部分：** 北斎特有の太い根・分岐・鉤状の先端、白の面積、輪郭、藍との境界。必要なら計算粒子の位置・速度・寿命を使って表示形状を作るが、人工的な形状制御を施した範囲を記録する。動きの出典と、見せるための造形を混同しない。

## Blender・Unity へ渡す際の制約

- **Blender：** Alembic の Mesh Sequence Cache は頂点数や面接続が変わるアニメーションを扱える。生成・消滅する白波を既存の固定頂点シェイプキーへそのまま移す設計にはしない。`.blend` だけで完結すると仮定せず、外部 `.abc` も配布対象として管理する。まず少数フレームで時刻、向き、大きさ、材質を確認する。[Blender 公式マニュアル](https://docs.blender.org/manual/en/latest/modeling/modifiers/modify/mesh_sequence_cache.html)
- **Unity：** 当面は独立した白波メッシュの Alembic を PC 上で比較する案とする。Alembic 2.4 の対応ビルド環境はデスクトップであり、Quest 単体の Android 再生へ適用済みとは扱わない。キャッシュ読込みの成功と、HMD の時間予算内で描画できることは別々に測る。[Unity Alembic 2.4](https://docs.unity3d.com/Packages/com.unity.formats.alembic@2.4/manual/index.html)
- **共通の未検証事項：** 粒子属性の転送、可変トポロジーの時間補間、泡のちらつき、ファイル容量、メモリー、描画負荷。材質ネットワークの自動互換は前提にしない。最初の合格対象は「短い独立白波キャッシュを再読込みし、主波と同じ時刻で動かせること」に限定する。
