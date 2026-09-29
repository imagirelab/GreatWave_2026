// 設計36：爪の t* の見え方の表。t* のコマの爪の結合メッシュを原画視点のカメラで描き、目の奥行き（m、カメラの前が正）を R に書く。
// DS36ClawPalette.Apply が 1 回だけ使う（作品の描画には使わない）。奥行きの比べで「t* に原画のカメラから見える面」を決める。
Shader "GreatWave/Design36/DS36 Claw TDepth"
{
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        Pass
        {
            Cull Off
            ZWrite On
            ZTest LEqual
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            struct v2f { float4 pos : SV_POSITION; float z : TEXCOORD0; };
            v2f vert(float4 v : POSITION)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v);
                o.z = -UnityObjectToViewPos(v.xyz).z;
                return o;
            }
            float4 frag(v2f i) : SV_Target { return float4(i.z, 0, 0, 1); }
            ENDCG
        }
    }
    Fallback Off
}
