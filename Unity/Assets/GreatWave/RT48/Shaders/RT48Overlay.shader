// RT48：VR の目の前の板と字（TextMesh）。深さを見ずに最後に描く。single-pass instanced の立体の書き方。
//   _UseAlphaTex 1：字（_MainTex の a、フォントの字の画）。0：板（色だけ）。
Shader "GreatWave/RT48/Overlay"
{
    Properties
    {
        _MainTex ("字の画", 2D) = "white" {}
        _Color ("色", Color) = (1, 1, 1, 1)
        _UseAlphaTex ("字の画の a を使う", Float) = 1
    }
    SubShader
    {
        Tags { "Queue"="Overlay" "RenderType"="Transparent" "IgnoreProjector"="True" }
        ZTest Always ZWrite Off Cull Off
        Blend SrcAlpha OneMinusSrcAlpha
        Pass
        {
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"
            sampler2D _MainTex;
            float4 _MainTex_ST;
            float4 _Color;
            float _UseAlphaTex;
            struct appdata { float4 vertex : POSITION; float4 color : COLOR; float2 uv : TEXCOORD0; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct v2f { float4 pos : SV_POSITION; float4 color : COLOR; float2 uv : TEXCOORD0; UNITY_VERTEX_OUTPUT_STEREO };
            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.color = v.color * _Color;
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                return o;
            }
            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float a = _UseAlphaTex > 0.5 ? tex2D(_MainTex, i.uv).a : 1.0;
                return float4(i.color.rgb, i.color.a * a);
            }
            ENDCG
        }
    }
    Fallback Off
}
