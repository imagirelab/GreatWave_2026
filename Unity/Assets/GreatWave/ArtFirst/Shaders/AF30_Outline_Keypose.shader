// 番号30：外殻線 v0（番号28 の AF28 Outline v0 と同じ反転シェル）に、形成の keypose の頂点補間を加えたもの。
// 位置と法線は AF30Keypose.cginc（keypose テクスチャ 4 層の Catmull-Rom、法線は八面体符号化を補間して正規化）から読む。
// 押し出し幅（m）= clamp(中心眼から頂点までの距離 × _LineAngle, _MinWidth, _MaxWidth)（番号28 と同じ）。原画にない線の除去（線マスク）は番号36。
// SPI の立体視マクロは Sampling19Surface.cginc と同じ形（立体視での描画は HMD 実機で未検証）。
Shader "GreatWave/ArtFirst/AF30 Outline Keypose"
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
            Name "AF30OUTLINE"
            Tags { "LightMode"="ForwardBase" }
            Cull Front
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "AF30Keypose.cginc"

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
                AF30Deform(v.vid, v.vertex, v.normal);
                float3 w = mul(unity_ObjectToWorld, float4(v.vertex.xyz, 1)).xyz;
                float3 n = normalize(UnityObjectToWorldNormal(v.normal));
                float width = clamp(distance(w, AF30CentreEye()) * _LineAngle, _MinWidth, _MaxWidth);
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
