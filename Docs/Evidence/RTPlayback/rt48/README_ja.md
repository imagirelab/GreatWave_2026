# RT48 の記録の写し（案内）

- 元：`Unity/Build/RT48/`（Git 対象外）。2026-10-11 の報告の段で `Tools/GWWaveGen/rt48/d_deliver.py copy` が写した。写しと元の SHA-256 は `../run.json` の `records`。
- 〔10/12 細かい元〕細かい元の段（10/11 12〜13 時）の後に `d_deliver.py copy_fine` で写し直した。粗い元の段の写しは中身が同じ物はそのまま、記録（`record_ja.md`・`data/record_ja.md`）は書き足した物に新しくした。
- 報告：[RT_Playback_ja.md](../../../Progress/RT_Playback_ja.md)。
- フォルダーの形は元と同じにしたので、記録どうしの相対のリンク（`plan/plan_ja.md`、`../record_ja.md` など）はこの写しの中でも同じ所を指す。計画の中の `../../../../Docs/...` のリンクは元の置き場所（`Unity/Build/RT48/plan/`）からの相対なので、この写しでは 1 段ずれて届かない。リポジトリの `Docs/` の同じ名前のファイル（制作手順・調べ・FLIP42 の報告）を見てください。写していない物（焼き `data/coarse/`、プレイヤー `unity/player/`、連番 `video/frames_*`、書き出し `verify/coarse/unity_editor/` など、大きい物）へのリンクと文中のパスは、元の `Unity/Build/RT48/` の物を指す。焼きとプレイヤーの大きさと SHA-256 は `../run.json` の `not_copied`。

| 写し | 中身 |
| --- | --- |
| `plan/plan_ja.md`・`plan/review_ja.md`・`plan/plan_frozen.json`・`plan/plan_numbers.json` | 走らせる前に書いて凍結した計画、独立のレビュー、計画の SHA-256、計画の数（R3 の入力の SHA-256 を含む） |
| `record_ja.md` | 全体の記録：計画の読み方、計画から変えた所、つなぎ・確かめ・動画の段（V0〜V12）、報告の段（D1〜D6、確かめを受けて直した言い方） |
| `data/record_ja.md`・`data/c1a.json` | データの段（R3 の記録の読み方、粗い元の焼き、C1 (a)・C3・C4・K・船の表） |
| `unity/record_ja.md` | Unity の段（部品、合成の曲線と粗い元での自己試験 T0〜T11・P1〜P8） |
| `verify/coarse/unity_editor_result.json`・`unity_player_result.json` | C5・C6 と取り置いたコマの補間（V1〜V6）の数（Editor とプレイヤー） |
| `verify/timing/c7_1/summary.json`・`machine.json` | 1 フレームの時間（C7）と、測る間の機械の様子 |
| `check/check_ja.md`・`check/k_*.py`・`check/out/k_*.json` | 独立の確かめ（試作を作っていない確かめ役が、自分で書いた道具で R3 の記録から数を出し直した）。大きい出力（`k_r3.json`・`k_video_*` の行ごとの値・`my_r3_frames.npz` など）は写していない |
| 〔10/12 細かい元〕`data/c1b.json`・`data/c2.json`・`data/fine/summary.json` | C1 (b)（R3e と R3 の記録の比べ）、C2（細かい面の確かめ。コマごとの値を含む）、細かい元の焼きのまとめ（C3・C4・K） |
| 〔10/12 細かい元〕`verify/fine/unity_editor_result.json`・`unity_player_result.json` | 細かい元の C5・C6 と取り置いたコマの補間（V1〜V6） |
| 〔10/12 細かい元〕`verify/<元>/taper.json`・`verify/<元>/interp_share.json` | x の両端の下ろしの見え方（v_taper.py）、補間しているフレームの割合（v_share.py）。粗い元と細かい元 |
| 〔10/12 細かい元〕`verify/timing/c7_fine/`・`verify/timing/c7_coarse_same_machine/` の `summary.json`・`machine.json` | 細かい元の C7 と、同じ時に測り直した粗い元 |
| 〔確かめ fine〕`check_fine/check_ja.md`・`check_fine/q_*.py`・`check_fine/out/*.json`・`*.txt` | 細かい元の段の独立の確かめ（細かい元の段を作っていない確かめ役が、自分で書いた道具で R3e の粒子・細かい面・焼き・Unity の書き出し・動画を読み直した。10/11 13 時台）。比べの絵（`out/video/`）は写していない。C2 (a) が波のある所を測っていなかったことなどを見つけ、報告と記録はこれに合わせて直した。`data/c2.json` は道具の出した値のまま（(a) の「入った」が残る） |
