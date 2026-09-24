using UnityEngine;
using UnityEngine.Formats.Alembic.Importer;
using UnityEngine.InputSystem;
using GreatWave.Playback18;

namespace GreatWave
{
    public class Playback18Player:MonoBehaviour
    {
        public AlembicStreamPlayer stream;
        public GameObject vatRoot;
        public Material vatMaterial;
        public Playback18VAT.Data vatData;
        public ComputeShader vatDecoder;
        public Bounds vatBounds;
        public bool recording,paused;
        public bool VatActive{get;private set;}
        public int Sample{get;private set;}
        public float ClipTime{get;private set;}
        Font font;GUIStyle style;
        void Start(){if(vatRoot!=null)foreach(var renderer in vatRoot.GetComponentsInChildren<Renderer>(true))renderer.localBounds=vatBounds;font=Font.CreateDynamicFontFromOSFont(new[]{"Yu Gothic","Meiryo","Microsoft YaHei UI"},22);SelectFormat(false);SetSample(0);}
        void Update()
        {
            if(recording)return;
            var keys=Keyboard.current;
            if(keys!=null)
            {
                if(keys.digit1Key.wasPressedThisFrame)SelectFormat(false);
                if(keys.digit2Key.wasPressedThisFrame)SelectFormat(true);
                if(keys.spaceKey.wasPressedThisFrame)paused=!paused;
                if(keys.rKey.wasPressedThisFrame){ClipTime=0;paused=false;SetSample(0);}
                if(keys.qKey.wasPressedThisFrame)Application.Quit();
            }
            if(!paused){ClipTime=Mathf.Min(2,ClipTime+Time.unscaledDeltaTime);int next=Mathf.Min(48,Mathf.FloorToInt(ClipTime*24+.00001f));if(next!=Sample)SetSample(next);if(ClipTime>=2)paused=true;}
        }
        public void SelectFormat(bool vat)
        {
            if(vat&&vatRoot==null)return;
            VatActive=vat;stream.gameObject.SetActive(!vat);if(vatRoot!=null)vatRoot.SetActive(vat);SetSample(Sample);
        }
        public void SetSample(int index)
        {
            Sample=Mathf.Clamp(index,0,48);
            if(VatActive)Playback18VAT.SetFrame(vatMaterial,vatData,Sample);
            else{stream.UpdateImmediately(Sample/24f);Playback18Validation.RefreshBounds(stream);}
        }
        void OnGUI()
        {
            if(recording)return;
            if(style==null){style=new GUIStyle(GUI.skin.label){font=font,fontSize=19};style.normal.textColor=Color.white;}
            GUI.Box(new Rect(14,14,Screen.width-28,74),"");
            GUI.Label(new Rect(28,18,Screen.width-56,30),"18 実FLIPの再生方式比較 / "+(VatActive?"Fluid VAT":"Alembic")+" / 時刻 "+(Sample/24f).ToString("F3")+" 秒",style);
            GUI.Label(new Rect(28,49,Screen.width-56,30),"1 Alembic　2 VAT　Space 停止・再開　R 先頭　Q 終了 / 物理精度・HMDは未検証",style);
        }
    }
}
