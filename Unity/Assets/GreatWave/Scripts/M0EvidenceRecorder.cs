using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace GreatWave
{
    public class M0EvidenceRecorder : MonoBehaviour
    {
        const int Frames = 480;
        const int Rate = 24;
        public M0ViewController controller;
        public Material captionPanelMaterial;

        IEnumerator Start()
        {
            var args = Environment.GetCommandLineArgs();
            int index = Array.IndexOf(args, "--capture-dir");
            if (index < 0 || index + 1 >= args.Length) yield break;
            if (Array.IndexOf(args, "--vr") >= 0)
            {
                UnityEngine.Debug.LogError("証拠用PCカメラとVRを同時に起動できません。");
                Application.Quit(2);
                yield break;
            }
            string destination = Path.GetFullPath(args[index + 1]);
            Directory.CreateDirectory(destination);
            yield return null;
            yield return null;
            var report = new CaptureReport { unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName,
                graphicsApi = SystemInfo.graphicsDeviceType.ToString(), width = Screen.width, height = Screen.height,
                startedUtc = DateTime.UtcNow.ToString("O"), mode = "PC実行ビルド・オフスクリーン描画・記録用自動カメラ", frameRate = Rate,
                performanceMeasurement = false, hmdStatus = "未検証", inputTestMethod = "Input System仮想キーボードのイベント。物理キー操作ではない" };
            // 実行ビルドの入力経路にイベントを流し、直接メソッド呼出だけの検査と分ける。
            var keyboard = InputSystem.AddDevice<Keyboard>();
            var previousFocusBehavior = InputSystem.settings.backgroundBehavior;
            InputSystem.settings.backgroundBehavior = InputSettings.BackgroundBehavior.IgnoreFocus;
            controller.inputTestKeyboard = keyboard;
            controller.ResetView();
            Quaternion initial = controller.viewCamera.transform.localRotation;
            InputSystem.QueueStateEvent(keyboard, new KeyboardState(Key.RightArrow));
            float inputUntil = Time.realtimeSinceStartup + .2f;
            while (Time.realtimeSinceStartup < inputUntil) yield return null;
            InputSystem.QueueStateEvent(keyboard, new KeyboardState());
            yield return null;
            report.inputLookChanged = Quaternion.Angle(initial, controller.viewCamera.transform.localRotation) > .1f;
            InputSystem.QueueStateEvent(keyboard, new KeyboardState(Key.Space));
            yield return null;
            yield return null;
            InputSystem.QueueStateEvent(keyboard, new KeyboardState());
            yield return null;
            var stopped = controller.viewCamera.transform.localRotation;
            InputSystem.QueueStateEvent(keyboard, new KeyboardState(Key.RightArrow));
            for (int i = 0; i < 5; i++) yield return null;
            report.inputPauseHeld = controller.Paused && Quaternion.Angle(stopped, controller.viewCamera.transform.localRotation) < .001f;
            InputSystem.QueueStateEvent(keyboard, new KeyboardState(Key.R));
            yield return null;
            yield return null;
            report.inputResetRestored = !controller.Paused && Quaternion.Angle(initial, controller.viewCamera.transform.localRotation) < .001f;
            InputSystem.QueueStateEvent(keyboard, new KeyboardState());
            yield return null;
            InputSystem.RemoveDevice(keyboard);
            controller.inputTestKeyboard = null;
            InputSystem.settings.backgroundBehavior = previousFocusBehavior;
            if (!(report.inputLookChanged && report.inputPauseHeld && report.inputResetRestored))
            {
                File.WriteAllText(Path.Combine(destination, "capture_report.json"), JsonUtility.ToJson(report, true));
                UnityEngine.Debug.LogError("M0_INPUT_EVENT_TEST_FAILED");
                Application.Quit(3);
                yield break;
            }
            controller.ResetView();
            controller.recordingCamera = true;
            var watch = Stopwatch.StartNew();
            Time.captureFramerate = Rate;
            var camera = controller.viewCamera;
            var seatedPosition = camera.transform.position;
            var renderTarget = new RenderTexture(1280, 720, 24, RenderTextureFormat.ARGB32);
            renderTarget.Create();
            camera.targetTexture = renderTarget;
            camera.cullingMask &= ~(1 << 31);
            var overlay = new GameObject("Evidence labels camera").AddComponent<Camera>();
            overlay.transform.position = new Vector3(1000, 1000, 1000);
            overlay.orthographic = true;
            overlay.orthographicSize = 360;
            overlay.aspect = 1280f / 720;
            overlay.nearClipPlane = .1f;
            overlay.farClipPlane = 20;
            overlay.clearFlags = CameraClearFlags.Depth;
            overlay.cullingMask = 1 << 31;
            overlay.targetTexture = renderTarget;
            overlay.enabled = false;
            var font = Font.CreateDynamicFontFromOSFont(new[] { "Yu Gothic", "Meiryo", "Microsoft YaHei UI", "MS Gothic" }, 32);
            Panel(overlay, new Vector3(-350, 281, 8), new Vector3(555, 128, .1f), captionPanelMaterial);
            Panel(overlay, new Vector3(0, -310, 8), new Vector3(1232, 54, .1f), captionPanelMaterial);
            Label(overlay, font, "神奈川沖浪裏 — M0 静止船", new Vector3(-600, 325, 7), 26);
            Label(overlay, font, "PC確認版 / HMD未検証", new Vector3(-600, 283, 7), 20);
            Label(overlay, font, "新規の検証用モデル・平面 / 波と操船は未実装", new Vector3(-600, 248, 7), 16);
            var caption = Label(overlay, font, "記録用自動カメラ", new Vector3(-600, -294, 7), 18);
            report.renderMethod = "Unity Camera.Render + 注記用Camera → RenderTexture → ReadPixels（画面提示の録画ではない）";
            report.width = renderTarget.width;
            report.height = renderTarget.height;
            report.minimumNonBlackFraction = 1;
            report.minimumSampledColors = int.MaxValue;
            for (int frame = 0; frame < Frames; frame++)
            {
                float t = frame / (float)Rate;
                if (t < 6)
                {
                    camera.transform.position = seatedPosition;
                    camera.transform.rotation = Quaternion.Euler(12, 24 * Mathf.Sin(t * .6f), 0);
                    controller.recordingLabel = "着座視点・見回し";
                }
                else if (t < 11)
                {
                    float angle = (t - 6) * 7;
                    camera.transform.position = new Vector3(7 * Mathf.Cos(angle * Mathf.Deg2Rad), 4.8f, -4.8f);
                    camera.transform.LookAt(new Vector3(0, .4f, 1.4f));
                    controller.recordingLabel = "静止船の外観・検証用の箱形状";
                }
                else if (t < 16)
                {
                    camera.transform.position = new Vector3(-10, 4.8f, 0);
                    camera.transform.LookAt(new Vector3(-5.5f, 1.65f, 6.9f));
                    controller.recordingLabel = "Blender校正モデル・1m箱と非対称の目印";
                }
                else
                {
                    camera.transform.position = seatedPosition;
                    camera.transform.rotation = Quaternion.Euler(8 + 8 * Mathf.Sin((t - 16) * .8f), -22 * Mathf.Sin((t - 16) * .7f), 0);
                    controller.recordingLabel = "着座へ復帰 / M0のHMD検証は保留";
                }
                caption.text = "自動カメラ / " + controller.recordingLabel + " / オフスクリーン描画・HMD未検証";
                yield return new WaitForEndOfFrame();
                camera.Render();
                overlay.Render();
                RenderTexture.active = renderTarget;
                var screenshot = new Texture2D(1280, 720, TextureFormat.RGB24, false);
                screenshot.ReadPixels(new Rect(0, 0, 1280, 720), 0, 0);
                screenshot.Apply();
                RenderTexture.active = null;
                var pixels = screenshot.GetPixels32();
                int count = 0, nonBlack = 0;
                var colors = new HashSet<int>();
                for (int p = 0; p < pixels.Length; p += 499)
                {
                    var c = pixels[p]; count++;
                    if (c.r > 8 || c.g > 8 || c.b > 8) nonBlack++;
                    colors.Add((c.r << 16) | (c.g << 8) | c.b);
                }
                report.minimumNonBlackFraction = Math.Min(report.minimumNonBlackFraction, nonBlack / (float)count);
                report.minimumSampledColors = Math.Min(report.minimumSampledColors, colors.Count);
                File.WriteAllBytes(Path.Combine(destination, "frame_" + frame.ToString("D4") + ".png"), screenshot.EncodeToPNG());
                Destroy(screenshot);
                report.capturedFrames++;
            }
            watch.Stop();
            Time.captureFramerate = 0;
            report.captureWallSeconds = watch.Elapsed.TotalSeconds;
            report.finishedUtc = DateTime.UtcNow.ToString("O");
            report.passed = report.capturedFrames == Frames && report.inputLookChanged && report.inputPauseHeld && report.inputResetRestored
                && report.width == 1280 && report.height == 720 && report.minimumNonBlackFraction > .2f
                && report.minimumSampledColors >= 8;
            File.WriteAllText(Path.Combine(destination, "capture_report.json"), JsonUtility.ToJson(report, true));
            UnityEngine.Debug.Log("M0_CAPTURE_COMPLETE: frames=" + report.capturedFrames + "; synthetic24fps; HMD未検証");
            Application.Quit(report.passed ? 0 : 4);
        }

        static void Panel(Camera camera, Vector3 position, Vector3 size, Material material)
        {
            var panel = GameObject.CreatePrimitive(PrimitiveType.Cube);
            panel.layer = 31;
            panel.transform.SetParent(camera.transform, false);
            panel.transform.localPosition = position;
            panel.transform.localScale = size;
            panel.GetComponent<Renderer>().sharedMaterial = material;
        }

        static TextMesh Label(Camera camera, Font font, string text, Vector3 position, float pixels)
        {
            var item = new GameObject("Evidence Japanese label");
            item.layer = 31;
            item.transform.SetParent(camera.transform, false);
            item.transform.localPosition = position;
            var label = item.AddComponent<TextMesh>();
            label.font = font;
            label.fontSize = 32;
            label.characterSize = 1;
            label.anchor = TextAnchor.UpperLeft;
            label.color = new Color(.97f, .95f, .88f);
            label.text = text;
            var renderer = item.GetComponent<MeshRenderer>();
            renderer.sharedMaterial = font.material;
            float height = renderer.bounds.size.y;
            item.transform.localScale = Vector3.one * (pixels / Mathf.Max(.001f, height));
            return label;
        }

        [Serializable] class CaptureReport
        {
            public string unity, device, graphicsApi, startedUtc, finishedUtc, mode, hmdStatus, inputTestMethod, renderMethod;
            public int width, height, frameRate, capturedFrames, minimumSampledColors;
            public float minimumNonBlackFraction;
            public double captureWallSeconds;
            public bool performanceMeasurement, inputLookChanged, inputPauseHeld, inputResetRestored, passed;
        }
    }
}
