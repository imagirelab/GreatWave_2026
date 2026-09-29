using System;
using System.IO;
using System.Linq;
using GreatWave.ArtFirst;
using GreatWave.Design27;
using GreatWave.Design27.EditorTools;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Design29.EditorTools
{
    // 設計29修正01（手渡し (a)）：色面（NPR の色区）を K*′ へ焼き直す入口。
    // 1) 入力は Tools/GWWaveGen/ds29r01/ds29r01_bake_input.py が作る <root>/bake_input/af28_bake_meta.json（K*′ の UV3 の表を含む）。
    // 2) 設計27 の場面 DS27_Formation.unity を開き（保存しない）、描画と同じカメラ「DS27 painting」（PaintingCam v1）を使う。
    //    設計27 の主役波の変換が単位行列であることを確かめる（焼き込みは K*′ を単位行列で描くので、描画と同じ置き方になる）。
    // 3) K*′ の .gwb を AF26KStarMesh で読み、UV3 の表を当て、DS29R01ProjectionBaker（美術優先28修正01 の焼き込みの写し）で
    //    r01（採用）と rule28（比較。美術優先28修正01 の評価器が両方を読む）を焼く。出力は <root>/bake/。
    // 引数：-ds29r01BakeRoot <Unity からの相対。既定 Build/Design/29R01/bake_kp>
    // 実行：Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29R01Bake.BakeKStarPrime -Log bake_kp
    // PC の GPU（Editor batchmode）での計算で、HMD 実機ではない。
    public static class DS29R01Bake
    {
        static string Arg(string[] a, string name)
        {
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }

        public static void BakeKStarPrime()
        {
            var args = Environment.GetCommandLineArgs();
            DS29R01ProjectionBaker.BuildRoot = Arg(args, "-ds29r01BakeRoot") ?? "Build/Design/29R01/bake_kp";
            var meta = DS29R01ProjectionBaker.LoadMeta();
            if (meta.kstar.Length != 1 || meta.kstar[0].key != "a45") throw new InvalidOperationException("焼き込みの入力は 45° だけのはずです。");
            var k = meta.kstar[0];
            if (!k.gwb.StartsWith("Unity/")) throw new InvalidOperationException("K* の .gwb はリポジトリの根からの Unity/… のはずです: " + k.gwb);

            string sceneBefore = AF28ProjectionBakerSha(DS27Formation.ScenePath);
            EditorSceneManager.OpenScene(DS27Formation.ScenePath, OpenSceneMode.Single);
            var roots = EditorSceneManager.GetActiveScene().GetRootGameObjects();
            var pl27 = roots.Select(g => g.GetComponent<DS27KeyposePlayer>()).First(x => x != null);
            if (pl27.transform.localToWorldMatrix != Matrix4x4.identity) throw new InvalidOperationException("設計27 の主役波の変換が単位行列ではありません。");
            pl27.gameObject.SetActive(false);
            var camT = GameObject.Find("DS27 カメラ").transform.Find("DS27 painting");
            if (camT == null) throw new InvalidOperationException("DS27 painting のカメラがありません。");
            var cam = camT.GetComponent<Camera>();

            var go = new GameObject("DS29R01 K*′（焼き込み用。メモリの上だけ）");
            go.AddComponent<MeshFilter>();
            go.AddComponent<MeshRenderer>();
            var km = go.AddComponent<AF26KStarMesh>();
            km.dataPath = k.gwb.Substring("Unity/".Length);
            var mesh = km.EnsureLoaded();
            if (mesh.vertexCount != 96000 || km.nu != k.nu || km.nv != k.nv) throw new InvalidOperationException("K*′ の格子が入力と違います: " + mesh.vertexCount);
            AF28NprWave.ApplyWarp(mesh, km.nu, km.nv, k.uWarp, k.vWarp);   // 焼き込み用 UV（UV3）
            var r01 = DS29R01ProjectionBaker.Bake(meta, k, mesh, cam, "r01", "");
            var r28 = DS29R01ProjectionBaker.Bake(meta, k, mesh, cam, "rule28", "_rule28");
            string sceneAfter = AF28ProjectionBakerSha(DS27Formation.ScenePath);
            if (sceneBefore != sceneAfter) throw new InvalidOperationException("設計27 の場面のファイルが変わりました。");
            File.WriteAllText(DS29R01ProjectionBaker.BuildRoot + "/ds29r01_bake_entry.json", JsonUtility.ToJson(new EntryReport
            {
                root = DS29R01ProjectionBaker.BuildRoot, gwb = k.gwb, gwbSha256 = r01.gwbSha256, camera = "DS27 painting（" + DS27Formation.ScenePath + "、保存しない）",
                cameraPosition = cam.transform.position, cameraForward = cam.transform.forward, fov = cam.fieldOfView, near = cam.nearClipPlane, far = cam.farClipPlane,
                sceneSha256 = sceneAfter, r01Direct = r01.direct, r01Empty = r01.emptyAfterFill, r01NotRasterised = r01.notRasterised, rule28Empty = r28.emptyAfterFill,
                r01Sdf = r01.outSdf, r01SdfSha256 = r01.outSdfSha256, warp = r01.outWarp, warpSha256 = r01.outWarpSha256, utc = DateTime.UtcNow.ToString("O")
            }, true));
            Debug.Log("DS29R01_BAKE_ALL_DONE direct=" + r01.direct + " empty=" + r01.emptyAfterFill);
        }

        static string AF28ProjectionBakerSha(string p) => GreatWave.ArtFirst.EditorTools.AF28ProjectionBaker.Sha(p);

        [Serializable] class EntryReport
        {
            public string root, gwb, gwbSha256, camera, sceneSha256, r01Sdf, r01SdfSha256, warp, warpSha256, utc;
            public Vector3 cameraPosition, cameraForward; public float fov, near, far;
            public long r01Direct, r01Empty, r01NotRasterised, rule28Empty;
        }
    }
}
