using System;
using System.Collections.Generic;
using GreatWave.Design30;
using GreatWave.Design42;
using UnityEngine;

namespace GreatWave.Design43
{
    // 設計43：船用水面データ。船（DS42Buoyancy）は、設計30 のうねり（near・far のシート。設計30 の海の式を表示と同じ標本で持つもの）と、
    // 主役波のシートの本体の下側の一価の面を、表示と同じ時計（DS30SinglePlayback の τ。シートへ渡したのと同じ値）で読む。
    //   ・時計：自分では時刻を持たない。問い合わせのたびに playback.Tau を見て、変わっていればシートの頂点と索引を作り直す（時刻のずれ 0）。
    //   ・高さ：点 (x, z) の鉛直の線と、描いているシート（主役波の本体の列・near・far のすその外）の交わりのうち、最も低いもの（下側の一価の面）。
    //     交わりが 1 つなら一価（砕けていない所）、2 つ以上なら巻き込み・唇の下（砕波域。下の面を読む）。
    //   ・範囲の外（索引の外、交わりなし）は予備として y = 0（t* の静めた海）を返し、回数を数える（関心の範囲を船のまわりに取るので、試験では 0 のはず）。
    //   ・設計30 の海の式そのもの（sea_function、far の半径方向の弱めを設計43 で書き足した版）は、表示の far の粗い網と最大 17 cm 違う
    //     （Tools/GWWaveGen/ds43 の前の確かめ）ので、船は式ではなく表示と同じ標本を読む（Q24 の判断。Docs/Progress/Design_43_ja.md）。
    // PC の batchmode で確かめた（HMD 実機ではない）。
    [DefaultExecutionOrder(60)]
    public class DS43BoatWater : DS42Water
    {
        public DS30SinglePlayback playback;
        [Tooltip("関心の範囲（世界の xz。x = xMin、y = zMin）。船のまわりだけ索引を作る")]
        public Rect region = new Rect(-40f, -50f, 80f, 60f);
        public float cellSize = 1.0f;
        [Tooltip("交わりをまとめる幅（m）。三角形の辺の上で 2 つの三角形が同じ高さを返すのを 1 つに数える")]
        public float mergeTolerance = 1e-3f;

        public readonly List<DS43SheetReader> readers = new List<DS43SheetReader>();
        public double TauUsed { get; private set; } = double.NaN;
        public int Rebuilds { get; private set; }
        public long FallbackCount { get; private set; }
        public long QueryCount { get; private set; }
        public double RebuildMsTotal { get; private set; }
        readonly List<float> hits = new List<float>(16);

        /// <summary>シートの再生器と同じパッケージ・同じ描く列の範囲から読み手を作る。</summary>
        public void Init(IEnumerable<DS30SheetPlayer> sheets)
        {
            readers.Clear();
            foreach (var s in sheets)
            {
                if (s == null) continue;
                bool far = s.sheetName == "far";
                readers.Add(new DS43SheetReader(s.sheetName, s.packageDir, s.colMin, s.colMax, far));
            }
            TauUsed = double.NaN;
        }

        public void Sync()
        {
            if (playback == null) return;
            double tau = playback.Tau;
            if (double.IsNaN(tau) || tau == TauUsed) return;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            foreach (var r in readers) r.Build(tau, region, cellSize);
            TauUsed = tau; Rebuilds++;
            RebuildMsTotal += sw.Elapsed.TotalMilliseconds;
        }

        /// <summary>点の鉛直の線の交わりの高さ（昇順、近いものはまとめる）。</summary>
        public int Hits(Vector3 p, List<float> outHits)
        {
            Sync();
            outHits.Clear();
            foreach (var r in readers) r.Query(p.x, p.z, outHits);
            outHits.Sort();
            int k = 0;
            for (int i = 0; i < outHits.Count; i++)
                if (k == 0 || outHits[i] - outHits[k - 1] > mergeTolerance) outHits[k++] = outHits[i];
            if (k < outHits.Count) outHits.RemoveRange(k, outHits.Count - k);
            return k;
        }

        public override float HeightAt(Vector3 worldPos)
        {
            QueryCount++;
            int k = Hits(worldPos, hits);
            if (k == 0) { FallbackCount++; return 0f; }
            return hits[0];
        }
    }
}
