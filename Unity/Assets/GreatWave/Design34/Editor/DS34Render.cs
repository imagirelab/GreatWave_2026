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
using GreatWave.Design31;
using UnityEditor;
using UnityEditor.Rendering;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design34.EditorTools
{
    // 設計34 Unity の部：帯・爪・小飛沫の 3 層を別々に、1 つの時計で Unity で再生する。
    // 設計31 の場面 DS31_WhiteSpray.unity（設計30 の単発再生＋飛沫。読むだけ）を開き、
    //   ・確認用の印（born・trace）と確認用の色の飛沫（spray_diag）を除き、飛沫 v0（spray）だけを残す、
    //   ・爪の層 DS34ClawPlayer（設計33 の 148 本の帯を 1 つの結合メッシュにし、コマの表の頂点を差し替える）と、
    //     入切の部品 DS34LayerSet（白の帯＝主役波のシートの色・爪・飛沫）を足し、
    //   ・設計34 の場面 DS34_ThreeLayers.unity として写しを保存する（設計30・31 の場面は変えない）。
    // そのあと、次を書く（Unity の PC オフスクリーン描画、HMD ではない）：
    //   a. t* の画像の組（美術優先28修正01 と同じ名前）：t28_white（爪なし・飛沫なし。設計31 の t28_white と同じはず）、t28_claws（爪を色の画像と ID に入れる）。
    //   b. 時刻のずれ：コマ k = 0〜420（t = k/30 s）ごとに Seek し、主役波の τ・爪のコマ番号・飛沫のコマ番号を記録する。さらに主役波の頂点を GPU で読み戻し
    //      （DS27KeyposeCapture.compute）、爪の根元（各爪の最初の頂点）とシートの結び付けの点（設計32 の sheet_rc、描画と同じ三角形の上）の距離を測る。
    //      対照として、爪を 1 コマ前・後にずらした距離も測る（ずれがあれば cm の桁で見える）。
    //   c. 静止画（painting・seat、3 層すべて）、d. 層の入切の一覧（2³ = 8 通り × t 11.5・12 s × painting・seat）、
    //   e. 動画（painting・seat × all・white・claws・spray、30 fps、t 0〜14 s）、
    //   f. 船の後ろの遮蔽：爪・飛沫を確認用の色（爪マゼンタ・飛沫シアン）で、①その層だけ、②その層＋船を深度だけで、③場面全体で、
    //      ④場面全体から船だけを消して描き、①にあって②にない画素（船の後ろ）のうち、④で見える画素（船がなければ見える＝船に隠されるべき画素）と、
    //      ③で見えている数（漏れ）を数える。視点 painting・seat・seat_low・seat_toward_wave と、船の向こうの爪を見上げる確認用の視点
    //      occl_mid・occl_fg・occl_left（舷の外、上端の 0.35 m 下。場面には保存しない）。
    //   g. Mock の両眼：seat・painting のカメラを右の向きへ ±IPD/2 = ±0.032 m ずらし、爪（と飛沫）の画素を目ごとに数える。色の画像も書く。
    //   h. 爪のシェーダーのコンパイル（キーワードなし・INSTANCING_ON・STEREO_INSTANCING_ON）。確認用の色が普通の描画に出ないこと（誤検出 0）。
    // 引数：-ds34Out（既定 Build/Design/34/unity3/main）、-ds34Skip scene,t28,timing,stills,toggles,video,occl,stereo,shader、-ds34Fps 30、
    //   -ds34VideoViews painting,seat、-ds34VideoSets all,white,claws,spray。
    // 実行は Tools/GWWaveGen/ds34/run_ds34_unity.ps1（unity.lock の手順、30 分以内）：-Method GreatWave.Design34.EditorTools.DS34Render.Render
    public static class DS34Render
    {
        const string Scene31 = "Assets/GreatWave/Design31/Scenes/DS31_WhiteSpray.unity";
        public const string Scene34 = "Assets/GreatWave/Design34/Scenes/DS34_ThreeLayers.unity";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const string ClawLayout = "Build/Design/33/claws/ds33_claw_layout.json";
        const string ClawRig = "Build/Design/33/claws/ds33_claw_rig.json";
        const string CapturePath = "Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute";
        const string DepthOnlyShader = "GreatWave/Design34/DS34 Depth Only";
        const string Ffmpeg = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe";
        static readonly string[] BoatNames = { "AF27 船 boat_left", "AF27 船 boat_mid", "AF27 船 boat_fg" };
        const int W = 1920, H = 1080;
        const float TStar = 12f, TEnd = 14f, Ipd = 0.064f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Color IdSky = new Color(1, 1, 1);
        static readonly Color32 ClawDiag = new Color32(255, 0, 255, 255), SprayDiag = new Color32(0, 255, 255, 255);

        static string[] Protected => new[] {
            "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity", Scene31,
            "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs", "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs",
            "Assets/GreatWave/Design31/Scripts/DS31InstancedParticles.cs", "Assets/GreatWave/Design31/Shaders/DS31_Spray_Unlit.shader",
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design27/Shaders/DS27KeyposeCore.cginc",
            "Assets/GreatWave/Design27/Shaders/DS27Keypose.cginc", CapturePath,
            "Build/Design/31/white/hero_pkg/ds27_keypose.json", "Build/Design/31/white/ds31_twhite_r32f.bin",
            "Build/Design/28R01F/F_final/timewarp_F_final.json", "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin",
            "Build/Design/31/spray/ds31_spray_frames.json", "Build/Design/31/spray/ds31_spray_frames.bin",
            ClawLayout, ClawRig, "Build/Design/33/claws/ds33_claw_frames_f32.bin", "Build/Design/33/claws/ds33_claw_tris_i32.bin",
            "Build/Design/33/claws/ds33_claw_tri_attr_u16.bin" };

        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        class Ctx
        {
            public GameObject ctx;
            public DS30SheetPlayer hero;
            public List<DS30SheetPlayer> sea = new List<DS30SheetPlayer>();
            public DS30SinglePlayback play;
            public MeshRenderer heroLine;
            public Dictionary<string, Camera> cams = new Dictionary<string, Camera>();
            public Vector3 sidePos0; public Quaternion sideRot0; public Vector3 oStar;
            public DS34ClawPlayer claws; public MeshRenderer clawR;
            public DS34LayerSet layers;
            public DS31InstancedParticles spray, sprayDiag;
            public Dictionary<string, List<Renderer>> boats = new Dictionary<string, List<Renderer>>();
            public List<Renderer> boatR = new List<Renderer>();
            public Material depthOnly;
        }

        class Cfg
        {
            public bool white = true, claws = true, spray = true, clawDiag, sprayDiag;
            public Cfg(bool w, bool c, bool s, bool cd = false, bool sd = false) { white = w; claws = c; spray = s; clawDiag = cd; sprayDiag = sd; }
            public string Tag => (white ? "W1" : "W0") + (claws ? "C1" : "C0") + (spray ? "S1" : "S0");   // Windows のファイル名は大文字と小文字を区別しないので 0/1 で書く
        }

        [Serializable] class TimingRec { public int k; public double t, clockSeconds, heroTau, warpTau, clawT, clawFrame, sprayT, sprayFrame; public bool clawOnGrid; public float rootMaxMm, rootMedMm, rootMaxPrevMm, rootMaxNextMm, rootTriMaxMm; }
        [Serializable] class RootClaw { public string id; public float maxMm, maxTriMm; public int worstK; }
        [Serializable] class OcclRec { public string view, layer; public float t; public int only, withBoat, behind, fullVisible, noBoatVisible, hiddenByBoat, leak; }
        [Serializable] class StereoRec { public string view; public float t; public int clawPxL, clawPxR, sprayPxL, sprayPxR; public float clawRelDiff, sprayRelDiff; }
        [Serializable] class VideoRec { public string set, view, path, sha256, ffmpegError; public int frames, fps; public float seconds; }
        [Serializable] class PassCheck { public string keywords, stage, messages; public bool compiled, stereoCheck, rtArrayIndexInOutput; }
        [Serializable] class CamRec { public string name; public Vector3 pos, target, boatMin, boatMax; public float fov; public string boat; }
        [Serializable] class FalsePos { public string view; public float t; public int clawDiagPx, sprayDiagPx; }
        [Serializable]
        class Report
        {
            public string unity, device, graphicsApi, scene34, scene34Sha256, clawLayout, clawFramesSha256, clawTrisSha256, clawAttrSha256, sprayPath, spraySha256, noteJa;
            public int clawCount, clawVertices, clawTriangles, clawWhiteTriangles, clawMizuiroTriangles, clawFrames, sprayCount, sprayFrames;
            public float clawHz, sprayHz, clawLoadSeconds;
            public TimingRec[] timing; public RootClaw[] rootPerClaw; public int timingMaxFrameOffsetClaw, timingMaxFrameOffsetSpray; public double timingMaxTauDiff;
            public float rootMaxMmAll, rootTriMaxMmAll, rootMaxPrevMmMin, rootMaxNextMmMin, rootMaxPrevMmMedian;
            public OcclRec[] occlusion; public CamRec[] occlCams; public StereoRec[] stereo; public FalsePos[] falsePositives; public VideoRec[] videos; public PassCheck[] shaderChecks;
            public string[] files, filesSha256, protectedFiles, changedFiles; public bool protectedUnchanged, shaderAllCompiled;
            public float secondsTotal; public double tauAtTStar;
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var a = Environment.GetCommandLineArgs();
            string od = Arg(a, "-ds34Out") ?? "Build/Design/34/unity3/main";
            var skip = new HashSet<string>((Arg(a, "-ds34Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            int fps = int.Parse(Arg(a, "-ds34Fps") ?? "30", CultureInfo.InvariantCulture);
            var vViews = (Arg(a, "-ds34VideoViews") ?? "painting,seat").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            var vSets = (Arg(a, "-ds34VideoSets") ?? "all,white,claws,spray").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var files = new List<string>();
            var rep = new Report { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString() };

            // ---- 場面
            EditorSceneManager.OpenScene(Scene31, OpenSceneMode.Single);
            var scene = EditorSceneManager.GetActiveScene();
            var roots = scene.GetRootGameObjects();
            var c = new Ctx { ctx = roots.First(g => g.name == ContextRootName) };
            c.play = roots.Select(g => g.GetComponentInChildren<DS30SinglePlayback>(true)).First(x => x != null);
            c.hero = c.play.sheets.First(s => s.sheetName == "hero");
            c.sea = c.play.sheets.Where(s => s != c.hero).ToList();
            c.heroLine = c.hero.outline;
            var camRoot = GameObject.Find(CamRoot).transform;
            foreach (var n in new[] { "painting", "seat", "seat_low", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            var stwT = camRoot.Find("DS30 seat_toward_wave");
            if (stwT != null) c.cams["seat_toward_wave"] = stwT.GetComponent<Camera>();
            var side31 = camRoot.Find("DS31 side_top");
            if (side31 != null) UnityEngine.Object.DestroyImmediate(side31.gameObject);
            var clock = c.play.clock;
            // 設計31 の粒子のうち、飛沫 v0 だけを残す（印と確認用の色の飛沫は設計31 の確認用で、作品には入れない）
            var allParts = roots.SelectMany(g => g.GetComponentsInChildren<DS31InstancedParticles>(true)).ToList();
            foreach (var p in allParts)
            {
                if (p.name == "DS31 spray") c.spray = p;
                else UnityEngine.Object.DestroyImmediate(p.gameObject);
            }
            if (c.spray == null) throw new InvalidOperationException("設計31 の場面に飛沫（DS31 spray）がありません");
            c.spray.drawInPlayMode = true; c.spray.clock = clock;
            if (c.spray.transform.parent != null) c.spray.transform.parent.name = "DS34 飛沫の層（設計31 の飛沫 v0、光を使わない不透明の小球の instancing）";
            rep.sprayPath = Path.GetFullPath(c.spray.dataPath);

            var cg = new GameObject("DS34 爪の層（設計33 の 148 本の帯、1 つの結合メッシュ）");
            cg.AddComponent<MeshFilter>();
            c.clawR = cg.AddComponent<MeshRenderer>();
            c.claws = cg.AddComponent<DS34ClawPlayer>();
            c.claws.layoutPath = ClawLayout; c.claws.clock = clock;
            var lg = new GameObject("DS34 3 層の入切（白の帯＝シートの色・爪・飛沫。Play モードの 1・2・3 キー）");
            c.layers = lg.AddComponent<DS34LayerSet>();
            c.layers.playback = c.play; c.layers.heroSheet = c.hero; c.layers.claws = c.claws; c.layers.spray = c.spray;
            if (!skip.Contains("scene"))
            {
                if (!EditorSceneManager.SaveScene(scene, Scene34, true)) throw new InvalidOperationException("場面を保存できません: " + Scene34);
                rep.scene34 = Scene34; rep.scene34Sha256 = Sha(Scene34);
            }

            // ---- 検査だけの物（場面には保存しない）
            var dg = new GameObject("DS34 確認用の色の飛沫（シアン）");
            c.sprayDiag = dg.AddComponent<DS31InstancedParticles>();
            c.sprayDiag.dataPath = c.spray.dataPath; c.sprayDiag.clock = clock; c.sprayDiag.subdivisions = c.spray.subdivisions;
            c.sprayDiag.colourFromJson = false; c.sprayDiag.colour = new Color(0, 1, 1, 1); c.sprayDiag.drawInPlayMode = false;
            var dsh = Shader.Find(DepthOnlyShader);
            if (dsh == null) throw new InvalidOperationException("シェーダーがありません: " + DepthOnlyShader);
            c.depthOnly = new Material(dsh) { hideFlags = HideFlags.DontSave };
            foreach (var bn in BoatNames)
            {
                var bt = c.ctx.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == bn);
                if (bt == null) continue;
                var rs = bt.GetComponentsInChildren<Renderer>(false).Where(r => r.enabled).ToList();
                c.boats[bn] = rs; c.boatR.AddRange(rs);
            }

            c.sidePos0 = c.cams["side_left"].transform.position; c.sideRot0 = c.cams["side_left"].transform.rotation;
            c.play.Prepare();
            c.spray.Load(); c.sprayDiag.Load(); c.claws.Load();
            c.oStar = c.hero.OriginAt(0.0);
            rep.tauAtTStar = c.play.Warp.TauAt(TStar);
            rep.clawLayout = Path.GetFullPath(ClawLayout); rep.clawFramesSha256 = c.claws.FramesSha256; rep.clawTrisSha256 = c.claws.TrisSha256; rep.clawAttrSha256 = c.claws.AttrSha256;
            rep.clawCount = c.claws.ClawCount; rep.clawVertices = c.claws.VertexCount; rep.clawTriangles = c.claws.TriangleCount; rep.clawFrames = c.claws.Frames; rep.clawHz = c.claws.Hz;
            rep.clawWhiteTriangles = c.claws.WhiteTriangles; rep.clawMizuiroTriangles = c.claws.MizuiroTriangles; rep.clawLoadSeconds = c.claws.LoadSeconds;
            rep.spraySha256 = c.spray.DataSha256; rep.sprayCount = c.spray.Count; rep.sprayFrames = c.spray.Frames; rep.sprayHz = c.spray.Hz;
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            Shader.SetGlobalFloat("_DS27DebugMode", 0);
            Shader.SetGlobalFloat("_DS27WhiteEnabled", 1);
            Shader.SetGlobalFloat("_DS34ClawDiag", 0);

            // 船の後ろから爪を見る確認用の視点（場面には保存しない）：t* の爪の根元のうち船の中心に近い 20 本の重心を狙い、
            // 水平にはその反対の側の舷の外（船の外接箱の水平の半径 + 0.3 m）、高さは舷の上端（外接箱の上端）の 0.35 m 下に置く。
            // 船の網が視野の下半分を覆い、爪・飛沫の一部が船の向こうに入る（船がなければ見える画素があることを ④ で確かめる）
            var occlCams = new List<CamRec>();
            Seek(c, TStar, new Cfg(true, true, true));
            foreach (var bn in new[] { "AF27 船 boat_mid", "AF27 船 boat_fg", "AF27 船 boat_left" })
            {
                if (!c.boats.ContainsKey(bn) || c.boats[bn].Count == 0) continue;
                var b = c.boats[bn][0].bounds;
                foreach (var r in c.boats[bn]) b.Encapsulate(r.bounds);
                var rootsNow = Enumerable.Range(0, c.claws.ClawCount).Select(i => c.claws.FrameVertex(c.claws.Frames - 1, c.claws.VertOffset[i])).ToList();
                var near = rootsNow.OrderBy(p => (p - b.center).sqrMagnitude).Take(20).ToList();
                var tgt = near.Aggregate(Vector3.zero, (s2, p) => s2 + p) / near.Count;
                var dh = new Vector3(b.center.x - tgt.x, 0, b.center.z - tgt.z).normalized;
                var pos = new Vector3(b.center.x, b.max.y - 0.35f, b.center.z) + dh * (new Vector2(b.extents.x, b.extents.z).magnitude + 0.3f);
                var nm = "occl_" + bn.Substring(bn.LastIndexOf('_') + 1);
                var go = new GameObject("DS34 " + nm);
                go.transform.SetParent(camRoot, true);
                var cam = go.AddComponent<Camera>();
                cam.enabled = false; cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = SkyTop;
                cam.fieldOfView = 60f; cam.nearClipPlane = .05f; cam.farClipPlane = 900; cam.aspect = (float)W / H; cam.allowHDR = false; cam.allowMSAA = true;
                go.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(tgt - pos, Vector3.up));
                c.cams[nm] = cam;
                occlCams.Add(new CamRec { name = nm, pos = pos, target = tgt, fov = 60f, boat = bn, boatMin = b.min, boatMax = b.max });
            }
            rep.occlCams = occlCams.ToArray();

            try
            {
                if (!skip.Contains("shader")) { rep.shaderChecks = ShaderCheck(); rep.shaderAllCompiled = rep.shaderChecks.All(x => x.compiled); }

                // a. t*
                if (!skip.Contains("t28"))
                {
                    Seek(c, TStar, new Cfg(true, false, false));
                    files.AddRange(RenderT28(c, od + "/t28_white/t28/render"));
                    Seek(c, TStar, new Cfg(true, true, false));
                    files.AddRange(RenderT28(c, od + "/t28_claws/t28/render"));
                }

                // b. 時刻のずれと根元
                if (!skip.Contains("timing")) Timing(c, rep);

                // c. 静止画
                if (!skip.Contains("stills"))
                    foreach (var t in new[] { 6f, 8f, 9f, 10f, 10.5f, 11f, 11.5f, 12f, 13f })
                    {
                        Seek(c, t, new Cfg(true, true, true));
                        foreach (var v in new[] { "painting", "seat", "seat_low", "seat_toward_wave" })
                            files.Add(CaptureCfg(c, v, new Cfg(true, true, true), string.Format(CultureInfo.InvariantCulture, "{0}/stills/ds34_all_{1}_t{2:00.00}s.png", od, v, t)));
                    }

                // d. 層の入切の一覧
                if (!skip.Contains("toggles"))
                    foreach (var t in new[] { 11.5f, 12f })
                        foreach (var w in new[] { false, true })
                            foreach (var cl in new[] { false, true })
                                foreach (var sp in new[] { false, true })
                                {
                                    var cfg = new Cfg(w, cl, sp);
                                    Seek(c, t, cfg);
                                    foreach (var v in new[] { "painting", "seat" })
                                        files.Add(CaptureCfg(c, v, cfg, string.Format(CultureInfo.InvariantCulture, "{0}/toggles/ds34_{1}_{2}_t{3:00.00}s.png", od, cfg.Tag, v, t)));
                                }

                // f. 船の後ろの遮蔽
                if (!skip.Contains("occl")) rep.occlusion = Occlusion(c, od + "/occl", files).ToArray();

                // g. Mock の両眼
                if (!skip.Contains("stereo")) { rep.stereo = Stereo(c, od + "/stereo", files).ToArray(); rep.falsePositives = FalsePositives(c).ToArray(); }

                // e. 動画
                var vids = new List<VideoRec>();
                if (!skip.Contains("video"))
                {
                    Directory.CreateDirectory(od + "/video");
                    foreach (var set in vSets)
                        foreach (var v in vViews)
                        {
                            var sw = Stopwatch.StartNew();
                            var mp4 = od + "/video/ds34_" + set + "_" + v + "_" + fps + "fps.mp4";
                            int nf = EncodeVideo(c, v, SetCfg(set), fps, TEnd, mp4, out string err);
                            vids.Add(new VideoRec { set = set, view = v, path = Path.GetFullPath(mp4), frames = nf, fps = fps, seconds = (float)sw.Elapsed.TotalSeconds, ffmpegError = err, sha256 = File.Exists(mp4) ? Sha(mp4) : "" });
                            if (!File.Exists(mp4)) throw new InvalidOperationException("動画を書けませんでした: " + err);
                        }
                }
                rep.videos = vids.ToArray();
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                Shader.SetGlobalFloat("_DS27DebugMode", 0);
                Shader.SetGlobalFloat("_DS34ClawDiag", 0);
                ResetCams(c);
                foreach (var s in c.play.sheets) s.Release();
                c.spray.Release(); c.sprayDiag.Release(); c.claws.Release();
            }
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.files = files.ToArray();
            rep.filesSha256 = files.Select(Sha).ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render）。HMD 実機ではない。Mock の両眼はカメラを ±0.032 m ずらした 2 回の描画で、立体の描画経路（SPI）ではない。";
            File.WriteAllText(od + "/ds34_render_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS34_RENDER_DONE seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static Cfg SetCfg(string set)
        {
            switch (set)
            {
                case "white": return new Cfg(true, false, false);
                case "claws": return new Cfg(false, true, false);
                case "spray": return new Cfg(false, false, true);
                case "none": return new Cfg(false, false, false);
                default: return new Cfg(true, true, true);
            }
        }

        // 1 つの時刻 t を 3 層へ同じに渡す（主役波と海は再生器の Seek で τ(t)、爪と飛沫は ApplyT(t)）。入切を適用する
        static void Seek(Ctx c, double t, Cfg cfg)
        {
            c.play.Seek(t);
            c.spray.ApplyT(t); c.sprayDiag.ApplyT(t);
            c.claws.ApplyT(t);
            Apply(c, cfg);
        }

        static void Apply(Ctx c, Cfg cfg)
        {
            c.layers.whiteBand = cfg.white; c.layers.clawsOn = cfg.claws; c.layers.sprayOn = cfg.spray;
            c.layers.ApplyToggles();
            Shader.SetGlobalFloat("_DS34ClawDiag", cfg.clawDiag ? 1f : 0f);
        }

        static void PlaceCams(Ctx c)
        {
            c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0 + (c.hero.AppliedOrigin - c.oStar), c.sideRot0);
        }

        static void ResetCams(Ctx c)
        {
            c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0, c.sideRot0);
        }

        // side_left・seat_toward_wave は背景（船・富士など）を隠す。空のドームと平らな海は残す（設計29〜31 と同じ）
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

        static CommandBuffer AttachSpray(Ctx c, Camera cam, Cfg cfg)
        {
            if (!cfg.spray) return null;
            var cb = new CommandBuffer { name = "DS34 飛沫" };
            (cfg.sprayDiag ? c.sprayDiag : c.spray).AddTo(cb);
            cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            return cb;
        }

        static void Detach(Camera cam, CommandBuffer cb)
        {
            if (cb == null) return;
            cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
            cb.Release();
        }

        static string CaptureCfg(Ctx c, string view, Cfg cfg, string path)
        {
            var cam = c.cams[view];
            var hid = HideFor(c, view);
            CommandBuffer cb = null;
            try
            {
                Apply(c, cfg);
                PlaceCams(c);
                cb = AttachSpray(c, cam, cfg);
                CaptureRaw(cam, W, H, true, SkyTop, path, null);
                return path;
            }
            finally { Detach(cam, cb); foreach (var r in hid) r.enabled = true; ResetCams(c); }
        }

        // 設計31 の RenderT28 と同じ（ID と _kstar にも周りの海と平らな海を入れる t28_seaids の読み）。爪は層の入切のまま色の画像と ID に入る。飛沫は入れない
        static List<string> RenderT28(Ctx c, string d28)
        {
            var f = new List<string>();
            Directory.CreateDirectory(d28);
            try
            {
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
            }
            return f;
        }

        // ---- b. 時刻のずれと根元
        static void Timing(Ctx c, Report rep)
        {
            var rig = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(ClawRig)), "rig");
            var rc = new Dictionary<string, double[]>();
            foreach (var o in (List<object>)DS27Json.Get(rig, "claws"))
            {
                var d = DS27Json.AsObj(o, "claw");
                rc[DS27Json.Text(d, "id")] = DS27Json.Nums(DS27Json.Get(d, "sheet_rc"), "sheet_rc");
            }
            var cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(CapturePath);
            int kern = cs.FindKernel("DS27Capture");
            int rows = c.hero.PackageMeta.rows, cols = c.hero.PackageMeta.cols, n = rows * cols;
            var buf = new ComputeBuffer(n * 2, 16);
            var outv = new Vector4[n * 2];
            int K = c.claws.ClawCount;
            var perMax = new float[K]; var perTri = new float[K]; var perK = new int[K];
            var recs = new List<TimingRec>();
            int nf = c.claws.Frames;
            try
            {
                for (int k = 0; k < nf; k++)
                {
                    double t = k / (double)c.claws.Hz;
                    Seek(c, t, new Cfg(true, true, true));
                    var r = new TimingRec
                    {
                        k = k, t = t, clockSeconds = c.play.clock != null ? c.play.clock.Seconds : double.NaN, heroTau = c.hero.AppliedTau, warpTau = c.play.Warp.TauAt(Math.Min(t, TStar)),
                        clawT = c.claws.AppliedT, clawFrame = c.claws.AppliedFrame, clawOnGrid = c.claws.AppliedOnGrid, sprayT = c.spray.AppliedT,
                        sprayFrame = (c.spray.AppliedT - c.spray.T0) * c.spray.Hz
                    };
                    c.hero.BindCompute(cs, kern);
                    cs.SetBuffer(kern, "_DS27Out", buf);
                    cs.SetInt("_DS27Count", n);
                    cs.Dispatch(kern, (n + 63) / 64, 1, 1);
                    buf.GetData(outv);
                    Func<int, int, Vector3> P = (ri, ci) => { var v = outv[2 * (ri * cols + ci)]; return new Vector3(v.x, v.y, v.z); };
                    var ds = new List<float>();
                    float mx = 0, mp = 0, mn = 0, mt = 0;
                    for (int i = 0; i < K; i++)
                    {
                        var id = c.claws.ClawIds[i];
                        if (!rc.ContainsKey(id)) continue;
                        double rr = rc[id][0], cc = rc[id][1];
                        int r0 = Math.Max(0, Math.Min(rows - 2, (int)Math.Floor(rr))), c0 = Math.Max(0, Math.Min(cols - 2, (int)Math.Floor(cc)));
                        float fr = (float)(rr - r0), fc = (float)(cc - c0);
                        Vector3 A = P(r0, c0), B = P(r0 + 1, c0), Cc = P(r0, c0 + 1), D = P(r0 + 1, c0 + 1);
                        Vector3 s = fr + fc <= 1f ? A + fr * (B - A) + fc * (Cc - A) : Cc + (1f - fc) * (B - Cc) + (fr + fc - 1f) * (D - Cc);
                        var root = c.claws.FrameVertex(k, c.claws.VertOffset[i]);
                        float d = (root - s).magnitude * 1000f;
                        // 近くの三角形（3 × 3 の四角）の面までの最短距離
                        float dt = float.MaxValue;
                        for (int ri = Math.Max(0, r0 - 1); ri <= Math.Min(rows - 2, r0 + 1); ri++)
                            for (int ci = Math.Max(0, c0 - 1); ci <= Math.Min(cols - 2, c0 + 1); ci++)
                            {
                                Vector3 a0 = P(ri, ci), b0 = P(ri + 1, ci), c1 = P(ri, ci + 1), d1 = P(ri + 1, ci + 1);
                                dt = Math.Min(dt, (ClosestOnTri(root, a0, b0, c1) - root).magnitude);
                                dt = Math.Min(dt, (ClosestOnTri(root, c1, b0, d1) - root).magnitude);
                            }
                        dt *= 1000f;
                        ds.Add(d);
                        mx = Math.Max(mx, d); mt = Math.Max(mt, dt);
                        if (d > perMax[i]) { perMax[i] = d; perK[i] = k; }
                        perTri[i] = Math.Max(perTri[i], dt);
                        if (k > 0) mp = Math.Max(mp, (c.claws.FrameVertex(k - 1, c.claws.VertOffset[i]) - s).magnitude * 1000f);
                        if (k < nf - 1) mn = Math.Max(mn, (c.claws.FrameVertex(k + 1, c.claws.VertOffset[i]) - s).magnitude * 1000f);
                    }
                    ds.Sort();
                    r.rootMaxMm = mx; r.rootMedMm = ds.Count > 0 ? ds[ds.Count / 2] : float.NaN; r.rootTriMaxMm = mt;
                    r.rootMaxPrevMm = k > 0 ? mp : float.NaN; r.rootMaxNextMm = k < nf - 1 ? mn : float.NaN;
                    recs.Add(r);
                }
            }
            finally { buf.Release(); }
            rep.timing = recs.ToArray();
            rep.rootPerClaw = Enumerable.Range(0, K).Select(i => new RootClaw { id = c.claws.ClawIds[i], maxMm = perMax[i], maxTriMm = perTri[i], worstK = perK[i] }).ToArray();
            rep.timingMaxFrameOffsetClaw = recs.Max(r => (int)Math.Round(Math.Abs(r.clawFrame - r.k) * 1000.0));   // 1/1000 コマの単位
            rep.timingMaxFrameOffsetSpray = recs.Max(r => (int)Math.Round(Math.Abs(r.sprayFrame - r.k) * 1000.0));
            rep.timingMaxTauDiff = recs.Max(r => Math.Abs(r.heroTau - r.warpTau));
            rep.rootMaxMmAll = recs.Max(r => r.rootMaxMm);
            rep.rootTriMaxMmAll = recs.Max(r => r.rootTriMaxMm);
            var prev = recs.Where(r => !float.IsNaN(r.rootMaxPrevMm)).Select(r => r.rootMaxPrevMm).OrderBy(x => x).ToList();
            rep.rootMaxPrevMmMin = prev.Count > 0 ? prev[0] : float.NaN;
            rep.rootMaxPrevMmMedian = prev.Count > 0 ? prev[prev.Count / 2] : float.NaN;
            var next = recs.Where(r => !float.IsNaN(r.rootMaxNextMm)).Select(r => r.rootMaxNextMm).OrderBy(x => x).ToList();
            rep.rootMaxNextMmMin = next.Count > 0 ? next[0] : float.NaN;
        }

        // 点 p に最も近い三角形 abc の上の点（Ericson, Real-Time Collision Detection 5.1.5）
        static Vector3 ClosestOnTri(Vector3 p, Vector3 a, Vector3 b, Vector3 c)
        {
            Vector3 ab = b - a, ac = c - a, ap = p - a;
            float d1 = Vector3.Dot(ab, ap), d2 = Vector3.Dot(ac, ap);
            if (d1 <= 0f && d2 <= 0f) return a;
            Vector3 bp = p - b; float d3 = Vector3.Dot(ab, bp), d4 = Vector3.Dot(ac, bp);
            if (d3 >= 0f && d4 <= d3) return b;
            float vc = d1 * d4 - d3 * d2;
            if (vc <= 0f && d1 >= 0f && d3 <= 0f) return a + ab * (d1 / (d1 - d3));
            Vector3 cp = p - c; float d5 = Vector3.Dot(ab, cp), d6 = Vector3.Dot(ac, cp);
            if (d6 >= 0f && d5 <= d6) return c;
            float vb = d5 * d2 - d1 * d6;
            if (vb <= 0f && d2 >= 0f && d6 <= 0f) return a + ac * (d2 / (d2 - d6));
            float va = d3 * d6 - d5 * d4;
            if (va <= 0f && (d4 - d3) >= 0f && (d5 - d6) >= 0f) return b + (c - b) * ((d4 - d3) / ((d4 - d3) + (d5 - d6)));
            float den = 1f / (va + vb + vc);
            return a + ab * (vb * den) + ac * (vc * den);
        }

        // ---- f. 船の後ろの遮蔽
        static List<OcclRec> Occlusion(Ctx c, string dir, List<string> files)
        {
            var recs = new List<OcclRec>();
            Directory.CreateDirectory(dir);
            var views = new[] { "painting", "seat", "seat_low", "seat_toward_wave", "occl_mid", "occl_fg", "occl_left" }.Where(v => c.cams.ContainsKey(v)).ToArray();
            var allR = UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None).Where(r => r.enabled).ToList();
            foreach (var t in new[] { 8f, 9f, 10f, 10.5f, 11f, 11.5f, 12f })
                foreach (var v in views)
                    foreach (var layer in new[] { "claws", "spray" })
                    {
                        var cam = c.cams[v];
                        bool isClaw = layer == "claws";
                        Color32 diag = isClaw ? ClawDiag : SprayDiag;
                        var only = new Cfg(false, isClaw, !isClaw, isClaw, !isClaw);
                        Seek(c, t, only);
                        PlaceCams(c);
                        // ① その層だけ、② その層＋船（深度だけ）
                        var off = new List<Renderer>();
                        var mats = new Dictionary<Renderer, Material[]>();
                        Color32[] p1, p2, p3, p4;
                        CommandBuffer cb = null;
                        try
                        {
                            foreach (var r in allR) if (r != c.clawR && r.enabled) { r.enabled = false; off.Add(r); }
                            cb = AttachSpray(c, cam, only);
                            p1 = CaptureRaw(cam, W, H, false, IdSky, null, null);
                            foreach (var r in c.boatR) { mats[r] = r.sharedMaterials; r.sharedMaterials = Enumerable.Repeat(c.depthOnly, r.sharedMaterials.Length).ToArray(); r.enabled = true; }
                            p2 = CaptureRaw(cam, W, H, false, IdSky, null, null);
                        }
                        finally
                        {
                            Detach(cam, cb); cb = null;
                            foreach (var kv in mats) kv.Key.sharedMaterials = kv.Value;
                            foreach (var r in c.boatR) r.enabled = false;
                            foreach (var r in off) r.enabled = true;
                        }
                        // ③ 場面全体（ほかの層は作品の色、調べる層だけ確認用の色）
                        var full = new Cfg(true, true, true, isClaw, !isClaw);
                        try
                        {
                            Apply(c, full);
                            cb = AttachSpray(c, cam, full);
                            p3 = CaptureRaw(cam, W, H, false, SkyTop, null, null);
                        }
                        finally { Detach(cam, cb); cb = null; }
                        // ④ 場面全体から船だけを消したもの（船がなければ見える画素。①にあって②にない画素のうち、ここで見えるものが「船に隠された」画素）
                        try
                        {
                            foreach (var r in c.boatR) r.enabled = false;
                            cb = AttachSpray(c, cam, full);
                            p4 = CaptureRaw(cam, W, H, false, SkyTop, null, null);
                        }
                        finally { Detach(cam, cb); foreach (var r in c.boatR) r.enabled = true; Apply(c, new Cfg(true, true, true)); ResetCams(c); }
                        var rec = new OcclRec { view = v, layer = layer, t = t };
                        var mask = new bool[p1.Length];
                        for (int i = 0; i < p1.Length; i++)
                        {
                            bool a1 = Eq(p1[i], diag), a2 = Eq(p2[i], diag), a3 = Eq(p3[i], diag), a4 = Eq(p4[i], diag);
                            if (a1) rec.only++;
                            if (a2) rec.withBoat++;
                            if (a3) rec.fullVisible++;
                            if (a4) rec.noBoatVisible++;
                            if (a1 && !a2) { rec.behind++; if (a4) { rec.hiddenByBoat++; mask[i] = true; } if (a3) rec.leak++; }
                        }
                        recs.Add(rec);
                        if (rec.hiddenByBoat > 0 && (t == 10f || t == 11f || t == 12f))
                        {
                            var name = string.Format(CultureInfo.InvariantCulture, "{0}/{1}_{2}_t{3:00.0}", dir, v, layer, t);
                            WritePng(p3, W, H, name + "_full.png", files);
                            WritePng(p4, W, H, name + "_noboat.png", files);
                            var mp = new Color32[p1.Length];
                            for (int i = 0; i < mp.Length; i++) mp[i] = mask[i] ? new Color32(255, 255, 255, 255) : new Color32(0, 0, 0, 255);
                            WritePng(mp, W, H, name + "_behind.png", files);
                            // 色の画像（MSAA、作品の色）も同じコマで
                            files.Add(CaptureCfg(c, v, new Cfg(true, true, true), name + "_colour.png"));
                        }
                    }
            return recs;
        }

        static bool Eq(Color32 a, Color32 b) => a.r == b.r && a.g == b.g && a.b == b.b;

        // ---- g. Mock の両眼
        static List<StereoRec> Stereo(Ctx c, string dir, List<string> files)
        {
            var recs = new List<StereoRec>();
            Directory.CreateDirectory(dir);
            foreach (var t in new[] { 8f, 9f, 10f, 11f, 12f, 13f })
            {
                Seek(c, t, new Cfg(true, true, true));
                foreach (var v in new[] { "seat", "painting" })
                {
                    var cam = c.cams[v];
                    var p0 = cam.transform.position;
                    var rec = new StereoRec { view = v, t = t };
                    try
                    {
                        foreach (var eye in new[] { -1, 1 })
                        {
                            cam.transform.position = p0 + cam.transform.right * (0.5f * Ipd * eye);
                            string tag = eye < 0 ? "L" : "R";
                            int nc = CountDiag(c, v, new Cfg(true, true, true, true, false), ClawDiag);
                            int ns = CountDiag(c, v, new Cfg(true, true, true, false, true), SprayDiag);
                            if (eye < 0) { rec.clawPxL = nc; rec.sprayPxL = ns; } else { rec.clawPxR = nc; rec.sprayPxR = ns; }
                            if (t >= 10f && t <= 12f)
                            {
                                var path = string.Format(CultureInfo.InvariantCulture, "{0}/{1}_t{2:00.0}_{3}.png", dir, v, t, tag);
                                var hid = HideFor(c, v); CommandBuffer cb = null;
                                try { Apply(c, new Cfg(true, true, true)); cb = AttachSpray(c, cam, new Cfg(true, true, true)); CaptureRaw(cam, W, H, true, SkyTop, path, files); }
                                finally { Detach(cam, cb); foreach (var r in hid) r.enabled = true; }
                                var pathd = string.Format(CultureInfo.InvariantCulture, "{0}/{1}_t{2:00.0}_{3}_clawdiag.png", dir, v, t, tag);
                                Apply(c, new Cfg(true, true, true, true, false));
                                CaptureRaw(cam, W, H, false, SkyTop, pathd, files);
                                Apply(c, new Cfg(true, true, true));
                            }
                        }
                    }
                    finally { cam.transform.position = p0; Apply(c, new Cfg(true, true, true)); }
                    rec.clawRelDiff = Math.Abs(rec.clawPxL - rec.clawPxR) / (float)Math.Max(1, Math.Max(rec.clawPxL, rec.clawPxR));
                    rec.sprayRelDiff = Math.Abs(rec.sprayPxL - rec.sprayPxR) / (float)Math.Max(1, Math.Max(rec.sprayPxL, rec.sprayPxR));
                    recs.Add(rec);
                }
            }
            return recs;
        }

        static int CountDiag(Ctx c, string v, Cfg cfg, Color32 diag)
        {
            var cam = c.cams[v];
            var hid = HideFor(c, v);
            CommandBuffer cb = null;
            try
            {
                Apply(c, cfg);
                PlaceCams(c);
                cb = AttachSpray(c, cam, cfg);
                var px = CaptureRaw(cam, W, H, false, SkyTop, null, null);
                int n = 0;
                foreach (var p in px) if (Eq(p, diag)) n++;
                return n;
            }
            finally { Detach(cam, cb); foreach (var r in hid) r.enabled = true; ResetCams(c); Apply(c, new Cfg(true, true, true)); }
        }

        // 確認用の色（マゼンタ・シアン）が、確認用の色を使わない描画に出ないこと
        static List<FalsePos> FalsePositives(Ctx c)
        {
            var l = new List<FalsePos>();
            foreach (var t in new[] { 10f, 12f })
            {
                Seek(c, t, new Cfg(true, true, true));
                foreach (var v in new[] { "painting", "seat", "seat_low", "seat_toward_wave", "occl_mid", "occl_fg", "occl_left" }.Where(x => c.cams.ContainsKey(x)))
                {
                    var cam = c.cams[v];
                    var hid = HideFor(c, v); CommandBuffer cb = null;
                    Color32[] px;
                    try { PlaceCams(c); cb = AttachSpray(c, cam, new Cfg(true, true, true)); px = CaptureRaw(cam, W, H, false, SkyTop, null, null); }
                    finally { Detach(cam, cb); foreach (var r in hid) r.enabled = true; ResetCams(c); }
                    l.Add(new FalsePos { view = v, t = t, clawDiagPx = px.Count(p => Eq(p, ClawDiag)), sprayDiagPx = px.Count(p => Eq(p, SprayDiag)) });
                }
            }
            return l;
        }

        static void WritePng(Color32[] px, int w, int h, string path, List<string> files)
        {
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, true);
            tex.SetPixels32(px); tex.Apply();
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllBytes(path, tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
            files?.Add(path);
        }

        static Color32[] CaptureRaw(Camera camera, int w, int h, bool colour, Color bgc, string path, List<string> files)
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
                files?.Add(path);
            }
            camera.targetTexture = prev; camera.aspect = asp;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return px;
        }

        static string Capture(Camera camera, int w, int h, bool colour, string path)
        {
            CaptureRaw(camera, w, h, colour, colour ? (Color)SkyTop : IdSky, path, null);
            return path;
        }

        static int EncodeVideo(Ctx c, string view, Cfg cfg, int fps, float seconds, string mp4, out string err)
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
                Apply(c, cfg);
                cb = AttachSpray(c, camera, cfg);
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
                            Seek(c, i / (double)fps, cfg);
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
            finally { Detach(camera, cb); foreach (var r in hid) r.enabled = true; ResetCams(c); Apply(c, new Cfg(true, true, true)); }
            return n;
        }

        static PassCheck[] ShaderCheck()
        {
            var checks = new List<PassCheck>();
            var sh = Shader.Find(DS34ClawPlayer.ShaderName);
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

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
