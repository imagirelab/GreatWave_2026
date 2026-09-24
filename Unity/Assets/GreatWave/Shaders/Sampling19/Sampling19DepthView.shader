Shader "Hidden/GreatWave/Sampling19/Depth View"
{
    Properties
    {
        _MainTex ("同じカメラの色画像", 2D) = "white" {}
        _DepthRange ("表示する眼奥行きの最小・最大メートル", Vector) = (0,20,0,0)
        _DepthMode ("0:表示 1:眼奥行きm 2:生深度", Integer) = 0
    }
    SubShader
    {
        Cull Off
        ZWrite Off
        ZTest Always
        Pass
        {
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex Sampling19DepthVert
            #pragma fragment Sampling19DepthFrag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"
            UNITY_DECLARE_DEPTH_TEXTURE(_CameraDepthTexture);
            float4 _MainTex_TexelSize;
            float4 _DepthRange;
            int _DepthMode;
            struct Sampling19DepthInput
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };
            struct Sampling19DepthVarying
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_OUTPUT_STEREO
            };
            Sampling19DepthVarying Sampling19DepthVert(Sampling19DepthInput v)
            {
                Sampling19DepthVarying o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(Sampling19DepthVarying, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                // 色RTと深度RTの上下が異なるAPI経路に合わせる。
                #if UNITY_UV_STARTS_AT_TOP
                    if (_MainTex_TexelSize.y < 0) o.uv.y = 1 - o.uv.y;
                #endif
                return o;
            }
            float4 Sampling19DepthFrag(Sampling19DepthVarying i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float rawDepth = SAMPLE_DEPTH_TEXTURE(_CameraDepthTexture, i.uv);
                // 透視投影カメラ用。正投影・MSAA・HMDは別検証。
                float eyeDepth = LinearEyeDepth(rawDepth);
                float value = 1.0 - saturate((eyeDepth - _DepthRange.x) /
                    max(_DepthRange.y - _DepthRange.x, 1e-5));
                if (_DepthMode == 1) value = eyeDepth;
                if (_DepthMode == 2) value = rawDepth;
                return float4(value, value, value, 1.0);
            }
            ENDCG
        }
    }
    Fallback Off
}
