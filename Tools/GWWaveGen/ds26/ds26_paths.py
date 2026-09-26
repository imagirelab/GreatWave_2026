# -*- coding: utf-8 -*-
"""設計26 の実験（E1〜E6・時間曲線の検査・図）と診断の入出力の場所と、入力の照合。

場所はすべてリポジトリの根からの相対で決める（このファイルは Tools/GWWaveGen/ds26/ にある）。
- 入力（Git 対象外だが本機にある）：26修正01 の K*（Unity/Build/ArtFirst/26修正01/kstar/）、
  美術優先30 の keypose（Unity/Build/ArtFirst/30/keypose/）、美術優先31 の白の時刻（Unity/Build/ArtFirst/31/white/）
- 出力：Unity/Build/Design/26/（Git 対象外。/Unity/Build/ は .gitignore にある）と、証拠の図 Docs/Evidence/Design/26/
- リポジトリ外（本機のみ）の入力：利用者の Houdini 解算（1.abc）から作った断面の npz（profiles_main_lateral.npz）。
  リポジトリには入れない。E2 の (c) と E2c だけが使う。場所は --sim <path> か環境変数 GW_DS26_SIM_NPZ で渡す。
- 論文の PDF（McAllister ほか 2019、CC BY 4.0）も本機にあるものを --pdf <path> で渡す（fig_paper_panels.py だけ）。
入力は使う前に SHA-256 を照合し、違えば止まる。
"""
import hashlib
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
KSTAR_DIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar")
KSTAR_ROWS = os.path.join(KSTAR_DIR, "kstar_a45_rows.npz")
KSTAR_META = os.path.join(KSTAR_DIR, "kstar_a45_meta.json")
KEYPOSE_DIR = os.path.join(REPO, "Unity", "Build", "ArtFirst", "30", "keypose")
OUT_ROOT = os.path.join(REPO, "Unity", "Build", "Design", "26")
OUT_FEAS = os.path.join(OUT_ROOT, "feas")
OUT_DIAG = os.path.join(OUT_ROOT, "diag")
OUT_PAPER = os.path.join(OUT_ROOT, "paper")
EVID = os.path.join(REPO, "Docs", "Evidence", "Design", "26")

# 記録した入力の SHA-256（Design_26_ja.md と run.json に同じ値）
SHA256 = {
    "kstar_a45_rows.npz": "c9eff8ddc6aa8f887c809b36431fafe00f5747084d8f689b75b9ae23029322bb",
    "kstar_a45_meta.json": "0651821b9e44f25724c8dc819d04567c97b36aec54e3c04454924949293f22fb",
    "profiles_main_lateral.npz": "17def6da6460bcac74824985cadc57ae3b3194df411cd6271d2862be995224e2",
    "paper_pdf": "05014cbfcebe4c4ee81292f3265788d214164e6c947a80497a3bb544074a337f",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fail(msg):
    sys.stderr.write("[ds26] " + msg + "\n")
    sys.exit(2)


def require(path, key=None):
    """入力があり、SHA-256 が記録と同じことを確かめてパスを返す。"""
    if not os.path.isfile(path):
        fail("入力がありません：%s" % os.path.relpath(path, REPO))
    if key is not None and sha256(path) != SHA256[key]:
        fail("入力の SHA-256 が記録と違います（%s）。記録した K* などの入力で作り直してください。" % key)
    return path


def kstar_rows():
    return require(KSTAR_ROWS, "kstar_a45_rows.npz")


def kstar_dir():
    require(KSTAR_ROWS, "kstar_a45_rows.npz")
    require(KSTAR_META, "kstar_a45_meta.json")
    return KSTAR_DIR


def outdir(path):
    os.makedirs(path, exist_ok=True)
    return path


def _opt(name, env=None):
    argv = sys.argv[1:]
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return os.environ.get(env) if env else None


def sim_npz():
    """利用者の解算から作った断面の npz（リポジトリ外・本機のみ）。無ければはっきり止まる。"""
    p = _opt("--sim", "GW_DS26_SIM_NPZ")
    if not p:
        fail("この計算には、利用者の Houdini 解算（1.abc）から作った断面の npz（profiles_main_lateral.npz、"
             "リポジトリ外・本機のみ、SHA-256 %s）が要ります。--sim <path> か環境変数 GW_DS26_SIM_NPZ で渡してください。"
             "npz が無い環境では E2 の (a)(b) だけを --skip-sim で計算できます（e2_residual.py）。"
             % SHA256["profiles_main_lateral.npz"])
    if not os.path.isfile(p):
        fail("解算の断面の npz が見つかりません（--sim / GW_DS26_SIM_NPZ の指す場所）。")
    if sha256(p) != SHA256["profiles_main_lateral.npz"]:
        fail("解算の断面の npz の SHA-256 が記録（%s）と違います。" % SHA256["profiles_main_lateral.npz"])
    return p


def paper_pdf():
    """McAllister ほか 2019 の PDF（CC BY 4.0）。本機にあるものを --pdf で渡す。"""
    p = _opt("--pdf", "GW_DS26_PAPER_PDF")
    if not p or not os.path.isfile(p):
        fail("論文の PDF（McAllister et al. 2019, J. Fluid Mech. 860, doi:10.1017/jfm.2018.886、CC BY 4.0）を --pdf <path> で渡してください。")
    if sha256(p) != SHA256["paper_pdf"]:
        fail("論文の PDF の SHA-256 が記録（%s）と違います（版が違う可能性）。" % SHA256["paper_pdf"])
    return p
