using System;
using System.Collections;
using System.Collections.Generic;
using static System.Runtime.InteropServices.Marshal;
using UnityEngine;
using UnityEngine.Rendering;

[RequireComponent (typeof(MeshFilter), typeof(MeshRenderer))]

public class FFTOcean_Script : MonoBehaviour
{

    //声明全部贴图
    public RenderTexture InitialSpectrumTexture,
                         SpectrumTexture,
                         DisplacementTexture,
                         SlopeTexture,
                         BuoyancyData,
                         VariationMask,
                         ClawMaskTexture;   // RGBA: heightScore, slopeScore, crestScore, clawScore
    [Header("Shaders")]
    public ComputeShader FFTComputeShader;
    public Shader FFTWaterShader;


    [Header("Water Surface Mesh Setting")]

    public int waterMeshLength = 200;
    public int waterMeshRes = 10;

    [Range(10, 20)]
    public int TessEdgeLength = 16;
    private Mesh waterSurface;
    private Material waterMaterial;
    private int Resolusion, threadGroupsX, threadGroupsY;


    [Header("GPU Safety")]
    // Editor Game view ignores QualitySettings vsync, so Play Mode runs uncapped and keeps the GPU
    // at 100% load with fast power transients — on an RTX 3080 this can trip the PSU and reboot the PC.
    // 编辑器 Game 视图会忽略 QualitySettings 的垂直同步，Play 模式不限帧会让 GPU 持续满载并产生功耗尖峰，
    // 3080 上足以触发电源过流保护导致整机重启。这里强制限帧。0 = 不限制（不建议）。
    [Tooltip("Play Mode frame rate cap. Prevents uncapped GPU load that can trip the PSU. 0 = uncapped (not recommended).")]
    public int playModeFrameRateCap = 60;

    [Header("General Settings")]
    public float DisplaceDepthAttenuation = 10;

    public float FoamDepthAttenuation = 20;

    [Range(0.0f, 5.0f)]
    public float Speed = 0.5f;
    public int Seed = 28;
    [Range(2.0f, 20.0f)]
    public float Gravity = 9.81f;

    private float Depth = 10.0f;
    private float RepeatTime = 200.0f;
    private float LowCutOff = 0.0001f;
    private float HighCutOff = 9000.0f;


    [Header("Layer 01")]
    [Range(0.0f, 1.0f)]
    public float LayerContribute0 = 0.8f;
    [Range(0.0f, 0.25f)]
    public float Tile0 = 0.04f;

    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum0;
    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum1;

    private int LengthScale0 = 4;


    [Header("Layer 02")]
    [Range(0.0f, 1.0f)]
    public float LayerContribute1 = 0.8f;

    [Range(0.0f, 0.25f)]
    public float Tile1 = 0.06f;

    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum2;
    public JONSWAP_DisplaySettings DisplaySpectrum3;
    private int LengthScale1 = 4;


    [Header("Layer 03")]
    [Range(0.0f, 1.0f)]
    public float LayerContribute2 = 0.6f;

    [Range(0.0f, 0.25f)]
    public float Tile2 = 0.12f;

    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum4;
    public JONSWAP_DisplaySettings DisplaySpectrum5;
    private int LengthScale2 = 4;


    [Header("Layer 04")]
    [Range(0.0f, 1.0f)]
    public float LayerContribute3 = 0.4f;

    [Range(0.0f, 0.25f)]
    public float Tile3 = 0.18f;

    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum6;
    public JONSWAP_DisplaySettings DisplaySpectrum7;
    private int LengthScale3 = 4;


    [Header("Shader Settings")]
    public Color ScatterColor = new Color(0.0f, 0.67f, 1.0f, 1.0f);
    public Color ScatterPeakColor = new Color(0.0f, 0.67f, 1.0f, 1.0f);
    public float WavePeakScatterStrength = 2.0f;
    public float ScatterStrength = 0.1f;
    public float ScatterShadowStrength = 0.1f;
    [Space(10)]

    public float AmbientDensity = 0.2f;
    public float EnvirReflectStrength = 1.0f;
    [Space(10)]
    public float FoamRoughness = 0.2f;
    public float Roughness = 0.1f;
    [Space(10)]
    public float NormalStrength = 0.2f;

    public float HeightStrength = 1.0f;

    [Header("Storm Wave Geometry")]
    // These values only change final visible displacement, not the FFT spectrum itself.
    // 这些参数只放大最终可见位移，不直接改 FFT 频谱本身。
    [Tooltip("Amplifies the actual vertical mesh displacement, making wave peaks and troughs taller.")]
    public float VerticalDisplacementStrength = 1.0f;
    [Tooltip("Amplifies horizontal choppiness in the displaced water mesh.")]
    public float HorizontalDisplacementStrength = 1.0f;
    [Tooltip("Extra non-linear lift for positive crests, making tall waves sharper and more Hokusai-like.")]
    public float CrestAmplification = 0.0f;

    [Space(10)]
    [Range(0.0f, 1.0f)]
    public float ShadowIntensity = 0.2f;


    [Header("Foam Settings")]
    public Color FoamColor = new Color(1, 1, 1, 1);
    [Space(10)]
    public Vector2 WaveSharp = new Vector2(0.4f, 0.4f);
    [Range(-1.0f, 1.0f)]
    public float FoamBias = 0.2f;

    [Range(-0.0f, 4.0f)]
    public float FoamPower = 1.5f;

    [Range(0.0f, 1.0f)]
    public float FoamAdd =0.1f;

    [Range(0.0f, 1.0f)]
    public float FoamDecayRate = 0.05f;
    [Range(0.01f, 1.0f)]
    public float EdgeFoamPower;

    [Header("Normal Variation")]
    [Range(0.01f, 10.0f)]
    public float VarMaskRange = 3.0f;
    [Range(0.01f, 10.0f)]
    public float VarMaskPower = 3.0f;
    [Range(0.01f, 10.0f)]
    public float VarMaskTexScale = 2.0f;

    // ---- Claw Mask Scoring (passed to compute shader) ----
    // The FFT compute shader writes an ARGBHalf mask used by OceanClawGpuInstancer.
    // FFT compute shader 会写入一张 ARGBHalf mask，供 OceanClawGpuInstancer 在 GPU 上筛选波峰。
    // R = height score, G = slope score, B = crest score, A = combined claw score.
    [Header("Claw Mask (GPU Scoring)")]
    [Tooltip("Minimum wave height (meters) for a non-zero height score")]
    public float ClawHeightMin = 0.5f;
    [Tooltip("Wave height (meters) that gives a height score of 1.0")]
    public float ClawHeightMax = 3.0f;
    [Tooltip("Minimum slope magnitude for a non-zero slope score")]
    public float ClawSlopeMin  = 0.1f;
    [Tooltip("Slope magnitude that gives a slope score of 1.0")]
    public float ClawSlopeMax  = 1.5f;

    // ---- Ukiyo-e woodblock style (Hokusai "Great Wave" palette) ----
    // The runtime material is created from FFTWaterShader, so every style property
    // must be exposed here and uploaded in SetMaterialParam each frame.
    // 浮世绘版画风格（神奈川冲浪里配色）。运行时材质由脚本创建，所有风格参数都在这里暴露并每帧上传。
    [Header("Ukiyo-e Style / 浮世绘风格")]
    [Tooltip("Deepest water ink, the dark Prussian blue of wave troughs. 波谷处最深的普鲁士蓝。")]
    public Color DeepInkColor = new Color(0.043f, 0.137f, 0.243f, 1f);
    [Tooltip("Mid-tone water band. 中间调的水面蓝。")]
    public Color MidWaterColor = new Color(0.165f, 0.357f, 0.529f, 1f);
    [Tooltip("Palest water band near crests. 接近波峰的最浅水色。")]
    public Color PaleWaterColor = new Color(0.520f, 0.690f, 0.735f, 1f);
    [Tooltip("Flat cream used for foam shapes, like aged paper white. 泡沫的奶油色（旧纸白）。")]
    public Color FoamCreamColor = new Color(0.992f, 0.974f, 0.908f, 1f);
    [Tooltip("Dark indigo ink for outlines around foam shapes and band edges. 泡沫边缘与色带交界的深蓝描线色。")]
    public Color OutlineInkColor = new Color(0.027f, 0.067f, 0.125f, 1f);
    [Space(6)]
    [Range(2, 6)]
    [Tooltip("Number of flat color bands across the water, like layered woodblock inks. 水面色带数量（套色版数）。")]
    public int ToonBands = 4;
    [Range(0f, 1f)]
    [Tooltip("Strength of the dark ink outlines. 描线整体强度。")]
    public float OutlineStrength = 0.85f;
    [Range(0.005f, 0.2f)]
    [Tooltip("Width of the ink outline around foam shapes. 泡沫描边宽度。")]
    public float OutlineWidth = 0.06f;
    [Header("Ukiyo-e Line Work / 描边 (Brown & Arandjelovic, Sci 2020 §2.1)")]
    [Range(0f, 1.5f)]
    [Tooltip("Overall strength of the woodblock keyblock outlines (silhouette + crease) on the waves. 海浪描边整体强度。")]
    public float NprOutlineStrength = 0.9f;
    [Range(0.0005f, 0.03f)]
    [Tooltip("Silhouette sensitivity (depth edge): lower = outline more wave crests against the water behind. 轮廓描边灵敏度（越低越多）。")]
    public float NprSilhouetteThreshold = 0.004f;
    [Range(0.02f, 0.7f)]
    [Tooltip("Crease sensitivity (normal edge): lower = ink more surface folds / breaking lips. 折痕描边灵敏度。")]
    public float NprCreaseThreshold = 0.28f;
    [Range(0f, 1f)]
    [Tooltip("Strength of inner crease lines relative to the silhouette contour. 折痕线相对强度。")]
    public float NprCreaseStrength = 0.6f;
    [Range(0.5f, 4f)]
    [Tooltip("Outline width in pixels. 描边像素宽度。")]
    public float NprOutlineWidth = 1.5f;
    [Range(0.2f, 0.85f)]
    [Tooltip("Grazing-angle threshold for crest contour lines: lower = outline more of each wave face. 掠射角描边阈值（越低勾勒越多浪面）。")]
    public float NprGrazeThreshold = 0.5f;
    [Range(0f, 1f)]
    [Tooltip("Strength of the in-shader wave crest/ridge contour lines (bold ukiyo-e wave outlines). 海浪波峰描边强度。")]
    public float NprWaveEdgeStrength = 0.85f;
    [Range(0f, 1f)]
    [Tooltip("Strength of the bold band-contour outlines (woodblock color-band boundary lines that follow the wave shape). 色带等高线描边强度（最版画的浪形描边）。")]
    public float NprBandContourStrength = 0.7f;
    [Range(0.02f, 0.5f)]
    [Tooltip("Thickness of the band-contour lines. 等高线粗细。")]
    public float NprBandContourWidth = 0.15f;
    [Range(2f, 12f)]
    [Tooltip("Number of height-contour keylines on the water (decoupled from color bands) — more = more woodblock wave outlines. 水面等高线数量（与色阶解耦），越多浪形描边越密。")]
    public float NprContourCount = 6f;
    [Range(0f, 1f)]
    [Tooltip("Strength of the black ink outline around the white foam shapes (like the Great Wave's foam). 白沫描边强度。")]
    public float NprFoamOutlineStrength = 1.0f;
    [Range(1f, 12f)]
    [Tooltip("Thickness of the foam outline IN PIXELS (fwidth-normalized = constant width regardless of edge sharpness). 白沫描边粗细（像素）。")]
    public float NprFoamOutlineWidth = 5.0f;
    [Range(0f, 1f)]
    [Tooltip("Strength of the wave-crest ridge keyline (the local-height-maximum line that traces each swell). 波峰脊线描边强度。")]
    public float NprCrestOutlineStrength = 0.85f;
    [Range(0.003f, 0.05f)]
    [Tooltip("Crest-line sensitivity: LOWER catches more (gentler) crests but risks speckle; higher = only strong crests. 波峰脊线灵敏度，越低描越多浪峰但易出噪点。")]
    public float NprCrestOutlineThresh = 0.013f;
    [Header("Ukiyo-e Ink/Paper Grain (paper §2.2.1)")]
    [Range(0f, 0.4f)]
    [Tooltip("Strength of the screen-space woodblock ink/paper grain on the flat colours. 版画墨色/纸纹颗粒强度（屏幕空间）。")]
    public float NprPaperStrength = 0.10f;
    [Range(1.5f, 8f)]
    [Tooltip("Grain size in pixels per noise cell (smaller = finer grain). 颗粒大小（每格像素数，越小越细）。")]
    public float NprPaperScale = 3.0f;
    [Range(0f, 4f)]
    [Tooltip("How strongly the grain follows the scene (temporal coherence, eqs 6-7) vs sticking to the screen. 颗粒跟随场景的程度（时间一致性）。")]
    public float NprPaperFollow = 1.0f;
    [Range(0f, 1f)]
    [Tooltip("Anchor the paper grain to the WORLD/FFT surface (1) so it moves with the water, vs screen-space (0, swims as the camera/water moves). 把纸纹锚定到世界/FFT水面（1=跟着水动，0=屏幕空间会游）。")]
    public float NprPaperWorld = 1.0f;
    [Range(0.05f, 12f)]
    [Tooltip("World-space grain frequency when anchored to the surface (higher = finer grain; very high may shimmer at distance). 世界空间颗粒频率（越高越细，太高远处会闪）。")]
    public float NprPaperWorldFreq = 4.0f;
    [Header("Ukiyo-e Bokashi gradation (paper §2.2.3)")]
    [Range(0f, 1f)]
    [Tooltip("Bokashi: softens the hard color bands into a smooth gradation (0 = flat bands, 1 = fully smooth). 晕色：把硬色阶柔化为平滑渐变。")]
    public float NprBokashiStrength = 0.4f;
    [Header("Foam crest-silhouette outline (view·normal)")]
    [Range(0.01f, 0.6f)]
    [Tooltip("Where on the foam the silhouette line sits (n·v contour). Lower = closer to the true outer edge / sparser; higher = more coverage but creeps inward. 白沫剪影线位置（n·v等值线），越低越贴真外缘。")]
    public float NprFoamProxyLo = 0.12f;
    [Range(0.4f, 0.85f)]
    [Tooltip("Foam-region height gate for the outline (lower = line reaches farther down past the crest; too high cuts the line). 白沫区域高度门控，太高会切断线。")]
    public float NprFoamProxyWidth = 0.62f;
    [Range(6f, 24f)]
    [Tooltip("Macro-normal flatness for the silhouette (higher = flatter = fewer interior false lines but the line is sparser/needs steeper crests). 宏观法线平整度，越高内部假线越少但线越稀。")]
    public float NprFoamNormalUp = 13f;
    [Header("细线 Crease (fine-normal) + Distance LOD")]
    [Range(0f, 1f)]
    [Tooltip("Crease normal fineness: 0 = smooth macro normal (clean/subtle), 1 = per-pixel FFT normal (detailed fold lines, more speckle). 细线法线细度，越高折痕越细越多但越易麻点。")]
    public float NprCreaseNFine = 0.5f;
    [Range(0.02f, 0.4f)]
    [Tooltip("Crease gate: higher = only the sharpest folds draw a line (fewer, cleaner). 折痕阈值，越高线越少越干净。")]
    public float NprCreaseNThresh = 0.16f;
    [Range(0f, 1.5f)]
    [Tooltip("Crease (fine line) ink strength. 细线深浅。")]
    public float NprCreaseNStrength = 0.85f;
    [Range(0f, 300f)]
    [Tooltip("Distance LOD: within this world distance the crease is full strength. LOD近距：此距离内细线满强度。")]
    public float NprLodNear = 40f;
    [Range(10f, 600f)]
    [Tooltip("Distance LOD: beyond this world distance the crease fully fades (kills far speckle). LOD远距：超此距离细线归零、远处干净。")]
    public float NprLodFar = 160f;
    [Range(0.5f, 4f)]
    [Tooltip("Distance LOD curve: 1 = linear, >1 = strong near / fast drop so mid-far stays weak. LOD曲线，越大近处越强、中远越弱。")]
    public float NprLodGamma = 2f;
    [Header("描边笔触 Stroke character (paper §2.1.6)")]
    [Range(0f, 1f)]
    [Tooltip("Hand-inked stroke: how much ink density varies along the outline (0 = uniform digital line, 1 = strong woodblock variation). 描边墨色沿线变化量，越高越像手刻木版笔触。")]
    public float NprStrokeVary = 0.4f;
    [Range(1f, 16f)]
    [Tooltip("Stroke ink-grain size in screen pixels (smaller = finer breakup along the line). 笔触墨纹大小（屏幕像素）。")]
    public float NprStrokeScale = 5f;
    [Range(0f, 0.6f)]
    [Tooltip("Stroke segmentation: how aggressively the outline breaks into discrete brush strokes (0 = continuous line, higher = more gaps/segments). 描边分段量，越高断口越多越像一段段笔触。")]
    public float NprStrokeGap = 0.12f;
    [Range(0f, 1f)]
    [Tooltip("Height-driven taper (Dadfar §5.1): how much the outline thins toward troughs — bold on crests, fading to nothing in deep troughs (0 = off = baseline, uniform). 线宽随高度收尖：浪尖粗、波谷渐细到无，0=关=现基准。")]
    public float NprStrokeTaper = 0f;
    [Range(0f, 0.7f)]
    [Tooltip("Height midpoint where the taper kicks in (lower = only deep troughs fade; higher = lines survive only on high crests). 收尖的高度中点，越低只有深谷消失、越高只有高浪尖留线。")]
    public float NprStrokeTaperHeight = 0.4f;
    [Range(0f, 1f)]
    [Tooltip("Foam coverage cutoff: lower = more cream foam shapes. 泡沫阈值，越低泡沫形状越多。")]
    public float FoamCutoff = 0.32f;
    [Range(0.01f, 0.5f)]
    [Tooltip("Softness of the foam shape edge before the ink line. 泡沫形状边缘的柔和度。")]
    public float FoamEdgeSoftness = 0.09f;
    [Range(0f, 1f)]
    [Tooltip("Woodblock print mottling from the variation mask. 版画印刷的颜料斑驳感。")]
    public float PrintMottle = 0.35f;
    [Range(0f, 1f)]
    [Tooltip("Subtle horizontal ink fibers across the water color bands.")]
    public float PrintLineStrength = 0.16f;
    [Range(0.01f, 0.25f)]
    [Tooltip("World-space spacing for the water ink fibers.")]
    public float PrintLineScale = 0.065f;
    [Range(0f, 1f)]
    [Tooltip("How strongly cream foam suppresses the water ink fibers.")]
    public float PrintLineFoamSuppression = 0.7f;
    [Range(0f, 1f)]
    [Tooltip("Strength of long vertical pale/deep blue woodblock color plates across the wave wall.")]
    public float PrintStripeStrength = 0.38f;
    [Range(0.005f, 0.12f)]
    [Tooltip("World-space spacing for vertical water color plates. Lower values make broader Hokusai-style bands.")]
    public float PrintStripeScale = 0.12f;
    [Range(0f, 24f)]
    [Tooltip("How much the vertical color plates bend with the FFT wave height.")]
    public float PrintStripeWarp = 1.20f;
    [Range(0f, 1f)]
    [Tooltip("Fade the vertical stripes out on the BRIGHTER water (pale iso-height/等高线 bands), keeping them on the darker water — so the bright bands stay clean (0 = off/baseline, 1 = full fade on bright bands). 竖条在亮色带上淡出、只留在较暗的水面，0=关，1=亮处全淡出。")]
    public float PrintStripeFaceGate = 0.85f;
    [Range(0.2f, 0.95f)]
    [Tooltip("Brightness midpoint where the stripes fade out: lower = stripes only survive in the very darkest water; higher = stripes persist into brighter bands before fading. 竖条淡出的亮度中点，越低越只在最暗的水里留、越高越往亮处保留。")]
    public float PrintStripeGateBright = 0.6f;
    [Range(0f, 1f)]
    [Tooltip("Bokashi (§2.2.3) on the stripe transition: widens the pale<->deep blend so the stripes gradate smoothly instead of a hard edge (0 = hard combs, 1 = very soft). 条纹明暗过渡的柔和度（bokashi 渐变），0=硬边，1=很柔。")]
    public float PrintStripeBokashi = 0.5f;
    [Range(0f, 1f)]
    [Tooltip("Additional flat cream applied to high crest lips before claw spawning.")]
    public float CrestWhiteBoost = 0.92f;
    [Range(0f, 1.5f)]
    [Tooltip("Threshold for crest-lip white foam plates.")]
    public float CrestWhiteThreshold = 0.46f;
    [Range(0f, 1f)]
    [Tooltip("Extra ink fibers on high, steep crest faces.")]
    public float CrestLineStrength = 0.22f;
    [Range(0f, 1f)]
    [Tooltip("Curved woodblock strokes on the blue wave wall below breaking foam.")]
    public float CrestCurlLineStrength = 0.18f;
    [Range(0.01f, 0.25f)]
    [Tooltip("World-space spacing for curved wave-wall strokes.")]
    public float CrestCurlLineScale = 0.055f;
    [Range(0f, 1f)]
    [Tooltip("Subtle ink contours inside cream foam shapes, like carved woodblock strokes.")]
    public float FoamContourStrength = 0.08f;
    [Range(0.01f, 0.3f)]
    [Tooltip("World-space spacing for the internal foam contour strokes.")]
    public float FoamContourScale = 0.085f;
    [Range(0f, 1f)]
    [Tooltip("Short scalloped cuts just inside foam rims.")]
    public float FoamScallopStrength = 0.12f;
    [Range(0.01f, 0.3f)]
    [Tooltip("World-space spacing for foam scallop cuts.")]
    public float FoamScallopScale = 0.115f;
    [Range(0f, 1f)]
    [Tooltip("Sparse blue negative-space pockets between cream foam leaves, matching Hokusai's carved foam gaps.")]
    public float FoamPocketStrength = 0.06f;
    [Range(0f, 1f)]
    [Tooltip("Short comb-like blue cuts on steep cream foam edges, echoing Hokusai foam tongues.")]
    public float FoamCombStrength = 0.08f;
    [Range(0.01f, 0.35f)]
    [Tooltip("World-space spacing for crest foam comb cuts.")]
    public float FoamCombScale = 0.13f;
    [Range(0f, 1f)]
    [Tooltip("Longer broken ink striations inside crest foam, following the carved flow of Hokusai foam.")]
    public float FoamStriationStrength = 0.07f;
    [Range(0.01f, 0.35f)]
    [Tooltip("World-space spacing for elongated crest foam striations.")]
    public float FoamStriationScale = 0.075f;
    [Range(0f, 1f)]
    [Tooltip("How much real lighting still affects the bands (0 = pure flat print). 光照对色带的影响程度（0 = 纯平涂）。")]
    public float LightInfluence = 0.3f;
    [Range(0f, 2f)]
    [Tooltip("How strongly wave height drives the color bands. 浪高对色带的驱动强度。")]
    public float HeightShadeScale = 0.55f;
    [Range(0f, 2f)]
    [Tooltip("How strongly wave steepness darkens toward the ink color. 坡度（浪壁）压暗色带的强度。")]
    public float SteepShadeScale = 0.5f;
    [Range(0, 6)]
    [Tooltip("Debug-only mask view: 0 off, 1 main wave gate, 2 lip gate, 3 raw foam/claw mask, 4 connected foam score, 5 final white mask, 6 stripe influence.")]
    public int HokusaiDebugView = 0;

    [Header("Fog Settings")]
    public Color FogColor = new Color(0.5f, 0.75f, 0.0f);

    [Range(0.0f, 20.0f)]
    public float FogDensity = 1.0f;
    [Range(0.0f, 10.0f)]
    public float FogPower = 4.0f;


    [System.Serializable]
    //传递到compute shader中的结构体
    public struct JONSWAP_ComputeSettings
    {
        public float scale;
        public float angle;
        public float spreadBlend;
        public float swell;
        public float alpha;
        public float peakOmega;
        public float gamma;
        public float shortWavesFade;
    }
    JONSWAP_ComputeSettings[] ComputeSpectrums = new JONSWAP_ComputeSettings[8];

    //开放的结构体参数 用windSpeed和windDirection动态计算alpha和peakOmega angle和gamma为了更好理解改了名称
    [System.Serializable]
    public struct JONSWAP_DisplaySettings
    {
        [Range(0, 5)]
        public float scale;
        public float windSpeed;

        [Range(0, 360)]
        public float windDirection;
        public float fetch;
        [Range(0, 1)]
        public float spreadBlend;
        [Range(0, 1)]
        public float swell;
        public float peakEnhancement;

        [Range(0, 1)]
        public float shortWavesFade;
    }
        // Allocate the JONSWAP parameter buffer for eight spectrum settings.
    private ComputeBuffer JonswapBuffer;

    //声明全部核心函数
    private int CS_InitializeSpectrum;
    private int CS_PackSpectrumConjugate;
    private int CS_UpdateSpectrum;
    private int CS_HorizontalIFFT;
    private int CS_VerticalIFFT;
    private int CS_AssembleTextures;

    // The initial spectrum only depends on the JONSWAP settings, so it is re-dispatched
    // only when those settings change instead of every frame (the per-frame re-init
    // doubled the GPU load for nothing and was a main contributor to the power spikes).
    // 初始频谱只取决于 JONSWAP 参数，因此只在参数变化时重新计算，而不是每帧重算。
    // 之前每帧重算让 GPU 负载凭空翻倍，是功耗尖峰的主要来源之一。
    private int _spectrumSettingsHash;
    private bool _spectrumDirty = true;

    // Saved so the Play Mode frame cap can be restored on disable.
    private int _prevVSyncCount;
    private int _prevTargetFrameRate;


    // Returns the low-cost height field used by buoyancy scripts.
    // 返回浮力脚本使用的低成本高度图。
    public RenderTexture GetBuoyancyData()   { return BuoyancyData; }

    // Returns the GPU claw mask consumed by OceanClawGpuInstancer.
    // 返回 OceanClawGpuInstancer 使用的 GPU 爪形评分图。
    public RenderTexture GetClawMaskTexture() { return ClawMaskTexture; }

    //设置默认值
    private void Reset()
    {
        //00
        DisplaySpectrum0.scale = 0.4f;
        DisplaySpectrum0.windSpeed = 1200.0f;
        DisplaySpectrum0.windDirection = 130.0f;
        DisplaySpectrum0.fetch = 600.0f;
        DisplaySpectrum0.spreadBlend = 1.0f;
        DisplaySpectrum0.swell = 0.9f;
        DisplaySpectrum0.peakEnhancement = 5.0f;
        DisplaySpectrum0.shortWavesFade = 0.8f;
        //01
        DisplaySpectrum1.scale = 0.4f;
        DisplaySpectrum1.windSpeed = 1000.0f;
        DisplaySpectrum0.windDirection = 50.0f;
        DisplaySpectrum1.fetch = 500.0f;
        DisplaySpectrum1.spreadBlend = 1.0f;
        DisplaySpectrum1.swell = 0.9f;
        DisplaySpectrum1.peakEnhancement = 5.0f;
        DisplaySpectrum1.shortWavesFade = 0.8f;


        //02
        DisplaySpectrum2.scale = 0.1f;
        DisplaySpectrum2.windSpeed = 800.0f;
        DisplaySpectrum2.windDirection = 45.0f;
        DisplaySpectrum2.fetch = 400.0f;
        DisplaySpectrum2.spreadBlend = 0.98f;
        DisplaySpectrum2.swell = 0.9f;
        DisplaySpectrum2.peakEnhancement = 5.0f;
        DisplaySpectrum2.shortWavesFade = 0.4f;
        //03
        DisplaySpectrum3.scale = 0.1f;
        DisplaySpectrum3.windSpeed = 800.0f;
        DisplaySpectrum3.windDirection = 135.0f;
        DisplaySpectrum3.fetch = 350.0f;
        DisplaySpectrum3.spreadBlend = 0.98f;
        DisplaySpectrum3.swell = 0.9f;
        DisplaySpectrum3.peakEnhancement = 5.0f;
        DisplaySpectrum3.shortWavesFade = 0.4f;


        //04
        DisplaySpectrum4.scale = 0.04f;
        DisplaySpectrum4.windSpeed = 100.0f;
        DisplaySpectrum4.windDirection = 260.0f;
        DisplaySpectrum4.fetch = 100.0f;
        DisplaySpectrum4.spreadBlend = 0.95f;
        DisplaySpectrum4.swell = 0.8f;
        DisplaySpectrum4.peakEnhancement = 3.0f;
        DisplaySpectrum4.shortWavesFade = 0.4f;
        //05
        DisplaySpectrum5.scale = 0.04f;
        DisplaySpectrum5.windSpeed = 50.0f;
        DisplaySpectrum5.windDirection = 280.0f;
        DisplaySpectrum5.fetch = 100.0f;
        DisplaySpectrum5.spreadBlend = 0.95f;
        DisplaySpectrum5.swell = 0.8f;
        DisplaySpectrum5.peakEnhancement = 3.0f;
        DisplaySpectrum5.shortWavesFade = 0.4f;


        //06
        DisplaySpectrum6.scale = 0.1f;
        DisplaySpectrum6.windSpeed = 10.0f;
        DisplaySpectrum6.windDirection = 0.0f;
        DisplaySpectrum6.fetch = 40.0f;
        DisplaySpectrum6.spreadBlend = 0.8f;
        DisplaySpectrum6.swell = 0.6f;
        DisplaySpectrum6.peakEnhancement = 1.0f;
        DisplaySpectrum6.shortWavesFade = 0.2f;
        //07
        DisplaySpectrum7.scale = 0.1f;
        DisplaySpectrum7.windSpeed = 10.0f;
        DisplaySpectrum7.windDirection = 0.0f;
        DisplaySpectrum7.fetch = 20.0f;
        DisplaySpectrum7.spreadBlend = 0.6f;
        DisplaySpectrum7.swell = 0.4f;
        DisplaySpectrum7.peakEnhancement = 1.0f;
        DisplaySpectrum7.shortWavesFade = 0.2f;
    }

    //生成水面mesh
    private void CreateWaterSurface()
    {
        GetComponent<MeshFilter>().mesh = waterSurface = new Mesh();
        waterSurface.name = "Water Surface";
        waterSurface.indexFormat = IndexFormat.UInt32;

        float halfLength = waterMeshLength / 2.0f;
        int sideVertCount = waterMeshLength * waterMeshRes / 100;

        Vector3[] vertices = new Vector3[(sideVertCount + 1) * (sideVertCount + 1)];
        Vector2[] uv = new Vector2[vertices.Length];
        Vector4[] tangents = new Vector4[vertices.Length];
        Vector4 tangent = new Vector4(1f, 0f, 0f, -1f);
        int[] triangles = new int[sideVertCount * sideVertCount * 6];

        //为顶点，uv，切线赋值
        for (int i = 0, x = 0; x <= sideVertCount; ++x)
        {
            for (int z = 0; z <= sideVertCount; ++z, ++i)
            {
                vertices[i] = new Vector3(((float)x / sideVertCount * waterMeshLength) - halfLength,
                                            0,
                                            ((float)z / sideVertCount * waterMeshLength) - halfLength);
                uv[i] = new Vector2((float)x / sideVertCount, (float)z / sideVertCount);
                tangents[i] = tangent;
            }
        }

        //为三角形赋值
        for (int triIndex = 0, verIndex = 0, x = 0; x < sideVertCount; ++verIndex, ++x)
        {
            for (int z = 0; z < sideVertCount; triIndex += 6, ++verIndex, ++z)
            {
                triangles[triIndex] = verIndex;
                triangles[triIndex + 1] = verIndex + 1;
                triangles[triIndex + 2] = verIndex + sideVertCount + 2;
                triangles[triIndex + 3] = verIndex;
                triangles[triIndex + 4] = verIndex + sideVertCount + 2;
                triangles[triIndex + 5] = verIndex + sideVertCount + 1;
            }
        }

        waterSurface.vertices = vertices;
        waterSurface.uv = uv;
        waterSurface.tangents = tangents;
        waterSurface.triangles = triangles;
        waterSurface.RecalculateNormals();
        Vector3[] normals = waterSurface.normals;
    }

    // Creates the runtime water material and assigns it to this GameObject MeshRenderer.
    private void CreateWaterMaterial()
    {
        if (FFTWaterShader == null) return;

        waterMaterial = new Material(FFTWaterShader);

        MeshRenderer renderer = GetComponent<MeshRenderer>();

        renderer.material = waterMaterial;
    }

    //———————————————————————————————————————————————————————————————————————
    //功能函数

    //Alpha数据转化函数
    float JonswapAlpha(float fetch, float windSpeed)
    {
        return 0.076f * Mathf.Pow(Gravity * fetch / windSpeed / windSpeed, -0.22f); //通过fetch和windSpeed来动态计算Alpha （需要寻找参考）
    }

    //PeakOmega数据转化函数
    float JonswapPeakFrequency(float fetch, float windSpeed)
    {
        return 22 * Mathf.Pow(windSpeed * fetch / Gravity / Gravity, -0.33f); //通过fetch和windSpeed来动态计算peakOmega （需要寻找参考）
    }

    //将用户数据传递到结构体中
    void FillSpectrumStruct(JONSWAP_DisplaySettings displaySettings, ref JONSWAP_ComputeSettings computeSettings)
    {
        computeSettings.scale = displaySettings.scale;
        computeSettings.angle = displaySettings.windDirection / 180 * Mathf.PI;
        computeSettings.spreadBlend = displaySettings.spreadBlend;
        computeSettings.swell = Mathf.Clamp(displaySettings.swell, 0.01f, 1);
        computeSettings.alpha = JonswapAlpha(displaySettings.fetch, displaySettings.windSpeed);
        computeSettings.peakOmega = JonswapPeakFrequency(displaySettings.fetch, displaySettings.windSpeed);
        computeSettings.gamma = displaySettings.peakEnhancement;
        computeSettings.shortWavesFade = displaySettings.shortWavesFade;
    }

    //创建缓冲区并将数据传递到缓冲区
    void SetSpectrumBuffers()
    {
        FillSpectrumStruct(DisplaySpectrum0, ref ComputeSpectrums[0]);
        FillSpectrumStruct(DisplaySpectrum1, ref ComputeSpectrums[1]);
        FillSpectrumStruct(DisplaySpectrum2, ref ComputeSpectrums[2]);
        FillSpectrumStruct(DisplaySpectrum3, ref ComputeSpectrums[3]);
        FillSpectrumStruct(DisplaySpectrum4, ref ComputeSpectrums[4]);
        FillSpectrumStruct(DisplaySpectrum5, ref ComputeSpectrums[5]);
        FillSpectrumStruct(DisplaySpectrum6, ref ComputeSpectrums[6]);
        FillSpectrumStruct(DisplaySpectrum7, ref ComputeSpectrums[7]);

        JonswapBuffer.SetData(ComputeSpectrums);
        FFTComputeShader.SetBuffer(0, "_JonswapParameters", JonswapBuffer);
    }

    //创建并设置贴图
    RenderTexture CreateRenderTexArray(int width, int height, int depth, RenderTextureFormat format, bool useMips)
    {
        RenderTexture rt = new RenderTexture(width, height, 0, format, RenderTextureReadWrite.Linear);
        rt.dimension = UnityEngine.Rendering.TextureDimension.Tex2DArray;
        rt.filterMode = FilterMode.Bilinear;
        rt.wrapMode = TextureWrapMode.Repeat;
        rt.enableRandomWrite = true;
        rt.volumeDepth = depth;
        rt.useMipMap = useMips;
        rt.autoGenerateMips = false;
        rt.anisoLevel = 16;
        rt.Create();

        return rt;
    }

    // Creates a writable 2D render texture used by the FFT pipeline.
    RenderTexture CreateRenderTex(int width, int height, RenderTextureFormat format, bool useMips)
    {
        RenderTexture rt = new RenderTexture(width, height, 0, format, RenderTextureReadWrite.Linear);
        rt.filterMode = FilterMode.Bilinear;
        rt.wrapMode = TextureWrapMode.Repeat;
        rt.enableRandomWrite = true;
        rt.useMipMap = useMips;
        rt.autoGenerateMips = false;
        rt.anisoLevel = 16;
        rt.Create();

        return rt;
    }

    // Uploads simulation constants to the FFT compute shader, including claw mask scoring thresholds.
    // 上传 FFT compute shader 参数，包括爪形评分阈值。
    void SetCompParam()
    {
        FFTComputeShader.SetFloat("_Depth", Depth);
        FFTComputeShader.SetFloat("_Gravity", Gravity);
        FFTComputeShader.SetFloat("_FrameTime", Time.time * Speed);
        FFTComputeShader.SetFloat("_RepeatTime", RepeatTime);
        FFTComputeShader.SetFloat("_LowCutOff", LowCutOff);
        FFTComputeShader.SetFloat("_HighCutOff", HighCutOff);
        FFTComputeShader.SetVector("_WaveSharp", WaveSharp);

        FFTComputeShader.SetInt("_Resolution", Resolusion);
        FFTComputeShader.SetInt("_LengthScale0", LengthScale0);
        FFTComputeShader.SetInt("_LengthScale1", LengthScale1);
        FFTComputeShader.SetInt("_LengthScale2", LengthScale2);
        FFTComputeShader.SetInt("_LengthScale3", LengthScale3);
        FFTComputeShader.SetInt("_Seed", Seed);

        FFTComputeShader.SetFloat("_FoamBias",      FoamBias);
        FFTComputeShader.SetFloat("_FoamPower",     FoamPower);
        FFTComputeShader.SetFloat("_FoamAdd",       FoamAdd);
        FFTComputeShader.SetFloat("_FoamDecayRate", FoamDecayRate);

        // Claw mask scoring params. These affect ClawMaskTexture only; final spawn persistence lives in OceanClawGpuInstancer.
        // 爪形 mask 评分参数。这里只影响 ClawMaskTexture；最终生成和生命周期由 OceanClawGpuInstancer 处理。
        FFTComputeShader.SetFloat("_ClawHeightMin", ClawHeightMin);
        FFTComputeShader.SetFloat("_ClawHeightMax", ClawHeightMax);
        FFTComputeShader.SetFloat("_ClawSlopeMin",  ClawSlopeMin);
        FFTComputeShader.SetFloat("_ClawSlopeMax",  ClawSlopeMax);
    }

    // Uploads per-frame material values so the rendered ocean matches the compute displacement textures.
    // 上传每帧材质参数，使渲染海面和 compute 生成的位移纹理保持一致。
    void SetMaterialParam()
    {
        waterMaterial.SetFloat("_DisplaceDepthAttenuation", DisplaceDepthAttenuation);
        waterMaterial.SetFloat("_FoamDepthAttenuation", FoamDepthAttenuation);

        waterMaterial.SetFloat("_TessEdgeLength", TessEdgeLength);
        waterMaterial.SetFloat("_Tile0", Tile0);
        waterMaterial.SetFloat("_Tile1", Tile1);
        waterMaterial.SetFloat("_Tile2", Tile2);
        waterMaterial.SetFloat("_Tile3", Tile3);

        waterMaterial.SetFloat("_LayerContribute0", LayerContribute0);
        waterMaterial.SetFloat("_LayerContribute1", LayerContribute1);
        waterMaterial.SetFloat("_LayerContribute2", LayerContribute2);
        waterMaterial.SetFloat("_LayerContribute3", LayerContribute3);

        waterMaterial.SetFloat("_NormalStrength", NormalStrength);
        waterMaterial.SetFloat("_HeightStrength", HeightStrength);
        waterMaterial.SetFloat("_VerticalDisplacementStrength", VerticalDisplacementStrength);
        waterMaterial.SetFloat("_HorizontalDisplacementStrength", HorizontalDisplacementStrength);
        waterMaterial.SetFloat("_CrestAmplification", CrestAmplification);

        waterMaterial.SetColor("_ScatterColor", ScatterColor);
        waterMaterial.SetColor("_ScatterPeakColor", ScatterPeakColor);
        waterMaterial.SetColor("_FoamColor", FoamColor);

        waterMaterial.SetFloat("_AmbientDensity", AmbientDensity);

        waterMaterial.SetFloat("_WavePeakScatterStrength", WavePeakScatterStrength);
        waterMaterial.SetFloat("_ScatterStrength", ScatterStrength);
        waterMaterial.SetFloat("_ScatterShadowStrength", ScatterShadowStrength);

        waterMaterial.SetFloat("_FoamRoughness", FoamRoughness);
        waterMaterial.SetFloat("_Roughness", Roughness);
        waterMaterial.SetFloat("_EnvirLightStrength", EnvirReflectStrength);

        waterMaterial.SetFloat("_EdgeFoamPower", EdgeFoamPower);
        waterMaterial.SetFloat("_ShadowIntensity", ShadowIntensity);

        waterMaterial.SetFloat("_VarMaskRange", VarMaskRange);
        waterMaterial.SetFloat("_VarMaskPower", VarMaskPower);
        waterMaterial.SetFloat("_VarMaskTexScale", VarMaskTexScale);

        waterMaterial.SetFloat("_FogDensity", FogDensity);
        waterMaterial.SetFloat("_FogPower", FogPower);
        waterMaterial.SetColor("_FogColor", FogColor);

        // Ukiyo-e style uniforms / 浮世绘风格参数
        waterMaterial.SetColor("_DeepInkColor", DeepInkColor);
        waterMaterial.SetColor("_MidWaterColor", MidWaterColor);
        waterMaterial.SetColor("_PaleWaterColor", PaleWaterColor);
        waterMaterial.SetColor("_FoamCreamColor", FoamCreamColor);
        waterMaterial.SetColor("_OutlineInkColor", OutlineInkColor);
        waterMaterial.SetFloat("_ToonBands", ToonBands);
        waterMaterial.SetFloat("_OutlineStrength", OutlineStrength);
        waterMaterial.SetFloat("_OutlineWidth", OutlineWidth);
        waterMaterial.SetFloat("_NprOutlineStrength", NprOutlineStrength);
        waterMaterial.SetFloat("_NprSilhouetteThreshold", NprSilhouetteThreshold);
        waterMaterial.SetFloat("_NprCreaseThreshold", NprCreaseThreshold);
        waterMaterial.SetFloat("_NprCreaseStrength", NprCreaseStrength);
        waterMaterial.SetFloat("_NprOutlineWidth", NprOutlineWidth);
        waterMaterial.SetFloat("_NprGrazeThreshold", NprGrazeThreshold);
        waterMaterial.SetFloat("_NprWaveEdgeStrength", NprWaveEdgeStrength);
        waterMaterial.SetFloat("_NprBandContourStrength", NprBandContourStrength);
        waterMaterial.SetFloat("_NprBandContourWidth", NprBandContourWidth);
        waterMaterial.SetFloat("_NprContourCount", NprContourCount);
        waterMaterial.SetFloat("_NprFoamOutlineStrength", NprFoamOutlineStrength);
        waterMaterial.SetFloat("_NprFoamOutlineWidth", NprFoamOutlineWidth);
        waterMaterial.SetFloat("_NprCrestOutlineStrength", NprCrestOutlineStrength);
        waterMaterial.SetFloat("_NprCrestOutlineThresh", NprCrestOutlineThresh);
        waterMaterial.SetFloat("_NprPaperStrength", NprPaperStrength);
        waterMaterial.SetFloat("_NprPaperScale", NprPaperScale);
        waterMaterial.SetFloat("_NprPaperFollow", NprPaperFollow);
        waterMaterial.SetFloat("_NprPaperWorld", NprPaperWorld);
        waterMaterial.SetFloat("_NprPaperWorldFreq", NprPaperWorldFreq);
        waterMaterial.SetFloat("_NprBokashiStrength", NprBokashiStrength);
        waterMaterial.SetFloat("_NprFoamProxyLo", NprFoamProxyLo);
        waterMaterial.SetFloat("_NprFoamProxyWidth", NprFoamProxyWidth);
        waterMaterial.SetFloat("_NprFoamNormalUp", NprFoamNormalUp);
        waterMaterial.SetFloat("_NprCreaseNFine", NprCreaseNFine);
        waterMaterial.SetFloat("_NprCreaseNThresh", NprCreaseNThresh);
        waterMaterial.SetFloat("_NprCreaseNStrength", NprCreaseNStrength);
        waterMaterial.SetFloat("_NprLodNear", NprLodNear);
        waterMaterial.SetFloat("_NprLodFar", NprLodFar);
        waterMaterial.SetFloat("_NprLodGamma", NprLodGamma);
        waterMaterial.SetFloat("_NprStrokeVary", NprStrokeVary);
        waterMaterial.SetFloat("_NprStrokeScale", NprStrokeScale);
        waterMaterial.SetFloat("_NprStrokeGap", NprStrokeGap);
        waterMaterial.SetFloat("_NprStrokeTaper", NprStrokeTaper);
        waterMaterial.SetFloat("_NprStrokeTaperHeight", NprStrokeTaperHeight);
        waterMaterial.SetFloat("_FoamCutoff", FoamCutoff);
        waterMaterial.SetFloat("_FoamEdgeSoftness", FoamEdgeSoftness);
        waterMaterial.SetFloat("_PrintMottle", PrintMottle);
        waterMaterial.SetFloat("_PrintLineStrength", PrintLineStrength);
        waterMaterial.SetFloat("_PrintLineScale", PrintLineScale);
        waterMaterial.SetFloat("_PrintLineFoamSuppression", PrintLineFoamSuppression);
        waterMaterial.SetFloat("_PrintStripeStrength", PrintStripeStrength);
        waterMaterial.SetFloat("_PrintStripeScale", PrintStripeScale);
        waterMaterial.SetFloat("_PrintStripeWarp", PrintStripeWarp);
        waterMaterial.SetFloat("_PrintStripeFaceGate", PrintStripeFaceGate);
        waterMaterial.SetFloat("_PrintStripeGateBright", PrintStripeGateBright);
        waterMaterial.SetFloat("_PrintStripeBokashi", PrintStripeBokashi);
        waterMaterial.SetFloat("_CrestWhiteBoost", CrestWhiteBoost);
        waterMaterial.SetFloat("_CrestWhiteThreshold", CrestWhiteThreshold);
        waterMaterial.SetFloat("_CrestLineStrength", CrestLineStrength);
        waterMaterial.SetFloat("_CrestCurlLineStrength", CrestCurlLineStrength);
        waterMaterial.SetFloat("_CrestCurlLineScale", CrestCurlLineScale);
        waterMaterial.SetFloat("_FoamContourStrength", FoamContourStrength);
        waterMaterial.SetFloat("_FoamContourScale", FoamContourScale);
        waterMaterial.SetFloat("_FoamScallopStrength", FoamScallopStrength);
        waterMaterial.SetFloat("_FoamScallopScale", FoamScallopScale);
        waterMaterial.SetFloat("_FoamPocketStrength", FoamPocketStrength);
        waterMaterial.SetFloat("_FoamCombStrength", FoamCombStrength);
        waterMaterial.SetFloat("_FoamCombScale", FoamCombScale);
        waterMaterial.SetFloat("_FoamStriationStrength", FoamStriationStrength);
        waterMaterial.SetFloat("_FoamStriationScale", FoamStriationScale);
        waterMaterial.SetFloat("_LightInfluence", LightInfluence);
        waterMaterial.SetFloat("_HeightShadeScale", HeightShadeScale);
        waterMaterial.SetFloat("_SteepShadeScale", SteepShadeScale);
        waterMaterial.SetFloat("_HokusaiDebugView", HokusaiDebugView);
    }

    // Allocates ocean meshes, materials, kernels, textures, and compute buffers when the component starts.
    void OnEnable()
    {
        ApplyFrameRateCap();
        CreateWaterSurface();
        CreateWaterMaterial();
        // Internal fixed resolution and compute dispatch dimensions.
        Resolusion = 1024;
        threadGroupsX = Mathf.CeilToInt(Resolusion / 8.0f);
        threadGroupsY = Mathf.CeilToInt(Resolusion / 8.0f);
        // Cache compute shader kernel indices once on startup.
        CS_InitializeSpectrum = FFTComputeShader.FindKernel("CS_InitializeSpectrum");
        CS_PackSpectrumConjugate = FFTComputeShader.FindKernel("CS_PackSpectrumConjugate");
        CS_UpdateSpectrum = FFTComputeShader.FindKernel("CS_UpdateSpectrum");
        CS_HorizontalIFFT = FFTComputeShader.FindKernel("CS_HorizontalIFFT");
        CS_VerticalIFFT = FFTComputeShader.FindKernel("CS_VerticalIFFT");
        CS_AssembleTextures = FFTComputeShader.FindKernel("CS_AssembleTextures");

        //创建贴图
        // Mips disabled: every shader samples these textures at LOD 0 and the mip chains were
        // never generated, so they only wasted ~60 MB of VRAM per play session.
        // 关闭 mipmap：所有采样都固定在 LOD 0，而且 mip 链从未被生成过，只会白白浪费显存。
        InitialSpectrumTexture = CreateRenderTexArray(Resolusion, Resolusion, 4, RenderTextureFormat.ARGBHalf, false);
        SpectrumTexture = CreateRenderTexArray(Resolusion, Resolusion, 8, RenderTextureFormat.ARGBHalf, false);
        DisplacementTexture = CreateRenderTexArray(Resolusion, Resolusion, 4, RenderTextureFormat.ARGBHalf, false);
        SlopeTexture = CreateRenderTexArray(Resolusion, Resolusion, 4, RenderTextureFormat.RGHalf, false);
        BuoyancyData     = CreateRenderTex(Resolusion, Resolusion, RenderTextureFormat.RHalf,     false);
        // ARGBHalf keeps enough precision for GPU-side crest scoring: R height, G slope, B crest, A final score.
        ClawMaskTexture  = CreateRenderTex(Resolusion, Resolusion, RenderTextureFormat.ARGBHalf,  false);
        VariationMask = CreateRenderTex(Resolusion, Resolusion, RenderTextureFormat.ARGBHalf, false);

        // Allocate the JONSWAP parameter buffer for eight spectrum settings.
        JonswapBuffer = new ComputeBuffer(8, 8 * sizeof(float));
        SetSpectrumBuffers();

        //赋值
        SetCompParam();

        // Force the initial spectrum to be computed on the first Update after every enable.
        _spectrumDirty = true;
    }

    // Caps the Play Mode frame rate so the GPU gets idle time each frame instead of
    // running flat-out (uncapped editor rendering is what pushes the PSU over its limit).
    // 限制 Play 模式帧率，让 GPU 每帧有空闲时间，避免编辑器不限帧导致电源过载。
    private void ApplyFrameRateCap()
    {
        if (!Application.isPlaying || playModeFrameRateCap <= 0)
            return;

        _prevVSyncCount = QualitySettings.vSyncCount;
        _prevTargetFrameRate = Application.targetFrameRate;
        QualitySettings.vSyncCount = 0;
        // Hardware-safety hard cap at 30 fps. The RTX 3080's microsecond transient power spikes are
        // what trip the PSU's over-current protection (the reboot). A lower frame rate gives the GPU
        // idle time every frame -> lower sustained utilization and temperature -> well under the trip
        // threshold (this matches the "rebooted after a while" thermal pattern). Raise this ONLY after
        // power-limiting the GPU in hardware (MSI Afterburner Power Limit ~70-80%).
        // 硬件安全：硬限 30fps。3080 的微秒级瞬时功耗尖峰才是触发电源过流保护(重启)的根因；
        // 降帧率让 GPU 每帧有空闲→持续占用和温度更低→远离触发阈值(对应你"过一会儿才重启"的热累积)。
        // 只有在硬件层面给 GPU 限功耗(Afterburner 功耗上限 ~70-80%)之后，才建议调高这个值。
        Application.targetFrameRate = Mathf.Clamp(playModeFrameRateCap, 1, 30);
    }

    // Restores frame pacing settings changed by ApplyFrameRateCap.
    private void RestoreFrameRateCap()
    {
        if (!Application.isPlaying || playModeFrameRateCap <= 0)
            return;

        QualitySettings.vSyncCount = _prevVSyncCount;
        Application.targetFrameRate = _prevTargetFrameRate;
    }

    // Hashes every setting that feeds CS_InitializeSpectrum so the expensive init pass
    // only re-runs when the user actually changes a JONSWAP parameter in the Inspector.
    // 对影响初始频谱的所有参数做哈希，只有在 Inspector 里改动参数时才重新执行初始化。
    private int HashSpectrumSettings()
    {
        unchecked
        {
            int h = 17;
            h = h * 31 + Seed;
            h = h * 31 + Gravity.GetHashCode();

            void Mix(in JONSWAP_DisplaySettings s)
            {
                h = h * 31 + s.scale.GetHashCode();
                h = h * 31 + s.windSpeed.GetHashCode();
                h = h * 31 + s.windDirection.GetHashCode();
                h = h * 31 + s.fetch.GetHashCode();
                h = h * 31 + s.spreadBlend.GetHashCode();
                h = h * 31 + s.swell.GetHashCode();
                h = h * 31 + s.peakEnhancement.GetHashCode();
                h = h * 31 + s.shortWavesFade.GetHashCode();
            }

            Mix(DisplaySpectrum0);
            Mix(DisplaySpectrum1);
            Mix(DisplaySpectrum2);
            Mix(DisplaySpectrum3);
            Mix(DisplaySpectrum4);
            Mix(DisplaySpectrum5);
            Mix(DisplaySpectrum6);
            Mix(DisplaySpectrum7);
            return h;
        }
    }

    // Runs the full FFT ocean simulation and publishes textures for water rendering and claw spawning.
    void Update()
    {
        //赋值
        SetCompParam();
        SetMaterialParam();

        // The spectrum init passes are deterministic for a given set of JONSWAP settings.
        // Dispatching them every frame doubled the GPU compute load; now they only run
        // on the first frame and when a relevant Inspector value changes.
        // 初始频谱对同一组 JONSWAP 参数是确定的。之前每帧都重新计算导致 GPU 负载翻倍；
        // 现在只在第一帧和 Inspector 参数变化时执行。
        int settingsHash = HashSpectrumSettings();
        if (_spectrumDirty || settingsHash != _spectrumSettingsHash)
        {
            _spectrumDirty = false;
            _spectrumSettingsHash = settingsHash;

            SetSpectrumBuffers();

            //初始化频谱
            FFTComputeShader.SetTexture(CS_InitializeSpectrum, "_InitialSpectrumTexture", InitialSpectrumTexture);
            FFTComputeShader.Dispatch(CS_InitializeSpectrum, threadGroupsX, threadGroupsY, 1);

            //共轭
            FFTComputeShader.SetTexture(CS_PackSpectrumConjugate, "_InitialSpectrumTexture", InitialSpectrumTexture);
            FFTComputeShader.Dispatch(CS_PackSpectrumConjugate, threadGroupsX, threadGroupsY, 1);
        }

        //为IFFT更新频谱
        FFTComputeShader.SetTexture(CS_UpdateSpectrum, "_InitialSpectrumTexture", InitialSpectrumTexture);
        FFTComputeShader.SetTexture(CS_UpdateSpectrum, "_SpectrumTexture", SpectrumTexture);
        FFTComputeShader.SetTexture(CS_UpdateSpectrum, "_VariationMask", VariationMask);
        FFTComputeShader.Dispatch(CS_UpdateSpectrum, threadGroupsX, threadGroupsY, 1);


        //海浪IFFT
        FFTComputeShader.SetTexture(CS_HorizontalIFFT, "_FourierTarget", SpectrumTexture);
        FFTComputeShader.SetTexture(CS_HorizontalIFFT, "_FourierTargetExtra", VariationMask);
        FFTComputeShader.Dispatch(CS_HorizontalIFFT, 1, Resolusion, 1);

        FFTComputeShader.SetTexture(CS_VerticalIFFT, "_FourierTarget", SpectrumTexture);
        FFTComputeShader.SetTexture(CS_VerticalIFFT, "_FourierTargetExtra", VariationMask);
        FFTComputeShader.Dispatch(CS_VerticalIFFT, 1, Resolusion, 1);


        //整合贴图
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_SpectrumTexture",     SpectrumTexture);
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_DisplacementTexture", DisplacementTexture);
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_SlopeTexture",        SlopeTexture);
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_BuoyancyData",        BuoyancyData);
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_VariationMask",       VariationMask);
        // The claw mask uses the same displacement and slope data as the visible ocean.
        // The claw mask uses the same displacement and slope data as the visible ocean.
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_ClawMaskTexture",     ClawMaskTexture);
        FFTComputeShader.Dispatch(CS_AssembleTextures, threadGroupsX, threadGroupsY, 1);

        //将结果传入Shader
        waterMaterial.SetTexture("_DisplacementTexture", DisplacementTexture);
        waterMaterial.SetTexture("_SlopeTexture", SlopeTexture);
        waterMaterial.SetTexture("_VariationMask", VariationMask);
        waterMaterial.SetTexture("_ClawMaskTexture", ClawMaskTexture);

        // Global fallback binding. The shader's Properties block is empty, so per-material
        // SetTexture can fail to bind these array textures (esp. in edit mode / on cloned
        // material instances). The shader reads global properties when a material override is
        // absent, so this guarantees the displacement/slope data reaches the water shader.
        // shader 的 Properties 块为空，逐材质 SetTexture 可能绑不上这些数组贴图；shader 会回退到
        // 全局属性，这里用全局兜底，保证位移/坡度数据一定送达水面 shader。
        Shader.SetGlobalTexture("_DisplacementTexture", DisplacementTexture);
        Shader.SetGlobalTexture("_SlopeTexture", SlopeTexture);
        Shader.SetGlobalTexture("_VariationMask", VariationMask);
        // ClawMaskTexture.b = crestScore = 1 - saturate(rawJacobian) = the instantaneous Tessendorf
        // breaking criterion; the water shader reads it to place white foam on the breaking lips.
        Shader.SetGlobalTexture("_ClawMaskTexture", ClawMaskTexture);
    }

    // Releases GPU buffers owned by the FFT ocean component.
    // Previously only JonswapBuffer was released; the seven 1024x1024 render textures leaked
    // (~200 MB of VRAM) every play session, adding GPU memory pressure on top of the load issues.
    // 之前只释放了 JonswapBuffer，七张 1024x1024 的 RenderTexture 每次 Play 都会泄漏约 200MB 显存。
    void OnDisable()
    {
        RestoreFrameRateCap();
        ReleaseResources();
    }

    void OnDestroy()
    {
        ReleaseResources();
    }

    private void ReleaseResources()
    {
        if (JonswapBuffer != null)
        {
            JonswapBuffer.Release();
            JonswapBuffer = null;
        }

        ReleaseRenderTexture(ref InitialSpectrumTexture);
        ReleaseRenderTexture(ref SpectrumTexture);
        ReleaseRenderTexture(ref DisplacementTexture);
        ReleaseRenderTexture(ref SlopeTexture);
        ReleaseRenderTexture(ref BuoyancyData);
        ReleaseRenderTexture(ref VariationMask);
        ReleaseRenderTexture(ref ClawMaskTexture);

        DestroyOwnedObject(ref waterMaterial);
        DestroyOwnedObject(ref waterSurface);
    }

    private static void ReleaseRenderTexture(ref RenderTexture rt)
    {
        if (rt == null)
            return;

        rt.Release();
        if (Application.isPlaying)
            Destroy(rt);
        else
            DestroyImmediate(rt);
        rt = null;
    }

    private static void DestroyOwnedObject<T>(ref T obj) where T : UnityEngine.Object
    {
        if (obj == null)
            return;

        if (Application.isPlaying)
            Destroy(obj);
        else
            DestroyImmediate(obj);
        obj = null;
    }
}
