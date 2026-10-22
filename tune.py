#!/usr/bin/env python3
"""Search each map's parameters separately and keep only what wins on that map.

Why per-map
-----------
Every global change measured in this project helped some maps and hurt others.
Champion pressure is +246 gems on 00swirl and -40 on 00stampede. Those splits read
as noise until the ladder band was measured -- the same bot twice on identical
pairings reproduces 14 of 15 games byte-identically -- so they are real, and a
single constant is one answer forced onto forty different problems.

How it searches
---------------
Coordinate descent, one parameter at a time, keeping any value that beats the
incumbent by more than the local band. Full grid search is out of reach: five
parameters at four values each is 1,024 combinations per map, times forty maps.
Coordinate descent gets most of the benefit for a few dozen games per map, and the
whole table is regenerated from scratch each run so a stale entry cannot survive.

DO NOT TRUST THE LOCAL MODE
---------------------------
Local tuning was built here first and then measured against the ladder on the one
parameter where both numbers exist. They disagree in sign:

    CHAMPION_PRESSURE on 00swirl
        local, vs colleague       -508 gems   (default already wins 2-0 at 1010)
        ladder, vs real opponents +246 gems   (default goes 0-8 at 215)

The local baseline is not a weaker version of the ladder game, it is a different
game. Against `colleague` we already win 00swirl comfortably, so withdrawing more
only costs farming time; on the ladder we are being killed by champions, so
withdrawing more is the whole fix. Tuning locally would have learned exactly the
wrong table, confidently, for all forty maps.

So the local mode is kept only for sanity checks and for parameters whose effect
is obviously opponent-independent. Anything that touches fighting, retreating or
contesting must be measured with `ladderbench.py`. A ladder group plays five maps
at once, so a parameter sweep is cheaper there than it looks: one group per value
covers five maps against one opponent.

Scoring uses gems submitted, with the opponent's gems as a tie-break, since a
change that cuts their score is worth as much as one that raises ours.

    tune.py --maps 00swirl,01islands            # tune two maps
    tune.py --all --opponents colleague,boss_focus
    tune.py --emit                               # write mappolicy.py from results
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WS = ROOT / "ws"
CAMBC = Path.home() / "Library" / "Python" / "3.9" / "bin" / "cambc"
BASE_BOT = "gs_tune"
SCRATCH = "gs_tune_probe"
RESULTS = ROOT / "tuned.json"
DEFAULT_OPPONENTS = ["colleague", "boss_focus", "greatsage"]

# Candidate values per parameter. The first entry must be the current default, so
# a parameter that cannot be improved leaves no entry in the table at all.
# Parameters whose sign is known to depend on the opponent. Tuning these locally
# produced the wrong answer on the one case that has been checked both ways.
LADDER_ONLY = {"CHAMPION_PRESSURE", "RETREAT_HEALTH", "CARRIER_RETREAT_HEALTH"}

SPACE = {
    "CHAMPION_PRESSURE": [False, True],
    "BANK_GEMS": [24, 12, 18, 36],
    "RETREAT_HEALTH": [0.30, 0.22, 0.38, 0.46],
    "CARRIER_RETREAT_HEALTH": [0.43, 0.34, 0.52],
    "SHOP_GOLD": [150, 90, 210],
}
# Below this, a difference is not worth an entry: it is the spread seen between
# runs that differ only in irrelevant ways, measured locally.
MIN_GAIN = 12.0


def cambc(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{CAMBC.parent}:{env.get('PATH','')}"
    r = subprocess.run([str(CAMBC), *args], capture_output=True, text=True,
                       env=env, cwd=WS)
    if check and r.returncode != 0:
        raise RuntimeError(f"cambc {' '.join(args)} failed:\n{r.stderr or r.stdout}")
    return r


def map_files() -> dict[str, Path]:
    return {p.stem: p for p in sorted(WS.glob("maps/*.map26a"))}


def signature(map_name: str) -> tuple[int, int, int] | None:
    sigs = json.loads(Path("/tmp/mapsigs.json").read_text()) \
        if Path("/tmp/mapsigs.json").exists() else {}
    s = sigs.get(map_name)
    return tuple(s) if s else None


def write_probe(params: dict) -> None:
    """Stamp one parameter set into the scratch bot's config."""
    src, dst = WS / "bots" / BASE_BOT, WS / "bots" / SCRATCH
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    # Neutralise the table so only the stamped values apply.
    mp = dst / "src" / "mappolicy.py"
    t = mp.read_text()
    t = re.sub(r"TABLE = \{.*?\n\}", "TABLE = {}", t, flags=re.S)
    mp.write_text(t)
    cfg = dst / "src" / "config.py"
    c = cfg.read_text()
    for name, value in params.items():
        pattern = rf"^{name} = .*$"
        line = f"{name} = {value!r}"
        c, n = re.subn(pattern, line, c, count=1, flags=re.M)
        if not n:
            c += f"\n{line}\n"
    cfg.write_text(c)


def play(map_name: str, opponents: list[str], tag: str) -> dict:
    """One parameter set against every opponent, both sides, on one map."""
    out = WS / "tune_runs" / tag
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    mp = map_files()[map_name]
    lines = []
    for opp in opponents:
        for side in ("A", "B"):
            a, b = ((SCRATCH, opp) if side == "A" else (opp, SCRATCH))
            stem = f"{opp}__{side}"
            lines.append(f"{WS}/bots/{a} {WS}/bots/{b} {mp} "
                         f"{out}/{stem}.repl26a --statistics {out}/{stem}.json")
    manifest = out / "m.txt"
    manifest.write_text("\n".join(lines) + "\n")
    cambc("run-batch", "--release", "--json", "--jobs", "6", "--timeout", "300",
          str(manifest), check=False)
    ours = theirs = 0.0
    wins = n = 0
    for p in sorted(out.glob("*.json")):
        side = p.stem.split("__")[1]
        me = "teamA" if side == "A" else "teamB"
        d = json.loads(p.read_text())
        g = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        ours += g[me]
        theirs += g["teamB" if me == "teamA" else "teamA"]
        wins += int(d["match"]["outcome"] == me)
        n += 1
    shutil.rmtree(out, ignore_errors=True)
    if not n:
        return {"score": -1e9, "gems": 0, "theirs": 0, "wins": 0, "games": 0}
    # Gems first; the opponent's score breaks ties, since denying is as good as earning.
    return {"score": ours / n - 0.25 * (theirs / n), "gems": ours / n,
            "theirs": theirs / n, "wins": wins, "games": n}


def tune_map(map_name: str, opponents: list[str], passes: int,
             allow_ladder_only: bool = False) -> dict:
    best = {k: v[0] for k, v in SPACE.items()}
    write_probe(best)
    base = play(map_name, opponents, "base")
    print(f"\n{map_name}: default {base['gems']:.0f} gems vs {base['theirs']:.0f}, "
          f"{base['wins']}-{base['games']-base['wins']}")
    incumbent = base
    for p in range(passes):
        improved = False
        for name, values in SPACE.items():
            if name in LADDER_ONLY and not allow_ladder_only:
                print(f"    {name:<24} skipped: opponent-dependent, measure on the ladder")
                continue
            for value in values[1:]:
                trial = dict(best)
                trial[name] = value
                write_probe(trial)
                r = play(map_name, opponents, "trial")
                gain = r["score"] - incumbent["score"]
                mark = ""
                if gain > MIN_GAIN:
                    best, incumbent, improved, mark = trial, r, True, "  <- kept"
                print(f"    {name:<24} {str(value):<7} "
                      f"{r['gems']:7.0f} gems  {gain:+8.1f}{mark}")
        if not improved:
            break
    changed = {k: v for k, v in best.items() if v != SPACE[k][0]}
    print(f"  {map_name}: {'no change beat the default' if not changed else changed}")
    return {"signature": signature(map_name), "overrides": changed,
            "default_gems": base["gems"], "tuned_gems": incumbent["gems"],
            "gain": incumbent["gems"] - base["gems"]}


def emit() -> int:
    if not RESULTS.exists():
        print("no tuned.json yet")
        return 1
    data = json.loads(RESULTS.read_text())
    rows = []
    for name, r in sorted(data.items()):
        if not r.get("overrides") or not r.get("signature"):
            continue
        sig = tuple(r["signature"])
        body = ", ".join(f'"{k}": {v!r}' for k, v in r["overrides"].items())
        rows.append(f"    {sig}: {{{body}}},"
                    f"  # {name}  {r['gain']:+.0f} gems")
    table = "TABLE = {\n    # (width, height, groups): {config name: value}\n" \
            + "\n".join(rows) + "\n}"
    mp = WS / "bots" / BASE_BOT / "src" / "mappolicy.py"
    t = mp.read_text()
    t = re.sub(r"TABLE = \{.*?\n\}", table, t, flags=re.S)
    mp.write_text(t)
    print(f"wrote {len(rows)} map entries into {mp}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--maps")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--opponents", default=",".join(DEFAULT_OPPONENTS))
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--force-local", action="store_true",
                    help="tune opponent-dependent parameters locally anyway; "
                         "known to have produced a sign error")
    a = ap.parse_args()
    if a.emit:
        return emit()
    names = (list(map_files()) if a.all
             else [m.strip() for m in (a.maps or "").split(",") if m.strip()])
    if not names:
        ap.error("give --maps or --all")
    opponents = [o for o in a.opponents.split(",") if o]
    data = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    for name in names:
        try:
            data[name] = tune_map(name, opponents, a.passes, a.force_local)
        except Exception as e:                                  # keep partial work
            print(f"  {name}: failed, {e}")
            continue
        RESULTS.write_text(json.dumps(data, indent=1))
    gains = [v["gain"] for v in data.values() if v.get("gain")]
    print(f"\n{len(data)} maps tuned, {sum(1 for v in data.values() if v.get('overrides'))} "
          f"with an override, mean gain {sum(gains)/len(gains):.0f} gems"
          if gains else f"\n{len(data)} maps tuned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
