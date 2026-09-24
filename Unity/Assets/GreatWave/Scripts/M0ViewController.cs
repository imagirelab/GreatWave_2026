using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;
using UnityEngine.XR;
using UnityEngine.XR.Management;

namespace GreatWave
{
    public class M0ViewController : MonoBehaviour
    {
        public Camera viewCamera;
        public TrackedPoseDriver trackedPose;
        public bool recordingCamera;
        public string recordingLabel = "";
        public bool VrActive { get; private set; }
        public bool Paused { get; private set; }
        public string Status { get; private set; } = "PC確認版 / HMD未検証";
        float yaw, pitch = 8;
        Font font;
        GUIStyle titleStyle, textStyle, smallStyle;
        bool ownsXR;

        IEnumerator Start()
        {
            ResetView();
            font = Font.CreateDynamicFontFromOSFont(new[] { "Yu Gothic", "Meiryo", "Microsoft YaHei UI", "MS Gothic" }, 24);
            Debug.Log("M0_DESKTOP_START: " + SystemInfo.graphicsDeviceName + "; " + Screen.width + "x" + Screen.height);
            yield return null;
            if (Array.IndexOf(Environment.GetCommandLineArgs(), "--vr") >= 0)
            {
                Status = "VR起動を試行中 / 実機未検証";
                var manager = XRGeneralSettings.Instance?.Manager;
                if (manager != null)
                {
                    yield return manager.InitializeLoader();
                    if (manager.activeLoader != null)
                    {
                        manager.StartSubsystems();
                        ownsXR = true;
                        var displays = new List<XRDisplaySubsystem>();
                        SubsystemManager.GetSubsystems(displays);
                        VrActive = displays.Exists(display => display.running);
                        if (VrActive)
                        {
                            recordingCamera = false;
                            viewCamera.transform.localPosition = Vector3.zero;
                            viewCamera.transform.localRotation = Quaternion.identity;
                            trackedPose.enabled = true;
                            Status = "VR起動 / 実寸・快適性は要確認";
                        }
                        else StopXR();
                    }
                }
                if (!VrActive)
                {
                    Status = "VRを開始できません / PC確認版へ戻りました";
                    Debug.LogWarning("M0_VR_UNAVAILABLE: desktop fallback; HMD検証は保留");
                }
            }
        }

        void Update()
        {
            var keyboard = Keyboard.current;
            if (keyboard != null)
            {
                if (keyboard.qKey.wasPressedThisFrame) Application.Quit();
                if (keyboard.rKey.wasPressedThisFrame)
                {
                    if (VrActive)
                    {
                        var inputs = new List<XRInputSubsystem>();
                        SubsystemManager.GetSubsystems(inputs);
                        foreach (var input in inputs) input.TryRecenter();
                    }
                    else ResetView();
                }
                if (!VrActive && !recordingCamera)
                {
                    if (keyboard.spaceKey.wasPressedThisFrame) SetPaused(!Paused);
                    if (keyboard.escapeKey.wasPressedThisFrame) SetPaused(true);
                    var horizontal = (keyboard.rightArrowKey.isPressed ? 1 : 0) - (keyboard.leftArrowKey.isPressed ? 1 : 0);
                    var vertical = (keyboard.downArrowKey.isPressed ? 1 : 0) - (keyboard.upArrowKey.isPressed ? 1 : 0);
                    ApplyLook(new Vector2(horizontal, vertical) * (45f * Time.unscaledDeltaTime));
                }
            }
            if (!VrActive && !recordingCamera && Mouse.current != null && Mouse.current.rightButton.isPressed)
            {
                var delta = Mouse.current.delta.ReadValue();
                ApplyLook(new Vector2(delta.x, -delta.y) * .12f);
            }
        }

        public void ApplyLook(Vector2 degrees)
        {
            if (VrActive || Paused || recordingCamera) return;
            yaw = Mathf.Repeat(yaw + degrees.x + 180, 360) - 180;
            pitch = Mathf.Clamp(pitch + degrees.y, -55, 65);
            viewCamera.transform.localRotation = Quaternion.Euler(pitch, yaw, 0);
        }

        public void SetPaused(bool value) { Paused = value; }

        public void ResetView()
        {
            if (VrActive) return;
            yaw = 0; pitch = 8; Paused = false;
            viewCamera.transform.localPosition = Vector3.zero;
            viewCamera.transform.localRotation = Quaternion.Euler(pitch, yaw, 0);
            if (trackedPose != null) trackedPose.enabled = false;
        }

        void StopXR()
        {
            if (!ownsXR) return;
            XRGeneralSettings.Instance.Manager.StopSubsystems();
            XRGeneralSettings.Instance.Manager.DeinitializeLoader();
            ownsXR = false;
            VrActive = false;
        }

        void OnDestroy() { StopXR(); }

        void OnGUI()
        {
            if (VrActive) return;
            if (titleStyle == null)
            {
                titleStyle = new GUIStyle(GUI.skin.label) { font = font, fontSize = 25, fontStyle = FontStyle.Bold };
                textStyle = new GUIStyle(GUI.skin.label) { font = font, fontSize = 18 };
                smallStyle = new GUIStyle(GUI.skin.label) { font = font, fontSize = 15 };
                titleStyle.normal.textColor = textStyle.normal.textColor = smallStyle.normal.textColor = new Color(.97f, .95f, .88f);
            }
            var scale = Screen.width / 1280f;
            GUI.matrix = Matrix4x4.Scale(new Vector3(scale, scale, 1));
            float height = Screen.height / scale;
            GUI.color = new Color(.055f, .12f, .16f, .92f);
            GUI.DrawTexture(new Rect(24, 22, 520, 115), Texture2D.whiteTexture);
            GUI.color = Color.white;
            GUI.Label(new Rect(42, 32, 500, 35), "神奈川沖浪裏 — M0 静止船", titleStyle);
            GUI.Label(new Rect(42, 73, 500, 28), Paused ? "視点を停止中 / Spaceで再開" : Status, textStyle);
            GUI.Label(new Rect(42, 105, 500, 25), "新規の検証用モデル・平面 / 波と操船は未実装", smallStyle);
            GUI.color = new Color(.055f, .12f, .16f, .92f);
            GUI.DrawTexture(new Rect(24, height - 68, 1232, 44), Texture2D.whiteTexture);
            GUI.color = Color.white;
            GUI.Label(new Rect(42, height - 60, 1210, 30), recordingCamera
                ? "記録用自動カメラ / " + recordingLabel + " / HMD映像・性能測定ではありません"
                : "右ドラッグ・矢印：見回す     R：座席に戻る     Space：停止・再開     Esc：停止     Q：終了", textStyle);
        }
    }
}
