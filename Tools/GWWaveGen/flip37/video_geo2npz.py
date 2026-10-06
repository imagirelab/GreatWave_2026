# -*- coding: utf-8 -*-
"""Houdini の形のファイルの列（.bgeo / .bgeo.sc / .abc / .obj、1 コマ 1 ファイル）→ 動画の道具の網目 mesh_FFFF.npz（P・tri・t）。
P2 の run_p2.py は計算の中で mesh_FFFF.npz を書くので、この変換は、P3 などが網目を Houdini の形で書いた時だけ使う。
重い計算ではない（読み込みと三角形への分割だけ）。hython で走らせる。

使い方:
  hython video_geo2npz.py <入力の glob（例 G:/.../surface.*.bgeo.sc）> <out_mesh_dir> [--fps 24] [--frame-regex "\\.(\\d+)\\.bgeo"]
         [--every 1] [--t-offset 0]
  コマの番号はファイル名の最後の数（--frame-regex で替えられる）。t = (コマ − 1) / fps + t_offset（P2 と同じ決め方）。
  ほかに、試験用に npz → bgeo.sc を書く: hython video_geo2npz.py --npz2geo <in.npz> <out.bgeo.sc>
"""
import sys, os, re, glob, argparse
import numpy as np
import hou


def tri_geo(path):
    g = hou.Geometry()
    g.loadFromFile(path)
    if any(p.type() != hou.primType.Polygon or len(p.vertices()) != 3 for p in g.prims()):
        verb = hou.sopNodeTypeCategory().nodeVerb("divide")
        verb.setParms({"convex": 1, "numsides": 3})
        out = hou.Geometry()
        verb.execute(out, [g])
        g = out
    # 三角形以外（体積・粒子など）は捨てる
    bad = [p for p in g.prims() if not (p.type() == hou.primType.Polygon and len(p.vertices()) == 3)]
    if bad:
        g.deletePrims(bad)
    P = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
    # 頂点ごとの点の番号（attribwrangle は verb として使えないので Python で回す。5 万の三角形で約 1 秒）
    tri = np.array([[v.point().number() for v in p.vertices()] for p in g.prims()], np.int32).reshape(-1, 3)
    return P, tri


def npz2geo(src, dst):
    d = np.load(src)
    g = hou.Geometry()
    pts = g.createPoints([tuple(map(float, q)) for q in d["P"]])
    g.createPolygons([tuple(int(i) for i in t) for t in d["tri"]])
    g.saveToFile(dst)
    print("wrote", dst, len(pts), len(d["tri"]))


def main():
    if "--npz2geo" in sys.argv:
        i = sys.argv.index("--npz2geo")
        npz2geo(sys.argv[i + 1], sys.argv[i + 2])
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("pattern"); ap.add_argument("out_dir")
    ap.add_argument("--fps", type=float, default=24.0)
    ap.add_argument("--frame-regex", default=r"(\d+)(?!.*\d)")
    ap.add_argument("--every", type=int, default=1)
    ap.add_argument("--t-offset", type=float, default=0.0)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    fs = sorted(glob.glob(a.pattern))
    rx = re.compile(a.frame_regex)
    for k, f in enumerate(fs):
        if k % a.every:
            continue
        m = rx.search(os.path.basename(f))
        if not m:
            print("skip (no frame number)", f); continue
        fr = int(m.group(1))
        P, tri = tri_geo(f)
        used = np.unique(tri)
        remap = -np.ones(len(P), np.int32); remap[used] = np.arange(len(used), dtype=np.int32)
        np.savez_compressed(os.path.join(a.out_dir, "mesh_%04d.npz" % fr), P=P[used], tri=remap[tri],
                            t=(fr - 1) / a.fps + a.t_offset, source=f.replace("\\", "/"))
        print("mesh_%04d verts=%d tris=%d" % (fr, len(used), len(tri)))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
