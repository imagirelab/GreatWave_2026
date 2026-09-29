using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design31;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design34.EditorTools
{
    // 設計34 Unity の部：保存した 3 層の場面（DS34_ThreeLayers.unity）を Editor の Play モードで 1 回再生し、実際の実行の経路
    // （DS30SinglePlayback.Update の Tick(Time.deltaTime) → GWClock → DS34ClawPlayer・DS31InstancedParticles の Update → DS34LayerSet の Update）で、
    // 毎フレーム 3 層が受け取った時刻を ds34_playmode.csv に書く（再生器の t、GWClock の秒、主役波の τ と τ(t)、爪の t とコマの位置、飛沫の t）。
    // 静止（t*）に入った後、層の入切を 1 つずつ変えて原画視点を 960 × 540 で描く（全部 → 白の帯を切る → 爪も切る → 飛沫も切る → 全部に戻す）。
    // 飛沫は Play モードでは Graphics.DrawMeshInstancedProcedural で描かれるが、この検査の手動の camera.Render には CommandBuffer（AddTo）で入れる。
    // 実行：run_ds34_unity.ps1 -NoQuit -Method GreatWave.Design34.EditorTools.DS34PlayModeCheck.Run -Log playmode -Extra "-ds34Out Build/Design/34/unity3/playmode"
    // batchmode ではプレイヤーのループが自分で回らないので、EditorApplication.update ごとに QueuePlayerLoopUpdate で 1 フレームずつ回す（設計30 と同じ）。
    [InitializeOnLoad]
    public static class DS34PlayModeCheck
    {
        const string Key = "DS34PlayModeCheck";
        static readonly List<string> rows = new List<string>();
        static readonly HashSet<string> shots = new HashSet<string>();
        static double holdSince = -1;
        static int lastFrame = -1, polls = 0, stage = 0;

        static DS34PlayModeCheck()
        {
            if (SessionState.GetBool(Key + ".active", false)) EditorApplication.update += Poll;
        }

        public static void Run()
        {
            var a = Environment.GetCommandLineArgs();
            string od = "Build/Design/34/unity3/playmode";
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == "-ds34Out") od = a[i + 1];
            Directory.CreateDirectory(od);
            EditorSceneManager.OpenScene(DS34Render.Scene34, OpenSceneMode.Single);
            SessionState.SetBool(Key + ".active", true);
            SessionState.SetString(Key + ".out", Path.GetFullPath(od));
            SessionState.SetFloat(Key + ".start", (float)EditorApplication.timeSinceStartup);
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static void Poll()
        {
            double now = EditorApplication.timeSinceStartup;
            double start = SessionState.GetFloat(Key + ".start", (float)now);
            string od = SessionState.GetString(Key + ".out", "");
            if (now - start > 150) { Finish(od, "打ち切り（150 s）", 2); return; }
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
            var pb = UnityEngine.Object.FindFirstObjectByType<DS30SinglePlayback>();
            var ls = UnityEngine.Object.FindFirstObjectByType<DS34LayerSet>();
            if (pb == null || ls == null || ls.claws == null || ls.spray == null || ls.heroSheet == null) return;
            var clk = pb.clock != null ? pb.clock : GWClock.Active;
            double warpTau = pb.Warp != null ? pb.Warp.TauAt(pb.T) : double.NaN;
            rows.Add(string.Join(",", (now - start).ToString("F4", CultureInfo.InvariantCulture), Time.frameCount.ToString(), Time.deltaTime.ToString("R", CultureInfo.InvariantCulture),
                pb.CurrentState.ToString(), R(pb.T), clk != null ? R(clk.Seconds) : "", R(ls.heroSheet.AppliedTau), R(warpTau),
                R(ls.claws.AppliedT), R(ls.claws.AppliedFrame), ls.claws.AppliedOnGrid ? "1" : "0", R(ls.spray.AppliedT),
                ls.whiteBand ? "1" : "0", ls.clawsOn ? "1" : "0", ls.sprayOn ? "1" : "0",
                ls.claws.GetComponent<MeshRenderer>().enabled ? "1" : "0", ls.spray.drawInPlayMode ? "1" : "0"));
            foreach (var mark in new[] { 8.0, 10.0, 11.0 })
            {
                string nm = "t" + mark.ToString("00", CultureInfo.InvariantCulture);
                if (pb.T >= mark - 1e-9 && !shots.Contains(nm)) { shots.Add(nm); Shot(od, ls, nm + "_T" + pb.T.ToString("00.000", CultureInfo.InvariantCulture)); }
            }
            if (pb.CurrentState == DS30SinglePlayback.State.Holding)
            {
                if (holdSince < 0) holdSince = now;
                double h = now - holdSince;
                // 静止の中で、層の入切を 1 つずつ変える（次のフレームの DS34LayerSet.Update が適用し、その後で描く）
                if (stage == 0 && h > 0.3) { Shot(od, ls, "hold_1_all"); ls.whiteBand = false; stage = 1; }
                else if (stage == 1 && h > 0.6) { Shot(od, ls, "hold_2_white_off"); ls.clawsOn = false; stage = 2; }
                else if (stage == 2 && h > 0.9) { Shot(od, ls, "hold_3_white_claws_off"); ls.sprayOn = false; stage = 3; }
                else if (stage == 3 && h > 1.2) { Shot(od, ls, "hold_4_all_off"); ls.whiteBand = true; ls.clawsOn = true; ls.sprayOn = true; stage = 4; }
                else if (stage == 4 && h > 1.5) { Shot(od, ls, "hold_5_all_on_again"); Finish(od, "静止に入って 1.5 s（層の入切 4 回）", 0); }
            }
        }

        static string R(double x) => double.IsNaN(x) ? "" : x.ToString("R", CultureInfo.InvariantCulture);

        static void Shot(string od, DS34LayerSet ls, string name)
        {
            var cam = GameObject.Find("DS27 カメラ")?.transform.Find("DS27 painting")?.GetComponent<Camera>();
            if (cam == null) return;
            CommandBuffer cb = null;
            if (ls.sprayOn) { cb = new CommandBuffer { name = "DS34 飛沫（検査の描画）" }; ls.spray.AddTo(cb); cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb); }
            var rt = new RenderTexture(960, 540, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
            var prev = cam.targetTexture; var cf = cam.clearFlags; var bg = cam.backgroundColor; var asp = cam.aspect;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color32(249, 232, 196, 255); cam.aspect = 960f / 540f;
            cam.targetTexture = rt; cam.Render(); cam.targetTexture = prev;
            cam.clearFlags = cf; cam.backgroundColor = bg; cam.aspect = asp;
            if (cb != null) { cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cb.Release(); }
            var res = new RenderTexture(960, 540, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            Graphics.Blit(rt, res);
            var tex = new Texture2D(960, 540, TextureFormat.RGB24, false);
            RenderTexture.active = res; tex.ReadPixels(new Rect(0, 0, 960, 540), 0, 0); tex.Apply(); RenderTexture.active = null;
            File.WriteAllBytes(Path.Combine(od, "ds34_playmode_painting_" + name + ".png"), tex.EncodeToPNG());
            UnityEngine.Object.Destroy(tex); rt.Release(); res.Release(); UnityEngine.Object.Destroy(rt); UnityEngine.Object.Destroy(res);
        }

        static void Finish(string od, string why, int code)
        {
            EditorApplication.update -= Poll;
            SessionState.EraseBool(Key + ".active");
            if (!string.IsNullOrEmpty(od))
            {
                var sb = new StringBuilder("realtime_s,frame,deltaTime,state,t,clock_s,hero_tau,warp_tau,claw_t,claw_frame,claw_on_grid,spray_t,white_band,claws_on,spray_on,claw_renderer,spray_draw\n");
                foreach (var r in rows) sb.AppendLine(r);
                File.WriteAllText(Path.Combine(od, "ds34_playmode.csv"), sb.ToString());
                File.WriteAllText(Path.Combine(od, "ds34_playmode_end.txt"), why + "\n" + "rows=" + rows.Count + "\n");
            }
            UnityEngine.Debug.Log("DS34_PLAYMODE_DONE " + why + " rows=" + rows.Count);
            EditorApplication.Exit(code);
        }
    }
}
