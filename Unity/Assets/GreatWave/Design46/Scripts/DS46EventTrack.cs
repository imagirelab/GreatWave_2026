using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using GreatWave.ArtFirst;
using GreatWave.Design27;
using UnityEngine;

namespace GreatWave.Design46
{
    // 設計46：演出の出来事の表（GreatWave.DS46.events/1）を共通時計（GWClock、Master）で進める。
    //   ・時計を進めた段（StepKind.Advance）で、前の時刻 < 出来事の時刻 ≤ 今の時刻 のものを時刻の順に一度だけ起こす（Fired）。
    //     起こすのは時刻をまたいだそのコマ（音・演出が見た目より遅れない。遅れ = 今の時刻 − 出来事の時刻 < 1 コマ）。
    //   ・初期化・途中からの再生（Seek）で跳んだときは起こさない。出来事の時刻 ≤ 今の時刻 のものを「通過」に数え直すだけ（Skipped）。
    //     後ろへ跳べば、その後の出来事はまた起こせる状態に戻る。通過の集合は時刻だけで決まる（どの道を通っても同じ時刻なら同じ）。
    //   ・中身の表は設計47 の絵コンテで置き換える（設計46 は仕組みと仮の 3 つだけ）。
    public class DS46EventTrack : MonoBehaviour
    {
        [Serializable]
        public class Entry { public string id; public double t; public string kind = "once"; }

        public struct Record { public string id; public double eventT; public double clockT; public long stepIndex; public bool fired; }

        [Tooltip("出来事の表（Unity プロジェクトからの相対パスか絶対パス）")]
        public string tablePath = "Assets/GreatWave/Design46/Data/ds46_events.json";

        public readonly List<Entry> entries = new List<Entry>();
        public readonly List<Record> log = new List<Record>();
        public event Action<Entry, GWClock.Step> Fired;
        public bool Loaded { get; private set; }
        public int FiredCount { get; private set; }
        public int SkippedCount { get; private set; }

        public void Load()
        {
            if (Loaded) return;
            var root = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(Path.GetFullPath(tablePath))), "events");
            if (DS27Json.Text(root, "schema") != "GreatWave.DS46.events/1") throw new InvalidDataException("出来事の表の書式ではありません: " + tablePath);
            var list = DS27Json.Get(root, "events") as IList;
            if (list == null) throw new InvalidDataException("events がありません");
            entries.Clear();
            foreach (var o in list)
            {
                var e = DS27Json.AsObj(o, "event");
                entries.Add(new Entry { id = DS27Json.Text(e, "id"), t = DS27Json.Num(e, "t"), kind = DS27Json.Has(e, "kind") ? DS27Json.Text(e, "kind") : "once" });
            }
            entries.Sort((a, b) => a.t.CompareTo(b.t));
            Loaded = true;
        }

        /// <summary>今の時刻で通過している出来事（時刻 ≤ t）の id を時刻の順に。</summary>
        public string PassedAt(double t)
        {
            var sb = new System.Text.StringBuilder();
            foreach (var e in entries) if (e.t <= t) { if (sb.Length > 0) sb.Append('|'); sb.Append(e.id); }
            return sb.ToString();
        }

        /// <summary>共通時計の段（GWClock.Register で登録する）。</summary>
        public void OnClock(GWClock clock, GWClock.Step st)
        {
            if (!Loaded) Load();
            if (st.kind == GWClock.StepKind.Advance)
            {
                foreach (var e in entries)
                {
                    if (e.t > st.previous && e.t <= st.experience)
                    {
                        FiredCount++;
                        log.Add(new Record { id = e.id, eventT = e.t, clockT = st.experience, stepIndex = st.index, fired = true });
                        Fired?.Invoke(e, st);
                    }
                }
            }
            else
            {
                foreach (var e in entries)
                {
                    // 跳んだ区間に入った出来事は起こさず、通過として記録する（前へ跳んだときだけ）
                    if (st.experience > st.previous && e.t > st.previous && e.t <= st.experience)
                    {
                        SkippedCount++;
                        log.Add(new Record { id = e.id, eventT = e.t, clockT = st.experience, stepIndex = st.index, fired = false });
                    }
                }
            }
        }
    }
}
