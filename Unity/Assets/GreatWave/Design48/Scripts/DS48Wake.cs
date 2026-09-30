using System;
using System.Collections.Generic;
using GreatWave.Design43;
using GreatWave.Design47;
using UnityEngine;

namespace GreatWave.Design48
{
    [Serializable] public class DS48Color { public int[] srgb8; public string source, sourceSha256; }
    [Serializable] public class DS48Motion { public float smoothS, vMinMs, vFullMs, yawRateFullDegS, teleportM; }
    [Serializable] public class DS48Bow { public int stations; public float lenMinM, lenPerSpeedM, widthM, widthMinFrac, turnAsym, bowFullLenFrac, liftM; }
    [Serializable] public class DS48WakeParams { public float emitEveryS, lifeS, washHalfWidthM, washGrowMs, armWidthM, armAngleDeg, armTurnAsym, liftM; }
    [Serializable] public class DS48Gate { public float fadeStartWaveS, fadeEndWaveS, guardHeightM; }
    [Serializable] public class DS48ShaderParams { public float dashFreqPerM, acrossFreq, solidLife; }

    [Serializable]
    public class DS48Config
    {
        public string schema;
        public DS48Color color;
        public DS48Motion motion;
        public DS48Bow bow;
        public DS48WakeParams wake;
        public DS48Gate gate;
        public DS48ShaderParams shader;

        public static DS48Config Parse(string json)
        {
            var c = JsonUtility.FromJson<DS48Config>(json);
            if (c == null || c.schema != "GreatWave.DS48.wake/1" || c.color == null || c.motion == null || c.bow == null || c.wake == null || c.gate == null || c.shader == null)
                throw new InvalidOperationException("DS48Config：表が読めません（GreatWave.DS48.wake/1）");
            return c;
        }

        public Color PaletteWhite => new Color(color.srgb8[0] / 255f, color.srgb8[1] / 255f, color.srgb8[2] / 255f, 1f);
    }

    // 設計48：座席の船の船首の泡と航跡（調色板の白の平たいメッシュ。ds48_wake.json）。
    //   ・毎フレームの LateUpdate（order 96。進行役 DS47Flow の 95 の後、カメラの描画の前）に、船の根の姿勢の差を共通時計の体験の秒で割って
    //     速さ（前向きの成分）と旋回の角速度を出し（指数平滑）、船首の泡（左右の舷の平たい帯）と航跡（中央の泡の帯と、ケルビンの角の両側の腕）の網を作り直す。
    //   ・航跡は船尾の点の履歴（emitEveryS ごと、体験の秒）。一時停止の間は時計が止まるので、履歴も年齢も進まない（止まって見える）。
    //   ・高さは船用水面データ（設計43）の下側の一価の面 + 少しの持ち上げ。水面が guardHeightM より高い所、シートと 2 回以上交わる所（巻き込み・唇の下）、
    //     範囲の外の頂点は描かない（D48-2 の場所の守り）。
    //   ・大波の時刻 fadeStartWaveS から新しい泡を出さず、fadeEndWaveS までに全部の幅を 0 へ縮め、その後は網を空にして描かない（D48-2 の時刻の守り）。
    //     形成・保持・余韻・終わりには出ないので、原画視点（余韻の終わり）の画は設計47 と同じ。
    // 物理・操船・乗客・時計には触れない（読むだけ）。PC の Editor の Play で確かめた。HMD 実機は保留。
    [DefaultExecutionOrder(96)]
    public class DS48Wake : MonoBehaviour
    {
        public TextAsset configJson;
        public DS47Flow flow;
        [Tooltip("座席の船の根（DS47 の物理の根）")]
        public Transform boat;
        public DS43BoatWater water;
        public Material material;
        public MeshFilter meshFilter;
        public MeshRenderer meshRenderer;

        public DS48Config Cfg { get; private set; }
        public bool Ready { get; private set; }
        public float SpeedMs { get; private set; }
        public float YawRateDegS { get; private set; }
        public float Sv { get; private set; }
        public float Sr { get; private set; }
        public float Gate { get; private set; } = 1f;
        public bool Emitting { get; private set; }
        public int Samples => hist.Count;
        public int VisibleVerts { get; private set; }
        public int GuardHidden { get; private set; }
        public int OverhangHidden { get; private set; }
        public int OutsideHidden { get; private set; }
        public long GuardHiddenTotal { get; private set; }
        public float MaxVisibleY { get; private set; } = float.NaN;
        public float BowPortW { get; private set; }
        public float BowStbdW { get; private set; }
        public float BowLenM { get; private set; }
        public float ArmPortW { get; private set; }
        public float ArmStbdW { get; private set; }
        public float WashHalfW { get; private set; }
        public int Rebuilds { get; private set; }
        public int Teleports { get; private set; }
        public float BowZ { get; private set; }
        public float SternZ { get; private set; }
        public float HalfBeam { get; private set; }
        public string LastError { get; private set; } = "";
        public int Errors { get; private set; }
        /// <summary>Tick（速さ・網の作り直し）にかかった時間（ms。PC の記録用）。</summary>
        public double TickMsTotal { get; private set; }
        public double TickMsMax { get; private set; }
        public int Ticks { get; private set; }
        readonly System.Diagnostics.Stopwatch sw = new System.Diagnostics.Stopwatch();

        struct Sample { public Vector2 p, right; public float v, sv, sr, s; public double t; }
        readonly List<Sample> hist = new List<Sample>();
        readonly List<Vector3> vx = new List<Vector3>(4096);
        readonly List<Vector2> uv = new List<Vector2>(4096), uv2 = new List<Vector2>(4096);
        readonly List<int> tri = new List<int>(8192);
        readonly List<float> hits = new List<float>(16);
        Mesh mesh;
        bool havePrev;
        Vector3 prevPos;
        float prevYaw;
        double prevExp, lastEmit = double.NegativeInfinity;
        float pathS;

        static float Smooth(float x) { x = Mathf.Clamp01(x); return x * x * (3f - 2f * x); }
        static float YawOf(Transform t) { var f = t.forward; return Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg; }

        void Start() { if (Application.isPlaying) Init(); }

        public void Init()
        {
            if (Ready) return;
            if (configJson == null || flow == null || boat == null) throw new InvalidOperationException("DS48Wake：configJson・flow・boat が要ります");
            Cfg = DS48Config.Parse(configJson.text);
            if (water == null && flow.bus != null) water = flow.bus.boatWater;
            // 船体の大きさ（船の根の局所の座標で、子の網の境界の箱から）
            var inv = boat.worldToLocalMatrix;
            float zMax = float.NegativeInfinity, zMin = float.PositiveInfinity, xMax = 0f;
            foreach (var mf in boat.GetComponentsInChildren<MeshFilter>(true))
            {
                if (mf.sharedMesh == null) continue;
                var b = mf.sharedMesh.bounds; var m = inv * mf.transform.localToWorldMatrix;
                for (int i = 0; i < 8; i++)
                {
                    var c = new Vector3((i & 1) == 0 ? b.min.x : b.max.x, (i & 2) == 0 ? b.min.y : b.max.y, (i & 4) == 0 ? b.min.z : b.max.z);
                    var p = m.MultiplyPoint3x4(c);
                    zMax = Mathf.Max(zMax, p.z); zMin = Mathf.Min(zMin, p.z); xMax = Mathf.Max(xMax, Mathf.Abs(p.x));
                }
            }
            if (float.IsInfinity(zMax)) { zMax = 5.6f; zMin = -5.6f; xMax = 1.2f; }
            BowZ = zMax; SternZ = zMin; HalfBeam = xMax;
            if (meshFilter == null) meshFilter = GetComponent<MeshFilter>();
            if (meshRenderer == null) meshRenderer = GetComponent<MeshRenderer>();
            mesh = new Mesh { name = "DS48 船首の泡・航跡（毎フレーム）" };
            mesh.MarkDynamic();
            meshFilter.sharedMesh = mesh;
            if (material != null) meshRenderer.sharedMaterial = material;
            transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            transform.localScale = Vector3.one;
            Ready = true;
        }

        void LateUpdate()
        {
            if (!Ready || flow == null || !flow.Ready) return;
            sw.Restart();
            try { Tick(); }
            catch (Exception ex) { Errors++; LastError = ex.GetType().Name + ": " + ex.Message; if (Errors <= 3) Debug.LogException(ex); }
            double ms = sw.Elapsed.TotalMilliseconds;
            TickMsTotal += ms; if (ms > TickMsMax) TickMsMax = ms; Ticks++;
        }

        void Tick()
        {
            double exp = flow.clock.ExperienceSeconds;
            var pos = boat.position; float yaw = YawOf(boat);
            var fw = boat.forward; var f2 = new Vector2(fw.x, fw.z).normalized; var r2 = new Vector2(f2.y, -f2.x);   // 右 = (fz, −fx)
            if (!havePrev) { havePrev = true; prevPos = pos; prevYaw = yaw; prevExp = exp; }
            double dt = exp - prevExp;
            if (dt > 1e-6)
            {
                var d = pos - prevPos;
                if (new Vector2(d.x, d.z).magnitude > Cfg.motion.teleportM) { hist.Clear(); Teleports++; SpeedMs = 0f; YawRateDegS = 0f; }
                else
                {
                    float v = Vector2.Dot(new Vector2(d.x, d.z), f2) / (float)dt;
                    float w = Mathf.DeltaAngle(prevYaw, yaw) / (float)dt;
                    float a = 1f - Mathf.Exp(-(float)dt / Mathf.Max(1e-4f, Cfg.motion.smoothS));
                    SpeedMs += (v - SpeedMs) * a; YawRateDegS += (w - YawRateDegS) * a;
                    pathS += new Vector2(d.x, d.z).magnitude;
                }
                prevPos = pos; prevYaw = yaw; prevExp = exp;
            }
            var M = Cfg.motion;
            Sv = Smooth((SpeedMs - M.vMinMs) / Mathf.Max(1e-4f, M.vFullMs - M.vMinMs));
            Sr = Mathf.Clamp(YawRateDegS / Mathf.Max(1e-4f, M.yawRateFullDegS), -1f, 1f);

            // 時刻の守り（D48-2）：大波の時刻（形成の始まりから）で出すのを止め、縮めて消す
            var G = Cfg.gate;
            double wave = flow.HandedOver ? exp - flow.WaveStartS : double.NegativeInfinity;
            Emitting = wave < G.fadeStartWaveS;
            Gate = wave <= G.fadeStartWaveS ? 1f : 1f - Smooth((float)((wave - G.fadeStartWaveS) / Math.Max(1e-6, G.fadeEndWaveS - G.fadeStartWaveS)));
            if (Gate <= 0f)
            {
                if (hist.Count > 0 || mesh.vertexCount > 0) { hist.Clear(); mesh.Clear(); Rebuilds++; }
                if (meshRenderer.enabled) meshRenderer.enabled = false;
                VisibleVerts = 0; GuardHidden = 0; OverhangHidden = 0; OutsideHidden = 0; MaxVisibleY = float.NaN;
                BowPortW = BowStbdW = ArmPortW = ArmStbdW = WashHalfW = 0f; BowLenM = 0f;
                return;
            }
            if (!meshRenderer.enabled) meshRenderer.enabled = true;

            // 船尾の点の履歴
            var W = Cfg.wake;
            var stern = boat.position + boat.rotation * new Vector3(0f, 0f, SternZ * 0.92f);
            var sternXZ = new Vector2(stern.x, stern.z);
            if (Emitting && exp - lastEmit >= W.emitEveryS - 1e-9)
            {
                hist.Add(new Sample { p = sternXZ, right = r2, v = Mathf.Max(0f, SpeedMs), sv = Sv, sr = Sr, s = pathS, t = exp });
                lastEmit = exp;
            }
            while (hist.Count > 0 && exp - hist[0].t >= W.lifeS) hist.RemoveAt(0);

            vx.Clear(); uv.Clear(); uv2.Clear(); tri.Clear();
            VisibleVerts = 0; GuardHidden = 0; OverhangHidden = 0; OutsideHidden = 0; MaxVisibleY = float.NegativeInfinity;
            BuildWake(exp, sternXZ, r2);
            BuildBow();
            mesh.Clear();
            mesh.SetVertices(vx); mesh.SetUVs(0, uv); mesh.SetUVs(1, uv2); mesh.SetTriangles(tri, 0, true);
            Rebuilds++;
            if (float.IsNegativeInfinity(MaxVisibleY)) MaxVisibleY = float.NaN;
        }

        // 頂点を 1 つ置く（高さは船用水面データ。守りで描かない頂点は life = 2）
        int Put(Vector2 xz, float lift, float along, float life, float across, bool visibleWidth)
        {
            float y = 0f; bool hide = false;
            if (water != null)
            {
                int k = water.Hits(new Vector3(xz.x, 0f, xz.y), hits);
                if (k == 0) { hide = true; OutsideHidden++; }
                else
                {
                    y = hits[0];
                    if (k >= 2) { hide = true; OverhangHidden++; }
                    else if (y > Cfg.gate.guardHeightM) { hide = true; GuardHidden++; }
                }
            }
            if (hide) { GuardHiddenTotal++; life = 2f; }
            else if (visibleWidth && life < 1f) { VisibleVerts++; MaxVisibleY = Mathf.Max(MaxVisibleY, y + lift); }
            vx.Add(new Vector3(xz.x, y + lift, xz.y)); uv.Add(new Vector2(along, life)); uv2.Add(new Vector2(across, 0f));
            return vx.Count - 1;
        }

        void Quad(int a0, int a1, int b0, int b1) { tri.Add(a0); tri.Add(b0); tri.Add(a1); tri.Add(a1); tri.Add(b0); tri.Add(b1); }

        void BuildWake(double exp, Vector2 sternNow, Vector2 rightNow)
        {
            var W = Cfg.wake;
            int n = hist.Count;
            if (n == 0) return;
            float tanA = Mathf.Tan(W.armAngleDeg * Mathf.Deg2Rad);
            float b0 = HalfBeam * 0.7f;
            // 古い順の履歴 + 今の船尾（年齢 0）
            int m = n + 1;
            int[] washL = new int[m], washR = new int[m], armPi = new int[m], armPo = new int[m], armSi = new int[m], armSo = new int[m];
            WashHalfW = 0f; ArmPortW = 0f; ArmStbdW = 0f;
            for (int i = 0; i < m; i++)
            {
                Sample smp = i < n ? hist[i] : new Sample { p = sternNow, right = rightNow, v = Mathf.Max(0f, SpeedMs), sv = Emitting ? Sv : (n > 0 ? hist[n - 1].sv : 0f), sr = Sr, s = pathS, t = exp };
                float age = (float)(exp - smp.t);
                float lf = Mathf.Clamp01(age / W.lifeS);
                float hw = smp.sv * (W.washHalfWidthM + W.washGrowMs * age) * (1f - lf * lf) * Gate;
                washL[i] = Put(smp.p - smp.right * hw, W.liftM, smp.s, lf, 0f, hw > 1e-3f);
                washR[i] = Put(smp.p + smp.right * hw, W.liftM, smp.s, lf, 1f, hw > 1e-3f);
                if (i == m - 1) WashHalfW = hw;
                float d = b0 + smp.v * age * tanA;
                for (int side = -1; side <= 1; side += 2)
                {
                    float sf = Mathf.Max(0f, 1f + W.armTurnAsym * smp.sr * -side);
                    float aw = W.armWidthM * smp.sv * (1f - lf) * Gate * sf;
                    var c = smp.p + smp.right * (side * d);
                    int vi = Put(c - smp.right * (side * aw * 0.5f), W.liftM * 1.25f, smp.s + (side > 0 ? 31f : 0f), lf, 0f, aw > 1e-3f);
                    int vo = Put(c + smp.right * (side * aw * 0.5f), W.liftM * 1.25f, smp.s + (side > 0 ? 31f : 0f), lf, 1f, aw > 1e-3f);
                    if (side < 0) { armPi[i] = vi; armPo[i] = vo; } else { armSi[i] = vi; armSo[i] = vo; }
                    if (i == Mathf.Max(0, m - 1 - (int)(1.5f / W.emitEveryS))) { if (side < 0) ArmPortW = aw; else ArmStbdW = aw; }
                }
            }
            for (int i = 0; i + 1 < m; i++)
            {
                Quad(washL[i], washR[i], washL[i + 1], washR[i + 1]);
                Quad(armPi[i], armPo[i], armPi[i + 1], armPo[i + 1]);
                Quad(armSi[i], armSo[i], armSi[i + 1], armSo[i + 1]);
            }
        }

        void BuildBow()
        {
            var B = Cfg.bow;
            int N = Mathf.Max(3, B.stations);
            float L = BowZ - SternZ;
            float len = (B.lenMinM + B.lenPerSpeedM * Sv);
            BowLenM = len;
            var yawQ = Quaternion.Euler(0f, YawOf(boat), 0f);
            var bp = boat.position;
            BowPortW = 0f; BowStbdW = 0f;
            for (int side = -1; side <= 1; side += 2)
            {
                float sf = Mathf.Max(0f, 1f - B.turnAsym * Sr * side);
                int prevI = -1, prevO = -1;
                for (int j = 0; j < N; j++)
                {
                    float f = j / (float)(N - 1);
                    float z = BowZ - len * f;
                    float hb = HalfBeam * Mathf.Sqrt(Mathf.Clamp01((BowZ - z) / Mathf.Max(1e-3f, B.bowFullLenFrac * L)));
                    float shape = f < 0.25f ? Mathf.Lerp(0.35f, 1f, f / 0.25f) : Mathf.Pow(1f - (f - 0.25f) / 0.75f, 1.5f);
                    float w = B.widthM * Mathf.Max(B.widthMinFrac, Sv) * sf * shape * Gate;
                    if (side < 0) BowPortW = Mathf.Max(BowPortW, w); else BowStbdW = Mathf.Max(BowStbdW, w);
                    var pin = bp + yawQ * new Vector3(side * hb, 0f, z);
                    var pout = bp + yawQ * new Vector3(side * (hb + w), 0f, z - w * 0.5f);
                    float life = 0.85f * f;
                    int vi = Put(new Vector2(pin.x, pin.z), B.liftM, 100f + len * f, life, 0f, w > 1e-3f);
                    int vo = Put(new Vector2(pout.x, pout.z), B.liftM, 100f + len * f, life, 1f, w > 1e-3f);
                    if (prevI >= 0) Quad(prevI, prevO, vi, vo);
                    prevI = vi; prevO = vo;
                }
            }
        }
    }
}
