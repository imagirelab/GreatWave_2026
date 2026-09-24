using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave
{
    public class Sampling19Recorder:MonoBehaviour
    {
        public Sampling19Player player;public Camera cameraToRender;public TextAsset source;public Light sun;public GameObject occluder;public Material depthMaterial,captionMaterial;
        RenderTexture target;Camera overlay;TextMesh title,caption;Font font;
        IEnumerator Start()
        {
            var args=Environment.GetCommandLineArgs();int ix=Array.IndexOf(args,"--capture-dir");if(ix<0||ix+1>=args.Length)yield break;
            string folder=Path.GetFullPath(args[ix+1]);Directory.CreateDirectory(folder);player.recording=true;yield return null;yield return null;
            var reference=Sampling19Reference.Read(source);var validation=Sampling19Validation.Measure(player,reference);File.WriteAllText(Path.Combine(folder,"validation.json"),JsonUtility.ToJson(validation,true));if(!validation.passed){Debug.LogError("SAMPLING19_GEOMETRY_FAILED");Application.Quit(3);yield break;}
            var report=new Report{unity=Application.unityVersion,startedUtc=DateTime.UtcNow.ToString("O"),method="Windows実行版の実Alembicを30/60Hzで保持再生。実Camera.Render採録。別に18の正式ABC/VATを19のShadowCaster付きshaderでPC2カメラ深度/影検査。",width=1280,height=720,videoRate=60,gpu=SystemInfo.graphicsDeviceName,api=SystemInfo.graphicsDeviceType.ToString(),ipdMetres=.064f};
            QualitySettings.vSyncCount=0;QualitySettings.antiAliasing=0;Application.targetFrameRate=-1;cameraToRender.allowMSAA=false;cameraToRender.enabled=false;cameraToRender.cullingMask&=~(1<<31);cameraToRender.depthTextureMode=DepthTextureMode.Depth;
            target=new RenderTexture(1280,720,24);target.Create();cameraToRender.targetTexture=target;SetupOverlay();
            title.text="19　左：30Hz　／　右：60Hz（同じ新規FLIPの実時刻）";
            for(int k=0;k<=120;k++)
            {
                var p=reference.samples[k].positions;var bounds=new Bounds(p[0],Vector3.zero);foreach(var q in p)bounds.Encapsulate(q);
                // 実HMD運動ではない。同じ自動移動/距離を左右に適用し、初期と崩壊部を見やすくする。
                float distance=Mathf.Max(3.4f,bounds.size.magnitude*1.25f);float angle=6*Mathf.Sin(k/120f*Mathf.PI*2);
                cameraToRender.transform.position=bounds.center+Quaternion.Euler(0,angle,0)*new Vector3(.58f,.5f,-.72f).normalized*distance;cameraToRender.transform.LookAt(bounds.center);cameraToRender.aspect=640f/612;
                foreach(int rate in new[]{30,60}){player.SetSample(k,rate);cameraToRender.rect=new Rect(rate==30?0:.5f,.15f,.5f,.85f);cameraToRender.Render();}
                caption.text="表示時刻 "+(k/60f).ToString("F3")+"秒 / 左保持 "+((k/2*2)/60f).ToString("F3")+"秒 / 右 "+(k/60f).ToString("F3")+"秒 / 自動カメラ・HMD未検証";overlay.Render();Save(target,Path.Combine(folder,"frame_"+k.ToString("D4")+".png"));report.frames++;yield return null;
            }
            // 固定した共通カメラを対照として保存する。動画のbounds追従と混同しない。
            cameraToRender.transform.position=new Vector3(11,8,-13);cameraToRender.transform.LookAt(new Vector3(0,.65f,0));cameraToRender.aspect=640f/612;
            foreach(int k in new[]{45,83,111})
            {
                foreach(int rate in new[]{30,60}){player.SetSample(k,rate);cameraToRender.rect=new Rect(rate==30?0:.5f,.15f,.5f,.85f);cameraToRender.Render();}
                title.text="19 固定カメラ対照：左30Hz保持／右60Hz";caption.text=(k/60f).ToString("F3")+"秒 / 同じ固定姿勢・透視投影 / 近景の動画とは取景が異なる / HMD未検証";overlay.Render();Save(target,Path.Combine(folder,"fixed_"+k.ToString("D3")+".png"));
            }
            player.HideSampling();player.shadowFixture.gameObject.SetActive(true);player.shadowFixture.recording=true;occluder.SetActive(true);cameraToRender.rect=new Rect(0,0,1,1);cameraToRender.aspect=640f/480;cameraToRender.fieldOfView=45;
            var color=new RenderTexture(640,480,24,RenderTextureFormat.ARGB32);color.Create();cameraToRender.targetTexture=color;var depthCapture=cameraToRender.gameObject.AddComponent<Sampling19DepthCapture>();depthCapture.Configure(depthMaterial,640,480);
            var records=new List<DepthShadow>();
            foreach(int k in new[]{0,24,48})foreach(int eye in new[]{-1,1})
            {
                occluder.transform.position=new Vector3(-.5f+k/48f,.7f,-.5f);var center=new Vector3(0,.65f,0);var position=k==0?new Vector3(2.8f,2.3f,-3.8f):new Vector3(11,8,-13);cameraToRender.transform.position=position;cameraToRender.transform.LookAt(center);cameraToRender.transform.position+=cameraToRender.transform.right*(eye*.032f);
                var record=new DepthShadow{sample24=k,seconds=k/24f,eye=eye,cameraPosition=cameraToRender.transform.position,cameraRotation=cameraToRender.transform.rotation,fieldOfView=cameraToRender.fieldOfView,occluderPosition=occluder.transform.position};
                var colors=new List<Texture2D>();var depths=new List<Texture2D>();var shadows=new List<Texture2D>();var depthArrays=new List<float[]>();var shadowArrays=new List<Color32[]>();var receivedCounts=new List<int>();
                player.shadowFixture.gameObject.SetActive(false);cameraToRender.Render();var emptyDepth=ReadDepth(depthCapture.eyeDepth);var noShadow=ReadColor(color);player.shadowFixture.gameObject.SetActive(true);
                foreach(bool vat in new[]{false,true})
                {
                    player.shadowFixture.SelectFormat(vat);player.shadowFixture.SetSample(k);var root=vat?player.shadowFixture.vatRoot:player.shadowFixture.stream.gameObject;var renderers=root.GetComponentsInChildren<Renderer>();
                    foreach(var r in renderers)r.shadowCastingMode=ShadowCastingMode.On;
                    cameraToRender.Render();colors.Add(ReadColor(color));var values=ReadDepth(depthCapture.eyeDepth);depthArrays.Add(values);depths.Add(ReadColor(depthCapture.visualDepth));
                    foreach(var r in renderers)r.shadowCastingMode=ShadowCastingMode.ShadowsOnly;
                    cameraToRender.Render();var shadow=ReadColor(color);shadows.Add(shadow);shadowArrays.Add(shadow.GetPixels32());foreach(var r in renderers)r.shadowCastingMode=ShadowCastingMode.On;
                    if(k==0)
                    {
                        // 別物体から流体への受影。光線の上流へ所有cubeを置き、見た目は消して影だけを切り替える。
                        var blocker=occluder.GetComponent<Renderer>();var oldPosition=occluder.transform.position;var oldScale=occluder.transform.localScale;
                        occluder.transform.position=new Vector3(.67f,1.15f,-.12f)-sun.transform.forward*1.4f;occluder.transform.localScale=Vector3.one*.45f;record.receiverBlockerPosition=occluder.transform.position;
                        blocker.shadowCastingMode=ShadowCastingMode.ShadowsOnly;blocker.enabled=false;root.SetActive(false);cameraToRender.Render();var receiverFloorDepth=ReadDepth(depthCapture.eyeDepth);root.SetActive(true);
                        cameraToRender.Render();var receiveOff=ReadColor(color);var receiveOffDepth=ReadDepth(depthCapture.eyeDepth);
                        blocker.enabled=true;cameraToRender.Render();var receiveOn=ReadColor(color);var receiveOnDepth=ReadDepth(depthCapture.eyeDepth);
                        record.receiverMaximumDepthChange=Mathf.Max(record.receiverMaximumDepthChange,receiveOnDepth.Zip(receiveOffDepth,(a,b)=>Math.Abs(a-b)).Max());
                        blocker.shadowCastingMode=ShadowCastingMode.On;occluder.transform.position=oldPosition;occluder.transform.localScale=oldScale;
                        var on=receiveOn.GetPixels32();var off=receiveOff.GetPixels32();receivedCounts.Add(Enumerable.Range(0,values.Length).Count(i=>receiveOffDepth[i]<receiverFloorDepth[i]-.001f&&off[i].r+off[i].g+off[i].b-(on[i].r+on[i].g+on[i].b)>9));
                        if(vat)Pair(receiveOff,receiveOn,"19 VAT受影：左 遮蔽物の影なし／右 影あり",record,Path.Combine(folder,"receive_000_"+(eye<0?"L":"R")+".png"));Destroy(receiveOff);Destroy(receiveOn);
                    }
                }
                var raw=ReadDepth(depthCapture.rawDepth);record.rawDepthFinite=raw.All(v=>!float.IsNaN(v)&&!float.IsInfinity(v));record.rawDepthMin=raw.Min();record.rawDepthMax=raw.Max();record.depthCallbackCount=depthCapture.callbackCount;record.zBufferParams=depthCapture.zBufferParams;record.depthPixelsChanged=Enumerable.Range(0,emptyDepth.Length).Count(i=>Math.Abs(depthArrays[0][i]-emptyDepth[i])>.001f);record.maximumDepthDifference=depthArrays[0].Zip(depthArrays[1],(a,b)=>Math.Abs(a-b)).Max();record.depthFinite=depthArrays.SelectMany(x=>x).All(v=>!float.IsNaN(v)&&!float.IsInfinity(v)&&v>0);
                var baseline=noShadow.GetPixels32();record.shadowPixelsChanged=Enumerable.Range(0,baseline.Length).Count(i=>Difference(shadowArrays[0][i],baseline[i])>3);record.shadowPixelsChangedVAT=Enumerable.Range(0,baseline.Length).Count(i=>Difference(shadowArrays[1][i],baseline[i])>3);record.meanShadowColorDifference=shadowArrays[0].Zip(shadowArrays[1],(a,b)=>(double)Difference(a,b)).Average();
                record.receiverTested=k==0;if(record.receiverTested){record.receiverChangedABC=receivedCounts[0];record.receiverChangedVAT=receivedCounts[1];record.receiverPassed=record.receiverMaximumDepthChange<.00001f&&receivedCounts.All(v=>v>20)&&receivedCounts[0]==receivedCounts[1];}
                record.passed=(!record.receiverTested||record.receiverPassed)&&record.rawDepthFinite&&record.rawDepthMax>record.rawDepthMin&&record.depthCallbackCount>0&&record.depthFinite&&record.depthPixelsChanged>30&&record.maximumDepthDifference<.002f&&record.shadowPixelsChanged>30&&record.shadowPixelsChangedVAT>30&&record.meanShadowColorDifference<1;records.Add(record);
                string stem=k.ToString("D3")+(eye<0?"_L":"_R");Pair(colors[0],colors[1],"19 色：左Alembic／右VAT・同じ18実試料",record,Path.Combine(folder,"color_"+stem+".png"));Pair(depths[0],depths[1],"19 CameraDepthTexture：左Alembic／右VAT",record,Path.Combine(folder,"depth_"+stem+".png"));Pair(shadows[0],shadows[1],"19 実受影床：左Alembic／右VAT（本体非表示）",record,Path.Combine(folder,"shadow_"+stem+".png"));
                foreach(var t in colors.Concat(depths).Concat(shadows))Destroy(t);Destroy(noShadow);yield return null;
            }
            report.depthShadow=records.ToArray();report.finishedUtc=DateTime.UtcNow.ToString("O");report.passed=validation.passed&&report.frames==121&&records.Count==6&&records.All(r=>r.passed);File.WriteAllText(Path.Combine(folder,"capture_report.json"),JsonUtility.ToJson(report,true));Debug.Log(report.passed?"SAMPLING19_CAPTURE_PASS":"SAMPLING19_CAPTURE_FAILED");Application.Quit(report.passed?0:4);
        }
        float[]ReadDepth(RenderTexture depth){RenderTexture.active=depth;var texture=new Texture2D(depth.width,depth.height,TextureFormat.RGBAFloat,false,true);texture.ReadPixels(new Rect(0,0,depth.width,depth.height),0,0);texture.Apply();RenderTexture.active=null;var values=texture.GetPixels().Select(c=>c.r).ToArray();Destroy(texture);return values;}
        static Texture2D ReadColor(RenderTexture target){RenderTexture.active=target;var texture=new Texture2D(target.width,target.height,TextureFormat.RGB24,false);texture.ReadPixels(new Rect(0,0,target.width,target.height),0,0);texture.Apply();RenderTexture.active=null;return texture;}
        static int Difference(Color32 a,Color32 b)=>Math.Max(Math.Abs(a.r-b.r),Math.Max(Math.Abs(a.g-b.g),Math.Abs(a.b-b.b)));
        static void Save(RenderTexture render,string path){var texture=ReadColor(render);File.WriteAllBytes(path,texture.EncodeToPNG());Destroy(texture);}
        void Pair(Texture2D a,Texture2D b,string heading,DepthShadow r,string path)
        {
            RenderTexture.active=target;GL.PushMatrix();GL.LoadPixelMatrix(0,1280,720,0);GL.Clear(true,true,new Color(.025f,.065f,.1f));Graphics.DrawTexture(new Rect(0,0,640,612),a);Graphics.DrawTexture(new Rect(640,0,640,612),b);GL.PopMatrix();RenderTexture.active=null;title.text=heading;caption.text=r.seconds.ToString("F3")+"秒 / 人工"+(r.eye<0?"左":"右")+"視点 / IPD64mm / 実XR・頭部追跡・深度提出は未検証";overlay.Render();Save(target,path);
        }
        void SetupOverlay()
        {
            overlay=new GameObject("19 実記録注記").AddComponent<Camera>();overlay.transform.position=new Vector3(2000,2000,2000);overlay.orthographic=true;overlay.orthographicSize=360;overlay.aspect=1280f/720;overlay.nearClipPlane=.1f;overlay.farClipPlane=20;overlay.clearFlags=CameraClearFlags.Depth;overlay.cullingMask=1<<31;overlay.targetTexture=target;overlay.enabled=false;
            var panel=GameObject.CreatePrimitive(PrimitiveType.Cube);panel.layer=31;panel.transform.SetParent(overlay.transform,false);panel.transform.localPosition=new Vector3(0,-303,8);panel.transform.localScale=new Vector3(1280,114,.1f);panel.GetComponent<Renderer>().sharedMaterial=captionMaterial;
            font=Font.CreateDynamicFontFromOSFont(new[]{"Yu Gothic","Meiryo","Microsoft YaHei UI"},32);title=Label("19",-254,21);caption=Label("試料",-287,17);Label("PC技術試験 / 元面の体積誤差と後半流出を含む / 記録fpsは性能値ではない / 方式採用は20で判断",-320,16);
        }
        TextMesh Label(string text,float y,float pixels){var go=new GameObject("19 日本語注記");go.layer=31;go.transform.SetParent(overlay.transform,false);go.transform.localPosition=new Vector3(-610,y,7);var label=go.AddComponent<TextMesh>();label.font=font;label.fontSize=32;label.characterSize=1;label.anchor=TextAnchor.UpperLeft;label.color=new Color(.97f,.95f,.88f);label.text=text;var renderer=go.GetComponent<MeshRenderer>();renderer.sharedMaterial=font.material;go.transform.localScale=Vector3.one*(pixels/Mathf.Max(.001f,renderer.bounds.size.y));return label;}
        [Serializable]public class Report{public string unity,startedUtc,finishedUtc,method,gpu,api;public int width,height,videoRate,frames;public float ipdMetres;public bool passed,hmdVerified,xrDepthSubmissionVerified;public DepthShadow[]depthShadow;}
        [Serializable]public class DepthShadow{public int sample24,eye,depthPixelsChanged,shadowPixelsChanged,shadowPixelsChangedVAT,depthCallbackCount,receiverChangedABC,receiverChangedVAT;public float seconds,fieldOfView,maximumDepthDifference,rawDepthMin,rawDepthMax,receiverMaximumDepthChange;public double meanShadowColorDifference;public bool depthFinite,rawDepthFinite,passed,receiverTested,receiverPassed;public Vector3 cameraPosition,occluderPosition,receiverBlockerPosition;public Vector4 zBufferParams;public Quaternion cameraRotation;}
    }
}
