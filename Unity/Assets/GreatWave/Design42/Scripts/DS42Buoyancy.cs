using System;
using UnityEngine;

namespace GreatWave.Design42
{
    // 設計42：船底の浮力点で船を浮かべる（静水の重量・排水容積・重心）。
    // 値は Tools/GWWaveGen/ds42/ds42_hydro.py が設計41 の浮力用の閉じた船体から作った ds42_buoyancy_points.json（TextAsset）。
    //   ・質量・重心・慣性（部品ごとの推定の和）を Rigidbody へ入れる（自動の重心・慣性は使わない）。
    //   ・浮力点 10 点（5 断面 × 左右）。各点は船体の区画を受け持ち、その点での水面の高さ（根の局所の y。船の上向きに沿って測る）
    //     ごとの区画の排水容積 V・浮心 C・水線面積 A の表を持つ。力は 水密度 × 重力 × V を鉛直上向きに、区画の浮心へ加える。
    //   ・抵抗（数値の条件）：点ごとの鉛直の速度に比例する減衰（水線面積の比で配る）、重心での水平の抵抗、首振りの減衰。
    // この部品を付ける GameObject（物理の根）は縮尺 1、原点は船体中央の船底、+z 船首、+y 上、+x 右舷。表示のモデルは子に縮尺 s で置く。
    // 静水での合わせ方と記録は Docs/Progress/Design_42_ja.md。頭部追跡・座席（RiderComfortRoot）には触れない（設計45）。
    [RequireComponent(typeof(Rigidbody))]
    public class DS42Buoyancy : MonoBehaviour
    {
        [Serializable]
        public class Config
        {
            public string schema;
            public float rho, g, scale, massKg;
            public float[] cgLocal, inertiaDiag, inertiaRot;
            public float levelMin, levelStep;
            public int levelCount, pointCount;
            public float[] pointPos, tabV, tabC, tabA;
            public float dampHeaveNsPerM, areaRefM2, dragHorizontalPerS, dragYawPerS;
            public float eqDraftMidM, eqTrimDeg, eqHeelDeg, eqKeelHeightM;
            public float[] periodsS, stiffness, inertiaWorldAxes;
        }

        public TextAsset pointsJson;
        public DS42Water water;
        [Tooltip("FixedUpdate で自分で進める（場面で遊ぶ時）。検査のように外から Step を呼ぶ時は切る")]
        public bool stepInFixedUpdate = true;
        [Tooltip("外から与える力のモーメント（世界、N·m）。検査の静的な傾け（人が船縁へ寄った時の代わり）に使う")]
        public Vector3 externalTorque;

        public Config Cfg { get; private set; }
        Rigidbody rb;
        Vector3[] pts;

        // 最後の Step の値（記録用）
        public float LastBuoyancyN { get; private set; }
        public float LastDampingN { get; private set; }
        public float LastVolumeM3 { get; private set; }
        public int LastWetPoints { get; private set; }
        public Vector3 LastCenterOfBuoyancy { get; private set; }

        void Awake() { Init(); }

        public void Init()
        {
            if (Cfg != null) return;
            if (pointsJson == null) throw new InvalidOperationException("DS42Buoyancy：pointsJson がありません");
            Cfg = JsonUtility.FromJson<Config>(pointsJson.text);
            if (Cfg.pointPos.Length != Cfg.pointCount * 3 || Cfg.tabV.Length != Cfg.pointCount * Cfg.levelCount || Cfg.tabC.Length != Cfg.pointCount * Cfg.levelCount * 3)
                throw new InvalidOperationException("DS42Buoyancy：表の長さが合いません");
            pts = new Vector3[Cfg.pointCount];
            for (int k = 0; k < Cfg.pointCount; k++) pts[k] = new Vector3(Cfg.pointPos[3 * k], Cfg.pointPos[3 * k + 1], Cfg.pointPos[3 * k + 2]);
            ApplyMass();
        }

        // 質量・重心・慣性を Rigidbody へ入れ直す（子に衝突形状を足した後にも呼ぶ。自動の重心・慣性は使わない）
        public void ApplyMass()
        {
            rb = GetComponent<Rigidbody>();
            rb.mass = Cfg.massKg;
            rb.automaticCenterOfMass = false;
            rb.centerOfMass = new Vector3(Cfg.cgLocal[0], Cfg.cgLocal[1], Cfg.cgLocal[2]);
            rb.automaticInertiaTensor = false;
            rb.inertiaTensor = new Vector3(Cfg.inertiaDiag[0], Cfg.inertiaDiag[1], Cfg.inertiaDiag[2]);
            rb.inertiaTensorRotation = new Quaternion(Cfg.inertiaRot[0], Cfg.inertiaRot[1], Cfg.inertiaRot[2], Cfg.inertiaRot[3]);
            rb.linearDamping = 0f;
            rb.angularDamping = 0f;
            rb.useGravity = true;
            rb.sleepThreshold = 0f;
            rb.maxAngularVelocity = 50f;
        }

        public Vector3 PointLocal(int k) => pts[k];

        float Tab(float[] tab, int k, float level)
        {
            int n = Cfg.levelCount, b = k * n;
            float u = (level - Cfg.levelMin) / Cfg.levelStep;
            if (u <= 0f) return tab[b];
            if (u >= n - 1) return tab[b + n - 1];
            int i = (int)u; float f = u - i;
            return tab[b + i] * (1f - f) + tab[b + i + 1] * f;
        }

        Vector3 TabC(int k, float level)
        {
            int n = Cfg.levelCount, b = k * n;
            float u = Mathf.Clamp((level - Cfg.levelMin) / Cfg.levelStep, 0f, n - 1.0001f);
            int i = (int)u; float f = u - i;
            int p = 3 * (b + i), q = 3 * (b + i + 1);
            return new Vector3(Cfg.tabC[p] * (1f - f) + Cfg.tabC[q] * f, Cfg.tabC[p + 1] * (1f - f) + Cfg.tabC[q + 1] * f, Cfg.tabC[p + 2] * (1f - f) + Cfg.tabC[q + 2] * f);
        }

        void FixedUpdate()
        {
            if (stepInFixedUpdate) Step(Time.fixedDeltaTime);
        }

        // 1 段分の力を Rigidbody へ加える（物理の段の前に呼ぶ）
        public void Step(float dt)
        {
            Init();
            if (water == null) return;
            var up = transform.up;
            float upY = Mathf.Max(up.y, 0.1f);
            float rg = Cfg.rho * Cfg.g;
            float sumF = 0f, sumD = 0f, sumV = 0f; Vector3 mom = Vector3.zero; int wet = 0;
            for (int k = 0; k < pts.Length; k++)
            {
                var pl = pts[k];
                var pw = transform.TransformPoint(pl);
                float lvl = pl.y + (water.HeightAt(pw) - pw.y) / upY;   // その点での水面の高さ（根の局所の y）
                float v = Tab(Cfg.tabV, k, lvl);
                if (v <= 0f) continue;
                wet++;
                var cw = transform.TransformPoint(TabC(k, lvl));
                float f = rg * v;
                rb.AddForceAtPosition(Vector3.up * f, cw, ForceMode.Force);
                float a = Tab(Cfg.tabA, k, lvl);
                float c = Cfg.dampHeaveNsPerM * a / Cfg.areaRefM2;
                float fd = -c * rb.GetPointVelocity(pw).y;
                rb.AddForceAtPosition(Vector3.up * fd, pw, ForceMode.Force);
                sumF += f; sumD += fd; sumV += v; mom += cw * v;
            }
            if (wet > 0)
            {
                var vel = rb.linearVelocity;
                rb.AddForce(new Vector3(-vel.x, 0f, -vel.z) * (Cfg.massKg * Cfg.dragHorizontalPerS), ForceMode.Force);
                float wy = rb.angularVelocity.y;
                rb.AddTorque(new Vector3(0f, -wy * Cfg.inertiaWorldAxes[1] * Cfg.dragYawPerS, 0f), ForceMode.Force);
            }
            if (externalTorque != Vector3.zero) rb.AddTorque(externalTorque, ForceMode.Force);
            LastBuoyancyN = sumF; LastDampingN = sumD; LastVolumeM3 = sumV; LastWetPoints = wet;
            LastCenterOfBuoyancy = sumV > 0f ? mom / sumV : transform.position;
        }

        // 検査用：閉じたメッシュ（世界の頂点）の、水平の水面 y = level の下の容積と浮心。
        // 三角形を水面で切り、水面上の点を頂点にした四面体の和（蓋の面は容積 0）。符号は全体の容積で決める。
        public static float SubmergedVolume(Vector3[] w, int[] tri, float level, out Vector3 centroid)
        {
            var o = new Vector3(w[0].x, level, w[0].z);
            double vol = 0; var m = Vector3.zero;
            var poly = new Vector3[4];
            for (int i = 0; i < tri.Length; i += 3)
            {
                int n = 0;
                for (int e = 0; e < 3; e++)
                {
                    var p = w[tri[i + e]]; var q = w[tri[i + (e + 1) % 3]];
                    float dp = p.y - level, dq = q.y - level;
                    if (dp <= 0f) poly[n++] = p;
                    if ((dp < 0f) != (dq < 0f) && dp != dq) poly[n++] = p + (q - p) * (dp / (dp - dq));
                }
                for (int j = 1; j < n - 1; j++)
                {
                    var a = poly[0] - o; var b = poly[j] - o; var c = poly[j + 1] - o;
                    float v = Vector3.Dot(a, Vector3.Cross(b, c)) / 6f;
                    vol += v; m += v * (a + b + c) / 4f;
                }
            }
            centroid = vol != 0 ? m / (float)vol + o : o;
            return (float)vol;
        }
    }
}
