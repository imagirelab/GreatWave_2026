using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.Design39;
using GreatWave.Design44;
using GreatWave.Design47;
using GreatWave.Design48.EditorTools;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace GreatWave.Design49.EditorTools
{
    // 設計49：体験の場面 DS49_Sound.unity を Editor の Play モードで通し、Unity の音の混ぜ（AudioListener が聞く 2 ch）を書き出す。PC の batchmode。HMD 実機ではない。
    //   ・GWClock が EarlyUpdate で進め、物理は FixedUpdate、乗客・進行役・航跡・音の位置は LateUpdate（設計47・48 と同じ）。1 フレーム = 1/90 s。
    //     ただし設計47・48 の EditorApplication.Step（一時停止のまま 1 フレームずつ）では Unity の音の系が止まって AudioSource が鳴らない（main1・main2 で確かめた）ので、
    //     部品の準備ができるまでだけ Step で進め、その後は一時停止を解き、Time.captureDeltaTime = 1/90 s でフレームの時刻を固定して進める。
    //   ・操船の入力は Input System の仮想のキーボード（設計48 の demo.main と同じ筋書き）を DS44Input.Read で読む（毎フレームの始め、DS49CaptureDriver.Update）。
    //   ・音は AudioRenderer（Unity の音の混ぜを、フレームの時刻に合わせてオフラインで作る。実時間の音の装置へは出さない）で、
    //     毎フレームそのフレームの分の標本（48 kHz・2 ch）を取り出し、float32 の生の列で書く。フレームごとの標本の数を CSV に残す（音の標本 ↔ 体験の時刻）。
    //   ・頭の向きの試験（ds49_sound.json の demo.headTurns）：導入で HMD Camera の局所の向きを右 90°・左 90° に回す（聞き手が回る）。
    //   ・記録（DS49Recorder）：毎フレームの音の状態と聞き手から見た音の位置、1/30 s ごとの HMD Camera の画。終わりに原画視点を描き、設計48 の画と比べる（Python 側）。
    // 実行：run_ds49_unity.ps1 -NoQuit -Method GreatWave.Design49.EditorTools.DS49SoundPlay.Run -Log main
    [InitializeOnLoad]
    public static class DS49SoundPlay
    {
        const string SessKey = "DS49SoundPlay";
        const string OutRoot = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/49/sound/unity";
        static int lastFrame = -1, polls = 0, fallbackFrames = 0, inputFrames = 0;
        static bool setup, captureSet;
        static DS49Recorder rec;
        static Keyboard kb;
        static DS44InputSample intended;
        static string od = OutRoot + "/main";
        static int endSeen = -1;
        static readonly List<string> notes = new List<string>();
        static Seg[] segs = new Seg[0];
        static Turn[] turns = new Turn[0];
        static Quaternion headQ0 = Quaternion.identity;

        class Seg { public double s0, s1; public Key[] keys; public string label; }
        class Turn { public double s0, s1; public float yaw; public string label; }
        [Serializable] class DemoSeg { public float s0, s1; public string keys, labelJa; }
        [Serializable] class Demo { public DemoSeg[] main; }
        [Serializable] class DemoRoot { public Demo demo; }
        [Serializable] class TurnSeg { public float s0, s1, yawDeg; public string labelJa; }
        [Serializable] class Demo49 { public TurnSeg[] headTurns; }
        [Serializable] class Demo49Root { public Demo49 demo; }

        static DS49SoundPlay()
        {
            if (SessionState.GetBool(SessKey + ".active", false)) EditorApplication.update += Poll;
        }

        static string F(double x) => x.ToString("R", CultureInfo.InvariantCulture);
        static string Esc(string s) => (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n");

        public static void BuildScene()
        {
            string o = OutRoot;
            Directory.CreateDirectory(o);
            var prot = DS49SoundBuild.Protected;
            var before = prot.ToDictionary(p => p, DS49SoundBuild.FileSha);
            string body = DS49SoundBuild.Build();
            var after = prot.ToDictionary(p => p, DS49SoundBuild.FileSha);
            var changed = prot.Where(p => before[p] != after[p]).ToList();
            var j = "{\"schema\":\"GreatWave.DS49.build/1\",\"unity\":\"" + Application.unityVersion + "\",\"utc\":\"" + DateTime.UtcNow.ToString("O") + "\"," + body +
                    ",\"protectedUnchanged\":" + (changed.Count == 0 ? "true" : "false") + ",\"changed\":[" + string.Join(",", changed.Select(p => "\"" + p + "\"")) + "]" +
                    ",\"protected\":[" + string.Join(",", prot.Select(p => "\"" + p + " " + after[p] + "\"")) + "]}";
            File.WriteAllText(Path.Combine(o, "ds49_build.json"), j, new UTF8Encoding(false));
            Debug.Log("DS49_BUILD_DONE protectedUnchanged=" + (changed.Count == 0));
        }

        public static void Run()
        {
            string o = OutRoot + "/main";
            Directory.CreateDirectory(o);
            foreach (var sub in new[] { "frames_hmd", "painting" })
            {
                var d = Path.Combine(o, sub); Directory.CreateDirectory(d);
                foreach (var f in Directory.GetFiles(d)) File.Delete(f);
            }
            foreach (var f in new[] { "status.jsonl", "ds49_mix.f32" }) if (File.Exists(Path.Combine(o, f))) File.Delete(Path.Combine(o, f));
            EditorSceneManager.OpenScene(DS49SoundBuild.Scene49, OpenSceneMode.Single);
            SessionState.SetBool(SessKey + ".active", true);
            SessionState.SetString(SessKey + ".out", Path.GetFullPath(o));
            SessionState.SetFloat(SessKey + ".start", (float)EditorApplication.timeSinceStartup);
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static Key[] ParseKeys(string s)
        {
            if (string.IsNullOrWhiteSpace(s)) return new Key[0];
            return s.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries).Select(k => (Key)Enum.Parse(typeof(Key), k)).ToArray();
        }

        static void Setup(DS47Flow flow, DS49Sound sound)
        {
            var wakeJson = AssetDatabase.LoadAssetAtPath<TextAsset>(DS48WakeBuild.WakeJson);
            var demo = JsonUtility.FromJson<DemoRoot>(wakeJson.text).demo;
            segs = demo.main.Select(d => new Seg { s0 = d.s0, s1 = d.s1, keys = ParseKeys(d.keys), label = d.labelJa }).ToArray();
            var d49 = JsonUtility.FromJson<Demo49Root>(sound.configJson.text).demo;
            turns = (d49 != null && d49.headTurns != null ? d49.headTurns : new TurnSeg[0]).Select(t => new Turn { s0 = t.s0, s1 = t.s1, yaw = t.yawDeg, label = t.labelJa }).ToArray();
            headQ0 = flow.hmdCamera.transform.localRotation;
            var go = new GameObject("DS49 記録（試験だけ・保存しない）") { hideFlags = HideFlags.DontSave };
            rec = go.AddComponent<DS49Recorder>();
            rec.flow = flow; rec.sound = sound; rec.outDir = od;
            drv = go.AddComponent<DS49CaptureDriver>();
            drv.outPath = Path.Combine(od, "ds49_mix.f32"); drv.frameDt = 1f / 90f;
            drv.clockNow = () => flow.clock.ExperienceSeconds;
            drv.onFrame = () => OnFrame(flow, sound);
            rec.capture = drv;
            rec.sprays = flow.bus.sprays.Where(s => s != null && s.name == "DS31 spray").ToList();
            rec.extra = () => intended.throttle.ToString("R", CultureInfo.InvariantCulture) + "|" + intended.turn.ToString("R", CultureInfo.InvariantCulture) + "|" + (intended.stop ? 1 : 0) + "|" + CurTurn(flow.clock.ExperienceSeconds).ToString("R", CultureInfo.InvariantCulture);
            flow.hmdCamera.enabled = false;   // 画面へは描かず、記録の部品が手で描く
            kb = InputSystem.AddDevice<Keyboard>("DS49VirtualKeyboard");
            flow.inputOverride = () =>
            {
                inputFrames++;
                var s = DS44Input.Read(kb, null, null);
                bool want = intended.throttle != 0f || intended.turn != 0f || intended.stop;
                bool got = s.throttle != 0f || s.turn != 0f || s.stop;
                if (want && !got) { fallbackFrames++; var f = intended; f.source = "fallback"; return f; }
                return s;
            };
            var paper = UnityEngine.Object.FindFirstObjectByType<DS39PaperLayers>();
            if (paper != null) { paper.Set(false, false, false); notes.Add("paper=off（設計47・48 の記録と同じ）"); }
            notes.Add("fixedDeltaTime=" + F(Time.fixedDeltaTime) + " stepping=EditorApplication.Step");
            notes.Add("headQ0=" + headQ0.eulerAngles.ToString("F3"));
            drv.Begin();
            sound.ResetClockMap();
            notes.Add(drv.NoteJa);
            setup = true;
        }

        static float CurTurn(double exp) { var t = turns.FirstOrDefault(x => exp >= x.s0 && exp < x.s1); return t != null ? t.yaw : 0f; }

        static void Poll()
        {
            double now = EditorApplication.timeSinceStartup;
            double start = SessionState.GetFloat(SessKey + ".start", (float)now);
            od = SessionState.GetString(SessKey + ".out", od);
            if (now - start > 1500) { Finish("打ち切り（1500 s）", 2); return; }
            if (!EditorApplication.isPlaying) return;
            if (doneCode >= 0) { Finish(doneWhy, doneCode); return; }
            if (setup)
            {
                // 以後はフレームの中（DS49CaptureDriver.Update → OnFrame）で進む。一時停止はしない。
                // Editor は窓の描画がないと Play のフレームを進めない（batchmode・窓が前にない時。main3・main5 で確かめた）ので、毎回プレイヤーのループを 1 回頼む
                if (EditorApplication.isPaused) EditorApplication.isPaused = false;
                EditorApplication.QueuePlayerLoopUpdate();
                ticks++;
                if (ticks % 2000 == 1) Debug.Log("DS49_TICK polls=" + ticks + " frame=" + Time.frameCount + " samples=" + (drv != null ? drv.Samples : -1));
                return;
            }
            if (!captureSet) { EditorApplication.isPaused = true; captureSet = true; }
            if (!Application.runInBackground) Application.runInBackground = true;
            polls++;
            if (Time.frameCount == lastFrame)
            {
                if (polls == 1 || polls % 20 == 0) { if (!EditorApplication.isPaused) EditorApplication.isPaused = true; EditorApplication.Step(); }
                return;
            }
            lastFrame = Time.frameCount; polls = 0;
            var flow = UnityEngine.Object.FindFirstObjectByType<DS47Flow>();
            var sound = UnityEngine.Object.FindFirstObjectByType<DS49Sound>();
            if (flow == null || !flow.Ready || sound == null || !sound.Ready) return;
            Setup(flow, sound);
            notes.Add("setup frame=" + Time.frameCount + " exp=" + F(flow.clock.ExperienceSeconds) + "（ここまで一時停止で 1 フレームずつ進め、以後は一時停止を解き Time.captureDeltaTime = 1/90 s で進める）");
            EditorApplication.isPaused = false;
        }

        static int doneCode = -1;
        static long ticks;
        static string doneWhy = "";
        static DS49CaptureDriver drv;

        static void OnFrame(DS47Flow flow, DS49Sound sound)
        {
            if (doneCode >= 0) return;
            var clk = flow.clock;
            double exp = clk.ExperienceSeconds;
            if (Time.frameCount % 90 == 0)
                File.AppendAllText(Path.Combine(od, "status.jsonl"), "{\"frame\":" + Time.frameCount + ",\"exp\":" + F(exp) + ",\"phase\":\"" + flow.CurrentPhase + "\",\"audioSamples\":" + drv.Samples + ",\"zeroFrames\":" + drv.ZeroFrames + ",\"errors\":" + (flow.Errors + sound.Errors) + ",\"lastError\":\"" + Esc(flow.LastError + " " + sound.LastError) + "\"}\n");
            if (!flow.HandedOver && exp > flow.Cfg.timing.introMaxS + 5.0) { WriteReport(flow, sound, "\"abortJa\":\"引き継ぎが起きなかった\""); doneWhy = "引き継ぎなし"; doneCode = 3; EditorApplication.isPaused = true; return; }

            var seg = segs.FirstOrDefault(s => exp >= s.s0 && exp < s.s1);
            var keys = seg != null ? seg.keys : new Key[0];
            InputState.Change(kb, new KeyboardState(keys));
            intended = new DS44InputSample
            {
                throttle = Mathf.Clamp((keys.Contains(Key.W) ? 1f : 0f) - (keys.Contains(Key.S) ? 1f : 0f), -1f, 1f),
                turn = Mathf.Clamp((keys.Contains(Key.D) ? 1f : 0f) - (keys.Contains(Key.A) ? 1f : 0f), -1f, 1f),
                stop = keys.Contains(Key.Space), source = "intended"
            };
            // 頭の向きの試験（このフレームの LateUpdate の聞き手の姿勢に入る。記録は各フレームの LateUpdate の聞き手の姿勢で数える）
            flow.hmdCamera.transform.localRotation = headQ0 * Quaternion.Euler(0f, CurTurn(exp), 0f);

            if (flow.HandedOver && clk.Ended && flow.CurrentPhase == DS47Flow.Phase.End)
            {
                if (endSeen < 0) { endSeen = Time.frameCount; return; }
                if (Time.frameCount - endSeen < 9) return;
                var img = Path.Combine(od, "painting");
                var t = rec.Render(flow.paintingCamera, 1920, 1080, 8, true);
                File.WriteAllBytes(Path.Combine(img, "painting_end.png"), t.EncodeToPNG()); UnityEngine.Object.Destroy(t);
                WriteReport(flow, sound, "\"final\":{\"images\":[\"painting/painting_end.png\"]}");
                doneWhy = "台本の終わり"; doneCode = 0;
                EditorApplication.isPaused = true;
            }
        }

        static void WriteReport(DS47Flow flow, DS49Sound sound, string final)
        {
            drv.End();
            File.WriteAllText(Path.Combine(od, "ds49_frames.csv"), rec.csv.ToString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(od, "ds49_audio_frames.csv"), drv.csv.ToString(), new UTF8Encoding(false));
            var ev = flow.bus.events;
            var j = new StringBuilder("{\"schema\":\"GreatWave.DS49.play/1\",\"unity\":\"").Append(Application.unityVersion)
                .Append("\",\"device\":\"").Append(Esc(SystemInfo.graphicsDeviceName)).Append("\",\"utc\":\"").Append(DateTime.UtcNow.ToString("O")).Append('"');
            j.Append(",\"scene\":\"").Append(DS49SoundBuild.Scene49).Append("\",\"sceneSha256\":\"").Append(DS49SoundBuild.FileSha(DS49SoundBuild.Scene49)).Append('"');
            j.Append(",\"fixedDeltaTime\":").Append(F(Time.fixedDeltaTime)).Append(",\"captureDeltaTime\":").Append(F(Time.captureDeltaTime)).Append(",\"frames\":").Append(rec.Frames).Append(",\"captured\":").Append(rec.Captured).Append(",\"renderMsTotal\":").Append(F(rec.RenderMsTotal));
            j.Append(",\"audio\":{\"rendererOk\":").Append(drv.Ok ? "true" : "false").Append(",\"sampleRate\":").Append(AudioSettings.outputSampleRate).Append(",\"channels\":").Append(drv.Channels).Append(",\"samples\":").Append(drv.Samples).Append(",\"zeroFrames\":").Append(drv.ZeroFrames).Append(",\"startExp\":").Append(F(drv.StartExp)).Append(",\"mapOffsetEnd\":").Append(F(sound.MapOffset)).Append(",\"mapResets\":").Append(sound.MapResets).Append(",\"file\":\"ds49_mix.f32\"}");
            j.Append(",\"handover\":{\"s\":").Append(F(flow.HandoverS)).Append(",\"waveStart\":").Append(F(flow.WaveStartS)).Append(",\"afterglowStart\":").Append(F(flow.AfterglowStartS))
             .Append(",\"end\":").Append(F(flow.EndS)).Append(",\"reason\":\"").Append(flow.HandoverReason).Append("\"}");
            j.Append(",\"clock\":{\"experienceEnd\":").Append(F(flow.clock.ExperienceSeconds)).Append(",\"ended\":").Append(flow.clock.Ended ? "true" : "false").Append('}');
            j.Append(",\"events\":[").Append(string.Join(",", ev.log.Select(e => "{\"id\":\"" + e.id + "\",\"eventT\":" + F(e.eventT) + ",\"clockT\":" + F(e.clockT) + ",\"step\":" + e.stepIndex + ",\"fired\":" + (e.fired ? "true" : "false") + "}"))).Append(']');
            j.Append(",\"soundStarts\":[").Append(string.Join(",", sound.StartLog)).Append(']');
            j.Append(",\"tracks\":[").Append(string.Join(",", sound.tracks.Select(s => "{\"key\":\"" + s.t.key + "\",\"clip\":\"" + (s.src.clip != null ? s.src.clip.name : "") + "\",\"starts\":" + s.starts + ",\"resyncs\":" + s.resyncs + ",\"stops\":" + s.stops + ",\"lostVoice\":" + s.lostVoice + ",\"anchorEvent\":\"" + s.t.anchorEvent + "\",\"anchorT\":" + F(s.anchorT) + ",\"spatialBlend\":" + F(s.src.spatialBlend) + ",\"doppler\":" + F(s.src.dopplerLevel) + ",\"spread\":" + F(s.src.spread) + ",\"minDistance\":" + F(s.src.minDistance) + "}"))).Append(']');
            j.Append(",\"windFromDir\":[").Append(F(sound.WindFromDir.x)).Append(',').Append(F(sound.WindFromDir.y)).Append(',').Append(F(sound.WindFromDir.z)).Append(']');
            j.Append(",\"soundErrors\":").Append(sound.Errors).Append(",\"soundLastError\":\"").Append(Esc(sound.LastError)).Append('"');
            j.Append(",\"flowErrors\":").Append(flow.Errors).Append(",\"flowLastError\":\"").Append(Esc(flow.LastError)).Append('"');
            j.Append(",\"input\":{\"frames\":").Append(inputFrames).Append(",\"fallbackFrames\":").Append(fallbackFrames).Append('}');
            j.Append(",\"boatWater\":{\"fallbacks\":").Append(flow.bus.boatWater.FallbackCount).Append(",\"queries\":").Append(flow.bus.boatWater.QueryCount).Append('}');
            j.Append(",\"soundLog\":[").Append(string.Join(",", sound.Log.Select(s => "\"" + Esc(s) + "\""))).Append(']');
            j.Append(",\"flowLog\":[").Append(string.Join(",", flow.Log.Select(s => "\"" + Esc(s) + "\""))).Append(']');
            j.Append(",\"notes\":[").Append(string.Join(",", notes.Select(s => "\"" + Esc(s) + "\""))).Append(']');
            j.Append(',').Append(final).Append('}');
            File.WriteAllText(Path.Combine(od, "ds49_play.json"), j.ToString(), new UTF8Encoding(false));
        }

        static void Finish(string why, int code)
        {
            EditorApplication.update -= Poll;
            SessionState.EraseBool(SessKey + ".active");
            try { if (kb != null) InputSystem.RemoveDevice(kb); } catch (Exception) { }
            try { drv?.End(); } catch (Exception) { }
            Debug.Log("DS49_PLAY_DONE " + why + " frames=" + (rec != null ? rec.Frames : -1) + " audioSamples=" + (drv != null ? drv.Samples : -1));
            EditorApplication.Exit(code);
        }
    }
}
