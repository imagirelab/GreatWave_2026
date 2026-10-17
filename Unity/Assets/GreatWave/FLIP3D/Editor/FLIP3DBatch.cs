using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.FLIP3D.EditorTools
{
    // FLIP3D：場面を作る・画面外に描いて連番にする・Release のプレイヤーを作る（batchmode。2026-10-16、進行役）。
    // 作るのは Assets/GreatWave/FLIP3D/ の下だけ。ほかの場面・資産は開かず、変えない。
    //   -executeMethod GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildSceneAndCapture
    //       -f3dcap stills,seat,print,move,seat3,verify   -f3dout <dir>   -f3dsize 1920x1080   -f3dfps 24   -f3dtiles 0
    //       2026-10-16 追記：-f3ddata <クリップのフォルダー>（既定は場面の値＝24 個/s の clip_DA3r_k5_r24。前の 8 個/s は clip_DA3_k5）、
    //       -f3dverifyout <dir>（verify の書き出し先、既定 Build/FLIP3D/verify）、seat3 は座席の 3 回の繰り返し（36 s）
    //   -executeMethod GreatWave.FLIP3D.EditorTools.FLIP3DBatch.BuildPlayerAndExit   （-f3dplayerout <dir>）
    //   2026-10-16 追記（続けて再生、進行役のサブエージェント）：連番 cseat・cprint・cmove は、記録の範囲（-f3dfrom・-f3dto、計算の時刻 s。
    //       なければ manifest の play_from_s・play_to_s）を続けて 1 回（繰り返さない）。cmove の視点の動きは -f3dmoves（既定：manifest の原画に最も近い瞬間 1 つ）・
    //       -f3dmovesec・-f3dhold・-f3dstay・-f3dback。長いクリップは続けて読む（FLIP3DStream。画面外の描画では記録が来るまで待つのでコマを落とさない）。
    //       cstills は予定の各動きの着く瞬間とその 3 s 前の静止画。verify は、続けて読んでいる時は輪の読み解き（GPU に送るのと同じ配列）を書く。
    //       -f3dstream で 12 s の窓も続けて読む道で描ける。
    //   2026-10-17 追記：連番 print3（原画の視点で繰り返し 3 回）・move3（繰り返し 3 回の中で座席 → 原画の視点。MoveLoops、-f3dminseat）。
    //       視点の値は ApplyPoses のまま。ただし manifest に cam_*（FLIP50 の D の水槽のカメラ）があるクリップはその値（FLIP3DPlayer.ApplyManifestPoses）
    public static class FLIP3DBatch
    {
        public const string Root = "Assets/GreatWave/FLIP3D";
        public const string ScenePath = Root + "/Scenes/FLIP3D_Playback.unity";
        public static string BuildRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "../Build/FLIP3D"));
        static readonly CultureInfo IC = CultureInfo.InvariantCulture;

        public static void BuildSceneAndCapture()
        {
            int code = 0;
            try
            {
                BuildScene();
                Capture();
            }
            catch (Exception e) { Debug.LogError("FLIP3D_BATCH_EXCEPTION " + e); code = 1; }
            EditorApplication.Exit(code);
        }

        static void EnsureFolder(string parent, string name)
        {
            if (!AssetDatabase.IsValidFolder(parent + "/" + name)) AssetDatabase.CreateFolder(parent, name);
        }

        static Material Mat(string name, Shader sh, Action<Material> set)
        {
            string p = Root + "/Materials/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(p);
            if (m == null) { m = new Material(sh); AssetDatabase.CreateAsset(m, p); }
            else m.shader = sh;
            set(m);
            EditorUtility.SetDirty(m);
            return m;
        }

        public static void BuildScene()
        {
            EnsureFolder(Root, "Scenes");
            EnsureFolder(Root, "Materials");
            var water = Shader.Find("GreatWave/FLIP3D/Water");
            var std = Shader.Find("Standard");
            var skySh = Shader.Find("Skybox/Procedural");
            if (water == null || std == null || skySh == null) throw new InvalidOperationException("シェーダーが見つかりません（コンパイルの誤り？）");
            Action<Material> wcol = m =>
            {
                // 陰影の候補 B_contrast（capture/look の比べで選んだ）
                m.SetColor("_Deep", new Color(0.012f, 0.070f, 0.100f)); m.SetColor("_Lit", new Color(0.110f, 0.420f, 0.450f));
                m.SetColor("_SkyTop", new Color(0.26f, 0.40f, 0.58f)); m.SetColor("_SkyHorizon", new Color(0.50f, 0.60f, 0.68f));
                m.SetFloat("_SunPower", 600f); m.SetFloat("_SunScale", 3f); m.SetFloat("_F0", 0.02f); m.SetFloat("_Wrap", 0.0f);
            };
            var mWater = Mat("FLIP3D_Water", water, wcol);
            var mSea = Mat("FLIP3D_Sea", water, wcol);
            var mBed = Mat("FLIP3D_Bed", std, m => { m.SetColor("_Color", new Color(0.52f, 0.46f, 0.36f)); m.SetFloat("_Glossiness", 0.08f); m.SetFloat("_Metallic", 0f); });
            var mSky = Mat("FLIP3D_Sky", skySh, m =>
            {
                m.SetFloat("_SunSize", 0.035f); m.SetFloat("_AtmosphereThickness", 0.9f); m.SetFloat("_Exposure", 1.15f);
                m.SetColor("_SkyTint", new Color(0.5f, 0.55f, 0.62f)); m.SetColor("_GroundColor", new Color(0.36f, 0.40f, 0.43f));
            });
            AssetDatabase.SaveAssets();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var sun = new GameObject("Sun");
            var L = sun.AddComponent<Light>();
            L.type = LightType.Directional; L.intensity = 1.15f; L.color = new Color(1f, 0.96f, 0.90f); L.shadows = LightShadows.None;
            sun.transform.rotation = Quaternion.LookRotation(new Vector3(-0.55f, -0.62f, 0.45f).normalized, Vector3.up);
            RenderSettings.sun = L;
            RenderSettings.skybox = mSky;
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.55f, 0.62f, 0.70f);
            RenderSettings.ambientEquatorColor = new Color(0.46f, 0.50f, 0.54f);
            RenderSettings.ambientGroundColor = new Color(0.22f, 0.22f, 0.22f);
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogStartDistance = 300f;
            RenderSettings.fogEndDistance = 1600f;
            RenderSettings.fogColor = new Color(0.76f, 0.81f, 0.85f);

            var camGo = new GameObject("MainCamera");
            camGo.tag = "MainCamera";
            var cam = camGo.AddComponent<Camera>();
            cam.nearClipPlane = 0.3f; cam.farClipPlane = 6000f; cam.fieldOfView = 55f; cam.allowMSAA = true; cam.allowHDR = false;
            cam.clearFlags = CameraClearFlags.Skybox;
            camGo.AddComponent<AudioListener>();

            var go = new GameObject("FLIP3D");
            var pl = go.AddComponent<FLIP3DPlayer>();
            pl.waterMaterial = mWater; pl.seaMaterial = mSea; pl.bedMaterial = mBed; pl.cam = cam;
            pl.dataDir = Path.Combine(BuildRoot, "clip_DA3r_k5_r24").Replace('\\', '/');      // 2026-10-16：毎コマの記録の 24 個/s
            pl.altDataDir = Path.Combine(BuildRoot, "clip_DA3_k5").Replace('\\', '/');        // 前の 8 個/s（キー [4]）
            ApplyPoses(pl);
            var tm = go.AddComponent<FLIP3DTiming>();
            tm.player = pl;
            EditorSceneManager.SaveScene(scene, ScenePath);
            Debug.Log("FLIP3D_SCENE saved " + ScenePath);
        }

        // 視点の値（ここだけで決める。動画と場面で同じ値）
        public static void ApplyPoses(FLIP3DPlayer pl)
        {
            pl.seatFovV = 55f;
            pl.seatLookAt = new Vector3(274f, 3.0f, 0f);
            pl.printPos = new Vector3(284f, 4.0f, -45f);       // 真ん中の断面を横から（原画との比べの断面と同じ向き。波は右へ進み右へ巻く）
            pl.printLookAt = new Vector3(279f, 5.5f, 0f);
            pl.printFovV = 38f;
            pl.seatHold = 4f; pl.moveSeconds = 6f; pl.printHold = 2f; pl.afterSeconds = 6f;
            pl.moveStay = 6f; pl.moveBack = 6f;                // 続けて再生：着いた後に留まる 6 s、座席へ戻る 6 s（2026-10-16 追記）
            if (pl.Manifest != null) pl.ApplyManifestPoses();  // 2026-10-17 追記：manifest に cam_* があるクリップ（FLIP50 の D）だけ。ないクリップは上の値のまま
        }

        static string Arg(string n, string d) => FLIP3DPlayer.Arg(n, d);

        public static void Capture()
        {
            var cap = Arg("-f3dcap", "");
            if (string.IsNullOrEmpty(cap)) return;
            var scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var pl = UnityEngine.Object.FindFirstObjectByType<FLIP3DPlayer>();
            pl.manualClock = true;
            pl.ApplyArgs();                                      // 2026-10-16 追記：続けて再生・続けて読むの引数（再生の形は連番の名前で決める）
            pl.tilesPerSide = int.Parse(Arg("-f3dtiles", "0"), IC);
            pl.dataDir = Arg("-f3ddata", pl.dataDir);
            var sw = System.Diagnostics.Stopwatch.StartNew();
            pl.Init();
            Debug.Log("FLIP3D_CAPTURE init_s=" + sw.Elapsed.TotalSeconds.ToString("F2", IC) + " record_fps=" + pl.Manifest.record_fps.ToString(IC) + " records=" + pl.RecordCount
                + " streaming=" + pl.Streaming + " data=" + pl.dataDir);
            string outDir = Arg("-f3dout", Path.Combine(BuildRoot, "capture"));
            var sz = Arg("-f3dsize", "1920x1080").Split('x');
            int w = int.Parse(sz[0], IC), h = int.Parse(sz[1], IC);
            double fps = double.Parse(Arg("-f3dfps", "24"), IC);
            foreach (var job in cap.Split(','))
            {
                var j = job.Trim();
                if (j == "stills") Stills(pl, Path.Combine(outDir, "stills"), w, h);
                else if (j == "debug") DebugStills(pl, Path.Combine(outDir, "debug"), w, h);
                else if (j == "look") LookStills(pl, Path.Combine(outDir, "look"), w, h);
                else if (j == "verify") VerifyExport(pl, Arg("-f3dverifyout", Path.Combine(BuildRoot, "verify")));
                else if (j == "seat") Sequence(pl, FLIP3DPlayer.Mode.Seat, pl.LoopSeconds, Path.Combine(outDir, "seat"), w, h, fps);
                else if (j == "seat3") Sequence(pl, FLIP3DPlayer.Mode.Seat, 3 * pl.LoopSeconds, Path.Combine(outDir, "seat3"), w, h, fps);
                else if (j == "switch") SwitchCheck(pl, Path.Combine(outDir, "switch"), w, h);
                else if (j == "toggle5") Toggle5Check(pl, Path.Combine(outDir, "toggle5"), w, h);
                else if (j == "print") Sequence(pl, FLIP3DPlayer.Mode.Print, pl.LoopSeconds, Path.Combine(outDir, "print"), w, h, fps);
                else if (j == "move") Sequence(pl, FLIP3DPlayer.Mode.Move, pl.MoveTotal, Path.Combine(outDir, "move"), w, h, fps);
                else if (j == "print3") Sequence(pl, FLIP3DPlayer.Mode.Print, 3 * pl.LoopSeconds, Path.Combine(outDir, "print3"), w, h, fps);   // 2026-10-17 追記
                else if (j == "move3") MoveLoops(pl, 3, Path.Combine(outDir, "move3"), w, h, fps);                                              // 2026-10-17 追記
                else if (j == "cseat") ContinuousSequence(pl, FLIP3DPlayer.Mode.Seat, Path.Combine(outDir, "cseat"), w, h, fps);
                else if (j == "cprint") ContinuousSequence(pl, FLIP3DPlayer.Mode.Print, Path.Combine(outDir, "cprint"), w, h, fps);
                else if (j == "cmove") ContinuousSequence(pl, FLIP3DPlayer.Mode.Move, Path.Combine(outDir, "cmove"), w, h, fps);
                else if (j == "cstills") ContinuousStills(pl, Path.Combine(outDir, "cstills"), w, h);
                else if (j == "xrcheck") XrShaderCheck(pl, Path.Combine(outDir, "xrcheck"), w, h);                                      // 2026-10-17 追記
                else Debug.LogWarning("FLIP3D_CAPTURE 知らない仕事：" + j);
            }
            if (pl.Stream != null)
                Debug.Log(string.Format(IC, "FLIP3D_STREAM_STATS read={0} MB={1:F1} uploads={2} urgent={3} evictions={4} sha_bad={5}/{6} error={7}",
                    pl.Stream.RecordsRead, pl.Stream.BytesRead / 1e6, pl.Stream.Uploads, pl.Stream.UrgentUploads, pl.Stream.Evictions, pl.Stream.ShaMismatches, pl.Stream.ShaChecked, pl.Stream.Error ?? "none"));
        }

        static void Stills(FLIP3DPlayer pl, string dir, int w, int h)
        {
            Directory.CreateDirectory(dir);
            var cam = pl.cam;
            double pp = pl.PrintPhase;
            // 原画の視点の候補（原画に最も近い瞬間）。名前に値を入れる
            var cands = new List<(string, Vector3, Vector3, float)>
            {
                ("R0_x283_y6_z-70_f34", new Vector3(283, 6, -70), new Vector3(280, 5.0f, 0), 34f),
                ("Q1_x300_y6_z-60_f38", new Vector3(300, 6, -60), new Vector3(279, 4.0f, 0), 38f),
                ("Q2_x282_y8_z-70_f34", new Vector3(282, 8, -70), new Vector3(280, 3.5f, 0), 34f),
                ("Q3_x282_y5_z-45_f50", new Vector3(282, 5, -45), new Vector3(279, 4.0f, 0), 50f),
                ("Q4_x295_y4_z-50_f42", new Vector3(295, 4, -50), new Vector3(279, 4.5f, 0), 42f),
                ("Q5_x282_y12_z-90_f28", new Vector3(282, 12, -90), new Vector3(280, 3.0f, 0), 28f),
                ("Q6_x275_y6_z-60_f40", new Vector3(275, 6, -60), new Vector3(279, 4.0f, 0), 40f),
            };
            var rows = new StringBuilder("name,tiles,phase,record,px,py,pz,lx,ly,lz,fov\n");
            foreach (int tiles in new[] { 0, 1 })
            {
                pl.SetTiles(tiles);
                foreach (var (name, p, l, f) in cands)
                {
                    pl.mode = FLIP3DPlayer.Mode.Print;
                    pl.printPos = p; pl.printLookAt = l; pl.printFovV = f;
                    pl.ApplyTime(pp);
                    Save(cam, w, h, Path.Combine(dir, string.Format(IC, "print_{0}_tiles{1}.png", name, tiles)), true);
                    rows.AppendLine(string.Format(IC, "{0},{1},{2:F4},{3},{4},{5},{6},{7},{8},{9},{10}", name, tiles, pl.LoopPhase, pl.ShownRecord, p.x, p.y, p.z, l.x, l.y, l.z, f));
                }
                ApplyPoses(pl);
                pl.mode = FLIP3DPlayer.Mode.Seat;
                foreach (double dt in new[] { -6.0, -3.0, -1.5, -0.5, 0.0, 0.75, 1.5, 4.0 })
                {
                    double ph = ((pp + dt) % pl.LoopSeconds + pl.LoopSeconds) % pl.LoopSeconds;
                    pl.ApplyTime(ph);
                    Save(cam, w, h, Path.Combine(dir, string.Format(IC, "seat_dt{0:+0.00;-0.00}_tiles{1}.png", dt, tiles)), true);
                    rows.AppendLine(string.Format(IC, "seat_dt{0:F2},{1},{2:F4},{3},,,,,,,{4}", dt, tiles, pl.LoopPhase, pl.ShownRecord, pl.seatFovV));
                }
            }
            File.WriteAllText(Path.Combine(dir, "stills.csv"), rows.ToString());
            pl.SetTiles(int.Parse(Arg("-f3dtiles", "0"), IC));
            ApplyPoses(pl);
            Debug.Log("FLIP3D_STILLS done " + dir);
        }

        // 陰影の候補（水の材質の値だけを変える。形は同じ）
        static void LookStills(FLIP3DPlayer pl, string dir, int w, int h)
        {
            Directory.CreateDirectory(dir);
            var m = pl.waterMaterial;
            var keep = new Material(m);
            var looks = new (string, Color, Color, Color, Color, float, Vector3)[]
            {
                ("A_now", new Color(0.035f, 0.150f, 0.190f), new Color(0.090f, 0.340f, 0.380f), new Color(0.30f, 0.44f, 0.62f), new Color(0.58f, 0.67f, 0.74f), 0.3f, new Vector3(-0.55f, -0.62f, 0.45f)),
                ("B_contrast", new Color(0.012f, 0.070f, 0.100f), new Color(0.110f, 0.420f, 0.450f), new Color(0.26f, 0.40f, 0.58f), new Color(0.50f, 0.60f, 0.68f), 0.0f, new Vector3(-0.55f, -0.62f, 0.45f)),
                ("C_lowsun", new Color(0.012f, 0.070f, 0.100f), new Color(0.110f, 0.420f, 0.450f), new Color(0.26f, 0.40f, 0.58f), new Color(0.50f, 0.60f, 0.68f), 0.0f, new Vector3(-0.80f, -0.38f, 0.46f)),
                ("D_sidesun", new Color(0.012f, 0.070f, 0.100f), new Color(0.110f, 0.420f, 0.450f), new Color(0.26f, 0.40f, 0.58f), new Color(0.50f, 0.60f, 0.68f), 0.0f, new Vector3(-0.30f, -0.45f, 0.84f)),
            };
            var sun = RenderSettings.sun;
            var sunRot = sun != null ? sun.transform.rotation : Quaternion.identity;
            double pp = pl.PrintPhase;
            foreach (var (name, deep, lit, top, hor, wrap, dir3) in looks)
            {
                foreach (var mm in new[] { pl.waterMaterial, pl.seaMaterial })
                {
                    mm.SetColor("_Deep", deep); mm.SetColor("_Lit", lit); mm.SetColor("_SkyTop", top); mm.SetColor("_SkyHorizon", hor); mm.SetFloat("_Wrap", wrap);
                }
                if (pl.WaterDoubleSided) pl.ApplyWaterSides();   // 2026-10-17 追記：両面のクリップの水の写しにも同じ色を写す
                if (sun != null) sun.transform.rotation = Quaternion.LookRotation(dir3.normalized, Vector3.up);
                ApplyPoses(pl);
                pl.mode = FLIP3DPlayer.Mode.Print; pl.ApplyTime(pp);
                Save(pl.cam, w, h, Path.Combine(dir, name + "_print.png"), true);
                pl.mode = FLIP3DPlayer.Mode.Seat; pl.ApplyTime(pp + 0.75);
                Save(pl.cam, w, h, Path.Combine(dir, name + "_seat.png"), true);
            }
            m.CopyPropertiesFromMaterial(keep);
            pl.seaMaterial.CopyPropertiesFromMaterial(keep);
            if (pl.WaterDoubleSided) pl.ApplyWaterSides();
            if (sun != null) sun.transform.rotation = sunRot;
            ApplyPoses(pl);
            Debug.Log("FLIP3D_LOOK done " + dir);
        }

        // 確かめの書き出し：Mesh を作るのと同じ関数で読み解いた点・法線・三角形を、記録 0・40・81・95 について書く（Python が元の記録と比べる）
        // 2026-10-16 追記：記録の目次（GW45CLP1・GW45LIST1）から読む。続けて読んでいる時は、輪の読み解き（GPU に送るのと同じ配列）を書く
        static void VerifyExport(FLIP3DPlayer pl, string dir)
        {
            Directory.CreateDirectory(dir);
            var mf = pl.Manifest;
            var x = FLIP3DRecordIndex.Open(pl.CurrentDataDir, mf);
            var sb = new StringBuilder("[");
            byte[] buf = null;
            var recs = new List<int>();
            foreach (int r0 in new[] { 0, 40, mf.print_record_index, mf.frames - 1 }) if (r0 >= 0 && r0 < mf.frames && !recs.Contains(r0)) recs.Add(r0);
            using (var rd = new FLIP3DRecordIndex.Reader(x))
            foreach (int r in recs)
            {
                Vector3[] pos, nrm; int[] idx; double t; int frame;
                if (pl.Stream != null)
                {
                    pl.Stream.CopyDecoded(r, 120000, out pos, out nrm, out idx, out var hh);
                    t = hh.t; frame = hh.frame;
                }
                else
                {
                    rd.Read(r, ref buf);
                    FLIP3DClip.DecodeArrays(buf, 0, out pos, out nrm, out idx, out t, out frame, out _, out _);
                }
                var fp = new float[pos.Length * 3]; var fn = new float[nrm.Length * 3];
                for (int k = 0; k < pos.Length; k++) { fp[3 * k] = pos[k].x; fp[3 * k + 1] = pos[k].y; fp[3 * k + 2] = pos[k].z; fn[3 * k] = nrm[k].x; fn[3 * k + 1] = nrm[k].y; fn[3 * k + 2] = nrm[k].z; }
                var bp = new byte[fp.Length * 4]; Buffer.BlockCopy(fp, 0, bp, 0, bp.Length);
                var bn = new byte[fn.Length * 4]; Buffer.BlockCopy(fn, 0, bn, 0, bn.Length);
                var bi = new byte[idx.Length * 4]; Buffer.BlockCopy(idx, 0, bi, 0, bi.Length);
                File.WriteAllBytes(Path.Combine(dir, "rec" + r + "_pos.f32"), bp);
                File.WriteAllBytes(Path.Combine(dir, "rec" + r + "_nrm.f32"), bn);
                File.WriteAllBytes(Path.Combine(dir, "rec" + r + "_idx.i32"), bi);
                sb.Append(string.Format(IC, "{0}{{\"record\":{1},\"frame\":{2},\"t\":{3},\"nv\":{4},\"nt\":{5},\"path\":\"{6}\"}}", r == recs[0] ? "" : ",", r, frame, t, pos.Length, idx.Length / 3,
                    pl.Stream != null ? "stream" : "preload"));
            }
            sb.Append("]");
            pl.InvalidateWanted();
            File.WriteAllText(Path.Combine(dir, "verify.json"), sb.ToString());
            Debug.Log("FLIP3D_VERIFY done " + dir);
        }

        // 確かめ：キー [4] と同じ ToggleClip で 24 個/s ⇔ 8 個/s を入れ替え、同じ体験の時刻で見せる記録・計算の時刻を書く（2026-10-16 追記）
        static void SwitchCheck(FLIP3DPlayer pl, string dir, int w, int h)
        {
            Directory.CreateDirectory(dir);
            var sb = new StringBuilder("step,data,record_fps,frames,s,phase,record,sim_t\n");
            pl.mode = FLIP3DPlayer.Mode.Seat;
            ApplyPoses(pl);
            double s = 5.3;
            for (int k = 0; k < 3; k++)
            {
                if (k > 0) pl.ToggleClip();
                pl.ApplyTime(s);
                var mf = pl.Manifest;
                sb.AppendLine(string.Format(IC, "{0},{1},{2},{3},{4:F4},{5:F5},{6},{7:F4}", k, pl.CurrentDataDir, mf.record_fps, pl.RecordCount, s, pl.LoopPhase,
                    pl.ShownRecord, mf.loop_start_s + pl.ShownRecord / mf.record_fps));
                Save(pl.cam, w, h, Path.Combine(dir, string.Format(IC, "switch_{0}_fps{1:0}.png", k, mf.record_fps)), true);
            }
            File.WriteAllText(Path.Combine(dir, "switch.csv"), sb.ToString());
            Debug.Log("FLIP3D_SWITCH done " + dir);
        }

        // 確かめ：キー [5]（続けて ⇔ 繰り返し）と同じ SetPlayback を、時計を 0 から始め直す形（RestartClock と同じ）で呼び、見せる記録を書く
        // （2026-10-16 確かめで足した。キーの入力そのものと Play モードは確かめていない。画面外の描画なので記録は待って揃える）
        static void Toggle5Check(FLIP3DPlayer pl, string dir, int w, int h)
        {
            Directory.CreateDirectory(dir);
            pl.mode = FLIP3DPlayer.Mode.Seat;
            ApplyPoses(pl);
            pl.ApplyMoveArgs();
            pl.endAction = FLIP3DPlayer.EndAction.Hold;
            var sb = new StringBuilder("step,playback,s,record,sim_t,sim_frame,ended,streaming\n");
            var steps = new (FLIP3DPlayer.Playback, double)[]
            {
                (FLIP3DPlayer.Playback.Continuous, 0.0), (FLIP3DPlayer.Playback.Continuous, 5.3),
                (FLIP3DPlayer.Playback.Loop, 0.0), (FLIP3DPlayer.Playback.Loop, 5.3),
                (FLIP3DPlayer.Playback.Continuous, 0.0), (FLIP3DPlayer.Playback.Continuous, 5.3), (FLIP3DPlayer.Playback.Continuous, 1e6),
            };
            int k = 0;
            foreach (var (p, s) in steps)
            {
                if (pl.playback != p) pl.SetPlayback(p);
                pl.ApplyTime(s);
                sb.AppendLine(string.Format(IC, "{0},{1},{2:F3},{3},{4:F4},{5},{6},{7}", k, p, s, pl.ShownRecord, pl.ShownSimTime, pl.ShownSimFrame, pl.Ended ? 1 : 0, pl.Streaming ? 1 : 0));
                Save(pl.cam, w, h, Path.Combine(dir, string.Format(IC, "toggle5_{0}_{1}.png", k, p)), true);
                k++;
            }
            File.WriteAllText(Path.Combine(dir, "toggle5.csv"), sb.ToString());
            Debug.Log("FLIP3D_TOGGLE5 done " + dir);
        }

        static void DebugStills(FLIP3DPlayer pl, string dir, int w, int h)
        {
            Directory.CreateDirectory(dir);
            var dbg = new Material(Shader.Find("GreatWave/FLIP3D/Debug"));
            var keep = pl.waterMaterial;
            double pp = pl.PrintPhase;
            foreach (var matName in new[] { "debug", "water" })
            {
                pl.SetWaterMaterial(matName == "debug" ? dbg : keep);
                ApplyPoses(pl);
                pl.mode = FLIP3DPlayer.Mode.Seat;
                foreach (double dt in new[] { -3.0, 0.0 })
                {
                    pl.ApplyTime(((pp + dt) % pl.LoopSeconds + pl.LoopSeconds) % pl.LoopSeconds);
                    Save(pl.cam, w, h, Path.Combine(dir, string.Format(IC, "{0}_seat_dt{1:+0.0;-0.0}.png", matName, dt)), true);
                }
                // 上から（真ん中の頂の上 120 m、真下を見る）
                pl.mode = FLIP3DPlayer.Mode.Print;
                pl.printPos = new Vector3(300, 160, -10); pl.printLookAt = new Vector3(300, 0, -9.9f); pl.printFovV = 60f;
                pl.ApplyTime(pp - 3.0);
                Save(pl.cam, w, h, Path.Combine(dir, matName + "_top_dt-3.png"), true);
            }
            pl.SetWaterMaterial(keep);
            ApplyPoses(pl);
            Debug.Log("FLIP3D_DEBUG done " + dir);
        }

        static void Sequence(FLIP3DPlayer pl, FLIP3DPlayer.Mode mode, double seconds, string dir, int w, int h, double fps)
        {
            Directory.CreateDirectory(dir);
            pl.mode = mode;
            ApplyPoses(pl);
            pl.ApplyMoveArgs();
            pl.SetPlayback(FLIP3DPlayer.Playback.Loop);
            SequenceFrames(pl, seconds, dir, w, h, fps);
        }

        // 繰り返しのクリップの動きを loops 回の繰り返しで（2026-10-17 追記。連番 move3）。位相 0（繰り返しの初め）から始め、座席に -f3dminseat（既定 12 s = うねりの
        // 1 周期。FLIP3DExperience の minSeatSeconds と同じ【選び】）以上いてから moveSeconds で見える動きをし、n 回目の繰り返しの原画に最も近い記録に着いて
        // printHold だけ止め、loops 回目の終わりまで原画の視点に留まる。プレイヤーの繰り返しの Move の式のまま、seatHold・afterSeconds だけをここで決める：
        //   n = ceil((minSeat + moveSeconds − 原画の位相) / 周期)（0〜loops − 1）、seatHold = n × 周期 + 原画の位相 − moveSeconds、afterSeconds = loops × 周期 − (n × 周期 + 原画の位相)
        static void MoveLoops(FLIP3DPlayer pl, int loops, string dir, int w, int h, double fps)
        {
            Directory.CreateDirectory(dir);
            pl.mode = FLIP3DPlayer.Mode.Move;
            ApplyPoses(pl);
            pl.ApplyMoveArgs();
            pl.SetPlayback(FLIP3DPlayer.Playback.Loop);
            double L = pl.LoopSeconds, P = pl.PrintPhase, minSeat = double.Parse(Arg("-f3dminseat", "12"), IC);
            int n = Math.Max(0, Math.Min(loops - 1, (int)Math.Ceiling((minSeat + pl.moveSeconds - P) / L - 1e-9)));
            pl.seatHold = (float)(n * L + P - pl.moveSeconds);
            pl.afterSeconds = (float)(loops * L - (n * L + P));
            if (pl.seatHold < 0f || pl.afterSeconds < 0f) throw new InvalidOperationException("move3：座席・後の時間が負（周期・原画の位相・動きの秒を見直す）");
            Debug.Log(string.Format(IC, "FLIP3D_MOVELOOPS loops={0} n={1} seatHold={2:F3} move={3:F3} hold={4:F3} after={5:F3} total={6:F3} arrive_s={7:F3} print_phase={8:F3}",
                loops, n, pl.seatHold, pl.moveSeconds, pl.printHold, pl.afterSeconds, pl.MoveTotal, pl.seatHold + pl.moveSeconds, P));
            SequenceFrames(pl, pl.MoveTotal, dir, w, h, fps);
            ApplyPoses(pl);
        }

        // 続けて再生の連番（2026-10-16 追記）：範囲の初めから終わりまで 1 回。長さは体験の秒（範囲 + cmove の止め）
        static void ContinuousSequence(FLIP3DPlayer pl, FLIP3DPlayer.Mode mode, string dir, int w, int h, double fps)
        {
            Directory.CreateDirectory(dir);
            pl.mode = mode;
            ApplyPoses(pl);
            pl.ApplyMoveArgs();
            pl.endAction = FLIP3DPlayer.EndAction.Hold;
            pl.SetPlayback(FLIP3DPlayer.Playback.Continuous);
            Debug.Log(string.Format(IC, "FLIP3D_CSEQ mode={0} range={1:F3}-{2:F3} s seconds={3:F3} schedule={4}", mode, pl.PlayFromSim, pl.PlayToSim, pl.ExperienceDuration, pl.ScheduleText));
            SequenceFrames(pl, pl.ExperienceDuration, dir, w, h, fps);
        }

        // 続けて再生の静止画（確かめ用）：予定の各動きの着く瞬間と、その 3 s 前（動きの途中）と、範囲の始め・終わり
        static void ContinuousStills(FLIP3DPlayer pl, string dir, int w, int h)
        {
            Directory.CreateDirectory(dir);
            ApplyPoses(pl);
            pl.ApplyMoveArgs();
            pl.mode = FLIP3DPlayer.Mode.Move;
            pl.endAction = FLIP3DPlayer.EndAction.Hold;
            pl.SetPlayback(FLIP3DPlayer.Playback.Continuous);
            var rows = new StringBuilder("name,s,record,sim_t,frame,frozen,blend\n");
            var shots = new List<(string, double)> { ("start", 0.0), ("end", pl.ExperienceDuration - 1e-6) };
            double held = 0, c0 = pl.PlayFromSim - pl.Manifest.t_first;
            foreach (var e in pl.Moves)
            {
                double sArrive = e.c - c0 + held;                // 体験の時刻（前の止めの分を足す）
                shots.Add(("f" + e.frame + "_minus3s", sArrive - 3.0));
                shots.Add(("f" + e.frame + "_arrive", sArrive));
                held += e.hold;
            }
            foreach (var (name, s) in shots)
            {
                pl.ApplyTime(Math.Max(0, s));
                Save(pl.cam, w, h, Path.Combine(dir, name + ".png"), true);
                rows.AppendLine(string.Format(IC, "{0},{1:F4},{2},{3:F4},{4},{5},{6:F4}", name, s, pl.ShownRecord, pl.ShownSimTime, pl.ShownSimFrame, pl.Frozen ? 1 : 0, pl.CameraBlend));
            }
            File.WriteAllText(Path.Combine(dir, "cstills.csv"), rows.ToString());
            Debug.Log("FLIP3D_CSTILLS done " + dir);
        }

        // 確かめ（2026-10-17 追記、連番 xrcheck）：VR の水の shader の写し（Resources/GreatWaveFLIP3D/FLIP3DWaterXR）を、FLIP3DXR.SwapStereoShaders と同じ写し方
        // （new Material(XR の shader) → CopyPropertiesFromMaterial → 両面の印）で水に入れ替え、座席の数コマを画面外（単眼）で描いて、PC の水の shader の絵と並べて書く。
        // 両面のクリップで印と _GWCull が写り、同じ式で描けるかを見る。HMD・両眼の描画では確かめていない。-f3dxrframes 0,21,50（記録の番号）。終わったら材質を戻す
        static void XrShaderCheck(FLIP3DPlayer pl, string dir, int w, int h)
        {
            Directory.CreateDirectory(dir);
            var sh = Resources.Load<Shader>("GreatWaveFLIP3D/FLIP3DWaterXR");
            if (sh == null || !sh.isSupported) throw new InvalidOperationException("FLIP3DWaterXR が読めない・使えない");
            pl.mode = FLIP3DPlayer.Mode.Seat;
            ApplyPoses(pl);
            pl.SetPlayback(FLIP3DPlayer.Playback.Loop);
            var recs = Arg("-f3dxrframes", "0,21,37,50,52").Split(',').Select(s => int.Parse(s, IC)).ToArray();
            var rows = new StringBuilder("record,sim_frame,shader,keyword,cull,file\n");
            var keep = new Dictionary<MeshRenderer, Material>();
            var copies = new Dictionary<Material, Material>();
            foreach (var r in pl.GetComponentsInChildren<MeshRenderer>(true))
            {
                var m = r.sharedMaterial;
                if (m == null || m.shader == null || m.shader.name != "GreatWave/FLIP3D/Water") continue;
                keep[r] = m;
                if (!copies.ContainsKey(m))
                {
                    var x = new Material(sh) { name = m.name + " (XR check)", hideFlags = HideFlags.DontSave };
                    x.CopyPropertiesFromMaterial(m);
                    if (m.IsKeywordEnabled("GW_WATER_DOUBLE_SIDED")) x.EnableKeyword("GW_WATER_DOUBLE_SIDED");
                    x.renderQueue = m.renderQueue;
                    copies[m] = x;
                }
            }
            foreach (var pass in new[] { "pc", "xr" })
            {
                if (pass == "xr") foreach (var kv in keep) kv.Key.sharedMaterial = copies[kv.Value];
                foreach (int rec in recs)
                {
                    pl.ApplyTime(rec / pl.Manifest.record_fps);
                    string file = string.Format(IC, "{0}_rec{1:D3}.png", pass, rec);
                    Save(pl.cam, w, h, Path.Combine(dir, file), true);
                    var wm = pl.GetComponentsInChildren<MeshRenderer>(true).Select(r => r.sharedMaterial).First(m => m != null && m.HasProperty("_GWCull"));
                    rows.AppendLine(string.Format(IC, "{0},{1},{2},{3},{4},{5}", rec, pl.ShownSimFrame, wm.shader.name, wm.IsKeywordEnabled("GW_WATER_DOUBLE_SIDED") ? 1 : 0,
                        wm.GetFloat("_GWCull"), file));
                }
            }
            foreach (var kv in keep) kv.Key.sharedMaterial = kv.Value;
            foreach (var x in copies.Values) UnityEngine.Object.DestroyImmediate(x);
            File.WriteAllText(Path.Combine(dir, "xrcheck.csv"), rows.ToString());
            Debug.Log("FLIP3D_XRCHECK done " + dir + " shader_messages=" + ShaderUtil.GetShaderMessageCount(sh));
        }

        static void SequenceFrames(FLIP3DPlayer pl, double seconds, string dir, int w, int h, double fps)
        {
            var mode = pl.mode;
            int n = (int)Math.Round(seconds * fps);
            var csv = new StringBuilder("i,s,phase,record,sim_t,frozen,blend,cx,cy,cz,fov,apply_ms,render_ms,wanted,sim_frame,cut,ended\n");
            var mf = pl.Manifest;
            var sw = new System.Diagnostics.Stopwatch();
            for (int i = 0; i < n; i++)
            {
                double s = i / fps;
                sw.Restart();
                pl.ApplyTime(s);
                double ap = sw.Elapsed.TotalMilliseconds;
                sw.Restart();
                Save(pl.cam, w, h, Path.Combine(dir, string.Format(IC, "frame_{0:D5}.jpg", i)), false);
                double rp = sw.Elapsed.TotalMilliseconds;
                var c = pl.cam.transform.position;
                // sim_t は見せた記録の頭の時刻（2026-10-16 から。前は loop_start_s + 記録 / 記録の数/s で、同じ値）
                csv.AppendLine(string.Format(IC, "{0},{1:F5},{2:F5},{3},{4:F4},{5},{6:F4},{7:F3},{8:F3},{9:F3},{10:F2},{11:F3},{12:F2},{13},{14},{15},{16}",
                    i, s, pl.LoopPhase, pl.ShownRecord, pl.ShownSimTime, pl.Frozen ? 1 : 0, pl.CameraBlend, c.x, c.y, c.z, pl.cam.fieldOfView, ap, rp,
                    pl.WantedRecord, pl.ShownSimFrame, pl.InCut ? 1 : 0, pl.Ended ? 1 : 0));
            }
            File.WriteAllText(Path.Combine(dir, "frames.csv"), csv.ToString());
            var mv = new StringBuilder("[");
            foreach (var e in pl.Moves)
                mv.Append(string.Format(IC, "{0}{{\"k\":{1},\"frame\":{2},\"record\":{3},\"sim_t\":{4},\"move\":{5},\"hold\":{6},\"stay\":{7},\"back\":{8}}}",
                    mv.Length > 1 ? "," : "", e.k, e.frame, e.record, mf.t_first + e.c, e.move, e.hold, e.stay, e.back));
            mv.Append("]");
            string capJson = string.Format(IC,
                "{{\"mode\":\"{0}\",\"seconds\":{1},\"fps\":{2},\"frames\":{3},\"size\":\"{4}x{5}\",\"tiles\":{6},\"seatHold\":{7},\"moveSeconds\":{8},\"printHold\":{9},\"afterSeconds\":{10},\"printPhase\":{11},\"printRecord\":{12},\"recordFps\":{13},\"dataDir\":\"{14}\","
                + "\"playback\":\"{15}\",\"playFromSim\":{16},\"playToSim\":{17},\"clipKind\":\"{18}\",\"streaming\":{19},\"ring\":{20},\"moveStay\":{21},\"moveBack\":{22},\"schedule\":\"{23}\",\"moves\":{24},\"records\":{25}}}",
                mode, seconds, fps, n, w, h, pl.tilesPerSide, pl.seatHold, pl.moveSeconds, pl.printHold, pl.afterSeconds, pl.PrintPhase, mf.print_record_index,
                mf.record_fps, (pl.CurrentDataDir ?? "").Replace('\\', '/'),
                pl.playback, pl.PlayFromSim, pl.PlayToSim, string.IsNullOrEmpty(mf.clip_kind) ? "loop" : mf.clip_kind, pl.Streaming ? "true" : "false",
                pl.Streaming ? pl.Stream.RingSize : 0, pl.moveStay, pl.moveBack, pl.ScheduleText, mv.ToString(), pl.RecordCount);
            // 2026-10-17 追記：両面の水のクリップ（manifest の water_double_sided）だけ項目を足す。前のクリップの capture.json は前と同じバイト
            if (pl.WaterDoubleSided) capJson = capJson.Substring(0, capJson.Length - 1) + ",\"waterDoubleSided\":true}";
            File.WriteAllText(Path.Combine(dir, "capture.json"), capJson);
            Debug.Log("FLIP3D_SEQ done " + mode + " " + pl.playback + " frames=" + n + " dir=" + dir);
        }

        static void Save(Camera cam, int w, int h, string path, bool png)
        {
            var desc = new RenderTextureDescriptor(w, h, RenderTextureFormat.ARGB32, 24) { msaaSamples = 4, sRGB = true };
            var rt = RenderTexture.GetTemporary(desc);
            var res = RenderTexture.GetTemporary(new RenderTextureDescriptor(w, h, RenderTextureFormat.ARGB32, 0) { sRGB = true });
            var prev = cam.targetTexture;
            cam.targetTexture = rt;
            cam.Render();
            Graphics.Blit(rt, res);
            var prevA = RenderTexture.active;
            RenderTexture.active = res;
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = prevA;
            cam.targetTexture = prev;
            RenderTexture.ReleaseTemporary(rt);
            RenderTexture.ReleaseTemporary(res);
            File.WriteAllBytes(path, png ? tex.EncodeToPNG() : tex.EncodeToJPG(93));
            UnityEngine.Object.DestroyImmediate(tex);
        }

        [Serializable]
        class BuildRep { public string unity, utc, scene, playerPath, result; public long size; public double seconds; public bool ftBefore, ftRestored; public string[] errors; }

        public static void BuildPlayerAndExit()
        {
            int code = 1;
            try { code = BuildPlayer() ? 0 : 2; }
            catch (Exception e) { Debug.LogError("FLIP3D_BUILD_EXCEPTION " + e); code = 1; }
            EditorApplication.Exit(code);
        }

        // Windows の Release プレイヤー。場面は FLIP3D_Playback.unity だけを引数で渡し、EditorBuildSettings は変えない。
        // PlayerSettings.enableFrameTimingStats はビルドの間だけ true にし、finally で元へ戻す（RT48 と同じ）。
        public static bool BuildPlayer()
        {
            if (!File.Exists(ScenePath)) BuildScene();
            string outDir = Path.GetFullPath(Arg("-f3dplayerout", Path.Combine(BuildRoot, "player")));
            if (!outDir.Replace('\\', '/').Contains("/Build/FLIP3D/")) throw new InvalidOperationException("FLIP3D の外へは書きません：" + outDir);
            Directory.CreateDirectory(outDir);
            var rep = new BuildRep { unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePath };
            bool prev = PlayerSettings.enableFrameTimingStats;
            rep.ftBefore = prev;
            BuildReport br;
            try
            {
                PlayerSettings.enableFrameTimingStats = true;
                br = BuildPipeline.BuildPlayer(new BuildPlayerOptions
                {
                    scenes = new[] { ScenePath }, locationPathName = Path.Combine(outDir, "FLIP3D.exe"),
                    target = BuildTarget.StandaloneWindows64, targetGroup = BuildTargetGroup.Standalone, options = BuildOptions.None
                });
            }
            finally
            {
                PlayerSettings.enableFrameTimingStats = prev;
                AssetDatabase.SaveAssets();
                rep.ftRestored = PlayerSettings.enableFrameTimingStats == prev;
            }
            rep.playerPath = Path.Combine(outDir, "FLIP3D.exe");
            rep.result = br.summary.result.ToString();
            rep.size = (long)br.summary.totalSize;
            rep.seconds = br.summary.totalTime.TotalSeconds;
            rep.errors = br.steps.SelectMany(s => s.messages).Where(m => m.type == LogType.Error || m.type == LogType.Exception).Select(m => m.content).ToArray();
            File.WriteAllText(Path.Combine(outDir, "flip3d_build_report.json"), JsonUtility.ToJson(rep, true));
            Debug.Log("FLIP3D_BUILD_DONE result=" + rep.result + " size=" + rep.size + " restored=" + rep.ftRestored);
            return br.summary.result == BuildResult.Succeeded && rep.ftRestored;
        }
    }
}
