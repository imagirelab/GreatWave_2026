# -*- coding: utf-8 -*-
"""FLIP42 R2 の段の独立の確かめ（入口と減り）：A1（帯の出口の 3 つの帯域・測った S）と B1（エネルギーの流れの減り）を、
計画 §5 と「計画の読み方」3・4 の定義のまま自前で計算し直す。加えて、読み方の細部（測る点の補間、窓）を変えた時の幅を見る。
入口の式は g_tanklib.py の文（η = Σ a cos(k_i(x − x_p − x_b) − ω_i(t − t_b))、a = S/Σk、ramp 0.5 − 0.5 cos(π t/R)、g 9.80665）。
g_analyze.py は使わない。使い方：py -3.10 check_R2_spec.py   出力：check_R2_spec.json
"""
import json, sys
import numpy as np
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/check/R2")
import check_R2_geom as G

g = 9.80665
H0 = 42.0


def k_of_f(f):
    f = np.atleast_1d(np.asarray(f, float))
    w = 2 * np.pi * f
    k = np.where(f > 0, w * w / g, 0.0)
    for _ in range(60):
        th = np.tanh(k * H0)
        F = g * k * th - w * w
        dF = g * th + g * k * H0 * (1 - th * th)
        k = np.where(f > 0, k - F / np.where(dF > 0, dF, 1.0), 0.0)
    return k


def cg_of_f(f):
    k = k_of_f(f)
    w = 2 * np.pi * np.asarray(f, float)
    c = np.where(k > 0, w / np.where(k > 0, k, 1), 0)
    kh = k * H0
    n = 0.5 * (1 + np.where(kh > 0, 2 * kh / np.sinh(np.where(kh > 0, 2 * kh, 1)), 1))
    return n * c


def main():
    cfg = json.load(open(G.RUNS + "/R3/cfg.json", encoding="utf-8"))
    P = cfg["parms"]
    N = int(P["ncomp"]); fc = P["fc"]; dff = P["dff"]; S = P["S"]
    fmin, fmax = fc * (1 - dff / 2), fc * (1 + dff / 2)
    fi = np.linspace(fmin, fmax, N)
    ki = k_of_f(fi)
    a = S / ki.sum()
    xb, tb, R = P["x_b"], P["t_b"], P["ramp_s"]
    delta = fi[1] - fi[0]
    fps = 24.0
    nwin = 4508
    t = np.arange(nwin) / fps
    ramp = np.where(t < R, 0.5 - 0.5 * np.cos(np.pi * np.clip(t / R, 0, 1)), 1.0)
    etap = ramp * np.sum(a * np.cos(ki[:, None] * xb + 2 * np.pi * fi[:, None] * (t[None, :] - tb)), axis=0)
    npad = 2 ** 17
    sp = np.fft.rfft(etap, npad)
    fp = np.fft.rfftfreq(npad, 1 / fps)
    kp = k_of_f(fp)

    def lin_at(X):
        return np.fft.irfft(sp * np.exp(-1j * kp * X), npad)[:nwin]

    gauges = cfg["case"]["gauges"]
    res = dict(a=float(a), fmin=fmin, fmax=fmax, delta=float(delta), check_paddle_peak=float(etap.max()))
    fw = np.fft.rfftfreq(nwin, 1 / fps)
    kw = k_of_f(fw); cgw = cg_of_f(fw)
    inband = (fw >= fmin - delta / 2) & (fw <= fmax + delta / 2)

    def subband(Fm, Fl, i0, i1):
        sel = (fw >= fi[i0 - 1] - delta / 2) & (fw <= fi[i1 - 1] + delta / 2)
        Rr = Fm[sel] / Fl[sel]
        w = np.abs(Fl[sel]) ** 2
        return dict(nbins=int(sel.sum()), amp=float(np.sum(w * np.abs(Rr)) / w.sum()),
                    phase=float(np.sum(w * np.angle(Rr)) / w.sum()),
                    amp_energy=float(np.sqrt(np.sum(np.abs(Fm[sel]) ** 2) / np.sum(np.abs(Fl[sel]) ** 2))))

    for run in ["R3", "R2", "R1b"]:
        hf = G.load_hf(run)
        L = json.load(open(G.OUT + "/check_R2_geom.json", encoding="utf-8"))[run]["level"]
        assert len(hf["t"]) == nwin and abs(hf["t"][-1] - t[-1]) < 1e-6
        out = {}
        for variant in ["interp3", "nearest3", "mid"]:
            def rec(xs):
                x = hf["x"]; dx = x[1] - x[0]
                if variant == "nearest3":
                    i = int(round(xs / dx)); v = np.nanmean(hf["eta3"][:, :, i], axis=1)
                else:
                    i = int(np.floor(xs / dx)); w = (xs - x[i]) / dx
                    if variant == "interp3":
                        v = np.nanmean((1 - w) * hf["eta3"][:, :, i] + w * hf["eta3"][:, :, i + 1], axis=1)
                    else:
                        v = (1 - w) * hf["eta"][:, i] + w * hf["eta"][:, i + 1]
                return v - L
            Fl, Fm = {}, {}
            for name, xs in gauges.items():
                X = xs - G.X_P
                Fl[name] = np.fft.rfft(lin_at(X))
                Fm[name] = np.fft.rfft(rec(xs))
            be = "band_exit"
            A1 = [subband(Fm[be], Fl[be], 1, 11), subband(Fm[be], Fl[be], 12, 21), subband(Fm[be], Fl[be], 22, 32)]
            Smeas = S * np.sum(kw[inband] * np.abs(Fm[be][inband])) / np.sum(kw[inband] * np.abs(Fl[be][inband]))
            flux = {n: float(np.sum(np.abs(Fm[n][inband]) ** 2 * cgw[inband]) / np.sum(np.abs(Fl[n][inband]) ** 2 * cgw[inband])) for n in gauges}
            B1 = 1 - flux["kc(x-xb)=-10"] / flux["band_exit"]
            out[variant] = dict(A1=A1, S=float(Smeas), flux=flux, B1=float(B1))
            # 窓の 0〜139 s（R3b と比べた窓）
            if variant == "interp3":
                n139 = int(139 * fps) + 1
                fw2 = np.fft.rfftfreq(n139, 1 / fps)
                Fm2 = np.fft.rfft(rec(gauges[be])[:n139]); Fl2 = np.fft.rfft(lin_at(gauges[be] - G.X_P)[:n139])
                sel = (fw2 >= fi[21] - delta / 2) & (fw2 <= fi[31] + delta / 2)
                Rr = Fm2[sel] / Fl2[sel]; w = np.abs(Fl2[sel]) ** 2
                out["A1_22_32_0_139s"] = float(np.sum(w * np.abs(Rr)) / w.sum())
        res[run] = out
        print(run, json.dumps(out["interp3"]["A1"]), "S", round(out["interp3"]["S"], 4), "B1", round(out["interp3"]["B1"], 4),
              {k: round(v, 3) for k, v in out["interp3"]["flux"].items()})
        for v in ["nearest3", "mid"]:
            print("   ", v, [round(s["amp"], 4) for s in out[v]["A1"]], round(out[v]["S"], 4), round(out[v]["B1"], 4))
        print("   amp_energy", [round(s["amp_energy"], 4) for s in out["interp3"]["A1"]], "0-139s 22-32:", round(out["A1_22_32_0_139s"], 4))
    json.dump(res, open(G.OUT + "/check_R2_spec.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main()
