// 設計39：DS27 keypose のシート（主役波・周りの海 near・far）に重ねる紙の地（①）・摺りのむら（②）。面に固定（UV 相当）。
//   位置：作品の面と同じ DS27Keypose.cginc の関数と同じ MaterialPropertyBlock の値（DS30SheetPlayer が面のレンダラーに入れる。この材質は
//         同じレンダラーの 2 つ目以降の材質として描くので、同じ値を読む）。
//   模様の座標：t*（体験の時刻 12 s）のその頂点のワールドの位置（_DS39RestSlices・_DS39RestWeights の 4 層の重み付きの和 ＋ _DS39RestOrigin）。
//         面の点ごとに決まり、形成の間も頭が動いても、模様はその面の点に付いたまま（画面の座標は使わない）。
//   描き方：掛け算（Blend DstColor SrcColor）、深度は書かない、LEqual と Offset −1（同じ面の上だけに重なる）。両面（面のシェーダーと同じ Cull Off）。
//   切った状態（材質を外す）では、作品の描画は設計38 と同じ（評価と原画比較は切って行う）。
Shader "GreatWave/Design39/DS39 Paper Keypose"
{
    Properties
    {
        _DS39Mode ("種類（0 紙の地・1 摺りのむら）", Float) = 0
        _DS39Amp ("振幅（係数 1 ± 振幅）", Float) = 0.03
        _DS39RestSlices ("t* の 4 層", Vector) = (0, 0, 0, 0)
        _DS39RestWeights ("t* の 4 層の重み", Vector) = (1, 0, 0, 0)
        _DS39RestOrigin ("t* の枠の原点（ワールド）", Vector) = (0, 0, 0, 0)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry+20" }
        Pass
        {
            Name "DS39PAPER"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite Off
            ZTest LEqual
            Offset -1, -1
            Blend DstColor SrcColor
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile _ DS27_POS_LO
            #include "../../Design27/Shaders/DS27Keypose.cginc"
            #include "DS39PaperCommon.cginc"

            float _DS39Mode, _DS39Amp;
            float4 _DS39RestSlices, _DS39RestWeights, _DS39RestOrigin;

            struct appdata
            {
                float4 vertex : POSITION;
                uint vid : SV_VertexID;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 rest : TEXCOORD0;
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
                float3 rest = w;
                if (_DS27Enabled > 0.5)
                {
                    rest = _DS39RestOrigin.xyz
                         + _DS39RestWeights.x * DS27LoadLocal(v.vid, _DS39RestSlices.x) + _DS39RestWeights.y * DS27LoadLocal(v.vid, _DS39RestSlices.y)
                         + _DS39RestWeights.z * DS27LoadLocal(v.vid, _DS39RestSlices.z) + _DS39RestWeights.w * DS27LoadLocal(v.vid, _DS39RestSlices.w);
                }
                o.rest = rest;
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                return DS39Out(i.rest, _DS39Mode, _DS39Amp);
            }
            ENDCG
        }
    }
}
