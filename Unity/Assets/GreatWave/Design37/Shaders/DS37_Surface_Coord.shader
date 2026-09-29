// 設計37：検査用の「面の座標」の表示（作品の描画には使わない）。DS27 形式のシート（主役波・near・far）の格子の座標
// （列、行。頂点の添字 = 行 × 列数 + 列 から求め、三角形の中は透視補正の線形補間＝面の上の同じ点）と、シートの番号を浮動小数で書く。
// R = 列 + 2000 × シートの番号（1 主役波・2 near・3 far・4 爪）、G = 行（DS37Render は R・G を float32 × 2 で書く）。ほかのシェーダーの物は R ≤ 1 程度なので区別できる。
// 位置は DS27Keypose.cginc（作品の描画と同じ関数・同じ MaterialPropertyBlock の値）。爪（_DS37SheetId = 4）はメッシュの頂点のまま（CPU で更新される）。
// ds37_flow_eval.py が、この座標と頂点の位置（DS27KeyposeCapture の読み戻し）から「面が画面の上でどう動いたか」を画素ごとに求める。
Shader "GreatWave/Design37/DS37 Surface Coord"
{
    Properties
    {
        _DS37SheetId ("シートの番号（1 主役波・2 near・3 far・4 爪）", Float) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" "Queue"="Geometry" }
        Pass
        {
            Tags { "LightMode"="ForwardBase" }
            Cull Off
            ZWrite On
            ZTest LEqual
            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ DS27_POS_LO
            #include "../../Design27/Shaders/DS27Keypose.cginc"

            float _DS37SheetId;

            struct appdata
            {
                float4 vertex : POSITION;
                uint vid : SV_VertexID;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 cr : TEXCOORD0;
            };

            v2f vert(appdata v)
            {
                v2f o;
                bool claw = _DS37SheetId > 3.5;
                float3 w = claw ? mul(unity_ObjectToWorld, float4(v.vertex.xyz, 1.0)).xyz : DS27WorldOrMesh(v.vid, v.vertex.xyz);
                o.pos = UnityWorldToClipPos(w);
                uint nu = max(DS27NU(), 1u);
                o.cr = claw ? float2(0, 0) : float2((float)(v.vid % nu), (float)(v.vid / nu));
                return o;
            }

            float4 frag(v2f i) : SV_Target
            {
                return float4(i.cr.x + 2000.0 * _DS37SheetId, i.cr.y, 0.0, 1.0);
            }
            ENDCG
        }
    }
    Fallback Off
}
