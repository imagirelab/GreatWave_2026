using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.ArtFirst.EditorTools
{
    // 番号23 第2部「較正門（Unity 側）と M1 Revision01 の基線描画」。
    // 1) Gate：保存しない空のシーンに PaintingCam v1（Tools/PaintingTruth/painting_truth.json をそのまま読む）と
    //    世界標識 5 点・平塗り色区を置き、1920×1080 で Camera.Render → RenderTexture → PNG に描く。
    //    位置と色の測定・判定は Tools/PaintingTruth/gate_part2.py が行う（ここでは描くだけ）。
    // 2) Baseline：M1 Revision01 の構図シーンを開き、同じ PaintingCam v1 から色画像と ID 画像を描く。
    //    シーンと依存資産は保存しない。前後の SHA-256 が一致することを記録する。
    // PC のオフスクリーン描画で、HMD 実機の結果ではない。
    public static class AF23CalibrationGate
    {
        const string TruthJson = "../Tools/PaintingTruth/painting_truth.json";
        const string GateJson = "../Tools/PaintingTruth/unity_gate.json";
        const string OutRoot = "Build/ArtFirst/23";
        const string ShaderName = "GreatWave/ArtFirst/AF23 Gate Flat";
        // 評価器の ID 色（成分は 0 か 1 だけ）。空＝青、左奥船＝赤、中船＝緑、手前船＝黄、その他＝黒。
        // 割り当ては描画ごとに af23_baseline_M1R01_idmap.json へ書き出し、評価器はそのファイルを読む。
        static readonly Color IdSky = new Color(0, 0, 1), IdOther = new Color(0, 0, 0);
        static readonly Color IdBoatLeft = new Color(1, 0, 0), IdBoatMid = new Color(0, 1, 0), IdBoatFg = new Color(1, 1, 0);

        public static void RunAll() { Gate(); Baseline(); }

        // ------------------------------------------------------------ 較正門
        public static void Gate()
        {
            var total = Stopwatch.StartNew();
            var truth = JsonUtility.FromJson<Truth>(File.ReadAllText(TruthJson));
            var def = JsonUtility.FromJson<GateDef>(File.ReadAllText(GateJson));
            int W = def.render.width, H = def.render.height;
            if (W != truth.display_frame.width || H != truth.display_frame.height) throw new InvalidOperationException("描画寸法が painting_truth.json と違います。");
            var shader = Shader.Find(ShaderName);
            if (shader == null) throw new InvalidOperationException("シェーダーがありません: " + ShaderName);
            Directory.CreateDirectory(OutRoot);

            // 保存しない空のシーン（既存のシーン・資産には触れない）
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var cam = MakePaintingCam(truth, W, H);
            float fy = (H * 0.5f) / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);

            var rep = new GateReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), utc = DateTime.UtcNow.ToString("O"), width = W, height = H, msaa = def.render.msaa,
                truthJsonSha256 = Sha(TruthJson), gateJsonSha256 = Sha(GateJson), shaderName = ShaderName,
                cameraPosition = cam.transform.position, cameraEuler = cam.transform.eulerAngles, cameraForward = cam.transform.forward,
                cameraFieldOfView = cam.fieldOfView, cameraAspect = cam.aspect, cameraNear = cam.nearClipPlane, cameraFar = cam.farClipPlane,
                worldToCameraMatrix = Flat(cam.worldToCameraMatrix), projectionMatrix = Flat(cam.projectionMatrix),
                gpuProjectionMatrixRT = Flat(GL.GetGPUProjectionMatrix(cam.projectionMatrix, true)),
                method = "Editor batchmode：保存しない空シーン → Camera.Render → RenderTexture → ReadPixels → PNG（PC オフスクリーン、HMD ではない）"
            };

            // 世界標識：画像面に平行な円板（投影は相似変換になり、円の像の中心 = 中心の投影）
            var disk = DiskMesh(128);
            var mats = new List<Material>();
            var markerObjs = new List<GameObject>();
            var markers = new List<MarkerOut>();
            foreach (var m in def.markers)
            {
                var P = V(m.world);
                float z = cam.transform.InverseTransformPoint(P).z;
                float r = m.radius_px * z / fy;
                var go = new GameObject("AF23 標識 " + m.id) { hideFlags = HideFlags.DontSave };
                go.AddComponent<MeshFilter>().sharedMesh = disk;
                var mr = go.AddComponent<MeshRenderer>();
                mr.sharedMaterial = FlatMat(shader, new Color(m.color[0], m.color[1], m.color[2]), mats);
                mr.shadowCastingMode = ShadowCastingMode.Off; mr.receiveShadows = false;
                go.transform.SetPositionAndRotation(P, cam.transform.rotation);
                go.transform.localScale = Vector3.one * r;
                markerObjs.Add(go);
                var vp = cam.WorldToViewportPoint(P);
                markers.Add(new MarkerOut { id = m.id, world = P, depth = z, radiusWorld = r, radiusPx = m.radius_px, color = m.color, unityViewport = vp,
                    unityDisplayPx = new Vector2(vp.x * W - 0.5f, (1f - vp.y) * H - 0.5f) });
            }
            rep.markers = markers.ToArray();
            // 標識の画像：線形（sRGB 変換なし）の RT に MSAA 8x。解決後の値 = 被覆率 × 色。
            rep.markersPng = OutRoot + "/af23_markers.png";
            RenderTo(cam, W, H, def.render.msaa, RenderTextureReadWrite.Linear, rep.markersPng);
            // 補助：MSAA なしでも描く（記録のみ）
            rep.markersNoMsaaPng = OutRoot + "/af23_markers_nomsaa.png";
            RenderTo(cam, W, H, 1, RenderTextureReadWrite.Linear, rep.markersNoMsaaPng);
            foreach (var go in markerObjs) go.SetActive(false);

            // 平塗り色区：画像面に平行な四角形。基線の色画像と同じ経路（sRGB の RT、MSAA 8x → 解決 → RGB24 → PNG）。
            var quadObjs = new List<GameObject>();
            var patches = new List<PatchOut>();
            foreach (var p in def.patches)
            {
                float vx0 = p.rect_px[0] / (float)W, vx1 = p.rect_px[2] / (float)W;
                float vyT = 1f - p.rect_px[1] / (float)H, vyB = 1f - p.rect_px[3] / (float)H;
                var mesh = new Mesh { hideFlags = HideFlags.DontSave };
                mesh.vertices = new[]
                {
                    cam.ViewportToWorldPoint(new Vector3(vx0, vyB, def.patch_depth_m)), cam.ViewportToWorldPoint(new Vector3(vx1, vyB, def.patch_depth_m)),
                    cam.ViewportToWorldPoint(new Vector3(vx1, vyT, def.patch_depth_m)), cam.ViewportToWorldPoint(new Vector3(vx0, vyT, def.patch_depth_m))
                };
                mesh.triangles = new[] { 0, 2, 1, 0, 3, 2 };
                mesh.RecalculateBounds();
                var go = new GameObject("AF23 色区 " + p.name) { hideFlags = HideFlags.DontSave };
                go.AddComponent<MeshFilter>().sharedMesh = mesh;
                var mr = go.AddComponent<MeshRenderer>();
                var c32 = new Color32((byte)p.srgb8[0], (byte)p.srgb8[1], (byte)p.srgb8[2], 255);
                mr.sharedMaterial = FlatMat(shader, c32, mats);
                mr.shadowCastingMode = ShadowCastingMode.Off; mr.receiveShadows = false;
                quadObjs.Add(go);
                patches.Add(new PatchOut { name = p.name, srgb8 = p.srgb8, rectPx = p.rect_px, materialGetColor = mr.sharedMaterial.GetColor("_Color") });
            }
            rep.patches = patches.ToArray();
            rep.flatPatchPng = OutRoot + "/af23_flat_patch.png";
            RenderTo(cam, W, H, def.render.msaa, RenderTextureReadWrite.sRGB, rep.flatPatchPng);
            // 対照（記録のみ）：線形の RT に描くと sRGB への符号化が抜ける。較正門がこの誤りを検出できるかの確認。
            rep.flatPatchLinearControlPng = OutRoot + "/af23_flat_patch_linear_rt_control.png";
            RenderTo(cam, W, H, def.render.msaa, RenderTextureReadWrite.Linear, rep.flatPatchLinearControlPng);

            foreach (var go in markerObjs.Concat(quadObjs)) UnityEngine.Object.DestroyImmediate(go);
            foreach (var m in mats) UnityEngine.Object.DestroyImmediate(m);
            UnityEngine.Object.DestroyImmediate(cam.gameObject);
            rep.seconds = (float)total.Elapsed.TotalSeconds;
            File.WriteAllText(OutRoot + "/af23_gate_unity_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("AF23_GATE_RENDER_DONE markers=" + rep.markers.Length + " patches=" + rep.patches.Length + " colorSpace=" + rep.colorSpace);
        }

        // ------------------------------------------------------------ M1 Revision01 の基線
        public static void Baseline()
        {
            var total = Stopwatch.StartNew();
            var truth = JsonUtility.FromJson<Truth>(File.ReadAllText(TruthJson));
            var def = JsonUtility.FromJson<GateDef>(File.ReadAllText(GateJson));
            int W = def.render.width, H = def.render.height;
            var shader = Shader.Find(ShaderName);
            if (shader == null) throw new InvalidOperationException("シェーダーがありません: " + ShaderName);
            Directory.CreateDirectory(OutRoot);
            string scenePath = def.baseline.scene;
            var deps = AssetDatabase.GetDependencies(scenePath, true).OrderBy(p => p, StringComparer.Ordinal).ToArray();
            var before = deps.Select(p => new FileHash { path = p, sha256 = Sha(p) }).ToArray();

            var scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
            var viewer = UnityEngine.Object.FindAnyObjectByType<GreatWave.M1DesktopViewer>();
            if (viewer == null) throw new InvalidOperationException("M1DesktopViewer がありません。");
            viewer.SelectView(0); // 視点0「原画比較視点」の状態（範囲図は非表示）にする。保存はしない。
            var vc = viewer.viewCamera;
            var cam = MakePaintingCam(truth, W, H);
            cam.clearFlags = vc.clearFlags;
            cam.backgroundColor = vc.backgroundColor;
            var rep = new BaselineReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), utc = DateTime.UtcNow.ToString("O"), scene = scenePath, width = W, height = H,
                msaa = def.render.msaa, idScale = def.baseline.id_scale, view0Label = viewer.views[0].label,
                view0Position = vc.transform.position, view0Euler = vc.transform.eulerAngles, view0FieldOfView = vc.fieldOfView,
                cameraPosition = cam.transform.position, cameraEuler = cam.transform.eulerAngles, cameraFieldOfView = cam.fieldOfView,
                backgroundColor = cam.backgroundColor, clearFlags = cam.clearFlags.ToString(),
                view0MaxPositionDiff = (vc.transform.position - cam.transform.position).magnitude,
                view0MaxAngleDiffDeg = Quaternion.Angle(vc.transform.rotation, cam.transform.rotation),
                method = "Editor batchmode：M1 Revision01 シーンを開き（保存しない）、PaintingCam v1 から Camera.Render → RenderTexture → PNG。色画像は sRGB RT・MSAA 8x、ID 画像は 3840×2160・線形 RT・MSAA なし。PC オフスクリーン描画で、HMD ではない。"
            };
            rep.colorPng = OutRoot + "/af23_baseline_M1R01.png";
            RenderTo(cam, W, H, def.render.msaa, RenderTextureReadWrite.sRGB, rep.colorPng);

            // ID 画像：空 = カメラの背景、三船 = 各船の子孫、ほか = other。マテリアル資産は変えず、メモリ上で差し替えて戻す。
            var mats = new List<Material>();
            var boats = new[] { (def.baseline.boat_left, IdBoatLeft), (def.baseline.boat_mid, IdBoatMid), (def.baseline.boat_fg, IdBoatFg) };
            var roots = boats.Select(b => (GameObject.Find(b.Item1), b.Item2)).ToArray();
            if (roots.Any(r => r.Item1 == null)) throw new InvalidOperationException("船の根が見つかりません。");
            var saved = new List<(Renderer, Material[])>();
            var boatRenderers = new int[3];
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude))
            {
                Color c = IdOther;
                for (int i = 0; i < roots.Length; i++) if (r.transform.IsChildOf(roots[i].Item1.transform)) { c = roots[i].Item2; boatRenderers[i]++; }
                saved.Add((r, r.sharedMaterials));
                var m = FlatMat(shader, c, mats);
                r.sharedMaterials = Enumerable.Repeat(m, Math.Max(1, r.sharedMaterials.Length)).ToArray();
            }
            rep.renderersOverridden = saved.Count;
            rep.boatRenderers = boatRenderers;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = IdSky;
            int s = Math.Max(1, def.baseline.id_scale);
            rep.idsPng = OutRoot + "/af23_baseline_M1R01_ids.png";
            var idTex = RenderTo(cam, W * s, H * s, 1, RenderTextureReadWrite.Linear, rep.idsPng, keep: true);
            var colors = new HashSet<int>();
            foreach (var p in idTex.GetPixels32()) colors.Add((p.r << 16) | (p.g << 8) | p.b);
            rep.idDistinctColors = colors.Count;
            UnityEngine.Object.DestroyImmediate(idTex);
            foreach (var (r, m) in saved) r.sharedMaterials = m;
            foreach (var m in mats) UnityEngine.Object.DestroyImmediate(m);
            UnityEngine.Object.DestroyImmediate(cam.gameObject);
            rep.idmapJson = OutRoot + "/af23_baseline_M1R01_idmap.json";
            File.WriteAllText(rep.idmapJson, "{\n \"classes\": {\n  \"sky\": [0, 0, 255],\n  \"boat_left\": [255, 0, 0],\n  \"boat_mid\": [0, 255, 0],\n  \"boat_fg\": [255, 255, 0]\n },\n \"other\": [0, 0, 0],\n \"note_ja\": \"番号23 第2部：M1 Revision01 の ID 画像（3840×2160、MSAA なし）。空＝カメラの背景、三船＝各船の子孫、ほかは全て other（旧主波・支え斜面・白波・参照海面・富士など）。\"\n}\n");

            // 開いたシーンは保存しない。空のシーンへ切り替えて変更を捨て、依存資産の SHA-256 を比べる。
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var after = deps.Select(p => new FileHash { path = p, sha256 = Sha(p) }).ToArray();
            rep.dependencies = before;
            rep.dependenciesUnchanged = before.Length == after.Length && before.Zip(after, (a, b) => a.path == b.path && a.sha256 == b.sha256).All(x => x);
            rep.sceneSha256 = Sha(scenePath);
            rep.seconds = (float)total.Elapsed.TotalSeconds;
            rep.passed = rep.dependenciesUnchanged && rep.idDistinctColors <= 5 && boatRenderers.All(n => n > 0);
            File.WriteAllText(OutRoot + "/af23_baseline_unity_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("AF23_BASELINE_RENDER_DONE unchanged=" + rep.dependenciesUnchanged + " idColors=" + rep.idDistinctColors + " passed=" + rep.passed);
            if (!rep.passed) throw new InvalidOperationException("基線描画の検査が不合格です（af23_baseline_unity_report.json を参照）。");
        }

        // ------------------------------------------------------------ 共通
        static Camera MakePaintingCam(Truth t, int W, int H)
        {
            var c = t.painting_cam;
            var go = new GameObject("AF23 PaintingCam v1") { hideFlags = HideFlags.DontSave };
            var cam = go.AddComponent<Camera>();
            cam.enabled = false; // Camera.Render でだけ使う
            cam.orthographic = false;
            cam.usePhysicalProperties = false;
            cam.fieldOfView = c.vertical_fov_deg;
            cam.nearClipPlane = c.near;
            cam.farClipPlane = c.far;
            cam.aspect = (float)W / H;
            cam.allowHDR = false;
            cam.allowMSAA = true;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Color.black;
            go.transform.position = V(c.position);
            go.transform.LookAt(V(c.target), V(c.up));
            return cam;
        }

        static Texture2D RenderTo(Camera cam, int w, int h, int msaa, RenderTextureReadWrite rw, string path, bool keep = false)
        {
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, rw) { antiAliasing = Math.Max(1, msaa) };
            rt.Create();
            RenderTexture resolve = null, src = rt;
            var prev = cam.targetTexture;
            cam.aspect = (float)w / h;
            cam.targetTexture = rt;
            cam.Render();
            cam.targetTexture = prev;
            if (msaa > 1)
            {
                resolve = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, rw);
                resolve.Create();
                Graphics.Blit(rt, resolve);
                src = resolve;
            }
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, rw == RenderTextureReadWrite.Linear);
            RenderTexture.active = src;
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToPNG());
            rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            if (resolve != null) { resolve.Release(); UnityEngine.Object.DestroyImmediate(resolve); }
            if (keep) return tex;
            UnityEngine.Object.DestroyImmediate(tex);
            return null;
        }

        static Material FlatMat(Shader shader, Color c, List<Material> mats)
        {
            var m = new Material(shader) { hideFlags = HideFlags.DontSave };
            m.SetColor("_Color", c);
            mats.Add(m);
            return m;
        }

        static Mesh DiskMesh(int n)
        {
            var v = new Vector3[n + 1];
            var tri = new int[n * 3];
            v[0] = Vector3.zero;
            for (int i = 0; i < n; i++)
            {
                double a = 2.0 * Math.PI * i / n;
                v[i + 1] = new Vector3((float)Math.Cos(a), (float)Math.Sin(a), 0);
                tri[3 * i] = 0; tri[3 * i + 1] = 1 + (i + 1) % n; tri[3 * i + 2] = 1 + i;
            }
            var mesh = new Mesh { hideFlags = HideFlags.DontSave, vertices = v, triangles = tri };
            mesh.RecalculateBounds();
            return mesh;
        }

        static Vector3 V(float[] a) => new Vector3(a[0], a[1], a[2]);
        static float[] Flat(Matrix4x4 m) { var o = new float[16]; for (int r = 0; r < 4; r++) for (int c = 0; c < 4; c++) o[r * 4 + c] = m[r, c]; return o; }

        static string Sha(string path)
        {
            using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant();
        }

        // ------------------------------------------------------------ JSON
        [Serializable] class Truth { public Cam painting_cam; public Frame display_frame; }
        [Serializable] class Cam { public string id; public float[] position, target, up; public float vertical_fov_deg, aspect, near, far; }
        [Serializable] class Frame { public int width, height; }
        [Serializable] class GateDef { public RenderDef render; public MarkerDef[] markers; public PatchDef[] patches; public float patch_depth_m; public BaselineDef baseline; }
        [Serializable] class RenderDef { public int width, height, msaa; }
        [Serializable] class MarkerDef { public string id; public float[] world; public float radius_px; public float[] color; }
        [Serializable] class PatchDef { public string name; public int[] srgb8; public int[] rect_px; }
        [Serializable] class BaselineDef { public string scene, boat_left, boat_mid, boat_fg; public int id_scale; }
        [Serializable] class MarkerOut { public string id; public Vector3 world, unityViewport; public Vector2 unityDisplayPx; public float depth, radiusWorld, radiusPx; public float[] color; }
        [Serializable] class PatchOut { public string name; public int[] srgb8, rectPx; public Color materialGetColor; }
        [Serializable] class FileHash { public string path, sha256; }
        [Serializable] class GateReport
        {
            public string unity, device, graphicsApi, colorSpace, utc, truthJsonSha256, gateJsonSha256, shaderName, method;
            public string markersPng, markersNoMsaaPng, flatPatchPng, flatPatchLinearControlPng;
            public int width, height, msaa;
            public Vector3 cameraPosition, cameraEuler, cameraForward;
            public float cameraFieldOfView, cameraAspect, cameraNear, cameraFar, seconds;
            public float[] worldToCameraMatrix, projectionMatrix, gpuProjectionMatrixRT;
            public MarkerOut[] markers;
            public PatchOut[] patches;
        }
        [Serializable] class BaselineReport
        {
            public string unity, device, graphicsApi, colorSpace, utc, scene, method, view0Label, clearFlags, colorPng, idsPng, idmapJson, sceneSha256;
            public int width, height, msaa, idScale, renderersOverridden, idDistinctColors;
            public int[] boatRenderers;
            public Vector3 view0Position, view0Euler, cameraPosition, cameraEuler;
            public float view0FieldOfView, cameraFieldOfView, view0MaxPositionDiff, view0MaxAngleDiffDeg, seconds;
            public Color backgroundColor;
            public FileHash[] dependencies;
            public bool dependenciesUnchanged, passed;
        }
    }
}
