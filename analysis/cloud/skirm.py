#!/usr/bin/env python3
"""Fights from decoded replay states (read.mjs JSONL: one line per round, champs as
[index, team, type, x, y, hp, maxhp, alive, gold, gems, kills]).

    skirm.py BUNDLE_DIR STATES_DIR

For every champion death (alive -> dead), the fight that killed it: allies and enemies of the victim within
R tiles of it in the 10 rounds before the death, their health, and where it happened. Also team spacing:
for each living champion each round, the distance to its nearest living teammate, by zone and team.
"""
import collections
import json
import sys
from pathlib import Path

US = "Milk and Potatoes"
TYPES = ["ryth", "vesper_vale", "vendetta", "cassi", "issac", "stellar", "prism", "marcella",
         "willow", "ren", "varg", "tavi", "heart_of_ruin"]
MAPINFO = json.loads(Path("/home/user/runs/mapinfo/mapinfo.json").read_text())
MAPINFO = {k.replace("-", "_"): v for k, v in MAPINFO.items()}
R = 6


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def zone_of(depth):
    return ("our spawn" if depth < 0.12 else "our half" if depth < 0.45 else "middle" if depth < 0.55
            else "their half" if depth < 0.88 else "their spawn")


def main(bdir, sdir):
    meta = json.loads((Path(bdir) / "meta.json").read_text())
    fights = []
    spacing = collections.defaultdict(list)   # (team 'us'/'them', zone) -> nearest-teammate distances
    alone = collections.Counter()              # (team, zone) -> champion-rounds with no teammate within 5
    total = collections.Counter()
    for m in meta:
        f = Path(sdir) / f"{m['matchId']}.jsonl"
        if not f.exists():
            continue
        focus = m.get("focus", US)
        me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
        ours = 0 if me["side"] == "a" else 1
        mi = MAPINFO.get(m["map"].replace("-", "_"))
        if not mi:
            continue
        own, enemy = (mi["spawn_a"], mi["spawn_b"]) if ours == 0 else (mi["spawn_b"], mi["spawn_a"])

        def depth(p):
            do = min(cheb(p, q) for q in own)
            de = min(cheb(p, q) for q in enemy)
            return do / max(1, do + de)

        rounds = [json.loads(line) for line in f.read_text().splitlines()]
        rounds = [r for r in rounds if r["c"]]
        prev_alive = {}
        hist = collections.deque(maxlen=11)
        for st in rounds:
            hist.append(st)
            champs = st["c"]
            living = [c for c in champs if c[7] and c[3] >= 0]
            for c in living:
                team = "us" if c[1] == ours else "them"
                mates = [cheb((c[3], c[4]), (o[3], o[4])) for o in living if o[1] == c[1] and o[0] != c[0]]
                z = zone_of(depth((c[3], c[4])))
                d = min(mates) if mates else 99
                spacing[(team, z)].append(d)
                total[(team, z)] += 1
                if d > 5:
                    alone[(team, z)] += 1
            for c in champs:
                was = prev_alive.get(c[0])
                if was is not None and was[7] and not c[7]:
                    # c died this round; its last living position is was[3], was[4].
                    pos = (was[3], was[4])
                    if pos[0] < 0:
                        continue
                    allies, foes = set(), set()
                    ally_hp, foe_hp = [], []
                    for h in list(hist)[:-1]:
                        for o in h["c"]:
                            if not o[7] or o[3] < 0 or o[0] == c[0]:
                                continue
                            if cheb(pos, (o[3], o[4])) <= R:
                                (allies if o[1] == c[1] else foes).add(o[0])
                    first = list(hist)[0]["c"]
                    for o in first:
                        if o[0] in allies and o[7]:
                            ally_hp.append(o[5] / max(1, o[6]))
                        if o[0] in foes and o[7]:
                            foe_hp.append(o[5] / max(1, o[6]))
                    vhp0 = next((o[5] / max(1, o[6]) for o in first if o[0] == c[0] and o[7]), None)
                    team = "us" if c[1] == ours else "them"
                    fights.append(dict(match=m["matchId"], map=m["map"], round=st["r"], victim=team,
                                       vtype=TYPES[c[2]] if c[2] < len(TYPES) else c[2],
                                       zone=zone_of(depth(pos)), allies=len(allies), foes=len(foes),
                                       vhp0=vhp0, ally_hp=ally_hp, foe_hp=foe_hp, gems=was[9]))
            prev_alive = {c[0]: c for c in champs}
    Path("/home/user/runs/fights.json").write_text(json.dumps(fights))
    zones = ["our spawn", "our half", "middle", "their half", "their spawn"]
    games = len({x["match"] for x in fights})
    print(f"{len(fights)} deaths in {games} games")
    print("\nDeaths by zone, victim side, and numbers in the 10 rounds before (victim's allies within 6 / enemies within 6):")
    for z in zones:
        for v in ("us", "them"):
            xs = [x for x in fights if x["zone"] == z and x["victim"] == v]
            if not xs:
                continue
            nums = collections.Counter((x["allies"], x["foes"]) for x in xs)
            top = ", ".join(f"{a}v{b}:{n}" for (a, b), n in nums.most_common(6))
            vhp = sorted(x["vhp0"] for x in xs if x["vhp0"] is not None)
            print(f"  {z:<12} {v:<5} {len(xs) / games:5.2f}/game  victim hp 10 rounds before: median "
                  f"{vhp[len(vhp) // 2] if vhp else float('nan'):.2f}  |  (allies v enemies) {top}")
    print("\nSpacing: share of living champion-rounds with no teammate within 5, and median nearest teammate:")
    for z in zones:
        row = []
        for t in ("us", "them"):
            d = sorted(spacing[(t, z)])
            if d:
                row.append(f"{t}: alone {100 * alone[(t, z)] / total[(t, z)]:4.1f}% median {d[len(d) // 2]:>2} (n {total[(t, z)]})")
        print(f"  {z:<12} " + "   ".join(row))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
