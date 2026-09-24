"""巻込みの空間を保ちながら、波の背面と峰方向をふくらませる造形試作。

流体の圧力や体積保存を解いたものではない。参照模型と複数視点で
比較するためのパラメトリックな水面である。
"""

import numpy as np

from gwave.localized_sweep import LocalizedSweep, SweepConfig, _smooth


class VolumetricSweep(LocalizedSweep):
    """局所的な高峰と、前方へ回り込む左右の肩を作る。"""

    def __init__(self, motion=None, config=None, fullness=.22, wrap=.28):
        super().__init__(motion=motion, config=config or SweepConfig(
            near_extent_H=1.05, far_extent_H=1.40,
            near_height_power=1.65, far_height_power=1.30,
            near_back_shift_H=1.20, far_back_shift_H=1.20,
        ))
        self.fullness = float(fullness)
        self.wrap = float(wrap)

    def sample(self, frame, H=11.0):
        p = super().sample(frame, H=1.0)
        tau = self.motion.tau_of_frame(min(frame, self.final_frame))
        gain = float(_smooth((tau-.22)/.65))
        u = np.arange(self.n_u)
        # 断面の背面だけを後ろへふくらませる。巻込み内壁の輪郭を押しつぶさない。
        back = (1-_smooth((u-(self.motion.i_c-20))/45))[None, :]
        p[:, :, 0] -= self.fullness * gain * back * np.sin(np.pi*np.clip(p[:, :, 2], 0, 1))
        # 峰方向の断面を平行に並べるだけでなく、両肩を少し前方へ向ける。
        # 同じ行の XZ 断面には線形回転を使い、局所的な押込みを避ける。
        angle = -self.wrap*self.v*gain
        pivot = self.motion.x_c_of_frame(min(frame, self.final_frame))-.20
        dx = p[:, :, 0]-pivot
        p[:, :, 0] = pivot + dx*np.cos(angle)[:, None]
        p[:, :, 1] += dx*np.sin(angle)[:, None]
        return p*float(H)

    def metadata(self):
        data = super().metadata()
        data.update({"description": "背面のふくらみと回り込む肩を持つ巻く波の造形試作",
                     "fullness_H": self.fullness, "wrap_radians": self.wrap})
        return data
