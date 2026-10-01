using System;
using System.Collections.Generic;
using GreatWave.Design34;
using GreatWave.Design38;
using GreatWave.Polish29;
using UnityEngine;

namespace GreatWave.Polish32
{
    // 仕上げ32 修正の回 1：爪の見え方の 2 つの決まり（どれも帯の頂点の並びだけで決まり、視点・原画カメラによらない）。
    //  1) pl32f_root_open：爪の縁の線（設計38 の DS38 爪の縁の線）の材質を PL32 Claw Outline にし、そのメッシュの UV3.x に根元 → 先の位置
    //     （根元の点 0・輪 s/(輪の数 − 1)・先 1・根元の円 −1）を入れる。線は根元で開き（幅 0 → 1 を _PL32RootFade の間で）、根元の円には線を描かない。
    //     伸びる途中の短い帯が閉じた輪（米粒）に見え、t* の b区域の爪が 1 本ずつ縁取られた虫に見えた（審査の指摘）のを、指が泡の胴から出る形にする。
    //     UV3.y には輪の頂点の向き（1 上面 φ 45〜135°、2 下面 φ 225〜315°、0 横・根元・先）を入れ、縁から見た帯の箱の線を出さない（pl32f_edge_box）。
    //  2) pl32f_tuft_base：根元の円（設計33 の根元の白の円。仕上げ32 修正の回 1 で根元の後ろ＝泡の胴の側へ伸びた楕円にした）を、PL29 Claw Shade の
    //     段で水色の版にする（UV2.x = tuftShade）。原画の爪の付け根の水色の版の雲（摺りの工程の調べ：爪の陰は水色の版）を、房ごとに根元へ置く。
    // 頂点の並び（設計33）：爪ごとに 根元の点 1・輪 stations × 8・先 1・根元の円の中心 1・円 8。
    // Play モードでは、爪の陰の段（PL29ClawShade、順 125）と縁の線のメッシュ（DS38ClawOutline の最初の Sync）の後の LateUpdate で付ける。Editor の道具は Apply() を呼ぶ。
    [DefaultExecutionOrder(130)]
    public class PL32ClawLook : MonoBehaviour
    {
        public DS34ClawPlayer claws;
        public PL29ClawShade shade;
        public DS38ClawOutline outline;
        [Tooltip("PL32 Claw Outline のシェーダー（場面から参照してビルドに入れる）")] public Shader outlineShader;
        [Tooltip("根元で線を開く（x：幅 0、y：幅 1。根元 0 → 先 1）")] public Vector2 rootFade = new Vector2(0.0f, 0.30f);
        [Tooltip("根元の円を水色の版にする")] public bool tuftBase = true;
        [Tooltip("根元の円の UV2.x（PL29 Claw Shade の段：_Steps.y < x ≤ _Steps.x で水色の版）")] public float tuftShade = 0.0f;
        [Tooltip("縁の線を根元で開く")] public bool rootOpen = true;

        public bool Applied { get; private set; }
        public int TuftVertices { get; private set; }
        public int LineVertices { get; private set; }
        Mesh appliedClaw, appliedLine;
        Material lineMat;

        DS34ClawPlayer Claws => claws != null ? claws : (claws = GetComponent<DS34ClawPlayer>());

        public void Apply()
        {
            var cp = Claws;
            if (cp == null) throw new InvalidOperationException("PL32ClawLook：DS34ClawPlayer がありません。");
            cp.Load();
            if (shade == null) shade = GetComponent<PL29ClawShade>();
            if (outline == null) outline = GetComponent<DS38ClawOutline>();
            if (shade != null && !shade.Applied) shade.Apply();
            var mesh = cp.GetComponent<MeshFilter>().sharedMesh;
            int n = mesh.vertexCount;
            // 2) 根元の円の色
            TuftVertices = 0;
            if (tuftBase)
            {
                var uv = new List<Vector2>();
                mesh.GetUVs(2, uv);
                if (uv.Count != n) { uv.Clear(); for (int i = 0; i < n; i++) uv.Add(new Vector2(1f, 0f)); }
                for (int k = 0; k < cp.ClawCount; k++)
                {
                    int o = cp.VertOffset[k], cnt = cp.VertCount[k], st = (cnt - 11) / 8;
                    for (int q = 0; q < 9; q++) { int i = o + 2 + st * 8 + q; uv[i] = new Vector2(tuftShade, 0f); TuftVertices++; }
                }
                mesh.SetUVs(2, uv);
            }
            // 1) 縁の線を根元で開く
            LineVertices = 0;
            if (rootOpen && outline != null)
            {
                outline.Sync();
                var line = outline.Line;
                if (line != null)
                {
                    var lm = line.GetComponent<MeshFilter>().sharedMesh;
                    if (lm != null && lm.vertexCount == n)
                    {
                        var a = new Vector2[n];
                        for (int k = 0; k < cp.ClawCount; k++)
                        {
                            int o = cp.VertOffset[k], cnt = cp.VertCount[k], st = (cnt - 11) / 8;
                            a[o] = new Vector2(0f, 0f);
                            for (int s = 0; s < st; s++)
                                for (int q = 0; q < 8; q++) a[o + 1 + s * 8 + q] = new Vector2(st > 1 ? s / (float)(st - 1) : 1f, q >= 1 && q <= 3 ? 1f : (q >= 5 ? 2f : 0f));
                            a[o + 1 + st * 8] = new Vector2(1f, 0f);
                            for (int q = 0; q < 9; q++) a[o + 2 + st * 8 + q] = new Vector2(-1f, 0f);
                        }
                        lm.SetUVs(3, a);
                        LineVertices = n;
                        var sh = outlineShader != null ? outlineShader : Shader.Find("GreatWave/Polish32/PL32 Claw Outline");
                        if (sh == null) throw new InvalidOperationException("PL32ClawLook：PL32 Claw Outline のシェーダーがありません。");
                        if (lineMat == null || line.sharedMaterial != lineMat)
                        {
                            var src = line.sharedMaterial;
                            lineMat = new Material(sh) { name = "PL32 爪の縁の線（根元で開く）", hideFlags = HideFlags.DontSave, enableInstancing = true };
                            if (src != null) lineMat.CopyPropertiesFromMaterial(src);
                            lineMat.SetVector("_PL32RootFade", new Vector4(rootFade.x, rootFade.y, 0, 0));
                            line.sharedMaterial = lineMat;
                        }
                        appliedLine = lm;
                    }
                }
            }
            appliedClaw = mesh;
            Applied = true;
            if (Application.isPlaying)
                Debug.Log("PL32_CLAW_LOOK_APPLIED tuftVertices=" + TuftVertices + " lineVertices=" + LineVertices + " rootFade=" + rootFade + " tuftShade=" + tuftShade);
        }

        bool NeedsApply
        {
            get
            {
                var cp = Claws;
                if (cp == null || !cp.Loaded) return false;
                if (shade != null && !shade.Applied) return false;   // 陰の段（PL29ClawShade）が先
                if (!Applied || cp.GetComponent<MeshFilter>().sharedMesh != appliedClaw) return true;
                if (rootOpen && outline != null && outline.Line != null)
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
