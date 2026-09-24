#ifndef GREATWAVE_PLAYBACK18_LIGHTING_INCLUDED
#define GREATWAVE_PLAYBACK18_LIGHTING_INCLUDED
// AlembicとVATの見え方を比較するために同じ照明式を使う。
// 浮世絵表現・物理的な水の描画・影・XRの検証用シェーダーではない。
float4 Playback18Shade(float3 worldNormal, float4 color, float3 lightDirection, float ambient)
{
    float light = ambient + (1.0 - ambient) *
        saturate(dot(normalize(worldNormal), normalize(lightDirection)));
    return float4(color.rgb * light, color.a);
}
#endif
