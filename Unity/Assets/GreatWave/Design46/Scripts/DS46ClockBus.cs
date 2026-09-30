using System.Collections.Generic;
using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design31;
using GreatWave.Design34;
using GreatWave.Design38;
using GreatWave.Design43;
using UnityEngine;

namespace GreatWave.Design46
{
    // 設計46：共通時計（GWClock、Master）に、場面の時刻で動くものを段として順に登録する。どの段も時刻の純粋な関数で形を決める。
    //   10 water      ：再生器 DS30SinglePlayback.Seek(大波の時刻)。τ(t) で主役波・周りの海・継ぎ目の幕・座席の船の支え・仮置きを同じ τ にする。
    //                   再生器は自分では進めない（場面で enabled = false、clock = null。時計の持ち主は GWClock だけ）。
    //   20 boat_water ：船用水面データ DS43BoatWater.Sync()（再生器がシートへ渡したのと同じ τ でシートの索引を作り直す）。
    //   30 white      ：白の帯と藍の色面（主役波のシートの色。DS27 NPR White が τ と T_white で塗る）。DS34LayerSet.ApplyToggles で τ を材質へ渡す。
    //   40 claws      ：爪 DS34ClawPlayer.ApplyT(大波の時刻)、爪の縁の線 DS38ClawOutline.Sync。
    //   50 spray      ：飛沫 DS31InstancedParticles.ApplyT(大波の時刻)（飛沫 v0 と設計39 の密な飛沫）。
    //   90 events     ：演出の出来事 DS46EventTrack（体験の時刻）。
    // Play モードでは Start で読み込み、時計を初期化して再生を始める（autoPlay）。以後は GWClock が EarlyUpdate で進め、この順に呼ぶ。
    // Editor の採取は Prepare() の後に clock.Initialise / Seek / Advance を直接呼ぶ（Play と同じ道）。
    [DefaultExecutionOrder(-90)]
    public class DS46ClockBus : MonoBehaviour
    {
        public GWClock clock;
        public DS30SinglePlayback playback;
        public DS34LayerSet layers;
        public DS34ClawPlayer claws;
        public DS38ClawOutline clawLine;
        public List<DS31InstancedParticles> sprays = new List<DS31InstancedParticles>();
        public DS43BoatWater boatWater;
        public DS46EventTrack events;
        [Tooltip("Play モードで読み込みの後すぐに再生を始める（負の遅れは設計47 の導入がつなぐ）")]
        public bool autoPlay = true;

        public bool Ready { get; private set; }

        public const int OrderWater = 10, OrderBoatWater = 20, OrderWhite = 30, OrderClaws = 40, OrderSpray = 50, OrderEvents = 90;

        /// <summary>読み込み（シート・爪・飛沫・船用水面データ・出来事の表）と段の登録。何度呼んでもよい。</summary>
        public void Prepare()
        {
            if (Ready) return;
            if (clock == null) clock = GetComponentInParent<GWClock>() ?? GWClock.Active;
            clock.mode = GWClock.ClockMode.Master;
            if (playback != null)
            {
                playback.clock = null;          // 再生器は時計へ書かない（時計の持ち主は GWClock だけ）
                playback.autoStartDelay = -1f;  // 自分では始めない（enabled = false でも念のため）
                playback.Prepare();
            }
            if (claws != null) { claws.followClockInPlayMode = false; claws.Load(); }
            foreach (var s in sprays) if (s != null) { s.followClockInPlayMode = false; s.Load(); }
            if (boatWater != null && playback != null) { boatWater.playback = playback; boatWater.Init(playback.sheets); }
            if (events != null) events.Load();

            clock.Register("water", OrderWater, (c, st) => { if (playback != null) playback.Seek(st.wave); });
            clock.Register("boat_water", OrderBoatWater, (c, st) => { if (boatWater != null) boatWater.Sync(); });
            clock.Register("white", OrderWhite, (c, st) => { if (layers != null) layers.ApplyToggles(); });
            clock.Register("claws", OrderClaws, (c, st) =>
            {
                if (claws != null) claws.ApplyT(st.wave);
                if (clawLine != null) clawLine.Sync();
            });
            clock.Register("spray", OrderSpray, (c, st) => { foreach (var s in sprays) if (s != null) s.ApplyT(st.wave); });
            clock.Register("events", OrderEvents, (c, st) => { if (events != null) events.OnClock(c, st); });
            Ready = true;
        }

        void Start()
        {
            if (!Application.isPlaying) return;
            Prepare();
            clock.Initialise(autoPlay);
        }
    }
}
