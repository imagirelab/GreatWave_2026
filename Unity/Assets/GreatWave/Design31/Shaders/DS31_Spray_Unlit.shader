// 設計31：飛沫 v0（と確認用の印）の、光を使わない不透明の小球。1 回の DrawMeshInstancedProcedural で 2〜3 千個を描く。
// 球の中心と半径は StructuredBuffer<float4> _DS31P（xyz = ワールドの位置 m、w = 半径 m。半径 0 の球は点につぶれて描かれない）。
// 色は平塗りの 1 色（既定は主役波の白・生成り、DS27 NPR White の _White と同じ値）。縁の暗い線・光る縁・四角い下地は作らない（バックログ 152）。
// 立体視（SPI）：Unity は両眼のために個数を 2 倍にして呼ぶので、SV_InstanceID の最下位の 1 bit を目、残りを球の番号にする
// （UnityInstancing.cginc の UNITY_SETUP_INSTANCE_ID と同じ分け方）。コンパイルだけを確かめた（HMD 実機は未検証）。
Shader "GreatWave/Design31/DS31 Spray Unlit"
{
    Properties
    {
        _Colour ("色（平塗り）", Color) = (0.97255, 0.95294, 0.87451, 1)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "DS31SprayUnlit"
            Tags { "LightMode"="ForwardBase" }
            Cull Back
            ZWrite On
            ZTest LEqual
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            StructuredBuffer<float4> _DS31P;
            float4 _Colour;
            float _AF28IdMode;   // 大域。ID の描画では白の ID（赤）で出す（採取では飛沫を ID に入れないので、ふつうは使わない）

            struct appdata
            {
                float4 vertex : POSITION;
                uint iid : SV_InstanceID;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                uint id = v.iid;
            #if defined(UNITY_STEREO_INSTANCING_ENABLED)
                unity_StereoEyeIndex = v.iid & 0x01;
                id = v.iid >> 1;
            #endif
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float4 p = _DS31P[id];
                float3 w = p.xyz + v.vertex.xyz * p.w;
                o.pos = UnityWorldToClipPos(w);
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                if (_AF28IdMode > 0.5) return float4(1, 0, 0, 1);
                return float4(_Colour.rgb, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
