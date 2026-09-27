// 設計27：主役波の NPR シェーダー。美術優先31 の AF31 NPR White（28修正01 の焼き込みの色区、白の時間場）を写して、位置の補間を DS27 keypose
// （DS27Keypose.cginc：不等間隔の節点の Hermite、ワールド = 波の枠の原点 O(τ) ＋ 局所）に、白の時刻を物理の時刻 τ に替えたもの。
// 色区の符号付き距離・調色板・アンチエイリアス・ID 表示（大域の _AF28IdMode）は AF28／AF31 と同じ式（美術優先のシェーダーは変えない）。
// 白の時間場（DS27 パッケージの ds27_twhite_r32f.bin、StructuredBuffer<float> _DS27White）：頂点が白なのは τ ≥ T_white のとき。
// +1e9（1e8 以上）は t* までに白にならない。三角形の中は、頂点の T_white（t* までに白にならない頂点は τ + 1 s に置き換える）を線形に補間し、
// 波面を fwidth で約 1 画素のアンチエイリアスにする（AF31 と同じ）。ただし三角形の 3 頂点がすべて白（T_white ≤ τ）なら白 1、
// 3 頂点がすべて t* まで白にならないなら白 0 とする（AF31 の「_AF31WhiteEnd の後は白の時間場を見ない」に代わる規則。
// t* で終態の白がそろう版では、t* の色が終態（美術優先30 と同じ）になる）。
// 終態の色区が白の所だけ、白が届く前は『白の前の色』（_PreWhiteClass、既定は藍中）で塗る。白でない色区は時刻によらず終態の色のまま。
// 検査の表示（大域）：_AF28IdMode = 1 で表示している色区の ID、_DS27DebugMode = 2 で終態の色区の ID、4 で白の到着時刻の色（τ −10 s 青 → 0 s 赤）。
// SPI の立体視マクロは Sampling19Surface.cginc・AF30 と同じ形。HMD 実機は未検証。
Shader "GreatWave/Design27/DS27 NPR White"
{
    Properties
    {
        _SdfTex ("色区の符号付き距離（UV3、RGBA32 線形）", 2D) = "gray" {}
        _White ("白・生成り", Color) = (0.97255, 0.95294, 0.87451, 1)
        _Mizuiro ("淡い水色", Color) = (0.77647, 0.84314, 0.79608, 1)
        _AiMid ("藍中（バックログの水色の既定）", Color) = (0.17255, 0.41176, 0.57647, 1)
        _AiDark ("藍濃", Color) = (0.13725, 0.25098, 0.38039, 1)
        _EncodeLevels ("1 表示 px あたりの段数", Float) = 8
        _AAScale ("アンチエイリアスの幅（画素）", Float) = 1
        _FlatClass ("平塗りの色区（−1 で距離テクスチャを使う。0 白、1 淡い水色、2 藍中、3 藍濃）", Float) = -1
        _PreWhiteClass ("白の前の色区（1 淡い水色、2 藍中、3 藍濃）", Float) = 2
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "DS27NPRWhite"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "DS27Keypose.cginc"

            sampler2D _SdfTex;
            float4 _White, _Mizuiro, _AiMid, _AiDark;
            float _EncodeLevels, _AAScale, _FlatClass, _PreWhiteClass;
            float _AF28IdMode;          // 大域。1 で表示している色区の ID（美術優先28 と同じ名前）
            float _DS27WhiteEnabled;    // 大域。0 で白の時間場を使わない（終態の色）
            float _DS27DebugMode;       // 大域。2 終態の色区の ID、4 白の到着時刻

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD2;
                uint vid : SV_VertexID;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
                float tw : TEXCOORD1;       // 白の時刻（τ、t* までに白にならない頂点は τ + 1）
                float2 fl : TEXCOORD2;      // x：頂点が白（T_white ≤ τ）なら 1、y：t* までに白にならないなら 1
                float twRaw : TEXCOORD3;    // 白の時刻（到着の図のため。t* までに白にならない頂点は 1e9 のまま）
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
                o.uv = v.uv;
                float T = _DS27Enabled > 0.5 ? _DS27White[v.vid] : -1e6;
                bool never = T >= 1e8;
                o.tw = never ? _DS27Tau + 1.0 : T;
                o.fl = float2(T <= _DS27Tau ? 1.0 : 0.0, never ? 1.0 : 0.0);
                o.twRaw = T;
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

            // 白の到着時刻の色（τ −10 s 青 → −5 s 緑 → 0 s 赤）
            float3 Ramp(float x)
            {
                x = saturate(x);
                float3 c0 = float3(0.19, 0.07, 0.55), c1 = float3(0.10, 0.55, 0.95), c2 = float3(0.20, 0.85, 0.35), c3 = float3(0.98, 0.80, 0.15), c4 = float3(0.85, 0.12, 0.08);
                float y = x * 4.0;
                return y < 1 ? lerp(c0, c1, y) : (y < 2 ? lerp(c1, c2, y - 1) : (y < 3 ? lerp(c2, c3, y - 2) : lerp(c3, c4, y - 3)));
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float4 d;
                if (_FlatClass > -0.5)
                {
                    int f = (int)round(_FlatClass);
                    d = float4(f == 0 ? 16 : -16, f == 1 ? 16 : -16, f == 2 ? 16 : -16, f == 3 ? 16 : -16);
                }
                else
                {
                    d = (tex2D(_SdfTex, i.uv) * 255.0 - 127.5) / _EncodeLevels;
                }
                float s[4] = { d.x, d.y, d.z, d.w };
                int a = 0;
                [unroll] for (int k = 1; k < 4; k++) if (s[k] > s[a]) a = k;
                int b = a == 0 ? 1 : 0;
                [unroll] for (int m = 0; m < 4; m++) if (m != a && s[m] > s[b]) b = m;
                float e = 0.5 * (s[a] - s[b]);
                float w = max(fwidth(e), 1e-4) * _AAScale;
                float t = saturate(0.5 + e / w);
                // 白の時間場：g > 0 で白が届いている。波面のアンチエイリアスは fwidth(tw) で約 1 画素
                float g = _DS27Tau - i.tw;
                float fw = max(fwidth(i.tw), 1e-5) * _AAScale;
                float fwhite = saturate(0.5 + g / fw);
                if (i.fl.x > 0.999) fwhite = 1.0;      // 3 頂点とも白が届いている
                if (i.fl.y > 0.999) fwhite = 0.0;      // 3 頂点とも t* までに白にならない
                if (_DS27WhiteEnabled < 0.5 || _DS27Enabled < 0.5) fwhite = 1.0;
                int pre = (int)round(_PreWhiteClass);
                if (_DS27DebugMode > 1.5 && _DS27DebugMode < 2.5) return float4(IdColour(a), 1);
                if (_AF28IdMode > 0.5) return float4(IdColour((a == 0 && fwhite < 0.5) ? pre : a), 1);
                if (_DS27DebugMode > 3.5)
                {
                    float3 base = Palette(a) * 0.35 + 0.35;
                    return float4(a == 0 ? (i.twRaw >= 1e8 ? float3(0.5, 0.5, 0.5) : Ramp((i.twRaw + 10.0) / 10.0)) : base, 1);
                }
                // fwhite = 1 のときは白をそのまま使う（lerp の丸めで終態の色から 1 ulp ずれないように。AF31 と同じ）
                float3 wcol = fwhite >= 1.0 ? _White.rgb : lerp(Palette(pre), _White.rgb, fwhite);
                float3 ca = a == 0 ? wcol : Palette(a);
                float3 cb = b == 0 ? wcol : Palette(b);
                return float4(lerp(cb, ca, t), 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
