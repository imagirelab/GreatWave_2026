using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace GreatWave
{
    public class FixedTopology16Recorder:MonoBehaviour
    {
        public FixedTopology16Player player;
        public Camera cameraToRender;
        public TextAsset reference;
        public Material captionMaterial;
        IEnumerator Start()
        {
            var args=Environment.GetCommandLineArgs();int arg=Array.IndexOf(args,"--capture-dir");if(arg<0||arg+1>=args.Length)yield break;
            var folder=Path.GetFullPath(args[arg+1]);Directory.CreateDirectory(folder);player.recording=true;
            yield return null;yield return null;
            var measured=FixedTopology16Validation.Measure(player.stream,JsonUtility.FromJson<FixedTopology16Reference>(reference.text));
            File.WriteAllText(Path.Combine(folder,"runtime_validation.json"),JsonUtility.ToJson(measured,true));
            if(!measured.passed){Debug.LogError("FIXED16_RUNTIME_VALIDATION_FAILED");Application.Quit(3);yield break;}
            var report=new CaptureReport{unity=Application.unityVersion,startedUtc=DateTime.UtcNow.ToString("O"),method="Windowsビルドの実Alembic再生・Camera.Render→RenderTexture→ReadPixels。画面録画ではない。",
                width=1280,height=720,sampleRate=30,minimumColors=int.MaxValue,minimumNonBlackFraction=1,validationPassed=measured.passed};
            var target=new RenderTexture(1280,720,24);target.Create();cameraToRender.targetTexture=target;cameraToRender.cullingMask&=~(1<<31);
            var overlay=new GameObject("16 記録注記").AddComponent<Camera>();overlay.transform.position=new Vector3(2000,2000,2000);overlay.orthographic=true;overlay.orthographicSize=360;overlay.aspect=1280f/720;
            overlay.nearClipPlane=.1f;overlay.farClipPlane=20;overlay.clearFlags=CameraClearFlags.Depth;overlay.cullingMask=1<<31;overlay.targetTexture=target;overlay.enabled=false;
            var panel=GameObject.CreatePrimitive(PrimitiveType.Cube);panel.layer=31;panel.transform.SetParent(overlay.transform,false);panel.transform.localPosition=new Vector3(0,-310,8);panel.transform.localScale=new Vector3(1248,86,.1f);panel.GetComponent<Renderer>().sharedMaterial=captionMaterial;
            var font=Font.CreateDynamicFontFromOSFont(new[]{"Yu Gothic","Meiryo","Microsoft YaHei UI","MS Gothic"},32);
            Label(overlay,font,"16 Houdini → Unity / 固定トポロジーの2秒キャッシュ",new Vector3(-607,-278,7),20);
            var time=Label(overlay,font,"時刻 0.000 秒",new Vector3(-607,-310,7),17);
            Label(overlay,font,"青：変形格子8×8m　黄：1m立方体　赤緑青：元のXYZ　桃：非対称点 / 流体・HMD未検証",new Vector3(-607,-327,7),14);
            for(int frame=0;frame<=60;frame++)
            {
                player.SetTime(frame/30f);time.text="時刻 "+player.ClipTime.ToString("F3")+" 秒 / 実Alembic・オフスクリーン描画 / 30Hzの記録・性能測定ではありません";
                yield return new WaitForEndOfFrame();cameraToRender.Render();overlay.Render();RenderTexture.active=target;
                var texture=new Texture2D(1280,720,TextureFormat.RGB24,false);texture.ReadPixels(new Rect(0,0,1280,720),0,0);texture.Apply();RenderTexture.active=null;
                var colors=new HashSet<int>();int sampled=0,nonBlack=0;var pixels=texture.GetPixels32();
                for(int i=0;i<pixels.Length;i+=499){var c=pixels[i];sampled++;if(c.r>8||c.g>8||c.b>8)nonBlack++;colors.Add((c.r<<16)|(c.g<<8)|c.b);}
                report.minimumColors=Math.Min(report.minimumColors,colors.Count);report.minimumNonBlackFraction=Math.Min(report.minimumNonBlackFraction,nonBlack/(float)sampled);
                File.WriteAllBytes(Path.Combine(folder,"frame_"+frame.ToString("D4")+".png"),texture.EncodeToPNG());Destroy(texture);report.frames++;
            }
            report.finishedUtc=DateTime.UtcNow.ToString("O");report.passed=report.validationPassed&&report.frames==61&&report.minimumColors>=16&&report.minimumNonBlackFraction>.2f;
            File.WriteAllText(Path.Combine(folder,"capture_report.json"),JsonUtility.ToJson(report,true));Debug.Log("FIXED16_CAPTURE_COMPLETE");Application.Quit(report.passed?0:4);
        }
        static TextMesh Label(Camera camera,Font font,string text,Vector3 position,float pixels)
        {
            var item=new GameObject("16 日本語注記");item.layer=31;item.transform.SetParent(camera.transform,false);item.transform.localPosition=position;
            var label=item.AddComponent<TextMesh>();label.font=font;label.fontSize=32;label.characterSize=1;label.anchor=TextAnchor.UpperLeft;label.color=new Color(.97f,.95f,.88f);label.text=text;
            var renderer=item.GetComponent<MeshRenderer>();renderer.sharedMaterial=font.material;item.transform.localScale=Vector3.one*(pixels/Mathf.Max(.001f,renderer.bounds.size.y));return label;
        }
        [Serializable]class CaptureReport{public string unity,startedUtc,finishedUtc,method;public int width,height,sampleRate,frames,minimumColors;public float minimumNonBlackFraction;public bool validationPassed,performanceMeasured,hmdVerified,fluidVerified,passed;}
    }
}
