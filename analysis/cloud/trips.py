#!/usr/bin/env python3
"""Recall trips from PF logs: recalls per champion per game by reason (the label before recalling), and the
rounds from the recall's end until the champion next hits a camp (farm/approach/capture/party-clear)."""
import collections, json, re, statistics, sys, zipfile
from pathlib import Path
US = "Milk and Potatoes"
PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) ")
d = Path(sys.argv[1]); meta = json.loads((d / "meta.json").read_text())
reasons = collections.Counter(); back = collections.defaultdict(list); champ_games = 0; deaths_back = []
WORK = {"farm", "approach", "capture", "party-clear", "to-reward"}
for m in meta:
    me = next(t for t in m["teams"] if t["name"] == US)
    try:
        out = zipfile.ZipFile(d / f"{m['matchId']}.repl26a").read(f"team-{me['side']}.stdout").decode("utf8", "replace").replace("\x00", "")
    except Exception: continue
    seq = collections.defaultdict(list)
    for p in PF.finditer(out): seq[int(p[2])].append((int(p[1]), p[3]))
    for t, rows in seq.items():
        rows.sort(); champ_games += 1
        i = 0
        while i < len(rows):
            r, lab = rows[i]
            if lab in ("recalling", "dead"):
                why = rows[i - 1][1] if i > 0 else "start"
                j = i
                while j < len(rows) and rows[j][1] == lab: j += 1
                if j >= len(rows): break
                end = rows[j][0]
                k = j
                while k < len(rows) and rows[k][1] not in WORK: k += 1
                if k < len(rows):
                    gap = rows[k][0] - end
                    if lab == "recalling":
                        reasons[why] += 1; back[why].append(gap)
                    else:
                        deaths_back.append(gap)
                i = j
            else:
                i += 1
print(f"{champ_games} champion-games")
tot = sum(reasons.values())
print(f"recalls per champion-game: {tot / champ_games:.1f}")
for why, c in reasons.most_common(8):
    g = back[why]
    print(f"  after {why:<12} {c / champ_games:4.1f} a champion-game, rounds back to a camp: median {statistics.median(g):.0f}, mean {statistics.mean(g):.0f}")
print(f"after death: {len(deaths_back) / champ_games:.1f} a champion-game, rounds from respawn to a camp: median {statistics.median(deaths_back):.0f}, mean {statistics.mean(deaths_back):.0f}")
