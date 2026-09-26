// 番号31：主役波の NPR シェーダー（番号30 の AF30 NPR Keypose と同じ位置の補間と色の式）に、白の時間場 T_white を加えたもの。
// 白の時間場（Tools/GWWaveGen/af31_white.py が書き、AF31WhiteField が大域の値で渡す）：頂点ごとの T_white（秒、RFloat、列 × 行）を
// SV_VertexID で Load し、三角形の中は線形に補間する。終態（28修正01 の焼き込み）の色区が白の所だけ、時刻 _AF31Time < T_white のあいだ
// 『白の前の色』（_PreWhiteClass、既定は藍中）で塗る。白でない色区（白の中の藍・淡い水色を含む）は時刻によらず終態の色のまま
// （一時的な白で塗りつぶさない）。t ≥ T_white では番号30 と同じ色になる。白の波面のアンチエイリアスは fwidth(T_white) で約 1 画素。
// 時刻が _AF31WhiteEnd（終態の白が全部そろう時刻、t* の 0.2 s 前）以後は白の時間場を見ない（輪郭の縁の微分の乱れで t* の色が変わらないように）。
// 色区は UV3（格子の添字だけで決まる）に貼り付いているので、縞は同じ水面とともに動く。
// 検査の表示（大域）：_AF28IdMode = 1 で表示している色区の ID（白の時間場を入れた後）、_AF31DebugMode = 2 で終態の色区の ID、
// 3 で焼き込みの UV3 のテクセル番号（R = U の上位 8 bit、G = U の下位 4 bit × 16 + V の上位 4 bit、B = V の下位 8 bit）、4 で白の到着時刻の色。
// SPI の立体視マクロは Sampling19Surface.cginc と同じ形（番号30 の AF30Keypose.cginc）。HMD 実機は未検証。
Shader "GreatWave/ArtFirst/AF31 NPR White"
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
            Name "AF31NPRWhite"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "AF30Keypose.cginc"

            sampler2D _SdfTex;
            float4 _White, _Mizuiro, _AiMid, _AiDark;
            float _EncodeLevels, _AAScale, _FlatClass, _PreWhiteClass;
            float _AF28IdMode;          // 大域。1 で表示している色区の ID
            Texture2D<float> _AF31WhiteTex;   // 大域。頂点ごとの T_white（秒）
            float _AF31GridNU;          // 大域。格子の列の数（400）
            float _AF31Time;            // 大域。GWClock の時刻（秒）
            float _AF31WhiteEnabled;    // 大域。0 で白の時間場を使わない（番号30 と同じ色）
            float _AF31WhiteEnd;        // 大域。終態の白が全部そろう時刻（秒）。これ以後は白の時間場を見ない（t* の色を終態と一致させる）
            float _AF31DebugMode;       // 大域。2 終態の色区の ID、3 UV3 のテクセル番号、4 白の到着時刻

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                float2 uv : TEXCOORD2;
                uint vid : SV_VertexID;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
                float tw : TEXCOORD1;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                AF30Deform(v.vid, v.vertex, v.normal);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                uint nu = (uint)(_AF31GridNU + 0.5);
                o.tw = nu > 0 ? _AF31WhiteTex.Load(int3((int)(v.vid % nu), (int)(v.vid / nu), 0)) : 0.0;
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

            // 白の到着時刻の色（2 s 青 → 7 s 緑 → 12 s 赤）
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
                // 白の時間場：g > 0 で白が届いている。波面のアンチエイリアスは fwidth(T_white) で約 1 画素
                bool on = _AF31WhiteEnabled > 0.5;
                float g = _AF31Time - i.tw;
                float fw = max(fwidth(i.tw), 1e-5) * _AAScale;
                float fwhite = (on && _AF31Time < _AF31WhiteEnd) ? saturate(0.5 + g / fw) : 1.0;
                int pre = (int)round(_PreWhiteClass);
                if (_AF31DebugMode > 1.5 && _AF31DebugMode < 2.5) return float4(IdColour(a), 1);
                if (_AF28IdMode > 0.5) return float4(IdColour((a == 0 && on && _AF31Time < _AF31WhiteEnd && g < 0) ? pre : a), 1);
                if (_AF31DebugMode > 2.5 && _AF31DebugMode < 3.5)
                {
                    uint U = (uint)clamp(floor(i.uv.x * 4096.0), 0.0, 4095.0);
                    uint V = (uint)clamp(floor(i.uv.y * 4096.0), 0.0, 4095.0);
                    return float4((U >> 4) / 255.0, (((U & 15u) << 4) | (V >> 8)) / 255.0, (V & 255u) / 255.0, 1);
                }
                if (_AF31DebugMode > 3.5)
                {
                    float3 base = Palette(a) * 0.35 + 0.35;
                    return float4(a == 0 ? Ramp((i.tw - 2.0) / 10.0) : base, 1);
                }
                // fwhite = 1 のときは白をそのまま使う（lerp の丸めで番号30 の色から 1 ulp ずれないように）
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
