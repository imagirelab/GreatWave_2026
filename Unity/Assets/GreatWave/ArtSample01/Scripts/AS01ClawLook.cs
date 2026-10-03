using System;
using System.Collections.Generic;
using GreatWave.Design34;
using GreatWave.Design38;
using UnityEngine;

namespace GreatWave.ArtSample01
{
    // 美術の見本01（Q29）改善の回 1（2026-10-03、美術監督の項目 1）：爪の層のうち id が noLinePrefix（既定 "U"）で始まる項目（爪の泡の塊、
    // as01_claw_foam）の縁の線を描かない。縁の線のメッシュ（設計38 の DS38 爪の縁の線、材質は PL33 Claw Outline）の UV3.x を −1 にする
    // （PL33 Claw Outline は UV3.x が −1 の頂点を含む三角形を押し出さない。PL33ClawLook が膜 W… に行うことと同じで、色は変えない）。
    // 泡の塊は白い板のまま隣の塊と線なしでつながり、白い泡の帯になる。鉤の指（縁の線あり）がその上と縁に墨の線で描かれる（原画の爪の輪の見え方）。
    // 色も形も頂点の id だけで決まり、視点・原画カメラによらない（Q28）。Play モードでは PL33ClawLook（順 135）の後の LateUpdate で付ける。
    [DefaultExecutionOrder(136)]
    public class AS01ClawLook : MonoBehaviour
    {
        public DS34ClawPlayer claws;
        public DS38ClawOutline outline;
        [Tooltip("縁の線を描かない項目の id の頭の文字")] public string noLinePrefix = "U";
        // 改善の回 2（2026-10-03）：場面の写しで、描画の道具の -as01ClawLineColor と同じく爪の縁の線の色を替える（既定は替えない）
        [Tooltip("爪の縁の線の色を lineColor にする（描画の道具の -as01ClawLineColor と同じ。sRGB の 0〜1）")] public bool setLineColor = false;
        public Color lineColor = new Color(31f / 255f, 60f / 255f, 94f / 255f, 1f);

        public bool Applied { get; private set; }
        public int NoLineEntries { get; private set; }
        public int NoLineVertices { get; private set; }
        Mesh appliedLine;

        DS34ClawPlayer Claws => claws != null ? claws : (claws = GetComponent<DS34ClawPlayer>());

        public void Apply()
        {
            var cp = Claws;
            if (cp == null) throw new InvalidOperationException("AS01ClawLook：DS34ClawPlayer がありません。");
            cp.Load();
            if (outline == null) outline = GetComponent<DS38ClawOutline>();
            if (outline == null) throw new InvalidOperationException("AS01ClawLook：DS38ClawOutline がありません。");
            outline.Sync();
            var line = outline.Line;
            if (line == null) return;
            var lm = line.GetComponent<MeshFilter>().sharedMesh;
            int n = cp.VertexCount;
            if (lm == null || lm.vertexCount != n) return;
            var a3 = new List<Vector2>();
            lm.GetUVs(3, a3);
            if (a3.Count != n) { a3.Clear(); for (int i = 0; i < n; i++) a3.Add(new Vector2(1f, 0f)); }
            NoLineEntries = 0; NoLineVertices = 0;
            for (int k = 0; k < cp.ClawCount; k++)
            {
                var id = cp.ClawIds[k] ?? "";
                if (string.IsNullOrEmpty(noLinePrefix) || !id.StartsWith(noLinePrefix, StringComparison.Ordinal)) continue;
                int o = cp.VertOffset[k], cnt = cp.VertCount[k];
                for (int i = 0; i < cnt; i++) a3[o + i] = new Vector2(-1f, a3[o + i].y);
                NoLineEntries++; NoLineVertices += cnt;
            }
            lm.SetUVs(3, a3);
            var lmat = line.sharedMaterial;
            if (setLineColor && lmat != null && lmat.HasProperty("_LineColor")) lmat.SetColor("_LineColor", lineColor);
            appliedLine = lm;
            Applied = true;
            if (Application.isPlaying) Debug.Log("AS01_CLAW_LOOK_APPLIED noLineEntries=" + NoLineEntries + " noLineVertices=" + NoLineVertices + " prefix=" + noLinePrefix);
        }

        void LateUpdate()
        {
            if (!Application.isPlaying) return;
            var cp = Claws;
            if (cp == null || !cp.Loaded || outline == null || outline.Line == null) return;
            var l33 = GetComponent<GreatWave.Polish33.PL33ClawLook>();
            if (l33 != null && !l33.Applied) return;   // PL33ClawLook が先（膜の UV3 を入れた後）
            var lm = outline.Line.GetComponent<MeshFilter>().sharedMesh;
            if (!Applied || lm != appliedLine || (setLineColor && outline.Line.sharedMaterial != null && outline.Line.sharedMaterial.HasProperty("_LineColor")
                                                  && outline.Line.sharedMaterial.GetColor("_LineColor") != lineColor)) Apply();
        }
    }
}
