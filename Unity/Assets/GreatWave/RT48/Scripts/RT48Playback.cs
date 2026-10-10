using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.InputSystem;

namespace GreatWave.RT48
{
    // RT48（Q48 の案 1）：FLIP42 R3 の巻き波の断面を、焼いた曲線から毎フレーム再生し、頂の向きに掃いて船から見る（計画 §3）。
    //   ・形は焼いた曲線のまま（再生の時に手で変えない）。補間は焼きの pair_interp の組だけ、混ぜる割合 (t − t_k) × 24。
    //     補間しない組（K から先・C4 で外れた組）は前のコマを保つ（まだ来ていないコマを先に見せない）。
    //   ・船：上下と縦揺れだけ。補間する組では描いている曲線（同じ組・同じ割合）の一番上の水面から、補間しない組ではコマごとの値を時刻で補間。
    //   ・時計：t ＝ 始めの時刻 ＋ 1.0 ×（unscaledTimeAsDouble − 押した時刻）。動画と試しは ManualClock で外から t を入れる。
    //   ・座標：X ＝ x − 座席の x、Y ＝ 静かな水面からの高さ、Z ＝ 頂の向き。波は −X から来て、船首は −X を向く。
    // 起動の引数（プレイヤー）：-rt48data <焼きのフォルダーかその親> -rt48source <id> -rt48seat <x> -rt48view bow|crest -rt48from <t>
    // キー：R 初めから、Space 止める／続ける、← → 止めている時に 1 コマ、1 / 2 座席、V 向き、F 元の切り替え、H 字、
    //       右ボタンを押して動かす 見回す、0 見回しを戻す、Esc / Q 終わる（VR の向きのやり直しは RT48Rig の C）。
    [DefaultExecutionOrder(-50)]
    public class RT48Playback : MonoBehaviour
    {
        [Header("場面の部品（RT48SceneBuilder が入れる）")]
        public MeshFilter sweepFilter;
        public MeshFilter loopsFilter;
        public MeshFilter seaFilter;
        public MeshFilter boatFilter;
        public Transform boatRoot;
        public Transform viewPivot;     // デスクトップの向きを入れる所（HMD Camera）
        public Camera viewCamera;
        public ComputeShader decodeCheck;

        [Header("設定")]
        [Tooltip("焼きの置き場（既定。; で区切って複数）。プレイヤーは -rt48data で変えられる")] public string defaultDataRoot = "";
        public double[] seatOptionsM = { 556.0, 574.0 };
        public string[] preferredSources = { "fine", "coarse", "synth" };
        public float eyeHeightM = 1.2f;
        public float alongCrestTurnDeg = 70f;
        public float desktopVFovDeg = 60f;
        public float nearClipM = 0.05f, farClipM = 25000f;
        public float fogDistM = 2000f;
        public float sunElevationDeg = 35f, sunAzimuthDeg = 40f;   // 方位：+X から +Z へ
        public Color sunColor = new Color(2.0f, 1.92f, 1.75f, 1f);
        public Color skyZenith = new Color(0.115f, 0.262f, 0.546f, 1f);
        public Color skyHorizon = new Color(0.578f, 0.658f, 0.716f, 1f);
        public Color skyGround = new Color(0.05f, 0.09f, 0.11f, 1f);
        public bool verifySha = true;

        // ---------------------------------------------------------------- 状態
        public readonly List<ISectionSource> Sources = new List<ISectionSource>();
        public ISectionSource Source { get; private set; }
        public int SourceIndex { get; private set; } = -1;
        public string DataRoot { get; private set; } = "";
        public string LoadError { get; private set; } = "";
        public double SeatX { get; private set; } = 556.0;
        public int ViewIndex { get; private set; }          // 0 船首の向き、1 頂に沿う向き
        public double TimeStart { get; private set; }
        public double TimeEnd { get; private set; }
        public string TimeEndFrom { get; private set; } = "";
        public double SimTime { get; private set; }
        public bool Paused { get; private set; }
        public bool Ended { get; private set; }
        public bool ManualClock { get; set; }
        public bool Initialized { get; private set; }
        public RT48SectionState State { get; private set; }
        public RT48BoatMotion.Pose BoatPose { get; private set; }
        public string BoatMode { get; private set; } = "";
        public double[] BoatYs { get; private set; } = new double[9];
        public int Restarts { get; private set; }
        public double ClipStartedRealtime { get; private set; }
        public event Action ClipRestarted, ClipEnded;
        public Vector2 LookOffsetDeg;
        public double[] FrameHeave => frameHeave;      // コマごとの上下（今の座席、補間しない所で使う）
        public double[] FramePitchDeg => framePitch;

        double clockOrigin, clockStartT, pausedAt;
        double[] curveXY, dispXY;
        double[] frameHeave = new double[0], framePitch = new double[0];
        int loopsFrame = -1;
        Mesh sweepMesh, loopsMesh, seaMesh, boatMesh;
        int sweepN = -1;
        readonly List<RT48Loop> loopList = new List<RT48Loop>();
        readonly List<Vector3> lv = new List<Vector3>(), ln = new List<Vector3>();
        readonly List<int> lt = new List<int>();
        readonly List<Vector2> lw = new List<Vector2>();

        static readonly int idCurves = Shader.PropertyToID("_RT48Curves"), idOffA = Shader.PropertyToID("_RT48OffsetA"), idOffB = Shader.PropertyToID("_RT48OffsetB"),
            idCount = Shader.PropertyToID("_RT48PointCount"), idAlpha = Shader.PropertyToID("_RT48Alpha"), idXShift = Shader.PropertyToID("_RT48XShift"),
            idTaper = Shader.PropertyToID("_RT48Taper"), idSunDir = Shader.PropertyToID("_RT48SunDir"), idSunCol = Shader.PropertyToID("_RT48SunColor"),
            idZen = Shader.PropertyToID("_RT48SkyZenith"), idHor = Shader.PropertyToID("_RT48SkyHorizon"), idGnd = Shader.PropertyToID("_RT48SkyGround"),
            idFogCol = Shader.PropertyToID("_RT48FogColor"), idFogDist = Shader.PropertyToID("_RT48FogDist");

        // ---------------------------------------------------------------- 引数
        public static string Arg(string name, string def)
        {
            var a = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(a, name);
            return i >= 0 && i + 1 < a.Length ? a[i + 1] : def;
        }
        public static bool HasArg(string name) => Array.IndexOf(Environment.GetCommandLineArgs(), name) >= 0;
        public static double ArgD(string name, double def) => double.TryParse(Arg(name, ""), NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : def;

        public double XShift => Source != null ? Source.XOriginM - SeatX : 0.0;
        public double XOfSeatStored => Source != null ? SeatX - Source.XOriginM : 0.0;
        public Vector3 SunDir
        {
            get
            {
                float e = sunElevationDeg * Mathf.Deg2Rad, a = sunAzimuthDeg * Mathf.Deg2Rad;
                return new Vector3(Mathf.Cos(e) * Mathf.Cos(a), Mathf.Sin(e), Mathf.Cos(e) * Mathf.Sin(a)).normalized;
            }
        }

        // ---------------------------------------------------------------- 始まり
        void Start()
        {
            if (!Application.isPlaying) return;
            Initialize(null);
            if (Source != null) Restart();
        }

        void OnDestroy() => ReleaseAll();
        void OnApplicationQuit() => ReleaseAll();

        public void ReleaseAll()
        {
            foreach (var s in Sources) s.Dispose();
            Sources.Clear();
            Source = null;
            Initialized = false;
        }

        // dataRootOverride が null なら、-rt48data、なければ defaultDataRoot、なければ Unity/Build/RT48/bake。
        public void Initialize(string dataRootOverride)
        {
            if (Initialized) return;
            ApplyShadingGlobals();
            string root = dataRootOverride ?? Arg("-rt48data", "");
            if (string.IsNullOrEmpty(root)) root = defaultDataRoot;
            if (string.IsNullOrEmpty(root)) root = Path.GetFullPath(Path.Combine(Application.dataPath, "../Build/RT48/data")) + ";" + Path.GetFullPath(Path.Combine(Application.dataPath, "../Build/RT48/bake"));
            DataRoot = root;
            foreach (var r in root.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries))
            {
                try { LoadSources(r.Trim()); }
                catch (Exception e) { LoadError += e.Message + " "; Debug.LogError("RT48_LOAD_ERROR " + e); }
            }
            SortSources();
            if (Sources.Count == 0 && string.IsNullOrEmpty(LoadError)) LoadError = "焼きが見つかりません：" + root;
            if (boatFilter != null)
            {
                boatMesh = RT48Geometry.BuildBoat();
                boatFilter.sharedMesh = boatMesh;
            }
            if (loopsFilter != null) { loopsMesh = new Mesh { name = "RT48 離れた水" }; loopsMesh.MarkDynamic(); loopsFilter.sharedMesh = loopsMesh; }
            if (viewCamera != null)
            {
                viewCamera.nearClipPlane = nearClipM; viewCamera.farClipPlane = farClipM;
                viewCamera.fieldOfView = desktopVFovDeg;
            }
            double seat = ArgD("-rt48seat", seatOptionsM.Length > 0 ? seatOptionsM[0] : 556.0);
            ViewIndex = Arg("-rt48view", "bow") == "crest" ? 1 : 0;
            Initialized = true;
            if (Sources.Count == 0) return;
            string want = Arg("-rt48source", "");
            int si = 0;
            if (!string.IsNullOrEmpty(want)) { int f = Sources.FindIndex(s => s.Id == want); if (f >= 0) si = f; }
            SeatX = seat;
            SelectSource(si);
            Debug.Log("RT48_INIT root=" + DataRoot + " sources=" + string.Join(",", Sources.ConvertAll(s => s.Id)) + " source=" + Source.Id + " seat=" + SeatX + " end=" + TimeEnd.ToString("F4", CultureInfo.InvariantCulture) + " (" + TimeEndFrom + ")");
        }

        void LoadSources(string root)
        {
            var dirs = new List<string>();
            if (RT48Bake.IsBakeDir(root)) dirs.Add(root);
            else if (Directory.Exists(root))
                foreach (var d in Directory.GetDirectories(root)) if (RT48Bake.IsBakeDir(d)) dirs.Add(d);
            var loaded = new List<ISectionSource>();
            foreach (var d in dirs)
            {
                try
                {
                    var b = RT48Bake.Load(d, verifySha);
                    if (b.ShaChecked && !b.ShaOk) Debug.LogWarning("RT48：SHA-256 が meta と合いません（" + d + "）：" + b.ShaNote);
                    if (Sources.Exists(s => s.Id == b.Meta.source_id) || loaded.Exists(s => s.Id == b.Meta.source_id)) { Debug.LogWarning("RT48：同じ名前の元を飛ばした：" + d); continue; }
                    loaded.Add(new RecordedSectionSource(b));
                }
                catch (Exception e) { LoadError += Path.GetFileName(d) + "：" + e.Message + " "; Debug.LogError("RT48_LOAD_ERROR " + d + " " + e); }
            }
            Sources.AddRange(loaded);
        }

        void SortSources()
        {
            Sources.Sort((a, b) =>
            {
                int ia = Array.IndexOf(preferredSources, a.Id), ib = Array.IndexOf(preferredSources, b.Id);
                if (ia < 0) ia = 99; if (ib < 0) ib = 99;
                return ia != ib ? ia.CompareTo(ib) : string.CompareOrdinal(a.Id, b.Id);
            });
        }

        // ---------------------------------------------------------------- 元・座席・向き
        public void SelectSource(int i)
        {
            if (Sources.Count == 0) return;
            SourceIndex = ((i % Sources.Count) + Sources.Count) % Sources.Count;
            Source = Sources[SourceIndex];
            int n = Source.PointCount;
            curveXY = new double[2 * n];
            dispXY = new double[2 * n];
            if (sweepFilter != null && sweepN != n)
            {
                sweepMesh = RT48Geometry.BuildSweep(n);
                sweepFilter.sharedMesh = sweepMesh;
                sweepN = n;
            }
            SetSeat(SeatX);
        }

        public void SetSeat(double x)
        {
            SeatX = x;
            if (Source == null) return;
            if (seaFilter != null)
            {
                var t = Source.TaperStored;
                float xa = (float)(t[0] + Source.XOriginM - SeatX), xb = (float)(t[3] + Source.XOriginM - SeatX);
                seaMesh = RT48Geometry.BuildSea(xa, xb, RT48Geometry.SweepZ[RT48Geometry.SweepZ.Length - 1]);
                seaFilter.sharedMesh = seaMesh;
            }
            ComputeFrameBoat();
            ComputeEnd();
            loopsFrame = -1;
            TimeStart = Math.Max(Source.TimeFirst, ArgD("-rt48from", Source.TimeFirst));
        }

        public void SetView(int v) { ViewIndex = v; ApplyDesktopView(); }

        void ComputeFrameBoat()
        {
            int F = Source.FrameCount;
            frameHeave = new double[F]; framePitch = new double[F];
            var ys = new double[9];
            for (int k = 0; k < F; k++)
            {
                Source.FillFrameCurve(k, curveXY);
                RT48BoatMotion.ToDisplayed(curveXY, Source.PointCount, Source.TaperStored, dispXY);
                var p = RT48BoatMotion.FromDisplayed(dispXY, Source.PointCount, XOfSeatStored, ys);
                frameHeave[k] = p.heave; framePitch[k] = p.pitchDeg;
            }
        }

        // 船からのクリップの終わり：焼きの表（座席ごと）。表にない座席は、最初の接触より後で、船体 ±6 m の鉛直の線が
        // 主な曲線と 3 回以上交わるか閉じた水に当たる最初のコマの 1 コマ前（読み方 1・2 を曲線に当てた。Unity の計算）。
        void ComputeEnd()
        {
            if (Source.TryGetSeatEnd(SeatX, out var e)) { TimeEnd = e; TimeEndFrom = "焼きの表"; return; }
            TimeEnd = EndFromCurves(out var from);
            TimeEndFrom = from;
        }

        public double EndFromCurves() => EndFromCurves(out _);

        public double EndFromCurves(out string from)
        {
            from = "最後のコマ（表になく、曲線にも多価の列がない）";
            int F = Source.FrameCount, n = Source.PointCount;
            for (int k = 1; k < F; k++)
            {
                double tk = Source.TimeFirst + k / Source.Fps;
                if (tk <= Source.ContactS + 1e-9) continue;
                Source.FillFrameCurve(k, curveXY);
                Source.GetLoops(k, loopList);
                bool multi = false;
                for (double xq = XOfSeatStored - 6.0; xq <= XOfSeatStored + 6.0 + 1e-9 && !multi; xq += 0.25)
                {
                    if (Crossings(curveXY, 0, n, xq, false) >= 3) multi = true;
                    foreach (var L in loopList) if (L.kind == 0 && CrossingsF(Source.LoopPoints, L.first, L.count, xq) > 0) multi = true;
                }
                if (multi) { from = "Unity の曲線から（読み方 1・2 を曲線に当てた）"; return Source.TimeFirst + (k - 1) / Source.Fps; }
            }
            return Source.TimeLast;
        }

        static int Crossings(double[] c, int first, int count, double xq, bool closed)
        {
            int cnt = 0, m = closed ? count : count - 1;
            for (int i = 0; i < m; i++)
            {
                int j = (i + 1) % count;
                double x0 = c[2 * (first + i)], x1 = c[2 * (first + j)];
                if ((x0 <= xq && x1 > xq) || (x1 <= xq && x0 > xq)) cnt++;
            }
            return cnt;
        }

        static int CrossingsF(float[] c, int first, int count, double xq)
        {
            int cnt = 0;
            for (int i = 0; i < count; i++)
            {
                int j = (i + 1) % count;
                double x0 = c[2 * (first + i)], x1 = c[2 * (first + j)];
                if ((x0 <= xq && x1 > xq) || (x1 <= xq && x0 > xq)) cnt++;
            }
            return cnt;
        }

        // ---------------------------------------------------------------- 時計
        public void Restart()
        {
            Ended = false; Paused = false;
            clockStartT = TimeStart;
            clockOrigin = Time.unscaledTimeAsDouble;
            ClipStartedRealtime = Time.realtimeSinceStartupAsDouble;
            Restarts++;
            ApplyTime(TimeStart);
            ClipRestarted?.Invoke();
        }

        public void TogglePause()
        {
            if (Ended) return;
            if (!Paused) { Paused = true; pausedAt = SimTime; }
            else { Paused = false; clockStartT = pausedAt; clockOrigin = Time.unscaledTimeAsDouble; }
        }

        public void StepFrames(int d)
        {
            if (Source == null) return;
            if (!Paused) TogglePause();
            int k = (int)Math.Floor((SimTime - Source.TimeFirst) * Source.Fps + 1e-6) + d;
            pausedAt = Math.Min(TimeEnd, Math.Max(TimeStart, Source.TimeFirst + k / Source.Fps));
            Ended = false;
            ApplyTime(pausedAt);
        }

        double autoQuitS = -1;

        void Update()
        {
            if (!Application.isPlaying || !Initialized) return;
            if (autoQuitS < 0) autoQuitS = ArgD("-rt48autoquit", 0);
            if (autoQuitS > 0 && Time.realtimeSinceStartupAsDouble > autoQuitS) { autoQuitS = 0; Quit("autoquit"); }
            ReadInput();
            if (Source == null || ManualClock) return;
            double t = Paused ? pausedAt : clockStartT + 1.0 * (Time.unscaledTimeAsDouble - clockOrigin);
            if (!Ended && t >= TimeEnd)
            {
                t = TimeEnd; Ended = true; Paused = false;
                ClipEnded?.Invoke();
            }
            if (Ended) t = TimeEnd;
            ApplyTime(t);
        }

        void LateUpdate()
        {
            if (Application.isPlaying) ApplyDesktopView();
        }

        // ---------------------------------------------------------------- 1 つの時刻を描く準備（Update とテストと動画が使う）
        public void ApplyTime(double t)
        {
            if (Source == null) return;
            SimTime = t;
            var s = Source.StateAt(t);
            State = s;
            ApplyShadingGlobals();
            Shader.SetGlobalBuffer(idCurves, Source.CurveBuffer);
            Shader.SetGlobalInteger(idOffA, s.offsetA);
            Shader.SetGlobalInteger(idOffB, s.offsetB);
            Shader.SetGlobalInteger(idCount, Source.PointCount);
            Shader.SetGlobalFloat(idAlpha, (float)s.alpha);
            Shader.SetGlobalFloat(idXShift, (float)XShift);
            var tp = Source.TaperStored;
            Shader.SetGlobalVector(idTaper, new Vector4((float)tp[0], (float)tp[1], (float)tp[2], (float)tp[3]));
            if (s.frame != loopsFrame && loopsMesh != null)
            {
                Source.GetLoops(s.frame, loopList);
                RT48Geometry.BuildLoops(loopsMesh, Source.LoopPoints, loopList, XShift, tp, lv, ln, lt, lw);
                loopsFrame = s.frame;
            }
            UpdateBoat(s);
        }

        void UpdateBoat(in RT48SectionState s)
        {
            RT48BoatMotion.Pose p;
            var ys = BoatYs;
            if (s.interpolating)
            {
                Source.FillCurve(s, curveXY);
                RT48BoatMotion.ToDisplayed(curveXY, Source.PointCount, Source.TaperStored, dispXY);
                p = RT48BoatMotion.FromDisplayed(dispXY, Source.PointCount, XOfSeatStored, ys);
                BoatMode = "curve";
            }
            else if (s.last)
            {
                int k = Source.FrameCount - 1;
                p = new RT48BoatMotion.Pose { heave = frameHeave[k], pitchDeg = framePitch[k], ok = true };
                BoatMode = "frame_last";
            }
            else
            {
                int k = s.frame;
                double w = s.w;
                p = new RT48BoatMotion.Pose { heave = frameHeave[k] + (frameHeave[k + 1] - frameHeave[k]) * w, pitchDeg = framePitch[k] + (framePitch[k + 1] - framePitch[k]) * w, ok = true };
                BoatMode = "frame_lerp";
            }
            p.slope = Math.Tan(p.pitchDeg * Math.PI / 180.0);
            BoatPose = p;
            if (boatRoot != null)
            {
                boatRoot.localPosition = new Vector3(0f, (float)p.heave, 0f);
                boatRoot.localRotation = Quaternion.Euler(0f, 0f, (float)p.pitchDeg);   // +X（船尾）が上がる向きが正
            }
        }

        public void ApplyShadingGlobals()
        {
            Shader.SetGlobalVector(idSunDir, SunDir);
            Shader.SetGlobalVector(idSunCol, sunColor);
            Shader.SetGlobalVector(idZen, skyZenith);
            Shader.SetGlobalVector(idHor, skyHorizon);
            Shader.SetGlobalVector(idGnd, skyGround);
            Shader.SetGlobalVector(idFogCol, skyHorizon);
            Shader.SetGlobalFloat(idFogDist, fogDistM);
        }

        // デスクトップと動画の向き：船首の向き（−X）か、船首から頂の向き（+Z）へ alongCrestTurnDeg 振り向いた向き。VR では RT48Rig が止める。
        public bool DesktopViewEnabled { get; set; } = true;
        public float ViewYawDeg => -90f + (ViewIndex == 1 ? alongCrestTurnDeg : 0f);

        public void ApplyDesktopView()
        {
            if (!DesktopViewEnabled || viewPivot == null) return;
            viewPivot.localPosition = Vector3.zero;
            viewPivot.localRotation = Quaternion.Euler(-LookOffsetDeg.y, ViewYawDeg + LookOffsetDeg.x, 0f);
            if (viewCamera != null && !viewCamera.stereoEnabled) viewCamera.fieldOfView = desktopVFovDeg;
        }

        // ---------------------------------------------------------------- 入力
        void ReadInput()
        {
            var kb = Keyboard.current;
            if (kb == null) return;
            if (kb.rKey.wasPressedThisFrame && Source != null) Restart();
            if (kb.spaceKey.wasPressedThisFrame) TogglePause();
            if (kb.rightArrowKey.wasPressedThisFrame) StepFrames(1);
            if (kb.leftArrowKey.wasPressedThisFrame) StepFrames(-1);
            if (kb.digit1Key.wasPressedThisFrame && seatOptionsM.Length > 0) { SetSeat(seatOptionsM[0]); Restart(); }
            if (kb.digit2Key.wasPressedThisFrame && seatOptionsM.Length > 1) { SetSeat(seatOptionsM[1]); Restart(); }
            if (kb.vKey.wasPressedThisFrame) SetView(1 - ViewIndex);
            if (kb.fKey.wasPressedThisFrame && Sources.Count > 1) { double t = SimTime; SelectSource(SourceIndex + 1); if (Paused) ApplyTime(Math.Min(t, TimeEnd)); else Restart(); }
            if (kb.digit0Key.wasPressedThisFrame) LookOffsetDeg = Vector2.zero;
            if (kb.escapeKey.wasPressedThisFrame || kb.qKey.wasPressedThisFrame) Quit("key");
            var ms = Mouse.current;
            if (ms != null && ms.rightButton.isPressed)
            {
                var d = ms.delta.ReadValue() * 0.12f;
                LookOffsetDeg = new Vector2(LookOffsetDeg.x + d.x, Mathf.Clamp(LookOffsetDeg.y + d.y, -80f, 80f));
            }
        }

        public void Quit(string cause)
        {
            Debug.Log("RT48_QUIT cause=" + cause);
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }

        public string FrameLabel()
        {
            if (Source == null) return "";
            var s = State;
            int f = Source.FrameNumberFirst + s.frame;
            return s.interpolating ? ("コマ " + f + "→" + (f + 1) + "、割合 " + s.alpha.ToString("F3", CultureInfo.InvariantCulture))
                                   : ("コマ " + f + "（補間なし" + (s.reason == 1 ? "・K から先" : s.reason == 2 ? "・C4 で外れた組" : s.reason == 3 ? "・自分と交わる組" : s.last ? "・最後のコマ" : "") + "）");
        }
    }
}
