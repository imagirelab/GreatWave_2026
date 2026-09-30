using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Controls;
using UnityEngine.InputSystem.XR;

namespace GreatWave.Design44
{
    public struct DS44InputSample
    {
        public float throttle;   // −1（後ろ・減速）〜 +1（前進）
        public float turn;       // −1（左）〜 +1（右）
        public bool stop;        // 停止（押している間）
        public string source;    // 読んだ機器（記録用）
    }

    // 設計44：操船の入力（Unity の Input System）。キーボードとゲームパッドを先に作る（計画 §2.4 設計44）。
    //   キーボード：W/↑ 前進、S/↓ 減速・後進、A/← 左、D/→ 右、Space 停止。
    //   ゲームパッド（DualSense を含む Gamepad）：左スティック（上下で前進・後進、左右で旋回）、R2 前進、L2 減速・後進、South（×）停止。
    //   XR のコントローラー（PS VR2 の Sense を SteamVR の OpenXR で使う場合を想定）：左手の thumbstick／primary2DAxis を左スティックと同じに読む。
    //     PS VR2 は未導入なので確かめていない（保留。利用者の手）。
    public static class DS44Input
    {
        static float K(Keyboard kb, Key a, Key b) => (kb[a].isPressed || kb[b].isPressed) ? 1f : 0f;

        public static DS44InputSample Read(Keyboard kb, Gamepad gp, InputDevice xr)
        {
            float thr = 0f, turn = 0f; bool stop = false;
            var src = new List<string>(3);
            if (kb != null)
            {
                float t = K(kb, UnityEngine.InputSystem.Key.W, UnityEngine.InputSystem.Key.UpArrow) - K(kb, UnityEngine.InputSystem.Key.S, UnityEngine.InputSystem.Key.DownArrow);
                float r = K(kb, UnityEngine.InputSystem.Key.D, UnityEngine.InputSystem.Key.RightArrow) - K(kb, UnityEngine.InputSystem.Key.A, UnityEngine.InputSystem.Key.LeftArrow);
                bool s = kb.spaceKey.isPressed;
                if (t != 0f || r != 0f || s) src.Add("keyboard");
                thr += t; turn += r; stop |= s;
            }
            if (gp != null)
            {
                var ls = gp.leftStick.ReadValue();
                float t = ls.y + gp.rightTrigger.ReadValue() - gp.leftTrigger.ReadValue();
                bool s = gp.buttonSouth.isPressed;
                if (Mathf.Abs(t) > 1e-4f || Mathf.Abs(ls.x) > 1e-4f || s) src.Add("gamepad");
                thr += t; turn += ls.x; stop |= s;
            }
            if (xr != null)
            {
                var c = xr.TryGetChildControl<Vector2Control>("thumbstick") ?? xr.TryGetChildControl<Vector2Control>("primary2DAxis");
                if (c != null)
                {
                    var v = c.ReadValue();
                    if (v.sqrMagnitude > 1e-8f) src.Add("xr");
                    thr += v.y; turn += v.x;
                }
            }
            return new DS44InputSample { throttle = Mathf.Clamp(thr, -1f, 1f), turn = Mathf.Clamp(turn, -1f, 1f), stop = stop, source = string.Join("+", src) };
        }

        /// <summary>実際の機器（今の Keyboard・Gamepad と左手の XR コントローラー）。</summary>
        public static DS44InputSample ReadLive() => Read(Keyboard.current, Gamepad.current, XRController.leftHand);
    }
}
