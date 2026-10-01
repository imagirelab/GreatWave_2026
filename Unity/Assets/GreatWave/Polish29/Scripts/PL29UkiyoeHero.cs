using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using GreatWave.Design30;
using UnityEngine;

namespace GreatWave.Polish29
{
    // 仕上げ29（Q28）：主役波のシート（DS30SheetPlayer）に、視点によらない立体の浮世絵の材質（PL29 Ukiyoe Keypose）を付ける。
    //  1) pl29_hero_attr_f32.bin（頂点ごとの float32 × 12。pl29_hero_attr.py が K*′ の格子から作る面の座標と t* の法線）を読み、
    //     主役波のメッシュの UV3・UV4・UV5（TEXCOORD3・4・5）に入れる。
    //  2) 主役波の面のレンダラーの材質を material（PL29_Ukiyoe_Hero.mat）にする（場面で既にそうなら何もしない）。
    // 原画カメラからの投影の焼き込み（色区テクスチャ・UV3 の表）は使わない。場面では DS30SheetPlayer の sdfPath・warpPath・uv3File を空にしておく
    // （PL29Setup が作る場面はそうなっている）。keypose の値（位置・T_white・τ）は DS30SheetPlayer が MaterialPropertyBlock で渡すので、材質を替えても同じ位置で描ける。
    // Play モードでは、シートが読み込まれた後の最初の OnEnable／LateUpdate で付ける。Editor の道具は Apply() を呼ぶ。
    [DefaultExecutionOrder(120)]
    public class PL29UkiyoeHero : MonoBehaviour
    {
        [Tooltip("主役波のシート（空なら同じ物の DS30SheetPlayer）")] public DS30SheetPlayer sheet;
        [Tooltip("面の座標（Unity プロジェクトからの相対パスか絶対パス）")] public string attrPath = "Build/Polish/29/after/attr/pl29_hero_attr_f32.bin";
        [Tooltip("面の座標の SHA-256（空なら照合しない）")] public string attrSha256 = "";
        [Tooltip("PL29 Ukiyoe Keypose の材質")] public Material material;

        public bool Applied { get; private set; }
        public string AttrSha256Read { get; private set; } = "";
        public Material PreviousMaterial { get; private set; }

        public const int FloatsPerVertex = 12;

        public DS30SheetPlayer Sheet => sheet != null ? sheet : (sheet = GetComponent<DS30SheetPlayer>());

        /// <summary>面の座標を主役波のメッシュへ入れ、材質を替える。シートは読み込む（未読なら）。</summary>
        public void Apply()
        {
            var sp = Sheet;
            if (sp == null) throw new InvalidOperationException("PL29UkiyoeHero：DS30SheetPlayer がありません。");
            sp.EnsureLoaded();
            var mesh = sp.SurfaceMesh;
            if (mesh == null) throw new InvalidOperationException("PL29UkiyoeHero：主役波のメッシュがありません。");
            int n = mesh.vertexCount;
            var bytes = File.ReadAllBytes(Path.GetFullPath(attrPath));
            if (bytes.Length != n * FloatsPerVertex * 4)
                throw new InvalidDataException("PL29UkiyoeHero：面の座標の大きさが頂点 × 12 × 4 と合いません: " + bytes.Length + " / " + n);
            using (var s = SHA256.Create()) AttrSha256Read = BitConverter.ToString(s.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
            if (!string.IsNullOrEmpty(attrSha256) && attrSha256 != AttrSha256Read)
                throw new InvalidDataException("PL29UkiyoeHero：面の座標の SHA-256 が違います: " + AttrSha256Read);
            var f = new float[n * FloatsPerVertex];
            Buffer.BlockCopy(bytes, 0, f, 0, bytes.Length);
            var a = new List<Vector4>(n);
            var b = new List<Vector4>(n);
            var cc = new List<Vector4>(n);
            for (int i = 0; i < n; i++)
            {
                int o = i * FloatsPerVertex;
                a.Add(new Vector4(f[o], f[o + 1], f[o + 2], f[o + 3]));
                b.Add(new Vector4(f[o + 4], f[o + 5], f[o + 6], f[o + 7]));
                cc.Add(new Vector4(f[o + 8], f[o + 9], f[o + 10], f[o + 11]));
            }
            var bounds = mesh.bounds;
            mesh.SetUVs(3, a);
            mesh.SetUVs(4, b);
            mesh.SetUVs(5, cc);
            mesh.bounds = bounds;
            var r = sp.Surface;
            if (r != null && material != null && r.sharedMaterial != material)
            {
                PreviousMaterial = r.sharedMaterial;
                r.sharedMaterial = material;
            }
            Applied = true;
            // 実行の記録（Release のプレイヤーの player.log で、投影の焼き込みではなくこの材質が付いたことを確かめる。仕上げ29 修正の回）
            if (Application.isPlaying)
                Debug.Log("PL29_HERO_APPLIED attr=" + attrPath + " sha256=" + AttrSha256Read + " shader=" + (r != null && r.sharedMaterial != null ? r.sharedMaterial.shader.name : "") +
                          " sdfPath='" + sp.sdfPath + "' warpPath='" + sp.warpPath + "' uv3File='" + sp.uv3File + "'");
        }

        /// <summary>材質を元へ戻す（Editor の道具の後始末）。メッシュの UV3・UV4 は残しても前の材質は読まない。</summary>
        public void Revert()
        {
            var sp = Sheet;
            if (sp != null && sp.Surface != null && PreviousMaterial != null) sp.Surface.sharedMaterial = PreviousMaterial;
            PreviousMaterial = null;
            Applied = false;
        }

        Mesh appliedMesh;

        bool NeedsApply => Sheet != null && Sheet.Loaded && (!Applied || Sheet.SurfaceMesh != appliedMesh);

        void OnEnable()
        {
            if (Application.isPlaying && NeedsApply) { Apply(); appliedMesh = Sheet.SurfaceMesh; }
        }

        void LateUpdate()
        {
            // シートが読み直された（メッシュが替わった）時も付け直す
            if (Application.isPlaying && NeedsApply) { Apply(); appliedMesh = Sheet.SurfaceMesh; }
        }
    }
}
