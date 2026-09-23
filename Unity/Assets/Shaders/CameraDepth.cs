using UnityEngine;

public class CameraDepth : MonoBehaviour
{
        void OnEnable()
    {
        GetComponent<Camera>().depthTextureMode = DepthTextureMode.DepthNormals;
    }
}
