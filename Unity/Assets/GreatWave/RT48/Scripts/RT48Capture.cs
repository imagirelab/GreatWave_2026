using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

namespace GreatWave.RT48
{
    // RT48：画面外に描いて PNG にする（計画 §3.6：動画は計算の時刻を 1/60 s ずつ進めて画面外に描き、ffmpeg で 60 fps にする）。
    //   -rt48capture <dir>  -rt48capfps 60  -rt48capfrom <t>  -rt48capto <t>  -rt48capsize 1920x1080   連番 frame_00000.png …
    //   -rt48stills <dir>  -rt48stilltimes a,b,c  -rt48stillseats 556,574  -rt48stillviews bow,crest   静止画
    //   -rt48decodecheck <out.json>   照合（C5 の測り方）を、この実行の GPU で行って書く
    //   -rt48quit   終わったら閉じる
    // 字（RT48Captions）は描く前に今の時刻に合わせるので、画面外の絵にも入る。
    public class RT48Capture : MonoBehaviour
    {
        public RT48Playback playback;
        public RT48Captions captions;
        public Camera captureCamera;
        public int msaa = 4;

        public bool Busy { get; private set; }

        IEnumerator Start()
        {
            if (!Application.isPlaying) yield break;
            string seq = RT48Playback.Arg("-rt48capture", ""), stills = RT48Playback.Arg("-rt48stills", ""), dc = RT48Playback.Arg("-rt48decodecheck", "");
            string ex = RT48Playback.Arg("-rt48export", "");   // 確かめの書き出し（RT48VerifyExport）。-rt48verifydir に v_prep.py の出力
            if (string.IsNullOrEmpty(seq) && string.IsNullOrEmpty(stills) && string.IsNullOrEmpty(dc) && string.IsNullOrEmpty(ex)) yield break;
            Busy = true;
            yield return null;   // 再生の初期化を待つ
            while (playback == null || !playback.Initialized) yield return null;
            if (playback.Source == null) { Debug.LogError("RT48_CAPTURE 元がありません"); Busy = false; yield break; }
            playback.ManualClock = true;
            ParseSize(RT48Playback.Arg("-rt48capsize", "1920x1080"), out int w, out int h);
            if (!string.IsNullOrEmpty(dc))
            {
                var src = playback.Source as RecordedSectionSource;
                var times = new List<double>();
                for (int k = 0; k < 20; k++) times.Add(src.TimeFirst + (src.TimeLast - src.TimeFirst) * (k + 0.37) / 20.0);
                var res = RT48DecodeCheck.Run(playback.decodeCheck, src, playback.SeatX, times);
                WriteText(dc, JsonUtility.ToJson(res, true));
                Debug.Log("RT48_DECODECHECK pass=" + res.pass + " maxPosErr=" + res.maxPosErr.ToString("E3", CultureInfo.InvariantCulture) + " maxNormDeg=" + res.maxNormDeg.ToString("E3", CultureInfo.InvariantCulture));
            }
            if (!string.IsNullOrEmpty(ex))
            {
                try { RT48VerifyExport.Run(playback, RT48Playback.Arg("-rt48verifydir", ""), ex, RT48Playback.HasArg("-rt48exportholdout")); }
                catch (Exception e) { Debug.LogError("RT48_VERIFYEXPORT_EXCEPTION " + e); }
                yield return null;
            }
            if (!string.IsNullOrEmpty(stills))
            {
                var tsArg = ParseList(RT48Playback.Arg("-rt48stilltimes", ""));
                var seats = ParseList(RT48Playback.Arg("-rt48stillseats", playback.SeatX.ToString(CultureInfo.InvariantCulture)));
                var views = RT48Playback.Arg("-rt48stillviews", "bow,crest").Split(',');
                foreach (var seat in seats)
                {
                    playback.SetSeat(seat);
                    var ts = tsArg.Count > 0 ? new List<double>(tsArg) : new List<double> { playback.TimeStart, playback.Source.OnsetS, playback.Source.ContactS, playback.TimeEnd };
                    foreach (var v in views)
                        foreach (var t in ts)
                        {
                            playback.SetView(v.Trim() == "crest" ? 1 : 0);
                            double tt = Math.Min(t, playback.TimeEnd);
                            var path = Path.Combine(stills, string.Format(CultureInfo.InvariantCulture, "still_{0}_seat{1:F0}_{2}_t{3:F3}.png", playback.Source.Id, seat, v.Trim(), tt));
                            Render(tt, w, h, path);
                            yield return null;
                        }
                }
                Debug.Log("RT48_STILLS done dir=" + stills);
            }
            if (!string.IsNullOrEmpty(seq))
            {
                double fps = RT48Playback.ArgD("-rt48capfps", 60), from = RT48Playback.ArgD("-rt48capfrom", playback.TimeStart), to = RT48Playback.ArgD("-rt48capto", playback.TimeEnd);
                int n = (int)Math.Floor((to - from) * fps + 1e-9) + 1;
                for (int i = 0; i < n; i++)
                {
                    double t = from + i / fps;
                    Render(t, w, h, Path.Combine(seq, string.Format(CultureInfo.InvariantCulture, "frame_{0:D5}.png", i)));
                    if (i % 30 == 0) yield return null;
                }
                WriteText(Path.Combine(seq, "capture.json"), "{\"from\":" + from.ToString("R", CultureInfo.InvariantCulture) + ",\"to\":" + to.ToString("R", CultureInfo.InvariantCulture) +
                    ",\"fps\":" + fps.ToString("R", CultureInfo.InvariantCulture) + ",\"frames\":" + n + ",\"source\":\"" + playback.Source.Id + "\",\"seat\":" + playback.SeatX.ToString("R", CultureInfo.InvariantCulture) +
                    ",\"view\":" + playback.ViewIndex + ",\"size\":\"" + w + "x" + h + "\"}");
                Debug.Log("RT48_CAPTURE done frames=" + n + " dir=" + seq);
            }
            playback.ManualClock = false;
            Busy = false;
            if (RT48Playback.HasArg("-rt48quit")) playback.Quit("capture_done");
        }

        public void Render(double t, int w, int h, string path)
        {
            playback.ApplyTime(t);
            playback.ApplyDesktopView();
            var tex = RenderCamera(captureCamera, w, h, msaa, captions);
            WriteBytes(path, tex.EncodeToPNG());
            DestroyImmediate(tex);
        }

        // カメラを w×h の画面外に描いて読み戻す（MSAA を解いてから読む）。字は描く前に合わせる。
        public static Texture2D RenderCamera(Camera cam, int w, int h, int msaa, RT48Captions caps)
        {
            var desc = new RenderTextureDescriptor(w, h, RenderTextureFormat.ARGB32, 24) { msaaSamples = Math.Max(1, msaa), sRGB = true };
            var rt = RenderTexture.GetTemporary(desc);
            var res = RenderTexture.GetTemporary(new RenderTextureDescriptor(w, h, RenderTextureFormat.ARGB32, 0) { sRGB = true });
            var prevT = cam.targetTexture;
            var prevEye = cam.stereoTargetEye;
            cam.targetTexture = rt;
            cam.stereoTargetEye = StereoTargetEyeMask.None;
            if (caps != null) caps.Refresh();
            cam.Render();
            Graphics.Blit(rt, res);
            var prevA = RenderTexture.active;
            RenderTexture.active = res;
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply();
            RenderTexture.active = prevA;
            cam.targetTexture = prevT;
            cam.stereoTargetEye = prevEye;
            if (caps != null) caps.Refresh();
            RenderTexture.ReleaseTemporary(rt);
            RenderTexture.ReleaseTemporary(res);
            return tex;
        }

        static void ParseSize(string s, out int w, out int h)
        {
            var p = s.ToLowerInvariant().Split('x');
            w = int.Parse(p[0], CultureInfo.InvariantCulture); h = int.Parse(p[1], CultureInfo.InvariantCulture);
        }

        static List<double> ParseList(string s)
        {
            var r = new List<double>();
            foreach (var p in s.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries))
                r.Add(double.Parse(p.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture));
            return r;
        }

        public static void WriteBytes(string path, byte[] b)
        {
            var d = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(d)) Directory.CreateDirectory(d);
            File.WriteAllBytes(path, b);
        }

        public static void WriteText(string path, string s)
        {
            var d = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(d)) Directory.CreateDirectory(d);
            File.WriteAllText(path, s, new System.Text.UTF8Encoding(false));
        }
    }
}
