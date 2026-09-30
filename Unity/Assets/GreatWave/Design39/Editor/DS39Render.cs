using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design30;
using GreatWave.Design31;
using GreatWave.Design34;
using GreatWave.Design35;
using GreatWave.Design36;
using GreatWave.Design37;
using GreatWave.Design38;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design39.EditorTools
{
    // 設計39 第「紙」部 Unity：紙の地（①）・摺りのむら（②）・小飛沫（③）を一つずつ入切し、切った状態が設計38 と同じであること、
    // 入れた状態の画像、頭の揺れ（±0.1 m）で模様が泳がないことを確かめる描画（PC オフスクリーン描画、HMD ではない）と、GPU 時間の計測器のプレイヤー。
    // 設計38 の場面 DS38_Outlines.unity（読むだけ）を開き、DS39PaperLayers（既定は全部切）と小飛沫の 2 つ目の DS31InstancedParticles を足して
    // DS39_Paper.unity として保存する（設計27〜38 の場面・スクリプト・シェーダー・材質は変えない）。
    // Render の段（-ds39Skip で飛ばせる）：
    //   t28.   全部切の t* の画像の組（設計38 の RenderT28 と同じ手順・同じ名前）。設計38 の画像との画素の一致と評価器で「切ったら同じ」を確かめる。
    //   onoff. 視点 painting（t 12）・seat（t 12）・seat_toward_wave（t 10.5）× {切, ①, ②, ③, 全部}。
    //   swim.  頭の揺れの検査：seat_toward_wave t 9・seat t 12 × 目 −0.1〜+0.1 m（5 段）× {切, ① 利得 15, ② 利得 15} の色と、面の座標（設計37 の DS37 Surface Coord）。
    //   video. 頭の揺れの動画（±0.1 m・周期 2 s・4 s）：全部入 seat_toward_wave t 9・seat t 12、①② 利得 6 の seat_toward_wave t 9。形成の動画（全部入、seat、t 0〜14 s）。
    // BuildPerf：DS39_Paper.unity を DS39_Perf.unity へ写して計測器 DS39PerfRunner を置き、美術優先32・設計35 と同じ Release のプレイヤーを作る。
    public static class DS39Render
    {
        const string Scene38 = "Assets/GreatWave/Design38/Scenes/DS38_Outlines.unity";
        public const string Scene39 = "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity";
        public const string ScenePerf = "Assets/GreatWave/Design39/Scenes/DS39_Perf.unity";
        const string MatDir = "Assets/GreatWave/Design39/Materials";
        const string KeyShader = "GreatWave/Design39/DS39 Paper Keypose", MeshShader = "GreatWave/Design39/DS39 Paper Mesh";
        const string CoordShaderName = "GreatWave/Design37/DS37 Surface Coord";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const string DenseData = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/39/paper/spray/ds39_spray_dense_frames.json";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const string PlayerPath = "Build/Design/39/paper/player/DS39Perf.exe";
        const int W = 1920, H = 1080, Fps = 30;
        const float TStar = 12f, TEnd = 14f, Sway = 0.1f, SwayPeriod = 2f, SwimGain = 15f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);

        static string[] Protected => new[] {
            Scene38, "Assets/GreatWave/Design37/Scenes/DS37_FlowLines.unity", "Assets/GreatWave/Design36/Scenes/DS36_Palette.unity",
            "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs", "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs",
            "Assets/GreatWave/Design31/Scripts/DS31InstancedParticles.cs", "Assets/GreatWave/Design31/Shaders/DS31_Spray_Unlit.shader",
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design36/Shaders/DS36_Claw_Palette.shader",
            "Assets/GreatWave/Design38/Shaders/DS38_Outline_Keypose.shader", "Assets/GreatWave/Design38/Shaders/DS38_Outline_Mesh.shader",
            "Assets/GreatWave/Design38/Materials/DS38_Outline_hero.mat", "Assets/GreatWave/Design38/Materials/DS38_Outline_near.mat",
            "Assets/GreatWave/Design38/Materials/DS38_Outline_claws.mat", "Assets/GreatWave/Design38/Editor/DS38Render.cs",
            "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin", "Build/Design/33/claws/ds33_claw_frames_f32.bin",
            "Build/Design/31/spray/ds31_spray_frames.bin", "Build/Design/38/outlines/unity/prep/ds38_hero_linemask_f32.bin",
            "Build/Design/36/palette/prep/ds36_sea_ramp_256_rgba8.bin" };

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        class Ctx
        {
            public GameObject ctx;
            public DS30SheetPlayer hero, near, far;
            public List<DS30SheetPlayer> sheets = new List<DS30SheetPlayer>();
            public DS30SinglePlayback play;
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public Dictionary<string, DS37HeadSway> sway = new Dictionary<string, DS37HeadSway>();
            public DS34ClawPlayer claws; public MeshRenderer clawR;
            public DS38ClawOutline clawLine;
            public List<DS38SheetOutline> lineComps = new List<DS38SheetOutline>();
            public DS34LayerSet layers;
            public DS31InstancedParticles spray, dense;
            public DS36ClawPalette pal;
            public DS36SeaPalette seaPal;
            public DS38LineGlobals globals;
            public DS39PaperLayers paper;
            public Material coordMat;
        }

        [Serializable] class ImgRec { public string view, cond, path; public float t, dx, gain; }
        [Serializable] class VideoRec { public string name, view, path, sha256, ffmpegError, cond; public int frames, fps; public float seconds, gain; }
        [Serializable] class Report
        {
            public string unity, device, graphicsApi, colorSpace, utc, scene39, scene39Sha256, noteJa;
            public float paperAmp, muraAmp, skyRadius, swimGain, sway, swayPeriod;
            public DS39PaperLayers.SheetRest[] rest; public DS39PaperLayers.MeshTarget[] meshTargets;
            public int sprayBase, sprayDense; public string sprayDenseSha256;
            public string[] t28Files; public ImgRec[] images; public ImgRec[] swim; public VideoRec[] videos;
            public string swimLayoutJa;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
            public float secondsTotal;
        }

        static Material MatAsset(string name, string shader)
        {
            var sh = Shader.Find(shader);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + shader);
            var path = MatDir + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
            m.shader = sh; m.enableInstancing = true;
            EditorUtility.SetDirty(m);
            return m;
        }

        // 設計38 の場面を開き、紙の部品を足して DS39_Paper.unity に保存する（全部切）。save = false なら保存しない。
        static Ctx OpenAndSetup(bool save, Report rep)
        {
            EditorSceneManager.OpenScene(Scene38, OpenSceneMode.Single);
            var scene = EditorSceneManager.GetActiveScene();
            var roots = scene.GetRootGameObjects();
            var c = new Ctx { ctx = roots.First(g => g.name == ContextRootName) };
            c.play = roots.Select(g => g.GetComponentInChildren<DS30SinglePlayback>(true)).First(x => x != null);
            c.sheets = c.play.sheets.Where(s => s != null).ToList();
            c.hero = c.sheets.First(s => s.sheetName == "hero");
            c.near = c.sheets.FirstOrDefault(s => s.sheetName == "near");
            c.far = c.sheets.FirstOrDefault(s => s.sheetName == "far");
            var camRoot = GameObject.Find(CamRoot).transform;
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            var stwT = camRoot.Find("DS30 seat_toward_wave");
            if (stwT != null) c.cams["seat_toward_wave"] = stwT.GetComponent<Camera>();
            foreach (var kv in c.cams) { var hs = kv.Value.GetComponent<DS37HeadSway>(); if (hs != null) c.sway[kv.Key] = hs; }
            c.claws = roots.Select(g => g.GetComponentInChildren<DS34ClawPlayer>(true)).First(x => x != null);
            c.clawR = c.claws.GetComponent<MeshRenderer>();
            c.layers = roots.Select(g => g.GetComponentInChildren<DS34LayerSet>(true)).First(x => x != null);
            c.spray = roots.SelectMany(g => g.GetComponentsInChildren<DS31InstancedParticles>(true)).First(p => p.name == "DS31 spray");
            c.pal = c.claws.GetComponent<DS36ClawPalette>();
            c.seaPal = roots.Select(g => g.GetComponentInChildren<DS36SeaPalette>(true)).First(x => x != null);
            c.clawLine = c.claws.GetComponent<DS38ClawOutline>();
            c.globals = c.play.GetComponent<DS38LineGlobals>();
            foreach (var s in c.sheets) { var so = s.GetComponent<DS38SheetOutline>(); if (so != null) c.lineComps.Add(so); }
            if (c.clawLine == null || c.globals == null || c.lineComps.Count == 0) throw new InvalidOperationException("設計38 の線の部品がありません");

            // ---- 設計39 の部品
            if (!AssetDatabase.IsValidFolder(MatDir)) AssetDatabase.CreateFolder("Assets/GreatWave/Design39", "Materials");
            var mPK = MatAsset("DS39_Paper_Keypose", KeyShader); mPK.SetFloat("_DS39Mode", 0);
            var mMK = MatAsset("DS39_Mura_Keypose", KeyShader); mMK.SetFloat("_DS39Mode", 1);
            var mPM = MatAsset("DS39_Paper_Mesh", MeshShader); mPM.SetFloat("_DS39Mode", 0);
            var mMM = MatAsset("DS39_Mura_Mesh", MeshShader); mMM.SetFloat("_DS39Mode", 1);
            AssetDatabase.SaveAssets();
            var go = new GameObject("DS39 紙・摺り・小飛沫（既定は全部切）");
            c.paper = go.AddComponent<DS39PaperLayers>();
            c.paper.playback = c.play;
            c.paper.paperKeypose = mPK; c.paper.muraKeypose = mMK; c.paper.paperMesh = mPM; c.paper.muraMesh = mMM;
            c.paper.skyDomeName = SkyDomeName;
            c.paper.paperOn = c.paper.muraOn = c.paper.sprayOn = false;
            var dgo = new GameObject("DS39 spray dense");
            dgo.transform.SetParent(c.spray.transform.parent, false);
            c.dense = dgo.AddComponent<DS31InstancedParticles>();
            c.dense.dataPath = DenseData;
            c.dense.colourFromJson = c.spray.colourFromJson; c.dense.colour = c.spray.colour; c.dense.subdivisions = c.spray.subdivisions;
            c.dense.clock = c.spray.clock; c.dense.drawInPlayMode = false; c.dense.verifySha256 = true;
            c.paper.denseSpray = c.dense;
            if (save)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(Scene39));
                if (!EditorSceneManager.SaveScene(scene, Scene39, true)) throw new InvalidOperationException("場面を保存できません: " + Scene39);
                if (rep != null) { rep.scene39 = Scene39; rep.scene39Sha256 = Sha(Scene39); }
            }
            return c;
        }

        // 設計38 の DS38Render.Render の描画の前の準備と同じ（部品は場面に保存済み）
        static void Prepare(Ctx c)
        {
            foreach (var so in c.lineComps) so.Attach();
            c.clawLine.Attach();
            c.globals.Apply();
            c.play.Prepare();
            c.spray.Load(); c.claws.Load(); c.dense.Load();
            var hp = c.seaPal.SyncFromHero();
            c.pal.white = hp[0]; c.pal.mizuiro = hp[1]; c.pal.aiMid = hp[2]; c.pal.aiDark = hp[3];
            c.pal.Apply();
            foreach (var so in c.lineComps) so.BindMask();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS38LineCoordMode", 0);
            Shader.SetGlobalVector("_DS38EyeOverride", Vector4.zero);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
            Shader.SetGlobalFloat("_DS34ClawDiag", 0);
            Shader.SetGlobalFloat("_DS36ClawFaceDiag", 0);
            Shader.SetGlobalFloat("_DS39Gain", 0);
            c.paper.Build();
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string od = Arg(a, "-ds39Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/39/paper/unity";
            var skip = new HashSet<string>((Arg(a, "-ds39Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), utc = DateTime.UtcNow.ToString("O"), swimGain = SwimGain, sway = Sway, swayPeriod = SwayPeriod,
                swimLayoutJa = "swim_*_coord.bin：float32 × 2 × W × H（画素ごとに R = 列 + 2000 × シートの番号（1 主役波・2 near・3 far・4 爪）、G = 行。背景は 0。行は上から）"
            };
            var c = OpenAndSetup(!skip.Contains("scene"), rep);
            var imgs = new List<ImgRec>(); var swim = new List<ImgRec>(); var vids = new List<VideoRec>();
            try
            {
                Prepare(c);
                rep.paperAmp = c.paper.paperAmp; rep.muraAmp = c.paper.muraAmp; rep.skyRadius = c.paper.skyRadius;
                rep.rest = c.paper.Rest.ToArray(); rep.meshTargets = c.paper.MeshTargets.ToArray();
                rep.sprayBase = c.spray.Count; rep.sprayDense = c.dense.Count; rep.sprayDenseSha256 = c.dense.DataSha256;
                var sh = Shader.Find(CoordShaderName);
                c.coordMat = new Material(sh) { hideFlags = HideFlags.DontSave };

                if (!skip.Contains("t28"))
                {
                    var f = new List<string>();
                    Set(c, false, false, false);
                    Seek(c, TStar, true, false, false);
                    f.AddRange(RenderT28(c, od + "/t28_white/t28/render"));
                    Seek(c, TStar, true, true, false);
                    f.AddRange(RenderT28(c, od + "/t28_claws/t28/render"));
                    rep.t28Files = f.ToArray();
                }
                var conds = new (string name, bool p, bool m, bool s)[] { ("off", false, false, false), ("paper", true, false, false), ("mura", false, true, false), ("spray", false, false, true), ("all", true, true, true) };
                if (!skip.Contains("onoff"))
                {
                    foreach (var (view, t) in new[] { ("painting", 12.0), ("seat", 12.0), ("seat_toward_wave", 10.5), ("seat_low", 12.0) })
                        foreach (var cd in conds)
                        {
                            Set(c, cd.p, cd.m, cd.s);
                            Seek(c, t, true, true, true);
                            var path = od + "/onoff/ds39_" + view + "_t" + ((int)Math.Round(t * 10)).ToString("000") + "_" + cd.name + ".png";
                            CaptureWithSpray(c, view, path, cd.s);
                            imgs.Add(new ImgRec { view = view, cond = cd.name, path = path, t = (float)t, gain = 1 });
                        }
                    Set(c, false, false, false);
                }
                if (!skip.Contains("swim"))
                {
                    foreach (var (view, t) in new[] { ("seat_toward_wave", 9.0), ("seat", 12.0) })
                    {
                        Seek(c, t, true, true, false);
                        foreach (var dx in new[] { -0.1f, -0.05f, 0f, 0.05f, 0.1f })
                        {
                            SetSway(c, view, dx);
                            string tag = view + "_t" + ((int)Math.Round(t * 10)).ToString("000") + "_dx" + ((int)Math.Round(dx * 1000)).ToString("+000;-000;+000");
                            foreach (var (cond, p, m, g) in new[] { ("off", false, false, 0f), ("paper", true, false, SwimGain), ("mura", false, true, SwimGain) })
                            {
                                Set(c, p, m, false);
                                Shader.SetGlobalFloat("_DS39Gain", g);
                                var path = od + "/swim/swim_" + tag + "_" + cond + ".png";
                                CaptureWithSpray(c, view, path, false);
                                swim.Add(new ImgRec { view = view, cond = cond, path = path, t = (float)t, dx = dx, gain = g > 0 ? g : 1 });
                            }
                            Shader.SetGlobalFloat("_DS39Gain", 0);
                            Set(c, false, false, false);
                            var cp = od + "/swim/swim_" + tag + "_coord.bin";
                            var hid = HideFor(c, view);
                            try { File.WriteAllBytes(cp, SurfaceCoordBytes(c, c.cams[view], W, H)); } finally { foreach (var r in hid) r.enabled = true; }
                            swim.Add(new ImgRec { view = view, cond = "coord", path = cp, t = (float)t, dx = dx, gain = 0 });
                        }
                        SetSway(c, view, 0f);
                    }
                }
                if (!skip.Contains("video"))
                {
                    Directory.CreateDirectory(od + "/video");
                    int nS = 4 * Fps + 1, nF = Mathf.RoundToInt(TEnd * Fps) + 1;
                    vids.Add(Video(c, "sway_seat_toward_wave_t09_all", "seat_toward_wave", nS, i => 9.0, i => SwayAt(i / (double)Fps), od, true, true, true, 0f));
                    vids.Add(Video(c, "sway_seat_tstar_all", "seat", nS, i => TStar, i => SwayAt(i / (double)Fps), od, true, true, true, 0f));
                    vids.Add(Video(c, "sway_seat_toward_wave_t09_paper_mura_gain6", "seat_toward_wave", nS, i => 9.0, i => SwayAt(i / (double)Fps), od, true, true, false, SwimGain));
                    vids.Add(Video(c, "formation_seat_all", "seat", nF, i => i / (double)Fps, i => 0f, od, true, true, true, 0f));
                    vids.Add(Video(c, "formation_painting_all", "painting", nF, i => i / (double)Fps, i => 0f, od, true, true, true, 0f));
                }
            }
            finally
            {
                foreach (var s in c.sway.Values) s.Restore();
                Shader.SetGlobalFloat("_DS39Gain", 0);
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                c.paper.Teardown();
                foreach (var so in c.lineComps) so.ReleaseMask();
                foreach (var s in c.play.sheets) s.Release();
                c.spray.Release(); c.dense.Release(); c.pal.Release(); c.clawLine.Release(); c.claws.Release();
                if (c.coordMat != null) UnityEngine.Object.DestroyImmediate(c.coordMat);
            }
            rep.images = imgs.ToArray(); rep.swim = swim.ToArray(); rep.videos = vids.ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render）。HMD 実機ではない。頭の揺れは座席のカメラを右の向きへずらした描画（設計37 の DS37HeadSway）。";
            File.WriteAllText(od + "/ds39_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS39_RENDER_DONE seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static float SwayAt(double t) => Sway * Mathf.Sin((float)(2.0 * Math.PI * t / SwayPeriod));

        static void Set(Ctx c, bool paper, bool mura, bool spray) => c.paper.Set(paper, mura, spray);

        static void Seek(Ctx c, double t, bool white, bool claws, bool spray)
        {
            c.play.Seek(t);
            c.spray.ApplyT(t);
            c.dense.ApplyT(t);
            c.claws.ApplyT(t);
            c.layers.whiteBand = white; c.layers.clawsOn = claws; c.layers.sprayOn = spray;
            c.layers.ApplyToggles();
            c.clawLine.Sync();
            c.paper.Apply();
        }

        static void SetLines(Ctx c, bool on)
        {
            foreach (var s in c.sheets) if (s.outline != null) s.outline.enabled = on;
            if (c.clawLine.Line != null) c.clawLine.Line.enabled = on && c.clawR.enabled;
        }

        static List<Renderer> HideFor(Ctx c, string view)
        {
            var hid = new List<Renderer>();
            if (view != "side_left" && view != "seat_toward_wave") return hid;
            foreach (var rr in c.ctx.GetComponentsInChildren<Renderer>(false))
            {
                if (!rr.enabled || rr.name == SkyDomeName || rr.name == FlatSeaName) continue;
                if (rr.transform.parent != null && (rr.transform.parent.name == SkyDomeName || rr.transform.parent.name == FlatSeaName)) continue;   // 空・平らな海の紙の子は残す
                rr.enabled = false; hid.Add(rr);
            }
            return hid;
        }

        static void SetSway(Ctx c, string view, float dx)
        {
            if (!c.sway.TryGetValue(view, out var s)) { if (Mathf.Abs(dx) > 0) throw new InvalidOperationException("揺れの部品がない視点: " + view); return; }
            if (Mathf.Abs(dx) > 0) s.Apply(dx); else s.Restore();
        }

        // 設計38 の RenderT28 と同じ手順（全部切で描く）
        static List<string> RenderT28(Ctx c, string d28)
        {
            var f = new List<string>();
            Directory.CreateDirectory(d28);
            try
            {
                SetLines(c, true);
                foreach (var v in new[] { "painting", "seat", "seat_low" }) f.Add(Capture(c.cams[v], W, H, true, d28 + "/af28r01_" + v + ".png"));
                c.ctx.SetActive(false);
                SetLines(c, false);
                f.Add(Capture(c.cams["painting"], W, H, true, d28 + "/af28r01_painting_kstar.png"));
                f.Add(Capture(c.cams["seat"], W, H, true, d28 + "/af28r01_seat_kstar.png"));
                f.Add(Capture(c.cams["seat_low"], W, H, true, d28 + "/af28r01_seat_low_kstar.png"));
                Shader.SetGlobalFloat("_AF28IdMode", 1);
                f.Add(Capture(c.cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_class_ids.png"));
                f.Add(Capture(c.cams["seat"], W, H, false, d28 + "/af28r01_seat_class_ids.png"));
                f.Add(Capture(c.cams["seat_low"], W, H, false, d28 + "/af28r01_seat_low_class_ids.png"));
                SetLines(c, true);
                f.Add(Capture(c.cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_line_ids.png"));
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                c.ctx.SetActive(true);
                SetLines(c, true);
            }
            return f;
        }

        static void CaptureWithSpray(Ctx c, string view, string path, bool dense)
        {
            var cam = c.cams[view];
            var cb = new CommandBuffer { name = "DS39 飛沫" };
            c.spray.AddTo(cb);
            if (dense) c.dense.AddTo(cb);
            var hid = HideFor(c, view);
            cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            try { Capture(cam, W, H, true, path); }
            finally
            {
                cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cb.Release();
                foreach (var r in hid) r.enabled = true;
            }
        }

        static byte[] SurfaceCoordBytes(Ctx c, Camera cam, int w, int h)
        {
            var saved = new List<(Renderer r, Material[] m)>();
            var mpb = new MaterialPropertyBlock();
            var lines = new List<(Renderer r, bool e)>();
            foreach (var s in c.sheets) if (s.outline != null) lines.Add((s.outline, s.outline.enabled));
            if (c.clawLine.Line != null) lines.Add((c.clawLine.Line, c.clawLine.Line.enabled));
            var clawMats = c.clawR.sharedMaterials;
            try
            {
                foreach (var s in c.sheets)
                {
                    var r = s.Surface;
                    int id = s == c.hero ? 1 : (s == c.near ? 2 : (s == c.far ? 3 : 0));
                    saved.Add((r, r.sharedMaterials));
                    r.sharedMaterials = new[] { c.coordMat };
                    r.GetPropertyBlock(mpb); mpb.SetFloat("_DS37SheetId", id); r.SetPropertyBlock(mpb);
                }
                if (c.clawR.enabled)
                {
                    var cm = new Material[clawMats.Length];
                    for (int i = 0; i < cm.Length; i++) cm[i] = c.coordMat;
                    c.clawR.sharedMaterials = cm;
                    c.clawR.GetPropertyBlock(mpb); mpb.SetFloat("_DS37SheetId", 4); c.clawR.SetPropertyBlock(mpb);
                }
                foreach (var (r, _) in lines) r.enabled = false;
                var f = RenderFloat(cam, w, h);
                var o = new float[w * h * 2];
                for (int y = 0; y < h; y++) { int src = (h - 1 - y) * w; for (int x = 0; x < w; x++) { o[2 * (y * w + x)] = f[4 * (src + x)]; o[2 * (y * w + x) + 1] = f[4 * (src + x) + 1]; } }
                var b = new byte[o.Length * 4];
                Buffer.BlockCopy(o, 0, b, 0, b.Length);
                return b;
            }
            finally
            {
                foreach (var (r, m) in saved) r.sharedMaterials = m;
                c.clawR.sharedMaterials = clawMats;
                foreach (var (r, e) in lines) r.enabled = e;
            }
        }

        static float[] RenderFloat(Camera cam, int w, int h)
        {
            var clear = cam.clearFlags; var bg = cam.backgroundColor; bool hdr = cam.allowHDR, aa = cam.allowMSAA;
            var prev = cam.targetTexture; float asp = cam.aspect;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGBFloat, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
            rt.Create();
            var tex = new Texture2D(w, h, TextureFormat.RGBAFloat, false, true);
            try
            {
                cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0, 0, 0, 0);
                cam.allowHDR = false; cam.allowMSAA = false; cam.aspect = (float)w / h; cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                RenderTexture.active = null;
                return tex.GetRawTextureData<float>().ToArray();
            }
            finally
            {
                RenderTexture.active = null;
                cam.targetTexture = prev; cam.aspect = asp; cam.clearFlags = clear; cam.backgroundColor = bg; cam.allowHDR = hdr; cam.allowMSAA = aa;
                UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            }
        }

        static VideoRec Video(Ctx c, string name, string view, int n, Func<int, double> tOf, Func<int, float> dxOf, string od, bool paper, bool mura, bool spray, float gain)
        {
            var sw = Stopwatch.StartNew();
            var mp4 = od + "/video/ds39_" + name + "_30fps.mp4";
            var camera = c.cams[view];
            string outs = string.Format("-vf vflip -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart \"{0}\"", Path.GetFullPath(mp4));
            var psi = new ProcessStartInfo
            {
                FileName = Ffmpeg,
                Arguments = string.Format("-y -loglevel error -f rawvideo -pix_fmt rgb24 -s {0}x{1} -r {2} -i - {3}", W, H, Fps, outs),
                UseShellExecute = false, RedirectStandardInput = true, RedirectStandardError = true, CreateNoWindow = true
            };
            var sb = new StringBuilder();
            var hid = HideFor(c, view);
            CommandBuffer cb = null;
            string err;
            try
            {
                Set(c, paper, mura, spray);
                Shader.SetGlobalFloat("_DS39Gain", gain);
                Seek(c, tOf(0), true, true, true);
                cb = new CommandBuffer { name = "DS39 飛沫" };
                c.spray.AddTo(cb);
                if (spray) c.dense.AddTo(cb);
                camera.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
                using (var p = new Process { StartInfo = psi })
                {
                    p.ErrorDataReceived += (s, e) => { if (e.Data != null) lock (sb) sb.AppendLine(e.Data); };
                    p.Start();
                    p.BeginErrorReadLine();
                    var stdin = p.StandardInput.BaseStream;
                    var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
                    var res = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                    rt.Create(); res.Create();
                    var tex = new Texture2D(W, H, TextureFormat.RGB24, false, false);
                    var clear = camera.clearFlags; var bg = camera.backgroundColor; var prev = camera.targetTexture; float asp = camera.aspect;
                    camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = SkyTop; camera.allowHDR = false; camera.allowMSAA = true;
                    camera.aspect = (float)W / H;
                    try
                    {
                        for (int i = 0; i < n; i++)
                        {
                            SetSway(c, view, 0f);
                            Seek(c, tOf(i), true, true, true);
                            SetSway(c, view, dxOf(i));
                            camera.targetTexture = rt;
                            camera.Render();
                            Graphics.Blit(rt, res);
                            RenderTexture.active = res;
                            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
                            RenderTexture.active = null;
                            var raw = tex.GetRawTextureData();
                            stdin.Write(raw, 0, raw.Length);
                        }
                    }
                    finally
                    {
                        SetSway(c, view, 0f);
                        stdin.Flush(); stdin.Close();
                        camera.targetTexture = prev; camera.clearFlags = clear; camera.backgroundColor = bg; camera.aspect = asp;
                        UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
                        UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
                    }
                    if (!p.WaitForExit(10 * 60 * 1000)) { p.Kill(); throw new InvalidOperationException("ffmpeg が終わりません。"); }
                    p.WaitForExit();
                    lock (sb) err = sb.ToString() + (p.ExitCode != 0 ? " exit=" + p.ExitCode : "");
                }
            }
            finally
            {
                if (cb != null) { camera.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cb.Release(); }
                foreach (var r in hid) r.enabled = true;
                Shader.SetGlobalFloat("_DS39Gain", 0);
                Set(c, false, false, false);
            }
            if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
            return new VideoRec { name = name, view = view, path = Path.GetFullPath(mp4), frames = n, fps = Fps, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = Sha(mp4),
                cond = (paper ? "①" : "") + (mura ? "②" : "") + (spray ? "③" : ""), gain = gain > 0 ? gain : 1 };
        }

        static string Capture(Camera camera, int w, int h, bool colour, string path)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture; float asp = camera.aspect;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = colour ? (Color)SkyTop : IdSky;
            camera.allowHDR = false; camera.allowMSAA = colour;
            var rw = colour ? RenderTextureReadWrite.sRGB : RenderTextureReadWrite.Linear;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, rw) { antiAliasing = colour ? 8 : 1 };
            var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, rw);
            rt.Create(); res.Create();
            camera.aspect = (float)w / h; camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, !colour);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev; camera.aspect = asp;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return path;
        }

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        // ---- GPU 時間の計測器のプレイヤー（美術優先32・設計35 と同じ Release、BuildOptions.None）
        [Serializable] class BuildReportJ
        {
            public string unity, utc, scene, scenePerfSha256, playerPath, buildResult, buildOptions;
            public bool frameTimingStatsBefore, frameTimingStatsDuringBuild, frameTimingStatsRestored, protectedUnchanged;
            public long totalSize; public double buildSeconds; public string[] buildErrors, changedProtected;
        }

        public static void BuildPerf()
        {
            var rep = new BuildReportJ { unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePerf };
            var before = Protected.ToDictionary(p => p, Sha);
            if (!File.Exists(Scene39)) throw new InvalidOperationException("先に Render で DS39_Paper.unity を作ること");
            AssetDatabase.Refresh();
            if (File.Exists(ScenePerf)) AssetDatabase.DeleteAsset(ScenePerf);
            if (!AssetDatabase.CopyAsset(Scene39, ScenePerf)) throw new InvalidOperationException("場面を複製できません");
            var scene = EditorSceneManager.OpenScene(ScenePerf, OpenSceneMode.Single);
            var go = new GameObject("DS39 計測器（紙・摺り・小飛沫の入切の GPU 時間、美術優先32 の測り方）");
            var run = go.AddComponent<DS39PerfRunner>();
            var keep = new List<Material>();
            foreach (var p in new[] { "Assets/GreatWave/Design35/Materials/DS35_Keep_ClawUnlit.mat", "Assets/GreatWave/Design35/Materials/DS35_Keep_SprayUnlit.mat" })
            { var m = AssetDatabase.LoadAssetAtPath<Material>(p); if (m != null) keep.Add(m); }
            run.keepShaders = keep.ToArray();
            var play = UnityEngine.Object.FindAnyObjectByType<DS30SinglePlayback>(FindObjectsInactive.Include);
            play.enabled = false;
            var layers = UnityEngine.Object.FindAnyObjectByType<DS34LayerSet>(FindObjectsInactive.Include);
            if (layers != null) layers.keyboardToggles = false;
            foreach (var hs in UnityEngine.Object.FindObjectsByType<DS37HeadSway>(FindObjectsInactive.Include, FindObjectsSortMode.None)) hs.swayInPlayMode = false;
            if (!EditorSceneManager.SaveScene(scene)) throw new InvalidOperationException("場面を保存できません");
            rep.scenePerfSha256 = Sha(ScenePerf);
            bool prev = PlayerSettings.enableFrameTimingStats;
            rep.frameTimingStatsBefore = prev;
            var playerDir = Path.GetDirectoryName(PlayerPath);
            if (Directory.Exists(playerDir)) Directory.Delete(playerDir, true);
            Directory.CreateDirectory(playerDir);
            BuildReport br;
            try
            {
                PlayerSettings.enableFrameTimingStats = true;
                rep.frameTimingStatsDuringBuild = PlayerSettings.enableFrameTimingStats;
                var opts = new BuildPlayerOptions { scenes = new[] { ScenePerf }, locationPathName = PlayerPath, target = BuildTarget.StandaloneWindows64, targetGroup = BuildTargetGroup.Standalone, options = BuildOptions.None };
                rep.buildOptions = opts.options.ToString();
                br = BuildPipeline.BuildPlayer(opts);
            }
            finally
            {
                PlayerSettings.enableFrameTimingStats = prev;
                AssetDatabase.SaveAssets();
                rep.frameTimingStatsRestored = PlayerSettings.enableFrameTimingStats == prev;
            }
            rep.playerPath = Path.GetFullPath(PlayerPath);
            rep.buildResult = br.summary.result.ToString();
            rep.totalSize = (long)br.summary.totalSize;
            rep.buildSeconds = br.summary.totalTime.TotalSeconds;
            rep.buildErrors = br.steps.SelectMany(s => s.messages).Where(m => m.type == LogType.Error || m.type == LogType.Exception).Select(m => m.content).ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.changedProtected = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.protectedUnchanged = rep.changedProtected.Length == 0;
            Directory.CreateDirectory("Build/Design/39/paper");
            File.WriteAllText("Build/Design/39/paper/ds39_build_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS39_BUILD result=" + rep.buildResult + " seconds=" + rep.buildSeconds);
            if (br.summary.result != BuildResult.Succeeded) throw new InvalidOperationException("ビルドに失敗: " + string.Join(" | ", rep.buildErrors));
        }
    }
}
