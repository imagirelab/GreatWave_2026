using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design30;
using GreatWave.Design38;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Polish30.EditorTools
{
    // 仕上げ30 の組み立て：
    //  EnsureMaterial：PL30 Ukiyoe Sea Keypose の材質 PL30_Ukiyoe_Sea.mat を作る（無ければ）。限定色は仕上げ29 の主役波の材質 PL29_Ukiyoe_Hero.mat から写す
    //    （主役波と海の藍濃の 1 段の差をなくす）。-pl30SeaParamFile があれば、その値（名前=値）を材質のファイルへ書く。
    //  BuildScenes：仕上げ29 の場面 PL29_Release.unity・PL29_SinglePlayback.unity を Polish30/Scenes へ写し（元の場面は読むだけ）、写しの周りの海を
    //    仕上げ30 のパッケージ（-pl30Sea、既定 Build/Polish/30/sea）と材質（PL30UkiyoeSea・面の座標）へ替え、座席の船の上下を同じフォルダーの boat_support.json に、
    //    T 字の幕（DS30SeamCurtain）を切り（far の行 0 は near の全部の列）、遠い海に外殻線（near の線の材質の写し、PL30_Outline_far.mat）を付け、
    //    仮置き M1_Revision_LeftSupport を隠す。設計36 の DS36SeaPalette は切る（t* の高さの段を使わない）。主役波・爪・飛沫・線の印は仕上げ29 のまま。
    public static class PL30Setup
    {
        public const string SeaMat = "Assets/GreatWave/Polish30/Materials/PL30_Ukiyoe_Sea.mat";
        public const string FarLineMat = "Assets/GreatWave/Polish30/Materials/PL30_Outline_far.mat";
        const string HeroMat = "Assets/GreatWave/Polish29/Materials/PL29_Ukiyoe_Hero.mat";
        const string ShaderName = "GreatWave/Polish30/PL30 Ukiyoe Sea Keypose";
        public const string SceneRelease29 = "Assets/GreatWave/Polish29/Scenes/PL29_Release.unity";
        public const string SceneSingle29 = "Assets/GreatWave/Polish29/Scenes/PL29_SinglePlayback.unity";
        public const string SceneRelease = "Assets/GreatWave/Polish30/Scenes/PL30_Release.unity";
        public const string SceneSingle = "Assets/GreatWave/Polish30/Scenes/PL30_SinglePlayback.unity";

        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        static string Sha(string path)
        {
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        static void WriteParams(Material m, string pf)
        {
            foreach (var raw in File.ReadAllLines(pf, Encoding.UTF8))
            {
                var line = raw.Split('#')[0].Trim();
                if (line.Length == 0) continue;
                int k = line.IndexOf('=');
                string name = line.Substring(0, k).Trim(), val = line.Substring(k + 1).Trim();
                var parts = val.Split(',').Select(x => float.Parse(x.Trim(), CultureInfo.InvariantCulture)).ToArray();
                if (!m.HasProperty(name)) throw new ArgumentException("材質にない値: " + name);
                if (parts.Length == 1) m.SetFloat(name, parts[0]);
                else
                {
                    var v = new Vector4(parts[0], parts.Length > 1 ? parts[1] : 0, parts.Length > 2 ? parts[2] : 0, parts.Length > 3 ? parts[3] : 1);
                    if (name.StartsWith("_White") || name.StartsWith("_Mizuiro") || name.StartsWith("_Ai") || name.StartsWith("_LineCol")) m.SetColor(name, v);
                    else m.SetVector(name, v);
                }
            }
            EditorUtility.SetDirty(m);
        }

        public static void EnsureMaterial()
        {
            var sh = Shader.Find(ShaderName);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + ShaderName);
            var m = AssetDatabase.LoadAssetAtPath<Material>(SeaMat);
            if (m == null)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(SeaMat));
                m = new Material(sh) { name = "PL30_Ukiyoe_Sea" };
                AssetDatabase.CreateAsset(m, SeaMat);
            }
            var hero = AssetDatabase.LoadAssetAtPath<Material>(HeroMat);
            if (hero != null) foreach (var p in new[] { "_White", "_Mizuiro", "_AiMid", "_AiDark", "_LineCol" }) if (hero.HasProperty(p)) m.SetColor(p, hero.GetColor(p));
            var pf = Arg("-pl30SeaParamFile");
            if (!string.IsNullOrEmpty(pf)) WriteParams(m, pf);
            EditorUtility.SetDirty(m);
            AssetDatabase.SaveAssets();
            Debug.Log("PL30_SETUP_MATERIAL " + SeaMat + " sha256=" + Sha(SeaMat));
        }

        [Serializable] class SceneRec { public string from, fromSha256Before, fromSha256After, to, toSha256; public string[] changesJa; }
        [Serializable] class Report { public string utc, unity, material, materialSha256, sea; public string[] attrSha256; public SceneRec[] scenes; }

        public static void BuildScenes()
        {
            EnsureMaterial();
            var mat = AssetDatabase.LoadAssetAtPath<Material>(SeaMat);
            var heroMat = AssetDatabase.LoadAssetAtPath<Material>(HeroMat);
            string sea = Arg("-pl30Sea") ?? "Build/Polish/30/sea";
            var recs = new List<SceneRec>();
            var shas = new List<string>();
            foreach (var nm in new[] { "near", "far" }) shas.Add(nm + " " + Sha(Path.GetFullPath(Path.Combine(sea, nm, "pl30_sea_attr_f32.bin"))));
            foreach (var (from, to) in new[] { (SceneRelease29, SceneRelease), (SceneSingle29, SceneSingle) })
            {
                var r = new SceneRec { from = from, fromSha256Before = Sha(from), to = to };
                var ch = new List<string>();
                Directory.CreateDirectory(Path.GetDirectoryName(to));
                if (File.Exists(to)) AssetDatabase.DeleteAsset(to);
                if (!AssetDatabase.CopyAsset(from, to)) throw new InvalidOperationException("場面を写せません: " + from);
                var scene = EditorSceneManager.OpenScene(to, OpenSceneMode.Single);
                var roots = scene.GetRootGameObjects();
                var play = roots.SelectMany(g => g.GetComponentsInChildren<DS30SinglePlayback>(true)).Single();
                var near = play.sheets.First(s => s != null && s.sheetName == "near");
                var far = play.sheets.First(s => s != null && s.sheetName == "far");
                foreach (var s in new[] { near, far })
                {
                    ch.Add(s.sheetName + " packageDir " + s.packageDir + " → " + sea + "/" + s.sheetName + "、色区の表・UV3（設計36）を外し、材質を PL30_Ukiyoe_Sea");
                    s.packageDir = sea + "/" + s.sheetName; s.meshGwb = ""; s.sdfPath = ""; s.uv3File = ""; s.warpPath = ""; s.whiteAboveTStarY = float.NaN;
                    s.Surface.sharedMaterial = mat;
                    EditorUtility.SetDirty(s); EditorUtility.SetDirty(s.Surface);
                }
                var uk = play.GetComponent<PL30UkiyoeSea>(); if (uk == null) uk = play.gameObject.AddComponent<PL30UkiyoeSea>();
                uk.material = mat; uk.heroMaterial = heroMat;
                uk.sheets = new List<PL30UkiyoeSea.Entry> {
                    new PL30UkiyoeSea.Entry { sheet = near, attrPath = sea + "/near/pl30_sea_attr_f32.bin", attrSha256 = shas[0].Split(' ')[1] },
                    new PL30UkiyoeSea.Entry { sheet = far, attrPath = sea + "/far/pl30_sea_attr_f32.bin", attrSha256 = shas[1].Split(' ')[1] } };
                EditorUtility.SetDirty(uk);
                ch.Add("PL30UkiyoeSea を付けた（" + string.Join("、", shas) + "）");
                foreach (var sp in roots.SelectMany(g => g.GetComponentsInChildren<GreatWave.Design36.DS36SeaPalette>(true)))
                {
                    // Awake は切った部品でも呼ばれる（Configure が設計36 の段の表を戻す）ので、再生器への参照も外す（SeaSheets が空になる）
                    sp.enabled = false; sp.playback = null; EditorUtility.SetDirty(sp);
                    ch.Add("設計36 の DS36SeaPalette（t* の高さの段）を切り、再生器への参照を外した：" + sp.gameObject.name);
                }
                foreach (var h in play.heaves.Where(h => h != null))
                {
                    ch.Add("座席の船の上下 " + h.supportPath + " → " + sea + "/boat_support.json");
                    h.supportPath = sea + "/boat_support.json"; EditorUtility.SetDirty(h);
                }
                foreach (var cu in play.curtains.Where(x => x != null))
                {
                    cu.gameObject.SetActive(false); EditorUtility.SetDirty(cu.gameObject);
                    ch.Add("T 字の幕を切った：" + cu.gameObject.name + "（far の行 0 は near の外周の全部の列）");
                }
                var nl = near.GetComponent<DS38SheetOutline>();
                if (nl != null && nl.lineMaterial != null && far.GetComponent<DS38SheetOutline>() == null)
                {
                    var fm = AssetDatabase.LoadAssetAtPath<Material>(FarLineMat);
                    if (fm == null) { fm = new Material(nl.lineMaterial) { name = "PL30_Outline_far" }; AssetDatabase.CreateAsset(fm, FarLineMat); }
                    var fl = far.gameObject.AddComponent<DS38SheetOutline>();
                    fl.sheet = far; fl.lineMaterial = fm; fl.sheetId = 3; fl.maskPath = "";
                    fl.Attach();
                    EditorUtility.SetDirty(fl);
                    ch.Add("遠い海に外殻線（DS38SheetOutline、PL30_Outline_far.mat＝near の線の材質の写し）を付けた");
                }
                Transform ctxRoot = null;
                foreach (var t in roots.SelectMany(g => g.GetComponentsInChildren<Transform>(true)).Where(t => t.name == "M1_Revision_LeftSupport").ToList())
                {
                    t.gameObject.SetActive(false); EditorUtility.SetDirty(t.gameObject);
                    ch.Add("仮置き M1_Revision_LeftSupport を隠した（座席の視点で画面の幅の約 40% を占めた平らな板）");
                    ctxRoot = t.root;
                }
                var boatLeft = roots.SelectMany(g => g.GetComponentsInChildren<Transform>(true)).FirstOrDefault(t => t.name == "AF27 船 boat_left");
                string lsp = Arg("-pl30LeftSwell") ?? "Build/Polish/30/left_swell/pl30_left_swell.json";
                if (ctxRoot != null && File.Exists(Path.GetFullPath(lsp)))
                {
                    var go = new GameObject("PL30 左奥の船のうねり");
                    go.transform.SetParent(ctxRoot, false);
                    go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                    var ls = go.AddComponent<PL30LeftSwell>();
                    ls.playback = play; ls.boat = boatLeft; ls.dataPath = lsp; ls.material = mat;
                    EditorUtility.SetDirty(go);
                    ch.Add("左奥の船のうねり（PL30LeftSwell、" + lsp + "、SHA-256 " + Sha(Path.GetFullPath(lsp)) + "）を置いた。船 " + (boatLeft != null ? boatLeft.name : "なし"));
                }
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                r.changesJa = ch.ToArray(); r.toSha256 = Sha(to); r.fromSha256After = Sha(from);
                recs.Add(r);
            }
            AssetDatabase.SaveAssets();
            var rep = new Report { utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, material = SeaMat, materialSha256 = Sha(SeaMat), sea = sea, attrSha256 = shas.ToArray(), scenes = recs.ToArray() };
            var od = Arg("-pl30Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "pl30_setup.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL30_SETUP_DONE " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)));
        }
    }
}
