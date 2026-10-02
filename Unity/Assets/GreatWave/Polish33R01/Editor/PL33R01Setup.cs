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

namespace GreatWave.Polish33R01.EditorTools
{
    // 仕上げ33修正01（修正の回 1 の後の採る状態）の組み立て：仕上げ33 の場面 PL33_Release.unity・PL33_SinglePlayback.unity を Polish33R01/Scenes へ写し（元の場面は読むだけ）、
    // 写しの爪の層（DS34ClawPlayer）の並びを、仕上げ33修正01 の爪（Build/Polish/33r01/fix01/claws：変種 SWEEP の立つ 3D の指を評審の 11 の指摘で作り直したもの。
    // 原画の爪 184（4 本は消した）・指の鉤の内の膜 WF… 180・仕上げ33 の鉤の内の膜 WC… 180・冠の爪 137（低い房 10 本は消した）。Tools/GWWaveGen/pl33r01/r01_build.py）にする。
    // PL33ClawLook・PL32ClawLook・PL32ClawDriver・PL29ClawShade・材質は仕上げ33 のまま（膜は id の頭 W で水色の版・線なし）。仕上げ33 までのファイルと場面、
    // 変種の場面（Polish33R01/sweep・houdini）は変えない。
    public static class PL33R01Setup
    {
        public const string SceneRelease33 = "Assets/GreatWave/Polish33/Scenes/PL33_Release.unity";
        public const string SceneSingle33 = "Assets/GreatWave/Polish33/Scenes/PL33_SinglePlayback.unity";
        public const string SceneRelease = "Assets/GreatWave/Polish33R01/Scenes/PL33R01_Release.unity";
        public const string SceneSingle = "Assets/GreatWave/Polish33R01/Scenes/PL33R01_SinglePlayback.unity";
        public const string DefaultClaws = "Build/Polish/33r01/fix01/claws/ds33_claw_layout.json";

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
        [Serializable] class Report { public string utc, unity, clawLayout, clawLayoutSha256; public SceneRec[] scenes; }

        public static void BuildScenes()
        {
            string clawLayout = Arg("-pl33r01Claws") ?? DefaultClaws;
            if (!File.Exists(Path.GetFullPath(clawLayout))) throw new InvalidOperationException("爪の並びがありません: " + clawLayout);
            var recs = new List<SceneRec>();
            foreach (var (from, to) in new[] { (SceneRelease33, SceneRelease), (SceneSingle33, SceneSingle) })
            {
                var r = new SceneRec { from = from, fromSha256Before = Sha(from), to = to };
                var ch = new List<string>();
                Directory.CreateDirectory(Path.GetDirectoryName(to));
                AssetDatabase.Refresh();
                if (File.Exists(to)) AssetDatabase.DeleteAsset(to);
                if (!AssetDatabase.CopyAsset(from, to)) throw new InvalidOperationException("場面を写せません: " + from);
                var scene = EditorSceneManager.OpenScene(to, OpenSceneMode.Single);
                var claws = scene.GetRootGameObjects().SelectMany(g => g.GetComponentsInChildren<DS34ClawPlayer>(true)).ToList();
                if (claws.Count == 0) ch.Add("爪の層はない（仕上げ33 と同じ）");
                foreach (var cp in claws)
                {
                    ch.Add("爪 " + cp.gameObject.name + " の layoutPath " + cp.layoutPath + " → " + clawLayout + "（仕上げ33修正01：立つ 3D の指・膜・冠の爪）");
                    cp.layoutPath = clawLayout; EditorUtility.SetDirty(cp);
                }
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                r.changesJa = ch.ToArray(); r.toSha256 = Sha(to); r.fromSha256After = Sha(from);
                recs.Add(r);
            }
            AssetDatabase.SaveAssets();
            var rep = new Report { utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, clawLayout = clawLayout, clawLayoutSha256 = Sha(Path.GetFullPath(clawLayout)), scenes = recs.ToArray() };
            var od = Arg("-pl33r01Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r01/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "pl33r01_setup.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL33R01_SETUP_DONE " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)));
        }
    }
}
