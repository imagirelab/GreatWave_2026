#ifndef RT48_DECODE_INCLUDED
#define RT48_DECODE_INCLUDED
// RT48（Q48 の案 1）：焼いた断面の曲線から、点 i の位置 (X, Y) と法線を作る（計画 §3.2）。
// 描くシェーダー（RT48Water.shader の RT48_SWEEP）と照合の計算シェーダー（RT48DecodeCheck.compute、C5）が、この 1 つのファイルを読む。
// UnityCG.cginc に頼らない（計算シェーダーでも読むため）。
//   _RT48Curves：全部の組の A・B の float2（x は x_origin からの距離、y は静かな水面からの高さ）
//   位置：P = A[i] + (B[i] - A[i]) * alpha、X = P.x + _RT48XShift（= x_origin - 座席の x）、Y = P.y * 重み(P.x)
//   重み：x の両端の下ろし（_RT48Taper = 保存の座標の a0, a1, b0, b1。a0〜a1 で 0→1、b0〜b1 で 1→0 の余弦）
//   法線：表示の点の i-1 と i+1（端は端の点）を結ぶ向きの左の法線 (-t.y, t.x)。頂の向きの成分は 0。

#ifndef RT48_PI
#define RT48_PI 3.14159265358979
#endif

StructuredBuffer<float2> _RT48Curves;
int _RT48OffsetA;
int _RT48OffsetB;
int _RT48PointCount;
float _RT48Alpha;
float _RT48XShift;
float4 _RT48Taper;

float RT48TaperWeight(float xs)
{
    if (xs <= _RT48Taper.x || xs >= _RT48Taper.w) return 0.0;
    if (xs < _RT48Taper.y) return 0.5 - 0.5 * cos(RT48_PI * (xs - _RT48Taper.x) / (_RT48Taper.y - _RT48Taper.x));
    if (xs > _RT48Taper.z) return 0.5 + 0.5 * cos(RT48_PI * (xs - _RT48Taper.z) / (_RT48Taper.w - _RT48Taper.z));
    return 1.0;
}

float2 RT48RawPoint(int i)
{
    i = clamp(i, 0, _RT48PointCount - 1);
    float2 a = _RT48Curves[_RT48OffsetA + i];
    float2 b = _RT48Curves[_RT48OffsetB + i];
    return a + (b - a) * _RT48Alpha;
}

float2 RT48Point(int i)
{
    float2 p = RT48RawPoint(i);
    return float2(p.x + _RT48XShift, p.y * RT48TaperWeight(p.x));
}

float2 RT48Normal(int i)
{
    float2 p0 = RT48Point(max(i - 1, 0));
    float2 p1 = RT48Point(min(i + 1, _RT48PointCount - 1));
    float2 t = p1 - p0;
    float len = length(t);
    return len > 1e-12 ? float2(-t.y, t.x) / len : float2(0.0, 1.0);
}

#endif
