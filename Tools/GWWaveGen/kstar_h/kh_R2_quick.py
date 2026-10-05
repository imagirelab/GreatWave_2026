# -*- coding: utf-8 -*-
"""K*′ 精修 R2：設計の json（kh_designR2）または行の npz を素早く測る（py -3.10、1 候補 約 15〜30 秒、--render で + 約 30 秒）。
  原画の関門（公式と大きな輪郭）、評審の膨らみ（j_bulge6 と同じ式、行・列を間引き、区域ごとの p99）、形の検査（kh_R1_quick）、
  ルーブリック（rubric_check.py をそのまま呼ぶ。必須の不合格の一覧）、--render：Blender の粘土の描画（v1 v3 v6 v9 u10 u11 u13）の並べ図。
usage: py -3.10 kh_R2_quick.py [--render OUTDIR] [--no-rubric] label=design.json|rows.npz ...
"""
import os
import sys
import json
import time
import subprocess
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (HERE, os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "PaintingTruth"),
          os.path.join(REPO, "Tools", "GWWaveGen"), os.path.join(REPO, "Unity", "Build", "Q20", "rubric", "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402
import kh_designR2 as D  # noqa: E402
import kh_R1_quick as Q1  # noqa: E402
import kh_common as KC  # noqa: E402

TMP = os.path.join(KC.OUT_ROOT, "final", "_work", "R2", "tmp")
QVIEWS = "v1_painting+v3_side_along_crest_cam_side+v6_top_down+v9_user8_az030_el25+u11_v9zoom_crest_bulge+u13_v8zoom_b_region+u10_foot_zoom+v5_back_three_quarter"


def load(spec):
    if spec.endswith(".json"):
        c, A, Y, P = D.build(D.Design.load(spec))
        return c, A, Y
    z = np.load(spec)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def bulge_regions(c, A, Y):
    r = Q1.bulge6(c, A, Y, 2, 3)
    cc = np.repeat(c[:, None], D.NU, 1)
    for R in ("R4", "R6"):
        M = Q1._CACHE["bulgemap_" + R]
        f = np.isfinite(M)
        reg = {}
        for nm, (ja, jb) in (("back", (18, 90)), ("top", (90, 201))):
            for cn, (ca, cb) in (("sh", (-16, -6)), ("main", (-6, 3)), ("far", (3, 16))):
                mm = f & (np.arange(D.NU)[None, :] >= ja) & (np.arange(D.NU)[None, :] < jb) & (cc >= ca) & (cc < cb)
                if mm.sum() > 10:
                    reg[nm + "/" + cn] = round(float(np.percentile(M[mm], 99)), 2)
        r[R]["regions_p99"] = reg
    return r


def rubric(c, A, Y, tag):
    import rubric_check as RC
    os.makedirs(TMP, exist_ok=True)
    p = os.path.join(TMP, "rq_%s_rows.npz" % tag)
    np.savez_compressed(p, A=A, Y=Y, c=c)
    R = RC.check(p)
    fails = []
    keep = {}
    for f, L in R["checks"].items():
        for x in L:
            if x["pass_must"] is not None and not bool(x["pass_must"]):   # numpy bools too
                v = x["value"]
                fails.append("%s %s=%s" % (f, x["name"][:26], json.dumps(v if not isinstance(v, float) else round(v, 2))))
            if any(k in x["name"] for k in ("折れ > 30", "壁の曲がり", "丸さ", "2 m あたりの向き", "高さの落ち", "固まりの幅", "奥 c > +3 の行の最小）")):
                v = x["value"]
                keep[f + " " + x["name"][:20]] = v if not isinstance(v, float) else round(v, 2)
    return {"n_must_fail_nogate": len(fails), "fails": fails, "key": keep}


def render(items, outdir):
    outdir = os.path.abspath(outdir)          # absolute: Blender resolves a relative output path against its own folder (C:)
    assert outdir.upper().startswith("G:"), outdir
    os.makedirs(outdir, exist_ok=True)
    arg = []
    for lab, (c, A, Y) in items:
        g = os.path.join(outdir, lab + ".gwb")
        KC.write_gwb(g, D.NU, len(c), np.zeros((len(c) * D.NU, 2)), np.zeros((len(c) * D.NU, 2)), KC.triangles(D.NU, len(c)), KC.world(c, A, Y))
        arg.append("%s=%s" % (lab, g))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    cmd = [KC.BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", os.path.join(HERE, "kh_bl.py"), "--",
           "views", outdir, ",".join(arg), "views=" + QVIEWS]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=900, encoding="utf-8", errors="replace", cwd=outdir)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-2000:])
    labs = ",".join(l for l, _ in items)
    subprocess.run(["py", "-3.10", os.path.join(HERE, "kh_contact.py"), outdir, os.path.join(outdir, "sheet.png"), labs, "views=" + QVIEWS, "cell=420"],
                   capture_output=True, text=True, env=env)
    return os.path.join(outdir, "sheet.png")


def quick(spec, tag, do_rubric=True):
    t0 = time.time()
    c, A, Y = load(spec)
    r = {"gate": Q1.official_gate(c, A, Y, os.path.join(TMP, "gate_%s.png" % tag)), "gate_lf": Q1.lf_gate(c, A, Y)}
    r["gate_pass_lf"] = bool(all(r["gate"][k]["max"] <= 4 for k in ("78", "130", "131")) and r["gate_lf"]["132"]["max"] <= 4
                             and r["gate_lf"]["72"]["p95"] <= 4)
    r["shape"] = Q1.shape_checks(c, A, Y)
    r["bulge6"] = bulge_regions(c, A, Y)
    if do_rubric:
        r["rubric"] = rubric(c, A, Y, tag)
    r["seconds"] = round(time.time() - t0, 1)
    return r, (c, A, Y)


if __name__ == "__main__":
    os.makedirs(TMP, exist_ok=True)
    rd0 = sys.argv[sys.argv.index("--render") + 1] if "--render" in sys.argv else None
    rd = os.path.abspath(rd0) if rd0 else None
    items = []
    skip = {rd0}
    for a in sys.argv[1:]:
        if a.startswith("--") or a in skip:
            continue
        lab, spec = a.split("=", 1)
        r, g = quick(spec, lab, "--no-rubric" not in sys.argv)
        items.append((lab, g))
        json.dump(r, open(os.path.join(TMP, "quick_%s.json" % lab), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(lab, json.dumps(r), flush=True)
    if rd:
        print("sheet", render(items, rd))
