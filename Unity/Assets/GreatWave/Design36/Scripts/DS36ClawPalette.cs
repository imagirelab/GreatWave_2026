using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using GreatWave.Design27;
using GreatWave.Design34;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design36
{
    // 設計36：爪の層（設計34 の DS34ClawPlayer の結合メッシュ）へ限定色を当てる。
    //   ・頂点の UV0 = t*（tStarSeconds、既定 12 s → コマ 360）の爪の頂点を paintingCamera で写したビューポートの位置（0〜1）。
    //   ・頂点の UV1.x = その爪の一覧の色区の影の色（ds36_claw_palette.json の shadow_class：0 白、1 淡い水色、2 藍中、3 藍濃）。
    //   ・2 つの材質（部分メッシュ 0 上面・白の円、1 縁の側面と下面）を DS36 Claw Palette に替え、原画の色区の符号付き距離の表を渡す。
    //   ・調色板の値は palette（主役波の材質から写す。DS36Render が渡す）。
    // 頂点のコマの差し替え（DS34ClawPlayer.ApplyT）は SetVertices だけなので、ここで足した UV はそのまま残る。
    // 読み込むときに表の SHA-256 を確かめる（ds36_claw_palette.json の label_sdf.sha256）。
    [DefaultExecutionOrder(65)]
    public class DS36ClawPalette : MonoBehaviour
    {
        public DS34ClawPlayer claws;
        public Camera paintingCamera;
        [Tooltip("爪の一覧の色区（Unity プロジェクトからの相対パスか絶対パス）")]
        public string palettePath = "Build/Design/36/palette/prep/ds36_claw_palette.json";
        public float tStarSeconds = 12f;
        [Tooltip("原画視点の描画の縦横比（表示フレーム 1920×1080）")]
        public float targetAspect = 1920f / 1080f;
        public float AspectAtApply { get; private set; }
        public Color white = new Color(0.97255f, 0.95294f, 0.87451f, 1f);
        public Color mizuiro = new Color(0.77647f, 0.84314f, 0.79608f, 1f);
        public Color aiMid = new Color(0.17255f, 0.41176f, 0.57647f, 1f);
        public Color aiDark = new Color(0.13725f, 0.25098f, 0.38039f, 1f);
        public bool faceFlip = false;
        public bool verifySha256 = true;

        public const string ShaderName = "GreatWave/Design36/DS36 Claw Palette";
        public const string TDepthShaderName = "GreatWave/Design36/DS36 Claw TDepth";
        [Tooltip("t* の見え方の表の大きさ（原画視点の描画の ID と同じ 3840×2160）")]
        public int tdepthW = 3840, tdepthH = 2160;
        [Tooltip("t* の奥行きの許し（m）＝ 絶対 + 相対 × 奥行き（ほかに表の 1 画素の奥行きの傾きの 1.5 倍）")]
        public float tdepthEpsAbs = 0.02f, tdepthEpsRel = 0.0005f;
        public bool TDepthFlip { get; private set; }
        public float[] TDepthMatchFrac { get; private set; }
        public float[] TDepthRange { get; private set; }
        RenderTexture tdepth;
        public bool Applied { get; private set; }
        public int TStarFrame { get; private set; }
        public string LabelSdfSha256 { get; private set; } = "";
        public string PaletteSha256 { get; private set; } = "";
        public int[] ShadowClassCounts { get; } = new int[4];
        public int ClawsWithoutEntry { get; private set; }
        public int VerticesOffscreenAtTStar { get; private set; }
        public float[] ShadowClassPerClaw { get; private set; }

        Texture2D sdf;
        Material matTop, matSide;

        public void Apply()
        {
            if (Applied) return;
            if (claws == null) claws = GetComponent<DS34ClawPlayer>();
            if (claws == null) throw new InvalidOperationException("DS34ClawPlayer がありません");
            if (paintingCamera == null) throw new InvalidOperationException("原画視点のカメラがありません");
            claws.Load();
            var pp = Path.GetFullPath(palettePath);
            var pb = File.ReadAllBytes(pp);
            PaletteSha256 = Sha(pb);
            var jo = DS27Json.AsObj(DS27Json.Parse(System.Text.Encoding.UTF8.GetString(pb)), "claw_palette");
            if (DS27Json.Text(jo, "schema") != "GreatWave.DS36.claw_palette/1") throw new InvalidDataException("爪の色区の書式ではありません: " + pp);
            var ls = DS27Json.AsObj(DS27Json.Get(jo, "label_sdf"), "label_sdf");
            int w = (int)DS27Json.Num(ls, "width"), h = (int)DS27Json.Num(ls, "height");
            float lv = (float)DS27Json.Num(ls, "levels_per_px");
            var sp = Path.Combine(Path.GetDirectoryName(pp), DS27Json.Text(ls, "file"));
            var sb = File.ReadAllBytes(sp);
            if (sb.Length != w * h * 4) throw new InvalidDataException("色区の表の大きさが違います: " + sb.Length);
            LabelSdfSha256 = Sha(sb);
            if (verifySha256 && LabelSdfSha256 != DS27Json.Text(ls, "sha256")) throw new InvalidDataException("色区の表の SHA-256 が JSON と違います");
            sdf = new Texture2D(w, h, TextureFormat.RGBA32, false, true)
            {
                name = "DS36 原画の色区の符号付き距離", wrapMode = TextureWrapMode.Clamp, filterMode = FilterMode.Bilinear, anisoLevel = 0, hideFlags = HideFlags.DontSave
            };
            sdf.LoadRawTextureData(sb);
            sdf.Apply(false, true);

            var cls = new Dictionary<string, int>();
            foreach (var o in (List<object>)DS27Json.Get(jo, "claws"))
            {
                var c = DS27Json.AsObj(o, "claw");
                cls[DS27Json.Text(c, "id")] = (int)DS27Json.Num(c, "shadow_class");
            }

            // t* のコマ（DS34ClawPlayer.FrameOf と同じ丸め）
            TStarFrame = DS34ClawPlayer.FrameOf(tStarSeconds, claws.Hz, claws.Frames);
            int n = claws.VertexCount;
            var uvP = new Vector2[n];
            var sh = new Vector2[n];
            ShadowClassPerClaw = new float[claws.ClawCount];
            int off = 0;
            // 原画視点の描画と同じ縦横比（1920×1080）で写す。batchmode の Editor ではカメラの aspect が画面の既定のままのことがあり、
            // 描画（CaptureRaw が aspect = 幅/高さ にする）とずれる
            float prevAspect = paintingCamera.aspect;
            AspectAtApply = prevAspect;
            paintingCamera.aspect = targetAspect;
            for (int ci = 0; ci < claws.ClawCount; ci++)
            {
                int k = 1;
                if (cls.TryGetValue(claws.ClawIds[ci], out int v)) k = v; else ClawsWithoutEntry++;
                ShadowClassCounts[Mathf.Clamp(k, 0, 3)]++;
                ShadowClassPerClaw[ci] = k;
                for (int j = 0; j < claws.VertCount[ci]; j++)
                {
                    int vi = claws.VertOffset[ci] + j;
                    var p = claws.FrameVertex(TStarFrame, vi);
                    var vp = paintingCamera.WorldToViewportPoint(p);
                    if (vp.x < 0 || vp.x > 1 || vp.y < 0 || vp.y > 1 || vp.z <= 0) off++;
                    uvP[vi] = new Vector2(vp.x, vp.y);
                    sh[vi] = new Vector2(k, vp.z);        // y = t* の原画視点の目の奥行き（m）
                }
            }
            VerticesOffscreenAtTStar = off;
            var mesh = claws.GetComponent<MeshFilter>().sharedMesh;
            mesh.SetUVs(0, uvP);
            mesh.SetUVs(1, sh);
            // t* の見え方の表：t* のコマの爪だけを原画視点のカメラで描いた目の奥行き（最も手前）。面の断片の t* の奥行きがこの表と同じなら
            // 「t* に原画のカメラから見える面」（原画の色区を投影で塗る）、奥なら「隠れた面」（上面は白、縁の側面と下面は一覧の影の色）
            RenderTDepth(mesh, uvP, sh);
            paintingCamera.aspect = prevAspect;

            var shd = Shader.Find(ShaderName);
            if (shd == null) throw new InvalidOperationException("シェーダーがありません: " + ShaderName);
            matTop = Make(shd, "DS36 爪 上面・白の円", 0f, w, h, lv);
            matSide = Make(shd, "DS36 爪 縁の側面と下面", 1f, w, h, lv);
            var r = claws.GetComponent<MeshRenderer>();
            r.sharedMaterials = new[] { matTop, matSide };
            r.shadowCastingMode = ShadowCastingMode.Off; r.receiveShadows = false;
            Applied = true;
        }

        void RenderTDepth(Mesh mesh, Vector2[] uvP, Vector2[] sh)
        {
            double tPrev = double.IsNaN(claws.AppliedT) ? 0.0 : claws.AppliedT;
            claws.ApplyT(TStarFrame / (double)claws.Hz);
            var dsh = Shader.Find(TDepthShaderName);
            if (dsh == null) throw new InvalidOperationException("シェーダーがありません: " + TDepthShaderName);
            var dm = new Material(dsh) { hideFlags = HideFlags.DontSave };
            tdepth = new RenderTexture(tdepthW, tdepthH, 24, RenderTextureFormat.RFloat, RenderTextureReadWrite.Linear)
            { name = "DS36 爪の t* の奥行き", filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp, hideFlags = HideFlags.DontSave };
            tdepth.Create();
            var cb = new CommandBuffer { name = "DS36 爪の t* の奥行き" };
            cb.SetRenderTarget(tdepth);
            cb.ClearRenderTarget(true, true, new Color(1e9f, 0, 0, 0));
            var proj = Matrix4x4.Perspective(paintingCamera.fieldOfView, targetAspect, paintingCamera.nearClipPlane, paintingCamera.farClipPlane);
            cb.SetViewProjectionMatrices(paintingCamera.worldToCameraMatrix, proj);
            for (int sm = 0; sm < mesh.subMeshCount; sm++) cb.DrawMesh(mesh, Matrix4x4.identity, dm, sm, 0);
            Graphics.ExecuteCommandBuffer(cb);
            cb.Release();
            // 読み戻して向き（v の上下）を決める：t* の頂点の奥行きと表の値が合う割合が大きい方
            var prevRt = RenderTexture.active;
            RenderTexture.active = tdepth;
            var tex = new Texture2D(tdepthW, tdepthH, TextureFormat.RFloat, false, true);
            tex.ReadPixels(new Rect(0, 0, tdepthW, tdepthH), 0, 0);
            tex.Apply();
            RenderTexture.active = prevRt;
            var d = tex.GetRawTextureData<float>();
            int[] ok = new int[2]; int nv = 0;
            for (int i = 0; i < uvP.Length; i += 7)
            {
                nv++;
                for (int f = 0; f < 2; f++)
                {
                    float u = uvP[i].x, v = f == 0 ? uvP[i].y : 1f - uvP[i].y;
                    int x = Mathf.Clamp((int)(u * tdepthW), 0, tdepthW - 1), y = Mathf.Clamp((int)(v * tdepthH), 0, tdepthH - 1);
                    float z = sh[i].y, dz = d[y * tdepthW + x];
                    if (Mathf.Abs(dz - z) < 0.05f + 0.002f * z) ok[f]++;
                }
            }
            TDepthFlip = ok[1] > ok[0];
            TDepthMatchFrac = new[] { ok[0] / (float)Math.Max(1, nv), ok[1] / (float)Math.Max(1, nv) };
            float zmin = float.MaxValue, zmax = 0;
            foreach (var q in sh) { zmin = Mathf.Min(zmin, q.y); zmax = Mathf.Max(zmax, q.y); }
            TDepthRange = new[] { zmin, zmax };
            if (Application.isPlaying) Destroy(tex); else DestroyImmediate(tex);
            if (Application.isPlaying) Destroy(dm); else DestroyImmediate(dm);
            claws.ApplyT(tPrev);
        }

        Material Make(Shader shd, string nm, float kind, int w, int h, float lv)
        {
            var m = new Material(shd) { name = nm, hideFlags = HideFlags.DontSave, enableInstancing = true };
            m.SetTexture("_LabelSdf", sdf);
            m.SetColor("_White", white); m.SetColor("_Mizuiro", mizuiro); m.SetColor("_AiMid", aiMid); m.SetColor("_AiDark", aiDark);
            m.SetFloat("_EncodeLevels", lv);
            m.SetVector("_LabelPx", new Vector4(w, h, 0, 0));
            m.SetFloat("_FaceKind", kind);
            m.SetFloat("_FaceFlip", faceFlip ? 1f : 0f);
            m.SetTexture("_TDepth", tdepth);
            m.SetFloat("_TDepthFlip", TDepthFlip ? 1f : 0f);
            m.SetVector("_TDepthPx", new Vector4(tdepthW, tdepthH, 0, 0));
            m.SetVector("_TDepthEps", new Vector4(tdepthEpsAbs, tdepthEpsRel, 0, 0));
            return m;
        }

        public void SetFaceFlip(bool on)
        {
            faceFlip = on;
            if (matTop != null) matTop.SetFloat("_FaceFlip", on ? 1f : 0f);
            if (matSide != null) matSide.SetFloat("_FaceFlip", on ? 1f : 0f);
        }

        void Start()
        {
            if (Application.isPlaying) Apply();
        }

        void OnDestroy() { Release(); }

        public void Release()
        {
            if (matTop != null) { if (Application.isPlaying) Destroy(matTop); else DestroyImmediate(matTop); matTop = null; }
            if (matSide != null) { if (Application.isPlaying) Destroy(matSide); else DestroyImmediate(matSide); matSide = null; }
            if (sdf != null) { if (Application.isPlaying) Destroy(sdf); else DestroyImmediate(sdf); sdf = null; }
            if (tdepth != null) { tdepth.Release(); if (Application.isPlaying) Destroy(tdepth); else DestroyImmediate(tdepth); tdepth = null; }
            Applied = false;
        }

        static string Sha(byte[] b)
        {
            using (var s = SHA256.Create()) return BitConverter.ToString(s.ComputeHash(b)).Replace("-", "").ToLowerInvariant();
        }
    }
}
