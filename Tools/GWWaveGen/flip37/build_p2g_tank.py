# -*- coding: utf-8 -*-
"""P2g 誘導の双子の水槽：P2 の版 3 の場面（Houdini/FLIP37/p2_tank.hiplc）を読み込み、誘導の力の場を 1 つ足して、
Houdini/FLIP37/p2g_tank.hiplc に保存する（hython 22.0.459）。P2 の場面は書き換えない。

足したもの（2026-10-06）：
- CTRL に誘導の値（g_amp ほか）。g_amp = 0 なら誘導の節は何もしない（誘導なしの双子）。
- DOP：relax_zones（波を吸う帯）の後ろに gasfieldwrangle「guide」を 1 つつないだ（FLIP Solver の同じ入力。
  格子の流速 vel に、上限付きの加速度 a を足すだけ：vel += a·dt。流速を目標で置き換える Guiding Velocity/Surface は使わない）。
- 誘導の形（提案 §3.5 の決まりの中）：
    a = -A · W(x, z, t) · v / max(|v|, v_ref)   （流れに逆らう弱い抵抗。|a| <= A·W <= g_amp·g <= 0.1 g）
    W = Wt(t) · Wz(z) · Wx(x - xc(t, z))
    Wt：g_t0 から g_ramp 秒で 1 へ、g_t1 - g_ramp から g_t1 で 0 へ（なめらかに）。g_t1 は t* の 1.0〜1.5 秒前。
    Wz：手前（z < 0）だけ。|z| が g_zin で 0、g_zfull で 1、g_zw0 から g_zw1 で 0（壁の手前で消す）。中央の巻く所（z > -g_zin）には当てない。
    Wx：頂の x の上のガウス（広がり g_sx）。頂の x の表 xc(t, z) は誘導なしの R18 の毎コマの頂（crest.npy）から作り、z と t でならした。
    深さ：Wy = smooth(g_y0, g_y1, y)（22:05 に足した。最初の G1 は水の柱の全部で、仕事が 5 % を超える見込みになったため、上の層だけにできるようにした）。
- 読み取り：P2_READ に vel の場の読み取り（OUT_VEL_FIELD）を足した（仕事と波のエネルギーの計算に使う）。
"""
import hou, os, sys, json
import numpy as np

SRC = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p2_tank.hiplc"
HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p2g_tank.hiplc"
R18 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2/R18_X30L120LG_H39"
CT = "/obj/P2_SETUP/CTRL/"

hou.hipFile.load(SRC, suppress_save_prompt=True, ignore_load_warnings=True)
ctrl = hou.node(CT)
ptg = ctrl.parmTemplateGroup()
GP = [
    ("g_amp", 0.0, "誘導の強さの上限（重力の何倍か。0＝誘導なし）"),
    ("g_vref", 2.0, "誘導：v_ref (m/s)（これより遅い流れには比例して弱く）"),
    ("g_t0", 4.0, "誘導の始まり t (s)"),
    ("g_t1", 9.0, "誘導が 0 になる t (s)"),
    ("g_ramp", 0.5, "誘導の上げ下げの長さ (s)"),
    ("g_zin", 10.0, "誘導：手前の |z| がこれより小さい所は 0"),
    ("g_zfull", 35.0, "誘導：手前の |z| がこれより大きい所で 1"),
    ("g_zw0", 104.0, "誘導：壁の手前で弱め始める |z|"),
    ("g_zw1", 116.0, "誘導：壁の手前で 0 になる |z|"),
    ("g_sx", 22.0, "誘導：頂の x の上のガウスの広がり (m)"),
    ("g_dx", 0.0, "誘導：頂の x からのずらし (m)（+ で岸の側）"),
    ("g_y0", -999.0, "誘導：高さ y がこれより下は 0（22:05 に足した。既定 -999＝水の柱の全部）"),
    ("g_y1", -998.0, "誘導：高さ y がこれより上で 1"),
]
for nm, dv, lb in GP:
    if ptg.find(nm) is None:
        ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
ctrl.setParmTemplateGroup(ptg)

# ---- 頂の x の表（R18、誘導なし）
c = np.load(os.path.join(R18, "crest.npy"))
fps = 24.0
TT = np.arange(3.5, 9.5001, 0.25)
ZC = np.arange(-115.0, 115.01, 10.0)
X = np.zeros((len(TT), len(ZC)))
for i, t in enumerate(TT):
    rows = []
    for df in (-6, -3, 0, 3, 6):
        f = int(round(t * fps)) + 1 + df
        rows.append(c[f - 1][3::3])
    X[i] = np.mean(rows, axis=0)
# z の 3 帯の中央値 → 3 帯の平均（端は端の値を延ばす。hython に scipy がないので numpy で）
Xp = np.pad(X, ((0, 0), (1, 1)), mode="edge")
X = np.median(np.stack([Xp[:, :-2], Xp[:, 1:-1], Xp[:, 2:]]), axis=0)
Xp = np.pad(X, ((0, 0), (1, 1)), mode="edge")
X = (Xp[:, :-2] + Xp[:, 1:-1] + Xp[:, 2:]) / 3.0
table = {"t": TT.tolist(), "z": ZC.tolist(), "x": X.round(2).tolist(), "src": R18 + "/crest.npy",
         "note": "R18 の毎コマ・10 m の z の帯ごとの最も高い粒子の x。±6 コマの平均、z の 3 帯の中央値と平均でならした"}
os.makedirs(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2g", exist_ok=True)
json.dump(table, open(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2g/guide_crest_table.json", "w"), indent=1)
arr = ", ".join("%.2f" % v for v in X.ravel())

GUIDE = r'''
#define GG 9.80665
#define CT "%s"
float XC[] = {%s};
int NT = %d; int NZ = %d;
float T0 = %.4f; float DT = %.4f; float Z0 = %.4f; float DZ = %.4f;
float A = chf(CT+"g_amp")*GG;
if (A > 0.0) {
    float t = f@Time;
    float t0 = chf(CT+"g_t0"); float t1 = chf(CT+"g_t1"); float rp = chf(CT+"g_ramp");
    float wt = smooth(t0, t0 + rp, t)*(1.0 - smooth(t1 - rp, t1, t));
    float u = -@P.z;
    float wz = smooth(chf(CT+"g_zin"), chf(CT+"g_zfull"), u)*(1.0 - smooth(chf(CT+"g_zw0"), chf(CT+"g_zw1"), u));
    if (wt > 0.0 && wz > 0.0) {
        float ft = clamp((t - T0)/DT, 0.0, NT - 1.0001); int it = int(floor(ft)); float at = ft - it;
        float fz = clamp((@P.z - Z0)/DZ, 0.0, NZ - 1.0001); int iz = int(floor(fz)); float az = fz - iz;
        float x00 = XC[it*NZ + iz]; float x01 = XC[it*NZ + iz + 1];
        float x10 = XC[(it + 1)*NZ + iz]; float x11 = XC[(it + 1)*NZ + iz + 1];
        float xc = lerp(lerp(x00, x01, az), lerp(x10, x11, az), at) + chf(CT+"g_dx");
        float sx = chf(CT+"g_sx");
        float wx = exp(-pow((@P.x - xc)/sx, 2.0));
        float wy = smooth(chf(CT+"g_y0"), chf(CT+"g_y1"), @P.y);
        float W = wt*wz*wx*wy;
        if (W > 1e-4) {
            vector vv = v@vel;
            float sp = length(vv);
            vector a = -A*W*vv/max(sp, chf(CT+"g_vref"));
            v@vel = vv + a*f@TimeInc;
        }
    }
}
''' % (CT, arr, len(TT), len(ZC), TT[0], TT[1] - TT[0], ZC[0], ZC[1] - ZC[0])

dop = hou.node("/obj/P2_SIM")
fs = dop.node("flipsolver")
relax = dop.node("relax_zones")
print("flip inputs:", fs.inputLabels())
print("relax connected to input:", [i for i, n in enumerate(fs.inputs()) if n is not None and n.name() == "relax_zones"])
g = dop.node("guide") or dop.createNode("gasfieldwrangle", "guide")
g.parm("snippet").set(GUIDE)
g.setInput(0, relax)
idx = [i for i, n in enumerate(fs.inputs()) if n is not None and n.name() == "relax_zones"][0]
fs.setInput(idx, g)
dop.layoutChildren()
print("guide bindings:", [(p.name(), p.eval()) for p in g.parms() if p.name().startswith("bind") or p.name() in ("field", "fieldname")][:20])

rd = hou.node("/obj/P2_READ")
fv = rd.node("vel_field") or rd.createNode("dopimportfield::2.0", "vel_field")
fv.parm("doppath").set("/obj/P2_SIM")
fv.parm("fields").set(1)
fv.parm("objname1").set("water")
fv.parm("fieldname1").set("vel")
ov = rd.node("OUT_VEL_FIELD") or rd.createNode("null", "OUT_VEL_FIELD")
ov.setInput(0, fv)
rd.layoutChildren()
hou.hipFile.save(HIP)
print("saved", HIP)
print("table x at t=6 :", X[int((6 - 3.5) / 0.25)].round(0).tolist())
