using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.Design30;
using GreatWave.Design31;
using GreatWave.Design34;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using Debug = UnityEngine.Debug;

namespace GreatWave.Design35.EditorTools
{
    // 設計35 variants の部：
    //  BuildAll：設計34 の場面 DS34_ThreeLayers.unity を DS35_Perf.unity へ複製し（設計34 の場面は読むだけ）、計測器 DS35PerfRunner と 3 版の表を置き、
    //    美術優先32 と同じ Release（BuildOptions.None）の Windows プレイヤーを作る。enableFrameTimingStats はビルドの間だけ true にし、finally で戻す
    //    （ProjectSettings のバイトの復元は外側の run_ds35_unity.ps1 が確かめる）。爪と飛沫のシェーダーは実行時に Shader.Find で探すので、
    //    instancing を有効にした参照用の材質 2 つを計測器の keepShaders に入れてプレイヤーへ含める。
    //  RenderVideos：同じ場面を Editor で開き（保存しない）、3 版 × 原画視点・座席 v1 の 1920×1080・30 fps・t 0〜14 s の動画と、
    //    t 8・10・11.5・12 s の静止画を撮る（設計34 の DS34Render の動画と同じ描き方：camera.Render、8×MSAA、飛沫はカメラの CommandBuffer）。
    public static class DS35Build
    {
        const string Scene34 = "Assets/GreatWave/Design34/Scenes/DS34_ThreeLayers.unity";
        public const string ScenePerf = "Assets/GreatWave/Design35/Scenes/DS35_Perf.unity";
        const string MatDir = "Assets/GreatWave/Design35/Materials";
        const string OutRoot = "Build/Design/35/variants";
        const string PlayerPath = OutRoot + "/player/DS35Perf.exe";
        const string Repo = "G:/Unity/GreatWave_2026_Fresh/Unity/";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);

        public static List<DS35PerfRunner.Variant> Variants => new List<DS35PerfRunner.Variant>
        {
            new DS35PerfRunner.Variant { name = "v1_list", nameJa = "一覧どおり", clawLayout = Repo + "Build/Design/33/claws/ds33_claw_layout.json", sprayData = Repo + "Build/Design/31/spray/ds31_spray_frames.json" },
            new DS35PerfRunner.Variant { name = "v2_light", nameJa = "数を減らした軽量版", clawLayout = Repo + "Build/Design/35/variants/data/v2_light/claw_layout.json", sprayData = Repo + "Build/Design/35/variants/data/v2_light/spray_frames.json" },
            new DS35PerfRunner.Variant { name = "v3_exag", nameJa = "大きさ・寿命を誇張した版", clawLayout = Repo + "Build/Design/35/variants/data/v3_exag/claw_layout.json", sprayData = Repo + "Build/Design/35/variants/data/v3_exag/spray_frames.json" },
        };

        static string[] Protected => new[] {
            Scene34, "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs", "Assets/GreatWave/Design34/Scripts/DS34LayerSet.cs",
            "Assets/GreatWave/Design34/Shaders/DS34_Claw_Unlit.shader", "Assets/GreatWave/Design31/Scripts/DS31InstancedParticles.cs",
            "Assets/GreatWave/Design31/Shaders/DS31_Spray_Unlit.shader", "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs",
            "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs", "Assets/GreatWave/Design31/Scenes/DS31_WhiteSpray.unity",
            "Build/Design/33/claws/ds33_claw_layout.json", "Build/Design/33/claws/ds33_claw_frames_f32.bin",
            "Build/Design/31/spray/ds31_spray_frames.json", "Build/Design/31/spray/ds31_spray_frames.bin" };

        [Serializable] class BuildReportJ
        {
            public string unity, utc, scene, scene34Sha256Before, scene34Sha256After, scenePerfSha256, playerPath, buildResult, buildOptions, noteJa;
            public bool frameTimingStatsBefore, frameTimingStatsDuringBuild, frameTimingStatsRestored, protectedUnchanged;
            public long totalSize; public double buildSeconds;
            public string[] buildErrors, playerFiles, changedProtected, keepMaterials;
        }

        [Serializable] class VideoRec { public string variant, view, path, sha256, ffmpegError; public int frames, fps; public float seconds; public string[] stills; }
        [Serializable] class VideoReport
        {
            public string unity, device, graphicsApi, utc, noteJa; public bool protectedUnchanged; public string[] changedProtected;
            public VideoRec[] videos; public string[] variantClawSha, variantSpraySha; public int[] variantClaws, variantSpray;
        }

        static Material KeepMat(string path, string shaderName)
        {
            var sh = Shader.Find(shaderName);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + shaderName);
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
            m.shader = sh; m.enableInstancing = true;
            EditorUtility.SetDirty(m);
            return m;
        }

        public static void BuildAll()
        {
            var rep = new BuildReportJ { unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePerf };
            var before = Protected.ToDictionary(p => p, Sha);
            rep.scene34Sha256Before = before[Scene34];
            Directory.CreateDirectory(Path.GetDirectoryName(ScenePerf));
            Directory.CreateDirectory(MatDir);
            AssetDatabase.Refresh();
            if (File.Exists(ScenePerf)) AssetDatabase.DeleteAsset(ScenePerf);
            if (!AssetDatabase.CopyAsset(Scene34, ScenePerf)) throw new InvalidOperationException("場面を複製できません");
            var mClaw = KeepMat(MatDir + "/DS35_Keep_ClawUnlit.mat", DS34ClawPlayer.ShaderName);
            var mSpray = KeepMat(MatDir + "/DS35_Keep_SprayUnlit.mat", DS31InstancedParticles.ShaderName);
            AssetDatabase.SaveAssets();
            rep.keepMaterials = new[] { AssetDatabase.GetAssetPath(mClaw), AssetDatabase.GetAssetPath(mSpray) };

            var scene = EditorSceneManager.OpenScene(ScenePerf, OpenSceneMode.Single);
            var go = new GameObject("DS35 計測器（3 版の最大密度の区間、美術優先32 の測り方）");
            var run = go.AddComponent<DS35PerfRunner>();
            run.variants = Variants;
            run.keepShaders = new[] { mClaw, mSpray };
            var play = UnityEngine.Object.FindAnyObjectByType<DS30SinglePlayback>(FindObjectsInactive.Include);
            if (play == null) throw new InvalidOperationException("DS30SinglePlayback がありません");
            play.enabled = false;
            var layers = UnityEngine.Object.FindAnyObjectByType<DS34LayerSet>(FindObjectsInactive.Include);
            if (layers != null) layers.keyboardToggles = false;
            if (!EditorSceneManager.SaveScene(scene)) throw new InvalidOperationException("場面を保存できません");
            rep.scenePerfSha256 = Sha(ScenePerf);

            bool prev = PlayerSettings.enableFrameTimingStats;
            rep.frameTimingStatsBefore = prev;
            var playerDir = Path.GetDirectoryName(PlayerPath);
            if (Directory.Exists(playerDir)) Directory.Delete(playerDir, true);
            Directory.CreateDirectory(playerDir);
            BuildReport br = null;
            try
            {
                PlayerSettings.enableFrameTimingStats = true;
                rep.frameTimingStatsDuringBuild = PlayerSettings.enableFrameTimingStats;
                var opts = new BuildPlayerOptions
                {
                    scenes = new[] { ScenePerf }, locationPathName = PlayerPath,
                    target = BuildTarget.StandaloneWindows64, targetGroup = BuildTargetGroup.Standalone, options = BuildOptions.None
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
            rep.playerPath = Path.GetFullPath(PlayerPath);
            rep.buildResult = br.summary.result.ToString();
            rep.totalSize = (long)br.summary.totalSize;
            rep.buildSeconds = br.summary.totalTime.TotalSeconds;
            rep.buildErrors = br.steps.SelectMany(s => s.messages).Where(m => m.type == LogType.Error || m.type == LogType.Exception).Select(m => m.content).ToArray();
            rep.playerFiles = Directory.Exists(playerDir) ? Directory.GetFiles(playerDir, "*", SearchOption.TopDirectoryOnly).Select(f => Path.GetFileName(f) + " " + new FileInfo(f).Length).OrderBy(s => s).ToArray() : new string[0];
            var after = Protected.ToDictionary(p => p, Sha);
            rep.scene34Sha256After = after[Scene34];
            rep.changedProtected = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.protectedUnchanged = rep.changedProtected.Length == 0;
            rep.noteJa = "BuildOptions.None の Release プレイヤー（美術優先32 と同じ）。enableFrameTimingStats はビルドの間だけ true にし、finally で元へ戻した。設計34 の場面は複製しただけで変えていない。";
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/ds35_build_report.json", JsonUtility.ToJson(rep, true));
            Debug.Log("DS35_BUILD_DONE result=" + rep.buildResult + " protectedUnchanged=" + rep.protectedUnchanged);
            if (br.summary.result != BuildResult.Succeeded) throw new InvalidOperationException("ビルドに失敗しました: " + string.Join(" / ", rep.buildErrors));
            if (!rep.protectedUnchanged) throw new InvalidOperationException("読むだけのファイルが変わりました: " + string.Join(", ", rep.changedProtected));
        }

        // ------------------------------------------------------------------ 動画
        public static void RenderVideos()
        {
            var total = Stopwatch.StartNew();
            var before = Protected.ToDictionary(p => p, Sha);
            string od = OutRoot + "/video_raw";
            Directory.CreateDirectory(od);
            Directory.CreateDirectory(OutRoot + "/stills");
            var rep = new VideoReport { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), utc = DateTime.UtcNow.ToString("O") };
            EditorSceneManager.OpenScene(ScenePerf, OpenSceneMode.Single);
            var play = UnityEngine.Object.FindAnyObjectByType<DS30SinglePlayback>(FindObjectsInactive.Include);
            var claws = UnityEngine.Object.FindAnyObjectByType<DS34ClawPlayer>(FindObjectsInactive.Include);
            var spray = UnityEngine.Object.FindAnyObjectByType<DS31InstancedParticles>(FindObjectsInactive.Include);
            var layers = UnityEngine.Object.FindAnyObjectByType<DS34LayerSet>(FindObjectsInactive.Include);
            var camRoot = GameObject.Find("DS27 カメラ").transform;
            var cams = new Dictionary<string, Camera> { { "painting", camRoot.Find("DS27 painting").GetComponent<Camera>() }, { "seat", camRoot.Find("DS27 seat").GetComponent<Camera>() } };
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
            Shader.SetGlobalFloat("_DS34ClawDiag", 0);
            play.Prepare();
            var vids = new List<VideoRec>();
            var cSha = new List<string>(); var sSha = new List<string>(); var cN = new List<int>(); var sN = new List<int>();
            var stillT = new[] { 8f, 10f, 11.5f, 12f };
            // -ds35Views painting,seat,painting_w0（_w0 は白の帯を切った読み：主役波の白の時間場を白の前の色で塗り、白いのは爪と飛沫だけになる。違いを見るため）
            var views = (ArgOf("-ds35Views") ?? "painting,seat,painting_w0").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            int fps = 30; float tEnd = 14f;
            try
            {
                foreach (var v in Variants)
                {
                    claws.Release(); claws.layoutPath = v.clawLayout; claws.Load();
                    spray.Release(); spray.dataPath = v.sprayData; spray.Load();
                    cSha.Add(claws.FramesSha256); sSha.Add(spray.DataSha256); cN.Add(claws.ClawCount); sN.Add(spray.Count);
                    foreach (var view in views)
                    {
                        var sw = Stopwatch.StartNew();
                        var mp4 = od + "/ds35_" + v.name + "_" + view + "_30fps.mp4";
                        var stills = new List<string>();
                        bool white = !view.EndsWith("_w0");
                        int nf = Encode(play, claws, spray, layers, cams[view.Replace("_w0", "")], white, fps, tEnd, mp4, stillT, OutRoot + "/stills/ds35_" + v.name + "_" + view, stills, out string err);
                        vids.Add(new VideoRec { variant = v.name, view = view, path = Path.GetFullPath(mp4), frames = nf, fps = fps, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = File.Exists(mp4) ? Sha(mp4) : "", stills = stills.ToArray() });
                        Debug.Log("DS35_VIDEO " + v.name + " " + view + " " + sw.Elapsed.TotalSeconds.ToString("F1", CultureInfo.InvariantCulture) + " s err=" + err);
                    }
                }
            }
            finally
            {
                claws.Release(); spray.Release();
            }
            rep.videos = vids.ToArray(); rep.variantClawSha = cSha.ToArray(); rep.variantSpraySha = sSha.ToArray(); rep.variantClaws = cN.ToArray(); rep.variantSpray = sN.ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.changedProtected = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.protectedUnchanged = rep.changedProtected.Length == 0;
            rep.noteJa = "Editor の batchmode の camera.Render（PC オフスクリーン、8×MSAA）。設計34 の動画と同じ描き方。場面は開いただけで保存していない。所要 " + total.Elapsed.TotalSeconds.ToString("F0", CultureInfo.InvariantCulture) + " s";
            var rp = OutRoot + "/ds35_video_report_" + string.Join("_", views) + ".json";
            File.WriteAllText(rp, JsonUtility.ToJson(rep, true));
            Debug.Log("DS35_VIDEOS_DONE n=" + vids.Count + " protectedUnchanged=" + rep.protectedUnchanged);
            if (vids.Any(x => !string.IsNullOrEmpty(x.ffmpegError))) throw new InvalidOperationException("ffmpeg の誤り");
        }

        static string ArgOf(string name)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        static int Encode(DS30SinglePlayback play, DS34ClawPlayer claws, DS31InstancedParticles spray, DS34LayerSet layers, Camera camera, bool white, int fps, float seconds, string mp4,
            float[] stillT, string stillPrefix, List<string> stills, out string err)
        {
            int n = Mathf.RoundToInt(seconds * fps) + 1;
            string outs = string.Format("-vf vflip -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart \"{0}\"", Path.GetFullPath(mp4));
            var psi = new ProcessStartInfo
            {
                FileName = Ffmpeg,
                Arguments = string.Format("-y -loglevel error -f rawvideo -pix_fmt rgb24 -s {0}x{1} -r {2} -i - {3}", W, H, fps, outs),
                UseShellExecute = false, RedirectStandardInput = true, RedirectStandardError = true, CreateNoWindow = true
            };
            var sb = new StringBuilder();
            var cb = new CommandBuffer { name = "DS35 飛沫" };
            spray.AddTo(cb);
            camera.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            var stillFrames = stillT.Select(t => Mathf.RoundToInt(t * fps)).ToArray();
            try
            {
                using (var p = new Process { StartInfo = psi })
                {
                    p.ErrorDataReceived += (s, e) => { if (e.Data != null) lock (sb) sb.AppendLine(e.Data); };
                    p.Start();
                    p.BeginErrorReadLine();
                    var stdin = p.StandardInput.BaseStream;
                    var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
                    var res = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                    rt.Create(); res.Create();
                    var tex = new Texture2D(W, H, TextureFormat.RGB24, false, false);
                    var clear = camera.clearFlags; var bg = camera.backgroundColor; var prev = camera.targetTexture;
                    camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = SkyTop; camera.allowHDR = false; camera.allowMSAA = true;
                    camera.aspect = (float)W / H;
                    try
                    {
                        for (int i = 0; i < n; i++)
                        {
                            double t = i / (double)fps;
                            play.Seek(t); spray.ApplyT(t); claws.ApplyT(t);
                            if (layers != null) { layers.whiteBand = white; layers.clawsOn = true; layers.sprayOn = true; layers.ApplyToggles(); }
                            camera.targetTexture = rt;
                            camera.Render();
                            Graphics.Blit(rt, res);
                            RenderTexture.active = res;
                            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
                            RenderTexture.active = null;
                            var raw = tex.GetRawTextureData();
                            stdin.Write(raw, 0, raw.Length);
                            int si = Array.IndexOf(stillFrames, i);
                            if (si >= 0)
                            {
                                tex.Apply();
                                var path = string.Format(CultureInfo.InvariantCulture, "{0}_t{1:00.00}s.png", stillPrefix, stillT[si]);
                                File.WriteAllBytes(path, tex.EncodeToPNG());
                                stills.Add(Path.GetFullPath(path));
                            }
                        }
                    }
                    finally
                    {
                        stdin.Flush(); stdin.Close();
                        camera.targetTexture = prev; camera.clearFlags = clear; camera.backgroundColor = bg;
                        UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
                        UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
                    }
                    if (!p.WaitForExit(10 * 60 * 1000)) { p.Kill(); throw new InvalidOperationException("ffmpeg が終わりません。"); }
                    p.WaitForExit();
                    lock (sb) err = sb.ToString() + (p.ExitCode != 0 ? " exit=" + p.ExitCode : "");
                }
            }
            finally
            {
                camera.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cb.Release();
                if (layers != null) { layers.whiteBand = true; layers.ApplyToggles(); }
            }
            return n;
        }

        static string Sha(string path)
        {
            using (var s = System.Security.Cryptography.SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
