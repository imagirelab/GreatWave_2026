using System;
using System.Collections.Generic;
using GreatWave.Design34;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design38
{
    // 設計38：爪の縁の線（DS38 Outline Mesh の反転シェル）。設計34 の爪の結合メッシュ（DS34ClawPlayer、コマの表の頂点を差し替える）の頂点を
    // 毎回写し、滑らかな頂点の法線を付けた自分のメッシュを子レンダラーで描く（DS34ClawPlayer は変えない）。
    //  ・Sync()：爪の今の頂点（DS34ClawPlayer.Current）を入れて法線を作り直す。爪の時刻を合わせた後（ApplyT の後）に呼ぶ。
    //    Play モードでは LateUpdate（爪の再生器は Update で頂点を入れる）で呼ぶので、線は同じコマの爪の位置になる（古い位置に残らない）。
    //  ・爪のレンダラーが切れている時（層の入切）は線も描かない。
    //  ・UV2 = (爪の番号, 爪の中の頂点の番号)（検査用の線の座標の出力）。
    [DefaultExecutionOrder(70)]
    public class DS38ClawOutline : MonoBehaviour
    {
        public DS34ClawPlayer claws;
        public Material lineMaterial;
        public bool syncInPlayMode = true;

        Mesh mesh;
        MeshRenderer lineR;
        public int VertexCount { get; private set; }
        public int TriangleCount { get; private set; }
        public double SyncedT { get; private set; } = double.NaN;

        public MeshRenderer Attach()
        {
            if (claws == null) claws = GetComponent<DS34ClawPlayer>();
            var tr = claws.transform.Find("DS38 爪の縁の線");
            GameObject go;
            if (tr == null)
            {
                go = new GameObject("DS38 爪の縁の線");
                go.transform.SetParent(claws.transform, false);
                go.AddComponent<MeshFilter>();
                go.AddComponent<MeshRenderer>();
            }
            else go = tr.gameObject;
            lineR = go.GetComponent<MeshRenderer>();
            lineR.sharedMaterial = lineMaterial;
            lineR.shadowCastingMode = ShadowCastingMode.Off; lineR.receiveShadows = false;
            lineR.lightProbeUsage = LightProbeUsage.Off; lineR.reflectionProbeUsage = ReflectionProbeUsage.Off;
            lineR.motionVectorGenerationMode = MotionVectorGenerationMode.ForceNoMotion;
            return lineR;
        }

        public MeshRenderer Line => lineR != null ? lineR : (lineR = claws != null && claws.transform.Find("DS38 爪の縁の線") != null ? claws.transform.Find("DS38 爪の縁の線").GetComponent<MeshRenderer>() : null);

        void Build()
        {
            var src = claws.GetComponent<MeshFilter>().sharedMesh;
            if (src == null) { claws.Load(); src = claws.GetComponent<MeshFilter>().sharedMesh; }
            var tris = new List<int>();
            for (int s = 0; s < src.subMeshCount; s++) tris.AddRange(src.GetTriangles(s));
            VertexCount = claws.VertexCount;
            TriangleCount = tris.Count / 3;
            mesh = new Mesh { name = "DS38 爪の縁の線のメッシュ", hideFlags = HideFlags.DontSave };
            mesh.indexFormat = VertexCount > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16;
            mesh.MarkDynamic();
            mesh.SetVertices(claws.Current);
            mesh.SetTriangles(tris, 0, false);
            var uv2 = new Vector2[VertexCount];
            for (int c = 0; c < claws.ClawCount; c++)
                for (int k = 0; k < claws.VertCount[c]; k++) uv2[claws.VertOffset[c] + k] = new Vector2(c, k);
            mesh.SetUVs(2, uv2);
            mesh.RecalculateNormals();
            mesh.bounds = new Bounds(Vector3.zero, Vector3.one * 2000f);
            var mf = Line.GetComponent<MeshFilter>();
            mf.sharedMesh = mesh;
            Line.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            Line.transform.localScale = Vector3.one;
        }

        /// <summary>爪の今の頂点を写して法線を作り直す（爪の ApplyT の後に呼ぶ）。</summary>
        public void Sync()
        {
            if (claws == null || !claws.Loaded || Line == null) return;
            if (mesh == null) Build();
            mesh.SetVertices(claws.Current);
            mesh.RecalculateNormals();
            mesh.bounds = new Bounds(Vector3.zero, Vector3.one * 2000f);
            var cr = claws.GetComponent<MeshRenderer>();
            Line.enabled = cr != null && cr.enabled && claws.gameObject.activeInHierarchy;
            SyncedT = claws.AppliedT;
        }

        void LateUpdate()
        {
            if (Application.isPlaying && syncInPlayMode) Sync();
        }

        void OnDestroy() { Release(); }

        public void Release()
        {
            if (mesh != null) { if (Application.isPlaying) Destroy(mesh); else DestroyImmediate(mesh); mesh = null; }
        }
    }
}
