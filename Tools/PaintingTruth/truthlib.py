# -*- coding: utf-8 -*-
"""PaintingTruth 共通処理（番号23「原画基準と評価器 v0」、修正2回目で高解像度原画へ移した）。

numpy と OpenCV だけを使う（matplotlib・scipy は使わない）。
画素座標は画素中心が整数の配列添字系（x 右、y 下）。
参照画像（ref）は v0.2 から Met_JP1847_DP130155.jpg（3859×2594）。旧原画 Met_JP1847.jpg（1200×807）の
座標は「旧参照 px（legacy）」と呼び、painting_truth.json の reference.px_per_legacy_ref_px 倍で高解像度 px に換える。
"""
import hashlib
import json
import math
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SPEC_PATH = os.path.join(HERE, "painting_truth.json")
MANUAL_PATH = os.path.join(HERE, "manual_annotations.json")
TARGET_DIR = os.path.join(HERE, "targets")
BUILD_DIR = os.path.join(HERE, "build")


# ---------------------------------------------------------------- 入出力
def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_rel(path):
    """リポジトリ根からの相対パス。根の外（別ドライブを含む）は絶対パスをそのまま返す。"""
    ap = os.path.abspath(path)
    try:
        rel = os.path.relpath(ap, REPO)
    except ValueError:  # Windows で別ドライブ
        return ap.replace("\\", "/")
    if rel == ".." or rel.startswith(".." + os.sep):
        return ap.replace("\\", "/")
    return rel.replace("\\", "/")


def repo_abs(rel):
    return os.path.join(REPO, rel.replace("/", os.sep))


def imread_rgb(path):
    """8bit RGB で読む（16bit・アルファは捨てる）。"""
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError("画像を読めません: " + path)
    return img[:, :, ::-1].copy()


def imwrite(path, img_rgb_or_gray):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img = img_rgb_or_gray
    if img.ndim == 3:
        img = img[:, :, ::-1]
    ok, buf = cv2.imencode(os.path.splitext(path)[1], img)
    if not ok:
        raise IOError("画像を書けません: " + path)
    buf.tofile(path)


def load_spec():
    spec = load_json(SPEC_PATH)
    ref = repo_abs(spec["reference"]["path"])
    got = sha256_file(ref)
    if got != spec["reference"]["sha256"]:
        raise RuntimeError("原画の SHA-256 が凍結値と違います: " + got)
    return spec


def load_manual():
    return load_json(MANUAL_PATH)


# ---------------------------------------------------------------- 色
_M_RGB2XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                       [0.2126729, 0.7151522, 0.0721750],
                       [0.0193339, 0.1191920, 0.9503041]])
_WHITE_D65 = np.array([0.95047, 1.0, 1.08883])


def srgb8_to_lab(rgb):
    """8bit sRGB（0..255）→ CIELAB（D65）。float64。"""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _M_RGB2XYZ.T
    t = xyz / _WHITE_D65
    e = 216.0 / 24389.0
    k = 24389.0 / 27.0
    f = np.where(t > e, np.cbrt(t), (k * t + 16.0) / 116.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def lab_to_srgb8(lab):
    """CIELAB（D65）→ 8bit sRGB（丸め・範囲外は切り詰め）。"""
    lab = np.asarray(lab, dtype=np.float64)
    fy = (lab[..., 0] + 16.0) / 116.0
    fx = fy + lab[..., 1] / 500.0
    fz = fy - lab[..., 2] / 200.0
    e = 216.0 / 24389.0
    k = 24389.0 / 27.0

    def finv(f):
        return np.where(f ** 3 > e, f ** 3, (116.0 * f - 16.0) / k)

    xyz = np.stack([finv(fx), np.where(lab[..., 0] > k * e, fy ** 3, lab[..., 0] / k), finv(fz)], -1) * _WHITE_D65
    lin = xyz @ np.linalg.inv(_M_RGB2XYZ).T
    lin = np.clip(lin, 0.0, 1.0)
    c = np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1.0 / 2.4) - 0.055)
    return np.clip(np.round(c * 255.0), 0, 255).astype(np.uint8)


def ciede2000(lab1, lab2, kL=1.0, kC=1.0, kH=1.0):
    """CIEDE2000（Sharma, Wu, Dalal 2005 の実装注意に従う）。配列対応。"""
    lab1 = np.asarray(lab1, dtype=np.float64)
    lab2 = np.asarray(lab2, dtype=np.float64)
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cb = (C1 + C2) / 2.0
    Cb7 = Cb ** 7
    G = 0.5 * (1.0 - np.sqrt(Cb7 / (Cb7 + 25.0 ** 7)))
    a1p = (1.0 + G) * a1
    a2p = (1.0 + G) * a2
    C1p = np.hypot(a1p, b1)
    C2p = np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360.0
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360.0
    h1p = np.where((b1 == 0) & (a1p == 0), 0.0, h1p)
    h2p = np.where((b2 == 0) & (a2p == 0), 0.0, h2p)
    dLp = L2 - L1
    dCp = C2p - C1p
    zero = (C1p * C2p) == 0
    dh = h2p - h1p
    dh = np.where(dh > 180.0, dh - 360.0, np.where(dh < -180.0, dh + 360.0, dh))
    dh = np.where(zero, 0.0, dh)
    dHp = 2.0 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2.0))
    Lbp = (L1 + L2) / 2.0
    Cbp = (C1p + C2p) / 2.0
    hs = h1p + h2p
    hbp = np.where(np.abs(h1p - h2p) <= 180.0, hs / 2.0,
                   np.where(hs < 360.0, (hs + 360.0) / 2.0, (hs - 360.0) / 2.0))
    hbp = np.where(zero, hs, hbp)
    T = (1.0 - 0.17 * np.cos(np.radians(hbp - 30.0)) + 0.24 * np.cos(np.radians(2.0 * hbp))
         + 0.32 * np.cos(np.radians(3.0 * hbp + 6.0)) - 0.20 * np.cos(np.radians(4.0 * hbp - 63.0)))
    dtheta = 30.0 * np.exp(-(((hbp - 275.0) / 25.0) ** 2))
    Cbp7 = Cbp ** 7
    RC = 2.0 * np.sqrt(Cbp7 / (Cbp7 + 25.0 ** 7))
    SL = 1.0 + 0.015 * (Lbp - 50.0) ** 2 / np.sqrt(20.0 + (Lbp - 50.0) ** 2)
    SC = 1.0 + 0.045 * Cbp
    SH = 1.0 + 0.015 * Cbp * T
    RT = -np.sin(np.radians(2.0 * dtheta)) * RC
    tL = dLp / (kL * SL)
    tC = dCp / (kC * SC)
    tH = dHp / (kH * SH)
    return np.sqrt(tL ** 2 + tC ** 2 + tH ** 2 + RT * tC * tH)


# ---------------------------------------------------------------- 画面写像
class FrameMap:
    """参照画像（v0.2 は 3859×2594）と表示フレーム（1920×1080）の写像。倍率は縦横同じ（等方）。"""

    def __init__(self, spec):
        d = spec["display_frame"]
        self.W = int(d["width"])
        self.H = int(d["height"])
        self.rw = int(spec["reference"]["width"])
        self.rh = int(spec["reference"]["height"])
        self.s = float(d["scale"])
        self.ox = float(d["offset_x"])
        self.oy = float(d["offset_y"])
        self.x0, self.x1 = d["scored_columns"]
        # 縮小（s < 1）のときは ss×ss の超標本化格子へ双線形で写してから ss×ss 平均する（面積平均の近似）。
        self.ss = int(d.get("downsample_supersample", 1))
        # 添字系での順写像 x_d = s*x_r + tx
        self.tx = 0.5 * self.s - 0.5 + self.ox
        self.ty = 0.5 * self.s - 0.5 + self.oy
        self.M = np.array([[self.s, 0.0, self.tx], [0.0, self.s, self.ty]])
        self.Minv = np.array([[1.0 / self.s, 0.0, -self.tx / self.s], [0.0, 1.0 / self.s, -self.ty / self.s]])

    def ref_to_disp(self, p):
        p = np.asarray(p, dtype=np.float64)
        return np.stack([self.s * p[..., 0] + self.tx, self.s * p[..., 1] + self.ty], -1)

    def disp_to_ref(self, p):
        p = np.asarray(p, dtype=np.float64)
        return np.stack([(p[..., 0] - self.tx) / self.s, (p[..., 1] - self.ty) / self.s], -1)

    def warp_to_disp(self, img, interp=cv2.INTER_LINEAR):
        """参照 → 表示。縮小のときは超標本化して平均する（uint8 は四捨五入して uint8 に戻す）。"""
        k = self.ss
        if self.s >= 1.0 or k <= 1 or interp == cv2.INTER_NEAREST:
            return cv2.warpAffine(img, self.M, (self.W, self.H), flags=interp, borderMode=cv2.BORDER_REPLICATE)
        Mk = np.array([[k * self.s, 0.0, k * (self.tx + 0.5) - 0.5], [0.0, k * self.s, k * (self.ty + 0.5) - 0.5]])
        src = np.asarray(img)
        big = cv2.warpAffine(src.astype(np.float32), Mk, (self.W * k, self.H * k), flags=interp, borderMode=cv2.BORDER_REPLICATE)
        sh = (self.H, k, self.W, k) + big.shape[2:]
        out = big.reshape(sh).mean(axis=(1, 3), dtype=np.float64)
        if src.dtype == np.uint8:
            return np.clip(np.round(out), 0, 255).astype(np.uint8)
        return out

    def warp_to_ref(self, img, interp=cv2.INTER_LINEAR):
        return cv2.warpAffine(img, self.Minv, (self.rw, self.rh), flags=interp, borderMode=cv2.BORDER_REPLICATE)

    def scored(self, pts):
        return (pts[:, 0] >= self.x0) & (pts[:, 0] <= self.x1)


# ---------------------------------------------------------------- カメラ
def cam_basis(spec):
    c = spec["painting_cam"]
    pos = np.array(c["position"], dtype=np.float64)
    f = np.array(c["target"], dtype=np.float64) - pos
    f /= np.linalg.norm(f)
    up = np.array(c["up"], dtype=np.float64)
    r = np.cross(up, f)
    r /= np.linalg.norm(r)
    u = np.cross(f, r)
    return pos, r, u, f


def cam_euler_deg(spec):
    """Unity の eulerAngles（ZXY 順、x=ピッチ, y=ヨー）。ロールは LookAt(up=Y) で 0。"""
    _, r, u, f = cam_basis(spec)
    pitch = -math.degrees(math.asin(max(-1.0, min(1.0, f[1]))))
    yaw = math.degrees(math.atan2(f[0], f[2]))
    roll = math.degrees(math.atan2(r[1], u[1])) + 0.0
    return [pitch % 360.0, yaw % 360.0, roll]


def project_world(spec, P):
    """世界座標 → (表示 px x, y, 視点深度 z, viewport vx, vy)。"""
    c = spec["painting_cam"]
    W = spec["display_frame"]["width"]
    H = spec["display_frame"]["height"]
    pos, r, u, f = cam_basis(spec)
    d = np.asarray(P, dtype=np.float64) - pos
    cx, cy, cz = d @ r, d @ u, d @ f
    t = math.tan(math.radians(c["vertical_fov_deg"]) / 2.0)
    vx = 0.5 + 0.5 * (cx / cz) / (t * c["aspect"])
    vy = 0.5 + 0.5 * (cy / cz) / t
    return vx * W - 0.5, (1.0 - vy) * H - 0.5, cz, vx, vy


def cam_matrices(spec):
    """Unity 互換の worldToCameraMatrix と projectionMatrix（OpenGL 規約、-Z 前方）。"""
    c = spec["painting_cam"]
    pos, r, u, f = cam_basis(spec)
    view = np.eye(4)
    view[0, :3], view[1, :3], view[2, :3] = r, u, -f
    view[:3, 3] = -view[:3, :3] @ pos
    n, fa = c["near"], c["far"]
    t = math.tan(math.radians(c["vertical_fov_deg"]) / 2.0)
    proj = np.zeros((4, 4))
    proj[0, 0] = 1.0 / (t * c["aspect"])
    proj[1, 1] = 1.0 / t
    proj[2, 2] = -(fa + n) / (fa - n)
    proj[2, 3] = -2.0 * fa * n / (fa - n)
    proj[3, 2] = -1.0
    return view, proj


# ---------------------------------------------------------------- 形態処理
def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def poly_mask(shape, pts):
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.round(np.asarray(pts, np.float64)).astype(np.int32)], 1)
    return m.astype(bool)


def fill_small_enclosed(fg, area_max):
    """fg 以外の連結成分のうち画像端に触れず面積 < area_max のものを fg にする。"""
    out = fg.copy()
    n, lab, st, _ = cv2.connectedComponentsWithStats((~fg).astype(np.uint8), connectivity=8)
    H, W = fg.shape
    for i in range(1, n):
        x, y, w, h, A = st[i]
        if x == 0 or y == 0 or x + w == W or y + h == H:
            continue
        if A < area_max:
            out[lab == i] = True
    return out


def barrier_lines_mask(shape, lines):
    """手で引いた障壁の折れ線（参照 px、画素中心 = 整数）を太さ width_ref_px の線として塗る。"""
    m = np.zeros(shape, np.uint8)
    for ln in lines:
        P = np.round(np.asarray(ln["points"], np.float64) * 16.0).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(m, [P], False, 1, int(ln["width_ref_px"]), cv2.LINE_8, shift=4)
    return m.astype(bool)


def segment_sky(lab, p, fill_polys=(), barrier_lines=()):
    """空マスク（参照解像度）。色と勾配の障壁で上端から塗りつぶし、境界を局所の空の明度で 1〜2 px 詰める。

    barrier_lines は原画の藍線が途切れた所を閉じる手動の障壁（manual_annotations.json の barriers_ref）。
    色の障壁と同じ扱いにし、塗りつぶしも境界の詰めも越えない。描画の評価（色モード）では使わない。
    p["barrier_dilate_ref_px"]（v0.2 で追加、既定 0）が正なら、塗りつぶしの前に障壁全体をその半径の円で膨らませ、
    線の端どうしの狭い途切れ（幅 < 2r）を閉じる。境界の詰め（refine）は膨らませる前の色の障壁で止まるので、
    境界は線の外縁へ戻る（refine_iterations は膨らませた分を含めて決める）。
    """
    L, a, b = lab[..., 0].astype(np.float32), lab[..., 1].astype(np.float32), lab[..., 2].astype(np.float32)
    Ls = cv2.GaussianBlur(L, (0, 0), p["blur_sigma_L"])
    gx = cv2.Sobel(Ls, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(Ls, cv2.CV_32F, 0, 1, ksize=3)
    g = np.hypot(gx, gy) / 8.0
    colour_barrier = (b < p["barrier_b_below"]) | (L < p["barrier_L_below"])
    if len(barrier_lines):
        colour_barrier |= barrier_lines_mask(L.shape, barrier_lines)
    barrier = colour_barrier | (g > p["gradient_threshold_L_per_px"])
    r = int(p.get("barrier_dilate_ref_px", 0))
    if r > 0:
        barrier = cv2.dilate(barrier.astype(np.uint8), disk(r)).astype(bool)
    n, cc = cv2.connectedComponents((~barrier).astype(np.uint8), connectivity=4)
    y = int(p["seed_row_ref"])
    x0, x1 = p["seed_x_ref"]
    seeds = np.unique(cc[y, x0:x1 + 1])
    seeds = seeds[seeds != 0]
    sky = np.isin(cc, seeds)
    w = int(p["refine_window_ref_px"])
    for _ in range(int(p["refine_iterations"])):
        sf = sky.astype(np.float32)
        s = cv2.boxFilter(L * sf, -1, (w, w), normalize=False)
        cnt = cv2.boxFilter(sf, -1, (w, w), normalize=False)
        meanL = s / np.maximum(cnt, 1.0)
        ring = cv2.dilate(sky.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & ~sky
        ring &= ~colour_barrier & (cnt > 0) & (np.abs(L - meanL) <= p["refine_L_tolerance"])
        sky |= ring
    for poly in fill_polys:
        sky |= poly_mask(sky.shape, poly)
    sky = fill_small_enclosed(sky, p["small_enclosed_area_ref_px"])
    return sky


def envelope_water(water, zone, p):
    """claw_zone 内だけ閉じ→開き→平滑化した水マスクに置き換える（爪なし包絡）。

    計算は claw_zone の外接矩形を余白（閉じ＋開きの半径＋平滑 σ の 5 倍）付きで切り出して行う（高解像度での速度対策）。
    画像端では全体で計算した場合と同じく、切り出しの縁も画像端に一致させる。
    """
    rc, ro, sg = int(p["close_radius_ref_px"]), int(p["open_radius_ref_px"]), float(p["smooth_sigma_ref_px"])
    ys, xs = np.nonzero(zone)
    m = rc + ro + int(math.ceil(5 * sg)) + 4
    y0, y1 = max(0, ys.min() - m), min(zone.shape[0], ys.max() + m + 1)
    x0, x1 = max(0, xs.min() - m), min(zone.shape[1], xs.max() + m + 1)
    w = water[y0:y1, x0:x1].astype(np.uint8)
    w = cv2.morphologyEx(w, cv2.MORPH_CLOSE, disk(rc))
    w = cv2.morphologyEx(w, cv2.MORPH_OPEN, disk(ro))
    ws = cv2.GaussianBlur(w.astype(np.float32), (0, 0), sg) > 0.5
    out = water.copy()
    sub = zone[y0:y1, x0:x1]
    out[y0:y1, x0:x1] = np.where(sub, ws, water[y0:y1, x0:x1])
    return out


# ---------------------------------------------------------------- 境界点
def iso_points(f, level=0.5):
    """被覆率 f の等値線点（画素中心格子の辺交点 + 2 交点セルの中点）。(N,2) x,y。"""
    f = np.asarray(f, dtype=np.float64)
    v = f - level
    s = v >= 0
    pts = []
    # 横辺
    hx = s[:, :-1] != s[:, 1:]
    iy, ix = np.nonzero(hx)
    t = v[iy, ix] / (v[iy, ix] - v[iy, ix + 1])
    hpx = np.stack([ix + t, iy.astype(np.float64)], -1)
    pts.append(hpx)
    # 縦辺
    vx = s[:-1, :] != s[1:, :]
    iy2, ix2 = np.nonzero(vx)
    t2 = v[iy2, ix2] / (v[iy2, ix2] - v[iy2 + 1, ix2])
    vpx = np.stack([ix2.astype(np.float64), iy2 + t2], -1)
    pts.append(vpx)
    # セル中点（交点がちょうど 2 個のセル）
    H, W = f.shape
    X = np.zeros((H - 1, W - 1))
    Y = np.zeros((H - 1, W - 1))
    C = np.zeros((H - 1, W - 1), np.int32)
    def acc(mask, px, py):
        nonlocal X, Y, C
        X += np.where(mask, px, 0.0)
        Y += np.where(mask, py, 0.0)
        C += mask
    hxf = np.zeros((H, W - 1))
    hxf[iy, ix] = hpx[:, 0]
    vyf = np.zeros((H - 1, W))
    vyf[iy2, ix2] = vpx[:, 1]
    jj = np.arange(W - 1)[None, :].astype(np.float64)
    ii = np.arange(H - 1)[:, None].astype(np.float64)
    acc(hx[:-1, :], hxf[:-1, :], ii + 0.0 * jj)          # 上辺
    acc(hx[1:, :], hxf[1:, :], ii + 1.0 + 0.0 * jj)      # 下辺
    acc(vx[:, :-1], jj + 0.0 * ii, vyf[:, :-1])          # 左辺
    acc(vx[:, 1:], jj + 1.0 + 0.0 * ii, vyf[:, 1:])      # 右辺
    two = C == 2
    mid = np.stack([X[two] / 2.0, Y[two] / 2.0], -1)
    pts.append(mid)
    return np.concatenate(pts, 0)


def nearest(query, train):
    """各 query 点に最も近い train 点（厳密な総当たり、OpenCV BFMatcher）。距離は float64 で再計算。"""
    query = np.asarray(query, dtype=np.float64)
    train = np.asarray(train, dtype=np.float64)
    if len(query) == 0:
        return np.zeros(0), np.zeros(0, np.int64)
    if len(train) == 0:
        return np.full(len(query), np.inf), np.full(len(query), -1, np.int64)
    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
    idx = np.empty(len(query), np.int64)
    step = 20000
    for k in range(0, len(query), step):
        q = query[k:k + step]
        ms = bf.match(q.astype(np.float32), train.astype(np.float32))
        qi = np.fromiter((m.queryIdx for m in ms), np.int64, len(ms))
        ti = np.fromiter((m.trainIdx for m in ms), np.int64, len(ms))
        idx[k + qi] = ti
    d = np.linalg.norm(query - train[idx], axis=1)
    return d, idx


def labelled_hausdorff(truth_pts, truth_sel, render_pts):
    """Voronoi 割当つき対称 Hausdorff。truth_sel は対象に属する真値点の真偽配列。"""
    T = truth_pts[truth_sel]
    out = {"n_truth": int(len(T)), "n_render_assigned": 0}
    if len(T) == 0:
        out["error"] = "真値点なし"
        return out, None, None
    if len(render_pts) == 0:
        out.update(max_px=float("inf"), p95_px=float("inf"), p50_px=float("inf"),
                   max_truth_to_render=float("inf"), max_render_to_truth=None, error="描画側の境界なし")
        return out, None, None
    d_tr, i_tr = nearest(T, render_pts)
    d_all, i_all = nearest(render_pts, truth_pts)
    assigned = truth_sel[i_all]
    d_rt = d_all[assigned]
    both = np.concatenate([d_tr, d_rt])
    out.update(
        n_render_assigned=int(assigned.sum()),
        max_px=float(both.max()),
        p95_px=float(np.percentile(both, 95)),
        p50_px=float(np.percentile(both, 50)),
        max_truth_to_render=float(d_tr.max()),
        max_render_to_truth=float(d_rt.max()) if len(d_rt) else None,
    )
    worst_t = T[int(np.argmax(d_tr))]
    worst = worst_t
    if len(d_rt) and d_rt.max() > d_tr.max():
        worst = render_pts[assigned][int(np.argmax(d_rt))]
    return out, (d_all, assigned), worst


def resample_polyline(P, step):
    P = np.asarray(P, dtype=np.float64)
    if len(P) < 2:
        return P
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(2, int(math.floor(s[-1] / step)) + 1)
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], -1)


def median_lab(lab_img, mask):
    v = lab_img[mask]
    if len(v) == 0:
        return None
    return np.median(v, axis=0)


def erode(mask, r):
    if r <= 0:
        return mask
    return cv2.erode(mask.astype(np.uint8), disk(r)).astype(bool)


# ---------------------------------------------------------------- Sharma 2005 表 1（34 組）
SHARMA2005 = [
    (50.0000, 2.6772, -79.7751, 50.0000, 0.0000, -82.7485, 2.0425),
    (50.0000, 3.1571, -77.2803, 50.0000, 0.0000, -82.7485, 2.8615),
    (50.0000, 2.8361, -74.0200, 50.0000, 0.0000, -82.7485, 3.4412),
    (50.0000, -1.3802, -84.2814, 50.0000, 0.0000, -82.7485, 1.0000),
    (50.0000, -1.1848, -84.8006, 50.0000, 0.0000, -82.7485, 1.0000),
    (50.0000, -0.9009, -85.5211, 50.0000, 0.0000, -82.7485, 1.0000),
    (50.0000, 0.0000, 0.0000, 50.0000, -1.0000, 2.0000, 2.3669),
    (50.0000, -1.0000, 2.0000, 50.0000, 0.0000, 0.0000, 2.3669),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0009, 7.1792),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0010, 7.1792),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0011, 7.2195),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0012, 7.2195),
    (50.0000, -0.0010, 2.4900, 50.0000, 0.0009, -2.4900, 4.8045),
    (50.0000, -0.0010, 2.4900, 50.0000, 0.0010, -2.4900, 4.8045),
    (50.0000, -0.0010, 2.4900, 50.0000, 0.0011, -2.4900, 4.7461),
    (50.0000, 2.5000, 0.0000, 50.0000, 0.0000, -2.5000, 4.3065),
    (50.0000, 2.5000, 0.0000, 73.0000, 25.0000, -18.0000, 27.1492),
    (50.0000, 2.5000, 0.0000, 61.0000, -5.0000, 29.0000, 22.8977),
    (50.0000, 2.5000, 0.0000, 56.0000, -27.0000, -3.0000, 31.9030),
    (50.0000, 2.5000, 0.0000, 58.0000, 24.0000, 15.0000, 19.4535),
    (50.0000, 2.5000, 0.0000, 50.0000, 3.1736, 0.5854, 1.0000),
    (50.0000, 2.5000, 0.0000, 50.0000, 3.2972, 0.0000, 1.0000),
    (50.0000, 2.5000, 0.0000, 50.0000, 1.8634, 0.5757, 1.0000),
    (50.0000, 2.5000, 0.0000, 50.0000, 3.2592, 0.3350, 1.0000),
    (60.2574, -34.0099, 36.2677, 60.4626, -34.1751, 39.4387, 1.2644),
    (63.0109, -31.0961, -5.8663, 62.8187, -29.7946, -4.0864, 1.2630),
    (61.2901, 3.7196, -5.3901, 61.4292, 2.2480, -4.9620, 1.8731),
    (35.0831, -44.1164, 3.7933, 35.0232, -40.0716, 1.5901, 1.8645),
    (22.7233, 20.0904, -46.6940, 23.0331, 14.9730, -42.5619, 2.0373),
    (36.4612, 47.8580, 18.3852, 36.2715, 50.5065, 21.2231, 1.4146),
    (90.8027, -2.0831, 1.4410, 91.1528, -1.6435, 0.0447, 1.4441),
    (90.9257, -0.5406, -0.9208, 88.6381, -0.8985, -0.7239, 1.5381),
    (6.7747, -0.2908, -2.4247, 5.8714, -0.0985, -2.2286, 0.6377),
    (2.0776, 0.0795, -1.1350, 0.9033, -0.0636, -0.5514, 0.9082),
]


# ---------------------------------------------------------------- 真値と描画で共通の領域処理
def boundary_points(cov, spec, fmap):
    """被覆率 → 平滑化 → 0.5 等値線点（採点列の内側だけ）。"""
    sig = float(spec["scoring"]["contour"]["boundary_smoothing_sigma_px"])
    f = cv2.GaussianBlur(np.asarray(cov, np.float64), (0, 0), sig) if sig > 0 else cov
    pts = iso_points(f, 0.5)
    return pts[fmap.scored(pts)]


def sky_dark_mask(lab_disp, sky_cov, L_mid, p, fmap):
    """暗い空（水平線際）: 空の被覆率 > 0.5 かつ平滑化した L* < L_mid。表示フレームで計算。

    飛沫の白点や題箋の文字が明暗境界に入らないよう、L* を σ で平滑化し、参照 y >= min_y_ref の帯に限り、
    面積の小さい島と穴を除く。
    """
    sky = (np.asarray(sky_cov) > 0.5).astype(np.float32)
    sg = float(p["smooth_sigma_display_px"])
    # 空の画素だけで平滑化する（正規化畳み込み）。波の暗い藍が空側へにじまないようにする。
    num = cv2.GaussianBlur(np.asarray(lab_disp[..., 0], np.float32) * sky, (0, 0), sg)
    den = cv2.GaussianBlur(sky, (0, 0), sg)
    Ls = num / np.maximum(den, 1e-6)
    m = (sky > 0.5) & (Ls < L_mid)
    y0 = fmap.s * float(p["min_y_ref"]) + fmap.ty
    m[: int(math.ceil(y0)), :] = False
    a = int(p["min_component_display_px"])
    m = fill_small_enclosed(m, 10 ** 9)      # 閉じた穴（飛沫の白点など）はすべて埋める（面積しきい値の揺れを避ける）
    m = ~fill_small_enclosed(~m, a)          # 小さい島を消す
    return m.astype(np.float64)


def ochre_mask(lab_ref, sky_ref, p):
    L = cv2.GaussianBlur(lab_ref[..., 0].astype(np.float32), (0, 0), p["blur_sigma"])
    b = cv2.GaussianBlur(lab_ref[..., 2].astype(np.float32), (0, 0), p["blur_sigma"])
    return (b > p["b_min"]) & (L >= p["L_range"][0]) & (L <= p["L_range"][1]) & ~sky_ref


def boat_mask(ochre_ref, roi_pts, p=None):
    """船ごとの範囲の中の黄土色。p は painting_truth.json の extraction.boat（v0.1 の値は閉じ 2・穴 2000・最小 30 旧参照 px）。"""
    p = p or {"close_radius_ref_px": 2, "fill_enclosed_area_ref_px": 2000, "min_component_ref_px": 30}
    m = ochre_ref & poly_mask(ochre_ref.shape, roi_pts)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, disk(int(p["close_radius_ref_px"]))).astype(bool)
    m = fill_small_enclosed(m, int(p["fill_enclosed_area_ref_px"]))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    keep = np.zeros_like(m)
    for i in range(1, n):
        if st[i, 4] >= int(p["min_component_ref_px"]):
            keep |= lab == i
    return keep


def ref_mask_to_cov(mask_ref, fmap):
    return np.asarray(fmap.warp_to_disp(mask_ref.astype(np.float32), cv2.INTER_LINEAR), np.float64)


def save_cov_png(path, cov):
    imwrite(path, np.clip(np.round(np.asarray(cov) * 65535.0), 0, 65535).astype(np.uint16))


def load_cov_png(path):
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise IOError(path)
    return img.astype(np.float64) / 65535.0


def painting_display(spec, fmap):
    """原画を表示フレームへ（v0.2：3×3 超標本化の双線形＋平均で縮小）。決定的に再生成できる。

    計測用は黒帯部分を端の画素で延長する（BORDER_REPLICATE）。黒帯は採点しないが、
    延長しておくと原画の左右端に人工の境界ができない。見せる図では黒帯を暗くする。
    """
    ref = imread_rgb(repo_abs(spec["reference"]["path"]))
    disp = fmap.warp_to_disp(ref, cv2.INTER_LINEAR)
    return ref, disp


def outline_normals(P, sky_img, probe=2.0):
    """折れ線 P の単位法線（水側＝空の被覆率が下がる向き）。sky_img は P と同じ座標系の空の被覆率（0..1）。"""
    P = np.asarray(P, np.float64)
    tan = np.gradient(P, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-9)
    nrm = np.stack([-tan[:, 1], tan[:, 0]], -1)
    s = np.asarray(sky_img, np.float32)

    def at(Q):
        return cv2.remap(s, Q[:, 0].astype(np.float32).reshape(1, -1), Q[:, 1].astype(np.float32).reshape(1, -1),
                         cv2.INTER_LINEAR).ravel()
    flip = at(P + probe * nrm) > at(P - probe * nrm)
    nrm[flip] *= -1
    return nrm


def line_width_profile(L_img, P, nrm, p):
    """藍の輪郭線の幅（半深さ全幅）。P は空境界（線の外縁）上の点、nrm は水側への単位法線。

    各点で法線に沿って L* を step 間隔で標本化し（双線形）、空側 [-a, -a/2] の中央値を空の明度 Ls、[-a/2, b] の最小を
    線の芯 Lmin とする。深さ Ls − Lmin が min_depth 未満なら「線なし」。しきい T = Ls − 深さ/2 を下回ってから再び上回るまでの
    長さ（線形補間）を幅とする。b までに上回らない点は「線が暗い面に続く（merged）」として除く。p の長さの単位は L_img の px。
    戻り値: dict（width、t_in、t_out、depth は該当しない点で nan、reason は 0=測定、1=線なし、2=merged）。
    """
    a, b, st = float(p["sky_side"]), float(p["max_width"]), float(p["step"])
    ts = np.arange(-a, b + 1e-9, st)
    P = np.asarray(P, np.float64)
    Q = P[:, None, :] + ts[None, :, None] * np.asarray(nrm, np.float64)[:, None, :]
    img = np.asarray(L_img, np.float32)
    v = cv2.remap(img, Q[..., 0].astype(np.float32), Q[..., 1].astype(np.float32), cv2.INTER_LINEAR,
                  borderMode=cv2.BORDER_REPLICATE).astype(np.float64)
    n = len(P)
    out = {k: np.full(n, np.nan) for k in ("width", "t_in", "t_out", "depth")}
    out["reason"] = np.zeros(n, np.int8)
    i_half = int(np.searchsorted(ts, -a / 2.0))
    Ls = np.median(v[:, :max(1, i_half)], axis=1)
    for i in range(n):
        seg = v[i, i_half:]
        k = int(np.argmin(seg))
        Lmin = seg[k]
        depth = Ls[i] - Lmin
        if depth < float(p["min_depth"]):
            out["reason"][i] = 1
            continue
        T = Ls[i] - depth / 2.0
        below = seg < T
        j0 = int(np.argmax(below))  # 最初に T を下回る添字（k 以前に必ずある）
        after = np.flatnonzero(~below[k:])
        if len(after) == 0:
            out["reason"][i] = 2
            continue
        j1 = k + int(after[0])       # 芯の後で最初に T 以上へ戻る添字
        def cross(j):  # seg[j-1] と seg[j] の間の T の交点（ts 上）
            if j == 0:
                return ts[i_half]
            y0, y1 = seg[j - 1], seg[j]
            f = (T - y0) / (y1 - y0) if y1 != y0 else 0.5
            return ts[i_half + j - 1] + f * st
        tin, tout = cross(j0), cross(j1)
        out["width"][i], out["t_in"][i], out["t_out"][i], out["depth"][i] = tout - tin, tin, tout, depth
    return out


def poly_to_disp(fmap, pts_ref):
    return fmap.ref_to_disp(np.asarray(pts_ref, np.float64))


def point_in_poly(pts, poly, margin=0.0):
    """pts が多角形の内側で、辺から margin px より離れているか。"""
    poly = np.asarray(poly, np.float32)
    out = np.empty(len(pts), bool)
    for i, p in enumerate(pts):
        d = cv2.pointPolygonTest(poly, (float(p[0]), float(p[1])), True)
        out[i] = d > margin
    return out


def lab_to_srgb8_best(lab):
    """CIELAB → ΔE00 が最小になる 8bit sRGB（丸め値の ±1 近傍を総当たり）。"""
    lab = np.asarray(lab, np.float64)
    c0 = lab_to_srgb8(lab).astype(int)
    best, bd = c0, None
    for dr in (-1, 0, 1):
        for dg in (-1, 0, 1):
            for db in (-1, 0, 1):
                c = np.clip(c0 + [dr, dg, db], 0, 255)
                d = float(ciede2000(srgb8_to_lab(c), lab))
                if bd is None or d < bd:
                    best, bd = c, d
    return best.astype(np.uint8), bd


def save_png_reserved(path, rgb, reserved):
    """記録用の重ね図を 256 色 PNG で保存する（容量対策。測定には使わない）。

    背景から 256 - len(reserved) 色を取り、線と文字の色（reserved）はそのまま残す。
    """
    from PIL import Image
    reserved = [tuple(int(v) for v in c) for c in reserved]
    n = 256 - len(reserved)
    base = Image.fromarray(np.ascontiguousarray(rgb)).quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = base.getpalette()[: 3 * n]
    for c in reserved:
        pal += list(c)
    pimg = Image.new("P", (1, 1))
    pimg.putpalette(pal + [0] * (768 - len(pal)))
    out = Image.fromarray(np.ascontiguousarray(rgb)).quantize(palette=pimg, dither=Image.Dither.NONE)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    out.save(path, optimize=True)
