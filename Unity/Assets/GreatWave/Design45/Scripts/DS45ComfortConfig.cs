using System;
using UnityEngine;

namespace GreatWave.Design45
{
    // 設計45：乗客の揺れの設定（ds45_comfort.json）。値はどれも進行役が決めた調整値で、資料の値ではない（D45-5）。
    [Serializable]
    public class DS45Level
    {
        public string key;          // L0〜L3
        public string nameJa;       // 画面・記録に出す名前
        public float kV;            // 上下動の速い成分を乗客へ渡す割合（0 = 上下動最小、1 = 船のまま）
        public bool yawFollow;      // 旋回：乗客の水平の向きが船の首振りに付いて回るか（false なら世界に固定）
        public float kTilt;         // 傾斜：船の傾き（横揺れ・縦揺れ）を乗客へ渡す割合
        public float tiltMaxDeg;    // 乗客へ渡す傾きの上限（柔らかい頭打ち）
    }

    [Serializable]
    public class DS45Switch
    {
        public float s;             // 体験の秒（設計44 の記録の s）
        public string device;       // keyboard / gamepad
        public string key;          // Key の名前（Digit1〜Digit4、R）
        public string button;       // DpadUp / DpadDown / Select
    }

    [Serializable]
    public class DS45TestCfg
    {
        public string boatStepsCsv, boatFramesJsonl, heave30Json, boatsJson, seatV1Json;
        public DS45Switch[] switches;
        public float holdS = 0.1f;          // 仮想のキーを押しておく秒
        public float lookUpDeg = 30f;       // 試験だけの見上げのカメラ（HMD Camera の子。頭を上げた人の代わり）
        public float vfovDeg = 90f;         // PC の代わりの画角（縦）
        public int width = 640, height = 360;
        public float[] stereoS;             // Mock の両目（試験だけ）を描く体験の秒（HMD の代わり。設計34・40 の Mock と同じ考え）
        public float ipdM = 0.064f;         // 両目の間（見上げのカメラの右向きに ±ipdM/2。進行役の既定値）
    }

    [Serializable]
    public class DS45ComfortCfg
    {
        public string schema, noteJa;
        public float eyeHeightM = 1.2f;         // 座席の目の甲板からの高さ（seat_v1.json の eye_above_deck_m）
        public float seatYawOffsetDeg;          // 座席の正面の、船首からの水平の角（seat_v1 の recenter_yaw − 船の原画の向き）
        public string seatYawOffsetSourceJa;
        public float blendS = 1f;               // 段を切り替えた時、値を移す秒（smoothstep）
        public float omegaV = 2.5f;             // 上下の追従の固有角振動数（rad/s）。これより遅い上下は全段で渡る
        public float betaV = 1f;                // 上下の追従の速度の先回りの重み（1 = 等速の上下で遅れない、0 = 普通の 2 次の低域通過）。水平は 1 のまま
        public float omegaH = 4f;               // 水平の追従（全段共通。細かい水平の揺れだけ除く）
        public float omegaTilt = 3f;            // 傾きの平滑化（L3 だけ使う）
        public float maxDevUpM = 0.1f;          // 乗客の目が座席の目から船の上向きに離れてよい量（船の枠。柔らかい頭打ち）
        public float maxDevDownM = 0.1f;        // 同、船の下向き（座席の目は船縁の上端より 0.149 m 上（設計41）。これより小さくして目を船縁の上に残す）
        public float maxDevHM = 0.25f;          // 同、船の水平
        public float seatEyeAboveGunwaleM = 0.149f;  // 記録と検査のため（設計41 の最小の受入 3。計算には使わない）
        public int defaultLevel;
        public DS45Level[] levels;
        public DS45TestCfg test;

        public static DS45ComfortCfg Parse(string json)
        {
            var c = JsonUtility.FromJson<DS45ComfortCfg>(json);
            if (c == null || c.levels == null || c.levels.Length != 4) throw new InvalidOperationException("DS45ComfortCfg：levels は 4 段");
            if (c.maxDevDownM >= c.seatEyeAboveGunwaleM) throw new InvalidOperationException("DS45ComfortCfg：maxDevDownM は座席の目の船縁の上端からの高さより小さくする（目が船縁の下へ沈まないため）");
            if (c.omegaV <= 0f || c.omegaH <= 0f || c.omegaTilt <= 0f || c.maxDevUpM <= 0f || c.maxDevDownM <= 0f || c.maxDevHM <= 0f || c.blendS <= 0f)
                throw new InvalidOperationException("DS45ComfortCfg：正の値が要る項目が 0 以下");
            c.defaultLevel = Mathf.Clamp(c.defaultLevel, 0, 3);
            return c;
        }
    }
}
