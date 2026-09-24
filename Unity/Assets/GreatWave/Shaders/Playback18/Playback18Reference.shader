Shader "GreatWave/Playback18/Reference"
{
    Properties
    {
        _Color ("表面色", Color) = (0.06,0.32,0.52,1)
        _LightDirection ("光源へ向かう方向", Vector) = (0.3,0.8,-0.5,0)
        _Ambient ("環境光の寄与", Range(0,1)) = 0.3
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Cull Back
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex Vert
            #pragma fragment Frag
            #include "UnityCG.cginc"
            #include "Playback18Lighting.cginc"
            float4 _Color;
            float4 _LightDirection;
            float _Ambient;
            struct Input { float4 position : POSITION; float3 normal : NORMAL; };
            struct Varying { float4 position : SV_POSITION; float3 normal : TEXCOORD0; };
            Varying Vert(Input input)
            {
                Varying result;
                result.position = UnityObjectToClipPos(input.position);
                result.normal = UnityObjectToWorldNormal(input.normal);
                return result;
            }
            float4 Frag(Varying input) : SV_Target
            {
                return Playback18Shade(input.normal, _Color, _LightDirection.xyz, _Ambient);
            }
            ENDCG
        }
    }
    Fallback Off
}
