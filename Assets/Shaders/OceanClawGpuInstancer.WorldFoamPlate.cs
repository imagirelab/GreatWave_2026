using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Rendering;

public partial class OceanClawGpuInstancer
{
    private const int WorldFoamPlateCrossSections = 10;
    private const int WorldFoamPlateCrossVertices = WorldFoamPlateCrossSections + 1;

    [StructLayout(LayoutKind.Sequential)]
    private struct WorldFoamPlateInstance
    {
        public Vector4 row0;
        public Vector4 row1;
        public Vector4 row2;
        public Vector4 row3;
        public Vector4 parameters;
    }

    private struct WorldFoamPlatePoint
    {
        public Vector3 world;
        public Vector3 viewport;
        public float weight;
    }

    private Mesh _worldCrestFoamPlateMesh;
    private Material _worldCrestFoamPlateMaterial;
    private WorldFoamPlateInstance[] _worldFoamInstanceReadback;
    private WorldFoamPlatePoint[] _worldFoamBins;
    private bool[] _worldFoamBinOccupied;
    private Vector3[] _worldFoamPlateVertices;
    private Vector2[] _worldFoamPlateUvs;
    private Color[] _worldFoamPlateColors;
    private int[] _worldFoamPlateTriangles;
    private int[] _worldFoamPlateActiveTriangles;
    private int[] _worldFoamPlateRowBins;
    private Vector3[] _worldFoamPlateRowViewports;

    private void DrawWorldCrestFoamPlate()
    {
        if (!drawWorldCrestFoamPlate
            || _instancesBuffer == null
            || _counterBuffer == null
            || worldFoamPlateAlpha <= 0.001f)
            return;

        Camera referenceCamera = Camera.main;
        if (referenceCamera == null)
            return;

        Mesh mesh = BuildWorldCrestFoamPlateMesh(referenceCamera);
        if (mesh == null)
            return;

        Material material = GetWorldCrestFoamPlateMaterial();
        if (material == null)
            return;

        material.SetColor("_PlateColor", worldFoamPlateColor);
        material.SetColor("_ShadowColor", worldFoamPlateShadowColor);
        material.SetFloat("_Alpha", worldFoamPlateAlpha);
        material.SetFloat("_ShadowStrength", worldFoamPlateShadowStrength);
        material.SetFloat("_EdgeInk", worldFoamPlateEdgeInk);
        Graphics.DrawMesh(mesh, Matrix4x4.identity, material, gameObject.layer, referenceCamera, 0, null, ShadowCastingMode.Off, false, null, LightProbeUsage.Off);
    }

    private Mesh BuildWorldCrestFoamPlateMesh(Camera referenceCamera)
    {
        uint[] counter = { 0u };
        _counterBuffer.GetData(counter);
        int rawCount = (int)Mathf.Min(counter[0], (uint)Mathf.Max(1, maxInstances));
        if (rawCount < 2)
            return null;

        if (_worldFoamInstanceReadback == null || _worldFoamInstanceReadback.Length < rawCount)
            _worldFoamInstanceReadback = new WorldFoamPlateInstance[Mathf.NextPowerOfTwo(rawCount)];
        _instancesBuffer.GetData(_worldFoamInstanceReadback, 0, 0, rawCount);

        int binCount = Mathf.Clamp(worldFoamPlateBins, 8, 96);
        EnsureWorldFoamBins(binCount);
        for (int i = 0; i < binCount; i++)
            _worldFoamBinOccupied[i] = false;

        for (int i = 0; i < rawCount; i++)
        {
            WorldFoamPlateInstance instance = _worldFoamInstanceReadback[i];
            float score = Mathf.Clamp01(instance.parameters.x);
            float life = Mathf.Clamp01(instance.parameters.y);
            float growth = Mathf.Clamp01(instance.parameters.w);
            if (score < worldFoamPlateMinScore || life < worldFoamPlateMinLife)
                continue;

            Vector3 position = new Vector3(instance.row0.w, instance.row1.w, instance.row2.w);
            Vector3 yAxis = new Vector3(instance.row0.y, instance.row1.y, instance.row2.y);
            float yLength = yAxis.magnitude;
            Vector3 yDir = yLength > 0.001f ? yAxis / yLength : Vector3.up;
            Vector3 crestPoint = position + yDir * Mathf.Min(yLength * 0.38f, 9.0f) + Vector3.up * worldFoamPlateLift;
            Vector3 viewport = referenceCamera.WorldToViewportPoint(crestPoint);
            if (viewport.z <= referenceCamera.nearClipPlane
                || viewport.x < -0.08f
                || viewport.x > 1.08f
                || viewport.y < 0.12f
                || viewport.y > 0.97f)
                continue;

            float plateArcMask = 1.0f;
            if (useScreenReferenceMask && screenReferenceStrength > 0.001f)
            {
                Vector2 visualCenter = screenReferenceCenter + screenRibbonCenterOffset;
                float halfWidth = Mathf.Max(screenReferenceHalfWidth * Mathf.Max(screenRibbonHalfWidthScale, 0.25f), 0.001f);
                float nx = (viewport.x - visualCenter.x) / halfWidth;
                if (Mathf.Abs(nx) > 1.10f)
                    continue;

                float arcY = visualCenter.y
                    + screenReferenceBend * screenRibbonBendScale * (1.0f - Mathf.Clamp01(nx * nx))
                    + screenReferenceTilt * screenRibbonTiltScale * nx;
                float distToArc = Mathf.Abs(viewport.y - arcY);
                float thickness = Mathf.Max(screenReferenceThickness * Mathf.Max(screenRibbonThicknessScale * 2.2f, 0.09f), 0.030f);
                float feather = Mathf.Max(screenReferenceFeather * 0.42f, 0.024f);
                if (distToArc > thickness + feather)
                    continue;

                plateArcMask = 1.0f - smoothstep(thickness, thickness + feather, distToArc);
                if (plateArcMask < 0.08f)
                    continue;
            }

            int bin = Mathf.Clamp(Mathf.FloorToInt(Mathf.Clamp01(viewport.x) * binCount), 0, binCount - 1);
            float weight = Mathf.Clamp01(score * 0.55f + life * 0.30f + growth * 0.15f);
            weight *= Mathf.Lerp(1.0f, plateArcMask, Mathf.Clamp01(screenReferenceStrength));
            float rank = viewport.y + weight * 0.055f;
            if (_worldFoamBinOccupied[bin] && rank <= _worldFoamBins[bin].viewport.y + _worldFoamBins[bin].weight * 0.055f)
                continue;

            _worldFoamBinOccupied[bin] = true;
            _worldFoamBins[bin] = new WorldFoamPlatePoint
            {
                world = crestPoint,
                viewport = viewport,
                weight = weight
            };
        }

        int pointCount = 0;
        for (int i = 0; i < binCount; i++)
        {
            if (_worldFoamBinOccupied[i])
                pointCount++;
        }
        if (pointCount < 2)
            return null;

        EnsureWorldFoamPlateMeshBuffers(pointCount);
        Vector3 cameraForward = referenceCamera.transform.forward.normalized;
        Vector3 fallbackNormal = referenceCamera.transform.up.normalized;
        int row = 0;
        for (int i = 0; i < binCount; i++)
        {
            if (!_worldFoamBinOccupied[i])
                continue;

            WorldFoamPlatePoint prev = FindNeighborWorldFoamPoint(i, -1, binCount);
            WorldFoamPlatePoint current = _worldFoamBins[i];
            WorldFoamPlatePoint next = FindNeighborWorldFoamPoint(i, 1, binCount);
            Vector3 center = current.world;
            if (prev.weight > 0.0f && next.weight > 0.0f)
                center = (prev.world + current.world * 2.0f + next.world) * 0.25f;

            Vector3 tangent = next.weight > 0.0f && prev.weight > 0.0f
                ? next.world - prev.world
                : (next.weight > 0.0f ? next.world - center : center - prev.world);
            if (tangent.sqrMagnitude < 0.0001f)
                tangent = referenceCamera.transform.right;
            tangent.Normalize();

            Vector3 normal = Vector3.Cross(cameraForward, tangent);
            if (normal.sqrMagnitude < 0.0001f)
                normal = fallbackNormal;
            normal.Normalize();

            float t01 = pointCount <= 1 ? 0.5f : row / (float)(pointCount - 1);
            float endFade = Mathf.Clamp01(Mathf.Sin(t01 * Mathf.PI));
            endFade = Mathf.Lerp(0.52f, 1.0f, Mathf.Pow(endFade, 0.42f));
            float hand = 1.0f
                + Mathf.Sin((t01 * 17.0f + randomSeed * 0.011f) * Mathf.PI * 2.0f) * 0.075f
                + Mathf.Sin((t01 * 43.0f + 1.7f) * Mathf.PI * 2.0f) * 0.035f;
            float toothProfile = (
                ScreenRibbonTooth(t01, 0.18f, 0.035f) * 0.44f
                + ScreenRibbonTooth(t01, 0.30f, 0.028f) * 0.70f
                + ScreenRibbonTooth(t01, 0.43f, 0.026f) * 0.58f
                + ScreenRibbonTooth(t01, 0.57f, 0.030f) * 0.64f
                + ScreenRibbonTooth(t01, 0.71f, 0.032f) * 0.46f
                + ScreenRibbonTooth(t01, 0.84f, 0.036f) * 0.28f)
                * endFade
                * Mathf.Lerp(0.52f, 1.0f, current.weight);
            float toothSkew = (
                ScreenRibbonTooth(t01, 0.18f, 0.038f) * -0.38f
                + ScreenRibbonTooth(t01, 0.30f, 0.030f) * -0.20f
                + ScreenRibbonTooth(t01, 0.43f, 0.028f) * 0.08f
                + ScreenRibbonTooth(t01, 0.57f, 0.032f) * 0.24f
                + ScreenRibbonTooth(t01, 0.71f, 0.034f) * 0.34f
                + ScreenRibbonTooth(t01, 0.84f, 0.038f) * 0.42f);
            float halfWidth = worldFoamPlateWidth
                * Mathf.Lerp(0.72f, 1.16f, current.weight)
                * endFade
                * hand;
            float alpha = Mathf.Clamp01(Mathf.Lerp(0.78f, 1.0f, current.weight) * Mathf.Lerp(0.76f, 1.0f, endFade));

            for (int j = 0; j <= WorldFoamPlateCrossSections; j++)
            {
                float u = j / (float)WorldFoamPlateCrossSections;
                float signedWidth = (u - 0.5f) * 2.0f;
                float lane = Mathf.Abs(signedWidth);
                float laneTaper = Mathf.Lerp(1.0f, 0.92f, smoothstep(0.72f, 1.0f, lane));
                float lowerSide = signedWidth > 0.0f ? 1.0f : 0.0f;
                float toothEdge = lowerSide * smoothstep(0.70f, 1.0f, lane) * toothProfile;
                int vertexIndex = row * WorldFoamPlateCrossVertices + j;
                _worldFoamPlateVertices[vertexIndex] = center
                    + normal * signedWidth * halfWidth * laneTaper * (1.0f + toothEdge * 1.16f)
                    + tangent * (halfWidth * toothEdge * toothSkew * 0.46f)
                    - referenceCamera.transform.up * (halfWidth * toothEdge * 0.18f);
                _worldFoamPlateUvs[vertexIndex] = new Vector2(u, t01);
                _worldFoamPlateColors[vertexIndex] = new Color(1.0f, 1.0f, 1.0f, alpha);
            }

            _worldFoamPlateRowBins[row] = i;
            _worldFoamPlateRowViewports[row] = current.viewport;
            row++;
        }

        int triangleCount = BuildWorldFoamPlateTriangles(row);
        if (triangleCount <= 0)
            return null;

        if (_worldCrestFoamPlateMesh == null)
        {
            _worldCrestFoamPlateMesh = new Mesh
            {
                name = "Hokusai World Crest Foam Plate",
                hideFlags = HideFlags.HideAndDontSave
            };
            _worldCrestFoamPlateMesh.MarkDynamic();
        }

        _worldCrestFoamPlateMesh.Clear();
        _worldCrestFoamPlateMesh.vertices = _worldFoamPlateVertices;
        _worldCrestFoamPlateMesh.uv = _worldFoamPlateUvs;
        _worldCrestFoamPlateMesh.colors = _worldFoamPlateColors;
        if (_worldFoamPlateActiveTriangles == null || _worldFoamPlateActiveTriangles.Length != triangleCount)
            _worldFoamPlateActiveTriangles = new int[triangleCount];
        System.Array.Copy(_worldFoamPlateTriangles, _worldFoamPlateActiveTriangles, triangleCount);
        _worldCrestFoamPlateMesh.triangles = _worldFoamPlateActiveTriangles;
        _worldCrestFoamPlateMesh.RecalculateBounds();
        return _worldCrestFoamPlateMesh;
    }

    private WorldFoamPlatePoint FindNeighborWorldFoamPoint(int start, int direction, int binCount)
    {
        for (int i = start + direction; i >= 0 && i < binCount; i += direction)
        {
            if (_worldFoamBinOccupied[i])
                return _worldFoamBins[i];
        }

        return new WorldFoamPlatePoint();
    }

    private void EnsureWorldFoamBins(int binCount)
    {
        if (_worldFoamBins != null && _worldFoamBins.Length == binCount)
            return;

        _worldFoamBins = new WorldFoamPlatePoint[binCount];
        _worldFoamBinOccupied = new bool[binCount];
    }

    private void EnsureWorldFoamPlateMeshBuffers(int pointCount)
    {
        int vertexCount = pointCount * WorldFoamPlateCrossVertices;
        int indexCount = Mathf.Max(0, pointCount - 1) * WorldFoamPlateCrossSections * 6;
        if (_worldFoamPlateVertices == null || _worldFoamPlateVertices.Length != vertexCount)
        {
            _worldFoamPlateVertices = new Vector3[vertexCount];
            _worldFoamPlateUvs = new Vector2[vertexCount];
            _worldFoamPlateColors = new Color[vertexCount];
        }

        if (_worldFoamPlateRowBins == null || _worldFoamPlateRowBins.Length != pointCount)
        {
            _worldFoamPlateRowBins = new int[pointCount];
            _worldFoamPlateRowViewports = new Vector3[pointCount];
        }

        if (_worldFoamPlateTriangles == null || _worldFoamPlateTriangles.Length != indexCount)
            _worldFoamPlateTriangles = new int[indexCount];
    }

    private int BuildWorldFoamPlateTriangles(int pointCount)
    {
        int triangleIndex = 0;
        for (int i = 0; i < pointCount - 1; i++)
        {
            int binDelta = _worldFoamPlateRowBins[i + 1] - _worldFoamPlateRowBins[i];
            Vector3 a = _worldFoamPlateRowViewports[i];
            Vector3 b = _worldFoamPlateRowViewports[i + 1];
            Vector2 viewportDelta = new Vector2(b.x - a.x, b.y - a.y);
            bool nearbyRows = binDelta > 0
                && binDelta <= 3
                && Mathf.Abs(viewportDelta.x) <= 0.16f
                && Mathf.Abs(viewportDelta.y) <= 0.18f
                && viewportDelta.sqrMagnitude <= 0.045f;
            if (!nearbyRows)
                continue;

            for (int j = 0; j < WorldFoamPlateCrossSections; j++)
            {
                int vertexIndex = i * WorldFoamPlateCrossVertices + j;
                int nextRow = vertexIndex + WorldFoamPlateCrossVertices;
                _worldFoamPlateTriangles[triangleIndex] = vertexIndex;
                _worldFoamPlateTriangles[triangleIndex + 1] = nextRow;
                _worldFoamPlateTriangles[triangleIndex + 2] = vertexIndex + 1;
                _worldFoamPlateTriangles[triangleIndex + 3] = vertexIndex + 1;
                _worldFoamPlateTriangles[triangleIndex + 4] = nextRow;
                _worldFoamPlateTriangles[triangleIndex + 5] = nextRow + 1;
                triangleIndex += 6;
            }
        }

        return triangleIndex;
    }

    private Material GetWorldCrestFoamPlateMaterial()
    {
        if (_worldCrestFoamPlateMaterial != null)
            return _worldCrestFoamPlateMaterial;

        Shader shader = Shader.Find("MasterProject/HokusaiWorldFoamPlate");
        if (shader == null)
            return null;

        _worldCrestFoamPlateMaterial = new Material(shader)
        {
            name = "Hokusai World Crest Foam Plate (Runtime)",
            hideFlags = HideFlags.HideAndDontSave
        };
        return _worldCrestFoamPlateMaterial;
    }

    private void ReleaseWorldCrestFoamPlateResources()
    {
        if (_worldCrestFoamPlateMesh != null)
        {
            if (Application.isPlaying)
                Destroy(_worldCrestFoamPlateMesh);
            else
                DestroyImmediate(_worldCrestFoamPlateMesh);
            _worldCrestFoamPlateMesh = null;
        }

        if (_worldCrestFoamPlateMaterial != null)
        {
            if (Application.isPlaying)
                Destroy(_worldCrestFoamPlateMaterial);
            else
                DestroyImmediate(_worldCrestFoamPlateMaterial);
            _worldCrestFoamPlateMaterial = null;
        }

        _worldFoamInstanceReadback = null;
        _worldFoamBins = null;
        _worldFoamBinOccupied = null;
        _worldFoamPlateVertices = null;
        _worldFoamPlateUvs = null;
        _worldFoamPlateColors = null;
        _worldFoamPlateTriangles = null;
        _worldFoamPlateActiveTriangles = null;
        _worldFoamPlateRowBins = null;
        _worldFoamPlateRowViewports = null;
    }
}
