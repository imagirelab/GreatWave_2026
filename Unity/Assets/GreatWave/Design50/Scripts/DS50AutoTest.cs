using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design45;
using GreatWave.Design47;
using GreatWave.Design49;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace GreatWave.Design50
{
    // 設計50：通しの自動の試し（引数 --ds50auto <main> のときだけ働く。場面には置くが、既定では何もしない）。
    //   開発者の操作（部品の関数を直接呼ぶ・時計を動かす）はしない。Input System に仮想のキーボードを足し、利用者と同じキーを押すだけ。
    //   入口 3 s → Enter → 導入で W・A・D の操船 → 停止の試し 3 回（導入・形成・余韻：P／Esc で止め、止めている間の時計・舟・音を測り、もう一度押して再開）
    //   → 揺れ軽減の切替 2 回（C）→ 終わりの画面 4 s → Q で出口。
    //   毎フレームの CSV（フレーム時間・FrameTimingManager の CPU／GPU 時間・状態）と、終わりに JSON の報告を --ds50out へ書く。
    //   --ds50capture：Time.captureDeltaTime = 1/30 にして毎フレームの画を JPG で書く（動画用。フレーム時間は測らない）。
    [DefaultExecutionOrder(-300)]
    public class DS50AutoTest : MonoBehaviour
    {
        public DS50Shell shell;
        public DS47Flow flow;
        public GWClock clock;
        public DS49Sound sound;
        public DS45RiderComfort rider;

        [Serializable] public class StopRec
        {
            public string label, key;
            public int injectFrame, keySeenFrame = -1, stopFrame = -1, resumeInjectFrame = -1, resumeFrame = -1, framesStopped;
            public double expAtStop = double.NaN, expAtResume = double.NaN, expMaxDriftWhileStopped, boatMaxDriftWhileStoppedM, pausedRealS;
            public int latencyFrames = -1, audioPlayingMaxWhileStopped = -1, clockRunningFramesWhileStopped, overlayShownFrames;
            public string phaseAtStop = "";
            public bool pass;
        }
        [Serializable] public class ComfortRec { public string key; public int injectFrame, changedFrame = -1, levelBefore, levelAfter; public bool pass; }
        [Serializable] public class Report
        {
            public string schema = "GreatWave.DS50.autotest/1", scenario, unity, utcStart, utcEnd, device, gpu, cpu, graphicsApi, os, commandLine, dataRoot, fontUsed, quitCause, vrStatusJa;
            public bool capture, vrRequested, vrActive, dataRootUsed, entryShown, pauseShownAll, endShown, quitRequested, pass, watchdog;
            public int frames, screenW, screenH, vSyncCount, targetFrameRate, errors, exceptions, warnings, eventsFired, endEventFrame = -1, endShownFrame = -1, quitFrame = -1, capturedFrames, entryFrames;
            public double realSeconds, experienceEndS, handoverS, waveStartS, afterglowStartS, endS, totalExperienceS, entryRealS, endScreenRealS;
            public float fixedDeltaTime;
            public StopRec[] stops;
            public ComfortRec[] comfort;
            public string[] shellLog, flowLog, soundStartLog, firstErrors, keysLog;
            public string[] stateChanges;
        }

        string outDir, scenario;
        bool capture, active, reported;
        Keyboard kb;
        readonly HashSet<Key> held = new HashSet<Key>();
        readonly List<(int frame, Key key, bool down)> keyLog = new List<(int, Key, bool)>();
        double st;              // 試しの時刻（Time.deltaTime の和。実時間でも記録の時間でも同じ筋書き）
        double entrySeenSt = -1, endSeenSt = -1, stopSinceSt;
        int stage;
        StringBuilder csv;
        StreamWriter csvW;
        readonly FrameTiming[] ft = new FrameTiming[1];
        readonly List<StopRec> stops = new List<StopRec>();
        readonly List<ComfortRec> comforts = new List<ComfortRec>();
        StopRec curStop;
        ComfortRec curComfort;
        Vector3 boatAtStop;
        readonly Report rep = new Report();
        readonly List<string> firstErrors = new List<string>();
        int errors, exceptions, warnings, captured, entryFrames;
        readonly List<(int frame, Key key)> taps = new List<(int, Key)>();
        double realStart;

        void Awake()
        {
            scenario = DS50Shell.Arg("--ds50auto", "");
            active = !string.IsNullOrEmpty(scenario);
            if (!active) { enabled = false; return; }
            capture = DS50Shell.HasArg("--ds50capture");
            outDir = DS50Shell.Arg("--ds50out", Path.Combine(DS50Shell.StartCwd, "ds50_out"));
            Directory.CreateDirectory(outDir);
            if (capture) { Directory.CreateDirectory(Path.Combine(outDir, "frames")); Time.captureDeltaTime = 1f / 30f; }
            else { QualitySettings.vSyncCount = 0; Application.targetFrameRate = -1; }
            // 窓が前にない時もキーを読む（自動の試しだけ。利用者の実行では既定のまま）
            InputSystem.settings.backgroundBehavior = InputSettings.BackgroundBehavior.IgnoreFocus;
            kb = InputSystem.AddDevice<Keyboard>("DS50AutoKeyboard");
            kb.MakeCurrent();
            Application.logMessageReceived += OnLog;
            csvW = new StreamWriter(Path.Combine(outDir, capture ? "frames_capture.csv" : "frames.csv"), false, new UTF8Encoding(false));
            csvW.WriteLine("frame,st,real,udt,dt,exp,wave,phase,shell,flowPaused,pauseReason,clockRunning,boatX,boatY,boatZ,riderLevel,audioPlaying,keys,ftCpu,ftCpuMain,ftCpuRender,ftGpu,screenW,screenH");
            rep.scenario = scenario; rep.capture = capture; rep.unity = Application.unityVersion; rep.utcStart = DateTime.UtcNow.ToString("O");
            rep.commandLine = string.Join(" ", Environment.GetCommandLineArgs());
            realStart = Time.realtimeSinceStartupAsDouble;
            Debug.Log("DS50_AUTO: scenario=" + scenario + " capture=" + capture + " out=" + outDir);
        }

        void OnLog(string msg, string stack, LogType type)
        {
            if (type == LogType.Error || type == LogType.Assert) errors++;
            else if (type == LogType.Exception) exceptions++;
            else if (type == LogType.Warning) warnings++;
            else return;
            if (type != LogType.Warning && firstErrors.Count < 20) firstErrors.Add(type + ": " + msg + " | " + (stack ?? "").Split('\n').FirstOrDefault());
        }

        void Start()
        {
            if (!active) return;
            if (shell != null) shell.QuitRequested += OnQuit;
            if (capture) StartCoroutine(CaptureLoop());
        }

        // ---------------------------------------------------------------- キー
        void Press(Key k) { if (held.Add(k)) { keyLog.Add((Time.frameCount, k, true)); Send(); } }
        void Release(Key k) { if (held.Remove(k)) { keyLog.Add((Time.frameCount, k, false)); Send(); } }
        void Tap(Key k) { Press(k); taps.Add((Time.frameCount, k)); }
        void Send()
        {
            var s = new KeyboardState(held.ToArray());
            InputSystem.QueueStateEvent(kb, s);
            kb.MakeCurrent();
        }
        void HoldIf(Key k, bool on) { if (on) Press(k); else Release(k); }

        // ---------------------------------------------------------------- 筋書き
        void Update()
        {
            if (!active || shell == null) return;
            st += Time.deltaTime;
            // 押した後 2 フレームで離す（一度の押し）
            for (int i = taps.Count - 1; i >= 0; i--) if (Time.frameCount - taps[i].frame >= 2) { Release(taps[i].key); taps.RemoveAt(i); }
            if (st > 300.0 && !reported) { rep.watchdog = true; Finish("watchdog"); Application.Quit(3); return; }

            double exp = clock.ExperienceSeconds;
            var S = shell.State;
            switch (stage)
            {
                case 0:   // 入口：3 s 見せてから Enter
                    if (S == DS50Shell.ShellState.Entry && !shell.VrInitBusy)
                    {
                        entryFrames++;
                        if (entrySeenSt < 0) entrySeenSt = st;
                        if (st - entrySeenSt >= 3.0) { Tap(Key.Enter); rep.entryShown = true; rep.entryRealS = st - entrySeenSt; stage = 1; }
                    }
                    break;
                case 1:   // 導入の操船と停止の試し 1
                    Steer(exp);
                    if (S == DS50Shell.ShellState.Running && exp >= 11.0) { Release(Key.W); Release(Key.A); Release(Key.D); BeginStop("導入（操船中）", Key.P); stage = 2; }
                    break;
                case 2: if (RunStop(2.0)) stage = 3; break;
                case 3:
                    Steer(exp);
                    if (S == DS50Shell.ShellState.Running && exp >= 16.0) { BeginComfort(Key.C); stage = 4; }
                    break;
                case 4: Steer(exp); if (CheckComfort()) stage = 5; break;
                case 5:
                    Steer(exp);
                    if (S == DS50Shell.ShellState.Running && exp >= 20.0) { BeginComfort(Key.C); stage = 6; }
                    break;
                case 6: Steer(exp); if (CheckComfort()) stage = 7; break;
                case 7:   // 形成の途中（大波の時刻 6 s）で Esc の停止
                    Steer(exp);
                    if (flow.HandedOver && S == DS50Shell.ShellState.Running && exp >= flow.WaveStartS + 6.0) { BeginStop("形成（大波の時刻 6 s）", Key.Escape); stage = 8; }
                    break;
                case 8: if (RunStop(1.5)) stage = 9; break;
                case 9:   // 余韻の視点の移動の途中で P の停止
                    if (flow.HandedOver && S == DS50Shell.ShellState.Running && exp >= flow.AfterglowStartS + 2.0) { BeginStop("余韻（視点の移動中）", Key.P); stage = 10; }
                    break;
                case 10: if (RunStop(1.0)) stage = 11; break;
                case 11:  // 終わりの画面を 4 s 見せてから Q
                    if (S == DS50Shell.ShellState.End)
                    {
                        if (endSeenSt < 0) { endSeenSt = st; rep.endShown = true; }
                        if (st - endSeenSt >= 4.0) { Tap(Key.Q); rep.endScreenRealS = st - endSeenSt; stage = 12; }
                    }
                    break;
            }
            WriteRow(exp);
        }

        void Steer(double exp)
        {
            if (flow.HandedOver || shell.State != DS50Shell.ShellState.Running) { Release(Key.W); Release(Key.A); Release(Key.D); return; }
            HoldIf(Key.W, (exp >= 0.5 && exp < 9.0) || (exp >= 10.0 && exp < 10.9) || (exp >= 13.0 && exp < 15.5));
            HoldIf(Key.D, exp >= 3.0 && exp < 5.5);
            HoldIf(Key.A, (exp >= 7.0 && exp < 8.5) || (exp >= 13.5 && exp < 14.5));
        }

        void BeginStop(string label, Key k)
        {
            curStop = new StopRec { label = label, key = k.ToString(), injectFrame = Time.frameCount, phaseAtStop = flow.CurrentPhase.ToString() };
            Tap(k);
        }

        // 止まるのを待ち、止めている間を測り、hold 秒の後に同じキーで再開。再開を見届けたら true
        bool RunStop(double holdS)
        {
            var r = curStop; var S = shell.State;
            if (r.stopFrame < 0)
            {
                if (S == DS50Shell.ShellState.Stopped)
                {
                    // 枠が停止へ入ったフレーム（キーを読んだフレーム）と、その時の体験の時刻を枠の記録から取る。
                    // 仮想のキーは押したフレームの次のフレームの Input System の更新で読まれるので、最も早くて injectFrame + 1。
                    var ch = shell.Changes.LastOrDefault(c => c.to == "Stopped");
                    r.keySeenFrame = ch.frame; r.stopFrame = ch.frame; r.expAtStop = ch.exp;
                    r.latencyFrames = ch.frame - (r.injectFrame + 1);
                    boatAtStop = flow.steer.transform.position; stopSinceSt = st;
                    r.audioPlayingMaxWhileStopped = 0;
                }
                else if (Time.frameCount - r.injectFrame > 10) { r.pass = false; r.stopFrame = -2; stops.Add(r); return true; }
                return false;
            }
            if (r.resumeInjectFrame < 0)
            {
                // 止めている間：時計・舟・音
                r.framesStopped++;
                r.expMaxDriftWhileStopped = Math.Max(r.expMaxDriftWhileStopped, Math.Abs(clock.ExperienceSeconds - r.expAtStop));
                r.boatMaxDriftWhileStoppedM = Math.Max(r.boatMaxDriftWhileStoppedM, (flow.steer.transform.position - boatAtStop).magnitude);
                r.audioPlayingMaxWhileStopped = Math.Max(r.audioPlayingMaxWhileStopped, AudioPlaying());
                if (clock.State == GWClock.RunState.Running) r.clockRunningFramesWhileStopped++;
                if (S == DS50Shell.ShellState.Stopped) r.overlayShownFrames++;
                if (st - stopSinceSt >= holdS) { r.pausedRealS = st - stopSinceSt; r.resumeInjectFrame = Time.frameCount; Tap(r.key == "Escape" ? Key.Escape : Key.P); }
                return false;
            }
            if (S == DS50Shell.ShellState.Running && r.resumeFrame < 0) { r.resumeFrame = Time.frameCount; r.expAtResume = clock.ExperienceSeconds; }
            if (r.resumeFrame >= 0 && Time.frameCount >= r.resumeFrame + 3)
            {
                r.pass = r.stopFrame > 0 && r.latencyFrames == 0 && r.expMaxDriftWhileStopped == 0.0 && r.boatMaxDriftWhileStoppedM < 1e-6
                         && r.audioPlayingMaxWhileStopped == 0 && r.clockRunningFramesWhileStopped == 0 && clock.ExperienceSeconds > r.expAtResume - 1e-12;
                stops.Add(r);
                return true;
            }
            return false;
        }

        void BeginComfort(Key k) { curComfort = new ComfortRec { key = k.ToString(), injectFrame = Time.frameCount, levelBefore = rider.Level }; Tap(k); }
        bool CheckComfort()
        {
            var c = curComfort;
            if (rider.Level != c.levelBefore) { c.changedFrame = Time.frameCount; c.levelAfter = rider.Level; c.pass = c.changedFrame - c.injectFrame <= 2; comforts.Add(c); return true; }
            if (Time.frameCount - c.injectFrame > 10) { c.pass = false; comforts.Add(c); return true; }
            return false;
        }

        int AudioPlaying()
        {
            if (sound == null) return -1;
            int n = 0;
            foreach (var s in sound.sources) if (s != null && s.isPlaying) n++;
            return n;
        }

        static string F(double x) => x.ToString("R", CultureInfo.InvariantCulture);

        void WriteRow(double exp)
        {
            FrameTimingManager.CaptureFrameTimings();
            uint got = FrameTimingManager.GetLatestTimings(1, ft);
            double cpu = got > 0 ? ft[0].cpuFrameTime : double.NaN, cpuM = got > 0 ? ft[0].cpuMainThreadFrameTime : double.NaN;
            double cpuR = got > 0 ? ft[0].cpuRenderThreadFrameTime : double.NaN, gpu = got > 0 ? ft[0].gpuFrameTime : double.NaN;
            var b = flow.steer.transform.position;
            string keys = string.Join("+", held.Select(k => k.ToString()));
            csvW.WriteLine(string.Join(",", new[] {
                Time.frameCount.ToString(), F(st), F(Time.realtimeSinceStartupAsDouble - realStart), F(Time.unscaledDeltaTime), F(Time.deltaTime), F(exp), F(clock.WaveSeconds),
                flow.CurrentPhase.ToString(), shell.State.ToString(), flow.Paused ? "1" : "0", flow.PauseReason, clock.State == GWClock.RunState.Running ? "1" : "0",
                F(b.x), F(b.y), F(b.z), rider != null ? rider.Level.ToString() : "-1", AudioPlaying().ToString(), keys, F(cpu), F(cpuM), F(cpuR), F(gpu), Screen.width.ToString(), Screen.height.ToString() }));
        }

        IEnumerator CaptureLoop()
        {
            var wait = new WaitForEndOfFrame();
            while (true)
            {
                yield return wait;
                if (reported) yield break;
                var tex = ScreenCapture.CaptureScreenshotAsTexture();
                var bytes = tex.EncodeToJPG(90);
                Destroy(tex);
                File.WriteAllBytes(Path.Combine(outDir, "frames", "f_" + Time.frameCount.ToString("D6") + ".jpg"), bytes);
                captured++;
            }
        }

        // ---------------------------------------------------------------- 終わり
        void OnQuit(string cause) { Finish(cause); }
        void OnApplicationQuit() { if (active && !reported) Finish("application_quit"); }

        void Finish(string cause)
        {
            if (reported) return;
            reported = true;
            try
            {
                rep.utcEnd = DateTime.UtcNow.ToString("O");
                rep.quitCause = cause; rep.quitRequested = shell.QuitCause != ""; rep.quitFrame = Time.frameCount;
                rep.frames = Time.frameCount; rep.realSeconds = Time.realtimeSinceStartupAsDouble - realStart;
                rep.device = SystemInfo.deviceModel; rep.gpu = SystemInfo.graphicsDeviceName; rep.cpu = SystemInfo.processorType + " x" + SystemInfo.processorCount;
                rep.graphicsApi = SystemInfo.graphicsDeviceType.ToString(); rep.os = SystemInfo.operatingSystem;
                rep.screenW = Screen.width; rep.screenH = Screen.height; rep.vSyncCount = QualitySettings.vSyncCount; rep.targetFrameRate = Application.targetFrameRate;
                rep.fixedDeltaTime = Time.fixedDeltaTime;
                rep.dataRoot = DS50Shell.DataRoot; rep.dataRootUsed = DS50Shell.DataRootUsed; rep.fontUsed = shell.FontUsed;
                rep.vrRequested = shell.VrRequested; rep.vrActive = shell.VrActive; rep.vrStatusJa = shell.VrStatusJa;
                rep.errors = errors; rep.exceptions = exceptions; rep.warnings = warnings; rep.firstErrors = firstErrors.ToArray();
                rep.endEventFrame = shell.EndEventFrame; rep.endShownFrame = shell.EndShownFrame;
                rep.experienceEndS = clock.ExperienceSeconds; rep.handoverS = flow.HandoverS; rep.waveStartS = flow.WaveStartS; rep.afterglowStartS = flow.AfterglowStartS; rep.endS = flow.EndS;
                rep.totalExperienceS = flow.EndS;
                rep.eventsFired = flow.bus != null && flow.bus.events != null ? flow.bus.events.FiredCount : -1;
                rep.stops = stops.ToArray(); rep.comfort = comforts.ToArray();
                rep.pauseShownAll = stops.Count == 3 && stops.All(s => s.overlayShownFrames == s.framesStopped && s.framesStopped > 0);
                rep.shellLog = shell.Log.ToArray(); rep.flowLog = flow.Log.ToArray(); rep.soundStartLog = sound != null ? sound.StartLog.ToArray() : new string[0];
                rep.keysLog = keyLog.Select(k => k.frame + " " + k.key + (k.down ? " down" : " up")).ToArray();
                rep.stateChanges = shell.Changes.Select(c => c.frame + " " + F(c.real) + " exp=" + F(c.exp) + " " + c.from + "→" + c.to + " " + c.cause).ToArray();
                rep.capturedFrames = captured; rep.entryFrames = entryFrames;
                rep.pass = !rep.watchdog && rep.entryShown && rep.endShown && cause.StartsWith("end_") && stops.Count == 3 && stops.All(s => s.pass)
                           && comforts.Count == 2 && comforts.All(c => c.pass) && exceptions == 0 && errors == 0 && rep.eventsFired == 9;
                File.WriteAllText(Path.Combine(outDir, capture ? "report_capture.json" : "report.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
                Debug.Log("DS50_AUTO_DONE: pass=" + rep.pass + " cause=" + cause + " frames=" + rep.frames);
            }
            catch (Exception ex) { Debug.LogException(ex); }
            finally { try { csvW?.Flush(); csvW?.Dispose(); } catch { } }
        }
    }
}
