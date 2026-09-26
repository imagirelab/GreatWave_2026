# -*- coding: utf-8 -*-
"""番号29（爪の一覧）の骨格化と枝の分割。numpy と OpenCV だけを使う（scipy・scikit-image は使わない）。

- zhang_suen：Zhang–Suen の細線化（1984）。8近傍の符号（0..255）を配列のずらしで作り、
  削除の条件を 256 通りの表で引く。2つの副反復を交互に、削る画素がなくなるまで繰り返す。
- thin_final：Zhang–Suen の後に残る余分な画素（太さ 2 の塊、偽の分岐）を、(8, 4) 単純点で近傍数 ≥ 3 のものだけ
  逐次に除く（位相は変えず、線の端も縮めない）。
- build_graph：骨格の画素を「分岐（交差数 ≥3 または近傍数 ≥4 の画素の塊）」「端点（近傍数 1）」
  「枝（分岐を除いた画素の連結成分を、一方の端から順にたどった画素列）」に分ける。
- prune_spurs：分岐から短く突き出た枝（とげ）を、分岐の内接円からの突き出しの長さで反復して除く。

画素座標は画素中心が整数の配列添字系（y 下、x 右）。path は (y, x) の整数列。
"""
import numpy as np
import cv2

# 近傍の順（Zhang–Suen の P2..P9）：北、北東、東、南東、南、南西、西、北西。ビット k が P(k+2)。
_OFFS = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
# 枝をたどるときは 4近傍を先に見る（斜めの近道で画素を飛ばさない）。
_WALK = [(-1, 0), (0, 1), (1, 0), (0, -1), (-1, 1), (1, 1), (1, -1), (-1, -1)]


def ncode(mask):
    """各画素の 8近傍の符号（ビット k = _OFFS[k] の近傍が前景）。"""
    m = np.asarray(mask).astype(np.uint8)
    p = np.pad(m, 1)
    H, W = m.shape
    c = np.zeros((H, W), np.uint8)
    for k, (dy, dx) in enumerate(_OFFS):
        c |= (p[1 + dy:1 + dy + H, 1 + dx:1 + dx + W] << k).astype(np.uint8)
    return c


def _tables():
    lut1 = np.zeros(256, bool)
    lut2 = np.zeros(256, bool)
    cn = np.zeros(256, np.uint8)
    nb = np.zeros(256, np.uint8)
    for i in range(256):
        b = [(i >> k) & 1 for k in range(8)]
        B = sum(b)
        A = sum(1 for k in range(8) if b[k] == 0 and b[(k + 1) % 8] == 1)  # 0→1 の遷移数（交差数）
        P2, P3, P4, P5, P6, P7, P8, P9 = b
        cn[i] = A
        nb[i] = B
        if 2 <= B <= 6 and A == 1:
            if P2 * P4 * P6 == 0 and P4 * P6 * P8 == 0:
                lut1[i] = True
            if P2 * P4 * P8 == 0 and P2 * P6 * P8 == 0:
                lut2[i] = True
    return lut1, lut2, cn, nb


LUT1, LUT2, CROSSING, NEIGHBOURS = _tables()


def _simple_table():
    """8近傍の符号ごとに、中心の画素が (8, 4) 単純点か（除いても前景の 8連結と背景の 4連結の位相が変わらないか）。
    前景：近傍の前景画素の 8連結成分の数 = 1。背景：近傍の背景画素の 4連結成分のうち、中心に 4近傍で接するものの数 = 1。"""
    pos = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
    simple = np.zeros(256, bool)
    for code in range(256):
        fg = [k for k in range(8) if (code >> k) & 1]
        bg = [k for k in range(8) if not (code >> k) & 1]

        def ncomp(ids, adj):
            ids = set(ids)
            comps = []
            while ids:
                s = ids.pop()
                stack, comp = [s], {s}
                while stack:
                    a = stack.pop()
                    for b in list(ids):
                        if adj(pos[a], pos[b]):
                            ids.discard(b)
                            comp.add(b)
                            stack.append(b)
                comps.append(comp)
            return comps
        a8 = lambda p, q: max(abs(p[0] - q[0]), abs(p[1] - q[1])) == 1  # noqa: E731
        a4 = lambda p, q: abs(p[0] - q[0]) + abs(p[1] - q[1]) == 1  # noqa: E731
        t8 = len(ncomp(fg, a8))
        t4 = sum(1 for c in ncomp(bg, a4) if any(k in (0, 2, 4, 6) for k in c))
        simple[code] = (t8 == 1 and t4 == 1)
    return simple


SIMPLE = _simple_table()


def thin_final(S, max_pass=50):
    """Zhang–Suen の後に残る余分な画素（太さ 2 の塊、偽の分岐）を、単純点で近傍数 ≥ 3 の画素だけ逐次に除く。
    近傍数 2 以下の画素（線の途中と端）は除かないので、線は端から縮まない（近傍数 2 の単純点まで除くと、4連結の階段の端から
    線が次々に削れる）。除くたびに近傍を数え直すので、位相（成分と穴の数）を変えない。
    戻り値は (骨格, 除いた画素数)。"""
    S = np.asarray(S).astype(bool).copy()
    H, W = S.shape
    removed = 0
    for _ in range(max_pass):
        c = ncode(S)
        cand = S & SIMPLE[c] & (NEIGHBOURS[c] >= 3)
        ys, xs = np.nonzero(cand)
        if len(ys) == 0:
            break
        changed = 0
        for y, x in zip(ys.tolist(), xs.tolist()):
            code = 0
            for k, (dy, dx) in enumerate(_OFFS):
                q0, q1 = y + dy, x + dx
                if 0 <= q0 < H and 0 <= q1 < W and S[q0, q1]:
                    code |= 1 << k
            if SIMPLE[code] and NEIGHBOURS[code] >= 3:
                S[y, x] = False
                changed += 1
        removed += changed
        if not changed:
            break
    return S, removed


def zhang_suen(mask, max_iter=2000):
    """Zhang–Suen の細線化。戻り値は (骨格, 反復回数)。"""
    s = np.asarray(mask).astype(bool).copy()
    it = 0
    for it in range(1, max_iter + 1):
        changed = False
        for lut in (LUT1, LUT2):
            d = s & lut[ncode(s)]
            if d.any():
                s[d] = False
                changed = True
        if not changed:
            break
    return s, it


def path_length(path):
    p = np.asarray(path, np.float64)
    if len(p) < 2:
        return 0.0
    d = np.diff(p, axis=0)
    return float(np.hypot(d[:, 0], d[:, 1]).sum())


def build_graph(S):
    """骨格 S（bool）→ (edges, junction_label, n_junction_labels)。

    edges の各要素：path（(y,x) の列）、j0 / j1（path の先頭 / 末尾に接する分岐の番号の並び）、
    end0 / end1（先頭 / 末尾が端点か）、jmid（途中の画素に接する分岐の番号の並び）。分岐に接する端がある枝は、先頭を分岐側にする。
    """
    S = np.asarray(S).astype(bool)
    H, W = S.shape
    c = ncode(S)
    cn = CROSSING[c]
    nb = NEIGHBOURS[c]
    # 分岐：交差数 ≥ 3 または近傍数 ≥ 4 の画素。線が分岐の画素の斜め脇を通り抜ける所（3 画素の三角）では、分岐が枝の途中に
    # 付くことがある。その枝は jmid に記録し、とげの除去で消さない（消すと、途中に付いた別の枝が切り離される）。
    J = S & ((cn >= 3) | (nb >= 4))
    nj, jl = cv2.connectedComponents(J.astype(np.uint8), connectivity=8)
    E = S & ~J
    ne, el = cv2.connectedComponents(E.astype(np.uint8), connectivity=8)
    ys, xs = np.nonzero(E)
    order = np.argsort(el[ys, xs], kind="stable")
    ys, xs = ys[order], xs[order]
    labs = el[ys, xs]
    starts = np.searchsorted(labs, np.arange(1, ne + 1))
    edges = []
    for e in range(1, ne):
        py = ys[starts[e - 1]:starts[e]].tolist()
        px = xs[starts[e - 1]:starts[e]].tolist()
        pix = set(zip(py, px))
        deg = {}
        jadj = {}
        for (y, x) in pix:
            d = 0
            for dy, dx in _WALK:
                q = (y + dy, x + dx)
                if q in pix:
                    d += 1
                elif 0 <= q[0] < H and 0 <= q[1] < W and jl[q] > 0:
                    jadj.setdefault((y, x), set()).add(int(jl[q]))
            deg[(y, x)] = d
        ends = sorted(p for p in pix if deg[p] <= 1)
        start = None
        for p in ends:
            if p in jadj:
                start = p
                break
        if start is None and ends:
            start = ends[0]
        if start is None:
            start = min(pix)
        path = [start]
        seen = {start}
        cur = start
        while True:
            nxt = None
            for dy, dx in _WALK:
                q = (cur[0] + dy, cur[1] + dx)
                if q in pix and q not in seen:
                    nxt = q
                    break
            if nxt is None:
                break
            path.append(nxt)
            seen.add(nxt)
            cur = nxt
        j0 = sorted(jadj.get(path[0], set()))
        j1 = sorted(jadj.get(path[-1], set())) if len(path) > 1 else list(j0)
        jmid = sorted(set().union(*[jadj[q] for q in path[1:-1] if q in jadj]) - set(j0) - set(j1)) if len(path) > 2 else []
        edges.append({
            "path": np.array(path, np.int32),
            "j0": j0,
            "j1": j1,
            "end0": bool(nb[path[0]] == 1),
            "end1": bool(nb[path[-1]] == 1) if len(path) > 1 else bool(nb[path[0]] == 1),
            "complete": len(seen) == len(pix),
            "jmid": jmid,
        })
    return edges, jl, nj


def junction_radius(DT, jl, jids):
    """分岐の塊の内接円の半径（距離変換の最大）。"""
    r = 0.0
    for j in jids:
        m = jl == j
        if m.any():
            r = max(r, float(DT[m].max()))
    return r


def prune_spurs(S, DT, ratio, min_px, rounds=6):
    """分岐の内接円からの突き出し（枝の長さ − 分岐の半径）が max(min_px, ratio × 枝の半幅の中央値) 未満の
    末端の枝を除く（途中に別の分岐が付いた枝と、端が 2 つの分岐に接する枝は除かない）。ただし 1 つの分岐で、除くと残りの枝が 2 本未満になる場合は、条件に当たる末端の枝のうち
    最も長い 1 本を残す（爪の先の近くに短いとげがあるとき、先端側の枝までとげと一緒に消さないため）。
    除いた後の骨格で分岐を数え直し、変化がなくなるまで（最大 rounds 回）繰り返す。
    戻り値は (骨格, 各回で除いた枝の数)。"""
    S = np.asarray(S).astype(bool).copy()
    removed = []
    for _ in range(rounds):
        edges, jl, _ = build_graph(S)
        deg = {}
        for e in edges:
            for j in set(e["j0"]) | set(e["j1"]):
                deg[j] = deg.get(j, 0) + 1
        flagged = {}
        for i, e in enumerate(edges):
            has_j = bool(e["j0"] or e["j1"])
            # 途中に別の分岐が付いた枝と、端が 2 つの分岐に接する枝（分岐どうしを結ぶ画素を含む）は、とげとして扱わない
            is_term = (e["end0"] or e["end1"]) and has_j and not e["jmid"] and len(e["j0"] or e["j1"]) == 1
            if not is_term:
                continue
            p = e["path"]
            L = path_length(p) + 1.0
            rj = junction_radius(DT, jl, e["j0"] or e["j1"])
            hw = float(np.median(DT[p[:, 0], p[:, 1]]))
            if L - rj < max(min_px, ratio * hw):
                flagged.setdefault((e["j0"] or e["j1"])[0], []).append((L, i))
        kill = []
        for j, lst in flagged.items():
            lst.sort()
            if deg.get(j, 0) - len(lst) < 2:
                lst = lst[:-1]  # 最も長い末端の枝を残す
            kill += [edges[i]["path"] for _, i in lst]
        removed.append(len(kill))
        if not kill:
            break
        for p in kill:
            S[p[:, 0], p[:, 1]] = False
        # 除いた後に残る分岐の画素の小さな突起は、次の回の細線化で整える
        S, _ = zhang_suen(S)
        S, _ = thin_final(S)
    return S, removed


def _out_dir(path, at_start, probe):
    """枝の端から枝の内側へ向かう単位ベクトル（x, y）。path は (y, x)。"""
    p = np.asarray(path, np.float64)[:, ::-1]
    if len(p) < 2:
        return np.zeros(2)
    k = min(int(probe), len(p) - 1)
    v = (p[k] - p[0]) if at_start else (p[-1 - k] - p[-1])
    n = np.hypot(*v)
    return v / n if n > 1e-9 else np.zeros(2)


def _end_halfwidth(DT, path, at_start, probe):
    p = np.asarray(path)
    k = max(1, min(int(probe), len(p)))
    q = p[:k] if at_start else p[-k:]
    return float(np.median(DT[q[:, 0], q[:, 1]]))


def strokes(edges, max_deflect_deg, probe_px, DT=None, max_width_ratio=None):
    """枝を『なめらかに続く線（ストローク）』にまとめる。

    各分岐で、出ていく向きのなす角が 180° に近い（折れ角 = 180° − なす角 が小さい）枝の組から順に、
    折れ角 ≤ max_deflect_deg なら対にする（貪欲法）。DT と max_width_ratio を渡すと、分岐の近く（probe_px）の半幅の比が
    max_width_ratio を超える組（細い爪が太い白の塊へ入る所）は対にしない。対にならなかった枝の端と端点が、ストロークの両端になる。
    戻り値は list of dict：parts（(枝の番号, 向き) の列。向き +1 は path の順、-1 は逆順）、
    ends（先頭と末尾の端の種類：('end',) 端点／('junction', 分岐の番号の並び)／('loop',)）。
    """
    inc = {}
    for i, e in enumerate(edges):
        for side, js in ((0, e["j0"]), (1, e["j1"])):
            for j in js[:1]:  # 分岐の塊が 2 つに接する稀な場合は最初の塊だけを使う
                inc.setdefault(j, []).append((i, side))
    pair = {}
    for j, lst in inc.items():
        cand = []
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                (ia, sa), (ib, sb) = lst[a], lst[b]
                if ia == ib:
                    continue
                va = _out_dir(edges[ia]["path"], sa == 0, probe_px)
                vb = _out_dir(edges[ib]["path"], sb == 0, probe_px)
                cosang = float(np.clip(np.dot(va, vb), -1.0, 1.0))
                deflect = 180.0 - np.degrees(np.arccos(cosang))
                if DT is not None and max_width_ratio:
                    wa = _end_halfwidth(DT, edges[ia]["path"], sa == 0, probe_px)
                    wb = _end_halfwidth(DT, edges[ib]["path"], sb == 0, probe_px)
                    if max(wa, wb) > max_width_ratio * max(min(wa, wb), 0.5):
                        continue
                cand.append((deflect, lst[a], lst[b]))
        cand.sort(key=lambda t: t[0])
        for deflect, A, B in cand:
            if deflect > max_deflect_deg:
                break
            if A in pair or B in pair:
                continue
            pair[A] = B
            pair[B] = A
    used = [False] * len(edges)

    def end_kind(i, side):
        e = edges[i]
        js = e["j0"] if side == 0 else e["j1"]
        if js:
            return ("junction", list(js))
        return ("end",) if (e["end0"] if side == 0 else e["end1"]) else ("free",)

    out = []

    def walk(i, side_in):
        parts = []
        start = end_kind(i, side_in)
        cur, s_in = i, side_in
        while True:
            used[cur] = True
            parts.append((cur, +1 if s_in == 0 else -1))
            s_out = 1 - s_in
            nxt = pair.get((cur, s_out))
            if nxt is None:
                return parts, start, end_kind(cur, s_out)
            if used[nxt[0]]:
                return parts, start, ("loop",)
            cur, s_in = nxt
    # 自由な端（対になっていない端）から歩く
    for i in range(len(edges)):
        for side in (0, 1):
            if not used[i] and (i, side) not in pair:
                parts, a, b = walk(i, side)
                out.append({"parts": parts, "ends": [a, b]})
    # 残りは閉じた輪
    for i in range(len(edges)):
        if not used[i]:
            parts, a, b = walk(i, 0)
            out.append({"parts": parts, "ends": [("loop",), ("loop",)]})
    return out, pair


def stroke_path(edges, parts, return_breaks=False):
    """ストロークの画素列（(y, x)、重複を除いてつなぐ）。return_breaks なら枝の継ぎ目（2 本目以降の枝の先頭の添字）も返す。"""
    seq = []
    breaks = []
    n = 0
    for i, d in parts:
        p = edges[i]["path"]
        p = p if d > 0 else p[::-1]
        if seq and len(p) and np.array_equal(seq[-1][-1], p[0]):
            p = p[1:]
        if seq:
            breaks.append(n)
        seq.append(p)
        n += len(p)
    out = np.concatenate(seq, 0) if seq else np.zeros((0, 2), np.int32)
    return (out, breaks) if return_breaks else out


def topology_check(mask, skel):
    """細線化で位相が保たれたかを数える：前景の 8連結成分の数と、背景の 4連結成分の数（穴の数 + 外側 1）。
    あわせて 2×2 がすべて前景の所（太さ 2 の残り）の数を返す。"""
    m = np.asarray(mask).astype(np.uint8)
    s = np.asarray(skel).astype(np.uint8)
    fg_m = cv2.connectedComponents(m, connectivity=8)[0] - 1
    fg_s = cv2.connectedComponents(s, connectivity=8)[0] - 1
    bg_m = cv2.connectedComponents(np.pad(1 - m, 1, constant_values=1), connectivity=4)[0] - 1
    bg_s = cv2.connectedComponents(np.pad(1 - s, 1, constant_values=1), connectivity=4)[0] - 1
    blk = int((s[:-1, :-1] & s[1:, :-1] & s[:-1, 1:] & s[1:, 1:]).sum())
    return {"components_mask": int(fg_m), "components_skeleton": int(fg_s),
            "background_regions_mask": int(bg_m), "background_regions_skeleton": int(bg_s), "blocks_2x2": blk}


def selftest():
    """合成図形での確認：21×101 の長方形の骨格が中央の行の 1 本の横線（長さは約 101 − 21 = 80 px。両端は半幅ずつ縮む）になるか、
    穴あき円板（半径 15〜40）の位相（成分 1、穴 1）が保たれ、太さ 2 の残りがないか。thin_final が階段の端を縮めず、2×2 の塊を消すか。"""
    out = {}
    R = np.zeros((41, 141), bool)
    R[10:31, 20:121] = True
    s, _ = zhang_suen(R)
    ys, xs = np.nonzero(s)
    out["rectangle_21x101"] = {"skeleton_px": int(s.sum()), "row_min": int(ys.min()), "row_max": int(ys.max()),
                               "centre_row": 20, "x_span": [int(xs.min()), int(xs.max())],
                               "pass": bool(ys.min() >= 19 and ys.max() <= 21 and abs((xs.max() - xs.min() + 1) - 80) <= 2)}
    yy, xx = np.mgrid[0:101, 0:101]
    rr = np.hypot(yy - 50, xx - 50)
    A = (rr <= 40) & (rr >= 15)
    s2, _ = zhang_suen(A)
    t = topology_check(A, s2)
    t["pass"] = bool(t["components_mask"] == t["components_skeleton"] and t["background_regions_mask"] == t["background_regions_skeleton"]
                     and t["blocks_2x2"] == 0)
    out["annulus_r15_40"] = t
    # thin_final：4連結の階段（太さ 2 の斜め線）は端を縮めずに 1 画素幅になり、2×2 の塊のある 4 叉の分岐は塊が消える
    St = np.zeros((12, 12), bool)
    for i in range(8):
        St[i + 1, i + 1] = True
        St[i + 1, i + 2] = True
    tt, n_t = thin_final(St)
    ys0, xs0 = np.nonzero(St)
    ys1, xs1 = np.nonzero(tt)
    tc = topology_check(St, tt)
    out["thin_final_staircase"] = {"removed_px": int(n_t), "px_before": int(St.sum()), "px_after": int(tt.sum()),
                                   "extent_kept": bool(ys0.min() == ys1.min() and ys0.max() == ys1.max() and xs0.min() == xs1.min() and xs0.max() == xs1.max()),
                                   "topology_kept": bool(tc["components_mask"] == tc["components_skeleton"] and tc["background_regions_mask"] == tc["background_regions_skeleton"])}
    out["thin_final_staircase"]["pass"] = bool(out["thin_final_staircase"]["extent_kept"] and out["thin_final_staircase"]["topology_kept"]
                                               and tc["blocks_2x2"] == 0 and n_t > 0)
    B = np.zeros((8, 8), bool)
    B[2:4, 2:4] = True
    B[0:2, 2] = True
    B[3, 0:2] = True
    B[4, 4] = B[5, 5] = B[1, 4] = B[0, 5] = True
    tb, n_b = thin_final(B)
    tc = topology_check(B, tb)
    out["thin_final_block_junction"] = {"removed_px": int(n_b), "blocks_2x2_after": tc["blocks_2x2"],
                                        "pass": bool(tc["blocks_2x2"] == 0 and tc["components_mask"] == tc["components_skeleton"]
                                                     and tc["background_regions_mask"] == tc["background_regions_skeleton"])}
    return out
