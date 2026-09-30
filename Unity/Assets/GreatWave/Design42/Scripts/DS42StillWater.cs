using UnityEngine;

namespace GreatWave.Design42
{
    // 静水：この GameObject の y の高さの平らな水面
    public class DS42StillWater : DS42Water
    {
        public override float HeightAt(Vector3 worldPos) => transform.position.y;
    }
}
