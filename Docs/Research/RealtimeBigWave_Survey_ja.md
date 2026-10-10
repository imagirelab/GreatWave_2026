# リアルタイムの流体計算で大波を出している例の調べ（Q47）

- 日付：2026-10-11（同日に見直しを受けて直した。直した点と採らなかった点は §9）。書いた者：進行役（Claude）。利用者を通して指導教員に見ていただくための報告（[制作手順の Q47](../Workflow/Production_Workflow_ja.md)）。
- 状態：読むだけの調べ。ダウンロード・インストール・流体の計算はしていない。実装は、利用者が案を選んでから始める（Q47 の扱い 5）。
- 印：【文献】出典にあること。図や動画を自分で見たものは「見た」と書き、見ていないものは「見ていない」と書く。【測った】このリポジトリの記録の値。【計算】式の値。【考え】【推定】進行役の推論と見積もり（確かめていない）。
- 作業メモ：`Unity/Build/SURVEY47/`（Git 対象外）。4 つの範囲の調べ（`papers_ja.md`・`games_vr_ja.md`・`engines_ja.md`・`demos_ja.md`）と、一次の出典での確かめ直し（`papers_verify_ja.md`・`games_vr_verify_ja.md`）。重複をまとめた候補の一覧は `candidates.json`。

## 0. 一枚で

| 流れ | 内容 |
| --- | --- |
| 方針 | 指導教員の指示（Q47）どおり、大波を出しているリアルタイムの流体計算を、論文・ゲームと VR・エンジン・公開の実演から調べた。比べる 6 点は調べる前に決めた（§1） |
| 目標 | 「大波を出していて、手法が確定しているリアルタイムの流体計算」があるかに例ごとの証拠で答え、実装の案を順位つきで出す（§2） |
| 結果 | 41 件（§3）。毎フレームの計算の上に前へ巻く唇を足す論文は 2 件（Thürey ら 2007、藤澤ら 2017）。どちらも唇を出す時・所・初速は手で決めた係数で、出た後は重力で動く。図で前へ巻く唇を確かめられたのは Thürey ら 2007 だけ。毎フレームの 3D の液体は、映像を見た 2 件とも箱の中で砕けるまでで、唇は見えなかった。浅水・ブシネスクの高さ場は険しくなるまでで、巻けない。製品で巻く大波の公開された作り方は、手で作った断面の形だった |
| 分かったこと | 「毎フレームの計算」「手法が確定」「唇が重力の計算から出る」を同時に満たす例は、調べた範囲になかった。唇が重力の計算から出ている例は、どれもオフラインの計算だった（§4） |
| 現在地 | 論文と、ゲーム・製品の 14 項目は一次の出典で確かめ直した。エンジンの製品の多くは確かめ直していない。実装・ダウンロードはしていない（§5） |
| 次 | 案 1：重力だけの FLIP の断面をオフラインで計算し、Unity で毎フレーム再生（約 2 週）。案 2：同じ断面の FLIP を Unity の GPU で毎フレーム計算（案 1 の部品の上に 1〜2 週、速さは測っていない）。案 3：群の進みを毎フレームのブシネスク（Celeris）で計算し、唇から先は再生か手の規則（2〜4 週）。案 4：3D の粒子で巻くかを確かめるだけ。進行役は案 1 を土台に作ることを推す。「リアルタイム」に再生が入るかを、10/13 までに Discord で伺いたい（§6） |

## 1. 方針

### 1.1 指導教員の指示

> まず、調査しましょうか。
> 大波を実現しているリアルタイムな流体シミュレーションを調査してもらいましょう。良いものがあったら、それを実装してもらうのが手法も確定しているので進めやすいと思います。

（2026-10-09 22:46、Discord。利用者が 10/10 に共有。[制作手順の Q47](../Workflow/Production_Workflow_ja.md)）

読み方（Q47 の扱い 2・3）：「リアルタイム」は毎フレームその場で水の動きを計算するものと読み、オフラインの計算の再生・手続きの形・手で作ったアニメーションは別の分類として書く。「大波」は、立ち上がり・険しい前の面・前へ巻く唇・空気を囲む・崩れのどこまでを出しているかを、図や映像で確かめて書く。

### 1.2 比べる 6 点（調べる前に決めた）

1. 分類：毎フレームの計算／オフラインの計算の再生（頂点アニメーションの画像、Alembic など）／手続きの形（Gerstner、FFT、手で作る崩れの形）／混成（どこが何か）／学習した計算。
2. 大波のどこまで：高さ、立ち上がり、険しい・鉛直の前の面、前へ巻く唇、囲んだ空気、崩れとしぶき。海の面だけのものはそう書き、自分で見られなかったものはそう書く。
3. 物理：解いている式（自由表面の Navier–Stokes を FLIP・PIC・APIC・MPM・SPH・PBF・LBM・背の高いセルで、浅水、ブシネスク、線形・非線形のポテンシャル流、波の包み）と、手で決めているもの。
4. 実時間の証拠：fps、格子・粒子の数、領域、機械。この機械（RTX 3080 10 GB、Unity 6000.4.3f1、OpenXR、PSVR2）の VR に入る見込み。PSVR2 は 90 Hz なら 1 フレーム 11.1 ms、120 Hz なら 8.3 ms で、両眼の描画もこの中に入る【計算】。
5. 入手：コード・製品、ライセンス、費用、エンジン、保守、Unity 6 で使えるか。
6. 10/29 までに実装する手間と、要るダウンロード・購入（大きさとライセンス）。

### 1.3 調べた所と読み方

- 論文：SIGGRAPH・TOG・SCA・Eurographics・Pacific Graphics・情報処理学会論文誌・工学の論文。15 系統を、本文・図・公式の動画・特許の記録で確かめ直した。
- ゲームと VR：GDC・SIGGRAPH の講演の資料、開発者の記事、製品の説明。14 項目を一次の資料で確かめ直した。
- エンジン・プラグイン・ミドルウェア：Unity・Unreal の公式の文書、Asset Store・Fab の頁、更新の記録。確かめ直したのは Crest・HDRP・Zibra の一部だけ（§5）。
- 公開の実演・オープンソース・日本語の資料：GitHub、個人の開発者、学会の論文誌、CEDEC の検索。
- 見たもの：Thürey ら 2007・Chentanez ら 2010・背の高いセル 2011・Mihalef ら 2004・PBF 2013 の論文の図、藤澤ら 2017 の論文の図 1〜14（見直しで見た。PDF の図の大きさ）、背の高いセル 2011 の公式の動画（2:30〜3:45）、PBF の補足の動画（0:14〜0:40）。
- 見ていないもの：ゲーム・製品の映像は一本も見ていない。Horizon Forbidden West の講演はスライドの文字だけを読み、図は見ていない。藤澤ら 2017 の動画は見ていない（見るにはファイルを取る形になるので、利用者の許可が要る）。
- 読めなかったもの：GDC Vault の会員向けの講演、CEDEC の資料（CEDiL）、10 MB を超える PDF の一部。「見つからなかった」は、この範囲の中での話である。

### 1.4 この作品の条件

- 【測った】Unity 6000.4.3f1、描画は Built-in（URP・HDRP の package なし）、OpenXR 1.16.1、Alembic 2.4.4。RTX 3080 10 GB・i7-12700K。
- 【測った】断面の板（幅は格子 4 個）の FLIP42：水深 42 m、Rapp & Melville 1990 の巻き波の組を 70 倍、入口の 32 成分の振幅・周波数・位相だけを選び、帯の外は重力だけで解いた。粒子 0.25 m（R3）で、154.7 s・508 m に前の面が鉛直を越え、156.0 s に唇が前の面に付いて空気を囲んだ。η_c 9.6 m、H は前の谷まで 10.7 m、頂は線形の 1.33 倍。唇は届く距離 3.7 m 以下・厚み 1 m 前後（格子 2〜7 個）。粒子 0.177 m（R4）が走らず、細かさで落ち着くかは判定できていない。R3 は CPU で 187.8 s の計算に 5〜7 時間かかった（[FLIP_Plunging_ja.md](../Progress/FLIP_Plunging_ja.md)）。
- 【測った】同じ断面の板で、粒子 0.5 m（R1、粒子の帯 4 m）では巻かず（前の面は最大 63°）、粒子 0.35 m（R2）と 0.25 m（R3）では巻いた（同 付録 B）。
- 【測った】18（[Step_18_ja.md](../Progress/Step_18_ja.md)）で、Houdini FLIP の小試料（FLIP17、49 コマ、85,542 三角形）を Unity 6000.4.3f1 Built-in で再生した。VAT は CPU の更新が中央 0.0018 ms・画像 約 226 MiB（1 コマ約 4.6 MiB）、Alembic は CPU の更新が p95 6.58 ms。PC の画面外の描画でだけ試し、GPU の時間と HMD・両眼の描画では測っていない。

## 2. 目標

1. 指導教員の問い「大波を実現しているリアルタイムな流体計算はあるか」に、例ごとの証拠（図・映像・数値と出典）で答える。
2. 「良いもの」があれば、その手法をこの作品で実装する案と、10/29 までの手間を示す。
3. 案を順位つきで出し、利用者が選ぶ。利用者を通して指導教員に確かめる（Q47 の扱い 5）。指導教員の求め（Q41：力は重力と風のような自然な力だけ。Q44：主な形と動きは計算から出す）に合うかは、方法を説明して指導教員が判断する（Q44 の扱い 7）。

## 3. 結果

### 3.1 候補の一覧（分類ごと）

列の (2)〜(6) は §1.2 の観点。「見た」「見ていない」は、大波の判断に使った図や映像を進行役が自分で見たかどうか。見直しで B5・D8 の 2 行を足し、41 件になった。

#### A. 毎フレームの計算：3D の液体

| # | 候補 | (2) 大波のどこまで | (3) 式と手で決めるもの | (4) 実時間の証拠 | (5) 入手・Unity 6 | (6) 手間・10/29 | 出典 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | Chentanez & Müller 2011（背の高いセルの格子） | 小さな箱（灯台の背丈の 3〜4 倍）の壁際で水が盛り上がり、白く砕けて灯台に当たる。唇・空気は見えない〔動画を見た〕【文献】 | 3D のオイラー方程式（粘りなし）、レベルセットの水面、多重格子の圧力。飛沫・泡・FFT の模様は見た目のため【文献】 | GTX 480、格子 128×34×128、1 フレーム 33.09 ms（描画込み）、刻み 1/30 s【文献】 | コードなし。特許 US10055875B2（Google Patents の表示で有効、2034-09-08 まで）【文献】 | 一から 3 週以上。10/29 までに大波で確かめるのは難しい【推定】 | [論文](https://matthias-research.github.io/pages/publications/tallCells.pdf)・[動画](https://www.youtube.com/watch?v=Jl54WZtm0QE)・[特許](https://patents.google.com/patent/US20130035917A1/en) |
| A2 | PBF（Macklin & Müller 2013）と NVIDIA FleX 1.2（PhysX 5 の PBD の液体も同じ系統） | FleX の灯台の場面：箱（灯台の土台の約 3 倍の幅）の中の波が土台の高さまで上がり、白く砕ける。唇・空気は見えない〔動画を見た〕。論文の場面に海の波はない【文献】 | 密度の拘束を位置で解く粒子法、人工の圧力（著者は物理でない副作用と書く）、XSPH の粘り、反復は 2〜4 回に固定。灯台の場面は重力を半分にし、渦を足す力 50 を入れ、壁をピストンのように動かす（周期 約 5.2 s）【文献】 | 灯台：25.6 万粒子＋飛沫 200 万で 15 fps（GTX 680、描画込み）。論文の表 1：8〜12.8 万粒子で 1 段 4.2〜7.8 ms【文献】 | GitHub で公開（約 319 MB、最後の更新 2021-04）。ライセンスは Nvidia Source Code License (1-Way Commercial)：世界での無償・非独占の利用と派生物を許し、通知を残すことを求める（本文、GitHub の判定は Other）。組み立ては Visual Studio 2013/2015 と、CUDA 9.2.148 か DirectX 11/12 SDK（README）。bin/ に組み立て済みの物があるかは README に書かれていない。Unity 版は販売終了【文献】 | Unity への結び付け 1〜2 週。重力を 9.81 に戻し、渦の力を 0 にする必要（Q41）【推定】 | [論文](https://matthias-research.github.io/pages/publications/pbf_sig_preprint.pdf)・[動画](https://www.youtube.com/watch?v=F5KuP6qEuew)・[GitHub](https://github.com/NVIDIAGameWorks/FleX)・[LICENSE](https://raw.githubusercontent.com/NVIDIAGameWorks/FleX/master/LICENSE.txt)・[灯台の場面](https://raw.githubusercontent.com/NVIDIAGameWorks/FleX/master/demo/scenes/lighthouse.h)・[Unity 版](https://assetstore.unity.com/packages/slug/120425) |
| A3 | Unreal Engine 5 Niagara Fluids | 文書は用途に「waves breaking on a beach」を挙げるが、巻く唇の図・数値はない〔見ていない〕【文献】 | 3D の PIC/FLIP、2D FLIP、浅水の高さ場【文献】 | fps・格子数の公表はない。3D は「hero effects or cinematics」向け、2D がゲーム向けと文書が書く【文献】 | UE5 に付く無料のプラグイン、UE 5.8 でも Beta。Unity では使えない【文献】 | 船・VR・場面を UE へ移すことになり、10/29 には重い【考え】 | [概要](https://dev.epicgames.com/documentation/en-us/unreal-engine/fluid-simulation-in-unreal-engine---overview)・[参照](https://dev.epicgames.com/documentation/unreal-engine/niagara-fluids-reference-in-unreal-engine)・[浜の例](https://80.lv/articles/real-time-beach-waves-simulations-in-unreal-engine-5-3/) |
| A4 | Zibra Liquid／Zibra Effects（Unity） | 海の波・砕波の例はない〔見ていない〕。津波の避難 VR（福岡工業大学、VRSJ 2025、Quest 3）で津波の流れに使われた。巻く波は対象外【文献】 | MLS-MPM（GPU）。物との当たりは学習した距離場【文献】 | 売り手の値で高い機械に数千万粒子。fps の公表はない【文献】 | $49.99、2.1.5（2024-05-22）から更新なし、Built-in・URP・HDRP。Unity 6 への対応は資料で食い違い、確かめていない。VR は上位の Zibra Effects【文献】 | 窓 60×120×20 m を 0.5 m で埋めると約 115 万粒子、0.25 m で約 920 万【推定】 | [記事](https://www.zibra.ai/blog-posts/approaches-to-real-time-fluid-simulation-in-visual-effects)・[店](https://assetstore.unity.com/packages/tools/physics/zibra-liquid-266451)・[津波 VR](https://conference.vrsj.org/ac2025/program/doc/1B1-04.pdf) |
| A5 | Obi Fluid 7 | 手で触る規模の液体。波の例はない〔見ていない〕【文献】 | 粒子と拘束の系（方法名は確かめていない）【推定】 | GPU の計算あり。VR の訓練の作品で 30〜40 fps 下がったという一人の評（検索の要約）【文献】 | $60、7.2（2026-08-26）、Unity 6000.0 で作られた【文献】 | 大波には使えない【考え】 | [店](https://assetstore.unity.com/packages/tools/physics/obi-fluid-63067)・[文書](https://obi.virtualmethodstudio.com/manual/7.0/backends.html) |
| A6 | NVIDIA Cataclysm（UE4、2016） | 町を水浸しにする研究の実演。波・巻く唇の例はない〔見ていない〕【文献】 | GPU の FLIP と UE4 の GPU 粒子【文献】 | 最大 200 万粒子を実時間と記事が書く。機械は確かめていない【文献】 | 当時コードが公開されたと記事が書く。今の入手は確かめていない。UE4 のみ【文献】 | 大波には使えない【考え】 | [記事](https://80.lv/articles/cataclysm-by-nvidia-flood-your-city-in-ue4)・[記事](https://cgpress.org/archives/cataclysm-real-time-fluids-for-ue4.html) |
| A7 | FluidX3D（格子ボルツマン法＋自由表面） | README に波・砕波の例はない〔見ていない〕【文献】 | 格子ボルツマン法、自由表面は VoF（PLIC）【文献】 | RTX 3080 10 GB で 4,230 MLUPs/s（FP32）。描画は実時間【文献】。格子 0.25 m の窓（約 920 万格子）で、格子の上の速さを 0.1 以下に保つと仮定すると、流れ 10 m/s なら計算は実時間の約 1.1 倍、波の速さ √(g·42) ≈ 20 m/s なら約 0.6 倍、巻く噴流（波の速さの 1.2〜1.5 倍）の 30 m/s なら約 0.4 倍。自由表面の手間と描画は別【計算・推定】 | 非商用は無料。OpenCL・C++、エンジンの統合はない【文献】 | 毎フレームの VR には入らない見込み。オフラインの計算の道具としてなら候補【推定】 | [GitHub](https://github.com/ProjectPhysX/FluidX3D) |
| A8 | 公開の小さな実演（matsuoka-601 の WebGPU MLS-MPM、Sebastian Lague の Unity SPH、ブラウザの FLIP、Ten Minute Physics の 2D FLIP、Taichi・NVIDIA Warp・Genesis） | 箱の水・ダム崩れ・水滴。波・唇の例はない〔見ていない〕【文献】 | MLS-MPM・SPH・FLIP【文献】 | WebGPU の MLS-MPM 50 万粒子（RTX 3060 Laptop）、授業の Unity の FLIP 10 万粒子で VR 30〜40 fps（Quest 2）【文献、作業メモの記録】 | オープンソース（ライセンスは一つずつは確かめていない） | 自作するときの土台の候補（案 2）【考え】 | [WebGPU-Ocean](https://github.com/matsuoka-601/WebGPU-Ocean)・[Fluid-Sim](https://github.com/SebLague/Fluid-Sim)・[2D FLIP](https://matthias-research.github.io/pages/tenMinutePhysics/18-flip.html)・[授業](https://courses.cs.washington.edu/courses/cse493v/25wi/public/poster_02.pdf) |
| A9 | Yan ほか 2009（大きさの変わる SPH） | 要旨は「崩れる波・洪水をリアルタイムで」と書く。本文・図は読めていない〔見ていない〕【文献】 | 粒子の分割と併合のある SPH【文献】 | 要旨に数値なし【文献】 | 有料の論文のみ | 判断できない | [要旨](https://pure.ecnu.edu.cn/en/publications/real-time-fluid-simulation-with-adaptive-sph/)・[DOI](https://doi.org/10.1002/cav.300) |
| A10 | Fei ほか 2021（GPU の MPM） | 雪と噴水（cm の規模の水）。波はない【文献】 | MPM【文献】 | Tesla V100 4 枚で 133 万粒子 68.5 fps、14.3 万粒子 55.9 fps【文献】 | 論文のみ | 1 枚の RTX 3080 で VR の 1 フレームに入るのは数十万粒子の見込み【推定】 | [arXiv](https://arxiv.org/abs/2111.00699) |

#### B. 毎フレームの計算：高さ場（浅水・ブシネスク・線形の波）

| # | 候補 | (2) 大波のどこまで | (3) 式と手で決めるもの | (4) 実時間の証拠 | (5) 入手・Unity 6 | (6) 手間・10/29 | 出典 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B1 | Celeris（Advent 2017、Base 2019、WebGPU 2026） | 浅くなって集まり、高くなり、険しくなり、崩れて波高が減るまで。高さ場なので唇・空気は出ない〔図は見ていない〕【文献】 | 拡張ブシネスク方程式（Madsen–Sørensen、kd < 3 で分散が合うと著者）。Advent は崩れの模型なし（数値の減りが崩れに似る）、WebGPU 版は Kennedy らの崩れの模型と泡【文献】 | 「実時間より速い」。Briggs の例（234×201）を Quadro K600 で 15 s 未満【文献】。RTX 3080 で格子 1000² 程度なら 90 Hz に入る見込み【推定】 | Base：Unity3D、VR の機器で見られると書く。Mendeley Data の版 1（2019-10-10）、MIT。頁に Unity の版・VR の SDK・ファイルの大きさの記載はない。WebGPU 版：MIT、約 0.9 GB。Advent：GPL【文献】 | 移植に 3〜7 日【推定】。ダウンロードに許可が要る | [論文](https://arxiv.org/abs/1611.05984)・[Base](https://data.mendeley.com/datasets/jdx7tddcxz)・[Base の要旨](https://research.google/pubs/celeris-base-an-interactive-and-immersive-boussinesq-type-nearshore-wave-simulation-software/)・[WebGPU](https://github.com/plynett/plynett.github.io) |
| B2 | Jeschke & Wojtan 2023（分散のある表面の波を足した浅水） | 船の航跡、反射、浸水。崩れない（「cannot handle breaking」と著者）【文献】 | 浅水の流れとエアリーの表面の波に分けて解き、毎段合わせる。正誤表 4 項目【文献】 | RTX 2080 Max-Q、512²・Δx 1 m で描画込み 40 fps 超、計算だけ約 100 fps【文献】 | コードなし。論文は公開【文献】 | 正誤表つきで一から 2 週以上。唇は出ない【考え】 | [ISTA](https://research-explorer.ista.ac.at/record/14240)・[頁](https://visualcomputing.ist.ac.at/publications/2023/GSWSDSW/) |
| B3 | ゲーム・道具の浅水（From Dust、Still Wakes the Deep、Godot RSW） | 浸水・段波・岸の波まで。巻かない〔見ていない〕【文献】 | 浅水の高さ場（From Dust は方法名を公表していない）。Still Wakes the Deep は Niagara の 2D の浅水【文献】 | Godot RSW：608²（5 cm）で 60 fps・計算は GPU の 5 % 未満、2048²（1 m）で約 28 fps（RTX 4070 ノート）【文献】 | Godot RSW は MIT＋CC0、Godot 4.7 以降。ほかは製品の中【文献】 | 大波の本体には使えない【考え】 | [Godot RSW](https://reboot16.itch.io/godot-rsw)・[Still Wakes the Deep](https://www.unrealengine.com/spotlights/making-waves-developing-realistic-water-mechanics-for-still-wakes-the-deep-in-ue5)・[From Dust](https://gdcvault.com/play/1013667/Creating-a-High-Performance-Simulation) |
| B4 | 線形の波（波の包み 2017、ウェーブレット 2018、基本解 2019、Wave Curves 2020、Wave Particles 2007） | 振幅の小さい線形の水面の波だけ。崩れ・唇はない〔見ていない〕【文献】 | 線形の波の理論（分散あり）。Wave Curves は既存の計算に後から足す処理【文献】 | 波の包み・ウェーブレットは実時間と著者。機械の数値は読んだ頁にない【文献】 | 波の包みは Zenodo にコード（1.5 MB、条件の書かれていない「Other (Open)」）。ほかはコードなし【文献】 | 大波には使えない。まわりの細かい波の部品【考え】 | [波の包み](https://visualcomputing.ist.ac.at/publications/2017/WWP)・[コード](https://zenodo.org/record/525184)・[ウェーブレット](https://research-explorer.ista.ac.at/record/134)・[Wave Curves](https://research-explorer.ista.ac.at/record/8535) |
| B5 | Unity の高さ場の製品（Fluid Frenzy、Corgi Fluids） | 地形の上を流れる水・岸の波まで。浅水の高さ場なので巻かない〔見ていない〕【文献（検索の要約）】 | Fluid Frenzy：2.5D の浅水（GPU）。Corgi Fluids：浅水（CPU、Unity の Jobs と Burst）【文献（検索の要約）】 | 数値は確かめていない | Fluid Frenzy：Asset Store、Built-in・URP・HDRP、$49.99（掲示板の投稿の値。公式の頁は開いておらず、版は確かめていない）。Corgi Fluids：Asset Store、Built-in・URP、試験の版 2022.3.21f1、$20（検索の要約）【文献】 | 大波の本体には使えない【考え】 | [Fluid Frenzy](https://assetstore.unity.com/packages/vfx/shaders/fluid-frenzy-273366)・[実演](https://frenzy-byte.itch.io/fluidfrenzy)・[Corgi Fluids](https://assetstore.unity.com/packages/slug/294922) |

#### C. 混成（毎フレームの計算に、手で決めた部分を足す）

| # | 候補 | (2) 大波のどこまで | (3) 計算する所／手で決める所 | (4) 実時間の証拠 | (5) 入手・Unity 6 | (6) 手間・10/29 | 出典 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | Thürey・Müller-Fischer・Schirm・Gross 2007（浅水＋巻く膜）と NVIDIA の特許 US8204725 | 険しい前の面から膜が前へ巻いて落ち、しぶきを出す。図 9 は人形の 2〜3 倍の波の唇が巻く。空気は計算せず、膜に厚みも質量もない〔図を見た〕【文献】 | 計算：浅水方程式（重力と圧力だけ）。膜は出た後、重力で弾道に動く。手：前の面のしきい値（p_H = 1/4）、膜の速さの係数 p_v、厚み p_m、崩れが線の中ほどから広がる規則。著者は「2D の計算では巻きを表せない」「見た目の主な特徴をとらえる」と書き、分散がないことも書く【文献】 | Core 2 Duo（1 コア）＋GeForce 7950 で 40.6〜75.2 fps（描画込み）。格子は表で 1.6 万〜2 万、本文で 16 万〜20 万と食い違う【文献】。RTX 3080 の GPU 版なら 90 Hz に入る見込み【推定】 | コードなし。特許は有効と表示、調整後の満了 2030-08-23【文献】。作品での特許の扱いは確かめていない | 1〜2 週で論文から自作【推定】。ダウンロードなし | [論文](https://matthias-research.github.io/pages/publications/breakingWaves.pdf)・[特許](https://patents.google.com/patent/US8204725) |
| C2 | 藤澤・中田・三河 2017（粒子の浅水＋3D の粒子、筑波大学） | ダム崩れ（中央から・建物の間）と水滴の場面。2D の粒子が急に高くなる所から、頂のしぶき（top）と、波の側面から横へ飛ぶ「巻き波」（steep）の 3D 粒子を出す。図 7・10・11 では、広がる輪の波と段波の頂に沿って白い 3D 粒子が帯になって出るのが見えるが、前へ巻いて前の面に落ち空気を囲む唇の形は、PDF の図の大きさでは確かめられなかった。図 1 の巻き波は模式図。海の大波の例はない〔論文の図を見た。動画は見ていない〕【文献・見た】 | 計算：2D の SPH の浅水（重力と高さの勾配）。3D の粒子は PBF で動かす（要旨は「3D SPH」と書き、本文 2・3.2 節が PBF と書く）。3D の粒子が水面の下に入ったら消し、その運動量を周りの 2D の粒子へ足す（式 10、3D から 2D への一方向。2D から 3D へは粒子を出す時だけ）。2D と 3D の間で質量は保たない（著者の限界）。手：粒子を出すしきい値 γ_3D・γ_top・γ_steep、初めの高さの係数 α_height、初速の係数 k_top・k_steep（表 1 で場面ごとに変える）。巻き波の粒子の横の速さは √(gh)、向きは 2D の粒子の加速度。出た後は重力と PBF で動く。著者は、波の速さの向きが正しくない場合があること（図 14 b）と、3D から 2D へ運動量を戻すと波が不自然に高くなることを書く【文献】 | GTX TITAN・CUDA、刻み 0.005 s。2D 1.1 万〜15.9 万粒子＋3D 最大 0.8 万〜14.3 万で平均 24.3〜137.5 fps（表面の作成込み）、全部 3D（24.4 万〜100.8 万粒子）の 2.64〜6.29 fps より 9〜23 倍速い【文献】。1 フレーム 1 段なら計算の進みは実時間の 0.12〜0.69 倍【推定】 | コードなし。論文は公開（情報処理学会 JIP 25:486–493）【文献】 | 自作で 1〜2 週【推定】。唇の出方は係数で決まる | [J-STAGE](https://www.jstage.jst.go.jp/article/ipsjjip/25/0/25_486/_article)・[PDF](https://ipsj.ixsq.nii.ac.jp/record/182745/files/IPSJ-JNL5807006.pdf) |
| C3 | Chentanez & Müller 2010（浅水＋粒子＋FFT の模様） | 川・浜・海の面。崩れる前の面は弱めてしぶきの粒子に替える。唇はない〔図を見た〕【文献】 | 計算：浅水、粒子と質量・運動量のやり取り。手：崩れとみなす 3 つのしきい値、流速の上限【文献】 | GTX 480 で 128²＋22 万粒子 9.88 ms、900×135＋25 万粒子 18.05 ms（描画込み）【文献】 | コードなし【文献】 | しぶきの層の参考だけ【考え】 | [論文](https://matthias-research.github.io/pages/publications/hfFluid.pdf) |
| C4 | Chentanez・Müller・Kim 2014（3D 格子＋PBF＋浅水＋手続きの海） | 鯨が跳ねて落ちる大きな水しぶきと、広がる波。崩れる海の波はない〔図は見ていない〕【文献】 | 計算：3D 格子・PBF・浅水を境界で結ぶ。遠くの海と細かい波は手続き【文献】 | GTX 780 Ti で約 30 fps（64³、浅水 512²、PBF 平均 11.2 万）【文献】 | コードなし【文献】 | 船のまわりだけ 3D にする形は合うが、巻く波の例がなく、複数の計算を結ぶので 10/29 には無理【考え】 | [論文](https://matthias-research.github.io/pages/publications/hybridsim_preprinted.pdf) |
| C5 | Crest Water 5／Crest 4（Unity） | 高さ場の重ね合わせで、立ち上がりまで。砕波の計算の記述はない〔見ていない〕【文献】 | 手続き：FFT・Gerstner。計算：物に応じる dynamic waves。Crest 5 は別売りの浅水の package【文献】 | dynamic waves は既定で毎秒 60 回更新。ms の値はない【文献】 | Crest 5：$240、5.10.2（2026-09-30）、浅水の package $80（検索の要約）。Crest 4：GitHub で MIT、Built-in、4.23.0 で Unity 6.4〜6.6 の修正【文献】 | まわりの海に使うなら数日。大波の本体は作れない【考え】 | [Crest 5](https://assetstore.unity.com/packages/tools/particles-effects/crest-water-5-oceans-rivers-lakes-268614)・[Crest 4](https://github.com/crest-ocean/crest)・[更新の記録](https://crest.readthedocs.io/en/stable/about/history.html) |
| C6 | KWS2 Dynamic Water System（Unity） | 砕波・巻く波の記述はない〔見ていない〕【文献】 | 手続き：FFT 4 段。計算：方法は公開されていない（区域ごとに粒子の数を変えると開発者）【文献】 | 開発者の発売前の値：見える 2 km の計算 約 0.2 ms、水全体 1.5〜2 ms（4K）【文献】 | $159、1.1.0f（2026-08-28）。Unity 6・VR の表記なし【文献】 | 方法が公開されておらず、物理の根拠を説明できない【考え】 | [店](https://assetstore.unity.com/packages/package/323662)・[記事](https://80.lv/articles/incredible-ocean-simulation-set-up-in-unity-with-kws2-real-time-water-system/) |
| C7 | Fluid Flux 2・3（Unreal Engine 5） | 岸の砕波は「計算しない」「決めた wave profile のアニメーション」と開発者が書く〔見ていない〕【文献】 | 計算：2D 格子の浅水。手：砕波の形【文献】 | 数値は確かめていない | 有料（記事で $349.99）、UE のみ【文献】 | Unity で使えず、砕波は Q41 に合わない【考え】 | [開発者の答え](https://forums.unrealengine.com/t/2420009)・[記事](https://80.lv/articles/highly-realistic-coastline-set-up-in-ue5-with-fluid-flux-2-0) |
| C8 | Sea of Thieves（2018） | 海は FFT の面。嵐は泡で荒く見せる。巻く波はない〔見ていない〕【文献】 | 計算：甲板に打つ水などの局所の浅水（Mei ら 2007）。手続き：Tessendorf の FFT【文献】 | 製品で実時間【文献】 | 製品の中 | 大波には使えない【考え】 | [講演](https://history.siggraph.org/wp-content/uploads/2022/09/2018-Talks-Ang_The-Technical-Art-of-Sea-of-Thieves.pdf) |
| C9 | phanerozoic/surf（浅水＋弱圧縮 SPH） | 映像なし。説明文は「高さ場は巻けない」と書き、巻く噴流に要る細かさの目安を挙げる（査読なし）〔見ていない〕【文献】 | 浅水と弱圧縮 SPH を別々に持つ（結ぶ口はない）【文献】 | 数値は確かめていない | Hugging Face の kernel | 査読がなく図もないので、§4.4 の根拠には使わない【考え】 | [頁](https://huggingface.co/kernels/phanerozoic/surf) |

#### D. オフラインの計算と、その再生

| # | 候補 | (2) 大波のどこまで | (3) 式と手で決めるもの | (4) 実時間の証拠 | (5) 入手・Unity 6 | (6) 手間・10/29 | 出典 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | Houdini FLIP を SideFX Labs VAT 3.1 で Unity に再生（Zenn の Quest 2 の例、AlembicToVAT、OpenVAT も同じ道） | 再生する元しだい。今の元（FLIP42 の R3、断面の板）は、立ち上がり・鉛直を越える前の面・前へ巻く唇・空気を囲むまで。唇から先は計算ごとに変わる。3D は計算していない〔このリポジトリの動画 fp_1・fp_2〕【測った】 | 元は Houdini FLIP（非圧縮の Navier–Stokes、自由表面、力は重力・圧力・慣性）。手で選んだのは入口の 32 成分と水深だけで、形を作る力と風はない。VAT は形を写すだけ【測った・文献】 | 18：85,542 三角形・49 コマで CPU 0.0018 ms、画像 約 226 MiB（RGBAFloat、1 コマ約 4.6 MiB）。GPU・HMD・両眼では測っていない。VAT だけで 90 Hz・12 s を持つと約 1,080 コマ・約 5 GiB（FLIP17 の 1 コマの値からの比。FLIP42 の面では変わる）【測った・計算・推定】 | SideFX Labs は無料。ライセンスは SideFX の著作権表示つきの BSD 3 条項と同じ形の条件（GitHub の判定は Other）。公式のシェーダーは URP 用で、Built-in のデコーダーは 18 で自作し、Unity 6000.4.3f1 で照合の幅に入った【文献・測った】 | 部品の多くはある。断面の板の結果を使って約 2 週（§6.1 案 1）【推定】。ダウンロード・購入なし | [VAT 3.1](https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.1.html)・[SideFXLabs](https://github.com/sideeffects/SideFXLabs)・[Step_18](../Progress/Step_18_ja.md)・[FLIP_Plunging](../Progress/FLIP_Plunging_ja.md)・[Zenn](https://zenn.dev/dami/articles/56fa752d69c23c) |
| D2 | Unity Alembic（com.unity.formats.alembic、この作品は 2.4.4） | D1 と同じ（FLIP42 の巻き波は通していない）【測った】 | 形の列を読むだけ【文献】 | 18：CPU の更新 p95 6.58 ms（90 Hz の 1 フレームの 59 %）。コマ間の補間は使えない【測った・計算】 | Unity 公式・無料。6000.4 の手引きは 2.4.5【文献】 | 確かめの基準に使う。VR の本番は D1 が向く【考え】 | [手引き](https://docs.unity3d.com/6000.4/Documentation/Manual/com.unity.formats.alembic.html)・[更新の記録](https://docs.unity3d.com/Packages/com.unity.formats.alembic@2.4/changelog/CHANGELOG.html) |
| D3 | 焼いたオフラインの計算を実時間の海に使った製品（Call of Duty: WWII 2017、Killzone 3 2011） | COD WWII：SideFX の頁は「Normandy の浜の写実の海と砕ける波を 60 fps で」「Houdini の海の道具と FLIP で、実時間の海を動かすデータを作った」の 2 文だけ。データの形（面の再生か、手続きの海を動かす値か）、波が巻くか、重力だけの計算かは公開されていない。浜の波で、大きく巻く波とは書かれていない。VR ではない。Killzone 3 は FLIP ではなく、手続きの海を Houdini で事前に動かした頂点の変形の再生〔見ていない〕【文献】 | COD WWII：Houdini Ocean Toolkit と FLIP（オフライン）【文献】 | 60 fps（機種の記述なし）【文献】 | 製品の中 | 「焼いたオフラインの計算を実時間で使う」形の製品の例。Horizon の講演 p.4 もこの二つを先例に挙げる（Killzone 3 は流したメッシュ、COD WWII は繰り返す Houdini の計算）〔スライドの文字〕。巻く大波を再生した先例としては使えない【文献・考え】 | [SideFX GDC 2018](https://www.sidefx.com/community/gdc-2018-presentations/)・[記事](https://80.lv/articles/creating-real-time-oceans-for-call-of-duty-wwii/)・[Killzone 3](https://www.sidefx.com/community/guerrilla-games-killzone-3/)・[Horizon の講演](https://advances.realtimerendering.com/s2022/SIGGRAPH2022-Advances-Water-Malan.pdf) |
| D4 | Mihalef・Metaxas・Sussman 2004（2D の計算から 3D の崩れる波）、Wang ほか 2006（2D の MPS を 3D へ） | Mihalef：オフラインの 3D Navier–Stokes で、唇の下に空気の管、2 つ目の噴流、岩に当たる波〔図を見た〕。図 1 は北斎の『神奈川沖浪裏』。Wang は見ていない【文献】 | Mihalef：CLSVOF の Navier–Stokes。2D の一覧は険しいストークス波から、速度に「運動の係数」2〜4 を掛けて始める（手の値）。選んだ断面を 3D の初めの状態にし、その後は重力だけ【文献】 | 2D 128×64 が 1 本 3〜4 分、3D は 128×128×64。実時間ではない【文献】 | 論文のみ | 断面の結果を 3D の初めの状態や再生に使う道の先例【考え】 | [論文](https://www.math.fsu.edu/~sussman/BreakingWavesElectronic.pdf)・[Wang](https://doi.org/10.1631/jzus.2006.A1018) |
| D5 | JangaFX LiquiGen、ZibraGDS | LiquiGen：GPU の FLIP の単独のソフトで、海・砕波・造波の例と機能の記述は見つからない。ZibraGDS：Alembic の列を圧縮して UE で再生【文献】 | LiquiGen は PIC/FLIP【文献】 | LiquiGen は計算の道具で、作品の中では再生【文献】 | LiquiGen：Indie $19.99/月 か $299.99、14 日の試用。ZibraGDS：UE 5.3〜5.8 のみ【文献】 | 今は Houdini で足りる【考え】 | [LiquiGen](https://www.cgchannel.com/2025/07/jangafx-releases-liquigen-1-0/)・[ZibraGDS](https://www.zibra.ai/zibragds) |
| D6 | 津波の避難 VR（中央大学 2022 の修士論文の要旨） | 遡上の流れ。巻く波は対象外〔見ていない〕【文献】 | 浅水長波の式を安定化有限要素法で解き、Unity 2020.3 で再生【文献】 | RTX 2070【文献】 | 要旨のみ | 防災 VR でも、計算は前もって行い再生する形が使われている例【考え】 | [要旨](https://chuo-u.repo.nii.ac.jp/record/16463/files/nenpou20N3100002E.pdf) |
| D7 | 制御の力で崩れる波を作る方法（Zhang ほか 2011、Brousset ほか 2015・2016） | 描いた形や表の値どおりに崩れる波（要旨）〔見ていない〕【文献】 | Navier–Stokes や SPH に、形へ寄せる外力を加える【文献】 | 実時間の主張なし【文献】 | 論文のみ | 外す。Q41 が外した「制御するための意味が分からない力」そのもの【考え】 | [Zhang](https://diglib.eg.org/handle/10.2312/PE.PG.PG2011short.061-066)・[Brousset](https://hal.archives-ouvertes.fr/hal-01285926) |
| D8 | 実験と比べた砕波の例のある海岸工学のオフラインの計算（DualSPHysics、OpenFOAM と olaFlow・waves2Foam、REEF3D、Basilisk） | 実験と比べた砕波の例がある：DualSPHysics はリーフの上の激しく巻く波（Lowe ら）、REEF3D は斜面の上の集まって崩れる波（Alagan Chella ら 2017）、olaFlow は砕波・遡上・戻り流れ（Higuera ら 2013）、Basilisk は不安定なストークス波から巻いて空気を巻き込む 3D の波（Mostert・Popinet・Deike）〔図は見ていない〕【文献（検索の要約）】 | DualSPHysics：弱圧縮 SPH（GPU は CUDA）。olaFlow：RANS の 2 相（interFoam 由来）。REEF3D：レベルセットの 2 相の Navier–Stokes。Basilisk：表面張力のある 2 相の Navier–Stokes（適応の格子）【文献】 | どれも実時間ではない。Basilisk の 3D は実効 4096³ まで【文献】 | DualSPHysics：LGPL 2.1（大学の頁と写しの記載。公式の LICENSE は開いていない）。REEF3D：GPL（第三者の一覧）。olaFlow・Basilisk：ライセンスは確かめていない。Basilisk は Q43 で潜堤の水面計のデータを取った計算の道具【文献】 | 作品の本番の道具にするのは 10/29 までに入らない見込み。案 1 の元の計算の確かめ（同じ群を別の検証のある道具で解いて比べる）には使える【考え】 | [DualSPHysics](https://github.com/DualSPHysics/DualSPHysics)・[Lowe ら](https://arxiv.org/abs/2002.00827)・[olaFlow](https://github.com/phicau/olaFlow)・[olaFlow の頁](https://csdms.colorado.edu/wiki/Model:OlaFlow)・[REEF3D](https://github.com/REEF3D/REEF3D)・[集まって崩れる波](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/2488783)・[Basilisk の 3D の砕波](https://arxiv.org/abs/2103.05851) |

#### E. 手続きの形・手で作る形

| # | 候補 | (2) 大波のどこまで | (3) 作り方 | (4) 実時間の証拠 | (5) 入手・Unity 6 | (6) 手間・10/29 | 出典 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | スペクトルの海（Tessendorf の FFT、NVIDIA WaveWorks 2.0 と Atlas、Assassin's Creed III・IV、Skull and Bones、UE の Water の Gerstner） | 海の面だけ。尖らせると頂は鋭くなるが、強くすると面が自分を突き抜けて裏返る（形の不具合）〔見ていない〕【文献】 | 線形の波の和と統計のスペクトル。崩れの物理はない【文献】 | どれも実時間。WaveWorks は波長を 4 帯に分けた FFT【文献】 | WaveWorks は GameWorks EULA、UE 用の開発は終了。Unity の統合はない【文献】 | まわりの海に使う部品【考え】 | [Tessendorf](https://jtessen.people.clemson.edu/reports/papers_files/coursenotes2002.pdf)・[WaveWorks](https://developer.nvidia.com/waveworks)・[AC3](https://www.fxguide.com/?p=38193) |
| E2 | Unity HDRP Water System | 文書は「Breaking waves on shorelines」を非対応と書く。Shore Wave の変形と、6.1 の横の変形で作る rolling wave の見本はある（形は画像で与える）〔見本は見ていない〕【文献】 | FFT の 3 帯域と、手で置く変形のデカール。流体の式は解かない【文献】 | ゲーム機で水の描画 約 4 ms（今の世代）・約 7 ms（前の世代）。PC・VR の値なし【文献】 | HDRP に付き無料。この作品は Built-in なので HDRP へ移る必要。HDRP は新機能の予定なし【文献】 | 大波には使わない（形を手で与えるので Q41 に合わない）【考え】 | [対応の一覧](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.2/manual/water-capabilities-of-the-water-system.html)・[変形](https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.2/manual/water-deform-a-water-surface.html)・[ブログ](https://unity.com/blog/engine-platform/new-hdrp-water-system-in-2022-lts-and-2023-1) |
| E3 | 形を式で作る崩れる波（Fournier & Reeves 1986、Peachey 1986、Gonzato & Le Saëc 2000、Jeschke ほか 2003、de Lima ほか 2010） | 岸の規模の巻き波の形（Gonzato・Jeschke・de Lima）。Peachey の高さ場は巻けない〔図は見ていない〕【文献】 | Gerstner・Biesel の軌道に、伸ばす関数・落とす関数を手で足す。流体の式は解かない【文献】 | de Lima：1 波 1 ms 未満（Quadro FX 4800）。Jeschke 2003：5 fps 以上（二次の情報）【文献】 | 論文のみ | 数日で作れるが、形を手で決めるので Q41・Q44 に合わない。比べの相手として記録【考え】 | [Gonzato](https://www.labri.fr/perso/gonzato/Articles/GONZATO_Wave_JVCS2000.pdf)・[de Lima](https://sbgames.org/papers/sbgames10/computing/full/full4.pdf) |
| E4 | Horizon Forbidden West（2022） | 立ち上がり→険しい→前へ巻く→泡、チューブの内側まで見える砕波、とスライドの文が書く〔スライドの文字を読んだ。図と動画は見ていない〕【文献】 | 一つの断面の変形を、手続きの波の線に沿って当てる。断面は薄い水槽の Houdini の計算から取ったが、手直しが多く、手で動かした曲線に替えた（p.10）。講演者は、この種の波を実時間で計算するのは現実的でなく、焼いたオフラインの計算で動かすべきだと書く（p.4）【文献】 | 製品で実時間【文献】 | 製品の中。講演の資料は公開 | 形の出どころが手なので Q41 に合わない。断面を物理の計算にすれば D1 に近づく【考え】 | [講演](https://advances.realtimerendering.com/s2022/SIGGRAPH2022-Advances-Water-Malan.pdf) |
| E5 | True Surf（Quest 版 2025）とサーフィンのゲーム（Barton Lynch Pro Surfing、The Surfer、Surf World Series、Virtual Surfing）、surf-js | バレル（チューブ）を見せるが、作り方は公開されていない。True Surf は、自作の 2D の水の計算を参考に作った断面のアニメーションを並べて補間し、浜と天気でどれを流すか決める〔見ていない〕【文献】 | 手で作る形・手続き（公開の範囲）【文献】 | 製品で実時間【文献】 | 製品の中。surf-js は LICENSE なし【文献】 | 形の出どころが手なので Q41 に合わない【考え】 | [True Surf](https://www.meta.com/blog/true-surf-launch/)・[Steam](https://store.steampowered.com/app/1776170)・[surf-js](https://github.com/lalomorales22/surf-js) |
| E6 | Oceanology NextGen（UE5）、Storm Breakers（Unity） | 販売者・作者は「バレル」「massive breaking waves」と書くが、式・高さは公開されていない〔見ていない〕【文献】 | 式で作る砕波（手続き）【文献】 | Oceanology は RTX 3080・4070 級以上が対象【文献】 | Oceanology：UE のみ、1.9.0（2026-08-04）。Storm Breakers：CC0、URP と VFX Graph、保守なし【文献】 | Built-in では使えず、形が手続きなので Q41 に合わない【考え】 | [Oceanology](https://www.fab.com/listings/87c9af41-62b7-4e70-98e3-fc72eff016ab)・[Storm Breakers](https://github.com/Stormrider31/Storm-Breakers) |
| E7 | Uncharted 3・4 | 大きな「crash wave」は、美術が時間に沿って動かす B スプラインの断面で作る〔スライドの文字を読んだ〕【文献】 | 全て手続きで、実時間の物理の計算は一つも使わないと発表者が書く。波は Wave Particles【文献】 | PS3、全体 30 fps【文献】 | 製品の中 | 形の出どころが手なので Q41 に合わない【考え】 | [要旨](https://history.siggraph.org/?p=140173)・[GDC 2012](https://gdcvault.com/play/1015309/Water-Technology-of) |
| E8 | 展示の作品（Utsubo の万博 2025 の北斎、teamLab「Black Waves」、NTT 東日本「Digital × Hokusai」） | 立ち上がる・巻く・崩れるの技術の記述はない〔見ていない〕【文献】 | Utsubo：流れのベクトル場に沿って約 100 万粒子を運ぶ（物理の正確さより表現と書く）。teamLab：数十万の粒子の相互作用、実時間かは書かれていない。NTT：HMD の擬似の奥行き【文献】 | Utsubo は WebGPU、98 インチ 4K【文献】 | 作品 | 比べの相手（同じ題材の先例）【考え】 | [Utsubo](https://www.utsubo.com/blog/hokusai-interactive-installation)・[teamLab](https://www.teamlab.art/ew/black_waves/borderless-odaiba/) |

#### F. 学習した計算

| # | 候補 | (2) 大波のどこまで | (3) 式 | (4) 実時間の証拠 | (5) 入手 | (6) 手間・10/29 | 出典 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | Hybrid Neural-MPM 2025、ISPH＋GNN 2024、NeuralPFEM 2025 | 前へ巻く波の例はない。ISPH＋GNN はダム崩れ・揺れ・孤立波〔見ていない〕【文献】 | 学習した模型と古典の解法の組み合わせ。Neural-MPM はスケッチから外力の場を作る制御器を持つ（Q41 で外す力）【文献】 | 数値は要旨にほぼない（ISPH＋GNN は圧力の段が最大 80 倍速い）【文献】 | コードは未公開か論文のみ【文献】 | 大波の例も学習用のデータもなく、10/29 の候補にならない【考え】 | [Neural-MPM](https://arxiv.org/abs/2505.18926)・[ISPH＋GNN](https://openaccess.city.ac.uk/id/eprint/32959/) |

### 3.2 強い候補の短い説明

**D1 Houdini FLIP → VAT（オフラインの計算の再生）。** 重力だけの計算で前へ巻いた形を VR に持ち込む道のうち、調べた範囲で例があり、今ある証拠の上で作れる道だった【考え】。FLIP42 の R3 では入口の 32 成分を選んだだけで頂が線形の 1.33 倍に育ち、前へ巻いて空気を囲んだ【測った】。再生は 18 で Built-in のデコーダーまで動いている（PC の画面外だけ）【測った】。ただし分類は「計算の再生」で、指導教員の言う毎フレームの計算ではない。唇から先（2 つ目の噴流、囲んだ空気の大きさ）は計算ごとに変わり、細かさでの落ち着きは判定できていない【測った】。

**B1 Celeris（毎フレームのブシネスク）。** Unity と VR で動く物理の波の計算として、コードと検証の論文がそろっている例は、調べた範囲でこれだけだった【考え】。周期の違う波が分散で集まる仕組みを扱える。ただし FLIP42 の群（水深 42 m、周期 6.96〜14.97 s）では、短い 5 成分が kd 3.0〜3.5 で範囲を外れ、Madsen–Sørensen の分散の式では位相の速さが線形の理論より 2.5〜3.9 % 速い（中心の成分は kd 1.9 で 0.4 %）【計算】。高さ場なので唇は出ない。

**C1 Thürey ら 2007。** 毎フレームの計算に前へ巻く唇を足す方法で、論文と特許に手順が書かれている。毎フレームの計算の例で、図で唇が前へ巻いて落ちるのを確かめられたのはこれだけだった（オフラインでは Mihalef ら 2004 の図も見た）【文献・見た】。膜を出す時・所と、速さ（p_v）・厚み（p_m）は手の係数で、出た後は重力で弾道に動く。膜は質量を運ばない【文献】。著者は、この方法は表面の速度を持つ他の高さ場（ブシネスクを含む）にも載せられると書く【文献】。

**C2 藤澤ら 2017。** 日本の研究で、粒子の浅水から「巻き波」の 3D 粒子を出す。毎フレームの計算で、全部 3D の計算より 9〜23 倍速い【文献】。巻き波の粒子は、しきい値 γ_steep を越えた所で出し、初速は √(gh) と係数 k_steep で決め、出た後は重力と PBF で動く。しきい値と係数は場面ごとに変える【文献】。図を見たが、前へ巻く唇の形は PDF の図の大きさでは確かめられず、場面はダム崩れと水滴で海の大波の例はない【見た】。

**A2 PBF と FleX。** 毎フレームの 3D の液体で、海の波を灯台に当てる場面を自分で見られた例の一つ【文献・見た】。コードは公開されている。ただし灯台の場面は重力を半分にし、渦を足す力を入れていて、Q41 に合わせるには両方を戻す必要がある【文献・考え】。見た範囲では唇は見えなかった。

**A1 背の高いセル 2011 と C4 の結び付け 2014。** 毎フレームの 3D の格子の計算で、波が当たって砕けるまで出している【文献・見た】。領域は灯台の背丈の数倍の箱で、唇は確かめられない。コードはなく、一から作ると 3 週以上【推定】。C4 の「船のまわりだけ 3D、外は浅水」という分け方は、この作品の場面に合う【考え】。

**E4 Horizon Forbidden West と E5 True Surf。** 製品で巻く大波を見せている、作り方の公開された二つの例で、どちらも「断面のアニメーションを波の線に沿って並べる」形だった【文献】。断面は計算を参考にした手の形である。Horizon の講演者は、この種の波は焼いたオフラインの計算で動かすべきだと書く（p.4）【文献】。どちらも映像・図は見ていない。

**D3 Call of Duty: WWII と Killzone 3。** オフラインの Houdini の計算で作ったデータを実時間の海に使った製品の例【文献】。COD WWII の公開の説明は 2 文だけで、データの形、波が巻くか、重力だけの計算かは分からない。Horizon の講演が挙げる先例でもあるが、巻く大波を再生した先例とは言えない【考え】。

**D4 Mihalef ら 2004。** オフラインの 3D Navier–Stokes で、唇の下に空気の管ができる崩れる波を出した。論文の図 1 は『神奈川沖浪裏』である【文献・見た】。断面の結果を 3D に広げる道の先例になるが、初めの速度に手の係数を掛けている【文献】。

## 4. 分かったこと

### 4.1 前へ巻く唇を出す方法と、唇の出どころ

「見たか」は、唇の形を進行役が図や映像で確かめたかどうか。

| 例 | 毎フレームに計算する所 | 唇を決めるもの | 見たか |
| --- | --- | --- | --- |
| Thürey ら 2007（C1） | 浅水の高さ場 | 出す時・所（前の面のしきい値、崩れの広がり方の規則）と初速・厚み（p_v・p_m）は手の係数、出た後は重力で弾道に動く【文献】 | 論文の図で見た |
| 藤澤ら 2017（C2） | 2D の粒子の浅水、3D の粒子（PBF） | 出す時・所（γ_3D・γ_steep）と初速（√(gh) と k_steep、向きは 2D の加速度）は手の係数と規則、出た後は重力と PBF で動く【文献】 | 図を見たが、唇の形は確かめられなかった |
| Horizon Forbidden West（E4） | なし（波の線は手続き） | 手で動かした断面の曲線【文献】 | 見ていない（スライドの文字） |
| True Surf（E5） | 公開の範囲ではなし | 2D の計算を参考に作った断面のアニメーション【文献】 | 見ていない |
| Fluid Flux（C7） | 浅水（岸の外） | 決めた wave profile。巻くかは書かれていない【文献】 | 見ていない |
| Unity HDRP の rolling wave（E2） | なし | 横の変形の画像。巻くかは書かれていない【文献】 | 見ていない |
| Mihalef ら 2004（D4、オフライン） | なし（オフライン） | 重力の計算。初めの速度に手の係数【文献】 | 論文の図で見た |
| この作品の FLIP42 → VAT（D1） | なし（再生） | 重力の計算。手で選んだのは入口の 32 成分と水深【測った】 | このリポジトリの動画 |

- 【考え】毎フレームの計算の上に唇を足している 2 件（C1・C2）は、唇を出す時・所・初速を手の係数と規則で決め、出た後の動きは重力で計算する。規則は力ではないが、唇の出方を係数で決めるので、Q44 の「主な形と動きは計算から出す」に当たるかは読みが分かれる。Q44 は初めの条件と境界の条件を選ぶことを形を作る力と区別しているので、この区別（出し方は手、出た後は重力）を示して指導教員が判断する。
- 【考え】唇が重力の計算から出ている例は、どれもオフラインの計算（Mihalef 2004、この作品の FLIP42）だった。

### 4.2 毎フレームの物理で出ている所まで

- 【文献】高さ場（浅水・ブシネスク：B1・B2・B3・B5、C1・C3 の土台）は、群の進み・浅くなっての集まり・立ち上がり・険しくなるまでを物理の式で出す。高さ場は水が自分の上へ倒れ込めないので、唇・空気は出ない（Thürey ら、Chentanez ら、Jeschke ら、HDRP の文書が同じことを書く）。
- 【文献・見た】毎フレームの 3D の液体（A1・A2）は、小さな箱の中で波が当たって白く砕けるまでで、唇・空気は見えなかった。ほかの 3D の例（A3〜A10）は箱の水・ダム崩れ・洪水で、海の巻く波の例は見つからなかった。
- 【推定】断面の 2D の FLIP を毎フレーム GPU で解いて巻き波の群を出した公開の例は、見つからなかった。粒子の数は、R3 と同じ水槽・粒子 0.25 m で約 140 万（R3 の最大 1,127 万粒子を、幅の向きの 8 層で割った値）。

### 4.3 海の面だけの例

- 【文献】FFT・Gerstner・スペクトルの海（E1）、Crest（C5）、KWS2（C6）、Sea of Thieves（C8）、Jeschke & Wojtan 2023（B2）、線形の波（B4）、Chentanez & Müller 2010（C3）は、海の面と細かい波、しぶき・泡までで、大波の唇はない。

### 4.4 細かさと速さ（毎フレームの 3D で巻かせるには）

- 【測った】FLIP42 の断面の板では、粒子 0.5 m（H 約 11 m の 1/22）で巻かず、0.35 m（1/31）と 0.25 m（1/44）で巻いた。R1 は粒子の帯 4 m も使っていて、条件は細かさだけの違いではない。0.25 m と 0.177 m の比べは R4 が走らず、できていない。
- 【推定】3D の窓を長さ 150 m・幅 40 m とし、粒子 0.35 m・格子 0.7 m にすると、水の全部の深さ（42 m）なら約 590 万粒子、水面から 6 m の帯だけなら約 84 万粒子、格子は約 100 万。公開の毎フレームの例（FleX の灯台 25.6 万粒子で 15 fps〔GTX 680〕、Cataclysm 最大 200 万）と同じ桁だが、同じ数で巻く波を出した例はない。
- 【推定】GPU の FLIP で 1 段 5〜15 ms、計算の 1 秒に 30〜60 段とすると、計算の 1 秒に要る GPU の時間は 0.15〜0.9 秒【計算】。GPU を計算に全部使えば実時間の 1.1〜6.7 倍の速さになる。VR の両眼の描画と GPU を分けると、上側（60 段 × 15 ms、全部の深さの 590 万粒子に近い側）では入らず、下側（30 段 × 5 ms、帯だけの 84 万粒子に近い側）なら入る可能性がある。根拠は A1 の圧力の時間と A2 の 1 段の時間を、帯域の比（RTX 3080 は GTX 480 の約 4.3 倍、GTX 680 の約 4 倍）で直した桁の見積もりで、測っていない。
- 【考え】したがって「毎フレームの 3D で巻かせる」ことが速さの上で無理だとは言えない。言えるのは、同じ規模で巻く波を出した公開の例がなく、確かめるには自分で作って測る必要があることである（案 4）。

### 4.5 指導教員の求めにとっての意味

1. 【考え】指導教員の言う「良いもの」（大波を出していて、手法が確定していて、リアルタイム）に当たる例は、調べた範囲になかった。三つのうちどれかを緩めるか、例のない組み合わせを自分で確かめる必要がある。
2. 【考え】「重力の計算から唇が出る」と「例がある」を守るなら、毎フレームの計算はあきらめて再生にする（D1）。研究の先例は D4（Mihalef ら）。製品では、Horizon の講演者が焼いたオフラインの計算を勧め、Killzone 3 と COD WWII を先例に挙げる（どちらも巻く大波かは公開されていない）。この作品では部品の多くがある。
3. 【考え】「重力の計算から唇が出る」と「毎フレームの計算」を守るなら、断面の 2D の FLIP を GPU で毎フレーム解く道（案 2）か、3D の計算を自分で確かめる道（案 4）になる。どちらも公開の例はない。
4. 【考え】「毎フレームの計算」と「例がある」を守るなら、唇は手の規則（C1・C2）になる。群の進み・集まり・立ち上がりまでは、毎フレームの物理（B1）で出せる見込みがある【推定】。
5. 【考え】「手法が確定」の点では、再生（VAT）・ブシネスク（Celeris）・膜（Thürey 2007）は、公開の資料で手順が決まっている。FLIP そのもの（Zhu & Bridson 2005）も確定した手法で、FLIP42 で使っている。確定していないのは、それを毎フレームの GPU の計算で巻き波の群に使うことである。

## 5. 現在地

| 項目 | 状態 |
| --- | --- |
| 調べ（Q47） | 4 つの範囲を読んだ。一次の出典で確かめ直したのは、論文の 15 系統と、ゲーム・製品の 14 項目（Horizon、COD WWII と Killzone 3、Sea of Thieves、Assassin's Creed、Atlas と WaveWorks、Uncharted、サーフィンのゲーム、True Surf、Oceanology と Storm Breakers、津波の VR と Zibra の一部、毎フレームの浅水、teamLab、Utsubo と NTT、Crest と HDRP）。エンジンの製品のうち Niagara・Obi・KWS2・Fluid Flux・FluidX3D・Cataclysm と Zibra の残りは確かめ直していない。公開の実演は藤澤ら 2017 だけ（図も見た）。見直しで、SideFX Labs と FleX のライセンスの本文、Celeris Base の頁、FleX の README を読み直し、B5・D8 を足して 41 件にした（`Unity/Build/SURVEY47/candidates.json`）。ダウンロード・インストール・計算はしていない |
| 実装 | していない。利用者が案を選んでから始める（Q47 の扱い 5） |
| 断面の板の計算 FLIP42 | R3 までの報告（[FLIP_Plunging_ja.md](../Progress/FLIP_Plunging_ja.md)）は、指導教員の確認を待っている（Q46）。残りの R4d（粒子 0.1768 m）は走らせている（Q47 の扱い 6） |
| 3D の窓（FLIP43） | Q46 で止めている |

## 6. 次

### 6.1 案（進行役の順位）

#### 案 1（土台として推す）：重力だけの FLIP の断面をオフラインで計算し、Unity で毎フレーム再生する

- なぜ：唇が重力の計算から出ていて、その証拠がある（FLIP42 の R3）【測った】。重力だけで巻いた形を VR に持ち込む道で、調べた範囲で例があるのはこの形だけだった【考え】。研究の先例は Mihalef ら 2004（D4）で、Horizon の講演者もこの形を勧める（E4、p.4）【文献】。部品（FLIP42 の設定、18 の Built-in の再生）の多くがある【測った】。
- 何が「リアルタイム」でないか：水の動きは毎フレーム計算しない。まわりの海（FFT）としぶきの粒子は毎フレーム計算にできるが、大波の形は作らない。
- 手順と時間【推定】：
  1. 再生する元を決める。(a) R3 の断面を横に並べる（波は横にどこも同じ形になる。横の変化を付けると手続きになる）。(b) 3D の窓を計算する（粒子 0.25 m・幅 40 m は断面の板（幅 2 m）の約 20 倍の量で、1 本 5〜7 時間から比で 100〜140 時間。粒子 0.35 m なら約 1/3.8 で 26〜37 時間。メモリーに入るかは見積もっていない。10/29 までに 1 本で、確かめはできない）。以下は (a) の場合。
  2. R3 の各コマから水面の断面の曲線を、決まった点の数で取り出す。唇が前の面に付くまでは一本の曲線で表せ、小さく、コマの間を補間できる。付いた後（空気を囲んだ後）は形のつながり方が変わるので、その区間だけ VAT にする。1〜2 日。
  3. 曲線を頂の線に沿って掃いて面にするシェーダーを書き、OpenXR の single-pass instanced の両眼に対応させる（18 のデコーダーは PC の画面外でしか試していない）。2〜3 日。
  4. 船の浮き：水面の高さを CPU で読む（曲線なら CPU に持てる。VAT の画像は GPU にある）。1 日。
  5. まわりの海（Crest 4 か自作の FFT）との継ぎ目と、板の両端の見え方（VR では端が見える）。3〜5 日。
  6. PSVR2 で 90 Hz の GPU と CPU の時間を測る。1 日。
  - 合わせて約 2 週。10/14 に決めると 10/29 に間に合うかはぎりぎり。
- ダウンロード・購入：なし（Crest 4 を使うなら GitHub から。大きさは確かめていない、MIT）。
- 主な危険：指導教員の言う「リアルタイムな流体シミュレーション」に入らない読み。断面の板は横の変化がない。唇は格子 2〜7 個の薄さで、細かさで落ち着くかは判定できていない。Fluid の型の VAT は文書にコマ間の補間がなく、24〜30 Hz の形を 90 Hz で描くと 3〜4 フレームに 1 回しか形が変わらない【文献・推定】。補間のためにコマを 90 Hz に増やすと、12 s で約 1,080 コマ・約 5 GiB になり、10 GB の GPU で VR の描画と並ぶ（FLIP17 の 1 コマ約 4.6 MiB からの比。FLIP42 の面では変わる）【計算・推定】。手順 2 で曲線にするのはこのためで、VAT は空気を囲んだ後の区間だけにする。クリップの長さとコマの速さは、まだ決めていない。
- 確かめ方：(1) Unity の再生と Houdini の面の頂点の位置の差（18 と同じ照合）。(2) PSVR2 で 1 フレームの時間の p95 が 11.1 ms 以下。(3) 見た目は Q44 の観点（波高・険しい前の面・唇・水の厚みと重さ）で利用者と指導教員が判定する。

#### 案 2（毎フレームの計算が要る場合に、案 1 の上に続ける）：同じ断面の FLIP を Unity の GPU で毎フレーム計算し、案 1 と同じ描き方で横へ並べる

- なぜ：唇が重力の計算から出て、しかも見ている間に計算する。指導教員の言う「リアルタイムな流体シミュレーション」に、案 1 より近い【考え】。手法は FLIP（Zhu & Bridson 2005）で、FLIP42 と同じ。公開の 2D の FLIP の実装（Ten Minute Physics、A8）を読んで土台にできる【文献】。2D なら粒子 0.177・0.125 m も軽く、FLIP42 の R4 で判定できなかった細かさの落ち着きにも答えられる見込み【推定】。
- 足りないこと：断面なので横の変化はない（案 1 (a) と同じ）。巻き波の群をこの形で毎フレーム解いた公開の例は見つからなかった。
- 数と速さ【推定】：R3 と同じ水槽で、粒子 0.25 m なら約 140 万、0.177 m で約 280 万、0.125 m で約 560 万。格子 0.5 m なら水の部分だけで約 35 万（1 格子に粒子 4 個）。R3 は CPU で 187.8 s の計算に 5〜7 時間（実時間より約 100〜135 倍遅い）だった【測った・計算】。幅の層をなくして GPU に移すと実時間に近づく見込みだが、測っていない。群が集まるまで約 155 s かかるので、見せる前の部分は場面の前に Unity で同じ計算で進めておき、見せる最後の 20〜30 s を毎フレーム計算する形になる【考え】。
- 手順と時間【推定】：案 1 の手順 3〜6（描き方・船・継ぎ目・測ること）を共通に使い、その上に 1〜2 週：GPU の 2D の FLIP（compute shader）、FLIP42 と同じ入口の帯（32 成分の水平の流速へ寄せる）、R3 との比べ。案 1 と合わせると 3〜4 週で、10/29 を越える見込み。
- ダウンロード・購入：なし（公開のコードは読むだけ。ライセンスは確かめていない）。
- 主な危険：別のコードで R3 の焦点（場所・時刻・頂）と唇が再現するか。速さが足りない場合は、場面の前に Unity で計算して再生する形になり、分類は案 1 と同じになる。
- 確かめ方：走らせる前に幅を決めて、焦点の場所・時刻・頂の比を R3 と比べる（例：FLIP42 の A3' と同じ ±0.1 Lc・±0.1 Tc）。唇が前の面に付くか。1 段の時間と、計算の 1 秒あたりの GPU の時間。

#### 案 3：群の進みと立ち上がりを毎フレームのブシネスク（Celeris）で計算し、唇から先は再生か手の規則にする

- なぜ：大波の動きのうち、群が進み、集まり、高くなり、険しくなるまでを、毎フレームの物理の式で計算できる【文献・推定】。Unity と VR で動くコード（Celeris Base、MIT）と検証の論文がある【文献】。
- 手順と時間【推定】：
  1. Celeris Base を取り、Unity 6000.4 の Built-in・OpenXR へ移す。3〜7 日。Celeris Base は 2019 年の Unity の作りで、Mendeley の頁に Unity の版と VR の SDK の記載はない【文献】。Unity の旧い組み込みの VR を使っていれば、それは 2020.1 で外されたので、VR の部分は OpenXR で作り直す【推定】。
  2. FLIP42 の 32 成分を入口に与える。位相は Celeris 自身の分散の式で設計し直す（入口が 32 成分を受けられるかは確かめていない）。焦点の場所・時刻・頂を線形の式と FLIP42 の R3 と比べる。2〜3 日。
  3. 唇から先：(3a) 前の面が険しくなった時刻に、案 1 の再生へ切り替える。3〜5 日に、案 1 の手順 2〜5 の一部 2〜4 日。(3b) Thürey 2007 の膜を足す。1〜2 週。
  - (3a) で合わせて 10〜19 日（2〜4 週）。10/14 に決めると (3a) も 10/29 に入らない見込みで、(3b) は越える。
- ダウンロード・購入：Celeris Base（Mendeley Data、MIT、大きさの表示なし）。利用者の許可が要る。参考に Celeris-WebGPU（GitHub、MIT、約 0.9 GB）は読むだけにする。
- 主な危険：FLIP42 の群の短い 5 成分は kd 3.0〜3.5 で、位相の速さが 2.5〜3.9 % 速い【計算】。Advent には崩れの模型がなく、焦点の近くで高さ場が不安定になるか高さを失う恐れがあり、FLIP42 の頂の 1.33 倍の育ちが出るかは分からない【推定】。高さ場は巻けない。(3a) は二つの計算の切り替えで形と位置が合わない恐れ。(3b) は唇の出し方が手の係数になり、Q41・Q44 に合うかは指導教員の判断。Thürey の方法の特許（US8204725、有効と表示）の扱いは確かめていない。
- 確かめ方：(1) 焦点の場所・時刻・頂の比を、走らせる前に幅を決めて（例：±0.1 Lc・±0.1 Tc）線形の式と R3 と比べる。(2) 1 フレームの時間。(3) 唇の部分は「手の規則」または「再生」と画面の説明で区別する。

#### 案 4：毎フレームの 3D の粒子で巻くかを小さく確かめる（確かめだけ）

- なぜ：指導教員の言葉どおりの「毎フレームの 3D の流体計算」で巻くかに、数で答える。§4.4 の見積もりでは、帯だけなら VR と並べて入る可能性が残る【推定】。
- 道具の選び方【考え】：私たちの巻きの証拠（FLIP42）は FLIP である。FleX の PBF は人工の圧力・XSPH の粘り・2〜4 回に固定した反復（非圧縮が弱い）を持ち【文献】、薄い膜を減らす恐れがある【推定】。PBF で巻かなくても「毎フレームの 3D の FLIP では巻かない」ことにはならず、巻いても FLIP42 の確かめは引き継げない。確かめるなら、案 2 の GPU の FLIP を 3D にするか、Taichi・NVIDIA Warp の FLIP を使う方が、今の証拠とつながる。
- 手順と時間【推定】：FleX なら、見本の水槽にピストンの造波を置き、重力 9.81・渦を足す力 0 で、粒子の間隔を 2 段（H の 1/22 と 1/31 に当たる間隔）で走らせる。組み立てに Visual Studio 2013/2015 と CUDA 9.2.148 か DirectX 11/12 SDK が要る（README）【文献】。2〜4 日。GPU の FLIP を 3D にする場合は、案 2 の後に 1 週ほど。
  - 確かめだけなら 10/29 前に入る。作品に入れるのは間に合わない見込み。
- ダウンロード・購入：FleX の GitHub（約 319 MB、Nvidia Source Code License (1-Way Commercial)）。利用者の許可が要る。
- 確かめ方：前の面が鉛直を越えるか、唇が前の面に付くか（FLIP42 と同じ読み方）、2 段の細かさで形が落ち着くか、1 段の時間。

### 6.2 利用者と指導教員に伺いたいこと

1. 指導教員の言う「リアルタイムな流体シミュレーション」に、オフラインの流体計算を毎フレーム再生する形（案 1）は入るか。入らない場合、断面の FLIP を毎フレーム計算する形（案 2、横の変化はない）か、唇を手の規則で出す形（案 3 の (3b)）か。
2. 案 1〜4 のどれで進めるか。利用者が選び、利用者を通して指導教員に確かめる。
3. 案 1 の場合、再生する元を (a) 断面の板 R3 を横に並べた形にするか、(b) 3D の窓（Q46 で止めている。粒子 0.35 m で 1 本 26〜37 時間の見込み）を走らせるか。
4. ダウンロードの許可：案 3 なら Celeris Base、案 4 で FleX を使うならその GitHub（約 319 MB）、まわりの海に Crest 4 を使うならその GitHub。
- 日付の提案：ゼミの資料の締め切りは 10/13 18:00（Q43 の扱い 4）。指導教員は Q47 に Discord で 1.5 時間で答えている。問い 1・2 を利用者から Discord で今送り、10/13 までの答えを資料に入れることを提案する。答えがなければ 10/14 のゼミで伺う。

## 7. 確かめられなかったこと・限界

- 映像は、背の高いセル 2011 と PBF の灯台の一部の時刻だけを見た（YouTube の解像度）。Niagara・Zibra・Obi・Cataclysm・FluidX3D・Horizon・COD WWII・True Surf・サーフィンのゲーム・HDRP の rolling wave・Oceanology・Storm Breakers が実際にどう巻くかは見ていない。Horizon はスライドの文字だけを読んだ（この機械には PDF の頁を画像にする道具がなく、10 頁を超える PDF の図は見られなかった）。
- 藤澤ら 2017 は、見直しで本文と図 1〜14 を見た。図は PDF の中の大きさで、唇の形は確かめられなかった。動画（著者の頁、mp4）は見ていない。見るにはファイルを取る形になるので、利用者の許可が要る。PDF は読み取りの道具が会話の一時置き場（リポジトリの外）に自動で保存したもので、図を見るためにその写しを会話の作業用の一時置き場に置いた。
- 実時間の数値は出典の機械の値で、RTX 3080 と PSVR2 では何も測っていない。§4.4 と各案の時間は桁の見積もりである。
- GDC Vault・CEDiL の会員向けの資料、Atlas の GDC 2019 のスライドの全文、Chentanez & Müller 2011 の ACM 版、Narita ら 2025（Quadtree Tall Cells）の本文は読めていない。
- Zibra Liquid の Unity 6 への対応、Crest 5 の浅水の package が本体に入っているか、KWS2 と Obi の方法名、Cataclysm の今の入手、Celeris Base の大きさと Unity の版、Fluid Frenzy の版と値段（公式の頁）、olaFlow と Basilisk のライセンス、Ten Minute Physics のコードのライセンスは確かめていない。D8 の砕波の例は検索の要約で読み、論文の図は見ていない。
- 特許（US8204725、US10055875B2）が研究の作品に関わるかは確かめていない。
- 学習した計算で大波を出す公開の例は見つからなかった。

## 8. 主な出典

- 論文：Thürey ら 2007 https://matthias-research.github.io/pages/publications/breakingWaves.pdf 、藤澤ら 2017 https://www.jstage.jst.go.jp/article/ipsjjip/25/0/25_486/_article 、Chentanez & Müller 2010 https://matthias-research.github.io/pages/publications/hfFluid.pdf 、同 2011 https://matthias-research.github.io/pages/publications/tallCells.pdf 、Chentanez ら 2014 https://matthias-research.github.io/pages/publications/hybridsim_preprinted.pdf 、PBF https://matthias-research.github.io/pages/publications/pbf_sig_preprint.pdf 、Celeris https://arxiv.org/abs/1611.05984 、Jeschke & Wojtan 2023 https://research-explorer.ista.ac.at/record/14240 、Mihalef ら 2004 https://www.math.fsu.edu/~sussman/BreakingWavesElectronic.pdf
- 海岸工学のオフラインの計算：DualSPHysics https://github.com/DualSPHysics/DualSPHysics 、Lowe ら https://arxiv.org/abs/2002.00827 、olaFlow https://github.com/phicau/olaFlow 、https://csdms.colorado.edu/wiki/Model:OlaFlow 、REEF3D https://github.com/REEF3D/REEF3D 、https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/2488783 、Basilisk の 3D の砕波 https://arxiv.org/abs/2103.05851
- ゲーム：Malan 2022 https://advances.realtimerendering.com/s2022/SIGGRAPH2022-Advances-Water-Malan.pdf 、SideFX GDC 2018 https://www.sidefx.com/community/gdc-2018-presentations/ 、Sea of Thieves https://history.siggraph.org/wp-content/uploads/2022/09/2018-Talks-Ang_The-Technical-Art-of-Sea-of-Thieves.pdf 、True Surf https://www.meta.com/blog/true-surf-launch/
- エンジン・道具：SideFX Labs VAT 3.1 https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.1.html 、SideFXLabs のライセンス https://github.com/sideeffects/SideFXLabs 、Niagara Fluids https://dev.epicgames.com/documentation/unreal-engine/niagara-fluids-reference-in-unreal-engine 、HDRP Water https://docs.unity3d.com/Packages/com.unity.render-pipelines.high-definition@17.2/manual/water-capabilities-of-the-water-system.html 、FleX https://github.com/NVIDIAGameWorks/FleX と https://raw.githubusercontent.com/NVIDIAGameWorks/FleX/master/LICENSE.txt 、Crest https://github.com/crest-ocean/crest 、FluidX3D https://github.com/ProjectPhysX/FluidX3D 、Celeris Base https://data.mendeley.com/datasets/jdx7tddcxz 、Fluid Frenzy https://assetstore.unity.com/packages/vfx/shaders/fluid-frenzy-273366 、Corgi Fluids https://assetstore.unity.com/packages/slug/294922
- 各候補の出典は §3.1 の表と `Unity/Build/SURVEY47/candidates.json`、作業メモにある。

## 9. 見直しの記録（2026-10-11）

見直しの指摘のうち、COD WWII の証拠の強さ、藤澤ら 2017 の唇（図を見て書き直した）、Horizon の見た印、確かめ直した範囲の書き方、「唯一の道」、§4.1 の唇の出どころ（出し方は手、出た後は重力）、§4.4 の計算の誤り、FluidX3D の速さの仮定、surf の頁を根拠から外すこと、断面の FLIP を毎フレーム GPU で解く案（案 2）、海岸工学のオフラインの計算（D8）、Unity の高さ場の製品（B5）、案 1 の VR・メモリー・船・継ぎ目の手間、案 3 の日数と Celeris Base の版、案 4 の PBF と FLIP の違い、Discord で先に伺う日付は、本文に入れた。

採らなかった点・一部だけ採った点：

1. 藤澤ら 2017 の「要旨は 3D SPH、報告は PBF」「要旨は一方向、報告は 2D へ戻す」の二つは、本文（2・3.2・3.3 節、式 10）が報告の書き方と合っていたので直さず、要旨との違いを C2 に書き足した。
2. 報告の長さは、記録として表と出典を残すため短くしていない。§0 を短くし、指導教員へは短い文で伝える。
3. Narita・Kanai の Eurographics 2026 の論文は、2 回の検索で見つからず、載せていない。
4. Fluid Frenzy の 1.4.0（2026-02-16）は、公式の頁で確かめられなかったので版を書いていない。検索で出た非公式の配布の頁は使っていない。
5. 指摘の最後の節（ライセンスについての E 節）は、受け取った文が途中で切れていて読めなかった。代わりに、SideFX Labs と FleX のライセンスの本文を読み直して表に入れた。
6. Horizon のスライドの図は、この機械に PDF の頁を画像にする道具がなく見られなかったので、「見た」の印を「文字を読んだ」に直すだけにした。藤澤ら 2017 の動画は、ファイルを取る形になるので見ていない（利用者の許可待ち）。
7. 「Unity の旧い組み込みの VR は 2020.1 で外された」は出典を開いておらず、【推定】のままにした。
