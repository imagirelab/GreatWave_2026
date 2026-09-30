using UnityEngine;

namespace GreatWave.Design45
{
    public struct DS45Pose
    {
        public Vector3 pos;
        public Quaternion rot;
    }

    // 設計45：乗客へ伝える揺れの計算（MonoBehaviour を持たない純粋なクラス。場面の部品と検査が同じものを使う）。
    //   入力：船の座席の目の点（世界）と船の根の回転（BoatSimulationRoot。読むだけ）。
    //   出力：RiderComfortRoot の姿勢（位置 = 乗客の目の点、回転 = 乗客の向き）。HMD Camera の局所の姿勢には触れない。
    //   ・位置：船の目の点を 2 次の追従（臨界減衰。水平は速度も追うので等速では遅れない。上下の速度の先回りは betaV 倍）で追い、差 e（速い成分）を
    //     上下は (1 − kV)、水平は全段 1 の割合で打ち消す。打ち消す量は船の枠（船の根の回転）で測って柔らかく頭打ちにする：
    //     船の上向きの成分は上 maxDevUpM・下 maxDevDownM、船の水平の成分は maxDevHM（修正：乗客が座席に座ったままでいるため。
    //     座席の目は船縁の上端より 0.149 m 上（設計41）なので、下へ 0.10 m までなら目は船縁の上に残る）。
    //     つまり、遅い上下（大波に持ち上げられるなど）は全段で渡り、速い上下は段ごとに kV の割合だけ、座席の枠の中で渡る。
    //   ・旋回：yawFollow の段は船の首振りに付いて回る（座席の正面 = 船首 + seatYawOffset）。そうでない段は世界に固定。
    //     段を切り替えた時は、今の向きから続ける（向きを跳ばさない。勝手に回さない）。向きを座席の正面へ戻すのは ResetYaw だけ。
    //   ・傾斜：船の上向きの傾き（世界の上向きからの角、軸つき）を平滑化し、kTilt 倍して tiltMax で柔らかく頭打ち。
    //   ・段の切り替え：kV・kTilt・tiltMax を blendS 秒で移す（smoothstep）。
    public class DS45ComfortSolver
    {
        public readonly DS45ComfortCfg Cfg;
        public int Level { get; private set; }
        public bool Initialized => init;
        public float BlendW => blendT >= Cfg.blendS ? 1f : Smooth(blendT / Cfg.blendS);

        // 最後の Step の値（記録用）
        public DS45Pose Last;
        public float LastBoatYawDeg, LastYawDeg, LastBoatTiltDeg, LastTiltDeg, LastDevV, LastDevH, LastKV, LastKTilt, LastTiltMax;   // LastDevV・LastDevH は船の枠（上向き・水平）

        bool init;
        Vector3 ps, vs, prevEye;        // 目の点の遅い成分・その速度・前の段の船の目
        Vector2 tf, tfv;                // 傾きのベクトル（世界の x・z。向き = 軸、長さ = 角 rad）と速度
        float blendT = float.PositiveInfinity;
        float fkV, fkTilt, fTiltMax;    // 切り替えの前の値
        float yawRef, yawOff;           // 世界に固定の向き、船に付く向きの差

        public DS45ComfortSolver(DS45ComfortCfg cfg, int level)
        {
            Cfg = cfg;
            Level = Mathf.Clamp(level, 0, 3);
        }

        static float Smooth(float x) { x = Mathf.Clamp01(x); return x * x * (3f - 2f * x); }
        static float SoftClamp(float x, float m) => m * (float)System.Math.Tanh(x / m);

        void Eff(out float kV, out float kTilt, out float tiltMax)
        {
            var L = Cfg.levels[Level];
            if (blendT >= Cfg.blendS) { kV = L.kV; kTilt = L.kTilt; tiltMax = L.tiltMaxDeg; return; }
            float w = Smooth(blendT / Cfg.blendS);
            kV = Mathf.Lerp(fkV, L.kV, w); kTilt = Mathf.Lerp(fkTilt, L.kTilt, w); tiltMax = Mathf.Lerp(fTiltMax, L.tiltMaxDeg, w);
        }

        /// <summary>段を切り替える（0〜3）。向きは今の向きから続ける。変わったら true。</summary>
        public bool SetLevel(int level)
        {
            level = Mathf.Clamp(level, 0, 3);
            if (level == Level) return false;
            Eff(out fkV, out fkTilt, out fTiltMax);
            if (init)
            {
                if (Cfg.levels[level].yawFollow) yawOff = LastYawDeg - LastBoatYawDeg;
                else yawRef = LastYawDeg;
            }
            Level = level;
            blendT = 0f;
            return true;
        }

        /// <summary>座席リセットの向きの部分：乗客の正面を座席の正面（船首 + seatYawOffset）へ戻す（利用者の操作の時だけ。瞬時）。</summary>
        public void ResetYaw()
        {
            if (!init) return;
            yawRef = LastBoatYawDeg + Cfg.seatYawOffsetDeg;
            yawOff = Cfg.seatYawOffsetDeg;
        }

        static Vector2 TiltVec(Vector3 up)
        {
            // 世界の上向き Y から船の上向き u への回転：軸 = Y × u = (u.z, 0, −u.x)、角 = atan2(|Y × u|, u.y)
            float s = Mathf.Sqrt(up.x * up.x + up.z * up.z);
            if (s < 1e-7f) return Vector2.zero;
            float ang = Mathf.Atan2(s, up.y);
            return new Vector2(up.z / s, -up.x / s) * ang;
        }

        public DS45Pose Step(float dt, Vector3 boatEye, Quaternion boatRot)
        {
            var f = boatRot * Vector3.forward;
            float by = Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg;
            var tb = TiltVec(boatRot * Vector3.up);
            if (!init)
            {
                ps = boatEye; vs = Vector3.zero; prevEye = boatEye;
                tf = tb; tfv = Vector2.zero;
                yawRef = by + Cfg.seatYawOffsetDeg; yawOff = Cfg.seatYawOffsetDeg;
                init = true;
            }
            else
            {
                by = LastBoatYawDeg + Mathf.DeltaAngle(LastBoatYawDeg, by);   // 巻き戻さずに続ける
                if (dt > 0f)
                {
                    blendT += dt;
                    var ve = (boatEye - prevEye) / dt;
                    float wV = Cfg.omegaV, wH = Cfg.omegaH, wT = Cfg.omegaTilt;
                    int n = Mathf.Max(1, Mathf.CeilToInt(dt * Mathf.Max(wV, Mathf.Max(wH, wT)) / 0.05f));
                    float h = dt / n;
                    for (int i = 0; i < n; i++)
                    {
                        var a = new Vector3(
                            wH * wH * (boatEye.x - ps.x) + 2f * wH * (ve.x - vs.x),
                            wV * wV * (boatEye.y - ps.y) + 2f * wV * (Cfg.betaV * ve.y - vs.y),
                            wH * wH * (boatEye.z - ps.z) + 2f * wH * (ve.z - vs.z));
                        vs += a * h; ps += vs * h;
                        var at = wT * wT * (tb - tf) - 2f * wT * tfv;
                        tfv += at * h; tf += tfv * h;
                    }
                    prevEye = boatEye;
                }
            }
            Eff(out float kV, out float kTilt, out float tiltMax);
            var e = ps - boatEye;
            // 打ち消す量（世界）→ 船の枠へ直して頭打ち → 世界へ戻す（目が座席の枠から出ない。船が傾いても、水平のずれが船の上下へ回り込まない）
            var ob = Quaternion.Inverse(boatRot) * new Vector3(e.x, (1f - kV) * e.y, e.z);
            float dv = ob.y >= 0f ? SoftClamp(ob.y, Cfg.maxDevUpM) : SoftClamp(ob.y, Cfg.maxDevDownM);
            var dh = new Vector2(ob.x, ob.z);
            float m = dh.magnitude;
            if (m > 1e-9f) dh *= SoftClamp(m, Cfg.maxDevHM) / m;
            var pos = boatEye + boatRot * new Vector3(dh.x, dv, dh.y);

            float yaw = Cfg.levels[Level].yawFollow ? by + yawOff : yawRef;
            float th = tf.magnitude * Mathf.Rad2Deg;
            float tr = (tiltMax > 1e-4f && kTilt > 0f) ? SoftClamp(kTilt * th, tiltMax) : 0f;
            var tiltQ = (th > 1e-6f && tr != 0f) ? Quaternion.AngleAxis(tr, new Vector3(tf.x, 0f, tf.y) / tf.magnitude) : Quaternion.identity;
            var rot = tiltQ * Quaternion.Euler(0f, yaw, 0f);

            LastBoatYawDeg = by; LastYawDeg = yaw; LastBoatTiltDeg = tb.magnitude * Mathf.Rad2Deg; LastTiltDeg = tr;
            LastDevV = dv; LastDevH = dh.magnitude; LastKV = kV; LastKTilt = kTilt; LastTiltMax = tiltMax;
            Last = new DS45Pose { pos = pos, rot = rot };
            return Last;
        }

        /// <summary>
        /// 座席リセットの頭の部分：今の頭部追跡の局所の姿勢（読むだけ）から、XR Origin の RiderComfortRoot に対する局所の姿勢を決める。
        /// 頭の位置が RiderComfortRoot の原点（座席の目）に、頭の水平の向きが RiderComfortRoot の正面に来る。
        /// Camera Offset・HMD Camera の姿勢は書かない（XR Origin だけを動かす。Unity の XR Origin の考え方）。
        /// </summary>
        public static DS45Pose RecenterOrigin(Vector3 offsetLocalPos, Quaternion offsetLocalRot, Vector3 headLocalPos, Quaternion headLocalRot)
        {
            var hp = offsetLocalPos + offsetLocalRot * headLocalPos;
            var hf = offsetLocalRot * headLocalRot * Vector3.forward;
            float yaw = Mathf.Atan2(hf.x, hf.z) * Mathf.Rad2Deg;
            var r = Quaternion.Euler(0f, -yaw, 0f);
            return new DS45Pose { pos = -(r * hp), rot = r };
        }
    }
}
