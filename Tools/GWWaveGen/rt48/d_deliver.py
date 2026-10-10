# -*- coding: utf-8 -*-
"""RT48 報告の段：動画・図・記録の写しを Docs/Evidence/RTPlayback/ に置き、run.json（SHA-256）を書き、提出の一覧を確かめる（py -3.10 -B）。
使い方:
  py -3.10 -B d_deliver.py copy      → 写しと run.json（写し先に違う中身のファイルがあれば止まる。同じ中身なら何もしない）
  py -3.10 -B d_deliver.py checklist → Unity/Build/RT48/commit_list.txt の確かめ（D4〜D6）
走らせる前に決めた確かめ（Unity/Build/RT48/record_ja.md の「報告の段」D1〜D6）:
  D1 写しの SHA-256 が元と同じ。D2 動画は 1 本 20 MB 未満。D3 動画のコマの数・速さ・大きさが記録と同じ（ffprobe）。
  D4 一覧の全部のファイルがあり、1 つ 20 MB 未満。D5 一覧に Library・Unity/Build・__pycache__ がない。
  D6 一覧のテキストのファイルに、利用者のアプリのデータのフォルダー・一時置き場・個人のパス（ユーザー名）がない。
何も消さない。git は使わない。"""
import os, sys, json, hashlib, shutil, subprocess, time, re, platform

ROOT = "G:/Unity/GreatWave_2026_Fresh"
B = ROOT + "/Unity/Build/RT48"
EV = ROOT + "/Docs/Evidence/RTPlayback"
FFPROBE = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffprobe.exe"
LIMIT = 20 * 1000 * 1000

# (写し先, 元, 説明)
VIDEOS = [
    ("rtp_01_boat556_bow_coarse.mp4", B + "/video/rt48_boat_seat556_bow_coarse.mp4", 1131, "船から（座席 556 m、船首の向き、目は水線から 1.2 m、縦の画角 60°）、138.25〜157.083 s、実時間。Unity のプレイヤーの画面外の描画"),
    ("rtp_02_side_coarse.mp4", B + "/video/rt48_side_coarse.mp4", 1426, "横から（x 470〜620 m を縦横同じ縮尺、上に断面の全体）、138.25〜162.0 s、実時間。焼いた曲線を Python（r_side.py）で描いた物で、Unity の絵ではない"),
    ("rtp_03_boat556_crest_coarse.mp4", B + "/video/rt48_boat_seat556_crest_coarse_extra.mp4", 1131, "参考：座席 556 m、頂に沿う向き（船首から 70°）、138.25〜157.083 s。Unity のプレイヤー"),
    ("rtp_04_boat574_bow_coarse.mp4", B + "/video/rt48_boat_seat574_bow_coarse_extra.mp4", 1193, "参考：座席 574 m、船首の向き、138.25〜158.117 s。Unity のプレイヤー"),
]
FIGS = [
    ("rtp_05_side_t154.710.png", B + "/video/side_coarse_t154.710.png", "横から、154.710 s（3714 コマ、巻き始め）。Python の絵"),
    ("rtp_06_side_t156.000.png", B + "/video/side_coarse_t156.000.png", "横から、156.0 s（3745 コマ、唇が前の面に付いて空気を囲む）。Python の絵"),
    ("rtp_07_boat556_bow_t154.717.png", B + "/video/frames_boat_seat556_bow/frame_00988.png", "船から（座席 556 m、船首）、154.717 s（3714 コマ）。Unity"),
    ("rtp_08_boat556_bow_t156.000.png", B + "/video/frames_boat_seat556_bow/frame_01065.png", "船から（座席 556 m、船首）、156.0 s（3745 コマ）。Unity"),
    ("rtp_09_boat556_bow_t157.083.png", B + "/video/frames_boat_seat556_bow/frame_01130.png", "船から（座席 556 m、船首）、157.083 s（3771 コマ、クリップの終わり）。Unity"),
    ("rtp_10_boat556_crest_t156.000.png", B + "/video/frames_boat_seat556_crest/frame_01065.png", "船から（座席 556 m、頂に沿う向き）、156.0 s。Unity"),
    ("rtp_11_endon_test_t156.000.png", B + "/unity/stills_coarse/coarse_endon_seat556_t156.000.png", "試しの視点：掃いた面の端（頂の向き 20 km）の 30 m 外から見た断面、156.0 s。体験では見えない所。Unity"),
    ("rtp_12_mock_botheyes.png", B + "/verify/timing/c7_1/mock_botheyes.png", "OpenXR の Mock Runtime（single-pass instanced、片眼 1512×1680）の左右の眼の絵。Unity のプレイヤー"),
]
REC = [  # 記録の写し（Unity/Build/RT48/ からの相対のまま rt48/ の下へ）
    "plan/plan_ja.md", "plan/review_ja.md", "plan/plan_frozen.json", "plan/plan_numbers.json",
    "record_ja.md", "data/record_ja.md", "data/c1a.json", "unity/record_ja.md",
    "verify/coarse/unity_editor_result.json", "verify/coarse/unity_player_result.json",
    "verify/timing/c7_1/summary.json", "verify/timing/c7_1/machine.json",
    "check/check_ja.md",
    "check/k_lib.py", "check/k_r3.py", "check/k_playback.py", "check/k_v2exact.py", "check/k_c3exact.py", "check/k_selfx.py",
    "check/k_interp.py", "check/k_boat.py", "check/k_taper.py", "check/k_timing.py", "check/k_timing_switch.py",
    "check/k_video.py", "check/k_video_side2.py", "check/k_video_events.py", "check/k_video_lip.py", "check/k_video_boat_timing.py",
    "check/k_snap.py", "check/k_mock.py",
    "check/out/k_playback_editor.json", "check/out/k_v2exact.json", "check/out/k_c3exact.json", "check/out/k_selfx.json",
    "check/out/k_interp.json", "check/out/k_boat.json", "check/out/k_taper.json", "check/out/k_timing.json",
    "check/out/k_timing_switch.json", "check/out/k_video_events.json", "check/out/k_video_lip.json",
    "check/out/k_video_boat_timing.json", "check/out/k_snap.json", "check/out/k_mock.json",
]
OTHER = {  # 大きくて写さない物（大きさと SHA-256 だけ書く）
    "bake_pairs": B + "/data/coarse/pairs.bin",
    "bake_loops": B + "/data/coarse/loops.bin",
    "bake_manifest": B + "/data/coarse/manifest.json",
    "player_exe": B + "/unity/player/RT48.exe",
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def put(src, dst, update=False):
    """update=True は記録の写し（元の記録がこの段で書き足されるため、この道具が前に写した物だけを新しくする）"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        if sha(dst) == sha(src):
            return "same"
        if not update:
            raise SystemExit("写し先に違う中身のファイルがある（上書きしない）: " + dst)
        shutil.copy2(src, dst)
        return "updated"
    shutil.copy2(src, dst)
    return "copied"


def probe(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_frames",
                        "-show_entries", "stream=codec_name,width,height,r_frame_rate,nb_read_frames,pix_fmt",
                        "-show_entries", "format=duration", "-of", "json", p], capture_output=True, text=True)
    d = json.loads(r.stdout)
    s = d["streams"][0]
    return dict(codec=s["codec_name"], width=s["width"], height=s["height"], fps=s["r_frame_rate"], pix_fmt=s.get("pix_fmt"),
                frames=int(s["nb_read_frames"]), duration_s=float(d["format"]["duration"]))


def copy():
    out = dict(schema="GreatWave.RTPlayback.deliver_run/1", date=time.strftime("%Y-%m-%d %H:%M"),
               note_ja="Docs/Evidence/RTPlayback を作った記録。この段で新しい流体の計算・Unity の描き直しはしていない（横からの静止画 1 枚 side_coarse_t154.710.png だけを r_side.py で描いた）。git の操作とダウンロードはしていない。何も消していない。パスはリポジトリからの相対",
               report="Docs/Progress/RT_Playback_ja.md", checks={}, videos=[], figures=[], records=[], not_copied={})
    out["commands"] = [
        "py -3.10 -B Tools/GWWaveGen/rt48/r_side.py coarse --stills 154.71   # 巻き始めのコマ（3714）の横からの静止画",
        "py -3.10 -B Tools/GWWaveGen/rt48/d_deliver.py copy                   # この証拠",
        "py -3.10 -B Tools/GWWaveGen/rt48/d_deliver.py checklist              # 提出の一覧の確かめ",
    ]
    out["upstream_commands_ja"] = {
        "計画": "py -3.10 Tools/GWWaveGen/rt48/p_inspect.py → plan/plan_numbers.json、plan_ja.md（走らせる前に書いて凍結した）",
        "焼き": "py -3.10 r_c1.py a（C1 (a)）、py -3.10 r_bake.py coarse（粗い元、C3・C4・K・船の表）、py -3.10 r_index.py",
        "Unity": "u_unity.ps1 で RT48SceneBuilder・RT48SelfTest・RT48PlayerBuild（Unity 6000.4.3f1 の batchmode）",
        "つなぎ・確かめ": "py -3.10 v_prep.py coarse → RT48VerifyEditor（Editor）と RT48.exe -rt48export（プレイヤー）→ py -3.10 v_compare.py coarse unity_editor／unity_player",
        "動画": "RT48.exe -rt48capture（1/60 s おき）→ ffmpeg libx264、py -3.10 r_side.py coarse",
        "時間": "powershell -File v_timing.ps1 -Tag c7_1 → py -3.10 v_timing_sum.py verify/timing/c7_1",
        "独立の確かめ": "Unity/Build/RT48/check/k_*.py（プロジェクトの比べる道具を読み込まない）",
        "R3e（まだ走っていない）": "py -3.10 r_chain.py rerun/cfg/cfg_R3e.json --after（R4d の後ろで待つ）→ r_after.py",
    }
    try:
        import numpy, scipy, PIL, cv2
        pv = dict(numpy=numpy.__version__, scipy=scipy.__version__, pillow=PIL.__version__, opencv=cv2.__version__)
    except Exception as e:  # noqa
        pv = dict(error=str(e))
    out["versions"] = dict(python=platform.python_version(), **pv, unity="6000.4.3f1（Built-in、OpenXR 1.16.1、single-pass instanced）",
                           ffmpeg="ffmpeg 2024-12-19-git-494c961379-full_build（libx264、yuv420p）", houdini_source="FLIP42 R3：Houdini 22.0.466 hython（この段では動かしていない）")
    ok = True
    for name, src, nf, desc in VIDEOS:
        dst = EV + "/" + name
        st = put(src, dst)
        s1, s2 = sha(src), sha(dst)
        pr = probe(dst)
        size = os.path.getsize(dst)
        d1, d2 = s1 == s2, size < LIMIT
        d3 = pr["frames"] == nf and pr["fps"] == "60/1" and pr["width"] == 1920 and pr["height"] == 1080 and pr["codec"] == "h264"
        ok &= d1 and d2 and d3
        out["videos"].append(dict(path=rel(dst), source=rel(src), bytes=size, sha256=s2, source_sha256=s1, action=st, desc_ja=desc,
                                  probe=pr, expected_frames=nf, D1=d1, D2=d2, D3=d3))
    for name, src, desc in FIGS:
        dst = EV + "/" + name
        st = put(src, dst)
        s1, s2 = sha(src), sha(dst)
        ok &= s1 == s2
        out["figures"].append(dict(path=rel(dst), source=rel(src), bytes=os.path.getsize(dst), sha256=s2, D1=s1 == s2, action=st, desc_ja=desc))
    for r in REC:
        src, dst = B + "/" + r, EV + "/rt48/" + r
        st = put(src, dst, update=True)
        s1, s2 = sha(src), sha(dst)
        ok &= s1 == s2
        out["records"].append(dict(path=rel(dst), source=rel(src), bytes=os.path.getsize(dst), sha256=s2, D1=s1 == s2, action=st))
    for k, p in OTHER.items():
        out["not_copied"][k] = dict(path=rel(p), bytes=os.path.getsize(p), sha256=sha(p), why_ja="大きい（Git 対象外の Unity/Build/RT48 に置いたまま）")
    # R3 の入力（計画の時に記録した SHA-256 と今の値）
    pn = json.load(open(B + "/plan/plan_numbers.json", encoding="utf-8"))
    r3 = {}
    r3dir = ROOT + "/Unity/Build/FLIP42/runs/R3/"
    for kk, h in pn.get("inputs_sha256", {}).items():
        q = r3dir + kk
        now = sha(q) if os.path.exists(q) else None
        r3[kk] = dict(path=rel(q), sha256_plan=h, sha256_now=now, same=(now == h))
    out["r3_inputs"] = r3
    # 道具・資産・場面
    tools = {}
    for f in sorted(os.listdir(ROOT + "/Tools/GWWaveGen/rt48")):
        p = ROOT + "/Tools/GWWaveGen/rt48/" + f
        if os.path.isfile(p):
            tools[rel(p)] = sha(p)
    out["tools"] = tools
    assets = {}
    base = ROOT + "/Unity/Assets/GreatWave/RT48"
    for dp, dn, fn in os.walk(base):
        for f in sorted(fn):
            p = os.path.join(dp, f)
            assets[rel(p)] = sha(p)
    assets[rel(base + ".meta")] = sha(base + ".meta")
    out["assets"] = dict(sorted(assets.items()))
    out["scene"] = dict(path="Unity/Assets/GreatWave/RT48/Scenes/RT48_Playback.unity", sha256=assets.get("Unity/Assets/GreatWave/RT48/Scenes/RT48_Playback.unity"))
    out["checks"] = dict(D1_D3_all=ok)
    js = EV + "/run.json"
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    open(js, "w", encoding="utf-8").write(txt)   # run.json はこの道具の出力なので書き直す
    print(json.dumps(dict(videos=[(v["path"], v["bytes"], v["probe"]["frames"], round(v["probe"]["duration_s"], 3), v["D1"], v["D2"], v["D3"]) for v in out["videos"]],
                          figures=len(out["figures"]), records=len(out["records"]), r3_inputs_same=all(v["same"] for v in r3.values()) if r3 else None,
                          r3_inputs=len(r3), tools=len(tools), assets=len(assets), ok=ok), ensure_ascii=False, indent=1))
    if not ok:
        raise SystemExit("D1〜D3 のどれかが外れた")


# 探す字は分けて書く（この道具そのものも一覧に入り、字のままだと自分に当たるため）
_U = os.environ.get("USERNAME", "") or "-"
# アプリのデータのフォルダーは、後ろにパスの区切りがある時だけ数える（シェーダーの構造体名 appdata に当たらないように）
BAD = [re.compile("App" + r"Data[\\/]", re.I), re.compile(r"[\\/]" + "Te" + r"mp[\\/]", re.I), re.compile(re.escape(_U), re.I),
       re.compile(r"[A-Za-z]:[\\/]" + "Us" + r"ers[\\/]", re.I)]
TEXT = (".md", ".txt", ".json", ".py", ".ps1", ".cs", ".shader", ".hlsl", ".compute", ".meta", ".unity", ".mat", ".asset")


def checklist():
    lst = B + "/commit_list.txt"
    items = [l.strip() for l in open(lst, encoding="utf-8") if l.strip()]
    res = dict(n=len(items), missing=[], big=[], forbidden=[], personal=[], dup=len(items) - len(set(items)))
    for it in items:
        p = ROOT + "/" + it
        if not os.path.isfile(p):
            res["missing"].append(it)
            continue
        if os.path.getsize(p) >= LIMIT:
            res["big"].append((it, os.path.getsize(p)))
        if re.search(r"(^|/)Library/|^Unity/Build/|__pycache__|\.pyc$", it):
            res["forbidden"].append(it)
        if it.lower().endswith(TEXT):
            t = open(p, encoding="utf-8", errors="replace").read()
            for b in BAD:
                m = b.search(t)
                if m:
                    res["personal"].append((it, b.pattern, t[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")))
    res["ok"] = not (res["missing"] or res["big"] or res["forbidden"] or res["personal"] or res["dup"])
    tot = sum(os.path.getsize(ROOT + "/" + it) for it in items if os.path.isfile(ROOT + "/" + it))
    res["total_bytes"] = tot
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if not res["ok"]:
        raise SystemExit("D4〜D6 のどれかが外れた")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    {"copy": copy, "checklist": checklist}[sys.argv[1]]()
