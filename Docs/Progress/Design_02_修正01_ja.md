# 設計02修正01：PS VR2をPCで使う準備（SteamVR）と、HMD実機確認の割り当て

日付：2026-09-26／結果：利用者の手元にあるPS VR2とPCアダプター（未導入）を前提に、要件・PCで使える機能・周波数・OpenXR runtimeを公式資料で確かめた。本機は読み取り専用で照会した。そのうえで、利用者が行う導入手順と、H1〜H7の確認表をPS VR2＋SteamVR向けに書き直し、H1〜H7を設計書の番号へ割り当てた。HMD実機の結果はまだない。代理はソフトの導入、設定の変更、購入、フォームの送信をしていない。

この「設計02修正01」は、[制作設計書](../Design/GreatWave_VR_Production_Design_ja.md)の設計02（PC/GPU/VRAMとHMDの有無を調べる）の修正1回目である。[02の記録](Step_02_ja.md)では、HMDは「利用者回答：現在なし」、機種・周波数・片眼解像度は「未定」だった。HMDの候補比較は美術優先25（[25の記録](Step_25_ja.md)：HMDの選定、購入提案、OpenXRの前提）で行った。どちらも書き換えず、このファイルに分けた。この文書は初め、美術優先25の修正（「25修正01」）として書いた。その後、数字だけの題名はCP2主線の5件で終え、以後は設計書の番号で書き分けることになったので、設計書の番号に付け替えた。旧設計書の25（収支・反射の物理検証、取消済み）とも別物である。

利用者の発言（Q8、2026-09-26、Claude Codeの会話、原文のまま）：

> HMD靠借，我现在自己有一个psvr2

質問ダイアログでの利用者の選択（Q8、原文のまま）：PSVR2 の PC アダプター「有适配器，但还没装过」

これで、美術優先25の候補比較（借用・Quest 3・Quest 3S・PICO 4 Ultra）とD5の期限（9/28、最遅9/29）は要らなくなった。ただし、手元のPS VR2が利用者のものか、借りたものかは、この発言からは決まらない（美術優先25のD5の選択肢は「借用」と「購入」だった）。そこでこの文書では「利用者の手元にあるPS VR2」と書く。借りたものなら、10/29まで使えるか、この本機でファームウェアの更新とPCとのペアリングをしてよいかも確かめる（下の準備0-0）。D5の結果は、進行役が制作指示のコミットで記録する。

同じQ8で、導師の指示により、進行の順番は制作設計書の番号26→50に戻す方針が示された。本書が定めるのはHMDの機器側の前提と導入手順だけである。H1〜H7をどの番号で行うかは、段階9までの実行計画（`Docs/Design/Stage9_Plan_2026-09-26_ja.md`、第3.2節）の割り当てに従う。末尾の「設計書の番号との対応」は、その割り当てと同じにした。

- 時間の上限：0.5日（進行役の指示）。実績は約1時間（名前の付け替えと割り当ての統一を除く）。Web閲覧と読み取り専用の照会、文書作業だけ。
- 修正回数：設計02の修正1回目。HMDが利用者の手元のPS VR2になり、02の「HMD未定」と美術優先25の前提が変わったため。
- 対応するバックログ項目：直接の項目はない。受入の根拠は[設計05](Step_05_ja.md)の「HMD入手後の必須項目」。
- 証拠の種類：公式資料（Sony、Steam、Khronos）と二次情報のWeb閲覧、本機の読み取り専用照会（`Get-CimInstance`、`Get-PnpDevice`、`Get-PnpDeviceProperty`、レジストリ・フォルダー・環境変数の存在確認）。機器の導入前なので、静止画・動画・metrics.json・run.jsonは作らない。

## 要点

1. **機材はほぼ揃っており、足りない見込みがあるのはDisplayPortケーブルだけ。** 必要なのはPS VR2本体、Senseコントローラー2本、PCアダプター（ACアダプターと電源コードが付属）、**DisplayPort 1.4対応ケーブル（別売り）**。DPケーブルが手元にあるかを確かめてほしい。手元のPS VR2が利用者のものか借りたものか（借りたものなら、10/29まで使えるか、この本機で更新とペアリングをしてよいか）も知らせてほしい。
2. **本機は公式の要件を満たす見込み。** GPUはRTX 3080（公式の推奨はRTX 3060以上）で、DisplayPort出力がある。内蔵Bluetoothは5.2相当（要件は4.0以上）、OSはWindows 11の64ビット版。背面のRTX 3080に空いたDP端子があるかは目視で確かめる（未確認）。
3. **OpenXR runtimeはSteamVRになる。** PS VR2のPC用ドライバーはSteamVRの上で動くので、UnityのOpenXRはSteamVRのOpenXR runtimeを通る。本機にSteamは入っているが、SteamVRとPlayStation VR2アプリは未導入で、OpenXRのactive runtimeも登録されていない。
4. **周波数は90Hz（目標）と120Hz（記録のみ）の2つ。PS VR2には72Hzがない。** 目標のGPU p95 ≤8.9ms（90Hz）は変えない。美術優先25と美術優先計画にあった「退避72Hz（≤11.1ms）」は使えないので、90Hzで届かないときはSteamVRの描画解像度を下げ、その値を記録する。
5. **PCでは視線追跡・HDR・ヘッドセットの振動・アダプティブトリガー・振動以外の触覚が使えない（Sony公式）。** 本作はどれにも頼っていない。
6. **interaction profileは、Oculus Touch Controller Profileを第一候補のまま残す。** ただし理由は変わる。SteamVRはSenseコントローラーを、アプリが持つprofileのうち最も近いTouchへ割り当てる、という報告がある（二次情報）。実際の割り当てはH1で記録する。

## 公式資料で確かめた要件（2026-09-26取得）

| 項目 | 公式の値 | 本機 |
| --- | --- | --- |
| OS | Windows 10／11（64ビット） | Windows 11 Home 中国語版 25H2（build 26200）、64ビット |
| CPU | 最低：Intel Core i5-7600／AMD Ryzen 3 3100（AMDはZen2以降） | i7-12700K（[設計02](Step_02_ja.md)） |
| メモリ | 8GB以上 | 約64GB（[設計02](Step_02_ja.md)） |
| GPU | 最低：GeForce GTX 1650以降（NVIDIAはTuring以降）／Radeon RX 5500XT以降。推奨：GeForce RTX 3060以降／Radeon RX 6600XT以降 | GeForce RTX 3080（HPのOEM品、ドライバー595.95） |
| 映像 | DisplayPort 1.4。PCのDP端子（標準またはMini）へ直接つなぐ。USB Type-CのDisplayPort出力は非対応 | GPUにDP出力あり（下の照会）。空き端子の数は未確認 |
| USB | USB 3.0 Type-Aへ直結。延長ケーブルやハブを通すと誤動作のおそれ | Intel USB 3.20 xHCI（[美術優先25](Step_25_ja.md)）。背面の端子の数は未確認 |
| Bluetooth | 4.0以降。動かないアダプターもある | 内蔵のIntel製、LMP版11（5.2相当） |
| 電源 | 付属のACアダプターをPCアダプターのDC INへつなぐ | コンセントが1口要る |
| ソフト | Steam、SteamVR、PlayStation VR2アプリ（Steamで無料。設定が済んでもアプリは削除しない） | Steamのみ導入済み |
| ヘッドセット | 有機EL、片眼2000×2040、90Hz／120Hz、視野約110°、レンズ間隔を調整できる | — |
| 容量 | PlayStation VR2アプリ 700MB。SteamVRの容量は確かめていない | 空きはC: 約4.8GB、D: 約333GB、E: 約10GB。**D:へ入れる** |

Bluetoothについて、Sonyは外付けアダプター4機種を試験している（2024-07-20の試験。動作は保証しない）：TP-Link UB500、Buffalo BSBT5D205BK、ASUS USB-BT500、IO-DATA USB-BT50LE。一覧に内蔵品は載っていない。Sonyの助言は次のとおり。

- メーカーが配布していれば、最新のBluetoothドライバーを入れる。
- 外付けアダプターは、USB 3.0端子からできるだけ離れたUSB 2.0端子へ挿す。必要ならUSB 2.0の延長ケーブルで見通しのよい場所へ出す。
- 外付けを使うときは、デバイスマネージャーで内蔵のBluetoothを無効にする。
- ほかのBluetooth機器を切る。Wi-Fiは5GHz帯を使う。コントローラーは満充電にし、アダプターとの間を遮らない。

## 本機の照会（読み取り専用、2026-09-26）

| 項目 | 結果 | 方法 |
| --- | --- | --- |
| 機種 | OMEN by HP 45L Gaming Desktop GT22-0xxx | `Win32_ComputerSystem` |
| GPU | NVIDIA GeForce RTX 3080。PCIのサブシステムは103C:88D7（HPのOEM品） | `Win32_VideoController`のPNPDeviceID |
| DP出力 | モニター2台のうち、LGの1台が外付けDisplayPort（VideoOutputTechnology＝10）、Sonyの1台がHDMI（＝5）でつながっている。GPUにDP端子があることは確か。端子の総数はOSからは読めない。販売店が載せる同系機（型番違い）の仕様は「3x DisplayPort, HDMI」（二次情報） | `WmiMonitorConnectionParams`、`WmiMonitorID` |
| Bluetooth | Intel Wireless Bluetooth（USB VID_8087・PID_0026）、状態OK、ドライバー23.40.0.2（2024-02-22）。ラジオのプロパティ`{A92F26CA-EDA7-4B1D-9DB2-27B68AA5A2EB} 4`（LMP版と読んだ）と同6（HCI版）がともに11で、Bluetooth 5.2に当たる。LEの列挙子もある。オーディオ機器が複数ペアリング済み（名前は記録しない） | `Get-PnpDevice -Class Bluetooth`、`Get-PnpDeviceProperty` |
| Steam | 導入済み（`D:\Program Files (x86)\Steam`）。表示言語は簡体字中国語。ライブラリはD:・E:・G: | `HKCU\Software\Valve\Steam`、`HKLM\SOFTWARE\WOW6432Node\Valve\Steam`、`libraryfolders.vdf` |
| SteamVR | 未導入（3つのライブラリに`appmanifest_250820.acf`も`common\SteamVR`もない）。起動した形跡もない（`%LOCALAPPDATA%\openvr`がない） | フォルダーの存在確認 |
| PlayStation VR2アプリ | 未導入（`appmanifest_2580190.acf`がない。2580190はSteamストアのアプリ番号） | 同上 |
| OpenXR active runtime | `HKLM\SOFTWARE\Khronos\OpenXR\1`がない（未登録）。HKCUとWOW6432Nodeにもない。環境変数`XR_RUNTIME_JSON`はユーザー・システムとも未設定 | レジストリと環境変数の読み取り |
| Unity側 | OpenXR 1.16.1、Standaloneは`m_renderMode: 1`（Single Pass Instanced）、interaction profileはすべて無効。導入済みパッケージのinteraction profileは14種（ほかに`Tests/Runtime`の試験用`MockInteractionFeature`が1つ）で、PS VR2 Sense用はない | `OpenXRPackageSettings.asset`、`Library/PackageCache/com.unity.xr.openxr@*/Runtime/Features/Interactions` |

どの照会も読むだけで、設定・レジストリ・ドライバーは変えていない。

## PCで使える機能と使えない機能

出典はPlayStation.Blog（2024-06-03）とUploadVRのレビュー（2024-08-07、二次情報）。

| 機能 | PC | 本作への影響 |
| --- | --- | --- |
| 片眼2000×2040、視野約110°、指の接触検出、シースルー表示 | 使える | — |
| 90Hz／120Hz | SteamVRで選べる（UploadVR） | 90Hzで測る。120Hzは記録のみ |
| 視線追跡（視線を使うfoveated rendering） | 使えない | 使わない。Eye Gaze profileは有効にしない |
| 視線なしのfoveated rendering、3Dオーディオ | 対応するゲームで使える | 本作では使わない |
| HDR | 使えない | 色面の判定はSDRの出力で行う |
| ヘッドセットの振動 | 使えない | 使わない |
| アダプティブトリガー（トリガーの抵抗） | 使えない | 使わない |
| 触覚 | 振動（rumble）以外は使えない | 今のところ振動も使わない |
| Tempest 3Dオーディオ | SteamVRの音響に置き換わる | 設計49（音）のときに考える |

非公式のドライバー改造（視線追跡を使えるようにするものなど）は使わない。

## 周波数と性能予算（美術優先25の表を置き換える）

| 周波数 | 1フレーム | GPU p95の上限（1フレームの約80%） | 位置づけ |
| --- | --- | --- | --- |
| 90Hz | 11.111ms | **≤8.9ms** | 目標（変えない） |
| 120Hz | 8.333ms | ≤6.7ms | 記録のみ |
| 72Hz | — | — | PS VR2にない。美術優先25と美術優先計画の「退避72Hz」は使えない |

90Hzで届かないときの扱い：

1. SteamVRのアプリ別の描画解像度を下げて測り直し、その％と片眼の画素数を記録する。
2. それでも届かなければ、不合格のまま記録し、設計書の段階10（51〜55）で扱う。
3. 再投影（SteamVRのMotion Smoothingなど）で見かけの90Hzを保っても、合格とはしない。再投影の回数は必ず書く。

描画量の目安（パネルの画素で計算。実際の描画解像度はSteamVRの推奨値と描画解像度の設定で決まり、H1で記録する）：

| 機種 | 片眼 | 両眼の画素数 | 1920×1080比 | 90Hzでの毎秒画素 | 120Hzでの毎秒画素 |
| --- | --- | --- | --- | --- | --- |
| PS VR2 | 2000×2040 | 8,160,000 | 3.94倍 | 約734M | 約979M |
| 参考：美術優先32の代理（Quest 3のパネル） | 2064×2208 | 9,114,624 | 4.40倍 | 約820M | — |

PS VR2のパネルは美術優先32の代理より約10%画素が少ない。ただし、SteamVRが推奨する描画解像度はレンズの歪みを補正するぶんパネルより大きくなることがある（PS VR2での値は未確認）。H1でUnityのログから推奨値を読み、2064×2208を超えていれば、美術優先32の代理をその寸法で測り直す（数十秒で済む）。美術優先32の代理のGPU p95は最大1.152msだった。

## OpenXR runtimeとinteraction profile（美術優先25の表を改訂）

**runtime**：SteamVRのOpenXR runtimeを使う。利用者がSteamVRの設定で「SteamVRをOpenXR runtimeにする」操作を行う（管理者権限が要る。下の手順8）。Windowsでは、active runtimeは`HKLM\SOFTWARE\Khronos\OpenXR\1\ActiveRuntime`に記録される（Khronosのローダー仕様）。設定後に代理がこのキーを読み、SteamVRを指しているかだけ確かめる。

**Unity側**：runtimeが変わってもプロジェクトの設定は変えずに済む見込み（OpenXR 1.16.1、Windows Standalone、SPI、Direct3D11）。ただしSteamVRのOpenXRでD3D11・SPIが問題なく動くかは、H1で確かめるまで未確認とする。美術優先32のMock測定は起動スクリプトの中だけで`XR_RUNTIME_JSON`をMockへ向けていた。実機では`XR_RUNTIME_JSON`を設定せず、システムのactive runtime（SteamVR）を使う。

| 区分 | profile | 理由 |
| --- | --- | --- |
| 有効にする（第一候補） | Oculus Touch Controller Profile（`/interaction_profiles/oculus/touch_controller`） | Unity OpenXR 1.16.1にPS VR2 Sense用のprofileはない（導入済みパッケージの一覧で確認）。OpenXRにもSense用の拡張は見当たらないという報告がある。SteamVRはSenseをTouchへ「最も近い型」として割り当てる、という報告が2件ある（Unityフォーラム2024-10、REFrameworkのissue 2024-09。どちらも二次情報） |
| 予備（1つずつ試す） | Valve Index Controller Profile → Khronos Simple Controller Profile | Touchで入力が来ないときだけ使う。同時に有効にするとSteamVRがどれを選ぶかが変わりうるので、一度に1つにする |
| 使わない | Meta Quest Touch Plus／Pro（Metaの拡張が要り、SteamVRでの対応は未確認）、Eye Gaze（PCでは視線追跡なし）、Hand Interaction、Palm Pose、HTC Vive、HP Reverb G2、Microsoft Motion Controller、D-Pad | 着座の鑑賞に要らないか、PS VR2では使えない |

profileを有効にする作業はこの番号では行わない。設計08の実機保留分（「機器固有profileと実機入力はHMD入手後」）に当たり、導入の直後の`設計08修正02：`で行う（段階9までの実行計画の第3.2節）。

操作の割り当ては美術優先25の案を引き継ぐ（右の第一ボタン`/input/a/click`＝停止・再開、右の第二ボタン`/input/b/click`＝座席視点へ戻す、終了はキーボードのQで操作者が行う、移動・旋回は割り当てない）。ただし、SenseのどのボタンがTouchのA・B・X・Yやmenuに当たるかは、公式資料では確かめられなかった。H1で、Input Systemに作られたコントローラーの型と、各ボタンの実際の対応を記録する。SteamVRの「コントローラーのバインド」画面で確かめてもよい。PSボタンはシステム側の操作に使われるものとして、アプリには割り当てない（挙動はH7で確かめる）。

美術優先25に書いた既存コードの注意点は変わらない。VR中の停止・再開、アプリ側の座席リセット、コントローラー入力はまだ実装していない。XR Originの追跡原点はDevice（着座）、CameraYOffsetは1.2m（`M0XRSetup.cs`）。SteamVRでは着座の原点が「着座位置のリセット」で決まるので、H4とH7の前に合わせる。`XRInputSubsystem.TryRecenter()`がSteamVRで効くかは未確認。

## 利用者が行う導入手順

ソフトの導入、Bluetoothのペアリング、OpenXR runtimeの切り替えは、システムの設定を書き換える操作なので本人が行う。代理は行わない。Steamの表示言語が簡体字中国語なので、画面の名前は下の日本語・英語の表記と違うことがある。画面の指示とSonyの手順が違うときは、画面の指示を優先してほしい。

**準備**

| 順 | 操作 | 確かめること |
| --- | --- | --- |
| 0-0 | 手元のPS VR2が自分のものか、借りたものかを知らせる。借りたものなら、10/29まで使えるか、この本機でファームウェアを更新し、PCとペアリングしてよいかを確かめる | 借用で期限や操作に制約があれば、導入の前に知らせてほしい |
| 0-1 | DisplayPort 1.4対応のケーブルがあるか確かめる | なければ入手が要る（購入は本人の判断。DP 1.4〔HBR3〕対応と書かれたもの。価格は調べていない） |
| 0-2 | PC背面で、RTX 3080の空いたDP端子を探す | マザーボード側の映像端子は使わない。LGのモニターが1つ使っている。空きがなければ知らせてほしい |
| 0-3 | 背面のUSB 3.0 Type-A端子を1つ空ける | ハブや延長ケーブルを通さない口 |
| 0-4 | Senseコントローラー2本を満充電にする | — |
| 0-5 | 部屋の明かりをつけ、直射日光が入らないようにカーテンを閉める | 着座で使う椅子の周りを片付ける |

**接続と導入**

| 順 | 操作 | 確かめること |
| --- | --- | --- |
| 1 | PCアダプターをUSB 3.0 Type-Aへつなぐ。DPケーブルでアダプターとGPUのDP端子をつなぐ。電源コードをACアダプターへ、ACアダプターをアダプターのDC INへつなぎ、コンセントへ挿す | アダプターの表示灯が赤で点灯する |
| 2 | ヘッドセットのUSB Type-Cケーブルをアダプターへつなぎ、ヘッドセットの電源ボタンを押す | アダプターとヘッドセットの表示灯が白で点灯する |
| 3 | Steamを更新して起動し、ストアからSteamVRとPlayStation VR2アプリ（どちらも無料）を導入する | **インストール先はD:（空き約333GB）を選ぶ。** C:は約4.8GBしか空いていない |
| 4 | PlayStation VR2アプリを起動し、画面の指示に従ってコントローラー・PCアダプター・ヘッドセットを設定する | ファームウェアの更新を求められたら従い、終わるまでケーブルを抜かない |
| 5 | Windowsの設定でBluetoothをオンにする。左はPSボタンとクリエイトボタン、右はPSボタンとオプションボタンを同時に長押しし、表示灯が点滅したら、Windowsの「デバイスの追加」→Bluetoothで1本ずつペアリングする | 2本とも「PlayStation VR2 Sense Controller」として入力デバイスに並ぶ。ゲームコントローラーとして登録されたら、解除してやり直すとよいという利用者報告がある。VR中はBluetoothのヘッドホン類を切る |
| 6 | ヘッドセットをかぶってヘッドバンドを合わせ、レンズ調整ダイヤルで目をレンズの中心に合わせる。ヘッドセットのカメラで部屋をスキャンしてプレイエリアを決める | 本作は着座で使う。画面に着座の選択肢があれば選ぶ |
| 7 | SteamVRを起動する | ヘッドセットとコントローラー2本が認識されている |
| 8 | SteamVRの設定（デスクトップの画面の左上のメニュー→設定）で詳細設定を表示し、「OpenXR」の項目で「Set SteamVR as OpenXR Runtime」を押す。そのあとSteamVRを再起動する | 管理者権限を求められる。システム全体のOpenXR設定が変わる |
| 9 | SteamVRの映像（Video）設定で、リフレッシュレートを90Hzにする。描画解像度は、最初は既定（自動）のままでよい | 表示された描画解像度の％と画素数をメモする |

**最初の試験**

| 順 | 操作 | 確かめること |
| --- | --- | --- |
| 10 | SteamVRのホーム（または既定の環境）で、座ったまま5分ほど見回す | 頭の回転と移動についてくる。両手のコントローラーが見える。映像が止まったり欠けたりしない。気分が悪くなったらすぐ外す |
| 11 | 終わったら代理へ知らせる | SteamVRとPlayStation VR2アプリの版、ファームウェア更新の有無、選んだ周波数、描画解像度（％と画素数）、困ったこと。画面のスクリーンショットがあればそれも |

## 導入後に代理が行う確認（読み取り専用）

- `HKLM\SOFTWARE\Khronos\OpenXR\1\ActiveRuntime`が、SteamVRのフォルダーにあるruntimeのJSON（`steamxr_win64.json`と見込む）を指しているか。
- SteamVRとPlayStation VR2アプリの導入先と、`appmanifest`に書かれたbuildid。
- どれも読むだけで、何も変更しない。

## H1〜H7確認表（PS VR2＋SteamVR版。[設計05](Step_05_ja.md)「HMD入手後の必須項目」との対応）

各回の冒頭で「対象環境」を固定して記録する：HMD（PS VR2、本体の型番）、ヘッドセット・PCアダプター・コントローラーのファームウェア（PlayStation VR2アプリの表示）、PlayStation VR2アプリの版、SteamVRの版、OpenXR runtimeの名前と版（Unityの起動ログ）、周波数、SteamVRの描画解像度（全体とアプリ別の％）とruntimeが推奨する片眼の解像度、再投影（Motion Smoothing）の設定、DPケーブル、USBの口、Bluetooth（内蔵か外付けか）、GPUドライバー、実行ファイルのSHA-256。

| H | 確認内容 | 設計05の項目 | 方法と記録 | 合格条件（引き下げない） |
| --- | --- | --- | --- | --- |
| H1 | SteamVRのOpenXRでセッションが始まり、SPIで両眼に出る | 対象環境、両眼と追跡 | `--vr`起動ログ（runtimeの名前と版、view数、推奨解像度、周波数）。Input Systemに作られた左右のコントローラーの型（＝選ばれたprofile）と、各ボタンの対応。美術優先32と同じ方法で左右の眼のテクスチャを複写する | セッションが始まり、両眼に同じ形が出る。頭の回転と位置移動が反映される。PC確認版へ戻っていない。コントローラーの型とボタンの対応を記録済み |
| H2 | フレーム時間 | 性能 | FrameTimingManagerのCPU／GPU（SteamVRのXR経路で有効値が出るかも記録する。Mockでは0件だった）。SteamVRのフレームタイミング表示（設定の開発者向けの項目。名前は版で違う）と、その保存機能（Epicの文書では`VRFrames.csv`をSteamの`logs`へ保存。本機なら`D:\Program Files (x86)\Steam\logs`）。再投影の回数。測定中の再投影の設定は、利用者がSteamVRのアプリ別設定で切り替えて記録する | 90HzでGPU p95 ≤8.9ms。72Hzの退避はない。未達なら描画解像度を下げた値を別に記録する。最大スパイクと再投影の回数を明記する |
| H3 | 藍線・爪先・飛沫が両眼で一致し、頭を動かしても点滅しない | 両眼と追跡 | 同じ時刻の左右の眼のテクスチャで線の画素数を比べる（美術優先32の尺度）。装着者の目視 | 片眼だけの欠け0件、左右の線の画素数の差10%未満、点滅の申告なし |
| H4 | 船上から見た波の高さ・厚み・内側空間（V3）と実寸 | 実寸と着座 | 先にSteamVRの着座位置を合わせる。座席は美術優先27修正01の右船（座席 v1）。1m基準、目の高さ、船縁との距離を確かめ、見え方を口頭で記録する | 1m基準が1mに見える（本人の判断）。目の高さを記録。V3の各項目を確認 |
| H5 | 波の先端（唇）が頭上を越えるときの快適性 | 快適性 | 着座で大波の区間を通して見る。頭部追跡を上書きしない | 本人が無理なく見続けられる。不快の申告があれば即中止して記録 |
| H6（読み替え） | 細線と白点の見え方 | 対象環境、性能 | PS VR2はDisplayPortで映像を送るので、Linkの動画圧縮の確認は要らなくなった。代わりに、SteamVRの描画解像度（自動と100%など）とレンズ越しの見え方が細線・白点に与える影響を、本人がPC側ミラーとレンズ越しで比べる。DP経路に圧縮（DSC）があるかは未確認 | 細線の途切れや白点のにじみが作品の判断を妨げない（本人の判定）。問題があれば線幅の下限を上げるか帯状のメッシュに替える（計画のR9） |
| H7 | 再センタリング・停止・復帰 | 操作 | runtime側（SteamVRのダッシュボードの視点リセット、着座位置のリセット）、アプリ側の座席リセット、VR中の停止・再開、PSボタンの挙動を試す。アプリ側の2つは実装してから試す | すべての操作が期待どおりに働き、頭部追跡を奪わない |

レンズ越しの像は直接撮影できない。SteamVRのミラー画面やUnityの眼のテクスチャは「PC側ミラー」と明記し、HMD内の見え方の証拠とは呼ばない。デスクトップのフレーム数、マウス操作、Mockの両眼画像はH1〜H7の代わりにしない（設計05の方針）。

## 設計書の番号との対応

段階9までの実行計画（`Docs/Design/Stage9_Plan_2026-09-26_ja.md`、第3.2節）の割り当てと同じ。設計08〜10の実機保留分は、PS VR2の導入の直後に、設計08→09→10の順で行う（`設計08修正02：`→`設計09修正01：`→`設計10修正02：`。旧`08修正`・`10修正`は番号のない修正なので修正01と数える）。この時期は、進行役ではなく利用者が選んだ（制作手順のQ9）。08〜10は26より前の番号なので、戻って埋めても設計書の番号の順は崩れない。

| H | 設計書でHMD実機が関わる番号 |
| --- | --- |
| H1 | 08（profileと実機入力）・10（起動と両眼）で回収、34で再確認 |
| H2 | 10（概値）、35（最大密度）、50（p95/p99、通し） |
| H3 | 34（爪・飛沫）、38（線） |
| H4 | 09（静止した座席での1m基準・目の高さ・頭部移動）、34、40 |
| H5 | 40、45 |
| H6 | 38 |
| H7 | 10（runtime側）、45（アプリ側の座席リセット）、50（通し） |

設計19のHMD描画（両眼の深度・影）と設計14の船上の確認は、それぞれの試料や配置を使わなくなった（19はD2で再生の経路がkeyposeに替わり、14は美術優先27修正01の座席v1に替わった）ので、番号としては回収しない。H2・H3（設計34・35）とH4（設計34・40）で取る。段階10の51〜55のフレーム時間は、段階10の番号で扱う。

## 美術優先25から変わる点

| 項目 | 美術優先25 | 設計02修正01 |
| --- | --- | --- |
| 機材 | 研究室からの借用を優先。購入するならQuest 3 512GB | 利用者の手元にあるPS VR2とPCアダプター。HMDは購入しない。利用者のものか借用かは未確認。DPケーブルの有無も未確認 |
| 決定期限 | 9/28、最遅9/29 | 要らない。導入は利用者の都合のつく早い日 |
| 接続 | Meta Horizon Link（USBで映像を圧縮して送る） | PCアダプター経由のDisplayPort 1.4とUSB 3.0。コントローラーはBluetooth |
| OpenXR runtime | Meta Horizon Link | SteamVR |
| 周波数 | 90Hz、退避72Hz | 90Hz。120Hzは記録のみ。72Hzはない |
| 片眼のパネル | 2064×2208（Quest 3） | 2000×2040 |
| interaction profile | Oculus Touch（Quest用として）。Touch Plusは保留 | Oculus Touch（SteamVRの割り当てとして）。予備はIndex→Simpleの順。Touch Plusの保留は外した |
| H2の計測 | Oculus Debug ToolのPerformance HUD | SteamVRのフレームタイミング表示と保存機能 |
| H6 | Linkの圧縮 | 描画解像度とレンズ越しの細部 |
| 利用者の操作 | Metaアカウント、Horizonアプリ、Linkアプリ | SteamVR、PlayStation VR2アプリ、Bluetoothのペアリング、SteamVRをOpenXR runtimeにする設定 |

変わらない点：90HzでGPU p95 ≤8.9ms。H1〜H7の合格条件は下げない。PC側ミラーをHMD内の証拠と呼ばない。VR中の停止・再開、アプリ側の座席リセット、コントローラー入力は未実装で、実装してから試す。代理は導入・設定変更・購入をしない。実機で確かめるまで、VR項目は「未検証」とする。

## 未確認事項

- 手元のPS VR2が利用者のものか借用か。借用なら、10/29まで使えるか、この本機でファームウェアの更新とPCとのペアリングをしてよいか（利用者への質問。未回答）。
- RTX 3080の背面の空いたDP端子の数と、DP 1.4ケーブルの有無（利用者への質問。未回答）。
- 内蔵Bluetooth（Intel、5.2相当）でSenseが安定してつながるか。Sonyの試験一覧に内蔵品はない。不安定なら一覧の外付けアダプターを検討する（購入は本人の判断）。
- SteamVRの推奨描画解像度（PS VR2の100%で片眼何画素になるか）。
- SenseのボタンとTouchのボタンの対応（SteamVRの割り当て）。
- FrameTimingManagerのGPU値が、SteamVRのXR経路で取れるか。
- SteamVRのフレームタイミングの保存機能の現在の名前と保存先。
- Unity（D3D11・SPI）がSteamVRのOpenXRで問題なく動くか。
- `XRInputSubsystem.TryRecenter()`がSteamVRで効くか。
- DP経路に圧縮（DSC）があるか。PS VR2で再投影（Motion Smoothing）が働くか。
- SteamVRの導入に要る容量。
- 本機のRTX 3080の端子構成（HPの公式仕様ページは取得できなかった）。

## 出典（特記がなければ2026-09-26取得）

公式：

- Sony：[How to prepare for using PS VR2 with PC](https://www.playstation.com/en-us/support/hardware/pc-prepare-ps-vr2/)、[日本語版](https://www.playstation.com/ja-jp/support/hardware/pc-prepare-ps-vr2/)（最低・推奨の要件、DP 1.4の直結、USB Type-Cの映像出力は非対応、USB 3.0の直結、Bluetooth 4.0以降、必要なアプリ）
- Sony：[How to set up PS VR2 on PC](https://www.playstation.com/en-us/support/hardware/pc-ps-vr2-set-up/)（接続、表示灯の色、アプリの導入、ペアリングのボタン、装着と部屋のスキャン）
- Sony：[Bluetooth adapters compatible with PS VR2 on PC](https://www.playstation.com/en-us/support/hardware/pc-ps-vr2-bluetooth/)（試験した4機種、2024-07-20、使い方の助言）
- Sony：[PS VR2 tech specs](https://www.playstation.com/en-us/ps-vr2/ps-vr2-tech-specs/)（有機EL、片眼2000×2040、90Hz／120Hz、視野約110°、SenseはBluetooth 5.1）
- PlayStation.Blog：[PlayStation VR2 players can access games on PC with adapter starting on August 7（2024-06-03）](https://blog.playstation.com/2024/06/03/playstation-vr2-players-can-access-games-on-pc-with-adapter-starting-on-august-7/)（PCで使えない機能、使える機能）
- Steam：[PlayStation®VR2 App](https://store.steampowered.com/app/2580190/PlayStationVR2_App/)（アプリ番号2580190、2024-08-06公開、システム要件、容量700MB）
- Khronos：[OpenXR Loader（1.1）](https://registry.khronos.org/OpenXR/specs/1.1/loader.html)（Windowsのactive runtimeのレジストリ、`XR_RUNTIME_JSON`）
- Unity：[OpenXR 1.16 Oculus Touch Controller Profile](https://docs.unity3d.com/Packages/com.unity.xr.openxr@1.16/manual/features/oculustouchcontrollerprofile.html)（2026-09-25取得、[美術優先25](Step_25_ja.md)）。導入済みパッケージのprofile一覧は本機で確認した

二次情報：

- UploadVR：[PlayStation VR2 PC Adapter Review（2024-08-07）](https://www.uploadvr.com/playstation-vr2-pc-adapter-review/)（SteamVRで90Hzと120Hzを選べる、PCで使えない機能）
- Unity Discussions：[PSVR2 on Steam with adapter（2024-08-29〜10-26）](https://discussions.unity.com/t/psvr2-on-steam-with-adapter/1511670)（OpenXRにSense用の拡張がない、SteamVRがTouchへ「best fit」で割り当てる）
- GitHub：[praydog/REFramework issue #1125（2024-09-21）](https://github.com/praydog/REFramework/issues/1125)（SteamVRがSenseを「Oculus Touch compatibility mode」で動かすという報告）
- Steam Community：[Useless without OpenXR, returning it（2024-08-07〜）](https://steamcommunity.com/app/2580190/discussions/0/4509877583653935248/)（SteamVRをactive runtimeにすればOpenXRのゲームが動く）
- Vrex Academy：[How to Set Your OpenXR Runtime](https://academy.vrex.no/knowledge-base/openxr/)（SteamVRの設定→OpenXR→SteamVRをruntimeにする、管理者権限が要る。日付の記載なし）
- Epic Games：[SteamVR Profiling and Performance in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/steamvr-profiling-and-performance-in-unreal-engine)（SteamVRのフレームタイミング表示、`VRFrames.csv`の保存）。Valve Developer Wikiの[SteamVR/Frame_Timing](https://developer.valvesoftware.com/wiki/SteamVR/Frame_Timing)は403で取得できなかった
- 販売店：[OMEN 45L GT22-0001ur（RTX 3080）の仕様](https://outletclick.com/catalog/product/view/_ignore_category/1/id/21428/s/hp-omen-45l-gaming-dt-gt22-0001ur-rtx-3080-10-gb/)（「3x DisplayPort, HDMI」、背面USB。本機とは型番が違う）。HPのサポートの仕様ページは時間切れで取得できなかった

## この番号の証拠と範囲

- 成果物は本文書のみ。
- 代理が行ったのはWeb閲覧（読むだけ）と本機の読み取り専用の照会だけである。ソフトの導入、ダウンロード、購入、アカウント操作、フォームの送信、OpenXR runtime・レジストリ・Unity設定・グローバル設定の変更はしていない。
- 照会で見えたSteamのアカウント名とBluetooth機器の名前は、この文書に書いていない。
- 旧試作の禁止場所、`G:\research\model`、732e198より前の履歴には触れていない。ほかの番号のファイルは変えていない。
