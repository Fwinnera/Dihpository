#!/usr/bin/env python3
"""Party-map screens: candidates against opponents on chosen maps, both sides, one batch.

    pmscreen.py run TAG --cands a,b --opps x,y [--maps party|others|all|m1,m2] [--jobs N]
    pmscreen.py show TAG [TAG ...]            per opponent and map, W/L and gems
    pmscreen.py same TAG_A CAND_A TAG_B CAND_B   game-for-game identity of two candidates

One `cambc run-batch` builds every bot once, then plays the games in parallel; two
batches that share a bot must not run at the same time (the cmake configure collides).
Results land in ws/bench/TAG/<cand>__<opp>__<map>__<side>.{json,repl26a}; side is the
candidate's. A replay is a zip holding team-a.stdout and team-b.stdout.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WS = ROOT / "ws"
BENCH = WS / "bench"
CAMBC = Path.home() / "Library/Python/3.9/bin/cambc"
PARTY = ["01boss-battle", "00anvil", "02guardians", "03showdown", "00stampede", "00contest", "03homonoliths"]


def all_maps() -> list[str]:
    return sorted(p.stem for p in (WS / "maps").glob("*.map26a"))


def pick_maps(spec: str) -> list[str]:
    if spec == "party":
        return PARTY
    if spec == "others":
        return [m for m in all_maps() if m not in PARTY]
    if spec == "all":
        return all_maps()
    return [m.strip() for m in spec.split(",") if m.strip()]


def run(args) -> int:
    out = BENCH / args.tag
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for c in args.cands.split(","):
        for o in args.opps.split(","):
            for m in pick_maps(args.maps):
                for side in ("A", "B"):
                    stem = f"{c}__{o}__{m}__{side}"
                    if (out / f"{stem}.json").exists() or (out / f"{stem}.json.gz").exists():
                        continue
                    a, b = (c, o) if side == "A" else (o, c)
                    lines.append(f"{WS}/bots/{a} {WS}/bots/{b} {WS}/maps/{m}.map26a "
                                 f"{out}/{stem}.repl26a --statistics {out}/{stem}.json")
    if not lines:
        print("nothing to play")
        return 0
    manifest = out / f"manifest-{os.getpid()}.txt"
    manifest.write_text("\n".join(lines) + "\n")
    print(f"{args.tag}: {len(lines)} games", flush=True)
    env = dict(os.environ)
    env["PATH"] = f"{CAMBC.parent}:{env.get('PATH', '')}"
    with (out / "run.log").open("a") as log:
        r = subprocess.run([str(CAMBC), "run-batch", "--release", "--json", "--jobs", str(args.jobs),
                            "--timeout", "900", "--log-limit", str(args.log_limit), str(manifest)],
                           cwd=WS, stdout=log, stderr=log, env=env)
    return r.returncode


def load(p: Path) -> dict:
    return json.loads(gzip.open(p).read() if p.suffix == ".gz" else p.read_text())


def games(tag: str) -> dict:
    """(cand, opp, map, side) -> facts, from the candidate's side."""
    res = {}
    for p in sorted((BENCH / tag).glob("*__*__*__*.json*")):
        stem = p.name.split(".json")[0]
        c, o, m, side = stem.split("__")
        d = load(p)
        me, them = ("teamA", "teamB") if side == "A" else ("teamB", "teamA")
        g = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        ch = [x for x in d["champions"] if x["team"] == me]
        en = [x for x in d["champions"] if x["team"] == them]
        res[(c, o, m, side)] = {
            "win": d["match"]["outcome"] == me, "us": g.get(me, 0), "them": g.get(them, 0),
            "rounds": d["match"].get("roundsCompleted"),
            "collected": sum(int(x["metrics"]["collectedGems"]) for x in ch),
            "deaths": sum(int(x["metrics"]["deaths"]) for x in ch),
            "kills": sum(int(x["metrics"]["kills"]) for x in ch),
            "their_collected": sum(int(x["metrics"]["collectedGems"]) for x in en),
            "sig": json.dumps([d["match"].get("roundsCompleted"), d["match"]["outcome"], sorted(g.items()),
                               [(x["name"], x["team"], x["metrics"]) for x in d["champions"]]], sort_keys=True),
        }
    return res


def show(tags: list[str]) -> int:
    rows = {}
    for t in tags:
        rows.update({(t,) + k: v for k, v in games(t).items()})
    cands = sorted({(k[0], k[1]) for k in rows})
    opps = sorted({k[2] for k in rows})
    maps = [m for m in PARTY if any(k[3] == m for k in rows)] + sorted({k[3] for k in rows} - set(PARTY))
    for t, c in cands:
        tot_w = tot_n = 0
        print(f"=== {c} ({t})")
        for o in opps:
            cells, w, n, margin = [], 0, 0, 0
            for m in maps:
                cell = []
                for s in "AB":
                    g = rows.get((t, c, o, m, s))
                    if not g:
                        cell.append("  -     ")
                        continue
                    w += g["win"]; n += 1; margin += g["us"] - g["them"]
                    cell.append(f"{'W' if g['win'] else 'l'}{g['us']:>4}-{g['them']:<4}")
                cells.append(" ".join(cell))
            if not n:
                continue
            tot_w += w; tot_n += n
            print(f"  {o:<12} {w:>2}/{n:<2} margin {margin / n:+5.0f} | " + " | ".join(cells) if len(maps) <= 7
                  else f"  {o:<12} {w:>3}/{n:<3} margin {margin / n:+5.0f}")
        print(f"  total {tot_w}/{tot_n}   maps: {' | '.join(m[:13] for m in maps) if len(maps) <= 7 else len(maps)}")
        # per map over opponents
        if len(maps) <= 7:
            line = []
            for m in maps:
                ws = [rows[(t, c, o, m, s)]["win"] for o in opps for s in "AB" if (t, c, o, m, s) in rows]
                line.append(f"{m[:13]} {sum(ws)}/{len(ws)}")
            print("  by map: " + ", ".join(line))
    return 0


def same(tag_a: str, cand_a: str, tag_b: str, cand_b: str) -> int:
    a = {k[1:]: v for k, v in games(tag_a).items() if k[0] == cand_a}
    b = {k[1:]: v for k, v in games(tag_b).items() if k[0] == cand_b}
    common = sorted(set(a) & set(b))
    diff = [k for k in common if a[k]["sig"] != b[k]["sig"]]
    print(f"{cand_a} ({tag_a}) vs {cand_b} ({tag_b}): {len(common)} common games, "
          f"{len(common) - len(diff)} identical, {len(diff)} differ")
    for k in diff[:40]:
        print("   differ:", k, a[k]["us"], a[k]["them"], "|", b[k]["us"], b[k]["them"])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("tag")
    r.add_argument("--cands", required=True)
    r.add_argument("--opps", required=True)
    r.add_argument("--maps", default="party")
    r.add_argument("--jobs", type=int, default=6)
    r.add_argument("--log-limit", type=int, default=1048576)
    s = sub.add_parser("show")
    s.add_argument("tags", nargs="+")
    q = sub.add_parser("same")
    q.add_argument("args", nargs=4)
    a = ap.parse_args()
    if a.cmd == "run":
        return run(a)
    if a.cmd == "show":
        return show(a.tags)
    return same(*a.args)


if __name__ == "__main__":
    sys.exit(main())
