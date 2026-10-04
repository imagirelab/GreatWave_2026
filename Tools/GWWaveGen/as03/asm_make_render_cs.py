# -*- coding: utf-8 -*-
"""美術の見本03 の組み立て：B2 の描画の道具 AS03SurfRender.cs（元のファイルは変えない）を写して AS03AsmRender.cs を作る。
足すもの：
  -as03CrownMask 1：views・crest・tt・cmp の爪ありの静止画ごとに、冠（-as03Crown のメッシュ）だけを ID の色 (0.25,0.5,1) にした画（_crownmask.png）を
     同じカメラ・同じ隠し方で描く（ほかの物は ID の色か色区の ID。深さで隠れる所は冠にならない）。T4「冠が原画視点のほかのどの視点でも枠の 0.5% より多く見える」の測り。
     -as03CrownMaskCheck 1 で、原画視点だけ冠を隠した同じ画（_crownmask_off.png。冠の色が 0 画素であることの確かめ）も描く。
  -pl29Only cmp と -as03Cmp "名前:方位:仰角:距離:画角[:中心の高さ];…"：回り台と同じ中心（主役波の原点＋高さ）と方位の決め方（方位 0 = 原画の側、
     反時計回り＝原画の側から見て右へ回る）で、爪あり・飛沫なしの静止画（cmp/<名前>.png）を描く。利用者だけの比べの図（彫刻の写真と並べる）に使う。
使い方：py -3.10 -B Tools/GWWaveGen/as03/asm_make_render_cs.py
"""
import hashlib
import os

ED = "G:/Unity/GreatWave_2026_Fresh/Unity/Assets/GreatWave/ArtSample03/Editor"
SRC = ED + "/AS03SurfRender.cs"
DST = ED + "/AS03AsmRender.cs"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def rep(s, old, new, count=1):
    n = s.count(old)
    if n != count:
        raise SystemExit("置き換えの数が合わない（%d / %d）: %r" % (n, count, old[:80]))
    return s.replace(old, new)


def main():
    s = open(SRC, encoding="utf-8-sig").read()
    src_sha = sha(SRC)
    head = ("    // 美術の見本03 の組み立て（Q31、2026-10-04）：B2 の AS03SurfRender を写し（元のファイルは変えない。写した元の SHA-256 は\n"
            "    //   " + src_sha + "）、次を足した。ほかの段・引数は元のまま。\n"
            "    //   -as03CrownMask 1：views・crest・tt・cmp の爪ありの静止画ごとに、冠（-as03Crown）だけを ID の色 (0.25,0.5,1)（書き出しの 8 ビットで (13,55,255)）にした画 <名前>_crownmask.png を、\n"
            "    //     同じカメラ・同じ隠し方で描く（_AF28IdMode = 1。ほかの物は色区の ID か ID の色。深さで隠れた所は冠にならない）。\n"
            "    //     -as03CrownMaskCheck 1 で、原画視点だけ冠を隠した同じ画 <名前>_crownmask_off.png も描く（冠の色が 0 画素の確かめ）。\n"
            "    //   -pl29Only cmp・-as03Cmp \"名前:方位:仰角:距離:画角[:中心の高さ];…\"：回り台と同じ中心と方位の決め方（方位 0 = 原画の側、反時計回り）で、\n"
            "    //     爪あり・飛沫なしの静止画 cmp/<名前>.png（と冠の画）を描く。利用者だけの比べの図（彫刻の写真と並べる）用。\n"
            "    //   記録は as03asm_render_report.json、終わりの印は AS03ASM_RENDER_DONE。PC オフスクリーン描画で、HMD 実機ではない。原画カメラの投影は使わない。\n"
            "    // ── 以下は写した B2 の説明 ──\n")
    s = rep(s, "    // 美術の見本03 の作り B2（Q31、2026-10-04）：彫りの面とシェーダー 2 つ", head + "    // 美術の見本03 の作り B2（Q31、2026-10-04）：彫りの面とシェーダー 2 つ")
    s = rep(s, "public static class AS03SurfRender", "public static class AS03AsmRender")
    s = rep(s, "public class AS03SurfDesignMeta", "public class AS03AsmDesignMeta")
    s = rep(s, "JsonUtility.FromJson<AS03SurfDesignMeta>", "JsonUtility.FromJson<AS03AsmDesignMeta>")
    # 守るファイルに B1・B2 の部品と見本02 の爪を足す
    s = rep(s, "\"Assets/GreatWave/Polish35/Scenes/PL35_Release.unity\", \"Assets/GreatWave/Polish35/Scenes/PL35_SinglePlayback.unity\" };",
            "\"Assets/GreatWave/Polish35/Scenes/PL35_Release.unity\", \"Assets/GreatWave/Polish35/Scenes/PL35_SinglePlayback.unity\",\n"
            "            \"Assets/GreatWave/ArtSample03/Shaders/AS03Common.cginc\", \"Assets/GreatWave/ArtSample03/Shaders/AS03_Flat_Keypose.shader\",\n"
            "            \"Assets/GreatWave/ArtSample03/Shaders/AS03_Sculpt_Keypose.shader\", \"Assets/GreatWave/ArtSample03/Editor/AS03SurfRender.cs\",\n"
            "            \"Assets/GreatWave/ArtSample03/Scripts/AS03StaticMesh.cs\", \"Build/Polish/sample02/fix01/assemble/claws/mesh/ds33_claw_frames_f32.bin\",\n"
            "            \"Build/Polish/sample02/fix01/assemble/claws/mesh/ds33_claw_layout.json\", \"Build/Polish/sample03/crown/OUT/as03_crown.bin\",\n"
            "            \"Build/Polish/sample03/crown/IN/as03_crown.bin\", \"Build/Polish/sample03/surface/mesh/hero_relief_b1v2c.bin\" };")
    # Ctx に冠のレンダラーと印の入切
    s = rep(s, "            public List<DS31InstancedParticles> sprays = new List<DS31InstancedParticles>(); public bool ttSpray = true, vidAsis = true, old31;\n        }",
            "            public List<DS31InstancedParticles> sprays = new List<DS31InstancedParticles>(); public bool ttSpray = true, vidAsis = true, old31;\n"
            "            public List<Renderer> crownR = new List<Renderer>(); public bool crownMask, crownMaskCheck; public List<string> crownMaskFiles = new List<string>();\n        }")
    s = rep(s, "            public int as03Vertices, as03Triangles; public string[] as03Channels; public bool as03HeroOutline; public ParamRec[] as03MaterialParams; public string[] as03Crown;",
            "            public int as03Vertices, as03Triangles; public string[] as03Channels; public bool as03HeroOutline; public ParamRec[] as03MaterialParams; public string[] as03Crown;\n"
            "            public string as03AsmNote, as03Cmp; public bool as03CrownMask; public string[] as03CrownMaskFiles;")
    # 冠を置いた後にレンダラーを覚える
    s = rep(s, "                    rep.as03Crown = recs.ToArray();\n",
            "                    rep.as03Crown = recs.ToArray();\n"
            "                    foreach (var e in as03Extra) { var mr = e.GetComponent<MeshRenderer>(); if (mr != null) c.crownR.Add(mr); }\n"
            "                    c.crownMask = (Arg(a, \"-as03CrownMask\") ?? \"0\") == \"1\";\n"
            "                    c.crownMaskCheck = (Arg(a, \"-as03CrownMaskCheck\") ?? \"0\") == \"1\";\n")
    # 波頭の回り台の段の後に cmp の段
    cmp = r'''                // ---- 美術の見本03 の組み立て：利用者だけの比べの図の視点（回り台と同じ中心・方位の決め方。爪あり・飛沫なし）
                var cmpSpec = Arg(a, "-as03Cmp");
                if (Do("cmp") && !string.IsNullOrEmpty(cmpSpec))
                {
                    rep.as03Cmp = cmpSpec;
                    foreach (var t in times)
                    {
                        foreach (var item in cmpSpec.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries))
                        {
                            var f = item.Split(':');
                            string nm = f[0];
                            float caz = float.Parse(f[1], CultureInfo.InvariantCulture), cel2 = float.Parse(f[2], CultureInfo.InvariantCulture);
                            float cd = float.Parse(f[3], CultureInfo.InvariantCulture), cf = float.Parse(f[4], CultureInfo.InvariantCulture);
                            float cy = f.Length > 5 ? float.Parse(f[5], CultureInfo.InvariantCulture) : 9f;
                            Seek(c, t, true, true, false);
                            PlaceCmp(c, caz, cel2, cd, cf, cy);
                            CaptureView(c, "tt", od + "/cmp/" + nm + ".png", t, false, imgs, "cmp_claws", true, caz);
                        }
                    }
                }
'''
    s = rep(s, "                if (Do(\"fields\"))\n", cmp + "                if (Do(\"fields\"))\n")
    # 波頭の回り台だけ周りの海のシートを隠す（-pl30TtSea 0 を全体に渡すと回り台 tt・比べ cmp の海も消えるため。見本02 の回り台は海あり）
    s = rep(s, "                    var flatHid = new List<Renderer>();\n",
            "                    var flatHid = new List<Renderer>();\n"
            "                    bool ttSeaKeep = c.ttSea;\n"
            "                    if ((Arg(a, \"-as03CrestSea\") ?? \"0\") == \"0\") c.ttSea = false;   // 組み立て：波頭の回り台は主役波（と冠・爪）だけ（調べ S3・B1・B2 と同じ）\n")
    s = rep(s, "                    finally { foreach (var rr in flatHid) rr.enabled = true; }",
            "                    finally { foreach (var rr in flatHid) rr.enabled = true; c.ttSea = ttSeaKeep; }")
    # 冠の画を CaptureView の中で
    s = rep(s, "            try { Capture(cam, W, H, true, path, Color.white); imgs.Add(Rec(view, cond, path, t, c, az)); }",
            "            try\n            {\n                Capture(cam, W, H, true, path, Color.white); imgs.Add(Rec(view, cond, path, t, c, az));\n"
            "                if (c.crownMask && c.crownR.Count > 0 && (cond == \"claws\" || cond == \"crest_claws\" || cond == \"tt_claws\" || cond == \"cmp_claws\"))\n"
            "                {\n"
            "                    var mp = path.Substring(0, path.Length - 4) + \"_crownmask.png\";\n"
            "                    CrownMask(c, cam, mp, false); c.crownMaskFiles.Add(mp);\n"
            "                    if (c.crownMaskCheck && view == \"painting\") { var mp0 = path.Substring(0, path.Length - 4) + \"_crownmask_off.png\"; CrownMask(c, cam, mp0, true); c.crownMaskFiles.Add(mp0); }\n"
            "                }\n            }")
    # 関数：冠の画と比べの視点
    funcs = r'''
        // 美術の見本03 の組み立て：冠だけを ID の色 (0.25,0.5,1) にした画（線なし・MSAA なし・線形）。ほかのレンダラーは今の入切のまま、
        // 頂点を GPU で動かす材質（Keypose ほか）は色区の ID（_AF28IdMode）、それ以外は黒の ID。hideCrown で冠を隠した確かめの画。
        static void CrownMask(Ctx c, Camera camera, string pngPath, bool hideCrown)
        {
            var idShader = Shader.Find("GreatWave/ArtFirst/AF24 ID Flat");
            if (idShader == null) throw new InvalidOperationException("AF24 ID Flat がありません。");
            var crownM = new Material(idShader) { hideFlags = HideFlags.DontSave }; crownM.SetVector("_IdColor", new Vector4(0.25f, 0.5f, 1, 1));   // 書き出しの 8 ビットで (13,55,255)（_IdColor は色の値なので線形へ直る）。ほかの ID・色区の色と重ならない
            var blackM = new Material(idShader) { hideFlags = HideFlags.DontSave }; blackM.SetVector("_IdColor", new Vector4(0, 0, 0, 1));
            var saved = new List<(Renderer, Material[])>();
            var hidden = new List<Renderer>();
            try
            {
                // 冠は HideFlags.DontSave の物なので FindObjectsByType に出ない。覚えておいたレンダラーを直に替える（修正：1 回目はここが効かず、冠が色区の白のまま描かれた）
                foreach (var r in c.crownR)
                {
                    if (r == null) continue;
                    if (hideCrown) { if (r.enabled) { r.enabled = false; hidden.Add(r); } continue; }
                    saved.Add((r, r.sharedMaterials));
                    r.sharedMaterials = Enumerable.Repeat(crownM, Math.Max(1, r.sharedMaterials.Length)).ToArray();
                }
                foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.None))
                {
                    if (!r.enabled || r.forceRenderingOff || c.crownR.Contains(r)) continue;
                    var sh = r.sharedMaterial != null ? r.sharedMaterial.shader : null;
                    if (KeepMaterial(sh)) continue;
                    saved.Add((r, r.sharedMaterials));
                    r.sharedMaterials = Enumerable.Repeat(blackM, Math.Max(1, r.sharedMaterials.Length)).ToArray();
                }
                var clear = camera.clearFlags; var bg = camera.backgroundColor;
                camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0, 0, 0, 0);
                var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear) { antiAliasing = 1 };
                rt.Create();
                var tex = new Texture2D(W, H, TextureFormat.RGB24, false, true);
                var prev = camera.targetTexture; bool hdr = camera.allowHDR, aa = camera.allowMSAA; float asp = camera.aspect;
                camera.allowHDR = false; camera.allowMSAA = false;
                Shader.SetGlobalFloat("_AF28IdMode", 1);
                camera.aspect = (float)W / H; camera.targetTexture = rt; camera.Render();
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, W, H), 0, 0); tex.Apply(); RenderTexture.active = null;
                Directory.CreateDirectory(Path.GetDirectoryName(pngPath));
                File.WriteAllBytes(pngPath, tex.EncodeToPNG());
                camera.targetTexture = prev; camera.allowHDR = hdr; camera.allowMSAA = aa; camera.aspect = asp;
                camera.clearFlags = clear; camera.backgroundColor = bg;
                UnityEngine.Object.DestroyImmediate(tex); rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
            }
            finally
            {
                Shader.SetGlobalFloat("_AF28IdMode", 0);
                foreach (var (r, m) in saved) r.sharedMaterials = m;
                foreach (var r in hidden) r.enabled = true;
                UnityEngine.Object.DestroyImmediate(crownM); UnityEngine.Object.DestroyImmediate(blackM);
            }
        }

        // 美術の見本03 の組み立て：比べの視点（PlaceTurntable と同じ中心 o＋(0, cy, 0) と方位 0 の決め方。仰角・距離・画角を選べる）
        static void PlaceCmp(Ctx c, double azDeg, double elDeg, float dist, float fov, float cy)
        {
            var o = OriginWorld(c);
            var c0 = o + new Vector3(0, cy, 0);
            var pc = new Vector3(0f, 3f, -62f) - (c.oStarWorld + new Vector3(0, 9, 0));
            double az0 = Math.Atan2(pc.z, pc.x), az = az0 + azDeg * Math.PI / 180.0, el = elDeg * Math.PI / 180.0;
            var eye = c0 + new Vector3((float)(dist * Math.Cos(el) * Math.Cos(az)), (float)(dist * Math.Sin(el)), (float)(dist * Math.Cos(el) * Math.Sin(az)));
            var cam = c.cams["tt"];
            var up = elDeg > 80.0 ? new Vector3(-(float)Math.Cos(az), 0f, -(float)Math.Sin(az)) : Vector3.up;   // 真上に近い時は、見る側の奥を画の上にする
            cam.transform.position = eye; cam.transform.LookAt(c0, up); cam.fieldOfView = fov;
        }
'''
    s = rep(s, "\n        static bool WaveOnly(string view) =>", funcs + "\n        static bool WaveOnly(string view) =>")
    # 記録
    s = rep(s, "            File.WriteAllText(od + \"/as03surf_render_report.json\", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));\n"
               "            UnityEngine.Debug.Log(\"AS03SURF_RENDER_DONE images=\"",
            "            rep.as03CrownMask = c.crownMask; rep.as03CrownMaskFiles = c.crownMaskFiles.ToArray();\n"
            "            rep.as03AsmNote = \"美術の見本03 の組み立て：B1 の冠（-as03Crown）・B2 の彫りの面とシェーダー・見本02 の爪のうち面の内と近い海の 35 本（-pl32Claws）を 1 つの描画で。\" +\n"
            "                              \"冠の画（_crownmask）は冠だけ (13,55,255)。原画カメラの投影は使わない。PC オフスクリーン描画、HMD 実機ではない。\";\n"
            "            File.WriteAllText(od + \"/as03asm_render_report.json\", JsonUtility.ToJson(rep, true), new UTF8Encoding(false));\n"
            "            UnityEngine.Debug.Log(\"AS03ASM_RENDER_DONE images=\"")
    open(DST, "w", encoding="utf-8-sig", newline="\n").write(s)
    meta = DST + ".meta"
    if not os.path.isfile(meta):
        g = hashlib.md5(("AS03AsmRender " + src_sha).encode()).hexdigest()
        open(meta, "w", encoding="utf-8", newline="\n").write("fileFormatVersion: 2\nguid: %s\n" % g)
    print("written", DST, sha(DST))


if __name__ == "__main__":
    main()
