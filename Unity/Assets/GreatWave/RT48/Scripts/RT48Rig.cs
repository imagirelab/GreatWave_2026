using System.Collections;
using System.Collections.Generic;
using Unity.XR.CoreUtils;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;
using UnityEngine.XR;
using UnityEngine.XR.Management;

namespace GreatWave.RT48
{
    // RT48：VR とデスクトップのカメラ（計画 §3.4・§3.6）。
    //   ・XR は起動時に始めない（XR General Settings の m_InitManagerOnStart: 0）。-rt48xr の時だけ、ここで OpenXR を始める（DS50 と同じ形）。
    //     始まったら TrackedPoseDriver を動かし、デスクトップの向きを止める。始まらなければデスクトップで続ける。
    //   ・XR Origin（Device の原点、座った姿勢）は船の座席の子。目は水線から eyeHeightM（CameraYOffset）。乗客の揺れを弱める設定はしない。
    //   ・C：向きのやり直し（今の頭の向きを船首の向きに合わせ、頭の位置を座席の真上に戻す）。
    public class RT48Rig : MonoBehaviour
    {
        public RT48Playback playback;
        public XROrigin origin;
        public Transform cameraOffset;
        public Camera hmdCamera;
        public TrackedPoseDriver poseDriver;

        public bool XrRequested { get; private set; }
        public bool XrActive { get; private set; }
        public bool XrBusy { get; private set; }
        public string XrStatusJa { get; private set; } = "デスクトップ";
        public string XrLoaderName { get; private set; } = "";
        public float XrWaitedSeconds { get; private set; }
        public float xrWaitSeconds = 5f;
        bool ownsXR;

        void Start()
        {
            if (!Application.isPlaying) return;
            if (poseDriver != null) poseDriver.enabled = false;
            if (cameraOffset != null && playback != null) cameraOffset.localPosition = new Vector3(0f, playback.eyeHeightM, 0f);
            if (origin != null && playback != null) origin.CameraYOffset = playback.eyeHeightM;
            XrRequested = RT48Playback.HasArg("-rt48xr");
            if (XrRequested) StartCoroutine(InitXR());
        }

        IEnumerator InitXR()
        {
            XrBusy = true;
            XrStatusJa = "VR を始めています…";
            yield return null;
            var mgr = XRGeneralSettings.Instance != null ? XRGeneralSettings.Instance.Manager : null;
            if (mgr != null)
            {
                yield return mgr.InitializeLoader();
                if (mgr.activeLoader != null)
                {
                    mgr.StartSubsystems();
                    ownsXR = true;
                    XrLoaderName = mgr.activeLoader.name;
                    // 表示の部品が動き出すまで数フレームかかる（Mock Runtime で、始めた直後は running = false だった。AF32 は 3 s 待つ）。
                    // 最大 xrWaitSeconds 待ち、動き出したら使う。
                    var displays = new List<XRDisplaySubsystem>();
                    float t0 = Time.realtimeSinceStartup;
                    while (true)
                    {
                        SubsystemManager.GetSubsystems(displays);
                        XrActive = displays.Exists(d => d.running) && XRSettings.isDeviceActive;
                        if (XrActive || Time.realtimeSinceStartup - t0 > xrWaitSeconds) break;
                        yield return null;
                    }
                    XrWaitedSeconds = Time.realtimeSinceStartup - t0;
                    if (!XrActive) StopXR();
                }
            }
            if (XrActive)
            {
                if (playback != null) playback.DesktopViewEnabled = false;
                if (hmdCamera != null) { hmdCamera.stereoTargetEye = StereoTargetEyeMask.Both; hmdCamera.transform.localRotation = Quaternion.identity; }
                if (poseDriver != null) poseDriver.enabled = true;
                if (origin != null) origin.transform.localRotation = Quaternion.Euler(0f, playback != null ? playback.ViewYawDeg : -90f, 0f);
                if (playback != null && playback.Source != null && !playback.ManualClock) playback.Restart();   // 始めの 3 s の板を HMD で見せるため、XR が動いてから初めから
            }
            XrStatusJa = XrActive ? "VR（" + XrLoaderName + "）" : "VR を始められませんでした。デスクトップで続けます";
            Debug.Log("RT48_XR requested=True active=" + XrActive + " loader=" + XrLoaderName + " waited=" + XrWaitedSeconds.ToString("F2") +
                      " device=" + XRSettings.loadedDeviceName + " stereo=" + XRSettings.stereoRenderingMode + " eye=" + XRSettings.eyeTextureWidth + "x" + XRSettings.eyeTextureHeight +
                      " camStereo=" + (hmdCamera != null && hmdCamera.stereoEnabled));
            XrBusy = false;
            // -rt48xrshot <png>：XR が動いてから 3 s 後に窓（HMD の写し）を撮る（煙の確かめ用。左右の眼の絵の確かめは手順 5）
            string shot = RT48Playback.Arg("-rt48xrshot", "");
            if (XrActive && !string.IsNullOrEmpty(shot))
            {
                float t1 = Time.realtimeSinceStartup;
                while (Time.realtimeSinceStartup - t1 < 3f) yield return null;
                // -rt48xrshotmode both：左右の眼の絵を並べて撮る（record_ja.md の V8）。既定は今までと同じ
                bool both = RT48Playback.Arg("-rt48xrshotmode", "") == "both";
                if (both) ScreenCapture.CaptureScreenshot(shot, ScreenCapture.StereoScreenCaptureMode.BothEyes);
                else ScreenCapture.CaptureScreenshot(shot);
                Debug.Log("RT48_XRSHOT " + shot + " mode=" + (both ? "both" : "default") + " t=" + (playback != null ? playback.SimTime.ToString("F3") : "") +
                          " stereo=" + XRSettings.stereoRenderingMode + " eye=" + XRSettings.eyeTextureWidth + "x" + XRSettings.eyeTextureHeight);
            }
        }

        void Update()
        {
            if (!XrActive) return;
            var kb = Keyboard.current;
            if (kb != null && kb.cKey.wasPressedThisFrame) Recenter();
        }

        public void Recenter()
        {
            if (origin == null || hmdCamera == null) return;
            var camLocal = hmdCamera.transform.localRotation;
            float headYaw = camLocal.eulerAngles.y;
            const float target = -90f;   // 船首の向き（−X）
            origin.transform.localRotation = Quaternion.Euler(0f, target - headYaw, 0f);
            var p = hmdCamera.transform.localPosition;
            var flat = origin.transform.localRotation * new Vector3(p.x, 0f, p.z);
            origin.transform.localPosition = -flat;
            Debug.Log("RT48_RECENTER headYaw=" + headYaw.ToString("F1"));
        }

        void OnDestroy() => StopXR();

        void StopXR()
        {
            if (!ownsXR) return;
            var mgr = XRGeneralSettings.Instance != null ? XRGeneralSettings.Instance.Manager : null;
            if (mgr != null) { mgr.StopSubsystems(); mgr.DeinitializeLoader(); }
            ownsXR = false;
            XrActive = false;
        }
    }
}
