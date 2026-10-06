using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using GreatWave.Design30;
using GreatWave.Polish29;

namespace GreatWave.FLIP37Proto.EditorTools
{
    // FLIP37 組み込みの準備の独立の試作の場面（先生の指示 Q37。巻き込みのある波ができた後に作品へ組み込むための下準備）。
    // 作品の場面・材質・スクリプトは開かない・変えない。この試作のフォルダー（Assets/GreatWave/FLIP37Proto）の中に、
    // 新しい場面 F37Proto.unity と新しい材質（AS05 のシェーダーを変えずに使う F37_AS05_Static.mat、周りの遠い海の単色 F37_SeaFar.mat）だけを作る。
    // カメラ：原画カメラ PaintingCam v1（位置 (0,3,−62)、注視点 (−2.5,9.7,4)、縦の画角 26°）と座席 seat_v1（Tools/GWContext/seat_v1.json の目と注視点、縦の画角 80°）。
    // 流体の並び：Unity/Build/FLIP37/integration_prep/pkg/<seq>/{sheet,frames}/index.json（Tools/GWWaveGen/flip37/integ_convert.py が書く）。
    // 入口：
    //   GreatWave.FLIP37Proto.EditorTools.F37ProtoBuild.Build   場面と材質を作る
    //   GreatWave.FLIP37Proto.EditorTools.F37ProtoBuild.Render  場面を開いて、方法 A（sheet＋周りの海）と方法 B（frames）を 2 つのカメラで描き PNG に書く
    //     引数：-f37Seqs R05,P1sweep  -f37Fps 24  -f37W 960 -f37H 540
    //     方法 A は作品の再生器でも描く（keypose）：Unity/Build/FLIP37/integration_prep/keypose/<seq>/ の包み（integ_keypose.py が書く、書式 GreatWave.DS27.keypose/1）を
    //     作品の DS30SheetPlayer（変えない）で読み、作品の PL29UkiyoeHero（変えない）で 12 個の属性を入れ、AS05 の keypose の道（_AS03Src = 0）の新しい材質で描く。
    public static class F37ProtoBuild
    {
        const string Root = "Assets/GreatWave/FLIP37Proto";
        const string ScenePath = Root + "/Scenes/F37Proto.unity";
        const string MatPath = Root + "/Materials/F37_AS05_Static.mat";
        const string SeaMatPath = Root + "/Materials/F37_SeaFar.mat";
        const string KpMatPath = Root + "/Materials/F37_AS05_Keypose.mat";
        const string ShaderName = "GreatWave/ArtSample05/AS05FlatSmoothKeypose";
        static readonly Vector3 PaintPos = new Vector3(0, 3, -62), PaintTgt = new Vector3(-2.5f, 9.7f, 4f);
        static readonly Vector3 SeatEye = new Vector3(3.9544f, 1.8323f, -15.0308f), SeatTgt = new Vector3(0.655f, 12.0f, -11.155f);
        static readonly Color32 Sky = new Color32(249, 232, 196, 255);
        static readonly Color SeaCol = new Color(0.13333f, 0.24706f, 0.37647f, 1f);
        static readonly string[] Seqs = { "R05", "P1sweep", "R18" };   // R18（P2 の本物の 3D の巻き波、誘導なし）は 2026-10-06 23:43 に追加

        static string Prep => Path.GetFullPath(Path.Combine(Application.dataPath, "../Build/FLIP37/integration_prep")).Replace('\\', '/');

        static string Arg(string[] a, string name)
        {
            int i = Array.IndexOf(a, name);
            return i >= 0 && i + 1 < a.Length ? a[i + 1] : null;
        }

        static void EnsureFolder(string parent, string name)
        {
            if (!AssetDatabase.IsValidFolder(parent + "/" + name)) AssetDatabase.CreateFolder(parent, name);
        }

        public static void Build()
        {
            EnsureFolder("Assets/GreatWave", "FLIP37Proto");
            EnsureFolder(Root, "Scenes");
            EnsureFolder(Root, "Materials");
            var sh = Shader.Find(ShaderName);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + ShaderName);
            var mat = AssetDatabase.LoadAssetAtPath<Material>(MatPath);
            if (mat == null) { mat = new Material(sh) { name = "F37_AS05_Static" }; AssetDatabase.CreateAsset(mat, MatPath); }
            mat.shader = sh;
            mat.SetFloat("_AS03Src", 1f);
            EditorUtility.SetDirty(mat);
            var seaMat = AssetDatabase.LoadAssetAtPath<Material>(SeaMatPath);
            if (seaMat == null) { seaMat = new Material(Shader.Find("Unlit/Color")) { name = "F37_SeaFar" }; AssetDatabase.CreateAsset(seaMat, SeaMatPath); }
            seaMat.SetColor("_Color", SeaCol);
            EditorUtility.SetDirty(seaMat);
            var kpMat = AssetDatabase.LoadAssetAtPath<Material>(KpMatPath);
            if (kpMat == null) { kpMat = new Material(sh) { name = "F37_AS05_Keypose" }; AssetDatabase.CreateAsset(kpMat, KpMatPath); }
            kpMat.shader = sh;
            kpMat.SetFloat("_AS03Src", 0f);
            EditorUtility.SetDirty(kpMat);
            AssetDatabase.SaveAssets();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var cams = new GameObject("F37 Cameras");
            MakeCamera(cams, "painting", PaintPos, PaintTgt, 26f);
            MakeCamera(cams, "seat", SeatEye, SeatTgt, 80f);
            // 遠くの海（計算の箱の外を空の色にしないための単色の面。y = −14 m、計算の谷より下）
            var sea = GameObject.CreatePrimitive(PrimitiveType.Quad);
            sea.name = "F37 SeaFar（単色、y −14）";
            UnityEngine.Object.DestroyImmediate(sea.GetComponent<Collider>());
            sea.transform.position = new Vector3(0, -14f, 0);
            sea.transform.rotation = Quaternion.Euler(90, 0, 0);
            sea.transform.localScale = new Vector3(4000, 4000, 1);
            sea.GetComponent<MeshRenderer>().sharedMaterial = seaMat;
            var root = new GameObject("F37 Players");
            foreach (var s in Seqs)
            {
                var g = new GameObject("F37 " + s);
                g.transform.SetParent(root.transform, false);
                AddPlayer(g, s, "sheet", false, 0f, mat);
                AddPlayer(g, s, "frames", false, 0f, mat);
                AddPlayer(g, s, "frames", true, 0.05f, mat);
                AddKeypose(g, s, kpMat);
            }
            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("場面を保存できません");
            AssetDatabase.SaveAssets();
            Debug.Log("F37_BUILD_DONE " + ScenePath);
        }

        static void AddPlayer(GameObject parent, string seq, string method, bool seaOnly, float yOff, Material mat)
        {
            var go = new GameObject(method + (seaOnly ? "_sea" : ""));
            go.transform.SetParent(parent.transform, false);
            go.AddComponent<MeshFilter>(); go.AddComponent<MeshRenderer>();
            var p = go.AddComponent<F37SeqPlayer>();
            p.indexPath = Prep + "/pkg/" + seq + "/" + method + "/index.json";
            p.material = mat; p.seaOnly = seaOnly; p.yOffset = yOff; p.interpolate = method == "sheet";
            go.SetActive(false);
        }

        static void AddKeypose(GameObject parent, string seq, Material kpMat)
        {
            var go = new GameObject("keypose");
            go.transform.SetParent(parent.transform, false);
            go.AddComponent<MeshFilter>();
            var mr = go.AddComponent<MeshRenderer>(); mr.sharedMaterial = kpMat;
            mr.shadowCastingMode = ShadowCastingMode.Off; mr.receiveShadows = false;
            var sp = go.AddComponent<DS30SheetPlayer>();
            sp.sheetName = "F37 " + seq;
            sp.packageDir = Prep + "/keypose/" + seq;
            sp.meshGwb = Prep + "/keypose/" + seq + "/tstar_sheet.gwb";
            sp.uv3File = ""; sp.warpPath = ""; sp.sdfPath = "";
            sp.readPosLo = true; sp.whiteEnabled = true; sp.verifySha256 = true;
            var ph = go.AddComponent<PL29UkiyoeHero>();
            ph.sheet = sp; ph.attrPath = Prep + "/keypose/" + seq + "/f37_hero_attr_f32.bin"; ph.material = kpMat;
            go.SetActive(false);
        }

        static Camera MakeCamera(GameObject parent, string name, Vector3 pos, Vector3 tgt, float fov)
        {
            var go = new GameObject("F37 " + name);
            go.transform.SetParent(parent.transform, false);
            var cam = go.AddComponent<Camera>();
            cam.enabled = false;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = Sky;
            cam.fieldOfView = fov; cam.nearClipPlane = 0.1f; cam.farClipPlane = 3000f;
            cam.allowHDR = false; cam.allowMSAA = true;
            go.transform.position = pos; go.transform.LookAt(tgt, Vector3.up);
            return cam;
        }

        static void Capture(Camera camera, int w, int h, string path)
        {
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
            var res = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rt.Create(); res.Create();
            camera.aspect = (float)w / h;
            camera.targetTexture = rt;
            camera.Render();
            Graphics.Blit(rt, res);
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false, false);
            RenderTexture.active = res;
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = null;
            File.WriteAllBytes(path, tex.EncodeToPNG());
            camera.targetTexture = null;
            UnityEngine.Object.DestroyImmediate(tex); rt.Release(); res.Release();
            UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(res);
        }

        public static void Render()
        {
            var a = Environment.GetCommandLineArgs();
            var seqs = (Arg(a, "-f37Seqs") ?? string.Join(",", Seqs)).Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            float fps = float.Parse(Arg(a, "-f37Fps") ?? "24", CultureInfo.InvariantCulture);
            int W = int.Parse(Arg(a, "-f37W") ?? "960"), H = int.Parse(Arg(a, "-f37H") ?? "540");
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var camRoot = GameObject.Find("F37 Cameras").transform;
            var cams = new Dictionary<string, Camera> { { "painting", camRoot.Find("F37 painting").GetComponent<Camera>() }, { "seat", camRoot.Find("F37 seat").GetComponent<Camera>() } };
            var players = Resources.FindObjectsOfTypeAll<F37SeqPlayer>().Where(p => p.gameObject.scene.IsValid()).ToList();
            var log = new StringBuilder();
            log.Append("{\n \"unity\": \"" + Application.unityVersion + "\",\n \"fps\": " + fps.ToString(CultureInfo.InvariantCulture) + ",\n \"size\": [" + W + "," + H + "],\n \"runs\": [\n");
            bool firstRun = true;
            foreach (var seq in seqs)
            {
                var mine = players.Where(p => p.transform.parent != null && p.transform.parent.name == "F37 " + seq).ToList();
                var sheet = mine.First(p => p.gameObject.name == "sheet");
                var frames = mine.First(p => p.gameObject.name == "frames");
                var sea = mine.First(p => p.gameObject.name == "frames_sea");
                foreach (var p in players) p.gameObject.SetActive(false);
                foreach (var p in new[] { sheet, frames, sea }) { p.gameObject.SetActive(true); p.Load(); p.gameObject.SetActive(false); }
                float t0 = sheet.T0, t1 = sheet.T1;
                int nOut = Mathf.FloorToInt((t1 - t0) * fps + 1e-3f) + 1;
                var kpGo = GameObject.Find("F37 Players").transform.Find("F37 " + seq + "/keypose");
                DS30SheetPlayer kp = null; double tstarKp = double.NaN;
                if (kpGo != null && File.Exists(Prep + "/keypose/" + seq + "/ds27_keypose.json"))
                {
                    kpGo.gameObject.SetActive(true);
                    kp = kpGo.GetComponent<DS30SheetPlayer>();
                    kp.EnsureLoaded();
                    kpGo.GetComponent<PL29UkiyoeHero>().Apply();
                    var kj = File.ReadAllText(Prep + "/keypose/" + seq + "/ds27_keypose.json");
                    int ix = kj.IndexOf("\"t_star_s\":", StringComparison.Ordinal);
                    tstarKp = double.Parse(kj.Substring(ix + 11).Split(',', '}')[0].Trim(), CultureInfo.InvariantCulture);
                    kpGo.gameObject.SetActive(false);
                }
                foreach (var method in new[] { "sheet", "frames", "keypose" })
                {
                    if (method == "keypose" && kp == null) continue;
                    var active = method == "sheet" ? new[] { sheet, sea } : method == "frames" ? new[] { frames } : new[] { sea };
                    foreach (var p in new[] { sheet, frames, sea }) p.gameObject.SetActive(active.Contains(p));
                    if (kp != null) kp.gameObject.SetActive(method == "keypose");
                    var sw = System.Diagnostics.Stopwatch.StartNew();
                    double setMs = 0, setMax = 0;
                    int verts = 0;
                    foreach (var cn in cams.Keys) Directory.CreateDirectory(Prep + "/unity_render/" + seq + "/" + method + "_" + cn);
                    int done = 0;
                    for (int i = 0; i < nOut; i++)
                    {
                        float t = t0 + i / fps;
                        if (method == "keypose" && t > tstarKp + 1e-4) break;
                        foreach (var p in active) { p.SetTime(t); setMs += p.LastSetMs; setMax = Math.Max(setMax, p.LastSetMs); }
                        if (method == "keypose") kp.ApplyTau(t - tstarKp);
                        verts = Math.Max(verts, active[0].LastVertices);
                        foreach (var kv in cams) Capture(kv.Value, W, H, Prep + "/unity_render/" + seq + "/" + method + "_" + kv.Key + "/f_" + i.ToString("0000") + ".png");
                        done++;
                    }
                    if (!firstRun) log.Append(",\n");
                    firstRun = false;
                    log.Append(string.Format(CultureInfo.InvariantCulture,
                        "  {{\"seq\": \"{0}\", \"method\": \"{1}\", \"t0\": {2}, \"t1\": {3}, \"frames_out\": {4}, \"wall_s\": {5:F1}, \"set_ms_mean\": {6:F2}, \"set_ms_max\": {7:F2}, \"hero_vertices_max\": {8}}}",
                        seq, method, t0, t1, done, sw.Elapsed.TotalSeconds, setMs / Math.Max(done, 1), setMax, verts));
                    Debug.Log("F37_RENDER " + seq + " " + method + " frames " + done + " " + sw.Elapsed.TotalSeconds.ToString("F1") + "s");
                }
                foreach (var p in new[] { sheet, frames, sea }) p.gameObject.SetActive(false);
                if (kp != null) { kp.gameObject.SetActive(false); }
            }
            log.Append("\n ],\n \"note_ja\": \"F37Proto.unity（独立の試作の場面）を開き、方法 A（sheet＋周りの海は frames から主役波の範囲を除いた網目）と方法 B（frames）を原画カメラと座席から描いた。set_ms はコマの網目を作る CPU の時間（補間・読み込みを含む、エディターの batchmode）。\"\n}\n");
            File.WriteAllText(Prep + "/unity_render/render_log.json", log.ToString(), new UTF8Encoding(false));
            Debug.Log("F37_RENDER_DONE");
        }
    }
}
