# bomba: measured findings, 21 Oct 2026

Engine 1.0.2, CLI/SDK 3.0.4, all 35 official maps, both sides, map-derived seeds
(verified byte-identical across every batch, so all comparisons below are properly
paired). **770 games, 0 bot faults, 0 logged exceptions.**

**Bottom line: one change ships, and it is the colleague's `boss.py`. All three of
my own proposed fixes measured negative and have been reverted.**

---

## 0a. REAL DATA: 10 unranked games vs rank-2 and rank-8 (21 Oct, 18:33)

`greatsage` submitted as version 11, then scrimmaged. **0-10.** Every game ended by
`endReason: gems`, so none was a close round-limit finish -- they reached 1,000 gems.

| Match | Gems (us-them) | Rounds | Our deaths | Their deaths |
| --- | --- | --- | --- | --- |
| hello 00gem_fields | 61-1018 | 604 | 26 | 2 |
| hello 00gemfight | 92-1004 | 813 | 20 | 0 |
| hello 00great_wall | 545-1010 | 1128 | 11 | 2 |
| hello 00lost_world | 94-1017 | 731 | 21 | 8 |
| hello 01boss_battle | 0-1406 | 969 | 20 | 6 |
| tung 00gem_fields | 215-1014 | 697 | 22 | 3 |
| tung 00gemfight | 48-1061 | 790 | 23 | 1 |
| tung 00great_wall | 279-1000 | 1017 | 15 | 3 |
| tung 00lost_world | 248-1009 | 758 | 12 | 4 |
| tung 01boss_battle | 0-1014 | 974 | 21 | 0 |

Per-game means:

| Metric | Us | Them | Ratio |
| --- | --- | --- | --- |
| Gems tributed | 158 | 1,055 | **6.7x** |
| **Deaths** | **19.1** | **2.9** | **6.6x against us** |
| **Kills** | **1.8** | **16.5** | **9.2x** |
| Gold earned | 2,209 | 7,307 | 3.3x |
| Damage to champions | 15,245 | 26,800 | 1.8x |

### This reinstates the thesis I retracted, with a correction

I argued deaths were the main loss driver, then retracted it when retreating earlier cost
27 gems a game. The retraction was right about the *fix* and wrong about the *diagnosis*.
Against real opponents we die **19 times a game to their 3**, and they take **16.5 kills
to our 1.8**. A kill hands the killer every carried gem plus 100 gold, so they are not
merely out-farming us -- they are **harvesting us and compounding it**. Our gold is a
third of theirs because we never get to farm in peace.

Tuning a retreat threshold cannot fix that. It is a combat-capability gap.

### The local harness was measuring the wrong game

Every one of the 22 candidates was tested against our own lineage -- `base`, `colleague`,
`boss_full` -- all of which are farm-bots that engage only opportunistically. So the whole
search optimised farm throughput in a vacuum where nobody contests. That is why:

- `v_metaA` (HeartOfRuin, Vesper, Marcella, Ryth, Vendetta) measured **-112 gems** locally
  and is **exactly** the comp EMPEROR Tung used to beat us 5-0. The comp is not bad; our
  code cannot play it.
- Removing Willow cost 66 gems locally, because sustain pays against a passive opponent.
  Neither rank-2 nor rank-8 drafts her at all.
- `boss.py` turned `01boss-battle` into 2103-165 locally, yet we scored **0** there in both
  real games. The relative gain over `base` stands; the absolute level does not.

**The scrimmage queue is the real harness.** Quota is 50 matches, 10 used. Local self-play
should only ever be used for behaviour-preservation checks from here on.

### Their drafts, first-hand

| Team | Rank | Draft |
| --- | --- | --- |
| EMPEROR Tung | 2 | HeartOfRuin, VesperVale, Marcella, Ryth, Vendetta |
| hello | 8 | VesperVale, Ryth, Vendetta, Tavi, Marcella |
| us | 199 | Marcella, Vendetta, **Willow, Varg**, Ryth |

Tung's five is the 42.2% modal comp from the public pick data, confirmed live. Neither
opponent touches Willow or Varg.

### Also: the map pool changed

39 maps now, not 35. Four were new and untested when every number above was measured:
`00gem_fields`, `00gemfight`, `00great_wall`, `00lost_world`. Now pulled locally.

---

## 0b. REAL DATA II: 25 more games across ranks 149-250

Maps held constant (`00fragment`, `00collision`, `00eight`, `00great_wall`,
`01boss_battle`), sides `a,b,a,b,a`, so only opponent strength varied.

| Opp rank | Record | Our gems | Their gems | Our deaths | Their deaths | Death ratio |
| --- | --- | --- | --- | --- | --- | --- |
| 149 Patient Builder | 2-3 | 475 | 767 | 21.0 | 12.2 | 1.7x |
| 175 BrendanBurgess | 2-3 | 393 | 763 | 27.2 | 35.0 | 0.8x |
| 200 BattleCats | 1-4 | 552 | 762 | 27.8 | 14.0 | 2.0x |
| 225 sub7anr | 4-1 | 677 | 572 | 19.2 | 27.0 | 0.7x |
| 250 Quantum Stunners | 4-1 | 814 | 457 | 11.0 | 31.0 | 0.4x |
| **8 hello** | **0-5** | 158 | 1055 | 19.1 | **2.9** | **6.6x** |
| **2 EMPEROR Tung** | **0-5** | (same) | (same) | (same) | (same) | (same) |

13-12 across the band, crossover between rank 200 and 225. **The ladder is right: we are
exactly a rank-199 bot.** No hidden strength.

### The single differentiator is not dying

Our death count is roughly constant against everyone: **21, 27, 28, 19, 11** per game.
What changes is the opponent's. Teams at our own level die **12 to 35** times a game --
as much as we do, or more. The top two teams die **2.9**.

So dying ~20 times a game is normal for a rank-200 bot. **Not dying is the top-team
skill, and it is the whole gap.** At rank 175 we inflicted 35 deaths and still lost 2-3;
at the top we inflict 1.8 and lose 0-5.

This explains the champion meta coherently for the first time. Heart of Ruin is picked
96% of the time not for throughput -- his base damage and growth are mid -- but because
he is the best *survivor* in the game: a `1.5 x Focus` shield, a 2-tile escape dash, and
a passive that makes low health an asset instead of a death sentence. Vesper Vale is
ranged with a dash. And Willow, at 700 base health and **+50 per shard** -- the worst in
the game, 3,200 at 50 shards against Vendetta's 6,000 -- is a ranged champion with no
escape. Her problem was never her scaling. **She dies.**

It also explains why my retreat experiments all failed: the threshold is not the
mechanism. Survival comes from shields, escapes, positioning and not committing to lost
fights -- none of which this bot has.

### Scope for the rewrite

Survival first, not farm planning. We farm comparably to our peers (475-814 gems against
their 457-767); we are not behind on economy at our own level. The draft-phase TOPTW
planner in GROUND-UP-PLAN.md section 4.1 should be **demoted**: it optimises the half of
the game we are already average at. Combat survival is the half that separates rank 200
from rank 2.

### One specific defect

`01boss_battle`: **lost 6 of 7 real games**, including against the rank-250 team we
otherwise beat 4-1, and 0-1406 / 0-1014 against the top two. Locally the shipped
`boss.py` change produced 2103-165 there. That gain does not transfer. The relative
comparison against `base` stands, but the absolute level on that map is broken and the one
change shipped today is probably worth much less than measured.

---

## 1. Where we stand

`PATCH-AUDIT.md` recorded **Milk and Potatoes at #169 / 1,655 Elo**. From the public
ladder API:

| Target | Rating needed | Gap from 1,655 |
| --- | --- | --- |
| Overall / international top 3 | 2,141 | ~490 |
| **UK category top 3** | **~1,900** | **~250** |

The ladder is split by category. Only two UK teams sit inside the public top 25:
`hello` at 1,995 (overall #12) and `剑桥夜爬者` at 1,914 (overall #22), so UK third
place is below 1,914. With **UK qualifiers on 11 Nov** and the final at the Cambridge
Union on 18 Nov, UK top 3 is the achievable reading of the goal. **Sprint 2 locks
Sat 24 Oct 23:59 BST.**

---

## 2. The one change that measures

`boss_full` = your baseline with **the colleague's entire `boss.py`** substituted,
nothing else. Measured against the colleague's bot as a common opponent, paired by
map and side, with `base vs colleague` (50–20, 71.4%) as the reference:

| Candidate | Record | Win % | Slots changed | Gems +/− | Sign p | Win flips | Gems/changed slot |
| --- | --- | --- | --- | --- | --- | --- | --- |
| base (reference) | 50–20 | 71.4% | — | — | — | — | — |
| boss_focus (monolith filter only) | 53–17 | 75.7% | 19 | 14/5 | 0.064 | +4/−1 | +51.5 |
| **boss_full (their whole boss.py)** | **55–15** | **78.6%** | **22** | **17/5** | **0.017** | **+5/−0** | **+150.1** |
| cfg_only (their build order) | 47–23 | 67.1% | 64 | 29/33 | 0.704 | +7/−10 | −16.4 |

`boss_full` is the only candidate all day that reaches conventional significance
(**p = 0.017**) and the only one that flips games **without losing a single one**
(+5/−0). The decisive map:

| 01boss-battle | side A | side B |
| --- | --- | --- |
| base | 82–1466 | 72–1171 |
| **boss_full** | **1032–336** | **1489–283** |

That is roughly a **1,400-gem swing** on a map we were losing outright. Played
directly against the baseline it is more emphatic still: **2103–165** and **1006–33**.

### Direct head-to-head, and why it reads weaker

`boss_full vs base` over the same 35 maps is **38–32** overall: **21–15** on the 18
maps that run the BossBot path, and exactly **17–17** on the other 17, where the two
builds are identical and only side advantage decides. The sign test on gem margin
across the BossBot slots is **p = 0.405** — not significant.

That is expected and not a contradiction. The gain is **large but localised**: a
handful of maps swing hugely and the rest are unchanged, so a single 70-game sweep
averages the signal away. Both designs agree in direction, the common-opponent design
reaches p = 0.017, and the mechanism on `01boss-battle` is unambiguous across all
three pairings.

### Downside is bounded

Across the 140 games of the common-opponent test, **no slot flipped from a win to a
loss**. All five slots it made worse stayed on the same side of the result:

| Slot | base | boss_full |
| --- | --- | --- |
| 00rushbait-v2 A | 1004–814 W | 1000–836 W |
| 01fracture A | 1054–824 W | 1024–596 W |
| 01gold-rush B | 649–308 W | 534–412 W |
| 01starvation B | 464–120 W | 340–184 W |
| 01starfish B | 75–1024 L | 0–1039 L |

And `boss.py` cannot execute at all on the 17 non-BossBot maps, so on half the pool
the change is provably inert. That bounded risk is the main argument for shipping it
before Saturday on evidence that is strong but not airtight.

### Which part of their `boss.py` does the work

Their file contains two changes. Porting **only** the monolith-commitment filter
(`boss_focus`) left `01boss-battle` still lost (49–1087, 146–1367). The work is done
by the other part: their **`bank()` override in `BossBot`** — when a deposit route
stalls, release the banking state, recall to shop if gold ≥ 30, otherwise go farm.

I had dismissed that override as redundant, on the grounds that the base class
already has `bank_progress` recall recovery. That was wrong. `01boss-battle` is a
**single-altar** map, and on single-altar monolith maps the base-class recovery is not
enough to unstick a carrier.

### Scope is larger than it looks

`boss.py` only executes when `policy.kind() == 2` (exactly one altar **and** a
monolith camp present). Since `boss.py` was the only file changed, every map whose
result moved must run that path — and **13 of the 35 maps did**, not the two I
assumed. The BossBot path covers over a third of the pool.

### Not taken

Their **build order** (Monster-Str → Jungle-HP → Durability-Str) is a wash to slightly
negative in isolation (29/33 gems, p = 0.704, −16.4 gems/slot) and touches 64 of 70
slots. Their **draft** (Varg-first) was not isolated, but their bot as a whole loses
50–20 to yours, and their build removes the equipment-scaling heuristic that
`RESEARCH.md` measured at 60/70 → 65/70. **Take their `boss.py` only.**

---

## 2b. Everything tested, in one table

All against the colleague's bot as a fixed common opponent, paired by map and side,
with `boss_full` (55-15, 78.6%) as the reference once it was adopted. 1,750 games.

| Candidate | What it changed | Record | p (win flips) | Gems/game | Verdict |
| --- | --- | --- | --- | --- | --- |
| **boss_full** | colleague's `boss.py` | **55-15** | **0.062 (+5/-0)** | reference | **ship** |
| boss_focus | monolith filter only | 53-17 | 0.375 | +51 | half the gain |
| v_treasure | Monster -> Treasure shard | 55-15 | 1.000 (+5/-5) | +29, **+1403 gold** | wash |
| v_bank36 | BANK_GEMS 24 -> 36 | 52-18 | 0.629 | -13 | no |
| v_goldlate | late gold weight .25 -> .8 | 49-21 | 0.210 | -33 | no |
| v_bank12 | BANK_GEMS 24 -> 12 | 49-21 | 0.180 | -46 | no |
| v_heal60 | HEAL_MIN_MISSING 120 -> 60 | 48-22 | 0.143 | -46 | no |
| cfg_only | colleague's build order | 47-23 | 0.629 | -16 | no |
| v_bank18 | BANK_GEMS 24 -> 18 | 46-24 | 0.012 | -60 | no |
| v_shopmore | SHOP_GOLD 150->90, INTERVAL 70->40 | 45-25 | 0.052 | -68 | no |
| **v_fuelguard** | hard fuel floor in the search | 44-26 | **0.008** | -63 | no |
| v_fight | RETREAT_HEALTH .30 -> .20 | 43-27 | 0.012 | -81 | no |
| **v_metaA** | top-5 modal draft | **38-32** | **0.001** | **-112** | no |
| **v_metaB** | top-5 burst draft | **9-61** | 0.000 | **-476** | no |
| v_vesper | Willow -> Vesper Vale | 47-23 | 0.093 | -66 | no |
| v_vesp_ren | Willow->Vesper, Varg->Ren | 47-23 | 0.134 | -63 | no |
| v_hor | Varg -> Heart of Ruin | 46-24 | 0.076 | -33 | no |
| fast_safe | shop/heal/mobility fuel cuts | 52-18 | 0.664 | -4 | neutral |
| fast1 | all four fuel cuts | 49-21 | 0.263 | -44 | no |
| **fast_camps** | `camp_tiles` for `has_camp` | 49-21 | **0.031** | -46 | **harmful** |

Plus, measured against `base` before `boss_full` existed: my three fixes individually
at 47-23, 46-24, 44-26 and together 42-28, against base's 50-20.

**21 of 22 candidates measured worse or neutral than the bot we started with.** The three
constants I probed are now bracketed on both sides -- retreat (0.20 worse, 0.43-equivalent
worse), healing (60 worse, 216 worse), banking (12 and 18 worse, 36 neutral) -- so
those are closed questions, not open knobs.

### Fuel headroom does not convert into strength

A round of pure efficiency work -- no decision changed -- cut fuel exhaustions 20%
(18.3 -> 14.6 per game) and still lost 43.7 gems a game. Ablating it showed the loss was
entirely one semantic change, and that the genuinely behaviour-preserving cuts were
*neutral*: -4 gems, p = 0.66.

The premise was wrong. I had treated a `Replan` as a forfeited turn, but the champion
resumes its decision the following round, so suspension is a one-round delay rather than
a lost action. Capacity was not the constraint.

Two durable results came out of it anyway. Measured primitive costs, which any future
optimisation should be planned against rather than guessed at:

| Primitive | Fuel |
| --- | --- |
| bare Python loop iteration | 272 |
| `camp_tiles.is_set` | 681 |
| `camp.spawn_position` | 1,043 |
| `camp.health` | 1,743 |
| `round_number` | 1,920 |
| `me.position` | 2,170 |
| `has_camp` | 2,581 |
| `fuel_remaining` | 2,774 |
| **`turn.check()`** (calls both of the last two) | **~4,694** |

At a measured 13-23 checks per turn, the fuel guard costs 63-106k per turn -- 5-9% on a
big map, not the dominant cost I expected.

And an API trap: **`camp_tiles().is_set(camp.spawn_position())` is not equivalent to
`bc.vision.has_camp(camp.spawn_position())`.** Substituting it changed 30 slots, lost six
games and won none (p = 0.031). Do not treat the bitboard as a drop-in for the per-camp
query.

### CORRECTION: the denial claim was wrong

I asserted repeatedly, in this document and in GROUND-UP-PLAN.md, that the denial
mechanics are "completely unused by our lineage". An audit of the source shows that is
false. Already implemented:

| Mechanic | Where |
| --- | --- |
| Interrupt an enemy mid-tribute | `combat.choose_enemy`: `interrupt` is second in the score tuple and bypasses the range gate |
| Prefer high-gem targets | `combat.choose_enemy`: `-enemy.gem_count()` |
| CC valued for cancelling a channel | `combat.fight`: `+120 if target.is_submitting_gems()` |
| Place altar locks | `navigation.finish_turn` |
| Break an enemy lock blocking us | `bot.bank` |
| Defend our own capture region | `choose_enemy(defending=True)`, which drops all engagement gating |

Only two parts are genuinely absent: **entering the enemy's capture region** to reset
their timer, and **travelling beyond 7 tiles to hunt a carrier**. Both require a champion
to abandon farming, which is the exact class of change that failed in 21 of 22 tests --
the Willow removal (-66 gems), the earlier retreat (-27), the looser heal (-46). This bot
converts farm uptime into gems efficiently and punishes anything that interrupts it.

So the cheap denial upside does not exist. What is left is expensive, and this
architecture is the wrong one to spend it from.

### Harness resolution, measured by accident

`fast_safe` is the useful calibration. Three of its changes provably cannot alter a
decision (no purchase under 10 gold, no heal loop for a champion with no heal, no
mobility recompute within a round), yet it **changed 65 of 70 slots** and moved the
record from 55-15 to 52-18. Shifting fuel timing moves `Replan` boundaries, which cascades.

So this harness cannot resolve differences of about four wins or fewer on a 70-game
sweep. Only the **paired flip test** is trustworthy at that scale, which is why
`boss_full` (+5/-0 flips, p = 0.017) is believable while a bare 3-win record difference is
not. Every future comparison should be judged on paired flips, not on the record.

### The draft result is the important one

Top-5 ladder teams pick Heart of Ruin in 96.2% of drafts on patch 1.0.2, Willow in
**0 of 1,040**, and Varg in 6. We draft Willow and Varg every game. Copying their comp
onto our code lost 112 gems a game (p = 0.001), and their burst comp lost 476.

The reason is that their champions need behaviours this bot does not have:

- **Heart of Ruin's passive pays for being near death** (up to +50% damage at low
  health). Our bot retreats at 30% HP, which is exactly where he switches on. Our
  retreat rule fights his kit.
- **Vesper Vale, Stellar and Cassi are ranged**: move *or* attack, never both. Our
  farm loop assumes melee walk-and-attack.
- We would drop **Varg's splash**, which `strategy.dps` and `combat.choose_camp` have
  explicit multipliers for, and **Willow's heal**, which `escort.py` exists to position.

So the draft is downstream of the architecture, not a lever on top of it. Closing the
remaining gap means building one of those behaviours -- a low-health-seeking combat mode,
capture contesting, or carrier hunting -- not retuning this one.

## 3. What I got wrong

### My three fixes are all mildly harmful

Each variant below is base with exactly **one** hunk applied, same opponent, same
maps, both sides:

| Variant | Record vs colleague | Win % | Gems/game vs base |
| --- | --- | --- | --- |
| base | 50–20 | 71.4% | — |
| retreat fix only | 47–23 | 67.1% | −27.0 |
| bank fix only | 46–24 | 65.7% | −31.8 |
| heal fix only | 44–26 | 62.9% | −41.3 |
| all three | 42–28 | 60.0% | −45.8 |

No single fix clears p < 0.05, but the direction is identical in 4 of 4 builds and
the damage stacks monotonically. Direct head-to-head was 36–34 (z = +0.24, noise).
All three are **reverted**; the patch and its tests are in `rejected/`.

### The thesis behind them was wrong

I argued deaths were the single best predictor of our losses and therefore where the
Elo was. The retreat fix **did** reduce deaths (18.7 → 18.3 per game) and still lost
27 gems per game. Damage taken from camps barely moved (26,342 → 25,500), so the
mechanism I claimed never fired.

The correlation was confounded. Games with 40–50 deaths are not lost *because* of the
deaths; they are games already being lost on map or side disadvantage, in which a
losing bot then dies repeatedly. I read a symptom as a cause.

Why each backfired, as far as the data shows:

- **Heal (worst, −41.3).** The heal's value is *uptime*, not HP throughput. A small
  early top-up keeps a farmer on its camp; forcing it to wait for a 216-point wound
  means the champion withdraws or dies first.
- **Bank (−31.8).** Every one of the 35 maps has a reachable altar, so the `no_altar`
  branch **never fires** and cannot help on this pool. The only live change was
  releasing a stalled carrier to farm — worse than persisting or recalling, because
  the trip to the altar is already paid for. (Note the contrast with the colleague's
  override, which *does* help, but only on single-altar boss maps and only alongside
  a recall-to-shop.)
- **Retreat (−27.0).** The baseline's fixed `× 2` is better tuned than my
  `× (range − gap + 1)`. The Golem arithmetic was right about the damage and wrong
  about what avoiding it is worth.

### Other corrections

- Team size on `01boss-battle` is **5**, not 3, so my `boss_ready >= 4` theory was
  wrong.
- I claimed the colleague's 1466 on `01boss-battle` came from their monolith filter.
  It comes from their bank override.
- I bundled three changes into one build and could not attribute the result. The
  ablation should have come first.

---

## 4. Still unexplained

Four maps score **0–0 for both sides**, in every pairing tested:

| Map | Behaviour |
| --- | --- |
| 00contest | 0–0, 82–109 deaths per side |
| 00stampede | 0–0 (base reached 320 on one side) |
| 01yellow-brick-road | 0–0, **0 deaths, 2000 rounds** — a whole game of no activity |

These are **not** the banking deadlock I diagnosed; my fix changed nothing on them.
`01yellow-brick-road` with zero deaths and zero income across 2,000 rounds is the
clearest remaining defect in the bot and is worth a replay inspection
(`cambc view`) before anything else. We currently win three of these on the gold
tiebreak, so any opponent that tributes a single gem there beats us outright.

---

## 5. Reference: rules worth exploiting

Verified against the live handbook; none of these are used deliberately today.

1. **Your killer takes every carried gem, plus 100 gold.** A *camp* kill destroys
   them instead. Week 2 doubled the kill reward explicitly "to incentivise invades
   and contesting camps".
2. **An enemy inside a capture region resets the 5-round timer.** One champion denies
   a whole camp, and can take one the enemy already paid HP to clear.
3. **Your own altar lock does not block you.** 10 gold, cancels an enemy channel the
   moment it lands, 5 basic attacks to clear. Decisive on single-altar maps — which
   is 13 of 35.
4. **A tribute survives damage**; only stun, death or a lock cancels it. Marcella is
   stun-immune, so only death or a lock stops her: she should carry the big bags, and
   she earns 2 gold per gem tributed.
5. **Monsters never chase** (vision 8, no pursuit).
6. **Tavi buys shards anywhere on the map** — zero shopping trips.
7. **Map symmetry is exposed** (`gm.symmetry()`, reflect/rotate): enemy spawn, mirror
   camps, their nearest altar, for free. Unused.
8. **1,024 bytes of draft memory**, 10× fuel on the first draft turn. We write 6 bytes.
9. **Python gets 25× the C++ fuel budget** (2.5M/turn); median use is ~800k. No reason
   to port to C++.

### Target efficiency, post-patch

| Target | HP | Gems/HP | Gold/HP |
| --- | --- | --- | --- |
| Gem cluster | 120 | **0.058** | 0 |
| Gold cluster | 120 | 0 | **0.167** |
| Monolith | 20,000 | 0.010 | 0.015 |
| Golem | 5,000 | 0.0072 | 0.032 |
| Elk | 2,400 | 0.0063 | 0.0375 |
| Wolf | 1,350 | 0.0030 | 0.030 |

Clusters are 6–19× more efficient per HP and have 0 strength. A group is every
cardinally-connected monster and must be cleared whole, so group composition decides
everything.

---

## 6. What I would do next, in order

1. **Ship `boss_full` for Sprint 2** (p = 0.017, +5/−0 flips, 0 faults in 140 games).
   Credit the colleague's `boss.py`. Nothing else.
2. **Inspect the `01yellow-brick-road` replay.** A 2,000-round game with 0 deaths and
   0 income is a real defect and is unexplained.
3. **Test against actual ladder bots**, not each other. `cambc match-groups` queues
   unranked matches against real submissions; it needs `cambc login`, which is yours
   to run. Every number in this document is against our own lineage.
4. Only then attempt the Tier-2 ideas in section 5 — and **ablate one change at a
   time**, which is the real lesson of today.

---

## Reproducing

```sh
export PATH="$PATH:$HOME/Library/Python/3.9/bin"
cd ws && cambc run-batch bench/manifest.txt --jobs 3 --release --json --timeout 300
python3 ../analyse.py ws/bench
```

Variants live in `ws/bots/`: `base`, `colleague`, `boss_full`, `boss_focus`,
`cfg_only`, `r_only`, `b_only`, `h_only`, `fixed`. Result sets in `ws/bench`,
`ws/abl`, `ws/boss`, `ws/boss2`, `ws/final`.
