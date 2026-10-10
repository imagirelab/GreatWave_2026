// RT48：水・まわりの海・離れた水・船の色（計画 §3.3）。Built-in、不透明、両面（裏は暗く）。
//   RT48_SWEEP：掃いた面。位置と法線は RT48Decode.hlsl（StructuredBuffer の曲線）から。メッシュの uv.x が点の番号、位置の z が頂の向きの Z。
//               掃いた面の物体は原点に回転なしで置く（物体の行列は使わない）。
//   キーワードなし：ふつうのメッシュ（まわりの海・離れた水・船）。
// 両眼は single-pass instanced（UNITY_VERTEX_INPUT_INSTANCE_ID・UNITY_SETUP_INSTANCE_ID・UNITY_VERTEX_OUTPUT_STEREO・
// UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO・UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX）。HMD の実機は未確認。
Shader "GreatWave/RT48/Water"
{
    Properties
    {
        _Albedo ("水の色（線形）", Color) = (0.007, 0.061, 0.080, 1)
        _F0 ("鏡の反射の F0", Float) = 0.02
        _Roughness ("粗さ（GGX の α）", Float) = 0.08
        _SpecScale ("太陽の鏡面の強さ", Float) = 1
        _Diffuse ("太陽の拡散の強さ", Float) = 0.5
        _BackDim ("裏の面の明るさ", Float) = 0.15
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "RT48Water"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile_local _ RT48_SWEEP
            #include "UnityCG.cginc"
            #include "RT48Decode.hlsl"
            #include "RT48Shading.hlsl"

            float4 _Albedo;
            float _F0, _Roughness, _SpecScale, _Diffuse, _BackDim;

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                float2 uv : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 wpos : TEXCOORD0;
                float3 wnrm : TEXCOORD1;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
            #if defined(RT48_SWEEP)
                int i = (int)(v.uv.x + 0.5);
                float2 p = RT48Point(i);
                float2 n = RT48Normal(i);
                o.wpos = float3(p.x, p.y, v.vertex.z);
                o.wnrm = float3(n.x, n.y, 0.0);
            #else
                o.wpos = mul(unity_ObjectToWorld, float4(v.vertex.xyz, 1.0)).xyz;
                o.wnrm = UnityObjectToWorldNormal(v.normal);
            #endif
                o.pos = UnityWorldToClipPos(o.wpos);
                return o;
            }

            float4 frag(v2f i, float facing : VFACE) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float3 n = normalize(i.wnrm);
                bool back = facing < 0;
                if (back) n = -n;
                float3 cam = _WorldSpaceCameraPos.xyz;
                float3 col = RT48Shade(i.wpos, cam, n, _Albedo.rgb, _F0, _Roughness, _SpecScale, _Diffuse);
                if (back) col *= _BackDim;
                col = RT48Fog(col, i.wpos, cam);
                return float4(col, 1.0);
            }
            ENDCG
        }
    }
    Fallback Off
}
