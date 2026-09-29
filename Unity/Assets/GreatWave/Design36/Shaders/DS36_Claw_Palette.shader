// 設計36：爪の層の限定色（白・淡い水色・藍中・藍濃）。設計34 の爪の結合メッシュ（DS34ClawPlayer）に、DS36ClawPalette が 2 つの UV を足す：
//   TEXCOORD0 = t*（t = 12 s、コマ 360）の爪の頂点を原画視点のカメラで写した画面の位置（ビューポート 0〜1、y は上向き）
//   TEXCOORD1 = (x) 爪の一覧の色区の影の色（0 白、1 淡い水色、2 藍中、3 藍濃。設計32 の爪の領域の中の原画の色区で、白でない最多のもの。計画 §6 の定義）
// 色の決め方（段は 4 色 ＋ 藍の線は設計38）：
//   ・t* の原画視点でカメラを向いていた面（下の判定）＝原画の色区の符号付き距離の表（1920×1080、表示フレーム）を投影の位置で引き、
//     主役波の DS27 NPR White と同じ最大の色区＋約 1 画素のアンチエイリアスで塗る（美術優先28 の投影と同じ考え。t* の原画視点では原画の色区と同じ色になる）。
//   ・t* にカメラに背を向けていた面：部分メッシュ 0（上面と根元の白の円）は白、部分メッシュ 1（縁の側面と下面）は爪の一覧の色区の影の色（_FaceKind で分ける）。
//   t* の向きの判定：画面の位置の微分から「今の画面 → t* の画面」の写像の向き o = sign(det J_P)·sign(det J_S) を求め、
//   今の面の表裏（SV_IsFrontFace）と比べる：t* に表 ⇔ (o > 0) == 今表（t* の原画視点では J_P = J_S なので、今表の面がそのまま t* に表）。
//   _FaceFlip = 1 で判定を反転（描画の向きの規約の確認用）。
// 検査の表示（大域）：_AF28IdMode = 1・_DS27DebugMode = 2 で色区 ID（白 赤、淡い水色 緑、藍中 青、藍濃 黄。主役波の IdColour と同じ）。
//   _DS34ClawDiag = 1 で確認用のマゼンタ。_DS36ClawFaceDiag = 1 で t* の向き（表 = 緑、裏 = 赤。確認用）。
// 立体視（SPI）：標準のマクロ。HMD 実機は未検証。
Shader "GreatWave/Design36/DS36 Claw Palette"
{
    Properties
    {
        _LabelSdf ("原画の色区の符号付き距離（1920×1080 RGBA8、下の行から）", 2D) = "gray" {}
        _White ("白・生成り", Color) = (0.97255, 0.95294, 0.87451, 1)
        _Mizuiro ("淡い水色", Color) = (0.77647, 0.84314, 0.79608, 1)
        _AiMid ("藍中", Color) = (0.17255, 0.41176, 0.57647, 1)
        _AiDark ("藍濃", Color) = (0.13725, 0.25098, 0.38039, 1)
        _EncodeLevels ("1 px あたりの段", Float) = 8
        _LabelPx ("表の画素数（幅, 高さ）", Vector) = (1920, 1080, 0, 0)
        _AAScale ("アンチエイリアスの幅（画素）", Float) = 1
        _FaceKind ("部分メッシュ（0 上面・白の円、1 縁の側面と下面）", Float) = 0
        _FaceFlip ("t* の向きの判定の反転（奥行きの表がないときだけ使う）", Float) = 0
        _TDepth ("t* の見え方の表（原画視点の目の奥行き、R32）", 2D) = "black" {}
        _TDepthFlip ("表の v の上下の反転", Float) = 0
        _TDepthPx ("表の画素数（0 で表を使わない）", Vector) = (0, 0, 0, 0)
        _TDepthEps ("奥行きの許し（絶対 m, 相対）", Vector) = (0.02, 0.0005, 0, 0)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "DS36ClawPalette"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            ZTest LEqual
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            sampler2D _LabelSdf, _TDepth;
            float4 _White, _Mizuiro, _AiMid, _AiDark, _LabelPx, _TDepthPx, _TDepthEps;
            float _EncodeLevels, _AAScale, _FaceKind, _FaceFlip, _TDepthFlip;
            float _AF28IdMode;          // 大域
            float _DS27DebugMode;       // 大域
            float _DS34ClawDiag;        // 大域
            float _DS36ClawFaceDiag;    // 大域

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uvP : TEXCOORD0;
                float2 shadow : TEXCOORD1;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uvP : TEXCOORD0;
                float4 scr : TEXCOORD1;
                nointerpolation float shadow : TEXCOORD2;
                float zT : TEXCOORD3;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uvP = v.uvP;
                o.scr = ComputeScreenPos(o.pos);
                o.shadow = v.shadow.x;
                o.zT = v.shadow.y;
                return o;
            }

            float3 Palette(int k)
            {
                return k == 0 ? _White.rgb : (k == 1 ? _Mizuiro.rgb : (k == 2 ? _AiMid.rgb : _AiDark.rgb));
            }

            float3 IdColour(int k)
            {
                return k == 0 ? float3(1, 0, 0) : (k == 1 ? float3(0, 1, 0) : (k == 2 ? float3(0, 0, 1) : float3(1, 1, 0)));
            }

            float4 frag(v2f i, bool front : SV_IsFrontFace) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                if (_DS34ClawDiag > 0.5) return float4(1, 0, 1, 1);
                // t* の向き
                float2 uvS = i.scr.xy / max(i.scr.w, 1e-6);
                float2 px = ddx(i.uvP), py = ddy(i.uvP), sx = ddx(uvS), sy = ddy(uvS);
                float detP = px.x * py.y - px.y * py.x;
                float detS = sx.x * sy.y - sx.y * sy.x;
                bool o = detP * detS > 0;
                bool frontT = (o == front);
                if (_FaceFlip > 0.5) frontT = !frontT;
                // t* に原画のカメラから見えるか（奥行きの表）：この断片の t* の奥行き zT と、表の最も手前の奥行きを比べる。
                // 許し = 絶対 + 相対·zT + 表の 1 画素ぶんの奥行きの傾き × 1.5（連鎖律で uvP あたりの zT の傾きを求める）。
                // 表が空（1e8 以上。t* の爪の縁の半画素）なら見えるとする
                if (_TDepthPx.x > 0.5)
                {
                    float2 uvD = float2(i.uvP.x, _TDepthFlip > 0.5 ? 1.0 - i.uvP.y : i.uvP.y);
                    float dT = tex2Dlod(_TDepth, float4(uvD, 0, 0)).r;
                    float dzx = ddx(i.zT), dzy = ddy(i.zT);
                    // [dzx dzy] = g · J、J = [[px.x, py.x], [px.y, py.y]] → g = [dzx dzy] · J⁻¹
                    float dj = px.x * py.y - py.x * px.y;
                    float2 g = abs(dj) > 1e-12 ? float2(dzx * py.y - dzy * px.y, -dzx * py.x + dzy * px.x) / dj : float2(0, 0);
                    float slope = length(g / _TDepthPx.xy) * 1.5;
                    float eps = _TDepthEps.x + _TDepthEps.y * i.zT + min(slope, 1.0);
                    frontT = dT > 1e8 || i.zT <= dT + eps;
                }
                if (_DS36ClawFaceDiag > 0.5) return frontT ? float4(0, 1, 0, 1) : float4(1, 0, 0, 1);

                int a, b;
                float t;
                if (frontT)
                {
                    float4 d = (tex2D(_LabelSdf, i.uvP) * 255.0 - 127.5) / _EncodeLevels;
                    float s[4] = { d.x, d.y, d.z, d.w };
                    a = 0;
                    [unroll] for (int k = 1; k < 4; k++) if (s[k] > s[a]) a = k;
                    b = a == 0 ? 1 : 0;
                    [unroll] for (int m = 0; m < 4; m++) if (m != a && s[m] > s[b]) b = m;
                    // 距離は表の画素（表示の px）。今の画面の 1 画素あたりの変化で約 1 画素のアンチエイリアス
                    float e = 0.5 * (s[a] - s[b]);
                    float w = max(fwidth(e), 1e-4) * _AAScale;
                    t = saturate(0.5 + e / w);
                }
                else
                {
                    a = _FaceKind < 0.5 ? 0 : (int)round(i.shadow);
                    b = a; t = 1;
                }
                bool idm = _AF28IdMode > 0.5 || (_DS27DebugMode > 1.5 && _DS27DebugMode < 2.5);
                if (idm) return float4(IdColour(a), 1);
                return float4(lerp(Palette(b), Palette(a), t), 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
