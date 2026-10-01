using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using GreatWave.Design30;
using UnityEngine;

namespace GreatWave.Polish30
{
    // 仕上げ30（Q28 を周りの海へ）：周りの海のシート（DS30SheetPlayer、near・far）に、視点によらない立体の浮世絵の材質（PL30 Ukiyoe Sea Keypose）を付ける。
    //  1) pl30_sea_attr_f32.bin（頂点ごとの float32 × 20。pl30_sea_attr.py が t* の網と地形の誘導から作る面の座標）を読み、シートのメッシュの UV3〜UV7 に入れる。
    //     修正01 で 12 → 20 個（稜の系・小波の系・海の沿う座標・谷の縁を分けた）。作る部の 12 個のファイルも読める（UV3〜UV5 だけ）。
    //  2) シートの面のレンダラーの材質を material にし、限定色（_White・_Mizuiro・_AiMid・_AiDark・_LineCol）を主役波の材質から写す（主役波と海の藍濃の 1 段の差をなくす）。
    //  3) 設計36 の t* の高さの段の表（sdfPath・uv3File）は使わない。設計30 の 2 色（whiteAboveTStarY）も使わない。読み込みの前に Configure を呼ぶ。
    // 原画カメラからの投影は使わない（Q28）。keypose の値は DS30SheetPlayer が MaterialPropertyBlock で渡す。
    [DefaultExecutionOrder(125)]
    public class PL30UkiyoeSea : MonoBehaviour
    {
        [Serializable]
        public class Entry
        {
            public DS30SheetPlayer sheet;
            [Tooltip("面の座標（Unity プロジェクトからの相対パスか絶対パス）")] public string attrPath;
            [Tooltip("面の座標の SHA-256（空なら照合しない）")] public string attrSha256 = "";
        }

        public List<Entry> sheets = new List<Entry>();
        [Tooltip("PL30 Ukiyoe Sea Keypose の材質")] public Material material;
        [Tooltip("限定色を写す主役波の材質（空なら写さない）")] public Material heroMaterial;

        public const int FloatsPerVertex = 20;
        public const int FloatsPerVertexOld = 12;
        public bool Applied { get; private set; }
        public List<string> ShaRead { get; } = new List<string>();
        static readonly string[] Palette = { "_White", "_Mizuiro", "_AiMid", "_AiDark", "_LineCol" };

        /// <summary>読み込みの前：設計36 の色区の表・設計30 の 2 色を切る。</summary>
        public void Configure()
        {
            foreach (var e in sheets)
            {
                if (e.sheet == null) continue;
                e.sheet.sdfPath = "";
                e.sheet.uv3File = "";
                e.sheet.warpPath = "";
                e.sheet.whiteAboveTStarY = float.NaN;
            }
        }

        public void Apply()
        {
            if (material != null && heroMaterial != null)
                foreach (var p in Palette) if (heroMaterial.HasProperty(p) && material.HasProperty(p)) material.SetColor(p, heroMaterial.GetColor(p));
            ShaRead.Clear();
            foreach (var e in sheets)
            {
                var sp = e.sheet;
                if (sp == null) continue;
                sp.EnsureLoaded();
                var mesh = sp.SurfaceMesh;
                int n = mesh.vertexCount;
                var bytes = File.ReadAllBytes(Path.GetFullPath(e.attrPath));
                int fpv = bytes.Length == n * FloatsPerVertex * 4 ? FloatsPerVertex : (bytes.Length == n * FloatsPerVertexOld * 4 ? FloatsPerVertexOld : -1);
                if (fpv < 0)
                    throw new InvalidDataException("PL30UkiyoeSea：" + sp.sheetName + " の面の座標の大きさが頂点 × 20（または 12）× 4 と合いません: " + bytes.Length + " / " + n);
                string sha;
                using (var s = SHA256.Create()) sha = BitConverter.ToString(s.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
                if (!string.IsNullOrEmpty(e.attrSha256) && e.attrSha256 != sha)
                    throw new InvalidDataException("PL30UkiyoeSea：" + sp.sheetName + " の面の座標の SHA-256 が違います: " + sha);
                ShaRead.Add(sp.sheetName + " " + sha);
                var f = new float[n * fpv];
                Buffer.BlockCopy(bytes, 0, f, 0, bytes.Length);
                var a = new List<Vector4>(n); var b = new List<Vector4>(n); var c = new List<Vector4>(n);
                var d = new List<Vector4>(fpv >= 16 ? n : 0); var e2 = new List<Vector4>(fpv >= 20 ? n : 0);
                for (int i = 0; i < n; i++)
                {
                    int o = i * fpv;
                    a.Add(new Vector4(f[o], f[o + 1], f[o + 2], f[o + 3]));
                    b.Add(new Vector4(f[o + 4], f[o + 5], f[o + 6], f[o + 7]));
                    c.Add(new Vector4(f[o + 8], f[o + 9], f[o + 10], f[o + 11]));
                    if (fpv >= 16) d.Add(new Vector4(f[o + 12], f[o + 13], f[o + 14], f[o + 15]));
                    if (fpv >= 20) e2.Add(new Vector4(f[o + 16], f[o + 17], f[o + 18], f[o + 19]));
                }
                var bounds = mesh.bounds;
                mesh.SetUVs(3, a); mesh.SetUVs(4, b); mesh.SetUVs(5, c);
                if (fpv >= 16) mesh.SetUVs(6, d);
                if (fpv >= 20) mesh.SetUVs(7, e2);
                mesh.bounds = bounds;
                var r = sp.Surface;
                if (r != null && material != null) r.sharedMaterial = material;
                // 設計36 の SyncFromHero が MaterialPropertyBlock に入れた色を消す（材質の値を使う）
                if (r != null)
                {
                    var blk = new MaterialPropertyBlock();
                    r.GetPropertyBlock(blk);
                    var blk2 = new MaterialPropertyBlock();
                    r.SetPropertyBlock(CopyKeypose(blk, blk2));
                }
            }
            Applied = true;
            if (Application.isPlaying)
                Debug.Log("PL30_SEA_APPLIED shader=" + (material != null ? material.shader.name : "") + " " + string.Join(" | ", ShaRead));
        }

        // 色の値（_White など）を除いた MaterialPropertyBlock（keypose の値は DS30SheetPlayer が毎回入れ直すので、色だけ消せばよい）
        static MaterialPropertyBlock CopyKeypose(MaterialPropertyBlock from, MaterialPropertyBlock to)
        {
            to.Clear();
            return to;
        }

        void Start()
        {
            if (Application.isPlaying && !Applied) Apply();
        }
    }
}
