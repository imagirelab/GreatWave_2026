using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Editor
{
    public static class M0BaselineBuilder
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/M0_DesktopPreflight.unity";

        public static Material Material(string name, Color color)
        {
            var path = "Assets/GreatWave/Materials/" + name + ".mat";
            var result = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (result == null)
            {
                result = new Material(Shader.Find("Standard"));
                AssetDatabase.CreateAsset(result, path);
            }
            result.color = color;
            result.SetFloat("_Glossiness", 0.05f);
            return result;
        }

        public static GameObject Box(string name, Vector3 position, Vector3 size, Material material, Transform parent = null)
        {
            var item = GameObject.CreatePrimitive(PrimitiveType.Cube);
            item.name = name;
            item.transform.SetParent(parent, false);
            item.transform.localPosition = position;
            item.transform.localScale = size;
            item.GetComponent<Renderer>().sharedMaterial = material;
            return item;
        }

        [MenuItem("GreatWave/06 基準シーンを新規作成")]
        public static void Create()
        {
            Directory.CreateDirectory("Assets/GreatWave/Scenes/Tests");
            Directory.CreateDirectory("Assets/GreatWave/Materials");
            Directory.CreateDirectory("../Docs/Evidence/M0");
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.72f, 0.77f, 0.81f);
            RenderSettings.fog = true;
            RenderSettings.fogColor = new Color(0.75f, 0.82f, 0.83f);
            RenderSettings.fogMode = FogMode.Exponential;
            RenderSettings.fogDensity = 0.008f;
            var water = Material("M0_FlatPlane", new Color(0.15f, 0.35f, 0.43f));
            var cream = Material("M0_Cream", new Color(0.91f, 0.87f, 0.72f));
            var red = Material("M0_AxisX", new Color(0.85f, 0.22f, 0.16f));
            var green = Material("M0_AxisY", new Color(0.25f, 0.65f, 0.32f));
            var blue = Material("M0_AxisZ", new Color(0.19f, 0.40f, 0.91f));
            Box("Flat reference plane - no waves", new Vector3(0, -0.06f, 0), new Vector3(400, 0.1f, 400), water);
            Box("Unity 1m reference", new Vector3(3, 0.5f, 7), Vector3.one, cream);
            var axes = new GameObject("World axes");
            axes.transform.position = new Vector3(-4, 0.03f, 7);
            Box("X+ red", new Vector3(0.75f, 0, 0), new Vector3(1.5f, .035f, .035f), red, axes.transform);
            Box("Y+ green", new Vector3(0, 0.75f, 0), new Vector3(.035f, 1.5f, .035f), green, axes.transform);
            Box("Z+ blue", new Vector3(0, 0, 0.75f), new Vector3(.035f, .035f, 1.5f), blue, axes.transform);
            var cameraObject = new GameObject("Desktop camera");
            cameraObject.tag = "MainCamera";
            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(.91f, .88f, .79f);
            camera.fieldOfView = 65;
            camera.nearClipPlane = .05f;
            camera.farClipPlane = 300;
            camera.transform.position = new Vector3(0, 1.2f, 0);
            camera.transform.rotation = Quaternion.Euler(8, 0, 0);
            cameraObject.AddComponent<AudioListener>();
            var sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional;
            sun.intensity = 1.1f;
            sun.transform.rotation = Quaternion.Euler(45, -30, 0);
            PlayerSettings.companyName = "GreatWave Research";
            PlayerSettings.productName = "GreatWave M0 PC確認版";
            PlayerSettings.defaultScreenWidth = 1280;
            PlayerSettings.defaultScreenHeight = 720;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
            PlayerSettings.runInBackground = true;
            PlayerSettings.colorSpace = ColorSpace.Linear;
            QualitySettings.vSyncCount = 0;
            QualitySettings.antiAliasing = 4;
            PlayerSettings.SetGraphicsAPIs(BuildTarget.StandaloneWindows64, new[] { GraphicsDeviceType.Direct3D11 });
            PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.Standalone, ScriptingImplementation.Mono2x);
            bool sceneSaved = EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            var report = new BaselineReport { unity = Application.unityVersion, scene = ScenePath,
                objects = scene.GetRootGameObjects().Length, cubeSize = GameObject.Find("Unity 1m reference").GetComponent<Renderer>().bounds.size,
                pipeline = "Built-in（M0暫定）", hmdStatus = "未所持・実機未検証" };
            report.sceneSaved = sceneSaved && File.Exists(ScenePath);
            report.sceneEnabled = EditorBuildSettings.scenes.Length == 1 && EditorBuildSettings.scenes[0].enabled
                && EditorBuildSettings.scenes[0].path == ScenePath;
            report.cubeWithinTolerance = Mathf.Abs(report.cubeSize.x - 1f) <= .001f
                && Mathf.Abs(report.cubeSize.y - 1f) <= .001f && Mathf.Abs(report.cubeSize.z - 1f) <= .001f;
            report.cameraConfigured = camera != null && camera.enabled && camera.nearClipPlane > 0
                && camera.farClipPlane > 200 && camera.CompareTag("MainCamera");
            report.materialsConfigured = water.shader != null && cream.shader != null;
            report.passed = report.sceneSaved && report.sceneEnabled && report.cubeWithinTolerance
                && report.cameraConfigured && report.materialsConfigured;
            File.WriteAllText("../Docs/Evidence/M0/06_baseline.json", JsonUtility.ToJson(report, true));
            if (!report.passed) throw new InvalidOperationException("06の基準シーン検証が不合格。JSONを確認してください。");
            Debug.Log("M0_STEP06_PASS: scene saved; unit cube=" + report.cubeSize);
        }

        [Serializable] class BaselineReport
        {
            public string unity, scene, pipeline, hmdStatus;
            public int objects;
            public Vector3 cubeSize;
            public bool sceneSaved, sceneEnabled, cubeWithinTolerance, cameraConfigured, materialsConfigured, passed;
        }
    }
}
