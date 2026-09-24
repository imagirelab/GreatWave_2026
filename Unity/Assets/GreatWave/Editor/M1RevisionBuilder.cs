using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Editor
{
    public static class M1RevisionBuilder
    {
        public const string ScenePath="Assets/GreatWave/Scenes/Tests/M1_StaticComposition_Revision01.unity";
        const string Evidence="../Docs/Evidence/M1/Revision01/";
        public static void Create()
        {
            var scene=EditorSceneManager.OpenScene(M1CompositionBuilder.ScenePath);
            EditorSceneManager.SaveScene(scene,ScenePath);
            var path="Assets/GreatWave/Art/M1_Revision01/revision_slopes.fbx";
            AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport);
            var importer=(ModelImporter)AssetImporter.GetAtPath(path);importer.globalScale=1;importer.useFileScale=true;importer.bakeAxisConversion=false;importer.importAnimation=false;importer.isReadable=true;importer.SaveAndReimport();
            var slopes=(GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(path));slopes.name="M1 Revision01 static supporting slopes";
            foreach(var renderer in slopes.GetComponentsInChildren<Renderer>())
            {
                renderer.sharedMaterials=renderer.sharedMaterials.Select(m=>M1CompositionBuilder.Mat(m.name,m.name.Contains("Indigo")?new Color(.018f,.10f,.20f):new Color(.065f,.27f,.39f))).ToArray();
                PrefabUtility.RecordPrefabInstancePropertyModifications(renderer);
            }
            var near=GameObject.Find("M1 foreground boat");var middle=GameObject.Find("M1 middle boat");var left=GameObject.Find("M1 left boat");
            Place(near,new Vector3(.7f,-.2f,-32),new Vector3(3,45,0),1.35f);
            Place(middle,new Vector3(11.6f,2,-2),new Vector3(-19,67,0),1.8f);
            Place(left,new Vector3(-15.5f,3.1f,-12),new Vector3(17,62,0),1.1f);
            var viewer=UnityEngine.Object.FindAnyObjectByType<M1DesktopViewer>();var camera=viewer.viewCamera;
            viewer.compactRevisionLayout=true;
            var previousRecorder=viewer.GetComponent<M1EvidenceRecorder>();var caption=previousRecorder.captionMaterial;UnityEngine.Object.DestroyImmediate(previousRecorder);
            var recorder=viewer.gameObject.AddComponent<M1RevisionEvidenceRecorder>();recorder.viewer=viewer;recorder.captionMaterial=caption;
            var deck=near.GetComponentsInChildren<MeshFilter>().Single(f=>f.name=="Boat_Deck_Planks");
            var collider=deck.gameObject.AddComponent<MeshCollider>();collider.sharedMesh=deck.sharedMesh;Physics.SyncTransforms();
            var probe=near.transform.TransformPoint(new Vector3(0,10,-2));
            bool hitDeck=collider.Raycast(new Ray(probe,Vector3.down),out RaycastHit hit,40);UnityEngine.Object.DestroyImmediate(collider);
            if(!hitDeck)throw new InvalidOperationException("修正した船の実甲板を測れません。");
            var eye=hit.point+Vector3.up*1.2f;
            viewer.views[1].position=eye;viewer.views[1].target=new Vector3(-7,5,3);
            viewer.views[2].position=new Vector3(53,22,-2);viewer.views[2].target=new Vector3(-1,7,0);viewer.views[2].fieldOfView=60;
            viewer.views[3].position=new Vector3(-4,20,55);viewer.views[3].target=new Vector3(0,7,-2);viewer.views[3].fieldOfView=65;
            foreach(var view in viewer.views.Take(4))
            {var marker=GameObject.Find("Viewpoint "+view.label);if(marker!=null){marker.transform.position=view.position;marker.transform.LookAt(view.target);}}
            var oldMap=viewer.mapOverlay;UnityEngine.Object.DestroyImmediate(oldMap);
            var map=new GameObject("M1 Revision01 provisional region overlay");viewer.mapOverlay=map;
            var wave=M1CompositionBuilder.BoundsOf(GameObject.Find("M1 main wave - static geometry"));
            wave.Encapsulate(M1CompositionBuilder.BoundsOf(GameObject.Find("M1 static foam and foreground swell")));wave.Encapsulate(M1CompositionBuilder.BoundsOf(slopes));
            var exclusion=Rect.MinMaxRect(wave.min.x-.5f,wave.min.z-.5f,wave.max.x+.5f,wave.max.z+.5f);
            float radius=near.GetComponentsInChildren<MeshFilter>().SelectMany(f=>f.sharedMesh.vertices.Select(v=>f.transform.TransformPoint(v)-near.transform.position)).Max(v=>new Vector2(v.x,v.z).magnitude);
            float candidateMin=Mathf.Ceil(exclusion.xMax+radius+2);var region=Rect.MinMaxRect(candidateMin,-22,candidateMin+14,-3);
            var route=new[]{new Vector3(candidateMin+2,.7f,-20),new Vector3(candidateMin+2,.7f,-12),new Vector3(candidateMin+9,.7f,-6)};
            Outline(map,"波の水平投影",exclusion,24,new Color(.9f,.28f,.2f));Outline(map,"船中心の候補",region,.7f,new Color(.58f,.9f,.45f));Line(map,"未走行の候補経路",route,new Color(.88f,.9f,.52f));
            var dot=GameObject.CreatePrimitive(PrimitiveType.Sphere);dot.name="現在の構図用船";dot.transform.SetParent(map.transform);dot.transform.position=near.transform.position+Vector3.up*3;dot.transform.localScale=Vector3.one*.7f;dot.GetComponent<Renderer>().sharedMaterial=M1CompositionBuilder.Mat("M1_MapBoat",new Color(1,.6f,.15f));
            viewer.views[4].position=new Vector3(10,85,0);viewer.views[4].target=new Vector3(10,0,0);viewer.views[4].orthographicSize=42;
            viewer.SelectView(0);camera.aspect=1280f/720;
            var temporaryColliders=new List<MeshCollider>();
            foreach(var filter in scene.GetRootGameObjects().SelectMany(g=>g.GetComponentsInChildren<MeshFilter>()))
            {
                if(filter.GetComponent<Collider>()!=null)continue;
                var meshCollider=filter.gameObject.AddComponent<MeshCollider>();meshCollider.sharedMesh=filter.sharedMesh;temporaryColliders.Add(meshCollider);
            }
            Physics.SyncTransforms();
            var boats=new[]{left,middle,near}.Select(b=>MeasureBoat(camera,b)).ToArray();
            foreach(var meshCollider in temporaryColliders)UnityEngine.Object.DestroyImmediate(meshCollider);
            int boatCount=scene.GetRootGameObjects().Count(g=>g.name.EndsWith(" boat"));
            float clearance=region.xMin-exclusion.xMax;
            var report=new RevisionResult{unity=Application.unityVersion,boats=boats,eyeWorld=eye,deckWorld=hit.point,deckNormal=hit.normal,eyeAboveDeck=eye.y-hit.point.y,deckMeasured=hitDeck,
                waveBoundsMin=wave.min,waveBoundsMax=wave.max,exclusion=exclusion,candidateRegion=region,boatRadius=radius,minimumClearance=clearance,
                envelopeClear=clearance>=radius+1,comparisonCameraPosition=camera.transform.position,comparisonCameraTarget=M1CompositionBuilder.ComparisonTarget,comparisonAspect=camera.aspect,
                fujiViewport=M1CompositionBuilder.ProjectedBounds(camera,GameObject.Find("M1 distant Fuji")),boatCount=boatCount,currentBoatOutsideCandidate=!region.Contains(new Vector2(near.transform.position.x,near.transform.position.z)),route=route,
                staticNotFluid=true,physicalNavigationVerified=false,hmdVerified=false};
            report.passed=hitDeck&&Mathf.Abs(report.eyeAboveDeck-1.2f)<.001f&&Vector3.Dot(hit.normal,Vector3.up)>.90f&&report.envelopeClear&&boatCount==3&&boats.All(b=>b.projectedBounds.width>.15f&&b.visibleSamples>=3)&&report.currentBoatOutsideCandidate&&route.All(p=>region.Contains(new Vector2(p.x,p.z)));
            File.WriteAllText(Evidence+"15_revision_layout.json",JsonUtility.ToJson(report,true));
            if(!report.passed)throw new InvalidOperationException("修正構図の寸法・着座・静止包絡が不合格です。");
            var labels=new[]{"comparison","boat","side","rear","region"};
            for(int i=0;i<5;i++){viewer.SelectView(i);M1CompositionBuilder.Render(camera,Evidence+"draft3_"+labels[i]+".png");}
            viewer.SelectView(0);EditorSceneManager.SaveScene(scene);AssetDatabase.SaveAssets();
            Debug.Log("M1_REVISION01_LAYOUT_PASS");
        }
        static BoatPlacement MeasureBoat(Camera camera,GameObject boat)
        {
            var result=new BoatPlacement{name=boat.name,position=boat.transform.position,rotation=boat.transform.eulerAngles,scale=boat.transform.localScale.x,projectedBounds=M1CompositionBuilder.ProjectedBounds(camera,boat)};
            var points=boat.GetComponentsInChildren<MeshFilter>().SelectMany(f=>f.sharedMesh.vertices.Select(v=>f.transform.TransformPoint(v))).ToArray();
            for(int i=0;i<points.Length;i+=13)
            {
                var point=points[i];var viewport=camera.WorldToViewportPoint(point);
                if(viewport.z<=0||viewport.x<0||viewport.x>1||viewport.y<0||viewport.y>1)continue;
                result.testedSamples++;var ray=point-camera.transform.position;
                if(Physics.Raycast(camera.transform.position,ray.normalized,out RaycastHit hit,ray.magnitude+.05f)&&hit.transform.IsChildOf(boat.transform))result.visibleSamples++;
            }
            return result;
        }
        public static void Build()
        {
            EditorSceneManager.OpenScene(ScenePath);Directory.CreateDirectory("Builds/M1_Revision01");AssetDatabase.SaveAssets();
            var before=SourcesNow();File.WriteAllText(Evidence+"15_prebuild_sources.json",JsonUtility.ToJson(new Sources{files=before},true));
            var build=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{ScenePath},target=BuildTarget.StandaloneWindows64,locationPathName="Builds/M1_Revision01/GreatWaveM1Revision01.exe",options=BuildOptions.Development});
            AssetDatabase.SaveAssets();var after=SourcesNow();
            var modified=before.Select(f=>f.path).Union(after.Select(f=>f.path)).Where(p=>!before.Any(b=>b.path==p&&after.Any(a=>a.path==p&&a.sha256==b.sha256))).ToArray();
            var report=new BuildInfo{unity=Application.unityVersion,utc=DateTime.UtcNow.ToString("O"),scene=ScenePath,result=build.summary.result.ToString(),errors=build.summary.totalErrors,warnings=build.summary.totalWarnings,bytes=build.summary.totalSize.ToString(),buildModifiedFiles=modified,passed=build.summary.result==BuildResult.Succeeded&&build.summary.totalErrors==0};
            File.WriteAllText(Evidence+"15_build_sources.json",JsonUtility.ToJson(new Sources{files=after},true));File.WriteAllText(Evidence+"15_build.json",JsonUtility.ToJson(report,true));
            if(!report.passed)throw new InvalidOperationException("修正01のWindowsビルドが失敗しました。");
            Debug.Log("M1_REVISION01_BUILD_PASS");
        }
        public static void ReferenceAspect()
        {
            foreach(var entry in new[]{new[]{M1CompositionBuilder.ScenePath,"before_reference_aspect.png"},new[]{ScenePath,"after_reference_aspect.png"}})
            {
                EditorSceneManager.OpenScene(entry[0]);var viewer=UnityEngine.Object.FindAnyObjectByType<M1DesktopViewer>();viewer.SelectView(0);var camera=viewer.viewCamera;
                camera.aspect=1200f/807;var target=new RenderTexture(1200,807,24);target.Create();camera.targetTexture=target;camera.Render();RenderTexture.active=target;
                var texture=new Texture2D(1200,807,TextureFormat.RGB24,false);texture.ReadPixels(new Rect(0,0,1200,807),0,0);texture.Apply();
                File.WriteAllBytes(Evidence+entry[1],texture.EncodeToPNG());camera.targetTexture=null;RenderTexture.active=null;target.Release();UnityEngine.Object.DestroyImmediate(target);UnityEngine.Object.DestroyImmediate(texture);
            }
            // 比較用の取景だけを変えた。元シーンも修正シーンも保存しない。
            Debug.Log("M1_REVISION01_REFERENCE_ASPECT_RENDERED");
        }
        static SourceFile[] SourcesNow()=>new[]{"Assets","Packages","ProjectSettings"}.SelectMany(f=>Directory.GetFiles(f,"*",SearchOption.AllDirectories)).OrderBy(p=>p).Select(p=>{using(var hash=SHA256.Create())return new SourceFile{path=p.Replace('\\','/'),sha256=BitConverter.ToString(hash.ComputeHash(File.ReadAllBytes(p))).Replace("-","").ToLowerInvariant()};}).ToArray();
        [Serializable]class SourceFile{public string path,sha256;}
        [Serializable]class Sources{public SourceFile[]files;}
        [Serializable]class BuildInfo{public string unity,utc,scene,result,bytes;public string[]buildModifiedFiles;public int errors,warnings;public bool passed;}
        static void Place(GameObject boat,Vector3 position,Vector3 euler,float scale){boat.transform.SetPositionAndRotation(position,Quaternion.Euler(euler));boat.transform.localScale=Vector3.one*scale;}
        static void Outline(GameObject parent,string name,Rect r,float y,Color c)=>Line(parent,name,new[]{new Vector3(r.xMin,y,r.yMin),new Vector3(r.xMax,y,r.yMin),new Vector3(r.xMax,y,r.yMax),new Vector3(r.xMin,y,r.yMax),new Vector3(r.xMin,y,r.yMin)},c);
        static void Line(GameObject parent,string name,Vector3[] positions,Color c){var go=new GameObject(name);go.transform.SetParent(parent.transform);var line=go.AddComponent<LineRenderer>();line.positionCount=positions.Length;line.SetPositions(positions);line.widthMultiplier=.18f;line.sharedMaterial=M1CompositionBuilder.Mat("M1_Map_"+ColorUtility.ToHtmlStringRGB(c),c);}
        [Serializable]class BoatPlacement{public string name;public Vector3 position,rotation;public float scale;public Rect projectedBounds;public int testedSamples,visibleSamples;}
        [Serializable]class RevisionResult{public string unity;public BoatPlacement[]boats;public int boatCount;public Vector3[]route;public Vector3 eyeWorld,deckWorld,deckNormal,waveBoundsMin,waveBoundsMax,comparisonCameraPosition,comparisonCameraTarget;public float eyeAboveDeck,boatRadius,minimumClearance,comparisonAspect;public Rect exclusion,candidateRegion,fujiViewport;public bool deckMeasured,envelopeClear,currentBoatOutsideCandidate,staticNotFluid,physicalNavigationVerified,hmdVerified,passed;}
    }
}
