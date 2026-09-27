using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using GreatWave.ArtFirst;
using UnityEditor;
using UnityEditor.Rendering;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design27.EditorTools
{
    // 設計27「単発砕波を作る ― 形成から t* まで」の Unity 側（再生と採取）。美術優先30 の AF30Formation・31 の AF31WhiteFormation と同じ組み立て・採取の
    // 手順で、主役波を DS27 keypose（DS27KeyposePlayer：不等間隔の節点の Hermite、波の枠の原点 O(τ)、τ の白の時間場）で動かす。
    // 美術優先の番号のファイル（シェーダー・スクリプト・マテリアル・シーン・Editor・プレハブ）は読むだけで変えない（前後の SHA-256 を記録）。
    // 1) Build：空のシーンに美術優先27修正01 のプレハブ AF27R01_Context.prefab を完全に展開し、GWClock と主役波を置く。
    //    主役波 = K*（26修正01）の固定位相のメッシュ（AF26KStarMesh）＋ 28修正01 の焼き込み（AF28NprWave、UV3）＋ DS27 NPR White／DS27 Outline Keypose
    //    ＋ DS27KeyposePlayer（既定のパッケージ Build/Design/27/art_on）。シーンは Assets/GreatWave/Scenes/Tests/DS27_Formation.unity。
    // 2) Render（引数で版・時間曲線・パッケージを選ぶ。シーンは保存しない）：出力は Build/Design/27/<版>_<時間曲線>/（Git 対象外）。
    //    a. t*（τ = 0）：美術優先28修正01・30・31 と同じ名前・同じ設定の色の画像と色区 ID・線 ID（t28/render）。原画の評価器（美術優先23 系）で測る。
    //    b. GPU の読み戻し：頂点シェーダーと同じ関数（DS27KeyposeCapture.compute）で全頂点の位置と法線を書き、ds27_player_ref.py が numpy と照合する。
    //    c. 静止画：段階の名前の付いた τ（a・b・c・d・唇先の頂点・t*）で、原画視点・座席 v1・左の側面。
    //    d. 動画：t = 0〜14 s を 30 fps（421 コマ）、各コマの τ は時間曲線の表（既定または代案）から。原画視点・座席 v1・左の側面
    //       （左の側面は波の枠とともに平行移動するカメラで、主役波・空のドーム・参照海面だけ。t* で美術優先30 の側面と同じ位置）。
    //       ffmpeg へ生の RGB を流し、同じ入力から MP4（libx264、美術優先30・31 と同じ設定）と PNG の連番を書く。
    //    e. 自作シェーダー（DS27 の 2 本）の SPI キーワードでのコンパイル（美術優先30・32 と同じ方法）。
    //    PC のオフスクリーン描画で、HMD 実機ではない。
    // 引数（Unity のコマンドラインの後ろ。run_ds27_unity.ps1 が渡す）：
    //   -ds27Version <art_on|art_off|…>（既定 art_on）、-ds27Warp <default|alt>（既定 default）、
    //   -ds27Package <フォルダー>（既定 Build/Design/27/<版>）、-ds27WarpFile <表>（既定 ../Tools/GWWaveGen/ds27/timewarp_<時間曲線>.json）、
    //   -ds27Out <フォルダー>（既定 Build/Design/27/<版>_<時間曲線>）、-ds27Stills a=-4.2,b=-3.4,…（既定はパッケージの stage_tau、なければ設計26 §3.1 の峰の行）、
    //   -ds27Views painting,seat,side_left（動画の視点。seat_form も可）、-ds27Skip video,frames,stills,t28,capture（飛ばす工程）、-ds27CaptureMax 120。
    // BuildAndRender はシーンを作り直す（保存するたびにシーンのファイルが変わる）ので、版・時間曲線の組ごとに描くときは、
    // 最初の 1 回だけ BuildAndRender、残りは RenderOnly を使う。
    public static class DS27Formation
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/DS27_Formation.unity";
        const string OutRoot = "Build/Design/27";
        const string MatDir = "Assets/GreatWave/Design27/Materials";
        const string ContextPrefab = "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab";
        const string Npr28Mat = "Assets/GreatWave/ArtFirst/Materials/AF28_NPR.mat";
        const string Outline28Mat = "Assets/GreatWave/ArtFirst/Materials/AF28_Outline.mat";
        const string NprMatPath = MatDir + "/DS27_NPR_White.mat";
        const string OutlineMatPath = MatDir + "/DS27_Outline_Keypose.mat";
        const string NprShaderPath = "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader";
        const string OutlineShaderPath = "Assets/GreatWave/Design27/Shaders/DS27_Outline_Keypose.shader";
        const string CapturePath = "Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute";
        const string SeatJson = "../Tools/GWContext/seat_v1.json";
        const string KStarGwb = "Build/ArtFirst/26修正01/kstar/kstar_a45.gwb";
        const string Bake28 = "Build/ArtFirst/28修正01/bake/af28r01_uvsdf_a45.bin";
        const string Warp28 = "Build/ArtFirst/28修正01/bake/af28r01_uvwarp_a45.json";
        const string RootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string WaveName = "DS27 主役波（K* の格子、DS27 keypose で形成から t* まで、NPR は 28修正01 の焼き込み＋τ の白の時間場）";
        const string ClockName = "DS27 GWClock";
        const string CamRoot = "DS27 カメラ";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080;
        const float TStar = 12f, TEnd = 14f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);
        static readonly Vector3 PaintingPosition = new Vector3(0, 3, -62), PaintingTarget = new Vector3(-2.5f, 9.7f, 4);
        static readonly Vector3 SidePosition = new Vector3(-90, 30, -14), SideTarget = new Vector3(-5, 8, -3);
        const float SideFov = 45;
        const float SeatFormPitchDeg = 30f;   // 美術優先30 と同じ：唇の方位、仰角 30°（任意の視点 seat_form）
        // 段階の名前の付いた τ の既定（設計26 §3.1 の峰で最も高い巻きの行。パッケージの stage_tau があればそちらを使う）
        static readonly string[] StageNames = { "a", "b", "c", "d", "apex", "tstar" };
        static readonly double[] StageTau = { -4.2, -3.4, -2.4, -2.05, -1.36, 0.0 };

        static string[] ProtectedFiles => new[] {
            ContextPrefab, Npr28Mat, Outline28Mat, "Assets/GreatWave/ArtFirst/Materials/AF28_SeaFlat.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_SkyDome.mat",
            "Assets/GreatWave/ArtFirst/Meshes/AF27R01_RightSlope.asset",
            "Assets/GreatWave/ArtFirst/Shaders/AF28_NPR.shader", "Assets/GreatWave/ArtFirst/Shaders/AF28_Outline.shader", "Assets/GreatWave/Shaders/Sampling19/Sampling19Surface.cginc",
            "Assets/GreatWave/ArtFirst/Shaders/AF30_NPR_Keypose.shader", "Assets/GreatWave/ArtFirst/Shaders/AF30_Outline_Keypose.shader", "Assets/GreatWave/ArtFirst/Shaders/AF30Keypose.cginc",
            "Assets/GreatWave/ArtFirst/Shaders/AF30KeyposeCore.cginc", "Assets/GreatWave/ArtFirst/Shaders/AF30KeyposeCapture.compute", "Assets/GreatWave/ArtFirst/Shaders/AF31_NPR_White.shader",
            "Assets/GreatWave/ArtFirst/Materials/AF30_NPR_Keypose.mat", "Assets/GreatWave/ArtFirst/Materials/AF30_Outline_Keypose.mat",
            "Assets/GreatWave/ArtFirst/Materials/AF31_NPR_White.mat", "Assets/GreatWave/ArtFirst/Materials/AF31_Outline_Keypose.mat",
            "Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs", "Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs", "Assets/GreatWave/ArtFirst/Scripts/AF30KeyposeWave.cs",
            "Assets/GreatWave/ArtFirst/Scripts/AF31WhiteField.cs", "Assets/GreatWave/ArtFirst/Scripts/GWClock.cs",
            "Assets/GreatWave/ArtFirst/Editor/AF28R01NprScene.cs", "Assets/GreatWave/ArtFirst/Editor/AF30Formation.cs", "Assets/GreatWave/ArtFirst/Editor/AF31WhiteFormation.cs",
            "Assets/GreatWave/Scenes/Tests/AF28R01_NPR.unity", "Assets/GreatWave/Scenes/Tests/AF30_Formation.unity", "Assets/GreatWave/Scenes/Tests/AF31_White.unity",
            "Assets/GreatWave/Scenes/Tests/AF_CP1.unity", SeatJson, KStarGwb, Bake28, Warp28 };

        // ------------------------------------------------------------------ 引数
        public class Config
        {
            public string version = "art_on", warp = "default", package, warpFile, outDir;
            public List<string> stillNames = new List<string>();
            public List<double> stillTau = new List<double>();
            public bool stillsFromArgs;
            public string[] views = { "painting", "seat", "side_left" };
            public HashSet<string> skip = new HashSet<string>();
            public int fps = 30, captureMax = 120;
        }

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        public static Config ParseArgs()
        {
            var a = Environment.GetCommandLineArgs();
            var c = new Config();
            c.version = Arg(a, "-ds27Version") ?? c.version;
            c.warp = Arg(a, "-ds27Warp") ?? c.warp;
            c.package = Arg(a, "-ds27Package") ?? (OutRoot + "/" + c.version);
            c.warpFile = Arg(a, "-ds27WarpFile") ?? ("../Tools/GWWaveGen/ds27/timewarp_" + c.warp + ".json");
            c.outDir = Arg(a, "-ds27Out") ?? (OutRoot + "/" + c.version + "_" + c.warp);
            var st = Arg(a, "-ds27Stills");
            if (!string.IsNullOrEmpty(st))
            {
                foreach (var kv in st.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries))
                {
                    var p = kv.Split('=');
                    c.stillNames.Add(p[0].Trim());
                    c.stillTau.Add(double.Parse(p[1], CultureInfo.InvariantCulture));
                }
                c.stillsFromArgs = true;
            }
            var v = Arg(a, "-ds27Views");
            if (!string.IsNullOrEmpty(v)) c.views = v.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            var sk = Arg(a, "-ds27Skip");
            if (!string.IsNullOrEmpty(sk)) foreach (var s in sk.Split(',')) c.skip.Add(s.Trim());
            var cm = Arg(a, "-ds27CaptureMax");
            if (!string.IsNullOrEmpty(cm)) c.captureMax = int.Parse(cm, CultureInfo.InvariantCulture);
            var fps = Arg(a, "-ds27Fps");
            if (!string.IsNullOrEmpty(fps)) c.fps = int.Parse(fps, CultureInfo.InvariantCulture);
            return c;
        }

        public static void BuildAndRender() { Build(); Render(ParseArgs()); }
        public static void RenderOnly() { Render(ParseArgs()); }

        // ------------------------------------------------------------------ マテリアル
        static void EnsureMaterials(out Material npr, out Material outline)
        {
            if (!AssetDatabase.IsValidFolder(MatDir)) AssetDatabase.CreateFolder("Assets/GreatWave/Design27", "Materials");
            var src = AssetDatabase.LoadAssetAtPath<Material>(Npr28Mat);
            var srcL = AssetDatabase.LoadAssetAtPath<Material>(Outline28Mat);
            var sh = AssetDatabase.LoadAssetAtPath<Shader>(NprShaderPath);
            var shL = AssetDatabase.LoadAssetAtPath<Shader>(OutlineShaderPath);
            if (src == null || srcL == null || sh == null || shL == null) throw new InvalidOperationException("美術優先28 のマテリアルか DS27 のシェーダーがありません。");
            if (ShaderUtil.ShaderHasError(sh) || ShaderUtil.ShaderHasError(shL))
                throw new InvalidOperationException("DS27 のシェーダーにエラーがあります: " + string.Join(" | ", ShaderUtil.GetShaderMessages(sh).Concat(ShaderUtil.GetShaderMessages(shL)).Select(m => m.message)));
            npr = AssetDatabase.LoadAssetAtPath<Material>(NprMatPath);
            if (npr == null) { npr = new Material(sh); AssetDatabase.CreateAsset(npr, NprMatPath); }
            npr.shader = sh;
            foreach (var p in new[] { "_White", "_Mizuiro", "_AiMid", "_AiDark" }) npr.SetColor(p, src.GetColor(p));
            foreach (var p in new[] { "_EncodeLevels", "_AAScale", "_FlatClass" }) npr.SetFloat(p, src.GetFloat(p));
            npr.SetFloat("_PreWhiteClass", 2);   // 美術優先31 と同じ既定（藍中）。パッケージの pre_white_index があれば DS27KeyposePlayer が上書きする
            EditorUtility.SetDirty(npr);
            outline = AssetDatabase.LoadAssetAtPath<Material>(OutlineMatPath);
            if (outline == null) { outline = new Material(shL); AssetDatabase.CreateAsset(outline, OutlineMatPath); }
            outline.shader = shL;
            outline.SetColor("_LineColor", srcL.GetColor("_LineColor"));
            foreach (var p in new[] { "_LineAngle", "_MinWidth", "_MaxWidth" }) outline.SetFloat(p, srcL.GetFloat(p));
            EditorUtility.SetDirty(outline);
            AssetDatabase.SaveAssets();
        }

        // ------------------------------------------------------------------ 組み立て
        public static void Build()
        {
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            EnsureMaterials(out var npr, out var outline);
            var seat = LoadSeat();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat; RenderSettings.ambientLight = Color.white; RenderSettings.fog = false; RenderSettings.skybox = null;
            var ctx = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(ContextPrefab));
            PrefabUtility.UnpackPrefabInstance(ctx, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            ctx.name = RootName;

            var clockGo = new GameObject(ClockName);
            var clock = clockGo.AddComponent<GWClock>();
            clock.seconds = TStar; clock.loopSeconds = TEnd; clock.tStarSeconds = TStar; clock.playInPlayMode = true;

            var wave = new GameObject(WaveName);
            wave.AddComponent<MeshFilter>();
            var r = wave.AddComponent<MeshRenderer>();
            r.sharedMaterial = npr;
            r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
            r.lightProbeUsage = LightProbeUsage.Off; r.reflectionProbeUsage = ReflectionProbeUsage.Off;
            wave.AddComponent<AF26KStarMesh>().dataPath = KStarGwb;
            var line = new GameObject("DS27 外殻線 v0（keypose、法線は格子から）");
            line.transform.SetParent(wave.transform, false);
            line.AddComponent<MeshFilter>();
            var lr = line.AddComponent<MeshRenderer>();
            lr.sharedMaterial = outline;
            lr.shadowCastingMode = ShadowCastingMode.Off; lr.receiveShadows = false;
            lr.lightProbeUsage = LightProbeUsage.Off; lr.reflectionProbeUsage = ReflectionProbeUsage.Off;
            var nw = wave.AddComponent<AF28NprWave>();
            nw.sdfPath = Bake28; nw.warpPath = Warp28; nw.size = 4096; nw.outline = lr;
            var pl = wave.AddComponent<DS27KeyposePlayer>();
            pl.packageDir = OutRoot + "/art_on"; pl.clock = clock; pl.driveFromClock = false;
            pl.timewarpPath = "../Tools/GWWaveGen/ds27/timewarp_default.json";

            var cams = new GameObject(CamRoot);
            var eye = V(seat.seat.eye_world);
            var tgt = V(seat.view.target_world);
            MakeCamera(cams, "painting", PaintingPosition, PaintingTarget, 26);
            MakeCamera(cams, "seat", eye, tgt, seat.view.vertical_fov_deg);
            MakeCamera(cams, "seat_low", eye, V(seat.view.qa_hemisphere_look_world), seat.view.vertical_fov_deg);
            MakeCamera(cams, "seat_form", eye, SeatFormTarget(eye, tgt), seat.view.vertical_fov_deg);
            MakeCamera(cams, "side_left", SidePosition, SideTarget, SideFov);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("シーンを保存できません。");
            AssetDatabase.SaveAssets();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(OutRoot);
            var rep = new BuildReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePath, sceneSha256 = Sha(ScenePath),
                nprMat = NprMatPath, nprMatSha256 = Sha(NprMatPath), outlineMat = OutlineMatPath, outlineMatSha256 = Sha(OutlineMatPath),
                seatEye = eye, seatTarget = tgt, seatFov = seat.view.vertical_fov_deg,
                protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]),
                protectedFiles = ProtectedFiles.Select(p => p + " " + after[p]).ToArray(), changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray()
            };
            File.WriteAllText(OutRoot + "/ds27_build_report.json", JsonUtility.ToJson(rep, true));
            if (!rep.protectedUnchanged) throw new InvalidOperationException("保護したファイルが変わりました: " + string.Join(", ", rep.changedFiles));
            UnityEngine.Debug.Log("DS27_BUILD_DONE");
        }

        static Vector3 SeatFormTarget(Vector3 eye, Vector3 tgt)
        {
            var f = tgt - eye;
            float yaw = Mathf.Atan2(f.x, f.z), p = SeatFormPitchDeg * Mathf.Deg2Rad;
            return eye + 10f * new Vector3(Mathf.Sin(yaw) * Mathf.Cos(p), Mathf.Sin(p), Mathf.Cos(yaw) * Mathf.Cos(p));
        }

        // ------------------------------------------------------------------ 描画
        public static void Render(Config cfg)
        {
            var total = Stopwatch.StartNew();
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var wave = FindRoot(WaveName);
            var ctx = FindRoot(RootName);
            var nw = wave.GetComponent<AF28NprWave>();
            var pl = wave.GetComponent<DS27KeyposePlayer>();
            var clock = FindRoot(ClockName).GetComponent<GWClock>();
            var mesh = nw.EnsureLoaded();
            long gfxBefore = UnityEngine.Profiling.Profiler.GetAllocatedMemoryForGraphicsDriver();
            pl.whiteEnabled = true;
            pl.Reload(cfg.package);
            long gfxAfter = UnityEngine.Profiling.Profiler.GetAllocatedMemoryForGraphicsDriver();
            var pm = pl.PackageMeta;
            var warp = DS27TimeWarp.Load(cfg.warpFile);
            string od = cfg.outDir;
            Directory.CreateDirectory(od);
            var names = new[] { "painting", "seat", "seat_low", "seat_form", "side_left" };
            var cams = names.ToDictionary(n => n, FindCamera);
            var sidePos0 = cams["side_left"].transform.position;
            var sideRot0 = cams["side_left"].transform.rotation;
            var o0 = pl.OriginAt(0.0);

            // 段階の静止画の τ
            var stillNames = new List<string>(); var stillTau = new List<double>();
            string stillSource;
            if (cfg.stillsFromArgs) { stillNames.AddRange(cfg.stillNames); stillTau.AddRange(cfg.stillTau); stillSource = "引数 -ds27Stills"; }
            else if (ReadStageTau(pm.dir, stillNames, stillTau)) stillSource = "パッケージの stage_tau";
            else { stillNames.AddRange(StageNames); stillTau.AddRange(StageTau); stillSource = "既定（設計26 §3.1 の峰で最も高い巻きの行の τ）"; }

            var rep = new RenderReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                graphicsMemoryMB = SystemInfo.graphicsMemorySize, colorSpace = QualitySettings.activeColorSpace.ToString(),
                version = cfg.version, warp = cfg.warp, package = pm.dir, packageJsonSha256 = pm.jsonSha256, posSha256 = pm.posSha256, twhiteSha256 = pm.twhiteSha256,
                warpFile = warp.Path, warpFileSha256 = Sha(warp.Path), warpRateHzMin = (float)warp.MinRateHz, warpTauMin = (float)warp.TauMin, warpTauMax = (float)warp.TauMax,
                outDir = Path.GetFullPath(od), layers = pm.layers, knotTau = pm.knotTau.Select(x => (float)x).ToArray(),
                frameTauMin = (float)pm.frameTau[0], frameTauMax = (float)pm.frameTau[pm.frameTau.Length - 1], frameRateHzMin = (float)pl.FrameMinRateHz,
                warpInsideKnots = warp.TauMin >= pm.knotTau[0] - 1e-9 && warp.TauMax <= 1e-9,
                warpInsideFrame = warp.TauMin >= pm.frameTau[0] - 1e-9 && warp.TauMax <= pm.frameTau[pm.frameTau.Length - 1] + 1e-9,
                positionGpuBytes = pl.PositionGpuBytes, whiteGpuBytes = pl.WhiteGpuBytes,
                texture2DArrayRgba64EquivalentBytes = (long)pm.layers * pm.rows * pm.cols * 8,
                graphicsDriverBytesBefore = gfxBefore, graphicsDriverBytesAfter = gfxAfter, loadSeconds = pl.LoadSeconds,
                alphaNot65535 = pl.AlphaNot65535, whiteFiniteMin = (float)pl.WhiteFiniteMin, whiteFiniteMax = (float)pl.WhiteFiniteMax, whiteNeverCount = pl.WhiteNeverCount,
                preWhiteIndex = pm.hasPreWhiteIndex ? pm.preWhiteIndex : -1, worldBoundsMin = pl.WorldBounds.min, worldBoundsMax = pl.WorldBounds.max,
                stillSource = stillSource, stillNames = stillNames.ToArray(), stillTau = stillTau.Select(x => (float)x).ToArray(),
                renderMethod = "Editor batchmode：DS27KeyposePlayer.ApplyTau（大域の値：4 層と重み、O(τ)、τ）→ Camera.Render → RenderTexture → ReadPixels。色は sRGB の RT（MSAA 8x → 解決）、ID は線形の RT（MSAA なし）。動画は各コマ t = i/fps の τ を時間曲線の表から求める。PC のオフスクリーン描画で、HMD 実機ではない。"
            };
            rep.vertexCount = mesh.vertexCount;
            rep.indexSha256 = TriSha(mesh);
            var files = new List<string>();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 0);
            try
            {
                // a. t*（美術優先28修正01・30・31 と同じ採取。ファイル名も同じにして、評価の手順をそのまま使う）
                if (!cfg.skip.Contains("t28"))
                {
                    SetTau(pl, clock, 0.0, TStar);
                    string d28 = od + "/t28/render";
                    Directory.CreateDirectory(d28);
                    nw.outline.enabled = true;
                    foreach (var v in new[] { "painting", "seat", "seat_low" }) files.Add(Capture(cams[v], W, H, true, d28 + "/af28r01_" + v + ".png"));
                    ctx.SetActive(false);
                    nw.outline.enabled = false;
                    files.Add(Capture(cams["painting"], W, H, true, d28 + "/af28r01_painting_kstar.png"));
                    files.Add(Capture(cams["seat"], W, H, true, d28 + "/af28r01_seat_kstar.png"));
                    files.Add(Capture(cams["seat_low"], W, H, true, d28 + "/af28r01_seat_low_kstar.png"));
                    Shader.SetGlobalFloat("_AF28IdMode", 1);
                    files.Add(Capture(cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_class_ids.png"));
                    files.Add(Capture(cams["seat"], W, H, false, d28 + "/af28r01_seat_class_ids.png"));
                    files.Add(Capture(cams["seat_low"], W, H, false, d28 + "/af28r01_seat_low_class_ids.png"));
                    nw.outline.enabled = true;
                    files.Add(Capture(cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_line_ids.png"));
                    Shader.SetGlobalFloat("_AF28IdMode", 0);
                    ctx.SetActive(true);
                    // 白の到着時刻の図（t*、主役波だけ、線なし）
                    nw.outline.enabled = false;
                    ctx.SetActive(false);
                    Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 4);
                    files.Add(Capture(cams["painting"], W, H, true, od + "/t28/ds27_arrival_painting.png"));
                    Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 0);
                    ctx.SetActive(true);
                    nw.outline.enabled = true;
                }

                // b. GPU の読み戻し（頂点シェーダーと同じ関数のコンピュート）
                if (!cfg.skip.Contains("capture"))
                {
                    var sw = Stopwatch.StartNew();
                    string dc = od + "/gpu_capture";
                    Directory.CreateDirectory(dc);
                    foreach (var f in Directory.GetFiles(dc, "ds27_gpu_*.bin")) File.Delete(f);
                    var cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(CapturePath);
                    if (cs == null) throw new InvalidOperationException("DS27KeyposeCapture.compute がありません。");
                    var msgs = ShaderUtil.GetComputeShaderMessages(cs);
                    rep.computeMessages = string.Join(" | ", msgs.Select(m => m.severity + ": " + m.message));
                    int k = cs.FindKernel("DS27Capture");
                    int nvtx = mesh.vertexCount;
                    var taus = CaptureTaus(pm.knotTau, warp, stillTau, cfg.captureMax);
                    var capList = new List<CaptureRec>();
                    using (var buf = new ComputeBuffer(nvtx * 2, 16))
                    {
                        var outv = new Vector4[nvtx * 2];
                        var fl = new float[nvtx * 6];
                        var bytes = new byte[nvtx * 24];
                        for (int q = 0; q < taus.Count; q++)
                        {
                            double tau = taus[q];
                            SetTau(pl, clock, tau, float.NaN);
                            pl.BindCompute(cs, k);
                            cs.SetBuffer(k, "_DS27Out", buf);
                            cs.SetInt("_DS27Count", nvtx);
                            cs.Dispatch(k, (nvtx + 63) / 64, 1, 1);
                            buf.GetData(outv);
                            for (int i = 0; i < nvtx; i++)
                            {
                                var p = outv[2 * i]; var n = outv[2 * i + 1];
                                fl[6 * i] = p.x; fl[6 * i + 1] = p.y; fl[6 * i + 2] = p.z; fl[6 * i + 3] = n.x; fl[6 * i + 4] = n.y; fl[6 * i + 5] = n.z;
                            }
                            Buffer.BlockCopy(fl, 0, bytes, 0, bytes.Length);
                            var name = string.Format(CultureInfo.InvariantCulture, "ds27_gpu_{0:000}_tau{1:+0.000000;-0.000000}.bin", q, tau);
                            File.WriteAllBytes(Path.Combine(dc, name), bytes);
                            capList.Add(new CaptureRec { tau = tau, file = name, slices = pl.Slices.ToArray(), weights = pl.WeightsNow.ToArray(), origin = new[] { pl.AppliedOrigin.x, pl.AppliedOrigin.y, pl.AppliedOrigin.z } });
                        }
                    }
                    var cr = new CaptureReport { layout_ja = "頂点ごとに float32 × 6（ワールドの位置 xyz、法線 xyz）、頂点の添字 = 行 × 400 + 列", captures = capList.ToArray(), seconds = (float)sw.Elapsed.TotalSeconds };
                    File.WriteAllText(Path.Combine(dc, "ds27_gpu_capture.json"), JsonUtility.ToJson(cr, true));
                    rep.captureCount = capList.Count;
                    rep.captureSeconds = cr.seconds;
                }

                // c. 段階の静止画
                if (!cfg.skip.Contains("stills"))
                {
                    string ds = od + "/stills";
                    Directory.CreateDirectory(ds);
                    for (int s = 0; s < stillNames.Count; s++)
                    {
                        SetTau(pl, clock, stillTau[s], float.NaN);
                        foreach (var v in new[] { "painting", "seat", "side_left" })
                        {
                            var hid = v == "side_left" ? HideContext(ctx) : new List<Renderer>();
                            try
                            {
                                PlaceSide(cams["side_left"], sidePos0, sideRot0, pl.AppliedOrigin - o0);
                                files.Add(Capture(cams[v], W, H, true, string.Format(CultureInfo.InvariantCulture, "{0}/ds27_{1}_{2}_tau{3:+0.000;-0.000}.png", ds, v, stillNames[s], stillTau[s])));
                            }
                            finally { foreach (var rr in hid) rr.enabled = true; }
                        }
                    }
                    PlaceSide(cams["side_left"], sidePos0, sideRot0, Vector3.zero);
                }

                // d. 動画（30 fps、t = 0〜14 s、421 コマ）
                if (!cfg.skip.Contains("video"))
                {
                    string dv = od + "/video";
                    Directory.CreateDirectory(dv);
                    int n = Mathf.RoundToInt(TEnd * cfg.fps) + 1;
                    var ft = new FrameTable { fps = cfg.fps, t = new float[n], tau = new float[n] };
                    for (int i = 0; i < n; i++) { ft.t[i] = i / (float)cfg.fps; ft.tau[i] = (float)warp.TauAt(i / (double)cfg.fps); }
                    File.WriteAllText(dv + "/ds27_frames_tau.json", JsonUtility.ToJson(ft, true));
                    foreach (var v in cfg.views)
                    {
                        var sw = Stopwatch.StartNew();
                        var mp4 = dv + "/ds27_" + v + "_" + cfg.fps + "fps.mp4";
                        string framesDir = cfg.skip.Contains("frames") ? null : od + "/frames/" + v;
                        bool side = v == "side_left";
                        var hidden = side ? HideContext(ctx) : new List<Renderer>();
                        int nf; string err;
                        try { nf = EncodeVideo(cams[v], pl, clock, warp, cfg.fps, TEnd, mp4, framesDir, side ? (Action)(() => PlaceSide(cams["side_left"], sidePos0, sideRot0, pl.AppliedOrigin - o0)) : null, out err); }
                        finally { foreach (var rr in hidden) rr.enabled = true; PlaceSide(cams["side_left"], sidePos0, sideRot0, Vector3.zero); }
                        int pngs = framesDir != null && Directory.Exists(framesDir) ? Directory.GetFiles(framesDir, "*.png").Length : 0;
                        rep.videos.Add(new VideoRec { view = v, path = Path.GetFullPath(mp4), frames = nf, fps = cfg.fps, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err,
                            sha256 = File.Exists(mp4) ? Sha(mp4) : "", framesDir = framesDir == null ? "" : Path.GetFullPath(framesDir), pngFrames = pngs, sideTracksFrame = side, contextHidden = side });
                        if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
                    }
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 0);
                ctx.SetActive(true);
                nw.outline.enabled = true;
                PlaceSide(cams["side_left"], sidePos0, sideRot0, Vector3.zero);
                SetTau(pl, clock, 0.0, TStar);
            }
            // e. SPI のコンパイル
            rep.spi = CheckShaders(new[] { NprShaderPath, OutlineShaderPath });
            rep.meshUnchanged = mesh.vertexCount == 96000 && TriSha(mesh) == rep.indexSha256;
            rep.cameras = names.Select(n => { var c = cams[n]; return new CamRec { name = n, position = c.transform.position, forward = c.transform.forward, fov = c.fieldOfView }; }).ToArray();
            rep.clampedKnotCalls = pl.ClampedKnotCount;
            rep.clampedFrameCalls = pl.ClampedFrameCount;
            rep.files = files.ToArray();
            rep.filesSha256 = files.Select(Sha).ToArray();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]);
            rep.changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray();
            rep.sceneSha256 = Sha(ScenePath);
            rep.totalSeconds = (float)total.Elapsed.TotalSeconds;
            rep.passed = rep.protectedUnchanged && rep.meshUnchanged && rep.spi.allCompiled && rep.spi.allStereoOutput && rep.alphaNot65535 == 0;
            File.WriteAllText(od + "/ds27_render_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("DS27_RENDER_DONE files=" + files.Count + " seconds=" + rep.totalSeconds + " passed=" + rep.passed + " out=" + rep.outDir);
            if (!rep.passed) throw new InvalidOperationException("描画の検査が不合格です（ds27_render_report.json）。");
        }

        static bool ReadStageTau(string dir, List<string> names, List<double> taus)
        {
            var root = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(Path.Combine(dir, "ds27_keypose.json"))), "ds27_keypose.json");
            if (!DS27Json.Has(root, "stage_tau")) return false;
            var st = DS27Json.AsObj(root["stage_tau"], "stage_tau");
            foreach (var kv in st)
            {
                if (!(kv.Value is double x)) continue;
                names.Add(kv.Key); taus.Add(x);
            }
            if (!names.Contains("tstar")) { names.Add("tstar"); taus.Add(0.0); }
            return names.Count > 0;
        }

        // 読み戻す τ：t*、最初の節点、段階の τ、時間曲線の 1 s ごと、節点（最大 20）、節点の間の 1/3・2/3（最大 captureMax まで、区間を等しく間引く）
        static List<double> CaptureTaus(double[] knots, DS27TimeWarp warp, List<double> stills, int max)
        {
            var l = new List<double> { 0.0, knots[0] };
            l.AddRange(stills);
            for (int s = 0; s <= (int)TEnd; s++) l.Add(warp.TauAt(s));
            int n = knots.Length;
            int kk = Math.Min(n, 20);
            for (int i = 0; i < kk; i++) l.Add(knots[kk == 1 ? 0 : (int)Math.Round(i * (n - 1) / (double)(kk - 1))]);
            int room = Math.Max(0, max - l.Count);
            int intervals = n - 1;
            int useI = Math.Min(intervals, room / 2);
            for (int j = 0; j < useI; j++)
            {
                int i = useI == 1 ? 0 : (int)Math.Round(j * (intervals - 1) / (double)(useI - 1));
                l.Add(knots[i] + (knots[i + 1] - knots[i]) / 3.0);
                l.Add(knots[i] + 2.0 * (knots[i + 1] - knots[i]) / 3.0);
            }
            var seen = new HashSet<long>();
            var outl = new List<double>();
            foreach (var t in l) if (seen.Add((long)Math.Round(t * 1e6))) outl.Add(t);
            outl.Sort();
            return outl;
        }

        static void SetTau(DS27KeyposePlayer pl, GWClock clock, double tau, float t)
        {
            if (!float.IsNaN(t)) clock.SetSeconds(t);
            pl.ApplyTau(tau);
        }

        // 左の側面：波の枠とともに平行移動する（t* で美術優先30 の側面と同じ位置・向き）
        static void PlaceSide(Camera cam, Vector3 pos0, Quaternion rot0, Vector3 delta)
        {
            cam.transform.SetPositionAndRotation(pos0 + delta, rot0);
        }

        // 確認用：主役波・空のドーム・参照海面だけ（船・富士・仮置き・右船の水面を描画の間だけ隠す。美術優先30 と同じ）
        static List<Renderer> HideContext(GameObject ctx)
        {
            var hid = new List<Renderer>();
            foreach (var rr in ctx.GetComponentsInChildren<Renderer>(false))
            {
                if (!rr.enabled || rr.name == "AF27 空のドーム" || rr.name == "AF27 参照海面") continue;
                rr.enabled = false; hid.Add(rr);
            }
            return hid;
        }

        // ffmpeg へ生の RGB を流し、同じ入力から MP4（美術優先30・31 と同じ libx264 の設定）と PNG の連番（framesDir があれば）を書く
        static int EncodeVideo(Camera camera, DS27KeyposePlayer pl, GWClock clock, DS27TimeWarp warp, int fps, float seconds, string mp4, string framesDir, Action beforeRender, out string err)
        {
            int n = Mathf.RoundToInt(seconds * fps) + 1;
            string outs;
            if (framesDir != null)
            {
                Directory.CreateDirectory(framesDir);
                foreach (var f in Directory.GetFiles(framesDir, "*.png")) File.Delete(f);
                outs = string.Format("-filter_complex \"[0:v]vflip,split=2[a][b]\" -map \"[a]\" -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart \"{0}\" -map \"[b]\" -start_number 0 \"{1}\"",
                    Path.GetFullPath(mp4), Path.Combine(Path.GetFullPath(framesDir), "f_%04d.png"));
            }
            else outs = string.Format("-vf vflip -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart \"{0}\"", Path.GetFullPath(mp4));
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
                        double t = i / (double)fps;
                        SetTau(pl, clock, warp.TauAt(t), (float)t);
                        beforeRender?.Invoke();
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

        // colour = true：sRGB の RT に MSAA 8x、背景は空上。false：線形の RT、MSAA なし、背景は ID の空（白）。（美術優先28・30 の Capture と同じ）
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
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return path;
        }

        // 美術優先30・32 の CheckShaders と同じ方法（ShaderData.Pass.CompileVariant。STEREO_INSTANCING_ON の頂点関数の出力に SV_RenderTargetArrayIndex があるか）
        static SpiReport CheckShaders(string[] paths)
        {
            var sets = new[] { new string[0], new[] { "INSTANCING_ON" }, new[] { "STEREO_INSTANCING_ON", "INSTANCING_ON" } };
            var checks = new List<PassCheck>();
            foreach (var path in paths)
            {
                var sh = AssetDatabase.LoadAssetAtPath<Shader>(path);
                var data = ShaderUtil.GetShaderData(sh);
                for (int s = 0; s < data.SubshaderCount; s++)
                {
                    var sub = data.GetSubshader(s);
                    for (int p = 0; p < sub.PassCount; p++)
                    {
                        var pass = sub.GetPass(p);
                        foreach (var kw in sets)
                            foreach (var st in new[] { ShaderType.Vertex, ShaderType.Fragment })
                            {
                                var c = new PassCheck { shader = sh.name, pass = pass.Name, keywords = string.Join(" ", kw), stage = st.ToString() };
                                if (!pass.HasShaderStage(st)) continue;
                                var info = pass.CompileVariant(st, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64);
                                c.compiled = info.Success;
                                c.messages = string.Join(" | ", info.Messages.Select(m => m.severity + ": " + m.message));
                                if (st == ShaderType.Vertex && kw.Contains("STEREO_INSTANCING_ON"))
                                {
                                    var pre = pass.PreprocessVariant(st, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64, true);
                                    var code = pre.Success ? (pre.PreprocessedCode ?? "") : "";
                                    var vm = Regex.Match(code, @"#pragma\s+vertex\s+(\w+)");
                                    if (!vm.Success) vm = Regex.Match(pass.SourceCode ?? "", @"#pragma\s+vertex\s+(\w+)");
                                    var vf = vm.Success ? vm.Groups[1].Value : "";
                                    var fm = vf.Length > 0 ? Regex.Match(code, @"(\w+)\s+" + Regex.Escape(vf) + @"\s*\(") : Match.Empty;
                                    var so = fm.Success ? fm.Groups[1].Value : "";
                                    var sm = so.Length > 0 ? Regex.Match(code, @"struct\s+" + Regex.Escape(so) + @"\s*\{([^}]*)\}") : Match.Empty;
                                    c.stereoCheck = true;
                                    c.rtArrayIndexInOutput = sm.Success && sm.Groups[1].Value.Contains("SV_RenderTargetArrayIndex");
                                }
                                checks.Add(c);
                            }
                    }
                }
            }
            var stereo = checks.Where(c => c.stereoCheck).ToList();
            return new SpiReport
            {
                passes = checks.ToArray(), allCompiled = checks.Count > 0 && checks.All(c => c.compiled),
                allStereoOutput = stereo.Count > 0 && stereo.All(c => c.rtArrayIndexInOutput),
                noteJa = "美術優先30・32 と同じ方法：ShaderData.Pass.CompileVariant（D3D、StandaloneWindows64）でキーワードなし・INSTANCING_ON・STEREO_INSTANCING_ON INSTANCING_ON をコンパイルし、STEREO_INSTANCING_ON の頂点関数の戻り値の構造体に SV_RenderTargetArrayIndex があるかを見た。コンパイルだけで、両眼の描画は確かめていない。"
            };
        }

        static Camera MakeCamera(GameObject parent, string name, Vector3 position, Vector3 target, float fov)
        {
            var go = new GameObject("DS27 " + name);
            go.transform.SetParent(parent.transform, false);
            var cam = go.AddComponent<Camera>();
            cam.enabled = false;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = SkyTop;
            cam.fieldOfView = fov; cam.nearClipPlane = .1f; cam.farClipPlane = 900; cam.aspect = (float)W / H;
            cam.allowHDR = false; cam.allowMSAA = true;
            go.transform.position = position;
            go.transform.LookAt(target, Vector3.up);
            return cam;
        }

        static Camera FindCamera(string name)
        {
            var root = GameObject.Find(CamRoot);
            var t = root == null ? null : root.transform.Find("DS27 " + name);
            if (t == null) throw new InvalidOperationException("カメラがありません: " + name);
            return t.GetComponent<Camera>();
        }

        static GameObject FindRoot(string name)
        {
            var go = EditorSceneManager.GetActiveScene().GetRootGameObjects().FirstOrDefault(g => g.name == name);
            if (go == null) throw new InvalidOperationException("見つかりません: " + name);
            return go;
        }

        static string TriSha(Mesh mesh)
        {
            var tris = mesh.triangles;
            var b = new byte[tris.Length * 4];
            Buffer.BlockCopy(tris, 0, b, 0, b.Length);
            using (var s = System.Security.Cryptography.SHA256.Create())
                return BitConverter.ToString(s.ComputeHash(b)).Replace("-", "").ToLowerInvariant();
        }

        static SeatFile LoadSeat()
        {
            var s = JsonUtility.FromJson<SeatFile>(File.ReadAllText(SeatJson));
            if (s == null || s.seat == null || s.view == null || s.seat.eye_world == null || s.seat.eye_world.Length != 3 || s.view.target_world == null)
                throw new InvalidOperationException("seat_v1.json を読めません。");
            if (s.version != "seat_v1") throw new InvalidOperationException("seat_v1.json の版が違います: " + s.version);
            return s;
        }

        static string Sha(string path)
        {
            using (var s = System.Security.Cryptography.SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        static Vector3 V(float[] a) => new Vector3(a[0], a[1], a[2]);

        [Serializable] class SeatJ { public float[] eye_world; }
        [Serializable] class ViewJ { public float[] target_world, qa_hemisphere_look_world; public float vertical_fov_deg; }
        [Serializable] class SeatFile { public string version; public SeatJ seat; public ViewJ view; }
        [Serializable] class CamRec { public string name; public Vector3 position, forward; public float fov; }
        [Serializable] class VideoRec { public string view, path, ffmpegError, sha256, framesDir; public int frames, fps, pngFrames; public float seconds; public bool sideTracksFrame, contextHidden; }
        [Serializable] class CaptureRec { public double tau; public string file; public int[] slices; public float[] weights; public float[] origin; }
        [Serializable] class CaptureReport { public string layout_ja; public CaptureRec[] captures; public float seconds; }
        [Serializable] class FrameTable { public int fps; public float[] t, tau; }
        [Serializable] class PassCheck { public string shader, pass, keywords, stage, messages; public bool compiled, stereoCheck, rtArrayIndexInOutput; }
        [Serializable] class SpiReport { public PassCheck[] passes; public bool allCompiled, allStereoOutput; public string noteJa; }
        [Serializable] class BuildReport
        {
            public string unity, utc, scene, sceneSha256, nprMat, nprMatSha256, outlineMat, outlineMatSha256;
            public Vector3 seatEye, seatTarget; public float seatFov;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
        }
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, renderMethod, version, warp, package, packageJsonSha256, posSha256, twhiteSha256, warpFile, warpFileSha256, outDir, indexSha256, sceneSha256, stillSource, computeMessages;
            public int graphicsMemoryMB, layers, vertexCount, whiteNeverCount, preWhiteIndex, captureCount, clampedKnotCalls, clampedFrameCalls;
            public long positionGpuBytes, whiteGpuBytes, texture2DArrayRgba64EquivalentBytes, graphicsDriverBytesBefore, graphicsDriverBytesAfter, alphaNot65535;
            public float warpRateHzMin, warpTauMin, warpTauMax, frameTauMin, frameTauMax, frameRateHzMin, loadSeconds, whiteFiniteMin, whiteFiniteMax, captureSeconds, totalSeconds;
            public float[] knotTau, stillTau; public string[] stillNames;
            public bool warpInsideKnots, warpInsideFrame, meshUnchanged, protectedUnchanged, passed;
            public Vector3 worldBoundsMin, worldBoundsMax;
            public List<VideoRec> videos = new List<VideoRec>();
            public SpiReport spi; public CamRec[] cameras; public string[] files, filesSha256, changedFiles;
        }
    }
}
