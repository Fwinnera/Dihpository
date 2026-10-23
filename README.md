# Milk and Potatoes — Cambridge Battlecode 2026a

Two AI agents work on this bot. **LOCAL** runs on the owner's Mac with the
engine, the local harness and the platform login. **CLOUD** is the second agent.
Each keeps its own section below current. Read **Shared rules** and the
**Ladder lock** before doing anything that touches the platform.

The full research record — every measurement, decision and retraction — is
`GROUND-UP-PLAN.md`. This file only says who is doing what right now.

---

## Shared rules

Both agents use the same team account, so they share one live submission and
one match quota. Most of the ways to waste a day here come from forgetting that.

1. **One live submission.** The ranked bot is `ws/bots/greatsage`, and
   `greatsage.zip` is the verified copy that every ladder test restores. Neither
   may be changed without saying so in your section first.
2. **Ladder tests submit a test bot temporarily.** `ladderbench.py` submits,
   queues unranked groups, waits for them to finish, then restores greatsage.
   If a second agent submits during that window, it replaces the test bot
   mid-run and the result is silently contaminated. **Take the ladder lock
   before any `cambc submit` or `ladderbench.py` run, and release it after the
   restore line prints.**
3. **Quota: 50 unranked matches an hour per team, shared by both agents.** A
   two-arm ladder test (4 opponents × 5 maps × 2 arms) uses 40. Other teams'
   scrims against us may also count.
4. **Pin opponents by team id.** Ladder ranks drift within hours, so
   `--opponents 25,60` means different teams on different runs. For any
   comparison across runs, use `--same-as TAG`.
5. **Every test arm** must parse (a build that fails is silently replaced by
   the previous bot), print a `BOTTAG`, and be compared against a fresh tagged
   baseline. Discard games that are bit-identical between arms.
6. **Local gate:** use the full 320-game pool (`bench.py`), never a hand-picked
   map set; eight hand-picked maps overstated one change about ninefold. The
   ladder decides.
7. **No credentials in the repo or in chat.** The platform login is the
   owner's (`cambc login`, done by the owner). GitHub access is a deploy key.
8. **Record results in `GROUND-UP-PLAN.md`** (append; state retractions
   explicitly), and keep your section here short and current.

## Ladder lock

    held by:   LOCAL
    since:     2026-10-23 15:21Z
    for:       disengage ladder test (tags da_base, da_dis)
    expected:  released by about 16:00Z

To take it: edit this block, commit and push *before* submitting. To release it:
set `held by: nobody` and push. If it has been held for more than 90 minutes,
ask the owner before overriding it.

---

## LOCAL

**Agent:** Claude Code on the owner's Mac. It has the engine (`cambc`), the
local harness, the platform login and the GitHub deploy key.
**Branch:** `shop-economy`.
**Updated:** 2026-10-23 15:35Z.

### Doing now

Ladder test of **candidate A, disengage at ratio 0.75** (`ws/bots/gs_dis075`)
against a fresh baseline (`gs_shopbase` = greatsage + a tag), on four opponents
pinned by id from `dv_base`, five maps. The baseline arm is done and restored;
the candidate arm is waiting for a safe window between ranked batches. Result
due about 16:00Z. Ship criterion: deaths down and gems not down on the ladder,
with the fresh baseline bit-identical to `dv_base` (the contamination check).

### What the bot is and what is live

- Live ranked bot: **greatsage**, a Python bot. Nothing new has been shipped
  today.
- `ws/bots/sage2` is a C++ rewrite. It is faster but weaker on navigation and
  not live.

### Established today (numbers in `GROUND-UP-PLAN.md`)

- **The gap is gold.** Opponents earn about 10,000 a game to our 4,500. Half
  the difference is kills (199 gold each; our 22.5 deaths a game pay them about
  4,480) and half is camp damage.
- **Deaths:** in about 14.6 fights a game we are at 8% odds or worse. Three
  causes in code:
  - `combat.choose_enemy` accepts any enemy within 4 tiles, whatever the odds.
  - The retreat logic ignores enemy champions until 30% health.
  - The farming penalty for nearby enemies is at most +20.
- **Candidate A**, disengage when the local strength ratio is below 0.75, on
  the full local pool: deaths −6.4 (se 0.56), kills +4.2, gems +47.7 (se 20),
  win rate +4.1. The first change today to beat the noise on gems.
- **Tested and not shipped:**
  - Treasure emblem first: gold +15–22%, gems flat.
  - Willow → Vesper Vale draft swap: gold up, gems flat on the ladder.
  - Gold weight 0.3: failed its held-out test.

### Next, in order

1. If A holds on the ladder: candidate **B**, removing the unconditional
   `gap <= 4` accept in `combat.choose_enemy`.
2. Candidate **C**: scale the farming penalty by the enemy strength near a camp.
3. Retest Treasure and the draft swap on top of A, since their extra gold may
   convert once we stop losing fights.
4. Banking only where it fails (bank earlier when enemy champions are visible).
5. Longer track: a C++ port with fight simulation.

### Useful files

| path | what |
|---|---|
| `ladderbench.py` | ladder test harness: submit, queue, wait, restore, compare |
| `bench.py` | local harness, 4 opponents × 40 maps × 2 sides = 320 games |
| `analysis/fights.py` | rebuilds every ladder fight from match summaries |
| `analysis/mkdisengage.py`, `analysis/calibrate.py` | candidate A and its calibration |
| `analysis/itemtable.py` | dumps the engine's item design table |
| `ws/bench/ladder/<tag>/` | ladder results per tag (not committed, about 4 GB) |

### Notes for CLOUD

- Take the ladder lock before submitting anything (rule 2).
- Don't edit `ws/bots/greatsage` or `greatsage.zip` without saying so here.
- If you want a local measurement run, ask in your section and LOCAL will run
  it.

---

## CLOUD

> Template — CLOUD fills this in and keeps it current.

**Agent:**  <!-- what you are and where you run -->
**Branch:**  <!-- the branch you commit to -->
**Updated:**  <!-- YYYY-MM-DD HH:MMZ -->
**Can run:**  <!-- engine locally? platform login? GitHub push? -->

### Doing now

<!-- the one task in progress, and what done looks like -->

### Needs the ladder?

<!-- yes/no; if yes, when, how many matches, and the lock is taken above first -->

### Findings

<!-- results with numbers, and where the full write-up is -->

### Next, in order

1. <!-- -->

### Files touched

| path | what changed |
|---|---|
| <!-- --> | <!-- --> |

### Notes for LOCAL

<!-- requests, conflicts, questions -->
