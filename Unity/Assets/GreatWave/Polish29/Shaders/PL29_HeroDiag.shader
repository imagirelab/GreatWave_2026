// 仕上げ29（前の点検）：主役波の面の診断の表示。作品の描画には使わない（PL29Audit が描く間だけ主役波の面の材質を差し替える）。
// 頂点の位置は設計27 の DS27 keypose（DS27Keypose.cginc）のまま。主役波のシートのバッファは DS30SheetPlayer がレンダラーの
// MaterialPropertyBlock で渡すので、材質を差し替えても同じ位置で描ける。精度の層 DS27_POS_LO は大域のキーワード。
// 出力（ARGB32 線形・MSAA なしの RT に書く。アルファ 128/255 が主役波の印。ほかの物は ID の色でアルファ 1）：
//   _PL29Mode = 0：UV3（焼き込みの色区テクスチャを読む座標）をテクセルの番号（4096 × 4096）で 24 bit（u 12 bit・v 12 bit）
//   _PL29Mode = 1：K* の頂点（頂点バッファ＝K*、ワールド）を原画カメラ（_PL29PaintVP、GL の約束）へ投影した x（1920 × 1080 の画素）を 24 bit の固定小数
//   _PL29Mode = 2：同じく y（下から上へ）
//   固定小数は (p + 2048) × 1024 を 0〜2^24−1 に切る（1/1024 画素）。原画カメラの後ろ（w ≤ 0）は 0 にする。
Shader "Hidden/GreatWave/Polish29/PL29 Hero Diag"
{
    Properties
    {
        _PL29Mode ("0 UV3、1 原画の x、2 原画の y", Float) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "PL29HeroDiag"
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

            float _PL29Mode;
            float4x4 _PL29PaintVP;

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
                float3 pp : TEXCOORD1;   // 原画の画素 x, y と、原画カメラの前なら 1
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
                float4 c = mul(_PL29PaintVP, float4(v.vertex.xyz, 1.0));
                float ok = c.w > 1e-4 ? 1.0 : 0.0;
                float2 ndc = c.xy / max(c.w, 1e-4);
                o.pp = float3((ndc.x * 0.5 + 0.5) * 1920.0, (ndc.y * 0.5 + 0.5) * 1080.0, ok);
                return o;
            }

            float3 Enc24(uint x)
            {
                return float3((x >> 16) & 255u, (x >> 8) & 255u, x & 255u) / 255.0;
            }

            uint Fix24(float p)
            {
                float q = (p + 2048.0) * 1024.0;
                return (uint)clamp(round(q), 1.0, 16777215.0);
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                const float marker = 128.0 / 255.0;
                if (_PL29Mode < 0.5)
                {
                    uint u = (uint)clamp(floor(i.uv.x * 4096.0), 0.0, 4095.0);
                    uint v = (uint)clamp(floor(i.uv.y * 4096.0), 0.0, 4095.0);
                    return float4(Enc24((u << 12) | v), marker);
                }
                if (i.pp.z < 0.999) return float4(0, 0, 0, marker);
                float p = _PL29Mode < 1.5 ? i.pp.x : i.pp.y;
                return float4(Enc24(Fix24(p)), marker);
            }
            ENDCG
        }
    }
    Fallback Off
}
