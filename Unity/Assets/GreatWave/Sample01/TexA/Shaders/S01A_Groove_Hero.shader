// 美術の見本01・見本 A（Q29：彫刻のような刻み）：主役波の視点によらない立体の材質。原画カメラの投影は使わない。
// 参照の彫刻（他者の展示作品。写真 G:\research\reality scan\北斋参考 は数値と作り方の参考だけ）の作り方に近づける：
//   ・深い藍の胴に、巻きの向き（背 → 頂 → 唇 → 管 → 前面）に沿って走る、等間隔でそろった溝。溝の中に淡い藍の線。
//   ・背の上と頂は白（彫刻のように滑らかな白）。背の下は藍。
//   ・頂・唇の前（爪の帯）は白にせず、藍中の地に水色の溝の線（立体の白い爪がその前で読めるように。課題の原因 3）。
// 溝は、美術の見本01 の面の座標 w（Build/Polish/sample01/param、s01_param.py。t* の面の上で巻きの向きにそろえ、世界の寸法でほぼ一様）の
// 等値線に置く。仕上げ29 のように行の c の上に置かない（課題の原因 1「歪」）。座標は格子の頂点に付いた値なので、形成の途中も頂点とともに動く。
// 頂点の属性（s01a_attr.py。PL29UkiyoeHero が UV3・UV4・UV5 に入れる）：
//   A = (F 流れの座標：背の足 0・頂 1・唇の先 2・管の奥 3・前面の下 4・端 5, hrel 行の相対の高さ, u 巻きの向きの弧長 m（頂 0）, w 頂に並ぶ向きの座標 m)
//   B = (gw |∇w|（溝の 3 次元の間隔は λ／gw）, hrow 行の頂の高さ／H0, X.x, X.y)
//   C = (t* の法線 xyz, X.z)  X は t* の頂に並ぶ向き（ワールド）
// 陰はどれも、ワールドに固定した向き（_LightDir・_ShadeDir）と t* の法線・X だけで決める（視点によらない）。画面の量は線の太さとアンチエイリアスだけ。
// ID 表示（大域の _AF28IdMode = 1）：白 赤、淡い水色 緑、藍中 青、藍濃 黄（評価器の色区の読み。設計27 の約束）。
// 診断（大域の _PL29Diag）：1 = 主役波の印と行・列（PL29 と同じ）、2 = F の帯、7 = w（紺）と u（赤）の等値線を F の帯の上に。
// 名前に Keypose を含むのは、ID の描画（KeepMaterial）がこの材質を残すため。
Shader "GreatWave/Sample01/S01A Groove Keypose"
{
    Properties
    {
        _White ("白・生成り", Color) = (0.97255, 0.95294, 0.87451, 1)
        _Mizuiro ("淡い水色", Color) = (0.77647, 0.84314, 0.79608, 1)
        _AiMid ("藍中", Color) = (0.17255, 0.41176, 0.57647, 1)
        _AiDark ("藍濃", Color) = (0.13725, 0.25098, 0.38039, 1)
        _AiDeep ("藍の陰（溝の陰の縁・胴の陰）", Color) = (0.08, 0.15, 0.25, 1)
        _GrooveLight ("溝の中の淡い藍の線", Color) = (0.45, 0.64, 0.76, 1)
        _LineCol ("藍の線（白の縁）", Color) = (0.2784314, 0.3137255, 0.372549, 1)
        _BackB ("背の白の境（x 行の相対の高さ、y うねりの振幅、z うねりの波長 m（w）、w 第 2 のうねりの振幅）", Vector) = (0.42, 0.035, 11, 0.015)
        _CapFront ("頂の白の前の縁（x 頂から前へ u m、y 縁の房の周期 m（w）、z 房の深さ m、w 1 で房）", Vector) = (1.6, 2.6, 0.9, 1)
        _ClawZone ("爪の帯（頂の白の前の縁〜唇の先）：x 終わりの F、y 地の藍中の割合（0 藍濃）、z 溝の中の線の水色の割合（0 溝の中の淡い藍、1 淡い水色）、w 1 で使う", Vector) = (2.0, 0.0, 0.6, 1)
        _MinRowH ("白を付ける行の頂の高さの下限（H0 の倍）", Float) = 0.08
        _GrooveLambda ("溝の 3 次元の周期 λ（m）", Float) = 1.0
        _GrooveWidth ("溝：x 帯の幅／周期、y 淡い藍の線の幅／周期、z 陰の縁の幅／周期、w 1 で描く", Vector) = (0.30, 0.07, 0.07, 1)
        _GrooveLod ("溝の本数を変える：x 間の溝が生まれ始める段の端数、y 全部、z 0 で変えない", Vector) = (0.22, 0.48, 1, 0)
        _GrooveFadePx ("溝を消す周期の画素（x 消える、y 全部）", Vector) = (3, 6, 0, 0)
        _GrooveBranch ("溝の生まれ方（0 間に細い溝が生まれる＝a5、1 隣の溝から Y 字に枝分かれする＝a6）", Float) = 0
        _AttrV2 ("属性の並び（0 = B (gw, hrow, X.x, X.y)・C.w X.z、1 = v2：B (gw, hrow, Ls 平らにした本数の段, X·L̂)＝a7）", Float) = 0
        _GrooveBack ("背の藍（F < 1）の溝の濃さ（0〜1）", Float) = 1
        _ClawBlend ("改善の回 1（美術監督の項目 6）爪の帯の境：x 移る幅の半分（F。0 で前の段差）、y 帯の中の溝の線の濃さ、z 帯の中の溝の陰の縁の濃さ、w 帯の中の溝の帯の濃さ", Vector) = (0, 1, 0, 1)
        _WGroove ("白の中の溝の名残（x 濃さ 0〜1、y 幅／周期）", Vector) = (0.0, 0.05, 0, 0)
        _LightDir ("溝の壁と胴の陰の光の向き（ワールド。光の来る向き）", Vector) = (-0.45, 0.75, -0.5, 0)
        _BodyShade ("胴の陰（x 法線と光の内積がこれ未満で藍の陰へ、y 陰の割合 0〜1、z 幅）", Vector) = (-0.35, 0.0, 0.05, 0)
        _ShadeDir ("白の陰（淡い水色）の向き（ワールド）", Vector) = (0, 1, -0.6, 0)
        _ShadeK ("白の陰の閾値（法線との内積がこれ未満で淡い水色）", Float) = -0.35
        _EdgeLinePx ("白と藍の境の線（画素。0 で描かない）", Float) = 1.5
        _EdgeGrazing ("線を薄める面の傾き（x 消える |n·v|、y 全部）", Vector) = (0.06, 0.2, 0, 0)
        _AAScale ("アンチエイリアスの幅（画素）", Float) = 1
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "S01AGroove"
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

            float4 _White, _Mizuiro, _AiMid, _AiDark, _AiDeep, _GrooveLight, _LineCol;
            float4 _BackB, _CapFront, _ClawZone, _GrooveWidth, _GrooveLod, _GrooveFadePx, _WGroove, _LightDir, _BodyShade, _ShadeDir, _EdgeGrazing, _ClawBlend;
            float _MinRowH, _GrooveLambda, _GrooveBack, _ShadeK, _EdgeLinePx, _AAScale, _GrooveBranch, _AttrV2;
            float _AF28IdMode;
            float _DS27WhiteEnabled;
            float _PL29Diag;

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

            float3 IdColour(int k)
            {
                return k == 0 ? float3(1, 0, 0) : (k == 1 ? float3(0, 1, 0) : (k == 2 ? float3(0, 0, 1) : float3(1, 1, 0)));
            }

            float3 FBand(float F)
            {
                float3 cs[6] = { float3(0.2, 0.6, 0.2), float3(0.9, 0.2, 0.2), float3(0.9, 0.8, 0.2), float3(0.2, 0.4, 0.95), float3(0.9, 0.5, 0.1), float3(0.5, 0.2, 0.6) };
                int i = clamp((int)floor(F), 0, 5);
                return cs[i] * (0.55 + 0.45 * step(0.5, frac(F * 4.0)));
            }

            // 溝：w の等値線に、3 次元の周期 lam で並べる。gw（|∇w|）で本数を 2 倍ずつ変え（彫刻の Y 字の枝分かれ）、
            // 近い溝の中心からの符号付きの距離 dW（w の単位）と、溝の帯の倍率 k（間の溝は生まれる途中で細い）と、周期の画素を返す。
            // lv：本数の段（log2(1/gw)、v2 では面の上で平らにした Ls。_GrooveLod.z = 0 なら 0）
            void NearestGroove(float w, float lv, float lam, float fw, out float dW, out float k, out float periodPx)
            {
                float L0 = round(lv);
                float fr = lv - L0;                                 // −0.5〜0.5
                float P0 = lam * exp2(-L0);                         // w の単位の基の周期
                float qn = w / P0;
                float g = frac(qn);
                float dB = (g < 0.5 ? g : g - 1.0) * P0;            // 基の溝（qn が整数）からの符号付きの距離
                float dM = (g - 0.5) * P0;                          // 間の溝（qn が整数 + 0.5）
                float km = smoothstep(_GrooveLod.x, _GrooveLod.y, fr);
                bool useM = abs(dM) < abs(dB) && km > 0.0;
                dW = useM ? dM : dB;
                k = useM ? km : 1.0;
                periodPx = (km > 0.5 ? 0.5 : 1.0) * P0 / max(fw, 1e-6);
            }

            // 1 本の溝の覆い（x 帯、y 淡い藍の線、z 陰の縁）。dPx は溝の中心からの画素（符号つき）、k は幅の倍率、side は光の側の符号。
            float3 OneGroove(float dPx, float k, float lam, float gw, float fw, float aa, float side)
            {
                float hb = 0.5 * _GrooveWidth.x * lam * gw * k / fw;
                float hl = 0.5 * _GrooveWidth.y * lam * gw * k / fw;
                float hs = _GrooveWidth.z * lam * gw * k / fw;
                float band = saturate(0.5 + (hb - abs(dPx)) / aa) * saturate(2.0 * hb / aa - 0.3);
                float lite = saturate(0.5 + (hl - abs(dPx)) / aa) * saturate(2.0 * hl / aa - 0.3);
                float dSide = dPx * side;
                float shad = saturate(0.5 + (0.5 * hs - abs(dSide + hb - 0.5 * hs)) / aa) * saturate(hs / aa - 0.3);
                return float3(band, lite, shad);
            }

            // a6：溝の本数を gw で 2 倍ずつ変える時、新しい溝を間に細く生ませず（a5 の点のような欠片の原因）、
            // 基の溝 n から Y 字に枝分かれさせる。子の溝は n + s（s = 0.5 km、w の周期 P0 の割合）にあり、km = 0 で親に重なり、
            // km = 1 で間（n + 0.5）に着く。幅は親と同じ（重なる所は親の中に隠れ、離れる所が Y 字の股になる）。
            float3 GrooveBranchCov(float w, float gw, float lv, float lam, float fw, float aa, float side, out float periodPx)
            {
                float L0 = round(lv);
                float fr = lv - L0;
                float P0 = lam * exp2(-L0);
                float qn = w / P0;
                float g = frac(qn);
                float km = smoothstep(_GrooveLod.x, _GrooveLod.y, fr);
                float s = 0.5 * km;
                float dB = (g < 0.5 ? g : g - 1.0) * P0;             // 基の溝 n または n + 1
                float dC = (g - s) * P0;                              // 子の溝 n + s
                float3 cB = OneGroove(dB / fw, 1.0, lam, gw, fw, aa, side);
                float3 cC = km > 0.0 ? OneGroove(dC / fw, 1.0, lam, gw, fw, aa, side) : float3(0, 0, 0);
                periodPx = lerp(1.0, 0.5, km) * P0 / max(fw, 1e-6);
                float band = max(cB.x, cC.x);
                float lite = max(cB.y, cC.y);
                float shad = max(cB.z * (1.0 - cC.x), cC.z * (1.0 - cB.x));   // 重なる所で、片方の陰の縁が他方の帯の中に出ないように
                return float3(band, lite, shad);
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float F = i.a.x, hrel = i.a.y, u = i.a.z, w = i.a.w;
                float gw = max(i.b.x, 0.05), hrow = i.b.y;
                float3 X = normalize(float3(i.b.z, i.b.w, i.nst.w) + 1e-6);   // v1 だけ（v2 では B.z = Ls、B.w = X·L̂）
                float lvRaw = log2(1.0 / max(gw, 1e-3));
                float lvG = (_GrooveLod.z > 0.5) ? (_AttrV2 > 0.5 ? i.b.z : lvRaw) : 0.0;
                float3 nst = normalize(i.nst.xyz + 1e-6);

                if (_PL29Diag > 0.5 && _PL29Diag < 1.5)
                {
                    uint col = (uint)(i.rc.y + 0.5);
                    return float4(i.rc.x / 255.0, (col & 255u) / 255.0, (col >> 8) / 255.0, 128.0 / 255.0);
                }
                if (_PL29Diag > 1.5 && _PL29Diag < 2.5) return float4(FBand(F), 1);
                if (_PL29Diag > 6.5 && _PL29Diag < 7.5)
                {
                    float lw = saturate(1.2 - abs(frac(w + 0.5) - 0.5) / max(fwidth(w), 1e-6));
                    float lu = saturate(1.2 - abs(frac(u / 2.0 + 0.5) - 0.5) / max(fwidth(u / 2.0), 1e-6));
                    float3 cc = lerp(FBand(F), float3(0.1, 0.12, 0.3), lw);
                    return float4(lerp(cc, float3(0.85, 0.1, 0.1), lu), 1);
                }
                float aa = max(_AAScale, 1e-3);
                float fw = max(fwidth(w), 1e-6);

                // ---- 白の範囲（画素の符号付き距離。正が白）
                // 背（u < 0）：行の相対の高さが境より上。境は w に沿ってゆるくうねる（彫刻の背の白の縁）
                float bb = _BackB.x + _BackB.y * sin(6.2831853 * w / max(_BackB.z, 0.1)) + _BackB.w * sin(6.2831853 * w / max(0.43 * _BackB.z, 0.1) + 1.7);
                float zBack = Px(hrel - bb);
                // 頂の前（u ≥ 0）：頂から u が _CapFront.x m まで。縁は w の周期 _CapFront.y の丸い房（爪の根の並び）
                float capEdge = _CapFront.x;
                if (_CapFront.w > 0.5)
                {
                    float P = max(_CapFront.y, 0.1);
                    float ws = w + 0.22 * P * sin(6.2831853 * w / (3.7 * P)) + 0.12 * P * sin(6.2831853 * w / (1.9 * P) + 1.1);   // 房の幅の不揃い
                    float fi = floor(ws / P);
                    float s = ws / P - fi;
                    float x = (s - 0.5) / 0.42;
                    float prof = sqrt(saturate(1.0 - x * x));
                    float len = _CapFront.z * (0.65 + 0.7 * Hash1(fi * 1.37 + 2.9));
                    capEdge += len * prof - 0.35 * _CapFront.z;
                }
                float zCap = Px(capEdge - u);
                float zZone = u < 0.0 ? zBack : zCap;
                zZone = min(zZone, Px(F + 0.25));                 // 背の足より外（余白）は白にしない
                zZone = min(zZone, Px(hrow - _MinRowH));          // 低すぎる行は白にしない
                // 白の時刻（設計27 と同じ約束）
                float zArr = Px(_DS27Tau - i.tw);
                if (i.fl.x > 0.999) zArr = 1e4;
                if (i.fl.y > 0.999) zArr = -1e4;
                if (_DS27WhiteEnabled < 0.5 || _DS27Enabled < 0.5) zArr = 1e4;
                float zW = min(zZone, zArr) / aa;
                float whiteCov = saturate(0.5 + zW);

                // ---- 爪の帯（頂の白の前の縁〜唇の先 F = _ClawZone.x）
                float zClaw = (_ClawZone.w > 0.5 && u >= 0.0) ? Px(_ClawZone.x - F) / aa : -1e4;
                float clawCov = saturate(0.5 + zClaw);
                // 改善の回 1（項目 6）：色の移り（clawS）は F の ±_ClawBlend.x の広い帯でなめらかに（前は 1 画素の段差＝座席の斜めの継ぎ目）
                float clawS = clawCov;
                if (_ClawBlend.x > 0.0) clawS = (_ClawZone.w > 0.5 && u >= 0.0) ? smoothstep(-_ClawBlend.x, _ClawBlend.x, _ClawZone.x - F) : 0.0;

                // ---- 溝（w の等値線。画面の微分は枝の外で取る）
                float lam = max(_GrooveLambda, 0.05);
                float dW, kG, periodPx;
                NearestGroove(w, lvG, lam, fw, dW, kG, periodPx);
                float fade = saturate((periodPx - _GrooveFadePx.x) / max(_GrooveFadePx.y - _GrooveFadePx.x, 1e-3));
                float dPx = dW / fw;                               // 溝の中心からの画素（符号つき、+X の向きが正）
                float hb = 0.5 * _GrooveWidth.x * lam * gw * kG / fw; // 帯の半幅（画素）
                float hl = 0.5 * _GrooveWidth.y * lam * gw * kG / fw;
                float hs = _GrooveWidth.z * lam * gw * kG / fw;
                float band = saturate(0.5 + (hb - abs(dPx)) / aa) * saturate(2.0 * hb / aa - 0.3);
                float lite = saturate(0.5 + (hl - abs(dPx)) / aa) * saturate(2.0 * hl / aa - 0.3);
                // 陰の縁：溝の壁のうち光に背を向ける側（X と光の向きの内積の符号。t* の X、ワールドで固定の光 → 視点によらない）
                float3 L = normalize(_LightDir.xyz);
                float side = (_AttrV2 > 0.5 ? i.b.w : dot(X, L)) >= 0.0 ? 1.0 : -1.0;
                float dSide = dPx * side;                          // 光の来る側が正
                float shad = saturate(0.5 + (0.5 * hs - abs(dSide + hb - 0.5 * hs)) / aa) * saturate(hs / aa - 0.3);
                if (_GrooveBranch > 0.5)
                {
                    float pPx;
                    float3 cv = GrooveBranchCov(w, gw, lvG, lam, fw, aa, side, pPx);
                    band = cv.x; lite = cv.y; shad = cv.z;
                    fade = saturate((pPx - _GrooveFadePx.x) / max(_GrooveFadePx.y - _GrooveFadePx.x, 1e-3));
                }
                band *= fade; lite *= fade; shad *= fade;
                if (_GrooveWidth.w < 0.5) { band = 0; lite = 0; shad = 0; }
                float backK = (u < 0.0) ? saturate(_GrooveBack) : 1.0;

                // ---- 胴の陰（t* の法線と固定の光。視点によらない）
                float tone = dot(nst, L) - _BodyShade.x;
                float bodyShade = saturate(0.5 - tone / max(_BodyShade.z, 1e-3)) * _BodyShade.y;

                // ---- 色
                float3 base = lerp(_AiDark.rgb, _AiDeep.rgb, bodyShade);
                float3 bandCol = _AiMid.rgb;
                float3 liteCol = _GrooveLight.rgb;
                float3 clawBase = lerp(_AiDark.rgb, _AiMid.rgb, _ClawZone.y);
                float3 clawBand = _AiMid.rgb;
                float3 clawLite = lerp(_GrooveLight.rgb, _Mizuiro.rgb, _ClawZone.z);
                base = lerp(base, clawBase, clawS);
                bandCol = lerp(bandCol, clawBand, clawS);
                liteCol = lerp(liteCol, clawLite, clawS);
                // 帯の中の溝の濃さ（項目 6：唇の上の溝が爪の輪に平行な「レール」に見えないよう弱める）。既定 (0,1,0,1) は前と同じ
                float kBand = lerp(1.0, _ClawBlend.w, clawS), kLite = lerp(1.0, _ClawBlend.y, clawS), kShad = 1.0 - clawS * (1.0 - _ClawBlend.z);
                float3 body = base;
                body = lerp(body, bandCol, band * backK * kBand);
                body = lerp(body, liteCol, lite * backK * kLite);
                body = lerp(body, _AiDeep.rgb, shad * backK * kShad);
                // 白：法線の段の淡い水色（背の白の陰）と、白の中の溝の名残
                float dsh = dot(nst, normalize(_ShadeDir.xyz)) - _ShadeK;
                float mizCov = saturate(0.5 - Px(dsh) / aa);
                float wg = _WGroove.x * saturate(0.5 + (0.5 * _WGroove.y * lam * gw / fw - abs(dPx)) / aa) * fade;
                float3 wcol = lerp(_White.rgb, _Mizuiro.rgb, max(mizCov, wg));
                float3 col = lerp(body, wcol, whiteCov);

                if (_AF28IdMode > 0.5)
                {
                    int cls = whiteCov >= 0.5 ? (max(mizCov, wg) >= 0.5 ? 1 : 0)
                            : ((band * backK >= 0.5 || clawCov >= 0.5) ? 2 : 3);
                    return float4(IdColour(cls), 1);
                }
                if (_EdgeLinePx > 0.0)
                {
                    float lineCov = saturate(0.5 * _EdgeLinePx + 0.5 - abs(zW));
                    float3 V = normalize(_WorldSpaceCameraPos - i.wp);
                    float nv = abs(dot(normalize(i.n), V));
                    lineCov *= saturate((nv - _EdgeGrazing.x) / max(_EdgeGrazing.y - _EdgeGrazing.x, 1e-3));
                    col = lerp(col, _LineCol.rgb, lineCov);
                }
                return float4(col, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
