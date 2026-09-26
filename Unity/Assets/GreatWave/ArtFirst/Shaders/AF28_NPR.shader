// 番号28：主役波の NPR シェーダー v1（無照明の調色板の平塗り）。
// 色は符号付き距離テクスチャ（AF28ProjectionBaker が t* の PaintingCam v1 から投影で焼いたもの）から決める。
// テクスチャの座標は焼き込み用の UV（UV3 = TEXCOORD2。UV0 を列・行ごとに単調に引き伸ばした u′, v′。AF28NprWave が格子の添字から付ける）。
//   各チャンネル = 色区（R 白、G 淡い水色、B 藍中、A 藍濃）の符号付き距離（表示 px、正が内側）。値 = 127.5 + 8·d（8bit、線形）。
//   画素の色区 = 距離が最大の色区。境の近くは上位 2 つの色区を、距離の差の画面上の変化量（fwidth）で混ぜてアンチエイリアスする。
// 色は番号28第A部の色区の中央値（表示フレームで 3 px 収縮）を 8bit sRGB にした値。Linear 色空間では Unity が Color を線形へ直し、
//   sRGB の描画先へ書くときに sRGB へ戻すので、平らな所の 8bit 値は入力と一致する（番号23 の較正門と同じ経路）。
// 照明・影・霧は使わない（ForwardBase でも光を読まない）。
// ID 表示：大域の _AF28IdMode = 1 のとき、色区ごとの ID 色（白 (1,0,0)、淡い水色 (0,1,0)、藍中 (0,0,1)、藍濃 (1,1,0)）をアンチエイリアスなしで出す（評価器用）。
// SPI（Single Pass Instanced）用の立体視マクロは Sampling19Surface.cginc と同じ形で入れた（立体視での描画は確かめていない）。
Shader "GreatWave/ArtFirst/AF28 NPR v1"
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
            Name "AF28NPR"
            Tags { "LightMode"="ForwardBase" }
            // 一枚の水面シートなので両面を描く（唇の下面と内壁も表が空気の側）。
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            sampler2D _SdfTex;
            float4 _White, _Mizuiro, _AiMid, _AiDark;
            float _EncodeLevels, _AAScale, _FlatClass;
            float _AF28IdMode;   // 大域（Shader.SetGlobalFloat）。1 で ID 表示

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD2;
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
                // 上位 2 つの色区
                float s[4] = { d.x, d.y, d.z, d.w };
                int a = 0;
                [unroll] for (int k = 1; k < 4; k++) if (s[k] > s[a]) a = k;
                int b = a == 0 ? 1 : 0;
                [unroll] for (int m = 0; m < 4; m++) if (m != a && s[m] > s[b]) b = m;
                if (_AF28IdMode > 0.5) return float4(IdColour(a), 1);
                // a と b の境までの距離（表示 px。a の内側が正）。画面上の変化量で 1 画素幅のアンチエイリアス
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
