# -*- coding: utf-8 -*-
"""FLIP45：すぐ走らせられる設定を runs/ready/ に書く（py -3.10。計算は走らせない。表も作らない：表は g45_chain.py・g45_queue.py が最初の起動の前に作る）。
凍結した計画の SHA-256 と入口の利得の記録を確かめてから、plan_numbers.json の runs の全部（kind infeasible を除く）の設定を g45_cfg.make で作る。
立ち上げの形は cfg の table.ramp（V3 だけ tanh_s。2026-10-12 12:45 に足した。g45_cfg.RAMP_BY_RUN）。目次にも書く。
途中保存は消さない決まり（ckpt_keep の allowed_by_user なし。計画 §7.3）。静かな水面を測る x の下限（N1）は、造波板から解く窓で 100 m、窓 L2 は窓の全部。
使い方：py -3.10 x45_ready.py   → Unity/Build/FLIP45/runs/ready/<計算>.json と ready_index.json
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC
import g45_cfg as C
import g45_ckpt as K

ok, bad = GC.frozen_ok()
if not ok:
    raise SystemExit("凍結した計画のファイルの SHA-256 が違う：%s" % bad)
plan = GC.load_plan()
out = GC.B45 + "/runs/ready"
os.makedirs(out, exist_ok=True)
idx = []
for r in plan["runs"]:
    if r["kind"] == "infeasible":
        continue
    cfg = C.make(r["name"], root="runs")
    cfg["ckpt_keep"] = K.keep_policy("main", allowed_by_user=None)
    cfg["n1_x_min"] = 100.0 if cfg["parms"]["x0"] == 0.0 else cfg["parms"]["x0"]
    p = os.path.join(out, r["name"] + ".json")
    json.dump(cfg, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    idx.append(dict(name=r["name"], kind=r["kind"], case=r["case"], layout=r["layout"], dp=r["dp"], f_end=cfg["f_end"], t_off=cfg["parms"]["t_off"],
                    max_hours=cfg["max_hours"], file=p, ox_oy_oz=[cfg["parms"]["ox"], cfg["parms"]["oy"], cfg["parms"]["oz"]],
                    ramp=cfg["table"].get("ramp")))
json.dump(dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), gain_file=GC.GAIN_FILE, gain_sha256=GC.sha256_file(GC.GAIN_FILE), runs=idx),
          open(os.path.join(out, "ready_index.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("wrote", len(idx), "configs to", out)
