using System.Globalization;
using System.Text;
using UnityEngine;

namespace GreatWave.RT48
{
    // RT48：画面と動画の字（計画 §3.6 の字 1〜7）。
    //   ・デスクトップと動画：カメラの子の字（TextMesh、深さを見ずに最後に描く）を画面の左下に小さく出し続ける。
    //     画面外に描く動画（RT48Capture）にも同じ字が入る。H で隠す。VR が動いている時は出さない。
    //   ・VR：始めの 3 s に船首の向きの板に 1〜5 を出し、終わりの板に 1〜7 を全部出す。見ている間は出さない。
    //   ・合成の元の時は、いちばん上に「合成の試しの曲線」と出す。
    public class RT48Captions : MonoBehaviour
    {
        public RT48Playback playback;
        public RT48Rig rig;
        public Camera hudCamera;
        public Transform vrAnchor;            // VR の板を置く所（座席）
        public Material overlayMaterial;      // RT48 Overlay
        public string[] fontNames = { "Yu Gothic UI", "Yu Gothic", "Meiryo", "MS Gothic" };
        public float hudLineFrac = 1f / 46f;  // 1 行の高さ（画面の高さに対して）
        public float vrIntroSeconds = 3f;
        public float vrPanelDistanceM = 2.2f;
        public int wrapChars = 52;

        public const string Cap1Default = "この波は 2 次元の断面の計算（FLIP42 R3、粒子 0.25 m、重力だけ）を横に並べたもので、長さの向きにどこも同じ形です";
        public const string Cap2 = "オフラインで計算した結果の再生で、水の動きは毎フレーム計算していません";
        public const string Cap5 = "唇の大きさは、細かさで落ち着くかをまだ判定できていません";
        public const string Cap6 = "ここから 24 コマ/秒、補間なし";
        public const string Cap7 = "接触の後の形は 1 回の計算の結果で、計算ごとに変わります（2 つ目の噴流の届く距離は 4.1〜9.1 m）。板の幅 2 m の中でも水面は最大 1.87 m 違い、並べたのは板の真ん中の 1 枚です";
        public const string SynthWarn = "【合成の試しの曲線：計算の結果ではありません。字 1〜7 の数は本物の元のためのもの】";

        public bool HudVisible { get; set; } = true;
        public string LastHudText { get; private set; } = "";
        public string LastVrText { get; private set; } = "";

        Font font;
        Material textMat, panelMat;
        TextMesh hud, vr;
        Transform hudBg, vrBg;
        GameObject hudRoot, vrRoot;
        bool built;

        void Start()
        {
            if (Application.isPlaying) Build();
        }

        public void Build()
        {
            if (built) return;
            font = Font.CreateDynamicFontFromOSFont(fontNames, 48);
            if (font == null) font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            textMat = new Material(overlayMaterial) { name = "RT48 字（実行時）" };
            textMat.SetFloat("_UseAlphaTex", 1f);
            textMat.mainTexture = font.material.mainTexture;
            panelMat = new Material(overlayMaterial) { name = "RT48 字の下地（実行時）" };
            panelMat.SetFloat("_UseAlphaTex", 0f);
            panelMat.color = new Color(0.02f, 0.03f, 0.05f, 0.55f);
            Font.textureRebuilt += OnFontTex;
            hudRoot = new GameObject("RT48 字（デスクトップ・動画）");
            hudRoot.transform.SetParent(hudCamera.transform, false);
            hud = MakeText(hudRoot.transform, TextAnchor.LowerLeft, out hudBg);
            vrRoot = new GameObject("RT48 字（VR の板）");
            vrRoot.transform.SetParent(vrAnchor != null ? vrAnchor : transform, false);
            vr = MakeText(vrRoot.transform, TextAnchor.MiddleCenter, out vrBg);
            vrRoot.SetActive(false);
            built = true;
        }

        void OnDestroy() { Font.textureRebuilt -= OnFontTex; }
        void OnFontTex(Font f) { if (f == font && textMat != null) textMat.mainTexture = font.material.mainTexture; }

        TextMesh MakeText(Transform parent, TextAnchor anchor, out Transform bg)
        {
            var go = new GameObject("字");
            go.transform.SetParent(parent, false);
            var tm = go.AddComponent<TextMesh>();
            tm.font = font; tm.fontSize = 48; tm.characterSize = 0.1f; tm.anchor = anchor;
            tm.alignment = TextAlignment.Left; tm.color = new Color(0.97f, 0.97f, 0.95f, 1f); tm.richText = false;
            var mr = go.GetComponent<MeshRenderer>();
            mr.sharedMaterial = textMat;
            mr.sortingOrder = 10;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; mr.receiveShadows = false;
            var q = GameObject.CreatePrimitive(PrimitiveType.Quad);
            q.name = "下地";
            Object.DestroyImmediate(q.GetComponent<Collider>());
            q.transform.SetParent(go.transform, false);
            var qr = q.GetComponent<MeshRenderer>();
            qr.sharedMaterial = panelMat; qr.sortingOrder = 9;
            qr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off; qr.receiveShadows = false;
            bg = q.transform;
            return tm;
        }

        string Wrap(string s)
        {
            if (s.Length <= wrapChars) return s;
            var sb = new StringBuilder();
            int c = 0;
            foreach (var ch in s)
            {
                sb.Append(ch); c++;
                if (c >= wrapChars && (ch == '、' || ch == '。' || ch == '）' || ch == ' ' || c >= wrapChars + 8)) { sb.Append('\n').Append("　"); c = 1; }
            }
            return sb.ToString();
        }

        public string BuildLines(bool all, bool forVr)
        {
            var p = playback;
            var src = p != null ? p.Source : null;
            var sb = new StringBuilder();
            if (src == null) { sb.Append("RT48：焼きを読めませんでした。").Append(p != null ? p.LoadError : ""); return sb.ToString(); }
            var s = p.State;
            if (src.IsSynthetic) sb.Append(Wrap(SynthWarn)).Append('\n');
            sb.Append("1 ").Append(Wrap(string.IsNullOrEmpty(src.Caption1Ja) ? Cap1Default : src.Caption1Ja)).Append('\n');
            sb.Append("2 ").Append(Wrap(Cap2)).Append('\n');
            sb.Append("3 ").Append(!string.IsNullOrEmpty(src.Caption3Ja) ? src.Caption3Ja : src.LabelJa + (src.InterpVerified ? "" : "・補間は未確認")).Append('\n');
            sb.Append("4 計算の時刻 ").Append(p.SimTime.ToString("F2", CultureInfo.InvariantCulture)).Append(" s　巻き始め ")
              .Append(src.OnsetS.ToString("F1", CultureInfo.InvariantCulture)).Append(" s　唇が前の面に付く ").Append(src.ContactS.ToString("F1", CultureInfo.InvariantCulture)).Append(" s\n");
            sb.Append("5 ").Append(Cap5);
            if (all || s.afterK) sb.Append('\n').Append("6 ").Append(Cap6);
            if (all || s.afterContact) sb.Append('\n').Append("7 ").Append(Wrap(Cap7));
            if (!forVr)
            {
                string view = p.ViewIndex == 1 ? "頂に沿う向き（船首から " + p.alongCrestTurnDeg.ToString("F0") + "°）" : "船首の向き";
                sb.Append('\n').Append("元 ").Append(src.Id).Append("　座席 x = ").Append(p.SeatX.ToString("F0", CultureInfo.InvariantCulture)).Append(" m　").Append(view)
                  .Append("　").Append(p.FrameLabel()).Append("　船：上下 ").Append(p.BoatPose.heave.ToString("+0.00;-0.00", CultureInfo.InvariantCulture))
                  .Append(" m・縦揺れ ").Append(p.BoatPose.pitchDeg.ToString("+0.00;-0.00", CultureInfo.InvariantCulture)).Append("°");
                if (rig != null && rig.XrRequested) sb.Append("　").Append(rig.XrStatusJa);
                if (p.Paused) sb.Append("　【止めている】");
                if (p.Ended) sb.Append("\n【終わり ").Append(p.TimeEnd.ToString("F3", CultureInfo.InvariantCulture)).Append(" s（").Append(p.TimeEndFrom).Append("）：R で初めから】");
                if (!p.ManualClock) sb.Append('\n').Append("R 初めから・Space 止める・←→ 1 コマ・1/2 座席・V 向き・F 元・H 字・右ドラッグ 見回す・0 戻す・Q 終わる");
            }
            return sb.ToString();
        }

        void LateUpdate()
        {
            if (Application.isPlaying) Refresh();
        }

        // 字を今の状態に合わせる（動画と試しは描く前に呼ぶ）。
        public void Refresh()
        {
            if (!built) Build();
            bool xr = rig != null && rig.XrActive;
            hudRoot.SetActive(HudVisible && !xr);
            if (hudRoot.activeSelf)
            {
                LastHudText = BuildLines(false, false);
                if (hud.text != LastHudText) hud.text = LastHudText;
                PlaceHud();
            }
            bool showVr = xr && playback != null && (playback.Ended || (Time.realtimeSinceStartupAsDouble - playback.ClipStartedRealtime) < vrIntroSeconds);
            if (showVr && !vrRoot.activeSelf) Debug.Log("RT48_VRPANEL show end=" + (playback != null && playback.Ended) + " t=" + (playback != null ? playback.SimTime.ToString("F3", CultureInfo.InvariantCulture) : ""));
            vrRoot.SetActive(showVr);
            if (showVr)
            {
                LastVrText = BuildLines(playback.Ended, true);
                if (vr.text != LastVrText) vr.text = LastVrText;
                vrRoot.transform.localPosition = new Vector3(-vrPanelDistanceM, playback.eyeHeightM, 0f);
                vrRoot.transform.localRotation = Quaternion.Euler(0f, -90f, 0f);
                FitBg(vr, vrBg, 0.03f);
            }
        }

        void PlaceHud()
        {
            var cam = hudCamera;
            float d = 1f;
            float halfH = d * Mathf.Tan(0.5f * cam.fieldOfView * Mathf.Deg2Rad);
            float aspect = cam.targetTexture != null ? (float)cam.targetTexture.width / cam.targetTexture.height : cam.aspect;
            float halfW = halfH * aspect;
            float line = 2f * halfH * hudLineFrac;
            // TextMesh の 1 行の高さ ≈ fontSize × characterSize × 0.1（行の送りは字の大きさより少し大きい）。行の高さが line になるように縮める
            float s = line / (hud.fontSize * hud.characterSize * 0.1f * 1.15f);
            hudRoot.transform.localPosition = new Vector3(-halfW + 0.02f * halfH, -halfH + 0.03f * halfH, d);
            hudRoot.transform.localRotation = Quaternion.identity;
            hudRoot.transform.localScale = new Vector3(s, s, s);
            FitBg(hud, hudBg, 0.15f);
        }

        static void FitBg(TextMesh tm, Transform bg, float pad)
        {
            var r = tm.GetComponent<MeshRenderer>();
            var b = r.localBounds;
            if (b.size.x <= 0 || b.size.y <= 0) { bg.localScale = Vector3.zero; return; }
            bg.localPosition = new Vector3(b.center.x, b.center.y, 0.01f);
            bg.localScale = new Vector3(b.size.x + 2 * pad, b.size.y + 2 * pad, 1f);
        }
    }
}
