using System;
using UnityEngine;

namespace GreatWave.Design45
{
    // 設計45：乗客の揺れ（設計書 §7.3 の RiderComfortRoot）。この部品を RiderComfortRoot に付ける。
    //   場面の構造（設計書 §7.3）：物理の船（BoatSimulationRoot。設計42〜44）と RiderComfortRoot は兄弟（どちらも親を持たない）。
    //     RiderComfortRoot（この部品。位置 = 乗客の目の点、回転 = 乗客の向き）
    //     └─ XR Origin（座席リセットの時だけ、この部品が局所の姿勢を書く）
    //        └─ Camera Offset（XR Origin が高さを決める。この部品は読むだけ）
    //           └─ HMD Camera（頭部追跡（TrackedPoseDriver）だけが局所の姿勢を書く。この部品は読むだけで、平滑化・逆回転・演出の揺れを上書きしない）
    //   段（ds45_comfort.json）：L0 水平維持（上下動最小）→ L1 弱い上下動 → L2 旋回 → L3 傾斜。キー 1〜4／十字キーで切り替え、R／Select で座席リセット。
    //   船は読むだけ（boatRoot の位置と回転）。船の物理（DS42Buoyancy・DS44BoatSteer）には触れない。
    [DefaultExecutionOrder(90)]
    public class DS45RiderComfort : MonoBehaviour
    {
        public TextAsset configJson;
        [Tooltip("物理の船の根（BoatSimulationRoot。読むだけ）")]
        public Transform boatRoot;
        [Tooltip("船の根の局所の座席の目の点（設計43 の ds43_boats.json の eyeLocal）")]
        public Vector3 seatEyeLocal;
        [Tooltip("XR Origin（座席リセットの時だけ局所の姿勢を書く）")]
        public Transform xrOrigin;
        [Tooltip("Camera Offset（読むだけ）")]
        public Transform cameraOffset;
        [Tooltip("HMD Camera（読むだけ。局所の姿勢は頭部追跡に任せる）")]
        public Transform hmdCamera;
        [Tooltip("-1 なら設定の defaultLevel")]
        public int startLevel = -1;
        [Tooltip("LateUpdate で今の機器を読んで進める（場面で遊ぶ時）。検査のように外から Step を呼ぶ時は切る")]
        public bool stepInLateUpdate = true;
        public bool readInput = true;

        public DS45ComfortCfg Cfg { get; private set; }
        public DS45ComfortSolver Solver { get; private set; }
        public DS45ComfortInput ComfortInput { get; private set; }
        public int Level => Solver != null ? Solver.Level : -1;
        public int ResetCount { get; private set; }

        void Awake() { Init(); }

        public void Init()
        {
            if (Solver != null) return;
            if (configJson == null) throw new InvalidOperationException("DS45RiderComfort：configJson がありません");
            if (boatRoot == null) throw new InvalidOperationException("DS45RiderComfort：boatRoot がありません");
            if (boatRoot.IsChildOf(transform) || transform.IsChildOf(boatRoot))
                throw new InvalidOperationException("DS45RiderComfort：物理の船と RiderComfortRoot は兄弟にする（船の回転が二重に乗客へ掛からないように。設計書 §7.3）");
            Cfg = DS45ComfortCfg.Parse(configJson.text);
            Solver = new DS45ComfortSolver(Cfg, startLevel >= 0 ? startLevel : Cfg.defaultLevel);
            ComfortInput = new DS45ComfortInput();
        }

        void LateUpdate()
        {
            if (!stepInLateUpdate) return;
            if (readInput) Apply(ComfortInput.ReadLive());
            Step(Time.deltaTime);
        }

        /// <summary>船の今の姿勢から乗客の姿勢を 1 回進め、この部品の Transform（RiderComfortRoot）へ書く。</summary>
        public void Step(float dt)
        {
            Init();
            var p = Solver.Step(dt, boatRoot.TransformPoint(seatEyeLocal), boatRoot.rotation);
            transform.SetPositionAndRotation(p.pos, p.rot);
        }

        public void Apply(DS45ComfortCmd c)
        {
            Init();
            if (c.level >= 0) Solver.SetLevel(c.level);
            if (c.delta != 0) Solver.SetLevel(Solver.Level + c.delta);
            if (c.reset) ResetSeat();
        }

        public bool SetLevel(int level) { Init(); return Solver.SetLevel(level); }

        /// <summary>
        /// 座席リセット（H7 のアプリ側）：乗客の正面を座席の正面へ戻し、今の頭の位置と水平の向きを座席の目と正面へ合わせる。
        /// 書くのは XR Origin の局所の姿勢だけ。HMD Camera と Camera Offset は読むだけ。
        /// </summary>
        public void ResetSeat()
        {
            Init();
            Solver.ResetYaw();
            if (xrOrigin != null && cameraOffset != null && hmdCamera != null)
            {
                var o = DS45ComfortSolver.RecenterOrigin(cameraOffset.localPosition, cameraOffset.localRotation, hmdCamera.localPosition, hmdCamera.localRotation);
                xrOrigin.SetLocalPositionAndRotation(o.pos, o.rot);
            }
            ResetCount++;
        }
    }
}
