using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
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
    // 2026-10-16 追記（続けて再生・続けて読む）：
    //   -f3dmeasure <s>        測る長さ（体験の秒）。既定：繰り返しは loops × 12 s、続けて再生は初めから終わりまで全部
    //   -f3dbench <n>          測り終えた後、記録 n 個（0 なら全部）の読み・読み解きの速さだけを測る（FLIP3DStream.Bench。Mesh に送らない）
    //   続けて再生では、助走の間は体験の時刻を 0 に保ち（最初の記録を見せる）、測り始めに時計を 0 から始める（範囲の全部を測る）。
    //   繰り返しの再生は前と同じ（時計は始めから動く）。続けて読む時は、間に合わなかったフレーム・GPU に送った時間・読みと読み解きの時間・メモリーも書く。
    public class FLIP3DTiming : MonoBehaviour
    {
        public FLIP3DPlayer player;

        [Serializable] public class Summary { public int n; public double mean, p50, p95, p99, max; public int over16_7ms, over11_1ms, hitches2xMedian; }
        [Serializable] public class Memory { public double workingSetMB, peakWorkingSetMB, privateMB, monoUsedMB, unityAllocatedMB, unityReservedMB, gpuMeshesMB, cpuSlotsMB; }
        [Serializable]
        public class Report
        {
            public string schema = "GreatWave.FLIP3D.timing/2";
            public string unity, device, graphicsApi, cpuName, os, startedUtc, finishedUtc, commandLine, mode;
            public bool isDebugBuild, frameTimingAvailable;
            public int screenWidth, screenHeight, vSyncCount, targetFrameRate, loops, frames, recordSwaps, tilesPerSide;
            public double warmSeconds, measuredSeconds, loadSeconds, clipMB;
            public double recordFps; public string dataDir;            // 2026-10-16 追記：24 個/s と 8 個/s のどちらのクリップか
            public double[] dtMs, swapMs, cpuMs, gpuMs; public int[] record;
            public Summary dt, swap, swapFramesOnly, cpu, gpu;
            // 2026-10-16 追記（続けて再生・続けて読む）
            public string playback, clipKind, schedule;
            public double playFromSim, playToSim, playLastSim, experienceSeconds, prefillSeconds;
            public bool streaming, ended; public int ring, recordCount;
            public int[] wanted, uploadFrameIdx, missFrameIdx, gcFrameIdx; public double[] uploadMs; public int gcCollections;
            public int missFrames, lateRecords, uploads, uploadOps, urgentUploads, recordsRead, evictions, shaChecked, shaMismatches; public int splitLevel; public bool index16, directGpu;
            public int distinctRecordsShown, recordsSkipped;
            public long bytesRead;
            public double loaderBusySeconds, loaderBusyFraction, readMBpsWhileReading;
            public Summary upload, dtOnUploadFrames, dtOnOtherFrames, readMs, decodeMs, shaMs;
            public Memory memStart, memEnd, memPeak;
            public FLIP3DStream.BenchResult bench;
            public string streamError;
            public string noteJa;
        }

        string outPath; int loops; float warm; bool quitAfter; double measureOverride = -1; int benchN = -1;
        bool active, measuring, done, released;
        double t0Warm, t0Meas, measureSeconds;
        readonly List<double> lDt = new List<double>(), lSwap = new List<double>(), lCpu = new List<double>(), lGpu = new List<double>();
        readonly List<int> lRec = new List<int>(), lWant = new List<int>(), lUpIdx = new List<int>(), lMissIdx = new List<int>(), lGcIdx = new List<int>();
        int gcLast, gc0;
        readonly List<double> lSwapOnly = new List<double>(), lUpMs = new List<double>(), lDtUp = new List<double>(), lDtOther = new List<double>();
        readonly FrameTiming[] ft = new FrameTiming[1];
        int lastRec = -1, swaps, miss0, late0, up0, ops0, urg0;
        bool ftAvail;
        Memory memStart, memPeak;

        void Awake()
        {
            if (!Application.isPlaying) return;
            if (string.IsNullOrEmpty(FLIP3DPlayer.Arg("-f3dtiming", ""))) return;
            if (player != null) player.holdClock = true;          // 続けて再生の助走：時刻を 0 に保つ（繰り返しの再生は最初のフレームで放す）
        }

        void Start()
        {
            if (!Application.isPlaying) return;
            outPath = FLIP3DPlayer.Arg("-f3dtiming", "");
            if (string.IsNullOrEmpty(outPath)) return;
            loops = int.Parse(FLIP3DPlayer.Arg("-f3dloops", "3"), CultureInfo.InvariantCulture);
            warm = float.Parse(FLIP3DPlayer.Arg("-f3dwarm", "3"), CultureInfo.InvariantCulture);
            measureOverride = double.Parse(FLIP3DPlayer.Arg("-f3dmeasure", "-1"), CultureInfo.InvariantCulture);
            benchN = int.Parse(FLIP3DPlayer.Arg("-f3dbench", "-1"), CultureInfo.InvariantCulture);
            quitAfter = FLIP3DPlayer.HasArg("-f3dquit");
            QualitySettings.vSyncCount = 0;
            // 2026-10-16 確かめで足した：-f3dtargetfps <n>（既定 −1 = 上限なし）。VR の 90 Hz に近い間隔で回し、1 拍（1/n s）を大きく越えたフレームを数えるため。
            // 上限なしでは主スレッドがいつも 100 % で走るので、主スレッドが外から止められた分（13〜32 ms、どこで止まったかは分かっていない）がそのまま 1 フレームに出る
            Application.targetFrameRate = int.Parse(FLIP3DPlayer.Arg("-f3dtargetfps", "-1"), CultureInfo.InvariantCulture);
            active = true;
        }

        bool Continuous => player.playback == FLIP3DPlayer.Playback.Continuous;

        void LateUpdate()
        {
            if (active && !done && player != null && !player.Initialized && player.LastError != null)
            {
                // 2026-10-16 追記：始めの読み込みで止まった時は、待ち続けずに誤りを書いて終わる
                done = true;
                var d0 = Path.GetDirectoryName(Path.GetFullPath(outPath));
                if (!string.IsNullOrEmpty(d0)) Directory.CreateDirectory(d0);
                File.WriteAllText(outPath, JsonUtility.ToJson(new Report { commandLine = Environment.CommandLine, streamError = player.LastError, noteJa = "FLIP3DPlayer.Init で止まった" }, true), new UTF8Encoding(false));
                Debug.LogError("FLIP3D_TIMING init failed: " + player.LastError);
                if (quitAfter) Application.Quit(2);
                return;
            }
            if (!active || done || player == null || !player.Initialized) return;
            double now = Time.realtimeSinceStartupAsDouble;
            if (!released && !Continuous) { player.holdClock = false; released = true; }
            if (t0Warm == 0) { t0Warm = now; return; }
            if (!measuring)
            {
                if (now - t0Warm < warm) return;
                measuring = true; t0Meas = now;
                if (Continuous) { player.RestartClock(); player.holdClock = false; released = true; }
                measureSeconds = measureOverride > 0 ? measureOverride : (Continuous ? player.ExperienceDuration : loops * player.LoopSeconds);
                // 2026-10-16 確かめで足した：記録の List を測り始めに大きく取っておく。前は 262,144 フレーム目に全部の List が同時に 2 倍に伸び、
                // 測りの道具そのものが 5.9〜6.8 ms のフレームを 1 回作っていた（st7_synth の 84 s・約 3,100 フレーム/s で、フレーム 262145）
                int capN = (int)Math.Min(1 << 22, Math.Max(1 << 16, measureSeconds * 5000.0));
                lDt.Capacity = capN; lSwap.Capacity = capN; lRec.Capacity = capN; lWant.Capacity = capN; lDtOther.Capacity = capN;
                lCpu.Capacity = capN; lGpu.Capacity = capN;
                miss0 = player.MissFrames; late0 = player.LateRecords;
                if (player.Streaming) { up0 = player.Stream.Uploads; ops0 = player.Stream.UploadOps; urg0 = player.Stream.UrgentUploads; }
                memStart = Mem(); memPeak = memStart;
                gcLast = gc0 = GC.CollectionCount(0);
                return;
            }
            FrameTimingManager.CaptureFrameTimings();
            uint got = FrameTimingManager.GetLatestTimings(1, ft);
            if (got > 0) { ftAvail = true; lCpu.Add(ft[0].cpuFrameTime); lGpu.Add(ft[0].gpuFrameTime); }
            double dt = Time.unscaledDeltaTime * 1000.0;
            int i = lDt.Count;
            lDt.Add(dt);
            lSwap.Add(player.LastSwapMs);
            lRec.Add(player.ShownRecord);
            lWant.Add(player.WantedRecord);
            if (player.UploadedThisFrame > 0) { lUpIdx.Add(i); lUpMs.Add(player.LastUploadMs); lDtUp.Add(dt); } else lDtOther.Add(dt);
            if (player.MissThisFrame) lMissIdx.Add(i);
            int gcNow = GC.CollectionCount(0);
            if (gcNow != gcLast) { lGcIdx.Add(i); gcLast = gcNow; }        // このフレームの間に GC が走った（2026-10-16 追記：止まりとの重なりを見る）
            if (player.ShownRecord != lastRec) { swaps++; lSwapOnly.Add(player.LastSwapMs); lastRec = player.ShownRecord; }
            if ((i & 1023) == 0) { var m = Mem(); if (m.workingSetMB > memPeak.workingSetMB) memPeak = m; }
            bool end = now - t0Meas >= measureSeconds;
            if (Continuous && measureOverride <= 0 && player.endAction == FLIP3DPlayer.EndAction.Hold) end = player.Ended;
            if (end) Finish(now);
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
        static Summary SumF(float[] v) { var l = new List<double>(v.Length); foreach (var x in v) l.Add(x); return Sum(l); }

        [StructLayout(LayoutKind.Sequential)]
        struct PMC
        {
            public uint cb, PageFaultCount;
            public UIntPtr PeakWorkingSetSize, WorkingSetSize, QuotaPeakPagedPoolUsage, QuotaPagedPoolUsage, QuotaPeakNonPagedPoolUsage, QuotaNonPagedPoolUsage, PagefileUsage, PeakPagefileUsage, PrivateUsage;
        }
        [DllImport("kernel32.dll", EntryPoint = "K32GetProcessMemoryInfo")] static extern bool GetProcessMemoryInfo(IntPtr p, out PMC c, uint cb);
        [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();

        // メモリー：プロセスの working set・private（Windows）、Mono・Unity の割り当て、続けて読む輪の GPU の Mesh の器と主メモリーの置き場（計算）
        Memory Mem()
        {
            var m = new Memory();
            try
            {
                if (GetProcessMemoryInfo(GetCurrentProcess(), out PMC c, (uint)Marshal.SizeOf(typeof(PMC))))
                {
                    m.workingSetMB = c.WorkingSetSize.ToUInt64() / 1e6; m.peakWorkingSetMB = c.PeakWorkingSetSize.ToUInt64() / 1e6; m.privateMB = c.PrivateUsage.ToUInt64() / 1e6;
                }
            }
            catch (Exception) { }
            m.monoUsedMB = UnityEngine.Profiling.Profiler.GetMonoUsedSizeLong() / 1e6;
            m.unityAllocatedMB = UnityEngine.Profiling.Profiler.GetTotalAllocatedMemoryLong() / 1e6;
            m.unityReservedMB = UnityEngine.Profiling.Profiler.GetTotalReservedMemoryLong() / 1e6;
            if (player != null && player.Streaming) { m.gpuMeshesMB = player.Stream.GpuBytes / 1e6; m.cpuSlotsMB = player.Stream.CpuSlotBytes / 1e6; }
            return m;
        }

        void Finish(double now)
        {
            done = true;
            var st = player.Stream;
            var mf = player.Manifest;
            var shown = new HashSet<int>(lRec);
            int skipped = 0;
            if (Continuous && lWant.Count > 0)
            {
                // 続けて再生で、予定の記録のうち一度も見せなかった物（間に合わずに飛んだ記録）
                var want = new HashSet<int>(lWant);
                foreach (var w in want) if (w >= 0 && !shown.Contains(w)) skipped++;
            }
            var r = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                cpuName = SystemInfo.processorType, os = SystemInfo.operatingSystem, startedUtc = DateTime.UtcNow.AddSeconds(-(now - t0Warm)).ToString("O"),
                finishedUtc = DateTime.UtcNow.ToString("O"), commandLine = Environment.CommandLine, mode = player.mode.ToString(),
                isDebugBuild = Debug.isDebugBuild, frameTimingAvailable = ftAvail, screenWidth = Screen.width, screenHeight = Screen.height,
                vSyncCount = QualitySettings.vSyncCount, targetFrameRate = Application.targetFrameRate, loops = loops, frames = lDt.Count,
                recordSwaps = swaps, tilesPerSide = player.tilesPerSide, warmSeconds = warm, measuredSeconds = now - t0Meas,
                loadSeconds = player.LoadSeconds, clipMB = player.DataBytes / 1e6,
                recordFps = mf.record_fps, dataDir = player.CurrentDataDir,
                dtMs = lDt.ToArray(), swapMs = lSwap.ToArray(), cpuMs = lCpu.ToArray(), gpuMs = lGpu.ToArray(), record = lRec.ToArray(),
                dt = Sum(lDt), swap = Sum(lSwap), swapFramesOnly = Sum(lSwapOnly), cpu = Sum(lCpu), gpu = Sum(lGpu),
                playback = player.playback.ToString(), clipKind = string.IsNullOrEmpty(mf.clip_kind) ? "loop" : mf.clip_kind, schedule = player.ScheduleText,
                playFromSim = player.PlayFromSim, playToSim = player.PlayToSim, playLastSim = player.PlayLastSim, experienceSeconds = player.ExperienceDuration, prefillSeconds = player.PrefillSeconds,
                streaming = player.Streaming, ended = player.Ended, ring = st != null ? st.RingSize : 0, recordCount = player.RecordCount,
                wanted = lWant.ToArray(), uploadFrameIdx = lUpIdx.ToArray(), missFrameIdx = lMissIdx.ToArray(), uploadMs = lUpMs.ToArray(),
                gcFrameIdx = lGcIdx.ToArray(), gcCollections = GC.CollectionCount(0) - gc0,
                missFrames = player.MissFrames - miss0, lateRecords = player.LateRecords - late0,
                distinctRecordsShown = shown.Count, recordsSkipped = skipped,
                upload = Sum(lUpMs), dtOnUploadFrames = Sum(lDtUp), dtOnOtherFrames = Sum(lDtOther),
                memStart = memStart, memEnd = Mem(), memPeak = memPeak,
                noteJa = "垂直同期なし。dt は Time.unscaledDeltaTime。swap は見せる記録の Mesh を入れ替える主スレッドの時間（続けて読む時は、その中に GPU に送る時間も入る。"
                       + "入れ替えたフレームだけの集計は swapFramesOnly）。cpu・gpu は FrameTimingManager（frameTimingAvailable が false なら空）。"
                       + "続けて読む時：upload は 1 フレームに 1 回 GPU に送る時間（splitLevel 回に分ける：2 なら点と法線・三角形。uploads は記録の数、uploadOps は回数。index16 なら三角形の添字は 16 bit）、dtOnUploadFrames はそのフレームの dt。missFrames は見せたい記録が GPU に間に合わず前の記録を見せたフレームの数。"
                       + "readMs・decodeMs は別のスレッドの記録ごとの時間（OS のファイルの写しが温かいかは分からない）。memory の gpuMeshesMB・cpuSlotsMB は輪の器の大きさの計算。"
            };
            if (st != null)
            {
                r.uploads = st.Uploads - up0; r.uploadOps = st.UploadOps - ops0; r.urgentUploads = st.UrgentUploads - urg0; r.splitLevel = st.SplitLevel; r.index16 = st.Index16; r.directGpu = st.DirectGpu;
                r.recordsRead = st.RecordsRead; r.bytesRead = st.BytesRead; r.evictions = st.Evictions;
                r.shaChecked = st.ShaChecked; r.shaMismatches = st.ShaMismatches;
                r.loaderBusySeconds = st.LoaderBusySeconds;
                r.loaderBusyFraction = st.LoaderBusySeconds / Math.Max(1e-9, now - t0Warm);
                var rm = st.ReadMs; double rs = 0; foreach (var v in rm) rs += v;
                r.readMBpsWhileReading = st.BytesRead / 1e6 / Math.Max(1e-9, rs / 1000.0);
                r.readMs = SumF(rm); r.decodeMs = SumF(st.DecodeMs); r.shaMs = SumF(st.ShaMs);
                r.streamError = st.Error;
            }
            if (benchN >= 0)
            {
                try { r.bench = FLIP3DStream.Bench(player.CurrentDataDir, benchN); }
                catch (Exception e) { Debug.LogError("FLIP3D_BENCH_EXCEPTION " + e); }
            }
            var d = Path.GetDirectoryName(Path.GetFullPath(outPath));
            if (!string.IsNullOrEmpty(d)) Directory.CreateDirectory(d);
            File.WriteAllText(outPath, JsonUtility.ToJson(r, true), new UTF8Encoding(false));
            Debug.Log(string.Format(CultureInfo.InvariantCulture, "FLIP3D_TIMING frames={0} dt_p50={1:F2} dt_p95={2:F2} dt_max={3:F2} swaps={4} streaming={6} miss={7} uploads={8} up_p95={9:F2} out={5}",
                r.frames, r.dt.p50, r.dt.p95, r.dt.max, swaps, outPath, r.streaming, r.missFrames, r.uploads, r.upload.p95));
            if (quitAfter) Application.Quit(0);
        }
    }
}
