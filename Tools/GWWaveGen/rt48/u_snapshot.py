"""RT48 Unity 側：プロジェクトのファイルの SHA-256 の一覧を取り、前後で比べる（RT48 の外を変えていないことの確かめ）。

使い方：
  python u_snapshot.py take <出力.json>            Assets・ProjectSettings・Packages の全部のファイル
  python u_snapshot.py diff <前.json> <後.json>     増えた・消えた・変わったファイルを出す（RT48 の下とそれ以外に分ける）
読むだけで、プロジェクトのファイルは変えない。
"""
import hashlib, json, os, sys, time

PROJECT = r"G:/Unity/GreatWave_2026_Fresh/Unity"
ROOTS = ["Assets", "ProjectSettings", "Packages"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def take(out):
    files = {}
    for r in ROOTS:
        for dp, dn, fn in os.walk(os.path.join(PROJECT, r)):
            for n in fn:
                p = os.path.join(dp, n)
                rel = os.path.relpath(p, PROJECT).replace("\\", "/")
                files[rel] = [os.path.getsize(p), sha(p)]
    json.dump({"project": PROJECT, "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "count": len(files), "files": files},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("files", len(files), "->", out)


def diff(a, b):
    A = json.load(open(a, encoding="utf-8"))["files"]
    B = json.load(open(b, encoding="utf-8"))["files"]
    inside = lambda p: p.startswith("Assets/GreatWave/RT48/") or p == "Assets/GreatWave/RT48.meta"
    res = {"added": sorted(set(B) - set(A)), "removed": sorted(set(A) - set(B)),
           "changed": sorted(p for p in set(A) & set(B) if A[p][1] != B[p][1])}
    out = {}
    for k, v in res.items():
        out[k + "_rt48"] = [p for p in v if inside(p)]
        out[k + "_outside"] = [p for p in v if not inside(p)]
    print(json.dumps({k: (len(v) if k.endswith("_rt48") else v) for k, v in out.items()}, ensure_ascii=False, indent=1))
    return out


if __name__ == "__main__":
    if sys.argv[1] == "take":
        take(sys.argv[2])
    else:
        diff(sys.argv[2], sys.argv[3])
