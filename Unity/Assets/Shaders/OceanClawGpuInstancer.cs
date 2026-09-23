using UnityEngine;

/// <summary>
/// Drives the GPU-only Hokusai claw system: scan the FFT wave, emit indirect instances,
/// and draw the claw mesh without creating per-claw GameObjects.
/// 驱动 GPU 版本的北斋浪爪系统：扫描 FFT 海浪、生成间接实例，并在不创建单个 GameObject 的情况下绘制爪形。
/// </summary>
[DefaultExecutionOrder(100)]
public partial class OceanClawGpuInstancer : MonoBehaviour
{
    private const int InstanceStride = sizeof(float) * 4 * 5;
    private const int IndirectArgsCount = 5;
    private const int CellStateStride = sizeof(float) * 4;
    private const int GenerateThreadGroupSize = 8;

    [Header("References")]
    public FFTOcean_Script oceanScript;
    public ComputeShader clawInstancingCompute;
    public Mesh clawMesh;
    public Material clawMaterial;

    [Header("Generation")]
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

    [Header("Visibility Focus")]
    [Tooltip("Keeps the limited GPU instance budget near the camera-facing wave field.")]
    public bool focusSpawnsNearCamera = true;
    [Tooltip("Optional transform used as the center/forward reference for visible claw spawning. Camera.main is used when this is empty.")]
    public Transform spawnFocus;
    public float focusDistance = 95f;
    public float focusRadius = 220f;
    public float focusFeather = 90f;

    [Header("Hokusai Composition")]
    [Tooltip("Biases claw spawning toward one dominant crest group plus a smaller side group, like The Great Wave composition.")]
    public bool useCompositionBias = true;
    [Range(0f, 1f)]
    public float compositionStrength = 0.82f;
    [Tooltip("Main crest center relative to the focus center. X = lateral across the crest, Y = forward along the wave direction.")]
    public Vector2 mainCrestOffset = new Vector2(18f, 32f);
    [Tooltip("Main crest elliptical radius. X = lateral width, Y = forward depth.")]
    public Vector2 mainCrestRadius = new Vector2(28f, 18f);
    [Range(0f, 2.5f)]
    public float mainCrestBoost = 1.75f;
    [Tooltip("Secondary crest center relative to the focus center. X = lateral across the crest, Y = forward along the wave direction.")]
    public Vector2 sideCrestOffset = new Vector2(22f, -35f);
    [Tooltip("Secondary crest elliptical radius. X = lateral width, Y = forward depth.")]
    public Vector2 sideCrestRadius = new Vector2(18f, 12f);
    [Range(0f, 2.5f)]
    public float sideCrestBoost = 0.65f;
    [Range(0f, 1f)]
    public float backgroundCrestFloor = 0.30f;
    [Tooltip("Spawn-density multiplier outside the main and side crest ellipses. Lower values keep background foam from stealing the instance budget.")]
    [Range(0f, 1f)]
    public float backgroundDensityScale = 0.08f;
    [Tooltip("Scale multiplier for claws outside the main and side crest ellipses, keeping stray background crests subordinate to the painting composition.")]
    [Range(0.1f, 1f)]
    public float backgroundClawScale = 0.42f;
    [Tooltip("Shapes the dominant crest ellipse into a Great-Wave-like curved ribbon instead of a filled blob.")]
    public bool useReferenceCrestArc = true;
    [Tooltip("How strongly the dominant crest follows the reference arc mask.")]
    [Range(0f, 1f)]
    public float referenceArcStrength = 0.85f;
    [Tooltip("Forward lift of the arc center. Positive values raise the middle of the crest ribbon.")]
    public float referenceArcForwardBend = 18f;
    [Tooltip("Diagonal curl of the arc. Negative/positive values tilt the claw ribbon across the wave.")]
    public float referenceArcCurl = -10f;
    [Tooltip("Half-width of the reference arc ribbon in world meters.")]
    [Range(0.5f, 30f)]
    public float referenceArcWidth = 7f;
    [Tooltip("Soft falloff outside the reference arc ribbon.")]
    [Range(0.5f, 30f)]
    public float referenceArcFeather = 8f;
    [Tooltip("Skews dedicated crest sampling along the reference arc. Negative favors the curling shoulder; positive favors the trailing side.")]
    [Range(-1f, 1f)]
    public float referenceArcDensityBias = -0.25f;
    [Tooltip("Extra size and foam emphasis on the dense curling shoulder of the reference arc.")]
    [Range(0f, 1f)]
    public float referenceArcShoulderSizeBoost = 0.28f;
    [Tooltip("Lets the curling shoulder unfold a little earlier while preserving the life-driven growth curve.")]
    [Range(0f, 1f)]
    public float referenceArcShoulderOpenBoost = 0.22f;
    [Tooltip("How strongly the reference arc imposes the Great-Wave size and reveal profile.")]
    [Range(0f, 1f)]
    public float hokusaiArcProfileStrength = 0.72f;
    [Tooltip("Extra broadening for the dense curling shoulder of the arc.")]
    [Range(0f, 1.5f)]
    public float hokusaiCurlShoulderBoost = 0.42f;
    [Tooltip("Scale multiplier for the trailing tail side of the foam arc.")]
    [Range(0.1f, 1f)]
    public float hokusaiTailScale = 0.52f;
    [Tooltip("Extra life delay for the trailing tail side so foam fingers unfold progressively.")]
    [Range(0f, 0.5f)]
    public float hokusaiTailRevealDelay = 0.18f;
    [Tooltip("Alternates large shoulder lobes, smaller inner teeth, and tail gaps along the Hokusai reference arc.")]
    [Range(0f, 1f)]
    public float hokusaiArcLobeContrast = 0.42f;
    [Tooltip("Keeps small reference-arc foam teeth in the draw buffer longer so they fade through life/growth alpha instead of popping off.")]
    [Range(0f, 1f)]
    public float hokusaiWeakToothRetention = 0.62f;
    [Tooltip("Adds a camera-space Great-Wave arc gate so the dominant crest stays in a stable screen composition.")]
    public bool useScreenReferenceMask = true;
    [Tooltip("How strongly the camera-space reference arc influences the dominant crest distribution.")]
    [Range(0f, 1f)]
    public float screenReferenceStrength = 0.32f;
    [Tooltip("Viewport center of the visible reference arc. X/Y are normalized screen coordinates.")]
    public Vector2 screenReferenceCenter = new Vector2(0.62f, 0.56f);
    [Tooltip("Half-width of the visible reference arc in normalized screen coordinates.")]
    [Range(0.02f, 0.8f)]
    public float screenReferenceHalfWidth = 0.24f;
    [Tooltip("Vertical bend of the visible reference arc in normalized screen coordinates.")]
    [Range(-0.4f, 0.4f)]
    public float screenReferenceBend = 0.08f;
    [Tooltip("Diagonal tilt of the visible reference arc in normalized screen coordinates.")]
    [Range(-0.4f, 0.4f)]
    public float screenReferenceTilt = -0.03f;
    [Tooltip("Half-thickness of the visible reference arc ribbon.")]
    [Range(0.005f, 0.3f)]
    public float screenReferenceThickness = 0.08f;
    [Tooltip("Soft edge of the visible reference arc ribbon.")]
    [Range(0.005f, 0.3f)]
    public float screenReferenceFeather = 0.10f;
    [Tooltip("Lets the composition mask drift with the traveling crest instead of staying fixed in world space.")]
    public bool driftCompositionWithCrests = true;
    [Tooltip("World meters per second used to drift the composition mask along the dominant wave direction.")]
    public float compositionDriftSpeed = 4.4f;
    [Tooltip("How quickly the drifting composition mask is pulled back toward the visible camera focus.")]
    [Range(0f, 4f)]
    public float compositionReturnRate = 0.45f;
    [Tooltip("Maximum XZ distance the drifting composition center may move away from the camera focus.")]
    public float compositionMaxDriftFromFocus = 42f;
    [Tooltip("How much the spawn focus gate follows the drifting composition center.")]
    [Range(0f, 1f)]
    public float compositionFocusGateFollow = 0.90f;
    [Tooltip("Extra scan-density multiplier inside the dominant crest region.")]
    [Range(0f, 5f)]
    public float mainCrestDensityBoost = 1.55f;
    [Tooltip("Extra scan-density multiplier inside the smaller side crest region.")]
    [Range(0f, 5f)]
    public float sideCrestDensityBoost = 0.4f;
    [Tooltip("Extra crest-search radius inside the dominant crest region.")]
    [Range(0f, 2f)]
    public float mainCrestSearchBoost = 0.75f;
    [Tooltip("Extra crest-search radius inside the smaller side crest region.")]
    [Range(0f, 2f)]
    public float sideCrestSearchBoost = 0.35f;
    [Tooltip("Fraction of scan cells dedicated to the dominant crest ellipse before random ocean-wide scanning.")]
    [Range(0f, 0.75f)]
    public float mainCrestDedicatedScanShare = 0.030f;
    [Tooltip("Fraction of scan cells dedicated to the smaller side crest ellipse.")]
    [Range(0f, 0.35f)]
    public float sideCrestDedicatedScanShare = 0.005f;

    [Header("Wave Coupling")]
    public float verticalDisplacementStrength = 4.2f;
    public float horizontalDisplacementStrength = 1.85f;
    public float crestAmplification = 0.17f;
    public float crestProbeDistance = 8.5f;
    public float crestHeightBias = 0.08f;
    public float crestHeightRange = 1.05f;
    [Tooltip("How far each spawn slot searches forward/backward to latch onto the local moving crest.")]
    public float crestSearchRadius = 9.0f;
    [Tooltip("How far each spawn slot searches sideways along the crest line.")]
    public float crestSearchLateral = 5.5f;

    [Header("Persistence")]
    [Tooltip("Seconds for a new claw to grow to full size after a crest is detected.")]
    public float lifeRiseTime = 2.3f;
    [Tooltip("Seconds for a claw to shrink away after the crest falls below threshold.")]
    public float lifeFallTime = 16.0f;
    [Range(0f, 1f)]
    public float visibleLifeThreshold = 0.035f;
    [Range(0f, 0.1f)]
    [Tooltip("Lower draw-retention threshold for fade-out tails. Keep below Visible Life Threshold so claws can disappear through shader alpha instead of dropping from the instance buffer.")]
    public float drawLifeThreshold = 0.006f;

    [Header("Crest Tracking / 波峰跟随")]
    [Tooltip("How fast a living claw's anchor drifts along the dominant wave direction (m/s). Match this roughly to the visible wave speed so claws ride their crest. 锚点沿主波向漂移的速度，大致匹配可见波速。")]
    public float crestDriftSpeed = 4.4f;
    [Tooltip("How quickly the drifting anchor re-locks onto the freshly found crest (1/s). Low = smooth but lags, high = accurate but jittery. 锚点向新搜到的波峰重新吸附的速率。")]
    public float crestRelockRate = 1.6f;
    [Tooltip("Life fall-speed multiplier once the crest under a claw has collapsed, so claws dissolve with their wave instead of sinking into the trough. 波峰塌掉后生命值下降的加速倍数，让爪形随波消散而不是沉进波谷。")]
    public float crestLostFallBoost = 1.10f;

    [Header("Organic Layout / 有机排布")]
    [Tooltip("0..1, how strongly cluster members snap onto the curved crest ridge line instead of a straight lateral row. 成员吸附到弯曲波峰脊线的强度（0 = 直线排布）。")]
    [Range(0f, 1f)]
    public float crestCurveFollow = 1.0f;
    [Tooltip("Members fan outward across the cluster like spreading fingers (degrees across the whole cluster). 整簇成员像张开的手指一样向外扇形展开的总角度。")]
    [Range(0f, 60f)]
    public float clusterFanDegrees = 38f;
    [Tooltip("Sink each claw's root into the wave by this fraction of its height, so fingers grow out of the crest mass. 根部埋入浪体的高度比例，让手指像从波峰里长出来。")]
    [Range(0f, 0.4f)]
    public float rootEmbedFraction = 0.012f;
    [Tooltip("Small world-space lift that keeps the root visible while still attached to the crest. X = folded, Y = fully open.")]
    public Vector2 rootLiftRangeMeters = new Vector2(0.18f, 0.45f);
    [Tooltip("Maximum world-space depth that the root may sink into the wave. This is capped in meters, not by model scale, to avoid burying large claws.")]
    [Range(0f, 1f)]
    public float rootEmbedMaxMeters = 0.12f;
    [Tooltip("0..1, size hierarchy across a cluster: 1 = strong center-big falloff like the painting, 0 = uniform sizes. 簇内“中间大两侧小”的层级强度。")]
    [Range(0f, 1f)]
    public float sizeHierarchy = 0.92f;
    [Tooltip("Pushes the middle of each claw cluster farther over the wave lip so the group forms a curved Hokusai-style crest instead of a flat row.")]
    [Range(0f, 12f)]
    public float clusterArcForwardOffset = 5.0f;
    [Tooltip("Extra lateral spread for members inside the dominant crest group.")]
    [Range(1f, 2.5f)]
    public float mainFanLateralScale = 1.45f;
    [Tooltip("Extra forward arc spread for members inside the dominant crest group.")]
    [Range(1f, 2f)]
    public float mainFanForwardScale = 1.22f;
    [Tooltip("Extra outward yaw fan for members inside the dominant crest group.")]
    [Range(0f, 1.5f)]
    public float mainFanYawBoost = 0.45f;
    [Tooltip("Pulls individual members of the dominant crest back toward the camera-space reference arc, so tips form one readable foam ribbon.")]
    [Range(0f, 1f)]
    public float mainMemberScreenArcFollow = 0.0f;
    [Tooltip("Flattens dominant-crest claws toward the wave sheet so large tips read as foam instead of upright objects.")]
    [Range(0f, 1f)]
    public float foamSheetFlatten = 0.42f;
    [Tooltip("Adds width/depth to flattened dominant-crest foam tips, preserving visible mass while reducing vertical object feel.")]
    [Range(0f, 1f)]
    public float foamSheetWidthBoost = 0.35f;

    [Header("Crest Clusters")]
    [Range(1, 12)]
    public int minClawsPerCrest = 3;
    [Range(1, 12)]
    public int maxClawsPerCrest = 10;
    [Tooltip("Caps members emitted by main reference-ribbon cells so the instance budget spreads along the whole Great-Wave arc.")]
    [Range(2, 12)]
    public int maxRibbonClawsPerCrest = 4;
    public float clusterLateralSpacing = 5.8f;
    public float clusterForwardJitter = 2.7f;
    public float clusterVerticalJitter = 0.16f;
    [Range(0f, 2f)]
    public float clusterLateralRandomness = 0.75f;
    [Range(0f, 2f)]
    public float clusterForwardRandomness = 0.90f;

    [Header("Claw Shape")]
    public Vector2 clawScaleRange = new Vector2(125f, 345f);
    public Vector3 clawScaleMultiplier = new Vector3(2.05f, 0.22f, 1.05f);
    [Range(0f, 0.75f)]
    public float scaleRandomness = 0.38f;
    [Tooltip("Small lift for the claw root above the detected crest. The mesh anchor is still locked to the wave peak.")]
    public float verticalOffset = 0.12f;
    public bool localYPointsTowardTip = false;
    [Range(0f, 1f)]
    public float forwardFromSlope = 0.0f;
    [Range(0f, 90f)]
    public float yawJitterDegrees = 11f;
    [Range(0f, 4f)]
    public float normalInfluence = 1.55f;
    [Tooltip("How much the claw orientation follows the animated water normal. Keep low to prevent visible spinning.")]
    [Range(0f, 1f)]
    public float surfaceNormalBlend = 0.0f;
    [Tooltip("How much the outward-pointing claw tip droops from horizontal toward the wave face.")]
    [Range(0f, 1.5f)]
    public float tipDownwardBias = 0.30f;

    [Header("Growth Animation")]
    [Tooltip("How far the claw folds back into the wave while the crest is still forming or falling.")]
    [Range(0f, 120f)]
    public float growthFoldDegrees = 96f;
    [Tooltip("Minimum model scale while the claw is just beginning to emerge.")]
    [Range(0.01f, 0.6f)]
    public float growthMinScale = 0.08f;
    [Tooltip("Higher values make the early claw rotation linger near the hidden tip state.")]
    [Range(0.2f, 4f)]
    public float growthCurvePower = 2.7f;
    [Tooltip("Per-claw delay variation inside a crest cluster, so the claws unfold one after another.")]
    [Range(0f, 0.85f)]
    public float growthStagger = 0.58f;
    [Tooltip("Minimum life-driven unfold for the main screen-locked foam ribbon, preventing the reference crest from collapsing into tiny dots between height peaks.")]
    [Range(0f, 1f)]
    public float ribbonOpenFloor = 0.34f;
    [Tooltip("Reduces random unfold delay on the main reference ribbon so it reads as one continuous crest while still growing gradually.")]
    [Range(0f, 1f)]
    public float ribbonDelayCompression = 0.55f;
    [Tooltip("How close to the strongest crest score the wave must be before claws can fully unfold.")]
    [Range(0f, 1f)]
    public float peakOpenThreshold = 0.88f;
    [Tooltip("Width of the crest-score band used for the final part of the unfolding motion.")]
    [Range(0.01f, 0.5f)]
    public float peakOpenFeather = 0.12f;
    [Tooltip("Higher values make full extension happen only at the very top of the crest.")]
    [Range(0.5f, 6f)]
    public float peakOpenPower = 3.1f;

    [Header("Crest Lip Filtering")]
    [Tooltip("Minimum member-level lip strength before an individual claw can read as a full foam finger.")]
    [Range(0f, 1f)]
    public float memberLipThreshold = 0.34f;
    [Tooltip("Softness of the member-level lip gate. Larger values fade low wave-face claws instead of popping them off.")]
    [Range(0.01f, 1f)]
    public float memberLipFeather = 0.30f;
    [Tooltip("Scale multiplier for members that have drifted down onto the lower wave face.")]
    [Range(0.02f, 0.8f)]
    public float lowLipScale = 0.20f;
    [Tooltip("Unfold multiplier for low-lip members, keeping tails folded into the wave.")]
    [Range(0f, 1f)]
    public float lowLipOpenScale = 0.18f;
    [Tooltip("Extra size for members sitting on the strongest crest lip.")]
    [Range(1f, 2.5f)]
    public float highLipScaleBoost = 1.32f;
    [Tooltip("Extra foam tint score for high-lip members.")]
    [Range(0f, 1f)]
    public float highLipFoamBoost = 0.35f;
    [Tooltip("Skips drawing tiny folded low-lip members while preserving their lifecycle state.")]
    public bool skipHiddenLowLipInstances = true;
    [Tooltip("Low-lip members below this visibility and scale/open thresholds are not appended to the draw buffer.")]
    [Range(0f, 1f)]
    public float hiddenLipSkipVisibility = 0.18f;
    [Range(0f, 0.5f)]
    public float hiddenLipSkipOpen = 0.12f;
    [Range(0f, 80f)]
    public float hiddenLipSkipScaleY = 12f;

    [Header("Material")]
    public Color baseColor = new Color(0.93f, 0.91f, 0.84f, 1f);
    public Color highScoreColor = new Color(0.99f, 0.98f, 0.94f, 1f);
    public Color rootBlendColor = new Color(0.50f, 0.66f, 0.74f, 1f);
    public Color outlineInkColor = new Color(0.025f, 0.060f, 0.118f, 1f);
    [Range(0f, 1f)]
    public float outlineStrength = 0.86f;
    [Tooltip("Solidity of the THIN dark ink rim around each claw body (woodblock linework). User wants a crisp 细墨线勾边 so the claw reads as a defined white shape — NOT a fat black hull (the earlier '黑色的条' regression).")]
    [Range(0f, 1f)]
    public float outlineHullAlpha = 0.85f;
    [Tooltip("How far the outline hull expands past the claw silhouette. Keep SMALL = hairline; large = the black-blob halo the user disliked.")]
    [Range(0f, 0.4f)]
    public float outlineHullExpand = 0.13f;
    [Range(0f, 0.4f)]
    public float outlineHullTipExpand = 0.09f;
    [Tooltip("Direct render-size multiply for the claw, fed to the shader as _ClawSizeBoost. The compute normalizes clawScaleRange/backgroundClawScale to a ~fixed per-instance scale, so THIS is the working lever to enlarge claws so they read at camera distance (1 = native ~speck, 3 = clearly visible).")]
    [Range(0.5f, 8f)]
    public float clawSizeBoost = 3.0f;
    [Range(0f, 1f)]
    public float contourLineStrength = 0.78f;
    [Range(0.005f, 0.18f)]
    public float contourLineWidth = 0.060f;
    public Color clawGreenShadowColor = new Color(0.43f, 0.64f, 0.54f, 1f);
    [Range(0f, 1f)]
    public float clawGreenShadowStrength = 0.74f;
    [Tooltip("Fraction of generated crest instances that render as visible claw tips. The hidden instances still feed the crest foam plate.")]
    [Range(0f, 1f)]
    public float visibleClawFraction = 1.0f;
    [Tooltip("Overall opacity for the visible claw-tip pass.")]
    [Range(0f, 1f)]
    public float visibleClawAlpha = 1.0f;
    [Range(0.02f, 0.8f)]
    public float rootFadeWidth = 0.34f;
    [Range(0f, 1f)]
    public float rootAlpha = 0.12f;
    [Header("Procedural Foam Fingers")]
    [Tooltip("Draws the visible claw pass with a flat generated foam-finger mesh instead of the faceted source claw mesh.")]
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
    [Tooltip("Turns flattened print-foam fingers toward the camera so they read as woodblock shapes instead of edge-on slivers.")]
    [Range(0f, 1f)]
    public float foamFingerCameraBillboard = 1.0f;
    [Header("Foam Ribbon Underlay")]
    [Tooltip("Draws a soft expanded foam pass before the individual claws, helping the main crest read as one continuous woodblock silhouette.")]
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
    [Header("Screen Reference Foam Ribbon")]
    [Tooltip("Draws the continuous paper-white crest plate that the foam fingers grow from.")]
    public bool drawScreenReferenceFoamRibbon = false;
    public Color screenRibbonColor = new Color(1.00f, 0.985f, 0.930f, 0.86f);
    public Color screenRibbonEdgeColor = new Color(0.52f, 0.70f, 0.60f, 0.40f);
    [Range(0f, 1f)]
    public float screenRibbonAlpha = 0.0f;
    [Tooltip("Viewport offset shared by the drawn ribbon and the compute-side claw attraction.")]
    public Vector2 screenRibbonCenterOffset = new Vector2(-0.03f, 0.02f);
    [Range(0.25f, 1.5f)]
    public float screenRibbonHalfWidthScale = 0.95f;
    [Range(0f, 1.5f)]
    public float screenRibbonBendScale = 1.10f;
    [Range(0f, 1.5f)]
    public float screenRibbonTiltScale = 0.95f;
    [Tooltip("Viewport-space half-thickness multiplier relative to the existing screen reference arc thickness.")]
    [Range(0.05f, 1.2f)]
    public float screenRibbonThicknessScale = 0.58f;
    [Tooltip("World depth from the reference camera where the ribbon is projected. ZTest Always keeps it visually locked to the wave face.")]
    [Range(10f, 180f)]
    public float screenRibbonDepth = 68f;
    [Range(0f, 1f)]
    public float screenRibbonEdgeBlend = 0.72f;
    [Tooltip("Optional visual-guide attraction. Keep at zero for foam-driven crest placement.")]
    [Range(0f, 1f)]
    public float screenRibbonClawFollow = 0.0f;

    [Header("World Crest Foam Plate")]
    [Tooltip("Builds a world-space white foam plate from the generated crest instances. This follows detected wave crests instead of a fixed screen ribbon.")]
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

    [Header("Debug")]
    public bool logMissingReferences = true;
    [Header("Development Snapshot Export")]
    [Tooltip("Editor/development-only capture path for tuning. Keep disabled for normal gameplay because it performs GPU readbacks and file writes.")]
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
    /// Resolves compute kernels and allocates buffers as soon as the component becomes active.
    /// 组件启用时查找 compute kernel，并提前分配 GPU buffer。
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
    /// Releases all GPU-side allocations owned by this component.
    /// 组件停用时释放由本组件持有的所有 GPU 资源。
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
    /// Keeps Inspector values inside ranges that are safe for compute dispatch and math divisions.
    /// 将 Inspector 参数限制在安全范围内，避免 compute dispatch 或数学计算出现无效值。
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
    /// Runs one frame of GPU claw generation, then submits the indirect draw call.
    /// 每帧执行一次 GPU 爪形生成，然后提交间接绘制调用。
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
    /// Clamps scan, count, density, and height gates used by the generator.
    /// 限制扫描密度、实例数量、生成密度和高度门槛相关参数。
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
    /// Clamps the optional camera/focus gate that keeps instances near the visible wave field.
    /// 限制可选的相机/焦点区域参数，使有限实例数量集中在可见海浪区域。
    /// </summary>
    private void ClampFocusSettings()
    {
        focusDistance = Mathf.Max(0.0f, focusDistance);
        focusRadius = Mathf.Max(1.0f, focusRadius);
        focusFeather = Mathf.Max(0.001f, focusFeather);
    }

    /// <summary>
    /// Clamps composition controls that shape the claw distribution into a dominant crest group.
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
    /// Clamps wave reconstruction values that must stay positive in the compute shader.
    /// 限制 compute shader 重建海浪时必须为正的参数。
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
    /// Clamps the number, spacing, and random scatter of claws within one crest cluster.
    /// 限制单个波峰簇中爪形数量、间距和随机散布范围。
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
    /// Clamps mesh scale and orientation controls for stable visible results.
    /// 限制模型缩放和朝向参数，保证视觉效果稳定。
    /// </summary>
    private void ClampShapeSettings()
    {
        clawScaleRange.x = Mathf.Max(0.01f, clawScaleRange.x);
        clawScaleRange.y = Mathf.Max(clawScaleRange.x, clawScaleRange.y);
        scaleRandomness = Mathf.Clamp(scaleRandomness, 0.0f, 0.75f);
    }

    /// <summary>
    /// Clamps lifecycle and unfolding controls for predictable growth animation.
    /// 限制生命周期和展开动画参数，使爪形生长过程可预测。
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
    /// Clamps member-level lip filtering that folds low wave-face tails into the water.
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
    /// Clamps material controls used for root-to-tip foam blending.
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
    /// Verifies all required Unity assets and compute kernels are available before dispatching.
    /// 在 dispatch 前确认 Unity 资源和 compute kernel 都已经正确配置。
    /// </summary>
    private bool HasRequiredReferences()
    {
        if (oceanScript == null)
            oceanScript = UnityEngine.Object.FindAnyObjectByType<FFTOcean_Script>();

        // SELF-HEAL kernel resolution. OnEnable's ResolveKernels() can run before the compute
        // shader is ready after a domain reload / Play-enter: FindKernel then returns -1 with NO
        // exception, and nothing ever retried -> HasRequiredReferences stayed false every frame and
        // the entire claw system silently never initialized (buffers null, zero claws drawn). Retry
        // here (called each Update) until the kernels resolve; once resolved this is a no-op.
        // 自愈 kernel 解析：域重载/进入 Play 后 OnEnable 的 ResolveKernels 可能在 compute 尚未就绪时运行，
        // FindKernel 返回 -1 且不抛异常，此后从不重试 -> HasRequiredReferences 恒为 false，爪形系统静默不初始化。
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
            Debug.LogWarning("[OceanClawGpuInstancer] Missing reference. Assign ocean, compute shader, mesh, and instanced material.");
            _reportedMissingReferences = true;
        }

        return ok;
    }

    /// <summary>
    /// Finds the three kernels used by the GPU pipeline: reset, generate, and finalize arguments.
    /// 查找 GPU 流程使用的三个 kernel：重置、生成、整理间接绘制参数。
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
            Debug.LogError($"[OceanClawGpuInstancer] Kernel lookup failed: {ex.Message}");
        }
    }

    /// <summary>
    /// Allocates or resizes GPU buffers when the instance budget or scan grid changes.
    /// 当实例上限或扫描网格变化时，分配或重建 GPU buffer。
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
        // Two float4 slots per scan cell: slot 0 = lifecycle, slot 1 = crest-locked anchor XZ.
        // 每个扫描格两个 float4：槽 0 = 生命周期，槽 1 = 锁定波峰的锚点 XZ。
        _cellStateBuffer = new ComputeBuffer(_cellStateCapacity * 2, CellStateStride, ComputeBufferType.Structured);

        // A fresh ComputeBuffer contains undefined GPU memory; the compute shader reads
        // state.w as an "initialized" flag, so garbage could resurrect random cells with
        // bogus life values. Zero-fill once so every cell starts in a known-dead state.
        // 新建的 ComputeBuffer 内容是未定义的 GPU 内存，compute shader 会把 state.w 当作
        // “已初始化”标记读取，垃圾数据可能让随机格子带着错误生命值复活，这里统一清零。
        _cellStateBuffer.SetData(new Vector4[_cellStateCapacity * 2]);
    }

    /// <summary>
    /// Releases compute buffers and clears capacity bookkeeping.
    /// 释放 compute buffer，并清空容量记录。
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
    /// Executes the reset, generation, and argument-finalization compute passes.
    /// 依次执行重置、实例生成、间接绘制参数整理三个 compute pass。
    /// </summary>
    private void DispatchInstancing(RenderTexture clawMask, RenderTexture displacement, RenderTexture slope)
    {
        // CS_Reset writes all five indirect-args values on the GPU every frame, so the
        // previous per-frame _argsBuffer.SetData upload (and its array allocation) was redundant.
        // CS_Reset 每帧都会在 GPU 上写入全部 5 个间接绘制参数，之前每帧的 SetData 上传
        // （以及它的数组分配）是多余的，已移除。
        Vector2 dominantDirection = WindDirectionToXZ(oceanScript.DisplaySpectrum0.windDirection);
        Vector3 oceanPosition = oceanScript.transform.position;

        SetComputeParams(clawMask.width, dominantDirection, oceanPosition);
        DispatchResetKernel();
        DispatchGenerateKernel(clawMask, displacement, slope);
        DispatchFinalizeKernel();
    }

    /// <summary>
    /// Uploads all per-frame values used by the compute shader.
    /// 上传 compute shader 每帧需要的所有参数。
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
    /// Sends mesh draw metadata and scan dimensions to the compute shader.
    /// 将网格绘制信息和扫描尺寸传给 compute shader。
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
    /// Sends FFT tile data so the compute shader can reconstruct the same visible wave surface.
    /// 传递 FFT tile 数据，使 compute shader 能重建和画面一致的海浪表面。
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
    /// Sends threshold and focus settings that decide whether a crest is allowed to spawn claws.
    /// 传递阈值和焦点区域参数，用于判断某个波峰是否允许生成爪形。
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
    /// Sends mesh scale, anchor, and orientation controls used to place each claw on the wave crest.
    /// 传递模型缩放、锚点和朝向控制参数，用于把每个爪形贴到波峰上。
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
    /// Sends persistence timings that keep claws alive long enough to grow and fade naturally.
    /// 传递生命周期参数，让爪形能自然生长和消失，而不是闪烁。
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
    /// Sends cluster layout controls: how many claws per crest and how randomly they are distributed.
    /// 传递簇布局参数：每个波峰有多少爪形，以及它们的随机分布方式。
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
    /// Sends unfolding controls so claws fully open only when their crest is near its strongest point.
    /// 传递展开动画参数，使爪形只在波峰接近最高点时完全展开。
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
    /// Sends per-member filtering so lower wave-face claws shrink/fold while crest lips stay bold.
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
    /// Sends the visible wave deformation strengths used by the claw compute shader.
    /// 传递当前可见海浪的形变强度，保证爪形位置贴合实际波峰。
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
    /// Computes and uploads the focus gate that spends the instance budget near the camera view.
    /// 计算并上传焦点区域，使有限实例数量优先用于相机附近的可见区域。
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
    /// Sends the stable spatial weights that form one main crest group and a smaller side group.
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
    /// Sends the main camera projection used to keep the dominant crest near the reference image composition.
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
    /// Keeps the composition mask riding the traveling crest while gently anchoring it to the camera view.
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
    /// Dispatches the reset pass that clears counters and initializes indirect draw arguments.
    /// 执行重置 pass，清空计数器并初始化间接绘制参数。
    /// </summary>
    private void DispatchResetKernel()
    {
        clawInstancingCompute.SetBuffer(_resetKernel, "_ClawCounter", _counterBuffer);
        clawInstancingCompute.SetBuffer(_resetKernel, "_ArgsBuffer", _argsBuffer);
        clawInstancingCompute.SetBuffer(_resetKernel, "_UnderlayArgsBuffer", _underlayArgsBuffer);
        clawInstancingCompute.Dispatch(_resetKernel, 1, 1, 1);
    }

    /// <summary>
    /// Dispatches the main generation pass over the scan grid.
    /// 在扫描网格上执行主要的爪形生成 pass。
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
    /// Dispatches the final pass that copies the generated instance count into the args buffer.
    /// 执行最后的 pass，将生成实例数量写入间接绘制参数。
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
    /// Converts the ocean wind angle into a normalized XZ direction used for crest search.
    /// 将海浪风向角转换为 XZ 平面方向，用于沿波峰方向搜索。
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
