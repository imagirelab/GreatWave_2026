using System;
using UnityEngine;
using UnityEngine.Formats.Alembic.Importer;
using UnityEngine.InputSystem;

namespace GreatWave
{
    public class Sampling19Player:MonoBehaviour
    {
        public AlembicStreamPlayer[] streams60;
        public AlembicStreamPlayer stream30;
        public Playback18Player shadowFixture;
        public bool recording,paused;
        public int Rate {get;private set;}=60;
        public int MasterSample {get;private set;}
        float seconds;Font font;GUIStyle style;
        void Start(){QualitySettings.shadows=ShadowQuality.All;QualitySettings.shadowResolution=ShadowResolution.High;QualitySettings.shadowDistance=45;font=Font.CreateDynamicFontFromOSFont(new[]{"Yu Gothic","Meiryo","Microsoft YaHei UI"},20);if(shadowFixture!=null){shadowFixture.recording=true;shadowFixture.gameObject.SetActive(false);}SetSample(0,60);}
        public AlembicStreamPlayer SetSample(int masterSample,int rate)
        {
            Rate=rate;MasterSample=Mathf.Clamp(masterSample,0,120);if(rate==30)MasterSample=MasterSample/2*2;
            int part=Mathf.Min(2,MasterSample/40);
            foreach(var s in streams60)s.gameObject.SetActive(rate==60&&s==streams60[part]);stream30.gameObject.SetActive(rate==30);
            var stream=rate==30?stream30:streams60[part];float local=(MasterSample-(rate==60?part*40:0))/60f;
            stream.UpdateImmediately(local);Playback18Validation.RefreshBounds(stream);return stream;
        }
        public void HideSampling(){foreach(var s in streams60)s.gameObject.SetActive(false);stream30.gameObject.SetActive(false);}
        void Update()
        {
            if(recording)return;var keys=Keyboard.current;
            if(keys!=null){if(keys.digit1Key.wasPressedThisFrame)Rate=30;if(keys.digit2Key.wasPressedThisFrame)Rate=60;if(keys.spaceKey.wasPressedThisFrame)paused=!paused;if(keys.rKey.wasPressedThisFrame){seconds=0;paused=false;}if(keys.qKey.wasPressedThisFrame)Application.Quit();}
            if(!paused){seconds=Mathf.Min(2,seconds+Time.unscaledDeltaTime);if(seconds>=2)paused=true;}SetSample(Mathf.Min(120,Mathf.FloorToInt(seconds*60+.00001f)),Rate);
        }
        void OnGUI()
        {
            if(recording)return;if(style==null){style=new GUIStyle(GUI.skin.label){font=font,fontSize=18};style.normal.textColor=Color.white;}
            GUI.Box(new Rect(14,14,Screen.width-28,72),"");GUI.Label(new Rect(28,18,Screen.width-56,28),"19 新規実FLIP / "+Rate+"Hz試料 / "+(MasterSample/60f).ToString("F3")+"秒 / HMD未検証",style);
            GUI.Label(new Rect(28,46,Screen.width-56,28),"1 30Hz　2 60Hz　Space 停止・再開　R 先頭　Q 終了 / 新規121時刻から比較",style);
        }
    }
}
