"""原画の画面座標とシーン座標の相互変換（仕様4）。numpy のみを使用する。

座標の約束
----------
* 画素座標: 左上が原点、右が X 正、下が Y 正の連続座標。画素 (i, j) は
  [i, i+1] x [j, j+1] を覆い、中心は (i + 0.5, j + 0.5)。
  X は [0, 3859]、Y は [0, 2594]。
* 百分率座標: 左から画像幅の何 % か、上から画像高さの何 % か（仕様5）。
* H 座標: 波高 H を単位とする (X_H, Z_H)。峰は (0, 1)、谷の水位は Z_H=0。
  +X は船側で、原画では右方向。
* メートル: H 座標に WAVE_HEIGHT_M を掛ける。
* 'pct_h': 画像高さに対する長さの百分率（1% = 25.94 px = 0.0151515 H）。
  水平方向の差も画像高さに対する百分率で表す。

基準値は params.json の crest_left_pct、crest_top_pct、height_pct と原画の寸法。
その他の値はここで計算する:

    frame_h  = 100 / height_pct                      = 1.515152 H
    frame_w  = frame_h * width_px / height_px        = 2.254036 H
    x_left   = -crest_left_pct/100 * frame_w         = -0.861042 H
    x_right  = x_left + frame_w                      = +1.392994 H
    z_top    = 1 + crest_top_pct/100 * frame_h       = +1.131818 H
    z_bottom = z_top - frame_h                       = -0.383333 H
"""
import math

import numpy as np

from . import paths


class Frame:
    """1枚の原画画面について座標を変換する。全メソッドがスカラーと配列を受け付ける。"""

    def __init__(self, width_px=3859, height_px=2594, crest_left_pct=38.2,
                 crest_top_pct=8.7, height_pct=66.0, wave_height_m=11.0):
        self.width_px = int(width_px)
        self.height_px = int(height_px)
        self.crest_left_pct = float(crest_left_pct)
        self.crest_top_pct = float(crest_top_pct)
        self.height_pct = float(height_pct)
        self.H = float(wave_height_m)

        self.frame_h = 100.0 / self.height_pct
        self.frame_w = self.frame_h * self.width_px / self.height_px
        self.x_left = -self.crest_left_pct / 100.0 * self.frame_w
        self.x_right = self.x_left + self.frame_w
        self.z_top = 1.0 + self.crest_top_pct / 100.0 * self.frame_h
        self.z_bottom = self.z_top - self.frame_h
        # 1画素あたりの H 単位。画素が正方形なので X と Y で同じ。
        self.H_per_px = self.frame_h / self.height_px
        self.px_per_H = self.height_px / self.frame_h

    # ---- 生成 -------------------------------------------------
    @classmethod
    def from_params(cls, params_path=None, wave_height_m=None):
        p = lambda k: paths.param(k, params_path)
        return cls(p("painting_width_px"), p("painting_height_px"), p("crest_left_pct"),
                   p("crest_top_pct"), p("height_pct"),
                   p("WAVE_HEIGHT_M") if wave_height_m is None else wave_height_m)

    def summary(self):
        keys = ("width_px", "height_px", "crest_left_pct", "crest_top_pct", "height_pct", "H",
                "frame_h", "frame_w", "x_left", "x_right", "z_top", "z_bottom",
                "H_per_px", "px_per_H")
        return {k: getattr(self, k) for k in keys}

    # 位置の変換
    def px_to_H(self, x_px, y_px):
        x_px = np.asarray(x_px, dtype=np.float64)
        y_px = np.asarray(y_px, dtype=np.float64)
        X = self.x_left + (x_px / self.width_px) * self.frame_w
        Z = self.z_top - (y_px / self.height_px) * self.frame_h
        return X, Z

    def H_to_px(self, X_H, Z_H):
        X_H = np.asarray(X_H, dtype=np.float64)
        Z_H = np.asarray(Z_H, dtype=np.float64)
        x = (X_H - self.x_left) / self.frame_w * self.width_px
        y = (self.z_top - Z_H) / self.frame_h * self.height_px
        return x, y

    def pct_to_px(self, left_pct, top_pct):
        return (np.asarray(left_pct, dtype=np.float64) / 100.0 * self.width_px,
                np.asarray(top_pct, dtype=np.float64) / 100.0 * self.height_px)

    def px_to_pct(self, x_px, y_px):
        return (np.asarray(x_px, dtype=np.float64) / self.width_px * 100.0,
                np.asarray(y_px, dtype=np.float64) / self.height_px * 100.0)

    def pct_to_H(self, left_pct, top_pct):
        return self.px_to_H(*self.pct_to_px(left_pct, top_pct))

    def H_to_pct(self, X_H, Z_H):
        return self.px_to_pct(*self.H_to_px(X_H, Z_H))

    def H_to_m(self, X_H, Z_H):
        return (np.asarray(X_H, dtype=np.float64) * self.H,
                np.asarray(Z_H, dtype=np.float64) * self.H)

    def m_to_H(self, X_m, Z_m):
        return (np.asarray(X_m, dtype=np.float64) / self.H,
                np.asarray(Z_m, dtype=np.float64) / self.H)

    def px_to_m(self, x_px, y_px):
        return self.H_to_m(*self.px_to_H(x_px, y_px))

    def m_to_px(self, X_m, Z_m):
        return self.H_to_px(*self.m_to_H(X_m, Z_m))

    # 形状が (N, 2) の配列を扱う関数
    def pts_px_to_H(self, pts_px):
        pts_px = np.asarray(pts_px, dtype=np.float64)
        X, Z = self.px_to_H(pts_px[..., 0], pts_px[..., 1])
        return np.stack([X, Z], axis=-1)

    def pts_H_to_px(self, pts_H):
        pts_H = np.asarray(pts_H, dtype=np.float64)
        x, y = self.H_to_px(pts_H[..., 0], pts_H[..., 1])
        return np.stack([x, y], axis=-1)

    # 長さの変換
    def px_to_pct_h(self, d_px):
        """px 単位の長さを画像高に対する百分率へ変換する。水平方向の長さも同じ基準を使う。"""
        return np.asarray(d_px, dtype=np.float64) / self.height_px * 100.0

    def pct_h_to_px(self, d_pct):
        return np.asarray(d_pct, dtype=np.float64) / 100.0 * self.height_px

    def H_to_pct_h(self, d_H):
        return np.asarray(d_H, dtype=np.float64) / self.frame_h * 100.0

    def pct_h_to_H(self, d_pct):
        return np.asarray(d_pct, dtype=np.float64) / 100.0 * self.frame_h

    def m_to_pct_h(self, d_m):
        return self.H_to_pct_h(np.asarray(d_m, dtype=np.float64) / self.H)

    def pct_h_to_m(self, d_pct):
        return self.pct_h_to_H(d_pct) * self.H

    def px_to_H_len(self, d_px):
        return np.asarray(d_px, dtype=np.float64) * self.H_per_px

    def H_to_px_len(self, d_H):
        return np.asarray(d_H, dtype=np.float64) * self.px_per_H

    # 角度の変換
    @staticmethod
    def px_dir_to_deg(dx_px, dy_px):
        """画素座標のベクトルの向きを X-Z 平面上の角度として返す。
        0 度は右向きの +X、+90 度は上向きの +Z、-90 度は下向き。画素座標の y は下向き。"""
        return np.degrees(np.arctan2(-np.asarray(dy_px, dtype=np.float64),
                                     np.asarray(dx_px, dtype=np.float64)))

    # CAM_print の設定
    def cam_print(self, res_x=None, distance_m=None, clip_m=None):
        """判定用カメラの数値（仕様第 4 節）。単位はメートル。

        正投影で +Y 方向を向き、[x_left, x_right] × [z_bottom, z_top] を画面に収める。
        Blender では rotation_euler = (pi/2, 0, 0) XYZ とし、画面の右が +X、上が +Z、
        視線方向が +Y となる。sensor_fit が AUTO で res_x > res_y の場合、ortho_scale は
        視野の幅を表す。

        res_x は描画幅（px）。既定値は原画の幅。res_y は round() で求める。
        res_x が width_px と異なる場合、縦横比の誤差は 1/res_y 未満であり、
        戻り値の辞書には実際に含まれる Z 範囲を z_range_covered_m として記録する。
        """
        res_x = self.width_px if res_x is None else int(res_x)
        res_y = int(round(res_x * self.height_px / self.width_px))
        if distance_m is None:
            try:
                distance_m = float(paths.param("cam_print_distance_m"))
            except Exception:
                distance_m = 200.0
        if clip_m is None:
            try:
                clip_m = [float(v) for v in paths.param("cam_print_clip_m")]
            except Exception:
                clip_m = [0.1, 1000.0]
        H = self.H
        cx = 0.5 * (self.x_left + self.x_right) * H
        cz = 0.5 * (self.z_top + self.z_bottom) * H
        ortho_scale = self.frame_w * H
        half_z = 0.5 * ortho_scale * res_y / res_x
        return {
            "name": "CAM_print",
            "type": "ORTHO",
            "ortho_scale": ortho_scale,
            "sensor_fit": "AUTO",
            "location": (cx, -float(distance_m), cz),
            "rotation_euler_xyz": (math.pi / 2.0, 0.0, 0.0),
            "clip_start": clip_m[0],
            "clip_end": clip_m[1],
            "resolution_x": res_x,
            "resolution_y": res_y,
            "pixel_aspect": 1.0,
            "x_range_m": (self.x_left * H, self.x_right * H),
            "z_range_m": (self.z_bottom * H, self.z_top * H),
            "z_range_covered_m": (cz - half_z, cz + half_z),
            "px_per_m": res_x / ortho_scale,
        }

    def make_cam_print(self, scene=None, res_x=None, name="CAM_print", make_active=True):
        """Blender 内の CAM_print カメラを作成または更新し、scene の描画解像度を設定する。カメラオブジェクトを返す。bpy が必要。"""
        import bpy
        scene = scene or bpy.context.scene
        spec = self.cam_print(res_x=res_x)
        cam_data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = spec["ortho_scale"]
        cam_data.sensor_fit = "AUTO"
        cam_data.shift_x = 0.0
        cam_data.shift_y = 0.0
        cam_data.clip_start = spec["clip_start"]
        cam_data.clip_end = spec["clip_end"]
        obj = bpy.data.objects.get(name)
        if obj is None:
            obj = bpy.data.objects.new(name, cam_data)
        else:
            obj.data = cam_data
        if obj.name not in scene.collection.all_objects:
            scene.collection.objects.link(obj)
        obj.rotation_mode = "XYZ"
        obj.location = spec["location"]
        obj.rotation_euler = spec["rotation_euler_xyz"]
        obj.scale = (1.0, 1.0, 1.0)
        scene.render.resolution_x = spec["resolution_x"]
        scene.render.resolution_y = spec["resolution_y"]
        scene.render.resolution_percentage = 100
        scene.render.pixel_aspect_x = 1.0
        scene.render.pixel_aspect_y = 1.0
        if make_active:
            scene.camera = obj
        return obj


# 仕様第 5 節の基準点を、左端と上端からの画像比率で表す。
SPEC_LANDMARKS_PCT = {
    "S1_crest": (38.2, 8.7),
    "S2_inner_arc_deepest": (39.5, 46.3),
    "S6_claw_rightmost": (59.2, 33.0),
}
SPEC_TROUGH_TOP_PCT = 74.7

_default = None


def get_frame(reload=False):
    """params.json から作った Frame を返す。結果をキャッシュする。"""
    global _default
    if _default is None or reload:
        if reload:
            paths.clear_cache()
        _default = Frame.from_params()
    return _default
