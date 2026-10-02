using System;
using System.Collections.Generic;
using System.IO;
using GreatWave.Design34;
using GreatWave.Design38;
using UnityEngine;

namespace GreatWave.Polish33R01H
{
    // 仕上げ33修正01（Houdini の変種）：立つ白い爪の指（Houdini の VDB の滑らかな和で作った鍵の形を、指の中心線に結び付けて全コマへ動かしたもの。
    // 書式は設計34 の爪の層と同じ GreatWave.DS33.claw_layout/1 で、DS34ClawPlayer がそのまま再生する）の見え方を付ける。
    //  1) 爪の結合メッシュの UV2 に、並びの横の pl33r01h_vattr_f32.bin（頂点 × 4）の (陰の段 x, 根元 0 → 先 1) を入れ、材質を PL29 Claw Shade にする
    //     （段：x > 0.30 で白、それ以下で水色の版。x は t* の頂点の法線と指の上の向き（根元の円の法線）の内積 + 0.25 で、視点によらない）。
    //  2) 設計38 の爪の縁の線（反転シェル）のメッシュの UV3.x に、縁の線の根元からの位置（−1 は線なし＝頂の帯の側）を入れ、材質を
    //     PL32 Claw Outline（根元で線を開く）にし、原画視点でも描く（_DS38PaintFade = 0、PL29ClawShade と同じ）。
    // 帯の輪の並び（8·stations + 11）を前提にする PL29ClawShade・PL32ClawLook・PL33ClawLook の代わり。原画カメラからの投影は使わない。
    [DefaultExecutionOrder(130)]
    public class PL33R01HClawLook : MonoBehaviour
    {
        public DS34ClawPlayer claws;
        [Tooltip("PL29 Claw Shade の材質")] public Material material;
        public DS38ClawOutline outline;
        [Tooltip("PL32 Claw Outline のシェーダー（場面から参照してビルドに入れる）")] public Shader outlineShader;
        [Tooltip("根元で線を開く（x：幅 0、y：幅 1。根元 0 → 先 1）")] public Vector2 rootFade = new Vector2(0.20f, 0.60f);
        public bool linesEverywhere = true;
        public const string VattrFile = "pl33r01h_vattr_f32.bin";

        public bool Applied { get; private set; }
        public int[] VertexClassCounts { get; } = new int[3];
        public int LineVertices { get; private set; }
        public string VattrPath { get; private set; } = "";
        Mesh appliedClaw, appliedLine;
        Material lineMat;
        Material[] previous;
        float[] vattr;
        MaterialPropertyBlock mpb;

        DS34ClawPlayer Claws => claws != null ? claws : (claws = GetComponent<DS34ClawPlayer>());

        void LoadVattr(int n)
        {
            if (vattr != null && vattr.Length == n * 4) return;
            VattrPath = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(Claws.layoutPath)), VattrFile);
            var b = File.ReadAllBytes(VattrPath);
            if (b.Length != n * 16) throw new InvalidDataException("PL33R01HClawLook：頂点の属性の大きさが合いません: " + b.Length + " / " + (n * 16));
            vattr = new float[n * 4];
            Buffer.BlockCopy(b, 0, vattr, 0, b.Length);
        }

        public void Apply()
        {
            var cp = Claws;
            if (cp == null) throw new InvalidOperationException("PL33R01HClawLook：DS34ClawPlayer がありません。");
            cp.Load();
            if (outline == null) outline = GetComponent<DS38ClawOutline>();
            var mesh = cp.GetComponent<MeshFilter>().sharedMesh;
            int n = mesh.vertexCount;
            LoadVattr(n);
            var uv2 = new Vector2[n];
            Array.Clear(VertexClassCounts, 0, 3);
            for (int i = 0; i < n; i++)
            {
                uv2[i] = new Vector2(vattr[4 * i], vattr[4 * i + 1]);
                VertexClassCounts[uv2[i].x > 0.30f ? 0 : (uv2[i].x > -0.45f ? 1 : 2)]++;
            }
            mesh.SetUVs(2, uv2);
            var r = cp.GetComponent<MeshRenderer>();
            if (material != null)
            {
                var cur = r.sharedMaterials;
                if (previous == null) previous = cur;
                var mats = new Material[Math.Max(1, cur.Length)];
                for (int i = 0; i < mats.Length; i++) mats[i] = material;
                r.sharedMaterials = mats;
            }
            LineVertices = 0;
            if (outline != null)
            {
                outline.Sync();
                var line = outline.Line;
                if (line != null)
                {
                    var lm = line.GetComponent<MeshFilter>().sharedMesh;
                    if (lm != null && lm.vertexCount == n)
                    {
                        var a = new Vector2[n];
                        for (int i = 0; i < n; i++) a[i] = new Vector2(vattr[4 * i + 2], vattr[4 * i + 3]);
                        lm.SetUVs(3, a);
                        LineVertices = n;
                        var sh = outlineShader != null ? outlineShader : Shader.Find("GreatWave/Polish32/PL32 Claw Outline");
                        if (sh == null) throw new InvalidOperationException("PL33R01HClawLook：PL32 Claw Outline のシェーダーがありません。");
                        if (lineMat == null || line.sharedMaterial != lineMat)
                        {
                            var src = line.sharedMaterial;
                            lineMat = new Material(sh) { name = "PL33R01H 指の縁の線（根元で開く）", hideFlags = HideFlags.DontSave, enableInstancing = true };
                            if (src != null) lineMat.CopyPropertiesFromMaterial(src);
                            lineMat.SetVector("_PL32RootFade", new Vector4(rootFade.x, rootFade.y, 0, 0));
                            line.sharedMaterial = lineMat;
                        }
                        if (linesEverywhere)
                        {
                            if (mpb == null) mpb = new MaterialPropertyBlock();
                            line.GetPropertyBlock(mpb);
                            mpb.SetVector("_DS38PaintFade", Vector4.zero);
                            line.SetPropertyBlock(mpb);
                        }
                        appliedLine = lm;
                    }
                }
            }
            appliedClaw = mesh;
            Applied = true;
            if (Application.isPlaying)
                Debug.Log("PL33R01H_CLAW_LOOK_APPLIED vertices=" + n + " classes=" + VertexClassCounts[0] + "/" + VertexClassCounts[1] + "/" + VertexClassCounts[2] + " lineVertices=" + LineVertices);
        }

        public void Revert()
        {
            var cp = Claws;
            if (cp != null && previous != null) cp.GetComponent<MeshRenderer>().sharedMaterials = previous;
            previous = null;
            if (outline != null && outline.Line != null) outline.Line.SetPropertyBlock(null);
            Applied = false;
        }

        bool NeedsApply
        {
            get
            {
                var cp = Claws;
                if (cp == null || !cp.Loaded) return false;
                if (!Applied || cp.GetComponent<MeshFilter>().sharedMesh != appliedClaw) return true;
                if (outline != null && outline.Line != null)
                {
                    var lm = outline.Line.GetComponent<MeshFilter>().sharedMesh;
                    if (lm != null && lm != appliedLine) return true;
                }
                return false;
            }
        }

        void LateUpdate()
        {
            if (!Application.isPlaying) return;
            if (NeedsApply) Apply();
        }

        void OnDestroy()
        {
            if (lineMat != null) { if (Application.isPlaying) Destroy(lineMat); else DestroyImmediate(lineMat); lineMat = null; }
        }
    }
}
