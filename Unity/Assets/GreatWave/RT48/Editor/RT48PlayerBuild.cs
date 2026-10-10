using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace GreatWave.RT48.EditorTools
{
    // RT48：Windows の Release プレイヤー（Development でない）を作る。場面は RT48_Playback.unity だけを引数で渡し、EditorBuildSettings は変えない。
    //   -executeMethod GreatWave.RT48.EditorTools.RT48PlayerBuild.BuildAndExit -rt48out <フォルダー>（既定 Unity/Build/RT48/unity/player）
    // PlayerSettings.enableFrameTimingStats はビルドの間だけ true にし、finally で元へ戻す（計画 C7）。ProjectSettings の写しと
    // 前後の SHA-256 の比べ・バイト単位の戻しは、外の Tools/GWWaveGen/rt48/u_unity.ps1 が Unity の前後で行う。
    public static class RT48PlayerBuild
    {
        [Serializable]
        class Report
        {
            public string unity, utc, scene, playerPath, buildResult, buildOptions, noteJa;
            public bool frameTimingStatsBefore, frameTimingStatsDuringBuild, frameTimingStatsRestored;
            public long totalSize; public double buildSeconds;
            public string[] buildErrors, buildWarnings, playerFiles;
        }

        public static void BuildAndExit()
        {
            int code = 1;
            try { code = Build() ? 0 : 2; }
            catch (Exception e) { Debug.LogError("RT48_BUILD_EXCEPTION " + e); code = 1; }
            EditorApplication.Exit(code);
        }

        public static bool Build()
        {
            if (!File.Exists(RT48SceneBuilder.ScenePath)) RT48SceneBuilder.Build();
            string outDir = RT48Playback.Arg("-rt48out", Path.Combine(RT48SceneBuilder.UnityOut, "player"));
            outDir = Path.GetFullPath(outDir);
            if (!outDir.Replace('\\', '/').Contains("/Build/RT48/")) throw new InvalidOperationException("RT48 の外へは書きません：" + outDir);
            Directory.CreateDirectory(outDir);
            var rep = new Report { unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = RT48SceneBuilder.ScenePath };
            bool prev = PlayerSettings.enableFrameTimingStats;
            rep.frameTimingStatsBefore = prev;
            BuildReport br = null;
            try
            {
                PlayerSettings.enableFrameTimingStats = true;
                rep.frameTimingStatsDuringBuild = PlayerSettings.enableFrameTimingStats;
                var opts = new BuildPlayerOptions
                {
                    scenes = new[] { RT48SceneBuilder.ScenePath },
                    locationPathName = Path.Combine(outDir, "RT48.exe"),
                    target = BuildTarget.StandaloneWindows64,
                    targetGroup = BuildTargetGroup.Standalone,
                    options = BuildOptions.None
                };
                rep.buildOptions = opts.options.ToString();
                br = BuildPipeline.BuildPlayer(opts);
            }
            finally
            {
                PlayerSettings.enableFrameTimingStats = prev;
                AssetDatabase.SaveAssets();
                rep.frameTimingStatsRestored = PlayerSettings.enableFrameTimingStats == prev;
            }
            rep.playerPath = Path.Combine(outDir, "RT48.exe");
            rep.buildResult = br.summary.result.ToString();
            rep.totalSize = (long)br.summary.totalSize;
            rep.buildSeconds = br.summary.totalTime.TotalSeconds;
            var msgs = br.steps.SelectMany(s => s.messages).ToArray();
            rep.buildErrors = msgs.Where(m => m.type == LogType.Error || m.type == LogType.Exception).Select(m => m.content).ToArray();
            rep.buildWarnings = msgs.Where(m => m.type == LogType.Warning).Select(m => m.content).Take(50).ToArray();
            rep.playerFiles = Directory.GetFiles(outDir, "*", SearchOption.AllDirectories).Select(f => f.Substring(outDir.Length + 1).Replace('\\', '/') + " " + new FileInfo(f).Length).OrderBy(s => s).Take(400).ToArray();
            rep.noteJa = "BuildOptions.None の Release プレイヤー。enableFrameTimingStats はビルドの間だけ true にし、finally で元へ戻した。焼きは -rt48data で読む（既定は場面に書いた Unity/Build/RT48/bake）。";
            File.WriteAllText(Path.Combine(outDir, "rt48_build_report.json"), JsonUtility.ToJson(rep, true));
            Debug.Log("RT48_BUILD_DONE result=" + rep.buildResult + " size=" + rep.totalSize + " restored=" + rep.frameTimingStatsRestored);
            return br.summary.result == BuildResult.Succeeded && rep.frameTimingStatsRestored;
        }
    }
}
