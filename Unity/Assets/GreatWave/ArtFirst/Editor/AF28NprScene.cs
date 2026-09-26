using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.ArtFirst.EditorTools
{
    // 番号28「色面の正解、SDF 投影ベイク、NPR shader v1」の Unity 側。
    // 1) Build：M1 Revision01 の構図シーンを別名 AF28_NPR.unity で複製し（番号24・26 と同じ手順）、旧い静止波・斜面・白帯・爪を
    //    新シーンだけで非表示にして、番号26 の K*（30°／45°／60°）に NPR shader v1 と外殻線 v0 を付けて置く。
    // 2) Bake：AF28ProjectionBaker（計画の GWProjectionBaker）で 3 案とも焼き込み用 UV（UV3）の色区テクスチャを焼く。
    // 3) Render：Camera.Render → RenderTexture → PNG（PC のオフスクリーン描画。HMD 実機ではない）。
    //    原画視点（全体・主役波だけ）、評価器用の色区 ID（3840×2160、主役波だけ、アンチエイリアスなし）、外殻線の ID、船上座席、側面、背面。
    public static class AF28NprScene
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF28_NPR.unity";
        const string MaterialDir = "Assets/GreatWave/ArtFirst/Materials";
        const string OutRoot = AF28ProjectionBaker.BuildRoot;
        const string LayoutJson = "../Docs/Evidence/M1/Revision01/15_revision_layout.json";
        const string KStarDir = "Build/ArtFirst/26/kstar";
        const int W = 1920, H = 1080;

        // PaintingCam v1（Tools/PaintingTruth/painting_truth.json と同じ値）と、番号26 と同じ確認用の視点
        static readonly Vector3 PaintingPosition = new Vector3(0, 3, -62);
        static readonly Vector3 PaintingTarget = new Vector3(-2.5f, 9.7f, 4);
        static readonly Vector3 BoatTarget = new Vector3(-7, 5, 3);
        const float BoatFov = 80;
        static readonly Vector3 SidePosition = new Vector3(53, 22, -2);
        static readonly Vector3 SideTarget = new Vector3(-1, 7, 0);
        const float SideFov = 60;
        static readonly Vector3 BackPosition = new Vector3(-45, 30, 60);
        static readonly Vector3 BackTarget = new Vector3(-5, 8, -3);
        const float BackFov = 50;
        static readonly Color32 SkyTop = new Color32(249, 232, 196, 255);   // 番号23 調色板 v0.2「空上」
        static readonly Color IdSky = new Color(1, 1, 1);

        public static void BakeBuildAndRender() { Build(); Bake(); Render(); CheckStereoVariants(); }

        // SPI（Single Pass Instanced）などの立体視の変種が D3D11 でコンパイルできるかを確かめる（描画はしない。立体視の描画は未確認）。
        public static void CheckStereoVariants()
        {
            var list = new List<VariantCheck>();
            var sets = new[] { new string[0], new[] { "INSTANCING_ON" }, new[] { "STEREO_INSTANCING_ON", "INSTANCING_ON" }, new[] { "UNITY_SINGLE_PASS_STEREO" }, new[] { "STEREO_MULTIVIEW_ON" } };
            foreach (var name in new[] { "GreatWave/ArtFirst/AF28 NPR v1", "GreatWave/ArtFirst/AF28 Outline v0" })
            {
                var sh = Shader.Find(name);
                if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + name);
                var pass = ShaderUtil.GetShaderData(sh).GetSubshader(0).GetPass(0);
                foreach (var kw in sets)
                    foreach (var st in new[] { UnityEditor.Rendering.ShaderType.Vertex, UnityEditor.Rendering.ShaderType.Fragment })
                    {
                        var info = pass.CompileVariant(st, kw, UnityEditor.Rendering.ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64);
                        list.Add(new VariantCheck { shader = name, keywords = string.Join(" ", kw), stage = st.ToString(), success = info.Success,
                            messages = string.Join(" | ", info.Messages.Select(m => m.severity + ": " + m.message)) });
                    }
            }
            var rep = new VariantReport { unity = Application.unityVersion, platform = "D3D（StandaloneWindows64）", items = list.ToArray(), allSuccess = list.All(x => x.success),
                noteJa = "ShaderData.Pass.CompileVariant でコンパイルだけを行った。立体視での描画・両眼の画像は確かめていない（番号32 の Mock と番号34 の HMD で確かめる）。" };
            File.WriteAllText(OutRoot + "/af28_spi_compile.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("AF28_SPI_COMPILE allSuccess=" + rep.allSuccess);
        }

        [Serializable] class VariantCheck { public string shader, keywords, stage, messages; public bool success; }
        [Serializable] class VariantReport { public string unity, platform, noteJa; public bool allSuccess; public VariantCheck[] items; }

        static Color C(int[] rgb) => new Color32((byte)rgb[0], (byte)rgb[1], (byte)rgb[2], 255);

        public static void Build()
        {
            var meta = AF28ProjectionBaker.LoadMeta();
            string source = GreatWave.Editor.M1RevisionBuilder.ScenePath;
            string sourceHashBefore = AF28ProjectionBaker.Sha(source);
            var scene = EditorSceneManager.OpenScene(source, OpenSceneMode.Single);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("新シーンを保存できません。");
            scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);

            var hidden = new List<string>();
            HideRoot("M1 main wave - static geometry", hidden);
            HideRoot("M1 Revision01 static supporting slopes", hidden);
            HideRoot("M1 Revision01 provisional region overlay", hidden);
            var foam = GameObject.Find("M1 static foam and foreground swell");
            if (foam == null) throw new InvalidOperationException("旧い白波の親が見つかりません。");
            foreach (var t in foam.GetComponentsInChildren<Transform>(true))
                if (t.name.StartsWith("M1_Foam_FrontRibbon") || t.name.StartsWith("M1_Foam_Claw"))
                    if (t.gameObject.activeSelf) { t.gameObject.SetActive(false); hidden.Add(PathOf(t)); }

            Directory.CreateDirectory(MaterialDir);
            var npr = MaterialAsset("AF28_NPR", "GreatWave/ArtFirst/AF28 NPR v1");
            SetPalette(npr, meta);
            npr.SetFloat("_FlatClass", -1);
            var seaFlat = MaterialAsset("AF28_SeaFlat", "GreatWave/ArtFirst/AF28 NPR v1");
            SetPalette(seaFlat, meta);
            seaFlat.SetFloat("_FlatClass", 3);   // 参照海面は藍濃の平塗り
            var outline = MaterialAsset("AF28_Outline", "GreatWave/ArtFirst/AF28 Outline v0");
            outline.SetColor("_LineColor", C(meta.lineColor));
            outline.SetFloat("_LineAngle", meta.lineAngleRad);
            outline.SetFloat("_MinWidth", meta.lineMinM);
            outline.SetFloat("_MaxWidth", meta.lineMaxM);
            foreach (var m in new[] { npr, seaFlat, outline }) EditorUtility.SetDirty(m);
            var sea = GameObject.Find("M1 flat reference sea");
            if (sea == null) throw new InvalidOperationException("参照海面が見つかりません。");
            sea.GetComponent<Renderer>().sharedMaterial = seaFlat;

            foreach (var k in meta.keys)
            {
                string name = "AF28 K* " + k;
                var old = GameObject.Find(name);
                if (old != null) UnityEngine.Object.DestroyImmediate(old);
                var wave = new GameObject(name);
                wave.AddComponent<MeshFilter>();
                var r = wave.AddComponent<MeshRenderer>();
                r.sharedMaterial = npr;
                r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
                r.lightProbeUsage = LightProbeUsage.Off; r.reflectionProbeUsage = ReflectionProbeUsage.Off;
                var km = wave.AddComponent<AF26KStarMesh>();
                km.dataPath = KStarDir + "/kstar_" + k + ".gwb";
                var line = new GameObject("AF28 外殻線 v0");
                line.transform.SetParent(wave.transform, false);
                line.AddComponent<MeshFilter>();
                var lr = line.AddComponent<MeshRenderer>();
                lr.sharedMaterial = outline;
                lr.shadowCastingMode = ShadowCastingMode.Off; lr.receiveShadows = false;
                lr.lightProbeUsage = LightProbeUsage.Off; lr.reflectionProbeUsage = ReflectionProbeUsage.Off;
                var nw = wave.AddComponent<AF28NprWave>();
                nw.sdfPath = OutRoot + "/bake/af28_uvsdf_" + k + ".bin";
                nw.warpPath = OutRoot + "/bake/af28_uvwarp_" + k + ".json";
                nw.size = meta.texSize;
                nw.outline = lr;
                wave.SetActive(k == "a45");   // 既定は 45°（作業計画 D6 の既定値・利用者未回答）
            }

            var layout = JsonUtility.FromJson<Layout>(File.ReadAllText(LayoutJson));
            MakeCamera("AF28 PaintingCam v1", PaintingPosition, PaintingTarget, 26);
            MakeCamera("AF28 船上座席カメラ", layout.eyeWorld, BoatTarget, BoatFov);
            MakeCamera("AF28 側面カメラ", SidePosition, SideTarget, SideFov);
            MakeCamera("AF28 背面カメラ", BackPosition, BackTarget, BackFov);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene)) throw new InvalidOperationException("新シーンを保存できません。");
            AssetDatabase.SaveAssets();
            string sourceHashAfter = AF28ProjectionBaker.Sha(source);
            var report = new BuildReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), sourceScene = source, scene = ScenePath,
                sourceSceneSha256Before = sourceHashBefore, sourceSceneSha256After = sourceHashAfter,
                sourceSceneUnchanged = sourceHashBefore == sourceHashAfter, hiddenObjects = hidden.ToArray(), eyeWorld = layout.eyeWorld,
                sceneSha256 = AF28ProjectionBaker.Sha(ScenePath)
            };
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/af28_build_report.json", JsonUtility.ToJson(report, true));
            if (!report.sourceSceneUnchanged) throw new InvalidOperationException("元の M1 Revision01 シーンが変わりました。");
            UnityEngine.Debug.Log("AF28_BUILD_DONE hidden=" + hidden.Count);
        }

        public static void Bake()
        {
            var meta = AF28ProjectionBaker.LoadMeta();
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var cam = FindCamera("AF28 PaintingCam v1");
            foreach (var k in meta.kstar)
            {
                var go = FindRoot("AF28 K* " + k.key);
                var km = go.GetComponent<AF26KStarMesh>();
                var mesh = km.EnsureLoaded();
                AF28NprWave.ApplyWarp(mesh, km.nu, km.nv, k.uWarp, k.vWarp);   // 焼き込み用 UV（UV3）
                if (go.transform.localToWorldMatrix != Matrix4x4.identity) throw new InvalidOperationException("K* の変換が単位行列ではありません。");
                AF28ProjectionBaker.Bake(meta, k, mesh, cam);
            }
            UnityEngine.Debug.Log("AF28_BAKE_ALL_DONE");
        }

        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var meta = AF28ProjectionBaker.LoadMeta();
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var roots = EditorSceneManager.GetActiveScene().GetRootGameObjects();
            var waves = meta.keys.Select(k => FindRoot("AF28 K* " + k)).ToArray();
            var cams = new Dictionary<string, Camera>
            {
                { "painting", FindCamera("AF28 PaintingCam v1") }, { "boat", FindCamera("AF28 船上座席カメラ") },
                { "side", FindCamera("AF28 側面カメラ") }, { "back", FindCamera("AF28 背面カメラ") }
            };
            var report = new RenderReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), startedUtc = DateTime.UtcNow.ToString("O"),
                renderMethod = "Editor batchmode：Camera.Render → RenderTexture → ReadPixels → PNG。色は sRGB の RT（MSAA 8x → 解決）、ID は線形の RT（MSAA なし）。PC のオフスクリーン描画で、HMD 実機ではない。"
            };
            var items = new List<RenderItem>();
            var initial = roots.ToDictionary(g => g, g => g.activeSelf);
            try
            {
                for (int i = 0; i < waves.Length; i++)
                {
                    string key = meta.keys[i];
                    foreach (var w in waves) w.SetActive(w == waves[i]);
                    var nw = waves[i].GetComponent<AF28NprWave>();
                    var mesh = nw.EnsureLoaded();
                    string dir = OutRoot + "/render/" + key;
                    Directory.CreateDirectory(dir);
                    var it = new RenderItem { key = key, sdf = nw.FullSdfPath, sdfSha256 = AF28ProjectionBaker.Sha(nw.FullSdfPath), vertexCount = mesh.vertexCount };
                    var files = new List<string>();
                    // 全体（外殻線あり）
                    Shader.SetGlobalFloat("_AF28IdMode", 0);
                    nw.outline.enabled = true;
                    files.Add(Capture(cams["painting"], W, H, true, dir + "/28_" + key + "_painting.png"));
                    files.Add(Capture(cams["boat"], W, H, true, dir + "/28_" + key + "_boat.png"));
                    if (key == "a45")
                    {
                        files.Add(Capture(cams["side"], W, H, true, dir + "/28_" + key + "_side.png"));
                        files.Add(Capture(cams["back"], W, H, true, dir + "/28_" + key + "_back.png"));
                    }
                    // 主役波だけ（ほかは隠す。空はカメラの背景）
                    foreach (var g in roots) if (g != waves[i] && g.GetComponent<Camera>() == null) g.SetActive(false);
                    nw.outline.enabled = false;
                    if (key == "a45")
                    {
                        files.Add(Capture(cams["painting"], W, H, true, dir + "/28_" + key + "_painting_kstar.png"));
                        files.Add(Capture(cams["boat"], W, H, true, dir + "/28_" + key + "_boat_kstar.png"));
                    }
                    Shader.SetGlobalFloat("_AF28IdMode", 1);
                    files.Add(Capture(cams["painting"], 2 * W, 2 * H, false, dir + "/28_" + key + "_class_ids.png"));
                    if (key == "a45")
                    {
                        files.Add(Capture(cams["boat"], W, H, false, dir + "/28_" + key + "_boat_class_ids.png"));
                        nw.outline.enabled = true;
                        files.Add(Capture(cams["painting"], 2 * W, 2 * H, false, dir + "/28_" + key + "_line_ids.png"));
                        nw.outline.enabled = false;
                    }
                    Shader.SetGlobalFloat("_AF28IdMode", 0);
                    nw.outline.enabled = true;
                    foreach (var kv in initial) kv.Key.SetActive(kv.Value);
                    it.files = files.ToArray();
                    it.filesSha256 = files.Select(f => AF28ProjectionBaker.Sha(f)).ToArray();
                    items.Add(it);
                }
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                foreach (var kv in initial) kv.Key.SetActive(kv.Value);
                foreach (var w in waves) w.SetActive(w.name == "AF28 K* a45");
            }
            File.WriteAllText(OutRoot + "/render/idmap.json",
                "{\n \"classes\": {\n  \"sky\": [255, 255, 255],\n  \"white\": [255, 0, 0],\n  \"mizuiro\": [0, 255, 0],\n  \"ai_mid\": [0, 0, 255],\n  \"ai_dark\": [255, 255, 0],\n  \"line\": [255, 0, 255]\n },\n" +
                " \"note_ja\": \"番号28 の ID 画像。主役波（K*）だけを描き、ほかは隠した。空 = カメラの背景（白）。色区は AF28 NPR v1 の ID 表示（アンチエイリアスなし）、line は外殻線 v0。\"\n}\n");
            report.items = items.ToArray();
            report.finishedUtc = DateTime.UtcNow.ToString("O");
            report.totalSeconds = (float)total.Elapsed.TotalSeconds;
            report.passed = items.Count == meta.keys.Length && items.All(x => x.vertexCount > 0);
            File.WriteAllText(OutRoot + "/af28_render_report.json", JsonUtility.ToJson(report, true));
            UnityEngine.Debug.Log("AF28_RENDER_DONE items=" + items.Count + " seconds=" + report.totalSeconds);
            if (!report.passed) throw new InvalidOperationException("描画の検査が不合格です。");
        }

        // colour = true：sRGB の RT に MSAA 8x、背景は空上。false：線形の RT、MSAA なし、背景は ID の空（白）。
        static string Capture(Camera camera, int w, int h, bool colour, string path)
        {
            var clear = camera.clearFlags; var bg = camera.backgroundColor; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            var prev = camera.targetTexture;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = colour ? (Color)SkyTop : IdSky;
            camera.allowHDR = false; camera.allowMSAA = colour;
            var rw = colour ? RenderTextureReadWrite.sRGB : RenderTextureReadWrite.Linear;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, rw) { antiAliasing = colour ? 8 : 1 };
            var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, rw);
            rt.Create(); res.Create();
            camera.aspect = (float)w / h;
            camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, !colour);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg; camera.allowHDR = hdr; camera.allowMSAA = aa;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return path;
        }

        static void SetPalette(Material m, AF28ProjectionBaker.BakeMeta meta)
        {
            m.SetColor("_White", C(meta.white));
            m.SetColor("_Mizuiro", C(meta.mizuiro));
            m.SetColor("_AiMid", C(meta.aiMid));
            m.SetColor("_AiDark", C(meta.aiDark));
            m.SetFloat("_EncodeLevels", meta.encodeLevels);
            m.SetFloat("_AAScale", 1);
        }

        static Camera MakeCamera(string name, Vector3 position, Vector3 target, float fov)
        {
            var old = GameObject.Find(name);
            if (old != null) UnityEngine.Object.DestroyImmediate(old);
            var go = new GameObject(name);
            var cam = go.AddComponent<Camera>();
            cam.enabled = false;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = SkyTop;
            cam.orthographic = false;
            cam.fieldOfView = fov;
            cam.nearClipPlane = .1f;
            cam.farClipPlane = 900;
            cam.aspect = (float)W / H;
            cam.allowHDR = false;
            cam.allowMSAA = true;
            go.transform.position = position;
            go.transform.LookAt(target, Vector3.up);
            return cam;
        }

        static Camera FindCamera(string name)
        {
            var go = GameObject.Find(name);
            if (go == null) throw new InvalidOperationException("カメラがありません: " + name);
            return go.GetComponent<Camera>();
        }

        static GameObject FindRoot(string name)
        {
            var go = EditorSceneManager.GetActiveScene().GetRootGameObjects().FirstOrDefault(g => g.name == name);
            if (go == null) throw new InvalidOperationException("見つかりません: " + name);
            return go;
        }

        static Material MaterialAsset(string name, string shaderName)
        {
            var shader = Shader.Find(shaderName);
            if (shader == null) throw new InvalidOperationException("シェーダーがありません: " + shaderName);
            string path = MaterialDir + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null) { m = new Material(shader); AssetDatabase.CreateAsset(m, path); }
            m.shader = shader;
            return m;
        }

        static void HideRoot(string name, List<string> hidden)
        {
            var go = EditorSceneManager.GetActiveScene().GetRootGameObjects().FirstOrDefault(g => g.name == name);
            if (go == null) throw new InvalidOperationException("非表示にする対象がありません: " + name);
            hidden.Add(go.activeSelf ? name : name + "（元から非表示）");
            go.SetActive(false);
        }

        static string PathOf(Transform t) => t.parent == null ? t.name : PathOf(t.parent) + "/" + t.name;

        [Serializable] class Layout { public Vector3 eyeWorld; }
        [Serializable] class BuildReport
        {
            public string unity, utc, sourceScene, scene, sourceSceneSha256Before, sourceSceneSha256After, sceneSha256;
            public bool sourceSceneUnchanged;
            public string[] hiddenObjects;
            public Vector3 eyeWorld;
        }
        [Serializable] class RenderItem
        {
            public string key, sdf, sdfSha256;
            public int vertexCount;
            public string[] files, filesSha256;
        }
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, startedUtc, finishedUtc, renderMethod;
            public float totalSeconds;
            public bool passed;
            public RenderItem[] items;
        }
    }
}
