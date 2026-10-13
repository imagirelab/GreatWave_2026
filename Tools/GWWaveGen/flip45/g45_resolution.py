# -*- coding: utf-8 -*-
"""FLIP45：細かさ・時間の刻み・窓・横の帯の位置の比べ（py -3.10。計画 plan_ja.md §6.7・§6.8・§6.10）。各計算の ana.json（g45_analyze.py）を読むだけ。
2026-10-12 進行役が新しく書いた。
  compare(a, b)        C1〜C5（§6.7）：巻き始めの時刻 ±0.1 T（0.70 s）・場所 ±0.1 λ（7.2 m）、Ac・H1 ±5 %、前の面の険しさ ±10 %、
                       噴流（巻き始めから着水までの時間と距離）±10 %、ℓ ±5 %。元は b（細かい方か刻みの小さい方）。巻かなかった時は
                       最も険しくなったコマの量で比べる（§6.8 の最後）。
  window_decision()    §6.8：V2 − V1 が巻き始めの時刻 ±0.70 s・場所 ±7.2 m・Ac と H1 ±5 %・ℓ ±5 % に全部入れば並び A、一つでも外れれば並び B。
                       runs/SEQ_DECISION.json に書く。
  side_band()          §6.10：V4 − V1（同じ 5 つの量）。
  gci3(...)            3 段（0.5・0.34375・0.25 m）の観察の次数と GCI（Celik ら 2008。安全率 1.25）。差が単調に縮まない量は出さない。
使い方：py -3.10 g45_resolution.py <a> <b> [runs]    （a と b の比べを表示）
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC

T = GC.T; LAM = GC.L0


def ana(rid, root="runs"):
    p = os.path.join(GC.B45, root, rid, "ana.json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else None


def quantities(a):
    on = a.get("onset")
    if on:
        td = a.get("touchdown") or {}
        return dict(kind="onset", t=on["t"], x=on["xc"], Ac=on["eta_c"], H1=on.get("H1"), ell=(a.get("ell") or {}).get("width"),
                    steep=on.get("front_steepness"), jet_t=td.get("jet_time_s"), jet_d=td.get("jet_dist_m"))
    st = a.get("steepest")
    if st:
        return dict(kind="steepest", t=st["t"], x=st["xc"], Ac=st["eta_c"], H1=st.get("H1"), ell=None, steep=None, jet_t=None, jet_d=None)
    return None


def _rel(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b - 1.0


def compare(a, b, five_only=False):
    """a を b（元）と比べる。返り値 dict(rows, all_inside)。"""
    qa, qb = quantities(a), quantities(b)
    if qa is None or qb is None:
        return dict(note="比べる量がない（%s・%s）" % (bool(qa), bool(qb)), all_inside=False)
    rows = {}
    rows["C1_t"] = dict(a=qa["t"], b=qb["t"], diff=qa["t"] - qb["t"], tol=0.1 * T, inside=abs(qa["t"] - qb["t"]) <= 0.1 * T)
    rows["C1_x"] = dict(a=qa["x"], b=qb["x"], diff=qa["x"] - qb["x"], tol=0.1 * LAM, inside=abs(qa["x"] - qb["x"]) <= 0.1 * LAM)
    for k, tol, nm in (("Ac", 0.05, "C2_Ac"), ("H1", 0.05, "C2_H1"), ("ell", 0.05, "C5_ell"), ("steep", 0.10, "C3_steep"),
                       ("jet_t", 0.10, "C4_jet_t"), ("jet_d", 0.10, "C4_jet_d")):
        r = _rel(qa[k], qb[k])
        rows[nm] = dict(a=qa[k], b=qb[k], rel=r, tol=tol, inside=(r is not None and abs(r) <= tol))
    keys5 = ["C1_t", "C1_x", "C2_Ac", "C2_H1", "C5_ell"]
    use = keys5 if five_only else list(rows)
    use = [k for k in use if not (rows[k].get("b") is None)]
    return dict(rows=rows, kind=(qa["kind"], qb["kind"]), all_inside=bool(use and all(rows[k]["inside"] for k in use)), used=use)


def window_decision(root="runs"):
    v1, v2 = ana("V1", root), ana("V2", root)
    if not v1 or not v2:
        res = dict(sequence="B", why_ja="V1 か V2 の解析がない（V2 を走らせなかった）ので並び B（計画 §6.8）")
    else:
        c = compare(v2, v1, five_only=True)
        res = dict(sequence="A" if c["all_inside"] else "B", compare=c,
                   why_ja="V2 − V1 が巻き始めの時刻 ±0.70 s・場所 ±7.2 m・Ac と H1 ±5 %%・ℓ ±5 %% に%s（計画 §6.8）" % ("全部入った" if c["all_inside"] else "入らない量があった"))
    json.dump(res, open(os.path.join(GC.B45, root, "SEQ_DECISION.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return res


def side_band(root="runs"):
    v1, v4 = ana("V1", root), ana("V4", root)
    if not v1 or not v4:
        return dict(note="V1 か V4 の解析がない")
    c = compare(v4, v1, five_only=True)
    return dict(compare=c, sentence_ja=("横の帯の位置（72 m と 108 m）はこの 5 つの量を動かさなかった（粒子 0.5 m）" if c["all_inside"]
                                        else "横の帯の位置で量が動いた：X60・X45 と F45 の比べの横に V4 − V1 の差を並べ、M1w を走らせるかを利用者に伺う（計画 §6.10）"))


def gci3(f1, f2, f3, h1, h2, h3, Fs=1.25):
    """Celik ら 2008 の 3 段の手順。f1 が最も細かい。返り値 dict（p・外挿の値・GCI_fine）か、単調でない時は理由。"""
    e21 = f2 - f1; e32 = f3 - f2
    if e21 == 0 or e32 == 0 or (e32 / e21) <= 0:
        return dict(note="差が単調に縮まない（e32/e21 = %s）ので GCI を出さない" % (None if e21 == 0 else e32 / e21))
    r21 = h2 / h1; r32 = h3 / h2
    s = 1.0 if e32 / e21 > 0 else -1.0
    p = 1.0
    for _ in range(100):
        q = math.log((r21 ** p - s) / (r32 ** p - s))
        p_new = abs(math.log(abs(e32 / e21)) + q) / math.log(r21)
        if abs(p_new - p) < 1e-10:
            break
        p = p_new
    f_ext = (r21 ** p * f1 - f2) / (r21 ** p - 1)
    ea = abs((f1 - f2) / f1) if f1 else float("nan")
    gci = Fs * ea / (r21 ** p - 1)
    return dict(p=p, f_ext=f_ext, e_a21=ea, GCI_fine=gci)


def three_level(root="runs", seq="B"):
    names = dict(A=["V2", "M1c_L2", "M1_L2"], B=["V1", "M1c_L1", "M1_L1"])[seq]
    A_ = [ana(n, root) for n in names]
    if not all(A_):
        return dict(note="3 段の解析がそろっていない（%s）" % names)
    h = [0.5, 0.34375, 0.25]
    Q = [quantities(a) for a in A_]
    out = {}
    for k in ("x", "Ac", "H1", "ell", "t"):
        v = [q[k] for q in Q]
        if None in v:
            out[k] = dict(note="値がない"); continue
        out[k] = dict(values=v, **gci3(v[2], v[1], v[0], h[2], h[1], h[0]))
    return dict(runs=names, h=h, results=out, note_ja="粒子 0.5 m は方法の確かめの範囲の外なので、3 段の結果は目安として書く（計画 §6.7）")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a, b = sys.argv[1], sys.argv[2]
    root = sys.argv[3] if len(sys.argv) > 3 else "runs"
    print(json.dumps(compare(ana(a, root), ana(b, root)), ensure_ascii=False, indent=1, default=float))
