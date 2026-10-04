// 美術の見本03 の作り B2（Q31）：主役波の彫りの面と、冠・爪の白い釉を同じ式で描く 2 つのシェーダー（FLAT・SCULPT）の共通部。
// 原画カメラの投影は使わない（Q28）。色・模様は頂点の属性（面の座標・高さ・稜の線の座標）とワールドに固定した光だけで決まり、
// どこから見ても同じ面は同じ色になる。SCULPT の艶（鏡の光と周りの映り込み）だけが、本物の釉のように見る位置で動く。
// 頂点の出どころ（材質の _AS03Src）：
//   0 = 主役波の keypose（DS30SheetPlayer。属性は見本02 の UV3 = (F, hrel, u, w)、UV4 = (gw, hrow, Ls, X·L̂)、UV5 = (法線, 0)）。稜は画素の傾き（バンプ）だけ。
//   1 = 主役波の静止のメッシュ（surf_relief.py。稜を本当の凹凸として刻んだ t* の面）。NORMAL = 刻む前の滑らかな法線、TANGENT = ∇q の向き、
//       UV3 = (F, hrel, u, w)、UV4 = (gq = |∇q|, hrow, Lq, q)、UV5 = (ao, keyVis, whiteSD, fade)、UV6 = (行, 列, λ, 白の時刻が来たか)。
//   2 = 冠・爪などの白い釉のメッシュ（B1。shared/README の約束）。NORMAL、UV5 = (ao, keyVis, whiteSD, 種類)。_MeshUseUV5 = 0 なら (1, 1, 10, 1)。
// 稜の式 AS03GrooveH は Tools/GWWaveGen/as03/surf_common.py の groove_h と同じ（どちらかを変えたら両方を変える）。
// 測りの道：大域の _AF28IdMode = 1 で色区 ID（白 赤・白の陰 緑・溝の線 青・稜 黄）、_PL29Diag = 1 で主役波の印（行・列。PL29 と同じ符号）。
#ifndef GREATWAVE_AS03_COMMON_INCLUDED
#define GREATWAVE_AS03_COMMON_INCLUDED

#include "../../Design27/Shaders/DS27Keypose.cginc"

float _AS03Src, _WhiteSrc, _MeshUseUV5, _MeshMizuiro;
float4 _White, _WhiteShade, _AiRidge, _AiRidgeLit, _AiDeep, _GrooveCol, _GrooveShade, _LineCol, _MeshTint;
float4 _Groove;        // x 深さ／周期（keypose の道の稜の深さ）, y 淡い水色の溝の幅／周期, z 玉縁, w 断面の指数
float4 _GrooveLod;     // x, y 子の溝が分かれる段の端数, z, w 画面の周期がこの画素の間で溝を消す
float4 _GrooveLam;     // x 下の面（0.25 H 以下）, y 中ほど（0.5 H）, z 冠の下（0.75 H 以上）の周期／H, w H0（m）
float4 _GrooveOn;      // x 1 で描く, y keypose の道の白の縁からの現れの長さ m, z 法線の傾きの強さ, w 溝の底の暗さ（SCULPT）
float4 _BackB, _CapFront;
float _MinRowH, _EdgeLinePx, _AAScale;
float4 _EdgeGrazing;
float4 _LightDir, _FillDir;
float4 _KeyCol, _FillCol, _SkyCol, _GroundCol;
float4 _Wrap;          // x 回り込み, y 焼いた影の強さ, z AO の強さ, w FLAT の陰の段の閾値
float4 _SpecWhite;     // x 鋭さ, y 強さ, z 映り込みの強さ, w F0
float4 _SpecAi;        // 同じ（藍）
float4 _EnvHorizon, _EnvWin, _EnvSky, _EnvGround;   // 映り込みの空：地平・窓の光・空・地（暗い部屋の中の釉のように、窓のほかは暗い）
float4 _WinDir;        // 窓の光の向き（ワールド）, w 鋭さ
float4 _FlatRib;       // x FLAT の稜の 2 段の強さ, y 光の側へ寄せる量
float4 _FlatAO;        // x FLAT の AO の段の閾値, y 強さ
float _AF28IdMode, _PL29Diag;
float _Shoulder, _EnvWinK;
float4 _SeaCol;

struct AS03In
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

struct AS03V2F
{
    float4 pos : SV_POSITION;
    float3 wp : TEXCOORD0;
    float3 n0 : TEXCOORD1;
    float3 tq : TEXCOORD2;
    float4 a : TEXCOORD3;      // F, hrel, u, w（冠：f, 番号, 種類, 0）
    float4 b : TEXCOORD4;      // gq, hrow, Lq, q
    float4 c : TEXCOORD5;      // ao, keyVis, whiteSD, fade
    float4 d : TEXCOORD6;      // λ, 白の時刻が来たか, T_white の印, 0
    nointerpolation float2 rc : TEXCOORD7;
    UNITY_VERTEX_OUTPUT_STEREO
};

float AS03Smooth(float e0, float e1, float x) { float t = saturate((x - e0) / (e1 - e0)); return t * t * (3.0 - 2.0 * t); }

float AS03Lam(float y)
{
    float H0 = max(_GrooveLam.w, 1.0);
    float t = y / H0;
    float e = exp(2.0 * clamp((t - 0.5) / 0.3, -10.0, 10.0));
    float ts = 0.5 + 0.3 * (e - 1.0) / (e + 1.0);                    // 0.5 + 0.3 tanh((t − 0.5)/0.3)
    float a = _GrooveLam.x, b = _GrooveLam.y, c = _GrooveLam.z;
    float x = (ts - 0.5) / 0.25;
    return (b + 0.5 * (c - a) * x + 0.5 * (a - 2.0 * b + c) * x * x) * H0;   // surf_common.GrooveParams.lam と同じ
}

AS03V2F AS03Vert(AS03In v)
{
    AS03V2F o;
    UNITY_SETUP_INSTANCE_ID(v);
    UNITY_INITIALIZE_OUTPUT(AS03V2F, o);
    UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
    if (_AS03Src < 0.5)
    {
        float3 w = DS27WorldOrMesh(v.vid, v.vertex.xyz);
        o.wp = w;
        o.n0 = _DS27Enabled > 0.5 ? DS27Normal(v.vid) : normalize(v.c.xyz + 1e-6);
        o.tq = float3(0, 0, 0);
        float lam = AS03Lam(w.y);
        o.a = v.a;
        o.b = float4(max(v.b.x, 0.05) / lam, v.b.y, v.b.z, v.a.w / lam);
        o.c = float4(1, 1, v.c.w, 1);   // C.w：白の印の符号付きの距離 m（surf_kp_attr.py。_WhiteSrc = 1 で使う）
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
        o.tq = normalize(mul((float3x3)unity_ObjectToWorld, v.tangent.xyz) + 1e-6);
        if (_AS03Src < 1.5)
        {
            o.a = v.a; o.b = v.b; o.c = v.c;
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

float AS03Hash1(float x) { return frac(sin(x * 127.1 + 311.7) * 43758.5453); }

// 見本02 の白の境（S01A Groove Keypose と同じ式）。画素の符号付き距離（正が白）を返す。
float AS03WhiteZ02(float F, float hrel, float u, float w, float hrow)
{
    float bb = _BackB.x + _BackB.y * sin(6.2831853 * w / max(_BackB.z, 0.1)) + _BackB.w * sin(6.2831853 * w / max(0.43 * _BackB.z, 0.1) + 1.7);
    float vb = hrel - bb;
    float zBack = vb / max(fwidth(vb), 1e-6);
    float capEdge = _CapFront.x;
    if (_CapFront.w > 0.5)
    {
        float P = max(_CapFront.y, 0.1);
        float ws = w + 0.22 * P * sin(6.2831853 * w / (3.7 * P)) + 0.12 * P * sin(6.2831853 * w / (1.9 * P) + 1.1);
        float fi = floor(ws / P);
        float s = ws / P - fi;
        float x = (s - 0.5) / 0.42;
        float prof = sqrt(saturate(1.0 - x * x));
        float len = _CapFront.z * (0.65 + 0.7 * AS03Hash1(fi * 1.37 + 2.9));
        capEdge += len * prof - 0.35 * _CapFront.z;
    }
    float vc = capEdge - u;
    float zCap = vc / max(fwidth(vc), 1e-6);
    float z = u < 0.0 ? zBack : zCap;
    float vf = F + 0.25; z = min(z, vf / max(fwidth(vf), 1e-6));
    float vh = hrow - _MinRowH; z = min(z, vh / max(fwidth(vh), 1e-6));
    return z;
}

// 稜の高さ（m）。q：線の座標、Lq：本数の段、gq = |∇q|（1/m）、lam：周期 m。d：近い溝の中心からの距離 m、gh：溝の半幅 m。
float AS03GrooveH(float q, float Lq, float gq, float lam, float depth, float gfrac, float bead, float pexp, out float d, out float gh)
{
    float L0 = round(Lq);
    float fr = Lq - L0;
    float P0 = exp2(-L0);
    float x = q / P0;
    float g = x - floor(x);
    float km = AS03Smooth(_GrooveLod.x, _GrooveLod.y, fr);
    float s = 0.5 * km;
    bool has = km > 1e-4;
    bool inA = has && (g < s);
    float a = inA ? 0.0 : (has ? s : 0.0);
    float b = inA ? s : 1.0;
    float igq = 1.0 / max(gq, 1e-4);
    float G = (b - a) * P0 * igq;
    d = min(g - a, b - g) * P0 * igq;
    gh = 0.5 * gfrac * lam;
    float R = 0.5 * G - gh;
    float Rn = max(0.5 * lam - gh, 1e-4);
    float xg = saturate(d / max(gh, 1e-6));
    float hg = -0.5 * depth + bead * depth * (1.0 - xg * xg);
    float xr = saturate((0.5 * G - d) / max(R, 1e-5));
    float amp = depth * saturate(R / Rn);
    float hr = -0.5 * depth + amp * pow(saturate(1.0 - pow(max(xr, 1e-6), pexp)), 1.0 / pexp);
    return (d < gh || R <= 0.0) ? hg : hr;
}

float3 AS03IdColour(int k)
{
    return k == 0 ? float3(1, 0, 0) : (k == 1 ? float3(0, 1, 0) : (k == 2 ? float3(0, 0, 1) : float3(1, 1, 0)));
}

// 映り込みの空（ワールドの向き R。視点によらない世界の明るさの分布）：地は暗い海、空は淡く、窓の光が 2 つ
float3 AS03Env(float3 R)
{
    float up = saturate(R.y * 1.6 + 0.15);
    float3 e = lerp(_EnvGround.rgb, lerp(_EnvHorizon.rgb, _EnvSky.rgb, saturate(R.y)), up);
    float3 L = normalize(_LightDir.xyz);
    float w1 = pow(saturate(dot(R, L)), 28.0);
    float w2 = pow(saturate(dot(R, normalize(_WinDir.xyz))), max(_WinDir.w, 1.0));
    return e + _EnvWin.rgb * max(_EnvWinK, 0.0) * (1.6 * w1 + 0.9 * w2);
}

struct AS03Surf
{
    float3 n0;        // 滑らかな法線（表の側）
    float3 n;         // 稜の傾きを足した法線
    float whiteCov;   // 白の割合
    float zWhite;     // 白の境の画素の符号付き距離
    float lineCov;    // 溝の淡い水色の線
    float grooveDepthFrac;   // 溝の底の深さの割合（0 稜の山 〜 1 溝の底）
    float ao, kv;
    float glaze;      // 1 = 冠・爪の白い釉
    float sea;        // 1 = 主役波の裾（背の足より外 F < 0・前の面の下より先 F > 4・頂の低い遠い行）。周りの海と同じ平らな藍にする割合
};

AS03Surf AS03Pattern(AS03V2F i, bool front)
{
    AS03Surf s;
    float3 n0 = normalize(i.n0);
    if (!front) n0 = -n0;
    s.n0 = n0; s.n = n0; s.lineCov = 0; s.grooveDepthFrac = 0; s.glaze = 0; s.sea = 0;
    s.ao = lerp(1.0, saturate(i.c.x), _Wrap.z);
    s.kv = lerp(1.0, saturate(i.c.y), _Wrap.y);
    float aa = max(_AAScale, 1e-3);
    if (_AS03Src > 1.5)
    {
        float wsd = i.c.z;
        s.zWhite = wsd / max(fwidth(wsd), 1e-6);
        s.whiteCov = saturate(0.5 + s.zWhite / aa);
        s.glaze = 1;
        return s;
    }
    float F = i.a.x, hrel = i.a.y, u = i.a.z, w = i.a.w;
    float hrow = i.b.y;
    s.sea = max(max(1.0 - AS03Smooth(-0.15, 0.2, F), AS03Smooth(3.9, 4.25, F)), 1.0 - AS03Smooth(0.12, 0.25, hrow));
    // ---- 白
    float z;
    if (_WhiteSrc < 0.5) z = AS03WhiteZ02(F, hrel, u, w, hrow);
    else { float wsd = i.c.z; z = wsd / max(fwidth(wsd), 1e-6); }
    if (i.d.y < 0.5) z = -1e4;
    s.zWhite = z;
    s.whiteCov = saturate(0.5 + z / aa);
    // ---- 稜
    float fade = i.c.w;
    if (_AS03Src < 0.5)
    {
        // keypose の道：白の縁（頂の前）からの u の距離で現れる。背（u < 0）には刻まない
        float capEdge = _CapFront.x;
        float fw = _WhiteSrc > 0.5 ? AS03Smooth(0.0, _GrooveOn.y, -i.c.z)                       // B1 の白の印からの距離（属性の C.w）
                                   : AS03Smooth(0.0, _GrooveOn.y, u - capEdge - 0.4 * _CapFront.z);   // 見本02 の頂の白の縁から
        fade = (u >= 0.0 ? fw : 0.0) * AS03Smooth(0.06, 0.12, hrow) * AS03Smooth(4.12, 3.92, F);
    }
    if (_GrooveOn.x > 0.5 && fade > 1e-3)
    {
        float q = i.b.w, gq = max(i.b.x, 1e-3), Lq = i.b.z, lam = max(i.d.x, 0.05);
        float dqpx = max(fwidth(q), 1e-7);
        float mpp = dqpx / gq;                                   // 溝に直交する向きの 1 画素の面の長さ m
        float periodPx = lam / max(mpp, 1e-6);
        float fpx = saturate((periodPx - _GrooveLod.z) / max(_GrooveLod.w - _GrooveLod.z, 1e-3));
        float depth = _Groove.x * lam * fade;
        float gfr = _Groove.y * (0.45 + 0.55 * sqrt(fade));
        float d, gh, d1, gh1, d2, gh2;
        float h = AS03GrooveH(q, Lq, gq, lam, depth, gfr, _Groove.z, _Groove.w, d, gh);
        float eps = 0.004;
        float hp = AS03GrooveH(q + eps, Lq, gq, lam, depth, gfr, _Groove.z, _Groove.w, d1, gh1);
        float hm = AS03GrooveH(q - eps, Lq, gq, lam, depth, gfr, _Groove.z, _Groove.w, d2, gh2);
        float slope = clamp((hp - hm) / (2.0 * eps) * gq, -4.0, 4.0);  // dh/ds（∇q の向きの面の長さあたり）
        float3 T = i.tq;
        if (_AS03Src < 0.5 || dot(T, T) < 0.25)
        {
            // keypose の道：画面の微分から面の上の ∇q の向き
            float3 dpx = ddx(i.wp), dpy = ddy(i.wp);
            float dqx = ddx(q), dqy = ddy(q);
            float3 gv = dqx * cross(dpy, n0) + dqy * cross(n0, dpx);
            float den = dot(n0, cross(dpx, dpy));
            T = gv / (abs(den) > 1e-12 ? den : 1e-12);
        }
        T = normalize(T - n0 * dot(T, n0) + 1e-7);
        s.n = normalize(n0 - slope * _GrooveOn.z * fpx * (1.0 - s.whiteCov) * T);   // 白の上には稜を刻まない
        float lc = saturate(0.5 + (gh - d) / max(mpp * aa, 1e-6)) * saturate(2.0 * gh / max(mpp, 1e-6) - 0.3);
        s.lineCov = lc * fpx * (1.0 - s.whiteCov);
        s.grooveDepthFrac = saturate((0.5 * depth - h) / max(depth, 1e-6)) * fpx;
    }
    return s;
}

// 測りの道（ID と主役波の印）。戻り値の w が 0 なら測りではない
float4 AS03Diag(AS03V2F i, AS03Surf s, bool flatShadow, float litFlat)
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
        int cls = s.whiteCov >= 0.5 ? ((flatShadow && litFlat < 0.5) ? 1 : 0) : (s.lineCov >= 0.5 ? 2 : 3);
        return float4(AS03IdColour(cls), 1);
    }
    return float4(0, 0, 0, 0);
}

#endif
