Shader "GreatWave/Sampling19/VAT HDR Shadow"
{
    Properties
    {
        _Color ("表面色", Color) = (0.06,0.32,0.52,1)
        _Ambient ("固定環境光の寄与", Range(0,1)) = 0.16
        [NoScaleOffset] _VatPosition ("HDR位置", 2D) = "black" {}
        [NoScaleOffset] _VatRotation ("HDR四元数", 2D) = "black" {}
        [NoScaleOffset] _VatLookup ("HDR検索表", 2D) = "black" {}
        _VatEncodedMin ("書出時の符号化最小値", Vector) = (0,0,0,0)
        _VatEncodedMax ("書出時の符号化最大値", Vector) = (0,0,0,0)
        _VatFrameCount ("標本数", Integer) = 49
        _VatFrameIndex ("標本番号・0始まり", Integer) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" "DisableBatching"="True" }
        Pass
        {
            Name "FORWARD"
            Tags { "LightMode"="ForwardBase" }
            Cull Back
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex Sampling19Vert
            #pragma fragment Sampling19Frag
            #pragma multi_compile_fwdbase nolightmap nodirlightmap nodynlightmap novertexlight
            #pragma multi_compile_instancing
            #define GREATWAVE_SAMPLING19_VAT 1
            #define GREATWAVE_SAMPLING19_FORWARD 1
            #include "Sampling19Surface.cginc"
            ENDCG
        }
        Pass
        {
            Name "SHADOWCASTER"
            Tags { "LightMode"="ShadowCaster" }
            Cull Back
            ZWrite On
            ZTest LEqual
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex Sampling19ShadowVert
            #pragma fragment Sampling19ShadowFrag
            #pragma multi_compile_shadowcaster
            #pragma multi_compile_instancing
            #define GREATWAVE_SAMPLING19_VAT 1
            #define GREATWAVE_SAMPLING19_SHADOW 1
            #include "Sampling19Surface.cginc"
            ENDCG
        }
    }
    Fallback Off
}
