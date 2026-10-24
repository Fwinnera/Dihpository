#!/usr/bin/env python3
"""Build apex variants: a copy of ws/bots/apex/src with switches in config.h changed.

    mkapex.py NAME [FLAG=value ...]

FLAG is any `inline constexpr` name in apex's config.h (DRAFT_TOP1, PRISM_CAP,
HEAL_RECALL, ...). The variant prints BOTTAG NAME. An ablation therefore differs
from apex only in the values it names, so its result is attributable to them.
"""
import re
import shutil
import sys
from pathlib import Path

BOTS = Path(__file__).resolve().parent.parent / "ws" / "bots"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    name, pairs = sys.argv[1], sys.argv[2:]
    src, out = BOTS / "apex" / "src", BOTS / name
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out / "src")
    cfg = out / "src" / "config.h"
    text = cfg.read_text()
    for pair in pairs:
        flag, value = pair.split("=", 1)
        pattern = re.compile(rf"(inline constexpr [\w:]+ {re.escape(flag)} = )[^;]+;")
        if len(pattern.findall(text)) != 1:
            sys.exit(f"config.h: {flag} not found exactly once")
        text = pattern.sub(lambda m: m.group(1) + value + ";", text)
    cfg.write_text(text)
    main_cpp = out / "src" / "main.cpp"
    body = main_cpp.read_text()
    old = '#define BOT_TAG "apex"'
    if body.count(old) != 1:
        sys.exit("main.cpp: BOT_TAG default not found")
    main_cpp.write_text(body.replace(old, f'#define BOT_TAG "{name}"'))
    print(f"built {out} with {' '.join(pairs) or 'no changes'}")


if __name__ == "__main__":
    main()
