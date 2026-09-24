using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Formats.Alembic.Importer;

namespace GreatWave
{
    // 参照値はHoudiniから書き出されたものだけを使う。解析式は実装しない。
    public static class FixedTopology16Validation
    {
        const float Tolerance=.0001f;
        public static void RefreshBounds(AlembicStreamPlayer stream)
        {foreach(var f in stream.GetComponentsInChildren<MeshFilter>())if(f.sharedMesh!=null)f.sharedMesh.RecalculateBounds();}
        public static Result Measure(AlembicStreamPlayer stream, FixedTopology16Reference reference)
        {
            if(reference.samples==null||reference.samples.Length<2) throw new InvalidOperationException("Houdini参照サンプルが不足しています。");
            var first=reference.samples[0];
            var lookup=new Dictionary<string,int>();
            for(int i=0;i<first.positions.Length;i++) lookup.Add(Key(Convert(first.positions[i])),i);
            var grid=stream.GetComponentsInChildren<MeshFilter>().Where(f=>AncestorNamed(f.transform,reference.grid_object_name,stream.transform)).ToArray();
            if(grid.Length==0) throw new InvalidOperationException("Alembic内の格子が見つかりません: "+reference.grid_object_name);
            var expectedTriangles=new HashSet<string>();
            for(int i=0;i<reference.triangles.Length;i+=3) expectedTriangles.Add(Triangle(reference.triangles[i],reference.triangles[i+1],reference.triangles[i+2]));
            var result=new Result {unity=Application.unityVersion,utc=DateTime.UtcNow.ToString("O"),mapping="Houdini(x,y,z) → Unity(-x,y,z), scale 1",
                mediaStart=stream.MediaStartTime,mediaEnd=stream.MediaEndTime,relativeDuration=stream.Duration,sourceStart=first.time_seconds,
                sourceEnd=reference.samples.Last().time_seconds,positionTolerance=Tolerance,normalToleranceDegrees=.2f,
                importedScale=stream.Settings.ScaleFactor,swapHandedness=stream.Settings.SwapHandedness,interpolation=stream.Settings.InterpolateSamples};
            var samples=new List<Measurement>();
            for(int i=0;i<reference.samples.Length;i++)
            {
                var sample=reference.samples[i];
                if(sample.normals==null||sample.normals.Length!=sample.positions.Length)throw new InvalidOperationException("参照法線の個数が頂点と一致しません。");
                samples.Add(At(stream,grid,lookup,expectedTriangles,reference,sample.positions,sample.normals,sample.time_seconds-first.time_seconds,false));
                if(i+1<reference.samples.Length)
                {
                    var next=reference.samples[i+1];
                    // 固定トポロジーの補間期待値は、隣接する実書出し座標の線形補間。
                    var mid=sample.positions.Select((p,j)=>Vector3.Lerp(p,next.positions[j],.5f)).ToArray();
                    samples.Add(At(stream,grid,lookup,expectedTriangles,reference,mid,null,(sample.time_seconds+next.time_seconds)*.5f-first.time_seconds,true));
                }
            }
            result.measurements=samples.ToArray();
            result.allSourceSamplesMeasured=reference.samples.Length==61&&samples.Count(m=>!m.interpolated)==61;
            result.timelineMatches=Mathf.Abs(result.relativeDuration-(result.sourceEnd-result.sourceStart))<.00001f&&Mathf.Abs(result.relativeDuration-2)<.00001f;
            result.settingsMatch=Mathf.Abs(result.importedScale-1)<.00001f&&result.swapHandedness&&result.interpolation;
            result.passed=result.allSourceSamplesMeasured&&result.timelineMatches&&result.settingsMatch&&samples.All(m=>m.passed);
            stream.UpdateImmediately(0);
            return result;
        }
        static Measurement At(AlembicStreamPlayer stream,MeshFilter[] filters,Dictionary<string,int> lookup,HashSet<string> expectedTriangles,
            FixedTopology16Reference reference,Vector3[] positions,Vector3[] normals,float time,bool interpolated)
        {
            stream.UpdateImmediately(time);
            var used=new HashSet<int>();var actualTriangles=new HashSet<string>();
            var measurement=new Measurement{time=time,interpolated=interpolated,sourceVertices=positions.Length,finite=true,minimumFaceNormalDot=1,minimumNormalY=1,normalsFiniteAndUnit=true};
            Bounds actualBounds=new Bounds(); bool initialized=false;
            foreach(var filter in filters)
            {
                var mesh=filter.sharedMesh;
                if(mesh==null) throw new InvalidOperationException("Alembicの格子メッシュが未生成です。");
                var vertices=mesh.vertices;var meshNormals=mesh.normals;var indices=new int[vertices.Length];
                if(meshNormals.Length!=vertices.Length)throw new InvalidOperationException("Alembic法線が不足しています。");
                for(int i=0;i<vertices.Length;i++)
                {
                    var actual=filter.transform.TransformPoint(vertices[i]);
                    measurement.finite&=Finite(actual);
                    if(!lookup.TryGetValue(Key(actual),out int source)) throw new InvalidOperationException("書出し格子と一致しないXZ座標: "+actual);
                    indices[i]=source;used.Add(source);
                    measurement.maxPositionError=Mathf.Max(measurement.maxPositionError,Vector3.Distance(actual,Convert(positions[source])));
                    measurement.normalsFiniteAndUnit&=Finite(meshNormals[i])&&Mathf.Abs(meshNormals[i].magnitude-1)<.01f;
                    measurement.minimumNormalY=Mathf.Min(measurement.minimumNormalY,filter.transform.TransformDirection(meshNormals[i]).y);
                    if(normals!=null&&normals.Length==positions.Length)
                    {
                        measurement.normalsFiniteAndUnit&=Finite(normals[source])&&Mathf.Abs(normals[source].magnitude-1)<.01f;
                        var actualNormal=filter.transform.TransformDirection(meshNormals[i]).normalized;
                        measurement.maxNormalAngle=Mathf.Max(measurement.maxNormalAngle,Vector3.Angle(actualNormal,Convert(normals[source]).normalized));
                    }
                    if(!initialized){actualBounds=new Bounds(actual,Vector3.zero);initialized=true;}else actualBounds.Encapsulate(actual);
                }
                var triangles=mesh.triangles;
                measurement.rawTriangleCount+=triangles.Length/3;
                for(int i=0;i<triangles.Length;i+=3)
                {
                    int a=triangles[i],b=triangles[i+1],c=triangles[i+2];
                    actualTriangles.Add(Triangle(indices[a],indices[b],indices[c]));
                    var face=Vector3.Cross(vertices[b]-vertices[a],vertices[c]-vertices[a]).normalized;
                    var smooth=(meshNormals[a]+meshNormals[b]+meshNormals[c]).normalized;
                    measurement.minimumFaceNormalDot=Mathf.Min(measurement.minimumFaceNormalDot,Vector3.Dot(face,smooth));
                }
                measurement.importedVertices+=vertices.Length;
            }
            measurement.uniqueSourceVertices=used.Count;
            measurement.triangleCount=actualTriangles.Count;
            measurement.connectivityMatches=actualTriangles.SetEquals(expectedTriangles)&&measurement.rawTriangleCount==reference.triangles.Length/3;
            measurement.actualBoundsMin=actualBounds.min;measurement.actualBoundsMax=actualBounds.max;
            measurement.horizontalSizeMatches=Mathf.Abs(actualBounds.size.x-8)<Tolerance&&Mathf.Abs(actualBounds.size.z-8)<Tolerance;
            var markers=new List<MarkerMeasurement>();
            foreach(var marker in reference.markers)
            {
                var markerFilters=stream.GetComponentsInChildren<MeshFilter>().Where(r=>AncestorNamed(r.transform,marker.name,stream.transform)).ToArray();
                if(markerFilters.Length==0) throw new InvalidOperationException("Alembicの非対称マーカーが見つかりません: "+marker.name);
                var world=markerFilters.SelectMany(f=>f.sharedMesh.vertices.Select(v=>f.transform.TransformPoint(v))).ToArray();
                measurement.finite&=world.All(Finite);
                var bounds=new Bounds(world[0],Vector3.zero);foreach(var v in world.Skip(1))bounds.Encapsulate(v);
                var renderer=markerFilters[0].GetComponent<MeshRenderer>();
                var measured=new MarkerMeasurement{name=marker.name,expectedCenter=Convert(marker.center),actualCenter=bounds.center,expectedSize=marker.size,actualSize=bounds.size,
                    nativeRendererBoundsMin=renderer.bounds.min,nativeRendererBoundsMax=renderer.bounds.max,normalsOutward=true};
                foreach(var f in markerFilters)
                {
                    var vertices=f.sharedMesh.vertices;var markerNormals=f.sharedMesh.normals;
                    if(markerNormals.Length!=vertices.Length)throw new InvalidOperationException("マーカー法線が不足しています。");
                    for(int i=0;i<vertices.Length;i++)
                    {
                        var n=f.transform.TransformDirection(markerNormals[i]);var radial=f.transform.TransformPoint(vertices[i])-measured.expectedCenter;
                        measured.normalsOutward&=Finite(n)&&Mathf.Abs(n.magnitude-1)<.01f&&Vector3.Dot(n,radial)>0;
                    }
                    f.sharedMesh.RecalculateBounds();
                }
                measured.refreshedBoundsMin=renderer.bounds.min;measured.refreshedBoundsMax=renderer.bounds.max;
                measured.renderBoundsMatch=Vector3.Distance(measured.refreshedBoundsMin,bounds.min)<Tolerance&&Vector3.Distance(measured.refreshedBoundsMax,bounds.max)<Tolerance;
                measured.positionError=Vector3.Distance(measured.expectedCenter,measured.actualCenter);measured.sizeError=Vector3.Distance(measured.expectedSize,measured.actualSize);
                measured.passed=measured.positionError<Tolerance&&measured.sizeError<Tolerance&&measured.normalsOutward&&measured.renderBoundsMatch;markers.Add(measured);
            }
            measurement.markers=markers.ToArray();
            measurement.normalsChecked=normals!=null;
            measurement.passed=measurement.finite&&measurement.normalsFiniteAndUnit&&measurement.minimumNormalY>.9f&&used.Count==positions.Length&&measurement.maxPositionError<Tolerance&&measurement.maxNormalAngle<=.2f&&measurement.minimumFaceNormalDot>.99f&&measurement.connectivityMatches&&measurement.horizontalSizeMatches&&markers.Count>=3&&markers.All(m=>m.passed);
            return measurement;
        }
        static bool AncestorNamed(Transform transform,string name,Transform root){for(var t=transform;t!=null;t=t.parent){if(t.name==name)return true;if(t==root)break;}return false;}
        static string Key(Vector3 value)=>Mathf.RoundToInt(value.x*10000)+":"+Mathf.RoundToInt(value.z*10000);
        static string Triangle(int a,int b,int c){var v=new[]{a,b,c};Array.Sort(v);return v[0]+":"+v[1]+":"+v[2];}
        static bool Finite(Vector3 v)=>!(float.IsNaN(v.x)||float.IsNaN(v.y)||float.IsNaN(v.z)||float.IsInfinity(v.x)||float.IsInfinity(v.y)||float.IsInfinity(v.z));
        public static Vector3 Convert(Vector3 v)=>new Vector3(-v.x,v.y,v.z);
        [Serializable] public class Result{public string unity,utc,mapping;public float mediaStart,mediaEnd,relativeDuration,sourceStart,sourceEnd,positionTolerance,normalToleranceDegrees,importedScale;public bool swapHandedness,interpolation,allSourceSamplesMeasured,timelineMatches,settingsMatch,passed;public Measurement[] measurements;}
        [Serializable] public class Measurement{public float time,maxPositionError,maxNormalAngle,minimumFaceNormalDot,minimumNormalY;public int sourceVertices,importedVertices,uniqueSourceVertices,triangleCount,rawTriangleCount;public bool interpolated,finite,normalsFiniteAndUnit,connectivityMatches,horizontalSizeMatches,normalsChecked,passed;public Vector3 actualBoundsMin,actualBoundsMax;public MarkerMeasurement[] markers;}
        [Serializable] public class MarkerMeasurement{public string name;public Vector3 expectedCenter,actualCenter,expectedSize,actualSize,nativeRendererBoundsMin,nativeRendererBoundsMax,refreshedBoundsMin,refreshedBoundsMax;public float positionError,sizeError;public bool normalsOutward,renderBoundsMatch,passed;}
    }
}
