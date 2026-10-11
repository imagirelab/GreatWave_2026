using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.RT48.EditorTools
{
    // RT48：船の外から見た試しの連番（Editor の batchmode、GPU あり）。体験（船の座席）では見えない所で、
    // 「Unity が描いている波を外から見る」ための絵。再生の部品・描き方・場面は変えない（場面は開くだけで保存しない）。
    //   -executeMethod GreatWave.RT48.EditorTools.RT48OutsideCapture.RunAndExit
    //     -rt48outsource fine  -rt48outdir <出力>  -rt48outviews endon,oblique  [-rt48capfps 60] [-rt48seat 556] [-rt48capfrom t -rt48capto t（試しの時だけ）]
    // 向き（RT48SelfTest の試しの視点と同じ考え）。どちらも −Z の側から +Z を見るので、波は画面の左から右へ進む（r_side.py の絵と同じ向き）：
    //   endon   掃いた面の端（頂の向き Z = −20,000 m）の 70 m 外から +Z を水平に見る。高さ 4.5 m、縦の画角 26°（端の断面で縦 32 m・横 57 m）。
    //           カメラは x の向きだけ頂に付いて動く：X ＝ 焼きの頂の x（前後 12 コマ＝1 s の平均でならした値をコマの中の進みで線形に補間）＋ 8 m − 座席。
    //           手前の端の断面と、奥へ続く同じ形の頂が見える。
    //   oblique 止めたカメラ。座席から 8 m 前・頂の向きに −50 m・高さ 7 m から、座席の 42 m 前・Z = +30 m・高さ 4.5 m を見る（頂の向きから約 23° 振った斜め）。
    //           縦の画角 45°。巻き始めのころから波が画面に入り、船（座席）も入る。
    //   high    止めたカメラ。座席の 20 m 後ろ・頂の向きに −40 m・高さ 15 m（頂より上）から、座席の 45 m 前・Z = +15 m・高さ 4 m を見下ろす。縦の画角 45°。
    //           （oblique は頂より低く、前の面が画面をふさいだので、10/11 12:30 に足した）
    // 出力：<出力>/<向き>/frame_00000.png …、<出力>/<向き>/capture.json（コマごとの時刻・見せるコマ・補間の有無）。字は Python で足す。
    public static class RT48OutsideCapture
    {
        [Serializable] public class FrameRow { public int i; public double t; public int frame; public bool interp; public int reason; public double alpha; public string label; public double heave, pitchDeg, camX; }
        [Serializable]
        public class Cap
        {
            public string schema = "GreatWave.RT48.outsidecapture/1";
            public string view, source, sourceLabel, gpu, graphicsApi, unity, utc, noteJa;
            public double seatX, fps, from, to, vfovDeg;
            public float[] camPos, camLookAt;
            public int width, height, frames;
            public FrameRow[] rows;
            public double seconds;
        }

        public static void RunAndExit()
        {
            int code = 1;
            try { Run(); code = 0; }
            catch (Exception e) { Debug.LogError("RT48_OUTSIDE_EXCEPTION " + e); code = 1; }
            EditorApplication.Exit(code);
        }

        static void Run()
        {
            string srcName = RT48Playback.Arg("-rt48outsource", "fine");
            string outDir = RT48Playback.Arg("-rt48outdir", Path.Combine(RT48SceneBuilder.BuildRoot, "video", "outside_" + srcName));
            string[] views = RT48Playback.Arg("-rt48outviews", "endon,oblique").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            double fps = RT48Playback.ArgD("-rt48capfps", 60);
            double seat = RT48Playback.ArgD("-rt48seat", 556.0);
            const int W = 1920, H = 1080;
            EditorSceneManager.OpenScene(RT48SceneBuilder.ScenePath, OpenSceneMode.Single);
            var pb = UnityEngine.Object.FindAnyObjectByType<RT48Playback>();
            if (pb == null) throw new InvalidOperationException("RT48Playback が場面にありません");
            pb.Initialize(Path.Combine(RT48SceneBuilder.DataRoot, srcName));
            if (pb.Source == null) throw new InvalidOperationException("元を読めません：" + pb.LoadError);
            pb.SetSeat(seat);
            pb.DesktopViewEnabled = false;
            Debug.Log("RT48_OUTSIDE source=" + pb.Source.Describe() + " seat=" + seat + " end=" + pb.TimeEnd.ToString("F4", CultureInfo.InvariantCulture));
            foreach (var v0 in views)
            {
                var v = v0.Trim();
                var sw = System.Diagnostics.Stopwatch.StartNew();
                Vector3 pos, look; float vfov;
                bool track = false;
                if (v == "endon")
                {
                    pos = new Vector3(0f, 4.5f, RT48Geometry.SweepZ[0] - 70f);
                    look = pos + Vector3.forward * 100f;
                    vfov = 26f;
                    track = true;
                }
                else if (v == "oblique")
                {
                    pos = new Vector3(-8f, 7f, -50f);
                    look = new Vector3(-42f, 4.5f, 30f);
                    vfov = 45f;
                }
                else if (v == "high")
                {
                    pos = new Vector3(20f, 15f, -40f);
                    look = new Vector3(-45f, 4f, 15f);
                    vfov = 45f;
                }
                else throw new ArgumentException("知らない向き：" + v);
                var src = pb.Source as RecordedSectionSource;
                double[] cxs = null;
                if (track)
                {
                    if (src == null) throw new InvalidOperationException("頂のたどりは焼いた元だけ");
                    var cx = src.Bake.Meta.crest_x_m; int F = cx.Length;
                    cxs = new double[F];
                    for (int f = 0; f < F; f++)
                    {
                        int a = Math.Max(0, f - 12), b = Math.Min(F - 1, f + 12); double sum = 0;
                        for (int q = a; q <= b; q++) sum += cx[q];
                        cxs[f] = sum / (b - a + 1);
                    }
                }
                var go = new GameObject("RT48 船の外の試しのカメラ " + v);
                var c = go.AddComponent<Camera>();
                c.fieldOfView = vfov; c.nearClipPlane = 0.1f; c.farClipPlane = 25000f; c.clearFlags = CameraClearFlags.Skybox;
                go.transform.position = pos;
                go.transform.LookAt(look, Vector3.up);
                string dir = Path.Combine(outDir, v);
                Directory.CreateDirectory(dir);
                double from = Math.Max(pb.TimeStart, RT48Playback.ArgD("-rt48capfrom", pb.TimeStart)), to = Math.Min(pb.TimeEnd, RT48Playback.ArgD("-rt48capto", pb.TimeEnd));
                int n = (int)Math.Floor((to - from) * fps + 1e-9) + 1;
                var rows = new List<FrameRow>();
                for (int i = 0; i < n; i++)
                {
                    double t = from + i / fps;
                    pb.ApplyTime(t);
                    if (track)
                    {
                        var st = pb.State; int f = st.frame, f1 = Math.Min(cxs.Length - 1, f + 1);
                        double w = Math.Max(0.0, Math.Min(1.0, st.w));
                        double xc = cxs[f] + (cxs[f1] - cxs[f]) * w - seat;
                        go.transform.position = new Vector3((float)(xc + 8.0), pos.y, pos.z);
                        go.transform.rotation = Quaternion.LookRotation(Vector3.forward, Vector3.up);
                    }
                    var tex = RT48Capture.RenderCamera(c, W, H, 4, null);
                    File.WriteAllBytes(Path.Combine(dir, string.Format(CultureInfo.InvariantCulture, "frame_{0:D5}.png", i)), tex.EncodeToPNG());
                    UnityEngine.Object.DestroyImmediate(tex);
                    var s = pb.State;
                    rows.Add(new FrameRow { i = i, t = t, frame = pb.Source.FrameNumberFirst + s.frame, interp = s.interpolating, reason = s.reason, alpha = s.alpha, label = pb.FrameLabel(), heave = pb.BoatPose.heave, pitchDeg = pb.BoatPose.pitchDeg, camX = go.transform.position.x });
                }
                UnityEngine.Object.DestroyImmediate(go);
                var cap = new Cap
                {
                    view = v, source = pb.Source.Id, sourceLabel = pb.Source.LabelJa, gpu = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                    unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture),
                    noteJa = "船の外の試しの視点（体験では見えない所）。Unity Editor の描画（再生の部品と描き方は動画と同じ）。字は Python で足す",
                    seatX = seat, fps = fps, from = from, to = to, vfovDeg = vfov, camPos = new[] { pos.x, pos.y, pos.z }, camLookAt = new[] { look.x, look.y, look.z },
                    width = W, height = H, frames = n, rows = rows.ToArray(), seconds = sw.Elapsed.TotalSeconds
                };
                File.WriteAllText(Path.Combine(dir, "capture.json"), JsonUtility.ToJson(cap, true), new UTF8Encoding(false));
                Debug.Log("RT48_OUTSIDE done view=" + v + " frames=" + n + " seconds=" + sw.Elapsed.TotalSeconds.ToString("F1", CultureInfo.InvariantCulture) + " dir=" + dir);
            }
            pb.ReleaseAll();
        }
    }
}
