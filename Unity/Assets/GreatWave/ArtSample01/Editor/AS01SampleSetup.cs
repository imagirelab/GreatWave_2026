using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design34;
using GreatWave.Polish29;
using GreatWave.Polish30;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.ArtSample01.EditorTools
{
    // 美術の見本01（Q29）組み立て：見本 A・B の場面の写しを作る（仕上げ36 の PL36Setup・仕上げ33修正01 の PL33R01Setup の形を写した）。
    //   元：仕上げ35 の場面 PL35_Release.unity・PL35_SinglePlayback.unity（今の採用の状態。読むだけで変えない）。
    //   先：Assets/GreatWave/ArtSample01/Scenes/AS01_Sample{A,B}_{Release,SinglePlayback}.unity（4 つ）。
    //   写しの中で替えるもの（描画の道具 AS01SampleRender が引数で行うことと同じ）：
    //     主役波の材質 → ArtSample01/Materials/AS01_Sample{A,B}_Hero.mat（シェーダー S01A Groove Keypose／S01B Tongue Keypose の既定の値に、
    //       値の表 s01a_material_params.txt／s01b_material_params.txt を書いたもの。描画の道具と同じ作り方）。PL29UkiyoeHero.material、
    //       仕上げ29 の材質を使うレンダラー、海が限定色を写す元（PL30UkiyoeSea.heroMaterial）。
    //     主役波の面の座標（PL29UkiyoeHero.attrPath・attrSha256）→ 見本 A は属性 v2、見本 B は s01b_attr_f32.bin。
    //     見本 B だけ：主役波に AS01DesignTexture（設計のテクスチャを大域へ渡す）を足す。
    //     爪（DS34ClawPlayer.layoutPath）→ 爪の部の爪 Build/Polish/sample01/claws/mesh（t* の 1 コマの静止の見本。ほかの時刻でも t* の形のまま）。
    //   海・飛沫・線・船・体験の流れ・計測器は替えない。データ（属性・設計・爪）は Git 対象外の Build/Polish/sample01 の下を指す（Editor で見るための場面）。
    //   改善の回 2（2026-10-03）：見本 A2・B2 の状態へ。値の表は回 1 の s01a_material_params_r1.txt・s01b_material_params_r1.txt、見本 B の設計は design_r2（点を戻した d2）、
    //     爪は claws/mesh_r2（v15）。爪の陰の材質を見本の写し ArtSample01/Materials/AS01_Claw_Shade.mat（PL29_Claw_Shade.mat ＋ as01_claw_params.txt の水色）にし、
    //     爪の層に AS01ClawLook（泡の鱗 U… の縁の線なし、縁の線の色を藍 31,60,94）を足す（描画の道具の -pl29ClawParamFile・-as01ClawLineColor・-as01NoLinePrefix と同じ）。
    // 実行：Tools/GWWaveGen/as01/as01s_run_unity_steps.sh setup
    public static class AS01SampleSetup
    {
        public const string SceneRelease35 = "Assets/GreatWave/Polish35/Scenes/PL35_Release.unity";
        public const string SceneSingle35 = "Assets/GreatWave/Polish35/Scenes/PL35_SinglePlayback.unity";
        public const string MatPath29 = "Assets/GreatWave/Polish29/Materials/PL29_Ukiyoe_Hero.mat";
        public const string SeaMat30 = "Assets/GreatWave/Polish30/Materials/PL30_Ukiyoe_Sea.mat";
        public const string Dir = "Assets/GreatWave/ArtSample01";
        public const string DefaultClaws = "Build/Polish/sample01/claws/mesh_r2/ds33_claw_layout.json";
        public const string ClawMat29 = "Assets/GreatWave/Polish29/Materials/PL29_Claw_Shade.mat";
        public const string ClawParams = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as01/as01_claw_params.txt";
        const string Tools = "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01/";

        class Sample
        {
            public string name, shader, paramFile, attr, designDir;
        }

        static readonly Sample[] Samples =
        {
            new Sample { name = "A", shader = "GreatWave/Sample01/S01A Groove Keypose", paramFile = Tools + "s01a_material_params_r1.txt",
                         attr = "Build/Polish/sample01/texA/attr/s01a_hero_attr_v2_f32.bin" },
            new Sample { name = "B", shader = "GreatWave/Sample01/S01B Tongue Keypose", paramFile = Tools + "s01b_material_params_r1.txt",
                         attr = "Build/Polish/sample01/texB/work/design_r2/s01b_attr_f32.bin", designDir = "Build/Polish/sample01/texB/work/design_r2" },
        };

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

        [Serializable] class ParamRec { public string name, value; }
        [Serializable] class MatRec { public string sample, material, materialSha256, shader, paramFile, paramFileSha256; public ParamRec[] values; }
        [Serializable] class SceneRec { public string sample, from, fromSha256Before, fromSha256After, to, toSha256; public string[] changesJa; }
        [Serializable] class Report { public string utc, unity, clawLayout, clawLayoutSha256; public MatRec[] materials; public SceneRec[] scenes; }

        // 描画の道具（S01ARender・S01BRender・AS01SampleRender）の ApplyParams と同じ読み方
        static List<ParamRec> ApplyParams(Material m, string file)
        {
            var recs = new List<ParamRec>();
            foreach (var raw in File.ReadAllLines(file, Encoding.UTF8))
            {
                var line = raw.Split('#')[0].Trim();
                if (line.Length == 0) continue;
                int k = line.IndexOf('=');
                if (k <= 0) throw new FormatException("材質の値の行: " + raw);
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
                recs.Add(new ParamRec { name = name, value = val });
            }
            return recs;
        }

        static Material EnsureMaterial(Sample s, List<MatRec> recs)
        {
            var sh = Shader.Find(s.shader);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + s.shader);
            string path = Dir + "/Materials/AS01_Sample" + s.name + "_Hero.mat";
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            if (File.Exists(path)) AssetDatabase.DeleteAsset(path);
            var m = new Material(sh) { name = "AS01_Sample" + s.name + "_Hero" };
            var vals = ApplyParams(m, s.paramFile);
            AssetDatabase.CreateAsset(m, path);
            AssetDatabase.SaveAssets();
            recs.Add(new MatRec { sample = s.name, material = path, materialSha256 = Sha(path), shader = s.shader, paramFile = s.paramFile, paramFileSha256 = Sha(s.paramFile), values = vals.ToArray() });
            return m;
        }

        public static void BuildScenes()
        {
            string clawLayout = Arg("-as01Claws") ?? DefaultClaws;
            if (!File.Exists(Path.GetFullPath(clawLayout))) throw new InvalidOperationException("爪の並びがありません: " + clawLayout);
            var m29 = AssetDatabase.LoadAssetAtPath<Material>(MatPath29);
            if (m29 == null) throw new InvalidOperationException("仕上げ29 の材質がありません: " + MatPath29);
            var sea0 = AssetDatabase.LoadAssetAtPath<Material>(SeaMat30);
            if (sea0 == null) throw new InvalidOperationException("仕上げ30 の海の材質がありません: " + SeaMat30);
            string sea0Sha = Sha(SeaMat30);
            var mats = new List<MatRec>();
            // 爪の陰の材質の写し（仕上げ29 の PL29_Claw_Shade.mat ＋ as01_claw_params.txt）
            var cm29 = AssetDatabase.LoadAssetAtPath<Material>(ClawMat29);
            if (cm29 == null) throw new InvalidOperationException("仕上げ29 の爪の材質がありません: " + ClawMat29);
            string clawMatPath = Dir + "/Materials/AS01_Claw_Shade.mat";
            if (File.Exists(clawMatPath)) AssetDatabase.DeleteAsset(clawMatPath);
            var clawMat = new Material(cm29) { name = "AS01_Claw_Shade" };
            var clawVals = ApplyParams(clawMat, ClawParams);
            AssetDatabase.CreateAsset(clawMat, clawMatPath);
            AssetDatabase.SaveAssets();
            mats.Add(new MatRec { sample = "AB", material = clawMatPath, materialSha256 = Sha(clawMatPath), shader = clawMat.shader.name, paramFile = ClawParams, paramFileSha256 = Sha(ClawParams), values = clawVals.ToArray() });
            var recs = new List<SceneRec>();
            foreach (var s in Samples)
            {
                var mat = EnsureMaterial(s, mats);
                string seaPath = Dir + "/Materials/AS01_Sample" + s.name + "_Sea.mat";
                if (File.Exists(seaPath)) AssetDatabase.DeleteAsset(seaPath);
                if (!AssetDatabase.CopyAsset(SeaMat30, seaPath)) throw new InvalidOperationException("海の材質を写せません: " + SeaMat30);
                var seaMat = AssetDatabase.LoadAssetAtPath<Material>(seaPath);
                mats.Add(new MatRec { sample = s.name, material = seaPath, materialSha256 = Sha(seaPath), shader = seaMat.shader.name, paramFile = SeaMat30 + "（写し）", paramFileSha256 = Sha(SeaMat30), values = new ParamRec[0] });
                string attrSha = Sha(Path.GetFullPath(s.attr));
                if (attrSha == "") throw new InvalidOperationException("面の座標がありません: " + s.attr);
                foreach (var (from, kind) in new[] { (SceneRelease35, "Release"), (SceneSingle35, "SinglePlayback") })
                {
                    string to = Dir + "/Scenes/AS01_Sample" + s.name + "_" + kind + ".unity";
                    var r = new SceneRec { sample = s.name, from = from, fromSha256Before = Sha(from), to = to };
                    var ch = new List<string>();
                    Directory.CreateDirectory(Path.GetDirectoryName(to));
                    AssetDatabase.Refresh();
                    if (File.Exists(to)) AssetDatabase.DeleteAsset(to);
                    if (!AssetDatabase.CopyAsset(from, to)) throw new InvalidOperationException("場面を写せません: " + from);
                    var scene = EditorSceneManager.OpenScene(to, OpenSceneMode.Single);
                    var roots = scene.GetRootGameObjects();
                    int nUk = 0, nRend = 0, nSea = 0, nDes = 0, nSeaMat = 0, nSeaRend = 0;
                    foreach (var uk in roots.SelectMany(g => g.GetComponentsInChildren<PL29UkiyoeHero>(true)))
                    {
                        uk.material = mat; uk.attrPath = s.attr; uk.attrSha256 = attrSha; EditorUtility.SetDirty(uk); nUk++;
                        if (!string.IsNullOrEmpty(s.designDir))
                        {
                            var dt = uk.gameObject.GetComponent<AS01DesignTexture>() ?? uk.gameObject.AddComponent<AS01DesignTexture>();
                            dt.designDir = s.designDir; dt.designSha256 = Sha(Path.Combine(Path.GetFullPath(s.designDir), "s01b_design_f16.bin"));
                            EditorUtility.SetDirty(dt); nDes++;
                        }
                    }
                    foreach (var sea in roots.SelectMany(g => g.GetComponentsInChildren<PL30UkiyoeSea>(true)))
                    {
                        if (sea.heroMaterial == m29) { sea.heroMaterial = mat; EditorUtility.SetDirty(sea); nSea++; }
                        // PL30UkiyoeSea は Play の時に主役波の限定色を海の材質のファイルへ写す（Configure）。採用の PL30_Ukiyoe_Sea.mat を書き換えないよう、
                        // 見本ごとの写し AS01_Sample{A,B}_Sea.mat を海に付ける（2026-10-03 の初回の Play の確かめで PL30_Ukiyoe_Sea.mat の色が 1e-5 の桁で書き換わったので足した）
                        if (sea.material == sea0) { sea.material = seaMat; EditorUtility.SetDirty(sea); nSeaMat++; }
                    }
                    foreach (var rr in roots.SelectMany(g => g.GetComponentsInChildren<Renderer>(true)))
                    {
                        var ms = rr.sharedMaterials;
                        bool any = false;
                        for (int i = 0; i < ms.Length; i++)
                        {
                            if (ms[i] == m29) { ms[i] = mat; any = true; }
                            else if (ms[i] == sea0) { ms[i] = seaMat; any = true; nSeaRend++; }
                        }
                        if (any) { rr.sharedMaterials = ms; EditorUtility.SetDirty(rr); nRend++; }
                    }
                    ch.Add("海の材質を見本ごとの写し " + AssetDatabase.GetAssetPath(seaMat) + " にした（PL30UkiyoeSea " + nSeaMat + "、レンダラーの枠 " + nSeaRend + "。採用の材質のファイルを Play で書き換えないため）");
                    if (nUk == 0) throw new InvalidOperationException("場面に PL29UkiyoeHero がない: " + to);
                    ch.Add("主役波の材質を " + AssetDatabase.GetAssetPath(mat) + " に、面の座標を " + s.attr + " にした（PL29UkiyoeHero " + nUk + "、レンダラー " + nRend + "、PL30UkiyoeSea の限定色の元 " + nSea + "）");
                    if (nDes > 0) ch.Add("主役波に AS01DesignTexture（" + s.designDir + "）を足した（" + nDes + "）");
                    var claws = roots.SelectMany(g => g.GetComponentsInChildren<DS34ClawPlayer>(true)).ToList();
                    if (claws.Count == 0) ch.Add("爪の層はない");
                    foreach (var cp in claws)
                    {
                        ch.Add("爪 " + cp.gameObject.name + " の layoutPath " + cp.layoutPath + " → " + clawLayout + "（美術の見本01 の爪。t* の 1 コマの静止の見本）");
                        cp.layoutPath = clawLayout; EditorUtility.SetDirty(cp);
                        int nShade = 0;
                        foreach (var sh in roots.SelectMany(g => g.GetComponentsInChildren<PL29ClawShade>(true)))
                            if (sh.material == cm29 || sh.Claws == cp) { sh.material = clawMat; EditorUtility.SetDirty(sh); nShade++; }
                        var ol = cp.GetComponent<GreatWave.Design38.DS38ClawOutline>() ?? roots.SelectMany(g => g.GetComponentsInChildren<GreatWave.Design38.DS38ClawOutline>(true)).FirstOrDefault(o => o.claws == cp);
                        var al = cp.GetComponent<AS01ClawLook>() ?? cp.gameObject.AddComponent<AS01ClawLook>();
                        al.claws = cp; al.outline = ol; al.noLinePrefix = "U"; al.setLineColor = true; al.lineColor = new Color(31f / 255f, 60f / 255f, 94f / 255f, 1f);
                        EditorUtility.SetDirty(al);
                        ch.Add("爪の陰の材質を " + clawMatPath + " にした（PL29ClawShade " + nShade + "）。AS01ClawLook（泡の鱗 U… の縁の線なし、縁の線の色 31,60,94、DS38ClawOutline " + (ol != null ? "あり" : "なし") + "）を足した");
                    }
                    EditorSceneManager.MarkSceneDirty(scene);
                    EditorSceneManager.SaveScene(scene);
                    r.changesJa = ch.ToArray(); r.toSha256 = Sha(to); r.fromSha256After = Sha(from);
                    recs.Add(r);
                }
            }
            AssetDatabase.SaveAssets();
            var rep = new Report
            {
                utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, clawLayout = clawLayout, clawLayoutSha256 = Sha(Path.GetFullPath(clawLayout)),
                materials = mats.ToArray(), scenes = recs.ToArray()
            };
            var od = Arg("-as01Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/assemble/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "as01s_setup.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("AS01S_SETUP_DONE " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)) + " unchanged35=" + recs.All(x => x.fromSha256Before == x.fromSha256After) + " sea30Unchanged=" + (Sha(SeaMat30) == sea0Sha));
        }
    }
}
