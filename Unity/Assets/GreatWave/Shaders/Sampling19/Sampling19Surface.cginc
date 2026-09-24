// 第19号専用。18のHDRデコードを読み取り依存として共用する。
// 色・影・CameraDepthTextureの各経路で同じ離散フレームを使う。
#ifndef GREATWAVE_SAMPLING19_SURFACE_INCLUDED
#define GREATWAVE_SAMPLING19_SURFACE_INCLUDED

#include "UnityCG.cginc"
#include "Lighting.cginc"
#include "AutoLight.cginc"
#ifdef GREATWAVE_SAMPLING19_VAT
    #include "../Playback18/Playback18VAT.cginc"
#endif

float4 _Color;
float _Ambient;

struct Sampling19Input
{
    float4 vertex : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
    UNITY_VERTEX_INPUT_INSTANCE_ID
};

void Sampling19Deform(inout Sampling19Input v)
{
    #ifdef GREATWAVE_SAMPLING19_VAT
        Playback18VATSample sample = Playback18Decode(v.uv);
        v.vertex = float4(sample.position.xyz, 1.0);
        v.normal = sample.normal.xyz;
    #endif
}

#if defined(GREATWAVE_SAMPLING19_FORWARD)
struct Sampling19Varying
{
    float4 pos : SV_POSITION;
    float3 normal : TEXCOORD0;
    float3 worldPosition : TEXCOORD1;
    UNITY_SHADOW_COORDS(2)
    UNITY_VERTEX_OUTPUT_STEREO
};

Sampling19Varying Sampling19Vert(Sampling19Input v)
{
    Sampling19Varying o;
    UNITY_SETUP_INSTANCE_ID(v);
    UNITY_INITIALIZE_OUTPUT(Sampling19Varying, o);
    UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
    Sampling19Deform(v);
    o.pos = UnityObjectToClipPos(v.vertex);
    o.normal = UnityObjectToWorldNormal(v.normal);
    o.worldPosition = mul(unity_ObjectToWorld, v.vertex).xyz;
    // 内部マクロがv.vertexを読む場合も変形後の位置を参照する。
    UNITY_TRANSFER_SHADOW(o, float2(0, 0));
    return o;
}

float4 Sampling19Frag(Sampling19Varying i) : SV_Target
{
    UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
    float3 normal = normalize(i.normal);
    float3 lightDirection = normalize(UnityWorldSpaceLightDir(i.worldPosition));
    UNITY_LIGHT_ATTENUATION(attenuation, i, i.worldPosition);
    // 同条件比較用。主指向性ライトと固定の環境項だけを使う。
    float3 lighting = max(_Ambient, 0.0) + _LightColor0.rgb *
        saturate(dot(normal, lightDirection)) * attenuation;
    return float4(_Color.rgb * lighting, 1.0);
}
#endif

#if defined(GREATWAVE_SAMPLING19_SHADOW)
struct Sampling19ShadowVarying
{
    V2F_SHADOW_CASTER;
    UNITY_VERTEX_OUTPUT_STEREO
};

Sampling19ShadowVarying Sampling19ShadowVert(Sampling19Input v)
{
    Sampling19ShadowVarying o;
    UNITY_SETUP_INSTANCE_ID(v);
    UNITY_INITIALIZE_OUTPUT(Sampling19ShadowVarying, o);
    UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
    Sampling19Deform(v);
    // 通常描画と同じ位置・法線から、Unityの影バイアスを適用する。
    TRANSFER_SHADOW_CASTER_NORMALOFFSET(o);
    return o;
}

float4 Sampling19ShadowFrag(Sampling19ShadowVarying i) : SV_Target
{
    UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
    SHADOW_CASTER_FRAGMENT(i)
}
#endif
#endif
