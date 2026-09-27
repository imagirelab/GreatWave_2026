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

namespace GreatWave.Design28.EditorTools
{
    // 設計28 の確認用の視点「seat_toward_wave」（証拠のための視点で、設計の変更ではない）。
    // 座席 v1 の目（seat_v1.json、設計27 の場面のカメラ「DS27 seat」と同じ位置）から、近づく波の方向（進行方向 t の逆、水平）を
    // 縦の画角 70° で見る。座席 v1 は上を急に見上げるので、形成の段階 a〜d が座席の視点では見えなかった（設計27 の限界 4）。
    // 設計27 の再生器と採取（Unity/Assets/GreatWave/Design27/、場面 DS27_Formation.unity）は変えない：
    //   場面を開き、この視点のカメラをメモリの上だけに足して描き、場面は保存しない（前後の SHA-256 を記録する）。
    //   静止画と動画の採取の設定は DS27Formation の Capture・EncodeVideo と同じ（写し：sRGB の RT、MSAA 8x、背景は空上、
    //   ffmpeg の libx264 -preset medium -crf 18、PNG の連番）。PC のオフスクリーン描画で、HMD 実機ではない。
    // 引数は DS27Formation と同じ（-ds27Package・-ds27Warp・-ds27WarpFile・-ds27Out・-ds27Stills・-ds27Skip video,frames,stills・-ds27Fps）。
    // 足した引数：-ds28Fov <縦の画角、既定 70>、-ds28HideContext 1（船・富士・仮置きを隠し、主役波・空・参照海面だけにする。既定は隠さない）、
    //   -ds28ViewName <名前、既定 seat_toward_wave>。
    // 出力：<out>/stills/ds27_<名前>_<段階>_tau±x.png、<out>/video/ds27_<名前>_30fps.mp4、<out>/frames/<名前>/f_0000.png…、
    //   <out>/ds28_review_view_<名前>.json（カメラ、パッケージ、ファイルの SHA-256、場面を保存していないことの確かめ）。
    // 実行は Tools/GWWaveGen/ds28/run_ds28_unity.ps1（unity.lock の手順、30 分以内）：
    //   -Method GreatWave.Design28.EditorTools.DS28ReviewView.Render
    public static class DS28ReviewView
    {
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080;
        const float TEnd = 14f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static string[] Protected => new[] {
            DS27Formation.ScenePath, "Assets/GreatWave/Design27/Editor/DS27Formation.cs", "Assets/GreatWave/Design27/Scripts/DS27KeyposePlayer.cs",
            "Assets/GreatWave/Design27/Materials/DS27_NPR_White.mat", "Assets/GreatWave/Design27/Materials/DS27_Outline_Keypose.mat",
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design27/Shaders/DS27_Outline_Keypose.shader",
            "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab", "../Tools/GWContext/seat_v1.json" };

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
            float fov = float.Parse(Arg(args, "-ds28Fov") ?? "70", CultureInfo.InvariantCulture);
            bool hideCtx = (Arg(args, "-ds28HideContext") ?? "0") == "1";
            string viewName = Arg(args, "-ds28ViewName") ?? "seat_toward_wave";
            var before = Protected.ToDictionary(p => p, Sha);

            EditorSceneManager.OpenScene(DS27Formation.ScenePath, OpenSceneMode.Single);
            var roots = EditorSceneManager.GetActiveScene().GetRootGameObjects();
            var pl = roots.Select(g => g.GetComponent<DS27KeyposePlayer>()).First(x => x != null);
            var nw = pl.GetComponent<AF28NprWave>();
            var clock = roots.Select(g => g.GetComponent<GWClock>()).First(x => x != null);
            var ctx = roots.First(g => g.name == ContextRootName);
            var seatCam = GameObject.Find(CamRoot).transform.Find("DS27 seat").GetComponent<Camera>();
            var mesh = nw.EnsureLoaded();
            pl.whiteEnabled = true;
            pl.Reload(cfg.package);
            var warp = DS27TimeWarp.Load(cfg.warpFile);
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat(DS27KeyposePlayer.DebugId, 0);
            nw.outline.enabled = true;

            // 近づく波の方向：波の枠の原点 O(τ) の動き（進行方向 t）の逆を、水平に
            var o0 = pl.OriginAt(pl.PackageMeta.knotTau[0]);
            var o1 = pl.OriginAt(0.0);
            var tdir = o1 - o0; tdir.y = 0; tdir.Normalize();
            var look = -tdir;
            var eye = seatCam.transform.position;
            var go = new GameObject("DS28 " + viewName + "（メモリの上だけ。場面は保存しない）");
            var cam = go.AddComponent<Camera>();
            cam.enabled = false;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = SkyTop;
            cam.fieldOfView = fov; cam.nearClipPlane = .1f; cam.farClipPlane = 900; cam.aspect = (float)W / H;
            cam.allowHDR = false; cam.allowMSAA = true;
            go.transform.SetPositionAndRotation(eye, Quaternion.LookRotation(look, Vector3.up));

            var hidden = hideCtx ? HideContext(ctx) : new List<Renderer>();
            string od = cfg.outDir;
            Directory.CreateDirectory(od);
            var files = new List<string>();
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                view = viewName, package = pl.PackageMeta.dir, packageJsonSha256 = pl.PackageMeta.jsonSha256, posSha256 = pl.PackageMeta.posSha256,
                warpFile = warp.Path, warpFileSha256 = Sha(warp.Path), eye = eye, forward = cam.transform.forward, fov = fov, contextHidden = hideCtx,
                travelDirWorld = tdir,
                noteJa = "座席 v1 の目から、近づく波の方向（波の枠の原点 O(τ) が τ の最初の節点から t* まで進む向き t の逆、水平）を縦の画角 " + fov.ToString(CultureInfo.InvariantCulture) +
                         "° で見る確認用の視点（設計28 の証拠。設計の変更ではない）。カメラはメモリの上だけで、場面は保存しない。" +
                         (hideCtx ? "船・富士・仮置きを隠し、主役波・空・参照海面だけを描いた。" : "背景（船・富士・前景の仮置き）はそのまま描いた。") +
                         "PC のオフスクリーン描画で、HMD 実機ではない。"
            };
            try
            {
                if (!cfg.skip.Contains("stills") && cfg.stillsFromArgs)
                {
                    string ds = od + "/stills";
                    Directory.CreateDirectory(ds);
                    for (int s = 0; s < cfg.stillNames.Count; s++)
                    {
                        pl.ApplyTau(cfg.stillTau[s]);
                        files.Add(Capture(cam, string.Format(CultureInfo.InvariantCulture, "{0}/ds27_{1}_{2}_tau{3:+0.000;-0.000}.png", ds, viewName, cfg.stillNames[s], cfg.stillTau[s])));
                    }
                }
                if (!cfg.skip.Contains("video"))
                {
                    string dv = od + "/video";
                    Directory.CreateDirectory(dv);
                    var mp4 = dv + "/ds27_" + viewName + "_" + cfg.fps + "fps.mp4";
                    string framesDir = cfg.skip.Contains("frames") ? null : od + "/frames/" + viewName;
                    var sw = Stopwatch.StartNew();
                    rep.videoFrames = EncodeVideo(cam, pl, clock, warp, cfg.fps, TEnd, mp4, framesDir, out var err);
                    rep.videoSeconds = (float)sw.Elapsed.TotalSeconds;
                    rep.ffmpegError = err;
                    if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
                    rep.video = Path.GetFullPath(mp4); rep.videoSha256 = Sha(mp4);
                    rep.framesDir = framesDir == null ? "" : Path.GetFullPath(framesDir);
                    rep.pngFrames = framesDir != null && Directory.Exists(framesDir) ? Directory.GetFiles(framesDir, "*.png").Length : 0;
                }
            }
            finally
            {
                foreach (var rr in hidden) rr.enabled = true;
                UnityEngine.Object.DestroyImmediate(go);
            }
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.sceneDirtyNotSaved = EditorSceneManager.GetActiveScene().isDirty;
            rep.meshVertexCount = mesh.vertexCount;
            rep.files = files.ToArray();
            rep.filesSha256 = files.Select(Sha).ToArray();
            rep.totalSeconds = (float)total.Elapsed.TotalSeconds;
            rep.passed = rep.protectedUnchanged && mesh.vertexCount == 96000;
            File.WriteAllText(od + "/ds28_review_view_" + viewName + ".json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("DS28_REVIEW_VIEW_DONE view=" + viewName + " files=" + files.Count + " seconds=" + rep.totalSeconds + " passed=" + rep.passed);
            if (!rep.passed) throw new InvalidOperationException("保護したファイルが変わったか、網が違います（ds28_review_view_*.json）。");
        }

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

        // DS27Formation.Capture（色）の写し：sRGB の RT に MSAA 8x、背景は空上
        static string Capture(Camera camera, string path)
        {
            var prev = camera.targetTexture;
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var res = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rt.Create(); res.Create();
            camera.aspect = (float)W / H;
            camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(W, H, TextureFormat.RGB24, false, false);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return path;
        }

        // DS27Formation.EncodeVideo の写し（各コマ t = i/fps の τ を時間曲線の表から求め、ffmpeg へ生の RGB を流す）
        static int EncodeVideo(Camera camera, DS27KeyposePlayer pl, GWClock clock, DS27TimeWarp warp, int fps, float seconds, string mp4, string framesDir, out string err)
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
                var prev = camera.targetTexture;
                camera.aspect = (float)W / H;
                try
                {
                    for (int i = 0; i < n; i++)
                    {
                        double t = i / (double)fps;
                        clock.SetSeconds((float)t);
                        pl.ApplyTau(warp.TauAt(t));
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
                    camera.targetTexture = prev;
                    UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
                    UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
                }
                if (!p.WaitForExit(10 * 60 * 1000)) { p.Kill(); throw new InvalidOperationException("ffmpeg が終わりません。"); }
                p.WaitForExit();
                lock (sb) err = sb.ToString() + (p.ExitCode != 0 ? " exit=" + p.ExitCode : "");
            }
            return n;
        }

        static string Sha(string path)
        {
            using (var s = System.Security.Cryptography.SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        [Serializable] class Report
        {
            public string unity, device, graphicsApi, view, package, packageJsonSha256, posSha256, warpFile, warpFileSha256, noteJa, video, videoSha256, framesDir, ffmpegError;
            public Vector3 eye, forward, travelDirWorld; public float fov, videoSeconds, totalSeconds; public bool contextHidden, protectedUnchanged, sceneDirtyNotSaved, passed;
            public int videoFrames, pngFrames, meshVertexCount; public string[] protectedFiles, files, filesSha256;
        }
    }
}
