using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using GreatWave.ArtFirst;
using GreatWave.Design27;
using GreatWave.Design30;
using UnityEditor;
using UnityEditor.Rendering;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design31.EditorTools
{
    // 設計31 白の部：設計30 の単発再生の場面（DS30_SinglePlayback.unity、読むだけ）を開き、
    //   ・主役波のパッケージを設計31 の写し（Build/Design/31/white/hero_pkg：位置は F_final のハードリンク、T_white だけ ds31_white_rate_cap の版）へ替え、
    //   ・光を使わない不透明の小球の instancing（DS31InstancedParticles）を 3 組足す：飛沫 v0（飛沫の部のパッケージ）、いま白くなった所の印（赤）、移流の印（朱）。
    //   ・設計31 の場面 DS31_WhiteSpray.unity として写しを保存する（設計30 の場面は変えない）。
    // そのあと、次を書く：
    //   a. t* の画像の組（美術優先28修正01 と同じ名前）：t28_white（飛沫なし。設計30 の t28_seaids と同じ読み）・t28_spray（色の画像と ID に飛沫を入れる）。
    //   b. 102・176 の ID の連続：主役波だけ（線なし・周りの海と文脈を隠す）を、原画視点と座席 v1 で、表示の色区 ID（_AF28IdMode = 1）と
    //      終態の色区 ID（_DS27DebugMode = 2）で描き、時刻ごとに「表示が白」「終態が白」「表示が白で終態が白でない」画素を数える。
    //   c. 静止画、d. 動画（gen：発生位置＝いま白くなった所の印＋飛沫、adv：移流の印＋飛沫、air：飛沫だけ。視点 painting・seat・side_left、30 fps、t 0〜14 s）、
    //   e. 152 の確かめ用の対（飛沫あり・なしの同じコマ、MSAA 8 の色の画像）、f. シェーダーのコンパイル（キーワードなし・INSTANCING_ON・STEREO_INSTANCING_ON）。
    // 引数：-ds31Out、-ds31Hero <パッケージ|package>、-ds31Spray <粒子の枠の JSON|none>、-ds31Born、-ds31Trace、-ds31Skip scene,t28,ids,stills,video,pairs,shader、
    //   -ds31Views painting,seat,side_left、-ds31Sets gen,adv,air、-ds31Fps 30、-ds31IdTimes（コンマ区切りの秒）、-ds31Sub 1（球の分割）。
    // 実行は Tools/GWWaveGen/ds31/run_ds31_unity.ps1（unity.lock の手順、30 分以内）：-Method GreatWave.Design31.EditorTools.DS31Render.Render
    public static class DS31Render
    {
        const string Scene30 = "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity";
        public const string Scene31 = "Assets/GreatWave/Design31/Scenes/DS31_WhiteSpray.unity";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const string HeroPkg31 = "Build/Design/31/white/hero_pkg";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        const int W = 1920, H = 1080;
        const float TStar = 12f, TEnd = 14f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);

        static string[] Protected => new[] {
            Scene30, "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs", "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs",
            "Assets/GreatWave/Design30/Editor/DS30Render.cs", "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader",
            "Assets/GreatWave/Design27/Shaders/DS27KeyposeCore.cginc", "Assets/GreatWave/Design27/Shaders/DS27Keypose.cginc",
            "Build/Design/28R01F/F_final/art_on/ds27_keypose.json", "Build/Design/28R01F/F_final/art_on/ds27_twhite_r32f.bin",
            "Build/Design/28R01F/F_final/timewarp_F_final.json", "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin" };

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        class Ctx
        {
            public GameObject ctx, flatSea, skyDome;
            public DS30SheetPlayer hero;
            public List<DS30SheetPlayer> sea = new List<DS30SheetPlayer>();
            public DS30SinglePlayback play;
            public MeshRenderer heroLine, curtainR;
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public Vector3 sidePos0; public Quaternion sideRot0; public Vector3 oStar;
            public Dictionary<string, DS31InstancedParticles> parts = new Dictionary<string, DS31InstancedParticles>();
            public Dictionary<string, KeyValuePair<Vector3, Quaternion>> extra = new Dictionary<string, KeyValuePair<Vector3, Quaternion>>();
        }

        [Serializable] class IdRec { public string view; public float t; public double tau; public int dispWhite, finalWhite, dispWhiteFinalNot, finalWhiteShownPre, finalNonWhite, dispNonWhiteNotFinal, sky; }
        [Serializable] class VideoRec { public string set, view, path, sha256, ffmpegError; public int frames, fps; public float seconds; }
        [Serializable] class PartRec { public string name, dataPath, dataSha256; public int count, frames, maxAlive, sphereTriangles; public float hz; public long gpuBytes; public float[] colour; }
        [Serializable] class PassCheck { public string keywords, stage, messages; public bool compiled, stereoCheck, rtArrayIndexInOutput; }
        [Serializable] class StereoRec { public string view; public float t; public int sprayPxL, sprayPxR; public float relDiff; }
        [Serializable] class AliveRec { public float t; public int spray, born, trace; }
        [Serializable]
        class Report
        {
            public string unity, device, graphicsApi, heroPkg, heroTwhiteSha256, scene31, scene31Sha256, sprayPath, noteJa;
            public PartRec[] particles; public IdRec[] ids; public StereoRec[] stereo; public VideoRec[] videos; public PassCheck[] shaderChecks; public AliveRec[] alive;
            public string[] files, filesSha256, protectedFiles, changedFiles; public bool protectedUnchanged, shaderAllCompiled;
            public float secondsTotal; public double tauAtTStar;
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string od = Arg(a, "-ds31Out") ?? "Build/Design/31/white/unity";
            string heroPkg = Arg(a, "-ds31Hero") ?? HeroPkg31;
            string sprayPath = Arg(a, "-ds31Spray") ?? "Build/Design/31/spray/ds31_spray_frames.json";
            string bornPath = Arg(a, "-ds31Born") ?? "Build/Design/31/white/ds31_marks_born.json";
            string tracePath = Arg(a, "-ds31Trace") ?? "Build/Design/31/white/ds31_marks_trace.json";
            var skip = new HashSet<string>((Arg(a, "-ds31Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            var views = (Arg(a, "-ds31Views") ?? "painting,seat,side_left,side_top").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            var sets = (Arg(a, "-ds31Sets") ?? "gen,adv,air").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            int fps = int.Parse(Arg(a, "-ds31Fps") ?? "30", CultureInfo.InvariantCulture);
            int sub = int.Parse(Arg(a, "-ds31Sub") ?? "1", CultureInfo.InvariantCulture);
            var idTimes = (Arg(a, "-ds31IdTimes") ?? "0,2,4,5.5,5.75,6,6.25,6.5,6.75,7,7.25,7.5,7.75,8,8.25,8.5,8.75,9,9.25,9.5,9.75,10,10.25,10.5,10.75,11,11.25,11.5,11.75,12,13,14")
                .Split(',').Select(x => float.Parse(x, CultureInfo.InvariantCulture)).ToArray();
            bool useSpray = sprayPath != "none" && File.Exists(sprayPath);
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var files = new List<string>();
            var rep = new Report { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), heroPkg = heroPkg, sprayPath = useSpray ? Path.GetFullPath(sprayPath) : "none" };

            // ---- 場面（設計30 の場面を開き、主役波のパッケージを替え、粒子を足して写しを保存する）
            EditorSceneManager.OpenScene(Scene30, OpenSceneMode.Single);
            var scene = EditorSceneManager.GetActiveScene();
            var roots = scene.GetRootGameObjects();
            var c = new Ctx { ctx = roots.First(g => g.name == ContextRootName) };
            c.play = roots.Select(g => g.GetComponentInChildren<DS30SinglePlayback>(true)).First(x => x != null);
            c.hero = c.play.sheets.First(s => s.sheetName == "hero");
            c.sea = c.play.sheets.Where(s => s != c.hero).ToList();
            c.heroLine = c.hero.outline;
            c.curtainR = c.play.curtains.Count > 0 && c.play.curtains[0] != null ? c.play.curtains[0].GetComponent<MeshRenderer>() : null;
            var camRoot = GameObject.Find(CamRoot).transform;
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            var stwT = camRoot.Find("DS30 seat_toward_wave");
            if (stwT != null) c.cams["seat_toward_wave"] = stwT.GetComponent<Camera>();
            c.flatSea = FindChild(c.ctx, FlatSeaName);
            c.skyDome = FindChild(c.ctx, SkyDomeName);
            if (heroPkg != "package") c.hero.packageDir = heroPkg;
            var clock = c.play.clock;

            var pr = new GameObject("DS31 飛沫と印（光を使わない不透明の小球の instancing）");
            Action<string, string, Color?> addPart = (key, path, col) =>
            {
                if (path == "none" || !File.Exists(path)) return;
                var g = new GameObject("DS31 " + key);
                g.transform.SetParent(pr.transform, false);
                var p = g.AddComponent<DS31InstancedParticles>();
                p.dataPath = path; p.clock = clock; p.subdivisions = sub;
                if (col.HasValue) { p.colourFromJson = false; p.colour = col.Value; }
                p.drawInPlayMode = key == "spray";   // Play モードで描くのは飛沫だけ（印と確認用の色の飛沫は確認用）
                c.parts[key] = p;
            };
            if (useSpray) addPart("spray", sprayPath, null);
            // 確認用の色の飛沫（同じ粒子の枠を明るい赤紫で描く。白い空・白い波・藍の海の前でも軌跡が読めるように。gen・adv の動画だけ）
            if (useSpray) addPart("spray_diag", sprayPath, new Color(0.93f, 0.15f, 0.72f, 1f));
            addPart("born", bornPath, null);
            addPart("trace", tracePath, null);
            if (!skip.Contains("scene"))
            {
                if (!EditorSceneManager.SaveScene(scene, Scene31, true)) throw new InvalidOperationException("場面を保存できません: " + Scene31);
                rep.scene31 = Scene31; rep.scene31Sha256 = Sha(Scene31);
            }

            c.sidePos0 = c.cams["side_left"].transform.position; c.sideRot0 = c.cams["side_left"].transform.rotation;
            // 追加の視点（場面には保存しない）：-ds31ExtraCams "名前:x,y,z,tx,ty,tz,fov;…"（t* のワールドの位置と注視点。波の枠とともに動く＝side_left と同じ扱い）
            foreach (var spec in (Arg(a, "-ds31ExtraCams") ?? "side_top:-17,40,-42,1,9,-8,30").Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries))
            {
                var nm = spec.Split(':')[0];
                var v = spec.Split(':')[1].Split(',').Select(x => float.Parse(x, CultureInfo.InvariantCulture)).ToArray();
                var go = new GameObject("DS31 " + nm);
                go.transform.SetParent(camRoot, true);
                var cam = go.AddComponent<Camera>();
                cam.enabled = false;
                cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = SkyTop;
                cam.fieldOfView = v[6]; cam.nearClipPlane = .1f; cam.farClipPlane = 900; cam.aspect = (float)W / H;
                cam.allowHDR = false; cam.allowMSAA = true;
                var pos = new Vector3(v[0], v[1], v[2]);
                go.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(new Vector3(v[3], v[4], v[5]) - pos, Vector3.up));
                c.cams[nm] = cam;
                c.extra[nm] = new KeyValuePair<Vector3, Quaternion>(go.transform.position, go.transform.rotation);
            }
            c.play.Prepare();
            foreach (var p in c.parts.Values) p.Load();
            c.oStar = c.hero.OriginAt(0.0);
            rep.tauAtTStar = c.play.Warp.TauAt(TStar);
            rep.heroTwhiteSha256 = c.hero.PackageMeta.twhiteSha256;
            rep.particles = c.parts.Select(kv => new PartRec
            {
                name = kv.Key, dataPath = Path.GetFullPath(kv.Value.dataPath), dataSha256 = kv.Value.DataSha256, count = kv.Value.Count, frames = kv.Value.Frames,
                maxAlive = kv.Value.MaxAlive, sphereTriangles = kv.Value.SphereTriangles, hz = kv.Value.Hz, gpuBytes = kv.Value.GpuBytes,
                colour = new[] { kv.Value.colour.r, kv.Value.colour.g, kv.Value.colour.b }
            }).ToArray();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);

            try
            {
                // f. シェーダーのコンパイル
                if (!skip.Contains("shader")) { rep.shaderChecks = ShaderCheck(); rep.shaderAllCompiled = rep.shaderChecks.All(x => x.compiled); }

                // 粒子の生きている数（30 Hz）
                var al = new List<AliveRec>();
                for (int k = 0; k <= Mathf.RoundToInt(TEnd * fps); k++)
                {
                    double t = k / (double)fps;
                    var r = new AliveRec { t = (float)t };
                    foreach (var kv in c.parts) { kv.Value.ApplyT(t); if (kv.Key == "spray") r.spray = kv.Value.AliveNow; else if (kv.Key == "born") r.born = kv.Value.AliveNow; else if (kv.Key == "trace") r.trace = kv.Value.AliveNow; }
                    al.Add(r);
                }
                rep.alive = al.ToArray();

                // a. t*
                if (!skip.Contains("t28"))
                {
                    Seek(c, TStar);
                    files.AddRange(RenderT28(c, od + "/t28_white/t28/render", new string[0]));
                    if (c.parts.ContainsKey("spray")) files.AddRange(RenderT28(c, od + "/t28_spray/t28/render", new[] { "spray" }));
                }

                // b. 102・176 の ID の連続（主役波だけ）
                if (!skip.Contains("ids")) rep.ids = IdSeries(c, od + "/ids", idTimes, files).ToArray();

                // c. 静止画
                if (!skip.Contains("stills"))
                {
                    foreach (var set in sets)
                        foreach (var t in (Arg(a, "-ds31StillT") ?? "6,8,9,10,10.5,11,11.5,12").Split(',').Select(x => float.Parse(x, CultureInfo.InvariantCulture)))
                        {
                            Seek(c, t);
                            foreach (var v in views)
                                files.Add(CaptureWith(c, v, SetParts(set), string.Format(CultureInfo.InvariantCulture, "{0}/stills/ds31_{1}_{2}_t{3:00.00}s.png", od, set, v, t)));
                        }
                }

                // d. 動画
                var vids = new List<VideoRec>();
                if (!skip.Contains("video"))
                {
                    Directory.CreateDirectory(od + "/video");
                    foreach (var set in sets)
                        foreach (var v in views)
                        {
                            var sw = Stopwatch.StartNew();
                            var mp4 = od + "/video/ds31_" + set + "_" + v + "_" + fps + "fps.mp4";
                            int nf = EncodeVideo(c, v, SetParts(set), fps, TEnd, mp4, out string err);
                            vids.Add(new VideoRec { set = set, view = v, path = Path.GetFullPath(mp4), frames = nf, fps = fps, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = File.Exists(mp4) ? Sha(mp4) : "" });
                            if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
                        }
                }
                rep.videos = vids.ToArray();

                // g. Mock の両眼（HMD の代わり。座席 v1 のカメラを右の向きへ ±IPD/2 = ±0.032 m ずらして 2 回描き、飛沫の画素を目ごとに数える）
                if (!skip.Contains("stereo") && c.parts.ContainsKey("spray"))
                {
                    var st = new List<StereoRec>();
                    foreach (var t in new[] { 10f, 11f, 12f })
                    {
                        Seek(c, t);
                        foreach (var v in new[] { "seat", "painting" })
                        {
                            var cam = c.cams[v];
                            var p0 = cam.transform.position;
                            var rec = new StereoRec { view = v, t = t };
                            try
                            {
                                foreach (var eye in new[] { -1, 1 })
                                {
                                    cam.transform.position = p0 + cam.transform.right * (0.032f * eye);
                                    string tag = eye < 0 ? "L" : "R";
                                    var on = CaptureWithRaw(c, v, new[] { "spray" }, string.Format(CultureInfo.InvariantCulture, "{0}/stereo/{1}_t{2:00.0}_{3}_on.png", od, v, t, tag), files);
                                    var off = CaptureWithRaw(c, v, new string[0], null, null);
                                    int n = 0;
                                    for (int i = 0; i < on.Length; i++) if (Math.Abs(on[i].r - off[i].r) > 6 || Math.Abs(on[i].g - off[i].g) > 6 || Math.Abs(on[i].b - off[i].b) > 6) n++;
                                    if (eye < 0) rec.sprayPxL = n; else rec.sprayPxR = n;
                                }
                            }
                            finally { cam.transform.position = p0; }
                            rec.relDiff = Math.Abs(rec.sprayPxL - rec.sprayPxR) / (float)Math.Max(1, Math.Max(rec.sprayPxL, rec.sprayPxR));
                            st.Add(rec);
                        }
                    }
                    rep.stereo = st.ToArray();
                }

                // e. 152 の対（飛沫あり・なし）
                if (!skip.Contains("pairs") && c.parts.ContainsKey("spray"))
                {
                    for (float t = 5f; t <= 12.001f; t += 0.5f)
                    {
                        Seek(c, t);
                        foreach (var v in new[] { "painting", "seat", "side_left", "side_top" })
                        {
                            files.Add(CaptureWith(c, v, new[] { "spray" }, string.Format(CultureInfo.InvariantCulture, "{0}/pairs/{1}_t{2:00.0}_on.png", od, v, t)));
                            files.Add(CaptureWith(c, v, new string[0], string.Format(CultureInfo.InvariantCulture, "{0}/pairs/{1}_t{2:00.0}_off.png", od, v, t)));
                        }
                    }
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat("_DS27DebugMode", 0);
                ResetCams(c);
                foreach (var s in c.play.sheets) s.Release();
                foreach (var p in c.parts.Values) p.Release();
            }
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.files = files.ToArray();
            rep.filesSha256 = files.Select(Sha).ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode）。HMD 実機ではない。粒子は DS31InstancedParticles（光を使わない不透明の小球、1 回の DrawMeshInstancedProcedural）。";
            File.WriteAllText(od + "/ds31_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS31_RENDER_DONE seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static string[] SetParts(string set)
        {
            switch (set)
            {
                case "gen": return new[] { "born", "spray_diag" };
                case "adv": return new[] { "trace", "spray_diag" };
                case "air": return new[] { "spray" };
                default: return new string[0];
            }
        }

        static void Seek(Ctx c, double t)
        {
            c.play.Seek(t);
            foreach (var p in c.parts.Values) p.ApplyT(t);
        }

        static void PlaceCams(Ctx c)
        {
            c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0 + (c.hero.AppliedOrigin - c.oStar), c.sideRot0);
            foreach (var kv in c.extra) c.cams[kv.Key].transform.SetPositionAndRotation(kv.Value.Key + (c.hero.AppliedOrigin - c.oStar), kv.Value.Value);
        }

        static void ResetCams(Ctx c)
        {
            c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0, c.sideRot0);
            foreach (var kv in c.extra) c.cams[kv.Key].transform.SetPositionAndRotation(kv.Value.Key, kv.Value.Value);
        }

        // side_left は背景（船・富士など）を隠す。空のドームと平らな海は残す（設計29・30 と同じ）
        static List<Renderer> HideFor(Ctx c, string view)
        {
            var hid = new List<Renderer>();
            if (view != "side_left" && view != "seat_toward_wave" && !c.extra.ContainsKey(view)) return hid;
            foreach (var rr in c.ctx.GetComponentsInChildren<Renderer>(false))
            {
                if (!rr.enabled || rr.name == SkyDomeName || rr.name == FlatSeaName) continue;
                rr.enabled = false; hid.Add(rr);
            }
            return hid;
        }

        static CommandBuffer Attach(Ctx c, Camera cam, IEnumerable<string> parts)
        {
            var list = parts.Where(p => c.parts.ContainsKey(p)).ToList();
            if (list.Count == 0) return null;
            var cb = new CommandBuffer { name = "DS31 粒子" };
            foreach (var p in list) c.parts[p].AddTo(cb);
            cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            return cb;
        }

        static void Detach(Camera cam, CommandBuffer cb)
        {
            if (cb == null) return;
            cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            cb.Release();
        }

        static string CaptureWith(Ctx c, string view, string[] parts, string path)
        {
            var cam = c.cams[view];
            var hid = HideFor(c, view);
            CommandBuffer cb = null;
            try
            {
                PlaceCams(c);
                cb = Attach(c, cam, parts);
                return Capture(cam, W, H, true, path);
            }
            finally { Detach(cam, cb); foreach (var r in hid) r.enabled = true; ResetCams(c); }
        }

        static Color32[] CaptureWithRaw(Ctx c, string view, string[] parts, string path, List<string> files)
        {
            var cam = c.cams[view];
            var hid = HideFor(c, view);
            CommandBuffer cb = null;
            try
            {
                PlaceCams(c);
                cb = Attach(c, cam, parts);
                return CaptureRaw(cam, W, H, true, path, files);
            }
            finally { Detach(cam, cb); foreach (var r in hid) r.enabled = true; ResetCams(c); }
        }

        // 設計30 の RenderT28 の t28_seaids の読み（ID と _kstar にも周りの海と平らな海を入れる）。parts の粒子は色の画像と ID の両方に入れる
        static List<string> RenderT28(Ctx c, string d28, string[] parts)
        {
            var f = new List<string>();
            Directory.CreateDirectory(d28);
            var cbs = new List<KeyValuePair<Camera, CommandBuffer>>();
            try
            {
                foreach (var v in new[] { "painting", "seat", "seat_low" }) cbs.Add(new KeyValuePair<Camera, CommandBuffer>(c.cams[v], Attach(c, c.cams[v], parts)));
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
                foreach (var kv in cbs) Detach(kv.Key, kv.Value);
            }
            return f;
        }

        // 102・176：主役波だけ（線なし、周りの海・幕・文脈を隠す）。表示の色区 ID と終態の色区 ID を同じコマで描いて数える
        static List<IdRec> IdSeries(Ctx c, string dir, float[] times, List<string> files)
        {
            var recs = new List<IdRec>();
            Directory.CreateDirectory(dir);
            var seaR = c.sea.Select(s => s.Surface).Where(r => r != null).ToList();
            if (c.curtainR != null) seaR.Add(c.curtainR);
            c.ctx.SetActive(false);
            foreach (var r in seaR) r.enabled = false;
            c.heroLine.enabled = false;
            try
            {
                foreach (var t in times)
                {
                    Seek(c, t);
                    foreach (var v in new[] { "painting", "seat" })
                    {
                        var cam = c.cams[v];
                        Shader.SetGlobalFloat("_DS27DebugMode", 0);
                        Shader.SetGlobalFloat("_AF28IdMode", 1);
                        var pd = CaptureRaw(cam, W, H, false, string.Format(CultureInfo.InvariantCulture, "{0}/{1}_t{2:00.00}_disp.png", dir, v, t), files);
                        Shader.SetGlobalFloat("_AF28IdMode", 0);
                        Shader.SetGlobalFloat("_DS27DebugMode", 2);
                        var pf = CaptureRaw(cam, W, H, false, string.Format(CultureInfo.InvariantCulture, "{0}/{1}_t{2:00.00}_final.png", dir, v, t), files);
                        Shader.SetGlobalFloat("_DS27DebugMode", 0);
                        var r = new IdRec { view = v, t = t, tau = c.play.Tau };
                        for (int i = 0; i < pd.Length; i++)
                        {
                            var d = pd[i]; var q = pf[i];
                            bool dw = d.r == 255 && d.g == 0 && d.b == 0, fw = q.r == 255 && q.g == 0 && q.b == 0;
                            bool fsky = q.r == 255 && q.g == 255 && q.b == 255;
                            if (fsky) { r.sky++; continue; }
                            if (dw) r.dispWhite++;
                            if (fw) r.finalWhite++; else r.finalNonWhite++;
                            if (dw && !fw) r.dispWhiteFinalNot++;
                            if (fw && !dw) r.finalWhiteShownPre++;
                            if (!dw && !fw && (d.r != q.r || d.g != q.g || d.b != q.b)) r.dispNonWhiteNotFinal++;
                        }
                        recs.Add(r);
                    }
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat("_DS27DebugMode", 0);
                c.ctx.SetActive(true);
                foreach (var r in seaR) r.enabled = true;
                c.heroLine.enabled = true;
            }
            return recs;
        }

        static Color32[] CaptureRaw(Camera camera, int w, int h, bool colour, string path, List<string> files)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = colour ? (Color)SkyTop : IdSky;
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
            camera.targetTexture = prev; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return px;
        }

        static string Capture(Camera camera, int w, int h, bool colour, string path)
        {
            CaptureRaw(camera, w, h, colour, path, null);
            return path;
        }

        static int EncodeVideo(Ctx c, string view, string[] parts, int fps, float seconds, string mp4, out string err)
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
                cb = Attach(c, camera, parts);
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
            finally { Detach(camera, cb); foreach (var r in hid) r.enabled = true; ResetCams(c); }
            return n;
        }

        static PassCheck[] ShaderCheck()
        {
            var checks = new List<PassCheck>();
            var sh = Shader.Find(DS31InstancedParticles.ShaderName);
            var data = ShaderUtil.GetShaderData(sh);
            var sets = new[] { new string[0], new[] { "INSTANCING_ON" }, new[] { "STEREO_INSTANCING_ON", "INSTANCING_ON" } };
            for (int s = 0; s < data.SubshaderCount; s++)
            {
                var subs = data.GetSubshader(s);
                for (int p = 0; p < subs.PassCount; p++)
                {
                    var pass = subs.GetPass(p);
                    foreach (var kw in sets)
                        foreach (var st in new[] { UnityEditor.Rendering.ShaderType.Vertex, UnityEditor.Rendering.ShaderType.Fragment })
                        {
                            if (!pass.HasShaderStage(st)) continue;
                            var ck = new PassCheck { keywords = string.Join(" ", kw), stage = st.ToString() };
                            var info = pass.CompileVariant(st, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64);
                            ck.compiled = info.Success;
                            ck.messages = string.Join(" | ", info.Messages.Select(m => m.severity + ": " + m.message));
                            if (st == UnityEditor.Rendering.ShaderType.Vertex && kw.Contains("STEREO_INSTANCING_ON"))
                            {
                                var pre = pass.PreprocessVariant(st, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64, true);
                                var code = pre.Success ? (pre.PreprocessedCode ?? "") : "";
                                var sm = Regex.Match(code, @"struct\s+v2f\s*\{([^}]*)\}");
                                ck.stereoCheck = true;
                                ck.rtArrayIndexInOutput = sm.Success && sm.Groups[1].Value.Contains("SV_RenderTargetArrayIndex");
                            }
                            checks.Add(ck);
                        }
                }
            }
            return checks.ToArray();
        }

        static GameObject FindChild(GameObject root, string n)
        {
            var t = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == n);
            return t != null ? t.gameObject : null;
        }

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
