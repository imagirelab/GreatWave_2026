using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Rendering;
using UnityEngine;

namespace GreatWave.Design29.EditorTools
{
    // 設計29修正01：精度の層のキーワード DS27_POS_LO を足した設計27 のシェーダー（DS27 NPR White・DS27 Outline Keypose）の変種のコンパイルの確かめ。
    // 設計27 の DS27Formation.CheckShaders（美術優先30・32 と同じ方法：ShaderData.Pass.CompileVariant、D3D、StandaloneWindows64）を写し、
    // キーワードの組に DS27_POS_LO を足した 3 組（DS27_POS_LO／+ INSTANCING_ON／+ STEREO_INSTANCING_ON INSTANCING_ON）を足した。
    // STEREO_INSTANCING_ON の頂点関数の戻り値の構造体に SV_RenderTargetArrayIndex があるかも見る。コンパイルだけで、両眼の描画は確かめていない。
    // 引数：-ds29r01Out <json のパス>（既定 Build/Design/29R01/unity/ds29r01_shader_check.json）。
    // 実行：Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29R01ShaderCheck.Run -Log shader_check
    public static class DS29R01ShaderCheck
    {
        static readonly string[] Shaders = {
            "Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader", "Assets/GreatWave/Design27/Shaders/DS27_Outline_Keypose.shader" };
        const string ComputePath = "Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute";

        [Serializable] class PassCheck { public string shader, pass, keywords, stage, messages; public bool compiled, stereoCheck, rtArrayIndexInOutput; }
        [Serializable] class Report { public PassCheck[] passes; public bool allCompiled, allStereoOutput; public string computeMessages, unity, noteJa; public int computeErrorCount; }

        public static void Run()
        {
            var a = Environment.GetCommandLineArgs();
            string outPath = "Build/Design/29R01/unity/ds29r01_shader_check.json";
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == "-ds29r01Out") outPath = a[i + 1];
            var sets = new[] {
                new string[0], new[] { "INSTANCING_ON" }, new[] { "STEREO_INSTANCING_ON", "INSTANCING_ON" },
                new[] { "DS27_POS_LO" }, new[] { "DS27_POS_LO", "INSTANCING_ON" }, new[] { "DS27_POS_LO", "STEREO_INSTANCING_ON", "INSTANCING_ON" } };
            var checks = new List<PassCheck>();
            foreach (var path in Shaders)
            {
                var sh = AssetDatabase.LoadAssetAtPath<Shader>(path);
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
                                if (!pass.HasShaderStage(st)) continue;
                                var c = new PassCheck { shader = sh.name, pass = pass.Name, keywords = string.Join(" ", kw), stage = st.ToString() };
                                var info = pass.CompileVariant(st, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64);
                                c.compiled = info.Success;
                                c.messages = string.Join(" | ", info.Messages.Select(m => m.severity + ": " + m.message));
                                if (st == ShaderType.Vertex && kw.Contains("STEREO_INSTANCING_ON"))
                                {
                                    var pre = pass.PreprocessVariant(st, kw, ShaderCompilerPlatform.D3D, BuildTarget.StandaloneWindows64, true);
                                    var code = pre.Success ? (pre.PreprocessedCode ?? "") : "";
                                    var vm = Regex.Match(code, @"#pragma\s+vertex\s+(\w+)");
                                    if (!vm.Success) vm = Regex.Match(pass.SourceCode ?? "", @"#pragma\s+vertex\s+(\w+)");
                                    var vf = vm.Success ? vm.Groups[1].Value : "";
                                    var fm = vf.Length > 0 ? Regex.Match(code, @"(\w+)\s+" + Regex.Escape(vf) + @"\s*\(") : Match.Empty;
                                    var so = fm.Success ? fm.Groups[1].Value : "";
                                    var sm = so.Length > 0 ? Regex.Match(code, @"struct\s+" + Regex.Escape(so) + @"\s*\{([^}]*)\}") : Match.Empty;
                                    c.stereoCheck = true;
                                    c.rtArrayIndexInOutput = sm.Success && sm.Groups[1].Value.Contains("SV_RenderTargetArrayIndex");
                                }
                                checks.Add(c);
                            }
                    }
                }
            }
            var cs = AssetDatabase.LoadAssetAtPath<ComputeShader>(ComputePath);
            var cm = ShaderUtil.GetComputeShaderMessages(cs);
            var stereo = checks.Where(c => c.stereoCheck).ToList();
            var rep = new Report
            {
                passes = checks.ToArray(), allCompiled = checks.Count > 0 && checks.All(c => c.compiled),
                allStereoOutput = stereo.Count > 0 && stereo.All(c => c.rtArrayIndexInOutput),
                computeMessages = string.Join(" | ", cm.Select(m => m.severity + ": " + m.message)),
                computeErrorCount = cm.Count(m => m.severity == ShaderCompilerMessageSeverity.Error),
                unity = Application.unityVersion,
                noteJa = "DS27Formation.CheckShaders と同じ方法（ShaderData.Pass.CompileVariant、D3D、StandaloneWindows64）で、キーワードなし・INSTANCING_ON・STEREO_INSTANCING_ON INSTANCING_ON と、" +
                         "それぞれに DS27_POS_LO を足した組をコンパイルした。コンパイルだけで、両眼の描画は確かめていない。コンピュートシェーダーはコンパイルの報告（GetComputeShaderMessages）だけ。"
            };
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath)));
            File.WriteAllText(outPath, JsonUtility.ToJson(rep, true));
            Debug.Log("DS29R01_SHADER_CHECK allCompiled=" + rep.allCompiled + " allStereoOutput=" + rep.allStereoOutput + " computeErrors=" + rep.computeErrorCount);
            if (!rep.allCompiled || !rep.allStereoOutput || rep.computeErrorCount > 0) throw new InvalidOperationException("シェーダーの変種のコンパイルの確かめが不合格です: " + outPath);
        }
    }
}
