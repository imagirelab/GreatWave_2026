// 設計38：シート（主役波・周りの海 near・far）の外殻線 v1。設計27 の DS27 Outline Keypose（反転シェル、同じ keypose の頂点補間）を写し、次を変えた：
//  1) 線幅の決まり（DS38LineCommon.cginc）：角幅 × 距離、世界寸法の上限 0.3 m、画素の下限（_MinPx）。設計27 の世界寸法の下限 5 cm を外した（近くで太らない）。
//  2) 法線：列の範囲（_DS38ColRange = (colMin, colMax)、負なら全部）の外の頂点を使わずに、範囲の中の三角形だけから求める。
//     設計30 の主役波は列 18〜394 だけを描き、境の列の法線が描かない余白の列から求まって外殻線が継ぎ目に沿って海の上に出た（設計30修正1 は外殻線を
//     両端から 10 列内側で止めた）。範囲の中だけの法線にしたので、継ぎ目の上の 10 列にも線を描ける（継ぎ目をまたいで周りの海の線とつながる）。
//  3) 原画視点で原画にない線の頂点の印（_DS38LineMask、頂点ごと 1 = 描く・0 = 原画視点では描かない。_DS38MaskOn = 1 のときだけ読む）。
//  4) 検査用の出力：_DS38LineCoordMode = 1 で (10 + シートの番号 _DS38SheetId, 列, 行, 中心眼からの距離)。
// 位置は DS27Keypose.cginc（作品の面と同じ関数・同じ MaterialPropertyBlock の値。DS30SheetPlayer が外殻線のレンダラーにも同じ値を入れる）。
// 設計38 修正の回（進行役の検査の後の 1 回、Q26）：5) 押し出した反転シェルを中心眼から見て奥へ押し下げる（_DS38PushBack × 線幅。DS38LineCommon.cginc）。
//   _DS38PushPaint = 1 なら原画視点の重みを掛ける（主役波。原画視点では押し下げない）。6) 表裏の判定を、三角形の面の法線（修正1）か、
//   3 頂点の法線（押し出しに使う平均の法線）の和かで選ぶ（_DS38FacingMode）。
// SPI の立体視マクロは設計27 と同じ形（立体視での描画は HMD 実機で未検証。Mock の両眼は _DS38EyeOverride で中心眼をそろえた 2 回の描画）。
Shader "GreatWave/Design38/DS38 Outline Keypose"
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
        _DS38FacingMode ("表裏の判定（0 面の法線・1 頂点の法線の和・2 原画視点の外だけ 1）", Float) = 0
        _DS38SheetId ("シートの番号（1 主役波・2 near・3 far）", Float) = 0
        _DS38MaskOn ("頂点ごとの印を読む", Float) = 0
        _DS38ColRange ("列の範囲（colMin, colMax, 0, 0）。負なら全部", Vector) = (-1, -1, 0, 0)
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry+10" }
        Pass
        {
            Name "DS38OUTLINE"
            Tags { "LightMode"="ForwardBase" }
            Cull Front
            ZWrite On
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma geometry geom
            #pragma fragment frag
            #pragma multi_compile_instancing
            #pragma multi_compile _ DS27_POS_LO
            #include "../../Design27/Shaders/DS27Keypose.cginc"
            #include "DS38LineCommon.cginc"

            float4 _LineColor;
            float _DS38BackOnly, _DS38FacingMin, _DS38PushBack, _DS38PushPaint, _DS38FacingMode;
            float _LineAngle, _MaxWidth, _MinPx, _DS38SheetId, _DS38MaskOn;
            float4 _DS38ColRange;
            StructuredBuffer<float> _DS38LineMask;

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                uint vid : SV_VertexID;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float4 coord : TEXCOORD0;
                float3 wo : TEXCOORD1;       // 押し出す前のワールドの位置（幾何シェーダーの表裏）   // 列, 行, 中心眼からの距離, 描くかの値（1 描く）
                float3 nw : TEXCOORD2;       // 押し出しに使った頂点の法線（_DS38FacingMode = 1 の表裏）
                UNITY_VERTEX_OUTPUT_STEREO
            };

            // 列の範囲の中の三角形だけの法線（DS27Normal と同じ 6 つの三角形の和。範囲の外の隣は無いものとする）
            float3 DS38NormalWin(uint vid)
            {
                uint nu = DS27NU(), nv = DS27NV();
                uint r = vid / nu, c = vid - r * nu;
                int lo = _DS38ColRange.x >= 0 ? (int)(_DS38ColRange.x + 0.5) : 0;
                int hi = _DS38ColRange.y >= 0 ? (int)(_DS38ColRange.y + 0.5) : (int)nu - 1;
                bool hu = r > 0u, hd = r + 1u < nv, hl = (int)c > lo, hr = (int)c + 1 <= hi;
                float3 n = 0;
                float3 dD = hd ? DS27Delta(vid + nu, vid) : 0;
                float3 dR = hr ? DS27Delta(vid + 1u, vid) : 0;
                float3 dU = hu ? DS27Delta(vid - nu, vid) : 0;
                float3 dL = hl ? DS27Delta(vid - 1u, vid) : 0;
                if (hd && hr) n += cross(dD, dR);
                if (hd && hl)
                {
                    float3 dDL = DS27Delta(vid + nu - 1u, vid);
                    n += cross(dL, dDL);
                    n += cross(dDL, dD);
                }
                if (hu && hr)
                {
                    float3 dUR = DS27Delta(vid - nu + 1u, vid);
                    n += cross(dUR, dU);
                    n += cross(dR, dUR);
                }
                if (hu && hl) n += cross(dU, dL);
                float l = length(n);
                return l > 1e-30 ? n / l : float3(0, 1, 0);
            }

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float3 w = DS27WorldOrMesh(v.vid, v.vertex.xyz);
                float3 n = _DS27Enabled > 0.5 ? DS38NormalWin(v.vid) : normalize(UnityObjectToWorldNormal(v.normal));
                float d = distance(w, DS38Eye());
                float width = DS38Width(d, _LineAngle, _MaxWidth, _MinPx);
                o.pos = UnityWorldToClipPos(w + n * width + DS38PushBackOffset(w, width, _DS38PushBack, _DS38PushPaint));
                o.wo = w;
                o.nw = n;
                uint nu = max(DS27NU(), 1u);
                float keep = 1.0;
                if (_DS38MaskOn > 0.5) keep = lerp(_DS38LineMask[v.vid], 1.0, DS38PaintWeight());
                o.coord = float4((float)(v.vid % nu), (float)(v.vid / nu), d, keep);
                return o;
            }

            // 設計38 修正1：幾何シェーダーで、元の三角形が中心眼に表を向けている三角形の押し出しを捨てる（押し出しで裏返った三角形が、
            // 粗い格子の稜線や薄い爪の先で面の上に長い棘の線を描き、コマごとに点滅した）。輪郭の線は、元の三角形が裏を向く所（輪郭の向こう側）の押し出しだけから出る。
            // 表裏は両眼で同じ中心眼（DS38Eye）で決めるので、左右の目で同じ三角形が線になる。_DS38BackOnly = 0 で捨てない（比べる用）。
            [maxvertexcount(3)]
            void geom(triangle v2f i[3], inout TriangleStream<v2f> s)
            {
                float3 n = cross(i[1].wo - i[0].wo, i[2].wo - i[0].wo);
                // _DS38FacingMode：1 = 表裏を、面の法線の代わりに 3 頂点の法線（押し出しに使う平均の法線）の和で決める。粗い格子の稜線の段にできる
                // 細い折れ（ひれ）の三角形は、面の法線では裏でも平均の法線でははっきり表なので押し出さない（面の上の扇の線が出ない）。
                // 2 = 原画視点の重み ≥ 0.5 の所だけ 1（原画視点では面の法線のまま＝原画視点の描画を変えない）。
                if (_DS38FacingMode > 0.5 && (_DS38FacingMode < 1.5 || DS38PaintWeight() >= 0.5))
                {
                    float3 ns = i[0].nw + i[1].nw + i[2].nw;
                    n = ns * length(n) / max(length(ns), 1e-20);
                }
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
