using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Editor
{
    public static class M1CompositionBuilder
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/M1_StaticComposition.unity";
        public static readonly Vector3 ComparisonPosition = new Vector3(0, 15, -62);
        public static readonly Vector3 ComparisonTarget = new Vector3(-2.5f, 8.4f, 4);

        public static Material Mat(string name, Color color)
        {
            string path = "Assets/GreatWave/Materials/" + name + ".mat";
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material == null) { material = new Material(Shader.Find("Standard")); AssetDatabase.CreateAsset(material, path); }
            material.color = color;
            material.SetFloat("_Glossiness", 0);
            return material;
        }

        public static GameObject Model(string filename, string name, Vector3 position)
        {
            string path = "Assets/GreatWave/Art/M1/" + filename;
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
            var importer = (ModelImporter)AssetImporter.GetAtPath(path);
            importer.globalScale = 1;
            importer.useFileScale = true;
            importer.bakeAxisConversion = false;
            importer.importAnimation = false;
            importer.isReadable = true;
            importer.SaveAndReimport();
            var root = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(path));
            root.name = name;
            root.transform.position = position;
            foreach (var renderer in root.GetComponentsInChildren<Renderer>())
            {
                renderer.sharedMaterials = renderer.sharedMaterials.Select(m =>
                {
                    var color = m == null ? Color.magenta : m.color;
                    if (m != null)
                    {
                        if (m.name.Contains("M1_Indigo")) color = new Color(.018f,.10f,.20f);
                        else if (m.name.Contains("M1_DeepBlue")) color = new Color(.012f,.053f,.12f);
                        else if (m.name.Contains("M1_LightBlue")) color = new Color(.23f,.46f,.53f);
                        else if (m.name.Contains("M1_Blue")) color = new Color(.065f,.27f,.39f);
                    }
                    return Mat(m == null ? "M1_MissingMaterial" : m.name, color);
                }).ToArray();
            }
            return root;
        }

        public static Bounds BoundsOf(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<Renderer>();
            var bounds = renderers[0].bounds;
            foreach (var renderer in renderers) bounds.Encapsulate(renderer.bounds);
            return bounds;
        }

        public static void Step11()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(.65f, .72f, .82f);
            RenderSettings.fog = false;
            var plane = M0BaselineBuilder.Box("M1 flat reference sea", new Vector3(0,-.32f,-170), new Vector3(240,.5f,476),
                Mat("M1_Sea", new Color(.055f,.17f,.25f)));
            var wave = Model("wave_static.fbx", "M1 main wave - static geometry", Vector3.zero);
            var camera = new GameObject("M1 comparison camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(.90f,.85f,.71f);
            camera.orthographic = true;
            camera.orthographicSize = 14.1f;
            camera.nearClipPlane = .1f;
            camera.farClipPlane = 300;
            camera.transform.position = ComparisonPosition;
            camera.transform.LookAt(ComparisonTarget);
            var light = new GameObject("M1 sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.15f;
            light.transform.rotation = Quaternion.Euler(45,-35,0);
            var measured = BoundsOf(wave);
            bool finite = wave.GetComponentsInChildren<MeshFilter>().All(f => f.sharedMesh.vertices.All(v =>
                !float.IsNaN(v.x) && !float.IsNaN(v.y) && !float.IsNaN(v.z)));
            bool volume = measured.size.x > 25 && measured.size.y > 15 && measured.size.z > 15;
            var source = JsonUtility.FromJson<SourceGeometry>(File.ReadAllText("../Blender/M1_Composition/11_blender_geometry.json"));
            var expectedMin = new Vector3(source.expected_unity_min_m[0],source.expected_unity_min_m[1],source.expected_unity_min_m[2]);
            var expectedMax = new Vector3(source.expected_unity_max_m[0],source.expected_unity_max_m[1],source.expected_unity_max_m[2]);
            bool matchingSource = Vector3.Distance(measured.min,expectedMin) < .001f && Vector3.Distance(measured.max,expectedMax) < .001f;
            var result = new GeometryResult { unity = Application.unityVersion, boundsCenter = measured.center, boundsSize = measured.size,
                meshVertices = wave.GetComponentsInChildren<MeshFilter>().Sum(f => f.sharedMesh.vertexCount), finiteVertices = finite,
                substantialDepth = volume, boundsMatchBlender = matchingSource, staticNotFluid = true, passed = finite && volume && matchingSource };
            File.WriteAllText("../Docs/Evidence/M1/11_unity_geometry.json", JsonUtility.ToJson(result,true));
            if (!result.passed) throw new InvalidOperationException("11の静止波の幾何検査が不合格です。");
            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.SaveAssets();
            Render(camera, "../Docs/Evidence/M1/11_wave_early.png");
            Debug.Log("M1_STEP11_PASS: static thick mesh; no fluid claim");
        }

        public static void Render(Camera camera, string path)
        {
            var target = new RenderTexture(1280,720,24);
            target.Create();
            var previous = camera.targetTexture;
            var active = RenderTexture.active;
            camera.targetTexture = target;
            camera.Render();
            RenderTexture.active = target;
            var image = new Texture2D(1280,720,TextureFormat.RGB24,false);
            image.ReadPixels(new Rect(0,0,1280,720),0,0);
            image.Apply();
            File.WriteAllBytes(path,image.EncodeToPNG());
            camera.targetTexture = previous;
            RenderTexture.active = active;
            UnityEngine.Object.DestroyImmediate(image);
            target.Release();
            UnityEngine.Object.DestroyImmediate(target);
        }

        [Serializable] class GeometryResult
        {
            public string unity;
            public Vector3 boundsCenter, boundsSize;
            public int meshVertices;
            public bool finiteVertices, substantialDepth, boundsMatchBlender, staticNotFluid, passed;
        }
        [Serializable] class SourceGeometry { public float[] expected_unity_min_m, expected_unity_max_m; }
    }
}
