using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Formats.Alembic.Importer;

namespace GreatWave.Editor
{
    public static class FixedTopology16Builder
    {
        public const string ScenePath="Assets/GreatWave/Scenes/Tests/M1_FixedTopology16.unity";
        public const string AbcPath="Assets/GreatWave/Art/FixedTopology16/fixed_topology_16.abc";
        public const string ReferencePath="Assets/GreatWave/Art/FixedTopology16/reference_samples.json";
        const string Evidence="../Docs/Evidence/M1/FixedTopology16/";
        public static void CreateAndValidate()
        {
            AssetDatabase.ImportAsset(AbcPath,ImportAssetOptions.ForceSynchronousImport);
            var importer=AssetImporter.GetAtPath(AbcPath);
            var serialized=new SerializedObject(importer);
            var settings=serialized.FindProperty("streamSettings");
            if(settings==null)throw new InvalidOperationException("Alembic2.4.4の読み込み設定が見つかりません。");
            settings.FindPropertyRelative("scaleFactor").floatValue=1;
            settings.FindPropertyRelative("swapHandedness").boolValue=true;
            settings.FindPropertyRelative("flipFaces").boolValue=false;
            settings.FindPropertyRelative("interpolateSamples").boolValue=true;
            serialized.ApplyModifiedPropertiesWithoutUndo();importer.SaveAndReimport();
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var root=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(AbcPath));
            root.name="16 Houdini実書き出し・固定トポロジー";
            var stream=root.GetComponent<AlembicStreamPlayer>();
            var referenceAsset=AssetDatabase.LoadAssetAtPath<TextAsset>(ReferencePath);
            var reference=JsonUtility.FromJson<FixedTopology16Reference>(referenceAsset.text);
            foreach(var renderer in root.GetComponentsInChildren<MeshRenderer>())
            {
                string name=renderer.gameObject.name;Color color=new Color(.06f,.38f,.58f);
                if(name.Contains("unit_cube"))color=new Color(.9f,.75f,.15f);
                if(name.Contains("axis_x"))color=new Color(.95f,.12f,.12f);
                if(name.Contains("axis_y"))color=new Color(.12f,.85f,.2f);
                if(name.Contains("axis_z"))color=new Color(.12f,.3f,.95f);
                if(name.Contains("asym_"))color=new Color(.95f,.15f,.75f);
                renderer.sharedMaterials=renderer.sharedMaterials.Select(_=>M1CompositionBuilder.Mat("Fixed16_"+name,color)).ToArray();
                PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);
            }
            var camera=new GameObject("16 検査カメラ").AddComponent<Camera>();camera.tag="MainCamera";
            camera.transform.position=new Vector3(12,10,-14);camera.transform.LookAt(new Vector3(0,.25f,0));camera.fieldOfView=47;camera.aspect=1280f/720;
            camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.82f,.87f,.89f);camera.farClipPlane=100;
            var sun=new GameObject("16 検査照明").AddComponent<Light>();sun.type=LightType.Directional;sun.intensity=1.2f;sun.transform.rotation=Quaternion.Euler(50,-35,0);
            RenderSettings.ambientLight=new Color(.48f,.52f,.56f);
            var floor=GameObject.CreatePrimitive(PrimitiveType.Plane);floor.name="16 寸法確認用床";floor.transform.position=new Vector3(0,-.8f,0);floor.transform.localScale=Vector3.one*2;
            floor.GetComponent<Renderer>().sharedMaterial=M1CompositionBuilder.Mat("Fixed16_Floor",new Color(.25f,.29f,.31f));
            var player=new GameObject("16 一回再生・終端停止").AddComponent<FixedTopology16Player>();player.stream=stream;
            var recorder=player.gameObject.AddComponent<FixedTopology16Recorder>();recorder.player=player;recorder.cameraToRender=camera;recorder.reference=referenceAsset;
            recorder.captionMaterial=M1CompositionBuilder.Mat("Fixed16_Caption",new Color(.025f,.065f,.10f));
            Directory.CreateDirectory(Evidence);
            var result=FixedTopology16Validation.Measure(stream,reference);
            File.WriteAllText(Evidence+"16_unity_editor_validation.json",JsonUtility.ToJson(result,true));
            var clips=AssetDatabase.LoadAllAssetsAtPath(AbcPath).OfType<AnimationClip>().Select(c=>new Sampling{name=c.name,times=AnimationUtility.GetAnimationEvents(c).Select(e=>e.time).ToArray()}).Where(c=>c.times.Length>0).ToArray();
            var sampling=new ArchiveSampling{method="Unity Alembic2.4.4の公式Importerが実アーカイブaiTimeSamplingから生成したAnimationEventを読む",archiveStart=stream.MediaStartTime,samplings=clips};
            sampling.passed=clips.Any(c=>c.times.Length==61&&c.times.Select((t,i)=>Math.Abs(t-(1.0/24+i/30.0))<.00001).All(v=>v));
            File.WriteAllText(Evidence+"16_archive_sampling.json",JsonUtility.ToJson(sampling,true));
            if(!result.passed||!sampling.passed)throw new InvalidOperationException("16の座標・法線・時間・接続検査が失敗しました。JSONを確認してください。");
            EditorSceneManager.SaveScene(scene,ScenePath);AssetDatabase.SaveAssets();
            M1CompositionBuilder.Render(camera,Evidence+"16_unity_early.png");
            Debug.Log("FIXED16_EDITOR_PASS: 61 native sample events, 61 samples + 60 midpoint positions; no fluid/HMD claim");
        }
        public static void Build()
        {
            EditorSceneManager.OpenScene(ScenePath);Directory.CreateDirectory("Builds/FixedTopology16");AssetDatabase.SaveAssets();
            var before=SourcesNow();File.WriteAllText(Evidence+"16_prebuild_sources.json",JsonUtility.ToJson(new Sources{files=before},true));
            var build=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},target=BuildTarget.StandaloneWindows64,locationPathName="Builds/FixedTopology16/GreatWave16.exe",options=BuildOptions.Development});
            AssetDatabase.SaveAssets();var after=SourcesNow();File.WriteAllText(Evidence+"16_build_sources.json",JsonUtility.ToJson(new Sources{files=after},true));
            var modified=before.Select(f=>f.path).Union(after.Select(f=>f.path)).Where(p=>!before.Any(b=>b.path==p&&after.Any(a=>a.path==p&&a.sha256==b.sha256))).ToArray();
            var result=new BuildInfo{unity=Application.unityVersion,utc=DateTime.UtcNow.ToString("O"),scene=ScenePath,result=build.summary.result.ToString(),errors=build.summary.totalErrors,warnings=build.summary.totalWarnings,bytes=build.summary.totalSize.ToString(),buildModifiedFiles=modified,passed=build.summary.result==BuildResult.Succeeded&&build.summary.totalErrors==0};
            File.WriteAllText(Evidence+"16_build.json",JsonUtility.ToJson(result,true));
            if(!result.passed)throw new InvalidOperationException("16 PCビルドが失敗しました。");
            Debug.Log("FIXED16_BUILD_PASS");
        }
        [Serializable]class Sampling{public string name;public float[]times;}
        static SourceFile[] SourcesNow()=>new[]{"Assets","Packages","ProjectSettings"}.SelectMany(f=>Directory.GetFiles(f,"*",SearchOption.AllDirectories)).OrderBy(p=>p).Select(p=>{using(var hash=SHA256.Create())return new SourceFile{path=p.Replace('\\','/'),sha256=BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(p))).Replace("-","").ToLowerInvariant()};}).ToArray();
        [Serializable]class SourceFile{public string path,sha256;}
        [Serializable]class Sources{public SourceFile[]files;}
        [Serializable]class ArchiveSampling{public string method;public float archiveStart;public Sampling[]samplings;public bool passed;}
        [Serializable]class BuildInfo{public string unity,utc,scene,result,bytes;public string[]buildModifiedFiles;public int errors,warnings;public bool passed;}
    }
}
