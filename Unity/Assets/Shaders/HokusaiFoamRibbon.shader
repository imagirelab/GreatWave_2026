Shader "MasterProject/HokusaiFoamRibbon"
{
    Properties
    {
        _RibbonColor ("Ribbon Foam Color", Color) = (0.96, 0.93, 0.82, 0.35)
        _EdgeColor ("Soft Edge Color", Color) = (0.47, 0.63, 0.72, 0.18)
        _EdgeBlend ("Edge Blend", Range(0, 1)) = 0.28
        _ShadowOffset ("Shadow Offset", Range(0, 0.05)) = 0.010
        _InkStrength ("Ink Strength", Range(0, 1)) = 1.0
    }

    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent+18" }
        LOD 80

        Pass
        {
            Cull Off
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            ZTest Always

            CGPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag

            #include "UnityCG.cginc"

            float4 _EdgeColor;
            float _EdgeBlend;
            float _ShadowOffset;

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
                o.pos.xy += float2(0.0f, -_ShadowOffset * o.pos.w);
                o.color = v.color;
                o.uv = v.uv;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float width01 = abs(i.uv.x - 0.5f) * 2.0f;
                float body = 1.0f - smoothstep(0.90f, 1.0f, width01);
                float lowerLane = smoothstep(0.46f, 1.0f, i.uv.x);
                float brush = sin(i.uv.y * 31.0f + 0.8f) * 0.22f + sin(i.uv.y * 79.0f) * 0.12f;
                brush = lerp(0.88f, 1.0f, saturate(brush * 0.5f + 0.5f));
                float alpha = _EdgeColor.a * saturate(_EdgeBlend) * i.color.a * body * lowerLane * brush;
                clip(alpha - 0.012f);
                return float4(_EdgeColor.rgb, alpha);
            }
            ENDCG
        }

        Pass
        {
            Cull Off
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            ZTest Always

            CGPROGRAM
            #pragma target 3.0
            #pragma vertex vert
            #pragma fragment frag

            #include "UnityCG.cginc"

            float4 _RibbonColor;
            float4 _EdgeColor;
            float _EdgeBlend;
            float _InkStrength;

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
                float body = 1.0f - smoothstep(0.92f, 1.0f, width01);
                float inkRim = smoothstep(0.64f, 0.94f, width01);
                float lowerShadow = smoothstep(0.54f, 1.0f, i.uv.x)
                    * (1.0f - smoothstep(0.70f, 1.0f, width01));
                float3 paperWhite = _RibbonColor.rgb;
                float3 color = lerp(paperWhite, _EdgeColor.rgb, lowerShadow * saturate(_EdgeBlend) * 0.84f);
                color = lerp(color, float3(0.020f, 0.055f, 0.115f), inkRim * saturate(_InkStrength));
                float brush = sin(i.uv.y * 37.0f) * 0.25f + sin(i.uv.y * 91.0f + 1.7f) * 0.18f;
                brush = lerp(0.93f, 1.0f, saturate(brush * 0.5f + 0.5f));
                float plateAlpha = lerp(0.82f, 1.0f, i.color.a);
                float alpha = _RibbonColor.a * plateAlpha * body * brush;
                alpha = max(alpha, _EdgeColor.a * plateAlpha * lowerShadow * body * 0.74f);
                alpha = max(alpha, _RibbonColor.a * plateAlpha * inkRim * 0.98f);
                clip(alpha - 0.018f);
                return float4(color, alpha);
            }
            ENDCG
        }
    }
}
