using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using GreatWave.Design27;
using GreatWave.Design30;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Polish30
{
    // 仕上げ30：仮置き M1_Revision_LeftSupport（左奥の船を載せた平らなクリーム色の板）の置き換え（名前の付いた美術の誘導 pl30_left_swell）。
    //  pl30_left_swell.json（pl30_left_swell.py）の網（ワールドの頂点、底は y = 0）と面の座標を読み、周りの海と同じ材質（PL30 Ukiyoe Sea Keypose）で描く。
    //  τ ごとに、盛り上がりの高さを m(τ) 倍（物体の y の縮尺）にし、左奥の船を (m − 1)·boat_lift_m だけ下げる（t* で 0：原画視点の t* は変わらない）。
    //  keypose のバッファは使わない（材質の _DS27Enabled は 0 のまま。シェーダーはメッシュの頂点をワールドとして読む）。原画カメラは読まない。
    [DefaultExecutionOrder(130)]
    public class PL30LeftSwell : MonoBehaviour
    {
        public DS30SinglePlayback playback;
        [Tooltip("左奥の船の根（AF27 船 boat_left）")] public Transform boat;
        [Tooltip("pl30_left_swell.json（Unity プロジェクトからの相対パスか絶対パス）")] public string dataPath = "Build/Polish/30/left_swell/pl30_left_swell.json";
        public Material material;

        Mesh mesh;
        double[] taus; double[] ms; double lift;
        Vector3 boatPos0; bool boatSaved;
        public bool Loaded { get; private set; }
        public string Sha256 { get; private set; } = "";
        public double CurrentM { get; private set; } = 1.0;

        public void Load()
        {
            if (Loaded) return;
            var path = Path.GetFullPath(dataPath);
            var bytes = File.ReadAllBytes(path);
            using (var s = SHA256.Create()) Sha256 = BitConverter.ToString(s.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
            var j = DS27Json.AsObj(DS27Json.Parse(System.Text.Encoding.UTF8.GetString(bytes)), "pl30_left_swell.json");
            var v = DS27Json.Nums(DS27Json.Get(j, "vertices_flat"), "vertices_flat");
            var tri = DS27Json.Nums(DS27Json.Get(j, "triangles"), "triangles");
            var at = DS27Json.Nums(DS27Json.Get(j, "attr"), "attr");
            taus = DS27Json.Nums(DS27Json.Get(j, "tau"), "tau");
            ms = DS27Json.Nums(DS27Json.Get(j, "m"), "m");
            lift = DS27Json.Num(j, "boat_lift_m");
            int n = v.Length / 3;
            var verts = new Vector3[n];
            for (int i = 0; i < n; i++) verts[i] = new Vector3((float)v[3 * i], (float)v[3 * i + 1], (float)v[3 * i + 2]);
            // 面の座標：修正01 の 20 個（UV3〜UV7）。作る部の 12 個（UV3〜UV5）のファイルも読める
            int fpv = at.Length == n * 20 ? 20 : 12;
            var a = new List<Vector4>(n); var b = new List<Vector4>(n); var c = new List<Vector4>(n);
            var d = new List<Vector4>(fpv == 20 ? n : 0); var e = new List<Vector4>(fpv == 20 ? n : 0);
            for (int i = 0; i < n; i++)
            {
                int o = i * fpv;
                a.Add(new Vector4((float)at[o], (float)at[o + 1], (float)at[o + 2], (float)at[o + 3]));
                b.Add(new Vector4((float)at[o + 4], (float)at[o + 5], (float)at[o + 6], (float)at[o + 7]));
                c.Add(new Vector4((float)at[o + 8], (float)at[o + 9], (float)at[o + 10], (float)at[o + 11]));
                if (fpv == 20)
                {
                    d.Add(new Vector4((float)at[o + 12], (float)at[o + 13], (float)at[o + 14], (float)at[o + 15]));
                    e.Add(new Vector4((float)at[o + 16], (float)at[o + 17], (float)at[o + 18], (float)at[o + 19]));
                }
            }
            var t = new int[tri.Length];
            for (int i = 0; i < t.Length; i++) t[i] = (int)tri[i];
            mesh = new Mesh { name = "PL30 左奥の船のうねり", indexFormat = IndexFormat.UInt32, hideFlags = HideFlags.DontSave };
            mesh.vertices = verts;
            mesh.triangles = t;
            mesh.SetUVs(3, a); mesh.SetUVs(4, b); mesh.SetUVs(5, c);
            if (fpv == 20) { mesh.SetUVs(6, d); mesh.SetUVs(7, e); }
            mesh.RecalculateBounds();
            var mf = GetComponent<MeshFilter>(); if (mf == null) mf = gameObject.AddComponent<MeshFilter>();
            mf.sharedMesh = mesh;
            var mr = GetComponent<MeshRenderer>(); if (mr == null) mr = gameObject.AddComponent<MeshRenderer>();
            mr.sharedMaterial = material;
            mr.shadowCastingMode = ShadowCastingMode.Off; mr.receiveShadows = false;
            transform.position = Vector3.zero; transform.rotation = Quaternion.identity;
            if (boat != null && !boatSaved) { boatPos0 = boat.position; boatSaved = true; }
            Loaded = true;
        }

        public double MAt(double tau)
        {
            if (taus == null || taus.Length == 0) return 1.0;
            if (tau <= taus[0]) return ms[0];
            if (tau >= taus[taus.Length - 1]) return ms[ms.Length - 1];
            int i = Array.BinarySearch(taus, tau);
            if (i >= 0) return ms[i];
            i = ~i - 1;
            double s = (tau - taus[i]) / (taus[i + 1] - taus[i]);
            return ms[i] + s * (ms[i + 1] - ms[i]);
        }

        /// <summary>物理の時刻 τ の盛り上がりの高さと船の高さにする。</summary>
        public void ApplyTau(double tau)
        {
            if (!Loaded) Load();
            CurrentM = MAt(tau);
            float m = Mathf.Max((float)CurrentM, 1e-3f);
            transform.localScale = new Vector3(1f, m, 1f);
            if (boat != null) boat.position = boatPos0 + new Vector3(0f, (float)((CurrentM - 1.0) * lift), 0f);
        }

        /// <summary>船を元の位置へ戻す（Editor の道具の後始末）。</summary>
        public void Restore()
        {
            if (boat != null && boatSaved) boat.position = boatPos0;
        }

        void LateUpdate()
        {
            if (!Application.isPlaying || playback == null) return;
            if (!double.IsNaN(playback.Tau)) ApplyTau(playback.Tau);
        }

        void OnDestroy()
        {
            if (mesh != null) { if (Application.isPlaying) Destroy(mesh); else DestroyImmediate(mesh); }
        }
    }
}
