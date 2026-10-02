using System;
using System.Reflection;
using GreatWave.Design34;
using GreatWave.Design38;
using GreatWave.Design46;
using GreatWave.Polish32;
using UnityEngine;

namespace GreatWave.Polish35
{
    // 仕上げ35 修正の回 1：爪の縁の線（DS38ClawOutline）の毎コマの写しから、配列の写し（DS34ClawPlayer.Current＝104,707 頂点 × 12 バイト ≈ 1.26 MB の
    // 新しい配列を毎コマ作る）をなくす。負荷の計測器（PL35PerfProbe）で、最大密度の区間の爪の段は CPU の主スレッドで約 3 ms、そのうえ毎コマ 1.26 MB の
    // ごみが出て、船用水面データの作り直しを止めた見込みの速さ（約 290 fps）では 8 秒に 110 回のごみ集めが起きていた（爪の段を切ると 1 回）。
    //  ・共通時計の "claws" の段（仕上げ32 の PL32ClawDriver が登録したもの）を、同じ規則（爪の時刻のコマの位置が前と同じなら何もしない、
    //    前も今も全部の爪が見えないなら何もしない）の段で置き換え、縁の線は DS34ClawPlayer の今の頂点の配列（非公開の now）をそのまま
    //    SetVertices へ渡す。法線は今までと同じ Mesh.RecalculateNormals。頂点・三角形・法線は DS38ClawOutline.Sync と同じ値になる（SelfCheck で確かめる）。
    //  ・DS38ClawOutline.SyncedT も同じ値に保つ（設計46 の検査が読む）。
    //  ・起動引数 --pl35legacy のときは何もしない（仕上げ33修正01 と同じ道。前と後を同じ exe で交互に測るため）。
    // 見え方は変えない。DS34ClawPlayer・DS38ClawOutline・PL32ClawDriver のファイルは変えない。
    [DefaultExecutionOrder(62)]   // PL32ClawDriver（61）の Start が段を登録した後に置き換える
    public class PL35ClawOutlineFast : MonoBehaviour
    {
        public DS34ClawPlayer claws;
        public DS38ClawOutline outline;
        public PL32ClawDriver driver;

        public bool Active { get; private set; }
        public int Applies { get; private set; }
        public int Skips { get; private set; }

        static readonly FieldInfo NowField = typeof(DS34ClawPlayer).GetField("now", BindingFlags.NonPublic | BindingFlags.Instance);
        Action<double> setSyncedT;
        bool[] anyVisible;
        double lastX = double.NaN;
        Mesh lineMesh;

        public static bool Legacy => Array.IndexOf(Environment.GetCommandLineArgs(), "--pl35legacy") >= 0;

        void Start()
        {
            if (!Application.isPlaying) return;
            if (Legacy) { enabled = false; Debug.Log("PL35_CLAW_OUTLINE_FAST legacy（仕上げ33修正01 の道）"); return; }
            if (claws == null) claws = GetComponent<DS34ClawPlayer>();
            if (outline == null) outline = GetComponent<DS38ClawOutline>();
            if (driver == null) driver = GetComponent<PL32ClawDriver>();
            if (claws == null || outline == null || NowField == null) { enabled = false; return; }
            var bus = FindAnyObjectByType<DS46ClockBus>();
            if (bus == null || bus.claws != claws || bus.clock == null) { enabled = false; return; }   // 共通時計のない場面では仕上げ32 の道のまま
            claws.Load();
            claws.followClockInPlayMode = false;
            outline.syncInPlayMode = false;
            var pi = typeof(DS38ClawOutline).GetProperty("SyncedT");
            var setter = pi != null ? pi.GetSetMethod(true) : null;
            if (setter != null) setSyncedT = (Action<double>)Delegate.CreateDelegate(typeof(Action<double>), outline, setter);
            anyVisible = new bool[claws.Frames];
            for (int k = 0; k < claws.Frames; k++)
                for (int i = 0; i < claws.ClawCount && !anyVisible[k]; i++)
                {
                    int o = claws.VertOffset[i];
                    if ((claws.FrameVertex(k, o + 1) - claws.FrameVertex(k, o)).sqrMagnitude > 1e-12f) anyVisible[k] = true;
                }
            if (driver != null) driver.enabled = false;   // 仕上げ32 の Update・LateUpdate（共通時計がある場面では何もしない）も止める
            bus.clock.Register("claws", DS46ClockBus.OrderClaws, (c, st) => Step(st.wave));
            Active = true;
            Debug.Log("PL35_CLAW_OUTLINE_FAST active frames=" + claws.Frames + " vertices=" + claws.VertexCount);
        }

        public void Step(double t)
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
            FastSync();
        }

        /// <summary>DS38ClawOutline.Sync と同じ仕事を、頂点の配列を写さずに行う。</summary>
        public void FastSync()
        {
            if (claws == null || !claws.Loaded || outline.Line == null) return;
            var mf = outline.Line.GetComponent<MeshFilter>();
            if (lineMesh == null || mf.sharedMesh != lineMesh)
            {
                if (mf.sharedMesh == null || mf.sharedMesh.vertexCount != claws.VertexCount) { outline.Sync(); }   // 初めは DS38 が線のメッシュを作る
                lineMesh = mf.sharedMesh;
                return;
            }
            var now = (Vector3[])NowField.GetValue(claws);
            lineMesh.SetVertices(now);
            lineMesh.RecalculateNormals();
            lineMesh.bounds = new Bounds(Vector3.zero, Vector3.one * 2000f);
            var cr = claws.GetComponent<MeshRenderer>();
            outline.Line.enabled = cr != null && cr.enabled && claws.gameObject.activeInHierarchy;
            setSyncedT?.Invoke(claws.AppliedT);
        }

        /// <summary>検査：時刻 t で、DS38ClawOutline.Sync と FastSync の線のメッシュの頂点・法線の差の最大（同じなら 0）。</summary>
        public Vector2 SelfCheck(double t)
        {
            claws.ApplyT(t);
            outline.Sync();
            var m = outline.Line.GetComponent<MeshFilter>().sharedMesh;
            var v0 = m.vertices; var n0 = m.normals;
            lineMesh = m;
            FastSync();
            var v1 = m.vertices; var n1 = m.normals;
            float dv = 0f, dn = 0f;
            for (int i = 0; i < v0.Length; i++) { dv = Mathf.Max(dv, (v0[i] - v1[i]).magnitude); dn = Mathf.Max(dn, (n0[i] - n1[i]).magnitude); }
            return new Vector2(dv, dn);
        }
    }
}
