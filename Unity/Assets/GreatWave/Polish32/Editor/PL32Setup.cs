using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design30;
using GreatWave.Design34;
using GreatWave.Polish29;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Polish32.EditorTools
{
    // 仕上げ32 の組み立て：仕上げ31 の場面 PL31_Release.unity・PL31_SinglePlayback.unity を Polish32/Scenes へ写し（元の場面は読むだけ）、写しの
    //  ・主役波のパッケージを、T_white だけ差し替えた hero_pkg（pl32_white.py：爪の根元の誘導 pl31_white_claw_pin を外し、飛沫の放出点の誘導
    //    pl32_white_spray_pin を掛けたもの。位置・精度の層は G_p28rec の art_on と同じバイト）へ
    //  ・爪の層（DS34ClawPlayer）の並びを、仕上げ32 の爪（pl32_claws.py。b区域の爪を加えた一覧を K*′ P28R2rec のシートへ結び付け直した帯）へ
    //  ・爪の材質（PL29ClawShade の material）を、仕上げ29 の PL29_Claw_Shade.mat を写した PL32_Claw_Shade.mat（-pl32ClawParamFile の値：
    //    摺りの工程の版に合わせ、下面の段を藍中から水色の版の色にした。Tools/GWWaveGen/pl32/pl32_claw_params.txt）へ
    // にする。海・飛沫・線・主役波の材質は仕上げ31 のまま。仕上げ29 の材質のファイルは変えない。
    // 仕上げ32 修正の回 1：爪の並びの既定を修正の回 1 の爪（Build/Polish/32/fix01/claws、pl32f_claws.py）にし、爪の物に
    //  ・PL32ClawLook（縁の線を根元で開く pl32f_root_open・縁から見た箱の線を出さない pl32f_edge_box・根元の円を水色の版にする pl32f_tuft_base。
    //    シェーダー PL32 Claw Outline を場面から参照してビルドに入れる）
    //  ・PL32ClawDriver（爪の時刻のコマが変わった時だけ頂点を入れ直す。設計46 の時計の "claws" の段を同じ名前で登録し直す）
    // を足す。DS34ClawPlayer・DS38ClawOutline・DS46ClockBus のファイルは変えない。
    public static class PL32Setup
    {
        public const string SceneRelease31 = "Assets/GreatWave/Polish31/Scenes/PL31_Release.unity";
        public const string SceneSingle31 = "Assets/GreatWave/Polish31/Scenes/PL31_SinglePlayback.unity";
        public const string SceneRelease = "Assets/GreatWave/Polish32/Scenes/PL32_Release.unity";
        public const string SceneSingle = "Assets/GreatWave/Polish32/Scenes/PL32_SinglePlayback.unity";
        public const string ClawMat29 = "Assets/GreatWave/Polish29/Materials/PL29_Claw_Shade.mat";
        public const string ClawMat = "Assets/GreatWave/Polish32/Materials/PL32_Claw_Shade.mat";

        // PL29_Claw_Shade.mat を写して、値のファイル（名前=値。色・ベクトルは「,」で 4 つまで）を書く
        static Material EnsureClawMaterial(string paramFile, List<string> log)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(ClawMat));
            if (File.Exists(ClawMat)) AssetDatabase.DeleteAsset(ClawMat);
            if (!AssetDatabase.CopyAsset(ClawMat29, ClawMat)) throw new InvalidOperationException("爪の材質を写せません: " + ClawMat29);
            AssetDatabase.ImportAsset(ClawMat);
            var m = AssetDatabase.LoadAssetAtPath<Material>(ClawMat);
            foreach (var raw in File.ReadAllLines(paramFile, Encoding.UTF8))
            {
                var line = raw.Split('#')[0].Trim();
                if (line.Length == 0) continue;
                int k = line.IndexOf('=');
                string name = line.Substring(0, k).Trim();
                var v = line.Substring(k + 1).Split(',').Select(x => float.Parse(x.Trim(), System.Globalization.CultureInfo.InvariantCulture)).ToArray();
                var v4 = new Vector4(v[0], v.Length > 1 ? v[1] : 0, v.Length > 2 ? v[2] : 0, v.Length > 3 ? v[3] : 1);
                if (name.StartsWith("_White") || name.StartsWith("_Mizuiro") || name.StartsWith("_Ai")) m.SetColor(name, v4); else m.SetVector(name, v4);
                log.Add(name + "=" + line.Substring(k + 1).Trim());
            }
            EditorUtility.SetDirty(m);
            AssetDatabase.SaveAssets();
            return m;
        }

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
        [Serializable] class Report { public string utc, unity, heroPkg, heroTwhiteSha256, clawLayout, clawLayoutSha256, clawMaterial, clawMaterialSha256, clawParamFile; public string[] clawParams; public SceneRec[] scenes; }

        public static void BuildScenes()
        {
            string heroPkg = Arg("-pl32HeroPkg") ?? "Build/Polish/32/white/hero_pkg";
            string clawLayout = Arg("-pl32Claws") ?? "Build/Polish/32/fix01/claws/ds33_claw_layout.json";
            var outlineShader = Shader.Find("GreatWave/Polish32/PL32 Claw Outline");
            if (outlineShader == null) throw new InvalidOperationException("PL32 Claw Outline のシェーダーがありません");
            if (!File.Exists(Path.GetFullPath(Path.Combine(heroPkg, "ds27_keypose.json")))) throw new InvalidOperationException("hero_pkg がありません: " + heroPkg);
            if (!File.Exists(Path.GetFullPath(clawLayout))) throw new InvalidOperationException("爪の並びがありません: " + clawLayout);
            string clawParam = Arg("-pl32ClawParamFile") ?? "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl32/pl32_claw_params.txt";
            var plog = new List<string>();
            var clawMat = EnsureClawMaterial(clawParam, plog);
            var recs = new List<SceneRec>();
            foreach (var (from, to) in new[] { (SceneRelease31, SceneRelease), (SceneSingle31, SceneSingle) })
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
                ch.Add("主役波 packageDir " + hero.packageDir + " → " + heroPkg + "（T_white だけ差し替え。pl31_white_claw_pin を外し、pl32_white_spray_pin を掛けた）");
                hero.packageDir = heroPkg; EditorUtility.SetDirty(hero);
                var claws = roots.SelectMany(g => g.GetComponentsInChildren<DS34ClawPlayer>(true)).ToList();
                if (claws.Count == 0) ch.Add("爪の層はない");
                foreach (var cp in claws)
                {
                    ch.Add("爪 " + cp.gameObject.name + " の layoutPath " + cp.layoutPath + " → " + clawLayout + "（仕上げ32 修正の回 1 の爪：184 本、K*′ P28R2rec のシート）");
                    cp.layoutPath = clawLayout; EditorUtility.SetDirty(cp);
                    var look = cp.GetComponent<GreatWave.Polish32.PL32ClawLook>() ?? cp.gameObject.AddComponent<GreatWave.Polish32.PL32ClawLook>();
                    look.claws = cp; look.shade = cp.GetComponent<PL29ClawShade>(); look.outline = cp.GetComponent<GreatWave.Design38.DS38ClawOutline>();
                    look.outlineShader = outlineShader; look.rootOpen = true; look.tuftBase = true;
                    EditorUtility.SetDirty(look);
                    ch.Add("爪 " + cp.gameObject.name + " に PL32ClawLook（pl32f_root_open・pl32f_edge_box・pl32f_tuft_base、根元で線を開く " + look.rootFade.ToString("F2") + "）");
                    var drv = cp.GetComponent<GreatWave.Polish32.PL32ClawDriver>() ?? cp.gameObject.AddComponent<GreatWave.Polish32.PL32ClawDriver>();
                    drv.claws = cp; drv.outline = look.outline;
                    EditorUtility.SetDirty(drv);
                    ch.Add("爪 " + cp.gameObject.name + " に PL32ClawDriver（時刻のコマが変わった時だけ頂点を入れ直す）");
                }
                foreach (var sh in roots.SelectMany(g => g.GetComponentsInChildren<PL29ClawShade>(true)))
                {
                    ch.Add("爪の材質 " + (sh.material != null ? AssetDatabase.GetAssetPath(sh.material) : "なし") + " → " + ClawMat + "（摺りの版の色：下面の段を水色の版に）");
                    sh.material = clawMat; EditorUtility.SetDirty(sh);
                }
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                r.changesJa = ch.ToArray(); r.toSha256 = Sha(to); r.fromSha256After = Sha(from);
                recs.Add(r);
            }
            AssetDatabase.SaveAssets();
            var rep = new Report
            {
                utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, heroPkg = heroPkg, heroTwhiteSha256 = Sha(Path.GetFullPath(Path.Combine(heroPkg, "ds27_twhite_r32f.bin"))),
                clawLayout = clawLayout, clawLayoutSha256 = Sha(Path.GetFullPath(clawLayout)), clawMaterial = ClawMat, clawMaterialSha256 = Sha(ClawMat),
                clawParamFile = clawParam, clawParams = plog.ToArray(), scenes = recs.ToArray()
            };
            var od = Arg("-pl32Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/32/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "pl32_setup.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL32_SETUP_DONE " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)));
        }
    }
}
