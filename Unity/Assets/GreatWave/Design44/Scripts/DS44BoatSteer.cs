using System;
using GreatWave.Design42;
using UnityEngine;

namespace GreatWave.Design44
{
    // 設計44：座席の船の操船（前進・減速・旋回・停止）。設計書 §7.3 の BoatSimulationRoot（物理の根。Rigidbody ＋ 設計42 の DS42Buoyancy）に付ける。
    // 乗客の側（RiderComfortRoot・XR Origin・HMD Camera）には触れない（設計45）。
    //   ・操船（Steering）：導入と接近の区間。入力（DS44Input）→ 推力（重心）・抵抗（船首方向は 1 次＋2 次、横は強い 1 次）・首振りのモーメントと減衰・停止。
    //     浮力（上下・横揺れ・縦揺れ）は DS42Buoyancy のまま。設計42 の水平の抵抗と首振りの減衰は、この部品の抵抗で置き換える（0 にする）。
    //   ・範囲の外（DS44Range）：縁の内側の帯から、外向きの推力を弱め、内向きの加速度と外向きの速度の減衰を足す（柔らかく押し戻す）。船首は勝手に回さない。
    //   ・引き継ぎ（Handover）：形成の前に固定の軌道（DS44Trajectory）へ。軌道の間は段ごとに水平の位置と首の向きを軌道へ合わせ、水平の速度と首振りの速さを軌道の値にする。
    //     引き継ぎの瞬間の目標は、その時の位置・速度・向き・首振りの速さそのもの（向きと速さが跳ばない。D26）。
    // Play モードでは FixedUpdate で今の機器を読んで進める。検査（DS44SteerTest）は Step を外から呼ぶ。
    [DefaultExecutionOrder(70)]
    public class DS44BoatSteer : MonoBehaviour
    {
        public enum Mode { Steering, Trajectory, Arrived }

        public TextAsset configJson;
        public DS42Buoyancy buoyancy;
        [Tooltip("FixedUpdate で今の機器を読んで進める（場面で遊ぶ時）。検査のように外から Step を呼ぶ時は切る")]
        public bool stepInFixedUpdate = true;

        public DS44SteerConfig Cfg { get; private set; }
        public DS44Frame Fr { get; private set; }
        public DS44Range Rng { get; private set; }
        public Mode CurrentMode { get; private set; } = Mode.Steering;
        public DS44Trajectory Traj { get; private set; }
        public double TrajT { get; private set; }
        public float Mass { get; private set; }
        public float InertiaYaw { get; private set; }
        public float AFwd { get; private set; }

        // 最後の Step の値（記録用）
        public float LastSurge, LastSway, LastD, LastPhi, LastPushAccel, LastThrustAccel, LastDragAccel, LastYawTorque, LastThF, LastTuF;
        public bool LastWet;
        public DS44InputSample LastInput;
        public DS44TrajSample LastTarget;
        public Vector2 LastTrackErr;
        public float LastYawErrDeg;

        Rigidbody rb;
        float th, tu;

        void Awake() { Init(); }

        public void Init()
        {
            if (Cfg != null) return;
            if (configJson == null) throw new InvalidOperationException("DS44BoatSteer：configJson がありません");
            if (buoyancy == null) buoyancy = GetComponent<DS42Buoyancy>();
            if (buoyancy == null) throw new InvalidOperationException("DS44BoatSteer：DS42Buoyancy がありません");
            Cfg = DS44SteerConfig.Parse(configJson.text);
            Fr = new DS44Frame(Cfg.painting);
            Rng = new DS44Range(Cfg.range, Fr);
            buoyancy.Init();
            buoyancy.Cfg.dragHorizontalPerS = 0f;   // 水平の抵抗と首振りの減衰はこの部品が持つ
            buoyancy.Cfg.dragYawPerS = 0f;
            rb = GetComponent<Rigidbody>();
            Mass = buoyancy.Cfg.massKg;
            InertiaYaw = buoyancy.Cfg.inertiaWorldAxes[1];
            var d = Cfg.dyn;
            AFwd = d.dragLinPerS * d.vMaxFwd + d.dragQuadPerM * d.vMaxFwd * d.vMaxFwd;
        }

        /// <summary>水平の船首の向き ψ（度、+z から +x へ）。</summary>
        public float HeadingDeg
        {
            get { var f = transform.forward; return Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg; }
        }

        void FixedUpdate()
        {
            if (!stepInFixedUpdate) return;
            Step(Time.fixedDeltaTime, DS44Input.ReadLive());
        }

        /// <summary>引き継ぎ：今の状態から固定の軌道を作り、軌道の区間へ移る。返り値は形成を始めるまでの秒（T − formationS）。</summary>
        public double Handover()
        {
            Init();
            var p = rb.position; var v = rb.linearVelocity;
            Traj = new DS44Trajectory(Cfg, new Vector2(p.x, p.z), new Vector2(v.x, v.z), HeadingDeg, rb.angularVelocity.y * Mathf.Rad2Deg, Fr);
            TrajT = 0.0;
            CurrentMode = Mode.Trajectory;
            return Traj.Lead;
        }

        /// <summary>1 段分（物理の段の前に呼ぶ。浮力の Step の後）。</summary>
        public void Step(float dt, DS44InputSample inp)
        {
            Init();
            LastInput = inp;
            LastWet = buoyancy.LastWetPoints > 0;
            if (CurrentMode == Mode.Steering) StepSteer(dt, inp);
            else StepTrajectory(dt);
        }

        void StepSteer(float dt, DS44InputSample inp)
        {
            var d = Cfg.dyn; var R = Cfg.range;
            var fw = transform.forward;
            var f = new Vector2(fw.x, fw.z);
            if (f.sqrMagnitude < 1e-8f) f = Fr.f;
            f.Normalize();
            var sv = new Vector2(f.y, -f.x);                 // 右舷
            var v3 = rb.linearVelocity;
            var vel = new Vector2(v3.x, v3.z);
            float u = Vector2.Dot(vel, f), v = Vector2.Dot(vel, sv);
            float k = Mathf.Min(dt / Mathf.Max(d.inputLagS, 1e-6f), 1f);
            th += (inp.throttle - th) * k;
            tu += (inp.turn - tu) * k;
            float w = rb.angularVelocity.y;
            float N = 0f;
            Vector2 thrust;
            if (inp.stop)
            {
                float ab = Mathf.Clamp(-d.brakePerS * u, -d.brakeAccelMax, d.brakeAccelMax);
                thrust = f * ab * Mass;
                N += -InertiaYaw * d.brakeYawDampPerS * w;
                th = 0f;
            }
            else
            {
                float a = AFwd * th * (th >= 0f ? 1f : d.reverseRatio);
                thrust = f * a * Mass;
            }
            var pos = new Vector2(rb.position.x, rb.position.z);
            float dd = Rng.Sdf(pos);
            float phi = Rng.Phi(dd);
            var nIn = -Rng.Grad(pos);
            if (phi > 0f)
            {
                float o = Vector2.Dot(thrust, nIn);
                if (o < 0f) thrust -= nIn * o * Mathf.Min(phi, 1f);
            }
            var drag = -Mass * (d.dragLinPerS * u + d.dragQuadPerM * u * Mathf.Abs(u)) * f - Mass * d.latDragPerS * v * sv;
            var push = Vector2.zero;
            if (phi > 0f)
            {
                push += Mass * R.pushAccel * phi * nIn;
                float vo = Vector2.Dot(vel, nIn);
                if (vo < 0f) push += -Mass * R.pushDampPerS * phi * vo * nIn;
            }
            float ramp = d.yawAtRestRatio + (1f - d.yawAtRestRatio) * Mathf.Min(Mathf.Abs(u) / d.yawRefSpeed, 1f);
            if (!inp.stop) N += InertiaYaw * d.yawDampPerS * d.yawRateMaxDeg * Mathf.Deg2Rad * tu * ramp;
            N += -InertiaYaw * d.yawDampPerS * w;
            var F = thrust + drag + push;
            if (LastWet)
            {
                rb.AddForce(new Vector3(F.x, 0f, F.y), ForceMode.Force);
                rb.AddTorque(new Vector3(0f, N, 0f), ForceMode.Force);
            }
            LastSurge = u; LastSway = v; LastD = dd; LastPhi = phi;
            LastPushAccel = push.magnitude / Mass; LastThrustAccel = Vector2.Dot(thrust, f) / Mass; LastDragAccel = Vector2.Dot(drag, f) / Mass;
            LastYawTorque = N; LastThF = th; LastTuF = tu;
        }

        void StepTrajectory(float dt)
        {
            // 段の始めに、水平の位置と首の向きを軌道の今の値へ合わせる（前の段の間のずれを戻す。高さ・横揺れ・縦揺れは浮力のまま）。
            // 引き継ぎの段（TrajT = 0）の目標はその時の位置と向きそのものなので、合わせる量は 0（跳びなし）。
            // 速度は段の中ほどの軌道の値（水平）と首振りの速さに合わせる。
            var now = Traj.Eval(TrajT);
            var mid = Traj.Eval(TrajT + 0.5 * dt);
            var p = rb.position;
            var err = now.pos - new Vector2(p.x, p.z);
            float yerr = Mathf.DeltaAngle(HeadingDeg, (float)now.yawDeg);
            rb.position = new Vector3(now.pos.x, p.y, now.pos.y);
            rb.rotation = Quaternion.AngleAxis(yerr, Vector3.up) * rb.rotation;
            var v3 = rb.linearVelocity;
            rb.linearVelocity = new Vector3(mid.vel.x, v3.y, mid.vel.y);
            var w = rb.angularVelocity;
            rb.angularVelocity = new Vector3(w.x, (float)mid.yawRateDegPs * Mathf.Deg2Rad, w.z);
            LastTarget = now; LastTrackErr = err; LastYawErrDeg = yerr;
            var fw = transform.forward; var f = new Vector2(fw.x, fw.z).normalized;
            var vel = new Vector2(v3.x, v3.z);
            LastSurge = Vector2.Dot(vel, f); LastSway = Vector2.Dot(vel, new Vector2(f.y, -f.x));
            LastD = Rng.Sdf(new Vector2(p.x, p.z)); LastPhi = 0f; LastPushAccel = 0f; LastThrustAccel = 0f; LastDragAccel = 0f; LastYawTorque = 0f;
            TrajT += dt;
            if (TrajT >= Traj.T) CurrentMode = Mode.Arrived;
        }
    }
}
