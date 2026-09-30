using UnityEngine.InputSystem;

namespace GreatWave.Design45
{
    public struct DS45ComfortCmd
    {
        public int level;       // 直接選んだ段（0〜3）。なければ −1
        public int delta;       // 段を一つ上げる（+1）・下げる（−1）
        public bool reset;      // 座席リセット
        public string source;   // 読んだ機器（記録用）
    }

    // 設計45：揺れの段の切り替えと座席リセットの入力（Unity の Input System）。押した瞬間（前の状態からの変化）だけを返す。
    //   キーボード：1〜4 で L0〜L3、R で座席リセット。
    //   ゲームパッド（DualSense を含む Gamepad）：十字キーの上で一つ上の段、下で一つ下の段、Select（DualSense のクリエイト）で座席リセット。
    //   設計44 の操船（W/A/S/D・矢印・Space、左スティック・R2・L2・×）とは重ならない。PS VR2 の Sense は未導入（保留）。
    public class DS45ComfortInput
    {
        bool p1, p2, p3, p4, pR, pUp, pDown, pSel;

        static bool Edge(bool now, ref bool prev) { bool e = now && !prev; prev = now; return e; }

        public DS45ComfortCmd Read(Keyboard kb, Gamepad gp)
        {
            var c = new DS45ComfortCmd { level = -1 };
            if (kb != null)
            {
                if (Edge(kb.digit1Key.isPressed, ref p1)) { c.level = 0; c.source = "keyboard"; }
                if (Edge(kb.digit2Key.isPressed, ref p2)) { c.level = 1; c.source = "keyboard"; }
                if (Edge(kb.digit3Key.isPressed, ref p3)) { c.level = 2; c.source = "keyboard"; }
                if (Edge(kb.digit4Key.isPressed, ref p4)) { c.level = 3; c.source = "keyboard"; }
                if (Edge(kb.rKey.isPressed, ref pR)) { c.reset = true; c.source = "keyboard"; }
            }
            if (gp != null)
            {
                if (Edge(gp.dpad.up.isPressed, ref pUp)) { c.delta += 1; c.source = "gamepad"; }
                if (Edge(gp.dpad.down.isPressed, ref pDown)) { c.delta -= 1; c.source = "gamepad"; }
                if (Edge(gp.selectButton.isPressed, ref pSel)) { c.reset = true; c.source = "gamepad"; }
            }
            return c;
        }

        public DS45ComfortCmd ReadLive() => Read(Keyboard.current, Gamepad.current);
    }
}
