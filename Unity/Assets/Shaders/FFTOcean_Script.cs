using System;
using System.Collections;
using System.Collections.Generic;
using static System.Runtime.InteropServices.Marshal;
using UnityEngine;
using UnityEngine.Rendering;

[RequireComponent (typeof(MeshFilter), typeof(MeshRenderer))]

public class FFTOcean_Script : MonoBehaviour
{

    // すべてのテクスチャを宣言する。
    public RenderTexture InitialSpectrumTexture,
                         SpectrumTexture,
                         DisplacementTexture,
                         SlopeTexture,
                         BuoyancyData,
                         VariationMask,
                         ClawMaskTexture;   // RGBA の順に高さ・傾斜・波頂・爪状白波の評価値を格納する。
    [Header("シェーダー")]
    public ComputeShader FFTComputeShader;
    public Shader FFTWaterShader;


    [Header("水面メッシュ設定")]

    public int waterMeshLength = 200;
    public int waterMeshRes = 10;

    [Range(10, 20)]
    public int TessEdgeLength = 16;
    private Mesh waterSurface;
    private Material waterMaterial;
    private int Resolusion, threadGroupsX, threadGroupsY;


    [Header("GPU の安全設定")]
    // エディターの Game ビューでは QualitySettings の垂直同期が効かず、Play モードが無制限に描画されることがある。
    // GPU 負荷と瞬間消費電力が大きくなり、RTX 3080 では電源保護による再起動が起き得る。
    // そのため Play モードのフレームレートに上限を設ける。
    // 0 は上限なし。電源保護動作の経験がある環境では推奨しない。
    [Tooltip("Play モードのフレームレート上限。無制限の GPU 負荷による電源保護動作を防ぐ。0 は無制限（非推奨）。")]
    public int playModeFrameRateCap = 60;

    [Header("一般設定")]
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


    [Header("レイヤー 01")]
    [Range(0.0f, 1.0f)]
    public float LayerContribute0 = 0.8f;
    [Range(0.0f, 0.25f)]
    public float Tile0 = 0.04f;

    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum0;
    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum1;

    private int LengthScale0 = 4;


    [Header("レイヤー 02")]
    [Range(0.0f, 1.0f)]
    public float LayerContribute1 = 0.8f;

    [Range(0.0f, 0.25f)]
    public float Tile1 = 0.06f;

    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum2;
    public JONSWAP_DisplaySettings DisplaySpectrum3;
    private int LengthScale1 = 4;


    [Header("レイヤー 03")]
    [Range(0.0f, 1.0f)]
    public float LayerContribute2 = 0.6f;

    [Range(0.0f, 0.25f)]
    public float Tile2 = 0.12f;

    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum4;
    public JONSWAP_DisplaySettings DisplaySpectrum5;
    private int LengthScale2 = 4;


    [Header("レイヤー 04")]
    [Range(0.0f, 1.0f)]
    public float LayerContribute3 = 0.4f;

    [Range(0.0f, 0.25f)]
    public float Tile3 = 0.18f;

    [SerializeField]
    public JONSWAP_DisplaySettings DisplaySpectrum6;
    public JONSWAP_DisplaySettings DisplaySpectrum7;
    private int LengthScale3 = 4;


    [Header("シェーダー設定")]
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

    [Header("荒波の形状")]
    // これらの値は表示される最終変位だけを変え、FFT スペクトル自体は変えない。
    // 波形の高さや尖りを調整するための表示用パラメータである。
    [Tooltip("実際のメッシュの鉛直変位を増幅し、波頂と谷の高さの差を大きくする。")]
    public float VerticalDisplacementStrength = 1.0f;
    [Tooltip("変位後の水面メッシュの水平方向の尖りを増幅する。")]
    public float HorizontalDisplacementStrength = 1.0f;
    [Tooltip("正の波頂を非線形にさらに持ち上げ、波を鋭く北斎風にする。")]
    public float CrestAmplification = 0.0f;

    [Space(10)]
    [Range(0.0f, 1.0f)]
    public float ShadowIntensity = 0.2f;


    [Header("泡の設定")]
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

    [Header("法線の変化")]
    [Range(0.01f, 10.0f)]
    public float VarMaskRange = 3.0f;
    [Range(0.01f, 10.0f)]
    public float VarMaskPower = 3.0f;
    [Range(0.01f, 10.0f)]
    public float VarMaskTexScale = 2.0f;

    // 爪状白波マスクの評価値を計算シェーダーに渡す。
    // FFT 計算シェーダーが ARGBHalf のマスクを書き、OceanClawGpuInstancer が使う。
    // OceanClawGpuInstancer はそのマスクを使って GPU 上で波頂を選別する。
    // R は高さ、G は傾斜、B は波頂、A は爪状白波の総合評価値。
    [Header("爪状白波のマスク（GPU 評価）")]
    [Tooltip("波高の評価値が 0 より大きくなる最小波高（m）。")]
    public float ClawHeightMin = 0.5f;
    [Tooltip("波高の評価値が 1.0 になる波高（m）。")]
    public float ClawHeightMax = 3.0f;
    [Tooltip("傾斜の評価値が 0 より大きくなる最小傾斜量。")]
    public float ClawSlopeMin  = 0.1f;
    [Tooltip("傾斜の評価値が 1.0 になる傾斜量。")]
    public float ClawSlopeMax  = 1.5f;

    // 北斎の「神奈川沖浪裏」に着想を得た浮世絵風の木版画色。
    // 実行時のマテリアルは FFTWaterShader から生成する。
    // そのため、スタイル用の各プロパティをここで公開し、SetMaterialParam で毎フレーム送る。
    // 色調整値は表示用であり、実行時に作ったマテリアルへ反映する。
    [Header("浮世絵風の色彩")]
    [Tooltip("谷の最も暗いプルシアンブルーの水色。")]
    public Color DeepInkColor = new Color(0.043f, 0.137f, 0.243f, 1f);
    [Tooltip("中間調の水色。")]
    public Color MidWaterColor = new Color(0.165f, 0.357f, 0.529f, 1f);
    [Tooltip("波頂付近の最も淡い水色。")]
    public Color PaleWaterColor = new Color(0.520f, 0.690f, 0.735f, 1f);
    [Tooltip("泡の形に使う、古紙の白に近い平坦なクリーム色。")]
    public Color FoamCreamColor = new Color(0.992f, 0.974f, 0.908f, 1f);
    [Tooltip("泡の形と色帯の境界を描く濃い藍色のインク。")]
    public Color OutlineInkColor = new Color(0.027f, 0.067f, 0.125f, 1f);
    [Space(6)]
    [Range(2, 6)]
    [Tooltip("木版画の重ね刷りのような、水面の平坦な色帯の数。")]
    public int ToonBands = 4;
    [Range(0f, 1f)]
    [Tooltip("濃いインクの輪郭線の強さ。")]
    public float OutlineStrength = 0.85f;
    [Range(0.005f, 0.2f)]
    [Tooltip("泡の形を囲むインク輪郭線の幅。")]
    public float OutlineWidth = 0.06f;
    [Header("浮世絵風の輪郭線（Brown & Arandjelovic, Sci 2020 §2.1）")]
    [Range(0f, 1.5f)]
    [Tooltip("波のシルエットと折れ目を描く主版輪郭線の全体的な強さ。")]
    public float NprOutlineStrength = 0.9f;
    [Range(0.0005f, 0.03f)]
    [Tooltip("深さの境界に基づくシルエット線の感度。下げると背後の水面に対する波頂をより多く描く。")]
    public float NprSilhouetteThreshold = 0.004f;
    [Range(0.02f, 0.7f)]
    [Tooltip("法線の境界に基づく折れ目線の感度。下げると表面の折れや砕ける縁をより多く描く。")]
    public float NprCreaseThreshold = 0.28f;
    [Range(0f, 1f)]
    [Tooltip("内側の折れ目線の強さ。シルエット輪郭線に対する相対値。")]
    public float NprCreaseStrength = 0.6f;
    [Range(0.5f, 4f)]
    [Tooltip("輪郭線の幅（画素）。")]
    public float NprOutlineWidth = 1.5f;
    [Range(0.2f, 0.85f)]
    [Tooltip("波頂の輪郭線を描く視線のかすめ角のしきい値。下げるとより多くの波面を描く。")]
    public float NprGrazeThreshold = 0.5f;
    [Range(0f, 1f)]
    [Tooltip("シェーダー内で描く波頂・稜線の輪郭線の強さ。")]
    public float NprWaveEdgeStrength = 0.85f;
    [Range(0f, 1f)]
    [Tooltip("波の形に沿う、木版画の色帯境界の太い輪郭線の強さ。")]
    public float NprBandContourStrength = 0.7f;
    [Range(0.02f, 0.5f)]
    [Tooltip("色帯境界の輪郭線の太さ。")]
    public float NprBandContourWidth = 0.15f;
    [Range(2f, 12f)]
    [Tooltip("水面の高さに沿う輪郭線の数。色帯の数とは独立しており、増やすと木版画風の波形線が密になる。")]
    public float NprContourCount = 6f;
    [Range(0f, 1f)]
    [Tooltip("白い泡の形の周囲に描く黒いインク輪郭線の強さ。")]
    public float NprFoamOutlineStrength = 1.0f;
    [Range(1f, 12f)]
    [Tooltip("泡の輪郭線の太さ（画素）。fwidth 正規化により境界の鋭さによらず一定幅となる。")]
    public float NprFoamOutlineWidth = 5.0f;
    [Range(0f, 1f)]
    [Tooltip("各うねりの局所的な最高線をなぞる、波頂稜線の強さ。")]
    public float NprCrestOutlineStrength = 0.85f;
    [Range(0.003f, 0.05f)]
    [Tooltip("波頂線の感度。下げると緩やかな波頂も拾うが斑点が増える。上げると強い波頂だけを拾う。")]
    public float NprCrestOutlineThresh = 0.013f;
    [Header("浮世絵風の墨・紙の粒子（論文 §2.2.1）")]
    [Range(0f, 0.4f)]
    [Tooltip("平坦な色面に重ねる、画面空間の木版画の墨・紙の粒子の強さ。")]
    public float NprPaperStrength = 0.10f;
    [Range(1.5f, 8f)]
    [Tooltip("ノイズ一セル当たりの画素数で示す粒子の大きさ。小さいほど細かい。")]
    public float NprPaperScale = 3.0f;
    [Range(0f, 4f)]
    [Tooltip("粒子が画面に固定されずシーンを追従する強さ。時間的一貫性に対応する（式 6～7）。")]
    public float NprPaperFollow = 1.0f;
    [Range(0f, 1f)]
    [Tooltip("紙の粒子をワールド座標の FFT 水面へ固定する度合い。1 は水とともに動き、0 は画面固定でカメラや水の移動時に泳いで見える。")]
    public float NprPaperWorld = 1.0f;
    [Range(0.05f, 12f)]
    [Tooltip("水面に固定した粒子のワールド空間周波数。高いほど細かいが、上げ過ぎると遠方でちらつく。")]
    public float NprPaperWorldFreq = 4.0f;
    [Header("浮世絵風のぼかし（論文 §2.2.3）")]
    [Range(0f, 1f)]
    [Tooltip("ぼかし。硬い色帯を滑らかな階調へ和らげる。0 は平坦な色帯、1 は完全に滑らか。")]
    public float NprBokashiStrength = 0.4f;
    [Header("泡の波頂シルエット線（視線と法線）")]
    [Range(0.01f, 0.6f)]
    [Tooltip("泡上のシルエット線の位置（n·v の等値線）。下げると真の外縁に近く線は疎になる。上げると広く描くが内側へ寄る。")]
    public float NprFoamProxyLo = 0.12f;
    [Range(0.4f, 0.85f)]
    [Tooltip("泡の高さによる輪郭線の制限。下げると波頂より下まで線が延び、上げ過ぎると線が途切れる。")]
    public float NprFoamProxyWidth = 0.62f;
    [Range(6f, 24f)]
    [Tooltip("シルエット判定に使う大まかな法線の平坦さ。上げると内部の偽線は減るが、線が疎になり急な波頂が必要になる。")]
    public float NprFoamNormalUp = 13f;
    [Header("細い折れ目線と距離別の詳細度")]
    [Range(0f, 1f)]
    [Tooltip("折れ目線に使う法線の細かさ。0 は滑らかな大まかな法線、1 は画素ごとの FFT 法線。上げると細部と斑点が増える。")]
    public float NprCreaseNFine = 0.5f;
    [Range(0.02f, 0.4f)]
    [Tooltip("折れ目線のしきい値。上げると鋭い折れだけに線を引き、線が少なく整う。")]
    public float NprCreaseNThresh = 0.16f;
    [Range(0f, 1.5f)]
    [Tooltip("細い折れ目線のインクの強さ。")]
    public float NprCreaseNStrength = 0.85f;
    [Range(0f, 300f)]
    [Tooltip("距離別の詳細度。これ以内のワールド距離では細い折れ目線が最大強度になる。")]
    public float NprLodNear = 40f;
    [Range(10f, 600f)]
    [Tooltip("距離別の詳細度。このワールド距離を超えると折れ目線が消え、遠方の斑点を抑える。")]
    public float NprLodFar = 160f;
    [Range(0.5f, 4f)]
    [Tooltip("距離別の詳細度の曲線。1 は線形、1 より大きいと近くで強く、中遠方で速く弱まる。")]
    public float NprLodGamma = 2f;
    [Header("版画の描線の筆致（論文 §2.1.6）")]
    [Range(0f, 1f)]
    [Tooltip("手描き風の描線に沿う墨の濃さの変化。0 は均一な線、1 は木版画らしい強い変化。")]
    public float NprStrokeVary = 0.4f;
    [Range(1f, 16f)]
    [Tooltip("描線内の墨の粒子の大きさ（画面上の画素）。小さいほど細かく途切れる。")]
    public float NprStrokeScale = 5f;
    [Range(0f, 0.6f)]
    [Tooltip("輪郭線を個々の筆致へ分ける強さ。0 は連続線、大きいほど切れ目が増える。")]
    public float NprStrokeGap = 0.12f;
    [Range(0f, 1f)]
    [Tooltip("高さに応じた線幅の先細り（Dadfar §5.1）。波頂で太く、谷へ向かって細く消す。0 は無効で均一な基準状態。")]
    public float NprStrokeTaper = 0f;
    [Range(0f, 0.7f)]
    [Tooltip("先細りが始まる高さの中点。下げると深い谷だけで消え、上げると高い波頂だけに線が残る。")]
    public float NprStrokeTaperHeight = 0.4f;
    [Range(0f, 1f)]
    [Tooltip("泡が現れる範囲のしきい値。下げるとクリーム色の泡の形が増える。")]
    public float FoamCutoff = 0.32f;
    [Range(0.01f, 0.5f)]
    [Tooltip("インク線の手前にある泡の形の縁の柔らかさ。")]
    public float FoamEdgeSoftness = 0.09f;
    [Range(0f, 1f)]
    [Tooltip("変化マスクによる木版画の印刷の色むら。")]
    public float PrintMottle = 0.35f;
    [Range(0f, 1f)]
    [Tooltip("水面の色帯を横切る、控えめな水平の墨繊維。")]
    public float PrintLineStrength = 0.16f;
    [Range(0.01f, 0.25f)]
    [Tooltip("水面の墨繊維のワールド空間での間隔。")]
    public float PrintLineScale = 0.065f;
    [Range(0f, 1f)]
    [Tooltip("クリーム色の泡が水面の墨繊維を抑える強さ。")]
    public float PrintLineFoamSuppression = 0.7f;
    [Range(0f, 1f)]
    [Tooltip("波壁を横切る、淡青色と濃青色の長い垂直な版の強さ。")]
    public float PrintStripeStrength = 0.38f;
    [Range(0.005f, 0.12f)]
    [Tooltip("垂直の水色版のワールド空間での間隔。小さいほど北斎風の幅広い色帯になる。")]
    public float PrintStripeScale = 0.12f;
    [Range(0f, 24f)]
    [Tooltip("垂直の色版が FFT の波高に応じて曲がる強さ。")]
    public float PrintStripeWarp = 1.20f;
    [Range(0f, 1f)]
    [Tooltip("明るい水面の色帯では縦縞を薄め、暗い部分に残す。0 は無効、1 は明部で完全に消す。")]
    public float PrintStripeFaceGate = 0.85f;
    [Range(0.2f, 0.95f)]
    [Tooltip("縦縞が薄くなる明るさの中点。下げると最暗部だけに残り、上げると明るい色帯まで残る。")]
    public float PrintStripeGateBright = 0.6f;
    [Range(0f, 1f)]
    [Tooltip("縦縞の明暗境界にかけるぼかし（§2.2.3）。0 は硬い櫛状の境界、1 は非常に柔らかい階調。")]
    public float PrintStripeBokashi = 0.5f;
    [Range(0f, 1f)]
    [Tooltip("爪状白波を生成する前に、高い波頂の縁へ追加する平坦なクリーム色。")]
    public float CrestWhiteBoost = 0.92f;
    [Range(0f, 1.5f)]
    [Tooltip("波頂の縁に白い泡の版を置くためのしきい値。")]
    public float CrestWhiteThreshold = 0.46f;
    [Range(0f, 1f)]
    [Tooltip("高く急な波頂面に追加する墨繊維。")]
    public float CrestLineStrength = 0.22f;
    [Range(0f, 1f)]
    [Tooltip("砕ける泡の下の青い波壁に描く、曲線状の木版画の線。")]
    public float CrestCurlLineStrength = 0.18f;
    [Range(0.01f, 0.25f)]
    [Tooltip("波壁の曲線状の線のワールド空間での間隔。")]
    public float CrestCurlLineScale = 0.055f;
    [Range(0f, 1f)]
    [Tooltip("クリーム色の泡の内部に入れる控えめなインク輪郭線。")]
    public float FoamContourStrength = 0.08f;
    [Range(0.01f, 0.3f)]
    [Tooltip("泡の内部輪郭線のワールド空間での間隔。")]
    public float FoamContourScale = 0.085f;
    [Range(0f, 1f)]
    [Tooltip("泡の縁の少し内側に入れる、短い波形の切れ目。")]
    public float FoamScallopStrength = 0.12f;
    [Range(0.01f, 0.3f)]
    [Tooltip("泡の波形の切れ目のワールド空間での間隔。")]
    public float FoamScallopScale = 0.115f;
    [Range(0f, 1f)]
    [Tooltip("クリーム色の泡の葉の間に残す、まばらな青い抜き形。北斎の彫り残した泡の隙間を表す。")]
    public float FoamPocketStrength = 0.06f;
    [Range(0f, 1f)]
    [Tooltip("急な泡の縁に入れる、北斎の泡の舌を思わせる短い櫛状の青い切れ目。")]
    public float FoamCombStrength = 0.08f;
    [Range(0.01f, 0.35f)]
    [Tooltip("波頂の泡に入れる櫛状の切れ目のワールド空間での間隔。")]
    public float FoamCombScale = 0.13f;
    [Range(0f, 1f)]
    [Tooltip("波頂の泡の内部に、彫りの流れに沿って入れる長めの途切れた墨筋。")]
    public float FoamStriationStrength = 0.07f;
    [Range(0.01f, 0.35f)]
    [Tooltip("細長い泡内の墨筋のワールド空間での間隔。")]
    public float FoamStriationScale = 0.075f;
    [Range(0f, 1f)]
    [Tooltip("実際の照明が色帯に影響する度合い。0 は完全に平坦な版画色。")]
    public float LightInfluence = 0.3f;
    [Range(0f, 2f)]
    [Tooltip("波高が色帯の位置を決める強さ。")]
    public float HeightShadeScale = 0.55f;
    [Range(0f, 2f)]
    [Tooltip("波面の急さに応じて色帯をインク色へ暗くする強さ。")]
    public float SteepShadeScale = 0.5f;
    [Range(0, 6)]
    [Tooltip("調査用マスク表示。0 は無効、1 は主波の領域、2 は波頂の縁、3 は元の泡・爪マスク、4 は連結した泡の評価値、5 は最終的な白マスク、6 は縞の影響。")]
    public int HokusaiDebugView = 0;

    [Header("霧の設定")]
    public Color FogColor = new Color(0.5f, 0.75f, 0.0f);

    [Range(0.0f, 20.0f)]
    public float FogDensity = 1.0f;
    [Range(0.0f, 10.0f)]
    public float FogPower = 4.0f;


    [System.Serializable]
    // 計算シェーダーへ渡す構造体。
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

    // 公開する設定から windSpeed と windDirection を使い、alpha、peakOmega、angle、gamma を動的に求める。
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
        // 8 組のスペクトル設定に使う JONSWAP パラメータバッファを確保する。
    private ComputeBuffer JonswapBuffer;

    // 主な関数の一覧。
    private int CS_InitializeSpectrum;
    private int CS_PackSpectrumConjugate;
    private int CS_UpdateSpectrum;
    private int CS_HorizontalIFFT;
    private int CS_VerticalIFFT;
    private int CS_AssembleTextures;

    // 初期スペクトルは JONSWAP 設定にのみ依存する。
    // その設定が変わった場合だけ再実行し、毎フレームの再初期化を避ける。
    // 毎フレーム計算すると GPU 負荷が無駄に約 2 倍となり、瞬間消費電力が増えていた。
    // JONSWAP パラメータが変わらない間は初期スペクトルを再利用する。
    // この処理は GPU 負荷と電源への負担を抑える。
    private int _spectrumSettingsHash;
    private bool _spectrumDirty = true;

    // 無効化時に Play モードのフレーム上限を戻すため、元の設定を保存する。
    private int _prevVSyncCount;
    private int _prevTargetFrameRate;


    // 浮力スクリプトが使う低負荷の高さ場を返す。
    // 浮力判定はこの高さ場を参照する。
    public RenderTexture GetBuoyancyData()   { return BuoyancyData; }

    // OceanClawGpuInstancer が使う GPU の爪状白波マスクを返す。
    // マスクには爪状白波の配置に使う評価値が入る。
    public RenderTexture GetClawMaskTexture() { return ClawMaskTexture; }

    // 既定値を設定する。
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

    // 水面メッシュを生成する。
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

        // 頂点座標、UV、接線を設定する。
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

        // 三角形を設定する。
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

    // 実行時の水面マテリアルを作成し、この GameObject の MeshRenderer に割り当てる。
    private void CreateWaterMaterial()
    {
        if (FFTWaterShader == null) return;

        waterMaterial = new Material(FFTWaterShader);

        MeshRenderer renderer = GetComponent<MeshRenderer>();

        renderer.material = waterMaterial;
    }

    //———————————————————————————————————————————————————————————————————————
    // 補助関数。

    // alpha の算出関数。
    float JonswapAlpha(float fetch, float windSpeed)
    {
        return 0.076f * Mathf.Pow(Gravity * fetch / windSpeed / windSpeed, -0.22f); // fetch と windSpeed から alpha を動的に計算する。参照資料の確認が必要。
    }

    // peakOmega の算出関数。
    float JonswapPeakFrequency(float fetch, float windSpeed)
    {
        return 22 * Mathf.Pow(windSpeed * fetch / Gravity / Gravity, -0.33f); // fetch と windSpeed から peakOmega を動的に計算する。参照資料の確認が必要。
    }

    // ユーザーの設定値を構造体に渡す。
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

    // バッファを作成し、設定値を転送する。
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

    // テクスチャを作成して設定する。
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

    // FFT 処理で使う、書き込み可能な二次元レンダーテクスチャを作成する。
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

    // 爪状白波マスクの評価しきい値を含む定数を FFT 計算シェーダーへ送る。
    // 計算シェーダーで使う波高・傾斜などの設定値を更新する。
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

        // 爪状白波マスクの評価値。ClawMaskTexture のみを変える。生成後の保持は OceanClawGpuInstancer が管理する。
        // 爪状白波の配置や寿命そのものは、ここでは制御しない。
        FFTComputeShader.SetFloat("_ClawHeightMin", ClawHeightMin);
        FFTComputeShader.SetFloat("_ClawHeightMax", ClawHeightMax);
        FFTComputeShader.SetFloat("_ClawSlopeMin",  ClawSlopeMin);
        FFTComputeShader.SetFloat("_ClawSlopeMax",  ClawSlopeMax);
    }

    // 毎フレームのマテリアル値を送り、表示する海面を計算シェーダーの変位テクスチャに合わせる。
    // 変位と傾斜のテクスチャを使った描画設定を更新する。
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

        // 浮世絵風の描画に使うシェーダー定数。
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

    // コンポーネントの起動時に海面メッシュ、マテリアル、カーネル、テクスチャ、計算バッファを確保する。
    void OnEnable()
    {
        ApplyFrameRateCap();
        CreateWaterSurface();
        CreateWaterMaterial();
        // 内部で固定する解像度と計算シェーダーのディスパッチ寸法。
        Resolusion = 1024;
        threadGroupsX = Mathf.CeilToInt(Resolusion / 8.0f);
        threadGroupsY = Mathf.CeilToInt(Resolusion / 8.0f);
        // 起動時に計算シェーダーのカーネル番号を取得して保持する。
        CS_InitializeSpectrum = FFTComputeShader.FindKernel("CS_InitializeSpectrum");
        CS_PackSpectrumConjugate = FFTComputeShader.FindKernel("CS_PackSpectrumConjugate");
        CS_UpdateSpectrum = FFTComputeShader.FindKernel("CS_UpdateSpectrum");
        CS_HorizontalIFFT = FFTComputeShader.FindKernel("CS_HorizontalIFFT");
        CS_VerticalIFFT = FFTComputeShader.FindKernel("CS_VerticalIFFT");
        CS_AssembleTextures = FFTComputeShader.FindKernel("CS_AssembleTextures");

        // テクスチャを作成する。
        // mipmap を無効にする。すべてのシェーダーがこれらのテクスチャを LOD 0 で参照し、
        // mipmap は生成されないため、Play ごとに約 60 MB の VRAM を無駄に消費していた。
        // LOD 0 以外を使わないため、不要な mipmap を作成しない。
        InitialSpectrumTexture = CreateRenderTexArray(Resolusion, Resolusion, 4, RenderTextureFormat.ARGBHalf, false);
        SpectrumTexture = CreateRenderTexArray(Resolusion, Resolusion, 8, RenderTextureFormat.ARGBHalf, false);
        DisplacementTexture = CreateRenderTexArray(Resolusion, Resolusion, 4, RenderTextureFormat.ARGBHalf, false);
        SlopeTexture = CreateRenderTexArray(Resolusion, Resolusion, 4, RenderTextureFormat.RGHalf, false);
        BuoyancyData     = CreateRenderTex(Resolusion, Resolusion, RenderTextureFormat.RHalf,     false);
        // ARGBHalf の精度で GPU 側の波頭評価値を保持する。R は波高、G は傾斜、B は波頭、A は最終評価値。
        ClawMaskTexture  = CreateRenderTex(Resolusion, Resolusion, RenderTextureFormat.ARGBHalf,  false);
        VariationMask = CreateRenderTex(Resolusion, Resolusion, RenderTextureFormat.ARGBHalf, false);

        // 8 組のスペクトル設定に使う JONSWAP パラメータバッファを確保する。
        JonswapBuffer = new ComputeBuffer(8, 8 * sizeof(float));
        SetSpectrumBuffers();

        // 値を設定する。
        SetCompParam();

        // 有効化のたびに、最初の Update で初期スペクトルを計算させる。
        _spectrumDirty = true;
    }

    // Play モードのフレームレートに上限を設け、GPU に毎フレームの空き時間を与える。
    // 編集画面で上限なしに描画すると、電源への負荷が大きくなる。
    // フレームレートを制限して、GPU の連続稼働を抑える。
    private void ApplyFrameRateCap()
    {
        if (!Application.isPlaying || playModeFrameRateCap <= 0)
            return;

        _prevVSyncCount = QualitySettings.vSyncCount;
        _prevTargetFrameRate = Application.targetFrameRate;
        QualitySettings.vSyncCount = 0;
        // ハードウェア保護のため 30 fps を上限にする。RTX 3080 の瞬間的な消費電力が
        // 電源の過電流保護を作動させる可能性がある。フレームレートを下げると GPU に
        // 毎フレームの空き時間が生まれ、継続的な使用率と温度を下げられる。
        // 再起動の原因は未確定のため、この上限は保守的な対策として扱う。
        // 上限を上げる場合は、まず GPU の電力制限などを確認する。
        // 30 fps の固定上限は、突然の再起動を避けるための暫定的な保護策。
        // GPU の負荷と温度を抑える狙いがあるが、再起動の原因は検証できていない。
        // 上限を引き上げる前に、ハードウェア側の電力制限（例：Afterburner の 70～80%）を確認する。
        Application.targetFrameRate = Mathf.Clamp(playModeFrameRateCap, 1, 30);
    }

    // ApplyFrameRateCap で変更したフレーム制御設定を元に戻す。
    private void RestoreFrameRateCap()
    {
        if (!Application.isPlaying || playModeFrameRateCap <= 0)
            return;

        QualitySettings.vSyncCount = _prevVSyncCount;
        Application.targetFrameRate = _prevTargetFrameRate;
    }

    // CS_InitializeSpectrum に渡す各設定値をハッシュ化し、計算負荷の高い初期化を
    // Inspector で JONSWAP パラメータが実際に変わった場合だけ再実行する。
    // 初期スペクトルに影響する設定が変わらない限り、再初期化を省く。
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

    // FFT による海面シミュレーションを実行し、描画と爪状白波の生成に使うテクスチャを公開する。
    void Update()
    {
        // 値を設定する。
        SetCompParam();
        SetMaterialParam();

        // 同じ JONSWAP 設定から計算する初期スペクトルは決定的に定まる。
        // 以前は毎フレーム初期化して GPU の計算負荷を増やしていたため、
        // 現在は最初のフレームと関連する Inspector の値が変わったときだけ実行する。
        // 同じ JONSWAP 設定なら初期スペクトルを再利用できる。
        // Inspector の設定が変わった場合だけ初期化する。
        int settingsHash = HashSpectrumSettings();
        if (_spectrumDirty || settingsHash != _spectrumSettingsHash)
        {
            _spectrumDirty = false;
            _spectrumSettingsHash = settingsHash;

            SetSpectrumBuffers();

            // 初期スペクトルを計算する。
            FFTComputeShader.SetTexture(CS_InitializeSpectrum, "_InitialSpectrumTexture", InitialSpectrumTexture);
            FFTComputeShader.Dispatch(CS_InitializeSpectrum, threadGroupsX, threadGroupsY, 1);

            // 共役成分を計算する。
            FFTComputeShader.SetTexture(CS_PackSpectrumConjugate, "_InitialSpectrumTexture", InitialSpectrumTexture);
            FFTComputeShader.Dispatch(CS_PackSpectrumConjugate, threadGroupsX, threadGroupsY, 1);
        }

        // IFFT 用のスペクトルを更新する。
        FFTComputeShader.SetTexture(CS_UpdateSpectrum, "_InitialSpectrumTexture", InitialSpectrumTexture);
        FFTComputeShader.SetTexture(CS_UpdateSpectrum, "_SpectrumTexture", SpectrumTexture);
        FFTComputeShader.SetTexture(CS_UpdateSpectrum, "_VariationMask", VariationMask);
        FFTComputeShader.Dispatch(CS_UpdateSpectrum, threadGroupsX, threadGroupsY, 1);


        // 海面の IFFT を実行する。
        FFTComputeShader.SetTexture(CS_HorizontalIFFT, "_FourierTarget", SpectrumTexture);
        FFTComputeShader.SetTexture(CS_HorizontalIFFT, "_FourierTargetExtra", VariationMask);
        FFTComputeShader.Dispatch(CS_HorizontalIFFT, 1, Resolusion, 1);

        FFTComputeShader.SetTexture(CS_VerticalIFFT, "_FourierTarget", SpectrumTexture);
        FFTComputeShader.SetTexture(CS_VerticalIFFT, "_FourierTargetExtra", VariationMask);
        FFTComputeShader.Dispatch(CS_VerticalIFFT, 1, Resolusion, 1);


        // 計算結果をテクスチャにまとめる。
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_SpectrumTexture",     SpectrumTexture);
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_DisplacementTexture", DisplacementTexture);
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_SlopeTexture",        SlopeTexture);
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_BuoyancyData",        BuoyancyData);
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_VariationMask",       VariationMask);
        // 爪状白波マスクには、表示中の海面と同じ変位と傾斜のデータを使う。
        // これにより、白波の配置を表示中の海面形状に合わせる。
        FFTComputeShader.SetTexture(CS_AssembleTextures, "_ClawMaskTexture",     ClawMaskTexture);
        FFTComputeShader.Dispatch(CS_AssembleTextures, threadGroupsX, threadGroupsY, 1);

        // 計算結果をシェーダーへ渡す。
        waterMaterial.SetTexture("_DisplacementTexture", DisplacementTexture);
        waterMaterial.SetTexture("_SlopeTexture", SlopeTexture);
        waterMaterial.SetTexture("_VariationMask", VariationMask);
        waterMaterial.SetTexture("_ClawMaskTexture", ClawMaskTexture);

        // 全体設定による代替の割り当てを行う。シェーダーの Properties ブロックは空なので、
        // マテリアルごとの SetTexture では配列テクスチャを割り当てられない場合がある。
        // 特に編集モードや複製されたマテリアルで生じ得る。マテリアル側に設定がなければ、
        // シェーダーは全体設定を参照し、変位と傾斜のデータを海面描画へ渡せる。
        // Properties ブロックが空の場合に備え、全体設定にもテクスチャを登録する。
        // これにより、海面シェーダーが変位と傾斜のデータを参照できる。
        Shader.SetGlobalTexture("_DisplacementTexture", DisplacementTexture);
        Shader.SetGlobalTexture("_SlopeTexture", SlopeTexture);
        Shader.SetGlobalTexture("_VariationMask", VariationMask);
        // ClawMaskTexture.b = crestScore = 1 - saturate(rawJacobian) は Tessendorf の
        // 瞬時の砕波判定値。海面シェーダーはこれを使って砕波部分へ白泡を置く。
        Shader.SetGlobalTexture("_ClawMaskTexture", ClawMaskTexture);
    }

    // FFT 海面コンポーネントが所有する GPU バッファを解放する。
    // 以前は JonswapBuffer だけが解放され、7 枚の 1024×1024 レンダーテクスチャが
    // Play ごとに解放されず、約 200 MB の VRAM を消費し続けていた。
    // すべてのレンダーテクスチャを解放して GPU メモリの使用量を抑える。
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
