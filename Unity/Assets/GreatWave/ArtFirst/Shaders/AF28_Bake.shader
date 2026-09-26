// 番号28：GWProjectionBaker（AF28ProjectionBaker.cs）が使う投影ベイクのシェーダー。エディター専用で、実行時には使わない。
// パス 0「DEPTH」：PaintingCam v1 から K* を描き、画素ごとの 1/視点深度（1/m）の最大（= 最も近い面）を RFloat に残す（BlendOp Max。深度バッファを使わない。背景は 0）。
// パス 1「SDF」・パス 2「AUX」：K* を焼き込み用の UV（UV3 = TEXCOORD2。UV0 を列・行ごとに引き伸ばした u′, v′）の空間へ広げて描き（1 テクセル = 1 画素）、
//   各テクセルの世界位置を PaintingCam へ投影する。
//   SDF：原画側の 4 色区の符号付き距離（表示 px）を、投影した位置で双線形に読む。
//   AUX：R = 見える(1) + 画面内(2)、G = 原画の有効域（0 遮蔽物／0.25 遠い空／0.5 近い空／1 主浪）、B = 世界の高さ y（m）、A = UV3 の v′（向きの確かめ用）。
// 投影は Unity の Camera.projectionMatrix × worldToCameraMatrix（OpenGL 規約）で、viewport (vx, vy) は左下原点。
Shader "Hidden/GreatWave/ArtFirst/AF28 Bake"
{
    Properties
    {
        _DepthTex ("PaintingCam の視点深度（RFloat）", 2D) = "white" {}
        _PaintSdf ("原画側の符号付き距離（RGBAHalf、高解像度原画の格子）", 2D) = "black" {}
        _PaintValid ("原画側の有効域（R8）", 2D) = "black" {}
    }
    CGINCLUDE
    #include "UnityCG.cginc"
    float4x4 _BakeGpuVP;     // GL.GetGPUProjectionMatrix(proj, true) × view（深度パス用）
    float4x4 _BakeVPGL;      // proj × view（OpenGL 規約。viewport と視点深度の計算用）
    float _UvFlip, _DepthFlip, _TolM, _TolRel, _ScoredX0, _ScoredX1, _OffX, _Scale, _PaintW;
    sampler2D _DepthTex, _PaintSdf, _PaintValid;

    struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD2; };
    struct v2fd { float4 pos : SV_POSITION; float eye : TEXCOORD0; };
    struct v2fu { float4 pos : SV_POSITION; float3 wpos : TEXCOORD0; float2 uv : TEXCOORD1; };

    v2fd vertDepth(appdata v)
    {
        v2fd o;
        float3 w = mul(unity_ObjectToWorld, float4(v.vertex.xyz, 1)).xyz;
        o.pos = mul(_BakeGpuVP, float4(w, 1));
        o.eye = mul(_BakeVPGL, float4(w, 1)).w;   // 透視投影の w = 視点深度
        return o;
    }
    float4 fragDepth(v2fd i) : SV_Target { return float4(1.0 / max(i.eye, 1e-4), 0, 0, 1); }

    v2fu vertUv(appdata v)
    {
        v2fu o;
        o.pos = float4(v.uv.x * 2 - 1, (v.uv.y * 2 - 1) * _UvFlip, 0.5, 1);
        o.wpos = mul(unity_ObjectToWorld, float4(v.vertex.xyz, 1)).xyz;
        o.uv = v.uv;
        return o;
    }

    // 投影：viewport、視点深度、画面内か、見えるか、原画の格子の座標
    void Project(float3 wpos, out float2 vp, out float eye, out float onScreen, out float vis, out float2 puv)
    {
        float4 c = mul(_BakeVPGL, float4(wpos, 1));
        eye = c.w;
        float2 ndc = c.xy / max(c.w, 1e-6);
        vp = ndc * 0.5 + 0.5;
        float xd = vp.x * 1920.0 - 0.5;
        float yd = (1.0 - vp.y) * 1080.0 - 0.5;
        onScreen = (eye > 0.1 && xd >= _ScoredX0 - 0.5 && xd <= _ScoredX1 + 0.5 && yd >= -0.5 && yd <= 1079.5) ? 1 : 0;
        float2 duv = float2(vp.x, _DepthFlip > 0.5 ? 1.0 - vp.y : vp.y);
        float inv = tex2Dlod(_DepthTex, float4(duv, 0, 0)).r;
        float dm = inv > 0 ? 1.0 / inv : 1e9;
        vis = (onScreen > 0.5 && eye <= dm + _TolM + _TolRel * eye) ? 1 : 0;
        // 表示 px → 高解像度原画の格子の UV（生データは下の行から入れてあるので v = vy）
        puv = float2((xd + 0.5 - _OffX) / (_Scale * _PaintW), vp.y);
    }

    float4 fragSdf(v2fu i) : SV_Target
    {
        float2 vp, puv; float eye, onScreen, vis;
        Project(i.wpos, vp, eye, onScreen, vis, puv);
        return tex2Dlod(_PaintSdf, float4(puv, 0, 0));
    }

    float4 fragAux(v2fu i) : SV_Target
    {
        float2 vp, puv; float eye, onScreen, vis;
        Project(i.wpos, vp, eye, onScreen, vis, puv);
        float valid = tex2Dlod(_PaintValid, float4(puv, 0, 0)).r;
        return float4(vis + 2 * onScreen, valid, i.wpos.y, i.uv.y);
    }
    ENDCG

    SubShader
    {
        Pass
        {
            Name "DEPTH"
            Cull Off ZWrite Off ZTest Always
            BlendOp Max
            Blend One One
            CGPROGRAM
            #pragma target 3.5
            #pragma vertex vertDepth
            #pragma fragment fragDepth
            ENDCG
        }
        Pass
        {
            Name "SDF"
            Cull Off ZWrite Off ZTest Always
            CGPROGRAM
            #pragma target 3.5
            #pragma vertex vertUv
            #pragma fragment fragSdf
            ENDCG
        }
        Pass
        {
            Name "AUX"
            Cull Off ZWrite Off ZTest Always
            CGPROGRAM
            #pragma target 3.5
            #pragma vertex vertUv
            #pragma fragment fragAux
            ENDCG
        }
    }
    Fallback Off
}
