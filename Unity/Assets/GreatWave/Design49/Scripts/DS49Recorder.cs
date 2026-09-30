using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using GreatWave.Design31;
using GreatWave.Design47;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design49
{
    // 設計49：試験だけの記録の部品（場面に保存しない。DS49SoundPlay が Play の間だけ足す）。
    //   毎フレームの LateUpdate の最後（order 1000。音の位置 DS49Sound の 100 の後）に、時計・聞き手の姿勢・音ごとの状態（鳴っているか、
    //   再生の位置、時計から決めた位置、音量、聞き手から見た音の位置）を 1 行に記録する。1/30 s（体験の時刻）ごとに HMD Camera（聞き手の目）を JPG で書く。
    [DefaultExecutionOrder(1000)]
    public class DS49Recorder : MonoBehaviour
    {
        public DS47Flow flow;
        public DS49Sound sound;
        public string outDir;
        public List<DS31InstancedParticles> sprays = new List<DS31InstancedParticles>();
        public int hmdW = 960, hmdH = 540, jpgQuality = 88, msaa = 4;
        public double captureEveryS = 1.0 / 30.0;
        public Func<string> extra;
        [Tooltip("音のオフラインの書き出し（試験だけ）。LateUpdate の始めに、このフレームの分の標本を取り出す")]
        public DS49CaptureDriver capture;
        public readonly StringBuilder csv = new StringBuilder();
        public int Frames { get; private set; }
        public int Captured { get; private set; }
        public double RenderMsTotal { get; private set; }
        double nextCap = 0.0;

        static string F(double x) => x.ToString("R", CultureInfo.InvariantCulture);

        void Awake()
        {
            var h = new StringBuilder("frame,exp,wave,phase,paused,clock_running,lis_x,lis_y,lis_z,lis_fx,lis_fz,lis_rx,lis_rz,boat_ang,boat_speed");
            foreach (var k in new[] { "rumble", "tstar", "wind", "creak" })
                h.Append(',').Append(k).Append("_active,").Append(k).Append("_playing,").Append(k).Append("_ts,").Append(k).Append("_target,").Append(k).Append("_drift,")
                 .Append(k).Append("_vol,").Append(k).Append("_lx,").Append(k).Append("_ly,").Append(k).Append("_lz,").Append(k).Append("_resyncs");
            h.Append(",extra,cap\n");
            csv.Append(h);
        }

        public Texture2D Render(Camera cam, int w, int h, int aa, bool withSprays)
        {
            var prevT = cam.targetTexture; float asp = cam.aspect;
            var r = RenderTexture.GetTemporary(new RenderTextureDescriptor(w, h, RenderTextureFormat.ARGB32, 24) { msaaSamples = aa, sRGB = true });
            var rr = RenderTexture.GetTemporary(new RenderTextureDescriptor(w, h, RenderTextureFormat.ARGB32, 0) { sRGB = true });
            CommandBuffer c = null;
            if (withSprays) { c = new CommandBuffer { name = "DS49 飛沫 v0" }; foreach (var s in sprays) if (s != null) s.AddTo(c); cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, c); }
            try { cam.aspect = (float)w / h; cam.targetTexture = r; cam.Render(); }
            finally { if (c != null) { cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, c); c.Release(); } cam.targetTexture = prevT; cam.aspect = asp; }
            Graphics.Blit(r, rr);
            var t = new Texture2D(w, h, TextureFormat.RGB24, false, false);
            RenderTexture.active = rr; t.ReadPixels(new Rect(0, 0, w, h), 0, 0); t.Apply(); RenderTexture.active = null;
            RenderTexture.ReleaseTemporary(r); RenderTexture.ReleaseTemporary(rr);
            return t;
        }

        void LateUpdate()
        {
            if (capture != null) capture.Pull();
            if (flow == null || sound == null || !flow.Ready || !sound.Ready) return;
            Frames++;
            var clk = flow.clock;
            double exp = clk.ExperienceSeconds;
            var L = sound.listener != null ? sound.listener.transform : flow.hmdCamera.transform;
            var inv = Quaternion.Inverse(L.rotation);
            var sb = new StringBuilder();
            sb.Append(Time.frameCount).Append(',').Append(F(exp)).Append(',').Append(F(clk.WaveSeconds)).Append(',').Append(flow.CurrentPhase).Append(',').Append(flow.Paused ? 1 : 0).Append(',')
              .Append(clk.State == GreatWave.ArtFirst.GWClock.RunState.Running ? 1 : 0).Append(',')
              .Append(F(L.position.x)).Append(',').Append(F(L.position.y)).Append(',').Append(F(L.position.z)).Append(',')
              .Append(F(L.forward.x)).Append(',').Append(F(L.forward.z)).Append(',').Append(F(L.right.x)).Append(',').Append(F(L.right.z)).Append(',')
              .Append(F(sound.BoatAngDegS)).Append(',').Append(F(sound.BoatSpeed));
            foreach (var s in sound.tracks)
            {
                var lp = inv * (s.src.transform.position - L.position);
                sb.Append(',').Append(s.active ? 1 : 0).Append(',').Append(s.src.isPlaying ? 1 : 0).Append(',').Append(s.src.timeSamples).Append(',').Append(F(s.lastTargetS)).Append(',').Append(F(s.lastDriftS))
                  .Append(',').Append(F(s.src.volume)).Append(',').Append(F(lp.x)).Append(',').Append(F(lp.y)).Append(',').Append(F(lp.z)).Append(',').Append(s.resyncs);
            }
            sb.Append(',').Append(extra != null ? extra() : "");
            int cap = -1;
            if (exp + 1e-9 >= nextCap && !string.IsNullOrEmpty(outDir))
            {
                var sw = System.Diagnostics.Stopwatch.StartNew();
                var t = Render(flow.hmdCamera, hmdW, hmdH, msaa, true);
                File.WriteAllBytes(Path.Combine(outDir, "frames_hmd", "h_" + Captured.ToString("D5") + ".jpg"), t.EncodeToJPG(jpgQuality));
                Destroy(t);
                RenderMsTotal += sw.Elapsed.TotalMilliseconds;
                cap = Captured++;
                while (nextCap <= exp + 1e-9) nextCap += captureEveryS;
            }
            sb.Append(',').Append(cap).Append('\n');
            csv.Append(sb);
        }
    }
}
