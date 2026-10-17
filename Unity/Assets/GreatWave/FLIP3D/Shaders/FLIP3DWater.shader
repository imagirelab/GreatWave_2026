// FLIP3D：簡単な水の陰影（2026-10-16、進行役）。Built-in の ForwardBase 1 パス、霧に対応。形（頂点）は変えない。
// 色＝深い水の色と、空の映り込み（Fresnel、空は上と地平の 2 色の傾き）と、太陽の照り返し（Blinn）。浮世絵の描き方は後の段。
Shader "GreatWave/FLIP3D/Water"
{
    Properties
    {
        _Deep ("Deep", Color) = (0.035, 0.150, 0.190, 1)
        _Lit ("Lit body", Color) = (0.090, 0.340, 0.380, 1)
        _SkyTop ("Sky top", Color) = (0.30, 0.44, 0.62, 1)
        _SkyHorizon ("Sky horizon", Color) = (0.58, 0.67, 0.74, 1)
        _SunPower ("Sun power", Float) = 600
        _SunScale ("Sun scale", Float) = 3.0
        _F0 ("F0", Float) = 0.02
        _Wrap ("Diffuse wrap", Float) = 0.3
        // 2026-10-17 追記（Claude）：両面の表示（表示だけ。形は変えない）。既定 2 = Back で前と同じ。FLIP3DPlayer が manifest の water_double_sided: true の
        // クリップの時だけ、実行中に作る材質の写しに 0 = Off と印 GW_WATER_DOUBLE_SIDED を入れる（材質の資産は変えない）
        [HideInInspector] _GWCull ("Cull (2 back = before; 0 both sides for water_double_sided clips)", Float) = 2
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" }
        Pass
        {
            Tags { "LightMode" = "ForwardBase" }
            Cull [_GWCull]
            ZWrite On
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #pragma multi_compile_local _ GW_WATER_DOUBLE_SIDED
            #include "UnityCG.cginc"
            #include "Lighting.cginc"

            float4 _Deep, _Lit, _SkyTop, _SkyHorizon;
            float _SunPower, _SunScale, _F0, _Wrap;

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 wpos : TEXCOORD0;
                float3 wn : TEXCOORD1;
                UNITY_FOG_COORDS(2)
            };

            v2f vert (appdata_base v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.wpos = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.wn = UnityObjectToWorldNormal(v.normal);
                UNITY_TRANSFER_FOG(o, o.pos);
                return o;
            }

#ifdef GW_WATER_DOUBLE_SIDED
            float4 frag (v2f i, fixed facing : VFACE) : SV_Target
#else
            float4 frag (v2f i) : SV_Target
#endif
            {
                float3 n = normalize(i.wn);
#ifdef GW_WATER_DOUBLE_SIDED
                // 裏の面（記録の面の穴の向こうに見える、水の向こう側の面）は法線を裏返し、表と同じ式で塗る。印のない時（前の全部のクリップ）はこの行がない
                n = facing > 0 ? n : -n;
#endif
                float3 v = normalize(_WorldSpaceCameraPos - i.wpos);
                float3 l = normalize(_WorldSpaceLightPos0.xyz);
                float ndv = saturate(dot(n, v));
                float fres = _F0 + (1.0 - _F0) * pow(1.0 - ndv, 5.0);
                float3 r = reflect(-v, n);
                // 空の映り込み：上は空の 2 色、下向きの反射（ほかの水面を映す）へは滑らかにつなぐ（段をつけると暗い帯が出た）
                float3 sky = lerp(_SkyHorizon.rgb, _SkyTop.rgb, saturate(r.y * 1.5));
                sky = lerp(sky, _Lit.rgb, saturate(-r.y * 3.0));
                float ndl = saturate((dot(n, l) + _Wrap) / (1.0 + _Wrap));
                float3 body = lerp(_Deep.rgb, _Lit.rgb, ndl) * _LightColor0.rgb;
                float3 h = normalize(l + v);
                float spec = pow(saturate(dot(n, h)), _SunPower) * _SunScale;
                float3 col = lerp(body, sky, fres) + spec * _LightColor0.rgb;
                UNITY_APPLY_FOG(i.fogCoord, col);
                return float4(col, 1.0);
            }
            ENDCG
        }
    }
    Fallback Off
}
