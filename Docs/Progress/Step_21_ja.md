# 21：小振幅波の条件を固定する

**単位・水深・波高・周期・進行方向と第22〜25号の測定契約を固定した。** 理論式の数値検算は合格。Houdini/Unityで波を計算・表示した番号ではなく、実伝播動画と波高計は22へ残す。HMD・主役砕波の合格にもならない。

- [条件・境界・ゲージ・測定契約](../../Houdini/WaveBaseline21/README_ja.md)
- [解析式のみの図](../../Houdini/WaveBaseline21/Evidence/21_analytic_reference.png)／[理論CSV](../../Houdini/WaveBaseline21/Evidence/21_theory_gauges.csv)
- [数値検算](../../Houdini/WaveBaseline21/Evidence/21_numeric_checks.json)／[出典SHA](../../Houdini/WaveBaseline21/Evidence/21_provenance.json)

| 固定条件 | 値 |
| --- | --- |
| 単位・座標 | m/s/kg、Y上、静水面0m、底−0.6m、+X単方向 |
| 波高・振幅・周期 | H=0.06m、a=0.03m、T=1.5s |
| 水深・重力・密度 | h=0.6m、g=9.81m/s²、ρ=1000kg/m³（淡水相当数値基準） |
| 有限水深の理論結果 | λ=2.990395m、c=1.993597m/s、cg=1.403313m/s |
| 本槽候補 | 長さ6λ=17.942371m、幅0.6m。入口0〜λ、出口減衰5λ〜6λ |
| 本槽の3ゲージ | X=(2,2.2,2.55)λ=(5.980790,6.578869,7.625508)m、Z=0 |

θ=kx−ωtの線形重力波を使い、深水/浅水近似へ置き換えない。kh=1.260673、ka=0.063034。式と根拠は[MITの一次資料、p5〜8](https://ocw.mit.edu/courses/2-20-marine-hydrodynamics-13-021-spring-2005/5d48a5937971d973fd8ca90c051a83f8_lecture20.pdf)に基づく。9つの検算は色散、底v=0、平均面v=∂η/∂t、非圧縮、T/λ周期性、+X進行、位相遅れ、合成入射波の反射分離。実流体検査とは別。

22では短い2λ槽・Δp=.04mの9標本から始め、時計・水保持・境界の強制mask・計算時間/メモリを確かめる。Δp=.04はHに対し1.5間隔しかなく、精度合格用ではない。本槽をΔp=.02で直ちに計算しない。圧力格子、solver SDF、表示meshのvoxel、実dt/採録密度を別に記録する。

造波方式は未選択で、独自Boundary Flowを入口だけへ適用できるか、または移動pistonと明示colliderを使うかを22で試す。目標波高とpiston strokeを同一視しない。初期条件は静水・速度0。内部のゲージを理論式で駆動した結果を「伝播」と呼ばない。

9〜16.5秒の5周期窓は候補のみ。入口がλまで及ぶ場合の長波反射目安は約7.95秒で、この窓を無反射と仮定できない。実定常性・強制帯不混入・反射診断が通らなければ窓を不採用とし、別caseで位置/槽/吸収を改める。23のT/λ/cは設計の5%目標、24で解像度/刻み依存、25で静水・開領域収支・反射を確認する。いずれも今回未実行。

解析CSVは0〜18秒・60Hz・終端込み1081行。定常解であり、実FLIPの立ち上がり/到達を表していない。図にも「解析式のみ・流体シミュレーション未実施」と明示した。実Unity画像を装った媒体は作らず、過去の01〜20ソース・証拠を保持した。

再現は専用Python環境から `Houdini/WaveBaseline21/Source/calculate_reference.py` を実行する。[依存固定表](../../Houdini/WaveBaseline21/Source/requirements.lock.txt)と日本語フォントのhashを保存。Houdini UI、既存HIP、global FPS、Unityシーンの変更はない。レビュー後、22の実pilotへ進む。
