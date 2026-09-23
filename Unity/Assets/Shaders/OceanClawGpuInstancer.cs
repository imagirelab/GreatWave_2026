using UnityEngine;

/// <summary>
/// FFT 海面を走査して GPU 上で北斎風の爪状白波を生成し、間接描画する。
/// 爪状白波ごとの GameObject は作らず、メッシュのインスタンスを描画する。
/// GPU 上で生成位置と描画数を管理する。
/// </summary>
[DefaultExecutionOrder(100)]
public partial class OceanClawGpuInstancer : MonoBehaviour
{
    private const int InstanceStride = sizeof(float) * 4 * 5;
    private const int IndirectArgsCount = 5;
    private const int CellStateStride = sizeof(float) * 4;
    private const int GenerateThreadGroupSize = 8;

    [Header("参照")]
    public FFTOcean_Script oceanScript;
    public ComputeShader clawInstancingCompute;
    public Mesh clawMesh;
    public Material clawMaterial;

    [Header("生成設定")]
    public bool enableGpuClaws = true;
    [Range(8, 96)]
    public int scanGridSize = 44;
    [Range(1, 1024)]
    public int maxInstances = 360;
    [Range(0f, 1f)]
    public float scoreThreshold = 0.48f;
    [Range(0f, 1f)]
    public float spawnDensity = 0.18f;
    public float worldHeightThreshold = 4.60f;
    public float worldHeightFeather = 1.85f;
    public int randomSeed = 6128;

    [Header("表示範囲の焦点")]
    [Tooltip("限られた GPU インスタンス数を、カメラに見える海面の近くへ集中させる。")]
    public bool focusSpawnsNearCamera = true;
    [Tooltip("爪状白波の生成範囲の中心と前方向を決める任意の Transform。空欄なら Camera.main を使う。")]
    public Transform spawnFocus;
    public float focusDistance = 95f;
    public float focusRadius = 220f;
    public float focusFeather = 90f;

    [Header("北斎の構図")]
    [Tooltip("「神奈川沖浪裏」の構図に近づけるため、主波頭と小さな副波頭の周辺へ生成を集中させる。")]
    public bool useCompositionBias = true;
    [Range(0f, 1f)]
    public float compositionStrength = 0.82f;
    [Tooltip("焦点中心から見た主波頭の中心。X は波頭に沿う左右方向、Y は波の進行方向。")]
    public Vector2 mainCrestOffset = new Vector2(18f, 32f);
    [Tooltip("主波頭の楕円形領域の半径。X は左右の幅、Y は前後の奥行き。")]
    public Vector2 mainCrestRadius = new Vector2(28f, 18f);
    [Range(0f, 2.5f)]
    public float mainCrestBoost = 1.75f;
    [Tooltip("焦点中心から見た副波頭の中心。X は波頭に沿う左右方向、Y は波の進行方向。")]
    public Vector2 sideCrestOffset = new Vector2(22f, -35f);
    [Tooltip("副波頭の楕円形領域の半径。X は左右の幅、Y は前後の奥行き。")]
    public Vector2 sideCrestRadius = new Vector2(18f, 12f);
    [Range(0f, 2.5f)]
    public float sideCrestBoost = 0.65f;
    [Range(0f, 1f)]
    public float backgroundCrestFloor = 0.30f;
    [Tooltip("主波頭と副波頭の楕円形領域の外側に適用する生成密度倍率。小さい値ほど背景の白泡を減らせる。")]
    [Range(0f, 1f)]
    public float backgroundDensityScale = 0.08f;
    [Tooltip("主波頭と副波頭の外側にある爪状白波の大きさの倍率。背景の波頭を構図の脇役にする。")]
    [Range(0.1f, 1f)]
    public float backgroundClawScale = 0.42f;
    [Tooltip("主波頭を塊状ではなく、「神奈川沖浪裏」に近い湾曲した帯状に整える。")]
    public bool useReferenceCrestArc = true;
    [Tooltip("主波頭が参照円弧のマスクに従う強さ。")]
    [Range(0f, 1f)]
    public float referenceArcStrength = 0.85f;
    [Tooltip("円弧中心の進行方向への持ち上げ量。正の値で波頭の帯の中央が高くなる。")]
    public float referenceArcForwardBend = 18f;
    [Tooltip("円弧の斜め方向への曲がり。値の符号で白波の帯が傾く方向が変わる。")]
    public float referenceArcCurl = -10f;
    [Tooltip("参照円弧の帯の半幅（ワールド座標のメートル）。")]
    [Range(0.5f, 30f)]
    public float referenceArcWidth = 7f;
    [Tooltip("参照円弧の帯の外側へ向かう減衰の滑らかさ。")]
    [Range(0.5f, 30f)]
    public float referenceArcFeather = 8f;
    [Tooltip("参照円弧に沿う専用サンプリングの偏り。負の値は巻き込む肩側、正の値は後方側を優先する。")]
    [Range(-1f, 1f)]
    public float referenceArcDensityBias = -0.25f;
    [Tooltip("参照円弧の密集した巻き込み部を大きくし、白泡を強調する。")]
    [Range(0f, 1f)]
    public float referenceArcShoulderSizeBoost = 0.28f;
    [Tooltip("巻き込み部をやや早めに展開させつつ、生存時間による成長曲線を維持する。")]
    [Range(0f, 1f)]
    public float referenceArcShoulderOpenBoost = 0.22f;
    [Tooltip("参照円弧が「神奈川沖浪裏」風の大きさと出現順序を決める強さ。")]
    [Range(0f, 1f)]
    public float hokusaiArcProfileStrength = 0.72f;
    [Tooltip("円弧の密集した巻き込み部をさらに幅広くする。")]
    [Range(0f, 1.5f)]
    public float hokusaiCurlShoulderBoost = 0.42f;
    [Tooltip("白泡の円弧の後方側に適用する大きさの倍率。")]
    [Range(0.1f, 1f)]
    public float hokusaiTailScale = 0.52f;
    [Tooltip("白泡の指が順番に開くよう、後方側の生存時間に追加する遅延。")]
    [Range(0f, 0.5f)]
    public float hokusaiTailRevealDelay = 0.18f;
    [Tooltip("北斎の参照円弧に沿って、大きな肩の張り出し、小さな内側の突起、後方の隙間を交互に配置する。")]
    [Range(0f, 1f)]
    public float hokusaiArcLobeContrast = 0.42f;
    [Tooltip("参照円弧の小さな白泡の突起を描画バッファに長く残し、突然消さずに不透明度でフェードさせる。")]
    [Range(0f, 1f)]
    public float hokusaiWeakToothRetention = 0.62f;
    [Tooltip("カメラ画面上の円弧マスクを追加し、主波頭の画面構図を安定させる。")]
    public bool useScreenReferenceMask = true;
    [Tooltip("画面上の参照円弧が主波頭の分布に影響する強さ。")]
    [Range(0f, 1f)]
    public float screenReferenceStrength = 0.32f;
    [Tooltip("画面に見える参照円弧の中心。X と Y は正規化した画面座標。")]
    public Vector2 screenReferenceCenter = new Vector2(0.62f, 0.56f);
    [Tooltip("画面上の参照円弧の半幅（正規化した画面座標）。")]
    [Range(0.02f, 0.8f)]
    public float screenReferenceHalfWidth = 0.24f;
    [Tooltip("画面上の参照円弧の縦方向の曲がり（正規化した画面座標）。")]
    [Range(-0.4f, 0.4f)]
    public float screenReferenceBend = 0.08f;
    [Tooltip("画面上の参照円弧の斜めの傾き（正規化した画面座標）。")]
    [Range(-0.4f, 0.4f)]
    public float screenReferenceTilt = -0.03f;
    [Tooltip("画面上の参照円弧の帯の半厚。")]
    [Range(0.005f, 0.3f)]
    public float screenReferenceThickness = 0.08f;
    [Tooltip("画面上の参照円弧の帯の境界をぼかす幅。")]
    [Range(0.005f, 0.3f)]
    public float screenReferenceFeather = 0.10f;
    [Tooltip("構図マスクを世界座標に固定せず、移動する波頭に合わせて流す。")]
    public bool driftCompositionWithCrests = true;
    [Tooltip("構図マスクが主な波の進行方向へ移動する速度（メートル毎秒）。")]
    public float compositionDriftSpeed = 4.4f;
    [Tooltip("移動する構図マスクを、画面上の焦点へ引き戻す速さ。")]
    [Range(0f, 4f)]
    public float compositionReturnRate = 0.45f;
    [Tooltip("構図の中心がカメラの焦点から離れられる XZ 平面上の最大距離。")]
    public float compositionMaxDriftFromFocus = 42f;
    [Tooltip("生成範囲の焦点マスクが、移動する構図の中心に追従する割合。")]
    [Range(0f, 1f)]
    public float compositionFocusGateFollow = 0.90f;
    [Tooltip("主波頭の領域内で追加する走査密度の倍率。")]
    [Range(0f, 5f)]
    public float mainCrestDensityBoost = 1.55f;
    [Tooltip("小さな副波頭の領域内で追加する走査密度の倍率。")]
    [Range(0f, 5f)]
    public float sideCrestDensityBoost = 0.4f;
    [Tooltip("主波頭の領域内で追加する波頭の探索半径。")]
    [Range(0f, 2f)]
    public float mainCrestSearchBoost = 0.75f;
    [Tooltip("小さな副波頭の領域内で追加する波頭の探索半径。")]
    [Range(0f, 2f)]
    public float sideCrestSearchBoost = 0.35f;
    [Tooltip("海全体の無作為な走査に先立ち、主波頭の楕円形領域へ割り当てる走査セルの割合。")]
    [Range(0f, 0.75f)]
    public float mainCrestDedicatedScanShare = 0.030f;
    [Tooltip("小さな副波頭の楕円形領域へ割り当てる走査セルの割合。")]
    [Range(0f, 0.35f)]
    public float sideCrestDedicatedScanShare = 0.005f;

    [Header("海面との連動")]
    public float verticalDisplacementStrength = 4.2f;
    public float horizontalDisplacementStrength = 1.85f;
    public float crestAmplification = 0.17f;
    public float crestProbeDistance = 8.5f;
    public float crestHeightBias = 0.08f;
    public float crestHeightRange = 1.05f;
    [Tooltip("各生成位置から、動く波頭を見つけて追従するために前後へ探索する距離。")]
    public float crestSearchRadius = 9.0f;
    [Tooltip("各生成位置から、波頭の線に沿って左右へ探索する距離。")]
    public float crestSearchLateral = 5.5f;

    [Header("持続時間")]
    [Tooltip("波頭を検出してから、新しい爪状白波が最大の大きさへ育つまでの秒数。")]
    public float lifeRiseTime = 2.3f;
    [Tooltip("波頭がしきい値を下回ってから、爪状白波が縮んで消えるまでの秒数。")]
    public float lifeFallTime = 16.0f;
    [Range(0f, 1f)]
    public float visibleLifeThreshold = 0.035f;
    [Range(0f, 0.1f)]
    [Tooltip("消失時の描画を続ける低いしきい値。Visible Life Threshold より低くし、インスタンスが突然消えないようにする。")]
    public float drawLifeThreshold = 0.006f;

    [Header("波頭への追従")]
    [Tooltip("生きている爪状白波の基点が主波方向へ移動する速度（m/s）。見える波の速度におおむね合わせる。")]
    public float crestDriftSpeed = 4.4f;
    [Tooltip("移動中の基点を新たに見つけた波頭へ合わせ直す速さ（1/s）。小さいと滑らかだが遅れ、大きいと正確だが揺れやすい。")]
    public float crestRelockRate = 1.6f;
    [Tooltip("爪状白波の下の波頭が崩れた後、生存値が下がる速さの倍率。白波が波とともに消えるようにする。")]
    public float crestLostFallBoost = 1.10f;

    [Header("自然な配置")]
    [Tooltip("簇の各要素が直線状の横列より湾曲した波頭の稜線へ沿う強さ（0～1）。")]
    [Range(0f, 1f)]
    public float crestCurveFollow = 1.0f;
    [Tooltip("簇の各要素を指のように外側へ扇形に広げる角度（簇全体の度数）。")]
    [Range(0f, 60f)]
    public float clusterFanDegrees = 38f;
    [Tooltip("爪状白波の根元を、その高さに対する指定割合だけ波の中へ沈める。")]
    [Range(0f, 0.4f)]
    public float rootEmbedFraction = 0.012f;
    [Tooltip("根元が波頭につながったまま見えるようにする小さなワールド座標上の持ち上げ量。X は折り畳み時、Y は展開時。")]
    public Vector2 rootLiftRangeMeters = new Vector2(0.18f, 0.45f);
    [Tooltip("根元を波の中へ沈める最大の深さ（メートル）。大きなモデルを埋めすぎないよう、モデルの倍率ではなく距離で制限する。")]
    [Range(0f, 1f)]
    public float rootEmbedMaxMeters = 0.12f;
    [Tooltip("簇の中で中央を大きく両端を小さくする強さ（0～1）。1 は絵に近い大きさの差、0 は同じ大きさ。")]
    [Range(0f, 1f)]
    public float sizeHierarchy = 0.92f;
    [Tooltip("各簇の中央を波の先端より前へ押し出し、平らな列ではなく北斎風の湾曲した波頭を作る。")]
    [Range(0f, 12f)]
    public float clusterArcForwardOffset = 5.0f;
    [Tooltip("主波頭の簇の中にある要素を、左右へさらに広げる。")]
    [Range(1f, 2.5f)]
    public float mainFanLateralScale = 1.45f;
    [Tooltip("主波頭の簇の中にある要素を、円弧に沿って進行方向へさらに広げる。")]
    [Range(1f, 2f)]
    public float mainFanForwardScale = 1.22f;
    [Tooltip("主波頭の簇の中にある要素を、外側へさらに扇形に回転させる。")]
    [Range(0f, 1.5f)]
    public float mainFanYawBoost = 0.45f;
    [Tooltip("主波頭の各要素を画面上の参照円弧へ引き戻し、白泡の先端が連続した帯として読めるようにする。")]
    [Range(0f, 1f)]
    public float mainMemberScreenArcFollow = 0.0f;
    [Tooltip("主波頭の爪状白波を波面に沿って寝かせ、先端が立った物体ではなく白泡に見えるようにする。")]
    [Range(0f, 1f)]
    public float foamSheetFlatten = 0.42f;
    [Tooltip("寝かせた主波頭の白泡の先端を幅と奥行きへ広げ、縦の物体感を抑えながら面積を保つ。")]
    [Range(0f, 1f)]
    public float foamSheetWidthBoost = 0.35f;

    [Header("波頭の簇")]
    [Range(1, 12)]
    public int minClawsPerCrest = 3;
    [Range(1, 12)]
    public int maxClawsPerCrest = 10;
    [Tooltip("主な参照円弧のセルから生成する要素数を制限し、インスタンスを円弧全体へ分散させる。")]
    [Range(2, 12)]
    public int maxRibbonClawsPerCrest = 4;
    public float clusterLateralSpacing = 5.8f;
    public float clusterForwardJitter = 2.7f;
    public float clusterVerticalJitter = 0.16f;
    [Range(0f, 2f)]
    public float clusterLateralRandomness = 0.75f;
    [Range(0f, 2f)]
    public float clusterForwardRandomness = 0.90f;

    [Header("爪状白波の形状")]
    public Vector2 clawScaleRange = new Vector2(125f, 345f);
    public Vector3 clawScaleMultiplier = new Vector3(2.05f, 0.22f, 1.05f);
    [Range(0f, 0.75f)]
    public float scaleRandomness = 0.38f;
    [Tooltip("検出した波頭から爪状白波の根元を少し持ち上げる。メッシュの基点は波頭へ追従させる。")]
    public float verticalOffset = 0.12f;
    public bool localYPointsTowardTip = false;
    [Range(0f, 1f)]
    public float forwardFromSlope = 0.0f;
    [Range(0f, 90f)]
    public float yawJitterDegrees = 11f;
    [Range(0f, 4f)]
    public float normalInfluence = 1.55f;
    [Tooltip("爪状白波の向きが動く水面の法線へ従う強さ。目立つ回転を防ぐには低く保つ。")]
    [Range(0f, 1f)]
    public float surfaceNormalBlend = 0.0f;
    [Tooltip("外側へ向いた先端を水平から波面の方へ垂らす強さ。")]
    [Range(0f, 1.5f)]
    public float tipDownwardBias = 0.30f;

    [Header("成長アニメーション")]
    [Tooltip("波頭の形成中または崩壊中に、爪状白波を波の中へ折り戻す距離。")]
    [Range(0f, 120f)]
    public float growthFoldDegrees = 96f;
    [Tooltip("爪状白波が現れ始めたときのモデルの最小倍率。")]
    [Range(0.01f, 0.6f)]
    public float growthMinScale = 0.08f;
    [Tooltip("値が大きいほど、成長初期の回転が隠れた状態に長く留まる。")]
    [Range(0.2f, 4f)]
    public float growthCurvePower = 2.7f;
    [Tooltip("簇内の各爪状白波に与える遅延のばらつき。順番に展開するようにする。")]
    [Range(0f, 0.85f)]
    public float growthStagger = 0.58f;
    [Tooltip("画面上の主な白泡の帯の最低展開量。波高のピーク間で小さな点へ縮むのを防ぐ。")]
    [Range(0f, 1f)]
    public float ribbonOpenFloor = 0.34f;
    [Tooltip("主な参照円弧上の無作為な展開遅延を減らし、段階的な成長を保ちながら連続した波頭に見せる。")]
    [Range(0f, 1f)]
    public float ribbonDelayCompression = 0.55f;
    [Tooltip("爪状白波が完全に展開できるまでに必要な、最大波頭評価値との近さ。")]
    [Range(0f, 1f)]
    public float peakOpenThreshold = 0.88f;
    [Tooltip("展開動作の最後の部分に使う、波頭評価値の幅。")]
    [Range(0.01f, 0.5f)]
    public float peakOpenFeather = 0.12f;
    [Tooltip("値が大きいほど、波頭の頂点付近でのみ完全に展開する。")]
    [Range(0.5f, 6f)]
    public float peakOpenPower = 3.1f;

    [Header("波頭先端のフィルタリング")]
    [Tooltip("個々の爪状白波が完全な白泡の指として見えるために必要な、先端の最低強度。")]
    [Range(0f, 1f)]
    public float memberLipThreshold = 0.34f;
    [Tooltip("要素ごとの先端判定を滑らかにする幅。大きいほど、波面の下側にある要素が徐々に薄くなる。")]
    [Range(0.01f, 1f)]
    public float memberLipFeather = 0.30f;
    [Tooltip("波面の下側へ移動した要素に適用する大きさの倍率。")]
    [Range(0.02f, 0.8f)]
    public float lowLipScale = 0.20f;
    [Tooltip("先端の強度が低い要素の展開倍率。後方の白泡を波へ折り込む。")]
    [Range(0f, 1f)]
    public float lowLipOpenScale = 0.18f;
    [Tooltip("波頭の最も強い先端にある要素の大きさを追加する。")]
    [Range(1f, 2.5f)]
    public float highLipScaleBoost = 1.32f;
    [Tooltip("先端の強度が高い要素の白泡の色評価値を追加する。")]
    [Range(0f, 1f)]
    public float highLipFoamBoost = 0.35f;
    [Tooltip("低い先端強度で小さく折り畳まれた要素は描画せず、生存状態は保持する。")]
    public bool skipHiddenLowLipInstances = true;
    [Tooltip("先端の強度が低く、表示値と大きさ・展開量がしきい値を下回る要素は描画バッファに追加しない。")]
    [Range(0f, 1f)]
    public float hiddenLipSkipVisibility = 0.18f;
    [Range(0f, 0.5f)]
    public float hiddenLipSkipOpen = 0.12f;
    [Range(0f, 80f)]
    public float hiddenLipSkipScaleY = 12f;

    [Header("マテリアル")]
    public Color baseColor = new Color(0.93f, 0.91f, 0.84f, 1f);
    public Color highScoreColor = new Color(0.99f, 0.98f, 0.94f, 1f);
    public Color rootBlendColor = new Color(0.50f, 0.66f, 0.74f, 1f);
    public Color outlineInkColor = new Color(0.025f, 0.060f, 0.118f, 1f);
    [Range(0f, 1f)]
    public float outlineStrength = 0.86f;
    [Tooltip("爪状白波の輪郭に付ける細い暗色の墨線の強さ。太い黒い塊に見えないようにする。")]
    [Range(0f, 1f)]
    public float outlineHullAlpha = 0.85f;
    [Tooltip("輪郭の外側へ広げる幅。細い線を保つため小さく設定する。")]
    [Range(0f, 0.4f)]
    public float outlineHullExpand = 0.13f;
    [Range(0f, 0.4f)]
    public float outlineHullTipExpand = 0.09f;
    [Tooltip("爪状白波の描画サイズ倍率。_ClawSizeBoost としてシェーダーへ渡す。遠くからの視認性を調整する。")]
    [Range(0.5f, 8f)]
    public float clawSizeBoost = 3.0f;
    [Range(0f, 1f)]
    public float contourLineStrength = 0.78f;
    [Range(0.005f, 0.18f)]
    public float contourLineWidth = 0.060f;
    public Color clawGreenShadowColor = new Color(0.43f, 0.64f, 0.54f, 1f);
    [Range(0f, 1f)]
    public float clawGreenShadowStrength = 0.74f;
    [Tooltip("生成した波頭インスタンスのうち、爪状白波の先端として表示する割合。非表示のものも白泡の面に使う。")]
    [Range(0f, 1f)]
    public float visibleClawFraction = 1.0f;
    [Tooltip("表示する爪状白波の先端の全体的な不透明度。")]
    [Range(0f, 1f)]
    public float visibleClawAlpha = 1.0f;
    [Range(0.02f, 0.8f)]
    public float rootFadeWidth = 0.34f;
    [Range(0f, 1f)]
    public float rootAlpha = 0.12f;
    [Header("手続き生成する白泡の指")]
    [Tooltip("元の多面体メッシュの代わりに、平らな白泡の指のメッシュを生成して表示する。")]
    public bool drawProceduralFoamFingers = true;
    [Range(0.2f, 1.8f)]
    public float foamFingerWidthScale = 1.78f;
    [Range(0f, 1f)]
    public float foamFingerCurl = 0.32f;
    [Range(0f, 1f)]
    public float foamFingerHookStrength = 0.56f;
    [Range(0f, 1f)]
    public float foamFingerScallopStrength = 0.48f;
    [Range(0f, 1f)]
    public float foamFingerInkCutStrength = 0.34f;
    [Range(0f, 1f)]
    public float foamFingerEdgeBiteStrength = 0.32f;
    [Tooltip("平らな版画風の白泡の指をカメラへ向け、薄い側面だけが見えないようにする。")]
    [Range(0f, 1f)]
    public float foamFingerCameraBillboard = 1.0f;
    [Header("白泡の帯の下地")]
    [Tooltip("個々の爪状白波より先に、柔らかく広がった白泡の層を描き、主波頭を連続した版画風の輪郭に見せる。")]
    public bool drawFoamRibbonUnderlay = false;
    public Color foamUnderlayColor = new Color(0.50f, 0.70f, 0.58f, 1f);
    [Range(0f, 1f)]
    public float foamUnderlayAlpha = 0.0f;
    [Range(0f, 2f)]
    public float foamUnderlayExpand = 0.92f;
    [Range(0f, 2f)]
    public float foamUnderlayTipExpand = 0.58f;
    [Range(0f, 1f)]
    public float foamUnderlayScoreFloor = 0.20f;
    [Header("画面上の参照用白泡帯")]
    [Tooltip("白泡の指が生える、連続した紙の白色の波頭面を描画する。")]
    public bool drawScreenReferenceFoamRibbon = false;
    public Color screenRibbonColor = new Color(1.00f, 0.985f, 0.930f, 0.86f);
    public Color screenRibbonEdgeColor = new Color(0.52f, 0.70f, 0.60f, 0.40f);
    [Range(0f, 1f)]
    public float screenRibbonAlpha = 0.0f;
    [Tooltip("描画する白泡帯と、計算側の爪状白波の引き寄せに共通する画面座標のずれ。")]
    public Vector2 screenRibbonCenterOffset = new Vector2(-0.03f, 0.02f);
    [Range(0.25f, 1.5f)]
    public float screenRibbonHalfWidthScale = 0.95f;
    [Range(0f, 1.5f)]
    public float screenRibbonBendScale = 1.10f;
    [Range(0f, 1.5f)]
    public float screenRibbonTiltScale = 0.95f;
    [Tooltip("既存の画面上の参照円弧の厚さに対する、画面座標での半厚の倍率。")]
    [Range(0.05f, 1.2f)]
    public float screenRibbonThicknessScale = 0.58f;
    [Tooltip("白泡帯を投影する、参照カメラからのワールド座標上の奥行き。ZTest Always で波面上に見える位置を保つ。")]
    [Range(10f, 180f)]
    public float screenRibbonDepth = 68f;
    [Range(0f, 1f)]
    public float screenRibbonEdgeBlend = 0.72f;
    [Tooltip("任意の視覚ガイドへ引き寄せる強さ。白泡を基準に波頭を配置する場合は 0 にする。")]
    [Range(0f, 1f)]
    public float screenRibbonClawFollow = 0.0f;

    [Header("世界座標の波頭白泡面")]
    [Tooltip("生成した波頭インスタンスから、世界座標上の白い白泡面を作る。固定された画面帯ではなく、検出した波頭を追う。")]
    public bool drawWorldCrestFoamPlate = true;
    [Range(0f, 1f)]
    public float worldFoamPlateAlpha = 0.58f;
    public Color worldFoamPlateColor = new Color(1.0f, 0.988f, 0.935f, 1f);
    public Color worldFoamPlateShadowColor = new Color(0.42f, 0.64f, 0.54f, 1f);
    [Range(0f, 1f)]
    public float worldFoamPlateShadowStrength = 0.42f;
    [Range(1f, 28f)]
    public float worldFoamPlateWidth = 10.0f;
    [Range(0f, 4f)]
    public float worldFoamPlateLift = 0.65f;
    [Range(8, 96)]
    public int worldFoamPlateBins = 34;
    [Range(0f, 1f)]
    public float worldFoamPlateMinScore = 0.30f;
    [Range(0f, 1f)]
    public float worldFoamPlateMinLife = 0.035f;
    [Range(0f, 1f)]
    public float worldFoamPlateEdgeInk = 0.42f;

    [Header("デバッグ")]
    public bool logMissingReferences = true;
    [Header("開発用スナップショット出力")]
    [Tooltip("調整に使うエディター・開発ビルド専用の撮影パス。GPU からの読み戻しとファイル書き込みがあるため、通常のプレイ中は無効にする。")]
    public bool exportDebugSnapshotOnPlay = false;
    [Range(1f, 30f)]
    public float debugSnapshotDelay = 11.5f;
    public bool exportDebugSnapshotSequence = true;
    public Vector4 debugSnapshotSequenceSeconds = new Vector4(4.0f, 8.0f, 11.5f, 0.0f);
    public string debugSnapshotBasename = "visual_ribbon_flattened_claws";

    private ComputeBuffer _instancesBuffer;
    private ComputeBuffer _counterBuffer;
    private ComputeBuffer _argsBuffer;
    private ComputeBuffer _underlayArgsBuffer;
    private ComputeBuffer _cellStateBuffer;
    private Vector3 _lastFocusCenter;
    private Vector3 _lastFocusGateCenter;
    private Vector3 _lastCompositionCenter;

    private int _resetKernel = -1;
    private int _generateKernel = -1;
    private int _finalizeKernel = -1;
    private int _bufferCapacity;
    private int _cellStateCapacity;
    private bool _reportedMissingReferences;
    private bool _hasCompositionCenter;
#if UNITY_EDITOR || DEVELOPMENT_BUILD
    private bool _debugSnapshotExported;
    private int _debugSnapshotSequenceMask;
    private float _debugSnapshotStartTime;
#endif

    /// <summary>
    /// コンポーネントが有効になると、計算カーネルを取得してバッファを確保する。
    /// GPU で使う資源を事前に準備する。
    /// </summary>
    private void OnEnable()
    {
        _hasCompositionCenter = false;
        _reportedMissingReferences = false;
#if UNITY_EDITOR || DEVELOPMENT_BUILD
        _debugSnapshotExported = false;
        _debugSnapshotSequenceMask = 0;
        _debugSnapshotStartTime = Time.realtimeSinceStartup;
#endif
        ResolveKernels();
        EnsureBuffers();
    }

    /// <summary>
    /// このコンポーネントが所有する GPU 資源をすべて解放する。
    /// 無効化時に確保済みのバッファを解放する。
    /// </summary>
    private void OnDisable()
    {
        _hasCompositionCenter = false;
        ReleaseBuffers();
        ReleaseRuntimeMaterial();
        ReleaseFoamFingerMesh();
        ReleaseFoamUnderlayMesh();
        ReleaseScreenFoamRibbonResources();
        ReleaseWorldCrestFoamPlateResources();
    }

    /// <summary>
    /// Inspector の設定値を、計算処理と除算で安全に扱える範囲に収める。
    /// 無効な値で計算シェーダーを実行しないための制限を行う。
    /// </summary>
    private void OnValidate()
    {
        ClampGenerationSettings();
        ClampFocusSettings();
        ClampCompositionSettings();
        ClampWaveCouplingSettings();
        ClampClusterSettings();
        ClampShapeSettings();
        ClampGrowthSettings();
        ClampLipFilteringSettings();
        ClampMaterialSettings();
        ClampDebugExportSettings();
    }

    /// <summary>
    /// GPU で爪状白波を 1 フレーム分生成し、間接描画を送信する。
    /// 毎フレーム、生成と描画を順番に実行する。
    /// </summary>
    private void Update()
    {
        if (!enableGpuClaws)
            return;

        if (!HasRequiredReferences())
            return;

        RenderTexture clawMask = oceanScript.GetClawMaskTexture();
        RenderTexture displacement = oceanScript.DisplacementTexture;
        RenderTexture slope = oceanScript.SlopeTexture;
        if (clawMask == null || displacement == null || slope == null)
            return;

        EnsureBuffers();
        if (_instancesBuffer == null || _counterBuffer == null || _argsBuffer == null || _cellStateBuffer == null)
            return;

        DispatchInstancing(clawMask, displacement, slope);
        DrawClaws();

#if UNITY_EDITOR || DEVELOPMENT_BUILD
        TryExportDebugSnapshot();
#endif
    }

    /// <summary>
    /// 走査、個数、密度、波高の判定に使う設定値を制限する。
    /// 生成処理の各しきい値を安全な範囲に収める。
    /// </summary>
    private void ClampGenerationSettings()
    {
        scanGridSize = Mathf.Clamp(scanGridSize, 8, 96);
        maxInstances = Mathf.Clamp(maxInstances, 1, 1024);
        scoreThreshold = Mathf.Clamp01(scoreThreshold);
        spawnDensity = Mathf.Clamp01(spawnDensity);
        worldHeightFeather = Mathf.Max(0.001f, worldHeightFeather);
    }

    /// <summary>
    /// 見える海面の近くにインスタンスを集める任意のカメラ・焦点マスク設定を制限する。
    /// 限られたインスタンス数を画面内の海面へ優先して割り当てる。
    /// </summary>
    private void ClampFocusSettings()
    {
        focusDistance = Mathf.Max(0.0f, focusDistance);
        focusRadius = Mathf.Max(1.0f, focusRadius);
        focusFeather = Mathf.Max(0.001f, focusFeather);
    }

    /// <summary>
    /// 分布を主波頭中心の構図に整える各設定値を制限する。
    /// </summary>
    private void ClampCompositionSettings()
    {
        compositionStrength = Mathf.Clamp01(compositionStrength);
        mainCrestRadius.x = Mathf.Max(0.001f, mainCrestRadius.x);
        mainCrestRadius.y = Mathf.Max(0.001f, mainCrestRadius.y);
        mainCrestBoost = Mathf.Max(0.0f, mainCrestBoost);
        sideCrestRadius.x = Mathf.Max(0.001f, sideCrestRadius.x);
        sideCrestRadius.y = Mathf.Max(0.001f, sideCrestRadius.y);
        sideCrestBoost = Mathf.Max(0.0f, sideCrestBoost);
        backgroundCrestFloor = Mathf.Clamp01(backgroundCrestFloor);
        backgroundDensityScale = Mathf.Clamp01(backgroundDensityScale);
        backgroundClawScale = Mathf.Clamp(backgroundClawScale, 0.1f, 1.0f);
        referenceArcStrength = Mathf.Clamp01(referenceArcStrength);
        referenceArcWidth = Mathf.Clamp(referenceArcWidth, 0.5f, 30.0f);
        referenceArcFeather = Mathf.Clamp(referenceArcFeather, 0.5f, 30.0f);
        referenceArcDensityBias = Mathf.Clamp(referenceArcDensityBias, -1.0f, 1.0f);
        referenceArcShoulderSizeBoost = Mathf.Clamp01(referenceArcShoulderSizeBoost);
        referenceArcShoulderOpenBoost = Mathf.Clamp01(referenceArcShoulderOpenBoost);
        hokusaiArcProfileStrength = Mathf.Clamp01(hokusaiArcProfileStrength);
        hokusaiCurlShoulderBoost = Mathf.Clamp(hokusaiCurlShoulderBoost, 0.0f, 1.5f);
        hokusaiTailScale = Mathf.Clamp(hokusaiTailScale, 0.1f, 1.0f);
        hokusaiTailRevealDelay = Mathf.Clamp(hokusaiTailRevealDelay, 0.0f, 0.5f);
        hokusaiArcLobeContrast = Mathf.Clamp01(hokusaiArcLobeContrast);
        hokusaiWeakToothRetention = Mathf.Clamp01(hokusaiWeakToothRetention);
        screenReferenceStrength = Mathf.Clamp01(screenReferenceStrength);
        screenReferenceCenter.x = Mathf.Clamp01(screenReferenceCenter.x);
        screenReferenceCenter.y = Mathf.Clamp01(screenReferenceCenter.y);
        screenReferenceHalfWidth = Mathf.Clamp(screenReferenceHalfWidth, 0.02f, 0.8f);
        screenReferenceBend = Mathf.Clamp(screenReferenceBend, -0.4f, 0.4f);
        screenReferenceTilt = Mathf.Clamp(screenReferenceTilt, -0.4f, 0.4f);
        screenReferenceThickness = Mathf.Clamp(screenReferenceThickness, 0.005f, 0.3f);
        screenReferenceFeather = Mathf.Clamp(screenReferenceFeather, 0.005f, 0.3f);
        compositionDriftSpeed = Mathf.Max(0.0f, compositionDriftSpeed);
        compositionReturnRate = Mathf.Clamp(compositionReturnRate, 0.0f, 4.0f);
        compositionMaxDriftFromFocus = Mathf.Max(1.0f, compositionMaxDriftFromFocus);
        compositionFocusGateFollow = Mathf.Clamp01(compositionFocusGateFollow);
        mainCrestDensityBoost = Mathf.Clamp(mainCrestDensityBoost, 0.0f, 5.0f);
        sideCrestDensityBoost = Mathf.Clamp(sideCrestDensityBoost, 0.0f, 5.0f);
        mainCrestSearchBoost = Mathf.Clamp(mainCrestSearchBoost, 0.0f, 2.0f);
        sideCrestSearchBoost = Mathf.Clamp(sideCrestSearchBoost, 0.0f, 2.0f);
        mainCrestDedicatedScanShare = Mathf.Clamp(mainCrestDedicatedScanShare, 0.0f, 0.75f);
        sideCrestDedicatedScanShare = Mathf.Clamp(sideCrestDedicatedScanShare, 0.0f, 0.35f);
        if (mainCrestDedicatedScanShare + sideCrestDedicatedScanShare > 0.85f)
            sideCrestDedicatedScanShare = Mathf.Max(0.0f, 0.85f - mainCrestDedicatedScanShare);
    }

    /// <summary>
    /// 計算シェーダーで海面を再構成する際、正の値が必要な設定を制限する。
    /// 海面再構成で無効な値を使わないようにする。
    /// </summary>
    private void ClampWaveCouplingSettings()
    {
        verticalDisplacementStrength = Mathf.Max(0.01f, verticalDisplacementStrength);
        horizontalDisplacementStrength = Mathf.Max(0.01f, horizontalDisplacementStrength);
        crestHeightRange = Mathf.Max(0.001f, crestHeightRange);
        crestSearchRadius = Mathf.Max(0.0f, crestSearchRadius);
        crestSearchLateral = Mathf.Max(0.0f, crestSearchLateral);
    }

    /// <summary>
    /// 一つの波頭の簇に含める爪状白波の個数、間隔、無作為な散らばりを制限する。
    /// 簇内の配置に使う設定値を安全な範囲に収める。
    /// </summary>
    private void ClampClusterSettings()
    {
        minClawsPerCrest = Mathf.Clamp(minClawsPerCrest, 1, 12);
        maxClawsPerCrest = Mathf.Clamp(maxClawsPerCrest, minClawsPerCrest, 12);
        maxRibbonClawsPerCrest = Mathf.Clamp(maxRibbonClawsPerCrest, minClawsPerCrest, maxClawsPerCrest);
        clusterLateralSpacing = Mathf.Max(0.0f, clusterLateralSpacing);
        clusterForwardJitter = Mathf.Max(0.0f, clusterForwardJitter);
        clusterVerticalJitter = Mathf.Max(0.0f, clusterVerticalJitter);
        clusterLateralRandomness = Mathf.Clamp(clusterLateralRandomness, 0.0f, 2.0f);
        clusterForwardRandomness = Mathf.Clamp(clusterForwardRandomness, 0.0f, 2.0f);
        clusterArcForwardOffset = Mathf.Max(0.0f, clusterArcForwardOffset);
        mainFanLateralScale = Mathf.Clamp(mainFanLateralScale, 1.0f, 2.5f);
        mainFanForwardScale = Mathf.Clamp(mainFanForwardScale, 1.0f, 2.0f);
        mainFanYawBoost = Mathf.Clamp(mainFanYawBoost, 0.0f, 1.5f);
        mainMemberScreenArcFollow = Mathf.Clamp01(mainMemberScreenArcFollow);
        foamSheetFlatten = Mathf.Clamp01(foamSheetFlatten);
        foamSheetWidthBoost = Mathf.Clamp01(foamSheetWidthBoost);
        rootEmbedFraction = Mathf.Clamp01(rootEmbedFraction);
        rootEmbedMaxMeters = Mathf.Clamp(rootEmbedMaxMeters, 0.0f, 1.0f);
        rootLiftRangeMeters.x = Mathf.Max(0.0f, rootLiftRangeMeters.x);
        rootLiftRangeMeters.y = Mathf.Max(rootLiftRangeMeters.x, rootLiftRangeMeters.y);
    }

    /// <summary>
    /// メッシュの大きさと向きを制限し、描画の安定性を保つ。
    /// モデルの拡大と回転に使う設定値を制限する。
    /// </summary>
    private void ClampShapeSettings()
    {
        clawScaleRange.x = Mathf.Max(0.01f, clawScaleRange.x);
        clawScaleRange.y = Mathf.Max(clawScaleRange.x, clawScaleRange.y);
        scaleRandomness = Mathf.Clamp(scaleRandomness, 0.0f, 0.75f);
    }

    /// <summary>
    /// 爪状白波の生存時間と展開動作を制限し、成長を安定させる。
    /// 成長と消失の設定値を安全な範囲に収める。
    /// </summary>
    private void ClampGrowthSettings()
    {
        lifeRiseTime = Mathf.Max(0.001f, lifeRiseTime);
        lifeFallTime = Mathf.Max(0.001f, lifeFallTime);
        visibleLifeThreshold = Mathf.Clamp01(visibleLifeThreshold);
        drawLifeThreshold = Mathf.Clamp(drawLifeThreshold, 0.0f, visibleLifeThreshold);
        crestDriftSpeed = Mathf.Max(0f, crestDriftSpeed);
        crestRelockRate = Mathf.Max(0f, crestRelockRate);
        crestLostFallBoost = Mathf.Max(1f, crestLostFallBoost);
        growthMinScale = Mathf.Clamp(growthMinScale, 0.01f, 0.6f);
        growthCurvePower = Mathf.Clamp(growthCurvePower, 0.2f, 4.0f);
        growthStagger = Mathf.Clamp(growthStagger, 0.0f, 0.85f);
        ribbonOpenFloor = Mathf.Clamp01(ribbonOpenFloor);
        ribbonDelayCompression = Mathf.Clamp01(ribbonDelayCompression);
        peakOpenThreshold = Mathf.Clamp01(peakOpenThreshold);
        peakOpenFeather = Mathf.Clamp(peakOpenFeather, 0.01f, 0.5f);
        peakOpenPower = Mathf.Clamp(peakOpenPower, 0.5f, 6.0f);
    }

    /// <summary>
    /// 要素ごとの波頭先端判定を制限し、波面下側の白泡を小さく折り畳む。
    /// </summary>
    private void ClampLipFilteringSettings()
    {
        memberLipThreshold = Mathf.Clamp01(memberLipThreshold);
        memberLipFeather = Mathf.Clamp(memberLipFeather, 0.01f, 1.0f);
        lowLipScale = Mathf.Clamp(lowLipScale, 0.02f, 0.8f);
        lowLipOpenScale = Mathf.Clamp01(lowLipOpenScale);
        highLipScaleBoost = Mathf.Clamp(highLipScaleBoost, 1.0f, 2.5f);
        highLipFoamBoost = Mathf.Clamp01(highLipFoamBoost);
        hiddenLipSkipVisibility = Mathf.Clamp01(hiddenLipSkipVisibility);
        hiddenLipSkipOpen = Mathf.Clamp(hiddenLipSkipOpen, 0.0f, 0.5f);
        hiddenLipSkipScaleY = Mathf.Clamp(hiddenLipSkipScaleY, 0.0f, 80.0f);
    }

    /// <summary>
    /// 白泡の根元から先端へ向かう色の混合に使うマテリアル設定を制限する。
    /// </summary>
    private void ClampMaterialSettings()
    {
        rootFadeWidth = Mathf.Clamp(rootFadeWidth, 0.02f, 0.8f);
        rootAlpha = Mathf.Clamp01(rootAlpha);
        outlineStrength = Mathf.Clamp01(outlineStrength);
        contourLineStrength = Mathf.Clamp01(contourLineStrength);
        contourLineWidth = Mathf.Clamp(contourLineWidth, 0.005f, 0.18f);
        clawGreenShadowStrength = Mathf.Clamp01(clawGreenShadowStrength);
        visibleClawFraction = Mathf.Clamp01(visibleClawFraction);
        visibleClawAlpha = Mathf.Clamp01(visibleClawAlpha);
        foamFingerWidthScale = Mathf.Clamp(foamFingerWidthScale, 0.2f, 1.8f);
        foamFingerCurl = Mathf.Clamp01(foamFingerCurl);
        foamFingerHookStrength = Mathf.Clamp01(foamFingerHookStrength);
        foamFingerScallopStrength = Mathf.Clamp01(foamFingerScallopStrength);
        foamFingerInkCutStrength = Mathf.Clamp01(foamFingerInkCutStrength);
        foamFingerEdgeBiteStrength = Mathf.Clamp01(foamFingerEdgeBiteStrength);
        foamFingerCameraBillboard = Mathf.Clamp01(foamFingerCameraBillboard);
        foamUnderlayAlpha = Mathf.Clamp01(foamUnderlayAlpha);
        foamUnderlayExpand = Mathf.Clamp(foamUnderlayExpand, 0.0f, 2.0f);
        foamUnderlayTipExpand = Mathf.Clamp(foamUnderlayTipExpand, 0.0f, 2.0f);
        foamUnderlayScoreFloor = Mathf.Clamp01(foamUnderlayScoreFloor);
        screenRibbonAlpha = Mathf.Clamp01(screenRibbonAlpha);
        screenRibbonCenterOffset.x = Mathf.Clamp(screenRibbonCenterOffset.x, -1.0f, 1.0f);
        screenRibbonCenterOffset.y = Mathf.Clamp(screenRibbonCenterOffset.y, -1.0f, 1.0f);
        screenRibbonHalfWidthScale = Mathf.Clamp(screenRibbonHalfWidthScale, 0.25f, 1.5f);
        screenRibbonBendScale = Mathf.Clamp(screenRibbonBendScale, 0.0f, 1.5f);
        screenRibbonTiltScale = Mathf.Clamp(screenRibbonTiltScale, 0.0f, 1.5f);
        screenRibbonThicknessScale = Mathf.Clamp(screenRibbonThicknessScale, 0.05f, 1.2f);
        screenRibbonDepth = Mathf.Clamp(screenRibbonDepth, 10.0f, 180.0f);
        screenRibbonEdgeBlend = Mathf.Clamp01(screenRibbonEdgeBlend);
        screenRibbonClawFollow = Mathf.Clamp01(screenRibbonClawFollow);
        worldFoamPlateAlpha = Mathf.Clamp01(worldFoamPlateAlpha);
        worldFoamPlateShadowStrength = Mathf.Clamp01(worldFoamPlateShadowStrength);
        worldFoamPlateWidth = Mathf.Clamp(worldFoamPlateWidth, 1.0f, 28.0f);
        worldFoamPlateLift = Mathf.Clamp(worldFoamPlateLift, 0.0f, 4.0f);
        worldFoamPlateBins = Mathf.Clamp(worldFoamPlateBins, 8, 96);
        worldFoamPlateMinScore = Mathf.Clamp01(worldFoamPlateMinScore);
        worldFoamPlateMinLife = Mathf.Clamp01(worldFoamPlateMinLife);
        worldFoamPlateEdgeInk = Mathf.Clamp01(worldFoamPlateEdgeInk);
    }

    private void ClampDebugExportSettings()
    {
        debugSnapshotDelay = Mathf.Clamp(debugSnapshotDelay, 1.0f, 30.0f);
        debugSnapshotSequenceSeconds.x = ClampDebugSnapshotSequenceTime(debugSnapshotSequenceSeconds.x);
        debugSnapshotSequenceSeconds.y = ClampDebugSnapshotSequenceTime(debugSnapshotSequenceSeconds.y);
        debugSnapshotSequenceSeconds.z = ClampDebugSnapshotSequenceTime(debugSnapshotSequenceSeconds.z);
        debugSnapshotSequenceSeconds.w = ClampDebugSnapshotSequenceTime(debugSnapshotSequenceSeconds.w);
        if (string.IsNullOrWhiteSpace(debugSnapshotBasename))
            debugSnapshotBasename = "visual_ribbon_flattened_claws";
    }

    private static float ClampDebugSnapshotSequenceTime(float seconds)
    {
        return seconds <= 0.001f ? 0.0f : Mathf.Clamp(seconds, 1.0f, 30.0f);
    }

    /// <summary>
    /// 実行前に必要な Unity アセットと計算カーネルがそろっているか確認する。
    /// 参照が欠けている場合は生成処理を実行しない。
    /// </summary>
    private bool HasRequiredReferences()
    {
        if (oceanScript == null)
            oceanScript = UnityEngine.Object.FindAnyObjectByType<FFTOcean_Script>();

        // 計算カーネルの取得を再試行する。OnEnable の ResolveKernels は、ドメインの再読み込みや
        // Play モードへ入った直後に、計算シェーダーの準備前に実行される場合がある。
        // その場合 FindKernel が例外を出さずに -1 を返し、再試行しなければ参照が不足したままになる。
        // 結果としてバッファが作られず、爪状白波が描画されない。
        // 毎フレームの確認時に再試行し、取得後は追加処理をしない。
        // 準備前に計算カーネルを探した場合にも、後続のフレームで再取得を試みる。
        // FindKernel が -1 を返した状態から復帰できるようにする。
        if (clawInstancingCompute != null
            && (_resetKernel < 0 || _generateKernel < 0 || _finalizeKernel < 0))
        {
            ResolveKernels();
        }

        bool ok = oceanScript != null
            && clawInstancingCompute != null
            && clawMesh != null
            && clawMaterial != null
            && _resetKernel >= 0
            && _generateKernel >= 0
            && _finalizeKernel >= 0;

        if (!ok && logMissingReferences && !_reportedMissingReferences)
        {
            Debug.LogWarning("[OceanClawGpuInstancer] 参照が不足しています。海面、計算シェーダー、メッシュ、インスタンス描画用マテリアルを設定してください。");
            _reportedMissingReferences = true;
        }

        return ok;
    }

    /// <summary>
    /// GPU 処理で使う三つのカーネルを取得する。リセット、生成、間接描画引数の確定を行う。
    /// 各カーネル番号を後続の計算に使う。
    /// </summary>
    private void ResolveKernels()
    {
        _resetKernel = -1;
        _generateKernel = -1;
        _finalizeKernel = -1;

        if (clawInstancingCompute == null)
            return;

        try
        {
            _resetKernel = clawInstancingCompute.FindKernel("CS_Reset");
            _generateKernel = clawInstancingCompute.FindKernel("CS_Generate");
            _finalizeKernel = clawInstancingCompute.FindKernel("CS_FinalizeArgs");
        }
        catch (System.Exception ex)
        {
            Debug.LogError($"[OceanClawGpuInstancer] カーネルの取得に失敗しました: {ex.Message}");
        }
    }

    /// <summary>
    /// インスタンスの上限や走査格子が変わった場合に、GPU バッファを確保または作り直す。
    /// 必要な容量に合わせてバッファを更新する。
    /// </summary>
    private void EnsureBuffers()
    {
        int desiredCapacity = Mathf.Max(1, maxInstances);
        int desiredCellCapacity = Mathf.Max(1, scanGridSize * scanGridSize);
        if (_instancesBuffer != null
            && _counterBuffer != null
            && _argsBuffer != null
            && _underlayArgsBuffer != null
            && _cellStateBuffer != null
            && _bufferCapacity == desiredCapacity
            && _cellStateCapacity == desiredCellCapacity)
            return;

        ReleaseBuffers();

        _bufferCapacity = desiredCapacity;
        _cellStateCapacity = desiredCellCapacity;
        _instancesBuffer = new ComputeBuffer(_bufferCapacity, InstanceStride, ComputeBufferType.Structured);
        _counterBuffer = new ComputeBuffer(1, sizeof(uint), ComputeBufferType.Structured);
        _argsBuffer = new ComputeBuffer(IndirectArgsCount, sizeof(uint), ComputeBufferType.IndirectArguments);
        _underlayArgsBuffer = new ComputeBuffer(IndirectArgsCount, sizeof(uint), ComputeBufferType.IndirectArguments);
        // 走査セルごとに float4 を二つ使う。スロット 0 は生存状態、スロット 1 は波頭に固定した基点の XZ 座標。
        // 各セルの状態と波頭への追従位置を別のスロットに保持する。
        _cellStateBuffer = new ComputeBuffer(_cellStateCapacity * 2, CellStateStride, ComputeBufferType.Structured);

        // 新しい ComputeBuffer の GPU メモリは未定義の内容を持つ。計算シェーダーは
        // state.w を初期化フラグとして読むため、未初期化データが誤った生存値を作る可能性がある。
        // 最初にすべてをゼロで埋め、全セルを既知の非活動状態から始める。
        // 新しいバッファの未定義値を生存状態として誤認しないようにする。
        // バッファ生成後に一度だけゼロで初期化する。
        _cellStateBuffer.SetData(new Vector4[_cellStateCapacity * 2]);
    }

    /// <summary>
    /// 計算バッファを解放し、容量の記録を消去する。
    /// GPU バッファとその管理値を初期状態へ戻す。
    /// </summary>
    private void ReleaseBuffers()
    {
        if (_instancesBuffer != null)
        {
            _instancesBuffer.Release();
            _instancesBuffer = null;
        }

        if (_counterBuffer != null)
        {
            _counterBuffer.Release();
            _counterBuffer = null;
        }

        if (_argsBuffer != null)
        {
            _argsBuffer.Release();
            _argsBuffer = null;
        }

        if (_underlayArgsBuffer != null)
        {
            _underlayArgsBuffer.Release();
            _underlayArgsBuffer = null;
        }

        if (_cellStateBuffer != null)
        {
            _cellStateBuffer.Release();
            _cellStateBuffer = null;
        }

        _bufferCapacity = 0;
        _cellStateCapacity = 0;
    }

    /// <summary>
    /// リセット、生成、間接描画引数の確定を順番に実行する。
    /// 三つの計算処理で描画用のインスタンスを準備する。
    /// </summary>
    private void DispatchInstancing(RenderTexture clawMask, RenderTexture displacement, RenderTexture slope)
    {
        // CS_Reset は毎フレーム GPU 上で五つの間接描画引数を書き込む。
        // 以前の毎フレームの _argsBuffer.SetData 転送と配列の確保は重複していた。
        // 描画引数は CS_Reset が更新するため、CPU からの再転送は行わない。
        // 不要な配列の確保も省く。
        Vector2 dominantDirection = WindDirectionToXZ(oceanScript.DisplaySpectrum0.windDirection);
        Vector3 oceanPosition = oceanScript.transform.position;

        SetComputeParams(clawMask.width, dominantDirection, oceanPosition);
        DispatchResetKernel();
        DispatchGenerateKernel(clawMask, displacement, slope);
        DispatchFinalizeKernel();
    }

    /// <summary>
    /// 計算シェーダーが毎フレーム使う設定値を転送する。
    /// フレームごとに変わる各設定を GPU へ渡す。
    /// </summary>
    private void SetComputeParams(int resolution, Vector2 dominantDirection, Vector3 oceanPosition)
    {
        SetMeshParams(resolution);
        SetOceanSamplingParams(oceanPosition);
        SetSpawnScoringParams(oceanPosition, dominantDirection);
        SetCompositionParams(dominantDirection);
        SetClawShapeParams(oceanPosition, dominantDirection);
        SetLifecycleParams();
        SetClusterParams();
        SetGrowthParams();
        SetLipFilteringParams();
        SetWaveCouplingParams();
    }

    /// <summary>
    /// メッシュの描画情報と走査格子の寸法を計算シェーダーへ送る。
    /// 間接描画と走査に必要な値を設定する。
    /// </summary>
    private void SetMeshParams(int resolution)
    {
        Mesh mainMesh = GetMainClawMesh();
        Mesh underlayMesh = GetUnderlayClawMesh();
        clawInstancingCompute.SetInt("_IndexCount", (int)mainMesh.GetIndexCount(0));
        clawInstancingCompute.SetInt("_StartIndex", (int)mainMesh.GetIndexStart(0));
        clawInstancingCompute.SetInt("_BaseVertex", (int)mainMesh.GetBaseVertex(0));
        clawInstancingCompute.SetInt("_UnderlayIndexCount", (int)underlayMesh.GetIndexCount(0));
        clawInstancingCompute.SetInt("_UnderlayStartIndex", (int)underlayMesh.GetIndexStart(0));
        clawInstancingCompute.SetInt("_UnderlayBaseVertex", (int)underlayMesh.GetBaseVertex(0));
        clawInstancingCompute.SetInt("_Resolution", resolution);
        clawInstancingCompute.SetInt("_ScanGridSize", scanGridSize);
        clawInstancingCompute.SetInt("_MaxInstances", maxInstances);
        clawInstancingCompute.SetInt("_RandomSeed", randomSeed);
    }

    /// <summary>
    /// FFT タイルの情報を送信し、計算シェーダーで表示中と同じ海面を再構成する。
    /// 見える波面と爪状白波の生成位置を合わせる。
    /// </summary>
    private void SetOceanSamplingParams(Vector3 oceanPosition)
    {
        clawInstancingCompute.SetVector("_OceanCenterXZ", new Vector4(oceanPosition.x, oceanPosition.z, 0f, 0f));
        clawInstancingCompute.SetFloat("_OceanLength", Mathf.Max(1f, oceanScript.waterMeshLength));
        clawInstancingCompute.SetVector("_TileScales", new Vector4(oceanScript.Tile0, oceanScript.Tile1, oceanScript.Tile2, oceanScript.Tile3));
        clawInstancingCompute.SetVector("_LayerContributes", new Vector4(
            oceanScript.LayerContribute0,
            oceanScript.LayerContribute1,
            oceanScript.LayerContribute2,
            oceanScript.LayerContribute3));
    }

    /// <summary>
    /// 爪状白波の生成を許可するか決める、波頭のしきい値と焦点範囲の設定を送る。
    /// 候補の波頭が生成条件を満たすか判定するための値を渡す。
    /// </summary>
    private void SetSpawnScoringParams(Vector3 oceanPosition, Vector2 dominantDirection)
    {
        clawInstancingCompute.SetFloat("_ScoreThreshold", scoreThreshold);
        clawInstancingCompute.SetFloat("_SpawnDensity", spawnDensity);
        clawInstancingCompute.SetFloat("_WorldHeightThreshold", worldHeightThreshold);
        clawInstancingCompute.SetFloat("_WorldHeightFeather", Mathf.Max(0.001f, worldHeightFeather));
        SetFocusParams(oceanPosition, dominantDirection);
    }

    /// <summary>
    /// 波頭に各爪状白波を配置するため、メッシュの大きさ、基点、向きの設定を送る。
    /// モデルが波頭に沿うように各値を計算シェーダーへ渡す。
    /// </summary>
    private void SetClawShapeParams(Vector3 oceanPosition, Vector2 dominantDirection)
    {
        clawInstancingCompute.SetVector("_ClawScaleRange", new Vector4(clawScaleRange.x, clawScaleRange.y, 0f, 0f));
        clawInstancingCompute.SetVector("_ClawScaleMultiplier", new Vector4(clawScaleMultiplier.x, clawScaleMultiplier.y, clawScaleMultiplier.z, 0f));
        clawInstancingCompute.SetFloat("_VerticalOffset", verticalOffset + oceanPosition.y);
        clawInstancingCompute.SetVector("_MeshAnchorLocal", GetMeshAnchorLocal());
        clawInstancingCompute.SetFloat("_LocalYPointsTowardTip", localYPointsTowardTip ? 1f : 0f);
        clawInstancingCompute.SetFloat("_ForwardFromSlope", forwardFromSlope);
        clawInstancingCompute.SetFloat("_YawJitterRadians", yawJitterDegrees * Mathf.Deg2Rad);
        clawInstancingCompute.SetFloat("_NormalInfluence", normalInfluence);
        clawInstancingCompute.SetVector("_DominantDirectionXZ", new Vector4(dominantDirection.x, dominantDirection.y, 0f, 0f));
        clawInstancingCompute.SetFloat("_SurfaceNormalBlend", surfaceNormalBlend);
        clawInstancingCompute.SetFloat("_TipDownwardBias", tipDownwardBias);
        clawInstancingCompute.SetFloat("_ScaleRandomness", scaleRandomness);
        clawInstancingCompute.SetFloat("_FoamFingerCameraBillboard", foamFingerCameraBillboard);
    }

    /// <summary>
    /// 爪状白波が自然に成長し、徐々に消えるまで保持する時間設定を送る。
    /// 急な出現や消失を抑えるための生存時間を渡す。
    /// </summary>
    private void SetLifecycleParams()
    {
        clawInstancingCompute.SetFloat("_DeltaTime", Mathf.Max(Time.deltaTime, 0.0001f));
        clawInstancingCompute.SetFloat("_LifeRiseTime", lifeRiseTime);
        clawInstancingCompute.SetFloat("_LifeFallTime", lifeFallTime);
        clawInstancingCompute.SetFloat("_VisibleLifeThreshold", visibleLifeThreshold);
        clawInstancingCompute.SetFloat("_DrawLifeThreshold", drawLifeThreshold);
        clawInstancingCompute.SetFloat("_CrestDriftSpeed", Mathf.Max(0f, crestDriftSpeed));
        clawInstancingCompute.SetFloat("_CrestRelockRate", Mathf.Max(0f, crestRelockRate));
        clawInstancingCompute.SetFloat("_CrestLostFallBoost", Mathf.Max(1f, crestLostFallBoost));
    }

    /// <summary>
    /// 簇の配置設定を送る。波頭ごとの爪状白波の個数と無作為な分布を決める。
    /// 一つの波頭内に生成する各要素の配置を制御する。
    /// </summary>
    private void SetClusterParams()
    {
        clawInstancingCompute.SetInt("_MinClawsPerCrest", minClawsPerCrest);
        clawInstancingCompute.SetInt("_MaxClawsPerCrest", maxClawsPerCrest);
        clawInstancingCompute.SetInt("_MaxRibbonClawsPerCrest", maxRibbonClawsPerCrest);
        clawInstancingCompute.SetFloat("_ClusterLateralSpacing", clusterLateralSpacing);
        clawInstancingCompute.SetFloat("_ClusterForwardJitter", clusterForwardJitter);
        clawInstancingCompute.SetFloat("_ClusterVerticalJitter", clusterVerticalJitter);
        clawInstancingCompute.SetFloat("_ClusterLateralRandomness", clusterLateralRandomness);
        clawInstancingCompute.SetFloat("_ClusterForwardRandomness", clusterForwardRandomness);
        clawInstancingCompute.SetFloat("_CrestCurveFollow", crestCurveFollow);
        clawInstancingCompute.SetFloat("_ClusterFanRadians", clusterFanDegrees * Mathf.Deg2Rad);
        clawInstancingCompute.SetFloat("_ClusterArcForwardOffset", clusterArcForwardOffset);
        clawInstancingCompute.SetFloat("_MainFanLateralScale", mainFanLateralScale);
        clawInstancingCompute.SetFloat("_MainFanForwardScale", mainFanForwardScale);
        clawInstancingCompute.SetFloat("_MainFanYawBoost", mainFanYawBoost);
        clawInstancingCompute.SetFloat("_MainMemberScreenArcFollow", mainMemberScreenArcFollow);
        clawInstancingCompute.SetFloat("_FoamSheetFlatten", foamSheetFlatten);
        clawInstancingCompute.SetFloat("_FoamSheetWidthBoost", foamSheetWidthBoost);
        clawInstancingCompute.SetFloat("_RootEmbedFraction", rootEmbedFraction);
        clawInstancingCompute.SetFloat("_RootEmbedMaxMeters", rootEmbedMaxMeters);
        clawInstancingCompute.SetVector("_RootLiftRangeMeters", new Vector4(rootLiftRangeMeters.x, rootLiftRangeMeters.y, 0f, 0f));
        clawInstancingCompute.SetFloat("_SizeHierarchy", sizeHierarchy);
    }

    /// <summary>
    /// 波頭が最も強くなる頃に爪状白波が完全に開くよう、展開の設定を送る。
    /// 成長段階と波頭の強さを合わせるための値を渡す。
    /// </summary>
    private void SetGrowthParams()
    {
        clawInstancingCompute.SetFloat("_GrowthFoldRadians", growthFoldDegrees * Mathf.Deg2Rad);
        clawInstancingCompute.SetFloat("_GrowthMinScale", growthMinScale);
        clawInstancingCompute.SetFloat("_GrowthCurvePower", growthCurvePower);
        clawInstancingCompute.SetFloat("_GrowthStagger", growthStagger);
        clawInstancingCompute.SetFloat("_RibbonOpenFloor", ribbonOpenFloor);
        clawInstancingCompute.SetFloat("_RibbonDelayCompression", ribbonDelayCompression);
        clawInstancingCompute.SetFloat("_PeakOpenThreshold", peakOpenThreshold);
        clawInstancingCompute.SetFloat("_PeakOpenFeather", peakOpenFeather);
        clawInstancingCompute.SetFloat("_PeakOpenPower", peakOpenPower);
    }

    /// <summary>
    /// 要素ごとのフィルタリング設定を送る。波面下側の白泡を縮めて折り畳み、先端を強調する。
    /// </summary>
    private void SetLipFilteringParams()
    {
        clawInstancingCompute.SetFloat("_MemberLipThreshold", memberLipThreshold);
        clawInstancingCompute.SetFloat("_MemberLipFeather", memberLipFeather);
        clawInstancingCompute.SetFloat("_LowLipScale", lowLipScale);
        clawInstancingCompute.SetFloat("_LowLipOpenScale", lowLipOpenScale);
        clawInstancingCompute.SetFloat("_HighLipScaleBoost", highLipScaleBoost);
        clawInstancingCompute.SetFloat("_HighLipFoamBoost", highLipFoamBoost);
        clawInstancingCompute.SetFloat("_SkipHiddenLowLipInstances", skipHiddenLowLipInstances ? 1.0f : 0.0f);
        clawInstancingCompute.SetFloat("_HiddenLipSkipVisibility", hiddenLipSkipVisibility);
        clawInstancingCompute.SetFloat("_HiddenLipSkipOpen", hiddenLipSkipOpen);
        clawInstancingCompute.SetFloat("_HiddenLipSkipScaleY", hiddenLipSkipScaleY);
    }

    /// <summary>
    /// 爪状白波の計算シェーダーに、表示中の波面の変形強度を送る。
    /// 爪状白波の位置を実際に描画される波頭へ合わせる。
    /// </summary>
    private void SetWaveCouplingParams()
    {
        float visibleVerticalStrength = oceanScript.VerticalDisplacementStrength > 0.0f
            ? oceanScript.VerticalDisplacementStrength
            : verticalDisplacementStrength;
        float visibleHorizontalStrength = oceanScript.HorizontalDisplacementStrength > 0.0f
            ? oceanScript.HorizontalDisplacementStrength
            : horizontalDisplacementStrength;
        float visibleCrestAmplification = oceanScript.CrestAmplification > 0.0f
            ? oceanScript.CrestAmplification
            : crestAmplification;

        clawInstancingCompute.SetFloat("_VerticalDisplacementStrength", visibleVerticalStrength);
        clawInstancingCompute.SetFloat("_HorizontalDisplacementStrength", visibleHorizontalStrength);
        clawInstancingCompute.SetFloat("_CrestAmplification", visibleCrestAmplification);
        clawInstancingCompute.SetFloat("_CrestProbeDistance", crestProbeDistance);
        clawInstancingCompute.SetFloat("_CrestHeightBias", crestHeightBias);
        clawInstancingCompute.SetFloat("_CrestHeightRange", crestHeightRange);
        clawInstancingCompute.SetFloat("_CrestSearchRadius", crestSearchRadius);
        clawInstancingCompute.SetFloat("_CrestSearchLateral", crestSearchLateral);
    }

    /// <summary>
    /// インスタンスをカメラに見える範囲へ集中させる焦点マスクを計算して送る。
    /// 限られたインスタンス数を見える海面へ優先して割り当てる。
    /// </summary>
    private void SetFocusParams(Vector3 oceanPosition, Vector2 dominantDirection)
    {
        bool useFocus = focusSpawnsNearCamera;
        Vector3 focusPosition = oceanPosition;
        Vector3 focusForward = new Vector3(dominantDirection.x, 0.0f, dominantDirection.y);

        Transform focusTransform = spawnFocus;
        if (focusTransform == null && Camera.main != null)
            focusTransform = Camera.main.transform;

        if (focusTransform != null)
        {
            focusPosition = focusTransform.position;
            focusForward = focusTransform.forward;
            focusForward.y = 0.0f;
        }
        else
        {
            useFocus = false;
        }

        if (focusForward.sqrMagnitude < 0.0001f)
            focusForward = new Vector3(dominantDirection.x, 0.0f, dominantDirection.y);
        if (focusForward.sqrMagnitude < 0.0001f)
            focusForward = Vector3.forward;

        focusForward.Normalize();
        _lastFocusCenter = focusPosition + focusForward * focusDistance;
        _lastFocusGateCenter = _lastFocusCenter;

        clawInstancingCompute.SetFloat("_UseFocusGate", useFocus ? 1.0f : 0.0f);
        clawInstancingCompute.SetVector("_FocusCenterXZ", new Vector4(_lastFocusCenter.x, _lastFocusCenter.z, 0f, 0f));
        clawInstancingCompute.SetFloat("_FocusRadius", focusRadius);
        clawInstancingCompute.SetFloat("_FocusFeather", focusFeather);
    }

    /// <summary>
    /// 主波頭と小さな副波頭を作るため、安定した空間的な重みを送る。
    /// </summary>
    private void SetCompositionParams(Vector2 dominantDirection)
    {
        Vector3 compositionCenter = UpdateCompositionCenter(dominantDirection);
        _lastFocusGateCenter = Vector3.Lerp(_lastFocusCenter, compositionCenter, compositionFocusGateFollow);

        clawInstancingCompute.SetFloat("_UseCompositionBias", useCompositionBias ? 1.0f : 0.0f);
        clawInstancingCompute.SetFloat("_CompositionStrength", compositionStrength);
        clawInstancingCompute.SetVector("_FocusCenterXZ", new Vector4(_lastFocusGateCenter.x, _lastFocusGateCenter.z, 0f, 0f));
        clawInstancingCompute.SetVector("_CompositionCenterXZ", new Vector4(compositionCenter.x, compositionCenter.z, 0f, 0f));
        clawInstancingCompute.SetVector("_MainCrestOffset", new Vector4(mainCrestOffset.x, mainCrestOffset.y, 0f, 0f));
        clawInstancingCompute.SetVector("_MainCrestRadius", new Vector4(mainCrestRadius.x, mainCrestRadius.y, 0f, 0f));
        clawInstancingCompute.SetFloat("_MainCrestBoost", mainCrestBoost);
        clawInstancingCompute.SetVector("_SideCrestOffset", new Vector4(sideCrestOffset.x, sideCrestOffset.y, 0f, 0f));
        clawInstancingCompute.SetVector("_SideCrestRadius", new Vector4(sideCrestRadius.x, sideCrestRadius.y, 0f, 0f));
        clawInstancingCompute.SetFloat("_SideCrestBoost", sideCrestBoost);
        clawInstancingCompute.SetFloat("_BackgroundCrestFloor", backgroundCrestFloor);
        clawInstancingCompute.SetFloat("_BackgroundDensityScale", backgroundDensityScale);
        clawInstancingCompute.SetFloat("_BackgroundClawScale", backgroundClawScale);
        clawInstancingCompute.SetFloat("_UseReferenceCrestArc", useReferenceCrestArc ? 1.0f : 0.0f);
        clawInstancingCompute.SetFloat("_ReferenceArcStrength", referenceArcStrength);
        clawInstancingCompute.SetFloat("_ReferenceArcForwardBend", referenceArcForwardBend);
        clawInstancingCompute.SetFloat("_ReferenceArcCurl", referenceArcCurl);
        clawInstancingCompute.SetFloat("_ReferenceArcWidth", referenceArcWidth);
        clawInstancingCompute.SetFloat("_ReferenceArcFeather", referenceArcFeather);
        clawInstancingCompute.SetFloat("_ReferenceArcDensityBias", referenceArcDensityBias);
        clawInstancingCompute.SetFloat("_ReferenceArcShoulderSizeBoost", referenceArcShoulderSizeBoost);
        clawInstancingCompute.SetFloat("_ReferenceArcShoulderOpenBoost", referenceArcShoulderOpenBoost);
        clawInstancingCompute.SetFloat("_HokusaiArcProfileStrength", hokusaiArcProfileStrength);
        clawInstancingCompute.SetFloat("_HokusaiCurlShoulderBoost", hokusaiCurlShoulderBoost);
        clawInstancingCompute.SetFloat("_HokusaiTailScale", hokusaiTailScale);
        clawInstancingCompute.SetFloat("_HokusaiTailRevealDelay", hokusaiTailRevealDelay);
        clawInstancingCompute.SetFloat("_HokusaiArcLobeContrast", hokusaiArcLobeContrast);
        clawInstancingCompute.SetFloat("_HokusaiWeakToothRetention", hokusaiWeakToothRetention);
        SetScreenReferenceParams();
        clawInstancingCompute.SetFloat("_MainCrestDensityBoost", mainCrestDensityBoost);
        clawInstancingCompute.SetFloat("_SideCrestDensityBoost", sideCrestDensityBoost);
        clawInstancingCompute.SetFloat("_MainCrestSearchBoost", mainCrestSearchBoost);
        clawInstancingCompute.SetFloat("_SideCrestSearchBoost", sideCrestSearchBoost);
        clawInstancingCompute.SetFloat("_MainCrestDedicatedScanShare", mainCrestDedicatedScanShare);
        clawInstancingCompute.SetFloat("_SideCrestDedicatedScanShare", sideCrestDedicatedScanShare);
    }

    /// <summary>
    /// 主波頭を参照画像の画面構図へ近づけるため、主カメラの投影情報を送る。
    /// </summary>
    private void SetScreenReferenceParams()
    {
        Camera referenceCamera = Camera.main;
        bool useMask = useScreenReferenceMask && referenceCamera != null;
        Matrix4x4 viewProjection = Matrix4x4.identity;
        Matrix4x4 inverseViewProjection = Matrix4x4.identity;
        Vector3 referenceCameraPosition = Vector3.zero;
        Vector3 referenceCameraRight = Vector3.right;
        Vector3 referenceCameraUp = Vector3.up;
        Vector3 referenceCameraForward = Vector3.forward;
        if (useMask)
        {
            viewProjection = GL.GetGPUProjectionMatrix(referenceCamera.projectionMatrix, false) * referenceCamera.worldToCameraMatrix;
            inverseViewProjection = viewProjection.inverse;
            referenceCameraPosition = referenceCamera.transform.position;
            referenceCameraRight = referenceCamera.transform.right;
            referenceCameraUp = referenceCamera.transform.up;
            referenceCameraForward = referenceCamera.transform.forward;
        }

        clawInstancingCompute.SetFloat("_UseScreenReferenceMask", useMask ? 1.0f : 0.0f);
        clawInstancingCompute.SetFloat("_ScreenReferenceStrength", screenReferenceStrength);
        clawInstancingCompute.SetMatrix("_ScreenReferenceVP", viewProjection);
        clawInstancingCompute.SetMatrix("_ScreenReferenceInvVP", inverseViewProjection);
        clawInstancingCompute.SetVector("_ReferenceCameraXZ", new Vector4(referenceCameraPosition.x, referenceCameraPosition.z, 0f, 0f));
        clawInstancingCompute.SetVector("_ReferenceCameraRight", new Vector4(referenceCameraRight.x, referenceCameraRight.y, referenceCameraRight.z, 0f));
        clawInstancingCompute.SetVector("_ReferenceCameraUp", new Vector4(referenceCameraUp.x, referenceCameraUp.y, referenceCameraUp.z, 0f));
        clawInstancingCompute.SetVector("_ReferenceCameraForward", new Vector4(referenceCameraForward.x, referenceCameraForward.y, referenceCameraForward.z, 0f));
        clawInstancingCompute.SetVector("_ScreenReferenceCenter", new Vector4(screenReferenceCenter.x, screenReferenceCenter.y, 0f, 0f));
        clawInstancingCompute.SetFloat("_ScreenReferenceHalfWidth", screenReferenceHalfWidth);
        clawInstancingCompute.SetFloat("_ScreenReferenceBend", screenReferenceBend);
        clawInstancingCompute.SetFloat("_ScreenReferenceTilt", screenReferenceTilt);
        clawInstancingCompute.SetFloat("_ScreenReferenceThickness", screenReferenceThickness);
        clawInstancingCompute.SetFloat("_ScreenReferenceFeather", screenReferenceFeather);

        bool useVisualRibbonMask = useMask
            && screenRibbonClawFollow > 0.001f;
        Vector2 visualCenter = screenReferenceCenter + screenRibbonCenterOffset;
        float visualHalfWidth = Mathf.Max(screenReferenceHalfWidth * screenRibbonHalfWidthScale, 0.001f);
        float visualBend = screenReferenceBend * screenRibbonBendScale;
        float visualTilt = screenReferenceTilt * screenRibbonTiltScale;
        float visualThickness = Mathf.Max(screenReferenceThickness * Mathf.Max(screenRibbonThicknessScale, 0.08f), 0.018f);
        float visualFeather = Mathf.Max(screenReferenceFeather * 0.65f, 0.03f);
        float visualInfluence = useVisualRibbonMask ? Mathf.Clamp01(screenReferenceStrength * screenRibbonClawFollow) : 0.0f;
        clawInstancingCompute.SetFloat("_UseVisualRibbonMask", useVisualRibbonMask ? 1.0f : 0.0f);
        clawInstancingCompute.SetFloat("_VisualRibbonInfluence", visualInfluence);
        clawInstancingCompute.SetVector("_VisualRibbonCenter", new Vector4(visualCenter.x, visualCenter.y, 0f, 0f));
        clawInstancingCompute.SetFloat("_VisualRibbonHalfWidth", visualHalfWidth);
        clawInstancingCompute.SetFloat("_VisualRibbonBend", visualBend);
        clawInstancingCompute.SetFloat("_VisualRibbonTilt", visualTilt);
        clawInstancingCompute.SetFloat("_VisualRibbonThickness", visualThickness);
        clawInstancingCompute.SetFloat("_VisualRibbonFeather", visualFeather);
    }

    /// <summary>
    /// 構図マスクを移動する波頭へ追従させつつ、画面の焦点から大きく離れないようにする。
    /// </summary>
    private Vector3 UpdateCompositionCenter(Vector2 dominantDirection)
    {
        Vector3 focusCenter = _lastFocusCenter;
        Vector3 dominant = new Vector3(dominantDirection.x, 0.0f, dominantDirection.y);
        if (dominant.sqrMagnitude < 0.0001f)
            dominant = Vector3.forward;
        dominant.Normalize();

        bool shouldDrift = driftCompositionWithCrests && Application.isPlaying;
        if (!_hasCompositionCenter || !shouldDrift)
        {
            _lastCompositionCenter = focusCenter;
            _hasCompositionCenter = true;
            return _lastCompositionCenter;
        }

        float dt = Mathf.Max(Time.deltaTime, 0.0001f);
        _lastCompositionCenter += dominant * (compositionDriftSpeed * dt);

        float returnT = 1.0f - Mathf.Exp(-compositionReturnRate * dt);
        _lastCompositionCenter = Vector3.Lerp(_lastCompositionCenter, focusCenter, returnT);
        _lastCompositionCenter.y = focusCenter.y;

        Vector3 offset = _lastCompositionCenter - focusCenter;
        offset.y = 0.0f;
        float maxOffset = Mathf.Max(1.0f, compositionMaxDriftFromFocus);
        if (offset.sqrMagnitude > maxOffset * maxOffset)
            _lastCompositionCenter = focusCenter + offset.normalized * maxOffset;

        return _lastCompositionCenter;
    }

    /// <summary>
    /// 計数値を消去し、間接描画引数を初期化するリセット処理を実行する。
    /// 生成処理の前に GPU 上の状態を整える。
    /// </summary>
    private void DispatchResetKernel()
    {
        clawInstancingCompute.SetBuffer(_resetKernel, "_ClawCounter", _counterBuffer);
        clawInstancingCompute.SetBuffer(_resetKernel, "_ArgsBuffer", _argsBuffer);
        clawInstancingCompute.SetBuffer(_resetKernel, "_UnderlayArgsBuffer", _underlayArgsBuffer);
        clawInstancingCompute.Dispatch(_resetKernel, 1, 1, 1);
    }

    /// <summary>
    /// 走査格子の全体にわたって、爪状白波を生成する主処理を実行する。
    /// 各走査セルから波頭の候補を調べる。
    /// </summary>
    private void DispatchGenerateKernel(RenderTexture clawMask, RenderTexture displacement, RenderTexture slope)
    {
        clawInstancingCompute.SetTexture(_generateKernel, "_ClawMaskTexture", clawMask);
        clawInstancingCompute.SetTexture(_generateKernel, "_DisplacementTexture", displacement);
        clawInstancingCompute.SetTexture(_generateKernel, "_SlopeTexture", slope);
        clawInstancingCompute.SetBuffer(_generateKernel, "_ClawInstances", _instancesBuffer);
        clawInstancingCompute.SetBuffer(_generateKernel, "_ClawCounter", _counterBuffer);
        clawInstancingCompute.SetBuffer(_generateKernel, "_ClawCellState", _cellStateBuffer);

        int groups = Mathf.CeilToInt(scanGridSize / (float)GenerateThreadGroupSize);
        clawInstancingCompute.Dispatch(_generateKernel, groups, groups, 1);
    }

    /// <summary>
    /// 生成したインスタンス数を引数バッファへ書き込む最終処理を実行する。
    /// 間接描画で使う個数を確定する。
    /// </summary>
    private void DispatchFinalizeKernel()
    {
        clawInstancingCompute.SetBuffer(_finalizeKernel, "_ClawCounter", _counterBuffer);
        clawInstancingCompute.SetBuffer(_finalizeKernel, "_ArgsBuffer", _argsBuffer);
        clawInstancingCompute.SetBuffer(_finalizeKernel, "_UnderlayArgsBuffer", _underlayArgsBuffer);
        clawInstancingCompute.Dispatch(_finalizeKernel, 1, 1, 1);
    }

    private static bool IsFinite(Vector4 value)
    {
        return IsFinite(value.x) && IsFinite(value.y) && IsFinite(value.z) && IsFinite(value.w);
    }

    private static bool IsFinite(float value)
    {
        return !float.IsNaN(value) && !float.IsInfinity(value);
    }

    private static float saturate(float value)
    {
        return Mathf.Clamp01(value);
    }

    private static float smoothstep(float edge0, float edge1, float value)
    {
        float t = Mathf.Clamp01((value - edge0) / Mathf.Max(edge1 - edge0, 0.0001f));
        return t * t * (3.0f - 2.0f * t);
    }

    /// <summary>
    /// 海面の風向角を、波頭の探索に使う正規化した XZ 平面上の方向へ変換する。
    /// 波の方向を平面上の単位ベクトルとして扱う。
    /// </summary>
    private static Vector2 WindDirectionToXZ(float degrees)
    {
        float radians = degrees * Mathf.Deg2Rad;
        Vector2 dir = new Vector2(Mathf.Cos(radians), Mathf.Sin(radians));
        if (dir.sqrMagnitude < 0.0001f)
            return Vector2.up;
        return dir.normalized;
    }
}
