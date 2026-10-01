using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using GreatWave.Design30;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using GreatWave.Polish29;
using UnityEngine;

namespace GreatWave.Polish30.EditorTools
{
    // 仕上げ29 修正の回（Q28）：体験の Release のプレイヤーを、仕上げ29 の場面 PL29_Release.unity から作る。
    // 設計50 の DS50ReleaseBuild は DS49_Sound.unity を DS50_Release.unity へ写してビルドするので、その exe の主役波は原画カメラからの投影の焼き込み
    // （Build/Design/31/white/hero_pkg・Build/Design/29R01/bake_kp の af28r01_uvsdf_a45.bin・uvwarp・ds29_uv3、DS27_NPR_White）のままだった（作る部の評審）。
    // ［仕上げ30：PL29ReleaseBuild を写し、場面を PL30_Release.unity（PL30Setup.BuildScenes）、出力を Build/Polish/30/release、必ず要るデータに仕上げ30 の海と左奥の船のうねりを足した］
    // ここでは PL29Setup.BuildScenes が DS50_Release.unity から作った PL29_Release.unity（主役波は K*′ P28R2rec・G_p28rec・PL29 Ukiyoe Keypose と面の座標、
    // 爪は PL29 Claw Shade）をビルドする。ビルドの設定・データの写し方は DS50ReleaseBuild と同じ（設計50 のファイルは変えない）：
    //   ・Release（BuildOptions.None、Development でない）の Windows プレイヤー 1 つ（PC と --vr は同じ exe）。enableFrameTimingStats・runInBackground・
    //     productName・fullScreenMode はビルドの間だけ替え、finally で戻す。
    //   ・場面の文字列のうち Build/…・Assets/… を指すもの（と、JSON が同じフォルダーで名前で指すファイル）を <exe>_Data/StreamingAssets/gwdata の下へ同じ相対の形で写す。
    // 出力：Unity/Build/Polish/29/release/player/GreatWave50.exe（Git 対象外）と Unity/Build/Polish/29/release/unity/pl30_build.json。
    // 使い方：run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30ReleaseBuild.BuildAll -Log release_build（PL30Setup.BuildScenes の後）
    public static class PL30ReleaseBuild
    {
        public const string Scene = PL30Setup.SceneRelease;
        const string OutRoot = "Build/Polish/30/release";
        const string PlayerDir = OutRoot + "/player";
        const string ExeName = "GreatWave50.exe";
        const string ProductName = "神奈川沖浪裏 VR（設計50・仕上げ30）";
        static readonly string[] SkipDirs = { "_work", "fig", "logs", "_tmp", "debug" };
        static readonly string[] MustHave = {
            "Build/Polish/28/G_p28rec/art_on", "Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb", "Build/Polish/28/G_p28rec/timewarp_G_p28rec.json",
            "Build/Polish/30/sea/near", "Build/Polish/30/sea/far", "Build/Polish/30/sea/boat_support.json", "Build/Polish/30/left_swell/pl30_left_swell.json" };

        [Serializable] public class DataFile { public string rel; public long bytes; public string sha256; }
        [Serializable] public class Report
        {
            public string schema = "GreatWave.Polish30.release_build/1", unity, utcStart, utcEnd, productName, fullScreenMode, scene, sceneSha256, playerPath, exeSha256, buildResult, buildOptions, dataRoot, noteJa;
            public string heroPackageDir, heroMeshGwb, heroSdfPath, heroWarpPath, heroUv3File, heroMaterial, heroShader, heroAttr, heroAttrSha256, timewarp;
            public bool frameTimingStatsRestored, settingsRestored, absolutePathsLeft, clawShadeOnClaws, mustHavePresent, bakeFilesAbsent;
            public int dataFiles, buildErrorCount, absolutePaths;
            public long totalSize, dataBytes;
            public double buildSeconds;
            public string[] scenesInBuild, buildErrors, playerFiles, dataSources, missingSources, mustHaveMissing, bakeFilesFound;
            public DataFile[] data;
        }

        static readonly Report rep = new Report();

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        static IEnumerable<(Component c, SerializedProperty p)> StringProps(UnityEngine.SceneManagement.Scene scene)
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
                        if (it.propertyType == SerializedPropertyType.String) yield return (c, it.Copy());
                    }
                }
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

        public static void BuildAll()
        {
            rep.unity = Application.unityVersion; rep.utcStart = DateTime.UtcNow.ToString("O");
            AssetDatabase.Refresh();
            if (!File.Exists(Scene)) throw new InvalidOperationException("場面がありません（PL30Setup.BuildScenes を先に）: " + Scene);
            var scene = EditorSceneManager.OpenScene(Scene, OpenSceneMode.Single);
            rep.scene = Scene; rep.sceneSha256 = Sha(Scene);
            // 主役波と爪の状態（読むだけ）
            var play = scene.GetRootGameObjects().SelectMany(g => g.GetComponentsInChildren<DS30SinglePlayback>(true)).First();
            var hero = play.sheets.First(s => s != null && s.sheetName == "hero");
            rep.heroPackageDir = hero.packageDir; rep.heroMeshGwb = hero.meshGwb; rep.heroSdfPath = hero.sdfPath; rep.heroWarpPath = hero.warpPath; rep.heroUv3File = hero.uv3File;
            rep.timewarp = play.timewarpPath;
            var hr = hero.GetComponent<MeshRenderer>();
            rep.heroMaterial = hr.sharedMaterial != null ? AssetDatabase.GetAssetPath(hr.sharedMaterial) : "";
            rep.heroShader = hr.sharedMaterial != null ? hr.sharedMaterial.shader.name : "";
            var uk = hero.GetComponent<PL29UkiyoeHero>();
            rep.heroAttr = uk != null ? uk.attrPath : ""; rep.heroAttrSha256 = uk != null ? uk.attrSha256 : "";
            rep.clawShadeOnClaws = scene.GetRootGameObjects().SelectMany(g => g.GetComponentsInChildren<GreatWave.Design34.DS34ClawPlayer>(true))
                                        .All(cp => cp.GetComponent<PL29ClawShade>() != null && cp.GetComponent<PL29ClawShade>().material != null);
            if (!string.IsNullOrEmpty(hero.sdfPath) || !string.IsNullOrEmpty(hero.warpPath) || !string.IsNullOrEmpty(hero.uv3File) || uk == null || rep.heroShader != "GreatWave/Polish29/PL29 Ukiyoe Keypose")
                throw new InvalidOperationException("PL30_Release の主役波が仕上げ29 の状態でない");
            rep.absolutePaths = StringProps(scene).Count(t => !string.IsNullOrEmpty(t.p.stringValue) && Regex.IsMatch(t.p.stringValue, @"^[A-Za-z]:[\\/]"));
            rep.absolutePathsLeft = rep.absolutePaths > 0;
            if (rep.absolutePathsLeft) throw new InvalidOperationException("絶対のパスが残る: " + rep.absolutePaths);
            // データの出どころ（DS50ReleaseBuild と同じ規則）
            var sources = new List<string>();
            foreach (var (c, p) in StringProps(scene))
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
            try
            {
                BuildPlayer();
                CopyData(sources);
            }
            finally
            {
                rep.utcEnd = DateTime.UtcNow.ToString("O");
                WriteReport();
            }
            if (rep.buildResult != "Succeeded") throw new InvalidOperationException("ビルドが失敗: " + rep.buildResult);
            Debug.Log("PL30_RELEASE_BUILD_DONE: " + rep.playerPath + " data=" + rep.dataFiles + " files " + rep.dataBytes + " bytes mustHave=" + rep.mustHavePresent + " bakeAbsent=" + rep.bakeFilesAbsent);
        }

        static void WriteReport()
        {
            Directory.CreateDirectory(OutRoot + "/unity");
            File.WriteAllText(OutRoot + "/unity/pl30_build.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
        }

        static void BuildPlayer()
        {
            bool prevFt = PlayerSettings.enableFrameTimingStats, prevBg = PlayerSettings.runInBackground;
            string prevName = PlayerSettings.productName;
            var prevFs = PlayerSettings.fullScreenMode;
            if (Directory.Exists(PlayerDir))
            {
                // 写したデータに読み取り専用のファイル（凍結した K*′ など）があると消せないので、属性を戻してから消す
                foreach (var f in Directory.GetFiles(PlayerDir, "*", SearchOption.AllDirectories)) File.SetAttributes(f, FileAttributes.Normal);
                Directory.Delete(PlayerDir, true);
            }
            Directory.CreateDirectory(PlayerDir);
            BuildReport br = null;
            try
            {
                PlayerSettings.enableFrameTimingStats = true;
                PlayerSettings.runInBackground = true;
                PlayerSettings.productName = ProductName;
                PlayerSettings.fullScreenMode = FullScreenMode.FullScreenWindow;
                rep.productName = PlayerSettings.productName; rep.fullScreenMode = PlayerSettings.fullScreenMode.ToString();
                var opts = new BuildPlayerOptions
                {
                    scenes = new[] { Scene }, locationPathName = PlayerDir + "/" + ExeName,
                    target = BuildTarget.StandaloneWindows64, targetGroup = BuildTargetGroup.Standalone, options = BuildOptions.None   // Release
                };
                rep.scenesInBuild = opts.scenes;
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
                rep.settingsRestored = PlayerSettings.runInBackground == prevBg && PlayerSettings.productName == prevName && PlayerSettings.fullScreenMode == prevFs;
            }
            rep.playerPath = Path.GetFullPath(PlayerDir + "/" + ExeName);
            rep.buildResult = br.summary.result.ToString();
            rep.totalSize = (long)br.summary.totalSize;
            rep.buildSeconds = br.summary.totalTime.TotalSeconds;
            rep.buildErrors = br.steps.SelectMany(s => s.messages).Where(m => m.type == LogType.Error || m.type == LogType.Exception).Select(m => m.content).Take(30).ToArray();
            rep.buildErrorCount = rep.buildErrors.Length;
            rep.exeSha256 = Sha(PlayerDir + "/" + ExeName);
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
                if (File.Exists(dst)) File.SetAttributes(dst, FileAttributes.Normal);
                File.Copy(f, dst, true);
                File.SetAttributes(dst, FileAttributes.Normal);   // 元が読み取り専用でも、プレイヤーの中の写しは普通のファイルにする
                long n = new FileInfo(f).Length; total += n;
                list.Add(new DataFile { rel = f, bytes = n, sha256 = Sha(f) });
            }
            rep.data = list.ToArray(); rep.dataFiles = list.Count; rep.dataBytes = total;
            // 主役波の採用のデータがある／投影の焼き込みのファイルがない
            var must = MustHave.Concat(new[] { rep.heroAttr }).ToArray();
            rep.mustHaveMissing = must.Where(m => !(File.Exists(dataDir + "/" + m) || Directory.Exists(dataDir + "/" + m))).ToArray();
            rep.mustHavePresent = rep.mustHaveMissing.Length == 0;
            rep.bakeFilesFound = list.Select(d => d.rel).Where(r => Regex.IsMatch(Path.GetFileName(r), @"af28r01_uvsdf|af28r01_uvwarp|ds29_uv3|_uvsdf_|_uvwarp_") || r.Contains("Build/Design/29R01/bake_kp") || r.Contains("Build/Design/31/white/hero_pkg")).ToArray();
            rep.bakeFilesAbsent = rep.bakeFilesFound.Length == 0;
            rep.noteJa = "Release（Development でない）。PC と --vr は同じ exe。データは <exe>_Data/StreamingAssets/gwdata の下（DS50Shell がプレイヤーの起動時に作業ディレクトリをそこへ移す）。" +
                         "設計50 の exe（Build/Design/50/release/player）は投影の焼き込みのまま残る（記録のため消さない）。体験の exe はこちら。";
        }
    }
}
