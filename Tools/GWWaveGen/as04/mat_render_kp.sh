#!/usr/bin/env bash
# 美術の見本04 の調べ M：同じ AS04 Flat Smooth が keypose の主役波（_AS03Src 0。DS30SheetPlayer、形成の動きでも使える道）にも効くことの確かめ。
# 属性は見本03 の surf_kp_attr.py の出力（見本02 の 12 個の C.w に白の印 v2 の whiteSD を入れたもの、変えない）。値の表は as04_flat_smooth_params.txt ＋ _AS03Src=0。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample04/mat/render/ の下）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/mat/render
LG=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/mat/logs
TA=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31; B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30; S2=Build/Polish/sample02/fix01
CL=Build/Polish/sample03/assemble/claws35/ds33_claw_layout.json; HERO_PKG=$S2/assemble/hero_pkg_AS02C; HERO_GWB=$S2/back/final/cand/kstarAS02C_a45.gwb
PKP=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/mat/params_kp.txt
{ cat $TA/as04_flat_smooth_params.txt; echo "_AS03Src=0"; } > $PKP
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as04/mat_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,back65 -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 0 -pl31TtSpray 0"
SH=GreatWave/ArtSample04/AS04FlatSmoothKeypose
$U -Method GreatWave.ArtSample03.EditorTools.AS03AsmRender.Render -Log $1_views -Extra "$V -pl29Out $B/$1 $S $M -pl29Attr Build/Polish/sample03/surface/attr/as03_kp_attr_f32.bin -pl29ParamFile $PKP -s01HeroShader $SH -as03ClawGlaze $SH -as03ClawParams $TA/as04_flat_smooth_params.txt -pl29Only views" > $LG/run_$1_views.txt 2>&1
tail -1 $LG/run_$1_views.txt
grep -E "AS03ASM_RENDER_DONE|error CS|Exception|ERROR" $LG/unity_as04mat_$1_views.log | head -5
