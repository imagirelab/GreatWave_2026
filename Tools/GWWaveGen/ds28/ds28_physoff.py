# -*- coding: utf-8 -*-
"""設計28：切った版を「物理の頂の高さ」で作る（設計27 の引き継ぎ 4 と、P14 と設計26 §1.1 の矛盾の解き方）。

README
======
設計27 の切った版（art_off）は、9 個の切り替えをすべて切っても、行ごとの t* の頂の高さを K* から受け継いでいた（175 行で相関 0.99999。
設計26 §1.1 が美術に数える約 35 m の局所の塔の形）。設計28 では、この行ごとの頂の高さを名前の付いた美術の誘導 ds_crest_tower として
数え、切った版では物理の頂の高さに替える。

  ds_crest_tower 入り（入れた版の既定）：行ごとの t* の頂の高さ = K*（設計27・設計28 の入れた版と同じ。この生成器は入れた版には使わない）
  ds_crest_tower 切り（設計28 の切った版）：行ごとの t* の頂の高さを、搬送波（±30° の 2 系、λp 195 m、NewWave）の分散集中の
      波峰線に沿った包絡 E(c) と狭帯域の 2 次（設計26 E2 と同じ式）から決める（焦点 c = 0 で H* = 20.80 m）。K* の頂が 3 m 以上の
      175 行だけに当て、各行の K* の断面を縦に H_phys/H_K* 倍した手本を使う（唇先・rim・巻きの行・張り出しの列の意味は元の K*）。
      峰の行は焦点の行（c = 0）、噴流の始まりの Froude の抑えは τ0·√(H/H_max)。

物理の頂の高さの式と、切った版の行の扱いは、入力条件の掃引の生成器 ds28_inputs_model.py（InputGen、crest="phys"。
60°・195 m の既定の入力で設計27 の切った版から作った「物理だけ」）と同じ（CarrierCrest・scaled_kstar をそこから import する）。
違うのは、ここでは設計28 の生成器 ds28_model.Generator（美術の誘導 12 個）の切った版に重ねること：設計28 の新しい 3 個
（ds_approach_kstar・ds_tower_peak・ds_tip_white_line）も切れ、設計27 の錨の ease-in（anchor.to_kstar_sigma。設計27 では切った版にも
掛かった）も入らない。唇の重み κ < 1 の行は設計28 と同じく打ち出しを弱めて重力だけで飛ぶ。

設計28 のレビュー対応（2026-09-27）：14 個目の名前の付いた誘導 ds_undercut_kstar を足した。
  ds28_model.Generator.anchor_q は、噴流の始まりの前（σ < −2.4）に、内壁の錨を寝た前面 D_s から始まりの位置 q_on へ寄せる。
  q_on は放出の前の帯の一番前から、始まりの張り出し Lo_on = clip(0.2 − 0.45·ov_K*, 0.06, 0.11)·h_c·H（ov_K* は K* の張り出しを
  波峰線方向にならした値）を引いた位置で、K* の錨の位置 q* で頭打ちする。つまり前面を頂の下までえぐる量が K* から決まっている。
  ds28_model ではこの分岐が切り替えを見ない（ds_approach_kstar を切っても残る）ので、ここで名前を付けて切れるようにした。
  ds_undercut_kstar 入り（入れた版の既定。ds28_model と同じ）：上のとおり。
  ds_undercut_kstar 切り：Lo_on = 0（前面は噴流の始まりにちょうど鉛直になる。設計26 §7.1 の表の「鉛直の前面と噴流の始まり：同じコマ」）、
      K* の錨の位置で頭打ちしない。錨が D_s から q_on へ寄る時刻（σ −4.7〜−2.4 の最小躍度）は同じ。
  既定は版に従う（art_on で入り、art_off で切り）。設計28 の切った版（物理だけ）は 14 個すべてを切る。
  ds28_model.py・ds28_params.json を変えずに（入れた版のパッケージのバイトと記録の SHA-256 を保つため）、ここで上書きする。
  ds28_params.json の切り替えの一覧と note（「12 個」）は ds_crest_tower・ds_undercut_kstar を含まない（この 2 つはこの生成器の引数）。

ds28_model.py・ds28_params.json・ds28_generate.py は変えない（設計28 の入れた版のパッケージのバイトを保つ）。

使い方（リポジトリの根で。1 回 約 10 分）：
    py -3.10 -B Tools/GWWaveGen/ds28/ds28_physoff.py [--out Unity/Build/Design/28] [--name art_off_phys] [--no-check] [--no-sea] [--undercut-kstar]
    （--undercut-kstar：レビューの前の切った版＝ds_undercut_kstar だけ入れた版を作る。比べるための参考）
出力（Git 対象外）：Unity/Build/Design/28/<名前>/ に設計27 と同じ書式のパッケージ（ds27_pos_rgba16.bin・ds27_keypose.json・
ds27_twhite_r32f.bin）、ds27_sea.npz、ds27_checks.json、ds28_generate_log.json。設計27 の Unity の再生器と関門の検査器がそのまま読む。
numpy だけ。利用者の Houdini 解算のファイルは読まない。
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")   # 行列積の和の順を固定し、同じバイトを保つ
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse  # noqa: E402
import datetime  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, HERE)
sys.path.insert(0, DS27)
import ds27_generate as G27  # noqa: E402
import ds27_model as MD  # noqa: E402
import ds28_generate as G28  # noqa: E402
import ds28_model as M8  # noqa: E402
from ds28_inputs_model import CarrierCrest, check_frozen, scaled_kstar  # noqa: E402

REPO = M8.REPO
OUT_DEFAULT = os.path.join(REPO, "Unity", "Build", "Design", "28")
CREST_MIN_H_M = 3.0          # 物理の頂の高さを当てる K* の頂の高さの下限（ds28_inputs_model の既定と同じ）
EXTRA_CODE = [("ds28", "ds28_physoff.py"), ("ds28", "ds28_inputs_model.py")]


class Generator(M8.Generator):
    """設計28 の生成器に、名前の付いた美術の誘導 ds_crest_tower（行ごとの t* の頂の高さを K* から受け継ぐ）と
    ds_undercut_kstar（噴流の始まりの前に前面を頂の下までえぐる量を K* から決める）を足したもの。
    crest_tower=False で物理の頂の高さ、undercut_kstar=False で始まりの張り出し 0（前面が始まりにちょうど鉛直）。
    どちらも既定は版に従う（art_on で入り、art_off で切り）。"""

    def __init__(self, version="art_off", params_path=M8.PARAMS_JSON, log=None, switches=None, crest_tower=None, undercut_kstar=None):
        self.crest_tower = (version == "art_on") if crest_tower is None else bool(crest_tower)
        self.undercut_kstar = (version == "art_on") if undercut_kstar is None else bool(undercut_kstar)
        M8.Generator.__init__(self, version, params_path=params_path, log=log, switches=switches)
        if not self.crest_tower:
            self.variant = self.variant + "+ds_crest_tower=0"
        if not self.undercut_kstar:
            self.variant = self.variant + "+ds_undercut_kstar=0"

    # ------------------------------------------------------------ 噴流の始まりの錨の位置（ds_undercut_kstar）
    def _approach_setup(self):
        M8.Generator._approach_setup(self)
        self.q_on_undercut = self.q_on.copy()          # ds_undercut_kstar 入りの値（記録と比べるため）
        if self.undercut_kstar:
            return
        # 切り：始まりの張り出し Lo_on = 0（放出の前の帯の一番前の真下に錨）、K* の錨の位置 q* で頭打ちしない。
        # 帯の一番前の距離は ds28_model.Generator._approach_setup と同じ式（始まりの帯の角 θ1・θ2、行ごとの帯の間隔）
        ap = self.ap
        H = self.H
        self.lo_on = np.zeros_like(self.lo_on)
        d1 = M8.angle_dir(self.th1f)
        d2 = M8.angle_dir(self.th2f)
        for r in range(self.K.nv):
            if not self.has_body[r]:
                continue
            dl = self.strip_delta * float(np.clip(H[r] / self.P["lip"]["strip_spacing_scale_H_m"], self.P["lip"]["strip_spacing_min_factor"], 1.0))
            n_up = max(int(self.tip[r]) - int(self.root[r]), 0)
            n_un = max(int(self.rim[r]) - int(self.tip[r]), 0)
            front = max(n_up * dl * d1[0], n_up * dl * d1[0] + n_un * dl * d2[0])
            self.q_on[r] = max(float(ap["q_floor"]), front / H[r])

    # ------------------------------------------------------------ 行ごとの値（物理の頂の高さ）
    def _rows(self):
        if self.crest_tower:
            MD.Generator._rows(self)
            self.phys_mask = np.zeros(self.K.nv, bool)
            self.phys_scale = np.ones(self.K.nv)
            return
        self.K_true = self.K
        MD.Generator._rows(self)
        keep = dict(tip=self.tip.copy(), rim=self.rim.copy(), e4_curled=self.e4_curled.copy(), overhang=self.overhang.copy(),
                    root=self.root.copy(), ja=self.ja.copy())
        self.carrier_crest = CarrierCrest(2.0 * self.half_angle, self.lam_p, self.gamma_j, H_ref=float(self.K_true.Y[self.K_true.main_row].max()))
        cc = self.carrier_crest
        Hk = self.K_true.Y.max(1)
        Hp = cc.height(cc.envelope_c(self.K_true.c))
        self.phys_mask = Hk >= CREST_MIN_H_M
        s = np.where(self.phys_mask, Hp / np.maximum(Hk, 1e-9), 1.0)
        self.phys_scale = s
        self.phys_H_target = np.where(self.phys_mask, Hp, Hk)
        self.K = scaled_kstar(self.K_true, s)
        MD.Generator._rows(self)
        assert np.array_equal(self.root, keep["root"]) and np.array_equal(self.ja, keep["ja"]), "縦に伸ばしても頂・錨の列は同じはず"
        self.tip, self.rim, self.e4_curled, self.overhang = keep["tip"], keep["rim"], keep["e4_curled"], keep["overhang"]
        # 峰の行は焦点の行（c = 0）。噴流の始まりの Froude の抑えは τ0·√(H/H_max)（ds28_inputs_model.InputGen._fix_Trow と同じ）
        c = self.K.c
        H = self.H
        if not (self.version == "art_on" or self.sw["ds_farwall_hold"]):
            self.c_pk = 0.0
        T = np.maximum(self.tau0 - np.abs(c - self.c_pk) / self.vpeel, self.floor)
        if not self.sw["ds_lip_target_kstar"]:
            cap = self.tau0 * np.sqrt(np.maximum(H, 0.0) / max(float(H.max()), 1e-9))
            T = np.maximum(np.minimum(T, cap), self.floor)
        self.T_row = T
        self.lag = self.tau0 - self.T_row

    def summary(self):
        s = M8.Generator.summary(self)
        s.update(ds_crest_tower=bool(self.crest_tower), phys_crest_rows=int(np.count_nonzero(self.phys_mask)), ds_undercut_kstar=bool(self.undercut_kstar))
        br = [int(self.K.main_row), int(np.argmin(np.abs(self.K.c - self.c_pk_on)))]      # 主断面（行 159）と峰の行（c +3.85 m、行 192）
        s.update(q_on_over_H={str(r): round(float(self.q_on[r]), 4) for r in br}, q_on_undercut_over_H={str(r): round(float(self.q_on_undercut[r]), 4) for r in br},
                 qst_over_H={str(r): round(float(self.qst[r]), 4) for r in br})
        if not self.crest_tower:
            cc = self.carrier_crest
            s.update(phys_crest_H_at_c_m={("%+.1f" % cv): round(float(np.interp(cv, self.K.c, self.H)), 2) for cv in (-29.5, -15.0, 0.0, 5.5, 12.0)},
                     carrier_AL_m=round(cc.AL, 3), carrier_kbar=round(cc.kbar, 5), c_pk_m=float(self.c_pk))
        return s


def code_sha():
    out = G28.code_sha()
    for d, f in EXTRA_CODE:
        out["%s/%s" % (d, f)] = MD.sha256_file(os.path.join(HERE, f))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="art_off_phys")
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--no-check", action="store_true")
    ap.add_argument("--no-sea", action="store_true")
    ap.add_argument("--undercut-kstar", action="store_true", help="ds_undercut_kstar を入れる（レビューの前の切った版の参考）")
    a = ap.parse_args()
    t0 = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)
    frozen = check_frozen()
    log("設計28 生成：切った版（12 個の切り替えをすべて切る）＋ ds_crest_tower を切る（物理の頂の高さ）＋ ds_undercut_kstar を%s → %s"
        % ("入れる（参考）" if a.undercut_kstar else "切る（始まりの張り出し 0）", a.name))
    g = Generator("art_off", log=log, crest_tower=False, undercut_kstar=bool(a.undercut_kstar))
    B = G27.Builder(g, log)
    B.build_knots()
    outdir = os.path.join(a.out, a.name)
    rec, deq = G28.export_package(g, B, outdir, log)
    rec["generator"]["code"] = "Tools/GWWaveGen/ds28/ds28_physoff.py（ds28_model.Generator の切った版＋ds_crest_tower を切る＋ds_undercut_kstar を%s）" % ("入れる" if a.undercut_kstar else "切る")
    rec["generator"]["code_sha256"] = code_sha()
    rec["tstar"]["note_ja"] = "切った版（物理の頂の高さ）。最後の層（τ = 0）は K* ではない（P14）。"
    G27.dump_json(os.path.join(outdir, "ds27_keypose.json"), rec, compact=True)
    tw = {k: dict(path=G27.rel(os.path.join(DS27, "timewarp_%s.json" % k)), sha256=MD.sha256_file(os.path.join(DS27, "timewarp_%s.json" % k)))
          for k in ("default", "alt")}
    vr = dict(dir=G27.rel(outdir), version="art_off", variant=g.variant, switches=dict(g.sw, ds_crest_tower=g.crest_tower, ds_undercut_kstar=g.undercut_kstar), layers=rec["layers"],
              pos_sha256=rec["pos_sha256"], twhite_sha256=rec["twhite_sha256"], keypose_json_sha256=MD.sha256_file(os.path.join(outdir, "ds27_keypose.json")),
              pos_mib=G27.fnum(rec["pos_bytes"] / 2 ** 20, 2), gpu_estimate=rec["gpu_estimate"], quantization_max_err_m=rec["quantization_max_err_m"],
              knot_tau_range=[rec["knot_tau"][0], rec["knot_tau"][-1]], generator_evals_knots=B.n_eval, summary=rec["generator"]["summary"])
    if not a.no_sea:
        ps = G27.export_sea(g, B, outdir)
        vr["sea_npz"] = dict(path=G27.rel(ps), sha256=MD.sha256_file(ps))
    if not a.no_check:
        chk = G27.run_checks(g, B, deq, log)
        G27.dump_json(os.path.join(outdir, "ds27_checks.json"), chk)
        vr["checks"] = {k: v for k, v in chk.items() if k != "stage_estimate"}
        vr["checks"]["stage_estimate"] = {k: {kk: vv for kk, vv in v.items() if kk != "series_every_0p1s"} for k, v in chk["stage_estimate"].items()}
    vr["seconds"] = round(time.time() - t0, 1)
    runlog = dict(generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  python=platform.python_version(), numpy=np.__version__, machine=platform.platform(),
                  command="py -3.10 -B Tools/GWWaveGen/ds28/ds28_physoff.py " + " ".join(sys.argv[1:]),
                  code_sha256=code_sha(), ds27_frozen_sha256=frozen, timewarp=tw, result=vr, log=logs)
    G27.dump_json(os.path.join(outdir, "ds28_generate_log.json"), runlog)
    print("DONE %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
