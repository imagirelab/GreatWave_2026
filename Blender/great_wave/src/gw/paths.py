"""Project paths, params.json / thresholds.json access, write guard.

Everything is derived from the location of this file, so the project can be
moved as a whole.  There is NO fallback to another drive: a missing input
raises FileNotFoundError, and writing outside the allowed roots raises
PermissionError (user rule: never silently fall back to drive C:).

Pure python (no bpy, no numpy).
"""
import datetime as _dt
import json
import os

# ---------------------------------------------------------------- locations
_THIS = os.path.abspath(__file__)
SRC_DIR = os.path.dirname(os.path.dirname(_THIS))            # .../great_wave/src
PROJECT_ROOT = os.path.dirname(SRC_DIR)                       # .../blender/great_wave
RESEARCH_ROOT = os.path.dirname(os.path.dirname(PROJECT_ROOT))  # repository root

PARAMS_JSON = os.path.join(PROJECT_ROOT, "params.json")
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
THRESHOLDS_JSON = os.path.join(TESTS_DIR, "thresholds.json")
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")
TARGET_DIR = os.path.join(PROJECT_ROOT, "target")
CANDIDATES_DIR = os.path.join(TARGET_DIR, "candidates")
BASE_CONTOUR_JSON = os.path.join(TARGET_DIR, "base_contour.json")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
STEP1_DIR = os.path.join(RESULTS_DIR, "step1_prepare")
LOGS_DIR = os.path.join(RESULTS_DIR, "logs")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
RECORDS_DIR = os.path.join(DOCS_DIR, "records")
TOOLS_DIR = os.path.join(PROJECT_ROOT, "tools")
SPEC_MD = os.path.join(PROJECT_ROOT, "docs", "great_wave_blender_prompt.md")

TIER_NAMES = ("spec", "user_relaxed_5pct")


def norm(path):
    """Absolute, normalised path with forward slashes (stable in logs / json)."""
    return os.path.abspath(os.path.expanduser(str(path))).replace("\\", "/")


def project_path(path):
    """Resolve an output path relative to this Blender project, independent of CWD."""
    path = os.path.expanduser(str(path))
    return norm(path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path))


# ---------------------------------------------------------------- json access
_cache = {}


def _load_json(path):
    key = norm(path)
    if key not in _cache:
        if not os.path.isfile(path):
            raise FileNotFoundError("required file is missing (no fallback): %s" % path)
        with open(path, "r", encoding="utf-8") as fh:
            _cache[key] = json.load(fh)
    return _cache[key]


def clear_cache():
    """Forget cached json files (call after editing params.json in-process)."""
    _cache.clear()


def load_params(path=None):
    """Raw params.json dict: {name: {value, unit, provenance, comment, ...}}."""
    return _load_json(path or PARAMS_JSON)


def param(name, path=None):
    """Value of one params.json entry.  KeyError if it does not exist."""
    entry = load_params(path)[name]
    value = entry["value"] if isinstance(entry, dict) and "value" in entry else entry
    if name == "painting_path":
        return project_path(value)
    return value


def load_thresholds(path=None):
    """Raw tests/thresholds.json dict."""
    return _load_json(path or THRESHOLDS_JSON)


def threshold(test_id, check, tier="spec", path=None):
    """Limit value of one check, e.g. threshold('S7', 'mean_dev_pct_h', 'spec') -> 1.0."""
    if tier not in TIER_NAMES:
        raise KeyError("unknown tier %r (known: %s)" % (tier, ", ".join(TIER_NAMES)))
    return load_thresholds(path)[test_id]["checks"][check]["tiers"][tier]


_OPS = {
    "abs_le": lambda m, v: abs(m) <= v,
    "le": lambda m, v: m <= v,
    "lt": lambda m, v: m < v,
    "ge": lambda m, v: m >= v,
    "gt": lambda m, v: m > v,
    "eq": lambda m, v: m == v,
}


def check_threshold(test_id, check, measured, path=None):
    """Compare a measured value with BOTH tiers.  Never picks one silently.

    Returns a json-ready dict:
      {test, check, measured, unit, op, provenance,
       tiers: {spec: {limit, pass, margin}, user_relaxed_5pct: {...}}}
    'pass' is None for report-only checks (limit null) or when measured is None / NaN.
    'margin' = limit - |measured| (abs_le) or the signed distance to the limit in
    the passing direction; negative margin = failing by that much.
    """
    entry = load_thresholds(path)[test_id]["checks"][check]
    op = entry.get("op", "le")
    out = {
        "test": test_id,
        "check": check,
        "measured": None if measured is None else float(measured),
        "unit": entry.get("unit"),
        "op": op,
        "provenance": entry.get("provenance"),
        "tiers": {},
    }
    bad = measured is None or (isinstance(measured, float) and measured != measured)
    for tier in TIER_NAMES:
        limit = entry["tiers"].get(tier)
        res = {"limit": limit, "pass": None, "margin": None}
        if limit is not None and not bad and op in _OPS:
            m = float(measured)
            res["pass"] = bool(_OPS[op](m, limit))
            if op == "abs_le":
                res["margin"] = limit - abs(m)
            elif op in ("le", "lt"):
                res["margin"] = limit - m
            elif op in ("ge", "gt"):
                res["margin"] = m - limit
            else:
                res["margin"] = -abs(m - limit)
        out["tiers"][tier] = res
    return out


def format_check(res):
    """One ASCII line for logs: 'S1.dx_pct_h m=+0.31 [% of image height] spec<=2:PASS user_relaxed_5pct<=5:PASS'."""
    parts = ["%s.%s" % (res["test"], res["check"]),
             "m=%s" % ("n/a" if res["measured"] is None else "%+.4g" % res["measured"])]
    for tier in TIER_NAMES:
        t = res["tiers"][tier]
        verdict = "n/a" if t["pass"] is None else ("PASS" if t["pass"] else "FAIL")
        parts.append("%s(%s %s):%s" % (tier, res["op"], t["limit"], verdict))
    return " ".join(parts)


# ---------------------------------------------------------------- inputs
def require_file(path):
    """Return the normalised path or raise FileNotFoundError.  No fallback."""
    if not os.path.isfile(path):
        raise FileNotFoundError("input file not found (no fallback is attempted): %s" % path)
    return norm(path)


def painting_path():
    return require_file(param("painting_path"))


def houdini_abc_path():
    return require_file(param("houdini_abc_path"))


def blender_exe():
    return require_file(param("blender_exe"))


# ---------------------------------------------------------------- write guard
def allowed_write_roots():
    roots = [norm(PROJECT_ROOT)]
    try:
        roots += [project_path(r) for r in param("allowed_write_roots")]
    except (KeyError, FileNotFoundError):
        pass
    seen, out = set(), []
    for r in roots:
        k = r.lower().rstrip("/")
        if k not in seen:
            seen.add(k)
            out.append(r.rstrip("/"))
    return out


def is_writable_location(path):
    p = norm(path).lower()
    for root in allowed_write_roots():
        r = root.lower()
        if p == r or p.startswith(r + "/"):
            return True
    return False


def assert_writable(path):
    """Raise PermissionError if `path` is outside the allowed write roots.

    Also refuses to overwrite the read-only inputs listed in params.json.
    """
    p = norm(path)
    if not is_writable_location(p):
        raise PermissionError(
            "refusing to write outside the allowed roots (%s): %s"
            % ("; ".join(allowed_write_roots()), p))
    protected = [SPEC_MD]
    for key in ("painting_path", "houdini_abc_path", "houdini_fbx_path",
                "ref_image_tank_frames", "ref_image_houdini_viewport"):
        try:
            protected.append(param(key))
        except (KeyError, FileNotFoundError):
            pass
    if p.lower() in [norm(q).lower() for q in protected]:
        raise PermissionError("refusing to overwrite a read-only input: %s" % p)
    return p


def ensure_dir(path):
    """Create a directory (inside the allowed roots) and return its normalised path."""
    p = assert_writable(path)
    os.makedirs(p, exist_ok=True)
    return p


def ensure_parent(path):
    """Create the parent directory of a file path; returns the normalised file path."""
    p = assert_writable(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def timestamp():
    """'YYYYMMDD_HHMMSS' (local time) for results/<datetime>/ folders."""
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def results_run_dir(name=None, stamp=None):
    """results/<datetime>[_name]/ as asked for by spec section 9 (created)."""
    stamp = stamp or timestamp()
    leaf = stamp if not name else "%s_%s" % (stamp, name)
    return ensure_dir(os.path.join(RESULTS_DIR, leaf))


def step1_dir(sub=None):
    """results/step1_prepare[/sub] (created)."""
    return ensure_dir(os.path.join(STEP1_DIR, sub) if sub else STEP1_DIR)


def blend_dir():
    """Directory for large regenerable files (.blend, caches); created on demand."""
    return ensure_dir(project_path(param("blend_dir")))


def write_json(path, obj, indent=2):
    """json.dump with utf-8, stable key order as given, trailing newline."""
    p = ensure_parent(path)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=indent, ensure_ascii=False)
        fh.write("\n")
    return p


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
