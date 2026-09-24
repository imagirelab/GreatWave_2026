using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Editor
{
    public static class M0CalibrationVerifier
    {
        const string ModelPath = "Assets/GreatWave/Art/Calibration/calibration.fbx";
        const float Tolerance = .001f;
        static bool Near(Vector3 a, Vector3 b) => Vector3.Distance(a, b) <= Tolerance;

        [MenuItem("GreatWave/07 校正モデルを読み込んで測定")]
        public static void ImportAndMeasure()
        {
            AssetDatabase.ImportAsset(ModelPath, ImportAssetOptions.ForceSynchronousImport);
            var importer = (ModelImporter)AssetImporter.GetAtPath(ModelPath);
            importer.globalScale = 1;
            importer.useFileScale = true;
            importer.bakeAxisConversion = false;
            importer.importAnimation = false;
            importer.isReadable = true;
            importer.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
            importer.SaveAndReimport();
            var scene = EditorSceneManager.OpenScene(M0BaselineBuilder.ScenePath);
            var previous = GameObject.Find("Blender calibration");
            if (previous != null) UnityEngine.Object.DestroyImmediate(previous);
            var root = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(ModelPath));
            root.name = "Blender calibration";
            root.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            root.transform.localScale = Vector3.one;
            var rows = new List<Measurement>();
            foreach (var meshFilter in root.GetComponentsInChildren<MeshFilter>())
            {
                var vertices = meshFilter.sharedMesh.vertices.Select(meshFilter.transform.TransformPoint).ToArray();
                var bounds = new Bounds(vertices[0], Vector3.zero);
                foreach (var vertex in vertices) bounds.Encapsulate(vertex);
                var normals = meshFilter.sharedMesh.normals;
                bool outward = normals.Length == vertices.Length;
                for (int i = 0; i < normals.Length && outward; i++)
                    outward &= Vector3.Dot(meshFilter.transform.TransformDirection(normals[i]), vertices[i] - bounds.center) > 0;
                rows.Add(new Measurement { name = meshFilter.name, center = bounds.center, size = bounds.size,
                    pivot = meshFilter.transform.position, vertices = vertices.Length, outwardNormals = outward });
            }
            Vector3 Center(string name) => rows.Single(row => row.name == name).center;
            var x = Center("Axis_PosX_2m");
            var y = Center("Axis_PosY_3m");
            var z = Center("Axis_PosZ_4m");
            var cube = rows.Single(row => row.name == "Calibration_Cube_1m");
            var report = new Report { unity = Application.unityVersion, globalScale = importer.globalScale,
                useFileScale = importer.useFileScale, fileScale = importer.fileScale, bakeAxisConversion = importer.bakeAxisConversion,
                toleranceM = Tolerance, measurements = rows.ToArray(), sourceXInUnity = x / 2,
                sourceYInUnity = y / 3, sourceZInUnity = z / 4,
                orderedTripleProduct = Vector3.Dot(Vector3.Cross(x, y), z),
                cubeUnit = Near(cube.size, Vector3.one), axesLengths = Mathf.Abs(x.magnitude - 2) < Tolerance
                    && Mathf.Abs(y.magnitude - 3) < Tolerance && Mathf.Abs(z.magnitude - 4) < Tolerance,
                axesOrthogonal = Mathf.Abs(Vector3.Dot(x, y)) < Tolerance && Mathf.Abs(Vector3.Dot(y, z)) < Tolerance
                    && Mathf.Abs(Vector3.Dot(z, x)) < Tolerance,
                upPreserved = Near(z / 4, Vector3.up), negativeXPreserved = Near(Center("Axis_NegX_1p5m"), -.75f * x),
                asymmetricPointPreserved = Near(Center("Handedness_P123"), .5f * x + (2f / 3) * y + .75f * z),
                cubeBottomAtOrigin = Near(cube.center, .125f * z), allPivotsAtOrigin = rows.All(row => Near(row.pivot, Vector3.zero)),
                noUnexpectedDistortion = Mathf.Abs(Mathf.Abs(Vector3.Dot(Vector3.Cross(x, y), z)) - 24) < Tolerance,
                expectedAxisMapping = Near(x / 2, Vector3.left) && Near(y / 3, Vector3.back) && Near(z / 4, Vector3.up),
                expectedHandedness = Mathf.Abs(Vector3.Dot(Vector3.Cross(x, y), z) + 24) < Tolerance,
                normalsOutward = rows.All(row => row.outwardNormals),
                hmdStatus = "未検証", visualNormalsStatus = "10の実画像で確認" };
            report.passed = rows.Count == 6 && report.cubeUnit && report.axesLengths && report.axesOrthogonal
                && report.upPreserved && report.negativeXPreserved && report.asymmetricPointPreserved
                && report.cubeBottomAtOrigin && report.allPivotsAtOrigin && report.noUnexpectedDistortion
                && report.expectedAxisMapping && report.expectedHandedness && report.normalsOutward;
            File.WriteAllText("../Docs/Evidence/M0/07_unity_import.json", JsonUtility.ToJson(report, true));
            if (!report.passed) throw new InvalidOperationException("07の単位・軸検証が不合格。実測JSONを確認してください。");
            // 数値検証後だけ表示位置を移し、実測時の原点条件と混同しない。
            root.transform.position = new Vector3(-5, .15f, 8);
            EditorSceneManager.SaveScene(scene);
            AssetDatabase.SaveAssets();
            Debug.Log("M0_STEP07_PASS: measured basis X=" + report.sourceXInUnity + " Y=" + report.sourceYInUnity
                + " Z=" + report.sourceZInUnity + " triple=" + report.orderedTripleProduct);
        }

        [Serializable] class Measurement { public string name; public Vector3 center, size, pivot; public int vertices; public bool outwardNormals; }
        [Serializable] class Report
        {
            public string unity, hmdStatus, visualNormalsStatus;
            public float globalScale, fileScale, toleranceM, orderedTripleProduct;
            public bool useFileScale, bakeAxisConversion, cubeUnit, axesLengths, axesOrthogonal, upPreserved,
                negativeXPreserved, asymmetricPointPreserved, cubeBottomAtOrigin, allPivotsAtOrigin, noUnexpectedDistortion,
                expectedAxisMapping, expectedHandedness, normalsOutward, passed;
            public Vector3 sourceXInUnity, sourceYInUnity, sourceZInUnity;
            public Measurement[] measurements;
        }
    }
}
