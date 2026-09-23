"""一つのシーンで形状 S1–S8、運動 M1–M6、網目 G1–G5 をこの順で検査する。
G5 はシーンを初期化するため網目検査を最後に行う。無画面で単独実行できる。

  blender --background --factory-startup --python-exit-code 1 [file.blend] --python tests/run_all.py -- --object <name>
          [--blend <path>] [--build-script <py> ...] [--contour <json>] [--final-frame N]
          [--only shape,motion,mesh] [--skip G5] [各検査の追加引数]
直接起動するときは --python-exit-code 1 が必須。tools/run_blender.ps1 は常に指定する。

出力：results/<YYYYMMDD_HHMMSS>_all/ に総合判定と全検査値の metrics.json、summary.md を置き、
shape/、motion/、mesh/ に各検査の全結果を保存する。

総合判定：全ての検査で形状が有効、違反がなく、S1–S8・M1–M6・G1–G5 の全項目を判定した場合だけ PASS。
--only、--skip、G5 の構築スクリプト未指定で項目が欠ければ INCOMPLETE となる。
有効性条件に違反すれば INVALID。例外時は ERROR とし、他の検査は続行して例外の詳細を記録する。
--only／--skip の未知の名前も ERROR。終了コードは指定段階の厳密な PASS のみ0、ERROR は2、その他は1。
W.*、T.*、S7の片方向・符号付き・下面・波腹、M6.backlog_*、M5.backlog_hold_* は報告専用である。
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
    ap = argparse.ArgumentParser(description="大波の総合検査：S1–S8、M1–M6、G1–G5")
    ct.add_common_args(ap)
    test_motion.add_args(ap)
    test_mesh.add_args(ap)
    ap.add_argument("--only", default="shape,motion,mesh", help="shape,motion,mesh から実行対象をカンマ区切りで指定。全対象を実行しない場合、総合判定は INCOMPLETE")
    args = bootstrap.parse_args(ap)

    def body(root):
        only = ct.validate_names(args.only.split(","), TESTS, "--only")
        if not only:
            raise ValueError("--only で検査が一つも選ばれていない（使用可能：%s）" % ", ".join(TESTS))
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
            args.res_scale = res_scale            # None の場合、各検査の既定解像度を使う
            ct.begin_run(ctx.run_dir, name)
            try:
                results[name] = fn(ctx)
            except Exception as exc:              # 一つが例外終了しても残りを実行し、総合判定は ERROR とする
                tb = traceback.format_exc()
                for ln in tb.rstrip().splitlines():
                    log("[all] %s でエラー: %s" % (name, ln))
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
            notes.append("未実行（--only %s）：%s。対応項目を判定していないため、総合判定は PASS にできない" % (args.only, ", ".join(not_run)))
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
        log("[all] 結果: %s" % root)
        return combined

    ct.guarded_main("all", args, body)


if __name__ == "__main__":
    main()
