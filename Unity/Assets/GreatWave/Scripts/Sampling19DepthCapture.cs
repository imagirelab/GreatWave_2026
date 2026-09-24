using UnityEngine;

namespace GreatWave
{
    // カメラ描画中の深度と投影定数を使用し、描画後は所有RTだけを読む。
    [RequireComponent(typeof(Camera))]
    public sealed class Sampling19DepthCapture:MonoBehaviour
    {
        public RenderTexture eyeDepth,rawDepth,visualDepth;
        public int callbackCount;
        public Vector4 zBufferParams;
        Material eyeMaterial,rawMaterial,visualMaterial;
        public void Configure(Material source,int width,int height)
        {
            eyeMaterial=new Material(source);eyeMaterial.SetInteger("_DepthMode",1);
            rawMaterial=new Material(source);rawMaterial.SetInteger("_DepthMode",2);
            visualMaterial=new Material(source);visualMaterial.SetInteger("_DepthMode",0);
            var camera=GetComponent<Camera>();visualMaterial.SetVector("_DepthRange",new Vector4(camera.nearClipPlane,camera.farClipPlane,0,0));
            eyeDepth=NewTarget(width,height);rawDepth=NewTarget(width,height);visualDepth=NewTarget(width,height);
        }
        static RenderTexture NewTarget(int width,int height){var value=new RenderTexture(width,height,0,RenderTextureFormat.ARGBFloat,RenderTextureReadWrite.Linear);value.Create();return value;}
        void OnRenderImage(RenderTexture source,RenderTexture destination)
        {
            if(eyeMaterial!=null)
            {
                callbackCount++;zBufferParams=Shader.GetGlobalVector("_ZBufferParams");
                Graphics.Blit(source,rawDepth,rawMaterial);Graphics.Blit(source,eyeDepth,eyeMaterial);Graphics.Blit(source,visualDepth,visualMaterial);
            }
            Graphics.Blit(source,destination);
        }
        void OnDestroy(){foreach(var t in new[]{eyeDepth,rawDepth,visualDepth})if(t!=null){t.Release();Destroy(t);}foreach(var m in new[]{eyeMaterial,rawMaterial,visualMaterial})if(m!=null)Destroy(m);}
    }
}
