using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using GreatWave.Design31;
using GreatWave.Design47;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design48
{
    // 設計48：試験だけの記録の部品（場面に保存しない。DS48WakePlay が Play の間だけ足す）。
    //   毎フレームの LateUpdate の最後（order 1000）に、操船の入力・速さ・旋回・泡と航跡の量を 1 行に記録する。
    //   1/30 s ごとに、追いかけのカメラ（船の斜め上から船と航跡を見下ろす。試験だけ）1280×720 と HMD Camera（座席の PC の視点）640×360 を JPG で書く（動画のコマ）。
    //   maskEvery コマごとに、2 つのカメラを 640×360（MSAA なし）で「全部」「航跡なし」「航跡なし・主役波なし」で描き（主役波の画素は毎回数える）、
    //   航跡が見えている画素（全部 ≠ 航跡なし）と主役波の画素（航跡なし ≠ 航跡なし・主役波なし）の重なりを数える（主役波の上に航跡が出ないことの検査）。
    [DefaultExecutionOrder(1000)]
    public class DS48Recorder : MonoBehaviour
    {
        public DS47Flow flow;
        public DS48Wake wake;
        public Camera chase;
        public string outDir;
        public List<Renderer> heroRenderers = new List<Renderer>();
        public List<DS31InstancedParticles> sprays = new List<DS31InstancedParticles>();
        public Func<string> extra;
        public int chaseW = 1280, chaseH = 720, hmdW = 640, hmdH = 360, maskW = 640, maskH = 360, jpgQuality = 90, msaa = 4, maskEvery = 3;
        public double captureEveryS = 1.0 / 30.0;
        public float chaseYawTauS = 1.5f;
        public Vector3 chaseOffset = new Vector3(16f, 28f, -4f);
        public Vector3 chaseLook = new Vector3(0f, 0f, -6f);
        public readonly StringBuilder csv = new StringBuilder();
        public readonly StringBuilder maskCsv = new StringBuilder();
        public int Frames { get; private set; }
        public int Captured { get; private set; }
        public double RenderMsTotal { get; private set; }
        double acc;
        int overlapSamples;
        float yawS = float.NaN;

        public const string Header = "frame,exp,wave,phase,paused,handed_over,steer_mode,in_thr,in_turn,in_stop,boat_x,boat_y,boat_z,boat_yaw,speed,yaw_rate,sv,sr,gate,emitting,samples,visible_verts,guard_hidden,overhang_hidden,outside_hidden,max_visible_y,bow_port_w,bow_stbd_w,bow_len,wash_hw,arm_port_w,arm_stbd_w,renderer_on,extra,cap";
        public const string MaskHeader = "cap,frame,exp,wave,phase,cam,wake_px,hero_px,overlap_px,hero_max_y";

        static string F(double x) => x.ToString("R", CultureInfo.InvariantCulture);
        static float YawOf(Transform t) { var f = t.forward; return Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg; }

        void Awake() { csv.Append(Header).Append('\n'); maskCsv.Append(MaskHeader).Append('\n'); }

        public Texture2D Render(Camera cam, int w, int h, int aa, bool withSprays)
        {
            var prevT = cam.targetTexture; float asp = cam.aspect;
            var r = RenderTexture.GetTemporary(new RenderTextureDescriptor(w, h, RenderTextureFormat.ARGB32, 24) { msaaSamples = aa, sRGB = true });
            var rr = RenderTexture.GetTemporary(new RenderTextureDescriptor(w, h, RenderTextureFormat.ARGB32, 0) { sRGB = true });
            CommandBuffer c = null;
            if (withSprays) { c = new CommandBuffer { name = "DS48 飛沫 v0" }; foreach (var s in sprays) if (s != null) s.AddTo(c); cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, c); }
            try { cam.aspect = (float)w / h; cam.targetTexture = r; cam.Render(); }
            finally { if (c != null) { cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, c); c.Release(); } cam.targetTexture = prevT; cam.aspect = asp; }
            Graphics.Blit(r, rr);
            var t = new Texture2D(w, h, TextureFormat.RGB24, false, false);
            RenderTexture.active = rr; t.ReadPixels(new Rect(0, 0, w, h), 0, 0); t.Apply(); RenderTexture.active = null;
            RenderTexture.ReleaseTemporary(r); RenderTexture.ReleaseTemporary(rr);
            return t;
        }

        public void PlaceChase(float dt)
        {
            var b = flow.steer.transform;
            float yaw = YawOf(b);
            if (float.IsNaN(yawS)) yawS = yaw;
            float a = 1f - Mathf.Exp(-Mathf.Max(0f, dt) / Mathf.Max(1e-3f, chaseYawTauS));
            yawS += Mathf.DeltaAngle(yawS, yaw) * a;
            var q = Quaternion.Euler(0f, yawS, 0f);
            var p = b.position; p.y = Mathf.Max(p.y, -0.8f);
            chase.transform.position = p + q * chaseOffset;
            chase.transform.rotation = Quaternion.LookRotation((p + q * chaseLook) - chase.transform.position, Vector3.up);
        }

        static int Diff(Color32[] a, Color32[] b, bool[] mask)
        {
            int n = 0;
            for (int i = 0; i < a.Length; i++)
            {
                bool d = Mathf.Abs(a[i].r - b[i].r) > 6 || Mathf.Abs(a[i].g - b[i].g) > 6 || Mathf.Abs(a[i].b - b[i].b) > 6;
                if (mask != null) mask[i] = d;
                if (d) n++;
            }
            return n;
        }

        float HeroMaxY()
        {
            var bw = flow.bus.boatWater; if (bw == null) return float.NaN;
            bw.Sync();
            var r = bw.readers.FirstOrDefault(x => x.Name == "hero");
            if (r == null || r.X == null) return float.NaN;
            float m = float.NegativeInfinity;
            for (int i = 1; i < r.X.Length; i += 3) if (r.X[i] > m) m = r.X[i];
            return m;
        }

        void MaskCheck(Camera cam, string name, double exp, double wave, string phase, float heroY)
        {
            var mr = wake.meshRenderer; bool was = mr.enabled;
            var full = Render(cam, maskW, maskH, 1, false);
            mr.enabled = false;
            var nowake = Render(cam, maskW, maskH, 1, false);
            var a = full.GetPixels32(); var b = nowake.GetPixels32();
            var wm = new bool[a.Length];
            int wpx = Diff(a, b, wm);
            int hpx, ov = 0;
            {
                // 主役波の画素は、航跡を消した画で主役波を消すと変わる所（航跡がその上に描かれていても数えられるように、航跡なしの画どうしで比べる）
                var on = heroRenderers.Where(r => r != null && r.enabled).ToList();
                foreach (var r in on) r.enabled = false;
                var nohero = Render(cam, maskW, maskH, 1, false);
                foreach (var r in on) r.enabled = true;
                var hm = new bool[a.Length];
                hpx = Diff(b, nohero.GetPixels32(), hm);
                for (int i = 0; i < a.Length; i++) if (wm[i] && hm[i]) ov++;
                if (ov > 0 || (wpx > 0 && hpx > 0 && overlapSamples < 40))
                {
                    overlapSamples++;
                    var img = new Texture2D(maskW, maskH, TextureFormat.RGB24, false, false);
                    var px = new Color32[a.Length];
                    for (int i = 0; i < a.Length; i++) px[i] = wm[i] && hm[i] ? new Color32(255, 0, 0, 255) : (wm[i] ? new Color32(255, 255, 255, 255) : (hm[i] ? new Color32(40, 90, 160, 255) : new Color32(0, 0, 0, 255)));
                    img.SetPixels32(px); img.Apply();
                    Directory.CreateDirectory(Path.Combine(outDir, "overlap"));
                    File.WriteAllBytes(Path.Combine(outDir, "overlap", name + "_" + Captured.ToString("00000") + (ov > 0 ? "_OVERLAP" : "") + ".png"), img.EncodeToPNG());
                    Destroy(img);
                }
                Destroy(nohero);
            }
            mr.enabled = was;
            maskCsv.Append(Captured).Append(',').Append(Time.frameCount).Append(',').Append(F(exp)).Append(',').Append(F(wave)).Append(',').Append(phase).Append(',').Append(name).Append(',')
                   .Append(wpx).Append(',').Append(hpx).Append(',').Append(ov).Append(',').Append(F(heroY)).Append('\n');
            Destroy(full); Destroy(nowake);
        }

        void LateUpdate()
        {
            if (flow == null || !flow.Ready || wake == null || !wake.Ready) return;
            var clk = flow.clock;
            double exp = clk.ExperienceSeconds;
            double wave = flow.HandedOver ? exp - flow.WaveStartS : double.NaN;
            var b = flow.steer.transform;
            var inp = flow.LastInput;
            string phase = flow.PhaseAt(exp).ToString();
            csv.Append(Time.frameCount).Append(',').Append(F(exp)).Append(',').Append(F(wave)).Append(',').Append(phase).Append(',').Append(flow.Paused ? 1 : 0).Append(',').Append(flow.HandedOver ? 1 : 0).Append(',')
               .Append(flow.steer.CurrentMode).Append(',').Append(F(inp.throttle)).Append(',').Append(F(inp.turn)).Append(',').Append(inp.stop ? 1 : 0).Append(',')
               .Append(F(b.position.x)).Append(',').Append(F(b.position.y)).Append(',').Append(F(b.position.z)).Append(',').Append(F(YawOf(b))).Append(',')
               .Append(F(wake.SpeedMs)).Append(',').Append(F(wake.YawRateDegS)).Append(',').Append(F(wake.Sv)).Append(',').Append(F(wake.Sr)).Append(',').Append(F(wake.Gate)).Append(',').Append(wake.Emitting ? 1 : 0).Append(',')
               .Append(wake.Samples).Append(',').Append(wake.VisibleVerts).Append(',').Append(wake.GuardHidden).Append(',').Append(wake.OverhangHidden).Append(',').Append(wake.OutsideHidden).Append(',').Append(F(wake.MaxVisibleY)).Append(',')
               .Append(F(wake.BowPortW)).Append(',').Append(F(wake.BowStbdW)).Append(',').Append(F(wake.BowLenM)).Append(',').Append(F(wake.WashHalfW)).Append(',').Append(F(wake.ArmPortW)).Append(',').Append(F(wake.ArmStbdW)).Append(',')
               .Append(wake.meshRenderer.enabled ? 1 : 0).Append(',').Append(extra != null ? extra() : "").Append(',');
            PlaceChase(Time.deltaTime);
            acc += Time.deltaTime;
            bool cap = Frames == 0 || acc >= captureEveryS - 1e-6;
            csv.Append(cap ? Captured : -1).Append('\n');
            if (cap)
            {
                acc = Frames == 0 ? 0.0 : acc - captureEveryS;
                if (acc > captureEveryS) acc = 0.0;
                var sw = System.Diagnostics.Stopwatch.StartNew();
                var t1 = Render(chase, chaseW, chaseH, msaa, true);
                File.WriteAllBytes(Path.Combine(outDir, "frames_chase", "c_" + Captured.ToString("00000") + ".jpg"), t1.EncodeToJPG(jpgQuality)); Destroy(t1);
                var t2 = Render(flow.hmdCamera, hmdW, hmdH, msaa, true);
                File.WriteAllBytes(Path.Combine(outDir, "frames_hmd", "h_" + Captured.ToString("00000") + ".jpg"), t2.EncodeToJPG(jpgQuality)); Destroy(t2);
                if (Captured % maskEvery == 0)
                {
                    float hy = HeroMaxY();
                    MaskCheck(chase, "chase", exp, wave, phase, hy);
                    MaskCheck(flow.hmdCamera, "hmd", exp, wave, phase, hy);
                }
                Captured++;
                RenderMsTotal += sw.Elapsed.TotalMilliseconds;
            }
            Frames++;
        }
    }
}
