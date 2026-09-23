"""検査用の合成波。峰、波頭先端、最深点と時間発展を解析的に求められる張り出し断面を、
固定トポロジーの格子メッシュへ展開する。

測定処理を検証するための既知形状であり、実作品の波形案ではない。
tests/selftest_measure.py はこれを使って gw.raster / gw.silhouette / gw.profile_metrics が
既知の値を復元できるか検証する。S / M / G 検査の仮モデルとしても再利用できる。

断面形状群（H 単位、最終姿勢の峰 = (0, 1)、静水面 Z = 0）
---------------------------------------------------------------------------
直線と円弧を順につなぐタートル方式の経路（G1 連続）。すべて閉形式で求める。

  back  : B0 円弧 0 -> a_low | B1 方向 a_low の直線（裾が Z = 0 になる長さを解く）|
          B2 円弧 a_low -> a_max | B3 方向 a_max の直線 | B4 円弧 a_max -> 0（峰で終わる）
  front : F1 円弧 0 -> -b | F2 直線（波頭の上側）| F3 先端の円弧、半径 r、回転角 kappa |
          F4 直線（下側）| F5 方向 -90 deg までの内側の円弧（張り出しがある場合のみ）|
          F6 方向 0 までの円弧。谷がちょうど Z = 0 で閉じる半径を求める。

各パラメーターは t in [0, 1] の滑らかな関数（立ち上がり -> 張り出し -> 巻き込み）なので、峰、
先端（先端円弧の最右点）、最深点（F5 の終点）、o、点ごとの theta (= b + kappa)、
phi（上側が十分長くなれば -b）を各フレームで解析的に求められる。

格子: U は断面方向（背の裾 -> 峰 -> 先端 -> 腹 -> 谷）、V は Y 方向。
Y 方向の両端を細める方式:
  'clip'   （既定、有効）段階1: c を最右点の X から最深点の X へ動かし、X' = min(X, c) とする。
           波頭を水平に引っ込めるので主断面の内部に収まる。
           段階2: g -> 0 とし、Z' = g * Z とする。展開した断面は輪郭全体を満たし、
           内側のくぼみを覆わない。
  'zscale' （失敗例）Z' = g * Z のみ。両端で押しつぶされた波頭がくぼみの前後にかかり、
           奥への見通しをふさぐ。
  'none'   （非立体の例）単純な押出し。端から見ると厚さのない面になり、投影面積はゼロ。
  'lift_clip'（原画の輪郭を展開するため2026-09-20に追加。docs/records/step1_proof.md）
           'clip' が有効なのは、波頭の下面が、その左側にあるくぼみの天井より下に出ない場合だけ。
           X' = min(X, c) は点を水平に動かすため、原画の輪郭（脇が最も高く、右側で波頭が垂れる）
           では経路がくぼみを横切り、断面の和集合の輪郭で天井が平らに埋まってしまう。
           'lift_clip' は段階0と上限処理を加え、各頂点を主断面内部の直線上で動かす。
             段階0（d 1 -> LIFT_END_D）: 先端から最深点までの区間を鉛直に波頭内部へ持ち上げ、
                     最深点から数えた Z の累積最大値へ合わせる。これにより下面の各点は、
                     その左側にあるどの天井点よりも下に出なくなる。
             段階1（d LIFT_END_D -> 0.5）: 'clip' と同様に X' = min(X, c) とする。さらに点が
                     x = c での主断面の上端を超えないよう Z' = min(Z', Z_top(c)) とし、切取り位置の
                     右側にある峰が元の高さのまま左へ引き延ばされるのを防ぐ。
             段階2（d 0.5 -> 0）: 'clip' と同様に Z' = g * Z とする。
           格子、頂点数、Y 方向の配置は 'clip' と同じ。

実行例（画面なし）:
  blender --background --factory-startup --python make_synthetic_wave.py -- [--frames 31]
          [--taper clip|lift_clip|zscale|none] [--profile-json <base_contour.json>] [--H 11]
          [--out-blend <path>] [--no-json]
モジュールとしての利用:  import make_synthetic_wave as msw ; obj, info = msw.build_object(scene, ...)
"""
import argparse
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from gw import bootstrap, frame as gw_frame, paths, profile_metrics as pm  # noqa: E402

N_FRAMES_DEFAULT = 31
FRAME_START = 1
SYNTHETIC_CONTOUR_JSON = os.path.join(_HERE, "synthetic_contour.json")

# 区間ごとの標本数（固定することでトポロジーを一定に保つ）
PIECES_BACK = (("B0", 24), ("B1", 50), ("B2", 24), ("B3", 30), ("B4", 40))
PIECES_FRONT = (("F1", 40), ("F2", 50), ("F3", 32), ("F4", 12), ("F5", 60), ("F6", 80))

# Y 方向の配置（H 単位）: 形状が一定の中央部と、両端を細める区間
Y_CENTER_HALF_H = 0.5
Y_TAPER_H = 0.6
N_V_CENTER = 9
N_V_STAGE1 = 10
N_V_STAGE2 = 14

# 検査用の動きの段階境界（全時間に対する割合）
T_RISE_END = 0.42
T_OVERHANG_END = 0.74


def _smooth(p):
    p = min(max(p, 0.0), 1.0)
    return p * p * p * (p * (6.0 * p - 15.0) + 10.0)


def _lerp(a, b, w):
    return a + (b - a) * w


def fixture_params(t):
    """正規化時刻 t in [0, 1] における全形状パラメーター。角度は度、長さは H 単位。"""
    t = min(max(float(t), 0.0), 1.0)
    p1 = _smooth(t / T_RISE_END)
    p2 = _smooth((t - T_RISE_END) / (T_OVERHANG_END - T_RISE_END))
    p3 = _smooth((t - T_OVERHANG_END) / (1.0 - T_OVERHANG_END))
    e = _smooth(t)
    return {
        "t": t,
        "h": _lerp(0.35, 1.0, p1),
        "x_c": _lerp(-0.55, 0.0, e),
        "a_low": _lerp(8.0, 25.0, p1),
        "a_max": _lerp(14.0, 47.0, p1),
        "R_b0": 1.0, "R_b2": 0.6, "L_b3": _lerp(0.05, 0.35, p1), "R_b4": _lerp(1.0, 0.30, p1),
        "b": _lerp(12.0, 20.0, p1) + 12.0 * p2 + 8.0 * p3,
        "kappa": 70.0 * p1 + 40.0 * p2 + 25.0 * p3,
        "r": _lerp(_lerp(0.35, 0.05, p1), 0.0125, p2),
        "R_f1": _lerp(_lerp(1.2, 0.45, p1), 0.20, p2),
        "L_f2": 0.22 * p2 + 0.08 * p3,
        "L_f4": 0.06 * p2,
        "R_f5": _lerp(0.05, 0.30, _smooth((t - T_RISE_END) / (1.0 - T_RISE_END))),
    }


# ---------------------------------------------------------------------- タートル方式の経路
def _arc(p0, psi0_deg, turn_deg, R, f):
    """p0 から方向 psi0 で始まり、符号付き回転角（度、正 = 反時計回り）と半径 R を持つ円弧の、
    比率 f（配列）に対応する点を返す。回転角または半径がゼロなら全点を p0 とする。"""
    f = np.asarray(f, dtype=np.float64)
    if abs(turn_deg) < 1e-12 or R <= 0:
        return np.repeat(np.asarray(p0, dtype=np.float64)[None, :], f.size, axis=0), psi0_deg
    k = math.copysign(1.0 / R, turn_deg)
    a0 = math.radians(psi0_deg)
    a = a0 + np.radians(turn_deg) * f
    x = p0[0] + (np.sin(a) - math.sin(a0)) / k
    z = p0[1] + (-np.cos(a) + math.cos(a0)) / k
    return np.stack([x, z], axis=1), psi0_deg + turn_deg


def _line(p0, psi_deg, L, f):
    f = np.asarray(f, dtype=np.float64)
    a = math.radians(psi_deg)
    return np.stack([p0[0] + L * f * math.cos(a), p0[1] + L * f * math.sin(a)], axis=1), psi_deg


def _piece_list(P):
    """全長・半径を解いた [(name, kind, value, extra)] を返す。背の経路は裾から始まる。"""
    a_low, a_max = P["a_low"], P["a_max"]
    h = P["h"]
    gained = (P["R_b0"] * (1 - math.cos(math.radians(a_low)))
              + P["R_b2"] * (math.cos(math.radians(a_low)) - math.cos(math.radians(a_max)))
              + P["L_b3"] * math.sin(math.radians(a_max))
              + P["R_b4"] * (1 - math.cos(math.radians(a_max))))
    L_b1 = (h - gained) / math.sin(math.radians(a_low))
    if L_b1 < 0:
        raise ValueError("fixture parameters give a negative back length (t=%.3f)" % P["t"])
    back = [("B0", "arc", +a_low, P["R_b0"]), ("B1", "line", L_b1, None),
            ("B2", "arc", a_max - a_low, P["R_b2"]), ("B3", "line", P["L_b3"], None),
            ("B4", "arc", -a_max, P["R_b4"])]
    b, kap = P["b"], P["kappa"]
    over = b + kap > 90.0
    front = [("F1", "arc", -b, P["R_f1"]), ("F2", "line", P["L_f2"], None),
             ("F3", "arc", -kap, P["r"]), ("F4", "line", P["L_f4"], None),
             ("F5", "arc", (b + kap - 90.0) if over else 0.0, P["R_f5"]),
             ("F6", "arc", 90.0 if over else (b + kap), None)]     # 経路をたどりながら半径を求める
    return back, front, over


def profile_points(t, samples=None, dense_ds=None):
    """時刻 t の主断面を返す。

    samples : 区間 -> 標本数 n の辞書（既定値は固定格子の標本数）。dense_ds を指定した場合は、
    各区間をおよそその弧長間隔で標本化する（解析的な参照曲線用）。
    戻り値: (pts (N, 2) H 単位, piece_index (N,) 整数, 解析的な基準点を含む info 辞書)
    """
    P = fixture_params(t)
    back, front, over = _piece_list(P)
    counts = dict(PIECES_BACK + PIECES_FRONT)
    if samples:
        counts.update(samples)
    names = [n for n, _ in PIECES_BACK + PIECES_FRONT]

    def n_for(name, length):
        if dense_ds is None:
            return counts[name]
        return max(2, int(math.ceil(length / dense_ds)))

    def walk(pieces, p0, psi0):
        pts, ids, ends = [], [], {}
        p, psi = np.asarray(p0, dtype=np.float64), psi0
        for name, kind, val, R in pieces:
            if kind == "line":
                length = val
                n = n_for(name, length)
                q, psi_n = _line(p, psi, val, np.arange(1, n + 1) / n)
            else:
                if name == "F6":
                    turn = val
                    R = p[1] / (1.0 - math.cos(math.radians(turn))) if turn > 1e-9 else 0.0
                length = R * math.radians(abs(val))
                n = n_for(name, length)
                q, psi_n = _arc(p, psi, val, R, np.arange(1, n + 1) / n)
            ends[name] = {"start": p.copy(), "psi0": psi, "turn": val if kind == "arc" else 0.0,
                          "R": R, "kind": kind, "length": length}
            pts.append(q)
            ids.append(np.full(n, names.index(name)))
            p, psi = q[-1].copy(), psi_n
        return np.concatenate(pts), np.concatenate(ids), ends, p

    # 背: 仮の裾 x = 0 から経路をたどり、終点が峰になるよう平行移動する
    bp, bid, bends, bend = walk(back, (0.0, 0.0), 0.0)
    shift = P["x_c"] - bend[0]
    bp[:, 0] += shift
    for v in bends.values():
        v["start"][0] += shift
    hem = np.array([[shift, 0.0]])
    crest = np.array([P["x_c"], P["h"]])
    bp[-1] = crest                                   # 峰の正確な位置へ合わせる（丸め誤差のずれを除く）
    fp, fid, fends, _ = walk(front, crest, 0.0)
    fp[-1, 1] = 0.0
    pts = np.concatenate([hem, bp, fp])
    ids = np.concatenate([[0], bid, fid])

    # ---- 解析的な基準点
    info = {"params": P, "overhanging": bool(over), "crest": [float(crest[0]), float(crest[1])],
            "theta_pointwise_deg": float(min(P["b"] + P["kappa"], 180.0)),
            "pieces": names, "hem_x": float(shift)}
    if over:
        c3 = fends["F3"]
        a0 = math.radians(c3["psi0"])
        centre = c3["start"] + P["r"] * np.array([math.sin(a0), -math.cos(a0)])    # 右向き法線（時計回りの円弧）
        tip = centre + np.array([P["r"], 0.0])
        deep = fends["F6"]["start"]
        info["head_tip"] = [float(tip[0]), float(tip[1])]
        info["inner_deepest"] = [float(deep[0]), float(deep[1])]
        info["o"] = float(max(0.0, tip[0] - crest[0]))
        info["cap_center"] = [float(centre[0]), float(centre[1])]
    else:
        info["head_tip"] = None
        info["inner_deepest"] = None
        info["o"] = 0.0
    info["x_clip_target"] = float(fends["F6"]["start"][0])      # F6 の始点の X（最深点／最も急な点）
    info["trough_end"] = [float(fp[-1, 0]), 0.0]
    info["x_max"] = float(pts[:, 0].max())
    info["top_side_straight_len"] = float(P["L_f2"])
    info["phi_exact_deg"] = float(-P["b"])
    info["rim_thickness_H"] = float(2.0 * P["r"])
    info["piece_ranges"] = {}
    for k, nme in enumerate(names):
        idx = np.nonzero(ids == k)[0]
        info["piece_ranges"][nme] = [int(idx[0]), int(idx[-1])]
    return pts, ids, info


def frame_to_t(frame, n_frames=N_FRAMES_DEFAULT):
    return (int(frame) - FRAME_START) / float(max(1, n_frames - 1))


# ---------------------------------------------------------------------- 輪郭 JSON から作る形状群
def _load_contour_curve(json_path, n_u):
    """基準輪郭 JSON の区間を連結して最終姿勢を作る。両端を端点の接線に沿って Z = 0 まで
    直線で延長し、弧長を等分した n_u 点へ再標本化する。"""
    bc = pm.load_base_contour(json_path)
    poly = pm.base_contour_polyline(bc)
    p = poly["pts_H"]
    ext = []
    # 左端: 最初の接線を Z = 0 まで下へ延ばす（仕様7bの直線延長）
    k = min(25, len(p) - 1)
    d = p[k] - p[0]
    if p[0, 1] > 1e-6 and d[1] > 1e-9:
        ext.append(p[0] - d * (p[0, 1] / d[1]))
    left = np.array(ext).reshape(-1, 2)
    # 右端: 輪郭が水面より上で終わる場合、最後の接線を Z = 0 まで下へ延ばす
    right = np.zeros((0, 2))
    if p[-1, 1] > 2e-3:
        d = p[-1] - p[-1 - k]
        if d[1] < -1e-9:
            right = (p[-1] - d * (p[-1, 1] / d[1])).reshape(1, 2)
        else:
            right = np.array([[p[-1, 0], 0.0]])
    q = np.concatenate([left, p, right])
    q[0, 1] = 0.0 if left.size else q[0, 1]
    C = pm.Curve(q)
    s = np.linspace(0.0, C.length, n_u)
    out = C.at(s)
    out[-1, 1] = min(out[-1, 1], 0.0) if right.size else out[-1, 1]
    return out, bc


def _contour_family_profile(final_pts, t):
    """接線角の補間により、穏やかなうねりから指定した最終折れ線へ変形する（標本数は固定）。
    (pts, info) を返す。この方式には解析的な基準点がなく、info には基本情報だけを収める。"""
    n = final_pts.shape[0]
    d = np.diff(final_pts, axis=0)
    ds1 = np.hypot(d[:, 0], d[:, 1])
    psi1 = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
    i_c = int(np.argmax(final_pts[:, 1]))
    u = (np.arange(n - 1) + 0.5) / (n - 1)
    u_c = (i_c) / float(n - 1)
    A = math.radians(18.0)
    psi0 = np.where(u <= u_c, A * np.sin(np.pi * u / max(u_c, 1e-6)),
                    -A * np.sin(np.pi * (u - u_c) / max(1.0 - u_c, 1e-6)))
    L0 = 3.0
    ds0 = np.full(n - 1, L0 / (n - 1))
    e = _smooth(t)
    psi = _lerp(psi0, psi1, e)
    ds = _lerp(ds0, ds1, e)
    x = np.concatenate([[0.0], np.cumsum(ds * np.cos(psi))])
    z = np.concatenate([[0.0], np.cumsum(ds * np.sin(psi))])
    s = np.concatenate([[0.0], np.cumsum(ds)])
    z0_final, z1_final = final_pts[0, 1], final_pts[-1, 1]
    # 弧長に比例させて終点の誤差を除く（e = 1 では変化が厳密にゼロ）
    z_start = e * z0_final
    z_end_target = e * z1_final
    z = z + z_start
    z = z - (z[-1] - z_end_target) * (s / s[-1])
    # 峰を配置する: x_c(t) を -0.55 から最終位置へ動かす
    k = int(np.argmax(z))
    x_c_final = final_pts[i_c, 0]
    x = x - x[k] + _lerp(-0.55, x_c_final, e)
    if e >= 1.0:
        return final_pts.copy(), {"overhanging": None}
    return np.stack([x, z], axis=1), {"overhanging": None}


# ---------------------------------------------------------------------- 格子
def v_layout():
    """'clip' の端部形状用に (y_H (n_v,), 段階1の重み q1 (n_v,), Z 倍率 g (n_v,)) を求める。"""
    inner = Y_CENTER_HALF_H
    d1 = np.linspace(1.0, 0.5, N_V_STAGE1 + 1)[1:]            # 端部を細める座標 d: 内側の端が1、外側の端が0
    d2 = np.linspace(0.5, 0.0, N_V_STAGE2 + 1)[1:]
    d_side = np.concatenate([d1, d2])
    y_side = inner + (1.0 - d_side) * Y_TAPER_H
    y_c = np.linspace(-inner, inner, N_V_CENTER)
    y = np.concatenate([-y_side[::-1], y_c, y_side])
    d = np.concatenate([d_side[::-1], np.ones(N_V_CENTER), d_side])
    q1 = np.array([_smooth((1.0 - v) / 0.5) for v in d])
    g = np.array([_smooth(v / 0.5) for v in d])
    return y, q1, g, d


LIFT_END_D = 0.8        # 'lift_clip': 下面の鉛直方向への持上げが完了する端部座標 d


def lift_clip_sections(profile_H, x_clip_target, d, g, under_branch=None):
    """'lift_clip' の端部断面を求める（モジュールの説明を参照）。d, g は各位置の端部座標と
    Z 倍率（v_layout）。under_branch は (波頭先端の添字, 最深点の添字) で、張り出しがなければ None。
    形状 (n_stations, n_u)、H 単位の配列 (X, Z) を返す。"""
    x, z = profile_H[:, 0], profile_H[:, 1]
    z_lift = z.copy()
    if under_branch is not None and int(under_branch[1]) > int(under_branch[0]):
        i_t, i_d = int(under_branch[0]), int(under_branch[1])
        z_lift[i_t:i_d + 1] = np.maximum.accumulate(z[i_t:i_d + 1][::-1])[::-1]
    x_max = x.max()
    X = np.empty((len(d), x.size))
    Z = np.empty((len(d), x.size))
    for j in range(len(d)):
        w_lift = _smooth((1.0 - d[j]) / (1.0 - LIFT_END_D))
        q = _smooth((LIFT_END_D - d[j]) / (LIFT_END_D - 0.5))
        zj = z + w_lift * (z_lift - z)
        c = x_max - q * (x_max - x_clip_target)
        over = x > c
        if over.any():
            k = int(np.argmax(x >= c))                 # 切取り線上またはその先の最初の標本が、その位置の上端
            if k > 0 and x[k] > x[k - 1]:
                z_top = z[k - 1] + (c - x[k - 1]) / (x[k] - x[k - 1]) * (z[k] - z[k - 1])
            else:
                z_top = z[k]
            sel = over.copy()
            sel[:k] = False
            zj = np.where(sel, np.minimum(zj, z_top), zj)
        X[j] = np.minimum(x, c)
        Z[j] = zj * g[j]
    return X, Z


def grid_vertices(profile_H, x_clip_target, taper="clip", H=11.0, under_branch=None):
    """一つの断面（H 単位）を展開した格子のワールド座標頂点 (n_v * n_u, 3) を返す。
    under_branch は端部方式 'lift_clip' だけで使う（lift_clip_sections を参照）。"""
    y, q1, g, d = v_layout()
    X = profile_H[:, 0][None, :].repeat(y.size, axis=0)
    Z = profile_H[:, 1][None, :].repeat(y.size, axis=0)
    if taper == "clip":
        x_max = profile_H[:, 0].max()
        c = x_max - q1 * (x_max - x_clip_target)
        X = np.minimum(X, c[:, None])
        Z = Z * g[:, None]
    elif taper == "lift_clip":
        X, Z = lift_clip_sections(profile_H, x_clip_target, d, g, under_branch)
    elif taper == "zscale":
        gz = np.array([_smooth(v) for v in d])
        Z = Z * gz[:, None]
    elif taper == "none":
        pass
    else:
        raise ValueError("unknown taper %r" % taper)
    Y = y[:, None].repeat(profile_H.shape[0], axis=1)
    V = np.stack([X * H, Y * H, Z * H], axis=-1).reshape(-1, 3)
    return V


def grid_faces(n_u, n_v):
    j, i = np.meshgrid(np.arange(n_v - 1), np.arange(n_u - 1), indexing="ij")
    a = (j * n_u + i).ravel()
    return np.stack([a, a + 1, a + n_u + 1, a + n_u], axis=1)


def grid_triangles(n_u, n_v):
    q = grid_faces(n_u, n_v)
    return np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])


class SyntheticWave:
    """Blender に依存しない断面形状群と格子。numpy のみを使う。

        sw = SyntheticWave(n_frames=31, taper='clip', H=11.0, profile_json=None, u_mult=1)
        verts = sw.vertices(frame)            # (n_v * n_u, 3) ワールド座標
        tris  = sw.triangles                  # (M, 3)
        info  = sw.analytic(frame)            # 既知の基準点（輪郭 JSON 方式では None の項目がある）
    """

    def __init__(self, n_frames=N_FRAMES_DEFAULT, taper="clip", H=11.0, profile_json=None, u_mult=1):
        self.n_frames = int(n_frames)
        self.taper = taper
        self.H = float(H)
        self.profile_json = profile_json
        self.u_mult = int(u_mult)
        self._final_json_pts = None
        if profile_json:
            n_u = 1 + sum(n for _, n in PIECES_BACK + PIECES_FRONT) * self.u_mult
            self._final_json_pts, self.base_contour = _load_contour_curve(profile_json, n_u)
        p, _ids, _info = self.profile(FRAME_START)
        self.n_u = p.shape[0]
        self.n_v = v_layout()[0].size
        self.faces = grid_faces(self.n_u, self.n_v)
        self.triangles = grid_triangles(self.n_u, self.n_v)

    def profile(self, frame):
        t = frame_to_t(frame, self.n_frames)
        if self._final_json_pts is not None:
            pts, info = _contour_family_profile(self._final_json_pts, t)
            m = pm.measure_profile(pts)
            if m["overhanging"]:
                xt = m["landmarks"]["inner_deepest"]["H"][0]
                info["under_branch"] = [int(m["landmarks"]["head_tip"]["index"]), int(m["landmarks"]["inner_deepest"]["index"])]
            else:
                xt = m["landmarks"]["theta_point"]["H"][0]
            info.update({"x_clip_target": float(xt), "overhanging": m["overhanging"], "params": {"t": t}})
            return pts, None, info
        samples = None
        if self.u_mult != 1:
            samples = {n: c * self.u_mult for n, c in PIECES_BACK + PIECES_FRONT}
        return profile_points(t, samples=samples)

    def analytic(self, frame):
        return self.profile(frame)[2]

    @staticmethod
    def under_branch(pts, ids, info):
        """端部方式 'lift_clip' 用の (波頭先端の添字, 最深点の添字)。None は張り出しなしを表す。"""
        if info.get("under_branch") is not None:
            return info["under_branch"]
        if ids is None or not info.get("overhanging") or not info.get("piece_ranges"):
            return None
        a, b = info["piece_ranges"]["F3"]                      # 解析的な形状群では先端円弧に波頭先端が含まれる
        return [a + int(np.argmax(pts[a:b + 1, 0])), int(info["piece_ranges"]["F5"][1])]

    def vertices(self, frame):
        pts, _ids, info = self.profile(frame)
        ub = self.under_branch(pts, _ids, info) if self.taper == "lift_clip" else None
        return grid_vertices(pts, info["x_clip_target"], self.taper, self.H, ub)

    def rim_u_indices(self):
        if self._final_json_pts is not None:
            m = pm.measure_profile(self._final_json_pts)
            if not m["overhanging"]:
                return np.zeros(0, np.int64)
            C = pm.Curve(self._final_json_pts)
            s_t = m["landmarks"]["head_tip"]["s"]
            return np.nonzero(np.abs(C.s - s_t) <= 0.02)[0]
        _p, ids, info = self.profile(FRAME_START + self.n_frames - 1)
        k = info["pieces"].index("F3")
        idx = np.nonzero(ids == k)[0]
        return np.concatenate([[idx[0] - 1], idx])

    def uv(self):
        pts, _ids, _info = self.profile(FRAME_START + self.n_frames - 1)
        s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1])))])
        u = s / s[-1]
        v = np.linspace(0.0, 1.0, self.n_v)
        return u, v


# ---------------------------------------------------------------------- Blender オブジェクト
def build_object(scene=None, n_frames=N_FRAMES_DEFAULT, taper="clip", H=11.0, profile_json=None,
                 name="SyntheticWave", u_mult=1, animate=True):
    """UV、頂点グループ 'crest_rim'、フレームごとのシェイプキーを持つメッシュオブジェクトを作る。
    キー k はシーンの FRAME_START + k フレームで厳密に1となる。(object, SyntheticWave) を返す。"""
    import bpy
    scene = scene or bpy.context.scene
    sw = SyntheticWave(n_frames, taper, H, profile_json, u_mult)
    v0 = sw.vertices(FRAME_START)
    me = bpy.data.meshes.new(name)
    me.from_pydata(v0.tolist(), [], sw.faces.tolist())
    me.update()
    # UV: U は最終姿勢の弧長方向、V は Y 方向
    u, v = sw.uv()
    uvl = me.uv_layers.new(name="UVMap")
    loop_vi = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", loop_vi)
    uv = np.stack([u[loop_vi % sw.n_u], v[loop_vi // sw.n_u]], axis=1).astype(np.float32)
    uvl.data.foreach_set("uv", uv.ravel())
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    vg = obj.vertex_groups.new(name="crest_rim")
    ru = sw.rim_u_indices()
    if ru.size:
        ids = (np.arange(sw.n_v)[:, None] * sw.n_u + ru[None, :]).ravel()
        vg.add([int(i) for i in ids], 1.0, "REPLACE")
    if animate and n_frames > 1:
        try:
            bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
        except Exception:
            pass
        obj.shape_key_add(name="Basis", from_mix=False)
        for k in range(1, n_frames):
            sk = obj.shape_key_add(name="f%03d" % (FRAME_START + k), from_mix=False)
            co = sw.vertices(FRAME_START + k).astype(np.float32)
            sk.data.foreach_set("co", co.ravel())
            f = FRAME_START + k
            sk.value = 0.0
            sk.keyframe_insert("value", frame=f - 1)
            sk.value = 1.0
            sk.keyframe_insert("value", frame=f)
            if k < n_frames - 1:
                sk.value = 0.0
                sk.keyframe_insert("value", frame=f + 1)
        scene.frame_start = FRAME_START
        scene.frame_end = FRAME_START + n_frames - 1
        scene.frame_set(FRAME_START)
    return obj, sw


# ---------------------------------------------------------------------- 輪郭 JSON の書出し
def export_contour_json(path=SYNTHETIC_CONTOUR_JSON, occluded_below_z=0.12, F=None):
    """解析的な最終断面を基準輪郭の形式 'gw.base_contour.v1' で書き出す。
    内側の弧の低い部分（Z < occluded_below_z）に 'completed_occluded' を付けて
    in_S7 = false とし、S7 の除外処理を検証する。"""
    F = F or gw_frame.get_frame()
    dense, _ids, info = profile_points(1.0, dense_ds=2e-4)
    C = pm.Curve(dense)
    # 画面の左端で切り取る
    i0 = int(np.nonzero(C.pts[:, 0] >= F.x_left)[0][0])
    s_left = np.interp(F.x_left, C.pts[i0 - 1:i0 + 1, 0], C.s[i0 - 1:i0 + 1])
    m = pm.measure_profile(dense)
    s_c = m["landmarks"]["crest"]["s"]
    s_t = m["landmarks"]["head_tip"]["s"]
    s_e = C.length
    sp = 2.0 * F.H_per_px

    def seg(name, jp, a, b):
        npt = max(2, int(round((b - a) / sp)) + 1)
        ph = C.at(np.linspace(a, b, npt))
        return name, jp, ph

    segs = [seg("back", "背", s_left, s_c), seg("head", "波頭", s_c, s_t),
            seg("inner_arc", "内側の弧", s_t, s_e)]
    # 解析的に求めた正確な接合点
    segs[0][2][-1] = info["crest"]
    segs[1][2][0] = info["crest"]
    segs[1][2][-1] = info["head_tip"]
    segs[2][2][0] = info["head_tip"]
    out_segs = []
    for name, jp, ph in segs:
        px = F.pts_H_to_px(ph)
        if name == "inner_arc":
            occl = ph[:, 1] < occluded_below_z
        else:
            occl = np.zeros(len(ph), bool)
        source = ["completed_occluded" if o else "traced" for o in occl]
        out_segs.append({"name": name, "jp": jp,
                         "points_px": [[round(float(a), 3), round(float(b), 3)] for a, b in px],
                         "points_H": [[round(float(a), 7), round(float(b), 7)] for a, b in ph],
                         "source": source, "in_S7": [not bool(o) for o in occl]})

    def lmk(pH):
        px = F.H_to_px(pH[0], pH[1])
        return {"px": [float(px[0]), float(px[1])], "H": [float(pH[0]), float(pH[1])]}

    tip = lmk(info["head_tip"])
    tip["direction_deg"] = float(m["phi_deg"])
    tip["direction_definition"] = ("gw.profile_metrics phi: direction of the chord of the top-side contour from "
                                   "(phi_skip_H + phi_len_H) to phi_skip_H of arc length before the head tip; "
                                   "exact analytic value here = -b = %.4f deg" % info["phi_exact_deg"])
    spec6 = [float(v) for v in F.pct_to_H(*gw_frame.SPEC_LANDMARKS_PCT["S6_claw_rightmost"])]
    doc = {
        "schema": "gw.base_contour.v1",
        "_comment": "SYNTHETIC fixture (analytic lines + arcs), NOT the painting. Written by tests/fixtures/make_synthetic_wave.py.",
        "image": {"path": None, "width": F.width_px, "height": F.height_px},
        "frame": {"crest_left_pct": F.crest_left_pct, "crest_top_pct": F.crest_top_pct, "height_pct": F.height_pct,
                  "frame_h_H": F.frame_h, "frame_w_H": F.frame_w, "x_left_H": F.x_left, "z_top_H": F.z_top},
        "order": "left frame edge -> crest -> head tip -> inner arc -> trough",
        "sample_spacing_px": 2.0,
        "segments": out_segs,
        "landmarks": {
            "crest": lmk(info["crest"]),
            "head_tip": tip,
            "inner_deepest": lmk(info["inner_deepest"]),
            "trough_level": {"y_px": float(F.H_to_px(0.0, 0.0)[1]), "top_pct": float(F.H_to_pct(0.0, 0.0)[1])},
            "claw_rightmost": {"px": [float(v) for v in F.H_to_px(*spec6)], "H": spec6,
                               "_comment": "not applicable to the synthetic wave; copy of spec S6"},
        },
        "remeasure": {"_comment": "not applicable to the synthetic fixture"},
        "analytic": {k: info[k] for k in ("crest", "head_tip", "inner_deepest", "o", "theta_pointwise_deg",
                                           "phi_exact_deg", "rim_thickness_H", "trough_end", "hem_x")},
    }
    paths.write_json(path, doc)
    return doc


# ---------------------------------------------------------------------- コマンド行からの実行
def main():
    ap = argparse.ArgumentParser(description="build the synthetic test wave")
    ap.add_argument("--frames", type=int, default=N_FRAMES_DEFAULT)
    ap.add_argument("--taper", default="clip", choices=["clip", "lift_clip", "zscale", "none"])
    ap.add_argument("--profile-json", default=None)
    ap.add_argument("--H", type=float, default=None)
    ap.add_argument("--out-blend", default=None)
    ap.add_argument("--no-json", action="store_true")
    args = bootstrap.parse_args(ap)
    H = args.H if args.H is not None else float(paths.param("WAVE_HEIGHT_M"))
    scene = bootstrap.reset_scene()
    obj, sw = build_object(scene, args.frames, args.taper, H, args.profile_json)
    bootstrap.log("synthetic wave: %d x %d = %d vertices, %d quads, %d frames, taper=%s, H=%.3f m"
                  % (sw.n_u, sw.n_v, sw.n_u * sw.n_v, len(sw.faces), args.frames, args.taper, H))
    if not args.no_json and not args.profile_json:
        export_contour_json()
        bootstrap.log("wrote", paths.norm(SYNTHETIC_CONTOUR_JSON))
    if args.out_blend:
        import bpy
        out = paths.ensure_parent(args.out_blend)
        from gw import silhouette
        silhouette.setup_cam_print(scene, H)
        bpy.ops.wm.save_as_mainfile(filepath=out)
        bootstrap.log("saved", out)
    bootstrap.finish(True, "make_synthetic_wave")


if __name__ == "__main__":
    main()
