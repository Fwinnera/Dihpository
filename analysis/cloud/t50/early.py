#!/usr/bin/env python3
"""early.py DIR [--team NAME_OR_ID ...]: per team-game economy at rounds 100/200/300/400 from match summaries.
Prints one row per (game, team) and the averages by group (focus teams vs their opponents, or us vs them)."""
import json, glob, sys, collections
from pathlib import Path

def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
    if len(out) < n: out += [out[-1] if out else 0.0] * (n - len(out))
    return out

def load(d):
    meta = {m["matchId"]: m for m in json.loads((Path(d) / "meta.json").read_text())}
    games = []
    for mid, m in meta.items():
        f = Path(d) / f"{mid}.json"
        if not f.exists(): continue
        s = json.loads(f.read_text())
        games.append((m, s))
    return games

MARKS = (100, 200, 300, 400)

def team_rows(m, s):
    rounds = int(s["match"]["roundsCompleted"])
    names = {}
    for t in m["teams"]:
        names["teamA" if t["side"] == "a" else "teamB"] = t
    tl = collections.defaultdict(dict)  # (team) -> metric -> per-round sum
    for t in s["championTimelines"]:
        team = t["owner"]["team"]; metric = t["metric"]
        if metric not in ("earnedGold", "spentGold", "collectedGems", "submittedGems", "monsterDamageDone", "deaths", "kills", "championDamageDone", "monsterDamageTaken", "championDamageTaken", "shieldingDone", "healingReceived"): continue
        v = expand(t["runs"], rounds + 2)
        cur = tl[team].get(metric)
        tl[team][metric] = v if cur is None else [a + b for a, b in zip(cur, v)]
    rows = {}
    for team in ("teamA", "teamB"):
        nch = len([c for c in s["champions"] if c["team"] == team])
        r = dict(team=names[team]["name"], teamId=names[team]["teamId"], result=names[team].get("result"), rounds=rounds, bodies=nch,
                 map=m.get("map"), draft=[c["name"] for c in s["champions"] if c["team"] == team])
        for mk in MARKS:
            i = min(mk, rounds)
            for metric, v in tl[team].items():
                r[f"{metric}@{mk}"] = v[min(i, len(v) - 1)]
        rows[team] = r
    # events
    for e in s["events"]:
        team = e["owner"]["team"] if isinstance(e["owner"], dict) else e["owner"]
        if team not in rows: continue
        r = rows[team]
        for en in e["entries"]:
            rd = en["timestamp"]["round"]
            if e["kind"] == "campClear" and rd <= 400: r["clears@400"] = r.get("clears@400", 0) + 1
            if e["kind"] == "buyItem":
                r.setdefault("buys", []).append((rd, e["owner"]["name"], en["target"]["name"], int(en["value"])))
            if e["kind"] == "itemCombination":
                r.setdefault("emblems", []).append((rd, e["owner"]["name"], en["target"]["name"]))
            if e["kind"] == "gemCollection" and rd <= 400:
                r.setdefault("coll", []).append((rd, e["owner"]["name"], en["target"].get("id"), int(en["value"])))
            if e["kind"] == "gemSubmission":
                r.setdefault("subs", []).append((rd, e["owner"]["name"], int(en["value"])))
    return rows

def main():
    d = sys.argv[1]
    focus = set(sys.argv[3:]) if len(sys.argv) > 3 and sys.argv[2] == "--team" else None
    games = load(d)
    groups = collections.defaultdict(list)
    for m, s in games:
        rows = team_rows(m, s)
        for team, r in rows.items():
            if focus is None:
                key = "focus" if r["teamId"] == m.get("focus") or r["team"] == m.get("focus") else "opp"
            else:
                key = "focus" if (r["teamId"] in focus or r["team"] in focus) else "opp"
            groups[key].append(r)
    for key, rs in groups.items():
        print(f"== {key}: {len(rs)} team-games; wins {sum(1 for r in rs if r['result']=='win')}; median rounds {sorted(r['rounds'] for r in rs)[len(rs)//2]}; bodies {sum(r['bodies'] for r in rs)/len(rs):.2f}")
        for metric in ("earnedGold", "spentGold", "collectedGems", "submittedGems", "monsterDamageDone", "monsterDamageTaken", "championDamageDone", "championDamageTaken", "deaths", "kills", "shieldingDone", "healingReceived"):
            print(f"  {metric:<22}" + "".join(f"{sum(r.get(f'{metric}@{mk}',0) for r in rs)/len(rs):>10.0f}" for mk in MARKS))
        print(f"  {'camp clears by 400':<22}{sum(r.get('clears@400',0) for r in rs)/len(rs):>10.1f}")
        first = [min(b[0] for b in r["buys"]) for r in rs if r.get("buys")]
        print(f"  first purchase round (team): mean {sum(first)/max(1,len(first)):.0f}")
        firstbank = [min(b[0] for b in r["subs"]) for r in rs if r.get("subs")]
        print(f"  first tribute round (team): mean {sum(firstbank)/max(1,len(firstbank)):.0f}; mean tribute size {sum(b[2] for r in rs for b in r.get('subs',[]))/max(1,sum(len(r.get('subs',[])) for r in rs)):.1f}")
        # emblem order per champion
        emb = collections.defaultdict(collections.Counter)
        for r in rs:
            per = collections.defaultdict(list)
            for rd, ch, name in sorted(r.get("emblems", [])):
                per[ch].append(name.replace(" Emblem of ", ":"))
            for ch, lst in per.items():
                emb[ch][" > ".join(lst[:4])] += 1
        for ch, c in sorted(emb.items(), key=lambda kv: -sum(kv[1].values())):
            tot = sum(c.values())
            print(f"  {ch:<14}{tot:>3}  " + " | ".join(f"{k} x{v}" for k, v in c.most_common(3)))
        dr = collections.Counter()
        for r in rs:
            for c in set(r["draft"]): dr[c] += 1
        print("  picks: " + ", ".join(f"{k} {v}" for k, v in dr.most_common()))

main()
