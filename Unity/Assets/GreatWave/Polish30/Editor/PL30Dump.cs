using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Polish30.EditorTools
{
    // 仕上げ30：場面の静的な物（仮置き・船・富士）と、座席・原画視点のカメラの置き方を JSON に書き出す（numpy の生成器と検査の入力。場面は開くだけで保存しない）。
    //  -pl30Out <json> -pl30Scene <場面>（既定 DS39_Paper.unity）。仮置き M1_Revision_LeftSupport は頂点（ワールド）も書く。
    public static class PL30Dump
    {
        [Serializable] class Obj { public string name, path; public bool active, rendererEnabled; public Vector3 boundsMin, boundsMax, position; public Quaternion rotation; public Vector3 lossyScale; public int vertexCount; public float[] worldVertices; public int[] triangles; }
        [Serializable] class CamRec { public string name; public Vector3 position, forward, up; public float fov, aspect, near, far; }
        [Serializable] class Rep { public string scene, utc; public Obj[] objects; public CamRec[] cameras; }

        static string Arg(string n) { var a = Environment.GetCommandLineArgs(); for (int i = 0; i < a.Length - 1; i++) if (a[i] == n) return a[i + 1]; return null; }

        public static void Run()
        {
            var scene = Arg("-pl30Scene") ?? "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity";
            var outp = Arg("-pl30Out") ?? "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30/dump/pl30_scene_dump.json";
            EditorSceneManager.OpenScene(scene, OpenSceneMode.Single);
            var names = new[] { "M1_Revision_LeftSupport", "M1_Revision_RightSlope", "M1_ForegroundSwell_Static", "M1_ForegroundFoam_Static", "M1 left boat", "M1 middle boat", "M1 foreground boat", "M1 distant Fuji", "boat_left", "boat_mid", "boat_fg", "fuji_blockout", "AF27 船 boat_left", "AF27 船 boat_mid", "AF27 船 boat_fg" };
            var objs = new List<Obj>();
            foreach (var t in Resources.FindObjectsOfTypeAll<Transform>())
            {
                if (t.gameObject.scene != EditorSceneManager.GetActiveScene()) continue;
                if (!names.Contains(t.name)) continue;
                var o = new Obj { name = t.name, path = PathOf(t), active = t.gameObject.activeInHierarchy, position = t.position, rotation = t.rotation, lossyScale = t.lossyScale };
                var rs = t.GetComponentsInChildren<Renderer>(true);
                if (rs.Length > 0)
                {
                    var b = rs[0].bounds; foreach (var r in rs) b.Encapsulate(r.bounds);
                    o.boundsMin = b.min; o.boundsMax = b.max; o.rendererEnabled = rs.Any(r => r.enabled);
                }
                if (t.name == "M1_Revision_LeftSupport" || t.name == "M1_Revision_RightSlope" || t.name == "M1_ForegroundSwell_Static" || t.name.StartsWith("AF27 船 "))
                {
                    var vs = new List<float>(); var tris = new List<int>(); int off = 0;
                    foreach (var mf in t.GetComponentsInChildren<MeshFilter>(true))
                    {
                        var m = mf.sharedMesh; if (m == null) continue;
                        foreach (var v in m.vertices) { var w = mf.transform.TransformPoint(v); vs.Add(w.x); vs.Add(w.y); vs.Add(w.z); }
                        foreach (var k in m.triangles) tris.Add(k + off);
                        off += m.vertexCount;
                    }
                    o.worldVertices = vs.ToArray(); o.triangles = tris.ToArray(); o.vertexCount = off;
                }
                objs.Add(o);
            }
            var cams = new List<CamRec>();
            foreach (var c in Resources.FindObjectsOfTypeAll<Camera>())
            {
                if (c.gameObject.scene != EditorSceneManager.GetActiveScene()) continue;
                cams.Add(new CamRec { name = PathOf(c.transform), position = c.transform.position, forward = c.transform.forward, up = c.transform.up, fov = c.fieldOfView, aspect = c.aspect, near = c.nearClipPlane, far = c.farClipPlane });
            }
            Directory.CreateDirectory(Path.GetDirectoryName(outp));
            File.WriteAllText(outp, JsonUtility.ToJson(new Rep { scene = scene, utc = DateTime.UtcNow.ToString("O"), objects = objs.ToArray(), cameras = cams.ToArray() }, true), new UTF8Encoding(false));
            Debug.Log("PL30_DUMP_DONE " + outp + " objects=" + objs.Count + " cameras=" + cams.Count);
        }

        static string PathOf(Transform t) { var s = t.name; while (t.parent != null) { t = t.parent; s = t.name + "/" + s; } return s; }
    }
}
