using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.Design30;
using GreatWave.Design47;
using GreatWave.Design48.EditorTools;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace GreatWave.Design49.EditorTools
{
    // 設計49：体験の場面 DS49_Sound.unity を作る（PC の Editor の batchmode。HMD 実機ではない）。
    //   1) 音の WAV（ds49_synth.py が numpy で合成）の読み込みの設定を、PCM・読み込み時に展開・元の標本化の周波数のままにする（Vorbis の前置きの遅れを入れない）。
    //   2) 設計48 の DS48_Wake.unity（体験の一本の場面）を開く（保存しない）。
    //   3) 「DS49 音」（DS49Sound）と 4 つの AudioSource（地鳴り・t* の音・風・きしみ。3D、ドップラーなし）を足す。聞き手は設計47 が HMD Camera に置いた AudioListener。
    //   4) DS49_Sound.unity として別に保存する。守るファイル（前の番号の場面・部品・表）は前後で SHA-256 を比べる。
    public static class DS49SoundBuild
    {
        public const string Scene48 = DS48WakeBuild.Scene48;
        public const string Scene49 = "Assets/GreatWave/Design49/Scenes/DS49_Sound.unity";
        public const string SoundJson = "Assets/GreatWave/Design49/Data/ds49_sound.json";
        public const string AudioDir = "Assets/GreatWave/Design49/Audio";
        public const string RootName = "DS49 音（波・木船・風）";

        public static string[] Protected => DS48WakeBuild.Protected.Concat(new[] {
            Scene48, DS48WakeBuild.WakeJson, DS48WakeBuild.ShaderPath, DS48WakeBuild.MatPath,
            "Assets/GreatWave/Design48/Scripts/DS48Wake.cs", "Assets/GreatWave/Design48/Scripts/DS48Recorder.cs",
            "Assets/GreatWave/Design48/Editor/DS48WakeBuild.cs", "Assets/GreatWave/Design48/Editor/DS48WakePlay.cs" }).Distinct().ToArray();

        public static string FileSha(string p) => DS48WakeBuild.FileSha(p);

        static void ImportSettings(string path)
        {
            var imp = AssetImporter.GetAtPath(path) as AudioImporter;
            if (imp == null) throw new InvalidOperationException("音の読み込みがありません: " + path);
            var s = imp.defaultSampleSettings;
            s.loadType = AudioClipLoadType.DecompressOnLoad;
            s.compressionFormat = AudioCompressionFormat.PCM;
            s.sampleRateSetting = AudioSampleRateSetting.PreserveSampleRate;
            imp.defaultSampleSettings = s;
            imp.forceToMono = true;
            imp.loadInBackground = false;
            imp.SaveAndReimport();
        }

        public static string Build()
        {
            AssetDatabase.Refresh();
            var jsonAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(SoundJson);
            var cfg = DS49Config.Parse(jsonAsset.text);
            var clips = new List<AudioClip>();
            foreach (var t in cfg.tracks)
            {
                var p = AudioDir + "/" + t.clip;
                ImportSettings(p);
                var c = AssetDatabase.LoadAssetAtPath<AudioClip>(p);
                if (c == null) throw new InvalidOperationException("AudioClip がありません: " + p);
                if (c.frequency != cfg.sampleRate) throw new InvalidOperationException("標本化の周波数が違います: " + p + " " + c.frequency);
                clips.Add(c);
            }

            var scene = EditorSceneManager.OpenScene(Scene48, OpenSceneMode.Single);
            var flow = UnityEngine.Object.FindFirstObjectByType<DS47Flow>();
            if (flow == null) throw new InvalidOperationException("DS47Flow がありません");
            var listeners = UnityEngine.Object.FindObjectsByType<AudioListener>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            var lis = flow.hmdCamera.GetComponent<AudioListener>();
            if (lis == null) throw new InvalidOperationException("HMD Camera に AudioListener がありません（設計47 が置くはず）");
            int enabledOthers = listeners.Count(l => l != lis && l.enabled);
            if (enabledOthers > 0) throw new InvalidOperationException("HMD Camera のほかに有効な AudioListener があります: " + enabledOthers);

            var root = new GameObject(RootName);
            root.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            var snd = root.AddComponent<DS49Sound>();
            snd.configJson = jsonAsset; snd.clock = flow.clock; snd.flow = flow; snd.events = flow.bus.events; snd.listener = lis;
            for (int i = 0; i < cfg.tracks.Length; i++)
            {
                var t = cfg.tracks[i];
                var go = new GameObject("DS49 音：" + t.nameJa + "（" + t.key + "）");
                go.transform.SetParent(root.transform, false);
                var src = go.AddComponent<AudioSource>();
                src.clip = clips[i]; src.playOnAwake = false; src.loop = t.loop; src.volume = 0f;
                src.spatialBlend = 1f; src.dopplerLevel = cfg.sync.dopplerLevel; src.rolloffMode = AudioRolloffMode.Logarithmic;
                src.minDistance = t.minDistanceM; src.maxDistance = t.maxDistanceM; src.spread = t.spreadDeg; src.priority = 64 + i;
                snd.sources.Add(src);
            }
            // 地鳴りの位置：主役波のシート（hero）の描画。t* の音の位置：爪の描画
            var hero = flow.bus.playback.sheets.FirstOrDefault(s => s != null && s.sheetName == "hero");
            if (hero == null) throw new InvalidOperationException("主役波のシート（hero）がありません");
            snd.heroRenderers = hero.GetComponentsInChildren<Renderer>(true).Where(r => r != null && r != hero.outline).ToList();
            if (flow.bus.claws != null) snd.crestRenderers = flow.bus.claws.GetComponentsInChildren<Renderer>(true).ToList();

            EditorSceneManager.MarkSceneDirty(scene);
            Directory.CreateDirectory(Path.GetDirectoryName(Scene49));
            if (!EditorSceneManager.SaveScene(scene, Scene49, true)) throw new InvalidOperationException("DS49_Sound.unity を保存できません");
            AssetDatabase.SaveAssets();
            var sb = new StringBuilder();
            sb.Append("\"scene\":\"").Append(Scene49).Append("\",\"sceneSha256\":\"").Append(FileSha(Scene49)).Append('"');
            sb.Append(",\"listener\":\"").Append(lis.gameObject.name).Append("\",\"listenersInScene\":").Append(listeners.Length).Append(",\"listenersEnabled\":").Append(listeners.Count(l => l.enabled));
            sb.Append(",\"heroRenderers\":").Append(snd.heroRenderers.Count).Append(",\"crestRenderers\":").Append(snd.crestRenderers.Count);
            sb.Append(",\"clips\":[").Append(string.Join(",", clips.Select(c => "{\"name\":\"" + c.name + "\",\"samples\":" + c.samples + ",\"frequency\":" + c.frequency + ",\"channels\":" + c.channels + ",\"loadType\":\"" + c.loadType + "\",\"sha256\":\"" + FileSha(AssetDatabase.GetAssetPath(c)) + "\"}"))).Append(']');
            sb.Append(",\"outputSampleRate\":").Append(AudioSettings.outputSampleRate).Append(",\"speakerMode\":\"").Append(AudioSettings.speakerMode).Append('"');
            return sb.ToString();
        }
    }
}
