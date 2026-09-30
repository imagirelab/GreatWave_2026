using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.Design30;
using GreatWave.Design38;
using GreatWave.Design39;
using GreatWave.Design44;
using GreatWave.Design47;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace GreatWave.Design48.EditorTools
{
    // 設計48：体験の場面 DS48_Wake.unity を Editor の Play モードで通す（設計47 の DS47FlowPlay と同じ道：止めた状態で EditorApplication.Step で
    // 1 フレーム = 1/90 s ずつ進め、GWClock が EarlyUpdate で進め、物理は FixedUpdate、乗客・進行役・泡と航跡は LateUpdate）。PC の batchmode。HMD 実機ではない。
    //   ・操船の入力は Input System の仮想のキーボードの状態（InputState.Change）を DS44Input.Read で読む（筋書き ds48_wake.json の demo.main）。
    //   ・記録（DS48Recorder）：毎フレームの泡と航跡の量、1/30 s ごとの追いかけのカメラと座席の視点のコマ、10 コマ/s の主役波との重なりの検査。
    //   ・終わりに原画視点（DS27 painting）を 1920×1080 で描き、設計47 の同じ画（painting_end.png）と比べる（Python 側）。
    // 実行：run_ds48_unity.ps1 -NoQuit -Method GreatWave.Design48.EditorTools.DS48WakePlay.Run -Log main
    [InitializeOnLoad]
    public static class DS48WakePlay
    {
        const string SessKey = "DS48WakePlay";
        const string OutRoot = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/48/wake/unity";
        static int lastFrame = -1, polls = 0, fallbackFrames = 0, inputFrames = 0;
        static bool setup, finalDone, captureSet;
        static DS48Recorder rec;
        static Keyboard kb;
        static DS44InputSample intended;
        static string od = OutRoot + "/main";
        static int endSeen = -1;
        static readonly List<string> notes = new List<string>();
        static Seg[] segs = new Seg[0];
        class Look { public string name; public double at; public bool relHandover, done; }
        static readonly Look[] looks = { new Look { name = "turn_right_s10.5", at = 10.5 }, new Look { name = "turn_left_s19.5", at = 19.5 }, new Look { name = "approach_h+4", at = 4.0, relHandover = true } };
        static readonly List<string> lookLog = new List<string>();

        class Seg { public double s0, s1; public Key[] keys; public string label; }
        [Serializable] class DemoSeg { public float s0, s1; public string keys, labelJa; }
        [Serializable] class Demo { public DemoSeg[] main; }
        [Serializable] class DemoRoot { public Demo demo; }

        static DS48WakePlay()
        {
            if (SessionState.GetBool(SessKey + ".active", false)) EditorApplication.update += Poll;
        }

        static string Arg(string name, string def) { var a = Environment.GetCommandLineArgs(); for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1]; return def; }
        static string F(double x) => x.ToString("R", CultureInfo.InvariantCulture);
        static string Esc(string s) => (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n");

        public static void BuildScene()
        {
            string o = OutRoot;
            Directory.CreateDirectory(o);
            var prot = DS48WakeBuild.Protected;
            var before = prot.ToDictionary(p => p, DS48WakeBuild.FileSha);
            string body = DS48WakeBuild.Build();
            var after = prot.ToDictionary(p => p, DS48WakeBuild.FileSha);
            var changed = prot.Where(p => before[p] != after[p]).ToList();
            var j = "{\"schema\":\"GreatWave.DS48.build/1\",\"unity\":\"" + Application.unityVersion + "\",\"utc\":\"" + DateTime.UtcNow.ToString("O") + "\"," + body +
                    ",\"protectedUnchanged\":" + (changed.Count == 0 ? "true" : "false") + ",\"changed\":[" + string.Join(",", changed.Select(p => "\"" + p + "\"")) + "]" +
                    ",\"protected\":[" + string.Join(",", prot.Select(p => "\"" + p + " " + after[p] + "\"")) + "]}";
            File.WriteAllText(Path.Combine(o, "ds48_build.json"), j, new UTF8Encoding(false));
            Debug.Log("DS48_BUILD_DONE protectedUnchanged=" + (changed.Count == 0));
        }

        public static void Run()
        {
            string o = OutRoot + "/main";
            Directory.CreateDirectory(o);
            foreach (var sub in new[] { "frames_chase", "frames_hmd", "overlap", "painting", "look" })
            {
                var d = Path.Combine(o, sub); Directory.CreateDirectory(d);
                foreach (var f in Directory.GetFiles(d)) File.Delete(f);
            }
            if (File.Exists(Path.Combine(o, "status.jsonl"))) File.Delete(Path.Combine(o, "status.jsonl"));
            EditorSceneManager.OpenScene(DS48WakeBuild.Scene48, OpenSceneMode.Single);
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

        static List<Renderer> HeroRenderers(DS47Flow flow)
        {
            var list = new List<Renderer>();
            var bus = flow.bus;
            var hero = bus.playback.sheets.FirstOrDefault(s => s != null && s.sheetName == "hero");
            if (hero != null)
            {
                list.AddRange(hero.GetComponentsInChildren<Renderer>(true));
                if (hero.outline != null) list.Add(hero.outline);
                foreach (var so in UnityEngine.Object.FindObjectsByType<DS38SheetOutline>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                    if (so.sheet == hero) list.AddRange(so.GetComponentsInChildren<Renderer>(true));
            }
            if (bus.claws != null) list.AddRange(bus.claws.GetComponentsInChildren<Renderer>(true));
            if (bus.clawLine != null) list.AddRange(bus.clawLine.GetComponentsInChildren<Renderer>(true));
            return list.Where(r => r != null).Distinct().ToList();
        }

        static void Setup(DS47Flow flow, DS48Wake wake)
        {
            var demo = JsonUtility.FromJson<DemoRoot>(wake.configJson.text).demo;
            segs = demo.main.Select(d => new Seg { s0 = d.s0, s1 = d.s1, keys = ParseKeys(d.keys), label = d.labelJa }).ToArray();
            var go = new GameObject("DS48 記録（試験だけ・保存しない）") { hideFlags = HideFlags.DontSave };
            var camGo = new GameObject("DS48 追いかけのカメラ（試験だけ・保存しない）") { hideFlags = HideFlags.DontSave };
            var chase = camGo.AddComponent<Camera>();
            chase.enabled = false;
            chase.fieldOfView = 50f; chase.nearClipPlane = 0.3f; chase.farClipPlane = 2000f;
            chase.clearFlags = flow.hmdCamera.clearFlags; chase.backgroundColor = flow.hmdCamera.backgroundColor;
            chase.allowHDR = flow.hmdCamera.allowHDR; chase.allowMSAA = flow.hmdCamera.allowMSAA; chase.cullingMask = flow.hmdCamera.cullingMask;
            rec = go.AddComponent<DS48Recorder>();
            rec.flow = flow; rec.wake = wake; rec.chase = chase; rec.outDir = od;
            rec.sprays = flow.bus.sprays.Where(s => s != null && s.name == "DS31 spray").ToList();
            rec.heroRenderers = HeroRenderers(flow);
            notes.Add("heroRenderers=" + rec.heroRenderers.Count + " [" + string.Join("|", rec.heroRenderers.Select(r => r.name)) + "]");
            rec.extra = () => intended.throttle.ToString("R", CultureInfo.InvariantCulture) + "|" + intended.turn.ToString("R", CultureInfo.InvariantCulture) + "|" + (intended.stop ? 1 : 0);
            flow.hmdCamera.enabled = false;   // 画面へは描かず、記録の部品が手で描く
            kb = InputSystem.AddDevice<Keyboard>("DS48VirtualKeyboard");
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
            if (paper != null) { paper.Set(false, false, false); notes.Add("paper=off（設計47 の記録と同じ）"); }
            notes.Add("fixedDeltaTime=" + F(Time.fixedDeltaTime) + " stepping=EditorApplication.Step");
            notes.Add("hull bowZ=" + F(wake.BowZ) + " sternZ=" + F(wake.SternZ) + " halfBeam=" + F(wake.HalfBeam));
            setup = true;
        }

        static void Poll()
        {
            double now = EditorApplication.timeSinceStartup;
            double start = SessionState.GetFloat(SessKey + ".start", (float)now);
            od = SessionState.GetString(SessKey + ".out", od);
            if (now - start > 1500) { Finish("打ち切り（1500 s）", 2); return; }
            if (!EditorApplication.isPlaying) return;
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
            var wake = UnityEngine.Object.FindFirstObjectByType<DS48Wake>();
            if (flow == null || !flow.Ready || wake == null || !wake.Ready) return;
            if (!setup) Setup(flow, wake);
            var clk = flow.clock;
            double exp = clk.ExperienceSeconds;
            if (Time.frameCount % 90 == 0)
                File.AppendAllText(Path.Combine(od, "status.jsonl"), "{\"frame\":" + Time.frameCount + ",\"exp\":" + F(exp) + ",\"phase\":\"" + flow.CurrentPhase + "\",\"samples\":" + wake.Samples + ",\"visible\":" + wake.VisibleVerts + ",\"errors\":" + (flow.Errors + wake.Errors) + ",\"lastError\":\"" + Esc(flow.LastError + " " + wake.LastError) + "\"}\n");
            if (!flow.HandedOver && exp > flow.Cfg.timing.introMaxS + 5.0) { WriteReport(flow, wake, "\"abortJa\":\"引き継ぎが起きなかった\""); Finish("引き継ぎなし", 3); return; }

            var seg = segs.FirstOrDefault(s => exp >= s.s0 && exp < s.s1);
            var keys = seg != null ? seg.keys : new Key[0];
            InputState.Change(kb, new KeyboardState(keys));
            intended = new DS44InputSample
            {
                throttle = Mathf.Clamp((keys.Contains(Key.W) ? 1f : 0f) - (keys.Contains(Key.S) ? 1f : 0f), -1f, 1f),
                turn = Mathf.Clamp((keys.Contains(Key.D) ? 1f : 0f) - (keys.Contains(Key.A) ? 1f : 0f), -1f, 1f),
                stop = keys.Contains(Key.Space), source = "intended"
            };

            // 座席から見回した画（試験だけ）：旋回の間と接近の間に、頭の向き（HMD Camera の局所の向き）を左舷・右舷・後ろへ一時だけ向けて描き、戻す
            foreach (var L in looks)
            {
                if (L.done || exp < (L.relHandover ? (flow.HandedOver ? flow.HandoverS + L.at : double.PositiveInfinity) : L.at)) continue;
                L.done = true;
                var ct = flow.hmdCamera.transform; var q0 = ct.localRotation;
                foreach (var yo in new[] { -110f, 110f, 180f })
                {
                    ct.localRotation = Quaternion.Euler(22f, yo, 0f);
                    var t = rec.Render(flow.hmdCamera, 960, 540, 8, true);
                    string nm = L.name + "_yaw" + ((int)yo).ToString("+0;-0") + ".png";
                    File.WriteAllBytes(Path.Combine(od, "look", nm), t.EncodeToPNG()); UnityEngine.Object.Destroy(t);
                    lookLog.Add("{\"name\":\"" + nm + "\",\"exp\":" + F(exp) + ",\"yawOffsetDeg\":" + F(yo) + ",\"pitchDownDeg\":22,\"bowPortW\":" + F(wake.BowPortW) + ",\"bowStbdW\":" + F(wake.BowStbdW) + ",\"yawRate\":" + F(wake.YawRateDegS) + "}");
                }
                ct.localRotation = q0;
            }

            if (!finalDone && flow.HandedOver && clk.Ended && flow.CurrentPhase == DS47Flow.Phase.End)
            {
                if (endSeen < 0) { endSeen = Time.frameCount; return; }
                if (Time.frameCount - endSeen < 9) return;
                finalDone = true;
                // 原画視点の終わりの画（設計47 の painting_end.png と同じ描き方：1920×1080、MSAA 8、飛沫 v0 を足す）
                var img = Path.Combine(od, "painting");
                var t = rec.Render(flow.paintingCamera, 1920, 1080, 8, true);
                File.WriteAllBytes(Path.Combine(img, "painting_end.png"), t.EncodeToPNG()); UnityEngine.Object.Destroy(t);
                var t2 = rec.Render(flow.hmdCamera, 1920, 1080, 8, true);
                File.WriteAllBytes(Path.Combine(img, "view_end.png"), t2.EncodeToPNG()); UnityEngine.Object.Destroy(t2);
                WriteReport(flow, wake, "\"final\":{\"images\":[\"painting/painting_end.png\",\"painting/view_end.png\"],\"wakeRendererOn\":" + (wake.meshRenderer.enabled ? "true" : "false") + ",\"wakeVertexCount\":" + wake.meshFilter.sharedMesh.vertexCount + "}");
                Finish("台本の終わり", 0);
            }
        }

        static void WriteReport(DS47Flow flow, DS48Wake wake, string final)
        {
            File.WriteAllText(Path.Combine(od, "ds48_frames.csv"), rec.csv.ToString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(od, "ds48_masks.csv"), rec.maskCsv.ToString(), new UTF8Encoding(false));
            var ev = flow.bus.events;
            var j = new StringBuilder("{\"schema\":\"GreatWave.DS48.play/1\",\"unity\":\"").Append(Application.unityVersion)
                .Append("\",\"device\":\"").Append(Esc(SystemInfo.graphicsDeviceName)).Append("\",\"utc\":\"").Append(DateTime.UtcNow.ToString("O")).Append('"');
            j.Append(",\"scene\":\"").Append(DS48WakeBuild.Scene48).Append("\",\"sceneSha256\":\"").Append(DS48WakeBuild.FileSha(DS48WakeBuild.Scene48)).Append('"');
            j.Append(",\"fixedDeltaTime\":").Append(F(Time.fixedDeltaTime)).Append(",\"frames\":").Append(rec.Frames).Append(",\"captured\":").Append(rec.Captured).Append(",\"renderMsTotal\":").Append(F(rec.RenderMsTotal));
            j.Append(",\"handover\":{\"s\":").Append(F(flow.HandoverS)).Append(",\"waveStart\":").Append(F(flow.WaveStartS)).Append(",\"afterglowStart\":").Append(F(flow.AfterglowStartS))
             .Append(",\"end\":").Append(F(flow.EndS)).Append(",\"reason\":\"").Append(flow.HandoverReason).Append("\"}");
            j.Append(",\"clock\":{\"experienceEnd\":").Append(F(flow.clock.ExperienceSeconds)).Append(",\"ended\":").Append(flow.clock.Ended ? "true" : "false").Append('}');
            j.Append(",\"events\":[").Append(string.Join(",", ev.log.Select(e => "{\"id\":\"" + e.id + "\",\"eventT\":" + F(e.eventT) + ",\"clockT\":" + F(e.clockT) + ",\"fired\":" + (e.fired ? "true" : "false") + "}"))).Append(']');
            j.Append(",\"wake\":{\"rebuilds\":").Append(wake.Rebuilds).Append(",\"teleports\":").Append(wake.Teleports).Append(",\"guardHiddenTotal\":").Append(wake.GuardHiddenTotal).Append(",\"errors\":").Append(wake.Errors)
             .Append(",\"lastError\":\"").Append(Esc(wake.LastError)).Append("\",\"bowZ\":").Append(F(wake.BowZ)).Append(",\"sternZ\":").Append(F(wake.SternZ)).Append(",\"halfBeam\":").Append(F(wake.HalfBeam)).Append(",\"ticks\":").Append(wake.Ticks).Append(",\"tickMsTotal\":").Append(F(wake.TickMsTotal)).Append(",\"tickMsMax\":").Append(F(wake.TickMsMax)).Append('}');
            j.Append(",\"flowErrors\":").Append(flow.Errors).Append(",\"flowLastError\":\"").Append(Esc(flow.LastError)).Append('"');
            j.Append(",\"input\":{\"frames\":").Append(inputFrames).Append(",\"fallbackFrames\":").Append(fallbackFrames).Append('}');
            j.Append(",\"boatWater\":{\"fallbacks\":").Append(flow.bus.boatWater.FallbackCount).Append(",\"queries\":").Append(flow.bus.boatWater.QueryCount).Append('}');
            j.Append(",\"flowLog\":[").Append(string.Join(",", flow.Log.Select(s => "\"" + Esc(s) + "\""))).Append(']');
            j.Append(",\"notes\":[").Append(string.Join(",", notes.Select(s => "\"" + Esc(s) + "\""))).Append(']');
            j.Append(",\"looks\":[").Append(string.Join(",", lookLog)).Append(']');
            j.Append(',').Append(final).Append('}');
            File.WriteAllText(Path.Combine(od, "ds48_play.json"), j.ToString(), new UTF8Encoding(false));
        }

        static void Finish(string why, int code)
        {
            EditorApplication.update -= Poll;
            SessionState.EraseBool(SessKey + ".active");
            try { if (kb != null) InputSystem.RemoveDevice(kb); } catch (Exception) { }
            Debug.Log("DS48_PLAY_DONE " + why + " frames=" + (rec != null ? rec.Frames : -1));
            EditorApplication.Exit(code);
        }
    }
}
