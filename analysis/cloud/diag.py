#!/usr/bin/env python3
"""Deaths in profiled games: p_pm prints, for every champion turn,
PF round type label x y hp maxhp gems gold group ne5 ne8 na5 dmin
(visible enemies within 5 and 8, allies within 5, nearest visible enemy; -1 when dead).

    diag.py DIR [DIR ...]

DIR holds <matchId>.repl26a bundles, <matchId>.json summaries (`cambc matches summary --json`) and
meta.json (a list of match records: matchId, map, teams[name, side, result]). Map facts (spawns) come
from MAPINFO, a JSON of map -> {spawn_a, spawn_b, w, h} made by the probe_mapinfo bot.

For each of our deaths it finds "contact": the first turn in the 40 before the death from which an
enemy stayed within 8 tiles (no gap longer than 3 turns), and reports what the champion was doing
then, its health, how many allies were within 5, how long it lived after contact, and where it died.
"""
import collections
import json
import re
import sys
import zipfile
from pathlib import Path

US = "Milk and Potatoes"
TYPES = ["ryth", "vesper_vale", "vendetta", "cassi", "issac", "stellar", "prism", "marcella",
         "willow", "ren", "varg", "tavi", "heart_of_ruin"]
PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) (-?\d+) (-?\d+) (\d+(?:\.\d+)?) (\d+(?:\.\d+)?) (\d+) (\d+) (-?\d+)"
                r"(?: (-?\d+) (-?\d+) (-?\d+) (-?\d+))?")
MAPINFO = Path("/home/user/runs/mapinfo/mapinfo.json")


def norm(name):
    return name.lower().replace(" ", "_").replace("-", "_")


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def zone(depth):
    if depth is None:
        return "?"
    return ("our spawn" if depth < 0.12 else "our half" if depth < 0.45 else "middle" if depth < 0.55
            else "their half" if depth < 0.88 else "their spawn")


ZONES = ["our spawn", "our half", "middle", "their half", "their spawn", "?"]


def main(dirs):
    info = json.loads(MAPINFO.read_text()) if MAPINFO.exists() else {}
    info = {norm(k): v for k, v in info.items()}
    games = wins = 0
    our_deaths = collections.Counter()
    their_deaths = collections.Counter()
    rows = []
    per_game = []
    for d in map(Path, dirs):
        meta = json.loads((d / "meta.json").read_text())
        for m in meta:
            mid = m["matchId"]
            bundle, summ = d / f"{mid}.repl26a", d / f"{mid}.json"
            if not bundle.exists() or not summ.exists():
                continue
            me = next(t for t in m["teams"] if t["name"] == US)
            opp = next(t for t in m["teams"] if t["name"] != US)
            side = me["side"]
            our_team = "teamA" if side == "a" else "teamB"
            mi = info.get(norm(m["map"]))
            if mi:
                own, enemy = (mi["spawn_a"], mi["spawn_b"]) if side == "a" else (mi["spawn_b"], mi["spawn_a"])
            else:
                own = enemy = None

            def depth(x, y):
                if own is None or x < 0:
                    return None
                do = min(cheb((x, y), q) for q in own)
                de = min(cheb((x, y), q) for q in enemy)
                return do / max(1, do + de)

            try:
                out = zipfile.ZipFile(bundle).read(f"team-{side}.stdout").decode("utf8", "replace").replace("\x00", "")
            except (KeyError, zipfile.BadZipFile):
                continue
            seq = collections.defaultdict(dict)
            for p in PF.finditer(out):
                r, t = int(p[1]), int(p[2])
                if t >= len(TYPES):
                    continue
                ex = [int(p[i]) if p[i] is not None else -1 for i in (11, 12, 13, 14)]
                seq[TYPES[t]][r] = dict(r=r, lab=p[3], x=int(p[4]), y=int(p[5]), hp=float(p[6]), mx=float(p[7]),
                                        gems=int(p[8]), gold=int(p[9]), ne5=ex[0], ne8=ex[1], na5=ex[2], dmin=ex[3])
            s = json.loads(summ.read_text())
            names = {c["id"]: (norm(c["name"]), c["team"]) for c in s["roster"]["champions"]}
            games += 1
            won = me.get("result") == "win"
            wins += won
            g_our = g_their = 0
            for ev in s["events"]:
                if ev["kind"] != "death":
                    continue
                vid = ev["owner"]["id"]
                vname, vteam = names.get(vid, ("?", "?"))
                for e in ev["entries"]:
                    r, x, y = e["timestamp"]["round"], e["x"], e["y"]
                    z = zone(depth(x, y))
                    if vteam != our_team:
                        # Their deaths: zone from our side.
                        their_deaths[z] += 1
                        g_their += 1
                        continue
                    our_deaths[z] += 1
                    g_our += 1
                    killer = e.get("target", {})
                    by_champ = killer.get("kind") == "champion"
                    track = seq.get(vname, {})
                    turns = [track[q] for q in range(r - 40, r + 1) if q in track and track[q]["lab"] != "dead"]
                    contact = None
                    if turns:
                        # Walk back from the death while an enemy stays within 8 (gaps up to 3 turns).
                        last_seen = None
                        for tr in reversed(turns):
                            if tr["ne8"] > 0:
                                last_seen = tr
                                contact = tr
                            elif last_seen is not None and last_seen["r"] - tr["r"] > 3:
                                break
                    pre = turns[-1] if turns else None
                    window = [tr for tr in turns if contact and tr["r"] >= contact["r"]]
                    leave = next((tr for tr in window if tr["lab"] in ("retreat", "disengage", "recalling")), None)
                    fought = [tr for tr in window if tr["lab"] == "combat" and (leave is None or tr["r"] < leave["r"])]
                    rows.append(dict(
                        match=mid, map=m["map"], opp=opp["name"], won=won, champ=vname, round=r, zone=z,
                        by_champ=by_champ, killer=norm(killer.get("name", killer.get("kind", "?"))),
                        gems=pre["gems"] if pre else None,
                        last=pre["lab"] if pre else None,
                        c_lab=contact["lab"] if contact else None,
                        c_hp=contact["hp"] / max(1, contact["mx"]) if contact else None,
                        c_ne8=contact["ne8"] if contact else None,
                        c_na5=contact["na5"] if contact else None,
                        c_dmin=contact["dmin"] if contact else None,
                        c_zone=zone(depth(contact["x"], contact["y"])) if contact else None,
                        live=(r - contact["r"]) if contact else None,
                        labs=" ".join(tr["lab"] for tr in window),
                        ne8max=max((tr["ne8"] for tr in window), default=None),
                        na5max=max((tr["na5"] for tr in window), default=None),
                        hp_leave=(leave["hp"] / max(1, leave["mx"])) if leave else None,
                        leave_lab=leave["lab"] if leave else None,
                        to_leave=(leave["r"] - contact["r"]) if leave else None,
                        leave_to_death=(r - leave["r"]) if leave else None,
                        fought=len(fought),
                    ))
            per_game.append((m["map"], opp["name"], won, g_our, g_their))
    print(f"{games} games, {wins} won")
    print(f"deaths a game by zone (our side's view):")
    print(f"  {'zone':<12}{'ours':>8}{'theirs':>8}")
    for z in ZONES:
        if our_deaths[z] or their_deaths[z]:
            print(f"  {z:<12}{our_deaths[z] / max(1, games):>8.2f}{their_deaths[z] / max(1, games):>8.2f}")
    print(f"  {'total':<12}{sum(our_deaths.values()) / max(1, games):>8.2f}{sum(their_deaths.values()) / max(1, games):>8.2f}")
    home = [x for x in rows if x["zone"] in ("our spawn", "our half") and x["by_champ"]]
    print(f"\nour deaths to champions at home (our spawn + our half): {len(home)}")
    if not home:
        return
    c = collections.Counter(x["c_lab"] for x in home)
    print("  doing at contact:", ", ".join(f"{k} {v}" for k, v in c.most_common()))
    c = collections.Counter(x["last"] for x in home)
    print("  last turn label: ", ", ".join(f"{k} {v}" for k, v in c.most_common()))
    hp = sorted(x["c_hp"] for x in home if x["c_hp"] is not None)
    if hp:
        print(f"  health at contact: median {hp[len(hp) // 2]:.2f}, under 0.5: {sum(h < 0.5 for h in hp)} of {len(hp)}")
    na = collections.Counter(x["c_na5"] for x in home)
    print("  allies within 5 at contact:", ", ".join(f"{k}: {v}" for k, v in sorted(na.items(), key=lambda kv: (kv[0] is None, kv[0]))))
    ne = collections.Counter(x["c_ne8"] for x in home)
    print("  enemies within 8 at contact:", ", ".join(f"{k}: {v}" for k, v in sorted(ne.items(), key=lambda kv: (kv[0] is None, kv[0]))))
    lv = sorted(x["live"] for x in home if x["live"] is not None)
    if lv:
        print(f"  rounds from contact to death: median {lv[len(lv) // 2]}, quartiles {lv[len(lv) // 4]}-{lv[3 * len(lv) // 4]}")
    dm = collections.Counter(x["c_dmin"] for x in home)
    print("  nearest enemy at contact:", ", ".join(f"{k}: {v}" for k, v in sorted(dm.items(), key=lambda kv: (kv[0] is None, kv[0]))))
    def dist(key, label):
        v = sorted(x[key] for x in home if x[key] is not None)
        if v:
            print(f"  {label}: median {v[len(v) // 2]}, quartiles {v[len(v) // 4]}-{v[3 * len(v) // 4]} (n {len(v)})")
    dist("ne8max", "most enemies within 8 before death")
    dist("na5max", "most allies within 5 before death")
    dist("hp_leave", "health when it first left (retreat/disengage/recall)")
    dist("to_leave", "rounds from contact to leaving")
    dist("leave_to_death", "rounds from leaving to death")
    dist("fought", "combat turns before leaving")
    print("  never left before dying:", sum(1 for x in home if x["leave_lab"] is None), "of", len(home))
    print("  victims:", ", ".join(f"{k} {v}" for k, v in collections.Counter(x["champ"] for x in home).most_common()))
    print("  killers:", ", ".join(f"{k} {v}" for k, v in collections.Counter(x["killer"] for x in home).most_common()))
    print("  gems carried:", sum(x["gems"] or 0 for x in home))
    Path("/home/user/runs/diag_rows.json").write_text(json.dumps(rows, indent=0))
    print("\n  sample sequences (contact -> death):")
    for x in home[:25]:
        print(f"   {x['map']:<22}{x['champ']:<13}r{x['round']:<5}hp {x['c_hp'] if x['c_hp'] is None else round(x['c_hp'], 2)} "
              f"allies {x['c_na5']} enemies {x['c_ne8']} d{x['c_dmin']}: {x['labs'][:150]}")


if __name__ == "__main__":
    main(sys.argv[1:])
