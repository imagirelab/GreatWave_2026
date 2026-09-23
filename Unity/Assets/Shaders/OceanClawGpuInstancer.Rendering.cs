using UnityEngine;
using UnityEngine.Rendering;

public partial class OceanClawGpuInstancer
{
    private MaterialPropertyBlock _propertyBlock;
    private MaterialPropertyBlock _underlayPropertyBlock;
    private MaterialPropertyBlock _outlinePropertyBlock;
    private Material _runtimeMaterial;
    private Bounds _drawBounds;

    /// <summary>
    /// Sends material data and issues the indirect draw call for all generated claws.
    /// 传递材质数据，并对所有生成的爪形发起间接绘制调用。
    /// </summary>
    private void DrawClaws()
    {
        Material drawMaterial = GetRuntimeMaterial();
        if (drawMaterial == null)
            return;

        // Persisted claw render-size lever. The compute normalizes clawScaleRange/backgroundClawScale
        // to a ~fixed per-instance scale, so the HokusaiClawInstanced vertex shader scales localPos by
        // this global instead (the only reliable way to make claws read at camera distance).
        Shader.SetGlobalFloat("_ClawSizeBoost", clawSizeBoost);

        if (_propertyBlock == null)
            _propertyBlock = new MaterialPropertyBlock();
        if (_underlayPropertyBlock == null)
            _underlayPropertyBlock = new MaterialPropertyBlock();
        if (_outlinePropertyBlock == null)
            _outlinePropertyBlock = new MaterialPropertyBlock();

        Mesh mainMesh = GetMainClawMesh();
        Mesh underlayMesh = GetUnderlayClawMesh();
        if (underlayMesh == null)
            underlayMesh = mainMesh;

        drawMaterial.SetBuffer("_ClawInstances", _instancesBuffer);
        drawMaterial.SetColor("_BaseColor", baseColor);
        drawMaterial.SetColor("_TipColor", highScoreColor);
        drawMaterial.SetColor("_RootBlendColor", rootBlendColor);
        drawMaterial.SetColor("_OutlineColor", outlineInkColor);
        drawMaterial.SetFloat("_OutlineStrength", outlineStrength);
        drawMaterial.SetFloat("_ContourLineStrength", contourLineStrength);
        drawMaterial.SetFloat("_ContourLineWidth", contourLineWidth);
        drawMaterial.SetColor("_GreenShadowColor", clawGreenShadowColor);
        drawMaterial.SetFloat("_GreenShadowStrength", clawGreenShadowStrength);
        drawMaterial.SetFloat("_VisibleFraction", visibleClawFraction);
        drawMaterial.SetFloat("_VisibleAlpha", visibleClawAlpha);
        ApplyVisibleRibbonGate(drawMaterial);
        drawMaterial.SetFloat("_RootFadeWidth", rootFadeWidth);
        drawMaterial.SetFloat("_RootAlpha", rootAlpha);
        drawMaterial.SetFloat("_FoamCutStrength", foamFingerInkCutStrength);
        drawMaterial.SetFloat("_EdgeScallopStrength", foamFingerEdgeBiteStrength);
        drawMaterial.SetColor("_UnderlayColor", foamUnderlayColor);
        drawMaterial.SetFloat("_UnderlayAlpha", foamUnderlayAlpha);
        drawMaterial.SetFloat("_UnderlayExpand", foamUnderlayExpand);
        drawMaterial.SetFloat("_UnderlayTipExpand", foamUnderlayTipExpand);
        drawMaterial.SetFloat("_UnderlayScoreFloor", foamUnderlayScoreFloor);

        _drawBounds = BuildDrawBounds();
        DrawWorldCrestFoamPlate();
        DrawScreenReferenceFoamRibbon();

        if (drawFoamRibbonUnderlay && foamUnderlayAlpha > 0.001f)
        {
            ConfigureClawDrawBlock(_underlayPropertyBlock, true);
            SetMeshRootTipY(_underlayPropertyBlock, drawMaterial, underlayMesh);
            Graphics.DrawMeshInstancedIndirect(
                underlayMesh,
                0,
                drawMaterial,
                _drawBounds,
                _argsBuffer,
                0,
                _underlayPropertyBlock,
                ShadowCastingMode.Off,
                false,
                gameObject.layer);
        }

        ConfigureClawDrawBlock(_outlinePropertyBlock, true);
        _outlinePropertyBlock.SetFloat("_FoamUnderlay", 2.0f);
        _outlinePropertyBlock.SetColor("_UnderlayColor", outlineInkColor);
        // THIN crisp ink rim: a small hull expansion at a solid, FIXED opacity (decoupled from
        // outlineStrength, which now only controls the faint interior ink). The earlier 0.42 expansion
        // made a fat dark halo that read as a black blob; 0.13 is a hairline woodblock outline around a
        // white claw body. This is the painting's linework: white shape, crisp dark edge, nothing filled.
        // 细而清晰的墨线勾边：小幅外扩壳 + 固定实心不透明度（与 outlineStrength 解耦，后者只管淡淡的内部墨线）。
        // 旧的 0.42 外扩成了肥厚黑晕（看着像黑团）；0.13 是白爪身外一圈发丝级版画勾线。白形、利落深边、内不填色。
        // Light outline: the claw is white foam with only a faint edge, NOT a heavy dark hull. The 0.82/0.22
        // hull read as a "black bar" on the white foam (user: 还有黑色的条). A thin, semi-transparent indigo
        // edge keeps the claw as part of the white foam silhouette instead of a dark blob.
        // 轻描边：爪形是白色泡沫、只带很淡的边，而非厚重深壳。旧的 0.82/0.22 在白沫上像"黑色的条"。
        _outlinePropertyBlock.SetFloat("_UnderlayAlpha", outlineHullAlpha);
        _outlinePropertyBlock.SetFloat("_UnderlayExpand", outlineHullExpand);
        _outlinePropertyBlock.SetFloat("_UnderlayTipExpand", outlineHullTipExpand);
        _outlinePropertyBlock.SetFloat("_UnderlayScoreFloor", 0.0f);
        SetMeshRootTipY(_outlinePropertyBlock, drawMaterial, mainMesh);
        Graphics.DrawMeshInstancedIndirect(
            mainMesh,
            0,
            drawMaterial,
            _drawBounds,
            _argsBuffer,
            0,
            _outlinePropertyBlock,
            ShadowCastingMode.Off,
            false,
            gameObject.layer);

        ConfigureClawDrawBlock(_propertyBlock, false);
        SetMeshRootTipY(_propertyBlock, drawMaterial, mainMesh);
        Graphics.DrawMeshInstancedIndirect(
            mainMesh,
            0,
            drawMaterial,
            _drawBounds,
            _argsBuffer,
            0,
            _propertyBlock,
            ShadowCastingMode.On,
            true,
            gameObject.layer);
    }

    /// <summary>
    /// Populates the shared material block for either the soft foam underlay or the crisp claw pass.
    /// </summary>
    private void ConfigureClawDrawBlock(MaterialPropertyBlock block, bool underlay)
    {
        block.Clear();
        block.SetBuffer("_ClawInstances", _instancesBuffer);
        block.SetColor("_BaseColor", baseColor);
        block.SetColor("_TipColor", highScoreColor);
        block.SetColor("_RootBlendColor", rootBlendColor);
        block.SetColor("_OutlineColor", outlineInkColor);
        block.SetFloat("_OutlineStrength", outlineStrength);
        block.SetFloat("_ContourLineStrength", contourLineStrength);
        block.SetFloat("_ContourLineWidth", contourLineWidth);
        block.SetColor("_GreenShadowColor", clawGreenShadowColor);
        block.SetFloat("_GreenShadowStrength", clawGreenShadowStrength);
        block.SetFloat("_VisibleFraction", visibleClawFraction);
        block.SetFloat("_VisibleAlpha", visibleClawAlpha);
        ApplyVisibleRibbonGate(block);
        block.SetFloat("_RootFadeWidth", rootFadeWidth);
        block.SetFloat("_RootAlpha", rootAlpha);
        block.SetFloat("_FoamUnderlay", underlay ? 1.0f : 0.0f);
        block.SetFloat("_FoamCutStrength", foamFingerInkCutStrength);
        block.SetFloat("_EdgeScallopStrength", foamFingerEdgeBiteStrength);
        block.SetColor("_UnderlayColor", foamUnderlayColor);
        block.SetFloat("_UnderlayAlpha", foamUnderlayAlpha);
        block.SetFloat("_UnderlayExpand", foamUnderlayExpand);
        block.SetFloat("_UnderlayTipExpand", foamUnderlayTipExpand);
        block.SetFloat("_UnderlayScoreFloor", foamUnderlayScoreFloor);
    }

    private void ApplyVisibleRibbonGate(Material material)
    {
        if (material == null)
            return;

        Vector4 ribbonParams;
        Vector4 ribbonShape;
        float gate = BuildVisibleRibbonGate(out ribbonParams, out ribbonShape);
        material.SetFloat("_VisibleRibbonGate", gate);
        material.SetVector("_VisibleRibbonParams", ribbonParams);
        material.SetVector("_VisibleRibbonShape", ribbonShape);
    }

    private void ApplyVisibleRibbonGate(MaterialPropertyBlock block)
    {
        if (block == null)
            return;

        Vector4 ribbonParams;
        Vector4 ribbonShape;
        float gate = BuildVisibleRibbonGate(out ribbonParams, out ribbonShape);
        block.SetFloat("_VisibleRibbonGate", gate);
        block.SetVector("_VisibleRibbonParams", ribbonParams);
        block.SetVector("_VisibleRibbonShape", ribbonShape);
    }

    private float BuildVisibleRibbonGate(out Vector4 ribbonParams, out Vector4 ribbonShape)
    {
        Vector2 center = screenReferenceCenter + screenRibbonCenterOffset;
        float halfWidth = Mathf.Max(screenReferenceHalfWidth * screenRibbonHalfWidthScale, 0.001f);
        float thickness = Mathf.Max(screenReferenceThickness * Mathf.Max(0.55f, screenRibbonThicknessScale * 4.0f), 0.045f);
        float feather = Mathf.Max(screenReferenceFeather * 0.62f, 0.035f);
        center.y += thickness * 0.85f;
        ribbonParams = new Vector4(center.x, center.y, halfWidth, thickness);
        ribbonShape = new Vector4(
            screenReferenceBend * screenRibbonBendScale,
            screenReferenceTilt * screenRibbonTiltScale,
            feather,
            0.0f);
        return drawScreenReferenceFoamRibbon && screenRibbonAlpha > 0.001f ? 1.0f : 0.0f;
    }

    /// <summary>
    /// Uploads the mesh local Y values used by the claw shader to fade roots into water.
    /// </summary>
    private void SetMeshRootTipY(MaterialPropertyBlock block, Material material, Mesh mesh)
    {
        if (mesh == null)
            return;

        Bounds bounds = mesh.bounds;
        float rootY = localYPointsTowardTip ? bounds.min.y : bounds.max.y;
        float tipY = localYPointsTowardTip ? bounds.max.y : bounds.min.y;

        block.SetFloat("_RootLocalY", rootY);
        block.SetFloat("_TipLocalY", tipY);
        material.SetFloat("_RootLocalY", rootY);
        material.SetFloat("_TipLocalY", tipY);
    }

    /// <summary>
    /// Builds a conservative world-space bound for indirect rendering and frustum culling.
    /// 构建用于间接绘制和视锥裁剪的保守世界包围盒。
    /// </summary>
    private Bounds BuildDrawBounds()
    {
        float span = focusSpawnsNearCamera
            ? Mathf.Max(80f, (focusRadius + focusFeather) * 2.4f)
            : Mathf.Max(50f, oceanScript.waterMeshLength * 1.1f);
        Vector3 center = focusSpawnsNearCamera
            ? new Vector3(_lastFocusGateCenter.x, oceanScript.transform.position.y + 8f, _lastFocusGateCenter.z)
            : oceanScript.transform.position + Vector3.up * 8f;

        return new Bounds(center, new Vector3(span, 120f, span));
    }

    /// <summary>
    /// Creates a hidden runtime material so this component can enable indirect instancing safely.
    /// 创建隐藏的运行时材质副本，避免直接修改项目里的共享材质资源。
    /// </summary>
    private Material GetRuntimeMaterial()
    {
        if (clawMaterial == null)
            return null;

        if (_runtimeMaterial == null || _runtimeMaterial.shader != clawMaterial.shader)
        {
            ReleaseRuntimeMaterial();
            _runtimeMaterial = new Material(clawMaterial)
            {
                name = clawMaterial.name + " (Runtime Indirect)",
                hideFlags = HideFlags.HideAndDontSave
            };
            _runtimeMaterial.enableInstancing = true;
            _runtimeMaterial.EnableKeyword("HOKUSAI_CLAW_INDIRECT");
        }

        return _runtimeMaterial;
    }

    /// <summary>
    /// Destroys the hidden runtime material using the correct API for Play Mode or Edit Mode.
    /// 根据当前是否在 Play Mode，使用正确 API 销毁隐藏运行时材质。
    /// </summary>
    private void ReleaseRuntimeMaterial()
    {
        if (_runtimeMaterial == null)
            return;

        if (Application.isPlaying)
            Destroy(_runtimeMaterial);
        else
            DestroyImmediate(_runtimeMaterial);
        _runtimeMaterial = null;
    }
}
