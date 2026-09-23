"""CAM_print から見た Blender メッシュの輪郭マスクと、そこから抽出する順序付きの波断面。
評価済みメッシュ形状だけを見るため、シェイプキー、Geometry Nodes、Alembic
キャッシュなど、形状の生成方法を問わず利用できる。

視点の幾何
----------
CAM_print は +Y 方向を見る正投影カメラ。輪郭は全三角形を XZ 平面へ投影した和集合。
`ViewRect` はワールド単位（メートル）の画面矩形と画素格子を表す。
既定値は gw.frame の CAM_print の構図（仕様4）。大きさや位置が異なる
Houdini の参照映像などには別の矩形も使える。

波の形状に固有の注意
------------------
波メッシュは閉じていない1枚の面である。真横から見ると、Y 方向に変化する
部分だけが面積を持つ輪郭を作る。断面を Y 方向へ単純に押し出すと投影は面積0の
曲線になり、塗る画素がない。端で断面を静水面へ縮めることで、完全な断面から
平らな端までの掃引が波の内部を覆う。静水面より下は `water_z` による
水の層で埋める。したがって次の点に注意する。

* 絞り込みが波本体全体を掃引しないと、マスク内に埋まらない穴が残る。
  `raster.hole_report(mask)` と profile['holes'] で報告する。
* 端の小さな断面が波頭の下の凹部を横切ると（Z だけを縮小した場合など）、
  空洞越しの視線を遮り、内側の弧が消える。これは3D形状の性質である
  （仕様5の注2）。tests/selftest_measure.py に例がある。

測定に用いる評価状態（2026-09-20 の2回目の強化）
------------------------------------------------
ここでは `bpy.context.evaluated_depsgraph_get()` によるビューポートでの評価を
測定する。`show_viewport` が有効なモディファイアーを含み、細分化では
ビューポート側の `levels` を使う。一方、レンダリングや RENDER モードの
Alembic 書出しは `show_render` / `render_levels` を使う。
どちらか片方だけに存在する形状があると、差が見えないまま誤測定する。
`viewport_render_mismatches(objs)` が差を列挙し、テストは差があれば INVALID とする。

断面
----
`extract_profile(mask, rect)` は左画面端から峰、波頭、その下面、内側の弧、谷を経て
右画面端の水面に至る、波と背景の間の順序付き境界を返す。
噴霧や孤立した斑点は輪郭線から除く（最大の8近傍連結成分を使い、背景には
画面端につながる4近傍成分を使う。囲まれた穴は埋めて報告する）。
ただし除去を黙って行わず、profile['components'] に各成分の面積と外接矩形
（px と H）を記録し、ラスタ化ノイズ 'specks' と実際に離れた形状 'islands' を
SPECK_AREA_PX_FULL_RES で区別する。有限でない頂点と、それにより除いた三角形は
info['n_nonfinite_vertices'] と info['n_dropped_triangles'] に数を記録する。
境界は画素間の線を正確に追跡し（波は右側）、画素中心を標本化したマスクに
偏りを生じさせないよう画素間の中点へ変換する。弧長方向の小さなガウス平滑化で
階段状の揺らぎを取り、一定間隔で再標本化する。
"""
import math
import time

import numpy as np

from . import draw, frame as gw_frame, raster

__all__ = [
    "ViewRect", "mesh_world_triangles", "mask_from_triangles", "silhouette_mask", "profile_of_objects",
    "profiles_over_frames", "drop_nonfinite_triangles", "speck_area_limit_px", "SPECK_AREA_PX_FULL_RES",
    "trace_boundary", "extract_profile", "ProfileError", "setup_cam_print", "viewport_render_mismatches",
    "make_camera_for_rect", "render_mask_cycles", "compare_masks", "draw_overlay",
]


class ProfileError(RuntimeError):
    """マスクから波断面を抽出できない場合の例外。例: 左画面端に波が接しない。"""


# ====================================================================== 画面矩形 ViewRect
class ViewRect:
    """ワールド単位の画面矩形、画素格子、任意の H 正規化を表す。

    ワールドでは X が右、Z が上（メートル）。画素は左上が原点、Y が下の連続座標。
    mirror_x=True なら画像の X 軸をワールドの -X 方向に向ける。
    -X へ進む波の参照画像に使い、正規化した X_H も反転させる。
    このため +X_H は常に画像の右、すなわち船側になる。

    正規化した H 座標: X_H = ±(X - x0) / H、Z_H = (Z - z0) / H。
    CAM_print では x0=0、z0=0、H=WAVE_HEIGHT_M。
    """

    def __init__(self, x_min, x_max, z_min, z_max, width_px, height_px, mirror_x=False,
                 H=1.0, x0=0.0, z0=0.0, is_cam_print=False, name="rect"):
        if not (x_max > x_min and z_max > z_min):
            raise ValueError("矩形の幅または高さがありません")
        self.x_min, self.x_max = float(x_min), float(x_max)
        self.z_min, self.z_max = float(z_min), float(z_max)
        self.width_px, self.height_px = int(width_px), int(height_px)
        self.mirror_x = bool(mirror_x)
        self.H, self.x0, self.z0 = float(H), float(x0), float(z0)
        self.is_cam_print = bool(is_cam_print)
        self.name = str(name)
        self.px_per_unit_x = self.width_px / (self.x_max - self.x_min)
        self.px_per_unit_z = self.height_px / (self.z_max - self.z_min)

    # ---- 生成
    @classmethod
    def from_cam_print(cls, H=None, scale=1.0, frame_obj=None):
        """波高 H [m] に対する CAM_print の構図（仕様4）。既定値は params.json。
        scale<1 なら画素格子を同比率で縮める。Z 範囲はその解像度で実際の Blender
        カメラが収める範囲で、Frame.cam_print と一致する。"""
        F = frame_obj or (gw_frame.Frame.from_params(wave_height_m=H) if H is not None else gw_frame.get_frame())
        res_x = int(round(F.width_px * float(scale)))
        spec = F.cam_print(res_x=res_x)
        x0, x1 = spec["x_range_m"]
        z0, z1 = spec["z_range_covered_m"]
        r = cls(x0, x1, z0, z1, spec["resolution_x"], spec["resolution_y"], False, F.H, 0.0, 0.0,
                True, "CAM_print x%.4g" % scale)
        r.frame = F
        return r

    @classmethod
    def from_bounds(cls, x_min, x_max, z_min, z_max, width_px=None, px_per_unit=None,
                    mirror_x=False, H=1.0, x0=0.0, z0=0.0, name="custom"):
        """任意の矩形を作る。width_px または px_per_unit を指定する。
        z_min を下に延ばして行数を整数とし、画素を正方形にする。"""
        if width_px is None:
            if px_per_unit is None:
                raise ValueError("width_px または px_per_unit を指定してください")
            width_px = int(math.ceil((x_max - x_min) * px_per_unit))
        upp = (x_max - x_min) / float(width_px)          # 1画素あたりのワールド単位。
        height_px = int(math.ceil((z_max - z_min) / upp - 1e-9))
        return cls(x_min, x_max, z_max - height_px * upp, z_max, width_px, height_px,
                   mirror_x, H, x0, z0, False, name)

    def scaled(self, scale):
        """同じ矩形で画素格子を `scale` 倍する。画素数は整数に丸める。"""
        if self.is_cam_print:
            return ViewRect.from_cam_print(scale=scale * self.width_px / float(self.frame.width_px),
                                           frame_obj=self.frame)
        return ViewRect.from_bounds(self.x_min, self.x_max, self.z_min, self.z_max,
                                    width_px=int(round(self.width_px * scale)), mirror_x=self.mirror_x,
                                    H=self.H, x0=self.x0, z0=self.z0, name=self.name)

    # ---- 座標変換。スカラーと配列の両方を受け付ける。
    def world_to_px(self, X, Z):
        X = np.asarray(X, dtype=np.float64)
        Z = np.asarray(Z, dtype=np.float64)
        if self.mirror_x:
            x = (self.x_max - X) * self.px_per_unit_x
        else:
            x = (X - self.x_min) * self.px_per_unit_x
        y = (self.z_max - Z) * self.px_per_unit_z
        return x, y

    def px_to_world(self, x, y):
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        X = (self.x_max - x / self.px_per_unit_x) if self.mirror_x else (self.x_min + x / self.px_per_unit_x)
        Z = self.z_max - y / self.px_per_unit_z
        return X, Z

    def world_to_H(self, X, Z):
        s = -1.0 if self.mirror_x else 1.0
        return s * (np.asarray(X, dtype=np.float64) - self.x0) / self.H, (np.asarray(Z, dtype=np.float64) - self.z0) / self.H

    def H_to_world(self, XH, ZH):
        s = -1.0 if self.mirror_x else 1.0
        return self.x0 + s * np.asarray(XH, dtype=np.float64) * self.H, self.z0 + np.asarray(ZH, dtype=np.float64) * self.H

    def px_to_H(self, x, y):
        return self.world_to_H(*self.px_to_world(x, y))

    def H_to_px(self, XH, ZH):
        return self.world_to_px(*self.H_to_world(XH, ZH))

    def pts_px_to_H(self, pts):
        pts = np.asarray(pts, dtype=np.float64)
        X, Z = self.px_to_H(pts[..., 0], pts[..., 1])
        return np.stack([X, Z], axis=-1)

    def pts_H_to_px(self, pts):
        pts = np.asarray(pts, dtype=np.float64)
        x, y = self.H_to_px(pts[..., 0], pts[..., 1])
        return np.stack([x, y], axis=-1)

    def to_painting_px(self, pts_px):
        """マスクの画素座標を原画の画素座標に変換する。CAM_print の矩形でのみ有効。"""
        if not self.is_cam_print:
            raise ValueError("CAM_print の矩形ではありません")
        return self.frame.pts_H_to_px(self.pts_px_to_H(pts_px))

    def summary(self):
        return {"name": self.name, "x_min": self.x_min, "x_max": self.x_max, "z_min": self.z_min,
                "z_max": self.z_max, "width_px": self.width_px, "height_px": self.height_px,
                "mirror_x": self.mirror_x, "H": self.H, "x0": self.x0, "z0": self.z0,
                "is_cam_print": self.is_cam_print, "px_per_unit": self.px_per_unit_x}


# ====================================================================== ビューポートとレンダリングの状態
def viewport_render_mismatches(objs):
    """指定したオブジェクトについて、ビューポートとレンダリング評価の差を調べる。
    このモジュールとテストはビューポートの依存グラフを測定する。対象は次の通り。
      * モディファイアーの show_viewport と show_render の差。
      * 細分化などの `levels` と `render_levels` の差。
      * オブジェクト自体の hide_viewport と hide_render の差。
    {'object', 'modifier', 'type', 'what', 'viewport', 'render'} の一覧を返す。
    オブジェクト自体のフラグでは modifier は None。空リストなら両方のスタックは同じ。
    制約: 'Is Viewport' 入力で切り替えるノード、評価モードを読むドライバー／
    ハンドラー、シーンの簡略化設定による差は検出できない。"""
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    out = []
    for obj in objs:
        if bool(getattr(obj, "hide_viewport", False)) != bool(getattr(obj, "hide_render", False)):
            out.append({"object": obj.name, "modifier": None, "type": "OBJECT", "what": "hide_viewport != hide_render",
                        "viewport": bool(obj.hide_viewport), "render": bool(obj.hide_render)})
        for md in getattr(obj, "modifiers", []):
            if bool(md.show_viewport) != bool(md.show_render):
                out.append({"object": obj.name, "modifier": md.name, "type": md.type, "what": "show_viewport != show_render",
                            "viewport": bool(md.show_viewport), "render": bool(md.show_render)})
            if hasattr(md, "levels") and hasattr(md, "render_levels") and int(md.levels) != int(md.render_levels) \
                    and (md.show_viewport or md.show_render):
                out.append({"object": obj.name, "modifier": md.name, "type": md.type, "what": "levels != render_levels",
                            "viewport": int(md.levels), "render": int(md.render_levels)})
    return out


# ====================================================================== メッシュから三角形へ
def mesh_world_triangles(objs, depsgraph=None, y_range=None):
    """Blender メッシュを評価してワールド空間の三角形を返す。

    objs: メッシュとして評価できるオブジェクト、またはそのリスト。
    depsgraph: 既定値は bpy.context.evaluated_depsgraph_get()。先に scene.frame_set を呼ぶ。
      これはビューポート評価であり、show_viewport と細分化のビューポート設定を使う。
      viewport_render_mismatches() も参照。
    y_range: 任意のワールド単位の (y_min, y_max)。3頂点すべてが範囲内の三角形だけを残す。
      参照映像の水槽壁を除く用途などに使う。
    戻り値は (verts: ワールド座標の float64 (N, 3)、tris: verts の番号の int64 (M, 3)、info)。

    有限でない形状を黙って捨てない。NaN / inf の頂点は投影できないため、それを使う三角形を
    この時点で `tris` から除いて数える。y_range による絞り込みより先に行う。
      info['n_nonfinite_vertices']: 座標に有限でない値を含む頂点数。
      info['n_dropped_triangles']: それらの頂点を使うため除いた三角形数。
      info['nonfinite_vertex_indices']: 該当頂点の番号、先頭20件。
      info['objects'][k]: オブジェクトごとの同じ2種類の数。
    `verts` の長さと順は維持し、問題の行も残すため頂点番号は有効。
    隣接する掃引面が隙間を覆い、三角形を除いたマスクが正常に見える場合もある。
    呼出側は必ず2種類の数を確認する。
    """
    import bpy
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    depsgraph = depsgraph or bpy.context.evaluated_depsgraph_get()
    all_v, all_t, base = [], [], 0
    info = {"objects": [], "n_vertices": 0, "n_triangles": 0, "n_nonfinite_vertices": 0, "n_dropped_triangles": 0,
            "nonfinite_vertex_indices": []}
    for obj in objs:
        ev = obj.evaluated_get(depsgraph)
        me = ev.to_mesh()
        try:
            n = len(me.vertices)
            co = np.empty(n * 3, np.float32)
            me.vertices.foreach_get("co", co)
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            tri = np.empty(nt * 3, np.int32)
            me.loop_triangles.foreach_get("vertices", tri)
        finally:
            ev.to_mesh_clear()
        M = np.array(ev.matrix_world, dtype=np.float64)
        v = co.reshape(n, 3).astype(np.float64)
        with np.errstate(invalid="ignore", over="ignore"):
            v = v @ M[:3, :3].T + M[:3, 3]
        t_obj = tri.reshape(nt, 3).astype(np.int64)
        bad_v_obj = ~np.isfinite(v).all(axis=1)
        n_bad_t_obj = int(bad_v_obj[t_obj].any(axis=1).sum()) if (nt and bad_v_obj.any()) else 0
        all_v.append(v)
        all_t.append(t_obj + base)
        base += n
        info["objects"].append({"name": obj.name, "n_vertices": n, "n_triangles": nt,
                                "n_nonfinite_vertices": int(bad_v_obj.sum()), "n_dropped_triangles": n_bad_t_obj})
    verts = np.concatenate(all_v) if all_v else np.zeros((0, 3))
    tris = np.concatenate(all_t) if all_t else np.zeros((0, 3), np.int64)
    tris, nf = drop_nonfinite_triangles(verts, tris)
    info.update(nf)
    if y_range is not None and tris.size:
        yy = verts[:, 1][tris]
        keep = (yy >= y_range[0]).all(axis=1) & (yy <= y_range[1]).all(axis=1)
        tris = tris[keep]
    info["n_vertices"] = int(verts.shape[0])
    info["n_triangles"] = int(tris.shape[0])
    return verts, tris, info


def drop_nonfinite_triangles(verts, tris):
    """X、Y、Z に有限でない座標を持つ頂点を使う三角形を除き、その数を記録する。
    戻り値は (除去後の tris, {'n_nonfinite_vertices', 'n_dropped_triangles',
    'nonfinite_vertex_indices'（先頭20件）})。n_nonfinite_vertices は三角形で使われたかに関係なく、
    `verts` にある有限でない値を持つ全行を数える。"""
    verts = np.asarray(verts, dtype=np.float64)
    tris = np.asarray(tris, dtype=np.int64)
    bad_v = ~np.isfinite(verts).all(axis=1) if verts.size else np.zeros(verts.shape[0], bool)
    out = {"n_nonfinite_vertices": int(bad_v.sum()), "n_dropped_triangles": 0,
           "nonfinite_vertex_indices": [int(i) for i in np.nonzero(bad_v)[0][:20]]}
    if bad_v.any() and tris.size:
        bad_t = bad_v[tris].any(axis=1)
        out["n_dropped_triangles"] = int(bad_t.sum())
        tris = tris[~bad_t]
    return tris, out


def mask_from_triangles(verts_world, tris, rect, water_z=0.0, thin="skip", thin_px=1.0, exact=True):
    """numpy のみでワールド空間の三角形を Y 方向に投影し、`rect` の輪郭マスクを作る。

    water_z: 水の層の上面のワールド Z。画面内でその高さ以下を埋める。None なら層はなし。
    exact: True なら1画素未満の境界交点も info['edges']（raster.EdgeData）に記録する。
      extract_profile(mask, rect, edges=info['edges']) は ±0.5 px ではなく浮動小数精度の
      境界点を返す。時間は約2倍、メモリは float32 画像4枚分。False ならマスクだけ。
    戻り値は (bool マスク (rect.height_px, rect.width_px), info)。

    有限でない形状は黙って捨てない。NaN / inf の頂点を使う三角形はラスタ化前に除き、
    info['n_nonfinite_vertices']（`verts_world` の該当する全行）と
    info['n_dropped_triangles'] に数を記録する。drop_nonfinite_triangles を参照。
    ラスタ化後の画素座標で有限でない三角形は別に info['n_nonfinite'] に数える。
    """
    verts_world = np.asarray(verts_world, dtype=np.float64)
    tris = np.asarray(tris, dtype=np.int64)
    t0 = time.perf_counter()
    tris, nf_info = drop_nonfinite_triangles(verts_world, tris)
    with np.errstate(invalid="ignore"):
        x, y = rect.world_to_px(verts_world[:, 0], verts_world[:, 2])
    tri_px = np.stack([x[tris], y[tris]], axis=-1)
    w, h = rect.width_px, rect.height_px
    y_w = None
    if water_z is not None:
        y_w = float(rect.world_to_px(0.0, float(water_z))[1])
    if exact:
        mesh_area = None
        if y_w is not None and y_w < h:
            yb = max(h + 2.0, y_w + 2.0)
            slab = np.array([[[-2.0, y_w], [w + 2.0, y_w], [w + 2.0, yb]],
                             [[-2.0, y_w], [w + 2.0, yb], [-2.0, yb]]])
            tri_px = np.concatenate([tri_px, slab], axis=0)
        mask, edges, info = raster.rasterize_exact(tri_px, w, h, thin=thin, thin_px=thin_px)
        info["edges"] = edges
        if y_w is not None:
            j = int(np.clip(np.ceil(y_w - 0.5 - 1e-9), 0, h))
            mesh_area = int(mask[:j].sum())
        info["mesh_area_px"] = int(mask.sum()) if mesh_area is None else mesh_area
        info["mesh_area_note"] = "水の層より上の画素" if y_w is not None else "全画素"
    else:
        mask, info = raster.rasterize_triangles(tri_px, w, h, thin=thin, thin_px=thin_px, return_info=True)
        info["mesh_area_px"] = int(mask.sum())
        info["mesh_area_note"] = "水の層を追加する前のメッシュ画素"
        info["edges"] = None
        if y_w is not None:
            raster.fill_below(mask, y_w)
    info["water_z"] = None if water_z is None else float(water_z)
    info["water_y_px"] = y_w
    info.update(nf_info)
    info["n_mesh_triangles_rasterized"] = int(tris.shape[0])
    info["seconds_rasterize"] = time.perf_counter() - t0
    return mask, info


def silhouette_mask(objs, rect=None, H=None, scale=1.0, water_z=0.0, thin="skip", thin_px=1.0,
                    y_range=None, depsgraph=None, exact=True):
    """CAM_print（または `rect`）から見た、評価済み Blender メッシュの輪郭。

    rect: ViewRect。既定値は ViewRect.from_cam_print(H, scale)。
    H: 既定の矩形で使うメートル単位の波高。既定値は params.json の WAVE_HEIGHT_M。
    scale: 既定の矩形の解像度比。1.0 なら 3859 x 2594。
    water_z: 水の層の上面のワールド Z。既定値0は静水面、None は無効。
    exact: mask_from_triangles を参照。
    (bool マスク, info 辞書) を返す。info['edges'] は extract_profile に渡せる。
    info['n_nonfinite_vertices'] と info['n_dropped_triangles'] は有限でない頂点と、
    そのためマスクから除いた三角形の数。正常なメッシュでは両方0。
    オブジェクトごとの数は info['mesh']['objects'] にある。
    """
    if rect is None:
        rect = ViewRect.from_cam_print(H=H, scale=scale)
    t0 = time.perf_counter()
    verts, tris, minfo = mesh_world_triangles(objs, depsgraph, y_range)
    t1 = time.perf_counter()
    mask, info = mask_from_triangles(verts, tris, rect, water_z, thin, thin_px, exact)
    # mesh_world_triangles は有限でない頂点を使う三角形を既に除いて数えている。
    # mask_from_triangles は同じ問題の頂点を見るが問題の三角形は見ないため、合計／大きい方を報告する。
    info["n_dropped_triangles"] = int(info["n_dropped_triangles"] + minfo["n_dropped_triangles"])
    info["n_nonfinite_vertices"] = int(max(info["n_nonfinite_vertices"], minfo["n_nonfinite_vertices"]))
    info.update({"mesh": minfo, "seconds_get_mesh": t1 - t0, "rect": rect.summary()})
    return mask, info


def profile_of_objects(objs, rect=None, H=None, scale=1.0, water_z=0.0, exact=True, y_range=None,
                       depsgraph=None, keep_mask=False):
    """シーンの現在フレームに対して silhouette_mask と extract_profile を1回で実行する。
    (断面の辞書, マスク, info) を返す。メモリ節約のため info から EdgeData を除く。"""
    if rect is None:
        rect = ViewRect.from_cam_print(H=H, scale=scale)
    mask, info = silhouette_mask(objs, rect=rect, water_z=water_z, y_range=y_range,
                                 depsgraph=depsgraph, exact=exact)
    prof = extract_profile(mask, rect, edges=info.get("edges"), keep_mask=keep_mask)
    info["edges"] = None
    return prof, mask, info


def profiles_over_frames(objs, frames, scene=None, rect=None, H=None, scale=0.5, water_z=0.0, exact=True,
                         y_range=None, on_frame=None):
    """`frames` の各フレームの断面を求める。各回で scene.frame_set を呼ぶ。

    exact=True なら精度が解像度に依存しないため、運動曲線（仕様6.2）には
    scale=0.25～0.5 で足りる。on_frame(frame, profile, mask, info) は
    重ね画像の保存などに使える任意のフック。マスクは保持しない。
    戻り値は {frame, H (N, 2) の順序付き断面, complete, holes, components,
    n_nonfinite_vertices, n_dropped_triangles, seconds} の辞書のリスト。
    gw.profile_metrics.measure_sequence([p['H'] for p in result]) に渡せる。
    """
    import bpy
    scene = scene or bpy.context.scene
    if rect is None:
        rect = ViewRect.from_cam_print(H=H, scale=scale)
    out = []
    for fr in frames:
        t0 = time.perf_counter()
        scene.frame_set(int(fr))
        prof, mask, info = profile_of_objects(objs, rect=rect, water_z=water_z, exact=exact, y_range=y_range)
        if on_frame is not None:
            on_frame(int(fr), prof, mask, info)
        out.append({"frame": int(fr), "H": prof["H"], "px": prof["px"], "complete": prof["complete"],
                    "end_border": prof["end_border"], "holes": prof["holes"], "components": prof["components"],
                    "n_nonfinite_vertices": info.get("n_nonfinite_vertices"),
                    "n_dropped_triangles": info.get("n_dropped_triangles"),
                    "n_cracks_without_exact_data": prof["n_cracks_without_exact_data"],
                    "seconds": time.perf_counter() - t0})
    return out


# ====================================================================== 境界追跡
_DX = (1, 0, -1, 0)      # d: 0 が右、1 が下、2 が左、3 が上。画像座標では Y が下向き。
_DY = (0, 1, 0, -1)
_AL = ((0, -1), (0, 0), (-1, 0), (-1, -1))     # 頂点から見た進行方向左前の画素のずれ。
_AR = ((0, 0), (-1, 0), (-1, -1), (0, -1))     # 進行方向右前の画素のずれ。


def trace_boundary(wave, start_row=None, max_steps=None):
    """bool マスク `wave` の画素間をたどり、境界を追跡する。

    左画面端の列0で最上部の波画素の上端から始める。波を右側に見ながら
    画素間を歩き（波は8近傍、背景は4近傍）、再び画面端に達するまで続ける。
    (int64 の画素間頂点 (n, 2)、終端の辺 'right'|'top'|'bottom'|'left') を返す。
    """
    W = np.ascontiguousarray(wave, dtype=bool)
    h, w = W.shape
    col0 = W[:, 0]
    if start_row is None:
        if not col0.any():
            raise ProfileError("マスクが左画面端に接していません（水の層がなく、メッシュも画面端に届かない可能性があります）")
        j0 = int(np.argmax(col0))
    else:
        j0 = int(start_row)
    if j0 <= 0:
        return np.array([[0, 0]], np.int64), "top"
    rows = [r.tobytes() for r in W.view(np.uint8)]
    if max_steps is None:
        max_steps = 8 * (w + h) + 4 * int(W.sum() ** 0.5) * 200 + 2_000_000

    def is_w(i, j):
        return 0 <= i < w and 0 <= j < h and rows[j][i] != 0

    vx, vy, d = 0, j0, 0
    path = [(vx, vy)]
    steps = 0
    while True:
        al = _AL[d]
        ar = _AR[d]
        if is_w(vx + al[0], vy + al[1]):
            d = (d + 3) % 4
        elif is_w(vx + ar[0], vy + ar[1]):
            pass
        else:
            d = (d + 1) % 4
        vx += _DX[d]
        vy += _DY[d]
        path.append((vx, vy))
        steps += 1
        if vx <= 0 or vx >= w or vy <= 0 or vy >= h:
            break
        if steps > max_steps:
            raise ProfileError("boundary trace did not terminate (%d steps)" % steps)
    end = "right" if vx >= w else ("top" if vy <= 0 else ("bottom" if vy >= h else "left"))
    return np.asarray(path, dtype=np.int64), end


def _resample_polyline(pts, spacing):
    """弧長方向に等間隔で再標本化する。始点と終点は保持する。"""
    seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    if total <= 0:
        return pts[:1].copy()
    n = max(2, int(round(total / float(spacing))) + 1)
    si = np.linspace(0.0, total, n)
    return np.stack([np.interp(si, s, pts[:, 0]), np.interp(si, s, pts[:, 1])], axis=1)


def _gauss_smooth_open(pts, sigma):
    """等間隔に標本化された開いた折れ線をガウス平滑化する。
    奇反射で両端を固定し、直線は直線のまま保つ。"""
    n = pts.shape[0]
    if sigma <= 0 or n < 5:
        return pts.copy()
    r = int(min(math.ceil(4.0 * sigma), n - 1))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / float(sigma)) ** 2)
    k /= k.sum()
    out = np.empty_like(pts)
    for c in range(2):
        v = pts[:, c]
        left = 2.0 * v[0] - v[r:0:-1]
        right = 2.0 * v[-1] - v[-2:-r - 2:-1]
        out[:, c] = np.convolve(np.concatenate([left, v, right]), k, mode="valid")
    out[0] = pts[0]
    out[-1] = pts[-1]
    return out


def _exact_crossings(verts, edges):
    """追跡した各画素間の境界を、両側の画素中心を結ぶ線上の正確な交点に置き換える。
    点列と、正確な交点データがない境界の数を返す。"""
    V = verts
    d = np.diff(V, axis=0)
    n = d.shape[0]
    vx, vy = V[:-1, 0], V[:-1, 1]
    down, up = d[:, 1] == 1, d[:, 1] == -1
    right, left = d[:, 0] == 1, d[:, 0] == -1
    # 波が右側にある各移動について、内部の画素（行 j・列 i）と境界位置を求める。
    j = np.where(down, vy, np.where(up, vy - 1, np.where(right, vy, vy - 1)))
    i = np.where(down, vx - 1, np.where(up, vx, np.where(right, vx, vx - 1)))
    base = np.where(down | up, vx, vy).astype(np.float64)
    h, w = edges.shape
    ok_idx = (j >= 0) & (j < h) & (i >= 0) & (i < w)
    jc, ic = np.clip(j, 0, h - 1), np.clip(i, 0, w - 1)
    c = np.where(down, edges.x_hi[jc, ic], np.where(up, edges.x_lo[jc, ic],
                 np.where(right, edges.y_lo[jc, ic], edges.y_hi[jc, ic]))).astype(np.float64)
    # 細片については、隙間を含む境界だけを扱う。
    kr, kc = edges._sl_row[0], edges._sl_col[0]
    key = np.where(down, j * (w + 2) + (i + 1), np.where(up, j * (w + 2) + i,
                   np.where(right, i * (h + 2) + j, i * (h + 2) + (j + 1))))
    has = np.zeros(n, bool)
    if kr.size:
        m = down | up
        has[m] = np.searchsorted(kr, key[m], "right") > np.searchsorted(kr, key[m], "left")
    if kc.size:
        m = right | left
        has[m] = np.searchsorted(kc, key[m], "right") > np.searchsorted(kc, key[m], "left")
    for k in np.nonzero(has & ok_idx & np.isfinite(c))[0]:
        kind = "right" if down[k] else ("left" if up[k] else ("top" if right[k] else "bottom"))
        c[k] = edges.crossing(kind, int(j[k]), int(i[k]))
    bad = ~ok_idx | ~np.isfinite(c) | (np.abs(c - base) > 0.5 + 1e-3)
    c = np.where(bad, base, c)
    px = np.where(down | up, c, i + 0.5)
    py = np.where(down | up, j + 0.5, c)
    return np.stack([px, py], axis=1), int(bad.sum())


SPECK_AREA_PX_FULL_RES = 25.0
"""除去した独立マスク成分のうち、この面積より小さいものを 'specks'、それ以外を 'islands' と呼ぶ。
面積は原画の全解像度（3859×2594 px）での画素数。25 px は 5×5 px、画像高の
0.19×0.19 %、8.5e-6 H² に相当する。マスクの線形解像度の二乗に応じて換算するため、
解像度が異なっても同じ形状を同じ種類に分類できる。仕様由来ではない基礎設定値。
細片のラスタ化に伴うごみは 1～数画素で、5×5 px 以上は制作された形状とみなす。"""


def speck_area_limit_px(rect, speck_area_px_full_res=None):
    """全解像度での SPECK_AREA_PX_FULL_RES を `rect` のマスク画素面積へ換算する。
    限界面積 = 全解像度の限界面積 × (rect の H 当たり画素数 / 原画の H 当たり画素数)²。"""
    full = SPECK_AREA_PX_FULL_RES if speck_area_px_full_res is None else float(speck_area_px_full_res)
    F = getattr(rect, "frame", None) or gw_frame.get_frame()
    lin = (rect.px_per_unit_z * rect.H) / F.px_per_H
    return float(full * lin * lin)


def _bbox_px_to_H(rect, bbox_px):
    """右端・下端を含まない画素境界枠を、H 単位の [X_min, Z_min, X_max, Z_max] に変換する。"""
    x0, y0, x1, y1 = (float(v) for v in bbox_px)
    Xa, Za = rect.px_to_H(x0, y1)
    Xb, Zb = rect.px_to_H(x1, y0)
    return [float(min(Xa, Xb)), float(min(Za, Zb)), float(max(Xa, Xb)), float(max(Za, Zb))]


def extract_profile(mask, rect, edges=None, smooth_sigma_px=None, spacing_px=None, keep_mask=False,
                    speck_area_px_full_res=None):
    """シルエットマスクから順序付きの波断面を抽出する。

    mask は波と水の層が True の真偽値マスク。rect はラスタ化に使った ViewRect。
    edges は exact=True の silhouette_mask が返す raster.EdgeData。存在すれば境界点を
    画素中心間の格子線と輪郭の正確な交点として求め、平滑化を要しない。なければ
    境界の中点（誤差 ±0.5 px）をガウス平滑化する。smooth_sigma_px は弧長方向の
    σ で、既定値は edges ありで 0、なしで 2.0。半径 R の凸円弧は約 σ²/(2R) px
    内側へ移る。spacing_px は出力間隔で、既定値は 1.0 / 2.0 px。
    speck_area_px_full_res は全解像度での小成分の限界面積（既定 25 px）。

    最大の 8 連結成分だけを追跡し、他は除去して profile['components'] に必ず報告する。
    removed_area_px / n_removed は総面積・総数、n_removed_specks / removed_specks_area_px は
    小成分、n_removed_islands / removed_islands_area_px はそれ以外の独立形状の数・面積。
    限界値は現在と全解像度の画素で記録する。removed には面積、種別、境界枠、中心を
    大きい順で最大 20 件含める。空洞内の独立形状は断面の指標を変えないため、形状の
    判定側は n_removed_islands を確認する必要がある。

    結果の px は画像左端→波頂→波頭先端→内側円弧→谷→画像右端の画素座標。
    world / H はワールド座標と H 正規化座標。painting_px は CAM_print の場合だけ。
    raw_px は平滑化前の点列。exact、n_cracks_without_exact_data、complete、
    end_border、n_trace_steps、components、holes、seconds も返す。
    """
    t0 = time.perf_counter()
    m = np.asarray(mask, dtype=bool)
    if m.shape != (rect.height_px, rect.width_px):
        raise ValueError("mask shape %r does not match the rect %r" % (m.shape, (rect.height_px, rect.width_px)))
    exact = edges is not None
    if smooth_sigma_px is None:
        smooth_sigma_px = 0.0 if exact else 2.0
    if spacing_px is None:
        spacing_px = 1.0 if exact else 2.0
    speck_lim = speck_area_limit_px(rect, speck_area_px_full_res)
    wave, cinfo = raster.largest_component(m, connectivity=8, speck_max_area_px=speck_lim)
    cinfo["speck_area_px_full_res"] = float(SPECK_AREA_PX_FULL_RES if speck_area_px_full_res is None else speck_area_px_full_res)
    for rc in cinfo["removed"]:
        rc["bbox_H"] = _bbox_px_to_H(rect, rc["bbox_px"])
        rc["centre_H"] = [0.5 * (rc["bbox_H"][0] + rc["bbox_H"][2]), 0.5 * (rc["bbox_H"][1] + rc["bbox_H"][3])]
    wave, holes_mask, hinfo = raster.fill_holes(wave, sky="top")
    tot = int(wave.sum())
    hinfo["filled_area_px"] = tot
    hinfo["hole_area_frac"] = float(hinfo["hole_area_px"]) / tot if tot else 0.0
    verts, end_border = trace_boundary(wave)
    v = verts.astype(np.float64)
    n_bad = None
    if v.shape[0] >= 2:
        if exact:
            mids, n_bad = _exact_crossings(verts, edges)
            first = np.array([[v[0, 0], mids[0, 1]]])
            last = np.array([[v[-1, 0], mids[-1, 1]]]) if end_border in ("right", "left") else v[-1:]
        else:
            mids = 0.5 * (v[:-1] + v[1:])
            first, last = v[:1], v[-1:]
        raw = np.concatenate([first, mids, last], axis=0)
    else:
        raw = v
    if raw.shape[0] >= 3:
        uni = _resample_polyline(raw, min(1.0, float(spacing_px)))
        sm = _gauss_smooth_open(uni, float(smooth_sigma_px))
        pts = _resample_polyline(sm, float(spacing_px))
    else:
        pts = raw.copy()
    X, Z = rect.px_to_world(pts[:, 0], pts[:, 1])
    out = {
        "px": pts,
        "world": np.stack([X, Z], axis=1),
        "H": rect.pts_px_to_H(pts),
        "raw_px": raw,
        "exact": bool(exact),
        "n_cracks_without_exact_data": n_bad,
        "complete": end_border == "right",
        "end_border": end_border,
        "n_trace_steps": int(verts.shape[0] - 1),
        "components": cinfo,
        "holes": hinfo,
        "smooth_sigma_px": float(smooth_sigma_px),
        "spacing_px": float(spacing_px),
        "rect": rect.summary(),
    }
    if rect.is_cam_print:
        out["painting_px"] = rect.to_painting_px(pts)
    if keep_mask:
        out["wave_mask"] = wave
        out["holes_mask"] = holes_mask
    out["seconds"] = time.perf_counter() - t0
    return out


# ====================================================================== Blender カメラと Cycles の照合
def setup_cam_print(scene=None, H=None, scale=1.0, name="CAM_print"):
    """波高 H [m]（既定値は params.json）に対する実際の判定カメラ CAM_print を作成・更新し、
    レンダー解像度を 3859×2594 の `scale` 倍にする。実装は gw.frame.Frame.make_cam_print に委ね、
    構図を数値で照合する。カメラ、ViewRect、照合結果を返す。"""
    import bpy
    scene = scene or bpy.context.scene
    F = gw_frame.Frame.from_params(wave_height_m=H) if H is not None else gw_frame.get_frame()
    rect = ViewRect.from_cam_print(scale=scale, frame_obj=F)
    cam = F.make_cam_print(scene, res_x=rect.width_px, name=name)
    check = _check_camera_matches_rect(scene, cam, rect)
    return cam, rect, check


def make_camera_for_rect(scene, rect, name="CAM_rect", distance=200.0, clip=(0.1, 2000.0)):
    """+Y 方向を見る正投影カメラで、反転していない `rect` を正確に収める。
    `scene` のレンダー解像度も設定する。"""
    import bpy
    if rect.mirror_x:
        raise ValueError("a mirrored rect cannot be represented by a camera looking along +Y")
    cam_data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam_data.type = "ORTHO"
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.ortho_scale = rect.x_max - rect.x_min
    cam_data.shift_x = cam_data.shift_y = 0.0
    cam_data.clip_start, cam_data.clip_end = clip
    obj = bpy.data.objects.get(name) or bpy.data.objects.new(name, cam_data)
    obj.data = cam_data
    if obj.name not in scene.collection.all_objects:
        scene.collection.objects.link(obj)
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
    obj.location = (0.5 * (rect.x_min + rect.x_max), -float(distance), 0.5 * (rect.z_min + rect.z_max))
    scene.render.resolution_x = rect.width_px
    scene.render.resolution_y = rect.height_px
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1.0
    scene.camera = obj
    return obj


def _check_camera_matches_rect(scene, cam, rect):
    """bpy_extras.world_to_camera_view で矩形の角を投影し、画素格子と照合する。
    最大誤差 max_err_px を返す。"""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    import bpy
    bpy.context.view_layer.update()
    errs = []
    for X, Z in ((rect.x_min, rect.z_min), (rect.x_max, rect.z_max), (rect.x_min, rect.z_max), (0.0, 0.0)):
        ndc = world_to_camera_view(scene, cam, Vector((X, 0.0, Z)))
        x_cam = ndc.x * rect.width_px
        y_cam = (1.0 - ndc.y) * rect.height_px
        x_r, y_r = rect.world_to_px(X, Z)
        errs.append(max(abs(x_cam - float(x_r)), abs(y_cam - float(y_r))))
    return {"max_err_px": float(max(errs))}


def render_mask_cycles(objs, rect, out_png, water_z=0.0, scene=None, samples=1, keep_setup=False):
    """照合用のレンダーを行う。Cycles CPU、`samples` 標本、黒いワールド上で白色発光の
    マテリアルを上書き適用し、Standard ビュー変換、ディザなし、小さい Blackman-Harris
    画素フィルタを使う。標本は画素中心に置かれる。水の層はオブジェクトの後ろに一時的な
    発光平面として置く。真偽値マスクと情報を返す。keep_setup=True でなければ設定を戻す。"""
    import bpy
    from . import imgio, paths
    scene = scene or bpy.context.scene
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    out_png = paths.ensure_parent(out_png)
    r = scene.render
    saved = {"engine": r.engine, "filepath": r.filepath, "res": (r.resolution_x, r.resolution_y, r.resolution_percentage),
             "camera": scene.camera, "film_transparent": r.film_transparent, "dither": r.dither_intensity,
             "view_transform": scene.view_settings.view_transform, "look": scene.view_settings.look,
             "world": scene.world, "fmt": (r.image_settings.file_format, r.image_settings.color_mode,
                                           r.image_settings.color_depth)}
    vl = bpy.context.view_layer
    saved_override = vl.material_override
    t0 = time.perf_counter()
    cam = make_camera_for_rect(scene, rect, name="CAM_maskcheck")
    r.engine = "CYCLES"
    cy = scene.cycles
    cy.device = "CPU"
    cy.samples = int(samples)
    cy.use_adaptive_sampling = False
    cy.use_denoising = False
    cy.pixel_filter_type = "BLACKMAN_HARRIS"
    cy.filter_width = 0.01
    cy.max_bounces = 0
    r.film_transparent = False
    r.dither_intensity = 0.0
    r.use_border = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "BW"
    r.image_settings.color_depth = "8"
    r.image_settings.compression = 15
    r.filepath = out_png
    # 黒いワールド。
    world = bpy.data.worlds.new("W_maskcheck")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is not None:
        bg.inputs[0].default_value = (0, 0, 0, 1)
        bg.inputs[1].default_value = 0.0
    scene.world = world
    # 白色発光の上書きマテリアル。
    mat = bpy.data.materials.new("M_maskcheck")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (1, 1, 1, 1)
    em.inputs[1].default_value = 1.0
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], outn.inputs[0])
    vl.material_override = mat
    slab = None
    if water_z is not None:
        y_far = 900.0
        me = bpy.data.meshes.new("slab_maskcheck")
        x0, x1 = rect.x_min - 1.0, rect.x_max + 1.0
        z0, z1 = rect.z_min - 1.0, float(water_z)
        me.from_pydata([(x0, y_far, z0), (x1, y_far, z0), (x1, y_far, z1), (x0, y_far, z1)], [], [(0, 1, 2, 3)])
        slab = bpy.data.objects.new("slab_maskcheck", me)
        scene.collection.objects.link(slab)
    hidden = []
    for ob in scene.objects:
        if ob.type == "MESH" and ob not in objs and ob is not slab and not ob.hide_render:
            ob.hide_render = True
            hidden.append(ob)
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        for ob in hidden:
            ob.hide_render = False
        vl.material_override = saved_override
        if slab is not None:
            me = slab.data
            bpy.data.objects.remove(slab)
            bpy.data.meshes.remove(me)
        if not keep_setup:
            r.engine = saved["engine"]
            r.filepath = saved["filepath"]
            r.resolution_x, r.resolution_y, r.resolution_percentage = saved["res"]
            scene.camera = saved["camera"]
            r.film_transparent = saved["film_transparent"]
            r.dither_intensity = saved["dither"]
            scene.view_settings.view_transform = saved["view_transform"]
            scene.view_settings.look = saved["look"]
            scene.world = saved["world"]
            r.image_settings.file_format, r.image_settings.color_mode, r.image_settings.color_depth = saved["fmt"]
            bpy.data.objects.remove(cam)
        bpy.data.materials.remove(mat)
        bpy.data.worlds.remove(world)
    img = imgio.load_image_rgb(out_png)
    vals = img[:, :, 0]
    mask = vals >= 128
    info = {"seconds": time.perf_counter() - t0, "n_gray_px": int(((vals > 0) & (vals < 255)).sum()),
            "path": out_png, "samples": int(samples)}
    return mask, info


def compare_masks(a, b):
    """二つの真偽値マスクで一致しない画素数と、それらの `a` の境界からの距離を返す。"""
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    if a.shape != b.shape:
        raise ValueError("mask shapes differ: %r vs %r" % (a.shape, b.shape))
    d = a != b
    n = int(d.sum())
    out = {"n_px": int(a.size), "n_disagree": n, "frac_disagree": n / float(a.size),
           "a_only": int((a & ~b).sum()), "b_only": int((b & ~a).sum())}
    # 境界から 1 px / 2 px 以内に分類する。輪郭を 8 近傍で拡張する。
    if n:
        edge = draw.mask_outline(a, 1) | draw.mask_outline(~a, 1)
        near1 = edge
        p = np.pad(near1, 1)
        near2 = np.zeros_like(near1)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                near2 |= p[dy:dy + a.shape[0], dx:dx + a.shape[1]]
        out["n_disagree_on_boundary_px"] = int((d & near1).sum())
        out["n_disagree_within_2px"] = int((d & near2).sum())
        out["n_disagree_far"] = int((d & ~near2).sum())
        ys, xs = np.nonzero(d & ~near2)
        out["far_examples_xy"] = [[int(x), int(y)] for x, y in list(zip(xs, ys))[:10]]
    else:
        out.update({"n_disagree_on_boundary_px": 0, "n_disagree_within_2px": 0, "n_disagree_far": 0,
                    "far_examples_xy": []})
    return out


# ====================================================================== 重ね画像
def draw_overlay(mask, profile, metrics=None, title=None, base=None, max_w=1600,
                 mask_color="blue", crop_px=None, crop_scale=None, extra_polylines=None):
    """色付きマスク、抽出輪郭、特徴点を重ねた RGB 画像を作る。

    mask と profile は同じ rect に対する silhouette_mask / extract_profile の結果。
    metrics を渡すと profile_metrics.measure_profile の特徴点を描く。
    base はマスクと同じ画素数の RGB 背景で、既定値は白。
    crop_px はマスク画素での切り出し範囲。crop_scale で拡大し、未指定なら
    幅 max_w 以下かつ 1 倍以上となる倍率を選ぶ。extra_polylines で折れ線を追加できる。
    画像上の文字は ASCII とし、uint8 RGB 画像を返す。"""
    h, w = mask.shape
    img = draw.canvas(h, w, "white") if base is None else draw.to_rgb(base).copy()
    draw.overlay_mask(img, mask, mask_color, 0.35)
    rect_s = profile["rect"]
    if crop_px is None:
        x0, y0, x1, y1 = 0, 0, w, h
        scale = min(1.0, max_w / float(w))
    else:
        x0, y0, x1, y1 = crop_px
        scale = crop_scale if crop_scale is not None else max(1.0, min(8.0, max_w / float(max(1, x1 - x0))))
    view = draw.View(img, x0, y0, x1, y1, scale=scale, method="auto" if scale < 1 else "nearest")
    out = view.img
    lw = 2.0
    pts = profile["px"]
    if metrics is not None and metrics.get("segments"):
        colors = {"back": "red", "head": "orange", "inner_arc": "magenta", "trough_run": "cyan", "front": "orange"}
        segs = metrics["segments"]
        drawn = False
        for name in ("back", "head", "inner_arc", "trough_run"):
            rng = segs.get(name)
            if rng is None:
                continue
            i0, i1 = rng
            if i1 > i0:
                draw.polyline(out, view.to_view(pts[i0:i1 + 1]), colors[name], lw)
                drawn = True
        if not drawn or segs.get("head") is None:
            rng = segs.get("front")
            if rng is not None:
                draw.polyline(out, view.to_view(pts[rng[0]:rng[1] + 1]), colors["front"], lw)
    else:
        draw.polyline(out, view.to_view(pts), "red", lw)
    for ex in (extra_polylines or []):                      # 見えるように最前面へ描く。
        draw.polyline(out, view.to_view(ex["px"]), ex.get("color", "green"), ex.get("width", 2.0),
                      dash=ex.get("dash"))
    if metrics is not None:
        H_to_px = lambda p: view.to_view(np.array(_rect_H_to_px(rect_s, p)))
        for key, label, col, off in (("crest", "crest", "red", (12, -12)), ("head_tip", "tip", "green", (12, -12)),
                                     ("inner_deepest", "deepest", "purple", (12, -12)),
                                     ("theta_point", "theta", "brown", (-12, 14))):
            lm = metrics["landmarks"].get(key)
            if lm is None:
                continue
            c = H_to_px(lm["H"])
            if -50 <= c[0] <= out.shape[1] + 50 and -50 <= c[1] <= out.shape[0] + 50:
                draw.label_point(out, c, label, col, scale=2, offset=off)
    if title:
        draw.text(out, 6, 6, title, "black", 2, bg="white", bg_alpha=0.85)
    return out


def _rect_H_to_px(rect_summary, pH):
    s = -1.0 if rect_summary["mirror_x"] else 1.0
    X = rect_summary["x0"] + s * pH[0] * rect_summary["H"]
    Z = rect_summary["z0"] + pH[1] * rect_summary["H"]
    if rect_summary["mirror_x"]:
        x = (rect_summary["x_max"] - X) * rect_summary["px_per_unit"]
    else:
        x = (X - rect_summary["x_min"]) * rect_summary["px_per_unit"]
    pz = rect_summary["height_px"] / (rect_summary["z_max"] - rect_summary["z_min"])
    y = (rect_summary["z_max"] - Z) * pz
    return [x, y]
