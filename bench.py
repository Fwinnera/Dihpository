#!/usr/bin/env python3
"""Measure a CAMBC bot against several opponents, both sides, by mechanism.

Why this exists
---------------
A 39-map sweep against one opponent cannot resolve a change worth less than about
twenty gems a game. The engine is deterministic -- two runs of one build are
byte-identical -- so there is no sampling noise to average away, but a 2,000-round
game amplifies any timing difference into a different trajectory. A dead loop whose
result nothing reads, sized like a real optimisation, moves fifteen of thirty-nine
maps and swings the gem mean by twenty-two.

Two things widen the instrument:

1.  More independent games. Each (opponent, map, side) is its own trajectory, so
    four opponents over both sides is 312 games rather than 39.
2.  Mechanism counts rather than the gem mean. Every change this project got right
    was visible as a direct count -- submitted over collected, healing received,
    damage taken per death -- and every one it got wrong was a gem mean inside the
    noise. A count does not pass through 2,000 rounds of amplification.

`--twin` is the honest part: give it a build whose decisions are identical to the
subject's (a dead loop is the usual trick) and every metric is reported with the
band that neutral build moved it by. A difference inside its own band is not a
measurement, whatever its sign.

Usage
-----
    bench.py BOT [--opponents a,b,c] [--twin BOT] [--tag NAME] [--jobs N]
    bench.py --compare TAG_A TAG_B
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent / "ws"
CAMBC = Path.home() / "Library" / "Python" / "3.9" / "bin" / "cambc"
DEFAULT_OPPONENTS = ["greatsage", "base", "colleague", "boss_focus"]
RESULTS = WS / "bench"

# Each entry is (label, how to compute it per game). "higher is better" is only
# used to orient the printed arrow, never to decide anything.
SUM_FIELDS = [
    "collectedGems", "deaths", "earnedGold", "healingDone", "healingReceived",
    "monsterDamageDone", "monsterDamageTaken", "championDamageDone",
    "championDamageTaken", "kills", "assists",
]


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{CAMBC.parent}:{env.get('PATH', '')}"
    return subprocess.run(cmd, env=env, **kw)


def build(bot: str) -> None:
    r = run([str(CAMBC), "build", "--release", f"bots/{bot}"],
            cwd=WS, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"build failed for {bot}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")


def sweep(bot: str, opponents: list[str], tag: str, jobs: int) -> Path:
    """Play every map against every opponent from both sides."""
    out = RESULTS / tag
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    maps = sorted(WS.glob("maps/*.map26a"))
    # BENCH_MAPS=a,b,c restricts a sweep to those maps, for a change that only
    # acts on some of them; everywhere else it would add re-roll noise alone.
    only = os.environ.get("BENCH_MAPS")
    if only:
        keep = {m.strip().replace("_", "-") for m in only.split(",")} | {m.strip() for m in only.split(",")}
        maps = [m for m in maps if m.stem in keep]
    if not maps:
        sys.exit(f"no maps under {WS / 'maps'}")
    lines = []
    for opp in opponents:
        for m in maps:
            for side in ("A", "B"):
                a, b = (bot, opp) if side == "A" else (opp, bot)
                stem = f"{opp}__{m.stem}__{side}"
                lines.append(
                    f"{WS}/bots/{a} {WS}/bots/{b} {m} "
                    f"{out}/{stem}.repl26a --statistics {out}/{stem}.json"
                )
    manifest = out / "manifest.txt"
    manifest.write_text("\n".join(lines) + "\n")
    print(f"  {tag}: {len(lines)} games "
          f"({len(opponents)} opponents x {len(maps)} maps x 2 sides)", flush=True)
    log = (out / "run.log").open("w")
    r = run([str(CAMBC), "run-batch", "--release", "--json", "--jobs", str(jobs),
             "--timeout", "300", str(manifest)], cwd=WS, stdout=log, stderr=log)
    log.close()
    done = len(list(out.glob("*.json")))
    if done < len(lines):
        print(f"  warning: {done}/{len(lines)} games produced statistics "
              f"(see {out / 'run.log'})", flush=True)
    return out


def read(folder: Path) -> dict:
    """Aggregate one sweep, always from the subject's point of view."""
    games, per_opp = [], {}
    for p in sorted(folder.glob("*.json")):
        opp, mapname, side = p.stem.split("__")
        d = json.loads(p.read_text())
        me, them = ("teamA", "teamB") if side == "A" else ("teamB", "teamA")
        subs = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        g = {"opp": opp, "map": mapname, "side": side,
             "submittedGems": float(subs.get(me, 0)),
             "oppGems": float(subs.get(them, 0)),
             "win": 1.0 if d["match"]["outcome"] == me else 0.0}
        for f in SUM_FIELDS:
            g[f] = sum(float(c["metrics"][f]) for c in d["champions"]
                       if c["team"] == me)
        games.append(g)
        per_opp.setdefault(opp, []).append(g)
    return {"games": games, "per_opp": per_opp, "n": len(games)}


def metrics(data: dict) -> dict:
    """Mechanism counts, each a mean per game over every opponent and side."""
    g = data["games"]
    if not g:
        return {}
    n = float(len(g))
    s = lambda f: sum(x[f] for x in g) / n
    safe = lambda a, b: a / b if b else 0.0
    collected, submitted = s("collectedGems"), s("submittedGems")
    taken = s("monsterDamageTaken") + s("championDamageTaken")
    return {
        "win rate %": 100.0 * s("win"),
        "gems submitted": submitted,
        "gems collected": collected,
        "submitted / collected %": 100.0 * safe(submitted, collected),
        "gems lost to deaths": collected - submitted,
        "gold earned": s("earnedGold"),
        "deaths": s("deaths"),
        "damage taken per death": safe(taken, s("deaths")),
        "healing received": s("healingReceived"),
        "healing done": s("healingDone"),
        "monster damage done": s("monsterDamageDone"),
        "monster dmg done per taken": safe(s("monsterDamageDone"),
                                           s("monsterDamageTaken")),
        # How much camp health we chew through per gem we get out of it. The
        # opponents sit at 133 and sage2 at 238, which is a target-selection
        # defect rather than a throughput one: a ratio, so it resolves far
        # better than the gem mean.
        "damage per gem collected": safe(s("monsterDamageDone"), collected),
        "gold per 1k monster damage": 1000.0 * safe(s("earnedGold"),
                                                    s("monsterDamageDone")),
        "kills": s("kills"),
        "opponent gems": s("oppGems"),
    }


def spread(data: dict) -> dict:
    """Per-metric standard error across games, for context on each mean.

    This is not the resolution band -- the band comes from --twin -- but a metric
    whose per-game spread is enormous is one to distrust even so.
    """
    g = data["games"]
    out = {}
    for f, label in (("submittedGems", "gems submitted"),
                     ("collectedGems", "gems collected"),
                     ("earnedGold", "gold earned"),
                     ("deaths", "deaths"),
                     ("win", "win rate %")):
        vals = [x[f] * (100.0 if f == "win" else 1.0) for x in g]
        if len(vals) < 2:
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
        out[label] = math.sqrt(var / len(vals))
    return out


def report(subject: dict, twin: dict | None, baseline: dict | None,
           baseline_twin: dict | None = None) -> None:
    m = metrics(subject)
    tw = metrics(twin) if twin else None
    bl = metrics(baseline) if baseline else None
    se = spread(subject)

    # When the baseline has a twin too, the band is the WORSE of the two. Using only
    # the subject's band flatters the result: a change can clear its own build's
    # band and sit inside the band of the build it is being compared against, which
    # means the two are not distinguishable. Reporting the ratio rather than a bare
    # real/noise label keeps 1.04x from reading like 13x.
    bl_tw = metrics(baseline_twin) if baseline_twin else None

    head = f"  {'metric':<30}{'value':>12}"
    if bl:
        head += f"{'baseline':>12}{'change':>10}"
    if tw:
        head += f"{'band':>9}{'ratio':>9}{'':>8}"
    print(head)
    print("  " + "-" * (len(head) - 2))
    rows = []
    for k in m:
        band = abs(tw[k] - m[k]) if tw else None
        if band is not None and bl_tw and k in bl_tw and bl:
            band = max(band, abs(bl_tw[k] - bl[k]))
        change = (m[k] - bl.get(k, 0.0)) if bl else None
        ratio = (abs(change) / band) if (band and change is not None) else None
        rows.append((k, band, change, ratio))
    # Largest signal-to-band first: that ordering is the finding.
    if any(r[3] is not None for r in rows):
        rows.sort(key=lambda r: -(r[3] if r[3] is not None else -1))
    for k, band, change, ratio in rows:
        row = f"  {k:<30}{m[k]:>12.2f}"
        if bl:
            row += f"{bl.get(k, 0.0):>12.2f}{change:>+10.2f}"
        if band is not None:
            row += f"{band:>9.2f}"
            if ratio is not None:
                row += f"{min(ratio, 999):>8.1f}x"
                row += "  REAL" if ratio > 1.0 else "  noise"
        elif k in se:
            row += f"{se[k]:>9.2f}  (se)"
        print(row)

    print()
    print("  by opponent (gems submitted / opponent gems / win rate):")
    for opp, games in sorted(subject["per_opp"].items()):
        n = float(len(games))
        mine = sum(x["submittedGems"] for x in games) / n
        theirs = sum(x["oppGems"] for x in games) / n
        wr = 100.0 * sum(x["win"] for x in games) / n
        print(f"    {opp:<22}{mine:>8.0f}{theirs:>10.0f}{wr:>9.1f}%  ({int(n)} games)")

    sides = {}
    for x in subject["games"]:
        sides.setdefault(x["side"], []).append(x)
    print()
    print("  by side (checks for a side bias in the pool, not in the bot):")
    for side, games in sorted(sides.items()):
        n = float(len(games))
        print(f"    team {side}{sum(x['submittedGems'] for x in games) / n:>12.0f} gems"
              f"{100.0 * sum(x['win'] for x in games) / n:>9.1f}% wins  ({int(n)} games)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bot", nargs="?", help="bot directory under ws/bots")
    ap.add_argument("--opponents", default=",".join(DEFAULT_OPPONENTS))
    ap.add_argument("--twin", help="decision-identical build, for the neutral band")
    ap.add_argument("--baseline", help="an earlier --tag to compare against")
    ap.add_argument("--tag", help="name for this run (default: the bot name)")
    ap.add_argument("--jobs", type=int, default=5)
    ap.add_argument("--reuse", action="store_true",
                    help="read existing results for --tag instead of replaying")
    ap.add_argument("--compare", nargs=2, metavar=("TAG_A", "TAG_B"),
                    help="report two existing tags against each other")
    args = ap.parse_args()

    if args.compare:
        a, b = (read(RESULTS / t) for t in args.compare)
        at, bt = (RESULTS / f"{t}__twin" for t in args.compare)
        print(f"\n{args.compare[1]} against {args.compare[0]} "
              f"({a['n']} vs {b['n']} games)\n")
        report(b, read(bt) if bt.exists() else None, a,
               read(at) if at.exists() else None)
        return 0

    if not args.bot:
        ap.error("a bot is required unless --compare is used")
    opponents = [o for o in args.opponents.split(",") if o]
    tag = args.tag or args.bot

    if not args.reuse:
        print(f"building {args.bot}" + (f" and {args.twin}" if args.twin else ""))
        build(args.bot)
        if args.twin:
            build(args.twin)
        print("playing:")
        sweep(args.bot, opponents, tag, args.jobs)
        if args.twin:
            sweep(args.twin, opponents, f"{tag}__twin", args.jobs)

    subject = read(RESULTS / tag)
    twin_dir = RESULTS / f"{tag}__twin"
    twin = read(twin_dir) if twin_dir.exists() else None
    base_dir = RESULTS / args.baseline if args.baseline else None
    baseline = read(base_dir) if base_dir and base_dir.exists() else None
    bt_dir = RESULTS / f"{args.baseline}__twin" if args.baseline else None
    baseline_twin = read(bt_dir) if bt_dir and bt_dir.exists() else None

    print(f"\n{args.bot} over {subject['n']} games "
          f"({len(opponents)} opponents, both sides, {len(list(WS.glob('maps/*.map26a')))} maps)\n")
    report(subject, twin, baseline, baseline_twin)
    if twin:
        print()
        print("  'neutral band' is how far a decision-identical build moved each metric.")
        print("  A change inside its own band is not a measurement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
