#!/usr/bin/env python3
"""One table comparing teams on every behaviour measured today.

    profile_top.py top1:prism best girl  top2:willow best girl  ...  us

Each `folder:team name` is a directory under ws/bench written by
fetch_team.py; `us` is our version 93 and greatsage ladder games.
Bases are located by where each team shops, and positions are placed on the
line between them: 0 at home, 1 at the enemy base. Monolith groups come from
ws/bench/camptable.json.
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
US = "Milk and Potatoes"
TABLE = json.loads((WS / "bench/camptable.json").read_text())


def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
    return (out + [out[-1] if out else 0.0] * n)[:n]


def games(spec):
    if spec == "us":
        for tag in ("v93_live", "db_base"):
            for gf in sorted((WS / "bench/ladder" / tag).glob("group_*.json")):
                for m in json.loads(gf.read_text()).get("matches", []):
                    me = next((t for t in m["teams"] if t["name"] == US), None)
                    f = WS / "bench/ladder" / tag / "summaries" / f"{m['matchId'][:8]}.json"
                    if me and f.exists():
                        yield f, ("teamA" if me["side"] == "a" else "teamB"), me["result"] == "win", m["map"]
        return
    folder, name = spec.split(":", 1)
    for m in json.loads((WS / "bench" / folder / "matches.json").read_text()):
        me = next((t for t in m["teams"] if t["name"] == name), None)
        f = WS / "bench" / folder / "summaries" / f"{m['matchId']}.json"
        if me and f.exists():
            yield f, ("teamA" if me["side"] == "a" else "teamB"), me["result"] == "win", m["map"]


def depth(p, home, away):
    vx, vy = away[0] - home[0], away[1] - home[1]
    L = vx * vx + vy * vy
    return None if not L else ((p[0] - home[0]) * vx + (p[1] - home[1]) * vy) / L


def profile(spec):
    S = defaultdict(float); n = 0; wins = 0
    draft = Counter(); held = Counter(); budget = Counter(); pickups = []
    clear_d, dep_d, mono_c, mono_g, carry_k = [], [], 0, 0.0, 0
    first_emblems = Counter()
    for path, side, win, mp in games(spec):
        d = json.loads(path.read_text()); n += 1; wins += win
        other = "teamB" if side == "teamA" else "teamA"
        R = d["match"]["roundsCompleted"]; S["rounds"] += R
        mono = {g["id"] for g in TABLE.get(mp.replace("-", "_"), []) if g["monolith"]}
        names = {c["id"]: c["name"] for c in d["roster"]["champions"] if c["team"] == side}
        for c in d["roster"]["champions"]:
            if c["team"] == side:
                draft[c["name"]] += 1
        for c in d["champions"]:
            if c["team"] == side:
                for i in c.get("items") or []:
                    if "Emblem" in i["item"]:
                        held[i["item"].split()[0]] += int(i.get("quantity", 1))
        tl = defaultdict(dict)
        for x in d["championTimelines"]:
            if x["owner"]["id"] in names and x["metric"] in ("championDamageDone", "championDamageTaken",
                                                             "monsterDamageDone", "deaths"):
                tl[x["owner"]["id"]][x["metric"]] = expand(x["runs"], R + 1)
        for s in tl.values():
            if len(s) < 4:
                continue
            dead = False
            for r in range(1, R + 1):
                up = lambda k: s[k][r] > s[k][r - 1]
                if up("deaths"):
                    dead = True
                if up("championDamageDone") or up("championDamageTaken"):
                    budget["fight"] += 1; dead = False
                elif up("monsterDamageDone"):
                    budget["farm"] += 1; dead = False
                elif dead:
                    budget["dead"] += 1
                else:
                    budget["other"] += 1
        buys = defaultdict(list)
        for e in d["events"]:
            if e["kind"] == "buyItem":
                buys[(e.get("owner") or {}).get("team")] += [(x["x"], x["y"]) for x in e["entries"] if "x" in x]
        home = away = None
        if buys[side] and buys[other]:
            home = (st.median(p[0] for p in buys[side]), st.median(p[1] for p in buys[side]))
            away = (st.median(p[0] for p in buys[other]), st.median(p[1] for p in buys[other]))
        losses = {}
        for e in d["events"]:
            if e["kind"] == "gemLoss" and (e.get("owner") or {}).get("team") == other:
                for x in e["entries"]:
                    losses[(e["owner"]["id"], x["timestamp"]["round"])] = float(x.get("value", 0) or 0)
        shards = defaultdict(Counter); seq = defaultdict(list)
        for e in d["events"]:
            o = e.get("owner") or {}
            if o.get("team") != side:
                continue
            for x in e.get("entries", []):
                k = e["kind"]; tg = x.get("target") or {}
                if k == "death": S["deaths"] += 1
                elif k == "kill":
                    S["kills"] += 1
                    if losses.get((tg.get("id"), x["timestamp"]["round"]), 0) > 0:
                        carry_k += 1
                elif k == "campClear":
                    S["clears"] += 1
                    if tg.get("id") in mono:
                        mono_c += 1
                    if home and "x" in x:
                        dp = depth((x["x"], x["y"]), home, away)
                        if dp is not None: clear_d.append(dp)
                elif k == "gemCollection" and tg.get("kind") == "campGroup":
                    v = float(x.get("value", 0) or 0); pickups.append(v)
                    if tg.get("id") in mono:
                        mono_g += v
                elif k == "gemSubmission":
                    S["deposits"] += 1; S["dep_gems"] += float(x.get("value", 0) or 0)
                    if home and "x" in x:
                        dp = depth((x["x"], x["y"]), home, away)
                        if dp is not None: dep_d.append(dp)
                elif k == "wardPlacement": S["wards"] += 1
                elif k == "buyItem":
                    it = tg.get("name", "")
                    if "Shard" in it:
                        shards[o["name"]][it] += int(x.get("value", 1) or 1)
                        if shards[o["name"]][it] >= 5:
                            shards[o["name"]][it] -= 5
                            seq[o["name"]].append((x["timestamp"]["round"], it.split()[0]))
                    elif "Emblem" in it:
                        seq[o["name"]].append((x["timestamp"]["round"], it.split()[0]))
        for nm, s in seq.items():
            first_emblems[" > ".join(f for _, f in sorted(s)[:3])] += 1
        g = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        S["gems"] += g[side]
    if not n:
        return None
    tb = sum(budget.values()) or 1
    return {
        "games": n, "record": f"{wins}-{n - wins}", "rounds": S["rounds"] / n, "gems": S["gems"] / n,
        "farm%": 100 * budget["farm"] / tb, "fight%": 100 * budget["fight"] / tb, "dead%": 100 * budget["dead"] / tb,
        "deaths": S["deaths"] / n, "kills": S["kills"] / n, "carrier kills": carry_k / n,
        "clears": S["clears"] / n, "gems/pickup": st.mean(pickups) if pickups else 0,
        "zero-gem %": 100 * sum(1 for v in pickups if v == 0) / max(1, len(pickups)),
        "monolith clears": mono_c / n, "monolith gems": mono_g / n,
        "clear depth": st.median(clear_d) if clear_d else 0, "deposit depth": st.median(dep_d) if dep_d else 0,
        "deposits": S["deposits"] / n, "gems/deposit": S["dep_gems"] / max(1, S["deposits"]),
        "wards": S["wards"] / n,
        "draft": ", ".join(f"{k} {100 * v / n:.0f}%" for k, v in draft.most_common(6)),
        "emblems held": ", ".join(f"{k} {v / n:.1f}" for k, v in held.most_common(5)),
        "opening": "; ".join(f"{k} ({v})" for k, v in first_emblems.most_common(3)),
    }


def main(specs):
    rows = [(s.split(":", 1)[-1] if s != "us" else "US (v93/greatsage)", profile(s)) for s in specs]
    rows = [(a, b) for a, b in rows if b]
    keys = ["games", "record", "rounds", "gems", "farm%", "fight%", "dead%", "deaths", "kills", "carrier kills",
            "clears", "gems/pickup", "zero-gem %", "monolith clears", "monolith gems", "clear depth",
            "deposit depth", "deposits", "gems/deposit", "wards"]
    w = 15
    print("%-18s" % "" + "".join(("%" + str(w) + "s") % a[:w - 1] for a, _ in rows))
    for k in keys:
        cells = []
        for _, p in rows:
            v = p[k]
            cells.append(("%" + str(w) + "s") % (v if isinstance(v, str) else f"{v:.1f}" if abs(v) < 100 else f"{v:.0f}"))
        print("%-18s" % k + "".join(cells))
    for k in ("draft", "emblems held", "opening"):
        print(f"\n{k.upper()}")
        for a, p in rows:
            print(f"  {a:<22} {p[k]}")


if __name__ == "__main__":
    main(sys.argv[1:])
