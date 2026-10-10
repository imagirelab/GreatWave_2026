using System;
using System.Collections.Generic;
using UnityEngine;

namespace GreatWave.RT48
{
    // 断面の元と、描き方・船・時計の境目（計画 §3.7）。今あるのは焼いた元（RecordedSectionSource）だけ。
    // 案 2（同じ断面を GPU で毎フレーム計算する）の元は、同じ形で、CurveBuffer を毎フレーム書き、StateAt で
    // offsetA = offsetB（混ぜない）を返せばよい。描き方（RT48Decode.hlsl）・まわりの海・船・字・時計はこの形だけを使う。
    public struct RT48SectionState
    {
        public double t;          // 計算の時刻（s）
        public int frame;         // 見せるコマ（0 始まり）。補間する時は組の前のコマ
        public int pair;          // 組の番号
        public double alpha;      // 混ぜる割合（補間しない時は 0、最後のコマは 1）
        public double w;          // コマの中の進み (t − t_k) × fps（船の時刻の補間に使う）
        public bool interpolating;
        public bool last;         // 最後のコマ
        public int reason;        // 補間しない理由（0 補間、1 K から先、2 C4 で外れた、3 自分と交わる、4 その他、−1 最後のコマ）
        public int offsetA, offsetB;   // GPU のバッファーの float2 の添字
        public bool afterK, afterContact, afterOnset;
    }

    public struct RT48Loop
    {
        public int kind;          // 0 離れた水、1 囲まれた空気
        public int first, count;  // 点の添字（float2）
    }

    public interface ISectionSource : IDisposable
    {
        string Id { get; }
        string LabelJa { get; }
        string Caption1Ja { get; }
        string Caption3Ja { get; }        // 空なら LabelJa（と、補間が未確認なら「・補間は未確認」）
        bool IsSynthetic { get; }
        bool InterpVerified { get; }
        int PointCount { get; }
        double XOriginM { get; }
        double Fps { get; }
        double TimeFirst { get; }
        double TimeLast { get; }
        double OnsetS { get; }
        double ContactS { get; }
        double KTimeS { get; }            // K のコマの時刻（なければ +∞）
        int FrameNumberFirst { get; }
        double[] TaperStored { get; }     // x の両端の下ろし（保存の座標）
        double SideEndS { get; }
        RT48SectionState StateAt(double t);
        GraphicsBuffer CurveBuffer { get; }   // 曲線の float2（StateAt の offsetA・offsetB で読む）
        void FillCurve(in RT48SectionState s, double[] xy);   // CPU の float64 の生の曲線（StateAt と同じ混ぜ方）
        void FillFrameCurve(int frame, double[] xy);
        int FrameCount { get; }
        void GetLoops(int frame, List<RT48Loop> loops);
        float[] LoopPoints { get; }
        bool TryGetSeatEnd(double seatX, out double endS);
        string Describe();
    }

    public sealed class RecordedSectionSource : ISectionSource
    {
        public const double FrameEps = 1e-9;   // u_bakeio.FRAME_EPS と同じ
        readonly RT48Bake bake;
        GraphicsBuffer buffer;
        readonly double[] taperStored;

        public RecordedSectionSource(RT48Bake bake)
        {
            this.bake = bake;
            taperStored = bake.TaperStored;
        }

        public RT48Bake Bake => bake;
        public string Id => bake.Meta.source_id;
        public string LabelJa => bake.Meta.label_ja;
        public string Caption1Ja => bake.Meta.caption1_ja;
        public string Caption3Ja => bake.Meta.caption3_ja;
        public bool IsSynthetic => bake.Meta.is_synthetic;
        public bool InterpVerified => bake.Meta.interp_verified;
        public int PointCount => bake.N;
        public double XOriginM => bake.Meta.x_origin_m;
        public double Fps => bake.Meta.fps;
        public double TimeFirst => bake.FrameTime(0);
        public double TimeLast => bake.FrameTime(bake.F - 1);
        public double OnsetS => bake.Meta.onset_s;
        public double ContactS => bake.Meta.contact_s;
        public double KTimeS => bake.Meta.k_frame > 0 ? (bake.Meta.k_frame - 1) / bake.Meta.fps : double.PositiveInfinity;
        public int FrameNumberFirst => bake.Meta.frame_first;
        public double[] TaperStored => taperStored;
        public double SideEndS => bake.Meta.side_end_s;
        public int FrameCount => bake.F;
        public float[] LoopPoints => bake.LoopPts;

        public GraphicsBuffer CurveBuffer
        {
            get
            {
                if (buffer == null)
                {
                    buffer = new GraphicsBuffer(GraphicsBuffer.Target.Structured, bake.Pairs.Length / 2, 8) { name = "RT48 曲線 " + Id };
                    buffer.SetData(bake.Pairs);
                }
                return buffer;
            }
        }

        // 時刻 t から見せる組と割合（u_bakeio.state_at と同じ式）。
        public RT48SectionState StateAt(double t)
        {
            var m = bake.Meta;
            double t0 = (m.frame_first - 1) / m.fps;
            double u = (t - t0) * m.fps;
            int k = (int)Math.Floor(u + FrameEps);
            var s = new RT48SectionState { t = t };
            if (k < 0) { s.frame = 0; s.pair = 0; s.alpha = 0; s.w = 0; s.interpolating = false; s.reason = 4; }
            else if (k >= bake.F - 1) { s.frame = bake.F - 1; s.pair = bake.P - 1; s.alpha = 1; s.w = 0; s.last = true; s.reason = -1; }
            else
            {
                double w = Math.Min(1.0, Math.Max(0.0, u - k));
                s.frame = k; s.pair = k; s.w = w;
                s.interpolating = m.pair_interp[k] != 0;
                s.alpha = s.interpolating ? w : 0.0;
                s.reason = m.pair_reason != null && k < m.pair_reason.Length ? m.pair_reason[k] : (s.interpolating ? 0 : 4);
            }
            s.offsetA = bake.OffsetA(s.pair);
            s.offsetB = bake.OffsetB(s.pair);
            s.afterK = m.k_frame > 0 && m.frame_first + s.frame >= m.k_frame;
            s.afterContact = t >= m.contact_s - 1e-9;
            s.afterOnset = t >= m.onset_s - 1e-9;
            return s;
        }

        public void FillCurve(in RT48SectionState s, double[] xy) => bake.FillBlended(s.pair, s.alpha, xy);
        public void FillFrameCurve(int frame, double[] xy) => bake.FillFrame(frame, xy);

        public void GetLoops(int frame, List<RT48Loop> loops)
        {
            loops.Clear();
            int n = bake.LoopCount(frame);
            for (int j = 0; j < n; j++)
            {
                int li = bake.LoopIndex(frame, j);
                loops.Add(new RT48Loop { kind = bake.Meta.loop_kind[li], first = bake.Meta.loop_point_first[li], count = bake.Meta.loop_point_count[li] });
            }
        }

        // 座席ごとの船からの終わり。焼きの表（seat_x_m・seat_end_s）にある座席だけ（±0.01 m）。
        public bool TryGetSeatEnd(double seatX, out double endS)
        {
            var m = bake.Meta;
            endS = double.NaN;
            if (m.seat_x_m == null || m.seat_end_s == null) return false;
            for (int i = 0; i < m.seat_x_m.Length && i < m.seat_end_s.Length; i++)
                if (Math.Abs(m.seat_x_m[i] - seatX) <= 0.01) { endS = m.seat_end_s[i]; return true; }
            return false;
        }

        public string Describe()
        {
            var m = bake.Meta;
            return Id + "（" + bake.MetaFormat + "）：コマ " + m.frame_first + "〜" + (m.frame_first + m.frame_count - 1) + "、" + m.n_points + " 点、K = " + m.k_frame +
                   "、補間する組 " + CountInterp() + "/" + m.pair_count + "、SHA-256 " + (bake.ShaChecked ? (bake.ShaOk ? "一致" : "不一致") : "未確認") +
                   "、読み " + bake.LoadSeconds.ToString("F2") + " s";
        }

        int CountInterp() { int c = 0; foreach (var v in bake.Meta.pair_interp) c += v != 0 ? 1 : 0; return c; }

        public void Dispose()
        {
            buffer?.Release();
            buffer = null;
        }
    }
}
