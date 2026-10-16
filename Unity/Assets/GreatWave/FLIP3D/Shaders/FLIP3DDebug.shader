// FLIP3D：確かめ用（2026-10-16、進行役）。表は法線の色（x→赤・上→緑・横→青を 0.5 + 0.5 n）、裏はマゼンタ。形は変えない。
Shader "GreatWave/FLIP3D/Debug"
{
    SubShader
    {
        Tags { "RenderType" = "Opaque" }
        Pass
        {
            Cull Off
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.0
            #include "UnityCG.cginc"
            struct v2f { float4 pos : SV_POSITION; float3 wn : TEXCOORD0; };
            v2f vert (appdata_base v) { v2f o; o.pos = UnityObjectToClipPos(v.vertex); o.wn = UnityObjectToWorldNormal(v.normal); return o; }
            float4 frag (v2f i, float face : VFACE) : SV_Target
            {
                if (face < 0) return float4(1, 0, 1, 1);
                return float4(0.5 + 0.5 * normalize(i.wn), 1);
            }
            ENDCG
        }
    }
}
