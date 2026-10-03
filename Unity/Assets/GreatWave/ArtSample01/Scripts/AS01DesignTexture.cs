using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

namespace GreatWave.ArtSample01
{
    // 美術の見本01（Q29）見本 B（原画のような舌形）の設計のテクスチャを読む部品。場面の写し（Assets/GreatWave/ArtSample01/Scenes/AS01_SampleB_*.unity）で、
    // 描画の道具（AS01SampleRender・S01BRender）が -s01bDesign で行うことと同じことを、場面を開いた時・Play の時に行う：
    //   s01b_design.json（U0・V0・h・rows_U・cols_V）と s01b_design_f16.bin（RGBAHalf、行 = u、列 = w）を読み、
    //   大域の _S01BDesign・_S01BRect = (U0, V0, h, 0)・_S01BSize = (rows_U, cols_V, 0, 0) に渡す（シェーダーは大域を読む。材質のファイルには書かない）。
    // テクスチャは場面にも材質のファイルにも保存しない（HideAndDontSave。データは Git 対象外の Build/Polish/sample01/texB/work/design_final）。
    // 静止の見本のための部品で、プレイヤーのビルドへの持ち込み（StreamingAssets）はしていない（Editor で見るため）。
    [ExecuteAlways]
    public class AS01DesignTexture : MonoBehaviour
    {
        [Serializable] class Meta { public float U0, V0, h; public int rows_U, cols_V; }

        [Tooltip("設計のフォルダー（Unity プロジェクトからの相対パスか絶対パス）。s01b_design.json と s01b_design_f16.bin")]
        public string designDir = "Build/Polish/sample01/texB/work/design_final";
        [Tooltip("s01b_design_f16.bin の SHA-256（空なら照合しない）")] public string designSha256 = "";

        public bool Loaded => tex != null;
        public string Sha256Read { get; private set; } = "";
        Texture2D tex;

        void OnEnable() => Load();

        void OnDisable()
        {
            if (tex != null)
            {
                if (Application.isPlaying) Destroy(tex); else DestroyImmediate(tex);
                tex = null;
            }
        }

        public void Load()
        {
            if (tex != null) { Bind(); return; }
            string dir = Path.GetFullPath(designDir);
            string js = Path.Combine(dir, "s01b_design.json"), bin = Path.Combine(dir, "s01b_design_f16.bin");
            if (!File.Exists(js) || !File.Exists(bin)) { Debug.LogError("AS01DesignTexture：設計のファイルがありません: " + dir); return; }
            var m = JsonUtility.FromJson<Meta>(File.ReadAllText(js, Encoding.UTF8));
            var raw = File.ReadAllBytes(bin);
            if (raw.Length != m.rows_U * m.cols_V * 8) { Debug.LogError("AS01DesignTexture：s01b_design_f16.bin の大きさが合いません: " + raw.Length); return; }
            using (var s = SHA256.Create()) Sha256Read = BitConverter.ToString(s.ComputeHash(raw)).Replace("-", "").ToLowerInvariant();
            if (!string.IsNullOrEmpty(designSha256) && designSha256 != Sha256Read) { Debug.LogError("AS01DesignTexture：SHA-256 が違います: " + Sha256Read); return; }
            tex = new Texture2D(m.cols_V, m.rows_U, TextureFormat.RGBAHalf, true, true)
            {
                hideFlags = HideFlags.HideAndDontSave, name = "AS01 S01B design", wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Trilinear, anisoLevel = 8
            };
            tex.SetPixelData(raw, 0);
            tex.Apply(true, false);
            Shader.SetGlobalVector("_S01BRect", new Vector4(m.U0, m.V0, m.h, 0));
            Shader.SetGlobalVector("_S01BSize", new Vector4(m.rows_U, m.cols_V, 0, 0));
            Bind();
            if (Application.isPlaying) Debug.Log("AS01_DESIGN_LOADED dir=" + designDir + " sha256=" + Sha256Read + " size=" + m.cols_V + "x" + m.rows_U);
        }

        void Bind()
        {
            Shader.SetGlobalTexture("_S01BDesign", tex);
        }
    }
}
