using System;
using System.Collections.Generic;
using GreatWave.Design30;
using UnityEngine;

namespace GreatWave.Design36
{
    // 設計36：周りの海のシート（DS30SheetPlayer、near・far）の色を、設計30 の仮の 2 色（t* の高さの閾値で白、ほかは藍濃）から、
    // 主役波と同じ調色板の 4 段（白・淡い水色・藍中・藍濃）へ替える。
    //   ・UV3 = ds36_palette_prep.py の頂点ごとの値（u = 0.05 + 0.9·s、s は t* の相対の高さ。谷の縁は藍中の 1 段）。
    //   ・色区の表 = u に沿った 4 色区の符号付き距離（256² RGBA8）。DS27 NPR White の読み（最大の色区＋約 1 画素のアンチエイリアス）のまま。
    //   ・白の段は、パッケージの白の時間場（T_white）がある頂点だけ。白が届く前は preWhiteClass（淡い水色）。
    // 読み込みの前（DS30SinglePlayback.Prepare の前）に Configure を呼ぶ。調色板の値（_White・_Mizuiro・_AiMid・_AiDark）は、
    // 読み込みの後に SyncFromHero で主役波の材質の値をレンダラーの MaterialPropertyBlock へ写す（材質のファイルは変えない。主役波と海の 1 段の差をなくす）。
    [DefaultExecutionOrder(40)]
    public class DS36SeaPalette : MonoBehaviour
    {
        public DS30SinglePlayback playback;
        public string rampPath = "Build/Design/36/palette/prep/ds36_sea_ramp_256_rgba8.bin";
        public int rampSize = 256;
        public string uv3Near = "Build/Design/36/palette/prep/ds36_sea_uv3_near_f32.bin";
        public string uv3Far = "Build/Design/36/palette/prep/ds36_sea_uv3_far_f32.bin";
        public int preWhiteClass = 1;
        public bool configured;

        static readonly string[] Props = { "_White", "_Mizuiro", "_AiMid", "_AiDark" };

        public List<DS30SheetPlayer> SeaSheets()
        {
            var l = new List<DS30SheetPlayer>();
            if (playback == null) return l;
            foreach (var s in playback.sheets) if (s != null && s.sheetName != "hero") l.Add(s);
            return l;
        }

        public DS30SheetPlayer Hero()
        {
            if (playback == null) return null;
            foreach (var s in playback.sheets) if (s != null && s.sheetName == "hero") return s;
            return null;
        }

        /// <summary>海のシートの色の設定を替える（読み込みの前）。</summary>
        public void Configure()
        {
            foreach (var s in SeaSheets())
            {
                string uv = s.sheetName == "near" ? uv3Near : (s.sheetName == "far" ? uv3Far : null);
                if (uv == null) continue;
                s.whiteAboveTStarY = float.NaN;
                s.sdfPath = System.IO.Path.GetFullPath(rampPath);
                s.sdfSize = rampSize;
                s.uv3File = System.IO.Path.GetFullPath(uv);
                s.warpPath = "";
                s.preWhiteClass = preWhiteClass;
                s.whiteEnabled = true;
            }
            configured = true;
        }

        /// <summary>主役波の材質の調色板を、海のシートのレンダラーの MaterialPropertyBlock へ写す（読み込みの後）。</summary>
        public Color[] SyncFromHero()
        {
            var h = Hero();
            if (h == null || h.Surface == null) return null;
            var hm = h.Surface.sharedMaterial;
            var cols = new Color[4];
            var b = new MaterialPropertyBlock();
            h.Surface.GetPropertyBlock(b);
            for (int i = 0; i < 4; i++) cols[i] = b.HasColor(Props[i]) ? b.GetColor(Props[i]) : hm.GetColor(Props[i]);
            foreach (var s in SeaSheets())
            {
                var r = s.Surface;
                if (r == null) continue;
                r.GetPropertyBlock(b);
                for (int i = 0; i < 4; i++) b.SetColor(Props[i], cols[i]);
                r.SetPropertyBlock(b);
            }
            return cols;
        }

        void Awake()
        {
            if (Application.isPlaying && !configured) Configure();
        }

        void Start()
        {
            if (Application.isPlaying) SyncFromHero();
        }
    }
}
