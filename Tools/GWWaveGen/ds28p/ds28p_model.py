# -*- coding: utf-8 -*-
"""仕上げ28：設計28修正01 試行F の生成器（Tools/GWWaveGen/ds28r01f/ds28r01f_model.py）を import して継承し、K*′ P28R2 の上の動きの
見え方の 2 つを、名前の付いた美術の誘導として足す層。試行F と設計26〜29 のファイルは変えない（読み込む時に SHA-256 を照合する）。

README
======
足す値（ds28p_params.json。どれも名前で切れる。t* ではどちらも何も動かさない）：
  ds_upper_back_aspect（M10：側面 t 4〜6.5 s の「平らな頂の塊」）：
     試行F の背は、K*′ の背面を頂を中心に縦に sy = y_頂/y_頂(t*) 倍、横に Lb′ 倍する（ds_back_width_retarget の後の表。形成の途中は 1.5〜1.8）。
     K*′（P28R2）の背は t* で広く丸いので、途中（sy 0.55〜0.8）では上の背が t* の約 2 倍なだらかになり、正側面で前が切り立ち頂の後ろが
     長く平らな塊に見えた（側面の包絡の読み：頂から 0.8H まで下がる後ろの距離 14 m、前 3.5 m）。
     背の上の部分（K*′ の背の高さの割合 η が eta0〜eta1 で重みが 0 → 1）だけ、横の倍率の t* の幅より広い分（Lb′ − 1）を k 倍にする
     （L_up = 1 + k·(Lb′ − 1)。k = 0 で上の背は t* の K*′ の幅のまま）。背の下の部分・足は Lb′ のまま（本体の量感と足の動きは変えない）。
     Lb′ と L_up はどちらも時間とともに 1 へ減るので、背の列の横の動きは単調（引かれて戻る往復を作らない）。t* の幅より狭くはしない。
     行の重みは K*′ の行の高さ H で row_H_zero_m → row_H_full_m（小さい奥の行・端の行には掛けない。頂が尖らないように）。
     t* では Lb′ = 1 なので L_up = 1（K*′ のまま）。
  ds_far_hook_earlier（M7：奥の行 c +10〜+14 m の唇の前の頂の尖り）：
     ds_far_hook_early（試行F）の ψ_b（頂〜錨の Hermite と K*′ の上の前面の相似変換の混ぜ）の σ の窓を、K*′ の c が c_min_m 以上の鉤の行だけ
     sigma_start〜sigma_end へ早める（両端で速さ・加速度 0 の smootherstep のまま。σ sigma_end より後は K*′ の上の前面の相似変換そのもの）。
     唇の模型を使う行（κ = 1）では ψ_b を使わないので変わらない。
使い方（numpy だけ）：
    from ds28p_model import Generator
    g = Generator(kstar_dir="Unity/Build/Polish/28/kstar_p28")
    X = g.local(-3.0)
"""
import copy
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DSF = os.path.abspath(os.path.join(HERE, "..", "ds28r01f"))
for _p in (DSF, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import ds28r01f_model as MF  # noqa: E402

MD = MF.MD
PARAMS_P = os.path.join(HERE, "ds28p_params.json")
P_NAMES = ("upper_back_aspect", "far_hook_earlier")


def load_p(path=PARAMS_P):
    R = MD.load_json(path)
    shas = {}
    for k, v in R["base"].items():
        if k.endswith("_sha256") or not k.startswith("trial_"):
            continue
        p = os.path.join(REPO, v)
        if not os.path.isfile(p):
            raise SystemExit("[ds28p] base のファイルがありません：%s" % v)
        s = MD.sha256_file(p)
        want = R["base"].get(k + "_sha256")
        if want and s != want:
            raise SystemExit("[ds28p] base のファイルの SHA-256 が違います：%s（%s ≠ %s）" % (v, s[:12], want[:12]))
        shas[v] = s
    return R, shas


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


class Generator(MF.Generator):
    """試行F ＋ ds_upper_back_aspect・ds_far_hook_earlier。"""

    def __init__(self, version="art_on", kstar_dir=None, log=None, p_path=PARAMS_P, p_overrides=None, off=(), **kw):
        self.RP, self.p_base_shas = load_p(p_path)
        if p_overrides:
            MF.M8.deep_merge(self.RP, copy.deepcopy(p_overrides))
        self.p_path = p_path
        self.p_sha = MD.sha256_file(p_path)
        off = tuple(off)
        self.p_off = tuple(n for n in off if n in P_NAMES)
        rest = tuple(n for n in off if n not in P_NAMES)
        on = version == "art_on"
        self.p_on = {n: bool(on and (self.RP.get(n) or {}).get("on", True) and n not in self.p_off) for n in P_NAMES}
        self._ub_w = None
        self._far_mask = None
        MF.Generator.__init__(self, version, kstar_dir=kstar_dir, log=log, off=rest, **kw)
        self._p_setup()

    # ------------------------------------------------------------ 準備
    def _p_setup(self):
        K = self.K
        H = np.asarray(self.H, float)
        UB = self.RP["upper_back_aspect"]
        h0, h1 = float(UB["row_H_zero_m"]), float(UB["row_H_full_m"])
        self._ub_w = np.where(np.asarray(self.has_body, bool), smoothstep((H - h0) / max(h1 - h0, 1e-6)), 0.0)
        FE = self.RP["far_hook_earlier"]
        c = np.asarray(K.c, float)
        if getattr(self, "_hook_mask", None) is None and getattr(self, "_hook_on", False):
            self._hook_setup()
        hm = self._hook_mask if getattr(self, "_hook_mask", None) is not None else np.zeros(len(c), bool)
        self._far_mask = hm & (c >= float(FE["c_min_m"]))
        self.p_info = dict(upper_back_rows=int((self._ub_w > 0).sum()), upper_back_full_rows=int((self._ub_w >= 1 - 1e-9).sum()),
                           far_hook_earlier_rows=[int(r) for r in np.nonzero(self._far_mask)[0]])

    # ------------------------------------------------------------ ds_far_hook_earlier
    def _shared(self, tau):
        S = MF.Generator._shared(self, tau)
        if getattr(self, "p_on", {}).get("far_hook_earlier") and self._far_mask is not None and self._far_mask.any() and self.sw["ds_tube_shape"]:
            FE = self.RP["far_hook_earlier"]
            s0, s1 = float(FE["sigma_start"]), float(FE["sigma_end"])
            S = dict(S)
            pb = np.asarray(S["psi_b"], float).copy()
            pn = MF.s5((np.asarray(S["sig"], float) - s0) / (s1 - s0))
            pb[self._far_mask] = pn[self._far_mask]
            S["psi_b"] = pb
        return S

    # ------------------------------------------------------------ ds_upper_back_aspect
    def _back(self, r, S, Lb_r, Arow, Yrow):
        capped = MF.Generator._back(self, r, S, Lb_r, Arow, Yrow)
        if not getattr(self, "p_on", {}).get("upper_back_aspect") or self._ub_w is None:
            return capped
        wr = float(self._ub_w[r])
        if wr <= 0.0 or not (self.sw["ds_body_narrow"] or self.sw["ds_back_steep"]):
            return capped
        UB = self.RP["upper_back_aspect"]
        A0, Y0 = self.K.A, self.K.Y
        jB = self.jB
        root = int(self.root[r])
        ac = float(S["a_c"][r])
        ar = float(self.a_root[r])
        d0 = A0[r, jB:root + 1] - ar                     # K*′ の背の列の頂からの横の距離（≤ 0）
        ok = d0 < -1e-9
        if not ok.any():
            return capped
        Lcur = np.ones_like(d0)
        Lcur[ok] = (Arow[jB:root + 1][ok] - ac) / d0[ok]  # 試行F が使った横の倍率（列ごと。ふつうは 1 つの値）
        eta = Y0[r, jB:root + 1] / max(float(self.y_root[r]), 1e-9)
        v = wr * smoothstep((eta - float(UB["eta0"])) / (float(UB["eta1"]) - float(UB["eta0"])))
        # 上の背の横の倍率：t* の K*′ の幅より広い分（Lcur − 1）だけを k 倍にする（k = 0 で上の背は t* の幅のまま）。
        # Lcur は時間とともに 1 へ減り、L_up = 1 + k·(Lcur − 1) も同じ向きに減るので、どの列の混ぜ Lnew も時間に対して単調（背が後ろへ
        # 引かれて戻る往復を作らない）。t* の K*′ より狭くはしない（狭くすると t* の前に広がり直す）
        k = float(UB["k"])
        Lup = np.where(Lcur > 1.0, 1.0 + k * (Lcur - 1.0), Lcur)
        Lnew = Lcur + v * (Lup - Lcur)
        Anew = Arow[jB:root + 1].copy()
        Anew[ok] = ac + Lnew[ok] * d0[ok]
        Arow[jB:root + 1] = Anew
        return capped
