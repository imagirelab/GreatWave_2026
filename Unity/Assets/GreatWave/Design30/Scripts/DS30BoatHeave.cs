using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using GreatWave.Design27;
using UnityEngine;

namespace GreatWave.Design30
{
    // 設計30：座席の船（boat_mid）の鉛直の支え。第A部の boat_support.json の Δ（竜骨の線の下の水面の t* からの差、0.1 s でならしたもの。
    // t* で 0）で、船と座席のカメラ（乗る物）を t* の姿勢のまま鉛直だけ上下させる。DS30SinglePlayback が毎コマ Apply(t, τ) を呼ぶ。
    // 表のキーは版で変わりうるので候補から探す：時刻 t（体験の秒）か tau（物理の秒）、Δ は delta_m・boat_dy_m・dy_m・heave_m・delta。
    // 配列か、frames（要素が {t, tau, delta_m, …}）のどちらでもよい。基準の位置は Load の時の位置（t* の姿勢）。
    public class DS30BoatHeave : MonoBehaviour
    {
        [Tooltip("boat_support.json（Unity プロジェクトからの相対パスか絶対パス）")]
        public string supportPath = "Build/Design/30/sea/boat_support.json";
        public Transform boat;
        [Tooltip("船と一緒に上下させる物（座席のカメラ・XR の原点など）")]
        public List<Transform> riders = new List<Transform>();

        static readonly string[] DeltaKeys = { "delta_m", "boat_dy_m", "dy_m", "heave_m", "delta", "Delta_m" };
        double[] x, dy;
        Vector3 boatPos0;
        Vector3[] riderPos0;
        bool loaded;
        public bool ByTau { get; private set; }
        public string Mode { get; private set; } = "";
        public double CurrentDelta { get; private set; }
        public string FullPath => Path.GetFullPath(supportPath);

        public void Load()
        {
            if (loaded) return;
            var r = DS27Json.AsObj(DS27Json.Parse(File.ReadAllText(FullPath)), "boat_support.json");
            string keyTime, keyDelta;
            List<object> rows = null;
            foreach (var k in new[] { "frames", "track", "rows" }) if (DS27Json.Has(r, k) && DS27Json.Get(r, k) is List<object> l) { rows = l; break; }
            if (rows != null && rows.Count > 0 && rows[0] is Dictionary<string, object> f0)
            {
                keyTime = f0.ContainsKey("t") ? "t" : "tau";
                keyDelta = DeltaKeys.First(k => f0.ContainsKey(k));
                x = rows.Select(o => DS27Json.Num((Dictionary<string, object>)o, keyTime)).ToArray();
                dy = rows.Select(o => DS27Json.Num((Dictionary<string, object>)o, keyDelta)).ToArray();
            }
            else
            {
                keyTime = DS27Json.Has(r, "t") ? "t" : "tau";
                keyDelta = DeltaKeys.FirstOrDefault(k => DS27Json.Has(r, k));
                if (keyDelta == null) throw new InvalidDataException("boat_support.json に Δ の配列がありません（鍵：" + string.Join(",", r.Keys) + "）");
                x = DS27Json.Nums(DS27Json.Get(r, keyTime), keyTime);
                dy = DS27Json.Nums(DS27Json.Get(r, keyDelta), keyDelta);
            }
            ByTau = keyTime == "tau";
            // 単調増加にそろえ、同じ値が続く所（t* の後の τ = 0 など）は最初だけ残す
            var pairs = x.Select((v, i) => new KeyValuePair<double, double>(v, dy[i])).OrderBy(p => p.Key).ToList();
            var ux = new List<double>(); var uy = new List<double>();
            foreach (var p in pairs) if (ux.Count == 0 || p.Key > ux[ux.Count - 1]) { ux.Add(p.Key); uy.Add(p.Value); }
            x = ux.ToArray(); dy = uy.ToArray();
            Mode = keyTime + " → " + keyDelta + "（" + x.Length + " 点）";
            if (boat != null) boatPos0 = boat.position;
            riderPos0 = riders.Select(t => t != null ? t.position : Vector3.zero).ToArray();
            loaded = true;
        }

        public double DeltaAt(double t, double tau)
        {
            Load();
            double q = ByTau ? tau : t;
            int n = x.Length;
            if (q <= x[0]) return dy[0];
            if (q >= x[n - 1]) return dy[n - 1];
            int i = Array.BinarySearch(x, q);
            if (i >= 0) return dy[i];
            i = ~i - 1;
            double s = (q - x[i]) / (x[i + 1] - x[i]);
            return dy[i] + s * (dy[i + 1] - dy[i]);
        }

        public void Apply(double t, double tau)
        {
            Load();
            CurrentDelta = DeltaAt(t, tau);
            var up = Vector3.up * (float)CurrentDelta;
            if (boat != null) boat.position = boatPos0 + up;
            for (int i = 0; i < riders.Count; i++) if (riders[i] != null) riders[i].position = riderPos0[i] + up;
        }
    }
}
