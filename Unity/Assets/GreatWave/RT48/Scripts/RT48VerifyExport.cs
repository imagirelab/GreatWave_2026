using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace GreatWave.RT48
{
    // RT48：確かめのための書き出し（Unity/Build/RT48/record_ja.md の V1・V3・V4・V5・V6）。Editor（RT48VerifyEditor）とプレイヤー（-rt48export）の両方から使う。
    //   ・曲線：描くシェーダーと同じ RT48Decode.hlsl を計算シェーダー（RT48DecodeCheck.compute）で走らせ、全部の点の (X, Y, nX, nY) を float32 で書く。
    //       src556    全部の組の割合 0（A）と 1（B）、座席 556 m（V1・V2・V4）
    //       src574    10 組おきの割合 0 と 1、座席 574 m（V1）
    //       interp556 補間する組の割合 j/30（j = 1〜29）、座席 556 m（V3）
    //       holdout   取り置いたコマの組（v_prep.py の holdout_pairs.bin）を同じ式で混ぜた線、座席 556 m（V5）
    //   ・船：c6_times.json の時刻で RT48Playback.ApplyTime を呼び、上下・縦揺れ・求め方と、船の根とカメラの世界の位置を書く（V4・V6）。
    // 判定はここではしない（Python の v_compare.py）。
    public static class RT48VerifyExport
    {
        [Serializable] public class CurveCase { public string group; public int pair; public double alpha; public double seatX; public long offsetFloats; public int frameA, frameB; }
        [Serializable]
        public class BoatCase
        {
            public double seatX, t, alpha, w, heave, pitchDeg, rootX, rootY, rootZ, rootRollZDeg, camX, camY, camZ;
            public string mode, kind; public int frame, pair, reason; public bool interp, last, afterK;
        }
        [Serializable]
        public class Index
        {
            public string schema = "GreatWave.RT48.verifyexport/1";
            public string source, sourceDir, gpu, graphicsApi, unity, utc, commandLine, curvesFile, holdoutFile, noteJa;
            public bool isEditor;
            public int nPoints, frameFirst;
            public double xOriginM;
            public double[] taperStored;
            public CurveCase[] curves, holdout;
            public BoatCase[] boats;
            public double seconds;
        }

        static void Decode(ComputeShader cs, int k, GraphicsBuffer curves, GraphicsBuffer outBuf, int n, int offA, int offB, double alpha, double shift, double[] tp, float[] dst)
        {
            cs.SetBuffer(k, "_RT48Curves", curves);
            cs.SetBuffer(k, "_RT48Out", outBuf);
            cs.SetInt("_RT48PointCount", n);
            cs.SetFloat("_RT48XShift", (float)shift);
            cs.SetVector("_RT48Taper", new Vector4((float)tp[0], (float)tp[1], (float)tp[2], (float)tp[3]));
            cs.SetInt("_RT48OffsetA", offA);
            cs.SetInt("_RT48OffsetB", offB);
            cs.SetFloat("_RT48Alpha", (float)alpha);   // 描く時と同じく float で渡す
            cs.Dispatch(k, (n + 63) / 64, 1, 1);
            outBuf.GetData(dst);
        }

        static void WriteFloats(FileStream fs, float[] a, byte[] tmp)
        {
            Buffer.BlockCopy(a, 0, tmp, 0, a.Length * 4);
            fs.Write(tmp, 0, a.Length * 4);
        }

        // verifyDir：v_prep.py の出力（holdout_pairs.bin・holdout_index.json・c6_times.json）。outDir：書き出し先。
        public static Index Run(RT48Playback pb, string verifyDir, string outDir, bool withHoldout)
        {
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var src = pb.Source as RecordedSectionSource;
            if (src == null) throw new InvalidOperationException("焼いた元がありません：" + pb.LoadError);
            Directory.CreateDirectory(outDir);
            var bake = src.Bake;
            int n = src.PointCount;
            var cs = pb.decodeCheck;
            int kern = cs.FindKernel("Decode");
            var outBuf = new GraphicsBuffer(GraphicsBuffer.Target.Structured, n, 16);
            var dst = new float[4 * n];
            var tmp = new byte[16 * n];
            var tp = src.TaperStored;
            var idx = new Index
            {
                source = src.Id, sourceDir = bake.Dir, gpu = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), unity = Application.unityVersion,
                utc = DateTime.UtcNow.ToString("O"), commandLine = Environment.CommandLine, isEditor = Application.isEditor, nPoints = n, frameFirst = src.FrameNumberFirst,
                xOriginM = src.XOriginM, taperStored = tp, curvesFile = "curves.bin",
                noteJa = "curves.bin・holdout_out.bin：float32 LE、組ごとに [点][X, Y, nX, nY]（X は Unity の X ＝ x_rel − 座席）。offsetFloats はファイルの中の float の番号。"
            };
            var cases = new List<CurveCase>();
            try
            {
                using (var fs = new FileStream(Path.Combine(outDir, "curves.bin"), FileMode.Create, FileAccess.Write))
                {
                    long off = 0;
                    void One(string g, int p, double a, double seat)
                    {
                        Decode(cs, kern, src.CurveBuffer, outBuf, n, bake.OffsetA(p), bake.OffsetB(p), a, src.XOriginM - seat, tp, dst);
                        WriteFloats(fs, dst, tmp);
                        cases.Add(new CurveCase { group = g, pair = p, alpha = a, seatX = seat, offsetFloats = off, frameA = src.FrameNumberFirst + p, frameB = src.FrameNumberFirst + p + 1 });
                        off += 4L * n;
                    }
                    for (int p = 0; p < bake.P; p++) { One("src556", p, 0.0, 556.0); One("src556", p, 1.0, 556.0); }
                    for (int p = 0; p < bake.P; p += 10) { One("src574", p, 0.0, 574.0); One("src574", p, 1.0, 574.0); }
                    for (int p = 0; p < bake.P; p++)
                        if (bake.Meta.pair_interp[p] != 0)
                            for (int j = 1; j < 30; j++) One("interp556", p, j / 30.0, 556.0);
                }
                idx.curves = cases.ToArray();

                // 取り置いたコマの組（V5）
                if (withHoldout && File.Exists(Path.Combine(verifyDir, "holdout_pairs.bin")))
                {
                    var hidx = RT48Json.O(RT48Json.Parse(File.ReadAllText(Path.Combine(verifyDir, "holdout_index.json"), System.Text.Encoding.UTF8)));
                    var ent = RT48Json.A(RT48Json.Get(hidx, "entries"));
                    var bytes = File.ReadAllBytes(Path.Combine(verifyDir, "holdout_pairs.bin"));
                    if (bytes.Length != ent.Count * 2L * n * 2 * 4) throw new InvalidOperationException("holdout_pairs.bin の大きさが索引と合いません");
                    var hf = new float[bytes.Length / 4];
                    Buffer.BlockCopy(bytes, 0, hf, 0, bytes.Length);
                    var hb = new GraphicsBuffer(GraphicsBuffer.Target.Structured, hf.Length / 2, 8) { name = "RT48 取り置いたコマの組" };
                    var hc = new List<CurveCase>();
                    try
                    {
                        hb.SetData(hf);
                        using (var fs = new FileStream(Path.Combine(outDir, "holdout_out.bin"), FileMode.Create, FileAccess.Write))
                        {
                            long off = 0;
                            for (int e = 0; e < ent.Count; e++)
                            {
                                var eo = RT48Json.O(ent[e]);
                                int i = RT48Json.I(RT48Json.Get(eo, "i")), k = RT48Json.I(RT48Json.Get(eo, "k")), kb = RT48Json.I(RT48Json.Get(eo, "kb"));
                                foreach (var av in RT48Json.A(RT48Json.Get(eo, "alphas")))
                                {
                                    double a = RT48Json.D(av);
                                    Decode(cs, kern, hb, outBuf, n, i * 2 * n, i * 2 * n + n, a, src.XOriginM - 556.0, tp, dst);
                                    WriteFloats(fs, dst, tmp);
                                    hc.Add(new CurveCase { group = "holdout", pair = i, alpha = a, seatX = 556.0, offsetFloats = off, frameA = k, frameB = kb });
                                    off += 4L * n;
                                }
                            }
                        }
                    }
                    finally { hb.Release(); }
                    idx.holdout = hc.ToArray();
                    idx.holdoutFile = "holdout_out.bin";
                }
            }
            finally { outBuf.Release(); }

            // 船（V4・V6）
            var boats = new List<BoatCase>();
            double seat0 = pb.SeatX;
            var c6p = Path.Combine(verifyDir, "c6_times.json");
            if (File.Exists(c6p))
            {
                var c6 = RT48Json.O(RT48Json.Parse(File.ReadAllText(c6p, System.Text.Encoding.UTF8)));
                var seats = RT48Json.GetO(c6, "seats");
                foreach (var kv in seats)
                {
                    var so = RT48Json.O(kv.Value);
                    double seat = RT48Json.D(RT48Json.Get(so, "seat_x"));
                    pb.SetSeat(seat);
                    var ts = new List<KeyValuePair<double, string>>();
                    foreach (var tv in RT48Json.A(RT48Json.Get(so, "times")))
                    {
                        var to = RT48Json.O(tv);
                        ts.Add(new KeyValuePair<double, string>(RT48Json.D(RT48Json.Get(to, "t")), (string)RT48Json.Get(to, "kind")));
                    }
                    // 目印の時刻（V4）：巻き始め・3744 コマ・最初の接触
                    ts.Add(new KeyValuePair<double, string>(src.OnsetS, "landmark_onset"));
                    ts.Add(new KeyValuePair<double, string>(src.ContactS - 1.0 / src.Fps, "landmark_contact_minus1"));
                    ts.Add(new KeyValuePair<double, string>(src.ContactS, "landmark_contact"));
                    foreach (var kt in ts)
                    {
                        pb.ApplyTime(kt.Key);
                        pb.ApplyDesktopView();
                        var s = pb.State; var bp = pb.BoatPose;
                        var rp = pb.boatRoot != null ? pb.boatRoot.position : Vector3.zero;
                        float rz = pb.boatRoot != null ? pb.boatRoot.rotation.eulerAngles.z : 0f;
                        if (rz > 180f) rz -= 360f;
                        var cp = pb.viewCamera != null ? pb.viewCamera.transform.position : Vector3.zero;
                        boats.Add(new BoatCase
                        {
                            seatX = seat, t = kt.Key, kind = kt.Value, alpha = s.alpha, w = s.w, heave = bp.heave, pitchDeg = bp.pitchDeg, mode = pb.BoatMode,
                            frame = src.FrameNumberFirst + s.frame, pair = s.pair, reason = s.reason, interp = s.interpolating, last = s.last, afterK = s.afterK,
                            rootX = rp.x, rootY = rp.y, rootZ = rp.z, rootRollZDeg = rz, camX = cp.x, camY = cp.y, camZ = cp.z
                        });
                    }
                }
                pb.SetSeat(seat0);
            }
            idx.boats = boats.ToArray();
            idx.seconds = sw.Elapsed.TotalSeconds;
            File.WriteAllText(Path.Combine(outDir, "index.json"), JsonUtility.ToJson(idx, true), new System.Text.UTF8Encoding(false));
            Debug.Log("RT48_VERIFYEXPORT done curves=" + cases.Count + " holdout=" + (idx.holdout != null ? idx.holdout.Length : 0) + " boats=" + boats.Count +
                      " seconds=" + idx.seconds.ToString("F1", CultureInfo.InvariantCulture) + " out=" + outDir);
            return idx;
        }
    }
}
