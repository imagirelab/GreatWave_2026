using System;
using System.IO;
using System.IO.Compression;
using UnityEngine;

namespace GreatWave
{
    public class Sampling19Reference
    {
        public Playback18Reference.Sample[] samples;
        public static Sampling19Reference Read(TextAsset asset)
        {
            using(var memory=new MemoryStream(asset.bytes))
            using(var zipped=new GZipStream(memory,CompressionMode.Decompress))
            using(var reader=new BinaryReader(zipped))
            {
                if(System.Text.Encoding.ASCII.GetString(reader.ReadBytes(8))!="GW19REF1"||reader.ReadInt32()!=1||reader.ReadInt32()!=121||reader.ReadInt32()!=60)
                    throw new InvalidDataException("19の実60Hz/121時刻ではありません。");
                var result=new Sampling19Reference{samples=new Playback18Reference.Sample[121]};
                for(int k=0;k<121;k++)
                {
                    int index=reader.ReadInt32();float time=reader.ReadSingle();int count=reader.ReadInt32(),indices=reader.ReadInt32();
                    if(index!=k||Math.Abs(time-k/60f)>1e-6||count<3||indices<3||indices%3!=0)throw new InvalidDataException("19の時刻/形状数が不正です。");
                    var s=new Playback18Reference.Sample{time=time,positions=new Vector3[count],normals=new Vector3[count],triangles=new int[indices]};
                    for(int i=0;i<count;i++)s.positions[i]=new Vector3(-reader.ReadSingle(),reader.ReadSingle(),reader.ReadSingle());
                    for(int i=0;i<count;i++)s.normals[i]=new Vector3(-reader.ReadSingle(),reader.ReadSingle(),reader.ReadSingle());
                    for(int i=0;i<indices;i++)s.triangles[i]=reader.ReadInt32();result.samples[k]=s;
                }
                if(reader.BaseStream.ReadByte()!=-1)throw new InvalidDataException("19の参照末尾に余分な値があります。");return result;
            }
        }
    }
}
