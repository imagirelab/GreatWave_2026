// 美術の見本04 の直しの回 1（fix1）：AS04Common.cginc の写し。白い点を AS04FlecksM（面の計量で丸く）と、u・w の格子が潰れた所の AS04FlecksW（ワールドの格子）に替えた。ほかは同じ。
// 美術の見本04 の調べ M（Q32、2026-10-04）：AS04 Flat Smooth（原画の平らな塗り、滑らかな面）の共通部。
// 見本03 の AS03Common.cginc（変えない）から頂点の読み方だけを写し、模様は作り直した。
// - 陰・艶・形の陰影はない。色は頂点の属性だけで決まる平らな色の区域（どこから見ても同じ面は同じ色）。原画カメラの投影・テクスチャは使わない。
// - 区域：紙の白（白の印 whiteSD > 0）／白の前の縁の水色の帯（u > 0 の白の中、境から _MizuInset m 奥の幅 W(w) の所）／藍濃の地／
//   巻きに沿う藍中の太い帯（線の座標 q の等値線。帯ごとに幅・ずれ・巻きの向きの太さの揺れが違う）／藍の上の白い点（u・w の格子）。
// - 線：白と藍の境の藍の線（画素の幅）、爪の縁の藍の線（|n·v| の小さい所。爪だけ）。主役波の外殻の線は描画の道具の設計38 の線。
// 頂点の出どころ（_AS03Src。描画の道具 AS03AsmRender がこの名前で値を入れる）：
//   0 = 主役波の keypose（DS30SheetPlayer。UV3 = (F, hrel, u, w)、UV4 = (gw, hrow, Ls, X·L̂)、UV5 = (法線, whiteSD)。見本03 の keypose の道と同じ読み方）
//   1 = 主役波の静止のメッシュ（as04/mat_smooth_mesh.py。属性の約束は Build/Polish/sample04/mat/README.md）
//   2 = 爪などのメッシュ（NORMAL、UV5 = (ao, keyVis, whiteSD, 種類)。_MeshUseUV5 = 0 なら全部白）
// 測りの道：大域の _AF28IdMode = 1 で色区 ID（白 赤・水色 緑・藍中 青・藍濃 黄）、_PL29Diag = 1 で主役波の印（行・列。PL29 と同じ符号）。
#ifndef GREATWAVE_AS04F_COMMON_INCLUDED
#define GREATWAVE_AS04F_COMMON_INCLUDED

#include "../../Design27/Shaders/DS27Keypose.cginc"

float _AS03Src, _MeshUseUV5, _MeshMizuiro;
float4 _MeshTint, _MeshRim;
float4 _White, _Mizuiro, _AiMid, _AiDark, _LineCol, _SeaCol;
float4 _Band, _BandVar, _BandOn, _Fork, _BandLam;
float4 _MizuFringe, _Fleck, _FleckDepth, _FleckShape;   // fix1：_FleckAniso は AS04FlecksM の前で宣言
float4 _EdgeGrazing;
float _EdgeLinePx, _AAScale, _SeaBlend, _MinRowH, _MizuInset, _BandBack;
float _AF28IdMode, _PL29Diag;

struct AS04In
{
    float4 vertex : POSITION;
    float3 normal : NORMAL;
    float4 tangent : TANGENT;
    float4 a : TEXCOORD3;
    float4 b : TEXCOORD4;
    float4 c : TEXCOORD5;
    float4 d : TEXCOORD6;
    uint vid : SV_VertexID;
    UNITY_VERTEX_INPUT_INSTANCE_ID
};

struct AS04V2F
{
    float4 pos : SV_POSITION;
    float3 wp : TEXCOORD0;
    float3 n0 : TEXCOORD1;
    float4 a : TEXCOORD3;      // F, hrel, u, w
    float4 b : TEXCOORD4;      // gq, hrow, Lq, q
    float4 c : TEXCOORD5;      // ao, keyVis, whiteSD, 0
    float4 d : TEXCOORD6;      // λ, 白の時刻が来たか, 0, 0
    nointerpolation float2 rc : TEXCOORD7;
    UNITY_VERTEX_OUTPUT_STEREO
};

float AS04Smooth(float e0, float e1, float x) { float t = saturate((x - e0) / (e1 - e0)); return t * t * (3.0 - 2.0 * t); }
float AS04Hash(float x) { return frac(sin(x * 127.1 + 311.7) * 43758.5453); }
float AS04Hash2(float2 p) { return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }

// 稜の周期 λ(y)（keypose の道だけ。静止のメッシュは UV6.z の λ を使う）。見本03 の AS03Lam と同じ式
float AS04Lam(float y)
{
    float H0 = max(_BandLam.w, 1.0);
    float t = y / H0;
    float e = exp(2.0 * clamp((t - 0.5) / 0.3, -10.0, 10.0));
    float ts = 0.5 + 0.3 * (e - 1.0) / (e + 1.0);
    float a = _BandLam.x, b = _BandLam.y, c = _BandLam.z;
    float x = (ts - 0.5) / 0.25;
    return (b + 0.5 * (c - a) * x + 0.5 * (a - 2.0 * b + c) * x * x) * H0;
}

AS04V2F AS04Vert(AS04In v)
{
    AS04V2F o;
    UNITY_SETUP_INSTANCE_ID(v);
    UNITY_INITIALIZE_OUTPUT(AS04V2F, o);
    UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
    if (_AS03Src < 0.5)
    {
        float3 w = DS27WorldOrMesh(v.vid, v.vertex.xyz);
        o.wp = w;
        o.n0 = _DS27Enabled > 0.5 ? DS27Normal(v.vid) : normalize(v.c.xyz + 1e-6);
        float lam = AS04Lam(w.y);
        o.a = v.a;
        o.b = float4(max(v.b.x, 0.05) / lam, v.b.y, v.b.z, v.a.w / lam);
        o.c = float4(1, 1, v.c.w, 0);
        float T = _DS27Enabled > 0.5 ? _DS27White[v.vid] : -1e6;
        bool never = T >= 1e8;
        o.d = float4(lam, (T <= _DS27Tau && !never) ? 1.0 : 0.0, 0, 0);
        uint nu = DS27NU();
        uint r = nu > 0u ? v.vid / nu : 0u;
        o.rc = float2(r, v.vid - r * nu);
    }
    else
    {
        float3 w = mul(unity_ObjectToWorld, float4(v.vertex.xyz, 1.0)).xyz;
        o.wp = w;
        o.n0 = normalize(UnityObjectToWorldNormal(v.normal));
        if (_AS03Src < 1.5)
        {
            o.a = v.a; o.b = v.b; o.c = float4(v.c.xyz, 0);
            o.d = float4(v.d.z, v.d.w, 0, 0);
            o.rc = v.d.xy;
        }
        else
        {
            o.a = v.a; o.b = float4(1, 1, 0, 0);
            o.c = _MeshUseUV5 > 0.5 ? v.c : float4(1, 1, 10, 1);
            o.d = float4(1, 1, 0, 0);
            o.rc = float2(0, 0);
        }
    }
    o.pos = UnityWorldToClipPos(o.wp);
    return o;
}

// 1 本の帯の被覆（0〜1）。qpos：帯の中心の線の座標（2 進の分数で、段が変わっても同じ値＝同じ帯）、wgt：子の帯の育ち（0〜1）。
// 幅は帯ごとの対数正規（中央 _Band.x × λ、ばらつき _Band.y、_Band.z〜w に切る）、中心のずれは ±_BandVar.x/2 × λ、
// 巻きの向き u に沿って太さが揺れる（波長 _BandVar.y × 0.7〜1.3、振幅 _BandVar.z）。頂の側は白の境から _BandOn.y m で始まり、_BandVar.w m で太りきる。
float AS04OneBand(float qpos, float wgt, float q, float gq, float lam, float u, float below, float mpp)
{
    float h1 = AS04Hash(qpos * 1.000 + 0.123), h2 = AS04Hash(qpos * 1.370 + 4.100), h3 = AS04Hash(qpos * 2.110 + 7.700);
    float h4 = AS04Hash(qpos * 0.731 + 2.300), h5 = AS04Hash(qpos * 1.913 + 5.300), h6 = AS04Hash(qpos * 2.857 + 9.100);
    float z = (h1 + h2 + h3 - 1.5) * 2.0;                       // ほぼ標準正規
    float wf = clamp(_Band.x * exp(_Band.y * z), _Band.z, _Band.w);
    float offm = (h4 - 0.5) * _BandVar.x * lam;
    float Lk = max(_BandVar.y * (0.7 + 0.6 * h5), 0.5);
    float modu = max(1.0 + _BandVar.z * sin(6.2831853 * (u / Lk + h6)), 0.0);
    float top = AS04Smooth(_BandOn.y, _BandOn.y + _BandVar.w, below);
    float hw = 0.5 * wf * lam * modu * wgt * lerp(0.25, 1.0, top) * step(_BandOn.y, below);
    float d = abs((q - qpos) / max(gq, 1e-4) - offm);
    return hw > 1e-4 ? saturate(0.5 + (hw - d) / max(mpp * max(_AAScale, 1e-3), 1e-6)) : 0.0;
}

// 巻きに沿う藍中の帯の被覆。線の座標 q（等値線が巻きに沿う）、本数の段 Lq（下へ扇に開く所で子の帯が Y 字に分かれる）。
float AS04Bands(float q, float Lq, float gq, float lam, float u, float below, float mpp)
{
    float L0 = round(Lq);
    float fr = Lq - L0;
    float P0 = exp2(-L0);
    float x = q / P0;
    float kc = floor(x);
    float km = AS04Smooth(_Fork.x, _Fork.y, fr);
    float cov = 0.0;
    [unroll] for (int j = -1; j <= 2; j++)
        cov = max(cov, AS04OneBand((kc + j) * P0, 1.0, q, gq, lam, u, below, mpp));
    [unroll] for (int k = -1; k <= 1; k++)
        cov = max(cov, AS04OneBand((kc + k + 0.5) * P0, km, q, gq, lam, u, below, mpp));
    return cov;
}

// 藍の上の白い点：u・w の格子（_Fleck.x m）に 1 つまで。点の大きさは対数正規（半径の中央 _Fleck.y m、ばらつき _Fleck.z）、
// 形は 4〜6 角の不揃いな欠片（_FleckShape：x 歪み、y 角の強さ）。白の境からの深さで現れる（_FleckDepth.x〜y m、割合の上限 _FleckDepth.w）。
// su・sw：u・w の面の上の勾配の大きさ（1/m）で、点を面の上の m で丸くする。mpp：面の 1 画素の長さ m。
float AS04Flecks(float u, float w, float su, float sw, float below, float mpp)
{
    float cell = max(_Fleck.x, 0.05);
    float2 p = float2(u, w) / cell;
    float2 ci = floor(p);
    float prob = _FleckDepth.w * AS04Smooth(_FleckDepth.x, _FleckDepth.y, below);
    float cov = 0.0;
    [unroll] for (int iy = -1; iy <= 1; iy++)
    [unroll] for (int ix = -1; ix <= 1; ix++)
    {
        float2 c = ci + float2(ix, iy);
        float e = AS04Hash2(c + 0.17);
        if (e < prob)
        {
            float2 jit = float2(AS04Hash2(c + 3.1), AS04Hash2(c + 7.9));
            float2 ctr = c + 0.15 + 0.7 * jit;
            float zz = (AS04Hash2(c + 11.3) + AS04Hash2(c + 13.7) + AS04Hash2(c + 17.9) - 1.5) * 2.0;
            float r = clamp(_Fleck.y * exp(_Fleck.z * zz), 0.4 * _Fleck.y, 2.6 * _Fleck.y);
            float2 dm = (p - ctr) * cell / float2(max(su, 0.2), max(sw, 0.2));   // 面の上の m
            float th = atan2(dm.y, dm.x);
            float ph = 6.2831853 * AS04Hash2(c + 23.3);
            // 角のある欠片（原画の白い点は 4〜6 角の不揃いな欠片）：正 n 角形の縁の距離 × 2θ の歪み。_FleckShape.y = 0 なら丸
            float nside = 4.0 + floor(3.0 * AS04Hash2(c + 29.1));
            float seg = 6.2831853 / nside;
            float aa_ = th - ph;
            float am = aa_ - seg * floor(aa_ / seg) - 0.5 * seg;
            float poly = lerp(1.0, cos(0.5 * seg) / max(cos(am), 0.2), _FleckShape.y);
            float re = r * poly * (1.0 + _FleckShape.x * sin(2.0 * th + 1.7 * ph));
            float dd = length(dm) - re;
            float diamPx = 2.0 * r / max(mpp, 1e-6);
            float vis = saturate((diamPx - _FleckDepth.z) / max(_FleckDepth.z, 1e-3));   // 小さすぎる点（画素の中に入る点）は描かない
            cov = max(cov, vis * saturate(0.5 - dd / max(mpp * max(_AAScale, 1e-3), 1e-6)));
        }
    }
    return cov;
}

// 直しの回 1（fix1）：点の大きさ・形を面の上の m で測る式を、u・w の勾配が直交しない（剪断された）所でも正しくした。
// 前の版は (Δu/|∇u|, Δw/|∇w|) を面の上の m としていたので、u と w の等値線が平行に近い所（唇を短くした湾の端など）で、
// 点が面の上で細長い白い切り傷（縦横比 8〜34）になった。今は勾配の 2×2 の計量 G = [∇u·∇u, ∇u·∇w; ∇u·∇w, ∇w·∇w] の逆で
// 面の上の変位 d を出し（|d|² = Δᵀ G⁻¹ Δ）、面の上の正規直交の向き（∇u の向きと、法線 × それ）で角度を測る。
// さらに、u・w の格子の歪みが大きい所（G の固有値の比の平方根 > _FleckAniso.x）は点を出さない（_FleckAniso.y まででなめらかに消す）。
float4 _FleckAniso;
// u・w の格子の歪み（計量の固有値の比の平方根）。1 が正方の格子
float AS04FAniso(float3 gu, float3 gw)
{
    float g11 = dot(gu, gu), g12 = dot(gu, gw), g22 = dot(gw, gw);
    float det = g11 * g22 - g12 * g12;
    float tr = g11 + g22;
    float disc = sqrt(max(0.25 * tr * tr - det, 0.0));
    float lmax = 0.5 * tr + disc, lmin = max(0.5 * tr - disc, 1e-12);
    return det < 1e-10 ? 1e4 : sqrt(lmax / lmin);
}

float AS04FlecksM(float u, float w, float3 gu, float3 gw, float3 n0, float below, float mpp, float keep)
{
    float cell = max(_Fleck.x, 0.05);
    float2 p = float2(u, w) / cell;
    float2 ci = floor(p);
    float g11 = dot(gu, gu), g12 = dot(gu, gw), g22 = dot(gw, gw);
    float det = g11 * g22 - g12 * g12;
    float prob = _FleckDepth.w * AS04Smooth(_FleckDepth.x, _FleckDepth.y, below) * keep;
    if (det < 1e-10 || prob <= 0.0) return 0.0;
    float3 eu = (g22 * gu - g12 * gw) / det;      // Δu = 1 の面の上の変位（Δw = 0）
    float3 ew = (g11 * gw - g12 * gu) / det;      // Δw = 1 の面の上の変位（Δu = 0）
    float3 t1 = normalize(gu);
    float3 t2 = normalize(cross(n0, t1));
    float cov = 0.0;
    [unroll] for (int iy = -1; iy <= 1; iy++)
    [unroll] for (int ix = -1; ix <= 1; ix++)
    {
        float2 c = ci + float2(ix, iy);
        float e = AS04Hash2(c + 0.17);
        if (e < prob)
        {
            float2 jit = float2(AS04Hash2(c + 3.1), AS04Hash2(c + 7.9));
            float2 ctr = c + 0.15 + 0.7 * jit;
            float zz = (AS04Hash2(c + 11.3) + AS04Hash2(c + 13.7) + AS04Hash2(c + 17.9) - 1.5) * 2.0;
            float r = clamp(_Fleck.y * exp(_Fleck.z * zz), 0.4 * _Fleck.y, 2.6 * _Fleck.y);
            float2 dp = (p - ctr) * cell;
            float3 d3 = dp.x * eu + dp.y * ew;                                   // 面の上の変位（m）
            float2 dm = float2(dot(d3, t1), dot(d3, t2));
            float th = atan2(dm.y, dm.x);
            float ph = 6.2831853 * AS04Hash2(c + 23.3);
            // 角のある欠片（原画の白い点は 4〜6 角の不揃いな欠片）：正 n 角形の縁の距離 × 2θ の歪み。_FleckShape.y = 0 なら丸
            float nside = 4.0 + floor(3.0 * AS04Hash2(c + 29.1));
            float seg = 6.2831853 / nside;
            float aa_ = th - ph;
            float am = aa_ - seg * floor(aa_ / seg) - 0.5 * seg;
            float poly = lerp(1.0, cos(0.5 * seg) / max(cos(am), 0.2), _FleckShape.y);
            float re = r * poly * (1.0 + _FleckShape.x * sin(2.0 * th + 1.7 * ph));
            float dd = length(dm) - re;
            float diamPx = 2.0 * r / max(mpp, 1e-6);
            float vis = saturate((diamPx - _FleckDepth.z) / max(_FleckDepth.z, 1e-3));   // 小さすぎる点（画素の中に入る点）は描かない
            cov = max(cov, vis * saturate(0.5 - dd / max(mpp * max(_AAScale, 1e-3), 1e-6)));
        }
    }
    return cov;
}

// 直しの回 1（fix1）：u・w の格子が潰れた所（唇を短くした湾の内の面など、歪み > _FleckAniso.x）の白い点は、
// ワールドの 3 次元の格子（_Fleck.x m）に置いた点の中心を、面の接平面へ落として丸く描く（どの視点でも同じ所・同じ形。原画カメラは使わない）。
// 点の中心と面の距離が格子の半分より近い時だけ描くので、面の上の点の数は u・w の格子とほぼ同じ（1 m² あたり割合 × 1/格子²）。
float AS04Hash3(float3 p) { return frac(sin(dot(p, float3(127.1, 311.7, 74.7))) * 43758.5453); }

float AS04FlecksW(float3 wp, float3 n0, float below, float mpp, float keep)
{
    float cell = max(_Fleck.x, 0.05);
    float prob = _FleckDepth.w * AS04Smooth(_FleckDepth.x, _FleckDepth.y, below) * keep;
    if (prob <= 0.0) return 0.0;
    float3 t1 = cross(n0, float3(0, 1, 0));
    if (dot(t1, t1) < 1e-4) t1 = cross(n0, float3(1, 0, 0));
    t1 = normalize(t1);
    float3 t2 = cross(n0, t1);
    float3 ci = floor(wp / cell);
    float cov = 0.0;
    [loop] for (int iz = -1; iz <= 1; iz++)
    [loop] for (int iy = -1; iy <= 1; iy++)
    [loop] for (int ix = -1; ix <= 1; ix++)
    {
        float3 c = ci + float3(ix, iy, iz);
        float e = AS04Hash3(c + 0.17);
        if (e < prob)
        {
            float3 jit = float3(AS04Hash3(c + 3.1), AS04Hash3(c + 7.9), AS04Hash3(c + 5.3));
            float3 d3 = wp - (c + 0.15 + 0.7 * jit) * cell;
            if (abs(dot(d3, n0)) < 0.5 * cell)
            {
                float2 dm = float2(dot(d3, t1), dot(d3, t2));
                float zz = (AS04Hash3(c + 11.3) + AS04Hash3(c + 13.7) + AS04Hash3(c + 17.9) - 1.5) * 2.0;
                float r = clamp(_Fleck.y * exp(_Fleck.z * zz), 0.4 * _Fleck.y, 2.6 * _Fleck.y);
                float th = atan2(dm.y, dm.x);
                float ph = 6.2831853 * AS04Hash3(c + 23.3);
                float nside = 4.0 + floor(3.0 * AS04Hash3(c + 29.1));
                float seg = 6.2831853 / nside;
                float aa_ = th - ph;
                float am = aa_ - seg * floor(aa_ / seg) - 0.5 * seg;
                float poly = lerp(1.0, cos(0.5 * seg) / max(cos(am), 0.2), _FleckShape.y);
                float re = r * poly * (1.0 + _FleckShape.x * sin(2.0 * th + 1.7 * ph));
                float dd = length(dm) - re;
                float diamPx = 2.0 * r / max(mpp, 1e-6);
                float vis = saturate((diamPx - _FleckDepth.z) / max(_FleckDepth.z, 1e-3));
                cov = max(cov, vis * saturate(0.5 - dd / max(mpp * max(_AAScale, 1e-3), 1e-6)));
            }
        }
    }
    return cov;
}

// 1 次元のなめらかな値の揺れ（0〜1）
float AS04VNoise(float x)
{
    float i = floor(x), f = frac(x);
    float s = f * f * (3.0 - 2.0 * f);
    return lerp(AS04Hash(i + 0.37), AS04Hash(i + 1.37), s);
}

struct AS04Surf
{
    float3 n0;
    float whiteCov, zWhite, mizuCov, bandCov, fleckCov, sea;
    float glaze;
};

AS04Surf AS04Pattern(AS04V2F i, bool front)
{
    AS04Surf s;
    float3 n0 = normalize(i.n0);
    if (!front) n0 = -n0;
    s.n0 = n0; s.mizuCov = 0; s.bandCov = 0; s.fleckCov = 0; s.sea = 0; s.glaze = 0;
    float aa = max(_AAScale, 1e-3);
    // 画面の微分（分岐の外で）
    float F = i.a.x, u = i.a.z, w = i.a.w;
    float hrow = i.b.y, q = i.b.w, gq = max(i.b.x, 1e-3), Lq = i.b.z, lam = max(i.d.x, 0.05);
    float wsd = i.c.z;
    float fw_wsd = max(fwidth(wsd), 1e-6);
    float fw_q = max(fwidth(q), 1e-7);
    float3 dpx = ddx(i.wp), dpy = ddy(i.wp);
    float dux = ddx(u), duy = ddy(u), dwx = ddx(w), dwy = ddy(w);
    if (_AS03Src > 1.5)
    {
        s.zWhite = wsd / fw_wsd;
        s.whiteCov = saturate(0.5 + s.zWhite / aa);
        s.glaze = 1;
        return s;
    }
    // u・w の面の上の勾配（画面の微分から）
    float den = dot(n0, cross(dpx, dpy));
    den = abs(den) > 1e-12 ? den : 1e-12;
    float3 gu = (dux * cross(dpy, n0) + duy * cross(n0, dpx)) / den;
    float3 gw = (dwx * cross(dpy, n0) + dwy * cross(n0, dpx)) / den;
    float su = length(gu), sw = length(gw);
    float mppU = max(sqrt(dux * dux + duy * duy), 1e-7) / max(su, 1e-3);   // u の向きの 1 画素の m
    float mppW = max(sqrt(dwx * dwx + dwy * dwy), 1e-7) / max(sw, 1e-3);
    float mpp = min(mppU, mppW);
    // ---- 白
    float z = wsd / fw_wsd;
    if (i.d.y < 0.5) z = -1e4;
    s.zWhite = z;
    s.whiteCov = saturate(0.5 + z / aa);
    float frontM = AS04Smooth(-0.25, 0.25, u);
    // ---- 白の前の縁の水色の帯（幅 W(w)：_MizuFringe.x〜y m、揺れの波長 _MizuFringe.z m）
    if (_MizuFringe.w > 0.5)
    {
        float W = lerp(_MizuFringe.x, _MizuFringe.y, AS04VNoise(w / max(_MizuFringe.z, 0.1)));
        float wi = wsd - _MizuInset;                              // 境から _MizuInset m は白のまま（白い舌の先）、その奥に幅 W の水色
        s.mizuCov = s.whiteCov * frontM * saturate(0.5 + wi / (fw_wsd * aa)) * saturate(0.5 + (W - wi) / (fw_wsd * aa));
    }
    // ---- 面（藍）
    float footM = AS04Smooth(0.06, 0.12, hrow) * AS04Smooth(4.12, 3.92, F);
    float mask = frontM * footM;                                  // 前の面（白い点と帯）
    float maskB = lerp(_BandBack, 1.0, frontM) * footM;           // 帯は背の藍にも _BandBack の強さで描く（背の形が読めるように）
    s.sea = max(max(1.0 - AS04Smooth(-0.15, 0.2, F), AS04Smooth(3.9, 4.25, F)), 1.0 - AS04Smooth(0.12, 0.25, hrow));
    float below = -wsd;
    if (_BandOn.x > 0.5 && maskB > 1e-3)
    {
        float mppQ = fw_q / gq;                                   // 線に直交する向きの 1 画素の m
        float periodPx = lam / max(mppQ, 1e-6);
        float fpx = saturate((periodPx - _BandOn.z) / max(_BandOn.w - _BandOn.z, 1e-3));
        float bc = AS04Bands(q, Lq, gq, lam, u, below, mppQ);
        s.bandCov = maskB * lerp(_Fork.z, bc, fpx) * AS04Smooth(_BandOn.y, _BandOn.y + 0.05, below);
    }
    if (_Fleck.w > 0.5 && mask > 1e-3)
    {
        // fix1：歪みの小さい所は u・w の格子（面の計量で丸く）、歪みの大きい所はワールドの格子（_FleckAniso.x〜y で入れ替える）
        float2 an = _FleckAniso.y > _FleckAniso.x ? _FleckAniso.xy : float2(3.0, 4.0);
        float wA = AS04Smooth(an.x, an.y, AS04FAniso(gu, gw));
        float fM = wA < 0.999 ? AS04FlecksM(u, w, gu, gw, n0, below, mpp, 1.0 - wA) : 0.0;
        float fW = wA > 0.001 ? AS04FlecksW(i.wp, n0, below, mpp, wA) : 0.0;
        s.fleckCov = mask * max(fM, fW);
    }
    return s;
}

// 測りの道（ID と主役波の印）。戻り値の w が 0 なら測りではない
float4 AS04Diag(AS04V2F i, AS04Surf s)
{
    if (_PL29Diag > 0.5 && _PL29Diag < 1.5)
    {
        if (_AS03Src > 1.5) return float4(0, 0, 0, 1);
        uint col = (uint)(i.rc.y + 0.5);
        uint row = (uint)(i.rc.x + 0.5);
        return float4(row / 255.0, (col & 255u) / 255.0, (col >> 8) / 255.0, 128.0 / 255.0);
    }
    if (_AF28IdMode > 0.5)
    {
        int cls = s.whiteCov >= 0.5 ? (s.mizuCov >= 0.5 ? 1 : 0) : (s.fleckCov >= 0.5 ? 0 : (s.bandCov >= 0.5 ? 2 : 3));
        float3 c = cls == 0 ? float3(1, 0, 0) : (cls == 1 ? float3(0, 1, 0) : (cls == 2 ? float3(0, 0, 1) : float3(1, 1, 0)));
        return float4(c, 1);
    }
    return float4(0, 0, 0, 0);
}

#endif
