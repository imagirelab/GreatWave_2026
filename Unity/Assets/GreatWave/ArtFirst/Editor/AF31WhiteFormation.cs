using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Rendering;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.ArtFirst.EditorTools
{
    // 番号31「白の出現と縞の追従」の Unity 側。番号30 の AF30Formation と同じ組み立て・採取の手順で、主役波のシェーダーだけを
    // AF31 NPR White（白の時間場 T_white）に替える。番号30 のファイル（シェーダー・スクリプト・マテリアル・シーン・Editor）は読むだけで変えない。
    // 1) Build：空のシーンに番号27修正01 のプレハブを完全に展開し、GWClock と、形成の keypose（番号30）で動く主役波を置く。
    //    主役波 = K*（26修正01）＋ 焼き込み r01（28修正01、UV3）＋ AF30KeyposeWave（番号30）＋ AF31WhiteField（T_white）。
    //    マテリアル AF31_NPR_White.mat は番号28 の AF28_NPR.mat の色を写し、白の前の色区は af31_twhite.json の値にする。
    //    外殻線は番号30 の AF30 Outline Keypose シェーダーを使う自分のマテリアル AF31_Outline_Keypose.mat（値は AF28_Outline.mat から写す）。
    // 2) Render：
    //    a. t* = 12.0 s：番号28修正01 と同じ名前・同じ設定の採取（Build/ArtFirst/31/t28/render）。終点の境界を同じ評価の手順で測る。
    //    b. 静止画：主な時刻の原画視点・座席（場面全体と主役波だけ）・左の側面。比べるために白の時間場を切った画像（番号30 と同じ色）も。
    //    c. ID の連続：0〜17 s（形成の区間は 0.25 s ごと）に、原画視点と座席で、表示の色区 ID・終態の色区 ID・UV3 のテクセル番号を主役波だけで描く。
    //    d. 白の到着時刻の図（t*）。e. 動画（60 fps、0〜17 s）：白の時間場あり 4 本、比べる用の白の時間場なし 2 本。
    //    f. AF31 NPR White の SPI のキーワードでのコンパイル（番号30・32 と同じ方法）。
    //    PC のオフスクリーン描画で、HMD 実機ではない。
    public static class AF31WhiteFormation
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF31_White.unity";
        const string OutRoot = "Build/ArtFirst/31";
        const string ContextPrefab = "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab";
        const string Npr28Mat = "Assets/GreatWave/ArtFirst/Materials/AF28_NPR.mat";
        const string Outline28Mat = "Assets/GreatWave/ArtFirst/Materials/AF28_Outline.mat";
        const string NprMatPath = "Assets/GreatWave/ArtFirst/Materials/AF31_NPR_White.mat";
        const string OutlineMatPath = "Assets/GreatWave/ArtFirst/Materials/AF31_Outline_Keypose.mat";
        const string NprShaderPath = "Assets/GreatWave/ArtFirst/Shaders/AF31_NPR_White.shader";
        const string OutlineShaderPath = "Assets/GreatWave/ArtFirst/Shaders/AF30_Outline_Keypose.shader";
        const string SeatJson = "../Tools/GWContext/seat_v1.json";
        const string KStarGwb = "Build/ArtFirst/26修正01/kstar/kstar_a45.gwb";
        const string Bake28 = "Build/ArtFirst/28修正01/bake/af28r01_uvsdf_a45.bin";
        const string Warp28 = "Build/ArtFirst/28修正01/bake/af28r01_uvwarp_a45.json";
        const string KeyposeDir = "Build/ArtFirst/30/keypose";
        const string WhiteMeta = "Build/ArtFirst/31/white/af31_twhite.json";
        const string RootName = "AF31 背景（番号27修正01 のプレハブ）";
        const string WaveName = "AF31 主役波（K* の格子、keypose で形成、NPR は 28修正01 の焼き込み＋白の時間場）";
        const string ClockName = "AF31 GWClock";
        const string CamRoot = "AF31 カメラ";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080;
        const float TStar = 12f, TEnd = 17f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);
        static readonly Vector3 PaintingPosition = new Vector3(0, 3, -62), PaintingTarget = new Vector3(-2.5f, 9.7f, 4);
        static readonly Vector3 SidePosition = new Vector3(-90, 30, -14), SideTarget = new Vector3(-5, 8, -3);
        static readonly Vector3 BackPosition = new Vector3(-45, 30, 60), BackTarget = new Vector3(-5, 8, -3);
        const float SideFov = 45, BackFov = 50;
        const float SeatFormPitchDeg = 30f;   // 番号30 と同じ：唇の方位、仰角 30°
        static readonly float[] StillTimes = { 0f, 2f, 3f, 4f, 5f, 6f, 7f, 8f, 9f, 9.5f, 10f, 10.5f, 11f, 11.5f, 12f, 17f };

        static float[] IdTimes()
        {
            var l = new List<float> { 0f, 1f, 1.75f };
            for (int i = 0; i <= 40; i++) l.Add(2f + 0.25f * i);
            l.AddRange(new[] { 13f, 15f, 17f });
            return l.ToArray();
        }

        static string[] ProtectedFiles => new[] {
            ContextPrefab, Npr28Mat, Outline28Mat, "Assets/GreatWave/ArtFirst/Materials/AF28_SeaFlat.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_SkyDome.mat",
            "Assets/GreatWave/ArtFirst/Meshes/AF27R01_RightSlope.asset",
            "Assets/GreatWave/ArtFirst/Shaders/AF28_NPR.shader", "Assets/GreatWave/ArtFirst/Shaders/AF28_Outline.shader", "Assets/GreatWave/Shaders/Sampling19/Sampling19Surface.cginc",
            "Assets/GreatWave/ArtFirst/Shaders/AF30_NPR_Keypose.shader", OutlineShaderPath, "Assets/GreatWave/ArtFirst/Shaders/AF30Keypose.cginc",
            "Assets/GreatWave/ArtFirst/Shaders/AF30KeyposeCore.cginc", "Assets/GreatWave/ArtFirst/Shaders/AF30KeyposeCapture.compute",
            "Assets/GreatWave/ArtFirst/Materials/AF30_NPR_Keypose.mat", "Assets/GreatWave/ArtFirst/Materials/AF30_Outline_Keypose.mat",
            "Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs", "Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs", "Assets/GreatWave/ArtFirst/Scripts/AF24WavePlayer.cs",
            "Assets/GreatWave/ArtFirst/Scripts/AF30KeyposeWave.cs", "Assets/GreatWave/ArtFirst/Scripts/GWClock.cs",
            "Assets/GreatWave/ArtFirst/Editor/AF28R01NprScene.cs", "Assets/GreatWave/ArtFirst/Editor/AF26R01KStar.cs", "Assets/GreatWave/ArtFirst/Editor/AF27R01Seat.cs",
            "Assets/GreatWave/ArtFirst/Editor/AFCP1Composite.cs", "Assets/GreatWave/ArtFirst/Editor/AF32PerfBuild.cs", "Assets/GreatWave/ArtFirst/Editor/AF30Formation.cs",
            "Assets/GreatWave/Scenes/Tests/AF28R01_NPR.unity", "Assets/GreatWave/Scenes/Tests/AF26R01_KStar.unity", "Assets/GreatWave/Scenes/Tests/AF27R01_Seat.unity",
            "Assets/GreatWave/Scenes/Tests/AF_CP1.unity", "Assets/GreatWave/Scenes/Tests/AF30_Formation.unity",
            SeatJson, KStarGwb, Bake28, Warp28, KeyposeDir + "/af30_keypose.json", KeyposeDir + "/af30_pos_rgba16.bin", KeyposeDir + "/af30_nrm_rg16.bin" };

        public static void BuildAndRender() { Build(); Render(); }

        // 下見：組み立てのあと、原画視点と座席（主役波だけ）の静止画を数枚だけ描く（白の時間場の見え方を先に確かめる）
        public static void BuildAndPreview()
        {
            Build();
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var wave = FindRoot(WaveName);
            var ctx = FindRoot(RootName);
            var nw = wave.GetComponent<AF28NprWave>();
            var kw = wave.GetComponent<AF30KeyposeWave>();
            var wf = wave.GetComponent<AF31WhiteField>();
            var clock = FindRoot(ClockName).GetComponent<GWClock>();
            nw.EnsureLoaded(); kw.EnsureLoaded(); wf.EnsureLoaded();
            string dp = OutRoot + "/preview_unity";
            Directory.CreateDirectory(dp);
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat(AF31WhiteField.DebugId, 0);
            foreach (var t in new[] { 3f, 5f, 7f, 8f, 9f, 10f, 11f, 11.5f, 12f })
            {
                SetTime(clock, kw, wf, t);
                Capture(FindCamera("painting"), W, H, true, string.Format("{0}/af31_painting_t{1:00.00}.png", dp, t));
                var hid = HideContext(ctx);
                try { Capture(FindCamera("seat_form"), W, H, true, string.Format("{0}/af31_seat_form_waveonly_t{1:00.00}.png", dp, t)); }
                finally { foreach (var rr in hid) rr.enabled = true; }
            }
            SetTime(clock, kw, wf, TStar);
            UnityEngine.Debug.Log("AF31_PREVIEW_DONE");
        }

        // ------------------------------------------------------------------ マテリアル
        static void EnsureMaterials(int preWhite, out Material npr, out Material outline)
        {
            var src = AssetDatabase.LoadAssetAtPath<Material>(Npr28Mat);
            var srcL = AssetDatabase.LoadAssetAtPath<Material>(Outline28Mat);
            var sh = AssetDatabase.LoadAssetAtPath<Shader>(NprShaderPath);
            var shL = AssetDatabase.LoadAssetAtPath<Shader>(OutlineShaderPath);
            if (src == null || srcL == null || sh == null || shL == null) throw new InvalidOperationException("番号28 のマテリアルか AF31／AF30 のシェーダーがありません。");
            if (ShaderUtil.ShaderHasError(sh) || ShaderUtil.ShaderHasError(shL))
                throw new InvalidOperationException("シェーダーにエラーがあります: " + string.Join(" | ", ShaderUtil.GetShaderMessages(sh).Concat(ShaderUtil.GetShaderMessages(shL)).Select(m => m.message)));
            npr = AssetDatabase.LoadAssetAtPath<Material>(NprMatPath);
            if (npr == null) { npr = new Material(sh); AssetDatabase.CreateAsset(npr, NprMatPath); }
            npr.shader = sh;
            foreach (var p in new[] { "_White", "_Mizuiro", "_AiMid", "_AiDark" }) npr.SetColor(p, src.GetColor(p));
            foreach (var p in new[] { "_EncodeLevels", "_AAScale", "_FlatClass" }) npr.SetFloat(p, src.GetFloat(p));
            npr.SetFloat("_PreWhiteClass", preWhite);
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
            var wm = JsonUtility.FromJson<AF31WhiteField.Meta>(File.ReadAllText(WhiteMeta));
            if (wm == null || wm.pre_white_index < 1 || wm.pre_white_index > 3) throw new InvalidOperationException("af31_twhite.json の白の前の色区が読めません。");
            EnsureMaterials(wm.pre_white_index, out var npr, out var outline);
            var seat = LoadSeat();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat; RenderSettings.ambientLight = Color.white; RenderSettings.fog = false; RenderSettings.skybox = null;
            var ctx = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(ContextPrefab));
            PrefabUtility.UnpackPrefabInstance(ctx, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            ctx.name = RootName;

            var clockGo = new GameObject(ClockName);
            var clock = clockGo.AddComponent<GWClock>();
            clock.seconds = TStar; clock.loopSeconds = TEnd; clock.tStarSeconds = TStar;

            var wave = new GameObject(WaveName);
            wave.AddComponent<MeshFilter>();
            var r = wave.AddComponent<MeshRenderer>();
            r.sharedMaterial = npr;
            r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
            r.lightProbeUsage = LightProbeUsage.Off; r.reflectionProbeUsage = ReflectionProbeUsage.Off;
            wave.AddComponent<AF26KStarMesh>().dataPath = KStarGwb;
            var line = new GameObject("AF31 外殻線 v0（keypose、番号30 のシェーダー）");
            line.transform.SetParent(wave.transform, false);
            line.AddComponent<MeshFilter>();
            var lr = line.AddComponent<MeshRenderer>();
            lr.sharedMaterial = outline;
            lr.shadowCastingMode = ShadowCastingMode.Off; lr.receiveShadows = false;
            lr.lightProbeUsage = LightProbeUsage.Off; lr.reflectionProbeUsage = ReflectionProbeUsage.Off;
            var nw = wave.AddComponent<AF28NprWave>();
            nw.sdfPath = Bake28; nw.warpPath = Warp28; nw.size = 4096; nw.outline = lr;
            var kw = wave.AddComponent<AF30KeyposeWave>();
            kw.keyposeDir = KeyposeDir; kw.clock = clock;
            var wf = wave.AddComponent<AF31WhiteField>();
            wf.metaPath = WhiteMeta; wf.clock = clock; wf.whiteEnabled = true;

            var cams = new GameObject(CamRoot);
            var eye = V(seat.seat.eye_world);
            var tgt = V(seat.view.target_world);
            MakeCamera(cams, "painting", PaintingPosition, PaintingTarget, 26);
            MakeCamera(cams, "seat", eye, tgt, seat.view.vertical_fov_deg);
            MakeCamera(cams, "seat_low", eye, V(seat.view.qa_hemisphere_look_world), seat.view.vertical_fov_deg);
            MakeCamera(cams, "seat_form", eye, SeatFormTarget(eye, tgt), seat.view.vertical_fov_deg);
            MakeCamera(cams, "side_left", SidePosition, SideTarget, SideFov);
            MakeCamera(cams, "back", BackPosition, BackTarget, BackFov);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("シーンを保存できません。");
            AssetDatabase.SaveAssets();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(OutRoot);
            var rep = new BuildReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePath, sceneSha256 = Sha(ScenePath),
                nprMat = NprMatPath, nprMatSha256 = Sha(NprMatPath), outlineMat = OutlineMatPath, outlineMatSha256 = Sha(OutlineMatPath),
                preWhiteClass = wm.pre_white_index, whiteSha256 = wm.sha256,
                seatEye = eye, seatTarget = tgt, seatFormTarget = SeatFormTarget(eye, tgt), seatFov = seat.view.vertical_fov_deg,
                protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]),
                protectedFiles = ProtectedFiles.Select(p => p + " " + after[p]).ToArray(), changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray()
            };
            File.WriteAllText(OutRoot + "/af31_build_report.json", JsonUtility.ToJson(rep, true));
            if (!rep.protectedUnchanged) throw new InvalidOperationException("保護したファイルが変わりました: " + string.Join(", ", rep.changedFiles));
            UnityEngine.Debug.Log("AF31_BUILD_DONE");
        }

        static Vector3 SeatFormTarget(Vector3 eye, Vector3 tgt)
        {
            var f = tgt - eye;
            float yaw = Mathf.Atan2(f.x, f.z), p = SeatFormPitchDeg * Mathf.Deg2Rad;
            return eye + 10f * new Vector3(Mathf.Sin(yaw) * Mathf.Cos(p), Mathf.Sin(p), Mathf.Cos(yaw) * Mathf.Cos(p));
        }

        // ------------------------------------------------------------------ 描画
        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var wave = FindRoot(WaveName);
            var ctx = FindRoot(RootName);
            var nw = wave.GetComponent<AF28NprWave>();
            var kw = wave.GetComponent<AF30KeyposeWave>();
            var wf = wave.GetComponent<AF31WhiteField>();
            var clock = FindRoot(ClockName).GetComponent<GWClock>();
            var mesh = nw.EnsureLoaded();
            kw.EnsureLoaded();
            wf.EnsureLoaded();
            var names = new[] { "painting", "seat", "seat_low", "seat_form", "side_left", "back" };
            var cams = names.ToDictionary(n => n, FindCamera);
            var rep = new RenderReport { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), colorSpace = QualitySettings.activeColorSpace.ToString() };
            rep.renderMethod = "Editor batchmode：GWClock.SetSeconds → AF30KeyposeWave.ApplyTime・AF31WhiteField.ApplyTime（大域の値）→ Camera.Render → RenderTexture → ReadPixels。色は sRGB の RT（MSAA 8x → 解決）、ID は線形の RT（MSAA なし、主役波だけ）。PC のオフスクリーン描画で、HMD 実機ではない。";
            rep.vertexCount = mesh.vertexCount;
            rep.indexSha256 = TriSha(mesh);
            rep.indexMatchesKeypose = rep.indexSha256 == kw.KeyMeta.index_sha256;
            rep.whiteSha256 = wf.FieldMeta.sha256;
            rep.whiteStart = wf.FieldMeta.t_start_s; rep.whiteEnd = wf.FieldMeta.t_end_s;
            var files = new List<string>();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat(AF31WhiteField.DebugId, 0);
            try
            {
                // a. t*（番号28修正01 と同じ採取。ファイル名も同じ）
                SetTime(clock, kw, wf, TStar);
                string d28 = OutRoot + "/t28/render";
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

                // d. 白の到着時刻の図（t*、主役波だけ、線なし）
                nw.outline.enabled = false;
                string da = OutRoot + "/arrival";
                Directory.CreateDirectory(da);
                Shader.SetGlobalFloat(AF31WhiteField.DebugId, 4);
                foreach (var v in new[] { "painting", "seat_form", "side_left", "back" }) files.Add(Capture(cams[v], W, H, true, da + "/af31_arrival_" + v + ".png"));
                Shader.SetGlobalFloat(AF31WhiteField.DebugId, 0);

                // c. ID の連続（主役波だけ、線なし）
                string di = OutRoot + "/ids";
                Directory.CreateDirectory(di);
                foreach (var t in IdTimes())
                {
                    SetTime(clock, kw, wf, t);
                    foreach (var v in new[] { "painting", "seat_form" })
                    {
                        Shader.SetGlobalFloat("_AF28IdMode", 1);
                        files.Add(Capture(cams[v], W, H, false, string.Format("{0}/af31_{1}_shown_t{2:00.00}.png", di, v, t)));
                        Shader.SetGlobalFloat("_AF28IdMode", 0);
                        Shader.SetGlobalFloat(AF31WhiteField.DebugId, 2);
                        files.Add(Capture(cams[v], W, H, false, string.Format("{0}/af31_{1}_final_t{2:00.00}.png", di, v, t)));
                        Shader.SetGlobalFloat(AF31WhiteField.DebugId, 3);
                        files.Add(Capture(cams[v], W, H, false, string.Format("{0}/af31_{1}_uv_t{2:00.00}.png", di, v, t)));
                        Shader.SetGlobalFloat(AF31WhiteField.DebugId, 0);
                    }
                }
                ctx.SetActive(true);
                nw.outline.enabled = true;

                // b. 静止画（白の時間場あり／なし）
                string ds = OutRoot + "/stills";
                Directory.CreateDirectory(ds);
                foreach (var on in new[] { true, false })
                {
                    wf.whiteEnabled = on;
                    string tag = on ? "" : "_off";
                    foreach (var t in StillTimes)
                    {
                        SetTime(clock, kw, wf, t);
                        foreach (var v in on ? new[] { "painting", "seat_form" } : new[] { "painting" })
                            files.Add(Capture(cams[v], W, H, true, string.Format("{0}/af31_{1}{2}_t{3:00.00}.png", ds, v, tag, t)));
                        var hid = HideContext(ctx);
                        try
                        {
                            files.Add(Capture(cams["seat_form"], W, H, true, string.Format("{0}/af31_seat_form_waveonly{1}_t{2:00.00}.png", ds, tag, t)));
                            if (on) files.Add(Capture(cams["side_left"], W, H, true, string.Format("{0}/af31_side_left_waveonly_t{1:00.00}.png", ds, t)));
                        }
                        finally { foreach (var rr in hid) rr.enabled = true; }
                    }
                }
                wf.whiteEnabled = true;

                // e. 形成の動画（60 fps、0〜17 s）
                string dv = OutRoot + "/video";
                Directory.CreateDirectory(dv);
                foreach (var v in new[] { "painting", "seat_form", "seat_form_waveonly", "side_left_waveonly", "painting_off", "seat_form_waveonly_off" })
                {
                    var sw = Stopwatch.StartNew();
                    var mp4 = dv + "/af31_formation_" + v + "_60fps.mp4";
                    bool off = v.EndsWith("_off");
                    string view = off ? v.Substring(0, v.Length - 4) : v;
                    bool waveOnly = view.EndsWith("_waveonly");
                    string cam = waveOnly ? view.Replace("_waveonly", "") : view;
                    wf.whiteEnabled = !off;
                    var hidden = waveOnly ? HideContext(ctx) : new List<Renderer>();
                    int n;
                    string err;
                    try { n = EncodeVideo(cams[cam], clock, kw, wf, 60, TEnd, mp4, out err); }
                    finally { foreach (var rr in hidden) rr.enabled = true; wf.whiteEnabled = true; }
                    rep.videos.Add(new VideoRec { view = v, path = Path.GetFullPath(mp4), frames = n, fps = 60, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = File.Exists(mp4) ? Sha(mp4) : "" });
                    if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat(AF31WhiteField.DebugId, 0);
                wf.whiteEnabled = true;
                ctx.SetActive(true);
                nw.outline.enabled = true;
                SetTime(clock, kw, wf, TStar);
            }
            // f. SPI のコンパイル
            rep.spi = CheckShaders(new[] { NprShaderPath });
            rep.meshUnchanged = mesh.vertexCount == 96000 && TriSha(mesh) == rep.indexSha256;
            rep.cameras = names.Select(n => { var c = cams[n]; return new CamRec { name = n, position = c.transform.position, forward = c.transform.forward, fov = c.fieldOfView }; }).ToArray();
            rep.idTimes = IdTimes();
            rep.stillTimes = StillTimes;
            rep.files = files.ToArray();
            rep.filesSha256 = files.Select(Sha).ToArray();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]);
            rep.protectedFiles = ProtectedFiles.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray();
            rep.sceneSha256 = Sha(ScenePath);
            rep.nprMatSha256 = Sha(NprMatPath);
            rep.outlineMatSha256 = Sha(OutlineMatPath);
            rep.totalSeconds = (float)total.Elapsed.TotalSeconds;
            rep.passed = rep.protectedUnchanged && rep.indexMatchesKeypose && rep.meshUnchanged && rep.spi.allCompiled && rep.spi.allStereoOutput;
            File.WriteAllText(OutRoot + "/af31_render_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("AF31_RENDER_DONE files=" + files.Count + " seconds=" + rep.totalSeconds + " passed=" + rep.passed);
            if (!rep.passed) throw new InvalidOperationException("描画の検査が不合格です（af31_render_report.json）。");
        }

        // 確認用：主役波・空のドーム・参照海面だけ（船・富士・仮置き・右船の水面を描画の間だけ隠す。番号30 と同じ）
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

        static void SetTime(GWClock clock, AF30KeyposeWave kw, AF31WhiteField wf, float t)
        {
            clock.SetSeconds(t);
            kw.ApplyTime(clock.Seconds);
            wf.ApplyTime(clock.Seconds);
        }

        static int EncodeVideo(Camera camera, GWClock clock, AF30KeyposeWave kw, AF31WhiteField wf, int fps, float seconds, string mp4, out string err)
        {
            int n = Mathf.RoundToInt(seconds * fps) + 1;
            var psi = new ProcessStartInfo
            {
                FileName = Ffmpeg,
                Arguments = string.Format("-y -loglevel error -f rawvideo -pix_fmt rgb24 -s {0}x{1} -r {2} -i - -vf vflip -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -movflags +faststart \"{3}\"", W, H, fps, Path.GetFullPath(mp4)),
                UseShellExecute = false, RedirectStandardInput = true, RedirectStandardError = true, CreateNoWindow = true
            };
            var sb = new System.Text.StringBuilder();
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
                        SetTime(clock, kw, wf, i / (float)fps);
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

        // colour = true：sRGB の RT に MSAA 8x、背景は空上。false：線形の RT、MSAA なし、背景は ID の空（白）。（番号28・28修正01・30 の Capture と同じ）
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

        // 番号30・32 の CheckShaders と同じ方法（ShaderData.Pass.CompileVariant。STEREO_INSTANCING_ON の頂点関数の出力に SV_RenderTargetArrayIndex があるか）
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
                noteJa = "番号30・32 と同じ方法：ShaderData.Pass.CompileVariant（D3D、StandaloneWindows64）でキーワードなし・INSTANCING_ON・STEREO_INSTANCING_ON INSTANCING_ON をコンパイルし、STEREO_INSTANCING_ON の頂点関数の戻り値の構造体に SV_RenderTargetArrayIndex があるかを見た。コンパイルだけで、両眼の描画は確かめていない。"
            };
        }

        static Camera MakeCamera(GameObject parent, string name, Vector3 position, Vector3 target, float fov)
        {
            var go = new GameObject("AF31 " + name);
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
            var t = root == null ? null : root.transform.Find("AF31 " + name);
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
        [Serializable] class VideoRec { public string view, path, ffmpegError, sha256; public int frames, fps; public float seconds; }
        [Serializable] class PassCheck { public string shader, pass, keywords, stage, messages; public bool compiled, stereoCheck, rtArrayIndexInOutput; }
        [Serializable] class SpiReport { public PassCheck[] passes; public bool allCompiled, allStereoOutput; public string noteJa; }
        [Serializable] class BuildReport
        {
            public string unity, utc, scene, sceneSha256, nprMat, nprMatSha256, outlineMat, outlineMatSha256, whiteSha256;
            public int preWhiteClass;
            public Vector3 seatEye, seatTarget, seatFormTarget; public float seatFov;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
        }
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, renderMethod, indexSha256, whiteSha256, sceneSha256, nprMatSha256, outlineMatSha256;
            public int vertexCount; public float whiteStart, whiteEnd;
            public bool indexMatchesKeypose, meshUnchanged, protectedUnchanged, passed;
            public List<VideoRec> videos = new List<VideoRec>();
            public SpiReport spi; public CamRec[] cameras; public float[] idTimes, stillTimes;
            public string[] files, filesSha256, protectedFiles, changedFiles; public float totalSeconds;
        }
    }
}
