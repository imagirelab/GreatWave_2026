# -*- coding: utf-8 -*-
"""1. R3 の記録から自分で線を取り、頂・巻き始め・最初の接触・唇・船の上下と縦揺れを自分で出す（3319〜3889 コマ）。
出力：out/my_r3_frames.npz（自分の線）、out/k_r3.json（数）"""
import time
import numpy as np
from k_lib import *

t0 = time.time()
rec = R3Rec()
n_multi, n_diff = rec.overlap_check()
print("overlap: frames-with-2-records", n_multi, "differ", n_diff, f"{time.time()-t0:.1f}s")

frames, rows = {}, []
xprev = 261.53670245673754 - 0.0   # 計画の 3319 コマの巻く頂（plan_numbers.json）。自分のたどりの始め
onset = contact = None
lipmax = None
for f in range(F0, F1 + 1):
    d = frame_curves(rec, f)
    P = d["main"]
    ic = crest_index(P, xprev)
    xc, yc = P[ic]
    xprev = xc
    ang, xv = front_overturn(P, ic)
    air = [L for L in d["loops"] if L["phase"] == 1 and L["area"] >= 0.25 and abs(L["pts"][:, 0].mean() - xc) <= 30.0]
    wat = [L for L in d["loops"] if L["phase"] == -1]
    lp = lip(P, ic) if onset is not None and contact is None else None
    if onset is None and ang >= 90.0:
        onset = dict(frame=f, t=t_of(f), x_vertical=xv, crest=(float(xc), float(yc)), ang=ang)
    if onset is not None and contact is None and len(air):
        contact = dict(frame=f, t=t_of(f), air_area=float(max(L["area"] for L in air)),
                       air_x=(float(min(L["pts"][:, 0].min() for L in air)), float(max(L["pts"][:, 0].max() for L in air))))
    if lp is not None and (lipmax is None or lp["reach"] > lipmax["reach"]):
        lipmax = dict(frame=f, t=t_of(f), **lp)
    b556 = boat_pose(P, 556.0); b574 = boat_pose(P, 574.0)
    rows.append(dict(frame=f, crest_x=float(xc), crest_y=float(yc), front_ang=ang, n_air=len([L for L in d["loops"] if L["phase"] == 1]),
                     n_water=len(wat), n_loops=len(d["loops"]), spans=d["spans"], n_other_open=d["n_other_open"], stitch=d["stitch"],
                     lip=lp, heave556=b556[0], pitch556=b556[1], heave574=b574[0], pitch574=b574[1]))
    frames[f] = dict(main=P, loops=d["loops"])
    if f % 50 == 0:
        print(f, f"{time.time()-t0:.1f}s", round(xc, 2), round(yc, 3), round(ang, 1))

save_frames(OUT + "/my_r3_frames.npz", frames)


# かぶさった水が船体に入る最初のコマ（最初の接触より後）：船体 ±6 m の鉛直の線が主な線と 3 回以上交わるか、水の閉じた線に当たる
def overturn_on_hull(seat):
    for f in range(contact["frame"] + 1, F1 + 1):
        P = frames[f]["main"]
        for xq in np.arange(seat - 6.0, seat + 6.0 + 1e-9, 0.25):
            if len(crossings_y(P, xq)) >= 3:
                return f, "main3"
            for L in frames[f]["loops"]:
                if L["phase"] == -1:
                    Q = np.vstack([L["pts"], L["pts"][:1]])
                    if len(crossings_y(Q, xq)) > 0:
                        return f, "water_loop"
    return None, None


ov = {str(s): overturn_on_hull(s) for s in (556.0, 574.0)}
sh = jload(R3 + "/shape.json")
res = dict(overlap=dict(frames_with_2_records=n_multi, differ=n_diff), XP=XP, OFF=OFF,
           onset=onset, contact=contact, lip_max_before_contact=lipmax, overturn_on_hull=ov,
           shape_json=dict(onset=dict(frame=sh["onset"]["frame"], x_vertical=sh["onset"]["vertical_x_rel"], crest=(sh["onset"]["xc_rel"], sh["onset"]["yc"])),
                           touchdown=dict(frame=sh["touchdown"]["frame"], cavity=sh["touchdown"].get("cavity"))),
           all_spans=all(r["spans"] for r in rows), max_other_open=max(r["n_other_open"] for r in rows),
           max_stitch=max(max(abs(r["stitch"][0]), abs(r["stitch"][1])) for r in rows),
           crest_max=max((r["crest_y"], r["frame"]) for r in rows if r["frame"] <= 3760),
           rows=rows, seconds=time.time() - t0)
jsave(OUT + "/k_r3.json", res)
print("onset", onset)
print("contact", contact)
print("lipmax", lipmax)
print("overturn", ov)
print("crest_max", res["crest_max"], "max_stitch", res["max_stitch"], "spans", res["all_spans"], "other_open", res["max_other_open"])
print(f"done {time.time()-t0:.1f}s")
