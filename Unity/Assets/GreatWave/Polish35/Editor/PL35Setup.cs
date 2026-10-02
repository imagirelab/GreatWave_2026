using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design46;
using GreatWave.Design47;
using GreatWave.Design50;
using GreatWave.Polish32;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Polish35.EditorTools
{
    // 仕上げ35（数量と負荷）の組み立て：仕上げ33修正01 の場面 PL33R01_Release.unity・PL33R01_SinglePlayback.unity を Polish35/Scenes へ写す（元の場面は読むだけ）。
    //   ・PL35_Release.unity：負荷の計測器 PL35PerfProbe（起動引数 --pl35perf の時だけ働く。無ければ何もしない）を足す。
    //     -pl35fix 1 のとき、修正の回の部品 PL35ClawOutlineFast（爪の縁の線の写しを、毎コマの配列の写しと法線の作り直しの代わりに、
    //     コマの表から前もって作った法線の補間で行う）を爪の層へ足す（-pl35fix 0 なら足さない＝仕上げ33修正01 と同じ仕事）。
    //   ・PL35_SinglePlayback.unity：中身は変えない（この群の次の群が続ける場面）。
    // 仕上げ33修正01 までの場面とファイルは変えない。
    public static class PL35Setup
    {
        public const string SceneRelease33 = "Assets/GreatWave/Polish33R01/Scenes/PL33R01_Release.unity";
        public const string SceneSingle33 = "Assets/GreatWave/Polish33R01/Scenes/PL33R01_SinglePlayback.unity";
        public const string SceneRelease = "Assets/GreatWave/Polish35/Scenes/PL35_Release.unity";
        public const string SceneSingle = "Assets/GreatWave/Polish35/Scenes/PL35_SinglePlayback.unity";
        public const string Claws = "Build/Polish/33r01/fix01/claws/ds33_claw_layout.json";

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
        [Serializable] class Report { public string utc, unity; public int fix; public SceneRec[] scenes; }

        public static void BuildScenes()
        {
            int fix = int.Parse(Arg("-pl35fix") ?? "0");
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
                if (to == SceneRelease)
                {
                    var roots = scene.GetRootGameObjects();
                    var shell = roots.SelectMany(g => g.GetComponentsInChildren<DS50Shell>(true)).FirstOrDefault();
                    var flow = roots.SelectMany(g => g.GetComponentsInChildren<DS47Flow>(true)).FirstOrDefault();
                    var bus = roots.SelectMany(g => g.GetComponentsInChildren<DS46ClockBus>(true)).FirstOrDefault();
                    var drv = roots.SelectMany(g => g.GetComponentsInChildren<PL32ClawDriver>(true)).FirstOrDefault();
                    if (shell == null || flow == null || bus == null || drv == null) throw new InvalidOperationException("場面に DS50Shell・DS47Flow・DS46ClockBus・PL32ClawDriver のどれかがない");
                    var go = new GameObject("PL35 負荷の計測器（--pl35perf の時だけ）");
                    var pr = go.AddComponent<PL35PerfProbe>();
                    pr.shell = shell; pr.flow = flow; pr.clock = flow.clock; pr.bus = bus; pr.clawDriver = drv;
                    ch.Add("PL35PerfProbe を足した（--pl35perf の時だけ働く）");
                    if (fix == 1)
                    {
                        var cp = bus.claws;
                        var fast = cp.gameObject.GetComponent<PL35ClawOutlineFast>() ?? cp.gameObject.AddComponent<PL35ClawOutlineFast>();
                        fast.claws = cp; fast.outline = bus.clawLine; fast.driver = drv;
                        EditorUtility.SetDirty(fast);
                        ch.Add("修正の回 1：爪 " + cp.gameObject.name + " へ PL35ClawOutlineFast を足した（縁の線の法線をコマの表から前もって作り、毎コマは補間して入れる）");
                    }
                }
                else ch.Add("中身は変えない（仕上げ33修正01 の場面の写し）");
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                r.changesJa = ch.ToArray(); r.toSha256 = Sha(to); r.fromSha256After = Sha(from);
                recs.Add(r);
            }
            AssetDatabase.SaveAssets();
            var rep = new Report { utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, fix = fix, scenes = recs.ToArray() };
            var od = Arg("-pl35Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/35/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "pl35_setup_fix" + fix + ".json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL35_SETUP_DONE fix=" + fix + " " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)));
        }
    }
}
