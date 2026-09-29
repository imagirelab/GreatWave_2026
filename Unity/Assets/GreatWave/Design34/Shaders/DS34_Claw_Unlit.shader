// 設計34：爪の層（設計33 の帯のメッシュを 1 つの結合メッシュにしたもの）の、光を使わない不透明の平塗り。
// 部分メッシュ 0 が白（上面と根元の白の円）、1 が淡い水色（縁の側面と下面）。色は主役波の DS27 NPR White の _White・_Mizuiro と同じ値。
// 検査の表示（大域）：
//   _AF28IdMode = 1（美術優先28 の色区 ID）と _DS27DebugMode = 2（終態の色区 ID）では、白を赤 (1,0,0)、淡い水色を緑 (0,1,0) で出す
//   （主役波のシェーダーの IdColour と同じ。爪は t* まで色が変わらないので、表示と終態は同じ）。
//   _DS34ClawDiag = 1 では、確認用のマゼンタ (1,0,1) の 1 色で出す（遮蔽と Mock の両眼で爪の画素を数えるため。作品には使わない）。
// 立体視（SPI）：UNITY_VERTEX_INPUT_INSTANCE_ID・UNITY_VERTEX_OUTPUT_STEREO の標準の形。コンパイルだけを確かめる（HMD 実機は未検証）。
Shader "GreatWave/Design34/DS34 Claw Unlit"
{
    Properties
    {
        _Colour ("色（平塗り）", Color) = (0.97255, 0.95294, 0.87451, 1)
        _IdClass ("色区の番号（0 白、1 淡い水色）", Float) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "DS34ClawUnlit"
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

            float4 _Colour;
            float _IdClass;
            float _AF28IdMode;      // 大域
            float _DS27DebugMode;   // 大域
            float _DS34ClawDiag;    // 大域

            struct appdata
            {
                float4 vertex : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                // 頂点はワールドの m（設計33 の表）。オブジェクトは原点・回転なし・倍率 1 に置く
                o.pos = UnityObjectToClipPos(v.vertex);
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                if (_DS34ClawDiag > 0.5) return float4(1, 0, 1, 1);
                bool idm = _AF28IdMode > 0.5 || (_DS27DebugMode > 1.5 && _DS27DebugMode < 2.5);
                if (idm) return _IdClass < 0.5 ? float4(1, 0, 0, 1) : float4(0, 1, 0, 1);
                return float4(_Colour.rgb, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
