Shader "GreatWave/Playback18/VAT HDR"
{
    Properties
    {
        _VatPosition ("HDR位置", 2D) = "black" {}
        _VatRotation ("HDR回転", 2D) = "black" {}
        _VatLookup ("HDR検索表", 2D) = "black" {}
        _VatEncodedMin ("書出元の符号化最小値", Vector) = (0,0,0,0)
        _VatEncodedMax ("書出元の符号化最大値", Vector) = (0,0,0,0)
        _VatFrameCount ("フレーム数", Integer) = 49
        _VatFrameIndex ("試料番号", Integer) = 0
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
            #include "Playback18VAT.cginc"
            #include "Playback18Lighting.cginc"
            float4 _Color;
            float4 _LightDirection;
            float _Ambient;
            struct Input { float4 position : POSITION; float2 uv : TEXCOORD0; };
            struct Varying { float4 position : SV_POSITION; float3 normal : TEXCOORD0; };
            Varying Vert(Input input)
            {
                Playback18VATSample decoded = Playback18Decode(input.uv);
                Varying result;
                result.position = UnityObjectToClipPos(float4(decoded.position.xyz, 1.0));
                result.normal = UnityObjectToWorldNormal(decoded.normal.xyz);
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
