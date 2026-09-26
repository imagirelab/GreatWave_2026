// 番号30：形成の keypose の頂点シェーダー用の部品。ひな形は Sampling19Surface.cginc（番号19）で、同じ形の SPI の立体視マクロ
// （UNITY_VERTEX_INPUT_INSTANCE_ID・UNITY_SETUP_INSTANCE_ID・UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO・UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX）を使う。
// 番号24 の CPU のメッシュ更新（AF24WavePlayer）に代えて、頂点の位置と法線を keypose テクスチャから GPU で補間する。
// 頂点の添字（SV_VertexID）＝ 行 × 400 + 列（固定位相の格子。K* の .gwb と同じ並び）。オブジェクトの変換は単位行列（位置はワールド座標）。
#ifndef GREATWAVE_AF30_KEYPOSE_INCLUDED
#define GREATWAVE_AF30_KEYPOSE_INCLUDED

#include "UnityCG.cginc"
#include "AF30KeyposeCore.cginc"

// _AF30Enabled = 0（keypose を読み込む前）のときはメッシュの頂点（K*）のまま。
void AF30Deform(uint vid, inout float4 vertex, inout float3 normal)
{
    if (_AF30Enabled > 0.5)
    {
        vertex = float4(AF30KeyposePosition(vid), 1.0);
        normal = AF30KeyposeNormal(vid);
    }
}

float3 AF30CentreEye()
{
#if defined(USING_STEREO_MATRICES)
    return 0.5 * (unity_StereoWorldSpaceCameraPos[0] + unity_StereoWorldSpaceCameraPos[1]);
#else
    return _WorldSpaceCameraPos;
#endif
}
#endif
