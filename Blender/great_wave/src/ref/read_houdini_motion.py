"""Houdini の参照キャッシュ 1.abc から運動を読み取る（仕様6.1・6.2）。

キャッシュは運動だけの参照資料であり、その形状を新しい波には使わない。

画面なしでの実行例:
    & tools/run_blender.ps1 src/ref/read_houdini_motion.py -Prefix REF
    任意: -ScriptArgs '--stage','measure'   （走査と各フレームの測定を生データに出力）
          -ScriptArgs '--stage','analyze'   （生データから段階・グラフ・JSONを生成。Alembicは不要）
          -ScriptArgs '--stage','render'    （数フレームを Workbench で斜めから確認）
          -ScriptArgs '--frames','40','55'  （指定範囲の短い確認。作業用ディレクトリだけに出力）

各シーンフレームを共通ライブラリ（gw.silhouette / gw.profile_metrics）で測り、
新しい波の曲線と直接比較できるようにする（仕様6.4）。測定対象は次の2種類。
  * 'full': 流体の塊全体を +Y 方向に投影した側面輪郭。
            CAM_print に相当する視点で、gw.silhouette の正確なモードを使う。
  * 'section': 固定平面 Y=y_section と閉じた流体の塊の真の交線。
            y_section は最終フレームの最も高い峰の Y。
            共通ライブラリに断面関数がないため、ここで平面切断と偶奇則の塗りから
            マスクを作り、gw.silhouette.extract_profile と
            gw.profile_metrics.measure_profile に渡す。
長さは最終形状の静水面からの峰高 H_ref で正規化する。

出力先: target/houdini_motion.json、results/step1_prepare/houdini_ref/*.png|npz|json。
"""
import argparse
import hashlib
import math
import os
import sys
import time

import numpy as np

_SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
from gw import bootstrap, paths, imgio, draw, plot, raster, silhouette  # noqa: E402
from gw import profile_metrics as pm  # noqa: E402

PARAMS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "read_houdini_motion_params.json")
OUT_JSON = os.path.join(paths.TARGET_DIR, "houdini_motion.json")
log = bootstrap.log


def P(name):
    return paths.param(name, PARAMS_JSON)


_QUICK_DIR = None


def out_dir():
    """通常は results/step1_prepare/houdini_ref、--frames の短い検査では作業用ディレクトリ。"""
    if _QUICK_DIR is not None:
        return paths.ensure_dir(_QUICK_DIR)
    return paths.step1_dir("houdini_ref")


def opath(name):
    return os.path.join(out_dir(), name)


# ====================================================================== Alembic の読込
class AbcReader:
    """1.abc を画面なしで読み込み、各フレームの評価済み三角形群をワールド座標で得る。"""

    def __init__(self):
        import bpy
        self.bpy = bpy
        self.scene = bootstrap.reset_scene()
        t0 = time.perf_counter()
        self.path = paths.houdini_abc_path()
        bpy.ops.wm.alembic_import(filepath=self.path, as_background_job=False)
        self.objs = [o for o in self.scene.objects if o.type == "MESH"]
        if not self.objs:
            raise RuntimeError("no mesh object after the Alembic import")
        self.import_seconds = time.perf_counter() - t0
        self.fps = self.scene.render.fps / self.scene.render.fps_base
        self.info = {"objects": [o.name for o in self.objs],
                     "modifiers": [[m.type for m in o.modifiers] for o in self.objs],
                     "scene_fps": self.fps, "scene_frame_range": [self.scene.frame_start, self.scene.frame_end],
                     "import_seconds": self.import_seconds}

    def mesh(self, frame):
        """ワールド座標の頂点 float64 (N,3) と三角形番号 int64 (M,3) を返す。
        共通ライブラリの取得処理（scene.frame_set、評価済み依存グラフ、foreach_get）を使う。"""
        self.scene.frame_set(int(frame))
        verts, tris, _info = silhouette.mesh_world_triangles(self.objs)
        return verts, tris


def real_triangles(verts, tris):
    """3頂点が同一の埋め草の三角形を除く。キャッシュは一定の頂点数に合わせており、
    不要な三角形は原点に畳まれている。"""
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    deg = (a == b).all(axis=1) & (b == c).all(axis=1)
    return tris[~deg], int(deg.sum())


# ====================================================================== 平面切断と断面マスク
def plane_cut_segments(verts, tris, yc):
    """三角形群と平面 Y=yc の交線を求める。
    戻り値はワールド座標 (X, Z) の線分 (N, 2, 2)。平面上の頂点は正側とみなす。
    辺との交点は常に正側の頂点から負側へ補間する。共有辺を持つ2つの三角形から
    ビット単位で同じ交点を得られ、閉じた輪郭が開かない。"""
    T = verts[tris]                                  # (M, 3, 3)
    d = T[:, :, 1] - float(yc)
    s = d >= 0.0
    cnt = s.sum(axis=1)
    sel = (cnt == 1) | (cnt == 2)
    T, d, s, cnt = T[sel], d[sel], s[sel], cnt[sel]
    if T.shape[0] == 0:
        return np.zeros((0, 2, 2))
    lone = np.where(cnt == 1, np.argmax(s, axis=1), np.argmin(s, axis=1))
    r = np.arange(T.shape[0])
    out = []
    for other in ((lone + 1) % 3, (lone + 2) % 3):
        pa, pb = T[r, lone], T[r, other]
        da, db = d[r, lone], d[r, other]
        swap = ~s[r, lone]                           # 'a' を正側の頂点にする。
        pa2 = np.where(swap[:, None], pb, pa)
        pb2 = np.where(swap[:, None], pa, pb)
        da2 = np.where(swap, db, da)
        db2 = np.where(swap, da, db)
        t = da2 / (da2 - db2)
        q = pa2 + t[:, None] * (pb2 - pa2)
        out.append(q[:, [0, 2]])
    return np.stack(out, axis=1)


def open_end_count(segs, decimals=6):
    """奇数回現れる線分端点の数を返す。閉じた輪郭では0。"""
    if segs.shape[0] == 0:
        return 0
    pts = np.round(segs.reshape(-1, 2), decimals)
    _u, c = np.unique(pts, axis=0, return_counts=True)
    return int((c % 2 == 1).sum())


def evenodd_mask(seg_px, w, h):
    """順序のない線分群として与えた閉じた輪郭を偶奇則で塗る。画素座標では Y は下向き。
    各線分は中心が [x0, x1) にある列で、その線分より下の画素の内外を反転する。
    全反転回数の偶奇が輪郭内を示す。画素中心の標本化は gw.raster と同じ規約。"""
    if seg_px.shape[0] == 0:
        return np.zeros((h, w), bool)
    x0, y0 = seg_px[:, 0, 0], seg_px[:, 0, 1]
    x1, y1 = seg_px[:, 1, 0], seg_px[:, 1, 1]
    sw = x1 < x0
    x0, x1 = np.where(sw, x1, x0), np.where(sw, x0, x1)
    y0, y1 = np.where(sw, y1, y0), np.where(sw, y0, y1)
    ia = np.ceil(x0 - 0.5).astype(np.int64)
    ib = np.ceil(x1 - 0.5).astype(np.int64)           # 終端を含まない。
    ia_c, ib_c = np.clip(ia, 0, w), np.clip(ib, 0, w)
    n = np.maximum(ib_c - ia_c, 0)
    tot = int(n.sum())
    if tot == 0:
        return np.zeros((h, w), bool)
    idx = np.repeat(np.arange(n.size), n)
    col = ia_c[idx] + (np.arange(tot) - np.repeat(np.cumsum(n) - n, n))
    xc = col + 0.5
    t = (xc - x0[idx]) / (x1[idx] - x0[idx])
    yl = y0[idx] + t * (y1[idx] - y0[idx])
    j = np.clip(np.floor(yl - 0.5).astype(np.int64) + 1, 0, h)
    D = np.zeros((h + 1, w), np.int32)
    np.add.at(D, (j, col), 1)
    return (np.cumsum(D[:h], axis=0) & 1).astype(bool)


def section_profile(verts, tris, yc, rect, water_z):
    """閉じた流体の塊の断面 Y=yc を求め、(断面の辞書, マスク, 情報) を返す。"""
    t0 = time.perf_counter()
    segs = plane_cut_segments(verts, tris, yc)
    x, y = rect.world_to_px(segs[..., 0], segs[..., 1])
    mask = evenodd_mask(np.stack([x, y], axis=-1), rect.width_px, rect.height_px)
    # 流体そのものの上面を X 方向0.5 m ごとの区間の上側包絡線として求める。
    # 測定矩形で切らず、水の層でも隠さないため、静水面より下の谷も見える。
    # 区間は三角形の辺（約0.17 m）より十分広く、上面線分の端点を含む。
    bw = 0.5
    if segs.shape[0]:
        pts_all = segs.reshape(-1, 2)
        xb0 = math.floor(pts_all[:, 0].min() / bw) * bw
        nb = int(math.ceil((pts_all[:, 0].max() - xb0) / bw)) + 1
        kbin = np.clip(((pts_all[:, 0] - xb0) / bw).astype(np.int64), 0, nb - 1)
        zs_top = np.full(nb, -np.inf)
        np.maximum.at(zs_top, kbin, pts_all[:, 1])
        zs_top = np.where(np.isfinite(zs_top), zs_top, np.nan)
        xs_top = xb0 + (np.arange(nb) + 0.5) * bw
    else:
        xs_top, zs_top = np.zeros(0), np.zeros(0)
    area_above = None
    if water_z is not None:
        y_w = float(rect.world_to_px(0.0, float(water_z))[1])
        jw = int(np.clip(math.ceil(y_w - 0.5 - 1e-9), 0, rect.height_px))
        area_above = int(mask[:jw].sum())
        raster.fill_below(mask, y_w)
    prof = silhouette.extract_profile(mask, rect, edges=None)
    info = {"n_segments": int(segs.shape[0]), "n_open_ends": open_end_count(segs),
            "area_above_water_px": area_above, "seconds": time.perf_counter() - t0,
            "top_surface_x_m": xs_top, "top_surface_z_m": zs_top}
    return prof, mask, info


def top_envelope(mask, rect, water_z):
    """各画素列で最も上の塗られた画素中心のワールド Z を返す。水だけなら NaN。"""
    h, w = mask.shape
    y_w = float(rect.world_to_px(0.0, float(water_z))[1])
    jw = int(np.clip(math.ceil(y_w - 0.5 - 1e-9), 0, h))
    sub = mask[:jw]
    has = sub.any(axis=0)
    jtop = np.argmax(sub, axis=0)
    X, _z = rect.px_to_world(np.arange(w) + 0.5, np.zeros(w))
    _x, Z = rect.px_to_world(np.zeros(w), jtop.astype(np.float64))      # その画素の上端。
    return X, np.where(has, Z, np.nan)


def envelope_check(verts, tris, yc, width, rect, water_z, mask_section):
    """平面切断のラスタ化と共通ライブラリを比較する。
    断面マスクの上側包絡線（各列の最上部の画素）と、切断平面の周囲にある薄い三角形層の
    gw.silhouette マスクの上側包絡線を比べる。キャッシュは薄い流体の殻であり、
    その一層は内部が塗られない開いた帯になるため、断面全体で比較できない。
    追跡した輪郭は意味を持たず、上端だけが有効。"""
    cy = verts[:, 1][tris].mean(axis=1)
    keep = np.abs(cy - yc) <= 0.5 * width
    mask_slab, _info = silhouette.mask_from_triangles(verts, tris[keep], rect, water_z=water_z, exact=False)
    _X, za = top_envelope(mask_section, rect, water_z)
    _X, zb = top_envelope(mask_slab, rect, water_z)
    both = np.isfinite(za) & np.isfinite(zb) & (za > water_z + 0.05) & (zb > water_z + 0.05)
    d = (zb - za)[both]
    px = 1.0 / rect.px_per_unit_z
    far = np.abs(d) > 0.2
    X = _X[both]
    return {"n_columns": int(both.sum()), "abs_median_m": float(np.median(np.abs(d))), "abs_p90_m": float(np.percentile(np.abs(d), 90)),
            "slab_minus_section_mean_of_close_columns_m": float(d[~far].mean()),
            "frac_columns_differing_more_than_0p2m": float(far.mean()),
            "x_range_of_those_columns_m": [float(X[far].min()), float(X[far].max())] if far.any() else None,
            "note": "columns differing by more than 0.2 m are columns where the slab strip is seen exactly edge-on (planar flat top) "
                    "or where the slab's slightly more forward nose covers the face below; see docs",
            "pixel_m": px, "slab_width_m": float(width)}


def selftest_plane_cut():
    """plane_cut_segments と evenodd_mask の解析的な検査。
    球と球殻を平面で切ると、画素中心標本化では円盤と円環にラスタ化されるはず。"""
    def sphere(R, c, nu=240, nv=480):
        th = np.linspace(0.0, math.pi, nu + 1)
        ph = np.linspace(0.0, 2.0 * math.pi, nv + 1)[:-1]
        T, Ph = np.meshgrid(th, ph, indexing="ij")
        v = np.stack([c[0] + R * np.sin(T) * np.cos(Ph), c[1] + R * np.cos(T), c[2] + R * np.sin(T) * np.sin(Ph)], axis=-1)
        idx = np.arange((nu + 1) * nv).reshape(nu + 1, nv)
        a, b = idx[:-1, :], idx[1:, :]
        a2, b2 = np.roll(a, -1, axis=1), np.roll(b, -1, axis=1)
        tris = np.concatenate([np.stack([a, b, b2], -1).reshape(-1, 3), np.stack([a, b2, a2], -1).reshape(-1, 3)])
        return v.reshape(-1, 3), tris
    c = (1.0, 0.4, 2.5)
    rect = silhouette.ViewRect.from_bounds(-4.0, 6.0, -2.0, 7.0, px_per_unit=100.0)
    yc = 1.2
    out = {}
    xs, zs = rect.px_to_world(np.arange(rect.width_px) + 0.5, np.arange(rect.height_px) + 0.5)
    XX, ZZ = np.meshgrid(xs, zs)
    rr = np.hypot(XX - c[0], ZZ - c[2])
    for name, radii in (("sphere", (3.0,)), ("shell", (3.0, 2.0))):
        vs, ts, base = [], [], 0
        for R in radii:
            v, t = sphere(R, c)
            vs.append(v)
            ts.append(t + base)
            base += v.shape[0]
        v, t = np.concatenate(vs), np.concatenate(ts)
        segs = plane_cut_segments(v, t, yc)
        x, y = rect.world_to_px(segs[..., 0], segs[..., 1])
        m = evenodd_mask(np.stack([x, y], axis=-1), rect.width_px, rect.height_px)
        r = [math.sqrt(R * R - (yc - c[1]) ** 2) for R in radii]
        ref = rr <= r[0]
        if len(r) > 1:
            ref &= rr >= r[1]
        diff = m != ref
        near = np.zeros_like(diff)
        for ri in r:
            near |= np.abs(rr - ri) < 0.02 / 100.0 * 5        # 多角形の弦による誤差として円から0.1 px 以内。
        out[name] = {"n_segments": int(segs.shape[0]), "n_open_ends": open_end_count(segs), "area_px": int(m.sum()),
                     "analytic_area_px": float(math.pi * (r[0] ** 2 - (r[1] ** 2 if len(r) > 1 else 0.0)) * 100.0 ** 2),
                     "n_px_differ": int(diff.sum()), "n_px_differ_not_on_boundary": int((diff & ~near).sum()),
                     # 検査用メッシュは多角形の球なので、切断線は真円より最大約0.02 px 内側にある。
                     # この帯内の一部の画素中心だけは異なり得るため、周長（px）の5%まで許し、他は許さない。
                     "n_px_differ_allowed": int(math.ceil(0.05 * sum(2.0 * math.pi * ri * 100.0 for ri in r)))}
    ok = all(o["n_open_ends"] == 0 and o["n_px_differ_not_on_boundary"] == 0 and o["n_px_differ"] <= o["n_px_differ_allowed"]
             for o in out.values())
    out["ok"] = bool(ok)
    return out


# ====================================================================== 補助処理
def make_rect(ppm, H=1.0, x0=0.0, z0=0.0, name="houdini"):
    r = P("view_rect_m")
    return silhouette.ViewRect.from_bounds(r["x_min"], r["x_max"], r["z_min"], r["z_max"],
                                           width_px=int(round((r["x_max"] - r["x_min"]) * ppm)),
                                           mirror_x=False, H=H, x0=x0, z0=z0, name=name)


def crest_along_y(verts, y_edges, z_floor):
    """Y 区間ごとの最大 Z と、その最大値から5 cm以内の頂点の平均 X を返す。峰の X を安定させる。"""
    yb = np.digitize(verts[:, 1], y_edges) - 1
    nb = len(y_edges) - 1
    ok = (yb >= 0) & (yb < nb) & (verts[:, 2] > z_floor)
    zmax = np.full(nb, np.nan)
    xat = np.full(nb, np.nan)
    if not ok.any():
        return zmax, xat
    yb, v = yb[ok], verts[ok]
    order = np.argsort(yb, kind="stable")
    yb, v = yb[order], v[order]
    starts = np.searchsorted(yb, np.arange(nb), "left")
    ends = np.searchsorted(yb, np.arange(nb), "right")
    for k in range(nb):
        if ends[k] > starts[k]:
            q = v[starts[k]:ends[k]]
            zm = q[:, 2].max()
            zmax[k] = zm
            top = q[q[:, 2] >= zm - 0.05]
            xat[k] = top[:, 0].mean()
    return zmax, xat


def metrics_row(m, prof, extra=None):
    """measure_profile と断面の信頼性情報から JSON に保存できる平坦な1行を作る。"""
    lm = m["landmarks"]
    row = {
        "h": m["h"], "x_c": m["x_c"], "theta": m["theta"], "theta_raw": m["theta_raw"], "o": m["o"],
        "cavity_depth": m["cavity_depth"], "phi_deg": m["phi_deg"], "overhanging": m["overhanging"],
        "phi_truncated": None if m["phi"] is None else bool(m["phi"]["truncated"]),
        "crest_H": lm["crest"]["H"], "crest_plateau_width_pct_h": lm["crest_plateau"]["width_pct_h"],
        "tip_H": None if lm["head_tip"] is None else lm["head_tip"]["H"],
        "deepest_H": None if lm["inner_deepest"] is None else lm["inner_deepest"]["H"],
        "theta_point_H": lm["theta_point"]["H"],
        "trough_end_H": lm["trough_end"]["H"], "reached_still_water": lm["trough_end"]["reached_still_water"],
        "back_mid_max_deg": m["S4"].get("mid_max_deg"),
        "complete": bool(prof["complete"]), "end_border": prof["end_border"],
        "n_holes": int(prof["holes"]["n_holes"]), "hole_area_px": int(prof["holes"]["hole_area_px"]),
        "hole_area_frac": float(prof["holes"]["hole_area_frac"]),
        "n_components_dropped": int(prof["components"]["n_components"]) - 1,
        "dropped_area_px": int(prof["components"]["removed_area_px"]),
        "notes": list(m["notes"]),
    }
    if extra:
        row.update(extra)
    return row


def measure_guarded(pts_H, H_ref, x0, params=None):
    """流体の塊の端による誤測定を防ぎながら gw.profile_metrics.measure_profile を実行する。

    塊は X=+5.26 m で終わり、X=+4.85 m 付近から丸い角が始まる。
    初期フレームの全体輪郭では、さざ波の包絡線が静水面より数 cm 高いまま角まで続く。
    その結果、前面に含まれる角で theta（前面の最大傾斜）が波の代わりに測られる。
    最も急な点が端の領域にあり、峰はまだ離れている場合は、端の領域の開始位置で
    断面を切り直して theta を再測定する。h、x_c、o、phi には影響しない。
    (指標, 制限の情報または None) を返す。"""
    m = pm.measure_profile(pts_H, params)
    x_end = float(P("chunk_end_zone_x_m"))
    tp_x = m["landmarks"]["theta_point"]["H"][0] * H_ref + x0
    crest_x = m["x_c"] * H_ref + x0
    if tp_x <= x_end or crest_x >= x_end - float(P("chunk_end_guard_min_distance_m")):
        return m, None
    keep = (np.asarray(pts_H)[:, 0] * H_ref + x0) <= x_end
    m2 = pm.measure_profile(np.asarray(pts_H)[keep], params)
    guard = {"theta_with_chunk_end_deg": m["theta"], "theta_point_with_chunk_end_x_m": float(tp_x)}
    m["theta"], m["theta_raw"] = m2["theta"], m2["theta_raw"]
    m["landmarks"]["theta_point"] = m2["landmarks"]["theta_point"]
    return m, guard


def overlay_cell(mask, prof, m, title, max_w, crop_px=None, crop_scale=None):
    return silhouette.draw_overlay(mask, prof, m, title=title, max_w=max_w, crop_px=crop_px, crop_scale=crop_scale)


def color_ramp(v):
    """0..1 を濃青→シアン→黄→赤の RGB に変換する。NaN は薄灰色。"""
    v = np.asarray(v, dtype=np.float64)
    stops = np.array([[20, 30, 110], [0, 170, 200], [250, 225, 60], [215, 40, 30]], dtype=np.float64)
    t = np.clip(np.nan_to_num(v, nan=0.0), 0, 1) * (len(stops) - 1)
    i = np.clip(np.floor(t).astype(int), 0, len(stops) - 2)
    f = (t - i)[..., None]
    rgb = stops[i] * (1 - f) + stops[i + 1] * f
    rgb[np.isnan(v)] = (225, 225, 225)
    return np.rint(rgb).astype(np.uint8)


# ====================================================================== 第1段階: 測定
def stage_measure(frame_range=None):
    rd = AbcReader()
    log("import", rd.info)
    quick = frame_range is not None
    if quick:
        global _QUICK_DIR
        _QUICK_DIR = os.path.join(paths.RESULTS_DIR, "houdini_ref_quick")
    res = {"abc": {"path": paths.norm(rd.path), "size_bytes": os.path.getsize(rd.path), **rd.info}}
    st = selftest_plane_cut()
    log("plane-cut self-test", st)
    if not st["ok"]:
        raise RuntimeError("plane-cut rasteriser self-test failed: %r" % (st,))
    res["plane_cut_selftest"] = st

    # ---- A. 異なるデータを持つフレームを調べる。
    f0, f1 = P("scan_frames")
    scan = []
    with bootstrap.Timer("scan frames %d..%d" % (f0, f1)):
        for fr in range(f0, f1 + 1):
            v, t = rd.mesh(fr)
            h = hashlib.md5(np.ascontiguousarray(v.astype(np.float32)).tobytes()).hexdigest()
            t_real, n_pad = real_triangles(v, t)
            vv = v[np.unique(t_real)] if t_real.size else v
            scan.append({"frame": fr, "md5": h, "n_vertices": int(v.shape[0]), "n_triangles": int(t.shape[0]),
                         "n_padding_triangles": n_pad,
                         "bbox_min": [float(a) for a in vv.min(axis=0)], "bbox_max": [float(a) for a in vv.max(axis=0)]})
    first_of = {}
    for s in scan:
        first_of.setdefault(s["md5"], s["frame"])
        s["same_as_frame"] = first_of[s["md5"]]
    distinct = [s["frame"] for s in scan if s["same_as_frame"] == s["frame"]]
    rest_hash = scan[0]["md5"]
    rest_copies = [s["frame"] for s in scan if s["md5"] == rest_hash]
    last_distinct = max(distinct)
    log("distinct frames: %d (first %d, last %d); frames equal to frame %d: %d (%s..%s)"
        % (len(distinct), min(distinct), last_distinct, f0, len(rest_copies), rest_copies[1] if len(rest_copies) > 1 else "-",
           rest_copies[-1]))
    res["scan"] = {"frames": scan, "distinct_frames": distinct, "last_distinct_frame": last_distinct,
                   "frames_equal_to_first": rest_copies}
    frames = list(range(f0, last_distinct + 1))
    final_frame = last_distinct

    # ---- B. 静水面（フレーム f0）、頂点の対応、メッシュ解像度。
    v1, t1 = rd.mesh(f0)
    t1r, n_pad1 = real_triangles(v1, t1)
    vr = v1[np.unique(t1r)]
    top = vr[vr[:, 2] > 0.5 * (vr[:, 2].min() + vr[:, 2].max()), 2]
    z_still = float(np.median(top))
    res["still_water"] = {"frame": f0, "z_still_m": z_still, "top_z_pcts_1_5_50_95_99": [float(np.percentile(top, p)) for p in (1, 5, 50, 95, 99)],
                          "bottom_z_m": float(vr[:, 2].min()), "n_top_vertices": int(top.size),
                          "chunk_x_range_m": [float(vr[:, 0].min()), float(vr[:, 0].max())],
                          "chunk_y_range_m": [float(vr[:, 1].min()), float(vr[:, 1].max())]}
    log("still water z = %.4f m (frame %d, median of %d top-surface vertices, p1..p99 %s)"
        % (z_still, f0, top.size, ["%.4f" % a for a in res["still_water"]["top_z_pcts_1_5_50_95_99"]]))
    v2, t2 = rd.mesh(f0 + 1)
    v3, _t3 = rd.mesh(f0 + 2)
    d23 = np.linalg.norm(v3 - v2, axis=1)
    e = np.linalg.norm(v2[t2[:, 0]] - v2[t2[:, 1]], axis=1)
    res["topology"] = {"median_index_wise_vertex_displacement_frame2_to_3_m": float(np.median(d23)),
                       "median_triangle_edge_m": float(np.median(e[e > 0])),
                       "comment": "index-wise displacement >> edge length -> vertex i of frame t is NOT the same material point "
                                  "in frame t+1 (no fixed topology; the constant count comes from padding)"}
    log("topology", res["topology"])

    # ---- C. 最終形状: H_ref、x0、断面平面。
    vf, tf = rd.mesh(final_frame)
    tf, _ = real_triangles(vf, tf)
    rect1 = make_rect(P("px_per_m_key"), H=1.0, x0=0.0, z0=z_still)
    mask, info = silhouette.mask_from_triangles(vf, tf, rect1, water_z=z_still, exact=True)
    prof = silhouette.extract_profile(mask, rect1, edges=info["edges"])
    H_ref = float(prof["world"][:, 1].max() - z_still)
    rect2 = make_rect(P("px_per_m_key"), H=H_ref, x0=0.0, z0=z_still)
    m2 = pm.measure_profile(rect2.pts_px_to_H(prof["px"]))
    x0 = float(m2["x_c"] * H_ref)
    log("final frame %d: H_ref = %.4f m, crest X (robust) = %.4f m, plateau width %.2f %% of image height"
        % (final_frame, H_ref, x0, m2["landmarks"]["crest_plateau"]["width_pct_h"]))
    ybin = float(P("y_bin_m"))
    ylo, yhi = res["still_water"]["chunk_y_range_m"]
    y_edges = np.arange(math.floor(ylo), math.ceil(yhi) + 1e-9, ybin)
    y_mid = 0.5 * (y_edges[:-1] + y_edges[1:])
    zmax_f, _x = crest_along_y(vf, y_edges, z_still)
    k = max(1, int(round(float(P("y_smooth_m")) / ybin)))
    zs = np.convolve(np.nan_to_num(zmax_f, nan=z_still), np.ones(k) / k, mode="same")
    inner = (y_mid > ylo + P("y_wall_margin_m")) & (y_mid < yhi - P("y_wall_margin_m"))
    zs_in = np.where(inner, zs, -np.inf)
    y_auto = float(round(y_mid[int(np.argmax(zs_in))] / 0.25) * 0.25)
    y_sec = y_auto if P("section_y") == "auto" else float(P("section_y"))
    near = np.abs(zmax_f - np.nanmax(zmax_f)) <= 0.01 * H_ref
    res["final_pose"] = {"frame": final_frame, "H_ref_m": H_ref, "x0_m": x0, "z0_m": z_still,
                         "crest_plateau_width_pct_h": m2["landmarks"]["crest_plateau"]["width_pct_h"],
                         "section_y_m": y_sec, "section_y_auto_m": y_auto,
                         "y_range_within_1pct_H_of_max_m": [float(y_mid[near].min()), float(y_mid[near].max())]}
    log("section plane Y = %.2f m (auto %.2f); crest within 1%% H_ref of the max for Y in %s"
        % (y_sec, y_auto, res["final_pose"]["y_range_within_1pct_H_of_max_m"]))

    rect_full = make_rect(P("px_per_m_full"), H=H_ref, x0=x0, z0=z_still, name="houdini_full")
    rect_sec = make_rect(P("px_per_m_section"), H=H_ref, x0=x0, z0=z_still, name="houdini_section")
    rect_ms = make_rect(P("px_per_m_multi_section"), H=H_ref, x0=x0, z0=z_still, name="houdini_multi_section")
    rect_key = make_rect(P("px_per_m_key"), H=H_ref, x0=x0, z0=z_still, name="houdini_key")
    res["rects"] = {"full": rect_full.summary(), "section": rect_sec.summary(), "multi_section": rect_ms.summary(),
                    "key": rect_key.summary()}

    if quick:
        frames = [f for f in frames if frame_range[0] <= f <= frame_range[1]]
    wide = {"theta_window_pct_h": float(P("theta_wide_window_pct_h"))}
    ys_multi = [float(y) for y in P("multi_section_y_m")]
    every = int(P("contact_sheet_every"))
    sheet_frames = set(range(frames[0], frames[-1] + 1, every)) | {frames[-1]}
    zf0, zf1 = P("zoom_sheet_frames")
    zw = P("zoom_window_H")
    rows = {"full": [], "section": []}
    multi = {("%g" % y): [] for y in ys_multi}
    profs = {}
    crest_y = []
    cells = {"full": [], "section": [], "zoom_full": [], "zoom_section": []}
    slab_check = []
    top_plane = []
    prev = {"full": None, "section": None}
    dens_frames = set(P("density_frames"))
    dens_imgs = {}

    for fr in frames:
        tA = time.perf_counter()
        v, t = rd.mesh(fr)
        t, n_pad = real_triangles(v, t)
        tsec = (fr - frames[0]) / rd.fps if not quick else (fr - f0) / rd.fps
        # -- 全体の輪郭（共通ライブラリ、正確な方式）。
        mask_f, info_f = silhouette.mask_from_triangles(v, t, rect_full, water_z=z_still, exact=True)
        prof_f = silhouette.extract_profile(mask_f, rect_full, edges=info_f["edges"])
        info_f["edges"] = None
        m_f, g_f = measure_guarded(prof_f["H"], H_ref, x0)
        m_fw, _g = measure_guarded(prof_f["H"], H_ref, x0, wide)
        # -- 平面切断による断面。
        prof_s, mask_s, info_s = section_profile(v, t, y_sec, rect_sec, z_still)
        m_s, g_s = measure_guarded(prof_s["H"], H_ref, x0)
        m_sw, _g = measure_guarded(prof_s["H"], H_ref, x0, wide)
        # -- 断面平面上の実際の流体表面の谷。断面輪郭では水の層に隠される。
        xt, zt_ = info_s["top_surface_x_m"], info_s["top_surface_z_m"]
        crest_xw = m_s["x_c"] * H_ref + x0
        trough = {"back_trough_z_rel_still_H": None, "back_trough_x_H": None, "back_trough_at_left_limit": None,
                  "front_min_z_rel_still_H": None}
        if m_s["h"] >= float(P("h_visible_frac")):
            behind = (xt < crest_xw) & (xt > float(P("view_rect_m")["x_min"])) & np.isfinite(zt_)
            # 前方では波の最前点より完全に外にある区間だけを使う。
            # 張り出す波頭の下では上側包絡線は水面ではなく波頭自体になる。
            lead_xw = crest_xw if m_s["landmarks"]["head_tip"] is None else m_s["landmarks"]["head_tip"]["H"][0] * H_ref + x0
            ahead = (xt - 0.25 > max(crest_xw, lead_xw)) & np.isfinite(zt_) & (xt + 0.25 < float(P("chunk_end_zone_x_m")))
            if behind.any():
                kb_ = int(np.nanargmin(np.where(behind, zt_, np.nan)))
                trough["back_trough_z_rel_still_H"] = float((zt_[kb_] - z_still) / H_ref)
                trough["back_trough_x_H"] = float((xt[kb_] - x0) / H_ref)
                trough["back_trough_at_left_limit"] = bool(kb_ == int(np.nonzero(behind)[0][0]))
            if ahead.any():
                trough["front_min_z_rel_still_H"] = float((np.nanmin(zt_[ahead]) - z_still) / H_ref)
        for key, prof_k, m_k, m_w, extra in (("full", prof_f, m_f, m_fw, {"n_cracks_without_exact_data": prof_f["n_cracks_without_exact_data"],
                                                                         "chunk_end_guard": g_f}),
                                             ("section", prof_s, m_s, m_sw, dict(trough, n_open_ends=info_s["n_open_ends"], chunk_end_guard=g_s))):
            if prev[key] is None:
                d = {"max_H": None, "p95_H": None, "mean_H": None}
            else:
                d = pm.contour_displacement(prev[key], prof_k["H"], z_min_H=0.01)
            prev[key] = prof_k["H"]
            tip_x_m = None if m_k["landmarks"]["head_tip"] is None else m_k["landmarks"]["head_tip"]["H"][0] * H_ref + x0
            extra = dict(extra, frame=fr, t_s=tsec, theta_wide=m_w["theta"], disp_max_H=d["max_H"], disp_p95_H=d["p95_H"],
                         disp_mean_H=d["mean_H"], tip_x_m=tip_x_m,
                         tip_gap_to_frame_edge_m=None if tip_x_m is None else float(P("view_rect_m")["x_max"] - tip_x_m))
            rows[key].append(metrics_row(m_k, prof_k, extra))
            profs["%s_%03d" % (key, fr)] = prof_k["H"].astype(np.float32)
        # -- Y 方向の断面。峰線に沿った時間差を調べる。
        for y in ys_multi:
            try:
                pr, _mk, inf = section_profile(v, t, y, rect_ms, z_still)
                mm = pm.measure_profile(pr["H"])
                multi["%g" % y].append({"frame": fr, "h": mm["h"], "x_c": mm["x_c"], "theta": mm["theta"], "o": mm["o"],
                                        "phi_deg": mm["phi_deg"], "overhanging": mm["overhanging"],
                                        "complete": bool(pr["complete"]), "n_open_ends": inf["n_open_ends"]})
            except Exception as exc:                  # noqa: BLE001
                multi["%g" % y].append({"frame": fr, "error": repr(exc)})
        # -- 上面が切断による正確な水平面か調べる。上部0.15 mにある三角形で法線が
        #    鉛直から0.5度以内の面積と、上部頂点が最も集まる Z の2 mm区間を測る。
        vr = v[np.unique(t)]
        zt = float(vr[:, 2].max())
        T3 = v[t]
        nrm = np.cross(T3[:, 1] - T3[:, 0], T3[:, 2] - T3[:, 0])
        area = 0.5 * np.linalg.norm(nrm, axis=1)
        nz = np.abs(nrm[:, 2]) / np.maximum(2.0 * area, 1e-12)
        zc = T3[:, :, 2].mean(axis=1)
        hor = (nz > math.cos(math.radians(0.5))) & (zc > zt - 0.15)
        topv = vr[vr[:, 2] > zt - 0.15]
        hist, edges = np.histogram(topv[:, 2], bins=np.arange(zt - 0.15, zt + 0.0021, 0.002))
        kb = int(np.argmax(hist))
        selv = topv[(topv[:, 2] >= edges[kb]) & (topv[:, 2] < edges[kb + 1])]
        top_plane.append({"frame": fr, "z_max_m": zt, "horizontal_triangle_area_top15cm_m2": float(area[hor].sum()),
                          "horizontal_triangle_z_range_m": [float(zc[hor].min()), float(zc[hor].max())] if hor.any() else None,
                          "most_populated_2mm_bin_z_m": float(edges[kb]), "most_populated_2mm_bin_count": int(hist[kb]),
                          "median_bin_count": int(np.median(hist[hist > 0])),
                          "bin_x_extent_m": float(np.ptp(selv[:, 0])), "bin_y_extent_m": float(np.ptp(selv[:, 1]))})
        # -- Y 方向に沿う峰。
        zmax, xat = crest_along_y(vr, y_edges, z_still - 10.0)
        crest_y.append({"frame": fr, "zmax_m": [None if np.isnan(a) else float(a) for a in zmax],
                        "x_at_m": [None if np.isnan(a) else float(a) for a in xat]})
        # -- 平面切断と共通ライブラリを薄い層の上側包絡線で照合する。
        if fr in set(P("slab_check_frames")):
            ec = envelope_check(v, t, y_sec, float(P("slab_check_width_m")), rect_sec, z_still, mask_s)
            ec["frame"] = fr
            slab_check.append(ec)
            log("envelope check frame %d: %s" % (fr, ec))
        # -- 画像。
        ttl = "f%02d t=%.2fs h=%.2f th=%.0f o=%.2f phi=%s" % (fr, tsec, m_f["h"], m_f["theta"], m_f["o"],
                                                                 "-" if m_f["phi_deg"] is None else "%.0f" % m_f["phi_deg"])
        tts = "f%02d t=%.2fs h=%.2f th=%.0f o=%.2f phi=%s" % (fr, tsec, m_s["h"], m_s["theta"], m_s["o"],
                                                                 "-" if m_s["phi_deg"] is None else "%.0f" % m_s["phi_deg"])
        if fr in sheet_frames:
            cells["full"].append(overlay_cell(mask_f, prof_f, m_f, ttl, 780))
            cells["section"].append(overlay_cell(mask_s, prof_s, m_s, tts, 780))
        if zf0 <= fr <= zf1:
            for key, rect_k, mask_k, prof_k, m_k, tt in (("zoom_full", rect_full, mask_f, prof_f, m_f, ttl),
                                                         ("zoom_section", rect_sec, mask_s, prof_s, m_s, tts)):
                cx, cz = m_k["landmarks"]["crest"]["H"]
                xa, ya = rect_k.H_to_px(cx - zw["left"], 1.0 + zw["up"])
                xb, yb = rect_k.H_to_px(cx + zw["right"], 1.0 - zw["down"])
                crop = (int(max(0, xa)), int(max(0, ya)), int(min(rect_k.width_px, xb)), int(min(rect_k.height_px, yb)))
                sc = 380.0 / max(1, crop[2] - crop[0])
                cells[key].append(overlay_cell(mask_k, prof_k, m_k, "f%02d o=%.2f phi=%s" % (
                    fr, m_k["o"], "-" if m_k["phi_deg"] is None else "%.0f" % m_k["phi_deg"]), 380, crop_px=crop, crop_scale=sc))
        if fr in dens_frames:
            dens_imgs[fr] = density_panel(v[np.unique(t)], fr, y_sec, z_still)
        if fr == final_frame or fr in set(P("slab_check_frames")):
            mk, ik = silhouette.mask_from_triangles(v, t, rect_key, water_z=z_still, exact=True)
            pk = silhouette.extract_profile(mk, rect_key, edges=ik["edges"])
            ik["edges"] = None
            mkm = pm.measure_profile(pk["H"])
            sec_px = rect_key.pts_H_to_px(prof_s["H"])
            img = silhouette.draw_overlay(mk, pk, mkm, title="1.abc frame %d  FULL side silhouette (blue, landmarks) + section Y=%.2f m (green)"
                                          % (fr, y_sec), max_w=1600,
                                          extra_polylines=[{"px": sec_px, "color": "green", "width": 2.0}])
            imgio.save_png(opath("key_frame_%03d.png" % fr), img)
            cx, cz = mkm["landmarks"]["crest"]["H"]
            xa, ya = rect_key.H_to_px(cx - 0.9, 1.25)
            xb, yb = rect_key.H_to_px(cx + 0.75, -0.05)
            crop = (int(max(0, xa)), int(max(0, ya)), int(min(rect_key.width_px, xb)), int(min(rect_key.height_px, yb)))
            img = silhouette.draw_overlay(mk, pk, mkm, title="frame %d head zoom: full (landmarks) + section (green)" % fr, max_w=1500,
                                          crop_px=crop, extra_polylines=[{"px": sec_px, "color": "green", "width": 2.0}])
            imgio.save_png(opath("key_frame_%03d_head.png" % fr), img)
        log("frame %3d  full: h=%.3f xc=%+.3f th=%5.1f (w %5.1f) o=%.3f phi=%s holes=%d | sec: h=%.3f xc=%+.3f th=%5.1f (w %5.1f) o=%.3f phi=%s open=%d | %.1fs"
            % (fr, m_f["h"], m_f["x_c"], m_f["theta"], m_fw["theta"], m_f["o"], "%6.1f" % m_f["phi_deg"] if m_f["phi_deg"] is not None else "   -  ",
               prof_f["holes"]["n_holes"], m_s["h"], m_s["x_c"], m_s["theta"], m_sw["theta"], m_s["o"],
               "%6.1f" % m_s["phi_deg"] if m_s["phi_deg"] is not None else "   -  ", info_s["n_open_ends"], time.perf_counter() - tA))

    res["frames"] = frames
    res["rows"] = rows
    res["multi_section"] = {"y_m": ys_multi, "rows": multi}
    res["crest_along_y"] = {"y_mid_m": [float(a) for a in y_mid], "frames": crest_y}
    res["plane_cut_envelope_check"] = slab_check
    res["top_plane"] = top_plane
    res["measure_params"] = pm.get_params()
    tag = "_quick" if quick else ""
    paths.write_json(opath("raw_measure%s.json" % tag), res)
    np.savez_compressed(paths.ensure_parent(opath("profiles_H%s.npz" % tag)), **profs)

    # ---- 一覧画像。
    for key, ncols, name in (("full", 2, "contact_full_silhouette"), ("section", 2, "contact_section")):
        imgs = cells[key]
        half = (len(imgs) + 1) // 2
        for part, sub in (("a", imgs[:half]), ("b", imgs[half:])):
            if sub:
                imgio.save_png(opath("%s_%s%s.png" % (name, part, tag)), draw.grid(sub, ncols=ncols, gap=6))
    for key, name in (("zoom_full", "contact_zoom_full_silhouette"), ("zoom_section", "contact_zoom_section")):
        if cells[key]:
            imgio.save_png(opath("%s%s.png" % (name, tag)), draw.grid(cells[key], ncols=4, gap=6))
    for fr, (xz, _top) in dens_imgs.items():
        imgio.save_png(opath("density_xz_by_y_frame_%03d%s.png" % (fr, tag)), xz)
    if dens_imgs:
        tops = [dens_imgs[fr][1] for fr in sorted(dens_imgs)]
        imgio.save_png(opath("top_view_frames%s.png" % tag), draw.grid(tops, ncols=2, gap=8))
    log("measure stage done: %d frames" % len(frames))
    return res


def density_panel(v, fr, y_sec, z_still):
    """1フレームの正投影の画像。Y の各層の XZ 頂点密度画像と、
    最大 Z で着色した上面図を作る。"""
    r = P("view_rect_m")
    xr, zr = (-28.5, 6.0), (-5.5, 7.5)
    ppm = 22
    w, h = int((xr[1] - xr[0]) * ppm), int((zr[1] - zr[0]) * ppm)
    panels = []
    for ya, yb in P("density_y_slabs_m"):
        q = v[(v[:, 1] >= ya) & (v[:, 1] < yb)]
        Hh, _, _ = np.histogram2d(q[:, 2], q[:, 0], bins=[h, w], range=[zr, xr])
        g = np.log1p(Hh[::-1])
        g = (255 - np.clip(g / max(1e-9, g.max()) * 255, 0, 255)).astype(np.uint8)
        img = draw.to_rgb(g).copy()
        yw = (zr[1] - z_still) * ppm
        draw.hline(img, yw, "cyan", 1, dash=(6, 6))
        for xv in (r["x_min"], r["x_max"]):
            draw.vline(img, (xv - xr[0]) * ppm, "orange", 1, dash=(4, 6))
        mark = " (has section plane)" if ya <= y_sec < yb else ""
        draw.text(img, 6, 6, "f%d XZ density, Y in [%g, %g) m%s" % (fr, ya, yb, mark), "red", 2, bg="white")
        panels.append(img)
    legend = draw.canvas(h, w, "white")
    for k, line in enumerate(["frame %d of 1.abc, points projected along Y" % fr, "one panel per Y slab (no perspective)",
                              "X: %g .. %g m (right = travel)" % xr, "Z: %g .. %g m" % zr,
                              "cyan dashes : still water z=%.3f m" % z_still, "orange dashes: measuring frame X",
                              "the cache is a thin fluid SHELL:", "top surface + underside are visible"]):
        draw.text(legend, 10, 10 + 28 * k, line, "black", 2)
    xz = draw.grid(panels + [legend], ncols=2, gap=6)
    # 上面図では X が右、Y が上。0.25 m ごとの格子で最大 Z を示す。
    ppm_t = 4
    xr_t, yr_t = (-28.5, 6.0), (-16.0, 16.0)
    wt, ht = int((xr_t[1] - xr_t[0]) * ppm_t), int((yr_t[1] - yr_t[0]) * ppm_t)
    i = np.clip(((v[:, 0] - xr_t[0]) * ppm_t).astype(int), 0, wt - 1)
    j = np.clip(((v[:, 1] - yr_t[0]) * ppm_t).astype(int), 0, ht - 1)
    Z = np.full((ht, wt), -1e9)
    np.maximum.at(Z, (j, i), v[:, 2])
    Zn = np.where(Z < -1e8, np.nan, (Z - (-2.0)) / (6.5 - (-2.0)))
    top = color_ramp(Zn)[::-1]
    top = draw.resize(np.ascontiguousarray(top), scale=5.0, method="nearest")
    sc = ppm_t * 5.0
    draw.hline(top, (yr_t[1] - y_sec) * sc, "white", 2, dash=(8, 6))
    for xv in (r["x_min"], r["x_max"]):
        draw.vline(top, (xv - xr_t[0]) * sc, "orange", 1, dash=(4, 6))
    draw.text(top, 6, 6, "f%d TOP VIEW  X right (travel), Y up" % fr, "black", 2, bg="white")
    draw.text(top, 6, 30, "colour = max Z: -2 m blue .. +6.5 m red", "black", 2, bg="white")
    draw.text(top, 6, 54, "white dashes = section plane Y=%.2f m" % y_sec, "black", 2, bg="white")
    return xz, top


# ====================================================================== 第2段階: 解析
def _arr(rows, key):
    return np.array([np.nan if r.get(key) is None else float(r[key]) for r in rows], dtype=np.float64)


def sustained_crossing(frames, vals, level):
    """`vals` が `level` を超え、最後までその値以上に留まる時点を小数フレームで返す。
    隣り合う2フレーム間を線形補間する。最後まで到達しなければ None、
    最初から最後まで上回る場合は最初のフレームを返す。"""
    v = np.asarray(vals, dtype=np.float64)
    ok = np.nan_to_num(v, nan=-np.inf) >= level
    if not ok[-1]:
        return None
    i = len(v) - 1
    while i > 0 and ok[i - 1]:
        i -= 1
    if i == 0:
        return float(frames[0])
    a, b = v[i - 1], v[i]
    if not np.isfinite(a) or b == a:
        return float(frames[i])
    return float(frames[i - 1] + (level - a) / (b - a) * (frames[i] - frames[i - 1]))


def first_run(flags, n):
    run = 0
    for i, f in enumerate(flags):
        run = run + 1 if f else 0
        if run >= n:
            return i - n + 1
    return None


def companions(pts, row, h_visible):
    """同じ順序付き断面から安定した補助指標を求める。単位は H。"""
    x, z = pts[:, 0].astype(np.float64), pts[:, 1].astype(np.float64)
    i = int(np.argmax(z))
    zmax = z[i]
    a = i
    while a > 0 and z[a - 1] >= zmax - 0.005:
        a -= 1
    b = i
    while b < len(z) - 1 and z[b + 1] >= zmax - 0.005:
        b += 1
    out = {"top_flat_width_H": float(abs(x[b] - x[a])), "top_flat_x_range_H": [float(min(x[a], x[b])), float(max(x[a], x[b]))]}
    if zmax >= h_visible:
        up = z >= 0.5 * zmax
        out["x_lead_H"] = float(x[up].max())
        out["x_back_half_H"] = float(x[up].min())
        out["width_at_half_height_H"] = out["x_lead_H"] - out["x_back_half_H"]
    else:
        out["x_lead_H"] = out["x_back_half_H"] = out["width_at_half_height_H"] = None
    out["tip_drop_H"] = None if row["tip_H"] is None else float(row["crest_H"][1] - row["tip_H"][1])
    return out


def phi_analysis(frames, phi, i_over):
    """参照映像に仕様 M4 を適用し、phi が下向きへ単調に回る終盤の区間があるか調べる。
    全数値を含む辞書を返す。'identified' にはパラメーターのしきい値を使う。"""
    tol = float(P("phi_monotone_tol_deg"))
    idx = [i for i in range(i_over, len(frames)) if np.isfinite(phi[i])]
    if len(idx) < 3:
        return {"n_frames_with_phi": len(idx), "identified": False}
    f = np.array([frames[i] for i in idx], dtype=np.float64)
    p = np.array([phi[i] for i in idx])
    A = np.stack([f - f.mean(), np.ones_like(f)], axis=1)
    coef, _res, _rk, _sv = np.linalg.lstsq(A, p, rcond=None)
    resid = p - A @ coef
    se = float(np.sqrt((resid ** 2).sum() / max(1, len(f) - 2) / ((f - f.mean()) ** 2).sum()))
    noise = float(np.std(np.diff(p)) / math.sqrt(2.0))
    # phi が累積最小値より tol を超えて上がらない最終区間の開始点。
    s = len(p) - 1
    for cand in range(len(p) - 1, -1, -1):
        seg = p[cand:]
        runmin = np.minimum.accumulate(seg)
        if np.all(seg[1:] <= runmin[:-1] + tol):
            s = cand
        else:
            break
    drop = float(p[-1] - p[s])
    n_run = int(len(p) - 1 - s)
    ident = bool(n_run >= int(P("curl_min_run_frames")) and drop <= -float(P("curl_min_drop_sigma")) * noise)
    return {"n_frames_with_phi": int(len(p)), "phi_first_deg": float(p[0]), "phi_last_deg": float(p[-1]),
            "phi_min_deg": float(p.min()), "phi_max_deg": float(p.max()), "phi_mean_deg": float(p.mean()),
            "trend_deg_per_frame": float(coef[0]), "trend_standard_error": se, "frame_to_frame_noise_sd_deg": noise,
            "final_monotone_run_start_frame": int(f[s]), "final_monotone_run_intervals": n_run,
            "final_monotone_run_change_deg": drop, "tolerance_deg": tol, "identified": ident}


def analyze_mode(name, rows, profs, frames, fps, H_ref, x0):
    hv = float(P("h_visible_frac"))
    f = np.array(frames, dtype=np.float64)
    comp = [companions(profs["%s_%03d" % (name, fr)], r, hv) for fr, r in zip(frames, rows)]
    h, xc, th, thw, o, cav, phi = (_arr(rows, k) for k in ("h", "x_c", "theta", "theta_wide", "o", "cavity_depth", "phi_deg"))
    over = [bool(r["overhanging"]) for r in rows]
    i_over = first_run(over, int(P("overhang_min_run_frames")))
    xl = np.array([np.nan if c["x_lead_H"] is None else c["x_lead_H"] for c in comp])
    flat = np.array([c["top_flat_width_H"] for c in comp])
    table = []
    for k, (fr, r, c) in enumerate(zip(frames, rows, comp)):
        flags = []
        if r["h"] < hv:
            flags.append("h_too_small")
        if r["h"] >= hv and c["top_flat_width_H"] > float(P("flat_top_flag_width_H")):
            flags.append("crest_x_ambiguous_flat_top")
        if k > 0 and r["h"] >= hv and np.isfinite(xl[k]) and np.isfinite(xl[k - 1]) and (xc[k] - xc[k - 1]) < 0 < (xl[k] - xl[k - 1]):
            flags.append("crest_x_jumped_back")
        if not r["reached_still_water"] and r["h"] >= hv:
            flags.append("front_toe_outside_frame")
        if r.get("tip_gap_to_frame_edge_m") is not None and r["tip_gap_to_frame_edge_m"] < 0.30:
            flags.append("tip_close_to_frame_edge")
        if r.get("chunk_end_guard"):
            flags.append("theta_remeasured_without_chunk_end")
        if r.get("phi_truncated"):
            flags.append("phi_window_truncated")
        if not r["complete"]:
            flags.append("profile_incomplete")
        if name == "full" and r["n_holes"] > 0:
            flags.append("mask_has_holes")
        if r["n_components_dropped"] > 0:
            flags.append("detached_blobs_dropped")
        table.append({
            "frame": int(fr), "t_s": float((fr - frames[0]) / fps), "tau": float((fr - frames[0]) / (frames[-1] - frames[0])),
            "h_H": r["h"], "h_m": r["h"] * H_ref, "x_c_H": r["x_c"], "x_c_world_m": r["x_c"] * H_ref + x0,
            "theta_deg": r["theta"], "theta_wide_deg": r["theta_wide"], "o_H": r["o"], "o_m": r["o"] * H_ref,
            "phi_deg": r["phi_deg"], "overhanging": bool(r["overhanging"]),
            "cavity_depth_H": r["cavity_depth"], "tip_H": r["tip_H"], "deepest_H": r["deepest_H"], "crest_H": r["crest_H"],
            "tip_drop_H": c["tip_drop_H"], "x_lead_H": c["x_lead_H"], "width_at_half_height_H": c["width_at_half_height_H"],
            "top_flat_width_H": c["top_flat_width_H"], "back_max_slope_deg": r["back_mid_max_deg"],
            "contour_disp_p95_H": r["disp_p95_H"], "contour_disp_max_H": r["disp_max_H"], "contour_disp_mean_H": r["disp_mean_H"],
            "hole_area_frac": r["hole_area_frac"],
            "back_trough_z_rel_still_H": r.get("back_trough_z_rel_still_H"), "back_trough_x_H": r.get("back_trough_x_H"),
            "back_trough_at_left_limit": r.get("back_trough_at_left_limit"),
            "front_min_z_rel_still_H": r.get("front_min_z_rel_still_H"),
            "theta_with_chunk_end_deg": None if not r.get("chunk_end_guard") else r["chunk_end_guard"]["theta_with_chunk_end_deg"],
            "flags": flags})
    ev = {"h_fraction_frames": {("%g" % q): sustained_crossing(frames, h, q) for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99)},
          "theta_deg_frames": {("%g" % q): sustained_crossing(frames, th, q) for q in (30, 45, 60, 80, 90, 120, 150)},
          "theta_wide_deg_frames": {("%g" % q): sustained_crossing(frames, thw, q) for q in (30, 45, 60, 80, 90)},
          "cavity_depth_H_frames": {("%g" % q): sustained_crossing(frames, cav, q) for q in (0.1, 0.2, 0.3, 0.4, 0.5)},
          "last_frame_theta_below_30": int(max([fr for fr, v in zip(frames, th) if v < 30.0] or [frames[0]])),
          "overhang_onset_frame": None if i_over is None else int(frames[i_over]),
          "o_at_onset_H": None if i_over is None else float(o[i_over]),
          "h_at_onset_H": None if i_over is None else float(h[i_over]),
          "theta_at_onset_deg": None if i_over is None else float(th[i_over])}
    # 単調性の事実。仕様 M2 / M3 の表現を参照映像に適用する。
    dh = np.diff(h)
    mono = {"h_largest_drop_H": float(max(0.0, -(dh.min()))), "h_n_decreasing_steps": int((dh < 0).sum())}
    if i_over is not None:
        do = np.diff(o[i_over:])
        dc = np.diff(cav[i_over:])
        mono.update({"o_largest_drop_after_onset_H": float(max(0.0, -do.min())) if do.size else 0.0,
                     "o_n_decreasing_steps_after_onset": int((do < 0).sum()),
                     "cavity_depth_largest_drop_after_onset_H": float(max(0.0, -dc.min())) if dc.size else 0.0,
                     "h_drop_after_onset_pct": float(max(0.0, (h[i_over:].max() - h[-1]) / h[i_over:].max() * 100.0)),
                     "o_final_H": float(o[-1]), "o_second_last_H": float(o[-2]), "cavity_depth_final_H": float(cav[-1]),
                     "cavity_growth_H_per_frame": float(np.polyfit(f[i_over:], cav[i_over:], 1)[0]),
                     "tip_speed_H_per_frame": float(np.polyfit(f[i_over:], np.array([r["tip_H"][0] for r in rows[i_over:]]), 1)[0]),
                     "deepest_speed_H_per_frame": float(np.polyfit(f[i_over:], np.array([r["deepest_H"][0] for r in rows[i_over:]]), 1)[0])})
    phi_info = phi_analysis(frames, phi, i_over) if i_over is not None else {"identified": False}
    # 段階。
    f_first, f_final = frames[0], frames[-1]
    total = f_final - f_first
    f_over = ev["overhang_onset_frame"]
    f_curl = phi_info.get("final_monotone_run_start_frame") if phi_info.get("identified") else None
    phases = {"rise": {"from_frame": int(f_first), "to_frame": f_over},
              "overhang": {"from_frame": f_over, "to_frame": f_curl if f_curl is not None else int(f_final)},
              "curl_in": None if f_curl is None else {"from_frame": f_curl, "to_frame": int(f_final)}}
    for ph in phases.values():
        if ph and ph["from_frame"] is not None and ph["to_frame"] is not None:
            n = ph["to_frame"] - ph["from_frame"]
            ph.update({"frames_at_24fps": int(n), "seconds": float(n / fps), "proportion": float(n / total)})
    # 速度と減速。
    d95 = _arr(rows, "disp_p95_H")
    kmax = int(np.nanargmax(d95))
    vis = h >= hv
    dxl = np.diff(xl)
    late = (f[1:] >= 30) & np.isfinite(dxl)
    decel = {"contour_disp_p95_max_H_per_frame": float(d95[kmax]), "at_frame": int(frames[kmax]),
             "contour_disp_p95_final_H_per_frame": float(d95[-1]), "final_over_max_ratio": float(d95[-1] / d95[kmax]),
             "contour_speed_max_m_per_s": float(d95[kmax] * H_ref * fps), "contour_speed_final_m_per_s": float(d95[-1] * H_ref * fps),
             "mean_ratio_last_24_frames": float(np.nanmean(d95[-24:]) / d95[kmax]),
             "travel_speed_x_lead_mean_f30_to_end_H_per_frame": float(np.mean(dxl[late])),
             "travel_speed_x_lead_mean_f30_to_end_m_per_s": float(np.mean(dxl[late]) * H_ref * fps),
             "travel_speed_x_lead_last5_H_per_frame": float(np.mean(dxl[-5:])),
             "dh_max_H_per_frame": float(dh.max()), "dh_max_at_frame": int(frames[int(np.argmax(dh)) + 1]),
             "dh_mean_last5_H_per_frame": float(dh[-5:].mean()),
             "crest_speed_H_per_frame_by_interval": {"%d-%d" % (a, b): float((xc[frames.index(b)] - xc[frames.index(a)]) / (b - a))
                                                     for a, b in ((10, 20), (20, 30), (30, 40), (40, 50), (50, 54)) if a in frames and b in frames},
             "x_c_travel_total_H": float(xc[-1] - np.nanmin(np.where(vis, xc, np.nan))),
             "x_lead_travel_total_H": float(np.nanmax(xl) - np.nanmin(xl))}
    return {"table": table, "events": ev, "monotonicity": mono, "phi": phi_info, "phases": phases, "deceleration": decel,
            "series": {"f": f, "h": h, "xc": xc, "th": th, "thw": thw, "o": o, "cav": cav, "phi": phi, "xl": xl, "flat": flat, "d95": d95}}


def map_to_target(phases):
    tl = P("target_timeline")
    n_tot, fps_t, back = int(tl["total_frames"]), float(tl["fps"]), [float(s) for s in tl["backlog_seconds"]]
    names = ["rise", "overhang", "curl_in"]
    out = {"target_total_frames": n_tot, "target_fps": fps_t, "backlog_seconds": dict(zip(names, back)), "reference_proportional": {}}
    for nm, b in zip(names, back):
        ph = phases.get(nm)
        p = 0.0 if not ph or ph.get("proportion") is None else ph["proportion"]
        out["reference_proportional"][nm] = {"proportion": p, "frames_at_30fps": p * n_tot, "seconds": p * n_tot / fps_t,
                                             "backlog_seconds": b, "difference_s": p * n_tot / fps_t - b,
                                             "backlog_proportion": b / sum(back)}
    return out


def stage_analyze():
    raw = paths.read_json(opath("raw_measure.json"))
    profs = np.load(opath("profiles_H.npz"))
    frames = raw["frames"]
    fps = float(raw["abc"]["scene_fps"])
    fp = raw["final_pose"]
    H_ref, x0, z_still, y_sec = fp["H_ref_m"], fp["x0_m"], fp["z0_m"], fp["section_y_m"]
    res = {k: analyze_mode(k, raw["rows"][k], profs, frames, fps, H_ref, x0) for k in ("full", "section")}
    for k in res:
        log("%s events %s" % (k, res[k]["events"]))
        log("%s phases %s" % (k, res[k]["phases"]))
        log("%s phi %s" % (k, res[k]["phi"]))
        log("%s monotonicity %s" % (k, res[k]["monotonicity"]))
        log("%s deceleration %s" % (k, res[k]["deceleration"]))
    mapping = {k: map_to_target(res[k]["phases"]) for k in res}
    log("mapping", {k: {n: round(v["seconds"], 3) for n, v in mapping[k]["reference_proportional"].items()} for k in mapping})

    # ---- 峰線に沿った3D構造。
    ym = np.array(raw["crest_along_y"]["y_mid_m"])
    cy = {c["frame"]: c for c in raw["crest_along_y"]["frames"]}
    zf = np.array([np.nan if a is None else a for a in cy[frames[-1]]["zmax_m"]])
    xf = np.array([np.nan if a is None else a for a in cy[frames[-1]]["x_at_m"]])
    along = {"y_mid_m": [float(a) for a in ym],
             "final_crest_height_m": [None if np.isnan(a) else float(a - z_still) for a in zf],
             "final_crest_x_m": [None if np.isnan(a) else float(a) for a in xf],
             "final_crest_height_min_over_max": float(np.nanmin(zf - z_still) / np.nanmax(zf - z_still)),
             "final_crest_x_range_m": [float(np.nanmin(xf)), float(np.nanmax(xf))],
             "sections": []}
    for y in raw["multi_section"]["y_m"]:
        rws = [r for r in raw["multi_section"]["rows"]["%g" % y] if "error" not in r]
        fr_ = [r["frame"] for r in rws]
        over = [bool(r["overhanging"]) for r in rws]
        i_o = first_run(over, int(P("overhang_min_run_frames")))
        along["sections"].append({"y_m": float(y), "h_final_H": rws[-1]["h"], "x_c_final_H": rws[-1]["x_c"],
                                  "theta_final_deg": rws[-1]["theta"], "o_final_H": rws[-1]["o"],
                                  "overhang_onset_frame": None if i_o is None else int(fr_[i_o]),
                                  "theta80_frame": sustained_crossing(fr_, [r["theta"] for r in rws], 80.0),
                                  "h_half_frame": sustained_crossing(fr_, [r["h"] for r in rws], 0.5 * rws[-1]["h"]),
                                  "n_open_ends_max": int(max(r["n_open_ends"] for r in rws))})
    for s in along["sections"]:
        log("along-crest section", s)

    make_plots(raw, res, mapping, along, profs)

    # ---- 比較用の方向のみ。原画の基準輪郭があれば同じ指標を読込専用で測る。
    base_cmp = None
    if os.path.isfile(paths.BASE_CONTOUR_JSON):
        try:
            bc = pm.load_base_contour()
            bm = pm.measure_base_contour(bc)
            lmk = bm["landmarks"]
            base_cmp = {"file": paths.norm(paths.BASE_CONTOUR_JSON), "file_mtime": os.path.getmtime(paths.BASE_CONTOUR_JSON),
                        "official": bc.get("official"), "variant": bc.get("variant"),
                        "note": "orientation for the motion design only; the reference's final SHAPE is not a target (spec 6.1)",
                        "h": bm["h"], "o": bm["o"], "cavity_depth": bm["cavity_depth"], "theta": bm["theta"], "phi_deg": bm["phi_deg"],
                        "tip_H": None if lmk["head_tip"] is None else lmk["head_tip"]["H"],
                        "deepest_H": None if lmk["inner_deepest"] is None else lmk["inner_deepest"]["H"],
                        "tip_drop_H": None if lmk["head_tip"] is None else float(lmk["crest"]["H"][1] - lmk["head_tip"]["H"][1])}
            log("base contour (orientation only)", {k: base_cmp[k] for k in ("h", "o", "cavity_depth", "theta", "phi_deg", "tip_H", "tip_drop_H")})
        except Exception as exc:                      # noqa: BLE001
            base_cmp = {"error": repr(exc)}

    # ---- JSON。
    scan = raw["scan"]
    i_last = scan["last_distinct_frame"] - scan["frames"][0]["frame"]
    out = {
        "schema": "gw.houdini_motion.v1",
        "generated_by": "src/ref/read_houdini_motion.py (params: src/ref/read_houdini_motion_params.json)",
        "purpose": "MOTION reference only (spec 6.1); no geometry of the Houdini cache is used for the new wave.",
        "source": {"path": raw["abc"]["path"], "size_bytes": raw["abc"]["size_bytes"], "object": raw["abc"]["objects"],
                   "fps": fps, "scene_frame_range": raw["abc"]["scene_frame_range"],
                   "n_vertices_every_frame": scan["frames"][0]["n_vertices"], "n_triangles_every_frame": scan["frames"][0]["n_triangles"],
                   "n_padding_triangles_first_and_last_distinct_frame": [scan["frames"][0]["n_padding_triangles"],
                                                                         scan["frames"][i_last]["n_padding_triangles"]],
                   "distinct_frames": [scan["distinct_frames"][0], scan["distinct_frames"][-1]], "n_distinct_frames": len(scan["distinct_frames"]),
                   "frames_identical_to_first_frame": [scan["frames_equal_to_first"][1], scan["frames_equal_to_first"][-1]]
                   if len(scan["frames_equal_to_first"]) > 1 else None,
                   "bbox_final_frame_m": [scan["frames"][i_last]["bbox_min"], scan["frames"][i_last]["bbox_max"]],
                   "topology": raw["topology"]},
        "meta": {"time_base": "t_s = (frame - %d) / %g ; tau = (frame - %d) / %d" % (frames[0], fps, frames[0], frames[-1] - frames[0]),
                 "first_frame_is_rest_pose": True, "final_frame": fp["frame"],
                 "mirroring": {"mirror_x": False, "reason": "the reference already travels and overhangs towards +X (boat side)"},
                 "H_ref_m": H_ref, "H_ref_definition": "max Z of the FULL side silhouette at the final frame minus the still-water level",
                 "x0_m": x0, "x0_definition": "robust crest X (gw.profile_metrics) of the full silhouette at the final frame",
                 "z_still_m": z_still, "still_water": raw["still_water"],
                 "normalisation": "X_H = (X - x0) / H_ref ; Z_H = (Z - z_still) / H_ref ; water slab at z_still",
                 "section_plane_y_m": y_sec, "section_plane_choice": fp, "rects": raw["rects"],
                 "measure_params": raw["measure_params"], "reader_params_file": "src/ref/read_houdini_motion_params.json"},
        "modes": {"full": "full side silhouette along +Y of the whole chunk (gw.silhouette exact mode) = what a CAM_print-like camera sees",
                  "section": "plane cut Y = section_plane_y_m (even-odd fill in this module, profile by gw.silhouette.extract_profile pixel mode)"},
        "flags_legend": {
            "h_too_small": "h < %g H_ref: crest position and theta are dominated by surface ripples" % float(P("h_visible_frac")),
            "crest_x_ambiguous_flat_top": "top within 0.5 %% H_ref of the max is wider than %g H_ref: x_c and o are uncertain by about half that width"
                                          % float(P("flat_top_flag_width_H")),
            "crest_x_jumped_back": "x_c moved backwards while the wave moved forwards (highest point switched on a flat top) -> o jumps",
            "front_toe_outside_frame": "the front face leaves the measuring frame (end of the fluid chunk at X=+5.26 m) above still water",
            "tip_close_to_frame_edge": "head tip closer than 0.30 m to the right frame edge",
            "theta_remeasured_without_chunk_end": "the steepest 'front' point was on the rounded end corner of the fluid chunk (X > %g m) while the "
                                                  "crest was far away; theta was re-measured on the profile cut at that X (old value kept in "
                                                  "theta_with_chunk_end_deg)" % float(P("chunk_end_zone_x_m")),
            "phi_window_truncated": "the head (crest..tip) is shorter than the phi window (0.08 H); the window was cut at the crest",
            "detached_blobs_dropped": "separate fluid blobs were ignored (largest component only)"},
        "per_frame": {k: res[k]["table"] for k in res},
        "events": {k: res[k]["events"] for k in res},
        "monotonicity": {k: res[k]["monotonicity"] for k in res},
        "phi_analysis": {k: res[k]["phi"] for k in res},
        "phases": {k: res[k]["phases"] for k in res},
        "deceleration": {k: res[k]["deceleration"] for k in res},
        "mapping_to_target_timeline": mapping,
        "along_crest_line": along,
        "base_contour_for_orientation": base_cmp,
        "top_plane_statistics": [tp for tp in raw.get("top_plane", []) if tp["frame"] >= frames[-1] - 9 or tp["frame"] % 10 == 0],
        "checks": {"plane_cut_selftest": raw.get("plane_cut_selftest"), "plane_cut_envelope_check": raw.get("plane_cut_envelope_check")},
    }
    paths.write_json(OUT_JSON, out)
    log("wrote", OUT_JSON)
    return out


def make_plots(raw, res, mapping, along, profs):
    frames = raw["frames"]
    S, Fu = res["section"]["series"], res["full"]["series"]
    ph = res["section"]["phases"]
    spans = [{"x0": ph["rise"]["from_frame"], "x1": ph["rise"]["to_frame"], "label": "rise (section)", "color": "green", "alpha": 0.10},
             {"x0": ph["overhang"]["from_frame"], "x1": ph["overhang"]["to_frame"], "label": "overhang", "color": "orange", "alpha": 0.14}]
    if ph["curl_in"]:
        spans.append({"x0": ph["curl_in"]["from_frame"], "x1": ph["curl_in"]["to_frame"], "label": "curl-in", "color": "purple", "alpha": 0.14})
    vl = [{"x": res["full"]["events"]["overhang_onset_frame"], "label": "onset full", "color": "blue"}]
    xl = (frames[0], frames[-1] + 1)
    size = (1500, 300)
    xlab = "scene frame of 1.abc (24 fps; t = (frame-1)/24 s; data end at frame %d)" % frames[-1]
    common = {"size": size, "xlim": xl, "spans": spans, "vlines": vl}
    plots = [
        dict(common, title="h(t)  crest height above still water / H_ref", ylabel="h [H]",
             series=[{"label": "full silhouette", "x": Fu["f"], "y": Fu["h"], "color": "blue"},
                     {"label": "section Y=%.2f" % raw["final_pose"]["section_y_m"], "x": S["f"], "y": S["h"], "color": "red"}]),
        dict(common, title="x_c(t) crest X relative to the final crest / H_ref (dashed: x_lead = most forward point of the upper half)",
             ylabel="x [H]",
             series=[{"label": "x_c full", "x": Fu["f"], "y": np.where(Fu["h"] >= 0.02, Fu["xc"], np.nan), "color": "blue"},
                     {"label": "x_c section", "x": S["f"], "y": np.where(S["h"] >= 0.02, S["xc"], np.nan), "color": "red"},
                     {"label": "x_lead full", "x": Fu["f"], "y": Fu["xl"], "color": "blue", "dash": (6, 4), "width": 1.5},
                     {"label": "x_lead section", "x": S["f"], "y": S["xl"], "color": "red", "dash": (6, 4), "width": 1.5}]),
        dict(common, title="theta(t) steepest front-face inclination (clockwise scale: 90 = vertical, >90 = overhanging)", ylabel="theta [deg]",
             hlines=[{"y": 30, "label": "30"}, {"y": 80, "label": "80"}],
             series=[{"label": "full (2% chord)", "x": Fu["f"], "y": Fu["th"], "color": "blue"},
                     {"label": "section (2% chord)", "x": S["f"], "y": S["th"], "color": "red"},
                     {"label": "full (6% chord)", "x": Fu["f"], "y": Fu["thw"], "color": "cyan", "dash": (5, 4), "width": 1.5},
                     {"label": "section (6% chord)", "x": S["f"], "y": S["thw"], "color": "orange", "dash": (5, 4), "width": 1.5}]),
        dict(common, title="o(t) = X_tip - X_crest (spec) and companion cavity depth = X_tip - X_deepest (dashed)", ylabel="o [H]",
             series=[{"label": "o full", "x": Fu["f"], "y": Fu["o"], "color": "blue", "marker": "o"},
                     {"label": "o section", "x": S["f"], "y": S["o"], "color": "red", "marker": "o"},
                     {"label": "cavity full", "x": Fu["f"], "y": Fu["cav"], "color": "blue", "dash": (6, 4), "width": 1.5},
                     {"label": "cavity section", "x": S["f"], "y": S["cav"], "color": "red", "dash": (6, 4), "width": 1.5}]),
        dict(common, title="phi(t) direction of the head tip (top-side chord 2%..8% H before the tip; negative = downward)",
             ylabel="phi [deg]", xlabel=xlab, size=(1500, 330), ylim=(-95, 5),
             series=[{"label": "full", "x": Fu["f"], "y": Fu["phi"], "color": "blue", "marker": "o"},
                     {"label": "section", "x": S["f"], "y": S["phi"], "color": "red", "marker": "o"}]),
    ]
    fig = plot.multi_plot(plots, ncols=1, title="Houdini reference 1.abc: motion quantities of spec 6.2 (shared library gw.profile_metrics)")
    imgio.save_png(opath("curves_motion_quantities.png"), fig)
    imgio.save_png(opath("curves_motion_quantities_theta_o_phi.png"), plot.multi_plot(plots[2:], ncols=1))
    imgio.save_png(opath("curves_motion_quantities_h_xc.png"),
                   plot.multi_plot([dict(plots[0]), dict(plots[1], xlabel=xlab, size=(1500, 330))], ncols=1))

    # 補助指標。
    dh_s, dh_f = np.diff(S["h"]), np.diff(Fu["h"])
    dx_s, dx_f = np.diff(S["xl"]), np.diff(Fu["xl"])
    tipdrop_s = np.array([np.nan if r["tip_drop_H"] is None else r["tip_drop_H"] for r in res["section"]["table"]])
    tipdrop_f = np.array([np.nan if r["tip_drop_H"] is None else r["tip_drop_H"] for r in res["full"]["table"]])
    plots2 = [
        dict(common, title="contour displacement to the previous frame, 95th percentile [H per frame] (spec M5/M6 quantity)", ylabel="[H/frame]",
             ylim=(0, None),
             series=[{"label": "full", "x": Fu["f"], "y": Fu["d95"], "color": "blue"}, {"label": "section", "x": S["f"], "y": S["d95"], "color": "red"}]),
        dict(common, title="per-frame rates: dh (solid) and d x_lead (dashed) [H per frame]", ylabel="[H/frame]",
             series=[{"label": "dh full", "x": Fu["f"][1:], "y": dh_f, "color": "blue"}, {"label": "dh section", "x": S["f"][1:], "y": dh_s, "color": "red"},
                     {"label": "dx_lead full", "x": Fu["f"][1:], "y": dx_f, "color": "blue", "dash": (6, 4), "width": 1.5},
                     {"label": "dx_lead section", "x": S["f"][1:], "y": dx_s, "color": "red", "dash": (6, 4), "width": 1.5}]),
        dict(common, title="width of the flat top (Z within 0.5% H of the max) [H] and tip drop = Z_crest - Z_tip [H] (dashed)", ylabel="[H]",
             xlabel=xlab, size=(1500, 330), ylim=(0, 0.6),
             series=[{"label": "flat top full", "x": Fu["f"], "y": np.where(Fu["h"] >= 0.1, Fu["flat"], np.nan), "color": "blue"},
                     {"label": "flat top section", "x": S["f"], "y": np.where(S["h"] >= 0.1, S["flat"], np.nan), "color": "red"},
                     {"label": "tip drop full", "x": Fu["f"], "y": tipdrop_f, "color": "blue", "dash": (6, 4), "width": 1.5},
                     {"label": "tip drop section", "x": S["f"], "y": tipdrop_s, "color": "red", "dash": (6, 4), "width": 1.5}]),
    ]
    imgio.save_png(opath("curves_companions.png"),
                   plot.multi_plot(plots2, ncols=1, title="Houdini reference 1.abc: companion quantities (not spec quantities)"))

    # 峰線に沿う指標。
    ym = np.array(along["y_mid_m"])
    cy = {c["frame"]: c for c in raw["crest_along_y"]["frames"]}
    z_still, H_ref = raw["final_pose"]["z0_m"], raw["final_pose"]["H_ref_m"]
    pick = [fr for fr in (10, 20, 30, 40, 50, frames[-1]) if fr in cy]
    ser_h = [{"label": "frame %d" % fr, "x": ym,
              "y": (np.array([np.nan if a is None else a for a in cy[fr]["zmax_m"]]) - z_still) / H_ref} for fr in pick]
    ser_x = [{"label": "frame %d" % fr, "x": ym, "y": np.array([np.nan if a is None else a for a in cy[fr]["x_at_m"]])}
             for fr in pick if fr >= 20]
    secs = along["sections"]
    ys = [s["y_m"] for s in secs]
    y_sec = raw["final_pose"]["section_y_m"]
    p3 = [dict(title="crest height along the crest line (max Z per 0.5 m Y bin) / H_ref", ylabel="h(Y) [H]", size=(1500, 320), xlim=(-16, 16),
               series=ser_h, vlines=[{"x": y_sec, "label": "section plane", "color": "red"}]),
          dict(title="plan view of the crest line: X of the crest per Y bin [m] (travel direction +X = up in this plot)", ylabel="X_crest [m]",
               size=(1500, 320), xlim=(-16, 16), series=ser_x, vlines=[{"x": y_sec, "color": "red"}]),
          dict(title="timing along the crest line from plane cuts at fixed Y: frame of theta>=80 (blue), overhang onset (red)", ylabel="frame",
               xlabel="Y [m] (along the crest line; tank side walls at +-15.4 m)", size=(1500, 330), xlim=(-16, 16),
               series=[{"label": "theta >= 80", "x": ys, "y": [np.nan if s["theta80_frame"] is None else s["theta80_frame"] for s in secs],
                        "color": "blue", "marker": "o"},
                       {"label": "overhang onset", "x": ys,
                        "y": [np.nan if s["overhang_onset_frame"] is None else s["overhang_onset_frame"] for s in secs],
                        "color": "red", "marker": "s"}])]
    imgio.save_png(opath("along_crest_line.png"), plot.multi_plot(p3, ncols=1, title="Houdini reference 1.abc: structure along Y"))

    # 固定フレームと先端位置を合わせた断面。
    sel = list(range(frames[0] + 4, frames[-1] + 1, 5))
    if frames[-1] not in sel:
        sel.append(frames[-1])
    for mode in ("section", "full"):
        ser_w, ser_a = [], []
        xlead = {r["frame"]: r["x_lead_H"] for r in res[mode]["table"]}
        for k, fr in enumerate(sel):
            p = profs["%s_%03d" % (mode, fr)].astype(np.float64)
            col = tuple(int(c) for c in color_ramp(np.array([k / max(1, len(sel) - 1)]))[0])
            ser_w.append({"label": "f%d" % fr, "x": p[:, 0], "y": p[:, 1], "color": col, "width": 1.6})
            if xlead[fr] is not None:
                ser_a.append({"label": "f%d" % fr, "x": p[:, 0] - xlead[fr], "y": p[:, 1], "color": col, "width": 1.6})
        a = plot.line_plot(ser_w, title="%s profiles every 5 frames, fixed frame (X relative to the final crest) [H]" % mode, size=(1500, 520),
                           xlim=(-4.2, 0.7), ylim=(-0.05, 1.15), equal_aspect=True, xlabel="X [H]", ylabel="Z [H]")
        b = plot.line_plot(ser_a, title="%s profiles aligned at x_lead (most forward point of the upper half): shape change only [H]" % mode,
                           size=(1500, 760), xlim=(-2.6, 0.6), ylim=(-0.05, 1.15), equal_aspect=True, xlabel="X - x_lead [H]", ylabel="Z [H]")
        imgio.save_png(opath("profiles_overlay_%s.png" % mode), draw.vstack([a, b], gap=8))

    # 時間軸の帯。
    W, Hh = 1500, 430
    img = draw.canvas(Hh, W, "white")
    draw.text(img, 20, 12, "Phase durations mapped onto 9.5 s = 285 frames @30 fps (reference proportions vs backlog initial split)", "black", 2)
    cols = {"rise": "green", "overhang": "orange", "curl_in": "purple"}
    bars = [("backlog 4 / 3 / 2.5 s", dict(mapping["section"]["backlog_seconds"]))]
    for mode in ("section", "full"):
        bars.append(("reference, %s" % mode, {n: v["seconds"] for n, v in mapping[mode]["reference_proportional"].items()}))
    x_a, x_b = 360, W - 40
    for k, (label, d) in enumerate(bars):
        y = 70 + k * 110
        draw.text(img, 20, y + 22, label, "black", 2)
        x = float(x_a)
        for n in ("rise", "overhang", "curl_in"):
            wpx = d[n] / 9.5 * (x_b - x_a)
            if wpx > 0:
                draw.rect(img, x, y, x + wpx, y + 60, cols[n], fill=True, alpha=0.55)
                draw.rect(img, x, y, x + wpx, y + 60, "black", 1)
                draw.text(img, x + 6, y + 8, n, "black", 2)
                draw.text(img, x + 6, y + 34, "%.2f s = %.0f fr" % (d[n], d[n] * 30), "black", 2)
            x += wpx
    draw.text(img, 20, Hh - 40, "reference: the cache ends at frame 55 while the wave is still travelling; it contains no curl-in and no stop",
              "red", 2)
    imgio.save_png(opath("timeline_mapping.png"), img)
    log("plots written")


# ====================================================================== 第3段階: 斜め視点の確認（任意）
def stage_render():
    """数フレームを Workbench で斜めから描く。3D の見た目だけを確認し、測定はしない。"""
    import bpy
    from mathutils import Vector
    rd = AbcReader()
    scene = rd.scene
    rp = P("perspective_render")
    cam_data = bpy.data.cameras.new("CAM_look")
    cam_data.lens = float(rp["lens_mm"])
    cam_data.clip_start, cam_data.clip_end = 0.1, 500.0
    cam = bpy.data.objects.new("CAM_look", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector(rp["location_m"])
    d = Vector(rp["look_at_m"]) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    r = scene.render
    r.engine = "BLENDER_WORKBENCH"
    r.resolution_x, r.resolution_y, r.resolution_percentage = int(rp["resolution"][0]), int(rp["resolution"][1]), 100
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.dither_intensity = 0.0
    scene.view_settings.view_transform = "Standard"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.single_color = (0.62, 0.64, 0.66)
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_shadows = False
    sh.show_object_outline = False
    world = bpy.data.worlds.new("W_look")
    world.color = (0.02, 0.03, 0.05)
    scene.world = world
    cells = []
    tmp = os.path.join(paths.RESULTS_DIR, "houdini_look_tmp.png")
    for fr in rp["frames"]:
        scene.frame_set(int(fr))
        r.filepath = paths.ensure_parent(tmp)
        bpy.ops.render.render(write_still=True)
        img = imgio.load_image_rgb(tmp).copy()
        draw.text(img, 8, 8, "1.abc frame %d  perspective look (Workbench), camera %s -> %s, %g mm"
                  % (fr, rp["location_m"], rp["look_at_m"], rp["lens_mm"]), "white", 2, bg="black")
        cells.append(img)
    imgio.save_png(opath("perspective_frames.png"), draw.grid(cells, ncols=1, gap=8, bg="black"))
    log("perspective renders written: frames %s" % (rp["frames"],))


# ====================================================================== 実行入口
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all", "measure", "analyze", "render"])
    ap.add_argument("--frames", nargs=2, type=int, default=None)
    args = bootstrap.parse_args(ap)
    bootstrap.set_log_prefix("REF")
    tl = P("target_timeline")
    assert tl["fps"] == paths.param("fps") and tl["total_frames"] == paths.param("total_frames") \
        and list(tl["backlog_seconds"]) == list(paths.param("backlog_phase_seconds")), "target_timeline differs from params.json"
    if args.stage in ("all", "measure"):
        stage_measure(args.frames)
    if args.stage in ("all", "analyze") and args.frames is None:
        stage_analyze()
    if args.stage in ("all", "render") and args.frames is None:
        stage_render()
    bootstrap.finish(True, "read_houdini_motion %s" % args.stage)


if __name__ == "__main__":
    main()
