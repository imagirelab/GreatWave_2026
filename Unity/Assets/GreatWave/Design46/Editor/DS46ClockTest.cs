using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design31;
using GreatWave.Design34;
using GreatWave.Design36;
using GreatWave.Design38;
using GreatWave.Design39;
using GreatWave.Design43;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design46.EditorTools
{
    // 設計46：共通時計（GWClock を Master に広げたもの）の検査。PC の Editor（batchmode）の描画と計算。HMD 実機ではない。
    //   1. 場面：設計41 の DS41_Boats.unity を開き（保存しない）、GWClock を Master に、再生器を時計の段に替え（enabled = false、clock = null）、
    //      爪・飛沫は自分で時計を読まない設定にし、段の部品 DS46ClockBus・出来事の表 DS46EventTrack・船用水面データ DS43BoatWater を足して、
    //      DS46_Clock.unity として別に保存する。
    //   2. 原画視点の回帰：同じ t* の原画視点を、DS41_Boats.unity の設計41 の道（再生器・爪・飛沫を直接 Seek）と、DS46_Clock.unity の時計の道（clock.Seek）で
    //      同じ描き方で描き、画素を比べる（同じなら評価器の値も同じ）。
    //   3. 基準の通し：初期化 → 1/32 s ずつ体験の 0〜14 s を進める。毎段で、全段が同じ時刻を受けたか（同期）と、層ごとの形の印（181 のため）を記録し、
    //      確かめの時刻（0・3・5・8・10.5・12・13・14 s）で形のハッシュ一式を取る。
    //   4. 停止・再開・初期化・途中からの再生の 4 つの道で、同じ時刻の形のハッシュ一式が基準と一致するかを見る。
    //   5. 181：白（頂点の旗と描いた白）・藍の色面（白を切った描画）・爪・飛沫が、どの時刻で終態に達するか（1/32 s の格子と t* のまわりの 1/256 s）。
    public static class DS46ClockTest
    {
        const string Scene41 = "Assets/GreatWave/Design41/Scenes/DS41_Boats.unity";
        public const string Scene46 = "Assets/GreatWave/Design46/Scenes/DS46_Clock.unity";
        const string OutRoot = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/46/clock/unity";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const int W = 1920, H = 1080;
        const double TStar = 12.0, Dt = 1.0 / 32.0;
        static readonly double[] Checks = { 0, 3, 5, 8, 10.5, 12, 13, 14 };
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Rect Region43 = new Rect(-31.29f, -48.25f, 23.03f - -31.29f, 3.47f - -48.25f);

        static string[] Protected => new[] {
            Scene41, "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity", "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity",
            "Assets/GreatWave/Design34/Scenes/DS34_ThreeLayers.unity", "Assets/GreatWave/Design43/Scenes/DS43_BoatWater.unity",
            "Assets/GreatWave/Design44/Scenes/DS44_Steer.unity", "Assets/GreatWave/Design45/Scenes/DS45_Comfort.unity",
            "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs", "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs",
            "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs", "Assets/GreatWave/Design43/Scripts/DS43BoatWater.cs",
            "../Tools/GWContext/seat_v1.json", "Build/Design/28R01F/F_final/timewarp_F_final.json", "Build/Design/33/claws/ds33_claw_frames_f32.bin" };

        class Ctx
        {
            public GameObject ctx; public DS30SinglePlayback play; public List<DS30SheetPlayer> sheets;
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public DS34ClawPlayer claws; public MeshRenderer clawR; public DS34LayerSet layers;
            public DS31InstancedParticles spray, dense; public DS36ClawPalette pal; public DS36SeaPalette seaPal;
            public DS38ClawOutline clawLine; public DS38LineGlobals globals; public List<DS38SheetOutline> lineComps = new List<DS38SheetOutline>();
            public DS39PaperLayers paper; public DS46ClockBus bus; public GWClock clock;
        }

        static string Arg(string[] a, string name) { for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1]; return null; }

        // ------------------------------------------------------------------ 1. 場面
        static void BuildScene(StringBuilder note)
        {
            EditorSceneManager.OpenScene(Scene41, OpenSceneMode.Single);
            var scene = EditorSceneManager.GetActiveScene();
            var roots = scene.GetRootGameObjects();
            var clock = roots.Select(g => g.GetComponentInChildren<GWClock>(true)).First(x => x != null);
            var play = roots.Select(g => g.GetComponentInChildren<DS30SinglePlayback>(true)).First(x => x != null);
            var claws = roots.Select(g => g.GetComponentInChildren<DS34ClawPlayer>(true)).First(x => x != null);
            var layers = roots.Select(g => g.GetComponentInChildren<DS34LayerSet>(true)).First(x => x != null);
            var clawLine = claws.GetComponent<DS38ClawOutline>();
            var parts = roots.SelectMany(g => g.GetComponentsInChildren<DS31InstancedParticles>(true)).ToList();
            var spray = parts.First(p => p.name == "DS31 spray");
            var dense = parts.First(p => p.name == "DS39 spray dense");

            clock.mode = GWClock.ClockMode.Master; clock.playInPlayMode = false; clock.loopSeconds = 0f; clock.seconds = 0f;
            clock.startSeconds = 0.0; clock.endSeconds = 14.0; clock.waveStartSeconds = 0.0; clock.tStarSeconds = 12f;
            clock.maxStepSeconds = 1.0 / 15.0; clock.advanceBeforePhysics = true; clock.speed = 1f;
            play.enabled = false; play.clock = null; play.autoStartDelay = -1f;
            claws.followClockInPlayMode = false;
            spray.followClockInPlayMode = false; dense.followClockInPlayMode = false;

            var go = new GameObject("DS46 共通時計の段");
            var bus = go.AddComponent<DS46ClockBus>();
            var ev = go.AddComponent<DS46EventTrack>();
            var water = go.AddComponent<DS43BoatWater>();
            water.playback = play; water.region = Region43; water.cellSize = 1f;
            bus.clock = clock; bus.playback = play; bus.layers = layers; bus.claws = claws; bus.clawLine = clawLine;
            bus.sprays = new List<DS31InstancedParticles> { spray, dense }; bus.boatWater = water; bus.events = ev; bus.autoPlay = true;
            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, Scene46, true)) throw new InvalidOperationException("DS46_Clock.unity を保存できません。");
            note.Append("場面：DS41_Boats.unity を開き（保存しない）、GWClock を Master（0〜14 s、大波の t* 12 s、EarlyUpdate で進める）、再生器 enabled=0・clock=null、" +
                        "爪と飛沫 2 つの followClockInPlayMode=0、段の部品・出来事の表・船用水面データ（DS43 と同じ範囲）を足して DS46_Clock.unity に保存した。");
        }

        // ------------------------------------------------------------------ 場面を開く・準備・片付け
        static Ctx Open(string path)
        {
            EditorSceneManager.OpenScene(path, OpenSceneMode.Single);
            var roots = EditorSceneManager.GetActiveScene().GetRootGameObjects();
            var c = new Ctx { ctx = roots.First(g => g.name == ContextRootName) };
            c.play = roots.Select(g => g.GetComponentInChildren<DS30SinglePlayback>(true)).First(x => x != null);
            c.sheets = c.play.sheets.Where(s => s != null).ToList();
            var camRoot = GameObject.Find(CamRoot).transform;
            c.cams["painting"] = camRoot.Find("DS27 painting").GetComponent<Camera>();
            c.cams["seat"] = camRoot.Find("DS27 seat").GetComponent<Camera>();
            c.claws = roots.Select(g => g.GetComponentInChildren<DS34ClawPlayer>(true)).First(x => x != null);
            c.clawR = c.claws.GetComponent<MeshRenderer>();
            c.layers = roots.Select(g => g.GetComponentInChildren<DS34LayerSet>(true)).First(x => x != null);
            var parts = roots.SelectMany(g => g.GetComponentsInChildren<DS31InstancedParticles>(true)).ToList();
            c.spray = parts.First(p => p.name == "DS31 spray");
            c.dense = parts.First(p => p.name == "DS39 spray dense");
            c.pal = c.claws.GetComponent<DS36ClawPalette>();
            c.seaPal = roots.Select(g => g.GetComponentInChildren<DS36SeaPalette>(true)).First(x => x != null);
            c.clawLine = c.claws.GetComponent<DS38ClawOutline>();
            c.globals = c.play.GetComponent<DS38LineGlobals>();
            foreach (var s in c.sheets) { var so = s.GetComponent<DS38SheetOutline>(); if (so != null) c.lineComps.Add(so); }
            c.paper = roots.Select(g => g.GetComponentInChildren<DS39PaperLayers>(true)).First(x => x != null);
            c.bus = roots.Select(g => g.GetComponentInChildren<DS46ClockBus>(true)).FirstOrDefault(x => x != null);
            c.clock = roots.Select(g => g.GetComponentInChildren<GWClock>(true)).First(x => x != null);
            return c;
        }

        // 設計41 の Prepare と同じ順。時計の場面では再生器・爪・飛沫の読み込みを段の部品（bus.Prepare）が行う
        static void Prepare(Ctx c)
        {
            foreach (var so in c.lineComps) so.Attach();
            c.clawLine.Attach();
            c.globals.Apply();
            if (c.bus != null) c.bus.Prepare();
            else { c.play.Prepare(); c.spray.Load(); c.claws.Load(); c.dense.Load(); }
            var hp = c.seaPal.SyncFromHero();
            c.pal.white = hp[0]; c.pal.mizuiro = hp[1]; c.pal.aiMid = hp[2]; c.pal.aiDark = hp[3];
            c.pal.Apply();
            foreach (var so in c.lineComps) so.BindMask();
            GlobalsDefault();
            c.paper.Build();
        }

        static void GlobalsDefault()
        {
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS38LineCoordMode", 0);
            Shader.SetGlobalVector("_DS38EyeOverride", Vector4.zero);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
            Shader.SetGlobalFloat("_DS34ClawDiag", 0);
            Shader.SetGlobalFloat("_DS36ClawFaceDiag", 0);
            Shader.SetGlobalFloat("_DS39Gain", 0);
        }

        static void Cleanup(Ctx c)
        {
            GlobalsDefault();
            c.paper.Teardown();
            foreach (var so in c.lineComps) so.ReleaseMask();
            foreach (var s in c.play.sheets) if (s != null) s.Release();
            c.spray.Release(); c.dense.Release(); c.pal.Release(); c.clawLine.Release(); c.claws.Release();
        }

        // 設計41 の道（DS41Boats.Seek と同じ呼び方）
        static void Seek41(Ctx c, double t)
        {
            c.play.Seek(t);
            c.spray.ApplyT(t); c.dense.ApplyT(t); c.claws.ApplyT(t);
            c.layers.whiteBand = true; c.layers.clawsOn = true; c.layers.sprayOn = true;
            c.layers.ApplyToggles();
            c.clawLine.Sync();
            c.paper.Apply();
        }

        // ------------------------------------------------------------------ 描画
        static byte[] Capture(Camera camera, int w, int h, bool colour, int msaa, CommandBuffer cb, string pngPath)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture; float asp = camera.aspect;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = colour ? (Color)SkyTop : Color.white;
            camera.allowHDR = false; camera.allowMSAA = msaa > 1;
            var rw = colour ? RenderTextureReadWrite.sRGB : RenderTextureReadWrite.Linear;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, rw) { antiAliasing = msaa };
            var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, rw);
            rt.Create(); res.Create();
            if (cb != null) camera.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            try
            {
                camera.aspect = (float)w / h; camera.targetTexture = rt;
                camera.Render();
            }
            finally { if (cb != null) camera.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); }
            Graphics.Blit(rt, res);
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, !colour);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            var raw = tex.GetRawTextureData();
            if (pngPath != null) { Directory.CreateDirectory(Path.GetDirectoryName(pngPath)); File.WriteAllBytes(pngPath, tex.EncodeToPNG()); }
            camera.targetTexture = prev; camera.aspect = asp;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return raw;
        }

        // 設計41 の painting_t120_off と同じ条件（紙・むら・密な飛沫なし、白・爪・飛沫 v0 あり、1920×1080、MSAA 8）
        static byte[] PaintingOff(Ctx c, string png)
        {
            c.paper.Set(false, false, false);
            var cb = new CommandBuffer { name = "DS46 飛沫" };
            c.spray.AddTo(cb);
            try { return Capture(c.cams["painting"], W, H, true, 8, cb, png); }
            finally { cb.Release(); }
        }

        static void SetLines(Ctx c, bool on)
        {
            foreach (var s in c.sheets) if (s.outline != null) s.outline.enabled = on;
            if (c.clawLine.Line != null) c.clawLine.Line.enabled = on && c.clawR.enabled;
        }

        // 181 の層の描画：シートだけ（背景・爪・線を隠す）の色区 ID（線形、MSAA なし、480×270）。white = true で白の時間場あり、false で終態の色（藍の色面の模様だけ）
        static byte[] SheetIds(Ctx c, bool white)
        {
            bool clawOn = c.clawR.enabled;
            c.ctx.SetActive(false); c.clawR.enabled = false; SetLines(c, false);
            Shader.SetGlobalFloat("_AF28IdMode", 1); Shader.SetGlobalFloat("_DS27WhiteEnabled", white ? 1 : 0);
            try { return Capture(c.cams["painting"], 480, 270, false, 1, null, null); }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0); Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
                c.ctx.SetActive(true); c.clawR.enabled = clawOn; SetLines(c, true);
            }
        }

        static int DiffPx(byte[] a, byte[] b)
        {
            if (a.Length != b.Length) return -1;
            int n = 0;
            for (int i = 0; i < a.Length; i += 3) if (a[i] != b[i] || a[i + 1] != b[i + 1] || a[i + 2] != b[i + 2]) n++;
            return n;
        }

        // ------------------------------------------------------------------ 本体
        class Snap { public string seq, label; public double exp, wave, tau; public long step; public string state; public SortedDictionary<string, string> h; public string passed; }

        public static void Run()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string od = Arg(a, "-ds46Out") ?? OutRoot;
            Directory.CreateDirectory(od);
            AssetDatabase.Refresh();
            var before = Protected.ToDictionary(p => p, FileSha);
            var note = new StringBuilder();
            var J = new StringBuilder();
            J.Append("{\"schema\":\"GreatWave.DS46.clock_report/1\",\"unity\":\"").Append(Application.unityVersion).Append("\",\"device\":\"").Append(Esc(SystemInfo.graphicsDeviceName))
             .Append("\",\"utc\":\"").Append(DateTime.UtcNow.ToString("O")).Append("\",\"dt\":").Append(F(Dt));

            BuildScene(note);
            J.Append(",\"scene\":\"").Append(Scene46).Append("\",\"sceneSha256\":\"").Append(FileSha(Scene46)).Append("\"");

            // 2. 原画視点の A/B（設計41 の道 と 時計の道）
            byte[] imgA, imgB;
            {
                var c = Open(Scene41);
                try { Prepare(c); Seek41(c, TStar); imgA = PaintingOff(c, od + "/tstar/painting_t120_off_ds41path.png"); }
                finally { Cleanup(c); }
            }
            var c46 = Open(Scene46);
            DS46Probe probe = null;
            var snaps = new List<Snap>();
            var stepCsv = new StringBuilder("seq,step,kind,exp,wave,tau,sync_bad,hero,white_flags,white_count,white_img,indigo_img,claws,spray,boat_tau,events_passed\n");
            int syncBadTotal = 0, stepsTotal = 0;
            try
            {
                Prepare(c46);
                var clock = c46.clock; var bus = c46.bus;
                probe = new DS46Probe(bus);
                c46.layers.whiteBand = true; c46.layers.clawsOn = true; c46.layers.sprayOn = true;
                clock.Seek(TStar);
                c46.paper.Apply();
                imgB = PaintingOff(c46, od + "/tstar/painting_t120_off_ds46clock.png");
                int abDiff = DiffPx(imgA, imgB);
                string prior = "Build/Design/41/model/unity/full/painting_t120_off.png";
                int priorDiff = -2;
                if (File.Exists(prior))
                {
                    var t0 = new Texture2D(2, 2, TextureFormat.RGB24, false);
                    t0.LoadImage(File.ReadAllBytes(prior));
                    var t1 = new Texture2D(W, H, TextureFormat.RGB24, false);
                    t1.LoadRawTextureData(imgB); t1.Apply();
                    var p0 = t0.GetPixels32(); var p1 = t1.GetPixels32();
                    priorDiff = p0.Length == p1.Length ? p0.Where((x, i) => x.r != p1[i].r || x.g != p1[i].g || x.b != p1[i].b).Count() : -1;
                    UnityEngine.Object.DestroyImmediate(t0); UnityEngine.Object.DestroyImmediate(t1);
                }
                J.Append(",\"tstarAB\":{\"ds41PathSha256\":\"").Append(DS46Probe.Sha(imgA)).Append("\",\"ds46ClockSha256\":\"").Append(DS46Probe.Sha(imgB))
                 .Append("\",\"diffPixels\":").Append(abDiff).Append(",\"priorDs41File\":\"").Append(prior).Append("\",\"diffPixelsVsPriorDs41File\":").Append(priorDiff)
                 .Append(",\"noteJa\":\"1920×1080・MSAA 8・紙なし・白と爪と飛沫 v0 あり（設計41 の painting_t120_off と同じ条件）。priorDs41File は設計41 の出力（PNG を読み戻して画素を比べた。-2 は無い）\"}");

                // --- 形のハッシュ一式を取る
                Func<string, string, Snap> snap = (seq, label) =>
                {
                    var s = new Snap { seq = seq, label = label, exp = clock.ExperienceSeconds, wave = clock.WaveSeconds, tau = c46.play.Tau, step = clock.StepIndex, state = clock.State.ToString(), h = probe.All(), passed = bus.events.PassedAt(clock.ExperienceSeconds) };
                    c46.paper.Apply();
                    s.h["image_painting"] = DS46Probe.Sha(Capture(c46.cams["painting"], 960, 540, true, 1, null, null));
                    snaps.Add(s);
                    return s;
                };
                // --- 同期の検査：全段が今の時刻の決定を受けたか、層が同じ時刻・同じ τ か
                Func<int> syncBad = () =>
                {
                    var st = clock.LastStep; int bad = 0;
                    foreach (var kv in clock.StageLast) if (kv.Value.index != st.index) bad++;
                    if (c46.play.T != st.wave) bad++;
                    if (c46.play.Tau != c46.play.Warp.TauAt(st.wave)) bad++;
                    foreach (var s in c46.sheets) if (s.AppliedTau != c46.play.Tau) bad++;
                    if (c46.claws.AppliedT != st.wave) bad++;
                    if (c46.spray.AppliedT != st.wave || c46.dense.AppliedT != st.wave) bad++;
                    if (bus.boatWater.TauUsed != c46.play.Tau) bad++;
                    if (c46.layers.LastHeroTau != c46.sheets[probe.HeroIndex].AppliedTau) bad++;
                    if (c46.clawLine.SyncedT != st.wave) bad++;
                    return bad;
                };
                // --- 181 の層の印（毎段）
                var series = new Dictionary<string, List<string>>();
                foreach (var k in new[] { "hero", "white_flags", "white_img", "indigo_img", "claws", "spray" }) series[k] = new List<string>();
                var seriesT = new List<double>();
                Action<string> rowStep = seq =>
                {
                    var st = clock.LastStep;
                    int bad = syncBad(); syncBadTotal += bad; stepsTotal++;
                    int wc;
                    string hero = probe.SheetHash(probe.HeroIndex), wf = DS46Probe.Sha(probe.WhiteFlags(out wc));
                    string wi = DS46Probe.Sha(SheetIds(c46, true)), ii = DS46Probe.Sha(SheetIds(c46, false));
                    string cl = DS46Probe.Sha(probe.ClawXyz()), sp = DS46Probe.Sha(probe.SprayXyzr());
                    if (seq == "R")
                    {
                        seriesT.Add(st.experience);
                        series["hero"].Add(hero); series["white_flags"].Add(wf); series["white_img"].Add(wi); series["indigo_img"].Add(ii); series["claws"].Add(cl); series["spray"].Add(sp);
                    }
                    stepCsv.Append(seq).Append(',').Append(st.index).Append(',').Append(st.kind).Append(',').Append(F(st.experience)).Append(',').Append(F(st.wave)).Append(',').Append(F(c46.play.Tau))
                        .Append(',').Append(bad).Append(',').Append(hero.Substring(0, 16)).Append(',').Append(wf.Substring(0, 16)).Append(',').Append(wc).Append(',').Append(wi.Substring(0, 16)).Append(',').Append(ii.Substring(0, 16))
                        .Append(',').Append(cl.Substring(0, 16)).Append(',').Append(sp.Substring(0, 16)).Append(',').Append(F(bus.boatWater.TauUsed)).Append(',').Append(bus.events.PassedAt(st.experience)).Append('\n');
                };
                Action<string, double> runTo = (seq, to) =>
                {
                    while (clock.ExperienceSeconds < to - 1e-12 && clock.State == GWClock.RunState.Running)
                    {
                        clock.Advance(Dt);
                        rowStep(seq);
                    }
                };

                // 3. 基準の通し R
                bus.events.log.Clear();
                clock.Initialise(true);
                rowStep("R");
                var refH = new Dictionary<double, Snap>();
                refH[0] = snap("R", "init");
                foreach (var t in Checks.Where(x => x > 0))
                {
                    runTo("R", t);
                    refH[t] = snap("R", "t" + F(t));
                }
                var evR = bus.events.log.ToList();
                bool rEnded = clock.Ended && clock.State == GWClock.RunState.Stopped && clock.ExperienceSeconds == 14.0;

                // 181：終態に達する時刻（1/32 s の格子）
                var j181 = new StringBuilder("{");
                bool all181 = true;
                foreach (var kv in series)
                {
                    var l = kv.Value; string fin = l[l.Count - 1];
                    int k = l.Count - 1;
                    while (k > 0 && l[k - 1] == fin) k--;
                    double tFinal = seriesT[k], tLastChange = k > 0 ? seriesT[k - 1] : double.NaN;
                    int distinct = l.Distinct().Count();
                    bool ok = Math.Abs(tFinal - TStar) < 1e-12;
                    if (kv.Key != "hero") all181 &= ok;
                    if (j181.Length > 1) j181.Append(',');
                    j181.Append('"').Append(kv.Key).Append("\":{\"tFinal\":").Append(F(tFinal)).Append(",\"tLastChange\":").Append(F(tLastChange)).Append(",\"distinctStates\":").Append(distinct).Append(",\"finalAtTStar\":").Append(ok ? "true" : "false").Append('}');
                }
                j181.Append('}');

                // 181：t* のまわりの 1/256 s（Seek。止めたまま）
                clock.Stop();
                clock.Seek(TStar);
                var finWi = SheetIds(c46, true); var finIi = SheetIds(c46, false);
                var finCl = probe.ClawXyz(); var finSp = probe.SprayXyzr(); int fwc; var finWf = probe.WhiteFlags(out fwc); var finHero = probe.SheetXyz(probe.HeroIndex);
                var fine = new StringBuilder("[");
                bool fineOk = true;
                for (int j = -8; j <= 8; j++)
                {
                    double t = TStar + j / 256.0;
                    clock.Seek(t);
                    int wcj; var wf = probe.WhiteFlags(out wcj);
                    int dWhiteFlags = 0; for (int i = 0; i < wf.Length; i++) if (wf[i] != finWf[i]) dWhiteFlags++;
                    int dWi = DiffPx(SheetIds(c46, true), finWi), dIi = DiffPx(SheetIds(c46, false), finIi);
                    float dCl = DS46Probe.MaxAbsDiff(probe.ClawXyz(), finCl), dSp = DS46Probe.MaxAbsDiff(probe.SprayXyzr(), finSp), dHero = DS46Probe.MaxAbsDiff(probe.SheetXyz(probe.HeroIndex), finHero);
                    bool atOrAfter = j >= 0;
                    bool allFinal = dWhiteFlags == 0 && dWi == 0 && dIi == 0 && dCl == 0f && dSp == 0f;
                    bool allMoving = dWi > 0 && dIi > 0 && dCl > 0f && dSp > 0f;
                    if (atOrAfter && !allFinal) fineOk = false;
                    if (fine.Length > 1) fine.Append(',');
                    fine.Append("{\"t\":").Append(F(t)).Append(",\"tau\":").Append(F(c46.play.Tau)).Append(",\"whiteFlagsDiff\":").Append(dWhiteFlags).Append(",\"whiteImgDiffPx\":").Append(dWi)
                        .Append(",\"indigoImgDiffPx\":").Append(dIi).Append(",\"clawsMaxDiffM\":").Append(F(dCl)).Append(",\"sprayMaxDiff\":").Append(F(dSp)).Append(",\"heroMaxDiffM\":").Append(F(dHero))
                        .Append(",\"allFinal\":").Append(allFinal ? "true" : "false").Append(",\"allStillMoving\":").Append(allMoving ? "true" : "false").Append('}');
                }
                fine.Append(']');

                // 4. 停止・再開・初期化・途中からの再生
                // S1：停止と再開
                clock.Initialise(true);
                rowStep("S1");
                runTo("S1", 5.0);
                clock.Stop();
                var s1a = snap("S1", "stop_at_5");
                long idxStop = clock.StepIndex; double tStop = clock.ExperienceSeconds;
                for (int i = 0; i < 32; i++) clock.Advance(Dt);   // 止まっている間の 32 コマ（1 s）
                bool stoppedHeld = clock.StepIndex == idxStop && clock.ExperienceSeconds == tStop;
                var s1b = snap("S1", "stopped_32_frames");
                clock.Resume();
                foreach (var t in new[] { 8.0, 10.5, 12.0, 14.0 }) { runTo("S1", t); snap("S1", "resume_t" + F(t)); }
                // S2：初期化（終わりから）
                clock.Initialise();
                var s2a = snap("S2", "init_from_end");
                clock.Resume();
                foreach (var t in new[] { 3.0, 5.0 }) { runTo("S2", t); snap("S2", "t" + F(t)); }
                // S3：途中からの再生（後ろ・前・後ろへ跳ぶ。止めたまま → 再生）
                bus.events.log.Clear();
                clock.Stop();
                foreach (var t in new[] { 10.5, 3.0, 13.0, 8.0 }) { clock.Seek(t); snap("S3", "seek_t" + F(t)); }
                clock.Resume();
                foreach (var t in new[] { 12.0, 14.0 }) { runTo("S3", t); snap("S3", "play_from_8_t" + F(t)); }
                var evS3 = bus.events.log.ToList();
                // S4：再生中に跳ぶ（2 s まで進め、再生のまま 12 → 0 → 10.5 へ Seek し、そこから進める）
                bus.events.log.Clear();
                clock.Initialise(true);
                runTo("S4", 2.0);
                clock.Seek(12.0); snap("S4", "running_seek_t12");
                clock.Seek(0.0); snap("S4", "running_seek_t0");
                clock.Seek(10.5); snap("S4", "running_seek_t10.5");
                runTo("S4", 13.0); snap("S4", "play_from_10.5_t13");
                var evS4 = bus.events.log.ToList();

                // 比べ：同じ体験の時刻の基準 R と一致するか
                var cmp = new StringBuilder("[");
                int compared = 0, mismatched = 0;
                foreach (var s in snaps.Where(x => x.seq != "R"))
                {
                    Snap r;
                    if (!refH.TryGetValue(s.exp, out r)) continue;
                    compared++;
                    var bad = s.h.Keys.Union(r.h.Keys).Where(k => !s.h.ContainsKey(k) || !r.h.ContainsKey(k) || s.h[k] != r.h[k]).ToList();
                    if (s.passed != r.passed) bad.Add("events_passed");
                    if (bad.Count > 0) mismatched++;
                    if (cmp.Length > 1) cmp.Append(',');
                    cmp.Append("{\"seq\":\"").Append(s.seq).Append("\",\"label\":\"").Append(s.label).Append("\",\"exp\":").Append(F(s.exp)).Append(",\"keys\":").Append(s.h.Count).Append(",\"mismatchKeys\":[")
                       .Append(string.Join(",", bad.Select(x => "\"" + x + "\""))).Append("]}");
                }
                cmp.Append(']');
                // 出来事
                Func<List<DS46EventTrack.Record>, string> evJ = l => "[" + string.Join(",", l.Select(e => "{\"id\":\"" + e.id + "\",\"eventT\":" + F(e.eventT) + ",\"clockT\":" + F(e.clockT) + ",\"step\":" + e.stepIndex + ",\"fired\":" + (e.fired ? "true" : "false") + "}")) + "]";
                bool evROk = bus.events.entries.All(e => evR.Count(x => x.id == e.id && x.fired) == 1) && evR.Where(x => x.fired).All(x => x.clockT >= x.eventT && x.clockT - x.eventT < Dt) && evR.All(x => x.fired);
                bool evS3Ok = evS3.Count(x => x.fired && x.id == "t_star" && x.clockT == 12.0) == 1 && evS3.Count(x => x.fired && x.id == "hold_end" && x.clockT == 14.0) == 1 && evS3.Count(x => x.fired) == 2;

                J.Append(",\"stages\":[").Append(string.Join(",", clock.StageNames().Select(x => "\"" + x + "\""))).Append(']');
                J.Append(",\"sync\":{\"steps\":").Append(stepsTotal).Append(",\"badChecks\":").Append(syncBadTotal).Append('}');
                J.Append(",\"reference\":{\"ended\":").Append(rEnded ? "true" : "false").Append(",\"checkpoints\":[").Append(string.Join(",", Checks.Select(F))).Append("]}");
                J.Append(",\"stop\":{\"tStop\":").Append(F(tStop)).Append(",\"heldWhileStopped\":").Append(stoppedHeld ? "true" : "false").Append(",\"sameShapeAfter32Frames\":").Append(s1a.h.All(kv => s1b.h[kv.Key] == kv.Value) ? "true" : "false").Append('}');
                J.Append(",\"compare\":{\"compared\":").Append(compared).Append(",\"mismatched\":").Append(mismatched).Append(",\"rows\":").Append(cmp).Append('}');
                J.Append(",\"acceptance1_sameTimeSameShape\":").Append(compared >= 15 && mismatched == 0 && stoppedHeld ? "true" : "false");
                J.Append(",\"b181\":{\"grid\":").Append(j181).Append(",\"fine\":").Append(fine).Append(",\"allFourFinalAtTStarOnGrid\":").Append(all181 ? "true" : "false").Append(",\"fineAtOrAfterTStarAllFinal\":").Append(fineOk ? "true" : "false").Append('}');
                J.Append(",\"events\":{\"R\":").Append(evJ(evR)).Append(",\"S3\":").Append(evJ(evS3)).Append(",\"S4\":").Append(evJ(evS4)).Append(",\"rOnceEachLagBelowOneStep\":").Append(evROk ? "true" : "false").Append(",\"s3SeekSkipsThenFires\":").Append(evS3Ok ? "true" : "false").Append('}');
                J.Append(",\"snaps\":[").Append(string.Join(",", snaps.Select(s => "{\"seq\":\"" + s.seq + "\",\"label\":\"" + s.label + "\",\"exp\":" + F(s.exp) + ",\"wave\":" + F(s.wave) + ",\"tau\":" + F(s.tau) + ",\"step\":" + s.step + ",\"state\":\"" + s.state + "\",\"passed\":\"" + s.passed + "\",\"h\":" + DS46Probe.J(s.h) + "}"))).Append(']');

                // 見るための静止画：原画視点と座席（t 8・10.5・12・13 s。時計の道）
                foreach (var t in new[] { 8.0, 10.5, 12.0, 13.0 })
                {
                    clock.Seek(t); c46.paper.Apply();
                    PaintingOff(c46, od + "/stills/painting_t" + t.ToString("00.0", CultureInfo.InvariantCulture) + ".png");
                    var cb = new CommandBuffer { name = "DS46 飛沫" }; c46.spray.AddTo(cb);
                    try { Capture(c46.cams["seat"], W, H, true, 8, cb, od + "/stills/seat_t" + t.ToString("00.0", CultureInfo.InvariantCulture) + ".png"); } finally { cb.Release(); }
                }
            }
            finally
            {
                probe?.Dispose();
                Cleanup(c46);
            }
            File.WriteAllText(od + "/ds46_steps.csv", stepCsv.ToString(), new UTF8Encoding(false));
            var after = Protected.ToDictionary(p => p, FileSha);
            J.Append(",\"protectedUnchanged\":").Append(Protected.All(p => before[p] == after[p]) ? "true" : "false");
            J.Append(",\"protected\":[").Append(string.Join(",", Protected.Select(p => "\"" + p + " " + after[p] + "\""))).Append(']');
            J.Append(",\"noteJa\":\"").Append(Esc(note.ToString() + " PC の Editor（batchmode）の計算と描画。HMD 実機ではない。")).Append("\"");
            J.Append(",\"secondsTotal\":").Append(F(total.Elapsed.TotalSeconds)).Append('}');
            File.WriteAllText(od + "/ds46_clock_report.json", J.ToString(), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS46_CLOCK_DONE seconds=" + total.Elapsed.TotalSeconds.ToString("0.0", CultureInfo.InvariantCulture));
        }

        static string F(double x) => DS46Probe.F(x);
        static string Esc(string s) => s.Replace("\\", "\\\\").Replace("\"", "\\\"");
        static string FileSha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
