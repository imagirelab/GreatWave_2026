using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using GreatWave.ArtFirst;
using GreatWave.Design45;
using GreatWave.Design46;
using GreatWave.Design47;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.XR;
using UnityEngine.XR.Management;

namespace GreatWave.Design50
{
    // 設計50：Release のビルドの体験の枠（入口 → 体験 → 終わり → 出口）。設計47〜49 の体験の場面（DS49_Sound.unity の写し）に載せる。
    //   ・入口：日本語の操作説明の画面。Enter ／ ×（ゲームパッドの South）／ Options で始める。始めるまで体験の時計は 0 で止めておく（DS47Flow.Pause("entry")）。
    //   ・停止の切替：P ／ Esc ／ Options。押したそのフレームで DS47Flow.Pause("user")（時計・座席の船の物理・音が止まる）。もう一度押すと再開。
    //   ・揺れ軽減の切替：C ／ △（North）。オン = L0（水平維持）、オフ = L3（傾斜まで）。1〜4 の直接の選択（設計45）もそのまま使える。
    //   ・終わり：体験の時計が終わり（DS47 の end）に着いたら終わりの画面。Q ／ Esc ／ Enter ／ × で出口（Application.Quit）。60 s で自動で終える。
    //   ・一時停止中は Q で体験を終える。
    //   ・--vr：同じ exe で OpenXR を手で起こす（美術優先の M0 と同じ形。XR General Settings の自動の初期化は切ってある）。起きなければ PC の画面で続ける。
    //   ・データ：Release では、場面の相対のパス（Build/Design/...・Assets/GreatWave/...）を StreamingAssets/gwdata の下で読むよう、
    //     場面を読む前に作業ディレクトリをそこへ移す（Editor では何もしない）。
    // 画面は HMD Camera の子の世界の板（DS50 Overlay の shader、深さを見ずに最後に描く）。PC と VR で同じ物を使う。
    [DefaultExecutionOrder(100)]
    public class DS50Shell : MonoBehaviour
    {
        public enum ShellState { Entry, Running, Stopped, End, Quitting }

        public DS47Flow flow;
        public GWClock clock;
        public DS45RiderComfort rider;
        public DS46EventTrack events;
        public Camera hmdCamera;
        [Tooltip("板の材質（DS50 Overlay、_UseAlphaTex 0）")] public Material panelMat;
        [Tooltip("文字の材質（DS50 Overlay、_UseAlphaTex 1）。_MainTex は実行時にフォントの字の画へ差し替える")] public Material textMat;
        [Tooltip("Shader.Find で探す shader をビルドへ入れるための参照（使わない）")] public Material[] keepMaterials;
        public float endAutoQuitS = 60f;
        public int comfortOnLevel = 0, comfortOffLevel = 3;
        public string[] fontNames = { "Yu Gothic UI", "Yu Gothic", "Meiryo", "MS Gothic" };
        public Color paperColor = new Color(0.93f, 0.89f, 0.80f, 0.97f);
        public Color endPaperColor = new Color(0.93f, 0.89f, 0.80f, 0.86f);
        public Color inkColor = new Color(0.09f, 0.16f, 0.31f, 1f);
        public float vrPanelDistanceM = 1.2f;

        // ---------------------------------------------------------------- データの置き場（Release だけ）
        public static string DataRoot { get; private set; } = "";
        public static bool DataRootUsed { get; private set; }
        public static string StartCwd { get; private set; } = "";

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void SetDataRoot()
        {
            StartCwd = Directory.GetCurrentDirectory();
            if (Application.isEditor) return;
            DataRoot = Path.Combine(Application.streamingAssetsPath, "gwdata");
            if (Directory.Exists(DataRoot)) { Directory.SetCurrentDirectory(DataRoot); DataRootUsed = true; }
            Debug.Log("DS50_DATA_ROOT: " + DataRoot + " used=" + DataRootUsed + " startCwd=" + StartCwd);
        }

        public static bool HasArg(string a) => Array.IndexOf(Environment.GetCommandLineArgs(), a) >= 0;
        public static string Arg(string name, string def)
        {
            var a = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(a, name);
            return i >= 0 && i + 1 < a.Length ? a[i + 1] : def;
        }

        // ---------------------------------------------------------------- 状態
        public ShellState State { get; private set; } = ShellState.Entry;
        public bool VrRequested { get; private set; }
        public bool VrActive { get; private set; }
        public bool VrInitBusy { get; private set; }
        public string VrStatusJa { get; private set; } = "";
        public bool ComfortOn => rider == null || rider.Level == comfortOnLevel;
        public int EndEventFrame { get; private set; } = -1;
        public int EndShownFrame { get; private set; } = -1;
        public string QuitCause { get; private set; } = "";
        public float EndElapsedS { get; private set; }
        public string FontUsed { get; private set; } = "";
        public readonly List<string> Log = new List<string>();

        public struct Change { public int frame; public double real, exp; public string from, to, cause; }
        public readonly List<Change> Changes = new List<Change>();
        public event Action<string> QuitRequested;

        Font font;
        bool ready, ownsXR;
        AudioSource[] audioSources = new AudioSource[0];
        readonly List<AudioSource> shellPaused = new List<AudioSource>();
        public int ShellPausedAudio { get; private set; }
        Panel entry, pause, end, toast;
        float toastLeftS;
        Texture lastFontTex;

        class Panel
        {
            public GameObject root, bg;
            public TextMesh title, body;
            public Vector2 sizeFrac, centerFrac;   // 画面の幅・高さに対する割合と中心（−0.5〜0.5）
            public float titleEm, bodyEm;          // 画面の高さに対する字の大きさ
            public bool center;
        }

        // ---------------------------------------------------------------- 始まり
        void Start()
        {
            if (!Application.isPlaying) return;
            if (flow != null && !flow.Ready) flow.Init();
            font = Font.CreateDynamicFontFromOSFont(fontNames, 64);
            FontUsed = font != null ? string.Join("/", font.fontNames) : "";
            if (font == null) { font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); FontUsed = "LegacyRuntime.ttf"; }
            textMat = new Material(textMat) { name = "DS50 文字（実行時）" };
            Font.textureRebuilt += OnFontTex;
            BuildPanels();
            audioSources = FindObjectsByType<AudioSource>();
            if (events != null) events.Fired += OnEvent;
            flow.Pause("entry");
            SetState(ShellState.Entry, "start");
            ShowOnly(entry);
            ready = true;
            VrRequested = HasArg("--vr");
            if (VrRequested) StartCoroutine(InitXR());
            RefreshEntry();
            Log.Add("start font=" + FontUsed + " dataRoot=" + DataRoot + " used=" + DataRootUsed + " vr=" + VrRequested);
        }

        void OnDestroy()
        {
            Font.textureRebuilt -= OnFontTex;
            if (events != null) events.Fired -= OnEvent;
            StopXR();
        }

        void OnFontTex(Font f)
        {
            if (f == font && textMat != null) { textMat.mainTexture = font.material.mainTexture; lastFontTex = textMat.mainTexture; }
        }

        void OnEvent(DS46EventTrack.Entry e, GWClock.Step st)
        {
            Log.Add("event " + e.id + " frame=" + Time.frameCount + " exp=" + st.experience.ToString("F4"));
            if (e.id == "end" && EndEventFrame < 0) EndEventFrame = Time.frameCount;
        }

        IEnumerator InitXR()
        {
            VrInitBusy = true;
            VrStatusJa = "VR（HMD）を開始しています…";
            RefreshEntry();
            yield return null;
            var mgr = XRGeneralSettings.Instance != null ? XRGeneralSettings.Instance.Manager : null;
            if (mgr != null)
            {
                yield return mgr.InitializeLoader();
                if (mgr.activeLoader != null)
                {
                    mgr.StartSubsystems();
                    ownsXR = true;
                    var displays = new List<XRDisplaySubsystem>();
                    SubsystemManager.GetSubsystems(displays);
                    VrActive = displays.Exists(d => d.running);
                    if (!VrActive) StopXR();
                }
            }
            VrStatusJa = VrActive ? "VR（HMD）で表示しています。" : "VR を開始できませんでした。PC の画面で続けます。";
            Log.Add("xr loader=" + (mgr != null && mgr.activeLoader != null ? mgr.activeLoader.name : "none") + " active=" + VrActive);
            Debug.Log("DS50_VR: requested=True active=" + VrActive + " status=" + VrStatusJa);
            VrInitBusy = false;
            RefreshEntry();
        }

        void StopXR()
        {
            if (!ownsXR) return;
            var mgr = XRGeneralSettings.Instance != null ? XRGeneralSettings.Instance.Manager : null;
            if (mgr != null) { mgr.StopSubsystems(); mgr.DeinitializeLoader(); }
            ownsXR = false;
            VrActive = false;
        }

        // ---------------------------------------------------------------- 入力と状態
        static bool P(UnityEngine.InputSystem.Controls.ButtonControl b) => b != null && b.wasPressedThisFrame;

        void Update()
        {
            if (!ready) return;
            var kb = Keyboard.current; var gp = Gamepad.current;
            bool enter = kb != null && (P(kb.enterKey) || P(kb.numpadEnterKey));
            bool esc = kb != null && P(kb.escapeKey);
            bool pKey = kb != null && P(kb.pKey);
            bool qKey = kb != null && P(kb.qKey);
            bool cKey = kb != null && P(kb.cKey);
            bool gSouth = gp != null && P(gp.buttonSouth);
            bool gStart = gp != null && P(gp.startButton);
            bool gNorth = gp != null && P(gp.buttonNorth);

            switch (State)
            {
                case ShellState.Entry:
                    if ((enter || gSouth || gStart) && !VrInitBusy) Begin(enter ? "enter" : gSouth ? "pad_south" : "pad_start");
                    break;
                case ShellState.Running:
                    if (IsEnd()) { ShowEnd(); break; }
                    if (pKey || esc || gStart)
                    {
                        if (flow.Paused && flow.PauseReason == "leave") Log.Add("stop ignored (leave pause) frame=" + Time.frameCount);
                        else StopNow(pKey ? "p" : esc ? "esc" : "pad_start");
                    }
                    else if (cKey || gNorth) ToggleComfort(cKey ? "c" : "pad_north");
                    break;
                case ShellState.Stopped:
                    if (pKey || esc || gStart) ResumeNow(pKey ? "p" : esc ? "esc" : "pad_start");
                    else if (qKey) QuitNow("stopped_q");
                    else if (cKey || gNorth) ToggleComfort(cKey ? "c" : "pad_north");
                    break;
                case ShellState.End:
                    EndElapsedS += Time.unscaledDeltaTime;
                    if (qKey || esc || enter || gSouth || gStart) QuitNow("end_" + (qKey ? "q" : esc ? "esc" : enter ? "enter" : "pad"));
                    else if (EndElapsedS >= endAutoQuitS) QuitNow("end_auto");
                    else SetEndCountdown();
                    break;
            }
            if (toastLeftS > 0f) { toastLeftS -= Time.unscaledDeltaTime; if (toastLeftS <= 0f) toast.root.SetActive(false); }
        }

        bool IsEnd() => flow.HandedOver && !double.IsNaN(flow.EndS) && clock.ExperienceSeconds >= flow.EndS - 1e-9;

        void SetState(ShellState s, string cause)
        {
            Changes.Add(new Change { frame = Time.frameCount, real = Time.realtimeSinceStartupAsDouble, exp = clock != null ? clock.ExperienceSeconds : 0, from = State.ToString(), to = s.ToString(), cause = cause });
            Log.Add("state " + State + "→" + s + " cause=" + cause + " frame=" + Time.frameCount + " exp=" + (clock != null ? clock.ExperienceSeconds.ToString("F4") : "-"));
            State = s;
        }

        void Begin(string cause)
        {
            ShowOnly(null);
            SetState(ShellState.Running, "begin_" + cause);
            flow.Resume();
        }

        public void StopNow(string cause)
        {
            flow.Pause("user");
            // 体験の停止では音もすべて止める。設計49 は時計の上で鳴っている区間の音だけを止めるので、時計の上では終わったが
            // まだ鳴り残っている一度きりの音（時計と音の処理の時計の差の分）も、ここで止めて再開で戻す
            shellPaused.Clear();
            foreach (var a in audioSources) if (a != null && a.isPlaying) { a.Pause(); shellPaused.Add(a); }
            ShellPausedAudio = shellPaused.Count;
            SetState(ShellState.Stopped, "stop_" + cause);
            RefreshPause();
            ShowOnly(pause);
        }

        void ResumeNow(string cause)
        {
            ShowOnly(null);
            SetState(ShellState.Running, "resume_" + cause);
            flow.Resume();
            foreach (var a in shellPaused) if (a != null) a.UnPause();
            shellPaused.Clear();
        }

        void ToggleComfort(string cause)
        {
            if (rider == null) return;
            int to = rider.Level == comfortOnLevel ? comfortOffLevel : comfortOnLevel;
            rider.SetLevel(to);
            Log.Add("comfort " + cause + " → L" + rider.Level + " frame=" + Time.frameCount);
            Toast(ComfortText());
            if (State == ShellState.Stopped) RefreshPause();
        }

        void ShowEnd()
        {
            EndShownFrame = Time.frameCount;
            SetState(ShellState.End, "end");
            EndElapsedS = 0f;
            SetEndCountdown();
            ShowOnly(end);
        }

        void QuitNow(string cause)
        {
            if (State == ShellState.Quitting) return;
            QuitCause = cause;
            SetState(ShellState.Quitting, "quit_" + cause);
            try { QuitRequested?.Invoke(cause); } catch (Exception ex) { Debug.LogException(ex); }
            Debug.Log("DS50_QUIT: " + cause + " frame=" + Time.frameCount);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit(0);
#endif
        }

        // ---------------------------------------------------------------- 文
        string ComfortText()
        {
            int l = rider != null ? rider.Level : comfortOnLevel;
            return l == comfortOnLevel ? "揺れ軽減：オン（L0 水平を保つ）"
                 : l == comfortOffLevel ? "揺れ軽減：オフ（L3 舟の上下・向き・傾きをそのまま）"
                 : "揺れ：L" + l + "（1〜4 で選択）";
        }

        const string EntryTitle = "神奈川沖浪裏 ― 押送船に乗って大波を迎える";
        const string EntryIntro =
            "約 75 秒の体験です。はじめは静かな海で、あなたの乗る舟を少し動かせます。\n" +
            "やがて舟は自動で原画の位置へ導かれ、目の前で大波が立ち上がります。\n" +
            "大波は原画の姿になった瞬間で止まり、最後に原画の視点から自分の舟を見て終わります。";
        const string EntryKeysHead = "操作（キーボード ／ ゲームパッド）";
        const string EntryKeysLabel = "前進・減速\n旋回\n舟を止める\n体験の停止・再開\n揺れ軽減の切替\n座席に戻る\n終了";
        const string EntryKeysValue =
            "W・S（↑・↓） ／ 左スティック上下・R2・L2\n" +
            "A・D（←・→） ／ 左スティック左右\n" +
            "Space ／ ×\n" +
            "P または Esc ／ Options（すぐに止まります。もう一度押すと再開）\n" +
            "C ／ △（オン＝水平を保つ。1〜4 で細かく選べます）\n" +
            "R ／ クリエイト\n" +
            "停止中または終わりの画面で Q";
        const string EntryNotes =
            "舟を動かせる範囲の縁では、舟は柔らかく押し戻されて止まります。\n" +
            "座席から大きく離れると、体験は自動で一時停止します（戻ると再開）。";
        const string EntryBody = EntryIntro + EntryKeysHead + EntryKeysLabel + EntryKeysValue + EntryNotes;
        TextMesh entryKeysLabel, entryKeysValue, entryFoot;

        void RefreshEntry()
        {
            if (entry == null) return;
            string vr = VrRequested ? VrStatusJa + "\n" : "";
            string go = VrInitBusy ? "（VR の準備中です…）" : "Enter ／ × で始める";
            entry.body.text = EntryIntro + "\n\n" + EntryKeysHead;
            entryKeysLabel.text = EntryKeysLabel;
            entryKeysValue.text = EntryKeysValue;
            entryFoot.text = EntryNotes + "\n\n" + vr + go;
        }

        void RefreshPause()
        {
            if (pause == null) return;
            pause.body.text = "体験を止めています。時計・舟・音はこのまま止まっています。\n\n" +
                              "P または Esc ／ Options で再開\n" +
                              "Q で体験を終える\n\n" + ComfortText();
        }

        void SetEndCountdown()
        {
            if (end == null) return;
            int left = Mathf.Max(0, Mathf.CeilToInt(endAutoQuitS - EndElapsedS));
            end.body.text = "大波が原画の姿になった瞬間を、原画の視点から見ました。\n" +
                            "あなたの舟は、右手で波の斜面を登っている舟です。\n\n" +
                            "Q ／ Esc ／ Enter ／ × で終了します（" + left + " 秒後に自動で終了）";
        }

        void Toast(string s)
        {
            toast.body.text = s;
            toast.root.SetActive(true);
            toastLeftS = 2.5f;
        }

        // ---------------------------------------------------------------- 板
        void BuildPanels()
        {
            entry = MakePanel("DS50 入口の画面", new Vector2(1.10f, 1.10f), Vector2.zero, paperColor, 0.056f, 0.030f, false);
            entry.title.text = EntryTitle;
            entryKeysLabel = MakeText(entry.root.transform, "操作の名前");
            entryKeysValue = MakeText(entry.root.transform, "操作のキー");
            entryFoot = MakeText(entry.root.transform, "注意と始め方");
            pause = MakePanel("DS50 停止の画面", new Vector2(1.10f, 1.10f), Vector2.zero, paperColor, 0.070f, 0.036f, true);
            pause.title.text = "一時停止中";
            // 終わりの画面は原画の視点の右上の空に置き、左の大波と、右手で斜面を登る自分の舟（文で指す舟）を隠さない
            end = MakePanel("DS50 終わりの画面", new Vector2(0.46f, 0.32f), new Vector2(0.26f, 0.31f), endPaperColor, 0.055f, 0.026f, true);
            end.title.text = "おわり";
            toast = MakePanel("DS50 知らせ", new Vector2(0.62f, 0.085f), new Vector2(0f, -0.40f), paperColor, 0f, 0.034f, true);
            foreach (var p in new[] { entry, pause, end, toast }) p.root.SetActive(false);
            font.RequestCharactersInTexture(EntryTitle + EntryBody + "一時停止中おわり揺れ軽減オンフオ水平を保つ舟の上下向き傾きそのままVR（HMD）開始していますできませんでしたPC画面で続けます準備中始める体験止めています時計音はこのまま再開終える大波が原画姿になった瞬間を視点から見ました。あなたは右手斜面登っている秒後自動終了0123456789", 64);
            OnFontTex(font);
        }

        Panel MakePanel(string name, Vector2 sizeFrac, Vector2 centerFrac, Color bg, float titleEm, float bodyEm, bool centerText)
        {
            var p = new Panel { sizeFrac = sizeFrac, centerFrac = centerFrac, titleEm = titleEm, bodyEm = bodyEm, center = centerText };
            p.root = new GameObject(name);
            p.root.transform.SetParent(hmdCamera.transform, false);
            p.bg = GameObject.CreatePrimitive(PrimitiveType.Quad);
            Destroy(p.bg.GetComponent<Collider>());
            p.bg.name = "板";
            p.bg.transform.SetParent(p.root.transform, false);
            var r = p.bg.GetComponent<MeshRenderer>();
            r.sharedMaterial = new Material(panelMat) { color = bg, renderQueue = 4000 };
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.receiveShadows = false;
            textMat.renderQueue = 4001;
            if (titleEm > 0f) p.title = MakeText(p.root.transform, "題");
            p.body = MakeText(p.root.transform, "文");
            return p;
        }

        TextMesh MakeText(Transform parent, string name)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var tm = go.AddComponent<TextMesh>();
            tm.font = font; tm.fontSize = 64; tm.color = inkColor; tm.richText = false;
            tm.lineSpacing = 1.12f;
            var r = go.GetComponent<MeshRenderer>();
            r.sharedMaterial = textMat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.receiveShadows = false;
            return tm;
        }

        void ShowOnly(Panel p)
        {
            foreach (var q in new[] { entry, pause, end }) if (q != null) q.root.SetActive(q == p);
        }

        // 板は毎フレーム、今のカメラ（画角・近い面・縦横比）に合わせて置き直す（余韻で画角と近い面が変わるため）
        void LateUpdate()
        {
            if (!ready) return;
            if (textMat != null && font != null && font.material != null && font.material.mainTexture != lastFontTex) OnFontTex(font);
            foreach (var p in new[] { entry, pause, end, toast }) if (p != null && p.root.activeSelf) Layout(p);
        }

        void Layout(Panel p)
        {
            var cam = hmdCamera;
            bool xr = XRSettings.isDeviceActive;
            float d = xr ? Mathf.Max(vrPanelDistanceM, cam.nearClipPlane * 1.5f) : Mathf.Max(0.3f, cam.nearClipPlane * 1.5f);
            float hh = d * Mathf.Tan(0.5f * cam.fieldOfView * Mathf.Deg2Rad);   // 画面の高さの半分（その距離で）
            float aspect = xr ? 1f : Mathf.Max(0.2f, cam.aspect);
            float hw = hh * aspect;
            p.root.transform.localPosition = new Vector3(p.centerFrac.x * 2f * hw, p.centerFrac.y * 2f * hh, d);
            p.root.transform.localRotation = Quaternion.identity;
            p.root.transform.localScale = Vector3.one;
            p.bg.transform.localScale = new Vector3(p.sizeFrac.x * 2f * hw, p.sizeFrac.y * 2f * hh, 1f);
            float sh = 2f * hh;   // 画面の高さ（世界の長さ）
            float w = Mathf.Min(p.sizeFrac.x, 1f) * 2f * hw;
            float top = Mathf.Min(p.sizeFrac.y, 1f) * hh;
            float y = top - sh * 0.06f;
            if (p.title != null)
            {
                SetText(p.title, p.titleEm * sh, p.center, p.center ? 0f : -w * 0.44f, y);
                y -= p.titleEm * sh * 1.9f;
            }
            SetText(p.body, p.bodyEm * sh, p.center, p.center ? 0f : -w * 0.44f, p.title == null ? 0f : y);
            if (p.title == null) { p.body.anchor = TextAnchor.MiddleCenter; }
            if (p == entry)
            {
                // 入口だけ：説明（題の下の body）→ 操作の 2 列（名前・キー）→ 注意と始め方。行の高さは初回の画の実測（字の大きさ em のおよそ 1.5 倍）
                float em = p.bodyEm * sh, line = em * 1.5f;
                float x0 = -w * 0.44f, yk = y - line * 5.0f;
                SetText(entryKeysLabel, em, false, x0 + em * 1.0f, yk);
                SetText(entryKeysValue, em, false, x0 + em * 10.0f, yk);
                SetText(entryFoot, em, false, x0, yk - line * 7.3f);
            }
        }

        static void SetText(TextMesh t, float em, bool center, float x, float y)
        {
            t.characterSize = em * 10f / t.fontSize;
            t.anchor = center ? TextAnchor.UpperCenter : TextAnchor.UpperLeft;
            t.alignment = center ? TextAlignment.Center : TextAlignment.Left;
            t.transform.localPosition = new Vector3(x, y, -0.001f);
        }
    }
}
