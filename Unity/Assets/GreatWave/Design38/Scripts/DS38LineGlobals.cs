using UnityEngine;

namespace GreatWave.Design38
{
    // 設計38：線のシェーダー（DS38 Outline Keypose・DS38 Outline Mesh）が読む大域の値を入れる。
    //  ・_DS38PaintCamPos・_DS38PaintFade：原画のカメラの位置と、そこからの離れの重みの r0・r1（m）。中心眼が原画のカメラの r0 以内なら、
    //    主役波の原画にない線（頂点ごとの印 0）と爪の線を描かない（原画視点では焼き込みの色面が線を担う）。r1 より離れれば全部の線を描く。
    //  ・_DS38EyeOverride：w = 0（Mock の両眼の描画だけが中心眼を入れる。ここでは外す）。
    // Play モードでは毎コマ入れる（原画のカメラは動かないが、場面を切り替えても値が残らないように）。Editor の描画（DS38Render）は Apply を直接呼ぶ。
    [ExecuteAlways]
    [DefaultExecutionOrder(-50)]
    public class DS38LineGlobals : MonoBehaviour
    {
        public Camera paintingCamera;
        public float r0 = 5f, r1 = 10f;

        public void Apply()
        {
            if (paintingCamera != null)
            {
                var p = paintingCamera.transform.position;
                Shader.SetGlobalVector("_DS38PaintCamPos", new Vector4(p.x, p.y, p.z, 1f));
            }
            Shader.SetGlobalVector("_DS38PaintFade", new Vector4(r0, r1, 0f, 0f));
            Shader.SetGlobalVector("_DS38EyeOverride", Vector4.zero);
            Shader.SetGlobalFloat("_DS38LineCoordMode", 0f);
        }

        void OnEnable() { Apply(); }

        void Update()
        {
            if (Application.isPlaying) Apply();
        }
    }
}
