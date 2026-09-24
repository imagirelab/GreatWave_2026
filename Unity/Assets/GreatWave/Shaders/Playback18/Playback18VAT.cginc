// SideFX Labs由来のHDR専用・整数時刻Dynamic Remeshingデコーダー。
// 出典：791ecfd07735bb8229fb679f08c000b8489b7a6c / URP_VAT3
// VAT_DynamicRemeshing_SSG.shadersubgraph。ライセンスはReference/LICENSE.md。
// 位置正規化・圧縮法線・位置2枚分割・時刻補間には対応しない。
#ifndef GREATWAVE_PLAYBACK18_VAT_INCLUDED
#define GREATWAVE_PLAYBACK18_VAT_INCLUDED

Texture2D<float4> _VatPosition;
Texture2D<float4> _VatRotation;
Texture2D<float4> _VatLookup;
float4 _VatEncodedMin;
float4 _VatEncodedMax;
int _VatFrameCount;
int _VatFrameIndex;

// 描画と計算で共用する、明示的なPoint・Repeat・LOD0参照。
// Unityへ読み込んだテクスチャを参照するため、画像の行を追加反転しない。
float4 Playback18PointRepeat(Texture2D<float4> image, float2 uv)
{
    uint width, height;
    image.GetDimensions(width, height);
    uint2 pixel = min((uint2)floor(frac(uv) * float2(width, height)),
                      uint2(width - 1, height - 1));
    return image.Load(int3(pixel, 0));
}

struct Playback18VATSample
{
    float4 position; // xyz：ローカル位置、w：隠すデバッグ形状以外のUV
    float4 normal;   // xyz：単位ローカル法線、w：正規化前の長さ
    float4 lookup;   // 元の検索表RGBA
    float4 address;  // xy：検索表UV、zw：アニメーションテクスチャUV
    float4 status;   // 有限値/配置の合格、位置HDR、検索表HDR、四元数の長さ
    float4 layout;   // xy：補正前の有効率、zw：実際に使った有効率
};

float Playback18SnapIntegerBoundary(float value, float tolerance)
{
    float nearest = round(value);
    return abs(value - nearest) <= tolerance ? nearest : value;
}

Playback18VATSample Playback18Decode(float2 uv0)
{
    Playback18VATSample result;
    // 公式グラフのノード：6310376d / 4e4177ba、c5cb943c / 6a6f086f。
    float scaledX = _VatEncodedMin.z * 10.0;
    float scaledY = -_VatEncodedMax.x * 10.0;
    float rawX = 1.0 - (ceil(scaledX) - scaledX);
    float rawY = 1.0 - frac(scaledY);
    uint lookupWidth, lookupHeight;
    _VatLookup.GetDimensions(lookupWidth, lookupHeight);
    // CPUと同じ限定補正。元メタデータは変更せず、正規の1画素差も隠さない。
    float tolerance = min(2e-5, 0.125 / max(lookupWidth, lookupHeight));
    float usedX = Playback18SnapIntegerBoundary(scaledX, tolerance);
    float usedY = Playback18SnapIntegerBoundary(scaledY, tolerance);
    float activeX = 1.0 - (ceil(usedX) - usedX);
    float activeY = 1.0 - frac(usedY);
    float positionHDR = frac(_VatEncodedMax.z * 10.0) >= 0.5 ? 1.0 : 0.0;
    float lookupHDR = frac(-_VatEncodedMin.x * 10.0) >= 0.5 ? 1.0 : 0.0;

    // 公式の手動displayFrameは1始まり、このAPIは0始まり。
    // ループせず、終端はframeCount - 1を保持する。
    float phase = (float)_VatFrameIndex / max(1, _VatFrameCount);
    float2 lookupUV = float2(uv0.x * activeX,
        1.0 - ((1.0 - uv0.y) + phase) * activeY);
    float4 lookup = Playback18PointRepeat(_VatLookup, lookupUV);
    // HDR検索表の分割係数は2048。LDRの255係数はここでは非対応。
    float2 animationUV = float2(lookup.r + lookup.g / 2048.0,
                               1.0 - (lookup.b + lookup.a / 2048.0));
    float4 position = Playback18PointRepeat(_VatPosition, animationUV);
    float4 rotation = Playback18PointRepeat(_VatRotation, animationUV);

    // HDR四元数は既に書出先の座標系になっている。
    // 公式グラフは基準法線+Yを回転させてから単位化する。
    float3 referenceNormal = float3(0.0, 1.0, 0.0);
    float3 rawNormal = referenceNormal + 2.0 * cross(rotation.xyz,
        rotation.w * referenceNormal + cross(rotation.xyz, referenceNormal));
    float normalLength = length(rawNormal);
    float3 normal = rawNormal / max(normalLength, 1e-20);
    float outsideDebug = uv0.y > 0.1 ? 1.0 : 0.0;
    result.position = float4(outsideDebug > 0.5 ? position.xyz : float3(0, 0, 0), outsideDebug);
    result.normal = float4(normal, normalLength);
    result.lookup = lookup;
    result.address = float4(lookupUV, animationUV);
    result.layout = float4(rawX, rawY, activeX, activeY);

    bool finite = all(isfinite(position)) && all(isfinite(rotation)) &&
                  all(isfinite(lookup)) && all(isfinite(result.address)) &&
                  all(isfinite(normal));
    bool layout = activeX > 0.0 && activeX <= 1.0 && activeY > 0.0 && activeY <= 1.0 &&
                  _VatFrameIndex >= 0 && _VatFrameIndex < _VatFrameCount &&
                  positionHDR > 0.5 && lookupHDR > 0.5 && normalLength > 1e-10;
    result.status = float4(finite && layout ? 1.0 : 0.0,
                          positionHDR, lookupHDR, length(rotation));
    return result;
}
#endif
