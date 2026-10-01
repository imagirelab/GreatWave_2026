using System;
using System.Collections.Generic;
using GreatWave.Design34;
using UnityEngine;

namespace GreatWave.Polish29
{
    // 仕上げ29 修正の回（Q28）：立体の爪（設計34 の DS34ClawPlayer の結合メッシュ）に、視点によらない陰の段を付ける。
    //  1) 頂点の UV2（TEXCOORD2）= (sin φ, 帯の根元 0 → 先 1) を、設計33 の頂点の並び（爪ごとに 根元 1・輪 stations × 8（φ = 0, 45, …, 315°）・先 1・根元の白の円 9）
    //     から入れる。φ 90° が上（シートの法線の向き）、270° が下面。根元・根元の白の円は上（白）、先は 0（側面）とする。
    //     DS34ClawPlayer.ApplyT は SetVertices だけなので、入れた UV2 はコマを替えても残る。
    //  2) 爪のレンダラーの 2 つの材質を material（PL29 Claw Shade）にする（白・淡い水色・藍中の段はシェーダーが UV2.x で決める）。
    //  3) 設計38 の爪の縁の線（DS38 爪の縁の線）を、原画視点でも描く（MaterialPropertyBlock で _DS38PaintFade を (0,0) にし、原画のカメラからの離れの重みを 1 にする）。
    //     設計38 は、原画視点では焼き込みの色面が線を担うとして爪の線を消していた。仕上げ29 で焼き込みをやめたので、どの視点でも同じ線にする。
    // 原画カメラからの投影は使わない。Play モードでは、爪が読み込まれた後の LateUpdate で付ける。Editor の道具は Apply() を呼ぶ。
    [DefaultExecutionOrder(125)]
    public class PL29ClawShade : MonoBehaviour
    {
        [Tooltip("爪の結合メッシュ（空なら同じ物の DS34ClawPlayer）")] public DS34ClawPlayer claws;
        [Tooltip("PL29 Claw Shade の材質")] public Material material;
        [Tooltip("爪の縁の線を原画視点でも描く")] public bool linesEverywhere = true;
        public const string LineChildName = "DS38 爪の縁の線";

        public bool Applied { get; private set; }
        public int ShadedVertices { get; private set; }
        public int[] VertexClassCounts { get; } = new int[3];   // 上（白）・側面（淡い水色）・下面（藍中）の頂点の数（既定の段の境で数える。記録用）
        Material[] previous;
        Mesh appliedMesh;
        MeshRenderer lineR;
        MaterialPropertyBlock mpb;

        public DS34ClawPlayer Claws => claws != null ? claws : (claws = GetComponent<DS34ClawPlayer>());

        public void Apply()
        {
            var cp = Claws;
            if (cp == null) throw new InvalidOperationException("PL29ClawShade：DS34ClawPlayer がありません。");
            cp.Load();
            var mesh = cp.GetComponent<MeshFilter>().sharedMesh;
            if (mesh == null) throw new InvalidOperationException("PL29ClawShade：爪のメッシュがありません。");
            int n = mesh.vertexCount;
            var att = new Vector2[n];
            for (int i = 0; i < n; i++) att[i] = new Vector2(1f, 0f);
            Array.Clear(VertexClassCounts, 0, 3);
            for (int k = 0; k < cp.ClawCount; k++)
            {
                int o = cp.VertOffset[k], cnt = cp.VertCount[k];
                int st = (cnt - 11) / 8;
                if (st * 8 + 11 != cnt) throw new InvalidOperationException("PL29ClawShade：爪 " + cp.ClawIds[k] + " の頂点の数が 8·stations + 11 でない: " + cnt);
                att[o] = new Vector2(1f, 0f);                                     // 根元の点（白）
                for (int s = 0; s < st; s++)
                    for (int q = 0; q < 8; q++)
                    {
                        float phi = q * 45f * Mathf.Deg2Rad;
                        att[o + 1 + s * 8 + q] = new Vector2(Mathf.Sin(phi), st > 1 ? s / (float)(st - 1) : 0f);
                    }
                att[o + 1 + st * 8] = new Vector2(0f, 1f);                          // 先
                for (int q = 0; q < 9; q++) att[o + 2 + st * 8 + q] = new Vector2(1f, 0f);   // 根元の白の円（中心と 8 点）
            }
            foreach (var v in att) VertexClassCounts[v.x > 0.30f ? 0 : (v.x > -0.45f ? 1 : 2)]++;
            mesh.SetUVs(2, new List<Vector2>(att));
            ShadedVertices = n;
            var r = cp.GetComponent<MeshRenderer>();
            if (material != null)
            {
                var cur = r.sharedMaterials;
                if (previous == null) previous = cur;
                var mats = new Material[Math.Max(1, cur.Length)];
                for (int i = 0; i < mats.Length; i++) mats[i] = material;
                r.sharedMaterials = mats;
            }
            ApplyLines();
            appliedMesh = mesh;
            Applied = true;
            if (Application.isPlaying)
                Debug.Log("PL29_CLAW_SHADE_APPLIED vertices=" + n + " classes=" + VertexClassCounts[0] + "/" + VertexClassCounts[1] + "/" + VertexClassCounts[2] +
                          " shader=" + (material != null ? material.shader.name : "") + " linesEverywhere=" + linesEverywhere + " lineRenderer=" + (lineR != null));
        }

        void ApplyLines()
        {
            var cp = Claws;
            if (!linesEverywhere || cp == null) return;
            var tr = cp.transform.Find(LineChildName);
            lineR = tr != null ? tr.GetComponent<MeshRenderer>() : null;
            if (lineR == null) return;
            if (mpb == null) mpb = new MaterialPropertyBlock();
            lineR.GetPropertyBlock(mpb);
            mpb.SetVector("_DS38PaintFade", Vector4.zero);   // y ≤ x：原画のカメラからの離れの重みはいつも 1（DS38LineCommon.cginc の DS38PaintWeight）
            lineR.SetPropertyBlock(mpb);
        }

        /// <summary>材質と線を元へ戻す（Editor の道具の後始末）。</summary>
        public void Revert()
        {
            var cp = Claws;
            if (cp != null && previous != null) cp.GetComponent<MeshRenderer>().sharedMaterials = previous;
            previous = null;
            if (lineR != null) lineR.SetPropertyBlock(null);
            Applied = false;
        }

        bool NeedsApply
        {
            get
            {
                var cp = Claws;
                if (cp == null || !cp.Loaded) return false;
                var mf = cp.GetComponent<MeshFilter>();
                if (!Applied || mf.sharedMesh != appliedMesh) return true;
                var r = cp.GetComponent<MeshRenderer>();
                return material != null && r.sharedMaterial != material;
            }
        }

        void LateUpdate()
        {
            if (!Application.isPlaying) return;
            if (NeedsApply) Apply();
            else if (linesEverywhere && lineR == null) ApplyLines();
        }
    }
}
