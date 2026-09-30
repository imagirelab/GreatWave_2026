using System;
using System.Collections.Generic;
using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design42;
using GreatWave.Design44;
using GreatWave.Design45;
using GreatWave.Design46;
using UnityEngine;
using UnityEngine.XR;

namespace GreatWave.Design47
{
    [Serializable] public class DS47Timing { public float introMinS, introMaxS, targetTotalS, handoverCheckEveryS, physicsDtS, formationS, holdS, afterglowMoveS, afterglowDwellS; }
    [Serializable] public class DS47Start { public float u, v, yawOffsetDeg; }
    [Serializable] public class DS47FormationPose { public float attStartWaveS, attEndWaveS, offsetDecayS; }
    [Serializable] public class DS47Afterglow { public float arcUpM, lookBoatUntil, pcSeatVfovDeg; public float[] boatLookLocal; public bool rotateRigInXr; }
    [Serializable] public class DS47Leave { public float radiusHM, radiusVM, graceS, returnGraceS; public float[] overlayColor, textColor; public string messageJa; }
    [Serializable] public class DS47Comfort { public int defaultLevel; }
    [Serializable] public class DS47Event { public string id, anchor, kind; public float offset; }

    [Serializable]
    public class DS47FlowConfig
    {
        public string schema;
        public DS47Timing timing;
        public DS47Start start;
        public DS47FormationPose formationPose;
        public DS47Afterglow afterglow;
        public DS47Leave leave;
        public DS47Comfort comfort;
        public DS47Event[] events;

        public static DS47FlowConfig Parse(string json)
        {
            var c = JsonUtility.FromJson<DS47FlowConfig>(json);
            if (c == null || c.schema != "GreatWave.DS47.flow/1" || c.timing == null || c.start == null || c.formationPose == null || c.afterglow == null || c.leave == null || c.events == null)
                throw new InvalidOperationException("DS47FlowConfig：表が読めません（GreatWave.DS47.flow/1）");
            return c;
        }
    }

    // 設計47：導入 → 接近 → 形成 → t* の保持 → 余韻 を一本につなぐ進行役（絵コンテ ds47_flow.json）。共通時計（GWClock、Master。設計46）の段として動く。
    //   ・段「flow」（order 5、水面より前）：引き継ぎの時刻を決め（D47-1。今の状態から軌道を仮に作り、全長の見込みが targetTotalS に届いた所、遅くとも introMaxS）、
    //     決めたら DS44BoatSteer.Handover()、大波の始まり（clock.waveStartSeconds = 引き継ぎ + T − 12）と終わり（endSeconds）を時計へ入れ、
    //     形成・余韻に結び付いた出来事を出来事の表（DS46EventTrack）へ体験の秒で入れる。
    //   ・段「seat_boat」（order 15、水面の後）：形成と保持の間、座席の船を時計の関数の姿勢で置く（D47-2。物理は止める。t* でちょうど原画の置き方）。
    //   ・FixedUpdate：導入と接近の間だけ、設計44 の操船を 1 段進める（浮力 DS42Buoyancy は自分の FixedUpdate で先に進む）。
    //   ・LateUpdate（order 95、乗客 DS45RiderComfort の 90 の後）：観賞の位置から外れた時の一時停止と再開（D47-4）、余韻の視点の移動（D47-3）。
    // 物理の時間刻みは Play の始めに physicsDtS（1/90 s）を Time.fixedDeltaTime へ入れる（ProjectSettings は変えない。D47-5）。
    // 乗客（HMD Camera の局所の姿勢）には触れない。余韻で動かすのは RiderComfortRoot の姿勢（PC では向きと画角も）。PC の Editor の Play で確かめた。HMD 実機は保留。
    [DefaultExecutionOrder(95)]
    public class DS47Flow : MonoBehaviour
    {
        public enum Phase { Intro, Approach, Formation, Hold, Afterglow, End }

        public TextAsset flowJson;
        public GWClock clock;
        public DS46ClockBus bus;
        public DS42Buoyancy buoyancy;
        public DS44BoatSteer steer;
        public DS45RiderComfort rider;
        public Camera hmdCamera;
        [Tooltip("原画の視点（DS27 painting。余韻の行き先。読むだけ）")]
        public Camera paintingCamera;
        [Tooltip("設計30 の座席の船の鉛直の支え（Δ(t) を読むだけ）")]
        public DS30BoatHeave seatHeave;
        [Tooltip("原画の場面の boat_mid の根（隠す。体験では物理の船が代わりに乗る）")]
        public Transform paintingSeatBoat;
        [Tooltip("t* の座席の船の根の置き方（ds43_boats.json の boat_mid の rootPos・rootRot）")]
        public Vector3 paintRootPos;
        public Quaternion paintRootRot = Quaternion.identity;
        [Tooltip("静水の喫水（出発点の高さ）")]
        public float eqDraftM = 0.249f;
        [Tooltip("出発点の水面の高さ（待機のコマ τ(0) の船用水面データ。場面を作る時に Editor で読んで入れる。Play の Start では、ほかの部品の初期化が再生器を一時 t* へ動かすことがあるので、その時の水を読まない）")]
        public float startWaterY = float.NaN;
        [Tooltip("観賞の位置から外れた時の覆い（HMD Camera の子。既定は非表示）")]
        public GameObject leaveOverlay;
        public bool placeAtStart = true;

        /// <summary>試験だけ：操船の入力を差し替える（null なら実際の機器 DS44Input.ReadLive）。</summary>
        public Func<DS44InputSample> inputOverride;

        public DS47FlowConfig Cfg { get; private set; }
        public bool Ready { get; private set; }
        public Phase CurrentPhase { get; private set; } = Phase.Intro;
        public bool HandedOver { get; private set; }
        public double HandoverS { get; private set; } = double.NaN;
        public double LeadS { get; private set; } = double.NaN;
        public double WaveStartS { get; private set; } = double.NaN;
        public double AfterglowStartS { get; private set; } = double.NaN;
        public double EndS { get; private set; } = double.NaN;
        public double PredictedTotalS { get; private set; } = double.NaN;
        public int Predictions { get; private set; }
        public string HandoverReason { get; private set; } = "";
        public bool Paused { get; private set; }
        public string PauseReason { get; private set; } = "";
        public int PauseCount { get; private set; }
        public int ResumeCount { get; private set; }
        public Vector3 LastHeadOffset { get; private set; }
        public float AfterglowU { get; private set; }
        public float LastYLocal { get; private set; }
        public float LastYPaint { get; private set; }
        public DS44InputSample LastInput { get; private set; }
        public readonly List<string> Log = new List<string>();

        public const int OrderFlow = 5, OrderSeatBoat = 15;
        public const double Far = 1.0e6;

        Rigidbody rb;
        double lastCheck = double.NegativeInfinity;
        bool formationCaptured, agCaptured, frozePhysics, buoyWasStepping, clockWasRunning;
        Vector3 offPos, savedV, savedW, agPos0, agRelPos, agPaintPos, agPaintPosXr;
        Quaternion tilt0 = Quaternion.identity, tiltPaint = Quaternion.identity, agRot0, agRelRot, agPaintRot;
        float offYaw, agFov0, agPaintFov, outT, inT, agNear0, agFar0;
        double twCap;
        Vector2 endErr;
        float endYawErr;

        static float Smooth(float x) { x = Mathf.Clamp01(x); return x * x * (3f - 2f * x); }
        static float Smoother(float x) { x = Mathf.Clamp01(x); return x * x * x * (x * (x * 6f - 15f) + 10f); }
        static Quaternion YawQ(float deg) => Quaternion.Euler(0f, deg, 0f);
        static float YawOf(Quaternion q) { var f = q * Vector3.forward; return Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg; }

        void Start()
        {
            if (Application.isPlaying) Init();
        }

        /// <summary>読み込みと段の登録、座席の船を出発点へ置く。DS46ClockBus.Start（order −90）の後に呼ぶ。</summary>
        public void Init()
        {
            if (Ready) return;
            if (flowJson == null) throw new InvalidOperationException("DS47Flow：flowJson がありません");
            Cfg = DS47FlowConfig.Parse(flowJson.text);
            if (Cfg.timing.physicsDtS > 0f) Time.fixedDeltaTime = Cfg.timing.physicsDtS;
            rb = steer.GetComponent<Rigidbody>();
            steer.Init();
            steer.stepInFixedUpdate = false;       // 操船はこの部品の FixedUpdate が進める（入力と一時停止をここで持つ）
            buoyancy.stepInFixedUpdate = true;
            bus.Prepare();
            if (paintingSeatBoat != null && paintingSeatBoat.gameObject.activeSelf) paintingSeatBoat.gameObject.SetActive(false);
            if (leaveOverlay != null) leaveOverlay.SetActive(false);
            if (hmdCamera != null && !XRSettings.isDeviceActive && Cfg.afterglow.pcSeatVfovDeg > 0f) hmdCamera.fieldOfView = Cfg.afterglow.pcSeatVfovDeg;
            tiltPaint = Quaternion.Inverse(YawQ(YawOf(paintRootRot))) * paintRootRot;

            // 時計：引き継ぎまで大波は t = 0（待機のコマ）、終わりは引き継ぎで決める
            clock.waveStartSeconds = Far;
            clock.endSeconds = Far;
            RebuildEvents();
            if (placeAtStart) PlaceAtStart();
            clock.Register("flow", OrderFlow, OnFlow);
            clock.Register("seat_boat", OrderSeatBoat, OnSeatBoat);
            CurrentPhase = PhaseAt(clock.ExperienceSeconds);
            Ready = true;
            Log.Add("init exp=" + clock.ExperienceSeconds.ToString("F4") + " fixedDt=" + Time.fixedDeltaTime.ToString("R"));
        }

        void PlaceAtStart()
        {
            var fr = steer.Fr;
            var xz = fr.ToWorld(Cfg.start.u, Cfg.start.v);
            float yaw = fr.yawDeg + Cfg.start.yawOffsetDeg;
            float hNow = bus.boatWater != null ? bus.boatWater.HeightAt(new Vector3(xz.x, 0f, xz.y)) : 0f;
            float h = float.IsNaN(startWaterY) ? hNow : startWaterY;
            Log.Add("place h=" + h.ToString("F4") + " hAtStart=" + hNow.ToString("F4") + " tau=" + (bus.playback != null ? bus.playback.Tau.ToString("F4") : "-"));
            var p = new Vector3(xz.x, h - eqDraftM, xz.y);
            var q = YawQ(yaw);
            rb.isKinematic = false;
            rb.position = p; rb.rotation = q;
            steer.transform.SetPositionAndRotation(p, q);
            rb.linearVelocity = Vector3.zero; rb.angularVelocity = Vector3.zero;
        }

        /// <summary>出来事の表を作り直す：体験の秒に結び付いたものは今、引き継ぎ・大波・余韻に結び付いたものは引き継ぎの後に入れる。</summary>
        void RebuildEvents()
        {
            var ev = bus.events;
            if (ev == null) return;
            ev.Load();
            ev.entries.Clear();
            foreach (var e in Cfg.events)
            {
                double t;
                switch (e.anchor)
                {
                    case "experience": t = Math.Max(e.offset, clock.startSeconds + 1e-6); break;   // 初期化の時刻ちょうどは起こせないので、最初の進める段で起こす
                    case "handover": if (!HandedOver) continue; t = HandoverS + e.offset; break;
                    case "wave": if (!HandedOver) continue; t = WaveStartS + e.offset; break;
                    case "afterglow": if (!HandedOver) continue; t = AfterglowStartS + e.offset; break;
                    default: throw new InvalidOperationException("出来事の anchor が分かりません: " + e.anchor);
                }
                ev.entries.Add(new DS46EventTrack.Entry { id = e.id, t = t, kind = string.IsNullOrEmpty(e.kind) ? "once" : e.kind });
            }
            ev.entries.Sort((a, b) => a.t.CompareTo(b.t));
        }

        public Phase PhaseAt(double exp)
        {
            if (!HandedOver) return Phase.Intro;
            if (exp < WaveStartS) return Phase.Approach;
            if (exp < WaveStartS + Cfg.timing.formationS) return Phase.Formation;
            if (exp < AfterglowStartS) return Phase.Hold;
            if (exp < EndS) return Phase.Afterglow;
            return Phase.End;
        }

        double PredictTotal(double exp, out double T)
        {
            var p = rb.position; var v = rb.linearVelocity;
            var tr = new DS44Trajectory(steer.Cfg, new Vector2(p.x, p.z), new Vector2(v.x, v.z), steer.HeadingDeg, rb.angularVelocity.y * Mathf.Rad2Deg, steer.Fr);
            T = tr.T;
            Predictions++;
            var tm = Cfg.timing;
            return exp + (tr.T - tm.formationS) + tm.formationS + tm.holdS + tm.afterglowMoveS + tm.afterglowDwellS;
        }

        // ---------------------------------------------------------------- 共通時計の段
        public string LastError { get; private set; } = "";
        public int Errors { get; private set; }

        void OnFlow(GWClock c, GWClock.Step st)
        {
            try { OnFlowInner(st); }
            catch (Exception ex) { Errors++; LastError = ex.GetType().Name + ": " + ex.Message + " @ " + ex.StackTrace; if (Errors <= 3) { Log.Add("error " + LastError); Debug.LogException(ex); } }
        }

        void OnFlowInner(GWClock.Step st)
        {
            double exp = st.experience;
            if (!HandedOver && st.kind == GWClock.StepKind.Advance && !Paused)
            {
                var tm = Cfg.timing;
                bool due = exp >= tm.introMaxS;
                if (!due && exp >= tm.introMinS && exp - lastCheck >= tm.handoverCheckEveryS - 1e-9)
                {
                    lastCheck = exp;
                    PredictedTotalS = PredictTotal(exp, out _);
                    if (PredictedTotalS >= tm.targetTotalS) { due = true; HandoverReason = "target"; }
                }
                else if (due) HandoverReason = "introMax";
                if (due) DoHandover(exp);
            }
            var ph = PhaseAt(exp);
            if (ph != CurrentPhase) { Log.Add("phase " + CurrentPhase + "→" + ph + " exp=" + exp.ToString("F4")); CurrentPhase = ph; }
        }

        void DoHandover(double exp)
        {
            var tm = Cfg.timing;
            PredictedTotalS = PredictTotal(exp, out _);
            LeadS = steer.Handover();
            HandedOver = true;
            HandoverS = exp;
            WaveStartS = exp + LeadS;
            AfterglowStartS = WaveStartS + tm.formationS + tm.holdS;
            EndS = AfterglowStartS + tm.afterglowMoveS + tm.afterglowDwellS;
            clock.waveStartSeconds = WaveStartS;
            clock.endSeconds = EndS;
            var tr = steer.Traj;
            var end = tr.Eval(tr.T);
            endErr = steer.Fr.o - end.pos;
            endYawErr = Mathf.DeltaAngle((float)end.yawDeg, steer.Fr.yawDeg);
            RebuildEvents();
            Log.Add("handover exp=" + exp.ToString("F4") + " lead=" + LeadS.ToString("F4") + " T=" + tr.T.ToString("F4") + " waveStart=" + WaveStartS.ToString("F4") + " end=" + EndS.ToString("F4") + " reason=" + HandoverReason);
        }

        /// <summary>形成と保持の座席の船の姿勢（時計の関数。tw = 体験の時刻 − 形成の始まり）。</summary>
        public void ScriptPose(double exp, double wave, double tau, out Vector3 pos, out float yaw, out Quaternion tiltT, out float wAtt)
        {
            var tm = Cfg.timing; var fp = Cfg.formationPose;
            var tr = steer.Traj;
            double tw = exp - WaveStartS;
            double ts = Math.Min(exp - HandoverS, tr.T);
            var smp = tr.Eval(ts);
            float wE = Smooth((float)(tw / tm.formationS));
            var xz = smp.pos + endErr * wE;
            yaw = (float)smp.yawDeg + endYawErr * wE;
            wAtt = Smooth((float)((wave - fp.attStartWaveS) / Math.Max(1e-6, fp.attEndWaveS - fp.attStartWaveS)));
            // 高さ：形成の前半はその場の水（船用水面データの下側の一価の面）に浮く高さ、attStart〜attEnd で原画の置き方 ＋ 設計30 の支えの Δ(t) へ移す
            float yPaint = paintRootPos.y + (seatHeave != null ? (float)seatHeave.DeltaAt(wave, tau) : 0f);
            float yLocal = bus.boatWater != null ? bus.boatWater.HeightAt(new Vector3(xz.x, 0f, xz.y)) - eqDraftM : yPaint;
            LastYLocal = yLocal; LastYPaint = yPaint;
            pos = new Vector3(xz.x, Mathf.Lerp(yLocal, yPaint, wAtt), xz.y);
            tiltT = tiltPaint;
        }

        void OnSeatBoat(GWClock c, GWClock.Step st)
        {
            try { OnSeatBoatInner(st); }
            catch (Exception ex) { Errors++; LastError = ex.GetType().Name + ": " + ex.Message + " @ " + ex.StackTrace; if (Errors <= 3) { Log.Add("error " + LastError); Debug.LogException(ex); } }
        }

        void OnSeatBoatInner(GWClock.Step st)
        {
            if (!HandedOver || st.experience < WaveStartS) return;
            double exp = st.experience, tw = exp - WaveStartS;
            double tau = bus.playback != null ? bus.playback.Tau : 0.0;
            ScriptPose(exp, st.wave, tau, out var sp, out var syaw, out var tiltT, out var wAtt);
            if (!formationCaptured)
            {
                // 物理の段の後の姿勢は、次の段の時刻の姿勢（1 段先）。つなぎ目のコマで水平に止まって見えないよう、水平の速度 × 1 段だけ先の位置から差を取る
                var pv = rb.linearVelocity;
                var pp = rb.position + new Vector3(pv.x, 0f, pv.z) * Time.fixedDeltaTime; var pq = rb.rotation;
                float pyaw = YawOf(pq);
                tilt0 = Quaternion.Inverse(YawQ(pyaw)) * pq;
                offPos = pp - sp;
                offYaw = Mathf.DeltaAngle(syaw, pyaw);
                twCap = tw;
                rb.isKinematic = true;
                buoyancy.stepInFixedUpdate = false;
                formationCaptured = true;
                Log.Add("formation_capture exp=" + exp.ToString("F4") + " tw=" + tw.ToString("F4") + " offPos=" + offPos.ToString("F4") + " offYaw=" + offYaw.ToString("F3"));
            }
            float decay = 1f - Smooth((float)((tw - twCap) / Math.Max(1e-6, Cfg.formationPose.offsetDecayS)));
            Vector3 pos; Quaternion rot;
            if (tw >= Cfg.timing.formationS && decay <= 0f)
            {
                pos = paintRootPos; rot = paintRootRot;   // t* 以後は原画の置き方そのもの（114）
            }
            else
            {
                pos = sp + offPos * decay;
                rot = YawQ(syaw + offYaw * decay) * Quaternion.Slerp(tilt0, tiltT, wAtt);
            }
            rb.position = pos; rb.rotation = rot;
            steer.transform.SetPositionAndRotation(pos, rot);
        }

        // ---------------------------------------------------------------- 物理の段
        DS44InputSample ReadInput() => inputOverride != null ? inputOverride() : DS44Input.ReadLive();

        void FixedUpdate()
        {
            if (!Ready || Paused) return;
            if (HandedOver && clock.ExperienceSeconds >= WaveStartS) return;   // 形成から先は時計の姿勢
            if (clock.State != GWClock.RunState.Running) return;
            var inp = steer.CurrentMode == DS44BoatSteer.Mode.Steering ? ReadInput() : default;
            LastInput = inp;
            steer.Step(Time.fixedDeltaTime, inp);
        }

        // ---------------------------------------------------------------- 一時停止（観賞の位置から外れた時、設計50 の停止の切替）
        public void Pause(string reason)
        {
            if (Paused) return;
            Paused = true; PauseReason = reason; PauseCount++;
            clockWasRunning = clock.State == GWClock.RunState.Running;
            clock.Stop();
            if (!rb.isKinematic)
            {
                savedV = rb.linearVelocity; savedW = rb.angularVelocity;
                buoyWasStepping = buoyancy.stepInFixedUpdate;
                buoyancy.stepInFixedUpdate = false;
                rb.isKinematic = true;
                frozePhysics = true;
            }
            if (leaveOverlay != null) leaveOverlay.SetActive(reason == "leave");
            Log.Add("pause reason=" + reason + " exp=" + clock.ExperienceSeconds.ToString("F4"));
        }

        public void Resume()
        {
            if (!Paused) return;
            if (frozePhysics)
            {
                rb.isKinematic = false;
                rb.linearVelocity = savedV; rb.angularVelocity = savedW;
                buoyancy.stepInFixedUpdate = buoyWasStepping;
                frozePhysics = false;
            }
            if (leaveOverlay != null) leaveOverlay.SetActive(false);
            Paused = false; ResumeCount++;
            if (clockWasRunning) clock.Resume();
            Log.Add("resume exp=" + clock.ExperienceSeconds.ToString("F4"));
        }

        // ---------------------------------------------------------------- 乗客の後（観賞の位置・余韻）
        void LateUpdate()
        {
            if (!Ready) return;
            double exp = clock.ExperienceSeconds;
            var ph = PhaseAt(exp);
            if (ph == Phase.Afterglow || ph == Phase.End) { if (Paused && PauseReason == "leave") Resume(); Afterglow(exp); return; }
            LeaveMonitor(Time.deltaTime);
        }

        void LeaveMonitor(float dt)
        {
            if (hmdCamera == null || rider == null) return;
            var d = hmdCamera.transform.position - rider.transform.position;
            LastHeadOffset = d;
            var L = Cfg.leave;
            bool outside = new Vector2(d.x, d.z).magnitude > L.radiusHM || Mathf.Abs(d.y) > L.radiusVM;
            if (outside) { outT += dt; inT = 0f; } else { inT += dt; outT = 0f; }
            if (!Paused && outside && outT >= L.graceS) Pause("leave");
            else if (Paused && PauseReason == "leave" && !outside && inT >= L.returnGraceS) Resume();
        }

        void Afterglow(double exp)
        {
            var ag = Cfg.afterglow;
            var root = rider.transform;
            bool xr = XRSettings.isDeviceActive;
            if (!agCaptured)
            {
                rider.stepInLateUpdate = false;    // 乗客の揺れの解を止め、視点はこの部品が動かす
                agPos0 = root.position; agRot0 = root.rotation;
                agFov0 = hmdCamera.fieldOfView; agNear0 = hmdCamera.nearClipPlane; agFar0 = hmdCamera.farClipPlane;
                agRelRot = Quaternion.Inverse(root.rotation) * hmdCamera.transform.rotation;
                agRelPos = Quaternion.Inverse(root.rotation) * (hmdCamera.transform.position - root.position);
                var pc = paintingCamera.transform;
                agPaintRot = pc.rotation * Quaternion.Inverse(agRelRot);
                agPaintPos = pc.position - agPaintRot * agRelPos;
                agPaintPosXr = pc.position - agRot0 * agRelPos;   // XR：向きは本人のまま、目だけを原画の視点へ
                agPaintFov = paintingCamera.fieldOfView;
                agCaptured = true;
                Log.Add("afterglow_capture exp=" + exp.ToString("F4") + " fov0=" + agFov0.ToString("F2") + " xr=" + xr);
            }
            float u = Mathf.Clamp01((float)((exp - AfterglowStartS) / Math.Max(1e-6, Cfg.timing.afterglowMoveS)));
            AfterglowU = u;
            float e = Smoother(u);
            Vector3 pos; Quaternion rot;
            var goal = xr && !ag.rotateRigInXr ? agPaintPosXr : agPaintPos;
            if (u >= 1f) { pos = goal; rot = xr && !ag.rotateRigInXr ? agRot0 : agPaintRot; }
            else
            {
                pos = Vector3.Lerp(agPos0, goal, e) + Vector3.up * (ag.arcUpM * Mathf.Sin(Mathf.PI * e));
                if (xr && !ag.rotateRigInXr) rot = agRot0;
                else
                {
                    var bl = ag.boatLookLocal != null && ag.boatLookLocal.Length == 3 ? new Vector3(ag.boatLookLocal[0], ag.boatLookLocal[1], ag.boatLookLocal[2]) : Vector3.zero;
                    var target = steer.transform.TransformPoint(bl);
                    var camPos = pos + agRot0 * agRelPos;
                    var dir = target - camPos;
                    var look = dir.sqrMagnitude > 1e-6f ? Quaternion.LookRotation(dir, Vector3.up) * Quaternion.Inverse(agRelRot) : agRot0;
                    float a = Mathf.Max(1e-3f, ag.lookBoatUntil);
                    rot = e < a ? Quaternion.Slerp(agRot0, look, Smooth(e / a)) : Quaternion.Slerp(look, agPaintRot, Smooth((e - a) / (1f - a)));
                }
            }
            root.SetPositionAndRotation(pos, rot);
            if (!xr) hmdCamera.fieldOfView = u >= 1f ? agPaintFov : Mathf.Lerp(agFov0, agPaintFov, e);
            // 近い面・遠い面も原画の視点の値へ（着いた後の画が原画視点の描画と同じになる。線の太さは射影の値で変わる）
            hmdCamera.nearClipPlane = u >= 1f ? paintingCamera.nearClipPlane : Mathf.Lerp(agNear0, paintingCamera.nearClipPlane, e);
            hmdCamera.farClipPlane = u >= 1f ? paintingCamera.farClipPlane : Mathf.Lerp(agFar0, paintingCamera.farClipPlane, e);
        }

    }
}
