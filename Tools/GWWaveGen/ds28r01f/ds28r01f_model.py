# -*- coding: utf-8 -*-
"""設計28修正01 試行F：試行E の動きを、Houdini で作る最後の一コマ K*′ へ、壊さずに当て直す生成器。K*′ はフォルダーで受け取る。

README
======
試行E の Generator（Tools/GWWaveGen/ds28r01e/ds28r01e_model.py）を import して継承する。試行A〜E・設計26〜29 のファイルは変えない。
読み込む時に、ds28r01f_params.json の base の SHA-256 と照合する（違えば止まる）。E の値（ds28r01e_params.json）はそのまま。

E の断面（海・行のならし・再上昇の直しの後、section_y の出力）に、次の 3 つの数値の条件を足す（名前の付いた値。どれも切れる）：
  num_tstar_exact（M2）：t* の差 R = K*′ − E(0)（足の列の高さなど、E の約束と K*′ の違い）を、行ごとの頂の高さの割合で掛けて足す。
     t* は K*′ と浮動小数の丸めまで同じ。
  num_sheet_clearance（M1）：行の断面の上の面 U と下の面 L が、t* の K*′ の隙間の割合で決めた下限の隙間より近づかない（押すのは形の
     連続な関数。t* では何も動かない）。ds28r01f_clearance.py。
  num_bridge_tangles（M1 の残り）：上の 2 つの後にまだ残る局所のもつれ（断面の自己交差・網の局所の自己交差。K*′ から受け継いだものを
     除く）を、行ごとの時間の区間で、端の位置と速さを合わせた 3 次の Hermite に置き換える。区間は生成（ds28r01f_generate.py）の中の
     走査で決め、ファイル（bridge.npz）で渡す。
K*′ を替える時はフォルダーを替えるだけ（コードは変えない）。

F_final（2026-09-29、F の独立の検査の直すべき点の 1・2）で足した美術の誘導の当て直し（どれも生成器を作る時に決まる。名前で切れる）：
  ds_anchor_retarget：内壁の錨（0.3H の点）の噴流の始まりの位置 q_on を、E の min(q_帯, q*) から max(q_帯, q*) に替える。
     K*′ の管が深い行（q* < q_帯。主断面 q* −0.28）では、E のままだと始まりの前（σ −7〜−2.4 の錨の進みの表）に錨が q* まで下がり、
     前面が 0.54／0.65 Hf で鉛直になった（高さより先に倒れる。E1 の後退）。当て直しの後は、始まりの前は E と同じ帯の前の位置 q_帯 まで、
     始まりの後に唇の rim の進み M に合わせて q* へ下がる（管が唇の伸びとともに深くなる。錨は後ろへ単調に動き、戻らない）。
     K*′ の前面が頂より前で終わる行（q* > q_帯。唇の組の外の奥の行 c +7〜+14）では、錨を q* より後ろへ下げない（E のままだと始まりの前に
     頂の真下まで下がって細い指の形になり、始まりの後に q* へ前へ戻った：頂の角 98〜105°、錨の前後の往復）。
  ds_far_hook_early：唇の模型を使わない行（κ < 1。奥の行と端の小さい行）の上の前面は、頂〜錨の Hermite と K*′ の上の前面の相似変換を
     ψ_b で混ぜる（設計27）。ψ_b は σ −3.4〜0 の ease-in（t* の直前に最も速く変わる）で、K*′ の鉤（張り出し 0.43〜0.6H）が
     τ −0.5〜0 に急にできた。行ごとの K*′ の張り出しが hook_min_overhang_H 以上の行だけ、ψ_b を σ s0〜s1 の smootherstep（両端で速さ 0）に
     替えて、鉤を唇の組と同じ時間で育てる（t* の形は同じ）。

使い方（numpy だけ）：
    from ds28r01f_model import Generator
    g = Generator(kstar_dir="Unity/Build/Design/28R01F/kstar_R2")
    X = g.local(-2.0)
    g.set_layers(bridge=False)        # 検査・P20 の比べ：層を切る（生成器を作り直さない）
"""
import copy
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DSE = os.path.abspath(os.path.join(HERE, "..", "ds28r01e"))
for _p in (DSE, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import ds28r01e_model as ME  # noqa: E402
import ds28r01f_clearance as CL  # noqa: E402

MDD, MC, MB, M8, MD = ME.MDD, ME.MC, ME.MB, ME.M8, ME.MD
REPO = ME.REPO
PARAMS_F = os.path.join(HERE, "ds28r01f_params.json")
F_NAMES = ("back_width_retarget", "back_no_undercut", "tail_lip_body", "small_lip_body", "tstar_exact", "sheet_clearance", "bridge",
           "anchor_retarget", "far_hook_early", "balance_swell_calm", "sea_sample_range")
F_INIT_NAMES = ("back_width_retarget", "anchor_retarget", "far_hook_early", "balance_swell_calm")     # 生成器を作る時に決まる（こまごとの層ではない）
# 仕上げ27（2026-09-30）で足した数値の条件（balance_swell_calm・sea_sample_range）は、params に無ければ切った扱い（F_final と同じ）。
# sea_sample_range は生成の書き出し（ds28r01f_generate.py の周りの海の標本）だけが読む
F_OPT_IN = ("anchor_retarget", "far_hook_early", "balance_swell_calm", "sea_sample_range")


def load_f(path=PARAMS_F):
    R = MD.load_json(path)
    shas = {}
    for k, v in R["base"].items():
        if k.endswith("_sha256") or not k.startswith("trial_e"):
            continue
        p = os.path.join(REPO, v)
        if not os.path.isfile(p):
            raise SystemExit("[ds28r01f] base のファイルがありません：%s" % v)
        s = MD.sha256_file(p)
        want = R["base"].get(k + "_sha256")
        if want and s != want:
            raise SystemExit("[ds28r01f] base のファイルの SHA-256 が違います：%s（%s ≠ %s）" % (v, s[:12], want[:12]))
        shas[v] = s
    return R, shas


def s5(x):
    x = np.clip(x, 0.0, 1.0)
    return x ** 3 * (x * (6 * x - 15) + 10)


class Generator(ME.Generator):
    """試行E ＋ num_tstar_exact・num_sheet_clearance・num_bridge_tangles。"""

    def __init__(self, version="art_on", kstar_dir=None, log=None, f_path=PARAMS_F, f_overrides=None, off=(), e_overrides=None,
                 no_rebound_cache=None, defer_no_rebound=False, bridge_file=None):
        self.RF, self.f_base_shas = load_f(f_path)
        if f_overrides:
            M8.deep_merge(self.RF, copy.deepcopy(f_overrides))
        self.f_path = f_path
        self.f_sha = MD.sha256_file(f_path)
        if not kstar_dir:
            raise SystemExit("[ds28r01f] --kstar（K*′ のフォルダー）を渡してください")
        off = tuple(off)
        self.f_off = tuple(n for n in off if n in F_NAMES)      # _back の差し替えが E の __init__ の中から読む
        e_off = [n for n in off if n not in F_NAMES]
        self._f_ready = False
        self._rho_w = self._width_ratio(kstar_dir) if (self.RF["back_width_retarget"].get("on", True) and "back_width_retarget" not in off
                                                         and version == "art_on") else None
        # ds_anchor_retarget・ds_far_hook_early（E の __init__ の中の _approach_setup・_shared が読むので先に決める）
        self._anc_rt_on = bool(version == "art_on" and (self.RF.get("anchor_retarget") or {}).get("on", False) and "anchor_retarget" not in off)
        self._hook_on = bool(version == "art_on" and (self.RF.get("far_hook_early") or {}).get("on", False) and "far_hook_early" not in off)
        self._hook_mask = None
        self._anc_rt = None
        # num_balance_swell_calm（仕上げ27）：E の __init__ の中からも海（sea）が呼ばれるので先に決める
        self._bal_ks_on = bool(version == "art_on" and (self.RF.get("balance_swell_calm") or {}).get("on", False) and "balance_swell_calm" not in off)
        # num_no_rebound_after_apex の格子は、tail_lip_body（唇の強さの差し替え）の後に作る（E の __init__ の中では作らない）
        self._nr_deferred = True
        self._nr_external = bool(defer_no_rebound)
        nr_on_e = "no_rebound" not in e_off
        if "no_rebound" not in e_off:
            e_off.append("no_rebound")
        ME.Generator.__init__(self, version, kstar_dir=kstar_dir, log=log, e_overrides=e_overrides, off=e_off,
                              no_rebound_cache=no_rebound_cache)
        on = version == "art_on"
        self.f_on = {n: bool(on and (self.RF.get(n) or {}).get("on", n not in F_OPT_IN) and n not in self.f_off)
                     for n in F_NAMES}
        self.f_layers = dict(self.f_on)
        self._tail_rows = self._tail_lip_body() if self.f_on["tail_lip_body"] else []
        if not nr_on_e:
            self._nr_deferred = False          # E の側で切った（P20 などの比べ）
        self._bridge = None
        self._bridge_sha = None
        self._gw = None
        self._gw_sha = None
        self._f_setup()
        self._f_ready = True
        self.variant_e = self.variant
        if bridge_file:
            self.set_bridge(bridge_file)
        self._set_variant()
        if self._nr_deferred and not self._nr_external:
            self.enable_no_rebound(no_rebound_cache)     # このプロセスで格子を作る（ファイルがあれば読む、無ければ作って書く）

    def _tail_lip_body(self):
        """tail_lip_body（数値の条件）：唇のある行（E の lip）のうち、主断面を含む続いた組から離れた島（唇のない行を挟んだ奥・手前の端の
        小さい唇）は、E の唇の模型（運び・巻き下ろし・爪）を使わず、本体の模型で動かす（唇の強さ κ = 0。E が唇のない奥の壁の行
        203〜230 にしているのと同じ扱い）。t* は本体の模型でも K*′ のまま（残りは num_tstar_exact）。戻り：差し替えた行。"""
        rows = sorted(int(r) for r in self.lip)
        if not rows:
            return []
        blocks = [[rows[0]]]
        for r in rows[1:]:
            if r - blocks[-1][-1] <= 1:
                blocks[-1].append(r)
            else:
                blocks.append([r])
        m = int(self.K.main_row)
        main = [b for b in blocks if b[0] <= m <= b[-1]]
        main = main[0] if main else max(blocks, key=len)
        out = []
        self._tail_kappa0 = {}
        for b in blocks:
            if b is main:
                continue
            for r in b:
                self._tail_kappa0[r] = float(self.kappa[r])
                self.kappa[r] = 0.0
                out.append(r)
        return out

    # ------------------------------------------------------------ ds_back_width_retarget（E の背の幅の表を K*′ の背の幅へ当て直す）
    def _width_ratio(self, kstar_dir):
        """行ごとの ρ = W_E / W_K′（W は t* の背の幅：足の列 j_B から頂の列（列 j_B〜j_tip の最高点）までの横の距離。W_E は E を作った
        K*（ds28r01e_params.json の kstar.dir_default）の同じ c の行を c で補間）。E の背の幅の表 Lb(σ)（K* の背の幅に対する倍率）を
        Lb′ = 1 + (Lb − 1)·ρ に置き換えて、形成の途中の背の幅の増減を K*′ の幅に対して E と同じ絶対の大きさにする（E の K* のままなら ρ = 1）。"""
        import ds28r01d_kstar as KS
        RE_ = MD.load_json(ME.PARAMS_E)
        old_dir = RE_["kstar"]["dir_default"]

        def widths(kd):
            K = KS.load(kd)
            A, Y, c = K["A"], K["Y"], K["c"]
            jB = int(K["landmarks"]["j_B"])
            idx = ((K["meta"].get("profile") or {}).get("index") or {})
            jt = int(idx.get("j_tip", self.RF["kstar"]["j_tip_default"]))
            root = jB + np.argmax(Y[:, jB:jt], 1)
            return c, A[np.arange(len(c)), root] - A[:, jB], Y.max(1)
        co, wo, ho = widths(old_dir)
        cn, wn, hn = widths(kstar_dir)
        BW = self.RF["back_width_retarget"]
        rho = np.interp(cn, co, wo) / np.maximum(wn, 1e-6)
        rho = np.clip(rho, float(BW["rho_min"]), float(BW["rho_max"]))
        rho = np.where(hn >= float(BW["row_min_H_m"]), rho, 1.0)
        self._rho_w_src = dict(old_kstar=old_dir, rho_min=float(rho.min()), rho_max=float(rho.max()),
                               rho_main=float(rho[int(np.argmin(np.abs(cn)))]))
        return rho

    def _shared(self, tau):
        S = ME.Generator._shared(self, tau)
        if getattr(self, "_rho_w", None) is not None:
            S = dict(S)
            S["Lb"] = 1.0 + (np.asarray(S["Lb"], float) - 1.0) * self._rho_w
        if getattr(self, "_hook_on", False):
            if self._hook_mask is None:
                self._hook_setup()
            if self._hook_mask.any():
                FH = self.RF["far_hook_early"]
                s0, s1 = float(FH["sigma_start"]), float(FH["sigma_end"])
                S = dict(S)
                pb = np.asarray(S["psi_b"], float).copy()
                pn = s5((np.asarray(S["sig"], float) - s0) / (s1 - s0))
                if self.sw["ds_tube_shape"]:
                    pb[self._hook_mask] = pn[self._hook_mask]
                S["psi_b"] = pb
        return S

    # ------------------------------------------------------------ ds_far_hook_early（唇の模型を使わない行の鉤を唇の組と同じ時間で育てる）
    def _hook_setup(self):
        """K*′ の行ごとの張り出し Lo/H（頂の列から j_corner までで最も前の点と、その先 j_facebot までの最も後ろの点の横の差 / 頂の高さ）が
        hook_min_overhang_H 以上で、高さ row_min_H_m 以上の行。ψ_b は唇の模型を使う行（κ = 1）では使われないので、κ によらず決める。"""
        FH = self.RF["far_hook_early"]
        K = self.K
        A, Y = K.A, K.Y_full
        idx = ((K.src.get("meta") or {}).get("profile") or {}).get("index") or {}
        jB = int(self.jB)
        jfb = int(idx.get("j_facebot", 379))
        jco = int(idx.get("j_corner", 314))
        nv = K.nv
        lo = np.zeros(nv)
        hh = np.zeros(nv)
        for r in range(nv):
            yr, ar = Y[r], A[r]
            kc = jB + int(np.argmax(yr[jB:jfb - 1]))
            H = float(yr[kc])
            hh[r] = H
            if H <= 0.5 or kc >= jco:
                continue
            km = kc + int(np.argmax(ar[kc:jco + 1]))
            lo[r] = float(ar[km] - ar[km:jfb + 1].min()) / H
        self._hook_lo = lo
        self._hook_mask = (lo >= float(FH["hook_min_overhang_H"])) & (hh >= float(FH["row_min_H_m"])) & np.asarray(self.has_body, bool)

    # ------------------------------------------------------------ ds_anchor_retarget（内壁の錨の噴流の始まりの位置を K*′ の管の深さへ当て直す）
    def _approach_setup(self):
        ME.Generator._approach_setup(self)
        self._anc_rt = None
        if not getattr(self, "_anc_rt_on", False):
            return
        H = self.H
        ap = self.ap
        h_c = float(self.P["crest_height"]["H_over_Hstar_at_onset"])
        d1 = MD.angle_dir(self.th1f)
        d2 = MD.angle_dir(self.th2f)
        q_e = self.q_on.copy()
        q_strip = np.full(self.K.nv, np.nan)
        for r in range(self.K.nv):
            if not self.has_body[r]:
                continue
            # ds28_model._approach_setup と同じ式（放出の前の帯の一番前 − 始まりの張り出し）
            dl = self.strip_delta * float(np.clip(H[r] / self.P["lip"]["strip_spacing_scale_H_m"], self.P["lip"]["strip_spacing_min_factor"], 1.0))
            n_up = max(int(self.tip[r]) - int(self.root[r]), 0)
            n_un = max(int(self.rim[r]) - int(self.tip[r]), 0)
            front = max(n_up * dl * d1[0], n_up * dl * d1[0] + n_un * dl * d2[0])
            q = max(float(ap["q_floor"]), front / H[r] - float(self.lo_on[r]) * h_c)
            q_strip[r] = q
            self.q_on[r] = max(q, float(self.qst[r]))
        self._q_on_e = q_e
        self._q_on_rt = self.q_on.copy()
        ch = np.abs(self.q_on - q_e) > 1e-9
        m = int(self.K.main_row)
        self._anc_rt = dict(rows_changed=int(ch.sum()), rows_deep=int(np.sum(ch & (self.qst < q_strip))),
                            rows_front_ahead=int(np.sum(ch & (self.qst > q_strip))),
                            max_change_m=float(np.nanmax(np.abs(self.q_on - q_e) * H)) if ch.any() else 0.0,
                            main_row=dict(row=m, q_strip=round(float(q_strip[m]), 4), q_star=round(float(self.qst[m]), 4),
                                          q_on_E=round(float(q_e[m]), 4), q_on_F=round(float(self.q_on[m]), 4)))

    def anchor_q(self, r, tau, sig_r, M):
        """ds_anchor_retarget：噴流の始まりの後に錨が q_on から q* へ下がる行（管の深い行、q* < q_on）だけ、進みを唇の rim の進み M
        （始まりで速さが 0 から急に立ち、t* まで一定の速さ）から、行の時計 σ の smootherstep s5((σ + 2.4)/2.4)（始まりと t* で速さ・加速度 0）
        に替える（progress = sigma_smootherstep）。M のままでは錨の速さが始まりで 0 → 約 2.8 m/s に跳び、形の変わる速さの立ち上がり
        （E の検査器の vdef の段）が主断面で 3.16 m/s²（上限 2.0）になった（F_final の 1 回目）。それ以外の行・時刻は E と同じ。"""
        if (getattr(self, "_anc_rt", None) is not None and sig_r >= -2.4 and self.sw["ds_approach_kstar"]
                and str(self.RF["anchor_retarget"].get("progress", "rim")) == "sigma_smootherstep"):
            q_on = float(self.q_on[r])
            qs = float(self.qst[r])
            if qs < q_on - 1e-12:
                u = (float(sig_r) + 2.4) / 2.4
                return q_on + (qs - q_on) * float(s5(u))
        return ME.Generator.anchor_q(self, r, tau, sig_r, M)

    def set_anchor_retarget(self, on):
        """P20 の比べ用：ds_anchor_retarget を入れた q_on と E の q_on を入れ替え、始まりの時の管の天井の形などを作り直す
        （num_no_rebound_after_apex の格子・水の釣り合いの当てはめは入れた版のまま：近似）。"""
        if getattr(self, "_anc_rt", None) is None and not hasattr(self, "_anc_rt_saved"):
            return
        if on:
            self._anc_rt = getattr(self, "_anc_rt_saved", self._anc_rt)
            self.q_on[:] = self._q_on_rt
        else:
            self._anc_rt_saved = self._anc_rt
            self._anc_rt = None
            self.q_on[:] = self._q_on_e
        self._onset_setup()

    # ------------------------------------------------------------ ds_back_no_undercut（E6 の背の水の釣り合いの山の掛け方の直し）と背の足の高さ
    def _back(self, r, S, Lb_r, Arow, Yrow):
        """E の _back（mode = lower_back）と同じ式で、水の釣り合いの山 δ = Lb − Lb_表 が負（背を狭める）の時だけ、重み w を背の全部の高さへ
        広げる（w_eff = w + (1 − w)·smoothstep(−δ/δ_sw)）。E は δ を背の下の部分（η ≤ 0.5）だけに掛けるので、δ < 0 では下の背だけが
        狭まり、上の背（表の Lb、K*′ で 1.7 倍）が張り出す（K*′ の R1・R2 で τ −3.0〜−1.4 s に、背が後ろへ 10 m 張り出すきのこ形・細い茎、
        茎が内壁を突き抜ける断面の自己交差）。δ ≥ 0 では E と同じ（t* の前の 2 s に頂を尖らせない E6 の目的はそのまま）。δ = 0 で連続。"""
        RFb = getattr(self, "RF", None)
        if RFb is None or self._bw_mode() != "lower_back":
            return ME.Generator._back(self, r, S, Lb_r, Arow, Yrow)
        use_uc = bool(RFb["back_no_undercut"].get("on", True)) and "back_no_undercut" not in getattr(self, "f_off", ())
        Lt = float(S["Lb"][r])
        d = float(Lb_r) - Lt
        capped = M8.Generator._back(self, r, S, Lt, Arow, Yrow)
        if abs(d) < 1e-12 or not (self.sw["ds_body_narrow"] or self.sw["ds_back_steep"]):
            return capped
        A0, Y0 = self.K.A, self.K.Y
        jB = self.jB
        root = int(self.root[r])
        ac = S["a_c"][r]
        ar = self.a_root[r]
        bw = max(ar - A0[r, jB], 1e-6)
        cap_ = max((ac - (A0[r, 0] + float(self.P["back"]["back_foot_margin_m"]))) / bw, 1.0)
        BW = self.RE["back_hold_water"]
        e0, e1 = [float(v) for v in BW.get("lower_back_eta", [0.5, 0.85])]
        eta = Y0[r, jB:root + 1] / max(float(self.y_root[r]), 1e-9)
        w = 1.0 - MD.smoothstep((eta - e0) / (e1 - e0))
        if use_uc:
            mode = str(RFb["back_no_undercut"].get("mode", "uniform"))
            if mode == "table_only":
                # 水の釣り合いの山を背に掛けない（δ = 0）：背は表の Lb（当て直しの後）だけで動く（D の背の保持で σ −1.0 に t* の値へ着いて止まる）
                d = 0.0
            elif mode == "no_narrow":
                # δ < 0（背を狭める）を使わない：C1 のなめらかな max(δ, 0)（δ ≤ 0 で 0、0〜s で δ²/(2s)、s 以上で δ − s/2）。δ = 0 で 0 なので、
                # 山のない時刻（δ = 0 で上の早い戻り）と連続。背は表の Lb のまま、張り出しも後の広がり直しもしない
                # （softplus は δ = 0 で s·log 2 ≠ 0 になり、山の始まりで背が 0.28 m 跳んだ：開発の試し、節点の適応が収束しない）
                sp = float(RFb["back_no_undercut"].get("softplus_m", 0.02))
                d = 0.0 if d <= 0.0 else (d * d / (2.0 * sp) if d < sp else d - 0.5 * sp)
            else:
                sw_ = float(RFb["back_no_undercut"]["delta_switch"])
                w = w + (1.0 - w) * MD.smoothstep(-d / sw_)
        L = np.minimum(Lt + w * d, cap_)
        Anew = ac + L * (A0[r, jB:root + 1] - ar)
        if self.cap_on:
            om_ = float(self.tab_cap(S["sig"][r])) * S["wbd"][r]
            if om_ > 0.0:
                H = self.H[r]
                yc = S["y_c"][r]
                sy = yc / max(self.y_root[r], 1e-9)
                Yb = sy * Y0[r, jB:root + 1]
                dd = np.maximum(ac - Anew, 0.0)
                fcap = 1.0 - om_ * (1.0 - MD.smoothstep(dd / max(self.cap_D_over_H * H, 1e-6)))
                Yrow[jB:root + 1] = yc - (yc - Yb) * fcap
        Arow[jB:root + 1] = Anew
        Arow[:jB + 1] = A0[r, 0] + self.fb[r] * (Arow[jB] - A0[r, 0])
        # 背の足の列 j_B の高さは 0（ds28 の _back の約束。E の _back は頂の帽子を j_B から掛け直すので、帽子の重み ω が 0 の時（ds28 の
        # 高さ 0）と正の時（K* の j_B の高さ sy·Y*）で跳ぶ。古い K* は j_B の高さが 0 で跳ばなかったが、K*′ の小さい行は 0.16〜0.22 m で、
        # 帽子が終わる時刻に足が跳んだ（開発の試し：R1 の行 22・235・236、240 Hz の二階差分 0.09〜0.21 m）。t* の K*′ の高さは num_tstar_exact）
        Yrow[jB] = 0.0
        return int(bool(np.any(Lt + w * d > cap_ + 1e-12)))

    def apply_delip(self, rows):
        """small_lip_body：指定の行の唇の強さ κ を 0 にする（本体の模型で動かす）。前に差し替えた行は E の値へ戻してから。
        num_no_rebound_after_apex の格子は、差し替えの後に作り直して読む（生成の中で行う）。"""
        for r, kv in getattr(self, "_delip_kappa0", {}).items():
            self.kappa[r] = kv
        self._delip_kappa0 = {}
        for r in rows:
            r = int(r)
            if r in self.lip and float(self.kappa[r]) > 0.0:
                self._delip_kappa0[r] = float(self.kappa[r])
                self.kappa[r] = 0.0
        self._delip_rows = sorted(self._delip_kappa0)
        return self._delip_rows

    def load_no_rebound(self, cache):
        """num_no_rebound_after_apex の格子を読み直す（作り直した格子。F の層の前の section_y で作ったもの）。"""
        if self._nr_deferred:
            return self.enable_no_rebound(cache)
        f = self._f_ready
        self._f_ready = False
        try:
            self._no_rebound_setup(cache)
        finally:
            self._f_ready = f

    # ------------------------------------------------------------ 準備
    def enable_no_rebound(self, cache):
        """num_no_rebound_after_apex の格子（cache。E と同じ、F の層の前の section_y、120 Hz）を読む（無ければこのプロセスで作る）。
        defer_no_rebound=True で作った生成器には、別のプロセスで作った格子を渡す。E の変種の文字列も E の既定の作りと同じに戻す。"""
        if not self._nr_deferred:
            return
        self.d_on["no_rebound"] = True
        self.d_off = tuple(n for n in self.d_off if n != "no_rebound")
        self.e_off = tuple(n for n in self.e_off if n != "no_rebound")
        f = self._f_ready
        self._f_ready = False
        try:
            self._no_rebound_setup(cache)
        finally:
            self._f_ready = f
        v = self.variant_e.replace("-off[no_rebound]", "").replace("-offE[no_rebound]", "")
        if "back_hold]" in v:
            v = v.replace("back_hold]", "back_hold,no_rebound]")
        self.variant_e = v
        self._nr_deferred = False
        self._set_variant()

    def nr_grid_taus(self):
        NR = self.RD["no_rebound"]
        hz = float(NR["grid_hz"])
        n = int(round(-float(NR["tau_start"]) * hz))
        return np.round(-np.arange(n, -1, -1) / hz, 9)

    def nr_grid_row(self, tau):
        """num_no_rebound_after_apex の格子の 1 こま（E の _no_rebound_setup と同じ値：F の層の前の section_y の Y[行, 列]）。"""
        rows, j0, j1 = self._nr_region()
        f = self._f_ready
        self._f_ready = False
        try:
            A, Y, _ = self.section_y(float(tau))
        finally:
            self._f_ready = f
        return Y[np.array(rows, int), j0:j1 + 1]

    def _landmark_tip(self):
        idx = ((self.K.src.get("meta") or {}).get("profile") or {}).get("index") or {}
        return int(idx.get("j_tip", self.RF["kstar"]["j_tip_default"]))

    def _f_setup(self):
        K = self.K
        nv = K.nv
        self.j_tip = self._landmark_tip()
        AK, YK = K.A, K.Y_full
        # num_tstar_exact：t* の差（F の層の前の E(0)）
        f = self._f_ready
        self._f_ready = False
        try:
            A0, Y0, _ = self.section_y(0.0)
        finally:
            self._f_ready = f
        self._R_A = AK - A0
        self._R_Y = YK - Y0
        yc0 = np.asarray(self.crest(0.0)[1], float)
        self._res_yc0 = yc0
        self._res_row_ok = yc0 > 0.05
        self._res_stats = dict(max_m=float(np.hypot(self._R_A, self._R_Y).max()), vertices_gt_1mm=int((np.hypot(self._R_A, self._R_Y) > 1e-3).sum()),
                               rows=sorted(int(r) for r in np.nonzero(np.hypot(self._R_A, self._R_Y).max(1) > 1e-3)[0]))
        # num_sheet_clearance：行ごとの基準（t* の K*′ の隙間 → g・w）
        SC = self.RF["sheet_clearance"]
        self._sc_prm = dict(share=float(SC["share"]), deep_full_m=float(SC["deep_full_m"]), deep_zero_m=float(SC["deep_zero_m"]),
                            k_tip=int(SC["k_tip"]), iters=int(SC["iters"]), smooth_cols=int(SC.get("smooth_cols", 0)))
        self._sc_ref = {}
        self._sc_back_only = bool(SC.get("back_moves_alone", True))
        Hk = YK.max(1)
        for r in range(nv):
            if not self.has_body[r] or Hk[r] < float(SC["row_min_H_m"]):
                continue
            (iu, cu, _, _, _), (il, cl, _, _, _) = CL.signed_clearance(AK[r], YK[r], self.j_tip, self.jB, self.jE, self._sc_prm["k_tip"])
            gU, wU = CL.gw_from_ref(cu, float(SC["gap_max_m"]), float(SC["soft_max_m"]), float(SC["gap_frac_of_tstar"]),
                                    float(SC["soft_frac_of_tstar"]), float(SC["min_tstar_clearance_m"]))
            gL, wL = CL.gw_from_ref(cl, float(SC["gap_max_m"]), float(SC["soft_max_m"]), float(SC["gap_frac_of_tstar"]),
                                    float(SC["soft_frac_of_tstar"]), float(SC["min_tstar_clearance_m"]))
            self._sc_ref[r] = (gU, wU, gL, wL)
        self._sc_last = dict(max_push_m=0.0, rows=0)

    def set_layers(self, **kw):
        """F の層を入れる・切る（検査・P20 の比べ用。生成器は作り直さない）。例：set_layers(bridge=False)"""
        for k, v in kw.items():
            if k not in F_NAMES:
                raise ValueError(k)
            self.f_layers[k] = bool(v) and self.f_on[k]
        self._set_variant()

    def set_guard_window(self, path):
        """num_sheet_clearance を働かせる行と時間の窓（生成の中の走査で、E のままの形にもつれがある行・時刻から決める）。
        ファイル：rows（行）、t0・t1（全部の重みの区間）、ramp（前後のなめらかな立ち上がりの長さ）。窓の外の行・時刻では何もしない。"""
        if path is None:
            self._gw = None
            self._gw_sha = None
            self._set_variant()
            return
        z = np.load(path)
        W = {}
        for r, a, b, rp in zip(z["rows"].astype(int), z["t0"], z["t1"], z["ramp"]):
            W.setdefault(int(r), []).append((float(a), float(b), float(rp)))
        self._gw = W
        self._gw_sha = MD.sha256_file(path)
        self._gw_path = path
        self._set_variant()

    def guard_weight(self, r, tau):
        """行 r・時刻 τ の num_sheet_clearance の重み（窓の中 1、前後 ramp の間に smootherstep で 0 へ。窓がない時は全部 1）。"""
        if self._gw is None:
            return 1.0
        w = 0.0
        for a, b, rp in self._gw.get(r, ()):
            if a <= tau <= b:
                return 1.0
            if tau < a:
                w = max(w, float(s5(1.0 - (a - tau) / rp)))
            else:
                w = max(w, float(s5(1.0 - (tau - b) / rp)))
        return w

    def set_bridge(self, path):
        z = np.load(path)
        rows = z["rows"].astype(int)
        B = {}
        for k, r in enumerate(rows):
            B.setdefault(int(r), []).append(dict(t0=float(z["t0"][k]), t1=float(z["t1"][k]), A0=z["A0"][k], Y0=z["Y0"][k], VA0=z["VA0"][k],
                                                 VY0=z["VY0"][k], A1=z["A1"][k], Y1=z["Y1"][k], VA1=z["VA1"][k], VY1=z["VY1"][k]))
        self._bridge = B
        self._bridge_sha = MD.sha256_file(path)
        self._bridge_path = path
        self._set_variant()

    def _set_variant(self):
        tags = [n for n in F_NAMES if self.f_layers.get(n)]
        if self.f_layers.get("bridge") and self._bridge is None:
            tags = [t for t in tags if t != "bridge"] + ["bridge(未設定)"]
        if self.f_layers.get("sheet_clearance") and self._gw is None:
            tags = [t if t != "sheet_clearance" else "sheet_clearance(窓なし)" for t in tags]
        self.variant = self.variant_e + "+ds28r01f[%s]" % ",".join(tags) if hasattr(self, "variant_e") else self.variant

    # ------------------------------------------------------------ F の層
    def res_scale(self, tau):
        """num_tstar_exact の係数 s(τ) = clip(y_c,m(τ)/y_c,m(0), 0, 1)^p（主断面 m の頂の高さの割合。全行で同じ）。
        （行ごとの頂の高さの割合は、小さい行で頂の検出が 2 つの山の間を跳び、足の列の差 R が跳んだ（開発の試し：行 22・235・236 の列 18、
        240 Hz の二階差分 0.09〜0.21 m。節点の適応が収束しない原因）ので使わない）"""
        if tau >= 0.0:
            return np.ones(self.K.nv)
        m = int(self.K.main_row)
        yc = float(np.asarray(self.crest(float(tau))[1], float)[m])
        p = float(self.RF["tstar_exact"]["exponent"])
        s = min(max(max(yc, 0.0) / max(float(self._res_yc0[m]), 1e-6), 0.0), 1.0) ** p
        return np.full(self.K.nv, s)

    def f_apply(self, tau, A, Y, layers=None):
        L = self.f_layers if layers is None else layers
        A = A.copy()
        Y = Y.copy()
        if L.get("tstar_exact"):
            s = self.res_scale(tau)
            A += s[:, None] * self._R_A
            Y += s[:, None] * self._R_Y
        if L.get("sheet_clearance"):
            mv = 0.0
            nr_ = 0
            rows = self._sc_ref.keys() if self._gw is None else [r for r in self._gw if r in self._sc_ref]
            for r in rows:
                w = self.guard_weight(r, tau)
                if w <= 0.0:
                    continue
                A2, Y2, m, n = CL.apply_row(A[r], Y[r], self.j_tip, self.jB, self.jE, self._sc_ref[r], self._sc_prm,
                                            root=int(self.root[r]) if self._sc_back_only else None)
                if m > 0.0:
                    A[r] = A[r] + w * (A2 - A[r])
                    Y[r] = Y[r] + w * (Y2 - Y[r])
                    mv = max(mv, w * m)
                    nr_ += 1
            self._sc_last = dict(max_push_m=mv, rows=nr_)
        if L.get("bridge") and self._bridge:
            for r, ivs in self._bridge.items():
                for iv in ivs:
                    if iv["t0"] < tau < iv["t1"]:
                        h = iv["t1"] - iv["t0"]
                        u = (tau - iv["t0"]) / h
                        h00 = 2 * u ** 3 - 3 * u ** 2 + 1
                        h10 = u ** 3 - 2 * u ** 2 + u
                        h01 = -2 * u ** 3 + 3 * u ** 2
                        h11 = u ** 3 - u ** 2
                        A[r] = h00 * iv["A0"] + h10 * h * iv["VA0"] + h01 * iv["A1"] + h11 * h * iv["VA1"]
                        Y[r] = h00 * iv["Y0"] + h10 * h * iv["VY0"] + h01 * iv["Y1"] + h11 * h * iv["VY1"]
                        break
        return A, Y

    # ------------------------------------------------------------ num_balance_swell_calm（仕上げ27：関門 P2・P3）
    def sea(self, tau, A, Y, diag=False):
        """海（層1）。num_balance_swell_calm が切りなら設計27 の式そのもの（ds27_model.Generator.sea）。
        入りのとき、搬送波の振幅 A_c,r(τ) を解く窓の釣り合いの、うねりの項（窓のうねり Sw − 本体が置き換えるうねり srepl）に、出力の海と同じ
        うねりを静める係数 κ_s(τ) を掛ける：areaB ＋ κ_s·(Sw − srepl) ＋ A_c·(Cw − repl) = 0（設計27 の式は κ_s = 1 で解き、出力だけ κ_s を掛けていた。
        設計27 §3.4 の P2 の原因 (2)）。κ_c（ds_sea_calm_painting）は釣り合いに入れない（ds28r01f_params.json の balance_swell_calm）。
        この差し替えのほかは設計27 の式と同じ行（振幅の上限・行の方向の平滑・頂点の海・記録の窓の断面積）。"""
        if not getattr(self, "_bal_ks_on", False):
            return ME.Generator.sea(self, tau, A, Y, diag=diag)
        K = self.K
        nv = K.nv
        O_tau = self.origin(tau)
        kc, ks = self.calm_factors(tau)
        W = self.world_xz(tau, A)
        car, swl = self.car, self.swl
        Abal = np.full(nv, np.nan)
        res = np.zeros(nv)
        apos = np.zeros(nv)
        for r in range(nv):
            a_bf, a_ff = A[r, self.jB], A[r, self.jE]
            wb = self.w_body[r] if self.has_body[r] else 0.0
            a_top = A[r, int(self.root[r])] if self.has_body[r] else 0.0
            a0w, a1w = a_top - self.win_half, a_top + self.win_half
            Cw = self.line_integral(car, O_tau, K.c[r], a0w, a1w, tau)
            Sw = self.line_integral(swl, O_tau, K.c[r], a0w, a1w, tau)
            if wb > 0:
                core = self.line_integral(car, O_tau, K.c[r], a_bf, a_ff, tau)
                ab = np.linspace(self.sheet_a0, a_bf, self.n_marg)
                af = np.linspace(a_ff, self.sheet_a1, self.n_marg)
                am = np.concatenate([ab, af])
                wm = self.margin_weight(am, a_bf, a_ff)
                P3 = O_tau[None, :] + K.c[r] * K.e[None, :] + am[:, None] * K.t[None, :]
                cm = self.field(car, P3[:, 0], P3[:, 2], tau)
                marg = np.trapezoid(wm[:self.n_marg] * cm[:self.n_marg], ab) + np.trapezoid(wm[self.n_marg:] * cm[self.n_marg:], af)
                repl = wb * (core + marg)
                if self.swell_repl:
                    core_s = self.line_integral(swl, O_tau, K.c[r], a_bf, a_ff, tau)
                    sm_ = self.field(swl, P3[:, 0], P3[:, 2], tau)
                    marg_s = np.trapezoid(wm[:self.n_marg] * sm_[:self.n_marg], ab) + np.trapezoid(wm[self.n_marg:] * sm_[self.n_marg:], af)
                    srepl = wb * (core_s + marg_s)
                else:
                    srepl = 0.0
            else:
                repl = 0.0
                srepl = 0.0
            areaB = float(np.sum((A[r, 1:] - A[r, :-1]) * (Y[r, 1:] + Y[r, :-1]) / 2.0))
            Rr = repl - Cw
            if wb > 0:
                ab = max(areaB + ks * (Sw - srepl), 0.0) * max(Rr, 0.0) / (Rr * Rr + self.R_min ** 2)     # ← 仕上げ27：κ_s を掛けた
                if self.cap_pow > 0:
                    Abal[r] = float(ab / (1.0 + (ab / self.Ac_max) ** self.cap_pow) ** (1.0 / self.cap_pow))
                else:
                    Abal[r] = float(self.Ac_max * math.tanh(ab / self.Ac_max))
        raw = np.where(np.isfinite(Abal), Abal, 0.0) * np.where(self.has_body, self.w_body, 0.0)
        Ac = self.Ac_smooth @ raw
        wv = np.ones_like(A)
        for r in range(nv):
            wb = self.w_body[r] if self.has_body[r] else 0.0
            wm = self.margin_weight(A[r], A[r, self.jB], A[r, self.jE])
            wm[self.jB:self.jE + 1] = 1.0
            wv[r] = wb * wm
        need = (1.0 - wv) > 1e-12
        Cv = np.zeros_like(A)
        if need.any():
            Cv[need] = self.field(car, W[..., 0][need], W[..., 1][need], tau)
        Sv = self.field(swl, W[..., 0], W[..., 1], tau)
        ws = (1.0 - wv) if self.swell_repl else 1.0
        Ynew = Y + (1.0 - wv) * kc * Ac[:, None] * Cv + ks * ws * Sv
        if diag:
            for r in range(nv):
                a_top = A[r, int(self.root[r])] if self.has_body[r] else 0.0
                a0w, a1w = a_top - self.win_half, a_top + self.win_half
                yph = Y[r] + (1.0 - wv[r]) * Ac[r] * Cv[r] + ((1.0 - wv[r]) if self.swell_repl else 1.0) * Sv[r]
                area_sheet = float(np.sum((A[r, 1:] - A[r, :-1]) * (yph[1:] + yph[:-1]) / 2.0))
                outb = Ac[r] * self.line_integral(car, O_tau, K.c[r], a0w, A[r, 0], tau) + self.line_integral(swl, O_tau, K.c[r], a0w, A[r, 0], tau)
                outf = Ac[r] * self.line_integral(car, O_tau, K.c[r], A[r, -1], a1w, tau) + self.line_integral(swl, O_tau, K.c[r], A[r, -1], a1w, tau)
                res[r] = area_sheet + outb + outf
                apos[r] = float(np.sum(np.clip((A[r, 1:] - A[r, :-1]) * (np.clip(yph[1:], 0, None) + np.clip(yph[:-1], 0, None)) / 2.0, None, None)))
            return Ynew, dict(Ac=Ac, Abal=Abal, A_net=res, A_pos_sheet=apos, kc=kc, ks=ks, wv=wv, balance_swell_calm=True)
        return Ynew, dict(Ac=Ac, kc=kc, ks=ks)

    def section_y(self, tau, diag=False):
        A, Y, d = ME.Generator.section_y(self, tau, diag=diag)
        if not getattr(self, "_f_ready", False):
            return A, Y, d
        A, Y = self.f_apply(float(tau), A, Y)
        return A, Y, d

    def section_y_layers(self, tau, layers):
        """層を指定した section_y（検査・P20・橋渡しの走査の中で使う）。"""
        f = self._f_ready
        self._f_ready = False
        try:
            A, Y, d = ME.Generator.section_y(self, float(min(tau, 0.0)))
        finally:
            self._f_ready = f
        A, Y = self.f_apply(float(min(tau, 0.0)), A, Y, layers)
        return A, Y, d

    # ------------------------------------------------------------ 記録
    def summary(self):
        s = ME.Generator.summary(self)
        s.update(number="設計28修正01 試行F",
                 ds28r01f=dict(on=self.f_on, layers=self.f_layers, off=list(self.f_off), params_sha256=self.f_sha, base_sha256=self.f_base_shas,
                               j_tip=int(self.j_tip), tstar_residual=self._res_stats, tail_lip_body_rows=list(self._tail_rows),
                               small_lip_body_rows=list(getattr(self, "_delip_rows", [])),
                               back_width_retarget=getattr(self, "_rho_w_src", None), sheet_clearance_rows=len(self._sc_ref),
                               anchor_retarget=getattr(self, "_anc_rt", None),
                               far_hook_early=(dict(rows=[int(r) for r in np.nonzero(self._hook_mask)[0]],
                                                    sigma=[float(self.RF["far_hook_early"]["sigma_start"]), float(self.RF["far_hook_early"]["sigma_end"])])
                                               if getattr(self, "_hook_mask", None) is not None else None),
                               bridge_sha256=self._bridge_sha, guard_window_sha256=self._gw_sha,
                               guard_window={str(r): [[round(a, 4), round(b, 4), round(rp, 3)] for a, b, rp in v] for r, v in self._gw.items()}
                               if self._gw else None,
                               bridge_rows=sorted(self._bridge) if self._bridge else [],
                               bridge_intervals=({str(r): [[round(iv["t0"], 4), round(iv["t1"], 4)] for iv in ivs] for r, ivs in self._bridge.items()}
                                                 if self._bridge else {})))
        return s
