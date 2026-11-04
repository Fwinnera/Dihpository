# CLOUD tools (2026-11-04)

Written in a claude.ai cloud container (engine 2.0.0, `cambc` 4.0.0 in a venv at
`/home/user/.venv-cambc`, workspace `/home/user/repo/ws`). Paths are hard-coded for that container;
change the constants at the top of each file to run elsewhere.

## Setting up the engine in a cloud container

`pip install cambc==4.0.0`, then `SSL_CERT_FILE=/root/.ccr/ca-bundle.crt cambc init --yes DIR` fetches
the SDK and the 86 maps. The CLI's own downloader rejects the proxy's certificate for the toolchain, so
fetch these with curl and unpack them into `~/.cache/cambc/` with the top folder stripped:
`wasi-sdk-33` (wasi-sdk-33.0-x86_64-linux.tar.gz), `cmake-3.31.8-linux-x86_64` and
`ninja-1.12.1-linux-x86_64` (ninja-linux.zip). Then copy `sdk/`, `maps/`, `cmake/` into `ws/`.

## Replays: every unit's position and health, every round

`read.mjs` runs the visualiser's own engine (`~/.cache/cambc/assets/<hash>/visualiser/assets/v2_0_0-*.wasm`)
under Node 22 and prints one JSON line per round:

    {"r": round, "c": [[index, team, type, x, y, hp, maxhp, alive, gold, gems, kills], ...]}

team 0 is side a; type is `champion_type` (ryth 0 ... heart_of_ruin 12). It loads the replay
(`Game_FromReplayFileBytes`), enables checkpoints (`Game_Runner_SetCheckpointsEnabled`) and seeks
the main timeline position by position (`Game_Visualiser_Timeline_Seek`), reading
`Game_Visualiser_ReadTimelineState` with the layout of the visualiser's timeline snapshot parser
(ABI 40152/42840). About 6 s a game. `decode_dir.sh SRC DST` decodes every bundle in a folder.

Other teams' ranked replays can be downloaded too (`cambc matches download ID`; no stdout), so the
top teams' play can be measured the same way (`fetchteam.py OUTDIR N "TEAM" ...`; use a team UUID
when the name is ambiguous).

## Analysis

- `skirm.py BUNDLES STATES`: every death with the victim's allies and enemies within 6 in the 10 rounds
  before, by zone; team spacing (share of time with no teammate within 5).
- `groups.py BUNDLES STATES`: time with 0/1/2/3+ teammates within 5 and the death hazard in each.
- `labmech.py BUNDLES STATES [ARM ...]`: one line per set of games (deaths by zone, alone share, hazard).
- `diag.py DIR`, `hazard.py DIR`, `combathaz.py DIR`, `mates.py`: need our stdout from the profiled
  build `ws/bots/p_pm` (v166 + one PF line per champion turn: round type label x y hp maxhp gems gold
  group ne5 ne8 na5 dmin).
- `items.py DIR`, `power.py BUNDLES STATES`: drafts, final items, strength and economy by team.

## Lab

`lab.py` and `labrun.sh` are the cloud copies of `analysis/rebuild/lab.py` / `labrun.sh`. `lab/` holds
v166's three arms recovered from the match history (`pm_best*`: 23 + 24 + 26 = 73 of 150, the same games
as the Mac's), es_r2m's (76), and `pfdiag` (the profiled v167 on set 1 against the opponents' versions of
4 Nov 09:47Z, 19 of 50). Copy them into `ws/bench/lab/` and queue a candidate with `--from pm_best`,
`--from pm_best_s2`, `--from pm_best_s3` to pair it game by game with v166.

`mapinfo.json`: spawns, altars, size and symmetry of all 86 maps (probe `ws/bots/probe_mapinfo`).
