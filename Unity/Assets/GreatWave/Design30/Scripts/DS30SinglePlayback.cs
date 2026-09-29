using System;
using System.Collections.Generic;
using GreatWave.ArtFirst;
using GreatWave.Design27;
using UnityEngine;

namespace GreatWave.Design30
{
    // 設計30：導入からの単発再生。1 つの時刻 t（GWClock）から世界全体の時間曲線 τ(t)（D31、DS27TimeWarp）で物理の時刻 τ を決め、
    // 場面のすべての DS27 形式のシート（主役波と周りの海。同じ knot_tau）へ同じ τ を渡す。
    // 状態：待機（導入の前。t = 0 のコマのまま止める）→ 再生（t を進める）→ 静止（t* で止め、最後のコマ τ = 0 を保つ）。折り返さない。
    //   ・開始で形が跳ばない：待機の間も t = 0 のコマ（τ(0)）を描くので、再生の最初のコマは待機のコマと同じ。
    //   ・終了で形が跳ばない：t ≥ t* では t = t* に留め、τ(t*) = 0（最後の層そのもの）を描き続ける。
    //   ・1 コマの時間の進みは maxStepSeconds で頭打ちにする（読み込みの引っかかりで時刻が飛ばないように。遅れはそのまま遅れになる）。
    // Play モードでは Update が Tick(Time.deltaTime) を呼ぶ。Editor の採取（DS30Render）は同じ Tick を 1/30 s で呼ぶので、動画と同じ経路を通る。
    // 時計（GWClock）は自分では進めない（playInPlayMode を切る）。この再生器が時刻を書き、ほかの時刻の読み手（白・爪など）は時計を読む。
    [DefaultExecutionOrder(50)]
    public class DS30SinglePlayback : MonoBehaviour
    {
        public enum State { Waiting, Playing, Holding }

        public GWClock clock;
        [Tooltip("τ(t) の表（Unity プロジェクトからの相対パスか絶対パス）。既定は設計28修正01 の F_final の時間曲線")]
        public string timewarpPath = "Build/Design/28R01F/F_final/timewarp_F_final.json";
        public List<DS30SheetPlayer> sheets = new List<DS30SheetPlayer>();
        [Tooltip("遠い海の足跡を抜いた平らな海（同じ τ で内側の縁を動かす）")]
        public List<DS30FlatSeaRing> rings = new List<DS30FlatSeaRing>();
        [Tooltip("near と far の T 字の継ぎ目の下の幕（同じ τ で動かす）")]
        public List<DS30SeamCurtain> curtains = new List<DS30SeamCurtain>();
        [Tooltip("座席の船の鉛直の支え（同じ t・τ で上下させる）")]
        public List<DS30BoatHeave> heaves = new List<DS30BoatHeave>();
        [Tooltip("シートの頂点に付けて動かす仮置き（手前の小波の泡の線など）")]
        public List<DS30AttachToVertex> attachments = new List<DS30AttachToVertex>();
        [Tooltip("原画の瞬間 t*（秒）。ここで止める")]
        public float tStarSeconds = 12f;
        [Tooltip("Play モードで、読み込みの後この秒数だけ待機（t = 0 のコマで止める）してから自動で始める。既定 0 は読み込みの直後に始める（止まった海を見せない）。負なら自動で始めない（Begin() を呼ぶ。設計47 の導入がつなぐ）")]
        public float autoStartDelay = 0f;
        [Tooltip("1 コマで進める時間の上限（秒）")]
        public float maxStepSeconds = 1f / 15f;

        public State CurrentState { get; private set; } = State.Waiting;
        public double T { get; private set; }
        public double Tau { get; private set; } = double.NaN;
        public int TickCount { get; private set; }
        public DS27TimeWarp Warp => warp;

        DS27TimeWarp warp;
        double waited;
        bool ready;

        /// <summary>時間曲線とすべてのシートを読み込み、待機の状態（t = 0 のコマ）にする。</summary>
        public void Prepare()
        {
            if (warp == null) warp = DS27TimeWarp.Load(timewarpPath);
            foreach (var s in sheets) if (s != null) s.EnsureLoaded();
            foreach (var r in rings) if (r != null) r.Load();
            foreach (var r in curtains) if (r != null) r.Load();
            foreach (var h in heaves) if (h != null) h.Load();
            foreach (var at in attachments) if (at != null) at.Load();
            if (clock != null) { clock.playInPlayMode = false; clock.loopSeconds = 0f; }
            CurrentState = State.Waiting;
            T = 0.0; waited = 0.0; TickCount = 0;
            ready = true;
            Apply();
        }

        /// <summary>再生を始める（待機の状態からだけ）。</summary>
        public void Begin()
        {
            if (!ready) Prepare();
            if (CurrentState == State.Waiting) { CurrentState = State.Playing; T = 0.0; }
        }

        /// <summary>1 コマ進める。dt は実時間の秒。</summary>
        public void Tick(double dt)
        {
            if (!ready) Prepare();
            dt = Math.Max(0.0, Math.Min(dt, maxStepSeconds));
            switch (CurrentState)
            {
                case State.Waiting:
                    waited += dt;
                    if (Application.isPlaying && autoStartDelay >= 0f && waited >= autoStartDelay) CurrentState = State.Playing;
                    break;
                case State.Playing:
                    T += dt;
                    if (T >= tStarSeconds - 1e-9) { T = tStarSeconds; CurrentState = State.Holding; }
                    break;
                case State.Holding:
                    T = tStarSeconds;
                    break;
            }
            TickCount++;
            Apply();
        }

        /// <summary>採取用：状態を直接決める（t は再生の時刻。t ≥ t* は静止）。</summary>
        public void Seek(double t)
        {
            if (!ready) Prepare();
            if (t <= 0.0) { T = 0.0; CurrentState = t < 0.0 ? State.Waiting : State.Playing; }
            else if (t >= tStarSeconds) { T = tStarSeconds; CurrentState = State.Holding; }
            else { T = t; CurrentState = State.Playing; }
            Apply();
        }

        void Apply()
        {
            Tau = warp.TauAt(T);
            if (clock != null) clock.SetSeconds((float)T);
            foreach (var s in sheets) if (s != null) s.ApplyTau(Tau);
            foreach (var r in rings) if (r != null) r.ApplyTau(Tau);
            foreach (var r in curtains) if (r != null) r.ApplyTau(Tau);
            foreach (var h in heaves) if (h != null) h.Apply(T, Tau);
            foreach (var at in attachments) if (at != null) at.ApplyTau(Tau);
        }

        void Start()
        {
            if (Application.isPlaying) Prepare();
        }

        void Update()
        {
            if (!Application.isPlaying || !ready) return;
            Tick(Time.deltaTime);
        }
    }
}
