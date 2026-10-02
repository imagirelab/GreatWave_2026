// 仕上げ33（設計33 爪の造形）：仕上げ32 の PL32 Claw Outline の写しに、pl33_web_noline を足したもの。
// 鉤の内の水色の版の膜（pl33_hook_web、id W＋爪の id）と根元の円は、UV3.x = −1（PL33ClawLook・PL32ClawLook が入れる）で、
// 3 頂点のどれかが −1 の三角形は押し出さない（膜は薄い 2 面の帯なので、PL32 の幅 0 の押し出しが膜と同じ深さに線の色で描かれて z の争いになるのを防ぐ）。
// 値は帯の頂点に付いた値だけで決まり、視点・原画カメラでは決まらない。ほかは PL32 Claw Outline と同じ。
// 仕上げ32 修正の回 1：爪の縁の線（設計38 の DS38 Outline Mesh の写し）に、根元で線を開く決まり（pl32f_root_open）を足したもの。
// 設計38 の反転シェルは帯の全周に線を出すので、伸びる途中の短い帯（原画視点 t 10.5 s の b区域）が閉じた輪（米粒）に見え、t* の b区域の爪も
// 1 本ずつ縁取られた「虫」に見えた（審査の指摘）。原画の爪の線は指の外側と先を回り、根元では泡の胴へ開いている（摺りの墨版の線）。
// そこで、押し出し幅に、根元 → 先の位置 a（頂点の UV3.x。PL32ClawLook が入れる。根元の点 0・輪 s/(輪の数 − 1)・先 1・根元の円は −1）の重み
//   smoothstep(_PL32RootFade.x, _PL32RootFade.y, a)
// を掛ける（根元の円は 0。線を描かない）。重みは帯の頂点に付いた値だけで決まり、視点・原画カメラでは決まらない。
// さらに pl32f_edge_box：帯は幅に対して薄い扁平な筒なので、縁から（面すれすれに）見ると上面・下面の三角形の押し出しが帯を囲む細い箱になった
// （座席から b区域の背の稜を見た時の「線の箱」、審査の指摘）。輪の頂点の向き（UV3.y：1 上面 φ 45〜135°、2 下面 φ 225〜315°、0 横と根元・先）で、
// 3 頂点がそろって上面か下面の三角形は押し出さない（輪郭の線は横の三角形から出る。正面から見た線は残る）。_PL32EdgeBox = 0 で設計38 と同じ。
// ほかは設計38 と同じ（線幅の決まりは DS38LineCommon.cginc、元の三角形が中心眼に裏を向く所だけ押し出す幾何シェーダー）。
Shader "GreatWave/Polish33/PL33 Claw Outline"
{
    Properties
    {
        _LineColor ("線の色（藍の線）", Color) = (0.2784314, 0.3137255, 0.372549, 1)
        _LineAngle ("線の角幅（rad）", Float) = 0.0012865962
        _MaxWidth ("押し出し幅の世界寸法の上限（m）", Float) = 0.3
        _MinPx ("画素の下限（画素）", Float) = 1.5
        _DS38BackOnly ("元の三角形が裏を向く所だけ押し出す", Float) = 1
        _DS38FacingMin ("裏を向く度合いの下限（内積の -値。既定 0）", Float) = 0
        _DS38PushBack ("奥への押し下げ（線幅の倍数。0 で押し下げない）", Float) = 0
        _DS38PushPaint ("押し下げに原画視点の重みを掛ける", Float) = 0
        _DS38SheetId ("番号（4 爪）", Float) = 4
        _PL32RootFade ("根元で線を開く（x：幅 0 の位置、y：幅 1 の位置。根元 0 → 先 1）", Vector) = (0.0, 0.3, 0, 0)
        _PL32EdgeBox ("上面・下面だけの三角形を押し出さない", Float) = 1
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry+10" }
        Pass
        {
            Name "PL33CLAWOUTLINE"
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
            #include "../../Design38/Shaders/DS38LineCommon.cginc"

            float4 _LineColor;
            float _DS38BackOnly, _DS38FacingMin, _DS38PushBack, _DS38PushPaint;
            float _LineAngle, _MaxWidth, _MinPx, _DS38SheetId;
            float4 _PL32RootFade;
            float _PL32EdgeBox;

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                float2 uv2 : TEXCOORD2;
                float2 uv3 : TEXCOORD3;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float4 coord : TEXCOORD0;
                float3 wo : TEXCOORD1;
                float cls : TEXCOORD2;
                float ax : TEXCOORD3;
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
                float a = v.uv3.x;
                float k = a < -0.5 ? 0.0 : smoothstep(_PL32RootFade.x, max(_PL32RootFade.y, _PL32RootFade.x + 1e-4), a);
                float width = DS38Width(d, _LineAngle, _MaxWidth, _MinPx) * k;
                o.pos = UnityWorldToClipPos(w + n * width + DS38PushBackOffset(w, width, _DS38PushBack, _DS38PushPaint));
                o.wo = w;
                o.cls = v.uv3.y;
                o.ax = v.uv3.x;
                o.coord = float4(v.uv2.x, floor(v.uv2.y / 8.0), d, DS38PaintWeight());
                return o;
            }

            [maxvertexcount(3)]
            void geom(triangle v2f i[3], inout TriangleStream<v2f> s)
            {
                float3 n = cross(i[1].wo - i[0].wo, i[2].wo - i[0].wo);
                float3 cen = (i[0].wo + i[1].wo + i[2].wo) / 3.0;
                if (_DS38BackOnly > 0.5 && dot(n, DS38Eye() - cen) > -_DS38FacingMin * length(n) * length(DS38Eye() - cen)) return;
                if (min(i[0].ax, min(i[1].ax, i[2].ax)) < -0.5) return;   // pl33_web_noline：膜と根元の円は線を出さない
                if (_PL32EdgeBox > 0.5)
                {
                    float c0 = round(i[0].cls), c1 = round(i[1].cls), c2 = round(i[2].cls);
                    if (c0 > 0.5 && c0 == c1 && c1 == c2) return;
                }
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
