# 基準の問題で方法を確かめる：水深で変わる波の速さを中心に（FLIP41 の調べ）

> 写し：元は `Unity/Build/FLIP41/research/benchmarks_ja.md`（Git 対象外、2026-10-08）。直したのは、ほかの文書を指す名前とリンクの相対パスと、読む道具の一時置き場のパス（個人のパス）1 か所だけで、ほかは元のまま。文中の【計算】の JSON は [Docs/Evidence/FLIPMethodCheck](../Evidence/FLIPMethodCheck/) に写した。測った結果は [方法の確かめの報告](../Progress/FLIP_MethodCheck_ja.md)。

- 日付：2026-10-08。書いた者：進行役（Claude）。
- 目的：Q41 の指導教員の答え「海底の深さに応じて速度は変化しますが、それの効果が反映されるシミュレーションなのかは、方法を確認しなければ何も言えません」に向けて、流体力学・海岸工学で数値の水槽を確かめるのに使われている基準の問題（理論の式や、公開された実験の値と比べる問題）を集め、何を比べられるか、どこにデータがあるか、この PC で小さく再現すると何時間かかるかを調べた。そのうえで、問いに答える最小の組を勧める。
- 状態：調べだけ。**流体の計算は一本も走らせていない。** 数のうち【測った】は、FLIP37・FLIP39 の既存の記録を読んだもの。
- 印：【文献】出典の内容。【計算】`Tools/GWWaveGen/flip41/b_theory_numbers.py` で出した理論の値（結果は同じフォルダーの `b_theory_numbers.json`）。【測った】既存の記録の値。【推定】既存の計算時間から比で見積もった値。【考え】進行役の推論。
- ダウンロード：データ・論文のファイルは取り込んでいない。リンクと大きさだけ §9 に書いた。ただし、論文の頁を読む時に、読む道具が PDF 5 本（合わせて約 12 MB）を会話の一時置き場（C: の `.claude` の下）に自動で保存した。G: と作品のフォルダーには何も入れていない（§8）。
- 関係する調べ：同じフォルダーの [WindWaves_Kanagawa_ja.md](WindWaves_Kanagawa_ja.md)（風で波を起こす方法と、神奈川沖の本当の水深）。風そのものの確かめと、場所の水深はそちらに任せ、この文書は「計算の方法が、水深で変わる波の速さを正しく表すか」に絞った。

## 0. 要点

1. **指導教員の問いに答える最小の組は三つ**：B1 一定の水深での波の速さ（線形の分散の式と比べる）、B2 ゆるい斜面を上る波の速さと高さ（線形の浅水変形と比べる）、B3 潜堤の上の波の変形（Beji & Battjes 1993 の実験。公開の測った値と比べる）。B1 は「速さが水深と波長でどう決まるか」そのもの、B2 は「水深が変わる所で速さが付いていくか」、B3 は「先人が使ってきた実験で、水深の変化が生む波の形の変化まで合うか」を見る（§5）。
2. **すでに測った事実がある。** FLIP39 の造波の較正 C1（格子 2 m、振幅の小さい群）で、短い成分ほど FLIP の中で遅く弱くなり、群が集まる所が設計より 108 m 沖・6.7 秒早くずれた【測った：FLIP39 E の記録 §4.1】。原因（格子の粗さ、粒子の帯、流速の受け渡しの方法など）は切り分けていない。今の設定では、少なくとも短い波の速さが線形の式と合っていない見込みが高い【考え】。
3. **C1 の記録は使い回せない。** 成分の間の周波数の差 0.0177 rad/s を分けて速さを測るには約 354 秒の記録が要るが、C1 は 95 秒しかない【計算】。成分ごとの速さを測るには、規則波の専用の計算（B1）が要る。
4. **今の造波の帯は、Jacobsen ら（2012）の方法そのものではない。** Jacobsen らは帯の中で流速の全成分と水の割合（水面）を目標へ寄せる【文献】。FLIP39 の帯は水平の流速だけを寄せ、縦の流速と水面は寄せていない【道具を読んだ：`flip39/e_tanklib.py` の `relax_zones`】。「確立した方法を使った」と書くには、帯から出た波が目標どおりかを B1 で測る必要がある。
5. **判定は走らせる前に決める。** 案（§5.5）：速さの誤差 1 % 以内（周期 7 秒の成分が 400 m 進む間の位相の誤差 0.3 rad に当たる【計算】）、高さの減り 3 波長で 5 % 以内（FLIP39 が仕組みの効きとして示した最小の差 +11 % の半分より小さく）、など。数は理由と一緒に置いたが、決めるのは利用者。
6. **時間の見積もり**：B1 は 3.5〜12.5 時間、B2 は 1〜6 時間、B3 は 1.5〜4 時間（データの準備を除く）。合わせて 6〜22 時間前後で、1 本 30 分以内の区切りに分けられる【推定】（§4・§5）。
7. **後に回すもの**：向きが曲がる効果（屈折）の Berkhoff ら（1982）は 3D で 7〜20 時間以上かかる見込み【推定】で、FLIP39 E3 の「屈折で +20 %」を使い続ける時に要る。崩れ（Ting & Kirby、Grilli ら）と集まる群（Rapp & Melville、CCP-WSI）は、崩れ方や集まり方を主張する段で要る（§6）。
8. **PIC・FLIP 系で波の水槽を確かめた先例はある**（PICIN：Kelly・Chen・Zang ら、TU Delft の Maljaars ら）が、Houdini の FLIP（APIC の受け渡し、粒子の帯）を確かめたものは見つからなかった。自分たちの設定で確かめる必要がある【考え】。

## 1. 何を確かめるのか

### 1.1 指導教員の問いと、確かめの範囲

Q41 の答えの読み（[制作手順の Q41](../Workflow/Production_Workflow_ja.md) の扱い 2）：使っているシミュレーションが、水深で波の速さが変わる効果（深い所で速く、浅くなると遅く、高くなり、向きが曲がる）を正しく表すかは、方法を確かめるまで主張しない。確かめは、既に使われている基準の問題を借りて行う。

この文書の基準の問題では、水槽と海底の形を「測るための道具」として使う。実験の水槽と同じ使い方で、作品の場面に水槽や岩棚を置くことの理由にはならない（Q41 の扱い 1。場面の水深は [WindWaves_Kanagawa_ja.md](WindWaves_Kanagawa_ja.md) §5）【考え】。

### 1.2 速さの変わり方の大きさ

線形の分散の関係 ω² = g k tanh(kh)（ω は角周波数、k は波数、h は水深）で、波の速さ c = ω/k は kh が小さいほど水深に強く依る【文献：Dean & Dalrymple 1991】。

| 場面 | 周期 | 水深の変化 | 速さの比 | 浅水係数（高さの比） |
| --- | --- | --- | --- | --- |
| 前の試作（沖 60 m → 岩棚 26 m） | 8 s | 60 → 26 m | 0.94 | 0.94 |
| 同上 | 12 s | 60 → 26 m | 0.79 | 0.98 |
| 同上 | 16 s | 60 → 26 m | 0.73 | 1.07 |
| 神奈川沖の風の波（WindWaves_Kanagawa_ja.md §5） | 7 s | 40 → 15 m | 0.89 | 0.92 |
| 同上 | 7 s | 40 → 8 m | 0.72 | 0.94 |
| 同上 | 10 s | 40 → 8 m | 0.57 | 1.09 |

【計算】`b_theory_numbers.json` の `depth_change`。

確かめる kh の範囲：前の試作の群（周期 7.5〜21.8 秒、水深 26〜60 m）は kh 0.5〜4.3、神奈川沖の風の波（周期 5〜8 秒、水深 15〜40 m）は kh 1.2〜6.4（WindWaves_Kanagawa_ja.md §5.3）。両方を覆うには kh 0.5〜6 前後を確かめる必要がある【計算・考え】。

## 2. 今の作り方で、まだ確かめていないこと

### 2.1 測った事実：C1 で、短い成分が遅く弱くなった

FLIP39 E の造波の較正 C1（板の水槽 12 m 幅、水深 60 m・岩棚、粒子 1 m・格子 2 m、32 成分の群、各成分の振幅 0.085 m、合わせた焦点の線形の頂 2.72 m）【測った：`Unity/Build/FLIP39/E/record_ja.md` §4.1】：

| x (m) | 160 | 200 | 300 | 400 | 480 | 520 | 540 | 556 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 実効値の比（計算 ÷ 線形） | 1.04 | 1.04 | 0.95 | 0.82 | 0.79 | 0.65 | 0.62 | 0.68 |

- 帯を出た所（160〜200 m）では目標どおりだったが、進むにつれて線形の見込みから離れた。
- 1.05〜1.3 fc の帯の振幅は x 200→400 m で 0.69 倍（線形 0.95 倍）、1.3〜1.6 fc の帯の群の遅れは計算 21.5 s・線形 16.5 s。
- 頂が最も高くなったのは設計の焦点より 108 m 沖・6.7 秒早い。

この読みは帯ごとの包絡の重心で測った粗い値である（記録にそう書かれている）。また、短い成分の波長と格子の比は次のとおりで、細かさの不足が原因の候補になる【計算】：

| 周期 | 水深 60 m の波長 | 格子 2 m での格子の数 | 格子 0.6 m（FLIP39 R） |
| --- | --- | --- | --- |
| 7.5 s（群のいちばん短い成分） | 88 m | 44 | 146 |
| 12 s（中心） | 212 m | 106 | 354 |
| 5 s（神奈川沖の短い側、水深 25 m） | 39 m | 19.5 | 65 |

各成分の振幅 0.085 m は格子 2 m の 1/24 で、1 成分ずつ見ると格子より小さな波を運んでいる。

### 2.2 方法の中身で、速さと減りに効きうる所

| 所 | 今の設定 | 確かめた範囲 |
| --- | --- | --- |
| 造波の帯 | 水平の流速（x・z）だけを、目標の線形の波の流速へ Jacobsen らの重みで寄せる。縦の流速と水面は寄せない | 帯を出た波の高さ 95 %（FLIP37 P0）・1.04 倍（C1）。位相と速さは測っていない |
| 粒子の帯（narrow band） | 水面から 4 格子だけ粒子を置き、深い所の流速は格子で持つ | 受け渡しの誤り（深い格子の流速が 0 から始まる）を FLIP39 で直した。速さへの効きは未確認 |
| 流速の受け渡し | APIC | 未確認 |
| 時間の刻み | 24 コマ/秒、最大 2 小刻み（周期 12 秒で 1 周期 288〜576 刻み） | 未確認 |
| 格子 | 2 m（E）、0.6 m（R）、0.5 m（P3） | 細かさを変えた比べはしていない |

【道具を読んだ：`flip39/e_build_tank.py`・`e_tanklib.py`】。FLIP37 P0 は、静かな水、小さな波の減り（周期 14 秒・高さ 3 m・格子 0.7 m で 2 波長あたり 0〜4 %）、吸う帯の跳ね返り（0.2〜3.8 %）、区切った計算の再開を確かめたが、速さは測っていない【測った：`Unity/Build/FLIP37/P0/record_ja.md`】。

### 2.3 広く使われている計算の道具でも、簡単な問題で外れることがある

Larsen・Fuhrman・Roenby（2019）は、OpenFOAM の interFoam で、水深 0.4 m・周期 2 s・高さ 0.125 m の進む波（Ting & Kirby の崩れ波の入射波と同じ）を 100 周期進めた。初めの設定では水面が高くなり続け、20 周期前後で崩れた。クーラン数 0.15 では 5 周期後に頂の流速を 17 % 多く出し、0.05 では 0.1 %。25 周期後の位相のずれは、クーラン数 0.05 以下で 0°、0.15 で −36°、0.5 で −198° だった【文献】。設定ひとつで速さと高さが大きく変わる例で、Houdini の FLIP でも同じ確かめが要る理由になる【考え】。

## 3. 基準の問題の一覧

各項：何を比べられるか／設定／測る量／公表の値とデータの場所／この PC での小さな再現の時間（§4 の元から見積もった【推定】）／注意。

### 3.1 一定の水深での分散（Airy の線形波）と Stokes の 2 次

- 何を比べられるか：波の速さ（位相の速さ）と群の速さが、kh に対して線形の式どおりか。数値の分散（格子・時間の刻みで速さがずれること）と数値の減りを、理論だけを相手に測れる。水深で速さが変わることの、いちばん基本の形。
- 設定：平らな底の 2D の水槽、規則波。険しさ H/L を小さく（0.01 前後、ka 0.03）すると、振幅による速さの変化は 0.05 % 前後で無視できる【計算：深い海の Stokes の 3 次の補正 (ka)²/2】。kh を 0.5〜6 の範囲で数点とる。
- Stokes の 2 次：険しい波（H/L 0.04 前後）では、頂が尖り谷が平たくなる。拘束された 2 倍の波の振幅 a2 = k a² cosh(kh)(2 + cosh 2kh)/(4 sinh³ kh) と比べる【文献：Dean & Dalrymple 1991】。2 次では速さは変わらないので、険しい波の速さを比べるなら、もっと高い次数の解（流れ関数の方法：Rienecker & Fenton 1981、Fenton 1985 の 5 次）を相手にする。
- 線形の式で波を起こす時の注意：造波の目標を線形の式で与えると、拘束された 2 倍の波のほかに、自由な 2 倍の波が出て、空間でうなりを作る（板を動かす造波で Madsen 1971 が示した。帯で寄せる時も同じ形の問題が出る見込み【考え】）。うなりの長さ Lb = 2π/|k(2ω) − 2k(ω)| は、周期 12 秒・水深 60 m で 119 m、周期 7 秒・水深 25 m で 39 m【計算】。高さを 1 か所で測ると、このうなりを速さや減りと取り違えるので、波長の数倍にわたって並べて測る。
- 測る量：水面計を 1 波長おきに 3〜4 波長並べ、規則になった区間で、(1) 時刻のずれから速さ、(2) 空間の写しから波長、(3) 高さの減り、(4) 2 倍・3 倍の周波数の振幅。入る波と跳ね返った波の分け方は Goda & Suzuki（1976）の 2 点の方法や Mansard & Funke（1980）の 3 点の方法が標準【文献】。
- 公表の値：式そのもの。データのダウンロードは要らない。
- 細かさの目安（文献）：Windt ら（2019）の OpenFOAM の比べでは、波高あたり 10 格子で波の高さが 0.01 % の桁まで収束し、時間は 1 周期 400 刻みで収束した【文献】。今の FLIP の格子 2 m は、C1 の群の頂（帯を出た所で 1.82 m）に対して 1 格子前後である【計算】。
- 小さな再現の時間：1 本 2 分〜2.7 時間（周期と細かさで変わる。§5.2 の表）。
- 注意：Houdini の FLIP は粘性と表面張力を入れない設定で使っているので、フルード則（長さを s 倍すると時間は √s 倍）で縮尺を変えても同じ問題になる【考え】。

### 3.2 ゆるい斜面での浅水変形

- 何を比べられるか：水深が変わる所で、速さが場所ごとの水深の値に付いていくか（指導教員の言う効果そのもの）。高さは線形の浅水係数 Ks = √(cg0/cg)（cg は群の速さ）と比べる【文献：Dean & Dalrymple 1991】。
- 設定：沖の平らな底 → ゆるい斜面 → 浅い平らな底 → 吸う帯。線形の浅水係数は斜面がゆるい前提で、緩斜面方程式は 1:3 程度まで良いとされる（Booij 1983）【文献】。今の岩棚の 1:4 は境目で、跳ね返りが出るので、ゆるい斜面（1:30 前後）で確かめるのがよい【考え】。
- 測る量：x ごとの速さ（時刻のずれ、または位相の傾き）、高さ、斜面の上まで着く時刻。例：周期 7 秒、水深 40 → 8 m、1:30（長さ 960 m）では、位相が斜面を上る時間は 94.7 秒で、水深 40 m のままなら 88.1 秒。差 6.6 秒（0.94 周期）が水深の効果【計算：`slope_travel`】。周期 10 秒では 78.9 秒対 65.6 秒で差 13.3 秒。
- 公表の値（実験）：Hansen & Svendsen（1979、デンマーク工科大学 ISVA の Series Paper 21）がゆるい斜面での規則波の高さ・速さ・形を測った。水深 0.36 m、例えば周期 2 s・振幅 0.018 m、周期 3.33 s・振幅 0.0215 m の組がある【文献：arXiv 1902.03021 の要約】。斜面の勾配は二次資料で 1:32.26 と約 1:35 に分かれ、速さの値には正誤表がある【文献】。報告書はオンラインで見つからなかった（§9）。
- 小さな再現の時間：理論との比べで 1 本 30 分〜3 時間（§5.3）。Hansen & Svendsen の再現は 2D の実験の縮尺で 1〜3 時間、ただし報告書の入手が先。
- 注意：浅い所で高さ / 水深が 0.1 を超えると線形の式から離れる（アーセル数が大きくなる）。高さを小さくすると格子に対して波が小さくなるので、B1 の結果で細かさを決めてから走らせる【考え】。

### 3.3 潜堤の上の波の変形（Beji & Battjes 1993 ほか）

- 何を比べられるか：水深 0.4 m から 0.1 m へ上る斜面で、波が浅くなって尖り、拘束された高い周波数の成分（2 倍・3 倍の波）が育ち、深くなる斜面でそれが自由な波として放たれて、波の形が崩れていく様子【文献：Beji & Battjes 1993】。非線形と分散の両方を、水深の変化と一緒に試す問題として、数値の水槽の確かめに広く使われている（例：Saincher & Banerjee の確かめ、PICIN の 2D の確かめ、Basilisk の試験）【文献】。放たれる 2 倍の波は kh 1.69、3 倍の波は kh 3.56 になり、入射波（kh 0.67）・堤の上（0.32）と合わせて、kh 0.3〜3.6 を一つの問題で通る【計算】。この範囲は前の試作と神奈川沖の波の範囲（§1.2）の大半に重なる。
- 設定（二次資料で一致している所）：水路の水深 0.4 m。x 6 m から 1:20 で上り、堤の頂の水深 0.1 m（12〜14 m）、14 m から 1:10 で下る（17 m で 0.4 m）。造波はサーボ制御のピストン板。規則波と JONSWAP の不規則波【文献：arXiv 1912.01905、Basilisk の bar.c ほか】。
  - よく使われる組：Case A（周期 2.02 s・高さ 2 cm、崩れない）。Bigoni ら（arXiv 1410.6338）は「Beji & Battjes の Case A、測定は Luth ら（1994）」として、水面計 4.0・10.5・13.5・14.5・15.7・17.3・19.0・21.0 m を使っている【文献】。
  - 崩れる組：規則波 周期 2.5 s・高さ 0.054 m（巻いて崩れる）、不規則波 Hs 0.049 m・Tp 2.5 s【文献：arXiv 1912.01905】。Luth ら（1994）の B1-r（周期 1.01 s・高さ 41〜59 mm）・B3-r（2.525 s・24〜40 mm）も使われている【文献：Derakhti ら arXiv 1911.06896】。
  - 水面計の位置は資料で違う（Beji & Battjes 1993 の 8 本：6・11・12・13・14・15・16・17 m。Luth ら・Dingemans の組：10.5〜21 m）。**どちらのデータと比べるかを先に決める必要がある。**
- 測る量：各水面計の時刻の水面。1・2・3 倍の周波数の振幅と位相。
- 公表の値とデータの場所：
  - 原典の図（Coastal Engineering 19, 151–162。出版社の有料の頁）。Ifremer の WAVEWATCH III 文献集に写しの PDF があるが、読む道具は 403 で断られた（§9）。
  - Basilisk（流体の計算の道具）の試験 `src/test/bar.c` に、水面計 4〜11（x 10.5〜21 m）の測った値が数のファイル `gauge-4`〜`gauge-11` として付いている。1 本は 2 列（時刻 33.07〜38.85 s と水面。単位は書かれていないが、図では水面を 100 倍して cm で描いている）× 34 行で、1 本 1 KB 前後、8 本で 6 KB 前後【文献：Basilisk の頁を読んだ。出どころの記載はない】。ダウンロードには利用者の許可が要る。
  - 原データは Beji 氏から提供を受けた例がある（arXiv 1912.01905 の謝辞）【文献】。Luth ら（1994）・Dingemans（1994）は Delft Hydraulics の報告書で、オンラインの置き場は見つからなかった。
  - 公表の報告には較正の詳細と測定の誤差が書かれていない、と指摘されている【文献：Bigoni ら】。Basilisk の例では、最初の水面計（4 番）に合うように造波の振幅を調整している【文献】。
- 小さな再現の時間：2D の板。高さあたり 1.5 格子（今の E の細かさに当たる）で 10〜30 分、5 格子（R に当たる）で 1〜3.5 時間。データの準備に 1〜2 時間【推定。§5.4】。
- 注意：PICIN の 2D の確かめ（Chen ら 2016）の基準の一つも「潜堤の上の浅水変形」である【文献：要旨。どの実験かは要旨では確かめられなかった】。

### 3.4 楕円の浅瀬による屈折の集中（Berkhoff ら 1982）

- 何を比べられるか：斜めの斜面の上の楕円の浅瀬で、波が曲がって浅瀬の後ろに集まり高くなる様子（屈折と回折）。指導教員の言う「向きが曲がる」効果と、FLIP39 E3 の「波長と同じ幅の盛り上がりの屈折で +20 %」の確かめに当たる【考え】。
- 設定（二次資料）：20 m × 22 m の水槽、1:50 の斜面を 20° 回し、基準の水深 0.45 m。浅瀬は回した座標で (x/4)² + (y/3)² ≤ 1 の範囲。規則波 周期 1 s・振幅 0.0232 m【文献：Duran & Marche arXiv 1604.05227 の要約】。浅瀬の厚さの式は二次資料の式のまま未確認。後の CERC の実験（Vincent & Briggs 1989）は寸法が違う別の浅瀬なので混ぜない【文献】。
- 測る量：断面 1〜8 の上の波の振幅の比（入射波に対する）【文献】。
- 公表の値とデータの場所：原典（Coastal Engineering 6, 255–279、有料）の図。Delft Hydraulics の報告 W154 第 8 部（74 頁）の目録がある（同じ浅瀬かは未確認）。Basilisk の例 `src/examples/shoal-ml.gpu.c` がこの実験を再現しようとしている（造波の振幅は測定に合わせて調整）【文献】。数のデータの公開は見つからなかった。
- 小さな再現の時間：3D。高さあたり 1.5 格子（格子 3 cm）で格子 880 万・粒子 1,500 万前後になり、FLIP39 R と同じ桁。1 周期 100〜300 刻みで 7〜20 時間、細かくすると数日【推定】。
- 注意：振幅 2.3 cm の波を格子 3 cm で運ぶことになる。B1 で「格子より小さな波の速さと減り」を確かめてからでないと、結果を読めない【考え】。

### 3.5 斜面での崩れ（Ting & Kirby、Grilli ら、崩れ始めの指標）

- Ting & Kirby（1994・1995・1996）：水深 0.4 m の平らな底から 1:35 の斜面。崩れ波（spilling）は沖の高さ 0.125 m・周期 2.0 s、巻き波（plunging）は崩れる時の高さ 0.128 m 前後・周期 5 s。容量式の水面計で高さの減りと平均の水位の上がり、光ファイバーのレーザー流速計で戻り流れと乱れを測った【文献】。周期 2 s の波は kh 0.68、5 s は 0.26【計算】。
  - データ：論文の図（Coastal Engineering 24、27。有料）。Ifremer の文献集に 1994 年の写しがあるが読めなかった。数のデータの公開は見つからなかった。
  - 先例の細かさ：DualSPHysics（SPH）での再現は粒子 5 mm 以下でほぼ変わらず、2 mm（2D で 122 万粒子）を使った【文献：arXiv 2002.00827】。
  - 小さな再現の時間：2D の板で 1 本 2〜6 時間（崩れる所で流速が上がり刻みが細かくなる）【推定】。
- Grilli・Svendsen・Subramanya（1997）：孤立波を 1:100〜1:8 の斜面で計算（実験で確かめた完全非線形のポテンシャル流のモデル）し、斜面のパラメーター S0 = 1.521 tanβ / √(H/h) で崩れ方を分けた：崩れ波 S0 < 0.025、巻き波 0.025〜0.30、寄せ波（surging）0.30〜0.37。12° より急な斜面では崩れない【文献：要旨と arXiv 1911.06896 の引用】。0.37 より大きいと崩れない、という読みは原典で確かめていない。崩れる時の高さ・水深・速さの式もある（係数は原典で確かめる）。
  - 既存の記録との照合：FLIP37 P1 の孤立波 2 本（計算の名前 `SW1_h20_Hs9_n15`・`SW2_h20_Hs9_n4` を水深 20 m・高さ 9 m と読んだ）は、1:15 で S0 0.15（巻き波の範囲）、1:4 で 0.57（寄せ波の範囲より大きい）で、記録の「1:15 で巻き、1:4 で駆け上がった」と分け方が合う【計算・測った】。
  - 小さな再現の時間：FLIP37 P1 の孤立波は 1 本 3〜4 分だった【測った】。斜面と高さを変えて 6 本で 1 時間前後【推定】。
- 崩れ始めの指標：頂の水の水平の速さ u と頂の進む速さ c の比 B = u/c が 0.85 前後を越えると崩れに進む（深い海〜中間の水深で 0.85〜0.86、浅い海で 0.85〜0.88）【文献：Barthelemy ら 2018、Derakhti ら arXiv 1911.06896】。FLIP37・FLIP39 の解析は既に B > 0.85 を使っている。

### 3.6 集まる波の群と、その崩れ（Rapp & Melville、CCP-WSI）

- Rapp & Melville（1990）：深い海の波の分散を使い、成分の位相をそろえて決めた場所・時刻に一つの崩れる群を作った。群から失われた運動量とエネルギーの流れは、一つの崩れ波で 10 %、巻き波で 25 % まで。失われたエネルギーの 9 割以上は 4 周期の中で消えた。結果は群の中心周波数でよくそろった【文献：要旨】。後の再現の表（Derakhti ら 2018）では、水深 0.60 m、32 成分、中心周波数 0.88 Hz、帯域 Δf/fc 0.75、険しさ S 0.30 の組が使われている【文献】。崩れ始めの険しさ（線形の焦点の傾き S）は、Sinnis ら（2021、水深 0.5 m、中心 0.85〜0.90 Hz、帯域 0.77〜1.19）で 0.29〜0.31 だった【文献】。
  - 何を比べられるか：群が設計した場所・時刻に集まるか（分散の速さが正しいかの総合の試験。C1 のずれはここに出た）、崩れ始めの S、崩れで失われるエネルギーの割合。
  - データ：原典の図（UCSD の Air-Sea 研究室の頁に PDF があるが 10 MB を超え、読む道具の上限を越えた）。数のデータの公開は見つからなかった。
  - 小さな再現の時間：2D の板で 1 本 1〜3 時間【推定】。
- CCP-WSI Blind Test Series 1（Ransley ら 2019）：プリマス大学 COAST 研究所の海洋水槽（35 m × 15.5 m、フラップ式の造波板 24 枚）。造波板の所の水深 4 m から斜面で、作業の所は 2.93 m。JONSWAP のスペクトルに NewWave の考えを当てて頂をそろえた群（崩れない）で、kA 0.13〜0.21（Hs 0.077〜0.103 m、Tp 1.362〜1.456 s）、向き 0・10・20°。参加者に先に渡されたのは、構造物のない水槽の水面計の記録だけ（128 Hz）【文献】。
  - 参加した 10 のコードの一つが PIC（PICIN）で、ピストン板を NewWave と 1 次の造波板の理論で動かして波を起こし、吸うのは緩和の帯。格子 0.025 m の一様な格子に 1 升 8 粒子、格子 約 1,600 万・粒子 約 1 億 500 万、クーラン数 0.5【文献】。
  - 結論：どのコードも全体としてよく予測したが、似た方法の間でもばらつきが目立った。崩れない穏やかな場合なので、どれだけ細かい方法が要るかは決められなかった【文献】。
  - データ：http://www.ccp-wsi.ac.uk/blind_test_series_1 （論文に書かれた置き場）、目録 https://ccp-wsi.ac.uk/catalogue/test_cases/test_case_003 。大きさと使用条件は頁が読めず確かめられなかった。
  - 小さな再現の時間：向き 0° の水槽の記録だけなら 2D の板で 1〜3 時間【推定】。
  - 水深 2.93 m で Tp 1.456 s は kh 5.6 の深い海の群で、水深の効果の試験にはならない【計算】。

### 3.7 PIC・FLIP 系の数値水槽の確かめ（先例）

| 文献 | 方法 | 確かめた問題 | 分かること |
| --- | --- | --- | --- |
| Kelly・Chen・Zang（2015）SIAM J. Sci. Comput. | PICIN：粒子が流れを運び、格子で圧力を解く PIC。固体と水の双方向の結合 | 2D の三つの例を他の研究者の数値結果と比べた | PIC で自由水面の流れを解く元の論文。正誤表あり（2 番目の例の CPU 時間は 12 秒ぶんで 1,200 秒、Δx = H/60）【文献】 |
| Chen・Kelly・Dimakopoulos・Zang（2016）Coastal Engineering | PICIN の 2D に造波と吸う仕組みを足した | 潜堤の上の浅水変形、低い構造物の越波、ダム崩壊による越流 | 「少ない計算資源で」波の伝わり・衝撃・越波を表せた、と要旨【文献】 |
| Chen・Zang・Kelly・Dimakopoulos（2018）Ocean Engineering | PICIN の 3D・並列 | 規則波・集まる群・孤立波と円柱 | 実験と VOF のコードと比べ、計算の速さは格子だけの方法と同じ程度【文献】 |
| Chen・Kelly・Zang（2019）Ocean Engineering | 緩和の帯で吸う方法の調べ | 波の種類ごとの吸い方 | 少し変えると帯の長さを約半分にできた【文献】 |
| Chen ら（2015）IWWWFB 30 | PICIN | 板の造波で起こした波（周期 1.3 s・高さ 0.15 m）と動くケーソン | 格子 0.013 m、6.4 万粒子、15 秒ぶんに 1 コアで 1.4 時間【文献：要旨の PDF を読んだ】 |
| Maljaars・Labeur・Möller・Uijttewaal（2017、TU Delft） | FLIP を元にした粒子と格子の方法 | 定在波、平らな底と斜面の上の孤立波の生成と伝わり | 定評のある SPH の結果と比べた【文献：要旨】 |

Houdini の FLIP を波の水槽として確かめた論文は見つからなかった。Houdini は流速の受け渡しに APIC を選べ、水面の近くだけに粒子を置く帯を持つなど、上の方法と中身が違う。先例は「PIC・FLIP 系でも確かめれば使える」ことの裏づけにはなるが、私たちの設定の確かめの代わりにはならない【考え】。

### 3.8 波の起こし方：緩和の帯と、板を動かす造波

- 緩和の帯（Jacobsen・Fuhrman・Fredsøe 2012、waves2Foam）：帯の中で、計算の値と理論の値を重み w(χ) = 1 − (exp(χ^3.5) − 1)/(exp(1) − 1) で混ぜる。造波にも吸うのにも使える。論文は伝わりと崩れの二つの基準の問題で示し、出口の帯の跳ね返りを条件ごとに調べた【文献：要旨、重みの形と指数 3.5 は arXiv 1810.03492 の引用】。崩れの例は浜の断面の上の崩れ（どの実験かは全文で確かめていない）。
- 板を動かす造波：実験の水槽と同じく、壁を動かして波を起こす。ピストン板の動きの幅 S と遠くの波の高さ H の比は Biésel の式 H/S = 2(cosh 2kh − 1)/(sinh 2kh + 2kh)【文献：Biésel & Suquet 1951、Dean & Dalrymple 1991】。周期 7 秒・水深 25 m で 1.73、周期 12 秒・水深 60 m で 1.57【計算】。板の近くには減衰する波が出る。
- 比べ（Windt・Davidson・Schmitt・Ringwood 2019、OpenFOAM）：緩和の帯、境界の流速で起こす方法（olaFlow・OpenFOAM）、板を動かす方法、運動量の源、吸う浜を同じ指標で比べた。海の状態は深い海の規則波（周期 8 s・高さ 1.5 m・水深 70 m、Stokes 2 次）、浅い海の規則波（周期 19 s・高さ 1.5 m・水深 7 m、クノイド波）、JONSWAP（Tp 8 s・Hs 1.5 m）【文献】。
  - 緩和の帯と境界の方法の波の高さの誤差は 1 % の桁。
  - 造波の所で跳ね返りを吸えるかの試験（定在波）では、緩和の帯の誤差 2.7 ± 2.1 % に対し、板を動かす方法は 80.5 ± 23.5 %。決めた動きをなぞるだけで、跳ね返ってきた波に応じて動きを変えないため。
  - 緩和の帯は全体に良いが計算が重い。板を動かす方法は格子あたりの計算がいちばん重かった。
  - これらの誤差は、実験の水槽の水面計の精度（0.5 mm）と同じ桁だった。
- 意味（Q41 の扱い 4 への材料）：緩和の帯も板も、計算の範囲の外で既にできた波が入ってくることを与える境界の条件で、水の中に力を足すものではない【考え】。帯が表すのが「遠くで風に起こされて入ってくる波」かどうかは、帯に与える波（スペクトル・周期・高さ）が、その海の風と吹送距離から決まるかで決まる。それは [WindWaves_Kanagawa_ja.md](WindWaves_Kanagawa_ja.md) §4.3 の扱い【考え】。
- 今の帯との違い：§0 の 4。帯の出口の波の高さ・位相・速さを目標と比べることが、Windt らの指標（目標の高さとの差）の形でそのまま確かめになる。

### 3.9 一覧

| 基準の問題 | 見る効果 | 相手 | データ | 小さな再現（この PC）【推定】 |
| --- | --- | --- | --- | --- |
| 一定の水深の分散・Stokes 2 次 | kh ごとの速さ・減り・形 | 理論の式 | 要らない | 1 本 2 分〜2.7 時間、組で 3.5〜12.5 時間 |
| ゆるい斜面の浅水変形 | 速さが水深に付いていくか、高さ | 線形の浅水係数（実験は Hansen & Svendsen） | 理論は要らない。実験は報告書が要る | 1〜6 時間 |
| 潜堤（Beji & Battjes 1993・Luth ら 1994） | 水深の変化による非線形と分散の変形（kh 0.3〜3.6） | 測った時系列 | 図、Basilisk の数のファイル 6 KB 前後、原典の著者 | 1.5〜4 時間＋準備 1〜2 時間 |
| 楕円の浅瀬（Berkhoff ら 1982） | 屈折・回折の集中 | 測った振幅の比 | 図 | 3D で 7〜20 時間以上 |
| 斜面での崩れ（Ting & Kirby） | 崩れる位置・高さの減り・水位・戻り流れ | 測った値 | 図 | 1 本 2〜6 時間 |
| 孤立波の崩れの分け方（Grilli ら 1997） | 崩れるか、崩れ方 | 式 | 要らない（係数は原典） | 6 本で 1 時間前後 |
| 集まる群の崩れ（Rapp & Melville 1990） | 集まる場所・時刻、崩れ始めの S、失うエネルギー | 測った値 | 図 | 1 本 1〜3 時間 |
| CCP-WSI BT1 の水槽の記録 | 集まる群の伝わり（深い海） | 測った時系列 | CCP-WSI の置き場（条件未確認） | 2D で 1〜3 時間 |
| ピストン板の造波 | 板の動きと波の高さ | Biésel の式 | 要らない | 0.5 時間前後 |

## 4. 時間の見積もりの元

既存の計算の記録（`Unity/Build/FLIP37/runs.jsonl`・`Unity/Build/FLIP39/runs.jsonl`）から、計算 1 秒ぶんに掛かった壁時計の秒を出した【測った】：

| 計算 | 粒子の間隔（格子） | 水槽 | 1 秒ぶんの壁時計 |
| --- | --- | --- | --- |
| FLIP39 E1（板） | 1 m（2 m） | 806 m × 幅 12 m、水深 60 m | 5.5 秒（2,305 コマ・96 秒ぶんに 500〜530 秒） |
| FLIP37 P1（板） | 0.5 m（1 m） | 806 m × 幅 2.8 m | 7〜32 秒（設定の違いで幅がある） |
| FLIP37 P0 T2（板） | 0.35 m（0.7 m） | 1,000 m × 幅 8 m | 37 秒（40 秒ぶんに 24.8 分） |
| FLIP37 P1 B025（板） | 0.25 m（0.5 m） | 806 m × 幅 2.0 m | 86 秒 |
| FLIP39 E2・E3（3D） | 1 m（2 m） | 806 × 240 m | 73〜100 秒 |
| FLIP39 R（3D の箱） | 0.3 m（0.6 m） | 270 × 100 m | 約 380 秒（1 コマ 15〜16 秒） |

見積もりの仮定【推定】：

- 板の水槽の費用は水槽の長さに比例し、粒子の間隔を半分にすると 1.3〜6 倍（0.5 m）、4〜16 倍（0.25 m）になる（上の表の幅のまま）。板の幅を格子 6 個に保てば、粒子と格子の数はおおむね 1/格子 に比例する見込みだが、P1 の実測はそれより重かったので、幅をとった。
- 時間の刻みは 1 周期 300 刻み以上（Windt らは 1 周期 400 刻みで収束を確かめた）。今の 24 コマ/秒・最大 2 小刻みは、周期 5 秒で 120〜240 刻み、周期 12 秒で 288〜576 刻みに当たる。周期の短い問題では、コマの数か小刻みを増やす必要がある。実験の縮尺（周期 1〜2 秒）で走らせる時は、周期あたりの刻みが同じになるようにコマの数を決める。
- 実験の縮尺の問題の費用は、縮尺によらず「格子と粒子の数 × 刻みの数」で決まる（粘性も表面張力も入れないので）。
- 重い計算は一度に一つ、1 回の起動は 30 分以内で区切り、途中保存から続ける（今までの決まりのまま）。

## 5. 勧める最小の組

### 5.1 なぜこの三つか

- B1（一定の水深の分散）：指導教員の「深さに応じて速度は変化する」は、まず ω² = g k tanh(kh) のことである。今の FLIP がこの式を、使う予定の細かさで、どの kh まで誤差いくつで表すかを数で出す。C1 で見えたずれ（§2.1）が、細かさ・粒子の帯・刻みのどれから来るかもここで切り分ける。相手は式なので、データの入手を待たずに始められる。
- B2（ゆるい斜面の浅水変形）：水深が場所で変わる時に、速さが場所ごとの水深の値に付いていくかを見る。「水深の効果が反映されるか」の直接の答えになる。相手は式。
- B3（Beji & Battjes の潜堤）：先人が数値の波のモデルを確かめるのに使ってきた実験で、測った値と比べる（指導教員の「先人の知恵を借ります」に当たる）。水深の変化が非線形と分散を通して波の形を変える所まで含み、kh 0.3〜3.6 を一つの問題で通る。
- 屈折（Berkhoff）は 3D で重く、B1 で格子より小さな波の振る舞いが分かってからでないと読めないので、次の段に回した（§6）。

### 5.2 B1：一定の水深の分散

水深 25 m（神奈川沖の点の値の中ほど。WindWaves_Kanagawa_ja.md §5.2）の平らな底の板の水槽で、規則波を起こす。高さは H/L 0.01（振幅による速さの変化を無視できる大きさ）。

| 周期 | kh | 波長 | 格子 2 / 1 / 0.5 m での波長あたりの格子 | 水槽（6 波長） | 計算する長さ（4 波長を群の速さで進む時間＋6 周期） | 1 本の時間（格子 2 m / 1 m / 0.5 m）【推定】 |
| --- | --- | --- | --- | --- | --- | --- |
| 5 s | 4.03 | 39 m | 19.5 / 39 / 78 | 234 m | 70 s | 2 分 / 2〜11 分 / 7〜29 分 |
| 7 s | 2.11 | 74 m | 37 / 74 / 149 | 446 m | 92 s | 5 分 / 6〜27 分 / 19〜73 分 |
| 10 s | 1.20 | 130 m | 65 / 130 / 261 | 782 m | 116 s | 10 分 / 13〜60 分 / 41 分〜2.7 時間 |
| 20 s | 0.52 | 300 m | 150 / 300 / 600 | 1,800 m | 207 s | 42 分 / 54 分〜4.1 時間 / （走らせない） |

【計算：`speed_table`。時間は §4 の元から】

- 高さ H/L 0.01 は、周期 5・7・10・20 秒で 0.39・0.74・1.3・3.0 m。格子 2 m では周期 5〜10 秒の波が格子より低い。C1 の成分（0.085 m）と同じく「格子より小さな波を運べるか」を、ここで一緒に確かめることになる【計算・考え】。
- 足す 1 本：周期 7 秒・H/L 0.05（高さ 3.7 m、神奈川沖の嵐の波の険しさに近い）を格子 1 m で。速さは流れ関数の解（Rienecker & Fenton 1981）と、形は Stokes 2 次と比べる。
- 原因の切り分け（C1 のずれ）：いちばん外れそうな周期 5 秒・格子 2 m で、一つずつ変える：粒子の帯 4 → 12 格子、最大の小刻み 2 → 4、受け渡し APIC → FLIP。3 本 × 2〜5 分。
- 任意：前の試作の結果を読み直すため、水深 60 m と 26 m の周期 12 秒を格子 2 m で（20 分＋14 分）。速さの比 0.79（§1.2）を FLIP が何 % で出すかを見る。
- 測り方：水面計を 1 波長おきに並べ、規則になった区間で、時刻のずれから速さ、空間の写しから波長、高さの減り、2・3 倍の周波数の振幅を出す。帯を出た所の高さと位相を目標と比べる。3 つの細かさ（比 2）から観測された収束の次数と、格子による誤差の目安 GCI を出す（Celik ら 2008 の手順）。
- 合わせて 15 本前後、3.5〜12.5 時間【推定】。

### 5.3 B2：ゆるい斜面の浅水変形

水深 40 m の平らな底 → 1:30 の斜面（960 m）→ 水深 8 m の平らな底 → 吸う帯。周期 7 秒と 10 秒、沖の高さ 1 m。

| 周期 | 速さの比（8 m ÷ 40 m） | 浅水係数 | 位相が斜面を上る時間（40 m のままなら） | 水槽 | 1 本の時間（格子 2 m / 1 m）【推定】 |
| --- | --- | --- | --- | --- | --- |
| 7 s | 0.72 | 0.94 | 94.7 s（88.1 s、差 6.6 s） | 約 1,330 m | 30 分 / 40 分〜3 時間 |
| 10 s | 0.57 | 1.09 | 78.9 s（65.6 s、差 13.3 s） | 約 1,590 m | 31 分 / 40 分〜3 時間 |

【計算：`depth_change`・`slope_travel`】

- 細かさは B1 の結果で決める（B1 で 1 % を満たした細かさ）。合わせて 1〜6 時間【推定】。
- 浅い所の高さ / 水深は 0.12〜0.14 で、線形の式からの離れが少し出る。周期 10 秒の水深 8 m でアーセル数 16 前後【計算】。高さは線形の浅水係数のほか、流れ関数の解でも比べる。

### 5.4 B3：Beji & Battjes の潜堤（Case A）

- 周期 2.02 s・高さ 2 cm、崩れない組。比べる相手は Luth ら（1994）の水面計 4〜11（Basilisk に付いている数のファイル、または原典の図を読み取った値）。どちらを使うかは利用者が決める（ファイルを使うならダウンロードの許可が要る）。
- 縮尺：Houdini の既定の値（衝突の隙間など）が今と同じ桁で働くように、今の計算と同じ単位の大きさで走らせる案がある。フルード則で 150 倍にすると、水深 60 m、堤の頂 15 m、周期 24.7 s、高さ 3 m、上りの斜面 900〜1,800 m、水面計 1,575〜3,150 m になり、格子 2 m で高さあたり 1.5 格子（E と同じ）、0.6 m で 5 格子（R と同じ）になる【計算：`bb_scale150`】。実験の縮尺のままでも同じ問題になる。
- 細かさ：高さあたり 1.5 格子と 5 格子の 2 本。10〜30 分と 1〜3.5 時間【推定】。データの準備に 1〜2 時間。
- 測り方：最初の水面計（10.5 m）で造波の振幅と位相を合わせ（Basilisk の例と同じ扱い）、その先の水面計で比べる。

### 5.5 判定（案）：走らせる前に決める

| 問題 | 項目 | 案 | 理由 |
| --- | --- | --- | --- |
| B1 | 速さの誤差 \|c計算/c線形 − 1\| | 1 % 以内（使う細かさで） | 群が集まるには成分の位相のずれをそろえる必要がある。位相のずれ 0.3 rad（ばらばらなら焦点の頂が 4.4 % 下がる）を許すと、400 m 進む成分の速さの誤差は周期 7 秒で 0.9 %、周期 5 秒で 0.5 %、周期 12 秒（前の試作、406 m）で 2.5 %【計算：`phase_tol`】。§1.2 の水深の効果（6〜43 %）よりも十分小さい |
| B1 | 高さの減り | 3 波長で 5 % 以内 | FLIP39 が仕組みの効きとして示した最小の差（向きの集中 +11 %）の半分より小さくないと、数値の減りと仕組みの効きを見分けられない。FLIP37 P0 の前の判定（2 波長で 15 % 未満）より厳しくした |
| B1 | 帯から出た波 | 高さ ±5 %、位相 ±0.1 rad | 前の測った値（95 %・1.04 倍）と同じ桁を、上の減りの判定と同じ幅で見る。位相は今まで測っていない |
| B1 | 細かさの収束 | 3 つの細かさで GCI を出し、使う細かさの速さの GCI が 1 % 以内 | 速さの判定（1 %）を、細かさによる不確かさの中で言えるようにする |
| B2 | 斜面の上の速さ | 場所ごとの線形の値の ±2 % | 浅い所ほど高さ / 水深が大きく、線形の式から少し離れるので B1 より広げる |
| B2 | 斜面の上まで着く時刻 | ±0.5 秒 | 水深の効果（6.6 秒・13.3 秒）の 1 割より小さく |
| B2 | 高さ | 線形の浅水係数の ±3 % | 浅水係数の効き（−6 %・+9 %）の向きと大きさを見分けられる幅 |
| B3 | 主な頂の着く時刻 | ±0.05 周期 | 読み取ったデータは約 0.09 周期おきの点なので、それより細かくは判定できない |
| B3 | 1 倍の周波数の振幅 | 測った値の ±10 % | 図から読んだ値の読み取りの誤差（数 %）より大きく取る |
| B3 | 2・3 倍の周波数の振幅 | 堤の上と後ろの水面計で ±25 %、後ろで形が分かれるか | 高い周波数は振幅が小さく、読み取りの誤差が相対的に大きい。まずは「放たれる」が起きるかを見る |

数の幅は進行役の案。利用者が決め、決めた値を記録に書いてから走らせる。数値の波を使う前に、決めておいた合格の基準で確かめる考え方は、数値の波の共同研究（Reproducible Offshore CFD JIP の Qualification criteria、Fouques ら・Bouscasse ら 2021）にもある【文献：要旨。基準の数そのものは読めていない】。

### 5.6 順番と、止める所

1. B1 を格子 2 m で全周期（約 1 時間）。周期 5・7 秒の誤差が 1 % を越えたら、原因の切り分けの 3 本（約 15 分）。
2. B1 を格子 1 m・0.5 m で。0.5 m でも周期 5 秒の誤差が 1 % を越えるなら、そこで止めて利用者に報告する（「この方法と細かさでは、周期 X 秒より短い波の速さを誤差 1 % で表せない」という答えになる）。
3. 満たした細かさで B2。
4. B3（2 本）。
5. 結果を指導教員の流れ（目標 → 何を確かめたか → 結果 → 分かったこと）でまとめる。

いちばん短くするなら、B1 を格子 2 m と 1 m だけ（格子 1 m の周期 20 秒は省く）、B3 を細かい 1 本で、2.5〜6 時間前後【推定】。

### 5.7 この組で言えること・言えないこと

- 言えること（結果しだい）：使う細かさで、FLIP が kh 0.5〜4 の速さを何 % で表すか。水深が変わる所で速さと高さが式に付いていくか。公開の実験の水深の変化による形の変化を、どこまで再現するか。
- 言えないこと：崩れ（崩れる高さ・位置・崩れ方）、屈折による集中、風による波の育ち、3D の向きの広がり。これらは §6 の問題で別に確かめる。作品の場面に水槽や岩棚を置くことの正しさも、この組では答えない。

## 6. 後に回すもの

| 段 | 問題 | いつ要るか |
| --- | --- | --- |
| 屈折 | Berkhoff ら（1982）の楕円の浅瀬（3D、7〜20 時間以上） | FLIP39 E3 の「盛り上がりの屈折で +20 %」を主張し続ける時、または場面の海底の形で波を集める時 |
| 崩れ | Grilli ら（1997）の孤立波の分け方（1 時間前後）、Ting & Kirby（1994）の崩れ波・巻き波（1 本 2〜6 時間）、崩れ始めの B = u/c | 崩れる高さ・崩れ方を主張する時（FLIP39 では細かさで崩れ方が変わった） |
| 集まる群 | Rapp & Melville（1990）の組（1 本 1〜3 時間）、CCP-WSI BT1 の水槽の記録（1〜3 時間、データの条件の確認が先） | 分散で群を集める設計（FLIP39 E）を主張する時 |
| 造波 | ピストン板の造波を Biésel の式と比べる（0.5 時間前後）。緩和の帯を Jacobsen らの形（全成分の流速と水面を寄せる）に近づけた版と比べる | 「実験の造波板と同じ扱い」と言いたい時（Q41 の扱い 4） |
| 風 | WindWaves_Kanagawa_ja.md §4.4 の判定 | 風で波を起こす時 |

## 7. 決めていただくこと

1. 最小の組（B1・B2・B3）で進めてよいか。時間がない時の短い版（§5.6 の最後）にするか。
2. §5.5 の判定の数。
3. B3 で比べるデータ：Basilisk に付いている数のファイル（8 本、6 KB 前後。ダウンロードの許可が要る）か、原典の図の読み取りか、原典の著者への依頼か。
4. B1 の水深：神奈川沖に合わせた 25 m でよいか（場面の水深と周期は WindWaves_Kanagawa_ja.md §6 の決めごとと関わる）。
5. この結果を、指導教員へ「方法の確かめの計画」として先に見せるか（10/14 のゼミの資料の半日前までに出す決まり：Q40 の扱い 7）。

## 8. 限界と、読めた範囲

- 全文を読めたもの：Windt ら 2019、Ransley ら 2019（Aalborg 大学の写し）、Sinnis ら 2021、Chen ら 2015（IWWWFB の要旨）、arXiv 2002.00827（SPH の Ting & Kirby の再現）、Larsen ら 2019 の arXiv 版、Basilisk の bar.c。
- 要旨・二次資料だけのもの：Beji & Battjes 1993、Luth ら 1994、Dingemans 1994、Berkhoff ら 1982、Ting & Kirby 1994〜96、Grilli ら 1997、Rapp & Melville 1990、Jacobsen ら 2012、Kelly ら 2015、Chen ら 2016・2018・2019、Maljaars ら 2017、Hansen & Svendsen 1979、Derakhti ら（1911.06896）、Bigoni ら（1410.6338）、Duran & Marche（1604.05227）。設定の数は二次資料どうしで一致した所だけを書き、食い違う所（水面計の位置、Hansen & Svendsen の斜面）は食い違うと書いた。
- Ifremer の文献集（Beji & Battjes 1993、Ting & Kirby 1994、Grilli ら 1997 の写し）は 403 で読めなかった。Rapp & Melville 1990 の PDF は 10 MB を越えて読めなかった。CCP-WSI の目録の頁は画像が大半で、データの大きさと使用条件が読めなかった。
- 原典で確かめていない数：Beji & Battjes の Case A の名前と値（二次資料 2 つで一致）、Berkhoff の浅瀬の厚さの式、Grilli らの崩れる時の式の係数、Jacobsen らの崩れの例がどの実験か、Luth ら・Dingemans の報告書の番号。
- 時間の見積もりは、設定の違う既存の計算からの比で、2〜4 倍外れうる【推定】。
- 読む道具が自動で保存した PDF（5 本、約 12 MB）：会話の一時置き場（C: の利用者のフォルダーの下）の `webfetch-*.pdf`（PICIN の要旨、Ransley ら 2019、Sinnis ら 2021、Windt ら 2019、arXiv 2002.00827）。文字を読むために、会話の一時置き場で文字を抜き出した。作品・G: には置いていない。消してよいかは利用者が決める。

## 9. 文献とデータの場所

理論・手順

1. Dean, R. G. & Dalrymple, R. A. (1991) *Water Wave Mechanics for Engineers and Scientists*. World Scientific.（分散の関係、浅水係数、Stokes 2 次、ピストン造波）
2. Le Méhauté, B. (1976) *An Introduction to Hydrodynamics and Water Waves*. Springer.（波の理論の使える範囲の図。Windt ら 2019 が引用）
3. Rienecker, M. M. & Fenton, J. D. (1981) A Fourier approximation method for steady water waves. *J. Fluid Mech.* 104, 119–137.
4. Fenton, J. D. (1985) A fifth-order Stokes theory for steady waves. *J. Waterway, Port, Coastal, Ocean Eng.* 111(2), 216–234.
5. Madsen, O. S. (1971) On the generation of long waves. *J. Geophys. Res.* 76(36), 8672–8683.
6. Booij, N. (1983) A note on the accuracy of the mild-slope equation. *Coastal Engineering* 7, 191–203.
7. Goda, Y. & Suzuki, Y. (1976) Estimation of incident and reflected waves in random wave experiments. *Proc. 15th ICCE*.／Mansard, E. P. D. & Funke, E. R. (1980) The measurement of incident and reflected spectra using a least squares method. *Proc. 17th ICCE*.
8. Celik, I. B. ほか (2008) Procedure for estimation and reporting of uncertainty due to discretization in CFD applications. *J. Fluids Eng.* 130(7), 078001.
9. Biésel, F. & Suquet, F. (1951) Les appareils générateurs de houle en laboratoire. *La Houille Blanche* (2), 147–165. https://www.shf-lhb.org/10.1051/lhb/1951033/pdf （第 1 部。DOI は掲載の頁の名前から推した値で未確認）
10. Fouques ら・Bouscasse ら (2021) Qualification criteria for the verification of numerical waves, Part 1・Part 2. OMAE2021（Part 2：doi:10.1115/OMAE2021-63710）。Part 1：https://hal-cnrs.archives-ouvertes.fr/LHEEA/hal-03546188v1

基準の問題（実験）

11. Beji, S. & Battjes, J. A. (1993) Experimental investigation of wave propagation over a bar. *Coastal Engineering* 19, 151–162. 写し：https://data-ww3.ifremer.fr/BIB/Beji_Battjes_CE1993.pdf （403 で読めず）
12. Luth, H. R., Klopman, G. & Kitou, N. (1994) Delft Hydraulics の報告書（潜堤の上で部分的に崩れる波の運動の測定。報告書の番号は未確認）。Dingemans, M. W. (1994) Delft Hydraulics の報告書（Boussinesq 型のモデルと実験の比べ。番号は未確認）。オンラインの置き場は見つからなかった。
13. Basilisk の試験 Periodic waves over a submerged bar：http://basilisk.fr/src/test/bar.c 。データ http://basilisk.fr/src/test/gauge-4 〜 gauge-11（各 34 行、1 KB 前後）。Basilisk の楕円の浅瀬の例：https://www.basilisk.fr/src/examples/shoal-ml.gpu.c
14. Berkhoff, J. C. W., Booij, N. & Radder, A. C. (1982) Verification of numerical wave propagation models for simple harmonic linear water waves. *Coastal Engineering* 6, 255–279.
15. Hansen, J. B. & Svendsen, I. A. (1979) Regular waves in shoaling water: experimental data. Series Paper 21, ISVA, Technical University of Denmark（正誤表あり。オンラインの置き場は見つからなかった）。
16. Ting, F. C. K. & Kirby, J. T. (1994) Observation of undertow and turbulence in a laboratory surf zone. *Coastal Engineering* 24, 51–80. doi:10.1016/0378-3839(94)90026-4 。(1995) Dynamics of surf-zone turbulence in a strong plunging breaker. *Coastal Engineering* 24, 177–204。(1996) Dynamics of surf-zone turbulence in a spilling breaker. *Coastal Engineering* 27, 131–160。写し：https://data-ww3.ifremer.fr/BIB/Ting_Kirby_CE1994.pdf （403 で読めず）
17. Grilli, S. T., Svendsen, I. A. & Subramanya, R. (1997) Breaking criterion and characteristics for solitary waves on slopes. *J. Waterway, Port, Coastal, Ocean Eng.* 123(3), 102–112. doi:10.1061/(ASCE)0733-950X(1997)123:3(102)
18. Barthelemy, X. ほか (2018) On a unified breaking onset threshold for gravity waves in deep and intermediate depth water. *J. Fluid Mech.* 841, 463–488（arXiv 1508.06002）。Derakhti, M., Kirby, J. T., Banner, M. L., Grilli, S. T. & Thomson, J. A unified breaking onset criterion for surface gravity water waves in arbitrary depth. https://arxiv.org/abs/1911.06896
19. Rapp, R. J. & Melville, W. K. (1990) Laboratory measurements of deep-water breaking waves. *Phil. Trans. R. Soc. Lond. A* 331, 735–800. doi:10.1098/rsta.1990.0098 。PDF：https://airsea.ucsd.edu/wp-content/uploads/sites/10/2019/06/1990_Rapp_Melville-A_Mathematical_and_Physical_Sciences_vol_331.pdf （10 MB 超）
20. Sinnis, J. T., Grare, L., Lenain, L. & Pizzo, N. (2021) Laboratory studies of the role of bandwidth in surface transport and energy dissipation of deep-water breaking waves. *J. Fluid Mech.* 927, A5. doi:10.1017/jfm.2021.734 （PDF 約 2 MB）
21. Ransley, E. ほか (2019) A blind comparative study of focused wave interactions with a fixed FPSO-like structure (CCP-WSI Blind Test Series 1). *Int. J. Offshore Polar Eng.* 29(2), 113–127. doi:10.17736/ijope.2019.jc748 。写し（約 3 MB）：https://vbn.aau.dk/ws/files/305542572/ijope_29_2_p113_jc748_Ransley.pdf 。データ：http://www.ccp-wsi.ac.uk/blind_test_series_1 、目録 https://ccp-wsi.ac.uk/catalogue/test_cases/test_case_003 （BT2・BT3 は test_case_004・005）。大きさと使用条件は未確認。

数値の水槽の方法と確かめ

22. Jacobsen, N. G., Fuhrman, D. R. & Fredsøe, J. (2012) A wave generation toolbox for the open-source CFD library: OpenFoam®. *Int. J. Numer. Meth. Fluids* 70(9), 1073–1088. doi:10.1002/fld.2726
23. Windt, C., Davidson, J., Schmitt, P. & Ringwood, J. V. (2019) On the assessment of numerical wave makers in CFD simulations. *J. Mar. Sci. Eng.* 7(2), 47. doi:10.3390/jmse7020047 （MDPI のオープンアクセス。PDF 約 3.2 MB：https://mural.maynoothuniversity.ie/12393/1/JR-Assessment-2019.pdf ）
24. Larsen, B. E., Fuhrman, D. R. & Roenby, J. (2019) Performance of interFoam on the simulation of progressive waves. *Coastal Engineering Journal* 61(3), 380–400. https://arxiv.org/abs/1804.01158
25. Saincher, S. & Banerjee, J. An inflow-boundary-based Navier-Stokes wave tank: verification and validation for waves propagating over flat and inclined bottoms. https://arxiv.org/abs/1902.09503
26. Kelly, D. M., Chen, Q. & Zang, J. (2015) PICIN: a particle-in-cell solver for incompressible free surface flows with two-way fluid-solid coupling. *SIAM J. Sci. Comput.* 37(3), B403–B424. doi:10.1137/140976911
27. Chen, Q., Kelly, D. M., Dimakopoulos, A. S. & Zang, J. (2016) Validation of the PICIN solver for 2D coastal flows. *Coastal Engineering* 112, 87–98. doi:10.1016/j.coastaleng.2016.03.005
28. Chen, Q., Zang, J., Kelly, D. M. & Dimakopoulos, A. S. (2018) A 3D parallel particle-in-cell solver for wave interaction with vertical cylinders. *Ocean Engineering* 147, 165–180. doi:10.1016/j.oceaneng.2017.10.023
29. Chen, Q., Kelly, D. M. & Zang, J. (2019) On the relaxation approach for wave absorption in numerical wave tanks. *Ocean Engineering* 187, 106210. https://researchportal.bath.ac.uk/en/publications/on-the-relaxation-approach-for-wave-absorption-in-numerical-wave-/
30. Chen, Q., Zang, J., Kelly, D. M., Williams, C. J. K. & Dimakopoulos, A. (2015) Particle-in-cell numerical solver for free surface flows with fluid-solid interactions. 30th IWWWFB. https://people.maths.bris.ac.uk/~marp/iwwwfb-2015/abstracts/iwwwfb30_11.pdf （約 0.6 MB）
31. Maljaars, J. M., Labeur, R. J., Möller, M. & Uijttewaal, W. S. J. (2017) A numerical wave tank using a hybrid particle-mesh approach. https://research.tudelft.nl/en/publications/a-numerical-wave-tank-using-a-hybrid-particle-mesh-approach/
32. Lowe ほか（arXiv 2002.00827）Numerical simulations of surf zone wave dynamics using Smoothed Particle Hydrodynamics. https://arxiv.org/abs/2002.00827 （著者・誌名は arXiv の頁で確かめていない）

二次資料（設定の数を取った所）

33. Bigoni, D., Engsig-Karup, A. P. & Eskilsson, C. Efficient uncertainty quantification of a fully nonlinear and dispersive water wave model with random inputs. https://arxiv.org/abs/1410.6338
34. Comparing methods of modeling depth-induced breaking of irregular waves with a fully nonlinear potential flow approach. https://arxiv.org/abs/1912.01905
35. Duran, A. & Marche, F. A discontinuous Galerkin method for a new class of Green-Naghdi equations on simplicial unstructured meshes. https://arxiv.org/abs/1604.05227
36. Implementation and evaluation of breaking detection criteria for a hybrid Boussinesq model. https://arxiv.org/abs/1902.03021

## 10. この調べで作ったファイル

- この文書：`Unity/Build/FLIP41/research/benchmarks_ja.md`
- 理論の値の道具：`Tools/GWWaveGen/flip41/b_theory_numbers.py`（`py -3.10 Tools/GWWaveGen/flip41/b_theory_numbers.py` で作り直せる）
- 理論の値：`Unity/Build/FLIP41/research/b_theory_numbers.json`
- 読んだ既存の記録：`Unity/Build/FLIP39/E/record_ja.md`（§4.1 の C1）、`Unity/Build/FLIP39/E/C1_full_reef_S010/`（`hf_c0001.npz` の大きさと成分の表だけ）、`Unity/Build/FLIP37/P0/record_ja.md`、`Unity/Build/FLIP37/runs.jsonl`、`Unity/Build/FLIP39/runs.jsonl`、`Tools/GWWaveGen/flip39/e_tanklib.py`・`e_build_tank.py`・`e_cfg.py`。どれも変えていない。
