# 大波を実現する実装の手法の調べ（Q47・Q51）

> **置き場所（指導教員のお尋ね、Q51 の 2）：** GitHub の imagirelab/GreatWave_2026 の `Docs/Research/` にある。この文書（`BigWave_Implementation_Survey_ja.md`）が三つの調べのまとめで、前の二つの調べ（[毎フレームの計算の例 41 件](RealtimeBigWave_Survey_ja.md)、[Houdini で大波を作る方法 53 項目](HoudiniBigWave_Survey_ja.md)）も同じ所にある。例ごとの細かい記録は本機だけにあり、指導教員が見られるのはこの文書の表（§3.2・§3.3）までである（§8）。

## 0. 一枚で

| 流れ | 内容 |
| --- | --- |
| 方針 | Houdini に限らず、大波を出している実装の手法（式と算法・公開のコード・道具・作品）を、例ごとに前もって決めた 5 点で調べた（今回 63 項目）。前の二つの調べと合わせて一つにまとめた |
| 目標 | 10/29 までに実装できる確立した手法を選び、順位をつけて示す（決めるのは指導教員） |
| 結果と分かったこと | (1) 重力と造波だけで前へ巻いて崩れる確立した実装は、海岸工学のオフラインの数値水槽（DualSPHysics など）で、今の計算（FLIP42）も同じ型だった。(2) 巻くまでなら境界要素法が、FLIP42 の元と同じ水路の実験の水面の高さと流速を再現している（唇の形は実験と比べていない）。(3) 毎フレームの計算で重力から前へ巻く唇を出した公開の例は見つからなかった（中身を見ていない動画と講座が 1 つずつある） |
| 現在地 | 読むだけの調べを終えた。動画・図は見ていない。実装と計算はしていない（Q49） |
| 次（候補） | ① 2D の境界要素法を論文から自作し、FLIP42 と同じ群を巻くまで解く（1〜3 週）。早い崩れと薄い唇の確かめで、見せる物は唇が触れるまでの同じ断面。② DualSPHysics（公開の GPU の粒子法）で同じ群を崩れまで解く（5〜8 日と計算。ダウンロードの許可が要る）。③ 毎フレームの計算が要る場合だけ、Unity の GPU で同じ断面の FLIP を解く（2〜4 週）。どれも断面なので、船から見上げる角（最大 17.5°）と横にどこも同じ形は変わらない。① → ② は日数の下の値なら 10/29 に入るが、上の値では ① も入らないので、10/21 に関門を置く（§5.0） |
| 伺うこと | 1. ①〜③ のどれから進めるか（進行役は ① → ②）。2. [10/12 の報告](../Progress/Supervisor_Report_20261012_ja.md) §6 の問い 1・2（毎フレームの再生を「リアルタイム」に入れるか、初めの条件と入口の決め方を物理の計算と認めるか）。10/13 18:00 までに Discord で、なければ 10/14 の共通ゼミで伺う |

## 1. 方針

### 1.0 この文書について

- 日付：2026-10-11（本機の日付）。書いた者：進行役（Claude）。利用者を通して指導教員に見ていただくための報告。
- 何のためか：指導教員の指示（Q47、10/9）「大波を実現しているリアルタイムな流体シミュレーションを調査してもらいましょう。良いものがあったら、それを実装してもらうのが手法も確定しているので進めやすいと思います」と、その後の答え（Q51、10/11）「もっと調べてもらってください。Houdiniにこだわりすぎる、実装手法を調べてもらったください」「調べてもらった結果を置いてある場所を教えてください」（[制作手順の Q47〜Q51](../Workflow/Production_Workflow_ja.md)）。
- 状態：読むだけの調べ。ダウンロード・リポジトリの取得・インストール・流体の計算・git はしていない。**動画・図は一本も見ていない**。大波の見え方は、本文・図の説明文・コードの文から読んだ。新しい計算と実装は、指導教員のお返事まで始めない（Q49）。
- 印：【文献】出典にあること。【記録】このリポジトリの記録の値。【計算】式の値。【考え】【推定】進行役の推論と見積もり（確かめていない）。「Q41 との関係」は進行役の読みで、合うかどうかは指導教員が判断する（Q44 の扱い 7）。
- 短い名前：FLIP42＝今の 2D の断面の計算（水槽の実験 Rapp & Melville 1990 の巻き波の群を 70 倍にして、重力だけの FLIP で解いたもの。[報告](../Progress/FLIP_Plunging_ja.md)）。R3・R4＝その粒子 0.25 m・0.177 m の計算。RT48＝その断面を Unity で毎フレーム再生する試作（[報告](../Progress/RT_Playback_ja.md)）。
- 作業メモ（本機だけ、Git に入れていない）：`Unity/Build/SURVEY51/` の 6 つの記録と、重なりをまとめた 64 項目の一覧 `items.json`。記録ごとの読み直しの程度は §9。

### 1.1 指示の読み

- Q47（10/9）の「リアルタイム」を、進行役は初め「毎フレームその場で水を計算するもの」と読んで 41 件を調べた。Q50（10/11）で利用者は「Houdini で大波を実現する方法」と読み直し、53 項目を調べた。Q51（10/11）で指導教員は Houdini に絞った読みを狭すぎるとした。
- そこで今回の的は、Houdini に限らない、大波を実現している**実装の手法**（解いている式と算法、公開のコード、エンジンや道具、作品の例）とした。Q47 の「良いものがあったら実装」に合わせ、実装できるだけの手順・コードが公開されているかを重く見た（[制作手順の Q51](../Workflow/Production_Workflow_ja.md) の扱い 1）。
- 「良いもの」の読み【考え】：(a) 大波（立ち上がり・険しい前の面・前へ巻く唇・崩れ）のどこまでを出しているかが証拠で分かる、(b) 手法が確定している（式が公開され、実験と比べてある）、(c) 私たちが実装するか借りて使える。「リアルタイム」かは、毎フレームの計算・オフラインの計算の再生・手続きの形の三つを分けて書いた。
- 力の範囲（Q41、10/8 の指導教員の答え）：加えてよい力は重力と、風のように波を自然に起こす力だけ。初めの条件と境界の条件を選ぶことは、選んだと書けばよい（Q44）。

### 1.2 調べる前に決めた 5 点

1. 見せる大波：立ち上がり、険しい前の面、前へ巻く唇とその厚み、空気を囲むか、崩れ、しぶき・白い水、大きさ。証拠（図・静止画・時刻・公式の説明）。見られなかったときはそう書く。
2. 方法：式と算法（FLIP・PIC・APIC、MPM、SPH の種類、PBF、格子ボルツマン法、背の高いセル・狭い帯、浅水・ブシネスク、ポテンシャル流（HOS・境界要素法）、波の束、学習した計算、組み合わせ）、波の起こし方（造波板、入口、理論の初めの状態、集める、海底）、使う力の全部、手で決めるもの。
3. 速さ：毎フレームか、fps、粒子・格子の数、領域、機械。RTX 3080 の VR で毎フレーム動くか、前もって計算して再生するか。
4. 実装のしやすさ：公開のコード（場所・言語・GPU の API・ライセンス・更新）か、実装できるだけの手順。Unity（コンピュートシェーダー）で作る手間か、外で計算して再生する手間。要るダウンロード・購入（大きさ・ライセンス）。
5. 合う所：作品に何をくれるか、危うさ、Q41 との関係。

### 1.3 調べた所

| 範囲 | 読んだもの | 項目 | 記録（`Unity/Build/SURVEY51/`） |
| --- | --- | --- | --- |
| 算法 | 流体力学・海岸工学の論文（JFM、Coastal Engineering、IJNMF、総説の章）、グラフィックスの論文（SIGGRAPH・TOG・Eurographics）。2000〜2026 年を中心に、元になった 1976・1988 年の論文 | 14 | `algorithms_ja.md` |
| 公開のコード | GitHub・GitLab の README とソースの一部、文書、ライセンスの本文、最後の更新の日 | 15 | `opensource_ja.md` |
| エンジンと製品 | Unreal・Unity の製品、Chaos Phoenix、RealFlow、Maya Bifrost、X-Particles・NeXus、LiquiGen、Blender、NVIDIA の部品の頁・文書・記事 | 12（ほか 3 は上と重なる） | `engines_ja.md` |
| 波の起こし方 | 数値の水槽、集まる群、斜面とリーフ、サーフィンのプール、映画の作り方 | 9（ほか 4 は上と重なる） | `breaking_ja.md` |
| 作品 | 展示・VR・ゲーム・映画の作り手の文・講演・記事 | 13 | `works_ja.md`・`works_verify_ja.md` |
| 前の調べ | 毎フレームの計算の例 41 件（`Unity/Build/SURVEY47/`）、Houdini の方法 53 項目（`Unity/Build/SURVEY50/`） | — | 各報告 |

探せなかった範囲と、一次の出典で確かめられなかったものは §9 に書いた。

### 1.4 この作品の条件【記録】

- 機械：CPU i7-12700K、GPU RTX 3080 10 GB、メモリー 64 GB。Houdini Indie 22。Unity 6000.4 の Built-in、OpenXR、PSVR2（90 Hz なら 1 フレーム 11.1 ms）。期限 10/29。
- FLIP42：粒子 0.25 m（R3）と 0.177 m（R4）で、前の面が鉛直を越え、唇が前の面に付いて空気を囲んだ。唇の厚みは約 1 m（波高の約 1 割）。走らせる前に決めた判定のうち、入口の波・焦点の場所と時刻・計算の中の減り・着水の時刻と場所の 4 つは外れ、出典の表の値より手前・早く崩れた（R4 で周期の 0.33 倍・波長の 0.38 倍）。原因は分かっていない（[FLIP_Plunging_ja.md](../Progress/FLIP_Plunging_ja.md) §0.1）。
- RT48：その断面を形を変えずに横へ並べ、Unity で毎フレーム再生した。頂が横にどこも同じ長い堤になり、船から見上げる角は最大 17.5°（[10/12 の報告](../Progress/Supervisor_Report_20261012_ja.md) §4・§5）。

## 2. 目標

例ごとの証拠で、次の三つに答える。

1. 大波（立ち上がり・険しい前の面・前へ巻く唇・崩れ）を、どの実装の手法が、どこまで出しているか。その手法は計算の途中にどんな力を使い、何を手で決めているか。
2. そのうち毎フレームの計算で動くものはどれか。
3. 私たちが 10/29 までに実装できるものはどれか、どう実装するか。2〜3 の候補を順位をつけて、作品での見え方・手順・この機械での時間・要るダウンロードと購入とライセンス・危うさ・Q41 との関係・確かめ方とともに示す（決めるのは指導教員）。

## 3. 結果

### 3.1 数

| 調べ | 項目 | 一次の出典で読み直した項目 |
| --- | --- | --- |
| 毎フレームの計算の例（10/10、[報告](RealtimeBigWave_Survey_ja.md)） | 41 | 論文 15 系統とゲーム・製品 14 |
| Houdini の方法（10/11、[報告](HoudiniBigWave_Survey_ja.md)） | 53 | 26（見直しの 4 を含む） |
| Houdini の外（今回） | 63＋本作 1 | 49（確かめの段 36、作品の確かめ 13） |

### 3.2 手法の系ごとの一覧（5 点の短い形）

「見た」ものはない（動画・図は見ていない）。(5) は進行役の読み。前の調べで扱った物は、その報告へのリンクで済ませた。例ごとの記録（`Unity/Build/SURVEY51/`）は本機だけにあるので、出典は表の中のリンクで示した。

| 系と手法 | (1) 見せる大波（証拠は文） | (2) 方法・起こし方・力 | (3) 速さ | (4) 実装・入手 | (5) この作品に |
| --- | --- | --- | --- | --- | --- |
| **ポテンシャル流（渦のない流れを水面の上だけで解く）** | | | | | |
| 2D の境界要素法（混合オイラー・ラグランジュ、MEL）：[Longuet-Higgins & Cokelet 1976](https://data-ww3.ifremer.fr/BIB/Longuet-Higgins_Cokelet_PRSLA1976.pdf) → [Dommermuth ら 1988](https://airsea.ucsd.edu/wp-content/uploads/sites/10/2019/06/1988_DOMMERMUTH_YUE_LIN_et_al-JOURNAL_OF_FLUID_MECHANICS_vol_189.pdf) | MIT の水路（水深 0.6 m）の深い水の巻き波 1 つ。32 成分（0.56〜1.2 Hz）の群が造波板から約 7.25 m・12.9 s で巻く。実験と比べたのは、波高計の水面の高さの時系列（著者は巻く所の近くまでほとんど見分けられないと書く。比べた所では波はまだ多価でない）、2 か所の流速、巻く場所と時刻（計算は約 9 cm 手前・約 0.06 s 早い。FLIP42 と同じ向きで、差は小さい）。唇の形と厚みは実験で測っていない。崩れ・しぶきはない | ラプラス方程式、水面は圧力 0、表面張力なし、重力だけ。入力は測った造波板の動き（付録 B に係数の表）。鋸の歯の揺れには並べ直しと平滑化（数値の工夫） | 1988 年は Cray 1 で 30 時間。今の CPU 1 コアで 1 本 20 秒〜7 分【推定】。巻く直前は 1/90 s に約 13 段要り、1 段ごとに約 550 未知数の密な行列を組んで解く（1988 年は時間の 8 割が組み立て）ので、毎フレームには入らない見込み。保存して再生する【推定】 | 1988 年のコードは非公開。式・手順・確かめの表は論文にある。自作 1〜3 週【推定】。MATLAB の [Surftank](https://github.com/KelvinHamster/surftank)（GPL-3.0）は巻きの記述がない | 重力と造波板だけ。FLIP42 の早い崩れと唇の厚みを、格子のない確立した方法で確かめる相手。実験の幅があるのは巻く場所と時刻だけで、唇の厚みは粘りのない理論の答えとの比べになる。崩れは FLIP へ渡す（§5.1） |
| 2D の境界要素法の別の書き方：Dold & Peregrine 1986・Dold 1992（コーシーの積分の高次の方法）、渦の層の方法（Baker・Meiron・Orszag 1982）【確かめていない：記憶による】 | 周期の箱の険しい波が巻くまで（記憶による） | ポテンシャル流、重力だけ | 軽い見込み | 論文の式。コードの公開は見ていない | 候補 1 を自作する時の手本と、周期の箱の試し（§5.4）の相手。今回は中身を読んでいない |
| 3D の高次の境界要素法の数値水槽：[Grilli ら 2001](https://digitalcommons.uri.edu/oce_facpubs/188)、Guyenne & Grilli 2006、Fochesato ら 2007（[総説の章](https://bpb-us-w2.wpmucdn.com/sites.udel.edu/dist/0/6223/files/2020/06/1_bc_ch3-SG.pdf)） | 斜面の尾根の上の孤立波（尾根の横の変化が急だと細く強い噴流）。向きを集める造波（30 成分、周期 7 s、水深 20 m、向き ±45°）で、頂 7.2 m・波高 10.8 m の波が、曲がった前線の真ん中の細い所で巻き始める。噴流が触れる直前まで | 16 節点の 3 次の要素、GMRES と高速多重極。蛇行する造波板か初めの孤立波。重力だけ | 1 万節点で 1 段 2 分、計 700 分（2 CPU） | コードの公開なし。自作は数週〜数か月 | 作品と同じ桁の波が、向きの集まりだけで細く巻いた計算。3D の窓の物理の根拠と比べの相手。道具としては使えない |
| 等角写像の 2D（[Dyachenko ら 2021](https://math.unm.edu/~plushnik/publications/DyachenkoDyachenkoLushnikovZakharvProcRoySocA2021shortbranchcut.pdf)） | 噴流と倒れる波の理論の解。実験との比べはない | 無限の深さ、重力を落とした近似が主 | 軽い見込み | 造波板・有限の深さなし | 記録だけ |
| **結び付け（遠くを速い式で運び、崩れる所だけ流体の式で解く）** | | | | | |
| ポテンシャル流 → Navier–Stokes：境界要素法 → VOF（[Biausser ら 2003](https://digitalcommons.uri.edu/oce_facpubs/180) ほか）、孤立波 → LBM–VOF（[Janßen ら 2013](https://digitalcommons.uri.edu/oce_facpubs/139/)）、OceanWave3D → DualSPHysics（[Kanehira ら 2026](https://arxiv.org/abs/2512.19924v1)）、HOS → CFD（[Grid2Grid](https://arxiv.org/pdf/1801.00026)） | 斜面の崩れと崩れた後、3D の斜面の砕波、向きを集めた軸対称の噴流（高さ 6 m まで、実験と Longuet-Higgins の式に合う） | 巻く少し前の状態を初めの状態に渡すか、境界の帯で一方向に渡す。重力（NS 側は粘りと乱れの模型も） | オフライン。Kanehira：1 本 6〜255 時間、全部を SPH にするより約 9 割減 | Grid2Grid・HOS-NWT は GPLv3。本作は HOS-Ocean を Q43 でダウンロード済み。2D の受け渡しは 2〜4 日、HOS → FLIP は 1〜2 週【推定】 | 巻くまでを確立した方法で、崩れからを FLIP で。FLIP の短い成分が遅く弱くなる運ぶ誤差と、計算の時間を減らす道 |
| 非線形の 2D の波と 3D の FLIP の両向き：[Wang ら 2026](https://arxiv.org/abs/2608.25203)、[Schreck & Wojtan 2022](https://visualcomputing.ist.ac.at/publications/2022/2dto3d_fundamental_sources/) | 船の航跡・水上機・潜水艦。崩れる波の場面はない（著者は 2D の波の模型は崩れる波を表せないと書く） | Zakharov の式を HOS で解く 2D と、狭い帯の FLIP（CUDA）を両向きに結ぶ | RTX 4090 で 3D の 1 小段 85 ms。オフライン | Wang はコードの告知なし。Schreck & Wojtan は MIT（Houdini 18.5 の HDK） | 3D の窓を軽くする新しい形。巻く波は 3D の箱の中で出す必要があり、今の段では参考 |
| 水面だけの境界要素法と FLIP（[Da ら 2016](http://www.cs.columbia.edu/cg/surfaceliquids/)、[Huang ら 2021](https://arxiv.org/abs/2108.05481)） | 水の鐘・王冠・船の航跡。著者は伸びていく巻き波は勧める使い方でないと書く | 三角形の網の上の境界積分、船のまわりは FLIP | 1 コマ 249 s（24 コア 2 つと V100） | Da のコードは FreeBSD | 巻き波の道具ではない |
| **粒子と格子の混成（FLIP・PIC・APIC・MPM）** | | | | | |
| Houdini の FLIP（[前の調べ](HoudiniBigWave_Survey_ja.md)） | 本作の FLIP42：重力だけで前へ巻き、空気を囲んだ。唇 約 1 m。出典の表より手前・早く崩れた【記録】 | 入口の帯で 32 成分の流速へ寄せ、帯の外は重力だけ | CPU。粒子 0.25 m で 1 本 5〜7 時間の見込み（139.6 s 分までは 2.8 時間）、0.177 m で 15 時間【記録】 | 本機にある | 今の道。制作の例の多くは途中に誘導の力を入れる（前の調べ） |
| Blender の [Mantaflow](https://github.com/tum-pbs/mantaflow)・[FLIP Fluids](https://github.com/rlguy/Blender-FLIP-Fluids) | 公式の巻き波の例はない。FLIP Fluids の浜の例は水の下の物を上下させて波を起こす | FLIP・APIC、狭い帯の FLIP、流入、動く障害物 | CPU、オフライン | Mantaflow は Apache-2.0 で本機の Blender 5.2.2 にある。FLIP Fluids の計算部は MIT | 別のコードの FLIP で同じ群を解き、巻きが Houdini の設定によらないかを見る確かめに使える（ダウンロードなし） |
| GPU の疎な格子の FLIP（[Wu ら 2018](https://people.csail.mit.edu/kuiwu/gvdb_sim.html)）、狭い帯の FLIP（[Ferstl ら 2016](https://www.cs.cit.tum.de/en/cg/research/publications/2016/narrow-band-flip-for-liquid-simulations/)） | 町の場面・ダム崩れ。海の巻き波なし | 疎な格子と行列なしの CG、水面の近くの帯だけに粒子 | 2,900 万粒子で 1 コマ 1.8 s（GP100）。帯は粒子を最大 22 分の 1 | [GVDB](https://github.com/NVIDIA/gvdb-voxels) は Apache 2.0・CUDA。帯は Houdini・Mantaflow にある | 3D の窓を軽くする部品。粒子 0.5 m・帯 4 m は前の面を変えて巻かなかった記録がある |
| 毎フレームの GPU の FLIP の公開のコード：[abecombe FLIP-Fluid-for-Unity](https://github.com/abecombe/FLIP-Fluid-for-Unity)、[blub](https://github.com/Wumpf/blub)、[jeantimex/fluid](https://github.com/jeantimex/fluid)、[Vulkan の 2D FLIP](https://sean-im.itch.io/interactive-fluid/devlog/906257/first-devlog-gpu-fluid-simulation)、手本の [Jet](https://github.com/doyubkim/fluid-engine-dev) | 波の例はない（箱の水） | PIC/FLIP/APIC。abecombe は圧力を Jacobi 法 15 回、blub は前処理つき共役勾配法、Jet は多重格子つき | Vulkan の 2D：26 万粒子で RTX 3080 で 1 フレーム 5 ms 未満（描画を含む）。粒子の数の比で直すと、FLIP42 の断面の全部（約 140 万粒子）は 1 段 27 ms 以下（上限で、測るまで分からない）、焦点のまわり 150〜300 m の窓なら 1 段 3〜7 ms 以下【推定】 | abecombe は Apache-2.0・Unity 2021.3 の HLSL で、描画は HDRP と VFX Graph（本作は 6000.4 の Built-in）。blub・jeantimex・Jet は MIT。blub は 2022-12 から更新がない | 毎フレームの断面の FLIP の土台（§5.3）。Jacobi 15 回では深い水に圧力が伝わらず、解き方の取り替えが要る【推定】 |
| MPM（[MLS-MPM](https://yuanming.taichi.graphics/publication/2018-mlsmpm/)、[Claymore](https://github.com/penn-graphics-research/claymore)）と [Zibra Liquid](https://www.zibra.ai/liquid-smoke-fire) | 海の巻き波の例なし | 弱い圧縮の水 | Claymore は 4 GPU で 1 億粒子近くを 1 コマ 4 分未満 | MLS-MPM・Claymore は MIT。Zibra は有料、2024-05 から版なし | 重力の波の分散と巻きを示した例がない |
| **粒子（SPH・PBF）**。MPS で巻き波を実験と比べた研究は、中身を読めていない（§9） | | | | | |
| [DualSPHysics](https://github.com/DualSPHysics/DualSPHysics) | 平らな浜とリーフで崩れ波と巻き波（リーフの斜面で激しく巻く）。巻き波が出る計算で、波の形の非対称・崩れの減衰・平均の水位・戻り流れを水路の実験と比べた（[Lowe ら 2019](https://arxiv.org/abs/2002.00827)）。巻く噴流の形そのものは比べていない。集める波の例 19_FocusedWaves | 弱圧縮 SPH。造波板（ピストン・フラップ、1・2 次、不規則、孤立波、NewWave の集める波）、吸う帯、OceanWave3D と連成。重力と、数値の安定のための人工の粘り・密度の拡散・粒子のずらし | GPU、オフライン。RTX 3080 の例で 168 万粒子・物理の 135 s に 59 時間【文献】。断面の時間は粒子の数で決まり、見積もりが割れる（§5.2） | LGPL-2.1、v5.4、Windows の組み立て済みあり。造波の部品と面の道具はソースなし | Houdini の外の確立した数値水槽。同じ群を崩れまで解く独立の相手（§5.2） |
| [GPUSPH](https://github.com/GPUSPH/gpusph)。ほかに [AQUAgpusph](https://github.com/sanguinariojoe/aquagpusph)、[SPHinXsys](https://github.com/Xiangyu-Hu/SPHinXsys)（この二つは頁の表だけ読み、表の数に入れていない） | GPUSPH：造波板と浜の水槽の例（WaveTank.cu）。AQUAgpusph・SPHinXsys：頁に造波・巻き波の例の記述なし | 弱圧縮 SPH、フラップ、重力 | 数値なし | GPUSPH は GPLv3・CUDA・Linux の手順だけ。AQUAgpusph は GPL-3.0・OpenCL。SPHinXsys は Apache-2.0・C++（SYCL） | DualSPHysics と役が重なる |
| [SPlisHSPlasH](https://github.com/InteractiveComputerGraphics/SPlisHSPlasH) | 波の例なし | DFSPH・IISPH など 6 種、CPU | 数値なし | MIT | 非圧縮 SPH の手本 |
| 箱の水の毎フレームの粒子：[Sebastian Lague Fluid-Sim](https://github.com/SebLague/Fluid-Sim)、[PhysX 5 の PBD](https://github.com/NVIDIA-Omniverse/PhysX)（FleX の後継）、[Obi Fluid](https://assetstore.unity.com/packages/tools/physics/obi-fluid-63067) | 波の例なし | 係数で決める圧力の SPH、位置で解く粒子 | 毎フレーム | MIT／BSD-3（CUDA だけ）／有料 | 大波の本体には使えない。Lague の空中の粒子の抵抗は根拠のない力。白い粒子の分け方は見た目の層として借りられる |
| **格子（VOF・レベルセット・格子ボルツマン法）** | | | | | |
| Basilisk（[wave.c](https://basilisk.fr/sandbox/popinet/wave.c)、[Mostert ら 2022](https://arxiv.org/abs/2103.05851)） | 3 次のストークス波（ak 0.55）を周期の箱に置き、重力だけで前へ巻いて崩す例。3D の直接計算で、囲んだ空洞の形と泡・滴の数が理論・実験と合うと著者 | 2 相の NS、VOF、表面張力、適応の格子。初めの条件だけで起こす | 3D は 1 本 約 50 万 CPU 時間。GPU は表面張力に未対応 | GPLv3、C99。Windows の手順なし（WSL が要る見込み） | 初めの条件から重力だけで巻く研究の手本。唇の厚みの確かめ役 |
| [OpenFOAM＋olaFlow](https://github.com/phicau/olaFlow)（OpenFOAM 本体の造波の境界と waves2Foam は[前の調べ](RealtimeBigWave_Survey_ja.md)）、[REEF3D](https://github.com/REEF3D/REEF3D)、Notus（[Lubin & Glockner 2015](https://notus-cfd.org/wp-content/uploads/2020/03/jfm_2015.pdf)）、[Surf Lakes の計算](https://icce-ojs-tamu.tdl.org/icce/article/download/12678/11951/38921) | 造波と吸収の境界での砕波（olaFlow の実験との比べは今回確かめていない）、斜面の巻き波（REEF3D）、弱い巻きから強い巻きまで 12 例（Lubin）、実物の大きさの巻く管（Surf Lakes、波高の差 5%） | RANS・LES、VOF・レベルセット、造波板・緩和の帯、重力 | CPU の MPI、オフライン。Surf Lakes の管の形には格子 0.0625 m（波高の 1/37）が要った | GPL。olaFlow は GitHub のライセンスの欄がないが、OpenFOAM から派生したので GPL の扱いの見込み【推定】。Linux か WSL | 確かめ役。Surf Lakes の比を当てると FLIP42 には格子 約 0.28 m が要る【計算】（R3 は 0.5 m） |
| [FluidX3D](https://github.com/ProjectPhysX/FluidX3D)（GPU の格子ボルツマン法） | コードに「浜に砕ける波」の例（造波の面の速度で起こす、128×640×96 格子）。巻くか・唇の厚みは見ていない | 格子ボルツマン法と VOF の水面。気相を解かない、Mach 0.3 未満で働く、LES あり。重力だけ | RTX 3080 10 GB で 8,118 MLUPs/s（FP32/FP16S、格子あたり 55 B、表面の計算なし）。0.25 m の 3D の窓（920 万格子）で物理の 1 秒に約 0.9 s（表面なし）【計算】。表面の計算で遅くなる量の公表値はない | C++・OpenCL。非商用の研究・教育は可。改変した版で作った結果（動画を含む）を公にするなら、改変したソースも公にする | 3D の窓を Houdini より速く解ける見込み（表面の計算を除いた見積もり。§5.4）。格子の粘り（水の約 50 万倍の値の例）で唇が太る恐れ |
| ELBE（Janßen ら 2013） | 浅くなる所で巻く波（LBM–VOF） | 孤立波の解を初めの状態に | 数値なし | コードの公開なし | 記録だけ |
| **高さ場（水面の高さを一つだけ持つ）** | | | | | |
| 浅水・ブシネスク（Celeris・TsuRuni、[前の調べ](RealtimeBigWave_Survey_ja.md) B 群）、[Fluid Frenzy](https://frenzybyte.github.io/fluidfrenzy/docs/index/)、HOS（[HOS-NWT](https://github.com/LHEEA/HOS-NWT)・HOS-Ocean）、FFT の海（[HDRP の水](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.2/manual/water-capabilities-of-the-water-system.html)・Crest・KWS2） | 群の進み・浅くなっての高まり・険しくなるまで。巻けない（一つの場所に高さを一つしか持たないので、水が自分の上へ倒れ込めない）。HDRP の文書は岸の砕波に非対応と書く | 浅水・ブシネスクの式、HOS（非線形のポテンシャル流）、スペクトルの海 | 毎フレーム（Celeris・Fluid Frenzy・海の面）。HOS は速いオフライン | Celeris Base は MIT、HOS-NWT は GPLv3（Fortran）、Fluid Frenzy は $69.99 | 近づく群・まわりの海・崩れた後の浅い流れ、受け渡しの元。唇は出ない |
| **学習した計算** | | | | | |
| [Neural SPH 2024](https://arxiv.org/abs/2402.06275)、[MLFLIP 2018](https://ar5iv.arxiv.org/html/1704.04456)、[ShipNet 2026](https://arxiv.org/pdf/2606.15356) | 大波が巻く例は見つからなかった | 学習した粒子・しぶき・ポテンシャル流の代わり | 推論は速い | 学習の計算が要る | 候補外。MLFLIP の学習した速度の変化は物理の式から来ない補正 |
| **製品・エンジン** | | | | | |
| [UE5 Niagara Fluids](https://dev.epicgames.com/documentation/en-us/unreal-engine/fluid-simulation-in-unreal-engine---overview) | 3D FLIP の用途に浜の波を挙げる。砕波の試しの動画あり（見ていない）。唇の数値の公開なし | 3D FLIP（Beta）、動く物で押す・力を足す | 毎フレーム。格子数・fps の公表なし | UE だけ | エンジンを替えるのは重い。唇の細かさでは実時間に入らない見込み |
| UE の海の製品（[KeraFlow](https://forums.unrealengine.com/t/brahoule-studio-keraflow-water-plugin/2834591)・[Fluid Flux](https://forums.unrealengine.com/t/2420009)・EasyWaterscape） | KeraFlow は C の形の唇に巻くと書くが、方法を出さず、しぶきを「描いた唇」に置く。Fluid Flux は砕波を計算しないと明記 | 手続きの波・FFT・浅水 | 毎フレーム | UE、有料 | 形を手続きで決める見込みで、対照として記録 |
| Unity の製品（Zibra・Obi・Fluid Frenzy・HDRP の水・Crest・KWS2） | 大波の例なし | MLS-MPM、粒子、2.5D の浅水、FFT | 毎フレーム | 有料〜無料 | まわりの海・浜の流れの候補。大波の本体ではない |
| オフラインの製品（[Chaos Phoenix の手引き](https://documentation.chaos.com/space/PHX4MAX/124761518)・[RealFlow](https://realflow.com/)・Maya Bifrost・[X-Particles の xpWave](https://docs.insydium.ltd/x-particles/dynamics/xpwave)・[LiquiGen](https://jangafx.com/software/liquigen)） | Phoenix の手引きで高さ約 50 m の巻き波。ほかは巻き波の公式の例なし | FLIP 系。大きな波は手続きの海の形へ寄せる力・速度の場（Wave Force・Ocean Force・xpWave・guided）。Phoenix は海の画像の変わる速さのつまみで巻かせる | オフライン（LiquiGen・NeXus は GPU） | 有料。Phoenix は 2026-04 に保守終了、RealFlow は 2019 から版なし | 勧められた作り方は形へ寄せる力。重力と動く境界だけでも使えるが、Houdini より得な点は GPU の速さだけ |
| Houdini Engine（Unity・UE） | — | エディターの中で HDA を動かす | 実行中の計算は公式に支えない | Indie は 3 本まで無料 | 大波の方法を増やすものではない |
| **作品** | | | | | |
| 展示：[Ars Electronica「Die Welle」](https://ars.electronica.art/aeblog/?p=78976)、[d'strict「WAVE」](https://www.designboom.com/design/dstrict-wave-led-screen-south-korea-05-16-2020/)、[HOKUSAI: ANOTHER STORY in TOKYO](https://cgworld.jp/article/202504-cgw320-hokusai.html)、動き出す浮世絵展・Digital×北斎 | 来場者の上で崩れる波、ガラスの箱の中の波、写実の大波から浮世絵の波へ | Die Welle は数か月・数 TB の計算を描いて流し、実時間は軽い粒子だけ。HOKUSAI は Houdini の計算を土台に手で動きを付け、キャッシュを混ぜる。ほかは方法非公開 | 再生 | 非公開 | 「大きな計算は再生、反応する軽い粒子だけ実時間」は今の再生と同じ型。巻く形を計算から出したと示す作品は見つからなかった |
| 粒子と線：[teamLab「Black Waves」](https://www.teamlab.art/jp/w/blackwaves/)・「憑依する滝」、[Utsubo「Waves of Connection」](https://www.utsubo.com/blog/hokusai-interactive-installation) | 波（巻きの記述なし）、滝、粒子のうねり | 粒子の相互作用を計算し表層の軌跡を線に（teamLab）。流れの場と体の力（Utsubo、約 100 万粒子、WebGPU） | 滝・Utsubo は毎フレーム | 非公開 | 線は動きを変えない見た目の層として借りられる |
| VR・ゲーム：[True Surf](https://www.meta.com/blog/true-surf-launch/)、Virtual Surfing、A Colossal Wave、[TsuRuni](https://media.oregonstate.edu/media/t/1_dnzeb389) | 巻く筒（True Surf）、様式化した津波、津波の浸水 | True Surf は自作の 2D の水の計算を参考に作った断面のアニメーションを混ぜる。TsuRuni は UE と compute shader で水を計算 | 毎フレーム | 非公開（Celeris は MIT） | True Surf は断面を並べる型で RT48 に最も近いが、形は手のアニメーション |
| 工学の計算の再生：計算結果を VR で見る津波（[東京大学の発表](https://www.u-tokyo.ac.jp/focus/ja/press/p01_241003.html)。計算は 2012 年）、[Particleworks の Unity 向け](https://monoist.itmedia.co.jp/mn/articles/2105/14/news016.html) | 石巻の津波の遡上（巻く大波ではない） | MPS（半陰的な粒子法）。粒子の径 2 m、最大 2,100 万粒子、768 コアで 27 時間 | 再生 | Particleworks は市販 | 工学の粒子法の結果を Unity で再生する市販の道がある。巻き波の確かめにはならない |
| 映画：LAIKA『KUBO』『Missing Link』（[Art of VFX](https://www.artofvfx.com/?p=16167)）、[Surf's Up](https://www.cgw.com/Publications/CGW/2007/Volume-30-Issue-6-June-2007-/Radical-Dude.aspx) | 嵐の夜の大波、管の巻き | LAIKA は Houdini の計算（Missing Link は誘導の海と狭い帯の FLIP）に、大波の模様を Mari で手描き。Surf's Up は流体計算を使わず rig で形を作る | オフライン | 骨組みだけ公開 | 計算の面に手描きの模様を載せる先例。Surf's Up の「唇から落とす球で落ちる速さを重力と照らす」確かめは借りられる |

### 3.3 波の起こし方（解き手によらない）

| 起こし方 | 例【文献】 | 手で決めるもの | 計算の途中の力 | Q41 との関係（進行役の読み） |
| --- | --- | --- | --- | --- |
| 釣り合っていない険しい波を 1 波長の周期の箱に置く | Deike ら 2016（S＝ak が 0.55・0.6 ではっきり巻く。0.35〜0.42 はこぼれる崩れ）、Mostert ら 2022、Lubin & Glockner 2015、Basilisk の wave.c | 険しさ S、水深と波長の比 | なし | 初めの条件を選んだと書けばよいが、限界より険しい波から放すので「その波がなぜそこにあるか」の説明が要る。場所と時刻は選べない。波高 10.7 m を S 0.55 で作ると波長 約 61 m・周期 約 6.3 s【計算】 |
| 理論の孤立波を斜面に上らせる | Mostert & Deike 2020、Grilli の 2D・3D、本作の FLIP37 P1【記録】 | 振幅と水深の比、勾配 | なし | 斜面を置く理由が要る。岸の崩れで、沖の大波とは場が違う |
| 造波板・入口の帯から分散で集まる群を入れる | Rapp & Melville 1990、Dommermuth ら 1988、FLIP42。焦点の位置は入力の位相の繰り返しの直しで合わせる（Chaplin 1996、Fernández ら 2014） | 成分の振幅・周波数・位相 | なし | 実験の水槽と同じ手順。NewWave も含め、成分の振幅を選ぶことで線形の頂の高さも決まる（Q44） |
| 一過性の波の包み | Bihs ら 2017・2019（REEF3D）：焦点より手前で崩れにくく、短い距離で頂が 9% 高い | 包みの振幅と位相 | なし | 入口の条件だけ。FLIP42 の早い崩れへの試しになる |
| 向きの集まり・交わる波（3D） | Fochesato ら 2007（±45°、細い頂で巻く）、McAllister ら 2019（JFM）・2024（Nature）（交わる角・広がりが大きいと上への噴流）、McAllister ら 2022（JFM）と Kanehira ら 2026（軸対称に集めた波の噴流） | 向きの広がり・交わる角 | なし | 2D では出ない短く高い頂を出す仕組みの一つ（3D で波を集めるものには、海底での屈折や流れとの相互作用もある）。どの広がりで前へ巻く形を保てるかは文献で条件が違い、決まっていない |
| 2D の断面から 3D を始める | Mihalef・Metaxas・Sussman 2004（[Slice Method](https://www.math.fsu.edu/~sussman/BreakingWavesElectronic.pdf)）、[Lee ら 2010](https://www.graphicon.ru/html/2010/conference/EN/Se2/85.pdf)、[Darles ら 2011](https://arxiv.org/pdf/1109.6494) の総説。Mihalef の 3D は 128×128×64 で 1 コマ 10〜12 分（2004 年） | 2D の計算の一覧から人が選ぶ断面と時刻、初めの速度に掛ける 2〜4 倍の係数（Mihalef）、断面をつなぐ補間とノイズ（Lee） | なし（初めの状態に手を入れる） | 「横にどこも同じ形」に直接当たる確立した手法だが、初めの速度の係数・人の断面選び・横の違いのノイズは Q41 の言う意味の分からない手の入力に当たる。唇が当たるまでは 3D でも真ん中の断面は 2D とよく似る（Guyenne & Grilli 2006）ので、横の違いを物理で出すには 3D で波を集める入力が要る、という裏付けになる【考え】 |
| 海底・リーフの形 | Mead & Black 2001（勾配が急なほど管が丸い）、Grilli の尾根、Surf Ranch・Surf Lakes（機械で押す＋設計した海底） | 勾配・棚・尾根 | なし | 海底を置く理由が要る（Q41）。神奈川沖の沖に急なリーフはない【記録：風の調べ】 |
| 水面に圧力を与える | Adams ら 2009（NFA） | 圧力の場所と時刻 | 水面の圧力 | 風の式から決めた圧力だけが自然の力と言える |
| 形を手で作る | Surf's Up、Horizon Forbidden West、True Surf、Moana（前の調べ） | 断面と動き | — | 主な形と動きを計算から出す求め（Q39・Q44）に合わない |

### 3.4 前の二つの調べの要点（表は各報告にある）

- [毎フレームの計算の例 41 件](RealtimeBigWave_Survey_ja.md)：毎フレームの計算の上に前へ巻く唇を足す論文は 2 件（Thürey ら 2007、藤澤ら 2017）で、唇を出す時・所・初速は手の係数。毎フレームの 3D の液体は箱の中で砕けるまで。高さ場は険しくなるまで。唇が重力の計算から出た例は、どれもオフラインの計算だった（§4）。利用者はその案 1（重力だけの FLIP をオフラインで計算し、Unity で毎フレーム再生）を選び（Q48）、RT48 を作った。
- [Houdini で大波を作る方法 53 項目](HoudiniBigWave_Survey_ja.md)：制作と講座の大波は、形を先に決めるか、計算の途中で誘導・制御の力を入れていた。途中に制御の力を入れない公式の型は「境界から海を入れ、中は重力だけ」の水槽で、公式の例に大波の巻きはない。FLIP42 はこの型に実験の群の条件を入れたもの（§0.2・§0.3）。

## 4. 分かったこと

1. **重力だけで前へ巻き、実験と比べた報告のある確立した実装は二つの系だった**【文献・考え】。(a) 水面を追う流体計算（VOF・レベルセット・SPH・FLIP・格子ボルツマン法）のオフラインの数値水槽。造波板・吸う帯・集める波の造波が、海岸工学の公開のコード（DualSPHysics・REEF3D・OpenFOAM＋olaFlow・HOS-NWT）に道具の機能として既にある。(b) ポテンシャル流の境界要素法（巻くまで）。1976 年に始まり、1988 年に実験と合い、2001〜2007 年に 3D へ広がった。製品の勧める作り方と作品の大波は、どちらにも当たらなかった（寄せる力、手の形、方法非公開）。
2. **FLIP42 は (a) の型で、足りないのは独立の確かめの相手だった**【記録・文献】。Dommermuth ら 1988 は、FLIP42 の元（水深 0.60 m、32 成分、中心 0.88 Hz、帯域の比 0.73）と同じ水路・同じ帯域（0.56〜1.2 Hz）の巻き波を (b) で解いた。巻く時刻は実験より中心周期の約 0.05 倍早く、場所は約 9 cm 手前だった（FLIP42 と同じ向き。FLIP42 は出典の表より周期の 0.33 倍早い）。実験と比べたのは波高計の水面の高さ・流速・巻く場所と時刻で、唇の形と厚みは比べていない。焦点の距離と振幅は FLIP42 の組と別の場合である。同じ群を (b) で解けば、早い崩れが FLIP の計算の癖かを、巻く場所と時刻の実験の幅で分けられる。唇の厚みには実験の幅がなく、粘りのない理論の答えとの比べになる【考え】。
3. **重力だけで粘りのない計算は、長さを何倍にしても同じ形になる**【考え：フルードの相似】。境界要素法（表面張力なし）は実験の大きさで解いた結果を 70 倍にそのまま直せる。FLIP42 も同じ扱い。DualSPHysics を人工の粘りだけで使う場合も、その粘りは粒子の大きさと音速（√(gd) に比例）に比例するので、粒子の数が同じなら同じ形になる【考え】。物理の粘りと乱れの模型（DualSPHysics の層流の粘りと SPS）や表面張力（Basilisk）を入れる場合は、この相似の外になる。
4. **毎フレームの計算で、重力から前へ巻く唇を出した公開の例は見つからなかった**【文献の範囲で】。三つの調べを通して同じだった。ただし、Niagara Fluids の砕波の試しの動画と SIGGRAPH 2023 の講座（Liu ら）は中身を見ていない（§9）。2D の断面に限ると、焦点のまわりの窓の GPU の FLIP は 1 段 3〜7 ms 以下の見込みで、測るまで分からない。2D の境界要素法は巻く直前に段が細かくなるので、毎フレームには入らない見込み【推定】。
5. **唇を厚く・張り出させる物理のつまみは、条件の選び方だけだった**【文献・考え】：群の強さ（S）、向きの集まり（3D）、海底の勾配（置く理由が要る）、焦点より手前で崩さない入力（波の包み）。細かさについて、Surf Lakes の計算は管の形に波高の 1/37 の格子が要った。FLIP42 の R3 は 1/21、R4 は 1/30 で、唇と囲んだ空気が細かさで落ち着かない記録とつじつまが合う【計算・考え】。
6. **3D の向きの集まりで巻くかは、文献の条件で分かれる**【文献】。Fochesato ら 2007 は水深 20 m・±45° の集まりで波高 10.8 m が細い頂で前へ巻いた。McAllister ら 2019・2024 は、交わる角や広がりが大きいと上への噴流になった。二つは造波の形が違い、この作品の条件でどちらになるかは計算してみるまで分からない【考え】。2D の断面から 3D を始める手法（Mihalef ら 2004 ほか）は、横の違いを人の選び・係数・ノイズで足すもので、横の違いを物理で出すものではない【考え】。
7. **Houdini の外の道具に替えても、重力だけで巻かせる方法は増えない**【考え】。どの FLIP の製品も重力と動く境界で波を起こせ、差は速さ（GPU の LiquiGen・NeXus・FluidX3D）・値段とライセンス・保守の状態にある。速さの差が最も大きいのは GPU の格子ボルツマン法（FluidX3D）だが、巻き波を実験と比べた例はない。
8. **作品から借りられるのは、分け方と見た目の層だった**【考え】。「大きな計算は再生、軽い粒子だけ実時間」（Die Welle）、表層の粒子の軌跡の線（teamLab）、計算の面に手描きの模様（LAIKA）。どれも水の動きは変えない。

## 5. 実装の候補（進行役の順位。決めるのは指導教員）

### 5.0 並べ方

候補を並べる前に、次の 5 つで比べると決めた【考え】：(i) 手法が確定している（式が公開され、実験と比べてある）、(ii) 計算の途中の力は重力だけで、波は境界か初めの条件から（Q41 の読み）、(iii) 10/29 までに見せる物か確かめの答えが出る、(iv) 今の足りない所（横にどこも同じ形、薄い唇、早い崩れ、毎フレームの計算でない）のどれに効くか、(v) ダウンロード・購入・ライセンスの重さ。

| 順 | 候補 | (i) 確定 | (ii) 力 | (iii) 10/29 | (iv) 効く所 | (v) 入手 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2D の境界要素法の数値水槽を自作し、FLIP42 と同じ群を巻くまで解く | 1976 年から。同じ水路・帯域の実験の再現がある | 重力と造波板 | 確かめの答えと、唇が触れるまでの同じ断面の動画 | 早い崩れの原因を分ける（巻く場所と時刻は実験の幅で、唇の厚みは理論の答えと比べる） | なし |
| 2 | DualSPHysics で同じ群を崩れまで解く | 海岸工学で波高・平均の水位などを実験と比べてある | 重力と造波板（数値の安定の項は書く） | 別の解き手による同じ断面の動画（崩れまで）。3D は 1 本が日の単位 | 崩れまで含めた独立の比べ。Houdini の外の実装 | ダウンロード（LGPL） |
| 3 | 同じ断面の FLIP を Unity の GPU で毎フレーム解く（毎フレームの計算が求められる場合だけ） | FLIP は確定。毎フレームで巻き波の群を解いた例はない | 重力と入口の帯 | 2〜4 週で試作（10/12 の報告の 1〜2 週を改める。§5.3） | 「毎フレームの計算でない」こと | 読むだけなら なし（取り込むならダウンロード） |

1 と 2 は、指導教員の「リアルタイム」の答えによらず役に立つ。3 は、毎フレームの再生が「リアルタイム」に入らない場合に要る。1 と 2 は造波板で波を起こすので、入口の帯で流れの速さを理論の値へ寄せること（Q41 の扱い 4 の問いの一つ）をしなくて済む。造波板が何を表すかの問いは残る。

**10/29 に作品で見せられる物【推定】**：
- 候補 1：今と同じ断面で、群が集まって唇が前の水面に触れるまで。崩れは出ない。崩れを FLIP へ渡す段（2〜4 日）は 10/29 に入らない恐れがある。
- 候補 2：今と同じ断面を、Houdini でない解き手で崩れまで計算したもの。
- 候補 3：今と同じ断面を、見ている間に計算するもの。
- どれも 2D の断面なので、作品の見え方の大きな所は変わらない：船から見上げる角（最大 17.5°）、横にどこも同じ形の長い堤、白い水がないこと。横の形を物理で変える道は §5.4 の 3D である。候補 1 は作品の見え方を変える物ではなく、今の計算が物理として正しいかを確かめる道具である。

**日付の見通し【推定】**：お返事が 10/14 なら 10/29 まで約 15 日。候補 1 は短い見積もりで約 1〜1.5 週、長い見積もりで 3〜4 週。候補 2 は 5〜8 日と計算の時間。両方の下の値の和は約 12 日で 15 日に入るが、上の値では 1 だけでも入らない。そこで関門を置く：**10/21 までに 1988 年の場合の再現（§5.1 の確かめ方 1）が通らなければ、候補 1 を止めて候補 2 へ移る。** 10/21 から候補 2 の 5〜8 日で 10/26〜10/29 になる。

### 5.1 候補 1（推し）：2D の境界要素法の数値水槽を論文から自作し、FLIP42 と同じ群を巻くまで解く

- **作品での見え方**：今と同じ断面の大波で、群が集まり、前の面が立ち、唇が前へ張り出して前の水面に触れるまで。水面は格子のない一本の線（数百の点）なので、唇の厚みと張り出しが粒子の大きさに縛られない。RT48 はコマごとの水面の線を横へ掃いて描くので、点を同じ数に並べ直せば載る見込み（試していない）。書き出す時刻は計算の段と別に選べるので、コマを細かく書き出せる（FLIP も書き出すコマを増やせば同じで、この候補だけの利点ではない）【考え】。唇が触れた後（崩れ）は出ない。崩れを見せるなら、触れる少し前の状態を Houdini の FLIP の初めの状態に渡す（海岸工学で使われてきた受け渡し、§3.2）。
- **手順と時間（この機械）【推定】**：
  1. 2D の MEL を NumPy で書く：コーシーの積分の式（または グリーンの式）、水面と造波板・奥の壁の境、水面と壁の交わる点（φ と流れ関数の両方を与える Lin 1984 の扱い）、ABM4 の時間の進め方（初めは RK4）、点の並べ直しと平滑化、段の長さの決め方（どの線分も 1 段で長さの 10 % 以上動かない）。1〜3 週（調べの二つの見積もり 3〜7 日と 2〜3 週の幅）。難所は、特異な積分、造波板と水面の角の点（Lin 1984 の扱い）、鋸の歯の揺れ。
  2. Dommermuth ら 1988 の場合を再現する（付録 B の造波板の係数の表をそのまま入れる）。走らせる前に幅を決めて凍結する。1 本 20 秒〜7 分（CPU 1 コア）。**関門：10/21 までにこれが通らなければ、候補 1 を止めて候補 2 へ移る（§5.0）。**
  3. FLIP42 の群（32 成分）を、線形の造波の理論で造波板の動きに直して解く。実験の大きさで解いて 70 倍にする（§4 の 3）。1〜2 日。
  4. （選べば）RT48 に載せる 1〜2 日、触れる少し前の状態を Houdini の FLIP へ渡す 2〜4 日。
  - 10/14 にお返事をいただくと、短い見積もりなら 1〜3 は 10/19〜10/24 ごろに終わる。候補 2 の 5〜8 日を足すと 10/24〜11/01 で、10/29 に入るのは早い側だけ。長い見積もりでは 1 だけで 10/29 を越えるので、上の関門で切り替える。4 の受け渡しは入らない恐れがある。CPU を使うので、Houdini の計算と同時に走らせると互いに遅くなる。
- **ダウンロード・購入・ライセンス**：なし。自分のコード。Surftank（MATLAB、GPL-3.0）は読むだけの参考。
- **危うさ**：
  - 方法は確定しているが、私たちのコードは新しい。だから 1988 年の場合の再現を、日付つきの最初の関門（10/21）にする。
  - 並べ直しと平滑化は数値の工夫で、強くすると唇の形を変えうる。1988 年もエネルギーの誤差が平滑化を入れた後に目立ったと書く【文献】。
  - FLIP42 は入口の帯で波を入れ、境界要素法は造波板で入れる。入れ方の違いを比べに含める必要がある。
  - 唇が触れた所で止まる。2D なので横にどこも同じ形のまま。
  - 毎フレームの計算には使わない。巻く直前は段が約 0.8 ms まで短くなり、1/90 s に約 13 段要る。1 段ごとに約 550 未知数の密な行列を組んで解く（1988 年は時間の 8 割が組み立て【文献】）ので、11.1 ms に入る根拠がない【推定】。保存して再生する。
- **Q41 との関係（進行役の読み）**：力は重力だけ。波は造波板（境界の条件）から起こり、造波板の動きは実験で測った値か線形の造波の理論で決める。並べ直しと平滑化は形を作る力ではないが、数値の工夫として書く。造波板が何を表すか（遠くで風に起こされて入ってくる波か）の問いは FLIP42 と同じく残る（Q41 の扱い 4）。
- **確かめ方**（走らせる前に幅を決めて凍結する）：
  1. 1988 年の場合：前の面が前の谷に触れる場所と時刻が、論文の計算の値に入るか。線分の数を 2 段（250・500 など）で変えて形が落ち着くか（論文は波長あたり 40 線分で誤差 0.5% 未満と書く）。エネルギーの誤差が論文と同じ桁（数 % 未満）か。
  2. FLIP42 の群：巻き始めの時刻と場所、頂の高さ、前の面の険しさ、触れる直前の唇の厚みを、FLIP42 の R3・R4 と比べる。実験の幅があるのは巻き始めの場所（484〜592 m を 70 で割った値）と時刻だけで、これは出典の表・実験の観測と比べる。境界要素法がその幅に入り FLIP42 だけが早ければ、早い崩れは FLIP の計算か入口の帯から来る。どちらも早ければ、入力の群か比べた値から来る【考え】。唇の厚みには実験の幅がない。境界要素法の唇が線分の数で落ち着き、FLIP42 より厚ければ、FLIP の細かさか数値の粘りが唇を薄くしていると読む。同じなら、唇の薄さはこの群の物理の答えと読む【考え】。

### 5.2 候補 2：海岸工学の公開の数値水槽 DualSPHysics（GPU の SPH）で、同じ群を崩れまで解く

- **作品での見え方**：同じ断面で、集まり → 前へ巻く → 前の水面に当たる → はね上がりまでを、Houdini の外の確立した実装で出す。粒子から作った水面（VTK）を水面の線に直して RT48 で再生する。指導教員の Q51 に、「Houdini でない確立した実装でも同じように巻くか」で答えられる【考え】。
- **手順と時間（この機械）【推定】**：
  1. 利用者にダウンロードの許可を伺う（配布の一式。大きさは確かめていない）。
  2. 付属の例 19_FocusedWaves（NewWave の集める波）を走らせ、道具が RTX 3080 で動くことと時間を測る。半日。
  3. 実験の大きさの水路（水深 0.6 m）に、FLIP42 と同じ 32 成分をピストンの造波板で入れる 2D の場面を作る（GenCase の XML）。Lowe ら 2019 の設定（人工の粘り α 0.01、核の大きさ h は粒子間隔の約 1.7 倍）から始める。1〜2 日。
  4. 粒子の数を決めて走らせる。人工の粘りだけの設定は、粒子の数が同じなら大きさによらず同じ形になる（§4 の 3）ので、実験の大きさで解いて 70 倍に直せばよく、70 倍の大きさで別に走らせる必要はない【考え】。Lowe らの目安（粒子間隔は波高の 1/10 以下）では実験の大きさの波高 約 0.15 m に 15 mm だが、唇（70 倍で約 1 m、実験の大きさで約 14 mm）を粒子 4 個で表すには 3.6 mm（R3 の 0.25 m と同じ比、約 47 万粒子）が要る。粗い段と 3.6 mm の 2 段で走らせる。1 本の時間は、二つの例から割った値が 0.5〜3 時間と 40 時間前後に割れている（例ごとに 2D と 3D、音速の置き方が違う）。測るまで分からない。GPU で走るので、Houdini の CPU の計算と並べられる。
  5. 面の道具 IsoSurface で VTK にし、水面の線に直して RT48 に載せる。1〜2 日。
  - 合わせて 5〜8 日と計算の時間。候補 1 の関門（10/21）で移る場合は 10/26〜10/29 になる。3D の窓（120 m × 40 m）は 1 本 20〜40 時間の見積もりで、確かめまではできない。
- **ダウンロード・購入・ライセンス**【文献】：DualSPHysics は LGPL-2.1、v5.4（最後の更新 2025-04）、Windows と Linux の組み立て済みの実行ファイルあり（自分で組み立てるなら Windows は CUDA 12.3 と VS2022）。造波の部品（JWaveGen）と面の道具（IsoSurface）は組み立て済みのライブラリーでソースが配られず、IsoSurface は改変なしの再配布だけ可。購入はなし。
- **危うさ**：
  - 唇 約 1 m は粒子 0.25 m（実験の大きさで 3.6 mm）の 4 個分で、核の効く範囲（h の 2 倍、粒子間隔の約 3.4 倍）とほぼ同じ。粒子が粗いと唇が粒の列になり、人工の粘り・密度の拡散が唇を太らせうる。弱い圧縮で圧力が揺れる。
  - 群は焦点まで約 7 波長・155 s 進む。その間に人工の粘りで群の高さが減る恐れがある（FLIP42 の計算の中の減り 6.0 % と比べる）。
  - 時間の見積もりが割れている（0.5〜3 時間と 40 時間前後）。
  - 造波の部品を書き換えられない。造波板の動きを外から与える道（動きの表を読む機能）で FLIP42 の成分を入れられるかは確かめていない。
  - 3D の向きの集まり（蛇行する造波板）を入れられるかは確かめていない。
- **Q41 との関係（進行役の読み）**：力は重力と、数値の安定のための人工の粘り・密度の拡散・粒子のずらし（形を作る力ではないが、名前と値を書く）。波は造波板（境界の条件）。緩和の帯（帯の中の粒子の速さを理論の値へ寄せる）は使わず、板で起こす形が最も説明しやすい。
- **確かめ方**：付属の例か Lowe ら 2019 の場合を先に再現する。FLIP42 と同じ判定（巻き始めの場所と時刻、前へ巻いて空気を囲むか、着水の時刻と場所、頂の高さ、唇の厚み）を、粒子間隔 2 段で比べる。候補 1 があれば、触れるまでの形を境界要素法と比べる。

### 5.3 候補 3（毎フレームの計算が求められる場合だけ）：同じ断面の FLIP を Unity の GPU で毎フレーム解く

- **作品での見え方**：今の RT48 と同じ断面の大波だが、見ている間に計算する。群が集まるまで約 155 s かかるので、見せる前の部分は場面の前に同じ計算で進めておくか、焦点のまわりの窓（150〜300 m）の入口に群を入れ、最後の 20〜30 s を毎フレーム計算する【考え】。
- **手順と時間【推定】**：RT48 の描き方・船・時計・測り方をそのまま使い、その上に 2〜4 週。10/12 の報告 §6 の 1〜2 週は、描画の方式の違い、圧力の解き方を一から書く手間、blub をそのまま移せないことを見落としていたので改める。
  1. 土台：abecombe の FLIP-Fluid-for-Unity（HLSL の 3D の PIC/FLIP）の計算のコンピュートシェーダーだけを取り出し、2D の断面に直す。abecombe は Unity 2021.3 で、描画は HDRP と VFX Graph なので、本作（6000.4 の Built-in）では描画を使えない（描画は RT48 の水面の線の描き方を使う）。
  2. 圧力の解き方を替える：Jacobi 法 15 回では深さ 30 格子の水に圧力が伝わらないので、多重格子の前処理つき共役勾配法（MGPCG）を HLSL で一から書く。blub の GPU の前処理つき共役勾配法（反復を CPU を待たずに止める作り）は手本になるが、blub は 2022-12 から更新がなく、作者は境界が粗いことを書いているので、そのまま移せる部品ではない。Jet を CPU の手本にする。
  3. FLIP42 と同じ入口の帯（32 成分の流速へ寄せる）と吸う帯を足し、マウスの力を外す。
  4. FLIP42 の R3 と比べ、1 段の時間を測る。
- **ダウンロード・購入・ライセンス**：読むだけなら なし。コードを取り込むなら abecombe（Apache-2.0。取り込んだ部分のライセンスと NOTICE を残す）・blub（MIT）のダウンロードの許可が要る。自分で書き直すこともできる。
- **危うさ**【推定】：巻き波の群を毎フレームの FLIP で解いた公開の例はない。別のコードで R3 の焦点と唇が再現するか分からない。1 段の時間は、断面の全部で 27 ms 以下（描画を含む値から比で直した上限）、窓で 3〜7 ms 以下で、測るまで分からない。RT48 の描画は GPU の p95 0.83〜1.57 ms だった【記録：RT_Playback C7】ので、11.1 ms のうち合成器などの分を残すと、計算に使えるのは約 7 ms。VR の描画と GPU を分け合う。速さが足りなければ、場面の前に計算して再生する形になり、分類は今と同じになる。
- **Q41 との関係（進行役の読み）**：FLIP42 と同じ（重力と入口の帯）。abecombe のマウスの力は外す。
- **確かめ方**：走らせる前に幅を決め、焦点の場所・時刻・頂の比を R3 と比べる（FLIP42 の A3' と同じ ±0.1 波長・±0.1 周期）。唇が前の面に付くか。1 段の時間と、PSVR2 の 1 フレームの時間の p95 が 11.1 ms 以下か。

### 5.4 次点の道（順位はつけない）

| 道 | 効く所 | 時間【推定】 | 入手 | 危うさ |
| --- | --- | --- | --- | --- |
| **3D の窓に向きの集まりを入れ、FluidX3D（GPU の格子ボルツマン法）で解く** | 横にどこも同じ形。短く高い頂が出るか | 用意 1〜2 週（入口に群を入れる境界を自作）。窓 長さ 150 m × 幅 136〜262 m × 高さ 57 m を 0.25 m の格子にすると 7,400 万〜1.43 億格子。メモリーは表面の計算なしで 4〜8 GB（格子あたり 55 B【文献：README】）。表面の分（格子あたり約 12 B【推定：ソースの記憶】）を足すと 5〜9.6 GB で、大きい方は 10 GB の GPU に入らない恐れがある。速さは表面の計算なしで物理の 1 秒に 7〜14 s【計算】、物理の 155 s の全部でも 18〜36 分。表面の計算と書き出しで数倍になっても、Houdini の見積もり（粒子 0.35 m で 1 本 88〜242 時間、10/12 の報告の付録 A）より 1 桁以上短い見込み【推定】。表面の計算で遅くなる量の公表値はない | ダウンロードと C++ の組み立て。LICENSE.md の条件【文献】：売ること、価値がこれに由来する製品やサービスにすることは作者の許しなしにできない、軍事に使わない、AI の学習に使わない、名前はドイツの作品名の保護の対象、挙げられた論文を引く。改変した版の実行ファイルや、それで作ったデータ・結果（動画を含む）を公にするなら、改変したソースも公にする。入口の造波を自作する時点で改変になるので、展示や論文で動画を出せばソースを公開する義務が生じる。入場料を取る展示など商用にあたる場では使えない恐れがある（指導教員に伺う） | 格子の粘り（0.25 m の格子で 0.5 m²/s の例、水の約 50 万倍）で唇が太る。粘りを下げた時の水面の安定は試すまで分からない。気相を解かない。巻き波を実験と比べた例がない。表面の計算の分の遅れは公表値がない |
| HOS で群を運び、FLIP の区画を短くする（受け渡し） | 早い崩れ（運ぶ誤差）と計算時間 | 1〜2 週 | HOS-Ocean はダウンロード済み（Q43、周期の海、Windows 版）。造波板の水槽の HOS-NWT は GPLv3・Fortran・Windows の手順なし | つなぎ目の確かめが要る。崩れより前に渡す |
| 険しいストークス波を周期の箱に置く（Houdini の FLIP か候補 1 の境界要素法で） | 唇の厚みが群の強さ S と細かさでどう変わるかを安く試す | 用意 1〜2 日、2D の 1 本 数分〜十数分 | なし | 自然の海の状態ではなく、作品の大波の本体の根拠には弱い |
| Blender の Mantaflow で同じ群を解く | 巻きが Houdini の設定によらないか | 1〜3 日 | なし（本機の Blender 5.2.2） | 同じ FLIP の系で、方法は増えない。流入を時間で変える入口を作れるかは確かめていない |
| Basilisk で 2 相の 2D の確かめ | 空気・表面張力が唇と囲んだ空気に効くか | 用意 2〜3 日、CPU で数時間 | WSL とダウンロード（GPLv3） | Windows の手順がない |
| 焦点の位置の繰り返しの直し（Chaplin 1996 ほか） | 焦点を決めた場所・時刻へ | 自作 1〜2 日、1 回が 1 本の計算 | なし | 実験の再現をうたう間は使わない（比べの意味が変わる） |
| 白い水の層（Lague の分け方、MIT を読んで自作） | 白い水がない | 3〜6 日 | なし | 出す所と量は手で決めるしきい値（水の動きには戻さない） |

### 5.5 10/12 の報告の 4 つの候補と、この調べで足したこと

[10/12 の報告](../Progress/Supervisor_Report_20261012_ja.md) §6 の候補（3D の窓で向きの集まり、断面のまま条件を変える、同じ断面を GPU で毎フレーム、白い水）に対して【考え】：

- 3D の窓で向きの集まり：Fochesato ら 2007 が、作品と同じ桁（水深 20 m、波高 10.8 m）で向きの集まりだけで細く巻いた計算の記録になる（§4 の 6）。道具としては FluidX3D で 1 本の時間が大きく縮む見込みがある（表面の計算を除いた見積もり。メモリーとライセンスの危うさは §5.4）。2D の断面から 3D を始める確立した手法（Mihalef ら 2004 ほか、§3.3）は、横の違いを手の選び・係数・ノイズで足すので Q41 に合わず、物理で横の形を変えるにはこの 3D の窓が要る、という裏付けになる。
- 断面のまま条件を変える：文献のつまみは群の強さ S（Deike ら・Derakhti ら）、一過性の波の包み（Bihs ら）、海底の勾配（Mead & Black、置く理由が要る）。細かさの目安は Surf Lakes の波高の 1/37。候補 1 の境界要素法なら、一つの条件を数分で試せる。
- 同じ断面を GPU で毎フレーム：土台にできる公開のコードと、圧力の解き方・描画の方式の問題が分かり、日数を 1〜2 週から 2〜4 週に改めた（§5.3）。
- 白い水：Lague の白い粒子の分け方（MIT）が手本になる。

## 6. 現在地

| 項目 | 状態 |
| --- | --- |
| 調べ（Q47・Q50・Q51） | 三つを読んで、この報告にまとめた。今回の 63 項目のうち 49 は一次の出典で読み直した。動画・図は見ていない。ダウンロード・インストール・計算はしていない |
| 実装 | していない。指導教員のお返事まで新しい計算・実装はしない（Q49） |
| FLIP42 と RT48 | 報告は [FLIP_Plunging_ja.md](../Progress/FLIP_Plunging_ja.md)・[RT_Playback_ja.md](../Progress/RT_Playback_ja.md)。指導教員の確認待ち（[10/12 の報告](../Progress/Supervisor_Report_20261012_ja.md)） |
| 3D の窓 | Q46 で止めている |

## 7. 次

**伺いたいこと（指導教員）**

1. 次に実装する手法を、候補 1（2D の境界要素法で同じ群を巻くまで）・候補 2（DualSPHysics で崩れまで）・候補 3（Unity の GPU で毎フレームの FLIP）から、組み合わせと順番も含めて選んでいただけるか。進行役の推しは 1 → 2【考え】。
2. [10/12 の報告](../Progress/Supervisor_Report_20261012_ja.md) §6 の問い 1・2（毎フレームの再生を「リアルタイムな流体シミュレーション」に入れるか、初めの条件と入口の決め方を物理の計算と認めるか）。問い 1 が「入らない」なら候補 3 が要る。
3. 3D を選ぶ場合、FluidX3D のライセンスの条件（非商用に限る。入口の造波を自作すると改変になり、展示や論文で動画を出せば改変したソースを公開する義務が生じる）で修士の作品に使ってよいか。

**日付**：10/13 18:00（ゼミの資料の締め切り）までに利用者から Discord で伺い、なければ 10/14 の共通ゼミで伺う。お返事が 10/14 なら 10/29 まで約 15 日。候補 1 を選んでいただいた場合は、10/21 に 1988 年の場合の再現が通ったかで続けるか候補 2 へ移るかを決め、利用者と指導教員に報告する（§5.0）。

**利用者に伺うこと**：候補 2 を選ぶ場合の DualSPHysics のダウンロードの許可、候補 3 でコードを取り込む場合のダウンロードの許可。

**お返事まで**：新しい計算と実装はしない（Q49）。

## 8. 結果の置き場所

GitHub の imagirelab/GreatWave_2026 の main の枝（作業の枝 `claude/art-first` から早送りで入れる。Q14）。

| 何 | 場所 |
| --- | --- |
| この報告（三つの調べのまとめ） | [`Docs/Research/BigWave_Implementation_Survey_ja.md`](https://github.com/imagirelab/GreatWave_2026/blob/main/Docs/Research/BigWave_Implementation_Survey_ja.md) |
| 毎フレームの計算の例 41 件（Q47） | [`Docs/Research/RealtimeBigWave_Survey_ja.md`](https://github.com/imagirelab/GreatWave_2026/blob/main/Docs/Research/RealtimeBigWave_Survey_ja.md) |
| Houdini で大波を作る方法 53 項目（Q50） | [`Docs/Research/HoudiniBigWave_Survey_ja.md`](https://github.com/imagirelab/GreatWave_2026/blob/main/Docs/Research/HoudiniBigWave_Survey_ja.md) |
| その前の調べ（高い波の仕組み、基準の問題、風、先行の作品） | `Docs/Research/TallWave_Mechanisms_ja.md`・`WaveTank_Benchmarks_ja.md`・`WindWaves_Kanagawa_ja.md`・`PriorWorks_GreatWave_ja.md` |
| 巻き波の計算（FLIP42）の報告と動画 | `Docs/Progress/FLIP_Plunging_ja.md`、`Docs/Evidence/FLIPPlunging/` |
| Unity の毎フレームの再生の試作（RT48）の報告と動画 | `Docs/Progress/RT_Playback_ja.md`、`Docs/Evidence/RTPlayback/` |
| 流体の方法の確かめ | `Docs/Progress/FLIP_MethodCheck_ja.md` |
| 指導教員への報告（10/12） | `Docs/Progress/Supervisor_Report_20261012_ja.md` |
| 指示の記録（Q39〜Q51） | `Docs/Workflow/Production_Workflow_ja.md` |
| 作業メモと項目の一覧（GitHub には上げていない、本機だけ。指導教員は見られない。例ごとの 5 点の短い形は §3.2・§3.3 の表にある） | `Unity/Build/SURVEY47/`（`candidates.json`）、`Unity/Build/SURVEY50/`（`items.json`）、`Unity/Build/SURVEY51/`（`items.json`、6 つの記録） |

## 9. 限界・確かめられなかったこと

- 動画・図を一本も見ていない。巻くか・唇の厚みは、どの例も本文・図の説明文・コードの文による（FluidX3D の浜の例、DualSPHysics の巻き波、Niagara の砕波の試し、KeraFlow、Phoenix の 50 m の巻き波を含む）。
- 唇が巻く所まで解ける 2D の境界要素法の公開のコードは見つからなかった。Grilli の研究室の頁はこの機械から開けなかった。
- 時間の見積もり（候補 1 の自作の日数と 1 本の時間、DualSPHysics の 1 本の時間、GPU の FLIP の 1 段の時間、FluidX3D の窓の時間とメモリー）は、どれも走らせて確かめていない。DualSPHysics の断面の 1 本の時間は、二つの例から割った値が 0.5〜3 時間と 40 時間前後に割れている。FluidX3D の表面の計算の分（格子あたり約 12 B）はソースの記憶による推定で、README・DOCUMENTATION に値がない。
- 確かめの段で読み直せなかったもの：エンジンの 5 項目（RealFlow・Bifrost・Phoenix・X-Particles と NeXus・Houdini Engine）と波の起こし方の 9 項目は、記録だけによる。LiquiGen は確かめの一覧が途中で切れていた。
- 一次の出典で確かめられなかったもの：olaFlow の砕波の実験との比べ（Higuera ら 2013）、REEF3D の巻き波の比べの中身、HOS-NWT の崩れの模型、MPS の巻き波の確かめ、Keeler & Bridson 2014、SIGGRAPH 2023 の講座「Building a Real-time System on GPUs for Simulation and Rendering of Realistic 3D Liquid in Video Games」の方法と数値、Epic の FAQ のコードの扱い、Zibra の VR 対応の区別、Crest 5・KWS2 の値段。
- 日本語の文献（海岸工学論文集の粒子法・GPU の計算）と、学習した計算の崩れの例は、検索の上限で深く探せなかった。
- Dommermuth ら 1988 と FLIP42 の対応（同じ水路・同じ帯域）は記録による。Rapp & Melville 1990 の論文そのものは今回読んでいない。Dommermuth ら 1988 が実験と比べたのは、波高計の水面の高さ・2 か所の流速・巻く場所と時刻で、唇の形と厚みは比べていない（本文で確かめた）。
- Dommermuth ら 1988 の本文は、論文の頁を読む道具が PDF を会話の一時置き場に自動で置いたものから文字を抜き出して読んだ（作品のフォルダーには入れていない）。
- 調べの途中で、ウェブの検索の回数の上限（会話全体で 200 回）に達した。上限の後は手持ちの URL だけを読んだ。毎フレームの計算で巻く例が本当にないか、AQUAgpusph・SPHinXsys の中身（GitHub の頁の表だけ読んだ）、Dold & Peregrine 1986・Dold 1992・Baker ら 1982 の中身（記憶による）、Zibra の更新の状況は、検索で確かめていない。
- まとめの前の確かめの段で一次の出典を読み直したのは 36 項目（items.json の `basis` が verified。うち LiquiGen は確かめの一覧が途中で切れていた）と、作品の 13 項目（`works_verify_ja.md`）。エンジンの 5 項目と波の起こし方の 9 項目は記録だけ（notes）、1 項目は本作の記録。

## 10. 主な出典

- ポテンシャル流：Dommermuth ら 1988（JFM 189, 423–442）https://airsea.ucsd.edu/wp-content/uploads/sites/10/2019/06/1988_DOMMERMUTH_YUE_LIN_et_al-JOURNAL_OF_FLUID_MECHANICS_vol_189.pdf ・ Longuet-Higgins & Cokelet 1976 https://data-ww3.ifremer.fr/BIB/Longuet-Higgins_Cokelet_PRSLA1976.pdf ・ Grilli ら 2010 の章 https://bpb-us-w2.wpmucdn.com/sites.udel.edu/dist/0/6223/files/2020/06/1_bc_ch3-SG.pdf ・ Grilli ら 2001 https://digitalcommons.uri.edu/oce_facpubs/188 ・ Surftank https://github.com/KelvinHamster/surftank
- 結び付け：Biausser ら 2003 https://digitalcommons.uri.edu/oce_facpubs/180 ・ Janßen ら 2013 https://digitalcommons.uri.edu/oce_facpubs/139/ ・ Kanehira ら https://arxiv.org/abs/2512.19924v1 ・ Grid2Grid https://arxiv.org/pdf/1801.00026 ・ Wang ら 2026 https://arxiv.org/abs/2608.25203 ・ Schreck & Wojtan 2022 https://visualcomputing.ist.ac.at/publications/2022/2dto3d_fundamental_sources/ ・ Huang ら 2021 https://arxiv.org/abs/2108.05481
- 初めの条件・起こし方：Deike ら 2016（JFM 801）https://airsea.ucsd.edu/wp-content/uploads/sites/10/2019/06/2016_Deike_Melville_Popinet-Journal_of_Fluid_Mechanics_vol_801.pdf ・ Mostert ら 2022 https://arxiv.org/abs/2103.05851 ・ Lubin & Glockner 2015 https://notus-cfd.org/wp-content/uploads/2020/03/jfm_2015.pdf ・ Stagonas ら（繰り返しの直し）https://discovery.ucl.ac.uk/10045296/1/Stagonas_Experimental_Generation_Focusing_Wave_Groups.pdf ・ Bihs ら https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/2485584 ・ Surf Lakes（Valizadeh ら）https://icce-ojs-tamu.tdl.org/icce/article/download/12678/11951/38921 ・ Mead & Black 2001 https://ref.coastalrestorationtrust.org.nz/documents/predicting-the-breaking-intensity-of-surfing-waves/ ・ McAllister ら 2019 https://www.research.ed.ac.uk/en/publications/laboratory-recreation-of-the-draupner-wave-and-the-role-of-breaki/ ・ McAllister ら 2022 https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/abs/wave-breaking-and-jet-formation-on-axisymmetric-surface-gravity-waves/487B14F30F0C90437038007C1D07FFBE ・ McAllister ら 2024（Nature 633）https://doi.org/10.1038/s41586-024-07886-z ・ 断面から 3D：Mihalef ら 2004 https://www.math.fsu.edu/~sussman/BreakingWavesElectronic.pdf ・ Lee ら 2010 https://www.graphicon.ru/html/2010/conference/EN/Se2/85.pdf ・ Darles ら 2011 https://arxiv.org/pdf/1109.6494
- 公開のコード：DualSPHysics https://github.com/DualSPHysics/DualSPHysics ・ Lowe ら 2019 https://arxiv.org/abs/2002.00827 ・ FluidX3D https://github.com/ProjectPhysX/FluidX3D ・ Basilisk https://basilisk.fr/sandbox/popinet/wave.c ・ REEF3D https://github.com/REEF3D/REEF3D ・ olaFlow https://github.com/phicau/olaFlow ・ HOS-NWT https://github.com/LHEEA/HOS-NWT ・ GPUSPH https://github.com/GPUSPH/gpusph ・ SPlisHSPlasH https://github.com/InteractiveComputerGraphics/SPlisHSPlasH ・ Mantaflow https://github.com/tum-pbs/mantaflow ・ FLIP Fluids https://github.com/rlguy/Blender-FLIP-Fluids ・ abecombe https://github.com/abecombe/FLIP-Fluid-for-Unity ・ blub https://github.com/Wumpf/blub ・ Jet https://github.com/doyubkim/fluid-engine-dev ・ Sebastian Lague https://github.com/SebLague/Fluid-Sim ・ AQUAgpusph https://github.com/sanguinariojoe/aquagpusph ・ SPHinXsys https://github.com/Xiangyu-Hu/SPHinXsys ・ FluidX3D の LICENSE https://github.com/ProjectPhysX/FluidX3D/blob/master/LICENSE.md
- エンジンと製品：Niagara Fluids https://dev.epicgames.com/documentation/en-us/unreal-engine/fluid-simulation-in-unreal-engine---overview ・ Chaos Phoenix の手引き https://documentation.chaos.com/space/PHX4MAX/124761518 ・ Phoenix の保守終了 https://cgpress.org/archives/chaos-moves-phoenix-to-end-of-support-status.html ・ RealFlow https://realflow.com/ ・ X-Particles の xpWave https://docs.insydium.ltd/x-particles/dynamics/xpwave ・ LiquiGen https://jangafx.com/software/liquigen ・ KeraFlow https://forums.unrealengine.com/t/brahoule-studio-keraflow-water-plugin/2834591 ・ Fluid Frenzy https://frenzybyte.github.io/fluidfrenzy/docs/index/ ・ HDRP の水 https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.2/manual/water-capabilities-of-the-water-system.html
- 作品：Die Welle https://ars.electronica.art/aeblog/?p=78976 ・ HOKUSAI: ANOTHER STORY https://cgworld.jp/article/202504-cgw320-hokusai.html ・ teamLab「Black Waves」https://www.teamlab.art/jp/w/blackwaves/ ・ Utsubo https://www.utsubo.com/blog/hokusai-interactive-installation ・ True Surf https://www.meta.com/blog/true-surf-launch/ ・ TsuRuni https://media.oregonstate.edu/media/t/1_dnzeb389 ・ LAIKA https://www.artofvfx.com/?p=16167 ・ Surf's Up https://www.cgw.com/Publications/CGW/2007/Volume-30-Issue-6-June-2007-/Radical-Dude.aspx ・ 津波の VR（東京大学）https://www.u-tokyo.ac.jp/focus/ja/press/p01_241003.html ・ Particleworks の Unity 向け https://monoist.itmedia.co.jp/mn/articles/2105/14/news016.html
- 前の調べと本作の記録：[RealtimeBigWave_Survey_ja.md](RealtimeBigWave_Survey_ja.md)、[HoudiniBigWave_Survey_ja.md](HoudiniBigWave_Survey_ja.md)、[FLIP_Plunging_ja.md](../Progress/FLIP_Plunging_ja.md)、[RT_Playback_ja.md](../Progress/RT_Playback_ja.md)、[Supervisor_Report_20261012_ja.md](../Progress/Supervisor_Report_20261012_ja.md)、[制作手順](../Workflow/Production_Workflow_ja.md)。各項目の出典の全部は `Unity/Build/SURVEY51/items.json` と各記録にある（本機だけ）。
