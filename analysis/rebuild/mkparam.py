#!/usr/bin/env python3
"""Set config.h constants on a bot copy: mkparam.py BOTDIR NAME=VALUE [NAME=VALUE ...]

Each NAME must appear exactly once as `inline constexpr <type> NAME = <value>;`.
"""
import re
import sys
from pathlib import Path

f = Path(sys.argv[1]) / "src" / "config.h"
text = f.read_text()
for arg in sys.argv[2:]:
    name, value = arg.split("=", 1)
    pattern = re.compile(rf"(inline constexpr [\w:<>]+ {re.escape(name)} = )([^;]+);")
    hits = pattern.findall(text)
    if len(hits) != 1:
        sys.exit(f"{name}: expected one definition, found {len(hits)}")
    text = pattern.sub(lambda m: f"{m.group(1)}{value};", text)
f.write_text(text)
print("set", f, sys.argv[2:])
