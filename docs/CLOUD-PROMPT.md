# Brief for CLOUD: the next round of improvements

You are CLOUD, one of two AI agents improving the team **Milk and Potatoes** in
Cambridge Battlecode 2026a. The other agent, LOCAL, wrote this brief. Work in the
GitHub repo **Fwinnera/Dihpository**, branch **`Fwinnera`**: run
`git pull --rebase` before every push, never force-push, and create no other
branches. The deadline that matters is the **Sprint 2 snapshot at 2026-10-24
22:59Z**, played on **maps nobody has seen**, so build rules that work on any
map. Per-map tuning won't carry over.

Read `README.md` (Shared rules, Ladder lock) and the last sections of
`GROUND-UP-PLAN.md` before doing anything. Keep your README section current.

## 1. Where things stand

- **Live bot: version 97**, `ws/bots/v97_submit`, uploaded 2026-10-23 23:21Z.
  It is v93 plus two changes: the late shop buys Bruiser shards instead of
  Power, and a champion below 60% health recalls to heal when recall is safe
  and it isn't standing on a camp.
- **v93** (`ws/bots/seelie_dis050_submit`, zip `seelie_dis050_submit.zip`) is
  Seelie's `py-t04-gem-value` (greatsage plus gold weight 0.3 and a retreat
  fix) plus **disengage**: leave a fight when local strength falls below 0.5 of
  the enemy's. It is the fallback if v97's ranked results slip.
- **Tagged twin for local testing:** `ws/bots/gs_seelie_dis050` is v93 with a
  BOTTAG. Every candidate below is built on it with `analysis/mkfixes.py`.
- `ladderbench.py` restores `v97_submit`, verified against `v97.zip`.
- **Rating** was about 1,640 (rank ~220 of 760) on 2026-10-23. The top teams
  are at 2,160-2,260.

## 2. Hard rules

1. **Never upload a bot to the website.** The owner decides what goes live.
   Hand over a zip, an untagged `*_submit` folder and the evidence. Test
   submissions are frozen until the owner lifts the freeze.
2. **Unranked games against the live bot need no submission, so you may run
   them.** Queue one match group (5 games) with `cambc match-groups create
   <teamId> --maps ... --sides ... --json`, against teams pinned **by team id**
   (ranks drift within hours), on maps and sides you can compare with earlier
   runs. Before queuing, count our unranked matches in the trailing hour
   (other teams' scrims against us count too); the limit is **50 an hour**.
   Write the group ids into `ws/bench/ladder/<tag>/meta.json` and record the
   use in the README.
3. Take the README's **ladder lock** before anything that touches the
   platform beyond read-only calls. Release it afterwards.
4. Every test arm must parse, carry a `BOTTAG`, pass a smoke game with no
   faults and no `ERROR` lines in its stdout, and differ from its base only in
   the files you meant to change.
5. No credentials in the repo or in chat.

## 3. How to measure: read this before testing anything

These lessons cost a day to learn. Skipping them produces false winners.

- **The winner's curse.** v93 was chosen as the best bot on the local pool, so
  its recorded results are 13-19 gems luckier than its true level. A change
  that does nothing scores −15 to −19 against it. **Never judge a candidate
  against v93's or v97's own recorded run.** Build the candidate with a
  decision-neutral re-roll (`mkfixes.py NAME=change+reroll` or `+reroll2`)
  and judge it against a fresh twin with the same re-roll
  (`gs93_twin2` = reroll, `gs93_twin3` = reroll2).
- **Once you pick a winner among several candidates, it carries the curse
  too.** Confirm it on a fresh re-roll that played no part in the selection.
  Bruiser looked like +28 (z 2.8), then scored −3.3 when re-rolled.
- **Distinct games matter more than repeats.** Most of the variance is
  game-to-game, not replay luck. The standard pool has 320 games (40 maps × 4
  opponents × 2 sides). Use **eight opponents**: the default four plus
  `boss_full,seelie_t04,priority_exp,gs_dis075` (`bench.py --opponents`).
  That gives 640 distinct games. Pool independent arms with
  `analysis/pooled.py --base A,B,C --cand X,Y`.
- **Acceptance test: one-sided z ≥ 1.28 on gems submitted (90% confidence),
  and a win-rate change that isn't negative.** That is what v97 passed (+19.4
  gems, z 1.51, over 640 games against four twins).
- **Local can mispredict the ladder.** Disengage at 0.75 was +48 gems locally
  and −60 on the ladder. Once a candidate is live, check it with unranked games
  against the same pinned teams, maps and sides as earlier runs.
- **Tools:** `bench.py` (`BENCH_MAPS=a,b` restricts maps),
  `analysis/paired.py`, `pooled.py`, `verdict.py`, `subset.py` (`--mono 0.5`
  for monolith-heavy maps), `h2h.py`, `errors.py` (lost turns),
  `study_team.py`, `study_space.py`, `profile_top.py`, `camptable.py`,
  `fetch_team.py`, `itemtable.py`.

## 4. Engine facts that shape everything

Read from inside a match:

- **A deposit is a channel of 0.1 rounds per gem**, within 1 tile of an
  altar. 24 gems takes 2.4 rounds; a 200-gem monolith reward takes 20.
- **Respawn takes 60 rounds. Spawn heals 100% of max health per round. Recall
  takes 5 rounds** (3 with a Home emblem).
- A kill pays 100 gold **plus everything the victim carried**. Assists pay
  nothing, and there is no passive gold.
- Each team has one active ward, with a 10-round cooldown.
- Ranged champions either move or basic-attack in a turn, not both.
- **Monolith camp groups hold 35% of all gems on the 40 maps** (mean 257 gems,
  361 gold and 24,086 health, against 16 gems for an ordinary group). On ten
  maps they hold half or more. Our camp choice skipped them until the raid
  candidate (`ws/bench/camptable.json`).

## 5. Already tested: don't repeat these without a new idea

Each change was tested alone on v93, judged against unselected twins:

| change | result |
|---|---|
| health gate (retreat at 60% when enemies are near) | −108 gems; hurt champions get chased down |
| removing the `gap <= 4` attack accept | −159; it is how champions fight back |
| Willow farms instead of escorting | −74 |
| safer Willow escort | −13 |
| travel weight 0.6 / 0.4 (farm further out) | −15 / −24 |
| bank at 36 / 48 gems | +8 / −3: noise, and bigger loads take longer to deposit |
| cached camp design stats (teammate's fix) | −45 |
| stale-vision replan (teammate's fix) | never fires; neutral |
| monolith raid from round 700 / 900 | −10 / +11 overall; +26 to +33 on monolith-heavy maps but z under 1, and win rate falls |
| Treasure first, the Vesper Vale draft swap | more gold, flat gems (tested on greatsage) |

## 6. What the top teams do that we don't

Profiles of ranks 1-5 on 2026-10-23 (25-60 recent ranked games each) against our
v93 and greatsage ladder games, from `analysis/profile_top.py`. Rerun it as
`profile_top.py "top1:prism best girl" "top2:willow best girl"
"top3:Intercontinental Fish" "top4:procless" "top5::3" us`; the data is in
`ws/bench/top1..top5`. Positions are on the line between the bases: 0 at home,
1 at the enemy base.

| | #1 prism best girl | #2 willow best girl | #3 Intercontinental Fish | #4 procless | #5 :3 | **us** |
|---|---|---|---|---|---|---|
| time hitting camps | 16.5% | 17.4% | 16.7% | 17.9% | 17.4% | **6.5%** |
| time fighting champions | 4.6% | 4.5% | 4.5% | 6.6% | 5.1% | 7.1% |
| deaths a game | 7.1 | 4.8 | 11.1 | 8.8 | 9.1 | **21.3** |
| kills / carrier kills | 9.0 / 3.3 | 9.0 / 3.3 | 8.9 / 2.4 | 7.2 / 1.6 | 7.0 / 1.9 | 5.5 / **0.6** |
| camp clears a game | 42 | 58 | 46 | 61 | 59 | 41 |
| gems per pickup | 19.9 | 15.6 | 18.6 | 14.4 | 12.1 | **8.4** |
| zero-gem pickups | 27% | 19% | 27% | 30% | 35% | **72%** |
| monolith gems a game | 167 | 50 | 104 | 16 | 24 | **0** |
| clear depth / deposit depth | 0.4 / 0.5 | 0.3 / 0.4 | 0.3 / 0.4 | 0.2 / 0.4 | 0.3 / 0.4 | 0.2 / **0.0** |
| deposits / gems each | 16.5 / 51 | 29.2 / 27 | 19.4 / 44 | 22.7 / 34 | 13.3 / 49 | 9.6 / 34 |
| wards a game | 141 | 82 | 152 | 82 | 174 | **271** |

Our ladder sample covers five maps, against the many maps of the top teams'
games, so treat the pickup rows with care. The farming, death and draft rows
are robust.

- **Draft:** Vesper Vale and Heart of Ruin appear in 85-100% of games for all
  five. Prism is first pick for #1 and #2 and is fielded by #5 in 76%. **None fields Varg**; our camp
  clearing is built around Varg's splash and Willow's escort.
- **Items:** Treasure is the first emblem for #2, #3 and #4 and the second for
  #5. Four of the five stack Bruiser (28-38 emblems a game); #3 mixes Power (25)
  and Bruiser (12). They hold 35-45 emblems a game; we hold about 20.
- **Banking:** they bank at the central altar (depth about 0.4-0.5). #1's Prism
  carries a median peak of 196 gems and deposits at the very end, as a
  finisher.
- **Monoliths:** #1 and #3 take 0.5-0.7 a game, three or more champions at
  once, around round 1,000.
- **The biggest robust gap is farming time:** all five top teams spend 16.5-17.9%
  of the game hitting camps; we spend 6.5%. The owner sees the same thing
  watching our games: champions wandering, poor pathing, and hurt champions
  taking fights.

## 7. The plan, in order

Each item: build it with `mkfixes.py`, test it under section 3, record the
result whether it passes or fails.

1. **Find where our champions' time goes, then fix the biggest leak.** We spend
   6.5% of the game hitting camps; the top five all spend 16.5-17.9%. Build a logger like
   `ws/bots/gs_fightlog` (see `analysis/mkdisengage.py --log`) that prints each
   champion's `status` label every turn: farm, travel, bank, retreat,
   disengage, combat, capture, shop, heal, idle. Profile v97 over the local
   pool. Then attack the largest non-farming state: long walks between camps,
   re-choosing objectives mid-route, returning to camps that are respawning,
   or waiting near altars. This is the owner's "wandering" observation, and it
   should be the largest lever left.
2. **Treasure first, on v97.** Four of the top five open with it. On greatsage
   it gave more gold but flat gems; with v97's lower deaths the gold may now
   convert. It's cheap to test: the `gs_treasure` build order on the v97 base.
3. **Hunt carriers and channellers.** The top teams kill gem carriers 1.6-3.3
   times a game; we manage 0.6. A champion depositing is stationary for 0.1
   rounds per gem. Raise visible carriers, and especially enemies depositing at
   altars, in `combat.choose_enemy`'s scoring, within the disengage rule.
4. **Monolith raids with a protected deposit, only on monolith-heavy maps.**
   Gate the raid on the map's monolith gem share (at least 0.5, computed at the
   start of the game) so it works on unseen maps. Fix the known failure: a
   200-gem reward is a 20-round deposit, and a lone carrier dies doing it.
   Have the raiders escort the carrier and guard the altar during the channel.
   Test it on the monolith-heavy maps (`BENCH_MAPS`, `subset.py --mono 0.5`)
   with several re-rolls, because those maps swing by hundreds of gems.
5. **Draft towards the top teams' core, with the behaviour to match.** All five
   field Vesper Vale and Heart of Ruin, and none fields Varg. A straight swap
   failed earlier (Heart of Ruin −42; swapping out Varg −287), because our
   code relies on Varg's splash. A real change needs Heart of Ruin played as a
   front-line tank (shield and dash) and our camp-clearing maths not tied to
   Varg. It is the biggest structural gap, and a good fit for the C++ rebuild.
6. **The C++ track** (gs_cpp parity, then fight simulation) continues, but
   items 1-4 are faster wins before the snapshot.

**Quick ladder check:** after any candidate the owner makes live, send **5
unranked games** (one match group) against one of the pinned `db_base` teams
on the maps `01islands,00swirl,01elk_arena,00quadrants,01yellow_brick_road`,
sides `a,b,a,b,a`, and compare with `ladderbench.py --compare v93_live <tag>`.
Five games give a lean, not a verdict; 20 (all four pinned teams) is the
minimum for a real check. LOCAL's v97 check at 23:29Z: gems +68.6 and gold
+1,334 against v93 on the same five pairings, 0-5 both.

## 8. Deliverables

For each experiment: the generator change (extend `analysis/mkfixes.py`), the
built arms, a smoke result, the pooled 640-game verdict against fresh twins,
and a write-up appended to `GROUND-UP-PLAN.md`, with the README's CLOUD
section updated. When something passes, build an untagged `*_submit` copy,
bundle it with `cambc bundle`, confirm its `main.py` matches the live bot's,
and hand the zip to the owner with the evidence. Do not upload it. Report back
in the README's "Notes for LOCAL".
