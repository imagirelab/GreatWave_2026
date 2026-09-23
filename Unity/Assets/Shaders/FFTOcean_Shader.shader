Shader "MasterProject/FFTOcean_Shader"
{
    //细分相关计算
    CGINCLUDE
    int _TessEdgeLength;

    struct TessellationFactors{
        float edge[3] : SV_TESSFACTOR;
        float inside : SV_INSIDETESSFACTOR;
    };

    //细分启动式
    float TessellationHeuristic(float3 cp1, float3 cp2){
        float edgeLength = distance(cp1, cp2);
        float3 edgeCenter = (cp1 + cp2) * 0.5;
        float viewDistance = distance(edgeCenter, _WorldSpaceCameraPos);

        // Unclamped this hits the hardware max (64x) whenever the camera nears the surface,
        // exploding triangle throughput exactly when the rest of the frame is heaviest.
        // 不加上限时，相机贴近水面会直接顶到硬件 64 倍细分，几何量在帧最重的时刻爆炸，这里限制到 32。
        return clamp(edgeLength * _ScreenParams.y / (_TessEdgeLength * pow(viewDistance * 0.5f, 1.2f)), 1.0f, 32.0f);
    }

    bool TriIsBelowClip (float3 p0, float3 p1, float3 p2, int planeIndex, float bias){
        float4 clipPlane = unity_CameraWorldClipPlanes[planeIndex];

        return dot(float4(p0, 1), clipPlane) < bias && dot(float4(p1, 1), clipPlane) < bias && dot(float4(p2, 1), clipPlane) < bias;
    }

    bool cullTriangle (float3 p0, float3 p1, float3 p2, float bias){
        return TriIsBelowClip(p0, p1, p2, 0, bias) ||
                TriIsBelowClip(p0, p1, p2, 1, bias) ||
                TriIsBelowClip(p0, p1, p2, 2, bias) ||
                TriIsBelowClip(p0, p1, p2, 3, bias);
    }

    ENDCG

    Properties
    {

    }
    SubShader
    {
        //基础着色pass
        pass{
            Tags { "LightMode" = "ForwardBase" }
            Tags { "RenderType"="Opaque" }
            LOD 200

            CGPROGRAM
            #pragma target 5.0
            #pragma multi_compile_fwdbase

            #include "UnityPBSLighting.cginc"
            #include "AutoLight.cginc"

            // The previous pass-through geometry stage only forwarded unused barycentric
            // coordinates while forcing every tessellated triangle through an extra pipeline
            // stage on the 1.2 km ocean - removed to cut GPU geometry cost.
            // 之前的 geometry shader 只透传了从未使用的重心坐标，却让全部细分三角形多走一个
            // 流水线阶段，已移除以降低 GPU 几何开销。
            #pragma vertex vert
            #pragma hull hull
            #pragma domain domain
            #pragma fragment frag

            UNITY_DECLARE_TEX2DARRAY(_DisplacementTexture);
            UNITY_DECLARE_TEX2DARRAY(_SlopeTexture);
            UNITY_DECLARE_TEX2D(_VariationMask);
            sampler2D _ClawMaskTexture;

            sampler2D _CameraDepthNormalsTexture;

            float _DisplaceDepthAttenuation, _FoamDepthAttenuation;

            float _Tile0, _Tile1, _Tile2, _Tile3, _LayerContribute0, _LayerContribute1, _LayerContribute2, _LayerContribute3;

            float _NormalStrength, _HeightStrength;
            float _VerticalDisplacementStrength, _HorizontalDisplacementStrength, _CrestAmplification;

            float3 _ScatterColor, _ScatterPeakColor, _FoamColor, _AmbientColor, _FogColor;

            float _AmbientDensity;

            float _WavePeakScatterStrength, _ScatterStrength, _ScatterShadowStrength;

            float _FoamRoughness, _Roughness, _EnvirLightStrength;

            float _EdgeFoamPower, _ShadowIntensity, _FogDensity, _FogPower;

            float _VarMaskRange, _VarMaskPower, _VarMaskTexScale;

            // Ukiyo-e woodblock style / 浮世绘版画风格参数（由 FFTOcean_Script.SetMaterialParam 上传）
            float3 _DeepInkColor, _MidWaterColor, _PaleWaterColor, _FoamCreamColor, _OutlineInkColor;
            float _ToonBands, _OutlineStrength, _OutlineWidth, _FoamCutoff, _FoamEdgeSoftness;
            float _PrintMottle, _LightInfluence, _HeightShadeScale, _SteepShadeScale;
            float _PrintLineStrength, _PrintLineScale, _PrintLineFoamSuppression, _CrestLineStrength;
            float _PrintStripeStrength, _PrintStripeScale, _PrintStripeWarp, _CrestWhiteBoost, _CrestWhiteThreshold;
            float _PrintStripeFaceGate, _PrintStripeGateBright, _PrintStripeBokashi;
            float _CrestCurlLineStrength, _CrestCurlLineScale;
            float _FoamContourStrength, _FoamContourScale, _FoamScallopStrength, _FoamScallopScale;
            float _FoamPocketStrength, _FoamCombStrength, _FoamCombScale, _FoamStriationStrength, _FoamStriationScale;
            float _HokusaiDebugView;
            // Ukiyo-e LINE WORK / 描边 — Brown & Arandjelovic (Sci 2020) §2.1 important edges,
            // adapted to a real-time screen-space detector on _CameraDepthNormalsTexture:
            // silhouette = depth discontinuity, crease = view-normal discontinuity.
            float _NprOutlineStrength, _NprSilhouetteThreshold, _NprCreaseThreshold, _NprCreaseStrength, _NprOutlineWidth;
            float _NprGrazeThreshold, _NprWaveEdgeStrength;
            float _NprBandContourStrength, _NprBandContourWidth, _NprContourCount;
            float _NprFoamOutlineStrength, _NprFoamOutlineWidth;
            float _NprPaperStrength, _NprPaperScale, _NprPaperFollow;
            float _NprPaperWorld, _NprPaperWorldFreq;
            float _NprBokashiStrength;
            float _NprCrestOutlineStrength, _NprCrestOutlineThresh;
            float _NprCreaseNStrength, _NprCreaseNThresh, _NprCreaseNFine;
            float _NprLodNear, _NprLodFar, _NprLodGamma;
            float _NprStrokeVary, _NprStrokeScale, _NprStrokeGap;
            float _NprStrokeTaper, _NprStrokeTaperHeight;
            float _NprFoamProxyLo, _NprFoamProxyWidth, _NprFoamNormalUp;
            // Live-tunable foam-mask shaping (global-fed): _FoamSmoothScale boosts the box-blurred breaking
            // signal back up (averaging weakens it), _FoamCut is the white-shape threshold on that smooth field,
            // _FoamJFloor floors the noisy per-texel Jacobian so foam follows the SMOOTH crest gates (1 = pure
            // clean crest-driven, 0 = breaking-gated/holey). _FoamJFloor is THE square-hole fix.
            float _FoamCut, _FoamSmoothScale, _FoamJFloor;

            struct a2h
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
                float3 normal : NORMAL;
                float4 _ShadowCoord : TEXCOORD1;
            };

            struct h2d
            {
                float4 vertex : INTERNALTESSPOS;
                float2 uv : TEXCOORD0;
                float3 normal : NORMAL;
                float4 _ShadowCoord : TEXCOORD1;
            };

            struct v2g
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
                float3 worldPos : TEXCOORD1;
                float3 worldNormal : TEXCOORD2;
                float clipDepth : TEXCOORD3;
                float viewDepth : TEXCOORD4;
                float2 screenUV : TEXCOORD5;
                float4 _ShadowCoord : TEXCOORD6;
            };

            h2d vert(a2h h)
            {
                h2d d;
                d.vertex = h.vertex;
                d.uv = h.uv;
                d.normal = h.normal;
                d._ShadowCoord = h._ShadowCoord;

                return d;
            }

            float DotClamped(float3 a, float3 b) {
                return saturate(dot(a, b));
            }

            v2g vp(h2d d)
            {
                v2g g;

                g.worldPos = mul(unity_ObjectToWorld, d.vertex);

                float3 displacement0 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(g.worldPos.xz * _Tile0, 0), 0) * _LayerContribute0;
                float3 displacement1 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(g.worldPos.xz * _Tile1, 1), 0) * _LayerContribute1;
                float3 displacement2 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(g.worldPos.xz * _Tile2, 2), 0) * _LayerContribute2;
                float3 displacement3 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(g.worldPos.xz * _Tile3, 3), 0) * _LayerContribute3;
                float3 displacement = displacement0 + displacement1 + displacement2 + displacement3;

                displacement.xz *= _HorizontalDisplacementStrength;
                displacement.y = displacement.y * _VerticalDisplacementStrength
                               + max(0.0f, displacement.y) * max(0.0f, displacement.y) * _CrestAmplification;

                float4 clipPos = UnityObjectToClipPos(d.vertex);
                float clipDepth = 1 - Linear01Depth(clipPos.z / clipPos.w);

                displacement = lerp(0.0f, displacement, pow(saturate(clipDepth), _DisplaceDepthAttenuation));
                d.vertex.xyz += mul(unity_WorldToObject, displacement.xyz);

                clipPos = UnityObjectToClipPos(d.vertex);
                float2 screenUV = ((clipPos.xy / clipPos.w) + 1) / 2;
                screenUV.y = 1 - screenUV.y;
                float viewDepth = -mul(UNITY_MATRIX_MV, d.vertex).z * _ProjectionParams.w;

                g.pos = UnityObjectToClipPos(d.vertex);
                g.worldNormal = normalize(mul((float3x3)unity_ObjectToWorld, d.normal));
                g.uv = g.worldPos.xz;
                g.clipDepth = clipDepth;
                g.viewDepth = viewDepth;
                g.screenUV = screenUV;

                TRANSFER_SHADOW(g);

                return g;
            }

            TessellationFactors PatchFunction(InputPatch < h2d, 3 > patch)
            {
                TessellationFactors f;

                float3 p0 = mul(unity_ObjectToWorld, patch[0].vertex);
                float3 p1 = mul(unity_ObjectToWorld, patch[1].vertex);
                float3 p2 = mul(unity_ObjectToWorld, patch[2].vertex);

                float bias = -0.5 * 100;

                if(cullTriangle(p0, p1, p2, bias))
                {
                    f.edge[0] = f.edge[1] = f.edge[2] = f.inside = 0;
                }else{
                    f.edge[0] = TessellationHeuristic(p1, p2);
                    f.edge[1] = TessellationHeuristic(p2, p0);
                    f.edge[2] = TessellationHeuristic(p0, p1);
                    f.inside = (TessellationHeuristic(p1, p2) +
                                TessellationHeuristic(p2, p0) +
                                TessellationHeuristic(p0, p1)) * (1.0f / 3.0f);
                }

                return f;
            }

            [UNITY_domain("tri")]
            [UNITY_outputcontrolpoints(3)]
            [UNITY_outputtopology("triangle_cw")]
            [UNITY_partitioning("integer")]
            [UNITY_patchconstantfunc("PatchFunction")]

            h2d hull(InputPatch < h2d, 3 > patch, uint id : SV_OUTPUTCONTROLPOINTID)
            {
                return patch[id];
            }

            #define DP_INTERPOLATE(fieldName) data.fieldName = \
                                     patch[0].fieldName * barycentricCoordinates.x + \
                                     patch[1].fieldName * barycentricCoordinates.y + \
                                     patch[2].fieldName * barycentricCoordinates.z;


            [UNITY_domain("tri")]
            v2g domain(TessellationFactors factors, OutputPatch < h2d, 3 > patch, float3 barycentricCoordinates : SV_DOMAINLOCATION)
            {
                a2h data = (a2h)0;
                DP_INTERPOLATE(vertex)
                DP_INTERPOLATE(uv)
                DP_INTERPOLATE(normal)
                DP_INTERPOLATE(_ShadowCoord)

                return vp(data);
            }

            float ComputeExpFogFactor(float depth, float density)
            {
                return saturate(pow(1.0 - exp(-depth * density), _FogPower));
            }

            float SampleWaveHeightAt(float2 worldXZ)
            {
                float h0 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldXZ * _Tile0, 0), 0).y * _LayerContribute0;
                float h1 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldXZ * _Tile1, 1), 0).y * _LayerContribute1;
                float h2 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldXZ * _Tile2, 2), 0).y * _LayerContribute2;
                float h3 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldXZ * _Tile3, 3), 0).y * _LayerContribute3;
                // Return VISIBLE height so ridge detection matches the displaced geometry.
                // 返回可见高度，使脊线检测与实际抬高的几何一致。
                return (h0 + h1 + h2 + h3) * max(_VerticalDisplacementStrength, 1.0f);
            }

            float SampleWaveFoamAt(float2 worldXZ)
            {
                float f0 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldXZ * _Tile0, 0), 0).a * _LayerContribute0;
                float f1 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldXZ * _Tile1, 1), 0).a * _LayerContribute1;
                float f2 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldXZ * _Tile2, 2), 0).a * _LayerContribute2;
                float f3 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldXZ * _Tile3, 3), 0).a * _LayerContribute3;
                return saturate(f0 + f1 + f2 + f3);
            }

            float SampleClawScoreAt(float2 worldXZ)
            {
                return tex2D(_ClawMaskTexture, frac(worldXZ * _Tile0)).a;
            }

            // Cheap 2D hash -> [0,1], for the scattered Hokusai spray dots.
            float Hash2(float2 p)
            {
                p = frac(p * float2(123.34f, 456.21f));
                p += dot(p, p + 45.32f);
                return frac(p.x * p.y);
            }

            // Smooth 2D value noise (smoothstep-interpolated hash lattice) -> [0,1], for the woodblock
            // ink/paper grain of Brown & Arandjelovic (Sci 2020) §2.2.1. Two octaves for a paper-like feel.
            float ValueNoise(float2 p)
            {
                float2 ip = floor(p);
                float2 fp = frac(p);
                fp = fp * fp * (3.0f - 2.0f * fp);
                float a = Hash2(ip + float2(0.0f, 0.0f));
                float b = Hash2(ip + float2(1.0f, 0.0f));
                float c = Hash2(ip + float2(0.0f, 1.0f));
                float d = Hash2(ip + float2(1.0f, 1.0f));
                return lerp(lerp(a, b, fp.x), lerp(c, d, fp.x), fp.y);
            }
            float PaperNoise(float2 p)
            {
                return ValueNoise(p) * 0.65f + ValueNoise(p * 2.17f + 11.3f) * 0.35f;
            }

            float4 frag(v2g i) : SV_TARGET
            {
                float3 worldPos = i.worldPos;
                float3 worldNormal = i.worldNormal;
                float clipDepth = i.clipDepth;
                float viewDepth = i.viewDepth;
                float2 screenUV = i.screenUV;

                fixed shadow = SHADOW_ATTENUATION(i);

                float screenDepth = DecodeFloatRG(tex2D(_CameraDepthNormalsTexture, screenUV).zw);
                float depthDiff =  screenDepth - viewDepth;
                float intersect = 0;
                if(depthDiff > 0){
                    intersect = 1 - smoothstep(0, _ProjectionParams.w, depthDiff);
                }

                float4 displacementFoam0 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldPos.xz * _Tile0, 0), 0) * _LayerContribute0;
                float4 displacementFoam1 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldPos.xz * _Tile1, 1), 0) * _LayerContribute1;
                float4 displacementFoam2 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldPos.xz * _Tile2, 2), 0) * _LayerContribute2;
                float4 displacementFoam3 = UNITY_SAMPLE_TEX2DARRAY_LOD(_DisplacementTexture, float3(worldPos.xz * _Tile3, 3), 0) * _LayerContribute3;
                float4 displacementFoam = displacementFoam0 + displacementFoam1 + displacementFoam2 + displacementFoam3;

                float foam = lerp(0.0f, saturate(displacementFoam.a), pow(clipDepth, _FoamDepthAttenuation));
                foam = foam + intersect * pow(foam, _EdgeFoamPower);
                foam *= saturate(shadow + _ShadowIntensity);

                float2 slope0 = UNITY_SAMPLE_TEX2DARRAY_LOD(_SlopeTexture, float3(i.uv * _Tile0, 0), 0) * _LayerContribute0;
                float2 slope1 = UNITY_SAMPLE_TEX2DARRAY_LOD(_SlopeTexture, float3(i.uv * _Tile1, 1), 0) * _LayerContribute1;
                float2 slope2 = UNITY_SAMPLE_TEX2DARRAY_LOD(_SlopeTexture, float3(i.uv * _Tile2, 2), 0) * _LayerContribute2;
                float2 slope3 = UNITY_SAMPLE_TEX2DARRAY_LOD(_SlopeTexture, float3(i.uv * _Tile3, 3), 0) * _LayerContribute3;
                float2 slopeMixA = slope0 + slope1 + slope2 + slope3;
                float2 slopeMixB = slope2 + slope3;
                float slopeMagnitude = saturate(length(slopeMixA));
                // The vertex shader displaces geometry by displacement.y * _VerticalDisplacementStrength,
                // so a visually tall crest stores only a small raw value here. Detect on the VISIBLE
                // height or every gate stays calibrated for waves that never exist in frag space.
                // 顶点着色器把几何抬高了 displacement.y * _VerticalDisplacementStrength 倍，所以一道视觉上很高的
                // 波峰在这里的原始值很小。检测必须用“可见高度”，否则所有门控都按不存在的大浪标定，永远不触发。
                float visHeight = displacementFoam.y * max(_VerticalDisplacementStrength, 1.0f);
                float crestFace = saturate(slopeMagnitude * 0.42f + max(0.0f, visHeight) * 0.055f);
                // SMOOTHED slope for the FOAM GATE only (sharp slopeMagnitude still drives the water normal).
                // slopeMixB = slope2+slope3 = the two FINE cascades that carry the texel-scale detail which was
                // speckling the foam-cap edges; subtract most of them so the gate sees only the coarse slope.
                float slopeMagSmooth  = saturate(length(slopeMixA - slopeMixB * 0.80f));
                float crestFaceSmooth = saturate(slopeMagSmooth * 0.42f + max(0.0f, visHeight) * 0.055f);
                float waveWallEnergy = smoothstep(
                    0.12f,
                    0.58f,
                    crestFace + max(0.0f, visHeight) * _HeightShadeScale * 0.05f + slopeMagnitude * 0.16f);
                float highWaterEnergy = smoothstep(
                    0.08f,
                    0.46f,
                    saturate(max(0.0f, visHeight) * _HeightShadeScale * 0.07f) + crestFace * 0.44f + slopeMagnitude * 0.16f);
                float mainWavePrintGate = saturate(waveWallEnergy * lerp(0.55f, 1.0f, highWaterEnergy));
                float crestAreaGate = smoothstep(0.12f, 0.48f, mainWavePrintGate);

                float4 clawMask = tex2D(_ClawMaskTexture, frac(worldPos.xz * _Tile0));

                // Data-driven foam plate: only actual FFT foam, steep local maxima, and
                // claw-mask crest candidates can turn white. The mask is built in world
                // space from the same displacement texture that moves the water vertices.
                float hCenter = visHeight; // visible-height units, consistent with SampleWaveHeightAt
                float hX0 = SampleWaveHeightAt(worldPos.xz + float2(6.0f, 0.0f));
                float hX1 = SampleWaveHeightAt(worldPos.xz + float2(-6.0f, 0.0f));
                float hZ0 = SampleWaveHeightAt(worldPos.xz + float2(0.0f, 6.0f));
                float hZ1 = SampleWaveHeightAt(worldPos.xz + float2(0.0f, -6.0f));

                float2 heightGradient = float2(hX0 - hX1, hZ0 - hZ1);
                float gradLenSq = max(dot(heightGradient, heightGradient), 0.00001f);
                float2 ridgeNormalDir = heightGradient * rsqrt(gradLenSq);
                float2 ridgeTangentDir = float2(-ridgeNormalDir.y, ridgeNormalDir.x);

                float hN0 = SampleWaveHeightAt(worldPos.xz + ridgeNormalDir * 5.5f);
                float hN1 = SampleWaveHeightAt(worldPos.xz - ridgeNormalDir * 5.5f);
                float hT0 = SampleWaveHeightAt(worldPos.xz + ridgeTangentDir * 7.5f);
                float hT1 = SampleWaveHeightAt(worldPos.xz - ridgeTangentDir * 7.5f);
                float hT2 = SampleWaveHeightAt(worldPos.xz + ridgeTangentDir * 13.0f);
                float hT3 = SampleWaveHeightAt(worldPos.xz - ridgeTangentDir * 13.0f);
                float neighborPeak = max(max(hN0, hN1), max(max(hT0, hT1), max(hT2, hT3)));
                float neighborAverage = (hN0 + hN1 + hT0 + hT1 + hT2 + hT3) * 0.1666667f;
                float ridgeLift = (hCenter - neighborPeak) * max(_HeightShadeScale, 0.001f);
                float ridgeShoulderLift = (hCenter - neighborAverage) * max(_HeightShadeScale, 0.001f);
                float ridgeScore = smoothstep(0.012f, 0.115f, ridgeLift)
                    * smoothstep(0.08f, 0.40f, crestFace + slopeMagnitude * 0.12f);
                float ridgeShoulder = smoothstep(-0.026f, 0.090f, ridgeShoulderLift)
                    * smoothstep(0.10f, 0.44f, crestFace + slopeMagnitude * 0.14f);
                // CREST SELECTIVITY (user: 白色范围太大). Raised 0.10/0.48 -> 0.24/0.60 so only the STRONGER
                // crests qualify for foam -> fewer white caps, weak crests stay deep-blue. Reduces white
                // COVERAGE without shrinking each cap (which exposes pale-blue edges = the 浅蓝色亮面).
                // Cut 0.28/0.62 (user chose A: fewer big masses). Uses the SMOOTHED slope (crestFaceSmooth /
                // slopeMagSmooth) so the cap edges are clean, not texel-speckled. jFloor=1.0 keeps masses clean.
                float highCrestGate = smoothstep(
                    0.28f,
                    0.62f,
                    saturate(max(0.0f, visHeight) * _HeightShadeScale * 0.040f) + crestFaceSmooth * 0.42f + slopeMagSmooth * 0.08f);
                float3 roughLipNormal = normalize(float3(-slopeMixA.x, 1.0f, -slopeMixA.y));
                float3 roughViewDir = normalize(_WorldSpaceCameraPos.xyz - worldPos);
                float viewGrazingLip = smoothstep(0.32f, 0.78f, 1.0f - abs(dot(roughLipNormal, roughViewDir)));
                float viewLipGate = highCrestGate * smoothstep(0.05f, 0.42f, ridgeScore + ridgeShoulder * 0.56f + foam * 0.20f);
                float crestSilhouette = viewGrazingLip
                    * viewLipGate
                    * highCrestGate
                    * crestAreaGate
                    * smoothstep(0.16f, 0.52f, crestFace + ridgeShoulder * 0.48f + slopeMagnitude * 0.16f);
                float clawRidgeCandidate = smoothstep(0.62f, 1.05f, clawMask.a + clawMask.b * 0.54f)
                    * smoothstep(0.03f, 0.34f, ridgeScore + crestFace * 0.10f);
                float heightLip = viewLipGate * highCrestGate * saturate(max(ridgeScore, clawRidgeCandidate * 0.58f));
                float crestBand = viewLipGate
                    * highCrestGate
                    * crestAreaGate
                    * saturate(max(max(ridgeScore * 1.20f, ridgeShoulder * 0.64f), crestSilhouette * 0.84f));
                float crestSeedGate = saturate(max(heightLip * 1.12f, crestBand * 0.92f));
                float foamN0 = SampleWaveFoamAt(worldPos.xz + ridgeNormalDir * 3.8f);
                float foamN1 = SampleWaveFoamAt(worldPos.xz - ridgeNormalDir * 3.8f);
                float foamT0 = SampleWaveFoamAt(worldPos.xz + ridgeTangentDir * 5.5f);
                float foamT1 = SampleWaveFoamAt(worldPos.xz - ridgeTangentDir * 5.5f);
                float foamT2 = SampleWaveFoamAt(worldPos.xz + ridgeTangentDir * 10.0f);
                float foamT3 = SampleWaveFoamAt(worldPos.xz - ridgeTangentDir * 10.0f);
                float fftFoamDilation = max(max(max(foam, foamN0), max(foamN1, foamT0)), max(max(foamT1, foamT2), foamT3));
                float fftFoamSeed = smoothstep(0.18f, 0.58f, fftFoamDilation) * crestSeedGate;
                float localClawPattern = smoothstep(0.16f, 0.72f, clawMask.a + clawMask.b * 0.46f);
                float clawFoamSeed = localClawPattern
                    * smoothstep(0.10f, 0.58f, crestFace + foam * 0.36f + slopeMagnitude * 0.14f)
                    * crestSeedGate;
                float neighborA = SampleClawScoreAt(worldPos.xz + ridgeTangentDir * 5.5f);
                float neighborB = SampleClawScoreAt(worldPos.xz - ridgeTangentDir * 5.5f);
                float neighborC = SampleClawScoreAt(worldPos.xz + ridgeNormalDir * 3.8f);
                float neighborD = SampleClawScoreAt(worldPos.xz - ridgeNormalDir * 3.8f);
                float neighborE = SampleClawScoreAt(worldPos.xz + ridgeTangentDir * 10.0f);
                float neighborF = SampleClawScoreAt(worldPos.xz - ridgeTangentDir * 10.0f);
                float neighborClawFoam = max(max(max(neighborA, neighborB), max(neighborC, neighborD)), max(neighborE, neighborF));
                neighborClawFoam *= crestSeedGate;
                float crestRibbonSeed = crestBand * saturate(
                    0.08f
                    + localClawPattern * 0.34f
                    + smoothstep(0.16f, 0.56f, fftFoamDilation) * 0.34f
                    + ridgeScore * 0.34f);
                float foamSupport = smoothstep(0.22f, 0.58f, fftFoamDilation + localClawPattern * 0.34f + neighborClawFoam * 0.20f);
                float connectedFoamScore = saturate(
                    crestRibbonSeed * 0.82f
                    + fftFoamSeed * 0.78f
                    + clawFoamSeed * 0.50f
                    + neighborClawFoam * 0.36f
                    + ridgeScore * highCrestGate * foamSupport * 0.18f);
                connectedFoamScore *= highCrestGate * pow(saturate(clipDepth), 0.18f);
                float solidFoamBridge = smoothstep(0.22f, 0.74f, fftFoamSeed + crestRibbonSeed + ridgeScore * foamSupport * 0.34f + neighborClawFoam * 0.22f);
                float strongFoamCandidate = smoothstep(0.12f, 0.42f, connectedFoamScore + solidFoamBridge * 0.30f);
                float physicalCrestWhitePlate = smoothstep(0.12f, 0.34f, connectedFoamScore)
                    * strongFoamCandidate
                    * smoothstep(0.08f, 0.34f, crestSeedGate + fftFoamSeed * 0.32f + ridgeScore * 0.42f);
                float lipWhiteBridge = crestBand
                    * smoothstep(
                        0.24f,
                        0.62f,
                        ridgeScore * 0.72f
                        + crestSilhouette * 0.42f
                        + localClawPattern * 0.28f
                        + smoothstep(0.20f, 0.60f, fftFoamDilation) * 0.28f);
                float crestTopEdgePlate = crestSilhouette
                    * smoothstep(0.20f, 0.58f, ridgeShoulder + highCrestGate * 0.32f + fftFoamDilation * 0.22f)
                    * crestAreaGate
                    * foamSupport;
                float crestFoamMass = viewLipGate
                    * crestAreaGate
                    * highCrestGate
                    * smoothstep(0.24f, 0.60f, crestFace + slopeMagnitude * 0.18f + ridgeShoulder * 0.54f)
                    * smoothstep(0.16f, 0.50f, ridgeShoulder + crestSilhouette * 0.42f + ridgeScore * 0.36f + fftFoamDilation * 0.42f)
                    * foamSupport;
                float crestCoreFoamPlate = viewLipGate
                    * highCrestGate
                    * smoothstep(0.28f, 0.66f, ridgeShoulder * 0.28f + ridgeScore * 0.52f + fftFoamDilation * 0.62f)
                    * foamSupport;
                physicalCrestWhitePlate = saturate(max(physicalCrestWhitePlate, lipWhiteBridge * 0.82f));
                physicalCrestWhitePlate = saturate(max(physicalCrestWhitePlate, crestTopEdgePlate * 0.56f));
                physicalCrestWhitePlate = saturate(max(physicalCrestWhitePlate, crestFoamMass * 0.16f));
                physicalCrestWhitePlate = saturate(max(physicalCrestWhitePlate, crestCoreFoamPlate * 0.32f));
                physicalCrestWhitePlate *= foamSupport;
                float physicalCrestInkRim = smoothstep(0.10f, 0.28f, connectedFoamScore)
                    * (1.0f - smoothstep(0.42f, 0.64f, connectedFoamScore))
                    * crestSeedGate;
                physicalCrestInkRim = saturate(max(
                    physicalCrestInkRim,
                    lipWhiteBridge
                    * (1.0f - smoothstep(0.48f, 0.82f, fftFoamDilation + ridgeScore * 0.55f))
                    * 0.62f));
                float physicalCrestLowerShadow = smoothstep(0.20f, 0.52f, connectedFoamScore)
                    * (1.0f - physicalCrestWhitePlate * 0.62f)
                    * smoothstep(0.12f, 0.70f, crestSeedGate + fftFoamDilation * crestBand * 0.34f);
                physicalCrestLowerShadow = saturate(max(physicalCrestLowerShadow, crestTopEdgePlate * (1.0f - physicalCrestWhitePlate * 0.42f) * 0.46f));
                physicalCrestLowerShadow = saturate(max(physicalCrestLowerShadow, crestFoamMass * (1.0f - physicalCrestWhitePlate * 0.50f) * 0.22f));
                physicalCrestLowerShadow = saturate(max(physicalCrestLowerShadow, crestCoreFoamPlate * (1.0f - physicalCrestWhitePlate * 0.48f) * 0.42f));

                // Extra cream on high, steep lips: Hokusai's wave fingers read as flat
                // foam shapes with ink rims, not just physically simulated speckles.
                float crestLipFoam = smoothstep(
                    0.34f,
                    0.88f,
                    displacementFoam.y * _HeightShadeScale * 0.16f
                    + slopeMagnitude * 0.34f
                    + foam * 0.22f);
                crestLipFoam *= pow(saturate(clipDepth), 0.35f) * mainWavePrintGate * crestSeedGate;
                foam *= lerp(0.02f, 0.90f, mainWavePrintGate);
                foam = saturate(max(foam, crestLipFoam * 0.40f));

                float inverseUVDepth = saturate(pow(length(i.uv / 500 * _VarMaskRange), _VarMaskPower));
                float normalVarMask = UNITY_SAMPLE_TEX2D(_VariationMask, float2(i.uv / 1000 * _VarMaskTexScale)).r * inverseUVDepth;
                normalVarMask = saturate(normalVarMask * 4);

                float2 finalSlope = lerp(slopeMixA, slopeMixB, normalVarMask) * _NormalStrength;

                //宏观法线和中观法线，可以理解为整体法线和细节法线
                float3 macroNormal = float3(0.0, 1.0, 0.0);
                float3 mesoNormal = normalize(float3(-finalSlope.x, 1.0, -finalSlope.y));
                mesoNormal = lerp(macroNormal, mesoNormal, pow(saturate(clipDepth), _DisplaceDepthAttenuation));
                mesoNormal = normalize(UnityObjectToWorldNormal(mesoNormal));

                // ================= CLEAN UKIYO-E COMPOSITION (v2) =================
                // Rewritten from the validated detection signals. Targets: every crest +
                // foam reads white, every wave face carries vertical comb stripes, flat
                // posterized blue bands with dark ink outlines. The legacy block below is
                // unreachable (kept temporarily; will be deleted once the look is dialed in).
                // 用已验证的检测信号重写：波峰+白沫全白、浪面竖条、平涂蓝色带+深墨描线。
                {
                    float3 ukLight = normalize(_WorldSpaceLightPos0.xyz);
                    float ukNdotl = saturate(dot(mesoNormal, ukLight));
                    float ukLitShadow = saturate(shadow + _ShadowIntensity);

                    // 1) Band shade from SIGNED RELATIVE height (raw texture height, decoupled from
                    //    _VerticalDisplacementStrength): troughs -> deep ink, crests -> pale. This lets
                    //    geometry waves be scaled big without saturating the color bands.
                    //    (max(0,...) was the earlier bug: troughs never darkened, so deep blue vanished.)
                    // Strong contrast: FFT height is Gaussian (most of the surface sits near the
                    // mean), so a gentle coefficient leaves everything in the mid band = uniform blue.
                    // A high coefficient makes TYPICAL waves (std ~0.7) cross band boundaries so the
                    // flat woodblock color separation actually appears. _HeightShadeScale is the knob.
                    float ukHeight01 = saturate(0.5f + displacementFoam.y * max(_HeightShadeScale, 0.001f) * 1.0f);
                    float ukSteep = saturate(slopeMagnitude * max(_SteepShadeScale, 0.001f) * 1.2f);
                    float ukShade = saturate(ukHeight01 - ukSteep * 0.30f
                                    + (ukNdotl - 0.5f) * _LightInfluence * 0.5f - (1.0f - ukLitShadow) * 0.15f);

                    // 2) Vertical comb stripes: phase runs along the crest line (perpendicular to
                    //    the horizontal height gradient) so the stripes read as vertical combs down
                    //    the wave face. Carved as dark gaps into the band shade, gated to wave faces.
                    // Vertical comb striations: phase along the crest line (perpendicular to the
                    // horizontal height gradient) so teeth run DOWN the wave face. Each tooth has a
                    // pale streak at its center and a dark gap at its edge -> the blue/white combs of
                    // the reference. Gated to sloped wave faces, where Hokusai's combs actually live.
                    // Coherent FIXED stripe direction (world X). Deriving direction from the per-pixel
                    // slope made every pixel's stripe point differently -> speckle. A fixed axis warped
                    // by Z + height gives clean vertical combs that curve organically down the faces.
                    float ukGradLen = length(slopeMixA);
                    float ukStripeWarp = sin(worldPos.z * 0.028f + visHeight * 0.4f) * _PrintStripeWarp;
                    float ukStripeCoord = worldPos.x * max(_PrintStripeScale, 0.001f) * 6.0f + ukStripeWarp;
                    float ukStripeTri = abs(frac(ukStripeCoord) - 0.5f) * 2.0f;   // 0 center .. 1 edge
                    // _PrintStripeBokashi widens the pale<->dark transition (paper §2.2.3 bokashi) so the light/deep
                    // streaks gradate smoothly into each other instead of a hard pale|gap|dark edge. 0 = original hard
                    // combs, 1 = very soft gradation. User: 浅蓝/深蓝条纹过渡稍微加点 bokashi。
                    float ukSb = saturate(_PrintStripeBokashi);
                    float ukCombDark = smoothstep(0.46f - ukSb * 0.30f, 0.86f + ukSb * 0.10f, ukStripeTri);     // dark gap at tooth edge
                    float ukCombLight = 1.0f - smoothstep(0.0f, 0.34f + ukSb * 0.42f, ukStripeTri); // pale streak at tooth center
                    float ukComb = max(ukCombDark, ukCombLight);                  // (debug)
                    // Gate stripes to STEEP WAVE FACES only (issue #4): in the reference the light/deep
                    // blue striations live on the rising face of a wave, not on flat open water. A smooth
                    // slope gate keeps calm water clean and concentrates the combs on the wave faces.
                    // 条纹只在陡峭浪面出现(#4)：参考图里浅蓝/深蓝条纹在浪的上升面，不在平静开阔水面。
                    float ukFaceGate = smoothstep(0.10f, 0.42f, slopeMagnitude);
                    float ukStripeGate = ukFaceGate * mainWavePrintGate * _PrintStripeStrength;
                    // (stripes are applied as a COLOR overlay after posterization below, so the band
                    //  quantization doesn't absorb them)

                    // Posterize into flat ink plates.
                    float ukBands = max(_ToonBands, 2.0f);
                    float ukB = saturate(floor(ukShade * ukBands) / (ukBands - 1.0f));
                    // BOKASHI (paper §2.2.3): hard cel bands are "inappropriate" for ukiyo-e — the print's colour
                    // gradates smoothly to approximate lighting/depth, with the line work carrying the detail.
                    // Blend the posterized band value back toward the CONTINUOUS shade so the 2 bands soften into a
                    // gradation (restrained by strength: 0 = flat bands, 1 = fully smooth). Same palette, gradated.
                    float ukBokashi = saturate(lerp(ukB, ukShade, _NprBokashiStrength));
                    float3 ukWater = ukBokashi < 0.5f
                        ? lerp(_DeepInkColor, _MidWaterColor, ukBokashi * 2.0f)
                        : lerp(_MidWaterColor, _PaleWaterColor, ukBokashi * 2.0f - 1.0f);

                    // 3) JACOBIAN-BASED WHITE FOAM — Tessendorf (2001) breaking criterion.
                    //    Whitewater forms where the horizontal displacement folds the surface, i.e. the
                    //    Jacobian J of x -> x + lambda*D(x) drops <= 0. clawMask.b = 1 - saturate(rawJacobian)
                    //    is exactly that breaking term, computed instantaneously in the compute shader
                    //    (so it is time-STABLE — no foam accumulation drift). Gating it by HIGH crest
                    //    height confines the foam to the breaking LIPS at the tops of waves, as in the
                    //    print — not troughs, not the whole sea.
                    //    雅可比破碎判据(Tessendorf)：水平位移把表面折叠(J<=0)处生白沫。clawMask.b=1-saturate(jacobian)
                    //    即瞬时破碎项，再乘"高波峰"门控，白沫只落在波峰顶的破碎唇，符合原作；瞬时量=时间稳定。
                    // Sharpen the broad compression signal down to the STRONGEST folding (the actual
                    // breaking lip, where J is most negative) so the white is a thin curling edge, not a
                    // broad cap. Then require the upper part of the wave so it sits at the crest top.
                    // FILL THE HOLES AT THE SOURCE. The Jacobian breaking signal (clawMask.b) is per-texel and
                    // has scattered near-ZERO spots inside a breaking crest; those punch the light-blue/black
                    // holes in the white (no threshold or boost can fill a true zero). Dilate it: take the MAX
                    // over two small rings (tex2Dlod, explicit LOD 0) so a hole surrounded by foam fills solid.
                    // 在源头填洞：雅可比破碎信号(clawMask.b)逐纹素、破碎区内散布近零点，在白色里打出浅蓝/黑洞
                    // （任何阈值/增益都填不了真零）。用两圈小邻域取最大值(tex2Dlod LOD0)膨胀，被破碎包围的洞即填实。
                    float2 ukMUV = frac(worldPos.xz * _Tile0);
                    // BOX-BLUR the per-texel Jacobian breaking signal into a SMOOTH field, THEN threshold. The raw
                    // clawMask.b is texel-noisy, so a hard cut on it speckles both the interior (holes) AND the
                    // edges — up close those read as the SQUARE light-blue spots. MAX-dilation filled solid cores
                    // but left the noisy threshold-crossing edges speckled. A 13-tap average (~4/8/12 texels)
                    // consolidates the signal; the sharp ukWhite cut below then re-crisps the silhouette along the
                    // SMOOTH contour = solid white shapes with clean edges, no squares. (user: 方形浅蓝色亮斑)
                    float ukO1 = _Tile0 * 0.7f, ukO2 = _Tile0 * 1.4f, ukO3 = _Tile0 * 2.2f;
                    float ukMb = clawMask.b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2( ukO1, 0.0f)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2(-ukO1, 0.0f)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2(0.0f,  ukO1)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2(0.0f, -ukO1)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2( ukO2,  ukO2)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2(-ukO2, -ukO2)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2( ukO2, -ukO2)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2(-ukO2,  ukO2)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2( ukO3, 0.0f)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2(-ukO3, 0.0f)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2(0.0f,  ukO3)),0,0)).b;
                    ukMb += tex2Dlod(_ClawMaskTexture, float4(frac(ukMUV+float2(0.0f, -ukO3)),0,0)).b;
                    ukMb /= 13.0f;
                    // Restore strength lost to averaging (×_FoamSmoothScale), then cut on the SMOOTH field at
                    // _FoamCut -> solid white shapes with clean edges. Both live-tunable; sensible defaults if unset.
                    float fScale = _FoamSmoothScale > 0.001f ? _FoamSmoothScale : 1.8f;
                    float fCut   = _FoamCut > 0.001f ? _FoamCut : 0.26f;
                    float ukBreakJ   = smoothstep(fCut, fCut + 0.20f, saturate(ukMb * fScale)); // smooth field -> no speckle
                    float ukHiCrest  = smoothstep(0.58f, 0.95f, ukHeight01);           // crest top only
                    // FILL THE FLANKS, NOT JUST THE TIP. The lerp floor was 0.22, so only the very
                    // crest tip (ukHiCrest~1) reached the white threshold; the foam flanks (height dips
                    // within the SAME breaking clump) fell into the dark rim zone -> broad black streaks
                    // exposing the shaded water (debug view 2 = big dark blobs inside the green). A HIGH
                    // floor makes the whole clump interior solid; the boundary still goes dark because
                    // ukBreakJ*highCrestGate -> 0 at the clump edge regardless of the floor.
                    // 填满浪面而非仅波峰尖：floor 0.22 时只有波峰尖到白阈值，破碎团内部的高度低洼落入暗描边区
                    // -> 露出受光水面的黑色竖条。高 floor 让整团内部全白，团边缘仍因 ukBreakJ*highCrestGate->0 而变暗。
                    // LIP-FOAM (user: 继续削减白色的生成区域 + match the painting). Was a solid-fill floor
                    // lerp(0.96,1) that whitened the whole breaking clump; now gate by ukHiCrest so foam sits
                    // only on the upper crest / curling LIP and the wave FACE below stays blue — like the
                    // painting's white-crest/blue-face waves. The lip core is still solid (ukBreakJ*gate*highCrest
                    // =1 at the top), so no internal stripes; the face is the (now-darkened) posterized blue.
                    // FLOOR the per-texel Jacobian (lerp toward 1 by _FoamJFloor) so it NEVER multiplies the foam
                    // to zero — that multiply-to-zero is what punched the square light-blue holes. Foam now follows
                    // the SMOOTH crest gate (ukHiCrest × highCrestGate, both from the noise-free FFT height/slope),
                    // with breaking only softly modulating intensity = solid clean white shapes. (user: 方形浅蓝色亮斑)
                    float ukJFloor = _FoamJFloor > 0.001f ? _FoamJFloor : 1.0f;
                    float ukBreakSig = saturate(lerp(ukBreakJ, 1.0f, ukJFloor) * smoothstep(0.35f, 0.65f, ukHiCrest)) * highCrestGate;
                    // Scalloped edge so the foam silhouette reads as Hokusai's curled fingers, not a flat
                    // line. Kept SMALL (was 0.10/0.06) so it scallops the EDGE without punching light-blue
                    // holes in the white interior (user: 白色的部分要纯白，不要里面有浅蓝色的竖条).
                    // 鳞边幅度调小：只勾边缘曲线，不在白色内部打出浅蓝色的洞。
                    float ukScallop = sin(worldPos.x * 0.42f + worldPos.z * 0.10f + visHeight * 0.25f) * 0.045f
                                    + sin(worldPos.x * 1.15f - worldPos.z * 0.18f) * 0.025f;
                    float ukScallopThresh = _CrestWhiteThreshold - ukScallop;
                    // SOLID flat cream: a NARROW smoothstep makes the foam a solid woodblock shape so no
                    // pale-blue band facets bleed through inside the white (issue #3 — white must be flat).
                    // Sharper edge (0.05 -> 0.02): collapses the partial-white transition zone so the foam
                    // is binary on/off — no pale-blue band shows through a half-white rim (user: 浅蓝色亮面又出来了).
                    float ukWhite = saturate(smoothstep(ukScallopThresh, ukScallopThresh + 0.02f, ukBreakSig) * max(_CrestWhiteBoost, 0.5f));
                    float ukWhiteRim = smoothstep(ukScallopThresh - _OutlineWidth * 2.5f, ukScallopThresh, ukBreakSig) * (1.0f - ukWhite);

                    // Pure flat cream foam (no lighting/band gradient inside the white).
                    float3 ukCol = lerp(ukWater, _FoamCreamColor, ukWhite);

                    // Vertical comb striations as a COLOR overlay (after posterization): pale streaks
                    // at tooth centers, dark indigo ink in the gaps — only on the blue wave faces,
                    // never on the cream foam. This is the Great Wave's combed-foam striation.
                    // User: keep the combs on the DARKER water and fade them out on the BRIGHTER bands (亮处的等高线区)
                    // so those clean bands stay clean. Gate by the uk-block water brightness ukShade: full where dark,
                    // ->0 where bright. _PrintStripeGateBright = brightness midpoint where they fade; _PrintStripeFaceGate
                    // = how strongly (0 = off/baseline .. 1 = full fade on bright bands).
                    float ukCombBrightGate = lerp(1.0f, 1.0f - smoothstep(_PrintStripeGateBright - 0.18f, _PrintStripeGateBright + 0.18f, ukShade), saturate(_PrintStripeFaceGate));
                    float ukCombApply = ukStripeGate * (1.0f - ukWhite) * ukCombBrightGate;
                    ukCol = lerp(ukCol, _PaleWaterColor, ukCombLight * ukCombApply * 0.65f);
                    ukCol = lerp(ukCol, _OutlineInkColor, ukCombDark * ukCombApply * 0.45f);

                    // 4) Dark ink outlines: band registration lines + foam/crest rim.
                    float ukBandPos = frac(ukShade * ukBands);
                    float ukBandEdge = 1.0f - smoothstep(0.0f, max(_OutlineWidth * 2.0f, 0.01f), min(ukBandPos, 1.0f - ukBandPos));
                    ukCol = lerp(ukCol, _OutlineInkColor, ukBandEdge * _OutlineStrength * 0.35f * mainWavePrintGate * (1.0f - ukWhite));
                    ukCol = lerp(ukCol, _OutlineInkColor, saturate(ukWhiteRim) * _OutlineStrength);

                    // 4b) Spray dots REMOVED (issue #2 — user finds the small white circles distracting).

                    // 5) Hand-print mottle + flat paper-sky fog.
                    ukCol *= 1.0f - saturate(normalVarMask) * _PrintMottle * 0.15f;
                    // NaN guard: at grazing/steep angles viewDepth can drive (1-exp) negative, and
                    // pow(negative, fractional) = NaN which blackens the whole surface. Clamp the base.
                    float ukFogBase = max(0.0f, 1.0f - exp(-max(viewDepth, 0.0f) * _FogDensity));
                    float ukFog = saturate(pow(ukFogBase, max(_FogPower, 0.001f)));
                    ukCol = lerp(ukCol, _FogColor, ukFog * (1.0f - ukWhite * 0.8f));

                    // ===== UKIYO-E INK / PAPER GRAIN — Brown & Arandjelovic (Sci 2020) §2.2.1 =====
                    // A woodblock print's flat colour is NOT perfectly uniform — ink soak + paper tooth give it a
                    // granular imperfection. The paper applies this noise in SCREEN space (the 2D print look), not
                    // mapped onto the 3D mesh (eqs 4-5), and offsets the screen coords by the object's screen-space
                    // centre (eqs 6-7) for temporal coherence so the grain follows the scene instead of the camera
                    // "swimming" through it (shower-door). For the whole-sea mesh the offset is the camera world XZ.
                    {
                        // User: the grain should FOLLOW the FFT surface, not swim in screen space. World-anchored sampling
                        // (worldPos.xz = the DISPLACED surface position) makes the grain stick to the water and move with the
                        // waves — the water-appropriate version of the paper's object-anchor (§2.2.1 eqs 6-7). _NprPaperWorld
                        // blends screen(0, original print look) -> world(1, follows FFT); _NprPaperWorldFreq = world grain size.
                        float2 inkScreenUV = (screenUV * _ScreenParams.xy) / max(_NprPaperScale, 1.0f) + _WorldSpaceCameraPos.xz * _NprPaperFollow;
                        float2 inkWorldUV  = worldPos.xz * max(_NprPaperWorldFreq, 0.001f);
                        float ukPaper = lerp(PaperNoise(inkScreenUV), PaperNoise(inkWorldUV), saturate(_NprPaperWorld)); // 0..1 grain
                        // Subtractive ink imperfection (darken toward ink where grain is low). Foam stays mostly
                        // pure white (user's hard-won requirement); the water bands carry the full grain.
                        float ukPaperAmt = _NprPaperStrength * (1.0f - ukWhite * 0.75f);
                        ukCol *= 1.0f - (1.0f - ukPaper) * ukPaperAmt;
                    }

                    // ===== UKIYO-E LINE WORK (描边) — Brown & Arandjelovic (Sci 2020) §2.1 important edges =====
                    // Detected screen-space from _CameraDepthNormalsTexture (zw = 01 depth, xy = view normal):
                    //   silhouette = a near wave occluding farther water (depth jump)  -> outer ink contour;
                    //   crease     = sharp surface fold / breaking lip (normal jump)    -> inner ink line.
                    // This is the woodblock keyblock line that gives the waves their bold ukiyo-e contour.
                    {
                        float2 nprUVStep = (_ScreenParams.zw - 1.0f) * max(_NprOutlineWidth, 0.5f);
                        float dC; float3 nC;
                        DecodeDepthNormal(tex2D(_CameraDepthNormalsTexture, screenUV), dC, nC);
                        float depthEdge = 0.0f, normalEdge = 0.0f;
                        float2 nprOff[4] = {
                            float2( nprUVStep.x, 0.0f), float2(-nprUVStep.x, 0.0f),
                            float2(0.0f,  nprUVStep.y), float2(0.0f, -nprUVStep.y) };
                        [unroll] for (int kNpr = 0; kNpr < 4; kNpr++)
                        {
                            float dN; float3 nN;
                            DecodeDepthNormal(tex2D(_CameraDepthNormalsTexture, screenUV + nprOff[kNpr]), dN, nN);
                            depthEdge  = max(depthEdge,  dN - dC);                       // neighbour farther => near silhouette
                            normalEdge = max(normalEdge, 1.0f - saturate(dot(nN, nC))); // dihedral fold (crease)
                        }
                        float silhouette = smoothstep(_NprSilhouetteThreshold, _NprSilhouetteThreshold * 2.2f, depthEdge);
                        float crease     = smoothstep(_NprCreaseThreshold, _NprCreaseThreshold + 0.22f, normalEdge);
                        // In-shader wave edges: a smooth FFT heightfield rarely produces hard screen-space depth
                        // jumps, so the paper's silhouette/crease are sparse here. Equivalent criteria on a
                        // heightfield, using the reliable wave data:
                        //   grazing = surface seen edge-on (the paper's front-/back-face transition, via the normal)
                        //             -> the crest contour line;
                        //   ridge   = a local height ridge (a crease/fold on a heightfield) -> the wave's crest line.
                        float3 vDirW   = normalize(_WorldSpaceCameraPos.xyz - worldPos);
                        // Paper's silhouette = the front-/back-face transition = the ZERO-CROSSING of n·v.
                        // Anchored with fwidth so it stays a thin ink line right on the wave-crest silhouette at
                        // ANY camera angle. Uses no _CameraDepthNormalsTexture, so unlike the depth silhouette it
                        // ALSO renders off the Scene-view camera — and it never floods the flat sea the way a fixed
                        // grazing threshold does (the line is pinned to |n·v|≈0, not to a magnitude band).
                        float nDotV    = dot(normalize(mesoNormal), vDirW);
                        // CLAMP the line width: a noisy meso-normal makes fwidth spike, which would widen the
                        // "thin" silhouette into a broad gray flood on near-grazing slopes. Cap keeps it a line.
                        float silW     = min(max(fwidth(nDotV), 1e-4f) * (_NprGrazeThreshold * 5.0f + 1.0f), 0.05f);
                        float grazeLine = 1.0f - smoothstep(0.0f, silW, abs(nDotV));
                        float ridgeLine = smoothstep(0.018f, 0.055f, ridgeLift) * smoothstep(0.14f, 0.44f, slopeMagnitude);
                        float waveEdge  = max(grazeLine, ridgeLine);
                        // ALL the screen-space (silhouette/crease) + n·v crest ink goes on the WATER only (×1-ukWhite).
                        // The foam caps must stay PURE WHITE inside — they are outlined ONLY by their crisp ddx/ddy
                        // boundary line (below), never flooded gray by a broad near-grazing slope. Blue (non-foam)
                        // wave crests still receive the n·v silhouette, so "every wave crest has a contour" holds.
                        float inkLine = saturate(max(max(silhouette, crease * _NprCreaseStrength),
                                                     waveEdge * _NprWaveEdgeStrength)) * _NprOutlineStrength * (1.0f - ukWhite);
                        // Band-contour line (色带等高线): the posterization band boundaries ARE woodblock keyblock
                        // contour lines that follow the wave height — the boldest, most ukiyo-e-authentic wave 描边
                        // (user's choice). Drawn on the water bands, suppressed on the foam (which has its own rim).
                        // Contour density DECOUPLED from the colour bands (_ToonBands=2) — the wave shapes need MANY
                        // keyblock height-contour lines (the Great Wave traces every swell), not just 1 band edge.
                        float ukBandF2 = ukShade * max(_NprContourCount, 2.0f);
                        float bandFrac = abs(frac(ukBandF2) - 0.5f) * 2.0f;            // 0 band-centre .. 1 band-edge
                        float bandContour = smoothstep(1.0f - max(_NprBandContourWidth, 0.02f), 1.0f, bandFrac)
                                          * (1.0f - ukWhite) * lerp(0.5f, 1.0f, mainWavePrintGate); // across the whole sea, not foam
                        inkLine = saturate(max(inkLine, bandContour * _NprBandContourStrength));
                        // CREST OUTER OUTLINE (波峰外轮廓线) — the actual goal. A bold ink keyline along each wave's
                        // crest ridge: ridgeLift>0 means this pixel is a LOCAL HEIGHT MAXIMUM (the crest top), so the
                        // line traces the silhouette/edge of every swell. VIEW-INDEPENDENT (renders from the top-down
                        // game camera) and catches gentle crests too — unlike the n·v silhouette (needs a grazing
                        // angle) and the depth silhouette (needs a sharp occlusion), which is why those were invisible.
                        float crestOutline = smoothstep(_NprCrestOutlineThresh, _NprCrestOutlineThresh + 0.014f, ridgeLift) * (1.0f - ukWhite);
                        inkLine = saturate(max(inkLine, crestOutline * _NprCrestOutlineStrength));
                        // CREASE (paper §2.1.1 Algorithm 1: an edge is important if n0·n1 < threshold = a sharp dihedral
                        // fold between adjacent faces). On the SMOOTH MACRO normal (±6 height gradient), NOT the per-pixel
                        // FFT normal — the per-pixel normal has fine ripples that flood to speckle (the earlier lesson).
                        // fwidth(macroN) = the screen-space rate of macro-normal change; it spikes where the macro surface
                        // FOLDS sharply (steep crest shoulders / breaking lips) and is ~0 on smooth swells. The paper's
                        // crease is on the whole object, so this is NOT gated to foam. _NprCreaseNStrength/Thresh tune it.
                        // _NprCreaseNFine dials the crease NORMAL between the SMOOTH macro normal (=0, clean/subtle:
                        // gentle swells give a faint crease) and the per-pixel FFT meso normal (=1, detailed: catches the
                        // sharp breaking-lip folds, but the fine FFT ripples reintroduce some speckle). Option B = push
                        // this up so the user can SEE the stronger crease and decide how much speckle is acceptable.
                        // DISTANCE LOD: near the camera the white foam is large and the crease reads as clean bold strokes;
                        // far away one pixel spans many FFT wavelengths, so the fine normal aliases into speckle (麻点). The
                        // LOD ramps the effect CONTINUOUSLY by distance — closer = stronger — and a gamma>1 bows the curve
                        // concave so it stays strong up close but drops off fast, keeping the mid/far sea weak and clean.
                        // _NprLodNear = distance where LOD reaches full 1; _NprLodFar = distance where it hits 0; _NprLodGamma
                        // = curve shape (1 = linear, >1 = strong-near / weak-mid-far).
                        float ukNprDist = length(_WorldSpaceCameraPos.xyz - worldPos);
                        float ukNprT    = saturate((_NprLodFar - ukNprDist) / max(_NprLodFar - _NprLodNear, 1.0f));
                        float ukNprLod  = pow(ukNprT, max(_NprLodGamma, 0.01f));
                        float3 ukMacroNcr = normalize(float3(-(hX0 - hX1), 12.0f, -(hZ0 - hZ1)));
                        float3 ukNcr = normalize(lerp(ukMacroNcr, mesoNormal, saturate(_NprCreaseNFine) * ukNprLod));
                        float ukCreaseN = length(fwidth(ukNcr));
                        float ukCrestCrease = smoothstep(_NprCreaseNThresh, _NprCreaseNThresh + max(_NprCreaseNThresh * 0.5f, 0.01f), ukCreaseN);
                        // UNGATED from white (user: 不要限制只在白色) but still distance-LOD'd, because the fine normal is the
                        // SPECKLE source: near it draws fold detail on all wave forms; far it fades to clean (no 麻点). The
                        // clean black OUTLINE at far/mid comes from the silhouette below, which is NOT LOD'd.
                        inkLine = saturate(max(inkLine, ukCrestCrease * _NprCreaseNStrength * ukNprLod));
                        // CREST SILHOUETTE of the white foam = the user's top-edge line: where the foam surface turns from
                        // near-facing to far-facing (n·v -> _NprFoamProxyLo), which IS the visible top edge. Line = a
                        // constant-px keyline along that n·v contour. FLATTER macro normal (up=20) so n·v only dips to the
                        // contour at a REAL crest tilt, not at tiny interior ripples = far fewer interior false lines.
                        float3 ukMacroN = normalize(float3(-(hX0 - hX1), max(_NprFoamNormalUp, 1.0f), -(hZ0 - hZ1)));
                        float3 ukViewD  = normalize(_WorldSpaceCameraPos.xyz - worldPos);
                        float ukNdV = dot(ukMacroN, ukViewD);
                        float ukNdVDistPx = (ukNdV - _NprFoamProxyLo) / max(fwidth(ukNdV), 1e-5f);   // signed px to the n·v=Lo contour
                        float ukHalf = max(_NprFoamOutlineWidth, 1.0f) * 0.5f;
                        float ukLineRaw = 1.0f - smoothstep(ukHalf - 0.75f, ukHalf + 0.75f, abs(ukNdVDistPx));
                        // Gate by the SMOOTH foam region (already-computed ridge height samples; no new taps) so breakup
                        // holes don't cut the line. _NprFoamProxyWidth = region height threshold (~0.68).
                        float ukHAvg = (hCenter + hX0 + hX1 + hZ0 + hZ1 + hN0 + hN1 + hT0 + hT1 + hT2 + hT3) * 0.0909f;
                        float ukH01avg = saturate(0.5f + (ukHAvg / max(_VerticalDisplacementStrength, 1.0f)) * max(_HeightShadeScale, 0.001f));
                        float ukFoamRegion = smoothstep(_NprFoamProxyWidth, _NprFoamProxyWidth + 0.08f, ukH01avg);
                        float foamInk = ukLineRaw * ukFoamRegion;
                        // DISTANCE-INDEPENDENT (no LOD): the silhouette is the clean macro-normal contour — it does NOT alias
                        // like the fine crease, so it stays a crisp BLACK line at ALL distances (near + mid + far). This is the
                        // main outline the user wants kept everywhere; only the fine crease above carries the distance LOD.
                        inkLine = saturate(max(inkLine, foamInk * _NprFoamOutlineStrength));
                        // §2.1.6 STROKE rendering: the paper draws outlines as discrete brush strokes with VARIABLE WIDTH
                        // (粗细, tapered ends) and SEGMENT breaks — not a uniform line. It does that with stroke geometry
                        // (link edges into chains, render textured ribbons with arc-length width profiles). Our outline is an
                        // image-space mask, so we approximate the same look by ERODING the line mask with a screen-stable,
                        // camera-followed noise: where the noise dips, the line THINS (taper / variable width); a second,
                        // coarser noise punches discrete BREAKS so it reads as separate brush marks. Camera-followed for
                        // temporal coherence like the paper grain. _NprStrokeVary = width-variation depth; _NprStrokeGap =
                        // how aggressively it segments; _NprStrokeScale = stroke noise size (px). +41/+91 decorrelate the noises.
                        float2 ukStrokeUV = (screenUV * _ScreenParams.xy) / max(_NprStrokeScale, 1.0f) + _WorldSpaceCameraPos.xz * _NprPaperFollow + 41.0f;
                        float ukStrokeErode = _NprStrokeVary * (1.0f - PaperNoise(ukStrokeUV));      // taper / variable width
                        inkLine = saturate((inkLine - ukStrokeErode) / max(1.0f - ukStrokeErode, 0.05f));
                        float ukStrokeSeg = PaperNoise(ukStrokeUV * 0.4f + 91.0f);                    // coarser -> discrete breaks
                        inkLine *= smoothstep(_NprStrokeGap, _NprStrokeGap + 0.12f, ukStrokeSeg);
                        // ① HEIGHT-DRIVEN TAPER (Dadfar & Welling §5.1): the painting's lines are bold on crests and thin to
                        // nothing toward the troughs. Drive the line by the smooth average height (ukH01avg, already computed
                        // above) so it fades in the deep troughs and stays full on crests. _NprStrokeTaper = strength (0 = off,
                        // identical to baseline); _NprStrokeTaperHeight = the height midpoint where the taper kicks in.
                        float ukHeightTaper = smoothstep(_NprStrokeTaperHeight - 0.12f, _NprStrokeTaperHeight + 0.12f, ukH01avg);
                        inkLine *= lerp(1.0f, ukHeightTaper, _NprStrokeTaper);
                        ukCol = lerp(ukCol, _OutlineInkColor, inkLine);
                    }

                    if (_HokusaiDebugView > 0.5f)
                    {
                        float3 d = ukCol;
                        if (_HokusaiDebugView < 1.5f) d = lerp(float3(0.02f,0.03f,0.05f), float3(1,0.9f,0.2f), mainWavePrintGate);
                        else if (_HokusaiDebugView < 2.5f) d = lerp(float3(0.02f,0.03f,0.05f), float3(0.2f,1,0.35f), ukWhite);
                        else if (_HokusaiDebugView < 3.5f) d = float3(ukBreakJ, ukBreakSig, ukWhite);
                        else if (_HokusaiDebugView < 4.5f) d = lerp(float3(0.02f,0.03f,0.05f), float3(1,0.5f,0.1f), crestFace);
                        else if (_HokusaiDebugView < 5.5f) d = lerp(float3(0.02f,0.03f,0.05f), float3(0.45f,0.78f,1), ukComb * ukStripeGate);
                        else d = float3(ukB, ukB, ukB);
                        return float4(d, 1.0f);
                    }
                    return float4(ukCol, 1.0f);
                }

            }

            ENDCG
        }

    }
    FallBack "Specular"
}
