// 番号23 第2部：較正門の標識・平塗り色区・基線の ID 画像に使う無光照の単色シェーダー（両面・混色なし）。
// _Color は Color 型なので、Linear 色空間では Unity が sRGB → 線形に変換してから渡す。
// sRGB の描画先へ書くと線形 → sRGB に戻り、8bit の値が入力に戻るかを較正門で確かめる。
Shader "GreatWave/ArtFirst/AF23 Gate Flat"
{
    Properties
    {
        _Color ("色", Color) = (1, 1, 1, 1)
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
