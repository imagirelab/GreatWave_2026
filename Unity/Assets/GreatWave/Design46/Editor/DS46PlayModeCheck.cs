using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design31;
using GreatWave.Design34;
using GreatWave.Design46;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Design46.EditorTools
{
    // 設計46：保存した DS46_Clock.unity を Editor の Play モードで再生し、実際の実行の道（GWClock が EarlyUpdate で進め、段を順に呼ぶ）で確かめる。
    //   ・毎フレーム：時計の状態・体験の時刻・大波の時刻、各層が受け取った時刻（再生器の t と τ、爪・飛沫の t、船用水面データの τ）、
    //     全段が同じ時刻の決定を受けたか、物理の段（FixedUpdate の検査の部品 DS46FixedProbe）が読んだ水の τ と、そのフレームに描く水の τ。
    //   ・台本（体験の時刻で）：5 s で停止 → 20 フレーム止めたまま（時刻と形が変わらない）→ 再開 → 8.4 s で停止して 8.0 へ Seek（ハッシュ）→ 再開
    //     → 10.9 s で初期化（ハッシュ）→ 8.0 へ Seek（ハッシュ）→ 12.0 へ Seek（ハッシュ）→ 3.0 へ Seek して再開（途中からの再生）
    //     → 途中の 60 フレームだけ advanceBeforePhysics を切り（時計を Update で進める対照。物理が 1 コマ前の水を読むはず）→ 戻す
    //     → 終わり（14 s）まで → 12.0・8.0 へ Seek、初期化（ハッシュ）。
    //   ハッシュは形のデータ（シートの GPU の読み戻し・白の旗・爪・飛沫・船用水面データ・通過した出来事）。Editor の検査（DS46ClockTest）の基準と、記録の道具で比べる。
    // 実行：run_ds46_unity.ps1 -NoQuit -Method GreatWave.Design46.EditorTools.DS46PlayModeCheck.Run -Log playmode
    // batchmode ではプレイヤーのループが自分で回らないので、EditorApplication.update ごとに QueuePlayerLoopUpdate で 1 フレームずつ回す（設計34 と同じ）。
    [InitializeOnLoad]
    public static class DS46PlayModeCheck
    {
        const string Key = "DS46PlayModeCheck";
        const string OutDefault = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/46/clock/playmode";
        static readonly List<string> rows = new List<string>();
        static readonly List<string> hashes = new List<string>();
        static int lastFrame = -1, polls = 0, stage = 0, stopFrames = 0, controlFrames = 0;
        static double tStop = double.NaN; static long idxStop = -1;
        static SortedDictionary<string, string> hStopA;
        static DS46Probe probe;
        static DS46FixedProbe fixedProbe;
        static readonly List<string> notes = new List<string>();

        static DS46PlayModeCheck()
        {
            if (SessionState.GetBool(Key + ".active", false)) EditorApplication.update += Poll;
        }

        public static void Run()
        {
            var a = Environment.GetCommandLineArgs();
            string od = OutDefault;
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == "-ds46Out") od = a[i + 1];
            Directory.CreateDirectory(od);
            EditorSceneManager.OpenScene(DS46ClockTest.Scene46, OpenSceneMode.Single);
            SessionState.SetBool(Key + ".active", true);
            SessionState.SetString(Key + ".out", Path.GetFullPath(od));
            SessionState.SetFloat(Key + ".start", (float)EditorApplication.timeSinceStartup);
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static void Hash(string label, GWClock clk)
        {
            var h = probe.All();
            hashes.Add("{\"label\":\"" + label + "\",\"frame\":" + Time.frameCount + ",\"exp\":" + DS46Probe.F(clk.ExperienceSeconds) + ",\"wave\":" + DS46Probe.F(clk.WaveSeconds) +
                       ",\"step\":" + clk.StepIndex + ",\"state\":\"" + clk.State + "\",\"h\":" + DS46Probe.J(h) + "}");
            if (label == "stop_a") hStopA = h;
            if (label == "stop_b") notes.Add("stop_same_shape=" + (hStopA != null && hStopA.All(kv => h[kv.Key] == kv.Value) ? "true" : "false"));
        }

        static void Poll()
        {
            double now = EditorApplication.timeSinceStartup;
            double start = SessionState.GetFloat(Key + ".start", (float)now);
            string od = SessionState.GetString(Key + ".out", "");
            if (now - start > 600) { Finish(od, "打ち切り（600 s）", 2); return; }
            if (!EditorApplication.isPlaying) return;
            if (!Application.runInBackground) Application.runInBackground = true;
            EditorApplication.QueuePlayerLoopUpdate();
            polls++;
            if (Time.frameCount == lastFrame)
            {
                if (polls > 50) { if (!EditorApplication.isPaused) EditorApplication.isPaused = true; EditorApplication.Step(); }
                return;
            }
            lastFrame = Time.frameCount;
            var bus = UnityEngine.Object.FindFirstObjectByType<DS46ClockBus>();
            if (bus == null || !bus.Ready) return;
            var clk = bus.clock;
            if (probe == null)
            {
                probe = new DS46Probe(bus);
                var go = new GameObject("DS46 検査の部品（保存しない）") { hideFlags = HideFlags.DontSave };
                fixedProbe = go.AddComponent<DS46FixedProbe>();
                fixedProbe.clock = clk; fixedProbe.playback = bus.playback; fixedProbe.boatWater = bus.boatWater;
                notes.Add("fixedDeltaTime=" + Time.fixedDeltaTime.ToString("R", CultureInfo.InvariantCulture) + " captureDeltaTime=" + Time.captureDeltaTime.ToString("R", CultureInfo.InvariantCulture));
            }
            var st = clk.LastStep;
            int bad = 0;
            foreach (var kv in clk.StageLast) if (kv.Value.index != st.index) bad++;
            var pb = bus.playback;
            if (pb.T != st.wave) bad++;
            if (bus.claws.AppliedT != st.wave) bad++;
            foreach (var s in bus.sprays) if (s.AppliedT != st.wave) bad++;
            if (bus.boatWater.TauUsed != pb.Tau) bad++;
            foreach (var s in pb.sheets) if (s != null && s.AppliedTau != pb.Tau) bad++;
            bool fixedThisFrame = fixedProbe != null && fixedProbe.LastFixedFrame == Time.frameCount;
            string lag = fixedThisFrame ? (fixedProbe.LastFixedTau == pb.Tau ? "0" : "1") : "";
            rows.Add(string.Join(",", Time.frameCount.ToString(), Time.deltaTime.ToString("R", CultureInfo.InvariantCulture), clk.State.ToString(), clk.advanceBeforePhysics ? "1" : "0",
                DS46Probe.F(clk.ExperienceSeconds), DS46Probe.F(clk.WaveSeconds), clk.StepIndex.ToString(), clk.EarlyTicks.ToString(), st.kind.ToString(),
                DS46Probe.F(pb.T), DS46Probe.F(pb.Tau), DS46Probe.F(bus.claws.AppliedT), DS46Probe.F(bus.sprays[0].AppliedT), DS46Probe.F(bus.boatWater.TauUsed),
                bad.ToString(), fixedThisFrame ? "1" : "0", fixedProbe != null ? fixedProbe.FixedThisFrame.ToString() : "", DS46Probe.F(fixedProbe != null ? fixedProbe.LastFixedTau : double.NaN), lag,
                bus.events.FiredCount.ToString(), bus.events.SkippedCount.ToString(), stage.ToString()));

            double t = clk.ExperienceSeconds;
            switch (stage)
            {
                case 0: if (t >= 5.0) { clk.Stop(); tStop = t; idxStop = clk.StepIndex; Hash("stop_a", clk); stage = 1; } break;
                case 1:
                    stopFrames++;
                    if (stopFrames >= 20)
                    {
                        notes.Add("stop_held=" + (clk.ExperienceSeconds == tStop && clk.StepIndex == idxStop ? "true" : "false") + " tStop=" + DS46Probe.F(tStop) + " frames=" + stopFrames);
                        Hash("stop_b", clk); clk.Resume(); stage = 2;
                    }
                    break;
                case 2: if (t >= 8.4) { clk.Stop(); clk.Seek(8.0); Hash("seek8_after_play", clk); clk.Resume(); stage = 3; } break;
                case 3:
                    if (t >= 10.9)
                    {
                        clk.Initialise(); Hash("init_a", clk);
                        clk.Seek(8.0); Hash("seek8_after_init", clk);
                        clk.Seek(12.0); Hash("seek12_a", clk);
                        clk.Seek(3.0); clk.Resume(); stage = 4;
                    }
                    break;
                case 4: if (t >= 6.0) { clk.advanceBeforePhysics = false; stage = 5; } break;   // 対照：Update で進める
                case 5: controlFrames++; if (controlFrames >= 60) { clk.advanceBeforePhysics = true; stage = 6; } break;
                case 6:
                    if (clk.Ended)
                    {
                        Hash("end14", clk);
                        clk.Seek(12.0); Hash("seek12_b", clk);
                        clk.Seek(8.0); Hash("seek8_after_end", clk);
                        clk.Initialise(); Hash("init_b", clk);
                        Finish(od, "台本の終わり", 0);
                    }
                    break;
            }
        }

        static void Finish(string od, string why, int code)
        {
            EditorApplication.update -= Poll;
            SessionState.EraseBool(Key + ".active");
            if (!string.IsNullOrEmpty(od))
            {
                var sb = new StringBuilder("frame,deltaTime,state,advance_before_physics,exp,wave,step,early_ticks,step_kind,pb_t,pb_tau,claw_t,spray_t,boat_tau,sync_bad,fixed_this_frame,fixed_count_this_frame,fixed_tau,fixed_lag_frames,events_fired,events_skipped,stage\n");
                foreach (var r in rows) sb.AppendLine(r);
                File.WriteAllText(Path.Combine(od, "ds46_playmode.csv"), sb.ToString());
                var j = new StringBuilder("{\"schema\":\"GreatWave.DS46.playmode/1\",\"why\":\"").Append(why).Append("\",\"rows\":").Append(rows.Count)
                    .Append(",\"notes\":[").Append(string.Join(",", notes.Select(n => "\"" + n + "\""))).Append("],\"hashes\":[").Append(string.Join(",", hashes)).Append("]}");
                File.WriteAllText(Path.Combine(od, "ds46_playmode.json"), j.ToString(), new UTF8Encoding(false));
            }
            probe?.Dispose(); probe = null;
            UnityEngine.Debug.Log("DS46_PLAYMODE_DONE " + why + " rows=" + rows.Count);
            EditorApplication.Exit(code);
        }
    }
}
