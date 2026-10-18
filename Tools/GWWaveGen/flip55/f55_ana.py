# -*- coding: utf-8 -*-
"""FLIP55: the DFG-2B-V judge, co-equal verdict and compare video applied UNCHANGED to a FLIP55 full-tank run (option A375) (py -3.10 -B;
numpy, scipy, PIL, ffmpeg). 2026-10-19 written new (Claude).
flip52b3/g52b3_ana.py and flip52b3/g52b3_video.py (frozen; their sha256 is checked against the FLIP55 plan) contain every rule (DFGB4's gates
G1-G6, eligibility, decision, co-equal criteria incl. 3b / 3c / keeps the curl, the hero class). They only refuse to WRITE outside
Unity/Build/FLIP52B3 (g52b3_common.guard_out). This wrapper changes, IN MEMORY of its own process only, g52b3_common.B52B3 and SCRATCH_PREFIX to
Unity/Build/FLIP55 so the same code writes <run>/g52b3/judge_DFGB4.json, <run>/g52/judge_DFG.json (pv53 alias), <run>/g52b3/coequal_DFGB4.json
and <run>/video/ inside the FLIP55 run folder. Nothing else is changed; no file of flip52b3 is edited.
Group-1 stage (frames 1-1657): the judge reads only the groups whose window lies inside the record (group 1); 'run_complete', 'groups3' and
G2f (t 49-105 s) cannot pass on 69 s - expected and REPORT ONLY at that stage (the plan's reading of the group-1 stage is the hollow, f55_hollow).
usage:
  py -3.10 -B f55_ana.py judge <run_dir> [--out=<Unity/Build/FLIP55/_scratch/...>] [--test-any-set]
  py -3.10 -B f55_ana.py coequal <run_dir> [--pv=<pv53 json>] [--out=... --judge=...]
  py -3.10 -B f55_ana.py video <run_dir> [--out=...]
  py -3.10 -B f55_ana.py selftest      (g52b3_ana selftest + DFG-2B-V judged by this wrapper into Unity/Build/FLIP55/_scratch/selftest_judge: the
                                        numbers must equal DFG-2B-V's own judge_DFGB4.json)
"""
import os, sys, json

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import f55_common as C                                   # noqa: E402
sys.path.insert(0, C.T52B3)
import g52b3_common as GC                                # noqa: E402  read only (patched in memory below)

GC.B52B3 = C.B55                                          # guard_out reads these module globals at call time
GC.SCRATCH_PREFIX = C.B55 + "/_scratch/"
import g52b3_ana as GA                                   # noqa: E402  frozen rules


def run_main(mod, argv):
    old = sys.argv
    sys.argv = [mod.__file__] + list(argv)
    try:
        mod.main()
    finally:
        sys.argv = old


def selftest():
    import io, contextlib
    ok = {}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ok["g52b3_ana_selftest"] = bool(GA.selftest())
    out = C.SCRATCH + "/selftest_judge"
    os.makedirs(out, exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):
        r = GA.judge(C.DFGBV_RUN, out_dir=out)
    ref = C.jload(C.DFGBV_RUN + "/g52b3/judge_DFGB4.json")
    keys = ("valid", "failed_gates", "core_miss_median")
    ok["same_as_DFGBV_judge"] = bool(all(json.dumps(C.clean(r.get(k))) == json.dumps(C.clean(ref.get(k))) for k in keys)
                                     and json.dumps(C.clean(r["median"])) == json.dumps(C.clean(ref["median"])))
    ok["written_inside_FLIP55"] = bool(r["_path"].startswith(C.B55 + "/"))
    res = dict(ok=bool(all(ok.values())), checks=ok, judge=r["_path"], valid=r.get("valid"), failed=r.get("failed_gates"),
               miss=r.get("core_miss_median"), ref_miss=ref.get("core_miss_median"))
    print(json.dumps(C.clean(res), ensure_ascii=False))
    return res["ok"]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "selftest":
        sys.exit(0 if selftest() else 1)
    if a[0] in ("judge", "coequal"):
        run_main(GA, a)
    elif a[0] == "video":
        import g52b3_video as GV                          # frozen (imports g52b3_common: the same patched module)
        run_main(GV, a[1:])
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
