using System;
using System.IO;
using System.IO.Compression;
using UnityEngine;

namespace GreatWave
{
    // 実BGEOからHoudiniで書いた三角化基準だけを読む。流体の式は再生成しない。
    public class Playback18Reference
    {
        public int rate;
        public Sample[] samples;
        public static Playback18Reference Read(TextAsset asset)
        {
            using(var memory=new MemoryStream(asset.bytes))
            using(var zipped=new GZipStream(memory,CompressionMode.Decompress))
            using(var reader=new BinaryReader(zipped))
            {
                if(System.Text.Encoding.ASCII.GetString(reader.ReadBytes(8))!="GW18REF1"||reader.ReadInt32()!=1)
                    throw new InvalidDataException("18のHoudini基準形式が一致しません。");
                int count=reader.ReadInt32(),rate=reader.ReadInt32();
                if(count!=49||rate!=24)throw new InvalidDataException("17由来の49時刻/24Hzではありません。");
                var result=new Playback18Reference{rate=rate,samples=new Sample[count]};
                for(int k=0;k<count;k++)
                {
                    int index=reader.ReadInt32();float time=reader.ReadSingle();int vertices=reader.ReadInt32(),indices=reader.ReadInt32();
                    if(index!=k||Math.Abs(time-k/24f)>1e-6||vertices<3||indices<3||indices%3!=0)
                        throw new InvalidDataException("参照の時刻または形状数が不正です。");
                    var sample=new Sample{time=time,positions=new Vector3[vertices],normals=new Vector3[vertices],triangles=new int[indices]};
                    for(int i=0;i<vertices;i++)sample.positions[i]=new Vector3(-reader.ReadSingle(),reader.ReadSingle(),reader.ReadSingle());
                    for(int i=0;i<vertices;i++)sample.normals[i]=new Vector3(-reader.ReadSingle(),reader.ReadSingle(),reader.ReadSingle());
                    for(int i=0;i<indices;i++)sample.triangles[i]=reader.ReadInt32();
                    result.samples[k]=sample;
                }
                if(reader.BaseStream.ReadByte()!=-1)throw new InvalidDataException("参照ファイルの末尾に余分なデータがあります。");
                return result;
            }
        }
        public class Sample{public float time;public Vector3[]positions,normals;public int[]triangles;}
    }
}
