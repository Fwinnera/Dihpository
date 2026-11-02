# Farming rebuild tools (2026-11-02)

Run from the repository root unless noted. Local bench games come from `bench.py`;
ladder data from `analysis/fetch_team.py` (folders under `ws/bench/`).

Profiler (one line per champion turn naming the decision branch):

    python3 analysis/rebuild/mkprof.py ws/bots/p_X     # on a copy of a j_hjt-line bot
    analysis/rebuild/profrun.sh p_X OUTDIR f_hor_h f_vv_h   # every map, both sides
    python3 -I analysis/rebuild/profsum.py OUTDIR      # share of rounds by decision
    python3 -I analysis/rebuild/trips.py OUTDIR        # how camp trips end
    python3 -I analysis/rebuild/homecost.py OUTDIR     # rounds lost per trip home
    python3 -I analysis/rebuild/opening.py OUTDIR 100  # the first 100 rounds
    python3 -I analysis/rebuild/deaths.py OUTDIR       # what preceded each death
    python3 -I analysis/rebuild/firstcamp.py OUTDIR    # each champion's first camp
    python3 -I analysis/rebuild/tl.py OUTDIR/<opp>__<map>__<A|B> A vendetta 300

Ladder summaries (`FOLDER:TEAM NAME`, e.g. `top_mite:Mite`):

    curve.py FOLDER:TEAM ...        team totals by round (gold, damage, gems, deaths)
    early.py 100 FOLDER:TEAM ...    per champion: rounds hitting camps, first hit
    openclears.py 100 FOLDER:TEAM   which camps are cleared early, how far from spawn
    shared.py 150 FOLDER:TEAM ...   clears with teammates helping; own/enemy half
    visits.py FOLDER:TEAM ...       trips home (spawn-heal spikes) and deaths
    sustain.py FOLDER:TEAM ...      healing, shielding, damage taken by champion

Local bench tags: `lshared.py 150 TAG ...` (shared clears, early damage and gold).

Camp table: `camps86.json` (78 of 86 maps: groups with gems, gold, respawn, health,
strength, first spawn tile; both spawns; altars). Rebuild with `probe1.sh` over every
map into a folder, then `camptab.py FOLDER camps86.json` (the probe is `p_hjt`).

Variants (patch a copy of j_hjt or tf1; see each script's docstring):

    mkjoin.py   group-aware camp choice (tf1)       mkhalf.py  own-half opening (tf3)
    mkhome.py   trips home priced by the walk back  mkrush.py  opening rush (tf4)

Screening: `screen.sh PREFIX LOG "CAND ..." ["OPP ..."]` runs `bench.py` per pairing and
appends the `h2h.py` line; `g1sum.py CANDS OPPS PREFIX` totals a screen.
