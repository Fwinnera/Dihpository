#!/usr/bin/env python3
"""Apply the acceptance test to candidates paired against a baseline.

Pass = at least 90% one-sided confidence that gems submitted improved (paired
z >= 1.28) and a win-rate change that is not negative.

    verdict.py BASE TAG [TAG ...]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main(base, tags):
    out = subprocess.run([sys.executable, "-I", str(HERE / "paired.py"), base, *tags],
                         capture_output=True, text=True).stdout
    blocks = re.split(r"\n(?=\S+ against the baseline)", out)
    print("%-24s%9s%7s%10s%9s%9s  %s" % ("candidate", "gems", "z", "win rate", "deaths", "games", "verdict"))
    rows = []
    for b in blocks:
        m = re.match(r"(\S+) against the baseline: (\d+) paired", b)
        if not m:
            continue
        get = lambda label: re.search(rf"{label}\s+[-\d.]+\s+[-\d.]+\s+([-+\d.]+)\s+([\d.]+)\s+([-+\d.]+)", b)
        g, w, d = get("gems submitted"), get("win rate %"), get(r"deaths")
        gz, wd = float(g.group(3)), float(w.group(1))
        ok = gz >= 1.28 and wd >= 0
        rows.append((gz, m.group(1)))
        print("%-24s%+9.1f%+7.1f%+10.1f%+9.2f%9s  %s" % (m.group(1), float(g.group(1)), gz, wd,
              float(d.group(1)), m.group(2), "PASS" if ok else "fail"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
