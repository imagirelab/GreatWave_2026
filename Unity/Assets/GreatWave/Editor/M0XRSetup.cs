using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEditor.XR.OpenXR;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features;
using Unity.XR.CoreUtils;

namespace GreatWave.Editor
{
    public static class M0XRSetup
    {
        const string Loader = "UnityEngine.XR.OpenXR.OpenXRLoader";
        [MenuItem("GreatWave/08 OpenXRのPC準備")]
        public static void Configure()
        {
            Directory.CreateDirectory("Assets/XR/Settings");
            AssetDatabase.Refresh();
            if (!EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out XRGeneralSettingsPerBuildTarget perTarget))
            {
                perTarget = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
                AssetDatabase.CreateAsset(perTarget, "Assets/XR/Settings/XR General Settings.asset");
                EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey, perTarget, true);
            }
            if (perTarget.SettingsForBuildTarget(BuildTargetGroup.Standalone) == null)
                perTarget.CreateDefaultSettingsForBuildTarget(BuildTargetGroup.Standalone);
            var general = perTarget.SettingsForBuildTarget(BuildTargetGroup.Standalone);
            if (general.Manager == null) perTarget.CreateDefaultManagerSettingsForBuildTarget(BuildTargetGroup.Standalone);
            general.InitManagerOnStart = false;
            if (!XRPackageMetadataStore.AssignLoader(general.Manager, Loader, BuildTargetGroup.Standalone))
                throw new InvalidOperationException("OpenXR loaderを保存できませんでした。");
            if (OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Standalone) == null)
            {
                var package = XRPackageMetadataStore.GetAllPackageMetadata().First(p => p.metadata.packageId == "com.unity.xr.openxr");
                var settingsType = TypeCache.GetTypesDerivedFrom<ScriptableObject>().First(t => t.FullName == package.metadata.settingsType);
                var settingsAsset = ScriptableObject.CreateInstance(settingsType);
                AssetDatabase.CreateAsset(settingsAsset, "Assets/XR/Settings/OpenXR Package Settings.asset");
                package.PopulateNewSettingsInstance(settingsAsset);
                EditorUtility.SetDirty(settingsAsset);
            }
            var settings = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Standalone);
            if (settings == null) throw new InvalidOperationException("OpenXR設定が作成されませんでした。");
            settings.renderMode = OpenXRSettings.RenderMode.SinglePassInstanced;
            // 機器未定のため、特定メーカーのprofileを対応済みとして有効化しない。
            var player = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset")[0]);
            player.FindProperty("activeInputHandler").intValue = 1;
            player.ApplyModifiedPropertiesWithoutUndo();
            var scene = EditorSceneManager.OpenScene(M0BaselineBuilder.ScenePath);
            var camera = Camera.main;
            var origin = GameObject.Find("M0 XR Origin") ?? new GameObject("M0 XR Origin");
            var offset = GameObject.Find("Camera Floor Offset") ?? new GameObject("Camera Floor Offset");
            offset.transform.SetParent(origin.transform, false);
            camera.transform.SetParent(offset.transform, false);
            camera.transform.localPosition = Vector3.zero;
            camera.transform.localRotation = Quaternion.identity;
            var xrOrigin = origin.GetComponent<XROrigin>() ?? origin.AddComponent<XROrigin>();
            xrOrigin.Origin = origin;
            xrOrigin.CameraFloorOffsetObject = offset;
            xrOrigin.Camera = camera;
            xrOrigin.RequestedTrackingOriginMode = XROrigin.TrackingOriginMode.Device;
            xrOrigin.CameraYOffset = 1.2f;
            var pose = camera.GetComponent<TrackedPoseDriver>() ?? camera.gameObject.AddComponent<TrackedPoseDriver>();
            pose.trackingType = TrackedPoseDriver.TrackingType.RotationAndPosition;
            pose.updateType = TrackedPoseDriver.UpdateType.UpdateAndBeforeRender;
            pose.ignoreTrackingState = false;
            pose.positionInput = new InputActionProperty(new InputAction("HMD position", InputActionType.Value, "<XRHMD>/centerEyePosition", expectedControlType: "Vector3"));
            pose.rotationInput = new InputActionProperty(new InputAction("HMD rotation", InputActionType.Value, "<XRHMD>/centerEyeRotation", expectedControlType: "Quaternion"));
            pose.trackingStateInput = new InputActionProperty(new InputAction("HMD tracking state", InputActionType.Value, "<XRHMD>/trackingState", expectedControlType: "Integer"));
            pose.enabled = false;
            EditorUtility.SetDirty(perTarget);
            EditorUtility.SetDirty(general);
            EditorUtility.SetDirty(general.Manager);
            EditorUtility.SetDirty(settings);
            EditorSceneManager.SaveScene(scene);
            AssetDatabase.SaveAssets();
            Validate();
        }

        public static void Validate()
        {
            var general = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(BuildTargetGroup.Standalone);
            bool assigned = general != null && general.Manager != null && general.Manager.activeLoaders.Any(l => l is OpenXRLoader);
            var settings = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Standalone);
            var scene = EditorSceneManager.OpenScene(M0BaselineBuilder.ScenePath);
            var origin = UnityEngine.Object.FindFirstObjectByType<XROrigin>();
            var pose = Camera.main.GetComponent<TrackedPoseDriver>();
            var issues = new List<OpenXRFeature.ValidationRule>();
            if (assigned && settings != null) OpenXRProjectValidation.GetCurrentValidationIssues(issues, BuildTargetGroup.Standalone);
            var report = new Report { unity = Application.unityVersion, loaderAssigned = assigned,
                settingsPersisted = settings != null, automaticInitializationOff = general != null && !general.InitManagerOnStart,
                originConfigured = origin != null && origin.Camera == Camera.main && origin.CameraFloorOffsetObject != null,
                trackedPoseConfigured = pose != null && !pose.enabled && pose.positionInput.action.bindings.Count > 0
                    && pose.rotationInput.action.bindings.Count > 0 && pose.trackingStateInput.action.bindings.Count > 0,
                projectValidationErrors = issues.Count(i => i.error),
                issues = issues.Select(i => new Issue { message = i.message, error = i.error, fixHint = i.fixItMessage }).ToArray(),
                hmdStatus = "機器なし・実機入力と両眼表示は保留" };
            report.configurationPassed = report.loaderAssigned && report.settingsPersisted && report.automaticInitializationOff
                && report.originConfigured && report.trackedPoseConfigured;
            File.WriteAllText("../Docs/Evidence/M0/08_xr_configuration.json", JsonUtility.ToJson(report, true));
            if (!report.configurationPassed) throw new InvalidOperationException("08の設定の保存・再読込が不合格です。");
            Debug.Log("M0_STEP08_CONFIG_PASS: saved settings; validationErrors=" + report.projectValidationErrors + "; HMD未検証");
        }
        [Serializable] class Issue { public string message, fixHint; public bool error; }
        [Serializable] class Report
        {
            public string unity, hmdStatus;
            public bool loaderAssigned, settingsPersisted, automaticInitializationOff, originConfigured, trackedPoseConfigured, configurationPassed;
            public int projectValidationErrors;
            public Issue[] issues;
        }
    }
}
