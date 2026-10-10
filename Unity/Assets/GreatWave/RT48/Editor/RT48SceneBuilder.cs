using System;
using System.IO;
using Unity.XR.CoreUtils;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace GreatWave.RT48.EditorTools
{
    // RT48：新しい場面 Assets/GreatWave/RT48/Scenes/RT48_Playback.unity と材質を作る（計画 §3.1）。
    // 既存の場面・資産は開かず、変えない（作るのは Assets/GreatWave/RT48/ の下だけ）。形（掃いた面・海・船）は実行の時に作る。
    //   batchmode：-executeMethod GreatWave.RT48.EditorTools.RT48SceneBuilder.BuildAndExit
    public static class RT48SceneBuilder
    {
        public const string Root = "Assets/GreatWave/RT48";
        public const string ScenePath = Root + "/Scenes/RT48_Playback.unity";
        public const string MatDir = Root + "/Materials";
        public const string ShaderDir = Root + "/Shaders";

        public static string BuildRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "../Build/RT48"));
        public static string BakeRoot => Path.Combine(BuildRoot, "bake");          // u_bakeio.py の形（合成の試し）
        public static string DataRoot => Path.Combine(BuildRoot, "data");          // r_bake.py の形（粗い元・細かい元）
        public static string UnityOut => Path.Combine(BuildRoot, "unity");

        public static void BuildAndExit()
        {
            int code = 0;
            try { Build(); }
            catch (Exception e) { Debug.LogError("RT48_SCENE_EXCEPTION " + e); code = 1; }
            EditorApplication.Exit(code);
        }

        public static void Build()
        {
            EnsureFolder(Root, "Scenes");
            EnsureFolder(Root, "Materials");
            var water = Shader.Find("GreatWave/RT48/Water");
            var sky = Shader.Find("GreatWave/RT48/Sky");
            var overlay = Shader.Find("GreatWave/RT48/Overlay");
            var cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(ShaderDir + "/RT48DecodeCheck.compute");
            if (water == null || sky == null || overlay == null || cs == null) throw new InvalidOperationException("RT48 のシェーダーが見つかりません（コンパイルの誤り？）");

            var mSweep = Mat("RT48_WaterSweep", water, m => { m.EnableKeyword("RT48_SWEEP"); });
            var mLoops = Mat("RT48_WaterLoops", water, m => { m.DisableKeyword("RT48_SWEEP"); });
            var mSea = Mat("RT48_Sea", water, m => { m.DisableKeyword("RT48_SWEEP"); });
            var mBoat = Mat("RT48_Boat", water, m =>
            {
                m.DisableKeyword("RT48_SWEEP");
                m.SetColor("_Albedo", new Color(0.20f, 0.11f, 0.05f, 1f));
                m.SetFloat("_F0", 0.04f); m.SetFloat("_Roughness", 0.5f); m.SetFloat("_SpecScale", 0.3f); m.SetFloat("_Diffuse", 1.0f); m.SetFloat("_BackDim", 0.6f);
            });
            var mSky = Mat("RT48_Sky", sky, m => { });
            var mOverlay = Mat("RT48_Overlay", overlay, m => { });
            AssetDatabase.SaveAssets();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.skybox = mSky;
            RenderSettings.fog = false;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.5f, 0.55f, 0.6f);

            var play = new GameObject("RT48 再生（RT48Playback）");
            var pb = play.AddComponent<RT48Playback>();

            var wave = MakeRenderer("RT48 波（掃いた面・RT48Decode.hlsl）", null, mSweep, out var waveMf);
            var loops = MakeRenderer("RT48 離れた水（閉じた線を掃いた管）", null, mLoops, out var loopsMf);
            var sea = MakeRenderer("RT48 まわりの海（波の所に穴）", null, mSea, out var seaMf);

            var boatRoot = new GameObject("RT48 船（上下と縦揺れ）");
            var hull = MakeRenderer("船体（水線の長さ 12 m・幅 2 m）", boatRoot.transform, mBoat, out var hullMf);
            var seat = new GameObject("座席");
            seat.transform.SetParent(boatRoot.transform, false);
            var origin = new GameObject("XR Origin（座席、Device の原点）");
            origin.transform.SetParent(seat.transform, false);
            var offset = new GameObject("Camera Offset");
            offset.transform.SetParent(origin.transform, false);
            offset.transform.localPosition = new Vector3(0f, 1.2f, 0f);
            var camGo = new GameObject("HMD Camera（デスクトップと共用）");
            camGo.tag = "MainCamera";
            camGo.transform.SetParent(offset.transform, false);
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.Skybox;
            cam.nearClipPlane = 0.05f; cam.farClipPlane = 25000f; cam.fieldOfView = 60f;
            cam.allowHDR = false; cam.allowMSAA = true;
            cam.stereoTargetEye = StereoTargetEyeMask.Both;
            camGo.AddComponent<AudioListener>();
            var xr = origin.AddComponent<XROrigin>();
            xr.Origin = origin; xr.CameraFloorOffsetObject = offset; xr.Camera = cam;
            xr.RequestedTrackingOriginMode = XROrigin.TrackingOriginMode.Device;
            xr.CameraYOffset = 1.2f;
            var pose = camGo.AddComponent<TrackedPoseDriver>();
            pose.trackingType = TrackedPoseDriver.TrackingType.RotationAndPosition;
            pose.updateType = TrackedPoseDriver.UpdateType.UpdateAndBeforeRender;
            pose.ignoreTrackingState = false;
            pose.positionInput = new InputActionProperty(new InputAction("HMD position", InputActionType.Value, "<XRHMD>/centerEyePosition", expectedControlType: "Vector3"));
            pose.rotationInput = new InputActionProperty(new InputAction("HMD rotation", InputActionType.Value, "<XRHMD>/centerEyeRotation", expectedControlType: "Quaternion"));
            pose.trackingStateInput = new InputActionProperty(new InputAction("HMD tracking state", InputActionType.Value, "<XRHMD>/trackingState", expectedControlType: "Integer"));
            pose.enabled = false;   // -rt48xr で XR が始まった時だけ RT48Rig が動かす

            pb.sweepFilter = waveMf; pb.loopsFilter = loopsMf; pb.seaFilter = seaMf; pb.boatFilter = hullMf;
            pb.boatRoot = boatRoot.transform; pb.viewPivot = camGo.transform; pb.viewCamera = cam; pb.decodeCheck = cs;
            pb.defaultDataRoot = DataRoot.Replace('\\', '/') + ";" + BakeRoot.Replace('\\', '/');

            var rig = play.AddComponent<RT48Rig>();
            rig.playback = pb; rig.origin = xr; rig.cameraOffset = offset.transform; rig.hmdCamera = cam; rig.poseDriver = pose;
            var caps = play.AddComponent<RT48Captions>();
            caps.playback = pb; caps.rig = rig; caps.hudCamera = cam; caps.vrAnchor = seat.transform; caps.overlayMaterial = mOverlay;
            var timing = play.AddComponent<RT48FrameTiming>();
            timing.playback = pb; timing.rig = rig; timing.captions = caps; timing.mainCamera = cam;
            var cap = play.AddComponent<RT48Capture>();
            cap.playback = pb; cap.captions = caps; cap.captureCamera = cam;

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("場面を保存できません：" + ScenePath);
            AssetDatabase.SaveAssets();
            Debug.Log("RT48_SCENE_DONE " + ScenePath + " dataRoot=" + pb.defaultDataRoot);
        }

        static GameObject MakeRenderer(string name, Transform parent, Material mat, out MeshFilter mf)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, false);
            mf = go.AddComponent<MeshFilter>();
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = false;
            mr.lightProbeUsage = LightProbeUsage.Off;
            mr.reflectionProbeUsage = ReflectionProbeUsage.Off;
            mr.motionVectorGenerationMode = MotionVectorGenerationMode.ForceNoMotion;
            mr.allowOcclusionWhenDynamic = false;
            return go;
        }

        static Material Mat(string name, Shader sh, Action<Material> set)
        {
            var path = MatDir + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null) { m = new Material(sh) { name = name }; AssetDatabase.CreateAsset(m, path); }
            else m.shader = sh;
            set(m);
            m.enableInstancing = true;
            EditorUtility.SetDirty(m);
            return m;
        }

        static void EnsureFolder(string parent, string name)
        {
            if (!AssetDatabase.IsValidFolder(parent + "/" + name)) AssetDatabase.CreateFolder(parent, name);
        }
    }
}
