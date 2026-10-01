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
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Polish29.EditorTools
{
    // 仕上げ29（Q28）の前の点検（AUDIT）：今の採用の状態（仕上げ28 の K*′ P28R2rec・動き G_p28rec・29修正01 の焼き込みを P28R2rec へ焼き直した bake_rec）を、
    // 原画視点・座席・座席から波の方向・左の側面・右の側面・後ろ（後ろ 65°）・真上と回り台から、同じ時刻（既定 t 6・9・10.5・12 s）で描く。
    // 仕上げ28 の PL28Render.cs の写しで、場面 DS39_Paper.unity（設計50 の DS50_Release.unity と同じ主役波・焼き込み・爪・飛沫・線・周りの海のファイル）を
    // 読むだけで開き（保存しない）、主役波のシートと時間曲線だけを差し替える（-pl29State p28）。爪（設計33）・飛沫・線の印・周りの海は合わせ直さない。
    // 色の画像（1920×1080、sRGB、MSAA 8）：asis＝爪・飛沫・線あり（紙なし）、clawfree＝爪なし・飛沫なし・線あり。
    // 診断の画像（1920×1080、ARGB32 線形、MSAA なし、線なし、飛沫なし。主役波の面だけ PL29_HeroDiag の材質へ一時的に替え、ほかは ID の色）：
    //   uv_claws0 / uv_claws1：主役波の UV3 のテクセルの番号（4096×4096、24 bit。アルファ 128 が主役波）。爪なし／爪あり（爪が主役波を隠す画素を数える）。
    //   px_claws0 / py_claws0：K* の頂点を原画カメラへ投影した原画の画素の x・y（24 bit の固定小数）。投影の引き伸ばしと継ぎ目を numpy で測る。
    //   id_claws0 / id_claws1：_AF28IdMode = 1 の色区の ID（白 赤、淡い水色 緑、藍中 青、藍濃 黄）。爪の色と後ろの主役波の色の比べ（溶けた爪）。
    // 場面・スクリプト・シェーダー・材質・データは変えない（守るファイルの SHA-256 を前後で比べる）。PC オフスクリーン描画で、HMD 実機ではない。
    public static class PL29Audit
    {
        const string Scene39 = "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity";
        const string ContextRootName = "DS27 背景（美術優先27修正01 のプレハブ）";
        const string CamRoot = "DS27 カメラ";
        const string FlatSeaName = "AF27 参照海面", SkyDomeName = "AF27 空のドーム";
        const int W = 1920, H = 1080;
        const float TStar = 12f;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);
        static readonly Vector3 E = new Vector3(0.6798348938056157f, 0f, 0.733365200404483f);
        static readonly Vector3 Tdir = new Vector3(0.7333652004044829f, 0f, -0.6798348938056156f);
        static readonly Vector4 IdSkyV = new Vector4(0, 1, 1, 1), IdOtherV = new Vector4(0, 0, 0, 1);
        static readonly Dictionary<string, Vector4> IdBoats = new Dictionary<string, Vector4> {
            { "boat_left", new Vector4(0.4f, 0, 0, 1) }, { "boat_mid", new Vector4(0, 0.4f, 0, 1) }, { "boat_fg", new Vector4(0.4f, 0.4f, 0, 1) } };
        static readonly string[] Views = { "painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top" };

        const string RecPkg = "Build/Polish/28/G_p28rec/art_on";
        const string RecWarp = "Build/Polish/28/G_p28rec/timewarp_G_p28rec.json";
        const string RecGwb = "Build/Polish/28/unity/bake_rec/kstar/kstar_a45.gwb";
        const string RecSdf = "Build/Polish/28/unity/bake_rec/bake/af28r01_uvsdf_a45.bin";
        const string RecUvWarp = "Build/Polish/28/unity/bake_rec/bake/af28r01_uvwarp_a45.json";

        static string[] Protected => new[] {
            Scene39, "Assets/GreatWave/Design50/Scenes/DS50_Release.unity", "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs",
            "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs", "Assets/GreatWave/Design34/Scripts/DS34ClawPlayer.cs",
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design38/Shaders/DS38_Outline_Keypose.shader",
            "Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin", "Build/Design/29R01/bake_kp/kstar/kstar_a45.gwb",
            "Build/Design/31/white/hero_pkg/ds27_keypose.json", "Build/Design/28R01F/F_final/timewarp_F_final.json",
            "Build/Design/33/claws/ds33_claw_frames_f32.bin", "Build/Design/31/spray/ds31_spray_frames.bin",
            "Build/Design/38/outlines/unity/prep/ds38_hero_linemask_f32.bin",
            RecPkg + "/ds27_keypose.json", RecWarp, RecGwb, RecSdf, RecUvWarp };

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
            public Material diag;
        }

        [Serializable] class ImgRec { public string view, cond, path, sha256; public float t, tau, az; public Vector3 camPos, camForward, camUp; public float fov; }
        [Serializable] class OriginRec { public float t, tau; public Vector3 originWorld; }
        [Serializable] class Report
        {
            public string unity, device, graphicsApi, colorSpace, utc, scene, sceneSha256, state, noteJa;
            public string heroPackage, heroPackageJsonSha256, heroMeshGwb, heroMeshSha256, heroSdf, heroSdfSha256, heroUvWarp, heroUvWarpSha256, timewarp, timewarpSha256;
            public int heroLayers; public bool heroPosLoUsed; public long heroGpuBytes;
            public Vector3 paintingCamPos, paintingCamForward, paintingCamUp; public float paintingFov, paintingNear, paintingFar;
            public float[] paintVP;
            public string[] views; public float[] times;
            public ImgRec[] images; public OriginRec[] origins;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
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
            foreach (var n in new[] { "painting", "seat", "side_left" }) c.cams[n] = camRoot.Find("DS27 " + n).GetComponent<Camera>();
            c.cams["seat_toward_wave"] = camRoot.Find("DS30 seat_toward_wave").GetComponent<Camera>();
            c.claws = roots.Select(g => g.GetComponentInChildren<DS34ClawPlayer>(true)).First(x => x != null);
            c.clawR = c.claws.GetComponent<MeshRenderer>();
            c.layers = roots.Select(g => g.GetComponentInChildren<DS34LayerSet>(true)).First(x => x != null);
            var parts = roots.SelectMany(g => g.GetComponentsInChildren<DS31InstancedParticles>(true)).ToList();
            c.spray = parts.First(p => p.name == "DS31 spray");
            c.dense = parts.First(p => p.name == "DS39 spray dense");
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
            var sh = Shader.Find("Hidden/GreatWave/Polish29/PL29 Hero Diag");
            if (sh == null) throw new InvalidOperationException("PL29 Hero Diag のシェーダーがありません。");
            c.diag = new Material(sh) { hideFlags = HideFlags.DontSave };
            return c;
        }

        static void Prepare(Ctx c)
        {
            foreach (var so in c.lineComps) so.Attach();
            c.clawLine.Attach();
            c.globals.Apply();
            c.play.Prepare();
            c.spray.Load(); c.claws.Load(); c.dense.Load();
            var hp = c.seaPal.SyncFromHero();
            c.pal.white = hp[0]; c.pal.mizuiro = hp[1]; c.pal.aiMid = hp[2]; c.pal.aiDark = hp[3];
            c.pal.Apply();
            foreach (var so in c.lineComps) so.BindMask();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
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
            string state = Arg(a, "-pl29State") ?? "p28";
            string od = Arg(a, "-pl29Out") ?? ("G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/29/before/" + state);
            var skip = new HashSet<string>((Arg(a, "-pl29Skip") ?? "").Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries));
            var times = (Arg(a, "-pl29Times") ?? "6,9,10.5,12").Split(',').Select(s => double.Parse(s, CultureInfo.InvariantCulture)).ToArray();
            int ttN = int.Parse(Arg(a, "-pl29TtN") ?? "12", CultureInfo.InvariantCulture);
            if (state != "stage9" && state != "p28") throw new ArgumentException("-pl29State は stage9 か p28");
            var before = Protected.ToDictionary(p => p, Sha);
            Directory.CreateDirectory(od);
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), utc = DateTime.UtcNow.ToString("O"), scene = Scene39, sceneSha256 = Sha(Scene39), state = state,
                views = Views, times = times.Select(x => (float)x).ToArray()
            };
            var c = Open();
            if (state == "p28")
            {
                c.hero.packageDir = Arg(a, "-pl29HeroPkg") ?? RecPkg;
                c.hero.meshGwb = Arg(a, "-pl29HeroGwb") ?? RecGwb;
                c.hero.sdfPath = Arg(a, "-pl29HeroSdf") ?? RecSdf;
                c.hero.warpPath = Arg(a, "-pl29HeroUvWarp") ?? RecUvWarp;
                c.play.timewarpPath = Arg(a, "-pl29Timewarp") ?? RecWarp;
            }
            rep.heroPackage = c.hero.packageDir; rep.heroPackageJsonSha256 = Sha(Path.Combine(c.hero.packageDir, "ds27_keypose.json"));
            rep.heroMeshGwb = c.hero.meshGwb; rep.heroMeshSha256 = Sha(c.hero.meshGwb);
            rep.heroSdf = c.hero.sdfPath; rep.heroSdfSha256 = Sha(c.hero.sdfPath);
            rep.heroUvWarp = c.hero.warpPath; rep.heroUvWarpSha256 = Sha(c.hero.warpPath);
            rep.timewarp = c.play.timewarpPath; rep.timewarpSha256 = Sha(c.play.timewarpPath);
            // 原画カメラ（焼き込みと同じ PaintingCam v1。焼き込みの記録 ds29r01_bake_entry.json の位置・向きと比べる）
            var pc = c.cams["painting"];
            float aspPrev = pc.aspect;
            pc.aspect = (float)W / H;
            var vp = pc.projectionMatrix * pc.worldToCameraMatrix;
            pc.aspect = aspPrev;
            rep.paintingCamPos = pc.transform.position; rep.paintingCamForward = pc.transform.forward; rep.paintingCamUp = pc.transform.up;
            rep.paintingFov = pc.fieldOfView; rep.paintingNear = pc.nearClipPlane; rep.paintingFar = pc.farClipPlane;
            rep.paintVP = Enumerable.Range(0, 16).Select(i => vp[i / 4, i % 4]).ToArray();
            c.diag.SetMatrix("_PL29PaintVP", vp);
            var imgs = new List<ImgRec>(); var origins = new List<OriginRec>();
            try
            {
                Prepare(c);
                rep.heroLayers = c.hero.PackageMeta.layers; rep.heroPosLoUsed = c.hero.PosLoFromPackage;
                rep.heroGpuBytes = c.hero.PositionGpuBytes + c.hero.PosLoGpuBytes + c.hero.WhiteGpuBytes;
                foreach (var t in times)
                {
                    string ts = "t" + ((int)Math.Round(t * 10)).ToString("000");
                    Set(c, false, false, false);
                    Seek(c, t, true, false, false);
                    origins.Add(new OriginRec { t = (float)t, tau = (float)c.play.Tau, originWorld = OriginWorld(c) });
                    if (!skip.Contains("views"))
                    {
                        // 爪なし（色・診断）
                        foreach (var v in Views)
                        {
                            CaptureView(c, v, od + "/views/" + v + "_" + ts + "_clawfree.png", t, false, imgs, "clawfree");
                            if (!skip.Contains("diag")) DiagSet(c, v, od + "/diag/" + v + "_" + ts, t, false, imgs, false);
                        }
                        // 爪あり（診断は飛沫なし、色はそのまま＝爪・飛沫・線）
                        Seek(c, t, true, true, false);
                        foreach (var v in Views)
                            if (!skip.Contains("diag")) DiagSet(c, v, od + "/diag/" + v + "_" + ts, t, true, imgs, false);
                        Seek(c, t, true, true, true);
                        foreach (var v in Views)
                            CaptureView(c, v, od + "/views/" + v + "_" + ts + "_asis.png", t, true, imgs, "asis");
                    }
                    if (!skip.Contains("tt"))
                    {
                        // 回り台（主役波だけ。爪あり・飛沫なし・線あり）。中心はその時刻の波の枠の原点 O(t)+(0,9,0)
                        for (int k = 0; k < ttN; k++)
                        {
                            double az = k * 360.0 / ttN;
                            string tn = od + "/tt/" + ts + "_az" + ((int)Math.Round(az)).ToString("000");
                            Seek(c, t, true, true, false);
                            PlaceTurntable(c, az);
                            CaptureView(c, "tt", tn + "_claws.png", t, false, imgs, "tt_claws", true, az);
                            if (!skip.Contains("diag")) { DiagSet(c, "tt", od + "/diag/tt_" + ts + "_az" + ((int)Math.Round(az)).ToString("000"), t, true, imgs, true, az); }
                            Seek(c, t, true, false, false);
                            PlaceTurntable(c, az);
                            if (!skip.Contains("diag")) { DiagSet(c, "tt", od + "/diag/tt_" + ts + "_az" + ((int)Math.Round(az)).ToString("000"), t, false, imgs, true, az); }
                        }
                    }
                }
                // F7-1 の数えの元（-pl29F71 "264,351"）：原画視点を 30 fps のコマ i（t = i/30）ごとに無圧縮の PNG で（爪なし・飛沫なし・線あり）。
                // 仕上げ28 の pl28_f71_count.py --kind pngseq で数える（数え方は段階7確認と同じ）。爪と飛沫は主役波の模様の跳びと別に動くので切る。
                var f71 = Arg(a, "-pl29F71");
                if (f71 != null)
                {
                    var p = f71.Split(',').Select(s => int.Parse(s, CultureInfo.InvariantCulture)).ToArray();
                    // -pl29F71Hz（既定 30。仕上げ29 の作る部で足した）：コマの番号 i の時刻 t = i / Hz
                    double hz = double.Parse(Arg(a, "-pl29F71Hz") ?? "30", CultureInfo.InvariantCulture);
                    Set(c, false, false, false);
                    for (int i = p[0]; i <= p[1]; i++)
                    {
                        double t = i / hz;
                        Seek(c, t, true, false, false);
                        CaptureView(c, "painting", od + "/f71/painting_f" + i.ToString("0000") + ".png", t, false, imgs, "f71");
                    }
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_DS39Gain", 0);
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                c.paper.Teardown();
                foreach (var so in c.lineComps) so.ReleaseMask();
                foreach (var s in c.play.sheets) s.Release();
                c.spray.Release(); c.dense.Release(); c.pal.Release(); c.clawLine.Release(); c.claws.Release();
                foreach (var g in c.temp) if (g != null) UnityEngine.Object.DestroyImmediate(g);
                if (c.diag != null) UnityEngine.Object.DestroyImmediate(c.diag);
            }
            rep.images = imgs.ToArray(); rep.origins = origins.ToArray();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.protectedFiles = Protected.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "Unity の PC オフスクリーン描画（batchmode、Editor の camera.Render、DS39_Paper.unity を開くだけで保存しない）。HMD 実機ではない。" +
                         (state == "p28" ? "主役波のシートと時間曲線だけを仕上げ28 の採用（P28R2rec・G_p28rec・bake_rec）へ替えた（爪・飛沫・線の印・周りの海は合わせ直していない）。" : "差し替えなし（段階9 の状態＝DS50_Release と同じファイル）。");
            File.WriteAllText(od + "/pl29_audit_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("PL29_AUDIT_DONE state=" + state + " images=" + imgs.Count + " seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged);
        }

        static Vector3 OriginWorld(Ctx c) => c.hero.transform.TransformPoint(c.hero.AppliedOrigin);

        static Vector3 Reflect(Vector3 v) => v - 2f * Vector3.Dot(v, E) * E;

        static void PlaceFor(Ctx c, string view)
        {
            var o = OriginWorld(c);
            if (view == "side_left")
                c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0 + (o - c.oStarWorld), c.sideRot0);
            else if (view == "side_right")
            {
                // 左の側面のカメラ（t* の原点からの位置と向き）を、原点を通り E（原画視点から見た横）に垂直な面で鏡に映したもの。波の枠とともに動く。
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
                // 真上：原点の 150 m 上から真下を見る。画面の上が −T（原画視点の観る人が画面の下）、横が E。縦の画角 40°。
                var cam = c.cams["top"];
                cam.transform.SetPositionAndRotation(o + new Vector3(0, 150, 0), Quaternion.LookRotation(Vector3.down, -Tdir));
                cam.fieldOfView = 40f;
            }
        }

        static void RestoreFor(Ctx c, string view)
        {
            if (view == "side_left") c.cams["side_left"].transform.SetPositionAndRotation(c.sidePos0, c.sideRot0);
        }

        // 仕上げ28 の回り台（中心 O+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点 (0,3,−62) の向きから azDeg）。中心はその時刻の原点。
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
            if (view == "tt") hid.AddRange(HideOtherSheets(c));
            return hid;
        }

        static void CaptureView(Ctx c, string view, string path, double t, bool spray, List<ImgRec> imgs, string cond, bool placed = false, double az = double.NaN)
        {
            if (!placed) PlaceFor(c, view);
            var cam = c.cams[view];
            CommandBuffer cb = null;
            if (spray) { cb = new CommandBuffer { name = "PL29 飛沫" }; c.spray.AddTo(cb); cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb); }
            var hid = HideAll(c, view);
            try { Capture(cam, W, H, path); imgs.Add(Rec(view, cond, path, t, c, az)); }
            finally
            {
                if (cb != null) { cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cb.Release(); }
                foreach (var r in hid) r.enabled = true;
                if (!placed) RestoreFor(c, view);
            }
        }

        // 診断の組：claws=false なら uv・px・py・id（爪なし）、claws=true なら uv・id（爪あり）
        static void DiagSet(Ctx c, string view, string stem, double t, bool claws, List<ImgRec> imgs, bool placed, double az = double.NaN)
        {
            if (!placed) PlaceFor(c, view);
            var cam = c.cams[view];
            var hid = HideAll(c, view);
            string s = claws ? "_claws1" : "_claws0";
            try
            {
                RenderDiag(c, cam, stem + "_uv" + s + ".png", 0); imgs.Add(Rec(view, "uv" + s, stem + "_uv" + s + ".png", t, c, az));
                if (!claws)
                {
                    RenderDiag(c, cam, stem + "_px" + s + ".png", 1); imgs.Add(Rec(view, "px" + s, stem + "_px" + s + ".png", t, c, az));
                    RenderDiag(c, cam, stem + "_py" + s + ".png", 2); imgs.Add(Rec(view, "py" + s, stem + "_py" + s + ".png", t, c, az));
                }
                RenderDiag(c, cam, stem + "_id" + s + ".png", -1); imgs.Add(Rec(view, "id" + s, stem + "_id" + s + ".png", t, c, az));
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
            c.spray.ApplyT(t);
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
                || n.StartsWith("GreatWave/Design38/") || n.StartsWith("GreatWave/Design31/");
        }

        // 診断の描画（線なし・MSAA なし・線形 ARGB32・アルファを保つ）。mode ≥ 0 なら主役波の面を PL29 Hero Diag（_PL29Mode = mode）に替える。
        // ほかの物は設計40 の RenderIdsFull と同じく、残す材質（_AF28IdMode = 1 で色区の ID）か ID の平らな色。
        static void RenderDiag(Ctx c, Camera camera, string pngPath, int mode)
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
                    if (!r.enabled) continue;
                    if (r == heroR)
                    {
                        if (mode >= 0)
                        {
                            c.diag.SetFloat("_PL29Mode", mode);
                            saved.Add((r, r.sharedMaterials));
                            r.sharedMaterials = Enumerable.Repeat(c.diag, Math.Max(1, r.sharedMaterials.Length)).ToArray();
                        }
                        continue;
                    }
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
                camera.aspect = (float)W / H; camera.targetTexture = rt; camera.Render();
                Shader.SetGlobalFloat("_AF28IdMode", 0);
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
                foreach (var (r, m) in saved) r.sharedMaterials = m;
                foreach (var m in mats.Values) UnityEngine.Object.DestroyImmediate(m);
                SetLines(c, true);
            }
        }

        static void Capture(Camera camera, int w, int h, string path)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture; float asp = camera.aspect;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = SkyTop;
            camera.allowHDR = false; camera.allowMSAA = true;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rt.Create(); res.Create();
            camera.aspect = (float)w / h; camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, false);
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
        }

        static string Sha(string path)
        {
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
