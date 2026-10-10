using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace GreatWave.RT48
{
    // RT48：1 フレームの時間の記録（計画 C7 の測り方。合格の判定はここではしない）。プレイヤーで使う。
    //   -rt48timing <out.json>   記録を始める（なければ何もしない）
    //   -rt48timingruns <n>      船からのクリップを何回測るか（既定 3）
    //   -rt48warm <s>            1 回目の前の助走（既定 3 s。助走の後にクリップを初めから始める）
    //   -rt48proxy <W>x<H>       両眼の代理：眼ごとの RT 2 枚（4×MSAA、目の幅 64 mm、縦の画角 96°）。画面には左眼を小さく写す
    //   -rt48quit                測り終えたら終わる
    // FrameTimingManager の CPU・GPU の時間は、ビルドで enableFrameTimingStats を入れた時だけ取れる（RT48PlayerBuild が一時的に入れる）。
    // 取れない時は Time.unscaledDeltaTime だけを書き、frameTimingAvailable = false とする。垂直同期は切る（vSyncCount 0、targetFrameRate −1）。
    public class RT48FrameTiming : MonoBehaviour
    {
        public RT48Playback playback;
        public RT48Rig rig;
        public RT48Captions captions;
        public Camera mainCamera;
        public const float Ipd = 0.064f, EyeVFov = 96f;
        public const int EyeMsaa = 4;

        [Serializable] public class Summary { public int n; public double p50, p95, p99, max, mean, over11_1ms, over8_9ms; }
        [Serializable]
        public class Run
        {
            public int index; public string startUtc, endUtc; public double simStart, simEnd, realSeconds; public int unityFrames;
            public double[] cpuMs, cpuMainMs, cpuRenderMs, presentWaitMs, gpuMs; public float[] dtMs;
            public Summary cpu, gpu, dt;
        }
        [Serializable]
        public class Report
        {
            public string schema = "GreatWave.RT48.timing/1";
            public string unity, device, graphicsApi, cpu, os, startedUtc, finishedUtc, commandLine, source, sourceLabel;
            public bool isDebugBuild, frameTimingAvailable, xrActive, proxy;
            public int screenWidth, screenHeight, eyeWidth, eyeHeight, eyeMsaa, vSyncCount, targetFrameRate, runsRequested;
            public double seatX, clipStart, clipEnd, warmSeconds, cpuTimerFrequency, gpuTimerFrequency;
            public string noteJa;
            public Run[] runs;
        }

        public bool Active { get; private set; }
        public bool Finished { get; private set; }
        string outPath;
        int runsRequested;
        float warm;
        bool quitAfter;
        Report rep;
        readonly List<Run> runs = new List<Run>();
        Run cur;
        enum Phase { Wait, Warm, Measure, Done }
        Phase phase = Phase.Wait;
        double phaseStartReal;
        readonly FrameTiming[] ft = new FrameTiming[8];
        readonly HashSet<ulong> seen = new HashSet<ulong>();
        readonly List<double> lCpu = new List<double>(), lMain = new List<double>(), lRender = new List<double>(), lWait = new List<double>(), lGpu = new List<double>();
        readonly List<float> lDt = new List<float>();
        Camera eyeL, eyeR;
        RenderTexture rtL, rtR;
        int proxyW, proxyH;

        void Start()
        {
            if (!Application.isPlaying) return;
            outPath = RT48Playback.Arg("-rt48timing", "");
            if (string.IsNullOrEmpty(outPath)) return;
            Active = true;
            runsRequested = (int)RT48Playback.ArgD("-rt48timingruns", 3);
            warm = (float)RT48Playback.ArgD("-rt48warm", 3);
            quitAfter = RT48Playback.HasArg("-rt48quit");
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;
            var proxy = RT48Playback.Arg("-rt48proxy", "");
            if (!string.IsNullOrEmpty(proxy))
            {
                var p = proxy.ToLowerInvariant().Split('x');
                proxyW = int.Parse(p[0], CultureInfo.InvariantCulture); proxyH = int.Parse(p[1], CultureInfo.InvariantCulture);
                SetupProxy();
                if (captions != null) captions.HudVisible = false;   // 代理の眼に字を入れない
            }
            rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                cpu = SystemInfo.processorType, os = SystemInfo.operatingSystem, startedUtc = DateTime.UtcNow.ToString("O"),
                commandLine = Environment.CommandLine, isDebugBuild = Debug.isDebugBuild, frameTimingAvailable = FrameTimingManager.IsFeatureEnabled(),
                proxy = proxyW > 0, eyeWidth = proxyW, eyeHeight = proxyH, eyeMsaa = proxyW > 0 ? EyeMsaa : 0,
                vSyncCount = QualitySettings.vSyncCount, targetFrameRate = Application.targetFrameRate, runsRequested = runsRequested, warmSeconds = warm,
                cpuTimerFrequency = FrameTimingManager.GetCpuTimerFrequency(), gpuTimerFrequency = FrameTimingManager.GetGpuTimerFrequency(),
                noteJa = "FrameTimingManager の値（ms）。クリップ 1 回 ＝ 船からのクリップの始めから終わりまで。合否の判定はこの記録の外（計画 C7）。"
            };
            phase = Phase.Wait;
            Debug.Log("RT48_TIMING start out=" + outPath + " runs=" + runsRequested + " proxy=" + proxy + " ftAvailable=" + rep.frameTimingAvailable);
        }

        void SetupProxy()
        {
            if (mainCamera == null) return;
            rtL = MakeRT("RT48 左眼"); rtR = MakeRT("RT48 右眼");
            eyeL = MakeEye("RT48 左眼の代理", -0.5f * Ipd, rtL);
            eyeR = MakeEye("RT48 右眼の代理", 0.5f * Ipd, rtR);
            mainCamera.cullingMask = 0;
            mainCamera.clearFlags = CameraClearFlags.SolidColor;
            mainCamera.backgroundColor = Color.black;
        }

        RenderTexture MakeRT(string name)
        {
            var rt = new RenderTexture(proxyW, proxyH, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { name = name, antiAliasing = EyeMsaa };
            rt.Create();
            return rt;
        }

        Camera MakeEye(string name, float x, RenderTexture rt)
        {
            var go = new GameObject(name);
            go.transform.SetParent(mainCamera.transform, false);
            go.transform.localPosition = new Vector3(x, 0f, 0f);
            var c = go.AddComponent<Camera>();
            c.CopyFrom(mainCamera);
            c.cullingMask = ~0;
            c.clearFlags = CameraClearFlags.Skybox;
            c.fieldOfView = EyeVFov;
            c.targetTexture = rt;
            c.stereoTargetEye = StereoTargetEyeMask.None;
            c.depth = mainCamera.depth - 1;
            return c;
        }

        void OnGUI()
        {
            if (rtL != null && Event.current.type == EventType.Repaint)
            {
                float h = Screen.height * 0.35f, w = h * proxyW / proxyH;
                GUI.DrawTexture(new Rect(8, 8, w, h), rtL, ScaleMode.StretchToFill, false);
            }
        }

        void Update()
        {
            if (!Active || Finished || playback == null || playback.Source == null) return;
            double now = Time.realtimeSinceStartupAsDouble;
            switch (phase)
            {
                case Phase.Wait:
                    playback.Restart();
                    phase = Phase.Warm; phaseStartReal = now;
                    break;
                case Phase.Warm:
                    if (now - phaseStartReal >= warm) BeginRun();
                    break;
                case Phase.Measure:
                    Collect();
                    if (playback.Ended) EndRun();
                    break;
            }
        }

        void BeginRun()
        {
            playback.Restart();
            seen.Clear();
            lCpu.Clear(); lMain.Clear(); lRender.Clear(); lWait.Clear(); lGpu.Clear(); lDt.Clear();
            cur = new Run { index = runs.Count, startUtc = DateTime.UtcNow.ToString("O"), simStart = playback.SimTime, unityFrames = Time.frameCount };
            phase = Phase.Measure; phaseStartReal = Time.realtimeSinceStartupAsDouble;
            // 始めの数フレームは前のクリップの値が混ざるので、ここで溜まっている値を読み捨てる
            FrameTimingManager.CaptureFrameTimings();
            uint n = FrameTimingManager.GetLatestTimings((uint)ft.Length, ft);
            for (int i = 0; i < n; i++) seen.Add(ft[i].frameStartTimestamp);
        }

        void Collect()
        {
            lDt.Add(Time.unscaledDeltaTime * 1000f);
            FrameTimingManager.CaptureFrameTimings();
            uint n = FrameTimingManager.GetLatestTimings((uint)ft.Length, ft);
            for (int i = (int)n - 1; i >= 0; i--)
            {
                var t = ft[i];
                if (t.frameStartTimestamp == 0 || !seen.Add(t.frameStartTimestamp)) continue;
                lCpu.Add(t.cpuFrameTime); lMain.Add(t.cpuMainThreadFrameTime); lRender.Add(t.cpuRenderThreadFrameTime);
                lWait.Add(t.cpuMainThreadPresentWaitTime); lGpu.Add(t.gpuFrameTime);
            }
        }

        void EndRun()
        {
            cur.endUtc = DateTime.UtcNow.ToString("O");
            cur.simEnd = playback.SimTime;
            cur.realSeconds = Time.realtimeSinceStartupAsDouble - phaseStartReal;
            cur.unityFrames = Time.frameCount - cur.unityFrames;
            cur.cpuMs = lCpu.ToArray(); cur.cpuMainMs = lMain.ToArray(); cur.cpuRenderMs = lRender.ToArray(); cur.presentWaitMs = lWait.ToArray(); cur.gpuMs = lGpu.ToArray();
            cur.dtMs = lDt.ToArray();
            cur.cpu = Summarize(lCpu); cur.gpu = Summarize(lGpu);
            var dd = new List<double>(); foreach (var v in lDt) dd.Add(v); cur.dt = Summarize(dd);
            runs.Add(cur);
            Debug.Log("RT48_TIMING run=" + cur.index + " frames=" + cur.unityFrames + " cpu_p95=" + cur.cpu.p95.ToString("F3", CultureInfo.InvariantCulture) +
                      " gpu_p95=" + cur.gpu.p95.ToString("F3", CultureInfo.InvariantCulture) + " dt_p95=" + cur.dt.p95.ToString("F3", CultureInfo.InvariantCulture));
            WriteReport();
            if (runs.Count >= runsRequested) Finish();
            else BeginRun();
        }

        public static Summary Summarize(List<double> v)
        {
            var s = new Summary { n = v.Count };
            if (v.Count == 0) return s;
            var a = v.ToArray(); Array.Sort(a);
            double sum = 0; int o11 = 0, o89 = 0;
            foreach (var x in a) { sum += x; if (x > 11.1) o11++; if (x > 8.9) o89++; }
            s.mean = sum / a.Length; s.max = a[a.Length - 1];
            s.p50 = Pct(a, 0.50); s.p95 = Pct(a, 0.95); s.p99 = Pct(a, 0.99);
            s.over11_1ms = (double)o11 / a.Length; s.over8_9ms = (double)o89 / a.Length;
            return s;
        }

        static double Pct(double[] sorted, double q)
        {
            double r = q * (sorted.Length - 1);
            int i = (int)Math.Floor(r); int j = Math.Min(i + 1, sorted.Length - 1);
            return sorted[i] + (sorted[j] - sorted[i]) * (r - i);
        }

        void WriteReport()
        {
            rep.finishedUtc = DateTime.UtcNow.ToString("O");
            rep.runs = runs.ToArray();
            rep.screenWidth = Screen.width; rep.screenHeight = Screen.height;
            rep.xrActive = rig != null && rig.XrActive;
            rep.source = playback.Source.Id; rep.sourceLabel = playback.Source.LabelJa;
            rep.seatX = playback.SeatX; rep.clipStart = playback.TimeStart; rep.clipEnd = playback.TimeEnd;
            var dir = Path.GetDirectoryName(Path.GetFullPath(outPath));
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            File.WriteAllText(outPath, JsonUtility.ToJson(rep, true));
        }

        void Finish()
        {
            Finished = true; phase = Phase.Done;
            Debug.Log("RT48_TIMING done runs=" + runs.Count + " out=" + outPath);
            if (quitAfter) playback.Quit("timing_done");
        }

        void OnDestroy()
        {
            if (rtL != null) rtL.Release();
            if (rtR != null) rtR.Release();
        }
    }
}
