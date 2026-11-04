#!/usr/bin/env python3
"""Unranked ladder tests: the live bot against a fixed set of real teams.

    lab.py queue ARM [--from BASE] [--teams N] [--set 2|3]   one five-map group per team
    lab.py show ARM [ARM ...]                    results per team, map and arm

Every arm plays the same maps and sides against each team. `--from BASE` also replays
the opponent's bot from BASE's group (`--source-group`), so arms differ only in our bot.
Unranked groups play whatever version is live, so make the candidate live first and
take the README ladder lock. Each group is five matches of the team's 50-an-hour quota.
Arms are stored in ws/bench/lab/ARM.json.
"""
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")
WS = Path("/Users/faeezaullyar/Claude/battlecode/ws")
LAB = WS / "bench" / "lab"
US = "Milk and Potatoes"
# Ranks 176-228 on 2026-11-03 at 11:50Z (ratings 1,708-1,777): the band above rank 200.
TEAMS = [
    ("24731510-784f-4176-985e-17c1626934ca", "Rusty Epee"),
    ("271f8b15-7d97-4a0a-bd32-b634dd006dc0", "Crimson Pathfinders"),
    ("e747283d-a801-4175-8b9d-ee36df006daa", "The something"),
    ("91b991b0-c974-4ffe-a1f8-4c83c171e9f4", "Tübingen Quants"),
    ("9b0a89b8-f553-4916-8b58-eea33334757c", "neuro"),
    ("abb3b776-7d71-41f6-90c6-885aebdc64b4", "Shinshilachki"),
    ("b50b3aa9-a0fb-4388-93d2-3459e1a350a9", "Kingstonks"),
    ("409129b9-e6ac-4f80-921c-2ede2ed1cb4f", "Memory?"),
    ("1e25877b-9ea9-4821-bd54-236e44c5e650", "Kaizen"),
    ("7348a083-dc1d-45ec-a355-c4bede12dd6a", "tip"),
]
# Set 3 (added 2026-11-04 01:55Z): ten other teams ranked 186-208 then (ratings 1,734-1,772) and maps
# from another shuffle, so a candidate that passes sets 1 and 2 can be confirmed on games it was not
# picked on. Its base arm is v155's ab3_s3.
TEAMS3 = [
    ("64ae7e80-d604-4121-a067-210e515e5bb5", "Alpha pekka"),
    ("ce501991-2191-4063-9cdb-86103b8e9f81", "CompetitiveBasmaga"),
    ("fd795986-cfd3-4732-9fa9-94caba40067a", "V4.1 Flash"),
    ("bee75a64-fae5-48aa-8751-73d4e78ebfb5", "DIET CODE"),
    ("2cb78ebc-e61e-4ee0-9950-b3e3963d9743", "Rogue Noogers"),
    ("432f7d69-cce1-48c4-a446-2b293aa210b9", "decrest"),
    ("f752d854-acdd-4417-8c41-bf4b39108db6", "patisserie du pont neuf"),
    ("33fd952b-b067-40b2-a0d4-ba289bddcb57", "Quantom"),
    ("4938a543-0798-4879-b8ce-f63f98ca13c3", "BrendanBurgess"),
    ("b9b2f439-fc05-437f-907e-e8380921f9a4", "ClosedAI"),
]


def cambc(*args):
    for attempt in range(6):
        r = subprocess.run([CAMBC, *args], cwd=WS, capture_output=True, text=True, env=dict(os.environ))
        if r.returncode == 0:
            return json.loads(r.stdout) if r.stdout.strip().startswith("{") else r.stdout
        # Rapid calls are refused with HTTP 429; wait and retry.
        time.sleep(3 + 4 * attempt)
    sys.exit(f"cambc {' '.join(args)} failed: {r.stderr.strip()[-300:]}")


def plan(which=1):
    """Five maps per team, sides alternating; fixed by the seed. Set 1 is fifty distinct
    maps; set 2 is the other 36 and fourteen of set 1's, each with the side swapped."""
    maps = sorted(p.stem.replace("-", "_") for p in (WS / "maps").glob("*.map26a"))
    if which == 3:
        random.Random(2026_11_04).shuffle(maps)
        return [dict(team=tid, name=name, maps=maps[5 * i:5 * i + 5],
                     sides=["a", "b", "a", "b", "a"] if i % 2 == 0 else ["b", "a", "b", "a", "b"])
                for i, (tid, name) in enumerate(TEAMS3)]
    random.Random(2026_11_03).shuffle(maps)
    out = []
    for i, (tid, name) in enumerate(TEAMS):
        sides = ["a", "b", "a", "b", "a"] if i % 2 == 0 else ["b", "a", "b", "a", "b"]
        if which == 1:
            out.append(dict(team=tid, name=name, maps=maps[5 * i:5 * i + 5], sides=sides))
        else:
            rest = maps[50:] + maps[:14]
            ms = rest[5 * i:5 * i + 5]
            flip = [("b" if s == "a" else "a") if m in maps[:14] else s for m, s in zip(ms, sides)]
            out.append(dict(team=tid, name=name, maps=ms, sides=flip))
    return out


def queue(arm, base=None, n=len(TEAMS), which=1):
    LAB.mkdir(parents=True, exist_ok=True)
    f = LAB / f"{arm}.json"
    if f.exists():
        sys.exit(f"{f} exists")
    rows = plan(which)[:n]
    if base:
        prev = {r["team"]: r for r in json.loads((LAB / f"{base}.json").read_text())["groups"]}
    live = cambc("submissions", "list", "--json")["active"]
    out = dict(arm=arm, base=base, version=live["version"], note=live.get("note"), queued=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), groups=[])
    for r in rows:
        args = ["match-groups", "create", r["team"], "--maps", ",".join(r["maps"]), "--sides", ",".join(r["sides"]), "--json"]
        if base:
            args += ["--source-group", prev[r["team"]]["group"]]
        d = cambc(*args)
        out["groups"].append(dict(r, group=d["groupId"]))
        print(f"{r['name']:<22} {d['groupId']}  {' '.join(r['maps'])}")
        f.write_text(json.dumps(out, indent=1))
        time.sleep(2)
    print(f"{arm}: version {out['version']} ({out['note']}), {len(out['groups'])} groups")


def results(arm):
    d = json.loads((LAB / f"{arm}.json").read_text())
    res = {}
    for g in d["groups"]:
        cache = LAB / "groups" / f"{g['group']}.json"
        if cache.exists():
            s = json.loads(cache.read_text())
        else:
            s = cambc("match-groups", "show", g["group"], "--json")
            if all(m.get("status") == "finished" for m in s["matches"]) and len(s["matches"]) == 5:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(s))
            time.sleep(1)
        for m in s["matches"]:
            if m.get("status") != "finished":
                res[(g["name"], m["map"])] = None
                continue
            me = next(t for t in m["teams"] if t["name"] == US)
            res[(g["name"], m["map"])] = me.get("result") == "win"
    return d, res


def show(arms):
    data = [results(a) for a in arms]
    keys = sorted({k for _, r in data for k in r})
    print(f"{'team':<22}{'map':<22}" + "".join(f"{a:>10}" for a in arms))
    for k in keys:
        cells = []
        for _, r in data:
            v = r.get(k, "")
            cells.append("" if v == "" else ("..." if v is None else ("W" if v else "-")))
        print(f"{k[0]:<22}{k[1]:<22}" + "".join(f"{c:>10}" for c in cells))
    for a, (d, r) in zip(arms, data):
        done = [v for v in r.values() if v is not None]
        print(f"{a}: version {d['version']}, {sum(done)} of {len(done)} won ({len(r) - len(done)} pending)")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "queue":
        args = sys.argv[3:]
        base = args[args.index("--from") + 1] if "--from" in args else None
        n = int(args[args.index("--teams") + 1]) if "--teams" in args else len(TEAMS)
        which = int(args[args.index("--set") + 1]) if "--set" in args else 1
        queue(sys.argv[2], base, n, which)
    elif cmd == "show":
        show(sys.argv[2:])
    else:
        sys.exit(__doc__)
