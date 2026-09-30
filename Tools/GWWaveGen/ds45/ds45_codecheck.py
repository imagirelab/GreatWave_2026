# -*- coding: utf-8 -*-
"""設計45：コードの検査。HMD Camera の局所の姿勢に手を入れていないことを、C# の書き込みの文を全部拾って確かめる（numpy なし）。

拾う書き込み（受け手の式を記録する）：
  ・代入：<受け手>.(localPosition|localRotation|position|rotation|localEulerAngles|eulerAngles|localScale|parent) (=|+=|-=|*=)
  ・呼び出し：<受け手>.(SetPositionAndRotation|SetLocalPositionAndRotation|Rotate|RotateAround|Translate|LookAt|SetParent)(
判定（実行時の部品 Design45/Scripts）：受け手が HMD Camera（hmdCamera）・Camera Offset（cameraOffset）・Camera.main・camera のどれでもない。
  書いてよい受け手は、この部品自身の transform（RiderComfortRoot）と xrOrigin（座席リセットの時だけ）。
  hmdCamera が出てくる行は全部、読むだけ（右辺・引数）であることも一覧にする。
検査の道具（Design45/Editor）は、組み立ての時の書き込み（新しく作った物の親・局所の位置）を別に一覧にする（判定には入れない。HMD Camera の局所の姿勢は書かない）。
"""
import json
import os
import re
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
RUNTIME = os.path.join(REPO, "Unity/Assets/GreatWave/Design45/Scripts")
EDITOR = os.path.join(REPO, "Unity/Assets/GreatWave/Design45/Editor")

PROP = r"(localPosition|localRotation|position|rotation|localEulerAngles|eulerAngles|localScale|parent)"
ASSIGN = re.compile(r"([A-Za-z_][\w\.\[\]\(\)]*?)\s*\.\s*" + PROP + r"\s*(=|\+=|-=|\*=)(?!=)")
CALL = re.compile(r"([A-Za-z_][\w\.\[\]\(\)]*?)\s*\.\s*(SetPositionAndRotation|SetLocalPositionAndRotation|Rotate|RotateAround|Translate|LookAt|SetParent)\s*\(")
FORBIDDEN = ("hmdCamera", "cameraOffset", "Camera.main", "camera", "cam")
ALLOWED_RUNTIME = ("transform", "xrOrigin")


def strip_comment(line):
    i = line.find("//")
    return line if i < 0 else line[:i]


def scan(folder):
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".cs"):
            continue
        path = os.path.join(folder, name)
        with open(path, encoding="utf-8-sig") as f:
            lines = f.read().split("\n")
        for no, raw in enumerate(lines, 1):
            line = strip_comment(raw)
            for m in ASSIGN.finditer(line):
                out.append({"file": name, "line": no, "kind": "assign", "receiver": m.group(1), "member": m.group(2), "code": raw.strip()})
            for m in CALL.finditer(line):
                out.append({"file": name, "line": no, "kind": "call", "receiver": m.group(1), "member": m.group(2), "code": raw.strip()})
    return out


def hmd_mentions(folder):
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".cs"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8-sig") as f:
            for no, raw in enumerate(f.read().split("\n"), 1):
                line = strip_comment(raw)
                if re.search(r"\bhmdCamera\b", line):
                    out.append({"file": name, "line": no, "code": raw.strip()})
    return out


def is_forbidden(recv):
    r = recv.replace(" ", "")
    last = r.split(".")[-1]
    return any(r == f or last == f or r.endswith("." + f) or r.startswith(f + ".") for f in FORBIDDEN)


def main():
    rt = scan(RUNTIME)
    ed = scan(EDITOR)
    bad = [w for w in rt if is_forbidden(w["receiver"])]
    other = [w for w in rt if w["receiver"] not in ALLOWED_RUNTIME]
    mentions = hmd_mentions(RUNTIME)
    # hmdCamera の行が読みだけか：その行に hmdCamera への書き込みが無い
    mention_writes = [m for m in mentions if any(w["file"] == m["file"] and w["line"] == m["line"] and is_forbidden(w["receiver"]) for w in rt)]
    ed_cam = [w for w in ed if is_forbidden(w["receiver"])]
    # 検査の道具で HMD Camera の局所の姿勢（localPosition・localRotation）を書く文（組み立ての SetParent は別）
    ed_cam_pose = [w for w in ed_cam if w["member"] in ("localPosition", "localRotation", "position", "rotation", "SetPositionAndRotation", "SetLocalPositionAndRotation", "Rotate", "RotateAround", "Translate", "LookAt", "localEulerAngles", "eulerAngles")]
    res = {
        "schema": "GreatWave.DS45.codecheck/1",
        "runtimeFolder": "Unity/Assets/GreatWave/Design45/Scripts",
        "runtimeWrites": rt,
        "runtimeWritesToHmdOrOffset": bad,
        "runtimeWritesOtherThanOwnTransformOrXrOrigin": other,
        "hmdCameraMentions": mentions,
        "hmdCameraMentionsThatWrite": mention_writes,
        "editorWrites": ed,
        "editorWritesOnCameraNames": ed_cam,
        "editorWritesHmdPose": ed_cam_pose,
        "passed": len(bad) == 0 and len(other) == 0 and len(mention_writes) == 0 and len(ed_cam_pose) == 0,
        "noteJa": "受け手の式を正規表現で拾った静的な検査。実行時の検査（Unity で HMD Camera の局所の姿勢が一度も変わらない）は ds45_unity_report.json の hmdLocalPosMaxAbsChange・hmdLocalRotMaxAngleDeg。",
    }
    return res


if __name__ == "__main__":
    r = main()
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "Unity/Build/Design/45/comfort/codecheck.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    print("DS45_CODECHECK passed=%s runtimeWrites=%d bad=%d other=%d hmdMentions=%d editorCamWrites=%d editorHmdPose=%d" % (
        r["passed"], len(r["runtimeWrites"]), len(r["runtimeWritesToHmdOrOffset"]), len(r["runtimeWritesOtherThanOwnTransformOrXrOrigin"]),
        len(r["hmdCameraMentions"]), len(r["editorWritesOnCameraNames"]), len(r["editorWritesHmdPose"])))
