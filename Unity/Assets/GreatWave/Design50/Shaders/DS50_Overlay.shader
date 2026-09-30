// 設計50：入口・一時停止・終わりの画面と短い知らせの板（HMD Camera の子に置く世界の板）。
//   深さを見ずに最後に描く（ZTest Always・Overlay の順）。船体や大波が手前にあっても隠れない。
//   _UseAlphaTex = 0：色の板（紙の色）。_UseAlphaTex = 1：文字（TextMesh のフォントの字の形を _MainTex の α で読み、頂点の色で塗る）。
//   Single Pass Instanced（OpenXR の --vr）でも両目へ描けるよう、立体の出力の宏を入れた（実機は未検証）。
Shader "GreatWave/Design50/DS50 Overlay"
{
    Properties
    {
        _Color ("Color", Color) = (1,1,1,1)
        _MainTex ("Texture", 2D) = "white" {}
        _UseAlphaTex ("Use alpha texture (text)", Float) = 0
    }
    SubShader
    {
        Tags { "Queue"="Overlay" "RenderType"="Transparent" "IgnoreProjector"="True" "PreviewType"="Plane" }
        Pass
        {
            ZTest Always
            ZWrite Off
            Cull Off
            Lighting Off
            Blend SrcAlpha OneMinusSrcAlpha
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"
            sampler2D _MainTex;
            float4 _MainTex_ST;
            fixed4 _Color;
            float _UseAlphaTex;
            struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD0; fixed4 color : COLOR; UNITY_VERTEX_INPUT_INSTANCE_ID };
            struct v2f { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; fixed4 color : COLOR; UNITY_VERTEX_OUTPUT_STEREO };
            v2f vert (appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                o.color = v.color * _Color;
                return o;
            }
            fixed4 frag (v2f i) : SV_Target
            {
                fixed4 c = i.color;
                fixed4 t = tex2D(_MainTex, i.uv);
                c.a *= lerp(1.0, t.a, _UseAlphaTex);
                return c;
            }
            ENDCG
        }
    }
}
