# Prompt: improve the bot before the UK qualifier (written 7 Nov 2026, 18:30Z)

Paste everything below the line into the AI that will work on the bot.

---

You are improving team **Milk and Potatoes**' C++ bot in Cambridge Battlecode 2026a
(https://2026a.battlecode.co.uk). The owner's goal is **top 8 among UK student teams at the UK
qualifiers on 11 November**: eight UK and eight international teams reach the final on 18 November.
Submissions are expected to lock around **10 Nov 23:59 GMT**; confirm the exact time on the site
first.

**Where we stand (7 Nov, 18:20Z).** Live is **v180 = mg4** (`ws/bots/mg4_submit`), pinned. It scores
rating 1,766, rank 206. The UK top-8 line is about 2,160, so we are about 400 points short. Tell the
owner plainly what is and is not realistic. Seeding comes from the ladder, so every point gained
before the lock still helps the bracket.

**Your job:** find changes that make v180 measurably stronger, prove each one on the platform, and
never leave the team worse off. A good outcome is a safe gain, a hard rule, and v180 restored when
nothing beats it.

## 1. Read first (in this order)

1. `docs/HANDOVER-CLOUD.md`: engine 3.0.0, the current state, the tools that decode replays, and
   what was rejected.
2. `docs/HANDOVER.md`: the rules, the lab method and the 3-4 Nov findings.
3. `README.md`: the shared rules and the **ladder lock** (who holds it and what is live).
4. `GROUND-UP-PLAN.md` from "CLOUD: why we die at home" onwards: the evidence behind everything
   below. It is append-only; add your own results there as you go.

## 2. Setup

- **Repo and branch:** GitHub `Fwinnera/Dihpository`, branch **`Fwinnera`** only. Run
  `git pull --rebase` before every push; never force-push.
- **Checkout:** on the owner's Mac it is `/Users/faeezaullyar/Claude/battlecode`. If a pull refuses
  because untracked local files would be overwritten, move just those files into a git-ignored
  backup folder (for example `ws/bench/_local_backup_DATE/`), never delete them, then pull.
- **The platform runs engine 3.0.0** (cambc 5.0.0, 128 maps; nerfs to Vesper Vale, Vendetta,
  Marcella, Heart of Ruin and Prism).
  - The Mac's CLI is `~/Library/Python/3.9/bin/cambc`, still **4.0.0**, so local games there run
    the old engine. Install cambc 5.0.0, make a fresh workspace with `cambc init`, and copy the bots
    in (src/ only).
  - In a cloud container, follow `analysis/cloud/README.md` and the engine-3.0.0 scripts in
    `analysis/cloud/e3/`.
- **Decoders:** the replay decoders (`analysis/cloud/read3.mjs`, `actions3.mjs`) need Node 22. Node
  is not installed on the Mac.
- **Login:** the owner runs `cambc login` personally.

## 3. Rules: do not break these

1. **Never use credentials that appear in chat.**
2. **Take the README ladder lock** before any platform action (`cambc submit`,
   `submissions activate`, `match-groups create`): edit the block, commit and push. Release it
   after re-pinning.
3. **Only untagged, smoke-tested `_submit` builds go live**: no debug prints and `DEBUG = false`.
   Smoke test with `cambc run --release` from both sides: exit 0, no ERROR lines, no faults, empty
   stdout.
4. **`cambc submit` switches the team to follow-newest:** re-pin with
   `cambc submissions activate N` and check `Live: N` before relying on it. Keep notes to 80
   characters or fewer. Re-activating an older version rebuilds it, and the queue can take 10+
   minutes; selecting another version cancels a pending build.
5. **Quota: 50 unranked match groups an hour** (5 games each); a three-set lab test uses 30.
6. **One live candidate at a time.** Write the keep or reject rule down in `GROUND-UP-PLAN.md`
   *before* the result arrives, and follow it.
7. **Files:**
   - Use `rm` only with `"${var:?}"`, and never delete data permanently. A safety check blocks
     risky removals; leave those to the owner.
   - Put downloaded data in a fresh folder and read it with `python3 -I`.
   - Copy a bot by its `src/` only (the `.cambc` cache holds absolute paths).
   - zsh does not word-split `$var`; use bash for loops over "name ARGS" pairs.
8. **Endgame:** pin the final entry by about **10 Nov 18:00Z**. Only upload after that if the owner
   asks. Then confirm `Live:` and record it in the README.

## 4. How to judge a change on engine 3.0.0

- **The ladder lab is the test.** Use `analysis/cloud/lab.py` / `labrun.sh` (or the
  `analysis/rebuild/` copies): three sets of 10 pinned teams × 5 maps.
  - Pair candidates against the engine-3.0.0 baselines: `e3v166*` (v166: 86 of 150; re-deals of
    v166 84 and 80) and `mg4*` (v180: 78).
  - Arms are in `analysis/cloud/lab/`; copy them into `ws/bench/lab/`.
  - `labmargin.py` gives paired gem margins.
- **Games are deterministic per build.** A candidate differs only in the games its code reaches,
  and any change in fuel use re-deals them, so a broad change lands within a few wins of its
  baseline by chance.
  - The lab resolves about +-12 wins in 150 at two standard errors.
  - Every change tried on 3.0.0 lost 9-11 of the games it changed, on balance.
- **Local screens do not choose.** On 3.0.0, screens against our own older bots ranked every
  rejected candidate above v166. Use them only to catch breakage. The gs_mix_camp screen
  predicted fight changes somewhat.
- **Gate map fixes inside code that already runs only on those maps** (BossBot, the policy
  checks). Then every other game stays identical, and ladder win rates on those maps measure the
  fix directly. That is how mg4 was shown: the maps it changed went from 7/69 to 20/46.
  - Ranked play gives about 700 games a day; mine them per map, per roster size and per mode.
  - An extra check that runs on every map re-deals the whole pool (fuel is counted per
    instruction).
- **The bot is fuel-limited:** fuel-only dead loops cost strength steeply, and about 120 turns a
  game end in a low-fuel bail-out before any action. Changes that add work every turn will cost
  you.

## 5. Already tried and rejected (do not repeat without a new reason)

- **On the 3.0.0 lab:**
  - hb3 (no recall right after losing health; withdraw hitting back) 77
  - fu1 (hb3 + cheaper re-planning) 75
  - hr6 (Heart of Ruin for Ryth) 77
  - hr70 (heal-recall at 70%) 76
  - rs4 (a recall variant) 81
  - tv1 (Tavi for Ryth) 78
- **Earlier, on 2.0.0** (level or worse):
  - farm-don't-chase, Prospector, Tavi + Prospector + softer late-camp rule
  - the ES-tuned settings
  - escorts and squads, assist-a-teammate (lab 62), early gold weighting
  - home-field caution, chase timeouts, party mode for central maps
  - Bruiser builds, no wards (much worse)
- **The danger response** (retreat / fall back / fight) was tested on-policy: today's rule is best.

## 6. Where the evidence says the gap is

- **Fights and map control, not bugs.** Mining 1,710 ranked games found no map bug left outside
  mg4's fixes. In losses we do 64k monster damage to their 107k, earn 4,032 gold to their 6,982,
  and die 19 times to their 6.
- **Isolation.** Our champions have no teammate within 5 tiles for 57% of their turns (ladder teams
  42%), and we die outnumbered (1v2, 1v3). The top UK teams keep a teammate within 4 and die about
  once a game per champion.
- **Roster size:** solo-controller win rate is 63% with 3 champions, 55% with 4 and 48% with 5. The
  five-a-side game is where we lose most.
- **Drafts after the patch:** the top ten pick Heart of Ruin in nearly every game, Vendetta and
  Marcella in most, and Vesper Vale often. We draft Varg, Vendetta, Vesper Vale, Ryth and Marcella;
  three of those were nerfed in 3.0.0. Our Ryth collected 93 gems a game on the 3.0.0 lab against
  158-331 for our other picks. Swapping in Tavi or Heart of Ruin alone did not help.
- **Open map items:**
  - 00anvil plays solo under mg4, 1/5, a three-a-side deathmatch. mg6 (`PARTY_MONO 0.75` returns it
    to party mode) is not built yet.
  - 04sanctum: we will not walk into an enemy-held centre altar, so we deposit nothing. A real
    behaviour change that local opponents cannot test.
  - Stronger-opponent losses: 01big_world 0/9, adgato_gemcombat4 1/21, 00great_wall 1/17,
    03contours 1/11.

## 7. Suggested plan for the three days

1. **Mine before building.** Decode a sample of our five-a-side losses and the worst maps with
   `read3.mjs` / `actions3.mjs`, and compare them with a top UK team's games
   (`cambc matches download`, `fetchteam.py`). Find the specific moment the game turns: the first
   lost fight, the first lost camp, an altar we abandon.
2. **Cheap, gated map fixes first.** Build mg6 (00anvil back to party mode) and judge it by ranked
   win rate on 00anvil and the maps it touches. Look for more fixes that run only where they
   apply.
3. **One structural bet at a time,** chosen from the evidence (the five-a-side game, cohesion,
   roster). Write its keep rule first, run the three-set lab, then a long ranked window if the
   lab is level. Revert to v180 if it fails.
4. **Keep the record:** append each result to `GROUND-UP-PLAN.md`, keep the README lock current,
   and pin a confirmed version by 10 Nov 18:00Z.
