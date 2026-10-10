using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Rendering;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.RT48.EditorTools
{
    // RT48：合成の曲線（Tools/GWWaveGen/rt48/u_synth.py）で Unity の部品を確かめる（batchmode、GPU あり）。
    //   -executeMethod GreatWave.RT48.EditorTools.RT48SelfTest.RunAll
    // 判定（走らせる前に決めた。Unity/Build/RT48/unity/record_ja.md）：
    //   T1 シェーダー：RT48 のシェーダーがコンパイルでき、STEREO_INSTANCING_ON の頂点の出力に SV_RenderTargetArrayIndex がある
    //   T2 時刻 → 組・割合・補間するか：Python と全部同じ（割合は 1e-12 以内）
    //   T3 CPU の曲線（表示の位置と法線）：Python と 1e-9 以内
    //   T4 GPU の読み解き（RT48Decode.hlsl）：CPU の float64 と、位置 max(1e-4 m, 4 ulp)・法線 0.5° 以内（C5 と同じ幅）
    //   T5 船の上下・縦揺れ：Python と 0.001 m・0.01° 以内（C6 と同じ幅）、求め方（曲線／コマの補間／最後）も同じ
    //   T6 表の向き：掃いた面の三角形の表が曲線の左の法線（空気）の向き、海は上、離れた水は外
    //   T7 船の傾きの向き：縦揺れが正なら船尾（+X）が上がる
    //   T8 離れた水：閉じた水のあるコマで管ができ、ないコマで空
    //   T9 終わりの時刻：座席 556・574 の終わりが焼きの表と同じ
    //   T10 静止画：書けて、真っ白・真っ黒でない（見た目は人が見る。合成の曲線なので判定の材料にしない）
    public static class RT48SelfTest
    {
        [Serializable] class RefPoint { public int i; public double xs, y, nx, ny; }
        [Serializable] class RefBoat { public double seat_x, heave, pitch_deg; public string mode; }
        [Serializable] class RefState { public double t, alpha; public int frame, pair; public bool interp, last; public RefPoint[] points; public RefBoat[] boats; }
        [Serializable] class Ref { public int k_frame, contact_frame; public double[] seat_x, seat_end_s; public RefState[] states; }

        [Serializable] public class Check { public string id, nameJa, detail; public bool pass; }
        [Serializable] public class Still { public string file, view; public double t, seat, meanLum, stdLum, skyFrac; }
        [Serializable]
        public class Report
        {
            public string schema = "GreatWave.RT48.selftest/1";
            public string unity, utc, gpu, graphicsApi, bakeDir, scenePath, noteJa;
            public bool pass;
            public Check[] checks;
            public RT48DecodeCheck.Result decode556, decode574, decodeCoarse556;
            public Still[] stillsCoarse;
            public double[] endsFromCurvesUnity, endsTable, endsPython;
            public Still[] stills;
            public string[] shaderPasses;
            public double loadSeconds, frameBoatSeconds, applyTimeMeanMs;
        }

        static readonly List<Check> checks = new List<Check>();
        static void Add(string id, string name, bool pass, string detail) { checks.Add(new Check { id = id, nameJa = name, pass = pass, detail = detail }); Debug.Log("RT48_CHECK " + id + " " + (pass ? "PASS" : "FAIL") + " " + detail); }

        public static void RunAll()
        {
            int code = 1;
            try
            {
                var rep = Run();
                code = rep.pass ? 0 : 2;
            }
            catch (Exception e) { Debug.LogError("RT48_SELFTEST_EXCEPTION " + e); code = 1; }
            EditorApplication.Exit(code);
        }

        public static Report Run()
        {
            checks.Clear();
            RT48SceneBuilder.Build();
            var rep = new Report { unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), gpu = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(), scenePath = RT48SceneBuilder.ScenePath };
            var outDir = RT48SceneBuilder.UnityOut;
            Directory.CreateDirectory(outDir);
            rep.shaderPasses = ShaderCheck();

            string bake = Path.Combine(RT48SceneBuilder.BakeRoot, "synth");
            rep.bakeDir = bake;
            var refj = JsonUtility.FromJson<Ref>(File.ReadAllText(Path.Combine(bake, "ref_python.json")));
            var pb = UnityEngine.Object.FindAnyObjectByType<RT48Playback>();
            var caps = UnityEngine.Object.FindAnyObjectByType<RT48Captions>();
            var sw = System.Diagnostics.Stopwatch.StartNew();
            pb.Initialize(bake);
            rep.loadSeconds = sw.Elapsed.TotalSeconds;
            if (pb.Source == null) throw new InvalidOperationException("合成の元を読めません：" + pb.LoadError);
            var src = (RecordedSectionSource)pb.Source;
            Add("T0", "焼きの読み込みと SHA-256", src.Bake.ShaChecked && src.Bake.ShaOk, src.Describe() + " " + src.Bake.ShaNote);

            // T2・T3
            int n = src.PointCount;
            var raw = new double[2 * n]; var disp = new double[2 * n];
            int bad2 = 0, bad3 = 0; double maxA = 0, maxP = 0, maxN = 0;
            foreach (var r in refj.states)
            {
                var s = src.StateAt(r.t);
                bool same = s.frame == r.frame && s.pair == r.pair && s.interpolating == r.interp && s.last == r.last;
                maxA = Math.Max(maxA, Math.Abs(s.alpha - r.alpha));
                if (!same || Math.Abs(s.alpha - r.alpha) > 1e-12) bad2++;
                src.FillCurve(s, raw);
                RT48BoatMotion.ToDisplayed(raw, n, src.TaperStored, disp);
                foreach (var p in r.points)
                {
                    double ex = Math.Abs(disp[2 * p.i] - p.xs), ey = Math.Abs(disp[2 * p.i + 1] - p.y);
                    int i0 = Math.Max(0, p.i - 1), i1 = Math.Min(n - 1, p.i + 1);
                    double tx = disp[2 * i1] - disp[2 * i0], ty = disp[2 * i1 + 1] - disp[2 * i0 + 1], L = Math.Sqrt(tx * tx + ty * ty);
                    double en = Math.Max(Math.Abs(-ty / L - p.nx), Math.Abs(tx / L - p.ny));
                    maxP = Math.Max(maxP, Math.Max(ex, ey)); maxN = Math.Max(maxN, en);
                    if (ex > 1e-9 || ey > 1e-9 || en > 1e-9) bad3++;
                }
            }
            Add("T2", "時刻 → 組・割合・補間するか（Python と）", bad2 == 0, refj.states.Length + " の時刻、違い " + bad2 + "、割合の差の最大 " + maxA.ToString("E2"));
            Add("T3", "CPU の表示の点と法線（Python と）", bad3 == 0, "差の最大 位置 " + maxP.ToString("E2") + " m・法線 " + maxN.ToString("E2") + "、外れ " + bad3);

            // T5・T9・船の時間
            int bad5 = 0; double maxH = 0, maxPd = 0; var modeBad = new List<string>();
            var endsU = new List<double>(); var endsT = new List<double>();
            double applySum = 0; int applyN = 0;
            for (int si = 0; si < refj.seat_x.Length; si++)
            {
                double seat = refj.seat_x[si];
                sw.Restart();
                pb.SetSeat(seat);
                rep.frameBoatSeconds = Math.Max(rep.frameBoatSeconds, sw.Elapsed.TotalSeconds);
                endsT.Add(pb.TimeEnd);
                endsU.Add(pb.EndFromCurves());
                foreach (var r in refj.states)
                {
                    var rb = r.boats.First(b => Math.Abs(b.seat_x - seat) < 1e-6);
                    sw.Restart();
                    pb.ApplyTime(r.t);
                    applySum += sw.Elapsed.TotalMilliseconds; applyN++;
                    double eh = Math.Abs(pb.BoatPose.heave - rb.heave), ep = Math.Abs(pb.BoatPose.pitchDeg - rb.pitch_deg);
                    maxH = Math.Max(maxH, eh); maxPd = Math.Max(maxPd, ep);
                    if (eh > 0.001 || ep > 0.01) bad5++;
                    if (pb.BoatMode != rb.mode) modeBad.Add(r.t.ToString("F4", CultureInfo.InvariantCulture) + ":" + pb.BoatMode + "≠" + rb.mode);
                }
            }
            rep.applyTimeMeanMs = applySum / Math.Max(1, applyN);
            Add("T5", "船の上下・縦揺れ（Python と）", bad5 == 0 && modeBad.Count == 0, "差の最大 上下 " + maxH.ToString("E2") + " m・縦揺れ " + maxPd.ToString("E2") + "°、外れ " + bad5 + "、求め方の違い " + modeBad.Count + " " + string.Join(" ", modeBad));
            rep.endsFromCurvesUnity = endsU.ToArray(); rep.endsTable = endsT.ToArray(); rep.endsPython = refj.seat_end_s;
            bool ends = endsT.Count == refj.seat_end_s.Length && endsT.Zip(refj.seat_end_s, (a, b) => Math.Abs(a - b) < 1e-9).All(x => x);
            Add("T9", "座席ごとの終わり（焼きの表）", ends, "表 " + string.Join(", ", endsT.Select(v => v.ToString("F4", CultureInfo.InvariantCulture))) +
                " s。参考：Unity が 8,192 点の曲線から求めた値 " + string.Join(", ", endsU.Select(v => v.ToString("F4", CultureInfo.InvariantCulture))) + " s（Python は取り直す前の細かい線で求めた）");

            // T4
            var times = refj.states.Select(r => r.t).ToList();
            rep.decode556 = RT48DecodeCheck.Run(pb.decodeCheck, src, 556.0, times);
            rep.decode574 = RT48DecodeCheck.Run(pb.decodeCheck, src, 574.0, times);
            Add("T4", "GPU の読み解き（RT48Decode.hlsl を計算シェーダーで）と CPU の float64", rep.decode556.pass && rep.decode574.pass,
                "座席 556：位置の差の最大 " + rep.decode556.maxPosErr.ToString("E2") + " m（幅に対し " + rep.decode556.maxPosErrOverTol.ToString("F3") + "）・法線 " + rep.decode556.maxNormDeg.ToString("E2") +
                "°。座席 574：" + rep.decode574.maxPosErr.ToString("E2") + " m・" + rep.decode574.maxNormDeg.ToString("E2") + "°。" + times.Count + " の時刻 × " + n + " 点");

            // T6・T7・T8
            pb.SetSeat(556.0);
            double tOver = refj.states.First(r => r.interp && r.t > 153.9 && r.t < 154.1).t;
            pb.ApplyTime(tOver);
            Add("T6", "表の向き（掃いた面・海・離れた水）", WindingCheck(pb, out var wdetail), wdetail);
            var slope = pb.BoatPose.slope;
            float sternUp = pb.boatRoot.TransformDirection(Vector3.right).y;
            bool t7 = Math.Abs(pb.BoatPose.pitchDeg) > 0.05 && Math.Sign(sternUp) == Math.Sign(slope);
            Add("T7", "船の傾きの向き", t7, "t=" + tOver.ToString("F4", CultureInfo.InvariantCulture) + " 縦揺れ " + pb.BoatPose.pitchDeg.ToString("F3") + "°、船の +X の向きの y " + sternUp.ToString("F4"));
            pb.ApplyTime(150.0);
            int v0 = pb.loopsFilter.sharedMesh.vertexCount;
            pb.ApplyTime(156.0);
            int v1 = pb.loopsFilter.sharedMesh.vertexCount;
            int nl = 0; foreach (var r in new[] { 156.0 }) { var st = src.StateAt(r); nl = src.Bake.LoopCount(st.frame); }
            Add("T8", "離れた水の管", v0 == 0 && v1 > 0, "150.0 s の点 " + v0 + "、156.0 s の点 " + v1 + "（閉じた線 " + nl + "、うち空気は描かない）");

            // T10 静止画
            var stills = new List<Still>();
            var stillDir = Path.Combine(outDir, "stills_synth");
            Directory.CreateDirectory(stillDir);
            foreach (var seat in new[] { 556.0, 574.0 })
            {
                pb.SetSeat(seat);
                var ts = new[] { pb.TimeStart, src.OnsetS, src.ContactS, pb.TimeEnd };
                foreach (var view in new[] { 0, 1 })
                    foreach (var t in ts)
                    {
                        pb.SetView(view);
                        pb.ApplyTime(t);
                        pb.ApplyDesktopView();
                        var tex = RT48Capture.RenderCamera(pb.viewCamera, 1920, 1080, 4, caps);
                        var file = Path.Combine(stillDir, string.Format(CultureInfo.InvariantCulture, "synth_seat{0:F0}_{1}_t{2:F3}.png", seat, view == 0 ? "bow" : "crest", t));
                        stills.Add(Stats(tex, file, view == 0 ? "bow" : "crest", t, seat));
                        File.WriteAllBytes(file, tex.EncodeToPNG());
                        UnityEngine.Object.DestroyImmediate(tex);
                    }
            }
            // 低く斜めから（試しのため。頂の 14 m 前・高さ 4 m・Z = 30 m から、頂に沿って唇の下を見る。合成の曲線のかぶさりが 3D で描けているか）
            pb.SetSeat(556.0);
            foreach (var t in new[] { 152.0, src.OnsetS, 155.5, src.ContactS, 157.5 })
            {
                pb.ApplyTime(t);
                var st = src.StateAt(t);
                float crest = (float)(src.Bake.Meta.crest_x_m[st.frame] - pb.SeatX);
                var go = new GameObject("RT48 試しの低い斜めのカメラ");
                var c = go.AddComponent<Camera>();
                c.fieldOfView = 50f; c.nearClipPlane = 0.1f; c.farClipPlane = 25000f; c.clearFlags = CameraClearFlags.Skybox;
                go.transform.position = new Vector3(crest + 14f, 4f, 30f);
                go.transform.LookAt(new Vector3(crest - 2f, 5f, -10f));
                var tex = RT48Capture.RenderCamera(c, 1600, 900, 4, null);
                var file = Path.Combine(stillDir, string.Format(CultureInfo.InvariantCulture, "synth_low_seat556_t{0:F3}.png", t));
                stills.Add(Stats(tex, file, "low", t, 556));
                File.WriteAllBytes(file, tex.EncodeToPNG());
                UnityEngine.Object.DestroyImmediate(tex);
                UnityEngine.Object.DestroyImmediate(go);
            }
            // 端から（試しのため。掃いた面の端 Z = +20,000 m の 30 m 外から −Z を見る。いちばん手前の断面の輪郭で、かぶさりが形として描けているかを見る）
            foreach (var t in new[] { 152.0, src.OnsetS, 155.5, src.ContactS })
            {
                pb.ApplyTime(t);
                var st = src.StateAt(t);
                float crest = (float)(src.Bake.Meta.crest_x_m[st.frame] - pb.SeatX);
                var go = new GameObject("RT48 試しの端のカメラ");
                var c = go.AddComponent<Camera>();
                c.fieldOfView = 40f; c.nearClipPlane = 0.1f; c.farClipPlane = 25000f; c.clearFlags = CameraClearFlags.Skybox;
                go.transform.position = new Vector3(crest - 4f, 5f, RT48Geometry.SweepZ[RT48Geometry.SweepZ.Length - 1] + 30f);
                go.transform.rotation = Quaternion.LookRotation(Vector3.back, Vector3.up);
                var tex = RT48Capture.RenderCamera(c, 1600, 900, 4, null);
                var file = Path.Combine(stillDir, string.Format(CultureInfo.InvariantCulture, "synth_endon_seat556_t{0:F3}.png", t));
                stills.Add(Stats(tex, file, "endon", t, 556));
                File.WriteAllBytes(file, tex.EncodeToPNG());
                UnityEngine.Object.DestroyImmediate(tex);
                UnityEngine.Object.DestroyImmediate(go);
            }
            rep.stills = stills.ToArray();
            bool t10 = stills.All(s => s.stdLum > 0.01 && s.meanLum > 0.02 && s.meanLum < 0.98);
            Add("T10", "静止画（書けた・一色でない）", t10, stills.Count + " 枚：" + stillDir);


            // ---------------- T11 本物の粗い元（Unity/Build/RT48/data/coarse、r_bake.py の manifest.json）
            string coarseDir = Path.Combine(RT48SceneBuilder.DataRoot, "coarse");
            if (RT48Bake.IsBakeDir(coarseDir))
            {
                pb.ReleaseAll();
                pb.Initialize(coarseDir);
                var cs = pb.Source as RecordedSectionSource;
                if (cs == null) { Add("T11a", "粗い元の読み込み", false, "読めない：" + pb.LoadError); }
                else
                {
                    var man = RT48Json.O(RT48Json.Parse(File.ReadAllText(Path.Combine(coarseDir, "manifest.json"), System.Text.Encoding.UTF8)));
                    var mp = RT48Json.A(RT48Json.Get(man, "pairs"));
                    int nInterpMan = mp.Count(q => RT48Json.B(RT48Json.Get(RT48Json.O(q), "interp")));
                    int nInterpU = cs.Bake.Meta.pair_interp.Sum();
                    int kMan = RT48Json.I(RT48Json.Get(RT48Json.GetO(man, "playback"), "K"));
                    int nfMan = RT48Json.I(RT48Json.Get(RT48Json.GetO(man, "time"), "n_frames"));
                    bool t11a = cs.Bake.ShaChecked && cs.Bake.ShaOk && cs.Bake.P == mp.Count && nInterpU == nInterpMan && cs.Bake.Meta.k_frame == kMan && cs.Bake.F == nfMan;
                    Add("T11a", "粗い元の読み込み（manifest.json）", t11a, cs.Describe() + "。manifest：組 " + mp.Count + "・補間する組 " + nInterpMan + "・K " + kMan + "・コマ " + nfMan + "。" + cs.Bake.ShaNote);
                    var boatMan = RT48Json.GetO(man, "boat");
                    var endsOk = true; var endTxt = new List<string>(); var boatTxt = new List<string>();
                    var coarseSeats = new[] { 556.0, 574.0 };
                    foreach (var seat in coarseSeats)
                    {
                        var bo = RT48Json.GetO(boatMan, seat.ToString("F0", CultureInfo.InvariantCulture));
                        pb.SetSeat(seat);
                        double endMan = bo != null ? RT48Json.D(RT48Json.Get(bo, "clip_end_t")) : double.NaN;
                        endsOk &= Math.Abs(pb.TimeEnd - endMan) < 1e-9;
                        endTxt.Add(seat.ToString("F0") + " m：Unity " + pb.TimeEnd.ToString("F4", CultureInfo.InvariantCulture) + "（" + pb.TimeEndFrom + "）・manifest " + endMan.ToString("F4", CultureInfo.InvariantCulture));
                        if (bo != null)
                        {
                            var hm = RT48Json.A(RT48Json.Get(bo, "heave_m")); var pm = RT48Json.A(RT48Json.Get(bo, "pitch_deg"));
                            int kEnd = (int)Math.Round((pb.TimeEnd - cs.TimeFirst) * cs.Fps);
                            double dh = 0, dp = 0; int kh = 0, kp = 0;
                            for (int k = 0; k <= kEnd && k < hm.Count; k++)
                            {
                                double a = Math.Abs(pb.FrameHeave[k] - RT48Json.D(hm[k])), b = Math.Abs(pb.FramePitchDeg[k] - RT48Json.D(pm[k]));
                                if (a > dh) { dh = a; kh = k; }
                                if (b > dp) { dp = b; kp = k; }
                            }
                            boatTxt.Add(seat.ToString("F0") + " m：上下の差の最大 " + dh.ToString("F4", CultureInfo.InvariantCulture) + " m（コマ " + (cs.FrameNumberFirst + kh) + "）・縦揺れ " + dp.ToString("F3", CultureInfo.InvariantCulture) + "°（コマ " + (cs.FrameNumberFirst + kp) + "）");
                        }
                    }
                    Add("T11b", "粗い元の座席の終わり", endsOk, string.Join("、", endTxt));
                    Add("T11c", "粗い元の船（参考、判定しない）", true, string.Join("、", boatTxt) + "。Unity は焼いた 8,192 点の A の線、manifest は焼く前の線から（と読める）");
                    var ctimes = new List<double>();
                    for (int k = 0; k < 20; k++) ctimes.Add(cs.TimeFirst + (cs.TimeLast - cs.TimeFirst) * (k + 0.37) / 20.0);
                    var dc = RT48DecodeCheck.Run(pb.decodeCheck, cs, 556.0, ctimes);
                    rep.decodeCoarse556 = dc;
                    Add("T11d", "粗い元の GPU の読み解き", dc.pass, "位置の差の最大 " + dc.maxPosErr.ToString("E2") + " m（幅に対し " + dc.maxPosErrOverTol.ToString("F3") + "）・法線 " + dc.maxNormDeg.ToString("E2") + "°、20 の時刻 × " + cs.PointCount + " 点");
                    var cdir = Path.Combine(outDir, "stills_coarse");
                    Directory.CreateDirectory(cdir);
                    var cst = new List<Still>();
                    foreach (var seat in coarseSeats)
                    {
                        pb.SetSeat(seat);
                        var ts = new[] { pb.TimeStart, cs.OnsetS, cs.ContactS, pb.TimeEnd };
                        foreach (var view in new[] { 0, 1 })
                            foreach (var t in ts)
                            {
                                pb.SetView(view);
                                pb.ApplyTime(t);
                                pb.ApplyDesktopView();
                                var tex = RT48Capture.RenderCamera(pb.viewCamera, 1920, 1080, 4, caps);
                                var file = Path.Combine(cdir, string.Format(CultureInfo.InvariantCulture, "coarse_seat{0:F0}_{1}_t{2:F3}.png", seat, view == 0 ? "bow" : "crest", t));
                                cst.Add(Stats(tex, file, view == 0 ? "bow" : "crest", t, seat));
                                File.WriteAllBytes(file, tex.EncodeToPNG());
                                UnityEngine.Object.DestroyImmediate(tex);
                            }
                    }
                    pb.SetSeat(556.0);
                    pb.SetView(0);
                    foreach (var t in new[] { 155.5, cs.OnsetS, cs.ContactS })
                    {
                        pb.ApplyTime(t);
                        var st = cs.StateAt(t);
                        float crest = (float)(cs.Bake.Meta.crest_x_m[st.frame] - pb.SeatX);
                        var go = new GameObject("RT48 試しの端のカメラ（粗い元）");
                        var c = go.AddComponent<Camera>();
                        c.fieldOfView = 40f; c.nearClipPlane = 0.1f; c.farClipPlane = 25000f; c.clearFlags = CameraClearFlags.Skybox;
                        go.transform.position = new Vector3(crest - 4f, 5f, RT48Geometry.SweepZ[RT48Geometry.SweepZ.Length - 1] + 30f);
                        go.transform.rotation = Quaternion.LookRotation(Vector3.back, Vector3.up);
                        var tex = RT48Capture.RenderCamera(c, 1600, 900, 4, null);
                        var file = Path.Combine(cdir, string.Format(CultureInfo.InvariantCulture, "coarse_endon_seat556_t{0:F3}.png", t));
                        cst.Add(Stats(tex, file, "endon", t, 556));
                        File.WriteAllBytes(file, tex.EncodeToPNG());
                        UnityEngine.Object.DestroyImmediate(tex);
                        UnityEngine.Object.DestroyImmediate(go);
                    }
                    rep.stillsCoarse = cst.ToArray();
                    Add("T11e", "粗い元の静止画", cst.All(s => s.stdLum > 0.01 && s.meanLum > 0.02 && s.meanLum < 0.98), cst.Count + " 枚：" + cdir);
                }
            }
            else Debug.Log("RT48_CHECK T11 粗い元がまだない：" + coarseDir);

            pb.ReleaseAll();
            rep.checks = checks.ToArray();
            rep.pass = checks.All(c => c.pass);
            rep.noteJa = "合成の曲線（u_synth.py、式で作った作り物）で Unity の部品を確かめた。見た目と数は FLIP42 の結果ではない。場面は保存した後に開いたまま試し、試しの後は保存していない。";
            File.WriteAllText(Path.Combine(outDir, "selftest_synth.json"), JsonUtility.ToJson(rep, true));
            Debug.Log("RT48_SELFTEST pass=" + rep.pass + " checks=" + string.Join(",", checks.Select(c => c.id + (c.pass ? ":ok" : ":NG"))));
            return rep;
        }

        static Still Stats(Texture2D tex, string file, string view, double t, double seat)
        {
            var px = tex.GetPixels32();
            double sum = 0, sum2 = 0; int sky = 0;
            for (int i = 0; i < px.Length; i += 7)
            {
                double l = (0.2126 * px[i].r + 0.7152 * px[i].g + 0.0722 * px[i].b) / 255.0;
                sum += l; sum2 += l * l;
                if (px[i].b > 150 && px[i].r > 100) sky++;
            }
            int m = (px.Length + 6) / 7;
            double mean = sum / m;
            return new Still { file = Path.GetFileName(file), view = view, t = t, seat = seat, meanLum = mean, stdLum = Math.Sqrt(Math.Max(0, sum2 / m - mean * mean)), skyFrac = (double)sky / m };
        }

        static bool WindingCheck(RT48Playback pb, out string detail)
        {
            var src = pb.Source;
            int n = src.PointCount;
            var raw = new double[2 * n]; var disp = new double[2 * n];
            src.FillCurve(pb.State, raw);
            RT48BoatMotion.ToDisplayed(raw, n, src.TaperStored, disp);
            double shift = pb.XShift;
            var mesh = pb.sweepFilter.sharedMesh;
            var uv = mesh.uv; var vz = mesh.vertices; var tri = mesh.triangles;
            Vector3d P(int v) { int i = (int)(uv[v].x + 0.5); return new Vector3d(disp[2 * i] + shift, disp[2 * i + 1], vz[v].z); }
            int bad = 0, degenerate = 0, total = 0;
            for (int t = 0; t < tri.Length; t += 3)
            {
                var a = P(tri[t]); var b = P(tri[t + 1]); var c = P(tri[t + 2]);
                var nrm = Vector3d.Cross(b - a, c - a);
                // 三角形の中の曲線の線分（同じ j の 2 点）の左の法線
                int ia = (int)(uv[tri[t]].x + 0.5), ib = (int)(uv[tri[t + 1]].x + 0.5), ic = (int)(uv[tri[t + 2]].x + 0.5);
                int i0 = Math.Min(ia, Math.Min(ib, ic)), i1 = Math.Max(ia, Math.Max(ib, ic));
                double tx = disp[2 * i1] - disp[2 * i0], ty = disp[2 * i1 + 1] - disp[2 * i0 + 1];
                double len = Math.Sqrt(tx * tx + ty * ty);
                total++;
                if (len < 1e-9 || nrm.Length < 1e-12) { degenerate++; continue; }
                if (nrm.x * (-ty) + nrm.y * tx <= 0) bad++;
            }
            // 海：表が上
            var sea = pb.seaFilter.sharedMesh; var sv = sea.vertices; var st = sea.triangles; int seaBad = 0;
            for (int t = 0; t < st.Length; t += 3) if (Vector3.Cross(sv[st[t + 1]] - sv[st[t]], sv[st[t + 2]] - sv[st[t]]).y <= 0) seaBad++;
            // 離れた水：156.0 s の管の表が外（その輪の真ん中から離れる向き）
            pb.ApplyTime(156.0);
            var lm = pb.loopsFilter.sharedMesh; var lv = lm.vertices; var lt = lm.triangles; int loopBad = 0;
            var lnrm = lm.normals;
            for (int t = 0; t < lt.Length; t += 3)
            {
                var nrm = Vector3.Cross(lv[lt[t + 1]] - lv[lt[t]], lv[lt[t + 2]] - lv[lt[t]]);
                var navg = lnrm[lt[t]] + lnrm[lt[t + 1]] + lnrm[lt[t + 2]];
                if (nrm.sqrMagnitude > 1e-12 && Vector3.Dot(nrm, navg) <= 0) loopBad++;
            }
            detail = "掃いた面 " + total + " 三角形のうち裏向き " + bad + "（長さ 0 " + degenerate + "）、海 " + (st.Length / 3) + " のうち " + seaBad + "、離れた水 " + (lt.Length / 3) + " のうち三角形の表と点の法線（外向き）が逆 " + loopBad;
            return bad == 0 && seaBad == 0 && loopBad == 0 && lt.Length > 0;
        }

        struct Vector3d
        {
            public double x, y, z;
            public Vector3d(double x, double y, double z) { this.x = x; this.y = y; this.z = z; }
            public static Vector3d operator -(Vector3d a, Vector3d b) => new Vector3d(a.x - b.x, a.y - b.y, a.z - b.z);
            public static Vector3d Cross(Vector3d a, Vector3d b) => new Vector3d(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
            public double Length => Math.Sqrt(x * x + y * y + z * z);
        }

        // ---------------------------------------------------------------- T1 シェーダー
        static string[] ShaderCheck()
        {
            var lines = new List<string>();
            bool ok = true;
            var sets = new[] { new string[0], new[] { "INSTANCING_ON" }, new[] { "STEREO_INSTANCING_ON", "INSTANCING_ON" } };
            foreach (var name in new[] { "GreatWave/RT48/Water", "GreatWave/RT48/Sky", "GreatWave/RT48/Overlay" })
            {
                var sh = Shader.Find(name);
                if (sh == null || ShaderUtil.ShaderHasError(sh)) { ok = false; lines.Add(name + " 見つからないか誤りあり"); continue; }
                var data = ShaderUtil.GetShaderData(sh);
                for (int s = 0; s < data.SubshaderCount; s++)
                {
                    var sub = data.GetSubshader(s);
                    for (int p = 0; p < sub.PassCount; p++)
                    {
                        var pass = sub.GetPass(p);
                        var extra = name.EndsWith("Water") ? new[] { new string[0], new[] { "RT48_SWEEP" } } : new[] { new string[0] };
                        foreach (var ex in extra)
                            foreach (var kw0 in sets)
                            {
                                var kw = kw0.Concat(ex).ToArray();
                                foreach (var stg in new[] { ShaderType.Vertex, ShaderType.Fragment })
                                {
                                    if (!pass.HasShaderStage(stg)) continue;
                                    var info = pass.CompileVariant(stg, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64);
                                    bool rtai = true;
                                    if (stg == ShaderType.Vertex && kw.Contains("STEREO_INSTANCING_ON"))
                                    {
                                        var pre = pass.PreprocessVariant(stg, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64, true);
                                        var code = pre.Success ? (pre.PreprocessedCode ?? "") : "";
                                        var vm = Regex.Match(code, @"#pragma\s+vertex\s+(\w+)");
                                        string fn = vm.Success ? vm.Groups[1].Value : "vert";
                                        var fm = Regex.Match(code, @"(\w+)\s+" + Regex.Escape(fn) + @"\s*\(");
                                        var sm = fm.Success ? Regex.Match(code, @"struct\s+" + Regex.Escape(fm.Groups[1].Value) + @"\s*\{([^}]*)\}") : Match.Empty;
                                        rtai = sm.Success && sm.Groups[1].Value.Contains("SV_RenderTargetArrayIndex");
                                    }
                                    bool good = info.Success && rtai;
                                    ok &= good;
                                    lines.Add(name + " [" + string.Join(" ", kw) + "] " + stg + " " + (info.Success ? "ok" : "NG") + (stg == ShaderType.Vertex && kw.Contains("STEREO_INSTANCING_ON") ? (rtai ? " 眼のスライスの出力あり" : " 眼のスライスの出力なし") : "") +
                                              (info.Success ? "" : " " + string.Join(" | ", info.Messages.Select(m => m.message))));
                                }
                            }
                    }
                }
            }
            var cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(RT48SceneBuilder.ShaderDir + "/RT48DecodeCheck.compute");
            var msgs = cs != null ? ShaderUtil.GetComputeShaderMessages(cs) : null;
            bool csOk = cs != null && (msgs == null || !msgs.Any(m => m.severity == ShaderCompilerMessageSeverity.Error));
            ok &= csOk;
            lines.Add("RT48DecodeCheck.compute " + (csOk ? "ok" : "NG " + (msgs == null ? "" : string.Join(" | ", msgs.Select(m => m.message)))));
            Add("T1", "シェーダーのコンパイルと single-pass instanced の出力", ok, lines.Count + " の組み合わせ");
            return lines.ToArray();
        }
    }
}
