// FLIP3D：体験の 1 本の時計（2026-10-17、Claude。新しいファイル。ほかのファイルは変えていない）。
//
// 何をするか：
//   - 体験の時刻 T（実時間。止めを含む）を持ち、再生の時計 s（止めを除く）に直して FLIP3DPlayer.ApplyTime(s) を毎フレーム呼ぶ。
//     プレイヤーは「s → 記録」を選ぶだけにする（mode = Seat：プレイヤー自身の止め・視点の重みは使わない。enabled = false：プレイヤーの Update・キー・画面の字を止める）。
//     記録の選び方（floor(s × 記録の数/s)、コマの間の形は作らない）はプレイヤーのまま変えない。
//   - 視点の動きの予定（座席 → 見える動き → 原画に最も近い瞬間に着く → 止め → 原画の視点に留まる → 終わり）をここで作り、重み ViewBlend を FLIP3DXR に渡す。
//       繰り返しのクリップ（12 s の窓など）：着く瞬間 = manifest の原画に最も近い記録（print_record_index）。座席に minSeatSeconds 以上いてから動き始める
//         いちばん早い周期を選ぶ：s_着く = n × 周期 + 記録の時刻、n = ceil((minSeatSeconds + 動き − 記録の時刻) / 周期)。
//       続けて再生のクリップ：-f3dmoves があればプレイヤーの予定（FLIP3DPlayer.Moves）のまま。なければ manifest の崩れ（breakers）のうち、
//         座席の時間が minSeatSeconds 以上になる物の中で score3 が最も小さい物（原画に最も近い）。どれもなければプレイヤーの既定（manifest の原画に最も近い瞬間）。
//     着いた瞬間に再生の時計だけを holdSeconds 止める（水の形は変えない）。重みは S 字（3u² − 2u³）で、着く瞬間にちょうど 1。白い画面・黒い画面で隠さない。
//   - 音の手掛かり：start、move_begin、arrive（原画に最も近い瞬間。DS49 のツケ打ちの所）、hold_end、return_begin、return_end、loop_seam（繰り返しの継ぎ目）、
//     breaker_onset・breaker_best・breaker_touchdown（続けて再生は manifest の breakers の巻き始め・最良・着水 + 0.5 s。繰り返しは breaker_best だけ）、end、restart。
//     C# の event CueFired と UnityEvent onCue（Inspector でつなぐ）で知らせる。sounds（手掛かり → AudioSource）は音の処理の時計で前もって予約する（PlayScheduled）。
//     引数 -f3dexpsound "arrive=G:/…/ds49_tstar.wav;start=…/ds49_rumble.wav!loop*0.6;move_begin=…@-0.5" でも WAV（PCM 16 bit・float 32 bit）を読んでつなげる。
//   - 始め・止め・始め直し（運営の PC のキーボード）：Space・Enter（ゲームパッドの ×）始める、P（Options）止める ⇔ 再開、R 始め直し（0.6 s の黒い幕。視点の動きではない）、
//     止めている時・終わった後の Q で終える。体験の終わりの後も時計は進む（繰り返しのクリップは原画の視点で波が続き、続けて再生は最後の記録で止まる）。
//   - 起動の引数 -f3dexp で、場面を変えずにこの Script と FLIP3DXR を FLIP3DPlayer の GameObject に足す（RuntimeInitializeOnLoadMethod）。-vr だけなら FLIP3DXR だけ足す。
//   - 画面外の描画（確かめ・動画用。実時間ではない）：-f3dexpfps <n> で T を 1/n s ずつ進め、記録が来るまで待つ（player.manualClock）。
//     -f3dexpcap <フォルダー> でフレームごとに f_00000.jpg と frames.csv（T・s・止め・重み・記録・コマ・heave・暗がり・手掛かり）を書く。-f3dexpquit で終わり + 3 s で終える。
//
// 引数：-f3dexp  -f3dexpseat <s>  -f3dexpmove <s>  -f3dexphold <s>  -f3dexpstay <s>  -f3dexpback <s>（座席へ戻る。なければ原画の視点で終わる）
//       -f3dexpdelay <s>  -f3dexpwait（キーで始める）  -f3dexprestart <s>（終わりの後に自動で始め直す）  -f3dexpnobreaker
//       -f3dexpsound <手掛かり=WAV[@秒][!loop][*音量];…>  -f3dexpfps <n>  -f3dexpcap <dir>  -f3dexpquit  -f3dexptail <s>
//   プレイヤーの引数（-f3ddata・-f3dplay・-f3dfrom・-f3dto・-f3dmoves・-f3dmovesec・-f3dhold・-f3dstay・-f3dtiles など）もそのまま効く。
// 印：【選び】minSeatSeconds 12 s（うねりの 1 周期を座席で見てから動く）、終わりは原画の視点に留まる（returnToSeat = false）、startDelaySeconds 2 s、fadeSeconds 0.6 s。
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Events;

namespace GreatWave.FLIP3D
{
    [DefaultExecutionOrder(-100)]
    public class FLIP3DExperience : MonoBehaviour
    {
        public enum Phase { Loading, Waiting, Running, Paused, Failed }

        [Serializable]
        public struct Cue
        {
            public string id;
            public int k, frame;
            public double T, s, simT;                 // 体験の時刻、再生の時計、計算の時刻
        }

        [Serializable]
        public class CueSound
        {
            public string cue = "arrive";
            public AudioSource source;
            [Tooltip("空なら source.clip のまま")] public AudioClip clip;
            [Tooltip("手掛かりからのずれ（s）。負なら前から鳴らす")] public float offsetSeconds;
            [Range(0f, 1f)] public float volume = 1f;
            public bool loop;
        }

        [Serializable] public class CueEvent : UnityEvent<string> { }    // Inspector でつなぐ（手掛かりの id を渡す）

        struct Stop { public double s, move, hold, stay, back; public int k, frame, record; }
        struct Env { public double u0, u1, d0, d1; public int first, last; }
        class Sched { public double T; public int sound, cue, state; }    // state 0 まだ・1 予約した・2 鳴らさない

        [Header("つなぐ物（空なら同じ GameObject・場面から探す）")]
        public FLIP3DPlayer player;
        public FLIP3DXR rig;

        [Header("体験の時間（s）")]
        [Tooltip("座席にいる最短の時間（動き始めまで）")]
        public float minSeatSeconds = 12f;
        [Tooltip("0 以下ならプレイヤーの moveSeconds（既定 6）")] public float moveSeconds = -1f;
        [Tooltip("負ならプレイヤーの printHold（既定 2）")] public float holdSeconds = -1f;
        [Tooltip("負ならプレイヤーの moveStay（既定 6）。着いた後、原画の視点に留まる再生の秒")] public float staySeconds = -1f;
        public bool returnToSeat;
        [Tooltip("0 以下ならプレイヤーの moveBack（正なら）か 6")] public float returnSeconds = -1f;
        [Tooltip("座席へ戻った後、終わりまで座席にいる秒（繰り返しのクリップ）")] public float tailSeatSeconds = 4f;
        [Tooltip("続けて再生で -f3dmoves がない時、座席の時間が足りる崩れのうち score3 の最も小さい物へ動く")] public bool chooseBreaker = true;

        [Header("始め・終わり")]
        public bool autoStart = true;
        public float startDelaySeconds = 2f;
        [Tooltip("負なら自動で始め直さない")] public float autoRestartAfterEndSeconds = -1f;
        public float fadeSeconds = 0.6f;
        [Tooltip("始める時に向き直す（VR）")] public bool recenterOnStart = true;

        [Header("音の手掛かり")]
        public List<CueSound> sounds = new List<CueSound>();
        public float scheduleAheadSeconds = 0.15f;
        public CueEvent onCue = new CueEvent();
        public event Action<Cue> CueFired;

        [Header("画面外の描画（確かめ・動画用）")]
        public float fixedStepFps;
        public string captureDir = "";
        public bool quitAtEnd;
        public float captureTailSeconds = 3f;

        // ---------------------------------------------------------------- 状態（読むだけ）
        public Phase State { get; private set; } = Phase.Loading;
        public bool Driving => State != Phase.Loading && State != Phase.Failed;
        public bool Ended { get; private set; }
        public double T { get; private set; }
        public double S { get; private set; }
        public bool Frozen { get; private set; }
        public float ViewBlend { get; private set; }
        public double EndT { get; private set; }
        public double StepSeconds => fixedStepFps > 0f ? 1.0 / fixedStepFps : 0.0;
        public string PlanText { get; private set; } = "";
        public string LastError { get; private set; }
        public IReadOnlyList<Cue> Cues => cues;
        public int CuesFired { get; private set; }
        public int StopCount => stops.Count;
        public double ArriveT(int i) => TArrive(i);

        readonly List<Stop> stops = new List<Stop>();
        readonly List<Env> envs = new List<Env>();
        readonly List<Cue> cues = new List<Cue>();
        readonly List<Sched> sched = new List<Sched>();
        readonly List<AudioSource> pausedSources = new List<AudioSource>();
        int cuePtr, schedPtr, capFrame;
        long stepIndex;
        double t0, pausedAt, waitSince, cFrom, sTotal, loopL;
        bool isLoop, restartPending;
        float fade, fadeTarget;
        StreamWriter csv;
        StringBuilder firedThisFrame;
        static readonly CultureInfo CI = CultureInfo.InvariantCulture;

        static double Now() => Time.unscaledTimeAsDouble;       // フレームの始めの時刻（同じフレームの中では同じ値）
        static float ArgF(string name, float def)
        {
            var s = FLIP3DPlayer.Arg(name, "");
            return s.Length > 0 && float.TryParse(s, NumberStyles.Float, CI, out var v) ? v : def;
        }

        // ---------------------------------------------------------------- 場面を変えずに足す
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            bool exp = FLIP3DPlayer.HasArg("-f3dexp"), vr = FLIP3DXR.VrArgGiven();
            if (!exp && !vr) return;
            var p = FindAnyObjectByType<FLIP3DPlayer>();
            if (p == null) return;                                  // FLIP3D の場面ではない（DS50 なども --vr を使う）
            if (exp && FindAnyObjectByType<FLIP3DExperience>() == null) p.gameObject.AddComponent<FLIP3DExperience>();
            if (FindAnyObjectByType<FLIP3DXR>() == null) p.gameObject.AddComponent<FLIP3DXR>();
            Debug.Log("F3DEXP_BOOT experience=" + exp + " vr_flag=" + vr + " on=" + p.gameObject.name);
        }

        // ---------------------------------------------------------------- 始まり
        void Awake()
        {
            if (!Application.isPlaying) return;
            if (player == null) player = GetComponent<FLIP3DPlayer>();
            if (player == null) player = FindAnyObjectByType<FLIP3DPlayer>();
            if (player != null) player.enabled = false;            // 時計の持ち主はこの Script（プレイヤーの Start・Update・キー・画面の字は動かない）
            ApplyArgs();
            if (rig == null) rig = GetComponent<FLIP3DXR>();
            if (rig == null) rig = FindAnyObjectByType<FLIP3DXR>();
            if (rig == null && player != null) rig = player.gameObject.AddComponent<FLIP3DXR>();   // 視点の動きは FLIP3DXR が置く
            if (rig != null)
            {
                rig.experience = this;
                if (fixedStepFps > 0f) rig.xrStart = FLIP3DXR.XrStart.Never;   // 画面外の描画は PC の画面だけ
            }
        }

        public void ApplyArgs()
        {
            minSeatSeconds = ArgF("-f3dexpseat", minSeatSeconds);
            moveSeconds = ArgF("-f3dexpmove", moveSeconds);
            holdSeconds = ArgF("-f3dexphold", holdSeconds);
            staySeconds = ArgF("-f3dexpstay", staySeconds);
            var back = FLIP3DPlayer.Arg("-f3dexpback", "");
            if (back.Length > 0 && float.TryParse(back, NumberStyles.Float, CI, out var bv)) { returnToSeat = true; returnSeconds = bv; }
            startDelaySeconds = ArgF("-f3dexpdelay", startDelaySeconds);
            if (FLIP3DPlayer.HasArg("-f3dexpwait")) autoStart = false;
            autoRestartAfterEndSeconds = ArgF("-f3dexprestart", autoRestartAfterEndSeconds);
            if (FLIP3DPlayer.HasArg("-f3dexpnobreaker")) chooseBreaker = false;
            fixedStepFps = ArgF("-f3dexpfps", fixedStepFps);
            captureDir = FLIP3DPlayer.Arg("-f3dexpcap", captureDir);
            if (!string.IsNullOrEmpty(captureDir) && fixedStepFps <= 0f) fixedStepFps = 24f;
            if (FLIP3DPlayer.HasArg("-f3dexpquit")) quitAtEnd = true;
            captureTailSeconds = ArgF("-f3dexptail", captureTailSeconds);
            if (fixedStepFps > 0f) { startDelaySeconds = 0f; autoStart = true; recenterOnStart = false; }
            LoadSoundArgs();
        }

        void Start()
        {
            if (!Application.isPlaying) return;
            if (player == null) { Fail("場面に FLIP3DPlayer がない"); return; }
            try
            {
                bool fresh = !player.Initialized;
                if (fresh) player.ApplyArgs();
                player.mode = FLIP3DPlayer.Mode.Seat;                // 止め・視点の重みはこの Script が持つ（プレイヤーは記録を選ぶだけ）
                player.endAction = FLIP3DPlayer.EndAction.Hold;     // 黒い切れ目は使わない
                player.showLabel = false;                           // 目の前の絵に字を出さない
                player.manualClock = fixedStepFps > 0f;             // 画面外の描画だけ、記録が来るまで待つ。実時間では待たない（間に合わなければ前の記録のまま）
                if (fresh) player.Init();
                if (!player.Initialized) { Fail("FLIP3DPlayer.Init が終わらない：" + player.LastError); return; }
                BuildPlan();
            }
            catch (Exception e) { Fail(e.ToString()); return; }
            if (fixedStepFps > 0f)
            {
                Time.captureDeltaTime = 1f / fixedStepFps;
                if (!string.IsNullOrEmpty(captureDir)) OpenCapture();
            }
            ApplyAt(0.0);
            State = Phase.Waiting;
            waitSince = Now();
            Debug.Log("F3DEXP_READY " + PlanText);
        }

        void Fail(string why)
        {
            LastError = why;
            State = Phase.Failed;
            Debug.LogError("F3DEXP_FAIL " + why);
        }

        void OnDestroy()
        {
            CloseCapture();
            if (fixedStepFps > 0f) Time.captureDeltaTime = 0f;
        }

        // ---------------------------------------------------------------- 予定
        public void BuildPlan()
        {
            var mf = player.Manifest;
            double mv = moveSeconds > 0f ? moveSeconds : player.moveSeconds;
            double hd = holdSeconds >= 0f ? holdSeconds : player.printHold;
            double sy = staySeconds >= 0f ? staySeconds : player.moveStay;
            double bk = returnSeconds > 0f ? returnSeconds : (player.moveBack > 0f ? player.moveBack : 6.0);
            stops.Clear();
            isLoop = player.playback == FLIP3DPlayer.Playback.Loop;
            string chose = "";
            if (isLoop)
            {
                loopL = player.LoopSeconds;
                if (!(loopL > 0)) throw new InvalidDataException("manifest の loop_seconds が 0");
                cFrom = 0; sTotal = double.PositiveInfinity;
                if (mf.print_record_frame > 0)
                {
                    double P = player.PrintPhase;
                    int n = Math.Max(0, (int)Math.Ceiling((minSeatSeconds + mv - P) / loopL - 1e-9));
                    stops.Add(new Stop { s = n * loopL + P, move = mv, hold = hd, stay = sy, back = returnToSeat ? bk : -1, k = mf.breaker_k, frame = mf.print_record_frame, record = mf.print_record_index });
                    chose = "print_record n=" + n;
                }
                else chose = "manifest に原画に最も近い記録がない（座席だけ）";
            }
            else
            {
                cFrom = player.PlayFromSim - mf.t_first;
                sTotal = player.ContinuousSeconds;                 // mode = Seat なので範囲の長さそのもの
                bool given = FLIP3DPlayer.Arg("-f3dmoves", "").Length > 0;
                if (chooseBreaker && !given && mf.breakers != null)
                {
                    FLIP3DBreaker best = null;
                    foreach (var b in mf.breakers)
                    {
                        double sb = (b.frame - mf.frame_first) / mf.sim_fps - cFrom;
                        if (sb - mv < minSeatSeconds || sb >= sTotal) continue;
                        if (best == null || b.score3 < best.score3) best = b;
                    }
                    if (best != null) { player.moveSpec = "k" + best.k.ToString(CI); player.BuildTimeline(); chose = "breaker k" + best.k + " score3=" + best.score3.ToString("F3", CI); }
                    else chose = "座席の時間が足りる崩れがない（プレイヤーの予定のまま）";
                }
                else chose = given ? "-f3dmoves " + player.moveSpec : "プレイヤーの予定";
                foreach (var e in player.Moves)
                    stops.Add(new Stop
                    {
                        s = e.c - cFrom, move = moveSeconds > 0f ? moveSeconds : e.move, hold = holdSeconds >= 0f ? holdSeconds : e.hold,
                        stay = staySeconds >= 0f ? staySeconds : e.stay, back = e.back, k = e.k, frame = e.frame, record = e.record
                    });
                if (stops.Count > 0) { var l = stops[stops.Count - 1]; l.back = returnToSeat ? bk : -1; stops[stops.Count - 1] = l; }
            }
            stops.Sort((a, b) => a.s.CompareTo(b.s));
            BuildEnvelopes();
            if (stops.Count == 0) EndT = isLoop ? Math.Max(minSeatSeconds, loopL) : sTotal;
            else
            {
                int li = stops.Count - 1; var l = stops[li]; double ta = TArrive(li);
                if (l.back < 0) EndT = ta + l.hold + l.stay;
                else EndT = isLoop ? ta + l.hold + l.stay + l.back + tailSeatSeconds : SToT(sTotal);
                if (!isLoop) EndT = Math.Min(EndT, SToT(sTotal));
            }
            BuildCues();
            BuildSched();
            var sb2 = new StringBuilder();
            sb2.AppendFormat(CI, "playback={0} data={1} records={2} record_fps={3:0.##} {4} choose=[{5}] stops=[", player.playback, player.CurrentDataDir, player.RecordCount, mf.record_fps,
                isLoop ? string.Format(CI, "loop_s={0:F3}", loopL) : string.Format(CI, "range_sim={0:F3}-{1:F3}", player.PlayFromSim, player.PlayToSim), chose);
            for (int i = 0; i < stops.Count; i++)
            {
                var e = stops[i];
                sb2.AppendFormat(CI, "{0}k{1} f{2} r{3} s={4:F3} T_arrive={5:F3} move={6:0.##} hold={7:0.##} stay={8:0.##} back={9:0.##}", i > 0 ? "; " : "",
                    e.k, e.frame, e.record, e.s, TArrive(i), e.move, e.hold, e.stay, e.back);
            }
            sb2.AppendFormat(CI, "] end_T={0:F3} cues={1} sounds={2}", EndT, cues.Count, sounds.Count);
            PlanText = sb2.ToString();
        }

        void BuildEnvelopes()
        {
            envs.Clear();
            int i = 0;
            while (i < stops.Count)
            {
                int j = i;
                while (j + 1 < stops.Count)
                {
                    var a = stops[j]; var b = stops[j + 1];
                    if (a.back >= 0 && a.s + a.stay + a.back <= b.s - b.move) break;   // 戻ってから次の動き：別の山
                    j++;                                                                  // 重なる：戻らずに原画の視点に留まる
                }
                var e = stops[i]; var last = stops[j];
                double d0 = last.back >= 0 ? last.s + last.stay : double.PositiveInfinity;
                double d1 = last.back >= 0 ? d0 + last.back : double.PositiveInfinity;
                envs.Add(new Env { u0 = e.s - e.move, u1 = e.s, d0 = d0, d1 = d1, first = i, last = j });
                i = j + 1;
            }
        }

        // 体験の時刻 T → 再生の時計 s（着いた瞬間から hold の間は s を止める）
        public void Map(double t, out double s, out bool frozen)
        {
            double acc = 0;
            foreach (var st in stops)
            {
                double ta = st.s + acc;
                if (t < ta) { s = t - acc; frozen = false; return; }
                if (t < ta + st.hold) { s = st.s; frozen = true; return; }
                acc += st.hold;
            }
            s = t - acc; frozen = false;
        }

        // 再生の時計 s → 体験の時刻 T（s がちょうど着く瞬間なら、その止めの前）
        public double SToT(double s)
        {
            double acc = 0;
            foreach (var st in stops) { if (st.s < s - 1e-9) acc += st.hold; else break; }
            return s + acc;
        }

        double TArrive(int i)
        {
            double acc = 0;
            for (int j = 0; j < i; j++) acc += stops[j].hold;
            return stops[i].s + acc;
        }

        static float Smooth(float u) { u = Mathf.Clamp01(u); return u * u * (3f - 2f * u); }

        float EnvBlend(double s)
        {
            float b = 0f;
            foreach (var v in envs)
            {
                if (s < v.u0) continue;
                float x;
                if (s < v.u1) x = Smooth((float)((s - v.u0) / Math.Max(1e-9, v.u1 - v.u0)));
                else if (s <= v.d0) x = 1f;
                else if (s < v.d1) x = 1f - Smooth((float)((s - v.d0) / Math.Max(1e-9, v.d1 - v.d0)));
                else x = 0f;
                b = Math.Max(b, x);
            }
            return b;
        }

        double SimTime(double s)
        {
            var mf = player.Manifest;
            if (isLoop) { double r = s % loopL; if (r < 0) r += loopL; return mf.t_first + r; }
            return mf.t_first + cFrom + Math.Min(Math.Max(0, s), sTotal);
        }

        void BuildCues()
        {
            var mf = player.Manifest;
            var tmp = new List<KeyValuePair<Cue, int>>();
            int seq = 0;
            void Add(string id, double T, double s, int k, int frame) =>
                tmp.Add(new KeyValuePair<Cue, int>(new Cue { id = id, T = T, s = s, k = k, frame = frame, simT = SimTime(s) }, seq++));
            Add("start", 0, 0, 0, -1);
            foreach (var v in envs)
            {
                var a = stops[v.first]; var z = stops[v.last];
                double u0 = Math.Max(0, v.u0);
                Add("move_begin", SToT(u0), u0, a.k, a.frame);
                if (!double.IsInfinity(v.d0)) { Add("return_begin", SToT(v.d0), v.d0, z.k, z.frame); Add("return_end", SToT(v.d1), v.d1, z.k, z.frame); }
            }
            for (int i = 0; i < stops.Count; i++)
            {
                var e = stops[i]; double ta = TArrive(i);
                Add("arrive", ta, e.s, e.k, e.frame);
                if (e.hold > 0) Add("hold_end", ta + e.hold, e.s, e.k, e.frame);
            }
            if (isLoop)
            {
                double horizon = EndT + 300.0;                      // 終わりの後も時計は進むので、5 分先まで手掛かりを作る
                for (int m = 0; m < 1000; m++)
                {
                    double ss = m * loopL;
                    if (SToT(ss) > horizon) break;
                    if (m > 0) Add("loop_seam", SToT(ss), ss, 0, mf.frame_first);
                    if (mf.print_record_frame > 0) { double sb = ss + player.PrintPhase; Add("breaker_best", SToT(sb), sb, mf.breaker_k, mf.print_record_frame); }
                }
            }
            else if (mf.breakers != null)
            {
                foreach (var b in mf.breakers)
                {
                    foreach (var (id, f) in new[] { ("breaker_onset", b.win_first), ("breaker_best", b.frame), ("breaker_touchdown", b.win_last) })
                    {
                        double sf = (f - mf.frame_first) / mf.sim_fps - cFrom;
                        if (sf >= 0 && sf <= sTotal) Add(id, SToT(sf), sf, b.k, f);
                    }
                }
            }
            Map(EndT, out double sEnd, out _);
            Add("end", EndT, sEnd, 0, -1);
            tmp.Sort((x, y) => { int c = x.Key.T.CompareTo(y.Key.T); return c != 0 ? c : x.Value.CompareTo(y.Value); });
            cues.Clear();
            foreach (var kv in tmp) cues.Add(kv.Key);
            cuePtr = 0;
        }

        void BuildSched()
        {
            sched.Clear();
            for (int ci = 0; ci < cues.Count; ci++)
                for (int si = 0; si < sounds.Count; si++)
                {
                    var cs = sounds[si];
                    if (cs != null && cs.source != null && cs.cue == cues[ci].id) sched.Add(new Sched { T = cues[ci].T + cs.offsetSeconds, sound = si, cue = ci });
                }
            sched.Sort((a, b) => a.T.CompareTo(b.T));
            schedPtr = 0;
        }

        // ---------------------------------------------------------------- 毎フレーム
        void Update()
        {
            if (State == Phase.Loading || State == Phase.Failed) return;
            HandleKeys();
            double now = Now();
            float fdt = fixedStepFps > 0f ? (float)StepSeconds : Time.unscaledDeltaTime;
            fade = fadeSeconds > 0f ? Mathf.MoveTowards(fade, fadeTarget, fdt / fadeSeconds) : fadeTarget;
            if (rig != null) rig.Fade = fade;
            if (restartPending && fade >= 0.999f) DoRestart();
            switch (State)
            {
                case Phase.Waiting:
                    if (rig != null && rig.XrRequested && rig.XrBusy) waitSince = now;          // VR の始まりを待つ
                    else if (autoStart && !restartPending && now - waitSince >= startDelaySeconds) Begin();
                    break;
                case Phase.Running:
                    Advance(fixedStepFps > 0f ? (++stepIndex) * StepSeconds : now - t0);
                    break;
            }
            if (State == Phase.Running && Ended && autoRestartAfterEndSeconds >= 0f && T - EndT >= autoRestartAfterEndSeconds) Restart();
        }

        public void Begin()
        {
            if (State != Phase.Waiting) return;
            if (recenterOnStart && rig != null) rig.Recenter();
            State = Phase.Running;
            t0 = Now(); stepIndex = 0; Ended = false; CuesFired = 0;
            cuePtr = 0; schedPtr = 0;
            foreach (var e in sched) e.state = 0;
            if (csv != null) StartCoroutine(CaptureLoop());
            Advance(0.0);
        }

        void Advance(double t)
        {
            T = t;
            ApplyAt(t);
            while (cuePtr < cues.Count && cues[cuePtr].T <= t + 1e-9) Fire(cues[cuePtr++]);
            ScheduleSounds(t);
            if (!Ended && t >= EndT - 1e-9) Ended = true;
            if (Ended && quitAtEnd && t >= EndT + captureTailSeconds) Quit("end");
        }

        void ApplyAt(double t)
        {
            Map(t, out double s, out bool frozen);
            S = s; Frozen = frozen;
            ViewBlend = frozen ? 1f : EnvBlend(s);
            player.ApplyTime(s);
        }

        void Fire(Cue c)
        {
            CuesFired++;
            Debug.Log(string.Format(CI, "F3DEXP_CUE id={0} k={1} frame={2} T={3:F3} s={4:F3} sim_t={5:F3} shown_frame={6} blend={7:F3}",
                c.id, c.k, c.frame, c.T, c.s, c.simT, player.ShownSimFrame, ViewBlend));
            if (firedThisFrame != null) firedThisFrame.Append(firedThisFrame.Length > 0 ? "|" : "").Append(c.id);
            try { CueFired?.Invoke(c); } catch (Exception e) { Debug.LogException(e); }
            try { onCue?.Invoke(c.id); } catch (Exception e) { Debug.LogException(e); }
        }

        // 手掛かりの音を音の処理の時計で予約する（フレームの刻みより細かく合う）。画面外の描画では鳴らさない
        void ScheduleSounds(double t)
        {
            if (fixedStepFps > 0f) return;
            while (schedPtr < sched.Count && sched[schedPtr].T - t <= scheduleAheadSeconds)
            {
                var e = sched[schedPtr++];
                if (e.state != 0) continue;
                var cs = sounds[e.sound];
                if (cs == null || cs.source == null || t - e.T > 0.25) { e.state = 2; continue; }   // 0.25 s より遅れた音は鳴らさない（再開の直後など）
                if (cs.clip != null) cs.source.clip = cs.clip;
                cs.source.volume = cs.volume;
                cs.source.loop = cs.loop;
                cs.source.PlayScheduled(AudioSettings.dspTime + Math.Max(0.0, e.T - t));
                e.state = 1;
            }
        }

        // ---------------------------------------------------------------- 止め・始め直し・終わり
        public void Pause()
        {
            if (State != Phase.Running) return;
            State = Phase.Paused;
            pausedAt = Now();
            // 予約したがまだ鳴っていない音は取り消し、再開の後にもう一度予約する
            for (int i = 0; i < sched.Count; i++)
            {
                var e = sched[i];
                if (e.state != 1 || e.T <= T) continue;
                var src = sounds[e.sound].source;
                if (src != null) src.Stop();
                e.state = 0;
                if (i < schedPtr) schedPtr = i;
            }
            pausedSources.Clear();
            foreach (var cs in sounds) if (cs != null && cs.source != null && cs.source.isPlaying && !pausedSources.Contains(cs.source)) { cs.source.Pause(); pausedSources.Add(cs.source); }
            Debug.Log(string.Format(CI, "F3DEXP_PAUSE T={0:F3}", T));
        }

        public void Resume()
        {
            if (State != Phase.Paused) return;
            t0 += Now() - pausedAt;
            State = Phase.Running;
            foreach (var s in pausedSources) if (s != null) s.UnPause();
            pausedSources.Clear();
            Debug.Log(string.Format(CI, "F3DEXP_RESUME T={0:F3}", T));
        }

        // 黒い幕を下ろしてから T = 0 に戻す（体験の始め直し。座席 → 原画の視点の動きには幕を使わない）
        public void Restart()
        {
            if (restartPending || State == Phase.Loading || State == Phase.Failed) return;
            restartPending = true;
            fadeTarget = 1f;
            if (fadeSeconds <= 0f) DoRestart();
        }

        void DoRestart()
        {
            restartPending = false;
            foreach (var cs in sounds) if (cs != null && cs.source != null) cs.source.Stop();
            pausedSources.Clear();
            StopAllCoroutines();
            State = Phase.Waiting;
            Ended = false; T = 0; stepIndex = 0; cuePtr = 0; schedPtr = 0;
            foreach (var e in sched) e.state = 0;
            ApplyAt(0.0);
            if (rig != null) rig.ResetMotion();
            waitSince = Now();
            fadeTarget = 0f;
            Fire(new Cue { id = "restart", T = 0, s = 0, k = 0, frame = -1, simT = SimTime(0) });
        }

        void Quit(string cause)
        {
            CloseCapture();
            Debug.Log(string.Format(CI, "F3DEXP_QUIT cause={0} T={1:F3} cues_fired={2} frames={3}", cause, T, CuesFired, capFrame));
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit(0);
#endif
        }

        void HandleKeys()
        {
#if ENABLE_INPUT_SYSTEM
            var kb = UnityEngine.InputSystem.Keyboard.current;
            var gp = UnityEngine.InputSystem.Gamepad.current;
            bool startKey = (kb != null && (kb.spaceKey.wasPressedThisFrame || kb.enterKey.wasPressedThisFrame || kb.numpadEnterKey.wasPressedThisFrame)) ||
                            (gp != null && gp.buttonSouth.wasPressedThisFrame);
            bool pauseKey = (kb != null && kb.pKey.wasPressedThisFrame) || (gp != null && gp.startButton.wasPressedThisFrame);
            if (startKey && State == Phase.Waiting && !restartPending) Begin();
            else if (pauseKey) { if (State == Phase.Running) Pause(); else if (State == Phase.Paused) Resume(); }
            if (kb != null && kb.rKey.wasPressedThisFrame) Restart();
            if (kb != null && kb.qKey.wasPressedThisFrame && (State == Phase.Paused || Ended)) Quit("q");
#endif
        }

        // ---------------------------------------------------------------- 画面外の描画（連番と frames.csv）
        void OpenCapture()
        {
            Directory.CreateDirectory(captureDir);
            csv = new StreamWriter(Path.Combine(captureDir, "frames.csv"), false, new UTF8Encoding(false));
            csv.WriteLine("frame,T,s,frozen,blend,record,sim_frame,sim_t,heave_raw,heave_shown,vignette,cues");
            File.WriteAllText(Path.Combine(captureDir, "plan.txt"), PlanText + "\n", new UTF8Encoding(false));
            firedThisFrame = new StringBuilder();
            capFrame = 0;
        }

        void CloseCapture()
        {
            if (csv == null) return;
            csv.Flush();
            csv.Dispose();
            csv = null;
        }

        IEnumerator CaptureLoop()
        {
            var eof = new WaitForEndOfFrame();
            while (csv != null)
            {
                yield return eof;                                   // FLIP3DXR の LateUpdate（カメラ）と描画の後
                if (csv == null) yield break;
                if (State != Phase.Running) continue;
                var tex = ScreenCapture.CaptureScreenshotAsTexture();
                File.WriteAllBytes(Path.Combine(captureDir, string.Format(CI, "f_{0:D5}.jpg", capFrame)), tex.EncodeToJPG(95));
                Destroy(tex);
                csv.WriteLine(string.Format(CI, "{0},{1:F5},{2:F5},{3},{4:F5},{5},{6},{7:F5},{8:F4},{9:F4},{10:F4},{11}",
                    capFrame, T, S, Frozen ? 1 : 0, ViewBlend, player.ShownRecord, player.ShownSimFrame, player.ShownSimTime,
                    rig != null ? rig.HeaveRaw : float.NaN, rig != null ? rig.HeaveShown : float.NaN, rig != null ? rig.VignetteAmount : 0f, firedThisFrame));
                firedThisFrame.Length = 0;
                capFrame++;
            }
        }

        // ---------------------------------------------------------------- 引数の音（WAV）
        void LoadSoundArgs()
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++)
            {
                if (a[i] != "-f3dexpsound") continue;
                foreach (var item0 in a[i + 1].Split(';'))
                {
                    string item = item0.Trim();
                    int eq = item.IndexOf('=');
                    if (eq <= 0) continue;
                    string cue = item.Substring(0, eq).Trim(), rest = item.Substring(eq + 1).Trim();
                    int wi = rest.LastIndexOf(".wav", StringComparison.OrdinalIgnoreCase);
                    string path = wi >= 0 ? rest.Substring(0, wi + 4) : rest, mods = wi >= 0 ? rest.Substring(wi + 4) : "";
                    float off = 0f, vol = 1f; bool loop = false;
                    foreach (var m in SplitMods(mods))
                    {
                        if (m[0] == '@') float.TryParse(m.Substring(1), NumberStyles.Float, CI, out off);
                        else if (m[0] == '*') float.TryParse(m.Substring(1), NumberStyles.Float, CI, out vol);
                        else if (m == "!loop") loop = true;
                    }
                    try
                    {
                        var clip = LoadWav(path);
                        var go = new GameObject("F3DEXP_Sound_" + cue);
                        go.transform.SetParent(transform, false);
                        var src = go.AddComponent<AudioSource>();
                        src.playOnAwake = false; src.spatialBlend = 0f; src.clip = clip;
                        sounds.Add(new CueSound { cue = cue, source = src, clip = clip, offsetSeconds = off, volume = Mathf.Clamp01(vol), loop = loop });
                        Debug.Log(string.Format(CI, "F3DEXP_SOUND cue={0} file={1} s={2:F2} offset={3:F2} vol={4:F2} loop={5}", cue, path, clip.length, off, vol, loop));
                    }
                    catch (Exception e) { Debug.LogWarning("F3DEXP_SOUND 読めない：" + path + " " + e.Message); }
                }
            }
        }

        static IEnumerable<string> SplitMods(string mods)
        {
            int i = 0;
            while (i < mods.Length)
            {
                int j = i + 1;
                while (j < mods.Length && mods[j] != '@' && mods[j] != '*' && mods[j] != '!') j++;
                var t = mods.Substring(i, j - i).Trim();
                if (t.Length > 0) yield return t;
                i = j;
            }
        }

        // RIFF WAV（PCM 16 bit・IEEE float 32 bit。DS49 の音は 48 kHz・1 ch・16 bit）を AudioClip にする
        public static AudioClip LoadWav(string path)
        {
            byte[] b = File.ReadAllBytes(path);
            if (b.Length < 44 || Encoding.ASCII.GetString(b, 0, 4) != "RIFF" || Encoding.ASCII.GetString(b, 8, 4) != "WAVE") throw new InvalidDataException("RIFF WAVE でない");
            int pos = 12, fmt = 0, ch = 0, rate = 0, bits = 0, dataOff = -1, dataLen = 0;
            while (pos + 8 <= b.Length)
            {
                string id = Encoding.ASCII.GetString(b, pos, 4);
                int len = BitConverter.ToInt32(b, pos + 4), body = pos + 8;
                if (id == "fmt " && len >= 16) { fmt = BitConverter.ToUInt16(b, body); ch = BitConverter.ToUInt16(b, body + 2); rate = BitConverter.ToInt32(b, body + 4); bits = BitConverter.ToUInt16(b, body + 14); }
                else if (id == "data") { dataOff = body; dataLen = Math.Max(0, Math.Min(len, b.Length - body)); break; }
                if (len < 0) break;
                pos = body + len + (len & 1);
            }
            if (dataOff < 0 || ch < 1 || rate < 1) throw new InvalidDataException("fmt・data がない");
            if (fmt == 0xFFFE) fmt = bits == 32 ? 3 : 1;           // WAVE_FORMAT_EXTENSIBLE（中身はほぼ PCM か float）
            float[] s;
            if (fmt == 1 && bits == 16)
            {
                s = new float[dataLen / 2];
                for (int i = 0; i < s.Length; i++) s[i] = BitConverter.ToInt16(b, dataOff + 2 * i) / 32768f;
            }
            else if (fmt == 3 && bits == 32)
            {
                s = new float[dataLen / 4];
                Buffer.BlockCopy(b, dataOff, s, 0, s.Length * 4);
            }
            else throw new InvalidDataException("対応していない形 fmt=" + fmt + " bits=" + bits);
            int frames = s.Length / ch;
            if (frames < 1) throw new InvalidDataException("音が空");
            var clip = AudioClip.Create(Path.GetFileNameWithoutExtension(path), frames, ch, rate, false);
            clip.SetData(s, 0);
            return clip;
        }
    }
}
