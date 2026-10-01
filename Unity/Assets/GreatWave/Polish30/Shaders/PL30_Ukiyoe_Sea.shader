// 仕上げ30（Q28 を周りの海へ）：周りの海（near・far）と、その上の右の高い波・肩の稜・手前の小波・谷の縁の、視点によらない立体の浮世絵の材質。
// 主役波の PL29 Ukiyoe Keypose と同じ版の重ね（藍濃の胴・流れに沿う藍中の溝・白の頂・爪の指の房と泡・境の藍の線・胴の白い点）を、海の面の座標で描く。
// 原画カメラからの投影・原画の色区・t* の高さの段の表（設計36 の DS36SeaPalette）は使わない。色は次だけで決まる：
//   ・面の座標（頂点ごと、pl30_sea_attr.py が t* の網と地形の誘導から作る。PL30UkiyoeSea が UV3〜UV7 に入れる。修正01 で 20 個）
//       UV3 = (qR, uR, hR, wR)      稜の系（右の高い波＋肩の稜）：稜に垂直な符号付きの距離 m（+ 前）、稜に沿う弧長 m、頂の t* の高さ m、重み
//       UV4 = (xS, yS, hfS, wS)     手前の小波の系：頂からの楕円の正規化の座標（角度と距離はこの断片の中で求める＝頂の後ろの切れ目がない）、t* の高さの比、重み
//       UV5 = (t* の法線 xyz, a*)    a* は波の枠の進む向きの座標 m
//       UV6 = (s, along, rimq, tw)  継ぎ目からの距離 m、海の溝の沿う座標 m（輪を一周すると 28 m の整数倍）、谷の縁の頂からの垂直の距離 m（− が谷の側）、谷の縁の重み
//       UV7 = (hfR, mixR, boatw, wsh) 稜の系の t* の高さの比、前と背の白の閾値の混ぜ、座席の船の支えの当て布の重み、肩の稜の重み
//   ・今の高さ（形成の途中の頂点の位置の y。DS27 keypose）と、今の時刻 τ（_DS27Tau。谷の縁の段の育ちだけに使う）。
// 修正01（自己評審）で変えた所：
//   1) 面の座標を連続な場にした（稜の系は二つの稜の座標を t* の高さの差で混ぜる。作る部の版は近い稜を頂点ごとに選び、u が 1000 m・q が 285 m 跳んで継ぎ目の線になった）。
//      海の溝のうねり・切れは稜の弧長ではなく、海の沿う座標 along で決める。
//   2) 白の縁の爪：周期の揃った房（櫛・ジッパーの歯）をやめ、二つの層（周期の違う房を確率で置く）・房ごとの長さと幅の揺れ・まとまり（ゆっくりした揺れで長い房が群れる）・
//      伸びるほど横へ曲がる指（主役波の _Finger と同じ形）・縁の低い揺れにした。背の白は頂だけ（閾値 0.92）で、房は短い。白の中は淡い水色の流れの線・房の陰・泡の粒。
//   3) 波の胴：溝の周期が画面で大きい所（近い所）に細い溝の段を足す（目の近くの平らな面）。急な面（t* の法線の上向きが小さい所）は溝を太くして面の向きを見せる。胴の白い点。
//   4) 谷：今の深さの段（t 9 s 前後の淡い色の斑）をやめ、生成器の谷の縁のうねり（pl30_trough_rim）の頂を境に、谷の側（継ぎ目〜頂）を藍中の地に藍濃の溝（縁に平行、
//      谷の底へ向かって太る）にし、頂に藍の線と泡の白い点を付ける。段は τ が _TroughGrow.x → y の間に頂から谷の底へ広がる（谷が深くなる最後の時間）。
// 修正02（自己評審の修正の回 2）で変えた所：
//   1) 形成の途中の偽の白：今の高さの比 hrel = y/hR だけでは、t* で頂でない頂点（帯が主役波の形成で持ち上がった所）でも白が出た。
//      今の高さの比を「その系の今の育ち g(τ)（表 _GrowR・_GrowS。生成器の growth_right_knots・growth_knots）× t* の高さの比 hf ＋ _CapGate.x」で上から抑え、
//      白を t* の頂の近くに限る（t* では g = 1 で hf の門。形成の途中は系がまだ育っていない所の白を消す）。頂の泡の線も同じ比を使う。
//   2) 手前の小波：楕円の座標の極（頂）から _CapGate.y〜z m の内は白の中の淡い水色（房の陰・流れの線・泡の粒・陰の帯）を描かない（三日月・輪）。
//      房の長さを今の小波の白い頂の高さ（(g − 閾値)/(1 − 閾値)）に比例させる（形成の途中の触手）。
//   3) 右の高い波の白：背の側は稜から _CapQ.x m（q）、前の側は _CapQ.y m を越えると閾値を坂で上げる（白の幅の上限。房は同じ閾値から垂れる）。
//      房は前の側からだけ垂らす（背の房の倍 _Claw3.w を前と背の混ぜで滑らかに）。
//   4) 肩の稜（低い鞍）の白：頂の泡の線を |q| < _CrestFoamQ.x m の細い線にし、線の幅が画面で _CrestFoamQ.y〜z 画素より細い所（遠く見える所）では切る。
//      肩の稜の普通の白も、肩の稜の重みに応じて同じ細い線に寄せる（原画視点 t* の水平線の白い楔）。肩の稜の所は 3) の q の坂を掛けない（q が二つの稜の混ぜ）。
//   5) 谷の縁の段の端：谷の縁の重み tw に応じて段の帯の幅を細らせる（真上で帯の端が真っ直ぐに切れていた）。
// ID 表示（大域の _AF28IdMode = 1）：白 赤、淡い水色 緑、藍中 青、藍濃 黄（主役波と同じ約束）。_PL29Diag が 1〜6 のときも ID の色（主役波の印ではない）。
//   _PL29Diag = 7：谷の縁の段の印（段の中 マゼンタ、ほか黒）。8：稜の系の重み（R）・小波の重み（G）・谷の縁の重み（B）。9：稜の系の今の高さの比（R）・q（G）・肩の稜の重み（B）。
//   10：海の溝（R）・波の溝（G）・波の溝の重み（B）。（7〜10 は修正01 の点検のため）
// 名前に Keypose を含むのは、ID の描画（KeepMaterial）がこの材質を残して色区の ID を描くため。SPI の立体視マクロは設計27 と同じ形（HMD 実機は未検証）。
Shader "GreatWave/Polish30/PL30 Ukiyoe Sea Keypose"
{
    Properties
    {
        _White ("白・生成り", Color) = (0.97255, 0.95294, 0.87451, 1)
        _Mizuiro ("淡い水色", Color) = (0.77647, 0.84314, 0.79608, 1)
        _AiMid ("藍中", Color) = (0.17255, 0.41176, 0.57647, 1)
        _AiDark ("藍濃", Color) = (0.13725, 0.25098, 0.38039, 1)
        _LineCol ("藍の線", Color) = (0.2784314, 0.3137255, 0.372549, 1)
        _SeaLines ("平らな海の溝：x 周期 m、y 幅／周期、z うねりの振幅（周期の倍）、w 0 で描かない", Vector) = (2.6, 0.16, 0.25, 1)
        _SeaLines2 ("平らな海の溝：x うねりの波長 m（along。28 の約数）、y 切れの長さ m（28 の約数）、z 埋める割合、w 継ぎ目の近くで消す s m", Vector) = (28, 14, 0.85, 0.6)
        _SeaFine ("近い所の細い溝の段：x 周期（主の周期の倍）、y 幅／周期、z 現れ始める主の周期の画素、w 全部の画素", Vector) = (0.25, 0.16, 36, 80)
        _SeaLinesFar ("遠い所の溝（波峰線に平行＝a の等値線）：x 周期 m、y 幅／周期、z 主役波の足に平行な溝から移る s の始め m、w 終わり m", Vector) = (3.4, 0.14, 16, 34)
        _FeatLines ("波の溝：x 周期 m、y 幅／周期（頂の側）、z 幅／周期（足の側）、w 0 で描かない", Vector) = (1.15, 0.14, 0.32, 1)
        _FeatLines2 ("波の溝：x うねりの振幅（周期の倍）、y うねりの波長 m（u）、z 切れの長さ m、w 埋める割合", Vector) = (0.12, 11, 9, 0.9)
        _FeatSteep ("急な面の溝：x 法線の上向きの閾値（これより小さいと太る）、y 太る幅／周期の足し分、z 細い溝の段の周期（主の倍）、w 細い溝の段が現れ始める主の周期の画素", Vector) = (0.62, 0.14, 0.33, 40)
        _GrooveFadePx ("溝を消す周期の画素（x 消える、y 全部）", Vector) = (3, 6, 0, 0)
        _CapR ("稜の系の白：x 前の閾値（今の高さ ÷ 頂の t* の高さ）、y 背の閾値、z（修正01 から使わない。前と背の混ぜは面の座標 UV7.y）、w 白にする頂の高さの下限 m", Vector) = (0.74, 0.92, 1.5, 2.0)
        _CapS ("小波の白：x 閾値、y 頂の高さ m、z 溝の半径の見当 m、w 爪の数（一周）", Vector) = (0.62, 5.64, 6.0, 24)
        _CapMin ("白の下限：x 今の高さの下限 m、y 頂の高さに対する今の高さの下限の倍、z 系の重みの下限、w 縁の低い揺れの振幅（比）", Vector) = (2.6, 0.62, 0.5, 0.035)
        _Claw ("爪の指の房（層 1）：x 周期 m、y 最長（比）、z 置く割合、w 曲がり m（最長のとき）", Vector) = (3.1, 0.16, 0.8, 1.6)
        _Claw2 ("爪の指の房（層 2）：x 周期 m、y 最長（比）、z 置く割合、w 幅（周期の倍）", Vector) = (4.9, 0.11, 0.55, 0.62)
        _Claw3 ("爪の不揃い：x 幅の揺れ、y 中心のずれ（周期の倍）、z まとまりの波長 m、w 背の長さの倍", Vector) = (0.45, 0.35, 23, 0.22)
        _Claw4 ("爪：x 層 1 の幅（周期の倍）、y 房の間の切れ込み（比）、z 長い房の割合、w 長い房の倍", Vector) = (0.7, 0.025, 0.18, 1.6)
        _ClawTip ("爪の先と縁の舌：x 指の先を小さな爪に割る切れ込み（長さの倍）、y 縁の小さな舌を置く割合", Vector) = (0.3, 0.6, 0, 0)
        _Fringe ("縁の泡の小さな舌：x 周期 m、y 長さ（比）、z 切れ込み（比）、w 0 で描かない", Vector) = (0.62, 0.03, 0.02, 1)
        _LobeShade ("房の陰（淡い水色）：x 縁からの帯の幅（比）、y 房の中の陰の側の割合、z 帯の揺れ（比）、w 0 で描かない", Vector) = (0.07, 0.42, 0.02, 1)
        _CapLines ("白の中の淡い水色の流れの線（q の等値線）：x 周期 m、y 幅／周期、z 頂の側で消す比、w 0 で描かない", Vector) = (2.2, 0.08, 0.97, 1)
        _ShadeN ("白の中の淡い水色の陰の帯（t* の法線の上向き n.y が x より小さい急な面）：x 閾値、y 帯の周期 m、z 淡い水色の割合、w 0 で描かない", Vector) = (0.6, 1.7, 0.5, 1)
        _FoamCells ("白の中の淡い水色の泡の粒：x 格子 m、y 半径（格子の倍）、z 縁での割合、w 縁から内へ届く幅（比）", Vector) = (0.9, 0.33, 0.7, 0.12)
        _FoamDots ("縁の外の泡の白い点：x 格子 m、y 半径 m、z 縁での割合、w 縁から外へ届く幅（比）", Vector) = (0.6, 0.12, 0.5, 0.12)
        _BodyDots ("胴の白い点：x 格子 m、y 半径 m、z 割合、w 置く比の下限", Vector) = (0.67, 0.07, 0.25, 0.3)
        _CrestFoam ("稜の頂の泡の線（低い鞍でも頂を白で続ける）：x 頂の高さの上限 m（これより低い稜だけ）、y 白の閾値（比）、z 今の高さの下限 m、w 0 で描かない", Vector) = (4.5, 0.86, 1.2, 1)
        _TroughRim ("谷の縁：x 縁の頂の継ぎ目からの垂直の距離 m（生成器の s_rim）、y 縁の揺れ m、z 揺れの波長 m、w 0 で描かない", Vector) = (2.6, 0.18, 9.3, 1)
        _TroughGrow ("谷の縁の段の育ち：x 始まりの τ s、y 終わりの τ s", Vector) = (-0.8, -0.05, 0, 0)
        _TroughLip ("谷の縁の頂の外の唇の帯：x 幅 m", Vector) = (0.9, 0, 0, 0)
        _TroughLines ("谷の側の溝（縁に平行、藍濃）：x 周期 m、y 幅／周期（縁）、z 幅／周期（谷の底）、w 切れの長さ m", Vector) = (0.55, 0.22, 0.72, 7)
        _TroughFoam ("谷の縁の泡の白い点：x 格子 m、y 半径 m、z 割合、w 縁から外へ届く幅 m", Vector) = (0.5, 0.075, 0.45, 0.7)
        _GrowR0 ("稜の系の育ち g_r の表（s = √(−τ/12) の 28 点、s = k/27）0〜3", Vector) = (1, 1, 1, 1)
        _GrowR1 ("同 4〜7", Vector) = (1, 1, 1, 1)
        _GrowR2 ("同 8〜11", Vector) = (1, 1, 1, 1)
        _GrowR3 ("同 12〜15", Vector) = (1, 1, 1, 1)
        _GrowR4 ("同 16〜19", Vector) = (1, 1, 1, 1)
        _GrowR5 ("同 20〜23", Vector) = (1, 1, 1, 1)
        _GrowR6 ("同 24〜27", Vector) = (1, 1, 1, 1)
        _GrowS0 ("小波の育ち g の表（同じ 28 点）0〜3", Vector) = (1, 1, 1, 1)
        _GrowS1 ("同 4〜7", Vector) = (1, 1, 1, 1)
        _GrowS2 ("同 8〜11", Vector) = (1, 1, 1, 1)
        _GrowS3 ("同 12〜15", Vector) = (1, 1, 1, 1)
        _GrowS4 ("同 16〜19", Vector) = (1, 1, 1, 1)
        _GrowS5 ("同 20〜23", Vector) = (1, 1, 1, 1)
        _GrowS6 ("同 24〜27", Vector) = (1, 1, 1, 1)
        _CapGate ("白の門：x 余裕（g×hf が 閾値 − 房 − x を越える所だけ白）、y 小波の極の近くで白の中の淡い水色を描かない半径 m（全部消す）、z 同（全部描く）、w 0 で使わない", Vector) = (0.1, 0.9, 1.6, 1)
        _CapQ ("稜の系の白の幅の上限：x 背の側 m（稜から背へ）、y 前の側 m、z その外で閾値を上げる坂（1 m あたり）、w 0 で使わない", Vector) = (1.0, 1.6, 0.4, 1)
        _CapQ2 ("稜の系の白の幅の上限（続き）：x 房を伸ばす時の自然の坂（今の高さの比の 1 m あたりの下がり）、y 肩の稜の細い線を頂のすぐ近く（今の高さの比がこれより上）でもつなぐ（低い鞍）、z 同（頂の高い合流の近く）", Vector) = (0.12, 0.985, 0.95, 0)
        _CrestFoamQ ("肩の稜の白の細い線：x 半幅 m、y 線の幅が画面でこの画素より細いと消える、z この画素で全部、w 0 で使わない", Vector) = (0.35, 1.2, 2.4, 1)
        _TroughTaper ("谷の縁の段の端を細らせる：x 重み tw の始め（帯の幅 0）、y 全部の幅", Vector) = (0.15, 0.85, 0, 0)
        _EdgeLinePx ("境の線（画素。0 で描かない）", Float) = 1.4
        _TroughLinePx ("谷の縁の線（画素。0 で描かない）", Float) = 1.6
        _EdgeGrazing ("線を薄める面の傾き（x 消える |n·v|、y 全部）", Vector) = (0.05, 0.16, 0, 0)
        _FeaturePx ("舌・切れ込みを消す画素（x 消える、y 全部）", Vector) = (1.0, 2.5, 0, 0)
        _AAScale ("アンチエイリアスの幅（画素）", Float) = 1
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "PL30UkiyoeSea"
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
            float4 _SeaLines, _SeaLines2, _SeaFine, _SeaLinesFar, _FeatLines, _FeatLines2, _FeatSteep, _GrooveFadePx;
            float4 _CapR, _CapS, _CapMin, _Claw, _Claw2, _Claw3, _Claw4, _ClawTip, _Fringe, _LobeShade, _CapLines, _ShadeN;
            float4 _FoamCells, _FoamDots, _BodyDots, _CrestFoam, _TroughRim, _TroughGrow, _TroughLip, _TroughLines, _TroughFoam, _EdgeGrazing, _FeaturePx;
            float4 _GrowR0, _GrowR1, _GrowR2, _GrowR3, _GrowR4, _GrowR5, _GrowR6, _GrowS0, _GrowS1, _GrowS2, _GrowS3, _GrowS4, _GrowS5, _GrowS6;
            float4 _CapGate, _CapQ, _CapQ2, _CrestFoamQ, _TroughTaper;
            float _EdgeLinePx, _TroughLinePx, _AAScale;
            float _AF28IdMode;
            float _PL29Diag;

            struct appdata
            {
                float4 vertex : POSITION;
                float4 a : TEXCOORD3;
                float4 b : TEXCOORD4;
                float4 nst : TEXCOORD5;
                float4 d : TEXCOORD6;
                float4 e : TEXCOORD7;
                uint vid : SV_VertexID;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float4 a : TEXCOORD0;
                float4 b : TEXCOORD1;
                float4 nst : TEXCOORD2;
                float4 d : TEXCOORD3;
                float4 e : TEXCOORD4;
                float3 n : TEXCOORD5;
                float3 wp : TEXCOORD6;
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
                o.a = v.a; o.b = v.b; o.nst = v.nst; o.d = v.d; o.e = v.e;
                o.n = _DS27Enabled > 0.5 ? DS27Normal(v.vid) : float3(0, 1, 0);
                return o;
            }

            float Px(float v) { return v / max(fwidth(v), 1e-6); }
            float Hash1(float x) { return frac(sin(x * 127.1 + 311.7) * 43758.5453); }
            float3 Hash3(float2 p)
            {
                float3 q = float3(dot(p, float2(127.1, 311.7)), dot(p, float2(269.5, 183.3)), dot(p, float2(419.2, 371.9)));
                return frac(sin(q) * 43758.5453);
            }
            float LobeProfile(float u, float w)
            {
                float x = (u - 0.5) / max(0.5 * saturate(w), 1e-3);
                return sqrt(saturate(1.0 - x * x));
            }
            float3 IdColour(int k)
            {
                return k == 0 ? float3(1, 0, 0) : (k == 1 ? float3(0, 1, 0) : (k == 2 ? float3(0, 0, 1) : float3(1, 1, 0)));
            }
            float FadePx(float px) { return saturate((px - _GrooveFadePx.x) / max(_GrooveFadePx.y - _GrooveFadePx.x, 1e-3)); }

            // 修正02：系の今の育ち g(τ)（生成器の growth_knots・growth_right_knots を s = √(−τ/12) の 28 点に取った表。τ ≥ 0 は表の 0 番＝1）
            float GrowTab(float4 t0, float4 t1, float4 t2, float4 t3, float4 t4, float4 t5, float4 t6)
            {
                float4 T[7] = { t0, t1, t2, t3, t4, t5, t6 };
                float s = sqrt(saturate(-_DS27Tau / 12.0)) * 27.0;
                int i0 = min((int)floor(s), 26);
                float f = s - (float)i0;
                int i1 = i0 + 1;
                float a0 = T[i0 >> 2][i0 & 3], a1 = T[i1 >> 2][i1 & 3];
                return lerp(a0, a1, f);
            }

            // 等値線の溝の覆い：座標 x の上に周期 P、幅の割合 ratio、切れ（沿う座標 along、長さ dashL、割合 duty）。fx は x の画面の微分
            float Lines(float x, float P, float ratio, float along, float dashL, float duty, float fx, out float periodPx)
            {
                float g = frac(x / P);
                float d = min(g, 1.0 - g) * P;
                float id = floor(x / P + 0.5);
                float tt = 1.0;
                if (dashL > 0.01)
                {
                    float uu = frac(along / dashL + Hash1(id * 3.17 + 0.5));
                    tt = uu < duty ? pow(saturate(sin(3.14159265 * uu / max(duty, 1e-3))), 0.35) : 0.0;
                }
                float hw = 0.5 * ratio * P * tt;
                periodPx = P / fx;
                return saturate(0.5 + (hw - d) / fx) * saturate(2.0 * hw / fx - 0.5);
            }

            // 爪の指の房の一つの層：沿う座標 cl の上に周期 P のセル。置く割合 pr、最長 Lm、幅 W（周期の倍）。まとまり clus（0〜1）で長さを変える。
            // perN > 0 なら房の番号を perN で割った余りで乱数を取る（一周で閉じる小波の角度の座標の切れ目をなくす）。返り値：舌の長さ（比）。uL に房の中の位置。
            float ClawLayer(float cl, float P, float pr, float Lm, float W, float seed, float clus, float perN, float fcl, float fH, out float uL)
            {
                float fi = floor(cl / P);
                float fiw = perN > 0.5 ? fi - perN * floor(fi / perN) : fi;
                float ul = cl / P - fi;
                float h1 = Hash1(fiw * 1.37 + seed), h2 = Hash1(fiw * 2.71 + seed + 4.7), h3 = Hash1(fiw * 3.91 + seed + 9.1), h4 = Hash1(fiw * 5.13 + seed + 2.3);
                float on = h1 < pr ? 1.0 : 0.0;
                float len = Lm * (0.35 + 0.65 * h2) * lerp(0.45, 1.0, clus);
                len *= h4 < _Claw4.z ? _Claw4.w : 1.0;
                float uc = ul - _Claw3.y * (h3 - 0.5);
                float wj = W * (1.0 - _Claw3.x * Hash1(fiw * 6.07 + seed + 1.1));
                // 指の形：先の尖った錐（_ClawTip.z の冪。丸い舌＝垂れた氷柱に見えないように）
                float xw = abs(uc - 0.5) / max(0.5 * saturate(wj), 1e-3);
                float prof = pow(saturate(1.0 - xw), max(_ClawTip.z, 0.3));
                // 指の先を小さな爪（2〜4 本）に割る：指の幅の中を nsub に分け、先の _Claw4 の… 長さの tipCut を切り込む（指の終わりの縁が丸い一つの舌にならない）
                float nsub = 2.0 + floor(3.0 * Hash1(fiw * 7.31 + seed + 0.9));
                float u2 = saturate((uc - 0.5) / max(wj, 1e-3) + 0.5);
                float subP = pow(saturate(1.0 - abs(frac(u2 * nsub) - 0.5) * 2.0), 0.6);
                prof *= 1.0 - _ClawTip.x * (1.0 - subP);
                uL = uc;
                float gapPx = P * (1.0 - saturate(W) * 0.7) / fcl;
                float depPx = len / fH;
                float k = saturate((min(gapPx, depPx) - _FeaturePx.x) / max(_FeaturePx.y - _FeaturePx.x, 1e-3));
                return on * k * len * prof;
            }

            struct Wv
            {
                float whiteCov; float zW; float mizCov; float groove; float dotOut; float bodyDot; float dIn; float3 dg;
            };

            // 波の系（稜の系・小波）の白・溝・泡。q 横切りの座標 m（+ 前）、u 沿う座標 m、hc 頂の t* の高さ m、w 重み、y 今の高さ、hf t* の高さの比、
            // nyS t* の法線の上向き、small 小波、fu・fq・fH 画面の微分（呼ぶ側で枝の外で取る）、perN 小波の爪の周期の数（稜の系は 0）
            Wv WaveSys(float q, float u, float hc, float w, float y, float hf, float nyS, bool small, float fu, float fq, float perN, float wsh, float mixF, float gNow)
            {
                Wv r;
                float aa = max(_AAScale, 1e-3);
                float hcs = max(hc, 0.5);
                // 修正02：白を t* の頂の近くに限る：今の高さの比を、その系の今の育ち × t* の高さの比（＋余裕 _CapGate.x）で上から抑える。
                // 形成の途中に帯が持ち上がった所（系がまだ育っていない所）と、t* でも帯・海が頂より高く持ち上げた所の偽の白を消す（t* で頂の近くは hf ≈ 今の高さの比で変わらない）
                float hExp = gNow * hf;
                float hrel = (_CapGate.w > 0.5) ? min(y / hcs, hExp + _CapGate.x) : y / hcs;
                float fH = max(fwidth(hrel), 1e-6);
                // 閾値：前へこぼれる白、背は頂だけ。縁の低い揺れ（帯の真っ直ぐな縁を割る）
                float thr0 = small ? _CapS.x : lerp(_CapR.y, _CapR.x, saturate(mixF));   // 前と背の閾値の混ぜは面の座標（二つの稜を混ぜた所で切れない）
                float wob = _CapMin.w * (sin(6.2831853 * u / 13.0 + 2.0 * sin(6.2831853 * u / 31.0)) * 0.7 + 0.3 * sin(6.2831853 * u / 5.3 + 1.1));
                thr0 += small ? 0.4 * wob : wob;
                // 修正02：稜の系の白の幅を q（m）で上限：背の側は稜から _CapQ.x m、前の側は _CapQ.y m を越えると、閾値を 1 m あたり _CapQ.z 上げる
                // （硬い q の切りは、q の 0 が本当の頂とずれる所で房の先だけが離れて残ったので、閾値の坂にして白の縁と房を同じ一つの場で決める）
                // 肩の稜（重み wsh）の所は q が二つの稜の座標を混ぜた値なので、坂を掛けない（肩の稜の白は下の細い線で決める。合流の所で白が切れた）
                float kShW = small ? 0.0 : saturate((wsh - 0.05) / 0.25);   // 肩の稜の重みが少しでもある所（合流の近くの混ぜの所を含む）は肩の稜として扱う
                float qPen = (!small && _CapQ.w > 0.5) ? _CapQ.z * (max(0.0, q - _CapQ.y) + max(0.0, -q - _CapQ.x)) * (1.0 - kShW) : 0.0;
                // 肩の稜の所は閾値を前の閾値 _CapR.x に寄せる（白は下の細い線で決まる。合流の近くは混ぜた頂の高さが本当の頂より高く、今の高さの比が 0.96〜0.98 に止まって背の閾値 0.94＋揺れで切れた）
                if (_CrestFoamQ.w > 0.5) thr0 = lerp(thr0, _CapR.x, kShW);
                thr0 += qPen;
                bool front = small ? true : (mixF > 0.5);
                // 頂が閾値を越えたばかりの所では房を短くする（細い白が梯子に割れるのを防ぐ）
                float crestNow = hrel / max(hf, 0.05);
                float emerge = saturate((crestNow - thr0) / 0.12);
                // 爪の指の房：伸びるほど横へ曲がる（主役波の _Finger と同じ形）。二つの層の大きい方
                float beyond = saturate((thr0 - hrel) / max(_Claw.y * _Claw4.w, 1e-3));
                float cl = u + _Claw.w * beyond * beyond * (front ? 1.0 : 0.4);
                float fcl = max(fu, 1e-6);
                float clus = 0.5 + 0.5 * sin(6.2831853 * u / max(_Claw3.z, 1.0) + 1.7 * sin(6.2831853 * u / 9.1));
                // 修正02：房は前の側から垂らす（背の倍 _Claw3.w を前と背の混ぜで滑らかに。作る部・修正01 は mixF 0.5 で切り替えた）
                float backK = small ? 1.0 : lerp(_Claw3.w, 1.0, smoothstep(0.3, 0.7, mixF));
                float uL1, uL2;
                float P1 = small ? (6.2831853 / max(perN, 1.0)) * 0.0 + _Claw.x * 0.5 : _Claw.x;
                float t1 = ClawLayer(cl, P1, _Claw.z, _Claw.y * backK, _Claw4.x, 3.1, clus, small ? perN : 0.0, fcl, fH, uL1);
                float t2 = small ? 0.0 : ClawLayer(cl + 0.37 * _Claw2.x, _Claw2.x, _Claw2.z, _Claw2.y * backK, _Claw2.w, 7.7, clus, 0.0, fcl, fH, uL2);
                float tongue = max(t1, t2);
                float uLobe = t1 >= t2 ? uL1 : uL2;
                // 房の間の小さな切れ込み（縁が真っ直ぐな帯に見えないように）
                tongue -= _Claw4.y * (1.0 - saturate(tongue / max(_Claw4.y, 1e-3))) * emerge;
                if (_Fringe.w > 0.5)
                {
                    float Pf = max(_Fringe.x, 0.05);
                    float cf = cl + 0.29 * Pf;
                    float ff = floor(cf / Pf);
                    float nF = round(perN * P1 / Pf);                  // 小波：一周の舌の数（_Claw.x·0.5·_CapS.w ÷ _Fringe.x を整数に選ぶ）
                    float ffw = small && perN > 0.5 ? ff - floor(ff / max(nF, 1.0)) * nF : ff;
                    float pf = LobeProfile(cf / Pf - ff, 0.55 + 0.4 * Hash1(ffw * 4.3 + 0.7));
                    float lf = _Fringe.y * (0.2 + 1.2 * Hash1(ffw * 1.7 + 5.3)) * (front ? 1.0 : 0.6);
                    lf *= Hash1(ffw * 2.9 + 8.1) < _ClawTip.y ? 1.0 : 0.0;          // 置く割合（櫛の歯のような揃いを崩す）
                    float gapPx = 0.45 * Pf / fcl;
                    float depPx = min(_Fringe.z, lf) / fH;
                    float k = saturate((min(gapPx, depPx) - _FeaturePx.x) / max(_FeaturePx.y - _FeaturePx.x, 1e-3));
                    tongue += k * (lf * pf - _Fringe.z * (1.0 - pf));
                }
                tongue *= emerge;
                // 修正02：小波の房の長さを、今の小波の白い頂の高さ（t* の白い頂の高さに対する比）に比例させる（形成の途中に房が長い触手に見えた）
                if (small) tongue *= saturate((gNow - _CapS.x) / max(1.0 - _CapS.x, 0.05));
                // 修正02：前の側の上限（_CapQ.y）の外では閾値の坂（_CapQ.z）の分だけ房を伸ばす（房の届く長さを坂のない所と同じ ≈ 房 ÷ 自然の坂 _CapQ2.x に保つ）
                float tScale = (!small && _CapQ.w > 0.5) ? (_CapQ.z / max(_CapQ2.x, 0.02)) * smoothstep(_CapQ.y - 0.3, _CapQ.y + 0.3, q) * (1.0 - kShW) : 0.0;
                float thr = thr0 - tongue * (1.0 + tScale);
                float minY = min(_CapMin.x, _CapMin.y * hcs);
                float zW = Px(hrel - thr);
                zW = min(zW, Px(w - _CapMin.z));
                zW = min(zW, Px(hc - (small ? 2.0 : _CapR.w)));
                zW = min(zW, Px(y - minY));
                r.dg = float3(hrel - thr, y / hcs - hrel, 0);
                r.dg.z = qPen > 0.0 ? 0.0 : 1.0;
                // 修正02：肩の稜（重み kShW のある所の全部）の白は |q| < _CrestFoamQ.x か頂のすぐ近くの細い線に寄せる。
                // 低い鞍（頂 < _CrestFoam.x m）で線の幅が画面で細すぎる所（遠く見える所）は切る（原画視点 t* の水平線の白い楔）
                float lineK = 1.0;
                float zLine = 1e3;
                if (!small && _CrestFoamQ.w > 0.5)
                {
                    float fqq = max(fwidth(q), 1e-6);
                    float linePx = 2.0 * _CrestFoamQ.x / fqq;
                    lineK = saturate((linePx - _CrestFoamQ.y) / max(_CrestFoamQ.z - _CrestFoamQ.y, 1e-3));
                    lineK = lerp(1.0, lineK, saturate((_CrestFoam.x - hc) / 1.0));   // 遠くで切るのは低い鞍（頂 < _CrestFoam.x m）だけ。合流の近くの高い頂は線を残す（右の高い波の白の帯が線へ細って続く）
                    // 線：|q| < 半幅、または頂のすぐ近く（今の高さの比 > _CapQ2.y。合流の近くでは q が二つの稜の混ぜで 0 にならず、線が切れたので）
                    float topThr = lerp(_CapQ2.z, _CapQ2.y, saturate((_CrestFoam.x - hc) / 1.0));   // 低い鞍は 0.985、合流の近く（頂が高い）は 0.95
                    zLine = min(max((_CrestFoamQ.x - abs(q)) / fqq, (hrel - topThr) / fH), (lineK - 0.5) * 4.0);
                    float kSh = kShW;   // 修正02：肩の稜の全部（低い鞍だけでなく合流の近くも）を細い線に寄せる
                    zW = lerp(zW, min(zW, zLine), kSh);
                }
                // 稜の頂の泡の線：低い稜（肩の稜の鞍）でも、頂（t* の高さの比 hf > 閾値）が今の高さで育った所は白でつなぐ
                if (!small && _CrestFoam.w > 0.5 && wsh > 0.05)
                {
                    float zc = min(Px(hrel - _CrestFoam.y + 0.5 * tongue), Px(_CrestFoam.x - hc));
                    zc = min(zc, Px(hc - _CrestFoam.z));                 // 頂の t* の高さが _CrestFoam.z より高い稜だけ
                    zc = min(zc, Px(y - _CrestFoam.z));
                    zc = min(zc, Px(w - _CapMin.z));
                    zc = min(zc, Px(wsh - 0.5));                              // 肩の稜（右の高い波との混ぜの重み > 0.5）だけ
                    if (_CrestFoamQ.w > 0.5) zc = min(zc, zLine);                                                  // 修正02：細い線・遠くは切る
                    zW = max(zW, zc);
                }
                r.zW = zW / aa;
                r.whiteCov = saturate(0.5 + r.zW);
                float dIn = hrel - thr, dOut = thr - hrel;
                r.dIn = dIn;
                float fDIn = max(fwidth(dIn), 1e-6);
                float fU = max(fwidth(uLobe), 1e-6);
                float fny = max(fwidth(nyS), 1e-4);
                float fsu = max(max(fu, fq), 1e-6);
                // ---- 白の中の淡い水色：房の陰、泡の粒、流れの線、急な面の帯
                r.mizCov = 0.0;
                [branch] if (r.whiteCov > 0.0)
                {
                    if (_LobeShade.w > 0.5 && front)
                    {
                        float band = _LobeShade.x + _LobeShade.z * (Hash1(floor(cl / max(_Claw.x, 0.1)) + 9.1) - 0.5);
                        float zb = (band - dIn) / fDIn;
                        float zs = (_LobeShade.y - uLobe) / fU;
                        r.mizCov = max(r.mizCov, saturate(0.5 + min(zb, zs) / aa) * saturate(0.5 + (dIn / fDIn) / aa) * emerge);
                    }
                    if (dIn < _FoamCells.w)
                    {
                        float cell = max(_FoamCells.x, 0.1);
                        float2 pc = float2(u, q) / cell;
                        pc += 0.3 * float2(sin(pc.y * 1.37), sin(pc.x * 1.09));
                        float2 ci = floor(pc);
                        float best = 1e3; float pick = 0.0;
                        [unroll] for (int dy = -1; dy <= 1; dy++)
                            [unroll] for (int dx = -1; dx <= 1; dx++)
                            {
                                float2 cc = ci + float2(dx, dy);
                                float3 hh = Hash3(cc + 17.0);
                                float2 ctr = cc + 0.15 + 0.7 * hh.yz;
                                float d = length(pc - ctr) / (0.6 + 0.4 * hh.x);
                                if (d < best) { best = d; pick = hh.x; }
                            }
                        float prob = _FoamCells.z * saturate(1.0 - max(dIn, 0.0) / max(_FoamCells.w, 1e-3));
                        float on = Hash1(pick * 91.7) < prob ? 1.0 : 0.0;
                        float lod = saturate((_FoamCells.y * cell / fsu - 1.5) / 1.5);
                        r.mizCov = max(r.mizCov, on * lod * saturate(0.5 + (_FoamCells.y - best) * cell / fsu / aa));
                    }
                    if (_CapLines.w > 0.5)
                    {
                        float pxW;
                        float wl = Lines(q + 0.45 * _CapLines.x * sin(6.2831853 * u / 17.0), max(_CapLines.x, 0.1), _CapLines.y, u, 12.0, 0.8, fq, pxW);
                        r.mizCov = max(r.mizCov, wl * FadePx(pxW) * saturate((_CapLines.z - hrel) / 0.04));
                    }
                    if (_ShadeN.w > 0.5)
                    {
                        float zs = (_ShadeN.x - nyS) / fny;
                        float pxB;
                        float bandB = Lines(q + 0.35 * _ShadeN.y * sin(6.2831853 * u / 13.0), max(_ShadeN.y, 0.1), _ShadeN.z, u, 10.0, 0.92, fq, pxB);
                        bandB = lerp(0.5, bandB, FadePx(pxB));
                        r.mizCov = max(r.mizCov, saturate(0.5 + zs / aa) * bandB * saturate((0.985 - hrel) / 0.03));
                    }
                }
                // 修正02：小波の楕円の座標の極（頂）の近くでは、白の中の淡い水色を描かない（極に房の陰・流れの線が集まり、三日月・輪になった）
                if (small && _CapGate.w > 0.5) r.mizCov *= smoothstep(_CapGate.y, _CapGate.z, q);
                // ---- 胴の溝（稜に平行。頂で細く足で太い。急な面は太る。近い所は細い溝の段を足す）
                float lam = max(_FeatLines.x, 0.05);
                float qq = q + _FeatLines2.x * lam * sin(6.2831853 * u / max(_FeatLines2.y, 0.1));
                float ratio = lerp(_FeatLines.z, _FeatLines.y, saturate(hrel / max(thr0, 0.05)));
                ratio += _FeatSteep.y * saturate((_FeatSteep.x - nyS) / 0.15);
                float pxF;
                float gcov = Lines(qq, lam, ratio, u, _FeatLines2.z, _FeatLines2.w, fq, pxF) * FadePx(pxF);
                float lamF = lam * _FeatSteep.z;
                float pxFF;
                float fine = Lines(qq + 0.5 * lamF, lamF, 0.16, u * 1.3 + q, 4.0, 0.8, fq, pxFF);
                fine *= saturate((pxF - _FeatSteep.w) / _FeatSteep.w) * FadePx(pxFF);
                float lamF2 = lamF / 3.0;
                float pxFF2;
                float fine2 = Lines(qq + 0.27 * lamF2, lamF2, 0.15, u * 3.1 + 2.0 * q, 1.6, 0.75, fq, pxFF2);
                fine2 *= saturate((pxF - 3.0 * _FeatSteep.w) / (3.0 * _FeatSteep.w)) * FadePx(pxFF2);
                r.groove = max(max(gcov, fine), fine2);
                // ---- 縁の外の泡の白い点（前の縁の外）
                r.dotOut = 0.0;
                [branch] if (r.whiteCov < 1.0 && _FoamDots.z > 0.0 && dOut >= 0.0 && dOut < _FoamDots.w && w > _CapMin.z && front)
                {
                    float cellD = max(_FoamDots.x, 0.05);
                    float2 pd = float2(u, q) / cellD + 0.5;
                    float2 cd = floor(pd);
                    float3 hd = Hash3(cd + 41.0);
                    float2 cen = cd + 0.2 + 0.6 * hd.yz;
                    float rr = _FoamDots.y * (0.45 + 0.75 * frac(hd.x * 7.31));
                    float d2 = length((pd - cen) * cellD);
                    float probD = _FoamDots.z * saturate(1.0 - dOut / max(_FoamDots.w, 1e-3)) * emerge;
                    float on = frac(hd.x * 3.17 + 0.11) < probD ? 1.0 : 0.0;
                    r.dotOut = on * saturate(0.5 + (rr - d2) / fsu) * saturate(rr / fsu - 0.7);
                }
                // ---- 胴の白い点（紙の抜け。主役波と同じ）
                r.bodyDot = 0.0;
                [branch] if (r.whiteCov < 1.0 && w > 0.5 && hrel > _BodyDots.w)
                {
                    float cell = max(_BodyDots.x, 0.05);
                    float2 cp = float2(u, q) / cell;
                    float2 ci2 = floor(cp);
                    float3 h3 = Hash3(ci2 + 3.0);
                    float2 ctr = ci2 + 0.2 + 0.6 * h3.yz;
                    float dd = length((cp - ctr) * cell);
                    float dotOn = h3.x < _BodyDots.z ? 1.0 : 0.0;
                    r.bodyDot = dotOn * saturate(0.5 + (_BodyDots.y - dd) / fsu) * saturate(_BodyDots.y / fsu - 0.7);
                }
                return r;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float qR = i.a.x, uR = i.a.y, hR = i.a.z, wR = i.a.w;
                float xS = i.b.x, yS = i.b.y, hfS = i.b.z, wS = i.b.w;
                float aSt = i.nst.w;
                float s = i.d.x, along = i.d.y, rimq = i.d.z, tw = i.d.w;
                float hfR = i.e.x, mixR = i.e.y, boatw = i.e.z, wsh = i.e.w;
                float wRraw = wR;
                wR *= 1.0 - saturate(boatw / 0.1);                      // 座席の船の支えの当て布の中は稜の系の白にしない（当て布が形を決める）。溝は右の高い波の流れのまま（wRraw）
                float y = i.wp.y;
                float aa = max(_AAScale, 1e-3);
                float nyS = normalize(i.nst.xyz).y;

                // ---- 画面の微分（枝の外で取る）
                float fqR = max(fwidth(qR), 1e-6), fuR = max(fwidth(uR), 1e-6);
                // 小波：角度は (xS, yS) から断片の中で求め、角度の微分は解析で取る（atan2 の切れ目で fwidth が跳ばない）
                float rS = length(float2(xS, yS));
                float th = atan2(yS, xS);
                float2 dxy = float2(ddx(xS), ddx(yS)), dyy = float2(ddy(xS), ddy(yS));
                float r2 = max(rS * rS, 1e-6);
                float dthx = (xS * dxy.y - yS * dxy.x) / r2, dthy = (xS * dyy.y - yS * dyy.x) / r2;
                float NS = max(_CapS.w, 1.0);
                float uSscale = NS * _Claw.x * 0.5 / 6.2831853;
                float uS = th * uSscale;
                float fuS = max((abs(dthx) + abs(dthy)) * uSscale, 1e-6);
                float qS = rS * _CapS.z;
                float fqS = max(fwidth(qS), 1e-6);

                float gR = GrowTab(_GrowR0, _GrowR1, _GrowR2, _GrowR3, _GrowR4, _GrowR5, _GrowR6);
                float gS = GrowTab(_GrowS0, _GrowS1, _GrowS2, _GrowS3, _GrowS4, _GrowS5, _GrowS6);
                Wv R = WaveSys(qR, uR, hR, wR, y, hfR, nyS, false, fuR, fqR, 0.0, wsh, mixR, gR);
                Wv Sm = WaveSys(qS, uS, _CapS.y, wS, y, hfS, nyS, true, fuS, fqS, NS, 0.0, 1.0, gS);

                // ---- 平らな海の溝（主役波の足に平行＝s の等値線、遠くは波峰線に平行＝a の等値線）。沿う座標は along（輪を一周して閉じる）
                float fs = max(fwidth(s), 1e-6);
                float seaCov = 0.0, pxS = 0.0;
                {
                    float lam = max(_SeaLines.x, 0.05);
                    float ss = s + _SeaLines.z * lam * sin(6.2831853 * along / max(_SeaLines2.x, 0.1) + 0.013 * s);
                    seaCov = _SeaLines.w > 0.5 ? Lines(ss, lam, _SeaLines.y, along + 0.71 * s, _SeaLines2.y, _SeaLines2.z, fs, pxS) : 0.0;
                    seaCov *= FadePx(pxS);
                    // 近い所の細い溝の段（主の溝の周期が画面で大きい所。目の近くの平らな面を割る）
                    float lamF = lam * _SeaFine.x;
                    float pxSF;
                    float fineS = Lines(ss + 0.5 * lamF, lamF, _SeaFine.y, along * 1.7 + 0.37 * s, _SeaLines2.y * 0.5, 0.7, fs, pxSF);
                    fineS *= saturate((pxS - _SeaFine.z) / max(_SeaFine.w - _SeaFine.z, 1.0)) * FadePx(pxSF);
                    seaCov = max(seaCov, fineS);
                    // 目のすぐ近く（座席の船の脇の水）では 2 段目の細い溝（主の 1/16）を足す
                    float lamF2 = lam * _SeaFine.x * 0.25;
                    float pxSF2;
                    float fineS2 = Lines(ss + 0.31 * lamF2, lamF2, _SeaFine.y * 0.9, along * 4.3 + 1.1 * s, _SeaLines2.y * 0.2, 0.7, fs, pxSF2);
                    fineS2 *= saturate((pxS - 4.0 * _SeaFine.z) / max(4.0 * (_SeaFine.w - _SeaFine.z), 1.0)) * FadePx(pxSF2);
                    seaCov = max(seaCov, fineS2);
                    seaCov *= saturate((s - _SeaLines2.w) / 0.6);
                    float fa = max(fwidth(aSt), 1e-6);
                    float lamA = max(_SeaLinesFar.x, 0.05);
                    float aa2 = aSt + _SeaLines.z * lamA * sin(6.2831853 * s / max(_SeaLines2.x * 1.7, 0.1));
                    float pxA;
                    float farCov = Lines(aa2, lamA, _SeaLinesFar.y, s * 0.83 + 0.5 * aSt, _SeaLines2.y * 1.4, _SeaLines2.z, fa, pxA) * FadePx(pxA);
                    float kFar = smoothstep(_SeaLinesFar.z, _SeaLinesFar.w, s);
                    seaCov = lerp(seaCov, farCov, kFar);
                }

                // ---- 谷の縁の段（谷の側＝継ぎ目〜縁の頂：藍中の地に藍濃の溝。頂に藍の線と泡の点）
                float growT = saturate((_DS27Tau - _TroughGrow.x) / max(_TroughGrow.y - _TroughGrow.x, 1e-3));
                float rq = rimq + _TroughRim.y * sin(6.2831853 * along / max(_TroughRim.z, 0.1) + 1.3 * sin(6.2831853 * along / 23.0));
                float frq = max(fwidth(rq), 1e-6);
                // 段の範囲：谷の側（継ぎ目〜頂。τ で頂から谷の底へ広がる）と、頂の外の唇の帯（_TroughLip.x m。座席のように谷の外から見ると、谷の側の面は向こうを向いて見えないので、
                // 頂の外の唇の帯と頂の線で縁を読ませる）
                // 修正02：谷の縁の重み tw に応じて帯の幅を細らせる（端で 0。作る部・修正01 は tw 0.5 で切り、真上で帯の端が真っ直ぐに切れた）
                float taperT = smoothstep(_TroughTaper.x, _TroughTaper.y, tw);
                float zT = min((_TroughLip.x * growT * taperT - rq) / frq, (rq + _TroughRim.x * growT * taperT) / frq);
                zT = min(zT, Px(tw - _TroughTaper.x));
                float troughCov = (_TroughRim.w > 0.5 && growT > 0.0) ? saturate(0.5 + zT / aa) : 0.0;
                float depth01 = saturate(-rq / max(_TroughRim.x, 0.1));       // 唇の帯（rq > 0）は 0＝細い溝
                float pxT;
                float troughGroove = Lines(rq + 0.12 * sin(6.2831853 * along / 6.1), max(_TroughLines.x, 0.05), lerp(_TroughLines.y, _TroughLines.z, depth01), along, _TroughLines.w, 0.85, frq, pxT);
                troughGroove = lerp(0.35, troughGroove, FadePx(pxT));
                float rimLine = (_TroughRim.w > 0.5 && _TroughLinePx > 0.0) ? saturate(0.5 * _TroughLinePx + 0.5 - abs(rq / frq)) * saturate((tw - 0.4) / 0.2) * saturate(growT * 4.0) : 0.0;
                float rimFoam = 0.0;
                float lipQ = rq - _TroughLip.x * growT;                    // 唇の帯の外の端からの距離（泡の点はその外）
                float fsd = max(max(fwidth(along), frq), 1e-6);
                [branch] if (_TroughRim.w > 0.5 && tw > 0.3 && lipQ > -0.15 && lipQ < _TroughFoam.w && growT > 0.5)
                {
                    float cellD = max(_TroughFoam.x, 0.05);
                    float2 pd = float2(along, lipQ * 2.0) / cellD + 0.5;
                    float2 cd = floor(pd);
                    float3 hd = Hash3(cd + 73.0);
                    float2 cen = cd + 0.2 + 0.6 * hd.yz;
                    float rr = _TroughFoam.y * (0.5 + 0.8 * frac(hd.x * 5.31));
                    float2 dv = (pd - cen) * cellD; dv.y *= 0.5;
                    float d2 = length(dv);
                    float probD = _TroughFoam.z * saturate(1.0 - max(lipQ, 0.0) / max(_TroughFoam.w, 1e-3)) * saturate((tw - 0.3) / 0.4);
                    float on = frac(hd.x * 2.19 + 0.37) < probD ? 1.0 : 0.0;
                    rimFoam = on * saturate(0.5 + (rr - d2) / fsd) * saturate(rr / fsd - 0.7);
                }

                // ---- 合わせる：波の系の白は大きい方、溝は重みで混ぜる
                float wFeat = saturate(max(saturate(hR * hfR / 1.0) * saturate(wRraw * 3.0), wS));
                float wsum = max(wRraw + wS, 1e-4);
                float featGroove = (R.groove * wRraw + Sm.groove * wS) / wsum;
                float lineCovBody = lerp(seaCov, featGroove, wFeat);
                float whiteCov = max(R.whiteCov, Sm.whiteCov);
                float mizCov = R.whiteCov >= Sm.whiteCov ? R.mizCov : Sm.mizCov;
                float dotCov = max(max(R.dotOut * (1.0 - Sm.whiteCov), Sm.dotOut * (1.0 - R.whiteCov)), max(R.bodyDot, Sm.bodyDot) * (1.0 - troughCov));
                dotCov = max(dotCov, rimFoam * (1.0 - wFeat));

                // ---- ID・診断
                if (_PL29Diag > 6.5 && _PL29Diag < 7.5) return float4(troughCov >= 0.5 ? float3(1, 0, 1) : float3(0, 0, 0), 1);
                if (_PL29Diag > 7.5 && _PL29Diag < 8.5) return float4(saturate(wR), saturate(wS), saturate(tw), 1);
                if (_PL29Diag > 10.5) return float4(R.dg.x > 0 ? 1 : 0, R.dg.y > 0 ? 1 : 0, R.dg.z > 0 ? 1 : 0, 1);   // 11（修正02 の点検）：稜の系の 今の高さの比の条件・育ちの門・q の上限
                if (_PL29Diag > 9.5) return float4(saturate(seaCov), saturate(featGroove), saturate(wFeat), 1);   // 10：海の溝・波の溝・波の溝の重み
                if (_PL29Diag > 8.5) return float4(saturate((y / max(hR, 0.5) - 0.6) / 0.4), saturate(qR / 6.0 + 0.5), saturate(wsh), 1);   // 9：稜の系の今の高さの比・q・肩の稜の重み
                if (_AF28IdMode > 0.5 || _PL29Diag > 0.5)
                {
                    int cls;
                    if (whiteCov >= 0.5) cls = mizCov >= 0.5 ? 1 : 0;
                    else if (dotCov >= 0.5) cls = 0;
                    else if (troughCov >= 0.5) cls = troughGroove >= 0.5 ? 3 : 2;
                    else cls = lineCovBody >= 0.5 ? 2 : 3;
                    return float4(IdColour(cls), 1);
                }

                // ---- 色
                float3 body = lerp(_AiDark.rgb, _AiMid.rgb, lineCovBody);
                float3 trough = lerp(_AiMid.rgb, _AiDark.rgb, troughGroove);
                body = lerp(body, trough, troughCov);
                body = lerp(body, _White.rgb, dotCov);
                float3 wcol = lerp(_White.rgb, _Mizuiro.rgb, mizCov);
                float3 col = lerp(body, wcol, whiteCov);
                float3 V = normalize(_WorldSpaceCameraPos - i.wp);
                float nv = abs(dot(normalize(i.n), V));
                float graze = saturate((nv - _EdgeGrazing.x) / max(_EdgeGrazing.y - _EdgeGrazing.x, 1e-3));
                if (_EdgeLinePx > 0.0)
                {
                    float lr = saturate(0.5 * _EdgeLinePx + 0.5 - abs(R.zW * aa)) * (1.0 - Sm.whiteCov);
                    float ls = saturate(0.5 * _EdgeLinePx + 0.5 - abs(Sm.zW * aa)) * (1.0 - R.whiteCov);
                    col = lerp(col, _LineCol.rgb, max(lr, ls) * graze);
                }
                col = lerp(col, _LineCol.rgb, rimLine * graze * (1.0 - whiteCov));
                return float4(col, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
