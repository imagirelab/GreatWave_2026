# -*- coding: utf-8 -*-
"""仕上げ28：コミットの一覧を依存で閉じる（py -3.10。git は読むだけ：ls-files と status。書き込みはしない）。

種のファイル（一覧の初めの形）から、Python の import（ast で読む。import X・from X import Y）と、ソースの中の文字列に出る
リポジトリの中のファイルの名前（.py・.json・.npz・.png・.txt・.cs・.shader・.cginc。同じフォルダーか、Tools の下で名前が 1 つに決まるもの）を
たどり、git が追っていないファイル（新しいファイル）を一覧へ足す。追っているが変えたファイル（git status の M）も、依存に出たら印を付けて返す
（ほかの群のコミットに入る予定のものは、呼び出し側が除いて記録する）。Unity/Build の下（Git 対象外）への依存は、別の一覧に出す。
禁止の場所の文字列（AGENTS.md の「旧試作の禁止」）が、一覧のファイルの中にないかも調べる（読むのは一覧のファイルだけ）。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_commit_deps.py <種の一覧.txt> <出力の一覧.txt> <報告.json>
"""
import ast
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXTS = (".py", ".json", ".npz", ".png", ".txt", ".cs", ".shader", ".cginc", ".sh", ".ps1")
# 禁止の場所（AGENTS.md）。一覧のファイルの中にこの文字列があれば報告する（参照モデルの 1 ファイルの名前は、記録の中の出典の書き方として許すので別に数える）
FORBIDDEN = [r"research[\\/]+Wave Simulation", r"Ukeyoe_Claw", r"Unity[\\/]+bigwave", r"GreatWave_2026[\\/]", r"Unity[\\/]+Ukeyoe\b",
             r"research[\\/]+model", r"reality scan"]
FORBIDDEN_OK = [r"research[\\/]+model[\\/]+wave_repair_zbrush2\.obj", r"reality scan[\\/]+北斋参考", r"research[\\/]+Wave Simulation[\\/]+1\.(abc|fbx)",
                r"Ukeyoe_Claw[\\/]+Docs[\\/]+Research[\\/]+Claw_Analysis[\\/]+README\.md", r"GreatWave_2026_Fresh"]


def git(*a):
    return subprocess.run(["git"] + list(a), cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout


def tracked_set():
    return set(x.strip() for x in git("ls-files", "-z").split("\0") if x.strip())


def modified_set():
    out = set()
    for line in git("status", "--porcelain", "-z").split("\0"):
        if len(line) > 3 and line[:2].strip() == "M":
            out.add(line[3:].strip())
    return out


def index_tools():
    idx = {}
    for root, dirs, files in os.walk(os.path.join(REPO, "Tools")):
        if "__pycache__" in root:
            continue
        for f in files:
            idx.setdefault(f, []).append(os.path.relpath(os.path.join(root, f), REPO).replace("\\", "/"))
    return idx


def deps_of(rel, idx):
    p = os.path.join(REPO, rel)
    here = os.path.dirname(rel)
    out, build, amb = set(), set(), set()
    try:
        src = open(p, encoding="utf-8").read()
    except Exception:
        return out, build, amb
    names = set()
    if rel.endswith(".py"):
        try:
            tree = ast.parse(src)
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    for a in n.names:
                        names.add(a.name.split(".")[0] + ".py")
                elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                    names.add(n.module.split(".")[0] + ".py")
        except SyntaxError:
            pass
    for m in re.finditer(r"[\"']([^\"'\n]*?)([A-Za-z0-9_\-\.]+(%s))[\"']" % "|".join(re.escape(e) for e in EXTS), src):
        full = (m.group(1) + m.group(2)).replace("\\", "/")
        if "Unity/Build" in full or "Build/" == full[:6]:
            build.add(full)
            continue
        names.add(m.group(2))
    for n in names:
        c = idx.get(n, [])
        if not c:
            continue
        same = [x for x in c if os.path.dirname(x) == here]
        pick = same if same else c
        if len(pick) == 1:
            out.add(pick[0])
        else:
            amb.add(n)
    return out, build, amb


def main():
    seed = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip() and not l.startswith("#")]
    tr = tracked_set(); md = modified_set(); idx = index_tools()
    lst = list(dict.fromkeys(seed)); seen = set()
    added, modified_deps, build_deps, ambiguous = [], set(), {}, {}
    k = 0
    while k < len(lst):
        f = lst[k]; k += 1
        if f in seen or not os.path.isfile(os.path.join(REPO, f)):
            continue
        seen.add(f)
        d, b, a = deps_of(f, idx)
        if b:
            build_deps[f] = sorted(b)
        if a:
            ambiguous[f] = sorted(a)
        for x in sorted(d):
            if x in tr:
                if x in md:
                    modified_deps.add(x)
                continue
            if x not in lst:
                lst.append(x); added.append({"file": x, "needed_by": f})
    missing = [f for f in lst if not os.path.isfile(os.path.join(REPO, f))]
    big = [f for f in lst if os.path.isfile(os.path.join(REPO, f)) and os.path.getsize(os.path.join(REPO, f)) > 5 * 1024 * 1024]
    bad = {}
    for f in lst:
        p = os.path.join(REPO, f)
        if not os.path.isfile(p) or f.endswith((".png", ".mp4", ".npz", ".hiplc")):
            continue
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for pat in FORBIDDEN:
            for m in re.finditer(pat, t):
                ctx = t[max(0, m.start() - 40): m.end() + 60]
                if any(re.search(ok, ctx) for ok in FORBIDDEN_OK):
                    continue
                bad.setdefault(f, []).append(ctx.replace("\n", " ")[:140])
    # バイナリ（hiplc）の中の文字列も調べる
    for f in lst:
        if f.endswith(".hiplc") and os.path.isfile(os.path.join(REPO, f)):
            b = open(os.path.join(REPO, f), "rb").read()
            for s in (b"wave_repair", b"research/model", b"research\\\\model", b"zbrush", b"reality scan", b"Wave Simulation", b"Ukeyoe"):
                if s in b:
                    bad.setdefault(f, []).append(s.decode())
    with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as fo:
        for f in lst:
            fo.write(f + "\n")
    rep = {"seed": len(seed), "total": len(lst), "added_untracked_deps": added, "tracked_but_modified_deps": sorted(modified_deps),
           "build_path_strings_in_code": build_deps, "ambiguous_names": ambiguous, "missing": missing, "over_5MB": big,
           "forbidden_strings": bad}
    json.dump(rep, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k2: (v if not isinstance(v, (list, dict)) else len(v)) for k2, v in rep.items()}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
