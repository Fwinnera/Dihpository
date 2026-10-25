#!/usr/bin/env python3
"""Write the per map-side arm choice into a copy of omni.

    mktable.py PREFIX NAME [--seeds 1,2,3,4] [--prior K] [--top N] [--reroll R]

Copies ws/bots/omni/src to ws/bots/NAME/src, fills policy_table.h's arm_a/arm_b
from pick_arms.choose on the screen PREFIX, sets REROLL (default 0: the
submitted build), and tags the build NAME.
"""
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_arms  # noqa: E402

BOTS = Path(__file__).resolve().parent.parent / "ws/bots"


def main(argv):
    prefix, name = argv[0], argv[1]
    seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")] if "--seeds" in argv else [1, 2, 3, 4]
    prior = float(argv[argv.index("--prior") + 1]) if "--prior" in argv else 2.0
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else None
    reroll = int(argv[argv.index("--reroll") + 1]) if "--reroll" in argv else 0
    data = pick_arms.load(prefix)
    complete = sorted(a for a in data if all(s in data[a] for s in seeds))
    rates = {a: sum(sum(data[a][s].values()) for s in seeds) for a in complete}
    arms = sorted(complete, key=lambda a: -rates[a])[:top] if top else complete
    pick, _ = pick_arms.choose(data, seeds, prior, arms)
    if "--stage2" in argv:
        # Contested map-sides: most wins over stage one plus the second stage's seeds
        # (ties: better overall record). Clear map-sides: the best overall arm among
        # those that won every stage-one seed.
        extra = {}
        for line in Path(argv[argv.index("--stage2") + 1], "results.txt").read_text().split("\n"):
            if line.strip():
                a, s, m, side, w = line.split()
                extra.setdefault((m, side), {}).setdefault(int(a), []).append(int(w))
        for k in pick:
            stage1 = {a: sum(data[a][s][k] for s in seeds) for a in arms}
            if k in extra:
                pick[k] = max(extra[k], key=lambda a: (stage1[a] + sum(extra[k][a]), rates[a]))
            else:
                perfect = [a for a in arms if stage1[a] == len(seeds)]
                if perfect:
                    pick[k] = max(perfect, key=lambda a: rates[a])
    if "--picks" in argv:
        # Explicit "map side arm" lines (pick_robust.py --write).
        for line in Path(argv[argv.index("--picks") + 1]).read_text().splitlines():
            if line.strip():
                m, side, a = line.split()
                pick[(m, side)] = int(a)
    out = BOTS / name
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(BOTS / "omni" / "src", out / "src")
    table = out / "src" / "policy_table.h"
    t = table.read_text()
    filled = 0

    def row(m):
        nonlocal filled
        w, h, g, gems, mapname = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        a, b = pick.get((mapname, "A"), 0), pick.get((mapname, "B"), 0)
        filled += 1
        return f"        {{{w}, {h}, {g}, {gems}, {a}, {b}}},  // {mapname}"

    t = re.sub(r"        \{(\d+), (\d+), (\d+), (\d+), \d+, \d+\},  // (\S+)", row, t)
    t = t.replace("inline constexpr int REROLL = 0;", f"inline constexpr int REROLL = {reroll};")
    table.write_text(t)
    main_cpp = out / "src" / "main.cpp"
    main_cpp.write_text(main_cpp.read_text().replace('"BOTTAG omni"', f'"BOTTAG {name}"'))
    print(f"{name}: {filled} map rows from {prefix} seeds {seeds}, prior {prior}, {len(arms)} arms, reroll {reroll}")


if __name__ == "__main__":
    main(sys.argv[1:])
