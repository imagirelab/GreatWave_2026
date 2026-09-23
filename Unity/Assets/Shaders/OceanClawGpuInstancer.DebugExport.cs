using System;
using System.IO;
using System.Runtime.InteropServices;
using UnityEngine;

#if UNITY_EDITOR || DEVELOPMENT_BUILD
public partial class OceanClawGpuInstancer
{
    [StructLayout(LayoutKind.Sequential)]
    private struct ClawInstanceSnapshot
    {
        public Vector4 row0;
        public Vector4 row1;
        public Vector4 row2;
        public Vector4 row3;
        public Vector4 parameters;
    }

    [Serializable]
    private class ClawDebugMetrics
    {
        public string metricsVersion;
        public string tuningProfile;
        public string tuningSummary;
        public string screenshotPath;
        public string metricsPath;
        public string timestampUtc;
        public float timeSinceLevelLoad;
        public float snapshotDelay;
        public int maxInstances;
        public int scanGridSize;
        public int visualArcBinCount;
        public float scoreThreshold;
        public float spawnDensity;
        public float screenReferenceStrength;
        public Vector2 screenReferenceCenter;
        public float screenReferenceHalfWidth;
        public float screenReferenceThickness;
        public float screenRibbonClawFollow;
        public Vector2 screenRibbonCenterOffset;
        public float screenRibbonHalfWidthScale;
        public float screenRibbonThicknessScale;
        public float hokusaiArcProfileStrength;
        public float hokusaiCurlShoulderBoost;
        public float hokusaiTailScale;
        public float hokusaiTailRevealDelay;
        public float hokusaiArcLobeContrast;
        public float hokusaiWeakToothRetention;
        public float drawLifeThreshold;
        public float visibleLifeThreshold;
        public float lifeRiseTime;
        public float lifeFallTime;
        public float ribbonOpenFloor;
        public float ribbonDelayCompression;
        public float memberLipThreshold;
        public float memberLipFeather;
        public float hiddenLipSkipScaleY;
        public float visualArcPreviousFailureScaleYMax;
        public float visualArcGapLeakLimit;
        public float visualArcPaintedCoverageLimit;
        public float visualArcLeafCoverageLimit;
        public float visualArcClumpLimit;
        public float visualArcLifecycleScoreLimit;
        public int count;
        public int bad;
        public int visible;
        public int counterOverflow;
        public float scoreAvg;
        public float scoreMax;
        public Vector2 scoreAvgMax;
        public float growthAvg;
        public float growthMax;
        public Vector2 growthAvgMax;
        public float scaleXMax;
        public float scaleYAvg;
        public float scaleYMax;
        public Vector2 scaleYAvgMax;
        public float scaleZAvg;
        public float scaleZMax;
        public Vector2 scaleZAvgMax;
        public float lifeAvg;
        public float lifeMax;
        public int screenVisible;
        public int visualArcOffscreen;
        public int visualArcOffRibbon;
        public int visualArcInRibbon;
        public int[] visualArcBins;
        public float[] visualArcNegativeSpace;
        public float[] visualArcPaintedWeight;
        public float[] visualArcFoamLeafWeight;
        public int[] visualArcExpectedGapBins;
        public int[] visualArcExpectedPaintedBins;
        public int[] visualArcExpectedLeafBins;
        public float[] visualArcScaleYMax;
        public float[] visualArcScaleZMax;
        public float[] visualArcGrowthAvg;
        public float[] visualArcGrowthMax;
        public float[] visualArcLifeAvg;
        public float[] visualArcLifeMax;
        public int[] visualArcGrowthEarlyBins;
        public int[] visualArcGrowthMidBins;
        public int[] visualArcGrowthOpenBins;
        public int growthEarly;
        public int growthMid;
        public int growthOpen;
        public int visualArcGrowthEarly;
        public int visualArcGrowthMid;
        public int visualArcGrowthOpen;
        public int visualArcNonEmptyBins;
        public int visualArcLargestBin;
        public int visualArcExpectedGapBinCount;
        public int visualArcExpectedPaintedBinCount;
        public int visualArcExpectedLeafBinCount;
        public int visualArcGapInstances;
        public int visualArcPaintedInstances;
        public int visualArcLeafInstances;
        public int visualArcPaintedNonEmptyBins;
        public int visualArcLeafNonEmptyBins;
        public float visualArcCoverage;
        public float visualArcClumpRatio;
        public float visualArcRibbonClumpRatio;
        public float visualArcGapLeakRatio;
        public float visualArcPaintedCoverage;
        public float visualArcLeafCoverage;
        public float visualArcPaintedToGapRatio;
        public float visualArcLeafToGapRatio;
        public float visualArcGrowthEarlyRatio;
        public float visualArcGrowthMidRatio;
        public float visualArcGrowthOpenRatio;
        public float visualArcLifecycleLayerScore;
        public float visualArcDistributionScore;
        public float visualArcScaleYMaxOverall;
        public float visualArcScaleZMaxOverall;
        public int badPass;
        public int scaleYUnderPreviousFailurePass;
        public int visualArcGapLeakPass;
        public int visualArcPaintedCoveragePass;
        public int visualArcLeafCoveragePass;
        public int visualArcClumpPass;
        public int visualArcLifecyclePass;
        public int hokusaiMetricsPass;
        public float previousFailedScaleYMax;
        public float hokusaiMetricsGateScore;
        public string hokusaiMetricsSummary;
        public string hokusaiFailureReasons;
        public string hokusaiTuningAdvice;
    }

    private void TryExportDebugSnapshot()
    {
        if (!CanExportDebugSnapshot())
            return;

        if (_instancesBuffer == null || _counterBuffer == null)
            return;

        ClampDebugExportSettings();
        float elapsed = Time.realtimeSinceStartup - _debugSnapshotStartTime;
        if (exportDebugSnapshotSequence)
        {
            for (int i = 0; i < 4; i++)
            {
                float snapshotTime = GetDebugSnapshotSequenceTime(i);
                if (snapshotTime <= 0.001f || elapsed < snapshotTime || (_debugSnapshotSequenceMask & (1 << i)) != 0)
                    continue;

                _debugSnapshotSequenceMask |= 1 << i;
                ExportDebugSnapshot(snapshotTime, BuildDebugSnapshotSuffix(snapshotTime));
                return;
            }

            return;
        }

        if (_debugSnapshotExported || elapsed < debugSnapshotDelay)
            return;

        _debugSnapshotExported = true;
        ExportDebugSnapshot(debugSnapshotDelay, string.Empty);
    }

    private bool CanExportDebugSnapshot()
    {
        if (!exportDebugSnapshotOnPlay || !Application.isPlaying)
            return false;

#if !UNITY_EDITOR && !DEVELOPMENT_BUILD
        return false;
#else
        return true;
#endif
    }

    private void ExportDebugSnapshot(float snapshotDelay, string filenameSuffix)
    {
        try
        {
            string tempDir = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Temp"));
            Directory.CreateDirectory(tempDir);

            string screenshotPath = Path.Combine(tempDir, debugSnapshotBasename + filenameSuffix + "_gameview.png");
            string metricsPath = Path.Combine(tempDir, debugSnapshotBasename + filenameSuffix + "_metrics.json");
            ClawDebugMetrics metrics = CollectClawDebugMetrics(screenshotPath, metricsPath, snapshotDelay);

            File.WriteAllText(metricsPath, JsonUtility.ToJson(metrics, true));
            ScreenCapture.CaptureScreenshot(screenshotPath);
            Debug.Log($"[OceanClawGpuInstancer] Debug snapshot export queued: {screenshotPath}; metrics: {metricsPath}");
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[OceanClawGpuInstancer] Debug snapshot export failed: {ex.Message}");
        }
    }

    private float GetDebugSnapshotSequenceTime(int index)
    {
        switch (index)
        {
            case 0:
                return debugSnapshotSequenceSeconds.x;
            case 1:
                return debugSnapshotSequenceSeconds.y;
            case 2:
                return debugSnapshotSequenceSeconds.z;
            case 3:
                return debugSnapshotSequenceSeconds.w;
            default:
                return 0.0f;
        }
    }

    private string BuildDebugSnapshotSuffix(float snapshotDelay)
    {
        if (Mathf.Abs(snapshotDelay - debugSnapshotDelay) < 0.05f)
            return string.Empty;

        int deciseconds = Mathf.RoundToInt(snapshotDelay * 10.0f);
        int whole = deciseconds / 10;
        int tenth = Mathf.Abs(deciseconds % 10);
        return tenth == 0
            ? $"_{whole:00}s"
            : $"_{whole:00}p{tenth}s";
    }

    private ClawDebugMetrics CollectClawDebugMetrics(string screenshotPath, string metricsPath, float snapshotDelay)
    {
        const int visualArcBinCount = 9;
        const float previousFailureScaleYMax = 109.67f;
        const float visualArcGapLeakLimit = 0.24f;
        const float visualArcPaintedCoverageLimit = 0.60f;
        const float visualArcLeafCoverageLimit = 0.58f;
        const float visualArcClumpLimit = 0.42f;
        const float visualArcLifecycleScoreLimit = 0.67f;
        ClawDebugMetrics metrics = new ClawDebugMetrics
        {
            metricsVersion = "hokusai-visual-ribbon-v3",
            tuningProfile = "visual-ribbon-flattened-claws",
            screenshotPath = screenshotPath,
            metricsPath = metricsPath,
            timestampUtc = DateTime.UtcNow.ToString("O"),
            timeSinceLevelLoad = Time.timeSinceLevelLoad,
            snapshotDelay = snapshotDelay,
            maxInstances = maxInstances,
            scanGridSize = scanGridSize,
            visualArcBinCount = visualArcBinCount,
            scoreThreshold = scoreThreshold,
            spawnDensity = spawnDensity,
            screenReferenceStrength = screenReferenceStrength,
            screenReferenceCenter = screenReferenceCenter,
            screenReferenceHalfWidth = screenReferenceHalfWidth,
            screenReferenceThickness = screenReferenceThickness,
            screenRibbonClawFollow = screenRibbonClawFollow,
            screenRibbonCenterOffset = screenRibbonCenterOffset,
            screenRibbonHalfWidthScale = screenRibbonHalfWidthScale,
            screenRibbonThicknessScale = screenRibbonThicknessScale,
            hokusaiArcProfileStrength = hokusaiArcProfileStrength,
            hokusaiCurlShoulderBoost = hokusaiCurlShoulderBoost,
            hokusaiTailScale = hokusaiTailScale,
            hokusaiTailRevealDelay = hokusaiTailRevealDelay,
            hokusaiArcLobeContrast = hokusaiArcLobeContrast,
            hokusaiWeakToothRetention = hokusaiWeakToothRetention,
            drawLifeThreshold = drawLifeThreshold,
            visibleLifeThreshold = visibleLifeThreshold,
            lifeRiseTime = lifeRiseTime,
            lifeFallTime = lifeFallTime,
            ribbonOpenFloor = ribbonOpenFloor,
            ribbonDelayCompression = ribbonDelayCompression,
            memberLipThreshold = memberLipThreshold,
            memberLipFeather = memberLipFeather,
            hiddenLipSkipScaleY = hiddenLipSkipScaleY,
            visualArcPreviousFailureScaleYMax = previousFailureScaleYMax,
            visualArcGapLeakLimit = visualArcGapLeakLimit,
            visualArcPaintedCoverageLimit = visualArcPaintedCoverageLimit,
            visualArcLeafCoverageLimit = visualArcLeafCoverageLimit,
            visualArcClumpLimit = visualArcClumpLimit,
            visualArcLifecycleScoreLimit = visualArcLifecycleScoreLimit,
            tuningSummary = $"follow={screenRibbonClawFollow:0.###}; lobe={hokusaiArcLobeContrast:0.###}; weakRetention={hokusaiWeakToothRetention:0.###}; drawLife={drawLifeThreshold:0.###}; visibleLife={visibleLifeThreshold:0.###}; life={lifeRiseTime:0.##}/{lifeFallTime:0.##}; ribbonWidth={screenRibbonHalfWidthScale:0.###}; ribbonThickness={screenRibbonThicknessScale:0.###}"
        };

        uint[] counter = { 0u };
        _counterBuffer.GetData(counter);
        uint capacity = (uint)Mathf.Max(0, _bufferCapacity);
        uint rawCount = counter[0];
        metrics.counterOverflow = rawCount > capacity ? 1 : 0;
        metrics.bad = metrics.counterOverflow;
        metrics.count = (int)Math.Min(rawCount, capacity);
        metrics.visualArcBins = new int[visualArcBinCount];
        metrics.visualArcNegativeSpace = new float[visualArcBinCount];
        metrics.visualArcPaintedWeight = new float[visualArcBinCount];
        metrics.visualArcFoamLeafWeight = new float[visualArcBinCount];
        metrics.visualArcExpectedGapBins = new int[visualArcBinCount];
        metrics.visualArcExpectedPaintedBins = new int[visualArcBinCount];
        metrics.visualArcExpectedLeafBins = new int[visualArcBinCount];
        metrics.visualArcScaleYMax = new float[visualArcBinCount];
        metrics.visualArcScaleZMax = new float[visualArcBinCount];
        metrics.visualArcGrowthAvg = new float[visualArcBinCount];
        metrics.visualArcGrowthMax = new float[visualArcBinCount];
        metrics.visualArcLifeAvg = new float[visualArcBinCount];
        metrics.visualArcLifeMax = new float[visualArcBinCount];
        metrics.visualArcGrowthEarlyBins = new int[visualArcBinCount];
        metrics.visualArcGrowthMidBins = new int[visualArcBinCount];
        metrics.visualArcGrowthOpenBins = new int[visualArcBinCount];
        float[] visualArcGrowthSums = new float[visualArcBinCount];
        float[] visualArcLifeSums = new float[visualArcBinCount];
        if (metrics.count <= 0)
        {
            metrics.previousFailedScaleYMax = previousFailureScaleYMax;
            metrics.hokusaiMetricsSummary = "CHECK: no claw instances were exported at this snapshot time";
            metrics.hokusaiFailureReasons = metrics.counterOverflow != 0 ? "counter overflow before instance read" : "no generated claw instances";
            metrics.hokusaiTuningAdvice = "verify Play Mode timing, claw mask input, and reference arc visibility before changing visual ribbon tuning";
            return metrics;
        }

        ClawInstanceSnapshot[] instances = new ClawInstanceSnapshot[metrics.count];
        _instancesBuffer.GetData(instances, 0, 0, metrics.count);

        float scoreSum = 0.0f;
        float growthSum = 0.0f;
        float scaleYSum = 0.0f;
        float scaleZSum = 0.0f;
        float lifeSum = 0.0f;
        int samples = 0;
        Camera referenceCamera = Camera.main;
        Vector2 visualCenter = screenReferenceCenter + screenRibbonCenterOffset;
        float visualHalfWidth = Mathf.Max(screenReferenceHalfWidth * screenRibbonHalfWidthScale, 0.001f);

        for (int i = 0; i < instances.Length; i++)
        {
            ClawInstanceSnapshot instance = instances[i];
            Vector3 scaleX = new Vector3(instance.row0.x, instance.row1.x, instance.row2.x);
            Vector3 scaleY = new Vector3(instance.row0.y, instance.row1.y, instance.row2.y);
            Vector3 scaleZ = new Vector3(instance.row0.z, instance.row1.z, instance.row2.z);

            float scaleXLength = scaleX.magnitude;
            float scaleYLength = scaleY.magnitude;
            float scaleZLength = scaleZ.magnitude;
            bool valid = IsFinite(instance.row0)
                && IsFinite(instance.row1)
                && IsFinite(instance.row2)
                && IsFinite(instance.row3)
                && IsFinite(instance.parameters)
                && IsFinite(scaleXLength)
                && IsFinite(scaleYLength)
                && IsFinite(scaleZLength)
                && scaleXLength > 0.0f
                && scaleYLength > 0.0f
                && scaleZLength > 0.0f
                && scaleXLength < 10000.0f
                && scaleYLength < 10000.0f
                && scaleZLength < 10000.0f;

            if (!valid)
            {
                metrics.bad++;
                continue;
            }

            float score = saturate(instance.parameters.x);
            float life = saturate(instance.parameters.y);
            float growth = saturate(instance.parameters.w);
            scoreSum += score;
            growthSum += growth;
            scaleYSum += scaleYLength;
            scaleZSum += scaleZLength;
            lifeSum += life;
            metrics.scoreMax = Mathf.Max(metrics.scoreMax, score);
            metrics.growthMax = Mathf.Max(metrics.growthMax, growth);
            metrics.scaleXMax = Mathf.Max(metrics.scaleXMax, scaleXLength);
            metrics.scaleYMax = Mathf.Max(metrics.scaleYMax, scaleYLength);
            metrics.scaleZMax = Mathf.Max(metrics.scaleZMax, scaleZLength);
            metrics.lifeMax = Mathf.Max(metrics.lifeMax, life);

            if (life > visibleLifeThreshold)
            {
                metrics.visible++;
                if (growth < 0.34f)
                    metrics.growthEarly++;
                else if (growth < 0.72f)
                    metrics.growthMid++;
                else
                    metrics.growthOpen++;

                if (referenceCamera != null)
                {
                    Vector3 position = new Vector3(instance.row0.w, instance.row1.w, instance.row2.w);
                    Vector3 viewport = referenceCamera.WorldToViewportPoint(position);
                    if (viewport.z > 0.0f
                        && viewport.x >= 0.0f
                        && viewport.x <= 1.0f
                        && viewport.y >= 0.0f
                        && viewport.y <= 1.0f)
                    {
                        metrics.screenVisible++;
                        float nx = (viewport.x - visualCenter.x) / visualHalfWidth;
                        if (Mathf.Abs(nx) <= 1.08f)
                        {
                            int bin = Mathf.Clamp(Mathf.FloorToInt((nx * 0.5f + 0.5f) * visualArcBinCount), 0, visualArcBinCount - 1);
                            metrics.visualArcInRibbon++;
                            metrics.visualArcBins[bin]++;
                            metrics.visualArcScaleYMax[bin] = Mathf.Max(metrics.visualArcScaleYMax[bin], scaleYLength);
                            metrics.visualArcScaleZMax[bin] = Mathf.Max(metrics.visualArcScaleZMax[bin], scaleZLength);
                            visualArcGrowthSums[bin] += growth;
                            metrics.visualArcGrowthMax[bin] = Mathf.Max(metrics.visualArcGrowthMax[bin], growth);
                            visualArcLifeSums[bin] += life;
                            metrics.visualArcLifeMax[bin] = Mathf.Max(metrics.visualArcLifeMax[bin], life);
                            if (growth < 0.34f)
                            {
                                metrics.visualArcGrowthEarly++;
                                metrics.visualArcGrowthEarlyBins[bin]++;
                            }
                            else if (growth < 0.72f)
                            {
                                metrics.visualArcGrowthMid++;
                                metrics.visualArcGrowthMidBins[bin]++;
                            }
                            else
                            {
                                metrics.visualArcGrowthOpen++;
                                metrics.visualArcGrowthOpenBins[bin]++;
                            }
                        }
                        else
                        {
                            metrics.visualArcOffRibbon++;
                        }
                    }
                    else
                    {
                        metrics.visualArcOffscreen++;
                    }
                }
            }

            samples++;
        }

        if (samples > 0)
        {
            metrics.scoreAvg = scoreSum / samples;
            metrics.growthAvg = growthSum / samples;
            metrics.scaleYAvg = scaleYSum / samples;
            metrics.scaleZAvg = scaleZSum / samples;
            metrics.lifeAvg = lifeSum / samples;
        }

        metrics.scoreAvgMax = new Vector2(metrics.scoreAvg, metrics.scoreMax);
        metrics.growthAvgMax = new Vector2(metrics.growthAvg, metrics.growthMax);
        metrics.scaleYAvgMax = new Vector2(metrics.scaleYAvg, metrics.scaleYMax);
        metrics.scaleZAvgMax = new Vector2(metrics.scaleZAvg, metrics.scaleZMax);
        int largestBin = 0;
        int nonEmptyBins = 0;
        int paintedNonEmptyBins = 0;
        int leafNonEmptyBins = 0;
        float lobeStrength = Mathf.Clamp01(hokusaiArcLobeContrast);
        for (int i = 0; i < metrics.visualArcBins.Length; i++)
        {
            largestBin = Mathf.Max(largestBin, metrics.visualArcBins[i]);
            float nx = ((i + 0.5f) / metrics.visualArcBins.Length) * 2.0f - 1.0f;
            float curlShoulder01 = VisualArcCurlShoulder01(nx);
            float negativeSpace = HokusaiArcNegativeSpaceProfile01(curlShoulder01) * lobeStrength;
            float paintedWeight = HokusaiArcPaintedBandWeight01(curlShoulder01);
            float foamLeafWeight = HokusaiArcFoamLeafWeight01(curlShoulder01);
            bool expectedGap = negativeSpace >= 0.28f;
            bool expectedPainted = paintedWeight >= 0.76f && negativeSpace < 0.36f;
            bool expectedLeaf = foamLeafWeight >= 0.58f && negativeSpace < 0.36f;

            metrics.visualArcNegativeSpace[i] = negativeSpace;
            metrics.visualArcPaintedWeight[i] = paintedWeight;
            metrics.visualArcFoamLeafWeight[i] = foamLeafWeight;
            metrics.visualArcExpectedGapBins[i] = expectedGap ? 1 : 0;
            metrics.visualArcExpectedPaintedBins[i] = expectedPainted ? 1 : 0;
            metrics.visualArcExpectedLeafBins[i] = expectedLeaf ? 1 : 0;

            if (expectedGap)
            {
                metrics.visualArcExpectedGapBinCount++;
                metrics.visualArcGapInstances += metrics.visualArcBins[i];
            }
            if (expectedPainted)
            {
                metrics.visualArcExpectedPaintedBinCount++;
                metrics.visualArcPaintedInstances += metrics.visualArcBins[i];
                if (metrics.visualArcBins[i] > 0)
                    paintedNonEmptyBins++;
            }
            if (expectedLeaf)
            {
                metrics.visualArcExpectedLeafBinCount++;
                metrics.visualArcLeafInstances += metrics.visualArcBins[i];
                if (metrics.visualArcBins[i] > 0)
                    leafNonEmptyBins++;
            }

            if (metrics.visualArcBins[i] > 0)
            {
                nonEmptyBins++;
                metrics.visualArcGrowthAvg[i] = visualArcGrowthSums[i] / metrics.visualArcBins[i];
                metrics.visualArcLifeAvg[i] = visualArcLifeSums[i] / metrics.visualArcBins[i];
            }

            metrics.visualArcScaleYMaxOverall = Mathf.Max(metrics.visualArcScaleYMaxOverall, metrics.visualArcScaleYMax[i]);
            metrics.visualArcScaleZMaxOverall = Mathf.Max(metrics.visualArcScaleZMaxOverall, metrics.visualArcScaleZMax[i]);
        }
        metrics.visualArcNonEmptyBins = nonEmptyBins;
        metrics.visualArcLargestBin = largestBin;
        metrics.visualArcPaintedNonEmptyBins = paintedNonEmptyBins;
        metrics.visualArcLeafNonEmptyBins = leafNonEmptyBins;
        metrics.visualArcCoverage = metrics.visualArcBins.Length > 0 ? nonEmptyBins / (float)metrics.visualArcBins.Length : 0.0f;
        metrics.visualArcClumpRatio = metrics.screenVisible > 0 ? largestBin / (float)metrics.screenVisible : 0.0f;
        metrics.visualArcRibbonClumpRatio = metrics.visualArcInRibbon > 0 ? largestBin / (float)metrics.visualArcInRibbon : 0.0f;
        metrics.visualArcGapLeakRatio = metrics.visualArcInRibbon > 0 ? metrics.visualArcGapInstances / (float)metrics.visualArcInRibbon : 0.0f;
        metrics.visualArcPaintedCoverage = metrics.visualArcExpectedPaintedBinCount > 0 ? metrics.visualArcPaintedNonEmptyBins / (float)metrics.visualArcExpectedPaintedBinCount : 0.0f;
        metrics.visualArcLeafCoverage = metrics.visualArcExpectedLeafBinCount > 0 ? metrics.visualArcLeafNonEmptyBins / (float)metrics.visualArcExpectedLeafBinCount : 0.0f;
        metrics.visualArcPaintedToGapRatio = metrics.visualArcGapInstances > 0 ? metrics.visualArcPaintedInstances / (float)metrics.visualArcGapInstances : metrics.visualArcPaintedInstances;
        metrics.visualArcLeafToGapRatio = metrics.visualArcGapInstances > 0 ? metrics.visualArcLeafInstances / (float)metrics.visualArcGapInstances : metrics.visualArcLeafInstances;
        metrics.visualArcGrowthEarlyRatio = metrics.visualArcInRibbon > 0 ? metrics.visualArcGrowthEarly / (float)metrics.visualArcInRibbon : 0.0f;
        metrics.visualArcGrowthMidRatio = metrics.visualArcInRibbon > 0 ? metrics.visualArcGrowthMid / (float)metrics.visualArcInRibbon : 0.0f;
        metrics.visualArcGrowthOpenRatio = metrics.visualArcInRibbon > 0 ? metrics.visualArcGrowthOpen / (float)metrics.visualArcInRibbon : 0.0f;
        metrics.visualArcLifecycleLayerScore = Mathf.Clamp01(
            (metrics.visualArcGrowthEarlyRatio > 0.03f ? 0.34f : 0.0f)
            + (metrics.visualArcGrowthMidRatio > 0.08f ? 0.33f : 0.0f)
            + (metrics.visualArcGrowthOpenRatio > 0.12f ? 0.33f : 0.0f));
        metrics.visualArcDistributionScore = Mathf.Clamp01(
            metrics.visualArcPaintedCoverage
            * Mathf.Lerp(0.78f, 1.0f, metrics.visualArcLeafCoverage)
            * (1.0f - metrics.visualArcGapLeakRatio)
            * (1.0f - Mathf.Clamp01(metrics.visualArcRibbonClumpRatio - 0.42f))
            * Mathf.Lerp(0.72f, 1.0f, metrics.visualArcLifecycleLayerScore));
        metrics.previousFailedScaleYMax = previousFailureScaleYMax;
        metrics.badPass = metrics.bad == 0 ? 1 : 0;
        metrics.scaleYUnderPreviousFailurePass = metrics.visualArcScaleYMaxOverall > 0.0f && metrics.visualArcScaleYMaxOverall < metrics.previousFailedScaleYMax ? 1 : 0;
        metrics.visualArcGapLeakPass = metrics.visualArcInRibbon > 0 && metrics.visualArcGapLeakRatio <= visualArcGapLeakLimit ? 1 : 0;
        metrics.visualArcPaintedCoveragePass = metrics.visualArcPaintedCoverage >= visualArcPaintedCoverageLimit ? 1 : 0;
        metrics.visualArcLeafCoveragePass = metrics.visualArcLeafCoverage >= visualArcLeafCoverageLimit ? 1 : 0;
        metrics.visualArcClumpPass = metrics.visualArcInRibbon > 0 && metrics.visualArcRibbonClumpRatio <= visualArcClumpLimit ? 1 : 0;
        metrics.visualArcLifecyclePass = metrics.visualArcLifecycleLayerScore >= visualArcLifecycleScoreLimit ? 1 : 0;
        metrics.hokusaiMetricsPass =
            metrics.badPass
            * metrics.scaleYUnderPreviousFailurePass
            * metrics.visualArcGapLeakPass
            * metrics.visualArcPaintedCoveragePass
            * metrics.visualArcLeafCoveragePass
            * metrics.visualArcClumpPass
            * metrics.visualArcLifecyclePass;
        int passedGates = metrics.badPass
            + metrics.scaleYUnderPreviousFailurePass
            + metrics.visualArcGapLeakPass
            + metrics.visualArcPaintedCoveragePass
            + metrics.visualArcLeafCoveragePass
            + metrics.visualArcClumpPass
            + metrics.visualArcLifecyclePass;
        metrics.hokusaiMetricsGateScore = passedGates / 7.0f;
        string reasons = string.Empty;
        string advice = string.Empty;
        if (metrics.badPass == 0)
        {
            reasons = AppendMetricNote(reasons, "bad instances or counter overflow detected");
            advice = AppendMetricNote(advice, "inspect invalid instance data and keep visual height/scale caps conservative");
        }
        if (metrics.scaleYUnderPreviousFailurePass == 0)
        {
            reasons = AppendMetricNote(reasons, "visual arc scaleY max is not safely below the previous spike failure");
            advice = AppendMetricNote(advice, "lower visual foam height cap or reduce Hokusai/visual ribbon scale lift before increasing density");
        }
        if (metrics.visualArcGapLeakPass == 0)
        {
            reasons = AppendMetricNote(reasons, "too many claws leaked into Hokusai negative-space gap bins");
            advice = AppendMetricNote(advice, "reduce visual follow or strengthen negative-space suppression before adding more teeth");
        }
        if (metrics.visualArcPaintedCoveragePass == 0)
        {
            reasons = AppendMetricNote(reasons, "expected painted foam-band bins are under-covered");
            advice = AppendMetricNote(advice, "increase painted-band retention or slightly raise visual follow/coverage after spike checks pass");
        }
        if (metrics.visualArcLeafCoveragePass == 0)
        {
            reasons = AppendMetricNote(reasons, "expected Hokusai foam-leaf clusters are under-covered");
            advice = AppendMetricNote(advice, "raise leaf-cluster retention or loosen leaf bin suppression without filling negative-space gap bins");
        }
        if (metrics.visualArcClumpPass == 0)
        {
            reasons = AppendMetricNote(reasons, "one visual arc bin is still too dominant");
            advice = AppendMetricNote(advice, "spread segmented arc slots or reduce visual candidate weighting to avoid a clump");
        }
        if (metrics.visualArcLifecyclePass == 0)
        {
            reasons = AppendMetricNote(reasons, "visual arc lacks early/mid/open lifecycle layering");
            advice = AppendMetricNote(advice, "increase member delay stagger or reduce over-retention so foam does not appear fully open at once");
        }

        metrics.hokusaiFailureReasons = string.IsNullOrEmpty(reasons) ? "none" : reasons;
        metrics.hokusaiTuningAdvice = string.IsNullOrEmpty(advice) ? "hold current tuning and judge the screenshot for art-direction refinements" : advice;
        metrics.hokusaiMetricsSummary = metrics.hokusaiMetricsPass == 1
            ? "PASS: known Hokusai claw metrics gates passed; confirm final art direction in screenshot"
            : "CHECK: one or more Hokusai claw metrics gates failed; read hokusaiFailureReasons and hokusaiTuningAdvice";
        return metrics;
    }

    private static string AppendMetricNote(string current, string note)
    {
        return string.IsNullOrEmpty(current) ? note : current + "; " + note;
    }

    private float VisualArcCurlShoulder01(float nx)
    {
        float shoulderSide = referenceArcDensityBias < 0.0f ? -1.0f : 1.0f;
        return Mathf.Clamp01(0.5f + shoulderSide * nx * 0.5f);
    }

}
#endif