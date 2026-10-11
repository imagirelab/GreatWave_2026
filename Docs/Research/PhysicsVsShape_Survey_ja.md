# 物理の計算と「描きたい波の形」の差を、他の作品・手法はどう扱ったか（Q53 の調べ）

- 2026-10-11 に書き、10-12 に別の者の確かめを受けて直した（直した所は §6）。書いた者：進行役（Claude）。学生（王）を通して指導教員にお送りする報告。記録は[制作手順](../Workflow/Production_Workflow_ja.md)の Q53〜Q55。
- きっかけ：学生の「外から力を加えずに原画の形まで持っていくのは非常に難しく、ある程度似せるところまでが限界」に、指導教員が「それを自分だけの感想で語るのではなく、他の作品・手法がどのように扱っているのかを調査してください。」と答えた（10/11 22:54）。
- 印：【文献】出典に書いてあること／【測った】この計画の記録の値／【計算】式の値／【考え】【推定】進行役の推論で、確かめていない／未確認＝読めなかった・見ていない。分類の記号は §1 の頭。

## 一枚で

| 流れ | 内容 |
| --- | --- |
| 方針 | 学生の見方を、感想ではなく、他の作品・手法の扱いで確かめる。調べる前に、項目ごとに書く 4 点を決めた：何を出したか（目標・原画への近さと証拠）／形をどう得たか／物理からの離れをどう言い、どう測ったか／この作品への意味 |
| 目標 | 3 つに証拠で答える。① 欲しい形にどう届かせているか　② 重力だけでどこまで届いたか　③ 物理からの離れをどう言い、どう測ったか |
| 結果 | 62 項目（『神奈川沖浪裏』を扱った作品 12、映画・アニメの制作 15、流体の制御の研究 16、原画・描画・もっともらしさの研究 14、確かめで足した 5。同じ物を別の角度で見た重なりを含む）。制作で主役の大波の作り方を書いた 12 項は、どれも形を先に作る・制御の力・物理でない境界のどれかを含む。『神奈川沖浪裏』の作品で、計算の途中の力で原画へ寄せた物は 0（§0 の数え） |
| 分かったこと | 1. 目標が物理で起こりうる波（記録の波の時系列）なら、造波を直す・計算を回して選ぶという重力だけの手で届かせた例がある。目標が描いた形なら、作り方の書かれた例はどれも物理の外の手を足していた<br>2. 重力だけで届いたのは、前へ巻く・局所の頂・巻き始めの立った壁まで。唇の厚みと唇の下の前の面の傾きが原画に届いた例はなく、届かないと試して確かめた研究もない<br>3. 離れを書いた資料は名前を付けて書く。数で示したのは研究の一部で、力を重力と比べた値は流体・映像の資料に見つからなかった |
| 現在地 | 読むだけの調べを終え、別の者の確かめを受けて直した（10/12）。比べの基準は重力だけの今の 2D の計算（FLIP42）。新しい計算は指導教員のお返事まで始めない（Q49）。期限 10/29 まで 17 日 |
| 次 | 指導教員に案を選んでいただく（§3.3）：A 重力と造波・海底の条件だけで続け、原画との差を同じ量で書く／B 物理的にありえる風の圧力を現実の大きさで足し、力なしと比べる／C 残る差を、浮世絵へ移す段の様式化として名前と数で計算の外に置く。組み合わせもできる。10/13 18:00 までに Discord で、なければ 10/14（水）のゼミで伺う。A なら礁の 2D の結果を 10/19、B なら礁の結果の後に 10/23 ごろ、C なら何を何倍にするかの案を 10/19 に、同じ量で報告する（日付は進行役の案）【推定】 |

## 0. 問いへの答え

### 0.1 数え（項目の分類から。分類の記号と表は §1）

| 群 | 項目の数 | 形の得方の数え【考え：項目の分類を数えた】 |
| --- | --- | --- |
| 『神奈川沖浪裏』を扱った作品 | 12 | 原画の形へ寄せる途中の力（G）0。形を手・原画の画像・置いた形から与えた 5（GW01、GW03〔推定〕、GW05〔始めのコマだけ〕、GW08、GW09）。大きな形の作り方を書いていない 4（GW02、GW04、GW06、GW11）。ほか 3（GW07 は渦の面の計算、GW10 は本物の高潮の映像、GW12 は研究の側を指すだけ） |
| 映画・アニメの制作 | 15 | 主役の大波の作り方を書いた 12 は、どれも S・G・B\* のどれかを含む（S を含む 8、G を含むか G に近い 5、B\* 1。重なりあり）。書いていない 3（PR04 Avatar、PR06 の浅瀬の主役の波、PR14 ゴジラ-1.0） |
| 流体の制御の研究 | 16 | G 12、B\* 2（FC06、FC12）、B 1（FC15）、後 1（FC14）。砕ける波を制御したのは FC06・FC12・FC16（FC16 は要旨だけ）。FC10 は高い波を持ち上げるだけで、巻く形は評価しない |
| 原画・描画・もっともらしさの研究 | 14 | 原画の読み 7（SC01〜SC07）、描く段の様式化 5（SC08〜SC12）、もっともらしさの物差し 2（PR16、SC14） |
| 確かめで足した項目 | 5 | 重力だけの 3D の巻き 1（AD01）、唇を手の規則で足す 1（AD02）、式で作る崩れる波 1（AD03）、物理の計算を回して選ぶ 1（AD04）、物理の外の助けの力を限度と比べる報告 1（AD05） |

- 62 項目には、同じ作品・論文を別の角度で見た重なり（Moana 3 項、Kim ら・McAllister ら・Mihalef ら・KUBO 各 2 項）と、指すだけの項目 1 つ（GW12）が入る。
- 確かめの段で一次の出典と照らした項目の中にも、本文が読めず要旨だけで照らした物がある（FC04、FC05、FC07 の Nielsen ら、FC13 の Chen ら・Li ら、SC05、SC08〜SC10、SC12）。FC16 と AD04 は検索の要約で要旨を読んだだけ、SC14 は作業メモだけ、AD01〜AD03 は前の調べの記録による（§4）。

### 0.2 ① 欲しい形にどう届かせているか

目標が何かで、手が二つに分かれた【文献】。

**目標が物理で起こりうる波（記録・実験の時系列）の時：重力の計算・実験のまま届かせる手が確立している。**

- 造波の境界を直して合わせる：Fernández ら 2014（FC15。造波板の信号を 2〜3 回直し、目標の時系列との相関 R = 0.97。著者は、目標は「現実らしい」物でなければならないと書く）。McAllister ら 2019（SC03。造波の振幅と位相を 7〜8 回直して Draupner の記録に合わせた、r² > 0.95【文献：[作り方の調べ](BigWave_Recipes_ja.md) B1】）。
- 物理の計算を多く回して選ぶ（Sel）：The Finest Hours（PR06。計算した海の図鑑から使える波を探す）、Twigg & James 2007（AD04。剛体の計算を並べて回し、見て選ぶ。要旨だけ）、Enright 2002（AD01。棚の形を 2D の試しを見て選び、3D は重力だけで解く）。どれも目標の形を点ごとに指定する使い方ではない。

**目標が描いた形（物理で起こるか分からない形）の時：作り方の書かれた例は、どれも物理の外の手を一つ以上足していた。**

- 形を先に手か手順で作り、計算は上に乗せる（S）：Surf's Up、Poseidon、Interstellar、Life of Pi、Moana の海の人物（形はリグとアニメーション）、Thürey ら 2007（唇だけを手の規則で足す）。HOKUSAI: ANOTHER STORY は「シミュレーションをベースに手付けで動きを付け」と書く【文献】。これを S と分けたのは進行役【考え】。
- 計算の途中で目標へ寄せる誘導・制御の力（G）：制作では Project Blue Book（誘導の形から範囲と速度の場を作り、FLIP を従わせる）、Hereafter（俳優の近くだけ実写の水に縛る）、研究では Fattal & Lischinski 2004 の目標へ運ぶ力、Pan ら 2013 のゴーストの力ほか。
- 物理と釣り合わない初め・境界の値（B\*）：Moana の崩れる波（境界を「物理ではあり得ないほど急な波」の値に替える）、Mihalef ら 2004（人が選んだ断面を初めの状態に置く）。
- 流体の式を解かずに形を作る（F）：式で作る崩れる波（Fournier & Reeves 1986 ほか）、原画の画像から作った 3D。
- 計算はそのまま、原画らしさは描く段の層で足す（後）：teamLab（粒子の軌跡の線）、KUBO（木目の模様）、描画の研究（Eden ら 2007、Kim ら 2020、Stevenson-Regla ら 2025）。これは形を物理の外で作る手ではなく、見え方を分ける手である。

『神奈川沖浪裏』を扱った作品で、計算の途中に力を入れて原画へ寄せたと書いた物は見つからなかった。原画に近い形を見せる作品は、形を手か原画の画像で与えていた（GW01、GW08、GW09。GW03 は置いた形と推定。GW05 は始めのコマだけ原画で、計算を進めると形は崩れた）【文献・推定】。

### 0.3 ② 重力だけでどこまで届いたか

比べの量は [形の違いの検討](PeriodicBigWave_Study_ja.md) §1.2（STUDY52）と同じ。η_c は静かな水面から頂までの高さ、H は頂から谷まで。量の名前をいつも書く。

**届いた所【文献・測った】**

- 前へ巻いて唇の下に空気を囲む：Enright 2002（3D。孤立波を斜面と棚に当て、空気の管、唇の指、2 つ目のはね上がりが出た。途中の力なし）、本作の FLIP42（2D の断面）。
- 局所に集まって前へ巻き始める頂：Fochesato ら 2007 の 3D の数値水槽（造波の境界だけ。Dudley ら 2013 が原画の読みに借りる）。
- 巻き始めに、前の面の頂の近くがほぼ鉛直の壁になる：McAllister ら 2019 の図 3（交わる角 0°）。本作の FLIP42 も前の面が頂の近くで鉛直を越えた。これは巻き始めの頂の近くの壁で、原画と比べた「唇の下の前の面の傾き」（いちばん巻いたコマの、0.1〜0.5 η_c の弦）とは別の量である。McAllister らの断面でこの量は未確認。

**届いていない所**

- 唇の下の前の面の傾き（0.1〜0.5 η_c の弦）：原画 64°、本作 19〜20°【測った】。文献でこの量を出した例は見つからなかった。
- 唇の厚み ÷ H：読んだ論文の値 0.04〜0.13、本作 0.08〜0.11、原画 0.17〜0.32【文献・測った・推定】。原画の値は、谷が手前の波と船に隠れて読めないので、本作の H ÷ η_c（1.11〜1.45）を借りて η_c で測った値（0.24〜0.35 η_c）から直した【推定】。原画の唇は泡と爪を含む描いた形で、測った噴流ではない。
- 唇の下の空気の高さ：原画 0.54 η_c 以上、本作 0.15〜0.17 η_c【測った】。群を強めた水槽の実験（Erinin ら 2023）を本作に当てても 0.20〜0.24 η_c ほど【推定】。

**「似た」と言われた例と、原画を物理で読んだ研究**

- 「北斎の大波に似る」と報じられた水槽の波（McAllister ら 2019）は、研究者自身が「まったくの偶然」と言い、似方は目で見た比べだけで測っていない【文献】。似ていると言われた写真の交わりの角は書かれていない。Draupner の高さに届いたのは大きく交わる時（発表で約 120°）なので、その側の、前へ巻かず上へ噴き上がる波と読む【推定】。
- Dudley ら 2013 は、南極の海で撮った異常波の写真（高さ 6〜8 m）を原画と並べ、局所の形が「著しく似る」と書く。これも目の比べで、角度や比は測っていない【文献】。
- 原画を物理で読んだ研究（Cartwright & Nakamura 2009）は、原画を本物の巻き波として「かなりもっともらしい」と書く。重力だけでは届かないと書いた研究、試して確かめた研究は見つからなかった【文献】。

### 0.4 ③ 離れをどう言い、どう測ったか

- 離れを書いた資料は、名前を付けて書いていた（「ゴーストの力」「物理でない集める項」「物理ではあり得ないほど急な境界」「原画を忠実に再現することではありませんでした」「形に打ち込む」など）【文献】。
- 一方で 10 項は、離れについて何も書いていない：GW05（作者は道具の名だけ）、GW06、GW09、GW10、GW11、PR03、PR06、PR12 の Aquaman、PR15 のポニョ・天気の子、FC16（本文未確認）。物理を名乗らない物も多く、隠したかどうかは判断できない【文献・考え】。
- 読んだ資料の多くは、手法を見せる講演・論文・取材の記事で、うまくいった所を書く向きがある。この偏りは割り引いて読む必要がある【考え】。

| 誰が | 言葉（離れの言い方） | 数（離れの測り方） |
| --- | --- | --- |
| 流体の制御の研究 | 「ゴーストの力」「架空の力」（Pan ら 2013）、「物理でない集める項」（Fattal & Lischinski 2004）、目標の形に合わせる制御は「超自然の効果」向け（Nielsen & Bridson 2011） | 値を書いた物：混ぜの係数 α = 0.5（Raveendran ら 2012）、力の係数 C_shape 500・C_velocity 20（Pan ら 2013）、力の量の表（Holl ら 2020、制御器どうしの比べ）、目標の時系列との相関 R = 0.97（Fernández ら 2014）。重みの名前だけで値のない物：力の 2 乗の罰 k_s（Treuille ら 2003）、r（Pan & Manocha 2017） |
| 映画・アニメの制作 | 「物理に逆らいつつ、起こり得る感じを保つ」（Moana の海の人物）、物理ではあり得ないほど急な境界（Moana の崩れる波）、「形に打ち込む」（The Day After Tomorrow）、物理に基づくが正確である必要はない（The Perfect Storm の記事の地の文）、ゆっくり迫る 200 フィートの波は本物なら崩れるので計算できない（Poseidon） | 離れの量の数はない。物理らしさを測って支えた手として記事にあったのは、唇に重力の玉を落として落ち方を確かめた Surf's Up と、水槽の壁の目盛りで波高を測った Life of Pi（どちらも結果の数は記事にない） |
| 『神奈川沖浪裏』の作品 | 「原画を忠実に再現することではありませんでした」「完全に物理的な正確さを追求するのではなく」（Utsubo）、「シミュレーションをベースに手付けで動きを付け」（HOKUSAI: ANOTHER STORY）、水は様式化するが水として振る舞わせる（KUBO の監督） | なし。原画との近さは記事の評（「思わせる」「似る」）だけ |
| 原画の研究 | 縦の尺度を約 30 % 伸ばした、高さを大きく描いた見込み（Cartwright & Nakamura 2009） | 縦の伸び約 30 %（富士の斜面と写真の比べ）。前の面・唇は測っていない |
| もっともらしさの研究 | 「物理としてもっともらしい」と「見た目にもっともらしい」を分ける。見る人が予想する見えない力（風）はもっともらしさを助け、予想しない力とエネルギーの足し過ぎは下げる（Barzel ら 1996。剛体の玉の論文） | 衝突の向きの乱れの幅（約 8°・10°）。著者が目で見て決めた幅で、人を集めた試しではない。人が異常に気づくかで測る研究（O'Sullivan ら 2003）は作業メモだけにより、閾値の数は未確認 |
| 隣の分野：生体の力学・人物の計算（AD05） | 物理の外の助けの力を「残りの力（residual forces）」と名付ける。Yuan & Kitani 2020 は「見えない力」と呼び、本物のロボットは出せないと書く | OpenSim の手引きは、残りの力の最大は 10〜20 N 未満、平均は 5〜10 N 未満を目安とする【文献：頁を読んだ】。Hicks ら 2015 は外の力の最大の約 5 % を目安にすると二次の資料が伝える（未確認）。Yuan & Kitani は報酬の罰（重み 0.1）で小さく保つが、大きさは報告しない |

力を重力と比べた値、力が水にした仕事（足したエネルギー）を数で出した例は、流体と映像の資料には見つからなかった（Pan ら 2013 は入るエネルギーの違いを図で比べただけ）【文献】。物理の外の助けの力に名前を付け、限度と比べて報告する形は、隣の生体の力学の計算に確立している（AD05）【文献】。

### 0.5 学生の見方の言い直し（文献で言える範囲）【考え】

「目標が物理で起こりうる波なら、重力のまま造波の条件を直す・計算を回して選ぶだけで届かせる方法が、水槽の実験と工学で確立している。目標が描いた形（原画）の時、重力と波の起こし方だけで届いた例は、作品・制作・研究のどこにも見つからなかった。描いた形が要る制作と研究は、形を先に作るか、名前を付けた制御の力・物理でない境界の値を足し、作り方を書いた資料はそのことを文で明記している。ただし、届かないことを試して確かめた研究もなく、原画の形が物理で起こりうる形かどうかも分かっていない。重力だけで届いたのは前へ巻く・局所の頂・巻き始めの立った壁までで、唇の厚みは論文の値が原画（換算した値）に届いていない。原画の側にも、文献が名前で挙げる画家の変形（縦の伸び、高さ、構図の比、円弧の作図、爪の型）がある。」

## 1. 形の得方で分けた一覧

分類の記号【考え：進行役が分けた】：P・B 重力と初め・境界の条件だけ／B\* 物理と釣り合わない初め・境界の値（原画の形を始めに置く「初」を含む）／Sel 物理の計算を回して選ぶ／G 計算の途中の誘導・制御の力・速度の縛り／S 形を手か手順で先に作る／F 流体の式を解かない／後 計算の後・描く段の見た目の層（様式化）／U 資料から決められない。原画の読みと物差しの研究は別の表にした（9 つの表）。

各行は (1) 出したもの・目標や原画への近さ、(2) 形の得方、(3) 離れの言い方・測り方、(4) この作品への意味。番号は `items.json` の id。詳しい記録と全部の出典は §5 と作業メモ。

### 1.1 重力と初め・境界の条件だけ（P・B）

| 例 | (1) 出したもの | (2) 形の得方 | (3) 離れの言い方・測り方 | (4) この作品への意味 |
| --- | --- | --- | --- | --- |
| 本作の今の 2D の計算（比べの基準、記録） | 前へ巻き、唇が付いて空気を囲む。唇の下の前の面の傾き 19〜20°、唇 約 1 m【測った】 | 入口の帯で 32 成分の線形の流速へ寄せ、外は重力だけ | 原画との差を STUDY52 の量で数に。入口の帯の意味は指導教員の確認待ち | 比べの基準。[形の違いの検討](PeriodicBigWave_Study_ja.md) |
| AD01 [Enright 2002](https://web.stanford.edu/group/fpc/Publications/Enright%20Thesis.pdf)（学位論文 §4.5.4） | 3D で前へ巻き、空気の管、唇の指、2 つ目のはね上がり（図 4.11〜4.14）。頂は横に長い。原画とは比べていない | 孤立波（H 7 m・水深 10 m）を 1:7 の斜面と水面下 2 m の棚に当てる。棚は 2D の試しを見て選び、少し斜めにして横に変えた。途中の力なし | 力の離れはない。棚の選びは目で行った（Sel の面）。総説（Darles ら 2011）は「格子の速度を式で縛った」と書くが、学位論文は初めの孤立波だけを書く【文献：[作り方の調べ](BigWave_Recipes_ja.md) C9・§8】 | 重力だけで 3D の巻きが出て、数がそろって書かれた例。2D で海底を選んでから 3D を解く順は、本作の礁の案と同じ |
| SC03 [McAllister ら 2019](https://doi.org/10.1017/jfm.2018.886) | 円い水槽で二つの群を交わらせて Draupner の波。前へ巻くのは 0°、120° は上へ噴き上がる。報道は北斎に似ると書く | 周りの造波板の動きだけ。造波の振幅と位相を 7〜8 回直して記録に合わせた（r² > 0.95） | 研究者は「まったくの偶然」（[EGU](https://blogs.egu.eu/geolog/2019/07/08/imaggeo-on-mondays-recreating-monster-waves-in-art-and-science/)）。似方は目の比べ。似たと言われた写真は 120° 側と読む【推定】 | 記録の波を境界の直しだけで出した例。原画は狙っておらず、似方は測っていない |
| SC02 [Dudley ら 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC3645210/)（Fochesato ら 2007） | 局所に集まって前へ巻き始める頂（3D の数値水槽）と、6〜8 m の異常波の写真 | 蛇行する造波板（境界）だけ。水に力なし | 写真と原画の似方は目の比べ（「著しく似る」）。角度・比は測らない | 3D の向きの集まりで局所の巻く頂が出る裏付け。唇の厚みの数はない |
| FC15 [Fernández ら 2014](https://icce-ojs-tamu.tdl.org/icce/article/download/7507/pdf_780/31186) | 水路の集まり波、目標の時系列との相関 R = 0.97。砕ける波は焦点で合わせられず上流で合わせた | 造波板の信号だけを繰り返し直す | 相関 R で数に。目標は「現実らしい」物でなければならないと書く | 境界だけで目標へ寄せ、誤差を数で出す工学の形。今の入口の帯と同じ置き場。巻く形を目標にした使い方はない |
| PR04 [Avatar: The Way of Water](https://firedbydesign.com/?p=15440) | 水のショット多数。崩れる大波の作り方は資料にない | 物理に基づく解き手が主。美術の注文の時だけ決まりを破る | 「美術の指定と物理らしさの引っ張り合い」と言う。数なし | 力なしを主に出し、例外を場所と理由で言う書き方の手本 |
| GW07 [Mark J. Stock](https://digitalartarchive.at/database/work/3631) | 原画への計算の献辞。前へ巻く形はない（小さな図を見た） | 渦の面の計算（水面の波ではない） | 原画の形を狙わない | 形でなく、原画の物理の性格（大きな渦から細かい渦へ）を見せる立て方 |

### 1.2 物理と釣り合わない初め・境界の値（B\*）

| 例 | (1) 出したもの | (2) 形の得方 | (3) 離れの言い方・測り方 | (4) この作品への意味 |
| --- | --- | --- | --- | --- |
| FC06 [Mihalef ら 2004](https://www.math.fsu.edu/~sussman/BreakingWavesElectronic.pdf) | 3D の巻き（唇の下の空気の管、2 つ目の噴流）。図 1 は原画だが目標ではない | 2D の一覧から人が断面を選んで 3D の初めに。途中の力なし。一覧の ω（角周波数）は線形の分散の値の約 2.5〜5.3 倍【計算・考え：g = 0.1、k = 2π、d = 0.25〜0.35 から】 | 「物理として正しい速度の場から始める」を根拠にする。離れの数はない | 初めの状態の選びで前へ巻く形を制御した研究。砕ける波の制御は、ほかに Moana（境界）と Brousset ら（外の力、要旨だけ）がある |
| PR02・FC12 [Moana の崩れる波](https://history.siggraph.org/wp-content/uploads/2022/09/2017-Talks-Byun_Moana-Crashing-Waves.pdf) | 40 を超える崩れる波、端から崩れる筒 | 断面の線の変形器（S）か、APIC の計算で境界を「物理ではあり得ないほど急な波」の値に替える | 境界が物理でないと明記。どれだけ急かは書かない | 離れを境界の一か所に置き、そこを名指す書き方 |
| GW05 [Sarah Hashem の FLIP](https://80.lv/articles/traditional-japanese-painting-brought-to-life-with-sidefx-houdini) | 始めのコマは原画の画像そのもの、15 秒後には形がほぼ残らない（動画を見た） | 原画の色の粒子を原画の形に並べて FLIP で動かしたと読む【推定】 | 作り手は道具の名だけ。記事は「現実離れ」 | 原画の形を始めに置いても保たれない。Q39 の「大きい波を用意した」型 |

### 1.3 物理の計算を回して選ぶ（Sel）

| 例 | (1) 出したもの | (2) 形の得方 | (3) 離れの言い方・測り方 | (4) この作品への意味 |
| --- | --- | --- | --- | --- |
| PR06 [The Finest Hours](https://www.fxguide.com/quicktakes/making-the-finest-hours/) | 嵐の海と浅瀬の 30〜50 フィートの波 | 長い周期の海を何種か計算し、合う波を探す。浅瀬の主役の波の作り方は未確認 | 形の離れの言葉なし | 礁に群を送り崩れる所を使う案と同じ向き。目標の形は指定していない |
| AD04 [Twigg & James 2007](https://history.siggraph.org/?p=115323) | 剛体の多体の場面で、使い手が望む結果を得る（要旨は、中くらいの場面なら使い手の時間 1 時間未満で、変わった結果を得られると書く） | 速い剛体の計算で多くの例を並べて回し、使い手が見て回って選び、手直しする | 最適化による制御は接触のある多体では解きにくい、を動機に書く。何を乱して例を作ったかは未確認（要旨だけ） | 「物理の計算を回して見て選ぶ」の確立した形。案 A の選び方の先例。流体ではない |

### 1.4 計算の途中の誘導・制御の力（G）

| 例 | (1) 出したもの | (2) 形の得方 | (3) 離れの言い方・測り方 | (4) この作品への意味 |
| --- | --- | --- | --- | --- |
| FC01 [Treuille ら 2003](https://grail.cs.washington.edu/projects/control/smokeControl.pdf) | 煙が文字・形のキーに合う | ガウスの風の力と渦の力を最適化。一例は最初の一歩だけ | 力の 2 乗の罰 k_s（例ごとの値は書かない）。「制御されすぎ」は罰を強めて力を減らし、目で判断 | 罰の重みを振って釣り合いを見せる形の元 |
| FC02 [McNamara ら 2004](https://grail.cs.washington.edu/projects/control/fluidAdjoint.pdf) | 液体が十字・人の形に、しぶきから水滴 | 風の力＋水の出し入れ（source）、随伴法 | 罰の重みで「もとの力学にどれだけ従うか」を決める。値なし。「決まった時刻に波を砕く」を将来の課題に | 砕ける波は扱えなかった |
| FC03 [Fattal & Lischinski 2004](https://pages.cs.huji.ac.il/danix-lab/cglab/projects/tdsmoke/tdsmoke.pdf) | 煙が順に目標の形に | 目標へ運ぶ力＋勢いを減らす項＋物理でない集める項（係数 4 つ） | 「力を小さくしようとしていない」「物理として実現できるとは限らない」と著者が書く | 「目標の形へ引く力」のいちばん近い先例 |
| FC04 [Shi & Yu 2005](https://diglib.eg.org/items/e9ad74b1-8e5d-49dc-9fb5-801d80773461) | 液体が速く変わる目標を追う | 形と速さの差を戻す帰還の力＋形のポテンシャルの勾配 | 本文未確認。Pan ら 2013 が C_velocity = 20 を借りる | 液体を目標へ引く力の確立した形の一つ |
| FC05 [Thürey ら 2006・2009](https://cris.fau.de/publications/113685044/) | 制御の粒子に液体が従う | 力を速度の粗い成分だけにかける | 小さな動きは自然に残ると要旨に書く | 唇・しぶきは物理に任せる手当て |
| FC07 [Inglis ら 2017](https://ar5iv.labs.arxiv.org/html/1611.03677)、Nielsen ら 2009・2010 | 細かい煙が粗い計算の形を受け継ぐ | 粗い計算の速度へ寄せる罰（重み W、ぼかし β） | 重みとぼかしで表す。離れの量は出さない | 案内が物理の計算である前提。原画の形はこの前提の外 |
| FC08 [Nielsen & Bridson 2011](https://www.cs.ubc.ca/~rbridson/docs/nielsen-siggraph2011-guidedfluid.pdf) | 船の引き上げ・航跡（Weta） | 水面下の案内の形に速度の境界を置き、表の殻だけ解く | 案内が物理の粗い計算なら正しい物理の解、と論拠を書く。目標の形に合わせる制御は「超自然の効果」向けと分ける | この論拠は原画の形へ引く力には使えない |
| FC09 [Raveendran ら 2012](https://faculty.cc.gatech.edu/~turk/paper_pages/2012_controlling_liquids/index.html) | 水でできたうさぎ・踊り手 | 制御の網を境界にし、制御あり・なしの射影を α で混ぜる | α = 0.5 と値を書く。目的を「超自然」と言い切る | 強さを一つの数で報告する例 |
| FC10 [Pan ら 2013](https://www.cs.columbia.edu/~cxz/publications/sketchy_fluids.pdf) | スケッチで高い波を持ち上げ灯台を飲ませる | 幾何で変形した後、ゴーストの力で計算し直す（C_shape 500、C_velocity 20） | 「架空の力から乱れが出うる」と書く。入るエネルギーは図で比べ、数なし | 「波を引き上げて望む形に」の手順として最も近い。高い波は超自然の出来事として作る。巻く形は評価しない |
| FC11 [Pan & Manocha 2017](https://ar5iv.arxiv.org/html/1608.01102) | 煙のキーの制御 | 時空間の最適な制御の力 | 罰の重み r で合いと煙らしさを釣り合わせる（値と力の大きさは出さない） | 重みを振って見せる決まった形 |
| FC13 [Holl ら 2020](https://arxiv.org/abs/2001.07457) ほか | 煙の形の移り変わり | 学習した制御器が力を出す | 力の量を表に数で出す（11.7 対 243 など、制御器どうしの比べ） | 力の量を数で比べる書き方を借りられる |
| FC16 [Brousset ら 2015・2016](https://doi.org/10.1016/j.cag.2016.03.003) | SPH で外の「波の力」によるうねりと砕ける波 | 速さ・高さ・幅を決める値を利用者の曲線で変える | 要旨は「制御できる」ことを利点とする。離れの示し方は未確認（要旨だけ） | 外の力で砕ける波を起こす研究の形 |
| PR13 [Project Blue Book](https://sidefx.com/community/houdini-connect-project-blue-book) ほか（Adrift、Swapped、Moana 2） | 筒に巻いて崩れる津波（350 コマ） | 誘導の形から範囲と速度の場を作り FLIP を従わせ、肩と着水は計算に任せる。目標は客が選んだ下見 | 道具として隠さず書く。強さの数なし。本物の波の映像を部分ごとに調べた | 目標の形へ寄せる制作の確立した形 |
| PR12 [Hereafter](https://www.fxguide.com/?p=21969) | 浜の町を襲う津波 | 俳優の近くは実写の水に縛り、離れると緩める | 縛りを使ったと言う。強さは書かない | 力を範囲で限る先例 |
| PR08 [The Perfect Storm](https://www.cgw.com/Publications/CGW/2000/Volume-23-Issue-7-July-2000-/Sea-Change.aspx)（G に近い） | 100〜150 フィートの海、悪い波 | 物理に基づく計算の中のつまみ（速く育てる・決めたコマで崩す）、後で鋭くする。名前の付いた力ではない | 物理に基づくが正確である必要はない（記事の地の文） | 物理の外の手を計算の中に入れ、そう書いた例 |
| PR10 [The Day After Tomorrow](https://history.siggraph.org/wp-content/uploads/2022/12/2004-Talks-Iversen_Growing-Up-with-Fluid-Simulation-on-The-Day-After-Tomorrow.pdf) | 街を通る高潮 | 弱い計算に替える、途中で速度の場を上書き、場所で変える粘り、形を曲げる | 節の題「形に打ち込む」。手を 4 段（入力と初め・解き手・出力・絵）に分ける | どの段で手を入れたかを書く分け方 |

### 1.5 形を手か手順で先に作る、流体の式を解かない（S・F）

| 例 | (1) 出したもの | (2) 形の得方 | (3) 離れの言い方・測り方 | (4) この作品への意味 |
| --- | --- | --- | --- | --- |
| GW01 [HOKUSAI: ANOTHER STORY](https://cgworld.jp/article/202504-cgw320-hokusai.html) | 写実の大波から浮世絵の波へ。浮世絵の段は書き割りの層（写真 2 枚を見た） | 静止画の絵が先。計算を土台に手で動きを付け、計算の結果を混ぜる。S と分けたのは進行役【考え】 | 「北斎のインプレッション」「手付けで動きを付け」と書く。数なし | 同じ題材の日本の例。Q39 で退けた「手で作る」側 |
| PR01 [Moana の海の人物](https://media.disneyanimation.com/uploads/production/publication_asset/163/asset/Moana-_Performing_Water.pdf)（S、G は従） | 水の山、割れる水の壁 | 見える大きな形はリグとアニメーションが決める。その面の上で誘導つきの計算を走らせる（G は従）。動作の後は重力に従う粒子に替えて崩す | 「物理に逆らいつつ、起こり得る感じを保つ」 | 力を切った後は重力だけ、と分けて書く型 |
| PR11 [Surf's Up](https://www.cgw.com/Publications/CGW/2007/Volume-30-Issue-6-June-2007-/Radical-Dude.aspx) | 筒に巻く波 3 型 | ブレンドシェイプのリグ、計算なし | 唇の頂から重力の玉を落とし、落ちる速さを確かめた（結果の数は記事になし） | 手の形でも重力と比べて確かめる手本 |
| PR09 [Poseidon](https://www.cgw.com/Publications/CGW/2006/Volume-29-Issue-4-April-2006-/Size-Matters.aspx) | 客船を倒す 150〜200 フィートの波 | 手で彫った形＋振り付けた粒子 | 「ゆっくり迫る波は計算できない、本物なら崩れる」 | 描きたい形が物理では保てないと作り手が言った記録 |
| PR07 [Interstellar](https://www.scientificamerican.com/blog/observations/parsing-the-science-of-interstellar-with-physicist-kip-thorne/) | 約 1,200 m の水の山 | アニメーションで形、上にしぶきの計算 | 科学者が後から物理の筋道（潮の段波）を付けた | 形は手、説明で支える型 |
| PR05 [Life of Pi](https://www.fxguide.com/?p=37947) | 高さ 15〜20 m の嵐の波 | 配置の格子と波の道具で形、計算は面の上の流れだけ。水槽の壁の目盛りで波高を測って合わせた | 監督は偶然に任せない | 数で合わせる手（水槽の目盛り）は借りられる |
| AD02 [Thürey ら 2007](https://matthias-research.github.io/pages/publications/breakingWaves.pdf) | 浅水の計算の険しい前の面から、膜が前へ巻いて落ちる（図 9 の唇を見た。前の調べ）。毎フレームの計算 | 浅水の式（重力と圧力）の上に、唇の膜を規則で出す：前の面のしきい値 p_H = 1/4、膜の速さ p_v、厚み p_m、崩れの広がり方。出た後は重力で弾道に動く。膜は厚みも質量も持たない | 著者は高さ場の計算では巻きを表せないと書き、「見た目の主な特徴をとらえる」と書く。手の係数を名前で書く【文献：[リアルタイムの調べ](RealtimeBigWave_Survey_ja.md) C1】 | 唇を解き手の外で、名前の付いた係数で足す先例。案 C の比べ相手 |
| GW03 [Utsubo](https://www.utsubo.com/ja/blog/hokusai-interactive-installation)（F＋初、来場者の力は G） | 粒子の大波と富士が原画の配置に並ぶ（図を見た） | 流れを模したベクトルの場に粒子が沿う計算。大きな形は原画の構図をもとに置いた形と推定（「初」は B\* の一つ）。来場者の体の動きが力として加わる（形を寄せる力ではない） | 「原画を忠実に再現することではない」「完全に物理的な正確さを追求するのではなく」 | 原画からと物理からの両方の離れを目的として書く先例 |
| AD03 式で作る崩れる波（[Gonzato & Le Saëc 2000](https://www.labri.fr/perso/gonzato/Articles/GONZATO_Wave_JVCS2000.pdf)、Fournier & Reeves 1986 ほか） | 岸の規模の巻き波の形（図は見ていない） | Gerstner・Biesel の軌道の式に、伸ばす関数・落とす関数を手で足す。流体の式は解かない（F） | 離れの言い方は前の調べで拾っていない（未確認） | 形を式と手で決める道。Q41・Q44 に合わないので比べの相手として記録 |
| GW08 手で作った再現（[Bo Cao](https://80.lv/articles/japanese-painting-brought-to-life-through-stunning-2d-animation)、[LEGO](https://www.thisiscolossal.com/?p=138774) ほか） | 2D の手描き、積み木、模型、光線追跡、VR の筆 | すべて手 | 物理を名乗らない | 手なら原画に近い形は作れる、という端 |
| GW09 [画像から作った 3D](https://sketchfab.com/3d-models/the-great-wave-off-kanagawa-katsushika-hokusai-f64171ed4ee243819a12a8031e9754d1) | 原画の画像の浮き彫りなど | 画像の明るさを高さにする（F） | 物理を名乗らない | 形の出どころは原画の画像 |
| PR15 様式化した水（[ポニョ](https://www.allcinema.net/cinema/pdf/327529)、[天気の子](https://cgworld.jp/interview/201910-tenkinoko02.html)） | 手描きの大津波、雨と波紋の素材 | 手描き、素材の合成 | 物理らしさを主張しない | 物理の形の議論には使えない |

### 1.6 計算や本物の水はそのまま、原画らしさは見た目の層（後）

| 例 | (1) 出したもの | (2) 形の得方 | (3) 離れの言い方・測り方 | (4) この作品への意味 |
| --- | --- | --- | --- | --- |
| GW04 [teamLab Black Waves](https://www.teamlab.art/jp/w/blackwaves/)（U＋後） | 粒子の軌跡の線で描く波 | 粒子の計算＋線と「超主観空間」。波の起こし方・形の寄せは書かれていない | 北斎の名は出さず、東アジアの線の伝統を根拠に | 形を力で寄せず、描き方で古典の絵に近づける |
| GW02 [KUBO](https://www.slashfilm.com/546075/kubo-and-the-two-strings-travis-knight-interview)（U＋後） | 冒頭の大波は原画への目配せ（監督） | Houdini の水＋木目の模様。大きな形の決め方は資料にない | 水は様式化するが水として振る舞わせる | 動きは写実、面は設計と分けて言う |
| GW10 [Great Wave Dirge](https://hightide2019.westeurope.cloudapp.azure.com/nuxt/artworks/great-wave-dirge) | 本物の高潮の映像を北斎の画風に | 様式の移し | 物理に触れない | 水は本物、原画らしさは画風の層 |
| SC08 [Eden ら 2007](https://cal.cs.umbc.edu/Papers/Eden-2007-AMF/)、Selle ら 2004 | 物理の液体の面に輪郭線と平らな色 | 描く段だけ | 物理の計算の出力を入力にすると明記 | 「計算は重力だけ、浮世絵らしさは描く段」の確立した先例 |
| SC09 [Browning ら 2014](https://pixl.cs.princeton.edu/pubs/Browning_2014_SKA/index.php) | 手描きのキーフレームを計算の動きに写す | 動きは計算、見た目は見本 | 動きは計算に「おおよそ従う」と離れを認める。数なし | 原画を見本に見た目を寄せる道 |
| SC10 [LazyFluids](https://dcgi.fel.cvut.cz/~sykorad/lazyfluids.html)、Fluidymation | 見本の見た目を流体の動きに写す | 見た目の写し | 物理の正しさを主張しない | 動きと見た目を分けるのが描画の研究の標準 |
| SC11・FC14 [Kim ら 2019・2020](https://arxiv.org/abs/2005.00803)、Manteaux ら 2016 | 計算済みの煙・液体を画像の画風へ寄せる。色の見本に「Kanagawa Wave」 | 計算の後に粒子の位置・値を最適化 | 「様式化」と呼び、量の保存の項で縛る。重みを図で振る。動かした量は数なし | 計算の後で見本の側へ引く学術の例。物理とは呼ばない |
| SC12 [Stevenson-Regla ら 2025](https://researchportal.ip-paris.fr/en/publications/implicit-field-based-stylization-of-2d-and-3d-liquid-animations/) | 粒子の液体の上に、絵らしい水の形（砕ける頂の凹みなど） | 描く段の陰関数の面 | 面積・体積を保つ縛り、様式化と呼ぶ | 唇・爪を描く段で作る道の候補（本文未確認） |

### 1.7 原画の読み（物理の研究・美術史）

| 例 | (1) 出したもの | (2) 原画の形の読み | (3) 物理の外の手の言い方 | (4) この作品への意味 |
| --- | --- | --- | --- | --- |
| SC01 [Cartwright & Nakamura 2009](https://doi.org/10.1098/rsnr.2007.0039) | 原画を巻き波・東京湾の嵐の異常に大きな波と読み「かなりもっともらしい」 | 観察した本物の波の種類＋画家の変形 | 縦の尺度を約 30 % 伸ばした、高さを大きく描いた見込みを名前で挙げる。前の面・唇は測らない | 30 % を戻しても前の面と唇の差は残る（STUDY52）。この差を説明する文献はない |
| SC04・SC05 作図と構図の比（『略画早指南』1812、柳 1977、[加藤・太田 2007](https://doi.org/10.5989/jsgs.41.4_3)） | 円弧の作図、黄金分割で波の高さを決めた説、黄金矩形 | 設計した形 | 物理と比べない | 輪郭の一部は設計された形。高さを物理だけで合わせなくてよい根拠 |
| SC06 爪の読み（[NGV](https://www.ngv.vic.gov.au/essay/the-old-man-mount-fuji-and-the-sea/)、[artscape](https://artscape.jp/study/art-achive/1205252_1984.html)） | 龍・獣の爪、琳派の型、巻き波の噴流の指 | 型と観察の合わせ | どちらも爪の大きさを測らない | 爪は描く段の様式として分けて書く方が、どちらの読みとも合う |
| SC07 大波の移り変わり（1796〜1835） | 30 年以上の描き直し | 設計の積み重ね | 研究者は後の版ほど物理のもっともらしさの側と読む | 原画は一度の観察の写しではない |

### 1.8 もっともらしさの物差しと、作り手の言葉

| 例 | (1) 出したもの | (2) やり方 | (3) 離れの言い方・測り方 | (4) この作品への意味 |
| --- | --- | --- | --- | --- |
| PR16 [Barzel ら 1996](https://perso.liris.cnrs.fr/nicolas.pronost/UUCourses/GamePhysics/literature/Plausible%20motion%20simulation%20for%20Computer%20Graphics%20Animation.pdf)、Chenney & Forsyth 2000 | 剛体の玉で望む結果を得る | 誤差の幅の中で衝突の向きを乱して選ぶ | 物理として／見た目にもっともらしいを分ける。予想しない見えない力とエネルギーの足し過ぎはもっともらしさを下げる。幅は約 8°・10° で、著者が目で決めた | 入口・礁・初めの条件を選ぶのは「物理としてもっともらしい」側。目標へ引く力は誤差の幅の外で、見る人が予想しない力なので、この論文の言い方ではもっともらしさを下げる側【考え：論文は剛体だけで、流体への当てはめは進行役の読み】 |
| SC14 [O'Sullivan ら 2003](https://gv2.scss.tcd.ie/cosulliv/Pubs/fidelity.pdf)、Um ら 2017 | 人が異常に気づく閾値、液体の計算法の人の比べ | 動画を見せて比べてもらう | 本物の参照の映像を並べると評価が揃う（Um）。作業メモだけによる記録で、閾値の数は未確認 | 力の版と重力だけの版を本物の水槽の映像と並べて比べる測り方 |
| AD05 物理の外の助けの力の報告（[OpenSim の手引き](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53086231/_RRA+Best+Practices)、Hicks ら 2015、[Yuan & Kitani 2020](https://arxiv.org/abs/2006.07364)） | 人の動きの計算で、測った動きと力学の食い違いを埋める | 骨盤などに「残りの力」を置き、小さく保つよう調整する（OpenSim）。体に外から残りの力を足して学習し、報酬の罰で小さく保つ（Yuan & Kitani） | 名前を付け、限度と比べる：最大 10〜20 N 未満・平均 5〜10 N 未満（OpenSim、頁を読んだ）、外の力の最大の約 5 %（Hicks ら、二次の資料による、未確認）。Yuan & Kitani は大きさを報告しない | 物理の外の力を名前と限度で報告する確立した形。流体には例がない。§3.2 の「大きさ」の行の形になる |
| PR14 [ゴジラ-1.0](https://cgworld.jp/regular/304-godzilla.html)（U） | 海の計算（形の誘導の有無は未確認） | Houdini | 「かっこよさと物理の正しさの両立はとても難しい」「演出上の嘘は要るが CG としての物理は信じる」 | 同じ緊張を日本の現場の言葉で語った例 |
| GW06 [SideFX の掲示板](https://www.sidefx.com/forum/post/321930/)（U） | 一般のチュートリアルでは「穏やかな浜の波か水槽のしぶき」 | 一般の設定 | 1 件の相談 | 数としては使えない |
| GW11 作り方を公開していない展示（動き出す浮世絵展、Digital×北斎 ほか）（U） | 北斎の大波を動かす展示・映像 | 書かれていない | 書かれていない | 波を起こした条件と原画との差を数で書くことは、同じ題材の展示と違う点になる【考え】 |

### 1.9 資料から形の得方を決められない（U）

| 例 | (1) 出したもの | (2) 形の得方 | (3) 離れの言い方・測り方 | (4) この作品への意味 |
| --- | --- | --- | --- | --- |
| PR03 [Frozen 2](https://www.sidefx.com/community/frozen-ii/) | 筒に巻く嵐の波、25 フィートの崩れる波 | ストークス波の速度の場で FLIP の水槽を動かす。初め・境界・途中ずっとのどれで効かせたかは記事にない（入口なら B、途中ずっとなら G）。25 フィートの場面は形の彫り（S）も | 物理と演出の釣り合いの言葉は少ない | 計算を先に走らせ、人物と構図を後で合わせる順は Q39 の扱いと同じ向き |

ほかに U を含む項目：GW02・GW04（§1.6）、PR14・GW06・GW11（§1.8）。

## 2. 横断して分かったこと

### 2.1 重力だけで届いた所と、届いていない所

- 届いた所【文献・測った】：前へ巻いて唇の下に空気を囲む（Enright 2002 の 3D、本作の 2D の計算）。局所に集まって前へ巻き始める頂（Fochesato ら 2007）。巻き始めに前の面の頂の近くがほぼ鉛直の壁になる（McAllister ら 2019 の向きの広がりのある群、本作の FLIP42。唇の下の前の面の傾きは未確認）。Mihalef ら 2004 も巻く形を出したが、初めの状態が線形の値と釣り合わない（B\*）ので、ここには入れない。
- 届いていない所【文献・測った】：唇の厚み ÷ H は、読んだ論文の値が 0.04〜0.13 で、原画の換算した値 0.17〜0.32 に届く例はない（[作り方の調べ](BigWave_Recipes_ja.md) §3.3）。唇の下の前の面の傾き（原画 64°）を出した文献は見つからない。唇の下の空気の高さも、群を強めた実験（Erinin ら 2023、唇の下の面積 +86 %）を本作に当てて 0.20〜0.24 η_c ほどで、原画の 0.54 η_c 以上に遠い【推定：[形の違いの検討](PeriodicBigWave_Study_ja.md) §1.3】。
- 文献に「届かない」と書いた物はない【文献】。原画を物理で読んだ研究は、むしろ原画を本物の巻き波として「かなりもっともらしい」と書く（Cartwright & Nakamura 2009）。
- 風・流れ・気圧・海底の中では、海底が形を最も動かす見込みである。この計画の以前の 2D の試作（1:4 の斜面と岩棚）で前の面の弦が 58° だったが、3D の試作では 37〜39° に寝た。弦の定義と波の大きさが違い、初めの流速に後で見つけた誤りのある計算でもあるので、向きの例としてだけ読み、そのままは比べられない【測った：前の記録。[物理的にありえる力の調べ](PhysicalForces_BreakingShape_ja.md) §2.6】。

### 2.2 決まった形が要る時の手

- 映画・アニメの制作 15 項のうち、主役の大波の作り方を資料が書くのは 12 項で、12 項ともに S・G・B\* のどれかを含む。3 項（PR04 Avatar、PR06 の浅瀬の主役の波、PR14 ゴジラ-1.0）は書いていない【文献】。前の [Houdini の調べ](HoudiniBigWave_Survey_ja.md)の「映画と講座の大波は、形を先に決めるか途中で導く」と同じ向きになった。
- 制作の作り手は、理由も書く：「いつ・どう崩れるかが決まっているので手順の道具に寄る」（Moana）、「監督は何も偶然に任せない」（Life of Pi）、「本物なら崩れるので、ゆっくり迫る形は計算できない」（Poseidon）【文献】。
- 研究で、砕ける波を扱った制御は、本文を読めた範囲では Mihalef ら 2004（初めの状態の選び）、Moana（物理でない境界）、Pan ら 2013（高い波を持ち上げる。巻く形の評価はない）の 3 つ。ほかに Brousset ら 2015・2016 が外の「波の力」で砕ける波を起こす（要旨だけ）。McNamara ら 2004 は「水面の形を指定せずに、波を決まった時刻に砕く」を将来の課題に挙げた【文献】。計算の途中の力で前へ巻く波を目標の形へ導き、その力の大きさを示した論文は見つからなかった（Brousset らの本文は未確認）。
- 目標が記録の波の時系列なら、造波を直す工学の方法（Fernández ら 2014、McAllister ら 2019）で届かせている。目標が描いた形の時と分けて読む必要がある【文献・考え】。
- 『神奈川沖浪裏』を扱った作品 12 項で、計算の途中に目標へ寄せる力を入れたと書いた物はない。原画に近い形は手か原画の画像から来ていた【文献・推定】。

### 2.3 物理らしさの支え方

文献で見つかった支え方は 6 つ【文献】。

1. 案内そのものを物理の計算から取る：案内が物理の粗い計算なら、導いた計算も正しい物理の解になる（Nielsen & Bridson 2011、Inglis ら 2017）。原画の形の案内には使えない論拠。
2. 力を大きな形にだけかけ、小さな形は物理に任せる（Thürey ら 2006・2009。Pan ら 2013 はしぶきの細い所にかけない）。
3. 制御の後は重力だけに戻す：Moana の「計算の起動」、Mihalef ら（選んだ後は Navier–Stokes だけ）、Treuille ら（最初の一歩だけの制御）、Thürey ら 2007（膜は出た後、重力で弾道に動く）。
4. 本物と測って合わせる・確かめる：Life of Pi の水槽の目盛り、Surf's Up の重力の玉、Fernández ら 2014 の相関。
5. 見る人が予想する力だけを使う：見る人が予想する見えない力（風）はもっともらしさを助け、予想しない力とエネルギーの足し過ぎは下げる（Barzel ら 1996）。Q41 の「風のような、波を自然に生じさせる力」と同じ線にある【考え】。
6. 物理の外の力に名前を付け、限度と比べて報告する：生体の力学の計算の「残りの力」（OpenSim の手引き、Hicks ら 2015）。流体と映像の資料には例が見つからなかった。

### 2.4 原画の側にある物理の外の手

文献は原画の形の一部を、画家が設計した物と読む【文献】：縦の尺度の約 30 % の伸びと高さを大きく描いた見込み（Cartwright & Nakamura 2009）、波頭より下の画面を黄金分割にする高さ（柳 1977 の説）、コンパスの円弧で波を描く方法（『略画早指南』1812）、30 年以上の描き直し、琳派・龍の型としての爪。ただし STUDY52 は縦の伸びを戻して測っており、今の波を縦に 1.3 倍しても唇の下の前の面の傾きは約 25° にしかならない【計算】。前の面と唇の差は、文献が挙げた変形では説明できない【考え】。

### 2.5 物理的にありえる力の大きさ（Q54。[物理的にありえる力の調べ](PhysicalForces_BreakingShape_ja.md) から）

Q54（「物理的にありえるものであれば考慮の余地があります」）を受けた別の調べの見積もりを引く。その調べでは別の者の確かめを受けて数を直しており、下の数は直した後の値である【計算・文献】。比べる相手は今の波（周期 約 9.5 s、水深 42 m、波高 11〜14 m）。

- 風：効くのは水面の圧力で、水面を引きずる応力は重力の 0.002 倍以下で形を変えない。向かい風 U10 20〜60 m/s で、厚さ 1 m の空中の唇に重力の 0.06〜0.6 倍（空気がはがれない流れの上限で 0.4〜1.9 倍）、働くのは崩れる直前の 1〜2 秒。台風の強さ（30 m/s）なら、唇が飛ぶ 0.5〜1 秒に 0.1〜1 m 動かす大きさ。唇を重力に逆らって支えきるには U10 80〜118 m/s が要り、東京湾の周りの記録（最大風速 23〜41 m/s）の 2〜3 倍になる。
- 風の文献の効き：浅い所で崩れる波では、巻きの断面の面積 ÷ 波高² が、追い風の端の 0.2 から強い向かい風の 0.4 だった（実物大の人工の波、[Feddersen ら 2023](https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/crossshore-windinduced-changes-to-fieldscale-overturning-wave-shape/4236FD21F9A9EA5AFCF6ED8966B93596) 図 10。両端どうしの値で、風なしからの変化ではない）。空気と水を解く実験室の大きさの 2D の計算では、唇（噴流）の面積は向かい風でほぼ変わらず（0.219〜0.229 の間）、追い風で約 4 割減った。同じ計算で、前の面の最も急な斜面は、同じ時刻で比べるとどの時刻でも追い風の方が急だった（差 4〜10°）（[Feddersen ら 2024](https://falk.ucsd.edu/pdf/Feddersen_etal2024JFM.pdf) 図 4d・7e）。深い所・中間の水深で集まって崩れる波で、向かい風が巻きを強める証拠は見つからなかった。風は崩れを早めたり遅らせたりする（Douglass 1990）。
- 風で原画の側へ動かせる量の見込み【推定】：唇の下の前の面の傾きは数度〜10° 前後（同じ時刻の比べで急なのは追い風の側で、向かい風で立つ裏付けはない）、唇の下の空気は差の 0〜16 %（中ほど 1 割前後、浅い所で崩れる時だけ）、唇の厚みはほぼ 0。
- 流れ：どこも同じ速さの海流は形を変えない（流れと一緒に動く目で見れば静かな海の波と同じ）【考え】。東京湾の流れは 1 m/s 前後（湾口の潮流は 0.77 m/s 以上、最大は未確認）【文献】。今の波が 1 m/s の逆向きの流れに入ると、線形で高さ 1.18 倍・険しさ 1.35 倍で、今の波はすでに崩れの限界に近いので、高い波より沖で早く崩れる波になる見込み【計算・考え】。流れが前の面・唇・唇の下の空気をどれだけ変えるかの数は、文献に見つからなかった。風が作る表層の薄い流れ（吹送流）は、崩れる前に届く頂の限界を、向かい風の側で 1.08〜1.18 倍、追い風の側で 0.83〜0.92 倍にする【計算：Banner & Phillips 1974 の式、式の形は二次の資料による】。
- 気圧：水に与える加速度は重力の 3×10⁻⁶〜3×10⁻⁵ 倍で、形には効かない。効くのは平均の水面の高さ（1 hPa の低下で約 1 cm）【計算】。
- 物差し：流れと気圧に元のある加速度は、どれも重力の 10⁻⁴ 倍以下。足す力が水の塊に重力の 0.01 倍以上を数秒以上与えるなら、流れや気圧では説明できない。足す力を判断する五つの問い（現実の元・入れる形・大きさ・時間と向き・力なしとの比べ）は、[物理的にありえる力の調べ](PhysicalForces_BreakingShape_ja.md) §4 にある【考え】。

## 3. この作品にとっての意味

### 3.1 目標の形へ引く力（制御の力）の位置

- 分類【考え】：計算の途中で水を目標の形の側へ引く力は G（誘導・制御の力）に当たる。研究の名では「目標へ運ぶ力」（Fattal & Lischinski 2004）、「帰還の力」（Shi & Yu 2005）、「ゴーストの力」（Pan ら 2013）、外の「波の力」（Brousset ら 2016）。制作の名では「誘導つきの計算」（Project Blue Book ほか）。Barzel ら 1996 の言葉では、誤差の幅の外の力なので「物理としてもっともらしい」側には入らず、見る人が予想しない見えない力なので、もっともらしさを下げる側に入る（論文は剛体だけで、流体への当てはめは進行役の読み）。
- 確立した形（制作）：目標の形を決める → 力を効かせる範囲（マスク）と目標の速度の場を作る → 範囲の中だけ寄せる → 力を切った後の崩れ・しぶきは計算に任せる → 混ぜのつまみで効き具合を合わせる（Project Blue Book、Hereafter）。研究では、これに力の罰の重みや係数の値が付く（Treuille ら 2003、Pan & Manocha 2017、Pan ら 2013）。

### 3.2 力を使う時に「意味の分からない力」にしない報告の形

どの力を使う場合も（風の圧力のような物理の力を含む）、次の形で書けば、力の意味と大きさを読む人が確かめられる【考え】。右の欄は先例の有無。

| 項目 | 書く中身 | 先例 |
| --- | --- | --- |
| 名前と現実の元 | 「制御の力」か、現実の何に当たるか（風の圧力、流れなど） | 研究は物理の外の力を名前で区別する（ゴーストの力、物理でない集める項）。生体の力学は「残りの力」と名付ける。現実の元を問うのは Q54 |
| 式と向き | 目標の点へ／目標の速さとの差／形のポテンシャルの勾配／水面の圧力 | Fattal & Lischinski 2004、Shi & Yu 2005、Pan ら 2013（係数の値まで書く） |
| 場所 | 効かせた水の範囲。外は重力だけ | Project Blue Book、Hereafter、Thürey ら（粗い成分だけ） |
| 時間 | 始めと終わり。切った後は重力だけ | Moana の「計算の起動」、Mihalef ら、Treuille ら（最初の一歩だけ）、Thürey ら 2007 |
| 大きさ | 単位質量あたりの力の最大と平均 ÷ 重力 g。現実の力の範囲と並べる | 流体・映像の資料には先例なし。隣の分野では、生体の力学の計算が残りの力を限度と比べて報告する（OpenSim：最大 10〜20 N 未満・平均 5〜10 N 未満。Hicks ら 2015：外の力の最大の約 5 %、未確認）。現実の範囲の目安は §2.5（唇に風で g の 0.06〜0.6 倍。流れ・気圧は 10⁻⁴ 倍以下） |
| 足したエネルギー | 力が水にした仕事 ÷ その時の波のエネルギー | 先例なし（Pan ら 2013 は図で比べただけ。Yuan & Kitani 2020 は罰の項で小さく保つが量は出さない）。Barzel ら 1996 は足し過ぎがもっともらしさを下げると書く。本作の方法の確かめでは、風の圧力の仕事を式と比べた（比 1.03・0.90、[方法の確かめ](../Progress/FLIP_MethodCheck_ja.md) §3.6） |
| 強さを振る | 強さ 0（重力だけ）を含めて何段か走らせ、形の量と並べる | Treuille ら の k_s、Pan & Manocha の r、Raveendran ら の α、Kim ら 2020 の図 |
| 力なしとの差 | 同じ条件で、唇の下の前の面の傾き・唇の下の空気・唇の厚みがどれだけ動いたか | 原画との差を数で書いた例は STUDY52 のほかになし |
| 切った後の確かめ | 唇が自由落下の速さで落ちるか | Surf's Up の重力の玉 |
| 見た目の比べ | 本物の水槽の映像を並べ、何人かに比べてもらう | Um ら 2017、O'Sullivan ら 2003（どちらも作業メモだけによる。閾値の数は未確認） |

### 3.3 指導教員に選んでいただく案

どれを選ぶかは指導教員にお決めいただく。どの案でも、§3.2 の形で書く。

| 案 | 中身 | 文献の先例 | 言えること・言えないこと |
| --- | --- | --- | --- |
| A 重力と造波・海底の条件だけを続ける | 入口の群・礁（[形の違いの検討](PeriodicBigWave_Study_ja.md) の次の案）・群の強さ・向きの集まりの中で条件を変え、原画との差を同じ量で書き続ける。条件は 2D で何本か回して選び（Sel）、選んだ理由と選ばなかった結果も書く。「物理で届いた所／届かない所」として報告する | Enright 2002（2D で棚を選んで 3D）、McAllister ら 2019、Dudley ら 2013、Fernández ら 2014、The Finest Hours、Twigg & James 2007 | 物理の作品として説明しやすい（Q39・Q41）。原画の唇の厚みに届く見込みは文献にない。選ぶ時の目の判断は、基準を先に書く必要がある |
| B 物理的にありえる力を足す（Q54） | 風の水面の圧力を、記録の風速から決まる大きさで入れ、向かい風が巻きを大きくする証拠は浅い所の崩れだけなので、A の礁の案と組み合わせる。力なしの計算と並べて差を測る。流れは、どこも同じ速さなら形を変えず、東京湾の 1 m/s 前後では早く崩す向きなので、入れるなら吹送流を入口の速さの形として入れる（頂の限界 ±1 割）。気圧は形に効かないので入れない。手順と本数は[物理的にありえる力の調べ](PhysicalForces_BreakingShape_ja.md) §6 | Feddersen ら 2023・2024、Douglass 1990、Banner & Phillips 1974、Barzel ら 1996（予想される見えない力） | 力の意味と大きさを現実と比べて言える。動く量は小さい見込み（唇の下の前の面の傾きは数度〜10° 前後で、急になるのは追い風の側、唇の下の空気は差の 0〜16 %、唇の厚みはほぼ 0。§2.5） |
| C 残る差を浮世絵へ移す段に置く | 計算は重力だけのまま残し、原画への寄せ（縦の伸び、高さ、唇の厚み、爪）を浮世絵へ移す段（Q42 の c）の「様式化」として、何を何倍にしたかを名前と数で書く | Cartwright & Nakamura 2009 の 30 % の読み、Thürey ら 2007（唇を名前の付いた係数で足す）、KUBO、teamLab、Eden ら 2007、Kim ら 2020、Stevenson-Regla ら 2025 | 計算の部分は物理のまま言える。学生の 10/8 の扱い（北斎が高く描いた分は浮世絵へ移す段で扱う、Q42）と同じ向き。様式化の量を数で書かないと、手で作った形と区別できなくなる |

名前を付けた制御の力（G）で原画の形へ寄せる道は、確立した形（§3.1）はあるが、Q41・Q54 の基準に合わないので、案に入れていない。

### 3.4 この調べから言えないこと

- 「重力だけでは原画の形に届かない」とは、文献からは言えない。試して測った研究がないからである。言えるのは「描いた形に届いた例がなく、届かせた例は物理の外の手を名指して使っている」までである。
- 目標が物理で起こりうる波なら、重力のまま届かせる方法がある。原画の形が物理で起こりうる形かどうかは、文献から分からない。
- 制作の例は、締め切りと監督の指定で動いている。物理の外の手を使ったことは、届かないことの証拠ではない。
- 制作と作品は離れの量を書かないので、「どれだけ離れたか」の比べはできない。離れを書いていない 10 項は、隠したのか、物理を名乗らないので書く必要がなかったのか、資料から分からない。

## 4. 確かめていないこと・足りないこと

- この段は読むだけの調べ：ダウンロード・インストール・流体の計算・git はしていない。
- 作業メモ（Git 対象外）：この機械の `Unity/Build/SURVEY53/` に 4 つの記録（『神奈川沖浪裏』を扱った作品、流体の制御の研究、映画・アニメの制作、原画の研究と描画の研究）と、まとめた 62 項目の一覧 `items.json`。前の調べ（[作り方の調べ](BigWave_Recipes_ja.md)、[Houdini の調べ](HoudiniBigWave_Survey_ja.md)、[実装の手法の調べ](BigWave_Implementation_Survey_ja.md)、[リアルタイムの調べ](RealtimeBigWave_Survey_ja.md)、[形の違いの検討](PeriodicBigWave_Study_ja.md)、[物理的にありえる力の調べ](PhysicalForces_BreakingShape_ja.md)）で書いたことはくり返さず、要る所で指した。
- 元の 57 項目の大半は、まとめの前に別の者が一次の出典と照らして直した（一覧の `basis` が verified）。そのうち本文が読めず要旨だけで照らした物：FC04、FC05、FC07 の Nielsen ら、FC13 の Chen ら・Li ら、SC05、SC08〜SC10、SC12。直しの一覧は途中で切れて渡ったので、Chenney & Forsyth 2000 の後半と SC14（O'Sullivan ら 2003・Um ら 2017）は作業メモだけによる。
- 確かめの段で足した 5 項目：AD01〜AD03 は前の調べ（作り方の調べ C9・D9、リアルタイムの調べ C1・E3）の記録で、この段で一次の出典は読み直していない。AD04 は要旨を検索の要約で読んだだけ。AD05 は OpenSim の頁と Yuan & Kitani の本文の要約を読み、Hicks ら 2015 は二次の資料だけ（未確認）。
- 見た物は少ない：Sarah Hashem の動画 1 本、HOKUSAI: ANOTHER STORY の来場記事の写真 2 枚、Utsubo の画面の図、Mark J. Stock の小さな図、Moana の 2 本・Frozen 2 の水の馬・The Day After Tomorrow の原稿の図、Thürey ら 2007 の図（前の調べ）。ほかの映像・図は見ていないので、波の高さ・前の面・唇は、どれも文からの読みである。
- 本文を読めなかった物：Shi & Yu 2005、Thürey ら 2006・2009、Nielsen ら 2009・2010、FAB の論文、Brousset ら 2015・2016（要旨だけ）、Stevenson-Regla ら 2025、Chen ら 2024・Li ら 2025、加藤・太田 2007、O'Sullivan ら 2003 の閾値の数、Twigg & James 2007、Hicks ら 2015。
- §2.5 の風・流れ・気圧の数は別の調べ（[物理的にありえる力の調べ](PhysicalForces_BreakingShape_ja.md)）から引いた。10/12 に、その調べの確かめで直した値へ書き直した（噴流の面積の「+5 %」、唇の下の空気の「13〜16 %」、前の面の「数度」を直した）。
- 見つからなかったことは、無いことの証ではない。特に、作り方を公開していない展示・制作（GW11 ほか）に、計算の途中に力を入れて原画へ寄せた物がある見込みは残る【考え】。

## 5. 出典

番号は §1 の表と `items.json` の id。

- 『神奈川沖浪裏』を扱った作品
  - GW01 HOKUSAI: ANOTHER STORY：https://cgworld.jp/article/202504-cgw320-hokusai.html 、https://www.fun-japan.jp/jp/articles/14085
  - GW02 KUBO：https://thefilmstage.com/kubo-and-the-two-strings-director-travis-knight-on-akira-kurosawas-influence-and-studio-ghiblis-legacy 、https://www.slashfilm.com/546075/kubo-and-the-two-strings-travis-knight-interview 、https://www.fxguide.com/?p=187493 、https://awn.com/vfxworld/explore-vfx-laika-s-kubo-and-two-strings
  - GW03 Utsubo：https://www.utsubo.com/ja/blog/hokusai-interactive-installation
  - GW04 teamLab：https://www.teamlab.art/jp/w/blackwaves/ 、https://www.teamlab.art/w/blackwaves_lost_immersed_and_reborn/ 、https://www.teamlab.art/jp/w/skytreemural/
  - GW05 Sarah Hashem：https://80.lv/articles/traditional-japanese-painting-brought-to-life-with-sidefx-houdini 、https://www.linkedin.com/embed/feed/update/urn:li:ugcPost:7193567663355215872?compact=1
  - GW06 SideFX の掲示板：https://www.sidefx.com/forum/post/321930/
  - GW07 Mark J. Stock：https://digitalartarchive.at/database/work/3631
  - GW08 手で作った再現：https://80.lv/articles/japanese-painting-brought-to-life-through-stunning-2d-animation 、https://www.thisiscolossal.com/?p=138774 、https://www.kocpc.com.tw/archives/293197 、https://www.toxel.com/inspiration/2019/12/27/the-great-wave-in-3d/ 、https://ftp.fau.de/pub/graphics/irtc/stills/2000-08-31/dmwave.txt 、https://www.thetvdb.com/series/374687-art-attack/episodes/7518210
  - GW09 画像から作った 3D：https://sketchfab.com/3d-models/the-great-wave-off-kanagawa-katsushika-hokusai-f64171ed4ee243819a12a8031e9754d1 、https://www.printables.com/model/1763457-3d-artwork-the-great-wave-off-kanagawa-hokusai 、https://www.youtube.com/watch?v=IUc19QNQ0hA
  - GW10 Great Wave Dirge：https://hightide2019.westeurope.cloudapp.azure.com/nuxt/artworks/great-wave-dirge
  - GW11 作り方を公開していない展示：https://bijutsutecho.com/magazine/news/report/30024 、https://www.tokyoweekender.com/art_and_culture/design/interact-rare-hokusai-works-ntt-easts-new-digital-art-exhibition/ 、https://kyodonewsprwire.jp/release/202112144975 、https://www.moaart.or.jp/en/?p=37026 、https://www.edinburghmusicreview.com/reviews/0d6v9xbd94fouad2kilo95chg8sy7u 、https://www.scottishopera.org.uk/news/get-to-know-the-great-wave-a-collaboration-that-bridges-cultures-and-honours-hokusai-s-legacy/ 、https://www.tv-tokyo.co.jp/broad_tvtokyo/program/detail/202105/14857_202105292200.html
  - GW12 研究の側（指すだけ）：https://eng.ox.ac.uk/news/famous-freak-wave-recreated-in-laboratory-mirrors-hokusai-s-great-wave 、https://imaggeo.egu.eu/view/14097/
- 流体の制御の研究
  - FC01 Treuille ら 2003：https://grail.cs.washington.edu/projects/control/smokeControl.pdf
  - FC02 McNamara ら 2004：https://grail.cs.washington.edu/projects/control/fluidAdjoint.pdf
  - FC03 Fattal & Lischinski 2004：https://pages.cs.huji.ac.il/danix-lab/cglab/projects/tdsmoke/tdsmoke.pdf
  - FC04 Shi & Yu 2005：https://diglib.eg.org/items/e9ad74b1-8e5d-49dc-9fb5-801d80773461 、https://www.ideals.illinois.edu/items/11020 、https://www.ideals.illinois.edu/items/10826 、https://hub.hku.hk/handle/10722/151992
  - FC05 Thürey ら 2006・2009：https://infoscience.epfl.ch/record/149341/files/thuerey_2006_DPF.pdf 、https://infoscience.epfl.ch/record/149340/files/thuerey_2009_DFC.pdf 、https://cris.fau.de/publications/113685044/
  - FC06 Mihalef ら 2004：https://www.math.fsu.edu/~sussman/BreakingWavesElectronic.pdf
  - FC07 Nielsen ら 2009・2010、Inglis ら 2017：https://nafees.net/publications/2009-08-Variational-Smoke-Guiding/ 、https://diglib.eg.org/items/7fde3794-e5a3-4cb8-a861-379cef4121d8 、https://ar5iv.labs.arxiv.org/html/1611.03677
  - FC08 Nielsen & Bridson 2011：https://www.cs.ubc.ca/~rbridson/docs/nielsen-siggraph2011-guidedfluid.pdf
  - FC09 Raveendran ら 2012：https://faculty.cc.gatech.edu/~turk/paper_pages/2012_controlling_liquids/index.html
  - FC10 Pan ら 2013：https://www.cs.columbia.edu/~cxz/publications/sketchy_fluids.pdf
  - FC11 Pan & Manocha 2017：https://ar5iv.arxiv.org/html/1608.01102 、https://gamma.cs.unc.edu/STMG/
  - FC12 FAB と Moana：https://disneyanimation.com/publications/fluxed-animated-boundary-method 、https://history.siggraph.org/?p=102377
  - FC13 Holl ら 2020、Chen ら 2024、Li ら 2025：https://arxiv.org/abs/2001.07457 、https://dgp.toronto.edu/projects/fluidcontrol 、https://arxiv.org/abs/2511.01259
  - FC14 Kim ら 2020、Manteaux ら 2016：https://ar5iv.labs.arxiv.org/html/2005.00803 、https://research-explorer.ista.ac.at/record/1136
  - FC15 Fernández ら 2014：https://icce-ojs-tamu.tdl.org/icce/article/download/7507/pdf_780/31186
  - FC16 Brousset ら 2015・2016：https://doi.org/10.1016/j.cag.2016.03.003 、https://hal.archives-ouvertes.fr/hal-01285926 、https://hal.archives-ouvertes.fr/hal-01227419 （要旨は検索の要約で読んだ）
- 映画・アニメの制作
  - PR01 Moana の海の人物：https://media.disneyanimation.com/uploads/production/publication_asset/163/asset/Moana-_Performing_Water.pdf
  - PR02 Moana の崩れる波：https://history.siggraph.org/wp-content/uploads/2022/09/2017-Talks-Byun_Moana-Crashing-Waves.pdf
  - PR03 Frozen 2：https://www.sidefx.com/community/frozen-ii/ 、https://media.disneyanimation.com/technology/publications/2020/Frozen2_CreatingTheWaterHorse_talk.pdf
  - PR04 Avatar: The Way of Water：https://firedbydesign.com/?p=15440 、https://unity.com/blog/industry/technology-behind-avatar-the-way-of-water 、https://beforesandafters.com/2022/12/21/why-the-cg-water-in-the-way-of-water-looks-so-good/ 、https://blogs.nvidia.com/blog/2023/03/07/oscar-visual-effects/ 、https://history.siggraph.org/?p=108548
  - PR05 Life of Pi：https://www.cgw.com/Publications/CGW/2013/Volume-35-Issue-7-Dec-2012-/Still-Waters-Run-Deep.aspx 、https://www.fxguide.com/?p=37947
  - PR06 The Finest Hours：https://www.fxguide.com/quicktakes/making-the-finest-hours/ 、https://www.cgw.com/Press-Center/Web-Exclusives/2016/The-Finest-Hours.aspx
  - PR07 Interstellar：https://www.scientificamerican.com/blog/observations/parsing-the-science-of-interstellar-with-physicist-kip-thorne/ 、https://www.postmagazine.com/Publications/Post-Magazine/2014/November-1-2014/VFX-Interstellar.aspx
  - PR08 The Perfect Storm：https://www.cgw.com/Publications/CGW/2000/Volume-23-Issue-7-July-2000-/Sea-Change.aspx
  - PR09 Poseidon：https://www.cgw.com/Publications/CGW/2006/Volume-29-Issue-4-April-2006-/Size-Matters.aspx 、https://www.fxguide.com/?p=21422
  - PR10 The Day After Tomorrow：https://history.siggraph.org/wp-content/uploads/2022/12/2004-Talks-Iversen_Growing-Up-with-Fluid-Simulation-on-The-Day-After-Tomorrow.pdf
  - PR11 Surf's Up：https://www.cgw.com/Publications/CGW/2007/Volume-30-Issue-6-June-2007-/Radical-Dude.aspx 、https://patents.google.com/patent/US8610721B2/en
  - PR12 Hereafter・Aquaman：https://www.fxguide.com/?p=21969 、https://www.artofvfx.com/aquaman-bryan-hirota-vfx-supervisor-scanline-vfx/
  - PR13 Project Blue Book ほか：https://sidefx.com/community/houdini-connect-project-blue-book 、https://www.sidefx.com/community/adrift/ 、https://cgworld.jp/flashnews/01-202607-Houdini-Swapped.html 、https://www.sidefx.com/stories/moana-2/
  - PR14 ゴジラ-1.0：https://cgworld.jp/regular/304-godzilla.html 、https://realsound.jp/tech/2024/06/post-1693763_2.html
  - PR15 様式化した水：https://www.allcinema.net/cinema/pdf/327529 、https://cgworld.jp/interview/201910-tenkinoko02.html 、https://cgworld.jp/flashnews/one-animevfx-water.html
  - PR16 Barzel ら 1996、Chenney & Forsyth 2000：https://perso.liris.cnrs.fr/nicolas.pronost/UUCourses/GamePhysics/literature/Plausible%20motion%20simulation%20for%20Computer%20Graphics%20Animation.pdf 、https://cs.brown.edu/people/jhughes/papers/Barzel-PMS-1996/main.htm 、https://pages.cs.wisc.edu/~schenney/research/directing/mcmc/mcmc.html
- 原画の研究・美術史・描画の研究
  - SC01 Cartwright & Nakamura 2009：https://doi.org/10.1098/rsnr.2007.0039
  - SC02 Dudley ら 2013：https://pmc.ncbi.nlm.nih.gov/articles/PMC3645210/
  - SC03 McAllister ら 2019：https://doi.org/10.1017/jfm.2018.886 、https://blogs.egu.eu/geolog/2019/07/08/imaggeo-on-mondays-recreating-monster-waves-in-art-and-science/ 、https://eng.ox.ac.uk/news/famous-freak-wave-recreated-in-laboratory-mirrors-hokusai-s-great-wave （造波の直しの回数は [作り方の調べ](BigWave_Recipes_ja.md) B1 から）
  - SC04 『略画早指南』：https://en.wikipedia.org/wiki/The_Great_Wave_off_Kanagawa （と SC01 の図 6）
  - SC05 加藤・太田 2007、柳 1977：https://www.jstage.jst.go.jp/article/jsgs1967/41/4/41_4_3/_article/-char/ja/ （柳は SC01 の注 19 からの孫引き）
  - SC06 爪の読み：https://www.metmuseum.org/art/collection/search/56353 、https://www.britishmuseum.org/collection/object/A_2008-3008-1 、https://artscape.jp/study/art-achive/1205252_1984.html 、https://www.ngv.vic.gov.au/essay/the-old-man-mount-fuji-and-the-sea/
  - SC07 大波の移り変わり：https://www.ngv.vic.gov.au/essay/the-old-man-mount-fuji-and-the-sea/ 、https://mymodernmet.com/hokusai-great-wave-evolution 、https://www.openculture.com/2018/12/the-evolution-of-the-great-wave-off-kanazawa.html
  - SC08 Selle ら 2004、Eden ら 2007：https://pages.cs.wisc.edu/~schenney/research/npar/smoke/index.html 、https://cal.cs.umbc.edu/Papers/Eden-2007-AMF/
  - SC09 Browning ら 2014：https://pixl.cs.princeton.edu/pubs/Browning_2014_SKA/index.php
  - SC10 LazyFluids、Fluidymation：https://dcgi.fel.cvut.cz/~sykorad/lazyfluids.html 、https://dcgi.fel.cvut.cz/~sykorad/fluidymation.html
  - SC11 Kim ら 2019・2020：https://arxiv.org/abs/1905.07442 、https://arxiv.org/abs/2005.00803
  - SC12 Stevenson-Regla ら 2025：https://researchportal.ip-paris.fr/en/publications/implicit-field-based-stylization-of-2d-and-3d-liquid-animations/ 、https://diglib.eg.org/handle/10.2312/stag20251324
  - SC14 O'Sullivan ら 2003、Um ら 2017：https://gv2.scss.tcd.ie/cosulliv/Pubs/fidelity.pdf 、https://ge.in.tum.de/?p=158
- 確かめで足した項目
  - AD01 Enright 2002（Stanford の学位論文 §4.5.4）：https://web.stanford.edu/group/fpc/Publications/Enright%20Thesis.pdf （[作り方の調べ](BigWave_Recipes_ja.md) C9 の記録による）
  - AD02 Thürey・Müller-Fischer・Schirm・Gross 2007：https://matthias-research.github.io/pages/publications/breakingWaves.pdf 、https://patents.google.com/patent/US8204725 （[リアルタイムの調べ](RealtimeBigWave_Survey_ja.md) C1 の記録による）
  - AD03 式で作る崩れる波（Fournier & Reeves 1986、Peachey 1986、Gonzato & Le Saëc 2000、Jeschke ら 2003、de Lima ら 2010）：https://www.labri.fr/perso/gonzato/Articles/GONZATO_Wave_JVCS2000.pdf 、https://sbgames.org/papers/sbgames10/computing/full/full4.pdf （[リアルタイムの調べ](RealtimeBigWave_Survey_ja.md) E3 の記録による）
  - AD04 Twigg & James 2007「Many-Worlds Browsing for Control of Multibody Dynamics」ACM TOG 26(3)：https://history.siggraph.org/?p=115323 、https://www.cs.princeton.edu/courses/archive/fall07/cos597B/papers/twigg-many-worlds.pdf （要旨を検索の要約で読んだ）
  - AD05 物理の外の助けの力の報告：OpenSim「RRA Best Practices」https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53086231/_RRA+Best+Practices （頁を読んだ）、Hicks, Uchida, Seth, Rajagopal & Delp 2015「Is my model good enough?」J. Biomech. Eng. 137(2):020905、https://pubmed.ncbi.nlm.nih.gov/25474098/ （5 % は二次の資料による、未確認）、Yuan & Kitani 2020「Residual Force Control for Agile Human Behavior Imitation and Extended Motion Synthesis」NeurIPS 2020、https://arxiv.org/abs/2006.07364 、https://ar5iv.labs.arxiv.org/html/2006.07364 （本文の要約を読んだ）
- §2.5 の文献（[物理的にありえる力の調べ](PhysicalForces_BreakingShape_ja.md) §9 と同じ）：Feddersen ら 2023 https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/crossshore-windinduced-changes-to-fieldscale-overturning-wave-shape/4236FD21F9A9EA5AFCF6ED8966B93596 、Feddersen ら 2024 https://falk.ucsd.edu/pdf/Feddersen_etal2024JFM.pdf 、Douglass, S. L. (1990) Influence of wind on breaking waves. J. Waterway, Port, Coastal, Ocean Eng. 116(6), 651–663、Banner, M. L. & Phillips, O. M. (1974) J. Fluid Mech. 65（式は二次の資料による）。

## 6. 確かめを受けて直したこと（10/12）

作っていない別の者が、この文書を `items.json` の全項目、Q52〜Q55 の記録、前の調べ、SURVEY54 の作業メモと照らし、足りない先例を探した。受けて直したのは次のとおり。§2.1・§2.5・§3.3・§4 の風と海底の数は、[物理的にありえる力の調べ](PhysicalForces_BreakingShape_ja.md) の確かめでも同じ日に直された。

| 直した所 | 初めの書き方 | 直した後 |
| --- | --- | --- |
| 一枚目・§0 の ① | 決まった形が要る制作と研究は、物理の外の手を足していた | 目標が物理で起こりうる波なら重力のまま届かせる手がある（Fernández ら、McAllister ら、選び）。描いた形の時に、書かれた例はどれも物理の外の手を足していた、と分けた |
| §0 の ① | 選び（Sel）を「重力だけでなく足す手」に数えた | 選びと造波の直しを「物理だけで目標へ届かせる手」に入れた |
| 一枚目・§0 の ③ | 離れは隠さず書かれていた | 書いた資料は名前を付けて書く。10 項は何も書いておらず、隠したかは判断できない |
| §0 の ②・SC03 の行 | 似たと言われた 120° は前へ巻かない【文献】 | 写真の角度は書かれておらず、120° 側と読むのは【推定】 |
| §2.1 | Mihalef ら 2004 を重力だけで届いた例に入れた | Mihalef ら は B\* なので外し、Enright 2002（重力だけの 3D の巻き）を足した |
| FC06 の行 | 初めの速度は線形の値の 2.5〜5.3 倍（印なし） | 一覧の ω が線形の分散の値の約 2.5〜5.3 倍【計算・考え】 |
| §2.1 の海底 | 海底は形を最も動かす条件、弦 58° | 風・流れ・気圧・海底の中で、と範囲を書き、3D の試作では 37〜39° だったこと、初めの流速に誤りのある計算であることを書いた |
| §2.2 | 制作 15 例で重力だけで応えた例はない | 作り方を書いた 12 項はどれも S・G・B\* を含み、3 項は書いていない |
| 唇の厚み | 一枚目は H、頭は η_c で書き、換算を書かなかった | H に揃え、原画の値は本作の H ÷ η_c を借りた【推定】と書き、原画の唇は泡と爪を含む描いた形と書いた |
| 前の面 | 「立った前の面」と「ほぼ鉛直の前の面」が同じ量に読めた | 「唇の下の前の面の傾き（0.1〜0.5 η_c の弦）」と「巻き始めの頂の近くの壁」を分けて名前で書いた |
| 力 ÷ g の先例 | 研究にも制作にも見つからない | 流体・映像の資料では、に限った。隣の生体の力学の「残りの力」の報告（AD05）を足した |
| Barzel ら の読み | 目標へ引く力は「見た目のもっともらしさ」の側 | 誤差の幅の外で、予想しない力なのでもっともらしさを下げる側。剛体だけの論文で、流体への当てはめは読みと書いた。8°・10° は著者の目の判断と書いた |
| 分類 | PR01・PR03 を G、GW03 を S/F、PR08 を G | PR01 は S（G は従）、PR03 は U、GW03 は F＋初、PR08 は G に近い。HOKUSAI: ANOTHER STORY の S は【考え】 |
| 数え | 57 項目と書くだけ | 群ごとの数えの表、重なり、要旨だけで照らした項目を書いた |
| 足りない先例 | — | Enright 2002、Thürey ら 2007、式で作る崩れる波、Twigg & James 2007、生体の力学の残りの力を足した（AD01〜AD05） |
| §2.5・案 B の風と流れ | 唇の下の空気は差の 13〜16 %、噴流の面積 +5 %、前の面は数度。流れは加速度だけ | 確かめの後の値（差の 0〜16 %、唇の厚みほぼ 0、前の面は数度〜10° 前後で急になるのは追い風の側）に直した。流れが形に効く道（流れの変わり目、吹送流）と、入れない理由を書いた |
| 一枚目 | 前置き 8 行、分かったことが長い、「8 つに分けた」、次に日付なし | 前置きを §1・§4 へ移し、分かったことを 3 行に、表は 9 つと書き、次に日付の案を足した |
| 言葉 | 「ただ一つの例」と言い切る語が 2 か所 | FC06・SC03 の行で外した（ほかの例が表にあるため） |

（2026-10-12 追記：学生の判断で、学生自身が手元で試した版への言及をこの報告から除いた。）
