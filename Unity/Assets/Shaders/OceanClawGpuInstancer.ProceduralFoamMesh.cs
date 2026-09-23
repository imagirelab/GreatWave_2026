using UnityEngine;

public partial class OceanClawGpuInstancer
{
    private Mesh _foamFingerMesh;
    private Mesh _foamFingerSourceMesh;
    private float _foamFingerWidthScaleCache = float.NaN;
    private float _foamFingerCurlCache = float.NaN;
    private float _foamFingerHookStrengthCache = float.NaN;
    private float _foamFingerScallopStrengthCache = float.NaN;
    private bool _foamFingerLocalYPointsTowardTipCache;
    private Mesh _foamUnderlayMesh;
    private Mesh _foamUnderlaySourceMesh;
    private bool _foamUnderlayLocalYPointsTowardTipCache;

    /// <summary>
    /// Returns the local-space mesh point that should remain attached to the water surface.
    /// 返回模型本地空间中需要贴住水面的锚点。
    /// </summary>
    private Vector4 GetMeshAnchorLocal()
    {
        if (clawMesh == null)
            return Vector4.zero;

        Mesh mesh = GetMainClawMesh();
        if (mesh == null)
            return Vector4.zero;

        Bounds bounds = mesh.bounds;
        float rootY = localYPointsTowardTip ? bounds.min.y : bounds.max.y;
        float rootZ = drawProceduralFoamFingers ? bounds.min.z : bounds.center.z;
        Vector3 anchor = new Vector3(bounds.center.x, rootY, rootZ);
        return new Vector4(anchor.x, anchor.y, anchor.z, 0f);
    }

    /// <summary>
    /// Returns the mesh used by the visible foam-finger pass.
    /// </summary>
    private Mesh GetMainClawMesh()
    {
        if (!drawProceduralFoamFingers)
            return clawMesh;

        EnsureFoamFingerMesh();
        return _foamFingerMesh != null ? _foamFingerMesh : clawMesh;
    }

    /// <summary>
    /// Returns the mesh used by the soft underlay pass.
    /// </summary>
    private Mesh GetUnderlayClawMesh()
    {
        EnsureFoamUnderlayMesh();
        return _foamUnderlayMesh != null ? _foamUnderlayMesh : clawMesh;
    }

    /// <summary>
    /// Builds a flat curved foam-finger mesh so the visible tips read as woodblock foam
    /// instead of the faceted source claw model.
    /// </summary>
    private void EnsureFoamFingerMesh()
    {
        if (!drawProceduralFoamFingers || clawMesh == null)
        {
            ReleaseFoamFingerMesh();
            return;
        }

        if (_foamFingerMesh != null
            && _foamFingerSourceMesh == clawMesh
            && Mathf.Approximately(_foamFingerWidthScaleCache, foamFingerWidthScale)
            && Mathf.Approximately(_foamFingerCurlCache, foamFingerCurl)
            && Mathf.Approximately(_foamFingerHookStrengthCache, foamFingerHookStrength)
            && Mathf.Approximately(_foamFingerScallopStrengthCache, foamFingerScallopStrength)
            && _foamFingerLocalYPointsTowardTipCache == localYPointsTowardTip)
            return;

        ReleaseFoamFingerMesh();
        _foamFingerSourceMesh = clawMesh;
        _foamFingerWidthScaleCache = foamFingerWidthScale;
        _foamFingerCurlCache = foamFingerCurl;
        _foamFingerHookStrengthCache = foamFingerHookStrength;
        _foamFingerScallopStrengthCache = foamFingerScallopStrength;
        _foamFingerLocalYPointsTowardTipCache = localYPointsTowardTip;

        Bounds bounds = clawMesh.bounds;
        float rootY = localYPointsTowardTip ? bounds.min.y : bounds.max.y;
        float tipY = localYPointsTowardTip ? bounds.max.y : bounds.min.y;
        float length = Mathf.Max(Mathf.Abs(tipY - rootY), 0.001f);
        float visualTipY = Mathf.Lerp(rootY, tipY, 0.48f);
        float baseHalfWidth = length * 0.460f * foamFingerWidthScale;
        float visibleLength = length * 0.135f;

        const int segments = 28;
        const int ringVertices = 7;
        Vector3[] vertices = new Vector3[(segments + 1) * ringVertices];
        Vector3[] normals = new Vector3[vertices.Length];
        Vector2[] uv = new Vector2[vertices.Length];
        int[] triangles = new int[segments * (ringVertices - 1) * 4 * 3];

        for (int i = 0; i <= segments; i++)
        {
            float t = i / (float)segments;
            float y = Mathf.Lerp(rootY, visualTipY, t);
            float z = Mathf.Lerp(0.0f, visibleLength, t);
            float body = Mathf.Pow(Mathf.Max(0.0f, Mathf.Sin(t * Mathf.PI)), 0.42f);
            float baseToTipTaper = Mathf.Pow(Mathf.Max(0.0f, 1.0f - t), 0.58f);
            float tipTaper = Mathf.Lerp(1.0f, 0.180f, smoothstep(0.58f, 1.0f, t));
            float rootTaper = Mathf.Lerp(0.42f, 1.0f, smoothstep(0.0f, 0.14f, t));
            float widthFloor = Mathf.Lerp(0.150f, 0.035f, smoothstep(0.66f, 1.0f, t));
            float halfWidth = baseHalfWidth * (widthFloor + (baseToTipTaper * 0.38f + body * 0.46f) * tipTaper * rootTaper);
            float curlOpen = smoothstep(0.08f, 1.0f, t);
            float curl = (Mathf.Sin((t - 0.08f) * Mathf.PI) * 0.72f + (t - 0.5f) * 0.32f) * baseHalfWidth * foamFingerCurl * curlOpen;
            float hookT = smoothstep(0.50f, 1.0f, t);
            float tipHook = hookT * hookT * foamFingerHookStrength;
            float curlSign = foamFingerCurl >= 0.5f ? 1.0f : -1.0f;
            curl += curlSign * tipHook * baseHalfWidth * 0.84f;
            z -= tipHook * visibleLength * 0.18f;
            float asymmetry = Mathf.Sin(t * Mathf.PI * 2.1f + 0.7f) * 0.060f + tipHook * 0.28f * curlSign;
            float scallopMask = (1.0f - smoothstep(0.88f, 1.0f, t)) * smoothstep(0.10f, 0.82f, t);
            float scallop = Mathf.Sin(t * Mathf.PI * 6.0f + 0.35f) * 0.13f * halfWidth * foamFingerScallopStrength * scallopMask;
            float ridge = (0.003f + foamFingerHookStrength * 0.0015f) * length * body;
            float innerPinch = smoothstep(0.50f, 1.0f, t) * foamFingerHookStrength * 0.46f;
            float outerBulge = smoothstep(0.12f, 0.66f, t) * (1.0f - smoothstep(0.86f, 1.0f, t)) * foamFingerHookStrength * 0.30f;

            int vertexIndex = i * ringVertices;
            float leftOuter = halfWidth * (1.0f + asymmetry + outerBulge);
            float leftMid = halfWidth * (0.68f + outerBulge * 0.24f);
            float leftInner = halfWidth * (0.34f + outerBulge * 0.18f);
            float rightInner = halfWidth * Mathf.Max(0.12f, 0.32f - innerPinch * 0.42f);
            float rightMid = halfWidth * Mathf.Max(0.22f, 0.62f - innerPinch * 0.58f);
            float rightOuter = halfWidth * Mathf.Max(0.16f, 1.0f - asymmetry * 0.70f - innerPinch);
            vertices[vertexIndex] = new Vector3(curl - leftOuter, y, z - ridge * 0.38f + scallop * 0.10f);
            vertices[vertexIndex + 1] = new Vector3(curl - leftMid + scallop * 0.42f, y, z + ridge * 0.05f);
            vertices[vertexIndex + 2] = new Vector3(curl - leftInner + scallop * 0.58f, y, z + ridge * 0.22f);
            vertices[vertexIndex + 3] = new Vector3(curl + scallop * 0.24f + tipHook * baseHalfWidth * 0.10f * curlSign, y, z + ridge * (0.38f + tipHook * 0.20f));
            vertices[vertexIndex + 4] = new Vector3(curl + rightInner + scallop * 0.22f, y, z + ridge * 0.18f);
            vertices[vertexIndex + 5] = new Vector3(curl + rightMid - scallop * 0.12f, y, z - ridge * 0.02f);
            vertices[vertexIndex + 6] = new Vector3(curl + rightOuter, y, z - ridge * 0.34f - scallop * 0.10f);
            normals[vertexIndex] = Vector3.forward;
            normals[vertexIndex + 1] = Vector3.forward;
            normals[vertexIndex + 2] = Vector3.forward;
            normals[vertexIndex + 3] = Vector3.forward;
            normals[vertexIndex + 4] = Vector3.forward;
            normals[vertexIndex + 5] = Vector3.forward;
            normals[vertexIndex + 6] = Vector3.forward;
            uv[vertexIndex] = new Vector2(0.0f, t);
            uv[vertexIndex + 1] = new Vector2(0.16f, t);
            uv[vertexIndex + 2] = new Vector2(0.32f, t);
            uv[vertexIndex + 3] = new Vector2(0.5f, t);
            uv[vertexIndex + 4] = new Vector2(0.68f, t);
            uv[vertexIndex + 5] = new Vector2(0.84f, t);
            uv[vertexIndex + 6] = new Vector2(1.0f, t);
        }

        int triangleIndex = 0;
        for (int i = 0; i < segments; i++)
        {
            int current = i * ringVertices;
            int next = (i + 1) * ringVertices;
            for (int j = 0; j < ringVertices - 1; j++)
            {
                int a0 = current + j;
                int b0 = current + j + 1;
                int a1 = next + j;
                int b1 = next + j + 1;
                AddTriangle(triangles, ref triangleIndex, a0, a1, b0);
                AddTriangle(triangles, ref triangleIndex, b0, a1, b1);
                AddTriangle(triangles, ref triangleIndex, b0, a1, a0);
                AddTriangle(triangles, ref triangleIndex, b1, a1, b0);
            }
        }

        _foamFingerMesh = new Mesh
        {
            name = "Hokusai Procedural Foam Finger",
            hideFlags = HideFlags.HideAndDontSave
        };
        _foamFingerMesh.SetVertices(vertices);
        _foamFingerMesh.SetNormals(normals);
        _foamFingerMesh.SetUVs(0, uv);
        _foamFingerMesh.SetTriangles(triangles, 0);
        _foamFingerMesh.RecalculateBounds();
    }

    private static void AddTriangle(int[] triangles, ref int index, int a, int b, int c)
    {
        triangles[index++] = a;
        triangles[index++] = b;
        triangles[index++] = c;
    }

    private void ReleaseFoamFingerMesh()
    {
        if (_foamFingerMesh == null)
            return;

        if (Application.isPlaying)
            Destroy(_foamFingerMesh);
        else
            DestroyImmediate(_foamFingerMesh);

        _foamFingerMesh = null;
        _foamFingerSourceMesh = null;
        _foamFingerWidthScaleCache = float.NaN;
        _foamFingerCurlCache = float.NaN;
        _foamFingerHookStrengthCache = float.NaN;
        _foamFingerScallopStrengthCache = float.NaN;
        _foamFingerLocalYPointsTowardTipCache = false;
    }

    /// <summary>
    /// Builds a smooth local X/Y foam shape for the underlay pass so the backing reads as a continuous ribbon instead of another copy of the claw mesh.
    /// </summary>
    private void EnsureFoamUnderlayMesh()
    {
        if (clawMesh == null)
            return;

        if (_foamUnderlayMesh != null
            && _foamUnderlaySourceMesh == clawMesh
            && _foamUnderlayLocalYPointsTowardTipCache == localYPointsTowardTip)
            return;

        ReleaseFoamUnderlayMesh();
        _foamUnderlaySourceMesh = clawMesh;
        _foamUnderlayLocalYPointsTowardTipCache = localYPointsTowardTip;

        Bounds bounds = clawMesh.bounds;
        float rootY = localYPointsTowardTip ? bounds.min.y : bounds.max.y;
        float tipY = localYPointsTowardTip ? bounds.max.y : bounds.min.y;
        float length = Mathf.Max(Mathf.Abs(tipY - rootY), 0.001f);
        float underlayTipY = Mathf.Lerp(rootY, tipY, 0.36f);
        float baseHalfWidth = Mathf.Max(bounds.extents.x, bounds.extents.z, length * 0.28f);

        const int segments = 18;
        Vector3[] vertices = new Vector3[(segments + 1) * 2];
        Vector3[] normals = new Vector3[vertices.Length];
        Vector2[] uv = new Vector2[vertices.Length];
        int[] triangles = new int[segments * 6];

        for (int i = 0; i <= segments; i++)
        {
            float t = i / (float)segments;
            float y = Mathf.Lerp(rootY, underlayTipY, t);
            float taper = Mathf.Pow(Mathf.Max(0.0001f, Mathf.Sin(t * Mathf.PI)), 0.48f);
            float tipBias = Mathf.Lerp(0.72f, 1.22f, t);
            float halfWidth = baseHalfWidth * (0.12f + taper * tipBias);
            int vertexIndex = i * 2;
            vertices[vertexIndex] = new Vector3(-halfWidth, y, 0.0f);
            vertices[vertexIndex + 1] = new Vector3(halfWidth, y, 0.0f);
            normals[vertexIndex] = Vector3.forward;
            normals[vertexIndex + 1] = Vector3.forward;
            uv[vertexIndex] = new Vector2(0.0f, t);
            uv[vertexIndex + 1] = new Vector2(1.0f, t);
        }

        for (int i = 0; i < segments; i++)
        {
            int vertexIndex = i * 2;
            int triangleIndex = i * 6;
            triangles[triangleIndex] = vertexIndex;
            triangles[triangleIndex + 1] = vertexIndex + 2;
            triangles[triangleIndex + 2] = vertexIndex + 1;
            triangles[triangleIndex + 3] = vertexIndex + 1;
            triangles[triangleIndex + 4] = vertexIndex + 2;
            triangles[triangleIndex + 5] = vertexIndex + 3;
        }

        _foamUnderlayMesh = new Mesh
        {
            name = "Hokusai Foam Ribbon Underlay",
            hideFlags = HideFlags.HideAndDontSave
        };
        _foamUnderlayMesh.SetVertices(vertices);
        _foamUnderlayMesh.SetNormals(normals);
        _foamUnderlayMesh.SetUVs(0, uv);
        _foamUnderlayMesh.SetTriangles(triangles, 0);
        _foamUnderlayMesh.RecalculateBounds();
    }

    /// <summary>
    /// Destroys the generated underlay mesh if the source claw mesh changes or the component is disabled.
    /// </summary>
    private void ReleaseFoamUnderlayMesh()
    {
        if (_foamUnderlayMesh == null)
            return;

        if (Application.isPlaying)
            Destroy(_foamUnderlayMesh);
        else
            DestroyImmediate(_foamUnderlayMesh);

        _foamUnderlayMesh = null;
        _foamUnderlaySourceMesh = null;
        _foamUnderlayLocalYPointsTowardTipCache = false;
    }
}
