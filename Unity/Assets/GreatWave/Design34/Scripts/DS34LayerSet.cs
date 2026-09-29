using System;
using GreatWave.ArtFirst;
using GreatWave.Design30;
using GreatWave.Design31;
using UnityEngine;

namespace GreatWave.Design34
{
    // 設計34：3 つの白波の層を 1 つの時計で再生し、層ごとに入切する。
    //   白の帯（white band）＝主役波のシートの色（設計31 の T_white の白の時間場。DS27 NPR White が τ ≥ T_white の頂点を白で塗る）。
    //     切ると、主役波のレンダラーの MaterialPropertyBlock の _DS27Tau だけを −1e7 に置き換え、終態が白の所を『白の前の色』（藍中）で塗る。
    //     _DS27Tau はこのシェーダーでは白の比べにしか使わない（位置は 4 層と重み・枠の原点で決まる）ので、形は変わらない。
    //   爪（claws）＝DS34ClawPlayer の結合メッシュ。切ると MeshRenderer を切る。
    //   飛沫（spray）＝DS31InstancedParticles の instancing。切ると Play モードの描画を止める（採取は DS34Render が層ごとに CommandBuffer を付ける）。
    // 時計：DS30SinglePlayback（実行順 50）が GWClock に t を書き、主役波と周りの海へ τ(t) を渡す。爪と飛沫（実行順 60）は同じ GWClock の秒を読む。
    // この部品（実行順 70）は、3 層がそのコマに受け取った時刻を記録し（LastT*）、入切を適用する。Play モードの数字キー 1・2・3 で白・爪・飛沫を入切する。
    [DefaultExecutionOrder(70)]
    public class DS34LayerSet : MonoBehaviour
    {
        public DS30SinglePlayback playback;
        public DS30SheetPlayer heroSheet;
        public DS34ClawPlayer claws;
        public DS31InstancedParticles spray;
        public bool whiteBand = true;
        public bool clawsOn = true;
        public bool sprayOn = true;
        [Tooltip("Play モードで数字キー 1・2・3（白の帯・爪・飛沫）で入切する")]
        public bool keyboardToggles = true;

        public const float WhiteOffTau = -1e7f;
        static readonly int TauId = Shader.PropertyToID("_DS27Tau");
        MaterialPropertyBlock block;

        /// <summary>このコマで各層が受け取った体験の時刻 t（主役波は再生器の t、爪・飛沫は自分の ApplyT の t）と、主役波の τ。</summary>
        public double LastClockT { get; private set; } = double.NaN;
        public double LastHeroTau { get; private set; } = double.NaN;
        public double LastClawT { get; private set; } = double.NaN;
        public double LastSprayT { get; private set; } = double.NaN;

        /// <summary>入切を今の状態へ適用する（主役波の ApplyTau の後に呼ぶ）。</summary>
        public void ApplyToggles()
        {
            if (heroSheet != null)
            {
                var r = heroSheet.Surface;
                if (r != null)
                {
                    if (block == null) block = new MaterialPropertyBlock();
                    r.GetPropertyBlock(block);
                    block.SetFloat(TauId, whiteBand ? (float)heroSheet.AppliedTau : WhiteOffTau);
                    r.SetPropertyBlock(block);
                }
            }
            if (claws != null) { var cr = claws.GetComponent<MeshRenderer>(); if (cr != null) cr.enabled = clawsOn; }
            if (spray != null) spray.drawInPlayMode = sprayOn;
            Record();
        }

        public void Record()
        {
            LastClockT = playback != null ? playback.T : double.NaN;
            LastHeroTau = heroSheet != null ? heroSheet.AppliedTau : double.NaN;
            LastClawT = claws != null ? claws.AppliedT : double.NaN;
            LastSprayT = spray != null ? spray.AppliedT : double.NaN;
        }

        void Update()
        {
            if (!Application.isPlaying) return;
            if (keyboardToggles)
            {
                // このプロジェクトは新しい Input System だけを使う（ProjectSettings の activeInputHandler = 1）
                var kb = UnityEngine.InputSystem.Keyboard.current;
                if (kb != null)
                {
                    if (kb.digit1Key.wasPressedThisFrame) whiteBand = !whiteBand;
                    if (kb.digit2Key.wasPressedThisFrame) clawsOn = !clawsOn;
                    if (kb.digit3Key.wasPressedThisFrame) sprayOn = !sprayOn;
                }
            }
            ApplyToggles();
        }
    }
}
