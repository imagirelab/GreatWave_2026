# -*- coding: utf-8 -*-
"""Fochesato・Grilli・Dias 2007（Wave Motion 44, 395-416）の刊行版の図から、線を数として読み取る（図はベクトルの線なので、目盛りに合わせて座標を戻す）。
調べの記録：Unity/Build/FLIP45/research/fochesato_ja.md（§3）
py -3.10 -I r45_fgd07_digitize.py で走らせる（numpy だけ。PDF は Wayback の写しを読み込み、ディスクには保存しない。1 分ほど）。
出力：Unity/Build/FLIP45/research/fochesato_bem_digitized.json（長さは水深 d = 20 m で割った値。m にするには 20 を掛ける）
読む図：4（y = 0 の断面、6.89T）、5a（z = Ac/2 の水平の断面）、5b（x = xc の横の断面）、6（横にずれた断面）、11（巻く頂の拡大）、
        13（9 例の y = 0 の断面、xc を 0 に）、14（9 例の z = Ac/2 の水平の断面）、15（9 例の x = xc の横の断面）、
        16（9 例の頂の下の水平の水の速さ）。
確かめ：目盛りの直線の当てはめの残り、表 1 の Ac・幅 ℓ・谷との比べを出す。
"""
import sys, re, zlib, json, math, os, urllib.request
import numpy as np

URL = "http://web.archive.org/web/20170706035805id_/https://personal.egr.uri.edu/grilli/FochesatoGrilliDias-07.pdf"
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP45/research/fochesato_bem_digitized.json"
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
except Exception:
    pass
data = urllib.request.urlopen(URL, timeout=180).read()


objs = {}
for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', data):
    num = int(m.group(1))
    start = m.end()
    end = data.find(b'endobj', start)
    if end < 0:
        continue
    objs[num] = data[start:end]


def stream_of(body):
    i = body.find(b'stream')
    if i < 0:
        return None, body
    d = body[:i]
    j = i + 6
    if body[j:j+2] == b'\r\n':
        j += 2
    elif body[j:j+1] in (b'\n', b'\r'):
        j += 1
    k = body.rfind(b'endstream')
    raw = body[j:k]
    if b'FlateDecode' in d:
        try:
            raw = zlib.decompressobj().decompress(raw)
        except Exception:
            return b'', d
    elif re.search(rb'/Filter', d):
        return b'', d
    return raw, d


def ref(s, key):
    m = re.search(rb'/' + key + rb'\s+(\d+)\s+0\s+R', s)
    return int(m.group(1)) if m else None


def dict_of(n):
    b = objs.get(n, b'')
    s, d = stream_of(b)
    return d


GLYPH = {'fi': 'fi', 'fl': 'fl', 'ff': 'ff', 'ffi': 'ffi', 'ffl': 'ffl', 'minus': '-', 'endash': '-', 'emdash': '--',
         'quoteright': "'", 'quoteleft': "'", 'quotedblleft': '"', 'quotedblright': '"', 'bullet': '*', 'degree': 'deg',
         'periodcentered': '.', 'multiply': 'x', 'plusminus': '+/-', 'space': ' ', 'hyphen': '-', 'period': '.',
         'comma': ',', 'colon': ':', 'semicolon': ';', 'parenleft': '(', 'parenright': ')', 'bracketleft': '[',
         'bracketright': ']', 'slash': '/', 'equal': '=', 'plus': '+', 'less': '<', 'greater': '>', 'percent': '%',
         'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7',
         'eight': '8', 'nine': '9', 'alpha': 'alpha', 'beta': 'beta', 'gamma': 'gamma', 'delta': 'delta',
         'epsilon': 'eps', 'eta': 'eta', 'theta': 'theta', 'lambda': 'lambda', 'mu': 'mu', 'nu': 'nu', 'pi': 'pi',
         'rho': 'rho', 'sigma': 'sigma', 'tau': 'tau', 'phi': 'phi', 'psi': 'psi', 'omega': 'omega', 'Delta': 'Delta',
         'Omega': 'Omega', 'Gamma': 'Gamma', 'Theta': 'Theta', 'approxequal': '~=', 'similar': '~', 'infinity': 'inf',
         'partialdiff': 'd', 'asterisk': '*', 'ampersand': '&', 'question': '?', 'exclam': '!', 'quotesingle': "'",
         'underscore': '_', 'bar': '|', 'xi': 'xi', 'zeta': 'zeta', 'kappa': 'kappa', 'chi': 'chi'}


def glyph_to_text(g):
    if g in GLYPH:
        return GLYPH[g]
    if len(g) == 1:
        return g
    if g.startswith('uni') and len(g) == 7:
        try:
            return chr(int(g[3:], 16))
        except Exception:
            pass
    return '{' + g + '}'


def parse_cmap(n):
    raw, _ = stream_of(objs.get(n, b''))
    m = {}
    if not raw:
        return m
    for blk in re.findall(rb'beginbfchar(.*?)endbfchar', raw, re.S):
        for a, b in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            try:
                m[int(a, 16)] = bytes.fromhex(b.decode()).decode('utf-16-be')
            except Exception:
                pass
    for blk in re.findall(rb'beginbfrange(.*?)endbfrange', raw, re.S):
        for a, b, c in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', blk):
            lo, hi, base = int(a, 16), int(b, 16), int(c, 16)
            for i in range(lo, hi + 1):
                m[i] = chr(base + i - lo)
    return m


font_cache = {}


def font_map(fn):
    if fn in font_cache:
        return font_cache[fn]
    d = dict_of(fn)
    mp = {}
    enc_ref = ref(d, rb'Encoding')
    encd = dict_of(enc_ref) if enc_ref else d
    dm = re.search(rb'/Differences\s*\[(.*?)\]', encd, re.S)
    if dm:
        code = 0
        for tok in re.findall(rb'/[^\s/\[\]]+|\d+', dm.group(1)):
            if tok.startswith(b'/'):
                mp[code] = glyph_to_text(tok[1:].decode('latin1'))
                code += 1
            else:
                code = int(tok)
    tu = ref(d, rb'ToUnicode')
    if tu:
        cm = parse_cmap(tu)
        for k, v in cm.items():
            mp[k] = v
    font_cache[fn] = mp
    return mp


def decode_str(s, fmap):
    out = []
    for c in s:
        if c in fmap:
            out.append(fmap[c])
        elif 32 <= c < 127:
            out.append(chr(c))
        else:
            out.append('{%d}' % c)
    return ''.join(out)


def lit_string(buf, i):
    # buf[i] == '('
    depth = 1
    i += 1
    out = bytearray()
    while i < len(buf) and depth:
        c = buf[i]
        if c == 0x5c:  # backslash
            i += 1
            e = buf[i:i+1]
            if e in b'nrtbf':
                out += {b'n': b'\n', b'r': b'\r', b't': b'\t', b'b': b'\b', b'f': b'\f'}[e]
                i += 1
            elif e.isdigit():
                j = i
                while j < len(buf) and j < i + 3 and buf[j:j+1].isdigit():
                    j += 1
                out.append(int(buf[i:j], 8) & 255)
                i = j
            elif e in (b'\r', b'\n'):
                i += 1
            else:
                out += e
                i += 1
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                i += 1
                break
        out.append(c)
        i += 1
    return bytes(out), i


TOK = re.compile(rb'\s*(?:(\()|<([0-9A-Fa-f\s]*)>|(\[)|(\])|(/[^\s/\[\]()<>]+)|([-+]?\d*\.?\d+)|(<<|>>)|([A-Za-z\'"*]+[0-9*]?))')


def run_content(cs, fonts, lines):
    i = 0
    stack = []
    cur_font = {}
    y = None
    x = 0
    line = []
    arr = None

    def flush():
        if line:
            lines.append(''.join(line))
            line.clear()

    while i < len(cs):
        m = TOK.match(cs, i)
        if not m:
            i += 1
            continue
        if m.group(1):
            s, i = lit_string(cs, m.start(1))
            (arr if arr is not None else stack).append(('s', s))
            continue
        i = m.end()
        if m.group(2) is not None:
            h = re.sub(rb'\s', b'', m.group(2))
            if len(h) % 2:
                h += b'0'
            (arr if arr is not None else stack).append(('s', bytes.fromhex(h.decode())))
        elif m.group(3):
            arr = []
        elif m.group(4):
            stack.append(('a', arr))
            arr = None
        elif m.group(5):
            (arr if arr is not None else stack).append(('n', m.group(5)))
        elif m.group(6):
            (arr if arr is not None else stack).append(('f', float(m.group(6))))
        elif m.group(7):
            pass
        elif m.group(8):
            op = m.group(8)
            if op == b'BI':
                j = cs.find(b'EI', i)
                i = j + 2 if j > 0 else len(cs)
                stack = []
                continue
            if op == b'Tf':
                nm = [v for t, v in stack if t == 'n']
                if nm:
                    cur_font = fonts.get(nm[-1][1:], {})
            elif op in (b'Td', b'TD'):
                nums = [v for t, v in stack if t == 'f']
                if len(nums) >= 2 and abs(nums[-1]) > 0.5:
                    flush()
                elif len(nums) >= 2 and nums[-2] > 1.0 and line and not line[-1].endswith(' '):
                    line.append(' ')
            elif op == b'Tm':
                nums = [v for t, v in stack if t == 'f']
                if len(nums) >= 6:
                    ny = nums[-1]
                    if y is None or abs(ny - y) > 2:
                        flush()
                    elif line and not line[-1].endswith(' '):
                        line.append(' ')
                    y = ny
            elif op in (b'T*', b"'", b'"'):
                flush()
                if op != b'T*':
                    for t, v in stack:
                        if t == 's':
                            line.append(decode_str(v, cur_font))
            elif op == b'Tj':
                for t, v in stack:
                    if t == 's':
                        line.append(decode_str(v, cur_font))
            elif op == b'TJ':
                for t, v in stack:
                    if t == 'a':
                        for tt, vv in v:
                            if tt == 's':
                                line.append(decode_str(vv, cur_font))
                            elif tt == 'f' and vv < -180:
                                line.append(' ')
            elif op == b'ET':
                pass
            stack = []
    flush()


def page_list():
    # find root pages
    root = None
    for n, b in objs.items():
        if re.search(rb'/Type\s*/Catalog', b):
            root = ref(b, rb'Pages')
            break
    out = []

    def walk(n, inherited):
        b = dict_of(n)
        res = inherited
        if re.search(rb'/Resources', b):
            res = (n, b)
        if re.search(rb'/Type\s*/Pages', b):
            km = re.search(rb'/Kids\s*\[(.*?)\]', b, re.S)
            for k in re.findall(rb'(\d+)\s+0\s+R', km.group(1)):
                walk(int(k), res)
        else:
            out.append((n, res))
    walk(root, None)
    return out


def fonts_for(page_body, res):
    src = page_body
    rr = ref(page_body, rb'Resources')
    if rr:
        src = dict_of(rr)
    elif res and not re.search(rb'/Resources', page_body):
        src = res[1]
    fm = re.search(rb'/Font\s*(\d+)\s+0\s+R', src)
    if fm:
        fd = dict_of(int(fm.group(1)))
    else:
        fm = re.search(rb'/Font\s*<<(.*?)>>', src, re.S)
        fd = fm.group(1) if fm else b''
    fonts = {}
    for name, num in re.findall(rb'/([^\s/]+)\s+(\d+)\s+0\s+R', fd):
        fonts[name] = font_map(int(num))
    return fonts



PAGES = page_list()

def collect(page_no):


    pn, res = PAGES[page_no - 1]
    pb = dict_of(pn)
    fonts = fonts_for(pb, res)
    cm_ = re.search(rb'/Contents\s*\[(.*?)\]', pb, re.S)
    refs = [int(x) for x in re.findall(rb'(\d+)\s+0\s+R', cm_.group(1))] if cm_ else [ref(pb, rb'Contents')]
    cs = b''
    for r in refs:
        s, _ = stream_of(objs.get(r, b''))
        cs += (s or b'') + b'\n'


    def mul(m1, m2):
        a, b, c, d, e, f = m1
        A, B, C, D, E, F = m2
        return [a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F]


    def apply(m, x, y):
        return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


    ctm = [1, 0, 0, 1, 0, 0]
    stack = []
    gs = {'w': 1.0, 'col': 'K0', 'dash': ''}
    path = []      # list of subpaths (lists of points)
    cur = None
    paths = []
    texts = []
    tm = [1, 0, 0, 1, 0, 0]
    tlm = [1, 0, 0, 1, 0, 0]
    cur_font = {}
    fsize = 1.0
    leading = 0.0
    ops_stack = []
    i = 0
    arr = None
    while i < len(cs):
        m = TOK.match(cs, i)
        if not m:
            i += 1
            continue
        if m.group(1):
            s, i = lit_string(cs, m.start(1))
            (arr if arr is not None else ops_stack).append(('s', s))
            continue
        i = m.end()
        if m.group(2) is not None:
            h = re.sub(rb'\s', b'', m.group(2))
            if len(h) % 2:
                h += b'0'
            (arr if arr is not None else ops_stack).append(('s', bytes.fromhex(h.decode())))
            continue
        if m.group(3):
            arr = []
            continue
        if m.group(4):
            ops_stack.append(('a', arr))
            arr = None
            continue
        if m.group(5):
            (arr if arr is not None else ops_stack).append(('n', m.group(5)))
            continue
        if m.group(6):
            (arr if arr is not None else ops_stack).append(('f', float(m.group(6))))
            continue
        if m.group(7):
            continue
        op = m.group(8)
        nums = [v for t, v in ops_stack if t == 'f']
        if op == b'q':
            stack.append((list(ctm), dict(gs)))
        elif op == b'Q':
            if stack:
                ctm, gs = stack.pop()
        elif op == b'cm' and len(nums) >= 6:
            ctm = mul(nums[-6:], ctm)
        elif op == b'w' and nums:
            gs['w'] = nums[-1]
        elif op in (b'G', b'g') and nums:
            gs['col'] = 'G%.2f' % nums[-1]
        elif op in (b'RG', b'rg') and len(nums) >= 3:
            gs['col'] = 'RGB%.2f,%.2f,%.2f' % tuple(nums[-3:])
        elif op in (b'K', b'k') and len(nums) >= 4:
            gs['col'] = 'CMYK%.2f,%.2f,%.2f,%.2f' % tuple(nums[-4:])
        elif op == b'd':
            a_ = [v for t, v in ops_stack if t == 'a']
            gs['dash'] = ','.join('%g' % x for t2, x in (a_[-1] if a_ else []) if t2 == 'f')
        elif op == b'm' and len(nums) >= 2:
            cur = [apply(ctm, nums[-2], nums[-1])]
            path.append(cur)
        elif op == b'l' and len(nums) >= 2 and cur is not None:
            cur.append(apply(ctm, nums[-2], nums[-1]))
        elif op == b'c' and len(nums) >= 6 and cur is not None:
            cur.append(apply(ctm, nums[-2], nums[-1]))
        elif op in (b'v', b'y') and len(nums) >= 4 and cur is not None:
            cur.append(apply(ctm, nums[-2], nums[-1]))
        elif op == b're' and len(nums) >= 4:
            x, y, w, h = nums[-4:]
            cur = [apply(ctm, x, y), apply(ctm, x + w, y), apply(ctm, x + w, y + h), apply(ctm, x, y + h), apply(ctm, x, y)]
            path.append(cur)
        elif op == b'h' and cur:
            cur.append(cur[0])
        elif op in (b'S', b's', b'f', b'F', b'f*', b'B', b'B*', b'b', b'b*', b'n'):
            if op != b'n':
                for sp in path:
                    if len(sp) >= 2:
                        paths.append({'op': op.decode(), 'w': gs['w'] * abs(ctm[0]) if ctm[0] else gs['w'], 'col': gs['col'], 'dash': gs['dash'],
                                      'pts': [(round(x, 3), round(y, 3)) for x, y in sp]})
            path = []
            cur = None
        elif op == b'BT':
            tm = [1, 0, 0, 1, 0, 0]
            tlm = [1, 0, 0, 1, 0, 0]
        elif op == b'Tf':
            nm = [v for t, v in ops_stack if t == 'n']
            if nm:
                cur_font = fonts.get(nm[-1][1:], {})
            if nums:
                fsize = nums[-1]
        elif op == b'Tm' and len(nums) >= 6:
            tm = nums[-6:]
            tlm = list(tm)
        elif op in (b'Td', b'TD') and len(nums) >= 2:
            tlm = mul([1, 0, 0, 1, nums[-2], nums[-1]], tlm)
            tm = list(tlm)
            if op == b'TD':
                leading = -nums[-1]
        elif op == b'TL' and nums:
            leading = nums[-1]
        elif op == b'T*':
            tlm = mul([1, 0, 0, 1, 0, -leading], tlm)
            tm = list(tlm)
        elif op in (b'Tj', b'TJ', b"'"):
            sstr = ''
            for t, v in ops_stack:
                if t == 's':
                    sstr += decode_str(v, cur_font)
                elif t == 'a':
                    for tt, vv in v:
                        if tt == 's':
                            sstr += decode_str(vv, cur_font)
            full = mul(tm, ctm)
            x0, y0 = full[4], full[5]
            texts.append({'s': sstr, 'x': round(x0, 2), 'y': round(y0, 2), 'size': round(abs(full[3]) * fsize, 2)})
        ops_stack = []

    return {'paths': paths, 'texts': texts}



W = {'0': .5, '1': .5, '2': .5, '3': .5, '4': .5, '5': .5, '6': .5, '7': .5, '8': .5, '9': .5, '.': .25, '-': .333, '—': 1.0, '–': .5}


def num(s):
    s2 = s.replace('—', '-').replace('–', '-')
    try:
        return float(s2)
    except ValueError:
        return None


def label_center(t):
    w = sum(W.get(ch, .5) for ch in t['s']) * t['size']
    return t['x'] + w / 2.0, t['y'] + 0.35 * t['size']


def segs(paths, box):
    """2-point (or short) stroked segments inside box (x0,y0,x1,y1)."""
    out = []
    for p in paths:
        if p['op'] not in ('S', 's'):
            continue
        pts = p['pts']
        for (a, b), (c, d) in zip(pts[:-1], pts[1:]):
            if min(a, c) >= box[0] - 1 and max(a, c) <= box[2] + 1 and min(b, d) >= box[1] - 1 and max(b, d) <= box[3] + 1:
                out.append((a, b, c, d, p))
    return out


def fit_axis(ticks, labels):
    """ticks: sorted tick positions; labels: list of (pos, value). Pair each label with nearest tick; LSQ fit value = A + B pos."""
    pairs = []
    for pos, val in labels:
        j = int(np.argmin([abs(t - pos) for t in ticks]))
        if abs(ticks[j] - pos) < 6:
            pairs.append((ticks[j], val))
    pairs = sorted(set(pairs))
    P = np.array(pairs)
    B, A = np.polyfit(P[:, 0], P[:, 1], 1)
    resid = P[:, 1] - (A + B * P[:, 0])
    return A, B, pairs, float(np.abs(resid).max())


def axes_from(d, box, xlab_region, ylab_region, tick_len=(1.5, 6.0)):
    """Find bottom/left axis lines in box, tick marks, and labels in given regions; return mapping functions."""
    S = segs(d['paths'], box)
    # long horizontal lines -> bottom axis = lowest; long vertical -> left axis = leftmost
    hor = [s for s in S if abs(s[1] - s[3]) < 0.01 and abs(s[0] - s[2]) > 40]
    ver = [s for s in S if abs(s[0] - s[2]) < 0.01 and abs(s[1] - s[3]) > 40]
    ybot = min(s[1] for s in hor)
    xleft = min(s[0] for s in ver)
    xt = sorted(set(round(s[0], 2) for s in S if abs(s[0] - s[2]) < 0.01 and tick_len[0] < abs(s[1] - s[3]) < tick_len[1]
                    and min(s[1], s[3]) - ybot < 0.05 and min(s[1], s[3]) - ybot > -0.05))
    yt = sorted(set(round(s[1], 2) for s in S if abs(s[1] - s[3]) < 0.01 and tick_len[0] < abs(s[0] - s[2]) < tick_len[1]
                    and abs(min(s[0], s[2]) - xleft) < 0.05))
    xl = [(label_center(t)[0], num(t['s'])) for t in d['texts'] if xlab_region[0] <= t['x'] <= xlab_region[2]
          and xlab_region[1] <= t['y'] <= xlab_region[3] and num(t['s']) is not None]
    yl = [(label_center(t)[1], num(t['s'])) for t in d['texts'] if ylab_region[0] <= t['x'] <= ylab_region[2]
          and ylab_region[1] <= t['y'] <= ylab_region[3] and num(t['s']) is not None]
    ax = fit_axis(xt, xl)
    ay = fit_axis(yt, yl)
    return {'ybot': ybot, 'xleft': xleft, 'xticks': xt, 'yticks': yt, 'xfit': ax, 'yfit': ay}


def to_data(pts, ax):
    A, B = ax['xfit'][0], ax['xfit'][1]
    C, D = ax['yfit'][0], ax['yfit'][1]
    return [(round(A + B * x, 4), round(C + D * y, 4)) for x, y in pts]


def chain(segments, tol=0.05):
    """Join 2-point segments into polylines by matching endpoints."""
    segs_ = [((a, b), (c, d)) for a, b, c, d, _ in segments]
    lines = []
    used = [False] * len(segs_)
    for i, (p, q) in enumerate(segs_):
        if used[i]:
            continue
        used[i] = True
        line = [p, q]
        changed = True
        while changed:
            changed = False
            for j, (r, s) in enumerate(segs_):
                if used[j]:
                    continue
                if math.dist(line[-1], r) < tol:
                    line.append(s); used[j] = True; changed = True
                elif math.dist(line[-1], s) < tol:
                    line.append(r); used[j] = True; changed = True
                elif math.dist(line[0], s) < tol:
                    line.insert(0, r); used[j] = True; changed = True
                elif math.dist(line[0], r) < tol:
                    line.insert(0, s); used[j] = True; changed = True
        lines.append(line)
    return lines


# ================================================================ 図ごとの読み取り
TABLE1 = {  # 刊行版の表 1（水深 d で割った値）。列は (d, θmax)
    "d1_th40": {"Ac": 0.337, "l": 3.030}, "d1_th45": {"Ac": 0.358, "l": 3.298}, "d1_th50": {"Ac": 0.309, "l": 4.062},
    "d2_th40": {"Ac": 0.339, "l": 3.876}, "d2_th45": {"Ac": 0.312, "l": 4.198}, "d2_th50": {"Ac": 0.260, "l": 4.496},
    "d3_th40": {"Ac": 0.335, "l": 3.852}, "d3_th45": {"Ac": 0.309, "l": 4.178}, "d3_th50": {"Ac": 0.264, "l": 4.430},
}
out = {"source": "Fochesato, Grilli & Dias 2007, Wave Motion 44(5) 395-416, publisher PDF (Wayback copy of personal.egr.uri.edu/grilli/FochesatoGrilliDias-07.pdf, 2017-07-06)",
       "units": "lengths divided by d = 20 m; times by sqrt(d/g) = 1.428 s", "figures": {}}


def prof_stats(a):
    i = int(np.argmax(a[:, 1]))
    L, R = a[:i + 1], a[i:]
    zc = [float(a[k, 0] + (a[k + 1, 0] - a[k, 0]) * (-a[k, 1]) / (a[k + 1, 1] - a[k, 1])) for k in range(len(a) - 1) if a[k, 1] * a[k + 1, 1] < 0]
    return {"crest_x": round(float(a[i, 0]), 4), "crest_z": round(float(a[i, 1]), 4),
            "min_z_rear_side": round(float(L[:, 1].min()), 4), "min_z_front_side": round(float(R[:, 1].min()), 4),
            "zero_crossings_x": [round(v, 4) for v in sorted(zc)]}


# 図 4（p. 405 = PDF の 11 枚目、上）：y = 0、t = 6.89T。縦の目盛りの負の値は記号が抜けるので、0 より下を負にする
d11 = collect(11)
z0 = [t for t in d11['texts'] if t['s'] == '0' and 85 < t['x'] < 100 and 600 < t['y'] < 620][0]['y']
for t in d11['texts']:
    if 85 < t['x'] < 100 and 545 < t['y'] < 675 and t['y'] < z0 - 1 and num(t['s']) not in (None, 0.0):
        t['s'] = '-' + t['s']
ax = axes_from(d11, (95, 535, 460, 680), (120, 530, 460, 535), (85, 545, 100, 675))
c = [p for p in d11['paths'] if len(p['pts']) > 80][0]
a = np.array(to_data(c['pts'], ax))
out["figures"]["fig4_y0_t6.89T"] = {"x": a[:, 0].round(4).tolist(), "z": a[:, 1].round(4).tolist(), "stats": prof_stats(a),
                                    "axis_fit_max_residual": [ax['xfit'][3], ax['yfit'][3]],
                                    "note": "縦は 9 倍に伸ばした図だが、座標は目盛りから戻したので伸びはない"}
# 図 5a（同じ頁、下の左）：z = Ac/2 の水平の断面（半分）
ax = axes_from(d11, (55, 95, 262, 236), (65, 95, 262, 99), (44, 95, 60, 236))
c = [p for p in d11['paths'] if len(p['pts']) == 36][0]
a = np.array(to_data(c['pts'], ax))
out["figures"]["fig5a_z_Ac_half"] = {"x": a[:, 0].round(4).tolist(), "y": a[:, 1].round(4).tolist(),
                                     "half_width": round(float(-a[:, 1].min()), 4), "x_at_widest": round(float(a[np.argmin(a[:, 1]), 0]), 4),
                                     "x_range_at_y0": [round(float(a[:, 0].min()), 4), round(float(a[:, 0].max()), 4)],
                                     "axis_fit_max_residual": [ax['xfit'][3], ax['yfit'][3]]}
# 図 5b（同じ頁、下の右）：x = xc の横の断面
ax = axes_from(d11, (286, 95, 494, 236), (286, 95, 494, 99), (276, 95, 292, 236))
c = [p for p in d11['paths'] if len(p['pts']) == 29][0]
b = np.array(to_data(c['pts'], ax))
zmax = float(b[:, 1].max())
yh = [float(b[k, 0] + (b[k + 1, 0] - b[k, 0]) * (zmax / 2 - b[k, 1]) / (b[k + 1, 1] - b[k, 1])) for k in range(len(b) - 1)
      if (b[k, 1] - zmax / 2) * (b[k + 1, 1] - zmax / 2) < 0]
out["figures"]["fig5b_x_xc"] = {"y": b[:, 0].round(4).tolist(), "z": b[:, 1].round(4).tolist(), "crest_z": round(zmax, 4),
                                "y_at_half_height": [round(v, 4) for v in yh], "axis_fit_max_residual": [ax['xfit'][3], ax['yfit'][3]]}
# 図 6（p. 406 = 12 枚目、上）：横にずれた断面（本文は y = ±ℓ/2 = 36 m と書く）
d12 = collect(12)
ax = axes_from(d12, (95, 535, 475, 690), (130, 530, 470, 534), (94, 600, 110, 672), tick_len=(1.0, 8))
c = [p for p in d12['paths'] if len(p['pts']) == 86][0]
a = np.array(to_data(c['pts'], ax))
a = a[np.argsort(a[:, 0])]
out["figures"]["fig6_y_offset"] = {"x": a[:, 0].round(4).tolist(), "z": a[:, 1].round(4).tolist(), "stats": prof_stats(a),
                                   "axis_fit_max_residual": [ax['xfit'][3], ax['yfit'][3]]}
# 図 11（p. 408 = 14 枚目）：巻く頂の拡大（説明は y = 0、t = 6.89T）
d14 = collect(14)
ax = axes_from(d14, (100, 540, 460, 680), (90, 530, 460, 540), (85, 570, 105, 670))
c = [p for p in d14['paths'] if len(p['pts']) > 8][0]
a = np.array(to_data(c['pts'], ax))
out["figures"]["fig11_closeup"] = {"x": a[:, 0].round(4).tolist(), "z": a[:, 1].round(4).tolist(),
                                   "crest_x": round(float(a[np.argmax(a[:, 1]), 0]), 4), "crest_z": round(float(a[:, 1].max()), 4),
                                   "tip_x_max": round(float(a[:, 0][a[:, 1] > 0.25].max()), 4),
                                   "axis_fit_max_residual": [ax['xfit'][3], ax['yfit'][3]]}
# 図 13・14・15（p. 411 = 17 枚目）
d17 = collect(17)
ax1 = axes_from(d17, (55, 400, 185, 510), (100, 405, 185, 410), (45, 450, 58, 500), tick_len=(1.0, 8))
A, B, C_, D_ = ax1['xfit'][0], ax1['xfit'][1], ax1['yfit'][0], ax1['yfit'][1]
names13 = {'': '40', '1.6587': '45', '0.1382,1.1058': '50'}
f13 = {}
for ip, Lft in enumerate([58.303, 212.509, 364.715]):
    for cpath in d17['paths']:
        pts = cpath['pts']
        if len(pts) > 30 and Lft - 1 <= min(x for x, y in pts) and max(x for x, y in pts) <= Lft + 125 and 440 < min(y for x, y in pts) < 520:
            arr = np.array([(A + B * (x - (Lft - 58.303)), C_ + D_ * y) for x, y in pts])
            key = 'd%d_th%s' % (ip + 1, names13[cpath['dash']])
            f13[key] = {"x_minus_xc": arr[:, 0].round(4).tolist(), "z": arr[:, 1].round(4).tolist(), "crest_z": round(float(arr[:, 1].max()), 4)}
out["figures"]["fig13_y0_shifted"] = {"curves": f13, "axis_fit_max_residual": [ax1['xfit'][3], ax1['yfit'][3]],
                                      "note": "d = 2・3 の頂は表 1 より約 0.02 高い（図 15 は表と合う）。図の z の基準が違う見込み"}


def curves17(box, dashmap, tol):
    S_ = segs(d17['paths'], box)
    res = {}
    for dash, name in dashmap.items():
        cand = [s for s in S_ if s[4]['dash'] == dash and len(s[4]['pts']) == 2]

        def on_edge(s):
            same_v = any(abs(s[0] - e) < 0.05 and abs(s[2] - e) < 0.05 for e in (box[0], box[2]))
            same_h = any(abs(s[1] - e) < 0.05 and abs(s[3] - e) < 0.05 for e in (box[1], box[3]))
            tick = (min(abs(s[0] - box[0]), abs(s[0] - box[2]), abs(s[2] - box[0]), abs(s[2] - box[2])) < 0.05 or
                    min(abs(s[1] - box[1]), abs(s[1] - box[3]), abs(s[3] - box[1]), abs(s[3] - box[3])) < 0.05) and math.dist(s[:2], s[2:4]) < 1.3
            return same_v or same_h or tick
        cand = [s for s in cand if not on_edge(s)]
        res[name] = [l for l in chain(cand, tol=tol) if len(l) >= 2]
    return res


f14 = {}
for ip, (x0, x1) in enumerate([(63.713, 188.001), (216.298, 340.586), (370.946, 495.234)]):
    cx = (x0 + x1) / 2
    for name, lines in curves17((x0, 247.805, x1, 341.195), {'': '40', '1.6655': '45', '0.1388,1.1103': '50'}, 0.6).items():
        Ls = [[(round((X - cx) / 31.066, 4), round((Y - 341.195) / 31.13, 4)) for (X, Y) in l] for l in lines]
        arr = np.array([p for l in Ls for p in l])
        key = 'd%d_th%s' % (ip + 1, name)
        f14[key] = {"lines_x_minus_xc_y": Ls, "width": round(float(-2 * arr[:, 1].min()), 4),
                    "x_minus_xc_at_widest": round(float(arr[np.argmin(arr[:, 1]), 0]), 4)}
out["figures"]["fig14_z_Ac_half"] = {"curves": f14, "scale": "x: 31.066 pt/d (ticks every 0.5 at 15.533 pt), y: 31.13 pt/d (ticks every 0.5 at 15.565 pt)"}
f15 = {}
for ip, (x0, x1) in enumerate([(62.55, 182.607), (215.698, 335.754), (368.956, 489.014)]):
    for name, lines in curves17((x0, 90.812, x1, 180.861), {'': '40', '1.4404': '45', '0.12,0.96029': '50'}, 0.6).items():
        arr = np.array(sorted([(round((X - x1) / 30.008, 4), round((Y - 135.824) / 30.006, 4)) for l in lines for (X, Y) in l]))
        zm = float(arr[:, 1].max())
        yh = [float(arr[k, 0] + (arr[k + 1, 0] - arr[k, 0]) * (zm / 2 - arr[k, 1]) / (arr[k + 1, 1] - arr[k, 1])) for k in range(len(arr) - 1)
              if (arr[k, 1] - zm / 2) * (arr[k + 1, 1] - zm / 2) < 0]
        key = 'd%d_th%s' % (ip + 1, name)
        f15[key] = {"y": arr[:, 0].tolist(), "z": arr[:, 1].tolist(), "crest_z": round(zm, 4), "y_at_half_height": [round(v, 4) for v in yh]}
out["figures"]["fig15_x_xc"] = {"curves": f15, "scale": "y: 30.008 pt/d, z: 30.006 pt/d; y = 0 at the right edge"}

# 図 16（p. 412 = 18 枚目、上）：頂の下の水平の水の速さ u/√(gd) と z（底 z = −d から）。
# 縦の目盛りの負の数は字が線で描かれていて読めないので、'0' の目盛りと底（線の下の端 = −d、本文 §3.4）で合わせる
d18 = collect(18)
f16 = {}
names16 = {'': '40', '1.8215': '45', '0.1518,1.2144': '50'}
for (x0, x1, zz0, zs, dep) in [(64.972, 188.108, 310.275, 68.66, 1), (219.139, 342.275, 321.714, 40.05, 2), (373.306, 496.441, 326.414, 28.27, 3)]:
    for cpath in d18['paths']:
        pts = cpath['pts']
        if cpath['op'] == 'S' and len(pts) > 100 and x0 - 5 <= min(x for x, y in pts) and max(x for x, y in pts) <= x1 + 1 and min(y for x, y in pts) > 240:
            arr = np.array([((X - x0) / ((x1 - x0) / 0.8), (Y - zz0) / zs) for X, Y in pts])
            key = 'd%d_th%s' % (dep, names16[cpath['dash']])
            k0 = int(np.argmin(np.abs(arr[:, 1])))
            f16[key] = {"u": arr[:, 0].round(4).tolist(), "z": arr[:, 1].round(4).tolist(),
                        "u_top": round(float(arr[np.argmax(arr[:, 1]), 0]), 4), "z_top": round(float(arr[:, 1].max()), 4),
                        "u_at_z0": round(float(arr[k0, 0]), 4), "u_bottom": round(float(arr[np.argmin(arr[:, 1]), 0]), 4)}
out["figures"]["fig16_u_under_crest"] = {"curves": f16, "scale": "u: 0..0.8 across the panel; z: tick spacing 0.2 (d=1), 0.5 (d=2, 3)"}

# ================================================================ 表 1 との比べ
chk = {}
for key, tb in TABLE1.items():
    chk[key] = {"Ac_table": tb["Ac"], "Ac_fig13": f13.get(key, {}).get("crest_z"), "Ac_fig15": f15.get(key, {}).get("crest_z"),
                "l_table": tb["l"], "l_fig14": f14.get(key, {}).get("width")}
s4 = out["figures"]["fig4_y0_t6.89T"]["stats"]
chk["d1_th45_fig4"] = {"Ac_table": 0.358, "Ac_fig4": s4["crest_z"], "At1_table": 0.180, "At1_fig4": -s4["min_z_rear_side"],
                       "At2_table": 0.107, "At2_fig4": -s4["min_z_front_side"], "xc_table": 10.585, "xc_fig4": s4["crest_x"],
                       "l_table": 3.298, "l_fig5a": round(2 * out["figures"]["fig5a_z_Ac_half"]["half_width"], 4)}
out["check_vs_table1"] = chk
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("wrote", OUT)
print(json.dumps(chk, indent=1))
print("fig6", out["figures"]["fig6_y_offset"]["stats"])
print("fig11", {k: v for k, v in out["figures"]["fig11_closeup"].items() if k not in ("x", "z")})
print("fig5a", {k: v for k, v in out["figures"]["fig5a_z_Ac_half"].items() if k not in ("x", "y")})
print("fig5b", {k: v for k, v in out["figures"]["fig5b_x_xc"].items() if k not in ("y", "z")})
print("fig16", {k: {kk: vv for kk, vv in v.items() if kk not in ("u", "z")} for k, v in f16.items()})

