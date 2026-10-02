using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design34;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Polish33R01H.EditorTools
{
    // 仕上げ33修正01（Houdini の変種）の組み立て：仕上げ33 の場面 PL33_Release.unity・PL33_SinglePlayback.unity を Polish33R01/houdini/Scenes へ写し
    // （元の場面は読むだけ）、写しの爪の層（DS34ClawPlayer）の並びを立つ白い爪の指（Build/Polish/33r01/houdini/claws）にし、帯の輪の並びを前提にする
    // PL29ClawShade・PL32ClawLook・PL33ClawLook を外して PL33R01HClawLook（同じ PL29 Claw Shade の材質、PL32 Claw Outline）を足す。
    // 主役波・海・飛沫・線・PL32ClawDriver・DS38ClawOutline は仕上げ33 のまま。PL33 までのファイルと場面は変えない。
    public static class PL33R01HSetup
    {
        public const string SceneRelease33 = "Assets/GreatWave/Polish33/Scenes/PL33_Release.unity";
        public const string SceneSingle33 = "Assets/GreatWave/Polish33/Scenes/PL33_SinglePlayback.unity";
        public const string SceneRelease = "Assets/GreatWave/Polish33R01/houdini/Scenes/PL33R01H_Release.unity";
        public const string SceneSingle = "Assets/GreatWave/Polish33R01/houdini/Scenes/PL33R01H_SinglePlayback.unity";

        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        static string Sha(string path)
        {
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        [Serializable] class SceneRec { public string from, fromSha256Before, fromSha256After, to, toSha256; public string[] changesJa; }
        [Serializable] class Report { public string utc, unity, clawLayout, clawLayoutSha256, outlineShader; public SceneRec[] scenes; }

        public static void BuildScenes()
        {
            string clawLayout = Arg("-pl33r01hClaws") ?? "Build/Polish/33r01/houdini/claws/ds33_claw_layout.json";
            var outlineShader = Shader.Find("GreatWave/Polish32/PL32 Claw Outline");
            if (outlineShader == null) throw new InvalidOperationException("PL32 Claw Outline のシェーダーがありません");
            if (!File.Exists(Path.GetFullPath(clawLayout))) throw new InvalidOperationException("爪の並びがありません: " + clawLayout);
            var recs = new List<SceneRec>();
            foreach (var (from, to) in new[] { (SceneRelease33, SceneRelease), (SceneSingle33, SceneSingle) })
            {
                var r = new SceneRec { from = from, fromSha256Before = Sha(from), to = to };
                var ch = new List<string>();
                Directory.CreateDirectory(Path.GetDirectoryName(to));
                if (File.Exists(to)) AssetDatabase.DeleteAsset(to);
                if (!AssetDatabase.CopyAsset(from, to)) throw new InvalidOperationException("場面を写せません: " + from);
                var scene = EditorSceneManager.OpenScene(to, OpenSceneMode.Single);
                var roots = scene.GetRootGameObjects();
                var claws = roots.SelectMany(g => g.GetComponentsInChildren<DS34ClawPlayer>(true)).ToList();
                if (claws.Count == 0) ch.Add("爪の層はない（仕上げ33 と同じ）");
                foreach (var cp in claws)
                {
                    ch.Add("爪 " + cp.gameObject.name + " の layoutPath " + cp.layoutPath + " → " + clawLayout + "（立つ白い爪の指、Houdini）");
                    cp.layoutPath = clawLayout; EditorUtility.SetDirty(cp);
                    Material mat = null;
                    var shade = cp.GetComponent<GreatWave.Polish29.PL29ClawShade>();
                    if (shade != null) { mat = shade.material; UnityEngine.Object.DestroyImmediate(shade, true); ch.Add("PL29ClawShade を外した（材質 " + (mat != null ? mat.name : "なし") + " は PL33R01HClawLook へ）"); }
                    var l32 = cp.GetComponent<GreatWave.Polish32.PL32ClawLook>();
                    if (l32 != null) { UnityEngine.Object.DestroyImmediate(l32, true); ch.Add("PL32ClawLook を外した"); }
                    var l33 = cp.GetComponent<GreatWave.Polish33.PL33ClawLook>();
                    if (l33 != null) { UnityEngine.Object.DestroyImmediate(l33, true); ch.Add("PL33ClawLook を外した"); }
                    var hl = cp.GetComponent<PL33R01HClawLook>() ?? cp.gameObject.AddComponent<PL33R01HClawLook>();
                    hl.claws = cp; hl.material = mat ?? AssetDatabase.LoadAssetAtPath<Material>("Assets/GreatWave/Polish29/Materials/PL29_Claw_Shade.mat");
                    hl.outline = cp.GetComponent<GreatWave.Design38.DS38ClawOutline>(); hl.outlineShader = outlineShader; hl.rootFade = new Vector2(0.20f, 0.60f);
                    EditorUtility.SetDirty(hl);
                    ch.Add("爪 " + cp.gameObject.name + " に PL33R01HClawLook（材質 " + (hl.material != null ? hl.material.name : "なし") + "、PL32 Claw Outline）");
                }
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                r.changesJa = ch.ToArray(); r.toSha256 = Sha(to); r.fromSha256After = Sha(from);
                recs.Add(r);
            }
            AssetDatabase.SaveAssets();
            var rep = new Report
            {
                utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, clawLayout = clawLayout, clawLayoutSha256 = Sha(Path.GetFullPath(clawLayout)),
                outlineShader = outlineShader.name, scenes = recs.ToArray()
            };
            var od = Arg("-pl33r01hOut") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r01/houdini/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "pl33r01h_setup.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL33R01H_SETUP_DONE " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)));
        }
    }
}
