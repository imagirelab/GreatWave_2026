using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design31;
using GreatWave.Design39;
using GreatWave.Design44;
using GreatWave.Design46;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace GreatWave.Design47.EditorTools
{
    // 設計47：体験の場面 DS47_Flow.unity を Editor の Play モードで通す（実際の実行の道：GWClock が EarlyUpdate で進め、段を順に呼び、
    // 物理（浮力・操船）は FixedUpdate、乗客は LateUpdate、進行役は FixedUpdate・LateUpdate）。PC の batchmode。HMD 実機ではない。
    //   ・止めた状態で EditorApplication.Step で 1 フレームずつ進める（1 フレーム = 固定の時間刻み 1/90 s、物理 1 段。VR の 90 Hz のコマの代わり）。
    //     動画のコマは記録の部品がフレームの時間の和で 1/30 s ごとに描く（3 フレームに 1 枚）。
    //   ・操船の入力は Input System の仮想のキーボードの状態（InputState.Change）を DS44Input.Read で読む（筋書き ds47_flow.json の demo）。
    //   ・main：通しの動画のコマ（HMD Camera の PC の視点、1920×1080 JPG）と毎フレームの記録。終わりに原画視点の確かめ（114）。
    //   ・variant：途中で止まった船（停止の後は入力なし）と、観賞の位置から外れた時（頭を 0.8 m・0.9 m ずらす）の一時停止と再開。静止画と記録だけ。
    // 実行：run_ds47_unity.ps1 -NoQuit -Method GreatWave.Design47.EditorTools.DS47FlowPlay.Run -Log main -Extra "-ds47Script main"
    // batchmode ではプレイヤーのループが自分で回らないので、EditorApplication.update ごとに QueuePlayerLoopUpdate で 1 フレームずつ回す（設計46 と同じ）。
    [InitializeOnLoad]
    public static class DS47FlowPlay
    {
        const string SessKey = "DS47FlowPlay";
        const string OutRoot = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/47/flow/unity";
        static int lastFrame = -1, polls = 0, fallbackFrames = 0, inputFrames = 0;
        static double rtime;
        static bool setup, finalDone, captureSet;
        static DS47Recorder rec;
        static Keyboard kb;
        static DS44InputSample intended;
        static string script = "main", od = OutRoot;
        static readonly List<string> notes = new List<string>();
        static readonly Dictionary<string, int> marks = new Dictionary<string, int>();
        static Seg[] segs = new Seg[0];
        static LeaveAct[] leaves = new LeaveAct[0];

        class Seg { public double s0, s1; public Key[] keys; public string label; }
        class LeaveAct { public string name; public double at; public bool relWave; public double dur, rStart; public Vector3 off; public int started = -1, paused = -1, restored = -1, resumed = -1; public double expStart, expPaused, expResumed; }

        [Serializable] class DemoSeg { public float s0, s1; public string keys, labelJa; }
        [Serializable] class DemoLeave { public float s0, s1, waveOffsetS, durS; public float[] offsetM; }
        [Serializable] class Demo { public DemoSeg[] main, variant; public DemoLeave variantLeave, variantLeaveHold; }
        [Serializable] class DemoRoot { public Demo demo; }

        static DS47FlowPlay()
        {
            if (SessionState.GetBool(SessKey + ".active", false)) EditorApplication.update += Poll;
        }

        static string Arg(string name, string def) { var a = Environment.GetCommandLineArgs(); for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1]; return def; }
        static string F(double x) => x.ToString("R", CultureInfo.InvariantCulture);
        static string Esc(string s) => (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n");

        /// <summary>場面を作る（-quit で呼ぶ）。</summary>
        public static void BuildScene()
        {
            string o = Arg("-ds47Out", OutRoot);
            Directory.CreateDirectory(o);
            var before = DS47FlowBuild.Protected.ToDictionary(p => p, DS47FlowBuild.FileSha);
            string body = DS47FlowBuild.Build();
            var after = DS47FlowBuild.Protected.ToDictionary(p => p, DS47FlowBuild.FileSha);
            var changed = DS47FlowBuild.Protected.Where(p => before[p] != after[p]).ToList();
            var j = "{\"schema\":\"GreatWave.DS47.build/1\",\"unity\":\"" + Application.unityVersion + "\",\"utc\":\"" + DateTime.UtcNow.ToString("O") + "\"," + body +
                    ",\"protectedUnchanged\":" + (changed.Count == 0 ? "true" : "false") + ",\"changed\":[" + string.Join(",", changed.Select(p => "\"" + p + "\"")) + "]" +
                    ",\"protected\":[" + string.Join(",", DS47FlowBuild.Protected.Select(p => "\"" + p + " " + after[p] + "\"")) + "]}";
            File.WriteAllText(Path.Combine(o, "ds47_build.json"), j, new UTF8Encoding(false));
            Debug.Log("DS47_BUILD_DONE protectedUnchanged=" + (changed.Count == 0));
        }

        /// <summary>確かめ用：Editor で場面を開き、段を準備して、出発点の水の高さを読む（保存しない）。</summary>
        public static void DebugStartHeight()
        {
            EditorSceneManager.OpenScene(DS47FlowBuild.Scene47, OpenSceneMode.Single);
            var flow = UnityEngine.Object.FindFirstObjectByType<DS47Flow>();
            var bus = flow.bus;
            bus.Prepare();
            flow.clock.Initialise(false);
            var cfg = DS47FlowConfig.Parse(flow.flowJson.text);
            flow.steer.Init();
            var xz = flow.steer.Fr.ToWorld(cfg.start.u, cfg.start.v);
            var sb = new StringBuilder("DS47_DEBUG tau=" + F(bus.playback.Tau) + " region=" + bus.boatWater.region + " readers=" + bus.boatWater.readers.Count + " xz=" + xz);
            var hits = new List<float>();
            int k = bus.boatWater.Hits(new Vector3(xz.x, 0f, xz.y), hits);
            sb.Append(" hits=").Append(k).Append(" [").Append(string.Join(",", hits.Select(h => F(h)))).Append("] fallbacks=").Append(bus.boatWater.FallbackCount);
            foreach (var r in bus.boatWater.readers) { var l = new List<float>(); bool q = r.Query(xz.x, xz.y, l); sb.Append(" | q=").Append(q).Append(" ").Append(string.Join(",", l.Select(h => F(h)))); }
            for (int i = 0; i < flow.buoyancy.Cfg.pointCount; i++)
            {
                var wp = flow.steer.transform.TransformPoint(flow.buoyancy.PointLocal(i));
                sb.Append(" | p").Append(i).Append(" y=").Append(F(wp.y)).Append(" h=").Append(F(bus.boatWater.HeightAt(wp)));
            }
            Debug.Log(sb.ToString());
            File.WriteAllText(OutRoot + "/debug_start_height.txt", sb.ToString());
        }

        public static void Run()
        {
            script = Arg("-ds47Script", "main");
            string o = Arg("-ds47Out", OutRoot + "/" + script);
            Directory.CreateDirectory(o);
            Directory.CreateDirectory(Path.Combine(o, "frames"));
            foreach (var f in Directory.GetFiles(Path.Combine(o, "frames"), "*.jpg")) File.Delete(f);
            EditorSceneManager.OpenScene(DS47FlowBuild.Scene47, OpenSceneMode.Single);
            SessionState.SetBool(SessKey + ".active", true);
            SessionState.SetString(SessKey + ".out", Path.GetFullPath(o));
            SessionState.SetString(SessKey + ".script", script);
            SessionState.SetFloat(SessKey + ".start", (float)EditorApplication.timeSinceStartup);
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static Key[] ParseKeys(string s)
        {
            if (string.IsNullOrWhiteSpace(s)) return new Key[0];
            return s.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries).Select(k => (Key)Enum.Parse(typeof(Key), k)).ToArray();
        }

        static void Setup(DS47Flow flow)
        {
            var demo = JsonUtility.FromJson<DemoRoot>(flow.flowJson.text).demo;
            var list = script == "variant" ? demo.variant : demo.main;
            segs = list.Select(d => new Seg { s0 = d.s0, s1 = d.s1, keys = ParseKeys(d.keys), label = d.labelJa }).ToArray();
            if (script == "variant")
            {
                var l1 = demo.variantLeave; var l2 = demo.variantLeaveHold;
                leaves = new[] {
                    new LeaveAct { name = "intro_leave", at = l1.s0, relWave = false, dur = l1.s1 - l1.s0, off = new Vector3(l1.offsetM[0], l1.offsetM[1], l1.offsetM[2]) },
                    new LeaveAct { name = "hold_leave", at = l2.waveOffsetS, relWave = true, dur = l2.durS, off = new Vector3(l2.offsetM[0], l2.offsetM[1], l2.offsetM[2]) } };
            }
            var go = new GameObject("DS47 記録（試験だけ・保存しない）") { hideFlags = HideFlags.DontSave };
            rec = go.AddComponent<DS47Recorder>();
            rec.flow = flow; rec.outDir = od; rec.captureFrames = script == "main";
            rec.sprays = flow.bus.sprays.Where(s => s != null && s.name == "DS31 spray").ToList();
            rec.extra = () => intended.throttle.ToString("R", CultureInfo.InvariantCulture) + "|" + intended.turn.ToString("R", CultureInfo.InvariantCulture) + "|" + (intended.stop ? 1 : 0) + "|" + flow.LastYLocal.ToString("R", CultureInfo.InvariantCulture) + "|" + flow.LastYPaint.ToString("R", CultureInfo.InvariantCulture);
            flow.hmdCamera.enabled = false;   // 画面へは描かず、記録の部品が手で描く（二重に描かない）
            kb = InputSystem.AddDevice<Keyboard>("DS47VirtualKeyboard");
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
            if (paper != null) { paper.Set(false, false, false); notes.Add("paper=off"); }
            notes.Add("script=" + script + " fixedDeltaTime=" + F(Time.fixedDeltaTime) + " stepping=EditorApplication.Step");
            setup = true;
        }

        static void Mark(string k) { if (!marks.ContainsKey(k)) { marks[k] = Time.frameCount; if (rec != null) rec.stillRequests.Add(k); } }

        static void Poll()
        {
            double now = EditorApplication.timeSinceStartup;
            double start = SessionState.GetFloat(SessKey + ".start", (float)now);
            od = SessionState.GetString(SessKey + ".out", od);
            script = SessionState.GetString(SessKey + ".script", script);
            if (now - start > 1500) { Finish("打ち切り（1500 s）", 2); return; }
            if (!EditorApplication.isPlaying) return;
            // 1 フレームずつ進める：止めた状態で EditorApplication.Step（1 フレームの時間 = 物理の固定の時間刻み 1/90 s。VR の 90 Hz の 1 コマ）
            if (!captureSet) { EditorApplication.isPaused = true; captureSet = true; }
            if (!Application.runInBackground) Application.runInBackground = true;
            polls++;
            if (Time.frameCount == lastFrame)
            {
                if (polls == 1 || polls % 20 == 0) { if (!EditorApplication.isPaused) EditorApplication.isPaused = true; EditorApplication.Step(); }
                return;
            }
            lastFrame = Time.frameCount; polls = 0;
            rtime += Time.deltaTime;
            var flow = UnityEngine.Object.FindFirstObjectByType<DS47Flow>();
            if (flow == null || !flow.Ready) return;
            if (!setup) Setup(flow);
            var clk = flow.clock;
            double exp = clk.ExperienceSeconds;
            if (Time.frameCount % 90 == 0)
            {
                File.AppendAllText(Path.Combine(od, "status.jsonl"), "{\"frame\":" + Time.frameCount + ",\"exp\":" + F(exp) + ",\"state\":\"" + clk.State + "\",\"phase\":\"" + flow.CurrentPhase + "\",\"handedOver\":" + (flow.HandedOver ? "true" : "false") +
                    ",\"paused\":" + (flow.Paused ? "true" : "false") + ",\"pred\":" + F(flow.PredictedTotalS) + ",\"predictions\":" + flow.Predictions + ",\"errors\":" + flow.Errors + ",\"lastError\":\"" + Esc(flow.LastError) + "\",\"stages\":\"" + string.Join("|", clk.StageNames()) + "\"}" + "\n");
            }
            if (!flow.HandedOver && exp > flow.Cfg.timing.introMaxS + 5.0) { WriteReport(flow, "\"abortJa\":\"引き継ぎが起きなかった\""); Finish("引き継ぎなし", 3); return; }

            // 操船の入力（次のフレームの物理の段が読む）
            var seg = segs.FirstOrDefault(s => exp >= s.s0 && exp < s.s1);
            var keys = seg != null ? seg.keys : new Key[0];
            InputState.Change(kb, new KeyboardState(keys));
            intended = new DS44InputSample
            {
                throttle = Mathf.Clamp((keys.Contains(Key.W) ? 1f : 0f) - (keys.Contains(Key.S) ? 1f : 0f), -1f, 1f),
                turn = Mathf.Clamp((keys.Contains(Key.D) ? 1f : 0f) - (keys.Contains(Key.A) ? 1f : 0f), -1f, 1f),
                stop = keys.Contains(Key.Space), source = "intended"
            };

            // 観賞の位置から外れる（variant）：HMD Camera の局所の位置をずらす（頭部追跡の代わり。試験だけ）
            foreach (var L in leaves)
            {
                double at = L.relWave ? (flow.HandedOver ? flow.WaveStartS + L.at : double.PositiveInfinity) : L.at;
                if (L.started < 0 && exp >= at) { L.started = Time.frameCount; L.rStart = rtime; L.expStart = exp; flow.hmdCamera.transform.localPosition = L.off; }
                else if (L.started >= 0 && L.restored < 0)
                {
                    if (L.paused < 0 && flow.Paused) { L.paused = Time.frameCount; L.expPaused = exp; Mark(script + "_" + L.name + "_paused"); }
                    if (rtime - L.rStart >= L.dur) { L.restored = Time.frameCount; flow.hmdCamera.transform.localPosition = Vector3.zero; }
                }
                else if (L.restored >= 0 && L.resumed < 0 && !flow.Paused) { L.resumed = Time.frameCount; L.expResumed = exp; }
            }

            // 見るための静止画（PNG、MSAA 8）
            if (exp >= 10.0) Mark(script + "_s10_intro");
            if (flow.HandedOver) Mark(script + "_handover");
            if (flow.HandedOver && exp >= flow.WaveStartS) Mark(script + "_formation_start");
            if (flow.HandedOver && exp >= flow.WaveStartS + 8.0) Mark(script + "_wave08");
            if (flow.HandedOver && exp >= flow.WaveStartS + 12.0) Mark(script + "_tstar");
            if (flow.HandedOver && exp >= flow.AfterglowStartS + 0.3 * 6.0) Mark(script + "_afterglow_u030");
            if (flow.HandedOver && exp >= flow.AfterglowStartS + 0.6 * 6.0) Mark(script + "_afterglow_u060");

            if (!finalDone && flow.HandedOver && clk.Ended && flow.CurrentPhase == DS47Flow.Phase.End)
            {
                // 終わりのフレームを 3 つ記録してから確かめる（止まった後も画が変わらないこと）
                if (!marks.ContainsKey("end_seen")) { marks["end_seen"] = Time.frameCount; Mark(script + "_end"); return; }
                if (Time.frameCount - marks["end_seen"] < 9) return;
                finalDone = true;
                string final = FinalChecks(flow);
                WriteReport(flow, final);
                Finish("台本の終わり", 0);
            }
        }

        // 原画視点の確かめ（114）：乗っていた船の根と、原画の場面の boat_mid の根（隠したまま、支えが t* の置き方へ戻したもの）の比べ、
        // 同じプレハブの頂点を原画視点（DS27 painting、1920×1080）へ写した画素のずれ、描いた画像（船あり・船なし・原画の船）。
        static string FinalChecks(DS47Flow flow)
        {
            var sb = new StringBuilder();
            var ride = flow.steer.transform; var paint = flow.paintingSeatBoat;
            sb.Append("\"poseVsPaintingJson\":{\"posDiffM\":").Append(F((ride.position - flow.paintRootPos).magnitude)).Append(",\"rotDiffDeg\":").Append(F(Quaternion.Angle(ride.rotation, flow.paintRootRot))).Append('}');
            sb.Append(",\"poseVsPaintingSceneRoot\":{\"posDiffM\":").Append(F((ride.position - paint.position).magnitude)).Append(",\"rotDiffDeg\":").Append(F(Quaternion.Angle(ride.rotation, paint.rotation))).Append('}');
            // 頂点の画素のずれ
            var cam = flow.paintingCamera;
            const int W = 1920, H = 1080;
            var proj = Matrix4x4.Perspective(cam.fieldOfView, (float)W / H, cam.nearClipPlane, cam.farClipPlane);
            var vpm = proj * cam.worldToCameraMatrix;
            Func<Vector3, Vector2> px = p => { var c = vpm * new Vector4(p.x, p.y, p.z, 1f); return new Vector2((c.x / c.w * 0.5f + 0.5f) * W, (c.y / c.w * 0.5f + 0.5f) * H); };
            var mfR = ride.GetComponentsInChildren<MeshFilter>(true).OrderBy(m => m.name).ToList();
            var mfP = paint.GetComponentsInChildren<MeshFilter>(true).OrderBy(m => m.name).ToList();
            var d = new List<float>();
            int pairs = 0;
            foreach (var a in mfR)
            {
                var b = mfP.FirstOrDefault(m => m.name == a.name);
                if (b == null || a.sharedMesh == null || a.sharedMesh != b.sharedMesh) continue;
                var rA = a.GetComponent<MeshRenderer>(); if (rA == null || !a.gameObject.activeInHierarchy) continue;
                pairs++;
                var vs = a.sharedMesh.vertices;
                var ma = a.transform.localToWorldMatrix; var mb = b.transform.localToWorldMatrix;
                foreach (var v in vs) d.Add((px(ma.MultiplyPoint3x4(v)) - px(mb.MultiplyPoint3x4(v))).magnitude);
            }
            d.Sort();
            float mx = d.Count > 0 ? d[d.Count - 1] : float.NaN, p95 = d.Count > 0 ? d[(int)(0.95 * (d.Count - 1))] : float.NaN;
            sb.Append(",\"vertexPx\":{\"meshPairs\":").Append(pairs).Append(",\"vertices\":").Append(d.Count).Append(",\"maxPx\":").Append(F(mx)).Append(",\"p95Px\":").Append(F(p95))
              .Append(",\"noteJa\":\"乗っていた船と原画の場面の boat_mid（同じプレハブ）の同じ頂点を、原画視点の 1920×1080 へ写した位置の差\"}");
            // 描いた画像
            string img = Path.Combine(od, "painting");
            Directory.CreateDirectory(img);
            Action<string, Camera> save = (name, c) => { var t = rec.Render(c, W, H, 8); File.WriteAllBytes(Path.Combine(img, name + ".png"), t.EncodeToPNG()); UnityEngine.Object.Destroy(t); };
            save("view_end", flow.hmdCamera);
            save("painting_end", cam);
            var rends = ride.GetComponentsInChildren<Renderer>(true).Where(r => r.enabled).ToList();
            foreach (var r in rends) r.enabled = false;
            save("painting_end_noboat", cam);
            paint.gameObject.SetActive(true);
            save("painting_end_refboat", cam);
            paint.gameObject.SetActive(false);
            foreach (var r in rends) r.enabled = true;
            var vc = flow.hmdCamera.transform;
            sb.Append(",\"viewCamVsPainting\":{\"posDiffM\":").Append(F((vc.position - cam.transform.position).magnitude)).Append(",\"rotDiffDeg\":").Append(F(Quaternion.Angle(vc.rotation, cam.transform.rotation)))
              .Append(",\"fovView\":").Append(F(flow.hmdCamera.fieldOfView)).Append(",\"fovPainting\":").Append(F(cam.fieldOfView)).Append('}');
            sb.Append(",\"images\":[\"painting/view_end.png\",\"painting/painting_end.png\",\"painting/painting_end_noboat.png\",\"painting/painting_end_refboat.png\"]");
            return sb.ToString();
        }

        static void WriteReport(DS47Flow flow, string final)
        {
            File.WriteAllText(Path.Combine(od, "ds47_frames.csv"), rec.csv.ToString(), new UTF8Encoding(false));
            var ev = flow.bus.events;
            var j = new StringBuilder("{\"schema\":\"GreatWave.DS47.play/1\",\"script\":\"").Append(script).Append("\",\"unity\":\"").Append(Application.unityVersion)
                .Append("\",\"device\":\"").Append(Esc(SystemInfo.graphicsDeviceName)).Append("\",\"utc\":\"").Append(DateTime.UtcNow.ToString("O")).Append('"');
            j.Append(",\"scene\":\"").Append(DS47FlowBuild.Scene47).Append("\",\"sceneSha256\":\"").Append(DS47FlowBuild.FileSha(DS47FlowBuild.Scene47)).Append('"');
            j.Append(",\"fixedDeltaTime\":").Append(F(Time.fixedDeltaTime)).Append(",\"frameStepping\":\"EditorApplication.Step（1 フレーム = Time.deltaTime）\"");
            j.Append(",\"frames\":").Append(rec.Frames).Append(",\"captured\":").Append(rec.Captured).Append(",\"realtimeSum\":").Append(F(rtime)).Append(",\"renderMsTotal\":").Append(F(rec.RenderMsTotal));
            j.Append(",\"handover\":{\"s\":").Append(F(flow.HandoverS)).Append(",\"lead\":").Append(F(flow.LeadS)).Append(",\"waveStart\":").Append(F(flow.WaveStartS)).Append(",\"afterglowStart\":").Append(F(flow.AfterglowStartS))
             .Append(",\"end\":").Append(F(flow.EndS)).Append(",\"predictedTotal\":").Append(F(flow.PredictedTotalS)).Append(",\"predictions\":").Append(flow.Predictions).Append(",\"reason\":\"").Append(flow.HandoverReason).Append("\"")
             .Append(",\"trajT\":").Append(F(flow.steer.Traj != null ? flow.steer.Traj.T : double.NaN)).Append(",\"trajL\":").Append(F(flow.steer.Traj != null ? flow.steer.Traj.L : double.NaN)).Append(",\"trajV0\":").Append(F(flow.steer.Traj != null ? flow.steer.Traj.V0 : double.NaN)).Append('}');
            j.Append(",\"clock\":{\"experienceEnd\":").Append(F(flow.clock.ExperienceSeconds)).Append(",\"state\":\"").Append(flow.clock.State).Append("\",\"ended\":").Append(flow.clock.Ended ? "true" : "false").Append(",\"stages\":[")
             .Append(string.Join(",", flow.clock.StageNames().Select(x => "\"" + x + "\""))).Append("]}");
            j.Append(",\"events\":[").Append(string.Join(",", ev.log.Select(e => "{\"id\":\"" + e.id + "\",\"eventT\":" + F(e.eventT) + ",\"clockT\":" + F(e.clockT) + ",\"step\":" + e.stepIndex + ",\"fired\":" + (e.fired ? "true" : "false") + "}"))).Append(']');
            j.Append(",\"eventTable\":[").Append(string.Join(",", ev.entries.Select(e => "{\"id\":\"" + e.id + "\",\"t\":" + F(e.t) + "}"))).Append(']');
            j.Append(",\"pause\":{\"count\":").Append(flow.PauseCount).Append(",\"resumes\":").Append(flow.ResumeCount).Append('}');
            j.Append(",\"leaves\":[").Append(string.Join(",", leaves.Select(L => "{\"name\":\"" + L.name + "\",\"started\":" + L.started + ",\"paused\":" + L.paused + ",\"restored\":" + L.restored + ",\"resumed\":" + L.resumed +
                ",\"expStart\":" + F(L.expStart) + ",\"expPaused\":" + F(L.expPaused) + ",\"expResumed\":" + F(L.expResumed) + ",\"offset\":[" + F(L.off.x) + "," + F(L.off.y) + "," + F(L.off.z) + "]}"))).Append(']');
            j.Append(",\"input\":{\"frames\":").Append(inputFrames).Append(",\"fallbackFrames\":").Append(fallbackFrames).Append('}');
            j.Append(",\"boatWater\":{\"rebuilds\":").Append(flow.bus.boatWater.Rebuilds).Append(",\"rebuildMsTotal\":").Append(F(flow.bus.boatWater.RebuildMsTotal)).Append(",\"fallbacks\":").Append(flow.bus.boatWater.FallbackCount)
             .Append(",\"queries\":").Append(flow.bus.boatWater.QueryCount).Append('}');
            j.Append(",\"marks\":{").Append(string.Join(",", marks.Select(kv => "\"" + kv.Key + "\":" + kv.Value))).Append('}');
            j.Append(",\"stills\":[").Append(string.Join(",", rec.stillsWritten.Select(s => "\"" + s + "\""))).Append(']');
            j.Append(",\"flowLog\":[").Append(string.Join(",", flow.Log.Select(s => "\"" + Esc(s) + "\""))).Append(']');
            j.Append(",\"notes\":[").Append(string.Join(",", notes.Select(s => "\"" + Esc(s) + "\""))).Append(']');
            j.Append(',').Append(final).Append('}');
            File.WriteAllText(Path.Combine(od, "ds47_play.json"), j.ToString(), new UTF8Encoding(false));
        }

        static void Finish(string why, int code)
        {
            EditorApplication.update -= Poll;
            SessionState.EraseBool(SessKey + ".active");
            try { if (kb != null) InputSystem.RemoveDevice(kb); } catch (Exception) { }
            Debug.Log("DS47_PLAY_DONE " + why + " script=" + script + " frames=" + (rec != null ? rec.Frames : -1));
            EditorApplication.Exit(code);
        }
    }
}
