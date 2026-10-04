// 美術の見本03 の作り B2（Q31）：SCULPT（彫刻の釉の艶と陰）。色は調べ S1 が彫刻の写真から測った色（白の釉・藍の釉・溝のコバルトの青）。
// 拡散：ワールドに固定した光（_LightDir）の回り込む拡散 × 焼いた見通し（keyVis）＋ 後ろからの補いの光 ＋ 半球の環境（空・海）× AO。
// 白は白のまま、光から背を向ける所は空の色の青灰の陰になる。稜（彫りの溝）は形（法線）と溝の底の暗さで読ませ、溝の中はコバルトの青。
// 艶：鋭い鏡の光（Blinn–Phong）と、周りの映り込み（空・海・窓の光。フレネルで縁ほど強い）。艶だけが見る位置で動く（本物の釉と同じ）。
// 描いた線はない（彫刻に線はない、S1）。色・模様・拡散は視点によらない。原画カメラの投影は使わない（Q28）。
// 名前に Keypose を含むのは、ID の描画（KeepMaterial）がこの材質を残すため。
Shader "GreatWave/ArtSample03/AS03 Sculpt Keypose"
{
    Properties
    {
        _AS03Src ("頂点の出どころ（0 keypose の主役波、1 主役波の静止のメッシュ、2 冠・爪の白い釉）", Float) = 1
        _WhiteSrc ("白の境（0 見本02 の式、1 頂点の whiteSD）", Float) = 0
        _MeshUseUV5 ("冠・爪：UV5 の (ao, keyVis, whiteSD) を使う（0 なら全部白・陰なし）", Float) = 1
        _MeshMizuiro ("冠・爪：淡い水色へ寄せる割合（鉤の内の面）", Float) = 0
        _MeshTint ("冠・爪の色の掛け算", Color) = (1, 1, 1, 1)
        _White ("白の釉", Color) = (0.94118, 0.94118, 0.92549, 1)
        _WhiteShade ("白の陰（ID の読みだけ）", Color) = (0.79608, 0.84314, 0.80784, 1)
        _AiRidge ("稜の藍の釉", Color) = (0.08627, 0.12549, 0.25098, 1)
        _AiRidgeLit ("（FLAT だけ）", Color) = (0.17255, 0.41176, 0.57647, 1)
        _AiDeep ("（FLAT だけ）", Color) = (0.07843, 0.14902, 0.25098, 1)
        _GrooveCol ("溝のコバルトの青", Color) = (0.25882, 0.40000, 0.61961, 1)
        _GrooveShade ("（FLAT だけ）", Color) = (0.14118, 0.31373, 0.47843, 1)
        _LineCol ("（FLAT だけ）", Color) = (0.12157, 0.23529, 0.36863, 1)
        _Groove ("稜：x 深さ／周期（keypose の道）, y 溝の幅／周期, z 玉縁, w 断面の指数", Vector) = (0.15, 0.244, 0.18, 2.2)
        _GrooveLod ("稜：x, y 子の溝の段の端数, z, w 消す画面の周期（画素）", Vector) = (0.22, 0.48, 4, 12)
        _GrooveLam ("稜の周期／H：x 下の面, y 中ほど, z 冠の下, w H0 m", Vector) = (0.056, 0.045, 0.035, 20.753)
        _GrooveOn ("稜：x 描く, y keypose の道の現れの長さ m, z 法線の傾きの強さ, w 溝の底の暗さ", Vector) = (1, 2.5, 1, 0.45)
        _BackB ("見本02 の背の白の境", Vector) = (0.42, 0.02, 16, 0)
        _CapFront ("見本02 の頂の白の前の縁", Vector) = (1.6, 2.6, 0.9, 1)
        _MinRowH ("白を付ける行の頂の高さの下限（H0 の倍）", Float) = 0.08
        _EdgeLinePx ("（使わない。彫刻に線はない）", Float) = 0
        _EdgeGrazing ("（使わない）", Vector) = (0.06, 0.2, 0, 0)
        _AAScale ("アンチエイリアスの幅（画素）", Float) = 1
        _LightDir ("固定の光の向き（ワールド、光の来る向き）", Vector) = (-0.45, 0.75, -0.5, 0)
        _FillDir ("補いの光の向き（前の低い所から。影なし）", Vector) = (-0.15, 0.30, -0.95, 0)
        _KeyCol ("主の光の色と強さ", Color) = (0.86, 0.85, 0.83, 1)
        _FillCol ("補いの光", Color) = (0.30, 0.31, 0.34, 1)
        _SkyCol ("空の環境（上）", Color) = (0.60, 0.62, 0.66, 1)
        _GroundCol ("海・台の照り返し（下）", Color) = (0.62, 0.64, 0.66, 1)
        _EnvHorizon ("映り込みの地平", Color) = (0.36, 0.38, 0.40, 1)
        _EnvSky ("映り込みの空", Color) = (0.20, 0.26, 0.38, 1)
        _EnvGround ("映り込みの地", Color) = (0.04, 0.05, 0.07, 1)
        _EnvWin ("映り込みの窓の光", Color) = (1, 1, 1, 1)
        _EnvWinK ("窓の光の強さ（釉に映る明るい窓。正面でも見える長い映り込み。回 7 の 6 は藍の背が金物のように灰色に光った）", Float) = 3
        _WinDir ("窓の光の向き（ワールド）, w 鋭さ", Vector) = (0.6, 0.55, -0.6, 10)
        _Wrap ("x 回り込み, y 焼いた影の強さ, z AO の強さ, w （FLAT だけ）", Vector) = (0.45, 0.8, 0.7, -0.08)
        _SpecWhite ("白の艶：x 鋭さ, y 強さ, z 映り込み, w F0", Vector) = (220, 0.5, 0.5, 0.04)
        _SpecAi ("藍の艶：x 鋭さ, y 強さ, z 映り込み, w F0", Vector) = (160, 0.8, 1.0, 0.04)
        _FlatRib ("（FLAT だけ）", Vector) = (0, 0.16, 0, 0)
        _Shoulder ("明るい所の肩（線形の値がこれより上をなめらかに 1 へ寄せる。白が飛ばないように）", Float) = 0.8
        _SeaCol ("主役波の裾の色（周りの海の藍濃に合わせる）", Color) = (0.13725, 0.25098, 0.38039, 1)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "AS03Sculpt"
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
                float4 dg = AS03Diag(i, s, false, 1.0);
                if (dg.w > 0.0) return dg;
                float3 L = normalize(_LightDir.xyz);
                float3 Lf = normalize(_FillDir.xyz);
                float3 V = normalize(DS27CentreEye() - i.wp);
                float3 n = s.n;
                if (dot(n, V) < 0.0 && dot(s.n0, V) > 0.0) n = normalize(n - 1.05 * dot(n, V) * V);   // 稜の傾きで裏を向いた画素は縁へ寝かせる
                float3 albedo = lerp(lerp(_AiRidge.rgb, _GrooveCol.rgb, s.lineCov), _White.rgb, s.whiteCov);
                if (s.glaze > 0.5) albedo = lerp(albedo, lerp(albedo, _WhiteShade.rgb * 0.9, _MeshMizuiro), s.whiteCov) * _MeshTint.rgb;
                float wrap = _Wrap.x;
                float key = saturate((dot(n, L) + wrap) / (1.0 + wrap)) * s.kv;
                float fill = saturate(dot(n, Lf));
                float3 amb = lerp(_GroundCol.rgb, _SkyCol.rgb, saturate(0.5 + 0.5 * n.y)) * s.ao;
                float cav = 1.0 - _GrooveOn.w * s.grooveDepthFrac * (1.0 - s.lineCov);   // 溝の壁の陰（溝の中の線そのものは玉縁で光を受ける）
                float3 diff = albedo * (_KeyCol.rgb * key + _FillCol.rgb * fill + amb) * cav;
                float4 sp = lerp(_SpecAi, _SpecWhite, s.whiteCov);
                float3 H = normalize(L + V);
                float nh = saturate(dot(n, H));
                float spec = pow(nh, sp.x) * sp.y * s.kv * step(0.0, dot(n, L));
                float3 Hf = normalize(Lf + V);
                spec += pow(saturate(dot(n, Hf)), sp.x) * sp.y * 0.45 * step(0.0, dot(n, Lf));   // 補いの光の鏡の光（影なし）
                float nv = saturate(dot(n, V));
                float fres = sp.w + (1.0 - sp.w) * pow(1.0 - nv, 5.0);
                float3 R = reflect(-V, n);
                float3 env = AS03Env(R) * sp.z * fres * lerp(1.0, s.ao, 0.7) * cav;
                float3 col = diff * (1.0 - fres * sp.z) + env + spec * _KeyCol.rgb;
                // 明るい所の肩：_Shoulder より上を 1 へなめらかに寄せる（白い釉の明るさの段が飛ばずに残る。線形の色空間の値）
                // 主役波の裾は周りの海（PL30 の平らな藍）へ寄せる：艶をやめ、藍濃の平らな色と固定の光の弱い段だけ（回 8 で裾が暗い艶の水たまりに見えた）
                float seaLit = saturate(0.5 + (dot(s.n0, L) + 0.08) / max(fwidth(dot(s.n0, L)), 1e-4));
                col = lerp(col, _SeaCol.rgb * lerp(0.78, 1.0, seaLit), s.sea * (1.0 - s.whiteCov));
                float sh = _Shoulder, rg = max(1.0 - sh, 1e-3);
                col = col > sh ? sh + rg * (1.0 - exp(-(col - sh) / rg)) : col;
                return float4(col, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
