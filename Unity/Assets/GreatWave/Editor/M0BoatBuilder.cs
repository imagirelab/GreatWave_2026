using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem.XR;
using Unity.XR.CoreUtils;

namespace GreatWave.Editor
{
    public static class M0BoatBuilder
    {
        [MenuItem("GreatWave/09 静止船とPC視点を作成")]
        public static void Create()
        {
            var scene = EditorSceneManager.OpenScene(M0BaselineBuilder.ScenePath);
            var old = GameObject.Find("M0 stationary test boat");
            if (old != null) UnityEngine.Object.DestroyImmediate(old);
            var boat = new GameObject("M0 stationary test boat");
            var wood = M0BaselineBuilder.Material("M0_DeckWood", new Color(.56f, .35f, .18f));
            var pale = M0BaselineBuilder.Material("M0_DeckPale", new Color(.71f, .51f, .29f));
            var dark = M0BaselineBuilder.Material("M0_Rails", new Color(.29f, .20f, .12f));
            M0BaselineBuilder.Box("Hull test block", new Vector3(0, .02f, 1.5f), new Vector3(2.4f, .4f, 7.4f), wood, boat.transform);
            for (int i = 0; i < 13; i++)
                M0BaselineBuilder.Box("Deck plank " + i, new Vector3(-1.1f + i * .1833f, .25f, 1.5f),
                    new Vector3(.176f, .1f, 7.1f), i % 3 == 0 ? wood : pale, boat.transform);
            foreach (float x in new[] { -1.16f, 1.16f })
            {
                M0BaselineBuilder.Box("Solid side " + x, new Vector3(x, .62f, 1.5f), new Vector3(.14f, .66f, 7.4f), wood, boat.transform);
                M0BaselineBuilder.Box("Side rail " + x, new Vector3(x, .99f, 1.5f), new Vector3(.19f, .12f, 7.45f), dark, boat.transform);
            }
            foreach (float z in new[] { -2.15f, 5.15f })
            {
                M0BaselineBuilder.Box("End board " + z, new Vector3(0, .62f, z), new Vector3(2.35f, .66f, .14f), wood, boat.transform);
                M0BaselineBuilder.Box("End rail " + z, new Vector3(0, .99f, z), new Vector3(2.5f, .12f, .19f), dark, boat.transform);
            }
            foreach (float z in new[] { -1.5f, 1.1f, 3.6f })
                M0BaselineBuilder.Box("Bench " + z, new Vector3(0, .7f, z), new Vector3(2.18f, .1f, .42f), pale, boat.transform);
            var origin = UnityEngine.Object.FindAnyObjectByType<XROrigin>();
            origin.transform.position = new Vector3(0, .3f, -1.5f);
            origin.CameraYOffset = 1.2f;
            origin.CameraFloorOffsetObject.transform.localPosition = new Vector3(0, 1.2f, 0);
            var camera = origin.Camera;
            var controller = origin.GetComponent<M0ViewController>() ?? origin.gameObject.AddComponent<M0ViewController>();
            controller.viewCamera = camera;
            controller.trackedPose = camera.GetComponent<TrackedPoseDriver>();
            controller.ResetView();
            var start = camera.transform.rotation;
            controller.ApplyLook(new Vector2(30, 10));
            bool look = Quaternion.Angle(start, camera.transform.rotation) > 25;
            controller.SetPaused(true);
            var paused = camera.transform.rotation;
            controller.ApplyLook(new Vector2(45, 10));
            bool stopped = Quaternion.Angle(paused, camera.transform.rotation) < .001f;
            controller.ResetView();
            bool reset = Quaternion.Angle(start, camera.transform.rotation) < .001f && !controller.Paused;
            var renderers = boat.GetComponentsInChildren<Renderer>();
            var boatBounds = renderers[0].bounds;
            foreach (var renderer in renderers) boatBounds.Encapsulate(renderer.bounds);
            float deckTop = boat.transform.Find("Deck plank 0").GetComponent<Renderer>().bounds.max.y;
            float railTop = boat.transform.Find("End rail 5.15").GetComponent<Renderer>().bounds.max.y;
            float seatTop = boat.transform.Find("Bench -1.5").GetComponent<Renderer>().bounds.max.y;
            var report = new Report { deckTopY = deckTop, railTopY = railTop, seatTopY = seatTop, eyeY = camera.transform.position.y,
                eyePosition = camera.transform.position, boatSize = boatBounds.size,
                viewChanges = look, pauseStopsLook = stopped, resetRestoresView = reset,
                cameraAboveRails = camera.transform.position.y > railTop, physicalKeyboardTest = "未実施・入力処理の数値検査のみ",
                hmdStatus = "実寸・頭部移動・快適性は機器入手後" };
            report.passed = look && stopped && reset && report.cameraAboveRails;
            File.WriteAllText("../Docs/Evidence/M0/09_desktop_controls.json", JsonUtility.ToJson(report, true));
            if (!report.passed) throw new InvalidOperationException("09の視点・停止・リセット検査が不合格です。");
            EditorSceneManager.SaveScene(scene);
            AssetDatabase.SaveAssets();
            Debug.Log("M0_STEP09_PASS: desktop command tests passed; HMD未検証");
        }
        [Serializable] class Report
        {
            public float deckTopY, railTopY, seatTopY, eyeY;
            public Vector3 eyePosition, boatSize;
            public bool viewChanges, pauseStopsLook, resetRestoresView, cameraAboveRails, passed;
            public string physicalKeyboardTest, hmdStatus;
        }
    }
}
