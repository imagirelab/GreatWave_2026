"""Run test_shape (S1-S8), test_motion (M1-M6) and test_mesh (G1-G5) on ONE scene, in this order
(test_mesh last: G5 resets the scene).  Stand-alone, headless:

  blender --background --factory-startup --python-exit-code 1 [file.blend] --python tests/run_all.py -- --object <name>
          [--blend <path>] [--build-script <py> ...] [--contour <json>] [--final-frame N]
          [--only shape,motion,mesh] [--skip G5] [... all options of the three tests ...]
(--python-exit-code 1 is REQUIRED for direct calls; tools/run_blender.ps1 always passes it.)

Output: results/<YYYYMMDD_HHMMSS>_all/ metrics.json (combined verdicts + all checks), summary.md and
the sub-directories shape/ motion/ mesh/ with the full output of each test.

Verdict of 'all' (common_test.summarize): PASS only when the validity of every sub-test is ok, nothing failed AND every
check of S1-S8, M1-M6 and G1-G5 was judged.  So a subset (--only shape, --skip G5, no --build-script for G5) can never
come out as PASS: it is INCOMPLETE (the verdicts of the sub-tests that did run are listed under 'tests').  INVALID = a
validity condition of a sub-test is not met; ERROR = a sub-test (or this script) raised: the other sub-tests still run,
metrics.json carries the traceback, exit code 2.  Unknown names in --only / --skip are an ERROR.
Exit code: 0 only for the exact verdict PASS of the --exit-tier (default 'spec'); 2 for ERROR; otherwise 1.
Report-only values (W.*, T.*, S7 single directions / signed / underside / belly, M6.backlog_*, M5.backlog_hold_*) never
enter a verdict.
"""
import argparse
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common_test as ct  # noqa: E402
from common_test import bootstrap, paths, log  # noqa: E402
import test_mesh  # noqa: E402
import test_motion  # noqa: E402
import test_shape  # noqa: E402

TESTS = ("shape", "motion", "mesh")


def main():
    ap = argparse.ArgumentParser(description="great_wave: all tests S1-S8, M1-M6, G1-G5")
    ct.add_common_args(ap)
    test_motion.add_args(ap)
    test_mesh.add_args(ap)
    ap.add_argument("--only", default="shape,motion,mesh", help="comma separated subset of shape,motion,mesh (a subset can never be PASS: the verdict of 'all' is then INCOMPLETE)")
    args = bootstrap.parse_args(ap)

    def body(root):
        only = ct.validate_names(args.only.split(","), TESTS, "--only")
        if not only:
            raise ValueError("--only selects no test (allowed: %s)" % ", ".join(TESTS))
        ct.validate_names(args.skip.split(","), test_mesh.G_IDS, "--skip")
        ctx = ct.setup_context(args, "all", run_dir=root)
        res_scale = args.res_scale
        results, errors = {}, []
        for name, fn in (("shape", lambda c: test_shape.run(c)), ("motion", lambda c: test_motion.run(c)),
                         ("mesh", lambda c: test_mesh.run(c, skip=args.skip.split(",")))):
            if name not in only:
                continue
            ctx.test_name = name
            ctx.run_dir = paths.ensure_dir(os.path.join(root, name))
            args.res_scale = res_scale            # None -> each test uses its own default resolution
            ct.begin_run(ctx.run_dir, name)
            try:
                results[name] = fn(ctx)
            except Exception as exc:              # one crashing sub-test must not hide the others; the total becomes ERROR
                tb = traceback.format_exc()
                for ln in tb.rstrip().splitlines():
                    log("[all] ERROR in %s: %s" % (name, ln))
                results[name] = ct.error_result(name, ctx.run_dir, exc, tb)
                ct.write_result(ctx.run_dir, results[name])
                errors.append("%s: %s: %s" % (name, type(exc).__name__, exc))
            ct.end_run(ctx.run_dir)
        ctx.run_dir, ctx.test_name = root, "all"
        checks = [c for r in results.values() for c in r["checks"]]
        valid = all(r["summary"]["validity_ok"] for r in results.values() if not r.get("error"))
        notes = ["%s: %s" % (k, n) for k, r in results.items() for n in r["summary"]["validity_notes"]]
        not_run = [t for t in TESTS if t not in only]
        if not_run:
            notes.append("NOT RUN (--only %s): %s - their checks are not judged, so the verdict of 'all' cannot be PASS" % (args.only, ", ".join(not_run)))
        skipped = [s for r in results.values() for s in r["summary"].get("skipped", [])]
        audit = {"non_default": [], "unlisted": [], "report_only_non_default": []}
        for r in results.values():
            for key in audit:
                for d in (r.get("settings_audit") or {}).get(key, []):
                    if d not in audit[key]:
                        audit[key].append(d)
        combined = {"schema": ct.RESULT_SCHEMA, "test": "all", "run_dir": root, "context": ctx.describe(),
                    "summary": ct.summarize(checks, valid, notes, skipped, expected=ct.EXPECTED_IDS["all"], audit=audit, errors=errors),
                    "tests": {k: r["summary"] for k, r in results.items()}, "tests_not_run": not_run,
                    "checks": checks, "sub_results": {k: r["run_dir"] for k, r in results.items()}, "settings_audit": audit,
                    "interpretation_notes": ct.INTERPRETATION_NOTES}
        ct.write_result(root, combined)
        for k, r in results.items():
            log("[all] %-6s %s" % (k, " ".join("%s=%s" % (t, r["summary"][t]["verdict"]) for t in ct.TIERS)))
        log("[all] results: %s" % root)
        return combined

    ct.guarded_main("all", args, body)


if __name__ == "__main__":
    main()
