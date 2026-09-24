"""局所的な北斎型の大波を、前進・倒れ込み・後続波へつなぐ形状試作。

既存の LocalizedSweep を受け取り、固定トポロジーのまま時間を再配分する。
高峰の形が読める区間にも前進を続け、後半は前傾と前側の下降を組み合わせる。
最後に低い進行波へつなぐ。既定の確認区間は30fpsで450フレームであり、
確認区間を越えて評価しても最後の姿勢には固定しない。

美術的な座標変換による運動であり、流体方程式、体積保存、砕波時の衝突、
飛沫の生成を解いた物理シミュレーションではない。基になる掃引の形状品質や
非隣接面の衝突検査を、このモジュールだけで保証することもできない。
"""

from dataclasses import asdict, dataclass

import numpy as np

from gwave.localized_sweep import LocalizedSweep


def _smooth(value):
    x = np.clip(value, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


@dataclass(frozen=True)
class SequenceConfig:
    """時間配分と H 単位の移動量。物理的な波速を同定した数値ではない。"""

    fps: int = 30
    formation_end: int = 180
    recognition_end: int = 240
    collapse_end: int = 345
    end_frame: int = 450
    start_offset_H: float = -1.25
    speed_H_per_second: float = 0.16
    lean_max: float = 0.95
    residual_height_gain: float = 0.28
    front_drop_strength: float = 1.8
    front_drop_start_H: float = 0.0
    front_drop_softness_H: float = 0.12
    recognition_lean: float = 0.025
    recognition_period_seconds: float = 1.7
    follow_start: int = 285
    follow_full: int = 390
    follow_amplitude_H: float = 0.10
    follow_wavelength_H: float = 1.15
    follow_speed_H_per_second: float = 0.24
    follow_offset_H: float = -1.35
    follow_width_H: float = 2.8
    follow_cross_width_H: float = 1.15

    def __post_init__(self):
        if not np.isfinite(np.asarray(list(asdict(self).values()), dtype=float)).all():
            raise ValueError("連続運動の設定は有限値で指定してください")
        if not (self.fps > 0 and 1 < self.formation_end < self.recognition_end
                < self.collapse_end < self.end_frame):
            raise ValueError("形成・高峰確認・下降・終了のフレームを昇順に指定してください")
        if not (self.recognition_end <= self.follow_start < self.follow_full <= self.end_frame):
            raise ValueError("後続波の開始と全振幅のフレームを下降区間以後に指定してください")
        if self.speed_H_per_second <= 0.0 or self.follow_speed_H_per_second <= 0.0:
            raise ValueError("最後にも波を進めるため、移動速度は正にしてください")
        if not 0.0 < self.residual_height_gain <= 1.0:
            raise ValueError("残る高さの倍率は0より大きく1以下にしてください")
        if min(self.front_drop_softness_H, self.recognition_period_seconds,
               self.follow_wavelength_H, self.follow_width_H, self.follow_cross_width_H) <= 0.0:
            raise ValueError("長さと周期は正にしてください")
        if min(self.lean_max, self.front_drop_strength, self.follow_amplitude_H) < 0.0:
            raise ValueError("前傾・下降・後続波の振幅は0以上にしてください")


@dataclass(frozen=True)
class BreakingConfig:
    """参照模型の唇を先に巻き下げる比較用の設定。旋心は高峰からの相対位置。"""

    start_frame: int = 240
    curl_end_frame: int = 320
    settle_start_frame: int = 310
    settle_end_frame: int = 405
    pivot_x_H: float = 0.32
    pivot_z_H: float = 0.35
    angle_degrees: float = 70.0
    front_start_H: float = 0.20
    front_full_H: float = 0.72
    height_start_H: float = 0.05
    height_full_H: float = 0.22
    body_lean: float = 0.10
    settle_lean: float = 0.32
    settle_height_gain: float = 0.20
    max_step_radians: float = 0.055

    def __post_init__(self):
        if not np.isfinite(np.asarray(list(asdict(self).values()), dtype=float)).all():
            raise ValueError("巻き下げ設定は有限値で指定してください")
        if not (1 < self.start_frame < self.curl_end_frame <= self.settle_end_frame
                and self.start_frame <= self.settle_start_frame < self.settle_end_frame):
            raise ValueError("巻き下げと低波への移行のフレームを確認してください")
        if not (self.front_start_H < self.front_full_H and self.height_start_H < self.height_full_H):
            raise ValueError("速度場の立上り区間は正の幅にしてください")
        if not (0.0 <= self.angle_degrees < 150.0 and 0.0 < self.max_step_radians <= 0.1
                and 0.0 < self.settle_height_gain <= 1.0):
            raise ValueError("回転角、積分刻み、高さ倍率の範囲を確認してください")


class TravelingSequence:
    """sample(frame, H) で元の掃引と同じ形の頂点配列を返す。

    base_sweep に sample、faces、motion、n_u、n_v、hero_row、y_H があれば、
    形状を厚くした別の掃引も差し替えられる。物質点の番号は変更しない。
    reference_frame は高峰を観察する時刻であり、final_frame は動画の推奨終了時刻。
    final_frame を波の静止開始や泡の基準形状として使わないこと。
    """

    def __init__(self, base_sweep=None, config=None):
        self.base_sweep = base_sweep if base_sweep is not None else LocalizedSweep()
        if config is None:
            config = SequenceConfig()
        elif isinstance(config, dict):
            config = SequenceConfig(**config)
        if not isinstance(config, SequenceConfig):
            raise TypeError("config は SequenceConfig または設定辞書で指定してください")
        self.config = config
        self.motion = self.base_sweep.motion
        self.n_u = int(self.base_sweep.n_u)
        self.n_v = int(self.base_sweep.n_v)
        self.hero_row = int(self.base_sweep.hero_row)
        self.y_H = np.asarray(self.base_sweep.y_H, dtype=float).copy()
        self.u = np.asarray(self.base_sweep.u, dtype=float).copy()
        self.follow_center_y_H = float(self.y_H[self.hero_row])
        self.follow_near_extent_H = min(float(self.follow_center_y_H - self.y_H.min()), config.follow_cross_width_H)
        self.follow_far_extent_H = min(float(self.y_H.max() - self.follow_center_y_H), config.follow_cross_width_H)
        if min(self.follow_near_extent_H, self.follow_far_extent_H) <= 0.0:
            raise ValueError("高峰の両側に幅を持つ掃引を指定してください")
        self.fps = int(config.fps)
        self.final_frame = int(config.end_frame)
        self.reference_frame = (config.formation_end + config.recognition_end) // 2
        self.base_final_frame = int(self.motion.n_frames)

    def state(self, frame):
        """形状生成、泡、カメラ追従が共有する時間状態。終端では固定しない。"""
        frame = float(frame)
        if not np.isfinite(frame):
            raise ValueError("frame は有限値で指定してください")
        frame = max(frame, 1.0)
        c = self.config
        seconds = (frame - 1.0) / c.fps
        formation = float(_smooth((frame - 1.0) / (c.formation_end - 1.0)))
        base_frame = 1.0 + formation * (self.base_final_frame - 1.0)
        collapse = float(_smooth((frame - c.recognition_end) / (c.collapse_end - c.recognition_end)))
        recognition = float(np.clip((frame - c.formation_end) / (c.recognition_end - c.formation_end), 0.0, 1.0))
        # 高峰の確認中もごく小さい前傾変化を与える。両端で値と速度を0にする。
        rock_envelope = np.sin(np.pi * recognition) ** 2
        rock_time = (frame - c.formation_end) / c.fps
        rock = c.recognition_lean * rock_envelope * np.sin(2.0 * np.pi * rock_time / c.recognition_period_seconds)
        follow = float(_smooth((frame - c.follow_start) / (c.follow_full - c.follow_start)))
        center_x_H = self.motion.x_c_final + c.start_offset_H + c.speed_H_per_second * seconds
        phase = "形成" if frame < c.formation_end else "高峰を見せる"
        if frame > c.recognition_end:
            phase = "前へ倒れ込む" if frame < c.collapse_end else "後続の低い波"
        return {
            "frame": frame,
            "seconds": seconds,
            "phase": phase,
            "base_frame": base_frame,
            "center_x_H": float(center_x_H),
            "base_center_x_H": float(self.motion.x_c_of_frame(base_frame)),
            "collapse": collapse,
            "lean": float(c.lean_max * collapse + rock),
            "height_gain": float(1.0 + collapse * (c.residual_height_gain - 1.0)),
            "front_drop": float(c.front_drop_strength * collapse),
            "follow_gain": follow,
            "foam_growth_frame": base_frame,
            "foam_attached_gain": float(1.0 - 0.9 * _smooth((collapse - 0.25) / 0.75)),
            "foam_release_gain": float(_smooth((collapse - 0.10) / 0.35) * (1.0 - _smooth((collapse - 0.72) / 0.28))),
        }

    def follow_height(self, world_x, world_y, frame, H=11.0):
        """後続する低波の水位。別の海面にも同じ場を適用できる。入力と出力はm。"""
        H = float(H)
        if not np.isfinite(H) or H <= 0.0:
            raise ValueError("H は正の有限値で指定してください")
        st, c = self.state(frame), self.config
        x, y = np.asarray(world_x, dtype=float) / H, np.asarray(world_y, dtype=float) / H
        center = st["center_x_H"] + c.follow_offset_H
        envelope = np.exp(-0.5 * ((x - center) / c.follow_width_H) ** 2)
        # 元の平らな境界で後続波を厳密に0に戻す。端の退化した直線に非線形の
        # 水位を与えると、離散線分だけが交差するため、その縁は持ち上げない。
        dy = y - self.follow_center_y_H
        extent = np.where(dy < 0.0, self.follow_near_extent_H, self.follow_far_extent_H)
        cross_envelope = np.maximum(0.0, 1.0 - (dy / extent) ** 2) ** 2
        envelope *= cross_envelope
        k = 2.0 * np.pi / c.follow_wavelength_H
        phase = k * (x - c.follow_speed_H_per_second * st["seconds"])
        oscillation = 0.78 * np.sin(phase) + 0.22 * np.sin(1.7 * phase + 0.4 * y)
        return H * c.follow_amplitude_H * st["follow_gain"] * envelope * oscillation

    def deform_points(self, points, frame, H=11.0, anchor_x_H=0.0, waterline_m=0.0,
                      form_from_reference=True, include_follow=True):
        """任意の Z-up 参照姿勢の点群 (..., 3) をm単位で変形する。

        XZ 変換は、せん断、正の高さ倍率、Xに依存する正の下降倍率、
        進行波の水位加算の順に適用する。これらは各時刻で可逆なので、
        連続曲面としては新しい自己交差を作らない。有限サイズの三角面への
        再近似と元形状の交差については、別途確認が必要である。

        anchor_x_H には参照姿勢の高峰のX座標をHで割った値を渡す。
        波が進む方向は +X である。逆向きの参照モデルは呼出し側で向きをそろえる。
        form_from_reference=True は静的な参照メッシュ向けで、初期の高さを
        正の倍率で縮めてから持ち上げる。巻いた形を平面へ展開する処理ではない。
        既に形成中の掃引を渡すときは False とし、形成を二重に適用しない。
        """
        H = float(H)
        if not np.isfinite(H) or H <= 0.0:
            raise ValueError("H は正の有限値で指定してください")
        if not np.isfinite([anchor_x_H, waterline_m]).all():
            raise ValueError("基準点と水位は有限値で指定してください")
        st, c = self.state(frame), self.config
        vertices = np.asarray(points, dtype=float).copy()
        if vertices.ndim < 2 or vertices.shape[-1] != 3 or not np.isfinite(vertices).all():
            raise ValueError("点群は有限値の (..., 3) 配列で指定してください")
        x = vertices[..., 0] / H - float(anchor_x_H)
        z = (vertices[..., 2] - waterline_m) / H
        if form_from_reference:
            final_height = float(self.motion.height_of_frame(self.base_final_frame))
            z = z * (self.motion.height_of_frame(st["base_frame"]) / final_height)
        x = x + st["lean"] * z
        front = c.front_drop_softness_H * np.logaddexp(0.0, (x - c.front_drop_start_H) / c.front_drop_softness_H)
        z = z * st["height_gain"] * np.exp(-st["front_drop"] * front)
        vertices[..., 0] = H * (x + st["center_x_H"])
        vertices[..., 2] = waterline_m + H * z
        if include_follow:
            vertices[..., 2] += self.follow_height(vertices[..., 0], vertices[..., 1], frame, H)
        return vertices

    def sample(self, frame, H=11.0):
        """前進する同一物質点群を (n_v, n_u, 3) のワールド座標mで返す。"""
        st = self.state(frame)
        vertices = self.base_sweep.sample(st["base_frame"], H)
        if np.asarray(vertices).shape != (self.n_v, self.n_u, 3):
            raise ValueError("基になる掃引の頂点配列が形状契約と一致しません")
        return self.deform_points(vertices, frame, H=H, anchor_x_H=st["base_center_x_H"],
                                  form_from_reference=False)

    def deform_breaking_points(self, points, frame, H=11.0, anchor_x_H=0.0,
                               waterline_m=0.0, form_from_reference=True,
                               include_follow=True, breaking_config=None):
        """参照姿勢から、背の高さを残しつつ前側の唇を巻き下げる独立した比較案。

        sample/deform_points の従来案は変更しない。240～320フレームで前側を
        内口の旋心へ回し、310～405フレームで初めて背を含む全体を低波へ移す。
        初期姿勢は Z-up、進行方向は +X、座標はm。anchor_x_H は参照高峰のX/H。

        頂点ごとに回転後の点を線形混合すると反転が起き得るため、現在位置に
        依存する滑らかな回転速度場を RK4 で積分する。連続速度場の流れは
        一対一の変形だが、有限刻みと有限三角面の誤差、元メッシュの交差は
        別途検査を要する。着水衝突と体積保存を解いた物理砕波ではない。
        """
        cfg = breaking_config if breaking_config is not None else BreakingConfig()
        if isinstance(cfg, dict):
            cfg = BreakingConfig(**cfg)
        if not isinstance(cfg, BreakingConfig):
            raise TypeError("breaking_config は BreakingConfig または設定辞書で指定してください")
        H = float(H)
        if not np.isfinite([H, anchor_x_H, waterline_m]).all() or H <= 0.0:
            raise ValueError("H は正の有限値、基準点と水位は有限値で指定してください")
        vertices = np.asarray(points, dtype=float).copy()
        if vertices.ndim < 2 or vertices.shape[-1] != 3 or not np.isfinite(vertices).all():
            raise ValueError("点群は有限値の (..., 3) 配列で指定してください")
        st = self.state(frame)
        x = vertices[..., 0] / H - float(anchor_x_H)
        z = (vertices[..., 2] - waterline_m) / H
        if form_from_reference:
            z = z * (self.motion.height_of_frame(st["base_frame"])
                     / self.motion.height_of_frame(self.base_final_frame))
        progress = float(_smooth((st["frame"] - cfg.start_frame) / (cfg.curl_end_frame - cfg.start_frame)))
        settle = float(_smooth((st["frame"] - cfg.settle_start_frame) / (cfg.settle_end_frame - cfg.settle_start_frame)))
        # 背全体の小さい前傾と、口の前側だけの回転を分離する。
        x = x + cfg.body_lean * progress * z
        angle = np.deg2rad(cfg.angle_degrees) * progress

        def velocity(xx, zz):
            front = _smooth((xx - cfg.front_start_H) / (cfg.front_full_H - cfg.front_start_H))
            height = _smooth((zz - cfg.height_start_H) / (cfg.height_full_H - cfg.height_start_H))
            weight = front * height
            # +Xへ進む波を、XZ図で時計回りに回す。
            return weight * (zz - cfg.pivot_z_H), -weight * (xx - cfg.pivot_x_H)

        if angle > 0.0:
            steps = max(1, int(np.ceil(angle / cfg.max_step_radians)))
            step = angle / steps
            for _ in range(steps):
                a, b = velocity(x, z)
                c, d = velocity(x + 0.5 * step * a, z + 0.5 * step * b)
                e, f = velocity(x + 0.5 * step * c, z + 0.5 * step * d)
                g, h = velocity(x + step * e, z + step * f)
                x = x + step * (a + 2.0 * c + 2.0 * e + g) / 6.0
                z = z + step * (b + 2.0 * d + 2.0 * f + h) / 6.0
        x = x + cfg.settle_lean * settle * z
        z = z * (1.0 + settle * (cfg.settle_height_gain - 1.0))
        vertices[..., 0] = H * (x + st["center_x_H"])
        vertices[..., 2] = waterline_m + H * z
        if include_follow:
            vertices[..., 2] += self.follow_height(vertices[..., 0], vertices[..., 1], frame, H)
        return vertices

    def row_state(self, frame):
        """既存の泡生成器に渡す発達段階と、新しい下降・移動情報。"""
        st = self.state(frame)
        out = dict(self.base_sweep.row_state(st["base_frame"]))
        out.update(st)
        return out

    def faces(self):
        """基になる掃引と同じ面番号。"""
        return self.base_sweep.faces()

    def landmarks(self, frame, H=11.0):
        """泡の付着位置と、高峰・先端・内弧の実際の移動位置。"""
        vertices = self.sample(frame, H)
        highest = np.argmax(vertices[:, :, 2], axis=1)
        return {
            "crest": vertices[:, self.motion.i_c].copy(),
            "tip": vertices[:, self.motion.i_t].copy(),
            "inner": vertices[:, self.motion.i_d].copy(),
            "armpit": vertices[:, self.motion.i_armpit].copy(),
            "highest": vertices[np.arange(self.n_v), highest].copy(),
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
        """シーンの記録に保存する設定と未検証事項。"""
        return {
            "description": "高峰を保って前進し、前側へ倒れ込んだ後に低い進行波が続く形状試作",
            "limitation": "流体物理、体積保存、実際の着水衝突と飛沫生成は未計算",
            "config": asdict(self.config),
            "n_u": self.n_u,
            "n_v": self.n_v,
            "hero_row": self.hero_row,
            "fps": self.fps,
            "reference_frame": self.reference_frame,
            "final_frame": self.final_frame,
            "after_end": "最終フレーム以後も移動と後続波を継続する。無縫合ループではない",
            "base": self.base_sweep.metadata(),
        }


def sample(frame, H=11.0, base_sweep=None, config=None):
    """単発評価用。反復生成では TravelingSequence を再利用する。"""
    return TravelingSequence(base_sweep=base_sweep, config=config).sample(frame, H)
