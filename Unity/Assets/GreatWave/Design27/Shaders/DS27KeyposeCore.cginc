// 設計27：DS27 keypose を読む共通部（頂点シェーダーと、検査用の DS27KeyposeCapture.compute が同じ関数を使う）。
// 美術優先30 の AF30KeyposeCore.cginc を写して、次を変えた：位置は StructuredBuffer<uint> に 16 bit × 3 を詰めたもの（A を捨てた）、
// 節点は不等間隔の τ（重みは CPU の DS27KeyposePlayer.Weights で計算。3 次 Hermite、傾きは中心差分、端は片側）、
// 位置は波の枠の局所座標で、ワールド = _DS27Origin + 局所。法線のファイルはなく、格子の 6 つの三角形から求める。
// UnityCG.cginc に頼らない HLSL だけで書く（コンピュートシェーダーからも読み込むため）。
//   _DS27Pos：頂点 v・層 l・成分 k の 16 bit の値の番号 i = (l × N + v) × 3 + k。uint の i/2 番目の、i が偶数なら下位、奇数なら上位の 16 bit。
//             局所の位置 = _DS27BBoxMin + q/65535 × _DS27BBoxSize（全層の外接箱で正規化。量子化の差は外接箱の 1/131070 の対角）。
//   _DS27Grid：(列の数 400, 行の数 240, 頂点の数 N, 0)。頂点の添字（SV_VertexID）= 行 × 列の数 + 列（K* の .gwb と同じ並び）。
//   _DS27Slices・_DS27Weights：補間に使う 4 つの層とその重み（範囲の外は (0, 1, 0, 0)）。重みが 0 の層も読む（分岐をなくす）。
// 設計29修正01：精度の層（パッケージの ds27_pos_lo_rgba8.bin、拡張 pos_lo_rgba8/1）を、大域のキーワード DS27_POS_LO があるときだけ読む。
//   _DS27PosLo：頂点 v・層 l の RGBA8 を、uint の (l × N + v) 番目にファイルのバイトのまま置く（R = x、G = y、B = z、A = 255。リトルエンディアン）。
//   復号：局所の位置 = _DS27BBoxMin + (q + lo/255 − 0.5)/65535 × _DS27BBoxSize（ds28r01e_generate.py の export_lo と同じ式。刻み約 7 µm）。
//   キーワードのない変種（精度の層のないパッケージ、設計27・28 の再生器）は、下の #else の中の元の式のままで、変える前とまったく同じに計算する。
#ifndef GREATWAVE_DS27_KEYPOSE_CORE_INCLUDED
#define GREATWAVE_DS27_KEYPOSE_CORE_INCLUDED

StructuredBuffer<uint> _DS27Pos;
StructuredBuffer<float> _DS27White;
float4 _DS27BBoxMin;
float4 _DS27BBoxSize;
float4 _DS27Slices;
float4 _DS27Weights;
float4 _DS27Origin;
float4 _DS27Grid;
float _DS27Tau;
float _DS27Enabled;

uint DS27NU() { return (uint)(_DS27Grid.x + 0.5); }
uint DS27NV() { return (uint)(_DS27Grid.y + 0.5); }

// 量子化した 16 bit の値（float にしても整数のまま正確）
float3 DS27LoadQ(uint vid, float slice)
{
    uint n = (uint)(_DS27Grid.z + 0.5);
    uint i = ((uint)(slice + 0.5) * n + vid) * 3u;
    uint w0 = _DS27Pos[i >> 1];
    uint w1 = _DS27Pos[(i >> 1) + 1u];
    uint3 q = (i & 1u) == 0u ? uint3(w0 & 0xFFFFu, w0 >> 16, w1 & 0xFFFFu) : uint3(w0 >> 16, w1 & 0xFFFFu, w1 >> 16);
    return float3(q);
}

#if defined(DS27_POS_LO)
StructuredBuffer<uint> _DS27PosLo;

// 精度の層の 8 bit の値（0〜255、x・y・z）
int3 DS27LoadLoI(uint vid, float slice)
{
    uint n = (uint)(_DS27Grid.z + 0.5);
    uint w = _DS27PosLo[(uint)(slice + 0.5) * n + vid];
    return int3(w & 0xFFu, (w >> 8) & 0xFFu, (w >> 16) & 0xFFu);
}

// 16 bit の丸めの残り（16 bit の刻みの単位、−0.5〜+0.5）
float3 DS27LoadLoOff(uint vid, float slice)
{
    return float3(DS27LoadLoI(vid, slice)) / 255.0 - 0.5;
}

// 2 頂点の差（16 bit の刻みの単位）：16 bit の整数の差（正確）＋ 精度の層の整数の差 / 255
float3 DS27LoadQDelta(uint a, uint b, float slice)
{
    return (DS27LoadQ(a, slice) - DS27LoadQ(b, slice)) + float3(DS27LoadLoI(a, slice) - DS27LoadLoI(b, slice)) / 255.0;
}
#endif

float3 DS27LoadLocal(uint vid, float slice)
{
#if defined(DS27_POS_LO)
    return _DS27BBoxMin.xyz + (DS27LoadQ(vid, slice) / 65535.0) * _DS27BBoxSize.xyz + (DS27LoadLoOff(vid, slice) / 65535.0) * _DS27BBoxSize.xyz;
#else
    return _DS27BBoxMin.xyz + (DS27LoadQ(vid, slice) / 65535.0) * _DS27BBoxSize.xyz;
#endif
}

// 4 層の重み付きの和（Hermite）。局所の位置。
float3 DS27Local(uint vid)
{
    return _DS27Weights.x * DS27LoadLocal(vid, _DS27Slices.x) + _DS27Weights.y * DS27LoadLocal(vid, _DS27Slices.y)
         + _DS27Weights.z * DS27LoadLocal(vid, _DS27Slices.z) + _DS27Weights.w * DS27LoadLocal(vid, _DS27Slices.w);
}

// 2 頂点の局所の位置の差 P(a) − P(b)。同じ 4 層・同じ重みなので、量子化の整数の差（正確）に重みを掛けてから尺度を掛ける
// （位置を引き算するより桁落ちが小さい。小さい三角形の法線の精度のため）。
float3 DS27Delta(uint a, uint b)
{
#if defined(DS27_POS_LO)
    float3 d = _DS27Weights.x * DS27LoadQDelta(a, b, _DS27Slices.x) + _DS27Weights.y * DS27LoadQDelta(a, b, _DS27Slices.y)
             + _DS27Weights.z * DS27LoadQDelta(a, b, _DS27Slices.z) + _DS27Weights.w * DS27LoadQDelta(a, b, _DS27Slices.w);
    return d * (_DS27BBoxSize.xyz / 65535.0);
#else
    float3 d = _DS27Weights.x * (DS27LoadQ(a, _DS27Slices.x) - DS27LoadQ(b, _DS27Slices.x))
             + _DS27Weights.y * (DS27LoadQ(a, _DS27Slices.y) - DS27LoadQ(b, _DS27Slices.y))
             + _DS27Weights.z * (DS27LoadQ(a, _DS27Slices.z) - DS27LoadQ(b, _DS27Slices.z))
             + _DS27Weights.w * (DS27LoadQ(a, _DS27Slices.w) - DS27LoadQ(b, _DS27Slices.w));
    return d * (_DS27BBoxSize.xyz / 65535.0);
#endif
}

// ワールドの位置 = 波の枠の原点 O(τ) ＋ 局所
float3 DS27WorldPosition(uint vid)
{
    return _DS27Origin.xyz + DS27Local(vid);
}

// 頂点の法線：K* の格子の三角形（四角 (r, c) ごとに T1 = (r,c)(r+1,c)(r,c+1)、T2 = (r,c+1)(r+1,c)(r+1,c+1)）のうち、
// この頂点を含む最大 6 つの面の法線（正規化しない外積 = 面積 × 2 の重み）の和を正規化する（美術優先30 の vertex_normals と同じ）。
// 平行移動は法線を変えないので、局所の位置で計算する。
float3 DS27Normal(uint vid)
{
    uint nu = DS27NU(), nv = DS27NV();
    uint r = vid / nu, c = vid - r * nu;
    bool hu = r > 0u, hd = r + 1u < nv, hl = c > 0u, hr = c + 1u < nu;
    float3 n = 0;
    // 隣の頂点への差（V からの相対の位置）。無い隣は 0（使わない）
    float3 dD = hd ? DS27Delta(vid + nu, vid) : 0;
    float3 dR = hr ? DS27Delta(vid + 1u, vid) : 0;
    float3 dU = hu ? DS27Delta(vid - nu, vid) : 0;
    float3 dL = hl ? DS27Delta(vid - 1u, vid) : 0;
    if (hd && hr) n += cross(dD, dR);                               // 四角 (r, c) の T1
    if (hd && hl)
    {
        float3 dDL = DS27Delta(vid + nu - 1u, vid);
        n += cross(dL, dDL);                                          // 四角 (r, c−1) の T1
        n += cross(dDL, dD);                                          // 四角 (r, c−1) の T2
    }
    if (hu && hr)
    {
        float3 dUR = DS27Delta(vid - nu + 1u, vid);
        n += cross(dUR, dU);                                          // 四角 (r−1, c) の T1
        n += cross(dR, dUR);                                          // 四角 (r−1, c) の T2
    }
    if (hu && hl) n += cross(dU, dL);                               // 四角 (r−1, c−1) の T2
    float l = length(n);
    return l > 1e-30 ? n / l : float3(0, 1, 0);
}
#endif
