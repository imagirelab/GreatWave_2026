"""Image input / output with numpy + bpy only (no PIL / cv2 in this environment).

Array convention everywhere in this project:
    uint8, shape (rows, cols[, channels]), rows TOP-to-BOTTOM, channels RGB(A).
    arr[y, x] is the pixel whose centre is (x + 0.5, y + 0.5) in continuous px coords.

Reading  : load_image_rgb / load_image_rgba go through bpy.data.images (JPEG, PNG,
           WebP, ...).  For 8-bit files Blender keeps the stored bytes; .pixels
           returns them as byte/255 floats, bottom-up RGBA.  No colour management is
           applied by this access path (verified in tests/selftest_foundation.py:
           values * 255 are integers within float32 precision, and PNGs written by
           save_png reload bit-exactly).
Writing  : save_png is a pure python/numpy PNG encoder (zlib + struct), so no colour
           management, view transform or dithering can touch the values.
           read_png is the matching pure decoder (8-bit, non-interlaced, non-palette)
           that allows an exact round-trip check without Blender.
"""
import os
import struct
import zlib

import numpy as np

from . import paths

last_load_info = {}


# ------------------------------------------------------------------ helpers
def _as_u8(arr):
    a = np.asarray(arr)
    if a.dtype == np.bool_:
        return a.astype(np.uint8) * 255
    if a.dtype != np.uint8:
        raise TypeError("expected a uint8 (or bool) array, got %s; convert explicitly" % a.dtype)
    return a


def to_rgb(arr):
    """gray (h,w) / (h,w,1) / RGBA (h,w,4) / RGB -> RGB uint8 (h,w,3). RGBA drops alpha."""
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
    """RGB(A) uint8 -> float32 luma (Rec.601) in 0..255."""
    a = _as_u8(arr)
    if a.ndim == 2:
        return a.astype(np.float32)
    r, g, b = (a[:, :, i].astype(np.float32) for i in range(3))
    return 0.299 * r + 0.587 * g + 0.114 * b


def rgb_to_hsv(arr):
    """RGB uint8 -> float32 (h,w,3): H in [0,360), S in [0,1], V in [0,1]."""
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


# ------------------------------------------------------------------ reading (bpy)
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
    # how far the floats are from exact byte values (should be ~1e-5 for 8-bit files)
    step = max(1, buf.size // 4_000_000)
    info["max_abs_dev_from_byte"] = float(np.abs(buf[::step] - rounded[::step]).max())
    np.clip(rounded, 0, 255, out=rounded)
    arr = rounded.astype(np.uint8).reshape(h, w, ch)[::-1]
    return np.ascontiguousarray(arr), info


def load_image(path):
    """-> (uint8 array (h,w,channels as stored by Blender, normally 4), info dict)."""
    global last_load_info
    arr, info = _load_bpy(path)
    last_load_info = info
    return arr, info


def load_image_rgba(path):
    """-> uint8 (h, w, 4), rows top-to-bottom."""
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
    """-> uint8 (h, w, 3), rows top-to-bottom, the stored (sRGB-encoded) byte values."""
    return np.ascontiguousarray(load_image_rgba(path)[:, :, :3])


def image_size(path):
    """(width, height) without keeping the pixels."""
    import bpy
    p = paths.require_file(path)
    img = bpy.data.images.load(p, check_existing=False)
    try:
        return int(img.size[0]), int(img.size[1])
    finally:
        bpy.data.images.remove(img)


def load_painting_rgb():
    """The Hokusai painting from params.json; asserts the 3859 x 2594 size."""
    arr = load_image_rgb(paths.painting_path())
    w, h = paths.param("painting_width_px"), paths.param("painting_height_px")
    if arr.shape[1] != w or arr.shape[0] != h:
        raise ValueError("painting is %dx%d px but the spec requires %dx%d"
                         % (arr.shape[1], arr.shape[0], w, h))
    return arr


# ------------------------------------------------------------------ PNG writer
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_COLOR_TYPE = {1: 0, 2: 4, 3: 2, 4: 6}          # channels -> PNG colour type
_CHANNELS = {0: 1, 4: 2, 2: 3, 6: 4}


def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def _filter_rows(a2, bpp, mode):
    """a2: (h, w*bpp) uint8.  Returns (h, 1 + w*bpp) uint8 with the filter byte."""
    h = a2.shape[0]
    out = np.empty((h, a2.shape[1] + 1), np.uint8)
    if mode == "none":
        out[:, 0] = 0
        out[:, 1:] = a2
        return out
    sub = a2.copy()
    sub[:, bpp:] = a2[:, bpp:] - a2[:, :-bpp]            # uint8 arithmetic wraps mod 256
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
    # adaptive: per row the candidate with the smallest sum of |signed byte|
    def cost(f):
        return np.minimum(f, 256 - f.astype(np.int16)).sum(axis=1, dtype=np.int64)
    costs = np.stack([cost(a2), cost(sub), cost(up)], axis=0)
    best = costs.argmin(axis=0).astype(np.uint8)
    out[:, 0] = best
    out[:, 1:] = np.where((best == 0)[:, None], a2, np.where((best == 1)[:, None], sub, up))
    return out


def encode_png(arr, compress_level=4, filter_mode="adaptive"):
    """uint8 gray (h,w) / gray+alpha (h,w,2) / RGB / RGBA -> PNG bytes."""
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
    """Write a uint8 (or bool) gray / RGB / RGBA array as PNG.  Exact: the file stores
    the array bytes losslessly, nothing is colour-managed.  Returns the path.
    Refuses to write outside the allowed roots (gw.paths.assert_writable)."""
    p = paths.ensure_parent(path)
    data = encode_png(arr, compress_level, filter_mode)
    tmp = p + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, p)
    return p


# ------------------------------------------------------------------ PNG reader
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
    """PNG bytes -> uint8 array (h,w) gray, (h,w,2), (h,w,3) or (h,w,4).
    Supports 8-bit, non-interlaced, non-palette files (everything save_png writes).
    Filters 0/1/2 are vectorised; 3/4 use a slow per-byte loop (small files only)."""
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
    """Pure python/numpy PNG reader (see decode_png).  Exact byte values."""
    with open(paths.require_file(path), "rb") as fh:
        return decode_png(fh.read())


def roundtrip_max_abs_diff(path, arr, via="both"):
    """Reload `path` and return the max abs difference to `arr` (uint8).
    via: 'numpy' (read_png), 'bpy' (load through Blender) or 'both' -> dict."""
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
