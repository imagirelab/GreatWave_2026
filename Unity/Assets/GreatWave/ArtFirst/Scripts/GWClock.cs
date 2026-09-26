using UnityEngine;

namespace GreatWave.ArtFirst
{
    // GWClock（作業計画 4.0・番号30）：体験の時刻（秒）を一か所で持つ時計。形成の keypose（AF30KeyposeWave）など、
    // 時刻で動くものはこの時計を読む（番号31 の白、番号35 の爪、番号37 の飛沫も同じ時計へつなぐ予定。番号38 で一括の駆動を確かめる）。
    // 時間軸（番号23 で凍結）：予備 0〜2 s、形成 2〜12 s、静止 12〜17 s、t* = 12.0 s。
    // 再生中（Play）は Time.deltaTime × speed で進め、loopSeconds で折り返す。Editor の採取（AF30Formation）は SetSeconds で時刻を直接決める。
    [DefaultExecutionOrder(-100)]
    public class GWClock : MonoBehaviour
    {
        public static GWClock Active { get; private set; }

        [Tooltip("いまの時刻（秒）")]
        public float seconds;
        [Tooltip("再生中に時刻を進める")]
        public bool playInPlayMode = true;
        [Tooltip("折り返す長さ（秒）。0 以下で折り返さない")]
        public float loopSeconds = 17f;
        [Tooltip("時刻の進む速さ（1 で実時間）")]
        public float speed = 1f;
        [Tooltip("原画対応の時刻 t*（秒）")]
        public float tStarSeconds = 12f;

        public float Seconds => seconds;

        public void SetSeconds(float s)
        {
            seconds = s;
        }

        void OnEnable()
        {
            Active = this;
        }

        void OnDisable()
        {
            if (Active == this) Active = null;
        }

        void Update()
        {
            if (!Application.isPlaying || !playInPlayMode) return;
            seconds += Time.deltaTime * speed;
            if (loopSeconds > 0f && seconds >= loopSeconds) seconds -= loopSeconds * Mathf.Floor(seconds / loopSeconds);
        }
    }
}
