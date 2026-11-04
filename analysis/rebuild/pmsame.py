#!/usr/bin/env python3
"""Identical-elsewhere check: a candidate's games against ab3's saved games, game for game.

    pmsame.py TAG CAND [--maps others|all|m1,m2]

TAG holds pmscreen games <CAND>__<opp>__<map>__<side>. References are the saved full-pool
screens of ab3_submit (byte-identical wasm to pm_ref) against the originals of our opponent
copies: s31_ab3_submit_vs_{cHG_submit,gs_mix_camp,sh_submit} (files <opp>__<map>__<side>, ab3 on
<side>) and s39_bk2_submit_vs_ab3_submit (bk2 was the subject there: our side B is its file
ab3_submit__<map>__A). A game is identical when outcome, rounds, both teams' submitted gems and
every champion's metrics match.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pmscreen import pick_maps  # noqa: E402

BENCH = Path(__file__).resolve().parents[2] / "ws/bench"
REFS = {
    "pm_o_chg": ("s31_ab3_submit_vs_cHG_submit", "cHG_submit", False),
    "pm_o_gsmix": ("s31_ab3_submit_vs_gs_mix_camp", "gs_mix_camp", False),
    "pm_o_sh": ("s31_ab3_submit_vs_sh_submit", "sh_submit", False),
    "pm_o_bk2": ("s39_bk2_submit_vs_ab3_submit", "ab3_submit", True),
    "pm_o_btbd": ("s31_ab3_submit_vs_b_tbd", "b_tbd", False),
}


def load(p: Path):
    for q in (p, Path(str(p) + ".gz")):
        if q.exists():
            return json.loads(gzip.open(q).read() if q.suffix == ".gz" else q.read_text())
    return None


def sig(d):
    return json.dumps([d["match"]["roundsCompleted"], d["match"]["outcome"],
                       sorted((t["team"], t["submittedGems"]) for t in d["teams"]),
                       sorted((c["team"], c["name"], json.dumps(c["metrics"], sort_keys=True)) for c in d["champions"])])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("cand")
    ap.add_argument("--maps", default="others")
    a = ap.parse_args()
    maps = pick_maps(a.maps)
    total = same = missing = 0
    for opp, (rtag, rname, flip) in REFS.items():
        n = s = miss = 0
        diffs = []
        for m in maps:
            for side in "AB":
                mine = load(BENCH / a.tag / f"{a.cand}__{opp}__{m}__{side}.json")
                rside = ("B" if side == "A" else "A") if flip else side
                ref = load(BENCH / rtag / f"{rname}__{m}__{rside}.json")
                if mine is None or ref is None:
                    miss += 1
                    continue
                n += 1
                if sig(mine) == sig(ref):
                    s += 1
                else:
                    diffs.append(f"{m}/{side}")
        print(f"{opp:<12} {s}/{n} identical" + (f", {miss} missing" if miss else "") + (f"; differ: {' '.join(diffs[:20])}" if diffs else ""))
        total += n
        same += s
        missing += miss
    print(f"all: {same}/{total} identical, {missing} missing")


if __name__ == "__main__":
    main()
