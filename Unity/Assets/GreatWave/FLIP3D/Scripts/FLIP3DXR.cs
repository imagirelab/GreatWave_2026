// FLIP3D：VR の座席（XR の原点）と、座席 → 原画の視点への見える動き（2026-10-17、Claude。新しいファイル。ほかのファイルは変えていない）。
//
// 何をするか：
//   - VR は起動の引数 -vr（--vr・-f3dvr も同じ）か xrStart = Always の時だけ始める（XR General Settings の m_InitManagerOnStart: 0 のまま。DS50・RT48 と同じ形）。
//     始まらなければ PC の画面で続ける。PC の画面でも同じ道でカメラを置く（FLIP3DPlayer.PlaceCamera と同じ式＋下の 2 つ）。
//   - XR の原点 = 「座席」の Transform（FLIP3D_Seat）。カメラはその孫（座席 → 向き直し → カメラ）。カメラの局所の位置・向きは HMD の頭そのもの。
//     座席の位置は FLIP3DPlayer と同じ式：座席 = manifest の座席（seat_x, 静かな水面 + seat_eye_m, seat_z）+ 上下 heave。
//     heave は FLIP の面の記録の上の水面の高さ hf を、船の足跡（x ±4 m・横 ±1.5 m）で平均した値（f3d_export.py・f3d50_export.py が manifest に 24 個/s で書く）。
//     ここでは FLIP3DPlayer.HeaveAt で読むだけで、水の面は変えない。
//   - 視点の動き：重み b（0 座席・1 原画の視点）で、位置は座席と原画の視点を結ぶ直線、VR の向きは水平の向き（yaw）だけを回す（上下の傾きは頭に任せ、地平線を傾けない）。
//     b は FLIP3DExperience（体験の時計）が決める。体験がなければ FLIP3DPlayer.CameraBlend（プレイヤー自身の予定）。白い画面・黒い画面で隠さない。
//   - 動きの間だけ、目の周りを暗くする輪（真ん中はいつも見える）。速さ（m/s）と回りの速さ（°/s）で強さを決める。heave の上下では暗くしない。
//   - 向き直し（C キー・ゲームパッドの Create・コントローラーのボタンを 1.5 s 押す）：今の頭の向きを座席の前に、頭の位置を座席の目の位置に合わせる。
//     VR が始まって頭が追えたら 1 回自動で行う。SteamVR 側で向き直した時（trackingOriginUpdated）ももう一度行う。
//   - 目の前の絵に字を出さない（FLIP3DPlayer の画面の字を VR では消す。この Script も字を描かない）。
//
// PC の画面との違い（正直に書く）：
//   - 繰り返しの継ぎ目で heave が跳ぶ（DA3r_k5_r24 で −0.087 m、DM1A_k4_r8 で −0.399 m【測定：manifest の heave_seam_jump_m】）。
//     heaveSeamAbsorb = true なら、繰り返しの再生で位相が周期の終わりから初めへ戻ったフレームだけ、そのフレームの heave の差をカメラの高さに足して
//     heaveSeamTau（0.5 s）で消す。水の面は変えない。カメラの高さだけ、継ぎ目の後 約 1 s の間、記録の heave からずれる（最大で跳びの大きさ）。
//     速さでは判定しない：DM1A の heave は前の面が座席を通る所で 7.3 m/s（続けて再生の DM1A は 9.1 m/s）まで速く変わる【計算：manifest の heave の 1/24 s の差】。
//     これは記録どおりの上下なので消さない（酔いが強ければ heaveScale・H キー）。DA3 は最大 2.2 m/s。
//   - 原画の視点の画角：PC は縦 38°（printFovV）、HMD は HMD の画角（PS VR2 は約 110°）で変えられない。原画の視点の位置は同じなので、見える範囲は広い。
//   - FLIP50 の頂は DA3 より x が小さい（約 266〜272 m）。crestAlign = true なら、原画の視点と座席の見る点を x 方向に
//     manifest の print_crest_x − crestRefX（278.5 m = clip_DA3r_k5_r24 の print_crest_x【測定】）だけずらす（f3d50_export.py の unity_notes_ja の直し）。
//     DA3r のクリップではずれは 0。
//
// コンパイルの守り：XR の部品（UnityEngine.XR の InputDevices・XRDisplaySubsystem・XRInputSubsystem、組み込みの XR module）は
//   ENABLE_VR の時だけ（GW_FLIP3D_NO_XR を Scripting Define Symbols に足すと全部外れる）。
//   XR Management（パッケージ com.unity.xr.management）は型を直に書かず、名前で探して呼ぶ（Reflection）。パッケージを外してもコンパイルは通り、-vr は PC で続ける。
//   XRSettings・XRDevice（VR module。XR Management が連れてくる）は使わない。
//   Input System（FLIP3DPlayer がもう使っている）は ENABLE_INPUT_SYSTEM の時だけ。
//
// 引数：-vr / --vr / -f3dvr  VR を始める。 -f3dheave <倍>（既定 1。酔いが強い時の運営の切替。物理の値ではなくなる）
//       -f3dnovignette  -f3dvignette <0〜1>  -f3dnocrestalign  -f3dcrestref <x>  -f3dvrnear <m>  -f3dnoshaderswap  -f3dnoseamabsorb
// キー（運営の PC のキーボード）：C 向き直し、V 周りを暗くする輪の入り切り、H heave 1 ⇔ 0.5。
#if ENABLE_VR && !GW_FLIP3D_NO_XR
#define F3D_XR
#endif
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using UnityEngine;
#if F3D_XR
using UnityEngine.XR;
#endif
#if !F3D_XR
#pragma warning disable 0169, 0414, 0649   // XR を外してコンパイルした時だけ使われない欄がある
#endif

namespace GreatWave.FLIP3D
{
    [DefaultExecutionOrder(100)]
    public class FLIP3DXR : MonoBehaviour
    {
        public enum XrStart { Never, OnFlag, Always }

        [Header("つなぐ物（空なら同じ GameObject・場面から探す）")]
        public FLIP3DPlayer player;
        public FLIP3DExperience experience;
        [Tooltip("HMD・PC の画面に描くカメラ。空なら player.cam か Camera.main")]
        public Camera cam;

        [Header("VR を始める")]
        public XrStart xrStart = XrStart.OnFlag;
        public float xrWaitSeconds = 5f;
        [Tooltip("頭が追えたら 1 回自動で向き直す")]
        public bool recenterWhenTracked = true;
        [Tooltip("VR の時のカメラの近い面（m）。0 以下なら変えない")]
        public float vrNearClip = 0.05f;
        [Tooltip("VR の時、水と海の材質を両眼を 1 回で描ける shader（Resources/GreatWaveFLIP3D/FLIP3DWaterXR）の写しに入れ替える")]
        public bool swapStereoShaders = true;

        [Header("座席（XR の原点）と原画の視点")]
        [Tooltip("原画の視点と座席の見る点を x 方向に manifest の print_crest_x − crestRefX だけずらす")]
        public bool crestAlign = true;
        public float crestRefX = 278.5f;
        [Tooltip("座席の上下（heave）の倍。1 = 記録どおり")]
        public float heaveScale = 1f;
        [Tooltip("繰り返しの継ぎ目（位相が初めへ戻ったフレーム）の heave の跳びだけをカメラの高さで消す")]
        public bool heaveSeamAbsorb = true;
        public float heaveSeamTau = 0.5f;

        [Header("周りを暗くする輪（VR の動きの間だけ）")]
        public bool vignette = true;
        public bool vignetteOnDesktop;
        [Range(0f, 1f)] public float vignetteMax = 0.7f;
        public float vigLinStart = 0.5f, vigLinFull = 4f;        // m/s【選び】
        public float vigAngStart = 3f, vigAngFull = 15f;         // °/s【選び】
        public float vigAttack = 0.15f, vigRelease = 0.5f;       // s
        public float vigOpenDeg = 70f, vigClosedDeg = 28f, vigFeatherDeg = 12f;   // 見える円の半分の角（0 → 1）【選び】
        public float vigDistance = 1f;                           // 輪を置く距離（m）

        // ---------------------------------------------------------------- 状態（読むだけ）
        public bool XrRequested { get; private set; }
        public bool XrBusy { get; private set; }
        public bool XrActive { get; private set; }
        public string XrLoaderName { get; private set; } = "";
        public float XrWaitedSeconds { get; private set; }
        public string Status { get; private set; } = "desktop";
        public bool HeadTracked { get; private set; }
        public int Recenters { get; private set; }
        public int SeamAbsorbs { get; private set; }
        public float VignetteAmount { get; private set; }
        public float HeaveRaw { get; private set; }
        public float HeaveShown { get; private set; }
        public float CrestShiftX { get; private set; }
        public float ViewBlend { get; private set; }
        public float RigYawDeg { get; private set; }
        public float MoveSpeed { get; private set; }
        public float TurnSpeed { get; private set; }
        public Transform Seat => seat;
        public Transform RecenterNode => recenter;
        public bool Ready => !XrBusy;
        [NonSerialized] public float Fade;     // 0〜1 の黒い幕。始め直し（FLIP3DExperience.Restart）だけが使う。視点の動きには使わない

        Transform seat, recenter;
        Camera proxy;
        bool built, ownsXR, needRecenter, stereoSwapped, hasPrevHeave, hasPrevMotion;
        int validHeadFrames;
        float prevHeaveRaw, heaveOffset, prevYaw, holdRecenterS;
        double prevPhase;
        Vector3 prevNoHeave;
        readonly Dictionary<Material, Material> stereoMats = new Dictionary<Material, Material>();

        public static bool VrArgGiven() => FLIP3DPlayer.HasArg("-vr") || FLIP3DPlayer.HasArg("--vr") || FLIP3DPlayer.HasArg("-f3dvr");
        static float ArgF(string name, float def)
        {
            var s = FLIP3DPlayer.Arg(name, "");
            return s.Length > 0 && float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : def;
        }

        // ---------------------------------------------------------------- 始まり
        void Awake()
        {
            if (!Application.isPlaying) return;
            if (player == null) player = GetComponent<FLIP3DPlayer>();
            if (player == null) player = FindAnyObjectByType<FLIP3DPlayer>();
            if (experience == null) experience = GetComponent<FLIP3DExperience>();
            if (experience == null) experience = FindAnyObjectByType<FLIP3DExperience>();
            if (cam == null && player != null) cam = player.cam;
            if (cam == null) cam = Camera.main;
            ApplyArgs();
            BuildRig();
        }

        public void ApplyArgs()
        {
            heaveScale = ArgF("-f3dheave", heaveScale);
            if (FLIP3DPlayer.HasArg("-f3dnovignette")) vignette = false;
            vignetteMax = Mathf.Clamp01(ArgF("-f3dvignette", vignetteMax));
            if (FLIP3DPlayer.HasArg("-f3dnocrestalign")) crestAlign = false;
            crestRefX = ArgF("-f3dcrestref", crestRefX);
            vrNearClip = ArgF("-f3dvrnear", vrNearClip);
            if (FLIP3DPlayer.HasArg("-f3dnoshaderswap")) swapStereoShaders = false;
            if (FLIP3DPlayer.HasArg("-f3dnoseamabsorb")) heaveSeamAbsorb = false;
        }

        void BuildRig()
        {
            if (cam == null) { Status = "no camera"; Debug.LogError("F3DXR カメラがない（player.cam・Camera.main とも空）"); return; }
            seat = new GameObject("FLIP3D_Seat (XR origin)").transform;
            recenter = new GameObject("FLIP3D_Recenter").transform;
            recenter.SetParent(seat, false);
            var ct = cam.transform;
            seat.SetPositionAndRotation(ct.position, Quaternion.Euler(0f, ct.eulerAngles.y, 0f));
            ct.SetParent(recenter, false);
            ct.localPosition = Vector3.zero;
            ct.localRotation = Quaternion.identity;
            // プレイヤーは自分の PlaceCamera で cam を動かすので、描かないカメラ（代わり）を渡す。本物のカメラはこの Script だけが置く
            proxy = new GameObject("FLIP3D_PlayerCameraProxy").AddComponent<Camera>();
            proxy.enabled = false;
            proxy.fieldOfView = cam.fieldOfView;
            if (player != null) player.cam = proxy;
            BuildVignette();
            built = true;
        }

        void Start()
        {
            if (!Application.isPlaying) return;
            XrRequested = xrStart == XrStart.Always || (xrStart == XrStart.OnFlag && VrArgGiven());
            if (XrRequested && built) StartCoroutine(InitXR());
            else Status = built ? "desktop" : Status;
        }

        void OnEnable() { Application.onBeforeRender += OnBeforeRender; }
        void OnDisable() { Application.onBeforeRender -= OnBeforeRender; }

        void OnDestroy()
        {
            StopXR();
            foreach (var m in stereoMats.Values) if (m != null) Destroy(m);
            stereoMats.Clear();
            if (vigMesh != null) Destroy(vigMesh);
            if (vigMat != null) Destroy(vigMat);
        }

        // ---------------------------------------------------------------- VR を始める・止める
        IEnumerator InitXR()
        {
            XrBusy = true;
            Status = "starting";
            yield return null;
            float t0 = Time.realtimeSinceStartup;
#if F3D_XR
            if (DisplayRunning())
            {
                XrActive = true;                                  // ほかの物が始めていた（止めるのもその物に任せる）
                XrLoaderName = "(already running)";
            }
            else
            {
                object mgr = null;
                try { mgr = XrManagement.Manager(); } catch (Exception e) { Debug.LogException(e); }
                if (mgr == null) Status = XrManagement.Installed ? "XR General Settings がない" : "XR Management が入っていない";
                else
                {
                    bool already = false;
                    try { already = XrManagement.IsInitialized(mgr); } catch (Exception e) { Debug.LogException(e); }
                    if (!already)
                    {
                        IEnumerator it = null;
                        try { it = XrManagement.InitializeLoader(mgr); } catch (Exception e) { Debug.LogException(e); }
                        // 読み手の初期化は数フレームに分かれる。中で例外が出ても止まらないよう、1 歩ずつ進める
                        while (it != null)
                        {
                            bool more = false; object cur = null;
                            try { more = it.MoveNext(); if (more) cur = it.Current; }
                            catch (Exception e) { Debug.LogException(e); more = false; }
                            if (!more) break;
                            yield return cur;
                        }
                    }
                    UnityEngine.Object loader = null;
                    try { loader = XrManagement.ActiveLoader(mgr); } catch (Exception e) { Debug.LogException(e); }
                    if (loader != null)
                    {
                        if (!already)
                        {
                            try { XrManagement.StartSubsystems(mgr); ownsXR = true; }
                            catch (Exception e) { Debug.LogException(e); }
                        }
                        XrLoaderName = loader.name;
                        // 表示の部品が動き出すまで数フレームかかる（RT48 の Mock Runtime の記録）。最大 xrWaitSeconds 待つ
                        float tw = Time.realtimeSinceStartup;
                        while (true)
                        {
                            XrActive = DisplayRunning();
                            if (XrActive || Time.realtimeSinceStartup - tw > xrWaitSeconds) break;
                            yield return null;
                        }
                        if (!XrActive) { Status = "HMD の表示が始まらない"; StopXR(); }
                    }
                    else Status = "読み手が始まらない（HMD・OpenXR の実行環境がない）";
                }
            }
            if (XrActive) OnXrStarted();
#else
            Status = "XR を外してコンパイルした（ENABLE_VR なし、または GW_FLIP3D_NO_XR）";
#endif
            XrWaitedSeconds = Time.realtimeSinceStartup - t0;
            XrBusy = false;
            Debug.Log(string.Format(CultureInfo.InvariantCulture, "F3DXR_START requested=True active={0} loader={1} waited_s={2:F2} status={3}",
                XrActive, XrLoaderName, XrWaitedSeconds, XrActive ? "vr" : Status + "（PC の画面で続ける）"));
        }

#if F3D_XR
        readonly List<XRInputSubsystem> originSubs = new List<XRInputSubsystem>();

        void OnXrStarted()
        {
            Status = "vr";
            cam.stereoTargetEye = StereoTargetEyeMask.Both;
            if (vrNearClip > 0f) cam.nearClipPlane = Mathf.Min(cam.nearClipPlane, vrNearClip);
            var inputs = new List<XRInputSubsystem>();
            SubsystemManager.GetSubsystems(inputs);
            foreach (var s in inputs)
            {
                bool ok = s.TrySetTrackingOriginMode(TrackingOriginModeFlags.Device);   // 座った体験：頭の位置を原点からの差で読む
                s.trackingOriginUpdated -= OnOriginUpdated;
                s.trackingOriginUpdated += OnOriginUpdated;
                originSubs.Add(s);
                Debug.Log("F3DXR_ORIGIN device_mode=" + ok + " now=" + s.GetTrackingOriginMode());
            }
            if (player != null) player.showLabel = false;          // 目の前の絵に字を出さない
            needRecenter = recenterWhenTracked;
            validHeadFrames = 0;
        }

        void OnOriginUpdated(XRInputSubsystem s) { needRecenter = true; validHeadFrames = 0; }

        static readonly List<XRDisplaySubsystem> displays = new List<XRDisplaySubsystem>();
        static bool DisplayRunning()
        {
            displays.Clear();
            SubsystemManager.GetSubsystems(displays);
            foreach (var d in displays) if (d.running) return true;
            return false;
        }
#endif

        void StopXR()
        {
#if F3D_XR
            foreach (var s in originSubs) if (s != null) s.trackingOriginUpdated -= OnOriginUpdated;
            originSubs.Clear();
            if (ownsXR)
            {
                try
                {
                    var mgr = XrManagement.Manager();
                    if (mgr != null) { XrManagement.StopSubsystems(mgr); XrManagement.DeinitializeLoader(mgr); }
                }
                catch (Exception e) { Debug.LogException(e); }
            }
#endif
            ownsXR = false;
            XrActive = false;
        }

        // ---------------------------------------------------------------- 毎フレーム
        void LateUpdate()
        {
            if (!built || player == null || !player.Initialized || cam == null) return;
            double step = experience != null && experience.Driving ? experience.StepSeconds : 0.0;
            float dt = step > 0 ? (float)step : Mathf.Max(1e-4f, Time.unscaledDeltaTime);
            if (proxy != null && player.cam != proxy) player.cam = proxy;
            if (XrActive && swapStereoShaders && !stereoSwapped) SwapStereoShaders();
            HandleInput(dt);

            var mf = player.Manifest;
            CrestShiftX = crestAlign && mf.print_crest_x != 0f ? mf.print_crest_x - crestRefX : 0f;
            var shift = new Vector3(CrestShiftX, 0f, 0f);
            float b = Mathf.Clamp01(experience != null && experience.Driving ? experience.ViewBlend : player.CameraBlend);
            ViewBlend = b;

            HeaveRaw = player.HeaveAt(player.LoopPhase);
            HeaveShown = AbsorbHeave(HeaveRaw, player.LoopPhase, dt);
            Vector3 seatBase = player.SeatBase;
            Vector3 seatEye = seatBase + Vector3.up * (heaveScale * HeaveShown);
            Vector3 printEye = player.printPos + shift;
            Vector3 seatDir = player.seatLookAt + shift - seatBase;
            Vector3 printDir = player.printLookAt - player.printPos;
            Vector3 pos = Vector3.Lerp(seatEye, printEye, b);
            float yaw = Mathf.LerpAngle(Yaw(seatDir), Yaw(printDir), b);
            RigYawDeg = yaw;

            if (XrActive)
            {
                // VR：座席は水平の向きだけ回す。上下・傾きは頭（HMD）に任せる
                seat.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
                ApplyHeadPose();
                if (needRecenter) TryAutoRecenter();
            }
            else
            {
                // PC の画面：FLIP3DPlayer.PlaceCamera と同じ（向きは球面の補間、画角は線形）
                seat.SetPositionAndRotation(pos, Quaternion.Slerp(LookRot(seatDir), LookRot(printDir), b));
                recenter.localPosition = Vector3.zero; recenter.localRotation = Quaternion.identity;
                cam.transform.localPosition = Vector3.zero; cam.transform.localRotation = Quaternion.identity;
                cam.fieldOfView = Mathf.Lerp(player.seatFovV, player.printFovV, b);
            }
            UpdateVignette(Vector3.Lerp(seatBase, printEye, b), yaw, dt);
        }

        void OnBeforeRender() => ApplyHeadPose();

        static float Yaw(Vector3 d) => Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg;
        static Quaternion LookRot(Vector3 d) => d.sqrMagnitude < 1e-8f ? Quaternion.identity : Quaternion.LookRotation(d, Vector3.up);

        // 繰り返しの継ぎ目の heave の跳びだけをカメラの高さで消す（水の面は変えない）。継ぎ目 = 繰り返しの再生で位相が半周期より大きく戻ったフレーム
        float AbsorbHeave(float raw, double phase, float dt)
        {
            if (!heaveSeamAbsorb) { heaveOffset = 0f; hasPrevHeave = false; return raw; }
            if (hasPrevHeave)
            {
                bool seam = player.playback == FLIP3DPlayer.Playback.Loop && phase < prevPhase - 0.5 * player.LoopSeconds;
                if (seam) { heaveOffset -= raw - prevHeaveRaw; SeamAbsorbs++; }
                heaveOffset *= Mathf.Exp(-dt / Mathf.Max(1e-3f, heaveSeamTau));
            }
            prevHeaveRaw = raw; prevPhase = phase; hasPrevHeave = true;
            return raw + heaveOffset;
        }

        // 始め直しの後など、続かない所で呼ぶ（跳びとみなさない・暗がりを付けない）
        public void ResetMotion()
        {
            hasPrevHeave = false; heaveOffset = 0f;
            hasPrevMotion = false; VignetteAmount = 0f;
        }

        // ---------------------------------------------------------------- 頭・向き直し
        void ApplyHeadPose()
        {
#if F3D_XR
            if (!XrActive || cam == null) return;
            if (TryHead(out var p, out var q, out bool tracked))
            {
                cam.transform.localPosition = p;
                cam.transform.localRotation = q;
                HeadTracked = tracked;
            }
#endif
        }

        void TryAutoRecenter()
        {
#if F3D_XR
            if (TryHead(out _, out _, out bool tracked) && tracked) validHeadFrames++; else validHeadFrames = 0;
            if (validHeadFrames >= 10) Recenter();                 // 追えてから 10 フレーム待つ（始めの不安定な値を避ける）【選び】
#endif
        }

        // 今の頭の向き（水平）を座席の前に、今の頭の位置を座席の目の位置（XR の原点）に合わせる
        public bool Recenter()
        {
#if F3D_XR
            if (!XrActive || recenter == null) return false;
            if (!TryHead(out var p, out var q, out _)) { needRecenter = true; return false; }
            Vector3 f = q * Vector3.forward; f.y = 0f;
            float headYaw = f.sqrMagnitude > 1e-6f ? Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg : 0f;
            var r = Quaternion.Euler(0f, -headYaw, 0f);
            recenter.localRotation = r;
            recenter.localPosition = -(r * p);
            needRecenter = false;
            validHeadFrames = 0;
            Recenters++;
            Debug.Log(string.Format(CultureInfo.InvariantCulture, "F3DXR_RECENTER n={0} head_yaw={1:F1} head_pos=({2:F3},{3:F3},{4:F3})", Recenters, headYaw, p.x, p.y, p.z));
            return true;
#else
            return false;
#endif
        }

#if F3D_XR
        InputDevice hmd;
        readonly List<InputDevice> devs = new List<InputDevice>();
        readonly List<InputDevice> ctrls = new List<InputDevice>();
        float ctrlRefreshS;

        bool TryHead(out Vector3 p, out Quaternion q, out bool tracked)
        {
            p = Vector3.zero; q = Quaternion.identity; tracked = false;
            if (!hmd.isValid)
            {
                devs.Clear();
                InputDevices.GetDevicesWithCharacteristics(InputDeviceCharacteristics.HeadMounted, devs);
                if (devs.Count == 0) return false;
                hmd = devs[0];
            }
            if (!hmd.TryGetFeatureValue(UnityEngine.XR.CommonUsages.centerEyeRotation, out q) &&
                !hmd.TryGetFeatureValue(UnityEngine.XR.CommonUsages.deviceRotation, out q)) return false;
            if (q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w < 1e-6f) { q = Quaternion.identity; return false; }
            q = Quaternion.Normalize(q);
            if (!hmd.TryGetFeatureValue(UnityEngine.XR.CommonUsages.centerEyePosition, out p) &&
                !hmd.TryGetFeatureValue(UnityEngine.XR.CommonUsages.devicePosition, out p)) p = Vector3.zero;
            if (!hmd.TryGetFeatureValue(UnityEngine.XR.CommonUsages.isTracked, out tracked)) tracked = true;
            return true;
        }

        // コントローラーのボタン（menu・primary・secondary のどれか）を 1.5 s 押し続けたら向き直す。
        // OpenXR の設定で手の操作の profile が 1 つも入っていない今は、コントローラーは見えない（キーボードの C は使える）
        bool ControllerHeld()
        {
            ctrlRefreshS -= Time.unscaledDeltaTime;
            if (ctrlRefreshS <= 0f)
            {
                ctrlRefreshS = 1f;
                ctrls.Clear();
                InputDevices.GetDevicesWithCharacteristics(InputDeviceCharacteristics.Controller, ctrls);
            }
            foreach (var c in ctrls)
            {
                if (!c.isValid) continue;
                if (c.TryGetFeatureValue(UnityEngine.XR.CommonUsages.menuButton, out bool m) && m) return true;
                if (c.TryGetFeatureValue(UnityEngine.XR.CommonUsages.primaryButton, out bool a) && a) return true;
                if (c.TryGetFeatureValue(UnityEngine.XR.CommonUsages.secondaryButton, out bool s) && s) return true;
            }
            return false;
        }
#endif

        void HandleInput(float dt)
        {
#if ENABLE_INPUT_SYSTEM
            var kb = UnityEngine.InputSystem.Keyboard.current;
            if (kb != null)
            {
                if (kb.cKey.wasPressedThisFrame) Recenter();
                if (kb.vKey.wasPressedThisFrame) { vignette = !vignette; Debug.Log("F3DXR_VIGNETTE " + vignette); }
                if (kb.hKey.wasPressedThisFrame) { heaveScale = heaveScale > 0.75f ? 0.5f : 1f; Debug.Log("F3DXR_HEAVE_SCALE " + heaveScale.ToString(CultureInfo.InvariantCulture)); }
            }
            var gp = UnityEngine.InputSystem.Gamepad.current;
            if (gp != null && gp.selectButton.wasPressedThisFrame) Recenter();
#endif
#if F3D_XR
            if (XrActive)
            {
                if (ControllerHeld())
                {
                    float before = holdRecenterS;
                    holdRecenterS += dt;
                    if (before < 1.5f && holdRecenterS >= 1.5f) Recenter();
                }
                else holdRecenterS = 0f;
            }
#endif
        }

        // ---------------------------------------------------------------- 両眼を 1 回で描く shader への入れ替え（VR の時だけ）
        void SwapStereoShaders()
        {
            stereoSwapped = true;                                   // 1 回だけ試す
            var sh = Resources.Load<Shader>("GreatWaveFLIP3D/FLIP3DWaterXR");
            if (sh == null || !sh.isSupported) { Debug.LogWarning("F3DXR_STEREO_SHADER FLIP3DWaterXR が読めない・使えない。水が片眼だけになるおそれ（OpenXR を Multi-pass にすれば直る）"); return; }
            int n = 0;
            foreach (var r in player.GetComponentsInChildren<MeshRenderer>(true))
            {
                var m = r.sharedMaterial;
                if (m == null || m.shader == null || m.shader.name != "GreatWave/FLIP3D/Water") continue;
                if (!stereoMats.TryGetValue(m, out var x))
                {
                    x = new Material(sh) { name = m.name + " (XR)" };
                    x.CopyPropertiesFromMaterial(m);
                    x.renderQueue = m.renderQueue;
                    stereoMats[m] = x;
                }
                r.sharedMaterial = x;
                n++;
            }
            Debug.Log("F3DXR_STEREO_SHADER renderers=" + n + " materials=" + stereoMats.Count);
        }

        // ---------------------------------------------------------------- 周りを暗くする輪
        const int VigSeg = 48;
        Mesh vigMesh; Material vigMat; MeshRenderer vigRenderer;
        Vector3[] vigV; Color32[] vigC;
        float vigLastIn = -1f, vigLastFade = -1f, vigLastD = -1f, vigLastEdge = -1f;

        void BuildVignette()
        {
            var sh = Resources.Load<Shader>("GreatWaveFLIP3D/FLIP3DVignetteXR");
            if (sh == null || !sh.isSupported) sh = Shader.Find("Sprites/Default");
            if (sh == null) { Debug.LogWarning("F3DXR_VIGNETTE shader がない（輪は出さない）"); return; }
            vigMat = new Material(sh) { name = "FLIP3D_Vignette", renderQueue = 4100 };
            var go = new GameObject("FLIP3D_Vignette");
            go.transform.SetParent(cam.transform, false);
            vigMesh = new Mesh { name = "FLIP3D_Vignette" };
            vigMesh.MarkDynamic();
            vigV = new Vector3[1 + 3 * VigSeg];
            vigC = new Color32[vigV.Length];
            var tri = new int[15 * VigSeg];
            int q = 0;
            for (int i = 0; i < VigSeg; i++)
            {
                int a0 = 1 + i, a1 = 1 + (i + 1) % VigSeg, b0 = a0 + VigSeg, b1 = a1 + VigSeg, c0 = b0 + VigSeg, c1 = b1 + VigSeg;
                tri[q++] = 0; tri[q++] = a0; tri[q++] = a1;                                   // 真ん中（幕の時だけ色が付く）
                tri[q++] = a0; tri[q++] = b0; tri[q++] = b1; tri[q++] = a0; tri[q++] = b1; tri[q++] = a1;   // 見える円の縁のぼかし
                tri[q++] = b0; tri[q++] = c0; tri[q++] = c1; tri[q++] = b0; tri[q++] = c1; tri[q++] = b1;   // 外側（暗い）
            }
            SetVignetteGeometry(vigOpenDeg, 0f, 0f, Mathf.Max(vigDistance, cam.nearClipPlane * 2f));
            vigMesh.vertices = vigV;
            vigMesh.colors32 = vigC;
            vigMesh.triangles = tri;
            vigMesh.RecalculateBounds();
            go.AddComponent<MeshFilter>().sharedMesh = vigMesh;
            vigRenderer = go.AddComponent<MeshRenderer>();
            vigRenderer.sharedMaterial = vigMat;
            vigRenderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            vigRenderer.receiveShadows = false;
            vigRenderer.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off;
            vigRenderer.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
            vigRenderer.enabled = false;
        }

        void SetVignetteGeometry(float inDeg, float edgeAlpha, float fade, float d)
        {
            float midDeg = Mathf.Min(inDeg + vigFeatherDeg, 88f), outDeg = 88.5f;
            float r0 = d * Mathf.Tan(Mathf.Min(inDeg, 87.9f) * Mathf.Deg2Rad), r1 = d * Mathf.Tan(midDeg * Mathf.Deg2Rad), r2 = d * Mathf.Tan(outDeg * Mathf.Deg2Rad);
            byte aIn = (byte)Mathf.RoundToInt(255f * Mathf.Clamp01(fade));
            byte aEdge = (byte)Mathf.RoundToInt(255f * Mathf.Clamp01(Mathf.Max(fade, edgeAlpha)));
            vigV[0] = new Vector3(0f, 0f, d); vigC[0] = new Color32(0, 0, 0, aIn);
            for (int i = 0; i < VigSeg; i++)
            {
                float a = 2f * Mathf.PI * i / VigSeg, cx = Mathf.Cos(a), cy = Mathf.Sin(a);
                vigV[1 + i] = new Vector3(cx * r0, cy * r0, d); vigC[1 + i] = new Color32(0, 0, 0, aIn);
                vigV[1 + VigSeg + i] = new Vector3(cx * r1, cy * r1, d); vigC[1 + VigSeg + i] = new Color32(0, 0, 0, aEdge);
                vigV[1 + 2 * VigSeg + i] = new Vector3(cx * r2, cy * r2, d); vigC[1 + 2 * VigSeg + i] = new Color32(0, 0, 0, aEdge);
            }
        }

        static float Ramp(float x, float a, float b) { float u = Mathf.Clamp01((x - a) / Mathf.Max(1e-6f, b - a)); return u * u * (3f - 2f * u); }

        void UpdateVignette(Vector3 noHeave, float yaw, float dt)
        {
            float target = 0f;
            if (hasPrevMotion)
            {
                MoveSpeed = (noHeave - prevNoHeave).magnitude / dt;
                TurnSpeed = Mathf.Abs(Mathf.DeltaAngle(prevYaw, yaw)) / dt;
                if (MoveSpeed < 200f) target = Mathf.Max(Ramp(MoveSpeed, vigLinStart, vigLinFull), Ramp(TurnSpeed, vigAngStart, vigAngFull));   // 200 m/s 以上は始め直しの飛び（暗くしない）
            }
            prevNoHeave = noHeave; prevYaw = yaw; hasPrevMotion = true;
            bool on = vignette && (XrActive || vignetteOnDesktop);
            target = on ? target * vignetteMax : 0f;
            float tau = target > VignetteAmount ? vigAttack : vigRelease;
            VignetteAmount += (target - VignetteAmount) * (1f - Mathf.Exp(-dt / Mathf.Max(1e-3f, tau)));
            if (VignetteAmount < 1e-3f && target == 0f) VignetteAmount = 0f;
            if (vigRenderer == null) return;
            float fade = Mathf.Clamp01(Fade);
            bool show = VignetteAmount > 0.002f || fade > 0.002f;
            vigRenderer.enabled = show;
            if (!show) return;
            float d = Mathf.Max(vigDistance, cam.nearClipPlane * 2f);
            float inDeg = Mathf.Lerp(vigOpenDeg, vigClosedDeg, VignetteAmount);
            float edge = VignetteAmount > 0.002f ? 1f : 0f;
            if (Mathf.Abs(inDeg - vigLastIn) < 0.05f && Mathf.Abs(fade - vigLastFade) < 0.002f && d == vigLastD && edge == vigLastEdge) return;
            vigLastIn = inDeg; vigLastFade = fade; vigLastD = d; vigLastEdge = edge;
            SetVignetteGeometry(inDeg, edge, fade, d);
            vigMesh.vertices = vigV;
            vigMesh.colors32 = vigC;
            vigMesh.RecalculateBounds();
        }

#if F3D_XR
        // XR Management（パッケージ）を型を書かずに呼ぶ。パッケージがなければ Installed = false で、何も呼ばない
        static class XrManagement
        {
            const BindingFlags PS = BindingFlags.Public | BindingFlags.Static, PI = BindingFlags.Public | BindingFlags.Instance;
            static Type settingsType; static bool looked;
            static Type SettingsType
            {
                get
                {
                    if (!looked) { looked = true; settingsType = Type.GetType("UnityEngine.XR.Management.XRGeneralSettings, Unity.XR.Management", false); }
                    return settingsType;
                }
            }
            public static bool Installed => SettingsType != null;
            public static object Manager()
            {
                var t = SettingsType;
                if (t == null) return null;
                var gs = t.GetProperty("Instance", PS)?.GetValue(null, null);
                if (gs == null || (gs is UnityEngine.Object g && g == null)) return null;
                var m = t.GetProperty("Manager", PI)?.GetValue(gs, null);
                if (m == null || (m is UnityEngine.Object mo && mo == null)) return null;
                return m;
            }
            public static bool IsInitialized(object mgr) => Prop(mgr, "isInitializationComplete") is bool b && b;
            public static UnityEngine.Object ActiveLoader(object mgr) { var o = Prop(mgr, "activeLoader") as UnityEngine.Object; return o != null ? o : null; }
            public static IEnumerator InitializeLoader(object mgr) => Call(mgr, "InitializeLoader") as IEnumerator;
            public static void StartSubsystems(object mgr) => Call(mgr, "StartSubsystems");
            public static void StopSubsystems(object mgr) => Call(mgr, "StopSubsystems");
            public static void DeinitializeLoader(object mgr) => Call(mgr, "DeinitializeLoader");
            static object Prop(object o, string n) => o?.GetType().GetProperty(n, PI)?.GetValue(o, null);
            static object Call(object o, string n) => o?.GetType().GetMethod(n, PI, null, Type.EmptyTypes, null)?.Invoke(o, null);
        }
#endif
    }
}
