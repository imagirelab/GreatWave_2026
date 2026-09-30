using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design30;
using GreatWave.Design42;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Design43.EditorTools
{
    // 設計43：船用水面データで 3 隻を小波へ反応させる（PC の batchmode。HMD 実機ではない）。
    //   1) 設計30 の単発再生の場面 DS30_SinglePlayback.unity を開く（保存しない。守るファイル）。座席の船の鉛直の支え（DS30BoatHeave）は外し、
    //      仮の blockout の船と静的な仮置き M1_Revision_LeftSupport は隠す（HideNames）。設計41 のプレハブを子に持つ物理の根（Rigidbody ＋ 設計42 の DS42Buoyancy。表は ds43_boats.py の相似の表）を
    //      3 隻の原画の水平の位置・首の向きに置き、DS43BoatWater（船用水面データ）を読ませる。この状態を DS43_BoatWater.unity として写しで保存する。
    //   2) 物理を手で進める（Physics.simulationMode = Script、dt = 1/120 s）。t = 0 のコマで水を止めたまま 4 s ならし、その後 t 0 → 14 s（t* = 12 s で止まる）。
    //      各段の前に再生器へ同じ時刻を渡し（Seek）、船はその τ の水を読む。30 fps のコマごとに：
    //        ・時刻：再生器の τ、各シートが描いた τ（AppliedTau）、船用水面データが使った τ（TauUsed）
    //        ・船ごと：姿勢、船底のサンプル（浮力点 10 ＋ 船底の 9 × 3 の格子）の位置と、船用水面データの高さと交わりの数
    //        ・座席の目（boat_mid）の位置と、そこの交わり
    //        ・3 枚のシートの頂点を GPU で読み戻す（DS27KeyposeCapture。描いた面そのもの）→ numpy（ds43_measure.py）が表示面の高さを別に求める
    //        ・2 つの視点の JPG（全体・座席の目）
    public static class DS43BoatWaterTest
    {
        const string BaseScene = "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity";
        const string ScenePath = "Assets/GreatWave/Design43/Scenes/DS43_BoatWater.unity";
        const string PrefabPath = "Assets/GreatWave/Design41/Prefabs/DS41_Oshiokuri.prefab";
        const string BoatsJson = "Assets/GreatWave/Design43/Data/ds43_boats.json";
        const string CapturePath = "Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute";
        const string OutRoot = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/43/boatwater/unity";
        const int FW = 960, FH = 540;
        const float Dt = 1f / 120f;
        const int Sub = 4;             // 1 コマ（1/30 s）の物理の段
        const float PreRollS = 4f;
        const float EndS = 14f;
        // 試験の場面だけで隠すもの（原画視点の場面 DS30_SinglePlayback.unity は保存しないので変わらない）：
        //   boat_blockout …… 仮の船（設計41 のプレハブの船に置き換える）
        //   M1_Revision_LeftSupport …… 美術優先の静的な仮置き（左の船の支え。y 0.64〜6.53 m、x −25〜−5、z −15〜−4）。
        //     設計30 は ほかの 3 つ（M1_Revision_RightSlope・M1_ForegroundSwell_Static・M1_ForegroundFoam_Static）を隠したがこれを残した。
        //     自由に浮く boat_left はこの面の下（海面の高さ）に入るので、残すと全体の動画で t ≈ 2〜10 s に見えない（設計43 の確かめで分かった。
        //     船はこの網を読まないので数値は変わらない）。原画の場面では t* の boat_left（根 y 4.82）はこの面の上に乗ったまま（仕上げ30 で置き換える）。
        static readonly HashSet<string> HideNames = new HashSet<string> { "boat_blockout", "M1_Revision_LeftSupport" };

        static string[] Protected => new[] {
            BaseScene, "Assets/GreatWave/Design41/Scenes/DS41_Boats.unity", PrefabPath, "Assets/GreatWave/Design41/Models/ds41_oshiokuri.fbx",
            "Assets/GreatWave/Design42/Scripts/DS42Buoyancy.cs", "Assets/GreatWave/Design42/Scripts/DS42Water.cs", "Assets/GreatWave/Design42/Data/ds42_buoyancy_points.json",
            "Assets/GreatWave/Design42/Scenes/DS42_Buoyancy.unity", "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs", "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs",
            "Assets/GreatWave/Design30/Scripts/DS30BoatHeave.cs", "Build/Design/30/sea/boat_support.json", "Build/Design/30/sea/sea_function.json",
            "Build/Design/30/sea/near/ds27_keypose.json", "Build/Design/30/sea/far/ds27_keypose.json", "Build/Design/28R01F/F_final/art_on/ds27_keypose.json",
            "../Tools/GWContext/seat_v1.json" };

        [Serializable] class BoatRec { public string key, cfg; public float scale, k, massKg, yawDeg, lengthM, beamM, eqDraftMidM; public float[] rootPos, rootRot, eyeLocal, eyeWorldPainting; }
        [Serializable] class BoatsRoot { public BoatRec[] boats; }

        class Boat
        {
            public BoatRec rec; public GameObject root; public Rigidbody rb; public DS42Buoyancy buoy; public Vector3[] samplesLocal; public DS42Buoyancy.Config cfg;
        }

        [Serializable] class Report
        {
            public string unity, device, graphicsApi, utc, scene, sceneSha256, baseScene, noteJa, simulationModeBefore, simulationModeAfter;
            public float dt, preRollS, endS, secondsTotal, secondsPhysicsLoop; public int frames, substeps, rebuilds; public long queries, fallbacks;
            public double rebuildMsMean;
            public string[] sheets; public int[] sheetVertexCounts; public string[] hiddenObjects; public string[] boats;
            public bool protectedUnchanged; public string[] changedFiles; public float[] region;
            public int[] indexedTrianglesLast; public long[] layerReads;
        }

        public static void Run()
        {
            var total = Stopwatch.StartNew();
            var before = Protected.ToDictionary(p => p, Sha);
            AssetDatabase.Refresh();
            Directory.CreateDirectory(OutRoot);
            string frameDir = OutRoot + "/frames";
            if (Directory.Exists(frameDir)) Directory.Delete(frameDir, true);
            Directory.CreateDirectory(frameDir);
            var rep = new Report { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), utc = DateTime.UtcNow.ToString("O"), baseScene = BaseScene, dt = Dt, preRollS = PreRollS, endS = EndS, substeps = Sub };
            var modeBefore = Physics.simulationMode; var gravityBefore = Physics.gravity;
            rep.simulationModeBefore = modeBefore.ToString();
            var writers = new List<BinaryWriter>();
            ComputeBuffer[] bufs = null;
            RenderTexture rtA = null, rtR = null; Texture2D tex = null;
            try
            {
                var scene = EditorSceneManager.OpenScene(BaseScene, OpenSceneMode.Single);
                var play = UnityEngine.Object.FindFirstObjectByType<DS30SinglePlayback>();
                if (play == null) throw new InvalidOperationException("DS30SinglePlayback がありません");
                play.heaves.Clear();
                foreach (var hv in UnityEngine.Object.FindObjectsByType<DS30BoatHeave>(FindObjectsInactive.Include, FindObjectsSortMode.None)) hv.enabled = false;
                var hidden = new List<string>();
                foreach (var tr in UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                    if (HideNames.Contains(tr.name) && tr.gameObject.activeSelf) { tr.gameObject.SetActive(false); hidden.Add(TPath(tr)); }
                if (!hidden.Any(p => p.EndsWith("/M1_Revision_LeftSupport") || p == "M1_Revision_LeftSupport"))
                    throw new InvalidOperationException("M1_Revision_LeftSupport が見つからない（隠せない）");
                rep.hiddenObjects = hidden.ToArray();
                play.Prepare();
                rep.sheets = play.sheets.Select(s => s.sheetName + " " + s.packageDir + " cols " + s.colMin + ".." + s.colMax).ToArray();

                // 船用水面データ
                var boatsRoot = JsonUtility.FromJson<BoatsRoot>(File.ReadAllText(BoatsJson));
                float x0 = float.MaxValue, x1 = float.MinValue, z0 = float.MaxValue, z1 = float.MinValue;
                foreach (var b in boatsRoot.boats) { x0 = Mathf.Min(x0, b.rootPos[0]); x1 = Mathf.Max(x1, b.rootPos[0]); z0 = Mathf.Min(z0, b.rootPos[2]); z1 = Mathf.Max(z1, b.rootPos[2]); }
                const float pad = 16f;
                var region = new Rect(x0 - pad, z0 - pad, (x1 - x0) + 2 * pad, (z1 - z0) + 2 * pad);
                rep.region = new[] { region.xMin, region.yMin, region.xMax, region.yMax };
                var wgo = new GameObject("DS43 船用水面データ（設計30 のうねり＋主役波の下側の一価の面、同じ時計）");
                var water = wgo.AddComponent<DS43BoatWater>();
                water.playback = play; water.region = region; water.cellSize = 1f;
                water.Init(play.sheets);
                play.Seek(0.0);

                // 3 隻（物理の根）
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
                var boats = new List<Boat>();
                foreach (var b in boatsRoot.boats)
                {
                    var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(b.cfg);
                    if (cfgAsset == null) throw new InvalidOperationException("浮力点の表がありません: " + b.cfg);
                    var root = new GameObject("DS43 船 " + b.key + "（物理の根）");
                    var rb = root.AddComponent<Rigidbody>();
                    var buoy = root.AddComponent<DS42Buoyancy>();
                    buoy.pointsJson = cfgAsset; buoy.water = water; buoy.stepInFixedUpdate = false;
                    buoy.Init();
                    var model = (GameObject)PrefabUtility.InstantiatePrefab(prefab, root.transform);
                    model.transform.localPosition = Vector3.zero; model.transform.localRotation = Quaternion.identity; model.transform.localScale = Vector3.one * buoy.Cfg.scale;
                    buoy.ApplyMass();
                    var xz = new Vector3(b.rootPos[0], 0f, b.rootPos[2]);
                    float h = water.HeightAt(xz);
                    root.transform.SetPositionAndRotation(new Vector3(xz.x, h - buoy.Cfg.eqDraftMidM, xz.z), Quaternion.Euler(0f, b.yawDeg, 0f));
                    var bt = new Boat { rec = b, root = root, rb = rb, buoy = buoy, cfg = buoy.Cfg };
                    var sl = new List<Vector3>();
                    for (int k = 0; k < buoy.Cfg.pointCount; k++) sl.Add(buoy.PointLocal(k));
                    for (int i = 0; i < 9; i++) for (int j = 0; j < 3; j++) sl.Add(new Vector3((-0.3f + 0.3f * j) * b.beamM, 0f, (-0.42f + 0.105f * i) * b.lengthM));
                    bt.samplesLocal = sl.ToArray();
                    boats.Add(bt);
                }
                rep.boats = boats.Select(b => b.rec.key + " mass " + b.cfg.massKg.ToString("F1", CultureInfo.InvariantCulture) + " kg scale " + b.cfg.scale.ToString("F6", CultureInfo.InvariantCulture)).ToArray();

                // カメラ
                var camWide = MakeCam("DS43 全体", new Vector3(12f, 45f, -80f), new Vector3(-3f, 0f, -18f), 45f);
                var camSeat = MakeCam("DS43 座席の目", Vector3.zero, Vector3.forward, 80f);
                Directory.CreateDirectory("Assets/GreatWave/Design43/Scenes");
                EditorSceneManager.SaveScene(scene, ScenePath, true);
                rep.scene = ScenePath;

                // GPU の読み戻し
                var cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(CapturePath);
                int kern = cs.FindKernel("DS27Capture");
                var sheets = play.sheets;
                bufs = new ComputeBuffer[sheets.Count];
                var outv = new Vector4[sheets.Count][];
                var cnt = new int[sheets.Count];
                for (int s = 0; s < sheets.Count; s++)
                {
                    cnt[s] = sheets[s].PackageMeta.rows * sheets[s].PackageMeta.cols;
                    bufs[s] = new ComputeBuffer(cnt[s] * 2, 16); outv[s] = new Vector4[cnt[s] * 2];
                    writers.Add(new BinaryWriter(File.Open(OutRoot + "/gpu_" + sheets[s].sheetName + ".f32", FileMode.Create)));
                }
                rep.sheetVertexCounts = cnt;

                Physics.simulationMode = SimulationMode.Script;
                Physics.gravity = new Vector3(0f, -boats[0].cfg.g, 0f);
                foreach (var b in boats) { b.rb.position = b.root.transform.position; b.rb.rotation = b.root.transform.rotation; b.rb.linearVelocity = Vector3.zero; b.rb.angularVelocity = Vector3.zero; }
                Physics.SyncTransforms();

                rtA = new RenderTexture(FW, FH, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                rtR = new RenderTexture(FW, FH, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                rtA.Create(); rtR.Create();
                tex = new Texture2D(FW, FH, TextureFormat.RGB24, false);

                var log = new StringBuilder();
                var hl = new List<float>(16);
                var loop = Stopwatch.StartNew();
                // ならし（水は t = 0 のコマのまま）
                int pre = Mathf.RoundToInt(PreRollS / Dt);
                play.Seek(0.0);
                for (int i = 0; i < pre; i++) { foreach (var b in boats) b.buoy.Step(Dt); Physics.Simulate(Dt); }
                int nFrames = Mathf.RoundToInt(EndS * 30f);
                for (int n = 0; n <= nFrames; n++)
                {
                    if (n > 0)
                        for (int k = 0; k < Sub; k++)
                        {
                            double ts = (n - 1) / 30.0 + k * (double)Dt;
                            play.Seek(ts);
                            foreach (var b in boats) b.buoy.Step(Dt);
                            Physics.Simulate(Dt);
                        }
                    double t = n / 30.0;
                    play.Seek(t);
                    // 記録
                    var L = new StringBuilder();
                    L.Append("{\"n\":").Append(n).Append(",\"t\":").Append(F(t)).Append(",\"tauPlay\":").Append(F(play.Tau)).Append(",\"state\":\"").Append(play.CurrentState).Append("\"");
                    L.Append(",\"tauSheets\":[").Append(string.Join(",", sheets.Select(s => F(s.AppliedTau)))).Append("]");
                    var bodies = new List<string>();
                    foreach (var b in boats)
                    {
                        var tr = b.root.transform;
                        var sb = new StringBuilder();
                        sb.Append("{\"key\":\"").Append(b.rec.key).Append("\",\"pos\":").Append(V(tr.position)).Append(",\"rot\":[").Append(F(tr.rotation.x)).Append(",").Append(F(tr.rotation.y)).Append(",").Append(F(tr.rotation.z)).Append(",").Append(F(tr.rotation.w)).Append("]");
                        sb.Append(",\"wet\":").Append(b.buoy.LastWetPoints).Append(",\"buoyN\":").Append(F(b.buoy.LastBuoyancyN)).Append(",\"vol\":").Append(F(b.buoy.LastVolumeM3));
                        sb.Append(",\"s\":[");
                        for (int i = 0; i < b.samplesLocal.Length; i++)
                        {
                            var pw = tr.TransformPoint(b.samplesLocal[i]);
                            int nh = water.Hits(pw, hl);
                            float h = nh > 0 ? hl[0] : float.NaN;
                            if (i > 0) sb.Append(",");
                            sb.Append("[").Append(F(pw.x)).Append(",").Append(F(pw.y)).Append(",").Append(F(pw.z)).Append(",").Append(F(h)).Append(",").Append(nh).Append("]");
                        }
                        sb.Append("]");
                        if (b.rec.key == "boat_mid")
                        {
                            var el = new Vector3(b.rec.eyeLocal[0], b.rec.eyeLocal[1], b.rec.eyeLocal[2]);
                            var ew = tr.TransformPoint(el);
                            int nh = water.Hits(ew, hl);
                            sb.Append(",\"eye\":").Append(V(ew)).Append(",\"eyeHits\":[").Append(string.Join(",", hl.Select(v => F(v)))).Append("]");
                            // 座席の目のカメラ：波の来る向き（−t）へ
                            var fwd = new Vector3(-0.7334f, 0.12f, 0.6798f);
                            camSeat.transform.SetPositionAndRotation(ew, Quaternion.LookRotation(fwd, Vector3.up));
                        }
                        sb.Append("}");
                        bodies.Add(sb.ToString());
                    }
                    L.Append(",\"tauWater\":").Append(F(water.TauUsed));
                    L.Append(",\"boats\":[").Append(string.Join(",", bodies)).Append("]}");
                    log.AppendLine(L.ToString());
                    // GPU の読み戻し（描いた面）
                    for (int s = 0; s < sheets.Count; s++)
                    {
                        sheets[s].BindCompute(cs, kern);
                        cs.SetBuffer(kern, "_DS27Out", bufs[s]);
                        cs.SetInt("_DS27Count", cnt[s]);
                        cs.Dispatch(kern, (cnt[s] + 63) / 64, 1, 1);
                        bufs[s].GetData(outv[s]);
                        var bw = writers[s];
                        for (int i = 0; i < cnt[s]; i++) { var p = outv[s][2 * i]; bw.Write(p.x); bw.Write(p.y); bw.Write(p.z); }
                    }
                    CaptureJpg(camWide, rtA, rtR, tex, string.Format(CultureInfo.InvariantCulture, "{0}/wide_{1:D4}.jpg", frameDir, n));
                    CaptureJpg(camSeat, rtA, rtR, tex, string.Format(CultureInfo.InvariantCulture, "{0}/seat_{1:D4}.jpg", frameDir, n));
                }
                rep.secondsPhysicsLoop = (float)loop.Elapsed.TotalSeconds;
                rep.frames = nFrames + 1;
                File.WriteAllText(OutRoot + "/ds43_frames.jsonl", log.ToString(), new UTF8Encoding(false));
                rep.rebuilds = water.Rebuilds; rep.queries = water.QueryCount; rep.fallbacks = water.FallbackCount;
                rep.rebuildMsMean = water.Rebuilds > 0 ? water.RebuildMsTotal / water.Rebuilds : 0;
                rep.indexedTrianglesLast = water.readers.Select(r => r.IndexedTriangles).ToArray();
                rep.layerReads = water.readers.Select(r => r.LayerReads).ToArray();
            }
            finally
            {
                foreach (var w in writers) w.Close();
                if (bufs != null) foreach (var b in bufs) b?.Release();
                if (rtA != null) rtA.Release(); if (rtR != null) rtR.Release();
                Physics.simulationMode = modeBefore; Physics.gravity = gravityBefore;
                rep.simulationModeAfter = Physics.simulationMode.ToString();
            }
            rep.sceneSha256 = File.Exists(ScenePath) ? Sha(ScenePath) : "";
            var after = Protected.ToDictionary(p => p, Sha);
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.protectedUnchanged = rep.changedFiles.Length == 0;
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "PC の batchmode（HMD 実機ではない）。物理は Physics.simulationMode = Script で手で進め、終わりに元の設定へ戻した。DS30_SinglePlayback.unity は開いただけで保存していない（写しを DS43_BoatWater.unity に保存）。";
            File.WriteAllText(OutRoot + "/ds43_unity_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS43_DONE seconds=" + rep.secondsTotal.ToString("F1", CultureInfo.InvariantCulture) + " protectedUnchanged=" + rep.protectedUnchanged + " fallbacks=" + rep.fallbacks);
        }

        static string F(double v) => double.IsNaN(v) ? "null" : v.ToString("R", CultureInfo.InvariantCulture);
        static string F(float v) => float.IsNaN(v) ? "null" : v.ToString("R", CultureInfo.InvariantCulture);
        static string V(Vector3 v) => "[" + F(v.x) + "," + F(v.y) + "," + F(v.z) + "]";
        static string TPath(Transform t) => t.parent == null ? t.name : TPath(t.parent) + "/" + t.name;

        static Camera MakeCam(string name, Vector3 pos, Vector3 target, float fov)
        {
            var go = new GameObject(name);
            var cam = go.AddComponent<Camera>();
            cam.fieldOfView = fov; cam.nearClipPlane = 0.1f; cam.farClipPlane = 2000f;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.93f, 0.89f, 0.80f, 1f);
            go.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(target - pos, Vector3.up));
            cam.enabled = false;
            return cam;
        }

        static void CaptureJpg(Camera cam, RenderTexture rt, RenderTexture res, Texture2D tex, string path)
        {
            cam.aspect = (float)FW / FH; cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
            Graphics.Blit(rt, res);
            RenderTexture.active = res; tex.ReadPixels(new Rect(0, 0, FW, FH), 0, 0); tex.Apply(); RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToJPG(90));
        }

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "missing";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
