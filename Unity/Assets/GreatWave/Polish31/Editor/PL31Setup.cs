using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design30;
using GreatWave.Design31;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Polish31.EditorTools
{
    // 仕上げ31 の組み立て：仕上げ30 の場面 PL30_Release.unity・PL30_SinglePlayback.unity を Polish31/Scenes へ写し（元の場面は読むだけ）、写しの
    //  ・主役波のパッケージを、T_white だけ差し替えた hero_pkg（pl31_white.py。位置・精度の層は G_p28rec の art_on と同じバイト）へ
    //  ・飛沫（DS31 spray）を仕上げ31 の白・生成りの段（pl31_spray_tone0_frames.json）へ、灰の白の段（pl31_spray_tone1_frames.json）を 2 つ目の
    //    DS31InstancedParticles で足す（DS46ClockBus の sprays の一覧に加え、入切は PL31SprayFollow で 1 つ目に合わせる）
    // にする。海・爪・線・材質は仕上げ30 のまま。設計39 の密な飛沫（既定は切）は設計31 の古い飛沫の子なので、そのまま切で残す。
    public static class PL31Setup
    {
        public const string SceneRelease30 = "Assets/GreatWave/Polish30/Scenes/PL30_Release.unity";
        public const string SceneSingle30 = "Assets/GreatWave/Polish30/Scenes/PL30_SinglePlayback.unity";
        public const string SceneRelease = "Assets/GreatWave/Polish31/Scenes/PL31_Release.unity";
        public const string SceneSingle = "Assets/GreatWave/Polish31/Scenes/PL31_SinglePlayback.unity";

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
        [Serializable] class Report { public string utc, unity, heroPkg, heroTwhiteSha256, sprayDir; public string[] sprayFiles; public SceneRec[] scenes; }

        public static void BuildScenes()
        {
            string heroPkg = Arg("-pl31HeroPkg") ?? "Build/Polish/31/white/hero_pkg";
            string sprayDir = Arg("-pl31Spray") ?? "Build/Polish/31/spray";
            string tone0 = sprayDir + "/pl31_spray_tone0_frames.json", tone1 = sprayDir + "/pl31_spray_tone1_frames.json";
            if (!File.Exists(Path.GetFullPath(Path.Combine(heroPkg, "ds27_keypose.json")))) throw new InvalidOperationException("hero_pkg がありません: " + heroPkg);
            if (!File.Exists(Path.GetFullPath(tone0))) throw new InvalidOperationException("飛沫のデータがありません: " + tone0);
            var recs = new List<SceneRec>();
            foreach (var (from, to) in new[] { (SceneRelease30, SceneRelease), (SceneSingle30, SceneSingle) })
            {
                var r = new SceneRec { from = from, fromSha256Before = Sha(from), to = to };
                var ch = new List<string>();
                Directory.CreateDirectory(Path.GetDirectoryName(to));
                if (File.Exists(to)) AssetDatabase.DeleteAsset(to);
                if (!AssetDatabase.CopyAsset(from, to)) throw new InvalidOperationException("場面を写せません: " + from);
                var scene = EditorSceneManager.OpenScene(to, OpenSceneMode.Single);
                var roots = scene.GetRootGameObjects();
                var play = roots.SelectMany(g => g.GetComponentsInChildren<DS30SinglePlayback>(true)).Single();
                var hero = play.sheets.First(s => s != null && s.sheetName == "hero");
                ch.Add("主役波 packageDir " + hero.packageDir + " → " + heroPkg + "（T_white だけ差し替え。修正01：pl31_white_order（patch）・pl31_white_claw_pin。pl31_white_rate_cap は 2% を越える時だけ掛かり、修正01 では掛からなかった）");
                hero.packageDir = heroPkg; EditorUtility.SetDirty(hero);
                var spray = roots.SelectMany(g => g.GetComponentsInChildren<DS31InstancedParticles>(true)).FirstOrDefault(p => p.name == "DS31 spray");
                if (spray != null)
                {
                    ch.Add("飛沫 DS31 spray の dataPath " + spray.dataPath + " → " + tone0 + "（白・生成り、色は JSON）");
                    spray.dataPath = tone0; spray.colourFromJson = true; EditorUtility.SetDirty(spray);
                    if (File.Exists(Path.GetFullPath(tone1)))
                    {
                        var go = new GameObject("PL31 spray tone1（灰の白）");
                        go.transform.SetParent(spray.transform.parent, false);
                        var sp1 = go.AddComponent<DS31InstancedParticles>();
                        sp1.dataPath = tone1; sp1.colourFromJson = true; sp1.subdivisions = spray.subdivisions; sp1.clock = spray.clock;
                        sp1.drawInPlayMode = spray.drawInPlayMode; sp1.followClockInPlayMode = spray.followClockInPlayMode; sp1.verifySha256 = spray.verifySha256;
                        var fol = go.AddComponent<PL31SprayFollow>();
                        fol.main = spray; fol.follow = new List<DS31InstancedParticles> { sp1 };
                        EditorUtility.SetDirty(go);
                        ch.Add("灰の白の段を 2 つ目の DS31InstancedParticles（" + tone1 + "）で足し、入切を PL31SprayFollow で 1 つ目に合わせた");
                        foreach (var bus in roots.SelectMany(g => g.GetComponentsInChildren<GreatWave.Design46.DS46ClockBus>(true)))
                        {
                            if (bus.sprays.Contains(spray) && !bus.sprays.Contains(sp1)) { bus.sprays.Add(sp1); EditorUtility.SetDirty(bus); ch.Add("DS46ClockBus の sprays に灰の白の段を加えた：" + bus.gameObject.name); }
                        }
                    }
                }
                else ch.Add("飛沫の層はない（単発再生の場面）");
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                r.changesJa = ch.ToArray(); r.toSha256 = Sha(to); r.fromSha256After = Sha(from);
                recs.Add(r);
            }
            AssetDatabase.SaveAssets();
            var rep = new Report
            {
                utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, heroPkg = heroPkg, heroTwhiteSha256 = Sha(Path.GetFullPath(Path.Combine(heroPkg, "ds27_twhite_r32f.bin"))),
                sprayDir = sprayDir, sprayFiles = new[] { tone0 + " " + Sha(Path.GetFullPath(tone0)), tone1 + " " + Sha(Path.GetFullPath(tone1)) }, scenes = recs.ToArray()
            };
            var od = Arg("-pl31Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "pl31_setup.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL31_SETUP_DONE " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)));
        }
    }
}
