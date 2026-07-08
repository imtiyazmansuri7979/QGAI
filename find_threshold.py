#!/usr/bin/env python3
import os, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."

KEYWORDS = [
    "threshold", "runner", "runner_target", "target", "tpcap",
    "tp_cap", "tp_target", "pred_threshold", "signal_threshold",
    "confidence", "min_conf", "cutoff", "score_threshold"
]

EXTS = {".py", ".js", ".ts", ".json", ".ini", ".cfg", ".yaml", ".yml", ".toml", ".mq4", ".mq5", ".txt", ".env"}

hits = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("__pycache__", "node_modules", "logs", ".git")]
    for fname in filenames:
        ext = os.path.splitext(fname)[1].lower()
        if ext not in EXTS:
            continue
        fpath = os.path.join(dirpath, fname)
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except:
            continue
        for i, line in enumerate(lines, 1):
            ll = line.lower()
            for kw in KEYWORDS:
                if kw in ll:
                    hits.append((fpath, i, kw, line.rstrip()))
                    break

if not hits:
    print("No matches found. Check your folder path.")
else:
    print(f"Found {len(hits)} match(es):\n")
    last_file = None
    for fpath, lineno, kw, line in hits:
        if fpath != last_file:
            print(f"\n📄  {fpath}")
            last_file = fpath
        print(f"   Line {lineno:4d} [{kw}]  →  {line.strip()}")
