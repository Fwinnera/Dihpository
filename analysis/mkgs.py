#!/usr/bin/env python3
"""Variants of a C++ gs-line bot: copy BASE's src, apply exact text replacements.

    mkgs.py BASE NAME 'old=>new' ['old=>new' ...]

Each replacement must match exactly once (FILE:old=>new to pick the file;
default config.h). The variant prints BOTTAG NAME.
"""
import re
import shutil
import sys
from pathlib import Path

BOTS = Path(__file__).resolve().parent.parent / "ws" / "bots"


def main() -> None:
    base, name, edits = sys.argv[1], sys.argv[2], sys.argv[3:]
    out = BOTS / name
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(BOTS / base / "src", out / "src")
    for e in edits:
        fname, rest = ("config.h", e) if ":" not in e.split("=>")[0] else e.split(":", 1)
        old, new = rest.split("=>", 1)
        p = out / "src" / fname
        t = p.read_text()
        if t.count(old) != 1:
            sys.exit(f"{fname}: {old!r} found {t.count(old)} times")
        p.write_text(t.replace(old, new))
    m = out / "src" / "main.cpp"
    t, n = re.subn(r'std::cout << "BOTTAG [^"]*" << std::endl;', f'std::cout << "BOTTAG {name}" << std::endl;', m.read_text(), count=1)
    if n != 1:
        sys.exit("BOTTAG line not found")
    m.write_text(t)
    print(f"built {name} from {base}: {len(edits)} edit(s)")


if __name__ == "__main__":
    main()
