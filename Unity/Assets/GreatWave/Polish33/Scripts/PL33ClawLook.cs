using System;
using System.Collections.Generic;
using GreatWave.Design34;
using GreatWave.Design38;
using GreatWave.Polish29;
using GreatWave.Polish32;
using UnityEngine;

namespace GreatWave.Polish33
{
    // 仕上げ33（設計33 爪の造形）：爪の層の 3 種類の項目の見え方（どれも帯の頂点の並びと id だけで決まり、視点・原画カメラによらない。Q28）。
    //  ・原画の爪（id C…、pl33_ray_relief で面から立ち上げた帯）と冠の爪（id K…、pl33_crown）：PL29 Claw Shade の段（上面 白、縁と下面 水色の版）と
    //    PL32ClawLook の縁の線（根元で開く）のまま。
    //  ・鉤の内の膜（id W…、pl33_hook_web）：全部の頂点の UV2.x を水色の版の段（webShade、既定 0.0）にし、縁の線のメッシュの UV3.x を −1 にする。
    //    縁の線の材質は PL33 Claw Outline（UV3.x が −1 の頂点を含む三角形を押し出さない）に替える（膜は薄い 2 面の帯で、線を出すと z の争いになる）。
    //  ・房の添え指（id S…p／S…m、仕上げ33 修正の回 1 の pl33f_tuft_fingers）：親の帯に向く側の半分の輪の頂点（…p は 3〜5、…m は 7・0・1）の
    //    縁の線のメッシュの UV3.x を −1 にする（pl33f_tuft_halfline：添え指と親の線が交わって閉じた輪にならず、外の縁だけに線が出る）。
    // Play モードでは PL32ClawLook（順 130）の後の LateUpdate で付ける。Editor の道具は Apply() を呼ぶ。
    [DefaultExecutionOrder(135)]
    public class PL33ClawLook : MonoBehaviour
    {
        public DS34ClawPlayer claws;
        public PL32ClawLook look32;
        public DS38ClawOutline outline;
        [Tooltip("PL33 Claw Outline のシェーダー（場面から参照してビルドに入れる）")] public Shader outlineShader;
        [Tooltip("膜の UV2.x（PL29 Claw Shade の段：_Steps.y < x ≤ _Steps.x で水色の版）")] public float webShade = 0.0f;
        [Tooltip("膜の id の頭の文字")] public string webPrefix = "W";
        [Tooltip("房の添え指の id の頭の文字（末尾 p／m で線を描かない半分を決める）")] public string tuftPrefix = "S";

        public bool Applied { get; private set; }
        public int WebEntries { get; private set; }
        public int WebVertices { get; private set; }
        public int CrownEntries { get; private set; }
        public int TuftEntries { get; private set; }
        Mesh appliedClaw, appliedLine;
        Material lineMat;

        DS34ClawPlayer Claws => claws != null ? claws : (claws = GetComponent<DS34ClawPlayer>());

        public void Apply()
        {
            var cp = Claws;
            if (cp == null) throw new InvalidOperationException("PL33ClawLook：DS34ClawPlayer がありません。");
            cp.Load();
            if (look32 == null) look32 = GetComponent<PL32ClawLook>();
            if (outline == null) outline = GetComponent<DS38ClawOutline>();
            if (look32 != null && !look32.Applied) look32.Apply();
            var mesh = cp.GetComponent<MeshFilter>().sharedMesh;
            int n = mesh.vertexCount;
            var web = new bool[cp.ClawCount];
            var tuftSide = new int[cp.ClawCount];   // 0 なし、+1 …p（頂点 3〜5 の側を描かない）、−1 …m（7・0・1 の側）
            WebEntries = 0; WebVertices = 0; CrownEntries = 0; TuftEntries = 0;
            for (int k = 0; k < cp.ClawCount; k++)
            {
                var id = cp.ClawIds[k] ?? "";
                if (id.StartsWith(webPrefix, StringComparison.Ordinal)) { web[k] = true; WebEntries++; WebVertices += cp.VertCount[k]; }
                else if (id.StartsWith("K", StringComparison.Ordinal)) CrownEntries++;
                else if (!string.IsNullOrEmpty(tuftPrefix) && id.StartsWith(tuftPrefix, StringComparison.Ordinal) && id.Length > 1)
                {
                    char e = id[id.Length - 1];
                    tuftSide[k] = e == 'p' ? 1 : (e == 'm' ? -1 : 0);
                    if (tuftSide[k] != 0) TuftEntries++;
                }
            }
            // 膜の色（UV2.x）
            var uv = new List<Vector2>();
            mesh.GetUVs(2, uv);
            if (uv.Count != n) { uv.Clear(); for (int i = 0; i < n; i++) uv.Add(new Vector2(1f, 0f)); }
            for (int k = 0; k < cp.ClawCount; k++)
            {
                if (!web[k]) continue;
                int o = cp.VertOffset[k], cnt = cp.VertCount[k];
                for (int i = 0; i < cnt; i++) uv[o + i] = new Vector2(webShade, uv[o + i].y);
            }
            mesh.SetUVs(2, uv);
            // 膜の縁の線を出さない
            if (outline != null)
            {
                outline.Sync();
                var line = outline.Line;
                if (line != null)
                {
                    var lm = line.GetComponent<MeshFilter>().sharedMesh;
                    if (lm != null && lm.vertexCount == n)
                    {
                        var a3 = new List<Vector2>();
                        lm.GetUVs(3, a3);
                        if (a3.Count != n) { a3.Clear(); for (int i = 0; i < n; i++) a3.Add(new Vector2(1f, 0f)); }
                        for (int k = 0; k < cp.ClawCount; k++)
                        {
                            if (web[k])
                            {
                                int o = cp.VertOffset[k], cnt = cp.VertCount[k];
                                for (int i = 0; i < cnt; i++) a3[o + i] = new Vector2(-1f, 0f);
                            }
                            else if (tuftSide[k] != 0)
                            {
                                // 頂点の並び（設計33）：根元 1・輪 stations × 8・先 1・根元の円の中心 1・円 8
                                int o = cp.VertOffset[k], cnt = cp.VertCount[k];
                                int st = (cnt - 11) / 8;
                                for (int j = 0; j < st; j++)
                                    for (int i = 0; i < 8; i++)
                                    {
                                        bool hide = tuftSide[k] > 0 ? (i >= 3 && i <= 5) : (i == 7 || i == 0 || i == 1);
                                        if (hide) a3[o + 1 + j * 8 + i] = new Vector2(-1f, a3[o + 1 + j * 8 + i].y);
                                    }
                            }
                        }
                        lm.SetUVs(3, a3);
                        var sh = outlineShader != null ? outlineShader : Shader.Find("GreatWave/Polish33/PL33 Claw Outline");
                        if (sh == null) throw new InvalidOperationException("PL33ClawLook：PL33 Claw Outline のシェーダーがありません。");
                        if (lineMat == null || line.sharedMaterial != lineMat)
                        {
                            var src = line.sharedMaterial;
                            lineMat = new Material(sh) { name = "PL33 爪の縁の線（膜は線なし）", hideFlags = HideFlags.DontSave, enableInstancing = true };
                            if (src != null) lineMat.CopyPropertiesFromMaterial(src);
                            line.sharedMaterial = lineMat;
                        }
                        appliedLine = lm;
                    }
                }
            }
            appliedClaw = mesh;
            Applied = true;
            if (Application.isPlaying)
                Debug.Log("PL33_CLAW_LOOK_APPLIED webEntries=" + WebEntries + " webVertices=" + WebVertices + " crownEntries=" + CrownEntries + " tuftEntries=" + TuftEntries + " webShade=" + webShade);
        }

        bool NeedsApply
        {
            get
            {
                var cp = Claws;
                if (cp == null || !cp.Loaded) return false;
                if (look32 != null && !look32.Applied) return false;   // PL32ClawLook が先
                if (!Applied || cp.GetComponent<MeshFilter>().sharedMesh != appliedClaw) return true;
                if (outline != null && outline.Line != null)
                {
                    var lm = outline.Line.GetComponent<MeshFilter>().sharedMesh;
                    if (lm != null && lm != appliedLine) return true;
                    if (lineMat != null && outline.Line.sharedMaterial != lineMat) return true;
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
