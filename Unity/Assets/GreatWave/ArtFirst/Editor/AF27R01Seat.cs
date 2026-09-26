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
    // 番号27修正01「座席を唇の真下の右船へ移す」（D7 = (a)、利用者の CP1 回答 2026-09-26）。
    // Tools/GWContext/seat_v1.json（af27r01_seat.py の出力）を読み、番号27 のプレハブ AF27_Context.prefab を置いて完全に展開したうえで、
    //   ・右船（boat_mid）を PaintingCam v1 の投影中心を中心に k 倍した置き方へ直す（原画視点の像は変わらない）
    //   ・右の斜面の仮置き（M1_Revision_RightSlope）のメッシュを、右船を載せる水面に作り直したもの（AF27R01_RightSlope.asset）へ差し替える
    //   ・座席 v1 の位置に目印（座席の Transform）を置く
    // を行い、新しいプレハブ AF27R01_Context.prefab とシーン AF27R01_Seat.unity を作る。主役波は番号26 の K* 45°（D6 の裁定）に番号28 の NPR v1・外殻線 v0。
    // 番号26・27・28・CP1 のファイルは読むだけで変えない（前後の SHA-256 を記録する）。
    // 描画は Camera.Render → RenderTexture → PNG（PC のオフスクリーン描画。HMD 実機ではない）。
    public static class AF27R01Seat
    {
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF27R01_Seat.unity";
        const string OutRoot = "Build/ArtFirst/27R01";
        const string SeatJsonPath = "../Tools/GWContext/seat_v1.json";
        const string ContextPrefab = "Assets/GreatWave/ArtFirst/Prefabs/AF27_Context.prefab";
        const string NewPrefab = "Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab";
        const string MeshDir = "Assets/GreatWave/ArtFirst/Meshes";
        const string MeshAsset = MeshDir + "/AF27R01_RightSlope.asset";
        const string NprMatPath = "Assets/GreatWave/ArtFirst/Materials/AF28_NPR.mat";
        const string OutlineMatPath = "Assets/GreatWave/ArtFirst/Materials/AF28_Outline.mat";
        const string KStarPath = "Build/ArtFirst/26/kstar/kstar_a45.gwb";
        const string SdfPath = "Build/ArtFirst/28/bake/af28_uvsdf_a45.bin";
        const string WarpPath = "Build/ArtFirst/28/bake/af28_uvwarp_a45.json";
        const string RootName = "AF27R01 背景（番号27 の背景、右船の置き直しと右船の水面）";
        const string SeatName = "AF27R01 座席 v1（右船、甲板から 1.2 m 上）";
        const string WaveName = "AF27R01 K* a45（番号26、NPR v1）";
        const int W = 1920, H = 1080;

        static readonly Vector3 PaintingPosition = new Vector3(0, 3, -62), PaintingTarget = new Vector3(-2.5f, 9.7f, 4);
        // 横（手前から近く）：右船の側面と、その上の唇
        static readonly Vector3 SideNearPosition = new Vector3(5, 7, -44), SideNearTarget = new Vector3(3, 7, -13);
        const float SideNearFov = 50;
        // 船尾の側の上から：船の軸の延長の上（右の斜面の仮置きの上）から、船・水面・唇の奥行きの関係を見る
        static readonly Vector3 SternPosition = new Vector3(34, 22, -27), SternTarget = new Vector3(3, 7, -13);
        const float SternFov = 50;
        // 評価器の ID 色（番号27・CP1 と同じ）
        static readonly Color IdSky = new Color(0, 0, 1), IdOther = new Color(0, 0, 0);
        static readonly Dictionary<string, Color> IdBoats = new Dictionary<string, Color> {
            { "boat_left", new Color(1, 0, 0) }, { "boat_mid", new Color(0, 1, 0) }, { "boat_fg", new Color(1, 1, 0) } };

        static string[] ProtectedFiles => new[] {
            ContextPrefab, "Assets/GreatWave/ArtFirst/Prefabs/AF27_SkyDome.prefab", NprMatPath, OutlineMatPath,
            "Assets/GreatWave/ArtFirst/Materials/AF27_SkyDome.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_ai_dark.mat",
            "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_white.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_boat_ochre.mat",
            "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_fuji_snow.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_Flat_fuji_slope.mat",
            "Assets/GreatWave/ArtFirst/Textures/AF27_SkyThetaT.asset", "Assets/GreatWave/ArtFirst/Textures/AF27_SkyGradient.asset",
            "Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs", "Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs",
            "Assets/GreatWave/ArtFirst/Shaders/AF28_NPR.shader", "Assets/GreatWave/ArtFirst/Shaders/AF28_Outline.shader",
            "Assets/GreatWave/ArtFirst/Shaders/AF27SkyDome.shader", "Assets/GreatWave/ArtFirst/Shaders/AF27Flat.shader",
            "Assets/GreatWave/Scenes/Tests/AF27_Context.unity", "Assets/GreatWave/Scenes/Tests/AF_CP1.unity",
            "Assets/GreatWave/Scenes/Tests/AF28_NPR.unity", "Assets/GreatWave/Scenes/Tests/AF26_KStar.unity",
            AF27ContextBuilder.FbxPath("boat_blockout"), AF27ContextBuilder.FbxPath("revision_slopes") };

        public static void BuildAndRender() { Build(); Render(); }

        // ------------------------------------------------------------------ 組み立て
        public static void Build()
        {
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            var S = JsonUtility.FromJson<SeatFile>(File.ReadAllText(SeatJsonPath)).unity;
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            RenderSettings.ambientMode = AmbientMode.Flat; RenderSettings.ambientLight = Color.white; RenderSettings.fog = false;
            RenderSettings.skybox = null;

            // 番号27 の背景一式を置き、完全に展開する（番号27 のプレハブは変えない）
            var ctxAsset = AssetDatabase.LoadAssetAtPath<GameObject>(ContextPrefab);
            if (ctxAsset == null) throw new InvalidOperationException("番号27 のプレハブがありません: " + ContextPrefab);
            var ctx = (GameObject)PrefabUtility.InstantiatePrefab(ctxAsset);
            PrefabUtility.UnpackPrefabInstance(ctx, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            ctx.name = RootName;

            // 右船：k 倍した置き方（位置・縮尺。回転は番号27 と同じ）
            var mid = ctx.GetComponentsInChildren<Transform>(true).First(t => t.name == "AF27 船 " + S.boatKey);
            var pos27 = mid.localPosition; var scale27 = mid.localScale.x; var rot27 = mid.localRotation;
            mid.localPosition = V(S.boatPosition);
            mid.localRotation = new Quaternion(S.boatRotation[0], S.boatRotation[1], S.boatRotation[2], S.boatRotation[3]);
            mid.localScale = Vector3.one * S.boatScale;

            // 右の斜面の仮置き → 右船を載せる水面（af27r01_seat.py が作った頂点・三角形、世界座標）
            var slope = ctx.GetComponentsInChildren<MeshFilter>(true).First(f => f.name == "M1_Revision_RightSlope");
            var mesh = LoadWaterMesh(S.waterMeshBin, slope.transform);
            if (!AssetDatabase.IsValidFolder(MeshDir)) AssetDatabase.CreateFolder("Assets/GreatWave/ArtFirst", "Meshes");
            if (AssetDatabase.LoadAssetAtPath<Mesh>(MeshAsset) != null) AssetDatabase.DeleteAsset(MeshAsset);
            AssetDatabase.CreateAsset(mesh, MeshAsset);
            mesh = AssetDatabase.LoadAssetAtPath<Mesh>(MeshAsset);
            slope.sharedMesh = mesh;
            slope.gameObject.name = "M1_Revision_RightSlope";   // 名前は番号27 と同じ（接地の確認などで引く）
            var slopeR = slope.GetComponent<MeshRenderer>();
            if (slopeR.sharedMaterials.Length != 2) throw new InvalidOperationException("右の斜面の材質の数が 2 ではありません。");

            // 座席 v1：番号27 と同じ測り方で甲板を測り、numpy の目の位置と比べる
            var deck = mid.GetComponentsInChildren<MeshFilter>().Single(f => f.name == "Boat_Deck_Planks");
            var col = deck.gameObject.AddComponent<MeshCollider>(); col.sharedMesh = deck.sharedMesh; Physics.SyncTransforms();
            var probe = mid.TransformPoint(V(S.probeLocal));
            bool hitDeck = col.Raycast(new Ray(probe, -mid.up), out RaycastHit hit, 100);
            UnityEngine.Object.DestroyImmediate(col);
            if (!hitDeck) throw new InvalidOperationException("右船の甲板を測れません。");
            var eye = hit.point + Vector3.up * S.eyeAboveDeck;
            var seat = new GameObject(SeatName);
            seat.transform.SetParent(ctx.transform, false);
            seat.transform.position = eye;
            seat.transform.rotation = Quaternion.LookRotation(V(S.target) - eye, Vector3.up);

            // 新しいプレハブ（CP2・番号30 の合成で使う）：背景一式＋右船の置き直し＋右船の水面＋座席の目印。主役波とカメラは入れない
            PrefabUtility.SaveAsPrefabAssetAndConnect(ctx, NewPrefab, InteractionMode.AutomatedAction);

            // 主役波 K* 45°（番号26）＋ NPR v1・外殻線 v0（番号28 のマテリアルを参照するだけ）
            var npr = AssetDatabase.LoadAssetAtPath<Material>(NprMatPath);
            var outline = AssetDatabase.LoadAssetAtPath<Material>(OutlineMatPath);
            if (npr == null || outline == null) throw new InvalidOperationException("番号28 のマテリアルがありません。");
            var wave = new GameObject(WaveName);
            wave.AddComponent<MeshFilter>();
            var wr = wave.AddComponent<MeshRenderer>();
            wr.sharedMaterial = npr; Quiet(wr);
            wave.AddComponent<AF26KStarMesh>().dataPath = KStarPath;
            var line = new GameObject("AF27R01 外殻線 v0（番号28）");
            line.transform.SetParent(wave.transform, false);
            line.AddComponent<MeshFilter>();
            var lr = line.AddComponent<MeshRenderer>();
            lr.sharedMaterial = outline; Quiet(lr);
            var nw = wave.AddComponent<AF28NprWave>();
            nw.sdfPath = SdfPath; nw.warpPath = WarpPath; nw.size = 4096; nw.outline = lr;

            var cams = new GameObject("AF27R01 カメラ");
            MakeCamera(cams, "AF27R01 PaintingCam v1", PaintingPosition, PaintingTarget, 26);
            MakeCamera(cams, "AF27R01 座席 v1（唇へ）", eye, V(S.target), S.fov);
            // 座席 v1（唇の方位で仰角 20°）：船・水面・波の足もとまで入る向き
            var f = V(S.target) - eye; f.y = 0; f.Normalize();
            var dirLow = (f * Mathf.Cos(20 * Mathf.Deg2Rad) + Vector3.up * Mathf.Sin(20 * Mathf.Deg2Rad)).normalized;
            MakeCamera(cams, "AF27R01 座席 v1（唇の方位、仰角 20°）", eye, eye + dirLow * 10, S.fov);
            // 座席 v1 から船首（甲板の前の尖った所、船の根の局所 (0, 0.5, 4.2)）を見下ろす：船の中を水面が横切らないかの確認
            MakeCamera(cams, "AF27R01 座席 v1（船首を見下ろす）", eye, mid.TransformPoint(new Vector3(0, 0.5f, 4.2f)), S.fov);
            MakeCamera(cams, "AF27R01 横（手前から近く）", SideNearPosition, SideNearTarget, SideNearFov);
            MakeCamera(cams, "AF27R01 船尾の側の上から", SternPosition, SternTarget, SternFov);
            // 接地の確認：船の軸に直交し PaintingCam の側を向く水平方向から、仰角 12° で船体の中央を見る（番号27 と同じ置き方）
            var hullF = mid.GetComponentsInChildren<MeshFilter>().Single(x => x.name == "Boat_Hull_OpenThick");
            var hb = hullF.GetComponent<Renderer>().bounds;
            var axis = mid.forward; axis.y = 0; axis.Normalize();
            var side = Vector3.Cross(Vector3.up, axis).normalized;
            if (Vector3.Dot(side, PaintingPosition - hb.center) < 0) side = -side;
            var dirC = (side * Mathf.Cos(12 * Mathf.Deg2Rad) + Vector3.up * Mathf.Sin(12 * Mathf.Deg2Rad)).normalized;
            MakeCamera(cams, "AF27R01 接地確認", hb.center + dirC * (9f * S.boatScale + 3f), hb.center, 50);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("シーンを保存できません。");
            AssetDatabase.SaveAssets();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            var rep = new BuildReport
            {
                unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePath, sceneSha256 = Sha(ScenePath),
                prefab = NewPrefab, prefabSha256 = Sha(NewPrefab), meshAsset = MeshAsset, meshSha256 = Sha(MeshAsset),
                meshVertices = mesh.vertexCount, meshSubMeshes = mesh.subMeshCount,
                boatPosition27 = pos27, boatScale27 = scale27, boatRotation27 = rot27,
                boatPosition = mid.position, boatScale = mid.localScale.x, boatRotation = mid.rotation,
                probe = probe, deckHit = hit.point, eyeUnity = eye, eyeNumpy = V(S.eyeNumpy), eyeDiff = Vector3.Distance(eye, V(S.eyeNumpy)),
                target = V(S.target), fov = S.fov,
                protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]),
                protectedFiles = ProtectedFiles.Select(p => p + " " + after[p]).ToArray(),
                changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray()
            };
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/af27r01_build_report.json", JsonUtility.ToJson(rep, true));
            if (!rep.protectedUnchanged) throw new InvalidOperationException("番号26・27・28・CP1 の資産が変わりました: " + string.Join(", ", rep.changedFiles));
            if (rep.eyeDiff > 0.002f) throw new InvalidOperationException("座席の目が numpy と 2 mm 以上ずれました: " + rep.eyeDiff);
            UnityEngine.Debug.Log("AF27R01_BUILD_DONE eyeDiff=" + rep.eyeDiff);
        }

        static Mesh LoadWaterMesh(string path, Transform tr)
        {
            var b = File.ReadAllBytes(path);
            if (b.Length < 16 || b[0] != 'G' || b[1] != 'W' || b[2] != 'M' || b[3] != '1') throw new InvalidOperationException("GWM1 ではありません: " + path);
            int nV = BitConverter.ToInt32(b, 4), n0 = BitConverter.ToInt32(b, 8), n1 = BitConverter.ToInt32(b, 12);
            int off = 16;
            var v = new Vector3[nV];
            for (int i = 0; i < nV; i++, off += 12)
                v[i] = tr.InverseTransformPoint(new Vector3(BitConverter.ToSingle(b, off), BitConverter.ToSingle(b, off + 4), BitConverter.ToSingle(b, off + 8)));
            var i0 = new int[n0]; for (int i = 0; i < n0; i++, off += 4) i0[i] = BitConverter.ToInt32(b, off);
            var i1 = new int[n1]; for (int i = 0; i < n1; i++, off += 4) i1[i] = BitConverter.ToInt32(b, off);
            if (off != b.Length) throw new InvalidOperationException("GWM1 の長さが合いません。");
            var m = new Mesh { name = "AF27R01_RightSlope", indexFormat = IndexFormat.UInt32 };
            m.vertices = v;
            m.subMeshCount = 2;
            m.SetTriangles(i0, 0); m.SetTriangles(i1, 1);
            m.RecalculateNormals(); m.RecalculateBounds();
            return m;
        }

        static void Quiet(Renderer r)
        {
            r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
            r.lightProbeUsage = LightProbeUsage.Off; r.reflectionProbeUsage = ReflectionProbeUsage.Off;
        }

        // ------------------------------------------------------------------ 描画
        public static void Render()
        {
            var total = Stopwatch.StartNew();
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var wave = FindRoot(WaveName);
            var nw = wave.GetComponent<AF28NprWave>();
            var mesh = nw.EnsureLoaded();
            string dir = OutRoot + "/render";
            Directory.CreateDirectory(dir);
            var files = new List<string>();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            nw.outline.enabled = true;
            var views = new[] {
                ("painting", "AF27R01 PaintingCam v1"), ("seat_lip", "AF27R01 座席 v1（唇へ）"), ("seat_low", "AF27R01 座席 v1（唇の方位、仰角 20°）"),
                ("seat_bow", "AF27R01 座席 v1（船首を見下ろす）"), ("side_near", "AF27R01 横（手前から近く）"), ("stern", "AF27R01 船尾の側の上から") };
            foreach (var (key, cam) in views) files.Add(Capture(FindCamera(cam), dir + "/af27r01_" + key + ".png"));
            // 接地の確認図：右船・右船の水面・参照海面・K*（平らな海）・空だけを表示する（確認用の図で、場面の見え方ではない）
            var ctx = FindRoot(RootName).transform;
            var mid = ctx.GetComponentsInChildren<Transform>(true).First(t => t.name == "AF27 船 boat_mid");
            var slope = ctx.GetComponentsInChildren<Transform>(true).First(t => t.name == "M1_Revision_RightSlope");
            var keep = new List<Transform> { mid, slope, wave.transform };
            var hidden = new List<Renderer>();
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude))
            {
                if (!r.enabled) continue;
                if (keep.Any(k => r.transform.IsChildOf(k)) || r.name == "AF27 空のドーム" || r.name == "AF27 参照海面") continue;
                r.enabled = false; hidden.Add(r);
            }
            try { files.Add(Capture(FindCamera("AF27R01 接地確認"), dir + "/af27r01_contact.png")); }
            finally { foreach (var r in hidden) r.enabled = true; }
            // 評価器用の ID（外殻線なし＝番号26・CP1 と同じ判定の条件、外殻線あり＝空の項目）
            var painting = FindCamera("AF27R01 PaintingCam v1");
            nw.outline.enabled = false;
            files.Add(RenderIds(painting, dir + "/af27r01_painting_ids.png"));
            nw.outline.enabled = true;
            files.Add(RenderIds(painting, dir + "/af27r01_painting_ids_line.png"));
            File.WriteAllText(dir + "/idmap.json",
                "{\n \"classes\": {\n  \"sky\": [0, 0, 255],\n  \"boat_left\": [255, 0, 0],\n  \"boat_mid\": [0, 255, 0],\n  \"boat_fg\": [255, 255, 0]\n },\n \"other\": [0, 0, 0],\n" +
                " \"note_ja\": \"番号27修正01 の ID 画像（3840×2160、MSAA なし）。CP1 と同じ規則：空＝番号27 の空のドーム（とカメラの背景）、3隻はそれぞれの色、ほかは全て other（K*・参照海面・富士・前景のうねりと斜面の仮置き・右船の水面は (0,0,0)、_ids_line.png の外殻線は (255,0,255)）。\"\n}\n");

            // Unity 側の接水の確認：船の軸に沿った s = −3, 0, +3 m で、軸から左右へ水平に 1.75 m（船体の足跡の外、水面の重み ≈ 1）の点の真上から
            // 右船の水面へ射線を当て、水面の高さと竜骨の線（numpy の当てはめ）の差を記録する（喫水に近いはず）。船の根の原点の真下は船体の足跡の穴なので使わない。
            var S = JsonUtility.FromJson<SeatFile>(File.ReadAllText(SeatJsonPath)).unity;
            var mc = slope.gameObject.AddComponent<MeshCollider>(); mc.sharedMesh = slope.GetComponent<MeshFilter>().sharedMesh; Physics.SyncTransforms();
            var hull = mid.GetComponentsInChildren<MeshFilter>().Single(x => x.name == "Boat_Hull_OpenThick");
            var hv = hull.sharedMesh.vertices.Select(v => hull.transform.TransformPoint(v)).ToArray();
            var low = hv.OrderBy(v => v.y).First();
            bool okMid = mc.Raycast(new Ray(mid.position + Vector3.up * 50, Vector3.down), out RaycastHit hm, 200);
            var probes = new List<WaterProbe>();
            var aH = V(S.keelAxisH); var nH = V(S.keelNormalH); var pRef = V(S.keelRef);
            foreach (var sAlong in new[] { -3f, 0f, 3f })
                foreach (var side in new[] { -1.75f, 1.75f })
                {
                    var q = pRef + aH * sAlong + nH * side; q.y = 0;
                    bool ok = mc.Raycast(new Ray(q + Vector3.up * 60, Vector3.down), out RaycastHit hw, 200);
                    float keelY = S.keelY0 + S.keelSlope * sAlong;
                    probes.Add(new WaterProbe { s = sAlong, lateral = side, hit = ok, waterY = ok ? hw.point.y : float.NaN, keelLineY = keelY,
                                                waterMinusKeelLine = ok ? hw.point.y - keelY : float.NaN, draft = S.draft });
                }
            UnityEngine.Object.DestroyImmediate(mc);
            var cams = new[] { "AF27R01 PaintingCam v1", "AF27R01 座席 v1（唇へ）", "AF27R01 座席 v1（唇の方位、仰角 20°）", "AF27R01 座席 v1（船首を見下ろす）", "AF27R01 横（手前から近く）", "AF27R01 船尾の側の上から", "AF27R01 接地確認" }
                .Select(n => { var c = FindCamera(n); return new CamRec { name = n, position = c.transform.position, euler = c.transform.rotation.eulerAngles, forward = c.transform.forward, fov = c.fieldOfView }; }).ToArray();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            var rep = new RenderReport
            {
                unity = Application.unityVersion, device = SystemInfo.graphicsDeviceName, graphicsApi = SystemInfo.graphicsDeviceType.ToString(),
                colorSpace = QualitySettings.activeColorSpace.ToString(),
                renderMethod = "Editor batchmode：Camera.Render → RenderTexture → ReadPixels → PNG。色は sRGB の RT（MSAA 8x → 解決）、ID は線形の RT（MSAA なし、3840×2160）。PC のオフスクリーン描画で、HMD 実機ではない。",
                waveVertexCount = mesh.vertexCount, gwb = wave.GetComponent<AF26KStarMesh>().FullDataPath, gwbSha256 = Sha(wave.GetComponent<AF26KStarMesh>().FullDataPath),
                sdf = nw.FullSdfPath, sdfSha256 = Sha(nw.FullSdfPath), cameras = cams,
                hullLowest = low, keelMid = mid.position, keelMidHit = okMid, keelMidWaterY = okMid ? hm.point.y : float.NaN,
                keelMidBelowWater = okMid ? hm.point.y - mid.position.y : float.NaN, waterProbes = probes.ToArray(),
                files = files.ToArray(), filesSha256 = files.Select(Sha).ToArray(),
                protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]), totalSeconds = (float)total.Elapsed.TotalSeconds
            };
            rep.passed = rep.protectedUnchanged && mesh.vertexCount == 80000;
            File.WriteAllText(OutRoot + "/af27r01_render_report.json", JsonUtility.ToJson(rep, true));
            UnityEngine.Debug.Log("AF27R01_RENDER_DONE files=" + files.Count + " seconds=" + rep.totalSeconds);
            if (!rep.passed) throw new InvalidOperationException("描画の検査が不合格です。");
        }

        static string Capture(Camera camera, string path)
        {
            var prev = camera.targetTexture;
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
            var res = new RenderTexture(W, H, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rt.Create(); res.Create();
            camera.aspect = (float)W / H;
            camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(W, H, TextureFormat.RGB24, false);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, W, H), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = prev;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
            return path;
        }

        // CP1（AFCP1Composite.RenderIds）と同じ規則：AF24 ID Flat で塗り分け、MSAA なし、3840×2160。外殻線は番号28 の ID 表示（(1,0,1)＝other）
        static string RenderIds(Camera camera, string pngPath)
        {
            const int w = W * 2, h = H * 2;
            var idShader = Shader.Find("GreatWave/ArtFirst/AF24 ID Flat");
            if (idShader == null) throw new InvalidOperationException("AF24 ID Flat がありません。");
            var mats = new Dictionary<string, Material>();
            Material Mat(string key, Color c) { if (!mats.TryGetValue(key, out var m)) { m = new Material(idShader) { hideFlags = HideFlags.DontSave }; m.SetColor("_IdColor", c); mats[key] = m; } return m; }
            var saved = new List<(Renderer, Material[])>();
            var dome = GameObject.Find("AF27 空のドーム");
            if (dome == null) throw new InvalidOperationException("空のドームがありません。");
            var boatRoots = IdBoats.Keys.ToDictionary(k => k, k => GameObject.Find("AF27 船 " + k));
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude))
            {
                if (!r.enabled) continue;
                if (r.sharedMaterial != null && r.sharedMaterial.shader != null && r.sharedMaterial.shader.name == "GreatWave/ArtFirst/AF28 Outline v0") continue;
                string key = "other"; Color c = IdOther;
                if (r.gameObject == dome) { key = "sky"; c = IdSky; }
                foreach (var b in IdBoats) { var root = boatRoots[b.Key]; if (root != null && r.transform.IsChildOf(root.transform)) { key = b.Key; c = b.Value; } }
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
            Shader.SetGlobalFloat("_AF28IdMode", 1);
            camera.aspect = (float)w / h; camera.targetTexture = rt; camera.Render();
            Shader.SetGlobalFloat("_AF28IdMode", 0);
            RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply(); RenderTexture.active = null;
            File.WriteAllBytes(pngPath, tex.EncodeToPNG());
            camera.targetTexture = prev; camera.allowHDR = hdr; camera.allowMSAA = aa; camera.aspect = (float)W / H;
            camera.clearFlags = clear; camera.backgroundColor = bg;
            foreach (var (r, m) in saved) r.sharedMaterials = m;
            foreach (var m in mats.Values) UnityEngine.Object.DestroyImmediate(m);
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            return pngPath;
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

        static GameObject FindRoot(string name)
        {
            var go = EditorSceneManager.GetActiveScene().GetRootGameObjects().FirstOrDefault(g => g.name == name);
            if (go == null) throw new InvalidOperationException("見つかりません: " + name);
            return go;
        }

        static string Sha(string path)
        {
            using (var s = System.Security.Cryptography.SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        static Vector3 V(float[] a) => new Vector3(a[0], a[1], a[2]);

        [Serializable] class SeatFile { public SeatJ unity; }
        [Serializable] class SeatJ
        {
            public string boatKey, waterMeshBin; public float[] boatPosition, boatRotation, probeLocal, eyeNumpy, target;
            public float boatScale, eyeAboveDeck, fov;
            public float keelY0, keelSlope, draft; public float[] keelAxisH, keelNormalH, keelRef;
        }
        [Serializable] class WaterProbe { public float s, lateral, waterY, keelLineY, waterMinusKeelLine, draft; public bool hit; }
        [Serializable] class BuildReport
        {
            public string unity, utc, scene, sceneSha256, prefab, prefabSha256, meshAsset, meshSha256;
            public int meshVertices, meshSubMeshes;
            public Vector3 boatPosition27, boatPosition, probe, deckHit, eyeUnity, eyeNumpy, target; public Quaternion boatRotation27, boatRotation;
            public float boatScale27, boatScale, eyeDiff, fov;
            public bool protectedUnchanged; public string[] protectedFiles, changedFiles;
        }
        [Serializable] class CamRec { public string name; public Vector3 position, euler, forward; public float fov; }
        [Serializable] class RenderReport
        {
            public string unity, device, graphicsApi, colorSpace, renderMethod, gwb, gwbSha256, sdf, sdfSha256;
            public int waveVertexCount; public CamRec[] cameras;
            public Vector3 hullLowest, keelMid; public bool keelMidHit; public float keelMidWaterY, keelMidBelowWater; public WaterProbe[] waterProbes;
            public string[] files, filesSha256; public bool protectedUnchanged, passed; public float totalSeconds;
        }
    }
}
