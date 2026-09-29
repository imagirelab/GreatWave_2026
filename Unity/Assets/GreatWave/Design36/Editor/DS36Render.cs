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
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design36.EditorTools
{
    // 設計36 第「調色板」部 Unity：爪・飛沫・形成の全コマ・周りの海（手前の小波・右の高い波を含む）へ同じ調色板を当てて描く。
    // 設計34 の場面 DS34_ThreeLayers.unity（読むだけ）を開き、
    //   ・爪：DS36ClawPalette（t* の原画視点への投影で原画の色区、t* に背を向けた面は上面が白・縁の側面と下面が一覧の色区の影の色）、
    //   ・海：DS36SeaPalette（相対の高さの 4 段＋谷の縁の藍中の 1 段。主役波の材質の調色板を写す）、
    //   ・飛沫：設計31 のまま（白。調色板の白と同じ値かを報告に書く）、
    // を足して、設計36 の場面 DS36_Palette.unity として保存する（設計30・31・34 の場面は変えない）。そのあと次を書く（PC オフスクリーン描画、HMD ではない）：
    //   a. t* の画像の組（美術優先28修正01 と同じ名前）：t28_white（爪なし・飛沫なし）、t28_claws（爪あり）。評価器は ds30b_tstar_regress.py。
    //   b. 色票の画像：視点 painting・seat・seat_low・seat_toward_wave × 時刻の色の画像と、領域の画像（主役波 赤・near 緑・far 青・爪 マゼンタ・飛沫 シアン、
    //      _DS27DebugMode = 2 と SetDebugFlatClass。外殻線は切る）。
    //   c. 爪の t* の向きの確認（原画視点 t*、_DS36ClawFaceDiag）。
    //   d. 動画（painting・seat・seat_toward_wave、全層、30 fps、t 0〜14 s）。
    // 引数：-ds36Out（既定 Build/Design/36/palette/unity）、-ds36Skip scene,t28,chart,face,video、-ds36FaceFlip 0|1。
    public static class DS36Render
    {
        const string Scene34 = "Assets/GreatWave/Design34/Scenes/DS34_ThreeLayers.unity";
        public const string Scene36 = "Assets/GreatWave/Design36/Scenes/DS36_Palette.unity";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080;
        const float TStar = 12f, TEnd = 14f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);

        static string[] Protected => new[] {
            Scene34, "Assets/GreatWave/Design31/Scenes/DS31_WhiteSpray.unity", "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity",
            "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs", "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs",
            "Assets/GreatWave/Design34/Shaders/DS34_Claw_Unlit.shader", "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader",
            "Assets/GreatWave/Design31/Shaders/DS31_Spray_Unlit.shader",
            "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin", "Build/Design/33/claws/ds33_claw_frames_f32.bin",
            "Build/Design/30/sea/near/ds27_keypose.json", "Build/Design/30/sea/far/ds27_keypose.json" };

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        class Ctx
        {
            public GameObject ctx;
            public DS30SheetPlayer hero, near, far;
            public List<DS30SheetPlayer> sea = new List<DS30SheetPlayer>();
            public DS30SinglePlayback play;
            public MeshRenderer heroLine;
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public DS34ClawPlayer claws; public MeshRenderer clawR;
            public DS34LayerSet layers;
            public DS31InstancedParticles spray, sprayDiag;
            public DS36ClawPalette pal;
            public DS36SeaPalette seaPal;
        }

        [Serializable] class ColourRec { public string name; public Color value; public int r8, g8, b8; }
        [Serializable] class SheetRec { public string name, uv3Source, meshSource; public int rows, cols, whiteNeverCount; public bool whiteFromPackage; public Color white, mizuiro, aiMid, aiDark; }
        [Serializable] class FaceRec { public string view; public float t; public int frontPx, backPx; }
        [Serializable] class VideoRec { public string view, path, sha256, ffmpegError; public int frames, fps; public float seconds; }
        [Serializable]
        class Report
        {
            public string unity, device, graphicsApi, scene36, scene36Sha256, clawPalettePath, clawPaletteSha256, labelSdfSha256, noteJa;
            public int clawTStarFrame, clawsWithoutEntry, clawVerticesOffscreenAtTStar; public int[] clawShadowClassCounts; public float[] clawShadowClassPerClaw; public string[] clawIds;
            public bool faceFlip; public float cameraAspectBeforeApply, clawProjectionAspect; public bool tdepthFlip; public float[] tdepthMatchFrac, tdepthRange;
            public ColourRec[] heroPalette; public ColourRec lineColour, sprayColour; public SheetRec[] sheets;
            public FaceRec[] face; public VideoRec[] videos; public float[] chartTimes; public string[] chartViews;
            public string[] files, filesSha256, protectedFiles, changedFiles; public bool protectedUnchanged;
            public float secondsTotal;
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string od = Arg(a, "-ds36Out") ?? "Build/Design/36/palette/unity";
            var skip = new HashSet<string>((Arg(a, "-ds36Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            bool flip = (Arg(a, "-ds36FaceFlip") ?? "0") == "1";
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var files = new List<string>();
            var rep = new Report { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), faceFlip = flip };

            EditorSceneManager.OpenScene(Scene34, OpenSceneMode.Single);
            var scene = EditorSceneManager.GetActiveScene();
            var roots = scene.GetRootGameObjects();
            var c = new Ctx { ctx = roots.First(g => g.name == ContextRootName) };
            c.play = roots.Select(g => g.GetComponentInChildren<DS30SinglePlayback>(true)).First(x => x != null);
            c.hero = c.play.sheets.First(s => s.sheetName == "hero");
            c.sea = c.play.sheets.Where(s => s != c.hero).ToList();
            c.near = c.sea.FirstOrDefault(s => s.sheetName == "near");
            c.far = c.sea.FirstOrDefault(s => s.sheetName == "far");
            c.heroLine = c.hero.outline;
            var camRoot = GameObject.Find(CamRoot).transform;
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            var stwT = camRoot.Find("DS30 seat_toward_wave");
            if (stwT != null) c.cams["seat_toward_wave"] = stwT.GetComponent<Camera>();
            c.claws = roots.Select(g => g.GetComponentInChildren<DS34ClawPlayer>(true)).First(x => x != null);
            c.clawR = c.claws.GetComponent<MeshRenderer>();
            c.layers = roots.Select(g => g.GetComponentInChildren<DS34LayerSet>(true)).First(x => x != null);
            c.spray = roots.SelectMany(g => g.GetComponentsInChildren<DS31InstancedParticles>(true)).First(p => p.name == "DS31 spray");

            // 爪の調色板と海の調色板を足す
            c.pal = c.claws.gameObject.AddComponent<DS36ClawPalette>();
            c.pal.claws = c.claws; c.pal.paintingCamera = c.cams["painting"]; c.pal.faceFlip = flip;
            c.pal.palettePath = "Build/Design/36/palette/prep/ds36_claw_palette.json";
            var sg = new GameObject("DS36 周りの海の調色板（4 段＋谷の縁）");
            c.seaPal = sg.AddComponent<DS36SeaPalette>();
            c.seaPal.playback = c.play;
            c.seaPal.Configure();
            // 飛沫：設計31 の JSON の色（251,246,227）ではなく、主役波の調色板の白（材質の _White）にする
            c.spray.colourFromJson = false;
            c.spray.colour = c.hero.Surface.sharedMaterial.GetColor("_White");
            // 場面に保存するパスはプロジェクトからの相対にしておく（Configure は絶対パスにする）
            if (!skip.Contains("scene"))
            {
                var saved = c.sea.Select(s => new { s, sdf = s.sdfPath, uv = s.uv3File }).ToList();
                foreach (var x in saved)
                {
                    x.s.sdfPath = c.seaPal.rampPath;
                    x.s.uv3File = Path.GetFullPath(x.s.sheetName == "near" ? c.seaPal.uv3Near : c.seaPal.uv3Far);
                }
                if (!EditorSceneManager.SaveScene(scene, Scene36, true)) throw new InvalidOperationException("場面を保存できません: " + Scene36);
                rep.scene36 = Scene36; rep.scene36Sha256 = Sha(Scene36);
                foreach (var x in saved) { x.s.sdfPath = x.sdf; x.s.uv3File = x.uv; }
            }

            // 検査だけの物：確認用の色の飛沫（シアン）
            var dg = new GameObject("DS36 確認用の色の飛沫（シアン）");
            c.sprayDiag = dg.AddComponent<DS31InstancedParticles>();
            c.sprayDiag.dataPath = c.spray.dataPath; c.sprayDiag.clock = c.play.clock; c.sprayDiag.subdivisions = c.spray.subdivisions;
            c.sprayDiag.colourFromJson = false; c.sprayDiag.colour = new Color(0, 1, 1, 1); c.sprayDiag.drawInPlayMode = false;

            c.play.Prepare();
            c.spray.Load(); c.sprayDiag.Load(); c.claws.Load();
            var hp = c.seaPal.SyncFromHero();
            string[] pn = { "white", "mizuiro", "ai_mid", "ai_dark" };
            rep.heroPalette = Enumerable.Range(0, 4).Select(i => Col(pn[i], hp[i])).ToArray();
            c.pal.white = hp[0]; c.pal.mizuiro = hp[1]; c.pal.aiMid = hp[2]; c.pal.aiDark = hp[3];
            c.pal.Apply();
            rep.lineColour = Col("line", c.heroLine.sharedMaterial.GetColor("_LineColor"));
            rep.sprayColour = Col("spray", c.spray.colour);
            rep.clawPalettePath = Path.GetFullPath(c.pal.palettePath); rep.clawPaletteSha256 = c.pal.PaletteSha256; rep.labelSdfSha256 = c.pal.LabelSdfSha256;
            rep.cameraAspectBeforeApply = c.pal.AspectAtApply; rep.clawProjectionAspect = c.pal.targetAspect;
            rep.tdepthFlip = c.pal.TDepthFlip; rep.tdepthMatchFrac = c.pal.TDepthMatchFrac; rep.tdepthRange = c.pal.TDepthRange;
            rep.clawTStarFrame = c.pal.TStarFrame; rep.clawsWithoutEntry = c.pal.ClawsWithoutEntry; rep.clawVerticesOffscreenAtTStar = c.pal.VerticesOffscreenAtTStar;
            rep.clawShadowClassCounts = c.pal.ShadowClassCounts; rep.clawShadowClassPerClaw = c.pal.ShadowClassPerClaw; rep.clawIds = c.claws.ClawIds;
            var mpb = new MaterialPropertyBlock();
            rep.sheets = c.play.sheets.Select(s =>
            {
                s.Surface.GetPropertyBlock(mpb);
                var m = s.Surface.sharedMaterial;
                Func<string, Color> g = p => mpb.HasColor(p) ? mpb.GetColor(p) : m.GetColor(p);
                return new SheetRec { name = s.sheetName, uv3Source = s.Uv3Source, meshSource = s.MeshSource, rows = s.PackageMeta.rows, cols = s.PackageMeta.cols, whiteNeverCount = s.WhiteNeverCount, whiteFromPackage = s.WhiteFromPackage, white = g("_White"), mizuiro = g("_Mizuiro"), aiMid = g("_AiMid"), aiDark = g("_AiDark") };
            }).ToArray();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
            Shader.SetGlobalFloat("_DS34ClawDiag", 0);
            Shader.SetGlobalFloat("_DS36ClawFaceDiag", 0);

            try
            {
                if (!skip.Contains("t28"))
                {
                    Seek(c, TStar, true, false, false);
                    files.AddRange(RenderT28(c, od + "/t28_white/t28/render"));
                    Seek(c, TStar, true, true, false);
                    files.AddRange(RenderT28(c, od + "/t28_claws/t28/render"));
                }
                if (!skip.Contains("face"))
                {
                    var fr = new List<FaceRec>();
                    foreach (var t in new[] { 12f, 10f })
                        foreach (var v in new[] { "painting", "seat" })
                        {
                            Seek(c, t, true, true, false);
                            Shader.SetGlobalFloat("_DS36ClawFaceDiag", 1);
                            var path = string.Format(CultureInfo.InvariantCulture, "{0}/face/ds36_face_{1}_t{2:00.00}s.png", od, v, t);
                            var px = CaptureRaw(c.cams[v], W, H, false, SkyTop, path, files);
                            Shader.SetGlobalFloat("_DS36ClawFaceDiag", 0);
                            // 爪だけ（主役波と海を切った）でも数える：t* に表の画素（緑）と裏（赤）
                            fr.Add(new FaceRec { view = v, t = t, frontPx = px.Count(p => p.r == 0 && p.g == 255 && p.b == 0), backPx = px.Count(p => p.r == 255 && p.g == 0 && p.b == 0) });
                        }
                    rep.face = fr.ToArray();
                }
                if (!skip.Contains("chart"))
                {
                    var times = new[] { 4f, 6f, 8f, 9f, 10f, 11f, 12f };
                    var views = new[] { "painting", "seat", "seat_low", "seat_toward_wave" };
                    rep.chartTimes = times; rep.chartViews = views;
                    foreach (var t in times)
                    {
                        Seek(c, t, true, true, true);
                        foreach (var v in views)
                        {
                            files.Add(CaptureColour(c, v, true, string.Format(CultureInfo.InvariantCulture, "{0}/chart/ds36_colour_{1}_t{2:00.00}s.png", od, v, t)));
                            files.Add(CaptureRegion(c, v, string.Format(CultureInfo.InvariantCulture, "{0}/chart/ds36_region_{1}_t{2:00.00}s.png", od, v, t)));
                        }
                    }
                }
                var vids = new List<VideoRec>();
                if (!skip.Contains("video"))
                {
                    Directory.CreateDirectory(od + "/video");
                    foreach (var v in new[] { "painting", "seat", "seat_toward_wave" })
                    {
                        var sw = Stopwatch.StartNew();
                        var mp4 = od + "/video/ds36_palette_" + v + "_30fps.mp4";
                        int nf = EncodeVideo(c, v, 30, TEnd, mp4, out string err);
                        vids.Add(new VideoRec { view = v, path = Path.GetFullPath(mp4), frames = nf, fps = 30, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = File.Exists(mp4) ? Sha(mp4) : "" });
                        if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
                    }
                }
                rep.videos = vids.ToArray();
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat("_DS27DebugMode", 0);
                Shader.SetGlobalFloat("_DS34ClawDiag", 0);
                Shader.SetGlobalFloat("_DS36ClawFaceDiag", 0);
                foreach (var s in c.play.sheets) s.Release();
                c.spray.Release(); c.sprayDiag.Release(); c.pal.Release(); c.claws.Release();
            }
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.files = files.ToArray();
            rep.filesSha256 = files.Select(Sha).ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render）。HMD 実機ではない。";
            File.WriteAllText(od + "/ds36_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS36_RENDER_DONE seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static ColourRec Col(string n, Color v)
        {
            var g = v; // 材質の Color は sRGB の値（Gamma の色の値）
            return new ColourRec { name = n, value = v, r8 = Mathf.RoundToInt(g.r * 255f), g8 = Mathf.RoundToInt(g.g * 255f), b8 = Mathf.RoundToInt(g.b * 255f) };
        }

        static void Seek(Ctx c, double t, bool white, bool claws, bool spray)
        {
            c.play.Seek(t);
            c.spray.ApplyT(t); c.sprayDiag.ApplyT(t);
            c.claws.ApplyT(t);
            c.layers.whiteBand = white; c.layers.clawsOn = claws; c.layers.sprayOn = spray;
            c.layers.ApplyToggles();
        }

        static List<Renderer> HideFor(Ctx c, string view)
        {
            var hid = new List<Renderer>();
            if (view != "side_left" && view != "seat_toward_wave") return hid;
            foreach (var rr in c.ctx.GetComponentsInChildren<Renderer>(false))
            {
                if (!rr.enabled || rr.name == SkyDomeName || rr.name == FlatSeaName) continue;
                rr.enabled = false; hid.Add(rr);
            }
            return hid;
        }

        static CommandBuffer AttachSpray(Ctx c, Camera cam, bool diag)
        {
            if (!c.layers.sprayOn) return null;
            var cb = new CommandBuffer { name = "DS36 飛沫" };
            (diag ? c.sprayDiag : c.spray).AddTo(cb);
            cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            return cb;
        }

        static void Detach(Camera cam, CommandBuffer cb)
        {
            if (cb == null) return;
            cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            cb.Release();
        }

        static string CaptureColour(Ctx c, string view, bool line, string path)
        {
            var cam = c.cams[view];
            var hid = HideFor(c, view);
            CommandBuffer cb = null;
            try { cb = AttachSpray(c, cam, false); CaptureRaw(cam, W, H, true, SkyTop, path, null); return path; }
            finally { Detach(cam, cb); foreach (var r in hid) r.enabled = true; }
        }

        // 領域の画像：主役波 赤（平塗り 0）・near 緑（1）・far 青（2）・爪 マゼンタ・飛沫 シアン。ほか（船・富士・空のドーム・平らな海の輪など）はそのままの色
        static string CaptureRegion(Ctx c, string view, string path)
        {
            var cam = c.cams[view];
            var hid = HideFor(c, view);
            CommandBuffer cb = null;
            try
            {
                c.hero.SetDebugFlatClass(0);
                if (c.near != null) c.near.SetDebugFlatClass(1);
                if (c.far != null) c.far.SetDebugFlatClass(2);
                Shader.SetGlobalFloat("_DS27DebugMode", 2);
                Shader.SetGlobalFloat("_DS34ClawDiag", 1);
                c.heroLine.enabled = false;
                cb = AttachSpray(c, cam, true);
                CaptureRaw(cam, W, H, false, SkyTop, path, null);
                return path;
            }
            finally
            {
                Detach(cam, cb); foreach (var r in hid) r.enabled = true;
                c.hero.SetDebugFlatClass(-1);
                if (c.near != null) c.near.SetDebugFlatClass(-1);
                if (c.far != null) c.far.SetDebugFlatClass(-1);
                Shader.SetGlobalFloat("_DS27DebugMode", 0);
                Shader.SetGlobalFloat("_DS34ClawDiag", 0);
                c.heroLine.enabled = true;
            }
        }

        // 設計34 の RenderT28 と同じ（t28_seaids の読み）。爪は層の入切のまま色の画像と ID に入る。飛沫は入れない
        static List<string> RenderT28(Ctx c, string d28)
        {
            var f = new List<string>();
            Directory.CreateDirectory(d28);
            try
            {
                c.heroLine.enabled = true;
                foreach (var v in new[] { "painting", "seat", "seat_low" }) f.Add(Capture(c.cams[v], W, H, true, d28 + "/af28r01_" + v + ".png"));
                c.ctx.SetActive(false);
                c.heroLine.enabled = false;
                f.Add(Capture(c.cams["painting"], W, H, true, d28 + "/af28r01_painting_kstar.png"));
                f.Add(Capture(c.cams["seat"], W, H, true, d28 + "/af28r01_seat_kstar.png"));
                f.Add(Capture(c.cams["seat_low"], W, H, true, d28 + "/af28r01_seat_low_kstar.png"));
                Shader.SetGlobalFloat("_AF28IdMode", 1);
                f.Add(Capture(c.cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_class_ids.png"));
                f.Add(Capture(c.cams["seat"], W, H, false, d28 + "/af28r01_seat_class_ids.png"));
                f.Add(Capture(c.cams["seat_low"], W, H, false, d28 + "/af28r01_seat_low_class_ids.png"));
                c.heroLine.enabled = true;
                f.Add(Capture(c.cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_line_ids.png"));
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                c.ctx.SetActive(true);
                c.heroLine.enabled = true;
            }
            return f;
        }

        static Color32[] CaptureRaw(Camera camera, int w, int h, bool colour, Color bgc, string path, List<string> files)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture; float asp = camera.aspect;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = bgc;
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
            var px = tex.GetPixels32();
            if (path != null)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.WriteAllBytes(path, tex.EncodeToPNG());
                files?.Add(path);
            }
            camera.targetTexture = prev; camera.aspect = asp;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return px;
        }

        static string Capture(Camera camera, int w, int h, bool colour, string path)
        {
            CaptureRaw(camera, w, h, colour, colour ? (Color)SkyTop : IdSky, path, null);
            return path;
        }

        static int EncodeVideo(Ctx c, string view, int fps, float seconds, string mp4, out string err)
        {
            var camera = c.cams[view];
            int n = Mathf.RoundToInt(seconds * fps) + 1;
            string outs = string.Format("-vf vflip -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart \"{0}\"", Path.GetFullPath(mp4));
            var psi = new ProcessStartInfo
            {
                FileName = Ffmpeg,
                Arguments = string.Format("-y -loglevel error -f rawvideo -pix_fmt rgb24 -s {0}x{1} -r {2} -i - {3}", W, H, fps, outs),
                UseShellExecute = false, RedirectStandardInput = true, RedirectStandardError = true, CreateNoWindow = true
            };
            var sb = new StringBuilder();
            var hid = HideFor(c, view);
            CommandBuffer cb = null;
            try
            {
                Seek(c, 0, true, true, true);
                cb = AttachSpray(c, camera, false);
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
                    var clear = camera.clearFlags; var bg = camera.backgroundColor; var prev = camera.targetTexture;
                    camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = SkyTop; camera.allowHDR = false; camera.allowMSAA = true;
                    camera.aspect = (float)W / H;
                    try
                    {
                        for (int i = 0; i < n; i++)
                        {
                            Seek(c, i / (double)fps, true, true, true);
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
                        stdin.Flush(); stdin.Close();
                        camera.targetTexture = prev; camera.clearFlags = clear; camera.backgroundColor = bg;
                        UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
                        UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
                    }
                    if (!p.WaitForExit(10 * 60 * 1000)) { p.Kill(); throw new InvalidOperationException("ffmpeg が終わりません。"); }
                    p.WaitForExit();
                    lock (sb) err = sb.ToString() + (p.ExitCode != 0 ? " exit=" + p.ExitCode : "");
                }
            }
            finally { Detach(camera, cb); foreach (var r in hid) r.enabled = true; }
            return n;
        }

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
