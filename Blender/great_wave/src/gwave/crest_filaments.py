"""波面から連続する泡の根と、先細りの鉤爪・小滴の造形。

太い根の断面を分け、子の断面と頂点を共有した管網を作る。
葉状の面を重ねる方式ではない。波と泡の物理計算は行わず、
原画と参照映像をもとにした再現可能な造形アニメーションである。
"""

from __future__ import annotations

import inspect
import math
import numpy as np


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def _smooth(v):
    v = np.clip(v, 0.0, 1.0)
    return v*v*(3.0-2.0*v)


def _curve(points, count):
    points = np.asarray(points, dtype=float)
    t = np.linspace(0.0, 1.0, count)[:, None]
    p = ((1-t)**3*points[0]+3*(1-t)**2*t*points[1]
         + 3*(1-t)*t*t*points[2]+t**3*points[3])
    tangent = (3*(1-t)**2*(points[1]-points[0])
               + 6*(1-t)*t*(points[2]-points[1])
               + 3*t*t*(points[3]-points[2]))
    return p, _unit(tangent)


class _BranchMesh:
    """断面の共有により、分岐の根元に隙間を作らない。"""

    def __init__(self):
        self.vertices, self.faces = [], []

    def add(self, points):
        first = len(self.vertices)
        self.vertices.extend(np.asarray(points).tolist())
        return list(range(first, len(self.vertices)))

    def cap(self, ring, end=False):
        center = np.asarray(self.vertices)[ring].mean(axis=0)
        index = self.add([center])[0]
        for i, a in enumerate(ring):
            b = ring[(i+1) % len(ring)]
            self.faces.append((index, b, a) if end else (index, a, b))

    def extend(self, ring, controls, radius_start, radius_end,
               count=11, flatness=.82):
        start = np.asarray(self.vertices)[ring]
        controls = np.asarray(controls, dtype=float).copy()
        controls[0] = start.mean(axis=0)
        points, tangent = _curve(controls, count)
        preferred = np.tile((0.0, 0.0, 1.0), (count, 1))
        lateral = _unit(np.cross(tangent, preferred))
        vertical = _unit(np.cross(lateral, tangent))
        first = start[0]-points[0]
        angle = math.atan2(float(first@vertical[0]), float(first@lateral[0]))
        theta = angle+np.linspace(0, math.tau, len(ring), endpoint=False)
        # 子の開始断面は半円と弦でできる。最初の2区間で円形へ移行する。
        offsets = start-points[0]
        old_ring = ring
        for k in range(1, count):
            t = k/(count-1)
            radius = radius_end+(radius_start-radius_end)*(1-t)**1.08
            radius *= 1.0+.035*math.sin(t*math.tau)
            ellipse = radius*(np.cos(theta)[:, None]*lateral[k]
                               + flatness*np.sin(theta)[:, None]*vertical[k])
            transition = float(_smooth(t/.24))
            verts = points[k]+(1-transition)*offsets+transition*ellipse
            new_ring = self.add(verts)
            for j, a in enumerate(old_ring):
                a_next = old_ring[(j+1) % len(old_ring)]
                b, b_next = new_ring[j], new_ring[(j+1) % len(new_ring)]
                self.faces.extend(((a, b, b_next), (a, b_next, a_next)))
            old_ring = new_ring
        return old_ring

    @staticmethod
    def fork(ring):
        # 親円周の左右半分を使い、二つの子は分割線の両端を共有する。
        n = len(ring)
        shift = n//4
        ordered = ring[shift:]+ring[:shift]
        mid = n//2
        return ordered[:mid+1], ordered[mid:]+ordered[:1]


def _cluster(seed):
    """短い二段分岐と回り込む先端を持つ、一つの連結した管網。"""
    rng = np.random.default_rng(seed)
    mesh = _BranchMesh()
    theta = np.linspace(0, math.tau, 16, endpoint=False)
    ring = mesh.add(np.column_stack((.19*np.cos(theta),
                                    np.full(16, -.19),
                                    .040*np.sin(theta))))
    mesh.cap(ring)
    trunk = mesh.extend(ring, ((0, -.19, 0), (-.025, -.06, .012),
                              (.01, .12, .045), (0, .27, .075)),
                        .19, .105, count=8, flatness=.52)
    roots = mesh.fork(trunk)
    for side, root in zip((-1, 1), roots):
        side_height = rng.uniform(.34, .43)
        parent = mesh.extend(root, ((0, .27, .075), (side*.11, .34, .10),
                                   (side*.22, .42, .12), (side*.26, side_height+.15, .12)),
                             .100, .061, count=7, flatness=.85)
        children = mesh.fork(parent)
        for rank, child in enumerate(children):
            lateral = side*(.46 if rank == 0 else .20)*rng.uniform(.85, 1.15)
            peak = (.85 if rank == 0 else 1.05)*rng.uniform(.88, 1.12)
            endpoint = np.array((lateral+side*rng.uniform(.04, .13),
                                 peak-rng.uniform(.12, .24), -.04-rank*.025))
            # 頂点を越えて少し戻る軌跡により、丸い棒先ではなく鉤になる。
            controls = ((0, 0, 0), (side*.29, peak-.25, .20),
                        (lateral-side*.11, peak+.13, .24), endpoint)
            tip = mesh.extend(child, controls, .060 if rank == 0 else .046,
                              .0045, count=16, flatness=.82)
            mesh.cap(tip, end=True)
    vertices = np.asarray(mesh.vertices, dtype=float)
    # 同形の複製に見えないよう、各群で幅と傾き、奥行きを連続的に変える。
    vertices[:, 0] *= rng.uniform(.80, 1.15)
    vertices[:, 0] += rng.uniform(-.10, .10)*np.maximum(vertices[:, 1], 0)**2
    vertices[:, 2] += rng.uniform(-.08, .08)*vertices[:, 0]*np.maximum(vertices[:, 1], 0)
    return vertices, np.asarray(mesh.faces, dtype=np.int32)


def _drop_template():
    """小さい滴を閉じた低密度メッシュで表す。"""
    vertices = [(0.0, 0.0, -.12)]
    rings = []
    for z, r in ((-.07, .07), (0.0, .10), (.075, .068)):
        ring = []
        for angle in np.linspace(0, math.tau, 8, endpoint=False):
            ring.append(len(vertices))
            vertices.append((r*math.cos(angle), r*math.sin(angle), z))
        rings.append(ring)
    top = len(vertices)
    vertices.append((0.0, 0.0, .18))
    faces = []
    for k in range(8):
        j = (k+1) % 8
        faces.append((0, rings[0][j], rings[0][k]))
        faces.append((top, rings[-1][k], rings[-1][j]))
        for a, b in zip(rings[:-1], rings[1:]):
            faces.extend(((a[k], a[j], b[j]), (a[k], b[j], b[k])))
    return np.asarray(vertices), np.asarray(faces, dtype=np.int32)


class Whitewater:
    """任意の格子波面へ付着する白波と小滴。

    必須の波面インターフェースは sample(frame, H) または sample(frame) のみ。
    返り値は (n_v, n_u, 3)。motion.i_c / i_t がなければ比率で仮配置する。
    sample は渡されたフレームを固定終端へ丸めず、波の継続運動を追従する。
    """

    def __init__(self, sweep, H=11.0, seed=793):
        self.sweep, self.H = sweep, float(H)
        signature = inspect.signature(sweep.sample)
        try:
            signature.bind(1, self.H)
            self._takes_height = True
        except TypeError:
            signature.bind(1)
            self._takes_height = False
        surface = self._surface(285)
        self.n_v, self.n_u = surface.shape[:2]
        motion = getattr(sweep, "motion", None)
        self.i_c = int(getattr(motion, "i_c", round(.475*(self.n_u-1))))
        self.i_t = int(getattr(motion, "i_t", round(.630*(self.n_u-1))))
        rng = np.random.default_rng(seed)
        positions = np.array((.30, .345, .392, .424, .458, .492,
                              .523, .558, .592, .632, .675, .722))
        roots = [(v, self.i_t-rng.uniform(3, 12), rng.uniform(.78, 1.20))
                 for v in positions]
        # 最高点から先端にも連ね、峰方向の一列だけの飾りにしない。
        roots += [(v, self.i_c+(self.i_t-self.i_c)*u, size)
                  for v, u, size in ((.49, .22, .42), (.46, .39, .54),
                                     (.53, .52, .64), (.485, .66, .74),
                                     (.55, .80, .68), (.47, .93, .82))]
        self.roots = np.array([(v*(self.n_v-1), u) for v, u, _ in roots])
        self.lengths = np.array([self.H*.17*size for _, _, size in roots])
        self.phase = rng.uniform(0, math.tau, len(roots))
        local, ids, faces = [], [], []
        offset = 0
        for group in range(len(roots)):
            vertices, topology = _cluster(seed+group*59)
            local.append(vertices)
            ids.append(np.full(len(vertices), group, dtype=np.int32))
            # 局所の「横・前・外」はワールド写像では左手系となる。
            faces.append(topology[:, ::-1]+offset)
            offset += len(vertices)
        self.local = np.vstack(local)
        self.group_ids = np.concatenate(ids)
        self.filament_vertex_count = len(self.local)
        drop_vertices, drop_faces = _drop_template()
        self.drop_local = drop_vertices
        self.drop_count = 54
        self.drop_group = rng.integers(0, len(roots), self.drop_count)
        self.drop_phase = rng.uniform(0, 102, self.drop_count)
        self.drop_size = rng.uniform(.25, .63, self.drop_count)*self.H/11
        self.drop_lateral = rng.uniform(-.55, .55, self.drop_count)
        self.drop_forward = rng.uniform(.30, .85, self.drop_count)
        self.drop_outward = rng.uniform(.25, .85, self.drop_count)
        for _ in range(self.drop_count):
            faces.append(drop_faces+offset)
            offset += len(drop_vertices)
        self.faces = np.vstack(faces)
        self.material_indices = np.zeros(len(self.faces), dtype=np.int32)
        self.vertex_count = offset
        self.root_uv_ranges = {
            "v": [float(self.roots[:, 0].min()/(self.n_v-1)),
                  float(self.roots[:, 0].max()/(self.n_v-1))],
            "u_indices": [int(self.roots[:, 1].min())-14, int(self.roots[:, 1].max())+7],
            "note": "各根の周囲で白を接続する。範囲全体を一枚の白い帯で塗りつぶさない。",
        }

    def _surface(self, frame):
        value = self.sweep.sample(frame, self.H) if self._takes_height else self.sweep.sample(frame)
        value = np.asarray(value, dtype=float)
        if value.ndim != 3 or value.shape[-1] != 3:
            raise ValueError("波面は (n_v, n_u, 3) の配列で渡してください。")
        return value

    def root_mask(self, frame=285, surface=None):
        """水体の頂点色へ合成する、根元だけの白色量 (n_v, n_u)。

        戻り値は 0～1。海面全体へ白い帯を広げず、各管の太い根が
        水体から連続して見えるよう、その周囲だけへ合成する。
        """
        if surface is None:
            surface = self._surface(frame)
        surface = np.asarray(surface, dtype=float)
        v, u = self.roots.T
        du = (self._interp(surface, v, u+1)-self._interp(surface, v, u-1))*.5
        dv = (self._interp(surface, v+1, u)-self._interp(surface, v-1, u))*.5
        spacing_u = np.maximum(np.linalg.norm(du, axis=1), self.H*.001)
        spacing_v = np.maximum(np.linalg.norm(dv, axis=1), self.H*.001)
        height = np.interp(v, np.arange(self.n_v), np.max(surface[:, :, 2], axis=1))/self.H
        growth = _smooth((float(frame)-105)/150)*_smooth((height-.42)/.38)
        yy, xx = np.mgrid[:self.n_v, :self.n_u]
        mask = np.zeros((self.n_v, self.n_u), dtype=float)
        for k in range(len(self.roots)):
            center_u = u[k]-.055*self.lengths[k]/spacing_u[k]
            radius_u = max(1.8, .29*self.lengths[k]/spacing_u[k])
            radius_v = max(.8, .27*self.lengths[k]/spacing_v[k])
            distance = ((xx-center_u)/radius_u)**2+((yy-v[k])/radius_v)**2
            patch = _smooth((1-distance)/.38)*growth[k]
            mask = np.maximum(mask, patch)
        return mask

    @staticmethod
    def _interp(surface, v, u):
        v = np.clip(v, 0, surface.shape[0]-1.001)
        u = np.clip(u, 0, surface.shape[1]-1.001)
        iv, iu = v.astype(int), u.astype(int)
        tv, tu = (v-iv)[:, None], (u-iu)[:, None]
        return ((1-tv)*((1-tu)*surface[iv, iu]+tu*surface[iv, iu+1])
                + tv*((1-tu)*surface[iv+1, iu]+tu*surface[iv+1, iu+1]))

    def sample(self, frame, surface=None):
        """固定トポロジの頂点をワールド座標 m で返す。

        小滴は波に対する局所的な放出軌跡であり、流体の粒子ではない。
        102 フレーム周期の再放出時は大きさを十分小さくして切替を隠す。
        """
        if surface is None:
            surface = self._surface(frame)
        surface = np.asarray(surface, dtype=float)
        v, u = self.roots.T
        origins = self._interp(surface, v, u)
        du = (self._interp(surface, v, u+1)-self._interp(surface, v, u-1))*.5
        dv = (self._interp(surface, v+1, u)-self._interp(surface, v-1, u))*.5
        forward, across = _unit(du), _unit(dv)
        outward = _unit(np.cross(forward, across))
        across = _unit(np.cross(outward, forward))
        crest_height = np.interp(v, np.arange(self.n_v), np.max(surface[:, :, 2], axis=1))/self.H
        maturity = _smooth((float(frame)-105)/150)
        growth = maturity*_smooth((crest_height-.42)/.38)
        group = self.group_ids
        x, t, z = self.local.T
        length = self.lengths[group]*(.006+.994*growth[group])
        # 枝は主流方向へ伸びる。横広がりの面は緩く回して、円柱の束に見えるのを避ける。
        turn = (.76+.28*np.sin(self.phase[group]))*_smooth(np.maximum(t, 0)/.60)
        spread = across[group]*np.cos(turn)[:, None]+outward[group]*np.sin(turn)[:, None]
        normal = outward[group]*np.cos(turn)[:, None]-across[group]*np.sin(turn)[:, None]
        breathing = 1.0+.028*np.sin(float(frame)*.065+self.phase[group])*_smooth(np.maximum(t, 0)/.65)
        result = (origins[group]+spread*(x*length)[:, None]
                  + forward[group]*(t*length*breathing)[:, None]+normal*(z*length)[:, None])
        # 太い根の後半は平面近似で浮かせず、実際の波面に沿わせる。
        along_spacing = np.maximum(np.linalg.norm(du, axis=1), self.H*.001)
        across_spacing = np.maximum(np.linalg.norm(dv, axis=1), self.H*.001)
        attached = self._interp(surface, v[group]+x*length/across_spacing[group],
                                u[group]+t*length/along_spacing[group])
        attached += outward[group]*(z*length)[:, None]
        attach_weight = 1-_smooth((t+.05)/.34)
        result = result*(1-attach_weight[:, None])+attached*attach_weight[:, None]
        result += outward[group]*(self.H*(.0018*growth[group]-.009*(1-growth[group])))[:, None]
        # 分離した滴。大きさを出現・消失の両端で滑らかに変える。
        dg = self.drop_group
        age = np.mod(float(frame)-190+self.drop_phase, 102)/30.0
        visibility = _smooth(age/.18)*(1-_smooth((age-1.30)/.45))*growth[dg]
        active_age = np.minimum(age, 1.75)
        centers = (origins[dg]+across[dg]*(self.drop_lateral*active_age)[:, None]
                   + forward[dg]*(self.lengths[dg]*.8+self.drop_forward*active_age)[:, None]
                   + outward[dg]*(self.drop_outward*active_age)[:, None])
        centers[:, 2] += .95*active_age-.80*active_age*active_age
        scale = self.drop_size*(.001+.999*visibility)
        drops = centers[:, None, :]+self.drop_local[None, :, :]*scale[:, None, None]
        return np.vstack((result, drops.reshape(-1, 3)))


CrestFilaments = Whitewater
