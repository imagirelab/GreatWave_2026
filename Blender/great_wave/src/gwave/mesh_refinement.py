"""参照模型の指定面だけを細分する、NumPyのみの補助処理。

長く細い三角面を非線形に変形した際の、面による近似誤差を減らす。
元の参照姿勢では面上に頂点を追加するだけで、輪郭や体積は変えない。
共有辺は隣接面でも同時に分割し、T字の接続を作らない。
"""

import numpy as np


DEFAULT_REFERENCE_FACES = (16, 79651)


def refine_reference(vertices, faces, target_faces=DEFAULT_REFERENCE_FACES):
    """指定面と共有辺を持つ隣接面を細分し、(新頂点, 新三角面) を返す。

    既定の面番号は source_reduced.npz の124511面に対する0始まりの番号。
    指定面の3辺に中点を置く。辺を共有する全ての面も同じ中点を使い、
    3辺を分ける面は4分割し、隣接面は分けた辺の数に応じて分割する。
    細分は1回とし、非対象の頂点座標はそのまま残す。
    細分した面の番号は変わるため、元の面番号を再度適用しないこと。
    色や材質などの面属性を継承する場合は呼出し側で改めて割り当てる。
    入力配列は変更せず、出力の面の巻き順は元の向きを保つ。
    """
    points = np.asarray(vertices, dtype=float)
    triangles = np.asarray(faces)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError("頂点は有限値の (N, 3) 配列で指定してください")
    if (triangles.ndim != 2 or triangles.shape[1] != 3
            or not np.issubdtype(triangles.dtype, np.integer)):
        raise ValueError("面は整数の (M, 3) 配列で指定してください")
    triangles = triangles.astype(np.int64, copy=False)
    if triangles.size and (triangles.min() < 0 or triangles.max() >= len(points)):
        raise ValueError("面の頂点番号が頂点配列の範囲外です")
    targets = np.asarray(tuple(target_faces), dtype=np.int64)
    if targets.ndim != 1 or (targets.size and (targets.min() < 0 or targets.max() >= len(triangles))):
        raise ValueError("対象の面番号が面配列の範囲外です")
    if not targets.size:
        return points.copy(), triangles.copy()
    # 同じ辺は向きに関係なく1つの番号へまとめる。
    directed_edges = triangles[:, ((0, 1), (1, 2), (2, 0))]
    edges, inverse = np.unique(np.sort(directed_edges, axis=2).reshape(-1, 2),
                               axis=0, return_inverse=True)
    edge_ids = inverse.reshape(-1, 3)
    split_edges = np.unique(edge_ids[targets].reshape(-1))
    split_mask = np.isin(edge_ids, split_edges)
    affected = np.flatnonzero(split_mask.any(axis=1))

    midpoint_ids = np.full(len(edges), -1, dtype=np.int64)
    midpoint_ids[split_edges] = len(points) + np.arange(len(split_edges))
    midpoints = points[edges[split_edges]].mean(axis=1)
    new_points = np.concatenate((points, midpoints), axis=0)
    rebuilt = []
    for face_id in affected:
        count = int(split_mask[face_id].sum())
        ids = triangles[face_id]
        mids = midpoint_ids[edge_ids[face_id]]
        if count == 3:
            a, b, c = ids
            ab, bc, ca = mids
            children = ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca))
        elif count == 1:
            index = int(np.flatnonzero(split_mask[face_id])[0])
            a, b, c = ids[np.array((index, index + 1, index + 2)) % 3]
            ab = mids[index]
            children = ((a, ab, c), (ab, b, c))
        else:
            index = next(i for i in range(3) if split_mask[face_id, i]
                         and split_mask[face_id, (i + 1) % 3])
            a, b, c = ids[np.array((index, index + 1, index + 2)) % 3]
            ab, bc = mids[index], mids[(index + 1) % 3]
            children = ((ab, b, bc), (a, ab, c), (ab, bc, c))
        rebuilt.extend(children)
    unaffected = np.flatnonzero(~split_mask.any(axis=1))
    unchanged = triangles[unaffected]
    new_faces = np.concatenate((unchanged, np.asarray(rebuilt, dtype=np.int64)), axis=0)
    return new_points, new_faces
