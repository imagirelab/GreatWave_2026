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
    public static class Sampling19Builder
    {
        public const string ScenePath="Assets/GreatWave/Scenes/Tests/M1_Sampling19.unity",Art="Assets/GreatWave/Art/Sampling19/",Evidence="../Docs/Evidence/M1/Sampling19/";
        public static void CreateAndValidate()
        {
            Directory.CreateDirectory(Evidence);var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var player=new GameObject("19 実30/60Hz一回再生").AddComponent<Sampling19Player>();var material=Material("Sampling19_Fluid","GreatWave/Sampling19/Reference Shadow",new Color(.06f,.32f,.52f));
            player.streams60=new AlembicStreamPlayer[3];var samplings=new System.Collections.Generic.List<Archive>();
            for(int part=0;part<3;part++){string name=$"fluid19_60_{part*40:D3}_{(part+1)*40:D3}.abc";player.streams60[part]=Import(name,material);samplings.Add(Sampling(name,part*40,41,60));}
            player.stream30=Import("fluid19_30_000_120.abc",material);samplings.Add(Sampling("fluid19_30_000_120.abc",0,61,30));
            File.WriteAllText(Evidence+"19_archive_sampling.json",JsonUtility.ToJson(new Archives{archives=samplings.ToArray(),passed=samplings.All(x=>x.passed)},true));if(samplings.Any(x=>!x.passed))throw new Exception("19の実アーカイブ時刻が一致しません。");
            var source=AssetDatabase.LoadAssetAtPath<TextAsset>(Art+"reference60.bytes");var reference=Sampling19Reference.Read(source);var measured=Sampling19Validation.Measure(player,reference);File.WriteAllText(Evidence+"19_editor_validation.json",JsonUtility.ToJson(measured,true));if(!measured.passed)throw new Exception("19の形状/時刻/境界検査が失敗しました。");
            player.shadowFixture=ShadowFixture();
            var camera=new GameObject("19 共通検査カメラ").AddComponent<Camera>();camera.tag="MainCamera";camera.transform.position=new Vector3(14,11,-16);camera.transform.LookAt(new Vector3(0,.6f,0));camera.fieldOfView=45;camera.aspect=1280f/720;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.82f,.87f,.89f);camera.nearClipPlane=.05f;camera.farClipPlane=60;camera.depthTextureMode=DepthTextureMode.Depth;
            var sun=new GameObject("19 実Directional影").AddComponent<Light>();sun.type=LightType.Directional;sun.intensity=1;sun.transform.rotation=Quaternion.Euler(48,-32,0);sun.shadows=LightShadows.Hard;sun.shadowBias=.01f;sun.shadowNormalBias=0;RenderSettings.ambientLight=new Color(.18f,.18f,.18f);
            var floor=GameObject.CreatePrimitive(PrimitiveType.Plane);floor.name="19 深度・受影床";floor.transform.position=new Vector3(0,-.1f,0);floor.transform.localScale=Vector3.one*1.8f;floor.GetComponent<Renderer>().sharedMaterial=Material("Sampling19_Floor","GreatWave/Sampling19/Reference Shadow",new Color(.64f,.64f,.57f));
            var occluder=GameObject.CreatePrimitive(PrimitiveType.Cube);occluder.name="19 深度遮蔽用の既知寸法";occluder.transform.position=new Vector3(.15f,.7f,-.5f);occluder.transform.localScale=new Vector3(.18f,1.6f,.18f);occluder.GetComponent<Renderer>().sharedMaterial=Material("Sampling19_Occluder","GreatWave/Sampling19/Reference Shadow",new Color(.8f,.3f,.12f));occluder.SetActive(false);
            var recorder=player.gameObject.AddComponent<Sampling19Recorder>();recorder.player=player;recorder.cameraToRender=camera;recorder.source=source;recorder.sun=sun;recorder.occluder=occluder;recorder.depthMaterial=Material("Sampling19_Depth","Hidden/GreatWave/Sampling19/Depth View",Color.white);recorder.captionMaterial=Material("Sampling19_Caption","Unlit/Color",new Color(.025f,.065f,.1f));
            player.SetSample(60,60);M1CompositionBuilder.Render(camera,Evidence+"19_early.png");player.SetSample(0,60);EditorSceneManager.SaveScene(scene,ScenePath);AssetDatabase.SaveAssets();Debug.Log("SAMPLING19_EDITOR_PASS");
        }
        static AlembicStreamPlayer Import(string name,Material material)
        {
            string path=Art+name;AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport);var importer=AssetImporter.GetAtPath(path);var data=new SerializedObject(importer);var settings=data.FindProperty("streamSettings");settings.FindPropertyRelative("scaleFactor").floatValue=1;settings.FindPropertyRelative("swapHandedness").boolValue=true;settings.FindPropertyRelative("flipFaces").boolValue=false;settings.FindPropertyRelative("interpolateSamples").boolValue=false;data.ApplyModifiedPropertiesWithoutUndo();importer.SaveAndReimport();return InstantiateStream(path,material);
        }
        static AlembicStreamPlayer InstantiateStream(string path,Material material)
        {
            var root=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(path));var stream=root.GetComponent<AlembicStreamPlayer>();stream.UpdateImmediately(0);foreach(var renderer in root.GetComponentsInChildren<Renderer>()){renderer.sharedMaterials=renderer.sharedMaterials.Select(_=>material).ToArray();PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);}return stream;
        }
        static Playback18Player ShadowFixture()
        {
            var fixture=new GameObject("19 深度影・18正式試料を再利用").AddComponent<Playback18Player>();fixture.recording=true;
            fixture.stream=InstantiateStream(Playback18Builder.Art+"fluid17.abc",Material("Sampling19_ShadowABC","GreatWave/Sampling19/Reference Shadow",new Color(.06f,.32f,.52f)));fixture.stream.transform.SetParent(fixture.transform,false);
            fixture.vatRoot=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Playback18Builder.Art+"VAT/fluid17_mesh.fbx"));fixture.vatRoot.transform.SetParent(fixture.transform,false);
            fixture.vatData=JsonUtility.FromJson<Playback18VAT.Data>(File.ReadAllText(Playback18Builder.Art+"VAT/metadata.json"));fixture.vatData.position=AssetDatabase.LoadAssetAtPath<Texture2D>(Playback18Builder.Art+"VAT/fluid17_pos.exr");fixture.vatData.rotation=AssetDatabase.LoadAssetAtPath<Texture2D>(Playback18Builder.Art+"VAT/fluid17_rot.exr");fixture.vatData.lookup=AssetDatabase.LoadAssetAtPath<Texture2D>(Playback18Builder.Art+"VAT/fluid17_lookup.exr");
            fixture.vatMaterial=Material("Sampling19_ShadowVAT","GreatWave/Sampling19/VAT HDR Shadow",new Color(.06f,.32f,.52f));Playback18VAT.Bind(fixture.vatMaterial,fixture.vatData,0);EditorUtility.SetDirty(fixture.vatMaterial);
            var old=Playback18Reference.Read(AssetDatabase.LoadAssetAtPath<TextAsset>(Playback18Builder.Art+"reference.bytes"));var bounds=new Bounds(old.samples[0].positions[0],Vector3.zero);foreach(var sample in old.samples)foreach(var p in sample.positions)bounds.Encapsulate(p);bounds.Expand(.002f);fixture.vatBounds=bounds;
            foreach(var renderer in fixture.vatRoot.GetComponentsInChildren<Renderer>()){renderer.sharedMaterials=renderer.sharedMaterials.Select(_=>fixture.vatMaterial).ToArray();renderer.localBounds=bounds;PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);}fixture.gameObject.SetActive(false);return fixture;
        }
        static Material Material(string name,string shader,Color color){var value=M1CompositionBuilder.Mat(name,color);value.shader=Shader.Find(shader);if(value.shader==null)throw new Exception("検査shaderがありません："+shader);value.SetColor("_Color",color);if(value.HasProperty("_Ambient"))value.SetFloat("_Ambient",.2f);EditorUtility.SetDirty(value);return value;}
        static Archive Sampling(string name,int first,int count,int rate)
        {
            var events=AssetDatabase.LoadAllAssetsAtPath(Art+name).OfType<AnimationClip>().Select(c=>AnimationUtility.GetAnimationEvents(c).Select(e=>e.time).ToArray()).FirstOrDefault(x=>x.Length==count);
            return new Archive{name=name,firstMaster=first,rate=rate,count=count,nativeTimes=events,passed=events!=null&&events.Select((v,i)=>Math.Abs(v-(1.0/24+first/60.0+i/(double)rate))<.00001).All(x=>x)};
        }
        public static void Build()
        {
            EditorSceneManager.OpenScene(ScenePath);Directory.CreateDirectory("Builds/Sampling19");AssetDatabase.SaveAssets();var before=SourcesNow();File.WriteAllText(Evidence+"19_prebuild_sources.json",JsonUtility.ToJson(new Sources{files=before},true));
            var result=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},target=BuildTarget.StandaloneWindows64,locationPathName="Builds/Sampling19/GreatWave19.exe",options=BuildOptions.Development});AssetDatabase.SaveAssets();var after=SourcesNow();File.WriteAllText(Evidence+"19_build_sources.json",JsonUtility.ToJson(new Sources{files=after},true));var changed=before.Select(f=>f.path).Union(after.Select(f=>f.path)).Where(p=>!before.Any(b=>b.path==p&&after.Any(a=>a.path==p&&a.sha256==b.sha256))).ToArray();var report=new BuildInfo{unity=Application.unityVersion,utc=DateTime.UtcNow.ToString("O"),scene=ScenePath,result=result.summary.result.ToString(),errors=result.summary.totalErrors,warnings=result.summary.totalWarnings,bytes=result.summary.totalSize.ToString(),buildModifiedFiles=changed,passed=result.summary.result==BuildResult.Succeeded&&result.summary.totalErrors==0&&changed.Length==0};File.WriteAllText(Evidence+"19_build.json",JsonUtility.ToJson(report,true));if(!report.passed)throw new Exception("19ビルド失敗またはソース変更");Debug.Log("SAMPLING19_BUILD_PASS");
        }
        static SourceFile[]SourcesNow()=>new[]{"Assets","Packages","ProjectSettings"}.SelectMany(f=>Directory.GetFiles(f,"*",SearchOption.AllDirectories)).OrderBy(p=>p).Select(p=>{using(var hash=SHA256.Create())return new SourceFile{path=p.Replace('\\','/'),sha256=BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(p))).Replace("-","").ToLowerInvariant()};}).ToArray();
        [Serializable]class SourceFile{public string path,sha256;}[Serializable]class Sources{public SourceFile[]files;}
        [Serializable]class BuildInfo{public string unity,utc,scene,result,bytes;public int errors,warnings;public string[]buildModifiedFiles;public bool passed;}
        [Serializable]class Archive{public string name;public int firstMaster,rate,count;public float[]nativeTimes;public bool passed;}[Serializable]class Archives{public Archive[]archives;public bool passed;}
    }
}
