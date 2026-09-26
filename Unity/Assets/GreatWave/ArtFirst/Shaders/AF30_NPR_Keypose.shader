// 番号30：主役波の NPR シェーダー（番号28 の AF28 NPR v1 と同じ色の決め方）に、形成の keypose の頂点補間を加えたもの。
// 位置は AF30Keypose.cginc（keypose テクスチャ 4 層の Catmull-Rom）で決め、色は番号28修正01 の焼き込み（UV3 = TEXCOORD2）を読む。
// UV3 は格子の添字だけで決まる（AF28NprWave.ApplyWarp）ので、色区は動く水面に貼り付いたまま動く（UV が変わらない）。
// 色区の符号付き距離・調色板・アンチエイリアス・ID 表示（大域の _AF28IdMode）は AF28_NPR.shader と同じ式（番号28 のシェーダーは変えない）。
// SPI の立体視マクロは Sampling19Surface.cginc と同じ形。立体視での描画は番号32 の Mock と同じ方法でしか確かめていない（HMD 実機は未検証）。
Shader "GreatWave/ArtFirst/AF30 NPR Keypose"
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
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "AF30NPR"
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
            float _EncodeLevels, _AAScale, _FlatClass;
            float _AF28IdMode;   // 大域（Shader.SetGlobalFloat）。1 で ID 表示（番号28 と同じ）

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
                if (_AF28IdMode > 0.5) return float4(IdColour(a), 1);
                float e = 0.5 * (s[a] - s[b]);
                float w = max(fwidth(e), 1e-4) * _AAScale;
                float t = saturate(0.5 + e / w);
                return float4(lerp(Palette(b), Palette(a), t), 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
