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
using GreatWave.Design36;
using GreatWave.Design37;
using GreatWave.Design38;
using GreatWave.Design39;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design40.EditorTools
{
    // 設計40 第「比較」部 Unity：段階7（設計36〜39）までを入れた場面 DS39_Paper.unity を読むだけで開き（保存しない）、
    // t*（t = 12 s）の原画視点・座席 v1・側面・背面を描く（PC オフスクリーン描画、HMD ではない）。
    //   t28.   設計38・39 と同じ t* の画像の組（t28_claws・t28_white。評価器 ds30b_tstar_regress.py の入力）。紙・摺り・小飛沫は切。
    //   full.  原画視点の作品のままの色画像（白・爪・飛沫・線。紙の 3 層は切＝評価の状態、全部入＝記録）と、
    //          美術優先23 の評価器（Tools/PaintingTruth/evaluate.py）の ID モード用の全体の ID 画像（3840×2160、MSAA なし、線なし・線あり）。
    //          ID：空（空のドームとカメラの背景）(0,255,255)、船 boat_left (102,0,0)・boat_mid (0,102,0)・boat_fg (102,102,0)、ほかは other。
    //          keypose のシート・爪・線は材質を替えずに大域の _AF28IdMode = 1 で色区の ID（白 赤、水色 緑、藍中 青、藍濃 黄、線 マゼンタ）で描く
    //          （評価器では other）。CPU のメッシュ（空・船・富士・平らな海・継ぎ目の幕など）は AF24 ID Flat に一時的に替える。飛沫は ID に入れない。
    //   views. 座席 v1（seat）・唇を見上げる座席（seat_low）・座席から波の方向（seat_toward_wave）・左の側面（side_left）・背面（back、
    //          美術優先28修正01・CP1 と同じ位置 (−45, 30, 60) → (−5, 8, −3)、縦画角 50°。この描画の間だけの一時のカメラ）× {切, 全部入}。
    //          側面・背面は、背景の船・富士・仮置きを隠した「波だけ」も描く（CP1 と同じ確認図）。
    //   mock.  座席 v1・seat_low の Mock の両眼（座席のカメラを右の向きへ ±0.032 m。DS37HeadSway）。PS VR2 の SPI ではない。
    // 場面・スクリプト・シェーダー・材質は変えない（守るファイルの SHA-256 を前後で比べる）。
    public static class DS40Render
    {
        const string Scene39 = "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム", FujiName = "AF27 富士";
        const int W = 1920, H = 1080;
        const float TStar = 12f, MockHalf = 0.032f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Vector3 BackPosition = new Vector3(-45, 30, 60), BackTarget = new Vector3(-5, 8, -3);
        const float BackFov = 50;
        static readonly Vector4 IdSkyV = new Vector4(0, 1, 1, 1), IdOtherV = new Vector4(0, 0, 0, 1);
        static readonly Dictionary<string, Vector4> IdBoats = new Dictionary<string, Vector4> {
            { "boat_left", new Vector4(0.4f, 0, 0, 1) }, { "boat_mid", new Vector4(0, 0.4f, 0, 1) }, { "boat_fg", new Vector4(0.4f, 0.4f, 0, 1) } };

        static string[] Protected => new[] {
            Scene39, "Assets/GreatWave/Design39/Scenes/DS39_Perf.unity", "Assets/GreatWave/Design38/Scenes/DS38_Outlines.unity",
            "Assets/GreatWave/Design39/Editor/DS39Render.cs", "Assets/GreatWave/Design39/Scripts/DS39PaperLayers.cs",
            "Assets/GreatWave/Design39/Shaders/DS39_Paper_Keypose.shader", "Assets/GreatWave/Design39/Shaders/DS39_Paper_Mesh.shader",
            "Assets/GreatWave/Design39/Materials/DS39_Paper_Keypose.mat", "Assets/GreatWave/Design39/Materials/DS39_Mura_Keypose.mat",
            "Assets/GreatWave/Design39/Materials/DS39_Paper_Mesh.mat", "Assets/GreatWave/Design39/Materials/DS39_Mura_Mesh.mat",
            "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs", "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs",
            "Assets/GreatWave/Design31/Scripts/DS31InstancedParticles.cs", "Assets/GreatWave/Design31/Shaders/DS31_Spray_Unlit.shader",
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design36/Shaders/DS36_Claw_Palette.shader",
            "Assets/GreatWave/Design38/Shaders/DS38_Outline_Keypose.shader", "Assets/GreatWave/Design38/Shaders/DS38_Outline_Mesh.shader",
            "Assets/GreatWave/Design38/Materials/DS38_Outline_hero.mat", "Assets/GreatWave/Design38/Materials/DS38_Outline_near.mat",
            "Assets/GreatWave/Design38/Materials/DS38_Outline_claws.mat", "Assets/GreatWave/ArtFirst/Shaders/AF24IdFlat.shader",
            "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab",
            "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin", "Build/Design/33/claws/ds33_claw_frames_f32.bin",
            "Build/Design/31/spray/ds31_spray_frames.bin", "Build/Design/38/outlines/unity/prep/ds38_hero_linemask_f32.bin",
            "Build/Design/36/palette/prep/ds36_sea_ramp_256_rgba8.bin", "Build/Design/39/paper/spray/ds39_spray_dense_frames.json" };

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        class Ctx
        {
            public GameObject ctx;
            public DS30SinglePlayback play;
            public List<DS30SheetPlayer> sheets = new List<DS30SheetPlayer>();
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
            public GameObject backGo;
        }

        [Serializable] class ImgRec { public string view, cond, path, sha256; public float t, dx; }
        [Serializable] class CamRec { public string view; public Vector3 position, euler; public float fov, near, far; public float[] worldToCamera, projection; }
        [Serializable] class ObjRec { public string name; public bool active; public Vector3 position, boundsCenter, boundsMin, boundsMax; public int renderers; }
        [Serializable] class IdRec { public string renderer, shader, decision; }
        [Serializable] class Report
        {
            public string unity, device, graphicsApi, colorSpace, utc, scene, sceneSha256, noteJa, idLegendJa;
            public string[] t28Files; public ImgRec[] images; public CamRec[] cameras; public ObjRec[] objects; public IdRec[] idDecisions;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
            public float secondsTotal;
        }

        static Ctx Open()
        {
            EditorSceneManager.OpenScene(Scene39, OpenSceneMode.Single);
            var roots = EditorSceneManager.GetActiveScene().GetRootGameObjects();
            var c = new Ctx { ctx = roots.First(g => g.name == ContextRootName) };
            c.play = roots.Select(g => g.GetComponentInChildren<DS30SinglePlayback>(true)).First(x => x != null);
            c.sheets = c.play.sheets.Where(s => s != null).ToList();
            var camRoot = GameObject.Find(CamRoot).transform;
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            c.cams["seat_toward_wave"] = camRoot.Find("DS30 seat_toward_wave").GetComponent<Camera>();
            foreach (var kv in c.cams) { var hs = kv.Value.GetComponent<DS37HeadSway>(); if (hs != null) c.sway[kv.Key] = hs; }
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
            if (c.clawLine == null || c.globals == null || c.lineComps.Count == 0 || c.paper == null) throw new InvalidOperationException("設計38・39 の部品がありません");
            // 背面：美術優先28修正01・CP1 と同じ位置（この描画の間だけ。場面は保存しない）
            c.backGo = new GameObject("DS40 背面カメラ（一時）") { hideFlags = HideFlags.DontSave };
            var bc = c.backGo.AddComponent<Camera>();
            bc.CopyFrom(c.cams["painting"]);
            bc.enabled = false;
            c.backGo.transform.position = BackPosition;
            c.backGo.transform.LookAt(BackTarget, Vector3.up);
            bc.fieldOfView = BackFov;
            c.cams["back"] = bc;
            return c;
        }

        // 設計39 の DS39Render.Prepare と同じ（部品は場面に保存済み）
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
            string od = Arg(a, "-ds40Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/40/compare/unity";
            var skip = new HashSet<string>((Arg(a, "-ds40Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), utc = DateTime.UtcNow.ToString("O"), scene = Scene39, sceneSha256 = Sha(Scene39),
                idLegendJa = "full/ids_*.png（3840×2160、線形、MSAA なし）：空 (0,255,255)、boat_left (102,0,0)、boat_mid (0,102,0)、boat_fg (102,102,0)。" +
                             "keypose のシート・爪は _AF28IdMode の色区 ID（白 (255,0,0)・水色 (0,255,0)・藍中 (0,0,255)・藍濃 (255,255,0)）、線 (255,0,255)、CPU のメッシュの other (0,0,0)。飛沫は入れない。"
            };
            var c = Open();
            var imgs = new List<ImgRec>(); var ids = new List<IdRec>();
            try
            {
                Prepare(c);
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
                if (!skip.Contains("full"))
                {
                    foreach (var (cond, on) in new[] { ("off", false), ("all", true) })
                    {
                        Set(c, on, on, on);
                        Seek(c, TStar, true, true, true);
                        var p = od + "/full/painting_t120_" + cond + ".png";
                        CaptureWithSpray(c, "painting", p, on, false);
                        imgs.Add(Rec("painting", cond, p, TStar, 0));
                    }
                    // 評価器の ID（作品のまま：白・爪あり、紙の 3 層は切、飛沫なし）
                    Set(c, false, false, false);
                    Seek(c, TStar, true, true, false);
                    var p1 = od + "/full/ids_noline.png"; RenderIdsFull(c, c.cams["painting"], p1, false, ids); imgs.Add(Rec("painting", "ids_noline", p1, TStar, 0));
                    var p2 = od + "/full/ids_line.png"; RenderIdsFull(c, c.cams["painting"], p2, true, null); imgs.Add(Rec("painting", "ids_line", p2, TStar, 0));
                    // 爪なし（段階5 の状態に近い、記録）
                    Seek(c, TStar, true, false, false);
                    var p3 = od + "/full/ids_line_noclaws.png"; RenderIdsFull(c, c.cams["painting"], p3, true, null); imgs.Add(Rec("painting", "ids_line_noclaws", p3, TStar, 0));
                    var p4 = od + "/full/ids_noline_noclaws.png"; RenderIdsFull(c, c.cams["painting"], p4, false, null); imgs.Add(Rec("painting", "ids_noline_noclaws", p4, TStar, 0));
                    SetLines(c, true);
                }
                if (!skip.Contains("views"))
                {
                    foreach (var (view, t) in new[] { ("seat", 12.0), ("seat_low", 12.0), ("seat_toward_wave", 12.0), ("seat_toward_wave", 10.5), ("side_left", 12.0), ("back", 12.0) })
                        foreach (var (cond, on) in new[] { ("off", false), ("all", true) })
                        {
                            Set(c, on, on, on);
                            Seek(c, t, true, true, true);
                            var p = od + "/views/" + view + "_t" + ((int)Math.Round(t * 10)).ToString("000") + "_" + cond + ".png";
                            CaptureWithSpray(c, view, p, on, false);
                            imgs.Add(Rec(view, cond, p, (float)t, 0));
                        }
                    Set(c, false, false, false);
                    Seek(c, TStar, true, true, true);
                    foreach (var view in new[] { "side_left", "back" })
                    {
                        var p = od + "/views/" + view + "_t120_off_waveonly.png";
                        CaptureWithSpray(c, view, p, false, true);
                        imgs.Add(Rec(view, "off_waveonly", p, TStar, 0));
                    }
                }
                if (!skip.Contains("mock"))
                {
                    Set(c, false, false, false);
                    Seek(c, TStar, true, true, true);
                    foreach (var view in new[] { "seat", "seat_low" })
                    {
                        if (!c.sway.ContainsKey(view)) continue;
                        foreach (var (eye, dx) in new[] { ("L", -MockHalf), ("R", MockHalf) })
                        {
                            c.sway[view].Apply(dx);
                            try
                            {
                                var p = od + "/mock/" + view + "_t120_" + eye + ".png";
                                CaptureWithSpray(c, view, p, false, false);
                                imgs.Add(Rec(view, "mock_" + eye, p, TStar, dx));
                            }
                            finally { c.sway[view].Restore(); }
                        }
                    }
                }
                // カメラと物の位置（配置の比較図の印に使う。数値だけ）
                var cams = new List<CamRec>();
                foreach (var kv in c.cams)
                {
                    var cam = kv.Value; float asp = cam.aspect; cam.aspect = (float)W / H;
                    cams.Add(new CamRec { view = kv.Key, position = cam.transform.position, euler = cam.transform.rotation.eulerAngles, fov = cam.fieldOfView,
                        near = cam.nearClipPlane, far = cam.farClipPlane, worldToCamera = M(cam.worldToCameraMatrix), projection = M(cam.projectionMatrix) });
                    cam.aspect = asp;
                }
                rep.cameras = cams.ToArray();
                var objs = new List<ObjRec>();
                foreach (Transform ch in c.ctx.transform) objs.Add(Obj(ch.gameObject));
                foreach (var n in new[] { "AF27 船 boat_left", "AF27 船 boat_mid", "AF27 船 boat_fg", FujiName, SkyDomeName, FlatSeaName })
                {
                    var g = GameObject.Find(n);
                    if (g != null) { var o = Obj(g); o.name = "find:" + n; objs.Add(o); }
                }
                rep.objects = objs.ToArray();
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
                if (c.backGo != null) UnityEngine.Object.DestroyImmediate(c.backGo);
            }
            rep.images = imgs.ToArray(); rep.idDecisions = ids.ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render、DS39_Paper.unity を開くだけで保存しない）。HMD 実機ではない。Mock の両眼は座席のカメラを右の向きへ ±0.032 m ずらした 2 回の描画。";
            File.WriteAllText(od + "/ds40_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS40_RENDER_DONE seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static float[] M(Matrix4x4 m) { var r = new float[16]; for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) r[i * 4 + j] = m[i, j]; return r; }

        static ObjRec Obj(GameObject g)
        {
            var rs = g.GetComponentsInChildren<Renderer>(false).Where(r => r.enabled).ToArray();
            var o = new ObjRec { name = g.name, active = g.activeInHierarchy, position = g.transform.position, renderers = rs.Length };
            if (rs.Length > 0)
            {
                var b = rs[0].bounds; foreach (var r in rs.Skip(1)) b.Encapsulate(r.bounds);
                o.boundsCenter = b.center; o.boundsMin = b.min; o.boundsMax = b.max;
            }
            return o;
        }

        static ImgRec Rec(string view, string cond, string path, float t, float dx) => new ImgRec { view = view, cond = cond, path = path, t = t, dx = dx, sha256 = Sha(path) };

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

        // 設計39 の HideFor と同じ（side_left と seat_toward_wave は背景の船・富士・仮置きを隠す）。waveOnly で背面にも同じ隠し方を使う。
        static List<Renderer> HideFor(Ctx c, string view, bool waveOnly)
        {
            var hid = new List<Renderer>();
            if (!waveOnly && view != "side_left" && view != "seat_toward_wave") return hid;
            foreach (var rr in c.ctx.GetComponentsInChildren<Renderer>(false))
            {
                if (!rr.enabled || rr.name == SkyDomeName || rr.name == FlatSeaName) continue;
                if (rr.transform.parent != null && (rr.transform.parent.name == SkyDomeName || rr.transform.parent.name == FlatSeaName)) continue;
                rr.enabled = false; hid.Add(rr);
            }
            return hid;
        }

        static List<string> RenderT28(Ctx c, string d28)
        {
            var f = new List<string>();
            Directory.CreateDirectory(d28);
            try
            {
                SetLines(c, true);
                foreach (var v in new[] { "painting", "seat", "seat_low" }) f.Add(Capture(c.cams[v], W, H, true, d28 + "/af28r01_" + v + ".png", Color.white));
                c.ctx.SetActive(false);
                SetLines(c, false);
                f.Add(Capture(c.cams["painting"], W, H, true, d28 + "/af28r01_painting_kstar.png", Color.white));
                f.Add(Capture(c.cams["seat"], W, H, true, d28 + "/af28r01_seat_kstar.png", Color.white));
                f.Add(Capture(c.cams["seat_low"], W, H, true, d28 + "/af28r01_seat_low_kstar.png", Color.white));
                Shader.SetGlobalFloat("_AF28IdMode", 1);
                f.Add(Capture(c.cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_class_ids.png", Color.white));
                f.Add(Capture(c.cams["seat"], W, H, false, d28 + "/af28r01_seat_class_ids.png", Color.white));
                f.Add(Capture(c.cams["seat_low"], W, H, false, d28 + "/af28r01_seat_low_class_ids.png", Color.white));
                SetLines(c, true);
                f.Add(Capture(c.cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_line_ids.png", Color.white));
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                c.ctx.SetActive(true);
                SetLines(c, true);
            }
            return f;
        }

        static void CaptureWithSpray(Ctx c, string view, string path, bool dense, bool waveOnly)
        {
            var cam = c.cams[view];
            var cb = new CommandBuffer { name = "DS40 飛沫" };
            c.spray.AddTo(cb);
            if (dense) c.dense.AddTo(cb);
            var hid = HideFor(c, view, waveOnly);
            cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            try { Capture(cam, W, H, true, path, Color.white); }
            finally
            {
                cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cb.Release();
                foreach (var r in hid) r.enabled = true;
            }
        }

        static bool KeepMaterial(Shader sh)
        {
            if (sh == null) return false;
            string n = sh.name;
            return n.Contains("Keypose") || n.StartsWith("GreatWave/Design27/") || n.StartsWith("GreatWave/Design34/") || n.StartsWith("GreatWave/Design36/DS36 Claw")
                || n.StartsWith("GreatWave/Design38/") || n.StartsWith("GreatWave/Design31/");
        }

        // 評価器の ID モード用の全体の ID 画像（CP1 の RenderIds と同じ 3840×2160・線形・MSAA なし。色は上の凡例）
        static void RenderIdsFull(Ctx c, Camera camera, string pngPath, bool lines, List<IdRec> log)
        {
            const int w = W * 2, h = H * 2;
            var idShader = Shader.Find("GreatWave/ArtFirst/AF24 ID Flat");
            if (idShader == null) throw new InvalidOperationException("AF24 ID Flat がありません。");
            var mats = new Dictionary<string, Material>();
            Material Mat(string key, Vector4 v) { if (!mats.TryGetValue(key, out var m)) { m = new Material(idShader) { hideFlags = HideFlags.DontSave }; m.SetVector("_IdColor", v); mats[key] = m; } return m; }
            var saved = new List<(Renderer, Material[])>();
            var dome = GameObject.Find(SkyDomeName);
            if (dome == null) throw new InvalidOperationException("空のドームがありません。");
            var boatRoots = IdBoats.Keys.ToDictionary(k => k, k => GameObject.Find("AF27 船 " + k));
            if (boatRoots.Values.Any(g => g == null)) throw new InvalidOperationException("船がありません。");
            SetLines(c, lines);
            try
            {
                foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                {
                    if (!r.enabled) continue;
                    var sh = r.sharedMaterial != null ? r.sharedMaterial.shader : null;
                    string key = null; Vector4 col = IdOtherV;
                    if (r.gameObject == dome) { key = "sky"; col = IdSkyV; }
                    foreach (var b in IdBoats) if (r.transform.IsChildOf(boatRoots[b.Key].transform)) { key = b.Key; col = b.Value; }
                    if (key == null && KeepMaterial(sh)) { log?.Add(new IdRec { renderer = r.name, shader = sh.name, decision = "keep(_AF28IdMode)" }); continue; }
                    if (key == null) key = "other";
                    log?.Add(new IdRec { renderer = r.name, shader = sh != null ? sh.name : "", decision = key });
                    saved.Add((r, r.sharedMaterials));
                    r.sharedMaterials = Enumerable.Repeat(Mat(key, col), Math.Max(1, r.sharedMaterials.Length)).ToArray();
                }
                var clear = camera.clearFlags; var bg = camera.backgroundColor;
                camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0, 1, 1, 1);
                var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
                rt.Create();
                var tex = new Texture2D(w, h, TextureFormat.RGB24, false, true);
                var prev = camera.targetTexture; bool hdr = camera.allowHDR, aa = camera.allowMSAA; float asp = camera.aspect;
                camera.allowHDR = false; camera.allowMSAA = false;
                Shader.SetGlobalFloat("_AF28IdMode", 1);
                camera.aspect = (float)w / h; camera.targetTexture = rt; camera.Render();
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply(); RenderTexture.active = null;
                Directory.CreateDirectory(Path.GetDirectoryName(pngPath));
                File.WriteAllBytes(pngPath, tex.EncodeToPNG());
                camera.targetTexture = prev; camera.allowHDR = hdr; camera.allowMSAA = aa; camera.aspect = asp;
                camera.clearFlags = clear; camera.backgroundColor = bg;
                UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                foreach (var (r, m) in saved) r.sharedMaterials = m;
                foreach (var m in mats.Values) UnityEngine.Object.DestroyImmediate(m);
            }
        }

        static string Capture(Camera camera, int w, int h, bool colour, string path, Color idSky)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture; float asp = camera.aspect;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = colour ? (Color)SkyTop : idSky;
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
    }
}
