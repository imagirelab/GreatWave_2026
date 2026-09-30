using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design31;
using GreatWave.Design34;
using UnityEngine;

namespace GreatWave.Design39
{
    // 設計39：紙の地（①）・摺りのむら（②）・小飛沫（③）の入切ごとの GPU 時間。設計35 の計測器（DS35PerfRunner、美術優先32 の測り方）を写し、
    // 「版」を「入切の組」（基準＝全部切＝設計38 の描画、①だけ、②だけ、③だけ、全部）に替えたもの。測り方・条件・数え方は設計35 と同じ：
    //   Release（Development でない）の Windows プレイヤーを見えるウィンドウで動かし、FrameTimingManager の CPU・GPU とフレームの開始時刻を集める。
    //   区間：体験の時刻 t を [windowStart, windowEnd)（既定 11〜12 s：爪と飛沫が全部出ている t* の直前の 1 秒）で実時間の速さで繰り返す。
    //   条件：① 1920×1080・原画視点 ② 1920×1080・座席 v1 ③ 立体の代理（座席 v1 から左右の眼カメラ、IPD 64 mm、縦画角 96°、各 2064×2208・4×MSAA の RT）。
    //   場面：DS39_Perf.unity（DS39_Paper.unity の写し。DS39Render.BuildPerf が作る）。入切は DS39PaperLayers.Set（測定の外）。
    // 起動引数：-ds39out <dir>、-ds39tag <名前>、-ds39warm <秒>（既定 3）、-ds39measure <秒>（既定 12）、-ds39variants base,paper,mura,spray,all、
    //   -ds39conds desk1080_painting,desk1080_seat,proxy_stereo_seat、-ds39window 11,12。
    [DefaultExecutionOrder(40)]
    public class DS39PerfRunner : MonoBehaviour
    {
        [Serializable]
        public class Variant
        {
            public string name, nameJa, clawLayout, sprayData;
            public bool paper, mura, spray;
        }

        public List<Variant> variants = new List<Variant>
        {
            new Variant { name = "base", nameJa = "全部切（設計38 の描画）" },
            new Variant { name = "paper", nameJa = "① 紙の地だけ", paper = true },
            new Variant { name = "mura", nameJa = "② 摺りのむらだけ", mura = true },
            new Variant { name = "spray", nameJa = "③ 小飛沫だけ", spray = true },
            new Variant { name = "all", nameJa = "①②③ 全部", paper = true, mura = true, spray = true },
        };
        public string paintingCameraName = "DS27 painting";
        public string seatCameraName = "DS27 seat";
        [Tooltip("プレイヤーに爪と飛沫のシェーダー（instancing の変種）を入れるための参照。場面では使わない")]
        public Material[] keepShaders;
        public float windowStart = 11f, windowEnd = 12f;

        public const int EyeWidth = 2064, EyeHeight = 2208, EyeMsaa = 4;
        public const float Ipd = 0.064f, EyeVerticalFov = 96f;
        public const int DesktopWidth = 1920, DesktopHeight = 1080;
        static readonly Color SkyTop = new Color32(249, 232, 196, 255);

        [Serializable]
        public class CondResult
        {
            public string variant, name, noteJa, view;
            public bool stereoProxy;
            public int vSyncCount, targetFrameRate, qualityMsaa, screenWidth, screenHeight, eyeWidth, eyeHeight, eyeMsaa;
            public string startUtc, endUtc;
            public double warmSeconds, measureSeconds;
            public int unityFramesInWindow;
            public bool frameTimingEnabled;
            public double cpuTimerFrequency, gpuTimerFrequency, vsyncsPerSecond;
            public long[] ftStart;
            public double[] ftCpu, ftCpuMain, ftCpuRender, ftCpuPresentWait, ftGpu;
            public int[] ftSync;
            public float[] dt;
            public float[] tPlayed;
            public int clawCount, clawVertices, clawTriangles, sprayCount, sprayAliveMin, sprayAliveMax;
            public string clawLayout, sprayData, clawFramesSha256, spraySha256;
            public float loadSeconds;
            public string screenshot;
            public string[] eyeImages;
        }

        [Serializable]
        public class RunResult
        {
            public string schema = "GreatWave.DS39.perf_run/1";
            public string tag, unity, device, deviceVendor, deviceVersion, graphicsApi, cpu, os, colorSpace, qualityName;
            public int graphicsMemoryMB, systemMemoryMB;
            public bool isDebugBuild, frameTimingFeatureEnabled;
            public string startedUtc, finishedUtc, commandLine, workingDirectory;
            public string refreshRate, fullScreenMode;
            public int screenWidth, screenHeight;
            public float windowStart, windowEnd;
            public CondResult[] conditions;
            public string errorJa;
        }

        RunResult result;
        string outDir, tag;
        float warmSeconds = 3f, measureSeconds = 12f;
        HashSet<string> onlyVariants, onlyConds;

        DS30SinglePlayback play;
        DS34ClawPlayer claws;
        DS31InstancedParticles spray, dense;
        DS39PaperLayers paperLayers;
        Camera displayCam, eyeL, eyeR;
        RenderTexture rtL, rtR;
        bool proxyActive, looping, collecting;
        float loopT0;
        int aliveMin, aliveMax;

        readonly FrameTiming[] ftBuf = new FrameTiming[8];
        readonly HashSet<ulong> seenStarts = new HashSet<ulong>();
        readonly List<long> lStart = new List<long>();
        readonly List<double> lCpu = new List<double>(), lCpuMain = new List<double>(), lCpuRender = new List<double>(), lWait = new List<double>(), lGpu = new List<double>();
        readonly List<int> lSync = new List<int>();
        readonly List<float> lDt = new List<float>(), lT = new List<float>();

        static string Arg(string key, string def)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == key) return a[i + 1];
            return def;
        }

        IEnumerator Start()
        {
            tag = Arg("-ds39tag", "run");
            outDir = Path.GetFullPath(Arg("-ds39out", Path.Combine(Application.dataPath, "..", "out")));
            warmSeconds = float.Parse(Arg("-ds39warm", "3"), CultureInfo.InvariantCulture);
            measureSeconds = float.Parse(Arg("-ds39measure", "12"), CultureInfo.InvariantCulture);
            var vs = Arg("-ds39variants", ""); onlyVariants = string.IsNullOrEmpty(vs) ? null : new HashSet<string>(vs.Split(','));
            var cs = Arg("-ds39conds", ""); onlyConds = string.IsNullOrEmpty(cs) ? null : new HashSet<string>(cs.Split(','));
            var win = Arg("-ds39window", "");
            if (!string.IsNullOrEmpty(win)) { var p = win.Split(','); windowStart = float.Parse(p[0], CultureInfo.InvariantCulture); windowEnd = float.Parse(p[1], CultureInfo.InvariantCulture); }
            Directory.CreateDirectory(outDir);
            result = new RunResult
            {
                tag = tag, unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, deviceVendor = SystemInfo.graphicsDeviceVendor,
                deviceVersion = SystemInfo.graphicsDeviceVersion, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), cpu = SystemInfo.processorType,
                os = SystemInfo.operatingSystem, colorSpace = QualitySettings.activeColorSpace.ToString(), qualityName = QualitySettings.names[QualitySettings.GetQualityLevel()],
                graphicsMemoryMB = SystemInfo.graphicsMemorySize, systemMemoryMB = SystemInfo.systemMemorySize, isDebugBuild = Debug.isDebugBuild,
                startedUtc = DateTime.UtcNow.ToString("O"), commandLine = Environment.CommandLine, workingDirectory = Directory.GetCurrentDirectory(),
                frameTimingFeatureEnabled = FrameTimingManager.IsFeatureEnabled(), windowStart = windowStart, windowEnd = windowEnd
            };
            Application.runInBackground = true;
            Application.targetFrameRate = -1;
            // 設計34 の採取（DS34Render）と同じ大域の値（白の帯を有効、確認用の色なし）
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
            Shader.SetGlobalFloat("_DS34ClawDiag", 0);
            Screen.SetResolution(DesktopWidth, DesktopHeight, FullScreenMode.Windowed);
            for (int i = 0; i < 30; i++) yield return null;
            result.screenWidth = Screen.width; result.screenHeight = Screen.height;
            result.refreshRate = Screen.currentResolution.refreshRateRatio.value.ToString("F3", CultureInfo.InvariantCulture);
            result.fullScreenMode = Screen.fullScreenMode.ToString();

            bool ok = true;
            try
            {
                play = FindAnyObjectByType<DS30SinglePlayback>(FindObjectsInactive.Include);
                claws = FindAnyObjectByType<DS34ClawPlayer>(FindObjectsInactive.Include);
                foreach (var p in FindObjectsByType<DS31InstancedParticles>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                {
                    if (p.name == "DS31 spray") spray = p;
                    else if (p.name == "DS39 spray dense") dense = p;
                }
                paperLayers = FindAnyObjectByType<DS39PaperLayers>(FindObjectsInactive.Include);
                if (play == null || claws == null || spray == null || dense == null || paperLayers == null) throw new InvalidOperationException("再生器・爪・飛沫・小飛沫・紙の部品のどれかがありません。");
                play.enabled = false;   // 時刻はこの計測器が Seek で決める（Tick で進めない）
                play.Prepare();
                spray.drawInPlayMode = true;
                if (!dense.Loaded) dense.Load();
                paperLayers.Build();
            }
            catch (Exception e) { result.errorJa = "場面の準備に失敗: " + e.Message; ok = false; }

            if (ok)
            {
                var conds = new List<CondResult>();
                foreach (var v in variants)
                {
                    if (onlyVariants != null && !onlyVariants.Contains(v.name)) continue;
                    float ls = 0f;
                    string err = null;
                    try { ls = LoadVariant(v); }
                    catch (Exception e) { err = "版 " + v.name + " を読めません: " + e.Message; }
                    if (err != null) { result.errorJa = err; break; }
                    foreach (var c in CondList())
                    {
                        if (onlyConds != null && !onlyConds.Contains(c.name)) continue;
                        var r = new CondResult { variant = v.name, name = c.name, view = c.view, noteJa = c.noteJa, stereoProxy = c.proxy, loadSeconds = ls,
                            clawLayout = v.nameJa, sprayData = (v.spray ? "設計31 ＋ 設計39 の子" : "設計31"), clawCount = claws.ClawCount, clawVertices = claws.VertexCount, clawTriangles = claws.TriangleCount,
                            clawFramesSha256 = claws.FramesSha256, sprayCount = spray.Count + (v.spray ? dense.Count : 0), spraySha256 = spray.DataSha256 + (v.spray ? "+" + dense.DataSha256 : "") };
                        yield return MeasureCondition(c, r);
                        conds.Add(r);
                        result.conditions = conds.ToArray();
                        File.WriteAllText(Path.Combine(outDir, "ds39_" + tag + ".json"), JsonUtility.ToJson(result, false));
                    }
                }
                result.conditions = conds.ToArray();
            }
            result.finishedUtc = DateTime.UtcNow.ToString("O");
            File.WriteAllText(Path.Combine(outDir, "ds39_" + tag + ".json"), JsonUtility.ToJson(result, false));
            Debug.Log("DS39_DONE tag=" + tag + " error=" + (result.errorJa ?? ""));
            yield return null;
            Application.Quit(string.IsNullOrEmpty(result.errorJa) ? 0 : 3);
        }

        float LoadVariant(Variant v)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            looping = false;
            paperLayers.Set(v.paper, v.mura, v.spray);
            SetT(windowStart);
            return (float)sw.Elapsed.TotalSeconds;
        }

        void SetT(double t)
        {
            play.Seek(t);
            claws.ApplyT(t);
            spray.ApplyT(t);
            dense.ApplyT(t);
        }

        struct Cond { public string name, view, noteJa; public bool proxy; }

        List<Cond> CondList() => new List<Cond>
        {
            new Cond { name = "desk1080_painting", view = paintingCameraName, proxy = false, noteJa = "1920×1080 の見えるウィンドウ、原画視点（PaintingCam v1）、画面へ直接描く、垂直同期なし" },
            new Cond { name = "desk1080_seat", view = seatCameraName, proxy = false, noteJa = "1920×1080 の見えるウィンドウ、座席 v1、画面へ直接描く、垂直同期なし" },
            new Cond { name = "proxy_stereo_seat", view = seatCameraName, proxy = true, noteJa = "立体の代理：座席 v1 から左右の眼カメラ（IPD 64 mm、縦画角 96°）で各 2064×2208・4×MSAA の RT へ描き、画面へ縮小表示。垂直同期なし（美術優先32 と同じ）" },
        };

        // 区間の繰り返し：毎フレーム、実時間で t を進め、窓の終わりで始まりへ戻す（爪・飛沫の Update（実行順 60）より前に時計を書く）
        void Update()
        {
            FrameTimingManager.CaptureFrameTimings();
            if (looping)
            {
                float len = Mathf.Max(1e-3f, windowEnd - windowStart);
                float t = windowStart + Mathf.Repeat(Time.realtimeSinceStartup - loopT0, len);
                play.Seek(t);
                if (collecting) lT.Add(t);
            }
            if (!collecting) return;
            lDt.Add(Time.unscaledDeltaTime);
            uint n = FrameTimingManager.GetLatestTimings((uint)ftBuf.Length, ftBuf);
            for (int i = 0; i < n; i++)
            {
                var ft = ftBuf[i];
                if (ft.frameStartTimestamp == 0 || !seenStarts.Add(ft.frameStartTimestamp)) continue;
                lStart.Add((long)ft.frameStartTimestamp);
                lCpu.Add(ft.cpuFrameTime); lCpuMain.Add(ft.cpuMainThreadFrameTime); lCpuRender.Add(ft.cpuRenderThreadFrameTime);
                lWait.Add(ft.cpuMainThreadPresentWaitTime); lGpu.Add(ft.gpuFrameTime); lSync.Add((int)ft.syncInterval);
            }
        }

        void LateUpdate()
        {
            if (!collecting) return;
            int al = spray.AliveNow + (dense.drawInPlayMode ? dense.AliveNow : 0); aliveMin = Math.Min(aliveMin, al); aliveMax = Math.Max(aliveMax, al);
        }

        Camera MakeCamera(string name, Camera src)
        {
            var go = new GameObject(name);
            var cam = go.AddComponent<Camera>();
            cam.transform.SetPositionAndRotation(src.transform.position, src.transform.rotation);
            cam.fieldOfView = src.fieldOfView;
            cam.nearClipPlane = src.nearClipPlane; cam.farClipPlane = src.farClipPlane;
            cam.cullingMask = src.cullingMask;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = SkyTop;
            cam.allowHDR = false; cam.allowMSAA = true;
            cam.stereoTargetEye = StereoTargetEyeMask.None;
            return cam;
        }

        static Camera FindCam(string name)
        {
            foreach (var c in Resources.FindObjectsOfTypeAll<Camera>()) if (c.name == name && c.gameObject.scene.IsValid()) return c;
            throw new InvalidOperationException("カメラがありません: " + name);
        }

        void Teardown()
        {
            proxyActive = false;
            if (displayCam != null) Destroy(displayCam.gameObject);
            if (eyeL != null) Destroy(eyeL.gameObject);
            if (eyeR != null) Destroy(eyeR.gameObject);
            if (rtL != null) { rtL.Release(); Destroy(rtL); }
            if (rtR != null) { rtR.Release(); Destroy(rtR); }
            displayCam = eyeL = eyeR = null; rtL = rtR = null;
        }

        IEnumerator MeasureCondition(Cond c, CondResult r)
        {
            Teardown();
            yield return null;
            var src = FindCam(c.view);
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;
            displayCam = MakeCamera("DS39 表示カメラ", src);
            displayCam.depth = 0;
            displayCam.aspect = (float)DesktopWidth / DesktopHeight;
            if (c.proxy)
            {
                displayCam.cullingMask = 0;
                rtL = NewEyeRT("DS39 左眼"); rtR = NewEyeRT("DS39 右眼");
                eyeL = MakeEye("DS39 左眼カメラ", src, -0.5f * Ipd, rtL, -2);
                eyeR = MakeEye("DS39 右眼カメラ", src, 0.5f * Ipd, rtR, -1);
                proxyActive = true;
            }
            r.vSyncCount = QualitySettings.vSyncCount; r.targetFrameRate = Application.targetFrameRate; r.qualityMsaa = QualitySettings.antiAliasing;
            r.eyeWidth = c.proxy ? EyeWidth : 0; r.eyeHeight = c.proxy ? EyeHeight : 0; r.eyeMsaa = c.proxy ? EyeMsaa : 0;
            r.cpuTimerFrequency = FrameTimingManager.GetCpuTimerFrequency();
            r.gpuTimerFrequency = FrameTimingManager.GetGpuTimerFrequency();
            r.vsyncsPerSecond = FrameTimingManager.GetVSyncsPerSecond();
            r.frameTimingEnabled = FrameTimingManager.IsFeatureEnabled();

            loopT0 = Time.realtimeSinceStartup;
            looping = true;
            float t0 = Time.realtimeSinceStartup;
            while (Time.realtimeSinceStartup - t0 < warmSeconds) yield return null;
            ClearCollect();
            aliveMin = int.MaxValue; aliveMax = 0;
            collecting = true;
            r.startUtc = DateTime.UtcNow.ToString("O");
            int f0 = Time.frameCount;
            float m0 = Time.realtimeSinceStartup;
            while (Time.realtimeSinceStartup - m0 < measureSeconds) yield return null;
            collecting = false;
            r.measureSeconds = Time.realtimeSinceStartup - m0;
            r.warmSeconds = warmSeconds;
            r.unityFramesInWindow = Time.frameCount - f0;
            r.endUtc = DateTime.UtcNow.ToString("O");
            r.ftStart = lStart.ToArray(); r.ftCpu = lCpu.ToArray(); r.ftCpuMain = lCpuMain.ToArray(); r.ftCpuRender = lCpuRender.ToArray();
            r.ftCpuPresentWait = lWait.ToArray(); r.ftGpu = lGpu.ToArray(); r.ftSync = lSync.ToArray(); r.dt = lDt.ToArray(); r.tPlayed = lT.ToArray();
            r.sprayAliveMin = aliveMin == int.MaxValue ? -1 : aliveMin; r.sprayAliveMax = aliveMax;
            r.screenWidth = Screen.width; r.screenHeight = Screen.height;

            // 測定の後に画像を撮る（測定値には入らない）。区間の終わりの近く（t = windowEnd − 0.05）で止めて撮る
            looping = false;
            SetT(windowEnd - 0.05);
            yield return null;
            yield return new WaitForEndOfFrame();
            var shot = ScreenCapture.CaptureScreenshotAsTexture();
            r.screenshot = "ds39_" + tag + "_" + r.variant + "_" + c.name + ".png";
            File.WriteAllBytes(Path.Combine(outDir, r.screenshot), shot.EncodeToPNG());
            Destroy(shot);
            if (c.proxy)
            {
                r.eyeImages = new[] { "ds39_" + tag + "_" + r.variant + "_" + c.name + "_L.png", "ds39_" + tag + "_" + r.variant + "_" + c.name + "_R.png" };
                SaveRT(rtL, Path.Combine(outDir, r.eyeImages[0]));
                SaveRT(rtR, Path.Combine(outDir, r.eyeImages[1]));
            }
            Teardown();
        }

        RenderTexture NewEyeRT(string name)
        {
            var rt = new RenderTexture(EyeWidth, EyeHeight, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { name = name, antiAliasing = EyeMsaa };
            rt.Create();
            return rt;
        }

        Camera MakeEye(string name, Camera src, float offset, RenderTexture rt, float depth)
        {
            var cam = MakeCamera(name, src);
            cam.transform.position = src.transform.position + src.transform.right * offset;
            cam.fieldOfView = EyeVerticalFov;
            cam.aspect = (float)EyeWidth / EyeHeight;
            cam.targetTexture = rt;
            cam.depth = depth;
            return cam;
        }

        static void SaveRT(RenderTexture rt, string path)
        {
            var res = new RenderTexture(rt.width, rt.height, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            res.Create();
            Graphics.Blit(rt, res);
            var prev = RenderTexture.active;
            RenderTexture.active = res;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            tex.Apply();
            RenderTexture.active = prev;
            File.WriteAllBytes(path, tex.EncodeToPNG());
            Destroy(tex); res.Release(); Destroy(res);
        }

        void OnGUI()
        {
            if (!proxyActive || rtL == null || rtR == null || Event.current.type != EventType.Repaint) return;
            float w = Screen.width, h = Screen.height;
            GUI.DrawTexture(new Rect(0, 0, w * 0.5f, h), rtL, ScaleMode.ScaleToFit, false);
            GUI.DrawTexture(new Rect(w * 0.5f, 0, w * 0.5f, h), rtR, ScaleMode.ScaleToFit, false);
        }

        void ClearCollect()
        {
            seenStarts.Clear(); lStart.Clear(); lCpu.Clear(); lCpuMain.Clear(); lCpuRender.Clear(); lWait.Clear(); lGpu.Clear(); lSync.Clear(); lDt.Clear(); lT.Clear();
        }
    }
}
