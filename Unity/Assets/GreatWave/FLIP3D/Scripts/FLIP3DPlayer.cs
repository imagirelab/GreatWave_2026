using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace GreatWave.FLIP3D
{
    // FLIP3D：DA3（周期のうねり・粒子 0.5 m）の 12 s の繰り返しを実時間で再生し、船の座席と原画の視点を見せる最小の場面（2026-10-16、進行役）。
    // 再生の決まり（形を変えない）：
    //   - 時計の時刻 → 繰り返しの中の位相 φ → その時刻以前の最後の記録（floor(φ × 記録の数/s)）を見せる。記録の数/s はクリップの頭と manifest の record_fps。
    //     コマの間の形は作らない（補間・速さでずらす・平滑をしない）。
    //   - 2026-10-16 追記：既定のクリップは毎コマの記録 DA3r の 24 個/s（clip_DA3r_k5_r24、24 fps の動画では各記録が 1 フレーム）。
    //     前の 3 コマおき 8 個/s のクリップ（clip_DA3_k5、各記録 3 フレーム）も同じ道で再生できる：-f3ddata <フォルダー> で選ぶか、キー [4] で切り替える
    //     （切り替えた先は初めての時だけ読み込む。読んだクリップは覚えておく）。
    //   - 横：記録は半分の水槽（横 0〜85 m、y = 0 は対称の面）。同じ Mesh を z → −z の変換でもう一度描いて全幅にする（計算の対称の仮定）。
    //     tilesPerSide > 0 なら、y = 85 m の壁で写して 170 m ごとに並べる（壁は鏡と同じなので、計算はこの並びの海と同じ）。
    //   - 船の上下：記録 hf（上の水面の高さ、毎コマ 24 個/s）の座席の足跡の平均（f3d_export.py）。この数だけは時刻で 1 次の補間をする（カメラの高さ）。
    //   - 計算にない物：水槽の外の平らな海（静かな水面の高さ）、霧、空、海底の色。
    // 視点：Seat（船の座席）・Print（原画の視点：真ん中の断面を横から）・Move（座席 → 見える動き → 原画に最も近い瞬間に原画の視点に着く → 止め）。
    // 2026-10-16 追記（続けて再生、進行役のサブエージェント）：
    //   - Playback.Continuous：記録の範囲 [from, to)（計算の時刻 s）を初めから終わりまで 1 回だけ、繰り返さずに見せる（継ぎ目がない）。
    //     時計の時刻 s → 計算の時刻 from + s（止めの分を引く）→ 記録 floor((時刻 − 記録 0 の時刻) × 記録の数/s)。終わりは EndAction：
    //     Hold（最後の記録で止める）か Restart（cutSeconds の黒い画面に「切れ目」と書いてから初めに戻る。繋がった繰り返しではないことを見せる）。
    //   - 長い記録（約 2,160 個）は全部を GPU に置けないので FLIP3DStream で続けて読む（記録が preloadMaxRecords より多い・GW45LIST1・-f3dstream の時）。
    //     12 s の窓（96・288 個）は前と同じく全部を GPU に置く（-f3dstream で続けて読む道も試せる）。
    //   - 続けて再生の Move：視点の動きの予定（moveSpec）で、決めた瞬間（既定は manifest の原画に最も近い瞬間 = k5 のコマ 2099）に原画の視点に着く。
    //     着く moveSeconds 前から見える動きで動き、着いたら printHold だけ再生の時計を止め、moveStay の間留まり、moveBack で座席へ戻る（負なら戻らない）。
    //     "each" は範囲の中の崩れごと（manifest の breakers）。次の動きと重なる時は戻らずに原画の視点に留まる。白い画面は使わない。
    public class FLIP3DPlayer : MonoBehaviour
    {
        public enum Mode { Seat, Print, Move }
        public enum Playback { Loop, Continuous }
        public enum EndAction { Hold, Restart }

        [Header("データ（f3d_export.py の出力）")]
        public string dataDir = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP3D/clip_DA3r_k5_r24";
        [Tooltip("キー [4] で切り替える先（前の 8 個/s のクリップ）")]
        public string altDataDir = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP3D/clip_DA3_k5";
        public Material waterMaterial, bedMaterial, seaMaterial;
        public int tilesPerSide = 1;
        public int maxTiles = 1;
        public float outerSeaHalfSize = 4000f;

        [Header("再生（2026-10-16 追記：続けて再生・続けて読む）")]
        public Playback playback = Playback.Loop;
        [Tooltip("manifest の clip_kind が continuous なら続けて再生にする（-f3dplay を渡すと使わない）")]
        public bool playbackFromManifest = true;
        [Tooltip("続けて再生の範囲（計算の時刻 s）。負なら manifest の play_from_s・play_to_s（なければ記録の全部）")]
        public float playFromS = -1f, playToS = -1f;
        public EndAction endAction = EndAction.Hold;
        public float cutSeconds = 1.5f;
        [Tooltip("続けて読む時の輪の大きさ（記録の数）")]
        public int streamRing = 24;
        [Tooltip("これより記録が多いクリップは続けて読む")]
        public int preloadMaxRecords = 400;
        public bool forceStream;
        [Tooltip("続けて読む時、記録ごとに SHA-256 を manifest と比べる（確かめ用）")]
        public bool verifySha;
        [Tooltip("続けて読む時、1 個の記録を何フレームに分けて GPU に送るか（1 全部・2 点と法線 → 三角形・3 点 → 法線 → 三角形）。-f3dsplit <n>")]
        public int uploadSplit = 2;

        [Header("視点")]
        public Camera cam;
        public Mode mode = Mode.Move;
        public float seatFovV = 55f;
        public Vector3 seatLookAt = new Vector3(274f, 3.0f, 0f);
        public Vector3 printPos = new Vector3(284f, 4.0f, -45f);
        public Vector3 printLookAt = new Vector3(279f, 5.5f, 0f);
        public float printFovV = 38f;
        public float seatHold = 4f, moveSeconds = 6f, printHold = 2f, afterSeconds = 6f;
        [Tooltip("続けて再生の視点の動きの予定。空＝manifest の原画に最も近い瞬間 1 つ（print）。例：k5、f2099、t87.4167、k3;k5、each、none。項目ごとに :move=6:hold=2:stay=6:back=6")]
        public string moveSpec = "";
        [Tooltip("続けて再生：着いた後に原画の視点に留まる計算の秒、座席へ戻る秒（負なら戻らない）")]
        public float moveStay = 6f, moveBack = 6f;

        [Header("時計")]
        public bool manualClock;
        public bool showLabel = true;
        [Tooltip("true の間は体験の時刻を 0 に保つ（時間の測りの助走用。FLIP3DTiming が使う）")]
        public bool holdClock;

        public FLIP3DClip Clip { get; private set; }
        public FLIP3DStream Stream { get; private set; }
        public FLIP3DManifest Manifest { get; private set; }
        public bool Streaming => Stream != null;
        public int RecordCount => Stream != null ? Stream.Index.Count : (Clip != null ? Clip.Meshes.Length : 0);
        public double LoadSeconds { get; private set; }
        public double PrefillSeconds { get; private set; }
        public long DataBytes { get; private set; }
        public bool Initialized { get; private set; }
        public double ExperienceTime { get; private set; }
        public double LoopPhase { get; private set; }          // 記録 0 からの時刻（s）。見せる記録 = floor(LoopPhase × 記録の数/s)
        public int ShownRecord { get; private set; } = -1;
        public int WantedRecord { get; private set; } = -1;
        public double ShownSimTime { get; private set; } = double.NaN;
        public int ShownSimFrame { get; private set; } = -1;
        public bool Frozen { get; private set; }
        public bool InCut { get; private set; }
        public bool Ended { get; private set; }
        public float CameraBlend { get; private set; }
        public double LastSwapMs { get; private set; }
        public bool MissThisFrame { get; private set; }
        public int MissFrames { get; private set; }
        public int LateRecords { get; private set; }
        public int UploadedThisFrame { get; private set; }
        public double LastUploadMs { get; private set; }
        public double LoopSeconds => Manifest.loop_seconds;
        public double PrintPhase => Manifest.print_record_index / Manifest.record_fps;
        public double MoveTotal => seatHold + moveSeconds + printHold + afterSeconds;
        public double PlayFromSim => Manifest.t_first + cFrom;
        public double PlayToSim => Manifest.t_first + cTo;               // 範囲の終わり（この時刻の記録は含まない）
        public double PlayLastSim => Manifest.t_first + (rTo - 1) / Manifest.record_fps;   // 範囲の最後の記録の時刻
        // 続けて再生の長さ（体験の秒）：範囲の長さ + 止めの合計（止めは Move の時だけ。座席・原画の視点だけの時は止めない）
        public double ContinuousSeconds => (cTo - cFrom) + (mode == Mode.Move ? holdsTotal : 0.0);
        public double ExperienceDuration => playback == Playback.Continuous ? ContinuousSeconds : (mode == Mode.Move ? MoveTotal : LoopSeconds);
        public string LastError { get; private set; }
        public string ScheduleText { get; private set; } = "";

        // 続けて再生の予定
        public struct MoveEvent { public double c, move, hold, stay, back; public int record, frame, k; }
        struct Envelope { public double u0, u1, d0, d1; }
        public readonly List<MoveEvent> Moves = new List<MoveEvent>();
        readonly List<Envelope> envs = new List<Envelope>();
        int rFrom, rTo; double cFrom, cTo, holdsTotal, maxHold;

        readonly List<MeshFilter> waterFilters = new List<MeshFilter>();
        readonly List<int> tileOf = new List<int>();
        readonly List<(int, GameObject)> bedTiles = new List<(int, GameObject)>();
        readonly List<(int, GameObject)> innerSea = new List<(int, GameObject)>();
        Transform root;
        double clockStart;
        readonly System.Diagnostics.Stopwatch swSwap = new System.Diagnostics.Stopwatch();
        readonly Dictionary<string, FLIP3DClip> clipCache = new Dictionary<string, FLIP3DClip>();
        readonly List<int> wantList = new List<int>();
        int lastWantedHead = -1;
        bool missing;
        CameraClearFlags keepClear; Color keepBg; bool cutOn;
        public string CurrentDataDir { get; private set; }

        public static string Arg(string name, string def)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return def;
        }
        public static bool HasArg(string name) => Array.IndexOf(Environment.GetCommandLineArgs(), name) >= 0;
        static float ArgF(string name, float def) => float.Parse(Arg(name, def.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);

        void Start()
        {
            if (!Application.isPlaying) return;
            try
            {
                ApplyArgs();
                var m = Arg("-f3dmode", "");
                if (m == "seat") mode = Mode.Seat; else if (m == "print") mode = Mode.Print; else if (m == "move") mode = Mode.Move;
                Init();
            }
            catch (Exception e) { LastError = e.ToString(); Debug.LogError("FLIP3D_INIT_EXCEPTION " + e); }
        }

        // 引数（プレイヤーと Editor の batch で同じ）。2026-10-16 追記の引数：
        //   -f3dplay continuous|loop  -f3dfrom <s> -f3dto <s>（計算の時刻）  -f3dend hold|restart  -f3dcut <s>
        //   -f3dmoves <予定>  -f3dmovesec <s>  -f3dhold <s>  -f3dstay <s>  -f3dback <s>
        //   -f3dring <n>  -f3dstream（12 s の窓も続けて読む）  -f3dsha（記録ごとに SHA-256 を比べる）  -f3dpreloadmax <n>
        public void ApplyArgs()
        {
            dataDir = Arg("-f3ddata", dataDir);
            altDataDir = Arg("-f3dalt", altDataDir);
            if (HasArg("-f3dnolabel")) showLabel = false;            // 時間の測りの切り分け用（画面の字を出さない）
            tilesPerSide = int.Parse(Arg("-f3dtiles", tilesPerSide.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);
            var pb = Arg("-f3dplay", "");
            if (pb == "continuous") { playback = Playback.Continuous; playbackFromManifest = false; }
            else if (pb == "loop") { playback = Playback.Loop; playbackFromManifest = false; }
            playFromS = ArgF("-f3dfrom", playFromS);
            playToS = ArgF("-f3dto", playToS);
            var en = Arg("-f3dend", "");
            if (en == "restart") endAction = EndAction.Restart; else if (en == "hold") endAction = EndAction.Hold;
            cutSeconds = ArgF("-f3dcut", cutSeconds);
            ApplyMoveArgs();
            streamRing = int.Parse(Arg("-f3dring", streamRing.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);
            preloadMaxRecords = int.Parse(Arg("-f3dpreloadmax", preloadMaxRecords.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);
            if (HasArg("-f3dstream")) forceStream = true;
            if (HasArg("-f3dsha")) verifySha = true;
            uploadSplit = int.Parse(Arg("-f3dsplit", uploadSplit.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);
        }

        // 視点の動きの予定と時間の引数だけ（Editor の batch が視点の値を決めた後にもう一度呼ぶ）
        public void ApplyMoveArgs()
        {
            moveSpec = Arg("-f3dmoves", moveSpec);
            moveSeconds = ArgF("-f3dmovesec", moveSeconds);
            printHold = ArgF("-f3dhold", printHold);
            moveStay = ArgF("-f3dstay", moveStay);
            moveBack = ArgF("-f3dback", moveBack);
        }

        // 先読みの予定を次の ApplyTime で作り直させる（確かめで輪を別に使った後など）
        public void InvalidateWanted() { lastWantedHead = -1; }

        public void Init()
        {
            if (Initialized) return;
            var sw = System.Diagnostics.Stopwatch.StartNew();
            var mf0 = FLIP3DManifest.Read(dataDir);
            bool stream = forceStream || mf0.format != "GW45CLP1" || mf0.frames > preloadMaxRecords;
            Mesh bed;
            if (stream)
            {
                Stream = FLIP3DStream.Open(dataDir, streamRing, verifySha);
                Stream.SplitLevel = uploadSplit;
                Stream.DirectGpu = !HasArg("-f3dmeshapi");                // -f3dmeshapi：Mesh.SetVertexBufferData で送る（比べ用）
                Manifest = Stream.Manifest;
                DataBytes = Stream.Index.TotalBytes;
                bed = FLIP3DClip.BuildBed(dataDir, Manifest);
            }
            else
            {
                Clip = FLIP3DClip.Load(dataDir);
                clipCache[dataDir] = Clip;
                Manifest = Clip.Manifest;
                DataBytes = Clip.ClipBytes;
                bed = Clip.BedMesh;
            }
            CurrentDataDir = dataDir;
            if (playbackFromManifest && Manifest.IsContinuousKind) playback = Playback.Continuous;
            var mf = Manifest;
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
                if (bed != null && bedMaterial != null) { var b = AddMesh("Bed_t" + t, bed, bedMaterial, new Vector3(0, 0, zc), Vector3.one); bedTiles.Add((Math.Abs(t), b.gameObject)); }
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
            BuildTimeline();
            if (Stream != null)
            {
                // 始めの読み込み：初めに見せる記録から輪の分（−2）を読み解いて GPU に送ってから時計を始める
                var st0 = Evaluate(0.0);
                ComputeWanted(0.0, st0.record);
                Stream.SetWanted(wantList, -1);
                lastWantedHead = st0.record;
                PrefillSeconds = Stream.Prefill(Math.Max(1, Stream.RingSize - 2), 120000);
            }
            clockStart = Time.realtimeSinceStartupAsDouble;
            Initialized = true;
            ApplyTime(0.0);
            LoadSeconds = Clip != null ? Clip.LoadSeconds : sw.Elapsed.TotalSeconds;
            Debug.Log(string.Format(CultureInfo.InvariantCulture,
                "FLIP3D_INIT frames={0} record_fps={6} load_s={1:F2} dataMB={2:F1} vmax={3} tmax={4} tiles={5} data={7} streaming={8} ring={9} prefill_s={10:F2} playback={11} range={12:F3}-{13:F3} moves={14}",
                RecordCount, LoadSeconds, DataBytes / 1e6, mf.vert_max, mf.tri_max, tilesPerSide, mf.record_fps, dataDir, Streaming, Streaming ? Stream.RingSize : 0,
                PrefillSeconds, playback, PlayFromSim, PlayToSim, ScheduleText));
        }

        void OnDestroy()
        {
            Stream?.Dispose();
            Stream = null;
        }

        // 続けて再生の範囲と視点の動きの予定を作る（再生の形・範囲・予定を変えたら呼ぶ）
        public void BuildTimeline()
        {
            var mf = Manifest;
            double fps = mf.record_fps;
            int n = RecordCount;
            double t0 = mf.t_first;
            bool hasRange = mf.play_to_s > mf.play_from_s;
            double from = playFromS >= 0 ? playFromS : (hasRange ? mf.play_from_s : t0);
            double to = playToS >= 0 ? playToS : (hasRange ? mf.play_to_s : t0 + n / fps);
            rFrom = Math.Min(n - 1, Math.Max(0, (int)Math.Round((from - t0) * fps)));
            rTo = Math.Min(n, Math.Max(rFrom + 1, (int)Math.Round((to - t0) * fps)));
            cFrom = rFrom / fps; cTo = rTo / fps;
            Moves.Clear();
            ParseMoves(moveSpec);
            Moves.Sort((a, b) => a.c.CompareTo(b.c));
            holdsTotal = 0; maxHold = 0;
            foreach (var e in Moves) { holdsTotal += e.hold; maxHold = Math.Max(maxHold, e.hold); }
            BuildEnvelopes();
            var sb = new System.Text.StringBuilder();
            foreach (var e in Moves) sb.Append(string.Format(CultureInfo.InvariantCulture, "{0}{1}f{2}@{3:F3}s(move{4:0.#},hold{5:0.#},stay{6:0.#},back{7:0.#})",
                sb.Length > 0 ? ";" : "", e.k > 0 ? "k" + e.k + ":" : "", e.frame, t0 + e.c, e.move, e.hold, e.stay, e.back));
            ScheduleText = sb.Length > 0 ? sb.ToString() : "none";
            lastWantedHead = -1;
        }

        int RecordOfFrame(int frame)
        {
            var mf = Manifest;
            if (mf.source_frames != null && mf.source_frames.Length == RecordCount)
            {
                for (int i = rFrom; i < rTo; i++) if (mf.source_frames[i] == frame) return i;
                return -1;
            }
            int r = (frame - mf.frame_first) / Math.Max(1, mf.record_step_frames);
            return r >= rFrom && r < rTo ? r : -1;
        }

        void ParseMoves(string spec)
        {
            var mf = Manifest;
            string sp = (spec ?? "").Trim();
            if (sp.Length == 0) sp = "print";
            if (sp == "none") return;
            foreach (var item0 in sp.Split(new[] { ';', ',', ' ' }, StringSplitOptions.RemoveEmptyEntries))
            {
                var parts = item0.Split(':');
                string tg = parts[0].Trim();
                var ev = new MoveEvent { move = moveSeconds, hold = printHold, stay = moveStay, back = moveBack };
                for (int i = 1; i < parts.Length; i++)
                {
                    var kv = parts[i].Split('=');
                    if (kv.Length != 2) continue;
                    double v = double.Parse(kv[1], CultureInfo.InvariantCulture);
                    if (kv[0] == "move") ev.move = v; else if (kv[0] == "hold") ev.hold = v; else if (kv[0] == "stay") ev.stay = v; else if (kv[0] == "back") ev.back = v;
                }
                var targets = new List<(int frame, int k)>();
                if (tg == "print") { if (mf.print_record_frame > 0) targets.Add((mf.print_record_frame, mf.breaker_k)); }
                else if (tg == "each") { if (mf.breakers != null) foreach (var b in mf.breakers) targets.Add((b.frame, b.k)); }
                else if (tg.StartsWith("k"))
                {
                    int k = int.Parse(tg.Substring(1), CultureInfo.InvariantCulture);
                    bool found = false;
                    if (mf.breakers != null) foreach (var b in mf.breakers) if (b.k == k) { targets.Add((b.frame, k)); found = true; }
                    if (!found && mf.breaker_k == k && mf.print_record_frame > 0) targets.Add((mf.print_record_frame, k));
                    if (!found && targets.Count == 0) Debug.LogWarning("FLIP3D_MOVES 崩れ k" + k + " が manifest にない");
                }
                else if (tg.StartsWith("f")) targets.Add((int.Parse(tg.Substring(1), CultureInfo.InvariantCulture), 0));
                else if (tg.StartsWith("t")) targets.Add(((int)Math.Round(double.Parse(tg.Substring(1), CultureInfo.InvariantCulture) * mf.sim_fps) + 1, 0));
                else { Debug.LogWarning("FLIP3D_MOVES 読めない項目：" + item0); continue; }
                foreach (var (frame, k) in targets)
                {
                    int r = RecordOfFrame(frame);
                    if (r < 0) { Debug.Log("FLIP3D_MOVES コマ " + frame + " は再生の範囲の外（使わない）"); continue; }
                    bool dup = false;
                    foreach (var e in Moves) if (e.record == r) dup = true;
                    if (dup) continue;
                    var e2 = ev; e2.record = r; e2.frame = frame; e2.k = k; e2.c = r / mf.record_fps;
                    if (e2.c - e2.move < cFrom) Debug.LogWarning("FLIP3D_MOVES コマ " + frame + " の動きの始めが再生の始めより前（始めから途中の位置で始まる）");
                    Moves.Add(e2);
                }
            }
        }

        // 原画の視点にいる重み：動きの始め u0 → 着く u1（= 原画に最も近い瞬間）→ 留まる → d0 → 戻る → d1。次の動きと重なる時は戻らずにまとめる
        void BuildEnvelopes()
        {
            envs.Clear();
            int i = 0;
            while (i < Moves.Count)
            {
                var e = Moves[i];
                int j = i;
                while (j + 1 < Moves.Count)
                {
                    var a = Moves[j]; var b = Moves[j + 1];
                    bool returns = a.back >= 0 && a.c + a.stay + a.back <= b.c - b.move;
                    if (returns) break;
                    j++;
                }
                var last = Moves[j];
                double d0 = last.back >= 0 ? last.c + last.stay : double.PositiveInfinity;
                double d1 = last.back >= 0 ? d0 + last.back : double.PositiveInfinity;
                envs.Add(new Envelope { u0 = e.c - e.move, u1 = e.c, d0 = d0, d1 = d1 });
                i = j + 1;
            }
        }

        float EnvBlend(double c)
        {
            float b = 0f;
            foreach (var v in envs)
            {
                float x;
                if (c < v.u0) continue;
                if (c < v.u1) x = Smooth((float)((c - v.u0) / Math.Max(1e-9, v.u1 - v.u0)));
                else if (c <= v.d0) x = 1f;
                else if (c < v.d1) x = 1f - Smooth((float)((c - v.d0) / Math.Max(1e-9, v.d1 - v.d0)));
                else x = 0f;
                b = Math.Max(b, x);
            }
            return b;
        }

        // 見せるクリップを入れ替える（24 個/s と 8 個/s。どちらも同じ窓・同じ海底・同じ座席。形は変えない）。体験の時刻はそのまま続ける
        // 2026-10-16 追記：全部を GPU に置く 12 s の窓どうしだけ（続けて読んでいる時は入れ替えない）
        public void UseClip(string dir)
        {
            if (!Initialized || string.IsNullOrEmpty(dir) || dir == CurrentDataDir) return;
            if (Stream != null) { Debug.Log("FLIP3D_CLIP 続けて読んでいる間は [4] で入れ替えない"); return; }
            if (!clipCache.TryGetValue(dir, out var c))
            {
                var mf = FLIP3DManifest.Read(dir);
                if (mf.format != "GW45CLP1" || mf.frames > preloadMaxRecords) { Debug.Log("FLIP3D_CLIP 長いクリップは [4] で入れ替えない：" + dir); return; }
                c = FLIP3DClip.Load(dir);
                clipCache[dir] = c;
                Debug.Log(string.Format(CultureInfo.InvariantCulture, "FLIP3D_CLIP loaded frames={0} record_fps={1} load_s={2:F2} data={3}", c.Meshes.Length, c.Manifest.record_fps, c.LoadSeconds, dir));
            }
            Clip = c;
            Manifest = c.Manifest;
            DataBytes = c.ClipBytes;
            CurrentDataDir = dir;
            ShownRecord = -1;
            BuildTimeline();
            ApplyTime(ExperienceTime);
        }

        public void ToggleClip() => UseClip(CurrentDataDir == dataDir ? altDataDir : dataDir);

        public void SetPlayback(Playback p)
        {
            playback = p;
            if (Initialized) BuildTimeline();
        }

        public void RestartClock()
        {
            clockStart = Time.realtimeSinceStartupAsDouble;
            lastWantedHead = -1;
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
            var mfil = AddMesh(name, Clip != null ? Clip.Meshes[0] : null, waterMaterial, offset, new Vector3(1, 1, zSign));
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
                if (kb.digit1Key.wasPressedThisFrame) { mode = Mode.Seat; RestartClock(); }
                if (kb.digit2Key.wasPressedThisFrame) { mode = Mode.Print; RestartClock(); }
                if (kb.digit3Key.wasPressedThisFrame) { mode = Mode.Move; RestartClock(); }
                if (kb.digit4Key.wasPressedThisFrame) ToggleClip();
                if (kb.digit5Key.wasPressedThisFrame) { SetPlayback(playback == Playback.Loop ? Playback.Continuous : Playback.Loop); RestartClock(); }
            }
            if (holdClock) clockStart = Time.realtimeSinceStartupAsDouble;
            ApplyTime(Time.realtimeSinceStartupAsDouble - clockStart);
        }

        static double Mod(double a, double m) { double r = a % m; return r < 0 ? r + m : r; }

        public struct State { public int record; public double phase; public bool frozen, cut, ended; public float blend; }
        // 計算の時刻の比べの許し（s）。丸めの差（約 1e-14 s）より大きく、記録を選ぶ floor(c × fps + 1e-6) の許し（1e-6 / fps ≒ 4e-8 s）より小さくする。
        // 2026-10-16 独立の確かめで 1e-7 → 1e-9 に直した：1e-7 だと、実時間で止めの終わりが [着く時刻 + 止め − 1e-7, … − 4e-8) に入ったフレームで、
        // 止めを抜けた後の記録が 1 つ前（着いた記録 − 1）に戻る（輪にないので「間に合わなかった」と数え、絵は着いた記録のまま）。連番の時刻では起きない
        const double TimeEps = 1e-9;

        // 体験の時刻 s → 見せる記録・記録 0 からの時刻・止め・カメラの重み（純粋な関数。先読みの予定もこれで計算する）
        public State Evaluate(double s)
        {
            var st = new State();
            var mf = Manifest;
            double fps = mf.record_fps;
            int n = RecordCount;
            if (playback == Playback.Continuous)
            {
                double total = ContinuousSeconds;
                bool useMoves = mode == Mode.Move;
                double x = s;
                if (endAction == EndAction.Restart) x = Mod(s, total + cutSeconds);
                if (x >= total)
                {
                    if (endAction == EndAction.Restart) { st.cut = true; st.record = -1; st.phase = cTo; return st; }
                    st.ended = true; x = total;                      // 終わり：最後の記録で止める
                }
                double c = cFrom + x;
                // 2026-10-16 確かめで直した：着く瞬間の比べに小さな許し（TimeEps）を入れる。前は cFrom + i/24 と記録の時刻 r/24 の丸めの差で、
                // 着いたフレームが止めに入らないことがあった（部分の記録の試し：止め 48 フレームのはずが 47、着いた記録が止めの前後に 1 回ずつ）。
                // 見せる記録の floor(c × 24 + 1e-6) と同じ向きの許し
                if (useMoves)
                    foreach (var e in Moves)
                    {
                        if (c < e.c - TimeEps) break;
                        if (c < e.c + e.hold - TimeEps) { st.frozen = true; c = e.c; break; }
                        c -= e.hold;
                    }
                int k = Math.Min(rTo - 1, Math.Max(rFrom, (int)Math.Floor(c * fps + 1e-6)));
                st.record = k; st.phase = st.ended ? (rTo - 1) / fps : c;
                st.blend = mode == Mode.Seat ? 0f : mode == Mode.Print ? 1f : (st.frozen ? 1f : EnvBlend(c));
                return st;
            }
            double L = mf.loop_seconds;
            double phase;
            float blend;
            if (mode == Mode.Move)
            {
                double sm = Mod(s, MoveTotal);
                double sPrint = seatHold + moveSeconds;
                if (sm < sPrint) { phase = PrintPhase + (sm - sPrint); blend = Smooth((float)((sm - seatHold) / moveSeconds)); }
                else if (sm < sPrint + printHold) { phase = PrintPhase; blend = 1f; st.frozen = true; }
                else { phase = PrintPhase + (sm - sPrint - printHold); blend = 1f; }
            }
            else
            {
                phase = s;
                blend = mode == Mode.Print ? 1f : 0f;
            }
            phase = Mod(phase, L);
            st.phase = phase;
            st.blend = blend;
            st.record = Math.Min(n - 1, Math.Max(0, (int)Math.Floor(phase * fps + 1e-6)));
            return st;
        }

        // 先読みの予定：今の記録から、時計の先（輪の 2 倍の時間 + 止め + 切れ目）までに見せる記録を見せる順に（重なりは除く）
        void ComputeWanted(double s, int head)
        {
            wantList.Clear();
            if (head >= 0) wantList.Add(head);
            int cap = Math.Max(1, Stream.RingSize - 2);
            double fps = Manifest.record_fps;
            double step = 0.5 / fps;
            double horizon = 2.0 * cap / fps + maxHold + (playback == Playback.Continuous && endAction == EndAction.Restart ? cutSeconds : 0) + 1.0;
            if (mode == Mode.Move && playback == Playback.Loop) horizon += printHold;
            for (double x = s + step; x <= s + horizon && wantList.Count < cap; x += step)
            {
                var st = Evaluate(x);
                if (st.record >= 0 && !wantList.Contains(st.record)) wantList.Add(st.record);
            }
        }

        // 体験の時刻 s から、再生の位相・見せる記録・カメラを決める（実時間の再生と画面外の描画で同じ関数）
        public void ApplyTime(double s)
        {
            ExperienceTime = s;
            var st = Evaluate(s);
            Frozen = st.frozen; Ended = st.ended;
            LoopPhase = st.phase;
            WantedRecord = st.record;
            CameraBlend = st.blend;
            UploadedThisFrame = 0; LastUploadMs = 0;
            swSwap.Restart();
            SetCut(st.cut);
            if (!st.cut) ShowRecord(st.record);
            swSwap.Stop();
            LastSwapMs = swSwap.Elapsed.TotalMilliseconds;
            if (cam != null && !st.cut) PlaceCamera(st.phase, st.blend);
        }

        void Swap(Mesh mesh, int k, double t, int frame)
        {
            for (int i = 0; i < waterFilters.Count; i++) waterFilters[i].sharedMesh = mesh;
            ShownRecord = k; ShownSimTime = t; ShownSimFrame = frame;
        }

        void ShowRecord(int k)
        {
            MissThisFrame = false;
            if (Stream == null)
            {
                if (k != ShownRecord) Swap(Clip.Meshes[k], k, Clip.Times[k], Clip.SimFrames[k]);
                return;
            }
            Stream.BeginFrame();
            int up0 = Stream.UploadOps;
            if (k != lastWantedHead)
            {
                ComputeWanted(ExperienceTime, k);
                Stream.SetWanted(wantList, ShownRecord);
                lastWantedHead = k;
            }
            if (k != ShownRecord)
            {
                if (Stream.TryGet(k, out var mesh, out var h))
                {
                    Swap(mesh, k, h.t, h.frame);
                    Stream.SetDisplayed(k);
                    if (missing) LateRecords++;
                    missing = false;
                }
                else if (manualClock)
                {
                    // 画面外の描画：記録が来るまで待つ（コマを落とさない）
                    mesh = Stream.WaitFor(k, 120000, out h);
                    Swap(mesh, k, h.t, h.frame);
                    Stream.SetDisplayed(k);
                }
                else
                {
                    // 実時間：間に合わない。前の記録を見せ続ける（形を作らない・別の記録で埋めない）
                    MissFrames++; MissThisFrame = true; missing = true;
                }
            }
            Stream.Pump();
            UploadedThisFrame = Stream.UploadOps - up0;
            if (UploadedThisFrame > 0) LastUploadMs = Stream.LastUploadMs;
        }

        // 切れ目（続けて再生の Restart の時だけ）：水・海底・海を隠し、黒い画面にする（視点の動きには使わない）
        void SetCut(bool on)
        {
            if (on == cutOn) { InCut = on; return; }
            cutOn = on; InCut = on;
            if (root != null) root.gameObject.SetActive(!on);
            if (cam == null) return;
            if (on) { keepClear = cam.clearFlags; keepBg = cam.backgroundColor; cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = Color.black; }
            else { cam.clearFlags = keepClear; cam.backgroundColor = keepBg; }
        }

        static float Smooth(float u) { u = Mathf.Clamp01(u); return u * u * (3f - 2f * u); }

        public float HeaveAt(double phase)
        {
            var h = Manifest.heave;
            if (h == null || h.Length < 2) return 0f;
            double fi = phase * Manifest.heave_fps;
            int i = Math.Min(h.Length - 2, Math.Max(0, (int)Math.Floor(fi)));
            float u = (float)(fi - i);
            return Mathf.Lerp(h[i], h[i + 1], Mathf.Clamp01(u));
        }

        public Vector3 SeatBase => new Vector3(Manifest.seat_x, Manifest.still_offset_m + Manifest.seat_eye_m, Manifest.seat_z);

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

        // 見せている記録が、どの崩れの巻き始め〜着水 + 0.5 s に入るか（manifest の breakers。なければ 0）
        public FLIP3DBreaker BreakerAt(int frame)
        {
            if (Manifest.breakers == null) return null;
            foreach (var b in Manifest.breakers) if (frame >= b.win_first && frame <= b.win_last) return b;
            return null;
        }

        // 画面の字の絵（グリフ）を始めに 1 回まとめて作っておく（2026-10-16 確かめで足した）。字ありの時間の測りでは、字が初めて出るフレームに
        // 10〜30 ms の止まりが 1 回ずつあった（部分の記録の試し v1cont：数字の「8」が初めて出る記録 50、「崩れ k2」の記録 67、「★…score3…」の記録 95。
        // 合成の列の記録 3 も k4 の ★ が初めて出る所）。字なしでは出なかった。Unity 6 の IMGUI は字を TextCore の動く字の置き場で描くので、
        // 初めての字はその場で絵を作って置き場へ送る【推測】。Font.RequestCharactersInTexture（古い字の道）では消えなかったので、
        // 同じ IMGUI の道で、字の型の文字と数字を全部、ほとんど透明（alpha 0.01）に 1 回だけ描く（助走の間に済む）。見せる字そのものは変えない
        bool glyphsWarmed;
        const string LabelGlyphs =
            "0123456789.,:;+-−/%()（）〜→⇔★【】［］[]、。・＝=：" +
            " !\"#$&'*<>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ\\^_`abcdefghijklmnopqrstuvwxyz{|}~" +
            "FLIP3D 試作：DA3（周期のうねり T 12 s・H 7.5 m、粒子 0.5 m）の面の記録を 12 s の繰り返しで再生。[1] 座席 [2] 原画の視点 [3] 動き [4] 24 個/s ⇔ 8 個/s [5] 続けて ⇔ 繰り返し　いま：" +
            "計算の時刻 s（記録 個/s を実時間で。コマの間の形は作らない）。水槽の外の平らな海・霧・空は計算にない。オフラインの計算の再生　止め（原画に最も近い瞬間）" +
            "【試験用の合成の列：同じ記録を繰り返し並べた物。本番の結果ではない】DA3r の面の記録を s 続けて 1 回再生（繰り返さない・継ぎ目なし）。" +
            "切れ目：ここで初めに戻る。繋がった繰り返しではない（の黒い画面）★ 崩れ k：score3 で原画に最も近い瞬間 コマ、記録 止め（再生の時計だけを止めた）終わり" +
            "続けて読む：輪 個、間に合わなかったフレーム 誤り：船の座席 原画の視点 座席 → 原画の視点";

        void WarmGlyphs()
        {
            if (Event.current == null || Event.current.type != EventType.Repaint) return;
            var keep = GUI.color;
            GUI.color = new Color(1f, 1f, 1f, 0.01f);
            GUI.Label(new Rect(12, 70, 1800, 400), LabelGlyphs);
            GUI.color = keep;
            glyphsWarmed = true;
        }

        void OnGUI()
        {
            if (!showLabel || !Initialized) return;
            if (!glyphsWarmed) WarmGlyphs();
            var mf = Manifest;
            GUI.color = Color.white;
            string modeJa = mode == Mode.Seat ? "船の座席" : mode == Mode.Print ? "原画の視点" : "座席 → 原画の視点";
            if (playback == Playback.Loop)
            {
                // 2026-10-16 独立の確かめで直した：繰り返しの長さは manifest の loop_seconds（12 s の窓は前と同じ「12 s」。長いクリップを [5] で繰り返しにした時は
                // 記録の全部 約 90 s を回すので、その長さを出す。前は「12 s」と決め打ちで、長いクリップの繰り返しの字が正しくなかった）
                GUI.Label(new Rect(12, 8, 1400, 22), string.Format(CultureInfo.InvariantCulture,
                    "FLIP3D 試作：DA3（周期のうねり T 12 s・H 7.5 m、粒子 0.5 m）の面の記録を {1:0.##} s の繰り返しで再生。[1] 座席 [2] 原画の視点 [3] 動き [4] 24 個/s ⇔ 8 個/s [5] 続けて ⇔ 繰り返し　いま：{0}", modeJa, mf.loop_seconds));
                GUI.Label(new Rect(12, 28, 1400, 22), string.Format(CultureInfo.InvariantCulture,
                    "計算の時刻 {0:F3} s（記録 {1}/{2}、{4:0} 個/s を実時間で。コマの間の形は作らない）{3}。水槽の外の平らな海・霧・空は計算にない。オフラインの計算の再生",
                    ShownSimTime, ShownRecord + 1, RecordCount, Frozen ? "　止め（原画に最も近い瞬間）" : "", mf.record_fps));
            }
            else
            {
                string kind = mf.clip_kind == "synthetic_test" ? "【試験用の合成の列：同じ記録を繰り返し並べた物。本番の結果ではない】" : "";
                GUI.Label(new Rect(12, 8, 1600, 22), string.Format(CultureInfo.InvariantCulture,
                    "{0}FLIP3D 試作：DA3r の面の記録を {1:F2}〜{2:F2} s 続けて 1 回再生（繰り返さない・継ぎ目なし）。[1] 座席 [2] 原画の視点 [3] 動き [5] 続けて ⇔ 繰り返し　いま：{3}",
                    kind, PlayFromSim, PlayLastSim, modeJa));
                if (InCut)
                {
                    GUI.Label(new Rect(12, 28, 1600, 22), string.Format(CultureInfo.InvariantCulture,
                        "切れ目：ここで初め（{0:F2} s）に戻る。繋がった繰り返しではない（{1:0.0} s の黒い画面）", PlayFromSim, cutSeconds));
                    return;
                }
                var b = BreakerAt(ShownSimFrame);
                string bk = b == null ? "" : (ShownSimFrame == b.frame ? string.Format(CultureInfo.InvariantCulture, "　★ 崩れ k{0}：score3 で原画に最も近い瞬間（{1:F3}）", b.k, b.score3)
                                                                       : string.Format(CultureInfo.InvariantCulture, "　崩れ k{0}", b.k));
                GUI.Label(new Rect(12, 28, 1600, 22), string.Format(CultureInfo.InvariantCulture,
                    "計算の時刻 {0:F3} s（コマ {1}、記録 {2}/{3}、{4:0} 個/s を実時間で。コマの間の形は作らない）{5}{6}{7}。水槽の外の平らな海・霧・空は計算にない",
                    ShownSimTime, ShownSimFrame, ShownRecord + 1, RecordCount, mf.record_fps, bk, Frozen ? "　止め（再生の時計だけを止めた）" : "", Ended ? "　終わり" : ""));
                if (Streaming)
                    GUI.Label(new Rect(12, 48, 1600, 22), string.Format(CultureInfo.InvariantCulture,
                        "続けて読む：輪 {0} 個、間に合わなかったフレーム {1}{2}", Stream.RingSize, MissFrames, Stream.Error != null ? "　誤り：" + Stream.Error : ""));
            }
        }
    }
}
