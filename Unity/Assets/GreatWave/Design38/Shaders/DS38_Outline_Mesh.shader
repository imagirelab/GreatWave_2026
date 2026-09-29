// 設計38：爪の縁の線と、爪が重なる所の手前の線（反転シェル）。DS38ClawOutline が設計34 の爪の結合メッシュの頂点（そのコマの位置）を写し、
// 滑らかな頂点の法線（RecalculateNormals。帯は輪 8 頂点の扁平な楕円の筒なので外向き）を付けたメッシュを描く。
// 線幅の決まりはシートと同じ（DS38LineCommon.cginc）。爪の筒の裏の面を法線の向きへ押し出して描くので、
//   ・爪の輪郭（空・主役波のシート・ほかの爪を背にした縁）に線が出る、
//   ・手前の爪が奥の爪に重なる所では、手前の爪の押し出しが奥の爪より手前にあり、奥の爪の上に手前の爪の縁の線が出る（奥の線は手前の爪の面に隠れる）。
// 原画視点の近くでは描かない（DS38PaintWeight < 0.5。原画視点では焼き込みの爪の模様が線を担う）。
// 検査用の出力：_DS38LineCoordMode = 1 で (10 + 4, 爪の番号, 輪の番号（頂点の番号 / 8）, 中心眼からの距離)。UV2 = (爪の番号, 爪の中の頂点の番号)。
Shader "GreatWave/Design38/DS38 Outline Mesh"
{
    Properties
    {
        _LineColor ("線の色（藍の線）", Color) = (0.2784314, 0.3137255, 0.372549, 1)
        _LineAngle ("線の角幅（rad）", Float) = 0.0012865962
        _MaxWidth ("押し出し幅の世界寸法の上限（m）", Float) = 0.3
        _MinPx ("画素の下限（画素）", Float) = 1.5
        _DS38BackOnly ("元の三角形が裏を向く所だけ押し出す", Float) = 1
        _DS38FacingMin ("裏を向く度合いの下限（内積の -値。既定 0）", Float) = 0
        _DS38PushBack ("奥への押し下げ（線幅の倍数。0 で押し下げない。設計38 修正の回）", Float) = 0
        _DS38PushPaint ("押し下げに原画視点の重みを掛ける", Float) = 0
        _DS38SheetId ("番号（4 爪）", Float) = 4
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry+10" }
        Pass
        {
            Name "DS38OUTLINEMESH"
            Tags { "LightMode"="ForwardBase" }
            Cull Front
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma geometry geom
            #pragma fragment frag
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"
            #include "DS38LineCommon.cginc"

            float4 _LineColor;
            float _DS38BackOnly, _DS38FacingMin, _DS38PushBack, _DS38PushPaint;
            float _LineAngle, _MaxWidth, _MinPx, _DS38SheetId;

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                float2 uv2 : TEXCOORD2;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float4 coord : TEXCOORD0;
                float3 wo : TEXCOORD1;       // 押し出す前のワールドの位置（幾何シェーダーの表裏）
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 w = mul(unity_ObjectToWorld, float4(v.vertex.xyz, 1.0)).xyz;
                float3 nn = UnityObjectToWorldNormal(v.normal);
                float ln = length(nn);
                float3 n = ln > 1e-12 ? nn / ln : float3(0, 0, 0);
                float d = distance(w, DS38Eye());
                float width = DS38Width(d, _LineAngle, _MaxWidth, _MinPx);
                o.pos = UnityWorldToClipPos(w + n * width + DS38PushBackOffset(w, width, _DS38PushBack, _DS38PushPaint));
                o.wo = w;
                o.coord = float4(v.uv2.x, floor(v.uv2.y / 8.0), d, DS38PaintWeight());
                return o;
            }

            // 設計38 修正1：幾何シェーダーで、元の三角形が中心眼に表を向けている三角形の押し出しを捨てる（押し出しで裏返った三角形が、
            // 粗い格子の稜線や薄い爪の先で面の上に長い棘の線を描き、コマごとに点滅した）。輪郭の線は、元の三角形が裏を向く所（輪郭の向こう側）の押し出しだけから出る。
            // 表裏は両眼で同じ中心眼（DS38Eye）で決めるので、左右の目で同じ三角形が線になる。_DS38BackOnly = 0 で捨てない（比べる用）。
            [maxvertexcount(3)]
            void geom(triangle v2f i[3], inout TriangleStream<v2f> s)
            {
                float3 n = cross(i[1].wo - i[0].wo, i[2].wo - i[0].wo);
                float3 cen = (i[0].wo + i[1].wo + i[2].wo) / 3.0;
                // _DS38FacingMin（既定 0）：元の三角形の単位法線と中心眼への単位の向きの内積がこれより小さい（はっきり裏を向く）三角形だけを押し出す
                if (_DS38BackOnly > 0.5 && dot(n, DS38Eye() - cen) > -_DS38FacingMin * length(n) * length(DS38Eye() - cen)) return;
                s.Append(i[0]); s.Append(i[1]); s.Append(i[2]);
            }

            float4 frag(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                if (i.coord.w < 0.5) discard;
                if (_DS38LineCoordMode > 0.5) return float4(10.0 + _DS38SheetId, i.coord.x, i.coord.y, i.coord.z);
                if (_AF28IdMode > 0.5) return float4(1, 0, 1, 1);
                return float4(_LineColor.rgb, 1);
            }
            ENDCG
        }
    }
    Fallback Off
}
