using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using GreatWave.Design47;
using GreatWave.Design47.EditorTools;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Design48.EditorTools
{
    // 設計48：体験の場面 DS48_Wake.unity を作る（PC の Editor の batchmode。HMD 実機ではない）。
    //   1) 設計47 の DS47_Flow.unity（体験の一本の場面）を開く（保存しない）。
    //   2) 「DS48 船首の泡・航跡」（DS48Wake ＋ 世界の原点の MeshFilter・MeshRenderer、材質 DS48_Foam.mat = 調色板の白）を足す。
    //      座席の船の根（DS47 の物理の根）・船用水面データ（設計43）・進行役（設計47）を読むだけで、ほかの部品は変えない。
    //   3) DS48_Wake.unity として別に保存する。守るファイル（前の番号の場面・部品・表）は前後で SHA-256 を比べる。
    public static class DS48WakeBuild
    {
        public const string Scene47 = "Assets/GreatWave/Design47/Scenes/DS47_Flow.unity";
        public const string Scene48 = "Assets/GreatWave/Design48/Scenes/DS48_Wake.unity";
        public const string WakeJson = "Assets/GreatWave/Design48/Data/ds48_wake.json";
        public const string ShaderPath = "Assets/GreatWave/Design48/Shaders/DS48_Foam.shader";
        public const string MatPath = "Assets/GreatWave/Design48/Materials/DS48_Foam.mat";
        public const string WakeName = "DS48 船首の泡・航跡（座席の船）";

        public static string[] Protected => DS47FlowBuild.Protected.Concat(new[] {
            Scene47, DS47FlowBuild.FlowJson, "Assets/GreatWave/Design47/Scripts/DS47Flow.cs", "Assets/GreatWave/Design47/Scripts/DS47Recorder.cs",
            "Assets/GreatWave/Design47/Editor/DS47FlowBuild.cs", "Assets/GreatWave/Design47/Editor/DS47FlowPlay.cs", "Assets/GreatWave/Design47/Materials/DS47_LeaveOverlay.mat" }).Distinct().ToArray();

        public static string FileSha(string path)
        {
            if (!File.Exists(path)) return "";
            using (var s = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }

        public static string Build()
        {
            AssetDatabase.Refresh();
            var wakeAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(WakeJson);
            var cfg = DS48Config.Parse(wakeAsset.text);
            var shader = AssetDatabase.LoadAssetAtPath<Shader>(ShaderPath);
            if (shader == null) throw new InvalidOperationException("DS48_Foam.shader がありません");
            Directory.CreateDirectory(Path.GetDirectoryName(MatPath));
            var mat = AssetDatabase.LoadAssetAtPath<Material>(MatPath);
            if (mat == null) { mat = new Material(shader); AssetDatabase.CreateAsset(mat, MatPath); }
            mat.shader = shader;
            mat.SetColor("_Color", cfg.PaletteWhite);
            mat.SetFloat("_DashFreq", cfg.shader.dashFreqPerM);
            mat.SetFloat("_AcrossFreq", cfg.shader.acrossFreq);
            mat.SetFloat("_SolidLife", cfg.shader.solidLife);
            mat.renderQueue = 2450;
            EditorUtility.SetDirty(mat);
            AssetDatabase.SaveAssets();

            var scene = EditorSceneManager.OpenScene(Scene47, OpenSceneMode.Single);
            var flow = UnityEngine.Object.FindFirstObjectByType<DS47Flow>();
            if (flow == null) throw new InvalidOperationException("DS47Flow がありません");
            var go = new GameObject(WakeName);
            go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            var mf = go.AddComponent<MeshFilter>();
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; mr.receiveShadows = false;
            mr.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off; mr.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
            mr.motionVectorGenerationMode = MotionVectorGenerationMode.ForceNoMotion;
            var w = go.AddComponent<DS48Wake>();
            w.configJson = wakeAsset; w.flow = flow; w.boat = flow.steer.transform; w.water = flow.bus.boatWater; w.material = mat; w.meshFilter = mf; w.meshRenderer = mr;
            EditorSceneManager.MarkSceneDirty(scene);
            Directory.CreateDirectory(Path.GetDirectoryName(Scene48));
            if (!EditorSceneManager.SaveScene(scene, Scene48, true)) throw new InvalidOperationException("DS48_Wake.unity を保存できません");
            AssetDatabase.SaveAssets();
            var sb = new StringBuilder();
            sb.Append("\"scene\":\"").Append(Scene48).Append("\",\"sceneSha256\":\"").Append(FileSha(Scene48)).Append('"');
            sb.Append(",\"material\":\"").Append(MatPath).Append("\",\"materialSha256\":\"").Append(FileSha(MatPath)).Append('"');
            var c = cfg.PaletteWhite;
            sb.Append(",\"colorSrgb8\":[").Append(cfg.color.srgb8[0]).Append(',').Append(cfg.color.srgb8[1]).Append(',').Append(cfg.color.srgb8[2]).Append(']');
            sb.Append(",\"otherBoatsJa\":\"boat_fg・boat_left は原画の置き方で止まっている（設計47 の D47-6）ので、泡と航跡は付けない\"");
            return sb.ToString();
        }
    }
}
