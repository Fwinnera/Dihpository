#!/usr/bin/env python3
"""Second-stage screen: replay each map-side's leading arms on fresh seeds.

    stage2.py PREFIX OUTDIR [--seeds 5,6,7,8] [--max 6] [--easy 6] [--jobs 11]

Stage one (screen_omni.sh, seeds 1-4) leaves several arms tied at the top of
many map-sides. Candidates are the arms within one win of the map-side's best
stage-one record, at most --max of them (best overall record first). A
map-side with --easy or more arms at a perfect record needs no second stage.
Builds ws/bots/<PREFIX>_<arm>_<seed> as needed (mkomni_arm.sh), runs only the
candidate games, and writes OUTDIR/results.txt: arm seed map side win.
"""
import collections
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_arms  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT / "ws"
CAMBC = Path.home() / "Library/Python/3.9/bin/cambc"


def candidates(data, seeds, max_arms, easy):
    arms = sorted(data)
    rate = {a: sum(sum(data[a][s].values()) for s in seeds if s in data[a]) for a in arms}
    keys = sorted(data[0][seeds[0]])
    out = {}
    for k in keys:
        rec = {a: sum(data[a][s][k] for s in seeds) for a in arms}
        best = max(rec.values())
        if sum(1 for v in rec.values() if v == len(seeds)) >= easy:
            continue
        cands = sorted((a for a in arms if rec[a] >= best - 1), key=lambda a: (-rec[a], -rate[a]))
        out[k] = cands[:max_arms]
    return out


def main(argv):
    prefix, outdir = argv[0], Path(argv[1]).resolve()
    opt = lambda name, default: argv[argv.index(name) + 1] if name in argv else default  # noqa: E731
    seeds2 = [int(x) for x in opt("--seeds", "5,6,7,8").split(",")]
    max_arms, easy, jobs = int(opt("--max", "6")), int(opt("--easy", "6")), int(opt("--jobs", "11"))
    data = pick_arms.load(prefix)
    cands = candidates(data, [1, 2, 3, 4], max_arms, easy)
    need = sorted({(a, s) for arms in cands.values() for a in arms for s in seeds2})
    print(f"{len(cands)} map-sides need a second stage; {sum(len(v) for v in cands.values()) * len(seeds2)} games; "
          f"{len(need)} builds")
    todo = [f"{a} {s}" for a, s in need if not (WS / "bots" / f"{prefix}_{a}_{s}" / ".cambc/build-release/bot-injected.wasm").exists()]
    if todo:
        subprocess.run(["xargs", "-P", "6", "-L", "1", str(ROOT / "analysis/mkomni_arm.sh")],
                       input="\n".join(todo) + "\n", text=True, check=True, stdout=subprocess.DEVNULL)
    outdir.mkdir(parents=True, exist_ok=True)
    lines = []
    for (m, side), arms in cands.items():
        for a in arms:
            for s in seeds2:
                bot = WS / "bots" / f"{prefix}_{a}_{s}"
                opp = WS / "bots" / "gs_eq"
                stem = outdir / f"{a}_{s}__{m}__{side}"
                if (stem.with_suffix(".json")).exists():
                    continue
                pair = f"{bot} {opp}" if side == "A" else f"{opp} {bot}"
                lines.append(f"{pair} {WS / 'maps' / (m + '.map26a')} {stem}.repl26a --statistics {stem}.json")
    manifest = outdir / "manifest.txt"
    manifest.write_text("\n".join(lines) + "\n")
    if lines:
        subprocess.run([str(CAMBC), "run-batch", "--release", "--json", "--jobs", str(jobs), "--timeout", "300", str(manifest)],
                       cwd=WS, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows = []
    for f in sorted(outdir.glob("*.json")):
        head, m, side = f.stem.split("__")
        a, s = head.split("_")
        d = json.loads(f.read_text())
        us = "teamA" if side == "A" else "teamB"
        them = "teamB" if us == "teamA" else "teamA"
        g = {k["team"]: int(k["submittedGems"]) for k in d["teams"]}
        rows.append(f"{a} {s} {m} {side} {int(g[us] > g[them])}")
    (outdir / "results.txt").write_text("\n".join(rows) + "\n")
    print(f"{len(rows)} second-stage games recorded in {outdir / 'results.txt'}")


if __name__ == "__main__":
    main(sys.argv[1:])
