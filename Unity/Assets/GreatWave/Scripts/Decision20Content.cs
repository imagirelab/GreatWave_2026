using UnityEngine;
using UnityEngine.Formats.Alembic.Importer;
using GreatWave.Playback18;
namespace GreatWave
{
    public class Decision20Content:MonoBehaviour
    {
        public bool useVat;public Camera testCamera;public AlembicStreamPlayer stream;public GameObject vatRoot;public Material vatMaterial;public Playback18VAT.Data vatData;public Bounds vatBounds;public Bounds[]captureBounds;[System.NonSerialized]public int cameraMode,currentSample;
        public void Initialize(){if(useVat){Playback18VAT.Bind(vatMaterial,vatData,0);foreach(var r in vatRoot.GetComponentsInChildren<Renderer>(true))r.localBounds=vatBounds;}SetSample(0);}
        public void SetSample(int k){currentSample=k;if(useVat)Playback18VAT.SetFrame(vatMaterial,vatData,k);else{stream.UpdateImmediately(k/24f);Playback18Validation.RefreshBounds(stream);}}
    }
}
