using System.Collections.Generic;
using GreatWave.Design31;
using UnityEngine;

namespace GreatWave.Polish31
{
    // 仕上げ31：飛沫を色の段ごとに 2 つの DS31InstancedParticles（白・生成りと灰の白）で描くので、2 つ目以後の Play モードの描画の入切を、
    // 1 つ目（設計34 の DS34LayerSet が入切する DS31 spray）に合わせる。時刻は設計46 の共通時計（DS46ClockBus の sprays の一覧）が当てる。
    // 粒の位置・色・数は変えない（読むだけ）。
    public class PL31SprayFollow : MonoBehaviour
    {
        public DS31InstancedParticles main;
        public List<DS31InstancedParticles> follow = new List<DS31InstancedParticles>();

        void Update() { Sync(); }
        void LateUpdate() { Sync(); }

        public void Sync()
        {
            if (main == null) return;
            foreach (var f in follow) if (f != null) f.drawInPlayMode = main.drawInPlayMode;
        }
    }
}
