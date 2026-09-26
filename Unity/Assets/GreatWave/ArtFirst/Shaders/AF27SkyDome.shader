// 番号27：世界の仰角によるグラデーションの空のドーム（画面空間のグラデーションは使わない）。
// 色はカメラから見た方向 d（= 正規化(世界位置 − カメラ位置)）だけで決まる。どの視点・両眼でも同じ空になる（無限遠の空と同じ扱い）。
//   el = asin(d.y)、az = atan2(d.x, d.z)（度）
//   e' = el − w(el)·(θt(az) − θ0)、w = saturate((θ0 + wZero − el) / (wZero − wFull))
//   色 = 表(e')（線形 RGB）
// θt(az)（暗い空の上端の仰角）と色の表は Tools/GWContext/sky_dome.json（原画から af27_sky.py が当てはめた値）から作ったテクスチャ。
// テクスチャは点標本で読み、隣の 2 点を線形補間する（numpy の予測と同じ式）。球の内側を描く（Cull Front）。SPI の立体視マクロ付き。
Shader "GreatWave/ArtFirst/AF27 Sky Dome"
{
    Properties
    {
        _ThetaT ("θt(az)（度、R）", 2D) = "black" {}
        _Gradient ("色の表（線形 RGB）", 2D) = "white" {}
        _ThetaParams ("θt の表：az0, 刻み, 個数, θ0", Vector) = (-60, 0.05, 2401, 2.9)
        _GradParams ("色の表：e0, 刻み, 個数, 0", Vector) = (-2, 0.02, 2101, 0)
        _WParams ("重み：wFull, wZero, 0, 0", Vector) = (1.5, 4.5, 0, 0)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Cull Front
            ZWrite On
            CGPROGRAM
            #pragma target 3.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"

            sampler2D _ThetaT;
            sampler2D _Gradient;
            float4 _ThetaParams;
            float4 _GradParams;
            float4 _WParams;

            struct appdata
            {
                float4 vertex : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 world : TEXCOORD0;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.world = mul(unity_ObjectToWorld, v.vertex).xyz;
                return o;
            }

            // 1 行のテクスチャを実数の添字 x で線形補間して読む（点標本 2 回）。
            float4 Lookup(sampler2D tex, float x, float n)
            {
                x = clamp(x, 0.0, n - 1.0);
                float i0 = floor(x);
                float i1 = min(i0 + 1.0, n - 1.0);
                float f = x - i0;
                float4 a = tex2Dlod(tex, float4((i0 + 0.5) / n, 0.5, 0, 0));
                float4 b = tex2Dlod(tex, float4((i1 + 0.5) / n, 0.5, 0, 0));
                return lerp(a, b, f);
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                float3 d = normalize(i.world - _WorldSpaceCameraPos.xyz);
                float el = degrees(asin(clamp(d.y, -1.0, 1.0)));
                float az = degrees(atan2(d.x, d.z));
                float theta = Lookup(_ThetaT, (az - _ThetaParams.x) / _ThetaParams.y, _ThetaParams.z).r;
                float theta0 = _ThetaParams.w;
                float w = saturate((theta0 + _WParams.y - el) / (_WParams.y - _WParams.x));
                float ep = el - w * (theta - theta0);
                float3 c = Lookup(_Gradient, (ep - _GradParams.x) / _GradParams.y, _GradParams.z).rgb;
                return float4(c, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
