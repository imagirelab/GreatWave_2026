using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using Unity.Profiling;
using Unity.Profiling.LowLevel.Unsafe;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.XR;
using UnityEngine.XR.Management;

namespace GreatWave.ArtFirst
{
    // 番号32：GPU 計時の修正と性能の初回測定（Release＝Development でない Windows プレイヤー、見えるウィンドウ）。
    // シーン AF32_Perf.unity（AF32PerfBuild が CP1 の合成シーンを複製して作る）に置く。主役波は番号26 の K*（45°）に
    // 番号28 の NPR v1・外殻線 v0 を付けたもので、データは Git 対象外の Build/ArtFirst/32/data/ に固定した複製から読む。
    //
    // 起動引数：
    //   -af32mode perf|mock   perf＝FrameTimingManager で CPU/GPU を測る、mock＝OpenXR Mock Runtime で両眼を撮る
    //   -af32out <dir>        結果の出力先（JSON・PNG）
    //   -af32data <dir>       主役波のデータ（既定：実行ファイルの 1 つ上の data/）
    //   -af32tag <文字列>     実行の名前（ファイル名に入る）
    //   -af32warm <秒>        条件ごとの助走（既定 3）
    //   -af32measure <秒>     条件ごとの測定（既定 15）
    //   -af32conds a,b,...    測る条件の部分集合（既定：全部）
    // 測定中は PNG の保存・読み戻し・検査をしない。画像は各条件の測定が終わってから撮る。
    public class AF32PerfRunner : MonoBehaviour
    {
        [Tooltip("主役波（シーンでは非表示。データの場所を書き換えてから表示する）")]
        public GameObject wave;
        public string paintingCameraName = "CP1 PaintingCam v1";
        public string seatRightCameraName = "CP1 座席候補 右船カメラ";
        public string gwbFile = "kstar_a45.gwb";
        public string sdfFile = "af28_uvsdf_a45.bin";
        public string warpFile = "af28_uvwarp_a45.json";

        // 立体の代理（Quest 3 の片眼パネル 2064×2208、4×MSAA、IPD 64 mm、縦画角 96°）
        public const int EyeWidth = 2064, EyeHeight = 2208, EyeMsaa = 4;
        public const float Ipd = 0.064f, EyeVerticalFov = 96f;
        public const int DesktopWidth = 1920, DesktopHeight = 1080;

        [Serializable]
        public class CondResult
        {
            public string name, noteJa, view;
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
            public string recGpuName, recGpuUnit;
            public bool recGpuValid;
            public double[] recGpu;
            public string[] memNames;
            public double[] memValues;
            public string screenshot;
            public string[] eyeImages;
        }

        [Serializable]
        public class RunResult
        {
            public string schema = "GreatWave.AF32.run/1";
            public string mode, tag, unity, device, deviceVendor, deviceVersion, graphicsApi, cpu, os, colorSpace, qualityName;
            public int graphicsMemoryMB, systemMemoryMB;
            public bool isDebugBuild;
            public string startedUtc, finishedUtc;
            public string commandLine;
            public string dataDir;
            public string[] dataFiles, dataSha256;
            public int waveVertexCount, sdfTextureBytes;
            public bool frameTimingFeatureEnabled;
            public string refreshRate;
            public int screenWidth, screenHeight, currentResWidth, currentResHeight;
            public string fullScreenMode;
            public string[] availableRecorders;
            public string[] memAfterLoadNames;
            public double[] memAfterLoadValues;
            public CondResult[] conditions;
            public MockResult mock;
            public string errorJa;
        }

        [Serializable]
        public class MockResult
        {
            public string xrRuntimeJsonEnv;
            public bool managerFound;
            public string[] configuredLoaders;
            public string activeLoader;
            public bool xrEnabled, deviceActive;
            public string loadedDeviceName, stereoRenderingMode, runtimeName, runtimeVersion, runtimeApiVersion, pluginVersion;
            public int eyeTextureWidth, eyeTextureHeight, eyeTextureMsaa, eyeTextureVolumeDepth;
            public string eyeTextureDimension, displayTextureLayout;
            public int renderPassCount;
            public string[] renderPasses;
            public string[] leftRightImages, bothImage, commandBufferImages;
            public string captureNoteJa;
            public float[] projLeft, projRight, viewLeft, viewRight;
            public double[] ftCpu, ftGpu;
            public float[] dt;
            // SPI の経路の GPU 時間を外部カウンター（GPU Engine の Running Time）で割り出すための窓（眼のテクスチャを 2064 幅へ拡大）
            public float spiScale;
            public int spiEyeWidth, spiEyeHeight, spiFrames;
            public string spiStartUtc, spiEndUtc;
            public double spiSeconds;
            public bool appGpuTimeAvailable;
            public float[] appGpuTimes;
            public string[] notes;
        }

        RunResult result;
        string outDir, dataDir, tag, mode;
        float warmSeconds = 3f, measureSeconds = 15f;
        HashSet<string> onlyConds;

        Camera displayCam, eyeL, eyeR;
        RenderTexture rtL, rtR;
        bool proxyActive;

        // 測定中の収集
        bool collecting;
        readonly FrameTiming[] ftBuf = new FrameTiming[8];
        readonly HashSet<ulong> seenStarts = new HashSet<ulong>();
        readonly List<long> lStart = new List<long>();
        readonly List<double> lCpu = new List<double>(), lCpuMain = new List<double>(), lCpuRender = new List<double>(), lWait = new List<double>(), lGpu = new List<double>(), lRec = new List<double>();
        readonly List<int> lSync = new List<int>();
        readonly List<float> lDt = new List<float>();
        ProfilerRecorder recGpu;
        string recGpuName = "", recGpuUnit = "";
        readonly List<KeyValuePair<string, ProfilerRecorder>> memRecorders = new List<KeyValuePair<string, ProfilerRecorder>>();

        static string Arg(string key, string def)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == key) return a[i + 1];
            return def;
        }

        IEnumerator Start()
        {
            mode = Arg("-af32mode", "perf");
            tag = Arg("-af32tag", mode);
            outDir = Path.GetFullPath(Arg("-af32out", Path.Combine(Application.dataPath, "..", "out")));
            dataDir = Path.GetFullPath(Arg("-af32data", Path.Combine(Application.dataPath, "..", "..", "data")));
            warmSeconds = float.Parse(Arg("-af32warm", "3"), CultureInfo.InvariantCulture);
            measureSeconds = float.Parse(Arg("-af32measure", "15"), CultureInfo.InvariantCulture);
            var conds = Arg("-af32conds", "");
            onlyConds = string.IsNullOrEmpty(conds) ? null : new HashSet<string>(conds.Split(','));
            Directory.CreateDirectory(outDir);

            result = new RunResult
            {
                mode = mode, tag = tag, unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, deviceVendor = SystemInfo.graphicsDeviceVendor,
                deviceVersion = SystemInfo.graphicsDeviceVersion, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), cpu = SystemInfo.processorType,
                os = SystemInfo.operatingSystem, colorSpace = QualitySettings.activeColorSpace.ToString(), qualityName = QualitySettings.names[QualitySettings.GetQualityLevel()],
                graphicsMemoryMB = SystemInfo.graphicsMemorySize, systemMemoryMB = SystemInfo.systemMemorySize, isDebugBuild = Debug.isDebugBuild,
                startedUtc = DateTime.UtcNow.ToString("O"), commandLine = Environment.CommandLine, dataDir = dataDir,
                frameTimingFeatureEnabled = FrameTimingManager.IsFeatureEnabled()
            };
            Application.runInBackground = true;
            Application.targetFrameRate = -1;
            Screen.SetResolution(DesktopWidth, DesktopHeight, FullScreenMode.Windowed);
            for (int i = 0; i < 30; i++) yield return null;
            result.screenWidth = Screen.width; result.screenHeight = Screen.height;
            result.currentResWidth = Screen.currentResolution.width; result.currentResHeight = Screen.currentResolution.height;
            result.refreshRate = Screen.currentResolution.refreshRateRatio.value.ToString("F3", CultureInfo.InvariantCulture);
            result.fullScreenMode = Screen.fullScreenMode.ToString();
            ListRecorders();

            bool ok = true;
            try { LoadWave(); }
            catch (Exception e) { result.errorJa = "主役波のデータを読めません: " + e.Message; ok = false; }

            if (ok)
            {
                for (int i = 0; i < 10; i++) yield return null;
                var mn = new List<string>(); var mv = new List<double>();
                foreach (var kv in memRecorders) { mn.Add(kv.Key); mv.Add(kv.Value.Valid ? kv.Value.LastValue : double.NaN); }
                result.memAfterLoadNames = mn.ToArray(); result.memAfterLoadValues = mv.ToArray();
                if (mode == "mock") yield return RunMock();
                else yield return RunPerf();
            }
            result.finishedUtc = DateTime.UtcNow.ToString("O");
            File.WriteAllText(Path.Combine(outDir, "af32_" + tag + ".json"), JsonUtility.ToJson(result, false));
            Debug.Log("AF32_DONE tag=" + tag + " mode=" + mode + " error=" + (result.errorJa ?? ""));
            foreach (var kv in memRecorders) kv.Value.Dispose();
            if (recGpu.Valid) recGpu.Dispose();
            yield return null;
            Application.Quit(string.IsNullOrEmpty(result.errorJa) ? 0 : 3);
        }

        // ------------------------------------------------------------------ 主役波
        void LoadWave()
        {
            if (wave == null) throw new InvalidOperationException("主役波の参照がありません。");
            var files = new[] { gwbFile, sdfFile, warpFile };
            result.dataFiles = files;
            result.dataSha256 = new string[files.Length];
            for (int i = 0; i < files.Length; i++) result.dataSha256[i] = Sha(Path.Combine(dataDir, files[i]));
            var km = wave.GetComponent<AF26KStarMesh>();
            var nw = wave.GetComponent<AF28NprWave>();
            km.dataPath = Path.Combine(dataDir, gwbFile);
            nw.sdfPath = Path.Combine(dataDir, sdfFile);
            nw.warpPath = Path.Combine(dataDir, warpFile);
            wave.SetActive(true);   // OnEnable で読み込む
            var mesh = nw.EnsureLoaded();
            result.waveVertexCount = mesh.vertexCount;
            result.sdfTextureBytes = nw.SdfTexture != null ? nw.SdfTexture.width * nw.SdfTexture.height * 4 : 0;
            if (nw.outline != null) nw.outline.enabled = true;
        }

        // ------------------------------------------------------------------ 性能
        struct Cond
        {
            public string name, view, noteJa; public bool proxy; public int vsync;
        }

        IEnumerator RunPerf()
        {
            var list = new List<Cond>
            {
                new Cond { name = "desk1080_painting", view = paintingCameraName, proxy = false, vsync = 0, noteJa = "1920×1080 の見えるウィンドウ、原画視点（PaintingCam v1）、画面へ直接描く、4×MSAA、垂直同期なし" },
                new Cond { name = "desk1080_seat_right", view = seatRightCameraName, proxy = false, vsync = 0, noteJa = "1920×1080 の見えるウィンドウ、右船の座席（D7）、画面へ直接描く、4×MSAA、垂直同期なし" },
                new Cond { name = "desk1080_seat_right_vsync", view = seatRightCameraName, proxy = false, vsync = 1, noteJa = "上と同じで垂直同期あり（表示の周期に合わせて提示する実際のループ）" },
                new Cond { name = "proxy_stereo_seat_right", view = seatRightCameraName, proxy = true, vsync = 0, noteJa = "立体の代理：右船の座席から左右の眼カメラ（IPD 64 mm、縦画角 96°）で各 2064×2208・4×MSAA の RT へ描き、画面へ縮小表示。垂直同期なし" },
            };
            var conds = new List<CondResult>();
            foreach (var c in list)
            {
                if (onlyConds != null && !onlyConds.Contains(c.name)) continue;
                var r = new CondResult { name = c.name, view = c.view, noteJa = c.noteJa, stereoProxy = c.proxy };
                yield return MeasureCondition(c, r);
                conds.Add(r);
                result.conditions = conds.ToArray();
                // 途中経過も書いておく（落ちたときの手がかり）
                File.WriteAllText(Path.Combine(outDir, "af32_" + tag + ".json"), JsonUtility.ToJson(result, false));
            }
            result.conditions = conds.ToArray();
        }

        Camera MakeCamera(string name, Camera src)
        {
            var go = new GameObject(name);
            var cam = go.AddComponent<Camera>();
            cam.transform.SetPositionAndRotation(src.transform.position, src.transform.rotation);
            cam.fieldOfView = src.fieldOfView;
            cam.nearClipPlane = src.nearClipPlane; cam.farClipPlane = src.farClipPlane;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = Color.black;
            cam.allowHDR = false; cam.allowMSAA = true;
            cam.stereoTargetEye = StereoTargetEyeMask.None;
            return cam;
        }

        static Camera FindCam(string name)
        {
            var go = GameObject.Find(name);
            if (go == null) throw new InvalidOperationException("カメラがありません: " + name);
            return go.GetComponent<Camera>();
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
            QualitySettings.vSyncCount = c.vsync;
            Application.targetFrameRate = -1;
            displayCam = MakeCamera("AF32 表示カメラ", src);
            displayCam.depth = 0;
            displayCam.aspect = (float)DesktopWidth / DesktopHeight;
            if (c.proxy)
            {
                displayCam.cullingMask = 0;   // 画面は OnGUI で両眼の縮小を出すだけ
                rtL = NewEyeRT("AF32 左眼"); rtR = NewEyeRT("AF32 右眼");
                eyeL = MakeEye("AF32 左眼カメラ", src, -0.5f * Ipd, rtL, -2);
                eyeR = MakeEye("AF32 右眼カメラ", src, 0.5f * Ipd, rtR, -1);
                proxyActive = true;
            }
            r.vSyncCount = QualitySettings.vSyncCount; r.targetFrameRate = Application.targetFrameRate; r.qualityMsaa = QualitySettings.antiAliasing;
            r.eyeWidth = c.proxy ? EyeWidth : 0; r.eyeHeight = c.proxy ? EyeHeight : 0; r.eyeMsaa = c.proxy ? EyeMsaa : 0;
            r.cpuTimerFrequency = FrameTimingManager.GetCpuTimerFrequency();
            r.gpuTimerFrequency = FrameTimingManager.GetGpuTimerFrequency();
            r.vsyncsPerSecond = FrameTimingManager.GetVSyncsPerSecond();
            r.frameTimingEnabled = FrameTimingManager.IsFeatureEnabled();

            // 助走
            float t0 = Time.realtimeSinceStartup;
            while (Time.realtimeSinceStartup - t0 < warmSeconds) yield return null;
            // 測定
            ClearCollect();
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
            r.ftCpuPresentWait = lWait.ToArray(); r.ftGpu = lGpu.ToArray(); r.ftSync = lSync.ToArray(); r.dt = lDt.ToArray();
            r.recGpuName = recGpuName; r.recGpuUnit = recGpuUnit; r.recGpuValid = recGpu.Valid; r.recGpu = lRec.ToArray();
            r.screenWidth = Screen.width; r.screenHeight = Screen.height;
            var names = new List<string>(); var vals = new List<double>();
            foreach (var kv in memRecorders) { names.Add(kv.Key); vals.Add(kv.Value.Valid ? kv.Value.LastValue : double.NaN); }
            r.memNames = names.ToArray(); r.memValues = vals.ToArray();

            // 測定の後に画像を撮る（測定値には入らない）
            yield return new WaitForEndOfFrame();
            var shot = ScreenCapture.CaptureScreenshotAsTexture();
            r.screenshot = "af32_" + tag + "_" + c.name + ".png";
            File.WriteAllBytes(Path.Combine(outDir, r.screenshot), shot.EncodeToPNG());
            Destroy(shot);
            if (c.proxy)
            {
                r.eyeImages = new[] { "af32_" + tag + "_" + c.name + "_L.png", "af32_" + tag + "_" + c.name + "_R.png" };
                SaveRT(rtL, Path.Combine(outDir, r.eyeImages[0]));
                SaveRT(rtR, Path.Combine(outDir, r.eyeImages[1]));
            }
            Teardown();
        }

        RenderTexture NewEyeRT(string name)
        {
            var rt = new RenderTexture(EyeWidth, EyeHeight, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB)
            { name = name, antiAliasing = EyeMsaa };
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
            seenStarts.Clear(); lStart.Clear(); lCpu.Clear(); lCpuMain.Clear(); lCpuRender.Clear(); lWait.Clear(); lGpu.Clear(); lSync.Clear(); lDt.Clear(); lRec.Clear();
        }

        void Update()
        {
            // 毎フレーム取り込む（FrameTimingManager は数フレーム遅れて値が確定する）。
            FrameTimingManager.CaptureFrameTimings();
            if (!collecting) return;
            lDt.Add(Time.unscaledDeltaTime);
            if (recGpu.Valid) lRec.Add(recGpu.LastValue);
            uint n = FrameTimingManager.GetLatestTimings((uint)ftBuf.Length, ftBuf);
            for (int i = 0; i < n; i++)
            {
                var t = ftBuf[i];
                if (t.frameStartTimestamp == 0 || !seenStarts.Add(t.frameStartTimestamp)) continue;
                lStart.Add((long)t.frameStartTimestamp);
                lCpu.Add(t.cpuFrameTime); lCpuMain.Add(t.cpuMainThreadFrameTime); lCpuRender.Add(t.cpuRenderThreadFrameTime);
                lWait.Add(t.cpuMainThreadPresentWaitTime); lGpu.Add(t.gpuFrameTime); lSync.Add((int)t.syncInterval);
            }
        }

        // ------------------------------------------------------------------ Profiler の記録器（Release でも使えるものだけ有効になる）
        void ListRecorders()
        {
            var handles = new List<ProfilerRecorderHandle>();
            ProfilerRecorderHandle.GetAvailable(handles);
            var names = new List<string>();
            var memWanted = new[] { "Gfx Used Memory", "Gfx Reserved Memory", "Total Used Memory", "Total Reserved Memory", "System Used Memory", "Texture Memory", "Mesh Memory", "Render Textures Bytes",
                "Video Memory Bytes", "App Committed Memory", "App Resident Memory", "System Total Used Memory" };
            foreach (var h in handles)
            {
                var d = ProfilerRecorderHandle.GetDescription(h);
                string nm = d.Name ?? "";
                string cat = d.Category.Name ?? "";
                bool interesting = nm.Contains("GPU") || nm.Contains("Memory") || nm.Contains("Frame Time") || nm.Contains("Gfx") || nm.Contains("Present");
                if (!interesting) continue;
                names.Add(cat + "/" + nm + " [" + d.UnitType + "]");
                if (nm == "GPU Frame Time" && !recGpu.Valid)
                {
                    recGpu = new ProfilerRecorder(h, 1, ProfilerRecorderOptions.Default);
                    recGpu.Start();
                    recGpuName = cat + "/" + nm; recGpuUnit = d.UnitType.ToString();
                }
                if (Array.IndexOf(memWanted, nm) >= 0 && !memRecorders.Exists(k => k.Key == nm))
                {
                    var rec = new ProfilerRecorder(h, 1, ProfilerRecorderOptions.Default);
                    rec.Start();
                    memRecorders.Add(new KeyValuePair<string, ProfilerRecorder>(nm, rec));
                }
            }
            names.Sort(StringComparer.Ordinal);
            result.availableRecorders = names.ToArray();
        }

        // ------------------------------------------------------------------ OpenXR Mock Runtime（XR_RUNTIME_JSON で導入済みパッケージの mock を指す）
        IEnumerator RunMock()
        {
            var m = new MockResult { xrRuntimeJsonEnv = Environment.GetEnvironmentVariable("XR_RUNTIME_JSON") ?? "" };
            result.mock = m;
            var notes = new List<string>();
            var src = FindCam(seatRightCameraName);
            QualitySettings.vSyncCount = 0;
            var cam = MakeCamera("AF32 XR カメラ（右船の座席）", src);
            cam.stereoTargetEye = StereoTargetEyeMask.Both;
            cam.tag = "MainCamera";
            var mgr = XRGeneralSettings.Instance != null ? XRGeneralSettings.Instance.Manager : null;
            m.managerFound = mgr != null;
            if (mgr == null) { result.errorJa = "XRGeneralSettings がありません。"; m.notes = notes.ToArray(); yield break; }
            var loaders = new List<string>();
            foreach (var l in mgr.activeLoaders) loaders.Add(l != null ? l.name : "null");
            m.configuredLoaders = loaders.ToArray();
            yield return mgr.InitializeLoader();
            m.activeLoader = mgr.activeLoader != null ? mgr.activeLoader.name : "";
            if (mgr.activeLoader == null) { result.errorJa = "OpenXR ローダーを初期化できません（Mock Runtime が見つからない可能性）。"; m.notes = notes.ToArray(); yield break; }
            mgr.StartSubsystems();
            float t0 = Time.realtimeSinceStartup;
            while (Time.realtimeSinceStartup - t0 < 3f) yield return null;

            m.xrEnabled = XRSettings.enabled; m.deviceActive = XRSettings.isDeviceActive; m.loadedDeviceName = XRSettings.loadedDeviceName;
            m.stereoRenderingMode = XRSettings.stereoRenderingMode.ToString();
            m.eyeTextureWidth = XRSettings.eyeTextureWidth; m.eyeTextureHeight = XRSettings.eyeTextureHeight;
            var desc = XRSettings.eyeTextureDesc;
            m.eyeTextureMsaa = desc.msaaSamples; m.eyeTextureVolumeDepth = desc.volumeDepth; m.eyeTextureDimension = desc.dimension.ToString();
            try
            {
                m.runtimeName = UnityEngine.XR.OpenXR.OpenXRRuntime.name; m.runtimeVersion = UnityEngine.XR.OpenXR.OpenXRRuntime.version;
                m.runtimeApiVersion = UnityEngine.XR.OpenXR.OpenXRRuntime.apiVersion; m.pluginVersion = UnityEngine.XR.OpenXR.OpenXRRuntime.pluginVersion;
            }
            catch (Exception e) { notes.Add("OpenXRRuntime: " + e.Message); }
            var displays = new List<XRDisplaySubsystem>();
            SubsystemManager.GetSubsystems(displays);
            var passes = new List<string>();
            foreach (var d in displays)
            {
                if (!d.running) continue;
                m.displayTextureLayout = d.textureLayout.ToString();
                m.renderPassCount = d.GetRenderPassCount();
                for (int i = 0; i < m.renderPassCount; i++)
                {
                    d.GetRenderPass(i, out var p);
                    var td = p.renderTargetDesc;
                    passes.Add("pass" + i + " " + td.width + "x" + td.height + " msaa" + td.msaaSamples + " " + td.dimension + " slices" + td.volumeDepth + " params" + p.GetRenderParameterCount());
                }
            }
            m.renderPasses = passes.ToArray();

            // 両眼の画像：① ScreenCapture の左右 ② カメラの最後に眼テクスチャの配列の各スライスを複写
            RenderTexture cb0 = null, cb1 = null;
            CommandBuffer cbuf = null;
            if (m.eyeTextureWidth > 0)
            {
                cb0 = new RenderTexture(m.eyeTextureWidth, m.eyeTextureHeight, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB); cb0.Create();
                cb1 = new RenderTexture(m.eyeTextureWidth, m.eyeTextureHeight, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB); cb1.Create();
                cbuf = new CommandBuffer { name = "AF32 両眼の複写" };
                cbuf.Blit(BuiltinRenderTextureType.CameraTarget, cb0, Vector2.one, Vector2.zero, 0, 0);
                cbuf.Blit(BuiltinRenderTextureType.CameraTarget, cb1, Vector2.one, Vector2.zero, 1, 0);
                cam.AddCommandBuffer(CameraEvent.AfterEverything, cbuf);
            }
            for (int i = 0; i < 10; i++) yield return null;
            yield return new WaitForEndOfFrame();
            try
            {
                var l = ScreenCapture.CaptureScreenshotAsTexture(ScreenCapture.StereoScreenCaptureMode.LeftEye);
                var r = ScreenCapture.CaptureScreenshotAsTexture(ScreenCapture.StereoScreenCaptureMode.RightEye);
                m.leftRightImages = new[] { "af32_" + tag + "_mock_sc_L.png", "af32_" + tag + "_mock_sc_R.png" };
                File.WriteAllBytes(Path.Combine(outDir, m.leftRightImages[0]), l.EncodeToPNG());
                File.WriteAllBytes(Path.Combine(outDir, m.leftRightImages[1]), r.EncodeToPNG());
                notes.Add("ScreenCapture 左 " + l.width + "x" + l.height + "、右 " + r.width + "x" + r.height);
                Destroy(l); Destroy(r);
                var b = ScreenCapture.CaptureScreenshotAsTexture(ScreenCapture.StereoScreenCaptureMode.BothEyes);
                m.bothImage = new[] { "af32_" + tag + "_mock_sc_both.png" };
                File.WriteAllBytes(Path.Combine(outDir, m.bothImage[0]), b.EncodeToPNG());
                notes.Add("ScreenCapture 両眼 " + b.width + "x" + b.height);
                Destroy(b);
            }
            catch (Exception e) { notes.Add("ScreenCapture 失敗: " + e.Message); }
            if (cbuf != null)
            {
                cam.RemoveCommandBuffer(CameraEvent.AfterEverything, cbuf);
                m.commandBufferImages = new[] { "af32_" + tag + "_mock_cb_L.png", "af32_" + tag + "_mock_cb_R.png" };
                SaveRT(cb0, Path.Combine(outDir, m.commandBufferImages[0]));
                SaveRT(cb1, Path.Combine(outDir, m.commandBufferImages[1]));
                cb0.Release(); cb1.Release();
            }
            m.captureNoteJa = "Mock Runtime は表示装置を持たないので、Unity 側で眼のテクスチャを読み出した。HMD のレンズ越しの見え方ではない。";
            m.projLeft = M16(cam.GetStereoProjectionMatrix(Camera.StereoscopicEye.Left)); m.projRight = M16(cam.GetStereoProjectionMatrix(Camera.StereoscopicEye.Right));
            m.viewLeft = M16(cam.GetStereoViewMatrix(Camera.StereoscopicEye.Left)); m.viewRight = M16(cam.GetStereoViewMatrix(Camera.StereoscopicEye.Right));

            // SPI の経路の GPU 時間（外部カウンターで割り出す窓）：眼のテクスチャの幅を Quest 3 の 2064 に合わせる（Mock は MSAA 1 のみ）
            if (m.eyeTextureWidth > 0)
            {
                m.spiScale = (float)EyeWidth / m.eyeTextureWidth;
                XRSettings.eyeTextureResolutionScale = m.spiScale;
                float s0 = Time.realtimeSinceStartup;
                while (Time.realtimeSinceStartup - s0 < 3f) yield return null;
                m.spiEyeWidth = XRSettings.eyeTextureWidth; m.spiEyeHeight = XRSettings.eyeTextureHeight;
                var gpuTimes = new List<float>();
                XRDisplaySubsystem disp = null;
                foreach (var d in displays) if (d.running) disp = d;
                m.spiStartUtc = DateTime.UtcNow.ToString("O");
                int sf0 = Time.frameCount;
                float w0 = Time.realtimeSinceStartup;
                while (Time.realtimeSinceStartup - w0 < 10f)
                {
                    yield return null;
                    if (disp != null && disp.TryGetAppGPUTimeLastFrame(out float g)) { m.appGpuTimeAvailable = true; gpuTimes.Add(g); }
                }
                m.spiSeconds = Time.realtimeSinceStartup - w0;
                m.spiFrames = Time.frameCount - sf0;
                m.spiEndUtc = DateTime.UtcNow.ToString("O");
                m.appGpuTimes = gpuTimes.ToArray();
                XRSettings.eyeTextureResolutionScale = 1f;
                notes.Add("SPI の窓：眼のテクスチャ " + m.spiEyeWidth + "x" + m.spiEyeHeight + "、" + m.spiFrames + " フレーム、" + m.spiSeconds.ToString("F2", CultureInfo.InvariantCulture) + " 秒。TryGetAppGPUTimeLastFrame は Mock が返す値で実測ではない。");
            }

            // 記録のみ：Mock で動かしたときの計時（Mock の xrWaitFrame の周期に左右される。性能の判定には使わない）
            ClearCollect();
            collecting = true;
            float m0 = Time.realtimeSinceStartup;
            while (Time.realtimeSinceStartup - m0 < 5f) yield return null;
            collecting = false;
            m.ftCpu = lCpu.ToArray(); m.ftGpu = lGpu.ToArray(); m.dt = lDt.ToArray();
            m.notes = notes.ToArray();
            mgr.StopSubsystems();
            mgr.DeinitializeLoader();
            yield return null;
        }

        static float[] M16(Matrix4x4 m)
        {
            var a = new float[16];
            for (int i = 0; i < 16; i++) a[i] = m[i];   // 列優先（Unity の添字）
            return a;
        }

        static string Sha(string path)
        {
            using (var s = SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
