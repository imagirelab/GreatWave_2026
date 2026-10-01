# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP の採用の設計（名前の付いた値）。faceswap_build.py が読む（py -3.10 faceswap_build.py faceswap_design_r1.py <out_prefix>）。
手順（steps の順）
  face_swap_arc     肩の行（c −24〜−2、端はなめらかに 0）で、列 55〜148 を 2 本の 3 次エルミート曲線で組み直し、頂を前へ fwd_m（最大 2.0 m）移す。
                    新しい頂の高さは、その行の原画の射線の面（視錐の跡）の、新しい頂の a での高さ（元の頂からの差を c に沿って σ 2 m でならし、各行の接する差以下）。
                    組み直しの変位は c に沿って σ 1 m、列に沿って σ 3 列でならす（行と行の間の縞を消す）。→ 左の外輪郭 78・130・131 を前の唇の上面が描く。
  tail_round        手前の尾（c ≤ −26.5、原画の枠の外）の頂を、同じ高さの cos² のうねりの上半分（0.5 H より上）と元の行のなめらかな max で丸める
                    （頂の ±2 m の弦の角 ≥ 120° を狙う。裾は元の背と前のまま＝背の足の線に段を作らない。Q17）。−26.5〜−23.8 は頂を揃えて混ぜる。
  wall_guard        背が管の内側の壁へ近づきすぎた所を戻す（厚み ≥ min(R4, 0.22 H)）。この設計では動かす所なし（記録）。
  bsfit_lead        原画視点の 78・130・131・132（132 は σ12 の大きな輪郭）を、なめらかな B スプラインの場（行 22 × 列 11 の係数、c −30〜+3、列 50〜185、
                    断面の法線の向き）で合わせる（ガウス・ニュートン 6 回）。場がなめらかなので、しわ・折れを作らない。
  edgefit_72        72（σ12 の大きな輪郭、爪の湾を含む）を唇の下と管の縁の頂点だけで合わせる（側の縁。Q21）。奥の端の最後の小さな行（c > 14.2）は動かさない。
  edgefit_all_small 5 本の輪郭を、1 回 0.05 m 以下の小さな動きで仕上げる。
  uncross_lip       唇の上面（列 100〜199）と下面・管（列 201〜320）の断面の交差がある行だけ、唇の領域を R4 へ最小の割合で混ぜ戻す（網の衛生。
                    交差は 132 の大きな輪郭へ唇の頭の前を寄せた所で、c +1.2〜+2.0 に出た）。
参照モデル（他者の作品）は読まない（F13-1）。入力は K*′ R4 の行（Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_rows.npz）だけ。
"""
DESIGN = {'steps': ['face_swap_arc', 'tail_round', 'wall_guard', 'bsfit_lead', 'edgefit_72', 'edgefit_all_small', 'uncross_lip'],
 'face_swap_arc': {'rows_ramp_c': [-24, -18, -7, -2.0],
                   'crest_col': 90,
                   'j0': 55,
                   'j1': 148,
                   'fwd_m': 2.0,
                   'margin_m': 0.0,
                   'smooth_c_m': 2.0,
                   'tan_scale': 0.85,
                   'solve_touch': False,
                   'smooth_disp_c_m': 1.0,
                   'smooth_disp_cols': 3.0},
 'tail_round': {'c_full': -26.5, 'c_end': -23.8, 'chord_min_deg': 120.0, 'keep_flanks': True, 'smoothmax_k': 4.0, 'cap_only_frac': 0.5},
 'wall_guard': {'tau': 0.22},
 'bsfit_lead': {'rows_c': [-30, 3.0],
                'cols': [50, 185],
                'n_c': 22,
                'n_j': 11,
                'segments': ['78', '130', '131', '132'],
                'iters': 6,
                'lam': 0.5,
                'smooth': 2.0},
 'edgefit_72': {'segments': ['72'], 'rows_c': [-60.0, 14.2], 'iters': 12, 'sigma_c': 1.2, 'sigma_s': 1.3, 'sigma_j': 16.0, 'damp': 0.7, 'max_move': 0.3},
 'edgefit_all_small': {'segments': ['78', '130', '131', '132', '72'],
                       'rows_c': [-60.0, 14.2],
                       'iters': 8,
                       'sigma_c': 1.2,
                       'sigma_s': 1.5,
                       'sigma_j': 18.0,
                       'damp': 0.7,
                       'max_move': 0.05},
 'uncross_lip': {'top_cols': [100, 199], 'under_cols': [201, 320], 'cols_ramp': [95, 120, 260, 290], 'pad_m': 0.6, 'extra': 0.1}}
