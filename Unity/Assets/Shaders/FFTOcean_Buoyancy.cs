using UnityEngine;
using UnityEngine.Rendering;
using Unity.Collections;
using System.Collections.Generic;

public class FFTOcean_Buoyancy : MonoBehaviour
{
    public FFTOcean_Script waterSource;
    public int voxelsPerAxisX = 2;
    public int voxelsPerAxisY = 2;
    public int voxelsPerAxisZ = 2;

    [Range(0.1f, 20.0f)]
    public float linearDragIntensity;
    [Range(0.1f, 20.0f)]
    public float angularDragIntensity;

    private Rigidbody rigidBody;
    private Collider cachedCollider;

    private Voxel[,,] voxels;
    private List<Vector3> receiverVoxels;
    private Vector3 voxelSize;

    public struct Voxel
    {
        public Vector3 position { get; }
        private float cachedBuoyancyData;
        private FFTOcean_Script waterSource;
        private AsyncGPUReadbackRequest voxelWaterRequest;

        public Voxel(Vector3 position, FFTOcean_Script waterSource)
        {
            this.position = position;
            this.cachedBuoyancyData = 0.0f;
            this.waterSource = waterSource;

            voxelWaterRequest = AsyncGPUReadback.Request(waterSource.GetBuoyancyData(), 0, 0, 1, 0, 1, 0, 1, null);
        }

        public float GetWaterHeight()
        {
            return cachedBuoyancyData;
        }

        public void Update(Transform parentTransform)
        {
            if (voxelWaterRequest.done)
            {
                if (voxelWaterRequest.hasError)
                {
                    Debug.Log("Buoyancy Request Error");
                    return;
                }

                NativeArray<ushort> buoyancyDataQuery = voxelWaterRequest.GetData<ushort>();

                cachedBuoyancyData = Mathf.HalfToFloat(buoyancyDataQuery[0]);

                Vector3 worldPos = parentTransform.TransformPoint(this.position);
                Vector2 pos = new Vector2(worldPos.x, worldPos.z);
                Vector2 uv = worldPos * waterSource.Tile0;

                int x = Mathf.FloorToInt((uv.x - Mathf.Floor(uv.x)) * 1023);
                int y = Mathf.FloorToInt((uv.y - Mathf.Floor(uv.y)) * 1023);

                voxelWaterRequest = AsyncGPUReadback.Request(waterSource.GetBuoyancyData(), 0, x, 1, y, 1, 0, 1, null);
            }
        }
    }
    private void CreateVoxels()
    {
        receiverVoxels = new List<Vector3>();

        Quaternion initialRotation = this.transform.rotation;
        this.transform.rotation = Quaternion.identity;

        Bounds bounds = this.cachedCollider.bounds;
        voxelSize = new Vector3(bounds.size.x / voxelsPerAxisX,
                                bounds.size.y / voxelsPerAxisY,
                                bounds.size.z / voxelsPerAxisZ);
        voxels = new Voxel[voxelsPerAxisX, voxelsPerAxisY, voxelsPerAxisZ];

        for (int x = 0; x < voxelsPerAxisX; ++x)
        {
            for (int y = 0; y < voxelsPerAxisY; ++y)
            {
                for (int z = 0; z < voxelsPerAxisZ; ++z)
                {
                    Vector3 voxelPoint = voxelSize;
                    voxelPoint.Scale(new Vector3(x + 0.5f, y + 0.5f, z + 0.5f));
                    voxelPoint += bounds.min;

                    voxels[x, y, z] = new Voxel(this.transform.InverseTransformPoint(voxelPoint), waterSource);
                    receiverVoxels.Add(new Vector3(x, y, z));
                }
            }
        }
    }

    private void OnEnable()
    {
        if (waterSource == null) return;
        rigidBody = GetComponent<Rigidbody>();
        cachedCollider = GetComponent<Collider>();
    }

    void Update()
    {
        if (voxels == null && waterSource.GetBuoyancyData() != null) CreateVoxels();
        for (int i = 0; i < receiverVoxels.Count; ++i) {
            voxels[ (int)receiverVoxels[i].x,
                    (int)receiverVoxels[i].y,
                    (int)receiverVoxels[i].z].Update(this.transform);
        }
    }

    void FixedUpdate()
    {
        if (voxels == null || cachedCollider == null || rigidBody == null) return;

        float boundsVolume = cachedCollider.bounds.size.x * cachedCollider.bounds.size.y * cachedCollider.bounds.size.z;
        float density = rigidBody.mass / boundsVolume;

        float submergedVolume = 0.0f;
        float voxelHeight = voxelSize.y;
        float UnitForce = (1.0f - density) / voxels.Length;

        for (int x = 0; x < voxelsPerAxisX; ++x)
        {
            for (int y = 0; y < voxelsPerAxisY; ++y)
            {
                for (int z = 0; z < voxelsPerAxisZ; ++z)
                {
                    Vector3 worldPos = this.transform.TransformPoint(voxels[x, y, z].position);

                    float waterLevel = voxels[x, y, z].GetWaterHeight();
                    float depth = waterLevel - worldPos.y + voxelHeight;
                    float submergedFactor = Mathf.Clamp(depth / voxelHeight, 0, 1);
                    submergedVolume += submergedFactor;

                    float displacement = Mathf.Max(0.0f, depth);

                    Vector3 force = -Physics.gravity * displacement * UnitForce;
                    rigidBody.AddForceAtPosition(force, worldPos);
                }
            }
        }

        submergedVolume /= voxels.Length;

        this.rigidBody.linearDamping = Mathf.Lerp(2.0f, linearDragIntensity, submergedVolume);
        this.rigidBody.angularDamping = Mathf.Lerp(2.0f, angularDragIntensity, submergedVolume);
    }

    void OnDisable()
    {
        voxels = null;
    }

    private void OnDrawGizmos()
    {
        if (this.voxels != null)
        {
            //            Fit.Plane(points, out origin, out direction, 50, true);

            for (int x = 0; x < voxelsPerAxisX; ++x)
            {
                for (int y = 0; y < voxelsPerAxisY; ++y)
                {
                    for (int z = 0; z < voxelsPerAxisZ; ++z)
                    {
                        Gizmos.color = Color.green;
                        Gizmos.DrawCube(this.transform.TransformPoint(this.voxels[x, y, z].position), this.voxelSize * 0.8f);
                    }
                }
            }
        }
    }
}
