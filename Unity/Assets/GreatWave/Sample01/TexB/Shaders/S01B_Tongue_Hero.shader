// 美術の見本01・見本 B（Q29：原画のような舌形）：主役波の視点によらない立体の材質。原画カメラの投影は使わない。
//   ・前（F ≥ 1）の模様は、面の座標 (u, w)（美術の見本01 の部 A の s01_param。t* の面の上の巻きの向きの弧長 u と、頂に並ぶ向きの w、どちらも m）の上に
//     設計して焼いた符号付きの距離のテクスチャ（大域の _S01BDesign、s01b_design.py）で決める：白い頂（R）、淡い水色の爪の帯（G）、藍濃の舌（B。外は藍中の線）、
//     藍濃の中の白い点（A）。どれも m の距離なので、画面の微分（fwidth）でアンチエイリアスする（画素の太さは視点で変わるが、形は面の上で決まる）。
//   ・背（F < 1）は行の相対の高さ hrel で白（彫刻の白い背）、その下は藍濃に藍中の線。第 2 版（2026-10-03）から、この線も同じ (u, w) の上に
//     設計したテクスチャの B・A（背の線は巻きの向きに一様な間。_BackDesign.x = 1）。低い行と範囲の外は仕上げ29 と同じ溝（周りの海とのつなぎ）。
//   ・前面の下（F > _Zone.y）と低すぎる行は、舌から背と同じ藍の胴（溝）へ移る（周りの海とのつなぎ）。
// 頂点の属性（s01b_design.py の s01b_attr_f32.bin。PL29UkiyoeHero が UV3・UV4・UV5 に入れる）：
//   A = (F 流れの座標：背の足 0・頂 1・唇の先 2・管の奥 3・前面の下 4・端 5, hrel 行の相対の高さ, kc 行の間隔の倍率, hrow 行の頂の高さ／H0)
//   B = (s 行ごとの弧長 m, c 行の座標 m, U = u m, V = w m)            ← 仕上げ29 の dtip・dtop を (u, w) に置き換えた
//   C = (t* の法線 xyz, ca 列ごとの弧長 m)
// 大域：_S01BDesign（RGBAHalf、行 = u、列 = w）、_S01BRect = (U0, V0, h, 0)、_S01BSize = (行の数, 列の数, 0, 0)。S01BRender が読み込んで渡す。
// ID 表示（大域の _AF28IdMode = 1）：白 赤、淡い水色 緑、藍中 青、藍濃 黄（評価器の色区の読み。設計27 の約束）。
// 診断（大域の _PL29Diag）：1 = 主役波の印と行・列（PL29 と同じ）。名前に Keypose を含むのは、ID の描画（KeepMaterial）がこの材質を残すため。
Shader "GreatWave/Sample01/S01B Tongue Keypose"
{
    Properties
    {
        _White ("白・生成り", Color) = (0.97255, 0.95294, 0.87451, 1)
        _Mizuiro ("淡い水色", Color) = (0.77647, 0.84314, 0.79608, 1)
        _AiMid ("藍中", Color) = (0.17255, 0.41176, 0.57647, 1)
        _AiDark ("藍濃", Color) = (0.13725, 0.25098, 0.38039, 1)
        _LineCol ("藍の線", Color) = (0.2784314, 0.3137255, 0.372549, 1)
        _BackB ("背の白の境 b（行の相対の高さ。c の節の左・中・右・右端）", Vector) = (0.41, 0.41, 0.24, 0.10)
        _BackC ("背の白の境の c の節（m）", Vector) = (-30, -8, 6, 14)
        _BackWave ("背の境のうねり（振幅：行の高さの倍、波長 m（ca））", Vector) = (0.02, 7, 0, 0)
        _MinRowH ("白を付ける行の頂の高さの下限（H0 の倍）", Float) = 0.08
        _Zone ("前の模様の範囲：x 始まりの F（背とのつなぎ）、y 前面の下で胴へ移る F、z 移る幅（F）、w 行の頂の高さの下限（H0 の倍）", Vector) = (0.98, 4.35, 0.25, 0.06)
        _ShadeDir ("白の陰（淡い水色）の向き（ワールド）", Vector) = (0, 1, -0.6, 0)
        _ShadeK ("白の陰の閾値（背の白だけ。法線との内積がこれ未満）", Float) = -0.35
        _GrooveLambda ("胴の溝の 3 次元の周期 λ（m）", Float) = 0.95
        _GrooveRatio ("胴の溝の幅／周期（x 上、y 下）", Vector) = (0.18, 0.32, 0, 0)
        _GrooveWander ("胴の溝のうねり（x 振幅：周期の倍、y 波長 m）", Vector) = (0.08, 9, 0, 0)
        _GrooveDash ("胴の溝の切れ（x 長さ m、y 埋める割合、z 1 で切る）", Vector) = (8.0, 0.9, 1, 0)
        _GrooveFadePx ("溝を消す周期の画素（x 消える、y 全部）", Vector) = (3, 6, 0, 0)
        _EdgeLinePx ("白と藍の境の線（画素。0 で描かない）", Float) = 1.5
        _MizLinePx ("淡い水色の帯と藍の境の線（画素。0 で描かない）", Float) = 1.0
        _EdgeGrazing ("線を薄める面の傾き（x 消える |n·v|、y 全部）", Vector) = (0.06, 0.2, 0, 0)
        _DotMinPx ("白い点を描く最小の半径（画素）", Float) = 0.7
        _AAScale ("アンチエイリアスの幅（画素）", Float) = 1
        _BackDesign ("背の胴（白の下）も設計のテクスチャの線にする（x 1 で使う、y 始まりの F、z 移る幅の F）", Vector) = (1, -0.3, 0.1, 0)
        _WLines ("改善の回 1（美術監督の項目 5）白の上の淡い水色の流れの線（w の等値線）：x 濃さ（0 で描かない）、y 間 m、z 幅／間、w 消える周期の画素", Vector) = (0, 1.9, 0.07, 6)
        _DesignBicubic ("改善の回 1（項目 7）設計のテクスチャを 3 次の B スプラインで読む（1。0 は前の双線形＝縞の縁の段）", Float) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "S01BTongue"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile _ DS27_POS_LO
            #include "../../../Design27/Shaders/DS27Keypose.cginc"

            float4 _White, _Mizuiro, _AiMid, _AiDark, _LineCol;
            float4 _BackB, _BackC, _BackWave, _Zone, _ShadeDir, _GrooveRatio, _GrooveWander, _GrooveDash, _GrooveFadePx, _EdgeGrazing, _BackDesign, _WLines;
            float _MinRowH, _ShadeK, _GrooveLambda, _EdgeLinePx, _MizLinePx, _DotMinPx, _AAScale, _DesignBicubic;
            float _AF28IdMode;          // 大域。1 で色区の ID
            float _DS27WhiteEnabled;    // 大域。0 で白の時刻を見ない（終態）
            float _PL29Diag;            // 大域。1 主役波の印と行・列
            sampler2D _S01BDesign;      // 大域（S01BRender）
            float4 _S01BRect, _S01BSize;

            // 改善の回 1（項目 7）：符号付きの距離のテクスチャを 3 次の B スプラインで読む（双線形 4 回。テクセルの格子の段が縞の縁に出ない）
            float4 DesignBicubic(float2 uv, float2 texSize)
            {
                float2 st = uv * texSize - 0.5;
                float2 i0 = floor(st);
                float2 f = st - i0;
                float2 f2 = f * f, f3 = f2 * f;
                float2 w0 = (-f3 + 3.0 * f2 - 3.0 * f + 1.0) / 6.0;
                float2 w1 = (3.0 * f3 - 6.0 * f2 + 4.0) / 6.0;
                float2 w2 = (-3.0 * f3 + 3.0 * f2 + 3.0 * f + 1.0) / 6.0;
                float2 w3 = f3 / 6.0;
                float2 g0 = w0 + w1, g1 = w2 + w3;
                float2 h0 = (i0 - 1.0 + w1 / max(g0, 1e-6) + 0.5) / texSize;
                float2 h1 = (i0 + 1.0 + w3 / max(g1, 1e-6) + 0.5) / texSize;
                float2 dx = ddx(uv), dy = ddy(uv);
                return g0.y * (g0.x * tex2Dgrad(_S01BDesign, float2(h0.x, h0.y), dx, dy) + g1.x * tex2Dgrad(_S01BDesign, float2(h1.x, h0.y), dx, dy))
                     + g1.y * (g0.x * tex2Dgrad(_S01BDesign, float2(h0.x, h1.y), dx, dy) + g1.x * tex2Dgrad(_S01BDesign, float2(h1.x, h1.y), dx, dy));
            }

            struct appdata
            {
                float4 vertex : POSITION;
                float4 a : TEXCOORD3;
                float4 b : TEXCOORD4;
                float4 nst : TEXCOORD5;
                uint vid : SV_VertexID;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float4 a : TEXCOORD0;
                float4 b : TEXCOORD1;
                float3 n : TEXCOORD2;
                float tw : TEXCOORD3;
                float2 fl : TEXCOORD4;
                nointerpolation float2 rc : TEXCOORD5;
                float4 nst : TEXCOORD6;
                float3 wp : TEXCOORD7;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 w = DS27WorldOrMesh(v.vid, v.vertex.xyz);
                o.pos = UnityWorldToClipPos(w);
                o.wp = w;
                o.a = v.a;
                o.b = v.b;
                o.n = _DS27Enabled > 0.5 ? DS27Normal(v.vid) : float3(0, 1, 0);
                o.nst = v.nst;
                float T = _DS27Enabled > 0.5 ? _DS27White[v.vid] : -1e6;
                bool never = T >= 1e8;
                o.tw = never ? _DS27Tau + 1.0 : T;
                o.fl = float2(T <= _DS27Tau ? 1.0 : 0.0, never ? 1.0 : 0.0);
                uint nu = DS27NU();
                uint r = nu > 0u ? v.vid / nu : 0u;
                o.rc = float2(r, v.vid - r * nu);
                return o;
            }

            float Px(float v) { return v / max(fwidth(v), 1e-6); }
            float Hash1(float x) { return frac(sin(x * 127.1 + 311.7) * 43758.5453); }

            float BackB(float c)
            {
                float4 k = _BackC, b = _BackB;
                if (c <= k.x) return b.x;
                if (c <= k.y) return lerp(b.x, b.y, (c - k.x) / max(k.y - k.x, 1e-3));
                if (c <= k.z) return lerp(b.y, b.z, (c - k.y) / max(k.z - k.y, 1e-3));
                if (c <= k.w) return lerp(b.z, b.w, (c - k.z) / max(k.w - k.z, 1e-3));
                return b.w;
            }

            float3 IdColour(int k)
            {
                return k == 0 ? float3(1, 0, 0) : (k == 1 ? float3(0, 1, 0) : (k == 2 ? float3(0, 0, 1) : float3(1, 1, 0)));
            }

            // 胴の溝（仕上げ29 の FlowLines と同じ：行の c の上に 3 次元の周期 lam3、kc で本数を 2 倍ずつ）
            float FlowLines(float q, float kc, float lam3, float ratio, float sa, float fq, out float periodPx)
            {
                float lv = log2(max(kc, 1e-3));
                float L0 = floor(lv);
                float fr = lv - L0;
                float P0 = lam3 * exp2(-L0);
                float qn = q / P0;
                float g = frac(qn);
                float dBase = min(g, 1.0 - g) * P0;
                float dMid = abs(g - 0.5) * P0;
                float idB = round(qn) * P0, idM = (floor(qn) + 0.5) * P0;
                float tB = 1.0, tM = 1.0;
                if (_GrooveDash.z > 0.5)
                {
                    float duty = saturate(_GrooveDash.y);
                    bool nearBase = dBase <= dMid;
                    float uu = frac(sa / max(_GrooveDash.x, 0.1) + Hash1(round((nearBase ? idB : idM) * 16.0)));
                    float tt = uu < duty ? pow(saturate(sin(3.14159265 * uu / max(duty, 1e-3))), 0.35) : 0.0;
                    tB = nearBase ? tt : 1.0;
                    tM = nearBase ? 1.0 : tt;
                }
                float hw3 = 0.5 * ratio * lam3;
                float hB = hw3 * tB / kc, hM = hw3 * tM * fr / kc;
                float covB = saturate(0.5 + (hB - dBase) / fq) * saturate(2.0 * hB / fq - 0.5);
                float covM = saturate(0.5 + (hM - dMid) / fq) * saturate(2.0 * hM / fq - 0.5);
                periodPx = 0.5 * P0 / fq;
                return max(covB, covM);
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float F = i.a.x, hrel = i.a.y, kc = max(i.a.z, 0.05), hrow = i.a.w;
                float s = i.b.x, c = i.b.y, U = i.b.z, V = i.b.w;
                float ca = i.nst.w;
                if (_PL29Diag > 0.5 && _PL29Diag < 1.5)
                {
                    uint col = (uint)(i.rc.y + 0.5);
                    return float4(i.rc.x / 255.0, (col & 255u) / 255.0, (col >> 8) / 255.0, 128.0 / 255.0);
                }
                float aa = max(_AAScale, 1e-3);

                // ---- 設計のテクスチャ（m の符号付きの距離）
                float2 tuv = float2(((V - _S01BRect.y) / _S01BRect.z + 0.5) / max(_S01BSize.y, 1.0),
                                    ((U - _S01BRect.x) / _S01BRect.z + 0.5) / max(_S01BSize.x, 1.0));
                float inTex = (tuv.x > 0.0 && tuv.x < 1.0 && tuv.y > 0.0 && tuv.y < 1.0) ? 1.0 : 0.0;
                float4 D = _DesignBicubic > 0.5 ? DesignBicubic(tuv, float2(_S01BSize.y, _S01BSize.x)) : tex2D(_S01BDesign, tuv);
                float fDw = max(fwidth(D.r), 1e-5), fDm = max(fwidth(D.g), 1e-5), fDd = max(fwidth(D.b), 1e-5), fDt = max(fwidth(D.a), 1e-5);

                // ---- 前の模様の重み（F の始まり・前面の下・低い行）
                float zoneTop = saturate((F - _Zone.x) / 0.02 + 0.5);
                float zoneBot = saturate((_Zone.y - F) / max(_Zone.z, 1e-3));
                float zoneRow = saturate((hrow - _Zone.w) / 0.03);
                float zone = zoneTop * zoneBot * zoneRow * inTex;

                // ---- 白の時刻（設計27 と同じ約束）
                float zArr = Px(_DS27Tau - i.tw);
                if (i.fl.x > 0.999) zArr = 1e4;
                if (i.fl.y > 0.999) zArr = -1e4;
                if (_DS27WhiteEnabled < 0.5 || _DS27Enabled < 0.5) zArr = 1e4;
                float arrived = saturate(0.5 + zArr / aa);

                // ---- 背の白（F < 1）：行の相対の高さが境より上
                float wave = _BackWave.x * sin(6.2831853 * ca / max(_BackWave.y, 0.1));
                float zBack = Px(hrel - (BackB(c) + wave));
                float zClamp = min(Px(F + 0.25), Px(hrow - _MinRowH));
                float zBackW = min(min(zBack, zClamp), zArr) / aa;
                // ---- 前の白（頂の白）：テクスチャの R
                float zFrontW = min(min(D.r / fDw, Px(hrow - _MinRowH)), zArr) / aa;
                bool front = F >= _Zone.x;
                float zW = front ? zFrontW : zBackW;
                float whiteCov = saturate(0.5 + zW);
                // 前の模様の外（前面の下・低い行）では、白は背の規則のまま（前面の下は白にならない）
                whiteCov = front ? lerp(saturate(0.5 + min(zBack, zClamp) / aa) * (F < 1.2 ? 1.0 : 0.0), whiteCov, zone) : whiteCov;

                // ---- 前の模様（白でない所）
                float mizCov = saturate(0.5 + D.g / fDm / aa) * arrived;
                float darkCov = saturate(0.5 + D.b / fDd / aa);
                float dotCov = saturate(0.5 + D.a / fDt / aa) * saturate((0.08 / fDt - _DotMinPx) / max(_DotMinPx, 1e-3));   // 点の半径（約 0.08 m）が画面で _DotMinPx を切ると消す
                dotCov *= darkCov;
                // 白の時刻の前は舌の模様も胴のまま（藍濃）
                float3 front3 = lerp(_AiMid.rgb, _AiDark.rgb, darkCov);
                front3 = lerp(front3, _White.rgb, dotCov);
                front3 = lerp(front3, _Mizuiro.rgb, mizCov * (1.0 - darkCov));
                front3 = lerp(_AiDark.rgb, front3, arrived);

                // ---- 胴（背の藍と、前の模様の外）：藍濃に藍中の溝
                float lam = max(_GrooveLambda, 0.05);
                float wander = _GrooveWander.x * lam * sin(6.2831853 * s / max(_GrooveWander.y, 0.1) + 2.3 * sin(6.2831853 * ca / (lam * 7.3)));
                float q = c + wander / kc;
                float fq = max(fwidth(q), 1e-6);
                float ratio = lerp(_GrooveRatio.y, _GrooveRatio.x, saturate(hrel));
                float periodPx;
                float grooveCov = FlowLines(q, kc, lam, ratio, s, fq, periodPx);
                grooveCov *= saturate((periodPx - _GrooveFadePx.x) / max(_GrooveFadePx.y - _GrooveFadePx.x, 1e-3));
                float3 body = lerp(_AiDark.rgb, _AiMid.rgb, grooveCov);
                // ---- 背の胴（第 2 版）：白の下の藍も、前と同じ (u, w) の上に設計した線（テクスチャの B）と点（A）。
                //      前の版の背は仕上げ29 の行の c の溝（Q29 の「歪み」の元）のままだった。低い行・範囲の外は溝へ移る。
                float zoneB = (_BackDesign.x > 0.5 && !(F >= _Zone.x)) ? inTex * zoneRow * saturate((F - _BackDesign.y) / max(_BackDesign.z, 1e-3)) : 0.0;
                float3 back3 = lerp(_AiMid.rgb, _AiDark.rgb, darkCov);
                back3 = lerp(back3, _White.rgb, dotCov);
                body = lerp(body, back3, zoneB);

                // ---- ID
                if (_AF28IdMode > 0.5)
                {
                    int cls;
                    if (whiteCov >= 0.5) cls = 0;
                    else if (zone >= 0.5 && front)
                    {
                        if (arrived < 0.5) cls = 3;
                        else if (darkCov >= 0.5) cls = dotCov >= 0.5 ? 0 : 3;
                        else cls = mizCov >= 0.5 ? 1 : 2;
                    }
                    else if (zoneB >= 0.5) cls = darkCov >= 0.5 ? (dotCov >= 0.5 ? 0 : 3) : 2;
                    else cls = grooveCov >= 0.5 ? 2 : 3;
                    return float4(IdColour(cls), 1);
                }

                float3 col = lerp(body, front3, front ? zone : 0.0);
                // 白の中の陰（背の白だけ。t* の法線と固定の向き）
                float3 nrm = normalize(i.nst.xyz);
                float dsh = dot(nrm, normalize(_ShadeDir.xyz)) - _ShadeK;
                float shadeCov = front ? 0.0 : saturate(0.5 - (dsh / max(fwidth(dsh), 1e-6)) / aa);
                float3 wcol = lerp(_White.rgb, _Mizuiro.rgb, shadeCov);
                if (_WLines.x > 0.0)
                {
                    // 改善の回 1（項目 5）：白の上の淡い水色の流れの線（w の等値線＝巻きの向き。前の舌の線・背の線と同じ座標。視点によらない）
                    float Pl = max(_WLines.y, 0.1);
                    float fV = max(fwidth(V), 1e-6);
                    float dl = abs(frac(V / Pl + 0.5) - 0.5) * Pl / fV;
                    float hwl = 0.5 * _WLines.z * Pl / fV;
                    float wl = saturate(0.5 + (hwl - dl) / aa) * saturate(2.0 * hwl / aa - 0.3) * saturate((Pl / fV - _WLines.w) / max(_WLines.w, 1e-3));
                    wcol = lerp(wcol, _Mizuiro.rgb, _WLines.x * wl);
                }
                col = lerp(col, wcol, whiteCov);
                // ---- 線（画面の太さ。面が視線にほぼ平行な所では薄める）
                float3 Vv = normalize(_WorldSpaceCameraPos - i.wp);
                float nv = abs(dot(normalize(i.n), Vv));
                float graze = saturate((nv - _EdgeGrazing.x) / max(_EdgeGrazing.y - _EdgeGrazing.x, 1e-3));
                if (_EdgeLinePx > 0.0)
                {
                    float lineCov = saturate(0.5 * _EdgeLinePx + 0.5 - abs(zW)) * graze;
                    col = lerp(col, _LineCol.rgb, lineCov * (front ? zone : 1.0));
                }
                if (_MizLinePx > 0.0 && front)
                {
                    // 淡い水色の帯と藍（舌の先・藍中の線）の境
                    float edge = saturate(0.5 * _MizLinePx + 0.5 - abs(D.g / fDm)) * (1.0 - darkCov);
                    float edgeD = saturate(0.5 * _MizLinePx + 0.5 - abs(D.b / fDd)) * mizCov;
                    float lc = max(edge, edgeD) * graze * zone * (1.0 - whiteCov) * arrived;
                    col = lerp(col, _LineCol.rgb, lc);
                }
                return float4(col, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
