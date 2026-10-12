# Basilisk で巻き波を独立に確かめる道具

Houdini FLIP の 2D の実験の結論（「急な海底で、巻きが原画に近づく」）を、別の解き手（Basilisk、空気と水の 2 相 NS ＋ VOF）で確かめるための道具。結果と読み方は [報告](../../Docs/Research/Basilisk_Check_ja.md)、動画と数の表は `Docs/Evidence/Basilisk/` にある。

## 置いた物

| ファイル | 中身 |
| --- | --- |
| `gw_shoal.c` | 計算の本体。Feddersen ら 2024 の風なしの算例（作者が Basilisk の sandbox に公開した `sandbox/ffeddersen/shoal_RE0_BO4000.c`）を元に、海底の形・波の大きさ・表面張力・粘りを実行時の引数で変えられるようにした |
| `cases.json` | 走らせた算例の全部（A：論文の再現、B：S1・S2・S5、C：条件を広げた探し）の引数と説明 |
| `run_cases.py` | `cases.json` の算例を走らせる（同時に走らせる数、MPI のプロセス数を選べる） |
| `post/gwread.py` | 書き出し（`win_*.bin`・`full_*.bin`・`log.txt`）を読む |
| `post/gwruler.py` | 原画と同じ物差し（`Tools/GWWaveGen/ruler/s52_shape.measure_mask`）で測り、score3 を出す |
| `post/gwpaper.py` | 論文と比べる巻きの量（着水の時刻、空洞の面積 A_O、噴流の面積 A_J、楕円の W/L、向き θ_O、噴流の幅） |
| `post/gwcase.py` | 1 本の計算をまとめて測る（論文の量＋物差し） |
| `post/gwtable.py` | 測った結果を集めて数の表（JSON・Markdown）にする |
| `post/gwvideo.py` | 動画（上：全体の側面、下：頂を追う拡大、巻く間は原画の輪郭を重ねる）と、並べた比べの動画 |
| `post/make_videos.py` | 算例ごとの動画と比べの動画を `Docs/Evidence/Basilisk/` に作る |

## 入手と組み立て（Linux）

1. 要る物（Ubuntu 24.04 で確かめた）：`gcc make flex bison gawk ffmpeg`、MPI で走らせるなら `libopenmpi-dev openmpi-bin`、動画の日本語の文字に `fonts-noto-cjk`。Python 3 に `numpy scipy scikit-image pillow matplotlib`。
2. Basilisk の取得：`curl -O https://basilisk.fr/basilisk/basilisk.tar.gz`（darcs でもよい：`darcs clone https://basilisk.fr/basilisk`）。
   - 今回使った tarball：2026-10-12 に取得、SHA-256 `de851a91712aa83b0592e1e1ae8f7d7e2ffe1ade0266433434700f8c313fbed4`（中のファイルの日付は 2026-09-18、NEWS の最新の版は「25-02-26 (macros)」）。
   - 元にした作者の設定 `shoal_RE0_BO4000.c`：`https://basilisk.fr/sandbox/ffeddersen/shoal_RE0_BO4000.c?raw`、SHA-256 `e09a4e6bfd5fb83031f49839e0edf66775fa0c3bf5fb0896eb8b180500840ebd`。
3. 組み立て：

   ```bash
   tar xzf basilisk.tar.gz && cd basilisk/src
   ln -s config.gcc config
   make -k        # -j を付けると ast/libast.a の順番で失敗することがあった。GPU 用（grid/gpu など）の失敗は使わないので無視してよい
   export BASILISK=$PWD PATH=$PATH:$PWD
   ```

4. 計算の本体の組み立て（`Tools/Basilisk` で）：

   ```bash
   qcc -O2 -Wall -disable-dimensions -DTENSION=1 gw_shoal.c -o $GW_BIN/gw_shoal_t -lm   # 表面張力あり（A）
   qcc -O2 -Wall -disable-dimensions -DTENSION=0 gw_shoal.c -o $GW_BIN/gw_shoal_n -lm   # 表面張力なし（B・C）
   # MPI 版（任意）
   CC99='mpicc -std=c99 -D_GNU_SOURCE=1' qcc -O2 -disable-dimensions -D_MPI=1 -DTENSION=0 gw_shoal.c -o $GW_BIN/gw_shoal_n_mpi -lm
   ```

## 走らせ方

```bash
python3 run_cases.py --bin $GW_BIN --runs $GW_RUNS --jobs 3 A_L10 B_S2_L11 C07_L10
python3 run_cases.py --print A_L12      # 命令だけ見る
```

書き出しは大きい（1 本 0.1〜1 GB）ので、リポジトリの外に置く。測る・動画を作るのは：

```bash
cd post
GW_RUNS=$GW_RUNS python3 gwcase.py $GW_RUNS/B_S2_L11 out.json --case B_S2_L11
GW_RUNS=$GW_RUNS GW_ANA=解析の置き場 python3 make_videos.py case B_S2_L11
```

## 計算の決まり（無次元：h0 = 1、g = 1、水の密度 1、時間 t√(g/h0)）

- 領域は正方形（一辺 `lbox`、左端 `xl`、上端は静かな水面から 10 h0）。海底は embed（固体の境界）で、区分線形の水深 `bathy=x1:d1,x2:d2,...`。
- 初めの波：GN の孤立波（振幅 `a0`、頂 `x0`）。水の中の流速は論文の式（u は深さによらない、w は深さに比例）。空気は静止。
- 境界：左は圧力 0（ディリクレ）、右は圧力の勾配 0、左右とも流速の法線の勾配 0、上は流速の法線 0。海底は滑りなし（流速 0）。作者の設定と同じ（指令の「両端は壁」とは違う）。
- 格子：適応の 4 分木。誤差の許し cs 0.03、f 0.01、u 4×10⁻⁴（作者の設定と同じ）。最も細かい段 `level`（Δ = lbox/2^level）。
- 書き出し：ふつうは Δt 0.1、前の面が 50° を超えるか覆いかぶさりが出たら Δt 0.02。覆いかぶさりを見つけてから `tail`（既定 3.0）後に止める。
  - `win_*.bin`：頂を追う窓（頂の 6 h0 後ろから 4.5 h0 前、y −0.7〜1.5）。間隔は最も細かい格子。
  - `full_*.bin`：全体（横 1600 点、y −1.1〜1.5）。
  - 形式：`GWS1`、double 5 個（t、窓の左下 x・y、間隔、追った頂の x）、int 2 個（nx・ny）、uint8 の f（×254）、uint8 の cs（×254）。行 0 が下。
  - `log.txt`：コマごとの時刻、頂の高さと位置、格子の数、水の体積、運動・位置のエネルギー、覆いかぶさった列の数、前の面の角度、経過時間。

## 作者の設定から変えた所

- 作者は、空気だけの段（風を育てる、t = 0〜1001）の後に水の段へ移る。風なしの算例なので、ここでは空気を静止させて水の段から始めた。時刻 t は作者の t − 1001 にあたる。
- 書き出し（窓と全体の 2 値の格子）、頂の追跡、覆いかぶさりを見つけて止める仕組みを足した。
- 表面張力を切る版（`-DTENSION=0`）と、粘りを切る引数（`re=0`）を足した。
