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
    public static class Playback18Builder
    {
        public const string ScenePath="Assets/GreatWave/Scenes/Tests/M1_Playback18.unity";
        public const string Art="Assets/GreatWave/Art/Playback18/";
        public const string Evidence="../Docs/Evidence/M1/Playback18/";
        public static void CreateAndValidate()
        {
            Directory.CreateDirectory(Evidence);
            AssetDatabase.ImportAsset(Art+"fluid17.abc",ImportAssetOptions.ForceSynchronousImport);
            var importer=AssetImporter.GetAtPath(Art+"fluid17.abc");var serialized=new SerializedObject(importer);
            var settings=serialized.FindProperty("streamSettings");
            settings.FindPropertyRelative("scaleFactor").floatValue=1;
            settings.FindPropertyRelative("swapHandedness").boolValue=true;
            settings.FindPropertyRelative("flipFaces").boolValue=false;
            settings.FindPropertyRelative("interpolateSamples").boolValue=false;
            serialized.ApplyModifiedPropertiesWithoutUndo();importer.SaveAndReimport();
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var root=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(Art+"fluid17.abc"));root.name="18 実FLIP Alembic";
            var stream=root.GetComponent<AlembicStreamPlayer>();stream.UpdateImmediately(0);
            var material=M1CompositionBuilder.Mat("Playback18_Fluid",new Color(.06f,.32f,.52f));
            material.shader=Shader.Find("GreatWave/Playback18/Reference");EditorUtility.SetDirty(material);
            foreach(var renderer in root.GetComponentsInChildren<MeshRenderer>())
            {renderer.sharedMaterials=renderer.sharedMaterials.Select(_=>material).ToArray();PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);}
            var text=AssetDatabase.LoadAssetAtPath<TextAsset>(Art+"reference.bytes");var reference=Playback18Reference.Read(text);
            var result=Playback18Validation.Alembic(stream,reference);File.WriteAllText(Evidence+"18_alembic_editor_validation.json",JsonUtility.ToJson(result,true));
            var clips=AssetDatabase.LoadAllAssetsAtPath(Art+"fluid17.abc").OfType<AnimationClip>().Select(c=>new Sampling{name=c.name,times=AnimationUtility.GetAnimationEvents(c).Select(e=>e.time).ToArray()}).Where(c=>c.times.Length>0).ToArray();
            var sampling=new ArchiveSampling{method="公式Alembic Importerが実アーカイブaiTimeSamplingから得たAnimationEvents",archiveStart=stream.MediaStartTime,samplings=clips};
            sampling.passed=clips.Any(c=>c.times.Length==49&&c.times.Select((t,i)=>Math.Abs(t-(i+1)/24.0)<.00001).All(x=>x));
            File.WriteAllText(Evidence+"18_archive_sampling.json",JsonUtility.ToJson(sampling,true));
            if(!result.passed||!sampling.passed)throw new InvalidOperationException("18 Alembic座標/法線/接続/時刻の検査が失敗しました。");
            var player=new GameObject("18 2形式・離散時刻の一回再生").AddComponent<Playback18Player>();player.stream=stream;
            if(File.Exists(Art+"VAT/metadata.json"))ConfigureVat(player,reference);
            var camera=new GameObject("18 共通検査カメラ").AddComponent<Camera>();camera.tag="MainCamera";camera.transform.position=new Vector3(10,8,-12);camera.transform.LookAt(new Vector3(0,.6f,0));camera.fieldOfView=45;camera.aspect=1280f/720;camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.82f,.87f,.89f);camera.farClipPlane=100;
            var sun=new GameObject("18 共通照明").AddComponent<Light>();sun.type=LightType.Directional;sun.intensity=1.2f;sun.transform.rotation=Quaternion.Euler(50,-35,0);RenderSettings.ambientLight=new Color(.48f,.52f,.56f);
            var floor=GameObject.CreatePrimitive(PrimitiveType.Plane);floor.name="18 寸法床";floor.transform.position=new Vector3(0,-.1f,0);floor.transform.localScale=Vector3.one*1.6f;floor.GetComponent<Renderer>().sharedMaterial=M1CompositionBuilder.Mat("Playback18_Floor",new Color(.25f,.29f,.31f));
            var recorder=player.gameObject.AddComponent<Playback18Recorder>();recorder.player=player;recorder.cameraToRender=camera;recorder.reference=text;recorder.captionMaterial=M1CompositionBuilder.Mat("Playback18_Caption",new Color(.025f,.065f,.1f));
            stream.UpdateImmediately(1);Playback18Validation.RefreshBounds(stream);M1CompositionBuilder.Render(camera,Evidence+"18_alembic_early.png");stream.UpdateImmediately(0);Playback18Validation.RefreshBounds(stream);
            EditorSceneManager.SaveScene(scene,ScenePath);AssetDatabase.SaveAssets();Debug.Log("PLAYBACK18_ALEMBIC_EDITOR_PASS");
        }
        static void ConfigureVat(Playback18Player player,Playback18Reference reference)
        {
            foreach(string name in new[]{"fluid17_pos.exr","fluid17_rot.exr","fluid17_lookup.exr"})
            {
                string path=Art+"VAT/"+name;AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport);
                var importer=(TextureImporter)AssetImporter.GetAtPath(path);importer.textureType=TextureImporterType.Default;importer.sRGBTexture=false;importer.mipmapEnabled=false;importer.npotScale=TextureImporterNPOTScale.None;importer.filterMode=FilterMode.Point;importer.wrapMode=TextureWrapMode.Repeat;importer.textureCompression=TextureImporterCompression.Uncompressed;importer.maxTextureSize=8192;importer.isReadable=false;
                var platform=importer.GetDefaultPlatformTextureSettings();platform.format=TextureImporterFormat.RGBAFloat;platform.maxTextureSize=8192;platform.textureCompression=TextureImporterCompression.Uncompressed;importer.SetPlatformTextureSettings(platform);
                importer.SetPlatformTextureSettings(new TextureImporterPlatformSettings{name="Standalone",overridden=true,maxTextureSize=8192,format=TextureImporterFormat.RGBAFloat,textureCompression=TextureImporterCompression.Uncompressed});importer.SaveAndReimport();
            }
            string fbx=Art+"VAT/fluid17_mesh.fbx";AssetDatabase.ImportAsset(fbx,ImportAssetOptions.ForceSynchronousImport);
            var model=(ModelImporter)AssetImporter.GetAtPath(fbx);model.globalScale=1;model.useFileScale=true;model.meshCompression=ModelImporterMeshCompression.Off;model.optimizeMeshPolygons=false;model.optimizeMeshVertices=false;model.weldVertices=false;model.isReadable=true;model.importNormals=ModelImporterNormals.Import;model.importTangents=ModelImporterTangents.Import;model.materialImportMode=ModelImporterMaterialImportMode.None;model.SaveAndReimport();
            var root=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(fbx));root.name="18 公式Fluid VAT・専用Built-in復号";
            var data=JsonUtility.FromJson<Playback18VAT.Data>(File.ReadAllText(Art+"VAT/metadata.json"));data.position=AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"VAT/fluid17_pos.exr");data.rotation=AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"VAT/fluid17_rot.exr");data.lookup=AssetDatabase.LoadAssetAtPath<Texture2D>(Art+"VAT/fluid17_lookup.exr");
            float scaledMinZ=data.encodedMin.z*10f,scaledMaxX=-data.encodedMax.x*10f;
            Debug.Log("18_ENCODED_ARITHMETIC minZ="+data.encodedMin.z.ToString("R")+" maxX="+data.encodedMax.x.ToString("R")+" scaledMinZ="+scaledMinZ.ToString("R")+" scaledMaxX="+scaledMaxX.ToString("R")+" activeX="+(1f-(Mathf.Ceil(data.encodedMin.z*10f)-data.encodedMin.z*10f)).ToString("R")+" activeY="+(1f-(scaledMaxX-Mathf.Floor(scaledMaxX))).ToString("R"));
            var meshInfo=root.GetComponentsInChildren<MeshFilter>().Select(f=>new VatMesh{name=f.name,vertices=f.sharedMesh.vertexCount,triangles=f.sharedMesh.triangles.Length/3,scale=f.transform.lossyScale,uvFirst=f.sharedMesh.uv.Take(12).ToArray()}).ToArray();
            File.WriteAllText(Evidence+"18_vat_import.json",JsonUtility.ToJson(new VatImport{meshes=meshInfo,textures=new[]{data.position,data.rotation,data.lookup}.Select(t=>new TextureInfo{name=t.name,width=t.width,height=t.height,format=t.format.ToString(),graphicsFormat=t.graphicsFormat.ToString(),mips=t.mipmapCount,filter=t.filterMode.ToString(),wrap=t.wrapMode.ToString()}).ToArray()},true));
            if(data.position.width!=1024||data.position.height!=1066||data.lookup.width!=2048||data.lookup.height!=6174)throw new InvalidOperationException("VATの実画像寸法が書出し元と違います。");
            var material=M1CompositionBuilder.Mat("Playback18_VAT",new Color(.06f,.32f,.52f));material.shader=Shader.Find(Playback18VAT.ShaderName);Playback18VAT.Bind(material,data,0);EditorUtility.SetDirty(material);
            foreach(var renderer in root.GetComponentsInChildren<MeshRenderer>()){renderer.sharedMaterials=renderer.sharedMaterials.Select(_=>material).ToArray();PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);}
            var compute=AssetDatabase.LoadAssetAtPath<ComputeShader>("Assets/GreatWave/Shaders/Playback18/Playback18VAT.compute");
            var bounds=new Bounds(reference.samples[0].positions[0],Vector3.zero);foreach(var sample in reference.samples)foreach(var p in sample.positions)bounds.Encapsulate(p);bounds.Expand(.002f);player.vatBounds=bounds;
            foreach(var renderer in root.GetComponentsInChildren<Renderer>(true))renderer.localBounds=bounds;
            var measured=Playback18VATValidation.Measure(root,data,compute,reference);File.WriteAllText(Evidence+"18_vat_editor_validation.json",JsonUtility.ToJson(measured,true));
            if(!measured.passed)throw new InvalidOperationException("18 VATの実GPU座標/法線/有向接続検査が失敗しました。");
            player.vatRoot=root;player.vatMaterial=material;player.vatData=data;player.vatDecoder=compute;root.SetActive(false);Debug.Log("PLAYBACK18_VAT_EDITOR_PASS");
        }
        public static void Build()
        {
            EditorSceneManager.OpenScene(ScenePath);Directory.CreateDirectory("Builds/Playback18");AssetDatabase.SaveAssets();
            var before=SourcesNow();File.WriteAllText(Evidence+"18_prebuild_sources.json",JsonUtility.ToJson(new Sources{files=before},true));
            var build=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},target=BuildTarget.StandaloneWindows64,locationPathName="Builds/Playback18/GreatWave18.exe",options=BuildOptions.Development});
            AssetDatabase.SaveAssets();var after=SourcesNow();File.WriteAllText(Evidence+"18_build_sources.json",JsonUtility.ToJson(new Sources{files=after},true));
            var modified=before.Select(f=>f.path).Union(after.Select(f=>f.path)).Where(p=>!before.Any(b=>b.path==p&&after.Any(a=>a.path==p&&a.sha256==b.sha256))).ToArray();
            var result=new BuildInfo{unity=Application.unityVersion,utc=DateTime.UtcNow.ToString("O"),scene=ScenePath,result=build.summary.result.ToString(),errors=build.summary.totalErrors,warnings=build.summary.totalWarnings,bytes=build.summary.totalSize.ToString(),buildModifiedFiles=modified,passed=build.summary.result==BuildResult.Succeeded&&build.summary.totalErrors==0&&modified.Length==0};
            File.WriteAllText(Evidence+"18_build.json",JsonUtility.ToJson(result,true));if(!result.passed)throw new InvalidOperationException("18 PCビルドが失敗しました。");Debug.Log("PLAYBACK18_BUILD_PASS");
        }
        static SourceFile[] SourcesNow()=>new[]{"Assets","Packages","ProjectSettings"}.SelectMany(f=>Directory.GetFiles(f,"*",SearchOption.AllDirectories)).OrderBy(p=>p).Select(p=>{using(var hash=SHA256.Create())return new SourceFile{path=p.Replace('\\','/'),sha256=BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(p))).Replace("-","").ToLowerInvariant()};}).ToArray();
        [Serializable]class SourceFile{public string path,sha256;}
        [Serializable]class Sources{public SourceFile[]files;}
        [Serializable]class BuildInfo{public string unity,utc,scene,result,bytes;public string[]buildModifiedFiles;public int errors,warnings;public bool passed;}
        [Serializable]class Sampling{public string name;public float[]times;}
        [Serializable]class ArchiveSampling{public string method;public float archiveStart;public Sampling[]samplings;public bool passed;}
        [Serializable]class VatImport{public VatMesh[]meshes;public TextureInfo[]textures;}
        [Serializable]class VatMesh{public string name;public int vertices,triangles;public Vector3 scale;public Vector2[]uvFirst;}
        [Serializable]class TextureInfo{public string name,format,graphicsFormat,filter,wrap;public int width,height,mips;}
    }
}

