// 編号24：主役波 v0 の仮の平塗りシェーダー（無光照）。
// 藍濃／藍中／水色／白を UV2（白帯からの弧長距離 m）と高さで帯状に塗るだけの仮置き。編号28の投影焼き込み・SDF とは別物。
// 色は編号23の調色板（palette.json）の 8bit sRGB。Linear 色空間では Unity が Color プロパティを線形へ変換する。
// SPI（Single Pass Instanced）用の立体視マクロは Sampling19Surface.cginc と同じ形で入れる。
Shader "GreatWave/ArtFirst/AF24 Palette v0"
{
    Properties
    {
        _White ("白・生成り", Color) = (0.98039, 0.96078, 0.88627, 1)
        _Mizuiro ("水色", Color) = (0.75686, 0.83137, 0.78431, 1)
        _AiMid ("藍中", Color) = (0.16078, 0.41176, 0.58039, 1)
        _AiDark ("藍濃", Color) = (0.12941, 0.24314, 0.37255, 1)
        _WhiteWidth ("白帯の幅 (m)", Float) = 1.6
        _MizuiroWidth ("水色帯の外縁 (m)", Float) = 3.2
        _AiMidWidth ("藍中帯の外縁 (m)", Float) = 7.5
        _ColumnWeight ("列（弧長距離）の重み", Float) = 0.35
        _RowWeight ("行（1 − 減衰 D）の重み (m)", Float) = 18
        _LipRowWeight ("唇の列の行の重み (m)", Float) = 5
        _SeaHeight ("これより低い面は藍濃 (m)", Float) = 0.3
        _Progress ("形成率 P_body（0〜1）", Range(0, 1)) = 1
        [Toggle] _SeaOnly ("参照海面用（常に藍濃）", Float) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Name "AF24PALETTE"
            Tags { "LightMode"="ForwardBase" }
            // 一枚の水面シートなので両面を描く（唇の下面と内壁は裏面側）。
            Cull Off
            ZWrite On
            CGPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            float4 _White, _Mizuiro, _AiMid, _AiDark;
            float _WhiteWidth, _MizuiroWidth, _AiMidWidth, _ColumnWeight, _RowWeight, _LipRowWeight, _SeaHeight, _Progress, _SeaOnly;

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv2 : TEXCOORD1;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 band : TEXCOORD0;
                float height : TEXCOORD1;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.band = v.uv2;
                o.height = mul(unity_ObjectToWorld, v.vertex).y;
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                if (_SeaOnly > 0.5) return float4(_AiDark.rgb, 1);
                // 帯座標：列（白帯からの弧長距離）と行（減衰 D が小さい断面ほど原画の輪郭から内側に投影される）を足す。
                // 唇の列（UV2.x = 0）は、唇がまだ厚い断面（D > 0.75）だけ行の重みを小さくして白くする。
                float rowW = (i.band.x < 1e-3 && i.band.y > 0.75) ? _LipRowWeight : _RowWeight;
                float d = _ColumnWeight * i.band.x + rowW * (1.0 - i.band.y);
                float p = saturate(_Progress);
                // 帯の外縁は形成率に合わせて広がる（仮）。白は p > 0.5、水色は p > 1/3 から現れる。
                float3 c = _AiDark.rgb;
                if (d < _AiMidWidth * p) c = _AiMid.rgb;
                if (d < _MizuiroWidth * (1.5 * p - 0.5)) c = _Mizuiro.rgb;
                if (d < _WhiteWidth * (2.0 * p - 1.0) + 1e-4 * step(0.5, p)) c = _White.rgb;
                if (i.height < _SeaHeight) c = _AiDark.rgb;
                return float4(c, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
