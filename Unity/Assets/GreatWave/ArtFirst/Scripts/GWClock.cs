using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.LowLevel;
using UnityEngine.PlayerLoop;

namespace GreatWave.ArtFirst
{
    // GWClock（作業計画 4.0・番号30）：体験の時刻（秒）を一か所で持つ時計。形成の keypose（AF30KeyposeWave）など、
    // 時刻で動くものはこの時計を読む（番号31 の白、番号35 の爪、番号37 の飛沫も同じ時計へつなぐ予定。番号38 で一括の駆動を確かめる）。
    // 時間軸（番号23 で凍結）：予備 0〜2 s、形成 2〜12 s、静止 12〜17 s、t* = 12.0 s。
    // 再生中（Play）は Time.deltaTime × speed で進め、loopSeconds で折り返す。Editor の採取（AF30Formation）は SetSeconds で時刻を直接決める。
    //
    // 設計46（共通時計）で広げた。mode = Master のときだけ新しい動きになり、既定の Legacy は上の番号30 の動きのまま変えない。
    //   ・時計が体験の時刻（double、ExperienceSeconds）の唯一の持ち主になる。停止（Stop）・再開（Resume）・初期化（Initialise）・
    //     途中からの再生（Seek）を持ち、時刻が決まるたびに、登録された段（Register）を順番（order の小さい順、同じなら登録順）に同じ時刻で呼ぶ。
    //     段は時刻の純粋な関数として形を決める（積分の状態を持たない）ので、同じ時刻なら、どの道を通っても同じ形になる。
    //   ・大波の時刻 WaveSeconds = clamp(体験の時刻 − waveStartSeconds, 0, tStarSeconds)。t* の後は t* の姿のまま（Q11：崩壊は作らない）。
    //     古い読み手（seconds・Seconds。爪・飛沫・AF30 などが「形成の時刻」として読む float）には WaveSeconds を写す。
    //   ・Play モードでは、プレイヤーのループの EarlyUpdate（FixedUpdate より前）で時刻を 1 回進める（advanceBeforePhysics）。
    //     そのコマの物理（船の浮力の FixedUpdate）と描画が同じ時刻の水を読む（段階8確認 F8-3 の「1 コマ前の水」をなくす）。
    //   ・1 コマの進みは maxStepSeconds で頭打ちにする（設計30 と同じ。読み込みの引っかかりで時刻が飛ばない）。endSeconds で止まる。
    //   ・止めている間は段を呼ばない（形は止めた時刻のまま）。
    // PC の Editor（batchmode）で確かめた。HMD 実機ではない。
    [DefaultExecutionOrder(-100)]
    public class GWClock : MonoBehaviour
    {
        public enum ClockMode { Legacy, Master }
        public enum RunState { Stopped, Running }
        public enum StepKind { Initialise, Advance, Seek }

        /// <summary>段へ渡す 1 回の時刻の決定。</summary>
        public struct Step
        {
            public StepKind kind;
            public long index;              // 時刻を決めた回数（初期化・進める・Seek のたびに 1 増える）
            public double experience;       // 体験の時刻（秒）
            public double previous;         // 前の体験の時刻（初期化・Seek では跳ぶ前の値）
            public double wave;             // 大波の時刻（0〜t*）
            public double dt;               // 進めた秒（Seek・初期化では 0）
            public bool Jumped => kind != StepKind.Advance;
        }

        public static GWClock Active { get; private set; }

        [Tooltip("いまの時刻（秒）。Master では大波の時刻（WaveSeconds）の写し")]
        public float seconds;
        [Tooltip("再生中に時刻を進める（Legacy のみ）")]
        public bool playInPlayMode = true;
        [Tooltip("折り返す長さ（秒）。0 以下で折り返さない（Legacy のみ）")]
        public float loopSeconds = 17f;
        [Tooltip("時刻の進む速さ（1 で実時間）")]
        public float speed = 1f;
        [Tooltip("原画対応の時刻 t*（秒。大波の時刻で）")]
        public float tStarSeconds = 12f;

        [Header("設計46：共通時計（Master）")]
        [Tooltip("Legacy：番号30 の動きのまま。Master：体験の時刻を持ち、段を順に駆動する")]
        public ClockMode mode = ClockMode.Legacy;
        [Tooltip("初期化の時刻（体験の秒）")]
        public double startSeconds = 0.0;
        [Tooltip("終わりの時刻（体験の秒）。ここで止まる。startSeconds 以下なら止まらない")]
        public double endSeconds = 14.0;
        [Tooltip("大波の時刻 0（設計30 の t = 0）の体験の時刻")]
        public double waveStartSeconds = 0.0;
        [Tooltip("1 コマで進める時間の上限（秒）")]
        public double maxStepSeconds = 1.0 / 15.0;
        [Tooltip("Play モードで、プレイヤーのループの EarlyUpdate（FixedUpdate より前）で時刻を進める")]
        public bool advanceBeforePhysics = true;

        public float Seconds => seconds;
        public RunState State { get; private set; } = RunState.Stopped;
        public double ExperienceSeconds { get; private set; }
        public double WaveSeconds => WaveOf(ExperienceSeconds);
        public bool Ended => endSeconds > startSeconds && ExperienceSeconds >= endSeconds;
        public long StepIndex { get; private set; }
        public Step LastStep { get; private set; }
        public int EarlyTicks { get; private set; }

        struct Stage { public string name; public int order; public int seq; public Action<GWClock, Step> fn; }
        readonly List<Stage> stages = new List<Stage>();
        int seq;
        /// <summary>段ごとに、最後に受け取った時刻の決定（番号・体験の時刻・大波の時刻）。同期の検査用。</summary>
        public readonly Dictionary<string, Step> StageLast = new Dictionary<string, Step>();

        public void SetSeconds(float s)
        {
            seconds = s;
        }

        public double WaveOf(double experience)
        {
            double w = experience - waveStartSeconds;
            return w < 0.0 ? 0.0 : (w > tStarSeconds ? tStarSeconds : w);
        }

        /// <summary>段を登録する。order の小さい順に、同じ時刻で呼ぶ（同じ名前は置き換える）。</summary>
        public void Register(string name, int order, Action<GWClock, Step> fn)
        {
            stages.RemoveAll(s => s.name == name);
            stages.Add(new Stage { name = name, order = order, seq = seq++, fn = fn });
            stages.Sort((a, b) => a.order != b.order ? a.order.CompareTo(b.order) : a.seq.CompareTo(b.seq));
        }

        public void Unregister(string name) { stages.RemoveAll(s => s.name == name); StageLast.Remove(name); }

        public List<string> StageNames() { var l = new List<string>(); foreach (var s in stages) l.Add(s.name + "@" + s.order); return l; }

        /// <summary>初期化：startSeconds へ戻し、すべての段を当て直す。止まった状態にする（runAfter で続けて再生）。</summary>
        public void Initialise(bool runAfter = false)
        {
            double prev = ExperienceSeconds;
            ExperienceSeconds = startSeconds;
            State = runAfter ? RunState.Running : RunState.Stopped;
            Broadcast(StepKind.Initialise, prev, 0.0);
        }

        /// <summary>停止：時刻をそのまま保つ。段を呼ばないので形も変わらない。</summary>
        public void Stop() { State = RunState.Stopped; }

        /// <summary>再開：止めた時刻から進める。終わりにいるときは何もしない。</summary>
        public void Resume() { if (!Ended) State = RunState.Running; }

        /// <summary>途中からの再生：体験の時刻を t に決め、すべての段を t で当て直す。停止・再生の状態は変えない。</summary>
        public void Seek(double t)
        {
            double prev = ExperienceSeconds;
            if (endSeconds > startSeconds) t = Math.Min(t, endSeconds);
            ExperienceSeconds = Math.Max(startSeconds, t);
            Broadcast(StepKind.Seek, prev, 0.0);
        }

        /// <summary>再生中なら dt（実時間の秒。maxStepSeconds で頭打ち）× speed だけ進める。止まっていれば何もしない。</summary>
        public void Advance(double dt)
        {
            if (State != RunState.Running) return;
            dt = Math.Max(0.0, Math.Min(dt, maxStepSeconds)) * speed;
            double prev = ExperienceSeconds;
            double t = prev + dt;
            if (endSeconds > startSeconds && t >= endSeconds - 1e-9) { t = endSeconds; State = RunState.Stopped; }
            ExperienceSeconds = t;
            Broadcast(StepKind.Advance, prev, t - prev);
        }

        void Broadcast(StepKind kind, double prev, double dt)
        {
            StepIndex++;
            var st = new Step { kind = kind, index = StepIndex, experience = ExperienceSeconds, previous = prev, wave = WaveSeconds, dt = dt };
            LastStep = st;
            seconds = (float)st.wave;
            var list = stages.ToArray();   // 段の中で登録が変わっても回せるように写しで回す
            foreach (var s in list)
            {
                s.fn(this, st);
                StageLast[s.name] = st;
            }
        }

        void OnEnable()
        {
            Active = this;
            if (mode == ClockMode.Master && Application.isPlaying && advanceBeforePhysics) EarlyLoop.Add(this);
        }

        void OnDisable()
        {
            if (Active == this) Active = null;
            EarlyLoop.Remove(this);
        }

        void EarlyTick()
        {
            if (!Application.isPlaying || !isActiveAndEnabled || mode != ClockMode.Master || !advanceBeforePhysics) return;
            EarlyTicks++;
            Advance(Time.deltaTime);
        }

        void Update()
        {
            if (!Application.isPlaying) return;
            if (mode == ClockMode.Master)
            {
                if (!advanceBeforePhysics) Advance(Time.deltaTime);
                return;
            }
            if (!playInPlayMode) return;
            seconds += Time.deltaTime * speed;
            if (loopSeconds > 0f && seconds >= loopSeconds) seconds -= loopSeconds * Mathf.Floor(seconds / loopSeconds);
        }

        // プレイヤーのループの EarlyUpdate に 1 つの系を差し込み、Master の時計を FixedUpdate より前に進める（設計46）。
        static class EarlyLoop
        {
            struct GWClockEarlyAdvance { }
            static readonly List<GWClock> clocks = new List<GWClock>();
            static bool installed;

            public static void Add(GWClock c)
            {
                if (!clocks.Contains(c)) clocks.Add(c);
                Install();
            }

            public static void Remove(GWClock c)
            {
                clocks.Remove(c);
                if (clocks.Count == 0) Uninstall();
            }

            static void Tick()
            {
                for (int i = 0; i < clocks.Count; i++) if (clocks[i] != null) clocks[i].EarlyTick();
            }

            static void Install()
            {
                if (installed) return;
                var loop = PlayerLoop.GetCurrentPlayerLoop();
                if (!Insert(ref loop)) return;
                PlayerLoop.SetPlayerLoop(loop);
                installed = true;
            }

            static void Uninstall()
            {
                if (!installed) return;
                var loop = PlayerLoop.GetCurrentPlayerLoop();
                RemoveFrom(ref loop);
                PlayerLoop.SetPlayerLoop(loop);
                installed = false;
            }

            static bool Insert(ref PlayerLoopSystem root)
            {
                if (root.subSystemList == null) return false;
                for (int i = 0; i < root.subSystemList.Length; i++)
                {
                    if (root.subSystemList[i].type != typeof(EarlyUpdate)) continue;
                    var sub = root.subSystemList[i];
                    var list = new List<PlayerLoopSystem>(sub.subSystemList ?? new PlayerLoopSystem[0]);
                    list.RemoveAll(s => s.type == typeof(GWClockEarlyAdvance));
                    list.Add(new PlayerLoopSystem { type = typeof(GWClockEarlyAdvance), updateDelegate = Tick });
                    sub.subSystemList = list.ToArray();
                    root.subSystemList[i] = sub;
                    return true;
                }
                return false;
            }

            static void RemoveFrom(ref PlayerLoopSystem root)
            {
                if (root.subSystemList == null) return;
                for (int i = 0; i < root.subSystemList.Length; i++)
                {
                    var sub = root.subSystemList[i];
                    if (sub.subSystemList == null) continue;
                    var list = new List<PlayerLoopSystem>(sub.subSystemList);
                    if (list.RemoveAll(s => s.type == typeof(GWClockEarlyAdvance)) > 0) { sub.subSystemList = list.ToArray(); root.subSystemList[i] = sub; }
                }
            }

            [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
            static void ResetStatics()
            {
                clocks.Clear();
                var loop = PlayerLoop.GetCurrentPlayerLoop();
                RemoveFrom(ref loop);
                PlayerLoop.SetPlayerLoop(loop);
                installed = false;
            }
        }
    }
}
