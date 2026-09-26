using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.Rendering;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.ArtFirst.EditorTools
{
    // 番号32：性能測定用の Release（Development でない）Windows プレイヤーを作る。
    //  1. 自作シェーダー（Assets/GreatWave 以下の全部）を SPI の立体視キーワードでコンパイルし、前処理後の頂点出力に
    //     SV_RenderTargetArrayIndex（眼のスライスへ振り分ける出力）があるかを確かめる。
    //  2. CP1 の合成シーン AF_CP1.unity（コミット済み）を AF32_Perf.unity へ複製し、K* 45° だけを残して計測器 AF32PerfRunner を置く。
    //     AF_CP1・番号26〜28 の資産は読むだけで変えない（前後の SHA-256 を記録する）。
    //  3. PlayerSettings.enableFrameTimingStats を一時的に true にしてビルドし、finally で元の値へ戻す。
    //     ProjectSettings.asset のバイト単位の復元は、外側の af32_run_unity.ps1 が Unity の終了後に確かめて行う。
    public static class AF32PerfBuild
    {
        const string SrcScene = "Assets/GreatWave/Scenes/Tests/AF_CP1.unity";
        const string SrcSceneCommittedSha = "553ab44a00710092cbea7d110ebfd467938682a4dfa952535986d6f73d7e8209";   // CP1（370297c）の run.json
        public const string ScenePath = "Assets/GreatWave/Scenes/Tests/AF32_Perf.unity";
        const string OutRoot = "Build/ArtFirst/32";
        const string PlayerPath = OutRoot + "/player/AF32Perf.exe";

        static string[] ProtectedFiles => new[] {
            SrcScene, "Assets/GreatWave/ArtFirst/Prefabs/AF27_Context.prefab", "Assets/GreatWave/ArtFirst/Prefabs/AF27_SkyDome.prefab",
            "Assets/GreatWave/ArtFirst/Materials/AF28_NPR.mat", "Assets/GreatWave/ArtFirst/Materials/AF28_Outline.mat",
            "Assets/GreatWave/ArtFirst/Materials/AF28_SeaFlat.mat", "Assets/GreatWave/ArtFirst/Materials/AF27_SkyDome.mat",
            "Assets/GreatWave/ArtFirst/Shaders/AF28_NPR.shader", "Assets/GreatWave/ArtFirst/Shaders/AF28_Outline.shader",
            "Assets/GreatWave/ArtFirst/Shaders/AF27SkyDome.shader", "Assets/GreatWave/ArtFirst/Shaders/AF27Flat.shader",
            "Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs", "Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs" };

        public static void BuildAll()
        {
            CheckShaders();
            BuildScene();
            BuildPlayer();
        }

        // ------------------------------------------------------------------ 1. シェーダー
        [Serializable] class ShaderPassCheck
        {
            public string shader, path, pass, keywords, stage; public int subshader, passIndex;
            public bool hasStage, compiled, rtArrayIndexInOutput; public string vertexFunction, vertexOutputStruct, messages;
        }
        [Serializable] class ShaderStatic
        {
            public string shader, path; public bool hasError;
            public bool vertexInputInstanceId, vertexOutputStereo, setupInstanceId, initVertexOutputStereo, setupStereoEyeIndexPostVertex, surfaceShader, usesMultiCompileInstancing;
        }
        [Serializable] class ShaderReport
        {
            public string unity, platform, noteJa; public string[] keywordSets;
            public ShaderStatic[] shaders; public ShaderPassCheck[] passes;
            public bool allCompiled, allStereoOutput; public string[] failures;
        }

        public static void CheckShaders()
        {
            Directory.CreateDirectory(OutRoot);
            var sets = new[] { new string[0], new[] { "INSTANCING_ON" }, new[] { "STEREO_INSTANCING_ON", "INSTANCING_ON" } };
            var checks = new List<ShaderPassCheck>();
            var statics = new List<ShaderStatic>();
            var failures = new List<string>();
            foreach (var guid in AssetDatabase.FindAssets("t:Shader", new[] { "Assets/GreatWave" }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                var sh = AssetDatabase.LoadAssetAtPath<Shader>(path);
                if (sh == null) continue;
                var src = File.ReadAllText(path);
                statics.Add(new ShaderStatic
                {
                    shader = sh.name, path = path, hasError = ShaderUtil.ShaderHasError(sh),
                    vertexInputInstanceId = src.Contains("UNITY_VERTEX_INPUT_INSTANCE_ID"), vertexOutputStereo = src.Contains("UNITY_VERTEX_OUTPUT_STEREO"),
                    setupInstanceId = src.Contains("UNITY_SETUP_INSTANCE_ID"), initVertexOutputStereo = src.Contains("UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO"),
                    setupStereoEyeIndexPostVertex = src.Contains("UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX"), surfaceShader = src.Contains("#pragma surface"),
                    usesMultiCompileInstancing = src.Contains("multi_compile_instancing")
                });
                var data = ShaderUtil.GetShaderData(sh);
                for (int s = 0; s < data.SubshaderCount; s++)
                {
                    var sub = data.GetSubshader(s);
                    for (int p = 0; p < sub.PassCount; p++)
                    {
                        var pass = sub.GetPass(p);
                        foreach (var kw in sets)
                            foreach (var st in new[] { ShaderType.Vertex, ShaderType.Fragment })
                            {
                                var c = new ShaderPassCheck { shader = sh.name, path = path, subshader = s, passIndex = p, pass = pass.Name, keywords = string.Join(" ", kw), stage = st.ToString() };
                                c.hasStage = pass.HasShaderStage(st);
                                if (c.hasStage)
                                {
                                    var info = pass.CompileVariant(st, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64);
                                    c.compiled = info.Success;
                                    c.messages = string.Join(" | ", info.Messages.Select(m => m.severity + ": " + m.message));
                                    if (st == ShaderType.Vertex && kw.Contains("STEREO_INSTANCING_ON"))
                                    {
                                        // 前処理後のコードで、頂点関数（#pragma vertex）の戻り値の構造体の中に SV_RenderTargetArrayIndex があるかを見る。
                                        // UnityCG.cginc の使わない構造体（v2f_img など）にも同じ語が出るので、コード全体の検索では判定しない。
                                        var pre = pass.PreprocessVariant(st, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64, true);
                                        var code = pre.Success ? (pre.PreprocessedCode ?? "") : "";
                                        var vm = Regex.Match(code, @"#pragma\s+vertex\s+(\w+)");
                                        if (!vm.Success) vm = Regex.Match(pass.SourceCode ?? "", @"#pragma\s+vertex\s+(\w+)");
                                        c.vertexFunction = vm.Success ? vm.Groups[1].Value : "";
                                        if (c.vertexFunction.Length > 0)
                                        {
                                            var fm = Regex.Match(code, @"(\w+)\s+" + Regex.Escape(c.vertexFunction) + @"\s*\(");
                                            c.vertexOutputStruct = fm.Success ? fm.Groups[1].Value : "";
                                            var sm = c.vertexOutputStruct.Length > 0 ? Regex.Match(code, @"struct\s+" + Regex.Escape(c.vertexOutputStruct) + @"\s*\{([^}]*)\}") : Match.Empty;
                                            c.rtArrayIndexInOutput = sm.Success && sm.Groups[1].Value.Contains("SV_RenderTargetArrayIndex");
                                        }
                                    }
                                    if (!c.compiled) failures.Add(sh.name + " " + pass.Name + " " + c.keywords + " " + c.stage);
                                }
                                checks.Add(c);
                            }
                    }
                }
            }
            var stereoVerts = checks.Where(c => c.hasStage && c.stage == "Vertex" && c.keywords.Contains("STEREO_INSTANCING_ON")).ToList();
            var rep = new ShaderReport
            {
                unity = Application.unityVersion, platform = "D3D（StandaloneWindows64）",
                keywordSets = sets.Select(k => string.Join(" ", k)).ToArray(),
                shaders = statics.ToArray(), passes = checks.ToArray(),
                allCompiled = checks.Where(c => c.hasStage).All(c => c.compiled),
                allStereoOutput = stereoVerts.Count > 0 && stereoVerts.All(c => c.rtArrayIndexInOutput),
                failures = failures.ToArray(),
                noteJa = "ShaderData.Pass.CompileVariant でコンパイルだけを行い、STEREO_INSTANCING_ON の頂点シェーダーは前処理後のコードに SV_RenderTargetArrayIndex（SPI で眼のスライスへ振り分ける出力）があるかを見た。両眼の描画そのものは Mock Runtime（af32_mock）で確かめる。"
            };
            File.WriteAllText(OutRoot + "/af32_spi_compile.json", JsonUtility.ToJson(rep, true));
            Debug.Log("AF32_SPI_COMPILE shaders=" + statics.Count + " allCompiled=" + rep.allCompiled + " allStereoOutput=" + rep.allStereoOutput);
        }

        // ------------------------------------------------------------------ 2. シーン
        [Serializable] class BuildReportJ
        {
            public string unity, utc, srcScene, srcSceneSha256, srcSceneCommittedSha256, scene, sceneSha256;
            public bool srcSceneMatchesCommitted, protectedUnchanged;
            public string[] protectedFiles, changedFiles;
            public string playerPath, buildResult, buildOptions; public long totalSize; public double buildSeconds;
            public bool frameTimingStatsDuringBuild, frameTimingStatsRestored; public bool frameTimingStatsBefore;
            public string[] buildErrors, playerFiles, sceneShaders;
            public string noteJa;
        }

        static BuildReportJ rep;

        public static void BuildScene()
        {
            rep = new BuildReportJ { unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), srcScene = SrcScene, srcSceneCommittedSha256 = SrcSceneCommittedSha, scene = ScenePath };
            var before = ProtectedFiles.ToDictionary(p => p, Sha);
            rep.srcSceneSha256 = before[SrcScene];
            rep.srcSceneMatchesCommitted = rep.srcSceneSha256 == SrcSceneCommittedSha;
            if (File.Exists(ScenePath)) AssetDatabase.DeleteAsset(ScenePath);
            if (!AssetDatabase.CopyAsset(SrcScene, ScenePath)) throw new InvalidOperationException("シーンを複製できません。");
            var scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            GameObject keep = null;
            foreach (var root in scene.GetRootGameObjects())
            {
                if (root.name == "CP1 K* a30" || root.name == "CP1 K* a60") UnityEngine.Object.DestroyImmediate(root);
                else if (root.name == "CP1 K* a45") keep = root;
            }
            if (keep == null) throw new InvalidOperationException("K* 45° がありません。");
            keep.name = "AF32 主役波 K* a45（番号26 の K*、番号28 の NPR v1・外殻線 v0）";
            // データは実行時に AF32PerfRunner が Build/ArtFirst/32/data/ の複製から読む（シーンの値は使わない印として空にする）
            keep.GetComponent<AF26KStarMesh>().dataPath = "";
            var nw = keep.GetComponent<AF28NprWave>();
            nw.sdfPath = ""; nw.warpPath = "";
            keep.SetActive(false);
            var go = new GameObject("AF32 計測（AF32PerfRunner）");
            var runner = go.AddComponent<AF32PerfRunner>();
            runner.wave = keep;
            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("シーンを保存できません。");
            rep.sceneSha256 = Sha(ScenePath);
            rep.sceneShaders = AssetDatabase.GetDependencies(ScenePath, true).Where(p => p.EndsWith(".shader") || p.EndsWith(".cginc")).OrderBy(p => p).ToArray();
            var after = ProtectedFiles.ToDictionary(p => p, Sha);
            rep.protectedUnchanged = ProtectedFiles.All(p => before[p] == after[p]);
            rep.protectedFiles = ProtectedFiles.Select(p => p + " " + after[p]).ToArray();
            rep.changedFiles = ProtectedFiles.Where(p => before[p] != after[p]).ToArray();
            WriteReport();
            if (!rep.protectedUnchanged) throw new InvalidOperationException("読むだけの資産が変わりました: " + string.Join(", ", rep.changedFiles));
            Debug.Log("AF32_SCENE_DONE srcMatchesCommitted=" + rep.srcSceneMatchesCommitted);
        }

        // ------------------------------------------------------------------ 3. Release プレイヤー
        public static void BuildPlayer()
        {
            if (rep == null) rep = new BuildReportJ { unity = Application.unityVersion, utc = DateTime.UtcNow.ToString("O"), scene = ScenePath };
            bool prev = PlayerSettings.enableFrameTimingStats;
            rep.frameTimingStatsBefore = prev;
            var playerDir = Path.GetDirectoryName(PlayerPath);
            if (Directory.Exists(playerDir)) Directory.Delete(playerDir, true);
            Directory.CreateDirectory(playerDir);
            BuildReport br = null;
            try
            {
                PlayerSettings.enableFrameTimingStats = true;
                rep.frameTimingStatsDuringBuild = PlayerSettings.enableFrameTimingStats;
                var opts = new BuildPlayerOptions
                {
                    scenes = new[] { ScenePath }, locationPathName = PlayerPath,
                    target = BuildTarget.StandaloneWindows64, targetGroup = BuildTargetGroup.Standalone,
                    options = BuildOptions.None   // Release（Development・Profiler 接続・スクリプトのデバッグなし）
                };
                rep.buildOptions = opts.options.ToString();
                br = BuildPipeline.BuildPlayer(opts);
            }
            finally
            {
                PlayerSettings.enableFrameTimingStats = prev;
                AssetDatabase.SaveAssets();
                rep.frameTimingStatsRestored = PlayerSettings.enableFrameTimingStats == prev;
            }
            rep.playerPath = Path.GetFullPath(PlayerPath);
            rep.buildResult = br.summary.result.ToString();
            rep.totalSize = (long)br.summary.totalSize;
            rep.buildSeconds = br.summary.totalTime.TotalSeconds;
            rep.buildErrors = br.steps.SelectMany(s => s.messages).Where(m => m.type == LogType.Error || m.type == LogType.Exception).Select(m => m.content).ToArray();
            rep.playerFiles = Directory.Exists(playerDir) ? Directory.GetFiles(playerDir, "*", SearchOption.AllDirectories).Select(f => f.Substring(playerDir.Length + 1).Replace('\\', '/') + " " + new FileInfo(f).Length).OrderBy(s => s).ToArray() : new string[0];
            rep.noteJa = "BuildOptions.None の Release プレイヤー。enableFrameTimingStats はビルドの間だけ true にし、finally で元へ戻した。";
            WriteReport();
            Debug.Log("AF32_BUILD_DONE result=" + rep.buildResult);
            if (br.summary.result != BuildResult.Succeeded) throw new InvalidOperationException("ビルドに失敗しました: " + string.Join(" / ", rep.buildErrors));
        }

        static void WriteReport()
        {
            Directory.CreateDirectory(OutRoot);
            File.WriteAllText(OutRoot + "/af32_build_report.json", JsonUtility.ToJson(rep, true));
        }

        static string Sha(string path)
        {
            using (var s = System.Security.Cryptography.SHA256.Create())
            using (var f = File.OpenRead(path))
                return BitConverter.ToString(s.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
