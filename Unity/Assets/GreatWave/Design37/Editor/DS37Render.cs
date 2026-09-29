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
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design37.EditorTools
{
    // 設計37 第「流れに沿う線」部 Unity：縞（藍の色区、美術優先28 の UV-SDF・美術優先31 の追従）と周りの海の模様（設計36 の段）が
    // 面に付いて動き、画面に貼り付かないことを確かめるための描画（PC オフスクリーン描画、HMD ではない）。
    // 設計36 の場面 DS36_Palette.unity（読むだけ）を開き、頭の揺れの部品 DS37HeadSway を足して DS37_FlowLines.unity として保存する
    // （色の描画の設定は設計36 のまま変えない）。そのあと次を書く：
    //   check. t* の原画視点の色の画像（設計36 の t28_claws の画像と画素まで同じかを ds37_flow_eval.py が比べる。原画視点に触れていないことの証拠）。
    //   flow.  形成の組（t, t + 0.1 s、t = 1〜13 s）× 視点 painting・seat：色の画像（白の時間場あり・なし）、面の座標（DS37 Surface Coord。浮動小数の描画の R・G を float32 × 2 で書く）、
    //          カメラの行列、各シートの全頂点の位置（DS27KeyposeCapture、頂点シェーダーと同じ関数）。
    //   flowk. 177 のための原画視点（背景と外殻線を切った主役波と海、形成の組と同じ時刻）：色の画像と面の座標とカメラの行列。
    //   sway.  頭の揺れ：視点 seat・seat_toward_wave × t 6・9・12 s × 左右 −0.1・0・+0.1 m：色の画像（作品のまま）、面の座標、カメラの行列。
    //   h177.  177 のための主役波の全頂点の位置（t 0〜14 s、0.25 s ごと）と UV3（頂点ごと）。
    //   l191.  191 の事前検査：視点 painting・seat の連続 301 コマ（t 2.0〜12.0 s、30 fps）の外殻線の画素（_AF28IdMode = 1 のマゼンタ）を
    //          1 bit に詰めた表と、各コマの主役波の頂点の画面の動き（前のコマから、p99・最大）。
    //   video. 形成の全区間（t 0〜14 s）の動画 painting・seat、頭の揺れの動画 3 本（seat の形成の全区間、seat の t*、seat_toward_wave の t 9 s）。
    // 引数：-ds37Out（既定 Build/Design/37/flowlines/unity）、-ds37Skip scene,check,flow,flowk,sway,h177,l191,video。
    public static class DS37Render
    {
        const string Scene36 = "Assets/GreatWave/Design36/Scenes/DS36_Palette.unity";
        public const string Scene37 = "Assets/GreatWave/Design37/Scenes/DS37_FlowLines.unity";
        const string CoordShaderName = "GreatWave/Design37/DS37 Surface Coord";
        const string CapturePath = "Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080, Fps = 30;
        const float TStar = 12f, TEnd = 14f, Sway = 0.1f, SwayPeriod = 2f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);

        static string[] Protected => new[] {
            Scene36, "Assets/GreatWave/Design34/Scenes/DS34_ThreeLayers.unity", "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity",
            "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs", "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs",
            "Assets/GreatWave/Design36/Scripts/DS36SeaPalette.cs", "Assets/GreatWave/Design36/Scripts/DS36ClawPalette.cs",
            "Assets/GreatWave/Design36/Shaders/DS36_Claw_Palette.shader", "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader",
            "Assets/GreatWave/Design27/Shaders/DS27_Outline_Keypose.shader", "Assets/GreatWave/Design31/Shaders/DS31_Spray_Unlit.shader",
            "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin", "Build/Design/33/claws/ds33_claw_frames_f32.bin",
            "Build/Design/36/palette/prep/ds36_sea_ramp_256_rgba8.bin", "Build/Design/36/palette/prep/ds36_sea_uv3_near_f32.bin",
            "Build/Design/36/palette/prep/ds36_sea_uv3_far_f32.bin",
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
            public List<DS30SheetPlayer> sheets = new List<DS30SheetPlayer>();
            public DS30SinglePlayback play;
            public MeshRenderer heroLine;
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public Dictionary<string, DS37HeadSway> sway = new Dictionary<string, DS37HeadSway>();
            public DS34ClawPlayer claws; public MeshRenderer clawR;
            public DS34LayerSet layers;
            public DS31InstancedParticles spray;
            public DS36ClawPalette pal;
            public DS36SeaPalette seaPal;
            public Material coordMat;
            public ComputeShader cs; public int kernel;
        }

        [Serializable] class SheetRec { public string name, packageDir, meshSource, uv3Source, sdfPath; public int rows, cols, sheetId; }
        [Serializable]
        class FrameRec
        {
            public string kind, view, colourWhiteOn, colourWhiteOff, coord; public float t, tau, dx;
            public float[] camPos, worldToCamera, projection; public int w, h;
        }
        [Serializable] class VertRec { public string sheet, path; public float t, tau; public int count; }
        [Serializable] class L191Rec { public string view, path; public int frames, w, h, firstFrame; public float[] heroMoveP99, heroMoveMax; public int[] linePx; }
        [Serializable] class VideoRec { public string name, view, path, sha256, ffmpegError; public int frames, fps; public float seconds; }
        [Serializable]
        class Report
        {
            public string unity, device, graphicsApi, scene37, scene37Sha256, heroUv3Path, heroSdfPath, noteJa, coordLayoutJa, vertLayoutJa, l191LayoutJa;
            public float sway, swayPeriod, tStar; public int w, h, fps;
            public SheetRec[] sheets; public FrameRec[] frames; public VertRec[] verts; public L191Rec[] l191; public VideoRec[] videos;
            public string[] files, protectedFiles, changedFiles; public bool protectedUnchanged; public float secondsTotal;
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string od = Arg(a, "-ds37Out") ?? "Build/Design/37/flowlines/unity";
            var skip = new HashSet<string>((Arg(a, "-ds37Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var files = new List<string>();
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                sway = Sway, swayPeriod = SwayPeriod, tStar = TStar, w = W, h = H, fps = Fps,
                coordLayoutJa = "float32 × 2（R = 列 + 2000 × シートの番号、G = 行）、下の行から上へ（Unity の読み戻しの順）。R < 1000 はシート以外（空・船・富士など）。シートの番号：1 主役波・2 near・3 far・4 爪（爪は列・行 0）",
                vertLayoutJa = "float32 × 3（ワールドの位置 xyz）、頂点の添字 = 行 × 列数 + 列",
                l191LayoutJa = "コマごとに W × H の 1 bit（行は上から下、行の中は左から右、各バイトの上位の bit が先。numpy の packbits と同じ）"
            };

            EditorSceneManager.OpenScene(Scene36, OpenSceneMode.Single);
            var scene = EditorSceneManager.GetActiveScene();
            var roots = scene.GetRootGameObjects();
            var c = new Ctx { ctx = roots.First(g => g.name == ContextRootName) };
            c.play = roots.Select(g => g.GetComponentInChildren<DS30SinglePlayback>(true)).First(x => x != null);
            c.sheets = c.play.sheets.Where(s => s != null).ToList();
            c.hero = c.sheets.First(s => s.sheetName == "hero");
            c.near = c.sheets.FirstOrDefault(s => s.sheetName == "near");
            c.far = c.sheets.FirstOrDefault(s => s.sheetName == "far");
            c.heroLine = c.hero.outline;
            var camRoot = GameObject.Find(CamRoot).transform;
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            var stwT = camRoot.Find("DS30 seat_toward_wave");
            if (stwT != null) c.cams["seat_toward_wave"] = stwT.GetComponent<Camera>();
            c.claws = roots.Select(g => g.GetComponentInChildren<DS34ClawPlayer>(true)).First(x => x != null);
            c.clawR = c.claws.GetComponent<MeshRenderer>();
            c.layers = roots.Select(g => g.GetComponentInChildren<DS34LayerSet>(true)).First(x => x != null);
            c.spray = roots.SelectMany(g => g.GetComponentsInChildren<DS31InstancedParticles>(true)).First(p => p.name == "DS31 spray");
            c.pal = c.claws.GetComponent<DS36ClawPalette>();
            c.seaPal = roots.Select(g => g.GetComponentInChildren<DS36SeaPalette>(true)).First(x => x != null);

            // 頭の揺れの部品（座席の 2 つのカメラ）を足して、設計37 の場面として保存する（色の設定は設計36 のまま）
            foreach (var v in new[] { "seat", "seat_toward_wave" })
            {
                if (!c.cams.ContainsKey(v)) continue;
                var hs = c.cams[v].gameObject.AddComponent<DS37HeadSway>();
                hs.target = c.cams[v]; hs.amplitude = Sway; hs.period = SwayPeriod; hs.swayInPlayMode = false;
                c.sway[v] = hs;
            }
            if (!skip.Contains("scene"))
            {
                if (!EditorSceneManager.SaveScene(scene, Scene37, true)) throw new InvalidOperationException("場面を保存できません: " + Scene37);
                rep.scene37 = Scene37; rep.scene37Sha256 = Sha(Scene37);
            }

            c.play.Prepare();
            c.spray.Load(); c.claws.Load();
            var hp = c.seaPal.SyncFromHero();
            c.pal.white = hp[0]; c.pal.mizuiro = hp[1]; c.pal.aiMid = hp[2]; c.pal.aiDark = hp[3];
            c.pal.Apply();
            var sh = Shader.Find(CoordShaderName);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + CoordShaderName);
            c.coordMat = new Material(sh) { hideFlags = HideFlags.DontSave };
            c.cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(CapturePath);
            if (c.cs == null) throw new InvalidOperationException("DS27KeyposeCapture.compute がありません。");
            c.kernel = c.cs.FindKernel("DS27Capture");
            var ids = new Dictionary<DS30SheetPlayer, int> { { c.hero, 1 } };
            if (c.near != null) ids[c.near] = 2;
            if (c.far != null) ids[c.far] = 3;
            rep.sheets = c.sheets.Select(s => new SheetRec { name = s.sheetName, packageDir = s.packageDir, meshSource = s.MeshSource, uv3Source = s.Uv3Source, sdfPath = s.sdfPath, rows = s.PackageMeta.rows, cols = s.PackageMeta.cols, sheetId = ids.ContainsKey(s) ? ids[s] : 0 }).ToArray();
            rep.heroSdfPath = Path.GetFullPath(c.hero.sdfPath);
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
            Shader.SetGlobalFloat("_DS34ClawDiag", 0);
            Shader.SetGlobalFloat("_DS36ClawFaceDiag", 0);

            var frames = new List<FrameRec>();
            var verts = new List<VertRec>();
            var l191 = new List<L191Rec>();
            var vids = new List<VideoRec>();
            try
            {
                // 主役波の UV3（頂点ごと）
                {
                    var uvs = new List<Vector2>();
                    c.hero.SurfaceMesh.GetUVs(2, uvs);
                    var fl = new float[uvs.Count * 2];
                    for (int i = 0; i < uvs.Count; i++) { fl[2 * i] = uvs[i].x; fl[2 * i + 1] = uvs[i].y; }
                    var p = od + "/hero_uv3_f32.bin";
                    WriteFloats(p, fl); files.Add(p); rep.heroUv3Path = Path.GetFullPath(p);
                }
                if (!skip.Contains("check"))
                {
                    Seek(c, TStar, true, true, false);
                    var p = od + "/check/ds37_painting_tstar.png";
                    CaptureColour(c, "painting", 0f, p); files.Add(p);
                }
                if (!skip.Contains("flow"))
                {
                    var ts = new List<float>();
                    for (int k = 1; k <= 13; k++) { ts.Add(k); ts.Add(k + 0.1f); }
                    foreach (var t in ts)
                    {
                        Seek(c, t, true, true, false);
                        foreach (var s in c.sheets) verts.Add(CaptureVerts(c, s, t, od + "/verts"));
                        foreach (var v in new[] { "painting", "seat" })
                            frames.Add(CaptureFrame(c, "flow", v, t, 0f, true, od + "/flow"));
                    }
                }
                if (!skip.Contains("flowk"))
                {
                    // 177 のための原画視点：背景（船・富士など）と外殻線を切った主役波と海だけ（評価器の af28r01_painting_kstar と同じ切り方）。
                    // 原画視点の左下の藍中の帯 4 本（A024・A021・A028・A018）は、背景ありの描画では手前の船に隠れる
                    for (int k = 1; k <= 13; k++)
                        foreach (var t in new[] { (float)k, k + 0.1f })
                        {
                            Seek(c, t, true, true, false);
                            bool line = c.heroLine.enabled;
                            c.ctx.SetActive(false); c.heroLine.enabled = false;
                            try { frames.Add(CaptureFrame(c, "flowk", "painting", t, 0f, false, od + "/flowk")); }
                            finally { c.ctx.SetActive(true); c.heroLine.enabled = line; }
                        }
                }
                if (!skip.Contains("sway"))
                {
                    foreach (var t in new[] { 6f, 9f, 12f })
                    {
                        Seek(c, t, true, true, false);
                        if (!verts.Any(x => Mathf.Abs(x.t - t) < 1e-4f && x.sheet == "hero"))
                            foreach (var s in c.sheets) verts.Add(CaptureVerts(c, s, t, od + "/verts"));
                        foreach (var v in new[] { "seat", "seat_toward_wave" })
                            foreach (var dx in new[] { -Sway, 0f, Sway })
                                frames.Add(CaptureFrame(c, "sway", v, t, dx, false, od + "/sway"));
                    }
                }
                if (!skip.Contains("h177"))
                {
                    for (int k = 0; k <= 56; k++)
                    {
                        float t = k * 0.25f;
                        Seek(c, t, true, true, false);
                        var vr = CaptureVerts(c, c.hero, t, od + "/h177");
                        verts.Add(vr);
                    }
                }
                if (!skip.Contains("l191"))
                {
                    foreach (var v in new[] { "painting", "seat" }) l191.Add(Line191(c, v, 60, 301, od + "/l191"));
                }
                if (!skip.Contains("video"))
                {
                    Directory.CreateDirectory(od + "/video");
                    int nF = Mathf.RoundToInt(TEnd * Fps) + 1, nS = 4 * Fps + 1;
                    vids.Add(Video(c, "formation_painting", "painting", nF, i => i / (double)Fps, i => 0f, od));
                    vids.Add(Video(c, "formation_seat", "seat", nF, i => i / (double)Fps, i => 0f, od));
                    vids.Add(Video(c, "sway_seat_formation", "seat", nF, i => i / (double)Fps, i => SwayAt(i / (double)Fps), od));
                    vids.Add(Video(c, "sway_seat_tstar", "seat", nS, i => TStar, i => SwayAt(i / (double)Fps), od));
                    vids.Add(Video(c, "sway_seat_toward_wave_t09", "seat_toward_wave", nS, i => 9.0, i => SwayAt(i / (double)Fps), od));
                }
            }
            finally
            {
                foreach (var s in c.sway.Values) s.Restore();
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat("_DS27DebugMode", 0);
                Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
                Shader.SetGlobalFloat("_DS34ClawDiag", 0);
                foreach (var s in c.play.sheets) s.Release();
                c.spray.Release(); c.pal.Release(); c.claws.Release();
                if (c.coordMat != null) UnityEngine.Object.DestroyImmediate(c.coordMat);
            }
            rep.frames = frames.ToArray(); rep.verts = verts.ToArray(); rep.l191 = l191.ToArray(); rep.videos = vids.ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.files = files.ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render）。HMD 実機ではない。頭の揺れは座席のカメラを右の向きへずらしたもの（PS VR2 の頭の追跡ではない）。";
            File.WriteAllText(od + "/ds37_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS37_RENDER_DONE seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static float SwayAt(double t) => Sway * Mathf.Sin((float)(2.0 * Math.PI * t / SwayPeriod));

        static void Seek(Ctx c, double t, bool white, bool claws, bool spray)
        {
            c.play.Seek(t);
            c.spray.ApplyT(t);
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

        static void SetSway(Ctx c, string view, float dx)
        {
            if (!c.sway.TryGetValue(view, out var s)) { if (Mathf.Abs(dx) > 0) throw new InvalidOperationException("揺れの部品がない視点: " + view); return; }
            if (Mathf.Abs(dx) > 0) s.Apply(dx); else s.Restore();
        }

        static void CaptureColour(Ctx c, string view, float dx, string path)
        {
            var cam = c.cams[view];
            var hid = HideFor(c, view);
            SetSway(c, view, dx);
            try { CaptureRaw(cam, true, path); }
            finally { SetSway(c, view, 0f); foreach (var r in hid) r.enabled = true; }
        }

        static float[] M(Matrix4x4 m)
        {
            var f = new float[16];
            for (int r = 0; r < 4; r++) for (int k = 0; k < 4; k++) f[4 * r + k] = m[r, k];
            return f;
        }

        // 1 つの視点・時刻・揺れの色の画像（白の時間場あり、形成の組では白の時間場なしも）と面の座標とカメラの行列
        static FrameRec CaptureFrame(Ctx c, string kind, string view, float t, float dx, bool whiteOff, string dir)
        {
            var cam = c.cams[view];
            string tag = string.Format(CultureInfo.InvariantCulture, "{0}_t{1:00.00}s_dx{2:+0.00;-0.00;+0.00}", view, t, dx);
            var fr = new FrameRec { kind = kind, view = view, t = t, tau = (float)c.play.Tau, dx = dx, w = W, h = H };
            var hid = HideFor(c, view);
            SetSway(c, view, dx);
            try
            {
                fr.colourWhiteOn = dir + "/colour_" + tag + ".png";
                CaptureRaw(cam, true, fr.colourWhiteOn);
                if (whiteOff)
                {
                    // 白の時間場を使わない（終態の色区のまま）。形成の間も模様が UV-SDF と頂点の値だけで決まる
                    fr.colourWhiteOff = dir + "/colourW0_" + tag + ".png";
                    SetWhite(c, false);
                    try { CaptureRaw(cam, true, fr.colourWhiteOff); }
                    finally { SetWhite(c, true); }
                }
                fr.coord = dir + "/coord_" + tag + ".bin";
                CaptureCoord(c, cam, fr.coord);
                float asp = cam.aspect; cam.aspect = (float)W / H;
                fr.worldToCamera = M(cam.worldToCameraMatrix); fr.projection = M(cam.projectionMatrix);
                var p = cam.transform.position; fr.camPos = new[] { p.x, p.y, p.z };
                cam.aspect = asp;
            }
            finally { SetSway(c, view, 0f); foreach (var r in hid) r.enabled = true; }
            return fr;
        }

        // 白の時間場の入切（シートごとの MaterialPropertyBlock の _DS27WhiteEnabled。DS30SheetPlayer.Fill と同じ値へ戻す）
        static void SetWhite(Ctx c, bool on)
        {
            var mpb = new MaterialPropertyBlock();
            foreach (var s in c.sheets)
            {
                var r = s.Surface;
                r.GetPropertyBlock(mpb);
                mpb.SetFloat("_DS27WhiteEnabled", on && s.whiteEnabled ? 1f : 0f);
                r.SetPropertyBlock(mpb);
            }
        }

        static void CaptureCoord(Ctx c, Camera cam, string path)
        {
            var saved = new List<(Renderer r, Material m)>();
            var mpb = new MaterialPropertyBlock();
            bool lineOn = c.heroLine.enabled;
            try
            {
                foreach (var s in c.sheets)
                {
                    var r = s.Surface;
                    int id = s == c.hero ? 1 : (s == c.near ? 2 : (s == c.far ? 3 : 0));
                    saved.Add((r, r.sharedMaterial));
                    r.sharedMaterial = c.coordMat;
                    r.GetPropertyBlock(mpb); mpb.SetFloat("_DS37SheetId", id); r.SetPropertyBlock(mpb);
                }
                if (c.clawR != null && c.clawR.enabled)
                {
                    saved.Add((c.clawR, c.clawR.sharedMaterial));
                    c.clawR.sharedMaterial = c.coordMat;
                    c.clawR.GetPropertyBlock(mpb); mpb.SetFloat("_DS37SheetId", 4); c.clawR.SetPropertyBlock(mpb);
                }
                c.heroLine.enabled = false;
                var clear = cam.clearFlags; var bg = cam.backgroundColor; bool hdr = cam.allowHDR, aa = cam.allowMSAA;
                var prev = cam.targetTexture; float asp = cam.aspect;
                // batchmode では AsyncGPUReadback の一時の領域がコマの終わりまで解放されず、メモリーが尽きた（1 回目の実行）ので ReadPixels で読む
                var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGBFloat, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
                rt.Create();
                var tex = new Texture2D(W, H, TextureFormat.RGBAFloat, false, true);
                try
                {
                    cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0, 0, 0, 0);
                    cam.allowHDR = false; cam.allowMSAA = false; cam.aspect = (float)W / H; cam.targetTexture = rt;
                    cam.Render();
                    RenderTexture.active = rt;
                    tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
                    RenderTexture.active = null;
                    var src = tex.GetRawTextureData<float>();
                    // シートは R = 列 + 2000 × 番号（爪は R = 8000）、G = 行
                    var rg = new float[W * H * 2];
                    for (int i = 0; i < W * H; i++) { rg[2 * i] = src[4 * i]; rg[2 * i + 1] = src[4 * i + 1]; }
                    WriteFloats(path, rg);
                }
                finally
                {
                    RenderTexture.active = null;
                    cam.targetTexture = prev; cam.aspect = asp; cam.clearFlags = clear; cam.backgroundColor = bg; cam.allowHDR = hdr; cam.allowMSAA = aa;
                    UnityEngine.Object.DestroyImmediate(tex);
                    rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
                }
            }
            finally
            {
                foreach (var (r, m) in saved) r.sharedMaterial = m;
                c.heroLine.enabled = lineOn;
            }
        }

        static VertRec CaptureVerts(Ctx c, DS30SheetPlayer s, float t, string dir)
        {
            Directory.CreateDirectory(dir);
            int n = s.PackageMeta.rows * s.PackageMeta.cols;
            var outv = new Vector4[n * 2];
            using (var buf = new ComputeBuffer(n * 2, 16))
            {
                s.BindCompute(c.cs, c.kernel);
                c.cs.SetBuffer(c.kernel, "_DS27Out", buf);
                c.cs.SetInt("_DS27Count", n);
                c.cs.Dispatch(c.kernel, (n + 63) / 64, 1, 1);
                buf.GetData(outv);
            }
            var fl = new float[n * 3];
            for (int i = 0; i < n; i++) { var p = outv[2 * i]; fl[3 * i] = p.x; fl[3 * i + 1] = p.y; fl[3 * i + 2] = p.z; }
            var path = string.Format(CultureInfo.InvariantCulture, "{0}/verts_{1}_t{2:00.000}.bin", dir, s.sheetName, t);
            WriteFloats(path, fl);
            return new VertRec { sheet = s.sheetName, path = path, t = t, tau = (float)s.AppliedTau, count = n };
        }

        // 191 の事前検査：連続のコマの外殻線の画素（ID の描画のマゼンタ）を 1 bit に詰めて書く。主役波の頂点の画面の動きも記録する
        static L191Rec Line191(Ctx c, string view, int first, int count, string dir)
        {
            Directory.CreateDirectory(dir);
            var cam = c.cams[view];
            var path = dir + "/l191_" + view + "_lines.bin";
            var rec = new L191Rec { view = view, path = path, frames = count, w = W, h = H, firstFrame = first, heroMoveP99 = new float[count], heroMoveMax = new float[count], linePx = new int[count] };
            int n = c.hero.PackageMeta.rows * c.hero.PackageMeta.cols;
            var outv = new Vector4[n * 2];
            Vector2[] prevScr = null; bool[] prevIn = null;
            var clear = cam.clearFlags; var bg = cam.backgroundColor; bool hdr = cam.allowHDR, aa = cam.allowMSAA;
            var prevT = cam.targetTexture; float asp = cam.aspect;
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
            rt.Create();
            var ltex = new Texture2D(W, H, TextureFormat.RGBA32, false, true);
            var hid = HideFor(c, view);
            try
            {
                using (var fs = File.Create(path))
                using (var buf = new ComputeBuffer(n * 2, 16))
                {
                    var packed = new byte[W * H / 8];
                    Shader.SetGlobalFloat("_AF28IdMode", 1);
                    cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = Color.white;
                    cam.allowHDR = false; cam.allowMSAA = false; cam.aspect = (float)W / H;
                    for (int q = 0; q < count; q++)
                    {
                        double t = (first + q) / (double)Fps;
                        Seek(c, t, true, true, false);
                        cam.targetTexture = rt;
                        cam.Render();
                        RenderTexture.active = rt;
                        ltex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
                        RenderTexture.active = null;
                        var px = ltex.GetRawTextureData<Color32>();
                        Array.Clear(packed, 0, packed.Length);
                        int lp = 0;
                        for (int y = 0; y < H; y++)
                        {
                            int src = (H - 1 - y) * W; // 読み戻しは下の行から。表は上の行から
                            int dst = y * W;
                            for (int x = 0; x < W; x++)
                            {
                                var p = px[src + x];
                                if (p.r >= 250 && p.g <= 5 && p.b >= 250)
                                {
                                    int k = dst + x;
                                    packed[k >> 3] |= (byte)(0x80 >> (k & 7));
                                    lp++;
                                }
                            }
                        }
                        fs.Write(packed, 0, packed.Length);
                        rec.linePx[q] = lp;
                        // 主役波の頂点の画面の位置（このコマのカメラ）と前のコマからの動き
                        c.hero.BindCompute(c.cs, c.kernel);
                        c.cs.SetBuffer(c.kernel, "_DS27Out", buf);
                        c.cs.SetInt("_DS27Count", n);
                        c.cs.Dispatch(c.kernel, (n + 63) / 64, 1, 1);
                        buf.GetData(outv);
                        var vp = cam.projectionMatrix * cam.worldToCameraMatrix;
                        var scr = new Vector2[n]; var inn = new bool[n];
                        for (int i = 0; i < n; i++)
                        {
                            var w4 = vp * new Vector4(outv[2 * i].x, outv[2 * i].y, outv[2 * i].z, 1f);
                            if (w4.w <= 1e-4f) { inn[i] = false; continue; }
                            float sx = (w4.x / w4.w * 0.5f + 0.5f) * W, sy = (w4.y / w4.w * 0.5f + 0.5f) * H;
                            scr[i] = new Vector2(sx, sy);
                            inn[i] = sx >= 0 && sx < W && sy >= 0 && sy < H;
                        }
                        if (prevScr != null)
                        {
                            var mv = new List<float>();
                            for (int i = 0; i < n; i++) if (inn[i] && prevIn[i]) mv.Add((scr[i] - prevScr[i]).magnitude);
                            if (mv.Count > 0)
                            {
                                mv.Sort();
                                rec.heroMoveP99[q] = mv[Mathf.Min(mv.Count - 1, (int)(0.99 * mv.Count))];
                                rec.heroMoveMax[q] = mv[mv.Count - 1];
                            }
                        }
                        prevScr = scr; prevIn = inn;
                    }
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                RenderTexture.active = null;
                cam.targetTexture = prevT; cam.aspect = asp; cam.clearFlags = clear; cam.backgroundColor = bg; cam.allowHDR = hdr; cam.allowMSAA = aa;
                UnityEngine.Object.DestroyImmediate(ltex);
                rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
                foreach (var r in hid) r.enabled = true;
            }
            return rec;
        }

        static VideoRec Video(Ctx c, string name, string view, int n, Func<int, double> tOf, Func<int, float> dxOf, string od)
        {
            var sw = Stopwatch.StartNew();
            var mp4 = od + "/video/ds37_" + name + "_30fps.mp4";
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
                Seek(c, tOf(0), true, true, true);
                cb = new CommandBuffer { name = "DS37 飛沫" };
                c.spray.AddTo(cb);
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
                            // 設計37 修正1：揺れを外してから時刻を合わせ（船の上下が座席のカメラを置く）、そのあと揺れを足す
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
            }
            if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
            return new VideoRec { name = name, view = view, path = Path.GetFullPath(mp4), frames = n, fps = Fps, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = Sha(mp4) };
        }

        static void CaptureRaw(Camera camera, bool colour, string path)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture; float asp = camera.aspect;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = SkyTop;
            camera.allowHDR = false; camera.allowMSAA = colour;
            var rw = colour ? RenderTextureReadWrite.sRGB : RenderTextureReadWrite.Linear;
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, rw) { antiAliasing = colour ? 8 : 1 };
            var res = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, rw);
            rt.Create(); res.Create();
            camera.aspect = (float)W / H; camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(W, H, TextureFormat.RGB24, false, !colour);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev; camera.aspect = asp;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
        }

        static void WriteFloats(string path, float[] data)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var bytes = new byte[data.Length * 4];
            Buffer.BlockCopy(data, 0, bytes, 0, bytes.Length);
            File.WriteAllBytes(path, bytes);
        }

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
