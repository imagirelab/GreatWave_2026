using UnityEngine;

namespace GreatWave.Design42
{
    // 設計42：船が読む水面の高さの入口。設計42 は静水（平らな水面）だけを使う。
    // 設計43 で、設計30 のうねりと主役波のシートの下側の一価の面を同じ時計で読む実装をこの型の子として足す。
    public abstract class DS42Water : MonoBehaviour
    {
        // 世界の点 (x, z) の真上・真下の水面の高さ（世界の y、m）
        public abstract float HeightAt(Vector3 worldPos);
    }
}
