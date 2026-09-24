# M0のPC中間成果

**M0正式完了ではない。HMD未所持・利用者確認待ち。**

[説明・操作・再現方法・保留一覧](../../Progress/Step_10_ja.md)

| ファイル | 内容 |
| --- | --- |
| [M0_Seated.png](M0_Seated.png) | 自動カメラ0秒、着座視点 |
| [M0_Boat_Exterior.png](M0_Boat_Exterior.png) | 自動カメラ8秒、検証用静止船の全体 |
| [M0_Calibration.png](M0_Calibration.png) | 自動カメラ13秒、Blenderの箱と非対称目印 |
| [M0_Desktop_Walkthrough.mp4](M0_Desktop_Walkthrough.mp4) | 20秒・1280×720・480枚を24fpsで再生 |
| [10_provenance.json](10_provenance.json) | 出典、記録条件、画像・動画・ビルド一式のハッシュ |

同じUnity PC実行版のシーンをCamera.Renderでオフスクリーンへ描画した実画像。注記もUnity内で描画している。通常画面の提示を録画したものではない。24fpsは記録用の固定時間から作った値であり、実時間性能・HMD性能を示さない。

校正画像の独立した6つの立体はBlender由来。灰色は1m箱、赤はBlender+X、緑は+Y、青は+Z、橙は-X、紫は非対称点。近くの細い3色の線は別のUnity世界軸で、赤+X・緑+Y・青+Zを示す。色が同じでも座標系が異なるため、寸法・符号は [07の実測](07_unity_import.json) と合わせて見る。
