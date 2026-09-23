using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using Unity.Collections;

// ---------------------------------------------------------------------------
// Shared data types
// ---------------------------------------------------------------------------

/// <summary>
/// One candidate location where a Hokusai claw crest could be spawned.
/// All values are filled in by OceanClawDetector each readback cycle.
/// </summary>
public struct ClawCandidate
{
    /// World-space position (Y is set to 0 here; the manager refines it via BuoyancyData)
    public Vector3 worldPos;

    /// Normalised UV within the FFT tile (Repeat-wrapped), used to re-query BuoyancyData
    public Vector2 anchorUV;

    /// GPU scores from ClawMaskTexture
    public float score;        // clawScore  (overall)
    public float heightScore;
    public float slopeScore;
    public float crestScore;

    /// Approximate surface normal derived from finite-difference of the readback buffer
    public Vector3 surfaceNormal;

    /// Approximate forward (wave propagation) direction derived from height gradient
    public Vector3 waveForward;
}

// ---------------------------------------------------------------------------
// OceanClawDetector
// ---------------------------------------------------------------------------

/// <summary>
/// Reads ClawMaskTexture back from the GPU each frame at low resolution,
/// then produces a filtered list of ClawCandidate positions in world space.
///
/// This component is intentionally separate from FFTOcean_Script so the detection
/// logic can be tuned without touching the FFT pipeline.
/// </summary>
public class OceanClawDetector : MonoBehaviour
{
    // ------------------------------------------------------------------
    // Inspector — references
    // ------------------------------------------------------------------
    [Header("References")]
    [Tooltip("The FFT ocean script that owns ClawMaskTexture")]
    public FFTOcean_Script oceanScript;

    // ------------------------------------------------------------------
    // Inspector — detection params
    // ------------------------------------------------------------------
    [Header("Claw Detection")]
    [Tooltip("Master switch. Disable to stop all readback and candidate generation.")]
    public bool enableClawGeneration = true;

    [Tooltip("World-space grid resolution used to scan for candidates each readback cycle. " +
             "E.g. 32 means a 32x32 grid across the ocean mesh.")]
    [Range(8, 64)]
    public int clawScanGridSize = 32;

    [Tooltip("Minimum combined clawScore for a grid cell to be considered a candidate.")]
    [Range(0f, 1f)]
    public float clawScoreThreshold = 0.25f;

    [Tooltip("Minimum world-space distance between two candidate points (prevents clustering).")]
    [Range(1f, 50f)]
    public float clawMinSpacing = 8f;

    [Tooltip("Maximum number of candidates retained after filtering.")]
    [Range(1, 64)]
    public int maxClawInstances = 20;

    // ------------------------------------------------------------------
    // Inspector — debug
    // ------------------------------------------------------------------
    [Header("Debug")]
    public bool showClawCandidates = true;

    [Tooltip("If assigned, the low-res readback texture is blitted here for inspection " +
             "(assign any small RenderTexture in the Inspector or a RawImage).")]
    public RenderTexture clawMaskDebugOutput;

    // ------------------------------------------------------------------
    // Public read-only output for OceanClawManager
    // ------------------------------------------------------------------
    public IReadOnlyList<ClawCandidate> Candidates => _candidates;
    public bool IsReady => _readbackReady;

    // ------------------------------------------------------------------
    // Private state
    // ------------------------------------------------------------------

    // Low-resolution copy of ClawMaskTexture used for CPU readback
    // Size = _readbackSize x _readbackSize, format = ARGBFloat for easy Color readback
    private RenderTexture _clawMaskLowRes;
    private const int _readbackSize = 32;   // 32×32 — tiny footprint, ~16 KB

    // Ping-pong readback buffer — we never block; we use the last completed result
    private Color[] _readbackBuffer;
    private bool    _readbackPending = false;
    private bool    _readbackReady   = false;

    private readonly List<ClawCandidate> _candidates = new List<ClawCandidate>(64);

    // ------------------------------------------------------------------
    // Lifecycle
    // ------------------------------------------------------------------

    void OnEnable()
    {
        _clawMaskLowRes = new RenderTexture(_readbackSize, _readbackSize, 0,
            RenderTextureFormat.ARGBFloat, RenderTextureReadWrite.Linear);
        _clawMaskLowRes.filterMode = FilterMode.Bilinear;
        _clawMaskLowRes.wrapMode   = TextureWrapMode.Repeat;
        _clawMaskLowRes.name       = "ClawMaskLowRes";
        _clawMaskLowRes.Create();

        _readbackBuffer = new Color[_readbackSize * _readbackSize];
    }

    void OnDisable()
    {
        if (_clawMaskLowRes != null)
        {
            _clawMaskLowRes.Release();
            _clawMaskLowRes = null;
        }
    }

    void Update()
    {
        if (!enableClawGeneration) return;
        if (oceanScript == null)   return;

        RenderTexture clawMask = oceanScript.GetClawMaskTexture();
        if (clawMask == null) return;

        // Downsample ClawMaskTexture → _clawMaskLowRes via bilinear blit
        Graphics.Blit(clawMask, _clawMaskLowRes);

        // Optional: mirror to a debug output RT
        if (clawMaskDebugOutput != null)
            Graphics.Blit(_clawMaskLowRes, clawMaskDebugOutput);

        // Request async readback (only one in flight at a time)
        if (!_readbackPending)
        {
            AsyncGPUReadback.Request(_clawMaskLowRes, 0, TextureFormat.RGBAFloat, OnReadbackComplete);
            _readbackPending = true;
        }
    }

    // ------------------------------------------------------------------
    // Readback completion
    // ------------------------------------------------------------------

    private void OnReadbackComplete(AsyncGPUReadbackRequest req)
    {
        _readbackPending = false;

        if (req.hasError)
        {
            Debug.LogWarning("[OceanClawDetector] GPU readback error – skipping frame.");
            return;
        }

        // Copy native array to managed buffer for safe reuse
        NativeArray<Color> native = req.GetData<Color>();
        if (native.Length != _readbackBuffer.Length)
        {
            Debug.LogWarning("[OceanClawDetector] Readback size mismatch.");
            return;
        }
        native.CopyTo(_readbackBuffer);

        // Build candidate list from new data
        FindCandidates(_readbackBuffer);
        _readbackReady = true;
    }

    // ------------------------------------------------------------------
    // Candidate detection
    // ------------------------------------------------------------------

    private void FindCandidates(Color[] buf)
    {
        if (oceanScript == null) return;

        _candidates.Clear();

        float oceanHalf = oceanScript.waterMeshLength * 0.5f;
        Vector3 oceanCenter = oceanScript.transform.position;

        // Scan a world-space grid across the ocean mesh surface
        for (int gz = 0; gz < clawScanGridSize; gz++)
        {
            for (int gx = 0; gx < clawScanGridSize; gx++)
            {
                float t = (float)oceanScript.waterMeshLength;

                float worldX = oceanCenter.x - oceanHalf + (gx + 0.5f) / clawScanGridSize * t;
                float worldZ = oceanCenter.z - oceanHalf + (gz + 0.5f) / clawScanGridSize * t;

                // Map world XZ → repeating UV via Tile0
                float uvX = Mathf.Repeat(worldX * oceanScript.Tile0, 1f);
                float uvZ = Mathf.Repeat(worldZ * oceanScript.Tile0, 1f);

                // Sample from readback buffer
                int px = Mathf.Clamp(Mathf.FloorToInt(uvX * _readbackSize), 0, _readbackSize - 1);
                int py = Mathf.Clamp(Mathf.FloorToInt(uvZ * _readbackSize), 0, _readbackSize - 1);

                Color s = buf[py * _readbackSize + px];
                // s.r = heightScore, s.g = slopeScore, s.b = crestScore, s.a = clawScore
                float clawScore = s.a;

                if (clawScore < clawScoreThreshold) continue;

                // Finite-difference surface normal & wave forward direction
                // from height scores in neighbouring pixels
                int pxR = Mathf.Clamp(px + 1, 0, _readbackSize - 1);
                int pxL = Mathf.Clamp(px - 1, 0, _readbackSize - 1);
                int pyU = Mathf.Clamp(py + 1, 0, _readbackSize - 1);
                int pyD = Mathf.Clamp(py - 1, 0, _readbackSize - 1);

                float dh_dx = buf[py  * _readbackSize + pxR].r - buf[py  * _readbackSize + pxL].r;
                float dh_dz = buf[pyU * _readbackSize + px ].r - buf[pyD * _readbackSize + px ].r;

                Vector3 approxNormal  = new Vector3(-dh_dx, 1f, -dh_dz).normalized;
                Vector3 approxForward = new Vector3( dh_dx, 0f,  dh_dz);
                if (approxForward.sqrMagnitude < 1e-6f)
                    approxForward = Vector3.forward;
                else
                    approxForward.Normalize();

                _candidates.Add(new ClawCandidate
                {
                    worldPos     = new Vector3(worldX, 0f, worldZ),
                    anchorUV     = new Vector2(uvX, uvZ),
                    score        = clawScore,
                    heightScore  = s.r,
                    slopeScore   = s.g,
                    crestScore   = s.b,
                    surfaceNormal = approxNormal,
                    waveForward  = approxForward,
                });
            }
        }

        // Sort highest score first, then enforce minimum spacing
        _candidates.Sort((a, b) => b.score.CompareTo(a.score));
        EnforceSpacing(_candidates, clawMinSpacing, maxClawInstances);
    }

    /// <summary>
    /// Greedy minimum-spacing filter: keep the highest-scoring candidate,
    /// then discard any that are within <minSpacing> of it, repeat.
    /// Modifies the list in-place.
    /// </summary>
    private static void EnforceSpacing(List<ClawCandidate> list, float minSpacing, int maxCount)
    {
        for (int i = list.Count - 1; i >= 0; i--)
        {
            if (i >= maxCount) { list.RemoveAt(i); continue; }

            bool tooClose = false;
            for (int j = 0; j < i; j++)
            {
                float dx = list[i].worldPos.x - list[j].worldPos.x;
                float dz = list[i].worldPos.z - list[j].worldPos.z;
                if (dx * dx + dz * dz < minSpacing * minSpacing)
                {
                    tooClose = true;
                    break;
                }
            }
            if (tooClose) list.RemoveAt(i);
        }
    }

    // ------------------------------------------------------------------
    // Debug Gizmos
    // ------------------------------------------------------------------

#if UNITY_EDITOR
    void OnDrawGizmos()
    {
        if (!showClawCandidates || !_readbackReady) return;

        foreach (var c in _candidates)
        {
            // Score mapped to green hue: low=yellow, high=green
            Gizmos.color = Color.Lerp(Color.yellow, Color.green, c.score);
            Gizmos.DrawWireSphere(c.worldPos + Vector3.up * 0.5f, 0.6f);

            // Surface normal
            UnityEditor.Handles.color = Color.cyan;
            UnityEditor.Handles.DrawLine(c.worldPos, c.worldPos + c.surfaceNormal * 2f);

            // Wave forward
            UnityEditor.Handles.color = Color.magenta;
            UnityEditor.Handles.DrawLine(c.worldPos, c.worldPos + c.waveForward * 1.5f);
        }
    }
#endif
}
