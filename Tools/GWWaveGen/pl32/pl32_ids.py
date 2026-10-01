# -*- coding: utf-8 -*-
"""仕上げ32：爪・白の帯・飛沫の群の ID を、仕上げ28 の主役波（K*′ P28R2rec・G_p28rec）と仕上げ29 の材質（PL29）・仕上げ31 の飛沫で作り直す。

設計32 の ds32_ids.py（シートへの結び付けと ID ごとの履歴、群、瞬間移動・点滅・129 の検査）を、次の差し替えでそのまま回す（numpy）：
  - 主役波：Unity/Build/Polish/32/white/hero_pkg（G_p28rec の位置。T_white は pl32_white.py の出力。最後の層 τ = 0 が K*′ P28R2rec）
  - 時間曲線：Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json
  - 爪の一覧：Unity/Build/Polish/32/list/ds32_claw_inventory.json（pl32_claw_list.py）
  - 白の帯の群の「t* で白の頂点」：設計32 は 29修正01 の色面（原画カメラの投影の焼き込み）の色区だったが、仕上げ29 で投影をやめたので（Q28）、
    材質 PL29 の白の範囲（pl31_zone の頂点の旗。Unity/Build/Polish/32/white/pl31_zone_vertex.npy）にする
  - 飛沫：仕上げ31 の 2,500 粒（白・生成りの段と灰の白の段の 2 つのコマの表）を、設計31 の書式（ds31_spray_table.json・ds31_spray_frames.json）の
    写しへまとめ直して読む（Unity/Build/Polish/32/spray_adapt。粒の並びは段 0 → 段 1、表の順。dot_id は粒の通し番号 S0000〜）
出力（Git 対象外）：Unity/Build/Polish/32/list/ds32_ids.json・ds32_claw_hist_f32.bin・ds32_group_hist_f32.bin・ds32_id_checks.json・ds32_band_members_i32.bin
"""
import ast
import hashlib
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds32")
import types  # noqa: E402

# 設計32 の ds32_ids.py の 1 行だけを替えて読み込む（名前の付いた決まり pl32_birth_all_corners）：
# 爪の誕生 τ_b を、根元の格子の 2×2 の T_white の「最小」（最初の角が白くなる時）から「最大」（4 つの角がそろって白くなる時）にする。
# 仕上げ31 の 136 の数え方（根元の格子の 4 頂点がそろって白くなる時刻が、最初に見えるコマより半コマ超遅い爪を数える）で 0 にするため。
_SRC = REPO + "/Tools/GWWaveGen/ds32/ds32_ids.py"
_OLD = "tau_b = float(fin.min())"
_NEW = "tau_b = float(fin.max()) if tb_how == \"2x2\" else float(fin.min())"
_code = open(_SRC, encoding="utf-8").read()
if _code.count(_OLD) != 1:
    raise SystemExit("ds32_ids.py の置き換え先が見つかりません")
D = types.ModuleType("ds32_ids_pl32")
D.__file__ = _SRC
exec(compile(_code.replace(_OLD, _NEW), _SRC, "exec"), D.__dict__)

B = REPO + "/Unity/Build/Polish"
HERO = B + "/32/white/hero_pkg"
WARP = B + "/28/G_p28rec/timewarp_G_p28rec.json"
LIST = B + "/32/list"
SPRAY31 = B + "/31/spray"
ADAPT = B + "/32/spray_adapt"
ZONE = B + "/32/white/pl31_zone_vertex.npy"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def build_spray_adapter():
    os.makedirs(ADAPT, exist_ok=True)
    tab = json.load(open(SPRAY31 + "/pl31_spray_table.json", encoding="utf-8"))["particles"]
    fr = []
    order = []
    for tone in (0, 1):
        m = json.load(open(SPRAY31 + "/pl31_spray_tone%d_frames.json" % tone, encoding="utf-8"))
        a = np.fromfile(SPRAY31 + "/" + m["file"], "<f4").reshape(m["frames"], m["count"], 4)
        fr.append(a)
        order += [i for i, p in enumerate(tab) if int(float(p["tone"])) == tone]
    F = np.concatenate(fr, 1)
    if F.shape[1] != len(tab) or len(order) != len(tab):
        raise SystemExit("飛沫の粒の数が表と合いません")
    # 並びの確かめ：t* のコマ（360）の位置と表の p_star
    ps = np.array([ast.literal_eval(tab[i]["p_star"]) if isinstance(tab[i]["p_star"], str) else tab[i]["p_star"] for i in order], np.float64)
    err = np.linalg.norm(F[360, :, :3] - ps, axis=1)
    parts = []
    for k, i in enumerate(order):
        p = tab[i]
        parts.append(dict(dot_id="S%04d" % k, source_dot_id=str(p["dot_id"]), kind=p.get("kind"), tone=int(float(p["tone"])),
                          tau_e=float(p["tau_e"]), p_e=[float(x) for x in (ast.literal_eval(p["p_e"]) if isinstance(p["p_e"], str) else p["p_e"])]))
    json.dump(dict(schema="GreatWave.Polish32.spray_adapt/1", count=len(parts), particles=parts,
                   note_ja="仕上げ31 の飛沫の表を設計31 の書式（数値）へ写したもの。並びは段 0 → 段 1、表の順",
                   source=dict(table_sha256=sha(SPRAY31 + "/pl31_spray_table.json"))),
              open(ADAPT + "/ds31_spray_table.json", "w", encoding="utf-8"), ensure_ascii=False)
    F.astype("<f4").tofile(ADAPT + "/ds31_spray_frames.bin")
    json.dump(dict(schema="GreatWave.DS31.particles/1", frames=int(F.shape[0]), hz=30, t0=0.0, count=int(F.shape[1]), file="ds31_spray_frames.bin",
                   sha256=sha(ADAPT + "/ds31_spray_frames.bin"), bytes=int(F.nbytes)),
              open(ADAPT + "/ds31_spray_frames.json", "w", encoding="utf-8"), ensure_ascii=False)
    return dict(count=int(F.shape[1]), order_check_tstar_max_m=float(err.max()))


def main():
    global LIST
    if '--list' in sys.argv:          # 修正の回 1：一覧と ID の置き場を替える（既定は Unity/Build/Polish/32/list）
        LIST = sys.argv[sys.argv.index('--list') + 1]
    info = build_spray_adapter()
    print("spray adapter", info)
    zone = np.load(ZONE)

    def vertex_class(R, C):
        v = np.where(zone.reshape(-1), 0, 3).astype(np.int32)
        return v, None
    D.HERO, D.WARP, D.SPRAY, D.OUT = HERO, WARP, ADAPT, LIST
    D.W31.vertex_class = vertex_class
    D.__doc__ = (D.__doc__ or "") + "\n［仕上げ32］pl32_ids.py で主役波・時間曲線・一覧・白の帯の定義・飛沫を差し替えて回した（pl32_ids.py の説明）。"
    sys.argv = [sys.argv[0], "--out", LIST]
    D.main()
    chk = json.load(open(LIST + "/ds32_id_checks.json", encoding="utf-8"))
    chk["pl32"] = dict(hero=HERO.replace(REPO + "/", ""), hero_twhite_sha256=sha(HERO + "/ds27_twhite_r32f.bin"), warp=WARP.replace(REPO + "/", ""),
                       warp_sha256=sha(WARP), white_band_from="PL29 の白の範囲（pl31_zone_vertex.npy）", zone_sha256=sha(ZONE), spray=info,
                       birth_rule_ja="pl32_birth_all_corners：爪の誕生 τ_b は根元の格子の 2×2 の T_white の最大（4 つの角がそろって白くなる時）。2×2 に有限の値がなければ設計32 のまま 5×5 の最小",
                       ds32_ids_sha256=sha(_SRC), replaced=[_OLD, _NEW])
    json.dump(chk, open(LIST + "/ds32_id_checks.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print({k: chk[k] for k in ("bound", "teleport_count", "flicker_count", "group_member_lost_count", "growth_decreasing_samples",
                               "reprojection_tstar_display_px", "max_moves_m", "sheet_max_vertex_move_m")})


if __name__ == "__main__":
    main()
