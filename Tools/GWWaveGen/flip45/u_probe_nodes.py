# -*- coding: utf-8 -*-
"""FLIP45（Unity での 3D の面の再生の調べ）：面を作る SOP と書き出しの ROP の引数の名前を、この Houdini の版で読む（hython で実行、数秒）。
推して名前を書かないための下調べ。計算はしない。
使い方: hython u_probe_nodes.py <出力 txt>
2026-10-12 進行役が書いた。"""
import sys
import hou

out = sys.argv[1]
lines = ["houdini %s" % hou.applicationVersionString()]
obj = hou.node("/obj")
geo = obj.createNode("geo", "probe")
for t in ["particlefluidsurface", "vdbfromparticles", "convertvdb", "polyreduce::2.0", "polyreduce", "blast", "clip", "attribwrangle"]:
    try:
        n = geo.createNode(t)
    except Exception as e:  # noqa
        lines.append("== %s : create failed %s" % (t, e))
        continue
    lines.append("== %s  (type %s)" % (t, n.type().nameWithCategory()))
    for p in n.parms():
        try:
            v = p.eval()
        except Exception:  # noqa
            v = "?"
        lines.append("  %s = %r" % (p.name(), v))
out_net = hou.node("/out")
for t in ["alembic"]:
    try:
        n = out_net.createNode(t)
        lines.append("== ROP %s" % t)
        for p in n.parms():
            try:
                v = p.eval()
            except Exception:  # noqa
                v = "?"
            lines.append("  %s = %r" % (p.name(), v))
    except Exception as e:  # noqa
        lines.append("== ROP %s : create failed %s" % (t, e))
open(out, "w", encoding="utf8").write("\n".join(lines))
print("wrote", out, len(lines))
