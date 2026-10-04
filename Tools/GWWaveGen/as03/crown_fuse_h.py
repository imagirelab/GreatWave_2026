# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1（試し）：冠の手・指・袖と、根元の周りの主役波の面の薄い板を VDB でひとつにし、つなぎ目に丸みをつける（Houdini の hython）。
crown_fuse.py が書いた parts.obj（手・指・袖の閉じた管）と slabs.obj（根元の周りの主役波の面の板、面から下へ 0.5 m）を読み、
VDB にして和を取り（SDF union）、閉じ（close：へこんだ角を丸める）、なめらかにして（Gaussian）、多角形に戻して fused.obj に書く。
場面（.hip）は保存しない。使い方：hython crown_fuse_h.py <parts.obj> <slabs.obj> <out.obj> <voxel> <close_radius>
"""
import sys

import hou

parts, slabs, out, vox, rclose = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
g = hou.node("/obj").createNode("geo", "as03_crown_fuse")


def vdb_of(path, name):
    f = g.createNode("file", name + "_in")
    f.parm("file").set(path)
    v = g.createNode("vdbfrompolygons", name + "_vdb")
    v.setInput(0, f)
    v.parm("voxelsize").set(vox)
    v.parm("useworldspaceunits").set(0)
    v.parm("exteriorbandvoxels").set(6)
    v.parm("interiorbandvoxels").set(6)
    v.parm("fillinterior").set(1)
    return v


a = vdb_of(parts, "parts")
b = vdb_of(slabs, "slabs")
c = g.createNode("vdbcombine", "union")
c.setInput(0, a)
c.setInput(1, b)
c.parm("operation").set("sdfunion")
r = g.createNode("vdbreshapesdf", "close")
r.setInput(0, c)
r.parm("operation").set("close")
r.parm("useworldspaceunits").set(1)
r.parm("radiusworld").set(rclose)
s = g.createNode("vdbsmoothsdf", "smooth")
s.setInput(0, r)
s.parm("operation").set("gaussian")
s.parm("iterations").set(2)
s.parm("radius").set(1)
cv = g.createNode("convertvdb", "topoly")
cv.setInput(0, s)
cv.parm("conversion").set("poly")
cv.parm("adaptivity").set(0.12)
cv.parm("computenormals").set(1)
geo = cv.geometry()
print("FUSED_POINTS", len(geo.points()), "PRIMS", len(geo.prims()), flush=True)
geo.saveToFile(out)
print("FUSE_DONE", out, flush=True)
