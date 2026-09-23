using UnityEngine;
using UnityEngine.Rendering;

public partial class OceanClawGpuInstancer
{
    private const int ScreenRibbonSegments = 56;
    private const int ScreenRibbonCrossSections = 10;
    private const int ScreenRibbonCrossVertices = ScreenRibbonCrossSections + 1;
    private const int ScreenRibbonToothCount = 7;
    private const int ScreenRibbonToothVertices = ScreenRibbonToothCount * 4;
    private const int ScreenRibbonToothTriangles = ScreenRibbonToothCount * 6;

    private Mesh _screenFoamRibbonMesh;
    private Material _screenFoamRibbonMaterial;
    private GameObject _screenFoamRibbonObject;
    private MeshFilter _screenFoamRibbonFilter;
    private MeshRenderer _screenFoamRibbonRenderer;
    private Vector3[] _screenRibbonVertices;
    private Vector2[] _screenRibbonUvs;
    private Color[] _screenRibbonColors;
    private int[] _screenRibbonTriangles;
    private float _screenFoamRibbonVisibility;

    /// <summary>
    /// 主な爪状白波の配置に使う基準曲線に沿って、カメラ空間に連続した白波の帯を描画する。
    /// </summary>
    private void DrawScreenReferenceFoamRibbon()
    {
        Camera referenceCamera = Camera.main;
        bool shouldDraw = drawScreenReferenceFoamRibbon
            && useScreenReferenceMask
            && referenceCamera != null
            && screenRibbonAlpha > 0.001f
            && screenReferenceStrength > 0.001f;

        float targetVisibility = shouldDraw ? 1.0f : 0.0f;
        float rise = Mathf.Max(lifeRiseTime, 0.001f);
        float fall = Mathf.Max(lifeFallTime * 0.35f, 0.001f);
        float speed = targetVisibility > _screenFoamRibbonVisibility ? 1.0f / rise : 1.0f / fall;
        _screenFoamRibbonVisibility = Mathf.MoveTowards(_screenFoamRibbonVisibility, targetVisibility, Time.deltaTime * speed);

        if (_screenFoamRibbonVisibility <= 0.001f || referenceCamera == null)
        {
            if (_screenFoamRibbonRenderer != null)
                _screenFoamRibbonRenderer.enabled = false;
            return;
        }

        Mesh mesh = BuildScreenFoamRibbonMesh(referenceCamera);
        Material material = GetScreenFoamRibbonMaterial();
        if (mesh == null || material == null)
            return;

        Color ribbonColor = screenRibbonColor;
        ribbonColor.a = screenRibbonAlpha * _screenFoamRibbonVisibility * saturate(screenReferenceStrength);
        Color edgeColor = screenRibbonEdgeColor;
        edgeColor.a *= _screenFoamRibbonVisibility;
        material.SetColor("_RibbonColor", ribbonColor);
        material.SetColor("_EdgeColor", edgeColor);
        material.SetFloat("_EdgeBlend", screenRibbonEdgeBlend);

        MeshRenderer ribbonRenderer = EnsureScreenFoamRibbonRenderer();
        if (ribbonRenderer == null)
            return;

        _screenFoamRibbonObject.layer = gameObject.layer;
        _screenFoamRibbonObject.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
        _screenFoamRibbonObject.transform.localScale = Vector3.one;
        _screenFoamRibbonFilter.sharedMesh = mesh;
        ribbonRenderer.sharedMaterial = material;
        ribbonRenderer.enabled = true;
    }

    /// <summary>
    /// 画面への投影が基準曲線に正確に沿う、小さなワールド空間のメッシュを再構築する。
    /// </summary>
    private Mesh BuildScreenFoamRibbonMesh(Camera referenceCamera)
    {
        if (_screenFoamRibbonMesh == null)
        {
            _screenFoamRibbonMesh = new Mesh
            {
                name = "Hokusai Screen Reference Foam Ribbon",
                hideFlags = HideFlags.HideAndDontSave
            };
            _screenFoamRibbonMesh.MarkDynamic();
        }

        EnsureScreenRibbonMeshBuffers();
        Vector3[] vertices = _screenRibbonVertices;
        Vector2[] uvs = _screenRibbonUvs;
        Color[] colors = _screenRibbonColors;
        int[] triangles = _screenRibbonTriangles;

        float halfWidth = Mathf.Max(screenReferenceHalfWidth * screenRibbonHalfWidthScale, 0.001f);
        float halfThickness = Mathf.Max(screenReferenceThickness * screenRibbonThicknessScale, 0.006f);
        float depth = Mathf.Clamp(screenRibbonDepth, referenceCamera.nearClipPlane + 0.01f, referenceCamera.farClipPlane * 0.95f);

        for (int i = 0; i <= ScreenRibbonSegments; i++)
        {
            float t = i / (float)ScreenRibbonSegments;
            float nx = Mathf.Lerp(-0.96f, 0.96f, t);
            Vector2 center = EvaluateScreenReferenceArc(nx, halfWidth);
            Vector2 prev = EvaluateScreenReferenceArc(Mathf.Clamp(nx - 0.04f, -0.96f, 0.96f), halfWidth);
            Vector2 next = EvaluateScreenReferenceArc(Mathf.Clamp(nx + 0.04f, -0.96f, 0.96f), halfWidth);
            Vector2 tangent = next - prev;
            if (tangent.sqrMagnitude < 0.000001f)
                tangent = Vector2.right;
            tangent.Normalize();
            Vector2 normal = new Vector2(-tangent.y, tangent.x);

            float endFade = Mathf.SmoothStep(0.0f, 1.0f, Mathf.Sin(t * Mathf.PI));
            float shoulderSide = referenceArcDensityBias < 0.0f ? -1.0f : 1.0f;
            float curlShoulder01 = Mathf.Clamp01(0.5f + shoulderSide * nx * 0.5f);
            float tail01 = Mathf.Clamp01(1.0f - curlShoulder01);
            float shoulderCrown = smoothstep(0.34f, 0.62f, curlShoulder01)
                * (1.0f - smoothstep(0.78f, 0.96f, curlShoulder01));
            float innerTooth = smoothstep(0.10f, 0.30f, curlShoulder01)
                * (1.0f - smoothstep(0.46f, 0.66f, curlShoulder01));
            float hookTip = smoothstep(0.82f, 0.98f, curlShoulder01);
            float tailTaper = smoothstep(0.36f, 1.0f, tail01);
            float lobeWave = 0.5f + 0.5f * Mathf.Sin((curlShoulder01 * 5.65f + randomSeed * 0.017f) * Mathf.PI * 2.0f);
            float lobeBreak = smoothstep(0.20f, 0.84f, lobeWave);
            float negativeSpace = HokusaiArcNegativeSpaceProfile01(curlShoulder01) * Mathf.Clamp01(hokusaiArcLobeContrast);
            float paintedBand = HokusaiArcPaintedBandWeight01(curlShoulder01);
            float foamLeaf = HokusaiArcFoamLeafWeight01(curlShoulder01);
            float paintedBandStrength = Mathf.Clamp01(hokusaiArcLobeContrast) * (1.0f - Mathf.Clamp01(negativeSpace));
            float foamMass = Mathf.Clamp01(
                shoulderCrown * 0.68f
                + innerTooth * 0.30f
                + hookTip * 0.42f
                + Mathf.Clamp01(paintedBand) * 0.34f
                + foamLeaf * 0.48f);
            float printedPresence = Mathf.Clamp01(
                shoulderCrown * 0.72f
                + innerTooth * 0.36f
                + hookTip * 0.52f
                + foamLeaf * 0.90f
                + smoothstep(0.56f, 1.06f, paintedBand) * 0.38f
                - negativeSpace * 0.38f);
            float lobeThickness = 0.92f
                + shoulderCrown * 1.06f
                + innerTooth * 0.30f
                + hookTip * 0.42f
                - tailTaper * 0.18f;
            lobeThickness *= Mathf.Lerp(0.82f, 1.16f, lobeBreak);
            lobeThickness *= Mathf.Lerp(1.0f, 0.90f, negativeSpace);
            lobeThickness *= Mathf.Lerp(1.0f, Mathf.Lerp(0.84f, 1.28f, Mathf.Clamp01(paintedBand)), paintedBandStrength * 0.64f);
            lobeThickness *= Mathf.Lerp(1.0f, Mathf.Lerp(0.88f, 1.32f, foamLeaf), paintedBandStrength * 0.86f);
            float lobeAlpha = Mathf.Clamp01(0.64f
                + shoulderCrown * 0.26f
                + innerTooth * 0.10f
                + hookTip * 0.10f
                - tailTaper * 0.22f);
            lobeAlpha *= Mathf.Lerp(0.68f, 1.0f, lobeBreak);
            lobeAlpha *= Mathf.Lerp(1.0f, 0.82f, negativeSpace);
            lobeAlpha *= Mathf.Lerp(1.0f, Mathf.Lerp(0.86f, 1.22f, Mathf.Clamp01(paintedBand)), paintedBandStrength * 0.68f);
            lobeAlpha *= Mathf.Lerp(1.0f, Mathf.Lerp(0.88f, 1.24f, foamLeaf), paintedBandStrength * 0.82f);
            lobeAlpha *= Mathf.Lerp(0.72f, 1.0f, smoothstep(0.18f, 0.62f, printedPresence));
            float handVariation = 1.0f + 0.11f * Mathf.Sin(t * 17.0f + randomSeed * 0.013f) + 0.06f * Mathf.Sin(t * 41.0f + 1.7f);
            float width = halfThickness
                * 1.58f
                * Mathf.Lerp(0.62f, 1.0f, endFade)
                * Mathf.Lerp(0.72f, 1.0f, printedPresence)
                * handVariation
                * Mathf.Max(0.58f, lobeThickness);
            float toothProfile = (
                ScreenRibbonTooth(t, 0.17f, 0.024f) * 0.24f
                + ScreenRibbonTooth(t, 0.27f, 0.020f) * 0.40f
                + ScreenRibbonTooth(t, 0.37f, 0.019f) * 0.34f
                + ScreenRibbonTooth(t, 0.48f, 0.020f) * 0.42f
                + ScreenRibbonTooth(t, 0.58f, 0.021f) * 0.36f
                + ScreenRibbonTooth(t, 0.69f, 0.022f) * 0.30f
                + ScreenRibbonTooth(t, 0.80f, 0.025f) * 0.22f)
                * endFade
                * Mathf.Lerp(0.42f, 1.0f, Mathf.Max(foamMass, printedPresence));
            float toothSkew = (
                ScreenRibbonTooth(t, 0.17f, 0.026f) * -0.34f
                + ScreenRibbonTooth(t, 0.27f, 0.022f) * -0.24f
                + ScreenRibbonTooth(t, 0.37f, 0.021f) * -0.08f
                + ScreenRibbonTooth(t, 0.48f, 0.022f) * 0.10f
                + ScreenRibbonTooth(t, 0.58f, 0.023f) * 0.22f
                + ScreenRibbonTooth(t, 0.69f, 0.024f) * 0.32f
                + ScreenRibbonTooth(t, 0.80f, 0.027f) * 0.40f);
            float crestSideBias = Mathf.Lerp(-0.06f, 0.16f, curlShoulder01) + hookTip * 0.08f - innerTooth * 0.04f;
            Vector2 biasedCenter = center + normal * (width * crestSideBias * endFade);

            for (int j = 0; j <= ScreenRibbonCrossSections; j++)
            {
                float u = j / (float)ScreenRibbonCrossSections;
                float signedWidth = (u - 0.5f) * 2.0f;
                float absWidth = Mathf.Abs(signedWidth);
                float centerFill = 1.0f - absWidth;
                float rimFade = 1.0f - smoothstep(0.74f, 1.0f, absWidth);
                float laneBrush = 1.0f
                    + 0.06f * Mathf.Sin(t * 23.0f + j * 0.91f + randomSeed * 0.011f) * Mathf.Lerp(0.35f, 1.0f, foamMass)
                    + 0.035f * Mathf.Sin(t * 61.0f + j * 1.37f + 2.2f);
                float laneOffset = signedWidth * width * laneBrush;
                float lowerSide = normal.y * signedWidth < 0.0f ? 1.0f : 0.0f;
                float toothEdge = lowerSide * smoothstep(0.80f, 1.0f, absWidth) * toothProfile;
                laneOffset *= 1.0f + toothEdge * 0.72f;
                Vector2 point = biasedCenter + normal * laneOffset;
                point += tangent * (width * toothEdge * toothSkew * 0.42f);
                point += Vector2.down * (width * toothEdge * 0.10f);

                int vertexIndex = i * ScreenRibbonCrossVertices + j;
                vertices[vertexIndex] = referenceCamera.ViewportToWorldPoint(new Vector3(point.x, point.y, depth));
                uvs[vertexIndex] = new Vector2(u, t);
                float laneAlpha = endFade * lobeAlpha;
                laneAlpha *= Mathf.Lerp(0.82f, 1.0f, centerFill);
                laneAlpha *= Mathf.Lerp(0.82f, 1.06f, rimFade);
                laneAlpha *= Mathf.Lerp(0.88f, 1.18f, foamMass);
                colors[vertexIndex] = new Color(1.0f, 1.0f, 1.0f, Mathf.Clamp01(laneAlpha));
            }
        }

        FillScreenRibbonToothVertices(referenceCamera, halfWidth, halfThickness, depth);

        _screenFoamRibbonMesh.Clear();
        _screenFoamRibbonMesh.vertices = vertices;
        _screenFoamRibbonMesh.uv = uvs;
        _screenFoamRibbonMesh.colors = colors;
        _screenFoamRibbonMesh.triangles = triangles;
        _screenFoamRibbonMesh.RecalculateBounds();
        return _screenFoamRibbonMesh;
    }

    private static float ScreenRibbonTooth(float t, float center, float width)
    {
        float x = (t - center) / Mathf.Max(width, 0.0001f);
        return Mathf.Exp(-x * x);
    }

    private void FillScreenRibbonToothVertices(Camera referenceCamera, float halfWidth, float halfThickness, float depth)
    {
        int baseVertexCount = (ScreenRibbonSegments + 1) * ScreenRibbonCrossVertices;
        float[] centers = { 0.18f, 0.29f, 0.39f, 0.50f, 0.61f, 0.72f, 0.83f };
        float[] rootWidths = { 0.72f, 0.58f, 0.52f, 0.66f, 0.50f, 0.44f, 0.36f };
        float[] lengths = { 1.26f, 1.58f, 1.36f, 1.72f, 1.32f, 1.08f, 0.78f };
        float[] skews = { -0.58f, -0.36f, -0.12f, 0.10f, 0.28f, 0.42f, 0.56f };

        for (int k = 0; k < ScreenRibbonToothCount; k++)
        {
            float t = centers[k];
            float nx = Mathf.Lerp(-0.96f, 0.96f, t);
            Vector2 center = EvaluateScreenReferenceArc(nx, halfWidth);
            Vector2 prev = EvaluateScreenReferenceArc(Mathf.Clamp(nx - 0.04f, -0.96f, 0.96f), halfWidth);
            Vector2 next = EvaluateScreenReferenceArc(Mathf.Clamp(nx + 0.04f, -0.96f, 0.96f), halfWidth);
            Vector2 tangent = next - prev;
            if (tangent.sqrMagnitude < 0.000001f)
                tangent = Vector2.right;
            tangent.Normalize();
            Vector2 normal = new Vector2(-tangent.y, tangent.x);
            Vector2 lowerNormal = normal.y < 0.0f ? normal : -normal;

            float endFade = Mathf.SmoothStep(0.0f, 1.0f, Mathf.Sin(t * Mathf.PI));
            float hand = 1.0f + 0.08f * Mathf.Sin(t * 37.0f + randomSeed * 0.019f);
            float width = halfThickness * 1.58f * Mathf.Lerp(0.78f, 1.0f, endFade) * hand;
            float rootHalf = width * rootWidths[k];
            float toothLength = width * lengths[k];
            Vector2 rootCenter = center + lowerNormal * (width * 0.72f);
            Vector2 left = rootCenter - tangent * rootHalf;
            Vector2 right = rootCenter + tangent * rootHalf;
            Vector2 shoulder = rootCenter + lowerNormal * (toothLength * 0.52f) + tangent * (width * skews[k] * 0.30f);
            Vector2 tip = rootCenter + lowerNormal * toothLength + tangent * (width * skews[k]);

            int vertexIndex = baseVertexCount + k * 4;
            _screenRibbonVertices[vertexIndex] = referenceCamera.ViewportToWorldPoint(new Vector3(left.x, left.y, depth));
            _screenRibbonVertices[vertexIndex + 1] = referenceCamera.ViewportToWorldPoint(new Vector3(right.x, right.y, depth));
            _screenRibbonVertices[vertexIndex + 2] = referenceCamera.ViewportToWorldPoint(new Vector3(shoulder.x, shoulder.y, depth));
            _screenRibbonVertices[vertexIndex + 3] = referenceCamera.ViewportToWorldPoint(new Vector3(tip.x, tip.y, depth));
            _screenRibbonUvs[vertexIndex] = new Vector2(0.04f, t);
            _screenRibbonUvs[vertexIndex + 1] = new Vector2(0.96f, t);
            _screenRibbonUvs[vertexIndex + 2] = new Vector2(0.50f, t);
            _screenRibbonUvs[vertexIndex + 3] = new Vector2(0.50f, t);
            Color color = new Color(1.0f, 1.0f, 1.0f, Mathf.Lerp(0.86f, 1.0f, endFade));
            _screenRibbonColors[vertexIndex] = color;
            _screenRibbonColors[vertexIndex + 1] = color;
            _screenRibbonColors[vertexIndex + 2] = color;
            _screenRibbonColors[vertexIndex + 3] = color;
        }
    }

    private void EnsureScreenRibbonMeshBuffers()
    {
        int baseVertexCount = (ScreenRibbonSegments + 1) * ScreenRibbonCrossVertices;
        int vertexCount = baseVertexCount + ScreenRibbonToothVertices;
        int indexCount = ScreenRibbonSegments * ScreenRibbonCrossSections * 6 + ScreenRibbonToothTriangles;
        if (_screenRibbonVertices == null
            || _screenRibbonUvs == null
            || _screenRibbonColors == null
            || _screenRibbonVertices.Length != vertexCount
            || _screenRibbonUvs.Length != vertexCount
            || _screenRibbonColors.Length != vertexCount)
        {
            _screenRibbonVertices = new Vector3[vertexCount];
            _screenRibbonUvs = new Vector2[vertexCount];
            _screenRibbonColors = new Color[vertexCount];
        }

        if (_screenRibbonTriangles != null && _screenRibbonTriangles.Length == indexCount)
            return;

        _screenRibbonTriangles = new int[indexCount];
        int triangleIndex = 0;
        for (int i = 0; i < ScreenRibbonSegments; i++)
        {
            for (int j = 0; j < ScreenRibbonCrossSections; j++)
            {
                int vertexIndex = i * ScreenRibbonCrossVertices + j;
                int nextRow = vertexIndex + ScreenRibbonCrossVertices;
                _screenRibbonTriangles[triangleIndex] = vertexIndex;
                _screenRibbonTriangles[triangleIndex + 1] = nextRow;
                _screenRibbonTriangles[triangleIndex + 2] = vertexIndex + 1;
                _screenRibbonTriangles[triangleIndex + 3] = vertexIndex + 1;
                _screenRibbonTriangles[triangleIndex + 4] = nextRow;
                _screenRibbonTriangles[triangleIndex + 5] = nextRow + 1;
                triangleIndex += 6;
            }
        }

        for (int k = 0; k < ScreenRibbonToothCount; k++)
        {
            int vertexIndex = baseVertexCount + k * 4;
            _screenRibbonTriangles[triangleIndex] = vertexIndex;
            _screenRibbonTriangles[triangleIndex + 1] = vertexIndex + 2;
            _screenRibbonTriangles[triangleIndex + 2] = vertexIndex + 1;
            _screenRibbonTriangles[triangleIndex + 3] = vertexIndex + 1;
            _screenRibbonTriangles[triangleIndex + 4] = vertexIndex + 2;
            _screenRibbonTriangles[triangleIndex + 5] = vertexIndex + 3;
            triangleIndex += 6;
        }
    }

    private Vector2 EvaluateScreenReferenceArc(float nx, float halfWidth)
    {
        float clampedNx = Mathf.Clamp(nx, -0.96f, 0.96f);
        Vector2 visualCenter = screenReferenceCenter + screenRibbonCenterOffset;
        float viewportX = visualCenter.x + clampedNx * halfWidth;
        float viewportY = visualCenter.y
                        + screenReferenceBend * screenRibbonBendScale * (1.0f - Mathf.Clamp01(clampedNx * clampedNx))
                        + screenReferenceTilt * screenRibbonTiltScale * clampedNx;
        return new Vector2(viewportX, viewportY);
    }

    private Material GetScreenFoamRibbonMaterial()
    {
        if (_screenFoamRibbonMaterial != null)
            return _screenFoamRibbonMaterial;

        Shader shader = Shader.Find("MasterProject/HokusaiFoamRibbon");
        if (shader == null)
            return null;

        _screenFoamRibbonMaterial = new Material(shader)
        {
            name = "Hokusai Screen Foam Ribbon (Runtime)",
            hideFlags = HideFlags.HideAndDontSave
        };
        return _screenFoamRibbonMaterial;
    }

    private MeshRenderer EnsureScreenFoamRibbonRenderer()
    {
        if (_screenFoamRibbonRenderer != null && _screenFoamRibbonFilter != null)
            return _screenFoamRibbonRenderer;

        _screenFoamRibbonObject = new GameObject("Hokusai Screen Foam Ribbon Renderer")
        {
            hideFlags = HideFlags.HideAndDontSave
        };
        _screenFoamRibbonObject.transform.SetParent(transform, false);
        _screenFoamRibbonObject.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
        _screenFoamRibbonObject.transform.localScale = Vector3.one;

        _screenFoamRibbonFilter = _screenFoamRibbonObject.AddComponent<MeshFilter>();
        _screenFoamRibbonRenderer = _screenFoamRibbonObject.AddComponent<MeshRenderer>();
        _screenFoamRibbonRenderer.shadowCastingMode = ShadowCastingMode.Off;
        _screenFoamRibbonRenderer.receiveShadows = false;
        _screenFoamRibbonRenderer.lightProbeUsage = LightProbeUsage.Off;
        _screenFoamRibbonRenderer.reflectionProbeUsage = ReflectionProbeUsage.Off;
        _screenFoamRibbonRenderer.enabled = false;
        return _screenFoamRibbonRenderer;
    }

    private void ReleaseScreenFoamRibbonResources()
    {
        if (_screenFoamRibbonObject != null)
        {
            if (Application.isPlaying)
                Destroy(_screenFoamRibbonObject);
            else
                DestroyImmediate(_screenFoamRibbonObject);
            _screenFoamRibbonObject = null;
            _screenFoamRibbonFilter = null;
            _screenFoamRibbonRenderer = null;
        }

        if (_screenFoamRibbonMesh != null)
        {
            if (Application.isPlaying)
                Destroy(_screenFoamRibbonMesh);
            else
                DestroyImmediate(_screenFoamRibbonMesh);
            _screenFoamRibbonMesh = null;
        }

        if (_screenFoamRibbonMaterial != null)
        {
            if (Application.isPlaying)
                Destroy(_screenFoamRibbonMaterial);
            else
                DestroyImmediate(_screenFoamRibbonMaterial);
            _screenFoamRibbonMaterial = null;
        }

        _screenRibbonVertices = null;
        _screenRibbonUvs = null;
        _screenRibbonColors = null;
        _screenRibbonTriangles = null;
        _screenFoamRibbonVisibility = 0.0f;
    }

    private static float HokusaiArcNegativeSpaceProfile01(float curlShoulder01)
    {
        float tailPocket = smoothstep(0.05f, 0.14f, curlShoulder01)
                         * (1.0f - smoothstep(0.22f, 0.32f, curlShoulder01));
        float innerPocket = smoothstep(0.29f, 0.38f, curlShoulder01)
                          * (1.0f - smoothstep(0.43f, 0.50f, curlShoulder01));
        float crownPocket = smoothstep(0.64f, 0.72f, curlShoulder01)
                          * (1.0f - smoothstep(0.80f, 0.88f, curlShoulder01));
        return Mathf.Clamp01(Mathf.Max(Mathf.Max(tailPocket * 0.58f, innerPocket * 0.82f), crownPocket));
    }

    private static float HokusaiArcPaintedBandWeight01(float curlShoulder01)
    {
        float shoulderCrown = smoothstep(0.36f, 0.62f, curlShoulder01)
                            * (1.0f - smoothstep(0.80f, 0.98f, curlShoulder01));
        float innerFoamTooth = smoothstep(0.12f, 0.32f, curlShoulder01)
                             * (1.0f - smoothstep(0.50f, 0.68f, curlShoulder01));
        float hookTip = smoothstep(0.84f, 0.98f, curlShoulder01);
        float tailTaper = smoothstep(0.42f, 1.0f, 1.0f - curlShoulder01);
        float negativeSpace = HokusaiArcNegativeSpaceProfile01(curlShoulder01);
        return Mathf.Max(0.18f,
            0.66f
            + shoulderCrown * 0.46f
            + innerFoamTooth * 0.19f
            + hookTip * 0.04f
            - tailTaper * 0.24f
            - negativeSpace * 0.30f);
    }

    private static float HokusaiArcBell01(float value, float center, float radius)
    {
        return 1.0f - smoothstep(radius * 0.42f, radius, Mathf.Abs(value - center));
    }

    private static float HokusaiArcFoamLeafWeight01(float curlShoulder01)
    {
        float innerLeaf = HokusaiArcBell01(curlShoulder01, 0.18f, 0.105f);
        float shoulderLeaf = HokusaiArcBell01(curlShoulder01, 0.48f, 0.155f);
        float crownLeaf = HokusaiArcBell01(curlShoulder01, 0.73f, 0.105f);
        float hookLeaf = HokusaiArcBell01(curlShoulder01, 0.92f, 0.085f);
        float negativeSpace = HokusaiArcNegativeSpaceProfile01(curlShoulder01);
        float paintedBand = Mathf.Clamp01(HokusaiArcPaintedBandWeight01(curlShoulder01));
        float leaf = Mathf.Max(Mathf.Max(innerLeaf * 0.92f, shoulderLeaf), Mathf.Max(crownLeaf * 0.86f, hookLeaf * 0.34f));
        leaf = Mathf.Clamp01(Mathf.Max(leaf, paintedBand * 0.38f) - negativeSpace * 0.48f);
        return leaf;
    }
}
