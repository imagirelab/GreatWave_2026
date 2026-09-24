using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using GreatWave.Playback18;

namespace GreatWave
{
    public static class Playback18VATValidation
    {
        public static Result Measure(GameObject root,Playback18VAT.Data data,ComputeShader decoder,Playback18Reference reference)
        {
            Playback18VAT.Validate(data);
            var filters=root.GetComponentsInChildren<MeshFilter>(true);
            var result=new Result{unity=Application.unityVersion,utc=DateTime.UtcNow.ToString("O"),method="実FBXのUV0と実EXRを描画と共通のGPUデコーダーで復号し同期readback。検査時間は再生負荷に加えない。",sampleCount=data.frameCount,cpuLayout=Playback18VAT.GetLayoutDiagnostics(data)};
            var records=new List<Sample>();
            for(int k=0;k<49;k++)
            {
                var setsP=new List<Vector3[]>();var setsN=new List<Vector3[]>();var setsT=new List<int[]>();var record=new Sample{sample=k,time=k/24f,gpuStatusValid=true};
                foreach(var filter in filters)
                {
                    var mesh=filter.sharedMesh;var decoded=Playback18VAT.ReadGpu(decoder,data,mesh.uv,k);var triangles=mesh.triangles;
                    var p=new List<Vector3>();var n=new List<Vector3>();var t=new List<int>();var mapping=new Dictionary<int,int>();
                    int Map(int original)
                    {
                        if(mapping.TryGetValue(original,out int id))return id;
                        id=p.Count;mapping.Add(original,id);var d=decoded[original];p.Add(filter.transform.TransformPoint(d.position));n.Add(filter.transform.TransformDirection(d.normal));
                        record.maximumRendererBoundsOutside=Mathf.Max(record.maximumRendererBoundsOutside,Mathf.Sqrt(filter.GetComponent<Renderer>().localBounds.SqrDistance((Vector3)d.position)));record.gpuLayout=d.layout;record.gpuStatusValid&=d.status.x>.5f&&Mathf.Abs(d.layout.z-result.cpuLayout.activeX)<1e-6f&&Mathf.Abs(d.layout.w-result.cpuLayout.activeY)<1e-6f;record.maximumQuaternionLengthError=Mathf.Max(record.maximumQuaternionLengthError,Mathf.Abs(d.status.w-1));return id;
                    }
                    for(int i=0;i<triangles.Length;i+=3)
                    {
                        int a=triangles[i],b=triangles[i+1],c=triangles[i+2];
                        Vector3 pa=decoded[a].position,pb=decoded[b].position,pc=decoded[c].position;
                        // 公式VATの未使用三角形は同一点へ縮退する。面積ゼロだけを別計上し、実面は全件比較する。
                        if(pa.Equals(pb)&&pa.Equals(pc)){record.collapsedPaddingTriangles++;continue;}
                        t.Add(Map(a));t.Add(Map(b));t.Add(Map(c));
                    }
                    setsP.Add(p.ToArray());setsN.Add(n.ToArray());setsT.Add(t.ToArray());record.fbxVertices+=mesh.vertexCount;record.fbxTriangles+=triangles.Length/3;
                }
                record.geometry=Playback18Validation.Compare(reference.samples[k],setsP.ToArray(),setsN.ToArray(),setsT.ToArray(),k);
                record.geometry.maximumBoundsOutside=record.maximumRendererBoundsOutside;record.geometry.boundsEncloseImportedVertices=record.maximumRendererBoundsOutside<Playback18Validation.PositionTolerance;record.geometry.passed&=record.geometry.boundsEncloseImportedVertices;
                record.passed=record.gpuStatusValid&&record.geometry.passed&&record.maximumQuaternionLengthError<.001f;records.Add(record);
            }
            result.samples=records.ToArray();result.passed=result.sampleCount==49&&records.All(r=>r.passed);return result;
        }
        [Serializable]public class Result{public string unity,utc,method;public int sampleCount;public bool passed;public Sample[]samples;public Playback18VATLayout.Diagnostics cpuLayout;}
        [Serializable]public class Sample{public int sample,fbxVertices,fbxTriangles,collapsedPaddingTriangles;public float time,maximumQuaternionLengthError,maximumRendererBoundsOutside;public bool gpuStatusValid,passed;public Playback18Validation.Measurement geometry;public Vector4 gpuLayout;}
    }
}


