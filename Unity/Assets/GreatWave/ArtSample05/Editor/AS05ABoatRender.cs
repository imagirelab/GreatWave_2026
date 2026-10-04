using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.ArtSample05.EditorTools
{
    // 美術の見本05 のやり方 A（Q33、2026-10-04）：一艘目の船（AF27 船 boat_left）を、原画のカメラの位置を中心とする相似で手前へ動かしてから、
    // 見本03 の描画の道具 AS03AsmRender.Render（変えない）をそのまま呼ぶ。
    //   相似：位置 p → cam + s·(p − cam)、大きさ ×s。原画視点の船の画は画素まで同じ（ほかの視点では s 倍の大きさ）。
    //   ③ の新しい小さな砕け波（原画のカメラから約 41 m）の面の手前に船を置き、原画のとおり舳先が ③ の藍の面の手前に立つようにする。
    //   名前の付いた美術の誘導（「一艘目の船を ③ の面の手前に置く」）。場面のファイル（.unity）・プレハブは変えない（開いた後のメモリの中だけ）。
    // 引数：-as05BoatScale s（既定 1 = 動かさない）、-as05BoatCam x,y,z（既定 0,3,-62 = 原画のカメラ）、-as05BoatLog <json の出力>。
    // ほかの引数は AS03AsmRender のまま。
    public static class AS05ABoatRender
    {
        const string BoatName = "AF27 船 boat_left";

        static string Arg(string[] a, string name)
        {
            int i = Array.IndexOf(a, name);
            return i >= 0 && i + 1 < a.Length ? a[i + 1] : null;
        }

        public static void Render()
        {
            var a = Environment.GetCommandLineArgs();
            float s = float.Parse(Arg(a, "-as05BoatScale") ?? "1", CultureInfo.InvariantCulture);
            var camS = (Arg(a, "-as05BoatCam") ?? "0,3,-62").Split(',').Select(x => float.Parse(x.Trim(), CultureInfo.InvariantCulture)).ToArray();
            var cam = new Vector3(camS[0], camS[1], camS[2]);
            string logPath = Arg(a, "-as05BoatLog");
            var log = new List<string>();
            EditorSceneManager.SceneOpenedCallback cb = (scene, mode) =>
            {
                try { log.Add(MoveBoat(s, cam)); }
                catch (Exception e) { log.Add("ERROR " + e.Message); Debug.LogError("AS05A_BOAT " + e); }
            };
            EditorSceneManager.sceneOpened += cb;
            try
            {
                GreatWave.ArtSample03.EditorTools.AS03AsmRender.Render();
            }
            finally
            {
                EditorSceneManager.sceneOpened -= cb;
                if (!string.IsNullOrEmpty(logPath))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(logPath));
                    File.WriteAllText(logPath, "{\n \"boatScale\": " + s.ToString("R", CultureInfo.InvariantCulture) + ",\n \"events\": [\n  " +
                        string.Join(",\n  ", log.Select(x => "\"" + x.Replace("\\", "/").Replace("\"", "'") + "\"")) + "\n ]\n}\n");
                }
                Debug.Log("AS05A_BOAT_DONE scale=" + s + " events=" + log.Count);
            }
        }

        static string MoveBoat(float s, Vector3 cam)
        {
            var go = GameObject.Find(BoatName);
            if (go == null) return "boat_left not found";
            if (Mathf.Abs(s - 1f) < 1e-6f) return "scale 1: not moved";
            var t = go.transform;
            var p0 = t.position;
            var sc0 = t.localScale;
            t.position = cam + s * (p0 - cam);
            t.localScale = sc0 * s;
            int reset = 0;
            // 船の位置を覚える部品（左の盛り上がり PL30LeftSwell・船の鉛直の支え DS30BoatHeave）が、動かす前の位置を覚えていたら忘れさせる
            foreach (var mb in UnityEngine.Object.FindObjectsByType<MonoBehaviour>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                if (mb == null) continue;
                var ty = mb.GetType();
                var fb = ty.GetField("boat", BindingFlags.Public | BindingFlags.Instance);
                if (fb == null || fb.FieldType != typeof(Transform)) continue;
                var bt = fb.GetValue(mb) as Transform;
                if (bt == null || (bt != t && !bt.IsChildOf(t))) continue;
                foreach (var fname in new[] { "boatSaved", "loaded" })
                {
                    var f = ty.GetField(fname, BindingFlags.NonPublic | BindingFlags.Instance);
                    if (f != null && f.FieldType == typeof(bool)) { f.SetValue(mb, false); reset++; }
                }
            }
            return string.Format(CultureInfo.InvariantCulture, "moved {0} from ({1:F4},{2:F4},{3:F4}) to ({4:F4},{5:F4},{6:F4}) scale {7:F4} -> {8:F4}; state reset {9}",
                BoatName, p0.x, p0.y, p0.z, t.position.x, t.position.y, t.position.z, sc0.x, t.localScale.x, reset);
        }
    }
}
