using System;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Experimental.Rendering;

namespace GreatWave.Playback18
{
    // 再生時計・シーン変更・インポーター変更・描画境界変更を持たない。
    // 呼出側が書出元の実メタデータを渡し、離散時刻を指定する。
    public static class Playback18VAT
    {
        [Serializable]
        public sealed class Data
        {
            public Texture2D position;
            public Texture2D rotation;
            public Texture2D lookup;
            public Vector3 encodedMin;
            public Vector3 encodedMax;
            public int frameCount = 49;
            public float sampleRate = 24f;
        }

        [StructLayout(LayoutKind.Sequential, Pack = 4)]
        public struct DecodedSample
        {
            public Vector4 position;
            public Vector4 normal;
            public Vector4 lookup;
            public Vector4 address;
            public Vector4 status;
            public Vector4 layout;
        }

        public const int OutputStride = 96;
        public const string ShaderName = "GreatWave/Playback18/VAT HDR";

        public static void Validate(Data data)
        {
            if (data == null) throw new ArgumentNullException(nameof(data));
            if (data.frameCount < 1 || !Finite(data.sampleRate) || data.sampleRate <= 0)
                throw new ArgumentException("VATのフレーム数または標本化周波数が不正です。");
            CheckTexture(data.position, "position");
            CheckTexture(data.rotation, "rotation");
            CheckTexture(data.lookup, "lookup");
            if (data.position.width != data.rotation.width || data.position.height != data.rotation.height)
                throw new ArgumentException("位置と回転は同じテクセル配置と寸法を必要とします。");
            if (!Finite(data.encodedMin) || !Finite(data.encodedMax))
                throw new ArgumentException("書出マテリアルの有限な符号化境界値を指定してください。");
            var layout = GetLayoutDiagnostics(data);
            if (layout.activeX <= 0f || layout.activeX > 1f || layout.activeY <= 0f || layout.activeY > 1f)
                throw new ArgumentException("符号化された検索表の有効画素率が不正です。");
            if (Fraction(data.encodedMax.z * 10f) < .5f || Fraction(-data.encodedMin.x * 10f) < .5f)
                throw new ArgumentException("このデコーダーは位置・回転・検索表すべてのHDR符号化を必要とします。");
            if (Marshal.SizeOf<DecodedSample>() != OutputStride)
                throw new InvalidOperationException("GPU出力バッファの配置が一致しません。");
        }

        public static Playback18VATLayout.Diagnostics GetLayoutDiagnostics(Data data)
        {
            if (data == null || data.lookup == null)
                throw new ArgumentException("配置診断には実検索表テクスチャが必要です。");
            return Playback18VATLayout.Evaluate(data.encodedMin.z, data.encodedMax.x,
                data.lookup.width, data.lookup.height);
        }

        public static void Bind(Material material, Data data, int frameIndex)
        {
            if (material == null) throw new ArgumentNullException(nameof(material));
            Validate(data);
            CheckFrame(data, frameIndex);
            material.SetTexture("_VatPosition", data.position);
            material.SetTexture("_VatRotation", data.rotation);
            material.SetTexture("_VatLookup", data.lookup);
            material.SetVector("_VatEncodedMin", data.encodedMin);
            material.SetVector("_VatEncodedMax", data.encodedMax);
            material.SetInteger("_VatFrameCount", data.frameCount);
            material.SetInteger("_VatFrameIndex", frameIndex);
        }

        public static void SetFrame(Material material, Data data, int frameIndex)
        {
            CheckFrame(data, frameIndex);
            material.SetInteger("_VatFrameIndex", frameIndex);
        }

        // 試料番号は0始まり。最後の49番目は48/24 = 2秒。
        public static int SampleAtSeconds(double relativeSeconds, Data data)
        {
            if (data == null || data.frameCount < 1 || !Finite(data.sampleRate) || data.sampleRate <= 0)
                throw new ArgumentException("フレーム数または標本化周波数が不正です。");
            if (double.IsNaN(relativeSeconds) || double.IsInfinity(relativeSeconds))
                throw new ArgumentOutOfRangeException(nameof(relativeSeconds));
            double index = Math.Floor(Math.Max(0.0, relativeSeconds) * data.sampleRate + 1e-7);
            return (int)Math.Min(data.frameCount - 1, index);
        }

        // 同期GPU読戻しによる診断専用。再生性能測定には含めない。
        // 縮退・余白を含む全頂点を、そのまま返す。
        public static DecodedSample[] ReadGpu(ComputeShader compute, Data data, Vector2[] uv0, int frameIndex)
        {
            if (compute == null) throw new ArgumentNullException(nameof(compute));
            if (uv0 == null) throw new ArgumentNullException(nameof(uv0));
            Validate(data);
            CheckFrame(data, frameIndex);
            if (!SystemInfo.supportsComputeShaders) throw new NotSupportedException("計算シェーダーを使用できません。");
            if (uv0.Length == 0) return Array.Empty<DecodedSample>();
            var inputs = new Vector4[uv0.Length];
            for (int i = 0; i < uv0.Length; i++)
            {
                if (!Finite(uv0[i].x) || !Finite(uv0[i].y))
                    throw new ArgumentException("メッシュUVに有限でない値があります。");
                inputs[i] = new Vector4(uv0[i].x, uv0[i].y, 0, 0);
            }
            var output = new DecodedSample[uv0.Length];
            using (var inputBuffer = new ComputeBuffer(inputs.Length, 16))
            using (var outputBuffer = new ComputeBuffer(output.Length, OutputStride))
            {
                int kernel = compute.FindKernel("DecodeVertices");
                inputBuffer.SetData(inputs);
                compute.SetTexture(kernel, "_VatPosition", data.position);
                compute.SetTexture(kernel, "_VatRotation", data.rotation);
                compute.SetTexture(kernel, "_VatLookup", data.lookup);
                compute.SetVector("_VatEncodedMin", data.encodedMin);
                compute.SetVector("_VatEncodedMax", data.encodedMax);
                compute.SetInt("_VatFrameCount", data.frameCount);
                compute.SetInt("_VatFrameIndex", frameIndex);
                compute.SetInt("_VatVertexCount", inputs.Length);
                compute.SetBuffer(kernel, "_VatInputUV", inputBuffer);
                compute.SetBuffer(kernel, "_VatDecoded", outputBuffer);
                compute.Dispatch(kernel, (inputs.Length + 127) / 128, 1, 1);
                outputBuffer.GetData(output);
            }
            return output;
        }

        static void CheckTexture(Texture2D texture, string label)
        {
            if (texture == null) throw new ArgumentException("VATテクスチャがありません：" + label);
            if (texture.format != TextureFormat.RGBAFloat || texture.mipmapCount != 1 ||
                GraphicsFormatUtility.IsSRGBFormat(texture.graphicsFormat))
                throw new ArgumentException(label + "：リニア・非圧縮RGBAFloat・ミップマップ無が必要です。");
        }

        static void CheckFrame(Data data, int index)
        {
            if (data == null || index < 0 || index >= data.frameCount)
                throw new ArgumentOutOfRangeException(nameof(index));
        }
        static float Fraction(float value) => value - Mathf.Floor(value);
        static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
        static bool Finite(Vector3 value) => Finite(value.x) && Finite(value.y) && Finite(value.z);
    }
}
