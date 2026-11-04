# Handover: CLOUD session of 4 Nov 2026 (Milk and Potatoes, Battlecode 2026a)

Read `docs/HANDOVER.md` (the Mac session's brief) first; this adds what the cloud session did on 4 November.

## State

- **Live: v166 = pm_best (`ws/bots/pm_best_submit`), pinned.** Every candidate tested today was rejected.
- The README ladder lock is the only coordination: take it (commit and push) before any submit, activate or
  match group, release it after re-pinning.
- The owner's goal: UK top 8 (about 2,160 rating; we were 1,693, 66th among teams without the International
  Qualifiers label, at 10:00Z on 4 Nov). The owner chose structural bets over retunes.

## Running in a claude.ai cloud container

`analysis/cloud/README.md` has the setup (cambc 4.0.0 in a venv; the SDK and maps with
`SSL_CERT_FILE=/root/.ccr/ca-bundle.crt cambc init --yes`; wasi-sdk-33, cmake-3.31.8 and ninja-1.12.1 fetched
with curl into `~/.cache/cambc/`, because the CLI's own downloader rejects the proxy certificate). The owner
logged this session in with `cambc login` (browser approval of a printed link; the session lasts seven days).
`analysis/cloud/labrun.sh`, `lab.py`, `screen.sh` are the cloud copies of the lab and screen scripts; local
games run about 170 every 3-4 minutes on 4 cores.

## Tools added (all in `analysis/cloud/`)

- `read.mjs`: runs the visualiser's own engine (wasm) under Node and prints every champion's position, health,
  gold and gems per round from any replay, ours or other teams' (about 6 s a game). Other teams' ranked replays
  can be downloaded with `cambc matches download`; `fetchteam.py` fetches a team's recent games.
- `skirm.py`, `groups.py`, `labmech.py`, `pairarms.py`: deaths by zone and by local numbers, spacing, hazards,
  and a paired comparison of lab arms (wins, margin, deaths by zone) from summaries.
- `gemsrc.py`, `captures.py`, `campwho.py`, `gemcurve.py`, `farmrate.py`, `items.py`: the economy and builds.
- `lab/`: v166's three lab arms recovered from the match history (`pm_best*`, 73 of 150; queue a candidate with
  `--from pm_best`, `--from pm_best_s2`, `--from pm_best_s3` to pair it game by game), es_r2m's and `pfdiag`.
- `ws/bots/p_pm`: v166 with one PF line per champion turn (and visible enemies/allies nearby); used live once.

## What the ladder data says (GROUND-UP-PLAN.md, sections from "CLOUD: why we die at home")

- We die 16.6 times a game to the lab teams' 7.7, mostly in our half and the middle, outnumbered (1v2, 1v3,
  0v2). Our champions have no teammate within 5 for 57% of their turns (ladder teams 42%, top UK teams 42%).
- We take 9.6 gems a capture before round 600 (lab teams 13.0, top teams 14.8); 38% of our captures give no
  gems. Top teams farm 43% more per living champion and bank twice our gems by round 600.
- Top UK teams all draft Heart of Ruin (with Vesper Vale, Marcella, Vendetta), buy Bruiser and Focus, keep a
  teammate within 4 tiles and die about once a game per champion.

## Tested on 4 Nov (lab: 150 games pinned to v166's opponents, v166 73)

    as2   assist a teammate an enemy reached              lab 62           local 120 vs gs_mix_camp (v166 132)
    gw04  early gold worth 0.4 of a gem                   lab 40 of 100    local 133.3 composite (v166 130.0)
    sq3b  Marcella escorts Vesper Vale                    lab 67           local 131.3
    sq4   sq3b in contested ground only                   (see GROUND-UP-PLAN.md)   local 133.0
    local only, all below v166: regroup, enemy memory, company, Heart of Ruin roster (hr1-hr5, 120-124),
    Bruiser strength builds (126), two-pair squads (118-121), Vendetta escort (119), gold 0.2/0.6.

Lessons: the gs_mix_camp screen predicted the lab for fight changes (as2); local gains of about +3 composite
did not survive the lab (gw04, sq3b); v166's 73 is typical of its lineage (sets average 26.0 / 21.8 / 25.2).
