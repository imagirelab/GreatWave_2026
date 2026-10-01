// 仕上げ29 修正の回（Q28）：立体の爪（設計33 の帯、設計34 の結合メッシュ）の、視点によらない陰の段。
// 設計34 の爪は白（上面と根元）・淡い水色（縁の側面と下面）の 2 色の平塗りで、主役波の白い頂の上では白に白が重なって読めなかった。
// ここでは帯の輪の向き（頂点の UV2.x = sin φ。φ 90° が上＝シートの法線の向き、φ 270° が下面。PL29ClawShade が頂点の並びから入れる）で段を付ける：
//   sin φ > _Steps.x → 白（上面）、_Steps.y < sin φ ≤ _Steps.x → 淡い水色（縁の側面）、sin φ ≤ _Steps.y → 藍中（下面＝影の側）。
// 段は帯の頂点に付いた値だけで決まり、視点・原画カメラでは決まらない（彫刻の爪の、白い上面と暗い下面の陰影を平塗りの段に置き換えたもの）。
// UV2.y は帯の根元 0 → 先 1 の位置（記録のみ。色には使わない）。
// 検査の表示（大域）：_AF28IdMode = 1 と _DS27DebugMode = 2 では白 (1,0,0)・淡い水色 (0,1,0)・藍中 (0,0,1)（主役波の IdColour と同じ約束）、
//   _DS34ClawDiag = 1 ではマゼンタ (1,0,1)（設計34 と同じ）。
// 立体視（SPI）：設計34 と同じ標準の形（HMD 実機は未検証）。
Shader "GreatWave/Polish29/PL29 Claw Shade"
{
    Properties
    {
        _White ("白・生成り", Color) = (0.97255, 0.95294, 0.87451, 1)
        _Mizuiro ("淡い水色", Color) = (0.77647, 0.84314, 0.79608, 1)
        _AiMid ("藍中", Color) = (0.17255, 0.41176, 0.57647, 1)
        _Steps ("段の境（x 白と淡い水色の sin φ、y 淡い水色と藍中の sin φ）", Vector) = (0.30, -0.45, 0, 0)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "PL29ClawShade"
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

            float4 _White, _Mizuiro, _AiMid, _Steps;
            float _AF28IdMode;      // 大域
            float _DS27DebugMode;   // 大域
            float _DS34ClawDiag;    // 大域

            struct appdata
            {
                float4 vertex : POSITION;
                float2 att : TEXCOORD2;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 att : TEXCOORD0;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);   // 頂点はワールドの m（設計33 の表）。物は原点・回転なし・倍率 1
                o.att = v.att;
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                if (_DS34ClawDiag > 0.5) return float4(1, 0, 1, 1);
                float up = i.att.x;
                int k = up > _Steps.x ? 0 : (up > _Steps.y ? 1 : 2);
                bool idm = _AF28IdMode > 0.5 || (_DS27DebugMode > 1.5 && _DS27DebugMode < 2.5);
                if (idm) return k == 0 ? float4(1, 0, 0, 1) : (k == 1 ? float4(0, 1, 0, 1) : float4(0, 0, 1, 1));
                float fw = max(fwidth(up), 1e-4);
                float w0 = saturate((up - _Steps.x) / fw + 0.5);
                float w2 = saturate((_Steps.y - up) / fw + 0.5);
                float3 col = lerp(lerp(_Mizuiro.rgb, _White.rgb, w0), _AiMid.rgb, w2);
                return float4(col, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
