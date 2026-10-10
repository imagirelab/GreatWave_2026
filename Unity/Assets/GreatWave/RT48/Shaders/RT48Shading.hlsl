#ifndef RT48_SHADING_INCLUDED
#define RT48_SHADING_INCLUDED
// RT48：中立の水の色（計画 §3.3）。拡散（太陽と空の環境光）、Schlick のフレネル（F0）で空のグラデーションを映す、太陽の鏡面（GGX）、
// 霧（見える割合 exp(-d / _RT48FogDist)）。泡・白い水・透ける光・浮世絵の線はない。色は線形の空間の値。
// 値は大域（Shader.SetGlobalVector）で、RT48Playback が入れる。

#ifndef RT48_PI
#define RT48_PI 3.14159265358979
#endif

float4 _RT48SunDir;       // 太陽へ向かう向き（正規化）
float4 _RT48SunColor;
float4 _RT48SkyZenith;
float4 _RT48SkyHorizon;
float4 _RT48SkyGround;    // 水平より下へ向かう反射の色
float4 _RT48FogColor;
float _RT48FogDist;       // 2000 m（50 m で 97.5 %、9.2 km で 1 %）

float3 RT48SkyNoSun(float3 d)
{
    float h = d.y;
    if (h >= 0.0) return lerp(_RT48SkyHorizon.rgb, _RT48SkyZenith.rgb, pow(saturate(h), 0.45));
    return lerp(_RT48SkyHorizon.rgb, _RT48SkyGround.rgb, saturate(-h * 4.0));
}

float3 RT48SkyWithSun(float3 d)
{
    float s = saturate(dot(d, _RT48SunDir.xyz));
    return RT48SkyNoSun(d) + _RT48SunColor.rgb * (pow(s, 2500.0) * 25.0 + pow(s, 80.0) * 0.12);
}

float3 RT48Shade(float3 wpos, float3 camPos, float3 n, float3 albedo, float f0, float rough, float specScale, float diffuse)
{
    float3 v = normalize(camPos - wpos);
    float ndv = max(dot(n, v), 1e-4);
    float3 l = _RT48SunDir.xyz;
    float ndl = saturate(dot(n, l));
    float F = f0 + (1.0 - f0) * pow(1.0 - ndv, 5.0);
    float3 amb = lerp(_RT48SkyGround.rgb, lerp(_RT48SkyHorizon.rgb, _RT48SkyZenith.rgb, 0.5), saturate(0.5 + 0.5 * n.y));
    float3 dif = albedo * (_RT48SunColor.rgb * ndl * diffuse + amb);
    float3 r = reflect(-v, n);
    float3 refl = RT48SkyNoSun(r);
    float3 h = normalize(l + v);
    float ndh = saturate(dot(n, h));
    float a = max(rough, 0.02);
    float a2 = a * a;
    float dd = ndh * ndh * (a2 - 1.0) + 1.0;
    float D = a2 / (RT48_PI * dd * dd);
    float k = a * 0.5;
    float Vis = 1.0 / ((ndl * (1.0 - k) + k) * (ndv * (1.0 - k) + k) * 4.0);
    float Fh = f0 + (1.0 - f0) * pow(1.0 - saturate(dot(v, h)), 5.0);
    float3 spec = _RT48SunColor.rgb * (D * Vis * Fh * ndl * specScale);
    return (1.0 - F) * dif + F * refl + spec;
}

float3 RT48Fog(float3 col, float3 wpos, float3 camPos)
{
    float f = exp(-distance(wpos, camPos) / max(_RT48FogDist, 1.0));
    return lerp(_RT48FogColor.rgb, col, f);
}

#endif
