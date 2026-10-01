# -*- coding: utf-8 -*-
"""設計28修正01 試行F（仕上げ27 の修正 1 回目、2026-09-30 に足した）：包みの生成の記録（ds28r01f_generate_log.json）と今の既定を比べる小さな道具。

背景：仕上げ27 で生成器の既定に 2 つの数値の条件（num_balance_swell_calm・num_sea_sample_range。ds28r01f_params.json で on）が入った。
それより前に作った包み（採用の F_final など）の生成の記録は off が []（何も切っていない）で、f_on にこの 2 つの名前が無い。記録の off だけで
生成器を作り直すと、記録に無い名前が今の既定で入り、別の中身（仕上げ27 の F_p27 の形。τ −4〜0 s の海の縁が最大 0.24 m 違う）になる。
  package_off(result)：記録の off に、F の名前のうち記録の f_on に無い（または切りの）ものを足した「切る名前」を返す。
      決定性の確かめ（ds28r01f_determinism.py）・P20（ds28r01f_p20.py）・仕上げ27 の再現の抜き取り（pl27_repro_check.py）が使う。
      f_on の無い古い記録では、記録の off をそのまま返す。
  rebuild_conflicts(result, off)：既にある包みを同じ場所へ作り直す時に、今の既定と off で作ると、記録では入っていなかったのに入る名前
      （一式 ds28r01f_pipeline.py が、F_final を新しい既定で上書きしないように止めるのに使う）。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def _names():
    import ds28r01f_model as MF
    return MF.F_NAMES, MF.F_OPT_IN, MF.PARAMS_F


def package_off(result):
    """生成の記録の result から、同じ生成器を作り直すための切る名前（list）。"""
    off = list(result.get("off") or [])
    fon = result.get("f_on")
    if not isinstance(fon, dict):
        return off
    names, _, _ = _names()
    for n in names:
        if not fon.get(n, False) and n not in off:
            off.append(n)
    return off


def default_on(off=(), params_path=None):
    """今の ds28r01f_params.json と off で生成器（art_on）を作った時の F の名前の入り切り（Generator.f_on と同じ決め方）。"""
    names, opt_in, pf = _names()
    R = json.load(open(params_path or pf, encoding="utf-8"))
    return {n: bool((R.get(n) or {}).get("on", n not in opt_in) and n not in off) for n in names}


def rebuild_conflicts(result, off=(), params_path=None):
    """記録（result）では入っていない（または名前が無い）のに、今の既定と off で作ると入る F の名前（list）。"""
    fon = result.get("f_on") or {}
    return [n for n, v in default_on(off, params_path).items() if v and not fon.get(n, False)]


def load_result(pkg_dir):
    p = os.path.join(pkg_dir, "ds28r01f_generate_log.json")
    if not os.path.isfile(p):
        return None
    return json.load(open(p, encoding="utf-8")).get("result") or {}
