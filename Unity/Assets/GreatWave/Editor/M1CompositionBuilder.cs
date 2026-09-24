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
        public static readonly Vector3 ComparisonPosition = new Vector3(0, 3, -62);
        public static readonly Vector3 ComparisonTarget = new Vector3(-2.5f, 9.7f, 4);

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
            if (importer.globalScale != 1 || !importer.useFileScale || importer.bakeAxisConversion || importer.importAnimation || !importer.isReadable)
            {
                importer.globalScale = 1; importer.useFileScale = true; importer.bakeAxisConversion = false;
                importer.importAnimation = false; importer.isReadable = true; importer.SaveAndReimport();
            }
            // FBX自体の軸変換を保持し、配置・回転には別の親を使う。
            var root = new GameObject(name);
            var imported = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(path));
            imported.transform.SetParent(root.transform, false);
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
                        else if (m.name.Contains("GW_Boat_Wood")) color = new Color(.69f,.43f,.20f);
                        else if (m.name.Contains("GW_Boat_Edge")) color = new Color(.04f,.10f,.16f);
                        else if (m.name.Contains("GW_Boat_Plank")) color = new Color(.87f,.66f,.35f);
                        else if (m.name.Contains("GW_Fuji_Blue")) color = new Color(.027f,.10f,.20f);
                        else if (m.name.Contains("GW_Fuji_Snow")) color = new Color(.94f,.90f,.76f);
                    }
                    return Mat(m == null ? "M1_MissingMaterial" : m.name, color);
                }).ToArray();
                PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);
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
            var plane = M0BaselineBuilder.Box("M1 flat reference sea", new Vector3(0,-.32f,100), new Vector3(1000,.5f,1000),
                Mat("M1_Sea", new Color(.055f,.17f,.25f)));
            var wave = Model("wave_static.fbx", "M1 main wave - static geometry", Vector3.zero);
            var camera = new GameObject("M1 comparison camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(.90f,.85f,.71f);
            camera.orthographic = false;
            camera.fieldOfView = 26;
            camera.orthographicSize = 14.1f;
            camera.aspect = 1280f / 720;
            camera.nearClipPlane = .1f;
            camera.farClipPlane = 900;
            camera.transform.position = ComparisonPosition;
            camera.transform.LookAt(ComparisonTarget);
            var light = new GameObject("M1 sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.15f;
            light.transform.rotation = Quaternion.Euler(45,-35,0);
            var measured = BoundsOf(wave);
            bool finite = wave.GetComponentsInChildren<MeshFilter>().All(f => f.sharedMesh.vertices.All(v =>
                !float.IsNaN(v.x) && !float.IsNaN(v.y) && !float.IsNaN(v.z)
                && !float.IsInfinity(v.x) && !float.IsInfinity(v.y) && !float.IsInfinity(v.z)));
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
            camera.aspect = 1280f / 720;
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

        public static void Step12()
        {
            var scene = EditorSceneManager.OpenScene(ScenePath);
            // 反復実行でも旧ルート直下のFBXや配置用親を残さない。
            foreach (var root in scene.GetRootGameObjects())
            {
                if (root.GetComponentsInChildren<Transform>().Any(t => {
                    var path = PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(t.gameObject);
                    return path.EndsWith("boat_blockout.fbx") || path.EndsWith("fuji_blockout.fbx");
                })) UnityEngine.Object.DestroyImmediate(root);
            }
            foreach (var name in new[] { "M1 foreground boat", "M1 middle boat", "M1 left boat", "M1 distant Fuji" })
            { var old = GameObject.Find(name); if (old != null) UnityEngine.Object.DestroyImmediate(old); }
            var boat = Model("boat_blockout.fbx", "M1 foreground boat", Vector3.zero);
            var boatBounds = BoundsOf(boat);
            bool boatDimensions = Vector3.Distance(boatBounds.size,new Vector3(1.8f,1.775f,10)) < .001f;
            boat.transform.position = new Vector3(8,-.28f,-8);
            boat.transform.rotation = Quaternion.Euler(0,65,0);
            boat.transform.localScale = Vector3.one * 1.35f;
            var middle = Model("boat_blockout.fbx", "M1 middle boat", new Vector3(0,-.23f,10));
            middle.transform.rotation = Quaternion.Euler(0,57,0);
            middle.transform.localScale = Vector3.one * .85f;
            var left = Model("boat_blockout.fbx", "M1 left boat", new Vector3(-16,-.1f,-.5f));
            left.transform.rotation = Quaternion.Euler(0,42,0);
            left.transform.localScale = Vector3.one * .8f;
            var fuji = Model("fuji_blockout.fbx", "M1 distant Fuji", Vector3.zero);
            var fujiBounds = BoundsOf(fuji);
            bool fujiDimensions = Vector3.Distance(fujiBounds.size,new Vector3(24,8,24)) < .001f;
            fuji.transform.position = new Vector3(37,-.1f,420);
            fuji.transform.localScale = Vector3.one * 2;
            var camera = Camera.main;
            camera.aspect = 1280f / 720;
            camera.orthographic = false;
            camera.fieldOfView = 26;
            camera.farClipPlane = 900;
            camera.transform.position = ComparisonPosition;
            camera.transform.LookAt(ComparisonTarget);
            var sea = GameObject.Find("M1 flat reference sea");
            sea.transform.position = new Vector3(0,-.32f,100);
            sea.transform.localScale = new Vector3(1000,.5f,1000);
            int boatCount = scene.GetRootGameObjects().Count(r => r.name.EndsWith(" boat"));
            var fujiScreen = ProjectedBounds(camera,fuji);
            var boatScreen = ProjectedBounds(camera,boat);
            bool compositionChecks = boatCount == 3 && fujiScreen.width > .08f && fujiScreen.height > .05f && boatScreen.width > .20f && boatScreen.width < .35f;
            var result = new PlacementResult { boatImportedSize = boatBounds.size, fujiImportedSize = fujiBounds.size,
                boatDimensions = boatDimensions, fujiDimensions = fujiDimensions,
                comparisonPosition = camera.transform.position, comparisonRotation = camera.transform.eulerAngles,
                orthographicSize = camera.orthographicSize, fujiApexViewport = camera.WorldToViewportPoint(fuji.transform.TransformPoint(new Vector3(0,8,0))),
                foregroundBoatViewport = camera.WorldToViewportPoint(BoundsOf(boat).center),
                fieldOfView = camera.fieldOfView, perspective = !camera.orthographic, aspect = camera.aspect,
                fujiDistanceFromBoat = Vector3.Distance(boat.transform.position,fuji.transform.position),
                foregroundBoatSize = BoundsOf(boat).size,
                fujiPlacedSize = BoundsOf(fuji).size, fujiViewportBounds = fujiScreen, foregroundBoatViewportBounds = boatScreen, boatCount = boatCount,
                note = "投影座標は左下(0,0)〜右上(1,1)。縮尺・配置は構図検討の仮値。物理・史実の復元ではない。",
                passed = boatDimensions && fujiDimensions && compositionChecks };
            File.WriteAllText("../Docs/Evidence/M1/12_placement.json",JsonUtility.ToJson(result,true));
            if (!result.passed) throw new InvalidOperationException("12の実インポート寸法が一致しません。");
            EditorSceneManager.SaveScene(scene);
            AssetDatabase.SaveAssets();
            Render(camera,"../Docs/Evidence/M1/12_composition_early.png");
            Debug.Log("M1_STEP12_PASS: imported dimensions and comparison camera saved");
        }

        public static Rect ProjectedBounds(Camera camera, GameObject root)
        {
            var points = root.GetComponentsInChildren<MeshFilter>().SelectMany(f => f.sharedMesh.vertices.Select(v => camera.WorldToViewportPoint(f.transform.TransformPoint(v)))).ToArray();
            return Rect.MinMaxRect(points.Min(p => p.x),points.Min(p => p.y),points.Max(p => p.x),points.Max(p => p.y));
        }

        [Serializable] class PlacementResult
        {
            public Vector3 boatImportedSize,fujiImportedSize,comparisonPosition,comparisonRotation,fujiApexViewport,foregroundBoatViewport,foregroundBoatSize,fujiPlacedSize;
            public Rect fujiViewportBounds,foregroundBoatViewportBounds;
            public int boatCount;
            public float orthographicSize,fieldOfView,aspect,fujiDistanceFromBoat;
            public bool boatDimensions,fujiDimensions,perspective,passed;
            public string note;
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
