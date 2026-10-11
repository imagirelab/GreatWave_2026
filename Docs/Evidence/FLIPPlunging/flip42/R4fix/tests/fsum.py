import sys, json
for line in open(sys.argv[1], encoding="utf8", errors="ignore"):
    line = line.strip()
    if line.startswith("frame"):
        print(line[:120]); continue
    parts = line.split(" ", 1)
    if len(parts) == 2 and parts[1].startswith("{") and not line.startswith("RUN"):
        d = json.loads(parts[1])
        print("  ", parts[0], {k: (v.get("res"), v.get("bmin", ["?"])[0], v.get("max")) for k, v in d.items() if isinstance(v, dict)})
