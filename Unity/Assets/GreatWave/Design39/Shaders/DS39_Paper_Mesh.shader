// 設計39：keypose でないメッシュ（富士・船・平らな海・継ぎ目の幕・空のドームなど）に重ねる紙の地（①）・摺りのむら（②）。
//   模様の座標（画面の座標は使わない）：
//     _DS39CoordMode = 0：物体に固定。物体の座標 × 物体の尺度（ワールドの m。回転と平行移動は含めない）。船が動いても模様は船に付いたまま。
//     _DS39CoordMode = 1：空（無限遠）。目からの向き × _DS39SkyRadius（m）。空のドーム（AF27）と同じ扱いで、向きだけで決まる
//                         （頭の平行移動で空の模様は動かない＝無限遠の物と同じ。回転では世界の向きに止まっている）。
//   描き方は DS39 Paper Keypose と同じ（掛け算、深度は書かない、LEqual と Offset −1、両面）。
Shader "GreatWave/Design39/DS39 Paper Mesh"
{
    Properties
    {
        _DS39Mode ("種類（0 紙の地・1 摺りのむら）", Float) = 0
        _DS39Amp ("振幅（係数 1 ± 振幅）", Float) = 0.03
        _DS39CoordMode ("座標（0 物体に固定・1 空の向き）", Float) = 0
        _DS39SkyRadius ("空の向きに掛ける長さ（m）", Float) = 100
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
            #include "UnityCG.cginc"
            #include "DS39PaperCommon.cginc"

            float _DS39Mode, _DS39Amp, _DS39CoordMode, _DS39SkyRadius;

            struct appdata
            {
                float4 vertex : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 obj : TEXCOORD0;
                float3 world : TEXCOORD1;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 s = float3(length(unity_ObjectToWorld._m00_m10_m20), length(unity_ObjectToWorld._m01_m11_m21), length(unity_ObjectToWorld._m02_m12_m22));
                o.obj = v.vertex.xyz * s;
                o.world = mul(unity_ObjectToWorld, float4(v.vertex.xyz, 1.0)).xyz;
                o.pos = UnityObjectToClipPos(v.vertex);
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float3 p = i.obj;
                if (_DS39CoordMode > 0.5) p = normalize(i.world - _WorldSpaceCameraPos) * _DS39SkyRadius;
                return DS39Out(p, _DS39Mode, _DS39Amp);
            }
            ENDCG
        }
    }
}
