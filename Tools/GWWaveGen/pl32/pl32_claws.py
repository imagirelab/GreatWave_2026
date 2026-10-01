# -*- coding: utf-8 -*-
"""仕上げ32：爪の帯（設計33 の型・骨格・帯・成長）を、仕上げ32 の一覧と ID（K*′ P28R2rec・G_p28rec へ結び付け直したもの）で作り直す。

設計33 の ds33_claw_rig.py（型・骨格・幅・成長の段の結び付け）と ds33_claw_anim.py（全コマの帯のメッシュと 105・137・139 の検査）を、
次の差し替えでそのまま回す（numpy。爪の形の作り方は設計33 のまま。帯の幅・断面・こぶは仕上げ33）：
  - 一覧と ID：Unity/Build/Polish/32/list（pl32_claw_list.py・pl32_ids.py）
  - 主役波：Unity/Build/Polish/32/white/hero_pkg、時間曲線 Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json
  - 爪の成長の始まり：根元の T_white（pl32_white.py。白の順 pl31_white_order patch で、爪の根元の誘導 pl31_white_claw_pin は外した）。
    設計33 と同じ「根元が白くなると伸び始め、t* で終わる」3 段の標準曲線
  - 支の判定：仕上げ32 の一覧は爪どうしが画素を分け合うので、支の根元は主爪の領域の中に入らない。rig の「根元が主爪の領域の中（2 px）」を外し
    （branch_inside_tol を 1e6）、残る条件（主爪の中心線の 10〜95% の所、主爪の幅 + 4 px 以内、主爪より短い）だけで決める
  - 関節の面の選び方：設計33 は「前にある面はいつも採る」。仕上げ32 の b区域の爪 C233 は、根元の面より 12.9 m 手前の別の面（隠れの境の向こう）に
    関節が載り、帯が 13 m に伸びてコマの間で跳んだ。前の面も直前の関節の深さから 3 m 以内だけ採り、それより手前なら直前の関節の深さの面に置く
    （FRONT_WINDOW_M。名前の付いた決まり pl32_joint_front_window）
  - 帯の持ち上げ（名前の付いた美術の誘導 pl32_band_lift）：帯を作る道具を pl32_claw_anim.py（ds33_claw_anim.py の写し）にして足した。説明はその道具の冒頭
  - 根元の色区の記録（anim の web_join）：29修正01 の色区（投影）ではなく、材質 PL29 の白の範囲で読む
出力（Git 対象外）：Unity/Build/Polish/32/claws/（設計33 と同じ名前のファイル。DS34ClawPlayer がそのまま読む ds33_claw_layout.json を含む）
"""
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
import ds33_common as U  # noqa: E402

B = REPO + "/Unity/Build/Polish"
U.OUT = B + "/32/claws"
U.D32 = B + "/32/list"
U.HERO = B + "/32/white/hero_pkg"
U.WARP = B + "/28/G_p28rec/timewarp_G_p28rec.json"
ZONE = B + "/32/white/pl31_zone_vertex.npy"
FRONT_WINDOW_M = 3.0


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(U.OUT, exist_ok=True)
    zone = np.load(ZONE)
    U.W31.vertex_class = lambda R, C: (np.where(zone.reshape(-1), 0, 3).astype(np.int32), None)
    if part in ("rig", "all"):
        import ds33_claw_rig as RIG
        RIG.P["branch_inside_tol_ref_px"] = 1e6

        def place(self, qd, depth_ref, window):
            """pl32_joint_front_window：前の面も直前の関節の深さから FRONT_WINDOW_M 以内だけ採る。"""
            h = self.hit(qd[0], qd[1])
            if h is not None:
                r, c = h
                p = U.tri_eval(self.X0, np.array(r), np.array(c))
                dz = float(self.cam.depth(p)) - depth_ref
                if -FRONT_WINDOW_M <= dz <= window:
                    return "sheet", p, r, c
            d = self.cam.ray(np.array(qd[0]), np.array(qd[1]))
            s_ = depth_ref / float(d @ self.cam.f)
            return "free", self.cam.pos + s_ * d, None, None
        RIG.Binder.place = place
        sys.argv = [sys.argv[0], "--out", U.OUT]
        RIG.main()
    if part in ("anim", "all"):
        import pl32_claw_anim as ANIM   # 設計33 の ds33_claw_anim.py の写しに pl32_band_lift を足したもの
        sys.argv = [sys.argv[0], "--out", U.OUT]
        ANIM.main()
    for fn in ("ds33_claw_rig.json", "ds33_claw_layout.json", "ds33_claw_checks.json"):
        p = os.path.join(U.OUT, fn)
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            d["pl32_note_ja"] = ("仕上げ32：pl32_claws.py で、一覧と ID（Unity/Build/Polish/32/list）・主役波（Unity/Build/Polish/32/white/hero_pkg）・"
                                 "時間曲線（G_p28rec）・支の判定（branch_inside_tol 1e6）・根元の色区（PL29 の白の範囲）を差し替えて回した")
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
