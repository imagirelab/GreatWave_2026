using UnityEngine;

namespace GreatWave.Design37
{
    // 設計37：座席で頭を左右に動かす想定の視点の揺れ（計画 §2.3 の設計37：左右 ±0.1 m）。
    // 対象のカメラを、そのカメラの右の向き（ワールド）へ dx だけずらす（親が動いても、親の中の元の位置からずらす）。
    // Editor の検査（DS37Render）は Apply/Restore を直接呼ぶ。Play モードでは swayInPlayMode のとき、正弦波（振幅 amplitude、周期 period）で揺らす。
    // PC の描画での模様の安定の確かめのためのもので、HMD の頭の追跡（PS VR2、保留）の代わりではない。
    public class DS37HeadSway : MonoBehaviour
    {
        public Camera target;
        [Tooltip("左右の振幅（m）。計画 §2.3 の設計37 の ±0.1 m")]
        public float amplitude = 0.1f;
        [Tooltip("揺れの周期（s）。既定値（進行役の判断）")]
        public float period = 2f;
        public bool swayInPlayMode = false;

        Vector3 baseLocal;
        Vector3 appliedLocal;
        bool hasBase;

        public float OffsetAt(double t) => amplitude * Mathf.Sin((float)(2.0 * Mathf.PI * t / Mathf.Max(period, 1e-3f)));

        // 設計37 修正1：前に置いた位置のままなら基準を持ち越し、ほかの部品（DS30BoatHeave の船の上下など）が位置を書き換えていたら、
        // 今の位置を新しい基準として読み直す（修正前は最初の基準を持ち越し、船の上下を毎コマ上書きしていた）。
        public void Apply(float dx)
        {
            if (target == null) return;
            var tr = target.transform;
            if (!hasBase || tr.localPosition != appliedLocal) { baseLocal = tr.localPosition; hasBase = true; }
            tr.localPosition = baseLocal;
            var worldOffset = tr.right * dx;
            var local = tr.parent != null ? tr.parent.InverseTransformVector(worldOffset) : worldOffset;
            tr.localPosition = baseLocal + local;
            appliedLocal = tr.localPosition;
        }

        // 揺れを外す。ほかの部品が位置を書き換えた後なら、その位置が揺れのない位置なので触らない
        public void Restore()
        {
            if (target == null || !hasBase) return;
            if (target.transform.localPosition == appliedLocal) target.transform.localPosition = baseLocal;
            hasBase = false;
        }

        void LateUpdate()
        {
            if (Application.isPlaying && swayInPlayMode) Apply(OffsetAt(Time.timeSinceLevelLoad));
        }

        void OnDisable() { Restore(); }
    }
}
