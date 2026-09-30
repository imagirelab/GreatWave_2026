# -*- coding: utf-8 -*-
"""設計41：押送船（おしおくりぶね）の Blender モデルを作る（船体・船縁・操作物、衝突形状、浮力用の船体）。

Blender 5.2.2 のバックグラウンドで実行する：
    blender.exe --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/ds41/ds41_boat_blender.py -- [--params <json>] [--out <dir>]

- 座標：Blender の右手系、上 +Z、船首 −Y（M1 の blockout と同じ）。原点は竜骨の中央（船底の中央の高さ 0）。
- 単位は「置き方の枠」：船首の先端 (0, −5, 1.775) と船尾の先端 (0, 5, 1.685) の間を 10 とする（美術優先27 の af27_place.py の
  TIP_PLUS_Z・TIP_MINUS_Z と同じ点）。Unity では 3 隻の根の Transform（位置・回転・縮尺）を変えずに差し替えるので、
  原画視点の両端の投影は変わらない。実寸は船ごとの縮尺を掛けた値。
- FBX は設計07 で確かめた設定（M1 の EXPORT_FLAGS と同じ。-Z forward / Y up、global_scale 1、apply_unit_scale、
  FBX_SCALE_UNITS、use_space_transform、bake_space_transform なし）で書き出す。Blender→Unity の対応は (x, y, z) → (−x, z, −y)。
- 形は原画と所蔵館・公的機関の資料の寸法の比から作る。旧試作・参照モデル・写真は使わない。
- 出力：<out>/ds41_oshiokuri.blend・.fbx、ds41_boat_geom.npz（部品ごとの頂点と三角形、Blender 座標）、
  ds41_blender_report.json（寸法・部品・往復の検査・浮力の表・浮力点・SHA-256）、preview_*.png。
"""
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default):
    return ARGV[ARGV.index(name) + 1] if name in ARGV else default


PARAMS = arg("--params", os.path.join(HERE, "ds41_boat_params.json"))
OUT = arg("--out", os.path.join(REPO, "Unity", "Build", "Design", "41", "model", "blender"))
TOL = 1e-5
# 設計07（M1 の generate_m1_assets.py）と同じ書き出しの設定
EXPORT_FLAGS = {
    'check_existing': False, 'use_selection': True, 'global_scale': 1.0,
    'apply_unit_scale': True, 'apply_scale_options': 'FBX_SCALE_UNITS',
    'axis_forward': '-Z', 'axis_up': 'Y', 'use_space_transform': True,
    'bake_space_transform': False, 'object_types': {'MESH'},
    'use_mesh_modifiers': True, 'use_triangles': True,
    'mesh_smooth_type': 'OFF', 'use_custom_props': True,
    'bake_anim': False, 'add_leaf_bones': False,
    'path_mode': 'STRIP', 'embed_textures': False,
}
IMPORT_FLAGS = {'global_scale': 1.0, 'use_manual_orientation': False, 'bake_space_transform': False,
                'use_anim': False, 'use_image_search': False, 'use_custom_props': True}

with open(PARAMS, encoding="utf-8") as f:
    P = json.load(f)


def val(x):
    return x["value"] if isinstance(x, dict) else x


HP = {k: val(v) for k, v in P["hull"].items()}
L = P["frame"]["tip_to_tip_units"]
W = HP["beam_over_length"] * L / 2.0          # 船縁の最大の半幅
D = HP["depth_over_length"] * L               # 船体中央の深さ（船底から舷の上縁）
BF = HP["bottom_half_width_over_half_beam"]
YB0, YB1 = HP["bow_end_bottom_y"], HP["bow_end_sheer_y"]
YS0, YS1 = HP["stern_end_bottom_y"], HP["stern_end_sheer_y"]
NST = int(HP["stations"])


# ---------------------------------------------------------------- 船体の形（u：船首 0 → 船尾 1、h：船底 0 → 舷の上縁 1）
def y_at(u, h):
    yb = YB0 + (YB1 - YB0) * h
    ys = YS0 + (YS1 - YS0) * h
    return yb + (ys - yb) * u


def rocker(y):
    r0 = HP["rocker_start_abs_y"]
    if y < -r0:
        t = (-r0 - y) / (-r0 - YB0)
        return HP["bow_rocker_rise"] * min(1.0, t) ** 2
    if y > r0:
        t = (y - r0) / (YS0 - r0)
        return HP["stern_rocker_rise"] * min(1.0, t) ** 2
    return 0.0


def sheer(y):
    yl, p = HP["sheer_low_y"], HP["sheer_exponent"]
    if y < yl:
        t = (yl - y) / (yl - YB1)
        return D + (HP["bow_sheer_height"] - D) * min(1.0, t) ** p
    t = (y - yl) / (YS1 - yl)
    return D + (HP["stern_sheer_height"] - D) * min(1.0, t) ** p


def beam_frac(y, bow_end, stern_end):
    ym = HP["max_beam_y"]
    if y <= ym:
        t = max(0.0, min(1.0, (y - bow_end) / (ym - bow_end)))
        return (1.0 - (1.0 - t) ** 2) ** 0.9
    t = max(0.0, min(1.0, (y - ym) / (stern_end - ym)))
    return 1.0 - (1.0 - HP["stern_half_beam_end_fraction"]) * t ** 2


def section(u):
    """片舷（x ≥ 0）の断面の 4 点：船底の中央・航の角（chine）・根棚と上棚の折れ（knuckle）・舷の上縁。"""
    y0, y1 = y_at(u, 0.0), y_at(u, 1.0)
    zb, zg = rocker(y0), sheer(y1)
    w = W * beam_frac(y1, YB1, YS1)
    b = BF * W * beam_frac(y0, YB0, YS0)
    kh, kw = HP["knuckle_height_fraction"], HP["knuckle_width_fraction"]
    yk = y0 + (y1 - y0) * kh
    return [(0.0, y0, zb), (b, y0, zb), (b + kw * (w - b), yk, zb + (zg - zb) * kh), (w, y1, zg)]


def full_section(u):
    s = section(u)
    left = [(-x, y, z) for (x, y, z) in reversed(s[1:])]   # −X（右舷）の上縁から
    return left + [s[0]] + s[1:]                           # 7 点：右舷の上縁 → 中央 → 左舷の上縁


def u_for_y(y, h):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if y_at(m, h) < y:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def half_width_at(y, z):
    """高さ z での船殻の内側の半幅（断面の折れ線を z で補間）。"""
    u = u_for_y(y, 0.5)
    s = section(u)
    pts = [(s[1][0], s[1][2]), (s[2][0], s[2][2]), (s[3][0], s[3][2])]
    if z <= pts[0][1]:
        return pts[0][0]
    for (xa, za), (xb, zb) in zip(pts, pts[1:]):
        if za <= z <= zb:
            return xa + (xb - xa) * (z - za) / max(1e-9, zb - za)
    return pts[-1][0]


# ---------------------------------------------------------------- Blender の部品
class MeshBuf:
    def __init__(self):
        self.v, self.f, self.key = [], [], {}

    def add(self, p, merge=False):
        p = tuple(float(c) for c in p)
        if merge:
            k = tuple(round(c, 7) for c in p)
            if k in self.key:
                return self.key[k]
            self.key[k] = len(self.v)
        self.v.append(p)
        return len(self.v) - 1

    def face(self, idx):
        out = []
        for i in idx:
            if i not in out:
                out.append(i)
        if len(out) >= 3:
            self.f.append(tuple(out))

    def box(self, center, size, basis=None):
        cx, cy, cz = center
        ex = basis or [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
        s = len(self.v)
        for sx, sy, sz in [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]:
            p = [cx, cy, cz]
            for k, (sg, e) in enumerate(zip((sx, sy, sz), ex)):
                for j in range(3):
                    p[j] += sg * size[k] / 2.0 * e[j]
            self.v.append(tuple(p))
        for fc in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
            self.f.append(tuple(s + i for i in fc))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = 'METERS'


MATS = {}


def material(name, rgba):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.diffuse_color = rgba
    MATS[name] = m
    return m


def make_object(name, buf, mat, role_ja, recalc=True, props=None):
    me = bpy.data.meshes.new(name + "_Mesh")
    me.from_pydata(buf.v, [], buf.f)
    me.validate(verbose=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(mat)
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(me)
        bm.free()
    for p in me.polygons:
        p.use_smooth = False
    ob["role_ja"] = role_ja
    ob["unit"] = "placement frame (tip-to-tip 10); real = x boat scale"
    ob["forward_axis_blender"] = "-Y"
    for k, v in (props or {}).items():
        ob[k] = v
    return ob


def build():
    wood = material("GW_Boat_Wood", (.63, .38, .18, 1))
    plank = material("GW_Boat_Plank", (.76, .58, .32, 1))
    edge = material("GW_Boat_Edge", (.16, .20, .24, 1))
    oar_m = material("GW_Boat_Oar", (.20, .22, .26, 1))
    helper = material("GW_Boat_Helper", (.9, .1, .9, 1))
    us = [i / (NST - 1) for i in range(NST)]
    secs = [full_section(u) for u in us]
    objs = {}

    # 1) 船殻（外面の一枚。両面で描く材質。船首は水押の線に集まり、船尾は戸立でふさぐ）
    hb = MeshBuf()
    idx = [[hb.add(p, merge=(i == 0)) for p in s] for i, s in enumerate(secs)]
    for i in range(NST - 1):
        for j in range(6):
            hb.face((idx[i][j], idx[i][j + 1], idx[i + 1][j + 1], idx[i + 1][j]))
    hb.face(list(reversed(idx[-1])))  # 戸立（船尾板）
    objs["Boat41_Hull"] = make_object("Boat41_Hull", hb, wood, "船体（外面。航・根棚・上棚の折れを持つ和船の断面、戸立の船尾板）")

    # 2) 水押（船首の柱）：前の稜が x = 0 で船首の先端 (0, −5, 1.775) を通る三角柱
    st = P["stem"]
    tip = Vector(P["frame"]["bow_tip_blender"])
    bot = Vector(section(0.0)[0]) + Vector((0, -0.02, -0.03))
    ax = (tip - bot).normalized()
    nb = Vector((0, 1, 0)) - ax * ax.dot(Vector((0, 1, 0)))
    nb.normalize()                                            # 船尾・上の向き（船体の内へ）
    sb = MeshBuf()
    ring = []
    for base in (bot, tip):
        ring.append([sb.add(base), sb.add(base + nb * st["depth"] + Vector((-st["width"] / 2, 0, 0))),
                     sb.add(base + nb * st["depth"] + Vector((st["width"] / 2, 0, 0)))])
    for j in range(3):
        sb.face((ring[0][j], ring[0][(j + 1) % 3], ring[1][(j + 1) % 3], ring[1][j]))
    sb.face(tuple(ring[0]))
    sb.face(tuple(reversed(ring[1])))
    objs["Boat41_Stem"] = make_object("Boat41_Stem", sb, wood, "水押（みよし。船首の柱）。前の稜の上端が船首の先端")

    # 3) 船縁（両舷の縁材。舷の上縁に沿う閉じた角材）
    gp = P["gunwale"]
    for side, lab in ((-1, "S"), (1, "P")):
        gb = MeshBuf()
        rings = []
        for i, u in enumerate(us):
            s = section(u)[3]
            w = s[0]
            if w < gp["width"] * 0.8:
                continue
            x0, x1 = side * w, side * (w - gp["width"])
            zt = s[2] + gp["top_above_sheer"]
            zb_ = zt - gp["height"]
            rings.append([gb.add((x0, s[1], zb_)), gb.add((x1, s[1], zb_)), gb.add((x1, s[1], zt)), gb.add((x0, s[1], zt))])
        for a, b in zip(rings, rings[1:]):
            for j in range(4):
                gb.face((a[j], a[(j + 1) % 4], b[(j + 1) % 4], b[j]))
        gb.face(tuple(rings[0]))
        gb.face(tuple(reversed(rings[-1])))
        nm = "Boat41_Gunwale_" + ("Starboard" if lab == "S" else "Port")
        objs[nm] = make_object(nm, gb, edge, "船縁（ふなべり）の縁材。%s（Blender の %sX、Unity の %sX）" % (
            "右舷" if lab == "S" else "左舷", "−" if lab == "S" else "+", "+" if lab == "S" else "−"))

    # 4) 敷板（床）
    fp = P["floor"]
    fb = MeshBuf()
    y = fp["from_y"]
    floor_rows = []
    while y + fp["plank_pitch"] <= fp["to_y"] + 1e-9:
        yc = y + fp["plank_pitch"] / 2
        ztop = rocker(yc) + fp["offset_above_bottom"]
        zc = ztop - fp["thickness"] / 2
        hw = min(half_width_at(yy, ztop - fp["thickness"]) for yy in (y, yc, y + fp["plank_pitch"])) - 0.04
        if hw > 0.05:
            fb.box((0, yc, zc), (2 * hw, fp["plank_pitch"] - fp["gap"], fp["thickness"]))
            floor_rows.append({"y": round(yc, 4), "top_z": round(ztop, 5), "half_width": round(hw, 4)})
        y += fp["plank_pitch"]
    objs["Boat41_Floor"] = make_object("Boat41_Floor", fb, plank, "敷板（床）。座席 v1 の甲板の高さを保つ")

    # 5) 船梁
    bp = P["beams"]
    bb = MeshBuf()
    beam_rows = []
    for yb in bp["y"]:
        zg = sheer(yb)
        zc = zg - bp["below_sheer"] - bp["size_z"] / 2
        hw = half_width_at(yb, zc + bp["size_z"] / 2) - 0.01
        bb.box((0, yb, zc), (2 * hw, bp["size_y"], bp["size_z"]))
        beam_rows.append({"y": yb, "center_z": round(zc, 4), "half_length": round(hw, 4)})
    objs["Boat41_Beams"] = make_object("Boat41_Beams", bb, edge, "船梁（ふなばり）")

    # 6) 艫の板（船尾の先端 (0, 5, 1.685) はこの板の後ろの上縁の中央）と、それを支える 2 本の柱
    sp = P["stern"]
    kb = MeshBuf()
    yc = 0.5 * (sp["deck_from_y"] + sp["deck_to_y"])
    for sx in (-1, 1):
        kb.box((sx * sp["half_width"] / 2, yc, sp["deck_top"] - sp["thickness"] / 2),
               (sp["half_width"], sp["deck_to_y"] - sp["deck_from_y"], sp["thickness"]))
    s_end = section(1.0)
    for sx in (-1, 1):
        zlo = s_end[3][2] - 0.10
        kb.box((sx * 0.32, sp["deck_from_y"] + 0.12, 0.5 * (zlo + sp["deck_top"] - sp["thickness"])), (0.06, 0.06, sp["deck_top"] - sp["thickness"] - zlo))
    objs["Boat41_SternDeck"] = make_object("Boat41_SternDeck", kb, wood, "艫の板と柱（戸立の上）")

    # 6b) 船尾の梯子状の枠（絵の P8）
    fr = P["stern_frame"]
    fb2 = MeshBuf()
    z0 = sp["deck_top"]
    z1 = z0 + fr["height_above_deck"]
    for sx in (-1, 1):
        fb2.box((sx * fr["post_x"], fr["post_y"], 0.5 * (z0 + z1)), (fr["post_size"], fr["post_size"], z1 - z0))
    for r in range(fr["rungs"]):
        zr = z0 + (r + 1) * (z1 - z0) / (fr["rungs"] + 0.5)
        fb2.box((0, fr["post_y"], zr), (2 * fr["post_x"], fr["post_size"] * 0.8, fr["post_size"] * 0.8))
    objs["Boat41_SternFrame"] = make_object("Boat41_SternFrame", fb2, wood, "船尾の梯子状の枠（原画の右船の読み P8。用途は資料で未確認）")

    # 7) 櫓（操作物）：7 丁（左舷 4・右舷 3 を交互）。右舷は Blender −X（Unity +X）、左舷は +X（Unity −X）。本数が左右で違うので左右の反転の検査にも使う
    op = P["oars"]
    d0 = op["direction_out_aft_down"]
    oar_rows = []
    cnt = {"S": 0, "P": 0}
    for yp2, lab in zip(op["pivot_y"], op["sides"]):
        side = -1 if lab == "S" else 1
        cnt[lab] += 1
        k = cnt[lab] - 1
        if True:
            u = u_for_y(yp2, 1.0)
            s = section(u)[3]
            piv = Vector((side * (s[0] - 0.02), yp2, s[2] + P["gunwale"]["top_above_sheer"]))
            if op.get("pose", "rowing") == "stowed":
                # 収めた姿：船梁の上に船の軸と平行に寝かせる（2 本の船梁の上面を結ぶ線の上）。羽（blade）は船尾の側
                sw = op["stowed"]
                ya = sw["y_start"] + sw["y_jitter"][len(oar_rows) % len(sw["y_jitter"])]
                total = op["inboard_length"] + op["outboard_length"]
                xo = side * sw["x_offsets"][lab][k]
                (yb1, yb2) = sw["rest_beams_y"]
                zt1 = sheer(yb1) - P["beams"]["below_sheer"] + op["shaft_radius"] + 0.005
                zt2 = sheer(yb2) - P["beams"]["below_sheer"] + op["shaft_radius"] + 0.005
                zl = lambda yy: zt1 + (zt2 - zt1) * (yy - yb1) / (yb2 - yb1)  # noqa: E731
                a = Vector((xo, ya, zl(ya)))
                c = Vector((xo, ya + total, zl(ya + total)))
                d = (c - a).normalized()
                bsh = c - d * op["blade_length"]
            else:
                d = Vector((side * d0[0], d0[1], d0[2])).normalized()
                a = piv - d * op["inboard_length"]
                bsh = piv + d * (op["outboard_length"] - op["blade_length"])
                c = piv + d * op["outboard_length"]
            wv = d.cross(Vector((0, 0, 1))).normalized()
            tv = wv.cross(d).normalized()
            ob_ = MeshBuf()
            # 櫓杭（ろぐい）：船縁の上の支点の小さな杭（漕ぐ姿のときの支点。収めた姿でも船縁に残す）
            ob_.box(tuple(piv + Vector((0, 0, 0.03))), (0.05, 0.05, 0.08))
            n8 = 8
            rr = []
            for q in (a, bsh):
                rr.append([ob_.add(q + (wv * math.cos(2 * math.pi * t / n8) + tv * math.sin(2 * math.pi * t / n8)) * op["shaft_radius"]) for t in range(n8)])
            for t in range(n8):
                ob_.face((rr[0][t], rr[0][(t + 1) % n8], rr[1][(t + 1) % n8], rr[1][t]))
            ob_.face(tuple(reversed(rr[0])))
            ob_.face(tuple(rr[1]))
            mid = 0.5 * (bsh + c)
            ob_.box(tuple(mid), (op["blade_width"], op["blade_length"], op["blade_thickness"]), basis=[tuple(wv), tuple(d), tuple(tv)])
            nm = "Boat41_Oar_%s%d" % (lab, k + 1)
            objs[nm] = make_object(nm, ob_, oar_m, "櫓（ろ）と櫓杭。%s、支点は船縁の上。姿は %s" % ("右舷" if lab == "S" else "左舷", op.get("pose", "rowing")),
                                   props={"pivot_blender": list(piv), "side": "starboard" if lab == "S" else "port"})
            oar_rows.append({"name": nm, "pivot": [round(v, 4) for v in piv], "blade_tip": [round(v, 4) for v in c]})

    # 8) 衝突形状（3 つの凸包）
    col_rows = []
    for k, (u0, u1) in enumerate(P["collision"]["pieces_u"]):
        pts = []
        for u, s in zip(us, secs):
            if u0 - 1e-9 <= u <= u1 + 1e-9:
                pts.extend(s)
        if k == 0:
            pts.append(tuple(tip))
        me = bpy.data.meshes.new("col%d" % k)
        bm = bmesh.new()
        for p in pts:
            bm.verts.new(p)
        res = bmesh.ops.convex_hull(bm, input=list(bm.verts))
        drop = list({id(v): v for v in list(res.get("geom_interior", [])) + list(res.get("geom_unused", []))
                     if isinstance(v, bmesh.types.BMVert)}.values())
        if drop:
            bmesh.ops.delete(bm, geom=drop, context='VERTS')
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.verts.index_update()
        buf = MeshBuf()
        buf.v = [tuple(v.co) for v in bm.verts]
        buf.f = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        nm = "Boat41_Col_" + ("Bow", "Mid", "Stern")[k]
        objs[nm] = make_object(nm, buf, helper, "衝突形状（凸包 %d/3、u %.2f〜%.2f）。Unity では MeshCollider（convex）で、描画しない" % (k + 1, u0, u1))
        col_rows.append({"name": nm, "u": [u0, u1], "triangles": len(buf.f), "vertices": len(buf.v)})

    # 9) 浮力用の船体（外面を舷の上縁でふさいだ閉じた形）
    bu = MeshBuf()
    bidx = [[bu.add(p, merge=True) for p in s] for s in secs]
    for i in range(NST - 1):
        for j in range(7):
            j1 = (j + 1) % 7
            bu.face((bidx[i][j], bidx[i][j1], bidx[i + 1][j1], bidx[i + 1][j]))
    bu.face(list(reversed(bidx[-1])))
    objs["Boat41_Buoyancy"] = make_object("Boat41_Buoyancy", bu, helper, "浮力用の船体（閉じた形、舷の上縁まで）。Unity では描画しない（設計42 の排水容積の元）")

    bpy.context.view_layer.update()
    return objs, {"floor": floor_rows, "beams": beam_rows, "oars": oar_rows, "collision": col_rows}


# ---------------------------------------------------------------- 測定
def world_verts(ob):
    m = ob.matrix_world
    return np.array([tuple(m @ v.co) for v in ob.data.vertices], np.float64)


def measure_all():
    out = {}
    for ob in sorted(bpy.data.objects, key=lambda o: o.name):
        if ob.type != 'MESH':
            continue
        V = world_verts(ob)
        out[ob.name] = {"vertices": len(ob.data.vertices), "polygons": len(ob.data.polygons),
                        "min": V.min(0).round(6).tolist(), "max": V.max(0).round(6).tolist(), "centroid": V.mean(0).round(6).tolist(),
                        "location": list(ob.location), "rotation_euler": list(ob.rotation_euler), "scale": list(ob.scale),
                        "materials": [m.name for m in ob.data.materials if m]}
    return out


def compare(a, b):
    worst = 0.0
    names_ok = sorted(a) == sorted(b)
    for k in a:
        if k not in b:
            continue
        for key in ("min", "max", "centroid"):
            worst = max(worst, float(np.abs(np.array(a[k][key]) - np.array(b[k][key])).max()))
    return {"names_match": names_ok, "max_abs_diff_m": worst, "pass": names_ok and worst < 1e-4}


def mesh_checks(ob, closed):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    vol = bm.calc_volume(signed=True) if closed else None
    bm.free()
    return {"non_manifold_edges": nonman, "boundary_edges": boundary, "degenerate_faces": degenerate,
            "signed_volume": None if vol is None else round(vol, 6)}


def outward_fraction(ob):
    """船殻の面の法線が船の中心線（x = 0、その断面の高さの中ほど）から外を向く割合。"""
    me = ob.data
    good = tot = 0
    for p in me.polygons:
        c = p.center
        u = u_for_y(c.y, 0.5)
        s = section(u)
        zc = 0.5 * (s[0][2] + s[3][2]) + 0.35 * (s[3][2] - s[0][2])
        r = Vector((c.x, 0.0, c.z - zc))
        if r.length < 1e-6 or abs(c.y) > 4.2:
            continue
        tot += 1
        good += 1 if p.normal.dot(r) > 0 else 0
    return {"faces_checked": tot, "outward": good, "fraction": round(good / max(1, tot), 4)}


def hydrostatics(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    tree = BVHTree.FromBMesh(bm)
    vol_mesh = bm.calc_volume(signed=True)
    bm.free()
    step = P["buoyancy"]["grid_step"]
    xs = np.arange(-W - 0.1 + step / 2, W + 0.1, step)
    ys = np.arange(-5.2 + step / 2, 5.2, step)
    cols = []
    for y in ys:
        for x in xs:
            h1 = tree.ray_cast(Vector((x, y, -2.0)), Vector((0, 0, 1)))
            if h1[0] is None:
                continue
            h2 = tree.ray_cast(Vector((x, y, 4.0)), Vector((0, 0, -1)))
            if h2[0] is None or h2[0].z <= h1[0].z:
                continue
            cols.append((x, y, h1[0].z, h2[0].z))
    C = np.array(cols)
    dA = step * step
    full = float(((C[:, 3] - C[:, 2]) * dA).sum())
    rows = []
    for d in P["buoyancy"]["drafts"]:
        hgt = np.clip(np.minimum(d, C[:, 3]) - C[:, 2], 0, None)
        v = float((hgt * dA).sum())
        wp = float(((C[:, 2] < d) & (C[:, 3] > d)).sum() * dA)
        if v > 0:
            lcb = float((C[:, 1] * hgt).sum() * dA / v)
            vcb = float((((C[:, 2] + np.minimum(d, C[:, 3])) / 2) * hgt).sum() * dA / v)
        else:
            lcb = vcb = None
        rows.append({"draft_units": d, "volume_units3": round(v, 5), "waterplane_area_units2": round(wp, 5),
                     "lcb_y_blender": None if lcb is None else round(lcb, 4), "vcb_z": None if vcb is None else round(vcb, 4)})
    return {"closed_mesh_volume_units3": round(vol_mesh, 5), "column_integral_volume_units3": round(full, 5),
            "volume_agreement_rel": round(abs(full - vol_mesh) / vol_mesh, 5), "grid_step_units": step, "columns": int(len(C)), "table": rows,
            "note_ja": "水面は船の局所の水平面 z = 喫水（縦・横の傾き 0）。実寸は 船の縮尺 s を掛けて：長さ ×s、面積 ×s²、容積 ×s³。"}


def render_previews(out):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'MATERIAL'
    sh.show_object_outline = True
    sh.show_cavity = True
    sh.cavity_type = 'BOTH'
    sc.world = bpy.data.worlds.new("QA_World")
    sc.world.color = (.73, .71, .65)
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.render.image_settings.file_format = 'PNG'
    cd = bpy.data.cameras.new("QA_Cam")
    cam = bpy.data.objects.new("QA_Cam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    hide = [o for o in bpy.data.objects if o.name.startswith("Boat41_Col_") or o.name == "Boat41_Buoyancy"]
    files = []
    views = [("side_port", (14, 0, 0.9), (0, 0, 0.9), 'ORTHO', 11.5),
             ("top", (0, 0, 14), (0, 0, 0), 'ORTHO', 11.5),
             ("three_quarter_bow", (7.5, -9.5, 5.5), (0, -0.5, 0.6), 'PERSP', 0),
             ("inside_from_stern", (0.0, 7.8, 3.0), (0, -1.0, 0.4), 'PERSP', 0)]
    for mode in ("visual", "helpers"):
        for o in bpy.data.objects:
            if o.type == 'MESH':
                is_h = o in hide
                o.hide_render = (is_h if mode == "visual" else not is_h)
        for name, loc, tgt, typ, osc in (views if mode == "visual" else views[:3]):
            cam.location = loc
            cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
            cd.type = typ
            if typ == 'ORTHO':
                cd.ortho_scale = osc
            else:
                cd.lens = 35
            if name == "top":
                cam.rotation_euler = (0, 0, math.pi / 2)
            p = os.path.join(out, "preview_%s_%s.png" % (mode, name))
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            files.append(p)
    for o in bpy.data.objects:
        o.hide_render = False
    bpy.data.objects.remove(cam)
    return files


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def research_input():
    out = {}
    for rp in (P.get("research_input", {}).get("path"), "Unity/Build/Design/41/research/dims.json"):
        if rp:
            ap = os.path.join(REPO, rp)
            out[rp] = {"sha256": sha(ap), "bytes": os.path.getsize(ap)} if os.path.exists(ap) else "無い"
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    reset()
    objs, tables = build()
    for ob in objs.values():
        assert max(abs(c) for c in ob.location) < 1e-12 and max(abs(c) for c in ob.rotation_euler) < 1e-12
    src = measure_all()
    # 両端の先端（置き方の枠の点）が頂点として在ること
    allv = np.concatenate([world_verts(o) for o in objs.values() if not (o.name.startswith("Boat41_Col") or o.name == "Boat41_Buoyancy")])
    tips = {}
    for key in ("bow_tip_blender", "stern_tip_blender"):
        t = np.array(P["frame"][key])
        dd = np.linalg.norm(allv - t, axis=1)
        tips[key] = {"target": t.tolist(), "nearest_vertex_distance": float(dd.min())}
    ext = {"x": [float(allv[:, 0].min()), float(allv[:, 0].max())], "y": [float(allv[:, 1].min()), float(allv[:, 1].max())],
           "z": [float(allv[:, 2].min()), float(allv[:, 2].max())]}
    checks = {"hull_outward_normals": outward_fraction(objs["Boat41_Hull"]),
              "buoyancy_closed": mesh_checks(objs["Boat41_Buoyancy"], True),
              "collision_closed": {n: mesh_checks(objs[n], True) for n in objs if n.startswith("Boat41_Col_")},
              "hull_open_sheet": mesh_checks(objs["Boat41_Hull"], False)}
    hyd = hydrostatics(objs["Boat41_Buoyancy"])
    # 部品ごとの頂点と三角形（Python の座席と船縁の関係・Unity の照合に使う）
    geom = {}
    for n, ob in objs.items():
        me = ob.data
        me.calc_loop_triangles()
        geom[n + "__v"] = world_verts(ob).astype(np.float32)
        geom[n + "__t"] = np.array([tuple(t.vertices) for t in me.loop_triangles], np.int32)
    np.savez_compressed(os.path.join(OUT, "ds41_boat_geom.npz"), **geom)
    blend = os.path.join(OUT, "ds41_oshiokuri.blend")
    fbx = os.path.join(OUT, "ds41_oshiokuri.fbx")
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objs.values():
        ob.select_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    assert 'FINISHED' in bpy.ops.export_scene.fbx(filepath=fbx, **EXPORT_FLAGS)
    previews = render_previews(OUT)
    # 往復：blend を開き直す、FBX を空の場面へ読み直す
    reset()
    bpy.ops.wm.open_mainfile(filepath=blend)
    saved = measure_all()
    rt_blend = compare({k: v for k, v in src.items()}, {k: v for k, v in saved.items() if k in src})
    reset()
    assert 'FINISHED' in bpy.ops.import_scene.fbx(filepath=fbx, **IMPORT_FLAGS)
    bpy.context.view_layer.update()
    imp = measure_all()
    rt_fbx = compare(src, {k: v for k, v in imp.items() if k in src})
    # 断面の表（座席の目と船縁の関係の計算に使う）
    st = []
    for i in range(NST):
        u = i / (NST - 1)
        s = section(u)
        st.append({"u": round(u, 5), "bottom_center": [round(c, 5) for c in s[0]], "chine": [round(c, 5) for c in s[1]],
                   "knuckle": [round(c, 5) for c in s[2]], "sheer": [round(c, 5) for c in s[3]]})
    bpts = []
    for yb in P["buoyancy"]["points_y"]:
        u = u_for_y(yb, 0.0)
        s = section(u)
        for sx in (-1, 1):
            p = (sx * P["buoyancy"]["points_x_fraction_of_bottom"] * s[1][0], s[1][1], s[1][2])
            bpts.append({"blender": [round(c, 5) for c in p], "unity_local": [round(-p[0], 5), round(p[2], 5), round(-p[1], 5)]})
    report = {
        "schema": "GreatWave.DS41.blender_report/1", "number": "設計41", "created_utc": datetime.now(timezone.utc).isoformat(),
        "software": {"blender": bpy.app.version_string, "build_hash": bpy.app.build_hash.decode("ascii")},
        "params": {"path": os.path.relpath(PARAMS, REPO).replace("\\", "/"), "sha256": sha(PARAMS), "values": P},
        "research_input": research_input(),
        "coordinates": {"unit": "placement frame（先端間 10）", "handedness": "right", "up": "+Z", "boat_forward": "-Y",
                        "blender_to_unity": "(x, y, z) -> (-x, z, -y)（設計07 の実測）", "origin": "竜骨の中央（船底の中央、z = 0）"},
        "derived_units": {"half_beam_max": W, "depth_mid": D, "bottom_half_width_max": BF * W, "extent_visual_blender": ext},
        "tips": tips, "objects": src, "tables": tables, "stations": st, "hydrostatics": hyd, "buoyancy_points": bpts,
        "checks": checks, "export_flags": {k: sorted(v) if isinstance(v, set) else v for k, v in EXPORT_FLAGS.items()},
        "reimport_flags": IMPORT_FLAGS, "roundtrip": {"blend_reopen": rt_blend, "fbx_reimport": rt_fbx},
        "files": {}, "unity_validation": "NOT_RUN（DS41Boats.ImportCheck で行う）", "hmd_validation": "NOT_RUN"}
    ok = (rt_blend["pass"] and rt_fbx["pass"] and all(v["nearest_vertex_distance"] < 1e-5 for v in tips.values())
          and checks["buoyancy_closed"]["non_manifold_edges"] == 0 and checks["buoyancy_closed"]["signed_volume"] > 0
          and all(c["non_manifold_edges"] == 0 for c in checks["collision_closed"].values())
          and checks["hull_outward_normals"]["fraction"] > 0.98)
    report["pass"] = bool(ok)
    for p in [os.path.abspath(__file__), PARAMS, blend, fbx, os.path.join(OUT, "ds41_boat_geom.npz")] + previews:
        report["files"][os.path.basename(p)] = {"bytes": os.path.getsize(p), "sha256": sha(p)}
    with open(os.path.join(OUT, "ds41_blender_report.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("DS41_BLENDER_" + ("PASS" if ok else "FAIL") + " " + json.dumps({"tips": tips, "rt_fbx": rt_fbx, "rt_blend": rt_blend,
                                                                            "checks": checks, "volume": hyd["closed_mesh_volume_units3"]}, ensure_ascii=False))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
