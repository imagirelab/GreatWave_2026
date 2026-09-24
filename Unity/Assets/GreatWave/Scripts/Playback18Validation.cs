using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using UnityEngine;
using UnityEngine.Formats.Alembic.Importer;

namespace GreatWave
{
    public static class Playback18Validation
    {
        public const float PositionTolerance=.0001f;
        const float Cell=.0001f;
        static bool Finite(Vector3 v)=>!(float.IsNaN(v.x)||float.IsNaN(v.y)||float.IsNaN(v.z)||float.IsInfinity(v.x)||float.IsInfinity(v.y)||float.IsInfinity(v.z));
        static Vector3Int Key(Vector3 p)=>new Vector3Int(Mathf.FloorToInt(p.x/Cell),Mathf.FloorToInt(p.y/Cell),Mathf.FloorToInt(p.z/Cell));
        static string Triangle(int a,int b,int c)
        {if(a<=b&&a<=c)return a+":"+b+":"+c;if(b<=a&&b<=c)return b+":"+c+":"+a;return c+":"+a+":"+b;}
        public static void RefreshBounds(AlembicStreamPlayer stream)
        {foreach(var f in stream.GetComponentsInChildren<MeshFilter>())if(f.sharedMesh!=null)f.sharedMesh.RecalculateBounds();}
        public static Result Alembic(AlembicStreamPlayer stream,Playback18Reference reference)
        {
            var result=new Result{unity=Application.unityVersion,utc=DateTime.UtcNow.ToString("O"),format="Alembic2.4.4",mapping="Houdini(x,y,z) → Unity(-x,y,z), scale1",positionTolerance=PositionTolerance,normalToleranceDegrees=.5f,
                mediaStart=stream.MediaStartTime,mediaEnd=stream.MediaEndTime,duration=stream.Duration,interpolation=stream.Settings.InterpolateSamples};
            result.settingsMatch=stream.Settings.SwapHandedness&&!stream.Settings.InterpolateSamples&&Math.Abs(stream.Settings.ScaleFactor-1)<1e-6;
            result.timeMatches=Math.Abs(stream.MediaStartTime-1f/24)<1e-5&&Math.Abs(stream.Duration-2)<1e-5;
            var records=new List<Measurement>();
            for(int k=0;k<reference.samples.Length;k++)
            {
                stream.UpdateImmediately(reference.samples[k].time);RefreshBounds(stream);
                var filters=stream.GetComponentsInChildren<MeshFilter>().Where(f=>f.sharedMesh!=null).ToArray();
                records.Add(Compare(reference.samples[k],filters.Select(f=>f.sharedMesh.vertices.Select(v=>f.transform.TransformPoint(v)).ToArray()).ToArray(),
                    filters.Select(f=>f.sharedMesh.normals.Select(v=>f.transform.TransformDirection(v)).ToArray()).ToArray(),filters.Select(f=>f.sharedMesh.triangles).ToArray(),k));
                // AABBの中心/半径のfloat往復による境界丸めも測り、座標と同じ0.1mm許容内か確認する。
                records.Last().maximumBoundsOutside=filters.SelectMany(f=>f.sharedMesh.vertices.Select(v=>Mathf.Sqrt(f.sharedMesh.bounds.SqrDistance(v)))).Max();
                records.Last().boundsEncloseImportedVertices=records.Last().maximumBoundsOutside<PositionTolerance;
                records.Last().passed&=records.Last().boundsEncloseImportedVertices;
            }
            result.samples=records.ToArray();result.passed=result.settingsMatch&&result.timeMatches&&records.Count==49&&records.All(x=>x.passed);
            stream.UpdateImmediately(0);RefreshBounds(stream);return result;
        }
        public static Measurement Compare(Playback18Reference.Sample source,Vector3[][]positionSets,Vector3[][]normalSets,int[][]indexSets,int sample)
        {
            if(positionSets.Length!=normalSets.Length||positionSets.Length!=indexSets.Length)throw new InvalidOperationException("読込形状の組が一致しません。");
            var cells=new Dictionary<Vector3Int,List<int>>();
            for(int i=0;i<source.positions.Length;i++)
            {var key=Key(source.positions[i]);if(!cells.TryGetValue(key,out var values)){values=new List<int>();cells.Add(key,values);}values.Add(i);}
            var expected=new Dictionary<string,int>();
            for(int i=0;i<source.triangles.Length;i+=3)
            {var key=Triangle(source.triangles[i],source.triangles[i+1],source.triangles[i+2]);if(!expected.ContainsKey(key))expected.Add(key,0);expected[key]++;}
            var actual=new Dictionary<string,int>();var used=new HashSet<int>();
            var r=new Measurement{sample=sample,time=source.time,sourcePoints=source.positions.Length,sourceTriangles=source.triangles.Length/3,finite=true,normalsFiniteAndUnit=true,indicesValid=true,minimumFaceNormalDot=1};
            double squared=0;bool initialized=false;Bounds bounds=new Bounds();
            for(int set=0;set<positionSets.Length;set++)
            {
                var positions=positionSets[set];var normals=normalSets[set];var triangles=indexSets[set];
                if(normals.Length!=positions.Length)throw new InvalidOperationException("法線数が頂点数と一致しません。");
                var mapping=new int[positions.Length];
                for(int i=0;i<positions.Length;i++)
                {
                    var p=positions[i];r.finite&=Finite(p);r.normalsFiniteAndUnit&=Finite(normals[i])&&Math.Abs(normals[i].magnitude-1)<.01f;
                    int best=-1;float distance=float.MaxValue;var cell=Key(p);
                    for(int x=-1;x<=1;x++)for(int y=-1;y<=1;y++)for(int z=-1;z<=1;z++)
                    if(cells.TryGetValue(cell+new Vector3Int(x,y,z),out var candidates))foreach(int j in candidates)
                    {float d=(p-source.positions[j]).sqrMagnitude;if(d<distance){distance=d;best=j;}}
                    if(best<0)throw new InvalidOperationException("元面に一致しない読込頂点があります。sample="+sample+" P="+p);
                    mapping[i]=best;used.Add(best);float error=Mathf.Sqrt(distance);squared+=distance;r.maximumPositionError=Mathf.Max(r.maximumPositionError,error);
                    r.maximumNormalAngle=Mathf.Max(r.maximumNormalAngle,Vector3.Angle(normals[i],source.normals[best]));
                    if(!initialized){bounds=new Bounds(p,Vector3.zero);initialized=true;}else bounds.Encapsulate(p);
                }
                r.importedPoints+=positions.Length;r.importedTriangles+=triangles.Length/3;
                for(int i=0;i<triangles.Length;i+=3)
                {
                    int a=triangles[i],b=triangles[i+1],c=triangles[i+2];
                    if(a<0||b<0||c<0||a>=positions.Length||b>=positions.Length||c>=positions.Length){r.indicesValid=false;continue;}
                    var key=Triangle(mapping[a],mapping[b],mapping[c]);if(!actual.ContainsKey(key))actual.Add(key,0);actual[key]++;
                    var cross=Vector3.Cross(positions[b]-positions[a],positions[c]-positions[a]);var normal=normals[a]+normals[b]+normals[c];
                    r.minimumFaceNormalDot=Mathf.Min(r.minimumFaceNormalDot,Vector3.Dot(cross.normalized,normal.normalized));
                }
            }
            var expectedBounds=new Bounds(source.positions[0],Vector3.zero);foreach(var p in source.positions)expectedBounds.Encapsulate(p);
            r.minimumBounds=bounds.min;r.maximumBounds=bounds.max;r.boundsError=Mathf.Max(Vector3.Distance(bounds.min,expectedBounds.min),Vector3.Distance(bounds.max,expectedBounds.max));
            r.rmsPositionError=(float)Math.Sqrt(squared/Math.Max(1,r.importedPoints));r.coveredSourcePoints=used.Count;
            r.orientedConnectivityMatches=actual.Count==expected.Count&&expected.All(pair=>actual.TryGetValue(pair.Key,out int n)&&n==pair.Value)&&r.importedTriangles==r.sourceTriangles;
            r.passed=r.finite&&r.normalsFiniteAndUnit&&r.indicesValid&&r.coveredSourcePoints==r.sourcePoints&&r.maximumPositionError<PositionTolerance&&r.maximumNormalAngle<=.5f&&r.boundsError<PositionTolerance&&r.orientedConnectivityMatches;
            return r;
        }
        public static Timing BenchmarkAlembic(AlembicStreamPlayer stream,int repeats=3)
        {
            for(int k=0;k<49;k++)stream.UpdateImmediately(k/24f);
            var times=new List<double>();var stopwatch=new Stopwatch();
            for(int n=0;n<repeats;n++)for(int k=0;k<49;k++)
            {stopwatch.Restart();stream.UpdateImmediately(k/24f);RefreshBounds(stream);stopwatch.Stop();times.Add(stopwatch.Elapsed.TotalMilliseconds);}
            times.Sort();return new Timing{method="1回warm-up後、全49時刻×3回のUpdateImmediately+実頂点AABB更新。CPU同期処理のみ、GPU/フレーム全体ではない。",samples=times.Count,medianMilliseconds=times[times.Count/2],p95Milliseconds=times[(int)(times.Count*.95)],maximumMilliseconds=times.Last()};
        }
        [Serializable]public class Result{public string unity,utc,format,mapping;public float positionTolerance,normalToleranceDegrees,mediaStart,mediaEnd,duration;public bool settingsMatch,timeMatches,interpolation,passed;public Measurement[]samples;}
        [Serializable]public class Measurement{public int sample,sourcePoints,importedPoints,coveredSourcePoints,sourceTriangles,importedTriangles;public float time,maximumPositionError,rmsPositionError,maximumNormalAngle,minimumFaceNormalDot,boundsError,maximumBoundsOutside;public bool finite,normalsFiniteAndUnit,indicesValid,orientedConnectivityMatches,boundsEncloseImportedVertices,passed;public Vector3 minimumBounds,maximumBounds;}
        [Serializable]public class Timing{public string method;public int samples;public double medianMilliseconds,p95Milliseconds,maximumMilliseconds;}
    }
}
