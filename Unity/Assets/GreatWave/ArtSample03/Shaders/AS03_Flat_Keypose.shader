// 美術の見本03 の作り B2（Q31）：FLAT（浮世絵の平らな色）。限られた色（白・淡い水色・藍中・藍濃・藍の陰・藍の線、設計36・要求書 T3）で、
// 稜（彫りの溝）は色で描く（藍濃の稜と、その間の細い溝の藍中の線。周期・幅・Y 字は S1 の数、AS03Common.cginc）。
// 陰はワールドに固定した光（_LightDir）と滑らかな法線の内積の 2 段（白 → 淡い水色、藍 → 藍の陰）と、焼いた固定の光の見通し（keyVis）。
// 稜は光を向く半分が藍濃、背を向ける半分が藍の陰の 2 段（_FlatRib）。白と藍の境に細い藍の線（_EdgeLinePx、0 で描かない）。
// 色・段は視点によらない（同じ面はどこから見ても同じ色。画面の量は線の太さとアンチエイリアスだけ）。原画カメラの投影は使わない（Q28）。
// 名前に Keypose を含むのは、ID の描画（KeepMaterial）がこの材質を残すため。
Shader "GreatWave/ArtSample03/AS03 Flat Keypose"
{
    Properties
    {
        _AS03Src ("頂点の出どころ（0 keypose の主役波、1 主役波の静止のメッシュ、2 冠・爪の白い釉）", Float) = 1
        _WhiteSrc ("白の境（0 見本02 の式、1 頂点の whiteSD）", Float) = 0
        _MeshUseUV5 ("冠・爪：UV5 の (ao, keyVis, whiteSD) を使う（0 なら全部白・陰なし）", Float) = 1
        _MeshMizuiro ("冠・爪：淡い水色へ寄せる割合（鉤の内の面）", Float) = 0
        _MeshTint ("冠・爪の色の掛け算", Color) = (1, 1, 1, 1)
        _White ("白", Color) = (0.97255, 0.95294, 0.87451, 1)
        _WhiteShade ("白の陰（淡い水色）", Color) = (0.79608, 0.84314, 0.80784, 1)
        _AiRidge ("稜（藍濃）", Color) = (0.13725, 0.25098, 0.38039, 1)
        _AiRidgeLit ("（使わない）", Color) = (0.17255, 0.41176, 0.57647, 1)
        _AiDeep ("藍の陰", Color) = (0.07843, 0.14902, 0.25098, 1)
        _GrooveCol ("溝の線（藍中）", Color) = (0.17255, 0.41176, 0.57647, 1)
        _GrooveShade ("溝の線の陰", Color) = (0.11765, 0.28235, 0.42353, 1)
        _LineCol ("藍の線", Color) = (0.12157, 0.23529, 0.36863, 1)
        _Groove ("稜：x 深さ／周期（keypose の道）, y 溝の幅／周期, z 玉縁, w 断面の指数", Vector) = (0.15, 0.244, 0.18, 2.2)
        _GrooveLod ("稜：x, y 子の溝の段の端数, z, w 消す画面の周期（画素）", Vector) = (0.22, 0.48, 4, 12)
        _GrooveLam ("稜の周期／H：x 下の面, y 中ほど, z 冠の下, w H0 m", Vector) = (0.056, 0.045, 0.035, 20.753)
        _GrooveOn ("稜：x 描く, y keypose の道の現れの長さ m, z 法線の傾きの強さ, w 溝の底の暗さ", Vector) = (1, 2.5, 1, 0.35)
        _BackB ("見本02 の背の白の境（x 行の相対の高さ, y うねり, z 波長 m, w 第 2 のうねり）", Vector) = (0.42, 0.02, 16, 0)
        _CapFront ("見本02 の頂の白の前の縁（x u m, y 房の周期 m, z 房の深さ m, w 1 で房）", Vector) = (1.6, 2.6, 0.9, 1)
        _MinRowH ("白を付ける行の頂の高さの下限（H0 の倍）", Float) = 0.08
        _EdgeLinePx ("白と藍の境の線（画素。0 で描かない）", Float) = 1.2
        _EdgeGrazing ("線を薄める面の傾き（x 消える |n·v|, y 全部）", Vector) = (0.06, 0.2, 0, 0)
        _AAScale ("アンチエイリアスの幅（画素）", Float) = 1
        _LightDir ("固定の光の向き（ワールド、光の来る向き）", Vector) = (-0.45, 0.75, -0.5, 0)
        _Wrap ("x 未使用, y 焼いた影（固定の光の見通し）の強さ（FLAT は既定 0：浮世絵に落ちる影はない）, z AO を読む（1）, w 陰の段の閾値（n·L）", Vector) = (0.5, 0, 1, -0.08)
        _FlatRib ("稜の 2 段：x 強さ（0 で稜は一色）, y 光の側へ寄せる量（n·L の差）", Vector) = (1, 0.04, 0, 0)
        _FlatAO ("面の遮りの段：x AO がこれ未満で陰の色（白 → 淡い水色、藍 → 藍の陰）, y 強さ", Vector) = (0.55, 1, 0, 0)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "AS03Flat"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile _ DS27_POS_LO
            #include "AS03Common.cginc"

            AS03V2F vert(AS03In v) { return AS03Vert(v); }

            float4 frag(AS03V2F i, bool front : SV_IsFrontFace) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                AS03Surf s = AS03Pattern(i, front);
                float3 L = normalize(_LightDir.xyz);
                // 2 段の陰（滑らかな法線と固定の光、焼いた見通し）
                float ndl = dot(s.n0, L) - _Wrap.w;
                float lit = saturate(0.5 + ndl / max(fwidth(ndl), 1e-4));
                lit = min(lit, saturate((s.kv - 0.5) * 8.0 + 0.5));
                float aoz = (s.ao - _FlatAO.x);
                float litW = min(lit, lerp(1.0, saturate(0.5 + aoz / max(fwidth(aoz), 1e-4)), _FlatAO.y));   // 白の凹んだ所（唇の下・背の裾）は淡い水色の段（藍には AO の段を付けない。回 3 で藍がまだらになった）
                // 稜の 2 段：稜の傾きを足した法線が光を向く半分は藍濃、背を向ける半分は藍の陰（版木の彫りのような平らな 2 色の稜）
                float rib = dot(s.n, L) - dot(s.n0, L) + _FlatRib.y;
                float ribLit = lerp(1.0, saturate(0.5 + rib / max(fwidth(rib), 1e-4)), _FlatRib.x);
                float3 ridge = lerp(_AiDeep.rgb, _AiRidge.rgb, lit * ribLit);
                float3 groove = lerp(_GrooveShade.rgb, _GrooveCol.rgb, lit);
                float3 body = lerp(ridge, groove, s.lineCov);
                float4 dg = AS03Diag(i, s, true, litW);
                if (dg.w > 0.0) return dg;
                float3 white = lerp(_WhiteShade.rgb, _White.rgb, litW);
                if (s.glaze > 0.5) white = lerp(white, _WhiteShade.rgb, _MeshMizuiro) * _MeshTint.rgb;
                float3 col = lerp(body, white, s.whiteCov);
                if (_EdgeLinePx > 0.0)
                {
                    float lineCov = saturate(0.5 * _EdgeLinePx + 0.5 - abs(s.zWhite));
                    float3 V = normalize(DS27CentreEye() - i.wp);
                    float nv = abs(dot(s.n0, V));
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
