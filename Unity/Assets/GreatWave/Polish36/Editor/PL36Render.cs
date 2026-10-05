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
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using GreatWave.Polish29;
using GreatWave.Polish30;

namespace GreatWave.Polish36.EditorTools
{
    // 仕上げ36（設計36 限定色）の描画：仕上げ33 の PL33Render を写し（PL33Render のファイルは変えない）、主役波の材質を -pl36HeroMat で選べるようにした。
    //   前：-pl36HeroMat Assets/GreatWave/Polish29/Materials/PL29_Ukiyoe_Hero.mat ＋ -pl29ParamFile Tools/GWWaveGen/pl29/pl29_material_params.txt（仕上げ33修正01・35 の状態）。
    //   後（既定）：Assets/GreatWave/Polish36/Materials/PL36_Ukiyoe_Hero.mat（PL36 Ukiyoe Keypose：爪の帯の藍の地と淡い水色の輪、谷の底の段）＋
    //     -pl29ParamFile Tools/GWWaveGen/pl36/pl36_material_params.txt。
    //   面の座標の画像の段（fields）は -pl36FieldModes で _PL29Diag の番号を選ぶ（既定 3,4,5,6。12 は爪の帯と谷の底の印）。
    // ── 以下は写した仕上げ33 の説明 ──
    // 仕上げ33（設計33 爪の造形）の描画：仕上げ32 の PL32Render を写し、-pl33Look 1 で爪の層に PL33ClawLook（鉤の内の膜を水色の版にし、
    //   膜の縁の線を出さない。縁の線の材質は PL33 Claw Outline）を付けて描く。爪の並びは -pl32Claws（Build/Polish/33/claws：原画の爪を射線の向きへ
    //   立ち上げた帯 ＋ 鉤の内の膜 ＋ 頂の裏の冠の爪）。前（仕上げ32 修正の回 1）は -pl32Claws Build/Polish/32/fix01/claws/ds33_claw_layout.json -pl33Look 0。
    // ── 以下は写した仕上げ32 の説明 ──
    // 仕上げ32（設計32 白波群と ID・爪の一覧）の描画：仕上げ31 の PL31Render を写し、爪の並び（DS34ClawPlayer の layoutPath）を -pl32Claws で替えて描く。
    //  前：仕上げ31 の状態（-pl29HeroPkg Build/Polish/31/white/hero_pkg、爪は設計33 の Build/Design/33/claws。-pl32Claws を渡さない）。
    //  後：-pl29HeroPkg Build/Polish/32/white/hero_pkg（pl32_white.py）と -pl32Claws Build/Polish/32/claws/ds33_claw_layout.json（pl32_claws.py。
    //    仕上げ32 の一覧（b区域の爪を加えた 209 本）を K*′ P28R2rec のシートへ結び付け直した帯）。
    // ── 以下は写した仕上げ31 の説明 ──
    // 仕上げ31（設計31 白波の発生と飛沫）の描画：仕上げ30 の PL30Render を写し、主役波の T_white と飛沫を替えて描く。
    //  前（-pl31Old 1）：仕上げ30 の状態（主役波の T_white は G_p28rec の art_on、飛沫は設計31 の 186 粒 Build/Design/31/spray）。
    //  後（既定）：主役波のパッケージを -pl29HeroPkg（pl31_white.py の hero_pkg。T_white だけ差し替え）、飛沫を -pl31Spray のフォルダーの
    //    <stem>_tone0_frames.json（白・生成り）と <stem>_tone1_frames.json（灰の白）の 2 つの DS31InstancedParticles にする（stem は -pl31SprayStem、既定 pl31_spray）。
    //  仕上げ31 で足した段：white（色区 ID を T_white あり・なしで描き、176・102 の内側を数える）、full の飛沫なしの画像（飛沫の印の差分）。
    //  回り台（tt）と動画は既定で作品のまま（爪・飛沫あり。-pl31TtSpray 0・-pl31VideoAsis 0 で仕上げ30 と同じ）。
    // ── 以下は写した仕上げ30 の説明 ──
    // 仕上げ30（設計30 周りの海）の描画：仕上げ29 の PL29Render を写し、周りの海を替えて描く。
    //  前（-pl30Old 1）：仕上げ29 の状態（主役波は K*′ P28R2rec・G_p28rec・PL29 Ukiyoe Keypose、爪は PL29 Claw Shade、海は設計30 のパッケージと設計36 の t* の高さの段）。
    //  後（既定）：海を -pl30Sea のパッケージ（pl30_sea_generate.py。G_p28rec の境の輪につないだ near・far、右の高い波・肩の稜・小波）にし、
    //    材質を PL30 Ukiyoe Sea Keypose（面の座標 pl30_sea_attr_f32.bin、今の高さで白と谷の段）にする。座席の船の上下は同じフォルダーの boat_support.json。
    //    遠い海にも外殻線（設計38 の near と同じ材質の写し）を付ける（-pl30FarLine 1）。仮置き M1_Revision_LeftSupport は -pl30HideLeft 1 で隠し、
    //    -pl30LeftMound <obj> があれば、その静的な水の盛り上がり（pl30_left_mound.py）を同じ海の材質で置く。
    // 視点・時刻は PL29Render と同じ（前後の図を同じ視点・同じ時刻で並べる）。回り台は -pl30TtSea 1（既定）で周りの海を隠さない（仕上げ30 は海の群）。
    // 段（-pl29Skip・-pl29Only は PL29Render と同じ名前）：views・ids・tt・t28・full・video・f71・fields と、仕上げ30 の
    //   fuji.  原画視点 t 5〜10.5 s（0.25 s おき）と t* の、富士の雪・山腹の見える画素（富士の材質だけ ID の色、ほかは ID、海・主役波は色区の ID）
    //   s5.    コマ 180〜190 の原画視点・座席から波の方向・左の側面（S5-1 のコマ 184→185 の跳び）と、座席 v1 のコマ 270〜300（S5-3 の稜線の段・F7-2 の線）
    // 場面・スクリプト・シェーダー・材質のファイルは変えない（守るファイルの SHA-256 を前後で比べる）。PC オフスクリーン描画で、HMD 実機ではない。
    public static class PL36Render
    {
        const string Scene39 = "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080, Fps = 30;
        const float TStar = 12f, TEnd = 14f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Vector3 E = new Vector3(0.6798348938056157f, 0f, 0.733365200404483f);
        static readonly Vector3 Tdir = new Vector3(0.7333652004044829f, 0f, -0.6798348938056156f);
        static readonly Vector4 IdSkyV = new Vector4(0, 1, 1, 1), IdOtherV = new Vector4(0, 0, 0, 1);
        static readonly Dictionary<string, Vector4> IdBoats = new Dictionary<string, Vector4> {
            { "boat_left", new Vector4(0.4f, 0, 0, 1) }, { "boat_mid", new Vector4(0, 0.4f, 0, 1) }, { "boat_fg", new Vector4(0.4f, 0.4f, 0, 1) } };
        static readonly string[] Views = { "painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top" };

        public const string RecPkg = "Build/Polish/28/G_p28rec/art_on";
        public const string RecWarp = "Build/Polish/28/G_p28rec/timewarp_G_p28rec.json";
        public const string RecGwb = "Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb";
        public const string AttrPath = "Build/Polish/29/after/attr/pl29_hero_attr_f32.bin";
        public const string MatPath = "Assets/GreatWave/Polish29/Materials/PL29_Ukiyoe_Hero.mat";
        public const string MatPath36 = "Assets/GreatWave/Polish36/Materials/PL36_Ukiyoe_Hero.mat";
        // 仕上げ29 修正の回：面の座標は t* の面の弧長の版（pl29_hero_attr.py --param arc）、爪は視点によらない陰の段（PL29 Claw Shade）
        public const string AttrPathFix01 = "Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin";
        public const string ClawMatPath = "Assets/GreatWave/Polish29/Materials/PL29_Claw_Shade.mat";
        public const string ClawShaderName = "GreatWave/Polish29/PL29 Claw Shade";
        public const string SeaMatPath = "Assets/GreatWave/Polish30/Materials/PL30_Ukiyoe_Sea.mat";
        public const string SeaShaderName = "GreatWave/Polish30/PL30 Ukiyoe Sea Keypose";
        public const string LeftSupportName = "M1_Revision_LeftSupport";
        public const string FujiName = "fuji_blockout";

        static string[] Protected => new[] {
            Scene39, "Assets/GreatWave/Design50/Scenes/DS50_Release.unity", "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs",
            "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs", "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs",
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design38/Shaders/DS38_Outline_Keypose.shader",
            "Build/Design/33/claws/ds33_claw_frames_f32.bin", "Build/Polish/31/white/hero_pkg/ds27_twhite_r32f.bin", "Build/Polish/31/spray/pl31_spray_tone0_frames.bin", "Build/Design/31/spray/ds31_spray_frames.bin",
            "Build/Design/38/outlines/unity/prep/ds38_hero_linemask_f32.bin",
            RecPkg + "/ds27_keypose.json", RecWarp, RecGwb, AttrPath, AttrPathFix01, MatPath, "Assets/GreatWave/Polish29/Shaders/PL29_Ukiyoe_Hero.shader",
            ClawMatPath, "Assets/GreatWave/Polish29/Shaders/PL29_Claw_Shade.shader", "Assets/GreatWave/Polish29/Scenes/PL29_Release.unity",
            "Assets/GreatWave/Polish29/Scenes/PL29_SinglePlayback.unity", "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity",
            "Assets/GreatWave/Design36/Scripts/DS36SeaPalette.cs", "Assets/GreatWave/Design38/Scripts/DS38SheetOutline.cs",
            "Assets/GreatWave/Polish30/Scenes/PL30_Release.unity", "Assets/GreatWave/Polish30/Scenes/PL30_SinglePlayback.unity",
            "Assets/GreatWave/Polish30/Shaders/PL30_Ukiyoe_Sea.shader", "Build/Polish/28/G_p28rec/art_on/ds27_twhite_r32f.bin",
            MatPath36, "Assets/GreatWave/Polish36/Shaders/PL36_Ukiyoe_Hero.shader", "Assets/GreatWave/Polish33/Editor/PL33Render.cs",
            "Assets/GreatWave/Polish35/Scenes/PL35_Release.unity", "Assets/GreatWave/Polish35/Scenes/PL35_SinglePlayback.unity" };

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
            public PL29UkiyoeHero uk; public Material mat; public string clawPal = "d34";
            public PL29ClawShade clawShade; public Material clawMat;
            public bool old; public PL30UkiyoeSea seaUk; public Material seaMat; public DS30BoatHeave heave; public string heaveFrom = "";
            public List<Renderer> leftSupport = new List<Renderer>(); public GameObject mound; public bool ttSea = true;
            public DS38SheetOutline farLine; public Material farLineMat;
            public PL30LeftSwell leftSwell;
            public List<DS31InstancedParticles> sprays = new List<DS31InstancedParticles>(); public bool ttSpray = true, vidAsis = true, old31;
        }

        [Serializable] class ImgRec { public string view, cond, path, sha256; public float t, tau, az; public Vector3 camPos, camForward, camUp; public float fov; }
        [Serializable] class VidRec { public string name, view, path, sha256, ffmpegError; public int frames, fps, w, h; public float seconds, t0, t1; }
        [Serializable] class OriginRec { public float t, tau; public Vector3 originWorld; }
        [Serializable] class ParamRec { public string name, value; }
        [Serializable] class FujiRec { public float t, tau; public int snowPx, slopePx; }
        [Serializable] class Report
        {
            public string unity, device, graphicsApi, colorSpace, utc, scene, sceneSha256, state, noteJa;
            public string heroPackage, heroPackageJsonSha256, heroMeshGwb, heroMeshSha256, heroSdf, heroUvWarp, heroUv3File, heroUv3Source, timewarp, timewarpSha256;
            public string clawPalette;
            public string heroShader, material, materialSha256, attr, attrSha256, paramFile, paramFileSha256;
            public string clawShade, clawMaterial, clawMaterialSha256, clawSteps; public int[] clawVertexClasses; public bool clawLinesEverywhere;
            public ParamRec[] materialParams;
            public int heroLayers; public bool heroPosLoUsed; public long heroGpuBytes;
            public string[] views; public float[] times; public string[] t28Files;
            public ImgRec[] images; public VidRec[] videos; public OriginRec[] origins;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
            public string state30, seaDir, nearPackage, farPackage, nearJsonSha256, farJsonSha256, seaShader, seaMaterial, seaMaterialSha256, heave, heaveSha256, mound;
            public string[] seaAttrSha256; public bool leftSupportHidden, farLine, ttSea; public long nearGpuBytes, farGpuBytes; public int nearRows, farCols;
            public FujiRec[] fuji;
            public string state31, sprayStem, heroTwhiteSha256; public string[] sprayData; public int sprayCount;
            public string state32, clawLayout, clawLayoutSha256, look32f; public int look32fTuftVertices, look32fLineVertices;
            public string look33; public int look33WebEntries, look33WebVertices, look33CrownEntries;
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
            c.sprays.Add(c.spray);
            c.pal = c.claws.GetComponent<DS36ClawPalette>();
            c.seaPal = roots.Select(g => g.GetComponentInChildren<DS36SeaPalette>(true)).First(x => x != null);
            c.clawLine = c.claws.GetComponent<DS38ClawOutline>();
            c.globals = c.play.GetComponent<DS38LineGlobals>();
            foreach (var s in c.sheets) { var so = s.GetComponent<DS38SheetOutline>(); if (so != null) c.lineComps.Add(so); }
            c.paper = roots.Select(g => g.GetComponentInChildren<DS39PaperLayers>(true)).First(x => x != null);
            if (c.clawLine == null || c.globals == null || c.lineComps.Count == 0 || c.paper == null) throw new InvalidOperationException("設計38・39 の部品がありません");
            foreach (var n in new[] { "side_right", "back65", "top", "tt" })
            {
                var go = new GameObject("PL29 " + n + "（一時のカメラ）") { hideFlags = HideFlags.DontSave };
                var cam = go.AddComponent<Camera>();
                cam.CopyFrom(c.cams["painting"]);
                cam.enabled = false;
                c.cams[n] = cam; c.temp.Add(go);
            }
            return c;
        }

        // 材質の値の上書き：1 行に「名前=値」（色・ベクトルは「,」で 4 つまで、数は 1 つ）。# から後は読まない。
        static List<ParamRec> ApplyParams(Material m, string file)
        {
            var recs = new List<ParamRec>();
            if (string.IsNullOrEmpty(file)) return recs;
            foreach (var raw in File.ReadAllLines(file, Encoding.UTF8))
            {
                var line = raw.Split('#')[0].Trim();
                if (line.Length == 0) continue;
                int k = line.IndexOf('=');
                if (k <= 0) throw new FormatException("材質の値の行: " + raw);
                string name = line.Substring(0, k).Trim(), val = line.Substring(k + 1).Trim();
                var parts = val.Split(',').Select(x => float.Parse(x.Trim(), CultureInfo.InvariantCulture)).ToArray();
                if (!m.HasProperty(name)) throw new ArgumentException("材質にない値: " + name);
                if (parts.Length == 1) m.SetFloat(name, parts[0]);
                else
                {
                    var v = new Vector4(parts[0], parts.Length > 1 ? parts[1] : 0, parts.Length > 2 ? parts[2] : 0, parts.Length > 3 ? parts[3] : 1);
                    if (name.StartsWith("_White") || name.StartsWith("_Mizuiro") || name.StartsWith("_Ai") || name.StartsWith("_LineCol")) m.SetColor(name, v);
                    else m.SetVector(name, v);
                }
                recs.Add(new ParamRec { name = name, value = val });
            }
            return recs;
        }

        static void Prepare(Ctx c)
        {
            if (c.seaUk != null) c.seaUk.Configure();
            foreach (var so in c.lineComps) so.Attach();
            c.clawLine.Attach();
            c.globals.Apply();
            c.play.Prepare();
            c.uk.Apply();
            foreach (var sp in c.sprays) sp.Load();
            c.claws.Load(); c.dense.Load();
            var hp = c.seaPal.SyncFromHero();
            c.pal.white = hp[0]; c.pal.mizuiro = hp[1]; c.pal.aiMid = hp[2]; c.pal.aiDark = hp[3];
            // 爪の色：既定（d34）は設計34 の視点によらない白（上面と根元）・淡い水色（縁の側面と下面）のまま（設計36 の原画カメラの投影の表を使わない）。
            // -pl29ClawPal d36 で設計36 の投影の色（前の点検と同じ）
            if (c.clawPal == "d36") c.pal.Apply();
            // 仕上げ29 修正の回：-pl29ClawShade 1 で、爪に視点によらない陰の段（PL29 Claw Shade）と、原画視点でも描く縁の線を付ける（既定 0 は作る部の描画と同じ）
            if (c.clawShade != null) c.clawShade.Apply();
            if (c.seaUk != null) c.seaUk.Apply();
            foreach (var so in c.lineComps) so.BindMask();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_PL29Diag", 0);
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
            string od = Arg(a, "-pl29Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/after/r1";
            var skip = new HashSet<string>((Arg(a, "-pl29Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            var only = new HashSet<string>((Arg(a, "-pl29Only") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            bool Do(string st) => !skip.Contains(st) && (only.Count == 0 || only.Contains(st));
            var times = (Arg(a, "-pl29Times") ?? "6,9,10.5,12").Split(',').Select(s => double.Parse(s, CultureInfo.InvariantCulture)).ToArray();
            var views = (Arg(a, "-pl29Views") ?? string.Join(",", Views)).Split(',');
            int ttN = int.Parse(Arg(a, "-pl29TtN") ?? "12", CultureInfo.InvariantCulture);
            var vidViews = (Arg(a, "-pl29VideoViews") ?? "painting,seat").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            int vw = int.Parse(Arg(a, "-pl29VideoW") ?? "960", CultureInfo.InvariantCulture), vh = vw * 9 / 16;
            string paramFile = Arg(a, "-pl29ParamFile");
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), utc = DateTime.UtcNow.ToString("O"), scene = Scene39, sceneSha256 = Sha(Scene39), state = "after",
                views = views, times = times.Select(x => (float)x).ToArray()
            };
            var c = Open();
            c.clawPal = Arg(a, "-pl29ClawPal") ?? "d34";
            rep.clawPalette = c.clawPal;
            // 主役波：仕上げ28 の採用の形と動き。焼き込み（色区テクスチャ・UV3 の表・UV3 のファイル）は読まない
            c.hero.packageDir = Arg(a, "-pl29HeroPkg") ?? RecPkg;
            c.hero.meshGwb = Arg(a, "-pl29HeroGwb") ?? RecGwb;
            c.hero.sdfPath = ""; c.hero.warpPath = ""; c.hero.uv3File = "";
            c.play.timewarpPath = Arg(a, "-pl29Timewarp") ?? RecWarp;
            string heroMatPath = Arg(a, "-pl36HeroMat") ?? MatPath36;
            var asset = AssetDatabase.LoadAssetAtPath<Material>(heroMatPath);
            if (asset == null) throw new InvalidOperationException("材質がありません（PL36Setup.EnsureMaterial を先に）: " + heroMatPath);
            c.mat = new Material(asset) { hideFlags = HideFlags.DontSave, name = asset.name + "（描画の写し）" };
            var prs = ApplyParams(c.mat, paramFile);
            c.uk = c.hero.gameObject.AddComponent<PL29UkiyoeHero>();
            c.uk.sheet = c.hero; c.uk.attrPath = Arg(a, "-pl29Attr") ?? AttrPath; c.uk.material = c.mat;
            if ((Arg(a, "-pl29ClawShade") ?? "0") == "1")
            {
                var cm = AssetDatabase.LoadAssetAtPath<Material>(ClawMatPath);
                if (cm == null) throw new InvalidOperationException("爪の材質がありません（PL29Setup.EnsureMaterial を先に）: " + ClawMatPath);
                c.clawMat = new Material(cm) { hideFlags = HideFlags.DontSave, name = cm.name + "（描画の写し）" };
                var cpf = Arg(a, "-pl29ClawParamFile");
                if (!string.IsNullOrEmpty(cpf)) ApplyParams(c.clawMat, cpf);
                c.clawShade = c.claws.gameObject.AddComponent<PL29ClawShade>();
                c.clawShade.claws = c.claws; c.clawShade.material = c.clawMat; c.clawShade.linesEverywhere = (Arg(a, "-pl29ClawLines") ?? "1") == "1";
                rep.clawShade = "PL29ClawShade（" + ClawShaderName + "）"; rep.clawMaterial = ClawMatPath; rep.clawMaterialSha256 = Sha(ClawMatPath);
                rep.clawSteps = c.clawMat.GetVector("_Steps").ToString("F3"); rep.clawLinesEverywhere = c.clawShade.linesEverywhere;
            }
            // ---- 仕上げ31：飛沫と T_white
            c.old31 = (Arg(a, "-pl31Old") ?? "0") == "1";
            c.ttSpray = (Arg(a, "-pl31TtSpray") ?? "1") == "1";
            c.vidAsis = (Arg(a, "-pl31VideoAsis") ?? "1") == "1";
            rep.state31 = c.old31 ? "before（仕上げ30 の状態：T_white は G_p28rec、飛沫は設計31 の 186 粒）" : "after（仕上げ31 の T_white と飛沫）";
            if (!c.old31)
            {
                string sd = Arg(a, "-pl31Spray") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31/spray";
                string stem = Arg(a, "-pl31SprayStem") ?? "pl31_spray";
                rep.sprayStem = stem;
                c.spray.dataPath = sd + "/" + stem + "_tone0_frames.json"; c.spray.colourFromJson = true;
                var t1 = sd + "/" + stem + "_tone1_frames.json";
                if (File.Exists(t1))
                {
                    var go = new GameObject("PL31 飛沫（灰の白、一時）") { hideFlags = HideFlags.DontSave };
                    go.transform.SetParent(c.spray.transform.parent, false);
                    var sp1 = go.AddComponent<DS31InstancedParticles>();
                    sp1.dataPath = t1; sp1.colourFromJson = true; sp1.subdivisions = c.spray.subdivisions; sp1.clock = c.spray.clock;
                    sp1.drawInPlayMode = false; sp1.followClockInPlayMode = false; sp1.verifySha256 = true;
                    c.sprays.Add(sp1); c.temp.Add(go);
                }
            }
            // ---- 仕上げ30：周りの海
            c.old = (Arg(a, "-pl30Old") ?? "0") == "1";
            c.ttSea = (Arg(a, "-pl30TtSea") ?? "1") == "1";
            rep.state30 = c.old ? "before（仕上げ29 の海：設計30 のパッケージと設計36 の段）" : "after（仕上げ30 の海）";
            rep.ttSea = c.ttSea;
            var near = c.sheets.First(x => x.sheetName == "near");
            var farS = c.sheets.First(x => x.sheetName == "far");
            c.heave = c.play.heaves.FirstOrDefault(h => h != null);
            if (!c.old)
            {
                string sea = Arg(a, "-pl30Sea") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30/sea";
                rep.seaDir = sea;
                near.packageDir = sea + "/near"; farS.packageDir = sea + "/far";
                near.meshGwb = ""; farS.meshGwb = "";
                if (c.heave != null)
                {
                    c.heaveFrom = c.heave.supportPath;
                    c.heave.supportPath = sea + "/boat_support.json";
                }
                foreach (var cu in c.play.curtains) if (cu != null) { cu.enabled = false; foreach (var r2 in cu.GetComponentsInChildren<Renderer>(true)) r2.enabled = false; }
                var sm = AssetDatabase.LoadAssetAtPath<Material>(SeaMatPath);
                if (sm == null) throw new InvalidOperationException("海の材質がありません（PL30Setup.EnsureMaterial を先に）: " + SeaMatPath);
                c.seaMat = new Material(sm) { hideFlags = HideFlags.DontSave, name = sm.name + "（描画の写し）" };
                var spf = Arg(a, "-pl30SeaParamFile");
                if (!string.IsNullOrEmpty(spf)) ApplyParams(c.seaMat, spf);
                c.seaUk = c.play.gameObject.AddComponent<PL30UkiyoeSea>();
                c.seaUk.material = c.seaMat; c.seaUk.heroMaterial = c.mat;
                c.seaUk.sheets.Add(new PL30UkiyoeSea.Entry { sheet = near, attrPath = sea + "/near/pl30_sea_attr_f32.bin" });
                c.seaUk.sheets.Add(new PL30UkiyoeSea.Entry { sheet = farS, attrPath = sea + "/far/pl30_sea_attr_f32.bin" });
                rep.seaShader = SeaShaderName; rep.seaMaterial = SeaMatPath; rep.seaMaterialSha256 = Sha(SeaMatPath);
                if ((Arg(a, "-pl30FarLine") ?? "1") == "1" && farS.GetComponent<DS38SheetOutline>() == null)
                {
                    var nl = near.GetComponent<DS38SheetOutline>();
                    if (nl != null && nl.lineMaterial != null)
                    {
                        c.farLineMat = new Material(nl.lineMaterial) { hideFlags = HideFlags.DontSave, name = nl.lineMaterial.name + "（far の写し）" };
                        c.farLine = farS.gameObject.AddComponent<DS38SheetOutline>();
                        c.farLine.sheet = farS; c.farLine.lineMaterial = c.farLineMat; c.farLine.sheetId = 3; c.farLine.maskPath = "";
                        c.lineComps.Add(c.farLine);
                        rep.farLine = true;
                    }
                }
                if ((Arg(a, "-pl30HideLeft") ?? "1") == "1")
                    foreach (var r in c.ctx.GetComponentsInChildren<Renderer>(true))
                        if (r.enabled && (r.name == LeftSupportName || (r.transform.parent != null && r.transform.parent.name == LeftSupportName))) { r.enabled = false; c.leftSupport.Add(r); }
                rep.leftSupportHidden = c.leftSupport.Count > 0;
                var lsp = Arg(a, "-pl30LeftSwell");
                if (!string.IsNullOrEmpty(lsp))
                {
                    var go = new GameObject("PL30 左奥の船のうねり（一時）") { hideFlags = HideFlags.DontSave };
                    go.transform.SetParent(c.ctx.transform, false);
                    c.leftSwell = go.AddComponent<PL30LeftSwell>();
                    c.leftSwell.playback = c.play; c.leftSwell.dataPath = lsp; c.leftSwell.material = c.seaMat;
                    var bl = GameObject.Find("AF27 船 boat_left");
                    c.leftSwell.boat = bl != null ? bl.transform : null;
                    c.leftSwell.Load();
                    go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                    c.temp.Add(go);
                    rep.mound = lsp + " " + c.leftSwell.Sha256;
                }
            }
            // ---- 仕上げ32：爪の並び
            var clawLayout = Arg(a, "-pl32Claws");
            if (!string.IsNullOrEmpty(clawLayout)) c.claws.layoutPath = clawLayout;
            rep.clawLayout = c.claws.layoutPath; rep.clawLayoutSha256 = Sha(c.claws.layoutPath);
            rep.state32 = string.IsNullOrEmpty(clawLayout) ? "before（爪は設計33 の並び）" : "after（仕上げ32 の爪の並び）";
            rep.heroPackage = c.hero.packageDir; rep.heroPackageJsonSha256 = Sha(Path.Combine(c.hero.packageDir, "ds27_keypose.json"));
            rep.heroMeshGwb = c.hero.meshGwb; rep.heroMeshSha256 = Sha(c.hero.meshGwb);
            rep.heroSdf = c.hero.sdfPath; rep.heroUvWarp = c.hero.warpPath; rep.heroUv3File = c.hero.uv3File;
            rep.timewarp = c.play.timewarpPath; rep.timewarpSha256 = Sha(c.play.timewarpPath);
            rep.material = heroMatPath; rep.materialSha256 = Sha(heroMatPath); rep.heroShader = asset.shader.name;
            rep.paramFile = paramFile ?? ""; rep.paramFileSha256 = Sha(paramFile); rep.materialParams = prs.ToArray();
            var imgs = new List<ImgRec>(); var vids = new List<VidRec>(); var origins = new List<OriginRec>();
            try
            {
                Prepare(c);
                // 仕上げ32 修正の回 1：-pl32Look 1 で、爪の縁の線を根元で開き（pl32f_root_open）、根元の円を水色の版にする（pl32f_tuft_base）
                if ((Arg(a, "-pl32Look") ?? "0") == "1")
                {
                    var look = c.claws.gameObject.GetComponent<GreatWave.Polish32.PL32ClawLook>() ?? c.claws.gameObject.AddComponent<GreatWave.Polish32.PL32ClawLook>();
                    look.claws = c.claws; look.shade = c.clawShade; look.outline = c.clawLine;
                    look.outlineShader = Shader.Find("GreatWave/Polish32/PL32 Claw Outline");
                    look.tuftBase = (Arg(a, "-pl32TuftBase") ?? "1") == "1";
                    look.rootOpen = (Arg(a, "-pl32RootOpen") ?? "1") == "1";
                    var rf = Arg(a, "-pl32RootFade");
                    if (!string.IsNullOrEmpty(rf)) { var v = rf.Split(','); look.rootFade = new Vector2(float.Parse(v[0], System.Globalization.CultureInfo.InvariantCulture), float.Parse(v[1], System.Globalization.CultureInfo.InvariantCulture)); }
                    look.Apply();
                    rep.look32f = "PL32ClawLook rootOpen=" + look.rootOpen + " rootFade=" + look.rootFade.ToString("F2") + " tuftBase=" + look.tuftBase + " tuftShade=" + look.tuftShade;
                    rep.look32fTuftVertices = look.TuftVertices; rep.look32fLineVertices = look.LineVertices;
                }
                // 仕上げ33：-pl33Look 1 で、鉤の内の膜（id W…）を水色の版にし、膜の縁の線を出さない（PL33ClawLook、PL33 Claw Outline）
                if ((Arg(a, "-pl33Look") ?? "0") == "1")
                {
                    var l33 = c.claws.gameObject.GetComponent<GreatWave.Polish33.PL33ClawLook>() ?? c.claws.gameObject.AddComponent<GreatWave.Polish33.PL33ClawLook>();
                    l33.claws = c.claws; l33.outline = c.clawLine;
                    l33.look32 = c.claws.gameObject.GetComponent<GreatWave.Polish32.PL32ClawLook>();
                    l33.outlineShader = Shader.Find("GreatWave/Polish33/PL33 Claw Outline");
                    l33.Apply();
                    rep.look33 = "PL33ClawLook webShade=" + l33.webShade + " outline=" + (l33.outlineShader != null ? l33.outlineShader.name : "");
                    rep.look33WebEntries = l33.WebEntries; rep.look33WebVertices = l33.WebVertices; rep.look33CrownEntries = l33.CrownEntries;
                }
                rep.attr = c.uk.attrPath; rep.attrSha256 = c.uk.AttrSha256Read; rep.heroUv3Source = c.hero.Uv3Source;
                rep.sprayData = c.sprays.Select(sp => sp.dataPath + " " + sp.DataSha256 + " count=" + sp.Count + " colour=" + sp.colour.ToString("F4")).ToArray();
                rep.sprayCount = c.sprays.Sum(sp => sp.Count);
                rep.heroTwhiteSha256 = Sha(Path.Combine(c.hero.packageDir, "ds27_twhite_r32f.bin"));
                if (c.clawShade != null) rep.clawVertexClasses = (int[])c.clawShade.VertexClassCounts.Clone();
                rep.heroLayers = c.hero.PackageMeta.layers; rep.heroPosLoUsed = c.hero.PosLoFromPackage;
                rep.nearPackage = near.packageDir; rep.farPackage = farS.packageDir;
                rep.nearJsonSha256 = Sha(Path.Combine(near.packageDir, "ds27_keypose.json")); rep.farJsonSha256 = Sha(Path.Combine(farS.packageDir, "ds27_keypose.json"));
                rep.nearGpuBytes = near.PositionGpuBytes + near.PosLoGpuBytes + near.WhiteGpuBytes; rep.farGpuBytes = farS.PositionGpuBytes + farS.PosLoGpuBytes + farS.WhiteGpuBytes;
                rep.nearRows = near.PackageMeta.rows; rep.farCols = farS.PackageMeta.cols;
                if (c.heave != null) { rep.heave = c.heave.supportPath; rep.heaveSha256 = Sha(c.heave.FullPath); }
                if (c.seaUk != null) rep.seaAttrSha256 = c.seaUk.ShaRead.ToArray();
                rep.heroGpuBytes = c.hero.PositionGpuBytes + c.hero.PosLoGpuBytes + c.hero.WhiteGpuBytes;
                Set(c, false, false, false);
                foreach (var t in times)
                {
                    string ts = "t" + ((int)Math.Round(t * 10)).ToString("000");
                    Seek(c, t, true, false, false);
                    origins.Add(new OriginRec { t = (float)t, tau = (float)c.play.Tau, originWorld = OriginWorld(c) });
                    if (Do("views"))
                    {
                        Shader.SetGlobalFloat("_PL29Diag", float.Parse(Arg(a, "-pl29Debug") ?? "0", CultureInfo.InvariantCulture));
                        foreach (var v in views) CaptureView(c, v, od + "/views/" + v + "_" + ts + "_clawfree.png", t, false, imgs, "clawfree");
                        Seek(c, t, true, true, true);
                        foreach (var v in views) CaptureView(c, v, od + "/views/" + v + "_" + ts + "_asis.png", t, true, imgs, "asis");
                        Shader.SetGlobalFloat("_PL29Diag", 0);
                    }
                    if (Do("ids"))
                    {
                        Seek(c, t, true, false, false);
                        foreach (var v in views) DiagSet(c, v, od + "/diag/" + v + "_" + ts, t, false, imgs, false);
                        Seek(c, t, true, true, false);
                        foreach (var v in views) DiagSet(c, v, od + "/diag/" + v + "_" + ts, t, true, imgs, false);
                    }
                    if (Do("tt"))
                    {
                        for (int k = 0; k < ttN; k++)
                        {
                            double az = k * 360.0 / ttN;
                            string azs = "_az" + ((int)Math.Round(az)).ToString("000");
                            Seek(c, t, true, true, c.ttSpray);
                            PlaceTurntable(c, az);
                            // 修正02：-pl29DebugTt で回り台にも点検の印（_PL29Diag）を描けるようにした
                            Shader.SetGlobalFloat("_PL29Diag", float.Parse(Arg(a, "-pl29DebugTt") ?? "0", CultureInfo.InvariantCulture));
                            CaptureView(c, "tt", od + "/tt/" + ts + azs + "_claws.png", t, c.ttSpray, imgs, c.ttSpray ? "tt_asis" : "tt_claws", true, az);
                            Shader.SetGlobalFloat("_PL29Diag", 0);
                            if (Do("ids")) DiagSet(c, "tt", od + "/diag/tt_" + ts + azs, t, true, imgs, true, az);
                            Seek(c, t, true, false, false);
                            PlaceTurntable(c, az);
                            if (Do("ids")) DiagSet(c, "tt", od + "/diag/tt_" + ts + azs, t, false, imgs, true, az);
                        }
                    }
                }
                if (Do("fields"))
                {
                    // 面の座標の値の画像（_PL29Diag = 3・4・5。t* と各時刻、爪なし）。原画視点で原画の色区と比べて数値を合わせるため
                    foreach (var t in times)
                    {
                        string ts = "t" + ((int)Math.Round(t * 10)).ToString("000");
                        Seek(c, t, true, false, false);
                        foreach (var v in views)
                        {
                            PlaceFor(c, v);
                            var hid = HideAll(c, v);
                            try { foreach (var md in (Arg(a, "-pl36FieldModes") ?? "3,4,5,6").Split(',').Select(x => int.Parse(x, CultureInfo.InvariantCulture))) RenderDiag(c, c.cams[v], od + "/fields/" + v + "_" + ts + "_m" + md + ".png", true, md); }
                            finally { foreach (var r in hid) r.enabled = true; RestoreFor(c, v); }
                        }
                    }
                }
                if (Do("white"))
                {
                    // 仕上げ31：色区 ID（線なし）を、白の時刻あり（_DS27WhiteEnabled 1）となし（0 = 終態の白の範囲）で同じ時刻・同じ形に描く。
                    // 176（白でない色区が白で塗られない）と 102 の内側（白が終態の白の範囲の外に出ない）を画素で数える（pl31_measure.py）
                    var wt = (Arg(a, "-pl31WhiteTimes") ?? "5.8,6,6.5,7,7.5,8,8.5,9,9.5,10,10.5,11,11.5,12").Split(',').Select(x => double.Parse(x, CultureInfo.InvariantCulture)).ToArray();
                    var wv = (Arg(a, "-pl31WhiteViews") ?? "painting,seat,side_left,top").Split(',');
                    Set(c, false, false, false);
                    foreach (var t in wt)
                    {
                        string ts = "t" + ((int)Math.Round(t * 10)).ToString("000");
                        Seek(c, t, true, false, false);
                        foreach (var v in wv)
                        {
                            PlaceFor(c, v);
                            var hid = HideAll(c, v);
                            try
                            {
                                // 白の時刻の入切は DS30SheetPlayer が MaterialPropertyBlock で渡す（大域の値は上書きされる）ので、主役波の whiteEnabled を替えて当て直す
                                c.hero.whiteEnabled = true; Seek(c, t, true, false, false);
                                RenderDiag(c, c.cams[v], od + "/white/" + v + "_" + ts + "_on.png", false); imgs.Add(Rec(v, "white_on", od + "/white/" + v + "_" + ts + "_on.png", t, c));
                                c.hero.whiteEnabled = false; Seek(c, t, true, false, false);
                                RenderDiag(c, c.cams[v], od + "/white/" + v + "_" + ts + "_off.png", false); imgs.Add(Rec(v, "white_off", od + "/white/" + v + "_" + ts + "_off.png", t, c));
                                RenderDiag(c, c.cams[v], od + "/white/" + v + "_" + ts + "_hero.png", true); imgs.Add(Rec(v, "white_hero", od + "/white/" + v + "_" + ts + "_hero.png", t, c));
                            }
                            finally { c.hero.whiteEnabled = true; Seek(c, t, true, false, false); foreach (var r in hid) r.enabled = true; RestoreFor(c, v); }
                        }
                    }
                }
                if (Do("t28"))
                {
                    var f = new List<string>();
                    Set(c, false, false, false);
                    Seek(c, TStar, true, false, false);
                    f.AddRange(RenderT28(c, od + "/t28_white/t28/render"));
                    Seek(c, TStar, true, true, false);
                    f.AddRange(RenderT28(c, od + "/t28_claws/t28/render"));
                    rep.t28Files = f.ToArray();
                }
                if (Do("full"))
                {
                    Set(c, false, false, false);
                    Seek(c, TStar, true, true, true);
                    var p0 = od + "/full/painting_t120_off.png";
                    CaptureView(c, "painting", p0, TStar, true, imgs, "full_off");
                    CaptureView(c, "painting", od + "/full/painting_t120_nospray.png", TStar, false, imgs, "full_nospray");
                    Seek(c, TStar, true, true, false);
                    var p1 = od + "/full/ids_noline.png"; RenderIdsFull(c, c.cams["painting"], p1, false); imgs.Add(Rec("painting", "ids_noline", p1, TStar, c));
                    var p2 = od + "/full/ids_line.png"; RenderIdsFull(c, c.cams["painting"], p2, true); imgs.Add(Rec("painting", "ids_line", p2, TStar, c));
                    Seek(c, TStar, true, false, false);
                    var p3 = od + "/full/ids_line_noclaws.png"; RenderIdsFull(c, c.cams["painting"], p3, true); imgs.Add(Rec("painting", "ids_line_noclaws", p3, TStar, c));
                    var p4 = od + "/full/ids_noline_noclaws.png"; RenderIdsFull(c, c.cams["painting"], p4, false); imgs.Add(Rec("painting", "ids_noline_noclaws", p4, TStar, c));
                    SetLines(c, true);
                }
                if (Do("video"))
                {
                    Set(c, false, false, false);
                    int n = (int)Math.Round(TEnd * Fps) + 1;
                    foreach (var v in vidViews)
                        vids.Add(Video(c, v, v, n, i => i / (double)Fps, null, od + "/video", vw, vh));
                    vids.Add(Video(c, "tt", "tt", 120, i => TStar, i => i * 3.0, od + "/video", vw, vh));
                }
                var f71 = Arg(a, "-pl29F71");
                if (f71 != null && Do("f71"))
                {
                    var p = f71.Split(',').Select(s => int.Parse(s, CultureInfo.InvariantCulture)).ToArray();
                    // -pl29F71Hz（既定 30）：コマの番号 i の時刻 t = i / Hz。90 なら同じ時間の窓を 3 倍の細かさで撮る（動く細い縞の 1 コマの読みの確かめ）
                    double hz = double.Parse(Arg(a, "-pl29F71Hz") ?? "30", CultureInfo.InvariantCulture);
                    Set(c, false, false, false);
                    for (int i = p[0]; i <= p[1]; i++)
                    {
                        double t = i / hz;
                        Seek(c, t, true, false, false);
                        CaptureView(c, "painting", od + "/f71/painting_f" + i.ToString("0000") + ".png", t, false, imgs, "f71");
                    }
                }
                if (Do("gpu") && (Arg(a, "-pl29Gpu") ?? "0") == "1") GpuTiming(c, od + "/gpu");
                if (Do("fuji"))
                {
                    var fr = new List<FujiRec>();
                    Set(c, false, false, false);
                    var ft = new List<double>();
                    // 修正02：-pl30FujiT1・-pl30FujiDt で t 5〜12 s の全部のコマ（1/30 s おき）も数えられるようにした（既定は作る部・修正01 と同じ t 5〜10.5 s の 0.25 s おき＋t*）
                    double fT1 = double.Parse(Arg(a, "-pl30FujiT1") ?? "10.5", CultureInfo.InvariantCulture);
                    double fDt = double.Parse(Arg(a, "-pl30FujiDt") ?? "0.25", CultureInfo.InvariantCulture);
                    int fN = (int)Math.Floor((fT1 - 5.0) / fDt + 1e-6);
                    for (int k = 0; k <= fN; k++) ft.Add(5.0 + k * fDt);
                    if (fT1 < TStar - 1e-6) ft.Add(TStar);
                    foreach (var t in ft)
                    {
                        Seek(c, t, true, false, false);
                        fr.Add(RenderFuji(c, od + "/fuji/painting_fuji_t" + ((int)Math.Round(t * 100)).ToString("0000") + ".png", t));
                    }
                    rep.fuji = fr.ToArray();
                }
                if (Do("s5"))
                {
                    Set(c, false, false, false);
                    for (int i = 180; i <= 190; i++)
                    {
                        double t = i / 30.0;
                        Seek(c, t, true, false, false);
                        foreach (var v in new[] { "painting", "seat_toward_wave", "side_left" })
                            CaptureView(c, v, od + "/s5/" + v + "_f" + i.ToString("0000") + ".png", t, false, imgs, "s5");
                    }
                    for (int i = 270; i <= 300; i++)
                    {
                        double t = i / 30.0;
                        Seek(c, t, true, false, false);
                        CaptureView(c, "seat", od + "/s5/seat_f" + i.ToString("0000") + ".png", t, false, imgs, "s5");
                    }
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_DS39Gain", 0);
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat("_PL29Diag", 0);
                c.paper.Teardown();
                foreach (var so in c.lineComps) so.ReleaseMask();
                c.uk.Revert();
                if (c.clawShade != null) { c.clawShade.Revert(); UnityEngine.Object.DestroyImmediate(c.clawShade); }
                if (c.clawMat != null) UnityEngine.Object.DestroyImmediate(c.clawMat);
                foreach (var s in c.play.sheets) s.Release();
                foreach (var sp in c.sprays) sp.Release();
                c.dense.Release(); c.pal.Release(); c.clawLine.Release(); c.claws.Release();
                foreach (var g in c.temp) if (g != null) UnityEngine.Object.DestroyImmediate(g);
                if (c.uk != null) UnityEngine.Object.DestroyImmediate(c.uk);
                if (c.mat != null) UnityEngine.Object.DestroyImmediate(c.mat);
                if (c.farLine != null) { c.farLine.ReleaseMask(); UnityEngine.Object.DestroyImmediate(c.farLine); }
                if (c.farLineMat != null) UnityEngine.Object.DestroyImmediate(c.farLineMat);
                if (c.seaUk != null) UnityEngine.Object.DestroyImmediate(c.seaUk);
                if (c.seaMat != null) UnityEngine.Object.DestroyImmediate(c.seaMat);
                foreach (var r in c.leftSupport) if (r != null) r.enabled = true;
                if (c.leftSwell != null) c.leftSwell.Restore();
                if (c.heave != null && c.heaveFrom != "") c.heave.supportPath = c.heaveFrom;
            }
            rep.images = imgs.ToArray(); rep.videos = vids.ToArray(); rep.origins = origins.ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "仕上げ30：" + rep.state30 + "。Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render、DS39_Paper.unity を開くだけで保存しない）。HMD 実機ではない。" +
                         "主役波を仕上げ28 の採用（P28R2rec・G_p28rec）へ替え、焼き込みのファイルを読まずに、視点によらない立体の材質（PL29 Ukiyoe Keypose）で描いた。" +
                         "爪・飛沫・線の印・周りの海は合わせ直していない（仕上げ30〜33・36・38）。";
            File.WriteAllText(od + "/pl33_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("PL36_RENDER_DONE images=" + imgs.Count + " videos=" + vids.Count + " seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static Vector3 OriginWorld(Ctx c) => c.hero.transform.TransformPoint(c.hero.AppliedOrigin);

        static Vector3 Reflect(Vector3 v) => v - 2f * Vector3.Dot(v, E) * E;

        // PL29Audit と同じ置き方
        static void PlaceFor(Ctx c, string view)
        {
            var o = OriginWorld(c);
            if (view == "side_left")
                c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0 + (o - c.oStarWorld), c.sideRot0);
            else if (view == "side_right")
            {
                var rel = Reflect(c.sidePos0 - c.oStarWorld);
                var f = Reflect(c.sideRot0 * Vector3.forward);
                var cam = c.cams["side_right"];
                cam.transform.SetPositionAndRotation(o + rel, Quaternion.LookRotation(f, Vector3.up));
                cam.fieldOfView = c.cams["side_left"].fieldOfView;
            }
            else if (view == "back65")
            {
                float ang = -65f * Mathf.Deg2Rad;
                var pos = o + 90f * (Mathf.Cos(ang) * E + Mathf.Sin(ang) * Tdir) + new Vector3(0, 18, 0);
                var cam = c.cams["back65"];
                cam.transform.position = pos; cam.transform.LookAt(o + new Vector3(0, 8, 0), Vector3.up); cam.fieldOfView = 26f;
            }
            else if (view == "top")
            {
                var cam = c.cams["top"];
                cam.transform.SetPositionAndRotation(o + new Vector3(0, 150, 0), Quaternion.LookRotation(Vector3.down, -Tdir));
                cam.fieldOfView = 40f;
            }
        }

        static void RestoreFor(Ctx c, string view)
        {
            if (view == "side_left") c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0, c.sideRot0);
        }

        static void PlaceTurntable(Ctx c, double azDeg)
        {
            var o = OriginWorld(c);
            var c0 = o + new Vector3(0, 9, 0);
            var pc = new Vector3(0f, 3f, -62f) - (c.oStarWorld + new Vector3(0, 9, 0));
            double az0 = Math.Atan2(pc.z, pc.x), az = az0 + azDeg * Math.PI / 180.0, el = 16.0 * Math.PI / 180.0;
            var eye = c0 + new Vector3((float)(72 * Math.Cos(el) * Math.Cos(az)), (float)(72 * Math.Sin(el)), (float)(72 * Math.Cos(el) * Math.Sin(az)));
            var cam = c.cams["tt"];
            cam.transform.position = eye; cam.transform.LookAt(c0, Vector3.up); cam.fieldOfView = 34f;
        }

        static bool WaveOnly(string view) => view == "side_left" || view == "side_right" || view == "seat_toward_wave" || view == "back65" || view == "top" || view == "tt";

        static ImgRec Rec(string view, string cond, string path, double t, Ctx c, double az = double.NaN)
        {
            var cam = c.cams[view];
            return new ImgRec { view = view, cond = cond, path = path, t = (float)t, tau = (float)c.play.Tau, az = (float)az, sha256 = Sha(path), camPos = cam.transform.position,
                                camForward = cam.transform.forward, camUp = cam.transform.up, fov = cam.fieldOfView };
        }

        static List<Renderer> HideAll(Ctx c, string view)
        {
            var hid = HideFor(c, WaveOnly(view));
            if (view == "tt" && !c.ttSea) hid.AddRange(HideOtherSheets(c));
            return hid;
        }

        static void CaptureView(Ctx c, string view, string path, double t, bool spray, List<ImgRec> imgs, string cond, bool placed = false, double az = double.NaN)
        {
            if (!placed) PlaceFor(c, view);
            var cam = c.cams[view];
            CommandBuffer cb = null;
            if (spray) { cb = new CommandBuffer { name = "PL31 飛沫" }; foreach (var sp in c.sprays) sp.AddTo(cb); cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb); }
            var hid = HideAll(c, view);
            try { Capture(cam, W, H, true, path, Color.white); imgs.Add(Rec(view, cond, path, t, c, az)); }
            finally
            {
                if (cb != null) { cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cb.Release(); }
                foreach (var r in hid) r.enabled = true;
                if (!placed) RestoreFor(c, view);
            }
        }

        // ID の組：claws=false なら id_claws0 と主役波の印 hero_claws0、claws=true なら id_claws1 と hero_claws1
        static void DiagSet(Ctx c, string view, string stem, double t, bool claws, List<ImgRec> imgs, bool placed, double az = double.NaN)
        {
            if (!placed) PlaceFor(c, view);
            var cam = c.cams[view];
            var hid = HideAll(c, view);
            string s = claws ? "_claws1" : "_claws0";
            try
            {
                RenderDiag(c, cam, stem + "_id" + s + ".png", false); imgs.Add(Rec(view, "id" + s, stem + "_id" + s + ".png", t, c, az));
                RenderDiag(c, cam, stem + "_hero" + s + ".png", true); imgs.Add(Rec(view, "hero" + s, stem + "_hero" + s + ".png", t, c, az));
            }
            finally
            {
                foreach (var r in hid) r.enabled = true;
                if (!placed) RestoreFor(c, view);
            }
        }

        static void Set(Ctx c, bool paper, bool mura, bool spray) => c.paper.Set(paper, mura, spray);

        static void Seek(Ctx c, double t, bool white, bool claws, bool spray)
        {
            c.play.Seek(t);
            if (c.leftSwell != null) c.leftSwell.ApplyTau(c.play.Tau);
            foreach (var sp in c.sprays) sp.ApplyT(t);
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

        static bool KeepMaterial(Shader sh)
        {
            if (sh == null) return false;
            string n = sh.name;
            return n.Contains("Keypose") || n.StartsWith("GreatWave/Design27/") || n.StartsWith("GreatWave/Design34/") || n.StartsWith("GreatWave/Design36/DS36 Claw")
                || n.StartsWith("GreatWave/Design38/") || n.StartsWith("GreatWave/Design31/") || n.StartsWith("GreatWave/Polish29/") || n.StartsWith("GreatWave/Polish30/");
        }

        // ID の描画（線なし・MSAA なし・線形 ARGB32）。heroMask なら _PL29Diag = 1（主役波の印と行・列。ほかの物はアルファ 1 の ID の色）。
        static void RenderDiag(Ctx c, Camera camera, string pngPath, bool heroMask, int diagMode = 1)
        {
            var idShader = Shader.Find("GreatWave/ArtFirst/AF24 ID Flat");
            if (idShader == null) throw new InvalidOperationException("AF24 ID Flat がありません。");
            var mats = new Dictionary<string, Material>();
            Material Mat(string key, Vector4 v) { if (!mats.TryGetValue(key, out var m)) { m = new Material(idShader) { hideFlags = HideFlags.DontSave }; m.SetVector("_IdColor", v); mats[key] = m; } return m; }
            var saved = new List<(Renderer, Material[])>();
            var dome = GameObject.Find(SkyDomeName);
            var boatRoots = IdBoats.Keys.ToDictionary(k => k, k => GameObject.Find("AF27 船 " + k));
            SetLines(c, false);
            try
            {
                var heroR = c.hero.Surface;
                foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                {
                    if (!r.enabled || r == heroR) continue;
                    var sh = r.sharedMaterial != null ? r.sharedMaterial.shader : null;
                    string key = null; Vector4 col = IdOtherV;
                    if (dome != null && r.gameObject == dome) { key = "sky"; col = IdSkyV; }
                    foreach (var b in IdBoats) if (boatRoots[b.Key] != null && r.transform.IsChildOf(boatRoots[b.Key].transform)) { key = b.Key; col = b.Value; }
                    if (key == null && KeepMaterial(sh)) continue;
                    if (key == null) key = "other";
                    saved.Add((r, r.sharedMaterials));
                    r.sharedMaterials = Enumerable.Repeat(Mat(key, col), Math.Max(1, r.sharedMaterials.Length)).ToArray();
                }
                var clear = camera.clearFlags; var bg = camera.backgroundColor;
                camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0, 0, 0, 0);
                var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
                rt.Create();
                var tex = new Texture2D(W, H, TextureFormat.RGBA32, false, true);
                var prev = camera.targetTexture; bool hdr = camera.allowHDR, aa = camera.allowMSAA; float asp = camera.aspect;
                camera.allowHDR = false; camera.allowMSAA = false;
                Shader.SetGlobalFloat("_AF28IdMode", 1);
                Shader.SetGlobalFloat("_PL29Diag", heroMask ? diagMode : 0);
                camera.aspect = (float)W / H; camera.targetTexture = rt; camera.Render();
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat("_PL29Diag", 0);
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, W, H), 0, 0); tex.Apply(); RenderTexture.active = null;
                Directory.CreateDirectory(Path.GetDirectoryName(pngPath));
                File.WriteAllBytes(pngPath, tex.EncodeToPNG());
                camera.targetTexture = prev; camera.allowHDR = hdr; camera.allowMSAA = aa; camera.aspect = asp;
                camera.clearFlags = clear; camera.backgroundColor = bg;
                UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat("_PL29Diag", 0);
                foreach (var (r, m) in saved) r.sharedMaterials = m;
                foreach (var m in mats.Values) UnityEngine.Object.DestroyImmediate(m);
                SetLines(c, true);
            }
        }

        // 仕上げ30：原画視点の富士の見える画素。富士の 2 つの材質（雪・山腹）だけ別の ID の色（雪 (1,0,1)、山腹 (0.5,0,0.5)）、ほかの物は ID、
        // 主役波・海・爪は色区の ID（_AF28IdMode）。線なし・MSAA なし・線形。富士の前の物（海・右の高い波・主役波）が隠した分だけ数が減る。
        static FujiRec RenderFuji(Ctx c, string pngPath, double t)
        {
            var idShader = Shader.Find("GreatWave/ArtFirst/AF24 ID Flat");
            var mats = new Dictionary<string, Material>();
            Material Mat(string key, Vector4 v) { if (!mats.TryGetValue(key, out var m)) { m = new Material(idShader) { hideFlags = HideFlags.DontSave }; m.SetVector("_IdColor", v); mats[key] = m; } return m; }
            var saved = new List<(Renderer, Material[])>();
            var camera = c.cams["painting"];
            SetLines(c, false);
            var rec = new FujiRec { t = (float)t, tau = (float)c.play.Tau };
            try
            {
                foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                {
                    if (!r.enabled) continue;
                    var sh = r.sharedMaterial != null ? r.sharedMaterial.shader : null;
                    bool fuji = r.name == FujiName || (r.transform.parent != null && r.transform.parent.name == FujiName);
                    if (fuji)
                    {
                        saved.Add((r, r.sharedMaterials));
                        r.sharedMaterials = r.sharedMaterials.Select(m => m != null && m.name.ToLowerInvariant().Contains("snow") ? Mat("snow", new Vector4(1, 0, 1, 1)) : Mat("slope", new Vector4(0.5f, 0, 0.5f, 1))).ToArray();
                        continue;
                    }
                    if (KeepMaterial(sh)) continue;
                    saved.Add((r, r.sharedMaterials));
                    bool dome = r.gameObject.name == SkyDomeName;
                    r.sharedMaterials = Enumerable.Repeat(Mat(dome ? "sky" : "other", dome ? IdSkyV : IdOtherV), Math.Max(1, r.sharedMaterials.Length)).ToArray();
                }
                var clear = camera.clearFlags; var bg = camera.backgroundColor;
                camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0, 1, 1, 1);
                var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
                rt.Create();
                var tex = new Texture2D(W, H, TextureFormat.RGBA32, false, true);
                var prev = camera.targetTexture; bool hdr = camera.allowHDR, aa = camera.allowMSAA; float asp = camera.aspect;
                camera.allowHDR = false; camera.allowMSAA = false;
                Shader.SetGlobalFloat("_AF28IdMode", 1);
                camera.aspect = (float)W / H; camera.targetTexture = rt; camera.Render();
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, W, H), 0, 0); tex.Apply(); RenderTexture.active = null;
                foreach (var p in tex.GetPixels32())
                {
                    if (p.r == 255 && p.g == 0 && p.b == 255) rec.snowPx++;
                    else if (p.g == 0 && p.r == p.b && p.r > 20 && p.r < 200) rec.slopePx++;
                }
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
                SetLines(c, true);
            }
            return rec;
        }

        // 設計40・仕上げ28 の RenderT28 と同じ（名前・設定・順）
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

        [Serializable] class GpuCond { public string cond; public float[] onMs, offMs; public float medianOnMs, medianOffMs, heroMs; }
        [Serializable] class GpuRep
        {
            public string state = "after_fix01", device, api, unity, heroShader, attr, methodJa;
            public long keyposeGpuBytes, sdfTextureBytes, meshVertexBufferBytes, meshRuntimeBytes; public int meshVertexCount; public int[] meshVertexStrides;
            public int frames; public GpuCond[] timing;
        }

        // 仕上げ29 修正の回：主役波の面の GPU の時間の見当（作る部の評審と同じ方法）。主役波の面だけを残し（ほかのレンダラーは隠す）、
        // t 6〜12 s を等分した 120 コマを RT へ描いて毎コマ 1 画素を読み戻す壁時計の平均を 3 回、主役波あり・なしで測り、中央値の差を主役波の分とする。
        // 2 眼は 2064×2208・MSAA 4 の RT へ同じカメラで 2 回描く。GPU のタイマーではない。HMD 実機ではない。
        static void GpuTiming(Ctx c, string od)
        {
            Directory.CreateDirectory(od);
            var rep = new GpuRep { device = SystemInfo.graphicsDeviceName, api = SystemInfo.graphicsDeviceType.ToString(), unity = Application.unityVersion, frames = 120 };
            var heroR = c.hero.Surface;
            // 仕上げ30：-pl30GpuTarget sea で、周りの海の面（near・far）だけを残して同じ方法で測る（既定は主役波）
            bool seaTarget = (Environment.GetCommandLineArgs().SkipWhile(x => x != "-pl30GpuTarget").Skip(1).FirstOrDefault() ?? "hero") == "sea";
            var targets = seaTarget ? c.sheets.Where(x => x.sheetName != "hero").Select(x => (Renderer)x.Surface).Where(x => x != null).ToList() : new List<Renderer> { heroR };
            rep.heroShader = targets[0].sharedMaterial != null ? targets[0].sharedMaterial.shader.name : "";
            rep.attr = c.uk != null ? c.uk.attrPath : "";
            rep.keyposeGpuBytes = c.hero.PositionGpuBytes + c.hero.PosLoGpuBytes + c.hero.WhiteGpuBytes;
            var mesh = c.hero.SurfaceMesh;
            rep.meshVertexCount = mesh.vertexCount;
            rep.meshVertexStrides = Enumerable.Range(0, mesh.vertexBufferCount).Select(k => mesh.GetVertexBufferStride(k)).ToArray();
            rep.meshVertexBufferBytes = rep.meshVertexStrides.Sum(s => (long)s) * mesh.vertexCount;
            rep.meshRuntimeBytes = UnityEngine.Profiling.Profiler.GetRuntimeMemorySizeLong(mesh);
            rep.sdfTextureBytes = 0;
            var hidden = new List<Renderer>();
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                if (r.enabled && !targets.Contains(r)) { r.enabled = false; hidden.Add(r); }
            var conds = new List<GpuCond>();
            try
            {
                foreach (var (name, view, w, h, msaa, eyes) in new[] {
                    ("painting_1920x1080_msaa8", "painting", 1920, 1080, 8, 1), ("seat_1920x1080_msaa8", "seat", 1920, 1080, 8, 1),
                    ("seat_toward_wave_1920x1080_msaa8", "seat_toward_wave", 1920, 1080, 8, 1), ("seat_toward_wave_2eyes_2064x2208_msaa4", "seat_toward_wave", 2064, 2208, 4, 2) })
                {
                    var cam = c.cams[view];
                    var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = msaa };
                    rt.Create();
                    var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB); res.Create();
                    var tex = new Texture2D(1, 1, TextureFormat.RGBA32, false);
                    var prev = cam.targetTexture; float asp = cam.aspect;
                    cam.aspect = (float)w / h;
                    var on = new List<float>(); var off = new List<float>();
                    try
                    {
                        for (int rep3 = 0; rep3 < 3; rep3++)
                            foreach (bool heroOn in new[] { true, false })
                            {
                                foreach (var tg in targets) tg.enabled = heroOn;
                                var sw = Stopwatch.StartNew();
                                for (int i = 0; i < rep.frames; i++)
                                {
                                    double t = 6.0 + 6.0 * i / (rep.frames - 1);
                                    Seek(c, t, true, false, false);
                                    foreach (var r in hidden) r.enabled = false;
                                    foreach (var tg in targets) tg.enabled = heroOn;
                                    PlaceFor(c, view);
                                    for (int e = 0; e < eyes; e++) { cam.targetTexture = rt; cam.Render(); }
                                    Graphics.Blit(rt, res);
                                    RenderTexture.active = res; tex.ReadPixels(new Rect(0, 0, 1, 1), 0, 0); tex.Apply(); RenderTexture.active = null;
                                    RestoreFor(c, view);
                                }
                                float ms = (float)(sw.Elapsed.TotalMilliseconds / rep.frames);
                                (heroOn ? on : off).Add(ms);
                            }
                    }
                    finally
                    {
                        foreach (var tg in targets) tg.enabled = true;
                        cam.targetTexture = prev; cam.aspect = asp;
                        rt.Release(); res.Release(); UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res); UnityEngine.Object.DestroyImmediate(tex);
                    }
                    float Med(List<float> x) { var s = x.OrderBy(v => v).ToList(); return s[s.Count / 2]; }
                    var gc = new GpuCond { cond = name, onMs = on.ToArray(), offMs = off.ToArray(), medianOnMs = Med(on), medianOffMs = Med(off) };
                    gc.heroMs = gc.medianOnMs - gc.medianOffMs;
                    conds.Add(gc);
                }
            }
            finally
            {
                foreach (var r in hidden) r.enabled = true;
                foreach (var tg in targets) tg.enabled = true;
            }
            rep.timing = conds.ToArray();
            if (seaTarget) rep.state = "sea（near・far の面だけ。" + (c.old ? "前：設計36 の段" : "後：PL30 Ukiyoe Sea") + "）";
            rep.methodJa = "Editor batchmode。主役波の面だけを残し（ほかのレンダラーは隠す）、t 6〜12 s を等分した 120 コマを RT へ描いて毎コマ 1 画素を読み戻す壁時計の平均を 3 回、" +
                           "主役波あり・なしで測り中央値の差を主役波の分とした（作る部の評審の judge_gpu と同じ方法）。2 眼は同じカメラで 2 回描く。GPU のタイマーではない。HMD 実機ではない。";
            File.WriteAllText(od + (seaTarget ? "/pl30_gpu_sea.json" : "/pl29_gpu.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("PL29_GPU_DONE " + string.Join(" ", conds.Select(x => x.cond + "=" + x.heroMs.ToString("0.000", CultureInfo.InvariantCulture))));
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

        // 動画（爪なし・飛沫なし・紙なし・線あり）。コマを ffmpeg へ生の RGB で渡す。azOf が null でなければ回り台。
        static VidRec Video(Ctx c, string name, string view, int n, Func<int, double> tOf, Func<int, double> azOf, string od, int w, int h)
        {
            var sw = Stopwatch.StartNew();
            Directory.CreateDirectory(od);
            var mp4 = od + "/pl32_" + name + "_30fps.mp4";
            var camera = c.cams[view];
            var psi = new ProcessStartInfo
            {
                FileName = Ffmpeg,
                Arguments = string.Format("-y -loglevel error -f rawvideo -pix_fmt rgb24 -s {0}x{1} -r {2} -i - -vf vflip -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -movflags +faststart \"{3}\"",
                                          w, h, Fps, Path.GetFullPath(mp4)),
                UseShellExecute = false, RedirectStandardInput = true, RedirectStandardError = true, CreateNoWindow = true
            };
            var sb = new StringBuilder();
            var hid = HideFor(c, WaveOnly(view));
            if (view == "tt" && !c.ttSea) hid.AddRange(HideOtherSheets(c));
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
                            Seek(c, tOf(i), true, c.vidAsis, c.vidAsis);
                            if (azOf != null) PlaceTurntable(c, azOf(i)); else PlaceFor(c, view);
                            camera.targetTexture = rt;
                            CommandBuffer vcb = null;
                            if (c.vidAsis) { vcb = new CommandBuffer { name = "PL31 飛沫（動画）" }; foreach (var sp in c.sprays) sp.AddTo(vcb); camera.AddCommandBuffer(CameraEvent.AfterForwardOpaque, vcb); }
                            try { camera.Render(); }
                            finally { if (vcb != null) { camera.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, vcb); vcb.Release(); } }
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
