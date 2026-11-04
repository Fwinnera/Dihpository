#!/usr/bin/env python3
"""Evolution-strategies tuner for the bot's decision constants (level 1 of docs/RL-PLAN.md).

The policy is the twenty numbers in PARAMS: fifteen config.h constants of ab3_submit and
five literals that `es.py base` turns into constants (the engage range and odds in
combat::choose_enemy, the early and late gold weights in strategy::choose_group, the shield
threshold in combat::fight). Each is scaled to [0, 1] over its range, and a separable
CMA-ES (Ros and Hansen 2008: diagonal covariance, cumulative step-size adaptation, pure
Python) searches that cube.

A generation samples LAM vectors, writes one bot per vector (ws/bots/es_RUN_gNN_cKK, a copy
of ws/bots/es_base with config.h set by analysis/rebuild/mkparam.py) and one for the current
mean (es_RUN_gNN_m), and plays them all on one shared draw of games: against every league
opponent, MAPS maps from both sides, the maps walking through a fixed per-opponent shuffle
so consecutive generations see different maps. Every candidate is ranked on the same
games. es_base, whose wasm is byte-identical to ab3_submit's, is read from the full-league
sweep under BASE_TAG (the engine is deterministic), so each generation also reports the
mean's paired fitness against ab3 at no extra cost.

Game fitness: our submitted gems minus theirs, plus WIN_BONUS when the engine outcome is
ours (a draw goes to the side that earned more gold). A candidate's fitness is its mean
over the generation's games; each opponent has the same number of games, so each counts
equally. The league is deliberately not only our own code (docs/RL-PLAN.md, "The trap").

Usage, from the repository root (at most 8 jobs while other screens run)
-----
    es.py base [--check]           create ws/bots/es_base from ab3_submit with the five new
                                   constants, or check an existing one; either way its
                                   release wasm must be byte-identical to ab3_submit's
    es.py league BOT --tag TAG     BOT against all twelve league opponents, every map, both
                                   sides (bench.py), summaries gzipped, then scored
    es.py run --run NAME [--gens N] [--until HH:MM] [--lam 16] [--maps 3] [--sigma 0.15]
              [--cm C] [--freeze] [--recentre] [--why TEXT]
                                   start or resume a run; state and logs in ws/bench/es/NAME/
                                   (--until is UTC: no generation starts that would end later).
                                   On resume, --cm 0 --freeze --recentre turns the run into
                                   sampling one fixed distribution around ab3, for `grad`
    es.py show --run NAME          one line a generation
    es.py grad --run NAME [--quad] each constant's fitness slope (and curvature), pooled over
                                   every candidate of the run, centred within generations
    es.py apply BOT --run NAME [--which mean|avg|gen:N|grad:T:S]
                                   write ws/bots/BOT (an es_* name) with that vector: the
                                   final mean, the mean averaged over the second half of the
                                   run, the mean after generation N, or ab3 moved S of the
                                   range (default 0.1) along each pooled slope with |t| >= T
    es.py score TAG [BASE_TAG]     fitness by opponent of a bench.py tag (json or json.gz);
                                   with a second tag, the paired difference game by game

Candidate bot folders are deleted after their generation (the vectors are in the log and
`apply` rebuilds any of them); replays and the candidates' raw summaries are deleted, the
mean's summaries are gzipped, and one compact line a game goes to games.jsonl.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import filecmp
import gzip
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WS = ROOT / "ws"
BOTS = WS / "bots"
BENCH = WS / "bench"
ES = BENCH / "es"
CAMBC = Path.home() / "Library" / "Python" / "3.9" / "bin" / "cambc"
MKPARAM = ROOT / "analysis" / "rebuild" / "mkparam.py"
SOURCE = "ab3_submit"
BASE = "es_base"
BASE_TAG = "es_league_base"
LEAGUE = ["cHG_submit", "rl_submit", "sh_submit", "gs_mix_camp", "gs_eq", "b_tbd", "next_trial",
          "f_hor_h", "f_tavi_n", "dH_submit", "sgA_submit", "d1"]
# ES_LEAGUE=a,b,c replaces the league for every command (run r2 uses the opponents whose local
# verdicts predict the ladder lab: analysis/rebuild/labpredict.py). They must be in the base sweep.
if os.environ.get("ES_LEAGUE"):
    LEAGUE = [o for o in os.environ["ES_LEAGUE"].split(",") if o]
WIN_BONUS = 200.0

# (name, ab3's value, low, high, integer)
PARAMS = [
    ("BANK_GEMS", 24, 12, 40, True),
    ("RETREAT_HEALTH", 0.30, 0.12, 0.50, False),
    ("CARRIER_RETREAT_HEALTH", 0.43, 0.25, 0.65, False),
    ("HEAL_RECALL", 0.60, 0.35, 0.85, False),
    ("SHOP_GOLD", 150, 60, 320, True),
    ("SHOP_INTERVAL", 70, 20, 200, True),
    ("DISENGAGE_RATIO", 0.5, 0.2, 1.0, False),
    ("DISENGAGE_HYSTERESIS", 0.2, 0.0, 0.6, False),
    ("DISENGAGE_RADIUS", 5, 3, 8, True),
    ("JOIN_ALPHA", 0.5, 0.0, 1.2, False),
    ("DMG_COST", 50, 0, 150, False),
    ("JOIN_SLACK", 8, 2, 16, True),
    ("ROLE_NEAR", 3, 1, 7, True),
    ("FAT_BAG", 40, 20, 80, True),
    ("RAID_ROUND", 900, 400, 1500, True),
    ("ENGAGE_RANGE", 4, 2, 6, True),
    ("ENGAGE_ODDS", 1.15, 0.7, 2.0, False),
    ("GOLD_EARLY", 1.0, 0.3, 2.0, False),
    ("GOLD_LATE", 0.25, 0.0, 1.0, False),
    ("SHIELD_HP", 0.95, 0.5, 1.0, False),
]
SIGMA_RANGE = (0.03, 0.35)
VAR_RANGE = (0.0625, 4.0)  # diagonal of C: a coordinate's step is a quarter to twice sigma's

# ---------------------------------------------------------------- vectors and bots


def default_u() -> list[float]:
    return [(d - lo) / (hi - lo) for _, d, lo, hi, _ in PARAMS]


def values(u: list[float]) -> dict:
    out = {}
    for (name, _, lo, hi, integer), x in zip(PARAMS, u):
        v = lo + (hi - lo) * min(1.0, max(0.0, x))
        out[name] = int(round(v)) if integer else round(v, 3)
    return out


def reflect(x: float) -> float:
    x %= 2.0
    return 2.0 - x if x > 1.0 else x


def env() -> dict:
    e = dict(os.environ)
    e["PATH"] = f"{CAMBC.parent}:{e.get('PATH', '')}"
    return e


def make_bot(name: str, vals: dict) -> None:
    dst = BOTS / name
    if not name.startswith("es_") or dst.parent != BOTS or name == BASE:
        sys.exit(f"refusing to write {dst}")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(BOTS / BASE / "src", dst / "src")
    r = subprocess.run([sys.executable, "-I", str(MKPARAM), str(dst)] + [f"{k}={v}" for k, v in vals.items()],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"mkparam failed for {name}: {r.stderr or r.stdout}")


def remove_bot(name: str) -> None:
    dst = BOTS / name
    if name.startswith("es_") and name != BASE and dst.parent == BOTS and dst.exists():
        shutil.rmtree(dst)


def build(name: str) -> str | None:
    r = subprocess.run([str(CAMBC), "build", "--release", f"bots/{name}"], cwd=WS, env=env(),
                       capture_output=True, text=True)
    return None if r.returncode == 0 else f"{name}: {(r.stdout + r.stderr)[-1500:]}"


def build_all(names: list[str], jobs: int) -> None:
    with cf.ThreadPoolExecutor(max_workers=jobs) as pool:
        errors = [e for e in pool.map(build, names) if e]
    if errors:
        sys.exit("build failed:\n" + "\n".join(errors))


def base_sources(dst: Path) -> None:
    """ab3_submit's src with the five literals the tuner needs as config.h constants."""
    shutil.copytree(BOTS / SOURCE / "src", dst)

    def sub(path: str, old: str, new: str) -> None:
        p = dst / path
        t = p.read_text()
        if t.count(old) != 1:
            sys.exit(f"{path}: expected one '{old[:60]}...', found {t.count(old)}")
        p.write_text(t.replace(old, new))

    sub("combat.h", "if (!(killable || interrupt || defending || gap <= 4 || allied_power > enemy_power * 1.15)) continue;",
        "if (!(killable || interrupt || defending || gap <= config::ENGAGE_RANGE ||\n"
        "              allied_power > enemy_power * config::ENGAGE_ODDS))\n            continue;")
    sub("combat.h", "if (gap > 4 && !(killable || interrupt || allied_power > enemy_power * 1.15)) continue;",
        "if (gap > config::ENGAGE_RANGE && !(killable || interrupt || allied_power > enemy_power * config::ENGAGE_ODDS)) continue;")
    sub("combat.h", "if (incoming && D(me.health()) < D(me.max_health()) * 0.95 && distance(me.position(), position) <= 4)",
        "if (incoming && D(me.health()) < D(me.max_health()) * config::SHIELD_HP && distance(me.position(), position) <= 4)")
    sub("strategy.h", "objective->gold * (now < 500 ? 1.0 : 0.25);",
        "objective->gold * (now < 500 ? config::GOLD_EARLY : config::GOLD_LATE);")
    sub("config.h", "inline constexpr int JOIN_SLACK = 8;\n",
        "inline constexpr int JOIN_SLACK = 8;\n"
        "// Exposed for the evolution-strategies tuner (analysis/rl/es.py); the defaults are the\n"
        "// literals they replace. combat::choose_enemy engages any enemy within ENGAGE_RANGE, and\n"
        "// one further out only when our local health-times-strength beats theirs by ENGAGE_ODDS.\n"
        "inline constexpr int ENGAGE_RANGE = 4;\n"
        "inline constexpr double ENGAGE_ODDS = 1.15;\n"
        "// strategy::choose_group values a camp's gold at GOLD_EARLY gems before round 500 and\n"
        "// GOLD_LATE after.\n"
        "inline constexpr double GOLD_EARLY = 1.0;\n"
        "inline constexpr double GOLD_LATE = 0.25;\n"
        "// combat::fight raises a self-shield once health is below SHIELD_HP of its maximum.\n"
        "inline constexpr double SHIELD_HP = 0.95;\n")


def cmd_base(a) -> int:
    dst = BOTS / BASE
    with tempfile.TemporaryDirectory() as tmp:
        want = Path(tmp) / "src"
        base_sources(want)
        if dst.exists():
            cmp = filecmp.dircmp(want, dst / "src")
            if cmp.diff_files or cmp.left_only or cmp.right_only:
                sys.exit(f"{dst} differs from a fresh build: {cmp.diff_files + cmp.left_only + cmp.right_only}")
            print(f"{dst}/src matches ab3_submit plus the five constants")
        elif a.check:
            sys.exit(f"{dst} does not exist")
        else:
            dst.mkdir()
            shutil.copytree(want, dst / "src")
            print(f"wrote {dst}")
    err = build(BASE)
    if err:
        sys.exit(err)
    ours, theirs = (BOTS / b / ".cambc/build-release/bot.wasm" for b in (BASE, SOURCE))
    if not theirs.exists():
        sys.exit(f"{theirs} missing: build {SOURCE} first")
    if not filecmp.cmp(ours, theirs, shallow=False):
        sys.exit(f"{ours} is not byte-identical to {theirs}")
    print(f"release wasm byte-identical to {SOURCE}'s ({ours.stat().st_size} bytes)")
    return 0

# ---------------------------------------------------------------- games and fitness


def record(path: Path, side: str) -> dict:
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    d = json.loads(raw)
    me, them = ("teamA", "teamB") if side == "A" else ("teamB", "teamA")
    gems = {t["team"]: float(t["submittedGems"]) for t in d["teams"]}
    gold = {me: 0.0, them: 0.0}
    deaths = {me: 0.0, them: 0.0}
    for c in d["champions"]:
        gold[c["team"]] += float(c["metrics"]["earnedGold"])
        deaths[c["team"]] += float(c["metrics"]["deaths"])
    outcome = d["match"]["outcome"]
    if outcome == me:
        win = 1.0
    elif outcome == them:
        win = 0.0
    else:
        win = 1.0 if gold[me] > gold[them] else 0.0 if gold[me] < gold[them] else 0.5
    margin = gems.get(me, 0.0) - gems.get(them, 0.0)
    return {"margin": margin, "win": win, "fit": margin + WIN_BONUS * win,
            "gems": gems.get(me, 0.0), "opp_gems": gems.get(them, 0.0),
            "gold": gold[me], "opp_gold": gold[them], "deaths": deaths[me], "opp_deaths": deaths[them],
            "faults": int(d.get("diagnostics", {}).get("botFaults", {}).get(me, 0)),
            "rounds": int(d["match"].get("roundsCompleted", 0))}


def finish_game(path_str: str, side: str, keep: bool) -> dict | None:
    """Read one ES game, then gzip its summary (keep) or delete it; the replay always goes."""
    p = Path(path_str)
    replay = p.with_suffix(".repl26a")
    rec = None
    if p.exists():
        try:
            rec = record(p, side)
        except (ValueError, KeyError) as e:
            print(f"  unreadable {p.name}: {e}", flush=True)
        if keep:
            Path(path_str + ".gz").write_bytes(gzip.compress(p.read_bytes(), 6))
        p.unlink()
    if replay.exists():
        replay.unlink()
    return rec


def read_tag(folder: Path) -> dict:
    """(opp, map, side) -> record for a bench.py tag folder, summaries plain or gzipped."""
    out = {}
    for p in sorted(folder.glob("*__*__*.json*")):
        stem = p.name.split(".json")[0]
        opp, mapname, side = stem.split("__")
        out[(opp, mapname, side)] = record(p, side)
    return out


def all_maps() -> list[str]:
    return sorted(m.stem for m in WS.glob("maps/*.map26a"))


def draw(run: str, gen: int, k: int) -> list[tuple[str, str, str]]:
    """This generation's games: k maps an opponent from its own fixed shuffle, both sides."""
    maps = all_maps()
    games = []
    for opp in LEAGUE:
        order = maps[:]
        random.Random(f"{run}:maps:{opp}").shuffle(order)
        for j in range(k):
            m = order[(gen * k + j) % len(order)]
            games += [(opp, m, "A"), (opp, m, "B")]
    return games


def summarise(recs: list[dict]) -> dict:
    n = len(recs)
    if not n:
        return {"n": 0}
    mean = lambda f: sum(r[f] for r in recs) / n
    return {"n": n, "fit": mean("fit"), "margin": mean("margin"), "win": mean("win"), "gold": mean("gold"),
            "deaths": mean("deaths"), "faults": sum(r["faults"] for r in recs)}


def paired(a: dict, b: dict, field: str = "fit") -> tuple[float, float, int]:
    """Mean and standard error of a - b over the games both have."""
    keys = [k for k in a if k in b]
    if len(keys) < 2:
        return 0.0, 0.0, len(keys)
    d = [a[k][field] - b[k][field] for k in keys]
    m = sum(d) / len(d)
    var = sum((x - m) ** 2 for x in d) / (len(d) - 1)
    return m, math.sqrt(var / len(d)), len(keys)

# ---------------------------------------------------------------- separable CMA-ES


def strategy(n: int, lam: int) -> dict:
    mu = lam // 2
    w = [math.log(mu + 0.5) - math.log(i + 1) for i in range(mu)]
    s = sum(w)
    w = [x / s for x in w]
    mueff = 1.0 / sum(x * x for x in w)
    cs = (mueff + 2) / (n + mueff + 5)
    ds = 1 + 2 * max(0.0, math.sqrt((mueff - 1) / (n + 1)) - 1) + cs
    cc = (4 + mueff / n) / (n + 4 + 2 * mueff / n)
    c1 = 2 / ((n + 1.3) ** 2 + mueff)
    cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((n + 2) ** 2 + mueff))
    scale = (n + 2) / 3.0  # the separable variant learns a diagonal this much faster
    c1s = c1 * scale
    cmus = min(1 - c1s, cmu * scale)
    chin = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n * n))
    return {"mu": mu, "w": w, "mueff": mueff, "cs": cs, "ds": ds, "cc": cc, "c1": c1s, "cmu": cmus, "chin": chin}


def sample(state: dict) -> list[list[float]]:
    rng = random.Random(f"{state['run']}:{state['gen']}")
    m, s, C = state["mean"], state["sigma"], state["C"]
    out = []
    for _ in range(state["lam"]):
        out.append([reflect(m[i] + s * math.sqrt(C[i]) * rng.gauss(0.0, 1.0)) for i in range(len(m))])
    return out


def update(state: dict, ranked: list[list[float]]) -> None:
    """One sep-CMA-ES step from the candidates, best first (repaired points, Lamarckian)."""
    n, g = len(state["mean"]), state["gen"]
    p = strategy(n, state["lam"])
    m, s, C, ps, pc = state["mean"], state["sigma"], state["C"], state["ps"], state["pc"]
    ys = [[(x[i] - m[i]) / s for i in range(n)] for x in ranked[:p["mu"]]]
    yw = [sum(p["w"][k] * ys[k][i] for k in range(p["mu"])) for i in range(n)]
    cs, cc, mueff = p["cs"], p["cc"], p["mueff"]
    ps = [(1 - cs) * ps[i] + math.sqrt(cs * (2 - cs) * mueff) * yw[i] / math.sqrt(C[i]) for i in range(n)]
    norm = math.sqrt(sum(x * x for x in ps))
    hsig = norm / math.sqrt(1 - (1 - cs) ** (2 * (g + 1))) / p["chin"] < 1.4 + 2 / (n + 1)
    pc = [(1 - cc) * pc[i] + (math.sqrt(cc * (2 - cc) * mueff) * yw[i] if hsig else 0.0) for i in range(n)]
    c1, cmu = p["c1"], p["cmu"]
    C = [(1 - c1 - cmu) * C[i]
         + c1 * (pc[i] ** 2 + (0.0 if hsig else cc * (2 - cc) * C[i]))
         + cmu * sum(p["w"][k] * ys[k][i] ** 2 for k in range(p["mu"]))
         for i in range(n)]
    state["mean"] = [min(1.0, max(0.0, m[i] + state["cm"] * s * yw[i])) for i in range(n)]
    state["ps"], state["pc"] = ps, pc
    # adapt false freezes sigma and C: with cm 0 the run then samples one fixed
    # distribution, the design `slopes` reads most cleanly (an OpenAI-ES style estimate).
    if state.get("adapt", True):
        state["C"] = [min(VAR_RANGE[1], max(VAR_RANGE[0], c)) for c in C]
        state["sigma"] = min(SIGMA_RANGE[1], max(SIGMA_RANGE[0], s * math.exp((cs / p["ds"]) * (norm / p["chin"] - 1))))

# ---------------------------------------------------------------- one generation


def generation(state: dict, a, base: dict, out: Path) -> dict:
    run, g = state["run"], state["gen"]
    started = time.time()
    xs = sample(state)
    bots = {f"es_{run}_g{g:02d}_c{k:02d}": x for k, x in enumerate(xs)}
    center = f"es_{run}_g{g:02d}_m"
    # A mean that is ab3's vector plays exactly es_base's games (checked in generation 0),
    # so after the first generation it is read from the cache instead of replayed.
    center_is_base = g > 0 and values(state["mean"]) == values(default_u())
    if not center_is_base:
        bots[center] = state["mean"]
    for name, x in bots.items():
        make_bot(name, values(x))
    build_all(list(bots), a.jobs)
    t_build = time.time() - started

    games = draw(run, g, state["maps"])
    folder = out / f"g{g:02d}"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    rows = [(b, gm) for b in bots for gm in games]
    # Base games the full-league sweep lacks, plus one an opponent already there in
    # generation 0 to confirm that a replay of es_base reproduces the stored result exactly.
    check, seen = [], set()
    for gm in games:
        if g == 0 and gm in base and gm[0] not in seen:
            seen.add(gm[0])
            check.append(gm)
    rows += [(BASE, gm) for gm in games if gm not in base or gm in check]
    lines = []
    for b, (opp, m, side) in rows:
        x, y = (b, opp) if side == "A" else (opp, b)
        stem = f"{b}__{opp}__{m}__{side}"
        lines.append(f"{BOTS}/{x} {BOTS}/{y} {WS}/maps/{m}.map26a {folder}/{stem}.repl26a "
                     f"--statistics {folder}/{stem}.json")
    manifest = folder / "manifest.txt"
    manifest.write_text("\n".join(lines) + "\n")
    print(f"g{g:02d}: {len(bots)} bots x {len(games)} games = {len(lines)} games "
          f"(built in {t_build:.0f}s)", flush=True)
    with (folder / "run.log").open("w") as log:
        subprocess.run([str(CAMBC), "run-batch", "--release", "--json", "--jobs", str(a.jobs),
                        "--timeout", "300", str(manifest)], cwd=WS, env=env(), stdout=log, stderr=log)
    t_play = time.time() - started - t_build

    jobs = []
    with cf.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        for b, gm in rows:
            stem = f"{b}__{gm[0]}__{gm[1]}__{gm[2]}"
            jobs.append((b, gm, pool.submit(finish_game, str(folder / f"{stem}.json"), gm[2], b == center)))
        results = {}
        for b, gm, fut in jobs:
            rec = fut.result()
            if rec is not None:
                results.setdefault(b, {})[gm] = rec
    for name in bots:
        remove_bot(name)

    mism = 0
    for gm, rec in results.get(BASE, {}).items():
        if gm in base and (base[gm]["margin"], base[gm]["win"]) != (rec["margin"], rec["win"]):
            mism += 1
        base[gm] = rec
    with (out / "games.jsonl").open("a") as f:
        for b, recs in results.items():
            for (opp, m, side), r in recs.items():
                f.write(json.dumps({"gen": g, "bot": b, "opp": opp, "map": m, "side": side, **r}) + "\n")

    # Rank on the games every candidate finished; a candidate missing more than a tenth
    # of them ranks last.
    names = [k for k in bots if k != center]
    common = [gm for gm in games if all(gm in results.get(b, {}) for b in names)]
    fits = {}
    for b in names:
        have = results.get(b, {})
        fits[b] = (sum(have[gm]["fit"] for gm in common) / max(1, len(common))
                   if len(have) >= 0.9 * len(games) else -1e9)
    order = sorted(names, key=lambda b: -fits[b])
    base_g = {gm: base[gm] for gm in games if gm in base}
    base_fit = sum(base_g[gm]["fit"] for gm in common if gm in base_g) / max(1, sum(gm in base_g for gm in common))
    ctr = dict(base_g) if center_is_base else results.get(center, {})
    d_fit, se_fit, n_pair = paired(ctr, base_g)
    d_margin = paired(ctr, base_g, "margin")[0]
    d_win = paired(ctr, base_g, "win")[0]
    by_opp = {}
    for opp in LEAGUE:
        c = {gm: r for gm, r in ctr.items() if gm[0] == opp}
        by_opp[opp] = round(paired(c, base_g)[0], 1)

    old_mean = state["mean"][:]
    update(state, [bots[b] for b in order])
    state["gen"] += 1
    state["means"].append(state["mean"][:])
    duration = time.time() - started
    entry = {
        "gen": g, "utc": dt.datetime.utcnow().strftime("%H:%M"), "minutes": round(duration / 60, 2),
        "build_s": round(t_build), "play_s": round(t_play), "games": len(lines), "common": len(common),
        "missing": {b: len(games) - len(results.get(b, {})) for b in bots if len(results.get(b, {})) < len(games)},
        "base_replay_mismatches": mism, "base_checked": len(check),
        "sigma_before": round(state["sigma_history"][-1], 4), "sigma_after": round(state["sigma"], 4),
        "fit_minus_base": {b: round(fits[b] - base_fit, 1) for b in order},
        "center_minus_base": {"fit": round(d_fit, 1), "se": round(se_fit, 1), "n": n_pair,
                              "margin": round(d_margin, 1), "win": round(d_win, 4), "by_opp": by_opp},
        "center": summarise(list(ctr.values())), "base": summarise([base_g[gm] for gm in ctr if gm in base_g]),
        "faults": {b: sum(r["faults"] for r in results.get(b, {}).values()) for b in bots},
        "mean_before": values(old_mean), "mean_after": values(state["mean"]),
        "candidates": {b: values(bots[b]) for b in order},
    }
    state["sigma_history"].append(state["sigma"])
    state["durations"].append(duration)
    with (out / "log.jsonl").open("a") as f:
        f.write(json.dumps(entry) + "\n")
    fit_sorted = [fits[b] - base_fit for b in order]
    line = (f"g{g:02d} {entry['utc']} {entry['minutes']:.1f}m  sigma {entry['sigma_before']:.3f}->{entry['sigma_after']:.3f}"
            f"  candidates-base best {fit_sorted[0]:+.0f} median {fit_sorted[len(order) // 2]:+.0f} worst {fit_sorted[-1]:+.0f}"
            f"  | mean-base fit {d_fit:+.1f} (se {se_fit:.1f}, n {n_pair}) margin {d_margin:+.1f} wins {100 * d_win:+.1f}%"
            f"  faults {sum(entry['faults'].values())}"
            + (f"  REPLAY MISMATCH {mism}/{len(check)}" if mism else "")
            + (f"  missing {entry['missing']}" if entry["missing"] else ""))
    with (out / "es.log").open("a") as f:
        f.write(line + "\n" + "    mean " + fmt(state["mean"]) + "\n")
    print(line, flush=True)
    return entry


def fmt(u: list[float]) -> str:
    return " ".join(f"{k}={v}" for k, v in values(u).items())


def load_state(out: Path) -> dict | None:
    p = out / "state.json"
    return json.loads(p.read_text()) if p.exists() else None


def save_state(out: Path, state: dict) -> None:
    tmp = out / "state.json.tmp"
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(out / "state.json")


def cmd_run(a) -> int:
    assert values(default_u()) == {p[0]: p[1] for p in PARAMS}, "PARAMS defaults do not round-trip"
    out = ES / a.run
    out.mkdir(parents=True, exist_ok=True)
    state = load_state(out)
    if state is None:
        n = len(PARAMS)
        cm = 1.0 if a.cm is None else a.cm
        state = {"run": a.run, "gen": 0, "lam": a.lam, "maps": a.maps, "cm": cm, "mean": default_u(),
                 "sigma": a.sigma, "C": [1.0] * n, "ps": [0.0] * n, "pc": [0.0] * n,
                 "means": [default_u()], "sigma_history": [a.sigma], "durations": []}
        save_state(out, state)
        with (out / "es.log").open("a") as f:
            f.write(f"# run {a.run}: lam {a.lam}, {a.maps} maps an opponent from both sides, sigma0 {a.sigma}, "
                    f"cm {cm}, league {','.join(LEAGUE)}, win bonus {WIN_BONUS:.0f}\n    mean {fmt(state['mean'])}\n")
    # A resumed run can change course from the next generation on.
    notes = []
    if a.cm is not None and a.cm != state["cm"]:
        state["cm"] = a.cm
        notes.append(f"cm {a.cm}")
    if a.freeze and state.get("adapt", True):
        state["adapt"] = False
        notes.append(f"sigma ({state['sigma']:.3f}) and C frozen")
    if a.recentre:
        state["mean"] = default_u()
        state["ps"] = [0.0] * len(PARAMS)
        state["pc"] = [0.0] * len(PARAMS)
        notes.append("mean reset to ab3")
    if notes:
        save_state(out, state)
        with (out / "es.log").open("a") as f:
            f.write(f"# from g{state['gen']:02d}: {', '.join(notes)}" + (f" ({a.why})" if a.why else "") + "\n")
    base_dir = BENCH / BASE_TAG
    base = read_tag(base_dir) if base_dir.exists() else {}
    print(f"run {a.run}: generation {state['gen']}, {len(base)} es_base games cached from {BASE_TAG}", flush=True)
    stop_at = None
    if a.until:
        hh, mm = (int(x) for x in a.until.split(":"))
        now = dt.datetime.utcnow()
        stop_at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if stop_at < now:
            stop_at += dt.timedelta(days=1)
    done = 0
    while a.gens is None or done < a.gens:
        if stop_at:
            guess = state["durations"][-1] if state["durations"] else 600.0
            if dt.datetime.utcnow() + dt.timedelta(seconds=guess) > stop_at:
                print(f"stopping: generation {state['gen']} would end after {a.until}Z", flush=True)
                break
        if shutil.disk_usage(BENCH).free < 8 * 2**30:
            print("stopping: less than 8 GB free", flush=True)
            break
        generation(state, a, base, out)
        save_state(out, state)
        done += 1
    print(f"run {a.run}: {state['gen']} generations; final mean {fmt(state['mean'])}", flush=True)
    return 0

# ---------------------------------------------------------------- reading results


def vector(state: dict, which: str) -> list[float]:
    means = state["means"]  # means[0] is ab3; means[g] is the mean after generation g
    if which == "mean":
        return means[-1]
    if which == "avg":
        half = means[(len(means) - 1) // 2 + 1:] or means[-1:]
        return [sum(m[i] for m in half) / len(half) for i in range(len(PARAMS))]
    if which.startswith("gen:"):
        return means[int(which[4:])]
    if which.startswith("grad"):
        # grad:T:S is ab3 moved S of the range (default a tenth) up or down each constant
        # whose pooled slope clears T standard errors (default 2.5): inside the region the
        # run sampled.
        parts = which.split(":")
        t = float(parts[1]) if len(parts) > 1 else 2.5
        step = float(parts[2]) if len(parts) > 2 else 0.1
        b, se, *_ = slopes(state["run"])
        u = means[0][:]
        for i in range(len(PARAMS)):
            if se[i] and abs(b[i] / se[i]) >= t:
                u[i] = min(1.0, max(0.0, u[i] + (step if b[i] > 0 else -step)))
        return u
    sys.exit(f"unknown --which {which}")


def cmd_show(a) -> int:
    out = ES / a.run
    rows = [json.loads(x) for x in (out / "log.jsonl").read_text().splitlines()] if (out / "log.jsonl").exists() else []
    tot, n = 0.0, 0
    print(f"{'gen':>4} {'utc':>6} {'min':>5} {'sigma':>6} {'best':>6} {'med':>6} {'mean-base':>10} {'se':>5} "
          f"{'margin':>7} {'wins%':>6} {'running':>8}")
    for r in rows:
        f = list(r["fit_minus_base"].values())
        c = r["center_minus_base"]
        if r["gen"] > 0 and not c["se"]:  # the mean was ab3's vector, read from the cache
            print(f"{r['gen']:>4} {r['utc']:>6} {r['minutes']:>5.1f} {r['sigma_after']:>6.3f} {f[0]:>+6.0f} "
                  f"{f[len(f) // 2]:>+6.0f} {'(mean is ab3)':>40}")
            continue
        tot += c["fit"] * c["n"]
        n += c["n"]
        print(f"{r['gen']:>4} {r['utc']:>6} {r['minutes']:>5.1f} {r['sigma_after']:>6.3f} {f[0]:>+6.0f} {f[len(f) // 2]:>+6.0f} "
              f"{c['fit']:>+10.1f} {c['se']:>5.1f} {c['margin']:>+7.1f} {100 * c['win']:>+6.1f} {tot / max(1, n):>+8.1f}")
    state = load_state(out)
    if state:
        print("\nab3   ", fmt(state["means"][0]))
        print("mean  ", fmt(vector(state, "mean")))
        print("avg   ", fmt(vector(state, "avg")))
    return 0


def solve(A: list[list[float]]) -> list[list[float]]:
    """Inverse of a small symmetric positive matrix by Gauss-Jordan with partial pivoting."""
    n = len(A)
    M = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        piv = M[c][c] or 1e-12
        M[c] = [x / piv for x in M[c]]
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [row[n:] for row in M]


def slopes(run: str, quad: bool = False) -> tuple[list[float], list[float], int, int, float]:
    """Fitness against each constant's displacement, pooled over every candidate of the run.

    Fitness and displacement are both centred within their generation, which removes the
    game draw and the mean's own drift, so the slopes describe the neighbourhood the run
    explored (around ab3). Returns slopes and standard errors per unit of [0, 1] (then the
    curvatures, with quad), the candidate and generation counts, and the residual sd.
    """
    rows = [json.loads(x) for x in (ES / run / "log.jsonl").read_text().splitlines()]
    to_u = lambda v: [(v[p[0]] - p[2]) / (p[3] - p[2]) for p in PARAMS]
    X, y = [], []
    for r in rows:
        m = to_u(r["mean_before"])
        cs = [c for c in r["candidates"] if r["fit_minus_base"][c] > -1e8]
        ds = [[u - mi for u, mi in zip(to_u(r["candidates"][c]), m)] for c in cs]
        fs = [r["fit_minus_base"][c] for c in cs]
        feats = [d + ([x * x for x in d] if quad else []) for d in ds]
        k = len(feats[0])
        avg = [sum(f[j] for f in feats) / len(feats) for j in range(k)]
        fbar = sum(fs) / len(fs)
        X += [[f[j] - avg[j] for j in range(k)] for f in feats]
        y += [f - fbar for f in fs]
    k, n = len(X[0]), len(X)
    xtx = [[sum(row[i] * row[j] for row in X) for j in range(k)] for i in range(k)]
    xty = [sum(row[i] * yi for row, yi in zip(X, y)) for i in range(k)]
    inv = solve(xtx)
    b = [sum(inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    res = [yi - sum(bj * xj for bj, xj in zip(b, row)) for row, yi in zip(X, y)]
    dof = n - k - len(rows)
    s2 = sum(r * r for r in res) / max(1, dof)
    se = [math.sqrt(max(0.0, s2 * inv[i][i])) for i in range(k)]
    return b, se, n, len(rows), math.sqrt(s2)


def cmd_grad(a) -> int:
    """Print slopes() in fitness per tenth of each constant's range."""
    b, se, n, gens, sd = slopes(a.run, a.quad)
    print(f"{n} candidates over {gens} generations; residual sd {sd:.0f}")
    print(f"  {'constant':<24}{'ab3':>8}{'range':>14}{'slope/0.1':>11}{'se':>7}{'t':>6}"
          + (f"{'curv/0.1^2':>12}{'se':>7}" if a.quad else ""))
    for i, (name, d0, lo, hi, _) in enumerate(PARAMS):
        line = f"  {name:<24}{d0:>8}{f'{lo}-{hi}':>14}{b[i] / 10:>+11.1f}{se[i] / 10:>7.1f}{b[i] / se[i]:>+6.1f}"
        if a.quad:
            j = i + len(PARAMS)
            line += f"{b[j] / 100:>+12.1f}{se[j] / 100:>7.1f}"
        print(line)
    return 0


def cmd_apply(a) -> int:
    if not a.bot.startswith("es_") or a.bot == BASE:
        sys.exit("apply writes es_* folders only, never es_base")
    if (BOTS / a.bot).exists() and not a.force:
        sys.exit(f"ws/bots/{a.bot} exists (--force replaces an es_* folder)")
    state = load_state(ES / a.run)
    vals = values(vector(state, a.which))
    make_bot(a.bot, vals)
    err = build(a.bot)
    if err:
        sys.exit(err)
    print(f"wrote and built ws/bots/{a.bot}: " + " ".join(f"{k}={v}" for k, v in vals.items()))
    return 0


def table(recs: dict, label: str) -> dict:
    print(f"\n{label}: {len(recs)} games")
    print(f"  {'opponent':<14}{'games':>6}{'win%':>7}{'margin':>8}{'fitness':>9}{'gold':>7}{'deaths':>7}{'faults':>7}")
    tot = []
    for opp in LEAGUE + sorted({k[0] for k in recs} - set(LEAGUE)):
        rs = [r for k, r in recs.items() if k[0] == opp]
        if not rs:
            continue
        s = summarise(rs)
        tot += rs
        print(f"  {opp:<14}{s['n']:>6}{100 * s['win']:>7.1f}{s['margin']:>+8.0f}{s['fit']:>+9.1f}{s['gold']:>7.0f}"
              f"{s['deaths']:>7.1f}{s['faults']:>7}")
    s = summarise(tot)
    print(f"  {'all':<14}{s['n']:>6}{100 * s['win']:>7.1f}{s['margin']:>+8.0f}{s['fit']:>+9.1f}{s['gold']:>7.0f}"
          f"{s['deaths']:>7.1f}{s['faults']:>7}")
    return s


def cmd_score(a) -> int:
    first = read_tag(BENCH / a.tags[0])
    table(first, a.tags[0])
    if len(a.tags) > 1:
        second = read_tag(BENCH / a.tags[1])
        table(second, a.tags[1])
        print(f"\n{a.tags[0]} minus {a.tags[1]}, paired game by game:")
        for opp in LEAGUE + sorted({k[0] for k in first} - set(LEAGUE)):
            x = {k: r for k, r in first.items() if k[0] == opp}
            if not x:
                continue
            f, se, n = paired(x, second)
            w = paired(x, second, "win")[0]
            mg = paired(x, second, "margin")[0]
            print(f"  {opp:<14}{n:>5} games  fitness {f:+7.1f} (se {se:5.1f})  margin {mg:+7.1f}  wins {100 * w:+6.1f}%")
        f, se, n = paired(first, second)
        w = paired(first, second, "win")[0]
        mg = paired(first, second, "margin")[0]
        print(f"  {'all':<14}{n:>5} games  fitness {f:+7.1f} (se {se:5.1f})  margin {mg:+7.1f}  wins {100 * w:+6.1f}%")
    return 0


def cmd_league(a) -> int:
    tag = BENCH / a.tag
    log = ES / f"league_{a.tag}.log"
    ES.mkdir(parents=True, exist_ok=True)
    with log.open("w") as f:
        r = subprocess.run([sys.executable, str(ROOT / "bench.py"), a.bot, "--opponents", a.opponents,
                            "--tag", a.tag, "--jobs", str(a.jobs)], cwd=ROOT, stdout=f, stderr=f)
    if r.returncode != 0:
        sys.exit(f"bench.py failed: see {log}")
    raw = sorted(str(p) for p in tag.glob("*__*__*.json"))
    with cf.ProcessPoolExecutor(max_workers=a.jobs) as pool:
        list(pool.map(gzip_file, raw, chunksize=16))
    cmd_score(argparse.Namespace(tags=[a.tag]))
    return 0


def gzip_file(path: str) -> None:
    p = Path(path)
    Path(path + ".gz").write_bytes(gzip.compress(p.read_bytes(), 6))
    p.unlink()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("base")
    p.add_argument("--check", action="store_true")
    p = sub.add_parser("run")
    p.add_argument("--run", required=True)
    p.add_argument("--gens", type=int)
    p.add_argument("--until", help="HH:MM UTC")
    p.add_argument("--lam", type=int, default=16)
    p.add_argument("--maps", type=int, default=3, help="maps an opponent a generation (both sides)")
    p.add_argument("--sigma", type=float, default=0.15)
    p.add_argument("--cm", type=float, help="mean learning rate (default 1; on resume, changes it)")
    p.add_argument("--freeze", action="store_true", help="from now on keep sigma and C fixed")
    p.add_argument("--recentre", action="store_true", help="reset the mean to ab3 before resuming")
    p.add_argument("--why", help="reason for a change of course, for es.log")
    p.add_argument("--jobs", type=int, default=8)
    p = sub.add_parser("show")
    p.add_argument("--run", required=True)
    p = sub.add_parser("grad")
    p.add_argument("--run", required=True)
    p.add_argument("--quad", action="store_true", help="add a curvature term for each constant")
    p = sub.add_parser("apply")
    p.add_argument("bot")
    p.add_argument("--run", required=True)
    p.add_argument("--which", default="mean")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("score")
    p.add_argument("tags", nargs="+")
    p = sub.add_parser("league")
    p.add_argument("bot")
    p.add_argument("--tag", required=True)
    p.add_argument("--opponents", default=",".join(LEAGUE))
    p.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    return {"base": cmd_base, "run": cmd_run, "show": cmd_show, "grad": cmd_grad, "apply": cmd_apply,
            "score": cmd_score, "league": cmd_league}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
