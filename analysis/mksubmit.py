#!/usr/bin/env python3
"""Build an untagged submission folder and zip from a mkfixes.py recipe.

    mksubmit.py v98 bruiser+heal60+fieldresume+cheapretry+party

builds `ws/bots/v98_submit` from mkfixes.py's base with those changes (no
re-roll: the re-roll is decision-neutral and only the test arms need it),
removes the BOTTAG line, checks that `main.py` is byte-identical to the live
bot's (`ws/bots/v97_submit` unless --live says otherwise), bundles
`v98_submit.zip` with `cambc bundle`, and prints each file's sha256 and how the
folder differs from the live one. It uploads nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mkfixes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "ws"
CAMBC = Path.home() / "Library" / "Python" / "3.9" / "bin" / "cambc"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("recipe", help="changes joined by +, as for mkfixes.py")
    ap.add_argument("--live", default="v97_submit")
    a = ap.parse_args()
    changes = a.recipe.split("+")
    if any(c.startswith("reroll") for c in changes):
        sys.exit("leave the re-roll out of a submission")
    name = f"{a.version}_submit"
    mkfixes.build(name, changes)
    src = WS / "bots" / name / "src"
    main_py = src / "main.py"
    text, n = re.subn(r'    print\("BOTTAG [^"]+", flush=True\)\n\n\n', "", main_py.read_text(), count=1)
    if n != 1:
        sys.exit("BOTTAG line not found in the expected form")
    main_py.write_text(text)
    live = WS / "bots" / a.live / "src"
    if main_py.read_bytes() != (live / "main.py").read_bytes():
        sys.exit(f"main.py differs from {a.live}'s")
    print(f"  main.py identical to {a.live}'s; no BOTTAG")
    for p in sorted(src.glob("*.py")):
        other = live / p.name
        state = "same" if other.exists() and other.read_bytes() == p.read_bytes() else "changed"
        print(f"  {hashlib.sha256(p.read_bytes()).hexdigest()[:16]}  {p.name:14} {state}")
    out = ROOT / f"{name}.zip"
    cambc = shutil.which("cambc") or str(CAMBC)
    subprocess.run([cambc, "bundle", str(WS / "bots" / name), "--output", str(out)], check=True, cwd=WS)
    print(f"  {out.name}: {out.stat().st_size} bytes, sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
