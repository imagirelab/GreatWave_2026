using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using GreatWave.ArtFirst;
using GreatWave.Design31;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.Design47
{
    // 設計47：試験だけの記録の部品（場面に保存しない。DS47FlowPlay が Play の間だけ足す）。
    //   毎フレームの LateUpdate の最後（order 1000。乗客・進行役の後）に、体験の状態を 1 行に記録し、
    //   captureFrames のとき HMD Camera（PC の視点）を 1920×1080 の RT へ描いて JPG で書く（通しの動画のコマ）。
    //   Play で Graphics.DrawMeshInstancedProcedural で描く飛沫 v0 は、手で描く時にも入るように CommandBuffer でも足す（同じ不透明の球なので二重でも画は同じ）。
    [DefaultExecutionOrder(1000)]
    public class DS47Recorder : MonoBehaviour
    {
        public DS47Flow flow;
        public string outDir;
        public bool captureFrames = true;
        public int width = 1920, height = 1080, msaa = 4, jpgQuality = 92;
        public List<DS31InstancedParticles> sprays = new List<DS31InstancedParticles>();
        public readonly StringBuilder csv = new StringBuilder();
        public int Frames { get; private set; }
        public int Captured { get; private set; }
        [Tooltip("動画のコマの間隔（フレームの時間の和で数える。1/30 s）")]
        public double captureEveryS = 1.0 / 30.0;
        double acc;
        public double RenderMsTotal { get; private set; }
        public readonly List<string> stillRequests = new List<string>();
        public readonly List<string> stillsWritten = new List<string>();
        public Func<string> extra;   // 試験の付け足しの列

        RenderTexture rt, res;
        Texture2D tex;
        CommandBuffer cb;

        public const string Header = "frame,dt,exp,wave,tau,clock_state,phase,paused,pause_reason,handed_over,steer_mode,in_thr,in_turn,in_stop,boat_x,boat_y,boat_z,boat_qx,boat_qy,boat_qz,boat_qw,boat_vx,boat_vy,boat_vz,kinematic,wet_points,rider_x,rider_y,rider_z,rider_qx,rider_qy,rider_qz,rider_qw,cam_x,cam_y,cam_z,cam_qx,cam_qy,cam_qz,cam_qw,cam_fov,head_dx,head_dy,head_dz,afterglow_u,events_fired,events_skipped,bw_rebuilds,bw_fallbacks,comfort_level,extra,cap";

        static string F(double x) => x.ToString("R", CultureInfo.InvariantCulture);

        void Awake() { csv.Append(Header).Append('\n'); }

        void Ensure()
        {
            if (rt != null) return;
            rt = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = msaa };
            res = new RenderTexture(width, height, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            rt.Create(); res.Create();
            tex = new Texture2D(width, height, TextureFormat.RGB24, false, false);
            cb = new CommandBuffer { name = "DS47 飛沫 v0" };
        }

        /// <summary>カメラを 1 枚描いて読み戻す（手で描く。背景は紙の上の色）。</summary>
        public Texture2D Render(Camera cam, int w, int h, int aa)
        {
            var prevT = cam.targetTexture; float asp = cam.aspect;
            var r = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = aa };
            var rr = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            r.Create(); rr.Create();
            var c = new CommandBuffer { name = "DS47 飛沫 v0（1 枚）" };
            foreach (var s in sprays) if (s != null) s.AddTo(c);
            cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, c);
            try { cam.aspect = (float)w / h; cam.targetTexture = r; cam.Render(); }
            finally { cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, c); c.Release(); cam.targetTexture = prevT; cam.aspect = asp; }
            Graphics.Blit(r, rr);
            var t = new Texture2D(w, h, TextureFormat.RGB24, false, false);
            RenderTexture.active = rr; t.ReadPixels(new Rect(0, 0, w, h), 0, 0); t.Apply(); RenderTexture.active = null;
            r.Release(); rr.Release(); Destroy(r); Destroy(rr);
            return t;
        }

        void LateUpdate()
        {
            if (flow == null || !flow.Ready) return;
            var clk = flow.clock;
            var st = clk.LastStep;
            var b = flow.steer.transform; var rbd = flow.steer.GetComponent<Rigidbody>();
            var r = flow.rider.transform; var c = flow.hmdCamera.transform;
            var q = b.rotation; var rq = r.rotation; var cq = c.rotation;
            var v = rbd.isKinematic ? Vector3.zero : rbd.linearVelocity;
            var inp = flow.LastInput;
            var ev = flow.bus.events; var bw = flow.bus.boatWater;
            var ho = flow.LastHeadOffset;
            csv.Append(Time.frameCount).Append(',').Append(F(Time.deltaTime)).Append(',').Append(F(clk.ExperienceSeconds)).Append(',').Append(F(clk.WaveSeconds)).Append(',')
               .Append(F(flow.bus.playback.Tau)).Append(',').Append(clk.State).Append(',').Append(flow.PhaseAt(clk.ExperienceSeconds)).Append(',').Append(flow.Paused ? 1 : 0).Append(',').Append(flow.PauseReason).Append(',')
               .Append(flow.HandedOver ? 1 : 0).Append(',').Append(flow.steer.CurrentMode).Append(',').Append(F(inp.throttle)).Append(',').Append(F(inp.turn)).Append(',').Append(inp.stop ? 1 : 0).Append(',')
               .Append(F(b.position.x)).Append(',').Append(F(b.position.y)).Append(',').Append(F(b.position.z)).Append(',')
               .Append(F(q.x)).Append(',').Append(F(q.y)).Append(',').Append(F(q.z)).Append(',').Append(F(q.w)).Append(',')
               .Append(F(v.x)).Append(',').Append(F(v.y)).Append(',').Append(F(v.z)).Append(',').Append(rbd.isKinematic ? 1 : 0).Append(',').Append(flow.buoyancy.LastWetPoints).Append(',')
               .Append(F(r.position.x)).Append(',').Append(F(r.position.y)).Append(',').Append(F(r.position.z)).Append(',')
               .Append(F(rq.x)).Append(',').Append(F(rq.y)).Append(',').Append(F(rq.z)).Append(',').Append(F(rq.w)).Append(',')
               .Append(F(c.position.x)).Append(',').Append(F(c.position.y)).Append(',').Append(F(c.position.z)).Append(',')
               .Append(F(cq.x)).Append(',').Append(F(cq.y)).Append(',').Append(F(cq.z)).Append(',').Append(F(cq.w)).Append(',').Append(F(flow.hmdCamera.fieldOfView)).Append(',')
               .Append(F(ho.x)).Append(',').Append(F(ho.y)).Append(',').Append(F(ho.z)).Append(',').Append(F(flow.AfterglowU)).Append(',')
               .Append(ev != null ? ev.FiredCount : -1).Append(',').Append(ev != null ? ev.SkippedCount : -1).Append(',').Append(bw != null ? bw.Rebuilds : -1).Append(',').Append(bw != null ? bw.FallbackCount : -1).Append(',')
               .Append(flow.rider.Level).Append(',').Append(extra != null ? extra() : "").Append(',');

            // 動画のコマ：フレームの時間の和で 1/30 s ごと（Play の 1 フレーム = 1/90 s なので 3 フレームに 1 枚）
            acc += Time.deltaTime;
            bool cap = captureFrames && (Frames == 0 || acc >= captureEveryS - 1e-6);
            csv.Append(cap ? Captured : -1).Append('\n');
            if (cap)
            {
                acc = Frames == 0 ? 0.0 : acc - captureEveryS;
                if (acc > captureEveryS) acc = 0.0;
                Ensure();
                var sw = System.Diagnostics.Stopwatch.StartNew();
                var cam = flow.hmdCamera;
                cb.Clear();
                foreach (var s in sprays) if (s != null) s.AddTo(cb);
                var prevT = cam.targetTexture; float asp = cam.aspect;
                cam.AddCommandBuffer(CameraEvent.AfterForwardOpaque, cb);
                try { cam.aspect = (float)width / height; cam.targetTexture = rt; cam.Render(); }
                finally { cam.RemoveCommandBuffer(CameraEvent.AfterForwardOpaque, cb); cam.targetTexture = prevT; cam.aspect = asp; }
                Graphics.Blit(rt, res);
                RenderTexture.active = res; tex.ReadPixels(new Rect(0, 0, width, height), 0, 0); tex.Apply(); RenderTexture.active = null;
                File.WriteAllBytes(Path.Combine(outDir, "frames", "f_" + Captured.ToString("00000") + ".jpg"), tex.EncodeToJPG(jpgQuality));
                Captured++;
                RenderMsTotal += sw.Elapsed.TotalMilliseconds;
            }
            if (stillRequests.Count > 0)
            {
                foreach (var label in stillRequests)
                {
                    var t = Render(flow.hmdCamera, width, height, 8);
                    var path = Path.Combine(outDir, "stills", label + ".png");
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    File.WriteAllBytes(path, t.EncodeToPNG());
                    Destroy(t);
                    stillsWritten.Add(label + "@" + F(clk.ExperienceSeconds) + "@frame" + Time.frameCount);
                }
                stillRequests.Clear();
            }
            Frames++;
        }

        void OnDestroy()
        {
            if (rt != null) { rt.Release(); res.Release(); Destroy(rt); Destroy(res); Destroy(tex); cb.Release(); }
        }
    }
}
