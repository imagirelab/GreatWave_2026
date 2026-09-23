using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using Unity.Collections;

/// <summary>
/// 北斎風の爪形の波頭メッシュについて、生成から回収までを管理する。
///
/// 担当する処理:
///   - 爪形 GameObject のプール
///   - 検出候補と稼働中の実体の対応付け（ヒステリシスあり）
///   - BuoyancyData の読戻しに基づく毎フレームの位置・回転・大きさの更新
///   - デバッグ用ギズモ
///
/// FFT の処理工程には手を加えない。OceanClawDetector と、高さの問い合わせ用の
/// FFTOcean_Script からのみデータを読む。
/// </summary>
public class OceanClawManager : MonoBehaviour
{
    // ======================================================================
    // 内部の型
    // ======================================================================

    private class ActiveClawInstance
    {
        public GameObject go;               // プール内の GameObject。
        public Transform  tr;               // 保持している Transform。

        public bool    active;              // 稼働中かどうか。
        public float   age;                 // 生成からの経過秒数。
        public float   maxLife;             // ギズモの寿命表示に使う上限時間（秒）。
        public float   currentScore;        // 近くの候補から毎フレーム更新する。

        public Vector2 anchorUV;            // FFT タイル内の UV。高さの読戻しに使う。
        public Vector2 anchorWorldXZ;       // ワールド XZ の基準点。生成時に固定する。

        // 補間して近づける変換の目標値。
        public Vector3 targetPos;
        public Quaternion targetRot;
        public Vector3 targetScale;

        // 実体ごとの高さの非同期読戻し。
        public AsyncGPUReadbackRequest heightRequest;
        public bool   heightRequestPending;
        public float  cachedWorldY;         // 最後に確認できた水面の高さ。

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
    // インスペクター — 参照
    // ======================================================================
    [Header("参照")]
    public FFTOcean_Script    oceanScript;
    public OceanClawDetector  clawDetector;

    // ======================================================================
    // インスペクター — 爪形メッシュの設定
    // ======================================================================

    /// <summary>
    /// 一つの爪形の定義。モデルの Mesh と Material を直接指定でき、Prefab の事前作成は不要。
    /// prefabOverride も指定した場合は Prefab を優先する。
    /// </summary>
    [System.Serializable]
    public class ClawMeshEntry
    {
        [Tooltip("Claw_low または別の変種の Mesh をここに指定します")]
        public Mesh     mesh;

        [Tooltip("爪形に使う材質を指定します")]
        public Material material;

        [Tooltip("任意。既存の Prefab を指定すると、上の Mesh と Material の設定より優先されます")]
        public GameObject prefabOverride;

        [Tooltip("変種をランダムに選ぶ際の重みです。値が大きいほど選ばれやすくなります")]
        [Range(0f, 10f)]
        public float weight = 1f;
    }

    [Header("爪形モデルの設定")]
    [Tooltip("爪形の変種を一つ以上追加します。\n" +
             "設定手順:\n" +
             "  1. + ボタンで項目を追加\n" +
             "  2. Claw_low の Mesh を Mesh 欄へ指定\n" +
             "  3. 対応する Material を指定\n" +
             "  4. 必要に応じて変種を追加")]
    public ClawMeshEntry[] clawMeshEntries;

    [Tooltip("オン: スコアに応じて変種を選び、強い波には後の変種を使います。\nオフ: weight に応じてランダムに選びます")]
    public bool clawVariantByScore = false;

    // ======================================================================
    // インスペクター — 生成と回収のしきい値
    // ======================================================================
    [Header("爪形の検出しきい値")]
    [Tooltip("候補のスコアがこの値以上になると爪形を生成します。" +
             "表示のちらつきを防ぐため、clawKillThreshold より高く設定します")]
    [Range(0f, 1f)]
    public float clawSpawnThreshold = 0.45f;

    [Tooltip("稼働中の爪形は、スコアがこの値を下回り、かつ " +
             "clawLifetimeMin 秒以上経過すると回収します")]
    [Range(0f, 1f)]
    public float clawKillThreshold  = 0.20f;

    [Tooltip("候補を既存の爪形と同一とみなす、基準点からの最大距離です。" +
             "目安は clawMinSpacing の約 0.6 倍です")]
    [Range(0.5f, 30f)]
    public float clawMatchRadius = 5f;

    // ======================================================================
    // インスペクター — 寿命
    // ======================================================================
    [Header("寿命")]
    [Tooltip("スコアにかかわらず爪形を保持する最小時間（秒）です")]
    [Range(0.1f, 10f)]
    public float clawLifetimeMin = 1.5f;

    [Tooltip("スコアが高くても、この時間を超えると爪形を回収します。" +
             "対応する候補を失った爪形を残さないための上限です")]
    [Range(1f, 60f)]
    public float clawLifetimeMax = 20f;

    // ======================================================================
    // インスペクター — 大きさ
    // ======================================================================
    [Header("大きさ")]
    [Tooltip("低いスコアの爪形メッシュに使う最小の大きさです")]
    public float clawScaleMin = 30f;

    [Tooltip("clawScore = 1 のときの爪形メッシュの大きさです")]
    public float clawScaleMax = 80f;

    // ======================================================================
    // インスペクター — 追従と平滑化
    // ======================================================================
    [Header("追従と平滑化")]
    [Tooltip("位置の追従速度です。小さいほど遅れて動きますが、安定します")]
    [Range(0.5f, 20f)]
    public float clawFollowStrength = 4f;

    [Tooltip("回転の追従速度です")]
    [Range(0.5f, 20f)]
    public float clawRotationFollowStrength = 3f;

    [Tooltip("大きさの追従速度です")]
    [Range(0.5f, 20f)]
    public float clawScaleFollowStrength = 5f;

    [Tooltip("生成時に各爪形へ加えるランダムな水平回転角（度）です")]
    [Range(0f, 180f)]
    public float clawRotationRandomness = 30f;

    [Tooltip("検出した波の進行方向を爪形の前方軸に反映する割合です。" +
             "0 は常にワールド Z 方向、1 は検出方向をそのまま使います")]
    [Range(0f, 1f)]
    public float clawForwardBlendWithWave = 0.7f;

    // ======================================================================
    // インスペクター — デバッグ
    // ======================================================================
    [Header("デバッグ")]
    public bool  showClawCandidates  = false;
    public bool  showActiveClaws     = true;
    public bool  logSpawnKill        = false;
    [Tooltip("確認用に水面から追加で持ち上げる高さ（m）です。確認後は 0 に戻します")]
    public float clawDebugHeightOffset = 3f;

    // ======================================================================
    // 非公開 — プール
    // ======================================================================
    private List<ActiveClawInstance> _pool   = new List<ActiveClawInstance>();
    private List<ActiveClawInstance> _active = new List<ActiveClawInstance>();

    // ======================================================================
    // 生存期間の管理
    // ======================================================================

    void Start()
    {
        if (clawMeshEntries == null || clawMeshEntries.Length == 0)
        {
            Debug.LogWarning("[OceanClawManager] clawMeshEntries が空です。インスペクターで Claw_low の Mesh を追加してください。");
            return;
        }

        // プールを先に用意する。
        int poolSize = clawDetector != null ? clawDetector.maxClawInstances : 20;
        for (int i = 0; i < poolSize; i++)
            _pool.Add(CreatePooledInstance());
    }

    void OnDisable()
    {
        // 稼働中の実体をすべてプールへ戻す。
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
    // 稼働中の実体を更新
    // ======================================================================

    private void UpdateActiveInstances(IReadOnlyList<ClawCandidate> candidates)
    {
        for (int i = _active.Count - 1; i >= 0; i--)
        {
            ActiveClawInstance inst = _active[i];
            inst.age += Time.deltaTime;

            // 対応半径内で最も近い候補を探す。
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

            // 回収の判定。スコアの低下と最小寿命の経過を両方必要とする。
            bool scoreDead   = inst.currentScore < clawKillThreshold;
            bool oldEnough   = inst.age >= clawLifetimeMin;
            bool tooOld      = inst.age >= clawLifetimeMax;

            if (tooOld || (scoreDead && oldEnough))
            {
                if (logSpawnKill)
                    Debug.Log($"[OceanClawManager] 爪形を回収: 位置={inst.anchorWorldXZ}, 経過時間={inst.age:F1} 秒");
                ReturnToPool(inst);
                _active.RemoveAt(i);
                continue;
            }

            // 基準 UV で BuoyancyData の高さを継続して読み戻す。
            UpdateHeightReadback(inst);

            // 変換の目標値を計算する。
            Vector3 worldPos = new Vector3(inst.anchorWorldXZ.x, inst.cachedWorldY + clawDebugHeightOffset, inst.anchorWorldXZ.y);

            // 対応する候補があればその法線と進行方向を使い、なければワールド座標の上と前を使う。
            Vector3 normal  = bestDist < float.MaxValue ? bestMatch.surfaceNormal : Vector3.up;
            Vector3 forward = bestDist < float.MaxValue ? bestMatch.waveForward   : Vector3.forward;

            // clawForwardBlendWithWave の割合で進行方向とワールド Z 方向を混ぜる。
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

            // 目標値へ滑らかに近づける。
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
    // 稼働中の実体に対応していない候補から新しい爪形を生成
    // ======================================================================

    private void SpawnFromCandidates(IReadOnlyList<ClawCandidate> candidates)
    {
        foreach (var c in candidates)
        {
            if (c.score < clawSpawnThreshold) continue;
            if (_pool.Count == 0) break;  // プールが空になった。

            // この候補に稼働中の実体がすでに対応しているか調べる。
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
    // 生成の補助処理
    // ======================================================================

    private void SpawnClaw(ClawCandidate c)
    {
        if (_pool.Count == 0) return;
        if (clawMeshEntries == null || clawMeshEntries.Length == 0)
        {
            Debug.LogWarning("[OceanClawManager] clawMeshEntries が空です。インスペクターで Claw_low の Mesh を追加してください。");
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

        // 変種を選ぶ。
        int variantIndex = PickVariantIndex(c.score);
        ApplyVariant(inst, variantIndex);

        // 初期変換を設定する。
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
            Debug.Log($"[OceanClawManager] 爪形を生成: 位置={c.worldPos}, スコア={c.score:F2}, 変種={variantIndex}");
    }

    // ------------------------------------------------------------------
    // 変種の選択
    // ------------------------------------------------------------------

    /// <summary>
    /// スコアに応じて、または weight による抽選で変種の番号を選ぶ。
    /// </summary>
    private int PickVariantIndex(float score)
    {
        if (clawMeshEntries == null || clawMeshEntries.Length == 0) return 0;
        if (clawMeshEntries.Length == 1) return 0;

        if (clawVariantByScore)
        {
            // score=0 は番号 0、score=1 は最後の番号。
            return Mathf.Clamp(
                Mathf.FloorToInt(score * clawMeshEntries.Length),
                0, clawMeshEntries.Length - 1);
        }

        // weight に応じてランダムに選ぶ。
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
    /// 選択した変種の Mesh と Material を実体へ適用する。
    /// Prefab Override、または Mesh と Material の直接指定に対応する。
    /// </summary>
    private void ApplyVariant(ActiveClawInstance inst, int variantIndex)
    {
        ClawMeshEntry entry = clawMeshEntries[variantIndex];

        if (entry.prefabOverride != null)
        {
            // Prefab 方式: 既存の子オブジェクトを除いてから置き換える。
            foreach (Transform oldChild in inst.tr)
                Destroy(oldChild.gameObject);

            GameObject newChild = Instantiate(entry.prefabOverride, inst.tr);
            newChild.transform.localPosition = Vector3.zero;
            newChild.transform.localRotation = Quaternion.identity;
            newChild.transform.localScale    = Vector3.one;
            return;
        }

        // Mesh と Material を直接指定する方式: MeshFilter と MeshRenderer を更新する。
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
            Debug.LogWarning("[OceanClawManager] Mesh が空です。Claw Mesh Entries で FBX を展開し、" +
                             "FBX ファイル自体ではなく、三角形アイコンの子アセット（Mesh）を Mesh 欄へ指定してください。");
        }

        if (entry.material != null) mr.sharedMaterial = entry.material;
        else Debug.LogWarning("[OceanClawManager] Material が空です。材質を指定してください。");
    }

    private void ReturnToPool(ActiveClawInstance inst)
    {
        inst.active = false;
        if (inst.go != null) inst.go.SetActive(false);
        _pool.Add(inst);
    }

    private ActiveClawInstance CreatePooledInstance()
    {
        // 基本の GameObject を作り、生成時に ApplyVariant で Mesh を取り付ける。
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
    // 実体ごとの非同期の高さ読戻し
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
                // 次の読戻し要求をすぐ登録する。
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
        // anchorUV を BuoyancyData（1024×1024）の画素座標へ変換する。
        int px = Mathf.Clamp(Mathf.FloorToInt(inst.anchorUV.x * 1023f), 0, 1023);
        int py = Mathf.Clamp(Mathf.FloorToInt(inst.anchorUV.y * 1023f), 0, 1023);

        inst.heightRequest        = AsyncGPUReadback.Request(rt, 0, px, 1, py, 1, 0, 1, null);
        inst.heightRequestPending = true;
    }

    // ======================================================================
    // デバッグ用ギズモ
    // ======================================================================

#if UNITY_EDITOR
    void OnDrawGizmos()
    {
        if (showActiveClaws)
        {
            foreach (var inst in _active)
            {
                if (!inst.active) continue;

                // 爪形の位置に青い球を描き、スコアに応じて大きさを変える。
                Gizmos.color = Color.blue;
                Gizmos.DrawWireSphere(inst.tr.position + Vector3.up, 0.5f + inst.currentScore);

                // 基準となる XZ 位置を描く。
                Vector3 anchor = new Vector3(inst.anchorWorldXZ.x, inst.cachedWorldY, inst.anchorWorldXZ.y);
                Gizmos.color = new Color(0.3f, 0.6f, 1f, 0.5f);
                Gizmos.DrawLine(anchor, anchor + Vector3.up * 3f);

                // 経過時間を示す線。寿命に近づくにつれて緑から赤に変わる。
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
            $"[ClawManager] 稼働中: {_active.Count}  待機中: {_pool.Count}");
        y += 20;

        if (clawDetector != null)
            GUI.Label(new Rect(10, y, 300, 20),
                $"[ClawDetector] 候補: {clawDetector.Candidates.Count}  準備完了: {clawDetector.IsReady}");
    }
#endif
}
