"""numpy と bpy のみを使う画像の入出力。この環境では PIL / cv2 を使わない。

このプロジェクトでの配列の約束:
    uint8、形は (行, 列[, チャンネル])、行は上から下、チャンネルは RGB(A)。
    arr[y, x] は連続的な画素座標で中心が (x + 0.5, y + 0.5) の画素。

読込: load_image_rgb / load_image_rgba は bpy.data.images を経由する（JPEG、PNG、WebP など）。
      8ビット画像では Blender が保存時のバイト値を保ち、.pixels は下から上の RGBA で
      バイト値 / 255 の浮動小数値を返す。この経路では色管理は適用されない。
      tests/selftest_foundation.py で、255 倍した値が float32 精度内で整数になり、
      save_png で書いた PNG をビット単位で同じ値として再読込できることを確認した。
書込: save_png は Python / numpy のみで PNG を符号化する（zlib + struct）。
      色管理、表示変換、ディザ処理は値を変えない。read_png は対応する復号器で、
      8ビット・非インターレース・非パレットの PNG を Blender なしで厳密に往復確認できる。
"""
import os
import struct
import zlib

import numpy as np

from . import paths

last_load_info = {}


# ------------------------------------------------------------------ 補助処理
def _as_u8(arr):
    a = np.asarray(arr)
    if a.dtype == np.bool_:
        return a.astype(np.uint8) * 255
    if a.dtype != np.uint8:
        raise TypeError("expected a uint8 (or bool) array, got %s; convert explicitly" % a.dtype)
    return a


def to_rgb(arr):
    """gray (h,w)、(h,w,1)、RGBA (h,w,4)、RGB を、RGB uint8 (h,w,3) に変換する。RGBA のアルファ値は除く。"""
    a = _as_u8(arr)
    if a.ndim == 2:
        return np.repeat(a[:, :, None], 3, axis=2)
    if a.ndim == 3 and a.shape[2] == 1:
        return np.repeat(a, 3, axis=2)
    if a.ndim == 3 and a.shape[2] == 3:
        return a
    if a.ndim == 3 and a.shape[2] == 4:
        return np.ascontiguousarray(a[:, :, :3])
    raise ValueError("unsupported image shape %r" % (a.shape,))


def to_gray(arr):
    """RGB または RGBA の uint8 画像を、Rec.601 による 0～255 の float32 輝度へ変換する。"""
    a = _as_u8(arr)
    if a.ndim == 2:
        return a.astype(np.float32)
    r, g, b = (a[:, :, i].astype(np.float32) for i in range(3))
    return 0.299 * r + 0.587 * g + 0.114 * b


def rgb_to_hsv(arr):
    """RGB uint8 を float32 の HSV (h,w,3) へ変換する。H は [0,360)、S と V は [0,1]。"""
    a = _as_u8(arr)[:, :, :3].astype(np.float32) / 255.0
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    d = mx - mn
    safe = np.where(d > 0, d, 1.0)
    h = np.where(mx == r, ((g - b) / safe) % 6.0,
                 np.where(mx == g, (b - r) / safe + 2.0, (r - g) / safe + 4.0)) * 60.0
    h = np.where(d > 0, h % 360.0, 0.0).astype(np.float32)
    s = np.where(mx > 0, d / np.where(mx > 0, mx, 1.0), 0.0).astype(np.float32)
    return np.stack([h, s, mx], axis=2)


# 画像の読み込み（bpy）
def _load_bpy(path):
    import bpy
    p = paths.require_file(path)
    img = bpy.data.images.load(p, check_existing=False)
    try:
        w, h = int(img.size[0]), int(img.size[1])
        ch = int(img.channels)
        if w <= 0 or h <= 0 or ch <= 0:
            raise IOError("Blender could not decode the image: %s" % p)
        info = {"path": p, "width": w, "height": h, "channels": ch, "depth": int(img.depth),
                "is_float": bool(img.is_float), "file_format": str(img.file_format),
                "colorspace": str(img.colorspace_settings.name),
                "alpha_mode": str(img.alpha_mode)}
        buf = np.empty(w * h * ch, dtype=np.float32)
        img.pixels.foreach_get(buf)
    finally:
        bpy.data.images.remove(img)
    buf *= 255.0
    rounded = np.rint(buf)
    # 浮動小数点値と元のバイト値との差。8 ビット画像なら約 1e-5 のはず。
    step = max(1, buf.size // 4_000_000)
    info["max_abs_dev_from_byte"] = float(np.abs(buf[::step] - rounded[::step]).max())
    np.clip(rounded, 0, 255, out=rounded)
    arr = rounded.astype(np.uint8).reshape(h, w, ch)[::-1]
    return np.ascontiguousarray(arr), info


def load_image(path):
    """Blender が保存したチャンネル数（通常 4）の uint8 配列 (h,w,channels) と情報辞書を返す。"""
    global last_load_info
    arr, info = _load_bpy(path)
    last_load_info = info
    return arr, info


def load_image_rgba(path):
    """上から下へ並ぶ uint8 配列 (h, w, 4) を返す。"""
    arr, _ = load_image(path)
    if arr.shape[2] == 4:
        return arr
    if arr.shape[2] == 3:
        alpha = np.full(arr.shape[:2] + (1,), 255, np.uint8)
        return np.concatenate([arr, alpha], axis=2)
    if arr.shape[2] == 1:
        rgb = np.repeat(arr, 3, axis=2)
        return np.concatenate([rgb, np.full(arr.shape[:2] + (1,), 255, np.uint8)], axis=2)
    raise ValueError("unexpected channel count %d" % arr.shape[2])


def load_image_rgb(path):
    """保存された sRGB 符号化後のバイト値を、上から下へ並ぶ uint8 配列 (h, w, 3) で返す。"""
    return np.ascontiguousarray(load_image_rgba(path)[:, :, :3])


def image_size(path):
    """画素データを保持せずに、画像の (幅, 高さ) を返す。"""
    import bpy
    p = paths.require_file(path)
    img = bpy.data.images.load(p, check_existing=False)
    try:
        return int(img.size[0]), int(img.size[1])
    finally:
        bpy.data.images.remove(img)


def load_painting_rgb():
    """params.json で指定された北斎の原画を読み、サイズが 3859 × 2594 か確認する。"""
    arr = load_image_rgb(paths.painting_path())
    w, h = paths.param("painting_width_px"), paths.param("painting_height_px")
    if arr.shape[1] != w or arr.shape[0] != h:
        raise ValueError("painting is %dx%d px but the spec requires %dx%d"
                         % (arr.shape[1], arr.shape[0], w, h))
    return arr


# PNG の書き込み
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_COLOR_TYPE = {1: 0, 2: 4, 3: 2, 4: 6}          # チャンネル数から PNG の色形式を求める。
_CHANNELS = {0: 1, 4: 2, 2: 3, 6: 4}


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def _filter_rows(a2, bpp, mode):
    """a2 は形状 (h, w*bpp) の uint8 配列。フィルターバイトを付けた形状 (h, 1 + w*bpp) の配列を返す。"""
    h = a2.shape[0]
    out = np.empty((h, a2.shape[1] + 1), np.uint8)
    if mode == "none":
        out[:, 0] = 0
        out[:, 1:] = a2
        return out
    sub = a2.copy()
    sub[:, bpp:] = a2[:, bpp:] - a2[:, :-bpp]            # uint8 の演算は 256 を法として折り返す。
    up = a2.copy()
    up[1:] = a2[1:] - a2[:-1]
    if mode == "sub":
        out[:, 0] = 1
        out[:, 1:] = sub
        return out
    if mode == "up":
        out[:, 0] = 2
        out[:, 1:] = up
        return out
    # 適応方式。各行で、符号付きバイト値の絶対値の和が最小になる候補を選ぶ。
    def cost(f):
        return np.minimum(f, 256 - f.astype(np.int16)).sum(axis=1, dtype=np.int64)
    costs = np.stack([cost(a2), cost(sub), cost(up)], axis=0)
    best = costs.argmin(axis=0).astype(np.uint8)
    out[:, 0] = best
    out[:, 1:] = np.where((best == 0)[:, None], a2, np.where((best == 1)[:, None], sub, up))
    return out


def encode_png(arr, compress_level=4, filter_mode="adaptive"):
    """uint8 のグレースケール (h,w)、グレーとアルファ (h,w,2)、RGB、RGBA を PNG のバイト列へ変換する。"""
    a = _as_u8(arr)
    if a.ndim == 2:
        a = a[:, :, None]
    if a.ndim != 3 or a.shape[2] not in _COLOR_TYPE:
        raise ValueError("unsupported array shape %r" % (a.shape,))
    h, w, ch = a.shape
    if h == 0 or w == 0:
        raise ValueError("empty image")
    raw = _filter_rows(np.ascontiguousarray(a).reshape(h, w * ch), ch, filter_mode)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, _COLOR_TYPE[ch], 0, 0, 0)
    return b"".join([_PNG_SIG, _chunk(b"IHDR", ihdr),
                     _chunk(b"IDAT", zlib.compress(raw.tobytes(), compress_level)),
                     _chunk(b"IEND", b"")])


def save_png(path, arr, compress_level=4, filter_mode="adaptive"):
    """uint8（または bool）のグレースケール、RGB、RGBA 配列を PNG へ書く。配列のバイト値を損失なく保存し、色管理による変換は行わない。保存先のパスを返す。
    許可されたルートの外側には書き込まない（gw.paths.assert_writable）。"""
    p = paths.ensure_parent(path)
    data = encode_png(arr, compress_level, filter_mode)
    tmp = p + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, p)
    return p


# PNG の読み込み
def _paeth_row(cur, prev, bpp):
    out = bytearray(cur)
    prev = bytes(prev)
    for i in range(len(out)):
        a = out[i - bpp] if i >= bpp else 0
        b = prev[i]
        c = prev[i - bpp] if i >= bpp else 0
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
        out[i] = (out[i] + pr) & 0xFF
    return np.frombuffer(bytes(out), np.uint8)


def _avg_row(cur, prev, bpp):
    out = bytearray(cur)
    prev = bytes(prev)
    for i in range(len(out)):
        a = out[i - bpp] if i >= bpp else 0
        out[i] = (out[i] + ((a + prev[i]) >> 1)) & 0xFF
    return np.frombuffer(bytes(out), np.uint8)


def decode_png(data):
    """PNG のバイト列を uint8 配列へ復元する。形状はグレースケール (h,w)、または (h,w,2)、(h,w,3)、(h,w,4)。
    8 ビット、非インターレース、パレットなしのファイルに対応する（save_png の出力範囲）。
    フィルター 0/1/2 は配列演算を使い、3/4 は遅いバイト単位の処理を使うため小さいファイル向け。"""
    if data[:8] != _PNG_SIG:
        raise ValueError("not a PNG file")
    pos, idat, ihdr = 8, [], None
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        (crc,) = struct.unpack(">I", data[pos + 8 + n:pos + 12 + n])
        if zlib.crc32(tag + body) & 0xFFFFFFFF != crc:
            raise ValueError("PNG chunk %r has a bad CRC" % tag)
        if tag == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif tag == b"IDAT":
            idat.append(body)
        elif tag == b"IEND":
            break
        pos += 12 + n
    if ihdr is None:
        raise ValueError("PNG without IHDR")
    w, h, depth, ctype, _comp, _flt, interlace = ihdr
    if depth != 8 or ctype not in _CHANNELS or interlace != 0:
        raise ValueError("unsupported PNG (depth %d, colour type %d, interlace %d)"
                         % (depth, ctype, interlace))
    ch = _CHANNELS[ctype]
    raw = np.frombuffer(zlib.decompress(b"".join(idat)), np.uint8).reshape(h, 1 + w * ch)
    ftype = raw[:, 0]
    out = raw[:, 1:].copy()
    zero = np.zeros(w * ch, np.uint8)
    for y in range(h):
        f = int(ftype[y])
        prev = out[y - 1] if y else zero
        if f == 0:
            continue
        if f == 1:
            out[y] = np.cumsum(out[y].reshape(w, ch), axis=0, dtype=np.uint8).reshape(-1)
        elif f == 2:
            out[y] = out[y] + prev
        elif f == 3:
            out[y] = _avg_row(out[y], prev, ch)
        elif f == 4:
            out[y] = _paeth_row(out[y], prev, ch)
        else:
            raise ValueError("bad PNG filter type %d in row %d" % (f, y))
    out = out.reshape(h, w, ch)
    return out[:, :, 0] if ch == 1 else out


def read_png(path):
    """Python と NumPy のみを使う PNG 読み込み関数（decode_png を参照）。元のバイト値を正確に返す。"""
    with open(paths.require_file(path), "rb") as fh:
        return decode_png(fh.read())


def roundtrip_max_abs_diff(path, arr, via="both"):
    """path を再読み込みし、uint8 配列 arr との差の最大絶対値を返す。
    via は numpy（read_png）、bpy（Blender で読み込む）、both（両方を辞書で返す）。"""
    a = _as_u8(arr)
    res = {}
    if via in ("numpy", "both"):
        b = read_png(path)
        res["numpy"] = int(np.abs(a.astype(np.int16) - b.astype(np.int16)).max()) \
            if a.shape == b.shape else None
    if via in ("bpy", "both"):
        b = load_image_rgba(path)
        ref = a
        if ref.ndim == 2:
            ref = np.repeat(ref[:, :, None], 3, axis=2)
        if ref.shape[2] == 3:
            b = b[:, :, :3]
        res["bpy"] = int(np.abs(ref.astype(np.int16) - b.astype(np.int16)).max()) \
            if ref.shape == b.shape else None
    return res
