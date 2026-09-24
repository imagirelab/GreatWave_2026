using UnityEngine;
using UnityEngine.Formats.Alembic.Importer;
using UnityEngine.InputSystem;

namespace GreatWave
{
    public class FixedTopology16Player : MonoBehaviour
    {
        public AlembicStreamPlayer stream;
        public bool recording;
        public bool paused;
        public float ClipTime { get; private set; }
        Font font;
        GUIStyle label;

        void Start() { font=Font.CreateDynamicFontFromOSFont(new[]{"Yu Gothic","Meiryo","Microsoft YaHei UI","MS Gothic"},24); SetTime(0); }
        void Update()
        {
            if(recording) return;
            var keyboard=Keyboard.current;
            if(keyboard!=null)
            {
                if(keyboard.qKey.wasPressedThisFrame) Application.Quit();
                if(keyboard.spaceKey.wasPressedThisFrame) paused=!paused;
                if(keyboard.rKey.wasPressedThisFrame) { paused=false; SetTime(0); }
            }
            if(!paused&&stream!=null&&stream.Duration>0)
            {
                SetTime(Mathf.Min(ClipTime+Time.unscaledDeltaTime,stream.Duration));
                if(ClipTime>=stream.Duration) paused=true;
            }
        }
        public void SetTime(float relativeSeconds)
        {
            if(stream==null) return;
            ClipTime=Mathf.Clamp(relativeSeconds,0,stream.Duration);
            // 実際のHoudini書き出しを読む。波形の式をUnity側で再生成しない。
            stream.UpdateImmediately(ClipTime);
            // この書出しの定数マーカーで退化したAABBを、読み込んだ実頂点から更新する。
            FixedTopology16Validation.RefreshBounds(stream);
        }
        void OnGUI()
        {
            if(recording) return;
            if(label==null) {label=new GUIStyle(GUI.skin.label){font=font,fontSize=18};label.normal.textColor=new Color(.97f,.95f,.88f);}
            float scale=Screen.width/1280f;GUI.matrix=Matrix4x4.Scale(new Vector3(scale,scale,1));float h=Screen.height/scale;
            GUI.color=new Color(.04f,.08f,.13f,.95f);GUI.DrawTexture(new Rect(16,h-75,1248,60),Texture2D.whiteTexture);GUI.color=Color.white;
            GUI.Label(new Rect(32,h-72,1210,26),"16 固定トポロジーの受け渡し検査 / Houdini Alembic / 流体・HMD未検証",label);
            GUI.Label(new Rect(32,h-44,1210,26),"時刻 "+ClipTime.ToString("F3")+" 秒　Space 停止・再開　R 先頭　Q 終了",label);
        }
    }
}
