using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Editor
{
    public static class M0Build
    {
        [MenuItem("GreatWave/10 PC確認版をビルド")]
        public static void Build()
        {
            M0XRSetup.Validate();
            var scene = EditorSceneManager.OpenScene(M0BaselineBuilder.ScenePath);
            var controller = UnityEngine.Object.FindAnyObjectByType<M0ViewController>();
            if (controller == null) throw new InvalidOperationException("09の静止船と視点が必要です。");
            var recorder = controller.GetComponent<M0EvidenceRecorder>() ?? controller.gameObject.AddComponent<M0EvidenceRecorder>();
            recorder.controller = controller;
            recorder.captionPanelMaterial = M0BaselineBuilder.Material("M0_EvidencePanel", new Color(.055f, .12f, .16f));
            EditorSceneManager.SaveScene(scene);
            AssetDatabase.SaveAssets();
            Directory.CreateDirectory("Builds/M0");
            var sources = new List<SourceFile>();
            foreach (string folder in new[] { "Assets", "Packages", "ProjectSettings" })
            foreach (var path in Directory.GetFiles(folder, "*", SearchOption.AllDirectories).OrderBy(p => p))
            {
                using (var sha = SHA256.Create())
                    sources.Add(new SourceFile { path = path.Replace('\\', '/'), sha256 = BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant() });
            }
            File.WriteAllText("../Docs/Evidence/M0/10_prebuild_sources.json", JsonUtility.ToJson(new Sources { files = sources.ToArray() }, true));
            var build = BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes = new[] { M0BaselineBuilder.ScenePath },
                target = BuildTarget.StandaloneWindows64, locationPathName = "Builds/M0/GreatWaveM0.exe", options = BuildOptions.Development });
            var summary = new Summary { unity = Application.unityVersion, target = "Windows x64 / Mono / Direct3D 11 / Development",
                result = build.summary.result.ToString(), errors = build.summary.totalErrors, warnings = build.summary.totalWarnings,
                bytes = build.summary.totalSize.ToString(), seconds = build.summary.totalTime.TotalSeconds,
                scene = M0BaselineBuilder.ScenePath, passed = build.summary.result == BuildResult.Succeeded && build.summary.totalErrors == 0 };
            AssetDatabase.SaveAssets();
            var changed = new List<string>();
            foreach (var entry in sources)
            {
                using (var sha = SHA256.Create())
                {
                    string after = BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(entry.path))).Replace("-", "").ToLowerInvariant();
                    if (after != entry.sha256) changed.Add(entry.path);
                    entry.sha256 = after;
                }
            }
            summary.buildModifiedFiles = changed.ToArray();
            File.WriteAllText("../Docs/Evidence/M0/10_build_sources.json", JsonUtility.ToJson(new Sources { files = sources.ToArray() }, true));
            File.WriteAllText("../Docs/Evidence/M0/10_build.json", JsonUtility.ToJson(summary, true));
            if (!summary.passed) throw new InvalidOperationException("10のWindowsビルドが不合格です。");
            Debug.Log("M0_STEP10_BUILD_PASS: " + summary.bytes + " bytes");
        }
        [Serializable] class Summary { public string unity, target, result, bytes, scene; public string[] buildModifiedFiles; public int errors, warnings; public double seconds; public bool passed; }
        [Serializable] class SourceFile { public string path, sha256; }
        [Serializable] class Sources { public SourceFile[] files; }
    }
}
