using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design27;
using GreatWave.Design27.EditorTools;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design30.EditorTools
{
    // 設計30 第B部：Unity の単発再生。主役波（設計28修正01 の F_final、精度の層つき、設計29修正01 の K*′ への焼き直しの色面）と、
    // 第A部の周りの海のシート（Unity/Build/Design/30/sea/<名前>/、同じ knot_tau の DS27 形式）を、1 つの時刻 t と世界全体の時間曲線 τ(t) で一緒に動かす。
    // 設計27 の場面 DS27_Formation.unity を開き、設計27 の主役波を除いて、DS30SheetPlayer（シートごとの MaterialPropertyBlock）・DS30FlatSeaRing
    // （far の足跡を抜いた平らな海）・DS30SinglePlayback（待機 → 再生 → t* で静止）を足し、単発再生の場面 DS30_SinglePlayback.unity として保存する
    // （保存はパッケージを読む前。メッシュとバッファは Play モードの OnEnable／Start で読む）。そのあと同じ場面をメモリの上で読み込み、次を書く：
    //   a. t*（t = 12 s）の画像（美術優先28修正01 と同じ名前・同じ設定）を 3 組：t28_ctrl（海のシートを隠し、元の平らな海。29修正01 と同じ場面の対照）、
    //      t28（色の画像は周りの海つき、ID と _kstar は主役波だけ＝評価器の読み方のまま）、t28_seaids（ID と _kstar にも周りの海と平らな海を入れる）。
    //   b. 静止画：t = 2・6・8・10・11・12 s（-ds30Stills）、視点 painting・seat・seat_toward_wave・side_left。
    //   c. 動画：t = 0〜14 s を 30 fps、同じ 4 視点。各コマは DS30SinglePlayback.Seek(t)（τ = τ(t)、t ≥ t* は静止）。
    //   d. 再生の検査（DS30SinglePlayback.Tick を 1/30 s で呼ぶ、Play モードと同じ経路）：待機 15 コマ → Begin → t* → 静止 30 コマ。
    //      毎コマ全シートの頂点を GPU で読み戻し（DS27KeyposeCapture.compute）、頂点の SHA-256・前のコマからの最大の動き・継ぎ目の差
    //      （主役波の外周と near の行 0、near の外周と far の行 0）・継ぎ目の法線の内積・座席の目の上下の水面（目が水の中か）を記録する。
    //      ほかに、揺れる dt（Play モードの引っかかり）での τ の進みの上限を確かめる。
    //   e. 穴の検査：10 Hz のコマで、座席の目から下向きの 5 方向（立方体の面）と原画視点を、背景を穴の色（マゼンタ）にして描き、
    //      水平より下で何も描かれない画素を数える（空のドーム・船・富士などの背景は隠す）。
    // 引数：-ds30Out <出力>、-ds30Name、-ds30Sea <海のフォルダー|none>、-ds30Sheets near,far、-ds30Warp <τ(t) の表>、-ds30Stills 2,6,8,10,11,12、
    //   -ds30Views painting,seat,seat_toward_wave,side_left、-ds30Skip scene,t28,stills,video,playback,holes、-ds30Fps 30、
    //   -ds30Hide <文脈の中の隠す物の名前、コンマ区切り>、-ds30FlatClass 3、-ds30Boat <boat_support.json>、
    //   -ds30LineInset 10（設計30修正1：主役波の外殻線を本体の境の輪から何列内側まで描くか）、-ds30AttachFoam 0（泡の線の仮置きを小波の頂に付けるか）。
    // 実行は Tools/GWWaveGen/ds30/run_ds30_unity.ps1（unity.lock の手順、30 分以内）：-Method GreatWave.Design30.EditorTools.DS30Render.Render
    public static class DS30Render
    {
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        public const string ScenePath30 = "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity";
        const string HeroPkg = "Build/Design/28R01F/F_final/art_on";
        const string HeroGwb = "Build/Design/29R01/bake_kp/kstar/kstar_a45.gwb";
        const string HeroSdf = "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin";
        const string HeroUvWarp = "Build/Design/29R01/bake_kp/bake/af28r01_uvwarp_a45.json";
        const string WarpDefault = "Build/Design/28R01F/F_final/timewarp_F_final.json";
        const string SeaDefault = "Build/Design/30/sea";
        const string ParamsJson = "../Tools/GWWaveGen/ds30/ds30_params.json";
        const string CapturePath = "Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const int W = 1920, H = 1080;
        const float TStar = 12f, TEnd = 14f, StwFov = 70f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);
        static readonly Color HoleColour = new Color(1, 0, 1);

        static string[] Protected => new[] {
            DS27Formation.ScenePath, "Assets/GreatWave/Design27/Editor/DS27Formation.cs", "Assets/GreatWave/Design27/Scripts/DS27KeyposePlayer.cs",
            "Assets/GreatWave/Design27/Scripts/DS27Json.cs", "Assets/GreatWave/Design27/Scripts/DS27TimeWarp.cs",
            "Assets/GreatWave/Design27/Materials/DS27_NPR_White.mat", "Assets/GreatWave/Design27/Materials/DS27_Outline_Keypose.mat",
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design27/Shaders/DS27_Outline_Keypose.shader",
            "Assets/GreatWave/Design27/Shaders/DS27Keypose.cginc", "Assets/GreatWave/Design27/Shaders/DS27KeyposeCore.cginc", CapturePath,
            "Assets/GreatWave/Design29/Scripts/DS29KeyposePlayer.cs", "Assets/GreatWave/Design29/Editor/DS29Render.cs",
            "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab", "Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs",
            "Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs", "Assets/GreatWave/ArtFirst/Scripts/GWClock.cs",
            "../Tools/GWContext/seat_v1.json", HeroGwb, HeroSdf, HeroUvWarp, HeroPkg + "/ds27_keypose.json" };

        static bool seaDirArgIsNone(string[] a) => (Arg(a, "-ds30Sea") ?? SeaDefault) == "none";

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        class Ctx
        {
            public GameObject ctx, heroGo, ringGo, flatSea, skyDome;
            public DS30SheetPlayer hero;
            public List<DS30SheetPlayer> sea = new List<DS30SheetPlayer>();
            public DS30FlatSeaRing ring;
            public DS30SinglePlayback play;
            public MeshRenderer heroLine;
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public Vector3 sidePos0; public Quaternion sideRot0; public Vector3 oStar;
            public Vector3 seatPos0; public Quaternion seatRot0; public Vector3 stwPos0; public Quaternion stwRot0;
            public DS30BoatHeave heave;
            public DS30AttachToVertex attach;
            public List<GameObject> hiddenGos = new List<GameObject>();
            public Vector3 flatSeaPos0; public bool flatLowered;
            public DS30SeamCurtain curtain; public MeshRenderer curtainR;
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string name = Arg(a, "-ds30Name") ?? "single";
            string od = Arg(a, "-ds30Out") ?? ("Build/Design/30/unity/" + name);
            string seaDir = Arg(a, "-ds30Sea") ?? SeaDefault;
            string warpPath = Arg(a, "-ds30Warp") ?? WarpDefault;
            var sheetNames = (Arg(a, "-ds30Sheets") ?? "near,far").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            var stillT = (Arg(a, "-ds30Stills") ?? "2,6,8,10,11,12").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries).Select(x => double.Parse(x, CultureInfo.InvariantCulture)).ToArray();
            var views = (Arg(a, "-ds30Views") ?? "painting,seat,seat_toward_wave,side_left").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            var skip = new HashSet<string>((Arg(a, "-ds30Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            int fps = int.Parse(Arg(a, "-ds30Fps") ?? "30", CultureInfo.InvariantCulture);
            // 第A部の約束（README_interface.txt v1 の 0 の (4)）：右の斜面と手前の小波の仮置きは near が置き換えるので描かない。
            // 設計30修正1：手前の小波の泡の線の仮置き（M1_ForegroundFoam_Static）も描かない。near の新しい小波は原画視点の同じ光線の上で約 10 m 手前にあり、
            // 泡の線は元の仮置きの位置に残って宙に浮いた（t* の seat_low で小波の上の白い Λ と海を横切る白い帯、原画視点の動画で小波の横の 2 つ目の白い V）。
            // 泡と線は設計36・38 で作り直す
            var hide = (Arg(a, "-ds30Hide") ?? (seaDirArgIsNone(a) ? "" : "M1_Revision_RightSlope,M1_ForegroundSwell_Static,M1_ForegroundFoam_Static")).Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            // 設計30修正1：主役波の外殻線は、本体の境の輪（列 colMin・colMax）から何列内側までを描くか（DS30SheetPlayer.outlineColInset。0 で面と同じ）。
            // 座席の目の低い視点では、谷の奥の壁が継ぎ目へ上がる所（列 394 から約 2〜13 列）が真横から見え、外殻線だけが継ぎ目に沿った灰色の線になった
            // （周りの海には外殻線がないので、線が継ぎ目で途切れて見える）。1・3 列では消えず、8・10・12 列は t = 6・10・11・12 s と t* で同じ画像（消える）。
            // 10 列 ≈ 列 394 の側 3.7 m・列 18 の側 3.1 m。海と接続帯の線は設計36・38 で作る
            int lineInset = int.Parse(Arg(a, "-ds30LineInset") ?? "10", CultureInfo.InvariantCulture);
            // 平らな仮置きの海：lower（既定）＝上面を y = −9 m へ下げて残す（第A部の約束の (3)。far のうねりの谷 −4.1 m・すそ −8 m より下で、
            // どの視点からも海のシートの陰になり、near と far の T 字の継ぎ目の画素の割れ目の後ろを同じ藍濃でふさぐ）／hide：描かない／ring：far の足跡を抜いた輪
            string flatMode = Arg(a, "-ds30FlatSea") ?? "lower";
            float flatLowerTop = float.Parse(Arg(a, "-ds30FlatSeaTop") ?? "-9", CultureInfo.InvariantCulture);
            int flatClass = int.Parse(Arg(a, "-ds30FlatClass") ?? "3", CultureInfo.InvariantCulture);
            string boatPath = Arg(a, "-ds30Boat");
            string heroColsArg = Arg(a, "-ds30HeroCols");
            // 周りの海の仮の色：t* の高さ ≥ この値（m）の頂点を白（仮置きの右の斜面・手前の小波の白と同じ役）、ほかは藍濃。none で全部藍濃
            string seaWhiteArg = Arg(a, "-ds30SeaWhiteY") ?? "0.5";   // 第A部の class_file の約束（t* の高さ ≥ 0.5 m を白）と同じ閾値
            float seaWhiteY = seaWhiteArg == "none" ? float.NaN : float.Parse(seaWhiteArg, CultureInfo.InvariantCulture);
            bool useSea = seaDir != "none";
            if (boatPath == null && useSea && File.Exists(seaDir.TrimEnd('/', '\\') + "/boat_support.json")) boatPath = seaDir.TrimEnd('/', '\\') + "/boat_support.json";
            if (boatPath == "none") boatPath = null;
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var files = new List<string>();
            var rep = new Report { seaWhiteY = seaWhiteY, name = name, unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), warpFile = Path.GetFullPath(warpPath), warpSha256 = Sha(warpPath), seaDir = useSea ? Path.GetFullPath(seaDir) : "none", hidden = hide, stillT = stillT, fps = fps, flatClass = flatClass };

            // ---- 場面を組む
            EditorSceneManager.OpenScene(DS27Formation.ScenePath, OpenSceneMode.Single);
            var scene = EditorSceneManager.GetActiveScene();
            var roots = scene.GetRootGameObjects();
            var pl27 = roots.Select(g => g.GetComponent<DS27KeyposePlayer>()).First(x => x != null);
            var wave27 = pl27.gameObject;
            var r27 = wave27.GetComponent<MeshRenderer>();
            var line27 = wave27.GetComponentsInChildren<MeshRenderer>(true).First(x => x.gameObject != wave27);
            var clock = roots.Select(g => g.GetComponent<GWClock>()).First(x => x != null);
            var c = new Ctx { ctx = roots.First(g => g.name == ContextRootName) };
            var camRoot = GameObject.Find(CamRoot).transform;
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            c.flatSea = FindChild(c.ctx, FlatSeaName);
            c.skyDome = FindChild(c.ctx, SkyDomeName);
            rep.wave27Transform = wave27.transform.localToWorldMatrix.ToString();

            c.heroGo = new GameObject("DS30 主役波（設計28修正01 の F_final、精度の層つき）");
            c.heroGo.transform.SetPositionAndRotation(wave27.transform.position, wave27.transform.rotation);
            c.heroGo.transform.localScale = wave27.transform.localScale;
            c.heroGo.AddComponent<MeshFilter>();
            var hr = c.heroGo.AddComponent<MeshRenderer>();
            CopyRenderer(r27, hr);
            c.heroGo.AddComponent<AF26KStarMesh>().dataPath = HeroGwb;
            var lineGo = new GameObject("DS30 外殻線 v0");
            lineGo.transform.SetParent(c.heroGo.transform, false);
            lineGo.AddComponent<MeshFilter>();
            c.heroLine = lineGo.AddComponent<MeshRenderer>();
            CopyRenderer(line27, c.heroLine);
            c.hero = c.heroGo.AddComponent<DS30SheetPlayer>();
            c.hero.sheetName = "hero"; c.hero.packageDir = HeroPkg; c.hero.meshGwb = HeroGwb; c.hero.warpPath = HeroUvWarp; c.hero.sdfPath = HeroSdf;
            c.hero.flatClass = -1; c.hero.outline = c.heroLine; c.hero.readPosLo = true;
            // 周りの海があるときは、主役波の本体の列だけを描く（第A部の ds30_params.json の hero.body_cols。外の平らな余白は接続帯が置き換える）
            if (useSea)
            {
                int[] hc = null;
                if (!string.IsNullOrEmpty(heroColsArg)) hc = heroColsArg.Split(',').Select(x => int.Parse(x, CultureInfo.InvariantCulture)).ToArray();
                else if (File.Exists(ParamsJson))
                {
                    var pr = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(ParamsJson)), "ds30_params.json");
                    var hj = DS27Json.AsObj(DS27Json.Get(pr, "hero"), "hero");
                    hc = DS27Json.Nums(DS27Json.Get(hj, "body_cols"), "body_cols").Select(x => (int)x).ToArray();
                    rep.paramsSha256 = Sha(ParamsJson);
                }
                if (hc != null) { c.hero.colMin = hc[0]; c.hero.colMax = hc[1]; c.hero.outlineColInset = lineInset; }
            }
            var nprMat = r27.sharedMaterials[0];
            UnityEngine.Object.DestroyImmediate(wave27);

            if (useSea)
            {
                foreach (var sn in sheetNames)
                {
                    var dir = seaDir.TrimEnd('/', '\\') + "/" + sn;
                    if (!File.Exists(Path.Combine(dir, "ds27_keypose.json"))) throw new FileNotFoundException("海のシートのパッケージがありません: " + dir);
                    var go = new GameObject("DS30 周りの海 " + sn);
                    go.AddComponent<MeshFilter>();
                    var mr = go.AddComponent<MeshRenderer>();
                    mr.sharedMaterials = new[] { nprMat };
                    SetRendererFlags(mr);
                    var sp = go.AddComponent<DS30SheetPlayer>();
                    sp.sheetName = sn; sp.packageDir = dir; sp.meshGwb = ""; sp.warpPath = ""; sp.sdfPath = ""; sp.flatClass = flatClass; sp.readPosLo = true;
                    // 白の色区（t* の高さ ≥ 0.5 m の等高線の内。頂点の側は第A部の ds30_class_u8.bin）は、パッケージの T_white（第A部 v1：高い所ほど早く白）
                    // から白（それまでは藍濃）。パッケージの T_white がすべて +1e9 なら、頂点の高さが 0.5 m を最後に超えた節点の τ から白
                    sp.whiteAboveTStarY = seaWhiteY; sp.whiteEnabled = !float.IsNaN(seaWhiteY); sp.preWhiteClass = flatClass;
                    c.sea.Add(sp);
                }
                var ft = c.flatSea.transform;
                rep.flatSeaMode = flatMode;
                if (flatMode == "ring")
                {
                    var farSheet = c.sea.LastOrDefault(s => s.sheetName == "far") ?? c.sea.Last();
                    c.ringGo = new GameObject("DS30 平らな海（far の足跡を抜いた輪）");
                    c.ringGo.AddComponent<MeshFilter>();
                    var rr = c.ringGo.AddComponent<MeshRenderer>();
                    rr.sharedMaterials = c.flatSea.GetComponent<MeshRenderer>().sharedMaterials;
                    SetRendererFlags(rr);
                    c.ring = c.ringGo.AddComponent<DS30FlatSeaRing>();
                    c.ring.far = farSheet;
                    c.ring.surfaceY = ft.position.y + 0.5f * ft.lossyScale.y;
                    c.ring.square = new Vector4(ft.position.x - 0.5f * ft.lossyScale.x, ft.position.x + 0.5f * ft.lossyScale.x, ft.position.z - 0.5f * ft.lossyScale.z, ft.position.z + 0.5f * ft.lossyScale.z);
                    rep.flatSeaSquare = c.ring.square; rep.flatSeaY = c.ring.surfaceY;
                }
                c.flatSeaPos0 = ft.position;
                if (flatMode == "lower")
                {
                    c.flatLowered = true;
                    ft.position = new Vector3(ft.position.x, flatLowerTop - 0.5f * ft.lossyScale.y, ft.position.z);
                    rep.flatSeaY = flatLowerTop;
                }
                else c.flatSea.SetActive(false);
            }
            // near と far の T 字の継ぎ目の下の幕（-ds30Curtain 0 で作らない）
            if (useSea && (Arg(a, "-ds30Curtain") ?? "1") == "1" && c.sea.Any(x => x.sheetName == "far"))
            {
                var cg = new GameObject("DS30 継ぎ目の幕（near と far の T 字の継ぎ目の下）");
                cg.AddComponent<MeshFilter>();
                c.curtainR = cg.AddComponent<MeshRenderer>();
                c.curtainR.sharedMaterials = c.flatSea.GetComponent<MeshRenderer>().sharedMaterials;
                SetRendererFlags(c.curtainR);
                c.curtain = cg.AddComponent<DS30SeamCurtain>();
                c.curtain.sheet = c.sea.First(x => x.sheetName == "far"); c.curtain.row = 0;
                rep.curtain = true;
            }
            foreach (var h in hide)
            {
                var found = c.ctx.GetComponentsInChildren<Transform>(true).Where(t => t.name == h).ToArray();
                if (found.Length == 0) throw new InvalidOperationException("隠す物が文脈にありません: " + h);
                foreach (var t in found) { t.gameObject.SetActive(false); c.hiddenGos.Add(t.gameObject); }
            }

            var playGo = new GameObject("DS30 単発再生（待機 → 再生 → t* で静止）");
            c.play = playGo.AddComponent<DS30SinglePlayback>();
            c.play.clock = clock; c.play.timewarpPath = warpPath; c.play.tStarSeconds = TStar;
            c.play.sheets = new List<DS30SheetPlayer> { c.hero };
            c.play.sheets.AddRange(c.sea);
            if (c.ring != null) c.play.rings = new List<DS30FlatSeaRing> { c.ring };
            if (c.curtain != null) c.play.curtains = new List<DS30SeamCurtain> { c.curtain };
            clock.playInPlayMode = false; clock.loopSeconds = 0f; clock.SetSeconds(0f);

            // seat_toward_wave（設計29 と同じ置き方。場面に保存する）
            var stwGo = new GameObject("DS30 seat_toward_wave");
            stwGo.transform.SetParent(camRoot, true);
            var stw = stwGo.AddComponent<Camera>();
            stw.enabled = false;
            stw.clearFlags = CameraClearFlags.SolidColor; stw.backgroundColor = SkyTop;
            stw.fieldOfView = StwFov; stw.nearClipPlane = .1f; stw.farClipPlane = 900; stw.aspect = (float)W / H;
            stw.allowHDR = false; stw.allowMSAA = true;
            c.cams["seat_toward_wave"] = stw;

            // seat_toward_wave の向き（設計29 と同じ置き方）：主役波の枠の原点の最初と t* の水平の差の逆向き。場面を保存する前に置く
            {
                var hm = GreatWave.Design29.DS29KeyposePlayer.ReadMeta(HeroPkg);
                var f0 = hm.frameOrigin[0]; var f1 = hm.frameOrigin[hm.frameOrigin.Length - 1];
                var td = new Vector3((float)(f1[0] - f0[0]), 0, (float)(f1[2] - f0[2])).normalized;
                stwGo.transform.SetPositionAndRotation(c.cams["seat"].transform.position, Quaternion.LookRotation(-td, Vector3.up));
                rep.travelDir = td;
            }
            // 座席の船の支え（第A部の boat_support.json。船と座席のカメラを鉛直だけ上下させる）
            if (!string.IsNullOrEmpty(boatPath))
            {
                var boatT = c.ctx.GetComponentsInChildren<Transform>(true).First(t => t.name == "AF27 船 boat_mid");
                var hg = new GameObject("DS30 座席の船の支え（boat_support.json の Δ）");
                c.heave = hg.AddComponent<DS30BoatHeave>();
                c.heave.supportPath = boatPath; c.heave.boat = boatT;
                c.heave.riders = new List<Transform> { c.cams["seat"].transform, c.cams["seat_low"].transform, stw.transform };
                var seatMark = c.ctx.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name.StartsWith("AF27R01 座席 v1"));
                if (seatMark != null && !seatMark.IsChildOf(boatT)) c.heave.riders.Add(seatMark);
                c.play.heaves = new List<DS30BoatHeave> { c.heave };
                rep.boat = new BoatRec { path = Path.GetFullPath(boatPath), sha256 = Sha(boatPath), boatObject = boatT.name };
            }

            // 手前の小波の泡の線を、near の小波の頂の頂点に付ける（第A部の near の small_apex.world）。設計30修正1 で泡の線は隠すので既定は付けない（-ds30AttachFoam 1 で付ける。
            // 隠したままなら activeInHierarchy の物がないので何もしない）
            if (useSea && (Arg(a, "-ds30AttachFoam") ?? "0") == "1" && c.sea.Any(x => x.sheetName == "near"))
            {
                var nearS = c.sea.First(x => x.sheetName == "near");
                var nj = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(Path.Combine(nearS.packageDir, "ds27_keypose.json"))), "near");
                if (DS27Json.Has(nj, "small_apex"))
                {
                    var ap = DS27Json.Nums(DS27Json.Get(DS27Json.AsObj(DS27Json.Get(nj, "small_apex"), "small_apex"), "world"), "world");
                    var foam = c.ctx.GetComponentsInChildren<Transform>(true).Where(t => t.name == "M1_ForegroundFoam_Static" && t.gameObject.activeInHierarchy).ToList();
                    if (foam.Count > 0)
                    {
                        var ag = new GameObject("DS30 手前の小波の泡の線を小波の頂に付ける");
                        var at = ag.AddComponent<DS30AttachToVertex>();
                        at.sheet = nearS; at.target = new Vector3((float)ap[0], (float)ap[1], (float)ap[2]); at.followers = foam;
                        c.play.attachments = new List<DS30AttachToVertex> { at };
                        c.attach = at;
                        rep.attachedFoam = foam.Select(t => t.name).ToArray();
                    }
                }
            }

            if (!skip.Contains("scene"))
            {
                if (!AssetDatabase.IsValidFolder("Assets/GreatWave/Design30/Scenes")) AssetDatabase.CreateFolder("Assets/GreatWave/Design30", "Scenes");
                if (!EditorSceneManager.SaveScene(scene, ScenePath30)) throw new InvalidOperationException("場面を保存できません: " + ScenePath30);
                rep.scenePath = ScenePath30; rep.sceneSha256 = Sha(ScenePath30);
            }

            // カメラの基準の置き場所（t* の姿勢。読み込みで船の支えが動かす前に取る）
            c.sidePos0 = c.cams["side_left"].transform.position; c.sideRot0 = c.cams["side_left"].transform.rotation;
            c.seatPos0 = c.cams["seat"].transform.position; c.seatRot0 = c.cams["seat"].transform.rotation;
            c.stwPos0 = stw.transform.position; c.stwRot0 = stw.transform.rotation;

            // ---- 読み込み
            long g0 = UnityEngine.Profiling.Profiler.GetAllocatedMemoryForGraphicsDriver();
            c.play.Prepare();
            long g1 = UnityEngine.Profiling.Profiler.GetAllocatedMemoryForGraphicsDriver();
            rep.driverBytesBefore = g0; rep.driverBytesAfter = g1;
            foreach (var s in c.play.sheets) rep.sheets.Add(SheetRec(s));
            rep.heroColMin = c.hero.colMin; rep.heroColMax = c.hero.colMax; rep.heroTrianglesFull = c.hero.FullTriangleCount; rep.heroTrianglesWindow = c.hero.WindowTriangleCount;
            rep.heroLineInset = c.hero.outlineColInset; rep.heroLineTrianglesWindow = c.hero.OutlineWindowTriangleCount;
            rep.knotTauSame = c.play.sheets.All(s => SameArr(s.PackageMeta.knotTau, c.hero.PackageMeta.knotTau));
            rep.frameSame = c.play.sheets.All(s => SameArr(s.PackageMeta.frameTau, c.hero.PackageMeta.frameTau) && s.PackageMeta.frameOrigin.Length == c.hero.PackageMeta.frameOrigin.Length
                                               && Enumerable.Range(0, s.PackageMeta.frameOrigin.Length).All(i => SameArr(s.PackageMeta.frameOrigin[i], c.hero.PackageMeta.frameOrigin[i])));
            rep.gpuBytesSheets = c.play.sheets.Sum(s => s.PositionGpuBytes + s.WhiteGpuBytes + s.PosLoGpuBytes);
            var warp = c.play.Warp;
            rep.tauAtT0 = warp.TauAt(0); rep.tauAtTStar = warp.TauAt(TStar);

            // カメラの初期の置き場所
            c.oStar = c.hero.OriginAt(0.0);
            rep.seatEye = c.seatPos0;
            if (c.heave != null) rep.boat.mode = c.heave.Mode;
            if (c.attach != null) { rep.attachVertex = c.attach.Vertex; rep.attachTargetDistance = c.attach.TargetDistance; }

            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 0);
            try
            {
                // a. t*
                if (!skip.Contains("t28"))
                {
                    Seek(c, TStar);
                    files.AddRange(RenderT28(c, od + "/t28_ctrl/t28/render", "ctrl"));
                    if (useSea)
                    {
                        files.AddRange(RenderT28(c, od + "/t28/t28/render", "main"));
                        files.AddRange(RenderT28(c, od + "/t28_seaids/t28/render", "seaids"));
                    }
                }

                // b. 静止画
                if (!skip.Contains("stills"))
                {
                    string ds = od + "/stills";
                    Directory.CreateDirectory(ds);
                    foreach (var t in stillT)
                    {
                        Seek(c, t);
                        foreach (var v in views)
                        {
                            var hid = HideFor(c, v);
                            try
                            {
                                PlaceCams(c);
                                files.Add(Capture(c.cams[v], W, H, true, string.Format(CultureInfo.InvariantCulture, "{0}/ds30_{1}_t{2:00.0}s_tau{3:+0.000;-0.000}.png", ds, v, t, c.play.Tau)));
                            }
                            finally { foreach (var r in hid) r.enabled = true; ResetCams(c); }
                        }
                    }
                }

                // c. 動画
                if (!skip.Contains("video"))
                {
                    string dv = od + "/video";
                    Directory.CreateDirectory(dv);
                    foreach (var v in views)
                    {
                        var sw = Stopwatch.StartNew();
                        var mp4 = dv + "/ds30_" + v + "_" + fps + "fps.mp4";
                        var hid = HideFor(c, v);
                        int nf; string err;
                        try { nf = EncodeVideo(c, c.cams[v], fps, TEnd, mp4, out err); }
                        finally { foreach (var r in hid) r.enabled = true; ResetCams(c); }
                        rep.videos.Add(new VideoRec { view = v, path = Path.GetFullPath(mp4), frames = nf, fps = fps, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = File.Exists(mp4) ? Sha(mp4) : "", contextHidden = hid.Count > 0 });
                        if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
                    }
                }

                // d. 再生の検査
                if (!skip.Contains("playback")) rep.playback = PlaybackCheck(c, od);

                // e. 穴の検査
                if (!skip.Contains("holes"))
                {
                    rep.holes = HoleCheck(c, od, files, true);
                    if (c.flatLowered) rep.holesNoFlat = HoleCheck(c, od, files, false);   // 下げた平らな海も隠した読み（継ぎ目の画素の割れ目の数の記録）
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 0);
                ResetCams(c);
                foreach (var s in c.play.sheets) s.Release();
            }
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.files = files.ToArray();
            rep.filesSha256 = files.Select(Sha).ToArray();
            rep.totalSeconds = (float)total.Elapsed.TotalSeconds;
            rep.passed = rep.protectedUnchanged && rep.knotTauSame && rep.sheets.All(s => s.alphaNot65535 == 0 && s.posLoAlphaNot255 == 0);
            File.WriteAllText(od + "/ds30_render_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("DS30_RENDER_DONE name=" + name + " files=" + files.Count + " seconds=" + rep.totalSeconds + " passed=" + rep.passed);
            if (!rep.passed) throw new InvalidOperationException("描画の検査が不合格です（ds30_render_report.json）。");
        }

        // ------------------------------------------------------------------ t*
        static List<string> RenderT28(Ctx c, string d28, string mode)
        {
            var f = new List<string>();
            Directory.CreateDirectory(d28);
            bool ctrl = mode == "ctrl", seaIds = mode == "seaids";
            var seaR = c.sea.Select(s => s.Surface).Where(r => r != null).ToList();
            if (c.curtainR != null) seaR.Add(c.curtainR);
            var ringR = c.ringGo != null ? c.ringGo.GetComponent<MeshRenderer>() : null;
            // 対照：海のシートと輪を隠し、元の平らな海を出す（29修正01 と同じ場面）
            foreach (var r in seaR) r.enabled = !ctrl;
            if (ringR != null) ringR.enabled = !ctrl;
            bool flatOn = ctrl || c.sea.Count == 0 || c.flatLowered;
            if (c.flatSea != null) c.flatSea.SetActive(flatOn);
            var flatPosNow = c.flatSea != null ? c.flatSea.transform.position : Vector3.zero;
            if (ctrl && c.flatSea != null && c.sea.Count > 0) c.flatSea.transform.position = c.flatSeaPos0;
            if (ctrl) foreach (var g in c.hiddenGos) g.SetActive(true);
            c.hero.UseColumnWindow(!ctrl);
            try
            {
                c.heroLine.enabled = true;
                foreach (var v in new[] { "painting", "seat", "seat_low" }) f.Add(Capture(c.cams[v], W, H, true, d28 + "/af28r01_" + v + ".png"));
                c.ctx.SetActive(false);
                foreach (var r in seaR) r.enabled = seaIds;
                if (ringR != null) ringR.enabled = seaIds;
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
                foreach (var r in seaR) r.enabled = true;
                if (ringR != null) ringR.enabled = true;
                if (c.flatSea != null) { c.flatSea.SetActive(c.sea.Count == 0 || c.flatLowered); c.flatSea.transform.position = flatPosNow; }
                foreach (var g in c.hiddenGos) g.SetActive(false);
                c.hero.UseColumnWindow(true);
            }
            return f;
        }

        // ------------------------------------------------------------------ 時刻とカメラ
        static void Seek(Ctx c, double t)
        {
            c.play.Seek(t);
            PlaceBoat(c);
        }

        static void PlaceBoat(Ctx c) { }   // 船の上下は DS30SinglePlayback（DS30BoatHeave）が同じ t・τ で行う

        static Vector3 SeatEyeNow(Ctx c) => c.heave == null ? c.seatPos0 : c.seatPos0 + Vector3.up * (float)c.heave.CurrentDelta;

        static void PlaceCams(Ctx c)
        {
            c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0 + (c.hero.AppliedOrigin - c.oStar), c.sideRot0);
        }

        static void ResetCams(Ctx c)
        {
            c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0, c.sideRot0);
        }

        // side_left と seat_toward_wave は背景（船・富士など）を隠す。空のドームと平らな海は残す（設計29 と同じ）
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

        // ------------------------------------------------------------------ 再生の検査
        class SheetCap
        {
            public DS30SheetPlayer s; public int n, rows, cols; public ComputeBuffer buf; public Vector4[] outv; public float[] pos, nrm, prev; public float orient = 1;
            public byte[] bytes;
        }

        static PlaybackRec PlaybackCheck(Ctx c, string od)
        {
            var sw = Stopwatch.StartNew();
            var rec = new PlaybackRec();
            var cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(CapturePath);
            int k = cs.FindKernel("DS27Capture");
            var caps = c.play.sheets.Select(s => new SheetCap { s = s, n = s.PackageMeta.rows * s.PackageMeta.cols, rows = s.PackageMeta.rows, cols = s.PackageMeta.cols }).ToList();
            foreach (var sc in caps)
            {
                sc.buf = new ComputeBuffer(sc.n * 2, 16);
                sc.outv = new Vector4[sc.n * 2];
                sc.pos = new float[sc.n * 3]; sc.nrm = new float[sc.n * 3];
                sc.bytes = new byte[sc.n * 12];
            }
            var frames = new List<FrameRec>();
            try
            {
                Action<string> grab = phase =>
                {
                    PlaceBoat(c);
                    var fr = new FrameRec { i = frames.Count, phase = phase, state = c.play.CurrentState.ToString(), t = c.play.T, tau = c.play.Tau };
                    var hashes = new List<string>(); var moves = new List<float>();
                    foreach (var sc in caps)
                    {
                        sc.s.BindCompute(cs, k);
                        cs.SetBuffer(k, "_DS27Out", sc.buf);
                        cs.SetInt("_DS27Count", sc.n);
                        cs.Dispatch(k, (sc.n + 63) / 64, 1, 1);
                        sc.buf.GetData(sc.outv);
                        for (int i = 0; i < sc.n; i++)
                        {
                            var p = sc.outv[2 * i]; var q = sc.outv[2 * i + 1];
                            sc.pos[3 * i] = p.x; sc.pos[3 * i + 1] = p.y; sc.pos[3 * i + 2] = p.z;
                            sc.nrm[3 * i] = q.x; sc.nrm[3 * i + 1] = q.y; sc.nrm[3 * i + 2] = q.z;
                        }
                        Buffer.BlockCopy(sc.pos, 0, sc.bytes, 0, sc.bytes.Length);
                        hashes.Add(ShaBytes(sc.bytes));
                        float mv = 0;
                        if (sc.prev != null)
                            for (int i = 0; i < sc.n; i++)
                            {
                                float dx = sc.pos[3 * i] - sc.prev[3 * i], dy = sc.pos[3 * i + 1] - sc.prev[3 * i + 1], dz = sc.pos[3 * i + 2] - sc.prev[3 * i + 2];
                                mv = Mathf.Max(mv, dx * dx + dy * dy + dz * dz);
                            }
                        moves.Add(sc.prev == null ? float.NaN : Mathf.Sqrt(mv));
                        if (sc.prev == null) sc.prev = new float[sc.n * 3];
                        Array.Copy(sc.pos, sc.prev, sc.pos.Length);
                    }
                    fr.hash = hashes.ToArray(); fr.maxMove = moves.ToArray();
                    if (frames.Count == 0) foreach (var sc in caps) sc.orient = Orientation(sc);
                    Seams(caps, fr);
                    Eye(c, caps, fr);
                    frames.Add(fr);
                };

                // 待機 15 コマ → Begin → 再生 → 静止 30 コマ
                c.play.Prepare();
                grab("prepare");
                for (int i = 0; i < 15; i++) { c.play.Tick(1.0 / 30.0); grab("waiting"); }
                c.play.Begin();
                int guard = 0;
                while (c.play.CurrentState != DS30SinglePlayback.State.Holding && guard++ < 2000) { c.play.Tick(1.0 / 30.0); grab("playing"); }
                for (int i = 0; i < 30; i++) { c.play.Tick(1.0 / 30.0); grab("holding"); }
            }
            finally { foreach (var sc in caps) sc.buf.Release(); }
            rec.frames = frames.ToArray();
            rec.sheetNames = caps.Select(x => x.s.sheetName).ToArray();
            rec.orientation = caps.Select(x => x.orient).ToArray();

            // 開始と終了の跳び
            int firstPlay = frames.FindIndex(f => f.phase == "playing");
            int firstHold = frames.FindIndex(f => f.state == "Holding");
            rec.waitingFramesSameAsStart = frames.Where(f => f.phase == "waiting" || f.phase == "prepare").All(f => f.hash.SequenceEqual(frames[0].hash));
            // Begin の直後の最初のコマの前（t = 0）は待機と同じ。待機の最後のコマ ＝ t = 0 のコマ
            rec.startFrameT = frames[firstPlay].t; rec.lastWaitingT = frames[firstPlay - 1].t; rec.lastWaitingTau = frames[firstPlay - 1].tau;
            rec.holdingFramesSameAsTStar = frames.Skip(firstHold).All(f => f.hash.SequenceEqual(frames[firstHold].hash));
            rec.firstHoldT = frames[firstHold].t; rec.firstHoldTau = frames[firstHold].tau;
            int ns = caps.Count;
            rec.startStep = new float[ns]; rec.startMedianNext30 = new float[ns]; rec.startMaxNext30 = new float[ns];
            rec.endStep = new float[ns]; rec.endMedianPrev30 = new float[ns]; rec.endMaxPrev30 = new float[ns]; rec.holdMaxStep = new float[ns]; rec.playMaxStep = new float[ns];
            for (int s = 0; s < ns; s++)
            {
                rec.startStep[s] = frames[firstPlay].maxMove[s];
                var nx = frames.Skip(firstPlay + 1).Take(30).Select(f => f.maxMove[s]).OrderBy(x => x).ToList();
                rec.startMedianNext30[s] = nx[nx.Count / 2]; rec.startMaxNext30[s] = nx.Last();
                rec.endStep[s] = frames[firstHold].maxMove[s];
                var pv = frames.Skip(firstHold - 30).Take(30).Select(f => f.maxMove[s]).OrderBy(x => x).ToList();
                rec.endMedianPrev30[s] = pv[pv.Count / 2]; rec.endMaxPrev30[s] = pv.Last();
                rec.holdMaxStep[s] = frames.Skip(firstHold + 1).Select(f => f.maxMove[s]).DefaultIfEmpty(0).Max();
                rec.playMaxStep[s] = frames.Skip(firstPlay).Take(firstHold - firstPlay + 1).Select(f => f.maxMove[s]).Max();
            }
            var pl = frames.Where(f => f.phase != "prepare").ToList();
            rec.seamHeroNearMaxGap = pl.Select(f => f.seamHeroNear).DefaultIfEmpty(-1).Max();
            rec.seamHeroNearMaxDy = pl.Select(f => f.seamHeroNearDy).DefaultIfEmpty(-1).Max();
            rec.seamHeroNearMinDot = pl.Select(f => f.seamHeroNearDot).DefaultIfEmpty(2).Min();
            rec.seamNearFarMaxGap = pl.Select(f => f.seamNearFar).DefaultIfEmpty(-1).Max();
            rec.seamNearFarMaxDy = pl.Select(f => f.seamNearFarDy).DefaultIfEmpty(-1).Max();
            rec.seamNearFarTJunctionMaxGap = pl.Select(f => f.seamNearFarT).DefaultIfEmpty(-1).Max();
            rec.seamNearFarMinDot = pl.Select(f => f.seamNearFarDot).DefaultIfEmpty(2).Min();
            rec.seamHeroNearMinDotP01 = pl.Select(f => f.seamHeroNearDotP01).DefaultIfEmpty(2).Min();
            rec.seamNearFarMinDotP01 = pl.Select(f => f.seamNearFarDotP01).DefaultIfEmpty(2).Min();
            rec.seamHeroNearMaxBelow05 = pl.Select(f => f.seamHeroNearDotBelow05).DefaultIfEmpty(0).Max();
            rec.seamNearFarMaxBelow05 = pl.Select(f => f.seamNearFarDotBelow05).DefaultIfEmpty(0).Max();
            rec.seamHeroNearSideMinDot = pl.Select(f => f.seamHeroNearSideDotMin).Where(x => !float.IsNaN(x)).DefaultIfEmpty(float.NaN).Min();
            rec.seamHeroNearSideMinDotP01 = pl.Select(f => f.seamHeroNearSideDotP01).Where(x => !float.IsNaN(x)).DefaultIfEmpty(float.NaN).Min();
            rec.seamHeroNearSideMaxBelow09 = pl.Select(f => f.seamHeroNearSideBelow09).DefaultIfEmpty(0).Max();
            rec.seamHeroNearSideCount = pl.Select(f => f.seamHeroNearSideCount).DefaultIfEmpty(0).Max();
            // 継ぎ目の速度の差（30 Hz のコマの差から）
            rec.seamHeroNearMaxDv = pl.Skip(1).Select((f, i) => Math.Abs(f.seamHeroNearSigned - pl[i].seamHeroNearSigned) * 30f).DefaultIfEmpty(0).Max();
            rec.eyeUnderWaterFrames = frames.Count(f => f.eyeUnderWater);
            rec.eyeMinClearance = frames.Where(f => !float.IsNaN(f.eyeClearance)).Select(f => f.eyeClearance).DefaultIfEmpty(float.NaN).Min();
            rec.eyeMinClearanceT = frames.Where(f => !float.IsNaN(f.eyeClearance)).OrderBy(f => f.eyeClearance).Select(f => f.t).FirstOrDefault();
            rec.eyeMinAbove = frames.Where(f => !float.IsNaN(f.eyeAbove)).Select(f => f.eyeAbove).DefaultIfEmpty(float.NaN).Min();

            // 揺れる dt（Play モードの引っかかりの代わり）
            var rnd = new System.Random(30);
            c.play.Prepare(); c.play.Begin();
            double prevTau = c.play.Tau, maxDTau = 0, maxDt = 0; int n2 = 0;
            while (c.play.CurrentState != DS30SinglePlayback.State.Holding && n2++ < 5000)
            {
                double dt = rnd.NextDouble() < 0.05 ? 0.25 + rnd.NextDouble() : 0.004 + rnd.NextDouble() * 0.03;
                maxDt = Math.Max(maxDt, dt);
                c.play.Tick(dt);
                maxDTau = Math.Max(maxDTau, Math.Abs(c.play.Tau - prevTau));
                prevTau = c.play.Tau;
            }
            rec.jitterTicks = n2; rec.jitterMaxDt = maxDt; rec.jitterMaxDTau = maxDTau; rec.jitterEndTau = c.play.Tau; rec.maxStepSeconds = c.play.maxStepSeconds;
            rec.seconds = (float)sw.Elapsed.TotalSeconds;
            // コマごとの表（CSV）
            var sb = new StringBuilder();
            sb.AppendLine("i,phase,state,t,tau," + string.Join(",", rec.sheetNames.Select(x => "move_" + x)) + ",seam_hero_near,seam_hero_near_dy,seam_hero_near_dot,seam_hero_near_dot_p01,seam_hero_near_dot_below05,seam_near_far,seam_near_far_dy,seam_near_far_t,seam_near_far_dot,seam_near_far_dot_p01,seam_near_far_dot_below05,eye_y,eye_under_water,eye_clearance,eye_above,eye_hits_above,eye_hits_below," + string.Join(",", rec.sheetNames.Select(x => "hash_" + x)));
            foreach (var f in frames)
                sb.AppendLine(string.Join(",", new[] { f.i.ToString(), f.phase, f.state, F(f.t), F(f.tau) }.Concat(f.maxMove.Select(x => F(x)))
                    .Concat(new[] { F(f.seamHeroNear), F(f.seamHeroNearDy), F(f.seamHeroNearDot), F(f.seamHeroNearDotP01), f.seamHeroNearDotBelow05.ToString(), F(f.seamNearFar), F(f.seamNearFarDy), F(f.seamNearFarT), F(f.seamNearFarDot), F(f.seamNearFarDotP01), f.seamNearFarDotBelow05.ToString(), F(f.eyeY), f.eyeUnderWater ? "1" : "0", F(f.eyeClearance), F(f.eyeAbove), f.eyeHitsAbove.ToString(), f.eyeHitsBelow.ToString() })
                    .Concat(f.hash.Select(h => h.Substring(0, 16)))));
            File.WriteAllText(od + "/ds30_playback_frames.csv", sb.ToString());
            rec.framesCsv = Path.GetFullPath(od + "/ds30_playback_frames.csv");
            rec.frames = null;   // JSON には入れない（CSV）
            return rec;
        }

        static string F(double x) => double.IsNaN(x) ? "" : x.ToString("R", CultureInfo.InvariantCulture);

        // 表の向き：全頂点のうち法線がはっきり上下を向く（|n.y| ≥ 0.3）頂点の n.y の中央値の符号（最初のコマ。どのシートも大部分は平らに近い海）
        static float Orientation(SheetCap sc)
        {
            var ys = new List<float>();
            for (int v = 0; v < sc.n; v++) { float y = sc.nrm[3 * v + 1]; if (Mathf.Abs(y) >= 0.3f) ys.Add(y); }
            if (ys.Count == 0) return 1f;
            ys.Sort();
            return ys[ys.Count / 2] >= 0 ? 1f : -1f;
        }

        static Vector3 P(SheetCap sc, int v) => new Vector3(sc.pos[3 * v], sc.pos[3 * v + 1], sc.pos[3 * v + 2]);
        static Vector3 N(SheetCap sc, int v) => new Vector3(sc.nrm[3 * v], sc.nrm[3 * v + 1], sc.nrm[3 * v + 2]) * sc.orient;

        // 主役波の外周の頂点の並び（第A部の約束：(行 0, 列 0→最後)、(行 1→最後, 列 最後)、(行 最後, 列 最後−1→0)、(行 最後−1→1, 列 0)、最初の写し）
        // 第A部の near/ds30_ring0_index.json（near の列 j の行 0 が主役波のどの（行, 列）か）。最後の列は列 0 の写し
        static readonly Dictionary<string, List<int>> ring0Cache = new Dictionary<string, List<int>>();
        static List<int> Ring0(DS30SheetPlayer near, int heroCols)
        {
            var p = Path.Combine(near.PackageMeta.dir, "ds30_ring0_index.json");
            if (!File.Exists(p)) return null;
            if (ring0Cache.TryGetValue(p, out var l)) return l;
            var r = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(p)), "ds30_ring0_index.json");
            var loop = (List<object>)DS27Json.Get(r, "loop");
            l = new List<int>();
            foreach (var o in loop)
            {
                var e = DS27Json.AsObj(o, "loop");
                l.Add((int)DS27Json.Num(e, "hero_row") * heroCols + (int)DS27Json.Num(e, "hero_col"));
            }
            if (l.Count == near.PackageMeta.cols - 1) l.Add(l[0]);
            ring0Cache[p] = l;
            return l;
        }

        static List<int> HeroRim(int rows, int cols, int c0, int c1)
        {
            var l = new List<int>();
            for (int col = c0; col <= c1; col++) l.Add(col);
            for (int r = 1; r < rows; r++) l.Add(r * cols + c1);
            for (int col = c1 - 1; col >= c0; col--) l.Add((rows - 1) * cols + col);
            for (int r = rows - 2; r >= 1; r--) l.Add(r * cols + c0);
            l.Add(c0);
            return l;
        }

        static void Seams(List<SheetCap> caps, FrameRec fr)
        {
            fr.seamHeroNear = fr.seamHeroNearDy = fr.seamNearFar = fr.seamNearFarDy = fr.seamNearFarT = float.NaN;
            fr.seamHeroNearDot = fr.seamNearFarDot = fr.seamHeroNearDotP01 = fr.seamNearFarDotP01 = float.NaN;
            var hero = caps.FirstOrDefault(x => x.s.sheetName == "hero");
            var near = caps.FirstOrDefault(x => x.s.sheetName == "near");
            var far = caps.FirstOrDefault(x => x.s.sheetName == "far");
            if (hero != null && near != null)
            {
                int hc0 = hero.s.colMin >= 0 ? hero.s.colMin : 0, hc1 = hero.s.colMax >= 0 ? hero.s.colMax : hero.cols - 1;
                var rim = Ring0(near.s, hero.cols) ?? HeroRim(hero.rows, hero.cols, hc0, hc1);
                int m = Math.Min(rim.Count, near.cols);
                float g = 0, gy = 0, signed = 0;
                var dots = new List<float>();
                var side = new List<float>();   // 主役波の列 18・394 の辺（行 1〜238）。行 0・239 の錐の点は法線が決まらないので分ける
                for (int j = 0; j < m; j++)
                {
                    var d = P(near, j) - P(hero, rim[j]);
                    if (d.magnitude > g) { g = d.magnitude; signed = d.y; }
                    gy = Mathf.Max(gy, Mathf.Abs(d.y));
                    float dt = Vector3.Dot(N(near, j), N(hero, rim[j]));
                    dots.Add(dt);
                    int hr = rim[j] / hero.cols;
                    if (hr >= 1 && hr <= hero.rows - 2) side.Add(dt);
                }
                side.Sort();
                if (side.Count > 0) { fr.seamHeroNearSideDotMin = side[0]; fr.seamHeroNearSideDotP01 = side[side.Count / 100]; fr.seamHeroNearSideBelow09 = side.Count(x => x < 0.9f); fr.seamHeroNearSideCount = side.Count; }
                dots.Sort();
                fr.seamHeroNear = g; fr.seamHeroNearDy = gy; fr.seamHeroNearDot = dots[0]; fr.seamHeroNearSigned = signed;
                fr.seamHeroNearDotP01 = dots[dots.Count / 100]; fr.seamHeroNearDotBelow05 = dots.Count(x => x < 0.5f);
                fr.rimCountMatches = rim.Count == near.cols;
            }
            if (near != null && far != null)
            {
                int lr = (near.rows - 1) * near.cols;
                float g = 0, gy = 0, gt = 0;
                var dots = new List<float>();
                int step = far.cols > 1 ? (near.cols - 1) / (far.cols - 1) : 1;
                for (int j = 0; j < far.cols; j++)
                {
                    int nc = Math.Min(j * step, near.cols - 1);
                    var d = P(far, j) - P(near, lr + nc);
                    g = Mathf.Max(g, d.magnitude); gy = Mathf.Max(gy, Mathf.Abs(d.y));
                    dots.Add(Vector3.Dot(N(far, j), N(near, lr + nc)));
                    if (j + 1 < far.cols)
                        for (int q = 1; q < step; q++)
                        {
                            var ip = Vector3.Lerp(P(far, j), P(far, j + 1), q / (float)step);
                            gt = Mathf.Max(gt, (P(near, lr + Math.Min(nc + q, near.cols - 1)) - ip).magnitude);
                        }
                }
                dots.Sort();
                fr.seamNearFar = g; fr.seamNearFarDy = gy; fr.seamNearFarT = gt; fr.seamNearFarDot = dots[0]; fr.nearFarStep = step;
                fr.seamNearFarDotP01 = dots[dots.Count / 100]; fr.seamNearFarDotBelow05 = dots.Count(x => x < 0.5f);
            }
        }

        // 座席の目の鉛直線と、すべてのシートの三角形の交点。目の上の最も近い面の空気の側が上なら、目は水の中
        static void Eye(Ctx c, List<SheetCap> caps, FrameRec fr)
        {
            var e = SeatEyeNow(c);
            fr.eyeY = e.y;
            var hits = new List<KeyValuePair<float, bool>>();   // (高さ, 空気の側が上)
            foreach (var sc in caps)
            {
                int cA = sc.s.colMin >= 0 && sc.s.ColumnWindowOn ? sc.s.colMin : 0, cB = sc.s.colMax >= 0 && sc.s.ColumnWindowOn ? sc.s.colMax : sc.cols - 1;
                for (int r = 0; r + 1 < sc.rows; r++)
                    for (int col = cA; col + 1 <= cB; col++)
                    {
                        int v = r * sc.cols + col;
                        int a0 = v, b0 = v + sc.cols, c0 = v + 1, d0 = v + sc.cols + 1;
                        float xmin = Mathf.Min(Mathf.Min(sc.pos[3 * a0], sc.pos[3 * b0]), Mathf.Min(sc.pos[3 * c0], sc.pos[3 * d0]));
                        float xmax = Mathf.Max(Mathf.Max(sc.pos[3 * a0], sc.pos[3 * b0]), Mathf.Max(sc.pos[3 * c0], sc.pos[3 * d0]));
                        if (e.x < xmin || e.x > xmax) continue;
                        float zmin = Mathf.Min(Mathf.Min(sc.pos[3 * a0 + 2], sc.pos[3 * b0 + 2]), Mathf.Min(sc.pos[3 * c0 + 2], sc.pos[3 * d0 + 2]));
                        float zmax = Mathf.Max(Mathf.Max(sc.pos[3 * a0 + 2], sc.pos[3 * b0 + 2]), Mathf.Max(sc.pos[3 * c0 + 2], sc.pos[3 * d0 + 2]));
                        if (e.z < zmin || e.z > zmax) continue;
                        TriHit(sc, a0, b0, c0, e, hits);
                        TriHit(sc, c0, b0, d0, e, hits);
                    }
            }
            float above = float.PositiveInfinity, below = float.NegativeInfinity; bool aboveUp = false;
            int na = 0, nb = 0;
            foreach (var h in hits)
            {
                if (h.Key > e.y) { na++; if (h.Key < above) { above = h.Key; aboveUp = h.Value; } }
                else { nb++; if (h.Key > below && h.Value) below = h.Key; }
            }
            fr.eyeHitsAbove = na; fr.eyeHitsBelow = nb;
            fr.eyeUnderWater = na > 0 && aboveUp;
            fr.eyeClearance = float.IsNegativeInfinity(below) ? float.NaN : e.y - below;
            fr.eyeAbove = float.IsPositiveInfinity(above) ? float.NaN : above - e.y;
        }

        static void TriHit(SheetCap sc, int ia, int ib, int ic, Vector3 e, List<KeyValuePair<float, bool>> hits)
        {
            var A = P(sc, ia); var B = P(sc, ib); var C = P(sc, ic);
            float d = (B.z - C.z) * (A.x - C.x) + (C.x - B.x) * (A.z - C.z);
            if (Mathf.Abs(d) < 1e-12f) return;
            float l1 = ((B.z - C.z) * (e.x - C.x) + (C.x - B.x) * (e.z - C.z)) / d;
            float l2 = ((C.z - A.z) * (e.x - C.x) + (A.x - C.x) * (e.z - C.z)) / d;
            float l3 = 1 - l1 - l2;
            if (l1 < 0 || l2 < 0 || l3 < 0) return;
            float y = l1 * A.y + l2 * B.y + l3 * C.y;
            var n = Vector3.Cross(B - A, C - A) * sc.orient;
            hits.Add(new KeyValuePair<float, bool>(y, n.y > 0));
        }

        // ------------------------------------------------------------------ 穴の検査（描画）
        static HoleRec HoleCheck(Ctx c, string od, List<string> files, bool withFlat = true)
        {
            string sfx = withFlat ? "" : "_noflat";
            bool curtainOn = c.curtainR != null && c.curtainR.enabled;
            if (c.curtainR != null) c.curtainR.enabled = withFlat;
            var sw = Stopwatch.StartNew();
            var rec = new HoleRec();
            const int S = 256;
            var probe = new GameObject("DS30 穴の検査のカメラ（メモリの上だけ）");
            var cam = probe.AddComponent<Camera>();
            cam.enabled = false; cam.fieldOfView = 90; cam.aspect = 1; cam.nearClipPlane = 0.05f; cam.farClipPlane = 2000; cam.allowHDR = false; cam.allowMSAA = false;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = HoleColour;
            var faces = new[] { Quaternion.LookRotation(Vector3.forward), Quaternion.LookRotation(Vector3.back), Quaternion.LookRotation(Vector3.left), Quaternion.LookRotation(Vector3.right), Quaternion.LookRotation(Vector3.down, Vector3.forward) };
            var faceNames = new[] { "pz", "nz", "nx", "px", "ny" };
            // 背景（船・富士・空のドーム・前景の仮置きなど）を隠す。主役波・海のシート・平らな海（輪）だけを描く
            var hid = new List<Renderer>();
            foreach (var rr in c.ctx.GetComponentsInChildren<Renderer>(false)) { if (!rr.enabled) continue; if (rr.name == FlatSeaName && withFlat && (c.sea.Count == 0 || c.flatLowered)) continue; rr.enabled = false; hid.Add(rr); }
            var rows = new List<string> { "t,tau,seat_hole_px_below_horizon,seat_px_below_horizon,painting_hole_px_below_horizon,painting_px_below_horizon" };
            var holeRows = new List<string> { "t,view,x,y,dir_x,dir_y,dir_z,neighbours" };
            var rt = new RenderTexture(S, S, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var tex = new Texture2D(S, S, TextureFormat.RGB24, false, false);
            const int PW = 960, PH = 540;
            var rtp = new RenderTexture(PW, PH, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var texp = new Texture2D(PW, PH, TextureFormat.RGB24, false, false);
            // 各画素の向き（立方体の面）
            var below = new bool[faces.Length][];
            for (int fi = 0; fi < faces.Length; fi++)
            {
                below[fi] = new bool[S * S];
                probe.transform.rotation = faces[fi];
                for (int y = 0; y < S; y++) for (int x = 0; x < S; x++)
                    {
                        var dir = cam.ViewportPointToRay(new Vector3((x + 0.5f) / S, (y + 0.5f) / S, 0)).direction;
                        below[fi][y * S + x] = dir.y < -0.01f;
                    }
            }
            var pc = c.cams["painting"];
            var belowP = new bool[PW * PH];
            float aspect = pc.aspect; pc.aspect = (float)PW / PH;
            for (int y = 0; y < PH; y++) for (int x = 0; x < PW; x++) belowP[y * PW + x] = pc.ViewportPointToRay(new Vector3((x + 0.5f) / PW, (y + 0.5f) / PH, 0)).direction.y < -0.01f;
            pc.aspect = aspect;
            int worstSeat = -1, worstPaint = -1; double worstSeatT = 0, worstPaintT = 0;
            try
            {
                for (int i = 0; i <= Mathf.RoundToInt(TEnd * 10); i++)
                {
                    double t = i / 10.0;
                    Seek(c, t);
                    var eye = SeatEyeNow(c);
                    probe.transform.position = eye;
                    int holes = 0, tot = 0;
                    for (int fi = 0; fi < faces.Length; fi++)
                    {
                        probe.transform.rotation = faces[fi];
                        cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
                        RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, S, S), 0, 0); RenderTexture.active = null;
                        var px = tex.GetRawTextureData();
                        byte[] idpx = null;
                        if (holeRows.Count < 400)
                        {
                            // 検査用の ID の描画（主役波 = 赤、near = 緑、far = 青）で、穴の画素の隣の面を記録する
                            bool anyHole = false;
                            for (int p = 0; p < S * S && !anyHole; p++) if (below[fi][p] && px[3 * p] > 240 && px[3 * p + 1] < 16 && px[3 * p + 2] > 240) anyHole = true;
                            if (anyHole) idpx = IdRender(c, cam, rt, tex, S, S);
                        }
                        for (int p = 0; p < S * S; p++)
                        {
                            if (!below[fi][p]) continue;
                            tot++;
                            if (px[3 * p] > 240 && px[3 * p + 1] < 16 && px[3 * p + 2] > 240)
                            {
                                holes++;
                                if (holeRows.Count < 400)
                                {
                                    var dir = cam.ViewportPointToRay(new Vector3((p % S + 0.5f) / S, (p / S + 0.5f) / S, 0)).direction;
                                    holeRows.Add(string.Join(",", F(t), "seat_" + faceNames[fi], (p % S).ToString(), (p / S).ToString(), F(dir.x), F(dir.y), F(dir.z), Neigh(idpx, p % S, p / S, S, S)));
                                }
                            }
                        }
                    }
                    // 原画視点
                    var pcl = pc.clearFlags; var pbg = pc.backgroundColor; var pa = pc.aspect;
                    pc.clearFlags = CameraClearFlags.SolidColor; pc.backgroundColor = HoleColour; pc.aspect = (float)PW / PH;
                    pc.targetTexture = rtp; pc.Render(); pc.targetTexture = null;
                    RenderTexture.active = rtp; texp.ReadPixels(new Rect(0, 0, PW, PH), 0, 0); RenderTexture.active = null;
                    var pp = texp.GetRawTextureData();
                    byte[] idpp = null;
                    if (holeRows.Count < 400)
                    {
                        bool anyHole = false;
                        for (int p = 0; p < PW * PH && !anyHole; p++) if (belowP[p] && pp[3 * p] > 240 && pp[3 * p + 1] < 16 && pp[3 * p + 2] > 240) anyHole = true;
                        if (anyHole) idpp = IdRender(c, pc, rtp, texp, PW, PH);
                    }
                    pc.clearFlags = pcl; pc.backgroundColor = pbg; pc.aspect = pa;
                    int ph = 0, pt = 0;
                    for (int p = 0; p < PW * PH; p++)
                    {
                        if (!belowP[p]) continue;
                        pt++;
                        if (pp[3 * p] > 240 && pp[3 * p + 1] < 16 && pp[3 * p + 2] > 240)
                        {
                            ph++;
                            if (holeRows.Count < 400) holeRows.Add(string.Join(",", F(t), "painting", (p % PW).ToString(), (p / PW).ToString(), "", "", "", Neigh(idpp, p % PW, p / PW, PW, PH)));
                        }
                    }
                    rows.Add(string.Join(",", F(t), F(c.play.Tau), holes.ToString(), tot.ToString(), ph.ToString(), pt.ToString()));
                    if (holes > worstSeat) { worstSeat = holes; worstSeatT = t; }
                    if (holes > 0) rec.seatFramesWithHoles++;
                    if (ph > 0) rec.paintingFramesWithHoles++;
                    if (ph > worstPaint) { worstPaint = ph; worstPaintT = t; }
                    rec.frames++;
                }
                // いちばん悪いコマの座席の下向きの面を保存（目で確かめるため）
                Seek(c, worstSeatT);
                probe.transform.position = SeatEyeNow(c);
                probe.transform.rotation = faces[4];
                var png = od + "/holes/ds30_holes" + sfx + "_seat_down_worst_t" + worstSeatT.ToString("00.0", CultureInfo.InvariantCulture) + ".png";
                Directory.CreateDirectory(od + "/holes");
                cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, S, S), 0, 0); tex.Apply(); RenderTexture.active = null;
                File.WriteAllBytes(png, tex.EncodeToPNG());
                files.Add(png);
            }
            finally
            {
                foreach (var r in hid) r.enabled = true;
                if (c.curtainR != null) c.curtainR.enabled = curtainOn;
                rt.Release(); rtp.Release();
                UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(rtp);
                UnityEngine.Object.DestroyImmediate(tex); UnityEngine.Object.DestroyImmediate(texp);
                UnityEngine.Object.DestroyImmediate(probe);
            }
            File.WriteAllText(od + "/ds30_holes" + sfx + ".csv", string.Join("\n", rows) + "\n");
            File.WriteAllText(od + "/ds30_holes" + sfx + "_px.csv", string.Join("\n", holeRows) + "\n");
            rec.csv = Path.GetFullPath(od + "/ds30_holes" + sfx + ".csv");
            rec.withFlatSea = withFlat;
            rec.seatWorstHolePx = worstSeat; rec.seatWorstT = worstSeatT; rec.paintingWorstHolePx = worstPaint; rec.paintingWorstT = worstPaintT;
            rec.methodJa = "10 Hz のコマ（t = 0〜14 s）で、座席の目から立方体の 5 面（上を除く、各 256²、視野 90°）と原画視点（960 × 540）を、背景をマゼンタにして描き、" +
                           "向きが水平より 0.01 rad 以上下の画素のうち何も描かれない（マゼンタのままの）画素を数えた。描くのは主役波・周りの海のシートと、" + (withFlat ? "平らな海（下げたもの・輪）" : "平らな海を隠した読み") + "（船・富士・空のドーム・前景の仮置きは隠す）。";
            rec.seconds = (float)sw.Elapsed.TotalSeconds;
            return rec;
        }

        // 検査用の ID の描画：主役波 = 黄（色区 3）、near = 緑（1）、far = 青（2）、何もない所 = マゼンタ。外殻線は隠す
        static byte[] IdRender(Ctx c, Camera cam, RenderTexture rt, Texture2D tex, int w, int h)
        {
            var sheets = c.play.sheets;
            for (int i = 0; i < sheets.Count; i++) sheets[i].SetDebugFlatClass(sheets[i].sheetName == "hero" ? 3 : sheets[i].sheetName == "near" ? 1 : sheets[i].sheetName == "far" ? 2 : 0);
            bool line = c.heroLine.enabled; c.heroLine.enabled = false;
            Shader.SetGlobalFloat("_AF28IdMode", 1);
            try
            {
                cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); RenderTexture.active = null;
                return tex.GetRawTextureData();
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                c.heroLine.enabled = line;
                foreach (var s in sheets) s.SetDebugFlatClass(-1);
            }
        }

        // 穴の画素の 8 近傍にある面（H 主役波・N near・F far・O ほか・M 何もない）
        static string Neigh(byte[] id, int x, int y, int w, int h)
        {
            if (id == null) return "";
            var set = new SortedSet<char>();
            for (int dy = -1; dy <= 1; dy++) for (int dx = -1; dx <= 1; dx++)
                {
                    int xx = x + dx, yy = y + dy;
                    if (xx < 0 || yy < 0 || xx >= w || yy >= h || (dx == 0 && dy == 0)) continue;
                    int p = yy * w + xx;
                    byte r = id[3 * p], g = id[3 * p + 1], b = id[3 * p + 2];
                    set.Add(r > 200 && g < 50 && b > 200 ? 'M' : r > 200 && g > 200 && b < 50 ? 'H' : g > 200 && r < 50 && b < 50 ? 'N' : b > 200 && r < 50 && g < 50 ? 'F' : 'O');
                }
            return new string(set.ToArray());
        }

        // ------------------------------------------------------------------ 描画の部品
        static int EncodeVideo(Ctx c, Camera camera, int fps, float seconds, string mp4, out string err)
        {
            int n = Mathf.RoundToInt(seconds * fps) + 1;
            string outs = string.Format("-vf vflip -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart \"{0}\"", Path.GetFullPath(mp4));
            var psi = new ProcessStartInfo
            {
                FileName = Ffmpeg,
                Arguments = string.Format("-y -loglevel error -f rawvideo -pix_fmt rgb24 -s {0}x{1} -r {2} -i - {3}", W, H, fps, outs),
                UseShellExecute = false, RedirectStandardInput = true, RedirectStandardError = true, CreateNoWindow = true
            };
            var sb = new StringBuilder();
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
                        Seek(c, i / (double)fps);
                        PlaceCams(c);
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
                    stdin.Flush();
                    stdin.Close();
                    camera.targetTexture = prev; camera.clearFlags = clear; camera.backgroundColor = bg;
                    UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
                    UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
                }
                if (!p.WaitForExit(10 * 60 * 1000)) { p.Kill(); throw new InvalidOperationException("ffmpeg が終わりません。"); }
                p.WaitForExit();
                lock (sb) err = sb.ToString() + (p.ExitCode != 0 ? " exit=" + p.ExitCode : "");
            }
            return n;
        }

        // DS27Formation.Capture の写し
        static string Capture(Camera camera, int w, int h, bool colour, string path)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = colour ? (Color)SkyTop : IdSky;
            camera.allowHDR = false; camera.allowMSAA = colour;
            var rw = colour ? RenderTextureReadWrite.sRGB : RenderTextureReadWrite.Linear;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, rw) { antiAliasing = colour ? 8 : 1 };
            var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, rw);
            rt.Create(); res.Create();
            camera.aspect = (float)w / h;
            camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, !colour);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return path;
        }

        static void CopyRenderer(MeshRenderer src, MeshRenderer dst)
        {
            dst.sharedMaterials = src.sharedMaterials;
            SetRendererFlags(dst);
        }

        static void SetRendererFlags(MeshRenderer dst)
        {
            dst.shadowCastingMode = ShadowCastingMode.Off; dst.receiveShadows = false;
            dst.lightProbeUsage = LightProbeUsage.Off; dst.reflectionProbeUsage = ReflectionProbeUsage.Off;
        }

        static GameObject FindChild(GameObject root, string n)
        {
            var t = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == n);
            return t != null ? t.gameObject : null;
        }

        static bool SameArr(double[] x, double[] y) => x.Length == y.Length && x.SequenceEqual(y);

        static SheetRecJ SheetRec(DS30SheetPlayer s)
        {
            var m = s.PackageMeta;
            return new SheetRecJ
            {
                name = s.sheetName, package = m.dir, jsonSha256 = m.jsonSha256, posSha256 = m.posSha256, posLoSha256 = s.PosLoSha256, rows = m.rows, cols = m.cols, layers = m.layers,
                posLoInPackage = s.PosLoInPackage, posLoFromPackage = s.PosLoFromPackage, positionGpuBytes = s.PositionGpuBytes, whiteGpuBytes = s.WhiteGpuBytes, posLoGpuBytes = s.PosLoGpuBytes,
                alphaNot65535 = s.AlphaNot65535, posLoAlphaNot255 = s.PosLoAlphaNot255, whiteNeverCount = s.WhiteNeverCount, meshSource = s.MeshSource, meshSha256 = s.MeshSha256, uv3Source = s.Uv3Source,
                flatClass = s.flatClass, sdf = s.sdfPath, whiteClassVertexCount = s.WhiteClassVertexCount, whiteEnabled = s.whiteEnabled, whiteFromHeight = s.WhiteFromHeight, whiteFromPackage = s.WhiteFromPackage, classFileUsed = s.ClassFileUsed, classFileAgree = s.ClassFileAgree, loadSeconds = s.LoadSeconds, worldBoundsMin = s.WorldBounds.min, worldBoundsMax = s.WorldBounds.max
            };
        }

        static string Sha(string path)
        {
            using (var s = System.Security.Cryptography.SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        static string ShaBytes(byte[] b)
        {
            using (var s = System.Security.Cryptography.SHA256.Create()) return BitConverter.ToString(s.ComputeHash(b)).Replace("-", "").ToLowerInvariant();
        }

        // ------------------------------------------------------------------ 報告
        [Serializable] class VideoRec { public string view, path, ffmpegError, sha256; public int frames, fps; public float seconds; public bool contextHidden; }
        [Serializable] class SheetRecJ
        {
            public string name, package, jsonSha256, posSha256, posLoSha256, meshSource, meshSha256, uv3Source, sdf;
            public int rows, cols, layers, whiteNeverCount, flatClass, whiteClassVertexCount, classFileAgree; public bool posLoInPackage, posLoFromPackage, whiteEnabled, whiteFromHeight, whiteFromPackage, classFileUsed;
            public long positionGpuBytes, whiteGpuBytes, posLoGpuBytes, alphaNot65535, posLoAlphaNot255; public float loadSeconds; public Vector3 worldBoundsMin, worldBoundsMax;
        }
        [Serializable] class FrameRec
        {
            public int i; public string phase, state; public double t, tau; public string[] hash; public float[] maxMove;
            public float seamHeroNear, seamHeroNearDy, seamHeroNearDot, seamHeroNearSigned, seamNearFar, seamNearFarDy, seamNearFarT, seamNearFarDot; public bool rimCountMatches; public int nearFarStep;
            public float seamHeroNearDotP01, seamNearFarDotP01; public int seamHeroNearDotBelow05, seamNearFarDotBelow05;
            public float seamHeroNearSideDotMin = float.NaN, seamHeroNearSideDotP01 = float.NaN; public int seamHeroNearSideBelow09, seamHeroNearSideCount;
            public float eyeY, eyeClearance, eyeAbove; public bool eyeUnderWater; public int eyeHitsAbove, eyeHitsBelow;
        }
        [Serializable] class PlaybackRec
        {
            public FrameRec[] frames; public string framesCsv; public string[] sheetNames; public float[] orientation;
            public bool waitingFramesSameAsStart, holdingFramesSameAsTStar; public double startFrameT, lastWaitingT, lastWaitingTau, firstHoldT, firstHoldTau;
            public float[] startStep, startMedianNext30, startMaxNext30, endStep, endMedianPrev30, endMaxPrev30, holdMaxStep, playMaxStep;
            public float seamHeroNearMaxGap, seamHeroNearMaxDy, seamHeroNearMinDot, seamHeroNearMaxDv, seamNearFarMaxGap, seamNearFarMaxDy, seamNearFarTJunctionMaxGap, seamNearFarMinDot;
            public float seamHeroNearMinDotP01, seamNearFarMinDotP01; public int seamHeroNearMaxBelow05, seamNearFarMaxBelow05;
            public float seamHeroNearSideMinDot, seamHeroNearSideMinDotP01; public int seamHeroNearSideMaxBelow09, seamHeroNearSideCount;
            public int eyeUnderWaterFrames; public float eyeMinClearance, eyeMinAbove; public double eyeMinClearanceT;
            public int jitterTicks; public double jitterMaxDt, jitterMaxDTau, jitterEndTau; public float maxStepSeconds; public float seconds;
        }
        [Serializable] class HoleRec { public string csv, methodJa; public int frames, seatWorstHolePx, paintingWorstHolePx, seatFramesWithHoles, paintingFramesWithHoles; public double seatWorstT, paintingWorstT; public float seconds; public bool withFlatSea; }
        [Serializable] class BoatRec { public string path, sha256, boatObject, mode; }
        [Serializable] class Report
        {
            public string name, unity, device, graphicsApi, warpFile, warpSha256, seaDir, scenePath, sceneSha256, wave27Transform, paramsSha256;
            public int heroColMin, heroColMax, heroTrianglesFull, heroTrianglesWindow, heroLineInset, heroLineTrianglesWindow;
            public string[] hidden; public double[] stillT; public int fps, flatClass; public float seaWhiteY; public bool curtain;
            public string[] attachedFoam; public int attachVertex = -1; public float attachTargetDistance;
            public Vector4 flatSeaSquare; public float flatSeaY; public string flatSeaMode = "";
            public List<SheetRecJ> sheets = new List<SheetRecJ>();
            public bool knotTauSame, frameSame; public long gpuBytesSheets, driverBytesBefore, driverBytesAfter; public double tauAtT0, tauAtTStar;
            public Vector3 seatEye, travelDir;
            public BoatRec boat;
            public List<VideoRec> videos = new List<VideoRec>();
            public PlaybackRec playback; public HoleRec holes, holesNoFlat;
            public bool protectedUnchanged, passed; public string[] protectedFiles, changedFiles, files, filesSha256; public float totalSeconds;
        }
    }
}
