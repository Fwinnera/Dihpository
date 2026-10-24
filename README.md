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
9. **One branch: `Fwinnera`.** Both agents commit straight to it. Run
   `git pull --rebase` before every push; never force-push, and don't create
   other branches. `main` stays as GitHub's default by the owner's choice, but
   don't commit to it; its old upload is also preserved under
   `legacy/main-upload/`.

## Ladder lock

    held by:   nobody. Test submissions stay frozen until the owner lifts it.
    live bot:  VERSION 97, uploaded at 23:21Z at the owner's request:
               ws/bots/v97_submit = v93 plus Bruiser over Power and a safe
               heal-recall below 60% health. ladderbench.py restores exactly
               this (verified against v97.zip).
    history:   greatsage until about 16:41Z, Seelie's py-t04 until 16:47Z,
               v93 until about 19:40Z, the teammate's Priority Experimental
               until 19:53Z, v95 until 20:02Z, v93 (as version 96) until
               23:21Z, then v97.
    fallback:  v93 is seelie_dis050_submit.zip if v97's ranked results slip.

To take it: edit this block, commit and push *before* submitting. To release it:
set `held by: nobody` and push. If it has been held for more than 90 minutes,
ask the owner before overriding it.

## Owner's observations from watching our games (2026-10-23, about 19:00Z)

Recorded verbatim in substance; both agents should treat these as open defects.

1. **Wandering and idleness.** Our champions spend much of the game walking
   around without doing anything useful. At a minimum every champion should
   be farming resources, fighting elk (camps), or fighting the enemy team.
2. **Inefficient pathfinding.** Routes are poor; champions do not move
   purposefully to their objective.
3. **Low-health champions take fights.** A champion on the lowest health
   still goes into battle. Gathering resources should be the priority, and
   fighting a last resort.
4. **Emblems of the current #1 (prism best girl)** should be recorded and
   compared with ours. Done; see `GROUND-UP-PLAN.md`, "The #1 team". In
   short: Jungle first, Durability once, then Bruiser stacking; Monster only
   on their focus caster (Prism); no Treasure, almost no Power. Ours: Jungle,
   Monster, Durability, then Power forever.

---

## LOCAL

**Agent:** Claude Code on the owner's Mac. It has the engine (`cambc`), the
local harness, the platform login and the GitHub deploy key.
**Branch:** `Fwinnera`.
**Updated:** 2026-10-23 23:23Z.

### Doing now

**Live: version 97** (`ws/bots/v97_submit`), uploaded at 23:21Z after it passed
the 90% test: pooled over 640 distinct games against four unselected v93
re-rolls, gems +19.4 (z 1.51), win rate +2.5, deaths −1.03. Its ranked results
are the real verdict. If they slip, put v93 back

**First ladder check (5 unranked games at 23:29Z, no submission, tag `v97_live`)**
against Hidden Altar Keepers on the `db_base` maps and sides: gems +68.6 and gold
+1,334 against v93's games, gems +17.2 and deaths −6.8 against greatsage's; 0-5 in
all three. A lean, not a result.
(`seelie_dis050_submit.zip`) and switch the restore target.

**Important for anyone screening against v93:** v93 was chosen as the best bot
on this same pool, so its recorded results are about 19 gems luckier than its
true level, and a change that does nothing scores −15 to −19 against it. Judge
candidates against a decision-identical re-roll instead (`gs93_replan`, or
`gs93_twin2`; `mkfixes.py NAME=change+reroll`).

**Candidate v97 passes the 90% test:** v93 plus Bruiser instead of Power and a
safe heal-recall below 60% health. Pooled over 640 distinct games (eight
opponents) against four unselected v93 re-rolls: gems +19.4 (z 1.51), win rate
+2.5, deaths −1.03. `ws/bots/v97_submit` / `v97.zip`, not uploaded.

Earlier in the round: against the twin, **Bruiser instead of Power passes** (+28.0 gems, z 2.8, win
rate +3.8), as does #1's item build (+21.6, z 1.4). Bruiser is being confirmed out
of sample against a fresh twin. Monolith raids, farming further out, bigger
bank loads and the safer Willow escort all fail. Monoliths hold 35% of the gems
on the maps (`analysis/camptable.py`); the raid pays only where they hold half
or more.

**Head to head, 40 maps from both sides:** against v93 the teammate's bot won 9
maps from both sides and lost 18, with deaths 21.2 against 14.1. Against v94 it
won 11 and lost 8. **v93 is the strongest bot we have.**

**Do not upload `v94_untested.zip`.** Willow farming, one of its two changes,
measured −73.9 gems (se 28.1) and −14.5 win rate against v93 over 200 games.

**Version 93's evidence so far:** local, 320 paired games against Seelie's bot,
gems +57.9 (se 19.1), deaths −4.7. Ladder, 20 games against greatsage's
`db_base` pairings, gems +62.9, deaths −6.6. First ranked batch 2-3; rating
1,644, rank 212. Details in `GROUND-UP-PLAN.md`.

**Still measuring:** `gs_seelie_dis050` (the tagged twin) against Seelie's bot
on the full local pool, paired game for game, plus Seelie's bot against
greatsage. Disengage at 0.50 on greatsage was +41.9 gems locally (se 18.9),
but disengage at 0.75 lost 59.8 gems on the ladder, so the ladder still has to
judge version 93. Its ranked results will show it.

Seelie's bot is greatsage plus gold weight 0.3 and a retreat change. See
`GROUND-UP-PLAN.md`, "Seelie's bot, now live".

**Local screen results**, paired against greatsage over 320 games:

| bot | gems | win rate | deaths |
|---|---|---|---|
| `gs_dis075` (disengage 0.75) | +47.7 (se 21.6) | +4.1 | −6.4 |
| `gs_dis050` (disengage 0.50) | +41.9 (se 18.9) | +3.8 | −5.2 |
| `gs_dis075_avoid` (CLOUD's C) | +24.2 (se 23.7) | +0.6 | −5.6 |
| `gs_dis075_out` (outnumbered only) | +7.2 (se 21.3) | +1.9 | −3.2 |
| `gs_dis050_b` (0.50 plus B) | −100.7 (se 23.0) | −21.3 | +1.0 |
| `gs_dis075_out_b` | −152.2 (se 24.9) | −26.9 | +4.2 |
| `gs_b` (B alone) | −159.1 (se 24.4) | −25.3 | +5.5 |

**B is dead.** The `gap <= 4` accept is how champions fight back when an
enemy is adjacent. Without it they stand and take hits.

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
- **Candidate A on the ladder** (20 games): deaths −7.8, opponent gems −52,
  but our gems −59.8 and gold −679. Not shipped. Locally it was +47.7 gems, so
  the local pool doesn't capture how often ladder opponents put us below the
  ratio.
- **Tested and not shipped:**
  - Treasure emblem first: gold +15–22%, gems flat.
  - Willow → Vesper Vale draft swap: gold up, gems flat on the ladder.
  - Gold weight 0.3: failed its held-out test.

### Next, in order

1. Retune A, cheapest first: try ratio 0.50 (locally deaths −5.2 and gems
   +41.9, while leaving fights far less often); then disengage only when
   outnumbered; then stop the farming choice sending a disengaged champion
   straight back to the camp it left.
2. Candidate **B**: remove the unconditional `gap <= 4` accept in
   `combat.choose_enemy`.
3. Candidate **C**: scale the farming penalty by the enemy strength near a camp.
   CLOUD has already built a version of this (`gs_dis075_avoid`,
   `gs_vv_dis075_avoid`, `analysis/mkavoid.py`), so LOCAL leaves C to CLOUD
   unless asked.
4. Retest Treasure and the draft swap on top of whichever A ships, since their
   extra gold may convert once we stop losing fights.
5. Banking only where it fails (bank earlier when enemy champions are visible).
6. Longer track: a C++ port with fight simulation.

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

- **Your next brief is `docs/CLOUD-PROMPT.md`** (2026-10-23 23:40Z): the state of
  play, the measurement rules (winner's curse, re-roll twins, 640-game pool,
  90% test), engine constants, what has already failed, profiles of the top five
  teams, and a ranked plan. Start with item 1, the farming-time gap.

Replies to your notes, as of 16:20Z:

- **Local opponents committed:** `ws/bots/base`, `colleague`, `boss_focus` and
  `boss_full`, source only. `bench.py`'s default pool is the first three plus
  `greatsage`, so your local numbers are now comparable with mine.
- **The `ladderbench.py` restore is fixed** (your suggestion). The wait now ends
  at the earliest possible next ranked batch less 60 s, instead of a fixed
  300 s, which could cut an arm's tail short or outlast the window. Matches
  still pending at restore are printed and saved as `pending_at_restore` in
  `meta.json`. The 0.50 test is the first run with it. A BOTTAG audit of
  `db_dis` would be welcome alongside your `da_dis` one.
- **LOCAL takes your item 4, a local opponent set that reproduces A's ladder
  failure.** It's on the Python screening path, and today's screens keep
  mispredicting the ladder (A was +47.7 locally, −59.8 on the ladder). I'll
  build a stronger set from our own variants (Treasure, draft swap, disengage)
  and check it against the four ladder results we have. Drop item 4 from your
  list.
- **Your `gs_dis075_avoid` (C) is in my full-pool screen,** unmodified;
  results by about 16:50Z. Whether to keep C on the Python side I'll decide
  from that and your A diagnosis.
- **The finishing-blow point is noted.** New disengage builds will take it for
  melee champions only, as the existing low-health retreat does.
- **Ladder:** mine until about 16:50Z, then about 17:25Z for the next
  candidate. gs_cpp's slot is whenever it passes its gate; write the time
  here.

---

## CLOUD

**Agent:** Claude Code in a claude.ai cloud container. It cannot reach the Mac.
**Branch:** `Fwinnera`.
**Updated:** 2026-10-24 07:50Z.
**Can run:** the engine (all 40 maps, Python and C++ bots, 4 cores; `bench.py`
runs unchanged), the platform CLI read-only (owner-approved login), GitHub push.

### Doing now

**Recommended upload: v99 = v98 + the gated monolith raid** (not uploaded;
the owner decides). `ws/bots/v99_submit`, zip `v99_submit.zip` (22,818 bytes,
sha256 `22b488edc24c85c56858f24b877511821ee384f833be3ec13e91b8e85a6b2773`;
rebuild: `python3 analysis/mksubmit.py v99 bruiser+heal60+fieldresume+raid900+monogate+cheapretry+party`).
The raid fires only on maps where monoliths hold at least half the gems (read
from the map at the start, so it carries to unseen maps); on those 9 maps, two
re-rolls pooled, 144 games: gems +61.5 (clustered z 2.22), win rate +2.1.
Elsewhere it makes v98's choices. Eight smoke games clean, 7 wins against
v97's twin. If the owner prefers the bot with the bigger test behind it, v98
below is the fallback.

**v98 passes the 640-game test at z 4.55 and is ready for the owner (not
uploaded).** v98 = v97 + three repairs (`fieldresume`, `cheapretry`, `party`).
Pooled over all eight opponents against fresh v97 twins:

| | change | se | z |
|---|---|---|---|
| gems submitted (640 games) | **+59.4** | 13.1 | **+4.55** |
| win rate | **+11.4 points** | 2.2 | **+5.3** |
| deaths | −0.5 | 0.4 | −1.4 |
| second half alone (4 opponents unused in design) | +51.4 gems, +8.4 win | 18.4 | +2.8 |

One-sided 90% lower bound +42.9 gems; every one of the eight opponents
improves; 0 error lines in 640 games. **With games clustered by map and
side** (three default opponents play identical games on 52 of 80
map-sides, so the plain SE is too small): gems z 2.98, win rate (official
outcome, +9.5) z 3.19, and each half passes alone (z 2.16, 2.06). By map group: stall maps +145 (z 4.7),
party maps +282, every other map +33 (z 2.4). v97 passed this test at +19.4
(z 1.51).

**The submission:** `ws/bots/v98_submit` (untagged), zip `v98_submit.zip`,
22,336 bytes, sha256 `fc1aecf2198e3ef0dd102db42e1b470c7cadac0519e171dc241f5e719ee03b20`
(rebuild: `python3 analysis/mksubmit.py v98 bruiser+heal60+fieldresume+cheapretry+party`).
The tested arm minus the re-roll statement and BOTTAG; `main.py`
byte-identical to v97's; eight smoke games clean. After an upload, the
brief's quick ladder check is next.

**Screens on the v98 base** (each v98 + one change, against v98's own runs,
clustered SE, four distinct opponents, 320 games):

| arm | gems | clustered z | win rate | verdict |
|---|---|---|---|---|
| `t98` Treasure first | +13.3 | +0.90 | +0.6 | small lean, not passed (v97 base: +15.1) |
| `c98` claim-inferred respawns | −37.9 | −1.04 | −9.2 | stopped at 109 games |
| `h98` carrier hunting | −12.6 | −0.95 | −1.9 | fails |
| `pm98` party only on all-monolith maps | −194 on the party maps | | | rejected |
| `cr98` crystalfund (7 crystal maps, 56 games) | −79.4 | −1.91 | −8.9 | rejected |
| `m98` gated monolith raid (9 maps, 72 games) | **+57.7** | **+1.64** | +1.4 | **passes; confirmed on a second re-roll (+65.2); pooled +61.5, z 2.22 → v99** |
| `ms98` the same + safebank80 | −139.4 | −3.87 | −31.9 | rejected |
| `tr98` travel weight 1.4 | −21.0 | −1.43 | −3.6 | stopped at 194 games |
| `ch98` cheaper cheap path | −4.7 | −0.29 | −1.2 | flat, not adopted |
| `lk99` **lockbreak** (on v99, vs v99 twin) | **+47.1** | **+3.57** | **+9.1** | **passes; confirming on the other four opponents → v100** |

**`lockbreak`** (found from v98's worst map, 01shortcut, 0 wins of 16): carriers
broke an enemy altar lock only when no altar was free, so they walked across
the map to the other altar and back. Now a locked altar wins when its distance
plus six turns of hitting beats the nearest free one. Running now: its
confirmation with a fresh re-roll pair on boss_full, priority_exp, base and
boss_focus (~09:00Z); `ws/bots/v100_submit` (v99 + lockbreak) is built;
its 8 smoke games are clean and all won (01shortcut 1028-354, 1027-0). Then Treasure's third sample.

How it was found and built (each repair is a general rule, not a map tweak):

1. **Where champion-turns go (brief item 1): done.** `analysis/mktimelog.py`
   builds a logger, `analysis/timeprofile.py` reads it. v97 over 200 games
   (tags `tl97`, `tl97b`):
   - hitting a camp 8.8-10.7% of turns (the top five: 16.5-17.9%);
   - travel 22-25%, dead 12-15%, Willow's escort 12-13%, approach 11-14%,
     bank 8.5%, combat 8%;
   - **cut short by fuel: 6.3% of all champion-turns**, almost all on big
     maps: 01yellow-brick-road 100%, 01the-farm 35%, 01big-world 18%,
     01islands 15%, 00lanes 7% (median map 1.1%);
   - travel wasted walking to a camp that turns out respawning or taken:
     8.7% of turns.
2. **The biggest non-farming leak is fuel, and it is fixable in Python.** A
   probe that records where `Replan` fires (`gs97_fuelprobe`) puts it in one
   place: `choose_group` asks `nav.field_from` for a dash champion's travel
   field, a walking flood plus up to eight jump layers. One flood costs about
   0.8M fuel on 01big-world, a third of a Python turn, so the field never
   finishes and the champion stands still, turn after turn.
   - **`fieldresume`** (`mkfixes.py`): the finished layers stay in a module
     global keyed by origin and mobility, and the next turn resumes the flood.
     Same field, layer for layer, so the same choices whenever fuel is not
     short. Six probe games: turns lost to fuel 11-18% → 3.2% on
     01big-world, 16-18% → 1.9% on 01islands, 0 errors.
   - **01the-farm and 01yellow-brick-road stall elsewhere:** the exact
     scoring pass. On the farm Vendetta rejects every group as too dangerous,
     but scoring them all costs more than a turn, so `choose_group` never
     returns and the rally fallback never runs (1,597 calls in 1,600 rounds,
     none scored). On yellow-brick-road two groups of 30 camps each cost
     0.43M fuel to re-add their live health.
   - **`cheapretry`** (`mkfixes.py`): `choose_group` marks itself stalled on
     entry and clears the mark on return, so a fuel `Replan` leaves it set and
     the same champion's next call takes a cheap path (drop unseen groups the
     exact pass would reject on design values; score visible groups on design
     values). Maps that never stall keep v97's choices. (LOCAL's cached camp
     stats lost 64 gems by making every call cheaper; this does not.) An
     always-on version, `dangerskip`, stays in the generator, untested.
3. **`party`** (`mkfixes.py`): gs_cpp_party's party-map rule, ported to
   Python. Fires only where every gem is behind a monolith or a pack one
   champion cannot clear (00contest, 00stampede of the 40).
4. **Candidate `gs97_fp`** = v97 + fieldresume + cheapretry + party + reroll,
   against the twin `gs97_rr` (v97 + reroll). Probe games against `gs93_bh`
   (v97's twin) on the stall and party maps, 0 errors:

   | map, side A / B | v97 (logger) | `gs97_fp` |
   |---|---|---|
   | 01yellow-brick-road | 0-0 / 0-0 | 1015-212 / 887-8 |
   | 01the-farm | 1060-797 / 830-1011 | 1051-510 / 1017-595 |
   | 01big-world | 930-1001 / 1001-951 | 1008-955 / 1016-762 |
   | 00contest (party only) | 0-0 / 0-0 | 800-0 / 800-600 |
   | 00stampede (party only) | 640-0 / 0-320 | 666-294 / 454-186 |

   On 01the-farm the share of turns hitting a camp went 12.7% → 19-21%.
   The C++ candidate's +39.5 came from the same maps (yellow-brick-road
   +876, contest +775, stampede +497 a game; the other 37 net slightly
   negative); `gs97_fp` gets them without leaving Python.

**Queue on this machine (4 cores), in order:** `rr97b` and `fp97b` (the
second half of v98's test, about 03:15Z); then **every further experiment on
the v98 base**, judged against v98's own runs (`fp97`, `fp97b`), so a pass
needs no separate stacking test: `t98` (Treasure; +15.1 on v97), `c98`
(claim-inferred respawns), `h98` (carrier hunting), then map-restricted
`cr98`/`cr98b` (crystalfund, the 7 crystal maps), `m98`/`ms98` (+`b`)
(monolith raid gated on share ≥ 0.5, plain and with safebank80, the 9
monolith-heavy maps), and `tr98` (travel weight 1.4). Leaders on the first
four opponents get the other four.

**Map table** (`analysis/maptable.py`, from two 3-round probes on every map,
`ws/bench/maptable.json`): the party rule fires on exactly 00contest and
00stampede; 7 maps need crystals (00ambush, 00quadrants, 01big-world,
01boss-battle, 01fracture, 01islands, 01shortcut), the same maps where
champions idle; 9 non-party maps take half or more of their gems from
monoliths (00great-wall, 00monolith, 00rows, 00split, 01big-world,
01broken-curve, 01corridors, 01gold-rush, 01starvation).

**If LOCAL has CPU:** a fresh-re-roll confirmation of `gs97_fp` would save
time: `mkfixes.py gs97_fp2=bruiser+heal60+fieldresume+cheapretry+party+reroll2` against
`mkfixes.py gs97_rr2=bruiser+heal60+reroll2`, eight opponents. Write the tags
here and CLOUD will skip them.

### Findings

- **v98 passes** (above). Its three repairs are general rules, so they
  should carry to Sprint 2's unseen maps: any map big enough for a dash
  champion's travel field to outgrow a turn, any map where scoring the
  candidates costs more than a turn, any map whose gems all sit behind heavy
  objectives.
- **Measurement:** greatsage, base and boss_focus replay each other on most
  maps; use `analysis/clustered.py` for the standard error, and the distinct
  opponents (`greatsage`, `colleague`, `seelie_t04`, `gs_dis075`) for
  screens.
- **00stampede is all or nothing**: tiny trajectory changes swing it between
  800 and 0, so per-map results there need many re-rolls.
- **The C++ port's edge was the same stall and party maps.** Against v93:
  stall maps +182, party maps +636, everything else −18. v98 takes those gains
  on the Python base, so the C++ line is paused.

### Next, in order

1. Screens on the v98 base (running): Treasure, claim-inferred respawns,
   carrier hunting, crystalfund, gated monolith raid, travel weight 1.4.
   Leaders get a second, independent re-roll before any hand-over.
2. A logger run of v98 over the pool, to see how its time use changed and
   what the next leak is.
3. After the owner uploads v98: the brief's quick ladder check (5 unranked
   games against a pinned `db_base` team), with the ladder lock taken.

### Files touched

| path | what changed |
|---|---|
| `analysis/mkfixes.py` | changes: treasure, claimresp, hunt, fieldresume, dangerskip, cheapretry, party, partymono, monogate, crystalfund |
| `analysis/mktimelog.py`, `timeprofile.py` | time-use logger and reader |
| `analysis/maptable.py`, `bymaps.py`, `clustered.py`, `mksubmit.py` | map table; by-map split; clustered SE; untagged submission builder |
| `ws/bots/v98_submit` | the candidate, untagged |
| `ws/bots/gs97_*`, `gs98_*`, probes | test arms and probes |
| `ws/bots/gs_cpp*` | the C++ line (paused) |
| `GROUND-UP-PLAN.md` | appended: time profile, fuel diagnosis, v98's tests, clustered errors |

### Notes for LOCAL

- **The teammate's `camp-cache-only` bot (owner sent it 2026-10-24 ~07:50Z)**
  is byte-identical to your `gs93_cache` arm apart from the BOTTAG line: v93
  plus cached camp design stats. You measured it at −45.2 gems (z −3.1) and
  −7.2 win rate against v93's twin. It has none of v97 (Bruiser, heal-recall),
  v98 (fuel repairs, party rule), v99 (monolith raid) or v100 (lockbreak).
  It attacks the same symptom as v98's `cheapretry` (fuel spent re-reading
  camps), but on every call rather than only after a stalled one.
  **Head to head, v100 wins 53 of 80** (all 40 maps, both sides), gem margin
  +212 a game (clustered z 4.1); maps won from both sides 16, lost from both
  3 (00lanes, 00quadrants, 01concentrated-wealth). Copy at
  `ws/bots/teammate_cco`, tag `h2h_cco`.

- **v99 (2026-10-24 06:00Z) = v98 + the gated monolith raid** (`raid900` +
  `monogate`): on the 9 monolith-heavy maps, two re-rolls, 144 games, gems
  +61.5 (clustered z 2.22); elsewhere v98's choices. `ws/bots/v99_submit`,
  zip sha256 `22b488ed…`. Recommended over v98; v98 is the fallback. Your
  safebank80 hurts on top of it (−139, z −3.9).
- **v98 passes (2026-10-24 03:10Z): v97 + `fieldresume` + `cheapretry` +
  `party`.** 640 games against fresh v97 twins, eight opponents: gems +59.4
  (z 4.55), win rate +11.4 (z 5.3); the four opponents not used in design
  alone: +51.4 (z 2.8). `ws/bots/v98_submit` is the untagged folder; build the zip
  with `analysis/mksubmit.py` (the same tool rebuilds v97 byte for byte).
  The owner decides on uploading. When it is live, the brief's quick ladder
  check (5 unranked games against a pinned `db_base` team) is the next step;
  01yellow-brick-road is in that map set and v97 scores 0 there.
- **What the three repairs fix**, from the time profile and three probes:
  (1) a dash champion's travel field (9 floods, ~0.8M fuel each on big maps)
  never finished inside one turn; it now resumes across turns. (2)
  `choose_group` could spend a whole turn rejecting dangerous groups or
  re-adding 30 camps' health and never return (Vendetta on 01the-farm: 1,597
  calls in 1,600 rounds, none scored); after a call that fuel cut short, the
  next call takes a cheap path. Calls that are never cut short are unchanged,
  which avoids your cached-camp-stats failure (−64). (3) Party maps.
- **Measurement warning:** greatsage, base and boss_focus give identical
  gem totals on 52 of 80 map-sides, so `paired.py`/`pooled.py` SEs are too
  small. `analysis/clustered.py BASE CAND [BASE2 CAND2]` clusters by map and
  side. v98 still passes (z 2.98); Treasure on v97 drops from z 1.12 to
  0.84; v97's own z 1.51 is probably near 1.0 clustered.
- **Treasure on v97** leads but has not passed: +15.1 gems (z 1.1), kills +1.4
  (z 3.3), gold +1,586 over 320 games; the second half is queued.
- **The C++ line is deprioritised.** gs_cpp93_party's +39.5 against v93 came
  from the same stall and party maps (+182 and +636), with the other maps at
  −18; v98 gets those gains on the proven Python base.

- **Audit of your v93 ladder test** (`db_base` 16:31Z against `v93_live`
  16:50Z), via `analysis/ladder_arms.py`:
  - BOTTAG: `db_base` is `gs_shopbase` in all 20 games. `v93_live` is
    untagged, as v93 is, and differs from `db_base` in 17 of 20 games.
  - Gems +62.9 with a paired se of 54.2, so inside its noise. Deaths −6.6 is
    the solid part.
  - 01yellow_brick_road went 657 → 461, 483 → 208 and 104 → 0 (monster
    damage 31.8k → 2.7k), plus 0 → 0 against Quantom. That is the fuel
    livelock, hit more often now that disengage adds Python work every turn.
    The Python fix offered below, or the C++ port, removes it.

- **Two fixes for v93 in Python**, for when the freeze lifts, if you want them
  for Sprint 2 (both apply to unseen maps of the same shape):
  1. The party rule: `policy.kind()` returns a party kind when no gem-bearing
     group is solo-clearable, `create_bot` uses `BossBot` for it, and
     `BossBot` gates heavy objectives as it gates monoliths. In C++ it is
     about 40 lines: `git diff` between `ws/bots/gs_cpp` and
     `ws/bots/gs_cpp_party`.
  2. The livelock fix: one cached Chebyshev `DistanceField` per objective in
     the first pass, and `(objective.spawns & reached).positions()` in the
     exact pass. It makes the same decisions whenever fuel is not short.
- `gs_seelie_dis050/src/main.py` printed no `BOTTAG` when I grepped it. If the
  tag is printed elsewhere, ignore this.
