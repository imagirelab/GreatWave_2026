using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design42.EditorTools
{
    // 設計42：静水で重量・排水容積・重心を合わせ、外力の後の戻りを確かめる（PC の batchmode。HMD 実機ではない）。
    //   Run. 新しい場面（原画視点の場面 DS41_Boats.unity は開かない）に、静水の水面と、設計41 のプレハブ（座席の船の縮尺 s）を子に持つ物理の根
    //        （Rigidbody ＋ DS42Buoyancy）を置き、DS42_Buoyancy.unity として保存する（船は Python の厳密な釣り合いの姿勢）。
    //        続けて、物理を手で進める（Physics.simulationMode = Script、dt = 1/120 s）：
    //          0 s   平衡から 0.15 m 上・横 6°・縦 2° で放す → 7〜8 s の平均を釣り合いの値にする
    //          8 s   下向きの力積（上下の戻り）、14 s 横揺れの力積、22 s 縦揺れの力積
    //          28〜36 s 一定の横のモーメント 824 N·m（人が船縁へ寄った時の代わり）→ 静的な横傾斜を GM の予測と比べる → 36 s に外して戻り
    //        30 fps ごとに、2 つの視点（左舷の船首寄り・船尾の真後ろ）を 960×540 の JPG で書き、値（喫水・傾き・浮力点の力の和・
    //        浮力用の閉じた船体を水面で切った厳密な容積・浮心・重心）を記録する。動画と図は ds42_report.py が作る。
    public static class DS42BuoyancyTest
    {
        const string CfgPath = "Assets/GreatWave/Design42/Data/ds42_buoyancy_points.json";
        const string PrefabPath = "Assets/GreatWave/Design41/Prefabs/DS41_Oshiokuri.prefab";
        const string ScenePath = "Assets/GreatWave/Design42/Scenes/DS42_Buoyancy.unity";
        const string MatDir = "Assets/GreatWave/Design42/Materials";
        const string MatOchre = "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_boat_ochre.mat";
        const string MatAiDark = "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_ai_dark.mat";
        const string OutRoot = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/42/buoyancy";
        const string ParamsPath = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/ds42/ds42_params.json";
        const int FW = 960, FH = 540;

        static string[] Protected => new[] {
            "Assets/GreatWave/Design41/Scenes/DS41_Boats.unity", PrefabPath, "Assets/GreatWave/Design41/Models/ds41_oshiokuri.fbx",
            "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity", MatOchre, MatAiDark,
            "Assets/GreatWave/Design30/Scripts/DS30BoatHeave.cs", "Build/Design/30/sea/boat_support.json", "../Tools/GWContext/seat_v1.json" };

        [Serializable] class TestPrm
        {
            public float dt_s, fps, total_s, start_offset_m, start_heel_deg, start_trim_deg;
            public float[] eq_window_s;
            public float heave_push_t, heave_push_target_m, roll_push_t, roll_push_target_deg, pitch_push_t, pitch_push_target_deg;
            public float static_heel_from_t, static_heel_to_t, static_heel_moment_Nm;
        }
        [Serializable] class PrmRoot { public TestPrm test; }

        [Serializable] class Series
        {
            public List<float> t = new List<float>(), keelY = new List<float>(), draft = new List<float>(), heel = new List<float>(), trim = new List<float>(), yaw = new List<float>();
            public List<float> posX = new List<float>(), posZ = new List<float>(), sumF = new List<float>(), dampF = new List<float>(), vPoints = new List<float>(), vExact = new List<float>();
            public List<float> cbX = new List<float>(), cbY = new List<float>(), cbZ = new List<float>(), cgX = new List<float>(), cgY = new List<float>(), cgZ = new List<float>();
            public List<float> torque = new List<float>();
            public List<int> wet = new List<int>();
        }
        [Serializable] class Event { public string name; public float t, value; public string unit, noteJa; }
        [Serializable] class Report
        {
            public string unity, device, graphicsApi, colorSpace, utc, scene, sceneSha256, cfg, cfgSha256, paramsSha256, prefabSha256, noteJa;
            public float massKg, dt, g, rho, scale, meshVolumeFullM3, stepMicrosecondsMean, secondsTotal;
            public Vector3 centerOfMassLocal, inertiaTensor, gravity; public Quaternion inertiaRot;
            public float eqDraftPython, eqTrimPython, eqHeelPython, eqKeelHeightPython;
            public Event[] events; public string[] frames; public string[] stills;
            public int frameCount, pointCount; public Vector3[] pointsLocal;
            public bool protectedUnchanged; public string[] changedFiles; public string simulationModeBefore, simulationModeAfter;
        }

        public static void Run()
        {
            var total = Stopwatch.StartNew();
            var before = Protected.ToDictionary(p => p, Sha);
            AssetDatabase.Refresh();
            var prm = JsonUtility.FromJson<PrmRoot>(File.ReadAllText(ParamsPath)).test;
            var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(CfgPath);
            if (cfgAsset == null) throw new InvalidOperationException("浮力点の表がありません: " + CfgPath);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
            Directory.CreateDirectory(OutRoot);
            string frameDir = OutRoot + "/frames";
            if (Directory.Exists(frameDir)) Directory.Delete(frameDir, true);
            Directory.CreateDirectory(frameDir);

            var modeBefore = Physics.simulationMode;
            var gravityBefore = Physics.gravity;
            var rep = new Report
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), utc = DateTime.UtcNow.ToString("O"), cfg = CfgPath, cfgSha256 = Sha(CfgPath),
                paramsSha256 = Sha(ParamsPath), prefabSha256 = Sha(PrefabPath), simulationModeBefore = modeBefore.ToString()
            };
            var events = new List<Event>();
            var frames = new List<string>();
            var stills = new List<string>();
            var ser = new Series();
            RenderTexture rtA = null, rtR = null; Texture2D tex = null;
            try
            {
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                Directory.CreateDirectory(MatDir);
                var ochre = AssetDatabase.LoadAssetAtPath<Material>(MatOchre).GetColor("_Color");
                var dark = AssetDatabase.LoadAssetAtPath<Material>(MatAiDark).GetColor("_Color");
                var mWood = MakeMat("DS42_Test_Wood", "Standard", ochre, false);
                var mDark = MakeMat("DS42_Test_Dark", "Standard", dark, false);
                var mWater = MakeMat("DS42_Test_Water", "Standard", new Color(0.10f, 0.28f, 0.50f, 0.72f), true);
                var mPoint = MakeMat("DS42_Test_Point", "Unlit/Color", new Color(0.85f, 0.1f, 0.1f, 1f), false);

                RenderSettings.ambientMode = AmbientMode.Flat; RenderSettings.ambientLight = new Color(0.45f, 0.45f, 0.45f);
                var sun = new GameObject("DS42 光").AddComponent<Light>(); sun.type = LightType.Directional; sun.intensity = 1.0f;
                sun.transform.rotation = Quaternion.Euler(50f, -40f, 0f); sun.shadows = LightShadows.None;

                // 静水
                var waterGo = new GameObject("DS42 静水（y = 0）");
                var water = waterGo.AddComponent<DS42StillWater>();
                var plane = GameObject.CreatePrimitive(PrimitiveType.Plane);
                UnityEngine.Object.DestroyImmediate(plane.GetComponent<Collider>());
                plane.name = "DS42 静水の面"; plane.transform.SetParent(waterGo.transform, false); plane.transform.localScale = new Vector3(300f, 1f, 300f);
                plane.GetComponent<MeshRenderer>().sharedMaterial = mWater;

                // 物理の根（縮尺 1）＋表示のモデル（縮尺 s）
                var root = new GameObject("DS42 船（物理の根）");
                var rb = root.AddComponent<Rigidbody>();
                var buoy = root.AddComponent<DS42Buoyancy>();
                buoy.pointsJson = cfgAsset; buoy.water = water; buoy.stepInFixedUpdate = true;
                buoy.Init();
                var cfg = buoy.Cfg;
                var model = (GameObject)PrefabUtility.InstantiatePrefab(prefab, root.transform);
                model.transform.localPosition = Vector3.zero; model.transform.localRotation = Quaternion.identity; model.transform.localScale = Vector3.one * cfg.scale;
                foreach (var mr in model.GetComponentsInChildren<MeshRenderer>(true))
                    mr.sharedMaterials = mr.sharedMaterials.Select(m => m != null && m.name.Contains("ai_dark") ? mDark : mWood).ToArray();
                buoy.ApplyMass();
                for (int k = 0; k < cfg.pointCount; k++)
                {
                    var s = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                    UnityEngine.Object.DestroyImmediate(s.GetComponent<Collider>());
                    s.name = "DS42 浮力点 " + k; s.transform.SetParent(root.transform, false);
                    s.transform.localPosition = buoy.PointLocal(k); s.transform.localScale = Vector3.one * 0.12f;
                    s.GetComponent<MeshRenderer>().sharedMaterial = mPoint;
                }
                var eqRot = Quaternion.Euler(-cfg.eqTrimDeg, 0f, -cfg.eqHeelDeg);
                root.transform.SetPositionAndRotation(new Vector3(0f, cfg.eqKeelHeightM, 0f), eqRot);

                // カメラ（世界に固定）
                var camA = MakeCam("DS42 カメラ 左舷の船首寄り", new Vector3(-10.5f, 1.6f, 6.0f), new Vector3(0f, 0.35f, 0.2f), 38f);
                var camB = MakeCam("DS42 カメラ 船尾の真後ろ", new Vector3(0f, 1.2f, -19f), new Vector3(0f, 0.75f, 0f), 14f);

                Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
                if (!EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(), ScenePath)) throw new InvalidOperationException("場面を保存できません");
                rep.scene = ScenePath; rep.sceneSha256 = Sha(ScenePath);

                // 釣り合いの姿勢の静止画（Python の厳密な値の姿勢。物理を進める前）
                stills.Add(CapturePng(camA, 1920, 1080, OutRoot + "/still_python_eq_port_bow.png"));
                stills.Add(CapturePng(camB, 1920, 1080, OutRoot + "/still_python_eq_stern.png"));

                // 浮力用の閉じた船体（厳密な容積の検査）
                var bmf = model.GetComponentsInChildren<MeshFilter>(true).First(m => m.name == "Boat41_Buoyancy");
                var bv = bmf.sharedMesh.vertices; var bt = bmf.sharedMesh.triangles;
                var bw = new Vector3[bv.Length];
                Func<Vector3[]> worldVerts = () => { for (int i = 0; i < bv.Length; i++) bw[i] = bmf.transform.TransformPoint(bv[i]); return bw; };
                float full = DS42Buoyancy.SubmergedVolume(worldVerts(), bt, 1e4f, out _);
                float sign = Mathf.Sign(full);
                rep.meshVolumeFullM3 = Mathf.Abs(full);

                // ---- 物理を手で進める
                Physics.simulationMode = SimulationMode.Script;
                gravityBefore = Physics.gravity;
                Physics.gravity = new Vector3(0f, -cfg.g, 0f);
                buoy.ApplyMass();
                buoy.stepInFixedUpdate = false;
                float dt = prm.dt_s;
                root.transform.SetPositionAndRotation(new Vector3(0f, cfg.eqKeelHeightM + prm.start_offset_m, 0f), Quaternion.Euler(-prm.start_trim_deg, 0f, -prm.start_heel_deg));
                rb.position = root.transform.position; rb.rotation = root.transform.rotation;
                rb.linearVelocity = Vector3.zero; rb.angularVelocity = Vector3.zero;
                Physics.SyncTransforms();
                int steps = Mathf.RoundToInt(prm.total_s / dt);
                int every = Mathf.Max(1, Mathf.RoundToInt(1f / (prm.fps * dt)));
                float wH = 2f * Mathf.PI / cfg.periodsS[0], wR = 2f * Mathf.PI / cfg.periodsS[1], wP = 2f * Mathf.PI / cfg.periodsS[2];
                bool pushH = false, pushR = false, pushP = false;
                var stepSw = new Stopwatch(); long stepCount = 0;
                rtA = new RenderTexture(FW, FH, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
                rtR = new RenderTexture(FW, FH, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                rtA.Create(); rtR.Create();
                tex = new Texture2D(FW, FH, TextureFormat.RGB24, false);
                int fi = 0;
                for (int i = 0; i <= steps; i++)
                {
                    float t = i * dt;
                    if (i % every == 0)
                    {
                        Sample(ser, t, root.transform, rb, buoy, water, worldVerts, bt, sign);
                        string a = string.Format(CultureInfo.InvariantCulture, "{0}/a_{1:D5}.jpg", frameDir, fi);
                        string b = string.Format(CultureInfo.InvariantCulture, "{0}/b_{1:D5}.jpg", frameDir, fi);
                        CaptureJpg(camA, rtA, rtR, tex, a); CaptureJpg(camB, rtA, rtR, tex, b);
                        frames.Add(Path.GetFileName(a)); fi++;
                    }
                    if (i == steps) break;
                    if (!pushH && t >= prm.heave_push_t - 1e-6f)
                    {
                        float j = cfg.massKg * prm.heave_push_target_m * wH;
                        rb.AddForce(Vector3.down * j, ForceMode.Impulse); pushH = true;
                        events.Add(new Event { name = "heave_push", t = t, value = j, unit = "N·s", noteJa = "重心へ下向きの力積（目標の沈み " + prm.heave_push_target_m + " m、減衰なしの見積もり）" });
                    }
                    if (!pushR && t >= prm.roll_push_t - 1e-6f)
                    {
                        float j = cfg.inertiaWorldAxes[2] * wR * prm.roll_push_target_deg * Mathf.Deg2Rad;
                        rb.AddTorque(root.transform.forward * j, ForceMode.Impulse); pushR = true;
                        events.Add(new Event { name = "roll_push", t = t, value = j, unit = "N·m·s", noteJa = "船首尾の軸まわりの角力積（目標 " + prm.roll_push_target_deg + "°、減衰なしの見積もり）" });
                    }
                    if (!pushP && t >= prm.pitch_push_t - 1e-6f)
                    {
                        float j = cfg.inertiaWorldAxes[0] * wP * prm.pitch_push_target_deg * Mathf.Deg2Rad;
                        rb.AddTorque(root.transform.right * j, ForceMode.Impulse); pushP = true;
                        events.Add(new Event { name = "pitch_push", t = t, value = j, unit = "N·m·s", noteJa = "左右の軸まわりの角力積（目標 " + prm.pitch_push_target_deg + "°、減衰なしの見積もり）" });
                    }
                    bool st = t >= prm.static_heel_from_t - 1e-6f && t < prm.static_heel_to_t - 1e-6f;
                    buoy.externalTorque = st ? root.transform.forward * -prm.static_heel_moment_Nm : Vector3.zero;   // 右舷を下げる向き
                    stepSw.Start();
                    buoy.Step(dt);
                    stepSw.Stop(); stepCount++;
                    Physics.Simulate(dt);
                }
                events.Add(new Event { name = "static_heel_moment", t = prm.static_heel_from_t, value = prm.static_heel_moment_Nm, unit = "N·m",
                    noteJa = "一定の横のモーメント（右舷を下げる向き）を " + prm.static_heel_from_t + "〜" + prm.static_heel_to_t + " s に与えた" });
                rep.stepMicrosecondsMean = (float)(stepSw.Elapsed.TotalMilliseconds * 1000.0 / Math.Max(1, stepCount));
                rep.frameCount = fi; rep.dt = dt;
                rep.massKg = rb.mass; rep.centerOfMassLocal = rb.centerOfMass; rep.inertiaTensor = rb.inertiaTensor; rep.inertiaRot = rb.inertiaTensorRotation;
                rep.gravity = Physics.gravity; rep.g = cfg.g; rep.rho = cfg.rho; rep.scale = cfg.scale;
                rep.eqDraftPython = cfg.eqDraftMidM; rep.eqTrimPython = cfg.eqTrimDeg; rep.eqHeelPython = cfg.eqHeelDeg; rep.eqKeelHeightPython = cfg.eqKeelHeightM;
                rep.pointCount = cfg.pointCount; rep.pointsLocal = Enumerable.Range(0, cfg.pointCount).Select(k => buoy.PointLocal(k)).ToArray();
                // 最後の姿勢の静止画（戻った後）
                stills.Add(CapturePng(camA, 1920, 1080, OutRoot + "/still_unity_end_port_bow.png"));
                stills.Add(CapturePng(camB, 1920, 1080, OutRoot + "/still_unity_end_stern.png"));
            }
            finally
            {
                Physics.simulationMode = modeBefore;
                Physics.gravity = gravityBefore;
                rep.simulationModeAfter = Physics.simulationMode.ToString();
                if (rtA != null) { rtA.Release(); UnityEngine.Object.DestroyImmediate(rtA); }
                if (rtR != null) { rtR.Release(); UnityEngine.Object.DestroyImmediate(rtR); }
                if (tex != null) UnityEngine.Object.DestroyImmediate(tex);
            }
            // 場面は保存した時の状態のまま（物理を進めた後の姿勢は保存しない）
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            AssetDatabase.Refresh();
            var after = Protected.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = Protected.All(p => before[p] == after[p]);
            rep.changedFiles = Protected.Where(p => before[p] != after[p]).ToArray();
            rep.events = events.ToArray(); rep.frames = new[] { frames.FirstOrDefault(), frames.LastOrDefault() }; rep.stills = stills.ToArray();
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            rep.noteJa = "PC の batchmode の描画（HMD 実機ではない）。物理は Physics.simulationMode = Script で手で進め、終わりに元の設定へ戻した。" +
                         "vExact は浮力用の閉じた船体（Boat41_Buoyancy、Unity の頂点）を水面で切った容積で、浮力点の表（vPoints）とは別の計算。" +
                         "draft は船体中央の船底（物理の根の原点）の水面からの深さ（鉛直）。heel は右舷が下がる向き、trim は船首が上がる向きが正（度）。";
            File.WriteAllText(OutRoot + "/ds42_unity_series.json", JsonUtility.ToJson(ser), new UTF8Encoding(false));
            File.WriteAllText(OutRoot + "/ds42_unity_report.json", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            UnityEngine.Debug.Log("DS42_TEST_DONE frames=" + rep.frameCount + " protectedUnchanged=" + rep.protectedUnchanged + " stepUs=" +
                                  rep.stepMicrosecondsMean.ToString("0.0", CultureInfo.InvariantCulture) + " seconds=" + rep.secondsTotal.ToString("0.0", CultureInfo.InvariantCulture));
            if (!rep.protectedUnchanged) EditorApplication.Exit(4);
        }

        static void Sample(Series s, float t, Transform tr, Rigidbody rb, DS42Buoyancy buoy, DS42Water water, Func<Vector3[]> worldVerts, int[] tri, float sign)
        {
            var p = tr.position;
            float level = water.HeightAt(p);
            s.t.Add(t); s.keelY.Add(p.y); s.draft.Add(level - p.y);
            s.heel.Add(Mathf.Asin(Mathf.Clamp(-tr.right.y, -1f, 1f)) * Mathf.Rad2Deg);
            s.trim.Add(Mathf.Asin(Mathf.Clamp(tr.forward.y, -1f, 1f)) * Mathf.Rad2Deg);
            s.yaw.Add(Mathf.Atan2(tr.forward.x, tr.forward.z) * Mathf.Rad2Deg);
            s.posX.Add(p.x); s.posZ.Add(p.z);
            s.sumF.Add(buoy.LastBuoyancyN); s.dampF.Add(buoy.LastDampingN); s.vPoints.Add(buoy.LastVolumeM3); s.wet.Add(buoy.LastWetPoints);
            float v = sign * DS42Buoyancy.SubmergedVolume(worldVerts(), tri, level, out var cb);
            s.vExact.Add(v); s.cbX.Add(cb.x); s.cbY.Add(cb.y); s.cbZ.Add(cb.z);
            var cg = rb.worldCenterOfMass; s.cgX.Add(cg.x); s.cgY.Add(cg.y); s.cgZ.Add(cg.z);
            s.torque.Add(Vector3.Dot(buoy.externalTorque, tr.forward));
        }

        static Material MakeMat(string name, string shader, Color c, bool transparent)
        {
            string path = MatDir + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            bool create = m == null;
            if (create) m = new Material(Shader.Find(shader));
            m.shader = Shader.Find(shader);
            m.color = c;
            if (shader == "Standard")
            {
                m.SetFloat("_Glossiness", 0.1f);
                if (transparent)
                {
                    m.SetFloat("_Mode", 3f);
                    m.SetInt("_SrcBlend", (int)BlendMode.One); m.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha); m.SetInt("_ZWrite", 0);
                    m.DisableKeyword("_ALPHATEST_ON"); m.DisableKeyword("_ALPHABLEND_ON"); m.EnableKeyword("_ALPHAPREMULTIPLY_ON");
                    m.renderQueue = (int)RenderQueue.Transparent;
                }
            }
            if (create) AssetDatabase.CreateAsset(m, path); else EditorUtility.SetDirty(m);
            AssetDatabase.SaveAssets();
            return m;
        }

        static Camera MakeCam(string name, Vector3 pos, Vector3 target, float fov)
        {
            var go = new GameObject(name);
            var cam = go.AddComponent<Camera>();
            go.transform.position = pos; go.transform.LookAt(target, Vector3.up);
            cam.fieldOfView = fov; cam.nearClipPlane = 0.1f; cam.farClipPlane = 5000f;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(0.93f, 0.89f, 0.80f, 1f);
            cam.allowHDR = false; cam.enabled = false;
            return cam;
        }

        static void CaptureJpg(Camera cam, RenderTexture rt, RenderTexture res, Texture2D tex, string path)
        {
            cam.aspect = (float)FW / FH; cam.targetTexture = rt; cam.Render(); cam.targetTexture = null;
            Graphics.Blit(rt, res);
            RenderTexture.active = res; tex.ReadPixels(new Rect(0, 0, FW, FH), 0, 0); tex.Apply(); RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToJPG(92));
        }

        static string CapturePng(Camera cam, int w, int h, string path)
        {
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rt.Create(); res.Create();
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            float asp = cam.aspect;
            cam.aspect = (float)w / h; cam.targetTexture = rt; cam.Render(); cam.targetTexture = null; cam.aspect = asp;
            Graphics.Blit(rt, res);
            RenderTexture.active = res; tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply(); RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToPNG());
            rt.Release(); res.Release(); UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res); UnityEngine.Object.DestroyImmediate(tex);
            return path;
        }

        static string Sha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
