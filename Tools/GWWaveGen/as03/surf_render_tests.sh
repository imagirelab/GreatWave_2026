#!/usr/bin/env bash
# 美術の見本03 の作り B2：同じシェーダーが、keypose の主役波（_AS03Src 0、形成の動きでも使える道）・見本02 の爪（_AS03Src 2）・B1 の冠（-as03Crown）
# にも効くことの確かめの描画。引数 1 = 彫りの面のメッシュの名前（surface/mesh/<名前>.json）、2 = 版の印（出力のフォルダー名の後ろ）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
MN=$1; TG=$2
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/surface/render
LG=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/surface/logs
MESH=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/surface/mesh
TA=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as03
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31; B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30; S2=Build/Polish/sample02/fix01
CL=$S2/assemble/claws/mesh/ds33_claw_layout.json; HERO_PKG=$S2/assemble/hero_pkg_AS02C; HERO_GWB=$S2/back/final/cand/kstarAS02C_a45.gwb
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as03/surf_unity.ps1 -LogDir $LG"
CROWN=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/crown/OUT/as03_crown.json
# 1) keypose の主役波に SCULPT（稜は画素の傾きだけ。白は B1 の白の印を属性 C.w に入れたもの）
V1="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 0 -as01ViewSpray 0 -s01TtClaws 0 -pl31TtSpray 0"
$U -Method GreatWave.ArtSample03.EditorTools.AS03SurfRender.Render -Log B2_kp_$TG -Extra "$V1 -pl29Out $B/B2_kp_$TG $S $M -pl29Attr Build/Polish/sample03/surface/attr/as03_kp_attr_f32.bin -pl29ParamFile $TA/surf_sculpt_kp_params.txt -s01HeroShader GreatWave/ArtSample03/AS03_Sculpt_Keypose -pl29Only views" > $LG/run_B2_kp_$TG.txt 2>&1
grep -E "AS03SURF_RENDER_DONE|error CS|Exception" $LG/unity_as03b2_B2_kp_$TG.log | head -3
# 2) 爪にも同じ式（SCULPT・FLAT）
for m in Sculpt Flat; do
  PF=$TA/surf_$(echo $m | tr 'A-Z' 'a-z')_params.txt
  V2="-pl29Views painting,seat,seat_toward_wave,side_left,back65 -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 0 -pl31TtSpray 0"
  $U -Method GreatWave.ArtSample03.EditorTools.AS03SurfRender.Render -Log B2_claws_${m}_$TG -Extra "$V2 -pl29Out $B/B2_claws_${m}_$TG $S $M -as03Surf $MESH/$MN.json -as03Shader GreatWave/ArtSample03/AS03_${m}_Keypose -as03Params $PF -as03ClawGlaze GreatWave/ArtSample03/AS03_${m}_Keypose -as03ClawParams $PF -pl29Only views" > $LG/run_B2_claws_${m}_$TG.txt 2>&1
  grep -E "AS03SURF_RENDER_DONE|error CS|Exception" $LG/unity_as03b2_B2_claws_${m}_$TG.log | head -3
done
# 3) B1 の冠（作業中の版）を同じ材質で
if [ -f $CROWN ]; then
  for m in sculpt flat; do bash Tools/GWWaveGen/as03/surf_render.sh B2_crowntest_${m}_$TG views,crest $m $MN -as03Crown $CROWN 2>&1 | grep -E "DONE|Exception|error" | head -2; done
fi
date
