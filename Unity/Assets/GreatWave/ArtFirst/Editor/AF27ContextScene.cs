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
    // 番号27「空のドーム・船・富士の配置」。Tools/GWContext/context_layout.json（af27_sky.py・af27_place.py の出力）から
    // 新しいシーン AF27_Context.unity と、CP1 の合成で使い回すプレハブ・マテリアル・テクスチャを作り、
    // PaintingCam v1・船上座席・側面・船の接地の確認視点から Camera.Render → RenderTexture → PNG で描く（PC のオフスクリーン描画。HMD 実機ではない）。
    // 主役波は番号24 の v0（AF24WavePlayer、t* のフレーム）を仮に置く（番号26 の K* で置き換える）。M1 のシーンと資産は書き換えない。
    public static class AF27ContextScene
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF27_Context.unity";
        const string LayoutPath = "../Tools/GWContext/context_layout.json";
        const string ArtFirst = "Assets/GreatWave/ArtFirst";
        const string MatDir = ArtFirst + "/Materials";
        const string TexDir = ArtFirst + "/Textures";
        const string PrefabDir = ArtFirst + "/Prefabs";
        const string OutRoot = AF27ContextBuilder.OutRoot;
        const int W = 1920, H = 1080;
        static readonly Vector3 PaintingPosition = new Vector3(0, 3, -62), PaintingTarget = new Vector3(-2.5f, 9.7f, 4);
        // 側面：番号24 の側面（(53,22,−2) から）は右の斜面の仮置き（高さ約 19 m、x 0〜32）の裏に入って何も見えないため、左（−x）側から見る。
        static readonly Vector3 SidePosition = new Vector3(-90, 30, -14), SideTarget = new Vector3(5, 3, -12);
        // 俯瞰：右手前の上から、3隻・主役波・仮置きをまとめて見る
        static readonly Vector3 OverviewPosition = new Vector3(40, 28, -70), OverviewTarget = new Vector3(0, 3, -12);
        // 評価器の ID 色（番号24 と同じ）
        static readonly Color IdSky = new Color(0, 0, 1), IdOther = new Color(0, 0, 0);
        static readonly Dictionary<string, Color> IdBoats = new Dictionary<string, Color> {
            { "boat_left", new Color(1, 0, 0) }, { "boat_mid", new Color(0, 1, 0) }, { "boat_fg", new Color(1, 1, 0) } };

        public static void BuildAndRender() { Build(); Render(); }

        // ------------------------------------------------------------------ 組み立て
        public static void Build()
        {
            var L = JsonUtility.FromJson<Layout>(File.ReadAllText(LayoutPath)).unity;
            var protectedFiles = new[] { AF27ContextBuilder.FbxPath("boat_blockout"), AF27ContextBuilder.FbxPath("fuji_blockout"),
                AF27ContextBuilder.FbxPath("foam_static"), AF27ContextBuilder.FbxPath("revision_slopes"), GreatWave.Editor.M1RevisionBuilder.ScenePath,
                "Assets/GreatWave/ArtFirst/Materials/AF24_Palette.mat", "Assets/GreatWave/ArtFirst/Scripts/AF24WavePlayer.cs" };
            var before = protectedFiles.ToDictionary(p => p, p => AF27ContextBuilder.Sha(p));
            foreach (var d in new[] { MatDir, TexDir, PrefabDir }) Directory.CreateDirectory(d);

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat; RenderSettings.ambientLight = Color.white; RenderSettings.fog = false;
            RenderSettings.skybox = null;

            var pal = L.palette.ToDictionary(p => p.key, p => new Color32((byte)p.srgb8[0], (byte)p.srgb8[1], (byte)p.srgb8[2], 255));
            var flat = new Dictionary<string, Material>();
            Material Flat(string key)
            {
                if (flat.TryGetValue(key, out var m)) return m;
                m = MaterialAsset("AF27_Flat_" + key, "GreatWave/ArtFirst/AF27 Flat");
                m.SetColor("_Color", (Color)pal[key]);
                EditorUtility.SetDirty(m);
                flat[key] = m;
                return m;
            }

            var context = new GameObject("AF27 背景（空・船・富士・海・仮置き）");
            // 空のドーム
            var skyMat = SkyMaterial(L.sky);
            var dome = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            dome.name = "AF27 空のドーム";
            UnityEngine.Object.DestroyImmediate(dome.GetComponent<Collider>());
            dome.transform.SetParent(context.transform, false);
            dome.transform.localScale = Vector3.one * (2f * L.sky.radius);
            SetupRenderer(dome.GetComponent<MeshRenderer>(), skyMat);
            // 海
            var sea = GameObject.CreatePrimitive(PrimitiveType.Cube);
            sea.name = "AF27 参照海面";
            UnityEngine.Object.DestroyImmediate(sea.GetComponent<Collider>());
            sea.transform.SetParent(context.transform, false);
            sea.transform.localPosition = V(L.sea.position); sea.transform.localScale = V(L.sea.scale);
            SetupRenderer(sea.GetComponent<MeshRenderer>(), Flat(L.sea.palette));
            // 船
            foreach (var b in L.boats)
            {
                var root = new GameObject("AF27 船 " + b.key);
                root.transform.SetParent(context.transform, false);
                root.transform.localPosition = V(b.position);
                root.transform.localRotation = new Quaternion(b.rotation[0], b.rotation[1], b.rotation[2], b.rotation[3]);
                root.transform.localScale = Vector3.one * b.scale;
                var inst = Instantiate(AF27ContextBuilder.FbxPath("boat_blockout"), root.transform);
                Recolor(inst, b.materials, Flat);
            }
            // 富士
            {
                var root = new GameObject("AF27 富士");
                root.transform.SetParent(context.transform, false);
                root.transform.localPosition = V(L.fuji.position); root.transform.localScale = V(L.fuji.scale);
                var inst = Instantiate(AF27ContextBuilder.FbxPath("fuji_blockout"), root.transform);
                Recolor(inst, L.fuji.materials, Flat);
            }
            // 仮置き（前景のうねり・斜面）
            {
                var root = new GameObject("AF27 仮置き（前景のうねり・斜面、番号39/40 で置き換え）");
                root.transform.SetParent(context.transform, false);
                var foam = Instantiate(AF27ContextBuilder.FbxPath("foam_static"), root.transform);
                var slopes = Instantiate(AF27ContextBuilder.FbxPath("revision_slopes"), root.transform);
                foreach (var t in foam.GetComponentsInChildren<Transform>(true))
                    if (t.name.StartsWith("M1_Foam_FrontRibbon") || t.name.StartsWith("M1_Foam_Claw")) t.gameObject.SetActive(false);
                foreach (var ph in L.placeholders)
                {
                    var t = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == ph.name);
                    if (t == null) throw new InvalidOperationException("仮置きがありません: " + ph.name);
                    t.localPosition += new Vector3(0, ph.translateY, 0);
                    Recolor(t.gameObject, ph.materials, Flat);
                }
            }
            // 主役波（番号24 v0 を仮に置く。プレハブには入れない）
            var wave = new GameObject("AF24 主役波 v0（仮置き、番号26 の K* で置き換え）");
            wave.AddComponent<MeshFilter>();
            var wr = wave.AddComponent<MeshRenderer>();
            wr.sharedMaterial = AssetDatabase.LoadAssetAtPath<Material>("Assets/GreatWave/ArtFirst/Materials/AF24_Palette.mat");
            wr.shadowCastingMode = ShadowCastingMode.Off; wr.receiveShadows = false;
            wave.AddComponent<AF24WavePlayer>().dataPath = "Build/ArtFirst/24/wave/wave_v0.gwb";

            // 座席（手前の船の甲板を M1 と同じ局所の点から測る。向きは船の局所の下向き）
            var fgRoot = GameObject.Find("AF27 船 boat_fg");
            var deck = fgRoot.GetComponentsInChildren<MeshFilter>().Single(f => f.name == "Boat_Deck_Planks");
            var col = deck.gameObject.AddComponent<MeshCollider>(); col.sharedMesh = deck.sharedMesh; Physics.SyncTransforms();
            var probe = fgRoot.transform.TransformPoint(V(L.seat.probeLocal));
            bool hitDeck = col.Raycast(new Ray(probe, -fgRoot.transform.up), out RaycastHit hit, 100);
            UnityEngine.Object.DestroyImmediate(col);
            if (!hitDeck) throw new InvalidOperationException("座席の甲板を測れません。");
            var eye = hit.point + Vector3.up * L.seat.eyeAboveDeck;

            var cams = new GameObject("AF27 カメラ");
            MakeCamera(cams, "AF27 PaintingCam v1", PaintingPosition, PaintingTarget, 26);
            MakeCamera(cams, "AF27 船上座席カメラ", eye, V(L.seat.target), L.seat.fov);
            MakeCamera(cams, "AF27 側面カメラ", SidePosition, SideTarget, 40);
            MakeCamera(cams, "AF27 俯瞰カメラ", OverviewPosition, OverviewTarget, 55);
            // 船の接地の確認用：船の軸に直交し PaintingCam の側を向く水平方向から、仰角 12° で船体の中央を見る
            foreach (var b in L.boats)
            {
                var r = GameObject.Find("AF27 船 " + b.key).transform;
                var hullF = r.GetComponentsInChildren<MeshFilter>().Single(f => f.name == "Boat_Hull_OpenThick");
                var hb = hullF.GetComponent<Renderer>().bounds;
                var axis = r.forward; axis.y = 0; axis.Normalize();
                var side = Vector3.Cross(Vector3.up, axis).normalized;
                if (Vector3.Dot(side, PaintingPosition - hb.center) < 0) side = -side;
                float dist = 9f * b.scale + 3f;
                var dir = (side * Mathf.Cos(12 * Mathf.Deg2Rad) + Vector3.up * Mathf.Sin(12 * Mathf.Deg2Rad)).normalized;
                MakeCamera(cams, "AF27 接地確認 " + b.key, hb.center + dir * dist, hb.center, 50);
            }

            // プレハブ（CP1 の合成で使う）：背景一式と空のドーム単体
            PrefabUtility.SaveAsPrefabAssetAndConnect(context, PrefabDir + "/AF27_Context.prefab", InteractionMode.AutomatedAction);
            var domeCopy = UnityEngine.Object.Instantiate(dome);
            domeCopy.name = "AF27 空のドーム";
            PrefabUtility.SaveAsPrefabAsset(domeCopy, PrefabDir + "/AF27_SkyDome.prefab");
            UnityEngine.Object.DestroyImmediate(domeCopy);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("シーンを保存できません。");
            AssetDatabase.SaveAssets();
            var after = protectedFiles.ToDictionary(p => p, p => AF27ContextBuilder.Sha(p));
            var rep = new BuildReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePath, sceneSha256 = AF27ContextBuilder.Sha(ScenePath),
                eyeUnity = eye, eyeNumpy = V(L.seat.eyeNumpy), eyeDiff = Vector3.Distance(eye, V(L.seat.eyeNumpy)), deckHit = hit.point, probe = probe,
                protectedUnchanged = protectedFiles.All(p => before[p] == after[p]),
                protectedFiles = protectedFiles.Select(p => p + " " + after[p]).ToArray(),
                prefabs = new[] { PrefabDir + "/AF27_Context.prefab", PrefabDir + "/AF27_SkyDome.prefab" }
            };
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/af27_build_report.json", JsonUtility.ToJson(rep, true));
            if (!rep.protectedUnchanged) throw new InvalidOperationException("M1 または番号24 の資産が変わりました。");
            UnityEngine.Debug.Log("AF27_BUILD_DONE eyeDiff=" + rep.eyeDiff);
        }

        static Material SkyMaterial(SkyJ s)
        {
            int nT = s.thetaT.Length, nG = s.gradientRGB.Length / 3;
            var tT = new Texture2D(nT, 1, TextureFormat.RFloat, false, true) { name = "AF27_SkyThetaT", filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp };
            tT.SetPixelData(s.thetaT, 0); tT.Apply(false, false);
            var g = new float[nG * 4];
            for (int i = 0; i < nG; i++) { g[4 * i] = s.gradientRGB[3 * i]; g[4 * i + 1] = s.gradientRGB[3 * i + 1]; g[4 * i + 2] = s.gradientRGB[3 * i + 2]; g[4 * i + 3] = 1; }
            var tG = new Texture2D(nG, 1, TextureFormat.RGBAFloat, false, true) { name = "AF27_SkyGradient", filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp };
            tG.SetPixelData(g, 0); tG.Apply(false, false);
            tT = SaveTexture(tT, TexDir + "/AF27_SkyThetaT.asset");
            tG = SaveTexture(tG, TexDir + "/AF27_SkyGradient.asset");
            var m = MaterialAsset("AF27_SkyDome", "GreatWave/ArtFirst/AF27 Sky Dome");
            m.SetTexture("_ThetaT", tT); m.SetTexture("_Gradient", tG);
            m.SetVector("_ThetaParams", new Vector4(s.thetaAz0, s.thetaStep, nT, s.theta0));
            m.SetVector("_GradParams", new Vector4(s.gradE0, s.gradStep, nG, 0));
            m.SetVector("_WParams", new Vector4(s.wFull, s.wZero, 0, 0));
            EditorUtility.SetDirty(m);
            return m;
        }

        static Texture2D SaveTexture(Texture2D t, string path)
        {
            var old = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            if (old != null) AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(t, path);
            return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
        }

        static GameObject Instantiate(string fbx, Transform parent)
        {
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(fbx);
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(asset);
            inst.transform.SetParent(parent, false);
            return inst;
        }

        static void Recolor(GameObject root, MatJ[] map, Func<string, Material> flat)
        {
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            {
                r.sharedMaterials = r.sharedMaterials.Select(m =>
                {
                    var e = map.FirstOrDefault(x => m != null && m.name == x.m1Material);
                    if (e == null) throw new InvalidOperationException("材質の対応がありません: " + (m == null ? "null" : m.name) + " @ " + r.name);
                    return flat(e.palette);
                }).ToArray();
                r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
            }
        }

        static void SetupRenderer(MeshRenderer r, Material m) { r.sharedMaterial = m; r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false; }

        // ------------------------------------------------------------------ 描画
        public static void Render()
        {
            var total = Stopwatch.StartNew();
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var player = UnityEngine.Object.FindAnyObjectByType<AF24WavePlayer>();
            player.EnsureLoaded();
            var waveRenderer = player.GetComponent<MeshRenderer>();
            var block = new MaterialPropertyBlock();
            var painting = FindCamera("AF27 PaintingCam v1");
            var msaa = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var resolve = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            msaa.Create(); resolve.Create();
            var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            var rep = new RenderReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(), startedUtc = DateTime.UtcNow.ToString("O"), frames = player.frameCount,
                fps = player.fps, tStarFrame = player.tStarFrame,
                renderMethod = "Editor batchmode：Camera.Render → RenderTexture（sRGB、MSAA 8x → 解決）→ ReadPixels → PNG。PC のオフスクリーン描画で、HMD 実機ではない。"
            };
            // 形成の全フレーム（PaintingCam）。カメラの位置・向き・画角・投影行列が変わらないこと（94）を毎フレーム記録する。
            string framesDir = OutRoot + "/frames_painting";
            if (Directory.Exists(framesDir)) Directory.Delete(framesDir, true);
            Directory.CreateDirectory(framesDir);
            painting.aspect = (float)W / H; // 描画と同じ縦横比にしてから基準の行列を取る
            var p0 = painting.transform.position; var q0 = painting.transform.rotation; float f0 = painting.fieldOfView;
            var proj0 = painting.projectionMatrix; var view0 = painting.worldToCameraMatrix;
            float maxPos = 0, maxAng = 0, maxFov = 0, maxProj = 0, maxView = 0;
            for (int f = 0; f < player.frameCount; f++)
            {
                player.SetFrame(f);
                block.SetFloat("_Progress", Progress(f / player.fps)); waveRenderer.SetPropertyBlock(block);
                Capture(painting, msaa, resolve, tex, Path.Combine(framesDir, "f_" + f.ToString("D4") + ".png"));
                maxPos = Mathf.Max(maxPos, Vector3.Distance(painting.transform.position, p0));
                maxAng = Mathf.Max(maxAng, Quaternion.Angle(painting.transform.rotation, q0));
                maxFov = Mathf.Max(maxFov, Mathf.Abs(painting.fieldOfView - f0));
                maxProj = Mathf.Max(maxProj, MaxAbsDiff(painting.projectionMatrix, proj0));
                maxView = Mathf.Max(maxView, MaxAbsDiff(painting.worldToCameraMatrix, view0));
                rep.renderedFrames++;
            }
            rep.cameraMaxPositionDelta = maxPos; rep.cameraMaxAngleDeltaDeg = maxAng; rep.cameraMaxFovDelta = maxFov;
            rep.cameraMaxProjectionDelta = maxProj; rep.cameraMaxViewDelta = maxView;
            rep.cameraPosition = p0; rep.cameraEuler = q0.eulerAngles; rep.cameraFov = f0;
            // t* の静止画
            player.SetFrame(player.tStarFrame);
            block.SetFloat("_Progress", 1); waveRenderer.SetPropertyBlock(block);
            Capture(painting, msaa, resolve, tex, OutRoot + "/27_painting_tstar.png");
            Capture(FindCamera("AF27 船上座席カメラ"), msaa, resolve, tex, OutRoot + "/27_boat_tstar.png");
            Capture(FindCamera("AF27 側面カメラ"), msaa, resolve, tex, OutRoot + "/27_side_tstar.png");
            Capture(FindCamera("AF27 俯瞰カメラ"), msaa, resolve, tex, OutRoot + "/27_overview_tstar.png");
            // 接地の確認図は、その船・その支え・空のドームだけを表示して描く（ほかの物は一時的に隠す。確認用の図で、場面の見え方ではない）。
            var supportOf = new Dictionary<string, string> { { "boat_fg", "AF27 参照海面" }, { "boat_mid", "M1_Revision_RightSlope" }, { "boat_left", "M1_Revision_LeftSupport" } };
            var allR = UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude);
            foreach (var k in IdBoats.Keys)
            {
                var boatRoot = GameObject.Find("AF27 船 " + k).transform;
                var sup = allR.First(r => r.gameObject.name == supportOf[k]).transform;
                var dome = GameObject.Find("AF27 空のドーム").transform;
                var hiddenR = allR.Where(r => r.enabled && !r.transform.IsChildOf(boatRoot) && r.transform != sup && r.transform != dome).ToList();
                foreach (var r in hiddenR) r.enabled = false;
                Capture(FindCamera("AF27 接地確認 " + k), msaa, resolve, tex, OutRoot + "/27_contact_" + k + ".png");
                foreach (var r in hiddenR) r.enabled = true;
            }
            RenderIds(painting, OutRoot + "/27_painting_tstar_ids.png", OutRoot + "/27_idmap.json", rep);
            rep.contacts = Contacts();
            var boatCam = FindCamera("AF27 船上座席カメラ");
            rep.seatEye = boatCam.transform.position;
            rep.finishedUtc = DateTime.UtcNow.ToString("O"); rep.totalSeconds = (float)total.Elapsed.TotalSeconds;
            File.WriteAllText(OutRoot + "/af27_render_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Object.DestroyImmediate(tex); msaa.Release(); resolve.Release();
            UnityEngine.Object.DestroyImmediate(msaa); UnityEngine.Object.DestroyImmediate(resolve);
            UnityEngine.Debug.Log("AF27_RENDER_DONE frames=" + rep.renderedFrames + " seconds=" + rep.totalSeconds);
        }

        // 船が支えの面に載っているか：竜骨の中央（船の根の原点）と船体（Boat_Hull_OpenThick）の最も低い頂点の真上 50 m から下へ、
        // 支えの面だけに射線を当てる。あわせて keelMaxAboveSurface（名前は記録の互換のため残す）を記録するが、これは竜骨の中線ではなく
        // 「船の根の空間 z = +5 の端の船首／船尾材の点（36 頂点）の、面より上に出ている量の最大」である（下の注記を参照）。
        static Contact[] Contacts()
        {
            var supports = new Dictionary<string, string> { { "boat_fg", "AF27 参照海面" }, { "boat_mid", "M1_Revision_RightSlope" }, { "boat_left", "M1_Revision_LeftSupport" } };
            var list = new List<Contact>();
            foreach (var kv in supports)
            {
                var boat = GameObject.Find("AF27 船 " + kv.Key);
                var hull = boat.GetComponentsInChildren<MeshFilter>().Single(f => f.name == "Boat_Hull_OpenThick");
                var verts = hull.sharedMesh.vertices.Select(v => hull.transform.TransformPoint(v)).ToArray();
                var low = verts.OrderBy(v => v.y).First();
                var sup = GameObject.Find(kv.Value);
                if (sup == null) sup = UnityEngine.Object.FindObjectsByType<Transform>(FindObjectsInactive.Include).First(t => t.name == kv.Value).gameObject;
                var mf = sup.GetComponent<MeshFilter>();
                var mc = sup.AddComponent<MeshCollider>(); mc.sharedMesh = mf.sharedMesh; Physics.SyncTransforms();
                bool ok = mc.Raycast(new Ray(low + Vector3.up * 50, Vector3.down), out RaycastHit h, 200);
                var mid = boat.transform.position;
                bool okMid = mc.Raycast(new Ray(mid + Vector3.up * 50, Vector3.down), out RaycastHit hm, 200);
                // 注記：メッシュの局所で |x| < 0.05 かつ y < 0.2 を選ぶと、実際に選ばれるのは船の根の空間 z = +5 の端の船首／船尾材の 36 頂点
                // （根の空間の y 0.74〜1.74）で、船底の中線には頂点がない。したがって maxGapKeel は「+z 端の船首／船尾材の 36 頂点が支えの面より
                // 上に出ている量の最大（ほぼ材の最上点）」で、竜骨（船底の線）の浮きの量ではない（番号27 のコミット前レビューで判明。竜骨の中央の接地は keelMid で見る）。
                float maxGapKeel = float.NegativeInfinity; int keelSamples = 0;
                var keel = hull.sharedMesh.vertices.Where(v => Mathf.Abs(v.x) < 0.05f && v.y < 0.2f).Select(v => hull.transform.TransformPoint(v)).ToArray();
                foreach (var k in keel)
                {
                    if (mc.Raycast(new Ray(k + Vector3.up * 50, Vector3.down), out RaycastHit hk, 200)) { maxGapKeel = Mathf.Max(maxGapKeel, k.y - hk.point.y); keelSamples++; }
                }
                UnityEngine.Object.DestroyImmediate(mc);
                list.Add(new Contact { boat = kv.Key, support = kv.Value, lowestHullPoint = low, supportHit = ok, supportY = ok ? h.point.y : float.NaN,
                    penetration = ok ? h.point.y - low.y : float.NaN, keelSamples = keelSamples, keelMaxAboveSurface = keelSamples > 0 ? maxGapKeel : float.NaN,
                    keelMid = mid, keelMidHit = okMid, keelMidBelowSurface = okMid ? hm.point.y - mid.y : float.NaN });
            }
            return list.ToArray();
        }

        static float MaxAbsDiff(Matrix4x4 a, Matrix4x4 b) { float m = 0; for (int i = 0; i < 16; i++) m = Mathf.Max(m, Mathf.Abs(a[i] - b[i])); return m; }

        // 形成率 P_body(t) = smootherstep((t - 2) / 10)（番号24 の AF24FirstLight と同じ）
        static float Progress(float t) { float x = Mathf.Clamp01((t - 2f) / 10f); return x * x * x * (x * (x * 6f - 15f) + 10f); }

        static void RenderIds(Camera camera, string pngPath, string idmapPath, RenderReport rep)
        {
            const int w = W * 2, h = H * 2;
            var idShader = Shader.Find("GreatWave/ArtFirst/AF24 ID Flat");
            var mats = new Dictionary<string, Material>();
            Material Mat(string key, Color c) { if (!mats.TryGetValue(key, out var m)) { m = new Material(idShader) { hideFlags = HideFlags.DontSave }; m.SetColor("_IdColor", c); mats[key] = m; } return m; }
            var saved = new List<(Renderer, Material[])>();
            var dome = GameObject.Find("AF27 空のドーム");
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude))
            {
                string key = "other"; Color c = IdOther;
                if (dome != null && r.gameObject == dome) { key = "sky"; c = IdSky; }
                foreach (var b in IdBoats) { var root = GameObject.Find("AF27 船 " + b.Key); if (root != null && r.transform.IsChildOf(root.transform)) { key = b.Key; c = b.Value; } }
                saved.Add((r, r.sharedMaterials));
                r.sharedMaterials = Enumerable.Repeat(Mat(key, c), Math.Max(1, r.sharedMaterials.Length)).ToArray();
            }
            var clear = camera.clearFlags; var bg = camera.backgroundColor;
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = IdSky;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
            rt.Create();
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, true);
            var prev = camera.targetTexture; bool hdr = camera.allowHDR, aa = camera.allowMSAA;
            camera.allowHDR = false; camera.allowMSAA = false;
            camera.aspect = (float)w / h; camera.targetTexture = rt; camera.Render();
            RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply(); RenderTexture.active = null;
            File.WriteAllBytes(pngPath, tex.EncodeToPNG());
            var colors = new HashSet<int>(); foreach (var p in tex.GetPixels32()) colors.Add((p.r << 16) | (p.g << 8) | p.b);
            rep.idDistinctColors = colors.Count;
            camera.targetTexture = prev; camera.allowHDR = hdr; camera.allowMSAA = aa; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg;
            foreach (var (r, m) in saved) r.sharedMaterials = m;
            foreach (var m in mats.Values) UnityEngine.Object.DestroyImmediate(m);
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            File.WriteAllText(idmapPath, "{\n \"classes\": {\n  \"sky\": [0, 0, 255],\n  \"boat_left\": [255, 0, 0],\n  \"boat_mid\": [0, 255, 0],\n  \"boat_fg\": [255, 255, 0]\n },\n \"other\": [0, 0, 0],\n \"note_ja\": \"番号27 の ID 画像（3840×2160、MSAA なし）。空＝AF27 空のドーム（とカメラの背景）、三船はそれぞれの色、ほかは全て other（番号24 v0 の主役波・参照海面・富士・前景のうねりと斜面の仮置き）。\"\n}\n");
        }

        static void Capture(Camera camera, RenderTexture msaa, RenderTexture resolve, Texture2D tex, string path)
        {
            var prev = camera.targetTexture;
            camera.aspect = (float)W / H;
            camera.targetTexture = msaa;
            camera.Render();
            Graphics.Blit(msaa, resolve);
            RenderTexture.active = resolve;
            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            camera.targetTexture = prev;
            File.WriteAllBytes(path, tex.EncodeToPNG());
        }

        static Camera MakeCamera(GameObject parent, string name, Vector3 position, Vector3 target, float fov)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent.transform, false);
            var cam = go.AddComponent<Camera>();
            cam.enabled = false; // Camera.Render でだけ使う
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Color.black;
            cam.fieldOfView = fov; cam.nearClipPlane = .1f; cam.farClipPlane = 900; cam.aspect = (float)W / H;
            cam.allowHDR = false; cam.allowMSAA = true;
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

        static Material MaterialAsset(string name, string shaderName)
        {
            var shader = Shader.Find(shaderName);
            if (shader == null) throw new InvalidOperationException("シェーダーがありません: " + shaderName);
            string path = MatDir + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (m == null) { m = new Material(shader); AssetDatabase.CreateAsset(m, path); }
            m.shader = shader;
            EditorUtility.SetDirty(m);
            return m;
        }

        static Vector3 V(float[] a) => new Vector3(a[0], a[1], a[2]);

        [Serializable] class Layout { public UnityJ unity; }
        [Serializable] class UnityJ { public PalJ[] palette; public BoatJ[] boats; public FujiJ fuji; public SeaJ sea; public PhJ[] placeholders; public SeatJ seat; public SkyJ sky; }
        [Serializable] class PalJ { public string key; public int[] srgb8; }
        [Serializable] class MatJ { public string m1Material, palette; }
        [Serializable] class BoatJ { public string key, m1Name; public float[] position, rotation; public float scale; public MatJ[] materials; }
        [Serializable] class FujiJ { public float[] position, scale; public MatJ[] materials; }
        [Serializable] class SeaJ { public float[] position, scale; public string palette; }
        [Serializable] class PhJ { public string name; public float translateY; public MatJ[] materials; }
        [Serializable] class SeatJ { public string boatKey; public float[] eyeNumpy, target, probeLocal; public float fov, eyeAboveDeck; }
        [Serializable] class SkyJ { public float radius, theta0, wFull, wZero, thetaAz0, thetaStep, gradE0, gradStep; public float[] thetaT, gradientRGB; }
        [Serializable] class BuildReport
        {
            public string unity, utc, scene, sceneSha256; public Vector3 eyeUnity, eyeNumpy, deckHit, probe; public float eyeDiff;
            public bool protectedUnchanged; public string[] protectedFiles, prefabs;
        }
        [Serializable] class Contact { public string boat, support; public Vector3 lowestHullPoint, keelMid; public bool supportHit, keelMidHit; public float supportY, penetration, keelMaxAboveSurface, keelMidBelowSurface; public int keelSamples; }
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, startedUtc, finishedUtc, renderMethod;
            public int frames, tStarFrame, renderedFrames, idDistinctColors; public float fps, totalSeconds;
            public float cameraMaxPositionDelta, cameraMaxAngleDeltaDeg, cameraMaxFovDelta, cameraMaxProjectionDelta, cameraMaxViewDelta, cameraFov;
            public Vector3 cameraPosition, cameraEuler, seatEye; public Contact[] contacts;
        }
    }
}
