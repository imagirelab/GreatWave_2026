// 設計27：外殻線 v0（美術優先28 の AF28 Outline v0・美術優先30 の AF30 Outline Keypose と同じ反転シェル）を、DS27 keypose の頂点補間で動かすもの。
// 位置は DS27Keypose.cginc（ワールド = 波の枠の原点 O(τ) ＋ 局所の Hermite）、法線は補間した位置から K* の格子の 6 つの三角形の面の法線の和で求める
// （DS27 のパッケージには法線のファイルがない。美術優先30 の keypose の法線と同じ定義）。
// 押し出し幅（m）= clamp(中心眼から頂点までの距離 × _LineAngle, _MinWidth, _MaxWidth)（美術優先28・30 と同じ）。
// SPI の立体視マクロは Sampling19Surface.cginc・AF30 と同じ形（立体視での描画は HMD 実機で未検証）。
Shader "GreatWave/Design27/DS27 Outline Keypose"
{
    Properties
    {
        _LineColor ("線の色（原画の外周の線の芯）", Color) = (0.2, 0.2, 0.25, 1)
        _LineAngle ("線の角幅（rad）", Float) = 0.00129
        _MinWidth ("押し出し幅の下限（m）", Float) = 0.05
        _MaxWidth ("押し出し幅の上限（m）", Float) = 0.3
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry+10" }
        Pass
        {
            Name "DS27OUTLINE"
            Tags { "LightMode"="ForwardBase" }
            Cull Front
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "DS27Keypose.cginc"

            float4 _LineColor;
            float _LineAngle, _MinWidth, _MaxWidth;
            float _AF28IdMode;

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                uint vid : SV_VertexID;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 w = DS27WorldOrMesh(v.vid, v.vertex.xyz);
                float3 n = DS27NormalOrMesh(v.vid, v.normal);
                float width = clamp(distance(w, DS27CentreEye()) * _LineAngle, _MinWidth, _MaxWidth);
                o.pos = UnityWorldToClipPos(w + n * width);
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                if (_AF28IdMode > 0.5) return float4(1, 0, 1, 1);
                return float4(_LineColor.rgb, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
