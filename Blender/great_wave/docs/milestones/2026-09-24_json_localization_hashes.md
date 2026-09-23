# JSON 説明文の日本語化とファイルハッシュの対応

記録日：2026-09-24。

## 変更の範囲

15 個の JSON に含まれる自然言語の説明を日本語にした。対象は `src/contour/base_contour_params.json` と Git 管理下の `target/` の JSON である。翻訳は 310 個の説明値（重複を除くと 127 種類）に適用した。その後、現行入力を検査できるよう、設定の `candidate_sha256_expected.value` の 3 個の期待値と同項目の説明を更新した。

輪郭点、フレーム値、しきい値、単位の意味、機械用キー・固定ラベル、配列の並び、ファイルパス、出典 URL は変更していない。波の生成、輪郭の再測定、候補の再判定、派生ファイルの再生成は行っていない。

## 数値と構造の確認

比較元はコミット `9b337656bc6512371d59e6aa0ba87906a7f5a177` の Git オブジェクトに保存された各ファイルの内容、比較先はこの記録を作成した時点の作業ファイルである。両方を JSON として解析し、全階層を比較した。

- 対象：15 ファイル。
- 比較した数値の葉：154,984 個。すべて同じ型・値だった。
- オブジェクトのキーと順序、配列長と順序、各値の型、真偽値、null：差異なし。
- 文字列の差：314 個。310 個の翻訳値に、期待ハッシュ 3 個とその説明 1 個を加えたもの。
- 形状の変更や新たな検証成功を意味する変更はない。

## 現行候補の期待値

`build_base_contour.py` はファイルをバイナリで読み、SHA-256 を大文字の16進表記にし、期待値との前方一致を調べる。現行候補の実ファイルを同じ方法で計算し、次の結果を確認した。

| 候補 | 現行の期待値（先頭 8 桁） | 現行ファイルとの照合 |
|---|---|---|
| A | `13638117` | 一致 |
| B | `AD8FF240` | 一致 |
| B_alt | `AA536773` | 一致 |

旧期待値は A=`A796F50B`、B=`65F5418D`、B_alt=`4931690E` であり、下表の日本語化前のファイルと一致する。期待値の更新は説明文の変化による。目視判定や数値幾何の更新ではない。

## 変更前後の SHA-256

パスは `Blender/great_wave/` からの相対パス。変更前は上記コミット内の実バイト列、変更後は作業ファイルの実バイト列に対する完全な SHA-256 である。設定ファイルの変更後ハッシュには、期待値と説明の更新も含む。

| ファイル | 日本語化前の SHA-256 | 現行の SHA-256 |
|---|---|---|
| `src/contour/base_contour_params.json` | `8A804D2E0BCF74105A1BC0858FA916835C9EE4FD40C2E5BBC23BFC1EE41C0D38` | `FD5FD29676CB5034A9BB001476AAD330CEFEDB6B880F26D6BA5DC0BF0A2C94BC` |
| `target/base_contour.json` | `4D670EACFA1E1DABCCAA870AF1EEEB41AEC6A1037B35E6256FDB9E3B5B0DB91B` | `E910D083069BB2C1A93C85CDC3E883EA07C86BDACFC4D98FA56A68764DDC9DA8` |
| `target/base_contour_finger_scale.json` | `94B5A01814DB2E3A044A81D273ECC9F07761254200F861C61423A0071760FE47` | `573B98F40F705D6DADE77A91FEBF676BBAC045F85328466BBD9991D18644B02A` |
| `target/candidates/a/base_contour.json` | `A796F50BEA7443CED3DB1BFD279B3D44AE4478C964D68C7FB81AEDB3FD01CA01` | `13638117B36A0EABB7A4DB0DFC9E27A42CB5ACA7731105593C209795DF6B509C` |
| `target/candidates/a/base_contour_smooth_r100.json` | `D8614C130573AFDB810F1D514CAB2FE3A3FF0161CFEF7A5FA7A06BFD45CE13F5` | `C6B948F7CD839C0B2726B5514BB1E55CAAE4EE7ADF100345265C0121C171A040` |
| `target/candidates/a/base_contour_smooth_r120.json` | `CD77EB596BF46EF406D226BD782C0E9A4364671E449D332E95305FCC1C727229` | `74CC9AC1EE7D8E918459EC5E3034AADCF156A8AFA3A91F4629D8F7D5E842BC19` |
| `target/candidates/b/base_contour.json` | `65F5418D04E33798DD5A6206B32D5078AACADE44E91A38D5297F36B04A64F0E9` | `AD8FF240E824F591934D29D910EE4757719840C76F272F9F23EDF776F7B40520` |
| `target/candidates/b/base_contour_alt_white_body_outline.json` | `4931690E1F88D981DFD7208D2B6D1682BD49F7560221802E7A7DA451E7FE577B` | `AA536773B65F4859AECDCC9B78ECE58F5EADB60BF707644DE31688426EC00868` |
| `target/houdini_motion.json` | `BABBD770B99605FEAB31A7CB4F42C4EAB2CB23D7598D3991A3C94711FBB9FA2F` | `1B81D3809CACB30374ECC501E4A4B90A9FB6A420D911F172DF889D2627627AB0` |
| `target/large_form_variants/large_form_r100.json` | `63DC87F4FA08BAD58CFD60A204827BCD643F78895C2D5A17447457ED1970F05A` | `426AA136846542F87EA985745AB7C173CAA2410BFBF92DF2828FFD812ADF3DB5` |
| `target/large_form_variants/large_form_r120.json` | `C58BD196F0E21F8846BCE24EA155B66691861A5A1D769FE3EEEAFD249CDEFF6F` | `F3814F026549E34C004F5309107B3CA808774696EB2ABB04F16DA2A31AA8BCCA` |
| `target/large_form_variants/large_form_r135.json` | `2356B8223BA04A5D602A059F91B584988DB754F3C7F2AAB58F1DCD1BB67FB52F` | `3ED759CAA299A7FEE6CB04CCA98FD13A96689718C20DFE1602FBF6496E046603` |
| `target/large_form_variants/large_form_r150.json` | `4D670EACFA1E1DABCCAA870AF1EEEB41AEC6A1037B35E6256FDB9E3B5B0DB91B` | `E910D083069BB2C1A93C85CDC3E883EA07C86BDACFC4D98FA56A68764DDC9DA8` |
| `target/large_form_variants/large_form_r150_alt_sky_silhouette.json` | `D63B586153DDE2BD42A6E1266CA08F04265223ED45A4174CC4BA3F5F6D40AE6E` | `B090C0A2FCB8E5AC8274FD517E1BC96FA4BCD555176ABFE1862984B23AA8EE8B` |
| `target/large_form_variants/large_form_r150_open_close.json` | `E970E7B9AC5F7B47D045F86D3EDAA96723C027BF21F3A1752BBD1D437953F8EA` | `689933BA55E2C6855A11EE06E21B545EE159C36F1C2C6791C0399704003510A2` |

## 過去の由来情報の扱い

既存の `derived_from`、`provenance`、過去の計測結果内のハッシュは書き換えていない。これらは当時の生成・測定に使用した、日本語化前の入力バイト列を記録している。現行の日本語化済みファイルから再生成した証拠として読んではならない。上の対応表で、説明文が変わったファイルと過去の記録を対応付ける。

候補生成器および派生輪郭生成器の内部に残る説明文字列は、今回の変更範囲外である。生成器を再実行すると日本語化前の説明が再び出力される場合がある。再生成した場合は、その実際の入力・出力とハッシュを別の実行記録として残す必要がある。

## 改行に関する再現条件

この表の現行 JSON は UTF-8、LF 改行である。SHA-256 は JSON の意味ではなくバイト列を検査するため、CRLF への変換だけでも変わる。この作業環境では `core.autocrlf=true` が確認された。同時にリポジトリ直下の `.gitattributes` へ `Blender/great_wave/**/*.json text eol=lf` を追加し、対象 JSON の LF を維持するよう指定した。Git の全体設定は変更していない。既存の作業ファイルが別の改行になっている場合は、そのファイルの実バイト列を確認する必要がある。
