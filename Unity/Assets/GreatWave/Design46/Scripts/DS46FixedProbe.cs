using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design43;
using UnityEngine;

namespace GreatWave.Design46
{
    // 設計46：Play モードで、物理の段（FixedUpdate）が読む水の時刻を記録する検査の部品（船の浮力 DS42Buoyancy と同じ場所で読む）。
    // FixedUpdate のたびに、船用水面データを同期させ（DS43BoatWater.Sync：浮力が HeightAt で行うのと同じ）、使った τ・時計の体験の時刻・コマの番号を残す。
    // 同じコマで描かれる水の τ（再生器の Tau）と比べれば、物理が何コマ前の水を読むかが分かる（段階8確認 F8-3）。
    // 検査の場面の写し（DS46PlayModeCheck）でだけ一時に足す。作品の場面には保存しない。
    [DefaultExecutionOrder(80)]
    public class DS46FixedProbe : MonoBehaviour
    {
        public GWClock clock;
        public DS30SinglePlayback playback;
        public DS43BoatWater boatWater;
        public Vector3 samplePoint = new Vector3(-4.0f, 0f, -20.0f);

        public int LastFixedFrame { get; private set; } = -1;
        public double LastFixedTau { get; private set; } = double.NaN;
        public double LastFixedClock { get; private set; } = double.NaN;
        public float LastFixedHeight { get; private set; } = float.NaN;
        public int FixedCount { get; private set; }
        public int FixedThisFrame { get; private set; }
        int countedFrame = -1;

        void FixedUpdate()
        {
            if (boatWater == null) return;
            LastFixedHeight = boatWater.HeightAt(samplePoint);   // 浮力と同じ読み方（中で Sync する）
            LastFixedTau = boatWater.TauUsed;
            LastFixedClock = clock != null ? clock.ExperienceSeconds : double.NaN;
            if (Time.frameCount != countedFrame) { countedFrame = Time.frameCount; FixedThisFrame = 0; }
            FixedThisFrame++;
            LastFixedFrame = Time.frameCount;
            FixedCount++;
        }
    }
}
