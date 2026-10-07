# D3 先行の作品と研究の調べ（新しさの言い方を利用者が決めるための材料）

> この文書は、D3 の調べ `Unity/Build/FLIP39/D3/prior_works_ja.md`（2026-10-07 19:53〜20:13） を 2026-10-08 にリポジトリへ写したものである。本文と出典は元のまま（直したのは、制作手順へのリンクの位置と、個人のパスを含む一時ファイルの書き方だけ）。調べの後に行った実験（E・R）の結果と、この調べの見込みが当たったか外れたかは [流体の高い波の報告](../Progress/FLIP_TallWave_ja.md) に書いた。本文の `Unity/Build/FLIP39/` は Git 対象外の作業フォルダーで、リポジトリには入っていない。


- 日付：2026-10-07 19:53〜20:13（時間の枠は 1.5 時間）。調べだけで、計算はしていない（runs.jsonl への記録はない）。
- 指示の元：制作手順の Q39（10/7 の個別ゼミ）。指導教員は「これまでの作品にも絵のように動く波はある」「どこで差をつけるの?」「視点を船の上に置くだけでは新しさにならない」「写実的な流体の計算は既にある」と述べ、新しさの言い方は利用者自身の研究の中身から出すよう求めた。この文書はその判断の材料だけを集める。**新しさの主張は書かない。** 空いている所は第 5 節に、利用者への問いとして並べる。
- 調べ方：Web の検索（約 50 回）と、ページの取得（英語と日本語）。ページの多くは要約の道具を通して読んだので、原文の全文を読んでいない所がある。全文を読んだのは、Moana の講演の原稿（PDF から文字を取り出した）、USC ICT の WSSOF の紹介（同じ）、事前の物理の確かめの記録（進行役の一時フォルダーにある事前の確かめの記録の physics の部分）の 3 つ。
- 印の意味：【資料】は出典に書いてある事。【資料になし】は読んだ資料に書かれていない事（しなかったとは限らない）。【推定】は進行役の読み。

## 0. まとめ（観察。主張ではない）

調べた約 55 件を、波の作り方で次の 8 つに分けた。

| 区分 | 波の作り方 | 主な例 |
| --- | --- | --- |
| A | 手で描く・手で形を作る（手描き、3DCG のキー、ブラシ、積み木） | Bo Cao の 2D アニメーション、動き出す浮世絵展、James R. Eads の Tilt Brush、LEGO |
| B | 大きな形は手で決め、流体計算は表面・しぶき・船の周りに使う | Poseidon、Interstellar、Moana（波の変形器）、Moana 2、HOKUSAI: ANOTHER STORY |
| C | 流体計算だが、境界の条件・誘導・制御で形や砕ける時を決める | Moana（完全な流体計算の版）、The Perfect Storm、Houdini の Guided Ocean Layer、Mihalef ら 2004 |
| D | 一般の海の面（スペクトル・FFT）。水面の張り出しは表せない | Sea of Thieves、Avatar の海の出発点、Powerboat VR（方法は書かれていない） |
| E | 水深で平均した物理の式（Boussinesq など）。浅くなる・屈折・砕けによる減りを計算するが、前へ巻く形は表せない | Celeris Base（VR 対応）、WSSOF（VR の船の模擬）、Ervin ら 2023（FUNWAVE の計算を Unreal Engine の VR へ） |
| F | 物理の仕組み（波の群の集中、向きの違う波の重なり）で一つの大波を起こす実験・数値計算 | McAllister ら 2019（FloWave）、Rapp & Melville 1990、Mostert ら 2022（初めの波の形から） |
| G | 実際の海の撮影 | Red Bull の Big Wave Surfing（Apple Vision Pro）、Nazaré の展示 |
| H | 流体計算と書かれているが、波の起こし方は書かれていない | teamLab の Black Waves、Ars Electronica の The Wave、Kubo の冒頭の波 |

観察：

1. 『神奈川沖浪裏』を動かした・立体にした・VR にした作品を 14 件挙げた（第 1 節）。見る人は絵の前に立つか、絵を広げた空間の中を歩く形が多い。動く波は A か B か H で、大波が物理の条件から生まれることを示した資料は見つからなかった。
2. 映画の大波は B と C が多い（第 2 節）。作り手が「ゆっくり迫る巨大な波は計算ではできない（本物の波なら崩れる）ので手で形を作った」と述べた例がある（Poseidon）。完全な流体計算で砕かせた例（Moana）も、境界の条件を、物理ではあり得ない急な波の条件へ変えて砕かせている。
3. 物理の仕組みで一つの大波を起こす仕事（F）は、実験室と数値計算の研究にある。見る人は水槽の横のカメラの写真や動画を見る。
4. VR で波の物理の計算を見せる例（E。船を操る VR を含む）はあるが、水深で平均した式なので、前へ巻く形は表せない【推定：式の性質から。Thürey ら 2007 も高さの場では砕ける波を表せないと書いている】。
5. 今回の調べでは、「物理の仕組みで生まれた一つの大波を、実物の大きさで、船の上から HMD で、崩れる瞬間まで体験する」例は見つからなかった。ただし調べの範囲は狭い（第 6 節）。見つからなかったことは、無いことの証ではない。

## 1. 『神奈川沖浪裏』を動かした・立体にした・VR にした作品

### 1-1 teamLab「Black Waves」（2017 年 2〜4 月に台北・華山1914文創園区で展示、ほかの会場でも展示）と「Black Waves: Lost, Immersed and Reborn」（2019 年）

- 何か：暗い部屋の壁と床に、線で描いた波を映す没入型の映像作品。音は高橋英明。
- 波の作り方（H）【資料】：数十万の水の粒の相互作用を計算し、3 次元の空間で水の動きを計算する。粒の動きに沿って線を引き、波の表面に描く。teamLab は、東アジアの古い絵で水が線の重なりで描かれることを手がかりにしたと書く。視点を固定しない描き方を「超主観空間」と呼ぶ。
- 見る人の体験【資料】：暗い部屋で壁の波に囲まれる。時間を忘れるという感想が記事にある。
- しない事・資料にない事：波をどんな物理の条件で起こすか、大波が崩れるか【資料になし】。北斎の名前は第三者の紹介文にはあるが、読んだ範囲の teamLab の文は、東アジア・日本の古い絵の水の線を挙げ、北斎の名は出していない。HMD ではない。船はない。
- 出典：https://www.teamlab.art/w/black_waves/amosrex/ 、https://neocha.com/magazine/black-waves/ 、https://www.teamlab.art/w/blackwaves_lost_immersed_and_reborn/

### 1-2「HOKUSAI: ANOTHER STORY in TOKYO」（東急プラザ渋谷 3F、2025-02-01〜08-11）

- 何か：北斎の世界を映像・音・振動で体験する展示。最後の部屋で『神奈川沖浪裏』の荒れた海を大きな Crystal LED の画面に映し、風と床の振動と音を合わせる（約 12 分）。映像は RED、写実の波は inbetween、触覚はソニーの技術。
- 波の作り方（B）【資料：CGWORLD 2025 年 4 月号 vol.320 の記事】：Houdini を中心に、シミュレーションを土台にして手で動きを付け、北斎の印象に寄せた。大波の形は計算の結果を保存して混ぜ合わせた（ブレンド）。写実の波から浮世絵の波へ段階的に移す構成。Cinema 4D と After Effects も使った。
- 見る人の体験【資料】：画面の前に立ち、波が自分へ迫るように感じ、風と床の振動を受ける。来場者の記事に、思わず身を引いたとある。
- しない事・資料にない事：HMD ではない。船の上の位置ではない【資料になし】。大波の形は混ぜ合わせと手の動きで決めており、流体の条件から一つの大波を生んだとは書かれていない。どんな流体計算（FLIP か海のスペクトルか）かは【資料になし】。
- 出典：https://cgworld.jp/article/202504-cgw320-hokusai.html 、https://www.fun-japan.jp/en/articles/14085 、https://www.timeout.com/tokyo/art/hokusai-another-story-in-tokyo

### 1-3 NTT 東日本「Digital×北斎【序章】」（NTT インターコミュニケーション・センター［ICC］、2019 年 11 月から。終わりは資料により 2020 年 2 月または 3 月）

- 何か：高精細の複製（DTIP という画像処理）を使った北斎のデジタル展示。その中に、畳の部屋で HMD を着けて『神奈川沖浪裏』を見る VR があった。
- 波の作り方（H）【資料：英語の紹介記事】：HMD の立体視で絵に疑似の奥行きを付ける。波が揺れ、しぶきが顔へ飛び、舟が揺れる。
- 見る人の体験【資料】：床の足跡の印に立ち、絵の方へ歩み寄る。舟には乗らず、絵の前に立つ。
- しない事・資料にない事：波の動きをどう作ったか、大波が崩れるか【資料になし】。元は絵の画像なので、立体の水の計算ではない【推定】。
- 出典：https://www.tokyoweekender.com/art_and_culture/design/interact-rare-hokusai-works-ntt-easts-new-digital-art-exhibition/ 、https://news.livedoor.com/article/detail/24135439/

### 1-4 KDDI・KDDI 総合研究所・NHK エデュケーショナル「バーチャル浮世絵」（配信開始 2021-12-15）

- 何か：浮世絵の風景を 360 度の映像へ広げた VR の動画。『神奈川沖浪裏』と広重の作品の 2 つ。
- 波の作り方（A か H）【資料】：絵を 360 度の CG に広げる。22.2 チャンネルの立体音響で、絵の各所に近づくと波の音や人の声が聞こえる。
- 見る人の体験【資料】：仮想の空間の中を動き、音で絵の世界に入る。
- しない事・資料にない事：波が動くか、崩れるか【資料になし】。主役は音である。
- 出典：https://kyodonewsprwire.jp/release/202112144975

### 1-5「動き出す浮世絵展 TOKYO」（寺田倉庫 G1 ビル、2024-12-21〜2025-03-31）

- 何か：浮世絵 300 点以上をもとにした、3DCG アニメーションと投影の没入型展示。「藍」の部屋で『神奈川沖浪裏』の波を中心に、ほかの浮世絵の海を合わせて映す。
- 波の作り方（A）【資料】：浮世絵の線のまま 3DCG で動かし、投影する。
- 見る人の体験【資料】：浮世絵を貼り合わせたような空間に立つ。
- しない事：流体の計算、HMD、船の位置【資料になし】。
- 出典：https://bijutsutecho.com/magazine/news/report/30024

### 1-6 James R. Eads の Tilt Brush による VR の『神奈川沖浪裏』（番組 Art Attack、VR Scout、2018-04-30 放送）

- 何か：画家が VR の中のブラシ（Tilt Brush）で名画を立体に描き直す番組の 1 回。
- 波の作り方（A）【資料】：手で描いた筆の跡。作者は描きながら舟に座ってみたと紹介されている。
- しない事・資料にない事：波が動くか【資料になし】。流体の計算はしない。
- 出典：https://www.thetvdb.com/series/374687-art-attack/episodes/7518210 、https://www.artsupplies.co.uk/blog/iconic-paintings-recreated-in-virtual-reality/ （後者は今回 403 で開けず、検索の抜き書きだけ）

### 1-7 Bo Cao の 2D アニメーション（年は記事に書かれていない）

- 何か：『神奈川沖浪裏』の場面を広げて、荒れた海を動かした 2D のアニメーション。
- 波の作り方（A）【資料】：Toon Boom Harmony で 1 コマずつ手で描いた。約 1 年半かかり、波がいちばん手間だった。
- しない事：流体の計算、立体、VR。
- 出典：https://80.lv/articles/japanese-painting-brought-to-life-through-stunning-2d-animation

### 1-8 映画『KUBO／クボ 二本の弦の秘密』（LAIKA、2016）の冒頭

- 何か：夜の嵐の海で、小舟の母と赤ん坊が巨大な波に向かう場面。人形の撮影と CG を合わせた映画。北斎のような波という評は第三者の記事にある。
- 波の作り方（H、手の比重が大きい）【資料】：Houdini の流体計算で動きを出し、波の模様と細部は Mari で手で描いた。流れの向きの絵とノイズで動いて見せる。様式化した美術の絵、ごみ袋やシャワーカーテンで作った撮影の試し、計算した水の動きを、約 6 か月かけて合わせた。
- 見る人の体験：映画の観客として、小舟と大波の場面を画面で見る。
- しない事・資料にない事：大波の大きな形を計算で作ったか、手で作ったか【資料になし】。HMD ではない。
- 出典：https://www.artofvfx.com/?p=16167 、https://www.fxguide.com/?p=187493 、https://foundry.com/industries/film-television/kubo-behind-the-scenes

### 1-9 そのほか（短く）

| 作品 | 波の作り方 | 見る人の体験 | 出典 |
| --- | --- | --- | --- |
| 映画『HOKUSAI』（橋本一 監督）の「怒涛図」の場面 | 吊るした水槽に光を当てた揺らぎ（実物の水と光） | 映画の観客 | https://press.moviewalker.jp/news/article/224041/p2/ |
| MOA 美術館「The Great Wave × Digital 2.0」（2025-04-25〜06-10） | 高精細の画像を大きな画面に映す | 本物の版画と並べて見る | https://www.meer.com/en/91952-the-great-wave-digital-2-point-0 |
| Google Arts & Culture の Art Projector | 版画を実物大で部屋に置く AR（動かない） | 携帯電話で近づいて見る | https://artsandculture.google.com/story/6gUh_88uR5Q89w |
| 三井淳平の LEGO の『神奈川沖浪裏』（阪急ブリックミュージアム） | 5 万個の積み木を手で組む。作者は波が崩れる動画と論文を調べた | 立体の彫刻を見る | https://www.thisiscolossal.com/?p=138774 |
| Scottish Opera「The Great Wave」（藤倉大 作曲、2026 年 2 月グラスゴー・エディンバラ）と、ロビーの「Digital x Hokusai in Scotland」 | 舞台の波の見せ方は【資料になし】 | 歌劇と北斎の生涯 | https://www.scottishopera.org.uk/news/digital-technology-brings-to-life-the-works-of-iconic-japanese-artist-katsushika-hokusai-in-an-exhibition-presented-alongside-scottish-opera-s-world-premiere-production-of-the-great-wave/ |
| SideFX の掲示板の個人の質問（Houdini Apprentice） | 『神奈川沖浪裏』を Houdini で試したが、穏やかな浜の波か水槽のしぶきにしか見えないという相談 | （作品ではない。試みの記録） | https://www.sidefx.com/forum/post/321930/ |

## 2. 流体計算で作った砕ける波（映画・VFX・ゲーム・CG の研究）と、極端な波の科学

### 2-A 映画・アニメーション

#### The Perfect Storm（ILM、2000）

- 何か：漁船 Andrea Gail が嵐の巨大な波に挑む映画。340 の特殊効果の場面。
- 波の作り方（C）【資料：CGW 2000 年 7 月号】：流体計算で海の動きの見本（約 20 種の海）を作り、そこから選ぶ。波を現実より早く育てる、決めたコマで砕かせる、寄せ合わせる、巨大な波にする、という制御を持たせた。しぶき・泡・霧は Maya の粒子、表面は RenderMan の複雑な陰影で仕上げた。
- 見る人の体験：映画の観客として画面で見る（物語は漁船の上）。
- しない事：巨大な波の育ち方を、現実の集中の仕組みに任せてはいない。砕ける時は制作の都合で決めている【資料】。最後の巨大な波だけの作り方は【資料になし】。
- 出典：https://www.cgw.com/Publications/CGW/2000/Volume-23-Issue-7-July-2000-/Sea-Change.aspx 、https://www.ilm.com/vfx/the-perfect-storm/

#### Poseidon（ILM、2006）

- 何か：巨大な波（約 150〜200 フィート）が客船を転覆させる映画。
- 波の作り方（B）【資料：CGW 2006 年 4 月号】：巨大な波の大きな形と動きは、手で形を作り振り付けた。作り手は、ゆっくり進んで船へ迫る 200 フィートの波は計算では作れない、本物なら崩れるからだ、と述べている。流体計算（Stanford の Fedkiw らの PhysBAM を ILM の道具に組み込んだもの）は船の周りの水のぶつかりに使った。計算は並列化して細かいしぶきを出した。
- しない事：大波の形を流体の条件から生むことはしていない【資料】。
- 出典：https://www.cgw.com/Publications/CGW/2006/Volume-29-Issue-4-April-2006-/Size-Matters.aspx 、https://www.fxguide.com/?p=21422 、https://en.wikipedia.org/wiki/Ronald_Fedkiw

#### Interstellar（Double Negative、2014）のミラーの星の巨大な波

- 何か：高さ 1,200 m ほどの潮の波（物語の中では巨大な天体の引力による）。
- 波の作り方（B）【資料：Post Magazine 2014-11】：形を細かく制御するため、まず普通の CG アニメーション（変形器）で波を動かした。その上の水面・波頭・しぶき・白い泡に、物理の計算を大量に使った（DNEG の Squirt、Houdini ほか）。
- しない事：波の大きな形は物理の条件からではない【資料】。
- 出典：https://www.postmagazine.com/Publications/Post-Magazine/2014/November-1-2014/VFX-Interstellar.aspx 、https://dneg.com/show/interstellar

#### Life of Pi（Rhythm & Hues・MPC、2012）

- 何か：救命ボートの少年の漂流。役者の撮影には台中の格納庫に作った長さ 230 フィートの造波水槽を使った。
- 波の作り方（C）【資料】：嵐の場面は水面全体を流体計算にし、高さ 20〜30 フィートの波を出した。監督は計算の結果に美術の指示を入れることを求めた。
- 見る人の体験：映画の観客として画面で見る（物語は救命ボートの上）。
- しない事：一つの大波の集中ではなく、嵐の海の全体【資料から読める範囲】。
- 出典：https://www.motionpictures.org/?p=342 、https://www.fxguide.com/?p=37947 、https://empireonline.com/movies/features/life-pi-vfx

#### Moana（Walt Disney Animation Studios、2016）— 講演の原稿を全文で読んだ

- 何か：40 を超える「走る波・砕ける波」の場面。
- 波の作り方（B と C）【資料：Byun & Stomakhin, SIGGRAPH 2017 Talks「Moana: Crashing Waves」】：
  - 一つ目は手順による波の変形器。断面の形の変化を、キーになる断面の曲線の列で与える（手で描いた曲線でも、式の曲線でもよい）。波の形・動き・画面の構図を、場面の美術の必要どおりに決める。白い水は、変形器が渡す波頭の場所と初めの速さから計算する。津波の場面では、計算済みの砕ける波 10 種を並べて変形した。
  - 二つ目は完全な流体計算（APIC）。ストークス波の 1 周期を、波と一緒に動く枠で計算する。境界の条件を、物理ではあり得ないほど急な波の条件へ変えると波が砕ける。条件を波に沿って変えると、端から砕けるチューブのような形もできる。船や人物と近くで関わる場面に使った。
  - 原稿は、映画ではいつ・どう砕けるかを決める要求があるので、手順の道具が使われがちだと書く。
- しない事：どちらの方法も、波の集中や浅くなることで大波を育てる形ではない【資料】。
- 出典：https://history.siggraph.org/wp-content/uploads/2022/09/2017-Talks-Byun_Moana-Crashing-Waves.pdf （doi:10.1145/3084363.3085056）、https://history.siggraph.org/?p=84221

#### Moana 2（Disney、2024）

- 波の作り方（B と C）【資料：SideFX の事例紹介】：嵐の巨大な波は、配置の段階で波の変形器を作り、アニメーションを経て効果の係が直してから海の面に入れた。流体は Houdini の FLIP と海のスペクトルで計算し、場面ごとに力と美術の制御を加えた。
- 出典：https://www.sidefx.com/community/moana-2/

#### Avatar: The Way of Water（Wētā FX、2022）

- 波の作り方（D を出発点に、物理の結合）【資料】：撮影の段階から実時間の海のスペクトルの変形器を使い、本番は Loki の各解き方（大きな水、しぶき、霧、泡、細かい波）を物理で結合した。細かい波は Wave Curves（下の 2-C）で足した。
- しない事：一つの大波を集中で作る話は【資料になし】。
- 出典：https://unity.com/blog/industry/technology-behind-avatar-the-way-of-water 、https://www.firedbydesign.com/2023/02/23/total-immersion-weta-digitals-vfx-toolset-on-avatar-the-way-of-water/2/

### 2-B ゲームと実時間・VR の海

| 名前 | 波の作り方 | 見る人の体験 | しない事・資料にない事 | 出典 |
| --- | --- | --- | --- | --- |
| Sea of Thieves（Rare） | D：Tessendorf 2001 の FFT の海に、色と形の様式化を足す【資料：SIGGRAPH 2018 Talks】 | 帆船の甲板から嵐の海を見る（画面） | FFT の高さの場は水面の張り出しを表せない【推定：式の性質】 | https://history.siggraph.org/?p=84316 、https://jtessen.people.clemson.edu/reports/papers_files/coursenotes2002.pdf |
| Powerboat VR（Steam、早期公開 2020-12-29） | 現実の海の状態の尺度に沿った 3D の波。凪から「Phenomenal」（14 m 以上）まで【資料：販売ページ】 | VR でボートを操る | 波の計算の方法【資料になし】 | https://www.dekudeals.com/items/powerboat-vr |
| Windfall | 帆と船体にかかる力、浮力、ロープを実時間で計算する VR の帆走【資料】 | VR で帆船を操る | 海の波の作り方【資料になし】 | https://rawg.io/games/windfall |
| VR Sailing（Steam、2024-10-15） | 360 度の帆走と波【資料】 | VR で帆船を操る | 波の作り方【資料になし】 | https://store.steampowered.com/app/3201570/VR/ |
| Storm Breakers（Unity の素材、開発中） | 嵐の海と巨大な砕ける波、大きな船と小舟の水のぶつかり【資料】 | 試しの版あり | 砕ける波の作り方、VR 対応【資料になし】 | https://the-storm-rider.itch.io/storm-breakers-demos |
| Houdini の Guided Ocean Layer・Wave Tank・Beach Tank（SideFX の道具） | C：薄い FLIP の層を海のスペクトルの速さで誘導し、境界の粒子が速さを戻して反射を抑える。Beach Tank はスペクトルの速さを足し続ける【資料：SideFX の説明書、事前の確かめの記録】 | 制作の道具 | 波の集中で大波を作る道具ではない | https://www.sidefx.com/docs/houdini/shelf/guidedoceanlayer.html 、https://www.sidefx.com/docs/houdini/shelf/wavetank.html 、https://www.sidefx.com/docs/houdini/shelf/beachtank.html |

### 2-C CG の研究（砕ける波の作り方）

| 研究 | 中身 | 波の大きな形を決めるもの | 出典 |
| --- | --- | --- | --- |
| Mihalef, Metaxas & Sussman 2004「Animation and Control of Breaking Waves」（SCA） | 2D の砕ける波の見本の集まりから、作り手が望む瞬間の砕ける形を選び、その後を 3D の Navier–Stokes の計算で解く（Slice Method） | 作り手が選ぶ見本の形（C） | https://diglib.eg.org/items/5898eea9-9584-4ce7-ae51-e4b3cf908000 |
| Thürey ら 2007「Real-time breaking waves for shallow water simulations」（Pacific Graphics） | 浅水の高さの場で急な波の前面を見つけ、粒子の幕を出して巻く形を足す。純粋な高さの場では砕ける波を表せないと書く | 高さの場の急さの判定（C） | https://vcg.iwr.uni-heidelberg.de/publications/pubdetails/Thurey2007bubbles 、https://patents.google.com/patent/US8204725 |
| Skrivan ら 2020「Wave Curves」（SIGGRAPH、Wētā と IST Austria） | 大きな計算の上に、細かい波の束を後から足す | 細部だけ。大きな形は元の計算 | https://visualcomputing.ist.ac.at/publications/2020/WaveCurves/ |
| 鶴野玲治（九州大学）の科研費 20K12534（2020〜2025） | 流体計算をせずに流れの模様を作り直す対話の道具（GAN とスケッチ） | 手と学習（A） | https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-20K12534 |

### 2-D 極端な波・砕ける波の科学（実験・数値計算・解釈）

#### McAllister ら 2019（J. Fluid Mech. 860）と Oxford・Edinburgh の発表（2019-01-23）

- 何か：1995 年に北海で測られた Draupner の巨大波を、Edinburgh 大学の FloWave（直径 25 m の円い水槽、周り全部に 168 の造波板、1:35 の縮尺）で再現した実験。
- 波の作り方（F）【資料】：二つの波の群を交わらせ、交わる角度を変えた。造波板の入力を周波数ごとに直す繰り返しで、焦点で狙った波形を出した。Draupner の高さに届いたのは角度が約 120° の時。
- 砕け方【資料：論文、事前の確かめの記録】：0°（一方向）では、前の面がほぼ垂直の壁になり、そこから前へ噴き出す典型的な巻き波になった。120° では高さは届いたが、砕け方はほぼ垂直に上へ噴き上がる形で、前へ巻く形ではない。
- 北斎との結びつき【資料】：発表は、再現した波が『神奈川沖浪裏』によく似ていたと書く。研究者自身は EGU の記事で、似ていたのは偶然だと書いている。似ていると言われた写真は 120° の場合である。
- 見る人の体験：水槽の横から撮った写真と動画（発表のページに動画がある）。
- しない事：実物の大きさで見せる、船の上から見せる、VR で見せることはしていない。研究の目的ではない。
- 出典：https://doi.org/10.1017/jfm.2018.886 、https://eng.ox.ac.uk/news/famous-freak-wave-recreated-in-laboratory-mirrors-hokusai-s-great-wave 、https://blogs.egu.eu/geolog/2019/07/08/imaggeo-on-mondays-recreating-monster-waves-in-art-and-science/ 、https://www.research.ed.ac.uk/en/publications/laboratory-recreation-of-the-draupner-wave-and-the-role-of-breaki/

#### そのほかの科学の仕事

| 仕事 | 波の作り方 | 見せ方 | 出典 |
| --- | --- | --- | --- |
| Rapp & Melville 1990（Phil. Trans. R. Soc. A 331） | 深い水の分散を使い、周期の違う波を一点・一時刻に集めて、一つの砕ける波の群を作る（F）。実験室で巻き波を作る標準のやり方 | 水路の測定 | https://airsea.ucsd.edu/wp-content/uploads/sites/10/2019/06/1990_Rapp_Melville-A_Mathematical_and_Physical_Sciences_vol_331.pdf |
| Mostert, Popinet & Deike 2022（J. Fluid Mech. 942, A27） | 空気と水の二相の Navier–Stokes を直接解く（Basilisk、実効 4096³）。初めに不安定な 3 次のストークス波を置き、巻き波を起こす（集中ではなく初めの形） | 泡としぶきの統計と 3D の可視化 | https://cambridge.org/core/journals/journal-of-fluid-mechanics/article/highresolution-direct-simulation-of-deep-water-breaking-waves-transition-to-turbulence-bubbles-and-droplets-production/C22BAE7BDB4A0D2CFE7E395E9D1483B0 |
| Chabchoub ら 2011（Phys. Rev. Lett. 106, 204502） | 非線形の自己集中（Peregrine の breather）を水槽で観測 | 水槽の測定 | https://www.doi.org/10.1103/PHYSREVLETT.106.204502 |
| Cartwright & Nakamura 2009（Notes Rec. R. Soc. 63:119–135） | 『神奈川沖浪裏』を、津波ではなく嵐の大波の巻き波と読み、高さを 10〜12 m と見積もった | 解釈の論文 | https://doi.org/10.1098/rsnr.2007.0039 |
| Dudley, Sarano & Dias 2013（Notes Rec. R. Soc. 67:159–164） | 同じく極端な巻き波で、異常に大きな波（rogue wave）に当たる見込みが高いと読み、向きの違う波の集中を仕組みの候補に挙げた。南極に近い海で撮った巨大波の写真と比べた | 解釈の論文 | https://pmc.ncbi.nlm.nih.gov/articles/PMC3645210/ |
| 板宮朋基（愛知工科大学）科研費 16K01292（2016〜2019） | 実験と数値計算の値を入れた、浸水の中の車の避難の HMD 体験。約 3,000 人が体験 | HMD と振動 | https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-16K01292 |
| 秋田市・凸版印刷の津波の避難 VR（2019-05） | 県の津波浸水想定の計算をもとに、実写と CG で津波の進み方を見せる | VR の避難体験 | https://www.watch.impress.co.jp/docs/news/1185540.html |
| Boorboor ら「Submerse」（IEEE TVCG 30(9), 2024） | 高潮の浸水の計算を、ニューヨークの街の 3D で見せる | 壁一面の没入型表示（Reality Deck）。HMD ではない | https://arxiv.org/abs/2304.06872 |
| Tavakkol & Lynett「Celeris Base」（Computer Physics Communications、2020） | 拡張 Boussinesq の式を GPU で実時間に解く、浅い海の波の計算と可視化の道具。Unity で作られ、VR の HMD で見られる。実験の観測と照合済み（E） | HMD で計算中の海岸の波を見る | https://research.google/pubs/celeris-base-an-interactive-and-immersive-boussinesq-type-nearshore-wave-simulation-software/ 、https://arxiv.org/abs/1611.05984v1 |
| USC ICT・USC Viterbi・米陸軍工兵隊 ERDC CHL「WSSOF（Watercraft and Ship Simulator of the Future）」（2023〜） | 地形・海底の深さ・非線形浅水と Boussinesq の波の計算と、1 隻の船の操船を合わせた VR の試作（E）。共同代表は Lynett | VR の船の模擬 | https://ict.usc.edu/wp-content/uploads/2023/11/ShipSim-One-Sheet.pdf |
| Ervin, Boone, Smink ら「Physics-Based Watercraft Simulator in Virtual Reality」（Virtual Worlds 2(4), 2023） | 米陸軍工兵隊 ERDC のスーパーコンピューターで計算した FUNWAVE 3.4（Boussinesq の式）の数百万点の結果を Unreal Engine に読み込み、上陸用の船が海岸近くの波に揺られる様子を VR で見せる（E）。目的は航路の設計と上陸の作業の理解 | VR の船橋で船を操る | https://doi.org/10.3390/virtualworlds2040024 |
| 東京大学 宝谷研究室（研究室紹介）、科研費の進捗の要約（木下） | 巨大な波ができる非線形の過程、水槽での異常に大きな波の再現、巨大な波の中の船の応答、異常波の起きやすさの指標と避け方の支援（F）【資料：検索の抜き書きだけ。本文は読んでいない】 | 水槽の実験と数値計算 | https://www.sys.t.u-tokyo.ac.jp/labinfo/doc/doc_h_houtani.pdf 、https://www.jsps.go.jp/j-grantsinaid/12_kiban/hyouka22/shinchoku_gaiyo/summary_63_kinoshita.pdf |

## 3. 大波の海にいる VR・没入の体験

| 名前 | 波の作り方 | 見る人の位置と体験 | しない事・資料にない事 | 出典 |
| --- | --- | --- | --- | --- |
| The World of Red Bull: Big Wave Surfing（Apple Vision Pro、Apple Immersive Video、2026-10-01 公開、約 8 分） | G：タヒチの Teahupo'o の実際の波を、8K・180° の立体映像で撮影 | 波の中のサーファーの近く、礁の魚、大波の水面の近く、観客の船の上、空から | 撮影なので波は作らない。見る位置は撮影の位置に決まる | https://www.uploadvr.com/the-world-of-red-bulls-big-wave-surfing-makes-apple-immersives-180deg-frame-feel-limitless/ 、https://roadtovr.com/apple-vision-pro-immersive-video-red-bull-real-madrid/ |
| Red Bull Brasil「Surfing with Pedro Scooby in VR」（2016） | G：Nazaré の 360° の撮影 | 360° 動画 | 同上 | https://www.redbull.com/us-en/big-wave-surfing-immersive-vr-film （今回は本文を読めず、検索の抜き書きだけ） |
| Red Bull Media World「Nazaré – Surfing the Beast」（スイス交通博物館、Wunderman Thompson Switzerland） | G：Nazaré の実写に、来場者の実時間の影を重ねる | 9 × 3 m の LED の壁の前で体を動かす。HMD なし | 同上 | https://www.organisator.ch/en/?p=19270 |
| Marshmallow Laser Feast・Presstube・Dpt.・Headspace「A Colossal Wave」（2017 Hull、のちに Montreal） | H：様式化した CG の巨大な波【推定：資料の写真と説明から】 | 高さ 9 m の塔から落としたボウリングの玉が銅鑼を打つと、傘の下で HMD を着けた人の上に巨大な波が崩れ落ちる | 波の物理の計算【資料になし】。船はない | https://uploadvr.com/colossal-wave-may-weirdest-vr-installation-weve-seen-far/ 、https://dpt.co/en/projects/a-colossal-wave/ |
| Ars Electronica Solutions「The Wave」（展示「Planet Ocean」、Gasometer Oberhausen、2024-03〜） | H：流体計算で作った、来場者の上で崩れる波。計算に数か月、データは数テラバイト | 高さ 40 m の傾けた画面の下から見上げる（投影、HMD ではない）。その後、水の下の世界へ入る演出 | 波をどう起こしたか（集中か、手で決めた形か）【資料になし】。船はない | https://ars.electronica.art/aeblog/?p=78976 |
| 船員の訓練の VR（Brave Dolphin、Solent 大学など） | 船内の火災・救命艇などの緊急時の場面 | HMD で船内の手順を練習 | 大波の体験は主題ではない【資料】 | https://www.innovasjonnorge.no/en/start-page/eea-norway-grants/success-stories/greece-brave-dophin-shakes-the-waters-of-maritime-training-with-vr/ 、https://www.solent.ac.uk/media-hub/news/solent-showcases-vr-breakthrough-for-seafarer-safety |
| Yamazaki, Leterrier, Taguchi, Virdi「Waiting for the Wave in Metaverse」（2023、ACM SIGGRAPH Digital Arts Community の展示「The Future of Reality」） | 手で作る形の揺らぎと海の物理を合わせて、サーフィンに理想の波の一瞬の形を 3 次元で作る【資料】 | VR で止まった波の形と向き合う | 動く大波・崩れる瞬間・船【資料になし】 | https://dac.siggraph.org/?p=2928 |
| VirtualSurf（フランス・ビアリッツの Cité de l'Océan、2015-07-22 公開） | Oculus Rift と Kinect。実在の 3 つの波（Belharra など）に乗る | 板の上の姿勢で体を傾けて波に乗る | 波を撮影したか CG か【資料になし】 | https://www.spabusiness.com/wellness-news/French-museum-launches-VR-surfing-experience/317063 |
| 第 2 節の Powerboat VR、Windfall、VR Sailing、Celeris Base、WSSOF、Ervin ら 2023、津波の避難 VR | 第 2 節を参照 | 船の上（ゲーム）、海岸（Celeris）、車の中（板宮）など | 第 2 節を参照 | 第 2 節 |

体験の研究（参考）：Chirico ら 2018（Frontiers in Psychology 8:2351）は、VR で「畏れ（awe）」を起こす環境を作って 36 人で比べ、畏れの要素として「大きさ・広がり（vastness）」と「考えの枠を直す必要」を置いた。作品の体験を測るかどうかの参考になる。https://pmc.ncbi.nlm.nih.gov/articles/PMC5786556/

## 4. 作り方ごとの、しない事の並べ（第 1〜3 節のまとめ）

この表は、読んだ資料に書かれた範囲で埋めた。「×」は資料からしていないと読める事、「？」は資料に書かれていない事。

| 例 | 大波の形が流体の条件から生まれる | 集中などの物理の仕組みで高くなる | 実物の大きさ | 船の上の位置 | HMD | 崩れる瞬間まで |
| --- | --- | --- | --- | --- | --- | --- |
| teamLab Black Waves | ？ | ？ | ？ | × | × | ？ |
| HOKUSAI: ANOTHER STORY | ×（手の動きと混ぜ合わせ） | ？ | ？ | ？ | ×（LED） | ○（崩れる表現あり） |
| Digital×北斎【序章】の VR | ×（元は絵の画像）【推定】 | × | ？ | ×（絵の前に立つ） | ○ | ？ |
| Poseidon・Interstellar | ×（手で形） | × | ○ | 映画（観客は画面の外） | × | ○ |
| Moana（流体の版） | △（境界の条件を物理ではあり得ない急さへ変える） | × | ○ | 映画 | × | ○ |
| The Perfect Storm | △（砕ける時を制御） | ×（現実より早く育てる制御） | ○ | 映画 | × | ○ |
| McAllister ら（FloWave） | ○ | ○（向きの違う波の集中） | ×（1:35） | ×（水槽の横） | × | ○ |
| Rapp & Melville | ○ | ○（分散による集中） | ×（実験室） | × | × | ○ |
| Celeris Base・WSSOF・Ervin ら 2023 | ○（水深で平均した式） | ○（浅くなる・屈折）【推定：式の性質】 | ○ | WSSOF と Ervin らは船、Celeris は海岸 | ○ | ×（巻く形は表せない）【推定】 |
| Red Bull（Vision Pro） | 実際の海 | 実際の海 | ○ | ○（船の上の場面あり） | ○ | 撮影の位置しだい |
| A Colossal Wave | ？ | ？ | ？ | × | ○ | ○（上に崩れ落ちる） |
| Ars Electronica The Wave | ？（流体計算とだけ） | ？ | ○（40 m の画面） | × | × | ○ |

（○＝する、△＝一部、×＝しない、？＝資料になし）

## 5. 空いている所（利用者への問い。主張ではない）

次の問いは、今回の調べで見えた空きを、利用者が判断するために並べた。どれを作品の違いとして言うか、言わないかは利用者が決める。

1. **物理の仕組みで生まれた大波を、船の上から体験する例は見つからなかった。** 実験と数値計算（第 2-D 節）は、分散や向きの違う波の集中で一つの大波を起こすが、見る人は水槽の横のカメラの映像を見る。VR の物理の波（Celeris Base、WSSOF、Ervin ら 2023。後の 2 つは船を操る VR）は水深で平均した式なので、前へ巻く形は表せない【推定】。この組み合わせ（物理の仕組みで高くなる・実物の大きさ・船の上・HMD・崩れる瞬間）を作品の違いとして言うか。言う場合、調べの範囲を広げるか（第 6 節の未調査の所）。
2. **映画の大波は、形を手で決める例が多い。** Poseidon の作り手は、迫る巨大な波は計算ではできず手で作ったと述べた。Moana の流体の版も、境界の条件を物理ではあり得ない急さへ変えて砕かせている。HOKUSAI: ANOTHER STORY も、計算を土台に手で動きを付けて混ぜ合わせた。「崩れる形を手で作らず、波を起こす境界と海底の条件だけで決める」ことを違いとして言うか。言うなら、何を測って示すか（例：箱の中に力・速さを入れていない記録、どの集中の仕組みが働いたかの測り）。
3. **『神奈川沖浪裏』を動かした作品は多い。** 見る人は絵の前に立つか、絵を広げた空間を歩く。舟の上の位置は、Tilt Brush の作者自身の体験と、映画『KUBO』の場面（観客は画面の外）のほかは見つからなかった。指導教員は「視点を船の上に置くだけでは新しさにならない」と述べた。船の上の視点を、ほかの何と組み合わせて言うか、言わないか。
4. **Oxford の発表は Draupner の再現を北斎と結びつけたが、似ていると言われた写真は 120° の交差の場合で、砕け方は上への噴き上がりだった。** 前へ巻く砕け方は 0°（一方向）の場合だった。作品の説明でこの違いをどう扱うか（研究を引く時に、どちらの場合を引くか）。
5. **利用者自身の 2 年間の研究（海洋学）の中身のどこを、違いの元にするか。** 指導教員はそれを求めた。この調べは利用者の研究の中身を知らないので、第 2-D 節のどの仕事が利用者の研究に近いか、利用者に決めていただく。
6. **Ars Electronica の「The Wave」（2024）は、流体計算で作った砕ける波を 40 m の画面で見上げさせる。** 波の起こし方は資料に書かれていない。この作品との違いを言うために、作り手の資料（講演・記事）を詳しく調べるか。
7. **体験を測るか。** VR の畏れの研究（Chirico ら 2018）は「大きさ」を要素としている。作品の体験を質問紙などで測るか、測らずに見せるか。
8. **線の表現と流体計算の組み合わせはすでにある（teamLab）。** 作品で浮世絵の線や色を美術の層として使う場合、teamLab との違いをどう言うか、言わないか。

## 6. この調べの限り（確かめていない所）

- 調べたのは主に英語と日本語の Web。中国語は 1 回だけ検索した（新しい例は出なかった）。韓国語・ほかの言語の作品は調べていない。
- 学術の目録（Google Scholar、ACM Digital Library の全文の検索、J-STAGE、CiNii）を順に調べてはいない。日本の CG の学会（Visual Computing、NICOGRAPH、芸術科学会）や修士・博士の論文も調べていない。
- 映画祭・展示の目録（SIGGRAPH の Art Gallery と VR Theater、Ars Electronica の過去の受賞作、Venice Immersive・Tribeca・Sundance New Frontier の全作品、Steam の全目録）を一つずつ見てはいない。Venice Immersive 2025 の評を 1 本読んだが、大波の作品は載っていなかった。
- ページの多くは要約の道具を通して読んだ。年・数・言い回しに要約の誤りが入りうる。開けなかったページ（403、読めない PDF）は、検索の抜き書きだけで書いた所がある（各項に記した）。
- 「北斎の波はハイスピードカメラの映像と一致した」という話は、出典を確かめられなかったので載せていない。
- 第 4 節の表の ○・×・？ は、資料の書き方に頼る。作り手が資料に書いていない事をしている場合がある。

## 7. 出典の一覧（本文に出た順ではなく、区分ごと）

『神奈川沖浪裏』の作品：
- https://www.teamlab.art/w/black_waves/amosrex/
- https://www.teamlab.art/w/blackwaves_lost_immersed_and_reborn/
- https://neocha.com/magazine/black-waves/
- https://cgworld.jp/article/202504-cgw320-hokusai.html
- https://www.fun-japan.jp/en/articles/14085
- https://www.timeout.com/tokyo/art/hokusai-another-story-in-tokyo
- https://www.tokyoweekender.com/art_and_culture/design/interact-rare-hokusai-works-ntt-easts-new-digital-art-exhibition/
- https://news.livedoor.com/article/detail/24135439/
- https://kyodonewsprwire.jp/release/202112144975
- https://bijutsutecho.com/magazine/news/report/30024
- https://www.thetvdb.com/series/374687-art-attack/episodes/7518210
- https://80.lv/articles/japanese-painting-brought-to-life-through-stunning-2d-animation
- https://www.artofvfx.com/?p=16167
- https://www.fxguide.com/?p=187493
- https://foundry.com/industries/film-television/kubo-behind-the-scenes
- https://press.moviewalker.jp/news/article/224041/p2/
- https://www.meer.com/en/91952-the-great-wave-digital-2-point-0
- https://artsandculture.google.com/story/6gUh_88uR5Q89w
- https://www.thisiscolossal.com/?p=138774
- https://www.scottishopera.org.uk/news/digital-technology-brings-to-life-the-works-of-iconic-japanese-artist-katsushika-hokusai-in-an-exhibition-presented-alongside-scottish-opera-s-world-premiere-production-of-the-great-wave/
- https://www.sidefx.com/forum/post/321930/

映画・VFX・ゲーム・CG の研究：
- https://www.cgw.com/Publications/CGW/2000/Volume-23-Issue-7-July-2000-/Sea-Change.aspx
- https://www.ilm.com/vfx/the-perfect-storm/
- https://www.cgw.com/Publications/CGW/2006/Volume-29-Issue-4-April-2006-/Size-Matters.aspx
- https://www.fxguide.com/?p=21422
- https://en.wikipedia.org/wiki/Ronald_Fedkiw
- https://www.postmagazine.com/Publications/Post-Magazine/2014/November-1-2014/VFX-Interstellar.aspx
- https://dneg.com/show/interstellar
- https://www.motionpictures.org/?p=342
- https://www.fxguide.com/?p=37947
- https://empireonline.com/movies/features/life-pi-vfx
- https://history.siggraph.org/wp-content/uploads/2022/09/2017-Talks-Byun_Moana-Crashing-Waves.pdf
- https://history.siggraph.org/?p=84221
- https://www.sidefx.com/community/moana-2/
- https://unity.com/blog/industry/technology-behind-avatar-the-way-of-water
- https://www.firedbydesign.com/2023/02/23/total-immersion-weta-digitals-vfx-toolset-on-avatar-the-way-of-water/2/
- https://history.siggraph.org/?p=84316
- https://jtessen.people.clemson.edu/reports/papers_files/coursenotes2002.pdf
- https://www.dekudeals.com/items/powerboat-vr
- https://rawg.io/games/windfall
- https://store.steampowered.com/app/3201570/VR/
- https://the-storm-rider.itch.io/storm-breakers-demos
- https://www.sidefx.com/docs/houdini/shelf/guidedoceanlayer.html
- https://www.sidefx.com/docs/houdini/shelf/wavetank.html
- https://www.sidefx.com/docs/houdini/shelf/beachtank.html
- https://diglib.eg.org/items/5898eea9-9584-4ce7-ae51-e4b3cf908000
- https://vcg.iwr.uni-heidelberg.de/publications/pubdetails/Thurey2007bubbles
- https://patents.google.com/patent/US8204725
- https://visualcomputing.ist.ac.at/publications/2020/WaveCurves/
- https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-20K12534

科学：
- https://doi.org/10.1017/jfm.2018.886
- https://eng.ox.ac.uk/news/famous-freak-wave-recreated-in-laboratory-mirrors-hokusai-s-great-wave
- https://blogs.egu.eu/geolog/2019/07/08/imaggeo-on-mondays-recreating-monster-waves-in-art-and-science/
- https://www.research.ed.ac.uk/en/publications/laboratory-recreation-of-the-draupner-wave-and-the-role-of-breaki/
- https://airsea.ucsd.edu/wp-content/uploads/sites/10/2019/06/1990_Rapp_Melville-A_Mathematical_and_Physical_Sciences_vol_331.pdf
- https://cambridge.org/core/journals/journal-of-fluid-mechanics/article/highresolution-direct-simulation-of-deep-water-breaking-waves-transition-to-turbulence-bubbles-and-droplets-production/C22BAE7BDB4A0D2CFE7E395E9D1483B0
- https://www.doi.org/10.1103/PHYSREVLETT.106.204502
- https://doi.org/10.1098/rsnr.2007.0039
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3645210/
- https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-16K01292
- https://www.watch.impress.co.jp/docs/news/1185540.html
- https://arxiv.org/abs/2304.06872
- https://research.google/pubs/celeris-base-an-interactive-and-immersive-boussinesq-type-nearshore-wave-simulation-software/
- https://arxiv.org/abs/1611.05984v1
- https://ict.usc.edu/wp-content/uploads/2023/11/ShipSim-One-Sheet.pdf
- https://doi.org/10.3390/virtualworlds2040024
- https://www.sys.t.u-tokyo.ac.jp/labinfo/doc/doc_h_houtani.pdf
- https://www.jsps.go.jp/j-grantsinaid/12_kiban/hyouka22/shinchoku_gaiyo/summary_63_kinoshita.pdf

VR・没入の体験：
- https://www.uploadvr.com/the-world-of-red-bulls-big-wave-surfing-makes-apple-immersives-180deg-frame-feel-limitless/
- https://roadtovr.com/apple-vision-pro-immersive-video-red-bull-real-madrid/
- https://www.redbull.com/us-en/big-wave-surfing-immersive-vr-film
- https://www.organisator.ch/en/?p=19270
- https://uploadvr.com/colossal-wave-may-weirdest-vr-installation-weve-seen-far/
- https://dpt.co/en/projects/a-colossal-wave/
- https://ars.electronica.art/aeblog/?p=78976
- https://www.innovasjonnorge.no/en/start-page/eea-norway-grants/success-stories/greece-brave-dophin-shakes-the-waters-of-maritime-training-with-vr/
- https://www.solent.ac.uk/media-hub/news/solent-showcases-vr-breakthrough-for-seafarer-safety
- https://mediaenviron.org/article/161234-liquid-vr-exhibition-review-venice-immersive-2025
- https://pmc.ncbi.nlm.nih.gov/articles/PMC5786556/
- https://dac.siggraph.org/?p=2928
- https://www.spabusiness.com/wellness-news/French-museum-launches-VR-surfing-experience/317063

事前の物理の確かめ（McAllister の 0° と 120° の砕け方、Dudley らの読み）：進行役の一時フォルダーにある事前の確かめの記録の physics の部分（リポジトリの外。個人のパスなので写さない）（リポジトリの外）。
