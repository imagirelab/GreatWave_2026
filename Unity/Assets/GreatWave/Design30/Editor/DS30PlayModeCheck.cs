using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Design30.EditorTools
{
    // 設計30 第B部：保存した単発再生の場面（DS30_SinglePlayback.unity）を Editor の Play モードで 1 回再生し、実際の実行の経路
    // （DS30SheetPlayer.OnEnable の読み込み → DS30SinglePlayback.Start → Update の Tick(Time.deltaTime)）で、待機 → 再生 → t* で静止まで
    // 進むことを記録する。毎フレームの実時間・Time.deltaTime・状態・t・τ・各シートの τ を ds30_playmode.csv に書き、
    // t が 2・6・12 s を過ぎた最初のフレームと静止の 1 s 後に原画視点を 960 × 540 で描いて保存する。PC の Editor（batchmode）で、HMD ではない。
    // 実行：run_ds30_unity.ps1 -NoQuit -Method GreatWave.Design30.EditorTools.DS30PlayModeCheck.Run -Log playmode -Extra "-ds30Out Build/Design/30/unity/playmode"
    // batchmode ではプレイヤーのループが自分で回らないので、EditorApplication.update ごとに QueuePlayerLoopUpdate で 1 フレームずつ回す。
    // 終わると EditorApplication.Exit で閉じる（90 s の実時間で打ち切り、終了コード 2）。
    [InitializeOnLoad]
    public static class DS30PlayModeCheck
    {
        const string Key = "DS30PlayModeCheck";
        static readonly List<string> rows = new List<string>();
        static readonly HashSet<string> shots = new HashSet<string>();
        static double holdSince = -1;
        static int lastFrame = -1, polls = 0;

        static DS30PlayModeCheck()
        {
            if (SessionState.GetBool(Key + ".active", false)) EditorApplication.update += Poll;
        }

        public static void Run()
        {
            var a = Environment.GetCommandLineArgs();
            string od = "Build/Design/30/unity/playmode";
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == "-ds30Out") od = a[i + 1];
            Directory.CreateDirectory(od);
            EditorSceneManager.OpenScene(DS30Render.ScenePath30, OpenSceneMode.Single);
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
            if (now - start > 90) { Finish(od, "打ち切り（90 s）", 2); return; }
            if (!EditorApplication.isPlaying) return;
            // batchmode ではプレイヤーのループが自分では回らないので、Editor の更新ごとに 1 回ずつ回す
            // batchmode の Editor は前面にならないので、実行中だけ runInBackground を入れる（プロジェクトの設定は変えない）
            if (!Application.runInBackground) Application.runInBackground = true;
            EditorApplication.QueuePlayerLoopUpdate();
            polls++;
            if (Time.frameCount == lastFrame)
            {
                // それでも進まないときは、一時停止にして 1 フレームずつ進める
                if (polls > 50) { if (!EditorApplication.isPaused) EditorApplication.isPaused = true; EditorApplication.Step(); }
                return;
            }
            lastFrame = Time.frameCount;
            var pb = UnityEngine.Object.FindFirstObjectByType<DS30SinglePlayback>();
            if (pb == null) return;
            var sheetTau = string.Join(";", pb.sheets.Select(s => s == null ? "" : s.AppliedTau.ToString("R", CultureInfo.InvariantCulture)));
            rows.Add(string.Join(",", (now - start).ToString("F4", CultureInfo.InvariantCulture), Time.frameCount.ToString(), Time.deltaTime.ToString("R", CultureInfo.InvariantCulture),
                pb.CurrentState.ToString(), pb.T.ToString("R", CultureInfo.InvariantCulture), double.IsNaN(pb.Tau) ? "" : pb.Tau.ToString("R", CultureInfo.InvariantCulture), sheetTau));
            foreach (var mark in new[] { 2.0, 6.0, 12.0 })
            {
                string nm = "t" + mark.ToString("00", CultureInfo.InvariantCulture);
                if (pb.T >= mark - 1e-9 && !shots.Contains(nm)) { shots.Add(nm); Shot(od, nm + "_T" + pb.T.ToString("00.000", CultureInfo.InvariantCulture)); }
            }
            if (pb.CurrentState == DS30SinglePlayback.State.Holding)
            {
                if (holdSince < 0) holdSince = now;
                if (now - holdSince > 1.0) { Shot(od, "hold_plus1s_T" + pb.T.ToString("00.000", CultureInfo.InvariantCulture)); Finish(od, "静止に入って 1 s", 0); }
            }
        }

        static void Shot(string od, string name)
        {
            var cam = GameObject.Find("DS27 カメラ")?.transform.Find("DS27 painting")?.GetComponent<Camera>();
            if (cam == null) return;
            var rt = new RenderTexture(960, 540, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
            var prev = cam.targetTexture; var cf = cam.clearFlags; var bg = cam.backgroundColor; var asp = cam.aspect;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color32(249, 232, 196, 255); cam.aspect = 960f / 540f;
            cam.targetTexture = rt; cam.Render(); cam.targetTexture = prev;
            cam.clearFlags = cf; cam.backgroundColor = bg; cam.aspect = asp;
            var res = new RenderTexture(960, 540, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            Graphics.Blit(rt, res);
            var tex = new Texture2D(960, 540, TextureFormat.RGB24, false);
            RenderTexture.active = res; tex.ReadPixels(new Rect(0, 0, 960, 540), 0, 0); tex.Apply(); RenderTexture.active = null;
            File.WriteAllBytes(Path.Combine(od, "ds30_playmode_painting_" + name + ".png"), tex.EncodeToPNG());
            UnityEngine.Object.Destroy(tex); rt.Release(); res.Release(); UnityEngine.Object.Destroy(rt); UnityEngine.Object.Destroy(res);
        }

        static void Finish(string od, string why, int code)
        {
            EditorApplication.update -= Poll;
            SessionState.EraseBool(Key + ".active");
            if (!string.IsNullOrEmpty(od))
            {
                var sb = new StringBuilder("realtime_s,frame,deltaTime,state,t,tau,sheet_tau\n");
                foreach (var r in rows) sb.AppendLine(r);
                File.WriteAllText(Path.Combine(od, "ds30_playmode.csv"), sb.ToString());
                File.WriteAllText(Path.Combine(od, "ds30_playmode_end.txt"), why + "\n" + "rows=" + rows.Count + "\n");
            }
            UnityEngine.Debug.Log("DS30_PLAYMODE_DONE " + why + " rows=" + rows.Count);
            EditorApplication.Exit(code);
        }
    }
}
