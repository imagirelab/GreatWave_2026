using System;
using System.IO;
using GreatWave.Design30;
using UnityEngine;

namespace GreatWave.Design38
{
    // 設計38：DS27 形式のシート（主役波・周りの海 near・far）の外殻線 v1（DS38 Outline Keypose）を 1 枚のシートに付ける。
    //  ・外殻線の子レンダラー（MeshFilter＋MeshRenderer）を作り、DS30SheetPlayer.outline に入れる（主役波は設計27 の外殻線の子を使い回し、材質だけ替える）。
    //    DS30SheetPlayer が keypose の値を外殻線のレンダラーの MaterialPropertyBlock にも入れるので、面と線は同じ時刻・同じ位置になる（古い位置に残らない）。
    //  ・材質の値：シートの番号（検査用）、列の範囲（法線を範囲の中の三角形だけから求める）、頂点ごとの印（原画視点で原画にない線を描かない）。
    //  ・DS30SheetPlayer が読み込む前（EnsureLoaded の前）に Attach を呼ぶこと（読み込みで外殻線の MeshFilter にメッシュが入る）。
    // PC のオフスクリーン描画（DS38Render）で使った。Play モードは OnEnable で印のバッファを作る（Play モードの確かめはこの番号ではしていない）。
    [DefaultExecutionOrder(-40)]
    public class DS38SheetOutline : MonoBehaviour
    {
        public DS30SheetPlayer sheet;
        [Tooltip("DS38 Outline Keypose の材質（シートごとに 1 つ）")]
        public Material lineMaterial;
        [Tooltip("検査用のシートの番号（1 主役波・2 near・3 far）")]
        public int sheetId = 1;
        [Tooltip("頂点ごとの印（float32 × 頂点、1 描く・0 原画視点では描かない）。空なら全部描く")]
        public string maskPath = "";

        ComputeBuffer maskBuf;
        public int MaskedVertices { get; private set; }
        public string MaskSha256 { get; private set; } = "";

        /// <summary>外殻線の子レンダラーを用意して DS30SheetPlayer.outline に入れる（読み込みの前に呼ぶ）。</summary>
        public MeshRenderer Attach()
        {
            if (sheet == null) sheet = GetComponent<DS30SheetPlayer>();
            if (sheet == null) throw new InvalidOperationException("DS30SheetPlayer がありません");
            var r = sheet.outline;
            if (r == null)
            {
                var go = new GameObject("DS38 外殻線 " + sheet.sheetName);
                go.transform.SetParent(sheet.transform, false);
                go.AddComponent<MeshFilter>();
                r = go.AddComponent<MeshRenderer>();
                sheet.outline = r;
            }
            r.sharedMaterial = lineMaterial;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            r.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off;
            r.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
            r.motionVectorGenerationMode = MotionVectorGenerationMode.ForceNoMotion;
            if (lineMaterial != null)
            {
                lineMaterial.SetFloat("_DS38SheetId", sheetId);
                lineMaterial.SetVector("_DS38ColRange", new Vector4(sheet.colMin, sheet.colMax, 0, 0));
            }
            return r;
        }

        /// <summary>頂点ごとの印のバッファを作って材質に入れる（シートを読み込んだ後。mask が null なら maskPath、それも空なら全部 1）。</summary>
        public void BindMask(float[] mask = null)
        {
            if (sheet == null || lineMaterial == null) return;
            sheet.EnsureLoaded();
            int n = sheet.PackageMeta.rows * sheet.PackageMeta.cols;
            if (mask == null && !string.IsNullOrEmpty(maskPath) && File.Exists(Path.GetFullPath(maskPath)))
            {
                var b = File.ReadAllBytes(Path.GetFullPath(maskPath));
                if (b.Length == n * 4) { mask = new float[n]; Buffer.BlockCopy(b, 0, mask, 0, b.Length); MaskSha256 = Sha(b); }
            }
            bool on = mask != null;
            if (mask == null) { mask = new float[n]; for (int i = 0; i < n; i++) mask[i] = 1f; }
            if (mask.Length != n) throw new InvalidDataException(sheet.sheetName + "：印の数が頂点の数と違います");
            ReleaseMask();
            maskBuf = new ComputeBuffer(n, 4);
            maskBuf.SetData(mask);
            lineMaterial.SetBuffer("_DS38LineMask", maskBuf);
            lineMaterial.SetFloat("_DS38MaskOn", on ? 1f : 0f);
            int m = 0; foreach (var x in mask) if (x < 0.5f) m++;
            MaskedVertices = m;
        }

        void OnEnable()
        {
            if (Application.isPlaying && sheet != null && lineMaterial != null && sheet.Loaded) BindMask();
        }

        void Start()
        {
            if (Application.isPlaying && maskBuf == null && sheet != null && lineMaterial != null) BindMask();
        }

        void OnDisable() { ReleaseMask(); }

        public void ReleaseMask()
        {
            if (maskBuf != null) { maskBuf.Release(); maskBuf = null; }
        }

        static string Sha(byte[] b)
        {
            using (var s = System.Security.Cryptography.SHA256.Create()) return BitConverter.ToString(s.ComputeHash(b)).Replace("-", "").ToLowerInvariant();
        }
    }
}
