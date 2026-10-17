// FLIP3D：VR の視点の動きの間に、目の周りだけを暗くする輪（2026-10-17、Claude。新しいファイル）。FLIP3DXR が頭の前に置く輪の Mesh に使う。
// 色は頂点の色（黒・透明さ）だけ。深さを見ずに最後に描く（ZTest Always・Overlay）。両眼を 1 回で描く道（Single Pass Instanced）の印を入れた。
// 真ん中はいつも透明で、動きは見える（白い画面・黒い画面で隠さない）。全部を黒くするのは始め直し・向き直しの短い幕だけ（FLIP3DXR.Fade）。
Shader "Hidden/GreatWave/FLIP3D/VignetteXR"
{
    SubShader
    {
        Tags { "Queue" = "Overlay+100" "RenderType" = "Transparent" "IgnoreProjector" = "True" }
        Pass
        {
            ZTest Always
            ZWrite Off
            Cull Off
            Blend SrcAlpha OneMinusSrcAlpha
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                fixed4 color : COLOR;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                fixed4 color : COLOR;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert (appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.color = v.color;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                return i.color;
            }
            ENDCG
        }
    }
    Fallback Off
}
