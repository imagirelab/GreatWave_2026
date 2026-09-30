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
using GreatWave.Design44;
using Unity.XR.CoreUtils;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.InputSystem.XR;

namespace GreatWave.Design45.EditorTools
{
    // 設計45：乗客の揺れの 4 段（PC の batchmode。HMD 実機ではない。H5・H7 の実機と利用者の試遊は保留）。
    //   1) 設計44 の操船の場面 DS44_Steer.unity を開く（保存しない）。物理の船（BoatSimulationRoot）の兄弟として RiderComfortRoot → XR Origin →
    //      Camera Offset → HMD Camera（TrackedPoseDriver）を作り、DS45RiderComfort を付けて、写しを DS45_Comfort.unity に保存する。
    //   2) 比較のため、段を固定した 4 つの乗客（L0〜L3。試験だけ。保存しない）を足す。各 HMD Camera の子に、頭を上げた人の代わりの見上げのカメラ（試験だけ）を付ける。
    //   3) 船の動きは、設計44 の記録（run3 の各段の剛体の状態 ds44_steps.csv、120 Hz。SHA-256 643b376f…）をそのまま入れる（物理は解かない）。
    //      ほかの 2 隻と単発再生の時刻は ds44_frames.jsonl（30 Hz）から。
    //   4) 主の乗客の段は、Input System の仮想のキーボードとゲームパッドの状態（InputState.Change）で筋書きどおりに切り替え、座席リセットも押す。
    //   5) 設計30 の座席の上下（boat_support.json の delta_m、30 Hz、最大 6 m/s²）を、原画の姿勢の船に鉛直に与え、4 段の乗客を計算する（描画なし）。
    //   6) HMD Camera の局所の姿勢が一度も変わらないこと、HMD Camera を参照する部品、兄弟の構造、座席リセットの計算を記録する。
    public static class DS45ComfortTest
    {
        const string BaseScene = "Assets/GreatWave/Design44/Scenes/DS44_Steer.unity";
        const string ScenePath = "Assets/GreatWave/Design45/Scenes/DS45_Comfort.unity";
        const string CfgPath = "Assets/GreatWave/Design45/Data/ds45_comfort.json";
        const string OutRoot = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/45/comfort/unity";
        const float Dt = 1f / 120f;
        const int Sub = 4;

        static string[] Protected => new[] {
            BaseScene, "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity",
            "Assets/GreatWave/Design44/Scripts/DS44BoatSteer.cs", "Assets/GreatWave/Design44/Scripts/DS44Input.cs", "Assets/GreatWave/Design44/Scripts/DS44Trajectory.cs",
            "Assets/GreatWave/Design44/Scripts/DS44SteerConfig.cs", "Assets/GreatWave/Design44/Data/ds44_steer.json", "Assets/GreatWave/Design44/Editor/DS44SteerTest.cs",
            "Assets/GreatWave/Design42/Scripts/DS42Buoyancy.cs", "Assets/GreatWave/Design43/Scripts/DS43BoatWater.cs", "Assets/GreatWave/Design43/Data/ds43_boats.json",
            "Assets/GreatWave/Design41/Prefabs/DS41_Oshiokuri.prefab", "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs", "Assets/GreatWave/Design30/Scripts/DS30BoatHeave.cs",
            "Build/Design/30/sea/boat_support.json", "Build/Design/44/steer/unity/ds44_steps.csv", "Build/Design/44/steer/unity/ds44_frames.jsonl",
            "../Tools/GWContext/seat_v1.json", "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity" };

        [Serializable] class BoatRec { public string key; public float[] rootPos, rootRot, eyeLocal; public float yawDeg; }
        [Serializable] class BoatsRoot { public BoatRec[] boats; }
        [Serializable] class FBoat { public string key; public float[] pos, rot; }
        [Serializable] class FRec { public int n; public double s; public FBoat[] boats; }
        [Serializable] class HFrame { public float t; public float delta_m; }
        [Serializable] class HRoot { public HFrame[] frames; }
        struct Row { public double s, tPlay; public Vector3 p; public Quaternion q; }

        class Rig
        {
            public string label; public int fixedLevel;
            public GameObject root; public DS45RiderComfort comfort;
            public Transform origin, offset, cam; public Camera look;
            public Vector3 cam0Pos; public Quaternion cam0Rot;
        }

        [Serializable] class Report
        {
            public string unity, device, graphicsApi, utc, scene, sceneSha256, baseScene, config, configSha256, noteJa, inputPath, inputCheckJa;
            public string boatStepsSha256, boatFramesSha256, heave30Sha256;
            public float dt, secondsTotal, secondsLoop, endS; public int frames, substeps, rows;
            public bool protectedUnchanged; public string[] changedFiles;
            public string[] levels;
            // 構造の検査
            public bool riderRootIsSceneRoot, boatRootIsSceneRoot, notAncestorEitherWay, chainOk;
            public string riderPath, boatPath, xrOriginPath, cameraOffsetPath, hmdCameraPath;
            public string[] hmdCameraReferencedBy;
            public bool trackedPoseDriverOnHmd; public string xrOriginMode; public float xrOriginCameraYOffset;
            // HMD Camera の局所の姿勢
            public double hmdLocalPosMaxAbsChange, hmdLocalRotMaxAngleDeg; public long hmdChecks;
            // 切り替え
            public string[] switchLog; public int resetCount; public int[] levelTimelineS;
            public double seatReplayMaxDiffM;
            // 座席リセットの計算
            public double recenterMaxPosErrM, recenterMaxYawErrDeg; public int recenterCases;
            public float[] originLocalAfterReset;
            // 設計30 の上下
            public int heaveFrames;
            public int stereoImages;
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
            var rep = new Report { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), utc = DateTime.UtcNow.ToString("O"), baseScene = BaseScene, dt = Dt, substeps = Sub, config = CfgPath, configSha256 = Sha(CfgPath) };
            RenderTexture rtA = null, rtR = null; Texture2D tex = null;
            Keyboard kb = null; Gamepad gp = null;
            StreamWriter csv = null;
            try
            {
                var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(CfgPath);
                var cfg = DS45ComfortCfg.Parse(cfgAsset.text);
                var T = cfg.test;
                rep.levels = cfg.levels.Select(l => l.key + " " + l.nameJa + " kV " + F(l.kV) + " yawFollow " + l.yawFollow + " kTilt " + F(l.kTilt) + " tiltMax " + F(l.tiltMaxDeg)).ToArray();
                rep.boatStepsSha256 = Sha(T.boatStepsCsv); rep.boatFramesSha256 = Sha(T.boatFramesJsonl); rep.heave30Sha256 = Sha(T.heave30Json);

                var scene = EditorSceneManager.OpenScene(BaseScene, OpenSceneMode.Single);
                var play = UnityEngine.Object.FindFirstObjectByType<DS30SinglePlayback>();
                if (play == null) throw new InvalidOperationException("DS30SinglePlayback がありません");
                play.autoStartDelay = -1f;
                play.Prepare();
                play.Seek(-1.0);

                // 船（設計44 の場面の物理の根）
                var boatTf = new Dictionary<string, Transform>();
                Transform seatRoot = null;
                foreach (var b in UnityEngine.Object.FindObjectsByType<DS42Buoyancy>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                {
                    foreach (var key in new[] { "boat_mid", "boat_fg", "boat_left" })
                        if (b.name.Contains(key)) boatTf[key] = b.transform;
                    if (b.GetComponent<DS44BoatSteer>() != null) seatRoot = b.transform;
                }
                if (seatRoot == null || boatTf.Count != 3) throw new InvalidOperationException("設計44 の 3 隻（座席の船は DS44BoatSteer つき）が見つからない：" + boatTf.Count);
                var boatsRoot = JsonUtility.FromJson<BoatsRoot>(File.ReadAllText(T.boatsJson));
                var mid = boatsRoot.boats.First(b => b.key == "boat_mid");
                var eyeLocal = new Vector3(mid.eyeLocal[0], mid.eyeLocal[1], mid.eyeLocal[2]);

                // 主の乗客（場面に保存する）
                var main = MakeRig("RiderComfortRoot", cfgAsset, cfg, seatRoot, eyeLocal, -1, true);
                StructureCheck(rep, main, seatRoot);
                Directory.CreateDirectory("Assets/GreatWave/Design45/Scenes");
                EditorSceneManager.SaveScene(scene, ScenePath, true);
                rep.scene = ScenePath;

                // 比較の 4 段（試験だけ）と見上げのカメラ（試験だけ）
                var rigs = new List<Rig> { main };
                for (int l = 0; l < 4; l++) rigs.Add(MakeRig("DS45 比較 " + cfg.levels[l].key + "（試験だけ。保存しない）", cfgAsset, cfg, seatRoot, eyeLocal, l, false));
                foreach (var r in rigs)
                {
                    var go = new GameObject("DS45 見上げのカメラ（試験だけ。頭を上げた人の代わり）");
                    go.transform.SetParent(r.cam, false);
                    go.transform.localRotation = Quaternion.Euler(-T.lookUpDeg, 0f, 0f);
                    var c = go.AddComponent<Camera>();
                    c.fieldOfView = T.vfovDeg; c.nearClipPlane = 0.05f; c.farClipPlane = 2000f;
                    c.clearFlags = CameraClearFlags.SolidColor; c.backgroundColor = new Color(0.93f, 0.89f, 0.80f, 1f);
                    c.enabled = false;
                    r.look = c;
                    r.cam0Pos = r.cam.localPosition; r.cam0Rot = r.cam.localRotation;
                }

                // 仮想の機器
                kb = InputSystem.AddDevice<Keyboard>("DS45VirtualKeyboard");
                gp = InputSystem.AddDevice<Gamepad>("DS45VirtualGamepad");
                rep.inputPath = CheckInput(kb, gp, out string chk);
                rep.inputCheckJa = chk;
                if (rep.inputPath == "fallback") throw new InvalidOperationException("仮想の機器から段の切り替えを読めない：" + chk);

                // 設計44 の記録
                var rows = ReadRows(T.boatStepsCsv);
                var frames = File.ReadAllLines(T.boatFramesJsonl).Where(l => l.Length > 0).Select(l => JsonUtility.FromJson<FRec>(l)).ToList();
                rep.rows = rows.Count;
                int nFrames = Math.Min(frames.Count, rows.Count / Sub + 1);

                rtA = new RenderTexture(T.width, T.height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                rtR = new RenderTexture(T.width, T.height, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                rtA.Create(); rtR.Create();
                tex = new Texture2D(T.width, T.height, TextureFormat.RGB24, false);

                csv = new StreamWriter(OutRoot + "/ds45_rider.csv", false, new UTF8Encoding(false));
                var hdr = new StringBuilder("i,s,frame,tPlay,level,blendW,kV,kTilt,tiltMax,cmd,resets,bex,bey,bez,bqx,bqy,bqz,bqw,boatYaw,boatTilt");
                foreach (var r in rigs)
                {
                    string p = r.fixedLevel < 0 ? "main" : cfg.levels[r.fixedLevel].key;
                    hdr.Append(",").Append(string.Join(",", new[] { "x", "y", "z", "qx", "qy", "qz", "qw", "yaw", "tilt", "devV", "devH", "cx", "cy", "cz" }.Select(k => p + "_" + k)));
                }
                csv.WriteLine(hdr.ToString());

                var loop = Stopwatch.StartNew();
                var swLog = new List<string>();
                var levelAt = new List<int>();
                double seatDiff = 0; long iStep = 0; int lastSw = -2;
                for (int n = 0; n < nFrames; n++)
                {
                    if (n == 0)
                    {
                        var fb = frames[0].boats.First(b => b.key == "boat_mid");
                        seatRoot.SetPositionAndRotation(V3(fb.pos), Q4(fb.rot));
                        foreach (var r in rigs) r.comfort.Step(0f);
                        CheckCam(rigs, rep);
                    }
                    else
                        for (int k = 0; k < Sub; k++)
                        {
                            var row = rows[(n - 1) * Sub + k];
                            seatRoot.SetPositionAndRotation(row.p, row.q);
                            int si = SwitchAt(T, row.s);
                            if (si != lastSw) { ApplySwitch(kb, gp, si >= 0 ? T.switches[si] : null); lastSw = si; }
                            var cmd = main.comfort.ComfortInput.Read(kb, gp);
                            int lvBefore = main.comfort.Level;
                            main.comfort.Apply(cmd);
                            string cmdTxt = "";
                            if (cmd.level >= 0 || cmd.delta != 0 || cmd.reset)
                            {
                                cmdTxt = (cmd.level >= 0 ? "set" + cmd.level : "") + (cmd.delta != 0 ? "d" + cmd.delta : "") + (cmd.reset ? "reset" : "") + "@" + cmd.source;
                                swLog.Add("s " + F(row.s) + "：" + cmdTxt + "（段 L" + lvBefore + " → L" + main.comfort.Level + "）");
                            }
                            foreach (var r in rigs) r.comfort.Step(Dt);
                            CheckCam(rigs, rep);
                            iStep++;
                            WriteRow(csv, iStep, row, n, main, rigs, cmdTxt, seatRoot, eyeLocal);
                        }
                    levelAt.Add(main.comfort.Level);
                    // ほかの 2 隻と水
                    var fr = frames[n];
                    foreach (var fb in fr.boats)
                    {
                        if (fb.key == "boat_mid") { seatDiff = Math.Max(seatDiff, (V3(fb.pos) - seatRoot.position).magnitude); continue; }
                        if (boatTf.TryGetValue(fb.key, out var tf)) tf.SetPositionAndRotation(V3(fb.pos), Q4(fb.rot));
                    }
                    double tPlay = n == 0 ? -1.0 : rows[n * Sub - 1].tPlay;
                    play.Seek(tPlay);
                    foreach (var r in rigs)
                        CaptureJpg(r.look, rtA, rtR, tex, T.width, T.height, string.Format(CultureInfo.InvariantCulture, "{0}/{1}_{2:D4}.jpg", frameDir, r.fixedLevel < 0 ? "main" : cfg.levels[r.fixedLevel].key, n));
                    // Mock の両目（試験だけ）：見上げのカメラ（HMD Camera の子。試験だけ）を右向きに ±ipd/2 ずらして描き、元へ戻す。HMD Camera の局所の姿勢は触らない
                    if (T.stereoS != null && T.stereoS.Any(sx => Math.Min(nFrames - 1, Mathf.RoundToInt(sx * 30f)) == n))
                        foreach (var r in rigs.Where(x => x.fixedLevel >= 0))
                        {
                            var lp = r.look.transform.localPosition;
                            foreach (var eye in new[] { -1, 1 })
                            {
                                r.look.transform.localPosition = lp + r.look.transform.localRotation * new Vector3(eye * T.ipdM * 0.5f, 0f, 0f);
                                CaptureJpg(r.look, rtA, rtR, tex, T.width, T.height, string.Format(CultureInfo.InvariantCulture, "{0}/stereo_{1}_{2:D4}_{3}.jpg", frameDir, cfg.levels[r.fixedLevel].key, n, eye < 0 ? "L" : "R"));
                            }
                            r.look.transform.localPosition = lp;
                            rep.stereoImages += 2;
                        }
                }
                rep.frames = nFrames;
                rep.endS = (nFrames - 1) / 30f;
                rep.secondsLoop = (float)loop.Elapsed.TotalSeconds;
                rep.switchLog = swLog.ToArray();
                rep.resetCount = main.comfort.ResetCount;
                rep.seatReplayMaxDiffM = seatDiff;
                rep.levelTimelineS = Enumerable.Range(0, (int)(rep.endS) + 1).Select(sec => levelAt[Math.Min(levelAt.Count - 1, sec * 30)]).ToArray();
                rep.originLocalAfterReset = new[] { main.origin.localPosition.x, main.origin.localPosition.y, main.origin.localPosition.z, main.origin.localRotation.x, main.origin.localRotation.y, main.origin.localRotation.z, main.origin.localRotation.w };

                // 座席リセットの計算（頭部追跡の値を仮に与えて、XR Origin の局所の姿勢だけで頭が座席の目と正面へ来るか）
                RecenterCheck(rep, cfg);

                // 設計30 の座席の上下を 4 段へ
                HeaveCheck(rep, cfg, mid, eyeLocal);
            }
            finally
            {
                csv?.Close();
                if (kb != null) InputSystem.RemoveDevice(kb);
                if (gp != null) InputSystem.RemoveDevice(gp);
                if (rtA != null) rtA.Release(); if (rtR != null) rtR.Release();
            }
            rep.sceneSha256 = File.Exists(ScenePath) ? Sha(ScenePath) : "";
            var after = Protected.ToDictionary(p => p, Sha);
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.protectedUnchanged = rep.changedFiles.Length == 0;
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "PC の batchmode（HMD 実機ではない）。Play モードではないので、TrackedPoseDriver も DS45RiderComfort の LateUpdate も動かない。DS45RiderComfort の Step・Apply・ResetSeat を外から呼んだ。船は設計44 の記録を入れただけで、物理は解いていない。DS44_Steer.unity は開いただけで保存していない（写しを DS45_Comfort.unity に保存）。";
            File.WriteAllText(OutRoot + "/ds45_unity_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS45_DONE seconds=" + rep.secondsTotal.ToString("F1", CultureInfo.InvariantCulture) + " frames=" + rep.frames + " protectedUnchanged=" + rep.protectedUnchanged + " hmdPos=" + rep.hmdLocalPosMaxAbsChange + " hmdRot=" + rep.hmdLocalRotMaxAngleDeg + " resets=" + rep.resetCount);
        }

        // ---------------------------------------------------------------- 乗客の組み立て
        static Rig MakeRig(string name, TextAsset cfgAsset, DS45ComfortCfg cfg, Transform boat, Vector3 eyeLocal, int level, bool forScene)
        {
            var root = new GameObject(name);   // 親なし（物理の船の兄弟）
            var origin = new GameObject(forScene ? "XR Origin" : "XR Origin（比較）");
            origin.transform.SetParent(root.transform, false);
            origin.transform.localPosition = new Vector3(0f, -cfg.eyeHeightM, 0f);
            var offset = new GameObject("Camera Offset");
            offset.transform.SetParent(origin.transform, false);
            var camGo = new GameObject(forScene ? "HMD Camera" : "HMD Camera（比較）");
            camGo.transform.SetParent(offset.transform, false);
            var cam = camGo.AddComponent<Camera>();
            cam.fieldOfView = cfg.test.vfovDeg; cam.nearClipPlane = 0.05f; cam.farClipPlane = 2000f;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.93f, 0.89f, 0.80f, 1f);
            cam.enabled = forScene;
            if (!forScene) cam.tag = "Untagged";
            var xr = origin.AddComponent<XROrigin>();
            xr.Origin = origin; xr.CameraFloorOffsetObject = offset; xr.Camera = cam;
            xr.RequestedTrackingOriginMode = XROrigin.TrackingOriginMode.Device;
            xr.CameraYOffset = cfg.eyeHeightM;
            offset.transform.localPosition = new Vector3(0f, cfg.eyeHeightM, 0f);
            if (forScene)
            {
                var pose = camGo.AddComponent<TrackedPoseDriver>();
                pose.trackingType = TrackedPoseDriver.TrackingType.RotationAndPosition;
                pose.updateType = TrackedPoseDriver.UpdateType.UpdateAndBeforeRender;
                pose.ignoreTrackingState = false;
                pose.positionInput = new InputActionProperty(new InputAction("HMD position", InputActionType.Value, "<XRHMD>/centerEyePosition", expectedControlType: "Vector3"));
                pose.rotationInput = new InputActionProperty(new InputAction("HMD rotation", InputActionType.Value, "<XRHMD>/centerEyeRotation", expectedControlType: "Quaternion"));
                pose.trackingStateInput = new InputActionProperty(new InputAction("HMD tracking state", InputActionType.Value, "<XRHMD>/trackingState", expectedControlType: "Integer"));
            }
            var rc = root.AddComponent<DS45RiderComfort>();
            rc.configJson = cfgAsset; rc.boatRoot = boat; rc.seatEyeLocal = eyeLocal;
            rc.xrOrigin = origin.transform; rc.cameraOffset = offset.transform; rc.hmdCamera = camGo.transform;
            rc.startLevel = level; rc.stepInLateUpdate = forScene; rc.readInput = forScene;
            rc.Init();
            return new Rig { label = name, fixedLevel = level, root = root, comfort = rc, origin = origin.transform, offset = offset.transform, cam = camGo.transform };
        }

        static void StructureCheck(Report rep, Rig main, Transform boat)
        {
            rep.riderRootIsSceneRoot = main.root.transform.parent == null;
            rep.boatRootIsSceneRoot = boat.parent == null;
            rep.notAncestorEitherWay = !boat.IsChildOf(main.root.transform) && !main.root.transform.IsChildOf(boat);
            rep.chainOk = main.origin.parent == main.root.transform && main.offset.parent == main.origin && main.cam.parent == main.offset;
            rep.riderPath = TPath(main.root.transform); rep.boatPath = TPath(boat); rep.xrOriginPath = TPath(main.origin); rep.cameraOffsetPath = TPath(main.offset); rep.hmdCameraPath = TPath(main.cam);
            rep.trackedPoseDriverOnHmd = main.cam.GetComponent<TrackedPoseDriver>() != null;
            var xr = main.origin.GetComponent<XROrigin>();
            rep.xrOriginMode = xr.RequestedTrackingOriginMode.ToString(); rep.xrOriginCameraYOffset = xr.CameraYOffset;
            // 場面のすべての部品のうち、HMD Camera（GameObject・Transform・Camera）を参照するもの
            var camGo = main.cam.gameObject;
            var refs = new List<string>();
            foreach (var go in main.root.scene.GetRootGameObjects())
                foreach (var c in go.GetComponentsInChildren<Component>(true))
                {
                    if (c == null || c is Transform) continue;
                    var so = new SerializedObject(c);
                    var it = so.GetIterator();
                    bool enter = true;
                    while (it.Next(enter))
                    {
                        enter = it.propertyType == SerializedPropertyType.Generic && !(it.isArray && it.arraySize > 64);
                        if (it.propertyType != SerializedPropertyType.ObjectReference) continue;
                        var o = it.objectReferenceValue;
                        if (o == null) continue;
                        bool hit = o == camGo || (o is Component oc && oc.gameObject == camGo);
                        if (hit && !(c.gameObject == camGo && it.propertyPath == "m_GameObject")) refs.Add(c.GetType().Name + "." + it.propertyPath + "（" + TPath(c.transform) + "）");
                    }
                }
            rep.hmdCameraReferencedBy = refs.ToArray();
        }

        static void CheckCam(List<Rig> rigs, Report rep)
        {
            foreach (var r in rigs)
            {
                var dp = r.cam.localPosition - r.cam0Pos;
                double m = Math.Max(Math.Abs(dp.x), Math.Max(Math.Abs(dp.y), Math.Abs(dp.z)));
                rep.hmdLocalPosMaxAbsChange = Math.Max(rep.hmdLocalPosMaxAbsChange, m);
                var q = r.cam.localRotation; var q0 = r.cam0Rot;
                bool same = q.x == q0.x && q.y == q0.y && q.z == q0.z && q.w == q0.w;
                if (!same) rep.hmdLocalRotMaxAngleDeg = Math.Max(rep.hmdLocalRotMaxAngleDeg, Math.Max(1e-9, Quaternion.Angle(q, q0)));
                rep.hmdChecks++;
            }
        }

        static void RecenterCheck(Report rep, DS45ComfortCfg cfg)
        {
            var heads = new[] {
                (Vector3.zero, Quaternion.identity),
                (new Vector3(0.12f, 0.05f, -0.08f), Quaternion.Euler(10f, 25f, 0f)),
                (new Vector3(-0.2f, -0.1f, 0.15f), Quaternion.Euler(-5f, -70f, 5f)),
                (new Vector3(0.05f, 0.2f, 0.3f), Quaternion.Euler(20f, 170f, -8f)) };
            var offPos = new Vector3(0f, cfg.eyeHeightM, 0f); var offRot = Quaternion.identity;
            double pe = 0, ye = 0;
            foreach (var (hp, hr) in heads)
            {
                var o = DS45ComfortSolver.RecenterOrigin(offPos, offRot, hp, hr);
                var headInRoot = o.pos + o.rot * (offPos + offRot * hp);
                var f = o.rot * offRot * hr * Vector3.forward;
                pe = Math.Max(pe, headInRoot.magnitude);
                ye = Math.Max(ye, Math.Abs(Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg));
            }
            rep.recenterMaxPosErrM = pe; rep.recenterMaxYawErrDeg = ye; rep.recenterCases = heads.Length;
        }

        static void HeaveCheck(Report rep, DS45ComfortCfg cfg, BoatRec mid, Vector3 eyeLocal)
        {
            var hr = JsonUtility.FromJson<HRoot>(File.ReadAllText(cfg.test.heave30Json));
            var go = new GameObject("DS45 設計30 の座席の上下（試験だけ）");
            var p0 = new Vector3(mid.rootPos[0], mid.rootPos[1], mid.rootPos[2]);
            var q0 = new Quaternion(mid.rootRot[0], mid.rootRot[1], mid.rootRot[2], mid.rootRot[3]);
            var sol = Enumerable.Range(0, 4).Select(l => new DS45ComfortSolver(cfg, l)).ToArray();
            using (var w = new StreamWriter(OutRoot + "/ds45_heave30.csv", false, new UTF8Encoding(false)))
            {
                w.WriteLine("t,delta,bex,bey,bez," + string.Join(",", cfg.levels.Select(l => l.key + "_x," + l.key + "_y," + l.key + "_z," + l.key + "_tilt," + l.key + "_yaw")));
                float prevT = float.NaN;
                foreach (var f in hr.frames)
                {
                    go.transform.SetPositionAndRotation(p0 + new Vector3(0f, f.delta_m, 0f), q0);
                    var eye = go.transform.TransformPoint(eyeLocal);
                    float dt = float.IsNaN(prevT) ? 0f : f.t - prevT;
                    prevT = f.t;
                    var sb = new StringBuilder();
                    sb.Append(F(f.t)).Append(',').Append(F(f.delta_m)).Append(',').Append(F(eye.x)).Append(',').Append(F(eye.y)).Append(',').Append(F(eye.z));
                    foreach (var s in sol)
                    {
                        var p = s.Step(dt, eye, q0);
                        sb.Append(',').Append(F(p.pos.x)).Append(',').Append(F(p.pos.y)).Append(',').Append(F(p.pos.z)).Append(',').Append(F(s.LastTiltDeg)).Append(',').Append(F(s.LastYawDeg));
                    }
                    w.WriteLine(sb.ToString());
                }
            }
            rep.heaveFrames = hr.frames.Length;
            UnityEngine.Object.DestroyImmediate(go);
        }

        // ---------------------------------------------------------------- 入力
        static int SwitchAt(DS45TestCfg T, double s)
        {
            for (int i = 0; i < T.switches.Length; i++) if (s >= T.switches[i].s - 1e-9 && s < T.switches[i].s + T.holdS - 1e-9) return i;
            return -1;
        }

        static void ApplySwitch(Keyboard kb, Gamepad gp, DS45Switch w)
        {
            var keys = new List<Key>();
            if (w != null && w.device == "keyboard") keys.Add((Key)Enum.Parse(typeof(Key), w.key));
            InputState.Change(kb, new KeyboardState(keys.ToArray()));
            var gs = new GamepadState();
            if (w != null && w.device == "gamepad") gs = gs.WithButton((GamepadButton)Enum.Parse(typeof(GamepadButton), w.button));
            InputState.Change(gp, gs);
        }

        static string CheckInput(Keyboard kb, Gamepad gp, out string note)
        {
            var inp = new DS45ComfortInput();
            InputState.Change(kb, new KeyboardState(Key.Digit3));
            var a = inp.Read(kb, gp);
            var a2 = inp.Read(kb, gp);   // 押したまま：2 回目は出ない
            InputState.Change(kb, new KeyboardState());
            InputState.Change(gp, new GamepadState().WithButton(GamepadButton.DpadUp).WithButton(GamepadButton.Select));
            var b = inp.Read(kb, gp);
            InputState.Change(gp, new GamepadState());
            var c = inp.Read(kb, gp);
            note = "Digit3 → level " + a.level + " (" + a.source + ")、押したまま → level " + a2.level + "、DpadUp+Select → delta " + b.delta + " reset " + b.reset + " (" + b.source + ")、離す → level " + c.level + " delta " + c.delta + " reset " + c.reset;
            bool ok = a.level == 2 && a2.level == -1 && b.delta == 1 && b.reset && c.level == -1 && c.delta == 0 && !c.reset;
            return ok ? "InputState.Change" : "fallback";
        }

        // ---------------------------------------------------------------- 記録
        static List<Row> ReadRows(string path)
        {
            var lines = File.ReadAllLines(path);
            var h = lines[0].Split(',');
            int I(string k) => Array.IndexOf(h, k);
            int iS = I("s"), iT = I("tPlay"), ix = I("x"), iy = I("y"), iz = I("z"), iqx = I("qx"), iqy = I("qy"), iqz = I("qz"), iqw = I("qw");
            var rows = new List<Row>(lines.Length);
            for (int i = 1; i < lines.Length; i++)
            {
                if (lines[i].Length == 0) continue;
                var c = lines[i].Split(',');
                rows.Add(new Row { s = D(c[iS]), tPlay = D(c[iT]), p = new Vector3((float)D(c[ix]), (float)D(c[iy]), (float)D(c[iz])), q = new Quaternion((float)D(c[iqx]), (float)D(c[iqy]), (float)D(c[iqz]), (float)D(c[iqw])) });
            }
            return rows;
        }

        static void WriteRow(StreamWriter w, long i, Row row, int n, Rig main, List<Rig> rigs, string cmd, Transform boat, Vector3 eyeLocal)
        {
            var s = main.comfort.Solver;
            var be = boat.TransformPoint(eyeLocal); var bq = boat.rotation;
            var sb = new StringBuilder(1024);
            sb.Append(i).Append(',').Append(F(row.s)).Append(',').Append(n).Append(',').Append(F(row.tPlay)).Append(',').Append(s.Level).Append(',').Append(F(s.BlendW)).Append(',');
            sb.Append(F(s.LastKV)).Append(',').Append(F(s.LastKTilt)).Append(',').Append(F(s.LastTiltMax)).Append(',').Append(cmd).Append(',').Append(main.comfort.ResetCount).Append(',');
            sb.Append(F(be.x)).Append(',').Append(F(be.y)).Append(',').Append(F(be.z)).Append(',').Append(F(bq.x)).Append(',').Append(F(bq.y)).Append(',').Append(F(bq.z)).Append(',').Append(F(bq.w)).Append(',');
            sb.Append(F(s.LastBoatYawDeg)).Append(',').Append(F(s.LastBoatTiltDeg));
            foreach (var r in rigs)
            {
                var t = r.root.transform; var p = t.position; var q = t.rotation; var so = r.comfort.Solver; var cw = r.cam.position;
                sb.Append(',').Append(F(p.x)).Append(',').Append(F(p.y)).Append(',').Append(F(p.z)).Append(',').Append(F(q.x)).Append(',').Append(F(q.y)).Append(',').Append(F(q.z)).Append(',').Append(F(q.w));
                sb.Append(',').Append(F(so.LastYawDeg)).Append(',').Append(F(so.LastTiltDeg)).Append(',').Append(F(so.LastDevV)).Append(',').Append(F(so.LastDevH));
                sb.Append(',').Append(F(cw.x)).Append(',').Append(F(cw.y)).Append(',').Append(F(cw.z));
            }
            w.WriteLine(sb.ToString());
        }

        static void CaptureJpg(Camera cam, RenderTexture rt, RenderTexture res, Texture2D tex, int W, int H, string path)
        {
            cam.aspect = (float)W / H; cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
            Graphics.Blit(rt, res);
            RenderTexture.active = res; tex.ReadPixels(new Rect(0, 0, W, H), 0, 0); tex.Apply(); RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToJPG(90));
        }

        static double D(string s) => double.Parse(s, NumberStyles.Float, CultureInfo.InvariantCulture);
        static Vector3 V3(float[] a) => new Vector3(a[0], a[1], a[2]);
        static Quaternion Q4(float[] a) => new Quaternion(a[0], a[1], a[2], a[3]);
        static string F(double v) => double.IsNaN(v) ? "null" : v.ToString("R", CultureInfo.InvariantCulture);
        static string F(float v) => float.IsNaN(v) ? "null" : v.ToString("R", CultureInfo.InvariantCulture);
        static string TPath(Transform t) => t.parent == null ? t.name : TPath(t.parent) + "/" + t.name;

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "missing";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
