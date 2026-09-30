using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design42;
using GreatWave.Design44;
using GreatWave.Design45;
using GreatWave.Design46;
using Unity.XR.CoreUtils;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;

namespace GreatWave.Design47.EditorTools
{
    // 設計47：体験の場面 DS47_Flow.unity を作る（PC の Editor の batchmode。HMD 実機ではない）。
    //   1) 設計46 の DS46_Clock.unity（設計41 の原画の場面 ＋ 共通時計 Master ＋ 段の部品 ＋ 出来事の表 ＋ 船用水面データ）を開く（保存しない）。
    //   2) 原画の座席の船「AF27 船 boat_mid」を隠し、代わりに物理の座席の船（BoatSimulationRoot：Rigidbody ＋ 設計42 の DS42Buoyancy ＋ 設計44 の DS44BoatSteer、
    //      設計41 のプレハブを子に縮尺 s で）を置く。船用水面データ（設計43）の関心の範囲を、操船の範囲・原画の位置・ほかの船まで広げる（設計44 の試験と同じ作り方）。
    //   3) 乗客（設計45 の RiderComfortRoot → XR Origin → Camera Offset → HMD Camera、TrackedPoseDriver、L0 既定）を物理の船の兄弟に置く。
    //   4) 進行役 DS47Flow と、観賞の位置から外れた時の覆い（HMD Camera の子、既定は非表示）を置く。ほかの 2 隻は原画の置き方のまま（D47-6）。
    //   5) DS47_Flow.unity として別に保存する。守るファイル（前の番号の場面・部品・表）は前後で SHA-256 を比べる。
    public static class DS47FlowBuild
    {
        public const string Scene46 = "Assets/GreatWave/Design46/Scenes/DS46_Clock.unity";
        public const string Scene47 = "Assets/GreatWave/Design47/Scenes/DS47_Flow.unity";
        public const string FlowJson = "Assets/GreatWave/Design47/Data/ds47_flow.json";
        const string SteerJson = "Assets/GreatWave/Design44/Data/ds44_steer.json";
        const string ComfortJson = "Assets/GreatWave/Design45/Data/ds45_comfort.json";
        const string BoatsJson = "Assets/GreatWave/Design43/Data/ds43_boats.json";
        const string PrefabPath = "Assets/GreatWave/Design41/Prefabs/DS41_Oshiokuri.prefab";
        const string OverlayMat = "Assets/GreatWave/Design47/Materials/DS47_LeaveOverlay.mat";
        public const string BoatRootName = "DS47 座席の船（BoatSimulationRoot・物理の根）";
        public const string PaintingBoatName = "AF27 船 boat_mid";
        public const string FlowName = "DS47 進行（導入→接近→形成→保持→余韻）";

        public static string[] Protected => new[] {
            Scene46, "Assets/GreatWave/Design41/Scenes/DS41_Boats.unity", "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity",
            "Assets/GreatWave/Design30/Scenes/DS30_SinglePlayback.unity", "Assets/GreatWave/Design43/Scenes/DS43_BoatWater.unity",
            "Assets/GreatWave/Design44/Scenes/DS44_Steer.unity", "Assets/GreatWave/Design45/Scenes/DS45_Comfort.unity",
            PrefabPath, "Assets/GreatWave/Design41/Models/ds41_oshiokuri.fbx",
            "Assets/GreatWave/Design42/Scripts/DS42Buoyancy.cs", "Assets/GreatWave/Design43/Scripts/DS43BoatWater.cs",
            "Assets/GreatWave/Design44/Scripts/DS44BoatSteer.cs", "Assets/GreatWave/Design44/Scripts/DS44Trajectory.cs", "Assets/GreatWave/Design44/Scripts/DS44Input.cs",
            "Assets/GreatWave/Design45/Scripts/DS45RiderComfort.cs", "Assets/GreatWave/Design45/Scripts/DS45ComfortSolver.cs",
            "Assets/GreatWave/Design46/Scripts/DS46ClockBus.cs", "Assets/GreatWave/Design46/Scripts/DS46EventTrack.cs", "Assets/GreatWave/ArtFirst/Scripts/GWClock.cs",
            "Assets/GreatWave/Design30/Scripts/DS30SinglePlayback.cs", "Assets/GreatWave/Design30/Scripts/DS30BoatHeave.cs",
            SteerJson, ComfortJson, BoatsJson, "Assets/GreatWave/Design43/Data/ds43_buoyancy_points_boat_mid.json",
            "Build/Design/30/sea/boat_support.json", "Build/Design/28R01F/F_final/timewarp_F_final.json", "../Tools/GWContext/seat_v1.json" };

        [Serializable] class BoatRec { public string key, cfg; public float scale, k, massKg, yawDeg, lengthM, beamM, eqDraftMidM; public float[] rootPos, rootRot, eyeLocal, eyeWorldPainting; }
        [Serializable] class BoatsRoot { public BoatRec[] boats; }

        public static string FileSha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        static string F(double x) => x.ToString("R", CultureInfo.InvariantCulture);

        /// <summary>場面を作って保存する。返り値は記録の JSON の断片。</summary>
        public static string Build()
        {
            AssetDatabase.Refresh();
            var flowAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(FlowJson);
            var flowCfg = DS47FlowConfig.Parse(flowAsset.text);
            var steerAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(SteerJson);
            var steerCfg = DS44SteerConfig.Parse(steerAsset.text);
            var comfortAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(ComfortJson);
            var comfortCfg = DS45ComfortCfg.Parse(comfortAsset.text);
            var boatsRoot = JsonUtility.FromJson<BoatsRoot>(File.ReadAllText(BoatsJson));
            var mid = boatsRoot.boats.First(b => b.key == "boat_mid");
            var fr = new DS44Frame(steerCfg.painting);

            var scene = EditorSceneManager.OpenScene(Scene46, OpenSceneMode.Single);
            var roots = scene.GetRootGameObjects();
            var clock = roots.Select(g => g.GetComponentInChildren<GWClock>(true)).First(x => x != null);
            var bus = roots.Select(g => g.GetComponentInChildren<DS46ClockBus>(true)).First(x => x != null);
            var play = bus.playback;
            var paintingBoat = GameObject.Find(PaintingBoatName);
            if (paintingBoat == null) throw new InvalidOperationException("原画の座席の船がありません: " + PaintingBoatName);
            var heave = roots.SelectMany(g => g.GetComponentsInChildren<DS30BoatHeave>(true)).FirstOrDefault(h => h.boat == paintingBoat.transform);
            if (heave == null) throw new InvalidOperationException("boat_mid の鉛直の支え（DS30BoatHeave）がありません");
            var camRoot = GameObject.Find("DS27 カメラ").transform;
            var paintingCam = camRoot.Find("DS27 painting").GetComponent<Camera>();
            var sb = new StringBuilder();

            // 原画の置き方の根と ds43_boats.json の一致（記録）
            var pr = paintingBoat.transform;
            var rp = new Vector3(mid.rootPos[0], mid.rootPos[1], mid.rootPos[2]);
            var rr = new Quaternion(mid.rootRot[0], mid.rootRot[1], mid.rootRot[2], mid.rootRot[3]);
            sb.Append("\"paintingBoat\":{\"scenePos\":[").Append(F(pr.position.x)).Append(',').Append(F(pr.position.y)).Append(',').Append(F(pr.position.z))
              .Append("],\"sceneRot\":[").Append(F(pr.rotation.x)).Append(',').Append(F(pr.rotation.y)).Append(',').Append(F(pr.rotation.z)).Append(',').Append(F(pr.rotation.w))
              .Append("],\"sceneLossyScale\":[").Append(F(pr.lossyScale.x)).Append(',').Append(F(pr.lossyScale.y)).Append(',').Append(F(pr.lossyScale.z))
              .Append("],\"jsonPos\":[").Append(F(rp.x)).Append(',').Append(F(rp.y)).Append(',').Append(F(rp.z)).Append("],\"posDiffM\":").Append(F((pr.position - rp).magnitude))
              .Append(",\"rotDiffDeg\":").Append(F(Quaternion.Angle(pr.rotation, rr))).Append('}');

            // 1) 時計：引き継ぎまで大波は t = 0、終わりは引き継ぎで決める（DS47Flow も Play の始めに入れる）
            clock.waveStartSeconds = DS47Flow.Far; clock.endSeconds = DS47Flow.Far; clock.startSeconds = 0.0;

            // 2) 船用水面データの関心の範囲（設計44 の試験と同じ：操船の範囲の角・原画の位置・3 隻＋余白 16 m）
            var pts = new List<Vector2>();
            foreach (var uv in new[] { new Vector2(steerCfg.range.uMin, steerCfg.range.vMin), new Vector2(steerCfg.range.uMin, steerCfg.range.vMax), new Vector2(steerCfg.range.uMax, steerCfg.range.vMin), new Vector2(steerCfg.range.uMax, steerCfg.range.vMax), Vector2.zero })
                pts.Add(fr.ToWorld(uv.x, uv.y));
            foreach (var b in boatsRoot.boats) pts.Add(new Vector2(b.rootPos[0], b.rootPos[2]));
            const float pad = 16f;
            float x0 = pts.Min(p => p.x) - pad, x1 = pts.Max(p => p.x) + pad, z0 = pts.Min(p => p.y) - pad, z1 = pts.Max(p => p.y) + pad;
            var water = bus.boatWater;
            water.region = new Rect(x0, z0, x1 - x0, z1 - z0);
            sb.Append(",\"boatWaterRegion\":[").Append(F(x0)).Append(',').Append(F(z0)).Append(',').Append(F(x1)).Append(',').Append(F(z1)).Append(']');

            // 3) 原画の座席の船を隠す（支えは Δ(t) を読むために残す。隠した根も支えが動かすが描かない）
            paintingBoat.SetActive(false);

            // 4) 物理の座席の船
            var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(mid.cfg);
            var root = new GameObject(BoatRootName);
            var rb = root.AddComponent<Rigidbody>();
            rb.interpolation = RigidbodyInterpolation.None;
            var buoy = root.AddComponent<DS42Buoyancy>();
            buoy.pointsJson = cfgAsset; buoy.water = water; buoy.stepInFixedUpdate = true;
            buoy.Init();
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
            var model = (GameObject)PrefabUtility.InstantiatePrefab(prefab, root.transform);
            model.name = "DS41 押送船（boat_mid・乗る船）";
            model.transform.localPosition = Vector3.zero; model.transform.localRotation = Quaternion.identity; model.transform.localScale = Vector3.one * buoy.Cfg.scale;
            buoy.ApplyMass();
            var steer = root.AddComponent<DS44BoatSteer>();
            steer.configJson = steerAsset; steer.buoyancy = buoy; steer.stepInFixedUpdate = false;
            steer.Init();
            var sxz = fr.ToWorld(flowCfg.start.u, flowCfg.start.v);
            root.transform.SetPositionAndRotation(new Vector3(sxz.x, -buoy.Cfg.eqDraftMidM, sxz.y), Quaternion.Euler(0f, fr.yawDeg + flowCfg.start.yawOffsetDeg, 0f));
            sb.Append(",\"seatBoat\":{\"name\":\"").Append(BoatRootName).Append("\",\"massKg\":").Append(F(buoy.Cfg.massKg)).Append(",\"scale\":").Append(F(buoy.Cfg.scale))
              .Append(",\"eqDraftMidM\":").Append(F(buoy.Cfg.eqDraftMidM)).Append(",\"startU\":").Append(F(flowCfg.start.u)).Append(",\"startV\":").Append(F(flowCfg.start.v)).Append('}');

            // 5) 乗客（設計45 の組み立てと同じ）
            var eyeLocal = new Vector3(mid.eyeLocal[0], mid.eyeLocal[1], mid.eyeLocal[2]);
            var rrig = new GameObject("RiderComfortRoot");
            var origin = new GameObject("XR Origin"); origin.transform.SetParent(rrig.transform, false);
            origin.transform.localPosition = new Vector3(0f, -comfortCfg.eyeHeightM, 0f);
            var offset = new GameObject("Camera Offset"); offset.transform.SetParent(origin.transform, false);
            var camGo = new GameObject("HMD Camera"); camGo.transform.SetParent(offset.transform, false);
            var cam = camGo.AddComponent<Camera>();
            cam.fieldOfView = flowCfg.afterglow.pcSeatVfovDeg; cam.nearClipPlane = 0.05f; cam.farClipPlane = 2000f;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color32(249, 232, 196, 255);
            cam.depth = 10f;
            // 描き方を原画視点のカメラ（DS27 painting）とそろえる（HDR なし・MSAA あり）。余韻の終わりの画が原画視点の描画と同じ画素になる（D47-3）
            cam.allowHDR = paintingCam.allowHDR; cam.allowMSAA = paintingCam.allowMSAA;
            camGo.tag = "MainCamera";
            var xr = origin.AddComponent<XROrigin>();
            xr.Origin = origin; xr.CameraFloorOffsetObject = offset; xr.Camera = cam;
            xr.RequestedTrackingOriginMode = XROrigin.TrackingOriginMode.Device;
            xr.CameraYOffset = comfortCfg.eyeHeightM;
            offset.transform.localPosition = new Vector3(0f, comfortCfg.eyeHeightM, 0f);
            var pose = camGo.AddComponent<TrackedPoseDriver>();
            pose.trackingType = TrackedPoseDriver.TrackingType.RotationAndPosition;
            pose.updateType = TrackedPoseDriver.UpdateType.UpdateAndBeforeRender;
            pose.ignoreTrackingState = false;
            pose.positionInput = new InputActionProperty(new InputAction("HMD position", InputActionType.Value, "<XRHMD>/centerEyePosition", expectedControlType: "Vector3"));
            pose.rotationInput = new InputActionProperty(new InputAction("HMD rotation", InputActionType.Value, "<XRHMD>/centerEyeRotation", expectedControlType: "Quaternion"));
            pose.trackingStateInput = new InputActionProperty(new InputAction("HMD tracking state", InputActionType.Value, "<XRHMD>/trackingState", expectedControlType: "Integer"));
            var rc = rrig.AddComponent<DS45RiderComfort>();
            rc.configJson = comfortAsset; rc.boatRoot = root.transform; rc.seatEyeLocal = eyeLocal;
            rc.xrOrigin = origin.transform; rc.cameraOffset = offset.transform; rc.hmdCamera = camGo.transform;
            rc.startLevel = flowCfg.comfort != null ? flowCfg.comfort.defaultLevel : -1; rc.stepInLateUpdate = true; rc.readInput = true;
            rrig.transform.SetPositionAndRotation(root.transform.TransformPoint(eyeLocal), Quaternion.Euler(0f, fr.yawDeg + comfortCfg.seatYawOffsetDeg, 0f));
            // 聞き手（設計49 の音のため）。場面にほかの AudioListener があれば、そちらを切る
            foreach (var al in roots.SelectMany(g => g.GetComponentsInChildren<AudioListener>(true))) al.enabled = false;
            camGo.AddComponent<AudioListener>();

            // 6) 観賞の位置から外れた時の覆い（HMD Camera の子。紙の色の半透明の板と案内の文字。暗転しない）
            Directory.CreateDirectory("Assets/GreatWave/Design47/Materials");
            var L = flowCfg.leave;
            var oc = new Color(L.overlayColor[0], L.overlayColor[1], L.overlayColor[2], L.overlayColor[3]);
            var mat = AssetDatabase.LoadAssetAtPath<Material>(OverlayMat);
            if (mat == null) { mat = new Material(Shader.Find("Sprites/Default")) { color = oc }; AssetDatabase.CreateAsset(mat, OverlayMat); }
            else { mat.color = oc; EditorUtility.SetDirty(mat); }
            var ov = GameObject.CreatePrimitive(PrimitiveType.Quad);
            UnityEngine.Object.DestroyImmediate(ov.GetComponent<Collider>());
            ov.name = "DS47 観賞の位置の案内（外れた時だけ）";
            ov.transform.SetParent(camGo.transform, false);
            ov.transform.localPosition = new Vector3(0f, 0f, 0.12f);
            ov.transform.localScale = new Vector3(0.8f, 0.5f, 1f);
            var ovr = ov.GetComponent<MeshRenderer>(); ovr.sharedMaterial = mat; ovr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; ovr.receiveShadows = false;
            var txt = new GameObject("文字");
            txt.transform.SetParent(ov.transform, false);
            txt.transform.localPosition = new Vector3(0f, 0f, -0.01f);
            txt.transform.localScale = new Vector3(1f / 0.8f, 1f / 0.5f, 1f);
            var tm = txt.AddComponent<TextMesh>();
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            tm.font = font; tm.fontSize = 120; tm.characterSize = 0.0011f; tm.anchor = TextAnchor.MiddleCenter; tm.alignment = TextAlignment.Center;
            tm.color = new Color(L.textColor[0], L.textColor[1], L.textColor[2], L.textColor[3]);
            tm.text = L.messageJa;
            var tr = txt.GetComponent<MeshRenderer>(); tr.sharedMaterial = font.material; tr.sortingOrder = 1;
            ov.SetActive(false);

            // 7) 進行役
            var fgo = new GameObject(FlowName);
            var flow = fgo.AddComponent<DS47Flow>();
            flow.flowJson = flowAsset; flow.clock = clock; flow.bus = bus; flow.buoyancy = buoy; flow.steer = steer; flow.rider = rc;
            flow.hmdCamera = cam; flow.paintingCamera = paintingCam; flow.seatHeave = heave; flow.paintingSeatBoat = paintingBoat.transform;
            flow.paintRootPos = rp; flow.paintRootRot = rr; flow.eqDraftM = buoy.Cfg.eqDraftMidM; flow.leaveOverlay = ov; flow.placeAtStart = true;

            EditorSceneManager.MarkSceneDirty(scene);
            Directory.CreateDirectory(Path.GetDirectoryName(Scene47));
            if (!EditorSceneManager.SaveScene(scene, Scene47, true)) throw new InvalidOperationException("DS47_Flow.unity を保存できません");
            AssetDatabase.SaveAssets();
            // 8) 出発点の水面の高さ：保存した場面を Editor で開いて段を準備し、待機のコマ τ(0) の船用水面データを読む（この状態は保存しない）。
            //    場面を開き直して、進行役・物理の船・乗客をその高さへ置いて、もう一度保存する（Play の始めに船が落ちない・乗客が沈まない）。
            float hStart;
            {
                EditorSceneManager.OpenScene(Scene47, OpenSceneMode.Single);
                var f2 = UnityEngine.Object.FindFirstObjectByType<DS47Flow>();
                f2.bus.Prepare();
                f2.clock.Initialise(false);
                hStart = f2.bus.boatWater.HeightAt(new Vector3(sxz.x, 0f, sxz.y));
                sb.Append(",\"startWater\":{\"tau\":").Append(F(f2.bus.playback.Tau)).Append(",\"heightM\":").Append(F(hStart)).Append(",\"fallbacks\":").Append(f2.bus.boatWater.FallbackCount).Append('}');
            }
            {
                var sc = EditorSceneManager.OpenScene(Scene47, OpenSceneMode.Single);
                var f3 = UnityEngine.Object.FindFirstObjectByType<DS47Flow>();
                f3.startWaterY = hStart;
                var bt = f3.steer.transform;
                bt.position = new Vector3(bt.position.x, hStart - f3.eqDraftM, bt.position.z);
                var rct = f3.rider.transform;
                rct.position = bt.TransformPoint(f3.rider.seatEyeLocal);
                EditorUtility.SetDirty(f3); EditorUtility.SetDirty(bt); EditorUtility.SetDirty(rct);
                EditorSceneManager.MarkSceneDirty(sc);
                if (!EditorSceneManager.SaveScene(sc, Scene47, false)) throw new InvalidOperationException("DS47_Flow.unity を保存し直せません");
            }
            sb.Append(",\"scene\":\"").Append(Scene47).Append("\",\"sceneSha256\":\"").Append(FileSha(Scene47)).Append("\"");
            sb.Append(",\"otherBoatsJa\":\"boat_fg・boat_left は原画の場面のまま（原画の置き方で止めた根。自由な物理にしない。D47-6）\"");
            return sb.ToString();
        }
    }
}
