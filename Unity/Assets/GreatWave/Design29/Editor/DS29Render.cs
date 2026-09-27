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

namespace GreatWave.Design29.EditorTools
{
    // 設計29「表示用サーフェス（密度の比較と軽量版）」の Unity 側（描画・GPU の容量・おおよその GPU 時間）。
    // 設計27 の場面 DS27_Formation.unity を開き、設計27 の主役波（DS27KeyposePlayer、240 × 400 に固定）をメモリの上だけで隠して、
    // 同じマテリアル（DS27 NPR White・DS27 Outline Keypose）で表示用サーフェスの主役波（AF26KStarMesh ＋ DS29KeyposePlayer）を足して描く。
    // 場面は保存しない（前後の SHA-256 を記録）。設計27・28 のファイルは変えない。カメラ・採取の設定は DS27Formation・DS28ReviewView の写し。
    //   a. t*（τ = 0）：美術優先28修正01・設計27 と同じ名前・同じ設定の画像（t28/render/af28r01_*.png）。ds27_tstar_eval.py で原画の関門を測り直す。
    //   b. GPU の読み戻し：設計27 の DS27KeyposeCapture.compute（頂点シェーダーと同じ関数）で、t*・段階の τ・節点の間の τ の全頂点の位置と法線。
    //   c. 静止画：段階の τ で、原画視点・座席 v1（背景あり）、左の側面（波の枠とともに動く）・seat_toward_wave（設計28 の確認用の視点。背景を隠す）。
    //   d. 動画：t = 0〜14 s を 30 fps、各コマの τ は時間曲線の表から（連番は書かない）。
    //   e. GPU の容量：位置と T_white のバッファの大きさ（count × stride）、メッシュの頂点・添字のバッファ、グラフィックドライバーの割り当ての前後の差。
    //   f. おおよその GPU 時間：原画視点と座席 v1 を 1920 × 1080・MSAA 8x の RT へ描き、毎コマ 1 画素を読み戻して GPU を待つ壁時計の時間。
    //      主役波を描く場合と隠した場合の差を主役波の分とする。PC のオフスクリーン描画で、HMD 実機ではない。
    // 引数：DS27Formation と同じ -ds27Package・-ds27Out・-ds27Stills・-ds27Views（動画の視点）・-ds27Skip（t28,capture,stills,video,timing）・-ds27WarpFile・-ds27Fps。
    //   足した引数：-ds29Name <名前>、-ds29MeshFromPackage 1|0（0 = 設計28 の K* の格子：メッシュは K* の .gwb、UV3 は 28修正01 の表）、
    //   -ds29StillViews painting,seat,side_left,seat_toward_wave、-ds29TimingFrames 180、-ds29CaptureMax 16。
    // 実行は Tools/GWWaveGen/ds29/run_ds29_unity.ps1（unity.lock の手順、30 分以内）：-Method GreatWave.Design29.EditorTools.DS29Render.Render
    public static class DS29Render
    {
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string KStarGwb = "Build/ArtFirst/26修正01/kstar/kstar_a45.gwb";
        const string Bake28 = "Build/ArtFirst/28修正01/bake/af28r01_uvsdf_a45.bin";
        const string Warp28 = "Build/ArtFirst/28修正01/bake/af28r01_uvwarp_a45.json";
        const string CapturePath = "Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080;
        const float TStar = 12f, TEnd = 14f, StwFov = 70f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);
        const string DefaultStills = "a=-4.433,b=-3.500,c=-2.933,d=-2.250,apex=-1.333,tstar=0";

        static string[] Protected => new[] {
            DS27Formation.ScenePath, "Assets/GreatWave/Design27/Editor/DS27Formation.cs", "Assets/GreatWave/Design27/Scripts/DS27KeyposePlayer.cs",
            "Assets/GreatWave/Design27/Scripts/DS27Json.cs", "Assets/GreatWave/Design27/Scripts/DS27TimeWarp.cs",
            "Assets/GreatWave/Design27/Materials/DS27_NPR_White.mat", "Assets/GreatWave/Design27/Materials/DS27_Outline_Keypose.mat",
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design27/Shaders/DS27_Outline_Keypose.shader",
            "Assets/GreatWave/Design27/Shaders/DS27Keypose.cginc", "Assets/GreatWave/Design27/Shaders/DS27KeyposeCore.cginc", CapturePath,
            "Assets/GreatWave/Design28/Editor/DS28ReviewView.cs", "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab",
            "Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs", "Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs",
            "../Tools/GWContext/seat_v1.json", KStarGwb, Bake28, Warp28 };

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var cfg = DS27Formation.ParseArgs();
            var args = Environment.GetCommandLineArgs();
            string name = Arg(args, "-ds29Name") ?? Path.GetFileName(cfg.package.TrimEnd('/', '\\'));
            bool meshFromPkg = (Arg(args, "-ds29MeshFromPackage") ?? "1") == "1";
            var stillViews = (Arg(args, "-ds29StillViews") ?? "painting,seat,side_left,seat_toward_wave").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            int timingFrames = int.Parse(Arg(args, "-ds29TimingFrames") ?? "180", CultureInfo.InvariantCulture);
            int captureMax = int.Parse(Arg(args, "-ds29CaptureMax") ?? "16", CultureInfo.InvariantCulture);
            var stillNames = new List<string>(); var stillTau = new List<double>();
            if (cfg.stillsFromArgs) { stillNames.AddRange(cfg.stillNames); stillTau.AddRange(cfg.stillTau); }
            else foreach (var kv in DefaultStills.Split(',')) { var p = kv.Split('='); stillNames.Add(p[0]); stillTau.Add(double.Parse(p[1], CultureInfo.InvariantCulture)); }
            var before = Protected.ToDictionary(p => p, Sha);

            EditorSceneManager.OpenScene(DS27Formation.ScenePath, OpenSceneMode.Single);
            var roots = EditorSceneManager.GetActiveScene().GetRootGameObjects();
            var pl27 = roots.Select(g => g.GetComponent<DS27KeyposePlayer>()).First(x => x != null);
            var wave27 = pl27.gameObject;
            var r27 = wave27.GetComponent<MeshRenderer>();
            var line27 = wave27.GetComponentsInChildren<MeshRenderer>(true).First(x => x.gameObject != wave27);
            var clock = roots.Select(g => g.GetComponent<GWClock>()).First(x => x != null);
            var ctx = roots.First(g => g.name == ContextRootName);
            var camRoot = GameObject.Find(CamRoot).transform;
            var cams = new Dictionary<string, Camera>();
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            wave27.SetActive(false);

            // 表示用サーフェスの主役波（メモリの上だけ）
            var wave = new GameObject("DS29 主役波（表示用サーフェス " + name + "。メモリの上だけ、場面は保存しない）");
            wave.transform.SetPositionAndRotation(wave27.transform.position, wave27.transform.rotation);
            wave.transform.localScale = wave27.transform.localScale;
            wave.AddComponent<MeshFilter>();
            var r = wave.AddComponent<MeshRenderer>();
            CopyRenderer(r27, r);
            var km = wave.AddComponent<AF26KStarMesh>();
            km.dataPath = KStarGwb;
            var line = new GameObject("DS29 外殻線 v0");
            line.transform.SetParent(wave.transform, false);
            line.AddComponent<MeshFilter>();
            var lr = line.AddComponent<MeshRenderer>();
            CopyRenderer(line27, lr);
            var pl = wave.AddComponent<DS29KeyposePlayer>();
            pl.packageDir = cfg.package; pl.meshFromPackage = meshFromPkg; pl.outline = lr; pl.clock = clock;
            pl.warpPath = Warp28; pl.sdfPath = Bake28; pl.whiteEnabled = true;

            // e. GPU の容量
            long g0 = UnityEngine.Profiling.Profiler.GetAllocatedMemoryForGraphicsDriver();
            var mesh = pl.LoadSurface();
            long g1 = UnityEngine.Profiling.Profiler.GetAllocatedMemoryForGraphicsDriver();
            pl.LoadKeypose();
            long g2 = UnityEngine.Profiling.Profiler.GetAllocatedMemoryForGraphicsDriver();
            var pm = pl.PackageMeta;
            var warp = DS27TimeWarp.Load(cfg.warpFile);
            long meshVb = 0;
            for (int s = 0; s < mesh.vertexBufferCount; s++) meshVb += (long)mesh.GetVertexBufferStride(s) * mesh.vertexCount;
            long meshIb = (long)mesh.GetIndexCount(0) * (mesh.indexFormat == IndexFormat.UInt32 ? 4 : 2);

            // seat_toward_wave（設計28 の DS28ReviewView と同じ置き方）
            var o0 = pl.OriginAt(pm.knotTau[0]);
            var o1 = pl.OriginAt(0.0);
            var tdir = o1 - o0; tdir.y = 0; tdir.Normalize();
            var stwGo = new GameObject("DS29 seat_toward_wave（メモリの上だけ）");
            var stw = stwGo.AddComponent<Camera>();
            stw.enabled = false;
            stw.clearFlags = CameraClearFlags.SolidColor; stw.backgroundColor = SkyTop;
            stw.fieldOfView = StwFov; stw.nearClipPlane = .1f; stw.farClipPlane = 900; stw.aspect = (float)W / H;
            stw.allowHDR = false; stw.allowMSAA = true;
            stwGo.transform.SetPositionAndRotation(cams["seat"].transform.position, Quaternion.LookRotation(-tdir, Vector3.up));
            cams["seat_toward_wave"] = stw;
            var sidePos0 = cams["side_left"].transform.position;
            var sideRot0 = cams["side_left"].transform.rotation;
            var oStar = pl.OriginAt(0.0);

            string od = cfg.outDir;
            Directory.CreateDirectory(od);
            var files = new List<string>();
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), graphicsMemoryMB = SystemInfo.graphicsMemorySize,
                name = name, package = pm.dir, packageJsonSha256 = pm.jsonSha256, posSha256 = pm.posSha256, twhiteSha256 = pm.twhiteSha256,
                meshFromPackage = meshFromPkg, meshPath = pl.MeshPath, meshSha256 = Sha(pl.MeshPath), uv3Source = pl.Uv3Source, uv3Sha256 = pl.Uv3Sha256,
                rows = pm.rows, cols = pm.cols, layers = pm.layers, vertexCount = mesh.vertexCount, indexCount = (long)mesh.GetIndexCount(0),
                warpFile = warp.Path, warpFileSha256 = Sha(warp.Path),
                positionGpuBytes = pl.PositionGpuBytes, whiteGpuBytes = pl.WhiteGpuBytes, meshVertexBufferBytes = meshVb, meshIndexBufferBytes = meshIb,
                meshVertexStreams = mesh.vertexBufferCount, sdfTextureBytes = 4096L * 4096 * 4,
                driverBytesBeforeSurface = g0, driverBytesAfterSurface = g1, driverBytesAfterKeypose = g2,
                surfaceLoadSeconds = pl.SurfaceLoadSeconds, keyposeLoadSeconds = pl.KeyposeLoadSeconds, alphaNot65535 = pl.AlphaNot65535, whiteNeverCount = pl.WhiteNeverCount,
                worldBoundsMin = pl.WorldBounds.min, worldBoundsMax = pl.WorldBounds.max, travelDirWorld = tdir,
                stillNames = stillNames.ToArray(), stillTau = stillTau.Select(x => (float)x).ToArray(),
                noteJa = "設計27 の場面を開き、設計27 の主役波を隠して、同じマテリアルで表示用サーフェスの主役波（AF26KStarMesh ＋ DS29KeyposePlayer）をメモリの上だけに足して描いた。場面は保存しない。" +
                         "GPU の位置のバッファは設計27 と同じ詰め方（頂点ごとに 16 bit × 3、StructuredBuffer<uint>、GPU だけ）。PC のオフスクリーン描画（Editor の batchmode）で、HMD 実機ではない。"
            };
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 0);
            try
            {
                pl.BindGlobals();
                // a. t*
                if (!cfg.skip.Contains("t28"))
                {
                    SetTau(pl, clock, 0.0, TStar);
                    string d28 = od + "/t28/render";
                    Directory.CreateDirectory(d28);
                    lr.enabled = true;
                    foreach (var v in new[] { "painting", "seat", "seat_low" }) files.Add(Capture(cams[v], W, H, true, d28 + "/af28r01_" + v + ".png"));
                    ctx.SetActive(false);
                    lr.enabled = false;
                    files.Add(Capture(cams["painting"], W, H, true, d28 + "/af28r01_painting_kstar.png"));
                    files.Add(Capture(cams["seat"], W, H, true, d28 + "/af28r01_seat_kstar.png"));
                    files.Add(Capture(cams["seat_low"], W, H, true, d28 + "/af28r01_seat_low_kstar.png"));
                    Shader.SetGlobalFloat("_AF28IdMode", 1);
                    files.Add(Capture(cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_class_ids.png"));
                    files.Add(Capture(cams["seat"], W, H, false, d28 + "/af28r01_seat_class_ids.png"));
                    files.Add(Capture(cams["seat_low"], W, H, false, d28 + "/af28r01_seat_low_class_ids.png"));
                    lr.enabled = true;
                    files.Add(Capture(cams["painting"], 2 * W, 2 * H, false, d28 + "/af28r01_line_ids.png"));
                    Shader.SetGlobalFloat("_AF28IdMode", 0);
                    ctx.SetActive(true);
                }

                // b. GPU の読み戻し
                if (!cfg.skip.Contains("capture"))
                {
                    var sw = Stopwatch.StartNew();
                    string dc = od + "/gpu_capture";
                    Directory.CreateDirectory(dc);
                    foreach (var f in Directory.GetFiles(dc, "ds29_gpu_*.bin")) File.Delete(f);
                    var cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(CapturePath);
                    int k = cs.FindKernel("DS27Capture");
                    int nvtx = mesh.vertexCount;
                    var taus = new List<double> { 0.0, pm.knotTau[0] };
                    taus.AddRange(stillTau);
                    var kt = pm.knotTau;
                    int extra = Math.Max(0, captureMax - taus.Count);
                    for (int j = 0; j < extra; j++)
                    {
                        int i = (int)Math.Round((j + 0.5) * (kt.Length - 1) / (double)extra);
                        i = Math.Min(Math.Max(i, 0), kt.Length - 2);
                        taus.Add(kt[i] + (kt[i + 1] - kt[i]) * (j % 2 == 0 ? 1.0 / 3.0 : 0.5));
                    }
                    taus = taus.Distinct().OrderBy(x => x).ToList();
                    var capList = new List<CaptureRec>();
                    using (var buf = new ComputeBuffer(nvtx * 2, 16))
                    {
                        var outv = new Vector4[nvtx * 2];
                        var fl = new float[nvtx * 6];
                        var bytes = new byte[nvtx * 24];
                        for (int q = 0; q < taus.Count; q++)
                        {
                            SetTau(pl, clock, taus[q], float.NaN);
                            pl.BindCompute(cs, k);
                            cs.SetBuffer(k, "_DS27Out", buf);
                            cs.SetInt("_DS27Count", nvtx);
                            cs.Dispatch(k, (nvtx + 63) / 64, 1, 1);
                            buf.GetData(outv);
                            for (int i = 0; i < nvtx; i++)
                            {
                                var p = outv[2 * i]; var nn = outv[2 * i + 1];
                                fl[6 * i] = p.x; fl[6 * i + 1] = p.y; fl[6 * i + 2] = p.z; fl[6 * i + 3] = nn.x; fl[6 * i + 4] = nn.y; fl[6 * i + 5] = nn.z;
                            }
                            Buffer.BlockCopy(fl, 0, bytes, 0, bytes.Length);
                            var fn = string.Format(CultureInfo.InvariantCulture, "ds29_gpu_{0:000}_tau{1:+0.000000;-0.000000}.bin", q, taus[q]);
                            File.WriteAllBytes(Path.Combine(dc, fn), bytes);
                            capList.Add(new CaptureRec { tau = taus[q], file = fn, slices = pl.Slices.ToArray(), weights = pl.WeightsNow.ToArray(), origin = new[] { pl.AppliedOrigin.x, pl.AppliedOrigin.y, pl.AppliedOrigin.z } });
                        }
                    }
                    var cr = new CaptureReport { layout_ja = "頂点ごとに float32 × 6（ワールドの位置 xyz、法線 xyz）、頂点の添字 = 行 × 列の数 + 列", rows = pm.rows, cols = pm.cols, captures = capList.ToArray(), seconds = (float)sw.Elapsed.TotalSeconds };
                    File.WriteAllText(Path.Combine(dc, "ds29_gpu_capture.json"), JsonUtility.ToJson(cr, true));
                    rep.captureCount = capList.Count;
                }

                // c. 段階の静止画
                if (!cfg.skip.Contains("stills"))
                {
                    string ds = od + "/stills";
                    Directory.CreateDirectory(ds);
                    for (int s = 0; s < stillNames.Count; s++)
                    {
                        SetTau(pl, clock, stillTau[s], float.NaN);
                        foreach (var v in stillViews)
                        {
                            bool hide = v == "side_left" || v == "seat_toward_wave";
                            var hid = hide ? HideContext(ctx) : new List<Renderer>();
                            try
                            {
                                PlaceSide(cams["side_left"], sidePos0, sideRot0, pl.AppliedOrigin - oStar);
                                files.Add(Capture(cams[v], W, H, true, string.Format(CultureInfo.InvariantCulture, "{0}/ds29_{1}_{2}_tau{3:+0.000;-0.000}.png", ds, v, stillNames[s], stillTau[s])));
                            }
                            finally { foreach (var rr in hid) rr.enabled = true; PlaceSide(cams["side_left"], sidePos0, sideRot0, Vector3.zero); }
                        }
                    }
                }

                // d. 動画
                if (!cfg.skip.Contains("video"))
                {
                    string dv = od + "/video";
                    Directory.CreateDirectory(dv);
                    foreach (var v in cfg.views)
                    {
                        var sw = Stopwatch.StartNew();
                        var mp4 = dv + "/ds29_" + v + "_" + cfg.fps + "fps.mp4";
                        bool side = v == "side_left";
                        bool hide = side || v == "seat_toward_wave";
                        var hidden = hide ? HideContext(ctx) : new List<Renderer>();
                        int nf; string err;
                        try { nf = EncodeVideo(cams[v], pl, clock, warp, cfg.fps, TEnd, mp4, side ? (Action)(() => PlaceSide(cams["side_left"], sidePos0, sideRot0, pl.AppliedOrigin - oStar)) : null, out err); }
                        finally { foreach (var rr in hidden) rr.enabled = true; PlaceSide(cams["side_left"], sidePos0, sideRot0, Vector3.zero); }
                        rep.videos.Add(new VideoRec { view = v, path = Path.GetFullPath(mp4), frames = nf, fps = cfg.fps, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = File.Exists(mp4) ? Sha(mp4) : "", contextHidden = hide });
                        if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
                    }
                }

                // f. おおよその GPU 時間
                if (!cfg.skip.Contains("timing"))
                {
                    foreach (var v in new[] { "painting", "seat" })
                    {
                        var tr = new TimingRec { view = v, frames = timingFrames, width = W, height = H, msaa = 8 };
                        var on = new List<double>(); var off = new List<double>();
                        for (int rep3 = 0; rep3 < 3; rep3++)
                        {
                            r.enabled = true; lr.enabled = true;
                            on.Add(TimeFrames(cams[v], pl, clock, warp, timingFrames));
                            r.enabled = false; lr.enabled = false;
                            off.Add(TimeFrames(cams[v], pl, clock, warp, timingFrames));
                        }
                        r.enabled = true; lr.enabled = true;
                        tr.msPerFrameWaveOn = on.Select(x => (float)x).ToArray();
                        tr.msPerFrameWaveOff = off.Select(x => (float)x).ToArray();
                        on.Sort(); off.Sort();
                        tr.medianOnMs = (float)on[1]; tr.medianOffMs = (float)off[1]; tr.waveMs = (float)(on[1] - off[1]);
                        rep.timing.Add(tr);
                    }
                    rep.timingMethodJa = "Editor の batchmode で、カメラを 1920 × 1080・MSAA 8x の RT へ描き（Camera.Render → 解決の Blit → 1 画素の ReadPixels で GPU の終わりを待つ）、" +
                                         timingFrames + " コマ（時間曲線の t = 0〜14 s を等分した τ）の壁時計の平均を 3 回測り、中央値を取った。主役波（面と外殻線）を描く場合と隠した場合の差を主役波の分とした。" +
                                         "CPU の命令の発行と同期の待ちを含むおおよその値で、GPU のタイマーの値ではない。両眼（SPI）では頂点の処理がおよそ 2 倍になる。HMD 実機ではない。";
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 0);
                ctx.SetActive(true);
                PlaceSide(cams["side_left"], sidePos0, sideRot0, Vector3.zero);
                pl.Release();
                UnityEngine.Object.DestroyImmediate(stwGo);
            }
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.sceneDirtyNotSaved = EditorSceneManager.GetActiveScene().isDirty;
            rep.files = files.ToArray();
            rep.filesSha256 = files.Select(Sha).ToArray();
            rep.totalSeconds = (float)total.Elapsed.TotalSeconds;
            rep.passed = rep.protectedUnchanged && rep.vertexCount == pm.rows * pm.cols && rep.alphaNot65535 == 0;
            File.WriteAllText(od + "/ds29_render_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("DS29_RENDER_DONE name=" + name + " files=" + files.Count + " seconds=" + rep.totalSeconds + " passed=" + rep.passed);
            if (!rep.passed) throw new InvalidOperationException("描画の検査が不合格です（ds29_render_report.json）。");
        }

        static void CopyRenderer(MeshRenderer src, MeshRenderer dst)
        {
            dst.sharedMaterials = src.sharedMaterials;
            dst.shadowCastingMode = ShadowCastingMode.Off; dst.receiveShadows = false;
            dst.lightProbeUsage = LightProbeUsage.Off; dst.reflectionProbeUsage = ReflectionProbeUsage.Off;
        }

        static void SetTau(DS29KeyposePlayer pl, GWClock clock, double tau, float t)
        {
            if (!float.IsNaN(t)) clock.SetSeconds(t);
            pl.ApplyTau(tau);
        }

        static void PlaceSide(Camera cam, Vector3 pos0, Quaternion rot0, Vector3 delta) => cam.transform.SetPositionAndRotation(pos0 + delta, rot0);

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

        // 1 コマの平均のミリ秒（毎コマ 1 画素を読み戻して GPU を待つ）
        static double TimeFrames(Camera camera, DS29KeyposePlayer pl, GWClock clock, DS27TimeWarp warp, int n)
        {
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var res = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rt.Create(); res.Create();
            var tex = new Texture2D(1, 1, TextureFormat.RGB24, false, false);
            var prev = camera.targetTexture;
            var clear = camera.clearFlags; var bg = camera.backgroundColor;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = SkyTop; camera.allowHDR = false; camera.allowMSAA = true;
            camera.aspect = (float)W / H;
            double ms;
            try
            {
                Action one = () =>
                {
                    camera.targetTexture = rt;
                    camera.Render();
                    Graphics.Blit(rt, res);
                    RenderTexture.active = res;
                    tex.ReadPixels(new Rect(W / 2, H / 2, 1, 1), 0, 0);
                    RenderTexture.active = null;
                };
                for (int i = 0; i < 10; i++) { SetTau(pl, clock, warp.TauAt(TStar), TStar); one(); }
                var sw = Stopwatch.StartNew();
                for (int i = 0; i < n; i++)
                {
                    double t = TEnd * i / Math.Max(1, n - 1);
                    SetTau(pl, clock, warp.TauAt(t), (float)t);
                    one();
                }
                ms = sw.Elapsed.TotalMilliseconds / n;
            }
            finally
            {
                camera.targetTexture = prev; camera.clearFlags = clear; camera.backgroundColor = bg;
                UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
                UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            }
            return ms;
        }

        // DS27Formation.EncodeVideo の写し（連番は書かない）
        static int EncodeVideo(Camera camera, DS29KeyposePlayer pl, GWClock clock, DS27TimeWarp warp, int fps, float seconds, string mp4, Action beforeRender, out string err)
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
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return path;
        }

        static string Sha(string path)
        {
            using (var s = System.Security.Cryptography.SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        [Serializable] class VideoRec { public string view, path, ffmpegError, sha256; public int frames, fps; public float seconds; public bool contextHidden; }
        [Serializable] class CaptureRec { public double tau; public string file; public int[] slices; public float[] weights; public float[] origin; }
        [Serializable] class CaptureReport { public string layout_ja; public int rows, cols; public CaptureRec[] captures; public float seconds; }
        [Serializable] class TimingRec { public string view; public int frames, width, height, msaa; public float[] msPerFrameWaveOn, msPerFrameWaveOff; public float medianOnMs, medianOffMs, waveMs; }
        [Serializable] class Report
        {
            public string unity, device, graphicsApi, name, package, packageJsonSha256, posSha256, twhiteSha256, meshPath, meshSha256, uv3Source, uv3Sha256, warpFile, warpFileSha256, noteJa, timingMethodJa;
            public int graphicsMemoryMB, rows, cols, layers, vertexCount, meshVertexStreams, whiteNeverCount, captureCount;
            public long indexCount, positionGpuBytes, whiteGpuBytes, meshVertexBufferBytes, meshIndexBufferBytes, sdfTextureBytes, driverBytesBeforeSurface, driverBytesAfterSurface, driverBytesAfterKeypose, alphaNot65535;
            public float surfaceLoadSeconds, keyposeLoadSeconds, totalSeconds;
            public bool meshFromPackage, protectedUnchanged, sceneDirtyNotSaved, passed;
            public Vector3 worldBoundsMin, worldBoundsMax, travelDirWorld;
            public string[] stillNames, files, filesSha256, protectedFiles, changedFiles; public float[] stillTau;
            public List<VideoRec> videos = new List<VideoRec>();
            public List<TimingRec> timing = new List<TimingRec>();
        }
    }
}
