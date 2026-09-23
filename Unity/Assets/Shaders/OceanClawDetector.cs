using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;
using Unity.Collections;

// ---------------------------------------------------------------------------
// 共通のデータ型
// ---------------------------------------------------------------------------

/// <summary>
/// 北斎の波頭に似た爪状白波を配置する候補地点。
/// 各値は OceanClawDetector が読み戻すたびに設定する。
/// </summary>
public struct ClawCandidate
{
    /// ワールド座標。ここでは Y を 0 とし、管理側が BuoyancyData から調整する。
    public Vector3 worldPos;

    /// FFT タイル内の正規化 UV。繰り返しを適用し、BuoyancyData の再取得に使う。
    public Vector2 anchorUV;

    /// ClawMaskTexture から得た GPU 評価値。
    public float score;        // clawScore の総合値
    public float heightScore;
    public float slopeScore;
    public float crestScore;

    /// 読み戻した値の有限差分から近似した面の法線。
    public Vector3 surfaceNormal;

    /// 高さの勾配から近似した波の進行方向。
    public Vector3 waveForward;
}

// ---------------------------------------------------------------------------
// OceanClawDetector
// ---------------------------------------------------------------------------

/// <summary>
/// 毎フレーム ClawMaskTexture を低解像度で GPU から読み戻し、
/// ワールド座標の ClawCandidate 候補を選別して返す。
///
/// 検出条件を FFT 処理から独立して調整できるよう、FFTOcean_Script とは分けている。
/// </summary>
public class OceanClawDetector : MonoBehaviour
{
    // ------------------------------------------------------------------
    // Inspector の参照設定
    // ------------------------------------------------------------------
    [Header("参照")]
    [Tooltip("ClawMaskTexture を管理する FFT 海面スクリプト")]
    public FFTOcean_Script oceanScript;

    // ------------------------------------------------------------------
    // Inspector の検出設定
    // ------------------------------------------------------------------
    [Header("爪状白波の検出")]
    [Tooltip("全体の切り替え。無効にすると読み戻しと候補生成を停止する。")]
    public bool enableClawGeneration = true;

    [Tooltip("読み戻しごとに候補を探すワールド空間の格子解像度。" +
             "32 なら海面メッシュを 32×32 の格子で調べる。")]
    [Range(8, 64)]
    public int clawScanGridSize = 32;

    [Tooltip("格子点を候補に加えるための総合 clawScore の最小値。")]
    [Range(0f, 1f)]
    public float clawScoreThreshold = 0.25f;

    [Tooltip("候補点同士のワールド空間での最小距離。密集を防ぐ。")]
    [Range(1f, 50f)]
    public float clawMinSpacing = 8f;

    [Tooltip("選別後に保持する候補の最大数。")]
    [Range(1, 64)]
    public int maxClawInstances = 20;

    // ------------------------------------------------------------------
    // Inspector のデバッグ設定
    // ------------------------------------------------------------------
    [Header("デバッグ")]
    public bool showClawCandidates = true;

    [Tooltip("設定すると、確認用に低解像度の読み戻しテクスチャをここへ転送する。" +
             "Inspector で小さな RenderTexture または RawImage を割り当てる。")]
    public RenderTexture clawMaskDebugOutput;

    // ------------------------------------------------------------------
    // OceanClawManager へ渡す読み取り専用の出力
    // ------------------------------------------------------------------
    public IReadOnlyList<ClawCandidate> Candidates => _candidates;
    public bool IsReady => _readbackReady;

    // ------------------------------------------------------------------
    // 内部状態
    // ------------------------------------------------------------------

    // CPU 読み戻し用の ClawMaskTexture の低解像度コピー。
    // 大きさは _readbackSize × _readbackSize。Color として読みやすい ARGBFloat 形式。
    private RenderTexture _clawMaskLowRes;
    private const int _readbackSize = 32;   // 32×32、約16 KB

    // 非同期読み戻しのバッファー。処理を待たず、直近の完了結果を使う。
    private Color[] _readbackBuffer;
    private bool    _readbackPending = false;
    private bool    _readbackReady   = false;

    private readonly List<ClawCandidate> _candidates = new List<ClawCandidate>(64);

    // ------------------------------------------------------------------
    // 動作周期
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

        // 双線形補間で ClawMaskTexture を _clawMaskLowRes へ縮小転送する。
        Graphics.Blit(clawMask, _clawMaskLowRes);

        // 必要に応じてデバッグ用の描画テクスチャへも転送する。
        if (clawMaskDebugOutput != null)
            Graphics.Blit(_clawMaskLowRes, clawMaskDebugOutput);

        // 非同期読み戻しを要求する。同時実行は一件に制限する。
        if (!_readbackPending)
        {
            AsyncGPUReadback.Request(_clawMaskLowRes, 0, TextureFormat.RGBAFloat, OnReadbackComplete);
            _readbackPending = true;
        }
    }

    // ------------------------------------------------------------------
    // 読み戻しの完了処理
    // ------------------------------------------------------------------

    private void OnReadbackComplete(AsyncGPUReadbackRequest req)
    {
        _readbackPending = false;

        if (req.hasError)
        {
            Debug.LogWarning("[OceanClawDetector] GPU の読み戻しに失敗したため、このフレームを飛ばします。");
            return;
        }

        // 再利用のため、ネイティブ配列を管理配列へコピーする。
        NativeArray<Color> native = req.GetData<Color>();
        if (native.Length != _readbackBuffer.Length)
        {
            Debug.LogWarning("[OceanClawDetector] 読み戻しデータの大きさが一致しません。");
            return;
        }
        native.CopyTo(_readbackBuffer);

        // 新しいデータから候補一覧を作る。
        FindCandidates(_readbackBuffer);
        _readbackReady = true;
    }

    // ------------------------------------------------------------------
    // 候補の検出
    // ------------------------------------------------------------------

    private void FindCandidates(Color[] buf)
    {
        if (oceanScript == null) return;

        _candidates.Clear();

        float oceanHalf = oceanScript.waterMeshLength * 0.5f;
        Vector3 oceanCenter = oceanScript.transform.position;

        // 海面メッシュ上のワールド空間格子を走査する。
        for (int gz = 0; gz < clawScanGridSize; gz++)
        {
            for (int gx = 0; gx < clawScanGridSize; gx++)
            {
                float t = (float)oceanScript.waterMeshLength;

                float worldX = oceanCenter.x - oceanHalf + (gx + 0.5f) / clawScanGridSize * t;
                float worldZ = oceanCenter.z - oceanHalf + (gz + 0.5f) / clawScanGridSize * t;

                // ワールド座標 XZ を Tile0 で繰り返し UV に変換する。
                float uvX = Mathf.Repeat(worldX * oceanScript.Tile0, 1f);
                float uvZ = Mathf.Repeat(worldZ * oceanScript.Tile0, 1f);

                // 読み戻しバッファーから値を採る。
                int px = Mathf.Clamp(Mathf.FloorToInt(uvX * _readbackSize), 0, _readbackSize - 1);
                int py = Mathf.Clamp(Mathf.FloorToInt(uvZ * _readbackSize), 0, _readbackSize - 1);

                Color s = buf[py * _readbackSize + px];
                // s.r は heightScore、s.g は slopeScore、s.b は crestScore、s.a は clawScore。
                float clawScore = s.a;

                if (clawScore < clawScoreThreshold) continue;

                // 隣接画素の高さ評価値から有限差分で面法線と波の進行方向を求める。
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

        // 評価値の高い順に並べ、候補間の最小距離を適用する。
        _candidates.Sort((a, b) => b.score.CompareTo(a.score));
        EnforceSpacing(_candidates, clawMinSpacing, maxClawInstances);
    }

    /// <summary>
    /// 評価値が最も高い候補を残し、その候補から minSpacing 未満の候補を除く処理を繰り返す。
    /// 入力の一覧をその場で変更する。
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
    // デバッグ用のギズモ
    // ------------------------------------------------------------------

#if UNITY_EDITOR
    void OnDrawGizmos()
    {
        if (!showClawCandidates || !_readbackReady) return;

        foreach (var c in _candidates)
        {
            // 評価値の低い候補を黄、高い候補を緑で示す。
            Gizmos.color = Color.Lerp(Color.yellow, Color.green, c.score);
            Gizmos.DrawWireSphere(c.worldPos + Vector3.up * 0.5f, 0.6f);

            // 面の法線。
            UnityEditor.Handles.color = Color.cyan;
            UnityEditor.Handles.DrawLine(c.worldPos, c.worldPos + c.surfaceNormal * 2f);

            // 波の進行方向。
            UnityEditor.Handles.color = Color.magenta;
            UnityEditor.Handles.DrawLine(c.worldPos, c.worldPos + c.waveForward * 1.5f);
        }
    }
#endif
}
