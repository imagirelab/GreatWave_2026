"""contour -- 基準輪郭の抽出と輪郭指標の計算。

輪郭とテストの担当が管理する。基盤工程ではパッケージを用意するだけ。
gw.frame の座標規約に従う。画素座標は左上を原点とする連続座標、
シーン座標は H で正規化した (X_H, Z_H)、長さは画像高さに対する百分率で表す。
出力先は target/（base_contour.json、candidates/a、candidates/b）と
results/step1_prepare/。
"""
