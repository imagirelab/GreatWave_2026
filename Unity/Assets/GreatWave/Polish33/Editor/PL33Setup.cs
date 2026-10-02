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

namespace GreatWave.Polish33.EditorTools
{
    // 仕上げ33 の組み立て：仕上げ32 の場面 PL32_Release.unity・PL32_SinglePlayback.unity を Polish33/Scenes へ写し（元の場面は読むだけ）、写しの
    //  ・爪の層（DS34ClawPlayer）の並びを、仕上げ33 の爪（Build/Polish/33/claws：原画の爪を射線の向きへ立ち上げた帯 pl33_ray_relief ＋
    //    鉤の内の膜 pl33_hook_web ＋ 頂の裏の冠の爪 pl33_crown。pl33_claw_relief.py → pl33_crown.py）へ
    //  ・爪の物に PL33ClawLook（膜を水色の版の段にし、膜の縁の線を出さない。シェーダー PL33 Claw Outline を場面から参照してビルドに入れる）を足す
    // にする。主役波・海・飛沫・線・爪の材質（PL32_Claw_Shade.mat）・PL32ClawLook・PL32ClawDriver は仕上げ32 のまま。
    // DS34ClawPlayer・DS38ClawOutline・PL32 のファイルと場面は変えない。
    public static class PL33Setup
    {
        public const string SceneRelease32 = "Assets/GreatWave/Polish32/Scenes/PL32_Release.unity";
        public const string SceneSingle32 = "Assets/GreatWave/Polish32/Scenes/PL32_SinglePlayback.unity";
        public const string SceneRelease = "Assets/GreatWave/Polish33/Scenes/PL33_Release.unity";
        public const string SceneSingle = "Assets/GreatWave/Polish33/Scenes/PL33_SinglePlayback.unity";

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
            string clawLayout = Arg("-pl33Claws") ?? "Build/Polish/33/fix02/claws/ds33_claw_layout.json";   // 修正の回 2（pl33f2_white_clip。修正の回 1 は Build/Polish/33/fix01/claws、作る部は Build/Polish/33/claws）
            var outlineShader = Shader.Find("GreatWave/Polish33/PL33 Claw Outline");
            if (outlineShader == null) throw new InvalidOperationException("PL33 Claw Outline のシェーダーがありません");
            if (!File.Exists(Path.GetFullPath(clawLayout))) throw new InvalidOperationException("爪の並びがありません: " + clawLayout);
            var recs = new List<SceneRec>();
            foreach (var (from, to) in new[] { (SceneRelease32, SceneRelease), (SceneSingle32, SceneSingle) })
            {
                var r = new SceneRec { from = from, fromSha256Before = Sha(from), to = to };
                var ch = new List<string>();
                Directory.CreateDirectory(Path.GetDirectoryName(to));
                if (File.Exists(to)) AssetDatabase.DeleteAsset(to);
                if (!AssetDatabase.CopyAsset(from, to)) throw new InvalidOperationException("場面を写せません: " + from);
                var scene = EditorSceneManager.OpenScene(to, OpenSceneMode.Single);
                var roots = scene.GetRootGameObjects();
                var claws = roots.SelectMany(g => g.GetComponentsInChildren<DS34ClawPlayer>(true)).ToList();
                if (claws.Count == 0) ch.Add("爪の層はない（仕上げ32 と同じ）");
                foreach (var cp in claws)
                {
                    ch.Add("爪 " + cp.gameObject.name + " の layoutPath " + cp.layoutPath + " → " + clawLayout +
                           "（仕上げ33 修正の回 1 の爪：原画の爪 184 の低い浮き彫り、鉤の内の膜 184、b区域の房の添え指、稜の房の冠の爪）");
                    cp.layoutPath = clawLayout; EditorUtility.SetDirty(cp);
                    var l33 = cp.GetComponent<GreatWave.Polish33.PL33ClawLook>() ?? cp.gameObject.AddComponent<GreatWave.Polish33.PL33ClawLook>();
                    l33.claws = cp; l33.look32 = cp.GetComponent<GreatWave.Polish32.PL32ClawLook>(); l33.outline = cp.GetComponent<GreatWave.Design38.DS38ClawOutline>();
                    l33.outlineShader = outlineShader;
                    EditorUtility.SetDirty(l33);
                    ch.Add("爪 " + cp.gameObject.name + " に PL33ClawLook（膜を水色の版の段 " + l33.webShade + "、膜の縁の線なし、PL33 Claw Outline）");
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
            var od = Arg("-pl33Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "pl33_setup.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL33_SETUP_DONE " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)));
        }
    }
}
