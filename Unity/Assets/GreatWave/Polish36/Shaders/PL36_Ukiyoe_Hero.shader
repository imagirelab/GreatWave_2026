// 仕上げ29（Q28）：主役波の視点によらない立体の浮世絵の材質。原画カメラからの投影の焼き込み（設計29修正01 の色区テクスチャと UV3）を使わない。
// 色・溝（縞）・白の塊・境の線は、面の座標と立体の量だけで決める：
//   ・面の座標（頂点ごと、K*′ の格子の材料の点に付いた値。pl29_hero_attr.py --param arc が作り、PL29UkiyoeHero が UV3・UV4・UV5 に入れる）
//       A = (F 流れの座標：背の足 0 → 頂 1 → 唇の先 2 → 管の奥 3 → 前面の下 4 → 端 5, hrel t* の高さ／行の頂の高さ,
//            kc 行の間隔の 3 次元の倍率（c の 1 m が面の上で何 m か。t* の面で測る）, hrow 行の頂の高さ／H0)
//       B = (s 行ごとに列に沿って測った t* の面の弧長 m, c 行の座標 m（白の範囲の折れ線に使う）, dtip 唇の先からの弧長 m, dtop 頂からの弧長 m)
//       C = (t* の法線 xyz, ca 列ごとに行を渡って測った t* の面の弧長 m（舌・点・泡の並びに使う）)
//   ・形成の途中の位置と法線（DS27 keypose。物体の空間＝波の枠。枠は平行移動だけなので法線はワールドのまま）
//   ・白の時刻 T_white（DS27 パッケージの _DS27White）
// 版の重ね（参照の彫刻と摺りの工程。Build/Polish/29/study の数値）：
//   1) 藍の胴（藍濃）に、流れ（行）に沿って走る藍中の溝。溝は行の c の上に並べ、3 次元の間隔がいつも約 λ になるように、
//      行の間隔の倍率 kc で本数を 2 倍ずつ変える（kc が 2 倍に近づくと、間に新しい溝が細く生まれて太る＝彫刻の Y 字の枝分かれ）。
//      幅／周期は上で細く下で太く、うねり・切れ（先の細る筆の形）つき。周期が画面で数画素より細かくなると薄めて消す（モアレよけ）。胴の中に紙の白い点。
//   2) 白：背は行の相対の高さ hrel が境 b(c)（うねりつき）より上、頂から唇の先の側へは F が 1 から F_end(c) まで。
//      前の白の縁は 2 段の舌で割る：爪の指の房（_Finger。ca に周期 _Finger.x m で並ぶ、先が丸く伸びるほど横へ曲がる大きな舌。間は藍の切れ込み）と、
//      その縁の泡の小さな舌（_Fringe）。舌は画面で 1〜2 画素より細くなる所では消す（細い藍の切れ込みが梯子に見えるのを避ける）。
//      白の時刻 T_white が来る前は胴のまま（形成の途中で白が頂から広がる）。
//   3) 白の中の淡い水色：① 房の陰（各房の縁の帯の片側）、② 泡の粒（白の縁の近くほど多い、面の弧長 (s, ca) の上の不規則な粒）、
//      ③ 法線と物体の空間で固定した向き _ShadeDir の内積が _ShadeK 未満の所（視点によらない陰の段。t* の法線。既定は背の白だけ：前の白で使うと
//      大きな平らな淡い水色の板になった（作る部の評審））、④ 白の中の淡い水色の流れの線。
//   4) 白の縁の外の藍の上に、泡の白い点（縁の近くほど多い）。
//   5) 白と藍の境に藍の線（画素の幅。位置は面の座標で決まり、視点では動かない）。線は、面が視線にほぼ平行な所（折り返しの細い帯）では薄める。
// ID 表示（大域の _AF28IdMode = 1）：白 赤、淡い水色 緑、藍中 青、藍濃 黄（設計27 の NPR と同じ約束。評価器の色区の読み）。
// 診断（大域の _PL29Diag）：1 = 主役波の印（アルファ 128/255）と行・列（R = 行/255、G = 列の下位 8 bit、B = 列の上位）、2 = 流れの座標 F の帯の色、
//   3〜5 = 面の座標の値（F・hrel、c・法線の上向き、s・陰の向き。frag の中の説明）、6 = ca と kc。数値の合わせと点検のためだけに使う。
// 名前に Keypose を含むのは、設計40・仕上げ28・29 の ID の描画（KeepMaterial）がこの材質を残して色区の ID を描くため。
// SPI の立体視マクロは設計27 と同じ形（HMD 実機は未検証）。
// ── 仕上げ36（設計36 限定色）で足したもの（PL29 Ukiyoe Keypose を写した新しい材質。PL29 のファイルは変えない）──
//   6) 爪の帯（Q28・121）：前の白（F 1 → F_end(c)）を、頂の白の帯（F < F_cz(c)、縁に小さな房）と、その先の爪の帯（F_cz(c) → 前の白の縁）に分ける。
//      爪の帯の地は藍の胴（藍濃に藍中の溝・白い点）で、頂の白の帯の側に淡い水色の輪（幅 _CzRingW(c)、藍の舌が輪へ食い込む房 _CzRing）を置く。
//      3D の白い爪はこの帯から立つので、藍か淡い水色の地の上の白い指として読める。帯は F・c・ca だけで決め、原画カメラは使わない。
//      背（F < 1）と頂の白の帯は白のまま（参照の彫刻の白い背と頂）。帯は白の時刻 T_white が来てから現れる（それまでは胴のまま）。
//   7) 谷の底の段（Q16 の谷・仕上げ30 の限界 1）：前面の下（F ≥ _Valley.z）で、今の高さ（形成の途中の位置の y。海の材質と同じく海面 0）が
//      −_Valley.x m より低い所を、藍中の地に藍濃の溝（谷の底へ太る）にし、境に藍の線を引く。海の谷の縁の帯（PL30。藍中の地に藍濃の溝）と同じ版の順。
//      地の藍中は胴の藍中の溝を同じ中心のまま太らせたもので、溝は段で途切れず、太さだけが段で変わる。
Shader "GreatWave/Polish36/PL36 Ukiyoe Keypose"
{
    Properties
    {
        _White ("白・生成り", Color) = (0.97255, 0.95294, 0.87451, 1)
        _Mizuiro ("淡い水色", Color) = (0.77647, 0.84314, 0.79608, 1)
        _AiMid ("藍中", Color) = (0.17255, 0.41176, 0.57647, 1)
        _AiDark ("藍濃", Color) = (0.13725, 0.25098, 0.38039, 1)
        _LineCol ("藍の線", Color) = (0.2784314, 0.3137255, 0.372549, 1)
        _BackB ("背の白の境 b（行の相対の高さ。c の節の左・中・右・右端）", Vector) = (0.41, 0.41, 0.24, 0.10)
        _BackC ("背の白の境の c の節（m。左・中・右・右端）", Vector) = (-30, -8, 6, 14)
        _BackWave ("背の境のうねり（振幅：行の高さの倍、波長 m（ca））", Vector) = (0.02, 7, 0, 0)
        _FrontC0 ("前の白の終わり F_end(c) の c の節 1〜4（m）", Vector) = (-11.5, -10, -6.5, -5)
        _FrontC1 ("前の白の終わり F_end(c) の c の節 5〜8（m）", Vector) = (5, 7, 30, 31)
        _FrontE0 ("前の白の終わり F_end の値 1〜4（流れの座標 F）", Vector) = (2.35, 1.42, 1.42, 2.25)
        _FrontE1 ("前の白の終わり F_end の値 5〜8", Vector) = (2.25, 1.95, 1.95, 1.95)
        _TipFoam ("唇の先のまわりの白（弧長 m）", Float) = 0
        _Finger ("爪の指の房：x 周期 m（ca）、y 長さ（F）、z 房の間の切れ込み（F）、w 曲がり（m／F²）", Vector) = (2.8, 0.30, 0.22, 4)
        _Finger2 ("爪の指の房：x 幅（周期の倍）、y 種、z 長さの揺れ（0〜1）、w 0 で房なし", Vector) = (0.78, 3.1, 0.5, 1)
        _Finger3 ("爪の指の房の不揃い：x 幅の揺れ（0〜1）、y 中心のずれ（周期の倍）", Vector) = (0.4, 0.25, 0, 0)
        _Fringe ("縁の泡の小さな舌：x 周期 m（ca）、y 長さ（F）、z 切れ込み（F）、w 0 で描かない", Vector) = (0.7, 0.06, 0.05, 1)
        _LobeShade ("房の陰（淡い水色）：x 縁からの帯の幅（F）、y 房の中の陰の側の割合（0〜1）、z 帯の上の端の揺れ（F）、w 0 で描かない", Vector) = (0.16, 0.45, 0.05, 1)
        _FoamCells ("泡の粒（白の中の淡い水色）：x 格子 m、y 半径（格子の倍）、z 縁での割合、w 縁から内へ届く幅（F）", Vector) = (1.3, 0.34, 0.65, 0.45)
        _FoamCells2 ("泡の粒：x 背（F < 1）の割合、y 頂の側で消す hrel、z 揺らぎの強さ（格子の倍）、w 0 で描かない", Vector) = (0.04, 0.97, 0.3, 1)
        _FoamDots ("縁の外の泡の白い点：x 格子 m、y 半径 m、z 縁での割合、w 縁から外へ届く幅（F）", Vector) = (0.55, 0.11, 0.55, 0.35)
        _MinRowH ("白を付ける行の頂の高さの下限（H0 の倍）", Float) = 0.08
        _ShadeDir ("淡い水色の段の向き（ワールド＝波の枠。正規化前）", Vector) = (0, 1, -0.6, 0)
        _ShadeK ("淡い水色の段の閾値（法線との内積がこれ未満）", Float) = -0.1
        _ShadeStatic ("陰に使う法線（0 形成の途中の法線、1 t* の法線＝面の座標の C）", Float) = 1
        _ShadeFront ("法線の段を前の白（F ≥ 1）にも使う（0 使わない＝前の白の淡い水色は房の陰と泡の粒だけ、1 使う）", Float) = 0
        _GrooveLambda ("溝の 3 次元の周期 λ（m）", Float) = 0.95
        _GrooveRatio ("溝の幅／周期（x 上の側 hrel=1、y 下の側 hrel=0）", Vector) = (0.16, 0.30, 0, 0)
        _GrooveWander ("溝のうねり（x 振幅：周期の倍、y 波長 m）", Vector) = (0.08, 9, 0, 0)
        _GrooveDash ("溝の切れ（x 長さ m、y 埋める割合、z 1 で切る）", Vector) = (8.0, 0.9, 1, 0)
        _GrooveFadePx ("溝を消す周期の画素（x 消える、y 全部）", Vector) = (3, 6, 0, 0)
        _WhiteLines ("白の中の淡い水色の流れの線（x 溝の何本ごと、y 幅／周期、z 頂の側で消す hrel、w 0 で描かない）", Vector) = (3, 0.07, 0.92, 1)
        _Dots ("胴の白い点（x 格子 m、y 半径 m、z 割合、w hrel の下限）", Vector) = (0.67, 0.07, 0.30, 0.25)
        _EdgeLinePx ("白と藍の境の線（画素。0 で描かない）", Float) = 1.5
        _EdgeGrazing ("線を薄める面の傾き（x 消える |n·v|、y 全部）", Vector) = (0.05, 0.16, 0, 0)
        _FeaturePx ("舌・切れ込みを消す画素（x 消える、y 全部）", Vector) = (1.0, 2.5, 0, 0)
        _AAScale ("アンチエイリアスの幅（画素）", Float) = 1
        _CzC0 ("仕上げ36 爪の帯の始まり F_cz(c) の c の節 1〜4（m）", Vector) = (-14, -10, -6, -2)
        _CzC1 ("爪の帯の始まり F_cz(c) の c の節 5〜8（m）", Vector) = (2, 6, 10, 14)
        _CzE0 ("爪の帯の始まり F_cz の値 1〜4（F。9 以上で帯なし＝仕上げ29 と同じ）", Vector) = (9, 9, 9, 9)
        _CzE1 ("爪の帯の始まり F_cz の値 5〜8", Vector) = (9, 9, 9, 9)
        _CzRingW0 ("淡い水色の輪の幅（F）の c の節 1〜4（節は _CzC0。0 で輪なし、9 で帯全部）", Vector) = (0.15, 0.15, 0.15, 0.15)
        _CzRingW1 ("淡い水色の輪の幅 節 5〜8", Vector) = (0.15, 0.15, 0.15, 0.15)
        _CzScallop ("頂の白の帯の縁の房：x 周期 m（ca）、y 深さ（F）、z 種、w 0 で描かない", Vector) = (2.2, 0.06, 7.3, 1)
        _CzRing ("輪へ食い込む藍の舌：x 周期 m（ca）、y 舌の幅（周期の倍）、z 舌の高さ（F。輪は細くても輪の幅の 1/4 を残す）、w 種", Vector) = (3.1, 0.6, 0.85, 2.7)
        _CzLines ("輪の中の流れの線：x 溝の何本ごと、y 幅／周期、z 色（0 藍中、1 白）、w 0 で描かない", Vector) = (1, 0.12, 0, 1)
        _CzLinePx ("輪と藍の境の線（画素。0 で描かない）", Float) = 1.0
        _Valley ("谷の底の段：x 今の高さが −x m より低い所、y 溝が太りきる深さの幅 m、z F の下限、w 0 で描かない", Vector) = (0.8, 3.0, 3.2, 0)
        _ValleyRatio ("谷の底の藍濃の溝の幅／周期（x 段の境、y 太りきった所。藍中の溝はその残り）", Vector) = (0.25, 0.45, 0, 0)
        _ValleyLinePx ("谷の底の段の境の線（画素。0 で描かない）", Float) = 1.5
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "PL29Ukiyoe"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile _ DS27_POS_LO
            #include "../../Design27/Shaders/DS27Keypose.cginc"

            float4 _White, _Mizuiro, _AiMid, _AiDark, _LineCol;
            float4 _Finger, _Finger2, _Finger3, _Fringe, _LobeShade, _FoamCells, _FoamCells2, _FoamDots, _WhiteLines, _EdgeGrazing, _FeaturePx;
            float4 _BackB, _BackC, _BackWave, _FrontC0, _FrontC1, _FrontE0, _FrontE1, _ShadeDir, _GrooveRatio, _GrooveWander, _GrooveDash, _GrooveFadePx, _Dots;
            float _ShadeStatic, _ShadeFront;
            float _TipFoam, _MinRowH, _ShadeK, _GrooveLambda, _EdgeLinePx, _AAScale;
            float4 _CzC0, _CzC1, _CzE0, _CzE1, _CzRingW0, _CzRingW1, _CzScallop, _CzRing, _CzLines, _Valley, _ValleyRatio;
            float _CzLinePx, _ValleyLinePx;
            float _AF28IdMode;          // 大域。1 で色区の ID
            float _DS27WhiteEnabled;    // 大域。0 で白の時刻を見ない（終態）
            float _PL29Diag;            // 大域。1 主役波の印と行・列、2 F の帯

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

            // 0 の等値線からの符号付きの距離（画素）
            float Px(float v) { return v / max(fwidth(v), 1e-6); }

            float Hash1(float x) { return frac(sin(x * 127.1 + 311.7) * 43758.5453); }
            float3 Hash3(float2 p)
            {
                float3 q = float3(dot(p, float2(127.1, 311.7)), dot(p, float2(269.5, 183.3)), dot(p, float2(419.2, 371.9)));
                return frac(sin(q) * 43758.5453);
            }

            // 背の白の境 b(c)：4 つの節の折れ線（端は延ばさず止める）
            float BackB(float c)
            {
                float4 k = _BackC, b = _BackB;
                if (c <= k.x) return b.x;
                if (c <= k.y) return lerp(b.x, b.y, (c - k.x) / max(k.y - k.x, 1e-3));
                if (c <= k.z) return lerp(b.y, b.z, (c - k.y) / max(k.z - k.y, 1e-3));
                if (c <= k.w) return lerp(b.z, b.w, (c - k.z) / max(k.w - k.z, 1e-3));
                return b.w;
            }

            // 前の白の終わり F_end(c)：8 つの節の折れ線（端の外は端の値）
            float FrontEnd(float c)
            {
                float kc[8] = { _FrontC0.x, _FrontC0.y, _FrontC0.z, _FrontC0.w, _FrontC1.x, _FrontC1.y, _FrontC1.z, _FrontC1.w };
                float ke[8] = { _FrontE0.x, _FrontE0.y, _FrontE0.z, _FrontE0.w, _FrontE1.x, _FrontE1.y, _FrontE1.z, _FrontE1.w };
                float r = ke[0];
                [unroll] for (int j = 0; j < 7; j++)
                    if (c > kc[j]) r = lerp(ke[j], ke[j + 1], smoothstep(0.0, 1.0, saturate((c - kc[j]) / max(kc[j + 1] - kc[j], 1e-3))));
                return r;
            }

            // 仕上げ36：8 つの節の折れ線（節は _CzC0・_CzC1。端の外は端の値。FrontEnd と同じなめらかなつなぎ）
            float Poly8(float c, float4 e0, float4 e1)
            {
                float kc[8] = { _CzC0.x, _CzC0.y, _CzC0.z, _CzC0.w, _CzC1.x, _CzC1.y, _CzC1.z, _CzC1.w };
                float ke[8] = { e0.x, e0.y, e0.z, e0.w, e1.x, e1.y, e1.z, e1.w };
                float r = ke[0];
                [unroll] for (int j = 0; j < 7; j++)
                    if (c > kc[j]) r = lerp(ke[j], ke[j + 1], smoothstep(0.0, 1.0, saturate((c - kc[j]) / max(kc[j + 1] - kc[j], 1e-3))));
                return r;
            }

            float3 IdColour(int k)
            {
                return k == 0 ? float3(1, 0, 0) : (k == 1 ? float3(0, 1, 0) : (k == 2 ? float3(0, 0, 1) : float3(1, 1, 0)));
            }

            float3 FBand(float F)
            {
                float3 cs[6] = { float3(0.2, 0.6, 0.2), float3(0.9, 0.2, 0.2), float3(0.9, 0.8, 0.2), float3(0.2, 0.4, 0.95), float3(0.9, 0.5, 0.1), float3(0.5, 0.2, 0.6) };
                int i = clamp((int)floor(F), 0, 5);
                float3 c = cs[i];
                return c * (0.55 + 0.45 * step(0.5, frac(F * 4.0)));
            }

            // 舌の形：周期 P の中の位置 u、幅（周期の倍）w。房の中心で 1、外で 0 の丸い形
            float LobeProfile(float u, float w)
            {
                float x = (u - 0.5) / max(0.5 * saturate(w), 1e-3);
                return sqrt(saturate(1.0 - x * x));
            }

            // 流れに沿う線（溝）の覆い：行の c の上に、3 次元の周期 lam3 で並べる。kc（c の 1 m が面の上で何 m か）で本数を 2 倍ずつ変え、
            // 間の新しい溝は kc の端数で細く生まれて太る。id は溝の c の位置（段が変わっても同じ溝は同じ id）。
            float FlowLines(float q, float kc, float lam3, float ratio, float sa, float fq, out float periodPx)
            {
                float lv = log2(max(kc, 1e-3));
                float L0 = floor(lv);
                float fr = lv - L0;
                float P0 = lam3 * exp2(-L0);                    // c の単位の基の周期（3 次元では lam3·2^fr）
                float qn = q / P0;
                float g = frac(qn);
                float dBase = min(g, 1.0 - g) * P0;             // 基の溝の中心（qn が整数）からの c の距離
                float dMid = abs(g - 0.5) * P0;                 // 間の新しい溝（qn が整数 + 0.5）
                float idB = round(qn) * P0, idM = (floor(qn) + 0.5) * P0;
                float tB = 1.0, tM = 1.0;
                if (_GrooveDash.z > 0.5)
                {
                    // 切れ：基の溝と間の新しい溝のうち、近い方だけを計算する（遠い方は覆いに効かない）
                    float duty = saturate(_GrooveDash.y);
                    bool nearBase = dBase <= dMid;
                    float uu = frac(sa / max(_GrooveDash.x, 0.1) + Hash1(round((nearBase ? idB : idM) * 16.0)));
                    float tt = uu < duty ? pow(saturate(sin(3.14159265 * uu / max(duty, 1e-3))), 0.35) : 0.0;
                    tB = nearBase ? tt : 1.0;
                    tM = nearBase ? 1.0 : tt;
                }
                float hw3 = 0.5 * ratio * lam3;                  // 3 次元の半幅（m）
                float hB = hw3 * tB / kc, hM = hw3 * tM * fr / kc; // c の単位の半幅
                float covB = saturate(0.5 + (hB - dBase) / fq) * saturate(2.0 * hB / fq - 0.5);
                float covM = saturate(0.5 + (hM - dMid) / fq) * saturate(2.0 * hM / fq - 0.5);
                periodPx = 0.5 * P0 / fq;
                return max(covB, covM);
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float F = i.a.x, hrel = i.a.y, kc = max(i.a.z, 0.05), hrow = i.a.w;
                float s = i.b.x, c = i.b.y, dtip = i.b.z;
                float ca = i.nst.w;

                if (_PL29Diag > 0.5 && _PL29Diag < 1.5)
                {
                    uint col = (uint)(i.rc.y + 0.5);
                    return float4(i.rc.x / 255.0, (col & 255u) / 255.0, (col >> 8) / 255.0, 128.0 / 255.0);
                }
                if (_PL29Diag > 1.5 && _PL29Diag < 2.5) return float4(FBand(F), 1);
                if (_PL29Diag > 2.5 && _PL29Diag < 6.5)
                {
                    // 3：(F+2)/12 を 16 bit（R 上位・G 下位）、B = hrel/1.2。4：(c+64)/96 を 16 bit、B = (法線の上向き+1)/2。
                    // 5：s/160 を 16 bit、B = (法線・陰の向き+1)/2。6：(ca+80)/140 を 16 bit、B = kc/4。アルファ 128/255 が主役波の印。
                    float3 nn = normalize(i.n);
                    float val = _PL29Diag < 3.5 ? (F + 2.0) / 12.0 : (_PL29Diag < 4.5 ? (c + 64.0) / 96.0 : (_PL29Diag < 5.5 ? s / 160.0 : (ca + 80.0) / 140.0));
                    float bb = _PL29Diag < 3.5 ? hrel / 1.2 : (_PL29Diag < 4.5 ? 0.5 * (nn.y + 1.0) : (_PL29Diag < 5.5 ? 0.5 * (dot(nn, normalize(_ShadeDir.xyz)) + 1.0) : kc / 4.0));
                    uint q16 = (uint)round(saturate(val) * 65535.0);
                    return float4((q16 >> 8) / 255.0, (q16 & 255u) / 255.0, round(saturate(bb) * 255.0) / 255.0, 128.0 / 255.0);
                }
                float aa = max(_AAScale, 1e-3);
                float fF = max(fwidth(F), 1e-6);

                // ---- 白の範囲（画素の符号付き距離。正が白）
                float wave = _BackWave.x * sin(6.2831853 * ca / max(_BackWave.y, 0.1));
                float zBack = Px(hrel - (BackB(c) + wave));          // 背：境より上
                // 頂から唇の先の側へ：F ≤ F_end(c) ＋ 房 ＋ 縁の泡の舌
                float fe = FrontEnd(c);
                float beyond = max(F - fe, 0.0);
                float cl = ca + _Finger.w * beyond * beyond;         // 伸びるほど横へ曲がる
                float fcl = max(fwidth(cl), 1e-6);
                float tongue = 0.0, uLobe = 0.5, prof = 1.0;
                if (_Finger2.w > 0.5)
                {
                    float P = max(_Finger.x, 0.1);
                    float fi = floor(cl / P);
                    uLobe = cl / P - fi;
                    float len = _Finger.y * (1.0 - _Finger2.z * Hash1(fi + _Finger2.y));
                    float wj = _Finger2.x * (1.0 - _Finger3.x * Hash1(fi * 2.13 + _Finger2.y + 4.7));
                    float uc = uLobe - _Finger3.y * (Hash1(fi * 3.71 + _Finger2.y + 1.3) - 0.5);
                    prof = LobeProfile(uc, wj);
                    uLobe = uc;
                    // 房の間の切れ込みの幅・深さ、房の長さが画面で 1〜2 画素を切るなら消す（細い藍の切れ込みの梯子よけ）
                    float gapPx = P * (1.0 - saturate(_Finger2.x) * 0.7) / fcl;
                    float depPx = min(_Finger.z, len) / fF;
                    float k = saturate((min(gapPx, depPx) - _FeaturePx.x) / max(_FeaturePx.y - _FeaturePx.x, 1e-3));
                    tongue = k * (len * prof - _Finger.z * (1.0 - prof));
                }
                if (_Fringe.w > 0.5)
                {
                    float Pf = max(_Fringe.x, 0.05);
                    float cf = cl + 0.37 * Pf;
                    float ff = floor(cf / Pf);
                    float uf = cf / Pf - ff;
                    float pf = LobeProfile(uf, 0.75);
                    float lf = _Fringe.y * (0.6 + 0.8 * Hash1(ff * 1.7 + 5.3));
                    float gapPx = 0.45 * Pf / fcl;
                    float depPx = min(_Fringe.z, lf) / fF;
                    float k = saturate((min(gapPx, depPx) - _FeaturePx.x) / max(_FeaturePx.y - _FeaturePx.x, 1e-3));
                    tongue += k * (lf * pf - _Fringe.z * (1.0 - pf));
                }
                float edgeF = fe + tongue;                            // 前の白の縁（F）。仕上げ36 では爪の帯の外の縁
                float fcs = max(fwidth(ca), 1e-6);

                // ---- 仕上げ36：爪の帯。頂の白の帯は F < czTop、爪の帯は czTop ≤ F < edgeF（どちらも面の座標だけ）
                float fcz = Poly8(c, _CzE0, _CzE1);
                bool czOn = fcz < 8.5;
                float scal = 0.0;
                if (czOn && _CzScallop.w > 0.5)
                {
                    // 頂の白の帯の縁の房（ca に周期 _CzScallop.x で並ぶ丸い舌＝爪の根元の塊）。画面で細すぎる所は消す
                    float Ps = max(_CzScallop.x, 0.1);
                    float fsi = floor(ca / Ps);
                    float us = ca / Ps - fsi;
                    float ws = 0.55 + 0.4 * Hash1(fsi * 1.37 + _CzScallop.z);
                    float ps = LobeProfile(us - 0.35 * (Hash1(fsi * 2.91 + _CzScallop.z) - 0.5), ws);
                    float ls = _CzScallop.y * (0.3 + 1.2 * Hash1(fsi * 4.03 + _CzScallop.z + 2.2));
                    float kS = saturate((Ps * 0.3 / fcs - _FeaturePx.x) / max(_FeaturePx.y - _FeaturePx.x, 1e-3)) *
                               saturate((ls / fF - _FeaturePx.x) / max(_FeaturePx.y - _FeaturePx.x, 1e-3));
                    scal = kS * (ls * ps - 0.35 * ls * (1.0 - ps));
                }
                float czTop = czOn ? min(fcz + scal, edgeF) : edgeF;  // 頂の白の帯の終わり（F）
                float zFront = Px(czTop - F);
                float zZone = F < 1.0 ? zBack : zFront;               // F = 1（頂）でつながる（どちらも白の側）
                float zTip = Px(_TipFoam - abs(dtip));                // 唇の先のまわり
                zZone = max(zZone, zTip);
                float zClamp = min(Px(F + 0.25), Px(hrow - _MinRowH)); // 背の足より外（余白）・低すぎる行は白にしない
                zZone = min(zZone, zClamp);
                // 白の時刻（設計27 と同じ約束。3 頂点とも届いていれば白、3 頂点とも t* まで届かなければ白にしない）
                float zArr = Px(_DS27Tau - i.tw);
                if (i.fl.x > 0.999) zArr = 1e4;
                if (i.fl.y > 0.999) zArr = -1e4;
                if (_DS27WhiteEnabled < 0.5 || _DS27Enabled < 0.5) zArr = 1e4;
                float zW = min(zZone, zArr) / aa;
                float whiteCov = saturate(0.5 + zW);
                bool front = F >= 1.0;
                float dIn = front ? (czTop - F) : 1e3;                // 前の白（頂の白の帯）の縁から内への F の距離（背では大きい）
                float arrived = saturate(0.5 + zArr / aa);

                // 爪の帯の被覆（白の時刻が来てから。それまでは胴のまま）
                float zCzOut = Px(edgeF - F);
                float zBelowTop = Px(F - czTop);                      // 頂の白の帯の縁から帯の側への画素（枝の外で取る）
                float zCz = min(min(zBelowTop, zCzOut), zClamp);
                float czCov = (czOn && front) ? saturate(0.5 + min(zCz, zArr) / aa) : 0.0;
                // 淡い水色の輪（頂の白の帯の側、幅 ringW(c)）。藍の舌（ca に周期 _CzRing.x）が輪へ食い込み、輪が舌を縁取る
                float ringW = czOn ? Poly8(c, _CzRingW0, _CzRingW1) : 0.0;
                float ringEnd = czTop;
                if (czOn && ringW > 0.0)
                {
                    float Pr = max(_CzRing.x, 0.1);
                    float fri = floor(ca / Pr);
                    float ur = ca / Pr - fri;
                    float wr = _CzRing.y * (0.8 + 0.4 * Hash1(fri * 1.91 + _CzRing.w));
                    float pr = LobeProfile(ur - 0.2 * (Hash1(fri * 3.3 + _CzRing.w) - 0.5), wr);
                    float hT = _CzRing.z * (0.7 + 0.6 * Hash1(fri * 5.17 + _CzRing.w + 1.1));
                    float kR = saturate((Pr * wr / fcs - _FeaturePx.x) / max(_FeaturePx.y - _FeaturePx.x, 1e-3));
                    ringEnd = czTop + max(ringW - kR * hT * pr, 0.25 * ringW);
                }
                float zRing = Px(ringEnd - F);
                float ringCov = ringW > 0.0 ? saturate(0.5 + zRing / aa) : 0.0;

                // 谷の底の段：前面の下で、今の高さ（海面 0）が −_Valley.x m より低い所
                float depth = -i.wp.y;
                float zValD = Px(depth - _Valley.x);
                float zValF = Px(F - _Valley.z);
                float valCov = _Valley.w > 0.5 ? saturate(0.5 + min(zValD, zValF) / aa) : 0.0;

                if (_PL29Diag > 11.5 && _PL29Diag < 12.5)
                    return float4(czCov * (1.0 - ringCov), czCov * ringCov, valCov, 128.0 / 255.0);   // 12：爪の帯（赤＝藍、緑＝輪）・谷の底（青）

                // 画面の微分は枝の外で取る（枝の中の fwidth は、隣の画素が別の枝を通ると定まらない）
                float fs = max(max(fwidth(s), fwidth(ca)), 1e-6);
                float3 nrm = normalize(lerp(i.n, i.nst.xyz, saturate(_ShadeStatic)));
                float dsh = dot(nrm, normalize(_ShadeDir.xyz)) - _ShadeK;
                float fDsh = max(fwidth(dsh), 1e-6);
                float fDIn = max(fwidth(dIn), 1e-6);
                float fU = max(fwidth(uLobe), 1e-6);
                float lam = max(_GrooveLambda, 0.05);
                float wander = _GrooveWander.x * lam * sin(6.2831853 * s / max(_GrooveWander.y, 0.1) + 2.3 * sin(6.2831853 * ca / (lam * 7.3)));
                float q = c + wander / kc;
                float fq = max(fwidth(q), 1e-6);

                // ---- 白の中の淡い水色（白の画素だけで計算する）
                float mizCov = 0.0;
                [branch] if (whiteCov > 0.0)
                {
                    // ③ 法線の段（t* の法線。視点によらない。既定は背の白だけ）
                    mizCov = saturate(0.5 - (dsh / fDsh) / aa) * (front ? saturate(_ShadeFront) : 1.0);
                    // ① 房の陰：縁から _LobeShade.x の帯のうち、房の陰の側（房の中の位置 uLobe が _LobeShade.y より小さい側）
                    if (_LobeShade.w > 0.5 && front && _Finger2.w > 0.5)
                    {
                        float band = _LobeShade.x + _LobeShade.z * (Hash1(floor(cl / max(_Finger.x, 0.1)) + 9.1) - 0.5);
                        float zb = (band - dIn) / fDIn;
                        float zs = (_LobeShade.y - uLobe) / fU;
                        mizCov = max(mizCov, saturate(0.5 + min(zb, zs) / aa) * saturate(0.5 + (dIn / fDIn) / aa));
                    }
                    // ② 泡の粒：(s, ca) の不規則な粒。縁の近くほど多い（前の白）、背では _FoamCells2.x
                    float prob = front ? _FoamCells.z * saturate(1.0 - dIn / max(_FoamCells.w, 1e-3)) : _FoamCells2.x;
                    prob *= saturate((_FoamCells2.y - hrel) / 0.05);
                    [branch] if (_FoamCells2.w > 0.5 && prob > 0.0)
                    {
                        float cell = max(_FoamCells.x, 0.1);
                        float2 p = float2(s, ca);
                        p += _FoamCells2.z * cell * float2(sin(p.y / (0.73 * cell)), sin(p.x / (0.91 * cell)));
                        float2 pc = p / cell;
                        float2 ci = floor(pc);
                        float best = 1e3; float pick = 1.0; float rsel = 1.0;
                        [unroll] for (int dy = -1; dy <= 1; dy++)
                            [unroll] for (int dx = -1; dx <= 1; dx++)
                            {
                                float2 cc = ci + float2(dx, dy);
                                float3 h = Hash3(cc + 17.0);
                                float2 ctr = cc + 0.15 + 0.7 * h.yz;
                                float d = length(pc - ctr) / (0.6 + 0.4 * h.x);
                                if (d < best) { best = d; pick = h.x; rsel = h.z; }
                            }
                        float rad = _FoamCells.y;
                        float on = Hash1(pick * 91.7 + rsel * 13.1) < prob ? 1.0 : 0.0;
                        float dpx = (rad - best) * cell / fs;               // 粒の縁からの画素
                        float lod = saturate((rad * cell / fs - 1.5) / 1.5);
                        mizCov = max(mizCov, on * lod * saturate(0.5 + dpx / aa));
                    }
                    // ④ 白の中の淡い水色の流れの線（溝と同じ並び。周期 λ×n。頂の近くでは消す）
                    if (_WhiteLines.w > 0.5)
                    {
                        float nl = max(_WhiteLines.x, 1.0);
                        float pw;
                        float wl = FlowLines(q, kc, lam * nl, _WhiteLines.y, s, fq, pw);
                        wl *= saturate((pw - _GrooveFadePx.x) / max(_GrooveFadePx.y - _GrooveFadePx.x, 1e-3)) * saturate((_WhiteLines.z - hrel) / 0.05);
                        mizCov = max(mizCov, wl);
                    }
                }

                // ---- 藍の胴（白でない画素だけで計算する。爪の帯の藍の舌もここ）
                float grooveCov = 0.0, dotCov = 0.0, gV = 0.0;
                [branch] if (whiteCov < 1.0)
                {
                    // 溝（流れ＝行に沿い、行の c の上に、3 次元の間隔 λ で並ぶ）
                    float ratio = lerp(_GrooveRatio.y, _GrooveRatio.x, saturate(hrel));
                    float periodPx;
                    grooveCov = FlowLines(q, kc, lam, ratio, s, fq, periodPx);
                    float fadeG = saturate((periodPx - _GrooveFadePx.x) / max(_GrooveFadePx.y - _GrooveFadePx.x, 1e-3));
                    grooveCov *= fadeG;
                    // 谷の底：同じ溝の中心のまま藍中の溝を太らせて地にし、溝の間の藍濃を細い溝として残す（段の上の藍中の溝が段で太り、藍濃の地が段で細る。
                    // 溝が途切れて反転して見えないように、中心は胴の溝と同じ）。藍濃の溝は谷の底へ太る
                    [branch] if (valCov > 0.0)
                    {
                        float vt = saturate((depth - _Valley.x) / max(_Valley.y, 0.1));
                        float pv;
                        gV = FlowLines(q, kc, lam, 1.0 - lerp(_ValleyRatio.x, _ValleyRatio.y, vt), s, fq, pv) * fadeG;   // 藍中の被覆
                    }
                    // 胴の白い点（紙の抜け。管の中 F > 1.5、hrel > _Dots.w だけ）
                    [branch] if (hrel > _Dots.w && F > 1.5)
                    {
                        float cell = max(_Dots.x, 0.05);
                        float2 cp = float2(s, ca) / cell;
                        float2 ci2 = floor(cp);
                        float3 h3 = Hash3(ci2);
                        float2 ctr = ci2 + 0.2 + 0.6 * h3.yz;
                        float dd = length((cp - ctr) * cell);
                        float dotOn = h3.x < _Dots.z ? 1.0 : 0.0;
                        dotCov = dotOn * saturate(0.5 + (_Dots.y - dd) / fs) * saturate(_Dots.y / fs - 0.7);
                    }
                    // 縁の外の泡の白い点：前の白（爪の帯）の縁の外 0〜_FoamDots.w（F）、縁の近くほど多い
                    float dOut = F - edgeF;
                    [branch] if (front && _FoamDots.z > 0.0 && dOut >= 0.0 && dOut < _FoamDots.w)
                    {
                        float cellD = max(_FoamDots.x, 0.05);
                        float2 pd = float2(s, ca) / cellD + 0.5;
                        float2 cd = floor(pd);
                        float3 hd = Hash3(cd + 41.0);
                        float2 cen = cd + 0.2 + 0.6 * hd.yz;
                        float rr = _FoamDots.y * (0.45 + 0.75 * frac(hd.x * 7.31));
                        float d2 = length((pd - cen) * cellD);
                        float probD = _FoamDots.z * saturate(1.0 - dOut / max(_FoamDots.w, 1e-3));
                        float on = frac(hd.x * 3.17 + 0.11) < probD ? 1.0 : 0.0;
                        dotCov = max(dotCov, on * arrived * saturate(0.5 + (rr - d2) / fs) * saturate(rr / fs - 0.7));
                    }
                }
                // ---- 爪の帯の輪の中の流れの線
                float ringLine = 0.0;
                [branch] if (czCov * ringCov > 0.0 && _CzLines.w > 0.5)
                {
                    float pw2;
                    ringLine = FlowLines(q, kc, lam * max(_CzLines.x, 1.0), _CzLines.y, s, fq, pw2);
                    ringLine *= saturate((pw2 - _GrooveFadePx.x) / max(_GrooveFadePx.y - _GrooveFadePx.x, 1e-3));
                }
                // ---- ID
                if (_AF28IdMode > 0.5)
                {
                    int cls;
                    if (whiteCov >= 0.5) cls = mizCov >= 0.5 ? 1 : 0;
                    else if (czCov >= 0.5 && ringCov >= 0.5) cls = ringLine >= 0.5 ? (_CzLines.z > 0.5 ? 0 : 2) : 1;
                    else if (dotCov >= 0.5) cls = 0;
                    else if (valCov >= 0.5) cls = gV >= 0.5 ? 2 : 3;
                    else cls = grooveCov >= 0.5 ? 2 : 3;
                    return float4(IdColour(cls), 1);
                }

                float3 body = lerp(_AiDark.rgb, _AiMid.rgb, grooveCov);
                float3 vbody = lerp(_AiDark.rgb, _AiMid.rgb, gV);
                body = lerp(body, vbody, valCov);
                body = lerp(body, _White.rgb, dotCov);
                float3 ringCol = lerp(_Mizuiro.rgb, _CzLines.z > 0.5 ? _White.rgb : _AiMid.rgb, ringLine);
                float3 col = lerp(body, lerp(body, ringCol, ringCov), czCov);
                float3 wcol = lerp(_White.rgb, _Mizuiro.rgb, mizCov);
                col = lerp(col, wcol, whiteCov);
                // 線は、面が視線にほぼ平行な所（唇の先の折り返しなど、面の帯が 1〜2 画素になる所）では薄める（線は画面の上の太さなので、ここだけは視点の量を使う。色の範囲は視点によらない）
                float3 V = normalize(_WorldSpaceCameraPos - i.wp);
                float nv = abs(dot(normalize(i.n), V));
                float graze = saturate((nv - _EdgeGrazing.x) / max(_EdgeGrazing.y - _EdgeGrazing.x, 1e-3));
                if (_EdgeLinePx > 0.0)
                {
                    float lineCov = saturate(0.5 * _EdgeLinePx + 0.5 - abs(zW)) * graze;
                    col = lerp(col, _LineCol.rgb, lineCov);
                }
                if (_CzLinePx > 0.0 && czOn && ringW > 0.0)
                {
                    // 輪と藍の境（輪の舌の縁と、帯の外の縁）。頂の白の帯の側は上の線が受け持つ
                    float zM = min(min(zRing, zCzOut), zArr) / aa;
                    float lc = saturate(0.5 * _CzLinePx + 0.5 - abs(zM)) * graze * saturate(0.5 + zBelowTop / aa) * (1.0 - whiteCov);
                    col = lerp(col, _LineCol.rgb, lc);
                }
                if (_ValleyLinePx > 0.0 && _Valley.w > 0.5)
                {
                    float lv = saturate(0.5 * _ValleyLinePx + 0.5 - abs(zValD / aa)) * saturate(0.5 + zValF / aa) * graze * (1.0 - whiteCov);
                    col = lerp(col, _LineCol.rgb, lv);
                }
                return float4(col, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
