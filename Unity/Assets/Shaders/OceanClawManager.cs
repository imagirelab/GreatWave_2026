using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using Unity.Collections;

/// <summary>
/// Manages the lifecycle of Hokusai-style claw crest mesh instances.
///
/// Responsibilities:
///   - Object pool of claw GameObjects
///   - Matching detector candidates to active instances (with hysteresis)
///   - Per-frame position / rotation / scale updates using BuoyancyData readback
///   - Debug gizmos
///
/// Does NOT touch the FFT pipeline. Reads only from OceanClawDetector and
/// FFTOcean_Script (for BuoyancyData height queries).
/// </summary>
public class OceanClawManager : MonoBehaviour
{
    // ======================================================================
    // Inner types
    // ======================================================================

    private class ActiveClawInstance
    {
        public GameObject go;               // The pooled GameObject
        public Transform  tr;               // Cached transform

        public bool    active;              // Is it live?
        public float   age;                 // Seconds since spawn
        public float   maxLife;             // Will not be killed before this age regardless of score
        public float   currentScore;        // Updated each frame from nearby candidates

        public Vector2 anchorUV;            // UV within the FFT tile — used for height readback
        public Vector2 anchorWorldXZ;       // World XZ anchor (fixed at spawn)

        // Smoothed transform targets (we lerp toward these)
        public Vector3 targetPos;
        public Quaternion targetRot;
        public Vector3 targetScale;

        // Per-instance async readback for height
        public AsyncGPUReadbackRequest heightRequest;
        public bool   heightRequestPending;
        public float  cachedWorldY;         // Last confirmed surface height

        public void Reset()
        {
            active               = false;
            age                  = 0f;
            currentScore         = 0f;
            heightRequestPending = false;
            cachedWorldY         = 0f;
        }
    }

    // ======================================================================
    // Inspector — References
    // ======================================================================
    [Header("References")]
    public FFTOcean_Script    oceanScript;
    public OceanClawDetector  clawDetector;

    // ======================================================================
    // Inspector — Claw Mesh 设置
    // ======================================================================

    /// <summary>
    /// 单条爪形定义。
    /// 直接把模型的 Mesh 和 Material 拖进来即可，无需提前制作 Prefab。
    /// 如果同时设置了 prefabOverride，则优先用 Prefab。
    /// </summary>
    [System.Serializable]
    public class ClawMeshEntry
    {
        [Tooltip("把 Claw_low（或其他变体）的 Mesh 拖到这里")]
        public Mesh     mesh;

        [Tooltip("爪形使用的材质")]
        public Material material;

        [Tooltip("（可选）如果有现成 Prefab 也可以直接拖这里，会覆盖上面的 Mesh/Material 设置")]
        public GameObject prefabOverride;

        [Tooltip("该变体的权重，用于随机选择时的概率分配（越大越容易被选中）")]
        [Range(0f, 10f)]
        public float weight = 1f;
    }

    [Header("爪形模型设置")]
    [Tooltip("在这里添加一或多个爪形变体。\n" +
             "操作方法：\n" +
             "  1. 点击 + 号新增一条\n" +
             "  2. 把 Claw_low 的 Mesh 拖到 Mesh 槽\n" +
             "  3. 拖入对应的 Material\n" +
             "  4. 重复以添加多个变体")]
    public ClawMeshEntry[] clawMeshEntries;

    [Tooltip("True = 按分数高低选变体（越强的浪用后面的变体）\nFalse = 按 weight 随机选")]
    public bool clawVariantByScore = false;

    // ======================================================================
    // Inspector — Spawn / Kill thresholds
    // ======================================================================
    [Header("Claw Detection Thresholds")]
    [Tooltip("A candidate must exceed this score before a claw is spawned. " +
             "Must be > ClawKillThreshold to prevent flicker.")]
    [Range(0f, 1f)]
    public float clawSpawnThreshold = 0.45f;

    [Tooltip("An active claw is killed when its score drops below this AND " +
             "it has lived at least ClawLifetimeMin seconds.")]
    [Range(0f, 1f)]
    public float clawKillThreshold  = 0.20f;

    [Tooltip("Distance from an active instance's anchor to a candidate for it " +
             "to count as 'the same claw'. Should be ~clawMinSpacing * 0.6f.")]
    [Range(0.5f, 30f)]
    public float clawMatchRadius = 5f;

    // ======================================================================
    // Inspector — Lifetime
    // ======================================================================
    [Header("Lifetime")]
    [Tooltip("Minimum seconds a claw stays alive regardless of score.")]
    [Range(0.1f, 10f)]
    public float clawLifetimeMin = 1.5f;

    [Tooltip("If score stays high, the claw lives indefinitely. This is a safety " +
             "cap so orphaned claws eventually die.")]
    [Range(1f, 60f)]
    public float clawLifetimeMax = 20f;

    // ======================================================================
    // Inspector — Scale
    // ======================================================================
    [Header("Scale")]
    [Tooltip("Scale of claw mesh when clawScore = 0 (minimum live score).")]
    public float clawScaleMin = 30f;

    [Tooltip("Scale of claw mesh when clawScore = 1.")]
    public float clawScaleMax = 80f;

    // ======================================================================
    // Inspector — Smoothing
    // ======================================================================
    [Header("Smoothing")]
    [Tooltip("Position follow speed (lerp). Lower = more lag, more stable.")]
    [Range(0.5f, 20f)]
    public float clawFollowStrength = 4f;

    [Tooltip("Rotation follow speed.")]
    [Range(0.5f, 20f)]
    public float clawRotationFollowStrength = 3f;

    [Tooltip("Scale follow speed.")]
    [Range(0.5f, 20f)]
    public float clawScaleFollowStrength = 5f;

    [Tooltip("Random yaw added at spawn to each claw (degrees). Adds variation.")]
    [Range(0f, 180f)]
    public float clawRotationRandomness = 30f;

    [Tooltip("How much the wave-forward direction from the detector influences " +
             "the claw's forward axis. 0 = always use world Z, 1 = full gradient.")]
    [Range(0f, 1f)]
    public float clawForwardBlendWithWave = 0.7f;

    // ======================================================================
    // Inspector — Debug
    // ======================================================================
    [Header("Debug")]
    public bool  showClawCandidates  = false;
    public bool  showActiveClaws     = true;
    public bool  logSpawnKill        = false;
    [Tooltip("调试用：在海面高度基础上再抬高多少米，方便观察。确认效果后改回 0")]
    public float clawDebugHeightOffset = 3f;

    // ======================================================================
    // Private — pool
    // ======================================================================
    private List<ActiveClawInstance> _pool   = new List<ActiveClawInstance>();
    private List<ActiveClawInstance> _active = new List<ActiveClawInstance>();

    // ======================================================================
    // Lifecycle
    // ======================================================================

    void Start()
    {
        if (clawMeshEntries == null || clawMeshEntries.Length == 0)
        {
            Debug.LogWarning("[OceanClawManager] clawMeshEntries 为空，请在 Inspector 里添加 Claw_low 的 Mesh。");
            return;
        }

        // Pre-populate pool
        int poolSize = clawDetector != null ? clawDetector.maxClawInstances : 20;
        for (int i = 0; i < poolSize; i++)
            _pool.Add(CreatePooledInstance());
    }

    void OnDisable()
    {
        // Return all active instances to pool cleanly
        for (int i = _active.Count - 1; i >= 0; i--)
            ReturnToPool(_active[i]);
    }

    void Update()
    {
        if (!clawDetector || !clawDetector.enableClawGeneration) return;
        if (!clawDetector.IsReady) return;

        IReadOnlyList<ClawCandidate> candidates = clawDetector.Candidates;

        UpdateActiveInstances(candidates);
        SpawnFromCandidates(candidates);
    }

    // ======================================================================
    // Update active instances
    // ======================================================================

    private void UpdateActiveInstances(IReadOnlyList<ClawCandidate> candidates)
    {
        for (int i = _active.Count - 1; i >= 0; i--)
        {
            ActiveClawInstance inst = _active[i];
            inst.age += Time.deltaTime;

            // Find best-matching candidate within match radius
            float bestScore = 0f;
            ClawCandidate bestMatch = default;
            float bestDist = float.MaxValue;

            foreach (var c in candidates)
            {
                float dx = c.worldPos.x - inst.anchorWorldXZ.x;
                float dz = c.worldPos.z - inst.anchorWorldXZ.y;
                float d  = dx * dx + dz * dz;
                if (d < clawMatchRadius * clawMatchRadius && d < bestDist)
                {
                    bestDist  = d;
                    bestScore = c.score;
                    bestMatch = c;
                }
            }

            inst.currentScore = bestScore;

            // Kill check (hysteresis: score must drop AND minimum life exceeded)
            bool scoreDead   = inst.currentScore < clawKillThreshold;
            bool oldEnough   = inst.age >= clawLifetimeMin;
            bool tooOld      = inst.age >= clawLifetimeMax;

            if (tooOld || (scoreDead && oldEnough))
            {
                if (logSpawnKill)
                    Debug.Log($"[OceanClawManager] Kill claw at {inst.anchorWorldXZ}, age={inst.age:F1}s");
                ReturnToPool(inst);
                _active.RemoveAt(i);
                continue;
            }

            // Height readback — keep querying BuoyancyData at anchor UV
            UpdateHeightReadback(inst);

            // Compute target transform
            Vector3 worldPos = new Vector3(inst.anchorWorldXZ.x, inst.cachedWorldY + clawDebugHeightOffset, inst.anchorWorldXZ.y);

            // Normal & forward from best candidate (if any), else fall back to world up
            Vector3 normal  = bestDist < float.MaxValue ? bestMatch.surfaceNormal : Vector3.up;
            Vector3 forward = bestDist < float.MaxValue ? bestMatch.waveForward   : Vector3.forward;

            // Blend forward with world-Z by clawForwardBlendWithWave
            Vector3 blendedForward = Vector3.Lerp(Vector3.forward, forward, clawForwardBlendWithWave);
            blendedForward = Vector3.ProjectOnPlane(blendedForward, normal).normalized;
            if (blendedForward.sqrMagnitude < 1e-6f) blendedForward = Vector3.forward;

            Quaternion targetRot = Quaternion.LookRotation(blendedForward, normal);

            float scaleFactor = Mathf.Lerp(clawScaleMin, clawScaleMax,
                Mathf.InverseLerp(clawKillThreshold, 1f, inst.currentScore));
            Vector3 targetScale = Vector3.one * scaleFactor;

            inst.targetPos   = worldPos;
            inst.targetRot   = targetRot;
            inst.targetScale = targetScale;

            // Smooth toward targets
            float dt = Time.deltaTime;
            inst.tr.position   = Vector3.Lerp(inst.tr.position, inst.targetPos,
                                              dt * clawFollowStrength);
            inst.tr.rotation   = Quaternion.Slerp(inst.tr.rotation, inst.targetRot,
                                                  dt * clawRotationFollowStrength);
            inst.tr.localScale = Vector3.Lerp(inst.tr.localScale, inst.targetScale,
                                              dt * clawScaleFollowStrength);
        }
    }

    // ======================================================================
    // Spawn new claws from candidates not yet covered by active instances
    // ======================================================================

    private void SpawnFromCandidates(IReadOnlyList<ClawCandidate> candidates)
    {
        foreach (var c in candidates)
        {
            if (c.score < clawSpawnThreshold) continue;
            if (_pool.Count == 0) break;  // pool exhausted

            // Is this candidate already covered by an active instance?
            bool covered = false;
            foreach (var inst in _active)
            {
                float dx = c.worldPos.x - inst.anchorWorldXZ.x;
                float dz = c.worldPos.z - inst.anchorWorldXZ.y;
                if (dx * dx + dz * dz < clawMatchRadius * clawMatchRadius)
                {
                    covered = true;
                    break;
                }
            }
            if (covered) continue;

            SpawnClaw(c);
        }
    }

    // ======================================================================
    // Spawn helpers
    // ======================================================================

    private void SpawnClaw(ClawCandidate c)
    {
        if (_pool.Count == 0) return;
        if (clawMeshEntries == null || clawMeshEntries.Length == 0)
        {
            Debug.LogWarning("[OceanClawManager] clawMeshEntries 为空，请在 Inspector 里添加 Claw_low 的 Mesh。");
            return;
        }

        ActiveClawInstance inst = _pool[_pool.Count - 1];
        _pool.RemoveAt(_pool.Count - 1);

        inst.Reset();
        inst.active        = true;
        inst.anchorUV      = c.anchorUV;
        inst.anchorWorldXZ = new Vector2(c.worldPos.x, c.worldPos.z);
        inst.currentScore  = c.score;
        inst.maxLife       = clawLifetimeMax;
        inst.cachedWorldY  = c.worldPos.y;

        // 选择变体
        int variantIndex = PickVariantIndex(c.score);
        ApplyVariant(inst, variantIndex);

        // 初始变换
        float      yawOffset = Random.Range(-clawRotationRandomness, clawRotationRandomness);
        Quaternion spawnRot  = Quaternion.LookRotation(c.waveForward, c.surfaceNormal)
                             * Quaternion.Euler(0f, yawOffset, 0f);
        float      spawnScale = Mathf.Lerp(clawScaleMin, clawScaleMax, c.score);

        inst.tr.position   = new Vector3(c.worldPos.x, inst.cachedWorldY, c.worldPos.z);
        inst.tr.rotation   = spawnRot;
        inst.tr.localScale = Vector3.one * spawnScale;
        inst.go.SetActive(true);

        _active.Add(inst);

        if (logSpawnKill)
            Debug.Log($"[OceanClawManager] 生成爪形 at {c.worldPos}, score={c.score:F2}, variant={variantIndex}");
    }

    // ------------------------------------------------------------------
    // 变体选择
    // ------------------------------------------------------------------

    /// <summary>
    /// 按分数或按 weight 随机选一个变体索引。
    /// </summary>
    private int PickVariantIndex(float score)
    {
        if (clawMeshEntries == null || clawMeshEntries.Length == 0) return 0;
        if (clawMeshEntries.Length == 1) return 0;

        if (clawVariantByScore)
        {
            // score=0 → 索引0，score=1 → 最后一个
            return Mathf.Clamp(
                Mathf.FloorToInt(score * clawMeshEntries.Length),
                0, clawMeshEntries.Length - 1);
        }

        // 按 weight 随机
        float totalWeight = 0f;
        foreach (var e in clawMeshEntries) totalWeight += Mathf.Max(e.weight, 0f);
        if (totalWeight <= 0f) return Random.Range(0, clawMeshEntries.Length);

        float r = Random.value * totalWeight;
        for (int i = 0; i < clawMeshEntries.Length; i++)
        {
            r -= Mathf.Max(clawMeshEntries[i].weight, 0f);
            if (r <= 0f) return i;
        }
        return clawMeshEntries.Length - 1;
    }

    /// <summary>
    /// 把选定变体的 Mesh / Material 应用到实例上。
    /// 支持两种方式：Prefab Override 或直接 Mesh + Material。
    /// </summary>
    private void ApplyVariant(ActiveClawInstance inst, int variantIndex)
    {
        ClawMeshEntry entry = clawMeshEntries[variantIndex];

        if (entry.prefabOverride != null)
        {
            // Prefab 模式：替换子对象，先清理旧子对象
            foreach (Transform oldChild in inst.tr)
                Destroy(oldChild.gameObject);

            GameObject newChild = Instantiate(entry.prefabOverride, inst.tr);
            newChild.transform.localPosition = Vector3.zero;
            newChild.transform.localRotation = Quaternion.identity;
            newChild.transform.localScale    = Vector3.one;
            return;
        }

        // Mesh + Material 模式：直接更新 MeshFilter / MeshRenderer
        MeshFilter   mf = inst.go.GetComponent<MeshFilter>();
        MeshRenderer mr = inst.go.GetComponent<MeshRenderer>();

        if (mf == null) mf = inst.go.AddComponent<MeshFilter>();
        if (mr == null) mr = inst.go.AddComponent<MeshRenderer>();

        if (entry.mesh != null)
        {
            mf.sharedMesh = entry.mesh;
        }
        else
        {
            Debug.LogWarning("[OceanClawManager] Mesh 为空！请在 Claw Mesh Entries 里展开 FBX，" +
                             "把三角形图标的子资产（Mesh）拖到 Mesh 槽，而不是 FBX 文件本身。");
        }

        if (entry.material != null) mr.sharedMaterial = entry.material;
        else Debug.LogWarning("[OceanClawManager] Material 为空，请填入材质。");
    }

    private void ReturnToPool(ActiveClawInstance inst)
    {
        inst.active = false;
        if (inst.go != null) inst.go.SetActive(false);
        _pool.Add(inst);
    }

    private ActiveClawInstance CreatePooledInstance()
    {
        // 创建一个基础 GameObject，ApplyVariant 会在 Spawn 时动态挂载 Mesh
        GameObject go = new GameObject("ClawInstance_pooled");
        go.transform.SetParent(transform, false);
        go.SetActive(false);

        return new ActiveClawInstance
        {
            go     = go,
            tr     = go.transform,
            active = false,
        };
    }

    // ======================================================================
    // Per-instance height readback (async, non-blocking)
    // ======================================================================

    private void UpdateHeightReadback(ActiveClawInstance inst)
    {
        if (oceanScript == null) return;
        RenderTexture buoyancyRT = oceanScript.GetBuoyancyData();
        if (buoyancyRT == null) return;

        if (inst.heightRequestPending)
        {
            if (inst.heightRequest.done)
            {
                inst.heightRequestPending = false;

                if (!inst.heightRequest.hasError)
                {
                    NativeArray<ushort> data = inst.heightRequest.GetData<ushort>();
                    if (data.Length > 0)
                        inst.cachedWorldY = Mathf.HalfToFloat(data[0])
                                          + oceanScript.transform.position.y;
                }
                // Immediately queue the next request
                QueueHeightRequest(inst, buoyancyRT);
            }
        }
        else
        {
            QueueHeightRequest(inst, buoyancyRT);
        }
    }

    private void QueueHeightRequest(ActiveClawInstance inst, RenderTexture rt)
    {
        // Map anchorUV → pixel coordinate in BuoyancyData (1024×1024)
        int px = Mathf.Clamp(Mathf.FloorToInt(inst.anchorUV.x * 1023f), 0, 1023);
        int py = Mathf.Clamp(Mathf.FloorToInt(inst.anchorUV.y * 1023f), 0, 1023);

        inst.heightRequest        = AsyncGPUReadback.Request(rt, 0, px, 1, py, 1, 0, 1, null);
        inst.heightRequestPending = true;
    }

    // ======================================================================
    // Debug Gizmos
    // ======================================================================

#if UNITY_EDITOR
    void OnDrawGizmos()
    {
        if (showActiveClaws)
        {
            foreach (var inst in _active)
            {
                if (!inst.active) continue;

                // Blue sphere at claw position, size scaled by score
                Gizmos.color = Color.blue;
                Gizmos.DrawWireSphere(inst.tr.position + Vector3.up, 0.5f + inst.currentScore);

                // Draw anchor XZ
                Vector3 anchor = new Vector3(inst.anchorWorldXZ.x, inst.cachedWorldY, inst.anchorWorldXZ.y);
                Gizmos.color = new Color(0.3f, 0.6f, 1f, 0.5f);
                Gizmos.DrawLine(anchor, anchor + Vector3.up * 3f);

                // Age bar (green→red over lifetime)
                float ageRatio = Mathf.Clamp01(inst.age / inst.maxLife);
                Gizmos.color = Color.Lerp(Color.green, Color.red, ageRatio);
                Gizmos.DrawLine(anchor, anchor + inst.tr.forward * (1f + inst.currentScore));
            }
        }
    }

    void OnGUI()
    {
        if (!Application.isPlaying) return;

        int y = 10;
        GUI.Label(new Rect(10, y, 300, 20),
            $"[ClawManager] Active: {_active.Count}  Pool: {_pool.Count}");
        y += 20;

        if (clawDetector != null)
            GUI.Label(new Rect(10, y, 300, 20),
                $"[ClawDetector] Candidates: {clawDetector.Candidates.Count}  Ready: {clawDetector.IsReady}");
    }
#endif
}
