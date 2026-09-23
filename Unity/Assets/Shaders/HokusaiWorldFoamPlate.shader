Shader "MasterProject/HokusaiWorldFoamPlate"
{
    Properties
    {
        _PlateColor ("版の色", Color) = (1, 0.988, 0.935, 1)
        _ShadowColor ("陰の色", Color) = (0.42, 0.64, 0.54, 1)
        _Alpha ("不透明度", Range(0, 1)) = 0.58
        _ShadowStrength ("陰の強さ", Range(0, 1)) = 0.42
        _EdgeInk ("縁の墨の強さ", Range(0, 1)) = 0.42
    }

    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent+16" }
        LOD 80

        Pass
        {
            Cull Off
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            ZTest Always
            Offset -2, -2

            CGPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            float4 _PlateColor;
            float4 _ShadowColor;
            float _Alpha;
            float _ShadowStrength;
            float _EdgeInk;

            struct appdata
            {
                float4 vertex : POSITION;
                float4 color : COLOR;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float4 color : COLOR;
                float2 uv : TEXCOORD0;
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.pos = mul(UNITY_MATRIX_VP, v.vertex);
                o.color = v.color;
                o.uv = v.uv;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float width01 = abs(i.uv.x - 0.5f) * 2.0f;
                float body = 1.0f - smoothstep(0.90f, 1.0f, width01);
                float rim = smoothstep(0.76f, 1.0f, width01);
                float shadowLane = smoothstep(0.52f, 1.0f, i.uv.x) * (1.0f - smoothstep(0.76f, 1.0f, width01));

                float brush = sin(i.uv.y * 41.0f) * 0.20f + sin(i.uv.y * 97.0f + 1.9f) * 0.16f;
                brush = lerp(0.92f, 1.0f, saturate(brush * 0.5f + 0.5f));

                float3 color = lerp(_PlateColor.rgb, _ShadowColor.rgb, shadowLane * _ShadowStrength);
                color = lerp(color, float3(0.020f, 0.055f, 0.115f), rim * _EdgeInk * 1.15f);

                float alpha = _Alpha * i.color.a * body * brush;
                alpha = max(alpha, _Alpha * i.color.a * rim * _EdgeInk * 0.78f);
                clip(alpha - 0.05f);

                return float4(color, alpha);
            }
            ENDCG
        }
    }
}
