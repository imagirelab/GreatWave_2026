Shader "MasterProject/FFTOcean_Shader"
{
    // テッセレーションに関する計算
    CGINCLUDE
    int _TessEdgeLength;

    struct TessellationFactors{
        float edge[3] : SV_TESSFACTOR;
        float inside : SV_INSIDETESSFACTOR;
    };

    // テッセレーション係数の算出式
    float TessellationHeuristic(float3 cp1, float3 cp2){
        float edgeLength = distance(cp1, cp2);
        float3 edgeCenter = (cp1 + cp2) * 0.5;
        float viewDistance = distance(edgeCenter, _WorldSpaceCameraPos);

        // カメラが水面へ近づくと無制限ではハードウェア上限の 64 倍に達し、
        // 最も負荷が高い場面で三角形数が急増するため、32 倍を上限とする。
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
        // 基本描画パス
        pass{
            Tags { "LightMode" = "ForwardBase" }
            Tags { "RenderType"="Opaque" }
            LOD 200

            CGPROGRAM
            #pragma target 5.0
            #pragma multi_compile_fwdbase

            #include "UnityPBSLighting.cginc"
            #include "AutoLight.cginc"

            // 旧ジオメトリ段階は使わない重心座標を渡すだけなのに、1.2 km の海面上の
            // 全細分三角形に処理段階を増やしていた。GPU の幾何負荷を下げるため削除した。
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

            // 浮世絵の木版画表現に使う値。FFTOcean_Script.SetMaterialParam から渡される。
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
            // 浮世絵の描線。Brown と Arandjelovic（Sci 2020）第2.1節の重要な辺を、
            // _CameraDepthNormalsTexture を使うリアルタイムの画面空間検出へ応用する。
            // 輪郭は深度の不連続、折れ線は視線空間法線の不連続で表す。
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
            // 実行中に調整できる泡マスク。平均化で弱くなる破砕信号を _FoamSmoothScale で補い、
            // 平滑化後の白形状を _FoamCut で切り分ける。_FoamJFloor は画素ごとのヤコビアンに
            // 下限を設け、泡を滑らかな波頂条件へ寄せる（1 は波頂のみ、0 は破砕信号で穴が出る）。
            // 四角い穴への対策として導入した。
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
                // 変位後の形状に稜線検出を合わせるため、見かけの高さを返す。
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

            // 北斎風の散った飛沫点に使う、軽量な 2D ハッシュ。出力は [0,1]。
            float Hash2(float2 p)
            {
                p = frac(p * float2(123.34f, 456.21f));
                p += dot(p, p + 45.32f);
                return frac(p.x * p.y);
            }

            // ハッシュ格子を smoothstep で補間した 2D 値雑音。[0,1] を返す。
            // Brown と Arandjelovic（Sci 2020）第2.2.1節の木版のインク・紙目を二オクターブで表す。
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
                // 頂点シェーダーは displacement.y に _VerticalDisplacementStrength を掛けて形状を上げる。
                // 見かけ上高い波頂でも元データは小さいので、条件判定には見かけの高さを使う。
                float visHeight = displacementFoam.y * max(_VerticalDisplacementStrength, 1.0f);
                float crestFace = saturate(slopeMagnitude * 0.42f + max(0.0f, visHeight) * 0.055f);
                // 泡の条件判定だけに平滑な傾斜を使う。水面法線には鋭い slopeMagnitude を残す。
                // slopeMixB は細かな二層の成分。泡の縁を斑点化するため大部分を引き、粗い傾斜を見る。
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

                // 白い泡は実際の FFT 泡、急な局所極大、爪マスクの波頂候補に限る。
                // 頂点を動かす変位テクスチャと同じ値から、ワールド空間でマスクを作る。
                float hCenter = visHeight; // SampleWaveHeightAt と同じ見かけの高さ
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
                // 白域が広すぎるという指摘に対し、強い波頂だけを泡にする。弱い波頂は濃紺に保つ。
                // 個々の泡を縮めず、白域の総面積を減らして淡青の縁の露出を避ける。
                // しきい値は 0.28／0.62。平滑化した傾斜を使って縁の斑点を抑える。
                // jFloor=1.0 は泡の塊をきれいに保つ。
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

                // 高く急な波頭の縁に白を足す。北斎の爪状の波は、物理的な細斑だけでなく
                // 墨の縁を持つ平坦な泡形状として見せる。
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

                // マクロ法線とメソ法線。全体形状と細部の法線に相当する。
                float3 macroNormal = float3(0.0, 1.0, 0.0);
                float3 mesoNormal = normalize(float3(-finalSlope.x, 1.0, -finalSlope.y));
                mesoNormal = lerp(macroNormal, mesoNormal, pow(saturate(clipDepth), _DisplaceDepthAttenuation));
                mesoNormal = normalize(UnityObjectToWorldNormal(mesoNormal));

                // ================= 浮世絵の色面構成（第2版） =================
                // 確認済みの検出信号から構成し直した。波頂と泡は白、波面には縦の櫛状線、
                // 水面は平坦な青の段階色と濃い墨の輪郭で表す。
                // 以下の旧ブロックには到達しないが、見た目の調整が済むまで一時的に残す。
                {
                    float3 ukLight = normalize(_WorldSpaceLightPos0.xyz);
                    float ukNdotl = saturate(dot(mesoNormal, ukLight));
                    float ukLitShadow = saturate(shadow + _ShadowIntensity);

                    // 1) 符号付き相対高さを青い色面へ写す。谷は濃い墨、波頂は淡色。
                    // 生テクスチャの高さを使い、形状の拡大率から切り離して色の飽和を防ぐ。
                    // 以前の max(0,...) では谷が暗くならず、深い青が消えていた。
                    // FFT の高さは平均付近に集中するため、_HeightShadeScale を強めて通常の波も色境界を越えさせる。
                    float ukHeight01 = saturate(0.5f + displacementFoam.y * max(_HeightShadeScale, 0.001f) * 1.0f);
                    float ukSteep = saturate(slopeMagnitude * max(_SteepShadeScale, 0.001f) * 1.2f);
                    float ukShade = saturate(ukHeight01 - ukSteep * 0.30f
                                    + (ukNdotl - 0.5f) * _LightInfluence * 0.5f - (1.0f - ukLitShadow) * 0.15f);

                    // 2) 波面の縦向きの櫛状線。淡い線の中心と暗い隙間を交互に作る。
                    // 画素ごとの傾斜から方向を決めると斑点化するため、ワールド X を基準方向に固定し、
                    // Z と高さでゆがませて波面を下る曲線にする。傾斜した波面にだけ適用する。
                    float ukGradLen = length(slopeMixA);
                    float ukStripeWarp = sin(worldPos.z * 0.028f + visHeight * 0.4f) * _PrintStripeWarp;
                    float ukStripeCoord = worldPos.x * max(_PrintStripeScale, 0.001f) * 6.0f + ukStripeWarp;
                    float ukStripeTri = abs(frac(ukStripeCoord) - 0.5f) * 2.0f;   // 0 は中心、1 は縁
                    // _PrintStripeBokashi は淡色と濃色の境界を広げ、ぼかしを与える（文献第2.2.3節）。
                    // 0 は硬い櫛状線、1 は非常に柔らかい階調。淡青と濃青の移行を少し滑らかにする。
                    float ukSb = saturate(_PrintStripeBokashi);
                    float ukCombDark = smoothstep(0.46f - ukSb * 0.30f, 0.86f + ukSb * 0.10f, ukStripeTri);     // 櫛の縁の暗い隙間
                    float ukCombLight = 1.0f - smoothstep(0.0f, 0.34f + ukSb * 0.42f, ukStripeTri); // 櫛の中心の淡い線
                    float ukComb = max(ukCombDark, ukCombLight);                  // 調査用
                    // 櫛状線は急な波面に限る。原画でも淡青と濃青の縞は立ち上がる波面にあり、
                    // 平らな海面にはない。滑らかな傾斜条件で静かな水面を保つ。
                    float ukFaceGate = smoothstep(0.10f, 0.42f, slopeMagnitude);
                    float ukStripeGate = ukFaceGate * mainWavePrintGate * _PrintStripeStrength;
                    // 縞は下の階調化後に色として重ね、色面の量子化で消えないようにする。

                    // 平坦なインク色面へ階調化する。
                    float ukBands = max(_ToonBands, 2.0f);
                    float ukB = saturate(floor(ukShade * ukBands) / (ukBands - 1.0f));
                    // ぼかし（文献第2.2.3節）。硬い色面だけでは浮世絵らしい光と奥行きの階調が出ない。
                    // 階調化した値を連続値へ戻し、同じ配色のまま境界を柔らかくする。
                    // 強度 0 は平坦な色面、1 は全面的に滑らかな階調。
                    float ukBokashi = saturate(lerp(ukB, ukShade, _NprBokashiStrength));
                    float3 ukWater = ukBokashi < 0.5f
                        ? lerp(_DeepInkColor, _MidWaterColor, ukBokashi * 2.0f)
                        : lerp(_MidWaterColor, _PaleWaterColor, ukBokashi * 2.0f - 1.0f);

                    // 3) Tessendorf（2001）のヤコビアン破砕条件による白泡。
                    // 水平変位 x→x+λD(x) で面が折れ、J<=0 となる位置を使う。
                    // clawMask.b=1-saturate(rawJacobian) は計算シェーダーで瞬時に求めるため、
                    // 泡の蓄積による時間的なずれがない。高い波頂で絞り、原画のように波頭の破砕縁に置く。
                    // 圧縮信号を J が最も負となる強い折れに絞り、白を広い帽子状ではなく細い巻き縁にする。
                    // さらに波の上部だけを選び、波頂に配置する。
                    // 穴を信号源で埋める。clawMask.b には画素ごとのゼロ付近の点が散在し、白域に穴を開ける。
                    // 真のゼロはしきい値や増幅では埋まらないため、小さな二重近傍の最大値で膨張させる。
                    float2 ukMUV = frac(worldPos.xz * _Tile0);
                    // 画素ごとの破砕信号を 13 点平均で平滑化してから切り分ける。
                    // 生の clawMask.b を硬く切ると内部と縁に四角い淡青斑が出る。
                    // 最大値膨張は内部を埋めるが、縁の雑音は残る。平均化した輪郭で ukWhite を鋭く切り、
                    // 内部が白く、縁のきれいな形状にする。
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
                    // 平均化で弱くなった信号を _FoamSmoothScale で戻し、_FoamCut で切り分ける。
                    // 両方とも実行中に調整でき、未設定時は既定値を使う。
                    float fScale = _FoamSmoothScale > 0.001f ? _FoamSmoothScale : 1.8f;
                    float fCut   = _FoamCut > 0.001f ? _FoamCut : 0.26f;
                    float ukBreakJ   = smoothstep(fCut, fCut + 0.20f, saturate(ukMb * fScale)); // 平滑化した場は斑点が少ない
                    float ukHiCrest  = smoothstep(0.58f, 0.95f, ukHeight01);           // 波頂上部のみ
                    // 旧下限 0.22 では尖端だけが白くなり、同じ破砕塊の側面は暗い縁に落ちた。
                    // 下限を上げると塊の内部は白く保てる。境界では ukBreakJ*highCrestGate がゼロへ向かう。
                    // 原画の白い波頂と青い波面へ寄せるため、ukHiCrest で白泡を巻く上縁に絞る。
                    // _FoamJFloor で画素ごとのヤコビアンが泡をゼロにしないようにし、四角い淡青穴を防ぐ。
                    // 泡は雑音の少ない FFT の高さ・傾斜による滑らかな波頂条件に従う。
                    float ukJFloor = _FoamJFloor > 0.001f ? _FoamJFloor : 1.0f;
                    float ukBreakSig = saturate(lerp(ukBreakJ, 1.0f, ukJFloor) * smoothstep(0.35f, 0.65f, ukHiCrest)) * highCrestGate;
                    // 泡の縁を小さく波打たせ、北斎の曲がる指の形にする。
                    // 振幅は旧値 0.10／0.06 より小さくし、白い内部に淡青の穴を開けない。
                    float ukScallop = sin(worldPos.x * 0.42f + worldPos.z * 0.10f + visHeight * 0.25f) * 0.045f
                                    + sin(worldPos.x * 1.15f - worldPos.z * 0.18f) * 0.025f;
                    float ukScallopThresh = _CrestWhiteThreshold - ukScallop;
                    // 狭い smoothstep で白泡を平坦な木版の形へする。
                    // 縁の幅を 0.05 から 0.02 へ狭め、半透明な白縁に淡青の色面が透けるのを防ぐ。
                    float ukWhite = saturate(smoothstep(ukScallopThresh, ukScallopThresh + 0.02f, ukBreakSig) * max(_CrestWhiteBoost, 0.5f));
                    float ukWhiteRim = smoothstep(ukScallopThresh - _OutlineWidth * 2.5f, ukScallopThresh, ukBreakSig) * (1.0f - ukWhite);

                    // 白泡の内部は照明や色面の階調を持たない平坦な乳白色。
                    float3 ukCol = lerp(ukWater, _FoamCreamColor, ukWhite);

                    // 階調化後、青い波面に淡色の中心線と濃紺の隙間を重ねる。白泡には描かない。
                    // 暗い色面では櫛状線を保ち、明るい色面では消して清潔な領域を残す。
                    // _PrintStripeGateBright は消え始める明度、_PrintStripeFaceGate はその強さ。
                    float ukCombBrightGate = lerp(1.0f, 1.0f - smoothstep(_PrintStripeGateBright - 0.18f, _PrintStripeGateBright + 0.18f, ukShade), saturate(_PrintStripeFaceGate));
                    float ukCombApply = ukStripeGate * (1.0f - ukWhite) * ukCombBrightGate;
                    ukCol = lerp(ukCol, _PaleWaterColor, ukCombLight * ukCombApply * 0.65f);
                    ukCol = lerp(ukCol, _OutlineInkColor, ukCombDark * ukCombApply * 0.45f);

                    // 4) 色面の境界線と泡・波頂の縁に濃い墨線を置く。
                    float ukBandPos = frac(ukShade * ukBands);
                    float ukBandEdge = 1.0f - smoothstep(0.0f, max(_OutlineWidth * 2.0f, 0.01f), min(ukBandPos, 1.0f - ukBandPos));
                    ukCol = lerp(ukCol, _OutlineInkColor, ukBandEdge * _OutlineStrength * 0.35f * mainWavePrintGate * (1.0f - ukWhite));
                    ukCol = lerp(ukCol, _OutlineInkColor, saturate(ukWhiteRim) * _OutlineStrength);

                    // 4b) 小さな白丸が目障りとの指摘を受け、飛沫点は削除済み。

                    // 5) 手刷りのむらと平坦な紙色の霧。
                    ukCol *= 1.0f - saturate(normalVarMask) * _PrintMottle * 0.15f;
                    // 斜め視点では viewDepth により 1-exp が負になり、分数乗で NaN が出て全体が黒くなる。
                    // 底値をゼロ以上に制限する。
                    float ukFogBase = max(0.0f, 1.0f - exp(-max(viewDepth, 0.0f) * _FogDensity));
                    float ukFog = saturate(pow(ukFogBase, max(_FogPower, 0.001f)));
                    ukCol = lerp(ukCol, _FogColor, ukFog * (1.0f - ukWhite * 0.8f));

                    // ===== 木版の墨と紙目：Brown と Arandjelovic（Sci 2020）第2.2.1節 =====
                    // 木版の平坦な色にも、墨の染みと紙の繊維による粒状のむらがある。
                    // 文献は 3D 網目上でなく画面空間に雑音を置き、物体の画面上の中心で座標をずらして
                    // カメラ移動時の滑りを抑える。海面全体ではカメラのワールド XZ をずれに用いる。
                    {
                        // 紙目を FFT 水面に追従させるには、変位後の worldPos.xz で標本化する。
                        // _NprPaperWorld は画面固定（0）と水面追従（1）を混合し、_NprPaperWorldFreq は粒径。
                        float2 inkScreenUV = (screenUV * _ScreenParams.xy) / max(_NprPaperScale, 1.0f) + _WorldSpaceCameraPos.xz * _NprPaperFollow;
                        float2 inkWorldUV  = worldPos.xz * max(_NprPaperWorldFreq, 0.001f);
                        float ukPaper = lerp(PaperNoise(inkScreenUV), PaperNoise(inkWorldUV), saturate(_NprPaperWorld)); // 0～1 の紙目
                        // 紙目の低い部分を墨色に暗くする。泡はほぼ純白に保ち、水面の色面に強く効かせる。
                        float ukPaperAmt = _NprPaperStrength * (1.0f - ukWhite * 0.75f);
                        ukCol *= 1.0f - (1.0f - ukPaper) * ukPaperAmt;
                    }

                    // ===== 浮世絵の描線：Brown と Arandjelovic（Sci 2020）第2.1節 =====
                    // _CameraDepthNormalsTexture から画面空間で検出する。
                    // 深度の跳びは手前の波が奥を隠す外輪郭、法線の跳びは折れや破砕縁の内側の墨線。
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
                            depthEdge  = max(depthEdge,  dN - dC);                       // 隣が遠ければ手前の輪郭
                            normalEdge = max(normalEdge, 1.0f - saturate(dot(nN, nC))); // 二面角による折れ
                        }
                        float silhouette = smoothstep(_NprSilhouetteThreshold, _NprSilhouetteThreshold * 2.2f, depthEdge);
                        float crease     = smoothstep(_NprCreaseThreshold, _NprCreaseThreshold + 0.22f, normalEdge);
                        // 滑らかな FFT 高さ場には急な深度跳びが少ないため、深度だけでは描線が不足する。
                        // 代わりに、接線方向に見る面を波頂の外輪郭、局所的な高さの稜線を波頂線として扱う。
                        float3 vDirW   = normalize(_WorldSpaceCameraPos.xyz - worldPos);
                        // 表裏の境目 n·v≈0 を輪郭とし、fwidth でどの視角でも細線に保つ。
                        // 深度テクスチャを使わないので Scene 視点でも描かれ、平坦な海面を塗り潰さない。
                        float nDotV    = dot(normalize(mesoNormal), vDirW);
                        // メソ法線の雑音で fwidth が増えると細線が広い灰色域になるため、線幅を制限する。
                        float silW     = min(max(fwidth(nDotV), 1e-4f) * (_NprGrazeThreshold * 5.0f + 1.0f), 0.05f);
                        float grazeLine = 1.0f - smoothstep(0.0f, silW, abs(nDotV));
                        float ridgeLine = smoothstep(0.018f, 0.055f, ridgeLift) * smoothstep(0.14f, 0.44f, slopeMagnitude);
                        float waveEdge  = max(grazeLine, ridgeLine);
                        // 画面空間の輪郭・折れと n·v の波頂墨線は、水面だけに描き、泡の内部は純白に保つ。
                        // 白泡は下の鋭い境界線だけで囲む。青い波頂には n·v の輪郭が残る。
                        float inkLine = saturate(max(max(silhouette, crease * _NprCreaseStrength),
                                                     waveEdge * _NprWaveEdgeStrength)) * _NprOutlineStrength * (1.0f - ukWhite);
                        // 色面の境界を波の高さに沿う木版の墨線として描く。泡には固有の縁があるため描かない。
                        // 線の密度は色面の段数 _ToonBands と切り離し、複数のうねりを追えるようにする。
                        float ukBandF2 = ukShade * max(_NprContourCount, 2.0f);
                        float bandFrac = abs(frac(ukBandF2) - 0.5f) * 2.0f;            // 0 は色面の中心、1 は境界
                        float bandContour = smoothstep(1.0f - max(_NprBandContourWidth, 0.02f), 1.0f, bandFrac)
                                          * (1.0f - ukWhite) * lerp(0.5f, 1.0f, mainWavePrintGate); // 白泡を除く海面全体
                        inkLine = saturate(max(inkLine, bandContour * _NprBandContourStrength));
                        // 波頂外輪郭。ridgeLift>0 の局所高さ極大を各うねりの太い墨線として描く。
                        // 視角に依存せず、上からのゲームカメラでも緩い波頂を捉える。
                        float crestOutline = smoothstep(_NprCrestOutlineThresh, _NprCrestOutlineThresh + 0.014f, ridgeLift) * (1.0f - ukWhite);
                        inkLine = saturate(max(inkLine, crestOutline * _NprCrestOutlineStrength));
                        // 折れ線は文献第2.1.1節の隣接面法線の差を、高さ場の法線変化として近似する。
                        // 細かい FFT 法線だけでは斑点が出るため、±6 の高さ差によるマクロ法線を基準とする。
                        // fwidth は急な肩や破砕縁で増え、滑らかなうねりではほぼゼロ。
                        // _NprCreaseNFine はマクロ法線（0）と細部法線（1）を混合し、細部と斑点の量を調整する。
                        // 遠方では細部法線が画素へ折り返して斑点になるので、距離に応じて効果を減らす。
                        // _NprLodNear／Far は近遠の距離、_NprLodGamma は減衰曲線の形。
                        float ukNprDist = length(_WorldSpaceCameraPos.xyz - worldPos);
                        float ukNprT    = saturate((_NprLodFar - ukNprDist) / max(_NprLodFar - _NprLodNear, 1.0f));
                        float ukNprLod  = pow(ukNprT, max(_NprLodGamma, 0.01f));
                        float3 ukMacroNcr = normalize(float3(-(hX0 - hX1), 12.0f, -(hZ0 - hZ1)));
                        float3 ukNcr = normalize(lerp(ukMacroNcr, mesoNormal, saturate(_NprCreaseNFine) * ukNprLod));
                        float ukCreaseN = length(fwidth(ukNcr));
                        float ukCrestCrease = smoothstep(_NprCreaseNThresh, _NprCreaseNThresh + max(_NprCreaseNThresh * 0.5f, 0.01f), ukCreaseN);
                        // 折れ線は白域だけに限定せず全波形に描く。ただし細部法線は斑点源なので遠方で弱める。
                        // 中遠景の明瞭な黒輪郭は、距離減衰させない下のシルエット線で保つ。
                        inkLine = saturate(max(inkLine, ukCrestCrease * _NprCreaseNStrength * ukNprLod));
                        // 白泡の波頂シルエットは、面が手前向きから奥向きへ変わる n·v の等値線。
                        // 一定画素幅の墨線とし、平坦寄りのマクロ法線で細波による内部の偽線を減らす。
                        float3 ukMacroN = normalize(float3(-(hX0 - hX1), max(_NprFoamNormalUp, 1.0f), -(hZ0 - hZ1)));
                        float3 ukViewD  = normalize(_WorldSpaceCameraPos.xyz - worldPos);
                        float ukNdV = dot(ukMacroN, ukViewD);
                        float ukNdVDistPx = (ukNdV - _NprFoamProxyLo) / max(fwidth(ukNdV), 1e-5f);   // n·v=Lo の等値線までの符号付き画素距離
                        float ukHalf = max(_NprFoamOutlineWidth, 1.0f) * 0.5f;
                        float ukLineRaw = 1.0f - smoothstep(ukHalf - 0.75f, ukHalf + 0.75f, abs(ukNdVDistPx));
                        // 計算済みの平滑な波頂高さで泡領域を限定し、破砕信号の穴で線が切れないようにする。
                        // _NprFoamProxyWidth は領域の高さしきい値（約 0.68）。
                        float ukHAvg = (hCenter + hX0 + hX1 + hZ0 + hZ1 + hN0 + hN1 + hT0 + hT1 + hT2 + hT3) * 0.0909f;
                        float ukH01avg = saturate(0.5f + (ukHAvg / max(_VerticalDisplacementStrength, 1.0f)) * max(_HeightShadeScale, 0.001f));
                        float ukFoamRegion = smoothstep(_NprFoamProxyWidth, _NprFoamProxyWidth + 0.08f, ukH01avg);
                        float foamInk = ukLineRaw * ukFoamRegion;
                        // シルエットはマクロ法線の清潔な輪郭なので距離減衰しない。
                        // 近景から遠景まで黒線を保ち、細かい折れ線だけを距離で弱める。
                        inkLine = saturate(max(inkLine, foamInk * _NprFoamOutlineStrength));
                        // 文献第2.1.6節の筆線は一定幅でなく、先細りと途切れを持つ。
                        // ここでは画面空間の線マスクを、カメラに追従する雑音で削って近似する。
                        // _NprStrokeVary は線幅変化、_NprStrokeGap は途切れ、_NprStrokeScale は雑音の画素寸法。
                        // +41／+91 は二つの雑音の相関を下げる。
                        float2 ukStrokeUV = (screenUV * _ScreenParams.xy) / max(_NprStrokeScale, 1.0f) + _WorldSpaceCameraPos.xz * _NprPaperFollow + 41.0f;
                        float ukStrokeErode = _NprStrokeVary * (1.0f - PaperNoise(ukStrokeUV));      // 先細りと線幅の変化
                        inkLine = saturate((inkLine - ukStrokeErode) / max(1.0f - ukStrokeErode, 0.05f));
                        float ukStrokeSeg = PaperNoise(ukStrokeUV * 0.4f + 91.0f);                    // 粗い雑音で離散的に途切れる
                        inkLine *= smoothstep(_NprStrokeGap, _NprStrokeGap + 0.12f, ukStrokeSeg);
                        // ① 高さによる先細り（Dadfar と Welling 第5.1節）。波頂で太く、谷で消える原画の線に合わせる。
                        // 平滑な平均高さ ukH01avg で制御する。_NprStrokeTaper は強さ（0 は無効）、
                        // _NprStrokeTaperHeight は細くなり始める高さの中心。
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
