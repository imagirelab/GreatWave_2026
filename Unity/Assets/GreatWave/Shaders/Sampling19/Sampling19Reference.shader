Shader "GreatWave/Sampling19/Reference Shadow"
{
    Properties
    {
        _Color ("表面色", Color) = (0.06,0.32,0.52,1)
        _Ambient ("固定環境光の寄与", Range(0,1)) = 0.16
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
            #define GREATWAVE_SAMPLING19_SHADOW 1
            #include "Sampling19Surface.cginc"
            ENDCG
        }
    }
    Fallback Off
}
