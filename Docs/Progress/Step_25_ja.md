# 25：HMDの候補比較と購入判断の前提

日付：2026-09-25／結果：候補比較と判断材料を文書で整理した。HMDは未所持で、実機の結果はない。代理は購入・注文・アカウント操作・設定変更を行っていない。

この「25」は2026-09-25の[新作業計画](../Design/ArtFirst_Plan_2026-09-25_ja.md)（CP0で利用者の承認待ち）での番号である。本文のD5は同計画の[第7節](../Design/ArtFirst_Plan_2026-09-25_ja.md#7-利用者に決めてほしい事項)、R8・R9は[第8節](../Design/ArtFirst_Plan_2026-09-25_ja.md#8-危険と損切りの発動条件)、CP4・CP5と番号32・34・43は[第4.1節の全体表](../Design/ArtFirst_Plan_2026-09-25_ja.md#41-全体表)を指す。旧設計書の25（収支・反射の物理検証）とは別物である。旧25は旧23・24とともに、2026-09-25の22の中止に合わせて取り消した（[進捗一覧](README.md#波の物理基準独立した小規模検証2026-09-25に22の中止で終了)の「旧23〜25」）。

- 時間の上限：0.5日。実施は同日中の文書作業と読み取り専用の確認だけ。
- 対応するバックログ項目：直接の項目はない。受入の根拠は[05](Step_05_ja.md)の「HMD入手後の必須項目」で、価値としてはV3（船上の立体把握）とV1の前提に当たる。

## 提案の要点

1. **研究室から借りられるなら借用を最優先する。** 条件は、この本機でMeta Horizon LinkかSteamVRを通してOpenXRが動く機種であること、10/9までに手元へ届くこと、10/29まで使えること。
2. 購入する場合は **Meta Quest 3 512GB（公式税込102,300円）と、3m以上のUSB3 Type-C Linkケーブル** を推奨する。接続は有線のMeta Horizon Link。目標90Hz、退避72Hz。
3. 次点はQuest 3S、非推奨はPICO 4 Ultra。Steam Frame、Valve Indexの新規購入、WMR機は本期に適さない（理由は後述）。
4. 判断期限は **9/28（月）、最遅9/29（火）**。10/9までに届けば実機確認を2回行える。10/20までに届かなければVR項目はすべて「未検証」とし、合格条件は下げない。

## 本機の前提（読み取り専用で再確認）

| 項目 | 値 | 確認方法 |
| --- | --- | --- |
| OS | Windows 11 Home 中国語版、25H2（build 26200） | `Win32_OperatingSystem`とレジストリ`DisplayVersion`の読み取り |
| GPU | NVIDIA GeForce RTX 3080（ドライバー32.0.15.9595＝595.95） | `Win32_VideoController`。[02](Step_02_ja.md)と一致 |
| USB | Intel USB 3.20 eXtensible Host Controller | `Win32_USBController`。背面のType-C端子の有無は未確認 |
| OpenXR ActiveRuntime | HKLM・HKCU・WOW6432Nodeのいずれも未登録 | レジストリの存在確認のみ。変更していない |
| Unity側 | OpenXR 1.16.1、Standaloneの描画方式はSingle Pass Instanced（`m_renderMode: 1`）、interaction profileは全て無効 | `Unity/Assets/XR/Settings/OpenXRPackageSettings.asset`と[08](Step_08_ja.md) |
| 追跡原点 | Device（着座）、CameraYOffset 1.2m | `M0XRSetup.cs`・[09](Step_09_ja.md) |

CPUはi7-12700K、RAMは約64GB（[02](Step_02_ja.md)）。Meta Horizon Linkの要件ページは、グラフィックカードの一覧に「NVIDIA GeForce RTX 30シリーズ」を載せ、USBケーブルは3m以上を推奨している。

## 候補比較

価格・在庫は2026-09-25に取得したWeb上の値で、今後変わりうる。実売の最安値は価格.comの表示で、販売店・送料・保証条件は確認していない。

| 候補 | 公式税込価格 | 実売参考（価格.com最安・表示） | 片眼パネル解像度 | 周波数 | レンズ・視野 | PC接続とOpenXR runtime | 評価 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 研究室の借用機 | 0円 | — | 機種による | 機種による | 機種による | Link（Quest系）またはSteamVR | **最優先**。機種・期間・付属品を確認 |
| Meta Quest 3 512GB | 102,300円（2026-04-19改定） | 94,084円・在庫ありと表示 | 2064×2208 | 72／90／120Hz | パンケーキ。水平110°・垂直96°。IPD無段階 | USB有線のMeta Horizon Link。Link自体がOpenXR runtime | **購入時の推奨** |
| Meta Quest 3S 128GB | 59,400円（256GBは77,000円） | 53,568円・在庫ありと表示 | 1832×1920 | 72／90／120Hz | フレネル。水平96°・垂直90°。IPD 3段階 | Quest 3と同じ | 次点。予算を優先する場合 |
| PICO 4 Ultra 256GB | 104,900円（2026-05-01改定） | 100,995円・在庫ありと表示 | 2160×2160 | 最大90Hz | 視野は公式ページに記載なし（未確認） | PICO ConnectとSteamVR。OpenXR runtimeはSteamVR | 非推奨 |

Quest 3を推す理由：

- 片眼の画素数はQuest 3Sの約1.30倍で、PICO 4 Ultraとの差は約2%。パンケーキレンズなので、視野の端でも藍線・爪先・白点を判定しやすい（H3・H6）。
- Meta Horizon Link自体がOpenXR runtimeになる。SteamVRを挟まないので、H1・H2で切り分ける層が一つ少ない。
- 導入済みのUnity OpenXR 1.16.1に、拡張不要のOculus Touch Controller Profileが入っている。
- 有線Linkは無線（Air Link）より帯域が安定し、計測条件を固定しやすい。

注意点：LinkはDisplayPort直結ではなく、映像を圧縮してUSBで送る。細い線や白点への影響はH6で確かめる。Quest 3Sは42,900円安いが、画素が約23%少なくフレネルレンズなので、細部の見え方を最終表示の代表として扱いにくい。PICO 4 UltraはQuest 3と価格がほぼ同じで、SteamVRとPICO Connectの2層が加わる。PICO ConnectがOpenXRを直接扱う機能は実験的という二次情報があり、本期の前提にはしない。

## 本期に適さない選択肢

| 選択肢 | 理由 |
| --- | --- |
| Steam Frame | 国内は2026-09-15にKOMODOが発売、199,980円から（1TBは244,980円）。発売当日に256GBが売り切れたと報じられた。9/25時点の在庫は未確認。PC接続は付属の6GHz無線アダプタによるストリーミングが標準で、有線接続の可否は確認していない。予算・納期・圧縮の三点で本期に合わない |
| Valve Index（新規購入） | Valveは2025年11月に製造終了を表明。新規入手は不確実。ただし研究室に既存機があれば、SteamVR経由の借用候補にはなる |
| WMR機（HP Reverb G2など） | Microsoftが「Windows 11 24H2で削除」と告知。本機は25H2なので動かない。借用も不可 |
| Air Link（無線） | ルーターと電波状況が計測条件に入る。H2・H6の基準は有線Linkで取る |
| スタンドアロン（Android）版 | 計画はPC接続VR。現行経路のAlembicはAndroid単体で使わない（[20](Step_20_ja.md)） |

## 費用の目安（購入する場合）

| 構成 | 内訳 | 合計 |
| --- | --- | --- |
| 推奨 | Quest 3 512GB 102,300円（公式）＋Meta Quest Linkケーブル約5m 10,780円（ツクモ実売） | 約113,080円 |
| 次点 | Quest 3S 128GB 59,400円（公式）＋同ケーブル10,780円 | 約70,180円 |

Meta公式ストアでのLinkケーブル価格は、ページを取得できず未確認。他社製のUSB3 Type-Cケーブル（3m以上）でもよいが、価格は未確認で、Linkアプリのケーブルテストで帯域を確かめる必要がある。支払い・契約は利用者の明示承認を要する（AGENTS.md）。代理は注文・支払い・フォーム入力を行わない。

## フレーム時間予算への影響

新作業計画の性能予算は、90HzでGPU p95 ≤8.9ms、72Hzで≤11.1msとしている。どちらも1フレーム時間の約80%に当たる。

| 周波数 | 1フレーム | GPU p95の上限 | 位置づけ |
| --- | --- | --- | --- |
| 90Hz | 11.111ms | 8.889ms → **≤8.9ms** | 目標 |
| 72Hz | 13.889ms | 11.111ms → **≤11.1ms** | 退避。90Hzで未達のとき切り替えて記録する |
| 120Hz | 8.333ms | 6.667ms | 対象外 |

描画量の目安（パネル解像度で計算。実際の描画解像度はruntimeの推奨値とLinkの設定で決まり、H1で記録する）：

| 機種 | 両眼の画素数 | 1920×1080比 | 90Hzでの毎秒画素 | 72Hzでの毎秒画素 |
| --- | --- | --- | --- | --- |
| Quest 3 | 9,114,624 | 4.40倍 | 約820M | 約656M |
| Quest 3S | 7,034,880 | 3.39倍 | 約633M | 約507M |
| PICO 4 Ultra | 9,331,200 | 4.50倍 | 約840M | 約672M |

backlogのデスクトップ基準（1920×1080で平均30fps）は毎秒約62M画素なので、Quest 3の90Hzはその約13倍になる。計画上の内訳推定はGPU 2.5〜4ms＋Link約1ms、CPU約1.5ms、draw call 20未満だが、これは見積もりにすぎない。[20](Step_20_ja.md)ではGPU有効値が全24条件で0件だった。GPU時間は32で測り直すまで「未測定」として扱う。デスクトップ基準（RTX3060で30fps）とHMD予算（90Hz）は別々に測り、一方を他方の代わりにしない。

作画への影響：4×MSAAの両眼描画を前提に、藍線の外殻は世界寸法で線幅を決め、上下限を設ける。1画素未満の細線はLinkの圧縮で消えるおそれがあり、H6で確かめる。

## OpenXR interaction profileの提案

現状、[08](Step_08_ja.md)のProject Validationに「interaction profile未選択」の警告が残っている。機種が決まったら、32または34で次のとおり設定する。本番号ではUnityの設定を変更しない。

| 区分 | profile | 理由 |
| --- | --- | --- |
| 有効にする | Oculus Touch Controller Profile（`/interaction_profiles/oculus/touch_controller`） | OpenXR中核のprofileで拡張不要。Quest 3／3SのコントローラーをLinkで扱える。本作に必要なのはボタン数個だけ |
| 保留 | Meta Quest Touch Plus Controller Profile | `XR_META_touch_controller_plus`拡張が要る。Link runtimeでの対応は未確認。H1のログで拡張の有無を見てから判断する |
| 借用機に応じて | Valve Index／HTC Vive Controller Profile、Khronos Simple Controller Profile | 借用機がTouch系でない場合だけ有効にする |
| 使わない | Hand Interaction、Eye Gaze、Palm Pose、HP Reverb G2、Microsoft Motion Controller | 着座・静止船の鑑賞では不要。WMR系は本機で動かない |

操作の割り当て案（キーボード欄のキーは[09](Step_09_ja.md)のPC確認版の操作から取った。VR中の現行の動作は表の下の注意点を参照）：

| 操作 | コントローラー | キーボード | 注記 |
| --- | --- | --- | --- |
| 停止・再開 | 右A（`/input/a/click`） | Space | VR中の停止・再開は未実装。現行のSpaceはPC確認版で視点操作を止めるだけで、VR中は無効 |
| 座席視点へ戻す（アプリ側） | 右B（`/input/b/click`） | R | XR Originを座席の目の位置へ合わせ直す。この処理は未実装で、現行のVR中のRはTryRecenterを呼ぶだけ |
| runtimeの再センタリング | Metaボタン長押し（runtimeが予約） | — | アプリからは発行しない |
| 終了 | 割り当てない | Q | 装着者の誤操作を防ぐため操作者が行う |
| 移動・旋回 | 割り当てない | — | 頭部追跡を上書きしない |

既存コードの注意点（`Unity/Assets/GreatWave/Scripts/M0ViewController.cs`を読んで確認。本番号ではコードを変更しない）：

- Space（停止・再開）とEsc（停止）の処理は`if (!VrActive && !recordingCamera)`の中にあり、VR中は働かない。PC確認版でも止まるのは視点操作で、波の再生ではない。
- VR中のRは`XRInputSubsystem.TryRecenter()`を呼ぶだけである。`ResetView()`はVR中は何もせずに戻るので、アプリ側の座席リセットは実装されていない。
- コントローラーのボタン入力は読んでいない。`M0XRSetup.cs`が設定する入力は頭部の位置・回転・追跡状態だけである。
- 導入済みOpenXRパッケージの`OpenXRSpaceSettings.cs`には、再センタリングのイベントはruntimeが送るもので、アプリ側のAPIは発行しないとある。TryRecenterがLinkで効くかは未確認。

したがって、上の右A・右B・Spaceの割り当ては提案である。VR中の停止・再開、アプリ側の座席リセット、コントローラー入力は、H7より前に32または34で実装する。H7ではruntime側の再センタリングとアプリ側の座席リセットを分けて試す。

## 利用者本人だけが行う操作

代理はこれらを代行しない。購入・アカウント・システム設定・ソフトウェア導入に当たるため。

| 順 | 操作 | 時期 | 注記 |
| --- | --- | --- | --- |
| 1 | 借用か購入か、機種と周波数方針を決めて伝える（新作業計画のD5） | 9/28、最遅9/29 | 購入の承認と支払いは本人 |
| 2 | 研究室へ借用を相談する（機種・期間・Linkケーブル等の付属品） | 9/28まで | 借用なら機種名・返却日を知らせる |
| 3 | Metaアカウントの作成またはログイン、スマートフォンのMeta Horizonアプリで初回ペアリング | 到着日 | 初回ペアリングと設定にアプリが必要（Metaヘルプ） |
| 4 | この本機とヘッドセットからMetaのサービスへ接続できるか確かめる | 到着前後 | 研究室ネットワークのプロキシ・フィルタを含む |
| 5 | Meta Horizon Link PCアプリを公式から入手して導入し、同じアカウントでログイン | 到着日 | 管理者権限が要る |
| 6 | Linkアプリの Settings > General > OpenXR Runtime で「Set Meta Horizon Link as active」を押す（日本語表示では名称が異なりうる） | 到着日 | 管理者権限。システム全体のOpenXR設定を書き換えるため本人が行う |
| 7 | Linkアプリの Devices > Graphics Preferences で90Hz（退避72Hz）と描画解像度を選ぶ | 冒頭試験 | 永続設定。72Hzを選べるかは実機で確認。Oculus Debug ToolでASW等を変える場合も本人の操作または明示承認 |
| 8 | 初回装着：充電、IPDとストラップ調整、着座用の境界設定、コントローラー接続、Link接続、ケーブルテスト | 到着日 | 初回は約2時間の見込み（計画） |
| 9 | 各回の装着と申告（冒頭・第1回・第2回） | 到着後 | 各回約1時間。不快なら即中止。快適性の判定は本人 |

PICO 4 Ultraを選んだ場合は、上の3・5・6の代わりに、PICOアカウント、PICO Connect、SteamとSteamVRの導入、SteamVRをOpenXR runtimeにする設定が要る。いずれも本人の操作である。

## H1〜H7確認表（[05](Step_05_ja.md)「HMD入手後の必須項目」との対応）

各回の冒頭で「対象環境」を固定して記録する：HMD機種、ヘッドセットのファームウェア、Linkアプリの版、OpenXR runtimeの名前と版（Unityの起動ログ）、周波数、runtimeが推奨する片眼描画解像度、Linkの帯域・エンコード設定、ケーブル、GPUドライバー、実行ファイルのSHA-256。

| H | 確認内容 | 05の項目 | 実施回 | 方法と記録 | 合格条件（引き下げない） |
| --- | --- | --- | --- | --- | --- |
| H1 | 実runtimeでOpenXRセッションが始まり、SPIで両眼に出る | 対象環境、両眼と追跡 | 冒頭・第1回 | `--vr`起動ログ（runtime名、view数、推奨解像度、周波数、選ばれたprofile）、PC側ミラー画像 | セッション開始、両眼に同じ形、頭の回転と位置移動が反映される。PC確認版へ戻っていない |
| H2 | フレーム時間 | 性能 | 冒頭（概値）・第2回（p95／p99） | FrameTimingManagerのCPU／GPU、Oculus Debug ToolのPerformance HUDにあるアプリGPU時間と欠落フレーム、ASWの状態 | 90HzでGPU p95 ≤8.9ms。未達なら72Hzで≤11.1msとし、その旨を記録。最大スパイクと再投影の状態を明記 |
| H3 | 藍線・爪先・飛沫が両眼で一致し、頭を動かしても点滅しない | 両眼と追跡 | 第1回 | 同時刻の両眼ミラーで線の画素数を比べる（32のMock両眼画像と同じ尺度）、装着者の目視 | 片眼だけの欠け0件、左右の線画素数の差10%未満、点滅の申告なし |
| H4 | 船上から見た波の高さ・厚み・内側空間（V3） | 実寸と着座 | 冒頭（座席の尺度）・第1回 | 着座で1m基準、目の高さ、船縁との距離を確認し、波の見え方を口頭で記録 | 1m基準が1mに見える（本人判断）。目の高さを記録。V3の各項目を確認 |
| H5 | 波の先端（唇部）が頭上を越えるときの快適性 | 快適性 | 第1回 | 着座で大波の区間を通して見る。頭部追跡を上書きしない | 本人が無理なく見続けられる。不快の申告は即中止して記録 |
| H6 | Linkの圧縮が細線と白点に与える影響 | 対象環境（接続方式）、性能 | 第2回 | Linkの帯域・エンコード設定を記録し、PC側ミラーとレンズ越しの見え方を本人が比べる | 細線の途切れ・白点のにじみが作品判断を妨げない（本人判定）。問題があれば線幅の下限引き上げや帯状メッシュへの置き換えを検討する（新作業計画のR9） |
| H7 | 再センタリング・停止・復帰 | 操作 | 冒頭（再センタリング）・第2回 | runtime側の再センタリング、アプリ側の座席リセット、停止と再開を実機で試す。アプリ側の座席リセットとVR中の停止・再開は、32または34で実装してから試す | 全操作が期待どおりに働き、頭部追跡を奪わない |

レンズ越しの像は直接撮影できない。PC側ミラーの画像・動画は「PC側ミラー」と明記し、HMD内の見え方の証拠とは呼ばない。デスクトップのフレーム数、マウス操作、Mock Runtimeの両眼画像はH1〜H7の代わりにしない（05の方針）。

## 判断期限と結果

| 状況 | 日付 | 結果 |
| --- | --- | --- |
| 決定 | 9/28（月）、最遅9/29（火） | 理想の到着は10/2 |
| 10/9（金）までに到着 | 冒頭は到着後2日以内、第1回は新作業計画のCP4（10/15）かCP5（10/20）、第2回は統合RC（43、10/21〜10/23） | H1〜H7を2回の枠で実施できる |
| 10/10〜10/20に到着 | 到着後に補測 | 確認は1回に縮める。第2回の項目（H2のp95／p99、H6、H7）は残り日程でできる範囲とし、できなければ未検証 |
| 9/29までに決定なし | — | D5の既定「購入しない」（既定値・利用者未回答）で進める。後から決めた場合も確認は1回に縮める（新作業計画のR8） |
| 10/20までにHMDなし | CP5 | VR項目はすべて「未検証」。合格条件は下げない。Mock Runtimeの両眼画像は事前確認であり、合格の代わりにしない |

配送日数は確認していない。注文時に表示される到着予定が10/9を過ぎる場合は、店頭購入か借用を検討してほしい。

## この番号の証拠と未検証事項

- 成果物は本文書のみ。HMDがなく購入前の比較なので、静止画・動画・metrics.json・run.jsonは作らない。
- 本機の値は読み取り専用の照会（`Get-CimInstance`、レジストリの存在確認）で得た。OpenXR runtime、Unity設定、グローバル設定は変更していない。
- 代理はWeb閲覧だけを行い、購入・注文・アカウント作成・フォーム送信・ソフトウェアのダウンロードはしていない。旧試作は参照していない。
- 未実装（32または34で対応）：VR中の停止・再開、アプリ側の座席リセット、コントローラー入力。
- 未確認：各店の在庫と配送日数、公式ストアのLinkケーブル価格、Linkで72Hzを選べるか、Link runtimeの`XR_META_touch_controller_plus`対応、TryRecenterの挙動、PICO 4 Ultraの視野、Steam Frameの現在の在庫、本機背面のType-C端子。

## 出典（すべて2026-09-25取得）

- Meta：[Meta Quest 3（日本）](https://www.meta.com/jp/quest/quest-3/)（512GB 102,300円）、[機種比較](https://www.meta.com/quest/compare/)（解像度・周波数・レンズ・視野）、[Linkの要件](https://www.meta.com/help/quest/articles/headsets-and-accessories/oculus-link/requirements-quest-link/)（対応GPU、3m以上のケーブル推奨）、[Quest 3の設定方法](https://www.meta.com/help/quest/10004693912934783/)、[Use Link for App Development](https://developers.meta.com/horizon/documentation/unity/unity-link/)（OpenXR Runtimeの設定手順）
- 価格改定：[MoguLive：Meta Quest値上げ（2026-04-17）](https://www.moguravr.com/meta-quest-3-price-increase-2026/)（4/19から3S 59,400円／77,000円、アクセサリーは据え置き）、[MoguLive：PICO 4 Ultra値上げ（2026-04-10）](https://www.moguravr.com/pico-4-ultra-price-revision-2026/)（5/1から104,900円）。PICO公式の[価格改定のお知らせ](https://www.picoxr.com/jp/about/newsroom/pricing)は本文を取得できなかった
- 実売：[価格.com Quest 3 512GB](https://kakaku.com/item/K0001572648/)、[価格.com Quest 3S 128GB](https://kakaku.com/item/K0001655502/)、[価格.com PICO 4 Ultra](https://kakaku.com/item/K0001653727/)、[ツクモ Meta Quest Linkケーブル](https://shop.tsukumo.co.jp/goods/0815820020417/)
- PICO：[PICO 4 Ultra製品ページ](https://www.picoxr.com/global/products/pico4-ultra)（2160×2160、最大90Hz）、[VR Expert：SteamVRでの使用](https://knowledge.vr-expert.com/kb/how-to-play-steamvr-games-with-the-pico-4/)、[DCS Forum：PICO ConnectのOpenXR実験機能](https://forum.dcs.world/topic/372463-pico-headsets-pico-connect-built-in-experimental-openxr-runtime/)（二次情報）
- Link周波数：[Road to VR（2024-03-07）](https://roadtovr.com/meta-quest-link-update-120hz-battery/)（Quest 3のLinkで120Hz、Graphics Preferencesで選択）
- Steam Frame：[TechnoEdge（2026-09-15）](https://www.techno-edge.net/article/2026/09/15/5499.html)、[Dream Seed（2026-09-15）](https://dreamseed.blog/post-204923/)
- Valve Index：[PC Guide（2025-11-13）](https://www.pcguide.com/news/with-steam-frame-on-the-way-valve-has-discontinued-its-index-vr-headset/)
- WMR：[Microsoft Learn：Deprecated features](https://learn.microsoft.com/en-us/windows/whats-new/deprecated-features)、[UploadVR（2024-10-01）](https://www.uploadvr.com/windows-11-24h2-kills-windows-mr-support/)
- Unity：[OpenXR 1.16 Oculus Touch Controller Profile](https://docs.unity3d.com/Packages/com.unity.xr.openxr@1.16/manual/features/oculustouchcontrollerprofile.html)、[Project configuration（Render Mode）](https://docs.unity3d.com/Packages/com.unity.xr.openxr@1.16/manual/project-configuration.html)。導入済みパッケージの`Documentation~`と`Runtime/OpenXRSpaceSettings.cs`も読んだ
