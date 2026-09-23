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
    /// 材質データを渡し、生成したすべての爪状白波を間接描画する。
    /// </summary>
    private void DrawClaws()
    {
        Material drawMaterial = GetRuntimeMaterial();
        if (drawMaterial == null)
            return;

        // 描画中の爪状白波の大きさを調整する値。計算側の clawScaleRange と backgroundClawScale は
        // 個体ごとにほぼ固定倍率へ正規化されるため、頂点シェーダー側で localPos にこの共通倍率を適用する。
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
        // 白波の輪郭は細く淡い藍色にする。旧値の外殻拡張0.42では暗い塊に、
        // 不透明度0.82／幅0.22では黒い帯に見えた。
        // outlineStrength は内側の薄い墨線を制御し、外縁の表示とは分ける。
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
    /// 柔らかい白波の下地、または鮮明な爪状部分に使う共通の材質ブロックを設定する。
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
    /// 白波の根元を水面へなじませるため、メッシュのローカル Y 値をシェーダーへ送る。
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
    /// 間接描画と視錐台判定に使う、余裕を持たせたワールド空間の境界箱を作る。
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
    /// 共通の材質資産を書き換えずに間接描画するため、非表示の実行時材質を複製する。
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
    /// 再生中か編集モードかに応じた API で、非表示の実行時材質を破棄する。
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
