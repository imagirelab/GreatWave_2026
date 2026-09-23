"""原画由来の断面を、局所的な高峰を持つ非対称の波面へ展開する。

中央の物質点列には既存の最終断面を使う。峰方向には高さ、発達段階、
後退量を連続的に変え、同じ断面を幅方向へ押し出した梁状の波頭を避ける。
左右の肩を中央断面の投影内へ押し込む処理は行わない。

これは美術的に制御した固定トポロジーの形状モデルである。
流体方程式、体積保存、飛沫の物理を解くシミュレーションではない。
既存の生成器、設定、点キャッシュには変更を加えない。
"""

from dataclasses import asdict, dataclass
from typing import Optional

import numpy as np

from gwave.profile_motion import WaveMotion, grid_faces


def _smooth(value):
    x = np.clip(value, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


@dataclass(frozen=True)
class SweepConfig:
    """H 単位の造形用初期設定。スキャンへの寸法フィット値ではない。"""

    n_v: int = 121
    peak_y_H: float = 0.0
    near_extent_H: float = 0.75
    far_extent_H: float = 1.25
    near_height_power: float = 2.2
    far_height_power: float = 1.4
    near_phase_reduction: float = 0.52
    far_phase_reduction: float = 0.44
    phase_height_start: float = 0.48
    near_back_shift_H: float = 1.60
    far_back_shift_H: float = 1.40
    height_back_shift_power: float = 0.65
    back_shift_floor_fade: float = 0.35
    near_x_scale_end: float = 0.84
    far_x_scale_end: float = 0.76

    def __post_init__(self):
        if self.n_v < 5 or self.n_v % 2 != 1:
            raise ValueError("n_v は5以上の奇数で指定してください")
        values = np.asarray([v for k, v in asdict(self).items() if k != "n_v"], dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("掃引設定は有限値で指定してください")
        if min(self.near_extent_H, self.far_extent_H) <= 0.0:
            raise ValueError("左右の幅は正の値で指定してください")
        if min(self.near_height_power, self.far_height_power) <= 1.0:
            raise ValueError("水面との接続勾配を0にするため高さの指数は1より大きくしてください")
        if not (0.0 <= self.near_phase_reduction < 1.0 and 0.0 <= self.far_phase_reduction < 1.0):
            raise ValueError("発達段階の減少量は0以上1未満で指定してください")
        if min(self.near_x_scale_end, self.far_x_scale_end) <= 0.0:
            raise ValueError("断面の水平倍率は正の値で指定してください")
        if min(self.near_back_shift_H, self.far_back_shift_H) < 0.0:
            raise ValueError("肩の後退量は0以上で指定してください")
        if not (0.0 < self.phase_height_start < 1.0 and 0.0 < self.back_shift_floor_fade < 1.0):
            raise ValueError("肩の高さの閾値は0より大きく1未満で指定してください")
        if self.height_back_shift_power <= 0.5:
            raise ValueError("中央で峰線の接線を連続にするため後退量の指数は0.5より大きくしてください")


class LocalizedSweep:
    """WaveMotion を利用する独立した非対称掃引。

    sample() の配列順は (峰方向の行, 断面の物質点, XYZ) である。
    行の負Y側を近側、正Y側を遠側と呼ぶ。カメラを移動しても造形は変えない。
    U は等間隔の弧長ではなく、元の WaveMotion と同じ421個の物質点に対応する。
    """

    def __init__(self, motion: Optional[WaveMotion] = None, config=None):
        self.motion = motion if motion is not None else WaveMotion()
        if config is None:
            config = SweepConfig()
        elif isinstance(config, dict):
            config = SweepConfig(**config)
        if not isinstance(config, SweepConfig):
            raise TypeError("config は SweepConfig または設定辞書で指定してください")
        self.config = config
        self.n_u = int(self.motion.n_u)
        self.n_v = int(config.n_v)
        self.hero_row = self.n_v // 2
        self.final_frame = int(self.motion.n_frames)
        self.hold_end_frame = self.final_frame + int(self.motion.WP.get("hold_frames", 60))
        self.fps = int(self.motion.WP.get("fps", 30))
        self.u = self.motion.S1 / self.motion.S1[-1]
        # 左右で幅を変えても中央に必ず1行を置く。等高の区間は作らない。
        self.v = np.linspace(-1.0, 1.0, self.n_v)
        self.radius = np.abs(self.v)
        near = self.v < 0.0
        extent = np.where(near, config.near_extent_H, config.far_extent_H)
        self.y_H = config.peak_y_H + self.v * extent
        self.height_power = np.where(near, config.near_height_power, config.far_height_power)
        self.height_envelope = np.maximum(0.0, 1.0 - self.radius ** 2) ** self.height_power
        self.phase_reduction = np.where(near, config.near_phase_reduction, config.far_phase_reduction)
        self.back_shift_H = np.where(near, config.near_back_shift_H, config.far_back_shift_H)
        self.x_scale_end = np.where(near, config.near_x_scale_end, config.far_x_scale_end)
        # 両端で高さを0にした際に折返し線を潰さないよう、端の断面は未巻込みにする。
        onset = float(self.motion.tau_onset())
        end_phases = 1.0 - np.asarray([config.near_phase_reduction, config.far_phase_reduction])
        if np.any(end_phases >= onset):
            raise ValueError("幅方向の端は張出し前の断面にしてください。phase_reduction を増やしてください")

    def row_state(self, frame):
        """行ごとの造形状態。local_tau は各行の物質点変形を表す。"""
        frame = float(np.clip(frame, 1.0, self.final_frame))
        tau = float(self.motion.tau_of_frame(frame))
        # 始点と終点の速度は既存の時間関数が0にする。最終以降も全行を固定する。
        # 高い肩の段階を遅らせると、まだ巻いていない前面が中央の空洞を塞ぐ。
        # 高さが十分低い外縁だけを未巻込みへ戻し、高い部分には同じ C 字断面を使う。
        shoulder = _smooth((self.config.phase_height_start - self.height_envelope)
                           / self.config.phase_height_start)
        local_tau = tau * (1.0 - self.phase_reduction * shoulder)
        development = float(_smooth(tau))
        # 低くした唇が中央断面の空洞内へ垂れ下がらないよう、断面全体を後退させる。
        # 頂点ごとの切断・投影はせず、失った高さと連動した連続移動で処理する。
        # 空洞より下の最外縁では後退量を0に戻し、水面の裾が後ろへ伸び過ぎないようにする。
        retreat = (1.0 - self.height_envelope) ** self.config.height_back_shift_power
        retreat *= _smooth(self.height_envelope / self.config.back_shift_floor_fade)
        back_shift = self.back_shift_H * retreat * development
        x_scale = 1.0 - (1.0 - self.x_scale_end) * self.radius ** 2 * development
        return {
            "frame": frame,
            "center_tau": tau,
            "local_tau": local_tau,
            "y_H": self.y_H.copy(),
            "height_envelope": self.height_envelope.copy(),
            "height_H": self.motion.height_of_frame(frame) * self.height_envelope,
            "back_shift_H": back_shift,
            "x_scale": x_scale,
        }

    def sample(self, frame, H=11.0):
        """ワールド座標の頂点 (n_v, n_u, 3) をメートル単位で返す。

        各行の Y を固定し、XZ 断面の発達だけを変える。正の異方拡大は
        各断面の交差関係を保存する。中央断面への投影や座標の切断は行わない。
        最終フレーム以後は同じ値を返し、既存の停止区間を保持する。
        """
        H = float(H)
        if not np.isfinite(H) or H <= 0.0:
            raise ValueError("H は正の有限値で指定してください")
        state = self.row_state(frame)
        X, Z = self.motion.shape_rows(state["local_tau"])
        row_height = np.max(Z, axis=1)
        if not np.isfinite(row_height).all() or np.any(row_height <= 0.0):
            raise ValueError("各断面の高さは正の有限値でなければなりません")
        Z *= (state["height_H"] / row_height)[:, None]
        X *= state["x_scale"][:, None]
        X += self.motion.x_c_of_frame(state["frame"]) - state["back_shift_H"][:, None]
        # 元の最終断面には手描き由来のごく小さい負の高さがある。
        # それを切断すると面が潰れるため、中央を含め元の対応関係を保つ。
        Y = np.broadcast_to(self.y_H[:, None], X.shape)
        return np.stack([X, Y, Z], axis=-1) * H

    def faces(self):
        """sample().reshape(-1, 3) に対応する外向き四角面の頂点番号。"""
        return grid_faces(self.n_u, self.n_v)

    def landmarks(self, frame, H=11.0):
        """泡の付着やカメラ確認に使う、全行の固定物質点と実際の最高点。"""
        verts = self.sample(frame, H)
        highest = np.argmax(verts[:, :, 2], axis=1)
        return {
            "crest": verts[:, self.motion.i_c].copy(),
            "tip": verts[:, self.motion.i_t].copy(),
            "inner": verts[:, self.motion.i_d].copy(),
            "armpit": verts[:, self.motion.i_armpit].copy(),
            "highest": verts[np.arange(self.n_v), highest].copy(),
            "highest_u_index": highest,
            "hero_row": self.hero_row,
            "material_indices": {
                "crest": int(self.motion.i_c),
                "tip": int(self.motion.i_t),
                "inner": int(self.motion.i_d),
                "armpit": int(self.motion.i_armpit),
            },
        }

    def metadata(self):
        """設定と制約をシーン生成側へ渡す。値の単位は名前に明示する。"""
        return {
            "description": "原画断面から生成した、局所高峰と非対称な肩を持つ形状試作",
            "limitation": "流体シミュレーションではなく、体積保存と実写相当の動きは未検証",
            "config": asdict(self.config),
            "n_u": self.n_u,
            "n_v": self.n_v,
            "hero_row": self.hero_row,
            "fps": self.fps,
            "final_frame": self.final_frame,
            "hold_end_frame": self.hold_end_frame,
            "u_parameter": "最終断面の累積弧長で正規化した固定物質点",
            "coordinates": "sample の H を掛けたワールド座標、上方向 Z、峰方向 Y",
        }


def sample(frame, H=11.0, motion=None, config=None):
    """一回だけ評価する場合の入口。反復再生では LocalizedSweep を再利用する。"""
    return LocalizedSweep(motion=motion, config=config).sample(frame, H)


def frame_vertices(motion, frame, H=11.0, config=None):
    """既存の WaveMotion を明示して (n_v, n_u, 3) を取得する入口。"""
    return LocalizedSweep(motion=motion, config=config).sample(frame, H)
