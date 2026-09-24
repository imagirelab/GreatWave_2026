using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.Profiling;
namespace GreatWave
{
    public class Decision20Runner:MonoBehaviour
    {
        public Material captionMaterial;
        static readonly Vector3 CameraPosition=new Vector3(14,12,-18),CameraTarget=new Vector3(0,.6f,0);
        IEnumerator Start()
        {
            DontDestroyOnLoad(gameObject);var args=Environment.GetCommandLineArgs();string format=Arg(args,"--format","abc"),folder=Arg(args,"--output",Path.Combine(Application.persistentDataPath,"Decision20"));bool capture=Array.IndexOf(args,"--capture")>=0;int run=int.Parse(Arg(args,"--run","0"));Directory.CreateDirectory(folder);
            var report=new Report{unity=Application.unityVersion,format=format,run=run,startedUtc=DateTime.UtcNow.ToString("O"),gpu=SystemInfo.graphicsDeviceName,cpu=SystemInfo.processorType,api=SystemInfo.graphicsDeviceType.ToString(),frameTimingFeatureEnabled=FrameTimingManager.IsFeatureEnabled(),method="同一build・形式専用sceneの新プロセス初回ロード。OS/GPU cache未制御。計時区間で画像readbackなし。raw.cpuSampleは直時計の対象、同rowのFrameTiming時刻は約4frame前で同一sample負荷と結び付けない。人工2視点は実XRではない。"};
            QualitySettings.vSyncCount=0;QualitySettings.antiAliasing=0;QualitySettings.shadows=ShadowQuality.All;QualitySettings.shadowResolution=ShadowResolution.High;QualitySettings.shadowDistance=45;Application.targetFrameRate=-1;
            var targets=new[]{new RenderTexture(1280,720,24),new RenderTexture(1280,720,24)};foreach(var t in targets)t.Create();
            yield return Resources.UnloadUnusedAssets();GC.Collect();yield return null;report.beforeLoad=Memory();report.beforeFluidTextures=FluidTextureNames();
            var timer=Stopwatch.StartNew();var load=SceneManager.LoadSceneAsync(format=="vat"?"M1_Decision20_VAT":"M1_Decision20_ABC",LoadSceneMode.Single);while(!load.isDone)yield return null;report.sceneLoadMilliseconds=timer.Elapsed.TotalMilliseconds;
            var content=FindFirstObjectByType<Decision20Content>();if(content==null||content.useVat!=(format=="vat"))throw new Exception("形式専用sceneが一致しません。");
            timer.Restart();content.Initialize();report.initializeMilliseconds=timer.Elapsed.TotalMilliseconds;report.afterLoad=Memory();report.afterFluidTextures=FluidTextureNames();
            var camera=content.testCamera;camera.enabled=false;camera.depthTextureMode=DepthTextureMode.Depth;camera.allowMSAA=false;camera.aspect=1280f/720;camera.targetTexture=targets[0];
            timer.Restart();Render(content,targets,1);report.firstRenderCpuMilliseconds=timer.Elapsed.TotalMilliseconds;
            // 初回可視化完了はreadbackの同期を含む。warm計時の前に限って行う。
            timer.Restart();var first=Read(targets[0]);report.firstReadbackMilliseconds=timer.Elapsed.TotalMilliseconds;report.firstImageColors=first.GetPixels32().Where((x,i)=>i%499==0).Select(x=>(x.r<<16)|(x.g<<8)|x.b).Distinct().Count();report.firstFluidPixels=first.GetPixels32().Count(c=>c.b>c.r+12&&c.b>c.g+12);File.WriteAllBytes(Path.Combine(folder,"first_visible.png"),first.EncodeToPNG());Destroy(first);report.afterFirstVisible=Memory();
            report.textures=Resources.FindObjectsOfTypeAll<Texture2D>().Where(t=>t.name.StartsWith("fluid17_")).Select(t=>new TextureInfo{name=t.name,width=t.width,height=t.height,format=t.format.ToString(),graphicsFormat=t.graphicsFormat.ToString(),runtimeBytes=Profiler.GetRuntimeMemorySizeLong(t),mips=t.mipmapCount}).ToArray();
            if(Array.IndexOf(args,"--probe")>=0){File.WriteAllText(Path.Combine(folder,"visibility_probe.json"),JsonUtility.ToJson(report,true));Application.Quit(0);yield break;}
            if(Array.IndexOf(args,"--present")>=0){yield return PresentProbe(content,folder,format);Application.Quit(0);yield break;}
            var timings=new List<Timing>();int[]views=run%2==0?new[]{1,2}:new[]{2,1};
            foreach(int cameraMode in new[]{0,1})foreach(int eyeCount in views)
            {
                content.cameraMode=cameraMode;
                for(int i=0;i<98;i++){content.SetSample(i%49);Render(content,targets,eyeCount);FrameTimingManager.CaptureFrameTimings();yield return null;}
                var update=new List<double>();var submission=new List<double>();var interval=new List<double>();var cpu=new List<double>();var gpu=new List<double>();var main=new List<double>();var renderThread=new List<double>();var memory=new List<MemoryInfo>();var raw=new List<FrameRecord>();int gpuZero=0,gpuMissing=0,gpuInvalid=0;var seen=new HashSet<ulong>();var ft=new FrameTiming[1];ulong minTimestamp=FrameTimingManager.GetLatestTimings(1,ft)>0?ft[0].frameStartTimestamp:0;double previous=Time.realtimeSinceStartupAsDouble;
                for(int i=0;i<980;i++)
                {
                    timer.Restart();content.SetSample(i%49);double u=timer.Elapsed.TotalMilliseconds;timer.Restart();Render(content,targets,eyeCount);double r=timer.Elapsed.TotalMilliseconds;FrameTimingManager.CaptureFrameTimings();yield return null;
                    double now=Time.realtimeSinceStartupAsDouble;double delta=(now-previous)*1000;previous=now;update.Add(u);submission.Add(r);interval.Add(delta);var row=new FrameRecord{ordinal=i,cpuSample=i%49,updateMs=u,submissionMs=r,intervalMs=delta};
                    if(FrameTimingManager.GetLatestTimings(1,ft)>0&&ft[0].frameStartTimestamp>minTimestamp&&seen.Add(ft[0].frameStartTimestamp))
                    {
                        row.timestamp=ft[0].frameStartTimestamp;row.cpuMs=ft[0].cpuFrameTime;row.gpuMs=ft[0].gpuFrameTime;
                        // APIは約4frame遅れる。先頭8回を集計から除外し、終了側の未取得分を推測補充しない。
                        if(i>=8){if(Valid(row.cpuMs))cpu.Add(row.cpuMs);if(Valid(row.gpuMs))gpu.Add(row.gpuMs);else if(row.gpuMs==0)gpuZero++;else gpuInvalid++;if(Valid(ft[0].cpuMainThreadFrameTime))main.Add(ft[0].cpuMainThreadFrameTime);if(Valid(ft[0].cpuRenderThreadFrameTime))renderThread.Add(ft[0].cpuRenderThreadFrameTime);}
                    }else if(i>=8)gpuMissing++;
                    raw.Add(row);
                    if(i%49==48)memory.Add(Memory());
                }
                timings.Add(new Timing{cameraMode=cameraMode==0?"wide":"near_window",views=eyeCount,widthPerView=1280,heightPerView=720,samples=980,warmup=98,frameTimingSkippedHead=8,frameTimingGpuZero=gpuZero,frameTimingGpuMissingOrDuplicate=gpuMissing,frameTimingGpuInvalid=gpuInvalid,cpuUpdate=Stats(update),cpuSubmission=Stats(submission),frameInterval=Stats(interval),frameTimingCpu=Stats(cpu),frameTimingGpu=Stats(gpu),frameTimingMainThread=Stats(main),frameTimingRenderThread=Stats(renderThread),memorySnapshots=memory.ToArray(),raw=raw.ToArray()});
            }
            report.timings=timings.ToArray();report.afterMeasurement=Memory();report.assetIsolationPassed=report.beforeFluidTextures.Length==0&&(format=="abc"?report.afterFluidTextures.Length==0:report.afterFluidTextures.Length==3);report.passed=report.assetIsolationPassed&&report.firstFluidPixels>=100&&timings.All(t=>t.samples==980&&t.cpuUpdate.available)&&report.beforeLoad.nativeAvailable&&report.afterMeasurement.nativeAvailable;
            File.WriteAllText(Path.Combine(folder,"performance.json"),JsonUtility.ToJson(report,true));
            if(capture&&report.passed)
            {
                content.cameraMode=2;var overlay=Overlay(targets[0],format,out var label);camera.targetTexture=targets[0];
                for(int k=0;k<=48;k++){content.SetSample(k);Render(content,targets,1);label.text="時刻 "+(k/24f).ToString("F3")+"秒 / 18の同一24Hz実FLIP / PC暫定評価・HMDと主役波は未検証";overlay.Render();Save(targets[0],Path.Combine(folder,"frame_"+k.ToString("D4")+".png"));yield return null;}
                foreach(int k in new[]{0,24,48}){content.SetSample(k);Render(content,targets,2);for(int eye=0;eye<2;eye++){overlay.targetTexture=targets[eye];label.text=(k/24f).ToString("F3")+"秒 / 人工"+(eye==0?"左":"右")+"視点・IPD64mm / 各1280×720 / HMDではない";overlay.Render();Save(targets[eye],Path.Combine(folder,"stereo_"+k.ToString("D3")+"_"+eye+".png"));}}
                report.capturedFrames=49;
            }
            report.finishedUtc=DateTime.UtcNow.ToString("O");File.WriteAllText(Path.Combine(folder,"result.json"),JsonUtility.ToJson(report,true));UnityEngine.Debug.Log(report.passed?"DECISION20_RUN_PASS":"DECISION20_RUN_FAILED");Application.Quit(report.passed?0:3);
        }
        IEnumerator PresentProbe(Decision20Content content,string folder,string format)
        {
            var camera=content.testCamera;camera.targetTexture=null;camera.enabled=true;camera.transform.position=new Vector3(4,3,-5);camera.transform.LookAt(CameraTarget);
            for(int i=0;i<98;i++){content.SetSample(i%49);FrameTimingManager.CaptureFrameTimings();yield return null;}
            var gpu=new List<double>();var cpu=new List<double>();var seen=new HashSet<ulong>();var ft=new FrameTiming[1];int zero=0,missing=0;ulong start=FrameTimingManager.GetLatestTimings(1,ft)>0?ft[0].frameStartTimestamp:0;
            for(int i=0;i<490;i++){content.SetSample(i%49);FrameTimingManager.CaptureFrameTimings();yield return null;if(i<8)continue;if(FrameTimingManager.GetLatestTimings(1,ft)>0&&ft[0].frameStartTimestamp>start&&seen.Add(ft[0].frameStartTimestamp)){if(Valid(ft[0].gpuFrameTime))gpu.Add(ft[0].gpuFrameTime);else zero++;if(Valid(ft[0].cpuFrameTime))cpu.Add(ft[0].cpuFrameTime);}else missing++;}
            File.WriteAllText(Path.Combine(folder,"present_probe.json"),JsonUtility.ToJson(new PresentReport{format=format,frameTimingFeatureEnabled=FrameTimingManager.IsFeatureEnabled(),cameraEnabled=camera.enabled,targetTextureNull=camera.targetTexture==null,gpu=Stats(gpu),cpu=Stats(cpu),zeroGpu=zero,missing=missing,method="通常PlayerLoopの有効Camera・targetTexture null・近景窓。非表示で起動したWindows process。実displayのpresent/HMDは未確認。離屏6-runとは別の診断。"},true));
        }
        [Serializable]public class PresentReport{public string format,method;public bool frameTimingFeatureEnabled,cameraEnabled,targetTextureNull,hmdVerified;public Distribution gpu,cpu;public int zeroGpu,missing;}
        static bool Valid(double value)=>value>0&&!double.IsNaN(value)&&!double.IsInfinity(value);
        static string Arg(string[]args,string key,string fallback){int i=Array.IndexOf(args,key);return i>=0&&i+1<args.Length?args[i+1]:fallback;}
        static string[]FluidTextureNames()=>Resources.FindObjectsOfTypeAll<Texture2D>().Where(t=>t.name.StartsWith("fluid17_")).Select(t=>t.name).OrderBy(s=>s).ToArray();
        static void Render(Decision20Content content,RenderTexture[]targets,int views){var camera=content.testCamera;Vector3 position=content.cameraMode==1?new Vector3(4,3,-5):CameraPosition;Vector3 target=CameraTarget;if(content.cameraMode==2){var b=content.captureBounds[content.currentSample];target=b.center;position=target+new Vector3(.58f,.5f,-.72f).normalized*Mathf.Max(2.7f,b.size.magnitude*1.25f);}camera.transform.position=position;camera.transform.LookAt(target);var right=camera.transform.right;for(int eye=0;eye<views;eye++){camera.transform.position=position+(views==2?right*(eye==0?-.032f:.032f):Vector3.zero);camera.targetTexture=targets[eye];camera.Render();}}
        static Texture2D Read(RenderTexture target){RenderTexture.active=target;var t=new Texture2D(target.width,target.height,TextureFormat.RGB24,false);t.ReadPixels(new Rect(0,0,target.width,target.height),0,0);t.Apply();RenderTexture.active=null;return t;}
        static void Save(RenderTexture rt,string path){var t=Read(rt);File.WriteAllBytes(path,t.EncodeToPNG());Destroy(t);}
        Camera Overlay(RenderTexture target,string format,out TextMesh label){var overlay=new GameObject("20 計測外の記録注記").AddComponent<Camera>();overlay.transform.position=Vector3.one*2000;overlay.orthographic=true;overlay.orthographicSize=360;overlay.aspect=1280f/720;overlay.nearClipPlane=.1f;overlay.farClipPlane=20;overlay.clearFlags=CameraClearFlags.Depth;overlay.cullingMask=1<<31;overlay.enabled=false;overlay.targetTexture=target;var panel=GameObject.CreatePrimitive(PrimitiveType.Cube);panel.layer=31;panel.transform.SetParent(overlay.transform,false);panel.transform.localPosition=new Vector3(0,-308,8);panel.transform.localScale=new Vector3(1280,104,.1f);panel.GetComponent<Renderer>().sharedMaterial=captionMaterial;var font=Font.CreateDynamicFontFromOSFont(new[]{"Yu Gothic","Meiryo","Microsoft YaHei UI"},32);Label(overlay,font,"20 "+(format=="vat"?"Fluid VAT":"Alembic")+" / 計測外の近景追従・同じ19の色/深度/影",-266,22);label=Label(overlay,font,"記録",-298,18);Label(overlay,font,"実Windowsのオフスクリーン描画 / 動画24fpsは性能値ではない / 元試料の面化誤差・流出を含む",-329,16);return overlay;}
        static TextMesh Label(Camera c,Font f,string value,float y,float size){var g=new GameObject("20 日本語注記");g.layer=31;g.transform.SetParent(c.transform,false);g.transform.localPosition=new Vector3(-610,y,7);var t=g.AddComponent<TextMesh>();t.font=f;t.fontSize=32;t.characterSize=1;t.anchor=TextAnchor.UpperLeft;t.color=new Color(.97f,.95f,.88f);t.text=value;var r=g.GetComponent<MeshRenderer>();r.sharedMaterial=f.material;g.transform.localScale=Vector3.one*(size/Mathf.Max(.001f,r.bounds.size.y));return t;}
        static Distribution Stats(List<double>v){v.Sort();return new Distribution{available=v.Count>0,count=v.Count,p50=v.Count>0?v[(int)((v.Count-1)*.5)]:0,p95=v.Count>0?v[(int)((v.Count-1)*.95)]:0,p99=v.Count>0?v[(int)((v.Count-1)*.99)]:0,maximum=v.Count>0?v.Last():0};}
        [DllImport("kernel32.dll")]static extern IntPtr GetCurrentProcess();[DllImport("psapi.dll",SetLastError=true)]static extern bool GetProcessMemoryInfo(IntPtr process,out Counters counters,uint size);
        [StructLayout(LayoutKind.Sequential)]struct Counters{public uint cb,pageFaultCount;public UIntPtr peakWorkingSet,workingSet,quotaPeakPagedPool,quotaPagedPool,quotaPeakNonPagedPool,quotaNonPagedPool,pagefile,peakPagefile,privateUsage;}
        static MemoryInfo Memory(){var size=(uint)Marshal.SizeOf(typeof(Counters));bool ok=GetProcessMemoryInfo(GetCurrentProcess(),out var c,size);return new MemoryInfo{nativeAvailable=ok,workingSet=ok?(long)c.workingSet.ToUInt64():0,peakWorkingSetSinceProcess=ok?(long)c.peakWorkingSet.ToUInt64():0,privateBytes=ok?(long)c.privateUsage.ToUInt64():0,unityAllocated=Profiler.GetTotalAllocatedMemoryLong(),unityReserved=Profiler.GetTotalReservedMemoryLong(),managedUsed=Profiler.GetMonoUsedSizeLong()};}
        [Serializable]public class Report{public string unity,format,startedUtc,finishedUtc,gpu,cpu,api,method;public int run,firstImageColors,firstFluidPixels,capturedFrames;public bool frameTimingFeatureEnabled,assetIsolationPassed,passed,hmdVerified;public double sceneLoadMilliseconds,initializeMilliseconds,firstRenderCpuMilliseconds,firstReadbackMilliseconds;public string[]beforeFluidTextures,afterFluidTextures;public MemoryInfo beforeLoad,afterLoad,afterFirstVisible,afterMeasurement;public TextureInfo[]textures;public Timing[]timings;}
        [Serializable]public class MemoryInfo{public bool nativeAvailable;public long workingSet,peakWorkingSetSinceProcess,privateBytes,unityAllocated,unityReserved,managedUsed;}
        [Serializable]public class TextureInfo{public string name,format,graphicsFormat;public int width,height,mips;public long runtimeBytes;}
        [Serializable]public class Timing{public string cameraMode;public int views,widthPerView,heightPerView,samples,warmup,frameTimingSkippedHead,frameTimingGpuZero,frameTimingGpuMissingOrDuplicate,frameTimingGpuInvalid;public Distribution cpuUpdate,cpuSubmission,frameInterval,frameTimingCpu,frameTimingGpu,frameTimingMainThread,frameTimingRenderThread;public MemoryInfo[]memorySnapshots;public FrameRecord[]raw;}
        [Serializable]public class FrameRecord{public int ordinal,cpuSample;public double updateMs,submissionMs,intervalMs,cpuMs,gpuMs;public ulong timestamp;}
        [Serializable]public class Distribution{public bool available;public int count;public double p50,p95,p99,maximum;}
    }
}
