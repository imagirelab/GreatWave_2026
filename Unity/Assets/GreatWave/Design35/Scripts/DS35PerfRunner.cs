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

namespace GreatWave.Design35
{
    // 設計35：3 版（一覧どおり／軽量版／誇張版）の最大密度の区間の性能。美術優先32 の計測器（AF32PerfRunner）と同じ測り方で、
    // Release（Development でない）の Windows プレイヤーを見えるウィンドウで動かし、FrameTimingManager の CPU・GPU とフレームの開始時刻を集める。
    //   ・場面：設計34 の DS34_ThreeLayers.unity の写し（DS35_Perf.unity。DS35Build が作る）。3 層（白の帯・爪・飛沫）を 1 つの時計で描く。
    //   ・区間：体験の時刻 t を [windowStart, windowEnd)（既定 11〜12 s：3 版とも爪と飛沫が全部出ている、t* の直前の 1 秒）で実時間の速さで繰り返す。
    //     毎フレーム DS30SinglePlayback.Seek(t)（主役波・海の τ(t) と GWClock）→ 爪（DS34ClawPlayer、実行順 60）と飛沫（DS31、実行順 60）が同じ時計を読む。
    //   ・条件：① 1920×1080・原画視点 ② 1920×1080・座席 v1 ③ 立体の代理（座席 v1 から左右の眼カメラ、IPD 64 mm、縦画角 96°、各 2064×2208・4×MSAA の RT）。
    //     AF32 と同じ（③ は画面へ縮小表示）。垂直同期なし。
    //   ・版の切り替え：爪の layoutPath と飛沫の dataPath を差し替えて読み直す（測定の外）。
    // 起動引数：-ds35out <dir>、-ds35tag <名前>、-ds35warm <秒>（既定 3）、-ds35measure <秒>（既定 12）、-ds35variants v1_list,v2_light,v3_exag、
    //   -ds35conds desk1080_painting,desk1080_seat,proxy_stereo_seat、-ds35window 11,12。
    // 作業ディレクトリは Unity プロジェクト（相対パスの Build/... を読むため。起動のスクリプトが決める）。
    [DefaultExecutionOrder(40)]
    public class DS35PerfRunner : MonoBehaviour
    {
        [Serializable]
        public class Variant
        {
            public string name, nameJa, clawLayout, sprayData;
        }

        public List<Variant> variants = new List<Variant>();
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
            public string schema = "GreatWave.DS35.perf_run/1";
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
        DS31InstancedParticles spray;
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
            tag = Arg("-ds35tag", "run");
            outDir = Path.GetFullPath(Arg("-ds35out", Path.Combine(Application.dataPath, "..", "out")));
            warmSeconds = float.Parse(Arg("-ds35warm", "3"), CultureInfo.InvariantCulture);
            measureSeconds = float.Parse(Arg("-ds35measure", "12"), CultureInfo.InvariantCulture);
            var vs = Arg("-ds35variants", ""); onlyVariants = string.IsNullOrEmpty(vs) ? null : new HashSet<string>(vs.Split(','));
            var cs = Arg("-ds35conds", ""); onlyConds = string.IsNullOrEmpty(cs) ? null : new HashSet<string>(cs.Split(','));
            var win = Arg("-ds35window", "");
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
                spray = FindAnyObjectByType<DS31InstancedParticles>(FindObjectsInactive.Include);
                if (play == null || claws == null || spray == null) throw new InvalidOperationException("再生器・爪・飛沫のどれかがありません。");
                play.enabled = false;   // 時刻はこの計測器が Seek で決める（Tick で進めない）
                play.Prepare();
                spray.drawInPlayMode = true;
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
                            clawLayout = v.clawLayout, sprayData = v.sprayData, clawCount = claws.ClawCount, clawVertices = claws.VertexCount, clawTriangles = claws.TriangleCount,
                            clawFramesSha256 = claws.FramesSha256, sprayCount = spray.Count, spraySha256 = spray.DataSha256 };
                        yield return MeasureCondition(c, r);
                        conds.Add(r);
                        result.conditions = conds.ToArray();
                        File.WriteAllText(Path.Combine(outDir, "ds35_" + tag + ".json"), JsonUtility.ToJson(result, false));
                    }
                }
                result.conditions = conds.ToArray();
            }
            result.finishedUtc = DateTime.UtcNow.ToString("O");
            File.WriteAllText(Path.Combine(outDir, "ds35_" + tag + ".json"), JsonUtility.ToJson(result, false));
            Debug.Log("DS35_DONE tag=" + tag + " error=" + (result.errorJa ?? ""));
            yield return null;
            Application.Quit(string.IsNullOrEmpty(result.errorJa) ? 0 : 3);
        }

        float LoadVariant(Variant v)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            looping = false;
            claws.Release(); claws.layoutPath = v.clawLayout; claws.Load();
            spray.Release(); spray.dataPath = v.sprayData; spray.Load();
            SetT(windowStart);
            return (float)sw.Elapsed.TotalSeconds;
        }

        void SetT(double t)
        {
            play.Seek(t);
            claws.ApplyT(t);
            spray.ApplyT(t);
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
            aliveMin = Math.Min(aliveMin, spray.AliveNow); aliveMax = Math.Max(aliveMax, spray.AliveNow);
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
            displayCam = MakeCamera("DS35 表示カメラ", src);
            displayCam.depth = 0;
            displayCam.aspect = (float)DesktopWidth / DesktopHeight;
            if (c.proxy)
            {
                displayCam.cullingMask = 0;
                rtL = NewEyeRT("DS35 左眼"); rtR = NewEyeRT("DS35 右眼");
                eyeL = MakeEye("DS35 左眼カメラ", src, -0.5f * Ipd, rtL, -2);
                eyeR = MakeEye("DS35 右眼カメラ", src, 0.5f * Ipd, rtR, -1);
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
            r.screenshot = "ds35_" + tag + "_" + r.variant + "_" + c.name + ".png";
            File.WriteAllBytes(Path.Combine(outDir, r.screenshot), shot.EncodeToPNG());
            Destroy(shot);
            if (c.proxy)
            {
                r.eyeImages = new[] { "ds35_" + tag + "_" + r.variant + "_" + c.name + "_L.png", "ds35_" + tag + "_" + r.variant + "_" + c.name + "_R.png" };
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
