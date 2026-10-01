using System;
using GreatWave.ArtFirst;
using GreatWave.Design34;
using GreatWave.Design38;
using UnityEngine;

namespace GreatWave.Polish32
{
    // 仕上げ32 修正の回 1：爪の層の毎コマの差し替えを、時刻が変わった時だけにする（審査の指摘：プレイヤーの描くコマが 17.6% 減り、
    // 導入・接近・余韻（爪が見えない・止まっている時）でも CPU の主スレッドが 0.30〜0.37 ms 増えた）。
    //  ・設計34 の DS34ClawPlayer（Update で毎コマ全部の頂点を入れ直す）と設計38 の DS38ClawOutline（LateUpdate で毎コマ頂点を写し法線を作り直す）の
    //    Play モードの自動の差し替えを止め、ここで、爪の時刻のコマの位置（t × 30 Hz）が前と同じなら何もしない。
    //    前のコマも今のコマも全部の爪が見えない（根元の点に潰してある）なら、やはり何もしない（形は同じ：面積 0）。
    //  ・体験の時計（設計46 の DS46ClockBus）があれば、その "claws" の段を同じ名前で登録し直す（GWClock.Register は同じ名前を置き換える）。
    //    無ければ（単独の再生の場面）、Update で GWClock の秒を読む（DS34ClawPlayer と同じ）。
    // 見え方は変えない（同じ時刻なら同じ頂点）。DS34ClawPlayer・DS38ClawOutline・DS46ClockBus のファイルは変えない。
    [DefaultExecutionOrder(61)]
    public class PL32ClawDriver : MonoBehaviour
    {
        public DS34ClawPlayer claws;
        public DS38ClawOutline outline;
        public GWClock clock;

        public int Applies { get; private set; }
        public int Skips { get; private set; }
        public bool OnBus { get; private set; }
        bool[] anyVisible;
        double lastX = double.NaN;
        bool dirty;

        void Start()
        {
            if (!Application.isPlaying) return;
            if (claws == null) claws = GetComponent<DS34ClawPlayer>();
            if (outline == null) outline = GetComponent<DS38ClawOutline>();
            if (claws == null) { enabled = false; return; }
            claws.followClockInPlayMode = false;
            if (outline != null) outline.syncInPlayMode = false;
            claws.Load();
            anyVisible = new bool[claws.Frames];
            for (int k = 0; k < claws.Frames; k++)
                for (int i = 0; i < claws.ClawCount && !anyVisible[k]; i++)
                {
                    int o = claws.VertOffset[i];
                    if ((claws.FrameVertex(k, o + 1) - claws.FrameVertex(k, o)).sqrMagnitude > 1e-12f) anyVisible[k] = true;
                }
            var bus = FindObjectOfType<GreatWave.Design46.DS46ClockBus>();
            if (bus != null && bus.claws == claws && bus.clock != null)
            {
                bus.clock.Register("claws", GreatWave.Design46.DS46ClockBus.OrderClaws, (c, st) => Step(st.wave, true));
                OnBus = true;
            }
            Debug.Log("PL32_CLAW_DRIVER onBus=" + OnBus + " frames=" + claws.Frames);
        }

        void Step(double t, bool syncNow)
        {
            double x = Math.Max(0.0, Math.Min(t * claws.Hz, claws.Frames - 1));
            if (!double.IsNaN(lastX))
            {
                if (Math.Abs(x - lastX) < 1e-7) { Skips++; return; }
                bool prevHidden = !anyVisible[(int)Math.Floor(lastX)] && !anyVisible[(int)Math.Ceiling(lastX)];
                bool nowHidden = !anyVisible[(int)Math.Floor(x)] && !anyVisible[(int)Math.Ceiling(x)];
                if (prevHidden && nowHidden) { lastX = x; Skips++; return; }
            }
            claws.ApplyT(t);
            lastX = x;
            Applies++;
            if (syncNow) { if (outline != null) outline.Sync(); }
            else dirty = true;
        }

        void Update()
        {
            if (!Application.isPlaying || OnBus || claws == null || !claws.Loaded) return;
            var c = clock != null ? clock : GWClock.Active;
            if (c != null) Step(c.Seconds, false);
        }

        void LateUpdate()
        {
            if (!Application.isPlaying || !dirty) return;
            dirty = false;
            if (outline != null) outline.Sync();
        }
    }
}
