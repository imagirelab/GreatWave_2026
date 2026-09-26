// 番号26：K* の形を確かめるための確認用シェーダー（色の正解ではない。色は番号28で作る）。
// 固定の平行光（ワールド方向）によるランバート＋環境光で立体の形を読めるようにし、海面の高さ（y < _SeaHeight）は藍濃の平塗りにする。
// 裏面（水の側）が見えた所は赤紫にして、開いた裏面を画像で見つけられるようにする。
// SPI（Single Pass Instanced）用の立体視マクロは AF24 と同じ形で入れる（立体視での描画は確かめていない）。
Shader "GreatWave/ArtFirst/AF26 Clay"
{
    Properties
    {
        _Base ("面の色", Color) = (0.62, 0.72, 0.80, 1)
        _Sea ("海面の色（藍濃）", Color) = (0.12941, 0.24706, 0.37647, 1)
        _Back ("裏面の色", Color) = (0.85, 0.20, 0.65, 1)
        _LightDir ("光の向き（ワールド、面から光へ）", Vector) = (-0.45, 0.75, -0.48, 0)
        _Ambient ("環境光", Range(0, 1)) = 0.38
        _SeaHeight ("これより低い面は海面の色 (m)", Float) = 0.05
        [Toggle] _SeaOnly ("参照海面用（常に海面の色）", Float) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "AF26CLAY"
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            float4 _Base, _Sea, _Back, _LightDir;
            float _Ambient, _SeaHeight, _SeaOnly;

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 nrm : TEXCOORD0;
                float3 wpos : TEXCOORD1;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.nrm = UnityObjectToWorldNormal(v.normal);
                o.wpos = mul(unity_ObjectToWorld, v.vertex).xyz;
                return o;
            }

            float4 frag(v2f i, float face : VFACE) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                if (_SeaOnly > 0.5 || i.wpos.y < _SeaHeight) return float4(_Sea.rgb, 1);
                if (face < 0) return float4(_Back.rgb, 1);
                float3 n = normalize(i.nrm);
                float3 l = normalize(_LightDir.xyz);
                float ndl = saturate(dot(n, l));
                float3 c = _Base.rgb * (_Ambient + (1.0 - _Ambient) * ndl);
                return float4(c, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
