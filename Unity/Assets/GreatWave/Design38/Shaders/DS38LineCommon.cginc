// 設計38：輪郭線（反転シェル）の共通部。シート用（DS38 Outline Keypose）と爪用（DS38 Outline Mesh）が同じ線幅の決まりを使う。
// 線幅（押し出し幅、m）＝ max( min(d × _LineAngle, _MaxWidth), d × θpx )
//   d：中心眼から頂点までの距離（Mock の両眼の描画では大域の _DS38EyeOverride（w = 1）を中心眼として使う。SPI の立体視では両眼の平均）。
//   _LineAngle：線の角幅（rad。設計27 の外殻線 v0 と同じ 0.0012866）。
//   _MaxWidth：世界寸法の上限（m。設計27 と同じ 0.3）。遠くの線が太りすぎないための上限。
//   θpx = _MinPx × 1 画素の角（今のカメラの射影と描く先の高さから。2 / (|P11| × 高さ)）：遠くで線が 1 画素より細くなって切れ、コマごとに点滅するのを防ぐ画素の下限。
//   設計27 の外殻線 v0 の世界寸法の下限（_MinWidth 0.05 m）は外した：近くでは 5 cm のまま画面で太る（座席の 80° の視野で 5 m 先なら約 6 画素）ので、
//   近くでも線の角幅は max(_LineAngle, θpx) を超えない（近くで太りすぎない）。
// 原画視点の扱い（_DS38PaintCamPos・_DS38PaintFade）：中心眼が原画のカメラの位置から r0 以内なら重み 0、r1 以上なら 1（その間は線形）。
//   シートは、原画視点で原画にない線（t* の原画視点で主役波の輪郭より 4 画素より内側に出た線の頂点、_DS38LineMask = 0）を重み < 0.5 で描かない。
//   爪は重み < 0.5 で描かない（原画視点では焼き込みの色面の爪の模様が線を担う。設計36 で爪は原画視点で原画の色区になる）。
// 検査用の出力（大域）：_AF28IdMode = 1 でマゼンタ（設計27 からの線の ID）、_DS38LineCoordMode = 1 で (10 + シートの番号, 列, 行, 中心眼からの距離) の浮動小数（面の色は 1 以下なので区別できる）。
#ifndef GREATWAVE_DS38_LINE_COMMON_INCLUDED
#define GREATWAVE_DS38_LINE_COMMON_INCLUDED

float4 _DS38EyeOverride;   // xyz = 中心眼、w = 1 で使う（Mock の両眼）
float4 _DS38PaintCamPos;   // xyz = 原画のカメラの位置
float4 _DS38PaintFade;     // x = r0、y = r1（m）。y ≤ x なら重みはいつも 1
float _DS38LineCoordMode;
float _AF28IdMode;

float3 DS38Eye()
{
    if (_DS38EyeOverride.w > 0.5) return _DS38EyeOverride.xyz;
#if defined(USING_STEREO_MATRICES)
    return 0.5 * (unity_StereoWorldSpaceCameraPos[0] + unity_StereoWorldSpaceCameraPos[1]);
#else
    return _WorldSpaceCameraPos;
#endif
}

// 1 画素の角（rad）。画面の中心の値
float DS38PixelAngle()
{
    float p11 = abs(UNITY_MATRIX_P[1][1]);
    float h = max(_ScreenParams.y, 1.0);
    return 2.0 / (max(p11, 1e-4) * h);
}

float DS38Width(float d, float lineAngle, float maxWidth, float minPx)
{
    return max(min(d * lineAngle, maxWidth), d * minPx * DS38PixelAngle());
}

// 原画視点からの離れの重み（0 = 原画のカメラの所、1 = 離れた所）
float DS38PaintWeight()
{
    if (_DS38PaintFade.y <= _DS38PaintFade.x) return 1.0;
    float e = distance(DS38Eye(), _DS38PaintCamPos.xyz);
    return saturate((e - _DS38PaintFade.x) / (_DS38PaintFade.y - _DS38PaintFade.x));
}

// 設計38 修正の回（進行役の検査の後の 1 回、Q26）：押し出した反転シェルを、中心眼から見て奥へ押し下げる量（m）。
//   押し下げ＝ k × 線幅（k = _DS38PushBack。材質ごと）。頂点の法線（6 つの三角形の平均）で押し出すと、面が視線に浅い角度の所（粗い格子の稜線の階段など）で
//   裏を向く三角形の頂点が目の側へ動き、自分の面や隣の面の上に細い楔の線（棘・扇）として出て、コマごと・目ごとに出入りした。
//   k ≥ 1 なら押し出しの目の側への成分（≤ 線幅）を打ち消す（本当の輪郭の外に出る線は、後ろが空か遠い面なので残る）。
//   paintScale = 1 の材質（主役波）は原画視点の重み（DS38PaintWeight）を掛け、原画視点（重み 0）では押し下げない（原画視点の描画を変えない）。
float3 DS38PushBackOffset(float3 w, float width, float k, float paintScale)
{
    if (k <= 0.0) return float3(0, 0, 0);
    float3 v = DS38Eye() - w;
    float l = length(v);
    if (l < 1e-6) return float3(0, 0, 0);
    float s = k * width * (paintScale > 0.5 ? DS38PaintWeight() : 1.0);
    return -(v / l) * s;
}

#endif
