// 設計27：DS27 keypose の頂点シェーダー用の部品（美術優先30 の AF30Keypose.cginc を写したもの）。SPI の立体視マクロ
// （UNITY_VERTEX_INPUT_INSTANCE_ID・UNITY_SETUP_INSTANCE_ID・UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO・UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX）
// は Sampling19Surface.cginc・AF30 と同じ形で、各シェーダーの頂点関数・断片関数に書く。
// 頂点の位置は keypose のバッファから GPU で補間する（頂点バッファは K* のまま）。オブジェクトの変換は単位行列とし、ワールドの位置から直接クリップ座標にする。
#ifndef GREATWAVE_DS27_KEYPOSE_INCLUDED
#define GREATWAVE_DS27_KEYPOSE_INCLUDED

#include "UnityCG.cginc"
#include "DS27KeyposeCore.cginc"

// _DS27Enabled = 0（パッケージを読み込む前）のときはメッシュの頂点（K*、ワールド）のまま。
float3 DS27WorldOrMesh(uint vid, float3 meshVertex)
{
    return _DS27Enabled > 0.5 ? DS27WorldPosition(vid) : mul(unity_ObjectToWorld, float4(meshVertex, 1.0)).xyz;
}

float3 DS27NormalOrMesh(uint vid, float3 meshNormal)
{
    return _DS27Enabled > 0.5 ? DS27Normal(vid) : normalize(UnityObjectToWorldNormal(meshNormal));
}

float3 DS27CentreEye()
{
#if defined(USING_STEREO_MATRICES)
    return 0.5 * (unity_StereoWorldSpaceCameraPos[0] + unity_StereoWorldSpaceCameraPos[1]);
#else
    return _WorldSpaceCameraPos;
#endif
}
#endif
