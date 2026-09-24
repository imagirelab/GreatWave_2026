using System;
using UnityEngine;

namespace GreatWave
{
    [Serializable] public class FixedTopology16Reference
    {
        public string grid_object_name;
        public float fps;
        public int[] triangles;
        public FixedTopology16Sample[] samples;
        public FixedTopology16Marker[] markers;
    }
    [Serializable] public class FixedTopology16Sample
    {
        public float frame,time_seconds;
        public Vector3[] positions,normals;
        public Vector3 bounds_min,bounds_max;
    }
    [Serializable] public class FixedTopology16Marker
    {
        public string name;
        public Vector3 center,size;
    }
}
