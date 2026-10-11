# Houdini で大波を作る方法の調べ（Q47・Q50。Q51 で広げた調べのうち Houdini の部分）

> **〔Q51、2026-10-11〕調べの範囲が広がった：** この報告を書き終えた直後に、指導教員から「もっと調べてもらってください。Houdiniにこだわりすぎる、実装手法を調べてもらったください」「調べてもらった結果を置いてある場所を教えてください」という答えが届いた（[制作手順の Q51](../Workflow/Production_Workflow_ja.md)）。この報告は、広げた調べのうち **Houdini の部分** である。前の調べ（[リアルタイムの流体計算の例 41 件](RealtimeBigWave_Survey_ja.md)）とこの報告は残し、Houdini の外も含めた実装の手法（解いている式と算法、公開のコード、エンジンや道具、作品の例）の調べを足して一つにまとめる（まだ始めていない）。実装できるだけの手順やコードが公開されているかを重く見る（Q51 の扱い 1）。置き場所は GitHub の imagirelab/GreatWave_2026 の `Docs/Research/`（調べ）と `Docs/Progress/`（計算の報告）。

- 日付：2026-10-11（本機の日付）。同じ日に別の者の見直しを受けて直した（直した点と採らなかった点は §10）。書いた者：進行役（Claude）。利用者を通して指導教員に見ていただくための報告。
- 何のためか：指導教員の指示（Q47、10/9 の Discord）「大波を実現しているリアルタイムな流体シミュレーションを調査してもらいましょう。良いものがあったら、それを実装してもらうのが手法も確定しているので進めやすいと思います」。利用者の訂正（Q50）により、これを「Houdini で大波を実現している方法の調べ」と読み直した。指導教員の 9/23 の設計の文は「波はHoudiniで流体シミュレ―ションしたものをサーフェス化してリアルタイムに表現したいです」で、「リアルタイム」は Houdini の計算を面にして実時間で見せる流れを指す（[制作手順の Q47〜Q50](../Workflow/Production_Workflow_ja.md)）。その後の Q51 で、Houdini に絞った読みは狭すぎたと分かった（上の囲み）。
- 状態：読むだけの調べ。ダウンロード・インストール・重い計算はしていない。新しい計算は始めていない（Q49：指導教員の返事を待つ）。ウェブの動画（YouTube・Vimeo・講座）は一本も見ていない。見たのは、この機械の Houdini 21.0.729 の help に同梱の絵と動画（3 本、Houdini の hffmpeg で 1 秒おきの一覧にした）だけ。
- 印：【文献】出典にあること。【見た】自分で見た絵や動画のコマ。【記録】このリポジトリの記録の値。【計算】式の値。【考え】【推定】進行役の推論と見積もり（確かめていない）。
- 短い名前（§1 から後で使う。§0 では使わない）：FLIP42＝今の 2D の断面の計算（Rapp & Melville 1990 の巻き波の組を 70 倍。[FLIP_Plunging_ja.md](../Progress/FLIP_Plunging_ja.md)）。R3・R4＝その粒子 0.25 m・0.177 m の計算（R4 は粒子 0.1767578125 m の R4d で判定した）。FLIP42 の凍結した判定：A1＝入口の波の振幅と位相、A3'＝焦点の場所と時刻の模型、B1＝計算の中の減り、C1〜C4＝細かさの比べ、D1〜D3＝実験との比べ（崩れ方・崩れ始めの場所・着水の時刻と場所）。RT48＝断面を横に掃いて Unity で再生した試作。Step 18＝VAT 3.1 を Unity の Built-in で再生した以前の確かめ。Q の番号は制作手順の指示の記録。分類の記号（P・B・B\*・G・S・U）は §1.2 の (3)。
- 作業メモ（Git 対象外）：`Unity/Build/SURVEY50/` の 4 つの記録（SideFX の公式 `sidefx_ja.md`、制作の例 `production_ja.md`、作り手の講座と掲示板 `artists_ja.md`、実時間へ渡す道と研究 `realtime_ja.md`）と、まとめた 53 項目の一覧 `items.json`。項目のうち 22 は、まとめの前の確かめの段で一次の出典と手元の Houdini の help・棚の script で読み直した（`items.json` の basis が verified）。確かめの段からまとめ役に渡された一覧は Swapped の項目の途中で切れていたので、26 項目は記録だけによる（basis が notes）。見直しの段で足した 4 項目は、その段で一次の出典を読んだ（basis が revise）。残る 1 項目は本作の FLIP42 で、basis が record。

## 0. 一枚で

### 0.1 流れ

| 指導教員の流れ | 内容 |
| --- | --- |
| 方針 | Houdini で大波を作っている例を、SideFX の公式の道具と文書、SideFX のサイトの講座とトーク、作り手の講座と掲示板、映画・配信・ゲームの制作の記事と講演、実時間へ渡す道から集めた。例ごとに、調べる前に決めた 6 点（§1.2）を書き、巻きの作り方で分けた |
| 目標 | Houdini で「高く立ち上がり、前の面が険しくなり、厚い唇が前へ巻いて崩れる」大波を出す確立した方法があるか、その方法が計算の途中にどんな力を使うか、今の 2D の計算と何を共有するかに、例ごとの証拠で答える。3D の段の候補を、時間・メモリー・危険とともに示す（決めるのは指導教員） |
| 結果 | 53 項目（制作 18、SideFX の道具と部品 12、SideFX のサイトの講座とトーク 4、作り手 9、実時間の例と渡す道 6、研究 3、本作 1）。巻きの作り方が資料の文で分かった制作と講座は、形を先に決める（変形器・手のアニメーション・断面の線）か、計算の途中で誘導・制御の力を入れる（速度の注ぎ込み、誘導の層、向きや強さを変えた重力）か、物理で釣り合わない急な境界の値で崩す（Moana 2016 の計算の版）ものだった。Frozen 2 は Houdini の FLIP の水槽を波の式（3 次のストークス波）から作った速度の場で動かし、筒の形に崩れる波を作ったが、その場がどこにどう効くか、形の彫り直しがどこに入ったかは書かれていない。計算の途中に制御の力を入れない公式の型は「境界から決めた海を入れ、中は重力だけで解く」水槽（Wave Tank、FLIP Configure Wave Tank、Guided ocean waves）で、公式の例で見えた崩れは 20 m ほどの箱の頂の白いこぼれだった【見た】 |
| 分かったこと | 計算の途中に制御の力を入れず、手順が公開され、厚い唇が前へ巻く大波を見せた Houdini の方法は、調べた範囲で見つからなかった。今の 2D の計算は、公式の水槽と同じ形（入口の帯で線形の波の流速へ寄せ、帯の外は重力だけ）に、実験で巻いたと記録された波の群の条件（Rapp & Melville 1990）を入れたもので、入口の帯の外では重力だけで沖の波が前へ巻いた。入口の帯は造波板の代わりで、その意味はまだ指導教員に確かめていない。唇は厚み 1 m 前後と薄い。走らせる前に決めた判定のうち、崩れ方と崩れ始めの場所は実験の幅に入ったが、入口の波の再現・焦点の場所と時刻・計算の中の減り・着水の時刻と場所の 4 つは外れ、実験より手前で早く崩れた。原因は分かっていない【記録】。研究の 3D の砕波の計算も途中に力を入れずに巻かせるが、どれも形と釣り合わない速度か、崩れる手前の険しい波から始めている【文献】 |
| 現在地 | Houdini の部分の調べは読むだけで終えた。動画で方法を確かめていない例が多い（§7）。2D の計算の報告（[FLIP_Plunging_ja.md](../Progress/FLIP_Plunging_ja.md)）とこの報告は指導教員の返事待ち。Houdini の外の実装の手法の調べ（10/11 の指導教員の答え）はまだ始めていない |
| 次 | 唇を厚くする物理の候補は、群を強めること（2D のまま、1 本 5〜7 時間）と、向きの違う波を一か所に集めること（3D、1 本 2〜6 日）の二つと読む【考え】。進行役は、2D のまま群を強めて唇が厚くなるかを先に見ることを推す（§0.4）。どれにするか、向きの違う波を入口の条件に入れてよいかは、指導教員に伺う。Houdini の外の調べの結果で、この候補は変わりうる |

### 0.2 巻きの作り方で分けた例（6 点の短い形）

「確」＝確かめの段で一次の出典と手元の help・script で読み直した項目。Swapped は確かめの一覧がこの項目の途中で切れたので「確（途中まで）」。「記」＝作業メモだけの項目。「見直し」＝見直しの段で一次の出典を読んだ項目。分類が書き込みや章の名からの読みの項目は「分類は推定」と書いた。6 点のうち (3) 巻きの作り方は分け方そのもので、「途中の制御」の欄に、計算の途中で何が制御として働くかを書いた。(6) は、ここで使うならという進行役の読みで、指導教員の求め（重力と、風のように波を自然に起こす力のほかは入れない）に合うかの判断ではない。詳しくは `items.json` と各記録。

| 例 | (1) 見せる波（どこまで・証拠） | (2) Houdini の方法と力 | (3) 途中の制御 | (4) 公開・費用 | (5) 実時間・絵 | (6) ここで使うなら（進行役の読み） |
| --- | --- | --- | --- | --- | --- | --- |
| **重力と巻きの仕組みの設定（群の集まりや海底の浅くなりを条件として置き、中は重力だけ）** | | | | | | |
| 本作の今の 2D の計算（記録） | 前の面が鉛直を越え、唇が付いて空気を囲む。静かな水面から頂まで 9.6 m、唇の厚み 1 m 前後、頂は横に同じ。判定の 4 つが外れ、実験より手前で早く崩れた【記録・[FLIP_Plunging_ja.md](../Progress/FLIP_Plunging_ja.md) の動画】 | DOP FLIP、入口の帯で 32 成分の線形の流速（有限水深）へ寄せる、狭い帯なし、重力だけ | 帯の中だけ流速を寄せる（造波板の代わり） | リポジトリの道具と記録 | 断面を横に掃いて Unity で再生した試作 | 入口の帯の意味と条件の決め方は、指導教員の確認待ち |
| [FLIP Configure Beach Tank](https://www.sidefx.com/docs/houdini/fluid/sopconfigbeach.html)（確） | 浜の岸。崩れは書かれず、この道具の巻きの絵はない | SOP FLIP、Boundary Flow でスペクトルの海、浜の衝突物、重力 | 見つからない | 同梱・無料 | 書いていない | 海底を置くならその理由が要る（10/8 の指導教員の答え）。浜の波は沖の大波と別の物 |
| **境界・初めに海を入れるだけ（巻きの仕組みは置かない）** | | | | | | |
| [Wave Tank](https://www.sidefx.com/docs/houdini/shelf/wavetank.html)（確） | 「最初の波の形だけを置く」。大波・巻きの記述も絵もない【見た：help の絵】 | 線形の海で満たし、境界の層で面と速度を上書き、粒子を消す・足す、重力だけ | 途中にない（境界の層の中だけ上書き） | 同梱・無料、棚の一押し | 書いていない | 骨組みとして使える。群を集める道具がなく、速度は深い水の指数の減りだけ |
| [FLIP Configure Wave Tank・Guided ocean waves](https://www.sidefx.com/docs/houdini/fluid/sopoceanwaves.html)（確） | 20 m の箱で頂が白くこぼれて崩れる。高い波・厚い唇はない【見た：help の動画 2 本】 | SOP FLIP の Boundary Flow でスペクトルの速度と静水圧、逆向きの波を混ぜて崩す | 途中にない（外の帯だけ） | 同梱・無料、値は頁に | 書いていない | 今の 2D の入口の帯にいちばん近い公式の形 |
| **形と釣り合わない速度や、崩れる手前の険しい波を、初めや境界に置いて崩す** | | | | | | |
| [Moana（2016）の計算の版](https://history.siggraph.org/wp-content/uploads/2022/09/2017-Talks-Byun_Moana-Crashing-Waves.pdf)（確） | 40 を超える崩れる波、端から崩れる筒。図は見ていない | Disney 独自の APIC（Houdini ではない）。ストークス波 1 周期を動く枠で解き、境界の値を「物理ではあり得ないほど急な波」に変える | 境界の値（著者が「制御の仕組み」と書く） | 2 頁の原稿 | オフライン | 解き手と境界の値だけで巻かせた制作の例。崩れは物理でない境界の値から来る |
| [Mihalef ら 2004](https://www.math.fsu.edu/~sussman/BreakingWavesElectronic.pdf)（記、Houdini の外） | 2D と 3D の巻き波（図 1 は『神奈川沖浪裏』） | 2D の一覧の断面を人が選んで並べ、3D の初めの状態に。初めの速度の値 ω は、波の速さの式の値の 2.5〜5 倍を選ぶ | 途中の力なし。初めの速度と断面の時刻が人の選び（題も「Control」） | 論文 | なし | 「2D の結果を横に並べて始める 3D」の元。人の選んだ速度は入れずに借りる |
| [Lubin 2015](https://notus-cfd.org/wp-content/uploads/2020/03/jfm_2015.pdf)・[Mostert 2022](https://par.nsf.gov/servlets/purl/10414842)（記、Houdini の外） | 3D の巻き波と崩れ | 横に同じ 2D の波から 3D を解く。初めは大きな正弦の波（Lubin）、崩れる手前の 3 次のストークス波（Mostert）で、どちらも初めの速度は形と釣り合わない人工の始め方と著者が書く | 途中の力なし。崩れは初めの状態から | 論文 | なし | 横に同じ 2D から始めると、唇が付くまで 2D と同じ形（§4） |
| **誘導・制御の力** | | | | | | |
| [Beach Tank](https://www.sidefx.com/docs/houdini/shelf/beachtank.html)（確） | 浜の崩れ。巻きの絵はない | POP Advect by Volumes で、傾けた海の速度を 1.5 倍で毎ステップ足す | ある | 同梱・無料 | 書いていない | 途中に速度を足すので、この形では使わない |
| [Guided Ocean Layer](https://www.sidefx.com/docs/houdini/shelf/guidedoceanlayer.html)（確） | 海の面の上の薄い層。大波なし | 誘導の衝突の床が海の速度で動く | ある | 同梱・無料 | 書いていない | 同上 |
| [Crashing Wave](https://www.sidefx.com/tutorials/crashing-wave/)・[Wave in a Box](https://www.sidefx.com/tutorials/houdini-breakdowntutorial-wave-in-a-box-part-01/)（確、分類は推定） | 灯台に砕ける波、狭い所で大きく砕ける波。見ていない | Volume Source で押す・@v を作って制御（書き込みと章の名からの読み） | ある見込み | 無料の動画 | Mantra | 動画を見るまで分からない |
| [Adrift](https://www.sidefx.com/community/adrift/)（確） | 約 30 m の波でヨットが縦に回る。巻きの記述なし | 手で置いた波、誘導の層、独自の誘導の速度、急な面で重力の向きを面に垂直に | ある | 概要 | Mantra、約 13 万コア | 急な面で粒子がすべるという注意は 3D で役に立つ |
| [Swapped](https://cgworld.jp/flashnews/01-202607-Houdini-Swapped.html)（確（途中まで））・[Pirates 5](https://history.siggraph.org/wp-content/uploads/2022/09/2017-Talks-Hopper_The-Water-Effects-of-Pirates-of-the-Caribbean-Dead-Men-Tell-no-Tales.pdf)・[Masters of the Sea](https://www.sidefx.com/tutorials/vfx-studio-oriented-masters-of-the-sea)（確） | 津波・水の壁・岩に当たる波 | 速度の注ぎ込みと高さで変わる重力、動かした代理と架空の力、独自の力の水槽 | ある | 講演の要約・2 頁・有料 | オフライン | 途中に力を入れるので、この形では使わない |
| 作り手の例（記）：[Supergirl](https://80.lv/articles/creating-ocean-waves-vfx-in-houdini)、主役の波の誘導（Gnomon・Aleix）、[Tidal Wave](https://forums.odforce.net/topic/17261-tidal-wave/)、[Gen Li](https://genlifx.com/miscs/2021/03/24/houdini-breaking-wave-m-f-a-thesis/)、Arabacıoğlu（分類は推定） | 崖や浜に打つ波、押し寄せる津波。見ていない | 1.5 倍の流速の場、線形の場への誘導、途中で重力を変える、キーで動かす境界、半分の管の型の衝突物 | ある | 文・値の一部 | 描いて合成 | 同上 |
| **形を手か式で作る** | | | | | | |
| [Moana 2](https://www.sidefx.com/stories/moana-2/)（確） | 嵐の大波、崩れる波が雲と消える。見ていない | 配置の段の Wave Deformer の形の上に計算を足す。海流は案内の線と独自の力 | 形（海流は力） | 記事 | オフライン、描く時の CSG | 崩れる瞬間を形で作る。海の状態の書き方と、計算の面と外の海の合わせ方は借りられる |
| [Horizon Forbidden West](https://advances.realtimerendering.com/s2022/SIGGRAPH2022-Advances-Water-Malan.pdf)（記） | 前へ巻く波が線に沿って順に崩れる。絵は見ていない | 「とても薄い造波水槽」の Houdini の計算から始め、手で動かした断面の線を波の線に沿って掃く | 形 | 講演の資料 | 実時間（PS4・PS5） | 断面を線に沿って掃く渡し方の先例。こちらは計算の断面を手で直さない |
| [Ocean Spectrum・Ocean Waves（hero wave）](https://www.sidefx.com/docs/houdini/nodes/sop/oceanwaves.html)（確） | 変形の海、計算でない | 手続きの形 | 形 | 同梱 | 変位の画像 | まわりの海に使う |
| 制作と講座のほか（確・記）：Moana（2016）の変形器、Piper、Interstellar、HOKUSAI: ANOTHER STORY、Ice Age 4（分類は推定）、Mardini、Advanced Tsunami、曲線のブレンド、Killzone 3、Unreal の津波 | 浜の波から 1,200 m の水の山まで。見ていない | 断面の線、手のアニメーション、手の動きとキャッシュの混ぜ合わせ、式の図鑑 | 形 | 原稿・記事・有料 | ほとんどオフライン | 崩れる瞬間を形で作る |
| **資料から分からない** | | | | | | |
| [Frozen 2](https://www.sidefx.com/community/frozen-ii/)（見直し） | 嵐の海で筒の形に崩れる波、約 25 フィート（約 7.6 m）の崩れる波。見ていない | Houdini の FLIP の水槽。VEX の HDA で 3 次のストークス波の式から速度の場を作り、計算に使う。しぶきのために FLIP を書き換え。波の彫り直しもした | 書かれていない（場が境界だけか、途中ずっとかは不明） | SideFX の記事 | オフライン | 今の 2D にいちばん近い制作の例。速度の場の効き方が分かれば比べられる |
| （確・記）Pipewave（hip €250）、Perfect Wave（$155）、有料の浜の講座、True Spirit、Vikings: Valhalla、ゴジラ-1.0、KUBO、Imageworks の浜、The Meg、SideFX のトーク（FMX 2018 Water）、COD WWII、The Wave（崖崩れの約 80 m の津波。起こし方は資料にない） | 管の巻き・嵐の海・津波など。どれも見ていない | 頁と記事に書いていない | 不明 | 有料か動画 | オフライン（COD は 60 fps） | 見るか買わないと分からない |
| **部品と渡す道** | | | | | | |
| [FLIP の部品](https://www.sidefx.com/docs/houdini/nodes/dop/flipsolver.html)（狭い帯・境界の層・圧力の適応）、Whitewater、MPM、Gas Wind（確） | 波の例なし | 部品。Gas Wind は水の速度を風の向きへ寄せる | Gas Wind は制御 | 同梱 | — | 狭い帯と適応は 3D を軽くする道。Gas Wind は使わない |
| [浅水の解き手](https://www.sidefx.com/docs/houdini/heightfields/shallowintro.html)・[Vellum の流体](https://www.sidefx.com/docs/houdini/vellum/vellumvsflip.html)・[POP Fluid](https://www.sidefx.com/docs/houdini/nodes/dop/popfluid.html)（見直し） | 波の例なし | 浅水は高さの場で、文書は砕ける波を出せないと書く。Vellum の流体は主に小さな規模（しぶき・注ぐ水）。POP Fluid は点の密度を保つ力で簡単な流体の効果を出す | — | 同梱 | — | 大波の巻きには使わない（理由は左） |
| [Labs VAT 3.1](https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.0.html)・Alembic・Houdini Engine（確）と Unity の読み解きの例（記） | — | オフラインの計算を焼いて再生。Houdini Engine は実行中の計算を支えない | — | Labs は無料 | 【記録】以前の確かめで VAT 3.1 を自作の Built-in の読み解きで再生 | 3D の面は画像の大きさが壁（§6.4） |

### 0.3 確立した方法はあるか、計算の途中に何を入れるか、2D と共有する所

| 方法の型 | 使っている所 | 手順の公開 | 巻きは何から | 計算の途中の制御（進行役の読み） |
| --- | --- | --- | --- | --- |
| 形を先に決め、計算を上に足す | Moana（2016）・Moana 2・Adrift・Piper・Interstellar・HOKUSAI: ANOTHER STORY・Horizon | 概要と 2 頁の原稿だけ | 変形器・断面の線・手のアニメーション | 崩れる瞬間を形で決める。10/7 の指導教員の言葉「そこはアートコントロールじゃダメだよ」に当たると読む |
| 誘導・速度の注ぎ込み・独自の力 | Beach Tank・Guided Ocean Layer・Adrift・Swapped・Pirates 5・講座の多く | 公式の道具と講座で値まで出ているものがある | 決めた速度の場や力 | 途中に速度や力を足す |
| 境界から決めた海を入れ、中は重力だけ | SideFX の Wave Tank・FLIP Configure Wave Tank・Guided ocean waves（海底を足すと FLIP Configure Beach Tank） | 同梱、手順と値が文書にある | 入れる海の状態（公式の例では逆向きの波の混ざり）と、足せば海底の浅くなり | 途中にない。境界の層や帯の中だけ速度を上書きする。公式の例に大波の巻きはない |
| 釣り合わない値・崩れる手前の波を初めや境界に置く | Moana（2016）の計算の版（境界）、Mihalef 2004・Lubin 2015・Mostert 2022（初めの状態） | 2 頁の原稿と論文 | 物理でない急な境界の値、形と釣り合わない初めの速度 | 途中にない。崩れは置いた値から来る。10/7 の「大きい波を用意したから大きな波ができました」に近い形と読む |
| Houdini の FLIP の水槽を波の式の速度の場で動かす | Frozen 2 | 記事の数行 | 3 次のストークス波の式から作った速度の場、波の彫り直し | 書かれていない |
| 今の 2D の計算 | — | リポジトリの記録 | 実験の群の条件（入口の帯）と、その後の重力の時間発展 | 入口の帯の中だけ流速を寄せる（造波板の代わり）。帯の外にはない |

- 答え：制作の「確立した方法」は、いつ・どこで砕けるかを決めるために形を先に決めるか、制御の力で導く方法だった（Moana 2016 の計算の版も、境界の値で崩れを振り付けた）。Moana の原稿は、映画では崩れの時と所を思いどおりにする要求があるので手続きの道具が選ばれがちだと書く【文献】。計算の途中に制御の力を入れない公式の型は「境界から海を入れ、中は重力だけ」の水槽で、その手順は公開されているが、公式の例は大波の巻きを示していない。3 つ（途中に制御の力を入れない・手順が公開・厚い唇の巻きを示した）を同時に満たす Houdini の方法は、調べた範囲で見つからなかった【考え】。Frozen 2 は Houdini の FLIP の水槽で筒の形の崩れる波を作った制作の例だが、速度の場の効き方と彫り直しの範囲が書かれていないので、この 3 つに当てはまるかは分からない。
- 今の 2D の計算が既に共有している所【記録・考え】：
  1. 解き手は同じ Houdini の FLIP。
  2. 入口の帯で格子の流速を線形の波の値へ寄せ、帯の外は重力だけ：公式の境界の層（FLIP Solver の Use Boundary Layer）と SOP の Boundary Flow と同じ考え。流体力学の計算の緩和の帯（Jacobsen ら 2012）の重みを使っている。
  3. 下流の吸う帯：公式の境界の層が「跳ね返りを減らす」のと同じ役。
  4. 面にして Unity へ渡す道：Labs VAT 3.1 を以前の確かめで自作の Built-in の読み解きで再生した。断面を横に掃いた Unity の再生の試作は、薄い水槽の断面を線に沿って掃く Horizon と同じ形。
- 今の 2D の計算が公式の道具にない所：(1) 実験で巻いたと記録された群の位相（焦点）を選ぶ。公式の Ocean Spectrum の位相は乱数の種で、集める道具はない。(2) 有限水深の速度の形（cosh）と Wheeler の伸ばし。公式の Ocean Evaluate は深い水の指数の減りだけで、水深と波長の比が今の 2D の値（kh 約 1.95）では、底近くの水平の速度が指数の約 2 倍になる【計算：1/cosh(1.95)=0.28、e^−1.95=0.14】。(3) 狭い帯を使わない。粒子 0.5 m で帯 4 m は前の面を変えて巻かなかった【記録】。(4) 走らせる前に判定の幅を決め、別の者が記録から数を読み直す確かめ。ただし判定のうち入口の波・焦点の場所と時刻・計算の中の減り・着水の時刻と場所は外れた【記録】。

### 0.4 3D の段の候補と進行役の推し（決めるのは指導教員）

| | 2D のまま群を強める | 2D の結果を横に並べて始める 3D | 入口から一方向の群を入れる 3D の水槽 | 入口から向きの違う波を入れる 3D の水槽 |
| --- | --- | --- | --- | --- |
| 中身 | 同じ仕組みの中で、群の強さ（崩れの強さを決める成分の振幅の和）を上げる。10/9 の利用者の指示の道 | 2D の計算の巻く少し前の状態を横に写して並べ、重力だけで 3D で解く（Mihalef ら 2004 と流体力学の 3D の砕波の始め方） | 公式の Wave Tank と同じ骨組みに、今の 2D の群を入れる | 同じ骨組みに、向きの違う波（向きの広がりか、角度をつけて交わる二つの群）を入れる。利用者が 10/10 に止めた |
| 1 本の時間・メモリー【推定】 | 5〜7 時間・約 7 GB | 幅 20 m で 6〜10 時間・約 13 GB、40 m で 13〜19 時間・約 21 GB | 幅 20 m で 14〜21 時間・約 13 GB、40 m で 28〜42 時間・約 21 GB | 幅 70〜135 m で 2〜6 日・32〜57 GB と格子の分（64 GB に近いか越える） |
| 見えるもの | 唇が厚くなるかを見られる（確かめていない）。頂は横に同じまま | 唇が付くまで 2D と同じ形、付いた後の 3D の崩れ。唇は薄いまま | 同じく唇が付くまで 2D と同じ形【考え：Lubin・Mostert から】。新しく見えるのは落ちた後の崩れ | 短く高い頂と厚い唇が出るかを確かめられる（確かめていない） |
| 主な危険 | 粒子 0.25 m では唇と囲んだ空気が細かさで落ち着かない（唇の値は目安） | 唇の厚みが格子 2 個で、3D の粒子の揺らぎで唇の膜に穴があきうる | 同左。吸う帯を短くすると跳ね返りが焦点へ戻りうる | メモリー、狭い帯（粒子 0.5 m で前の面を変えた記録）、1 本が日の単位で 10/29 までに 1〜2 本 |

進行役の推し【考え】：唇を厚くする物理の候補は、群を強めることと、向きの違う波を集めることの二つと読む。安いのは 2D のまま群を強める道で、1 本 5〜7 時間で唇が厚くなるかを見られ、10/9 の利用者の指示（実験の仕組みの中で物理の条件を変えて大きさと感じへ近づける）の道でもある。だからこれを先に推す。3D で短く高い頂を出しうる候補は、向きの違う波を入れる水槽だけだが、1 本が日の単位で、メモリーが上限に近く、狭い帯の 2D での確かめが先に要る。一方向の 3D の水槽と横に並べる 3D は、唇が付くまで 2D と同じ形になる見込みで、新しく見えるのは落ちた後の崩れなので、単独では推さない（横に並べる 3D は、3D の面を Unity へ渡す道を早く確かめたい時に使える）。前の版は一方向と向きの違う波の 3D の水槽をまとめて推したが、一方向の分で得られるものを大きく書いていたので改めた（§10）。

## 1. 方針

### 1.1 読み方

- 「調査」：Houdini で大波を作っている例とその方法。使う道具と設定、制御や誘導の力を使っているか、再現できるほど手順が公開されているか、実時間の作品へどう渡しているか（Q50 の扱い 2）。Q51 で範囲は Houdini の外へ広がった。この報告はそのうち Houdini の部分。
- 「大波」：立ち上がり、険しい（鉛直を越える）前の面、前へ巻く唇（その厚さ）、裏返り、崩れ、白い水のどこまでを出しているかを、絵や記された時刻で確かめて書く。見られなかったものはそう書く。
- 「良いもの」：Q41 の範囲（重力と、風のように波を自然に起こす力。造波板・海底・初めの波の場のような初めの条件と境界の条件は、理由を書けば選んでよい）で、手順が確かめられるもの【考え：Q41・Q44 から】。合うかどうかは指導教員が判断する。この報告は、例ごとに計算の途中で何が制御として働くかを書くところまでにとどめる。

### 1.2 調べる前に決めた 6 点

1. 見せる波とどこまでか（高さ・立ち上がり・前の面・唇の厚み・裏返り・崩れ・白い水）、指させる証拠、見られなかった時はそう書く。
2. Houdini の方法：解き手（FLIP、狭い帯、誘導の層・境界の層、Ocean Spectrum・Evaluate・Source、Wave Tank、POP、Vellum の流体、MPM）、領域と解像度、波の起こし方（造波板、流れ込み、初めの波の場、スペクトル、集まり、海底、衝突物）、使った力の全部。
3. 巻きの作り方の分類：P 重力と自然な設定／B 初めの条件・境界の条件だけ／G 誘導・制御の力／S 形を手で作る。何が制御かを書く。まとめの段で次を足した：B\* 形と釣り合わない速度や崩れる手前の険しい波・物理でない急な値を、初めや境界に置いて崩す／U 資料から分からない／部品／渡す道。
   - P と B の境：どちらも計算の途中の力は重力だけで、境界や初めに海を入れる点も同じ。P は、巻きを起こす仕組み（群の集まり・海底の浅くなり）を条件として置いたもの、B は仕組みを置かずに海の状態を入れるもの。違いは仕組みを置いたかだけで、Q41 の上でどちらが良いという分け方ではない。本作の FLIP42 の入口の帯も、公式の Wave Tank の境界の層も、指導教員の確認を受けていない（Q41 の扱い 4）。
   - B と B\* の境：入れる値が物理の波として釣り合っているか。Moana（2016）の計算の版の境界の値と、Mihalef・Lubin・Mostert の初めの速度は、著者が物理でない・人工のと書くので B\*。
4. 再現のしやすさ：手順・節点・値の公開、費用と使用の条件。
5. 実時間・最後の絵への渡し方と、その大きさと費用。
6. ここで要るもの：この機械での時間、危険、Q41 との関わり（判断は指導教員）。

### 1.3 調べた所

- SideFX の文書（Houdini 22.0 のウェブ版と、この機械の 21.0.729 の help の zip）、棚の道具の script（`dopparticlefluidtoolutils.py`、`ExtraTools.shelf`）、help の絵と動画。見直しの段で、Steam の Houdini Indie（22.0）の `python3.13libs/dopparticlefluidtoolutils.py` が 21.0.729 の `python3.11libs` の同じファイルとバイト単位で同じことを確かめた。
- SideFX のサイトのチュートリアル・masterclass・トーク・制作の記事、SIGGRAPH の講演の原稿（Moana、Pirates 5、Horizon は文字を読んだ）、CGWORLD・fxguide・Art of VFX・befores & afters・AWN・Post Magazine・80.lv。
- 作り手の講座の頁（Gumroad・Rebelway・Gnomon など、頁だけ）と掲示板（SideFX、odforce）。
- 見直しの段：Frozen 2 の SideFX の記事、浅水の解き手の手引き、Vellum と FLIP の比べ、POP Fluid の文書、Unity の画像の大きさの上限の文書。
- 前の調べ（`Unity/Build/SURVEY47/`）と重なる所は読み直した所だけを書いた。

## 2. 目標

1. Houdini で大波（立ち上がり・険しい前の面・厚い唇・崩れ）を出す確立した方法があるかに、例ごとの証拠で答える。
2. その方法が計算の途中にどんな力と条件を使うかを並べて示す（Q41 に合うかの判断は指導教員）。
3. 今の 2D の計算（FLIP42）がそれらと共有する所と違う所を示す。
4. 3D の段の候補を、Houdini の手順・解像度・この機械での時間とメモリー・Unity への道・危険・確かめることとともに示し、理由を付けて推す。

## 3. 結果

### 3.1 数

- 53 項目（`items.json`）。分類ごと：P 2（本作、FLIP Configure Beach Tank）、B 2（Wave Tank、Guided ocean waves）、B\* 3（Moana 2016 の計算の版、Mihalef 2004、Lubin・Mostert）、G 14、S 11、U 12、部品 6、渡す道 3。
- G と S のうち、分類が書き込み・章の名・検索の要約からの読みの項目は 5（G：Crashing Wave、Wave in a Box、Arabacıoğlu。S：Ice Age 4、Lee 2010）。残る G 11・S 9 は資料の文で作り方が書かれている。
- 巻きの作り方が資料の文で分かった制作・講座は、S か G か、物理でない境界の値で崩した Moana 2016 の計算の版（B\*）だった。P と B は公式の道具と本作だけで、公式の水槽は大波の巻きを示していない。Frozen 2（Houdini の FLIP の水槽を波の式の速度の場で動かした制作）と The Wave（崖崩れの津波）は、起こし方や制御の有無が資料にないので U にした。
- 研究の 3 項目（Mihalef、Lubin・Mostert、Lee）は Houdini の外。Mihalef と Lubin・Mostert は計算の途中に力を入れないが、初めの速度が形と釣り合わない始め方なので B\* にした。

### 3.2 SideFX の公式の道具（手元の script で網を確かめた）

- Wave Tank：H21.0.729 の棚の script（H22 の script も同じ）は、FLIP Solver 自身の境界の層（面と速度は Ocean Source から）、狭い帯、圧力の適応、Gravity DOP を組む。Gas Guiding Volume と POP Advect は作らない。境界の層は層の中の速度を上書きし、面より上の粒子を消して下を足す（固い境界の条件）【文献・script】。help の共通の説明（Volume Source と Gas Guiding Volume）は古い網の説明で、script と合わない。
- FLIP Configure Wave Tank と Guided ocean waves：境界の帯でスペクトルの速度と静水圧を注ぎ、中は重力だけ。文書は崩れを「逆に流れる粒子が前へ進む粒子とぶつかる」ためと書き、それは Directional Movement 0.3 で風と逆向きの成分を残す設定から来る【文献】。help の動画 2 本では、20 m ほどの箱の頂の白いこぼれとしぶきで、厚い唇はなかった【見た】。
- Beach Tank：POP Advect by Volumes で傾けた海の速度を 1.5 倍で毎ステップ足す（Velocity Scale 1.5、Treat as Wind 切）、浜の Stick on Collision 0.1 m【script】。文書の「速度を弱めると浅くなるにつれて自然に崩れる」は、この誘導と浅くなりが混ざった結果で、分けられない【考え】。
- FLIP Configure Beach Tank：Boundary Flow（Pressure）と浜の衝突物だけで、速度の傾きも advect もない【script】。help の浜の動画（NPS_beach.mp4）の一コマに頂の下の空洞が見えたが、それは面の作り方の比べの動画で、計算の設定は書かれていない【見た】。
- Ocean Spectrum の位相は乱数の種から作られ、phase の体積として出る。深さの減りは None・Exponential・Exponential by Frequency だけ【文献】。
- 浅水の解き手（SOP）：高さの場で水を解く。手引きの「制限」の節は、砕ける波は出せず、しぶきも出せないと書く【文献】。Moana 2 の記事では 19.5 の機能として挙がる。大波の巻きには使えない。
- Vellum の流体：Vellum と FLIP の比べの頁は、Vellum の流体を「主に小さな規模（しぶき、注ぐ水、物を満たす）」に使うと書き、泡やしぶきを作る場を出さない。FLIP は小さな規模から大きな規模まで、浜の砕ける波にも使うと書く【文献】。
- POP Fluid：近くの点どうしに力をかけて密度を保つ節点で、「まとまり・簡単な表面張力」のような簡単な流体の効果を点で出す、と書く。海や波の例はない【文献】。
- Houdini 22 の What's new に、FLIP と海の道具の新しい項目はない【文献】。

### 3.3 制作の例

- 嵐の大波の作り方が書かれた制作（Moana 2、Moana、Adrift、Piper、Interstellar、HOKUSAI: ANOTHER STORY、Horizon）は、どれも形を先に決めた。制御の力も普通に使われる（Adrift の独自の誘導の速度と面に垂直な重力、Swapped の速度の注ぎ込みと高さで変わる重力、Pirates 5 の架空の力、Moana 2 の場面ごとの独自の力）【文献】。
- Moana（2016）の計算の版は、Disney 独自の解き手で、境界の条件だけで崩れを起こしたが、境界の値は「物理ではあり得ないほど急な波」で、著者はそれを崩れを振り付ける制御の仕組みと呼ぶ【文献】。SideFX は FAB の技術が後に Houdini の FLIP に入ったと書くが、どの節点・設定かは確かめていない。
- Frozen 2（Walt Disney Animation Studios、2019。SideFX の記事 2020-08-11）：嵐の海の場面の大きな筒の形の崩れる波を、Houdini の FLIP の水槽の仕組みで作った。効果の監督の Erin Ramos は、波の式（3 次のストークス波）を VEX で HDA に書き、波長と振幅を入れて計算に使う速度の場を作ったと話し、「the equation for third-order Stokes waves driving the simulation」と書く【文献】。しぶきのために FLIP の解き手を書き換え、波の振り付けが構図の要だったので FLIP の計算と波の彫り直しの両方を Houdini で行ったとも書く【文献】。速度の場が境界だけで効くのか、初めの状態か、計算の途中ずっと寄せるのか、彫り直しが巻きの形に入ったのかは書かれていない。今の 2D の計算（入口の帯で線形の波の流速へ寄せる）にいちばん近い制作の例だが、制御の有無は分からない（U）。
- Horizon Forbidden West は、Houdini の薄い造波水槽の断面を 1 枚の画像に焼き、波の線に沿って掃いて実時間で出した。ただし計算の断面は直しが多すぎて、手で動かした曲線に替えた【文献】。
- 日本の制作（ゴジラ-1.0、HOKUSAI: ANOTHER STORY）は Houdini の水を使ったが、大波の巻きの作り方は公開されていない【文献】。

### 3.4 作り手の講座と掲示板

- 値まで公開された講座・解説の作り方は、線形の海の速度への誘導（POP Advect by Volumes、Gas Guiding Volume、Boundary Flow）か、自分で作った速度の場の注ぎ込み（Volume Source、@v、Trail と VDB）で、巻きの形は型の衝突物・途中の重力の変更・キーの境界で決める例もあった【文献】。
- 管のように巻く波の例（Pipewave、Perfect Wave）は方法が頁になく、確かめるには動画を見るか購入が要る。
- 掲示板には「スペクトルを強くすると制御できないしぶきになった」「造波板で始めて細かくすると全体がしぶきだらけになった」という声がある【文献】。線形の海を強めるか動く板で巻かせる道の難しさの例として記録した。
- Houdini の FLIP を造波水路の実験と比べた作り手の例・論文は見つからなかった（ウェブの検索も含む。見直しの段の検索でも新しい物は出なかった）。

### 3.5 実時間へ渡す道

- Houdini の大波を実時間に出した製品の例は、どれもオフラインの計算か手の形を焼いて再生する形で、Houdini Engine は実行中の計算を支えない【文献】。指導教員の 9/23 の文（「サーフェス化してリアルタイムに表現」）と合う。
- 公式の Labs VAT 3.1 の Unity 用の陰影は URP だけで、この作品は Built-in。Step 18 で自作の読み解きを照合済み【記録】。3D の面は画像の大きさが壁になる（§6.4）。

## 4. 分かったこと

1. Houdini で大波を作る確立した方法（制作と講座の普通のやり方）は、形を先に決めるか、計算の途中で制御の力で導く方法だった。崩れる瞬間を形や力で決める点で、Q39（崩れる瞬間をアートコントロールで作らない）と Q41（制御するための意味が分からない力を入れない）の言葉に当たると進行役は読む【考え】。判断は指導教員。借りられるのは道具の組み合わせ（FLIP、境界の層、狭い帯、白い水、面にして VAT で渡す）、粗く決めてから細かくする進め方、海の状態をビューフォートの段のスペクトルで書く形（Moana 2、Pirates 5）、計算の面と外の海を描く時に合わせる手（Moana 2 の CSG）、薄い水槽の断面を線に沿って掃く形（Horizon、RT48）である。
2. 計算の途中に制御の力を入れない公式の型（境界から海を入れ、中は重力だけ）は、FLIP42 と同じ骨組みである。公式の道具には、群を集める位相の道具と有限水深の速度の形がない。そこは FLIP42 の自作の帯が持っている。
3. 「手法が確定しているものを借りる」という指導教員の理由に照らすと、借りられる確定した部分は骨組み（境界の層・Boundary Flow）と渡す道（VAT）で、厚い唇の巻きを作る部分には、調べた範囲で手順が公開された確定した方法がない。FLIP42 は実験で巻いたと記録された群の条件を使い、帯の外は重力だけで巻いたが、唇は薄く、判定 A1・A3'・B1・D3 は外れ（D1・D2 は入った）、実験より手前で早く崩れた原因は分かっていない【記録】。Frozen 2 は Houdini の FLIP の水槽で筒の形の崩れる波を作ったが、手順と制御の有無は公開されていない。研究の 3D の計算（Mihalef、Lubin、Mostert）は途中に力を入れずに巻かせるが、形と釣り合わない速度や崩れる手前の波から始める【文献】。
4. 横にどこも同じ 2D の状態から 3D を始めても、唇が付くまでは 2D と同じ形になる（Lubin & Glockner 2015、Mostert ら 2022）【文献】。だから 3D にするだけでは唇は厚くならない。短く高い頂と厚い唇を物理で出す候補は、向きの集まり（入口の条件）か、より強く巻く群である【考え：確かめていない】。
5. 急な面で誘導の層の粒子がすべる（Adrift）、狭い帯が前の面を変える（FLIP42 の R1）、格子の大きさが 2 進で割り切れないと圧力が解けない（FLIP42 の R4）など、3D の水槽で起こりうる困りごとの記録がある。

## 5. 現在地

- Houdini の部分の調べは読むだけで終えた（53 項目）。ダウンロード・インストール・計算はしていない。
- 動画で方法を確かめていない例が多い（§7）。
- 2D の計算（FLIP42 の R3・R4）は終わり、報告は指導教員の返事待ち。新しい計算（3D の水槽など）は始めていない（Q49）。
- 前の調べ（毎フレームの計算の例）の冒頭に、読み方の違い（Q50）と範囲の広がり（Q51）とこの報告への案内を書き足した。
- Q51 の Houdini の外の実装の手法の調べは、まだ始めていない。

## 6. 次（候補。決めるのは指導教員と利用者）

### 6.1 四つの候補の時間とメモリー【推定】

R3 の記録（最大 1,127 万粒子、平面 1 m² あたり約 4,690 粒子、巻く前 1 コマ約 3.0 秒・巻く所 約 7.5 秒）を粒子の数に比べて伸ばした。時間は、粒子の数に比例すると置いた下限と、その 1.5 倍（圧力の解きは格子が増えると比例より重くなりうる）。メモリーは、R3（1,105 万粒子で 6.7 GB）と R4d（2,163 万粒子で 8.0 GB）の記録の最大の使用量【記録：`Unity/Build/FLIP42/runs/R3/run_c3793.json`・`R4d/run_c3241.json` の rss_peak_gb】から、約 5.3 GB＋100 万粒子あたり約 0.12 GB と置いた。途中保存の大きさは R3 の 1 粒子あたり約 55 バイト（61 個で約 38 GB【記録：RT48】）から。

| 候補 | 幅 W | 粒子 | コマ | 1 本の時間 | メモリー | 途中保存 1 個 |
| --- | --- | --- | --- | --- | --- | --- |
| 2D のまま群を強める | 板（2 m） | 約 1,100 万 | 約 4,500 | 5〜7 時間（FLIP_Plunging_ja.md §7 の見込み） | 約 7 GB【記録】 | 約 0.6 GB |
| 2D の結果を横に並べて始める 3D | 20 m | 約 6,500 万 | 523 | 6〜10 時間 | 約 13 GB | 約 3.6 GB |
| 同上 | 40 m | 約 1.3 億 | 523 | 13〜19 時間 | 約 21 GB | 約 7 GB |
| 入口から一方向の群を入れる 3D の水槽 | 20 m | 約 6,200 万 | 約 2,300 | 14〜21 時間 | 約 13 GB | 約 3.5 GB |
| 同上 | 40 m | 約 1.25 億 | 約 2,300 | 28〜42 時間 | 約 21 GB | 約 7 GB |
| 入口から向きの違う波を入れる 3D の水槽 | 70〜135 m | 2.2〜4.2 億 | 約 2,300 | 2〜6 日 | 32〜57 GB と格子の分 | 12〜24 GB |

- 時間に入っていないもの：起動のし直しと途中保存の書き出し・読み込み（R4d は 15.2 時間で 32 回起動した。3D の途中保存は 1 個 3.5〜24 GB）、毎コマの面の作り。実際の時間はこの表より長くなる。
- メモリー：向きの違う波を入れる水槽は、粒子だけで 32〜57 GB【推定】。3D では格子も体積に比例して増え（幅 135 m・格子 0.5 m で約 4,400 万セル【計算】）、板の記録の係数に格子の分がどれだけ含まれるかは分けられないので、上の端は本機の 64 GB を越えうる。その時は狭い帯が要るが、粒子 0.5 m で帯 4 m は前の面を変えて巻かなかった【記録：R1】ので、2D の板で深い帯（例 12〜16 m）が R3 と判定の幅に入るかを先に確かめる。
- 向きの違う波の幅：交わる 2 群なら横の模様の周期で決まり、交わる角度 60° で Lc/(2 sin 30°) = 約 135 m ごとに対称の面がある【計算】。向きの広がりの群の頂の長さも 1〜数波長と読む【考え】。だから 70〜135 m とした。
- 最初にする時間の試し：選んだ候補の始めの 100 コマ（約 1 時間）と巻く所の 48 コマ（約 1 時間）。1 コマの時間とメモリーを測り、この表を置き換える。

### 6.2 3D の水槽（一方向・向きの違う波）の Houdini での作り【考え】

1. FLIP42 の水槽の作り（`Tools/GWWaveGen/flip42/g_build_tank.py`、DOP FLIP）を 3D の水槽に広げる。水槽は進む向き 135〜800 m（帯 135〜270 m、波が進む所 270〜650 m、吸う帯 650〜800 m）、幅 W、水深 42 m。帯の出口を −15 の点（造波板から 268.8 m）に置くのは、そこまでは水面の時系列が線形の重ね合わせに近かったから【記録：FLIP_Plunging_ja.md §2.1】。
2. 帯は今の VEX（32 成分、有限水深の cosh、Wheeler の伸ばし、Jacobsen の重み）をそのまま使い、成分に向き θ を足す。一方向は θ = 0。向きの違う波は、向きの広がりか交わる 2 群（McAllister ら 2019 の形）で、利用者が 10/10 に止めた（Q46）ので指導教員の判断の後に限る。
3. 始め方：始めの時刻は、−15 の点で線形の水面が最大の 1 割を越える 73.7 s【計算】の少し前（約 65 s）とした。2D の計算は静かな水から始め、1 周期かけてなだらかに立ち上げた。65 s から始めるなら、水槽の水を線形の重ね合わせのその時刻の水面と速度で満たすか、立ち上げを入れる。静かな水のまま帯だけに 1 割近い波を課すと、始めに乱れが出る【考え】。
4. 吸う帯：271 m から 150 m に縮めると、いちばん長い成分（0.0668 Hz、水深 42 m で波長 約 266 m【計算：ω² = gk tanh kh】）の波長の 0.56 倍になる（2D の計算は約 1.0 倍）。長い成分は崩れるずっと前に吸う帯に届くので、跳ね返りが焦点へ戻り、焦点の場所と時刻を変えうる【考え】。2D の板で吸う帯 150 m を先に試して焦点が変わらないかを見るか、271 m のまま（粒子が 2 割ほど増える【推定】）にする。
5. 横の境界：一方向は滑る壁で足りる。向きの違う波は、FLIP Solver の Use Boundary Layer に同じ線形の群の面（SDF）と速度の体積を渡す（公式の Wave Tank の仕組み）か、左右対称の群なら焦点の線に壁を置いて幅を半分にする【考え：確かめていない】。
6. 粒子 0.25 m（格子 0.5 m、2 進で割り切れる）。狭い帯は 6.1 の確かめの後だけ。力は重力だけ。CFL と最大小刻みは R3 と同じ。
7. 途中保存は少なく（G: の空きに合わせる）、面は波の所だけを毎コマ作る。

### 6.3 2D の結果を横に並べて始める 3D の作り【考え】

1. R3 の 138.2 s の途中保存（R5'・R3m・R3d がここから始めた）から、進む向き 105〜800 m を切り出し、幅 2 m の板を W/2 回写して並べる。
2. 上流の端 105〜240 m に、同じ線形の群へ寄せる帯を置く（138.2 s のこの辺りの水は線形に近いと読む【考え】）。下流の端は吸う帯。
3. 重力だけで 138.2〜160 s（523 コマ）を解く。横の乱れは足さない。足すなら、それは手の選びとして書く。
4. 見えるもの：唇が付くまでは 2D と同じ形で、唇は薄いまま【考え】。横の違いは唇が付いた後に数値の揺らぎから出るだけ。3D の面を VAT で Unity へ渡す道と、その時間と画像の大きさは、3D の水槽より早く確かめられる。
5. 確かめること：真ん中の断面が唇の付くまで R3 と同じか、横の違いがいつ出るか、Unity での再生の時間。

### 6.4 Unity へ【考え・推定】

1. 毎コマ、粒子から面を作り（Particle Fluid Surface か VDB from Particles）、波の所（例 進む向き 150 m × 幅 W）だけを切り出し、15 万三角形以下に減らす。
2. Labs VAT 3.1 の Dynamic Remeshing（Fluid）で書き出し、Step 18 の自作の Built-in の読み解きで再生する。画像の大きさの壁：
   - Step 18 の並びでは、引く表の画像（lookup）の高さは「コマ数 × (3 × 三角形の数 ÷ 幅 を切り上げ)」になる（2048 × 6174 = 49 コマ × 126 行、85,542 三角形で合う【記録・計算】）。
   - 15 万三角形・240 コマでは、幅 2048 で 52,800 行になり、Unity の上限 16,384【文献：Unity の SystemInfo.maxTextureSize の頁】を越える。幅 8192 なら 13,200 行で上限の中だが、Step 18 で固定した読み込みの上限 8192 を上げる必要がある。その 1 枚は RGBAFloat で約 1.7 GB で、D3D11 の 1 資源の上限（約 2 GB【推定】）に近い。位置と回転の画像を足すと約 2.3 GB【推定】。
   - 手立て：コマか三角形を減らす、引く表を何枚かに分ける、位置と回転の画像だけ半精度にする（引く表の番号は、半精度では 2048 を越えると正しく持てない【考え】）。
   - 50 万三角形・300 コマなら約 9.6 GB で、10 GB の GPU に入らず、引く表 1 枚の大きさも上限を越える。
3. まわりの海は自作の簡単な海（Q48 の扱い 5）。水槽の面と外の海の継ぎ目は、Moana 2 の描く時の CSG のような合わせ方が要る。
4. フレームの時間は RT48 の測り方（PSVR2 に近い片眼の大きさ 3 つ、4×MSAA）で測る。

### 6.5 共通の危険

1. 時間：向きの違う波を入れる水槽は 1 本が日の単位で、10/29 までに試せるのは 1〜2 本【推定】。1〜6 日の計算の間は CPU とメモリーがふさがり、10/29 までの Unity と PSVR2 の作業と取り合う。
2. 置き場：G: の空きは 145 GB（10/11 測った。FLIP42 の `runs/` が 259 GB）。消すのは利用者（Q43 の扱い 3）。
3. 唇の細かさ：厚み 1 m の唇は格子 0.5 m で 2 個分しかない。本当の 3D では FLIP の粒子の揺らぎが横の対称を崩し、薄い膜に穴があいて裂けうる。3D の結果が、断面を横に掃いた見え方より悪く見えることもありうる【考え】。
4. 横の境界：公式の境界の層は層の中の速度を線形の場で上書きするので、焦点の近くの非線形の波（頂が線形の 1.33 倍【記録】）と食い違うと、乱れが入るか跳ね返る。焦点から離して置く。
5. 入口：帯の出口の短い成分の不足（A1、約 5 %【記録】）は 3D でも残る見込み。
6. 唇：一方向の 3D の唇は 2D と同じく薄い見込み【考え：Lubin・Mostert】。向きの違う波で厚くなるかは確かめていない。利用者の選んだ参考の写真（Q45）は指導教員の指示ではない。
7. Q41 との関わり：入口の帯は「遠くから入ってくる波を造波板の代わりに入れる」境界の条件で、焦点（線形の頂の高さ・場所・時刻）を選んでいる。これを認めるかは指導教員が判断する。

確かめること（Q44 の扱い 8 の主な危険だけ）：

- 2D のまま群を強める：凍結した判定の形（A1・D1・D2 と唇の厚み・届く距離）。唇の値は粒子 0.25 m では目安。
- 一方向の 3D の水槽：真ん中の断面が、R3 と同じ判定の幅（C1〜C4）に入るか。3D の水槽と境界が 2D の結果を変えないことの確かめを兼ねる。帯の出口の A1。
- 向きの違う波の 3D の水槽：向き別の成分の振幅と位相（帯の出口）、焦点の場所と時刻、頂の長さ、唇の厚みと届く距離、前の面の険しさ。評価は Q44 の観点（波高・険しい前の面・唇・水の厚みと重さ）で利用者と指導教員がする。粒子 0.35 m は 2D で巻かなかった【記録】ので、粗い方への細かさの比べは役に立たない。

### 6.6 指導教員に伺いたいこと

1. 置き場所：調べの結果は GitHub の imagirelab/GreatWave_2026 の `Docs/Research/`、計算の報告は `Docs/Progress/` に置く（Q51 の扱い 3）。Houdini の外の実装の手法の調べを足して一つにまとめたら、同じ場所に置いてお知らせする。
2. Houdini の「確立した方法」として借りるのは、公式の「境界から海を入れ、中は重力だけ」の骨組みと VAT の渡し方で、巻きを作る部分は今の 2D の計算の実験の群の条件を使う、という考えでよいか。制作の方法（形を先に決める・制御の力）は使わない。入口の帯（造波板の代わり）の扱いもあわせて伺う。
3. 次の段を「2D のまま群を強める」にするか、3D（横に並べる・一方向の水槽・向きの違う波の水槽）にするか。進行役は 2D のまま群を強める段を先に推す（§0.4）。
4. 向きの違う波（短い頂）を入口の条件に入れてよいか（利用者が 10/10 に止めた）。
5. 方法を確かめるために動画を見るか（読むだけでダウンロードはしない）：FMX 2018 Water（約 1 時間）、Crashing Wave の 3 回目、Pipewave。有料の講座（Perfect Wave $155、Pipewave の hip €250）を買うかは利用者が決める。

日付：この報告は、コミットして GitHub に置いた後に、置き場所の答えとして利用者を通して知らせる。Houdini の外の実装の手法の調べは、ゼミの資料の締め切り（10/13 18:00）までに足す予定（利用者の確認待ち）。返事の後に計画を書いて凍結し、時間の試し（約 2 時間）から始める。

## 7. 限り・見ていないもの

- ウェブの動画は一本も見ていない：SideFX の講座（Crashing Wave、Wave in a Box、Pipewave、Masters of the Sea）、トーク（FMX 2018 Water、H16 Ocean Tools、Wagner の FLIP、HIVE 2022）、制作の講演（True Spirit、Swapped、ゴジラ-1.0、COD WWII、The Wave）。これらの波の起こし方と巻きの有無は、頁の文・章の名・書き込みからの読みである。Frozen 2 も記事の文だけで、映像は見ていない。
- PDF の図と写真は見ていない（文字だけ抜いて読んだ）。どの制作の例も、波の高さ・前の面の険しさ・唇の厚みを絵で確かめていない。
- 棚の script で網を確かめたのは H21.0.729 で、見直しの段で H22（Steam の Houdini Indie）の同じ script がバイト単位で同じことを確かめた。読んだ範囲の文書は 22.0 と 21.0 で同じだった。
- 3D の時間とメモリーの数は、2D の板の記録から伸ばした見積もりで、時間の試しで置き換える。
- FAB の技術が Houdini の FLIP のどの設定に当たるかは確かめていない。Frozen 2 の速度の場がどこに効くかも確かめていない。
- 確かめの段の一覧は Swapped の途中で切れて渡されたので、それより後の 26 項目は記録だけによる。
- 確かめに一度だけ、`Unity/Build/` が Git の対象外かを読むだけの git の命令で見た（変更はしていない）。

## 8. 記録の間の食い違いと直したこと

- Wave Tank と Beach Tank が Gas Guiding Volume で海の速度を足す（`sidefx_ja.md` §1.1、`artists_ja.md` 項目 1・2）：H21 の script では、Wave Tank は FLIP Solver の境界の層、Beach Tank は POP Advect by Volumes で、Gas Guiding Volume は作らない。分類は Wave Tank が B（`artists_ja.md` の G を直す）、Beach Tank が G のまま。
- Guided ocean waves の値（20×20×10 m など）は手引きの頁の値で、FLIP Configure Wave Tank の既定は 15×5×15 m・粒子 0.15・Velocity Driven。
- help の浜の動画の巻きは「何コマか」ではなく 10 枚のうち 1 枚で、その動画は面の作り方の比べ。
- 3D の時間の見積もりが記録ごとに違った（`sidefx_ja.md` 4〜15 時間、`artists_ja.md` 幅 40 m で 100〜140 時間、`production_ja.md` 幅 100 m で約 26 日、`realtime_ja.md` 狭い帯 8 m で 1〜3 時間）。どれも根拠が足りないので、§6.1 の R3 の 1 コマの時間と粒子の数からの見積もりに置き換え、時間の試しで測るまでの仮の値とした。
- VAT の画像の大きさ：位置と回転の画像を入れて、15 万三角形・240 コマで約 2.3 GB（`sidefx_ja.md` の 1.7 GB、`realtime_ja.md` の 1 三角形 56 バイトによる値を置き換える）。引く表 1 枚の高さと大きさの壁は §6.4。
- Wave in a Box の作者の表示は PIXELSTUFF（頁を読み直した）。
- Moana（2016）の計算の版は「力を足していない自然な崩れ」ではなく、境界の値を制御として使う（B\*）。
- Moana 2 の浅水の解き手と TMA は、採用の決め手になった 19.5 の機能として挙げられただけで、カットで使ったとは書かれていない。
- 見直しの段：The Wave を P から U へ移した（起こし方は資料になく、「崖崩れで起こしたなら」という読みだけだった）。Mihalef 2004 と Lubin・Mostert を B から B\* へ移した（初めの速度が形と釣り合わない始め方で、Moana 2016 の計算の版と同じ扱いにした）。Frozen 2・浅水の解き手・Vellum の流体・POP Fluid を足した。「ただ一つの例」という強い言い方を本文・`items.json`・`production_ja.md` から消した（Q39「強い主張の言葉を一切使うな」）。

## 9. 主な出典

SideFX の文書と道具：

- Wave Tank https://www.sidefx.com/docs/houdini/shelf/wavetank.html ・海の道具の違い https://www.sidefx.com/docs/houdini/shelf/ocean_differences.html ・Ocean Source https://www.sidefx.com/docs/houdini/nodes/sop/oceansource.html
- FLIP Solver（DOP）https://www.sidefx.com/docs/houdini/nodes/dop/flipsolver.html ・FLIP Solver（SOP）https://www.sidefx.com/docs/houdini/nodes/sop/flipsolver.html ・狭い帯 https://www.sidefx.com/docs/houdini/fluid/narrowband.html
- Guided ocean waves https://www.sidefx.com/docs/houdini/fluid/sopoceanwaves.html ・FLIP Configure Wave Tank https://www.sidefx.com/docs/houdini/fluid/sopconfigwave.html ・Beach Tank https://www.sidefx.com/docs/houdini/shelf/beachtank.html ・FLIP Configure Beach Tank https://www.sidefx.com/docs/houdini/fluid/sopconfigbeach.html ・Guided Ocean Layer https://www.sidefx.com/docs/houdini/shelf/guidedoceanlayer.html
- Ocean Spectrum https://www.sidefx.com/docs/houdini/nodes/sop/oceanspectrum.html ・Ocean Waves https://www.sidefx.com/docs/houdini/nodes/sop/oceanwaves.html ・Gas Wind https://www.sidefx.com/docs/houdini/nodes/dop/gaswind.html ・Whitewater https://www.sidefx.com/docs/houdini/fluid/whitewater.html ・MPM https://www.sidefx.com/docs/houdini/mpm/overview.html ・H22 の What's new https://www.sidefx.com/docs/houdini/news/22/index.html
- 浅水の解き手 https://www.sidefx.com/docs/houdini/heightfields/shallowintro.html ・Vellum と FLIP の比べ https://www.sidefx.com/docs/houdini/vellum/vellumvsflip.html ・POP Fluid https://www.sidefx.com/docs/houdini/nodes/dop/popfluid.html
- Labs VAT 3.0 https://www.sidefx.com/docs/houdini/nodes/out/labs--vertex_animation_textures-3.0.html ・VAT の Unity の手引き https://www.sidefx.com/tutorials/vertex-animation-textures-in-unity/
- この機械の Houdini 21.0.729 の help（shelf.zip・fluid.zip・nodes.zip・images.zip・videos）と棚の script（python3.11libs/dopparticlefluidtoolutils.py、toolbar/ExtraTools.shelf）。H22（Steam の Houdini Indie）の python3.13libs/dopparticlefluidtoolutils.py

SideFX のサイトの講座・トーク：

- Crashing Wave https://www.sidefx.com/tutorials/crashing-wave/ ・Wave in a Box https://www.sidefx.com/tutorials/houdini-breakdowntutorial-wave-in-a-box-part-01/ ・Masters of the Sea https://www.sidefx.com/tutorials/vfx-studio-oriented-masters-of-the-sea ・Pipewave https://www.sidefx.com/tutorials/pipewave-flip-simulation-tutorial/ ・Mardini Wave https://www.sidefx.com/tutorials/mardini-wave ・Advanced Tsunami https://sidefx.com/tutorials/houdini-tutorial-advanced-tsunami-simulation
- H16 Ocean Tools https://www.sidefx.com/tutorials/houdini-16-ocean-tools/ ・FMX 2018 Water https://www.sidefx.com/forum/topic/55797/ ・HIVE SIGGRAPH 2022 https://www.sidefx.com/houdini-hive/siggraph-2022/

制作：

- Moana 2 https://www.sidefx.com/stories/moana-2/ ・Byun & Stomakhin 2017（Moana）https://history.siggraph.org/wp-content/uploads/2022/09/2017-Talks-Byun_Moana-Crashing-Waves.pdf
- Frozen 2 https://www.sidefx.com/community/frozen-ii/
- Adrift https://www.sidefx.com/community/adrift/ ・https://www.artofvfx.com/?p=22747 ・https://awn.com/news/milk-visual-effects-weathers-rendering-storm-adrift
- Hopper & Wolter 2017（Pirates 5）https://history.siggraph.org/wp-content/uploads/2022/09/2017-Talks-Hopper_The-Water-Effects-of-Pirates-of-the-Caribbean-Dead-Men-Tell-no-Tales.pdf
- Vikings: Valhalla https://beforesandafters.com/2022/04/13/how-that-massive-ocean-storm-scene-was-created-in-the-first-episode-of-vikings-valhalla/ ・True Spirit https://www.sidefx.com/learn/talks/procedural-workflows-for-large-scale-oceans ・Swapped https://cgworld.jp/flashnews/01-202607-Houdini-Swapped.html
- Malan 2022（Horizon Forbidden West）https://advances.realtimerendering.com/s2022/SIGGRAPH2022-Advances-Water-Malan.pdf
- ゴジラ-1.0 https://cgworld.jp/regular/304-godzilla.html ・HOKUSAI: ANOTHER STORY https://cgworld.jp/article/202504-cgw320-hokusai.html ・The Wave https://www.sidefx.com/forum/topic/38376/ ・Piper https://renderman.pixar.com/stories/piper

作り手：

- Supergirl https://80.lv/articles/creating-ocean-waves-vfx-in-houdini ・Tidal Wave https://forums.odforce.net/topic/17261-tidal-wave/ ・Rolling Waves https://forums.odforce.net/topic/27171-rolling-waves/ ・Gen Li https://genlifx.com/miscs/2021/03/24/houdini-breaking-wave-m-f-a-thesis/ ・Perfect Wave https://80.lv/articles/perfect-wave-houdini-fluid-simulation-course

研究：

- Mihalef, Metaxas & Sussman 2004 https://www.math.fsu.edu/~sussman/BreakingWavesElectronic.pdf ・Lubin & Glockner 2015 https://notus-cfd.org/wp-content/uploads/2020/03/jfm_2015.pdf ・Mostert, Popinet & Deike 2022 https://par.nsf.gov/servlets/purl/10414842

Unity：

- SystemInfo.maxTextureSize（Unity が扱う画像は 16384 まで）https://docs.unity3d.com/ScriptReference/SystemInfo-maxTextureSize.html

このリポジトリ：

- [FLIP_Plunging_ja.md](../Progress/FLIP_Plunging_ja.md)（FLIP42 の R1〜R4 と確かめ）、[Step_18_ja.md](../Progress/Step_18_ja.md)（VAT 3.1 と Alembic の再生）、`Unity/Build/RT48/record_ja.md`（断面を掃いた再生の時間、Git 対象外）、`Unity/Build/FLIP42/runs/R3/run_c3793.json`・`runs/R4d/run_c3241.json`（メモリーの最大、Git 対象外）、`Tools/GWWaveGen/flip42/g_tanklib.py`（入口の帯の VEX）

## 10. 見直しを受けて直したこと・取らなかったこと

10/11 に別の者がこの報告・まとめの文・指導教員への文を、制作手順の Q39〜Q51、FLIP_Plunging_ja.md、計算の記録、`items.json` と作業メモと照らして読み直した。

直したこと：

1. Q51（この報告の保存の 21 秒後に記録された指導教員の答え）を冒頭の囲みと §1.1・§5・§6.6 に入れ、この報告を広げた調べのうち Houdini の部分とした。前の調べの冒頭にも Q51 の一行を足した。置き場所の答えを §6.6 と指導教員への文に入れた。
2. 「制御の力も形の指定もなく巻いた例は本作だけ」と、本作を「ただ一つの物理の根拠」とした言い方を消した。入口の帯の中では流速を寄せること（造波板の代わり、指導教員の確認待ち）、研究の 3D の計算も途中に力を入れないこと、Frozen 2 の制御の有無が分からないことを書いた。
3. FLIP42 の判定のうち A1・A3'・B1・D3 が外れ、実験より手前で早く崩れた原因が分からないことを §0.1・§0.3・§4 に書いた。「実験と比べる判定と独立の確かめ」を公式の道具にない良さとして書いた所に、外れた判定を並べた。
4. 「Q41 に合う／合わない」の判定を表と本文から外し、「計算の途中の制御（進行役の読み）」に改めた。判断は指導教員とした。
5. §0 から情報のない名前（案 A・B、A-1・A-2、P・B・G・S・U、R3、A1 など）を外し、候補は中身の名前（「2D のまま群を強める」「2D の結果を横に並べて始める 3D」「入口から一方向の群を入れる 3D の水槽」「入口から向きの違う波を入れる 3D の水槽」）にした。§1 から後の短い名前は冒頭で説明した。
6. The Wave を U へ、Mihalef と Lubin・Mostert を B\* へ移し、P と B の境、B と B\* の境を §1.2 に書いた。分類が推定の 5 項目を数の中で分けた。Swapped を「確（途中まで）」にした。
7. Frozen 2、浅水の解き手、Vellum の流体、POP Fluid を足した（見直しの段で一次の出典を読んだ）。
8. 3D のメモリーを記録から見積もった（§6.1）。VAT の引く表の画像の高さと大きさの壁（§6.4）、吸う帯を縮めた時の跳ね返り（§6.2 の 4）、始め方（§6.2 の 3）、起動のし直し・途中保存・面の作りの時間、10/29 までの作業と機械の取り合い、唇の膜が裂ける恐れ（§6.5）を足した。
9. 一方向の 3D の水槽で得られるものを大きく書いていたので、推す候補を「2D のまま群を強める」に改め、理由を書いた（§0.4）。
10. H22 の棚の script が H21 と同じことを確かめ、§7 の「H22 の script は見ていない」を直した。

取らなかったこと・一部だけ取ったこと：

1. コミットと GitHub への置き（見直しの「置き場所はまだない」）：この段は git を使わない決まりなので、コミットする物の一覧と文を `Unity/Build/SURVEY50/commit_list.txt`・`READY_TO_COMMIT.txt` に用意するまでにした。指導教員への文は、コミットして push した後に送る。
2. 浅水の解き手の文書の言葉：見直しは「大きな海の砕ける波には使えない」と引いたが、文書の「制限」の節の言葉は「砕ける波は出せない」なので、そちらで書いた。19.5 からの機能であることは、その頁では確かめられず、Moana 2 の記事の記述によった。
3. 3D の格子のメモリー：見直しは粒子の分に「格子の分（数 GB）」を足すとしたが、板の記録の係数にも格子の分が含まれていて分けられないので、足し算はせず「上の端は 64 GB を越えうる」と書いた。
4. VAT の手立ての半精度：引く表の番号は半精度では 2048 を越えると正しく持てないので、半精度は位置と回転の画像だけに書いた。
5. 吸う帯の跳ね返り：見直しは「確かめるだけでなく本当の危険」とした。危険として書いたが、起こるとは決めず、2D の板で先に試す道を書いた。
6. FLIP42 と Wave Tank の分け方：両方を B に入れる案もあったが、P と B の境（巻きの仕組みを条件として置いたか）を書き、それが Q41 の上での良し悪しではないことを書く方を選んだ。
