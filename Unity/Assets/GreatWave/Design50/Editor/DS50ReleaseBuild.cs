using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using GreatWave.Design30;
using GreatWave.Design31;
using GreatWave.Design34;
using GreatWave.Design36;
using GreatWave.Design47;
using GreatWave.Design49;
using GreatWave.Design49.EditorTools;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Design50.EditorTools
{
    // 設計50 release の部：
    //  BuildScene：設計49 の体験の場面 DS49_Sound.unity を DS50_Release.unity へ写し（設計49 の場面は読むだけ）、
    //    ① 場面の絶対のパス（設計41 から写った 3 つ）を、プロジェクトからの相対のパスへ直す（DS30SheetPlayer.uv3File はパッケージからの相対）。
    //    ② 開発者の切替（DS34LayerSet の数字キーで層を消す）を切る（設計45 の 1〜4 の揺れの段と重なるため）。
    //    ③ 体験の枠 DS50Shell（入口・停止・揺れ軽減・終わり・--vr）と自動の試し DS50AutoTest（引数がなければ何もしない）を置く。
    //    ④ 実行時に Shader.Find で探す shader 4 つを、instancing を有効にした参照用の材質でビルドへ入れる（設計35 と同じ形）。
    //  BuildPlayer：Release（BuildOptions.None、Development でない）の Windows プレイヤー 1 つを作る（PC と --vr は同じ exe）。
    //    enableFrameTimingStats（H2 の CPU／GPU 時間）と runInBackground はビルドの間だけ true にし、finally で戻す
    //    （ProjectSettings のバイトの復元は外側の run_ds50_unity.ps1 が確かめる）。
    //    場面が読むデータ（Build/Design/...・Assets/GreatWave/...）を <exe>_Data/StreamingAssets/gwdata の下へ同じ相対の形で写す。
    public static class DS50ReleaseBuild
    {
        public const string Scene49 = DS49SoundBuild.Scene49;
        public const string Scene50 = "Assets/GreatWave/Design50/Scenes/DS50_Release.unity";
        const string MatDir = "Assets/GreatWave/Design50/Materials";
        const string OverlayShader = "GreatWave/Design50/DS50 Overlay";
        const string OutRoot = "Build/Design/50/release";
        const string PlayerDir = OutRoot + "/player";
        const string ExeName = "GreatWave50.exe";
        const string ProjPrefix = "G:/Unity/GreatWave_2026_Fresh/Unity/";
        public const string ShellName = "DS50 体験の枠（入口・停止・揺れ軽減・終わり）";
        const string ProductName = "神奈川沖浪裏 VR（設計50）";
        static readonly string[] SkipDirs = { "_work", "fig", "logs", "_tmp", "debug" };

        public static string[] Protected => DS49SoundBuild.Protected.Concat(new[] {
            Scene49, DS49SoundBuild.SoundJson, "Assets/GreatWave/Design49/Scripts/DS49Sound.cs",
            "Assets/GreatWave/Design49/Editor/DS49SoundBuild.cs", "Assets/GreatWave/Design49/Editor/DS49SoundPlay.cs" }).Distinct().ToArray();

        public static string FileSha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        [Serializable] public class Rewrite { public string obj, component, field, from, to; }
        [Serializable] public class DataFile { public string rel; public long bytes; public string sha256; }
        [Serializable] public class Report
        {
            public string schema = "GreatWave.DS50.build/1", unity, utcStart, utcEnd, productName, fullScreenMode, scene50, scene50Sha256, scene49Sha256Before, scene49Sha256After, playerPath, exeSha256, buildResult, buildOptions, dataRoot, noteJa;
            public bool protectedUnchanged, frameTimingStatsDuringBuild, frameTimingStatsRestored, runInBackgroundRestored, absolutePathsLeft;
            public int absolutePathsAfter, layerSetTogglesOff, dataFiles, buildErrorCount;
            public long totalSize, dataBytes;
            public double buildSeconds;
            public Rewrite[] rewrites;
            public string[] changedProtected, buildErrors, playerFiles, dataSources, keepMaterials, missingSources;
            public DataFile[] data;
        }

        static readonly Report rep = new Report();

        public static void BuildAll()
        {
            rep.unity = Application.unityVersion; rep.utcStart = DateTime.UtcNow.ToString("O");
            var before = Protected.ToDictionary(p => p, FileSha);
            rep.scene49Sha256Before = before[Scene49];
            List<string> sources;
            try { sources = BuildScene(); }
            finally
            {
                var after = Protected.ToDictionary(p => p, FileSha);
                rep.scene49Sha256After = after[Scene49];
                rep.changedProtected = Protected.Where(p => before[p] != after[p]).ToArray();
                rep.protectedUnchanged = rep.changedProtected.Length == 0;
                WriteReport();
            }
            if (!rep.protectedUnchanged) throw new InvalidOperationException("守るファイルが変わった: " + string.Join(", ", rep.changedProtected));
            BuildPlayer();
            CopyData(sources);
            rep.utcEnd = DateTime.UtcNow.ToString("O");
            WriteReport();
            if (rep.buildResult != "Succeeded") throw new InvalidOperationException("ビルドが失敗: " + rep.buildResult);
            Debug.Log("DS50_BUILD_DONE: " + rep.playerPath + " data=" + rep.dataFiles + " files " + rep.dataBytes + " bytes");
        }

        static void WriteReport()
        {
            Directory.CreateDirectory(OutRoot + "/unity");
            File.WriteAllText(OutRoot + "/unity/ds50_build.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
        }

        static Material KeepMat(string path, string shaderName, bool instancing)
        {
            var sh = Shader.Find(shaderName);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + shaderName);
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
            m.shader = sh; m.enableInstancing = instancing;
            EditorUtility.SetDirty(m);
            return m;
        }

        static IEnumerable<(Component c, SerializedObject so, SerializedProperty p)> StringProps(UnityEngine.SceneManagement.Scene scene)
        {
            foreach (var root in scene.GetRootGameObjects())
                foreach (var c in root.GetComponentsInChildren<MonoBehaviour>(true))
                {
                    if (c == null) continue;
                    var so = new SerializedObject(c);
                    var it = so.GetIterator();
                    bool enter = true;
                    while (it.Next(enter))
                    {
                        enter = it.propertyType != SerializedPropertyType.String;
                        if (it.propertyType == SerializedPropertyType.String) yield return (c, so, it.Copy());
                    }
                }
        }

        static bool IsAbs(string v) => !string.IsNullOrEmpty(v) && Regex.IsMatch(v, @"^[A-Za-z]:[\\/]");

        public static List<string> BuildScene()
        {
            AssetDatabase.Refresh();
            Directory.CreateDirectory(Path.GetDirectoryName(Scene50));
            Directory.CreateDirectory(MatDir);
            if (File.Exists(Scene50)) AssetDatabase.DeleteAsset(Scene50);
            if (!AssetDatabase.CopyAsset(Scene49, Scene50)) throw new InvalidOperationException("場面を写せません");
            var panel = KeepMat(MatDir + "/DS50_OverlayPanel.mat", OverlayShader, false);
            panel.SetFloat("_UseAlphaTex", 0f); panel.renderQueue = 4000;
            var text = KeepMat(MatDir + "/DS50_OverlayText.mat", OverlayShader, false);
            text.SetFloat("_UseAlphaTex", 1f); text.renderQueue = 4001;
            var keeps = new[] {
                KeepMat(MatDir + "/DS50_Keep_Spray.mat", DS31InstancedParticles.ShaderName, true),
                KeepMat(MatDir + "/DS50_Keep_Claw.mat", DS34ClawPlayer.ShaderName, true),
                KeepMat(MatDir + "/DS50_Keep_ClawPalette.mat", DS36ClawPalette.ShaderName, true),
                KeepMat(MatDir + "/DS50_Keep_ClawTDepth.mat", DS36ClawPalette.TDepthShaderName, false) };
            AssetDatabase.SaveAssets();
            rep.keepMaterials = keeps.Select(AssetDatabase.GetAssetPath).ToArray();

            var scene = EditorSceneManager.OpenScene(Scene50, OpenSceneMode.Single);
            // ① 絶対のパスを相対へ
            var rewrites = new List<Rewrite>();
            foreach (var (c, so, p) in StringProps(scene).ToList())
            {
                var v = p.stringValue;
                if (!IsAbs(v)) continue;
                var n = v.Replace('\\', '/');
                if (!n.StartsWith(ProjPrefix, StringComparison.OrdinalIgnoreCase)) continue;
                var rel = n.Substring(ProjPrefix.Length);
                string to = rel;
                if (c is DS30SheetPlayer sp && p.name == "uv3File")
                {
                    int depth = sp.packageDir.Replace('\\', '/').Trim('/').Split('/').Length;
                    to = string.Concat(Enumerable.Repeat("../", depth)) + rel;   // Path.Combine(パッケージ, uv3File) で読むので、パッケージからの相対
                }
                p.stringValue = to;
                so.ApplyModifiedPropertiesWithoutUndo();
                rewrites.Add(new Rewrite { obj = c.gameObject.name, component = c.GetType().Name, field = p.name, from = v, to = to });
            }
            rep.rewrites = rewrites.ToArray();
            rep.absolutePathsAfter = StringProps(scene).Count(t => IsAbs(t.p.stringValue));
            rep.absolutePathsLeft = rep.absolutePathsAfter > 0;
            if (rep.absolutePathsLeft) throw new InvalidOperationException("絶対のパスが残る: " + rep.absolutePathsAfter);

            // データの出どころ（場面の文字列のうち、プロジェクトの Build/・Assets/ の下を指すもの）
            var sources = new List<string>();
            foreach (var (c, so, p) in StringProps(scene))
            {
                var v = p.stringValue;
                if (string.IsNullOrEmpty(v)) continue;
                string rel = null;
                if (v.StartsWith("Build/") || v.StartsWith("Assets/")) rel = v;
                else if (v.StartsWith("../") && c is DS30SheetPlayer sp2) rel = NormRel(sp2.packageDir.Trim('/') + "/" + v);
                if (rel == null) continue;
                if (File.Exists(rel) || Directory.Exists(rel)) { if (!sources.Contains(rel)) sources.Add(rel); }
            }
            rep.dataSources = sources.ToArray();

            // ② 開発者の数字キーの切替を切る
            int toggles = 0;
            foreach (var ls in UnityEngine.Object.FindObjectsByType<DS34LayerSet>(FindObjectsInactive.Include))
            { if (ls.keyboardToggles) { ls.keyboardToggles = false; EditorUtility.SetDirty(ls); toggles++; } }
            rep.layerSetTogglesOff = toggles;

            // ③ 体験の枠と自動の試し
            var flow = UnityEngine.Object.FindAnyObjectByType<DS47Flow>(FindObjectsInactive.Include);
            if (flow == null) throw new InvalidOperationException("DS47Flow がありません");
            var sound = UnityEngine.Object.FindAnyObjectByType<DS49Sound>(FindObjectsInactive.Include);
            var old = GameObject.Find(ShellName);
            if (old != null) UnityEngine.Object.DestroyImmediate(old);
            var go = new GameObject(ShellName);
            var shell = go.AddComponent<DS50Shell>();
            shell.flow = flow; shell.clock = flow.clock; shell.rider = flow.rider; shell.events = flow.bus != null ? flow.bus.events : null;
            shell.hmdCamera = flow.hmdCamera; shell.panelMat = panel; shell.textMat = text; shell.keepMaterials = keeps;
            if (shell.events == null) throw new InvalidOperationException("出来事の表がありません");
            var auto = go.AddComponent<DS50AutoTest>();
            auto.shell = shell; auto.flow = flow; auto.clock = flow.clock; auto.sound = sound; auto.rider = flow.rider;
            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene)) throw new InvalidOperationException("場面を保存できません");
            AssetDatabase.SaveAssets();
            rep.scene50 = Scene50; rep.scene50Sha256 = FileSha(Scene50);
            return sources;
        }

        static string NormRel(string p)
        {
            var parts = new List<string>();
            foreach (var s in p.Replace('\\', '/').Split('/'))
            {
                if (s == "" || s == ".") continue;
                if (s == "..") { if (parts.Count > 0) parts.RemoveAt(parts.Count - 1); continue; }
                parts.Add(s);
            }
            return string.Join("/", parts);
        }

        static void BuildPlayer()
        {
            bool prevFt = PlayerSettings.enableFrameTimingStats, prevBg = PlayerSettings.runInBackground;
            string prevName = PlayerSettings.productName;
            var prevFs = PlayerSettings.fullScreenMode;
            if (Directory.Exists(PlayerDir)) Directory.Delete(PlayerDir, true);
            Directory.CreateDirectory(PlayerDir);
            BuildReport br = null;
            try
            {
                PlayerSettings.enableFrameTimingStats = true;
                PlayerSettings.runInBackground = true;
                // 初めての人が開く既定：窓の題名を体験の名前に（M0 の「PC確認版」のままにしない）、画面いっぱいの窓（自動の試しは引数で 1920×1080 の窓）
                PlayerSettings.productName = ProductName;
                PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
                rep.productName = PlayerSettings.productName; rep.fullScreenMode = PlayerSettings.fullScreenMode.ToString();
                rep.frameTimingStatsDuringBuild = PlayerSettings.enableFrameTimingStats;
                var opts = new BuildPlayerOptions
                {
                    scenes = new[] { Scene50 }, locationPathName = PlayerDir + "/" + ExeName,
                    target = BuildTarget.StandaloneWindows64, targetGroup = BuildTargetGroup.Standalone, options = BuildOptions.None   // Release
                };
                rep.buildOptions = opts.options.ToString();
                br = BuildPipeline.BuildPlayer(opts);
            }
            finally
            {
                PlayerSettings.enableFrameTimingStats = prevFt;
                PlayerSettings.runInBackground = prevBg;
                PlayerSettings.productName = prevName;
                PlayerSettings.fullScreenMode = prevFs;
                AssetDatabase.SaveAssets();
                rep.frameTimingStatsRestored = PlayerSettings.enableFrameTimingStats == prevFt;
                rep.runInBackgroundRestored = PlayerSettings.runInBackground == prevBg && PlayerSettings.productName == prevName && PlayerSettings.fullScreenMode == prevFs;
            }
            rep.playerPath = Path.GetFullPath(PlayerDir + "/" + ExeName);
            rep.buildResult = br.summary.result.ToString();
            rep.totalSize = (long)br.summary.totalSize;
            rep.buildSeconds = br.summary.totalTime.TotalSeconds;
            rep.buildErrors = br.steps.SelectMany(s => s.messages).Where(m => m.type == LogType.Error || m.type == LogType.Exception).Select(m => m.content).Take(30).ToArray();
            rep.buildErrorCount = rep.buildErrors.Length;
            rep.exeSha256 = FileSha(PlayerDir + "/" + ExeName);
            rep.playerFiles = Directory.Exists(PlayerDir) ? Directory.GetFiles(PlayerDir, "*", SearchOption.TopDirectoryOnly).Select(f => Path.GetFileName(f) + " " + new FileInfo(f).Length).OrderBy(s => s).ToArray() : new string[0];
        }

        static void CopyData(List<string> sources)
        {
            var dataDir = PlayerDir + "/" + Path.GetFileNameWithoutExtension(ExeName) + "_Data/StreamingAssets/gwdata";
            rep.dataRoot = Path.GetFullPath(dataDir);
            var files = new SortedSet<string>(StringComparer.Ordinal);
            var missing = new List<string>();
            foreach (var s in sources)
            {
                if (Directory.Exists(s))
                {
                    foreach (var f in Directory.GetFiles(s, "*", SearchOption.AllDirectories))
                    {
                        var r = f.Replace('\\', '/');
                        var parts = r.Substring(s.Length).Split('/');
                        if (parts.Any(x => SkipDirs.Contains(x))) continue;
                        if (r.EndsWith(".meta")) continue;
                        files.Add(r);
                    }
                }
                else if (File.Exists(s))
                {
                    files.Add(s);
                    if (s.EndsWith(".json"))
                    {
                        // 表が同じフォルダーのほかのファイル（.bin など）を名前で指すときは、それも写す
                        var dir = Path.GetDirectoryName(s).Replace('\\', '/');
                        foreach (Match m in Regex.Matches(File.ReadAllText(s), "\"([^\"/\\\\:]+\\.[A-Za-z0-9_]+)\""))
                        {
                            var sib = dir + "/" + m.Groups[1].Value;
                            if (File.Exists(sib)) files.Add(sib);
                        }
                    }
                }
                else missing.Add(s);
            }
            rep.missingSources = missing.ToArray();
            var list = new List<DataFile>();
            long total = 0;
            foreach (var f in files)
            {
                var dst = dataDir + "/" + f;
                Directory.CreateDirectory(Path.GetDirectoryName(dst));
                File.Copy(f, dst, true);
                long n = new FileInfo(f).Length; total += n;
                list.Add(new DataFile { rel = f, bytes = n, sha256 = FileSha(f) });
            }
            rep.data = list.ToArray(); rep.dataFiles = list.Count; rep.dataBytes = total;
            rep.noteJa = "Release（Development でない）。PC と --vr は同じ exe。データは <exe>_Data/StreamingAssets/gwdata の下（プレイヤーは場面を読む前に作業ディレクトリをそこへ移す）。";
        }
    }
}
