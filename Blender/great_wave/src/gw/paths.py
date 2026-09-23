"""プロジェクト内のパス、params.json / thresholds.json の読込、書込先の制限。

すべてのパスをこのファイルの位置から求めるため、プロジェクト全体を移動できる。
別のドライブへの代替処理はない。入力がなければ FileNotFoundError、
許可された書込先の外では PermissionError を発生させる。
ユーザー指定により、C ドライブへ黙って切り替えない。

Python 標準機能のみを使い、bpy と numpy は使わない。
"""
import datetime as _dt
import json
import os

# ---------------------------------------------------------------- パス
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
    """区切りをスラッシュに統一した絶対パスを返す。ログと JSON で安定して表記できる。"""
    return os.path.abspath(os.path.expanduser(str(path))).replace("\\", "/")


def project_path(path):
    """出力先を Blender プロジェクトを基準に解決する。現在の作業ディレクトリに依存しない。"""
    path = os.path.expanduser(str(path))
    return norm(path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path))


# ---------------------------------------------------------------- JSON の読込
_cache = {}


def _load_json(path):
    key = norm(path)
    if key not in _cache:
        if not os.path.isfile(path):
            raise FileNotFoundError("必要なファイルがありません。別の場所への代替読込は行いません: %s" % path)
        with open(path, "r", encoding="utf-8") as fh:
            _cache[key] = json.load(fh)
    return _cache[key]


def clear_cache():
    """読込済み JSON のキャッシュを消す。同じ処理内で params.json を編集した後に呼ぶ。"""
    _cache.clear()


def load_params(path=None):
    """params.json の元の辞書を返す。形式: {name: {value, unit, provenance, comment, ...}}。"""
    return _load_json(path or PARAMS_JSON)


def param(name, path=None):
    """params.json の1項目の値を返す。項目がなければ KeyError。"""
    entry = load_params(path)[name]
    value = entry["value"] if isinstance(entry, dict) and "value" in entry else entry
    if name == "painting_path":
        return project_path(value)
    return value


def load_thresholds(path=None):
    """tests/thresholds.json の元の辞書を返す。"""
    return _load_json(path or THRESHOLDS_JSON)


def threshold(test_id, check, tier="spec", path=None):
    """1つの検査の限界値を返す。例: threshold('S7', 'mean_dev_pct_h', 'spec') -> 1.0。"""
    if tier not in TIER_NAMES:
        raise KeyError("不明な判定基準 %r（既知: %s）" % (tier, ", ".join(TIER_NAMES)))
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
    """測定値を両方の判定基準と比較する。片方だけを黙って選ばない。

    JSON に保存できる次の辞書を返す:
      {test, check, measured, unit, op, provenance,
       tiers: {spec: {limit, pass, margin}, user_relaxed_5pct: {...}}}
    報告のみの検査（限界値が null）、または測定値が None / NaN の場合、'pass' は None。
    'margin' は abs_le では限界値 - |測定値|、それ以外では合格方向への符号付き距離。
    負の値はその量だけ不合格であることを表す。
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
    """検査結果をログ向けの ASCII 1行に整形する。例: 'S1.dx_pct_h m=+0.31 spec(le 2):PASS'。"""
    parts = ["%s.%s" % (res["test"], res["check"]),
             "m=%s" % ("n/a" if res["measured"] is None else "%+.4g" % res["measured"])]
    for tier in TIER_NAMES:
        t = res["tiers"][tier]
        verdict = "n/a" if t["pass"] is None else ("PASS" if t["pass"] else "FAIL")
        parts.append("%s(%s %s):%s" % (tier, res["op"], t["limit"], verdict))
    return " ".join(parts)


# ---------------------------------------------------------------- 入力
def require_file(path):
    """正規化したパスを返す。ファイルがなければ FileNotFoundError。代替読込はしない。"""
    if not os.path.isfile(path):
        raise FileNotFoundError("入力ファイルがありません。別の場所への代替読込は行いません: %s" % path)
    return norm(path)


def painting_path():
    return require_file(param("painting_path"))


def houdini_abc_path():
    return require_file(param("houdini_abc_path"))


def blender_exe():
    return require_file(param("blender_exe"))


# ---------------------------------------------------------------- 書込先の制限
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
    """`path` が許可された書込先の外なら PermissionError を発生させる。

    params.json に列挙した読込専用の入力も上書きしない。
    """
    p = norm(path)
    if not is_writable_location(p):
        raise PermissionError(
            "許可された書込先の外には書き込めません（%s）: %s"
            % ("; ".join(allowed_write_roots()), p))
    protected = [SPEC_MD]
    for key in ("painting_path", "houdini_abc_path", "houdini_fbx_path",
                "ref_image_tank_frames", "ref_image_houdini_viewport"):
        try:
            protected.append(param(key))
        except (KeyError, FileNotFoundError):
            pass
    if p.lower() in [norm(q).lower() for q in protected]:
        raise PermissionError("読込専用の入力は上書きできません: %s" % p)
    return p


def ensure_dir(path):
    """許可された場所にディレクトリを作り、正規化したパスを返す。"""
    p = assert_writable(path)
    os.makedirs(p, exist_ok=True)
    return p


def ensure_parent(path):
    """ファイルの親ディレクトリを作り、正規化したファイルのパスを返す。"""
    p = assert_writable(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def timestamp():
    """results/<日時>/ 用の現地時刻を 'YYYYMMDD_HHMMSS' 形式で返す。"""
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def results_run_dir(name=None, stamp=None):
    """仕様9に従う results/<日時>[_名前]/ を作成して返す。"""
    stamp = stamp or timestamp()
    leaf = stamp if not name else "%s_%s" % (stamp, name)
    return ensure_dir(os.path.join(RESULTS_DIR, leaf))


def step1_dir(sub=None):
    """results/step1_prepare[/sub] を作成して返す。"""
    return ensure_dir(os.path.join(STEP1_DIR, sub) if sub else STEP1_DIR)


def blend_dir():
    """再生成できる大きなファイル（.blend、キャッシュ）用のディレクトリを必要時に作る。"""
    return ensure_dir(project_path(param("blend_dir")))


def write_json(path, obj, indent=2):
    """UTF-8 の JSON を指定されたキー順で書き出し、末尾に改行を入れる。"""
    p = ensure_parent(path)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=indent, ensure_ascii=False)
        fh.write("\n")
    return p


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
