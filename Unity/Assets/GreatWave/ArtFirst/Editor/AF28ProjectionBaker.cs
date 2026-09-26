using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using Unity.Collections;
using UnityEngine;
using UnityEngine.Rendering;

namespace GreatWave.ArtFirst.EditorTools
{
    // 番号28：GWProjectionBaker（作業計画 4.0・4.2 の名前。ファイル名は番号の接頭辞 AF28 を付けた）。
    // t* の K*（番号26）を PaintingCam v1 から GPU で深度テスト付きに投影し、原画の色区の符号付き距離を焼き込み用の UV（UV3）の 4096² へ焼く。
//   UV3 = UV0 を列ごと・行ごとに単調に引き伸ばした (u′, v′)。表は af28_bake_input.py が原画視点で見える面の画面上の長さから決める。
    //   1) 深度：K* だけを PaintingCam v1 から 3840×2160 へ描き、画素ごとの最小の視点深度を残す（1/深度 の BlendOp Max）。
    //   2) UV：K* を UV3 の空間へ広げて描き、各テクセルの世界位置を投影して、深度テストの可否・画面内か・原画の有効域・高さと、
    //      原画側の 4 色区の符号付き距離（表示 px）を読む（AF28_Bake.shader）。
    //   3) 外挿（CPU）：見えないテクセルを埋める。規則は Tools/PaintingTruth/colour/af28_params.json の fill_ja と同じ。
    //      直接 → 内側の藍濃（K* 自身に隠れた唇先端〜内壁の下端）→ u 方向（色）→ v 方向（縞、画面外）→ 海面の藍濃 → 残り。
    //   4) 8bit に符号化して Build/ArtFirst/28/bake/af28_uvsdf_<key>.bin（RGBA32 の生データ、下の行 = v 0 から）に書く。
    // PC の GPU（Editor batchmode）での計算で、HMD 実機ではない。
    public static class AF28ProjectionBaker
    {
        public const string BuildRoot = "Build/ArtFirst/28";
        public const string MetaPath = BuildRoot + "/bake_input/af28_bake_meta.json";

        [Serializable] public class KStar { public string key, gwb, gwbSha256; public int nu, nv; public float uTip, uFacebot, uTop, uCorner; public float[] uWarp, vWarp; }
        [Serializable] public class BakeMeta
        {
            public int paintW, paintH, texSize, depthW, depthH;
            public float scale, offsetX, sdfClamp, encodeLevels, depthTolM, depthTolRel, seaHeightM, scoredX0, scoredX1, lineAngleRad, lineMinM, lineMaxM;
            public string sdfFile, validFile;
            public int[] white, mizuiro, aiMid, aiDark, lineColor;
            public string[] keys;
            public KStar[] kstar;
        }

        [Serializable] public class BakeReport
        {
            public string key, unity, device, graphicsApi, utc, gwb, gwbSha256, paintSdfSha256, paintValidSha256, outSdf, outSdfSha256, outCat, outCatSha256, outWarp, outWarpSha256;
            public int texSize, depthW, depthH;
            public bool depthRowsFlipped, uvRowsFlipped;
            public int depthCheckMatchNormal, depthCheckMatchFlipped, depthCheckSamples;
            public long texels, rasterised, notRasterised, onScreen, visible, direct, innerDark, uFill, uFillBlue, vFill, sea, leftoverU, leftoverV, leftoverDefault, emptyAfterFill, noPositiveClass;
            public long[] classCountsDirect, classCountsAll;
            public float seaSanityMaxHeightNearU0, secondsGpu, secondsFill, secondsTotal;
            public string categoriesJa = "カテゴリ（af28_uvcat_<key>.bin の値）：1 直接、2 内側の藍濃、3 u 方向（色）、9 u 方向（原画の遮蔽物に隠れた所。藍だけ）、4 v 方向（縞）、5 海面の藍濃、6 残り u、7 残り v、8 残り既定の藍濃、0 未設定（0 のはず）";
        }

        public static BakeMeta LoadMeta()
        {
            if (!File.Exists(MetaPath)) throw new FileNotFoundException("先に af28_bake_input.py を実行してください: " + MetaPath);
            return JsonUtility.FromJson<BakeMeta>(File.ReadAllText(MetaPath));
        }

        public static BakeReport Bake(BakeMeta meta, KStar k, Mesh mesh, Camera cam)
        {
            var total = Stopwatch.StartNew();
            int N = meta.texSize;
            var shader = Shader.Find("Hidden/GreatWave/ArtFirst/AF28 Bake");
            if (shader == null) throw new InvalidOperationException("AF28 Bake シェーダーがありません。");
            var mat = new Material(shader) { hideFlags = HideFlags.DontSave };

            // ---- 原画側の入力
            string inDir = BuildRoot + "/bake_input/";
            var sdfBytes = File.ReadAllBytes(inDir + meta.sdfFile);
            var valBytes = File.ReadAllBytes(inDir + meta.validFile);
            if (sdfBytes.Length != meta.paintW * meta.paintH * 8 || valBytes.Length != meta.paintW * meta.paintH) throw new InvalidDataException("原画側の入力の容量が違います。");
            var paintSdf = new Texture2D(meta.paintW, meta.paintH, TextureFormat.RGBAHalf, false, true) { filterMode = FilterMode.Bilinear, wrapMode = TextureWrapMode.Clamp, hideFlags = HideFlags.DontSave };
            paintSdf.LoadRawTextureData(sdfBytes); paintSdf.Apply(false, false);
            var paintValid = new Texture2D(meta.paintW, meta.paintH, TextureFormat.R8, false, true) { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp, hideFlags = HideFlags.DontSave };
            paintValid.LoadRawTextureData(valBytes); paintValid.Apply(false, false);

            // ---- 行列（PaintingCam v1）
            cam.aspect = 1920f / 1080f;
            var view = cam.worldToCameraMatrix;
            var proj = cam.projectionMatrix;
            mat.SetMatrix("_BakeGpuVP", GL.GetGPUProjectionMatrix(proj, true) * view);
            mat.SetMatrix("_BakeVPGL", proj * view);
            mat.SetFloat("_TolM", meta.depthTolM); mat.SetFloat("_TolRel", meta.depthTolRel);
            mat.SetFloat("_ScoredX0", meta.scoredX0); mat.SetFloat("_ScoredX1", meta.scoredX1);
            mat.SetFloat("_OffX", meta.offsetX); mat.SetFloat("_Scale", meta.scale); mat.SetFloat("_PaintW", meta.paintW);
            mat.SetTexture("_PaintSdf", paintSdf); mat.SetTexture("_PaintValid", paintValid);

            // ---- 1) 深度
            var gpu = Stopwatch.StartNew();
            var depthRT = new RenderTexture(meta.depthW, meta.depthH, 0, RenderTextureFormat.RFloat, RenderTextureReadWrite.Linear) { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp, antiAliasing = 1 };
            depthRT.Create();
            var cmd = new CommandBuffer { name = "AF28 深度" };
            cmd.SetRenderTarget(depthRT);
            cmd.ClearRenderTarget(false, true, Color.clear);
            cmd.DrawMesh(mesh, Matrix4x4.identity, mat, 0, 0);
            Graphics.ExecuteCommandBuffer(cmd);
            cmd.Release();
            var depthArr = ReadFloat(depthRT, TextureFormat.RFloat, 1);
            // 向きの確かめ：見える頂点の視点深度が、深度画像のどちらの行の向きで一致するか
            var verts = mesh.vertices;
            var VP = proj * view;
            int mN = 0, mF = 0, samples = 0;
            for (int i = 0; i < verts.Length; i += 7)
            {
                var c = VP * new Vector4(verts[i].x, verts[i].y, verts[i].z, 1);
                if (c.w < 0.2f) continue;
                float vx = c.x / c.w * 0.5f + 0.5f, vy = c.y / c.w * 0.5f + 0.5f;
                if (vx < 0 || vx >= 1 || vy < 0 || vy >= 1) continue;
                samples++;
                int col = Mathf.Clamp((int)(vx * meta.depthW), 0, meta.depthW - 1);
                int rN = Mathf.Clamp((int)(vy * meta.depthH), 0, meta.depthH - 1), rF = meta.depthH - 1 - rN;
                float dN = depthArr[rN * meta.depthW + col], dF = depthArr[rF * meta.depthW + col];
                if (dN > 0 && Mathf.Abs(1f / dN - c.w) < 0.3f) mN++;
                if (dF > 0 && Mathf.Abs(1f / dF - c.w) < 0.3f) mF++;
            }
            bool depthFlip = mF > mN;
            mat.SetFloat("_DepthFlip", depthFlip ? 1 : 0);
            mat.SetTexture("_DepthTex", depthRT);

            // ---- 2) UV の空間へ
            mat.SetFloat("_UvFlip", 1);
            var sdfRT = new RenderTexture(N, N, 0, RenderTextureFormat.ARGBHalf, RenderTextureReadWrite.Linear) { filterMode = FilterMode.Point, antiAliasing = 1 };
            var auxRT = new RenderTexture(N, N, 0, RenderTextureFormat.ARGBHalf, RenderTextureReadWrite.Linear) { filterMode = FilterMode.Point, antiAliasing = 1 };
            sdfRT.Create(); auxRT.Create();
            cmd = new CommandBuffer { name = "AF28 UV 投影" };
            cmd.SetRenderTarget(sdfRT); cmd.ClearRenderTarget(false, true, Color.clear); cmd.DrawMesh(mesh, Matrix4x4.identity, mat, 0, 1);
            cmd.SetRenderTarget(auxRT); cmd.ClearRenderTarget(false, true, Color.clear); cmd.DrawMesh(mesh, Matrix4x4.identity, mat, 0, 2);
            Graphics.ExecuteCommandBuffer(cmd);
            cmd.Release();
            var sdfH = ReadHalf(sdfRT, N);
            var auxH = ReadHalf(auxRT, N);
            float secondsGpu = (float)gpu.Elapsed.TotalSeconds;
            RenderTexture.active = null;
            depthRT.Release(); sdfRT.Release(); auxRT.Release();
            UnityEngine.Object.DestroyImmediate(depthRT); UnityEngine.Object.DestroyImmediate(sdfRT); UnityEngine.Object.DestroyImmediate(auxRT);
            UnityEngine.Object.DestroyImmediate(paintSdf); UnityEngine.Object.DestroyImmediate(paintValid); UnityEngine.Object.DestroyImmediate(mat);

            // 行の向き：AUX.a に書いた v と行番号を比べる
            int midCol = N / 2;
            float vRow0 = Mathf.HalfToFloat(auxH[(0 * N + midCol) * 4 + 3]);
            float vRowL = Mathf.HalfToFloat(auxH[((N - 1) * N + midCol) * 4 + 3]);
            bool uvFlip = vRow0 > vRowL;

            // ---- 3) 外挿
            var fill = Stopwatch.StartNew();
            long n = (long)N * N;
            var outB = new byte[n * 4];
            var cat = new byte[n];
            var flags = new byte[n];   // bit0 見える、bit1 画面内、bit2 描かれた、bit3 有効、bit4 原画の遮蔽物
            var height = new float[n];
            float enc = meta.encodeLevels;
            byte Enc(float d) => (byte)Mathf.Clamp(Mathf.RoundToInt(127.5f + enc * Mathf.Clamp(d, -meta.sdfClamp, meta.sdfClamp)), 0, 255);
            byte dark0 = Enc(-meta.sdfClamp), dark1 = Enc(meta.sdfClamp);
            HardHi = dark1; HardLo = dark0;
            int tipX0 = Mathf.FloorToInt(k.uTip * N), tipX1 = Mathf.CeilToInt(k.uFacebot * N);
            var rep = new BakeReport { key = k.key, texSize = N, depthW = meta.depthW, depthH = meta.depthH, depthRowsFlipped = depthFlip, uvRowsFlipped = uvFlip,
                depthCheckMatchNormal = mN, depthCheckMatchFlipped = mF, depthCheckSamples = samples, texels = n,
                classCountsDirect = new long[4], classCountsAll = new long[4] };
            for (int r = 0; r < N; r++)
            {
                int src = uvFlip ? N - 1 - r : r;
                for (int x = 0; x < N; x++)
                {
                    long i = (long)r * N + x, s4 = ((long)src * N + x) * 4;
                    float a0 = Mathf.HalfToFloat(auxH[s4]), a1 = Mathf.HalfToFloat(auxH[s4 + 1]), a2 = Mathf.HalfToFloat(auxH[s4 + 2]), a3 = Mathf.HalfToFloat(auxH[s4 + 3]);
                    bool rast = a3 > 0;
                    int code = Mathf.RoundToInt(a0);
                    // 有効域：1 = 主浪の色区、0.5 = 主浪の近くの空（ここまで有効）、0.25 = 遠い空、0 = 原画の遮蔽物（前景の波・船など）
                    bool vis = rast && (code & 1) != 0, on = rast && (code & 2) != 0, valid = rast && a1 > 0.4f, occluder = rast && a1 < 0.1f;
                    byte fl = (byte)((vis ? 1 : 0) | (on ? 2 : 0) | (rast ? 4 : 0) | (valid ? 8 : 0) | (occluder ? 16 : 0));
                    flags[i] = fl;
                    height[i] = rast ? a2 : 0;
                    if (rast) rep.rasterised++; else rep.notRasterised++;
                    if (on) rep.onScreen++;
                    if (vis) rep.visible++;
                    if (vis && valid)
                    {
                        for (int c = 0; c < 4; c++) outB[i * 4 + c] = Enc(Mathf.HalfToFloat(sdfH[s4 + c]));
                        cat[i] = 1;
                    }
                }
            }
            // 2 内側の藍濃
            for (int r = 0; r < N; r++)
                for (int x = tipX0; x <= Math.Min(tipX1, N - 1); x++)
                {
                    long i = (long)r * N + x;
                    if (cat[i] == 0 && (flags[i] & 4) != 0 && (flags[i] & 2) != 0 && (flags[i] & 1) == 0) { SetDark(outB, i, dark0, dark1); cat[i] = 2; }
                }
            // 3 u 方向（画面内で無効なテクセル）：同じ行で最も近い直接のテクセル
            //   原画の遮蔽物（前景の波・船など、原画で主役波の外）に隠れた見えるテクセルは、泡（白・淡い水色）を延ばすと縦の筋になるので、
            //   同じ行で最も近い藍（藍中・藍濃）の直接のテクセルを写す（藍中の縞を延ばす。なければ最も近い直接のテクセル）。カテゴリ 9。
            var left = new int[N]; var right = new int[N];
            var leftB = new int[N]; var rightB = new int[N];
            for (int r = 0; r < N; r++)
            {
                long row = (long)r * N;
                NearestInLine(N, x => cat[row + x] == 1, left, right);
                NearestInLine(N, x => cat[row + x] == 1 && IsBlue(outB, row + x), leftB, rightB);
                for (int x = 0; x < N; x++)
                {
                    long i = row + x;
                    if (cat[i] != 0 || (flags[i] & 2) == 0) continue;
                    bool hiddenByPaintingOccluder = (flags[i] & 1) != 0 && (flags[i] & 16) != 0;
                    int p = -1;
                    if (hiddenByPaintingOccluder) p = Pick(x, leftB[x], rightB[x]);
                    bool blue = p >= 0;
                    if (p < 0) p = Pick(x, left[x], right[x]);
                    if (p < 0) continue;
                    CopyHard(outB, row + p, i); cat[i] = (byte)(blue ? 9 : 3);
                }
            }
            // 4 v 方向（画面外のテクセル）：同じ列で最も近い直接または u 方向のテクセル
            var up = new int[N]; var down = new int[N];
            for (int x = 0; x < N; x++)
            {
                int xx = x;
                NearestInLine(N, r => cat[(long)r * N + xx] == 1 || cat[(long)r * N + xx] == 3 || cat[(long)r * N + xx] == 9, up, down);
                for (int r = 0; r < N; r++)
                {
                    long i = (long)r * N + x;
                    if (cat[i] != 0 || (flags[i] & 2) != 0) continue;
                    int p = Pick(r, up[r], down[r]);
                    if (p < 0) continue;
                    CopyHard(outB, (long)p * N + x, i); cat[i] = 4;
                }
            }
            // 5 海面（無効で低い所は藍濃。直接と内側の藍濃は変えない）
            for (long i = 0; i < n; i++)
                if ((cat[i] == 0 || cat[i] == 3 || cat[i] == 4 || cat[i] == 9) && (flags[i] & 4) != 0 && height[i] < meta.seaHeightM) { SetDark(outB, i, dark0, dark1); cat[i] = 5; }
            // 6 残り
            for (int r = 0; r < N; r++)
            {
                long row = (long)r * N;
                NearestInLine(N, x => cat[row + x] != 0, left, right);
                for (int x = 0; x < N; x++)
                {
                    long i = row + x;
                    if (cat[i] != 0) continue;
                    int p = Pick(x, left[x], right[x]);
                    if (p < 0 || cat[row + p] == 0) continue;
                    CopyHard(outB, row + p, i); cat[i] = 6;
                }
            }
            for (int x = 0; x < N; x++)
            {
                int xx = x;
                NearestInLine(N, r => cat[(long)r * N + xx] != 0 && cat[(long)r * N + xx] != 7, up, down);
                for (int r = 0; r < N; r++)
                {
                    long i = (long)r * N + x;
                    if (cat[i] != 0) continue;
                    int p = Pick(r, up[r], down[r]);
                    if (p < 0) continue;
                    CopyHard(outB, (long)p * N + x, i); cat[i] = 7;
                }
            }
            for (long i = 0; i < n; i++) if (cat[i] == 0) { SetDark(outB, i, dark0, dark1); cat[i] = 8; }

            // ---- 集計
            for (long i = 0; i < n; i++)
            {
                switch (cat[i])
                {
                    case 1: rep.direct++; break;
                    case 2: rep.innerDark++; break;
                    case 3: rep.uFill++; break;
                    case 4: rep.vFill++; break;
                    case 5: rep.sea++; break;
                    case 6: rep.leftoverU++; break;
                    case 7: rep.leftoverV++; break;
                    case 8: rep.leftoverDefault++; break;
                    case 9: rep.uFillBlue++; break;
                    default: rep.emptyAfterFill++; break;
                }
                int a = 0; byte best = outB[i * 4];
                for (int c = 1; c < 4; c++) if (outB[i * 4 + c] > best) { best = outB[i * 4 + c]; a = c; }
                if (best <= 127) rep.noPositiveClass++;
                rep.classCountsAll[a]++;
                if (cat[i] == 1) rep.classCountsDirect[a]++;
            }
            // 海の確かめ：u が 0 に近い列（後ろの平らな海）の最大の高さ
            float seaMax = 0;
            for (int r = 0; r < N; r += 16) seaMax = Mathf.Max(seaMax, height[(long)r * N + 8]);
            rep.seaSanityMaxHeightNearU0 = seaMax;
            rep.secondsGpu = secondsGpu;
            rep.secondsFill = (float)fill.Elapsed.TotalSeconds;

            // ---- 4) 書き出し
            string outDir = BuildRoot + "/bake";
            Directory.CreateDirectory(outDir);
            rep.outSdf = outDir + "/af28_uvsdf_" + k.key + ".bin";
            rep.outCat = outDir + "/af28_uvcat_" + k.key + ".bin";
            File.WriteAllBytes(rep.outSdf, outB);
            File.WriteAllBytes(rep.outCat, cat);
            rep.outSdfSha256 = Sha(rep.outSdf); rep.outCatSha256 = Sha(rep.outCat);
            rep.outWarp = outDir + "/af28_uvwarp_" + k.key + ".json";
            File.WriteAllText(rep.outWarp, JsonUtility.ToJson(new AF28NprWave.Warp { key = k.key, nu = k.nu, nv = k.nv, uWarp = k.uWarp, vWarp = k.vWarp }, false));
            rep.outWarpSha256 = Sha(rep.outWarp);
            rep.gwb = k.gwb; rep.gwbSha256 = Sha(Path.GetFullPath(Path.Combine("..", k.gwb)));
            rep.paintSdfSha256 = Sha(inDir + meta.sdfFile); rep.paintValidSha256 = Sha(inDir + meta.validFile);
            rep.unity = Application.unityVersion; rep.device = SystemInfo.graphicsDeviceName; rep.graphicsApi = SystemInfo.graphicsDeviceType.ToString();
            rep.utc = DateTime.UtcNow.ToString("O");
            rep.secondsTotal = (float)total.Elapsed.TotalSeconds;
            File.WriteAllText(outDir + "/af28_bake_" + k.key + ".json", JsonUtility.ToJson(rep, true));
            if (rep.gwbSha256 != k.gwbSha256) throw new InvalidDataException("K* の .gwb の SHA-256 が入力の記録と違います: " + k.key);
            UnityEngine.Debug.Log("AF28_BAKE_DONE key=" + k.key + " direct=" + rep.direct + " empty=" + rep.emptyAfterFill + " depthFlip=" + depthFlip + " uvFlip=" + uvFlip + " s=" + rep.secondsTotal);
            return rep;
        }

        static bool IsBlue(byte[] o, long i)
        {
            int a = 0; byte best = o[i * 4];
            for (int c = 1; c < 4; c++) if (o[i * 4 + c] > best) { best = o[i * 4 + c]; a = c; }
            return a >= 2;
        }

        static void SetDark(byte[] o, long i, byte d0, byte d1) { o[i * 4] = d0; o[i * 4 + 1] = d0; o[i * 4 + 2] = d0; o[i * 4 + 3] = d1; }
        // 外挿のテクセルは、元のテクセルの色区だけを写す（最大の色区を +clamp、ほかを −clamp）。距離の値ごと写すと、
        // 境の近くの値が縞の向きに延びて、別の元から写した隣のテクセルとの間で距離が飛び、アンチエイリアスで細い線が出るため。
        static void CopyHard(byte[] o, long from, long to)
        {
            int a = 0; byte best = o[from * 4];
            for (int c = 1; c < 4; c++) if (o[from * 4 + c] > best) { best = o[from * 4 + c]; a = c; }
            for (int c = 0; c < 4; c++) o[to * 4 + c] = c == a ? HardHi : HardLo;
        }
        static byte HardHi = 255, HardLo = 0;

        // 1 次元の並びで、各位置から左（手前）と右（奥）の最も近い「条件を満たす位置」
        static void NearestInLine(int N, Func<int, bool> ok, int[] left, int[] right)
        {
            int last = -1;
            for (int x = 0; x < N; x++) { if (ok(x)) last = x; left[x] = last; }
            last = -1;
            for (int x = N - 1; x >= 0; x--) { if (ok(x)) last = x; right[x] = last; }
        }

        static int Pick(int x, int l, int r)
        {
            if (l < 0) return r;
            if (r < 0) return l;
            return (x - l) <= (r - x) ? l : r;
        }

        static float[] ReadFloat(RenderTexture rt, TextureFormat fmt, int channels)
        {
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var t = new Texture2D(rt.width, rt.height, fmt, false, true);
            t.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
            t.Apply(false);
            RenderTexture.active = prev;
            var a = t.GetRawTextureData<float>().ToArray();
            UnityEngine.Object.DestroyImmediate(t);
            if (a.Length != rt.width * rt.height * channels) throw new InvalidDataException("読み戻しの容量が違います。");
            return a;
        }

        static ushort[] ReadHalf(RenderTexture rt, int N)
        {
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            var t = new Texture2D(N, N, TextureFormat.RGBAHalf, false, true);
            t.ReadPixels(new Rect(0, 0, N, N), 0, 0);
            t.Apply(false);
            RenderTexture.active = prev;
            var a = t.GetRawTextureData<ushort>().ToArray();
            UnityEngine.Object.DestroyImmediate(t);
            if (a.Length != N * N * 4) throw new InvalidDataException("読み戻しの容量が違います。");
            return a;
        }

        public static string Sha(string path)
        {
            using (var h = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(h.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
        }
    }
}
