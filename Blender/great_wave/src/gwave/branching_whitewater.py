"""波面に付着する、厚みを持つ分岐白波の固定トポロジ生成。

映像参照の広い根元と短い鉤状の枝を、連結した輪郭から立体化する。
流体計算ではなく造形アニメーションであり、参照映像の複製ではない。
NumPy のみを使用し、Blender の状態を変更しない。
"""

from __future__ import annotations

import math
import numpy as np


def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-10)


def _bezier(points, count=34):
    p = np.asarray(points, dtype=float)
    t = np.linspace(0.0, 1.0, count)[:, None]
    return ((1-t)**3*p[0] + 3*(1-t)**2*t*p[1]
            + 3*(1-t)*t*t*p[2] + t**3*p[3])


def _outline(field, xs, ys):
    """等値線をたどり、最も大きな閉曲線を返す。"""
    cases = {
        1: ((3, 0),), 2: ((0, 1),), 3: ((3, 1),),
        4: ((1, 2),), 5: ((3, 2), (0, 1)), 6: ((0, 2),),
        7: ((3, 2),), 8: ((2, 3),), 9: ((0, 2),),
        10: ((0, 3), (1, 2)), 11: ((1, 2),),
        12: ((1, 3),), 13: ((0, 1),), 14: ((0, 3),),
    }
    edge_pairs = ((0, 1), (1, 2), (2, 3), (3, 0))
    adjacent, positions = {}, {}
    sign = field > 0
    codes = (sign[:-1, :-1].astype(np.uint8)
             + 2*sign[:-1, 1:] + 4*sign[1:, 1:] + 8*sign[1:, :-1])
    for j, i in np.argwhere((codes > 0) & (codes < 15)):
        pts = np.array(((xs[i], ys[j]), (xs[i+1], ys[j]),
                        (xs[i+1], ys[j+1]), (xs[i], ys[j+1])))
        vals = np.array((field[j, i], field[j, i+1],
                         field[j+1, i+1], field[j+1, i]))
        for ea, eb in cases[int(codes[j, i])]:
            keys = []
            for edge in (ea, eb):
                a, b = edge_pairs[edge]
                q = pts[a] + vals[a]/(vals[a]-vals[b])*(pts[b]-pts[a])
                key = tuple(np.round(q, 8))
                positions[key] = q
                keys.append(key)
            a, b = keys
            adjacent.setdefault(a, []).append(b)
            adjacent.setdefault(b, []).append(a)
    loops, used = [], set()
    for start in adjacent:
        if start in used:
            continue
        current, previous, loop = start, None, []
        for _ in range(len(adjacent)+1):
            loop.append(positions[current])
            used.add(current)
            candidates = [q for q in adjacent[current] if q != previous]
            if not candidates:
                break
            nxt = candidates[0]
            if nxt == start:
                if len(loop) > 8:
                    loops.append(np.array(loop))
                break
            if nxt in used:
                break
            previous, current = current, nxt
    if not loops:
        raise ValueError("白波の閉じた輪郭を生成できませんでした。")
    return max(loops, key=lambda p: abs(np.sum(
        p[:, 0]*np.roll(p[:, 1], -1)-p[:, 1]*np.roll(p[:, 0], -1))))


def _resample_closed(p, count=220):
    """細い枝先を残しながら輪郭の密度をそろえる。"""
    p = np.vstack((p, p[0]))
    distances = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    target = np.linspace(0, distances[-1], count, endpoint=False)
    q = np.column_stack([np.interp(target, distances, p[:, k]) for k in (0, 1)])
    for _ in range(2):
        q = 0.76*q + 0.12*(np.roll(q, 1, axis=0)+np.roll(q, -1, axis=0))
    if np.sum(q[:, 0]*np.roll(q[:, 1], -1)-q[:, 1]*np.roll(q[:, 0], -1)) < 0:
        q = q[::-1]
    return q


def _triangulate(p):
    """凹形の白波輪郭を三角形分割する。穴を作らず根元を接続する。"""
    remaining = list(range(len(p)))
    triangles = []
    guard = 0
    while len(remaining) > 3 and guard < len(p)*len(p):
        guard += 1
        found = False
        for k in range(len(remaining)):
            ia, ib, ic = remaining[k-1], remaining[k], remaining[(k+1) % len(remaining)]
            a, b, c = p[ia], p[ib], p[ic]
            ab, bc = b-a, c-b
            if ab[0]*bc[1]-ab[1]*bc[0] <= 1e-11:
                continue
            others = [v for v in remaining if v not in (ia, ib, ic)]
            q = p[others]
            cross_a = ab[0]*(q[:, 1]-a[1])-ab[1]*(q[:, 0]-a[0])
            cross_b = bc[0]*(q[:, 1]-b[1])-bc[1]*(q[:, 0]-b[0])
            ca = a-c
            cross_c = ca[0]*(q[:, 1]-c[1])-ca[1]*(q[:, 0]-c[0])
            if np.any((cross_a > -1e-10) & (cross_b > -1e-10) & (cross_c > -1e-10)):
                continue
            triangles.append((ia, ib, ic))
            remaining.pop(k)
            found = True
            break
        if not found:
            raise ValueError("白波輪郭の三角形分割に失敗しました。")
    if len(remaining) == 3:
        triangles.append(tuple(remaining))
    return np.asarray(triangles, dtype=np.int32)


def _template(seed):
    """広い根元、一段目の枝、二段目の短い鉤を一つの厚片にする。"""
    rng = np.random.default_rng(seed)
    branches = [
        (((0, -.035), (-.08, .19), (.14, .51), (.05, .65)), .160, .070),
        (((-.02, .23), (-.33, .32), (-.54, .90), (-.42, .32)), .110, .002),
        (((.03, .31), (.48, .43), (.80, .89), (.65, .30)), .108, .002),
        (((.02, .49), (-.16, .93), (.55, 1.17), (.25, .65)), .125, .002),
        (((-.17, .39), (-.49, .39), (-.79, .82), (-.76, .26)), .068, .002),
        (((.00, .60), (-.43, .80), (-.21, 1.08), (-.06, .85)), .063, .002),
        (((.28, .47), (.38, .73), (.90, .79), (.78, .56)), .073, .002),
    ]
    xs = np.linspace(-1.0, 1.0, 100)
    ys = np.linspace(-.40, 1.30, 110)
    xx, yy = np.meshgrid(xs, ys)
    field = np.full_like(xx, -10.0)
    for number, (control, radius_a, radius_b) in enumerate(branches):
        control = np.asarray(control, dtype=float)
        # 分岐の接続点を動かし過ぎず、先端の方向と長さを変える。
        control[1:] += rng.normal(0.0, .032, (3, 2))
        if number > 6 and rng.random() < .22:
            continue
        curve = _bezier(control)
        t = np.linspace(0, 1, len(curve))
        radii = radius_b + (radius_a-radius_b)*(1-t)
        # 先端直前を細くし過ぎず、白い面として読める幅を確保する。
        radii += .014*np.sin(np.pi*t)
        for center, radius in zip(curve, radii):
            field = np.maximum(field, radius-np.hypot(xx-center[0], yy-center[1]))
    boundary = _resample_closed(_outline(field, xs, ys))
    triangles = _triangulate(boundary)
    centers = boundary[triangles].mean(axis=1)
    plane = np.vstack((boundary, centers))
    n, n_boundary = len(plane), len(boundary)
    positive, negative = [], []
    for i, (a, b, c) in enumerate(triangles):
        mid = n_boundary+i
        positive.extend(((a, b, mid), (b, c, mid), (c, a, mid)))
        negative.extend(((mid+n, b+n, a+n), (mid+n, c+n, b+n), (mid+n, a+n, c+n)))
    faces = positive + negative
    material_indices = [0]*len(positive) + [1]*len(negative)
    for i in range(n_boundary):
        j = (i+1) % n_boundary
        faces.extend(((i+n, j+n, j), (i+n, j, i)))
        material_indices.extend((1, 1))
    vertices = np.vstack((plane, plane))
    side = np.r_[np.ones(n), -np.ones(n)]
    # 表面の中心をふくらませ、板の厚みと枝の曲がりを別々に持たせる。
    pillow = np.r_[np.full(n_boundary, .50), np.full(len(centers), 1.0)]
    pillow = np.tile(pillow, 2)
    return vertices, side*pillow, np.asarray(faces, dtype=np.int32), np.asarray(material_indices)


class Whitewater:
    """LocalizedSweep を追従する白波。faces は全フレーム共通。

    使用例::

        foam = Whitewater(sweep, H=11)
        vertices = foam.sample(285)
        mesh.from_pydata(vertices.tolist(), [], foam.faces.tolist())

    material_indices の 0 は乳白色の表面、1 は薄い青灰色の裏面と厚み。
    初期は水面内へ格納し、120～285 フレームで成長する。
    """

    def __init__(self, sweep, H=11.0, seed=271):
        self.sweep = sweep
        self.H = float(H)
        self.motion = sweep.motion
        self.n_v = int(sweep.n_v)
        self.n_u = int(sweep.n_u)
        rng = np.random.default_rng(seed)
        # 主列は張り出しの縁、補助列は直前の波面。周期的な等間隔を避ける。
        positions = np.array((.285, .325, .370, .400, .435, .465, .490,
                              .520, .550, .580, .615, .650, .685, .715, .750))
        positions[1:-1] += rng.uniform(-.006, .006, len(positions)-2)
        roots = [(v, self.motion.i_t-rng.uniform(7, 15), 1.0) for v in positions]
        roots += [(v, self.motion.i_t-rng.uniform(26, 35), .55)
                  for v in np.array((.365, .435, .505, .570, .640))]
        # 主峰から先端へ連なる別の枝群。峰方向の一列だけでは、側面の
        # 高い輪郭が無地の塊になるため、断面方向にも大小を連ねる。
        roots += [(v, u, size) for v, u, size in (
            (.468, 213, .48), (.485, 223, .62), (.455, 231, .68),
            (.515, 239, .78), (.477, 247, .91), (.540, 254, .85),
            (.495, 263, 1.00), (.468, 273, .75))]
        local, depth, ids, faces, material_indices = [], [], [], [], []
        self.roots, lengths, widths, turns, phases = [], [], [], [], []
        offset = 0
        for group, (v, u, size) in enumerate(roots):
            points, depths, topology, materials = _template(seed+group*37)
            local.append(points)
            depth.append(depths)
            ids.append(np.full(len(points), group, dtype=np.int32))
            faces.append(topology+offset)
            material_indices.append(materials)
            offset += len(points)
            self.roots.append((v*(self.n_v-1), u))
            strength = .65+.35*np.exp(-((v-.50)/.22)**2)
            lengths.append(self.H*.20*size*strength*rng.uniform(.72, 1.22))
            widths.append(rng.uniform(.65, 1.12))
            turns.append(rng.uniform(-.38, .38))
            phases.append(rng.uniform(0, math.tau))
        self.local = np.vstack(local)
        self.depth = np.concatenate(depth)
        self.group_ids = np.concatenate(ids)
        # 峰方向、断面方向、外向き法線の基底は左手系なので面の向きを反転する。
        self.faces = np.vstack(faces)[:, ::-1].copy()
        self.material_indices = np.concatenate(material_indices).astype(np.int32)
        self.roots = np.asarray(self.roots)
        self.lengths = np.asarray(lengths)
        self.widths = np.asarray(widths)
        self.turns = np.asarray(turns)
        self.phases = np.asarray(phases)

    @staticmethod
    def _interpolate(surface, v, u):
        v = np.clip(v, 0, surface.shape[0]-1.001)
        u = np.clip(u, 0, surface.shape[1]-1.001)
        vi, ui = v.astype(int), u.astype(int)
        fv, fu = (v-vi)[:, None], (u-ui)[:, None]
        return ((1-fv)*((1-fu)*surface[vi, ui]+fu*surface[vi, ui+1])
                + fv*((1-fu)*surface[vi+1, ui]+fu*surface[vi+1, ui+1]))

    def sample(self, frame, surface=None):
        """波面の位置・接線・法線から白波を計算する。単位はメートル。

        既に評価した波面を surface に渡せば、水体を二重に計算しない。
        群ごとの位相差は成長中だけに適用し、285 以後は厳密に静止する。
        """
        frame = min(float(frame), 285.0)
        if surface is None:
            surface = self.sweep.sample(frame, self.H)
        surface = np.asarray(surface, dtype=float)
        v, u = self.roots.T
        roots = self._interpolate(surface, v, u)
        along = _unit(self._interpolate(surface, v, u+2)
                      - self._interpolate(surface, v, u-2))
        across = _unit(self._interpolate(surface, v+1, u)
                       - self._interpolate(surface, v-1, u))
        normal = _unit(np.cross(along, across))
        across = _unit(np.cross(normal, along))
        # 120 の前には水面の内側に小さく格納する。ゼロ面積にはしない。
        tau = np.clip((frame-120.0)/165.0, 0.0, 1.0)
        delay = .14*(.5+.5*np.sin(self.phases))
        growth = _smooth((tau-delay)/(1-delay))
        # 低い肩には大きな爪を生やさない。局所高と発達段階の両方を使う。
        crest_heights = np.max(surface[:, :, 2], axis=1)/self.H
        local_height = np.interp(v, np.arange(len(crest_heights)), crest_heights)
        local_tau = self.sweep.row_state(frame)["local_tau"]
        local_tau = np.interp(v, np.arange(len(local_tau)), local_tau)
        growth *= _smooth((local_height-.45)/.32)*_smooth((local_tau-.42)/.43)
        scale = .012+.988*growth
        root_shift = self.H*(-.010*(1-growth)+.0020*growth)
        roots = roots+normal*root_shift[:, None]
        group = self.group_ids
        x, t = self.local.T
        angle = self.turns[group]
        x_local = x*np.cos(angle)-t*np.sin(angle)
        t_local = x*np.sin(angle)+t*np.cos(angle)
        length = self.lengths[group]*scale[group]
        x_local = x_local*self.widths[group]*length
        t_local = t_local*length
        # 先端を面の外へ浮かせ、枝ごとに奥行きの差と巻きを付ける。
        bend = (.12*np.maximum(t, 0)**1.5
                + .055*np.sin(5*x+self.phases[group])*np.maximum(t, 0)
                - .075*np.maximum(t-.72, 0)**2/.28**2)
        thickness = self.H*.006*(.65+.35*np.clip(1-t, 0, 1))*self.depth
        depth = bend*length+thickness*scale[group]
        # 根元は水面に沿い、枝先ほど片面を立てる。正面で細い側面だけになるのを防ぐ。
        twist = (1.02+.22*np.sin(self.phases[group]))*_smooth(np.maximum(t, 0)/.60)
        spread = across[group]*np.cos(twist)[:, None]+normal[group]*np.sin(twist)[:, None]
        sheet_normal = normal[group]*np.cos(twist)[:, None]-across[group]*np.sin(twist)[:, None]
        return (roots[group]+spread*x_local[:, None]
                + along[group]*t_local[:, None]+sheet_normal*depth[:, None])
