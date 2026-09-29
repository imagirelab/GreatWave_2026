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
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design38.EditorTools
{
    // 設計38 第「輪郭線」部 Unity：必要な輪郭線（外殻線 v1 を主役波・周りの海 near・far へ、爪の縁の線と爪が重なる所の手前の線、継ぎ目をまたぐ線）を
    // 足し、線の点滅・跳び（191）、古い位置に残る線（192）、Mock の両眼の線の左右差、近くの線の太さを確かめるための描画（PC オフスクリーン描画、HMD ではない）。
    // 設計37 の場面 DS37_FlowLines.unity（読むだけ）を開き、次を足して DS38_Outlines.unity として保存する（設計27〜37 の場面・スクリプト・シェーダーは変えない）：
    //   ・DS38SheetOutline（主役波・near・far）：外殻線 v1 の材質（DS38 Outline Keypose）。主役波は設計27 の外殻線の子の材質を替え、outlineColInset 10 → 0。
    //   ・DS38ClawOutline（爪）：爪の縁の線（DS38 Outline Mesh）。
    //   ・DS38LineGlobals：原画のカメラの位置（原画視点の近くで、原画にない線と爪の線を描かない）。
    // そのあと次を書く：
    //   mask.  原画視点で原画にない線の頂点の印（t 10・11・11.5・12 s の原画視点で、主役波の面の外から 4 画素より内側に出た線の頂点。輪郭の 4 画素以内に出た頂点は除く）。
    //   t28.   t* の画像の組（t28_white・t28_claws。美術優先28修正01 と同じ名前。線は色の画像と line_ids に入り、_kstar と class_ids には入れない）。評価器は ds30b_tstar_regress.py。
    //   l191.  線の連続のコマ（t 2.0〜12.0 s の 301 コマ）× 視点 painting・seat・seat_toward_wave と、頭の揺れ（seat_toward_wave、t 9 s のまま目を ±0.1 m・周期 2 s で 301 コマ）：
    //          線の画素（MSAA なし）ごとの (番号, 列, 行, 中心眼からの距離) と、コマごとの各シート・爪の頂点の画面の動き。
    //   s192.  古い位置に残る線：l191 の中の 24 コマを、でたらめな順（前に別の時刻へ合わせてから）で描き直した線の画素と、面だけ（線なし）の画素の 1 bit。
    //   mock.  Mock の両眼：視点 seat・seat_toward_wave・seat_low × t 6・9・10.5・12 s × 左右の目（±0.032 m、中心眼は _DS38EyeOverride でそろえる）：線の画素と色の画像。
    //   near.  近くの線の太さ：t* の主役波の座席から最も近い点へ、座席の向きのまま 4・8・16 m まで寄せたカメラで、線（新しい決まり）と設計27 の外殻線 v0 の決まり。
    //   video. 形成の全区間（t 0〜14 s）の動画 painting・seat・seat_toward_wave、頭の揺れの動画（seat_toward_wave t 9 s）。
    // 引数：-ds38Out（既定 Build/Design/38/outlines/unity）、-ds38Skip scene,mask,t28,l191,s192,mock,near,video、-ds38MinPx（既定 1.5）。
    public static class DS38Render
    {
        const string Scene37 = "Assets/GreatWave/Design37/Scenes/DS37_FlowLines.unity";
        public const string Scene38 = "Assets/GreatWave/Design38/Scenes/DS38_Outlines.unity";
        const string MatDir = "Assets/GreatWave/Design38/Materials";
        const string SheetShader = "GreatWave/Design38/DS38 Outline Keypose";
        const string MeshShader = "GreatWave/Design38/DS38 Outline Mesh";
        const string CoordShaderName = "GreatWave/Design37/DS37 Surface Coord";
        const string OldLineMat = "Assets/GreatWave/Design27/Materials/DS27_Outline_Keypose.mat";
        const string CapturePath = "Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080, Fps = 30;
        const float TStar = 12f, TEnd = 14f, Sway = 0.1f, SwayPeriod = 2f, HalfIpd = 0.032f;
        const float PaintR0 = 5f, PaintR1 = 10f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);

        static string[] Protected => new[] {
            Scene37, "Assets/GreatWave/Design36/Scenes/DS36_Palette.unity", "Assets/GreatWave/Design34/Scenes/DS34_ThreeLayers.unity",
            "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity",
            "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs", "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs",
            "Assets/GreatWave/Design36/Scripts/DS36SeaPalette.cs", "Assets/GreatWave/Design36/Scripts/DS36ClawPalette.cs",
            "Assets/GreatWave/Design36/Shaders/DS36_Claw_Palette.shader", "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader",
            "Assets/GreatWave/Design27/Shaders/DS27_Outline_Keypose.shader", OldLineMat, "Assets/GreatWave/Design31/Shaders/DS31_Spray_Unlit.shader",
            "Assets/GreatWave/Design37/Scripts/DS37HeadSway.cs",
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
            public Dictionary<DS30SheetPlayer, DS38SheetOutline> lines = new Dictionary<DS30SheetPlayer, DS38SheetOutline>();
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public Dictionary<string, DS37HeadSway> sway = new Dictionary<string, DS37HeadSway>();
            public DS34ClawPlayer claws; public MeshRenderer clawR;
            public DS38ClawOutline clawLine;
            public DS34LayerSet layers;
            public DS31InstancedParticles spray;
            public DS36ClawPalette pal;
            public DS36SeaPalette seaPal;
            public DS38LineGlobals globals;
            public Material coordMat;
            public ComputeShader cs; public int kernel;
        }

        [Serializable] class MatRec { public string name, path, shader; public float lineAngle, maxWidth, minPx, backOnly, facingMin, pushBack, pushPaint, facingMode; public Color lineColour; }

        // 設計38 修正の回（進行役の検査の後の 1 回、Q26）で採った材質の値（候補 X2・X3 の試しから。進行役の判断・既定値）：
        //   主役波：奥への押し下げ 3 × 線幅（原画視点の重みを掛ける＝原画視点では 0）、表裏は原画視点の外だけ頂点の法線の和（2）。
        //           頭の揺れで唇の内側の縁の 1 px の細い線が出入りしたのを、押し下げで常に隠す（X3 で頭の揺れの出入り 0）。
        //   near：押し下げ 1 × 線幅、表裏はいつも頂点の法線の和（1）。右の高い波の稜線の段の扇の線（191 の塊の大半）を消す（X2）。
        //   爪：変えない（押し下げ 1 は爪が重なる所の手前の線を減らした。X3 で爪の線の画素 −30%）。
        //   値の組は（押し下げ、原画視点の重みを掛けるか、表裏の判定）。表裏の選別（_DS38BackOnly = 1）と _DS38FacingMin = 0 は修正1 のまま。
        static readonly Dictionary<string, float[]> Adopted = new Dictionary<string, float[]> {
            { "DS38_Outline_hero", new[] { 3f, 1f, 2f } }, { "DS38_Outline_near", new[] { 1f, 0f, 1f } }, { "DS38_Outline_claws", new[] { 0f, 0f, 0f } } };
        [Serializable] class MaskRec { public float[] times; public int interiorVerts, boundaryVerts, maskedVerts, interiorLinePx, boundaryLinePx; public string path, sha256; public float interiorPx; }
        [Serializable] class SeqRec { public string name, view, path; public int frames, firstFrame, w, h; public float swayAmp, holdT; public int[] linePx; public float[] moveMax, moveP99; public int[] linePxBySheet; }
        [Serializable] class S192Rec { public string view; public int frame; public float t, prevT; public int seqLinePx, redrawLinePx, diffPx; public string objPath; }
        [Serializable] class MockRec { public string view, eye; public float t, dx; public int linePx; public int[] bySheet; public string colour, lines; public float[] centre; }
        [Serializable] class NearRec { public string law, path; public float dist; public float[] camPos, target; public int linePx; public float fovDeg; }
        [Serializable] class VideoRec { public string name, view, path, sha256, ffmpegError; public int frames, fps; public float seconds; }
        [Serializable] class CamRec { public string name; public float[] pos; public float fovDeg, distToPainting; }
        [Serializable]
        class Report
        {
            public string unity, device, graphicsApi, scene38, scene38Sha256, noteJa, seqLayoutJa, maskLayoutJa, candidate;
            public float minPx, paintR0, paintR1, halfIpd, sway, swayPeriod; public int w, h, fps, heroOutlineColInsetBefore, heroOutlineColInsetAfter;
            public MatRec[] materials; public CamRec[] cameras; public MaskRec mask; public SeqRec[] seqs; public S192Rec[] s192; public MockRec[] mock; public NearRec[] near; public VideoRec[] videos;
            public string[] files, protectedFiles, changedFiles; public bool protectedUnchanged; public float secondsTotal;
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string od = Arg(a, "-ds38Out") ?? "Build/Design/38/outlines/unity";
            var skip = new HashSet<string>((Arg(a, "-ds38Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            float minPx = float.Parse(Arg(a, "-ds38MinPx") ?? "1.5", CultureInfo.InvariantCulture);
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var files = new List<string>();
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                minPx = minPx, paintR0 = PaintR0, paintR1 = PaintR1, halfIpd = HalfIpd, sway = Sway, swayPeriod = SwayPeriod, w = W, h = H, fps = Fps,
                seqLayoutJa = "コマごとに int32 の画素の数 n、続いて n 個 × 12 バイト（uint32 画素の番号 = y × W + x（y は上から）、uint16 番号（1 主役波・2 near・3 far・4 爪）、" +
                              "uint16 round(列 × 10)（爪は爪の番号 × 10）、uint16 round(行 × 10)（爪は輪の番号 × 10）、uint16 round(中心眼からの距離 m × 10)）",
                maskLayoutJa = "float32 × 主役波の頂点（行 × 列数 + 列）。1 描く、0 原画視点では描かない"
            };

            EditorSceneManager.OpenScene(Scene37, OpenSceneMode.Single);
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

            // ---- 線の材質（アセット）と部品を足す
            var oldHeroMat = c.hero.outline.sharedMaterial;
            Color lineColour = oldHeroMat.GetColor("_LineColor");
            float lineAngle = oldHeroMat.GetFloat("_LineAngle"), maxWidth = oldHeroMat.GetFloat("_MaxWidth");
            if (!AssetDatabase.IsValidFolder(MatDir)) AssetDatabase.CreateFolder("Assets/GreatWave/Design38", "Materials");
            var mats = new List<MatRec>();
            Func<string, string, Material> mk = (name, shader) =>
            {
                var sh = Shader.Find(shader);
                if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + shader);
                var path = MatDir + "/" + name + ".mat";
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (m == null) { m = new Material(sh); AssetDatabase.CreateAsset(m, path); }
                m.shader = sh;
                m.SetColor("_LineColor", lineColour); m.SetFloat("_LineAngle", lineAngle); m.SetFloat("_MaxWidth", maxWidth); m.SetFloat("_MinPx", minPx);
                m.SetFloat("_DS38BackOnly", 1f); m.SetFloat("_DS38FacingMin", 0f);
                float[] ad;
                if (Adopted.TryGetValue(name, out ad)) { m.SetFloat("_DS38PushBack", ad[0]); m.SetFloat("_DS38PushPaint", ad[1]); if (m.HasProperty("_DS38FacingMode")) m.SetFloat("_DS38FacingMode", ad[2]); }
                EditorUtility.SetDirty(m);
                mats.Add(new MatRec { name = name, path = path, shader = shader, lineAngle = lineAngle, maxWidth = maxWidth, minPx = minPx, lineColour = lineColour,
                    backOnly = m.GetFloat("_DS38BackOnly"), facingMin = m.GetFloat("_DS38FacingMin"), pushBack = m.GetFloat("_DS38PushBack"), pushPaint = m.GetFloat("_DS38PushPaint"),
                    facingMode = m.HasProperty("_DS38FacingMode") ? m.GetFloat("_DS38FacingMode") : 0f });
                return m;
            };
            // 設計38 修正1：far（遠くの海のうねり）には線を付けない。水平線の近くのうねりの輪郭は原画にない細い線で、視差と浅い角度でコマごと・目ごとに出入りした
            // （最初の評価の原画視点の跳びの塊と Mock の座席の低い視点の左右差）。near（手前の小波・谷・右の高い波・主役波への接続帯）と主役波に付ける。
            var ids = new Dictionary<string, int> { { "hero", 1 }, { "near", 2 } };
            rep.heroOutlineColInsetBefore = c.hero.outlineColInset;
            c.hero.outlineColInset = 0;   // 継ぎ目の上の 10 列にも線を描く（法線は列の範囲の中だけで求める）
            rep.heroOutlineColInsetAfter = c.hero.outlineColInset;
            foreach (var s in c.sheets)
            {
                if (!ids.ContainsKey(s.sheetName)) continue;
                var so = s.GetComponent<DS38SheetOutline>() ?? s.gameObject.AddComponent<DS38SheetOutline>();
                so.sheet = s; so.sheetId = ids[s.sheetName];
                so.lineMaterial = mk("DS38_Outline_" + s.sheetName, SheetShader);
                so.maskPath = s == c.hero ? "Build/Design/38/outlines/unity/prep/ds38_hero_linemask_f32.bin" : "";
                so.Attach();
                c.lines[s] = so;
            }
            c.clawLine = c.claws.GetComponent<DS38ClawOutline>() ?? c.claws.gameObject.AddComponent<DS38ClawOutline>();
            c.clawLine.claws = c.claws;
            c.clawLine.lineMaterial = mk("DS38_Outline_claws", MeshShader);
            c.clawLine.lineMaterial.SetFloat("_DS38SheetId", 4);
            c.clawLine.Attach();
            // 候補の試し（-ds38Candidate "hero:backOnly:facingMin[:pushBack[:pushPaint[:facingMode]]],near:…"）：材質のアセットを変えずに写しを使う。場面は保存しない（-ds38Skip scene と一緒に使う）
            string cand = Arg(a, "-ds38Candidate");
            if (!string.IsNullOrEmpty(cand))
            {
                foreach (var part in cand.Split(','))
                {
                    var q = part.Split(':');
                    var sh = c.sheets.FirstOrDefault(x => x.sheetName == q[0]);
                    Material cm;
                    if (sh != null && c.lines.ContainsKey(sh)) { cm = new Material(c.lines[sh].lineMaterial) { hideFlags = HideFlags.DontSave }; c.lines[sh].lineMaterial = cm; c.lines[sh].Attach(); }
                    else if (q[0] == "claws") { cm = new Material(c.clawLine.lineMaterial) { hideFlags = HideFlags.DontSave }; c.clawLine.lineMaterial = cm; c.clawLine.Attach(); }
                    else continue;
                    cm.SetFloat("_DS38BackOnly", float.Parse(q[1], CultureInfo.InvariantCulture));
                    cm.SetFloat("_DS38FacingMin", float.Parse(q[2], CultureInfo.InvariantCulture));
                    // 設計38 修正の回：4 つ目以降（任意）＝ 奥への押し下げ（線幅の倍数）、原画視点の重みを掛けるか、表裏の判定（0 面・1 頂点の法線の和。シートだけ）
                    if (q.Length > 3) cm.SetFloat("_DS38PushBack", float.Parse(q[3], CultureInfo.InvariantCulture));
                    if (q.Length > 4) cm.SetFloat("_DS38PushPaint", float.Parse(q[4], CultureInfo.InvariantCulture));
                    if (q.Length > 5) cm.SetFloat("_DS38FacingMode", float.Parse(q[5], CultureInfo.InvariantCulture));
                }
                rep.candidate = cand;
            }
            c.globals = c.play.GetComponent<DS38LineGlobals>() ?? c.play.gameObject.AddComponent<DS38LineGlobals>();
            c.globals.paintingCamera = c.cams["painting"]; c.globals.r0 = PaintR0; c.globals.r1 = PaintR1;
            c.globals.Apply();
            AssetDatabase.SaveAssets();
            rep.materials = mats.ToArray();
            var pc = c.cams["painting"].transform.position;
            rep.cameras = c.cams.Select(kv => new CamRec { name = kv.Key, pos = V(kv.Value.transform.position), fovDeg = kv.Value.fieldOfView, distToPainting = Vector3.Distance(kv.Value.transform.position, pc) }).ToArray();
            if (!skip.Contains("scene"))
            {
                if (!EditorSceneManager.SaveScene(scene, Scene38, true)) throw new InvalidOperationException("場面を保存できません: " + Scene38);
                rep.scene38 = Scene38; rep.scene38Sha256 = Sha(Scene38);
            }

            c.play.Prepare();
            c.spray.Load(); c.claws.Load();
            var hp = c.seaPal.SyncFromHero();
            c.pal.white = hp[0]; c.pal.mizuiro = hp[1]; c.pal.aiMid = hp[2]; c.pal.aiDark = hp[3];
            c.pal.Apply();
            foreach (var so in c.lines.Values) so.BindMask();
            var sh37 = Shader.Find(CoordShaderName);
            if (sh37 == null) throw new InvalidOperationException("シェーダーがありません: " + CoordShaderName);
            c.coordMat = new Material(sh37) { hideFlags = HideFlags.DontSave };
            c.cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(CapturePath);
            c.kernel = c.cs.FindKernel("DS27Capture");
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS38LineCoordMode", 0);
            Shader.SetGlobalVector("_DS38EyeOverride", Vector4.zero);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
            Shader.SetGlobalFloat("_DS34ClawDiag", 0);
            Shader.SetGlobalFloat("_DS36ClawFaceDiag", 0);

            var seqs = new List<SeqRec>(); var s192 = new List<S192Rec>(); var mock = new List<MockRec>(); var nears = new List<NearRec>(); var vids = new List<VideoRec>();
            try
            {
                // ---- mask：原画視点で原画にない線の頂点
                string maskPath = od + "/prep/ds38_hero_linemask_f32.bin";
                if (!skip.Contains("mask"))
                {
                    rep.mask = BuildMask(c, new[] { 10f, 11f, 11.5f, 12f }, maskPath, od + "/prep");
                    files.Add(maskPath);
                }
                if (File.Exists(maskPath))
                {
                    var b = File.ReadAllBytes(maskPath);
                    var m = new float[b.Length / 4]; Buffer.BlockCopy(b, 0, m, 0, b.Length);
                    c.lines[c.hero].BindMask(m);
                }
                if (!skip.Contains("t28"))
                {
                    Seek(c, TStar, true, false, false);
                    files.AddRange(RenderT28(c, od + "/t28_white/t28/render"));
                    Seek(c, TStar, true, true, false);
                    files.AddRange(RenderT28(c, od + "/t28_claws/t28/render"));
                }
                if (!skip.Contains("l191"))
                {
                    foreach (var v in new[] { "painting", "seat", "seat_toward_wave" })
                        seqs.Add(Sequence(c, "form_" + v, v, 60, 301, i => (60 + i) / (double)Fps, i => 0f, od + "/l191"));
                    seqs.Add(Sequence(c, "sway_seat_toward_wave_t09", "seat_toward_wave", 0, 301, i => 9.0, i => SwayAt(i / (double)Fps), od + "/l191"));
                }
                if (!skip.Contains("s192"))
                {
                    var rnd = new System.Random(38192);
                    foreach (var v in new[] { "painting", "seat_toward_wave" })
                    {
                        var qs = Enumerable.Range(0, 24).Select(k => 60 + 12 * k + rnd.Next(0, 12)).ToList();
                        qs = qs.OrderBy(_ => rnd.Next()).ToList();
                        foreach (var q in qs)
                        {
                            double prev = rnd.NextDouble() * 14.0;
                            s192.Add(Redraw(c, v, q, prev, od + "/s192"));
                        }
                    }
                }
                if (!skip.Contains("mock"))
                {
                    foreach (var t in new[] { 6f, 9f, 10.5f, 12f })
                    {
                        Seek(c, t, true, true, false);
                        foreach (var v in new[] { "seat", "seat_toward_wave", "seat_low" })
                            foreach (var e in new[] { -1, 1 })
                                mock.Add(MockEye(c, v, t, e, od + "/mock"));
                    }
                }
                if (!skip.Contains("near")) nears.AddRange(NearProbe(c, od + "/near"));
                if (!skip.Contains("video"))
                {
                    Directory.CreateDirectory(od + "/video");
                    int nF = Mathf.RoundToInt(TEnd * Fps) + 1, nS = 4 * Fps + 1;
                    vids.Add(Video(c, "formation_painting", "painting", nF, i => i / (double)Fps, i => 0f, od));
                    vids.Add(Video(c, "formation_seat", "seat", nF, i => i / (double)Fps, i => 0f, od));
                    vids.Add(Video(c, "formation_seat_toward_wave", "seat_toward_wave", nF, i => i / (double)Fps, i => 0f, od));
                    vids.Add(Video(c, "sway_seat_toward_wave_t09", "seat_toward_wave", nS, i => 9.0, i => SwayAt(i / (double)Fps), od));
                }
            }
            finally
            {
                foreach (var s in c.sway.Values) s.Restore();
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat("_DS38LineCoordMode", 0);
                Shader.SetGlobalVector("_DS38EyeOverride", Vector4.zero);
                Shader.SetGlobalFloat("_DS27DebugMode", 0);
                Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
                Shader.SetGlobalFloat("_DS34ClawDiag", 0);
                foreach (var so in c.lines.Values) so.ReleaseMask();
                foreach (var s in c.play.sheets) s.Release();
                c.spray.Release(); c.pal.Release(); c.clawLine.Release(); c.claws.Release();
                if (c.coordMat != null) UnityEngine.Object.DestroyImmediate(c.coordMat);
            }
            rep.seqs = seqs.ToArray(); rep.s192 = s192.ToArray(); rep.mock = mock.ToArray(); rep.near = nears.ToArray(); rep.videos = vids.ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.files = files.ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render）。HMD 実機ではない。Mock の両眼は座席のカメラを右の向きへ ±0.032 m ずらした 2 回の描画（中心眼は _DS38EyeOverride でそろえた）で、PS VR2 の立体視（SPI）ではない。";
            File.WriteAllText(od + "/ds38_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS38_RENDER_DONE seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static float[] V(Vector3 v) => new[] { v.x, v.y, v.z };
        static float SwayAt(double t) => Sway * Mathf.Sin((float)(2.0 * Math.PI * t / SwayPeriod));

        static void Seek(Ctx c, double t, bool white, bool claws, bool spray)
        {
            c.play.Seek(t);
            c.spray.ApplyT(t);
            c.claws.ApplyT(t);
            c.layers.whiteBand = white; c.layers.clawsOn = claws; c.layers.sprayOn = spray;
            c.layers.ApplyToggles();
            c.clawLine.Sync();
        }

        static IEnumerable<Renderer> LineRenderers(Ctx c)
        {
            foreach (var s in c.sheets) if (s.outline != null) yield return s.outline;
            if (c.clawLine.Line != null) yield return c.clawLine.Line;
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
                rr.enabled = false; hid.Add(rr);
            }
            return hid;
        }

        static void SetSway(Ctx c, string view, float dx)
        {
            if (!c.sway.TryGetValue(view, out var s)) { if (Mathf.Abs(dx) > 0) throw new InvalidOperationException("揺れの部品がない視点: " + view); return; }
            if (Mathf.Abs(dx) > 0) s.Apply(dx); else s.Restore();
        }

        // ---- 描画の小道具
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

        // 線の座標の描画（_DS38LineCoordMode）。線の画素（R ≥ 10）を上の行からの順で返す
        struct LinePx { public int idx; public ushort sheet, col, row, dist; }
        static List<LinePx> LineCoord(Ctx c, Camera cam, int w, int h)
        {
            Shader.SetGlobalFloat("_DS38LineCoordMode", 1);
            float[] f;
            try { f = RenderFloat(cam, w, h); }
            finally { Shader.SetGlobalFloat("_DS38LineCoordMode", 0); }
            var list = new List<LinePx>();
            for (int y = 0; y < h; y++)
            {
                int src = (h - 1 - y) * w;
                for (int x = 0; x < w; x++)
                {
                    int k = 4 * (src + x);
                    float r = f[k];
                    if (r < 10.5f) continue;
                    list.Add(new LinePx
                    {
                        idx = y * w + x, sheet = (ushort)Mathf.RoundToInt(r - 10f),
                        col = (ushort)Mathf.Clamp(Mathf.RoundToInt(f[k + 1] * 10f), 0, 65535), row = (ushort)Mathf.Clamp(Mathf.RoundToInt(f[k + 2] * 10f), 0, 65535),
                        dist = (ushort)Mathf.Clamp(Mathf.RoundToInt(f[k + 3] * 10f), 0, 65535)
                    });
                }
            }
            return list;
        }

        // 面の座標（DS37 Surface Coord。線を切る）：R = 列 + 2000 × 番号（1 主役波・2 near・3 far、爪 8000）。上の行からの順の R を返す
        static float[] SurfaceCoord(Ctx c, Camera cam, int w, int h)
        {
            var saved = new List<(Renderer r, Material m)>();
            var mpb = new MaterialPropertyBlock();
            var lineState = LineRenderers(c).Select(r => (r, r.enabled)).ToList();
            var clawMats = c.clawR.sharedMaterials;
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
                if (c.clawR.enabled)
                {
                    var cm = new Material[clawMats.Length];
                    for (int i = 0; i < cm.Length; i++) cm[i] = c.coordMat;
                    c.clawR.sharedMaterials = cm;
                    c.clawR.GetPropertyBlock(mpb); mpb.SetFloat("_DS37SheetId", 4); c.clawR.SetPropertyBlock(mpb);
                }
                foreach (var (r, _) in lineState) r.enabled = false;
                var f = RenderFloat(cam, w, h);
                var o = new float[w * h];
                for (int y = 0; y < h; y++) { int src = (h - 1 - y) * w; for (int x = 0; x < w; x++) o[y * w + x] = f[4 * (src + x)]; }
                return o;
            }
            finally
            {
                foreach (var (r, m) in saved) r.sharedMaterial = m;
                c.clawR.sharedMaterials = clawMats;
                foreach (var (r, e) in lineState) r.enabled = e;
            }
        }

        // ---- mask
        static MaskRec BuildMask(Ctx c, float[] times, string path, string dir)
        {
            Directory.CreateDirectory(dir);
            int nu = c.hero.PackageMeta.cols, nv = c.hero.PackageMeta.rows, n = nu * nv;
            var interior = new bool[n]; var boundary = new bool[n];
            int ipx = 0, bpx = 0;
            var cam = c.cams["painting"];
            // 印を外した（全部 1）状態で数える
            var ones = new float[n]; for (int i = 0; i < n; i++) ones[i] = 1f;
            c.lines[c.hero].BindMask(ones);
            foreach (var t in times)
            {
                Seek(c, t, true, true, false);
                var surf = SurfaceCoord(c, cam, W, H);
                // 主役波（と爪）の面：R が 2000〜3000 か 8000
                var inside = new bool[W * H];
                for (int i = 0; i < W * H; i++) { float r = surf[i]; inside[i] = (r >= 2000f && r < 3000f) || (r >= 7999f && r < 8001f); }
                var dist = Chamfer(inside, W, H);
                var lp = LineCoord(c, cam, W, H);
                foreach (var p in lp)
                {
                    if (p.sheet != 1) continue;
                    int col = Mathf.Clamp(Mathf.RoundToInt(p.col / 10f), 0, nu - 1), row = Mathf.Clamp(Mathf.RoundToInt(p.row / 10f), 0, nv - 1);
                    int v = row * nu + col;
                    if (dist[p.idx] > 4f) { interior[v] = true; ipx++; } else { boundary[v] = true; bpx++; }
                }
            }
            var mask = new float[n];
            int masked = 0;
            for (int v = 0; v < n; v++) mask[v] = 1f;
            for (int v = 0; v < n; v++)
            {
                if (!interior[v] || boundary[v]) continue;
                int r = v / nu, cc = v % nu;
                for (int dr = -1; dr <= 1; dr++)
                    for (int dc = -1; dc <= 1; dc++)
                    {
                        int rr = r + dr, c2 = cc + dc;
                        if (rr < 0 || rr >= nv || c2 < 0 || c2 >= nu) continue;
                        int u = rr * nu + c2;
                        if (boundary[u]) continue;
                        mask[u] = 0f;
                    }
            }
            for (int v = 0; v < n; v++) if (mask[v] < 0.5f) masked++;
            var bytes = new byte[n * 4];
            Buffer.BlockCopy(mask, 0, bytes, 0, bytes.Length);
            File.WriteAllBytes(path, bytes);
            return new MaskRec { times = times, interiorVerts = interior.Count(x => x), boundaryVerts = boundary.Count(x => x), maskedVerts = masked, interiorLinePx = ipx, boundaryLinePx = bpx, interiorPx = 4f, path = Path.GetFullPath(path), sha256 = Sha(path) };
        }

        // 外（inside = false）までの距離（画素。3-4 の chamfer を 3 で割った近似）
        static float[] Chamfer(bool[] inside, int w, int h)
        {
            var d = new float[w * h];
            const float INF = 1e9f;
            for (int i = 0; i < w * h; i++) d[i] = inside[i] ? INF : 0f;
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    int i = y * w + x; if (d[i] == 0f) continue;
                    float m = d[i];
                    if (x > 0) m = Math.Min(m, d[i - 1] + 3);
                    if (y > 0) { m = Math.Min(m, d[i - w] + 3); if (x > 0) m = Math.Min(m, d[i - w - 1] + 4); if (x < w - 1) m = Math.Min(m, d[i - w + 1] + 4); }
                    d[i] = m;
                }
            for (int y = h - 1; y >= 0; y--)
                for (int x = w - 1; x >= 0; x--)
                {
                    int i = y * w + x; if (d[i] == 0f) continue;
                    float m = d[i];
                    if (x < w - 1) m = Math.Min(m, d[i + 1] + 3);
                    if (y < h - 1) { m = Math.Min(m, d[i + w] + 3); if (x < w - 1) m = Math.Min(m, d[i + w + 1] + 4); if (x > 0) m = Math.Min(m, d[i + w - 1] + 4); }
                    d[i] = m;
                }
            for (int i = 0; i < w * h; i++) d[i] /= 3f;
            return d;
        }

        // ---- t28（DS36Render.RenderT28 と同じ組。線はすべての線のレンダラーを同じに入切する）
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

        // ---- 191：連続のコマの線の画素と頂点の画面の動き
        static SeqRec Sequence(Ctx c, string name, string view, int first, int count, Func<int, double> tOf, Func<int, float> dxOf, string dir)
        {
            Directory.CreateDirectory(dir);
            var cam = c.cams[view];
            var path = dir + "/l191_" + name + ".bin";
            var rec = new SeqRec { name = name, view = view, path = Path.GetFullPath(path), frames = count, firstFrame = first, w = W, h = H, linePx = new int[count], moveMax = new float[count], moveP99 = new float[count], linePxBySheet = new int[5] };
            if (name.StartsWith("sway")) { rec.swayAmp = Sway; rec.holdT = (float)tOf(0); }
            var hid = HideFor(c, view);
            Vector2[][] prev = null; bool[][] prevIn = null;
            try
            {
                using (var fs = File.Create(path))
                using (var bw = new BinaryWriter(fs))
                {
                    for (int q = 0; q < count; q++)
                    {
                        SetSway(c, view, 0f);
                        Seek(c, tOf(q), true, true, false);
                        SetSway(c, view, dxOf(q));
                        var lp = LineCoord(c, cam, W, H);
                        bw.Write(lp.Count);
                        foreach (var p in lp) { bw.Write((uint)p.idx); bw.Write(p.sheet); bw.Write(p.col); bw.Write(p.row); bw.Write(p.dist); if (p.sheet < 5) rec.linePxBySheet[p.sheet]++; }
                        rec.linePx[q] = lp.Count;
                        // 頂点の画面の位置（主役波・near・far・爪）と前のコマからの動き
                        var scr = ScreenVerts(c, cam, out var inn);
                        if (prev != null)
                        {
                            var mv = new List<float>();
                            for (int s = 0; s < scr.Length; s++)
                                for (int i = 0; i < scr[s].Length; i++) if (inn[s][i] && prevIn[s][i]) mv.Add((scr[s][i] - prev[s][i]).magnitude);
                            if (mv.Count > 0) { mv.Sort(); rec.moveP99[q] = mv[Mathf.Min(mv.Count - 1, (int)(0.99 * mv.Count))]; rec.moveMax[q] = mv[mv.Count - 1]; }
                        }
                        prev = scr; prevIn = inn;
                    }
                }
            }
            finally { SetSway(c, view, 0f); foreach (var r in hid) r.enabled = true; }
            return rec;
        }

        static Vector2[][] ScreenVerts(Ctx c, Camera cam, out bool[][] inn)
        {
            float asp = cam.aspect; cam.aspect = (float)W / H;
            var vp = cam.projectionMatrix * cam.worldToCameraMatrix;
            cam.aspect = asp;
            var lists = new List<Vector3[]>();
            foreach (var s in new[] { c.hero, c.near, c.far })
            {
                if (s == null) continue;
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
                var p = new Vector3[n];
                for (int i = 0; i < n; i++) p[i] = outv[2 * i];
                lists.Add(p);
            }
            if (c.clawR.enabled) lists.Add(c.claws.Current);
            var res = new Vector2[lists.Count][]; inn = new bool[lists.Count][];
            for (int s = 0; s < lists.Count; s++)
            {
                var p = lists[s]; res[s] = new Vector2[p.Length]; inn[s] = new bool[p.Length];
                for (int i = 0; i < p.Length; i++)
                {
                    var w4 = vp * new Vector4(p[i].x, p[i].y, p[i].z, 1f);
                    if (w4.w <= 1e-4f) continue;
                    float sx = (w4.x / w4.w * 0.5f + 0.5f) * W, sy = (w4.y / w4.w * 0.5f + 0.5f) * H;
                    res[s][i] = new Vector2(sx, sy);
                    inn[s][i] = sx >= 0 && sx < W && sy >= 0 && sy < H;
                }
            }
            return res;
        }

        // ---- 192：でたらめな順で描き直す（前に別の時刻 prev へ合わせて 1 回描く）
        static S192Rec Redraw(Ctx c, string view, int frame, double prevT, string dir)
        {
            Directory.CreateDirectory(dir);
            var cam = c.cams[view];
            var hid = HideFor(c, view);
            try
            {
                double t = frame / (double)Fps;
                Seek(c, prevT, true, true, false);
                LineCoord(c, cam, W, H);   // 前の時刻で 1 回描く（何かが持ち越されるなら、ここで残る）
                Seek(c, t, true, true, false);
                var lp = LineCoord(c, cam, W, H);
                // 面だけの 1 bit は背景（船・富士など）を切って描く（線は背景の手前にも出るので、面が背景に隠れた所の線を外れと数えない。修正1 の測り方の直し）
                float[] surf;
                c.ctx.SetActive(false);
                try { surf = SurfaceCoord(c, cam, W, H); }
                finally { c.ctx.SetActive(true); }
                var tag = string.Format(CultureInfo.InvariantCulture, "{0}_f{1:000}", view, frame);
                var lpath = dir + "/redraw_" + tag + ".bin";
                using (var bw = new BinaryWriter(File.Create(lpath)))
                {
                    bw.Write(lp.Count);
                    foreach (var p in lp) { bw.Write((uint)p.idx); bw.Write(p.sheet); bw.Write(p.col); bw.Write(p.row); bw.Write(p.dist); }
                }
                var opath = dir + "/obj_" + tag + ".bin";
                var bits = new byte[W * H / 8];
                for (int i = 0; i < W * H; i++) if (surf[i] >= 1000f) bits[i >> 3] |= (byte)(0x80 >> (i & 7));
                File.WriteAllBytes(opath, bits);
                return new S192Rec { view = view, frame = frame, t = (float)t, prevT = (float)prevT, redrawLinePx = lp.Count, objPath = Path.GetFullPath(opath) };
            }
            finally { foreach (var r in hid) r.enabled = true; }
        }

        // ---- Mock の両眼
        static MockRec MockEye(Ctx c, string view, float t, int eye, string dir)
        {
            Directory.CreateDirectory(dir);
            var cam = c.cams[view];
            var tr = cam.transform;
            var p0 = tr.position;
            var hid = HideFor(c, view);
            try
            {
                Shader.SetGlobalVector("_DS38EyeOverride", new Vector4(p0.x, p0.y, p0.z, 1f));
                tr.position = p0 + tr.right * (eye * HalfIpd);
                var tag = string.Format(CultureInfo.InvariantCulture, "{0}_t{1:00.0}s_{2}", view, t, eye < 0 ? "L" : "R");
                var lp = LineCoord(c, cam, W, H);
                var lpath = dir + "/lines_" + tag + ".bin";
                using (var bw = new BinaryWriter(File.Create(lpath)))
                {
                    bw.Write(lp.Count);
                    foreach (var p in lp) { bw.Write((uint)p.idx); bw.Write(p.sheet); bw.Write(p.col); bw.Write(p.row); bw.Write(p.dist); }
                }
                var cpath = dir + "/colour_" + tag + ".png";
                CaptureRaw(cam, W, H, true, SkyTop, cpath);
                var by = new int[5]; foreach (var p in lp) if (p.sheet < 5) by[p.sheet]++;
                return new MockRec { view = view, eye = eye < 0 ? "L" : "R", t = t, dx = eye * HalfIpd, linePx = lp.Count, bySheet = by, colour = Path.GetFullPath(cpath), lines = Path.GetFullPath(lpath), centre = V(p0) };
            }
            finally
            {
                tr.position = p0;
                Shader.SetGlobalVector("_DS38EyeOverride", Vector4.zero);
                foreach (var r in hid) r.enabled = true;
            }
        }

        // ---- 近くの線の太さ：t* の主役波の座席から最も近い見える頂点へ寄せたカメラ
        static List<NearRec> NearProbe(Ctx c, string dir)
        {
            Directory.CreateDirectory(dir);
            var res = new List<NearRec>();
            Seek(c, TStar, true, true, false);
            var seat = c.cams["seat"];
            var go = new GameObject("DS38 近くの線の確かめ（一時）") { hideFlags = HideFlags.DontSave };
            var cam = go.AddComponent<Camera>();
            cam.CopyFrom(seat);
            cam.enabled = false;
            try
            {
                int n = c.hero.PackageMeta.rows * c.hero.PackageMeta.cols;
                var outv = new Vector4[n * 2];
                using (var buf = new ComputeBuffer(n * 2, 16))
                {
                    c.hero.BindCompute(c.cs, c.kernel);
                    c.cs.SetBuffer(c.kernel, "_DS27Out", buf);
                    c.cs.SetInt("_DS27Count", n);
                    c.cs.Dispatch(c.kernel, (n + 63) / 64, 1, 1);
                    buf.GetData(outv);
                }
                // 座席の視野の中央の 60% にある主役波の描く列（colMin〜colMax）の頂点で、座席から最も近いもの
                var sp = seat.transform.position; float asp = seat.aspect; seat.aspect = (float)W / H;
                var vp = seat.projectionMatrix * seat.worldToCameraMatrix; seat.aspect = asp;
                int nu = c.hero.PackageMeta.cols; float best = float.MaxValue; Vector3 tgt = Vector3.zero;
                for (int i = 0; i < n; i++)
                {
                    int col = i % nu; if (col < c.hero.colMin + 2 || col > c.hero.colMax - 2) continue;
                    var p = (Vector3)outv[2 * i];
                    var w4 = vp * new Vector4(p.x, p.y, p.z, 1f);
                    if (w4.w <= 1e-3f) continue;
                    float x = w4.x / w4.w, y = w4.y / w4.w;
                    if (Mathf.Abs(x) > 0.6f || Mathf.Abs(y) > 0.6f) continue;
                    float d = Vector3.Distance(p, sp);
                    if (d < best) { best = d; tgt = p; }
                }
                var dirv = (tgt - sp).normalized;
                var oldMat = AssetDatabase.LoadAssetAtPath<Material>(OldLineMat);
                var heroLine = c.hero.outline;
                var newMat = heroLine.sharedMaterial;
                foreach (var dist in new[] { 4f, 8f, 16f })
                {
                    cam.transform.position = tgt - dirv * dist;
                    cam.transform.rotation = Quaternion.LookRotation(dirv, Vector3.up);
                    foreach (var law in new[] { "ds38", "ds27_v0" })
                    {
                        heroLine.sharedMaterial = law == "ds38" ? newMat : oldMat;
                        var tag = string.Format(CultureInfo.InvariantCulture, "{0}_{1:00}m", law, dist);
                        Shader.SetGlobalFloat("_AF28IdMode", 1);
                        var ids = CaptureRaw(cam, W, H, false, IdSky, dir + "/ids_" + tag + ".png");
                        Shader.SetGlobalFloat("_AF28IdMode", 0);
                        CaptureRaw(cam, W, H, true, SkyTop, dir + "/colour_" + tag + ".png");
                        int lpx = ids.Count(p => p.r >= 250 && p.g <= 5 && p.b >= 250);
                        res.Add(new NearRec { law = law, dist = dist, path = Path.GetFullPath(dir + "/ids_" + tag + ".png"), camPos = V(cam.transform.position), target = V(tgt), linePx = lpx, fovDeg = cam.fieldOfView });
                    }
                    heroLine.sharedMaterial = newMat;
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                UnityEngine.Object.DestroyImmediate(go);
            }
            return res;
        }

        static VideoRec Video(Ctx c, string name, string view, int n, Func<int, double> tOf, Func<int, float> dxOf, string od)
        {
            var sw = Stopwatch.StartNew();
            var mp4 = od + "/video/ds38_" + name + "_30fps.mp4";
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
                cb = new CommandBuffer { name = "DS38 飛沫" };
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

        static Color32[] CaptureRaw(Camera camera, int w, int h, bool colour, Color bgc, string path)
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
            }
            camera.targetTexture = prev; camera.aspect = asp;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return px;
        }

        static string Capture(Camera camera, int w, int h, bool colour, string path)
        {
            CaptureRaw(camera, w, h, colour, colour ? (Color)SkyTop : IdSky, path);
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
