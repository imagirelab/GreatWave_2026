// 設計39：紙の地の質感（①）と摺りのむら（②）の共通部。どちらも「面か世界に固定した 3 次元の座標 p（m）」の値の雑音で、画面の座標は使わない。
//   ① 紙の地（_DS39Mode = 0）：細かい繊維と地の粒。水平の 2 方向（x・z）へ引き伸ばした繊維 2 つと、等方の粒 3 オクターブ。
//   ② 摺りのむら（_DS39Mode = 1）：大きなむら。水平（版木の木目の向き）へ引き伸ばした低い周波数の雑音 2 オクターブ。
// 係数 f = 1 + 振幅 × 利得 × (2g − 1)（g は 0〜1 の雑音）。描画は掛け算（Blend DstColor SrcColor、出力 0.5 × f。2 倍の掛け算で 0.5 が 1 倍）。
// エイリアスの抑え：オクターブごとに、画素あたりの周期の数（fwidth(p) × 周波数）が 0.25 を超えると平均（0.5）へ寄せ、0.5 で消す。
// これは細かすぎる模様を消すだけで、模様の位置は p だけで決まる（頭が動いても面・世界の上で止まっている）。
// 大域の _DS39Gain（未設定は 0 → 1 倍として読む）：検査の描画で模様を強めて測るためだけに使う。作品の描画では入れない。
#ifndef GREATWAVE_DS39_PAPER_COMMON_INCLUDED
#define GREATWAVE_DS39_PAPER_COMMON_INCLUDED

float _DS39Gain;

float DS39Hash(float3 p)
{
    p = frac(p * 0.3183099 + float3(0.71, 0.113, 0.419));
    p *= 17.0;
    return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
}

// 3 次元の値の雑音（0〜1、格子の 8 隅の三重線形、smoothstep の重み）
float DS39Noise(float3 x)
{
    float3 i = floor(x);
    float3 f = frac(x);
    f = f * f * (3.0 - 2.0 * f);
    float a = DS39Hash(i + float3(0, 0, 0)), b = DS39Hash(i + float3(1, 0, 0));
    float c = DS39Hash(i + float3(0, 1, 0)), d = DS39Hash(i + float3(1, 1, 0));
    float e = DS39Hash(i + float3(0, 0, 1)), g = DS39Hash(i + float3(1, 0, 1));
    float h = DS39Hash(i + float3(0, 1, 1)), k = DS39Hash(i + float3(1, 1, 1));
    return lerp(lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y), lerp(lerp(e, g, f.x), lerp(h, k, f.x), f.y), f.z);
}

// 周波数 freq（1/m、成分ごと）のオクターブ。fw は p の画素あたりの変化（fwidth）
float DS39Octave(float3 p, float3 freq, float3 fw, float3 shift)
{
    float cyc = length(fw * freq);                 // 画素あたりの周期の数
    float w = saturate((0.5 - cyc) / 0.25);        // 0.25 以下で 1、0.5 以上で 0
    return lerp(0.5, DS39Noise(p * freq + shift), w);
}

// ① 紙の地：0〜1（平均 0.5）
float DS39PaperGrain(float3 p, float3 fw)
{
    float fib1 = DS39Octave(p, float3(3.0, 14.0, 14.0), fw, float3(11.3, 0, 5.1));     // x へ長い繊維（長さ約 33 cm、幅約 7 cm）
    float fib2 = DS39Octave(p, float3(14.0, 14.0, 3.0), fw, float3(3.7, 19.1, 0));     // z へ長い繊維
    float g1 = DS39Octave(p, float3(6.0, 6.0, 6.0), fw, float3(0, 7.7, 2.9));
    float g2 = DS39Octave(p, float3(16.0, 16.0, 16.0), fw, float3(5.5, 1.3, 8.2));
    float g3 = DS39Octave(p, float3(40.0, 40.0, 40.0), fw, float3(2.1, 4.4, 0.6));
    float fib = max(fib1, fib2) - 0.08;               // 繊維は明るい筋（2 つの最大は平均が約 0.58 なので 0.08 引いて平均を 0.5 近くへ）
    return 0.30 * fib + 0.25 * g1 + 0.25 * g2 + 0.20 * g3;
}

// ② 摺りのむら：0〜1（平均 0.5）。水平の x へ引き伸ばしたむら（版木の木目）と、大きな斑
float DS39Mura(float3 p, float3 fw)
{
    float m1 = DS39Octave(p, float3(0.05, 0.35, 0.12), fw, float3(1.9, 3.3, 7.1));    // 横に長いむら（約 20 m × 3 m）
    float m2 = DS39Octave(p, float3(0.12, 0.12, 0.12), fw, float3(9.4, 2.2, 4.6));    // 大きな斑（約 8 m）
    float m3 = DS39Octave(p, float3(0.4, 1.2, 0.4), fw, float3(6.6, 0.8, 3.1));       // 版木の木目の細い筋
    return 0.45 * m1 + 0.35 * m2 + 0.20 * m3;
}

// 掛け算の係数の出力（Blend DstColor SrcColor で 2 × 出力 × 下の色）
float4 DS39Out(float3 p, float mode, float amp)
{
    float3 fw = fwidth(p);
    float g = mode < 0.5 ? DS39PaperGrain(p, fw) : DS39Mura(p, fw);
    float gain = _DS39Gain > 0.0 ? _DS39Gain : 1.0;
    float f = 1.0 + amp * gain * (2.0 * g - 1.0);
    f = clamp(f, 0.0, 2.0);
    return float4(0.5 * f, 0.5 * f, 0.5 * f, 0.5);
}
#endif
