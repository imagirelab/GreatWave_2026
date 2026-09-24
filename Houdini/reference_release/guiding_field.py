"""有限時間の主循環速度場。Houdini に依存せず NumPy で評価する。

Y は鉛直上向き、X は前方、Z は幅方向。座標は m、時刻は開始後の s、
速度は m/s、流れ関数の強度は m²/s。形を生成する流体計算ではない。
ψ=-A exp(-dx²/sx²-dy²/sy²) Wx Wy Wz w(t) から
u=∂ψ/∂y、v=-∂ψ/∂x、wz=0 を求める。空間窓は全て ψ の中にある。
低い水体がC形に育つか、制御後に着水するかは、別のFLIP試験を要する。

G=exp(-dx²/sx²-dy²/sy²)、T=w(t) とすると、明示式は次のとおり。
u=A T G Wz Wx (2dy Wy/sy² - Wy')
v=A T G Wz Wy (Wx' - 2dx Wx/sx²)
W=S((q-a)/(b-a)) S((d-q)/(d-c))、S(r)=6r⁵-15r⁴+10r³。
Sの引数は0～1へ制限し、範囲外の導関数は0とする。
Wxなどの窓を速度の算出後に掛ける操作は、この式とは異なる。

既定値の上層速度は初期水位より高い位置の目標値であり、流体の実測ではない。
幅方向は強度だけが非対称で、Z方向への流入・集束速度は含まない。
時間窓が0のとき、適用側も速度緩和を停止する。0の目標速度への緩和を
続けると、自由発展ではなく流体を止める制御になってしまう。
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np


def _step(q):
    """両端で一階・二階微分が0の五次補間と、その引数による一階微分。"""
    r = np.clip(q, 0.0, 1.0)
    return r * r * r * (10.0 + r * (-15.0 + 6.0 * r)), 30.0 * r * r * (1.0 - r) ** 2


def _window(x, cuts):
    """外端a,dで0、内端b,cの間で1となるC²窓と dW/dx。b=cも可。"""
    a, b, c, d = cuts
    left, dl = _step((x - a) / (b - a))
    right, dr = _step((d - x) / (d - c))
    return left * right, dl * right / (b - a) - left * dr / (d - c)


@dataclass(frozen=True)
class GuidingConfig:
    """主循環は一つだけ。参考高さと水位は連携先へ渡す条件情報。"""

    domain_x_m: tuple = (-12.0, 12.0)
    domain_y_m: tuple = (0.0, 6.0)
    domain_z_m: tuple = (-4.0, 4.0)
    water_level_m: float = 1.4
    reference_height_m: float = 3.0
    center_x_m: float = 0.0
    center_y_m: float = 2.0
    width_x_m: float = 2.4
    width_y_m: float = 1.2
    strength_m2_s: float = 5.0
    window_x_m: tuple = (-5.0, -3.0, 3.0, 5.0)
    window_y_m: tuple = (0.0, 1.2, 4.5, 5.8)
    window_z_m: tuple = (-2.6, 0.2, 0.2, 3.6)
    rise_start_s: float = 0.0
    rise_end_s: float = 0.25
    fall_start_s: float = 1.25
    fall_end_s: float = 1.75

    def __post_init__(self):
        for value in asdict(self).values():
            if not np.isfinite(np.asarray(value, dtype=float)).all():
                raise ValueError("条件には有限値を指定してください")
        for axis in "xyz":
            domain = getattr(self, f"domain_{axis}_m")
            cuts = getattr(self, f"window_{axis}_m")
            if len(domain) != 2 or len(cuts) != 4:
                raise ValueError("領域は2値、窓は4値で指定してください")
            a, b, c, d = cuts
            if not domain[0] <= a < b <= c < d <= domain[1]:
                raise ValueError("窓は領域内で a<b<=c<d となるよう指定してください")
        if not self.domain_y_m[0] < self.water_level_m < self.domain_y_m[1]:
            raise ValueError("水位は領域の底と上端の間に指定してください")
        if min(self.width_x_m, self.width_y_m, self.reference_height_m) <= 0.0:
            raise ValueError("幅と参考高さは正にしてください")
        if self.strength_m2_s < 0.0:
            raise ValueError("時計回りの循環には0以上の強度を指定してください")
        if not self.rise_start_s < self.rise_end_s <= self.fall_start_s < self.fall_end_s:
            raise ValueError("時間窓は立上げ、保持、終了の順に指定してください")


class GuidingField:
    """sample(points, time_s) で (..., 3) の目標速度を返す。入力は変更しない。"""

    def __init__(self, config=None):
        if config is None:
            config = GuidingConfig()
        elif isinstance(config, dict):
            config = GuidingConfig(**config.get("parameters", config))
        if not isinstance(config, GuidingConfig):
            raise TypeError("config は GuidingConfig または条件辞書で指定してください")
        self.config = config

    @classmethod
    def from_json(cls, path):
        """日本語の説明と parameters を持つ条件JSONから作成する。"""
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def temporal_weight(self, time_s):
        """0～0.25秒で立上がり、1.25～1.75秒で厳密に0へ戻る既定窓。"""
        t = float(time_s)
        if not np.isfinite(t):
            raise ValueError("時刻は有限値で指定してください")
        c = self.config
        rise, _ = _step((t - c.rise_start_s) / (c.rise_end_s - c.rise_start_s))
        fall, _ = _step((t - c.fall_start_s) / (c.fall_end_s - c.fall_start_s))
        return float(rise * (1.0 - fall))

    def evaluate(self, points, time_s):
        """(速度配列, ψ配列) を返す。主循環の速度を成分別に切り詰めない。"""
        p = np.asarray(points, dtype=float)
        if p.ndim < 1 or p.shape[-1] != 3 or not np.isfinite(p).all():
            raise ValueError("点は有限値の (..., 3) 配列で指定してください")
        c = self.config
        wx, dxw = _window(p[..., 0], c.window_x_m)
        wy, dyw = _window(p[..., 1], c.window_y_m)
        wz, _ = _window(p[..., 2], c.window_z_m)
        dx, dy = p[..., 0] - c.center_x_m, p[..., 1] - c.center_y_m
        gaussian = np.exp(-(dx / c.width_x_m) ** 2 - (dy / c.width_y_m) ** 2)
        common = c.strength_m2_s * self.temporal_weight(time_s) * gaussian * wz
        velocity = np.zeros_like(p)
        velocity[..., 0] = common * wx * (2.0 * dy / c.width_y_m ** 2 * wy - dyw)
        velocity[..., 1] = common * wy * (dxw - 2.0 * dx / c.width_x_m ** 2 * wx)
        potential = -common * wx * wy
        return velocity, potential

    def sample(self, points, time_s):
        """目標速度のみを返す。FLIPの現在速度へ直接代入する処理は含めない。"""
        return self.evaluate(points, time_s)[0]

    def vex_source(self):
        """同じ係数・明示微分を持つVEX関数。戻り値は (u,v,wz,ψ)。

        gw_field(@P, 経過秒) を評価し、xyzを目標速度として使用する。
        Houdini内でのコンパイル・適用は未検証。位置Pの書換えは含まない。
        """
        c = self.config
        number = lambda x: format(float(x), ".17g")
        cuts = lambda values: "set(" + ", ".join(number(v) for v in values) + ")"
        return f'''// C²窓を流れ関数へ含めた単一循環場。単位は m、s。
float gw_step(float q) {{
    float r = clamp(q, 0.0, 1.0);
    return r*r*r*(10.0+r*(-15.0+6.0*r));
}}
float gw_dstep(float q) {{
    float r = clamp(q, 0.0, 1.0);
    return 30.0*r*r*(1.0-r)*(1.0-r);
}}
vector2 gw_window(float x; vector4 cuts) {{
    float a=(x-cuts.x)/(cuts.y-cuts.x);
    float b=(cuts.w-x)/(cuts.w-cuts.z);
    float l=gw_step(a), r=gw_step(b);
    return set(l*r, gw_dstep(a)*r/(cuts.y-cuts.x)-l*gw_dstep(b)/(cuts.w-cuts.z));
}}
vector4 gw_field(vector pos; float elapsed_s) {{
    vector2 wx=gw_window(pos.x, {cuts(c.window_x_m)});
    vector2 wy=gw_window(pos.y, {cuts(c.window_y_m)});
    vector2 wz=gw_window(pos.z, {cuts(c.window_z_m)});
    float rise=gw_step((elapsed_s-{number(c.rise_start_s)})/{number(c.rise_end_s-c.rise_start_s)});
    float fall=gw_step((elapsed_s-{number(c.fall_start_s)})/{number(c.fall_end_s-c.fall_start_s)});
    float dx=pos.x-{number(c.center_x_m)}, dy=pos.y-{number(c.center_y_m)};
    float sx2={number(c.width_x_m**2)}, sy2={number(c.width_y_m**2)};
    float common={number(c.strength_m2_s)}*rise*(1.0-fall)*exp(-dx*dx/sx2-dy*dy/sy2)*wz.x;
    float u=common*wx.x*(2.0*dy/sy2*wy.x-wy.y);
    float v=common*wy.x*(wx.y-2.0*dx/sx2*wx.x);
    float psi=-common*wx.x*wy.x;
    return set(u, v, 0.0, psi);
}}
'''


def verify_offline():
    """既定値と隣接JSONをNumPyだけで確認する。シミュレーションは実行しない。

    乱数点と窓の接続点、境界、XY格子を調べる。VEXの実行は含まない。
    速度上界は導関数の解析的上界と格子値から求める浮動小数点評価。
    """
    field = GuidingField.from_json(Path(__file__).with_suffix(".json"))
    c = field.config
    if json.dumps(asdict(c), sort_keys=True) != json.dumps(asdict(GuidingConfig()), sort_keys=True):
        raise ValueError("JSONと既定値が異なります。この検証の条件を更新してください")
    rng = np.random.default_rng(20260924)
    lower, upper = [-5.2, -0.1, -2.8], [5.2, 5.9, 3.8]
    points = [rng.uniform(lower, upper, (20000, 3))]
    cuts = (c.window_x_m, c.window_y_m, c.window_z_m)
    for axis, values in enumerate(cuts):
        for value in values:
            p = rng.uniform(lower, upper, (300, 3))
            p[:, axis] = value
            points.append(p)
    points = np.vstack(points)
    velocity = field.sample(points, 0.5)
    differences = []
    for h in (0.002, 0.001, 0.0005):
        divergence = np.zeros(len(points))
        error = 0.0
        for axis in (0, 1):
            offset = np.zeros(3)
            offset[axis] = h
            plus, psi_plus = field.evaluate(points + offset, 0.5)
            minus, psi_minus = field.evaluate(points - offset, 0.5)
            divergence += (plus[:, axis] - minus[:, axis]) / (2.0 * h)
            expected = velocity[:, 0] if axis == 1 else -velocity[:, 1]
            error = max(error, float(np.max(np.abs((psi_plus - psi_minus) / (2.0 * h) - expected))))
        differences.append({"刻み_m": h, "最大発散残差_毎秒": float(np.max(np.abs(divergence))),
                            "流れ関数の差分誤差_m_s": error})
    boundary = []
    for axis, limits in enumerate((c.domain_x_m, c.domain_y_m, c.domain_z_m)):
        for value in limits:
            p = rng.uniform([-12, 0, -4], [12, 6, 4], (2000, 3))
            p[:, axis] = value
            boundary.append(p)
    for axis, values in enumerate(cuts):
        for value in (values[0], values[3]):
            p = rng.uniform([-5, 0, -2.6], [5, 5.8, 3.6], (2000, 3))
            p[:, axis] = value
            boundary.append(p)
    boundary = np.vstack(boundary)
    boundary_v, boundary_psi = field.evaluate(boundary, 0.5)
    boundary_derivative = []
    for axis in range(3):
        offset = np.zeros(3)
        offset[axis] = 0.0001
        delta = field.evaluate(boundary + offset, 0.5)[1] - field.evaluate(boundary - offset, 0.5)[1]
        boundary_derivative.append(float(np.max(np.abs(delta / 0.0002))))

    # Wzと時間窓は0～1なので、最大値1の断面だけで速度上界を評価できる。
    spacing = 0.0025
    xs, ys = np.linspace(-5, 5, 4001), np.linspace(0, 5.8, 2321)
    maximum, crest_maximum, maximum_position = 0.0, 0.0, None
    for index in range(0, len(ys), 64):
        xx, yy = np.meshgrid(xs, ys[index:index + 64])
        p = np.stack((xx, yy, np.full_like(xx, 0.2)), axis=-1)
        speed = np.linalg.norm(field.sample(p, 0.5), axis=-1)
        at = np.unravel_index(speed.argmax(), speed.shape)
        if speed[at] > maximum:
            maximum, maximum_position = float(speed[at]), p[at].tolist()
        crest_maximum = max(crest_maximum, float(np.max(np.where(yy >= 2.0, speed, 0.0))))

    # sup|G'|=sqrt(2/e)/s、sup|G''|=2/s²。
    # 五次窓の各ランプではsup|S'|=1.875、sup|S''|=10sqrt(3)/3。
    # X・Yの窓のランプは重ならない。速度ヤコビ行列のFrobeniusノルムを上から抑える。
    bounds = []
    for width, values in ((c.width_x_m, c.window_x_m), (c.width_y_m, c.window_y_m)):
        ramp = min(values[1] - values[0], values[3] - values[2])
        g1, g2 = np.sqrt(2.0 / np.e) / width, 2.0 / width ** 2
        w1, w2 = 1.875 / ramp, (10.0 * np.sqrt(3.0) / 3.0) / ramp ** 2
        bounds.append((g1 + w1, g2 + 2.0 * g1 * w1 + w2))
    (fx1, fx2), (gy1, gy2) = bounds
    lipschitz = c.strength_m2_s * np.sqrt(2.0 * (fx1 * gy1) ** 2 + fx2 ** 2 + gy2 ** 2)
    upper_speed = maximum + lipschitz * spacing / np.sqrt(2.0)
    probes = np.array([[-1.7, 2.0, 0.2], [0.0, 2.85, 0.2], [1.7, 2.0, 0.2],
                       [0.0, 1.4, 0.2], [0.0, 2.85, -1.3], [0.0, 2.85, 1.7]])
    probe_velocity = field.sample(probes, 0.5)
    weights = {str(t): field.temporal_weight(t) for t in (-0.1, 0, 0.125, 0.25, 1.25, 1.5, 1.75, 2)}
    assert differences[-1]["最大発散残差_毎秒"] < 0.00001
    assert differences[-1]["流れ関数の差分誤差_m_s"] < 0.00001
    assert not np.any(boundary_v) and not np.any(boundary_psi)
    assert probe_velocity[0, 1] > 0 and probe_velocity[1, 0] > 0 and probe_velocity[2, 1] < 0
    assert 3.0 <= crest_maximum <= 5.0 and upper_speed < 5.0
    assert list(weights.values()) == [0.0, 0.0, 0.5, 1.0, 1.0, 0.5, 0.0, 0.0]
    return {"範囲": "既定解析場のオフライン検証。FLIP形成とVEX実行は未検証。",
            "差分評価点数": len(points), "中央差分": differences,
            "境界評価点数": len(boundary), "境界最大速度_m_s": float(np.max(np.abs(boundary_v))),
            "境界最大流れ関数_m2_s": float(np.max(np.abs(boundary_psi))),
            "境界の流れ関数の差分勾配_m_s": boundary_derivative,
            "時間窓": weights, "格子点数": len(xs) * len(ys), "格子間隔_m": spacing,
            "格子最大速度_m_s": maximum, "格子最大速度の位置_m": maximum_position,
            "Yが2m以上の格子最大速度_m_s": crest_maximum,
            "XY速度のLipschitz上界_毎秒": float(lipschitz),
            "格子間を含む保守的速度上界_m_s": float(upper_speed),
            "確認点": [{"位置_m": p.tolist(), "速度_m_s": v.tolist()} for p, v in zip(probes, probe_velocity)]}


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="NumPyだけで解析場を確認する。Houdiniは起動しない。")
    parser.add_argument("--verify", action="store_true", help="既定条件をオフラインで確認する")
    args = parser.parse_args()
    if args.verify:
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(verify_offline(), ensure_ascii=False, indent=2))
    else:
        parser.print_help()
