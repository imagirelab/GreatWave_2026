// 番号30：形成の keypose を読む共通部（頂点シェーダーと、検査用の AF30KeyposeCapture.compute が同じ関数を使う）。
// UnityCG.cginc に頼らない HLSL だけで書く（コンピュートシェーダーからも読み込むため）。
// keypose（Tools/GWWaveGen/af30_formation.py が書き、AF30KeyposeWave が Texture2DArray にして大域の値で渡す）：
//   _AF30PosTex：RGBA16 UNORM（TextureFormat.RGBA64）。層 = key、texel (列, 行) = 頂点（頂点の添字 = 行 × _AF30GridNU + 列）。
//                位置 = _AF30BBoxMin + rgb × _AF30BBoxSize（全 key の外接箱で正規化、量子化の差は最大 約 1.2 mm）。
//   _AF30NrmTex：RG16 UNORM（TextureFormat.RG32）。法線の八面体符号化 e = rg × 2 − 1。
//   _AF30Slices：補間に使う 4 つの層、_AF30Weights：その重み（非一様の節点の Catmull-Rom。CPU の AF30KeyposeWave.Weights で計算。
//                端の外は (0, 1, 0, 0)）。texel は Load で読み、フィルターを使わない。
#ifndef GREATWAVE_AF30_KEYPOSE_CORE_INCLUDED
#define GREATWAVE_AF30_KEYPOSE_CORE_INCLUDED

Texture2DArray<float4> _AF30PosTex;
Texture2DArray<float2> _AF30NrmTex;
float4 _AF30BBoxMin;
float4 _AF30BBoxSize;
float4 _AF30Slices;
float4 _AF30Weights;
float _AF30GridNU;
float _AF30Enabled;

int4 AF30Texel(uint vid, float slice)
{
    uint nu = (uint)(_AF30GridNU + 0.5);
    return int4((int)(vid % nu), (int)(vid / nu), (int)(slice + 0.5), 0);
}

float3 AF30LoadPos(uint vid, float slice)
{
    return _AF30BBoxMin.xyz + _AF30PosTex.Load(AF30Texel(vid, slice)).xyz * _AF30BBoxSize.xyz;
}

float3 AF30OctaDecode(float2 e)
{
    float3 n = float3(e.x, e.y, 1.0 - abs(e.x) - abs(e.y));
    float t = saturate(-n.z);
    n.x += n.x >= 0.0 ? -t : t;
    n.y += n.y >= 0.0 ? -t : t;
    return normalize(n);
}

float3 AF30LoadNrm(uint vid, float slice)
{
    return AF30OctaDecode(_AF30NrmTex.Load(AF30Texel(vid, slice)) * 2.0 - 1.0);
}

// 4 層の重み付きの和（Catmull-Rom）。重みが 0 の層も読む（分岐をなくす。端では同じ層が並ぶ）。
float3 AF30KeyposePosition(uint vid)
{
    return _AF30Weights.x * AF30LoadPos(vid, _AF30Slices.x) + _AF30Weights.y * AF30LoadPos(vid, _AF30Slices.y)
         + _AF30Weights.z * AF30LoadPos(vid, _AF30Slices.z) + _AF30Weights.w * AF30LoadPos(vid, _AF30Slices.w);
}

float3 AF30KeyposeNormal(uint vid)
{
    float3 n = _AF30Weights.x * AF30LoadNrm(vid, _AF30Slices.x) + _AF30Weights.y * AF30LoadNrm(vid, _AF30Slices.y)
             + _AF30Weights.z * AF30LoadNrm(vid, _AF30Slices.z) + _AF30Weights.w * AF30LoadNrm(vid, _AF30Slices.w);
    return normalize(n);
}
#endif
