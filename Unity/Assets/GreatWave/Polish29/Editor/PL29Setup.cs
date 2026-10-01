using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design30;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Polish29.EditorTools
{
    // 仕上げ29（Q28）の組み立て：
    //  EnsureMaterial：PL29 Ukiyoe Keypose の材質 PL29_Ukiyoe_Hero.mat を作る（無ければ）。限定色（設計36）は設計27 の DS27_NPR_White.mat の値を写す。
    //    -pl29ParamFile があれば、その値（名前=値）を材質のファイルへ書く（決めた数値を材質に残す）。
    //  BuildScenes：設計50 の体験の場面 DS50_Release.unity と、設計30 の単発再生の場面 DS30_SinglePlayback.unity を、Polish29/Scenes へ写し
    //    （元の場面は読むだけ）、写しの主役波を仕上げ28 の採用（K*′ P28R2rec・動き G_p28rec）へ替え、焼き込みのファイル（sdfPath・warpPath・uv3File）を空にし、
    //    面の材質を PL29_Ukiyoe_Hero.mat にして、PL29UkiyoeHero（面の座標を読む）を付ける。時間曲線も G_p28rec のものにする。
    //    爪の色は、設計36 の DS36ClawPalette（原画カメラの投影の表）を切って、設計34 の視点によらない白・淡い水色に戻す（Q28。爪の形・軌跡は替えない）。
    //    飛沫・線の印・周りの海は替えない（仕上げ30〜33・36・38）。
    //  ［修正の回］EnsureMaterial は爪の材質 PL29_Claw_Shade.mat（PL29 Claw Shade）も作り、-pl29ClawParamFile の値を書く。
    //    BuildScenes は爪に PL29ClawShade（視点によらない陰の段と、原画視点でも描く縁の線）を付ける。面の座標は -pl29Attr（修正の回は t* の弧長の版）。
    public static class PL29Setup
    {
        public const string MatPath = PL29Render.MatPath;
        const string ShaderName = "GreatWave/Polish29/PL29 Ukiyoe Keypose";
        const string OldMat = "Assets/GreatWave/Design27/Materials/DS27_NPR_White.mat";
        public const string Scene50 = "Assets/GreatWave/Design50/Scenes/DS50_Release.unity";
        public const string Scene30 = "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity";
        public const string SceneRelease = "Assets/GreatWave/Polish29/Scenes/PL29_Release.unity";
        public const string SceneSingle = "Assets/GreatWave/Polish29/Scenes/PL29_SinglePlayback.unity";

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

        public static void EnsureMaterial()
        {
            var sh = Shader.Find(ShaderName);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + ShaderName);
            var m = AssetDatabase.LoadAssetAtPath<Material>(MatPath);
            if (m == null)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(MatPath));
                m = new Material(sh) { name = "PL29_Ukiyoe_Hero" };
                var old = AssetDatabase.LoadAssetAtPath<Material>(OldMat);
                if (old != null) foreach (var p in new[] { "_White", "_Mizuiro", "_AiMid", "_AiDark" }) m.SetColor(p, old.GetColor(p));
                AssetDatabase.CreateAsset(m, MatPath);
            }
            var pf = Arg("-pl29ParamFile");
            if (!string.IsNullOrEmpty(pf))
            {
                foreach (var raw in File.ReadAllLines(pf, Encoding.UTF8))
                {
                    var line = raw.Split('#')[0].Trim();
                    if (line.Length == 0) continue;
                    int k = line.IndexOf('=');
                    string name = line.Substring(0, k).Trim(), val = line.Substring(k + 1).Trim();
                    var parts = val.Split(',').Select(x => float.Parse(x.Trim(), CultureInfo.InvariantCulture)).ToArray();
                    if (!m.HasProperty(name)) throw new ArgumentException("材質にない値: " + name);
                    if (parts.Length == 1) m.SetFloat(name, parts[0]);
                    else
                    {
                        var v = new Vector4(parts[0], parts.Length > 1 ? parts[1] : 0, parts.Length > 2 ? parts[2] : 0, parts.Length > 3 ? parts[3] : 1);
                        if (name.StartsWith("_White") || name.StartsWith("_Mizuiro") || name.StartsWith("_Ai") || name.StartsWith("_LineCol")) m.SetColor(name, v);
                        else m.SetVector(name, v);
                    }
                }
                EditorUtility.SetDirty(m);
            }
            // シェーダーにない古い値（作る途中の版の名前）を材質のファイルから消す
            var so = new SerializedObject(m);
            int removed = 0;
            foreach (var arr in new[] { "m_SavedProperties.m_Floats", "m_SavedProperties.m_Colors", "m_SavedProperties.m_TexEnvs", "m_SavedProperties.m_Ints" })
            {
                var sp = so.FindProperty(arr);
                if (sp == null) continue;
                for (int i = sp.arraySize - 1; i >= 0; i--)
                {
                    var nm = sp.GetArrayElementAtIndex(i).FindPropertyRelative("first").stringValue;
                    if (!m.shader.FindPropertyIndex(nm).Equals(-1)) continue;
                    sp.DeleteArrayElementAtIndex(i); removed++;
                }
            }
            if (removed > 0) { so.ApplyModifiedPropertiesWithoutUndo(); EditorUtility.SetDirty(m); }
            EnsureClawMaterial();
            AssetDatabase.SaveAssets();
            Debug.Log("PL29_SETUP_MATERIAL_REMOVED_STALE " + removed);
            Debug.Log("PL29_SETUP_MATERIAL " + MatPath + " sha256=" + Sha(MatPath) + " shader=" + m.shader.name);
        }

        static void WriteParams(Material m, string pf)
        {
            foreach (var raw in File.ReadAllLines(pf, Encoding.UTF8))
            {
                var line = raw.Split('#')[0].Trim();
                if (line.Length == 0) continue;
                int k = line.IndexOf('=');
                string name = line.Substring(0, k).Trim(), val = line.Substring(k + 1).Trim();
                var parts = val.Split(',').Select(x => float.Parse(x.Trim(), CultureInfo.InvariantCulture)).ToArray();
                if (!m.HasProperty(name)) throw new ArgumentException("材質にない値: " + name);
                if (parts.Length == 1) m.SetFloat(name, parts[0]);
                else
                {
                    var v = new Vector4(parts[0], parts.Length > 1 ? parts[1] : 0, parts.Length > 2 ? parts[2] : 0, parts.Length > 3 ? parts[3] : 1);
                    if (name.StartsWith("_White") || name.StartsWith("_Mizuiro") || name.StartsWith("_Ai") || name.StartsWith("_LineCol")) m.SetColor(name, v);
                    else m.SetVector(name, v);
                }
            }
            EditorUtility.SetDirty(m);
        }

        // 爪の材質（PL29 Claw Shade）。限定色は主役波の材質の白・淡い水色・藍中を写す
        static void EnsureClawMaterial()
        {
            var sh = Shader.Find(PL29Render.ClawShaderName);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + PL29Render.ClawShaderName);
            var m = AssetDatabase.LoadAssetAtPath<Material>(PL29Render.ClawMatPath);
            if (m == null)
            {
                m = new Material(sh) { name = "PL29_Claw_Shade", enableInstancing = true };
                AssetDatabase.CreateAsset(m, PL29Render.ClawMatPath);
            }
            var hero = AssetDatabase.LoadAssetAtPath<Material>(MatPath);
            if (hero != null) foreach (var p in new[] { "_White", "_Mizuiro", "_AiMid" }) m.SetColor(p, hero.GetColor(p));
            m.enableInstancing = true;
            var pf = Arg("-pl29ClawParamFile");
            if (!string.IsNullOrEmpty(pf)) WriteParams(m, pf);
            EditorUtility.SetDirty(m);
            Debug.Log("PL29_SETUP_CLAW_MATERIAL " + PL29Render.ClawMatPath + " steps=" + m.GetVector("_Steps"));
        }

        [Serializable] class SceneRec { public string from, fromSha256Before, fromSha256After, to, toSha256; public string[] changesJa; }
        [Serializable] class Report { public string utc, unity, material, materialSha256, attr, attrSha256; public SceneRec[] scenes; }

        public static void BuildScenes()
        {
            EnsureMaterial();
            var mat = AssetDatabase.LoadAssetAtPath<Material>(MatPath);
            var attr = Arg("-pl29Attr") ?? PL29Render.AttrPath;
            var attrSha = Sha(attr);
            var recs = new List<SceneRec>();
            foreach (var (from, to) in new[] { (Scene50, SceneRelease), (Scene30, SceneSingle) })
            {
                var r = new SceneRec { from = from, fromSha256Before = Sha(from), to = to };
                var ch = new List<string>();
                Directory.CreateDirectory(Path.GetDirectoryName(to));
                if (File.Exists(to)) AssetDatabase.DeleteAsset(to);
                if (!AssetDatabase.CopyAsset(from, to)) throw new InvalidOperationException("場面を写せません: " + from);
                var scene = EditorSceneManager.OpenScene(to, OpenSceneMode.Single);
                var players = scene.GetRootGameObjects().SelectMany(g => g.GetComponentsInChildren<DS30SinglePlayback>(true)).ToList();
                if (players.Count != 1) throw new InvalidOperationException("DS30SinglePlayback が 1 つでない: " + players.Count);
                var play = players[0];
                var hero = play.sheets.First(s => s != null && s.sheetName == "hero");
                ch.Add("主役波 packageDir " + hero.packageDir + " → " + PL29Render.RecPkg);
                ch.Add("主役波 meshGwb " + hero.meshGwb + " → " + PL29Render.RecGwb);
                ch.Add("主役波 sdfPath " + hero.sdfPath + " → 空（投影の色区テクスチャを読まない）");
                ch.Add("主役波 warpPath " + hero.warpPath + " → 空（投影の UV3 の表を読まない）");
                ch.Add("主役波 uv3File " + hero.uv3File + " → 空");
                ch.Add("時間曲線 " + play.timewarpPath + " → " + PL29Render.RecWarp);
                hero.packageDir = PL29Render.RecPkg; hero.meshGwb = PL29Render.RecGwb;
                // ［修正の回］主役波の物の AF26KStarMesh.dataPath に残っていた前の K* のパス（Build/Design/29R01/bake_kp/kstar/kstar_a45.gwb）も替える。
                // 実行時は DS30SheetPlayer が meshGwb で上書きするので描画は変わらないが、Release のビルドがそのファイルを写し、焼き込みのフォルダーを指したままになっていた。
                var km = hero.GetComponent<GreatWave.ArtFirst.AF26KStarMesh>();
                if (km != null && km.dataPath != PL29Render.RecGwb)
                {
                    ch.Add("主役波の AF26KStarMesh.dataPath " + km.dataPath + " → " + PL29Render.RecGwb + "（実行時は meshGwb で上書きされる。古いパスを残さない）");
                    km.dataPath = PL29Render.RecGwb; EditorUtility.SetDirty(km);
                }
                hero.sdfPath = ""; hero.warpPath = ""; hero.uv3File = "";
                play.timewarpPath = PL29Render.RecWarp;
                var hr = hero.GetComponent<MeshRenderer>();
                ch.Add("主役波の面の材質 " + (hr.sharedMaterial != null ? hr.sharedMaterial.name : "なし") + " → PL29_Ukiyoe_Hero");
                hr.sharedMaterial = mat;
                var uk = hero.GetComponent<PL29UkiyoeHero>();
                if (uk == null) uk = hero.gameObject.AddComponent<PL29UkiyoeHero>();
                uk.sheet = hero; uk.attrPath = attr; uk.attrSha256 = attrSha; uk.material = mat;
                ch.Add("PL29UkiyoeHero を付けた（面の座標 " + attr + "、SHA-256 " + attrSha + "）");
                // 爪の色：設計36 の DS36ClawPalette（原画カメラの投影の表で塗る）を切り、設計34 の視点によらない白（上面）・淡い水色（縁の側面と下面）にする
                foreach (var cp in scene.GetRootGameObjects().SelectMany(g => g.GetComponentsInChildren<GreatWave.Design36.DS36ClawPalette>(true)))
                {
                    if (cp.enabled) { cp.enabled = false; EditorUtility.SetDirty(cp); ch.Add("爪の DS36ClawPalette（原画カメラの投影の色）を切った：" + cp.gameObject.name + "（設計34 の白・淡い水色のまま）"); }
                }
                // ［修正の回］爪に視点によらない陰の段（PL29ClawShade、PL29_Claw_Shade.mat）と、原画視点でも描く縁の線
                var clawMat = AssetDatabase.LoadAssetAtPath<Material>(PL29Render.ClawMatPath);
                foreach (var cpl in scene.GetRootGameObjects().SelectMany(g => g.GetComponentsInChildren<GreatWave.Design34.DS34ClawPlayer>(true)))
                {
                    var cs = cpl.GetComponent<PL29ClawShade>();
                    if (cs == null) cs = cpl.gameObject.AddComponent<PL29ClawShade>();
                    cs.claws = cpl; cs.material = clawMat; cs.linesEverywhere = true;
                    EditorUtility.SetDirty(cs);
                    ch.Add("爪に PL29ClawShade を付けた：" + cpl.gameObject.name + "（" + PL29Render.ClawMatPath + "。白・淡い水色・藍中の段と、原画視点でも描く縁の線）");
                }
                EditorUtility.SetDirty(hero); EditorUtility.SetDirty(play); EditorUtility.SetDirty(hr); EditorUtility.SetDirty(uk);
                EditorSceneManager.MarkSceneDirty(scene);
                if (!EditorSceneManager.SaveScene(scene)) throw new InvalidOperationException("場面を保存できません: " + to);
                r.changesJa = ch.ToArray(); r.toSha256 = Sha(to); r.fromSha256After = Sha(from);
                if (r.fromSha256After != r.fromSha256Before) throw new InvalidOperationException("元の場面が変わった: " + from);
                recs.Add(r);
            }
            AssetDatabase.SaveAssets();
            var rep = new Report { utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, material = MatPath, materialSha256 = Sha(MatPath), attr = attr, attrSha256 = attrSha, scenes = recs.ToArray() };
            var od = Arg("-pl29Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/after/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(od + "/pl29_setup_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL29_SETUP_SCENES_DONE " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)));
        }
    }
}
