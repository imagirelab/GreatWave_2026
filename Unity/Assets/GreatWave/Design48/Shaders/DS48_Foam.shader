// 設計48：船首の泡と航跡の平塗り（調色板の白・生成り、不透明、切り抜き）。Built-in、光を使わない（NPR）。
//   頂点の uv.x = 道の長さ方向の距離（m）、uv.y = 年齢の割合 life（0 = 新しい、1 以上 = 描かない）、uv2.x = 帯の横の位置（0〜1）。
//   life が _SolidLife までは切れ目のない白、その後は道の長さ方向の値の雑音で白がちぎれて減る（木版の泡の切れ切れの形の代わり）。
//   深度の検査は普通（LEqual）。主役波・船体の後ろでは隠れる。水面の網との z の競り合いを避けるため少しだけ手前へずらす。
Shader "GreatWave/DS48_Foam"
{
    Properties
    {
        _Color ("白・生成り", Color) = (0.98431, 0.96471, 0.89020, 1)
        _DashFreq ("道の長さ方向の雑音の細かさ（1/m）", Float) = 0.55
        _AcrossFreq ("横方向の雑音の細かさ", Float) = 2.5
        _SolidLife ("切れ目のない年齢の割合", Range(0, 1)) = 0.25
    }
    SubShader
    {
        Tags { "Queue" = "AlphaTest" "RenderType" = "TransparentCutout" "IgnoreProjector" = "True" }
        Pass
        {
            Cull Off
            ZWrite On
            ZTest LEqual
            Offset -1, -1
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            float4 _Color;
            float _DashFreq, _AcrossFreq, _SolidLife;
            struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD0; float2 uv2 : TEXCOORD1; };
            struct v2f { float4 pos : SV_POSITION; float3 d : TEXCOORD0; };
            v2f vert (appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.d = float3(v.uv.x, v.uv.y, v.uv2.x);
                return o;
            }
            float h21(float2 p) { p = frac(p * float2(123.34, 456.21)); p += dot(p, p + 45.32); return frac(p.x * p.y); }
            float vnoise(float2 p)
            {
                float2 i = floor(p), f = frac(p);
                float2 u = f * f * (3.0 - 2.0 * f);
                return lerp(lerp(h21(i), h21(i + float2(1, 0)), u.x), lerp(h21(i + float2(0, 1)), h21(i + float2(1, 1)), u.x), u.y);
            }
            fixed4 frag (v2f i) : SV_Target
            {
                float life = i.d.y;
                if (life >= 1.0) discard;
                float n = 0.65 * vnoise(float2(i.d.x * _DashFreq, i.d.z * _AcrossFreq)) + 0.35 * vnoise(float2(i.d.x * _DashFreq * 2.7 + 17.0, i.d.z * _AcrossFreq * 1.9 + 5.0));
                float k = saturate((life - _SolidLife) / max(1e-4, 1.0 - _SolidLife));
                clip(n - k);
                return fixed4(_Color.rgb, 1.0);
            }
            ENDCG
        }
    }
    Fallback Off
}
