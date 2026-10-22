#!/usr/bin/env python3
"""Benchmark a bot against real ladder teams without exposing the ranked rating.

Why this exists
---------------
The local opponents are weaker than the teams either side of us on the ladder. Same
build, same five maps: our gems barely move (472 local, 371 ladder) but the
opponents' go 919 to 1,024, and a record of 8-32 becomes 0-15. Every local
measurement in this project was taken against bots that cannot reach 1,000 gems,
so a change that buys a local win can buy nothing real.

Unranked match groups play the team's *current* submission, so measuring a bot
means making it current for a moment -- and ranked batches fire automatically on a
ten-minute cycle, five matches at a time, which would play the test bot and move
the rating.

The window
----------
Measured over 183 batches: gaps of 8 to 12 minutes, median 10. So the safe moment
is immediately after a batch lands, which leaves at least eight minutes. A submit,
three queued groups, and a restore took 52 seconds. This script refuses to start
unless it can see a batch that landed recently enough to guarantee margin, and it
restores the ranked bot in a `finally` so an exception or a failed queue cannot
leave the test bot live.

It then checks whether a ranked batch landed inside the window anyway, and says so
loudly if one did, because a silent near-miss is how the rating gets spent.

Usage
-----
    ladderbench.py --bot sage2 --tag eff_order
    ladderbench.py --bot sage2 --tag eff_order --opponents 158,156,1
    ladderbench.py --report eff_order
    ladderbench.py --compare old_order eff_order
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WS = ROOT / "ws"
CAMBC = Path.home() / "Library" / "Python" / "3.9" / "bin" / "cambc"
RANKED_BOT = "greatsage"             # restored after every run
RESTORE_REFERENCE = ROOT / "greatsage.zip"
OUR_TEAM = "Milk and Potatoes"
RESULTS = WS / "bench" / "ladder"

# The platform allows 50 unranked matches an hour per team, which the `quota`
# subcommand does not report (it prints the map list instead). That is ten groups
# an hour, so a two-arm comparison across eight opponents -- 80 matches -- takes
# about an hour and a half of wall clock, not one sitting. Plan around it: fewer
# opponents per arm, or fewer maps, or accept the wait.
UNRANKED_PER_HOUR = 50

# From 183 observed batches: min gap 8 min, median 10, max 12.
BATCH_MIN_GAP = timedelta(minutes=8)
SAFETY_MARGIN = timedelta(minutes=4)   # includes the settle wait   # refuse to start with less than this left
DEFAULT_MAPS = "01yellow_brick_road,01islands,00quadrants,00ambush,00lanes"
DEFAULT_SIDES = "a,b,a,b,a"

# Seconds to wait after submitting before queuing, so the groups snapshot the
# bot we just uploaded rather than the previous one.
SETTLE_SECONDS = 25


def cambc(*args: str, check: bool = True, retries: int = 4) -> subprocess.CompletedProcess:
    """Run the CLI, retrying the public API's rate limit.

    A 429 on the third queued group once aborted a run after the first two were
    already queued, which is the worst moment to fail: the test bot is live and the
    results are half-collected.
    """
    env = dict(os.environ)
    env["PATH"] = f"{CAMBC.parent}:{env.get('PATH','')}"
    for attempt in range(retries + 1):
        r = subprocess.run([str(CAMBC), *args], capture_output=True, text=True,
                           env=env, cwd=WS)
        if r.returncode == 0:
            return r
        blob = (r.stderr or "") + (r.stdout or "")
        transient = ("429" in blob or "busy" in blob.lower()
                     or "invalid response" in blob.lower()
                     or "timed out" in blob.lower()
                     or "connection" in blob.lower())
        if transient:
            if attempt < retries:
                wait = 3 * (attempt + 1)
                print(f"  rate limited; retrying in {wait}s")
                time.sleep(wait)
                continue
        if check:
            raise RuntimeError(f"cambc {' '.join(args)} failed:\n{blob}")
        return r
    return r


def ranked_batches(limit: int = 100) -> list[datetime]:
    d = json.loads(cambc("matches", "list", "--team", "me", "--kind", "ranked",
                         "--limit", str(limit), "--json").stdout)
    seen = {m["createdAt"] for m in d.get("matches", [])}
    return sorted(datetime.fromisoformat(t.replace("Z", "+00:00")) for t in seen)


def fingerprint(path: Path) -> tuple[int, int, str]:
    z = zipfile.ZipFile(path)
    h = hashlib.sha256()
    for n in sorted(z.namelist()):
        h.update(n.encode())
        h.update(z.read(n))
    return len(z.namelist()), sum(i.file_size for i in z.infolist()), h.hexdigest()[:20]


def verify_restore_bundle() -> None:
    """Never submit a test bot without a checked copy of the ranked one."""
    fresh = Path("/tmp/_ladderbench_restore.zip")
    if fresh.exists():
        fresh.unlink()
    cambc("bundle", f"bots/{RANKED_BOT}", "--output", str(fresh))
    got = fingerprint(fresh)
    if not RESTORE_REFERENCE.exists():
        print(f"  no reference bundle at {RESTORE_REFERENCE}; using the fresh bundle "
              f"({got[0]} files, {got[1]} bytes, {got[2]})")
        return
    want = fingerprint(RESTORE_REFERENCE)
    if got != want:
        raise RuntimeError(
            f"bots/{RANKED_BOT} does not match {RESTORE_REFERENCE.name}:\n"
            f"  fresh     {got}\n  reference {want}\n"
            "Refusing to submit: the restore would not put back what is live."
        )
    print(f"  restore copy verified: {got[0]} files, {got[1]} bytes, {got[2]}")


def wait_for_window(auto_wait: bool) -> datetime:
    """Return once we are just after a batch, with margin to spare."""
    while True:
        batches = ranked_batches()
        now = datetime.now(timezone.utc)
        last = batches[-1] if batches else None
        if last is None:
            print("  no ranked batches found; proceeding")
            return now
        since = now - last
        left = BATCH_MIN_GAP - since
        if left >= SAFETY_MARGIN:
            print(f"  last batch {since.total_seconds()/60:.1f} min ago, "
                  f"at least {left.total_seconds()/60:.1f} min before the next: safe")
            return last
        nxt = last + BATCH_MIN_GAP
        sleep_for = max(30.0, (nxt - now).total_seconds() + 45)
        if not auto_wait:
            raise SystemExit(
                f"  not in a safe window: last batch {since.total_seconds()/60:.1f} min "
                f"ago, only {max(0.0, left.total_seconds())/60:.1f} min of margin.\n"
                f"  Re-run with --wait to sleep {sleep_for/60:.1f} min for the next gap."
            )
        print(f"  only {max(0.0,left.total_seconds())/60:.1f} min of margin; "
              f"waiting {sleep_for/60:.1f} min for the next batch to land")
        time.sleep(sleep_for)


def team_ids(spec: str) -> list[tuple[str, str, int]]:
    """Accept ranks ('158,1') or team UUIDs, return (name, id, rank)."""
    page, teams = 1, []
    while True:
        d = json.loads(cambc("ladder", "--page", str(page), "--limit", "100",
                             "--json").stdout)
        teams += d.get("teams", [])
        if len(teams) >= d.get("total", 0) or not d.get("teams"):
            break
        page += 1
    by_rank = {t["rank"]: t for t in teams}
    by_id = {t["teamId"]: t for t in teams}
    out = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        if item.isdigit() and int(item) in by_rank:
            t = by_rank[int(item)]
        elif item in by_id:
            t = by_id[item]
        else:
            raise SystemExit(f"  cannot resolve opponent {item!r} as a rank or team id")
        if t["name"] == OUR_TEAM:
            raise SystemExit("  cannot queue a match group against ourselves")
        out.append((t["name"], t["teamId"], t["rank"]))
    return out


def run(bot: str, tag: str, opponents: str, maps: str, sides: str,
        auto_wait: bool) -> int:
    out = RESULTS / tag
    out.mkdir(parents=True, exist_ok=True)
    targets = team_ids(opponents)

    print("checks before anything is submitted:")
    verify_restore_bundle()
    probe = Path(f"/tmp/_ladderbench_{bot}.zip")
    if probe.exists():
        probe.unlink()            # the CLI refuses to overwrite
    cambc("bundle", f"bots/{bot}", "--output", str(probe))
    n, b, h = fingerprint(probe)
    print(f"  {bot} bundles cleanly: {n} files, {b} bytes, {h}")
    for name, _, rank in targets:
        print(f"  opponent: rank {rank:>4}  {name}")

    planned = len(targets) * 5
    if planned > UNRANKED_PER_HOUR:
        print(f"  {planned} matches requested but the limit is {UNRANKED_PER_HOUR} an "
              f"hour; queue at most {UNRANKED_PER_HOUR // 5} opponents per run")
        return 1
    print("waiting for a safe window:")
    wait_for_window(auto_wait)
    before = ranked_batches()
    opened = datetime.now(timezone.utc)
    groups, submitted_version = [], None
    try:
        r = cambc("submit", f"bots/{bot}", "--note",
                  f"ladderbench {tag} - temporary, {RANKED_BOT} restored immediately")
        submitted_version = r.stdout.strip().splitlines()[-1]
        print(f"  submitted: {submitted_version}")
        # A submission is not necessarily the active bot the instant the call
        # returns. Three arms queued immediately after submitting once came back
        # byte-identical across 40 games with different bots and different match
        # ids -- the only reading is that all three played whatever was already
        # live. Match groups snapshot the submission when queued, so the queue has
        # to wait for the new one to land.
        time.sleep(SETTLE_SECONDS)
        print(f"  waited {SETTLE_SECONDS}s for the submission to become active")
        for name, tid, rank in targets:
            g = json.loads(cambc("match-groups", "create", tid, "--maps", maps,
                                 "--sides", sides, "--json").stdout)
            groups.append((name, rank, g["groupId"], tid))
            print(f"  queued 5 unranked against {name} (rank {rank})")
    finally:
        # Always put the ranked bot back, even on an exception or a failed queue.
        # A failed restore is the one outcome that costs the rating, so it gets a
        # bigger budget than anything else and its success is checked, not assumed.
        # Seen in the wild: "platform returned an invalid response", which the 429
        # retry did not cover.
        restored = False
        for attempt in range(8):
            try:
                r = cambc("submit", f"bots/{RANKED_BOT}", "--note",
                          f"{RANKED_BOT} restored by ladderbench", retries=2)
                line = r.stdout.strip().splitlines()[-1]
                if "Submitted bot version" in line:
                    print(f"  restored: {line}")
                    restored = True
                    break
                print(f"  restore attempt {attempt+1} gave an odd reply: {line}")
            except Exception as e:
                print(f"  restore attempt {attempt + 1} failed: {e}")
            time.sleep(5 * (attempt + 1))
        if not restored:
            print(f"\n  *** RESTORE FAILED after 8 attempts.\n"
                  f"  *** The live submission may still be {bot!r}.\n"
                  f"  *** Run this NOW:  cd {WS} && cambc submit bots/{RANKED_BOT}\n",
                  file=sys.stderr)
            raise RuntimeError(f"could not restore {RANKED_BOT}")
    closed = datetime.now(timezone.utc)

    # The groups snapshot the submission when they are QUEUED, not when they run:
    # a run that restored before its matches played still produced the test bot's
    # numbers (19.4 deaths a game, against greatsage's ~6). So the ranked bot goes
    # back immediately and the wait happens afterwards, outside the window.
    print("  waiting for the queued matches to play (ranked bot already restored)")
    deadline = time.time() + 300
    while time.time() < deadline:
        pending = 0
        for *_, gid, _ in groups:
            d = json.loads(cambc("match-groups", "show", gid, "--json").stdout)
            pending += sum(1 for m in d.get("matches", [])
                           if m.get("status") != "finished")
        if pending == 0:
            break
        time.sleep(10)
    print(f"  all {len(groups) * 5} unranked matches finished")

    after = ranked_batches()
    intruders = [t for t in after if t not in before and opened <= t <= closed]
    print(f"  window open {(closed-opened).total_seconds():.0f}s")
    if intruders:
        print("  *** A RANKED BATCH LANDED INSIDE THE WINDOW: "
              + ", ".join(t.isoformat() for t in intruders))
        print("  *** those matches were played by the test bot; the rating moved.")
    else:
        print("  no ranked batch landed inside the window: the rating was not exposed")

    for name, rank, gid, tid in groups:
        (out / f"group_{rank}_{name.replace(' ', '_')}.json").write_text(
            cambc("match-groups", "show", gid, "--json").stdout)
    meta = {"bot": bot, "tag": tag, "opened": opened.isoformat(),
            "closed": closed.isoformat(), "exposed": bool(intruders),
            "groups": [{"opponent": n, "rank": r, "groupId": g, "teamId": i}
                       for n, r, g, i in groups]}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    return report(tag)


def collect(tag: str) -> list[dict]:
    out = RESULTS / tag
    games = []
    for p in sorted(out.glob("group_*.json")):
        d = json.loads(p.read_text())
        for m in d.get("matches", []):
            us = next((t for t in m["teams"] if t["name"] == OUR_TEAM), None)
            th = next((t for t in m["teams"] if t["name"] != OUR_TEAM), None)
            if not us or not th:
                continue
            games.append({"opponent": th["name"], "map": m["map"], "side": us["side"],
                          "win": us["result"] == "win", "matchId": m["matchId"],
                          "end": m.get("endReason")})
    return games


def summaries(tag: str, games: list[dict]) -> list[dict]:
    """Pull per-match statistics; the roster names are the authoritative identities."""
    out = RESULTS / tag / "summaries"
    out.mkdir(exist_ok=True)
    rows = []
    for g in games:
        f = out / f"{g['matchId'][:8]}.json"
        if not f.exists():
            cambc("matches", "summary", g["matchId"], "--json", "-o", str(f),
                  check=False)
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        me = "teamA" if g["side"] == "a" else "teamB"
        them = "teamB" if me == "teamA" else "teamA"
        gems = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        mine = [c for c in d["champions"] if c["team"] == me]
        s = lambda k: sum(float(c["metrics"][k]) for c in mine)
        rows.append(dict(
            g, gems=gems[me], theirs=gems[them],
            rounds=d["match"]["roundsCompleted"],
            collected=s("collectedGems"), deaths=s("deaths"),
            gold=s("earnedGold"), monsterDmg=s("monsterDamageDone"),
            kills=s("kills"),
            roster=[c["name"] for c in d.get("roster", {}).get("champions", [])
                    if c["team"] == me]))
    return rows


def report(tag: str) -> int:
    games = collect(tag)
    if not games:
        print(f"no games recorded under {RESULTS / tag}")
        return 1
    rows = summaries(tag, games)
    meta_path = RESULTS / tag / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    print(f"\n{tag}: {len(rows)} unranked games"
          + (f" (bot {meta['bot']})" if meta.get("bot") else ""))
    if meta.get("exposed"):
        print("  WARNING: a ranked batch landed inside this run's window")
    print("  %-22s%-22s%5s%8s%8s%8s%8s" % ("opponent", "map", "side", "ours",
                                           "theirs", "rounds", "deaths"))
    for r in rows:
        print("  %-22s%-22s%5s%8d%8d%8d%8.0f"
              % (r["opponent"][:21], r["map"][:21], r["side"], r["gems"],
                 r["theirs"], r["rounds"], r["deaths"]))
    n = len(rows)
    w = sum(1 for r in rows if r["win"])
    f = lambda k: sum(r[k] for r in rows) / n
    print("  " + "-" * 84)
    print("  %-50s%8.0f%8.0f%8.0f%8.1f"
          % ("MEAN", f("gems"), f("theirs"), f("rounds"), f("deaths")))
    print(f"  record {w}-{n - w}")
    print("  gems collected %.0f, gold %.0f, damage per gem %.0f, kills %.2f"
          % (f("collected"), f("gold"),
             f("monsterDmg") / f("collected") if f("collected") else 0, f("kills")))
    by = {}
    for r in rows:
        by.setdefault(r["opponent"], []).append(r)
    print("  by opponent:")
    for k, v in sorted(by.items(), key=lambda kv: -sum(x["gems"] for x in kv[1])):
        print("    %-24s%8.0f gems vs %6.0f   %d-%d"
              % (k[:23], sum(x["gems"] for x in v) / len(v),
                 sum(x["theirs"] for x in v) / len(v),
                 sum(1 for x in v if x["win"]), sum(1 for x in v if not x["win"])))
    rosters = {tuple(r["roster"]) for r in rows if r["roster"]}
    for ro in rosters:
        print("  roster fielded: " + ", ".join(ro))
    return 0


def compare(a: str, b: str) -> int:
    ra, rb = summaries(a, collect(a)), summaries(b, collect(b))
    if not ra or not rb:
        print("need results for both tags")
        return 1
    key = lambda r: (r["opponent"], r["map"], r["side"])
    da, db = {key(r): r for r in ra}, {key(r): r for r in rb}
    shared = sorted(set(da) & set(db))
    print(f"\n{b} against {a}: {len(shared)} games played on identical pairings")
    if not shared:
        print("  no overlapping pairings; run both tags with the same opponents and maps")
        return 1
    fields = [("gems", "gems submitted"), ("collected", "gems collected"),
              ("gold", "gold earned"), ("deaths", "deaths"), ("theirs", "opponent gems"),
              ("rounds", "rounds")]
    print("  %-22s%12s%12s%10s" % ("metric", a[:11], b[:11], "change"))
    for f, lab in fields:
        va = sum(da[k][f] for k in shared) / len(shared)
        vb = sum(db[k][f] for k in shared) / len(shared)
        print("  %-22s%12.1f%12.1f%+10.1f" % (lab, va, vb, vb - va))
    wa = sum(1 for k in shared if da[k]["win"])
    wb = sum(1 for k in shared if db[k]["win"])
    print("  %-22s%12s%12s" % ("record", f"{wa}-{len(shared)-wa}",
                               f"{wb}-{len(shared)-wb}"))
    better = sum(1 for k in shared if db[k]["gems"] > da[k]["gems"])
    worse = sum(1 for k in shared if db[k]["gems"] < da[k]["gems"])
    print("  per-game gems: %d better, %d worse, %d same"
          % (better, worse, len(shared) - better - worse))

    # The breakdown, printed before anyone is tempted to trust the mean. A +246
    # per-map average once turned out to be one game against one opponent, and the
    # mean gave no hint of it. If a row's sign is not consistent across opponents,
    # the effect belongs to the matchup and not to the map.
    maps = sorted({k[1] for k in shared})
    opps = sorted({k[0] for k in shared})
    if len(maps) > 1 or len(opps) > 1:
        print()
        print("  gem delta per map per opponent (the mean hides outliers):")
        head = "    %-22s" % "map" + "".join("%11s" % o[:10] for o in opps) + "%10s" % "row"
        print(head)
        for m in maps:
            cells, tot, n = "", 0.0, 0
            for o in opps:
                ks = [k for k in shared if k[1] == m and k[0] == o]
                if not ks:
                    cells += "%11s" % "-"
                    continue
                d = sum(db[k]["gems"] - da[k]["gems"] for k in ks) / len(ks)
                tot += d
                n += 1
                cells += "%+11.0f" % d
            print("    %-22s%s%+10.0f" % (m[:21], cells, tot / n if n else 0))
        print()
        for m in maps:
            ds = []
            for o in opps:
                ks = [k for k in shared if k[1] == m and k[0] == o]
                if ks:
                    ds.append(sum(db[k]["gems"] - da[k]["gems"] for k in ks) / len(ks))
            if len(ds) < 2:
                continue
            pos = sum(1 for d in ds if d > 0)
            # The rule fixed before the data: a map earns an entry only if the sign
            # holds for at least three quarters of opponents. Anything short of that
            # is a matchup effect wearing a map's clothes.
            share = max(pos, len(ds) - pos) / len(ds)
            if share >= 0.75 and len(ds) >= 4:
                verdict = "CONSISTENT -- %s" % ("apply" if pos > len(ds) - pos
                                                else "withhold")
            else:
                verdict = "split -- opponent-dependent, not a map property"
            print("    %-22s %d of %d opponents positive   %s"
                  % (m[:21], pos, len(ds), verdict))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot")
    ap.add_argument("--tag")
    ap.add_argument("--opponents", default="158,156,1",
                    help="ladder ranks or team UUIDs, comma separated")
    ap.add_argument("--same-as", metavar="TAG",
                    help="reuse the exact opponents a previous run used, by team id; "
                         "ranks drift between runs and would silently change the "
                         "comparison")
    ap.add_argument("--maps", default=DEFAULT_MAPS)
    ap.add_argument("--sides", default=DEFAULT_SIDES)
    ap.add_argument("--wait", action="store_true",
                    help="sleep until a safe window instead of refusing")
    ap.add_argument("--report", metavar="TAG")
    ap.add_argument("--compare", nargs=2, metavar=("TAG_A", "TAG_B"))
    a = ap.parse_args()
    if a.compare:
        return compare(*a.compare)
    if a.report:
        return report(a.report)
    if not a.bot or not a.tag:
        ap.error("--bot and --tag are required unless --report or --compare is used")
    opponents = a.opponents
    if a.same_as:
        prev = RESULTS / a.same_as / "meta.json"
        if not prev.exists():
            ap.error(f"no meta.json for --same-as {a.same_as}")
        ids = [g["teamId"] for g in json.loads(prev.read_text())["groups"]
               if g.get("teamId")]
        if not ids:
            ap.error(f"{a.same_as} recorded no team ids; re-run it to pin opponents")
        opponents = ",".join(ids)
        print(f"  reusing {a.same_as}'s opponents by team id")
    return run(a.bot, a.tag, opponents, a.maps, a.sides, a.wait)


if __name__ == "__main__":
    sys.exit(main())
