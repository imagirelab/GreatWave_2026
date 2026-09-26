// 番号27：船・富士・海面・前景のうねりと斜面の仮置きを、調色板の色で平塗りする（無光照・両面）。
// _Color は Color 型なので、Linear 色空間では Unity が sRGB → 線形に直して渡し、sRGB の描画先へ書くときに sRGB へ戻る
// （番号23 の較正門で 8bit 値が入力へ戻ることを確かめた経路と同じ）。SPI（シングルパス・インスタンシング）の立体視マクロ付き。
Shader "GreatWave/ArtFirst/AF27 Flat"
{
    Properties
    {
        _Color ("色（調色板の 8bit sRGB）", Color) = (1, 1, 1, 1)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            float4 _Color;

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
                o.pos = UnityObjectToClipPos(v.vertex);
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                return float4(_Color.rgb, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
