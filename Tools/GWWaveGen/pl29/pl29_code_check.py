# -*- coding: utf-8 -*-
"""仕上げ29（Q28）のコードの点検：主役波と周りの海の材質の道（場面 → シートの読み込み → 材質 → シェーダー → 面の座標の生成器）に、
原画カメラからの投影（原画カメラの行列・原画の色区の表・投影の UV3・焼き込みの色区テクスチャ）が残っていないことを、ファイルの中身で確かめる。

確かめること（どれも Polish29 の場面 PL29_Release.unity・PL29_SinglePlayback.unity が実際に使う物）：
  1) 主役波のシェーダー PL29_Ukiyoe_Hero.shader：テクスチャ（sampler2D・Texture2D・tex2D・_SdfTex）も、原画カメラの行列（_PL29PaintVP など）も、
     焼き込みの UV3（TEXCOORD2）も読まない。読む物は、keypose のバッファ（位置・T_white）・頂点の番号・面の座標（TEXCOORD3〜5）・材質の数・大域の切替だけ。
  2) PL29UkiyoeHero.cs：面の座標のファイルと材質だけを扱い、カメラ・焼き込みのパスに触れない。
  3) 面の座標の生成器 pl29_hero_attr.py：入力は K*′ の .gwb と meta（目印の列・H0）だけ。カメラ・原画・投影を読まない。
  4) 場面：主役波の DS30SheetPlayer の sdfPath・warpPath・uv3File が空、面の材質が PL29_Ukiyoe_Hero.mat、PL29UkiyoeHero が付く、
     爪の DS36ClawPalette（原画カメラの投影の表で塗る）が切ってある。
  5) 材質 PL29_Ukiyoe_Hero.mat：シェーダーが PL29 Ukiyoe Keypose、テクスチャの欄が空。
  6) 周りの海（near・far）：色の表（ds36_sea_ramp_256・ds36_sea_uv3_*）を作る ds36_palette_prep.py の sea_part は、t* の高さ（tstar_world）だけを使い、
     原画の色区の表（PAINT_SDF・LABELS）やカメラを読まない（関数の本体を抜き出して調べる）。シートの読み込み DS30SheetPlayer は、そのパスを読むだけ。
  7) 実行の記録：PL29Render の報告で主役波の sdfPath・warpPath・uv3File が空、UV3 の出どころが「なし（平塗り）」、Play モードの確かめで全コマ
     PL29 のシェーダー・焼き込みのパスが空。
  8) 記録のみ（主役波・海の材質の道の外で、原画視点に依る物）：設計38 の主役波の線の印（原画視点で原画にない線を描かない頂点の印）と押し下げの重み、
     設計36 の爪の投影の表（Polish29 の場面では切った）、設計50 の DS50_Release.unity（仕上げ29 の前の投影のまま。体験の exe は 10 で作る）。
  ［修正の回で加えた］
  9) 爪の材質 PL29_Claw_Shade.shader と PL29ClawShade.cs：テクスチャ・原画カメラの行列・投影を読まない。色の段は帯の頂点の値（UV2 の sin φ）だけ。
     PL29ClawShade は設計38 の爪の線の原画カメラからの離れの重みを切る（_DS38PaintFade を 0 にする）だけで、カメラを読まない。
  10) Release のビルド（PL29ReleaseBuild）：ビルドした場面が PL29_Release.unity だけ、StreamingAssets/gwdata に主役波の採用のデータ
     （Build/Polish/28/G_p28rec/art_on、Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb、G_p28rec の時間曲線、面の座標 pl29_hero_attr_f32.bin）があり、
     焼き込みのファイル（uvsdf・uvwarp・ds29_uv3、Build/Design/29R01/bake_kp、Build/Design/31/white/hero_pkg）がない（ディスクの上のフォルダーを数える）。
     プレイヤーを PC で 1 回動かした player.log に PL29_HERO_APPLIED（焼き込みのパスが空）と PL29_CLAW_SHADE_APPLIED があり、自動の試しが pass。
  11) 主役波のシェーダーの _WorldSpaceCameraPos は、白と藍の境の線を面が視線にほぼ平行な所で薄めるためだけに使う（線は画面の上の太さ。色の範囲は視点によらない）。
出力：<out>/code_check.json。使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_code_check.py --render <PL29Render の出力> --playmode <dir> [<dir> …] --out <dir>
       ［修正の回］--release-build <pl29_build.json> --player-run <run の dir> を足すと 10 を確かめる。
"""
import argparse
import ast
import hashlib
import json
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
A = os.path.join(REPO, "Unity", "Assets", "GreatWave")
SHADER = os.path.join(A, "Polish29", "Shaders", "PL29_Ukiyoe_Hero.shader")
COMP = os.path.join(A, "Polish29", "Scripts", "PL29UkiyoeHero.cs")
ATTR = os.path.join(REPO, "Tools", "GWWaveGen", "pl29", "pl29_hero_attr.py")
MAT = os.path.join(A, "Polish29", "Materials", "PL29_Ukiyoe_Hero.mat")
SCENES = [os.path.join(A, "Polish29", "Scenes", "PL29_Release.unity"), os.path.join(A, "Polish29", "Scenes", "PL29_SinglePlayback.unity")]
SEA_PREP = os.path.join(REPO, "Tools", "GWWaveGen", "ds36", "ds36_palette_prep.py")
SHEET = os.path.join(A, "Design30", "Scripts", "DS30SheetPlayer.cs")
LINE38 = os.path.join(A, "Design38", "Shaders", "DS38_Outline_Keypose.shader")
CLAW36 = os.path.join(A, "Design36", "Shaders", "DS36_Claw_Palette.shader")
CLAWSH = os.path.join(A, "Polish29", "Shaders", "PL29_Claw_Shade.shader")
CLAWCOMP = os.path.join(A, "Polish29", "Scripts", "PL29ClawShade.cs")
CLAWMAT = os.path.join(A, "Polish29", "Materials", "PL29_Claw_Shade.mat")
DS50 = os.path.join(A, "Design50", "Scenes", "DS50_Release.unity")
BAKE_RE = r"uvsdf|uvwarp|ds29_uv3|29R01/bake_kp|31/white/hero_pkg"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def strip_comments_hlsl(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return "\n".join(l.split("//")[0] for l in s.splitlines())


def strip_comments_cs(s):
    return strip_comments_hlsl(s)


def guid(meta):
    m = re.search(r"guid: ([0-9a-f]{32})", read(meta))
    return m.group(1) if m else ""


def check_shader():
    code = strip_comments_hlsl(read(SHADER))
    # Properties ブロックの表示名（"…"）は文字列なので除いて調べる
    code_ns = re.sub(r'"[^"\n]*"', '""', code)
    bad = {k: len(re.findall(k, code_ns)) for k in [r"\bsampler2D\b", r"\bTexture2D\b", r"\btex2D", r"\bSAMPLE_TEXTURE", r"_SdfTex", r"PaintVP", r"_LabelSdf",
                                                     r"\bunity_MatrixVP\b", r"ComputeScreenPos", r"\bUNITY_MATRIX_VP\b"]}
    # 頂点の入力（appdata）
    m = re.search(r"struct appdata\s*\{(.*?)\};", code, flags=re.S)
    inputs = [l.strip() for l in m.group(1).splitlines() if l.strip()] if m else []
    uses_tc2_input = any("TEXCOORD2" in l for l in inputs)
    buffers = sorted(set(re.findall(r"(_DS27\w+)", code)))
    ok = all(v == 0 for v in bad.values()) and not uses_tc2_input
    # クリップ座標は表示中のカメラの UnityWorldToClipPos だけ（原画カメラの行列を持たない）
    clip = re.findall(r"UnityWorldToClipPos|UnityObjectToClipPos|mul\(\s*_\w+VP", code)
    # _WorldSpaceCameraPos は線の薄め（_EdgeGrazing）だけに使う：その変数を含む行が「float3 V =」の 1 行で、lineCov の計算の中にあること
    cam_lines = [l.strip() for l in code.splitlines() if "_WorldSpaceCameraPos" in l]
    cam_ok = len(cam_lines) <= 1 and all(l.startswith("float3 V =") for l in cam_lines) and ("lineCov *= saturate((nv" in code)
    return {"file": os.path.relpath(SHADER, REPO).replace("\\", "/"), "sha256": sha(SHADER), "forbiddenTokenCounts": bad,
            "vertexInputs": inputs, "readsBakeUv3_TEXCOORD2": uses_tc2_input, "keyposeAndGlobals": buffers, "clipTransforms": clip,
            "cameraPosLines": cam_lines, "cameraPosOnlyForLineFade": cam_ok, "pass": ok and clip == ["UnityWorldToClipPos"] and cam_ok}


def check_component():
    code = strip_comments_cs(read(COMP))
    code = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', code)   # 文字列（player.log へ出す説明）は除いて調べる
    # 焼き込みのパスは書かない・読み込まない（修正の回で player.log へ値を出すために読む行だけは許す）
    toks = {k: len(re.findall(k, code)) for k in [r"\bCamera\b", r"\b(sdfPath|warpPath|uv3File)\s*=[^=]", r"Read\w*\([^)]*(sdfPath|warpPath|uv3File)",
                                                   r"[Pp]aint", r"worldToCamera", r"projectionMatrix", r"SetUVs\(2"]}
    return {"file": os.path.relpath(COMP, REPO).replace("\\", "/"), "sha256": sha(COMP), "tokenCounts": toks, "pass": all(v == 0 for v in toks.values())}


def check_claw():
    sh = strip_comments_hlsl(read(CLAWSH))
    sh_ns = re.sub(r'"[^"\n]*"', '""', sh)
    bad = {k: len(re.findall(k, sh_ns)) for k in [r"\bsampler2D\b", r"\bTexture2D\b", r"\btex2D", r"_LabelSdf", r"PaintVP", r"ComputeScreenPos", r"_WorldSpaceCameraPos"]}
    clip = re.findall(r"UnityWorldToClipPos|UnityObjectToClipPos|mul\(\s*_\w+VP", sh)
    cs = strip_comments_cs(read(CLAWCOMP))
    ctoks = {k: len(re.findall(k, cs)) for k in [r"\bCamera\b", r"worldToCamera", r"projectionMatrix", r"_DS38PaintCamPos"]}
    fade_zero = bool(re.search(r'SetVector\("_DS38PaintFade",\s*Vector4\.zero\)', cs))
    mt = read(CLAWMAT)
    sg = re.search(r"m_Shader: \{fileID: \d+, guid: ([0-9a-f]{32})", mt).group(1)
    tex = re.search(r"m_TexEnvs: (\[\])?", mt)
    ok = all(v == 0 for v in bad.values()) and clip == ["UnityObjectToClipPos"] and all(v == 0 for v in ctoks.values()) and fade_zero and sg == guid(CLAWSH + ".meta")
    return {"shader": os.path.relpath(CLAWSH, REPO).replace("\\", "/"), "shaderSha256": sha(CLAWSH), "forbiddenTokenCounts": bad, "clipTransforms": clip,
            "component": os.path.relpath(CLAWCOMP, REPO).replace("\\", "/"), "componentSha256": sha(CLAWCOMP), "componentTokenCounts": ctoks,
            "linesPaintFadeSetToZero": fade_zero, "material": os.path.relpath(CLAWMAT, REPO).replace("\\", "/"), "materialSha256": sha(CLAWMAT),
            "materialShaderIsClawShade": sg == guid(CLAWSH + ".meta"), "materialTexEnvsEmpty": bool(tex and tex.group(1) == "[]"), "pass": ok}


def check_attr():
    src = read(ATTR)
    tree = ast.parse(src)
    code_no_doc = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute, ast.Constant)):
            pass
    # 文字列の定数（docstring・説明）を除いた識別子だけを見る
    names = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)})
    hits = [n for n in names if re.search(r"cam|paint|proj|label|sdf|uvwarp|vp\b", n, flags=re.I)]
    opens = re.findall(r"open\(([^)]*)\)", src)
    return {"file": os.path.relpath(ATTR, REPO).replace("\\", "/"), "sha256": sha(ATTR), "identifierHits": hits, "fileOpens": opens,
            "inputsJa": "--gwb（K*′ の .gwb）と --meta（目印の列 profile.index と H0_m）だけ", "pass": len(hits) == 0}


def scene_blocks(text):
    return text.split("\n--- ")


def check_scene(p, mat_guid, comp_guid, claw36_guid, clawcomp_guid="", clawmat_guid=""):
    t = read(p)
    blocks = scene_blocks(t)
    hero = [b for b in blocks if "sheetName: hero" in b]
    out = {"file": os.path.relpath(p, REPO).replace("\\", "/"), "sha256": sha(p)}
    if len(hero) != 1:
        out["pass"] = False; out["errorJa"] = "主役波のシートが 1 つでない"
        return out
    h = hero[0]
    def field(name):
        m = re.search(r"\n  " + name + r": ?(.*)", h)
        return m.group(1).strip() if m else None
    out["hero"] = {k: field(k) for k in ["packageDir", "meshGwb", "uv3File", "warpPath", "sdfPath", "flatClass"]}
    go = re.search(r"m_GameObject: \{fileID: (\d+)\}", h).group(1)
    rend = [b for b in blocks if b.startswith("!u!23 ") and ("m_GameObject: {fileID: %s}" % go) in b]
    out["heroRendererMaterialGuids"] = re.findall(r"guid: ([0-9a-f]{32}), type: 2", rend[0]) if rend else []
    comps = [b for b in blocks if ("m_GameObject: {fileID: %s}" % go) in b and comp_guid in b]
    out["pl29UkiyoeHeroOnHero"] = len(comps) == 1
    claws = [b for b in blocks if claw36_guid and claw36_guid in b and "m_Script" in b]
    out["ds36ClawPaletteEnabled"] = [bool(re.search(r"m_Enabled: 1", b)) for b in claws]
    tw = re.search(r"\n  timewarpPath: (.*)", t)
    out["timewarpPath"] = tw.group(1).strip() if tw else None
    out["pass"] = (out["hero"]["sdfPath"] == "" and out["hero"]["warpPath"] == "" and out["hero"]["uv3File"] == "" and
                   out["heroRendererMaterialGuids"] == [mat_guid] and out["pl29UkiyoeHeroOnHero"] and not any(out["ds36ClawPaletteEnabled"]))
    if clawcomp_guid:
        cb = [b for b in blocks if clawcomp_guid in b and "m_Script" in b]
        out["pl29ClawShade"] = [{"enabled": bool(re.search(r"m_Enabled: 1", b)), "materialGuid": (re.findall(r"material: \{fileID: \d+, guid: ([0-9a-f]{32})", b) or [""])[0],
                                 "linesEverywhere": bool(re.search(r"linesEverywhere: 1", b))} for b in cb]
        has_claws = "GreatWave.Design34.DS34ClawPlayer" in t
        out["hasClawPlayer"] = has_claws
        # 焼き込みのファイルの名前：周りの海のシートで、色の表（sdfPath）が空で平塗り（flatClass）のものの uv3File は使われない残りなので、別に記録する
        sea_flat = []
        other = []
        for bl in blocks:
            hits = sorted(set(re.findall(r"[^\s:]*(?:%s)[^\s]*" % BAKE_RE, bl)))
            if not hits:
                continue
            sn = re.search(r"\n  sheetName: (\w+)", bl)
            sdf = re.search(r"\n  sdfPath: ?(.*)", bl)
            if sn and sn.group(1) in ("near", "far") and sdf and sdf.group(1).strip() == "":
                sea_flat += ["%s: %s" % (sn.group(1), h) for h in hits]
            else:
                other += hits
        out["bakeStringsInScene"] = sorted(set(other))
        out["seaFlatUv3Leftovers"] = sea_flat
        claw_ok = (not has_claws) or (len(cb) >= 1 and all(x["enabled"] and x["materialGuid"] == clawmat_guid and x["linesEverywhere"] for x in out["pl29ClawShade"]))
        out["pass"] = out["pass"] and claw_ok and len(out["bakeStringsInScene"]) == 0
    return out


def check_release(build_json, run_dir):
    b = json.load(open(build_json, encoding="utf-8-sig"))
    root = b["dataRoot"]
    files = []
    for dp, dn, fn in os.walk(root):
        for f in fn:
            files.append(os.path.relpath(os.path.join(dp, f), root).replace("\\", "/"))
    must = ["Build/Polish/28/G_p28rec/art_on/ds27_keypose.json", "Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb",
            "Build/Polish/28/G_p28rec/timewarp_G_p28rec.json", b["heroAttr"]]
    art_on = [f for f in files if f.startswith("Build/Polish/28/G_p28rec/art_on/")]
    bake = [f for f in files if re.search(BAKE_RE, f)]
    log = open(os.path.join(run_dir, "player.log"), encoding="utf-8", errors="replace").read()
    hero_lines = [l.strip() for l in log.splitlines() if "PL29_HERO_APPLIED" in l]
    claw_lines = [l.strip() for l in log.splitlines() if "PL29_CLAW_SHADE_APPLIED" in l]
    rp = os.path.join(run_dir, "report.json")
    rpt = json.load(open(rp, encoding="utf-8-sig")) if os.path.exists(rp) else {}
    out = {"buildJson": build_json.replace("\\", "/"), "buildJsonSha256": sha(build_json), "scenesInBuild": b["scenesInBuild"], "exeSha256": b["exeSha256"],
           "dataRoot": root.replace("\\", "/"), "dataFilesOnDisk": len(files), "mustHave": {m: (m in files) for m in must}, "artOnFiles": len(art_on),
           "bakeFilesOnDisk": bake, "heroAppliedLog": hero_lines[:2], "clawShadeLog": claw_lines[:2],
           "playerRun": {"dir": run_dir.replace("\\", "/"), "pass": rpt.get("pass"), "errors": rpt.get("errors"), "exceptions": rpt.get("exceptions"), "quitCause": rpt.get("quitCause")}}
    out["pass"] = (b["scenesInBuild"] == ["Assets/GreatWave/Polish29/Scenes/PL29_Release.unity"] and all(out["mustHave"].values()) and len(art_on) > 0 and len(bake) == 0
                   and len(hero_lines) >= 1 and all("sdfPath='' warpPath='' uv3File=''" in l and "PL29 Ukiyoe Keypose" in l for l in hero_lines)
                   and len(claw_lines) >= 1 and rpt.get("pass") is True and rpt.get("errors") == 0 and rpt.get("exceptions") == 0)
    return out


def check_material(shader_guid):
    t = read(MAT)
    sg = re.search(r"m_Shader: \{fileID: \d+, guid: ([0-9a-f]{32})", t).group(1)
    tex = re.search(r"m_TexEnvs: (\[\])?", t)
    return {"file": os.path.relpath(MAT, REPO).replace("\\", "/"), "sha256": sha(MAT), "shaderGuid": sg, "shaderIsPL29": sg == shader_guid,
            "texEnvsEmpty": bool(tex and tex.group(1) == "[]"), "pass": sg == shader_guid and bool(tex and tex.group(1) == "[]")}


def check_sea():
    src = read(SEA_PREP)
    tree = ast.parse(src)
    fn = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    res = {"file": os.path.relpath(SEA_PREP, REPO).replace("\\", "/"), "sha256": sha(SEA_PREP)}
    seen, stack, called = set(), ["sea_part"], []
    while stack:
        f = stack.pop()
        if f in seen or f not in fn:
            continue
        seen.add(f)
        for n in ast.walk(fn[f]):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in fn:
                stack.append(n.func.id)
    called = sorted(seen)
    names = set()
    for f in called:
        for n in ast.walk(fn[f]):
            if isinstance(n, ast.Name):
                names.add(n.id)
    hits = sorted(n for n in names if n in ("PAINT_SDF", "PAINT_META", "LABELS", "LABELS_HI", "REGIONS", "INVENTORY", "paint_sdf_display2x", "claw_part"))
    res["seaPartCalls"] = called
    res["paintingInputsReachedFromSeaPart"] = hits
    res["pass"] = len(hits) == 0
    sheet = strip_comments_cs(read(SHEET))
    res["sheetPlayerCameraTokens"] = len(re.findall(r"\bCamera\b|worldToCamera|projectionMatrix", sheet))
    res["pass"] = res["pass"] and res["sheetPlayerCameraTokens"] == 0
    return res


def runtime(render_dir, playdirs):
    r = json.load(open(os.path.join(render_dir, "pl29_render_report.json"), encoding="utf-8"))
    out = {"render": {"heroSdf": r.get("heroSdf"), "heroUvWarp": r.get("heroUvWarp"), "heroUv3File": r.get("heroUv3File"), "heroUv3Source": r.get("heroUv3Source"),
                      "heroShader": r.get("heroShader"), "clawPalette": r.get("clawPalette")}}
    out["render"]["pass"] = r.get("heroSdf") == "" and r.get("heroUvWarp") == "" and r.get("heroUv3File") == "" and (r.get("heroUv3Source") or "").startswith("なし") and r.get("clawPalette") == "d34"
    pm = []
    for d in playdirs:
        j = json.load(open(os.path.join(d, "pl29_playmode.json"), encoding="utf-8"))
        pm.append({"scene": j["scene"], "end": j["end"], "rows": j["rows"], "sawPl29Shader": j["sawPl29Shader"], "sawApplied": j["sawApplied"],
                   "bakePathsEmptyAllFrames": j["bakePathsEmptyAllFrames"], "pass": j["sawPl29Shader"] and j["sawApplied"] and j["bakePathsEmptyAllFrames"]})
    out["playmode"] = pm
    return out


def record_only():
    l38 = strip_comments_hlsl(read(LINE38))
    c36 = strip_comments_hlsl(read(CLAW36))
    return {"ds38_outline": {"file": os.path.relpath(LINE38, REPO).replace("\\", "/"), "usesLineMask": "_DS38LineMask" in l38, "usesPushPaint": "_DS38PushPaint" in l38,
                             "noteJa": "主役波の外殻線（設計38）は、原画視点で原画にない線を描かない頂点の印（ds38_hero_linemask_f32.bin、原画視点で作った）と、原画視点の押し下げの重みを使う。"
                                       "線の見える・見えないの決まりで、色・溝・白の材質ではない。仕上げ38 で扱う（記録のみ）。"},
            "ds50_release_scene": {"file": os.path.relpath(DS50, REPO).replace("\\", "/"), "sha256": sha(DS50),
                                   "bakeStrings": sorted(set(re.findall(r"[^\s:]*(?:%s)[^\s]*" % BAKE_RE, read(DS50)))),
                                   "noteJa": "設計50 の場面（と Build/Design/50/release の exe）は仕上げ29 の前の投影の焼き込みのまま。記録のため変えない。体験の Release は PL29ReleaseBuild が PL29_Release.unity から作る（10）。"},
            "ds36_claw_palette": {"file": os.path.relpath(CLAW36, REPO).replace("\\", "/"), "usesPaintingLabelSdf": "_LabelSdf" in c36,
                                  "noteJa": "設計36 の爪の色は原画視点の画面の位置で原画の色区の表を引く（投影）。Polish29 の場面では DS36ClawPalette を切り、設計34 の視点によらない白・淡い水色にした。"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", required=True)
    ap.add_argument("--playmode", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--release-build", default="")
    ap.add_argument("--player-run", default="")
    a = ap.parse_args()
    shader_guid = guid(SHADER + ".meta")
    mat_guid = guid(MAT + ".meta")
    comp_guid = guid(COMP + ".meta")
    claw36_guid = guid(os.path.join(A, "Design36", "Scripts", "DS36ClawPalette.cs.meta"))
    clawcomp_guid = guid(CLAWCOMP + ".meta") if os.path.exists(CLAWCOMP + ".meta") else ""
    clawmat_guid = guid(CLAWMAT + ".meta") if os.path.exists(CLAWMAT + ".meta") else ""
    res = {"schema": "GreatWave.Polish29.code_check/1", "noteJa": __doc__.strip().split("\n")[0],
           "shader": check_shader(), "component": check_component(), "attrGenerator": check_attr(), "material": check_material(shader_guid),
           "scenes": [check_scene(p, mat_guid, comp_guid, claw36_guid, clawcomp_guid, clawmat_guid) for p in SCENES], "sea": check_sea(), "runtime": runtime(a.render, a.playmode),
           "recordOnly": record_only()}
    if clawcomp_guid:
        res["claw"] = check_claw()
    if a.release_build:
        res["release"] = check_release(a.release_build, a.player_run)
    res["allPass"] = all([res["shader"]["pass"], res["component"]["pass"], res["attrGenerator"]["pass"], res["material"]["pass"], res["sea"]["pass"],
                          all(s["pass"] for s in res["scenes"]), res["runtime"]["render"]["pass"], all(p["pass"] for p in res["runtime"]["playmode"]),
                          res.get("claw", {"pass": True})["pass"], res.get("release", {"pass": True})["pass"]])
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "code_check.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("allPass", res["allPass"], {k: (v["pass"] if isinstance(v, dict) and "pass" in v else None) for k, v in res.items() if isinstance(v, dict)},
          [s["pass"] for s in res["scenes"]])


if __name__ == "__main__":
    main()
