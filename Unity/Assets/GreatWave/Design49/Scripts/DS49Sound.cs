using System;
using System.Collections.Generic;
using GreatWave.ArtFirst;
using GreatWave.Design46;
using GreatWave.Design47;
using UnityEngine;

namespace GreatWave.Design49
{
    [Serializable] public class DS49Track { public string key, nameJa, clip, anchorEvent, place; public bool loop; public float volume, minDistanceM, maxDistanceM, spreadDeg; }
    [Serializable] public class DS49Place { public float windFromYawOffsetDeg, windDistanceM; public float[] creakLocal; }
    [Serializable] public class DS49WindGain { public float intro, formationPeak, hold, holdDropS, afterglowPeak, endFadeS; }
    [Serializable] public class DS49CreakGain { public float angDegSLow, angDegSHigh, speedLow, speedHigh, angWeight, speedWeight, smoothS; }
    [Serializable] public class DS49Sync { public float resyncToleranceS, dopplerLevel; public int stageOrder; }

    [Serializable]
    public class DS49Config
    {
        public string schema;
        public int sampleRate;
        public DS49Track[] tracks;
        public DS49Place place;
        public DS49WindGain windGain;
        public DS49CreakGain creakGain;
        public DS49Sync sync;

        public static DS49Config Parse(string json)
        {
            var c = JsonUtility.FromJson<DS49Config>(json);
            if (c == null || c.schema != "GreatWave.DS49.sound/1" || c.tracks == null || c.place == null || c.windGain == null || c.creakGain == null || c.sync == null)
                throw new InvalidOperationException("DS49Config：表が読めません（GreatWave.DS49.sound/1）");
            return c;
        }
    }

    // 設計49：波・木船・風の音。共通時計（GWClock、Master。設計46）の段「sound」（order 95、出来事 90 の後）として、
    // 音の中身の時刻を時計から決める：再生の位置 = 体験の時刻 − 出来事の時刻（出来事の表 DS46EventTrack の、設計47 が入れた時刻）。
    //   ・出来事が起きた段（前の時刻 < 出来事 ≤ 今の時刻）でその音を始め、位置を 今の時刻 − 出来事の時刻 にする（見た目の時刻と同じ所から鳴る）。
    //   ・毎段、再生の位置と時計の差が resyncToleranceS を超えたら合わせ直す。輪の音は長さで割った余り。
    //   ・止めている間（時計の停止・進行役の一時停止）は音も止め（AudioSource.Pause）、再開で合わせ直す。途中からの再生（Seek）・初期化でも同じ規則。
    //   ・位置（LateUpdate、order 100。乗客 90・進行役 95・航跡 96 の後）：地鳴り = 主役波の描画の範囲の中心、t* の音 = t* の爪の範囲の中心、
    //     風 = 聞き手 ＋ 世界に固定した向き × 距離、きしみ = 座席の船の局所の点。
    //   ・音量：風は時計の関数（相と時刻）、きしみは船の動き（体験の時刻で微分）。地鳴りと t* の音は中身に強弱を焼いてある。
    // 崩壊の音は作らない（Q11）。PC の Editor で確かめた。HMD 実機（PS VR2）は保留。
    [DefaultExecutionOrder(100)]
    public class DS49Sound : MonoBehaviour
    {
        public TextAsset configJson;
        public GWClock clock;
        public DS47Flow flow;
        public DS46EventTrack events;
        public AudioListener listener;
        [Tooltip("key の順（rumble, tstar, wind, creak）に AudioSource")]
        public List<AudioSource> sources = new List<AudioSource>();
        [Tooltip("主役波のシート（hero）の描画（地鳴りの位置）")]
        public List<Renderer> heroRenderers = new List<Renderer>();
        [Tooltip("爪の描画（t* の音の位置）")]
        public List<Renderer> crestRenderers = new List<Renderer>();

        public DS49Config Cfg { get; private set; }
        public bool Ready { get; private set; }

        public class TrackState
        {
            public DS49Track t;
            public AudioSource src;
            public double anchorT = double.NaN;     // 出来事の時刻（体験の秒）。まだなら NaN
            public bool active;                      // 時計の上で鳴っている区間にいる
            public bool paused;
            public int starts, resyncs, stops, lostVoice;
            public bool scheduled;
            public double lastTargetS = double.NaN, lastDriftS;
            public float gain = 1f;
            public string lastStartJa = "";
        }

        public readonly List<TrackState> tracks = new List<TrackState>();
        /// <summary>音を始めた記録（出来事の段と同じ段か、位置をいくつにしたか）。</summary>
        public readonly List<string> StartLog = new List<string>();
        public readonly List<string> Log = new List<string>();
        public int Errors { get; private set; }
        public string LastError { get; private set; } = "";
        public Vector3 WindFromDir { get; private set; }
        public float BoatAngDegS { get; private set; }
        public float BoatSpeed { get; private set; }
        public bool AudioPausedByClock { get; private set; }
        /// <summary>前の段の体験の時刻 − dspTime の最小（音の流れへ写す差。混ぜ終わった所が時計にいちばん近い時の値）。</summary>
        public double MapOffset { get; private set; } = double.NaN;
        /// <summary>次に混ぜる所の体験の時刻（dspTime + MapOffset）。</summary>
        public double LastExpMix { get; private set; } = double.NaN;
        bool mapReset = true, resumedSincePause;
        public int MapResets { get; private set; }
        /// <summary>時計 ↔ 音の処理の時計の対応を次の段で取り直す（音の出力の方式を変えた時など。試験の AudioRenderer.Start の後に呼ぶ）。</summary>
        public void ResetClockMap() { mapReset = true; }

        Quaternion lastBoatRot; Vector3 lastBoatPos; double lastBoatExp = double.NaN;
        bool crestFixed; Vector3 crestPos;
        readonly Dictionary<string, double> firedAt = new Dictionary<string, double>();

        static float Smooth(float x) { x = Mathf.Clamp01(x); return x * x * (3f - 2f * x); }

        void Start() { if (Application.isPlaying) Init(); }

        public void Init()
        {
            if (Ready) return;
            Cfg = DS49Config.Parse(configJson.text);
            if (sources.Count != Cfg.tracks.Length) throw new InvalidOperationException("DS49Sound：AudioSource の数が表の tracks と違います");
            tracks.Clear();
            for (int i = 0; i < Cfg.tracks.Length; i++)
            {
                var src = sources[i];
                var t = Cfg.tracks[i];
                src.playOnAwake = false; src.loop = t.loop; src.spatialBlend = 1f; src.dopplerLevel = Cfg.sync.dopplerLevel;
                src.rolloffMode = AudioRolloffMode.Logarithmic; src.minDistance = t.minDistanceM; src.maxDistance = t.maxDistanceM; src.spread = t.spreadDeg;
                src.volume = 0f;
                if (src.isPlaying) src.Stop();
                tracks.Add(new TrackState { t = t, src = src });
            }
            // 風の来る向き：原画のカメラの左（大波の側）を水平にし、windFromYawOffsetDeg だけ回す（世界に固定）
            var pc = flow != null && flow.paintingCamera != null ? flow.paintingCamera.transform : null;
            var left = pc != null ? -pc.right : Vector3.left; left.y = 0f;
            WindFromDir = Quaternion.Euler(0f, Cfg.place.windFromYawOffsetDeg, 0f) * left.normalized;
            if (events != null) events.Fired += OnFired;
            clock.Register("sound", Cfg.sync.stageOrder, OnClock);
            Ready = true;
            Log.Add("init tracks=" + tracks.Count + " windFrom=" + WindFromDir.ToString("F3") + " outputRate=" + AudioSettings.outputSampleRate);
        }

        void OnDestroy() { if (events != null) events.Fired -= OnFired; }

        void OnFired(DS46EventTrack.Entry e, GWClock.Step st) { firedAt[e.id] = st.experience; }

        double AnchorOf(string id)
        {
            if (events == null) return double.NaN;
            foreach (var e in events.entries) if (e.id == id) return e.t;
            return double.NaN;
        }

        // ---------------------------------------------------------------- 共通時計の段（order 95）
        void OnClock(GWClock c, GWClock.Step st)
        {
            try { OnClockInner(st); }
            catch (Exception ex) { Errors++; LastError = ex.GetType().Name + ": " + ex.Message; if (Errors <= 3) { Log.Add("error " + LastError); Debug.LogException(ex); } }
        }

        void OnClockInner(GWClock.Step st)
        {
            double exp = st.experience;
            UpdateBoatMotion(exp, st);
            // 時計 ↔ 音の処理の時計（AudioSettings.dspTime）の対応：音は 1024 標本の塊でまとめて混ぜられ、次に混ぜる塊の頭は体験の時刻より
            // 最大 1 塊（≈ 21 ms ≈ 1.9 フレーム）前にある（main7 で確かめた）。そこで 差 = 体験の時刻 − dspTime の最小（塊の頭にいちばん近い時）を対応として持ち、
            // 次に混ぜる所の体験の時刻 expMix = dspTime + 差 で中身の位置を決める（始まりが未来なら PlayScheduled で標本の精度で予約する）。
            // 跳んだ時（初期化・Seek）と、止めた後の再開では対応を取り直す（止めている間も dspTime は進む）。
            double dsp = AudioSettings.dspTime;
            if (st.kind != GWClock.StepKind.Advance || resumedSincePause) { mapReset = true; resumedSincePause = false; }
            // この段の時点で混ぜ終わっている音は、前の段の時刻（st.previous）までの分。差は前の段の時刻で取る（今の時刻で取ると 1 段ぶん遅れて写る：main8 で 1 フレーム遅れ）
            double o = (st.kind == GWClock.StepKind.Advance ? st.previous : exp) - dsp;
            // 実時間で時計が音の時計より速く進んだ（差が塊の粒 + 許し幅より大きく開いた）時も取り直す
            if (!double.IsNaN(MapOffset) && o - MapOffset > Cfg.sync.resyncToleranceS) { mapReset = true; MapResets++; }
            if (mapReset || double.IsNaN(MapOffset) || o < MapOffset) { MapOffset = o; mapReset = false; }
            double expMix = dsp + MapOffset;
            LastExpMix = expMix;
            foreach (var s in tracks)
            {
                double a = AnchorOf(s.t.anchorEvent);
                s.anchorT = a;
                var clip = s.src.clip;
                if (clip == null) continue;
                double len = clip.samples / (double)clip.frequency;
                bool inRange = !double.IsNaN(a) && exp >= a && (s.t.loop || exp - a < len);
                s.gain = GainOf(s, exp);
                s.src.volume = s.t.volume * s.gain;
                if (!inRange)
                {
                    if (s.active)
                    {
                        // 一回きりの音が終わりまで来た時は止めずに鳴り終わらせる（中身の終わりは体験の時刻より最大 1 塊遅れて混ぜられる）。それ以外（後ろへ跳んだ等）は止める
                        if (!(!s.t.loop && exp - a >= len)) s.src.Stop();
                        s.active = false; s.stops++;
                    }
                    s.lastTargetS = double.NaN;
                    continue;
                }
                double pos = expMix - a;   // 次に混ぜる所での中身の位置（負なら、まだ始まっていない）
                if (s.t.loop && pos >= 0) pos -= Math.Floor(pos / len) * len;
                int target = (int)Math.Min(clip.samples - 1, Math.Max(0, Math.Round(pos * clip.frequency)));
                s.lastTargetS = pos;
                if (s.active && !s.src.isPlaying && !s.paused && !s.scheduled)
                {
                    // 鳴っているはずの区間で声が止まっている（音の装置がない・声を取られた）：その時刻の位置から鳴らし直す（記録は数だけ）
                    s.lostVoice++;
                    s.src.timeSamples = target;
                    s.src.Play();
                    continue;
                }
                if (!s.active)
                {
                    double at = double.NaN;
                    if (pos < 0 && st.kind == GWClock.StepKind.Advance)
                    {
                        s.src.timeSamples = 0;
                        at = dsp + (-pos);
                        s.src.PlayScheduled(at);   // 出来事の時刻ちょうどの標本から（音の処理の時計で予約）
                        s.scheduled = true;
                    }
                    else { s.src.timeSamples = target; s.src.Play(); s.scheduled = false; }
                    s.active = true; s.paused = false; s.starts++;
                    bool sameStep = firedAt.TryGetValue(s.t.anchorEvent, out var fs) && Math.Abs(fs - exp) < 1e-9;
                    s.lastStartJa = s.t.key + " kind=" + st.kind + " step=" + st.index + " exp=" + exp.ToString("R") + " anchor=" + a.ToString("R") + " pos=" + pos.ToString("R") + " sameStepAsEvent=" + sameStep;
                    StartLog.Add("{\"track\":\"" + s.t.key + "\",\"event\":\"" + s.t.anchorEvent + "\",\"kind\":\"" + st.kind + "\",\"step\":" + st.index + ",\"frame\":" + Time.frameCount +
                        ",\"exp\":" + exp.ToString("R") + ",\"prev\":" + st.previous.ToString("R") + ",\"eventT\":" + a.ToString("R") + ",\"dsp\":" + dsp.ToString("R") + ",\"mapOffset\":" + MapOffset.ToString("R") +
                        ",\"expMix\":" + expMix.ToString("R") + ",\"startPosS\":" + pos.ToString("R") + ",\"startSample\":" + target +
                        ",\"scheduledDsp\":" + (double.IsNaN(at) ? "null" : at.ToString("R")) + ",\"eventFiredThisStep\":" + (sameStep ? "true" : "false") + "}");
                    continue;
                }
                if (s.scheduled) { if (pos >= 0) s.scheduled = false; else continue; }
                if (st.kind != GWClock.StepKind.Advance) { s.src.timeSamples = target; s.resyncs++; continue; }   // 跳んだ：その時刻の位置へ
                double now = s.src.timeSamples / (double)clip.frequency;
                double drift = now - pos;
                if (s.t.loop && Math.Abs(drift) > len * 0.5) drift -= Math.Sign(drift) * len;
                s.lastDriftS = drift;
                if (Math.Abs(drift) > Cfg.sync.resyncToleranceS) { s.src.timeSamples = target; s.resyncs++; }
            }
        }

        float GainOf(TrackState s, double exp)
        {
            if (s.t.key == "wind") return WindGain(exp);
            if (s.t.key == "creak") return CreakGain();
            return 1f;
        }

        public float WindGain(double exp)
        {
            var g = Cfg.windGain;
            if (flow == null || !flow.HandedOver || exp < flow.WaveStartS) return g.intro;
            double tw = exp - flow.WaveStartS;
            double form = flow.Cfg.timing.formationS;
            if (tw < form) return Mathf.Lerp(g.intro, g.formationPeak, Smooth((float)(tw / form)));
            if (exp < flow.AfterglowStartS) return Mathf.Lerp(g.formationPeak, g.hold, Smooth((float)((tw - form) / Math.Max(1e-6, g.holdDropS))));
            double u = (exp - flow.AfterglowStartS) / Math.Max(1e-6, flow.Cfg.timing.afterglowMoveS);
            float up = Mathf.Lerp(g.hold, g.afterglowPeak, Smooth((float)u));
            float fade = 1f - Smooth((float)((exp - (flow.EndS - g.endFadeS)) / Math.Max(1e-6, g.endFadeS)));
            return up * fade;
        }

        void UpdateBoatMotion(double exp, GWClock.Step st)
        {
            if (flow == null || flow.steer == null) return;
            var b = flow.steer.transform;
            if (double.IsNaN(lastBoatExp) || st.kind != GWClock.StepKind.Advance || exp - lastBoatExp <= 1e-9)
            {
                lastBoatRot = b.rotation; lastBoatPos = b.position; lastBoatExp = exp; return;
            }
            // 注：段 95 の時点の船の姿勢は、この段の前の物理（FixedUpdate は段の後）か、段 15 の時計の姿勢。どちらも 1 段の中で決まった値
            double dt = exp - lastBoatExp;
            // 1 段の回転は 0.1° ほどで、Quaternion.Angle は内積が 0.999999 を超えると 0 を返す（main9 で角速度が常に 0）。差の四元数のベクトル部から半角を取る
            var dq = b.rotation * Quaternion.Inverse(lastBoatRot);
            double vx = dq.x, vy = dq.y, vz = dq.z;
            double half = Math.Asin(Math.Min(1.0, Math.Sqrt(vx * vx + vy * vy + vz * vz)));
            float ang = (float)(2.0 * half * 180.0 / Math.PI / dt);
            var dp = b.position - lastBoatPos; dp.y = 0f;
            float spd = dp.magnitude / (float)dt;
            float a = 1f - Mathf.Exp(-(float)dt / Mathf.Max(1e-3f, Cfg.creakGain.smoothS));
            BoatAngDegS += (ang - BoatAngDegS) * a;
            BoatSpeed += (spd - BoatSpeed) * a;
            lastBoatRot = b.rotation; lastBoatPos = b.position; lastBoatExp = exp;
        }

        public float CreakGain()
        {
            var c = Cfg.creakGain;
            float ga = Mathf.Clamp01((BoatAngDegS - c.angDegSLow) / Mathf.Max(1e-3f, c.angDegSHigh - c.angDegSLow));
            float gs = Mathf.Clamp01((BoatSpeed - c.speedLow) / Mathf.Max(1e-3f, c.speedHigh - c.speedLow));
            return Mathf.Clamp01(c.angWeight * ga + c.speedWeight * gs);
        }

        static bool BoundsOf(List<Renderer> rs, out Bounds b)
        {
            b = new Bounds(); bool any = false;
            foreach (var r in rs)
            {
                if (r == null || !r.enabled || !r.gameObject.activeInHierarchy) continue;
                var rb = r.bounds;
                if (rb.size.sqrMagnitude < 1e-8f) continue;
                if (!any) { b = rb; any = true; } else b.Encapsulate(rb);
            }
            return any;
        }

        // ---------------------------------------------------------------- 位置と一時停止（乗客・進行役・航跡の後）
        void LateUpdate()
        {
            if (!Ready) return;
            try
            {
                bool running = clock.State == GWClock.RunState.Running && (flow == null || !flow.Paused);
                foreach (var s in tracks)
                {
                    if (!s.active) continue;
                    if (!running && !s.paused) { s.src.Pause(); s.paused = true; resumedSincePause = true; }
                    else if (running && s.paused) { s.src.UnPause(); s.paused = false; }
                }
                AudioPausedByClock = !running;
                var lp = listener != null ? listener.transform.position : Vector3.zero;
                foreach (var s in tracks)
                {
                    switch (s.t.place)
                    {
                        case "hero":
                            if (BoundsOf(heroRenderers, out var hb)) s.src.transform.position = hb.center;
                            break;
                        case "crest":
                            if (!crestFixed || clock.WaveSeconds < clock.tStarSeconds - 1e-6)
                            {
                                if (BoundsOf(crestRenderers, out var cb)) crestPos = cb.center;
                                else if (BoundsOf(heroRenderers, out var hb2)) crestPos = new Vector3(hb2.center.x, hb2.max.y, hb2.center.z);
                                crestFixed = clock.WaveSeconds >= clock.tStarSeconds - 1e-6;
                            }
                            s.src.transform.position = crestPos;
                            break;
                        case "wind":
                            s.src.transform.position = lp + WindFromDir * Cfg.place.windDistanceM;
                            break;
                        case "boat":
                            if (flow != null && flow.steer != null)
                            {
                                var cl = Cfg.place.creakLocal;
                                s.src.transform.position = flow.steer.transform.TransformPoint(new Vector3(cl[0], cl[1], cl[2]));
                            }
                            break;
                    }
                }
            }
            catch (Exception ex) { Errors++; LastError = ex.GetType().Name + ": " + ex.Message; if (Errors <= 3) { Log.Add("error " + LastError); Debug.LogException(ex); } }
        }
    }
}
