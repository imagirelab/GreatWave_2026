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
using GreatWave.Design38;
using GreatWave.Design39;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Polish28.EditorTools
{
    // 仕上げ28（焼き直しと Unity の描画）：段階7〜9 の場面 DS39_Paper.unity（設計40 が評価器を回した場面。主役波・焼き込み・時間曲線・線・爪・飛沫・周りの海の
    // ファイルは設計50 の DS50_Release.unity と同じ）を読むだけで開き（保存しない）、主役波だけを差し替えて描く（PC オフスクリーン描画、HMD ではない）。
    //   -pl28State stage9 ：差し替えない（段階9 の状態＝設計28修正01 の F_final・K*′ R4・設計29修正01 の焼き込み・設計31 の T_white）。前後の図の「前」。
    //   -pl28State p28    ：主役波のシートの packageDir・meshGwb・sdfPath・warpPath と、再生の時間曲線 timewarpPath を仕上げ28 のものへ替える
    //                       （既定は G_p28b/art_on・timewarp_G_p28b.json・Build/Polish/28/unity/bake_kp の焼き込み。-pl28HeroPkg などで替えられる）。
    //                       爪（設計33 の爪の軌跡）・飛沫（設計31）・線の印（設計38）・周りの海（設計30。near の行 0 は F_final の主役波の境の輪）は
    //                       合わせ直さず、そのまま描く（仕上げ30〜33・36・38 の最初に作り直す。計画 §5.1）。
    // 段（-pl28Skip で飛ばせる）：
    //   t28.   設計40 と同じ t* の画像の組（t28_white＝爪なし・t28_claws＝爪あり。紙の 3 層は切）。評価器 ds29r01_tstar_eval・大きな輪郭・両側の読みの入力。
    //   full.  原画視点の作品のままの色画像（紙などを切、爪・飛沫あり）と、評価器23 の ID モード用の全体の ID 画像（設計40 と同じ 4 枚）。
    //   views. 前後の図の静止画：painting・seat・seat_toward_wave・side_left（波の枠とともに動く）・back65（粘土の後ろ 65° と同じ置き方、波の枠とともに動く）・
    //          back_cp1（設計40 の背面）× -pl28Times の時刻 ×「爪なし」（白あり・爪なし・飛沫なし・紙なし・線あり）と、t* の「そのまま」（爪・飛沫あり）。
    //   tt.    回り台（t*、粘土の回り台と同じ：中心 O(0)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごとに 12 枚。主役波だけ：
    //          背景の船・富士・仮置きと周りの海のシート（near・far）を隠す。平らな海と空は残す）。
    //   video. 動画（爪なし、960 × 540、30 fps）：-pl28VideoViews の視点を t 0〜14 s（421 コマ）と、回り台の 1 周（120 コマ）。
    // 場面・スクリプト・シェーダー・材質・データは変えない（守るファイルの SHA-256 を前後で比べる）。
    public static class PL28Render
    {
        const string Scene39 = "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080, Fps = 30;
        const float TStar = 12f, TEnd = 14f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        // 波の枠の向き（kh_common・rays_common と同じ。E＝原画視点から見た横、T＝進む向き）
        static readonly Vector3 E = new Vector3(0.6798348938056157f, 0f, 0.733365200404483f);
        static readonly Vector3 Tdir = new Vector3(0.7333652004044829f, 0f, -0.6798348938056156f);
        static readonly Vector3 BackCp1Position = new Vector3(-45, 30, 60), BackCp1Target = new Vector3(-5, 8, -3);
        static readonly Vector4 IdSkyV = new Vector4(0, 1, 1, 1), IdOtherV = new Vector4(0, 0, 0, 1);
        static readonly Dictionary<string, Vector4> IdBoats = new Dictionary<string, Vector4> {
            { "boat_left", new Vector4(0.4f, 0, 0, 1) }, { "boat_mid", new Vector4(0, 0.4f, 0, 1) }, { "boat_fg", new Vector4(0.4f, 0.4f, 0, 1) } };

        const string P28Pkg = "Build/Polish/28/G_p28b/art_on";
        const string P28Warp = "Build/Polish/28/G_p28b/timewarp_G_p28b.json";
        const string P28Gwb = "Build/Polish/28/unity/bake_kp/kstar/kstar_a45.gwb";
        const string P28Sdf = "Build/Polish/28/unity/bake_kp/bake/af28r01_uvsdf_a45.bin";
        const string P28UvWarp = "Build/Polish/28/unity/bake_kp/bake/af28r01_uvwarp_a45.json";

        static string[] Protected => new[] {
            Scene39, "Assets/GreatWave/Design50/Scenes/DS50_Release.unity", "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs",
            "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs", "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs",
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design38/Shaders/DS38_Outline_Keypose.shader",
            "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin", "Build/Design/29R01/bake_kp/kstar/kstar_a45.gwb",
            "Build/Design/31/white/hero_pkg/ds27_keypose.json", "Build/Design/28R01F/F_final/timewarp_F_final.json",
            "Build/Design/33/claws/ds33_claw_frames_f32.bin", "Build/Design/31/spray/ds31_spray_frames.bin",
            "Build/Design/38/outlines/unity/prep/ds38_hero_linemask_f32.bin",
            P28Pkg + "/ds27_keypose.json", P28Warp, P28Gwb, P28Sdf, P28UvWarp };

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        class Ctx
        {
            public GameObject ctx;
            public DS30SinglePlayback play;
            public DS30SheetPlayer hero;
            public List<DS30SheetPlayer> sheets = new List<DS30SheetPlayer>();
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public DS34ClawPlayer claws; public MeshRenderer clawR;
            public DS38ClawOutline clawLine;
            public List<DS38SheetOutline> lineComps = new List<DS38SheetOutline>();
            public DS34LayerSet layers;
            public DS31InstancedParticles spray, dense;
            public DS36ClawPalette pal;
            public DS36SeaPalette seaPal;
            public DS38LineGlobals globals;
            public DS39PaperLayers paper;
            public List<GameObject> temp = new List<GameObject>();
            public Vector3 sidePos0; public Quaternion sideRot0; public Vector3 oStarWorld;
        }

        [Serializable] class ImgRec { public string view, cond, path, sha256; public float t, tau; public Vector3 camPos, camTarget; public float fov; }
        [Serializable] class VidRec { public string name, view, path, sha256, ffmpegError; public int frames, fps, w, h; public float seconds, t0, t1; }
        [Serializable] class OriginRec { public float t, tau; public Vector3 originWorld; }
        [Serializable] class Report
        {
            public string unity, device, graphicsApi, colorSpace, utc, scene, sceneSha256, state, noteJa;
            public string heroPackage, heroPackageJsonSha256, heroMeshGwb, heroMeshSha256, heroSdf, heroSdfSha256, heroUvWarp, heroUvWarpSha256, timewarp, timewarpSha256;
            public int heroLayers; public bool heroPosLoUsed; public string heroPosLoSha256; public long heroGpuBytes;
            public string[] t28Files; public ImgRec[] images; public VidRec[] videos; public OriginRec[] origins;
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
            c.hero = c.sheets.First(s => s.sheetName == "hero");
            var camRoot = GameObject.Find(CamRoot).transform;
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            c.cams["seat_toward_wave"] = camRoot.Find("DS30 seat_toward_wave").GetComponent<Camera>();
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
            foreach (var n in new[] { "back65", "back_cp1", "tt" })
            {
                var go = new GameObject("PL28 " + n + "（一時のカメラ）") { hideFlags = HideFlags.DontSave };
                var cam = go.AddComponent<Camera>();
                cam.CopyFrom(c.cams["painting"]);
                cam.enabled = false;
                c.cams[n] = cam; c.temp.Add(go);
            }
            return c;
        }

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
            c.sidePos0 = c.cams["side_left"].transform.position; c.sideRot0 = c.cams["side_left"].transform.rotation;
            c.oStarWorld = c.hero.transform.TransformPoint(c.hero.OriginAt(0.0));
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string state = Arg(a, "-pl28State") ?? "p28";
            string od = Arg(a, "-pl28Out") ?? ("G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/28/unity/scene_" + state);
            var skip = new HashSet<string>((Arg(a, "-pl28Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            var times = (Arg(a, "-pl28Times") ?? "6,8,10,11,12").Split(',').Select(s => double.Parse(s, CultureInfo.InvariantCulture)).ToArray();
            var vidViews = (Arg(a, "-pl28VideoViews") ?? "painting,seat_toward_wave,side_left,back65").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            int vw = int.Parse(Arg(a, "-pl28VideoW") ?? "960", CultureInfo.InvariantCulture), vh = vw * 9 / 16;
            if (state != "stage9" && state != "p28") throw new ArgumentException("-pl28State は stage9 か p28");
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), utc = DateTime.UtcNow.ToString("O"), scene = Scene39, sceneSha256 = Sha(Scene39), state = state
            };
            var c = Open();
            if (state == "p28")
            {
                c.hero.packageDir = Arg(a, "-pl28HeroPkg") ?? P28Pkg;
                c.hero.meshGwb = Arg(a, "-pl28HeroGwb") ?? P28Gwb;
                c.hero.sdfPath = Arg(a, "-pl28HeroSdf") ?? P28Sdf;
                c.hero.warpPath = Arg(a, "-pl28HeroUvWarp") ?? P28UvWarp;
                c.play.timewarpPath = Arg(a, "-pl28Timewarp") ?? P28Warp;
            }
            rep.heroPackage = c.hero.packageDir; rep.heroPackageJsonSha256 = Sha(Path.Combine(c.hero.packageDir, "ds27_keypose.json"));
            rep.heroMeshGwb = c.hero.meshGwb; rep.heroMeshSha256 = Sha(c.hero.meshGwb);
            rep.heroSdf = c.hero.sdfPath; rep.heroSdfSha256 = Sha(c.hero.sdfPath);
            rep.heroUvWarp = c.hero.warpPath; rep.heroUvWarpSha256 = Sha(c.hero.warpPath);
            rep.timewarp = c.play.timewarpPath; rep.timewarpSha256 = Sha(c.play.timewarpPath);
            var imgs = new List<ImgRec>(); var vids = new List<VidRec>(); var origins = new List<OriginRec>();
            try
            {
                Prepare(c);
                rep.heroLayers = c.hero.PackageMeta.layers; rep.heroPosLoUsed = c.hero.PosLoFromPackage; rep.heroPosLoSha256 = c.hero.PosLoSha256;
                rep.heroGpuBytes = c.hero.PositionGpuBytes + c.hero.PosLoGpuBytes + c.hero.WhiteGpuBytes;
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
                    Set(c, false, false, false);
                    Seek(c, TStar, true, true, true);
                    var p0 = od + "/full/painting_t120_off.png";
                    CaptureView(c, "painting", p0, TStar, W, H, true, imgs, "full_off");
                    Set(c, false, false, false);
                    Seek(c, TStar, true, true, false);
                    var p1 = od + "/full/ids_noline.png"; RenderIdsFull(c, c.cams["painting"], p1, false); imgs.Add(Rec("painting", "ids_noline", p1, TStar, c));
                    var p2 = od + "/full/ids_line.png"; RenderIdsFull(c, c.cams["painting"], p2, true); imgs.Add(Rec("painting", "ids_line", p2, TStar, c));
                    Seek(c, TStar, true, false, false);
                    var p3 = od + "/full/ids_line_noclaws.png"; RenderIdsFull(c, c.cams["painting"], p3, true); imgs.Add(Rec("painting", "ids_line_noclaws", p3, TStar, c));
                    var p4 = od + "/full/ids_noline_noclaws.png"; RenderIdsFull(c, c.cams["painting"], p4, false); imgs.Add(Rec("painting", "ids_noline_noclaws", p4, TStar, c));
                    SetLines(c, true);
                }
                if (!skip.Contains("views"))
                {
                    Set(c, false, false, false);
                    foreach (var t in times)
                    {
                        Seek(c, t, true, false, false);
                        origins.Add(new OriginRec { t = (float)t, tau = (float)c.play.Tau, originWorld = OriginWorld(c) });
                        foreach (var v in new[] { "painting", "seat", "seat_toward_wave", "side_left", "back65", "back_cp1" })
                            CaptureView(c, v, od + "/views/" + v + "_t" + ((int)Math.Round(t * 10)).ToString("000") + "_clawfree.png", t, W, H, false, imgs, "clawfree");
                    }
                    Seek(c, TStar, true, true, true);
                    foreach (var v in new[] { "painting", "seat", "seat_toward_wave", "side_left", "back65" })
                        CaptureView(c, v, od + "/views/" + v + "_t120_asis.png", TStar, W, H, true, imgs, "asis");
                }
                if (!skip.Contains("tt"))
                {
                    Set(c, false, false, false);
                    Seek(c, TStar, true, false, false);
                    for (int k = 0; k < 12; k++)
                    {
                        PlaceTurntable(c, k * 30.0);
                        CaptureView(c, "tt", od + "/tt/tt_az" + (k * 30).ToString("000") + ".png", TStar, W, H, false, imgs, "clawfree", true);
                    }
                }
                if (!skip.Contains("video"))
                {
                    Set(c, false, false, false);
                    int n = (int)Math.Round(TEnd * Fps) + 1;
                    foreach (var v in vidViews)
                        vids.Add(Video(c, v, v, n, i => i / (double)Fps, null, od + "/video", vw, vh));
                    vids.Add(Video(c, "tt", "tt", 120, i => TStar, i => i * 3.0, od + "/video", vw, vh));
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_DS39Gain", 0);
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                c.paper.Teardown();
                foreach (var so in c.lineComps) so.ReleaseMask();
                foreach (var s in c.play.sheets) s.Release();
                c.spray.Release(); c.dense.Release(); c.pal.Release(); c.clawLine.Release(); c.claws.Release();
                foreach (var g in c.temp) if (g != null) UnityEngine.Object.DestroyImmediate(g);
            }
            rep.images = imgs.ToArray(); rep.videos = vids.ToArray(); rep.origins = origins.ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render、DS39_Paper.unity を開くだけで保存しない）。HMD 実機ではない。" +
                         (state == "p28" ? "主役波のシートと時間曲線だけを仕上げ28 のものへ替えた（爪・飛沫・線の印・周りの海は合わせ直していない）。" : "差し替えなし（段階9 の状態）。");
            File.WriteAllText(od + "/pl28_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("PL28_RENDER_DONE state=" + state + " seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static Vector3 OriginWorld(Ctx c) => c.hero.transform.TransformPoint(c.hero.AppliedOrigin);

        // 視点ごとのカメラの置き方（時刻に従って動くもの）
        static void PlaceFor(Ctx c, string view)
        {
            if (view == "side_left")
                c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0 + (OriginWorld(c) - c.oStarWorld), c.sideRot0);
            else if (view == "back65")
            {
                var o = OriginWorld(c);
                float ang = -65f * Mathf.Deg2Rad;
                var pos = o + 90f * (Mathf.Cos(ang) * E + Mathf.Sin(ang) * Tdir) + new Vector3(0, 18, 0);
                var cam = c.cams["back65"];
                cam.transform.position = pos; cam.transform.LookAt(o + new Vector3(0, 8, 0), Vector3.up); cam.fieldOfView = 26f;
            }
            else if (view == "back_cp1")
            {
                var cam = c.cams["back_cp1"];
                cam.transform.position = BackCp1Position; cam.transform.LookAt(BackCp1Target, Vector3.up); cam.fieldOfView = 50f;
            }
        }

        static void RestoreFor(Ctx c, string view)
        {
            if (view == "side_left") c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0, c.sideRot0);
        }

        // 粘土の回り台（backfirst_bl.turntable_mode）と同じ：C0 = O(0)+(0,9,0)、半径 72、仰角 16°、縦 34°、原画視点 (0,3,−62) の向きから azDeg
        static void PlaceTurntable(Ctx c, double azDeg)
        {
            var c0 = c.oStarWorld + new Vector3(0, 9, 0);
            var pc = new Vector3(0f, 3f, -62f) - c0;
            double az0 = Math.Atan2(pc.z, pc.x), az = az0 + azDeg * Math.PI / 180.0, el = 16.0 * Math.PI / 180.0;
            var eye = c0 + new Vector3((float)(72 * Math.Cos(el) * Math.Cos(az)), (float)(72 * Math.Sin(el)), (float)(72 * Math.Cos(el) * Math.Sin(az)));
            var cam = c.cams["tt"];
            cam.transform.position = eye; cam.transform.LookAt(c0, Vector3.up); cam.fieldOfView = 34f;
        }

        static bool WaveOnly(string view) => view == "side_left" || view == "seat_toward_wave" || view == "back65" || view == "tt";

        static ImgRec Rec(string view, string cond, string path, double t, Ctx c)
        {
            var cam = c.cams[view];
            return new ImgRec { view = view, cond = cond, path = path, t = (float)t, tau = (float)c.play.Tau, sha256 = Sha(path), camPos = cam.transform.position,
                                camTarget = cam.transform.position + cam.transform.forward * 10f, fov = cam.fieldOfView };
        }

        static void CaptureView(Ctx c, string view, string path, double t, int w, int h, bool spray, List<ImgRec> imgs, string cond, bool placed = false)
        {
            if (!placed) PlaceFor(c, view);
            var cam = c.cams[view];
            CommandBuffer cb = null;
            if (spray) { cb = new CommandBuffer { name = "PL28 飛沫" }; c.spray.AddTo(cb); cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb); }
            var hid = HideFor(c, WaveOnly(view));
            if (view == "tt") hid.AddRange(HideOtherSheets(c));
            try { Capture(cam, w, h, true, path, Color.white); imgs.Add(Rec(view, cond, path, t, c)); }
            finally
            {
                if (cb != null) { cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cb.Release(); }
                foreach (var r in hid) r.enabled = true;
                RestoreFor(c, view);
            }
        }

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

        // 設計39・40 の HideFor と同じ（波だけ：背景の船・富士・仮置きを隠し、空と平らな海は残す）
        static List<Renderer> HideFor(Ctx c, bool waveOnly)
        {
            var hid = new List<Renderer>();
            if (!waveOnly) return hid;
            foreach (var rr in c.ctx.GetComponentsInChildren<Renderer>(false))
            {
                if (!rr.enabled || rr.name == SkyDomeName || rr.name == FlatSeaName) continue;
                if (rr.transform.parent != null && (rr.transform.parent.name == SkyDomeName || rr.transform.parent.name == FlatSeaName)) continue;
                rr.enabled = false; hid.Add(rr);
            }
            return hid;
        }

        // 回り台は粘土の回り台と同じく主役波だけを見る：周りの海のシート（near・far）の面と外殻線を隠す（平らな海と空は残す）
        static List<Renderer> HideOtherSheets(Ctx c)
        {
            var hid = new List<Renderer>();
            foreach (var s in c.sheets)
            {
                if (s == c.hero) continue;
                foreach (var r in new Renderer[] { s.Surface, s.outline })
                    if (r != null && r.enabled) { r.enabled = false; hid.Add(r); }
            }
            return hid;
        }

        // 設計40 の RenderT28 と同じ（名前・設定・順）
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

        static bool KeepMaterial(Shader sh)
        {
            if (sh == null) return false;
            string n = sh.name;
            return n.Contains("Keypose") || n.StartsWith("GreatWave/Design27/") || n.StartsWith("GreatWave/Design34/") || n.StartsWith("GreatWave/Design36/DS36 Claw")
                || n.StartsWith("GreatWave/Design38/") || n.StartsWith("GreatWave/Design31/");
        }

        // 設計40 の RenderIdsFull と同じ（3840×2160・線形・MSAA なし）
        static void RenderIdsFull(Ctx c, Camera camera, string pngPath, bool lines)
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
                    if (key == null && KeepMaterial(sh)) continue;
                    if (key == null) key = "other";
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

        // 動画（爪なし・飛沫なし・紙なし・線あり）。コマを ffmpeg へ生の RGB で渡す（連番は書かない）。azOf が null でなければ回り台。
        static VidRec Video(Ctx c, string name, string view, int n, Func<int, double> tOf, Func<int, double> azOf, string od, int w, int h)
        {
            var sw = Stopwatch.StartNew();
            Directory.CreateDirectory(od);
            var mp4 = od + "/pl28_" + name + "_30fps.mp4";
            var camera = c.cams[view];
            var psi = new ProcessStartInfo
            {
                FileName = Ffmpeg,
                Arguments = string.Format("-y -loglevel error -f rawvideo -pix_fmt rgb24 -s {0}x{1} -r {2} -i - -vf vflip -c:v libx264 -preset medium -crf 16 -pix_fmt yuv420p -movflags +faststart \"{3}\"",
                                          w, h, Fps, Path.GetFullPath(mp4)),
                UseShellExecute = false, RedirectStandardInput = true, RedirectStandardError = true, CreateNoWindow = true
            };
            var sb = new StringBuilder();
            var hid = HideFor(c, WaveOnly(view));
            if (view == "tt") hid.AddRange(HideOtherSheets(c));
            string err;
            try
            {
                using (var p = new Process { StartInfo = psi })
                {
                    p.ErrorDataReceived += (s, e) => { if (e.Data != null) lock (sb) sb.AppendLine(e.Data); };
                    p.Start();
                    p.BeginErrorReadLine();
                    var stdin = p.StandardInput.BaseStream;
                    var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
                    var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                    rt.Create(); res.Create();
                    var tex = new Texture2D(w, h, TextureFormat.RGB24, false, false);
                    var clear = camera.clearFlags; var bg = camera.backgroundColor; var prev = camera.targetTexture; float asp = camera.aspect;
                    bool hdr = camera.allowHDR, aa = camera.allowMSAA;
                    camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = SkyTop; camera.allowHDR = false; camera.allowMSAA = true;
                    camera.aspect = (float)w / h;
                    try
                    {
                        for (int i = 0; i < n; i++)
                        {
                            Seek(c, tOf(i), true, false, false);
                            if (azOf != null) PlaceTurntable(c, azOf(i)); else PlaceFor(c, view);
                            camera.targetTexture = rt;
                            camera.Render();
                            Graphics.Blit(rt, res);
                            RenderTexture.active = res;
                            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                            RenderTexture.active = null;
                            var raw = tex.GetRawTextureData();
                            stdin.Write(raw, 0, raw.Length);
                        }
                    }
                    finally
                    {
                        stdin.Flush(); stdin.Close();
                        RestoreFor(c, view);
                        camera.targetTexture = prev; camera.clearFlags = clear; camera.backgroundColor = bg; camera.aspect = asp; camera.allowHDR = hdr; camera.allowMSAA = aa;
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
                foreach (var r in hid) r.enabled = true;
            }
            if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
            return new VidRec { name = name, view = view, path = Path.GetFullPath(mp4), frames = n, fps = Fps, w = w, h = h, seconds = (float)sw.Elapsed.TotalSeconds,
                                ffmpegError = err, sha256 = Sha(mp4), t0 = (float)tOf(0), t1 = (float)tOf(n - 1) };
        }

        static string Sha(string path)
        {
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
