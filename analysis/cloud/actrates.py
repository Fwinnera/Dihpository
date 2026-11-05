#!/usr/bin/env python3
"""Per-turn action rates by side (focus team vs opponents) from action streams: move 4, attack 5, cast 6,
recall 11, out-of-fuel turn end 26 (no code 8), and turns with no move/attack/cast while alive."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
bdir, sdir, adir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
arm = sys.argv[4] if len(sys.argv) > 4 else None
meta = json.loads((bdir / "meta.json").read_text())
cnt = {"focus": collections.Counter(), "opp": collections.Counter()}
for m in meta:
    if arm and m.get("arm") != arm: continue
    fa = adir / f"{m['matchId']}.jsonl"; fs = sdir / f"{m['matchId']}.jsonl"
    if not fa.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    team_of = {}
    turn = collections.defaultdict(set)
    for l in fa.read_text().splitlines():
        r = json.loads(l)
        if not r[8] or r[1] < 0: continue
        turn[(r[0], r[1])].add(r[2])
    # team of each champion index: from the states if present, else from the first round's positions is unknown
    if fs.exists():
        for l in fs.read_text().splitlines():
            s = json.loads(l)
            if s["c"]:
                team_of = {c[0]: c[1] for c in s["c"]}; break
    else:
        continue
    for (rd, k), codes in turn.items():
        side = "focus" if team_of.get(k) == ours else "opp"
        c = cnt[side]
        c["turns"] += 1
        for code, name in ((4, "move"), (5, "attack"), (6, "cast"), (11, "recall"), (26, "fuel-out")):
            if code in codes: c[name] += 1
for side, c in cnt.items():
    print(f"{side:<6} turns {c['turns']:>8}  " + "  ".join(f"{k} {100 * c[k] / max(1, c['turns']):.2f}%" for k in ("move", "attack", "cast", "recall", "fuel-out")))
