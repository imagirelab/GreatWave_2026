using System;
using System.Globalization;
using System.IO;
using System.Text;
using Unity.Collections;
using UnityEngine;

namespace GreatWave.Design49
{
    // 設計49：試験だけ（場面に保存しない。DS49SoundPlay が Play の間だけ足す）。Unity の音の混ぜを、フレームの時刻に合わせてオフラインで書き出す。
    //   ・Editor の一時停止（EditorApplication.Step）の間は Unity の音の系も止まり、AudioRenderer が標本を返さない。そこでこの試験では一時停止をせず、
    //     Time.captureDeltaTime = 1/90 s で 1 フレーム = 1/90 s に固定して進める（設計47・48 の Step と同じ時刻の刻み。壁の時計とは切り離す）。
    //   ・毎フレームの LateUpdate の終わり（記録の部品 DS49Recorder、order 1000 が Pull を呼ぶ。音の位置 DS49Sound の 100 の後）に、そのフレームの分の標本
    //     （AudioRenderer.GetSampleCountForCaptureFrame）を取り出して float32 の生の列で書き、フレームごとの体験の時刻と標本の数を CSV に残す
    //     （batchmode では WaitForEndOfFrame が呼ばれないので、フレームの終わりの代わりに LateUpdate の最後で取る）。
    //   ・毎フレームの始め（order -1000 の Update）に、試験の筋書き（操船の入力・頭の向き）を onFrame で当てる。
    [DefaultExecutionOrder(-1000)]
    public class DS49CaptureDriver : MonoBehaviour
    {
        public string outPath;
        public float frameDt = 1f / 90f;
        public Func<double> clockNow;
        public Action onFrame;
        public bool Ok { get; private set; }
        public long Samples { get; private set; }
        public int Channels { get; private set; }
        public int ZeroFrames { get; private set; }
        public readonly StringBuilder csv = new StringBuilder("frame,exp,samples,cum,dsp\n");
        /// <summary>AudioRenderer.Start を呼んだ時の体験の時刻（音の流れの標本 0 の時刻）。</summary>
        public double StartExp { get; private set; } = double.NaN;
        public string NoteJa { get; private set; } = "";
        BinaryWriter bw;
        bool stopped;

        static string F(double x) => x.ToString("R", CultureInfo.InvariantCulture);

        public void Begin()
        {
            Time.captureDeltaTime = frameDt;
            StartExp = clockNow != null ? clockNow() : double.NaN;
            Ok = AudioRenderer.Start();
            Channels = AudioSettings.speakerMode == AudioSpeakerMode.Mono ? 1 : 2;
            bw = new BinaryWriter(new FileStream(outPath, FileMode.Create, FileAccess.Write));
            AudioSettings.GetDSPBufferSize(out int len, out int num);
            NoteJa = "AudioRenderer.Start=" + Ok + " captureDeltaTime=" + F(Time.captureDeltaTime) + " outputSampleRate=" + AudioSettings.outputSampleRate + " speakerMode=" + AudioSettings.speakerMode + " dspBuffer=" + len + "x" + num;
        }

        void Update() { onFrame?.Invoke(); }

        public void Pull()
        {
            if (!Ok || bw == null || stopped) return;
            int n = AudioRenderer.GetSampleCountForCaptureFrame();
            // 標本が 0 でも Render を毎フレーム呼ぶ（Unity Recorder と同じ。最初の Render までオフラインの書き出しが始まらない：main6 で 0 標本のまま）
            using (var buf = new NativeArray<float>(Math.Max(0, n) * Channels, Allocator.Temp))
            {
                AudioRenderer.Render(buf);
                for (int i = 0; i < buf.Length; i++) bw.Write(buf[i]);
            }
            if (n > 0) Samples += n; else ZeroFrames++;
            double e = clockNow != null ? clockNow() : double.NaN;
            csv.Append(Time.frameCount).Append(',').Append(F(e)).Append(',').Append(n).Append(',').Append(Samples).Append(',').Append(F(AudioSettings.dspTime)).Append('\n');
        }

        public void End()
        {
            if (stopped) return;
            stopped = true;
            try { bw?.Flush(); bw?.Close(); } catch (Exception) { }
            bw = null;
            if (Ok) AudioRenderer.Stop();
            Time.captureDeltaTime = 0f;
        }

        void OnDestroy() { End(); }
    }
}
