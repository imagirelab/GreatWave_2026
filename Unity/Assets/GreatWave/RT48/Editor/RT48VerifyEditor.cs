using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.RT48.EditorTools
{
    // RT48：確かめの書き出しを Editor の batchmode で走らせる（record_ja.md の V1・V3・V4・V5・V6。判定は Python の v_compare.py）。
    //   -executeMethod GreatWave.RT48.EditorTools.RT48VerifyEditor.RunAndExit -rt48verifysource coarse [-rt48export <出力>]
    // 場面 RT48_Playback.unity を開くだけで、作り直さず、保存もしない。読む焼きは Unity/Build/RT48/data/<元>/、
    // v_prep.py の出力は Unity/Build/RT48/verify/<元>/、書き出しの既定は Unity/Build/RT48/verify/<元>/unity_editor/。
    public static class RT48VerifyEditor
    {
        public static void RunAndExit()
        {
            int code = 1;
            try
            {
                string srcName = RT48Playback.Arg("-rt48verifysource", "coarse");
                string dataDir = Path.Combine(RT48SceneBuilder.DataRoot, srcName);
                string verifyDir = Path.Combine(RT48SceneBuilder.BuildRoot, "verify", srcName);
                string outDir = RT48Playback.Arg("-rt48export", Path.Combine(verifyDir, "unity_editor"));
                EditorSceneManager.OpenScene(RT48SceneBuilder.ScenePath, OpenSceneMode.Single);
                var pb = UnityEngine.Object.FindAnyObjectByType<RT48Playback>();
                if (pb == null) throw new InvalidOperationException("RT48Playback が場面にありません");
                pb.Initialize(dataDir);
                if (pb.Source == null) throw new InvalidOperationException("元を読めません：" + pb.LoadError);
                Debug.Log("RT48_VERIFY source=" + pb.Source.Describe());
                RT48VerifyExport.Run(pb, verifyDir, outDir, true);
                pb.ReleaseAll();
                code = 0;
            }
            catch (Exception e) { Debug.LogError("RT48_VERIFY_EXCEPTION " + e); code = 1; }
            EditorApplication.Exit(code);
        }
    }
}
