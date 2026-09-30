using System;
using System.Collections.Generic;
using System.Linq;
using GreatWave.Design30;
using GreatWave.Design31;
using UnityEngine;

namespace GreatWave.Design39
{
    // 設計39：紙の地（①）・摺りのむら（②）・小飛沫（③）を一つずつ入切する。既定は全部切（評価と原画比較は切って行う）。
    //   ①②：面の上に掛け算で重ねる材質（DS39 Paper Keypose・DS39 Paper Mesh）。
    //     ・keypose のシート（主役波・near・far）：面のレンダラーの材質の配列の後ろに足す（同じレンダラーなので DS30SheetPlayer の
    //       MaterialPropertyBlock の keypose の値をそのまま読む）。シートごとに材質を写し、t* の 4 層・重み・枠の原点を入れる（Build）。
    //     ・ほかのメッシュ（富士・船・平らな海・継ぎ目の幕・空のドームなど）：同じメッシュを共有する子のレンダラー（部分メッシュの数だけ材質）を作る。
    //       空のドームは向きの座標（無限遠）、ほかは物体に固定の座標。
    //     ・重ねないもの：外殻線（線は藍のまま）、爪（CPU で毎コマ作り直す世界の座標のメッシュで、面の座標がない。記録の限界）、飛沫。
    //   ③：設計31 の飛沫の子（ds39_spray_dense.py）を、2 つ目の DS31InstancedParticles で描く（Play モードは drawInPlayMode、採取はカメラの CommandBuffer）。
    //   切ったとき：足した材質を配列から外し、子のレンダラーを切る → 描画は設計38 と同じ。
    [DefaultExecutionOrder(45)]
    public class DS39PaperLayers : MonoBehaviour
    {
        public DS30SinglePlayback playback;
        [Tooltip("紙の地（keypose のシート用、写して使う）")] public Material paperKeypose;
        [Tooltip("摺りのむら（keypose のシート用、写して使う）")] public Material muraKeypose;
        [Tooltip("紙の地（メッシュ用、写して使う）")] public Material paperMesh;
        [Tooltip("摺りのむら（メッシュ用、写して使う）")] public Material muraMesh;
        public DS31InstancedParticles denseSpray;
        public GameObject[] meshRoots;
        public string skyDomeName = "AF27 空のドーム";
        public float skyRadius = 100f;
        public float paperAmp = 0.03f, muraAmp = 0.04f;
        public float tStar = 12f;
        public bool paperOn, muraOn, sprayOn;

        [Serializable] public class SheetRest { public string sheet; public int[] slices; public float[] weights; public float[] origin; public int subMeshes, baseMaterials; }
        [Serializable] public class MeshTarget { public string name, shader, coord; public int subMeshes; }

        public List<SheetRest> Rest { get; } = new List<SheetRest>();
        public List<MeshTarget> MeshTargets { get; } = new List<MeshTarget>();
        public bool Built { get; private set; }

        readonly Dictionary<Renderer, (Material paper, Material mura)> sheetMats = new Dictionary<Renderer, (Material, Material)>();
        readonly Dictionary<Renderer, Material[]> sheetBase = new Dictionary<Renderer, Material[]>();
        readonly List<MeshRenderer> paperChildren = new List<MeshRenderer>(), muraChildren = new List<MeshRenderer>();
        readonly List<UnityEngine.Object> made = new List<UnityEngine.Object>();

        static readonly string[] SkipShaderWords = { "Outline", "Depth", "Claw", "Coord", "Spray", "DS39" };

        /// <summary>シートの t* の値を読み、材質と子のレンダラーを作る（シートを読み込んだ後。時刻を t* へ動かすので、呼んだ側が時刻を戻す）。</summary>
        public void Build()
        {
            if (Built) return;
            if (playback == null) playback = FindAnyObjectByType<DS30SinglePlayback>(FindObjectsInactive.Include);
            playback.Seek(tStar);
            var sheetRenderers = new HashSet<Renderer>();
            foreach (var s in playback.sheets)
            {
                if (s == null) continue;
                var r = s.Surface;
                if (r == null) continue;
                sheetRenderers.Add(r);
                if (s.outline != null) sheetRenderers.Add(s.outline);
                var sl = s.Slices; var wt = s.WeightsNow; var o = s.AppliedOrigin;
                var smf = r.GetComponent<MeshFilter>();
                var rec = new SheetRest { sheet = s.sheetName, slices = sl.ToArray(), weights = wt.ToArray(), origin = new[] { o.x, o.y, o.z },
                    subMeshes = smf != null && smf.sharedMesh != null ? smf.sharedMesh.subMeshCount : -1, baseMaterials = r.sharedMaterials.Length };
                Rest.Add(rec);
                var mp = Make(paperKeypose, "DS39 紙の地 " + s.sheetName); var mm = Make(muraKeypose, "DS39 摺りのむら " + s.sheetName);
                foreach (var m in new[] { mp, mm })
                {
                    m.SetVector("_DS39RestSlices", new Vector4(sl[0], sl[1], sl[2], sl[3]));
                    m.SetVector("_DS39RestWeights", new Vector4(wt[0], wt[1], wt[2], wt[3]));
                    m.SetVector("_DS39RestOrigin", new Vector4(o.x, o.y, o.z, 0));
                }
                mp.SetFloat("_DS39Mode", 0); mp.SetFloat("_DS39Amp", paperAmp);
                mm.SetFloat("_DS39Mode", 1); mm.SetFloat("_DS39Amp", muraAmp);
                sheetMats[r] = (mp, mm);
                sheetBase[r] = r.sharedMaterials;
            }
            var pm = Make(paperMesh, "DS39 紙の地 メッシュ"); pm.SetFloat("_DS39Mode", 0); pm.SetFloat("_DS39Amp", paperAmp); pm.SetFloat("_DS39CoordMode", 0);
            var mmesh = Make(muraMesh, "DS39 摺りのむら メッシュ"); mmesh.SetFloat("_DS39Mode", 1); mmesh.SetFloat("_DS39Amp", muraAmp); mmesh.SetFloat("_DS39CoordMode", 0);
            var ps = Make(paperMesh, "DS39 紙の地 空"); ps.SetFloat("_DS39Mode", 0); ps.SetFloat("_DS39Amp", paperAmp); ps.SetFloat("_DS39CoordMode", 1); ps.SetFloat("_DS39SkyRadius", skyRadius);
            var ms = Make(muraMesh, "DS39 摺りのむら 空"); ms.SetFloat("_DS39Mode", 1); ms.SetFloat("_DS39Amp", muraAmp); ms.SetFloat("_DS39CoordMode", 1); ms.SetFloat("_DS39SkyRadius", skyRadius);
            var roots = (meshRoots != null && meshRoots.Length > 0) ? meshRoots : gameObject.scene.GetRootGameObjects();
            var targets = new List<MeshRenderer>();
            foreach (var g in roots)
            {
                if (g == null) continue;
                foreach (var mr in g.GetComponentsInChildren<MeshRenderer>(true))
                {
                    if (sheetRenderers.Contains(mr) || targets.Contains(mr)) continue;
                    if (mr.GetComponent<DS31InstancedParticles>() != null) continue;
                    if (mr.GetComponent<Design34.DS34ClawPlayer>() != null) continue;
                    var mf = mr.GetComponent<MeshFilter>();
                    if (mf == null || mf.sharedMesh == null) continue;
                    var sh = mr.sharedMaterial != null && mr.sharedMaterial.shader != null ? mr.sharedMaterial.shader.name : "";
                    if (SkipShaderWords.Any(wd => sh.Contains(wd))) continue;
                    targets.Add(mr);
                }
            }
            foreach (var mr in targets)
            {
                var mf = mr.GetComponent<MeshFilter>();
                bool sky = mr.name == skyDomeName;
                int n = Mathf.Max(1, mf.sharedMesh.subMeshCount);
                MeshTargets.Add(new MeshTarget { name = mr.name, shader = mr.sharedMaterial != null ? mr.sharedMaterial.shader.name : "", coord = sky ? "空の向き" : "物体に固定", subMeshes = n });
                paperChildren.Add(Child(mr, mf, "DS39 紙の地", sky ? ps : pm, n));
                muraChildren.Add(Child(mr, mf, "DS39 摺りのむら", sky ? ms : mmesh, n));
            }
            Built = true;
            Apply();
        }

        Material Make(Material template, string name)
        {
            var m = new Material(template) { name = name, hideFlags = HideFlags.DontSave };
            made.Add(m);
            return m;
        }

        MeshRenderer Child(MeshRenderer src, MeshFilter mf, string label, Material m, int n)
        {
            var go = new GameObject(label + " " + src.name) { hideFlags = HideFlags.DontSave };
            go.layer = src.gameObject.layer;
            go.transform.SetParent(src.transform, false);
            var f = go.AddComponent<MeshFilter>(); f.sharedMesh = mf.sharedMesh;
            var r = go.AddComponent<MeshRenderer>();
            var arr = new Material[n]; for (int i = 0; i < n; i++) arr[i] = m;
            r.sharedMaterials = arr;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; r.receiveShadows = false;
            r.lightProbeUsage = UnityEngine.Rendering.LightProbeUsage.Off; r.reflectionProbeUsage = UnityEngine.Rendering.ReflectionProbeUsage.Off;
            r.motionVectorGenerationMode = MotionVectorGenerationMode.ForceNoMotion;
            r.enabled = false;
            made.Add(go);
            return r;
        }

        /// <summary>入切を適用する。子のレンダラーは親が見えるときだけ描く。</summary>
        public void Apply()
        {
            if (!Built) return;
            foreach (var kv in sheetMats)
            {
                var r = kv.Key;
                var list = new List<Material>(sheetBase[r]);
                if (paperOn) list.Add(kv.Value.paper);
                if (muraOn) list.Add(kv.Value.mura);
                r.sharedMaterials = list.ToArray();
            }
            foreach (var c in paperChildren) if (c != null) c.enabled = paperOn && ParentOn(c);
            foreach (var c in muraChildren) if (c != null) c.enabled = muraOn && ParentOn(c);
            if (denseSpray != null) denseSpray.drawInPlayMode = sprayOn;
        }

        static bool ParentOn(MeshRenderer c)
        {
            var p = c.transform.parent != null ? c.transform.parent.GetComponent<MeshRenderer>() : null;
            return p != null && p.enabled && p.gameObject.activeInHierarchy;
        }

        public void Set(bool paper, bool mura, bool spray)
        {
            paperOn = paper; muraOn = mura; sprayOn = spray;
            Apply();
        }

        void Start()
        {
            if (Application.isPlaying && playback != null && playback.sheets.Any(s => s != null && s.Loaded)) Build();
        }

        void LateUpdate()
        {
            if (Application.isPlaying && Built)
            {
                // 親の入切（原画の視点の場面の切り替えなど）に子を合わせる
                foreach (var c in paperChildren) if (c != null) c.enabled = paperOn && ParentOn(c);
                foreach (var c in muraChildren) if (c != null) c.enabled = muraOn && ParentOn(c);
            }
        }

        /// <summary>作った材質と子を消し、シートの材質を元に戻す（Editor の採取の後）。</summary>
        public void Teardown()
        {
            foreach (var kv in sheetBase) if (kv.Key != null) kv.Key.sharedMaterials = kv.Value;
            foreach (var o in made) if (o != null) { if (Application.isPlaying) Destroy(o); else DestroyImmediate(o); }
            made.Clear(); sheetMats.Clear(); sheetBase.Clear(); paperChildren.Clear(); muraChildren.Clear(); Rest.Clear(); MeshTargets.Clear();
            Built = false;
        }

        void OnDestroy() { Teardown(); }
    }
}
