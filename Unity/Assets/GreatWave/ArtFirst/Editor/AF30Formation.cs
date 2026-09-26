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
    // 番号30「形成の動き K0→K*」の Unity 側。
    // 1) Build：空のシーンに番号27修正01 のプレハブ AF27R01_Context.prefab を完全に展開し、GWClock と、形成の keypose で動く主役波を置く。
    //    主役波 = K*（26修正01）の固定位相のメッシュ（AF26KStarMesh）＋ 番号28修正01 の焼き込み r01（AF28NprWave、UV3）＋
    //    AF30 NPR Keypose / AF30 Outline Keypose（keypose の頂点補間）＋ AF30KeyposeWave（keypose テクスチャ、GWClock の時刻）。
    //    マテリアル AF30_NPR_Keypose.mat・AF30_Outline_Keypose.mat は番号28 のマテリアルの値を写して作る（番号28 のマテリアルは変えない）。
    // 2) Render：
    //    a. t* = 12.0 s：番号28修正01 と同じ採取（同じ名前・同じ設定）で、原画視点・座席の色の画像と色区 ID・線 ID を Build/ArtFirst/30/t28/render へ。
    //    b. 形成の動画：原画視点と座席（唇の方位、仰角 30°）を 60 fps・0〜17 s（1021 コマ）で描き、ffmpeg へ生の RGB を流して MP4 にする。
    //       確認用に、座席と左の側面の「主役波・空・海だけ」（船・富士・仮置きを描画の間だけ隠す）も同じ形で書く。
    //    c. 静止画：主な時刻の原画視点・座席・左の側面・背面。
    //    d. シェーダーの補間の照合：頂点シェーダーと同じ関数（AF30KeyposeCapture.compute）で全頂点の位置を読み戻し、.bin に書く。
    //    e. 自作シェーダー（AF30 の 2 本）の SPI キーワードでのコンパイル（番号32 と同じ方法）。
    //    PC のオフスクリーン描画で、HMD 実機ではない。番号26・27・28・CP1 などのファイルは読むだけで変えない（前後の SHA-256 を記録）。
    public static class AF30Formation
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF30_Formation.unity";
        const string OutRoot = "Build/ArtFirst/30";
        const string ContextPrefab = "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab";
        const string Npr28Mat = "Assets/GreatWave/ArtFirst/Materials/AF28_NPR.mat";
        const string Outline28Mat = "Assets/GreatWave/ArtFirst/Materials/AF28_Outline.mat";
        const string NprMatPath = "Assets/GreatWave/ArtFirst/Materials/AF30_NPR_Keypose.mat";
        const string OutlineMatPath = "Assets/GreatWave/ArtFirst/Materials/AF30_Outline_Keypose.mat";
        const string NprShaderPath = "Assets/GreatWave/ArtFirst/Shaders/AF30_NPR_Keypose.shader";
        const string OutlineShaderPath = "Assets/GreatWave/ArtFirst/Shaders/AF30_Outline_Keypose.shader";
        const string CapturePath = "Assets/GreatWave/ArtFirst/Shaders/AF30KeyposeCapture.compute";
        const string SeatJson = "../Tools/GWContext/seat_v1.json";
        const string KStarGwb = "Build/ArtFirst/26修正01/kstar/kstar_a45.gwb";
        const string Bake28 = "Build/ArtFirst/28修正01/bake/af28r01_uvsdf_a45.bin";
        const string Warp28 = "Build/ArtFirst/28修正01/bake/af28r01_uvwarp_a45.json";
        const string RootName = "AF30 背景（番号27修正01 のプレハブ）";
        const string WaveName = "AF30 主役波（K* の格子、keypose で形成、NPR は 28修正01 の焼き込み）";
        const string ClockName = "AF30 GWClock";
        const string CamRoot = "AF30 カメラ";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080;
        const float TStar = 12f, TEnd = 17f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);
        static readonly Vector3 PaintingPosition = new Vector3(0, 3, -62), PaintingTarget = new Vector3(-2.5f, 9.7f, 4);
        static readonly Vector3 SidePosition = new Vector3(-90, 30, -14), SideTarget = new Vector3(-5, 8, -3);
        static readonly Vector3 BackPosition = new Vector3(-45, 30, 60), BackTarget = new Vector3(-5, 8, -3);
        const float SideFov = 45, BackFov = 50;
        const float SeatFormPitchDeg = 30f;   // 形成を座席から見る向き：唇の方位、仰角 30°（縦画角 80° で −10°〜70° が入る）
        static readonly float[] StillTimes = { 0f, 2f, 4f, 6f, 7f, 8f, 9f, 9.5f, 10f, 10.5f, 11f, 11.5f, 12f, 17f };
        static readonly float[] CaptureTimes = {
            0f, 1f, 2f, 2.5f, 3f, 3.5f, 4f, 4.5f, 5f, 5.5f, 6f, 6.5f, 7f, 7.5f, 8f, 8.5f, 9f, 9.5f, 10f, 10.5f, 11f, 11.5f, 12f,
            6.1f, 7.7333f, 9.0333f, 9.5667f, 10.0333f, 10.3f, 10.8f, 11.0333f, 11.3f, 11.7f, 11.9667f, 14f, 17f };

        static string[] ProtectedFiles => new[] {
            ContextPrefab, Npr28Mat, Outline28Mat, "Assets/GreatWave/ArtFirst/Materials/AF28_SeaFlat.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_SkyDome.mat",
            "Assets/GreatWave/ArtFirst/Meshes/AF27R01_RightSlope.asset",
            "Assets/GreatWave/ArtFirst/Shaders/AF28_NPR.shader", "Assets/GreatWave/ArtFirst/Shaders/AF28_Outline.shader", "Assets/GreatWave/Shaders/Sampling19/Sampling19Surface.cginc",
            "Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs", "Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs", "Assets/GreatWave/ArtFirst/Scripts/AF24WavePlayer.cs",
            "Assets/GreatWave/ArtFirst/Editor/AF28R01NprScene.cs", "Assets/GreatWave/ArtFirst/Editor/AF26R01KStar.cs", "Assets/GreatWave/ArtFirst/Editor/AF27R01Seat.cs",
            "Assets/GreatWave/ArtFirst/Editor/AFCP1Composite.cs", "Assets/GreatWave/ArtFirst/Editor/AF32PerfBuild.cs",
            "Assets/GreatWave/Scenes/Tests/AF28R01_NPR.unity", "Assets/GreatWave/Scenes/Tests/AF26R01_KStar.unity", "Assets/GreatWave/Scenes/Tests/AF27R01_Seat.unity",
            "Assets/GreatWave/Scenes/Tests/AF_CP1.unity", SeatJson, KStarGwb, Bake28, Warp28 };

        public static void BuildAndRender() { Build(); Render(); }

        // ------------------------------------------------------------------ マテリアル
        static void EnsureMaterials(out Material npr, out Material outline)
        {
            var src = AssetDatabase.LoadAssetAtPath<Material>(Npr28Mat);
            var srcL = AssetDatabase.LoadAssetAtPath<Material>(Outline28Mat);
            var sh = AssetDatabase.LoadAssetAtPath<Shader>(NprShaderPath);
            var shL = AssetDatabase.LoadAssetAtPath<Shader>(OutlineShaderPath);
            if (src == null || srcL == null || sh == null || shL == null) throw new InvalidOperationException("番号28 のマテリアルか AF30 のシェーダーがありません。");
            if (ShaderUtil.ShaderHasError(sh) || ShaderUtil.ShaderHasError(shL))
                throw new InvalidOperationException("AF30 のシェーダーにエラーがあります: " + string.Join(" | ", ShaderUtil.GetShaderMessages(sh).Concat(ShaderUtil.GetShaderMessages(shL)).Select(m => m.message)));
            npr = AssetDatabase.LoadAssetAtPath<Material>(NprMatPath);
            if (npr == null) { npr = new Material(sh); AssetDatabase.CreateAsset(npr, NprMatPath); }
            npr.shader = sh;
            foreach (var p in new[] { "_White", "_Mizuiro", "_AiMid", "_AiDark" }) npr.SetColor(p, src.GetColor(p));
            foreach (var p in new[] { "_EncodeLevels", "_AAScale", "_FlatClass" }) npr.SetFloat(p, src.GetFloat(p));
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
            clock.seconds = TStar; clock.loopSeconds = TEnd; clock.tStarSeconds = TStar;

            var wave = new GameObject(WaveName);
            wave.AddComponent<MeshFilter>();
            var r = wave.AddComponent<MeshRenderer>();
            r.sharedMaterial = npr;
            r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
            r.lightProbeUsage = LightProbeUsage.Off; r.reflectionProbeUsage = ReflectionProbeUsage.Off;
            wave.AddComponent<AF26KStarMesh>().dataPath = KStarGwb;
            var line = new GameObject("AF30 外殻線 v0（keypose）");
            line.transform.SetParent(wave.transform, false);
            line.AddComponent<MeshFilter>();
            var lr = line.AddComponent<MeshRenderer>();
            lr.sharedMaterial = outline;
            lr.shadowCastingMode = ShadowCastingMode.Off; lr.receiveShadows = false;
            lr.lightProbeUsage = LightProbeUsage.Off; lr.reflectionProbeUsage = ReflectionProbeUsage.Off;
            var nw = wave.AddComponent<AF28NprWave>();
            nw.sdfPath = Bake28; nw.warpPath = Warp28; nw.size = 4096; nw.outline = lr;
            var kw = wave.AddComponent<AF30KeyposeWave>();
            kw.keyposeDir = OutRoot + "/keypose"; kw.clock = clock;

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
                seatEye = eye, seatTarget = tgt, seatFormTarget = SeatFormTarget(eye, tgt), seatFov = seat.view.vertical_fov_deg,
                protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]),
                protectedFiles = ProtectedFiles.Select(p => p + " " + after[p]).ToArray(), changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray()
            };
            File.WriteAllText(OutRoot + "/af30_build_report.json", JsonUtility.ToJson(rep, true));
            if (!rep.protectedUnchanged) throw new InvalidOperationException("保護したファイルが変わりました: " + string.Join(", ", rep.changedFiles));
            UnityEngine.Debug.Log("AF30_BUILD_DONE");
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
            var clock = FindRoot(ClockName).GetComponent<GWClock>();
            var mesh = nw.EnsureLoaded();
            kw.EnsureLoaded();
            var names = new[] { "painting", "seat", "seat_low", "seat_form", "side_left", "back" };
            var cams = names.ToDictionary(n => n, FindCamera);
            var rep = new RenderReport { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), colorSpace = QualitySettings.activeColorSpace.ToString() };
            rep.renderMethod = "Editor batchmode：GWClock.SetSeconds → AF30KeyposeWave.ApplyTime（大域の値）→ Camera.Render → RenderTexture → ReadPixels。色は sRGB の RT（MSAA 8x → 解決）、ID は線形の RT（MSAA なし）。PC のオフスクリーン描画で、HMD 実機ではない。";
            rep.vertexCount = mesh.vertexCount;
            rep.indexSha256 = TriSha(mesh);
            rep.keyposeIndexSha256 = kw.KeyMeta.index_sha256;
            rep.indexMatchesKeypose = rep.indexSha256 == kw.KeyMeta.index_sha256;
            rep.layers = kw.KeyMeta.layers;
            rep.positionSha256 = Sha(OutRoot + "/keypose/" + kw.KeyMeta.position_file);
            rep.normalSha256 = Sha(OutRoot + "/keypose/" + kw.KeyMeta.normal_file);
            rep.keyposeFilesMatchJson = rep.positionSha256 == kw.KeyMeta.position_sha256 && rep.normalSha256 == kw.KeyMeta.normal_sha256;
            rep.textureMemoryBytes = UnityEngine.Profiling.Profiler.GetRuntimeMemorySizeLong(kw.PositionTexture) + UnityEngine.Profiling.Profiler.GetRuntimeMemorySizeLong(kw.NormalTexture);
            var files = new List<string>();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            try
            {
                // a. t*（番号28修正01 と同じ採取。ファイル名も同じにして、評価の手順をそのまま使う）
                SetTime(clock, kw, TStar);
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
                ctx.SetActive(true);

                // c. 静止画
                string ds = OutRoot + "/stills";
                Directory.CreateDirectory(ds);
                foreach (var t in StillTimes)
                {
                    SetTime(clock, kw, t);
                    foreach (var v in new[] { "painting", "seat_form", "seat", "side_left", "back" })
                        files.Add(Capture(cams[v], W, H, true, string.Format("{0}/af30_{1}_t{2:00.00}.png", ds, v, t)));
                    var hid = new List<Renderer>();
                    foreach (var rr in ctx.GetComponentsInChildren<Renderer>(false))
                    {
                        if (!rr.enabled || rr.name == "AF27 空のドーム" || rr.name == "AF27 参照海面") continue;
                        rr.enabled = false; hid.Add(rr);
                    }
                    try
                    {
                        files.Add(Capture(cams["seat_form"], W, H, true, string.Format("{0}/af30_seat_form_waveonly_t{1:00.00}.png", ds, t)));
                        files.Add(Capture(cams["side_left"], W, H, true, string.Format("{0}/af30_side_left_waveonly_t{1:00.00}.png", ds, t)));
                    }
                    finally { foreach (var rr in hid) rr.enabled = true; }
                }

                // b. 形成の動画（60 fps、0〜17 s）
                string dv = OutRoot + "/video";
                Directory.CreateDirectory(dv);
                foreach (var v in new[] { "painting", "seat_form", "seat_form_waveonly", "side_left_waveonly" })
                {
                    var sw = Stopwatch.StartNew();
                    var mp4 = dv + "/af30_formation_" + v + "_60fps.mp4";
                    bool waveOnly = v.EndsWith("_waveonly");
                    var hidden = new List<Renderer>();
                    // 確認用：主役波・空のドーム・参照海面だけ（船・富士・仮置き・右船の水面を描画の間だけ隠す。番号28修正01 の waveonly と同じ）
                    if (waveOnly)
                        foreach (var rr in ctx.GetComponentsInChildren<Renderer>(false))
                        {
                            if (!rr.enabled || rr.name == "AF27 空のドーム" || rr.name == "AF27 参照海面") continue;
                            rr.enabled = false; hidden.Add(rr);
                        }
                    int n;
                    string err;
                    try { n = EncodeVideo(cams[waveOnly ? v.Replace("_waveonly", "") : v], clock, kw, 60, TEnd, mp4, out err); }
                    finally { foreach (var rr in hidden) rr.enabled = true; }
                    rep.videos.Add(new VideoRec { view = v, path = Path.GetFullPath(mp4), frames = n, fps = 60, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = File.Exists(mp4) ? Sha(mp4) : "" });
                    if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
                }

                // d. シェーダーの補間の照合（頂点シェーダーと同じ関数のコンピュート）
                string dc = OutRoot + "/gpu_capture";
                Directory.CreateDirectory(dc);
                var cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(CapturePath);
                if (cs == null) throw new InvalidOperationException("AF30KeyposeCapture.compute がありません。");
                int k = cs.FindKernel("AF30Capture");
                int nvtx = mesh.vertexCount;
                using (var buf = new ComputeBuffer(nvtx, 16))
                {
                    var outv = new Vector4[nvtx];
                    foreach (var t in CaptureTimes)
                    {
                        SetTime(clock, kw, t);
                        kw.BindCompute(cs, k);
                        cs.SetBuffer(k, "_AF30Out", buf);
                        cs.SetInt("_AF30Count", nvtx);
                        cs.Dispatch(k, (nvtx + 63) / 64, 1, 1);
                        buf.GetData(outv);
                        var bytes = new byte[nvtx * 12];
                        var fl = new float[nvtx * 3];
                        for (int i = 0; i < nvtx; i++) { fl[3 * i] = outv[i].x; fl[3 * i + 1] = outv[i].y; fl[3 * i + 2] = outv[i].z; }
                        Buffer.BlockCopy(fl, 0, bytes, 0, bytes.Length);
                        var p = string.Format("{0}/af30_gpu_t{1:00.0000}.bin", dc, t);
                        File.WriteAllBytes(p, bytes);
                        rep.captures.Add(new CaptureRec { t = t, path = Path.GetFullPath(p), slices = kw.Slices.ToArray(), weights = kw.WeightsNow.ToArray() });
                    }
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                ctx.SetActive(true);
                SetTime(clock, kw, TStar);
            }
            // e. SPI のコンパイル
            rep.spi = CheckShaders(new[] { NprShaderPath, OutlineShaderPath });
            rep.meshUnchanged = mesh.vertexCount == 96000 && TriSha(mesh) == rep.indexSha256;
            var camRecs = names.Select(n => { var c = cams[n]; return new CamRec { name = n, position = c.transform.position, forward = c.transform.forward, fov = c.fieldOfView }; }).ToArray();
            rep.cameras = camRecs;
            rep.files = files.ToArray();
            rep.filesSha256 = files.Select(Sha).ToArray();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]);
            rep.changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray();
            rep.totalSeconds = (float)total.Elapsed.TotalSeconds;
            rep.passed = rep.protectedUnchanged && rep.indexMatchesKeypose && rep.keyposeFilesMatchJson && rep.meshUnchanged && rep.spi.allCompiled && rep.spi.allStereoOutput;
            File.WriteAllText(OutRoot + "/af30_render_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("AF30_RENDER_DONE files=" + files.Count + " seconds=" + rep.totalSeconds + " passed=" + rep.passed);
            if (!rep.passed) throw new InvalidOperationException("描画の検査が不合格です（af30_render_report.json）。");
        }

        static void SetTime(GWClock clock, AF30KeyposeWave kw, float t)
        {
            clock.SetSeconds(t);
            kw.ApplyTime(clock.Seconds);
        }

        static int EncodeVideo(Camera camera, GWClock clock, AF30KeyposeWave kw, int fps, float seconds, string mp4, out string err)
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
                        SetTime(clock, kw, i / (float)fps);
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

        // colour = true：sRGB の RT に MSAA 8x、背景は空上。false：線形の RT、MSAA なし、背景は ID の空（白）。（番号28・28修正01 の Capture と同じ）
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

        // 番号32 の CheckShaders と同じ方法（ShaderData.Pass.CompileVariant。STEREO_INSTANCING_ON の頂点関数の出力に SV_RenderTargetArrayIndex があるか）
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
                noteJa = "番号32 と同じ方法：ShaderData.Pass.CompileVariant（D3D、StandaloneWindows64）でキーワードなし・INSTANCING_ON・STEREO_INSTANCING_ON INSTANCING_ON をコンパイルし、STEREO_INSTANCING_ON の頂点関数の戻り値の構造体に SV_RenderTargetArrayIndex があるかを見た。コンパイルだけで、両眼の描画は確かめていない。"
            };
        }

        static Camera MakeCamera(GameObject parent, string name, Vector3 position, Vector3 target, float fov)
        {
            var go = new GameObject("AF30 " + name);
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
            var t = root == null ? null : root.transform.Find("AF30 " + name);
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
        [Serializable] class CaptureRec { public float t; public string path; public int[] slices; public float[] weights; }
        [Serializable] class PassCheck { public string shader, pass, keywords, stage, messages; public bool compiled, stereoCheck, rtArrayIndexInOutput; }
        [Serializable] class SpiReport { public PassCheck[] passes; public bool allCompiled, allStereoOutput; public string noteJa; }
        [Serializable] class BuildReport
        {
            public string unity, utc, scene, sceneSha256, nprMat, nprMatSha256, outlineMat, outlineMatSha256;
            public Vector3 seatEye, seatTarget, seatFormTarget; public float seatFov;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
        }
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, renderMethod, indexSha256, keyposeIndexSha256, positionSha256, normalSha256;
            public int vertexCount, layers; public long textureMemoryBytes;
            public bool indexMatchesKeypose, keyposeFilesMatchJson, meshUnchanged, protectedUnchanged, passed;
            public List<VideoRec> videos = new List<VideoRec>();
            public List<CaptureRec> captures = new List<CaptureRec>();
            public SpiReport spi; public CamRec[] cameras; public string[] files, filesSha256, changedFiles; public float totalSeconds;
        }
    }
}
