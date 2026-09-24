using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Formats.Alembic.Importer;
using GreatWave.Playback18;
namespace GreatWave.Editor
{
    public static class Decision20Builder
    {
        const string Base="Assets/GreatWave/Scenes/Tests/M1_Decision20_",Evidence="../Docs/Evidence/M1/Decision20/",Art="Assets/GreatWave/Art/Playback18/";
        public static void Create()
        {
            Directory.CreateDirectory(Evidence);var reference=Playback18Reference.Read(AssetDatabase.LoadAssetAtPath<TextAsset>(Art+"reference.bytes"));var bounds=new Bounds(reference.samples[0].positions[0],Vector3.zero);foreach(var sample in reference.samples)foreach(var p in sample.positions)bounds.Encapsulate(p);bounds.Expand(.002f);
            var dependencies=new System.Collections.Generic.List<SceneDependencies>();
            foreach(bool vat in new[]{false,true})
            {
                var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);var content=new GameObject("20 形式専用コンテンツ").AddComponent<Decision20Content>();content.useVat=vat;content.vatBounds=bounds;content.captureBounds=reference.samples.Select(sample=>{var b=new Bounds(sample.positions[0],Vector3.zero);foreach(var p in sample.positions)b.Encapsulate(p);return b;}).ToArray();
                if(vat)
                {
                    content.vatRoot=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Art+"VAT/fluid17_mesh.fbx"));content.vatData=JsonUtility.FromJson<Playback18VAT.Data>(File.ReadAllText(Art+"VAT/metadata.json"));content.vatData.position=AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"VAT/fluid17_pos.exr");content.vatData.rotation=AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"VAT/fluid17_rot.exr");content.vatData.lookup=AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"VAT/fluid17_lookup.exr");content.vatMaterial=Mat("Decision20_VAT","GreatWave/Sampling19/VAT HDR Shadow",new Color(.06f,.32f,.52f));Playback18VAT.Bind(content.vatMaterial,content.vatData,0);EditorUtility.SetDirty(content.vatMaterial);foreach(var r in content.vatRoot.GetComponentsInChildren<Renderer>()){r.sharedMaterials=r.sharedMaterials.Select(_=>content.vatMaterial).ToArray();r.localBounds=bounds;PrefabUtility.RecordPrefabInstancePropertyModifications(r);}
                }
                else
                {
                    var root=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Art+"fluid17.abc"));content.stream=root.GetComponent<AlembicStreamPlayer>();var material=Mat("Decision20_ABC","GreatWave/Sampling19/Reference Shadow",new Color(.06f,.32f,.52f));foreach(var r in root.GetComponentsInChildren<Renderer>()){r.sharedMaterials=r.sharedMaterials.Select(_=>material).ToArray();PrefabUtility.RecordPrefabInstancePropertyModifications(r);}
                }
                var camera=new GameObject("20 同一カメラ").AddComponent<Camera>();camera.tag="MainCamera";camera.transform.position=new Vector3(14,12,-18);camera.transform.LookAt(new Vector3(0,.6f,0));camera.fieldOfView=45;camera.nearClipPlane=.05f;camera.farClipPlane=60;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.82f,.87f,.89f);camera.cullingMask&=~(1<<31);camera.depthTextureMode=DepthTextureMode.Depth;camera.enabled=false;content.testCamera=camera;
                var light=new GameObject("20 同一Directional光源").AddComponent<Light>();light.type=LightType.Directional;light.intensity=1;light.transform.rotation=Quaternion.Euler(48,-32,0);light.shadows=LightShadows.Hard;light.shadowBias=.01f;light.shadowNormalBias=0;RenderSettings.ambientLight=new Color(.18f,.18f,.18f);
                var floor=GameObject.CreatePrimitive(PrimitiveType.Plane);floor.name="20 共通の受影床";floor.transform.position=new Vector3(0,-.1f,0);floor.transform.localScale=Vector3.one*1.8f;floor.GetComponent<Renderer>().sharedMaterial=Mat("Decision20_Floor","GreatWave/Sampling19/Reference Shadow",new Color(.64f,.64f,.57f));content.Initialize();string path=Base+(vat?"VAT":"ABC")+".unity";if(!EditorSceneManager.SaveScene(scene,path))throw new Exception("20 scene保存失敗");AssetDatabase.SaveAssets();dependencies.Add(Dependencies(path,vat?"vat":"abc"));
            }
            var boot=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);var runner=new GameObject("20 独立プロセス測定").AddComponent<Decision20Runner>();runner.captionMaterial=Mat("Decision20_Caption","Unlit/Color",new Color(.025f,.065f,.1f));EditorSceneManager.SaveScene(boot,Base+"Boot.unity");AssetDatabase.SaveAssets();dependencies.Add(Dependencies(Base+"Boot.unity","boot"));
            File.WriteAllText(Evidence+"20_scene_isolation.json",JsonUtility.ToJson(new Isolation{scenes=dependencies.ToArray(),passed=dependencies.All(x=>x.passed)},true));if(dependencies.Any(x=>!x.passed))throw new Exception("sceneに別形式の入力参照が混入しています。");Debug.Log("DECISION20_SCENES_PASS");
        }
        static Material Mat(string name,string shader,Color color){var m=M1CompositionBuilder.Mat(name,color);m.shader=Shader.Find(shader);if(m.shader==null)throw new Exception(shader);m.SetColor("_Color",color);if(m.HasProperty("_Ambient"))m.SetFloat("_Ambient",.2f);EditorUtility.SetDirty(m);return m;}
        static SceneDependencies Dependencies(string path,string format){var fluid=AssetDatabase.GetDependencies(path,true).Where(p=>p.StartsWith(Art)&&(p.EndsWith(".abc")||p.EndsWith(".fbx")||p.EndsWith(".exr")||p.EndsWith("reference.bytes"))).OrderBy(p=>p).ToArray();return new SceneDependencies{scene=path,format=format,fluidAssets=fluid,passed=format=="boot"?fluid.Length==0:format=="abc"?fluid.Length==1&&fluid[0].EndsWith(".abc"):fluid.Length==4&&fluid.All(p=>p.EndsWith(".fbx")||p.EndsWith(".exr"))};}
        public static void Build()
        {
            Directory.CreateDirectory("Builds/Decision20");AssetDatabase.SaveAssets();bool old=PlayerSettings.enableFrameTimingStats;var baseline=SourcesNow();File.WriteAllText(Evidence+"20_project_sources.json",JsonUtility.ToJson(new Sources{files=baseline},true));BuildReport result=null;SourceFile[] compiled=null;string[]modified;
            try
            {
                PlayerSettings.enableFrameTimingStats=true;AssetDatabase.SaveAssets();compiled=SourcesNow();File.Copy("ProjectSettings/ProjectSettings.asset",Evidence+"20_compiled_PlayerSettings.asset",true);File.WriteAllText(Evidence+"20_compiled_sources.json",JsonUtility.ToJson(new Sources{files=compiled},true));
                result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{Base+"Boot.unity",Base+"ABC.unity",Base+"VAT.unity"},target=BuildTarget.StandaloneWindows64,locationPathName="Builds/Decision20/GreatWave20.exe",options=BuildOptions.Development});AssetDatabase.SaveAssets();modified=Changed(compiled,SourcesNow());
            }
            finally{PlayerSettings.enableFrameTimingStats=old;AssetDatabase.SaveAssets();}
            var after=SourcesNow();File.WriteAllText(Evidence+"20_restored_sources.json",JsonUtility.ToJson(new Sources{files=after},true));var restored=Changed(baseline,after);var overrides=Changed(baseline,compiled);var info=new BuildInfo{unity=Application.unityVersion,utc=DateTime.UtcNow.ToString("O"),result=result.summary.result.ToString(),errors=result.summary.totalErrors,warnings=result.summary.totalWarnings,bytes=result.summary.totalSize.ToString(),frameTimingBefore=old,frameTimingCompiled=true,frameTimingRestored=PlayerSettings.enableFrameTimingStats,compiledOverrideFiles=overrides,buildModifiedFiles=modified,restorationModifiedFiles=restored};info.passed=result.summary.result==BuildResult.Succeeded&&info.errors==0&&modified.Length==0&&restored.Length==0&&overrides.All(p=>p=="ProjectSettings/ProjectSettings.asset");File.WriteAllText(Evidence+"20_build.json",JsonUtility.ToJson(info,true));if(!info.passed)throw new Exception("20 buildまたは設定復元が失敗");Debug.Log("DECISION20_BUILD_PASS");
        }
        static string[]Changed(SourceFile[]a,SourceFile[]b)=>a.Select(x=>x.path).Union(b.Select(x=>x.path)).Where(p=>!a.Any(x=>x.path==p&&b.Any(y=>y.path==p&&y.sha256==x.sha256))).ToArray();
        static SourceFile[]SourcesNow()=>new[]{"Assets","Packages","ProjectSettings"}.SelectMany(f=>Directory.GetFiles(f,"*",SearchOption.AllDirectories)).OrderBy(p=>p).Select(p=>{using(var h=SHA256.Create())return new SourceFile{path=p.Replace('\\','/'),sha256=BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(p))).Replace("-","").ToLowerInvariant()};}).ToArray();
        [Serializable]class SourceFile{public string path,sha256;}[Serializable]class Sources{public SourceFile[]files;}
        [Serializable]class SceneDependencies{public string scene,format;public string[]fluidAssets;public bool passed;}[Serializable]class Isolation{public SceneDependencies[]scenes;public bool passed;}
        [Serializable]class BuildInfo{public string unity,utc,result,bytes;public int errors,warnings;public bool frameTimingBefore,frameTimingCompiled,frameTimingRestored,passed;public string[]compiledOverrideFiles,buildModifiedFiles,restorationModifiedFiles;}
    }
}
