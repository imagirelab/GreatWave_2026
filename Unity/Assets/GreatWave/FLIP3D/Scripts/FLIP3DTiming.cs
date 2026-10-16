using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace GreatWave.FLIP3D
{
    // FLIP3D：実時間の再生の 1 フレームの時間を記録する（プレイヤーで使う。判定はここではしない。2026-10-16、進行役）。
    //   -f3dtiming <out.json>  記録を始める（なければ何もしない）
    //   -f3dloops <n>          繰り返しを何回測るか（既定 3。12 s × n）
    //   -f3dwarm <s>           測る前の助走（既定 3 s）
    //   -f3dquit               測り終えたら終わる
    // 垂直同期を切る（vSyncCount 0、targetFrameRate −1）ので、1 フレームの時間は描く・入れ替える仕事そのもの。
    // FrameTimingManager の CPU・GPU の時間は、ビルドで enableFrameTimingStats を入れた時だけ取れる（FLIP3DBatch.BuildPlayer が一時的に入れる）。
    public class FLIP3DTiming : MonoBehaviour
    {
        public FLIP3DPlayer player;

        [Serializable] public class Summary { public int n; public double mean, p50, p95, p99, max; public int over16_7ms, over11_1ms, hitches2xMedian; }
        [Serializable]
        public class Report
        {
            public string schema = "GreatWave.FLIP3D.timing/1";
            public string unity, device, graphicsApi, cpuName, os, startedUtc, finishedUtc, commandLine, mode;
            public bool isDebugBuild, frameTimingAvailable;
            public int screenWidth, screenHeight, vSyncCount, targetFrameRate, loops, frames, recordSwaps, tilesPerSide;
            public double warmSeconds, measuredSeconds, loadSeconds, clipMB;
            public double recordFps; public string dataDir;            // 2026-10-16 追記：24 個/s と 8 個/s のどちらのクリップか
            public double[] dtMs, swapMs, cpuMs, gpuMs; public int[] record;
            public Summary dt, swap, swapFramesOnly, cpu, gpu;
            public string noteJa;
        }

        string outPath; int loops; float warm; bool quitAfter;
        bool active, measuring, done;
        double t0Warm, t0Meas;
        readonly List<double> lDt = new List<double>(), lSwap = new List<double>(), lCpu = new List<double>(), lGpu = new List<double>();
        readonly List<int> lRec = new List<int>();
        readonly List<double> lSwapOnly = new List<double>();
        readonly FrameTiming[] ft = new FrameTiming[1];
        int lastRec = -1, swaps;
        bool ftAvail;

        void Start()
        {
            if (!Application.isPlaying) return;
            outPath = FLIP3DPlayer.Arg("-f3dtiming", "");
            if (string.IsNullOrEmpty(outPath)) return;
            loops = int.Parse(FLIP3DPlayer.Arg("-f3dloops", "3"), CultureInfo.InvariantCulture);
            warm = float.Parse(FLIP3DPlayer.Arg("-f3dwarm", "3"), CultureInfo.InvariantCulture);
            quitAfter = FLIP3DPlayer.HasArg("-f3dquit");
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;
            active = true;
        }

        void LateUpdate()
        {
            if (!active || done || player == null || !player.Initialized) return;
            double now = Time.realtimeSinceStartupAsDouble;
            if (t0Warm == 0) { t0Warm = now; return; }
            if (!measuring)
            {
                if (now - t0Warm < warm) return;
                measuring = true; t0Meas = now;
                return;
            }
            FrameTimingManager.CaptureFrameTimings();
            uint got = FrameTimingManager.GetLatestTimings(1, ft);
            if (got > 0) { ftAvail = true; lCpu.Add(ft[0].cpuFrameTime); lGpu.Add(ft[0].gpuFrameTime); }
            lDt.Add(Time.unscaledDeltaTime * 1000.0);
            lSwap.Add(player.LastSwapMs);
            lRec.Add(player.ShownRecord);
            if (player.ShownRecord != lastRec) { swaps++; lSwapOnly.Add(player.LastSwapMs); lastRec = player.ShownRecord; }
            if (now - t0Meas >= loops * player.LoopSeconds) Finish(now);
        }

        static Summary Sum(List<double> v)
        {
            var s = new Summary { n = v.Count };
            if (v.Count == 0) return s;
            var a = v.ToArray(); Array.Sort(a);
            double sum = 0; foreach (var x in a) sum += x;
            s.mean = sum / a.Length;
            s.p50 = a[(int)(0.50 * (a.Length - 1))]; s.p95 = a[(int)(0.95 * (a.Length - 1))]; s.p99 = a[(int)(0.99 * (a.Length - 1))]; s.max = a[a.Length - 1];
            foreach (var x in a) { if (x > 16.7) s.over16_7ms++; if (x > 11.1) s.over11_1ms++; if (x > 2 * s.p50) s.hitches2xMedian++; }
            return s;
        }

        void Finish(double now)
        {
            done = true;
            var r = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                cpuName = SystemInfo.processorType, os = SystemInfo.operatingSystem, startedUtc = DateTime.UtcNow.AddSeconds(-(now - t0Warm)).ToString("O"),
                finishedUtc = DateTime.UtcNow.ToString("O"), commandLine = Environment.CommandLine, mode = player.mode.ToString(),
                isDebugBuild = Debug.isDebugBuild, frameTimingAvailable = ftAvail, screenWidth = Screen.width, screenHeight = Screen.height,
                vSyncCount = QualitySettings.vSyncCount, targetFrameRate = Application.targetFrameRate, loops = loops, frames = lDt.Count,
                recordSwaps = swaps, tilesPerSide = player.tilesPerSide, warmSeconds = warm, measuredSeconds = now - t0Meas,
                loadSeconds = player.Clip.LoadSeconds, clipMB = player.Clip.ClipBytes / 1e6,
                recordFps = player.Clip.Manifest.record_fps, dataDir = player.CurrentDataDir,
                dtMs = lDt.ToArray(), swapMs = lSwap.ToArray(), cpuMs = lCpu.ToArray(), gpuMs = lGpu.ToArray(), record = lRec.ToArray(),
                dt = Sum(lDt), swap = Sum(lSwap), swapFramesOnly = Sum(lSwapOnly), cpu = Sum(lCpu), gpu = Sum(lGpu),
                noteJa = "垂直同期なし。dt は Time.unscaledDeltaTime。swap は見せる記録の Mesh を入れ替える主スレッドの時間（入れ替えたフレームだけの集計は swapFramesOnly）。"
                       + "cpu・gpu は FrameTimingManager（frameTimingAvailable が false なら空）。"
            };
            var d = Path.GetDirectoryName(Path.GetFullPath(outPath));
            if (!string.IsNullOrEmpty(d)) Directory.CreateDirectory(d);
            File.WriteAllText(outPath, JsonUtility.ToJson(r, true), new UTF8Encoding(false));
            Debug.Log(string.Format(CultureInfo.InvariantCulture, "FLIP3D_TIMING frames={0} dt_p50={1:F2} dt_p95={2:F2} dt_max={3:F2} swaps={4} out={5}",
                r.frames, r.dt.p50, r.dt.p95, r.dt.max, swaps, outPath));
            if (quitAfter) Application.Quit(0);
        }
    }
}
