using System;
using System.IO;
using UnityEngine;

namespace GreatWave.ArtFirst
{
    // 番号31：白の時間場 T_white を AF31 NPR White シェーダーへ渡す。
    // T_white（Tools/GWWaveGen/af31_white.py が Build/ArtFirst/31/white/ に書く。Git 対象外）は固定位相の格子（K*、列 400 × 行 240）の
    // 頂点ごとの時刻（秒、R32 float）。RFloat の Texture2D（点サンプル）にして大域の値で渡し、頂点シェーダーが SV_VertexID で Load する。
    // 時刻は GWClock（番号30）から読む。Editor の採取（AF31WhiteFormation）は ApplyTime で時刻を直接決める。
    // メッシュ・焼き込み・keypose は同じ GameObject の AF26KStarMesh・AF28NprWave・AF30KeyposeWave のまま（変えない）。
    [RequireComponent(typeof(AF26KStarMesh))]
    [DefaultExecutionOrder(110)]
    public class AF31WhiteField : MonoBehaviour
    {
        [Tooltip("T_white の表（Unity プロジェクトからの相対パス、Git 対象外の /Unity/Build/ の下）")]
        public string metaPath = "Build/ArtFirst/31/white/af31_twhite.json";
        [Tooltip("時刻を読む時計（空なら GWClock.Active）")]
        public GWClock clock;
        [Tooltip("白の時間場を使う（切ると番号30 と同じ色：終態の白が最初から見える）")]
        public bool whiteEnabled = true;

        [Serializable]
        public class Meta
        {
            public string file, sha256, pre_white_class;
            public int nu, nv, pre_white_index;
            public float t_start_s, t_end_s, t_star_s;
            public long bytes;
        }

        Meta meta;
        Texture2D tex;
        public Meta FieldMeta => meta;
        public Texture2D FieldTexture => tex;
        public float AppliedSeconds { get; private set; } = float.NaN;

        public static readonly int TexId = Shader.PropertyToID("_AF31WhiteTex"), GridNUId = Shader.PropertyToID("_AF31GridNU"),
            TimeId = Shader.PropertyToID("_AF31Time"), EnabledId = Shader.PropertyToID("_AF31WhiteEnabled"), DebugId = Shader.PropertyToID("_AF31DebugMode"),
            EndId = Shader.PropertyToID("_AF31WhiteEnd");

        public void EnsureLoaded()
        {
            if (meta != null && tex != null) return;
            var full = Path.GetFullPath(metaPath);
            var m = JsonUtility.FromJson<Meta>(File.ReadAllText(full));
            if (m == null || m.nu <= 0 || m.nv <= 0 || string.IsNullOrEmpty(m.file)) throw new InvalidDataException("af31_twhite.json を読めません。");
            var km = GetComponent<AF26KStarMesh>();
            var mesh = km.EnsureLoaded();
            if (mesh.vertexCount != m.nu * m.nv || km.nu != m.nu || km.nv != m.nv)
                throw new InvalidDataException("T_white の格子と K* のメッシュが合いません: " + mesh.vertexCount);
            var bytes = File.ReadAllBytes(Path.Combine(Path.GetDirectoryName(full), m.file));
            if (bytes.LongLength != (long)m.nu * m.nv * 4) throw new InvalidDataException("T_white の容量が違います: " + bytes.LongLength);
            using (var s = System.Security.Cryptography.SHA256.Create())
            {
                var h = BitConverter.ToString(s.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
                if (h != m.sha256) throw new InvalidDataException("T_white の SHA-256 が違います: " + h);
            }
            if (!SystemInfo.SupportsTextureFormat(TextureFormat.RFloat)) throw new NotSupportedException("RFloat のテクスチャが使えません。");
            tex = new Texture2D(m.nu, m.nv, TextureFormat.RFloat, false, true)
            {
                name = "AF31 白の時間場 T_white", filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp, anisoLevel = 0, hideFlags = HideFlags.DontSave
            };
            tex.LoadRawTextureData(bytes);
            tex.Apply(false, true);
            meta = m;
            Shader.SetGlobalTexture(TexId, tex);
            Shader.SetGlobalFloat(GridNUId, m.nu);
            Shader.SetGlobalFloat(EndId, m.t_end_s);
            Shader.SetGlobalFloat(EnabledId, whiteEnabled ? 1f : 0f);
            Shader.SetGlobalFloat(DebugId, 0f);
        }

        /// <summary>時刻 t（秒）をシェーダーへ渡す（大域の値）。</summary>
        public void ApplyTime(float t)
        {
            EnsureLoaded();
            Shader.SetGlobalFloat(TimeId, t);
            Shader.SetGlobalFloat(EndId, meta.t_end_s);
            Shader.SetGlobalFloat(EnabledId, whiteEnabled ? 1f : 0f);
            AppliedSeconds = t;
        }

        void OnEnable()
        {
            if (Application.isPlaying) EnsureLoaded();
        }

        void LateUpdate()
        {
            if (!Application.isPlaying) return;
            var c = clock != null ? clock : GWClock.Active;
            if (c != null) ApplyTime(c.Seconds);
        }

        void OnDestroy()
        {
            Shader.SetGlobalFloat(EnabledId, 0f);
            if (tex != null)
            {
                if (Application.isPlaying) Destroy(tex); else DestroyImmediate(tex);
            }
        }
    }
}
