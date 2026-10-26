#!/usr/bin/env python3
"""Summarise new-emblem variants against a fixed opponent set (engine 2.0.0, 70 maps).

    emblems.py VARIANT [VARIANT ...]

Each VARIANT has tags e2_<VARIANT>_vs_<opp> for opp in OPPONENTS. A base against
itself splits every map (70 of 140), so the base rows use that for its own
pairing. Prints wins and gems against each opponent, the total of 420, and the
old-40 / new-30 map split.
"""
import json
import statistics as st
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"
OPPONENTS = ("b_tbd", "next_trial", "gs_stand_submit")
NEW = set("00anvil 00breadcrumbs 00crater 00dunes 00galaxy 00oasis 00quarry 00ribs 00the-line 00vault "
          "02arena 02crossing 02cuts 02famine 02fields 02geodes 02gift-wrapping 02guardians 02harvest "
          "02stalactites 02tangle 02the-pack 02the-pond 02treasure-box 02uncharted-lands adgato-gemcombat1 "
          "adgato-gemcombat2 adgato-gemcombat3 adgato-gemcombat4 adgato-gemcombat5".split())


def games(tag):
    flip = tag.startswith("~")  # "~tag": the same games from the other bot's side
    tag = tag.lstrip("~")
    out = []
    for f in (BENCH / tag).glob("*__*__*.json"):
        _, m, s = f.stem.split("__")
        us = "teamA" if s == "A" else "teamB"
        them = "teamB" if us == "teamA" else "teamA"
        d = json.loads(f.read_text())
        g = {k["team"]: int(k["submittedGems"]) for k in d["teams"]}
        if flip:
            us, them = them, us
        out.append((m in NEW, g[us] > g[them], g[us] - g[them]))
    return out


def row(name, tags):
    cells, allg = [], []
    for opp, tag in tags:
        if tag is None:  # a bot against itself splits every map
            cells.append(f"{opp[:10]:>10} 70/140    +0")
            allg += [(m, i % 2 == 0, 0) for i, m in enumerate([False] * 80 + [True] * 60)]
            continue
        g = games(tag)
        if len(g) < 140:
            cells.append(f"{opp[:10]:>10} {len(g):3}/140 run")
            allg = None
            continue
        allg = allg + g if allg is not None else None
        cells.append(f"{opp[:10]:>10} {sum(w for _, w, _ in g):3}/140 {st.mean(x for *_, x in g):+5.0f}")
    total = ""
    if allg is not None:
        old = [w for n, w, _ in allg if not n]
        new = [w for n, w, _ in allg if n]
        total = f"  total {sum(old) + sum(new):3}/420  old {100 * sum(old) / len(old):.0f}% new {100 * sum(new) / len(new):.0f}%"
    print(f"{name:12} " + "  ".join(cells) + total)


def main(variants):
    row("b_tbd *", [("b_tbd", None), ("next_trial", "~e2_next_trial_vs_b_tbd"), ("gs_stand_submit", "e2_b_tbd_vs_gs_stand_submit")])
    row("next_trial *", [("b_tbd", "e2_next_trial_vs_b_tbd"), ("next_trial", None), ("gs_stand_submit", "e2_next_trial_vs_gs_stand_submit")])
    for v in variants:
        row(v, [(o, f"e2_{v}_vs_{o}") for o in OPPONENTS])
    print("* base rows: its own pairing counted as 70/140 (identical bots split every map)")


if __name__ == "__main__":
    main(sys.argv[1:])
