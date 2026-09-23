Shader "MasterProject/HokusaiClawInstanced"
{
    Properties
    {
        // 爪状の形状自体が白波なので、旧紙に近いクリーム色を基調とし、
        // 影を淡青、輪郭を濃い藍色にして海面シェーダーと揃える。
        _BaseColor ("基本色（白波のクリーム色）", Color) = (0.93, 0.91, 0.84, 1)
        _TipColor ("高評価部分の色", Color) = (0.98, 0.97, 0.93, 1)
        _RootBlendColor ("根元で混ぜる水面色", Color) = (0.50, 0.66, 0.74, 1)
        _ShadowTint ("陰側の色", Color) = (0.62, 0.73, 0.78, 1)
        _OutlineColor ("輪郭の墨色", Color) = (0.027, 0.067, 0.125, 1)
        _OutlineStrength ("輪郭の強さ", Range(0, 1)) = 0.58
        _RimStart ("輪郭を描き始める位置", Range(0.1, 0.95)) = 0.76
        _ContourLineStrength ("木版画風の輪郭線の強さ", Range(0, 1)) = 0.72
        _ContourLineWidth ("木版画風の輪郭線の幅", Range(0.005, 0.18)) = 0.055
        _GreenShadowColor ("波の緑色の陰", Color) = (0.43, 0.64, 0.54, 1)
        _GreenShadowStrength ("緑色の陰の強さ", Range(0, 1)) = 0.68
        _VisibleFraction ("見える爪状白波の割合", Range(0, 1)) = 1
        _VisibleAlpha ("爪状白波の不透明度", Range(0, 1)) = 1
        _VisibleRibbonGate ("白波の帯の表示条件", Range(0, 1)) = 0
        _VisibleRibbonParams ("白波の帯の設定", Vector) = (0.5, 0.5, 0.24, 0.08)
        _VisibleRibbonShape ("白波の帯の形状", Vector) = (0.08, 0.0, 0.06, 0)
        _Ambient ("環境光", Range(0, 1)) = 0.55
        _LightStrength ("光の強さ", Range(0, 3)) = 0.85
        _ScoreTintStrength ("評価値による色の変化", Range(0, 1)) = 0.65
        _RootFadeWidth ("根元がなじむ範囲", Range(0.02, 0.8)) = 0.26
        _RootAlpha ("根元の不透明度", Range(0, 1)) = 0.18
        _FoamCutStrength ("白波内側の彫り跡の強さ", Range(0, 1)) = 0.28
        _EdgeScallopStrength ("白波の縁の欠けの強さ", Range(0, 1)) = 0.24
        _FoamUnderlay ("白波の帯の下地", Range(0, 1)) = 0
        _UnderlayColor ("下地の白波の色", Color) = (0.96, 0.93, 0.82, 1)
        _UnderlayAlpha ("下地の不透明度", Range(0, 1)) = 0.36
        _UnderlayExpand ("下地の幅の拡大", Range(0, 2)) = 0.65
        _UnderlayTipExpand ("下地の先端の拡大", Range(0, 2)) = 0.40
        _UnderlayScoreFloor ("下地の評価値の下限", Range(0, 1)) = 0.22
    }

    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent+20" }
        LOD 100

        Pass
        {
            Tags { "LightMode" = "ForwardBase" }
            Cull Off
            Blend SrcAlpha OneMinusSrcAlpha
            ZWrite Off
            ZTest Always
            Offset -2, -2

            CGPROGRAM
            #pragma target 4.5
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_local _ HOKUSAI_CLAW_INDIRECT

            #include "UnityCG.cginc"
            #include "Lighting.cginc"

#if defined(HOKUSAI_CLAW_INDIRECT)
            struct ClawInstanceData
            {
                float4 row0;
                float4 row1;
                float4 row2;
                float4 row3;
                float4 params;
            };

            StructuredBuffer<ClawInstanceData> _ClawInstances;
#endif

            float4 _BaseColor;
            float4 _TipColor;
            float4 _RootBlendColor;
            float4 _ShadowTint;
            float4 _OutlineColor;
            float _ClawSizeBoost; // 実行時の大きさの倍率。0 または未設定なら 1 とみなす。
                                  // clawScaleRange と backgroundClawScale は個体ごとにほぼ固定した倍率となるため、
                                  // 再生成せずに描画中の爪状白波を大きくするには、この値を調整する。
            float _OutlineStrength;
            float _RimStart;
            float _ContourLineStrength;
            float _ContourLineWidth;
            float4 _GreenShadowColor;
            float _GreenShadowStrength;
            float _VisibleFraction;
            float _VisibleAlpha;
            float _VisibleRibbonGate;
            float4 _VisibleRibbonParams;
            float4 _VisibleRibbonShape;
            float _Ambient;
            float _LightStrength;
            float _ScoreTintStrength;
            float _RootLocalY;
            float _TipLocalY;
            float _RootFadeWidth;
            float _RootAlpha;
            float _FoamCutStrength;
            float _EdgeScallopStrength;
            float _FoamUnderlay;
            float4 _UnderlayColor;
            float _UnderlayAlpha;
            float _UnderlayExpand;
            float _UnderlayTipExpand;
            float _UnderlayScoreFloor;

            struct appdata
            {
                float4 vertex : POSITION;
                float3 normal : NORMAL;
                float2 uv : TEXCOORD0;
#if defined(HOKUSAI_CLAW_INDIRECT)
                uint instanceID : SV_InstanceID;
#endif
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 worldNormal : TEXCOORD0;
                float score : TEXCOORD1;
                float3 worldPos : TEXCOORD2;
                float tip01 : TEXCOORD3;
                float life : TEXCOORD4;
                float growth : TEXCOORD5;
                float2 uv : TEXCOORD6;
                float random01 : TEXCOORD7;
                float2 screenUv : TEXCOORD8;
            };

#if defined(HOKUSAI_CLAW_INDIRECT)
            float3 TransformPoint(ClawInstanceData data, float3 localPos)
            {
                float4 p = float4(localPos, 1.0f);
                return float3(dot(data.row0, p), dot(data.row1, p), dot(data.row2, p));
            }

            float3 TransformNormal(ClawInstanceData data, float3 localNormal)
            {
                return normalize(float3(
                    dot(data.row0.xyz, localNormal),
                    dot(data.row1.xyz, localNormal),
                    dot(data.row2.xyz, localNormal)));
            }
#endif

            v2f vert(appdata v)
            {
                v2f o;
#if defined(HOKUSAI_CLAW_INDIRECT)
                ClawInstanceData data = _ClawInstances[v.instanceID];
                float rootToTip = _TipLocalY - _RootLocalY;
                rootToTip = abs(rootToTip) < 1e-4f ? 1e-4f : rootToTip;
                float tip01 = saturate((v.vertex.y - _RootLocalY) / rootToTip);
                float3 localPos = v.vertex.xyz;
                float underlay = saturate(_FoamUnderlay);
                float outlineShell = _FoamUnderlay > 1.5f ? 1.0f : 0.0f;
                float tipSpread = smoothstep(0.22f, 1.0f, tip01);
                float yCenter = lerp(_RootLocalY, _TipLocalY, 0.42f);
                localPos.y = yCenter + (localPos.y - yCenter) * (1.0f + outlineShell * (_UnderlayExpand * 0.34f + _UnderlayTipExpand * 0.22f));
                localPos.xz *= 1.0f + underlay * (_UnderlayExpand + _UnderlayTipExpand * tipSpread);
                float clawBoost = _ClawSizeBoost > 0.001f ? _ClawSizeBoost : 1.0f;
                float3 worldPos = TransformPoint(data, localPos * clawBoost);
                o.pos = mul(UNITY_MATRIX_VP, float4(worldPos, 1.0f));
                o.worldNormal = TransformNormal(data, v.normal);
                o.score = saturate(data.params.x);
                o.worldPos = worldPos;
                o.tip01 = tip01;
                o.life = saturate(data.params.y);
                o.growth = saturate(data.params.w);
                o.random01 = saturate(data.params.z);
                o.uv = v.uv;
                o.screenUv = o.pos.xy / max(o.pos.w, 0.0001f) * 0.5f + 0.5f;
#else
                o.pos = UnityObjectToClipPos(v.vertex);
                o.worldNormal = UnityObjectToWorldNormal(v.normal);
                o.score = 0.0f;
                o.worldPos = mul(unity_ObjectToWorld, v.vertex).xyz;
                float rootToTip = _TipLocalY - _RootLocalY;
                rootToTip = abs(rootToTip) < 1e-4f ? 1e-4f : rootToTip;
                o.tip01 = saturate((v.vertex.y - _RootLocalY) / rootToTip);
                o.life = 1.0f;
                o.growth = 1.0f;
                o.random01 = 0.0f;
                o.uv = v.uv;
                o.screenUv = o.pos.xy / max(o.pos.w, 0.0001f) * 0.5f + 0.5f;
#endif
                return o;
            }

            fixed4 frag(v2f i, fixed facing : VFACE) : SV_Target
            {
                if (_VisibleRibbonGate > 0.5f)
                {
                    float nx = (i.screenUv.x - _VisibleRibbonParams.x) / max(_VisibleRibbonParams.z, 0.001f);
                    float arcY = _VisibleRibbonParams.y
                        + _VisibleRibbonShape.x * (1.0f - saturate(nx * nx))
                        + _VisibleRibbonShape.y * nx;
                    float distToRibbon = abs(i.screenUv.y - arcY);
                    float insideX = 1.0f - smoothstep(1.0f, 1.14f, abs(nx));
                    float insideY = 1.0f - smoothstep(_VisibleRibbonParams.w, _VisibleRibbonParams.w + _VisibleRibbonShape.z, distToRibbon);
                    if (insideX * insideY < 0.035f)
                        discard;
                }

                if (i.random01 > _VisibleFraction)
                    discard;

                float3 n = normalize(i.worldNormal);
                if (facing < 0.0f)
                    n = -n;
                float3 l = normalize(_WorldSpaceLightPos0.xyz);
                float3 v = normalize(_WorldSpaceCameraPos - i.worldPos);
                float ndotl = saturate(dot(n, l));

                // 白波の明部をクリーム色、暗部を淡青色の二段階で塗る。
                // 滑らかな階調を使わず、海面の木版画表現に合わせる。
                float litBand = step(0.35f, ndotl);
                float tint = saturate(i.score * _ScoreTintStrength);
                float rootBlend = smoothstep(0.0f, max(_RootFadeWidth, 0.001f), i.tip01);
                float3 paperWhite = float3(1.0f, 0.988f, 0.935f);
                float3 creamColor = lerp(_BaseColor.rgb, _TipColor.rgb, tint);
                creamColor = lerp(creamColor, paperWhite, saturate(0.38f + rootBlend * 0.42f + i.score * 0.12f));
                float3 rootColor = lerp(_RootBlendColor.rgb, creamColor * _ShadowTint.rgb, 0.30f);
                float3 foamColor = lerp(rootColor, creamColor, rootBlend);

                if (_FoamUnderlay > 0.5f)
                {
                    bool outlineUnderlay = _FoamUnderlay > 1.5f;
                    float scoreGate = lerp(0.42f, 1.0f, smoothstep(_UnderlayScoreFloor, 1.0f, i.score));
                    float lifeGate = smoothstep(0.006f, 0.14f, i.life);
                    float growthGate = smoothstep(0.00f, 0.18f, i.growth);
                    float underlayLifeFront = smoothstep(i.tip01 * 0.46f - 0.10f, i.tip01 * 0.46f + 0.24f, i.life);
                    float underlayWidth01 = abs(i.uv.x - 0.5f) * 2.0f;
                    float underlayNoise = saturate(sin(i.uv.y * 47.0f + i.uv.x * 19.0f) * 0.5f + 0.5f);
                    float underlayEdgeLife = smoothstep(0.02f, 0.36f, i.life - underlayWidth01 * 0.050f - underlayNoise * 0.025f);
                    float rootGate = lerp(_RootAlpha, 1.0f, rootBlend);
                    float shadowSide = smoothstep(0.42f, 1.0f, i.uv.x);
                    float printShadowPlate = smoothstep(0.05f, 0.36f, i.tip01)
                        * (1.0f - smoothstep(0.84f, 1.0f, i.tip01));
                    float alpha = _UnderlayAlpha
                        * scoreGate
                        * lifeGate
                        * lerp(0.12f, 1.0f, growthGate)
                        * lerp(0.46f, 1.0f, underlayLifeFront)
                        * lerp(0.56f, 1.0f, underlayEdgeLife)
                        * rootGate
                        * lerp(0.58f, 1.08f, printShadowPlate)
                        * lerp(0.56f, 1.0f, shadowSide)
                        * (1.0f - smoothstep(0.92f, 1.0f, underlayWidth01) * 0.36f);
                    if (outlineUnderlay)
                    {
                        float outlineAlpha = _UnderlayAlpha
                            * scoreGate
                            * lifeGate
                            * lerp(0.48f, 1.0f, growthGate)
                            * rootGate
                            * smoothstep(0.02f, 0.92f, i.tip01)
                            * (1.0f - smoothstep(0.98f, 1.0f, underlayWidth01) * 0.16f);
                        return float4(_UnderlayColor.rgb, saturate(outlineAlpha * _VisibleAlpha));
                    }
                    float shadowFoot = 1.0f - smoothstep(0.18f, 0.92f, i.tip01);
                    float3 waveGreen = lerp(_RootBlendColor.rgb, _GreenShadowColor.rgb, saturate(0.48f + shadowFoot * 0.34f));
                    float3 underlayColor = lerp(_UnderlayColor.rgb, waveGreen, saturate(_GreenShadowStrength) * saturate(0.30f + shadowFoot * 0.48f));
                    alpha *= lerp(0.64f, 1.0f, saturate(_GreenShadowStrength));
                    return float4(underlayColor, alpha * _VisibleAlpha);
                }

                // 指状部分は紙のように平坦に見せる。法線に応じた強い色帯を付けると、
                // 透過メッシュが北斎風の白波ではなく、多面体の結晶に見えてしまう。
                float sideBlue = (1.0f - rootBlend) * 0.22f
                               + smoothstep(0.18f, 0.92f, i.tip01) * (1.0f - ndotl) * 0.08f;
                float3 lit = lerp(foamColor, foamColor * _ShadowTint.rgb, saturate(sideBlue));

                float paperMottle = frac(sin(dot(floor(i.worldPos.xz * 0.18f), float2(12.9898f, 78.233f))) * 43758.5453f);
                lit *= lerp(0.96f, 1.015f, paperMottle) * lerp(0.985f, 1.0f, rootBlend);
                float width01 = abs(i.uv.x - 0.5f) * 2.0f;
                float printGreenShade = (1.0f - rootBlend) * 0.26f
                    + smoothstep(0.08f, 0.72f, i.tip01) * (1.0f - smoothstep(0.62f, 1.0f, width01)) * 0.10f;
                float sideShadowPlate = smoothstep(0.50f, 1.0f, i.uv.x)
                    * smoothstep(0.08f, 0.74f, i.tip01)
                    * (1.0f - smoothstep(0.92f, 1.0f, i.tip01));
                lit = lerp(lit, _GreenShadowColor.rgb, saturate((printGreenShade + sideShadowPlate * 0.16f) * _GreenShadowStrength * 0.58f));
                float leafEdge = 1.0f - smoothstep(0.78f, 1.0f, width01);
                float brushNoise = sin(i.uv.y * 53.0f + i.uv.x * 17.0f) * 0.5f
                                 + sin(i.uv.y * 137.0f + 2.1f) * 0.5f;
                float brushAlpha = lerp(0.78f, 1.0f, saturate(brushNoise * 0.5f + 0.5f));
                float dissolveNoise = saturate(sin(i.uv.y * 91.0f + i.uv.x * 37.0f + paperMottle * 6.2831853f) * 0.5f + 0.5f);

                // 原画の白波の墨線に倣い、外形に濃い藍色の縁取りを付ける。
                float rim = 1.0f - saturate(dot(n, v));
                float outline = smoothstep(_RimStart, saturate(_RimStart + 0.16f), rim);
                float tipInk = smoothstep(0.42f, 0.92f, i.tip01);
                // 爪状白波は寿命の最後まで形として見えるため、縁取りは細い木版画の墨線に留める。
                // 以前の縁幅8倍と下限0.6では全体が黒い刃のように塗られたため、細線へ戻した。
                float growthInk = max(smoothstep(0.04f, 0.55f, i.growth), smoothstep(0.00f, 0.16f, i.growth) * 0.68f);
                float edgeInk = smoothstep(1.0f - _ContourLineWidth * 4.4f, 1.0f, width01);
                float centerRidgeInk = (1.0f - smoothstep(0.0f, _ContourLineWidth * 1.35f, abs(i.uv.x - 0.5f)))
                    * smoothstep(0.16f, 0.88f, i.tip01)
                    * (1.0f - smoothstep(0.90f, 1.0f, i.tip01));
                float carvedLineCoord = i.uv.y * 4.8f - i.uv.x * 1.65f + sin(i.uv.y * 12.0f + i.uv.x * 2.4f) * 0.07f;
                float carvedLine = (1.0f - smoothstep(0.0f, _ContourLineWidth * 0.58f, abs(frac(carvedLineCoord) - 0.5f)))
                    * smoothstep(0.20f, 0.96f, i.tip01)
                    * (1.0f - smoothstep(0.44f, 0.96f, width01));
                float woodblockContour = saturate(edgeInk * 1.45f + centerRidgeInk * 0.16f + carvedLine * 0.18f) * _ContourLineStrength;
                float outlineRoot = lerp(0.70f, 1.0f, rootBlend);
                float outlineAmount = saturate(outline * 0.22f + woodblockContour * 0.92f) * _OutlineStrength * outlineRoot * smoothstep(0.01f, 0.99f, i.tip01) * growthInk;
                float printedEdgeInk = edgeInk * _OutlineStrength * _ContourLineStrength * 0.55f * lerp(0.48f, 0.92f, rootBlend) * smoothstep(0.03f, 0.98f, i.tip01) * growthInk;
                lit = lerp(lit, _OutlineColor.rgb, outlineAmount);

                // 白波の内側の短い彫り跡と縁の小さな欠けにより、
                // 大きな指状部分が整いすぎたベクター画像に見えるのを防ぐ。
                float cutCoord = i.uv.y * 4.4f - i.uv.x * 1.35f + sin(i.uv.y * 15.0f + i.uv.x * 3.0f) * 0.07f;
                float cutCenter = abs(frac(cutCoord) - 0.5f);
                float foamCut = 1.0f - smoothstep(0.0f, 0.038f, cutCenter);
                float cutGate = smoothstep(0.24f, 0.92f, i.tip01)
                              * (1.0f - smoothstep(0.78f, 1.0f, width01))
                              * growthInk;
                float3 cutColor = lerp(_RootBlendColor.rgb, _OutlineColor.rgb, 0.26f);
                lit = lerp(lit, cutColor, saturate(foamCut * cutGate * _FoamCutStrength * (0.10f + _ContourLineStrength * 0.08f)));

                float scallopWave = sin(i.uv.y * 38.0f + (i.uv.x > 0.5f ? 1.7f : 0.0f));
                float edgeBand = smoothstep(0.70f, 1.0f, width01);
                float edgeBite = smoothstep(0.25f, 0.95f, scallopWave * 0.5f + 0.5f)
                               * edgeBand
                               * smoothstep(0.12f, 0.95f, i.tip01)
                               * (1.0f - smoothstep(0.96f, 1.0f, i.tip01))
                               * growthInk
                               * _EdgeScallopStrength;
                lit = lerp(lit, _OutlineColor.rgb, edgeBite * _OutlineStrength * (0.12f + _ContourLineStrength * 0.10f));

                float growthAlpha = smoothstep(-0.02f, 0.72f, i.growth);
                float rootToTipReveal = smoothstep(i.tip01 - 0.18f, i.tip01 + 0.22f, i.growth);
                float lifeRootToTip = smoothstep(i.tip01 * 0.58f - 0.08f, i.tip01 * 0.58f + 0.24f, i.life);
                // 出現時の不透明度の下限を上げる。砕波は短く、寿命と成長の値は約0.3までしか
                // 上がらない。以前は alpha が約0.02まで下がり、爪状白波がほぼ見えなかった。
                // 下限を上げると、生成直後から見えつつ、成長に伴う濃淡はわずかに残せる。
                float revealAlpha = lerp(0.80f, 1.0f, growthAlpha)
                    * lerp(0.78f, 1.0f, rootToTipReveal)
                    * lerp(0.74f, 1.0f, lifeRootToTip);
                float lifeAlpha = smoothstep(0.006f, 0.24f, i.life);
                float edgeLifeDelay = width01 * 0.10f + i.tip01 * 0.045f + dissolveNoise * 0.055f;
                float edgeGrowthDelay = width01 * 0.070f + dissolveNoise * 0.035f;
                float lifeEdgeDissolve = smoothstep(0.02f, 0.72f, i.life - edgeLifeDelay);
                float growthEdgeDissolve = smoothstep(-0.03f, 0.66f, i.growth - edgeGrowthDelay);
                float carvedDissolve = lerp(0.42f, 1.0f, lifeEdgeDissolve) * lerp(0.66f, 1.0f, growthEdgeDissolve);
                float alpha = lerp(_RootAlpha, 0.92f, rootBlend) * lifeAlpha * revealAlpha * lerp(0.84f, 1.0f, leafEdge) * brushAlpha;
                float printPlateLife = smoothstep(0.006f, 0.13f, i.life);
                float printPlateGrowth = smoothstep(0.00f, 0.20f, i.growth);
                float printPlateAlpha = lerp(_RootAlpha, 0.92f, rootBlend)
                    * printPlateLife
                    * lerp(0.48f, 1.0f, printPlateGrowth)
                    * lerp(0.78f, 1.0f, leafEdge)
                    * brushAlpha;
                alpha = max(alpha, printPlateAlpha * lerp(0.82f, 1.0f, carvedDissolve));
                float bodyFill = (1.0f - smoothstep(0.94f, 1.0f, width01))
                    * smoothstep(0.006f, 0.12f, i.life)
                    * smoothstep(0.00f, 0.18f, i.growth);
                float paperFillAlpha = lerp(_RootAlpha, 0.98f, rootBlend) * bodyFill * brushAlpha;
                alpha = max(alpha, paperFillAlpha);
                alpha *= lerp(0.82f, 1.0f, carvedDissolve);
                alpha = max(alpha, paperFillAlpha * 0.92f);
                alpha = max(alpha, printedEdgeInk * 0.82f);
                alpha *= 1.0f - edgeBite * 0.20f;
                return float4(lit, alpha * _VisibleAlpha);
            }
            ENDCG
        }
    }
}
