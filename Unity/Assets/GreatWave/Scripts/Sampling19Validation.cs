using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace GreatWave
{
    public static class Sampling19Validation
    {
        public static Report Measure(Sampling19Player player,Sampling19Reference source)
        {
            var report=new Report{unity=Application.unityVersion,utc=DateTime.UtcNow.ToString("O"),method="新規60Hz実FLIPと同master偶数30Hz。各実AlembicのP/N/有向三角形接続を対応させ、別時刻の頂点番号は使わない。"};var rows=new List<Record>();
            foreach(int rate in new[]{30,60})for(int k=0;k<=120;k+=60/rate)
            {
                var stream=player.SetSample(k,rate);var filters=stream.GetComponentsInChildren<MeshFilter>().Where(f=>f.sharedMesh!=null).ToArray();
                var result=Playback18Validation.Compare(source.samples[k],filters.Select(f=>f.sharedMesh.vertices.Select(p=>f.transform.TransformPoint(p)).ToArray()).ToArray(),filters.Select(f=>f.sharedMesh.normals.Select(n=>f.transform.TransformDirection(n)).ToArray()).ToArray(),filters.Select(f=>f.sharedMesh.triangles).ToArray(),k);
                result.maximumBoundsOutside=filters.SelectMany(f=>f.sharedMesh.vertices.Select(v=>Mathf.Sqrt(f.sharedMesh.bounds.SqrDistance(v)))).Max();result.boundsEncloseImportedVertices=result.maximumBoundsOutside<Playback18Validation.PositionTolerance;result.passed&=result.boundsEncloseImportedVertices;
                int start=rate==30?0:Math.Min(2,k/40)*40;
                var r=new Record{rate=rate,masterSample=k,seconds=k/60f,archiveStart=stream.MediaStartTime,archiveEnd=stream.MediaEndTime,geometry=result};
                r.timeSettingsMatch=Math.Abs(stream.MediaStartTime-(start/60f+1f/24))<.00001&&stream.Settings.SwapHandedness&&!stream.Settings.InterpolateSamples&&Math.Abs(stream.Settings.ScaleFactor-1)<1e-6;r.passed=result.passed&&r.timeSettingsMatch;rows.Add(r);
            }
            // 分割境界は次segmentだけでなく前segmentの終端も同じ参照へ照合する。
            var seams=new List<Playback18Validation.Measurement>();
            for(int part=0;part<2;part++)
            {
                int k=(part+1)*40;player.HideSampling();var stream=player.streams60[part];stream.gameObject.SetActive(true);stream.UpdateImmediately(40f/60);Playback18Validation.RefreshBounds(stream);
                var filters=stream.GetComponentsInChildren<MeshFilter>().Where(f=>f.sharedMesh!=null).ToArray();
                seams.Add(Playback18Validation.Compare(source.samples[k],filters.Select(f=>f.sharedMesh.vertices.Select(p=>f.transform.TransformPoint(p)).ToArray()).ToArray(),filters.Select(f=>f.sharedMesh.normals.Select(n=>f.transform.TransformDirection(n)).ToArray()).ToArray(),filters.Select(f=>f.sharedMesh.triangles).ToArray(),k));
            }
            report.records=rows.ToArray();report.previousSegmentEndpoints=seams.ToArray();report.passed=rows.Count==182&&rows.All(x=>x.passed)&&seams.Count==2&&seams.All(x=>x.passed);player.SetSample(0,60);return report;
        }
        [Serializable]public class Report{public string unity,utc,method;public bool passed,hmdVerified;public Record[]records;public Playback18Validation.Measurement[]previousSegmentEndpoints;}
        [Serializable]public class Record{public int rate,masterSample;public float seconds,archiveStart,archiveEnd;public bool timeSettingsMatch,passed;public Playback18Validation.Measurement geometry;}
    }
}
