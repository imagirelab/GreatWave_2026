using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace GreatWave
{
    public class M1EvidenceRecorder : MonoBehaviour
    {
        public M1DesktopViewer viewer;
        public Material captionMaterial;
        const int Rate=24,Frames=480;

        IEnumerator Start()
        {
            var args=Environment.GetCommandLineArgs(); int arg=Array.IndexOf(args,"--capture-dir");
            if(arg<0||arg+1>=args.Length) yield break;
            if(Array.IndexOf(args,"--vr")>=0) { Debug.LogError("M1はPCの静止構図検証です。VR記録ではありません。"); Application.Quit(2); yield break; }
            string folder=Path.GetFullPath(args[arg+1]); Directory.CreateDirectory(folder);
            yield return null; yield return null;
            var report=new Report{unity=Application.unityVersion,device=SystemInfo.graphicsDeviceName,graphicsApi=SystemInfo.graphicsDeviceType.ToString(),
                startedUtc=DateTime.UtcNow.ToString("O"),width=1280,height=720,frameRate=Rate,minimumNonBlackFraction=1,minimumSampledColors=int.MaxValue,
                mode="PC実行ビルド・静止形状・記録用自動カメラ",renderMethod="Camera.Renderと注記用Camera → RenderTexture → ReadPixels。表示窓の録画ではない。",
                inputMethod="Input System仮想キーボードイベント。物理操作ではない。",performanceMeasurement=false,hmdVerified=false,fluidVerified=false};
            var background=InputSystem.settings.backgroundBehavior;
            InputSystem.settings.backgroundBehavior=InputSettings.BackgroundBehavior.IgnoreFocus;
            // 非表示起動時のフォーカス変更が落ち着いてから、検査用デバイスを明示的に有効化する。
            yield return null; yield return null;
            var keyboard=InputSystem.AddDevice<Keyboard>();
            InputSystem.EnableDevice(keyboard); keyboard.MakeCurrent();
            viewer.testKeyboard=keyboard;
            yield return null;
            report.virtualKeyboardEnabled=keyboard.enabled;
            report.applicationFocusedDuringInput=Application.isFocused;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.Digit2)); yield return null; yield return null;
            report.inputBoatView=viewer.CurrentView==1&&Vector3.Distance(viewer.viewCamera.transform.position,viewer.views[1].position)<.001f;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState()); yield return null;
            var initial=viewer.viewCamera.transform.rotation;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.RightArrow));
            float until=Time.realtimeSinceStartup+.2f; while(Time.realtimeSinceStartup<until) yield return null;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState()); yield return null;
            report.inputLook=Quaternion.Angle(initial,viewer.viewCamera.transform.rotation)>.1f;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.Space)); yield return null; yield return null;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState()); yield return null;
            var stopped=viewer.viewCamera.transform.rotation;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.RightArrow));
            until=Time.realtimeSinceStartup+.1f; while(Time.realtimeSinceStartup<until) yield return null;
            report.inputPause=viewer.Paused&&Quaternion.Angle(stopped,viewer.viewCamera.transform.rotation)<.001f;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.R)); yield return null; yield return null;
            report.inputReset=!viewer.Paused&&Quaternion.Angle(initial,viewer.viewCamera.transform.rotation)<.001f;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.Digit5)); yield return null; yield return null;
            report.inputMapView=viewer.CurrentView==4&&viewer.mapOverlay.activeSelf;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState(Key.Digit1)); yield return null; yield return null;
            report.inputComparison=viewer.CurrentView==0&&!viewer.mapOverlay.activeSelf;
            InputSystem.QueueStateEvent(keyboard,new KeyboardState()); yield return null;
            viewer.testKeyboard=null; InputSystem.RemoveDevice(keyboard); InputSystem.settings.backgroundBehavior=background;
            bool inputPassed=report.virtualKeyboardEnabled&&report.inputBoatView&&report.inputLook&&report.inputPause&&report.inputReset&&report.inputMapView&&report.inputComparison;
            if(!inputPassed) { File.WriteAllText(Path.Combine(folder,"capture_report.json"),JsonUtility.ToJson(report,true)); Debug.LogError("M1_INPUT_EVENT_TEST_FAILED"); Application.Quit(3); yield break; }
            viewer.recording=true;
            var camera=viewer.viewCamera;
            var target=new RenderTexture(1280,720,24); target.Create(); camera.targetTexture=target; camera.cullingMask&=~(1<<31);
            var overlay=new GameObject("M1 evidence caption camera").AddComponent<Camera>();
            overlay.transform.position=new Vector3(2000,2000,2000); overlay.orthographic=true; overlay.orthographicSize=360; overlay.aspect=1280f/720;
            overlay.nearClipPlane=.1f; overlay.farClipPlane=20; overlay.clearFlags=CameraClearFlags.Depth; overlay.cullingMask=1<<31; overlay.targetTexture=target; overlay.enabled=false;
            var panel=GameObject.CreatePrimitive(PrimitiveType.Cube); panel.layer=31; panel.transform.SetParent(overlay.transform,false);
            panel.transform.localPosition=new Vector3(0,-313,8); panel.transform.localScale=new Vector3(1248,82,.1f); panel.GetComponent<Renderer>().sharedMaterial=captionMaterial;
            var font=Font.CreateDynamicFontFromOSFont(new[]{"Yu Gothic","Meiryo","Microsoft YaHei UI","MS Gothic"},32);
            var heading=Label(overlay,font,"M1 静止構図",new Vector3(-608,-282,7),20);
            var status=Label(overlay,font,"自動カメラ / オフスクリーン描画 / 流体未検証 / HMD未検証",new Vector3(-608,-313,7),16);
            var detail=Label(overlay,font,"",new Vector3(-608,-337,7),14);
            Time.captureFramerate=Rate;
            for(int frame=0;frame<Frames;frame++)
            {
                int view=frame/96; float t=(frame%96)/(float)Rate;
                viewer.SelectView(view);
                if(view==1) camera.transform.rotation*=Quaternion.Euler(-5*Mathf.Sin(t*.8f),7*Mathf.Sin(t*.7f),0);
                if(view==2||view==3) { camera.transform.position+=Vector3.right*(2*Mathf.Sin(t*.7f)); camera.transform.LookAt(viewer.views[view].target); }
                heading.text="神奈川沖浪裏 — M1 静止構図 / "+viewer.views[view].label;
                detail.text=view==4?"黄緑：将来の船中心候補　赤：波の水平投影　橙：現在の構図用船　実船の通過・操船は未検証":"新規制作の形状模型 / 物理的な波・完成版の浮世絵表現ではありません";
                yield return new WaitForEndOfFrame();
                camera.Render(); overlay.Render(); RenderTexture.active=target;
                var image=new Texture2D(1280,720,TextureFormat.RGB24,false); image.ReadPixels(new Rect(0,0,1280,720),0,0); image.Apply(); RenderTexture.active=null;
                var pixels=image.GetPixels32(); var colors=new HashSet<int>(); int count=0,nonBlack=0;
                for(int p=0;p<pixels.Length;p+=499) { var c=pixels[p]; count++; if(c.r>8||c.g>8||c.b>8)nonBlack++; colors.Add((c.r<<16)|(c.g<<8)|c.b); }
                report.minimumNonBlackFraction=Math.Min(report.minimumNonBlackFraction,nonBlack/(float)count); report.minimumSampledColors=Math.Min(report.minimumSampledColors,colors.Count);
                File.WriteAllBytes(Path.Combine(folder,"frame_"+frame.ToString("D4")+".png"),image.EncodeToPNG()); Destroy(image); report.capturedFrames++;
            }
            Time.captureFramerate=0;
            report.finishedUtc=DateTime.UtcNow.ToString("O");
            report.passed=inputPassed&&report.capturedFrames==Frames&&report.minimumNonBlackFraction>.2f&&report.minimumSampledColors>=8;
            File.WriteAllText(Path.Combine(folder,"capture_report.json"),JsonUtility.ToJson(report,true));
            Debug.Log("M1_CAPTURE_COMPLETE: "+report.capturedFrames+" actual offscreen frames; synthetic24fps"); Application.Quit(report.passed?0:4);
        }

        static TextMesh Label(Camera camera,Font font,string text,Vector3 position,float pixels)
        {
            var item=new GameObject("M1 Japanese evidence label"); item.layer=31; item.transform.SetParent(camera.transform,false); item.transform.localPosition=position;
            var label=item.AddComponent<TextMesh>(); label.font=font; label.fontSize=32; label.characterSize=1; label.anchor=TextAnchor.UpperLeft; label.color=new Color(.97f,.95f,.88f); label.text=string.IsNullOrEmpty(text)?"仮":text;
            var renderer=item.GetComponent<MeshRenderer>(); renderer.sharedMaterial=font.material;
            item.transform.localScale=Vector3.one*(pixels/Mathf.Max(.001f,renderer.bounds.size.y)); label.text=text; return label;
        }
        [Serializable] class Report
        {
            public string unity,device,graphicsApi,startedUtc,finishedUtc,mode,renderMethod,inputMethod;
            public int width,height,frameRate,capturedFrames,minimumSampledColors;
            public float minimumNonBlackFraction;
            public bool virtualKeyboardEnabled,applicationFocusedDuringInput,inputBoatView,inputLook,inputPause,inputReset,inputMapView,inputComparison,performanceMeasurement,hmdVerified,fluidVerified,passed;
        }
    }
}
