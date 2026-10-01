using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.Design30;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Polish29.EditorTools
{
    // 仕上げ29（Q28）：Polish29 の場面（PL29_SinglePlayback.unity・PL29_Release.unity）を Editor の Play モードで再生し、実際の実行の経路
    // （DS30SheetPlayer.OnEnable の読み込み → PL29UkiyoeHero が面の座標と材質を付ける → DS30SinglePlayback が τ を進める）で、
    // 主役波が視点によらない立体の材質（PL29 Ukiyoe Keypose）で描かれることを確かめる。設計30 の DS30PlayModeCheck の形を写した。
    //   ・毎フレーム：実時間・フレーム・t・τ・主役波の材質のシェーダー名・PL29UkiyoeHero.Applied・メッシュの UV4 の数・焼き込みのパス（sdfPath・warpPath）。
    //   ・t が 6・9・10.5・12 s を過ぎた最初のフレームで、原画視点と（あれば）体験の HMD のカメラの画を 960 × 540 で保存する。
    //   ・体験の場面（PL29_Release）は、入口の画面に 3 s いたら Enter と同じ DS50Shell.Begin を反射で呼んで進め（設計50 の自動の試しの仮想のキーは
    //     batchmode の Editor では届かなかった）、共通時計の大波の時刻で撮り、終わりの画面に入って 1.5 s で閉じる。
    // 実行：run_pl29_unity.ps1 -NoQuit なしで -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Extra "-pl29Scene <場面> -pl29Out <出力> [--ds50auto main]"
    // batchmode ではプレイヤーのループが自分で回らないので、EditorApplication.update ごとに QueuePlayerLoopUpdate で回す。上限の実時間で打ち切る（終了コード 2）。
    // PC の Editor（batchmode）で、HMD 実機ではない。
    [InitializeOnLoad]
    public static class PL29PlayModeCheck
    {
        const string Key = "PL29PlayModeCheck";
        static readonly List<string> rows = new List<string>();
        static readonly HashSet<string> shots = new HashSet<string>();
        static readonly List<string> shotFiles = new List<string>();
        static double holdSince = -1;
        static int lastFrame = -1, polls = 0;
        static bool sawApplied, sawShader, sawEmptyBake = true, begun;
        static string shaderName = "";

        static PL29PlayModeCheck()
        {
            if (SessionState.GetBool(Key + ".active", false)) EditorApplication.update += Poll;
        }

        static string Arg(string name, string def)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return def;
        }

        public static void Run()
        {
            string scene = Arg("-pl29Scene", PL29Setup.SceneSingle);
            string od = Arg("-pl29Out", "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/after/playmode");
            float limit = float.Parse(Arg("-pl29Limit", "240"), CultureInfo.InvariantCulture);
            Directory.CreateDirectory(od);
            EditorSceneManager.OpenScene(scene, OpenSceneMode.Single);
            SessionState.SetBool(Key + ".active", true);
            SessionState.SetString(Key + ".out", Path.GetFullPath(od));
            SessionState.SetString(Key + ".scene", scene);
            SessionState.SetFloat(Key + ".limit", limit);
            SessionState.SetFloat(Key + ".start", (float)EditorApplication.timeSinceStartup);
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static void Poll()
        {
            double now = EditorApplication.timeSinceStartup;
            double start = SessionState.GetFloat(Key + ".start", (float)now);
            string od = SessionState.GetString(Key + ".out", "");
            float limit = SessionState.GetFloat(Key + ".limit", 240f);
            if (now - start > limit) { Finish(od, "打ち切り（" + limit + " s）", 2); return; }
            if (!EditorApplication.isPlaying) return;
            if (!Application.runInBackground) Application.runInBackground = true;
            EditorApplication.QueuePlayerLoopUpdate();
            polls++;
            if (Time.frameCount == lastFrame)
            {
                if (polls > 50) { if (!EditorApplication.isPaused) EditorApplication.isPaused = true; EditorApplication.Step(); }
                return;
            }
            lastFrame = Time.frameCount;
            var pb = UnityEngine.Object.FindAnyObjectByType<DS30SinglePlayback>();
            if (pb == null) return;
            var hero = pb.sheets.FirstOrDefault(s => s != null && s.sheetName == "hero");
            var uk = hero != null ? hero.GetComponent<PL29UkiyoeHero>() : null;
            var r = hero != null ? hero.Surface : null;
            shaderName = r != null && r.sharedMaterial != null ? r.sharedMaterial.shader.name : "";
            bool applied = uk != null && uk.Applied;
            int uv4 = 0;
            if (hero != null && hero.SurfaceMesh != null) { var l = new List<Vector4>(); hero.SurfaceMesh.GetUVs(4, l); uv4 = l.Count; }
            if (applied) sawApplied = true;
            if (shaderName == "GreatWave/Polish29/PL29 Ukiyoe Keypose") sawShader = true;
            if (hero != null && (!string.IsNullOrEmpty(hero.sdfPath) || !string.IsNullOrEmpty(hero.warpPath))) sawEmptyBake = false;
            var clk0 = GreatWave.ArtFirst.GWClock.Active;
            rows.Add(string.Join(",", (now - start).ToString("F4", CultureInfo.InvariantCulture), Time.frameCount.ToString(), pb.CurrentState.ToString(),
                clk0 != null ? clk0.ExperienceSeconds.ToString("R", CultureInfo.InvariantCulture) : "", clk0 != null ? clk0.WaveSeconds.ToString("R", CultureInfo.InvariantCulture) : "",
                pb.T.ToString("R", CultureInfo.InvariantCulture), double.IsNaN(pb.Tau) ? "" : pb.Tau.ToString("R", CultureInfo.InvariantCulture),
                shaderName, applied ? "1" : "0", uv4.ToString(), hero != null ? hero.sdfPath : "", hero != null ? hero.warpPath : ""));
            // 体験の場面（DS50Shell がある）では、共通時計の大波の時刻で撮り、終わりの画面に入って 1.5 s で閉じる。単発再生の場面では再生器の t と静止で。
            var shell = UnityEngine.Object.FindAnyObjectByType<GreatWave.Design50.DS50Shell>();
            var clk = GreatWave.ArtFirst.GWClock.Active;
            bool exp = shell != null && clk != null;
            double tw = exp ? clk.WaveSeconds : pb.T;
            if (exp && shell.State == GreatWave.Design50.DS50Shell.ShellState.Entry)
            {
                tw = -1;   // 入口の画面の間は撮らない
                // 入口の画面に 3 s いたら、Enter と同じ DS50Shell.Begin を反射で呼ぶ（設計50 の自動の試しの仮想のキーは batchmode の Editor では届かなかった）
                if (now - start > 3.0 && !begun)
                {
                    var mi = typeof(GreatWave.Design50.DS50Shell).GetMethod("Begin", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
                    if (mi != null) { mi.Invoke(shell, new object[] { "pl29_check" }); begun = true; }
                }
            }
            foreach (var mark in new[] { 6.0, 9.0, 10.5, 12.0 })
            {
                string nm = "t" + ((int)Math.Round(mark * 10)).ToString("000");
                if (tw >= mark - 1e-9 && !shots.Contains(nm)) { shots.Add(nm); Shot(od, nm + "_T" + tw.ToString("00.000", CultureInfo.InvariantCulture)); }
            }
            bool done = exp ? (shell.State == GreatWave.Design50.DS50Shell.ShellState.End || shell.State == GreatWave.Design50.DS50Shell.ShellState.Quitting)
                            : pb.CurrentState == DS30SinglePlayback.State.Holding;
            if (done)
            {
                if (holdSince < 0) holdSince = now;
                if (now - holdSince > 1.5) { Shot(od, "end_T" + tw.ToString("00.000", CultureInfo.InvariantCulture)); Finish(od, exp ? "体験の終わりの画面に入って 1.5 s" : "静止に入って 1.5 s", 0); }
            }
        }

        static void Shot(string od, string name)
        {
            var cams = new List<(string, Camera)>();
            var pc = GameObject.Find("DS27 カメラ")?.transform.Find("DS27 painting")?.GetComponent<Camera>();
            if (pc != null) cams.Add(("painting", pc));
            var shell = UnityEngine.Object.FindAnyObjectByType<GreatWave.Design50.DS50Shell>();
            if (shell != null && shell.hmdCamera != null) cams.Add(("hmd", shell.hmdCamera));
            foreach (var (tag, cam) in cams)
            {
                var rt = new RenderTexture(960, 540, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                var prev = cam.targetTexture; var cf = cam.clearFlags; var bg = cam.backgroundColor; var asp = cam.aspect;
                if (tag == "painting") { cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color32(249, 232, 196, 255); }
                cam.aspect = 960f / 540f;
                cam.targetTexture = rt; cam.Render(); cam.targetTexture = prev;
                cam.clearFlags = cf; cam.backgroundColor = bg; cam.aspect = asp;
                var res = new RenderTexture(960, 540, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                Graphics.Blit(rt, res);
                var tex = new Texture2D(960, 540, TextureFormat.RGB24, false);
                RenderTexture.active = res; tex.ReadPixels(new Rect(0, 0, 960, 540), 0, 0); tex.Apply(); RenderTexture.active = null;
                var p = Path.Combine(od, "pl29_playmode_" + tag + "_" + name + ".png");
                File.WriteAllBytes(p, tex.EncodeToPNG());
                shotFiles.Add(p);
                UnityEngine.Object.Destroy(tex); rt.Release(); res.Release(); UnityEngine.Object.Destroy(rt); UnityEngine.Object.Destroy(res);
            }
        }

        static void Finish(string od, string why, int code)
        {
            EditorApplication.update -= Poll;
            SessionState.EraseBool(Key + ".active");
            if (!string.IsNullOrEmpty(od))
            {
                var sb = new StringBuilder("realtime_s,frame,state,clock_experience_s,clock_wave_s,t,tau,hero_shader,pl29_applied,mesh_uv4_count,hero_sdfPath,hero_warpPath\n");
                foreach (var r in rows) sb.AppendLine(r);
                File.WriteAllText(Path.Combine(od, "pl29_playmode.csv"), sb.ToString());
                var j = new StringBuilder();
                j.Append("{\n \"scene\": \"" + SessionState.GetString(Key + ".scene", "") + "\",\n \"end\": \"" + why + "\",\n \"rows\": " + rows.Count +
                         ",\n \"sawPl29Shader\": " + (sawShader ? "true" : "false") + ",\n \"sawApplied\": " + (sawApplied ? "true" : "false") +
                         ",\n \"bakePathsEmptyAllFrames\": " + (sawEmptyBake ? "true" : "false") + ",\n \"lastHeroShader\": \"" + shaderName + "\",\n \"shots\": [" +
                         string.Join(", ", shotFiles.Select(s => "\"" + s.Replace("\\", "/") + "\"")) + "]\n}\n");
                File.WriteAllText(Path.Combine(od, "pl29_playmode.json"), j.ToString(), new UTF8Encoding(false));
            }
            UnityEngine.Debug.Log("PL29_PLAYMODE_DONE " + why + " rows=" + rows.Count + " shader=" + shaderName + " applied=" + sawApplied);
            EditorApplication.Exit(code);
        }
    }
}
