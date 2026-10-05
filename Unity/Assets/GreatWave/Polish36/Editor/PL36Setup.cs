using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Polish29;
using GreatWave.Polish30;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Polish36.EditorTools
{
    // 仕上げ36（設計36 限定色）の組み立て。仕上げ35 までの場面・材質・シェーダーのファイルは変えない（読むだけ）。
    //  EnsureMaterial：PL36 Ukiyoe Keypose（Polish36/Shaders/PL36_Ukiyoe_Hero.shader）の材質 PL36_Ukiyoe_Hero.mat を作る（無ければ）。
    //    値は仕上げ29 の PL29_Ukiyoe_Hero.mat から同じ名前の値を写し、-pl36ParamFile（名前=値の行）があれば、その値を材質のファイルへ書く（決めた数値を材質に残す）。
    //  BuildScenes：仕上げ35 の場面 PL35_Release.unity・PL35_SinglePlayback.unity を Polish36/Scenes へ写し（元の場面は読むだけ）、
    //    写しの主役波の材質（PL29UkiyoeHero.material と面のレンダラー）と、海が限定色を写す元（PL30UkiyoeSea.heroMaterial）を PL36_Ukiyoe_Hero.mat にする。
    //    爪・飛沫・海・線・計測器（PL35PerfProbe）・爪の縁の線の写しの部品（PL35ClawOutlineFast）は替えない。
    public static class PL36Setup
    {
        public const string MatPath = "Assets/GreatWave/Polish36/Materials/PL36_Ukiyoe_Hero.mat";
        public const string MatPath29 = "Assets/GreatWave/Polish29/Materials/PL29_Ukiyoe_Hero.mat";
        public const string ShaderName = "GreatWave/Polish36/PL36 Ukiyoe Keypose";
        public const string SceneRelease35 = "Assets/GreatWave/Polish35/Scenes/PL35_Release.unity";
        public const string SceneSingle35 = "Assets/GreatWave/Polish35/Scenes/PL35_SinglePlayback.unity";
        public const string SceneRelease = "Assets/GreatWave/Polish36/Scenes/PL36_Release.unity";
        public const string SceneSingle = "Assets/GreatWave/Polish36/Scenes/PL36_SinglePlayback.unity";

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
        [Serializable] class MatReport { public string utc, unity, material, materialSha256, shader, from29, from29Sha256, paramFile, paramFileSha256; public ParamRec[] values; public string[] removedJa; }

        public static void EnsureMaterial()
        {
            var sh = Shader.Find(ShaderName);
            if (sh == null) throw new InvalidOperationException("シェーダーがありません: " + ShaderName);
            var m29 = AssetDatabase.LoadAssetAtPath<Material>(MatPath29);
            if (m29 == null) throw new InvalidOperationException("仕上げ29 の材質がありません: " + MatPath29);
            var m = AssetDatabase.LoadAssetAtPath<Material>(MatPath);
            if (m == null)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(MatPath));
                m = new Material(sh) { name = "PL36_Ukiyoe_Hero" };
                AssetDatabase.CreateAsset(m, MatPath);
            }
            if (m.shader != sh) m.shader = sh;
            // 仕上げ29 の材質の値（同じ名前）を写す。仕上げ36 で足した値はシェーダーの既定のまま（帯なし＝仕上げ29 と同じ見え方）
            int nProps = sh.GetPropertyCount();
            for (int i = 0; i < nProps; i++)
            {
                string pn = sh.GetPropertyName(i);
                if (!m29.HasProperty(pn)) continue;
                switch (sh.GetPropertyType(i))
                {
                    case UnityEngine.Rendering.ShaderPropertyType.Color: m.SetColor(pn, m29.GetColor(pn)); break;
                    case UnityEngine.Rendering.ShaderPropertyType.Vector: m.SetVector(pn, m29.GetVector(pn)); break;
                    case UnityEngine.Rendering.ShaderPropertyType.Float:
                    case UnityEngine.Rendering.ShaderPropertyType.Range: m.SetFloat(pn, m29.GetFloat(pn)); break;
                }
            }
            var recs = new List<ParamRec>();
            var pf = Arg("-pl36ParamFile");
            if (!string.IsNullOrEmpty(pf))
            {
                foreach (var raw in File.ReadAllLines(pf, Encoding.UTF8))
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
            }
            // シェーダーにない古い値を材質のファイルから消す
            var removed = new List<string>();
            var so = new SerializedObject(m);
            foreach (var listName in new[] { "m_SavedProperties.m_Floats", "m_SavedProperties.m_Colors", "m_SavedProperties.m_TexEnvs" })
            {
                var arr = so.FindProperty(listName);
                if (arr == null) continue;
                for (int i = arr.arraySize - 1; i >= 0; i--)
                {
                    var nm = arr.GetArrayElementAtIndex(i).FindPropertyRelative("first").stringValue;
                    bool known = false;
                    for (int j = 0; j < nProps; j++) if (sh.GetPropertyName(j) == nm) { known = true; break; }
                    if (!known) { arr.DeleteArrayElementAtIndex(i); removed.Add(nm); }
                }
            }
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(m);
            AssetDatabase.SaveAssets();
            var rep = new MatReport
            {
                utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, material = MatPath, materialSha256 = Sha(MatPath), shader = ShaderName,
                from29 = MatPath29, from29Sha256 = Sha(MatPath29), paramFile = pf ?? "", paramFileSha256 = Sha(pf), values = recs.ToArray(), removedJa = removed.ToArray()
            };
            var od = Arg("-pl36Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/36/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "pl36_material.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL36_MATERIAL_DONE " + MatPath + " sha256=" + rep.materialSha256 + " values=" + recs.Count + " removed=" + removed.Count);
        }

        [Serializable] class SceneRec { public string from, fromSha256Before, fromSha256After, to, toSha256; public string[] changesJa; }
        [Serializable] class SceneReport { public string utc, unity, material, materialSha256; public SceneRec[] scenes; }

        public static void BuildScenes()
        {
            var mat = AssetDatabase.LoadAssetAtPath<Material>(MatPath);
            if (mat == null) throw new InvalidOperationException("材質がありません（EnsureMaterial を先に）: " + MatPath);
            var m29 = AssetDatabase.LoadAssetAtPath<Material>(MatPath29);
            var recs = new List<SceneRec>();
            foreach (var (from, to) in new[] { (SceneRelease35, SceneRelease), (SceneSingle35, SceneSingle) })
            {
                var r = new SceneRec { from = from, fromSha256Before = Sha(from), to = to };
                var ch = new List<string>();
                Directory.CreateDirectory(Path.GetDirectoryName(to));
                AssetDatabase.Refresh();
                if (File.Exists(to)) AssetDatabase.DeleteAsset(to);
                if (!AssetDatabase.CopyAsset(from, to)) throw new InvalidOperationException("場面を写せません: " + from);
                var scene = EditorSceneManager.OpenScene(to, OpenSceneMode.Single);
                var roots = scene.GetRootGameObjects();
                int nUk = 0, nRend = 0, nSea = 0;
                foreach (var uk in roots.SelectMany(g => g.GetComponentsInChildren<PL29UkiyoeHero>(true)))
                {
                    uk.material = mat; EditorUtility.SetDirty(uk); nUk++;
                }
                foreach (var sea in roots.SelectMany(g => g.GetComponentsInChildren<PL30UkiyoeSea>(true)))
                    if (sea.heroMaterial == m29) { sea.heroMaterial = mat; EditorUtility.SetDirty(sea); nSea++; }
                // ほかのレンダラーで仕上げ29 の材質を使うもの（あれば）も替える
                foreach (var rr in roots.SelectMany(g => g.GetComponentsInChildren<Renderer>(true)))
                {
                    var ms = rr.sharedMaterials;
                    bool any = false;
                    for (int i = 0; i < ms.Length; i++) if (ms[i] == m29) { ms[i] = mat; any = true; }
                    if (any) { rr.sharedMaterials = ms; EditorUtility.SetDirty(rr); nRend++; }
                }
                if (nUk == 0) throw new InvalidOperationException("場面に PL29UkiyoeHero がない: " + to);
                ch.Add("主役波の材質を " + MatPath + " にした（PL29UkiyoeHero " + nUk + "、レンダラー " + nRend + "、PL30UkiyoeSea の限定色の元 " + nSea + "）");
                EditorSceneManager.MarkSceneDirty(scene);
                EditorSceneManager.SaveScene(scene);
                r.changesJa = ch.ToArray(); r.toSha256 = Sha(to); r.fromSha256After = Sha(from);
                recs.Add(r);
            }
            AssetDatabase.SaveAssets();
            var rep = new SceneReport { utc = DateTime.UtcNow.ToString("O"), unity = Application.unityVersion, material = MatPath, materialSha256 = Sha(MatPath), scenes = recs.ToArray() };
            var od = Arg("-pl36Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/36/setup";
            Directory.CreateDirectory(od);
            File.WriteAllText(Path.Combine(od, "pl36_setup.json"), JsonUtility.ToJson(rep, true), new UTF8Encoding(false));
            Debug.Log("PL36_SETUP_DONE " + string.Join(" ", recs.Select(x => x.to + "=" + x.toSha256)));
        }

        // 材質の作り直しと場面の写しを 1 回の Unity で行う
        public static void All()
        {
            EnsureMaterial();
            BuildScenes();
        }
    }
}
