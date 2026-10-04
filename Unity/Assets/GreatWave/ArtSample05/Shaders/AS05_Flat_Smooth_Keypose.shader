// 美術の見本05 の材質（Q33、2026-10-04）：AS05 Flat Smooth。見本04 の AS04F Flat Smooth（変えない）の写しで、波の本体の白い点（粒）を外した（要求書 T5）。
// 唇の下の内の縁（T6）は頂点の白の印（Tools/GWWaveGen/as05/mat_edge.py）で扱う。ほかは AS04F と同じ。
// 美術の見本04 の調べ M（Q32、2026-10-04）：AS04 Flat Smooth。原画の平らな塗りで、滑らかな面（彫りの凹凸・冠・泡の皮・滴なし）。
// 見本03 の AS03 Flat Keypose（変えない）から作り直した。光・艶・形の陰影はない：色は頂点の属性で決まる平らな色の区域だけ（AS04Common.cginc）。
// 限られた色（紙の白・水色・藍中・藍濃・藍の線。設計36・要求書 T3、原画の色は Tools/PaintingTruth/targets/palette.json の値）。
// 1 パス（Built-in の ForwardBase）、視点によらない（同じ面はどこから見ても同じ色。画面の量は線の太さ・アンチエイリアス・小さすぎる点の省きだけ）。
// 原画カメラの投影は使わない（Q28）。名前に Keypose を含むのは、ID の描画（KeepMaterial）がこの材質を残すため。
// 名前に空白を入れないのは、描画の道具の引数（-as03Shader・-s01HeroShader）が空白で区切られ、-s01HeroShader は _ を空白に直さないため。
Shader "GreatWave/ArtSample05/AS05FlatSmoothKeypose"
{
    Properties
    {
        _AS03Src ("頂点の出どころ（0 keypose の主役波、1 主役波の静止のメッシュ、2 爪などのメッシュ）", Float) = 1
        _MeshUseUV5 ("爪など：UV5 の whiteSD を使う（0 なら全部白）", Float) = 1
        _MeshMizuiro ("爪など：水色へ寄せる割合（鉤の内の膜）", Float) = 0
        _MeshTint ("爪などの色の掛け算", Color) = (1, 1, 1, 1)
        _MeshRim ("爪などの縁の藍の線：x |n·v| がこれ未満で線, y 1 で描く", Vector) = (0.28, 1, 0, 0)
        _White ("紙の白", Color) = (0.98431, 0.96471, 0.89020, 1)
        _Mizuiro ("水色", Color) = (0.75294, 0.82745, 0.78039, 1)
        _AiMid ("藍中（帯）", Color) = (0.16078, 0.41176, 0.58039, 1)
        _AiDark ("藍濃（地）", Color) = (0.13333, 0.24706, 0.37647, 1)
        _LineCol ("藍の線", Color) = (0.08627, 0.15686, 0.26667, 1)
        _SeaCol ("裾の色（周りの海へ寄せる）", Color) = (0.13333, 0.24706, 0.37647, 1)
        _SeaBlend ("裾を周りの海の色へ寄せる強さ", Float) = 1
        _Band ("帯の幅：x 中央（周期 λ の倍）, y 対数のばらつき, z 最小, w 最大", Vector) = (0.18, 0.77, 0.06, 0.62)
        _BandVar ("帯：x 中心のずれ（λ の倍の幅）, y 太さの揺れの波長 m, z 揺れの振幅, w 頂の側で太りきる長さ m", Vector) = (0.5, 5.0, 0.55, 1.5)
        _BandOn ("帯：x 描く, y 白の境からの始まり m, z, w 消す画面の周期（画素）", Vector) = (1, 0.15, 3, 8)
        _BandBack ("帯：背の藍（u < 0）に描く強さ（0 で描かない、1 で前と同じ）", Float) = 1
        _Fork ("帯：x, y 子の帯が分かれる段の端数, z 消した所の平均の被覆", Vector) = (0.22, 0.48, 0.24, 0)
        _BandLam ("keypose の道の λ(y)／H：x 下の面, y 中ほど, z 冠の下, w H0 m", Vector) = (0.056, 0.045, 0.035, 20.753)
        _MizuInset ("白の前の縁の水色：境から白のまま残す幅 m（白い舌の先）", Float) = 0.3
        _MizuFringe ("白の前の縁の水色：x 最小の幅 m, y 最大の幅 m, z 揺れの波長 m, w 描く", Vector) = (0.25, 1.3, 3.0, 1)
        _EdgeLinePx ("白と藍の境の線（画素。0 で描かない）", Float) = 1.2
        _EdgeGrazing ("線を薄める面の傾き（x 消える |n·v|, y 全部）", Vector) = (0.06, 0.2, 0, 0)
        _AAScale ("アンチエイリアスの幅（画素）", Float) = 1
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "AS05FlatSmooth"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile _ DS27_POS_LO
            #include "AS05Common.cginc"

            AS05V2F vert(AS05In v) { return AS05Vert(v); }

            float4 frag(AS05V2F i, bool front : SV_IsFrontFace) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                AS05Surf s = AS05Pattern(i, front);
                float4 dg = AS05Diag(i, s);
                if (dg.w > 0.0) return dg;
                float3 V = normalize(DS27CentreEye() - i.wp);
                float nv = abs(dot(s.n0, V));
                if (s.glaze > 0.5)
                {
                    // 爪など：平らな白（膜は水色）、縁に藍の線
                    float3 cw = lerp(_White.rgb, _Mizuiro.rgb, _MeshMizuiro) * _MeshTint.rgb;
                    float3 cb = lerp(_AiDark.rgb, cw, s.whiteCov);
                    if (_MeshRim.y > 0.5)
                    {
                        float rim = saturate(0.5 + (_MeshRim.x - nv) / max(fwidth(nv), 1e-4));
                        cb = lerp(cb, _LineCol.rgb, rim);
                    }
                    return float4(cb, 1);
                }
                // 藍の地 → 藍中の帯 → 裾（AS05：波の本体の白い点はない）
                float3 body = lerp(_AiDark.rgb, _AiMid.rgb, s.bandCov);
                body = lerp(body, _SeaCol.rgb, saturate(s.sea * _SeaBlend));
                // 白（前の縁は水色）
                float3 white = lerp(_White.rgb, _Mizuiro.rgb, s.mizuCov);
                float3 col = lerp(body, white, s.whiteCov);
                if (_EdgeLinePx > 0.0)
                {
                    float lineCov = saturate(0.5 * _EdgeLinePx + 0.5 - abs(s.zWhite));
                    lineCov *= saturate((nv - _EdgeGrazing.x) / max(_EdgeGrazing.y - _EdgeGrazing.x, 1e-3));
                    col = lerp(col, _LineCol.rgb, lineCov);
                }
                return float4(col, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
