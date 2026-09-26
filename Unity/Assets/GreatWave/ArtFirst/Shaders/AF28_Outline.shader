// 番号28：外殻線 v0（反転シェル）。主役波の水面シートを頂点法線（空気の側）へ押し出した殻の、裏向きの面だけを描く。
// 面の縁（シルエット）の外側に、押し出し幅の分だけ線がのぞく。
// 押し出し幅（m）= clamp(中心眼から頂点までの距離 × _LineAngle, _MinWidth, _MaxWidth)。
//   _LineAngle は原画の輪郭線の幅（表示 px）× 原画視点（PaintingCam v1、縦画角 26°、縦 1080 px）の 1 px の角度（rad）。
//   中心眼：SPI などの立体視では左右の眼の位置の中点、単眼では _WorldSpaceCameraPos。両眼で同じ世界の幅になる。
// ID 表示（大域の _AF28IdMode = 1）では (1, 0, 1) を出す。原画にない線を消す頂点ごとの線マスクは番号36 で作る。
// SPI 用の立体視マクロは Sampling19Surface.cginc と同じ形で入れた（立体視での描画は確かめていない）。
Shader "GreatWave/ArtFirst/AF28 Outline v0"
{
    Properties
    {
        _LineColor ("線の色（原画の外周の線の芯）", Color) = (0.2, 0.2, 0.25, 1)
        _LineAngle ("線の角幅（rad）", Float) = 0.00129
        _MinWidth ("押し出し幅の下限（m）", Float) = 0.05
        _MaxWidth ("押し出し幅の上限（m）", Float) = 0.3
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry+10" }
        Pass
        {
            Name "AF28OUTLINE"
            Tags { "LightMode"="ForwardBase" }
            Cull Front
            ZWrite On
            CGPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            float4 _LineColor;
            float _LineAngle, _MinWidth, _MaxWidth;
            float _AF28IdMode;

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            float3 CentreEye()
            {
            #if defined(USING_STEREO_MATRICES)
                return 0.5 * (unity_StereoWorldSpaceCameraPos[0] + unity_StereoWorldSpaceCameraPos[1]);
            #else
                return _WorldSpaceCameraPos;
            #endif
            }

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 w = mul(unity_ObjectToWorld, float4(v.vertex.xyz, 1)).xyz;
                float3 n = normalize(UnityObjectToWorldNormal(v.normal));
                float width = clamp(distance(w, CentreEye()) * _LineAngle, _MinWidth, _MaxWidth);
                o.pos = UnityWorldToClipPos(w + n * width);
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                if (_AF28IdMode > 0.5) return float4(1, 0, 1, 1);
                return float4(_LineColor.rgb, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
