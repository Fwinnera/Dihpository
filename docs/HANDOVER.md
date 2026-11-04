# Handover: Milk and Potatoes, Cambridge Battlecode 2026a (4 Nov 2026, 07:20Z)

Paste everything below the line into the next AI.

---

You are taking over team **Milk and Potatoes**' C++ bot in Cambridge Battlecode 2026a
(https://2026a.battlecode.co.uk). This brief tells you what is live, the rules, how to
measure a change, what was tried and what is still open. The full record is in the repo.

## 1. Goal and deadline

- **The owner's goal is top 8 among UK student teams at the UK qualifiers on 11 November**
  (streamed and ladder-seeded). The site says: "Eight teams qualify from the UK and eight
  from the international category." The 16-team final is on 18 November.
- **Submissions:** the owner said "we have till the 10th", so expect the lock around
  10 Nov 23:59 GMT (confirm on the site). Before the International Qualifiers seeding,
  uploads were frozen from 00:20Z to 01:29Z on 4 Nov (`cambc submit` returned 409,
  "Submissions are frozen during tournament seeding"). Expect the same before the UK seeding,
  and have the entry pinned well before.
- **Standing (05:45Z, 4 Nov): rank 235, rating 1,705.** The ladder API has no country
  field, but international student teams carry an "International Qualifiers" label. Among
  the 315 teams without it (UK students plus non-students) we were about 55th. 8th was
  QS2isLaw at about 2,135 (rank 40). Top 8 needs roughly +400 rating: a step change, not a
  tweak. Be honest with the owner about that.

## 2. Where things are

- **Repo:** GitHub `Fwinnera/Dihpository`, branch **`Fwinnera`** only. Run
  `git pull --rebase` before every push; never force-push. Local checkout:
  `/Users/faeezaullyar/Claude/battlecode`.
- **Workspace** `ws/`: bots in `ws/bots/<name>/src` (C++ against `ws/sdk/cpp/cambc.h`); maps
  in `ws/maps`; data in `ws/bench`.
- **CLI:** `~/Library/Python/3.9/bin/cambc`. **The owner runs `cambc login` personally.**
- **Read first:**
  - `README.md`: shared rules and the **ladder lock**.
  - `docs/UK-PLAN.md`: the week's protocol and the summary of the night of 3-4 Nov, with
    the open decisions.
  - `GROUND-UP-PLAN.md`: the append-only research log. Its sections from "Toward the UK
    qualifier" onward cover the last day.
  - `docs/RL-PLAN.md`: the ES tuner and the danger-response bandit.
- **Tools:** `analysis/rebuild/` (its README lists the older ones) and `analysis/rl/es.py`.

## 3. What is live

- **v166 = pm_best** (`ws/bots/pm_best_submit`), live and **pinned**. It is v155 plus
  party-map fixes inside BossBot: nearest-first group scan, the 00anvil cluster opening,
  and banking at the altar.
- Every non-party game is identical to v155's: 149 of 150 lab results are the same.
- Over five-build families on party maps it scores 70% against v155's 61% (+9, se 5).
- **Owner, 07:15Z: "Keep pm_best live".**
- Fallback: **v155 = ab3** (`ws/bots/ab3_submit`).
- The ladder lock was released at 07:10Z.

## 4. Rules: do not break these

1. **Never use credentials that appear in chat.** Earlier in the season the owner pasted a
   login; it was declined and must never be used. The platform login is the owner's.
2. **Take the README ladder lock before any platform action** (submit, activate, queueing
   match groups); commit and push it, then release it afterwards.
3. **Only untagged, smoke-tested `_submit` builds go live**: no debug prints, `DEBUG = false`.
   Smoke test with `cambc run --release` from both sides: exit 0, no ERROR lines, no faults,
   empty stdout.
4. **`cambc submit` switches the team to "follow newest"**, so re-pin with
   `cambc submissions activate N`. Re-activating an old version rebuilds it (the build queue
   can take 10+ minutes); selecting another version cancels a pending build. Upload notes
   must be at most 80 characters.
5. **Quota: 50 unranked match groups an hour** (one group is 5 games); a three-set lab test
   uses 30.
6. **One live candidate at a time.** Side sessions never commit or touch the platform; the
   main session commits.
7. **Files:**
   - Use `rm` only with `"${var:?}"`, and never delete data permanently. A safety check
     blocks risky removals; ask the owner instead.
   - Put downloaded data in a fresh folder and read it with `python3 -I`.
   - To copy a bot, copy only its `src/`. The `.cambc` build cache holds absolute paths and
     breaks cmake in a copy.
   - **zsh does not word-split `$var`**: loops like `for s in "a b"; do set -- $s` need bash.
     That bug left four junk folders under `ws/bots/` with spaces in their names (listed in
     section 8).
8. **Disk:** about 37 GB free; `ws/bench` is about 140 GB. Screens gzip their own
   summaries.

## 5. How to measure (the night's main lessons)

- **Ladder lab** (`analysis/rebuild/lab.py`; `labrun.sh BOT ARM "NOTE"` runs the whole
  cycle):
  - Each set is 10 pinned teams × 5 maps. Sets 1-2 use ranks 176-228 from 3 Nov; set 3
    (`--set 3`) uses ten other teams ranked 186-208.
  - Opponents' versions are pinned with `--from v140` / `--from rl_s2` / `--from ab3_s3`.
  - v155's baseline is **23 + 25 + 26 = 74 of 150**. Margins come from `labmargin.py`.
- **The lab is deterministic.** The same code gives the same games, so a candidate differs
  from v155 only in the games its code reaches. A broad change re-deals all of them and
  lands within about +-6 wins (one sd) by chance. **Its resolution is about +-12 wins in
  150 at two sd**, so gains under about 8% cannot be confirmed in one run.
  - v155's 25 on set 2 is the best of 15 versions tested there (the others average 19.5).
  - Write the keep or reject rule down before the result arrives.
- **Local filter:** `analysis/rebuild/screen.sh` against **gs_mix_camp, b_tbd and next_trial**.
  - `labpredict.py` gives their rank correlations with lab results as 0.81, 0.52 and 0.49.
    Head to head against our own lineage predicts almost nothing (0.15).
  - v155 scores **132 / 124 / 132 = 129.3 of 172**; panel (sh, rl, cHG, gs_mix_camp, b_tbd,
    next_trial, f_hor_h) 818; held out: f_cast_n 160, gs_eq about 132.
  - `mapdiff.py CAND BASE OPP...` compares per map against v155's saved screens
    (`s31_ab3_submit_vs_*`).
  - Even so, local gains of 3-8% did not carry over to the lab.
- **Builds are chaotic.** Any change in fuel use re-deals games, party maps especially. Five
  decision-identical builds of v155 scored 37-48 of 70 there. Compare small changes as
  families (`pmfam.py`, `pmsame.py`, `wasmdiff.py`).
- **The bot is fuel-limited.** Fuel-only dead loops (`mktwin.py`) cost strength steeply:
  300 / 1,200 / 4,000 additions a turn scored 125.7 / 113.3 / 54.7.
  - Median use is about 20k fuel a champion-turn (p99 92k of 100k).
  - Longer soft scan budgets (fb) are level.

## 6. What was tried on 3-4 November

**On the lab** (150 games; v155 74). All were level and rejected:

    fc      farm, don't chase (step to an enemy only when it pays)   48 of 100 (sets 1-2)
    pro     Prospector as a fourth emblem                            46 of 100 (sets 1-2)
    tvop    Tavi before Ryth + Prospector + late camps cost 15       71
    proop   Prospector + late camps cost 15                          73
    es_r2m  ES tuner mean (league gs_mix_camp, b_tbd, next_trial)    76
    pm_best party-map fixes only (kept: identical elsewhere)         73

**Local only, with the three-opponent composite in brackets (v155 129.3):**

- **Worse:**
  - home-field caution `mkhf.py` (115 / 112 / 124)
  - chase timeout `mkct.py` (108 / 92)
  - party controller for central maps `mkpc.py` (131, but worse on 00breadcrumbs and
    00the-line)
  - no wards (114)
  - Capture fourth emblem (125)
  - the twins (above)
- **Level:** fcN and fcG (123, 126), Bruiser scaling (130), op0 (128), Prospector first
  (129), Tavi third (132), fb (130).
- **Better locally but unconfirmed:** op15 (132), pro (133), proop (135), proop25 (136),
  tv (134), tvop (137), tvopR (139), es_r2m / es_r2f / es_r2a (138 / 137 / 135).
  - es_r2a, the ES r2 second-half average, has the best held-out line: f_hor_h 156 and gs_eq
    146, against v155's 135 and about 132.
- **Danger-response bandit** (1,376 games): today's retreat rule beats falling back and
  fighting for every champion type, so it was left unchanged.

## 7. Why we lose (ladder evidence)

- **Fights at home.** Lab deaths to champions per game, by territory from our side:
  - **In our own half we die 4 times for every kill.** In theirs the trade is even.
  - In profiled local games, 81-84% of our deaths come while retreating.
  - 2.9 deaths a game come within 8 tiles of our own spawn.
  - Both teams credit about 2.7 champions per kill, so they are not fighting in bigger
    groups. They win the fights: 13.5 kills a game to our 8.1.
- **00lost_world.** Against Rusty Epee our team does no camp damage for 150 rounds while the
  enemy clears and banks the central clusters. fc and the softened late-camp rule do not
  fix it on the ladder.
- **01hooks.** Champions trickle into the one central altar area; locally they are dead
  44-58% of turns, and on the lab it is 54 deaths a game.
- **UK-level teams** (QS2isLaw 2,135, policy wonk 2,334):
  - They die 6-10 times a game to our 15 and finish about 300 rounds sooner.
  - They buy Bruiser plus economy emblems (Prospector, Capture, Treasure).
  - They draft Prism and Tavi.

## 8. Open decisions for the owner

1. **A diagnostic window.** May a profiled build of v155 run live for one lab set (50 games,
   about 5 minutes)? It breaks rule 3, so **ask first**.
   - The build is `ws/bots/p_ab3` (`mkprof2.py`), which prints one PF line per champion turn.
   - Download replays with `cambc matches download ID -o FILE.repl26a`. Our team's stdout
     is inside the bundle (the `team-<side>.stdout` member of the zip).
   - Analyse in the style of `deepwhy.py`. This is the most direct way to see why we lose
     fights at home.
2. **Tuned settings plus party fixes.** The owner chose pm_best for now. If revisited,
   build es_r2a plus pm_best's `bot.h` and its 13 party constants, as `ws/bots/es_pm` was
   built: `mkparty.py` anchors on `JOIN_SLACK = 8`, which the ES changed. Then give it a long
   ranked window (most of a day, about 700 games).
3. **Four leftover folders to delete** (unpatched ab3 copies; the safety check blocked their
   removal):
   - `ws/bots/br SCALE=bruiser`
   - `ws/bots/pro EXTRA=prospector`
   - `ws/bots/brpro SCALE=bruiser EXTRA=prospector`
   - `ws/bots/cap EXTRA=capture`

## 9. Suggested next steps

1. Ask the owner about the diagnostic window (decision 1). Fights at home are the biggest
   gap, and no local test reproduces them.
2. Only take lab slots for changes large enough to see (8% or more). Map-specific
   mechanisms have carried over before: the 03homonoliths spawn attack went from 0 of 8 to
   8 of 8, and capture-reward routing gave +23% team gold. 00lost_world and 01hooks are the
   clearest remaining map failures.
3. Keep a confirmed version pinned well before the UK lock, and watch for a seeding freeze.

## 10. Sessions from this night

- **"Fix party maps: chokepoint altars and monolith control"** is done. Its tools are
  `analysis/rebuild/mkparty.py`, `pm*.py` and `wasmdiff.py`, and its write-up is in
  `GROUND-UP-PLAN.md` ("Party maps: BossBot's fuel-starved scan").
- **"Evolution-strategies tuner"** is idle. `analysis/rl/es.py` accepts `ES_LEAGUE=a,b,c` to
  set the league. Run r2 (`ws/bench/es/r2`) finished: 118 generations, running +50.5
  against v155 on its league.
