using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Profiling;

namespace GreatWave
{
    public class Playback18Recorder:MonoBehaviour
    {
        public Playback18Player player;
        public Camera cameraToRender;
        public TextAsset reference;
        public Material captionMaterial;
        IEnumerator Start()
        {
            var args=Environment.GetCommandLineArgs();int index=Array.IndexOf(args,"--capture-dir");if(index<0||index+1>=args.Length)yield break;
            string folder=Path.GetFullPath(args[index+1]);Directory.CreateDirectory(folder);player.recording=true;
            yield return null;yield return null;
            var timer=Stopwatch.StartNew();var source=Playback18Reference.Read(reference);double referenceLoad=timer.Elapsed.TotalMilliseconds;
            var abc=Playback18Validation.Alembic(player.stream,source);File.WriteAllText(Path.Combine(folder,"alembic_validation.json"),JsonUtility.ToJson(abc,true));
            var vat=Playback18VATValidation.Measure(player.vatRoot,player.vatData,player.vatDecoder,source);File.WriteAllText(Path.Combine(folder,"vat_validation.json"),JsonUtility.ToJson(vat,true));
            if(!abc.passed||!vat.passed){UnityEngine.Debug.LogError("PLAYBACK18_RUNTIME_VALIDATION_FAILED");Application.Quit(3);yield break;}
            var report=new Report{unity=Application.unityVersion,startedUtc=DateTime.UtcNow.ToString("O"),method="Windows実行版の実ABCと実Fluid VATを同じカメラで順にCamera.Render。左右合成は実描画、OS画面録画ではない。",width=1280,height=720,rate=24,referenceReadMilliseconds=referenceLoad,
                gpu=SystemInfo.graphicsDeviceName,graphicsApi=SystemInfo.graphicsDeviceType.ToString(),cpu=SystemInfo.processorType,systemRamMB=SystemInfo.systemMemorySize,graphicsMemoryMB=SystemInfo.graphicsMemorySize,startupToValidationSeconds=Time.realtimeSinceStartup};
            var all=source.samples.SelectMany(s=>s.positions).ToArray();var bounds=new Bounds(all[0],Vector3.zero);foreach(var p in all)bounds.Encapsulate(p);bounds.Expand(.002f);
            foreach(var renderer in player.vatRoot.GetComponentsInChildren<Renderer>(true))renderer.localBounds=bounds;
            report.animationBoundsMin=bounds.min;report.animationBoundsMax=bounds.max;report.runtimeTextures=new[]{player.vatData.position,player.vatData.rotation,player.vatData.lookup}.Select(t=>new TextureInfo{name=t.name,width=t.width,height=t.height,format=t.format.ToString(),graphicsFormat=t.graphicsFormat.ToString(),mips=t.mipmapCount,estimatedGpuTexelBytes=(long)t.width*t.height*16,unityRuntimeSizeBytes=Profiler.GetRuntimeMemorySizeLong(t)}).ToArray();
            report.textureDimensionsMatch=player.vatData.position.width==1024&&player.vatData.position.height==1066&&player.vatData.lookup.width==2048&&player.vatData.lookup.height==6174;
            var target=new RenderTexture(1280,720,24);target.Create();cameraToRender.targetTexture=target;cameraToRender.enabled=false;cameraToRender.cullingMask&=~(1<<31);
            QualitySettings.vSyncCount=0;Application.targetFrameRate=-1;
            cameraToRender.rect=new Rect(0,0,1,1);cameraToRender.aspect=1280f/720;
            var timings=new List<Timing>();
            foreach(bool useVat in new[]{false,true})
            {
                player.SelectFormat(useVat);
                for(int k=0;k<49;k++){player.SetSample(k);cameraToRender.Render();FrameTimingManager.CaptureFrameTimings();yield return null;}
                var updates=new List<double>();var renders=new List<double>();var frameTimes=new List<double>();var cpuTimings=new List<double>();var gpuTimings=new List<double>();double last=Time.realtimeSinceStartupAsDouble;
                var seenTimestamps=new HashSet<ulong>();var priorTiming=new FrameTiming[1];ulong minimumTimestamp=FrameTimingManager.GetLatestTimings(1,priorTiming)>0?priorTiming[0].frameStartTimestamp:0;
                for(int repeat=0;repeat<3;repeat++)for(int k=0;k<49;k++)
                {
                    timer.Restart();player.SetSample(k);timer.Stop();updates.Add(timer.Elapsed.TotalMilliseconds);
                    timer.Restart();cameraToRender.Render();timer.Stop();renders.Add(timer.Elapsed.TotalMilliseconds);
                    FrameTimingManager.CaptureFrameTimings();yield return null;
                    double now=Time.realtimeSinceStartupAsDouble;frameTimes.Add((now-last)*1000);last=now;
                    // APIの遅延と同一値の再取得を避け、形式ごとの49 warm-up後の新しい記録だけを採る。
                    var timing=new FrameTiming[1];if(FrameTimingManager.GetLatestTimings(1,timing)>0&&timing[0].frameStartTimestamp>minimumTimestamp&&seenTimestamps.Add(timing[0].frameStartTimestamp)){if(timing[0].cpuFrameTime>0)cpuTimings.Add(timing[0].cpuFrameTime);if(timing[0].gpuFrameTime>0)gpuTimings.Add(timing[0].gpuFrameTime);}
                }
                timings.Add(new Timing{format=useVat?"Fluid VAT HDR":"Alembic2.4.4",samples=147,warmupSamples=49,cpuUpdate=Stats(updates),cpuRenderSubmission=Stats(renders),observedLoopInterval=Stats(frameTimes),frameTimingCpu=Stats(cpuTimings),frameTimingGpu=Stats(gpuTimings),processPrivateBytes=Process.GetCurrentProcess().PrivateMemorySize64,
                    method="1280×720・同一視点/片面shader・vSync0・targetFrameRate無制限。画像読戻し/保存/形状検査なし。Camera.Render計時はCPU呼出しでGPU専用時間ではない。FrameTimingはwarm-up中も採取し、段階開始時より新しい一意timestampだけ使用。両形式のassetが同時常駐するためprocess memory差を形式固有量としない。"});
            }
            report.timings=timings.ToArray();File.WriteAllText(Path.Combine(folder,"performance.json"),JsonUtility.ToJson(report,true));
            // 動画は49枚の実サンプルを採録し、再生では0〜47を24Hz・2秒にする。末端48は静止画へ保存。
            var overlay=new GameObject("18 記録注記").AddComponent<Camera>();overlay.transform.position=new Vector3(2000,2000,2000);overlay.orthographic=true;overlay.orthographicSize=360;overlay.aspect=1280f/720;overlay.nearClipPlane=.1f;overlay.farClipPlane=20;overlay.clearFlags=CameraClearFlags.Depth;overlay.cullingMask=1<<31;overlay.targetTexture=target;overlay.enabled=false;
            var panel=GameObject.CreatePrimitive(PrimitiveType.Cube);panel.layer=31;panel.transform.SetParent(overlay.transform,false);panel.transform.localPosition=new Vector3(0,-303,8);panel.transform.localScale=new Vector3(1280,114,.1f);panel.GetComponent<Renderer>().sharedMaterial=captionMaterial;
            var font=Font.CreateDynamicFontFromOSFont(new[]{"Yu Gothic","Meiryo","Microsoft YaHei UI","MS Gothic"},32);
            Label(overlay,font,"18　左：Alembic　／　右：Fluid VAT（専用Built-in復号）",new Vector3(-610,-254,7),21);
            var label=Label(overlay,font,"時刻 0.000 秒",new Vector3(-610,-287,7),18);
            Label(overlay,font,"17の同じ実FLIP・49離散時刻 / 元面の体積膨張と後半流出を含む / 物理精度・HMD未検証",new Vector3(-610,-320,7),16);
            cameraToRender.aspect=640f/612;cameraToRender.transform.position=new Vector3(14,12,-18);cameraToRender.transform.LookAt(new Vector3(0,.6f,0));
            for(int k=0;k<49;k++)
            {
                RenderPair(k,target,overlay,label,false);Save(target,Path.Combine(folder,"frame_"+k.ToString("D4")+".png"),report);report.frames++;yield return null;
            }
            foreach(int k in new[]{0,3,18,19,24,48})
            {
                var current=source.samples[k].positions;var box=new Bounds(current[0],Vector3.zero);foreach(var p in current)box.Encapsulate(p);
                float distance=Mathf.Max(2.7f,box.size.magnitude*1.25f);cameraToRender.transform.position=box.center+new Vector3(.58f,.5f,-.72f).normalized*distance;cameraToRender.transform.LookAt(box.center);
                RenderPair(k,target,overlay,label,true);Save(target,Path.Combine(folder,"detail_"+k.ToString("D3")+".png"),report);yield return null;
            }
            report.finishedUtc=DateTime.UtcNow.ToString("O");report.passed=abc.passed&&vat.passed&&report.textureDimensionsMatch&&report.frames==49&&report.minimumColors>=16&&report.minimumNonBlackFraction>.2f;
            File.WriteAllText(Path.Combine(folder,"capture_report.json"),JsonUtility.ToJson(report,true));UnityEngine.Debug.Log("PLAYBACK18_CAPTURE_COMPLETE");Application.Quit(report.passed?0:4);
        }
        void RenderPair(int k,RenderTexture target,Camera overlay,TextMesh label,bool detail)
        {
            foreach(bool useVat in new[]{false,true}){player.SelectFormat(useVat);player.SetSample(k);cameraToRender.rect=new Rect(useVat?.5f:0,.15f,.5f,.85f);cameraToRender.Render();}
            label.text="時刻 "+(k/24f).ToString("F3")+" 秒 / 実行版・オフスクリーン描画 / 24Hz記録（性能とは別） / "+(detail?"同じ近景画角":"共通の固定画角");overlay.Render();
        }
        static void Save(RenderTexture target,string path,Report report)
        {
            RenderTexture.active=target;var texture=new Texture2D(target.width,target.height,TextureFormat.RGB24,false);texture.ReadPixels(new Rect(0,0,target.width,target.height),0,0);texture.Apply();RenderTexture.active=null;
            var colors=new HashSet<int>();int count=0,nonBlack=0;var pixels=texture.GetPixels32();for(int i=0;i<pixels.Length;i+=499){var c=pixels[i];count++;if(c.r>8||c.g>8||c.b>8)nonBlack++;colors.Add((c.r<<16)|(c.g<<8)|c.b);}
            report.minimumColors=Math.Min(report.minimumColors,colors.Count);report.minimumNonBlackFraction=Math.Min(report.minimumNonBlackFraction,nonBlack/(float)count);File.WriteAllBytes(path,texture.EncodeToPNG());Destroy(texture);
        }
        static TextMesh Label(Camera camera,Font font,string text,Vector3 position,float pixels)
        {
            var item=new GameObject("18 日本語注記");item.layer=31;item.transform.SetParent(camera.transform,false);item.transform.localPosition=position;var label=item.AddComponent<TextMesh>();label.font=font;label.fontSize=32;label.characterSize=1;label.anchor=TextAnchor.UpperLeft;label.color=new Color(.97f,.95f,.88f);label.text=text;var renderer=item.GetComponent<MeshRenderer>();renderer.sharedMaterial=font.material;item.transform.localScale=Vector3.one*(pixels/Mathf.Max(.001f,renderer.bounds.size.y));return label;
        }
        static Distribution Stats(List<double> values){values.Sort();return new Distribution{available=values.Count>0,count=values.Count,median=values.Count>0?values[values.Count/2]:0,p95=values.Count>0?values[(int)(values.Count*.95)]:0,maximum=values.Count>0?values.Last():0};}
        [Serializable]public class Distribution{public bool available;public int count;public double median,p95,maximum;}
        [Serializable]public class Timing{public string format,method;public int samples,warmupSamples;public Distribution cpuUpdate,cpuRenderSubmission,observedLoopInterval,frameTimingCpu,frameTimingGpu;public long processPrivateBytes;}
        [Serializable]public class TextureInfo{public string name,format,graphicsFormat;public int width,height,mips;public long estimatedGpuTexelBytes,unityRuntimeSizeBytes;}
        [Serializable]public class Report{public string unity,startedUtc,finishedUtc,method,gpu,graphicsApi,cpu;public int width,height,rate,frames,systemRamMB,graphicsMemoryMB,minimumColors=int.MaxValue;public float minimumNonBlackFraction=1,startupToValidationSeconds;public double referenceReadMilliseconds;public Vector3 animationBoundsMin,animationBoundsMax;public bool textureDimensionsMatch,passed,hmdVerified,physicalAccuracyVerified;public Timing[]timings;public TextureInfo[]runtimeTextures;}
    }
}

