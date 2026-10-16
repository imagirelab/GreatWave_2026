using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace GreatWave.FLIP3D
{
    // FLIP3D：DA3（周期のうねり・粒子 0.5 m）の 12 s の繰り返しを実時間で再生し、船の座席と原画の視点を見せる最小の場面（2026-10-16、進行役）。
    // 再生の決まり（形を変えない）：
    //   - 面の記録は 3 コマおき（8 個/s）。時計の時刻 → 繰り返しの中の位相 φ → その時刻以前の最後の記録（floor(φ × 8)）を見せる。
    //     コマの間の形は作らない（補間・速さでずらす・平滑をしない）。24 fps の動画では各記録が 3 フレーム続く。
    //   - 横：記録は半分の水槽（横 0〜85 m、y = 0 は対称の面）。同じ Mesh を z → −z の変換でもう一度描いて全幅にする（計算の対称の仮定）。
    //     tilesPerSide > 0 なら、y = 85 m の壁で写して 170 m ごとに並べる（壁は鏡と同じなので、計算はこの並びの海と同じ）。
    //   - 船の上下：記録 hf（上の水面の高さ、毎コマ 24 個/s）の座席の足跡の平均（f3d_export.py）。この数だけは時刻で 1 次の補間をする（カメラの高さ）。
    //   - 計算にない物：水槽の外の平らな海（静かな水面の高さ）、霧、空、海底の色。
    // 視点：Seat（船の座席）・Print（原画の視点：真ん中の断面を横から）・Move（座席 → 見える動き → 原画に最も近い瞬間に原画の視点に着く → 止め）。
    public class FLIP3DPlayer : MonoBehaviour
    {
        public enum Mode { Seat, Print, Move }

        [Header("データ（f3d_export.py の出力）")]
        public string dataDir = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP3D/clip_DA3_k5";
        public Material waterMaterial, bedMaterial, seaMaterial;
        public int tilesPerSide = 1;
        public int maxTiles = 1;
        public float outerSeaHalfSize = 4000f;

        [Header("視点")]
        public Camera cam;
        public Mode mode = Mode.Move;
        public float seatFovV = 55f;
        public Vector3 seatLookAt = new Vector3(274f, 3.0f, 0f);
        public Vector3 printPos = new Vector3(284f, 4.0f, -45f);
        public Vector3 printLookAt = new Vector3(279f, 5.5f, 0f);
        public float printFovV = 38f;
        public float seatHold = 4f, moveSeconds = 6f, printHold = 2f, afterSeconds = 6f;

        [Header("時計")]
        public bool manualClock;
        public bool showLabel = true;

        public FLIP3DClip Clip { get; private set; }
        public bool Initialized { get; private set; }
        public double ExperienceTime { get; private set; }
        public double LoopPhase { get; private set; }
        public int ShownRecord { get; private set; } = -1;
        public bool Frozen { get; private set; }
        public float CameraBlend { get; private set; }
        public double LastSwapMs { get; private set; }
        public double LoopSeconds => Clip.Manifest.loop_seconds;
        public double PrintPhase => Clip.Manifest.print_record_index / Clip.Manifest.record_fps;
        public double MoveTotal => seatHold + moveSeconds + printHold + afterSeconds;
        public string LastError { get; private set; }

        readonly List<MeshFilter> waterFilters = new List<MeshFilter>();
        readonly List<int> tileOf = new List<int>();
        readonly List<(int, GameObject)> bedTiles = new List<(int, GameObject)>();
        readonly List<(int, GameObject)> innerSea = new List<(int, GameObject)>();
        Transform root;
        double clockStart;
        readonly System.Diagnostics.Stopwatch swSwap = new System.Diagnostics.Stopwatch();

        public static string Arg(string name, string def)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return def;
        }
        public static bool HasArg(string name) => Array.IndexOf(Environment.GetCommandLineArgs(), name) >= 0;

        void Start()
        {
            if (!Application.isPlaying) return;
            try
            {
                dataDir = Arg("-f3ddata", dataDir);
                tilesPerSide = int.Parse(Arg("-f3dtiles", tilesPerSide.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);
                var m = Arg("-f3dmode", "");
                if (m == "seat") mode = Mode.Seat; else if (m == "print") mode = Mode.Print; else if (m == "move") mode = Mode.Move;
                Init();
            }
            catch (Exception e) { LastError = e.ToString(); Debug.LogError("FLIP3D_INIT_EXCEPTION " + e); }
        }

        public void Init()
        {
            if (Initialized) return;
            Clip = FLIP3DClip.Load(dataDir);
            var mf = Clip.Manifest;
            root = new GameObject("FLIP3D_Runtime").transform;
            root.SetParent(transform, false);
            root.gameObject.hideFlags = HideFlags.DontSave;
            float W = mf.tank_half_width;
            // 水：半分の水槽を z と −z。さらに壁で写して 170 m ごと（maxTiles まで作り、tilesPerSide で見せる数を選ぶ）
            for (int t = -maxTiles; t <= maxTiles; t++)
            {
                float zc = t * 2f * W;                        // 全幅 170 m ごと
                tileOf.Add(Math.Abs(t)); AddWater("Water_t" + t + "_pos", new Vector3(0, 0, zc), 1f);
                tileOf.Add(Math.Abs(t)); AddWater("Water_t" + t + "_neg", new Vector3(0, 0, zc), -1f);
                if (Clip.BedMesh != null && bedMaterial != null) { var b = AddMesh("Bed_t" + t, Clip.BedMesh, bedMaterial, new Vector3(0, 0, zc), Vector3.one); bedTiles.Add((Math.Abs(t), b.gameObject)); }
            }
            // 水槽の外の平らな海（計算にない）。並べた水槽の周りに 4 枚。並べない時は内側の 2 枚も出す
            if (seaMaterial != null)
            {
                float y = mf.still_offset_m;
                float zH = W + maxTiles * 2f * W;
                float S = outerSeaHalfSize, x0 = mf.tank_x0, x1 = mf.tank_x1;
                AddQuad("Sea_back", new Vector3(x0 - S, y, -S), new Vector3(x0, y, S));
                AddQuad("Sea_front", new Vector3(x1, y, -S), new Vector3(x1 + S, y, S));
                AddQuad("Sea_left", new Vector3(x0, y, -S), new Vector3(x1, y, -zH));
                AddQuad("Sea_right", new Vector3(x0, y, zH), new Vector3(x1, y, S));
                for (int t = 1; t <= maxTiles; t++)
                {
                    float za = W + (t - 1) * 2f * W, zb = W + t * 2f * W;
                    innerSea.Add((t, AddQuad("Sea_inner_l" + t, new Vector3(x0, y, -zb), new Vector3(x1, y, -za))));
                    innerSea.Add((t, AddQuad("Sea_inner_r" + t, new Vector3(x0, y, za), new Vector3(x1, y, zb))));
                }
            }
            SetTiles(tilesPerSide);
            if (cam == null) cam = Camera.main;
            clockStart = Time.realtimeSinceStartupAsDouble;
            Initialized = true;
            ApplyTime(0.0);
            Debug.Log(string.Format(CultureInfo.InvariantCulture, "FLIP3D_INIT frames={0} load_s={1:F2} clipMB={2:F1} vmax={3} tmax={4} tiles={5}",
                Clip.Meshes.Length, Clip.LoadSeconds, Clip.ClipBytes / 1e6, mf.vert_max, mf.tri_max, tilesPerSide));
        }

        // 見せる並びの数（0：全幅の 1 つだけ、1：両側に 1 つずつ）。並べない所は平らな海で埋める
        public void SetTiles(int n)
        {
            tilesPerSide = Mathf.Clamp(n, 0, maxTiles);
            for (int i = 0; i < waterFilters.Count; i++) waterFilters[i].gameObject.SetActive(tileOf[i] <= tilesPerSide);
            foreach (var (t, go) in bedTiles) go.SetActive(t <= tilesPerSide);
            foreach (var (t, go) in innerSea) go.SetActive(t > tilesPerSide);
        }

        // 確かめ用：水の材質を入れ替える（形は変えない）
        public void SetWaterMaterial(Material m)
        {
            foreach (var f in waterFilters) f.GetComponent<MeshRenderer>().sharedMaterial = m;
        }

        void AddWater(string name, Vector3 offset, float zSign)
        {
            var mfil = AddMesh(name, Clip.Meshes[0], waterMaterial, offset, new Vector3(1, 1, zSign));
            waterFilters.Add(mfil);
        }

        MeshFilter AddMesh(string name, Mesh mesh, Material mat, Vector3 pos, Vector3 scale)
        {
            var go = new GameObject(name);
            go.hideFlags = HideFlags.DontSave;
            go.transform.SetParent(root, false);
            go.transform.localPosition = pos;
            go.transform.localScale = scale;
            var f = go.AddComponent<MeshFilter>();
            f.sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = mat;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            return f;
        }

        GameObject AddQuad(string name, Vector3 a, Vector3 b)
        {
            var m = new Mesh { name = "FLIP3D_" + name };
            m.vertices = new[] { new Vector3(a.x, a.y, a.z), new Vector3(a.x, a.y, b.z), new Vector3(b.x, a.y, b.z), new Vector3(b.x, a.y, a.z) };
            m.normals = new[] { Vector3.up, Vector3.up, Vector3.up, Vector3.up };
            m.triangles = new[] { 0, 1, 2, 0, 2, 3 };
            m.RecalculateBounds();
            m.hideFlags = HideFlags.DontSave;
            return AddMesh(name, m, seaMaterial, Vector3.zero, Vector3.one).gameObject;
        }

        void Update()
        {
            if (!Initialized || manualClock) return;
            var kb = UnityEngine.InputSystem.Keyboard.current;
            if (kb != null)
            {
                if (kb.digit1Key.wasPressedThisFrame) { mode = Mode.Seat; clockStart = Time.realtimeSinceStartupAsDouble; }
                if (kb.digit2Key.wasPressedThisFrame) { mode = Mode.Print; clockStart = Time.realtimeSinceStartupAsDouble; }
                if (kb.digit3Key.wasPressedThisFrame) { mode = Mode.Move; clockStart = Time.realtimeSinceStartupAsDouble; }
            }
            ApplyTime(Time.realtimeSinceStartupAsDouble - clockStart);
        }

        static double Mod(double a, double m) { double r = a % m; return r < 0 ? r + m : r; }

        // 体験の時刻 s から、再生の位相・見せる記録・カメラを決める（実時間の再生と画面外の描画で同じ関数）
        public void ApplyTime(double s)
        {
            ExperienceTime = s;
            var mf = Clip.Manifest;
            double L = mf.loop_seconds;
            double phase;
            float blend;
            Frozen = false;
            if (mode == Mode.Move)
            {
                double sm = Mod(s, MoveTotal);
                double sPrint = seatHold + moveSeconds;
                if (sm < sPrint) { phase = PrintPhase + (sm - sPrint); blend = Smooth((float)((sm - seatHold) / moveSeconds)); }
                else if (sm < sPrint + printHold) { phase = PrintPhase; blend = 1f; Frozen = true; }
                else { phase = PrintPhase + (sm - sPrint - printHold); blend = 1f; }
            }
            else
            {
                phase = s;
                blend = mode == Mode.Print ? 1f : 0f;
            }
            phase = Mod(phase, L);
            LoopPhase = phase;
            int k = Math.Min(Clip.Meshes.Length - 1, Math.Max(0, (int)Math.Floor(phase * mf.record_fps + 1e-6)));
            swSwap.Restart();
            if (k != ShownRecord)
            {
                var mesh = Clip.Meshes[k];
                for (int i = 0; i < waterFilters.Count; i++) waterFilters[i].sharedMesh = mesh;
                ShownRecord = k;
            }
            swSwap.Stop();
            LastSwapMs = swSwap.Elapsed.TotalMilliseconds;
            CameraBlend = blend;
            if (cam != null) PlaceCamera(phase, blend);
        }

        static float Smooth(float u) { u = Mathf.Clamp01(u); return u * u * (3f - 2f * u); }

        public float HeaveAt(double phase)
        {
            var h = Clip.Manifest.heave;
            if (h == null || h.Length < 2) return 0f;
            double fi = phase * Clip.Manifest.heave_fps;
            int i = Math.Min(h.Length - 2, Math.Max(0, (int)Math.Floor(fi)));
            float u = (float)(fi - i);
            return Mathf.Lerp(h[i], h[i + 1], Mathf.Clamp01(u));
        }

        public Vector3 SeatBase => new Vector3(Clip.Manifest.seat_x, Clip.Manifest.still_offset_m + Clip.Manifest.seat_eye_m, Clip.Manifest.seat_z);

        void PlaceCamera(double phase, float blend)
        {
            var seatPos = SeatBase + Vector3.up * HeaveAt(phase);
            var seatRot = Quaternion.LookRotation(seatLookAt - SeatBase, Vector3.up);   // 向きは上下で変えない（地平線を保つ）
            var printRot = Quaternion.LookRotation(printLookAt - printPos, Vector3.up);
            // 動き：位置は座席と原画の視点を結ぶ（上下の分は動きにつれて消える）、向きは球面の補間、画角は線形
            cam.transform.position = Vector3.Lerp(seatPos, printPos, blend);
            cam.transform.rotation = Quaternion.Slerp(seatRot, printRot, blend);
            cam.fieldOfView = Mathf.Lerp(seatFovV, printFovV, blend);
        }

        void OnGUI()
        {
            if (!showLabel || !Initialized) return;
            var mf = Clip.Manifest;
            GUI.color = Color.white;
            string modeJa = mode == Mode.Seat ? "船の座席" : mode == Mode.Print ? "原画の視点" : "座席 → 原画の視点";
            GUI.Label(new Rect(12, 8, 1400, 22), string.Format(CultureInfo.InvariantCulture,
                "FLIP3D 試作：DA3（周期のうねり T 12 s・H 7.5 m、粒子 0.5 m）の面の記録を 12 s の繰り返しで再生。[1] 座席 [2] 原画の視点 [3] 動き　いま：{0}", modeJa));
            GUI.Label(new Rect(12, 28, 1400, 22), string.Format(CultureInfo.InvariantCulture,
                "計算の時刻 {0:F3} s（記録 {1}/{2}、8 個/s をコマを保って実時間で）{3}。水槽の外の平らな海・霧・空は計算にない。オフラインの計算の再生",
                mf.loop_start_s + ShownRecord / mf.record_fps, ShownRecord + 1, Clip.Meshes.Length, Frozen ? "　止め（原画に最も近い瞬間）" : ""));
        }
    }
}
