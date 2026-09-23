"""Blender を画面なしで実行するスクリプト向けの補助機能。

tests/、tools/、src/<pkg>/ の各スクリプトは次のヘッダーで始める。
gw の読込には src/ を sys.path に含める必要があるため、最初の4行を置く。

    import os, sys
    _SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    from gw import bootstrap
    args = bootstrap.script_args()          # '--' 以降の全引数

環境変数の読込や変更は行わない。ユーザー指定により PYTHONPATH に触れない。
"""
import os
import sys
import time

_THIS = os.path.abspath(__file__)
SRC_DIR = os.path.dirname(os.path.dirname(_THIS))

LOG_PREFIX = "GW"


def add_src_to_path():
    """<project>/src を sys.path の先頭に置き、そのパスを返す。繰り返し呼んでも結果は同じ。"""
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)
    return SRC_DIR


def script_args(argv=None):
    """Blender のコマンド行で最初の '--' より後の引数を返す。なければ空リスト。"""
    argv = sys.argv if argv is None else list(argv)
    if "--" in argv:
        return list(argv[argv.index("--") + 1:])
    return []


def parse_args(parser, argv=None):
    """'--' より後の引数を argparse.ArgumentParser で解析する。"""
    return parser.parse_args(script_args(argv))


def in_blender():
    """Blender の Python 内で動き、bpy を読み込める場合に True を返す。"""
    try:
        import bpy  # noqa: F401
        return True
    except Exception:
        return False


def blender_version():
    """Blender のバージョン文字列を返す。Blender 外では None。例: '5.2.2 LTS'。"""
    try:
        import bpy
        return bpy.app.version_string
    except Exception:
        return None


def set_log_prefix(prefix):
    global LOG_PREFIX
    LOG_PREFIX = str(prefix)


def log(*parts, prefix=None):
    """'GW <本文>' を出力し、バッファーを流す。tools/run_blender.ps1 はこの接頭辞の行を表示する。

    非 ASCII 文字をエスケープし、文字コードが異なる端末でも例外や文字化けを避ける。
    """
    text = " ".join(str(p) for p in parts)
    text = text.encode("ascii", "backslashreplace").decode("ascii")
    pre = LOG_PREFIX if prefix is None else prefix
    for line in text.splitlines() or [""]:
        sys.stdout.write("%s %s\n" % (pre, line))
    sys.stdout.flush()


class Timer:
    """with Timer('原画読込'): ... の所要時間をログに記録する。"""

    def __init__(self, label, quiet=False):
        self.label = label
        self.quiet = quiet
        self.seconds = None

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self._t0
        if not self.quiet:
            log("[time] %s: %.3f s" % (self.label, self.seconds))
        return False


def reset_scene():
    """キューブ、照明、カメラを含まない空の初期シーンにする。Blender 専用。"""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def finish(ok, message=""):
    """最終判定をログに記録し、終了コード0または1で Blender を終了する。"""
    log("RESULT %s %s" % ("PASS" if ok else "FAIL", message))
    sys.stdout.flush()
    sys.exit(0 if ok else 1)
