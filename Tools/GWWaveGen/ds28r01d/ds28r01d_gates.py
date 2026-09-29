# -*- coding: utf-8 -*-
"""設計28修正01 試行D：関門の検査器（設計27 の ds27_gates.py、設計28 の ds28_gates_extra.py、試行A の包み ds28r01_gates.py と
独立の検査器 ds28r01_overlap.py）を、変えずに、別の K* のフォルダーで走らせる包み。

これらの検査器は K* を決まった場所（Unity/Build/ArtFirst/26修正01/kstar）と決まった SHA-256 で読む。この包みは、同じプロセスの中だけで
ds27_gates の KSTAR_DIR・KStar の既定の引数・SHA256 の表を --kstar のフォルダーの値に差し替えてから、元の main を呼ぶ（ファイルは変えない）。
K* のファイル名が kstar_a45.* でない場合（K*′ など）は、Unity/Build/Design/28R01D/_gates_kstar/<gwb の SHA-256 の頭>/ に
kstar_a45.* の名前で写してから使う。目印の列 j_corner・j_E は検査器が meta の profile.index から読む。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_gates.py --kstar <K* のフォルダー> --tool gates -- <ds28r01_gates.py の引数>
  py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_gates.py --kstar <K* のフォルダー> --tool overlap -- <ds28r01_overlap.py の引数>
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for sub in ("ds27", "ds28", "ds28r01"):
    p = os.path.abspath(os.path.join(HERE, "..", sub))
    if p not in sys.path:
        sys.path.insert(0, p)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds27_gates as DG  # noqa: E402
import ds28r01d_kstar as KS  # noqa: E402

NAMES = {"gwb": "kstar_a45.gwb", "rows": "kstar_a45_rows.npz", "meta": "kstar_a45_meta.json"}


def patch_kstar(kdir):
    f = KS.find_files(kdir)
    d = os.path.dirname(f["gwb"])
    if any(os.path.basename(f[k]) != NAMES[k] for k in NAMES):
        sha = KS.sha256_file(f["gwb"])[:12]
        d = os.path.join(KS.REPO, "Unity", "Build", "Design", "28R01D", "_gates_kstar", sha)
        os.makedirs(d, exist_ok=True)
        for k in NAMES:
            dst = os.path.join(d, NAMES[k])
            if not os.path.isfile(dst) or KS.sha256_file(dst) != KS.sha256_file(f[k]):
                shutil.copyfile(f[k], dst)
    DG.KSTAR_DIR = d
    DG.KStar.__init__.__defaults__ = (d,)
    for k, n in NAMES.items():
        DG.SHA256[n] = KS.sha256_file(os.path.join(d, n))
    return d


def main():
    argv = sys.argv[1:]
    if "--" not in argv:
        raise SystemExit("使い方：--kstar <フォルダー> --tool gates|overlap -- <元の引数>")
    k = argv.index("--")
    own, rest = argv[:k], argv[k + 1:]
    kdir = own[own.index("--kstar") + 1] if "--kstar" in own else KS.DEFAULT_KSTAR
    tool = own[own.index("--tool") + 1] if "--tool" in own else "gates"
    d = patch_kstar(kdir)
    print("[ds28r01d_gates] K* = %s（%s）" % (KS.rel(d), tool), flush=True)
    if tool == "gates":
        import ds28r01_gates as T
    elif tool == "overlap":
        import ds28r01_overlap as T
    else:
        raise SystemExit("tool は gates か overlap")
    sys.argv = [T.__file__] + rest
    T.main()


if __name__ == "__main__":
    main()
