# Top-50 push tools (10 Nov 2026, CLOUD)

Paths are for the container of that day (`/home/user/ws5`, cambc 5.0.1 in `/home/user/.venv-cambc5`).

- `arm.sh BOT ARM "NOTE"`: smoke test (both sides, empty stdout), upload, wait until live, pin, queue lab sets 1-3
  (`--from pm_best*`), wait, print the result. `queue.sh LOG "BOT|ARM|NOTE" ...` runs several in turn.
- `lab.py`: the lab with today's paths and **set 4** (ten teams ranked 85-148 on 10 Nov). Today's arms use the
  128-map plan, so they pair with each other (`lab/`), not with the 6 Nov arms by map.
- `fetchlab.py OUTDIR [--replays] ARM...`, `pair.py BASE CAND` (paired wins, gem margin, deaths, economy).
- `fetch.py` (ranked games of teams by id), `ranked.py` (our ranked win rate by live-version window).
- `early.py` (economy at rounds 100-400, purchases), `company.py`, `coattack.py` (who attacks a camp group
  together), `actbudget.py` (action shares per living turn), `trace.py` (one team's timeline),
  `deaths.py`, `deathact.py` (local numbers and actions before each death), `pfsum.py` (profile of `ws/bots/pf183`).
- `read3_camps.mjs`: read3.mjs plus a first line with every camp's position and health.
