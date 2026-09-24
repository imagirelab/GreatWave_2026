using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Editor
{
    public static class M1DeliveryBuilder
    {
        public static void Step15()
        {
            var scene=EditorSceneManager.OpenScene(M1CompositionBuilder.ScenePath);
            var viewer=UnityEngine.Object.FindAnyObjectByType<M1DesktopViewer>();
            // 14の見上げ検査記録を残し、配布時は船縁がフッターの上に見える初期向きにする。
            viewer.views[1].target=new Vector3(-7,4,3);
            var seatMarker=GameObject.Find("Viewpoint 船上の着座視点");
            if(seatMarker!=null) seatMarker.transform.LookAt(viewer.views[1].target);
            var old=GameObject.Find("M1 provisional region overlay");
            if(old!=null) UnityEngine.Object.DestroyImmediate(old);
            var map=new GameObject("M1 provisional region overlay"); viewer.mapOverlay=map;
            var wave=M1CompositionBuilder.BoundsOf(GameObject.Find("M1 main wave - static geometry"));
            wave.Encapsulate(M1CompositionBuilder.BoundsOf(GameObject.Find("M1 static foam and foreground swell")));
            var exclusion=Rect.MinMaxRect(wave.min.x-.5f,wave.min.z-.5f,wave.max.x+.5f,wave.max.z+.5f);
            var region=Rect.MinMaxRect(17,-22,31,-3);
            var route=new[] {new Vector3(18,.7f,-20),new Vector3(18,.7f,-12),new Vector3(24,.7f,-6)};
            Outline(map,"波の水平投影・立入候補から除外",exclusion,22,new Color(.9f,.28f,.2f));
            Outline(map,"将来の観賞・航行候補（船中心のみ）",region,.7f,new Color(.58f,.9f,.45f));
            Line(map,"候補経路・未走行",route,new Color(.88f,.9f,.52f),.16f);
            var boat=GameObject.Find("M1 foreground boat");
            float radius=boat.GetComponentsInChildren<MeshFilter>().SelectMany(f=>f.sharedMesh.vertices.Select(v=>f.transform.TransformPoint(v)-boat.transform.position)).Max(v=>new Vector2(v.x,v.z).magnitude);
            float separationX=Mathf.Max(0,Mathf.Max(region.xMin-exclusion.xMax,exclusion.xMin-region.xMax));
            float separationZ=Mathf.Max(0,Mathf.Max(region.yMin-exclusion.yMax,exclusion.yMin-region.yMax));
            float clearance=new Vector2(separationX,separationZ).magnitude;
            bool envelopeClear=clearance>=radius+1;
            var marker=GameObject.CreatePrimitive(PrimitiveType.Sphere); marker.name="現在の構図用船の中心";
            marker.transform.SetParent(map.transform); marker.transform.position=boat.transform.position+Vector3.up*3;
            marker.transform.localScale=Vector3.one*.7f;
            marker.GetComponent<Renderer>().sharedMaterial=M1CompositionBuilder.Mat("M1_MapBoat",new Color(1,.6f,.15f));
            viewer.views=viewer.views.Take(4).Concat(new[] {new M1DesktopViewer.View {label="仮の範囲図・操船未実装",position=new Vector3(0,70,0),target=Vector3.zero,orthographic=true,orthographicSize=32.5f}}).ToArray();
            bool disjoint=!region.Overlaps(exclusion);
            bool routeInside=route.All(p=>region.Contains(new Vector2(p.x,p.z)));
            var report=new MapResult {waveProjectionExclusion=exclusion,candidateCenterRegion=region,route=route,
                finalBoatView=viewer.views[1],
                currentCompositionBoatCenter=boat.transform.position,candidateAndWaveProjectionDisjoint=disjoint,routePointsInsideCandidate=routeInside,
                conservativeBoatRadius=radius,provisionalMargin=1,minimumRegionToExclusionDistance=clearance,staticHorizontalEnvelopeClear=envelopeClear,
                boatFootprintClearanceVerified=false,boatPhysicsImplemented=false,passed=disjoint&&routeInside&&envelopeClear,
                note="上面図の船中心候補。実頂点から求めた水平半径+1mを波投影から確保。静止包絡だけの検査で、水面変動・衝突・快適性・実操船は未検証。現在の構図用船は候補範囲外。富士は図外。"};
            File.WriteAllText("../Docs/Evidence/M1/15_region.json",JsonUtility.ToJson(report,true));
            if(!report.passed) throw new InvalidOperationException("15の候補範囲が投影境界と重複しています。");
            viewer.SelectView(4); M1CompositionBuilder.Render(viewer.viewCamera,"../Docs/Evidence/M1/15_region_early.png");
            viewer.SelectView(0);
            var recorder=viewer.GetComponent<M1EvidenceRecorder>()??viewer.gameObject.AddComponent<M1EvidenceRecorder>();
            recorder.viewer=viewer;
            recorder.captionMaterial=M1CompositionBuilder.Mat("M1_CaptionPanel",new Color(.035f,.09f,.14f));
            EditorSceneManager.SaveScene(scene); AssetDatabase.SaveAssets();
            Debug.Log("M1_STEP15_REGION_PASS: candidate map only; no navigation physics");
        }

        static void Outline(GameObject parent,string name,Rect bounds,float y,Color color)
        { Line(parent,name,new[] {new Vector3(bounds.xMin,y,bounds.yMin),new Vector3(bounds.xMax,y,bounds.yMin),new Vector3(bounds.xMax,y,bounds.yMax),new Vector3(bounds.xMin,y,bounds.yMax),new Vector3(bounds.xMin,y,bounds.yMin)},color,.18f); }
        static void Line(GameObject parent,string name,Vector3[] points,Color color,float width)
        {
            var go=new GameObject(name); go.transform.SetParent(parent.transform);
            var line=go.AddComponent<LineRenderer>(); line.positionCount=points.Length; line.SetPositions(points); line.widthMultiplier=width;
            line.sharedMaterial=M1CompositionBuilder.Mat("M1_Map_"+ColorUtility.ToHtmlStringRGB(color),color);
        }

        public static void Build()
        {
            EditorSceneManager.OpenScene(M1CompositionBuilder.ScenePath);
            var viewer=UnityEngine.Object.FindAnyObjectByType<M1DesktopViewer>();
            if(viewer==null||viewer.views.Length!=5||viewer.GetComponent<M1EvidenceRecorder>()==null) throw new InvalidOperationException("15のシーンを先に生成してください。");
            Directory.CreateDirectory("Builds/M1");
            AssetDatabase.SaveAssets();
            var sources=SourcesNow();
            File.WriteAllText("../Docs/Evidence/M1/15_prebuild_sources.json",JsonUtility.ToJson(new Sources{files=sources},true));
            var build=BuildPipeline.BuildPlayer(new BuildPlayerOptions{scenes=new[]{M1CompositionBuilder.ScenePath},target=BuildTarget.StandaloneWindows64,locationPathName="Builds/M1/GreatWaveM1.exe",options=BuildOptions.Development});
            AssetDatabase.SaveAssets();
            var after=SourcesNow();
            var modified=after.Where(f=>!sources.Any(b=>b.path==f.path&&b.sha256==f.sha256)).Select(f=>f.path).ToArray();
            var summary=new BuildSummary{utc=DateTime.UtcNow.ToString("O"),unity=Application.unityVersion,scene=M1CompositionBuilder.ScenePath,
                result=build.summary.result.ToString(),errors=build.summary.totalErrors,warnings=build.summary.totalWarnings,bytes=build.summary.totalSize.ToString(),seconds=build.summary.totalTime.TotalSeconds,
                buildModifiedFiles=modified,passed=build.summary.result==BuildResult.Succeeded&&build.summary.totalErrors==0};
            File.WriteAllText("../Docs/Evidence/M1/15_build_sources.json",JsonUtility.ToJson(new Sources{files=after},true));
            File.WriteAllText("../Docs/Evidence/M1/15_build.json",JsonUtility.ToJson(summary,true));
            if(!summary.passed) throw new InvalidOperationException("M1のPCビルドに失敗しました。");
            Debug.Log("M1_STEP15_BUILD_PASS: "+summary.bytes+" bytes");
        }
        static SourceFile[] SourcesNow()
        {
            return new[]{"Assets","Packages","ProjectSettings"}.SelectMany(folder=>Directory.GetFiles(folder,"*",SearchOption.AllDirectories)).OrderBy(p=>p).Select(path=>{
                using(var sha=SHA256.Create()) return new SourceFile{path=path.Replace('\\','/'),sha256=BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-","").ToLowerInvariant()};
            }).ToArray();
        }
        [Serializable] class MapResult {public Rect waveProjectionExclusion,candidateCenterRegion;public Vector3[] route;public Vector3 currentCompositionBoatCenter;public M1DesktopViewer.View finalBoatView;public float conservativeBoatRadius,provisionalMargin,minimumRegionToExclusionDistance;public bool staticHorizontalEnvelopeClear,candidateAndWaveProjectionDisjoint,routePointsInsideCandidate,boatFootprintClearanceVerified,boatPhysicsImplemented,passed;public string note;}
        [Serializable] class SourceFile{public string path,sha256;}
        [Serializable] class Sources{public SourceFile[] files;}
        [Serializable] class BuildSummary{public string utc,unity,scene,result,bytes;public int errors,warnings;public double seconds;public string[] buildModifiedFiles;public bool passed;}
    }
}
