using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Editor
{
    public static class M1ViewBuilder
    {
        public static void Step14()
        {
            var scene = EditorSceneManager.OpenScene(M1CompositionBuilder.ScenePath);
            var camera = Camera.main;
            var viewer = camera.GetComponent<M1DesktopViewer>() ?? camera.gameObject.AddComponent<M1DesktopViewer>();
            viewer.viewCamera = camera;
            var boat = GameObject.Find("M1 foreground boat");
            // FBX実メッシュの甲板表面を測り、上り勾配を含む実際の着座位置を使う。
            var deckMesh = boat.GetComponentsInChildren<MeshFilter>().Single(f=>f.name=="Boat_Deck_Planks");
            var probe=deckMesh.gameObject.AddComponent<MeshCollider>();
            probe.sharedMesh=deckMesh.sharedMesh;
            var rayOrigin=boat.transform.TransformPoint(new Vector3(0,10,-2));
            Physics.SyncTransforms();
            bool deckHit=probe.Raycast(new Ray(rayOrigin,Vector3.down),out RaycastHit hit,30);
            UnityEngine.Object.DestroyImmediate(probe);
            if(!deckHit) throw new InvalidOperationException("船上の甲板表面を検出できません。");
            var deck = hit.point;
            var seat = deck + Vector3.up * 1.2f;
            viewer.views = new[] {
                new M1DesktopViewer.View { label="原画比較視点", position=M1CompositionBuilder.ComparisonPosition, target=M1CompositionBuilder.ComparisonTarget, fieldOfView=26 },
                new M1DesktopViewer.View { label="船上の着座視点", position=seat, target=new Vector3(-7,12,3), fieldOfView=80 },
                new M1DesktopViewer.View { label="側面・厚みの確認", position=new Vector3(40,16,-1), target=new Vector3(-7,8,2), fieldOfView=55 },
                new M1DesktopViewer.View { label="背面・奥行きの確認", position=new Vector3(-4,16,44), target=new Vector3(-7,8,0), fieldOfView=60 }
            };
            foreach (var view in viewer.views)
            {
                var old = GameObject.Find("Viewpoint " + view.label);
                if (old != null) UnityEngine.Object.DestroyImmediate(old);
                var marker = new GameObject("Viewpoint " + view.label);
                marker.transform.position = view.position; marker.transform.LookAt(view.target);
            }
            var names = new[] { "14_comparison", "14_boat", "14_side", "14_rear" };
            for (int i=0;i<4;i++) { viewer.SelectView(i); M1CompositionBuilder.Render(camera,"../Docs/Evidence/M1/"+names[i]+".png"); }
            viewer.SelectView(1);
            // ワールドX方向0.6mを基線とする幾何的な角度視差。画像移動量やHMD計測ではない。
            Vector3 far = GameObject.Find("M1 distant Fuji").transform.TransformPoint(new Vector3(0,8,0));
            Vector3 near = new Vector3(-5,12,2);
            float farShift = AngularParallax(seat,far,.6f);
            float nearShift = AngularParallax(seat,near,.6f);
            var waveBounds=M1CompositionBuilder.BoundsOf(GameObject.Find("M1 main wave - static geometry"));
            bool outside = !waveBounds.Contains(seat);
            var result = new ViewResult { views = viewer.views, seatWorld=seat, deckWorld=deck, eyeAboveDeck=seat.y-deck.y,
                importedDeckSurfaceMeasured=deckHit,deckTriangle=hit.triangleIndex,deckSurfaceNormal=hit.normal,
                nearProbeWorld=near,farProbeWorld=far,baselineDirection=Vector3.right,
                cameraOutsideMainWaveBounds=outside, comparisonAndSeatDistinct=Vector3.Distance(seat,viewer.views[0].position)>20,
                lateralBaseline=.6f, fujiAngularParallaxDegrees=farShift, nearWaveAngularParallaxDegrees=nearShift,
                farParallaxLower=farShift<nearShift*.15f, hmdVerified=false };
            result.passed = deckHit && Vector3.Dot(hit.normal,Vector3.up)>.99f && outside && result.comparisonAndSeatDistinct && Mathf.Abs(result.eyeAboveDeck-1.2f)<.001f && result.farParallaxLower;
            File.WriteAllText("../Docs/Evidence/M1/14_views.json",JsonUtility.ToJson(result,true));
            if(!result.passed) throw new InvalidOperationException("14の視点検査に失敗しました。");
            viewer.SelectView(0);
            EditorSceneManager.SaveScene(scene); AssetDatabase.SaveAssets();
            Debug.Log("M1_STEP14_PASS: four desktop viewpoints; HMD unverified");
        }
        static float AngularParallax(Vector3 eye,Vector3 target,float baseline) { return Vector3.Angle(target-eye-Vector3.right*baseline*.5f,target-eye+Vector3.right*baseline*.5f); }
        [Serializable] class ViewResult
        {
            public M1DesktopViewer.View[] views;
            public Vector3 seatWorld,deckWorld,deckSurfaceNormal,nearProbeWorld,farProbeWorld,baselineDirection;
            public int deckTriangle;
            public float eyeAboveDeck,lateralBaseline,fujiAngularParallaxDegrees,nearWaveAngularParallaxDegrees;
            public bool importedDeckSurfaceMeasured,cameraOutsideMainWaveBounds,comparisonAndSeatDistinct,farParallaxLower,hmdVerified,passed;
        }
    }
}
