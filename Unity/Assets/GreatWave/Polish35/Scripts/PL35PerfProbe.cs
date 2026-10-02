using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using GreatWave.ArtFirst;
using GreatWave.Design31;
using GreatWave.Design34;
using GreatWave.Design38;
using GreatWave.Design46;
using GreatWave.Design47;
using GreatWave.Design50;
using GreatWave.Polish30;
using GreatWave.Polish32;
using UnityEngine;

namespace GreatWave.Polish35
{
    // 仕上げ35（数量と負荷）：体験の場面（設計50 の Release の場面の仕上げ35 の写し）のまま、最大密度の区間（大波の時刻 t 11〜12 s）を繰り返して
    // フレームの時間を測る計測器。起動引数 --pl35perf のときだけ働く（無ければ何もしない。体験の exe と同じ exe）。
    //   ・入口の画面で DS50Shell の Begin を呼び（利用者の Enter と同じ道。DS50AutoTest は使わない）、導入（操作なし）→ 接近 → 形成を体験のまま進め、
    //     大波の時刻が windowStart − 0.2 s に来たら共通時計（GWClock、Master）を止め、毎フレーム clock.Seek（形成の始まり ＋ t）で t を
    //     [windowStart, windowEnd) の中で実時間の速さで繰り返す（設計35 の DS35PerfRunner と同じ区間と進め方。段（水面・船用水面データ・白・爪・飛沫・座席の船・
    //     出来事・音）は体験と同じ関数を同じ順で呼ぶ）。
    //   ・段の時間：水面・船用水面データ・白・爪・飛沫の 5 つの段を、同じ関数を呼ぶ包み（Stopwatch）で登録し直す（GWClock.Register は同じ名前を置き換え、
    //     order は元と同じなので順は変わらない）。爪の段は仕上げ32 の PL32ClawDriver.Step（非公開）をそのまま呼ぶ。
    //   ・条件（既定の並び。-pl35conds で選ぶ）：
    //       exp_hmd           体験の PC の画面（HMD Camera、1920×1080 の窓、単眼）
    //       desk1080_painting 原画視点（DS27 painting）を画面へ
    //       desk1080_seat     座席 v1（DS27 seat）を画面へ
    //       proxy_stereo_hmd  立体の代理：HMD Camera の位置から左右の眼（IPD 64 mm、縦画角 96°、各 2064×2208・4×MSAA の RT。設計35・美術優先32 と同じ）
    //       proxy_stereo_seat 立体の代理：DS27 seat から（設計35 と同じ）
    //       exp_hmd_static    時刻を止めたまま（段を呼ばない。描画と段の外の毎フレームの仕事だけ）
    //       exp_hmd_no_boatwater / exp_hmd_no_claws / exp_hmd_no_spray / exp_hmd_no_all3：その段を呼ばず、爪・飛沫は描画も切る（負荷の切り分け）。
    //         船用水面データは、座席の船の段（seat_boat）の水の問い合わせ（HeightAt → Sync）でも作り直されるので、切る時は DS43BoatWater.playback を外して作り直しを止める
    //         （船はその間、最後に作った索引の水を読む。測る間だけ）。
    //       ps_static_*：時刻を t 11.5 s で止めた立体の代理（HMD Camera から）。GPU の描画の時間だけを、CPU の待ちの泡なしで見る（all／no_sea／no_hero／no_claws／no_spray）。
    //       desk1080_painting_static・desk1080_seat_static：同じく 1920×1080 の原画視点・座席 v1。
    //   ・数え方は設計35 と同じ：FrameTimingManager の開始時刻の差（間隔）、CPU 主スレッド・GPU の時間。条件ごとに助走 -pl35warm（既定 2 s）・測定 -pl35measure（既定 8 s）。
    //   ・出力：-pl35out <dir> に pl35perf_<tag>.json と、条件ごとの画面（測定の後に t = windowEnd − 0.05 で止めて撮る。測定値には入らない）。
    // 見え方は変えない（測る間だけカメラを足し・切り、段を包む）。HMD 実機ではない（PS VR2 は未導入）。
    [DefaultExecutionOrder(-280)]
    public class PL35PerfProbe : MonoBehaviour
    {
        public DS50Shell shell;
        public DS47Flow flow;
        public GWClock clock;
        public DS46ClockBus bus;
        public PL32ClawDriver clawDriver;
        public string paintingCameraName = "DS27 painting";
        public string seatCameraName = "DS27 seat";
        public float windowStart = 11f, windowEnd = 12f;

        public const int EyeWidth = 2064, EyeHeight = 2208, EyeMsaa = 4;
        public const float Ipd = 0.064f, EyeVerticalFov = 96f;
        static readonly Color SkyTop = new Color32(249, 232, 196, 255);

        [Serializable]
        public class CondResult
        {
            public string name, noteJa, view;
            public bool stereoProxy, seekEachFrame, boatWaterOn, clawsOn, sprayOn;
            public int vSyncCount, targetFrameRate, screenWidth, screenHeight, eyeWidth, eyeHeight, eyeMsaa;
            public string startUtc, endUtc;
            public double warmSeconds, measureSeconds;
            public int unityFrames, gcGen0Collections, gcGen1Collections, gcGen2Collections, boatWaterRebuilds;
        public bool seaOn, heroOn;
        public long privateBytesEnd, workingSetEnd, monoHeapEnd, totalReservedEnd;
            public long monoUsedStart, monoUsedEnd, totalAllocatedStart, totalAllocatedEnd;
            public double boatWaterRebuildMs;
            public long[] ftStart;
            public double[] ftCpuMain, ftCpuRender, ftGpu;
            public float[] dt, tPlayed;
            // 段の時間（ms、フレームごと。そのフレームで呼ばなかった段は 0）
            public float[] msSeek, msWater, msBoatWater, msWhite, msClaws, msSpray;
            public string screenshot;
            public string[] eyeImages;
        }

        [Serializable]
        public class RunResult
        {
            public string schema = "GreatWave.Polish35.perf_probe/1";
            public string tag, unity, device, graphicsApi, cpu, os, qualityName, startedUtc, finishedUtc, commandLine, errorJa, hmdCamera, paintingCamera, seatCamera;
            public bool isDebugBuild, frameTimingFeatureEnabled, xrActive;
            public int screenWidth, screenHeight, clawVertices, clawTriangles, clawItems, sprayCount0, sprayCount1;
            public float windowStart, windowEnd;
            public double waveStartS, handoverS, reachRealS, takeoverWave;
            public string[] stagesBefore, stagesAfter;
            public bool legacy, fastOutlineActive;
            public float[] selfCheckT, selfCheckMaxVertexDiff, selfCheckMaxNormalDiff;
            public int seaRenderers, heroRenderers;
            public CondResult[] conditions;
        }

        static string Arg(string key, string def)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == key) return a[i + 1];
            return def;
        }

        RunResult result;
        string outDir, tag;
        float warmS = 2f, measureS = 8f;
        bool looping, collecting, seekOn = true, boatWaterOn = true, clawsOn = true, sprayOn = true;
        GreatWave.Design30.DS30SinglePlayback boatWaterPlayback;
        readonly List<Renderer> seaRenderers = new List<Renderer>(), heroRenderers = new List<Renderer>();
        float loopT0;
        Camera hmdCam, displayCam, eyeL, eyeR, srcEnabledCam;
        RenderTexture rtL, rtR;
        bool proxyActive;
        Action<double, bool> clawStep;
        readonly System.Diagnostics.Stopwatch sw = new System.Diagnostics.Stopwatch();
        float fWater, fBoat, fWhite, fClaws, fSpray;

        readonly FrameTiming[] ftBuf = new FrameTiming[8];
        readonly HashSet<ulong> seen = new HashSet<ulong>();
        readonly List<long> lStart = new List<long>();
        readonly List<double> lMain = new List<double>(), lRender = new List<double>(), lGpu = new List<double>();
        readonly List<float> lDt = new List<float>(), lT = new List<float>(), lSeek = new List<float>(), lWater = new List<float>(), lBoat = new List<float>(), lWhite = new List<float>(), lClaws = new List<float>(), lSpray = new List<float>();

        void Awake()
        {
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "--pl35perf") < 0) { enabled = false; return; }
        }

        IEnumerator Start()
        {
            if (!enabled) yield break;
            tag = Arg("-pl35tag", "run");
            outDir = Path.GetFullPath(Arg("-pl35out", Path.Combine(DS50Shell.StartCwd, "pl35_out")));
            warmS = float.Parse(Arg("-pl35warm", "2"), CultureInfo.InvariantCulture);
            measureS = float.Parse(Arg("-pl35measure", "8"), CultureInfo.InvariantCulture);
            var condArg = Arg("-pl35conds", "");
            Directory.CreateDirectory(outDir);
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = -1;
            Application.runInBackground = true;
            result = new RunResult
            {
                tag = tag, unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                cpu = SystemInfo.processorType, os = SystemInfo.operatingSystem, qualityName = QualitySettings.names[QualitySettings.GetQualityLevel()],
                isDebugBuild = Debug.isDebugBuild, frameTimingFeatureEnabled = FrameTimingManager.IsFeatureEnabled(), startedUtc = DateTime.UtcNow.ToString("O"),
                commandLine = Environment.CommandLine, windowStart = windowStart, windowEnd = windowEnd, xrActive = UnityEngine.XR.XRSettings.isDeviceActive
            };
            string err = null;
            // 入口の画面が出るまで待ち、Begin（利用者の Enter と同じ）を呼ぶ
            float t0 = Time.realtimeSinceStartup;
            while (shell == null || shell.State != DS50Shell.ShellState.Entry || shell.VrInitBusy || !flow.Ready)
            {
                if (Time.realtimeSinceStartup - t0 > 120f) { err = "入口の画面に来ない"; break; }
                yield return null;
            }
            for (int i = 0; i < 30 && err == null; i++) yield return null;
            if (err == null)
            {
                var begin = typeof(DS50Shell).GetMethod("Begin", BindingFlags.NonPublic | BindingFlags.Instance);
                begin.Invoke(shell, new object[] { "pl35perf" });
                float r0 = Time.realtimeSinceStartup;
                while (!(flow.CurrentPhase == DS47Flow.Phase.Formation && clock.WaveSeconds >= windowStart - 0.2))
                {
                    if (Time.realtimeSinceStartup - r0 > 240f) { err = "形成の区間に来ない phase=" + flow.CurrentPhase + " wave=" + clock.WaveSeconds; break; }
                    yield return null;
                }
                result.reachRealS = Time.realtimeSinceStartup - r0;
            }
            if (err == null)
            {
                try { TakeOver(); }
                catch (Exception e) { err = "乗っ取りに失敗: " + e.Message; }
            }
            if (err == null)
            {
                var conds = new List<CondResult>();
                foreach (var c in CondList())
                {
                    if (!string.IsNullOrEmpty(condArg) && Array.IndexOf(condArg.Split(','), c.name) < 0) continue;
                    var r = new CondResult();
                    yield return Measure(c, r);
                    conds.Add(r);
                    result.conditions = conds.ToArray();
                    Write();
                }
                result.conditions = conds.ToArray();
                // 修正の回 1 の検査：DS38ClawOutline.Sync と PL35ClawOutlineFast.FastSync の線のメッシュの差（測定の後。測定値には入らない）
                var fast = FindAnyObjectByType<PL35ClawOutlineFast>();
                if (fast != null && fast.Active)
                {
                    looping = false;
                    var ts = new[] { 7.0123f, 9.0f, 10.5f, 11.5123f, 12.0f };
                    result.selfCheckT = ts; result.selfCheckMaxVertexDiff = new float[ts.Length]; result.selfCheckMaxNormalDiff = new float[ts.Length];
                    for (int i = 0; i < ts.Length; i++) { var d = fast.SelfCheck(ts[i]); result.selfCheckMaxVertexDiff[i] = d.x; result.selfCheckMaxNormalDiff[i] = d.y; }
                }
            }
            result.errorJa = err;
            result.finishedUtc = DateTime.UtcNow.ToString("O");
            Write();
            Debug.Log("PL35_PERF_DONE tag=" + tag + " error=" + (err ?? ""));
            yield return null;
            Application.Quit(err == null ? 0 : 3);
        }

        void Write() => File.WriteAllText(Path.Combine(outDir, "pl35perf_" + tag + ".json"), JsonUtility.ToJson(result, false));

        void TakeOver()
        {
            if (bus == null) bus = FindAnyObjectByType<DS46ClockBus>();
            if (clawDriver == null) clawDriver = FindAnyObjectByType<PL32ClawDriver>();
            hmdCam = flow.hmdCamera;
            result.hmdCamera = hmdCam != null ? hmdCam.name : "";
            result.stagesBefore = clock.StageNames().ToArray();
            result.waveStartS = flow.WaveStartS; result.handoverS = flow.HandoverS; result.takeoverWave = clock.WaveSeconds;
            if (bus.claws != null) { result.clawVertices = bus.claws.VertexCount; result.clawTriangles = bus.claws.TriangleCount; result.clawItems = bus.claws.ClawCount; }
            if (bus.sprays.Count > 0 && bus.sprays[0] != null) result.sprayCount0 = bus.sprays[0].Count;
            if (bus.sprays.Count > 1 && bus.sprays[1] != null) result.sprayCount1 = bus.sprays[1].Count;
            // 海と主役波のレンダラー（描画の切り分け用。いま描いているものだけ）
            foreach (var sea in FindObjectsByType<PL30UkiyoeSea>(FindObjectsSortMode.None))
                foreach (var e in sea.sheets) if (e != null && e.sheet != null) foreach (var x in e.sheet.GetComponentsInChildren<Renderer>(false)) if (x.enabled && !seaRenderers.Contains(x)) seaRenderers.Add(x);
            if (bus.playback != null) foreach (var sh in bus.playback.sheets) if (sh != null && sh.sheetName == "hero") foreach (var x in sh.GetComponentsInChildren<Renderer>(false)) if (x.enabled && !heroRenderers.Contains(x)) heroRenderers.Add(x);
            result.seaRenderers = seaRenderers.Count; result.heroRenderers = heroRenderers.Count;
            clock.Stop();
            // 段を同じ関数を呼ぶ包みで登録し直す（順の値は DS46ClockBus と同じ）
            var fast = FindAnyObjectByType<PL35ClawOutlineFast>();
            result.legacy = PL35ClawOutlineFast.Legacy; result.fastOutlineActive = fast != null && fast.Active;
            if (fast != null && fast.Active) clawStep = (t, sync) => fast.Step(t);   // 修正の回 1 の道（仕上げ35 の採る状態）
            else if (clawDriver != null && clawDriver.OnBus)
            {
                var mi = typeof(PL32ClawDriver).GetMethod("Step", BindingFlags.NonPublic | BindingFlags.Instance);
                clawStep = (Action<double, bool>)Delegate.CreateDelegate(typeof(Action<double, bool>), clawDriver, mi);
            }
            clock.Register("water", DS46ClockBus.OrderWater, (c, st) => { sw.Restart(); if (bus.playback != null) bus.playback.Seek(st.wave); fWater += Ms(); });
            clock.Register("boat_water", DS46ClockBus.OrderBoatWater, (c, st) => { if (!boatWaterOn) return; sw.Restart(); if (bus.boatWater != null) bus.boatWater.Sync(); fBoat += Ms(); });
            clock.Register("white", DS46ClockBus.OrderWhite, (c, st) => { sw.Restart(); if (bus.layers != null) bus.layers.ApplyToggles(); fWhite += Ms(); });
            clock.Register("claws", DS46ClockBus.OrderClaws, (c, st) =>
            {
                if (!clawsOn) return;
                sw.Restart();
                if (clawStep != null) clawStep(st.wave, true);
                else { if (bus.claws != null) bus.claws.ApplyT(st.wave); if (bus.clawLine != null) bus.clawLine.Sync(); }
                fClaws += Ms();
            });
            clock.Register("spray", DS46ClockBus.OrderSpray, (c, st) => { if (!sprayOn) return; sw.Restart(); foreach (var s in bus.sprays) if (s != null) s.ApplyT(st.wave); fSpray += Ms(); });
            result.stagesAfter = clock.StageNames().ToArray();
            loopT0 = Time.realtimeSinceStartup;
            looping = true;
        }

        float Ms() => (float)sw.Elapsed.TotalMilliseconds;

        struct Cond { public string name, view, noteJa; public bool proxy, seek, boat, claws, spray, noSea, noHero; }

        List<Cond> CondList() => new List<Cond>
        {
            new Cond { name = "exp_hmd", view = "hmd", seek = true, boat = true, claws = true, spray = true, noteJa = "体験の PC の画面（HMD Camera、1920×1080 の窓、単眼）。段は体験と同じ" },
            new Cond { name = "desk1080_painting", view = paintingCameraName, seek = true, boat = true, claws = true, spray = true, noteJa = "原画視点（DS27 painting）を 1920×1080 の窓へ" },
            new Cond { name = "desk1080_seat", view = seatCameraName, seek = true, boat = true, claws = true, spray = true, noteJa = "座席 v1（DS27 seat）を 1920×1080 の窓へ" },
            new Cond { name = "proxy_stereo_hmd", view = "hmd", proxy = true, seek = true, boat = true, claws = true, spray = true, noteJa = "立体の代理：HMD Camera から左右の眼（IPD 64 mm、縦画角 96°、各 2064×2208・4×MSAA の RT）、画面へ縮小表示" },
            new Cond { name = "proxy_stereo_seat", view = seatCameraName, proxy = true, seek = true, boat = true, claws = true, spray = true, noteJa = "立体の代理：DS27 seat から（設計35 と同じ）" },
            new Cond { name = "exp_hmd_static", view = "hmd", seek = false, boat = true, claws = true, spray = true, noteJa = "時刻を t 11.5 s で止める（段を呼ばない）。描画と段の外の毎フレームの仕事だけ" },
            new Cond { name = "exp_hmd_no_boatwater", view = "hmd", seek = true, boat = false, claws = true, spray = true, noteJa = "船用水面データの段を呼ばない（船はその間の水を読み直さない）" },
            new Cond { name = "exp_hmd_no_spray", view = "hmd", seek = true, boat = true, claws = true, spray = false, noteJa = "飛沫の段を呼ばず、飛沫を描かない" },
            new Cond { name = "exp_hmd_no_claws", view = "hmd", seek = true, boat = true, claws = false, spray = true, noteJa = "爪の段（爪の頂点と縁の線）を呼ばず、爪と線を描かない" },
            new Cond { name = "exp_hmd_no_all3", view = "hmd", seek = true, boat = false, claws = false, spray = false, noteJa = "船用水面データ・爪・飛沫の 3 つの段を呼ばず、爪・飛沫を描かない" },
            new Cond { name = "proxy_stereo_hmd_no_boatwater", view = "hmd", proxy = true, seek = true, boat = false, claws = true, spray = true, noteJa = "立体の代理（HMD Camera）で、船用水面データの作り直しだけを止める（仕上げ43 の後の見込み）" },
            new Cond { name = "desk1080_painting_static", view = paintingCameraName, seek = false, boat = true, claws = true, spray = true, noteJa = "原画視点、時刻を t 11.5 s で止める（描画の時間）" },
            new Cond { name = "desk1080_seat_static", view = seatCameraName, seek = false, boat = true, claws = true, spray = true, noteJa = "座席 v1、時刻を t 11.5 s で止める（描画の時間）" },
            new Cond { name = "ps_static_all", view = "hmd", proxy = true, seek = false, boat = true, claws = true, spray = true, noteJa = "立体の代理（HMD Camera）、時刻を t 11.5 s で止める（描画の時間）" },
            new Cond { name = "ps_static_no_sea", view = "hmd", proxy = true, seek = false, boat = true, claws = true, spray = true, noSea = true, noteJa = "同じ、周りの海（near・far のシートとその子の線・紙）を描かない" },
            new Cond { name = "ps_static_no_hero", view = "hmd", proxy = true, seek = false, boat = true, claws = true, spray = true, noHero = true, noteJa = "同じ、主役波のシート（とその子）を描かない" },
            new Cond { name = "ps_static_no_claws", view = "hmd", proxy = true, seek = false, boat = true, claws = false, spray = true, noteJa = "同じ、爪と縁の線を描かない" },
            new Cond { name = "ps_static_no_spray", view = "hmd", proxy = true, seek = false, boat = true, claws = true, spray = false, noteJa = "同じ、飛沫を描かない" },
        };

        void SetLayers(bool claws, bool spray)
        {
            if (bus.layers != null) { bus.layers.clawsOn = claws; bus.layers.sprayOn = spray; bus.layers.ApplyToggles(); }
            if (bus.clawLine != null && bus.clawLine.Line != null) bus.clawLine.Line.enabled = claws;
        }

        // 区間の繰り返し：毎フレーム、実時間で t を進め、窓の終わりで始まりへ戻す（Update の早い順。段は Seek の中で同じ順に呼ばれる）
        void Update()
        {
            FrameTimingManager.CaptureFrameTimings();
            fWater = fBoat = fWhite = fClaws = fSpray = 0f;
            float seekMs = 0f;
            if (looping && seekOn)
            {
                float len = Mathf.Max(1e-3f, windowEnd - windowStart);
                float t = windowStart + Mathf.Repeat(Time.realtimeSinceStartup - loopT0, len);
                var s2 = System.Diagnostics.Stopwatch.StartNew();
                clock.Seek(flow.WaveStartS + t);
                seekMs = (float)s2.Elapsed.TotalMilliseconds;
                if (collecting) lT.Add(t);
            }
            if (!collecting) return;
            lDt.Add(Time.unscaledDeltaTime);
            lSeek.Add(seekMs); lWater.Add(fWater); lBoat.Add(fBoat); lWhite.Add(fWhite); lClaws.Add(fClaws); lSpray.Add(fSpray);
            uint n = FrameTimingManager.GetLatestTimings((uint)ftBuf.Length, ftBuf);
            for (int i = 0; i < n; i++)
            {
                var ft = ftBuf[i];
                if (ft.frameStartTimestamp == 0 || !seen.Add(ft.frameStartTimestamp)) continue;
                lStart.Add((long)ft.frameStartTimestamp);
                lMain.Add(ft.cpuMainThreadFrameTime); lRender.Add(ft.cpuRenderThreadFrameTime); lGpu.Add(ft.gpuFrameTime);
            }
        }

        static Camera FindCam(string name)
        {
            foreach (var c in Resources.FindObjectsOfTypeAll<Camera>()) if (c.name == name && c.gameObject.scene.IsValid()) return c;
            return null;
        }

        Camera MakeCamera(string name, Camera src)
        {
            var go = new GameObject(name);
            var cam = go.AddComponent<Camera>();
            cam.transform.SetPositionAndRotation(src.transform.position, src.transform.rotation);
            cam.fieldOfView = src.fieldOfView;
            cam.nearClipPlane = src.nearClipPlane; cam.farClipPlane = src.farClipPlane;
            cam.cullingMask = src.cullingMask;
            cam.clearFlags = src.clearFlags; cam.backgroundColor = src.backgroundColor;
            cam.allowHDR = false; cam.allowMSAA = true;
            cam.stereoTargetEye = StereoTargetEyeMask.None;
            return cam;
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
            if (hmdCam != null) hmdCam.enabled = true;
        }

        IEnumerator Measure(Cond c, CondResult r)
        {
            Teardown();
            seekOn = c.seek; boatWaterOn = c.boat; clawsOn = c.claws; sprayOn = c.spray;
            SetLayers(c.claws, c.spray);
            if (bus.boatWater != null) { if (boatWaterPlayback == null) boatWaterPlayback = bus.boatWater.playback; bus.boatWater.playback = c.boat ? boatWaterPlayback : null; }
            foreach (var x in seaRenderers) if (x != null) x.enabled = !c.noSea;
            foreach (var x in heroRenderers) if (x != null) x.enabled = !c.noHero;
            if (!c.seek) { looping = false; clock.Seek(flow.WaveStartS + 0.5 * (windowStart + windowEnd)); }
            else if (!looping) { loopT0 = Time.realtimeSinceStartup; looping = true; }
            yield return null;
            Camera src = c.view == "hmd" ? hmdCam : FindCam(c.view);
            if (src == null) { r.noteJa = c.noteJa + "（カメラ " + c.view + " がない）"; r.name = c.name; yield break; }
            if (c.view == paintingCameraName) result.paintingCamera = src.name;
            if (c.view == seatCameraName) result.seatCamera = src.name;
            if (c.view != "hmd" || c.proxy)
            {
                // 体験の HMD Camera を切り、測るカメラを画面（または代理の 2 眼の RT）へ描く
                if (hmdCam != null) hmdCam.enabled = false;
                displayCam = MakeCamera("PL35 表示カメラ", src);
                displayCam.depth = 50;
                displayCam.aspect = (float)Screen.width / Mathf.Max(1, Screen.height);
                if (c.proxy)
                {
                    displayCam.cullingMask = 0; displayCam.clearFlags = CameraClearFlags.SolidColor; displayCam.backgroundColor = Color.black;
                    rtL = NewEyeRT("PL35 左眼"); rtR = NewEyeRT("PL35 右眼");
                    eyeL = MakeEye("PL35 左眼カメラ", src, -0.5f * Ipd, rtL, 48);
                    eyeR = MakeEye("PL35 右眼カメラ", src, 0.5f * Ipd, rtR, 49);
                    proxyActive = true;
                }
            }
            r.name = c.name; r.view = src.name; r.noteJa = c.noteJa; r.stereoProxy = c.proxy; r.seekEachFrame = c.seek; r.boatWaterOn = c.boat; r.clawsOn = c.claws; r.sprayOn = c.spray; r.seaOn = !c.noSea; r.heroOn = !c.noHero;
            r.vSyncCount = QualitySettings.vSyncCount; r.targetFrameRate = Application.targetFrameRate;
            r.eyeWidth = c.proxy ? EyeWidth : 0; r.eyeHeight = c.proxy ? EyeHeight : 0; r.eyeMsaa = c.proxy ? EyeMsaa : 0;
            float w0 = Time.realtimeSinceStartup;
            while (Time.realtimeSinceStartup - w0 < warmS) yield return null;
            Clear();
            var bw = bus.boatWater;
            int rb0 = bw != null ? bw.Rebuilds : 0; double rms0 = bw != null ? bw.RebuildMsTotal : 0;
            int g0 = GC.CollectionCount(0), g1 = GC.CollectionCount(1), g2 = GC.CollectionCount(2);
            r.monoUsedStart = UnityEngine.Profiling.Profiler.GetMonoUsedSizeLong(); r.totalAllocatedStart = UnityEngine.Profiling.Profiler.GetTotalAllocatedMemoryLong();
            collecting = true;
            r.startUtc = DateTime.UtcNow.ToString("O");
            int f0 = Time.frameCount;
            float m0 = Time.realtimeSinceStartup;
            while (Time.realtimeSinceStartup - m0 < measureS) yield return null;
            collecting = false;
            r.measureSeconds = Time.realtimeSinceStartup - m0; r.warmSeconds = warmS;
            r.unityFrames = Time.frameCount - f0;
            r.endUtc = DateTime.UtcNow.ToString("O");
            r.gcGen0Collections = GC.CollectionCount(0) - g0; r.gcGen1Collections = GC.CollectionCount(1) - g1; r.gcGen2Collections = GC.CollectionCount(2) - g2;
            r.monoUsedEnd = UnityEngine.Profiling.Profiler.GetMonoUsedSizeLong(); r.totalAllocatedEnd = UnityEngine.Profiling.Profiler.GetTotalAllocatedMemoryLong();
            r.boatWaterRebuilds = bw != null ? bw.Rebuilds - rb0 : 0; r.boatWaterRebuildMs = bw != null ? bw.RebuildMsTotal - rms0 : 0;
            using (var pr = System.Diagnostics.Process.GetCurrentProcess()) { pr.Refresh(); r.privateBytesEnd = pr.PrivateMemorySize64; r.workingSetEnd = pr.WorkingSet64; }
            r.monoHeapEnd = UnityEngine.Profiling.Profiler.GetMonoHeapSizeLong(); r.totalReservedEnd = UnityEngine.Profiling.Profiler.GetTotalReservedMemoryLong();
            r.ftStart = lStart.ToArray(); r.ftCpuMain = lMain.ToArray(); r.ftCpuRender = lRender.ToArray(); r.ftGpu = lGpu.ToArray();
            r.dt = lDt.ToArray(); r.tPlayed = lT.ToArray();
            r.msSeek = lSeek.ToArray(); r.msWater = lWater.ToArray(); r.msBoatWater = lBoat.ToArray(); r.msWhite = lWhite.ToArray(); r.msClaws = lClaws.ToArray(); r.msSpray = lSpray.ToArray();
            r.screenWidth = Screen.width; r.screenHeight = Screen.height;
            result.screenWidth = Screen.width; result.screenHeight = Screen.height;
            // 測定の後に画面を撮る（測定値には入らない）
            bool wasLooping = looping;
            looping = false;
            if (c.seek) clock.Seek(flow.WaveStartS + windowEnd - 0.05);
            yield return null;
            yield return new WaitForEndOfFrame();
            var shot = ScreenCapture.CaptureScreenshotAsTexture();
            r.screenshot = "pl35perf_" + tag + "_" + c.name + ".png";
            File.WriteAllBytes(Path.Combine(outDir, r.screenshot), shot.EncodeToPNG());
            Destroy(shot);
            if (c.proxy)
            {
                r.eyeImages = new[] { "pl35perf_" + tag + "_" + c.name + "_L.png", "pl35perf_" + tag + "_" + c.name + "_R.png" };
                SaveRT(rtL, Path.Combine(outDir, r.eyeImages[0]));
                SaveRT(rtR, Path.Combine(outDir, r.eyeImages[1]));
            }
            Teardown();
            seekOn = boatWaterOn = clawsOn = sprayOn = true;
            SetLayers(true, true);
            if (bus.boatWater != null && boatWaterPlayback != null) bus.boatWater.playback = boatWaterPlayback;
            foreach (var x in seaRenderers) if (x != null) x.enabled = true;
            foreach (var x in heroRenderers) if (x != null) x.enabled = true;
            loopT0 = Time.realtimeSinceStartup; looping = wasLooping || true;
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

        void Clear()
        {
            seen.Clear(); lStart.Clear(); lMain.Clear(); lRender.Clear(); lGpu.Clear(); lDt.Clear(); lT.Clear();
            lSeek.Clear(); lWater.Clear(); lBoat.Clear(); lWhite.Clear(); lClaws.Clear(); lSpray.Clear();
        }
    }
}
