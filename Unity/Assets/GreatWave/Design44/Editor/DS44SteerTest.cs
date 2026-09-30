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
using GreatWave.Design43;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace GreatWave.Design44.EditorTools
{
    // 設計44：前進・減速・旋回・停止、範囲の外の押し戻し、形成の前の固定の軌道への引き継ぎ（PC の batchmode。HMD 実機ではない）。
    //   1) 設計30 の単発再生の場面 DS30_SinglePlayback.unity を開く（保存しない）。設計43 と同じく座席の船の鉛直の支えを外し、仮の船と静的な仮置きを隠す。
    //      座席の船（boat_mid の表）を操船の範囲の中の出発点に、ほかの 2 隻を原画の水平の位置に置き（設計43 と同じ自由に浮く船）、
    //      座席の船に DS44BoatSteer を付ける。範囲の縁に目印の柱（試験の場面だけ）を立て、写しを DS44_Steer.unity に保存する。
    //   2) Input System の仮想のキーボードとゲームパッドを足し、筋書き（ds44_steer.json の test.segments）どおりに状態を入れる（InputState.Change）。
    //      操船の部品は実際の機器と同じ読み方（DS44Input.Read）で読む。
    //   3) 物理を手で進める（dt = 1/120 s、1 コマ 4 段）。導入と接近（体験の秒 s < 引き継ぎ）は単発再生の待機（t = 0 のコマ）の水の上で操船。
    //      s = handoverS で固定の軌道へ引き継ぎ、軌道の所要 T から形成の始まり s_f = s_h + T − 12 を決め、s ≥ s_f で単発再生の t = s − s_f を進める。
    //      t* で原画の位置に着き、その後 2 s 保つ。
    //   4) 各段の記録（CSV）と各コマの記録（JSONL、カメラの行列）、2 つの視点の JPG（追う視点・真上の地図）。
    public static class DS44SteerTest
    {
        const string BaseScene = "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity";
        const string ScenePath = "Assets/GreatWave/Design44/Scenes/DS44_Steer.unity";
        const string PrefabPath = "Assets/GreatWave/Design41/Prefabs/DS41_Oshiokuri.prefab";
        const string BoatsJson = "Assets/GreatWave/Design43/Data/ds43_boats.json";
        const string SteerJson = "Assets/GreatWave/Design44/Data/ds44_steer.json";
        const string PostMat = "Assets/GreatWave/Design44/Materials/DS44_Post_Red.mat";
        const string OutRoot = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/44/steer/unity";
        const int FW = 960, FH = 540;
        const float Dt = 1f / 120f;
        const int Sub = 4;
        static readonly HashSet<string> HideNames = new HashSet<string> { "boat_blockout", "M1_Revision_LeftSupport" };

        static string[] Protected => new[] {
            BaseScene, "Assets/GreatWave/Design41/Scenes/DS41_Boats.unity", PrefabPath, "Assets/GreatWave/Design41/Models/ds41_oshiokuri.fbx",
            "Assets/GreatWave/Design42/Scripts/DS42Buoyancy.cs", "Assets/GreatWave/Design42/Scripts/DS42Water.cs", "Assets/GreatWave/Design42/Data/ds42_buoyancy_points.json",
            "Assets/GreatWave/Design42/Scenes/DS42_Buoyancy.unity", "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs", "Assets/GreatWave/Design30/Scripts/DS30SheetPlayer.cs",
            "Assets/GreatWave/Design30/Scripts/DS30BoatHeave.cs", "Build/Design/30/sea/boat_support.json", "Build/Design/30/sea/sea_function.json",
            "Build/Design/30/sea/near/ds27_keypose.json", "Build/Design/30/sea/far/ds27_keypose.json", "Build/Design/28R01F/F_final/art_on/ds27_keypose.json",
            "../Tools/GWContext/seat_v1.json",
            "Assets/GreatWave/Design43/Scripts/DS43BoatWater.cs", "Assets/GreatWave/Design43/Scripts/DS43SheetReader.cs", "Assets/GreatWave/Design43/Editor/DS43BoatWaterTest.cs",
            "Assets/GreatWave/Design43/Data/ds43_boats.json", "Assets/GreatWave/Design43/Data/ds43_buoyancy_points_boat_mid.json",
            "Assets/GreatWave/Design43/Data/ds43_buoyancy_points_boat_fg.json", "Assets/GreatWave/Design43/Data/ds43_buoyancy_points_boat_left.json",
            "Assets/GreatWave/Design43/Scenes/DS43_BoatWater.unity", "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity" };

        [Serializable] class BoatRec { public string key, cfg; public float scale, k, massKg, yawDeg, lengthM, beamM, eqDraftMidM; public float[] rootPos, rootRot, eyeLocal, eyeWorldPainting; }
        [Serializable] class BoatsRoot { public BoatRec[] boats; }

        class Boat { public BoatRec rec; public GameObject root; public Rigidbody rb; public DS42Buoyancy buoy; public DS44BoatSteer steer; }

        [Serializable] class Report
        {
            public string unity, device, graphicsApi, utc, scene, sceneSha256, baseScene, noteJa, simulationModeBefore, simulationModeAfter, inputPath, inputCheckJa;
            public float dt, settleS, handoverS, formationStartS, endS, secondsTotal, secondsLoop; public int frames, substeps, rebuilds, posts; public long queries, fallbacks;
            public double rebuildMsMean;
            public string[] hiddenObjects, boats; public float[] region;
            public bool protectedUnchanged; public string[] changedFiles;
            // 引き継ぎ
            public float[] handoverPos, handoverVel; public float handoverYawDeg, handoverYawRateDegPs, handoverSurge, handoverSway;
            public double trajL, trajT, trajLead, trajV0, trajVCap, trajBeta0, trajCRate, trajArcDeg, trajArcR, trajAPlan0; public int trajPoints;
            public float[] trajPathX, trajPathZ;
            public float[] arrivalPos; public float arrivalYawDeg, arrivalSpeed; public float[] paintingPos; public float paintingYawDeg;
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
            var rep = new Report { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), utc = DateTime.UtcNow.ToString("O"), baseScene = BaseScene, dt = Dt, substeps = Sub };
            var modeBefore = Physics.simulationMode; var gravityBefore = Physics.gravity;
            rep.simulationModeBefore = modeBefore.ToString();
            RenderTexture rtA = null, rtR = null; Texture2D tex = null;
            Keyboard kb = null; Gamepad gp = null;
            StreamWriter csv = null, jl = null;
            try
            {
                var steerAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(SteerJson);
                var cfg = DS44SteerConfig.Parse(steerAsset.text);
                var fr = new DS44Frame(cfg.painting);
                var rng = new DS44Range(cfg.range, fr);
                rep.settleS = cfg.test.settleS; rep.handoverS = cfg.test.handoverS;
                rep.paintingPos = new[] { cfg.painting.x, cfg.painting.z }; rep.paintingYawDeg = cfg.painting.yawDeg;

                var scene = EditorSceneManager.OpenScene(BaseScene, OpenSceneMode.Single);
                var play = UnityEngine.Object.FindFirstObjectByType<DS30SinglePlayback>();
                if (play == null) throw new InvalidOperationException("DS30SinglePlayback がありません");
                play.heaves.Clear();
                foreach (var hv in UnityEngine.Object.FindObjectsByType<DS30BoatHeave>(FindObjectsInactive.Include, FindObjectsSortMode.None)) hv.enabled = false;
                var hidden = new List<string>();
                foreach (var tr in UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                    if (HideNames.Contains(tr.name) && tr.gameObject.activeSelf) { tr.gameObject.SetActive(false); hidden.Add(TPath(tr)); }
                rep.hiddenObjects = hidden.ToArray();
                play.autoStartDelay = -1f;   // 待機のまま（形成の始まりはこの試験が決める。設計47 がつなぐ）
                play.Prepare();

                // 船用水面データ（設計43）。関心の範囲 = 操船の範囲＋原画の位置＋ほかの船＋余白
                var boatsRoot = JsonUtility.FromJson<BoatsRoot>(File.ReadAllText(BoatsJson));
                var pts = new List<Vector2>();
                foreach (var uv in new[] { new Vector2(cfg.range.uMin, cfg.range.vMin), new Vector2(cfg.range.uMin, cfg.range.vMax), new Vector2(cfg.range.uMax, cfg.range.vMin), new Vector2(cfg.range.uMax, cfg.range.vMax), Vector2.zero })
                    pts.Add(fr.ToWorld(uv.x, uv.y));
                foreach (var b in boatsRoot.boats) pts.Add(new Vector2(b.rootPos[0], b.rootPos[2]));
                const float pad = 16f;
                float x0 = pts.Min(p => p.x) - pad, x1 = pts.Max(p => p.x) + pad, z0 = pts.Min(p => p.y) - pad, z1 = pts.Max(p => p.y) + pad;
                var region = new Rect(x0, z0, x1 - x0, z1 - z0);
                rep.region = new[] { region.xMin, region.yMin, region.xMax, region.yMax };
                var wgo = new GameObject("DS43 船用水面データ（設計44 の範囲）");
                var water = wgo.AddComponent<DS43BoatWater>();
                water.playback = play; water.region = region; water.cellSize = 1f;
                water.Init(play.sheets);
                play.Seek(-1.0);

                // 船
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
                var boats = new List<Boat>();
                Boat seat = null;
                foreach (var b in boatsRoot.boats)
                {
                    var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(b.cfg);
                    var root = new GameObject("DS44 船 " + b.key + "（物理の根）");
                    var rb = root.AddComponent<Rigidbody>();
                    var buoy = root.AddComponent<DS42Buoyancy>();
                    buoy.pointsJson = cfgAsset; buoy.water = water; buoy.stepInFixedUpdate = false;
                    buoy.Init();
                    var model = (GameObject)PrefabUtility.InstantiatePrefab(prefab, root.transform);
                    model.transform.localPosition = Vector3.zero; model.transform.localRotation = Quaternion.identity; model.transform.localScale = Vector3.one * buoy.Cfg.scale;
                    buoy.ApplyMass();
                    var bt = new Boat { rec = b, root = root, rb = rb, buoy = buoy };
                    Vector2 xz; float yaw;
                    if (b.key == cfg.painting.key)
                    {
                        xz = fr.ToWorld(cfg.test.startU, cfg.test.startV); yaw = cfg.painting.yawDeg + cfg.test.startYawOffsetDeg;
                        var st = root.AddComponent<DS44BoatSteer>();
                        st.configJson = steerAsset; st.buoyancy = buoy; st.stepInFixedUpdate = false;
                        st.Init();
                        bt.steer = st; seat = bt;
                    }
                    else { xz = new Vector2(b.rootPos[0], b.rootPos[2]); yaw = b.yawDeg; }
                    float h = water.HeightAt(new Vector3(xz.x, 0f, xz.y));
                    root.transform.SetPositionAndRotation(new Vector3(xz.x, h - buoy.Cfg.eqDraftMidM, xz.y), Quaternion.Euler(0f, yaw, 0f));
                    boats.Add(bt);
                }
                if (seat == null) throw new InvalidOperationException("座席の船がありません");
                rep.boats = boats.Select(b => b.rec.key + (b.steer != null ? "（操船）" : "（自由に浮く）") + " mass " + b.buoy.Cfg.massKg.ToString("F1", CultureInfo.InvariantCulture)).ToArray();

                // 範囲の目印の柱（試験の場面だけ）
                Directory.CreateDirectory("Assets/GreatWave/Design44/Materials");
                var mat = AssetDatabase.LoadAssetAtPath<Material>(PostMat);
                if (mat == null)
                {
                    mat = new Material(Shader.Find("Unlit/Color")) { color = new Color(0.78f, 0.18f, 0.12f, 1f) };
                    AssetDatabase.CreateAsset(mat, PostMat);
                }
                var postsRoot = new GameObject("DS44 範囲の目印（試験だけ。原画の場面には置かない）");
                int nPost = 0;
                foreach (var uv in RangeOutline(cfg.range, 8f))
                {
                    var p = fr.ToWorld(uv.x, uv.y);
                    var go = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                    UnityEngine.Object.DestroyImmediate(go.GetComponent<Collider>());
                    go.name = "post_" + nPost;
                    go.transform.SetParent(postsRoot.transform, false);
                    go.transform.position = new Vector3(p.x, 1f, p.y);
                    go.transform.localScale = new Vector3(0.5f, 4f, 0.5f);
                    go.GetComponent<MeshRenderer>().sharedMaterial = mat;
                    nPost++;
                }
                rep.posts = nPost;

                // カメラ
                var camChase = MakeCam("DS44 追う視点", Vector3.zero, Vector3.forward, 55f);
                var camMap = MakeCam("DS44 真上の地図", Vector3.zero, Vector3.forward, 50f);
                var sidePos = fr.ToWorld(-40f, -110f); var sideTgt = fr.ToWorld(-35f, 5f);   // 左舷の側から（右舷の側は右の高い波が視野をふさぐ）
                var camSide = MakeCam("DS44 横から見た全体", new Vector3(sidePos.x, 40f, sidePos.y), new Vector3(sideTgt.x, 0f, sideTgt.y), 55f);
                var mc = fr.ToWorld(-30f, 0f);
                camMap.orthographic = true; camMap.orthographicSize = 57f; camMap.nearClipPlane = 1f; camMap.farClipPlane = 1000f;
                camMap.transform.SetPositionAndRotation(new Vector3(mc.x, 300f, mc.y), Quaternion.LookRotation(Vector3.down, new Vector3(fr.f.x, 0f, fr.f.y)));
                Directory.CreateDirectory("Assets/GreatWave/Design44/Scenes");
                EditorSceneManager.SaveScene(scene, ScenePath, true);
                rep.scene = ScenePath;

                // 仮想の機器
                kb = InputSystem.AddDevice<Keyboard>("DS44VirtualKeyboard");
                gp = InputSystem.AddDevice<Gamepad>("DS44VirtualGamepad");
                rep.inputPath = CheckInput(kb, gp, out string chk);
                rep.inputCheckJa = chk;
                bool deviceOk = rep.inputPath != "fallback";

                Physics.simulationMode = SimulationMode.Script;
                Physics.gravity = new Vector3(0f, -seat.buoy.Cfg.g, 0f);
                foreach (var b in boats) { b.rb.position = b.root.transform.position; b.rb.rotation = b.root.transform.rotation; b.rb.linearVelocity = Vector3.zero; b.rb.angularVelocity = Vector3.zero; }
                Physics.SyncTransforms();

                rtA = new RenderTexture(FW, FH, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                rtR = new RenderTexture(FW, FH, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                rtA.Create(); rtR.Create();
                tex = new Texture2D(FW, FH, TextureFormat.RGB24, false);

                csv = new StreamWriter(OutRoot + "/ds44_steps.csv", false, new UTF8Encoding(false));
                csv.WriteLine("i,s,frame,mode,playState,tPlay,tau,x,y,z,yawDeg,qx,qy,qz,qw,vx,vy,vz,wxDeg,wyDeg,wzDeg,surge,sway,thrIn,turnIn,stopIn,src,thF,tuF,d,phi,pushA,thrustA,dragA,wet,tgtX,tgtZ,tgtYaw,tgtYawRate,tgtSpeed,errX,errZ,yawErr,seg");
                jl = new StreamWriter(OutRoot + "/ds44_frames.jsonl", false, new UTF8Encoding(false));

                var loop = Stopwatch.StartNew();
                // ならし（入力なし、水は t = 0 のコマ）
                ApplySegment(kb, gp, null);
                int pre = Mathf.RoundToInt(cfg.test.settleS / Dt);
                for (int i = 0; i < pre; i++)
                {
                    play.Seek(-1.0);
                    foreach (var b in boats) b.buoy.Step(Dt);
                    seat.steer.Step(Dt, default(DS44InputSample));
                    Physics.Simulate(Dt);
                }
                bool handed = false; double sForm = double.PositiveInfinity, sEnd = double.PositiveInfinity;
                int segIdx = -2; long iStep = 0;
                var chase = new Vector3(seat.rb.position.x, 0f, seat.rb.position.z);
                var hl = new List<float>(16);
                int n = 0;
                double handoverS = cfg.test.handoverS;
                while (true)
                {
                    if (n > 0)
                        for (int k = 0; k < Sub; k++)
                        {
                            double s = (n - 1) / 30.0 + k * (double)Dt;
                            int si = SegmentAt(cfg.test.segments, s);
                            if (si != segIdx) { ApplySegment(kb, gp, si >= 0 ? cfg.test.segments[si] : null); segIdx = si; }
                            DS44InputSample inp = deviceOk ? DS44Input.Read(kb, gp, null) : ScriptInput(cfg.test.segments, si);
                            if (!handed && s >= handoverS - 1e-9)
                            {
                                double lead = seat.steer.Handover();
                                handed = true; sForm = s + lead; sEnd = sForm + cfg.traj.formationS + cfg.test.holdAfterStarS;
                                var hp = seat.rb.position; var hv = seat.rb.linearVelocity;
                                rep.handoverPos = new[] { hp.x, hp.y, hp.z }; rep.handoverVel = new[] { hv.x, hv.y, hv.z };
                                rep.handoverYawDeg = seat.steer.HeadingDeg; rep.handoverYawRateDegPs = seat.rb.angularVelocity.y * Mathf.Rad2Deg;
                                var fw = seat.root.transform.forward; var f2 = new Vector2(fw.x, fw.z).normalized;
                                rep.handoverSurge = Vector2.Dot(new Vector2(hv.x, hv.z), f2); rep.handoverSway = Vector2.Dot(new Vector2(hv.x, hv.z), new Vector2(f2.y, -f2.x));
                                var T = seat.steer.Traj;
                                rep.trajL = T.L; rep.trajT = T.T; rep.trajLead = T.Lead; rep.trajV0 = T.V0; rep.trajVCap = T.VCap; rep.trajBeta0 = T.Beta0; rep.trajCRate = T.CRate;
                                rep.trajArcDeg = T.ArcDeg; rep.trajArcR = T.ArcR; rep.trajAPlan0 = T.APlan0; rep.trajPoints = T.S.Length;
                                int stride = Math.Max(1, T.S.Length / 400);
                                var pxl = new List<float>(); var pzl = new List<float>();
                                for (int q = 0; q < T.S.Length; q += stride) { pxl.Add((float)T.X[q]); pzl.Add((float)T.Z[q]); }
                                pxl.Add((float)T.X[T.S.Length - 1]); pzl.Add((float)T.Z[T.S.Length - 1]);
                                rep.trajPathX = pxl.ToArray(); rep.trajPathZ = pzl.ToArray();
                                rep.formationStartS = (float)sForm;
                                UnityEngine.Debug.Log("DS44_HANDOVER s=" + s.ToString("F3", CultureInfo.InvariantCulture) + " lead=" + lead.ToString("F2", CultureInfo.InvariantCulture) + " L=" + T.L.ToString("F2", CultureInfo.InvariantCulture) + " arc=" + T.ArcDeg.ToString("F1", CultureInfo.InvariantCulture));
                            }
                            double tPlay = (handed && s >= sForm) ? s - sForm : -1.0;
                            play.Seek(tPlay);
                            foreach (var b in boats) b.buoy.Step(Dt);
                            seat.steer.Step(Dt, inp);
                            Physics.Simulate(Dt);
                            iStep++;
                            WriteStep(csv, iStep, s + Dt, n, seat, play, tPlay, inp, si);
                        }
                    double sNow = n / 30.0;
                    // カメラ（追う視点：世界に固定した向き、位置だけ船を追う）
                    var bp = seat.rb.position;
                    float a = n == 0 ? 1f : 1f - Mathf.Exp(-(1f / 30f) / 0.8f);
                    chase = Vector3.Lerp(chase, new Vector3(bp.x, 0f, bp.z), a);
                    var fw3 = new Vector3(fr.f.x, 0f, fr.f.y); var sw3 = new Vector3(fr.s.x, 0f, fr.s.y);
                    var camPos = chase - 26f * fw3 - 10f * sw3 + new Vector3(0f, 13f, 0f);   // 左舷の後ろ（形成の間、右舷側は右の高い波が来る）
                    camChase.transform.SetPositionAndRotation(camPos, Quaternion.LookRotation(chase + 8f * fw3 + new Vector3(0f, 1f, 0f) - camPos, Vector3.up));
                    // 記録
                    var L = new StringBuilder();
                    L.Append("{\"n\":").Append(n).Append(",\"s\":").Append(F(sNow)).Append(",\"mode\":\"").Append(seat.steer.CurrentMode).Append("\",\"playState\":\"").Append(play.CurrentState).Append("\",\"tPlay\":").Append(F(play.T)).Append(",\"tau\":").Append(F(play.Tau)).Append(",\"tauWater\":").Append(F(water.TauUsed));
                    L.Append(",\"camChase\":").Append(CamJson(camChase)).Append(",\"camMap\":").Append(CamJson(camMap)).Append(",\"camSide\":").Append(CamJson(camSide));
                    L.Append(",\"boats\":[");
                    for (int bi = 0; bi < boats.Count; bi++)
                    {
                        var b = boats[bi]; var tr = b.root.transform;
                        if (bi > 0) L.Append(",");
                        L.Append("{\"key\":\"").Append(b.rec.key).Append("\",\"pos\":").Append(V(tr.position)).Append(",\"rot\":[").Append(F(tr.rotation.x)).Append(",").Append(F(tr.rotation.y)).Append(",").Append(F(tr.rotation.z)).Append(",").Append(F(tr.rotation.w)).Append("],\"wet\":").Append(b.buoy.LastWetPoints).Append("}");
                    }
                    L.Append("]");
                    var el = new Vector3(seat.rec.eyeLocal[0], seat.rec.eyeLocal[1], seat.rec.eyeLocal[2]);
                    var ew = seat.root.transform.TransformPoint(el);
                    int nh = water.Hits(ew, hl);
                    L.Append(",\"eye\":").Append(V(ew)).Append(",\"eyeHits\":[").Append(string.Join(",", hl.Select(v => F(v)))).Append("]");
                    L.Append(",\"d\":").Append(F(seat.steer.LastD)).Append("}");
                    jl.WriteLine(L.ToString());
                    CaptureJpg(camChase, rtA, rtR, tex, string.Format(CultureInfo.InvariantCulture, "{0}/chase_{1:D4}.jpg", frameDir, n));
                    CaptureJpg(camMap, rtA, rtR, tex, string.Format(CultureInfo.InvariantCulture, "{0}/map_{1:D4}.jpg", frameDir, n));
                    CaptureJpg(camSide, rtA, rtR, tex, string.Format(CultureInfo.InvariantCulture, "{0}/side_{1:D4}.jpg", frameDir, n));
                    if (handed && sNow >= sEnd - 1e-9) break;
                    if (n > 30 * 400) throw new InvalidOperationException("コマ数の上限");
                    n++;
                }
                rep.frames = n + 1;
                rep.endS = n / 30f;
                rep.secondsLoop = (float)loop.Elapsed.TotalSeconds;
                var ap = seat.rb.position; var av = seat.rb.linearVelocity;
                rep.arrivalPos = new[] { ap.x, ap.y, ap.z }; rep.arrivalYawDeg = seat.steer.HeadingDeg; rep.arrivalSpeed = new Vector2(av.x, av.z).magnitude;
                rep.rebuilds = water.Rebuilds; rep.queries = water.QueryCount; rep.fallbacks = water.FallbackCount;
                rep.rebuildMsMean = water.Rebuilds > 0 ? water.RebuildMsTotal / water.Rebuilds : 0;
            }
            finally
            {
                csv?.Close(); jl?.Close();
                if (kb != null) InputSystem.RemoveDevice(kb);
                if (gp != null) InputSystem.RemoveDevice(gp);
                if (rtA != null) rtA.Release(); if (rtR != null) rtR.Release();
                Physics.simulationMode = modeBefore; Physics.gravity = gravityBefore;
                rep.simulationModeAfter = Physics.simulationMode.ToString();
            }
            rep.sceneSha256 = File.Exists(ScenePath) ? Sha(ScenePath) : "";
            var after = Protected.ToDictionary(p => p, Sha);
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.protectedUnchanged = rep.changedFiles.Length == 0;
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "PC の batchmode（HMD 実機ではない）。物理は Physics.simulationMode = Script で手で進め、終わりに元の設定へ戻した。DS30_SinglePlayback.unity は開いただけで保存していない（写しを DS44_Steer.unity に保存）。入力は Input System の仮想の機器（キーボード・ゲームパッド）の状態を InputState.Change で入れ、DS44Input.Read で読んだ。";
            File.WriteAllText(OutRoot + "/ds44_unity_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS44_DONE seconds=" + rep.secondsTotal.ToString("F1", CultureInfo.InvariantCulture) + " frames=" + rep.frames + " protectedUnchanged=" + rep.protectedUnchanged + " input=" + rep.inputPath + " fallbacks=" + rep.fallbacks);
        }

        // ---------------------------------------------------------------- 入力
        static int SegmentAt(DS44Segment[] segs, double s)
        {
            for (int i = 0; i < segs.Length; i++) if (s >= segs[i].s0 - 1e-9 && s < segs[i].s1 - 1e-9) return i;
            return -1;
        }

        static void ApplySegment(Keyboard kb, Gamepad gp, DS44Segment g)
        {
            var keys = new List<Key>();
            if (g != null && g.device == "keyboard")
                foreach (var k in g.keys.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries)) keys.Add((Key)Enum.Parse(typeof(Key), k));
            InputState.Change(kb, new KeyboardState(keys.ToArray()));
            var gs = new GamepadState();
            if (g != null && g.device == "gamepad")
            {
                gs.leftStick = new Vector2(g.stick[0], g.stick[1]);
                gs.rightTrigger = g.trig[0]; gs.leftTrigger = g.trig[1];
                if (g.south != 0) gs = gs.WithButton(GamepadButton.South);
            }
            InputState.Change(gp, gs);
        }

        // 筋書きを機器を通さずに読む（仮想の機器が読めない時の予備。使ったら記録に残す）
        static DS44InputSample ScriptInput(DS44Segment[] segs, int si)
        {
            if (si < 0) return new DS44InputSample { source = "script" };
            var g = segs[si];
            var keys = g.keys.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            float thr = (keys.Contains("W") ? 1f : 0f) - (keys.Contains("S") ? 1f : 0f) + g.stick[1] + g.trig[0] - g.trig[1];
            float turn = (keys.Contains("D") ? 1f : 0f) - (keys.Contains("A") ? 1f : 0f) + g.stick[0];
            return new DS44InputSample { throttle = Mathf.Clamp(thr, -1f, 1f), turn = Mathf.Clamp(turn, -1f, 1f), stop = keys.Contains("Space") || g.south != 0, source = "script" };
        }

        static string CheckInput(Keyboard kb, Gamepad gp, out string note)
        {
            var sb = new StringBuilder();
            InputState.Change(kb, new KeyboardState(Key.W, Key.D));
            var a = DS44Input.Read(kb, gp, null);
            InputState.Change(kb, new KeyboardState());
            var gs = new GamepadState { leftStick = new Vector2(-1f, 0f), rightTrigger = 1f }.WithButton(GamepadButton.South);
            InputState.Change(gp, gs);
            var b = DS44Input.Read(kb, gp, null);
            InputState.Change(gp, new GamepadState());
            var c = DS44Input.Read(kb, gp, null);
            sb.Append("W+D → throttle ").Append(F(a.throttle)).Append(" turn ").Append(F(a.turn)).Append(" (").Append(a.source).Append(")；");
            sb.Append("stick(−1,0)+R2+South → throttle ").Append(F(b.throttle)).Append(" turn ").Append(F(b.turn)).Append(" stop ").Append(b.stop).Append(" (").Append(b.source).Append(")；");
            sb.Append("離す → throttle ").Append(F(c.throttle)).Append(" turn ").Append(F(c.turn)).Append(" stop ").Append(c.stop);
            note = sb.ToString();
            bool ok = a.throttle > 0.99f && a.turn > 0.99f && b.throttle > 0.99f && b.turn < -0.99f && b.stop && c.throttle == 0f && c.turn == 0f && !c.stop;
            return ok ? "InputState.Change" : "fallback";
        }

        // ---------------------------------------------------------------- 記録
        static void WriteStep(StreamWriter w, long i, double s, int n, Boat seat, DS30SinglePlayback play, double tPlay, DS44InputSample inp, int si)
        {
            var st = seat.steer; var tr = seat.root.transform; var rb = seat.rb;
            var p = rb.position; var q = rb.rotation; var v = rb.linearVelocity; var wv = rb.angularVelocity * Mathf.Rad2Deg;
            var tg = st.LastTarget;
            var sb = new StringBuilder(512);
            sb.Append(i).Append(',').Append(F(s)).Append(',').Append(n).Append(',').Append(st.CurrentMode).Append(',').Append(play.CurrentState).Append(',').Append(F(tPlay)).Append(',').Append(F(play.Tau)).Append(',');
            sb.Append(F(p.x)).Append(',').Append(F(p.y)).Append(',').Append(F(p.z)).Append(',').Append(F(st.HeadingDeg)).Append(',');
            sb.Append(F(q.x)).Append(',').Append(F(q.y)).Append(',').Append(F(q.z)).Append(',').Append(F(q.w)).Append(',');
            sb.Append(F(v.x)).Append(',').Append(F(v.y)).Append(',').Append(F(v.z)).Append(',').Append(F(wv.x)).Append(',').Append(F(wv.y)).Append(',').Append(F(wv.z)).Append(',');
            sb.Append(F(st.LastSurge)).Append(',').Append(F(st.LastSway)).Append(',').Append(F(inp.throttle)).Append(',').Append(F(inp.turn)).Append(',').Append(inp.stop ? 1 : 0).Append(',').Append(string.IsNullOrEmpty(inp.source) ? "-" : inp.source).Append(',');
            sb.Append(F(st.LastThF)).Append(',').Append(F(st.LastTuF)).Append(',').Append(F(st.LastD)).Append(',').Append(F(st.LastPhi)).Append(',').Append(F(st.LastPushAccel)).Append(',').Append(F(st.LastThrustAccel)).Append(',').Append(F(st.LastDragAccel)).Append(',').Append(st.LastWet ? 1 : 0).Append(',');
            if (st.Traj != null && st.CurrentMode != DS44BoatSteer.Mode.Steering)
                sb.Append(F(tg.pos.x)).Append(',').Append(F(tg.pos.y)).Append(',').Append(F(tg.yawDeg)).Append(',').Append(F(tg.yawRateDegPs)).Append(',').Append(F(tg.speed)).Append(',').Append(F(st.LastTrackErr.x)).Append(',').Append(F(st.LastTrackErr.y)).Append(',').Append(F(st.LastYawErrDeg));
            else sb.Append(",,,,,,,");
            sb.Append(',').Append(si);
            w.WriteLine(sb.ToString());
        }

        static IEnumerable<Vector2> RangeOutline(DS44RangeCfg R, float spacing)
        {
            // 角を丸めた長方形の縁を spacing ごとに（細かい点の列を弧長で等分）
            float r = R.cornerRadius;
            float u0 = R.uMin, u1 = R.uMax, v0 = R.vMin, v1 = R.vMax;
            var corners = new[] { new Vector3(u1 - r, v1 - r, 0f), new Vector3(u0 + r, v1 - r, 90f), new Vector3(u0 + r, v0 + r, 180f), new Vector3(u1 - r, v0 + r, 270f) };
            var dense = new List<Vector2>();
            foreach (var c in corners)
                for (int k = 0; k <= 32; k++) { float a = (c.z + 90f * k / 32f) * Mathf.Deg2Rad; dense.Add(new Vector2(c.x + r * Mathf.Cos(a), c.y + r * Mathf.Sin(a))); }
            dense.Add(dense[0]);
            var cum = new List<float> { 0f };
            for (int i = 1; i < dense.Count; i++) cum.Add(cum[i - 1] + (dense[i] - dense[i - 1]).magnitude);
            float per = cum[cum.Count - 1];
            int n = Mathf.Max(4, Mathf.RoundToInt(per / spacing));
            var pts = new List<Vector2>();
            int j = 1;
            for (int k = 0; k < n; k++)
            {
                float sPos = per * k / n;
                while (j < cum.Count - 1 && cum[j] < sPos) j++;
                float f = (sPos - cum[j - 1]) / Mathf.Max(cum[j] - cum[j - 1], 1e-6f);
                pts.Add(Vector2.Lerp(dense[j - 1], dense[j], Mathf.Clamp01(f)));
            }
            return pts;
        }

        static string CamJson(Camera c)
        {
            var m = c.worldToCameraMatrix;
            var pm = c.projectionMatrix;
            var sb = new StringBuilder();
            sb.Append("{\"pos\":").Append(V(c.transform.position)).Append(",\"ortho\":").Append(c.orthographic ? "true" : "false").Append(",\"fov\":").Append(F(c.fieldOfView)).Append(",\"size\":").Append(F(c.orthographicSize));
            sb.Append(",\"w2c\":[");
            for (int i = 0; i < 16; i++) { if (i > 0) sb.Append(","); sb.Append(F(m[i / 4, i % 4])); }
            sb.Append("],\"proj\":[");
            for (int i = 0; i < 16; i++) { if (i > 0) sb.Append(","); sb.Append(F(pm[i / 4, i % 4])); }
            sb.Append("]}");
            return sb.ToString();
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
