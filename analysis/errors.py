#!/usr/bin/env python3
"""Count the turns a bot loses to exceptions, by where in its own code they fire.

`main.py` catches any exception other than Replan, prints
`ERROR <type>: <message> @ <file:line> > ...` and ends the turn, so every line is
a champion-turn lost. The bot's stdout sits inside each replay bundle,
NUL-padded. Bench bundles are named `<opponent>__<map>__<A|B>`, the side being
the bot under test.

    errors.py TAG [TAG ...]          # folders under ws/bench
"""
from __future__ import annotations

import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"
LINE = re.compile(r"ERROR (\w+): (.*?) @ (.*)")


def census(tag: str):
    games, lines, where, kinds, per_game = 0, 0, Counter(), Counter(), []
    for bundle in sorted((BENCH / tag).glob("*.repl26a")):
        side = bundle.stem.rsplit("__", 1)[-1].lower()
        try:
            raw = zipfile.ZipFile(bundle).read(f"team-{side}.stdout")
        except (KeyError, zipfile.BadZipFile):
            continue
        games += 1
        n = 0
        for line in raw.decode("utf8", "replace").replace("\x00", "").splitlines():
            m = LINE.search(line)
            if not m:
                continue
            n += 1
            kind, message, trace = m.groups()
            frames = [f for f in trace.split(" > ") if f]
            ours = [f for f in frames if not f.split(":")[0].endswith("__init__.py")]
            site = (ours[-1] if ours else frames[-1]).split("/")[-1]
            where[(kind, message[:48], site)] += 1
            kinds[kind] += 1
        lines += n
        per_game.append(n)
    return games, lines, where, kinds, per_game


def main(tags: list[str]) -> int:
    for tag in tags:
        games, lines, where, kinds, per_game = census(tag)
        if not games:
            print(f"{tag}: no bundles")
            continue
        hit = sum(1 for n in per_game if n)
        print(f"=== {tag}: {games} games, {lines} lost champion-turns "
              f"({lines / games:.1f} a game; {hit} games with any) ===")
        for (kind, message, site), n in where.most_common(12):
            print(f"  {n:6d}  {n / games:6.2f}/game  {site:<22} {kind}: {message}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["wide_shopbase"]))
