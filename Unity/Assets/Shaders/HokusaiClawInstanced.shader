Shader "MasterProject/HokusaiClawInstanced"
{
    Properties
    {
        // Ukiyo-e foam palette: the claws ARE foam, so they default to flat paper-cream
        // with a pale blue shadow side and a dark indigo ink rim, matching the ocean shader.
        // 浮世绘泡沫配色：爪形本身就是浪花，默认旧纸奶油色，暗部偏淡蓝，外缘深蓝描线，与海面风格一致。
        _BaseColor ("Base Color (foam cream)", Color) = (0.93, 0.91, 0.84, 1)
        _TipColor ("High Score Color", Color) = (0.98, 0.97, 0.93, 1)
        _RootBlendColor ("Root Blend Water Color", Color) = (0.50, 0.66, 0.74, 1)
        _ShadowTint ("Shadow Side Tint", Color) = (0.62, 0.73, 0.78, 1)
        _OutlineColor ("Outline Ink Color", Color) = (0.027, 0.067, 0.125, 1)
        _OutlineStrength ("Outline Strength", Range(0, 1)) = 0.58
        _RimStart ("Outline Rim Start", Range(0.1, 0.95)) = 0.76
        _ContourLineStrength ("Woodblock Contour Line Strength", Range(0, 1)) = 0.72
        _ContourLineWidth ("Woodblock Contour Line Width", Range(0.005, 0.18)) = 0.055
        _GreenShadowColor ("Wave Green Shadow Color", Color) = (0.43, 0.64, 0.54, 1)
        _GreenShadowStrength ("Wave Green Shadow Strength", Range(0, 1)) = 0.68
        _VisibleFraction ("Visible Claw Fraction", Range(0, 1)) = 1
        _VisibleAlpha ("Visible Claw Alpha", Range(0, 1)) = 1
        _VisibleRibbonGate ("Visible Ribbon Gate", Range(0, 1)) = 0
        _VisibleRibbonParams ("Visible Ribbon Params", Vector) = (0.5, 0.5, 0.24, 0.08)
        _VisibleRibbonShape ("Visible Ribbon Shape", Vector) = (0.08, 0.0, 0.06, 0)
        _Ambient ("Ambient", Range(0, 1)) = 0.55
        _LightStrength ("Light Strength", Range(0, 3)) = 0.85
        _ScoreTintStrength ("Score Tint Strength", Range(0, 1)) = 0.65
        _RootFadeWidth ("Root Fade Width", Range(0.02, 0.8)) = 0.26
        _RootAlpha ("Root Alpha", Range(0, 1)) = 0.18
        _FoamCutStrength ("Foam Interior Cut Strength", Range(0, 1)) = 0.28
        _EdgeScallopStrength ("Foam Edge Scallop Strength", Range(0, 1)) = 0.24
        _FoamUnderlay ("Foam Ribbon Underlay", Range(0, 1)) = 0
        _UnderlayColor ("Underlay Foam Color", Color) = (0.96, 0.93, 0.82, 1)
        _UnderlayAlpha ("Underlay Alpha", Range(0, 1)) = 0.36
        _UnderlayExpand ("Underlay Width Expand", Range(0, 2)) = 0.65
        _UnderlayTipExpand ("Underlay Tip Expand", Range(0, 2)) = 0.40
        _UnderlayScoreFloor ("Underlay Score Floor", Range(0, 1)) = 0.22
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
            float _ClawSizeBoost; // runtime size multiply (0/unset -> treated as 1). The compute normalizes
                                  // clawScaleRange/backgroundClawScale to a ~fixed per-instance scale, so this
                                  // is the only reliable lever to enlarge the rendered claw without a respawn.
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

                // Flat two-band foam shading: lit side cream, shadow side pale blue —
                // no smooth gradient, matching the woodblock ocean shader.
                // 平涂两档明暗：亮面奶油色，暗面淡蓝，无渐变，与海面版画风格一致。
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

                // Keep the fingers paper-flat. Strong normal bands make the transparent
                // mesh read as faceted crystal instead of Hokusai-style foam.
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

                // Dark indigo ink rim around the silhouette, like the painting's outlines.
                // 轮廓处的深蓝描线，模拟画中泡沫的勾线。
                float rim = 1.0f - saturate(dot(n, v));
                float outline = smoothstep(_RimStart, saturate(_RimStart + 0.16f), rim);
                float tipInk = smoothstep(0.42f, 0.92f, i.tip01);
                // Thin tasteful ink line only — claws now reach full life (visible on their own), so the
                // outline is a delicate woodblock contour, NOT a solid fill. The earlier 8x edge band +
                // 0.6 floor turned the whole claw into ink (it read as a black blade). Back to a hairline.
                // 仅细淡墨线——爪形现已涨到满 life（本身就可见），描边只作精致的版画勾线，而非整片填墨。
                // 之前 8x 边带+0.6 下限把整个爪身染成墨色（看着像黑刀片），改回发丝级细线。
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

                // Short carved cuts inside the foam and tiny bites along the edge keep
                // large fingers from reading as clean vector leaves.
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
                // Reveal floors RAISED: the wave breaking is transient so life/growth ramp only to
                // ~0.3, which previously multiplied alpha down to ~0.02 (claws nearly invisible — the
                // real reason no claws were seen). High floors keep claws clearly visible once spawned
                // while still letting the grow-in animation modulate alpha subtly.
                // 渐入下限提高：波峰破碎是瞬时的，life/growth 只涨到 ~0.3，旧下限把 alpha 压到 ~0.02
                // (几乎透明——这才是看不到爪形的真正原因)。提高下限让爪形生成后就清晰可见。
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
