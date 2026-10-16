using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Threading;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.FLIP3D
{
    // FLIP3D：長い記録（24 個/s で約 2,160 個）を続けて読む再生の道（2026-10-16 追記、進行役のサブエージェント）。
    // 全部を GPU に置くと足りない（288 個で約 0.7 GB）ので、小さい輪（ring、既定 24 個 ≒ 1 s）だけを持つ：
    //   1. 主スレッドが、これから見せる記録の番号を見せる順に渡す（SetWanted。再生の時計と視点の予定から計算する）。
    //   2. 別のスレッド（1 本）が、まだ輪にない記録を先頭から読み（ファイル → バイト）、読み解き（FLIP3DClip.DecodeInto：量子化を戻す・三角形の回りだけ）、
    //      輪の空いた所（見せる予定のない記録の所）に置く。見せている記録と、予定の記録の所は使わない。
    //   3. 主スレッドは 1 フレームに 1 個だけ、読み解いた記録を GPU の Mesh に送る（Pump。予定の早い物から）。
    //   4. 見せる時は Mesh の参照を入れ替えるだけ（前の全部を置く道と同じ）。
    //      SplitLevel（既定 2）で 1 個を何フレームに分けて送るかを選ぶ：1＝全部を 1 フレーム、2＝点と法線 → 三角形と範囲、3＝点 → 法線 → 三角形と範囲。
    //      1 フレームに送る量を減らす（VR の 90 Hz でも 24 個/s × 3 回 = 72 回/s < 90 フレーム/s）。
    //      点の数が 65,536 より少ない（manifest の vert_max）なら三角形の添字を 16 bit で送る（値は同じ。量が半分）。
    // 間に合わなかった時（実時間）：前の記録を見せ続け、Misses を数える（形を作らない・別の記録で埋めない）。画面外の描画（連番）では待つ（WaitFor）。
    // 形は変えない：Mesh に送るのは DecodeInto の点・法線・三角形そのもの。点の数は記録ごとに違うので、Mesh の器は最大の数で 1 回作り、
    // 部分の範囲（SubMeshDescriptor の indexCount・vertexCount）と箱（bounds）を記録ごとに書く。
    public sealed class FLIP3DStream : IDisposable
    {
        const int Free = 0, Loading = 1, Decoded = 2, Uploading = 3, Uploaded = 4, HalfUploaded = 5;   // HalfUploaded：点だけ送った（分けて送る時）
        const MeshUpdateFlags UF = MeshUpdateFlags.DontValidateIndices | MeshUpdateFlags.DontRecalculateBounds | MeshUpdateFlags.DontResetBoneBounds;

        sealed class Slot
        {
            public int id, record = -1, state = Free;
            public Vector3[] pos, nrm; public int[] idx; public ushort[] idx16;
            public FLIP3DRecordHeader h;
            public Mesh mesh; public int meshVertCap, meshTriCap; public bool mesh16;
            public int upPart, upOp;            // GPU に送り終えた部分（0 点・1 法線・2 三角形）の数と回数
            public GraphicsBuffer vb0, vb1, ib;  // DirectGpu：Mesh の GPU の器を直に書く（Mesh.GetVertexBuffer・GetIndexBuffer）
            public bool use16;
            public string error;
        }

        public FLIP3DManifest Manifest { get; private set; }
        public FLIP3DRecordIndex Index { get; private set; }
        public string Dir { get; private set; }
        public int RingSize { get; private set; }
        public int VertCap { get; private set; }
        public int TriCap { get; private set; }
        public double OpenSeconds { get; private set; }
        public bool VerifySha { get; private set; }
        public string Error { get; private set; }
        public int SplitLevel { get; set; } = 2;
        // true：Mesh の GPU の器（GraphicsBuffer）に直に書く（GraphicsBuffer.SetData）。false：Mesh.SetVertexBufferData（Unity が主メモリーの写しを通して送る）。
        // 2026-10-16 の試し：false では GPU に送るフレームで時々 10〜20 ms の止まりが出た（送る呼び出し自体は最大 2 ms）。どちらも描いた絵は同じか、確かめで比べる
        public bool DirectGpu { get; set; } = true;
        public bool Index16 { get; private set; }
        public int UploadOps { get; private set; }      // GPU に送った回数（分けて送る時は 1 個 = SplitLevel 回）

        // 数（主スレッドで読む。別のスレッドが書く物は lock の中で）
        public int Uploads { get; private set; }
        public int UrgentUploads { get; private set; }
        public double LastUploadMs { get; private set; }
        public int RecordsRead { get; private set; }
        public long BytesRead { get; private set; }
        public int ShaChecked { get; private set; }
        public int ShaMismatches { get; private set; }
        public int Evictions { get; private set; }
        public double LoaderBusySeconds { get; private set; }
        readonly List<float> readMs = new List<float>(), decodeMs = new List<float>(), shaMs = new List<float>(), uploadMs = new List<float>();

        readonly object gate = new object();
        Slot[] slots;
        int[] slotOf;                       // 記録 → 輪の所（なければ −1）
        int[] wanted = new int[0]; int wantedCount;
        int[] wantStamp; int stamp = 1;     // 予定に入っている記録の印
        int displayed = -1;
        Thread thread;
        volatile bool stop;
        int uploadsThisFrame;

        // 輪の Mesh は主メモリーの写しを持つ（isReadable のまま）。UploadMeshData(true) で写しを捨てると、Editor では書けたが
        // Release のプレイヤーでは SetVertexBufferData が「isReadable is false」で止まった（2026-10-16 の試し st4a）ので使わない
        public static FLIP3DStream Open(string dir, int ring, bool verifySha)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var s = new FLIP3DStream { Dir = dir, VerifySha = verifySha };
            s.Manifest = FLIP3DManifest.Read(dir);
            s.Index = FLIP3DRecordIndex.Open(dir, s.Manifest);
            int n = s.Index.Count;
            s.RingSize = Mathf.Clamp(ring, 4, Math.Max(4, n + 2));
            s.VertCap = Math.Max(1, s.Manifest.vert_max);
            s.TriCap = Math.Max(1, s.Manifest.tri_max);
            s.Index16 = s.Manifest.vert_max > 0 && s.Manifest.vert_max <= 65535;
            s.slotOf = new int[n];
            for (int i = 0; i < n; i++) s.slotOf[i] = -1;
            s.wantStamp = new int[n];
            s.slots = new Slot[s.RingSize];
            for (int i = 0; i < s.RingSize; i++)
            {
                var sl = new Slot { id = i, pos = new Vector3[s.VertCap], nrm = new Vector3[s.VertCap], idx = new int[3 * s.TriCap], idx16 = s.Index16 ? new ushort[3 * s.TriCap] : null };
                // MarkDynamic は使わない：D3D11 の dynamic の器は GPU が毎フレーム主メモリーから読むことがあり、6 回描く水で GPU の時間が増えた
                // （2026-10-16 の試し st1_loop：GPU p95 0.22 → 2.69 ms）。見せている Mesh は書き換えないので、ふつうの器で足りる
                sl.mesh = new Mesh { name = "FLIP3D_stream_slot" + i, indexFormat = IndexFormat.UInt32 };
                s.AllocMesh(sl, s.VertCap, s.TriCap, s.Index16);
                s.slots[i] = sl;
            }
            s.thread = new Thread(s.LoaderLoop) { IsBackground = true, Name = "FLIP3D_stream_loader", Priority = System.Threading.ThreadPriority.Normal };
            s.thread.Start();
            s.OpenSeconds = sw.Elapsed.TotalSeconds;
            return s;
        }

        void AllocMesh(Slot sl, int vcap, int tcap, bool use16)
        {
            sl.mesh.SetVertexBufferParams(vcap,
                new VertexAttributeDescriptor(VertexAttribute.Position, VertexAttributeFormat.Float32, 3, 0),
                new VertexAttributeDescriptor(VertexAttribute.Normal, VertexAttributeFormat.Float32, 3, 1));
            sl.mesh.SetIndexBufferParams(3 * tcap, use16 ? IndexFormat.UInt16 : IndexFormat.UInt32);
            sl.mesh.subMeshCount = 1;
            sl.meshVertCap = vcap; sl.meshTriCap = tcap; sl.mesh16 = use16;
            sl.vb0?.Dispose(); sl.vb1?.Dispose(); sl.ib?.Dispose();
            sl.vb0 = sl.vb1 = sl.ib = null;
        }

        // GPU に置く Mesh の大きさ（器の分。点 24 B・三角形 12 B（16 bit なら 6 B））と、主メモリーの読み解きの置き場の大きさ
        public long GpuBytes { get { long b = 0; foreach (var s in slots) b += 24L * s.meshVertCap + (s.mesh16 ? 6L : 12L) * s.meshTriCap; return b; } }
        public long CpuSlotBytes { get { long b = 0; foreach (var s in slots) b += 24L * s.pos.Length + 4L * s.idx.Length + (s.idx16 != null ? 2L * s.idx16.Length : 0); return b; } }

        // 見せる順の予定（先頭が今見せたい記録）と、今見せている記録（その Mesh は使い回さない）
        public void SetWanted(List<int> order, int displayedRecord)
        {
            lock (gate)
            {
                if (wanted.Length < order.Count) wanted = new int[Math.Max(order.Count, 2 * wanted.Length)];
                stamp++;
                if (stamp == int.MaxValue) { Array.Clear(wantStamp, 0, wantStamp.Length); stamp = 1; }
                wantedCount = 0;
                foreach (var r in order)
                {
                    if (r < 0 || r >= slotOf.Length || wantStamp[r] == stamp) continue;
                    wantStamp[r] = stamp;
                    wanted[wantedCount++] = r;
                }
                displayed = displayedRecord;
                Monitor.PulseAll(gate);
            }
        }

        public void SetDisplayed(int r) { lock (gate) { displayed = r; Monitor.PulseAll(gate); } }

        void LoaderLoop()
        {
            byte[] buf = null;
            ushort[] scratch = null;
            SHA256 sha = VerifySha ? SHA256.Create() : null;
            var sw = new System.Diagnostics.Stopwatch();
            try
            {
                using (var rd = new FLIP3DRecordIndex.Reader(Index))
                {
                    while (!stop)
                    {
                        Slot sl = null; int rec = -1;
                        lock (gate)
                        {
                            while (!stop)
                            {
                                rec = -1;
                                for (int i = 0; i < wantedCount; i++) { int r = wanted[i]; if (slotOf[r] < 0) { rec = r; break; } }
                                if (rec >= 0) { sl = PickVictim(); if (sl != null) break; }
                                Monitor.Wait(gate, 50);
                            }
                            if (stop) break;
                            if (sl.record >= 0) { slotOf[sl.record] = -1; Evictions++; }
                            sl.record = rec; sl.state = Loading; sl.error = null; sl.upPart = 0; sl.upOp = 0;
                            slotOf[rec] = sl.id;
                        }
                        double tr, td, ts = 0;
                        sw.Restart();
                        int len = rd.Read(rec, ref buf);
                        tr = sw.Elapsed.TotalMilliseconds;
                        bool shaBad = false;
                        if (sha != null && Manifest.source_sha256 != null && rec < Manifest.source_sha256.Length)
                        {
                            sw.Restart();
                            var hb = sha.ComputeHash(buf, 0, len);
                            shaBad = !HexEq(hb, Manifest.source_sha256[rec]);
                            ts = sw.Elapsed.TotalMilliseconds;
                        }
                        sw.Restart();
                        var h = FLIP3DClip.ReadHeader(buf, 0);
                        if (h.nv > sl.pos.Length) { sl.pos = new Vector3[h.nv]; sl.nrm = new Vector3[h.nv]; }
                        if (3 * h.nt > sl.idx.Length) sl.idx = new int[3 * h.nt];
                        sl.h = FLIP3DClip.DecodeInto(buf, 0, sl.pos, sl.nrm, sl.idx, ref scratch);
                        // 16 bit の添字（点が 65,536 より少ない時だけ。値は同じ）
                        sl.use16 = Index16 && sl.h.nv <= 65535;
                        if (sl.use16)
                        {
                            int m3 = 3 * sl.h.nt;
                            if (sl.idx16 == null || sl.idx16.Length < m3) sl.idx16 = new ushort[m3];
                            var a = sl.idx; var a16 = sl.idx16;
                            for (int q = 0; q < m3; q++) a16[q] = (ushort)a[q];
                        }
                        td = sw.Elapsed.TotalMilliseconds;
                        string err = null;
                        if (Manifest.source_frames != null && rec < Manifest.source_frames.Length && Manifest.source_frames[rec] != sl.h.frame)
                            err = "記録 " + rec + " のコマが manifest と違う：" + sl.h.frame + " != " + Manifest.source_frames[rec];
                        lock (gate)
                        {
                            sl.error = err;
                            if (err != null) Error = err;
                            sl.state = Decoded;
                            RecordsRead++; BytesRead += len; LoaderBusySeconds += (tr + td + ts) / 1000.0;
                            if (readMs.Count < 200000) { readMs.Add((float)tr); decodeMs.Add((float)td); if (sha != null) shaMs.Add((float)ts); }
                            if (sha != null) { ShaChecked++; if (shaBad) { ShaMismatches++; Error = "記録 " + rec + " の SHA-256 が manifest と違う"; } }
                            Monitor.PulseAll(gate);
                        }
                    }
                }
            }
            catch (Exception e)
            {
                lock (gate) { Error = e.ToString(); Monitor.PulseAll(gate); }
                Debug.LogError("FLIP3D_STREAM_LOADER_EXCEPTION " + e);
            }
            finally { sha?.Dispose(); }
        }

        static bool HexEq(byte[] h, string hex)
        {
            if (hex == null || hex.Length != 2 * h.Length) return false;
            const string d = "0123456789abcdef";
            for (int i = 0; i < h.Length; i++)
                if (char.ToLowerInvariant(hex[2 * i]) != d[h[i] >> 4] || char.ToLowerInvariant(hex[2 * i + 1]) != d[h[i] & 15]) return false;
            return true;
        }

        // lock の中で呼ぶ。空いた所、なければ予定に入っていない・見せていない記録の所（読み解き中・送る途中は除く）
        Slot PickVictim()
        {
            Slot best = null;
            foreach (var s in slots)
            {
                if (s.state == Free) return s;
                if (s.state == Loading || s.state == Uploading) continue;    // HalfUploaded は使い回してよい（見せていない）
                if (s.record == displayed) continue;
                if (s.record >= 0 && wantStamp[s.record] == stamp) continue;
                if (best == null || (best.state == Decoded && s.state == Uploaded)) best = s;
            }
            return best;
        }

        // フレームの始め（主スレッド。FLIP3DPlayer.ApplyTime が 1 回呼ぶ）：このフレームで送った数を 0 に戻す
        public void BeginFrame() { uploadsThisFrame = 0; }

        // 1 フレームに 1 回だけ、予定の早い順に、読み解いた記録を GPU に送る（主スレッド）。送った回数を返す
        public int Pump()
        {
            if (uploadsThisFrame > 0) return 0;
            Slot pick = null; int was = 0;
            lock (gate)
            {
                for (int i = 0; i < wantedCount && pick == null; i++)
                {
                    int si = slotOf[wanted[i]];
                    if (si >= 0 && (slots[si].state == Decoded || slots[si].state == HalfUploaded)) pick = slots[si];
                }
                if (pick == null) return 0;
                was = pick.state;
                pick.state = Uploading;
            }
            Upload(pick, false, was, SplitLevel <= 1);
            return 1;
        }

        static readonly int[][] Plans = { new[] { 3 }, new[] { 3 }, new[] { 2, 1 }, new[] { 1, 1, 1 } };

        // 送る前の状態は upPart（0 点・1 法線・2 三角形まで済み）。full：残りを全部このフレームで送る
        void Upload(Slot s, bool urgent, int was, bool full)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var h = s.h;
            var m = s.mesh;
            var plan = Plans[Math.Max(1, Math.Min(3, SplitLevel))];
            int n = full ? 3 - s.upPart : Math.Min(3 - s.upPart, plan[Math.Min(s.upOp, plan.Length - 1)]);
            for (int part = s.upPart; part < s.upPart + n; part++)
            {
                if (part == 0)
                {
                    if (h.nv > s.meshVertCap || h.nt > s.meshTriCap || s.use16 != s.mesh16) AllocMesh(s, Math.Max(h.nv, s.meshVertCap), Math.Max(h.nt, s.meshTriCap), s.use16);
                    if (DirectGpu) { if (s.vb0 == null) s.vb0 = m.GetVertexBuffer(0); s.vb0.SetData(s.pos, 0, 0, h.nv); }
                    else m.SetVertexBufferData(s.pos, 0, 0, h.nv, 0, UF);
                }
                else if (part == 1)
                {
                    if (DirectGpu) { if (s.vb1 == null) s.vb1 = m.GetVertexBuffer(1); s.vb1.SetData(s.nrm, 0, 0, h.nv); }
                    else m.SetVertexBufferData(s.nrm, 0, 0, h.nv, 1, UF);
                }
                else
                {
                    if (DirectGpu)
                    {
                        if (s.ib == null) s.ib = m.GetIndexBuffer();
                        if (s.use16) s.ib.SetData(s.idx16, 0, 0, 3 * h.nt); else s.ib.SetData(s.idx, 0, 0, 3 * h.nt);
                    }
                    else if (s.use16) m.SetIndexBufferData(s.idx16, 0, 0, 3 * h.nt, UF);
                    else m.SetIndexBufferData(s.idx, 0, 0, 3 * h.nt, UF);
                    var b = new Bounds((h.lo + h.hi) * 0.5f, h.hi - h.lo);
                    m.SetSubMesh(0, new SubMeshDescriptor(0, 3 * h.nt, MeshTopology.Triangles) { bounds = b, firstVertex = 0, vertexCount = h.nv }, UF);
                    m.bounds = b;
                }
            }
            s.upPart += n; s.upOp++;
            bool doneAll = s.upPart >= 3;
            LastUploadMs = sw.Elapsed.TotalMilliseconds;
            lock (gate) { s.state = doneAll ? Uploaded : HalfUploaded; Monitor.PulseAll(gate); }
            if (doneAll) Uploads++;
            UploadOps++; uploadsThisFrame++;
            if (urgent) UrgentUploads++;
            if (uploadMs.Count < 200000) uploadMs.Add((float)LastUploadMs);
        }

        // 記録 r が GPU にあれば Mesh を返す。読み解き済みでまだ送っていなければ、今送る（このフレームの 2 個目なら「急ぎ」と数える）
        public bool TryGet(int r, out Mesh mesh, out FLIP3DRecordHeader h)
        {
            mesh = null; h = default;
            Slot s = null; bool up = false; int was = 0;
            lock (gate)
            {
                int si = slotOf[r];
                if (si < 0) return false;
                s = slots[si];
                if (s.state == Uploaded) { mesh = s.mesh; h = s.h; return true; }
                if (s.state != Decoded && s.state != HalfUploaded) return false;
                was = s.state;
                s.state = Uploading; up = true;
            }
            if (up)
            {
                Upload(s, uploadsThisFrame > 0, was, true);
                mesh = s.mesh; h = s.h;
                return true;
            }
            return false;
        }

        // 記録 r が GPU に来るまで待つ（画面外の描画・始めの読み込み用。実時間の再生では使わない）
        public Mesh WaitFor(int r, int timeoutMs, out FLIP3DRecordHeader h)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            while (true)
            {
                if (TryGet(r, out var m, out h)) return m;
                lock (gate)
                {
                    if (Error != null && !Error.StartsWith("記録")) throw new InvalidOperationException("FLIP3D の読み込みが止まった：" + Error);
                    if (sw.ElapsedMilliseconds > timeoutMs) throw new TimeoutException("記録 " + r + " が " + timeoutMs + " ms で来ない");
                    int si = slotOf[r];
                    if (si < 0 || slots[si].state == Loading) Monitor.Wait(gate, 20);
                }
            }
        }

        // 予定の先頭から count 個が読み解かれるまで待ち、全部を GPU に送る（始めの読み込み）
        public double Prefill(int count, int timeoutMs)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            int[] want;
            lock (gate) { want = new int[Math.Min(count, wantedCount)]; Array.Copy(wanted, want, want.Length); }
            foreach (var r in want) WaitFor(r, timeoutMs, out _);
            return sw.Elapsed.TotalSeconds;
        }

        // 確かめ用：記録 r の読み解いた配列（GPU に送ったのと同じ物）を写す
        public void CopyDecoded(int r, int timeoutMs, out Vector3[] pos, out Vector3[] nrm, out int[] idx, out FLIP3DRecordHeader h)
        {
            bool inWanted; int disp;
            lock (gate) { inWanted = wantStamp[r] == stamp; disp = displayed; }
            if (!inWanted) SetWanted(new List<int> { r }, disp);       // 予定にない記録は、それだけを予定にして読ませる（後で FLIP3DPlayer.InvalidateWanted）
            WaitFor(r, timeoutMs, out h);
            lock (gate)
            {
                var s = slots[slotOf[r]];
                pos = new Vector3[s.h.nv]; nrm = new Vector3[s.h.nv]; idx = new int[3 * s.h.nt];
                Array.Copy(s.pos, pos, pos.Length); Array.Copy(s.nrm, nrm, nrm.Length); Array.Copy(s.idx, idx, idx.Length);
                h = s.h;
            }
        }

        public int ReadyCount { get { lock (gate) { int c = 0; foreach (var s in slots) if (s.state == Uploaded) c++; return c; } } }

        public float[] ReadMs { get { lock (gate) return readMs.ToArray(); } }
        public float[] DecodeMs { get { lock (gate) return decodeMs.ToArray(); } }
        public float[] ShaMs { get { lock (gate) return shaMs.ToArray(); } }
        public float[] UploadMsAll => uploadMs.ToArray();

        public void Dispose()
        {
            stop = true;
            lock (gate) Monitor.PulseAll(gate);
            if (thread != null && !thread.Join(5000)) Debug.LogWarning("FLIP3D_STREAM loader did not stop in 5 s");
            thread = null;
            if (slots != null)
                foreach (var s in slots)
                {
                    s.vb0?.Dispose(); s.vb1?.Dispose(); s.ib?.Dispose(); s.vb0 = s.vb1 = s.ib = null;
                    if (s.mesh != null) { if (Application.isPlaying) UnityEngine.Object.Destroy(s.mesh); else UnityEngine.Object.DestroyImmediate(s.mesh); s.mesh = null; }
                }
        }

        // 読みと読み解きの速さだけを測る（Mesh に送らない。主スレッドで順に。OS のファイルの写しが温かいかは分からない）
        [Serializable] public class BenchResult { public int records; public long bytes; public double seconds, readSeconds, decodeSeconds, readMBps, recordsPerSecond, decodeMsP50, decodeMsP95, readMsP50, readMsP95, readMsMax; public string where; }
        public static BenchResult Bench(string dir, int maxRecords)
        {
            var mf = FLIP3DManifest.Read(dir);
            var x = FLIP3DRecordIndex.Open(dir, mf);
            int n = Math.Min(x.Count, maxRecords <= 0 ? x.Count : maxRecords);
            var pos = new Vector3[Math.Max(1, mf.vert_max)]; var nrm = new Vector3[pos.Length]; var idx = new int[3 * Math.Max(1, mf.tri_max)];
            byte[] buf = null; ushort[] scratch = null;
            var rms = new List<double>(); var dms = new List<double>();
            long bytes = 0;
            var all = System.Diagnostics.Stopwatch.StartNew();
            var sw = new System.Diagnostics.Stopwatch();
            using (var rd = new FLIP3DRecordIndex.Reader(x))
            {
                for (int i = 0; i < n; i++)
                {
                    sw.Restart(); int len = rd.Read(i, ref buf); rms.Add(sw.Elapsed.TotalMilliseconds); bytes += len;
                    var h = FLIP3DClip.ReadHeader(buf, 0);
                    if (h.nv > pos.Length) { pos = new Vector3[h.nv]; nrm = new Vector3[h.nv]; }
                    if (3 * h.nt > idx.Length) idx = new int[3 * h.nt];
                    sw.Restart(); FLIP3DClip.DecodeInto(buf, 0, pos, nrm, idx, ref scratch); dms.Add(sw.Elapsed.TotalMilliseconds);
                }
            }
            double rs = 0, ds = 0; foreach (var v in rms) rs += v; foreach (var v in dms) ds += v;
            var ra = rms.ToArray(); Array.Sort(ra); var da = dms.ToArray(); Array.Sort(da);
            return new BenchResult
            {
                records = n, bytes = bytes, seconds = all.Elapsed.TotalSeconds, readSeconds = rs / 1000, decodeSeconds = ds / 1000,
                readMBps = bytes / 1e6 / Math.Max(1e-9, rs / 1000), recordsPerSecond = n / Math.Max(1e-9, all.Elapsed.TotalSeconds),
                decodeMsP50 = da[(int)(0.5 * (n - 1))], decodeMsP95 = da[(int)(0.95 * (n - 1))],
                readMsP50 = ra[(int)(0.5 * (n - 1))], readMsP95 = ra[(int)(0.95 * (n - 1))], readMsMax = ra[n - 1], where = x.Where
            };
        }
    }
}
