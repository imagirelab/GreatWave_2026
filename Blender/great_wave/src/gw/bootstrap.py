"""Helpers for scripts that are run headless by Blender.

Header every script in tests/, tools/ or src/<pkg>/ should start with
(the import of gw itself needs src/ on sys.path, hence the 4 plain lines):

    import os, sys
    _SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)
    from gw import bootstrap
    args = bootstrap.script_args()          # everything after '--'

No environment variable is read or modified (user rule: do not touch PYTHONPATH).
"""
import os
import sys
import time

_THIS = os.path.abspath(__file__)
SRC_DIR = os.path.dirname(os.path.dirname(_THIS))

LOG_PREFIX = "GW"


def add_src_to_path():
    """Put <project>/src at the front of sys.path (idempotent). Returns the path."""
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)
    return SRC_DIR


def script_args(argv=None):
    """Arguments after the first '--' of the Blender command line ([] if none)."""
    argv = sys.argv if argv is None else list(argv)
    if "--" in argv:
        return list(argv[argv.index("--") + 1:])
    return []


def parse_args(parser, argv=None):
    """Run an argparse.ArgumentParser on the arguments after '--'."""
    return parser.parse_args(script_args(argv))


def in_blender():
    """True when running inside Blender's python (bpy importable)."""
    try:
        import bpy  # noqa: F401
        return True
    except Exception:
        return False


def blender_version():
    """e.g. '5.2.2 LTS' or None outside Blender."""
    try:
        import bpy
        return bpy.app.version_string
    except Exception:
        return None


def set_log_prefix(prefix):
    global LOG_PREFIX
    LOG_PREFIX = str(prefix)


def log(*parts, prefix=None):
    """print('GW <text>') and flush; tools/run_blender.ps1 shows only such lines.

    Non-ASCII characters are replaced so that a cp936/cp1252 console never raises.
    """
    text = " ".join(str(p) for p in parts)
    text = text.encode("ascii", "backslashreplace").decode("ascii")
    pre = LOG_PREFIX if prefix is None else prefix
    for line in text.splitlines() or [""]:
        sys.stdout.write("%s %s\n" % (pre, line))
    sys.stdout.flush()


class Timer:
    """with Timer('load painting'): ...   -> logs 'GW [time] load painting: 0.412 s'."""

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
    """Empty factory scene (no cube / light / camera).  Blender only."""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def finish(ok, message=""):
    """Log a final verdict line and leave Blender with exit code 0 / 1."""
    log("RESULT %s %s" % ("PASS" if ok else "FAIL", message))
    sys.stdout.flush()
    sys.exit(0 if ok else 1)
