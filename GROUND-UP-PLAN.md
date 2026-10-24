# A ground-up bot: research, champion utility, and build plan

Written 21 Oct 2026, after 1,960 measured games on engine 1.0.2.

---

## 0. The premise

The current bot is at a local optimum. Across 14 candidate changes — three of my own
reasoned fixes, eight constant perturbations, the top-5 meta draft, and a fuel-guard
fix — **13 measured worse** and one (the colleague's `boss.py`) measured better at
p = 0.017. The retreat threshold, heal threshold and bank threshold are now bracketed
on *both* sides, so they are closed questions, not knobs.

That is the signature of a well-tuned machine of the wrong *kind*. A rewrite is
justified not because the code is bad — the navigation is genuinely strong — but
because the architecture answers a different question than the game asks.

---

## 1. What the literature and the winners actually say

### 1.1 Battlecode postmortems: process beats cleverness

The convergent message from the 2025 winner and runner-up is uncomfortable for anyone
who wants to write a clever bot.

- [Just Woke Up (2025 winner)](https://battlecode.org/assets/files/postmortem-2025-just-woke-up.pdf)
  shipped **57 bot versions in 25 days** — more than two per day — each A/B tested
  against the previous one, keeping winners and branching from the last good version on
  losses. Their own summary: there was no single thing that won it, just "a bunch of
  tiny basic things extremely well". They also say outright that exotic bytecode
  optimisation and unrolled pathfinding are "by no means required".
- [confused (2025, 2nd)](https://battlecode.org/assets/files/postmortem-2025-confused.pdf)
  took 1st seed into the qualifier with a deliberately simple bot and no bytecode
  optimisation. Their method was replay analysis → a written **core game philosophy**
  → align every feature to it. Two principles they derived: establish the economic
  structure early, and **minimise unit idle time** (they added an explicit idle timer
  that redirects long-inactive units).
- [no thoughts head empty (2023)](https://battlecode.org/assets/files/postmortem-2023-no-thoughts.pdf)
  flags the lesson we only learned today: *"many top teams had built up custom systems
  for quickly running many matches in parallel for A/B testing. It might be worth
  investing time at the start of the tournament to build up these tools."*

Three techniques recur across all of them and all apply directly here:

1. **Symmetry from immutable terrain.** Maps are symmetric for fairness. Deduce it from
   walls and static features, store it, then use it to predict enemy structures and
   retarget occupied objectives. `confused` defaults to assuming rotational symmetry and
   walks to the centre, because the centre is both the best place to disambiguate
   symmetry and the shortest path to the enemy.
2. **Distribute expensive computation across turns** into a persistent map-sized array,
   so the per-turn query is O(1). Both 2025 teams did this; `just-woke-up` abandoned a
   k-d tree for a plain 2D array for exactly this reason.
3. **Cheap denial.** `confused` partially painted enemy build sites — one unit of paint
   blocked a whole tower. The highest-leverage plays were the cheapest ones that removed
   an enemy option.

### 1.2 The farming loop is a Team Orienteering Problem with Time Windows

This is the key formal insight, and it is exact rather than analogical.

Camp groups are nodes with a profit (gems + gold), a service time (clear + 5-round
capture), and a **time window** set by a deterministic respawn period — wolf 40, elk 60,
golem 80, clusters 50, monolith 150. Champions are vehicles moving 1 tile/turn. The
horizon is 2,000 rounds. Maximise collected profit. That is the
**Team Orienteering Problem with Time Windows (TOPTW)**, and it is well studied:
[iterated local search with insertion and shake steps (Vansteenwegen et al.)](https://thesis.eur.nl/pub/30280),
an [iterative three-component heuristic combining local search, simulated annealing and
route recombination (Hu & Lim)](https://scholars.cityu.edu.hk/en/publications/an-iterative-three-component-heuristic-for-the-team-orienteering-/),
[granular VNS (Labadie et al.)](https://hal-utt.archives-ouvertes.fr/hal-02521846), and
a [branch-and-price exact method](https://remotecenter.postech.ac.kr/handle/2014.oak/27109)
for small instances.

**Our bot currently solves this greedily, per champion, from scratch, every single
turn** — a measured median of 800k fuel and a 95th percentile of 2.28M against a 2.5M
cap. The camp layout and respawn arithmetic are static and fully observable. Re-deriving
them 2,000 times is the single largest waste in the system.

### 1.3 Combat is a portfolio search problem, and the simulator is free

[Churchill & Buro, *Portfolio Greedy Search and Simulation for Large-Scale Combat in
StarCraft* (2013)](https://www.cs.mun.ca/~dchurchill/publications/pdf/combat13.pdf)
searches over **which script each unit follows** rather than over raw joint actions,
which collapses the search space at the cost of needing hand-written scripts. It handled
50v50 under a 40 ms budget.

The follow-up — [Churchill, Lin & Synnaeve, AIIDE 2017](https://ojs.aaai.org/index.php/AIIDE/article/view/12962)
— found performance "relies heavily on the accuracy of the underlying model", doing best
where the simulator matched the game.

**The model condition is satisfied here, but the compute condition is not.** The game
has no damage rolls: a basic attack deals exactly `Strength`, a spell exactly
`multiplier × Focus`. M1 built that simulator and validated it on 22,029 in-engine
predictions (see §4.3a). But M1 also measured the fuel cost, and it kills playout search
in Python.

### 4.3a MEASURED: Python cannot afford playout search

| Operation | Fuel |
| --- | --- |
| empty Python loop iteration | **~510** |
| `predict_damage` | 11,282 |
| `clear_turns_fast` (33 iterations) | 172,993 |

A 2,500,000-fuel turn buys about **4,900 Python loop iterations**, or ~220 damage
predictions. A single portfolio search over 6 scripts x 5 champions with 10-turn
playouts needs ~300 strike computations, which is ~1.5M fuel -- 60% of a turn for one
search, before any of the bot's actual work.

**This inverts my earlier conclusion**, and the follow-up measurement in C++ settles it.
I previously wrote that Python's 25x fuel multiplier meant there was no reason to port.
That was wrong. Both languages measured in-engine, one timing per turn:

| Operation | Python (2.5M/turn) | C++ (100k/turn) | C++ advantage per call |
| --- | --- | --- | --- |
| bare loop iteration | 272 | **2.70** | 101x |
| `predict_damage` | 11,282 | **7.00** | **1,612x** |
| `fuel_remaining` | 2,774 | 17.05 | 163x |
| `round_number` | 1,920 | 28.05 | 68x |
| 10-turn 1v4 playout (400 damage calcs) | ~4,500,000 | **436** | ~10,000x |

Converting to capacity per turn, after Python's 25x budget advantage:

| Capacity per turn | Python | C++ |
| --- | --- | --- |
| `predict_damage` calls | 222 | **14,288** |
| **10-turn 1v4 playouts** | **0.55** | **229** |

**Python cannot complete a single playout in a turn. C++ can run about 229.** That is the
entire case for the rewrite, and it is not close.

One nuance that shapes the design: the advantage is 68-163x per *SDK call*, which the 25x
budget difference reduces to only ~3-6x more engine calls per turn. So C++ buys enormous
**computation** and only modest **engine interaction**. The navigation layer -- which is
bound by native SDK primitives, not arithmetic -- gains little and should be ported
faithfully rather than redesigned. Combat search gains everything.

### 4.3c MEASURED: the fuel multipliers equalise engine calls, not arithmetic

The decisive comparison, both measured in-engine:

| | Python (2.5M/turn) | C++ (100k/turn) | C++ edge |
| --- | --- | --- | --- |
| bare loop iteration | 272-280 | 2.70 | ~100x |
| scalar SDK call (`round_number`) | 1,933 | 28 | 69x |
| **vector SDK call (`vision::camps()`)** | **25,125** | **82-1,291** | 19-300x |
| `predict_damage` | 11,282 | 7.00 | 1,612x |

Converted to capacity per turn, which is what actually matters:

| Capacity per turn | Python | C++ |
| --- | --- | --- |
| `vision::camps()` calls | ~99 | ~77 (worst) to ~207 (typical) |
| `predict_damage` calls | 222 | 14,288 |
| 10-turn 1v4 playouts | **0.55** | **229** |

**The engine-call budget is roughly equal between the two languages -- within about 2x --
while the arithmetic budget is 65x better in C++.** The fuel multipliers appear to be
calibrated precisely so that a bot doing ordinary engine interaction performs the same in
any language, and the only real difference is compute.

Two consequences:

1. **The C++ rewrite is justified only by the search.** For farming, routing, banking and
   drafting -- all engine-call-bound -- C++ offers nothing and costs the accumulated
   edge-case knowledge that is most of the Python bot's value. If M3's portfolio search is
   not built, the rewrite is not worth finishing.
2. **"SDK calls in loops" is a trap in both languages, not a C++ one.** sage2 blew its
   whole turn on eighty `champions()` calls inside a loop over camp groups; the same code
   in Python would have spent 2,010,000 of its 2,500,000. My earlier framing -- that C++
   is more constrained on engine interaction -- was wrong.

### 4.3b MEASURED: data layout dominates the playout budget

The same `predict_damage` costs wildly different amounts depending on where its operands
live:

| Context | Fuel per damage calc | Playouts per turn |
| --- | --- | --- |
| small local arrays (hot) | **~1.1** | **~229** |
| 600-entry table of 112-byte structs | **111.5** | ~22 |

Both were measured in-engine on the same build. Memory traffic, not arithmetic, is the
cost. So the combat search must keep playout state in **small flat arrays of doubles**,
not arrays of fat structs -- a 10x difference in how much search is affordable. The
`sim::Unit` struct is fine as an interface for one-off queries and wrong as the inner
loop's data structure.

Two consequences for this plan:

1. **A search-based bot should be written in C++ or Rust.** 100k fuel of native
   instructions is far more effective compute than 2.5M of interpreted ones.
2. **Any Python bot must push work into native SDK primitives** -- `Bitboard`,
   `DistanceField`, `shadow_cast`, `reachable_tiles` -- and keep Python loops tiny. This
   is exactly what the current `navigation.py` does, and it is why that module is the
   strongest part of the existing bot. Its author understood this constraint.

The draft-phase planner in §4.1 survives either way: it runs once, in the turn with 10x
fuel, and its output is a table lookup. It is the right first milestone precisely
because it does not need per-turn compute.

### 1.4 Runtime reassignment: token passing

[Ma, Li, Kumar & Koenig, *Lifelong Multi-Agent Path Finding for Online Pickup and
Delivery Tasks* (AAMAS 2017)](https://arxiv.org/pdf/1705.10868) defines the MAPD problem
— agents repeatedly assigned tasks requiring travel to a pickup then a delivery, which
is literally clear-camp-then-tribute-at-altar. They give **Token Passing (TP)** and
**TP with Task Swaps**, prove both solve well-formed instances, and note TP "can easily
be extended to a fully distributed algorithm and is the best choice when real-time
computation is of primary concern".

Our `teamwork.py` is already a primitive token: 10 bits per champion in 8 shared bytes.
The upgrade is to make claims reference *plan steps with deadlines* so a dropped task is
reclaimable, and to free bits for intel (§4.4).

### 1.5 Influence maps for routing and positioning

Influence maps assign each cell the summed influence of nearby entities; potential fields
turn that into movement. The division of labour in the literature is the useful part:
*good influence maps tell you where to go, good navigation tells you how to get there*
([Liu, Louis & Nicolescu](https://www.cse.unr.edu/~simingl/papers/publish/CIG2014IMPFMicro.pdf)).

We have excellent navigation (native distance fields, dash-aware multi-component
routing, crystal portals) and **no influence map at all**. `threat_mask` is a per-turn
binary union of visible camp radii. A camp threat field is static and precomputable:
every camp's strength spread over its attack radius, known at draft time.

---

## 2. Champion utility, from first principles

### 2.1 Per-shard growth is the dominant term

A game yields roughly 7,500 team gold — about 250 shards at 30g, so ~50 per champion.
End-game stats are therefore dominated by growth, not base stats.

| Champion | +Str | +HP | +Focus | Class |
| --- | --- | --- | --- | --- |
| Marcella | 5.0 | 100 | **15** | top-tier, best total |
| **Vendetta** | **6.0** | 100 | 10 | top-tier, best Strength |
| Ryth | 5.0 | 100 | 10 | top-tier (+1 Str per HP shard) |
| Vesper Vale | 5.0 | 100 | 10 | top-tier, +33% gold |
| Varg | 5.0 | 100 | 10 | top-tier |
| Ren | 5.0 | 100 | 9 | top-tier |
| Heart of Ruin | 3.5 | 100 | 12 | Focus-scaling tank |
| Tavi | 5.0 | 75 | 10 | mid |
| Cassi | 3.0 | 65 | 13 | Focus-scaling, fragile, twin risk |
| Issac | 3.0 | 80 | 10 | mid, twin risk |
| Stellar | 3.5 | 65 | 7 | weak |
| Prism | 2.5 | 60 | 8 | weak |
| **Willow** | **3.0** | **50** | **5** | **worst in the game** |

Base sustained damage (basic attack plus best ability amortised over its 8-turn
cooldown): Vendetta 78.8, Tavi 69.9, Marcella 65.6, Ryth 63.1, Vesper 61.9, Willow 61.9,
Prism 50, Heart of Ruin 48.8, Stellar/Cassi 47.5, Varg 45 single-target, Ren 44.4.

### 2.2 What this explains, and what it doesn't

**It explains Willow.** She looks fine at round 0 — 61.9 sustained damage, the only heal
in the game — and is dead last once gold arrives. 50 shards buy her +150 Strength where
they buy Vendetta +300. Top-5 teams picked her in **0 of 1,040** drafts on 1.0.2. Our bot
picks her third, every game.

**It explains Varg's absence only partly.** His growth is top-tier and his splash is
real. But his second ability is a self-shield — no economy, no control — and he has no
stun and no dash. He does Vendetta's job worse, and Vendetta's passive (a kill refreshes
*all* cooldowns) chains through cluster-dense groups, which is where splash would have
paid. Top-5 pick rate: 0.6%.

**It does not explain Heart of Ruin at 96.2%.** His growth is mid and his base damage is
poor. So his value is not throughput — it is *utility that doesn't appear in a damage
column*: a 2-tile dash with AoE damage **and a stun** on landing, a `1.5 × Focus` shield,
and a passive paying up to +50% damage as health falls. Scaled on Focus at +12/shard, a
50-shard Heart of Ruin dashes for `1.5 × 700 = 1,050` area damage, ×1.5 at low health.

And the stun is the point. **A tribute channel survives damage but is cancelled by a
stun.** Tributing is the win condition. Heart of Ruin is the best tribute-denial tool in
the game, attached to a durable body that gets stronger the closer it is to dying.

### 2.3 Utility tiers

- **Tier 1, always:** Vendetta (best damage scaler, kill-chains cooldowns), Marcella
  (best total growth, stun-immune so her tributes can only be stopped by death or a
  lock, +2 gold per gem tributed).
- **Tier 1 with the right architecture:** Heart of Ruin (Focus-scaled AoE stun; needs a
  low-health-seeking combat mode and a Focus build), Ryth (tanky, area stun, HP shards
  convert to Strength).
- **Tier 2:** Vesper Vale (+33% gold, stacks to 53% with Treasure, top-tier growth, and
  a *basic-attack Strength scaler* — architecture-compatible today), Ren (stun + dash,
  top-tier growth).
- **Tier 3, situational:** Tavi (buys shards anywhere — zero shopping trips, a real
  tempo edge our recall logic would currently waste), Cassi & Issac (two bodies, one
  death), Prism (scales on carried gems, so it wants to *not* tribute — directly opposed
  to the win condition).
- **Never, in the top meta:** Stellar (nerfed twice, weak growth), Prism (scales on
  gems it must not tribute).
- **Willow and Varg: system-relative.** Both are near-absent from top-5 drafts, and both
  are load-bearing *for us* — see §2.4.

### 2.4 Measured correction: champion value is architecture-relative

I predicted from the growth table that swapping out the worst-scaling champion would be
a free gain. It is not. Three one-swap variants, each against the same opponent, paired
by map and side, against `boss_full`'s 55-15:

| Swap | Record | Gem flips | Gems/game | Gold/game |
| --- | --- | --- | --- | --- |
| Willow -> Vesper Vale | 47-23 | +7/-16 | **-66.2** | +520 |
| Willow -> Vesper, Varg -> Ren | 47-23 | +7/-15 | **-63.0** | +704 |
| Varg -> Heart of Ruin | 46-24 | +8/-18 | **-32.5** | +358 |

Every swap **gained gold and lost gems**. Vesper's +33% gold is real and arrives; it just
does not convert. Removing Willow costs 66 gems a game despite her having the worst stat
growth in the game.

The reason is sustain. Her heal is `3 x Focus` -- 360 at base -- and `escort.py` exists to
keep her beside a farmer, which keeps that farmer *on the camp* instead of recalling. That
is the same uptime mechanism three other experiments pointed at: making the heal stricter
cost 41 gems/game, making it looser cost 46, and deleting the healer costs 66.

**So this bot is a sustain-farming system, and the top meta is a burst-denial system.**
A champion's worth is defined by the architecture around it. Willow is last in growth and
still essential here; Heart of Ruin is picked 96% of the time there and is net-negative
here. That is the sharpest possible statement of why the rewrite has to be a coherent
whole rather than a sequence of swaps -- and the sharpest possible warning that the new
architecture must bring its own answer to uptime before it drops the healer.

---

## 3. Why the current architecture cannot get there

Our bot is a **coherent Strength / basic-attack farming system**: melee-biased walk-and-
attack, Strength-first build (Jungle-Str → Monster-Str → Durability-HP), Varg splash
multipliers in `strategy.dps` and `combat.choose_camp`, a Willow escort module, and a
retreat rule that pulls out at 30% health.

The top meta is a **Focus / ability-burst system** with stun denial and a champion that
is *rewarded* for being near death.

These are incompatible, which is why dropping the top-5 draft onto our code cost 112
gems a game (p = 0.001) and the burst comp cost 476. Our retreat rule actively fights
Heart of Ruin's passive. Our build buys him the wrong stat. Our combat never evaluates a
dash as an attack.

**You cannot reach the other system by perturbing this one.** That is the measured case
for a rewrite, and it is the one thing today's 14 experiments established beyond doubt.

---

## 4. The new architecture

Five components. The ordering is deliberate: each one frees the budget for the next.

### 4.1 Draft-phase global planner — the central idea

The draft phase **sees the entire map** and gets **10× fuel on its first turn**. The
first play turn gets 2×. There are **1,024 bytes of draft memory**, writable in the draft
and readable all match. We currently use six of them (`b"bomba" + variant`).

So solve the TOPTW offline, in the draft, once:

1. Detect symmetry from static terrain; derive enemy spawn, mirror camps, their nearest
   altar.
2. Value every camp group: gems, gold, HP, incoming strength, respawn period, distance
   to the nearest altar, and distance to the symmetry midline (contest risk).
3. Construct routes by **greedy insertion** then improve with local search (the standard
   TOPTW construction), honouring respawn windows and the 5-round capture.
4. Choose the draft *from the plan* — pick the champions the route set actually wants,
   rather than from a fixed list.
5. Encode and store.

**Encoding budget.** At ≤46 camp groups, 6 bits per group id. 40 route steps × 5
champions × 6 bits = 150 bytes. Plus symmetry (2 bits), per-champion role and build
policy (5 × 8 bits), altar assignments, and a contest watch-list. Comfortably inside
1,024 bytes.

**Why this is the big win.** Per-turn cost collapses from ~800k fuel of re-derivation to
a few thousand fuel of "read my next step", and the routes become *globally coordinated*
instead of five greedy agents colliding. The freed ~2M fuel per turn is what pays for
everything below. This is also exactly the postmortems' "distribute expensive computation"
lesson, taken to its limit: distribute it into the one turn that has 10× the budget and
perfect information.

### 4.2 Runtime executor with token passing

Follow the plan. Re-assign only on invalidation — a champion dies, a camp is contested, a
respawn drifts. Use Ma et al.'s Token Passing over the 8 shared bytes, with claims
referencing plan-step indices and carrying a deadline so dropped tasks are reclaimable.
TP is the right choice precisely because it is cheap and distributable.

### 4.3 Combat: portfolio greedy search over a perfect simulator

Build the forward simulator first; it is deterministic and therefore exact. Then a script
portfolio: `burst`, `kite` (attack then step out of range — the 2023 team's launcher
micro), `stun-deny` (hold CC for an enemy tribute channel), `dive-carrier`, `tank`
(shield and absorb), `disengage`. Greedy portfolio search assigns a script per champion,
evaluated by short playouts. At ≤5v5 this is cheap relative to a 2.5M budget.

This is where Heart of Ruin becomes usable: the combat module, not the retreat constant,
decides when low health is an asset.

### 4.4 Denial as a second economy

**Correction (measured after writing this):** four of these are already implemented in
the current bot -- mid-tribute interruption, high-gem target preference, CC valued for
cancelling a channel, altar-lock placement, breaking a blocking lock, and defending our
own capture region. Only two are absent: entering the *enemy's* capture region, and
travelling far to hunt a carrier. Both require abandoning farm, which measured worse in
21 of 22 tests. The denial upside is therefore smaller and more expensive than this
section originally claimed; it needs an architecture that is not purely farm-throughput.

The mechanics themselves remain live and decisive:

- an enemy standing in a capture region **resets its 5-round timer** — one champion can
  deny a whole camp, and take one the enemy paid health to clear;
- **our own altar lock does not block us**, costs 10 gold, **cancels an enemy channel the
  instant it lands**, and takes five basic attacks to clear — decisive on single-altar
  maps, which is 18 of the 35;
- a **stun cancels a tribute**; damage does not;
- **the killer takes every carried gem** plus 100 gold, and the victim sits out 60 rounds.

Denying 50 gems is worth exactly as much as earning 50. Symmetry tells us where their
carriers will walk. This needs shared intel, which needs bits — re-encode the token as
5 × 8-bit plan-step claims (40 bits) and spend the remaining 24 on an enemy-carrier
sighting (7-bit x, 7-bit y, 5-bit gem count, flags).

### 4.5 Build engine keyed to scaling class

Two policies, chosen per champion rather than one global order:

- **Strength scalers** (Vendetta, Ryth, Marcella, Vesper, Ren): close to today's order,
  which measured well — Jungle-Str, Monster-Str, Durability-HP, then alternate Power by
  marginal `health_growth × Strength` vs `strength_growth × max_health`.
- **Focus scalers** (Heart of Ruin, Cassi, Prism): Focus shards, because their damage is
  `multiplier × Focus` on a fixed cooldown.

Re-test **Treasure** here. It measured +1,403 gold/game (+19%) at a neutral win rate on
the current bot; on a high-growth champion in a system that converts gold to stats faster,
it should compound rather than wash out. Vesper Vale plus Treasure is +53% gold.

### 4.6 Influence maps

Precompute a static camp-threat field at draft time and route on
`travel_cost + λ × threat` rather than distance. Add a dynamic enemy-threat layer at
runtime. Keep the existing navigation — it is the strongest part of the current bot and
should be ported wholesale.

---

## 5. Build plan, with gates

Each milestone has a measurable gate against the current champion, `boss_full`, on the
35-map two-sided harness. **If a milestone does not clear its gate, it does not merge.**

Re-ordered after the 35 real games: survival first, farm planning demoted. We tribute
475-814 gems against our peers' 457-767, so economy is *average, not behind*. Deaths are
the gap.

| # | Deliverable | Gate | State |
| --- | --- | --- | --- |
| M0 | A/B harness + gauntlet | done | **done** |
| M0b | **Scrimmage harness** (real opponents, 50 groups of quota) | real data, not self-play | **done** |
| M1 | Deterministic damage model, Python | exact vs engine | **done: 22,029 predictions** |
| M1b | Damage model ported to C++ | bit-exact vs the Python reference | **done: 600 vectors, 0 mismatched** |
| M1c | Survival model (time-to-death vs time-to-escape) | hand-computed cases pinned | **done: 18 checks, 0 failed** |
| **M2** | **Survival wired into a playing bot** | **scrimmage: deaths/game below 20** | next |
| M3 | Portfolio search combat on flat arrays | scrimmage win rate vs rank ~200 | |
| M4 | Port navigation faithfully from Python | parity on routing | |
| M5 | Farm/objective selection | parity with greatsage economy | |
| M6 | Focus build policy + Heart of Ruin | HoR comp at least Strength comp | |
| M7 | Denial: capture contesting, carrier intercept | measurable gem denial | |

### M2 status: sage2 plays, and is not yet competitive

Built in C++: `turnguard.h`, `nav.h` (core routing ported faithfully), `sim.h`,
`survive.h`, `bot.cpp`, plus a fixed draft matching greatsage so an A/B measures
architecture rather than roster.

Gates green: **600 damage vectors bit-exact, 21 survival checks, 3 replan logs and no
other errors in a full game.**

First full game against `boss_full` on 00fragment: **26 gems to 1,016, 54 deaths to 0,
202 gold to 14,296.** It plays; it is nowhere near competitive. That is the expected
distance between a few hours of porting and 1,443 lines of tuned Python.

Branch distribution per champion over 400 turns:

| | moving | attacking | survive | banking | idle |
| --- | --- | --- | --- | --- | --- |
| champion 1 | 291 | 43 | 65 | 0 | 0 |
| champion 2 | 257 | 28 | 101 | 8 | 5 |
| champion 3 | 255 | 51 | 90 | 0 | 3 |

**Movement is 64-73% of turns and attacking only ~10%.** The cause is missing objective
persistence: `farm()` re-ranks every group every turn with no memory, so the cheapest
target flips as distances change and the champion thrashes between them. greatsage keeps
`self.objective` and a shared-memory claim precisely to stop this.

Three bugs found and fixed during the port, all of them lessons the Python bot had
already learned and I had dropped:

1. `camp_group::state()` throws "camp group is not in vision" unless the group's spawn
   tiles intersect our vision. The first version threw **4,726 times in one game** and
   scored nothing.
2. Routing *onto* a group's spawn tiles bails once the group is visible, because live
   camps occupy those tiles and `blocked()` excludes occupied tiles. Must route to a
   tile within attack range of a camp instead.
3. `survive::should_disengage` returned "leave" for an unescapable chaser, which donates
   free hits to something that moves at our speed. Replaced with an action -- carry on,
   disengage, or **fight** -- plus a duel prediction. This was my own design error,
   caught by sage2 dying 51 times in a game.

### Persistence and claims: measured result

`claims.h` ports the Python eight-byte protocol (ten bits per champion: nine for group
handle + 1, one for a support flag) and `farm()` now commits to a target until it goes
bad -- respawning, claimed by an ally, or stalled for 12 ticks with neither position nor
camp health changing.

| Per 400 turns | before | after |
| --- | --- | --- |
| attacks | 43, 28 | **75, 100, 103** |
| moves | 291, 257 | 220, 230, 232 |
| retargets | every turn | 30-44 |
| gold earned (full game) | 202 | **542** |

The thrashing is fixed. But 542 gold against `boss_full`'s 14,108 is still a 26x gap, and
58 deaths against 2.

### The next bottleneck is abilities, not targeting

sage2 uses **only basic attacks**. It never casts anything: no attack resets, no area
damage, no crowd control, no Varg splash. The Python `combat.fight` scores every ability
against every candidate tile and sequences attack resets around the ordinary attack,
which is a large part of its damage. Three champions earning 542 gold cannot buy shards,
so they lose every fight they are forced into, die, and fall further behind -- a spiral
whose root is clear rate, not combat tactics.

So the order is: **abilities next**, then capture handling, then the cooperative rally.

### sage2 build log, each step measured on 00fragment vs boss_full

| Step | Gems | Gold | Deaths | Note |
| --- | --- | --- | --- | --- |
| first playing version | 0 | 0 | 0 | `state()` threw 4,726 times, no vision guard |
| + vision guard on `state()` | 0 | 0 | 4 | moves, still never attacks |
| + route to attack range, not onto spawn tiles | 0 | 254 | 51 | starts attacking |
| + action model, fixed draft, opportunistic banking | 26 | 202 | 54 | first gems submitted |
| + objective persistence and claims | 26 | 542 | 58 | attacks/400 turns 43 -> 100 |
| + ability selection (resets, AoE, CC, splash) | 0 | 660 | 56 | 43 more vision errors, then fixed |
| + enemy-proximity penalty on target choice | 0 | **1,100** | 54 | first 2 kills; boss_full's first 2 deaths |

`boss_full` earns ~13,000 gold in the same game, so sage2 is at about **8.5% of its
income**, up from zero. Gems remain near zero because it rarely survives long enough to
bank a worthwhile bag.

**The arithmetic that governs everything:** 54 deaths x 60 rounds of respawn is 3,240
lost champion-rounds out of 3 x 2,000 = 6,000. Over half the team's time is spent dead.
No amount of better fighting recovers that; being somewhere else does, which is why the
enemy-proximity penalty bought more (+67% income) than the entire ability port (+22%).

Shopping is not the problem: every champion spends all the gold it earns (360/120/180
against boss_full's 5,498/7,570).

### sage2 baseline: 39 maps vs boss_full

Established after fixing the claims fuel bug, so these are the first trustworthy sage2
numbers. Every future change is measured against this, across all 39 maps -- single games
swung 580 to 1,100 gold on identical logic.

| | sage2 | boss_full |
| --- | --- | --- |
| record | **0-39** | |
| gems/game | 31.3 | 931.2 |
| gold earned/game | 863 | 8,604 (**10%**) |
| deaths/game | **45.9** | 4.9 |
| time spent dead | **45% of champion-rounds** | |
| maps scoring 0 gems | 23 of 39 | |
| maps still fully inert | 4 (00eight, 00lanes, 00split, 01boss-battle) | |

The first attempt at this baseline measured 72 gold/game and 0 deaths on 38 of 39 maps --
it was measuring the claims fuel bug, not the bot. sage2 had only ever worked on
00fragment, the one map small enough to hide eighty SDK calls per turn. **Every single-map
number quoted during the port -- 254, 542, 660, 1,100, 970 -- came from that map.**

### Three 39-map baselines, and what each fix cost

Measured against `boss_full`, sage2 always side A. Single maps swing 460-1,100 gold on
identical logic, so only these sweeps are trustworthy.

| | 1: claims snapshot | 2: cached geometry | 3: + respawn memory | 4: + banking |
| --- | --- | --- | --- | --- |
| gems submitted/game | 31.3 | 13.9 | 39.6 | **78.2** |
| gems collected/game | 88.7 | 45.3 | 95.7 | **108.2** |
| gems carried into a death | 57.4 | 31.4 | 56.2 | **30.1** |
| submitted / collected | 35% | 31% | 41% | **72%** |
| gold earned | 863 | 479 | 910 | **1,034** |
| deaths/game | 45.9 | 44.7 | 52.5 | 52.0 |
| share of opponent income | 10% | 5% | 10% | 12% |
| zero-gem maps | 23/39 | 29/39 | 24/39 | **11/39** |
| inert maps | 4 | 4 | **3** | 3 |
| wins | 0 | 0 | 0 | 0 |

Baseline 2 is the instructive one. Removing the per-group `state()` call was a genuine
fuel fix -- it recovered 00lanes and 01boss-battle from being wholly inert -- and it
**halved income**, because respawn state was the only thing stopping a champion
re-picking an empty group every turn. Restoring it as remembered timers rather than a
per-turn query recovered everything and a little more.

**Banking was the biggest single leak and is now the biggest single fix.** At baseline 3,
95.7 gems were collected and 39.6 submitted: fifty-six a game carried to a death, where
the killer took them. Three changes closed most of it:

1. `BANK_GEMS` 24 -> 8. A 24-gem bag assumes a carrier lives long enough to fill it. At
   fifty deaths a game it does not.
2. **Tribute under fire.** A tribute is cancelled by stun, death or lock but *not* by
   damage, so when an altar is within `submit_gems_range` and time-to-death exceeds the
   tribute's `ceil(gems/10)` ticks plus one, submit instead of disengaging.
3. **Withdraw toward an altar, not spawn.** A carrier forced off a camp routes to the
   nearest altar goal when it holds gems, converting a retreat into a deposit.

Submitted nearly doubled, 39.6 -> 78.2, and -- the part that matters -- collected *rose*
too, 95.7 -> 108.2, so the smaller bag is not costing farming time in travel. Gems carried
into a death halved, 56.2 -> 30.1. Zero-gem maps fell from 24 to 11; 00lanes went 26 ->
243 gems and four maps that had never scored started scoring (01gold-rush 143, 00packs
110, 00pilgrimage 105, 00rows 207 -> 345). Deaths did not move (52.5 -> 52.0), which is
the expected shape: this fix banks the gems a dying champion was already going to lose,
it does not stop the dying.

Still 0-39. 78 gems a game against a 1,000-gem win condition is a tenth of boss_full.

The threshold was ablated on its own -- the other two changes held constant, `BANK_GEMS`
alone moved -- because bundling three changes is what made earlier experiments
uninterpretable. The curve has a peak:

| `BANK_GEMS` | 24 | **8** | 4 |
| --- | --- | --- | --- |
| gems submitted | 41.3 | **78.2** | 75.1 |
| gems collected | 91.9 | **108.2** | 101.1 |
| gold earned | 869 | **1,034** | 965 |
| submitted / collected | 45% | 72% | **74%** |
| deaths/game | 52.4 | 52.0 | 52.2 |

So the bag size is essentially the whole effect: with the other two changes in and the
threshold back at 24, submitted falls to 41.3, within two gems of baseline 3's 39.6.
Tribute-under-fire and altar-withdrawal are worth about 1.7 gems between them. Going below
8 starts paying for trips that are not worth taking -- at 4 the ratio is marginally better
but both totals are lower, which is travel cost, not banking.

### The death rate is a sustain problem, not an avoidance problem

Splitting damage by source across the sweep turns the whole death thesis around:

| per game | sage2 | boss_full |
| --- | --- | --- |
| monster damage taken | 35,633 | 36,425 |
| champion damage taken | 23,555 | 8,832 |
| **healing received** | **1,350** | **51,949** |
| damage taken per death | 1,138 | 9,145 |
| monster damage *done* per point taken | 0.83 | 3.78 |
| deaths | 52 | 4.9 |

boss_full takes **more** monster damage than sage2 does and dies a tenth as often. It is
not avoiding damage better. It heals back 52,000 a game; sage2 heals 1,350.

The only sustain in this game is `game_settings.spawn_healing` -- a fraction of maximum
health restored each round to a living champion standing on its own spawn region. 1,350
health a game across five champions over 2,000 rounds is about eleven champion-rounds
spent on spawn. boss_full spends roughly four hundred. **sage2 never goes home.**

The cause is a deliberate choice made earlier in this port, recorded in the comment at the
top of `bot.cpp`: the time-to-death model *replaced* the Python bot's health thresholds
rather than supplementing them. The model is better physics and worse behaviour, because
it is reactive. It fires at `ttd <= tte + 1.5`, one or two turns from death, at which point
walking out of a camp's attack range donates exactly the hits that kill you. With no flat
floor, a champion at 20% health with nothing currently in range is "safe", so it walks
into the next camp and dies there. That is the 52 deaths, and it is also the 0.83 damage
ratio: a champion that is always at low health trades badly against every camp it touches.

boss_full's trigger, which this port dropped:

```python
retreat_at = max(me.max_health() * threshold,          # 0.30, or 0.43 carrying gems
                 camp_pressure * 2 + me.max_health() * 0.08)
if not at_spawn and me.health() < retreat_at:
```

`camp_pressure` is the summed strength of awake camps already in attack range, doubled
because monsters act before your next turn, plus an 8% buffer. Restored to sage2 as
`Bot::heal_trip()`, running after the survival check rather than instead of it, with the
withdraw path factored out so both layers share it.

It is the largest single change of the port:

| per game | 4: banking | 5: + health floor | boss_full |
| --- | --- | --- | --- |
| healing received | 1,350 | **26,116** | 51,949 |
| deaths/game | 52.0 | **38.3** | 4.9 |
| gems submitted | 78.2 | **133** | 931 |
| gems collected | 108.2 | **170** | 1,013 |
| gold earned | 1,034 | **1,487** | 9,340 |
| monster damage done | 29,671 | 41,974 | 137,665 |
| monster damage *taken* | 35,633 | **43,355** | 36,425 |
| damage done per point taken | 0.83 | 0.97 | 3.78 |
| damage taken per death | 1,138 | **1,846** | 9,145 |
| zero-gem maps | 11/39 | 10/39 | -- |
| wins | 0 | 0 | -- |

Note the shape: monster damage *taken* went **up**, 35,633 to 43,355, while deaths went
down by a quarter. That is boss_full's own profile -- absorb more, die less, because the
damage is healed off rather than avoided. Everything downstream moves with it: a champion
that is alive and near full health clears faster (damage done +41%), so it collects more
(+57%), banks more (+70%) and earns more gold (+44%) without a single change to farming,
routing or target selection.

Of boss_full's 51,949 healing, 40,832 is spawn healing and 11,117 is Willow's heal
ability, cast by its third draft pick. sage2 drafts Willow too and had never cast it:
`combat::heal_allies` ported next, cheapest-target-first with the same 120-point minimum
missing health, cast without consuming the turn exactly as the Python bot does.

That one measured roughly neutral: healing done 0 -> 2,110, deaths 38.3 -> 37.3, gems
submitted 133 -> 136, collected 170 -> 176, gold 1,487 -> 1,480. Re-measured later on a
working instrument at **-1 gem**, so "neutral" was right for the wrong reason. Kept because the mechanic is
correct and was doing nothing, but note that 2,110 is a fifth of boss_full's 11,117 from
the same champion. The difference is not the cast logic, it is that a heal needs a hurt
ally inside its range: boss_full travels as a party (`escort.py`), sage2 scatters its
champions across claimed groups, so Willow usually has nobody to heal. The heal's value is
gated on grouping, which is still unported.

### Where the remaining time goes

Branch counters from one game on 00rows, per champion per 1,200 turns:

| | champion 1 | champion 2 |
| --- | --- | --- |
| move | 701 (58%) | 791 (66%) |
| attack | 240 (20%) | 181 (15%) |
| bank | 133 | 78 |
| survive | 27 | 84 |
| health floor | 42 | 29 |
| idle | 45 | 25 |

Deaths are no longer the main consumer of champion time -- 37 deaths at ~60 rounds of
respawn is about 11% of the team's champion-rounds. **Walking is: roughly 60% of an alive
champion's turns.** That is the whole of the remaining 3.3x monster-damage gap; boss_full
is simply at a camp far more of the time.

The first lever tried against it failed, clearly. Group selection costed only the
outbound leg, `travel * 100 / value`; every camp cleared implies walking the gems
somewhere they can be deposited, at the same speed, so the group's distance to its nearest
altar was added to the cost, precomputed once since both ends are static. Measured over
39 maps: **gems 136 -> 91, collected 176 -> 123, gold 1,480 -> 1,036, deaths 37 -> 41.**
Reverted.

The reason is worth keeping, because it rules out a family of ideas rather than one line.
`altar_dist` is a constant per group, so adding it to the cost does not rank *a
champion's* options -- it reorders *every* champion's options identically. All five
converge on the handful of groups nearest an altar, the claim protocol locks four of them
out, and they fall through to worse targets or to nothing (zero-gem maps went 11 -> 15).
A per-champion term like `travel` discriminates; a per-map constant only distorts. Gold
needs no altar at all, which the term penalised anyway, and growing the cost scale
weakened the flat `+60` enemy-proximity penalty that is the biggest measured income lever
in this bot.

So the 60%-walking problem is not addressable by reweighting a single global cost. What
boss_full actually does is different in kind, and reading `escort.py` showed it is not a
general rally at all -- it is a **support-role override on one champion**. Willow does not
pick a group. It picks an *ally that already holds a claim*, reserves the same group with
the support bit set (which `taken_by_other` deliberately ignores, so two champions on one
group is intended rather than a collision), and works that group from within three tiles
of the leader. Leader preference: Varg first, because its splash clears a group fast
enough that the camps die while the healer is still standing there; then nearest, in units
of twelve tiles so distance never outweighs the role; and a hurt ally outranks both,
because that is who the heal is for.

Ported as `Bot::escort()`, gated on having a heal ability rather than on the champion's
name, running in the farm slot with the ordinary selection as fallback -- a healer with no
party is better off clearing something.

| per game | 6 (re-run) | 8: escort |
| --- | --- | --- |
| healing done | 2,184 | **6,194** |
| gems submitted | 126 | **164** |
| gems collected | 171 | **201** |
| gold earned | 1,500 | **1,605** |
| monster damage done | 41,587 | **44,622** |
| deaths | 37.2 | 37.2 |
| zero-gem maps | 11/39 | **14/39** |

Healing done went up 2.8x, which confirms the diagnosis: the cast logic was never the
problem, the heal had nobody in range.

**The +38 gems and the win reported here are both artefacts.** Read on -- the harness
could not resolve either at the time, and a 2x2 ablation on the fixed instrument puts the
escort's contribution at exactly zero. The `01yellow-brick-road` win in particular is
decided by a dead loop. The healing-done figure survives; nothing else in this subsection
does.

### The escort needs a gate

The zero-gem count moving 11 -> 14 is a real cost, not noise, and the per-map split says
why. The escort is enormously positive on large maps and negative on small ones:

| | before | after |
| --- | --- | --- |
| 01yellow-brick-road | 349 | **1,010** |
| 00ambush | 323 | **609** |
| 01islands | 444 | **650** |
| 00quadrants | 208 | **366** |
| 00interlock | 4 | **125** |
| 00expanse | 481 | **334** |
| 01shortcut | 110 | **30** |
| 00great-wall | 60 | **0** |
| 00gemfight | 41 | **0** |
| 00fragment | 26 | **0** |

On every regressed map Willow collects nearly nothing -- 0, 0, 0, 2 gems -- while healing
three to four thousand. That is the trade stated plainly: the escort removes a fifth of the
team's collectors. On a map where travel dominates, the party it creates is worth far more
than the collector it costs. On a small map where the whole team only banks forty gems,
losing a collector is most of the income and the healing buys nothing back.

So the gate should be the same quantity the whole problem is about -- travel. The healer
escorts when joining the leader's group is *cheaper than opening a new front of its own*,
and collects otherwise -- a per-champion comparison between two costs it already computes,
rather than a map-size heuristic or a tuned constant. `group_cost()` was factored out of
the selection loop so both sides are scored on one scale.

| per game | no escort | ungated | gated |
| --- | --- | --- | --- |
| gems submitted | 126 | 164 | 156 |
| gems collected | 171 | 201 | 201 |
| gold earned | 1,500 | 1,605 | 1,613 |
| deaths | 37.2 | 37.2 | 36.4 |
| healing done | 2,184 | 6,194 | 4,246 |
| zero-gem maps | 11/39 | 14/39 | 11/39 |

The gate keeps the income, restores the zero-gem count and costs nothing. But the per-map
records already said something the means hid:

| | better | worse | same |
| --- | --- | --- | --- |
| ungated vs no escort | 13 | 14 | 12 |
| gated vs no escort | 15 | 13 | 11 |
| gated vs ungated | 12 | 13 | 14 |

The escort loses on about as many maps as it wins. Its positive mean comes from a few very
large gains outweighing many small losses -- which is worth having, but is not the "broad
improvement" the average suggests.

## The harness cannot resolve a 30-gem change

Then the floor fell out of all of it.

Two sweeps of an identical build are byte-identical, so the engine is deterministic and
there is no sampling noise. The conclusion I drew from that -- that every number is now
exact -- was wrong, and the way it was wrong matters more than any result above.

An incomplete revert had left a nested loop in `load_groups()` computing `altar_dist`, a
value **read by nothing**. Removing it cost 12 gems a game and the one win. Re-adding it
as an explicitly dead loop reproduced the original build byte for byte. So a third probe
went in: a *differently sized* dead loop, summing tile coordinates. Three builds that make
identical decisions on every turn:

| dead code in `load_groups()` | gems/game | wins | 01yellow-brick-road |
| --- | --- | --- | --- |
| none | 144 | 0 | 310 |
| probe A: altars x tiles | **156** | **1** | **1,018** |
| probe B: sum of tile coordinates | 141 | 0 | 210 |

Identical behaviour, 141 to 156 gems, 0 to 1 wins, and one map swinging **310 to 1,018**
on arithmetic nobody reads. Fuel is the mechanism: any change in fuel consumption re-rolls
which turns exhaust their budget and throw `Replan`, and that cascades through the rest of
the game. Six of 39 maps changed outcome under probe A, four under probe B, and they are
the same few large maps where fuel is tight.

**So the resolution floor of this 39-map sweep is about +-15 gems and +-1 win, and it has
nothing to do with sampling.** Consequences:

- The escort's +30 gems is twice the floor. Real, but weak.
- The win on `01yellow-brick-road` is *inside* the floor and is worth nothing as evidence.
  It was announced earlier in this session as sage2's first real win; it is not evidence of
  one. A dead loop decides it.
- The heal ability's +3 gems is far inside the floor, in both directions. Unknowable here.
- What survives: **healing done 2,184 -> 6,194**, a direct count of the mechanism firing,
  which no fuel perturbation explains. The escort does what it was built to do. Whether
  that converts into gems at this bot's level is not measurable on this pool.
- The banking fix (+39) and the health floor (+55) are 2.6x and 3.7x the floor, and both
  moved healing and death counts by multiples. Those stand.

The dead loop was removed rather than kept. Keeping unread code because it lands on a
lucky side of a fuel boundary is overfitting to 39 fixed games, and would not survive
contact with a different opponent, let alone the ladder.

This was already known and was forgotten. A behaviour-neutral change was used earlier in
this project to establish that the *self-play* harness could not resolve fewer than about
four wins in seventy games -- and the same instrument was then trusted here to resolve
single-gem differences. Any future change to sage2 gets a behaviour-neutral probe
alongside it, or its measurement means nothing.

### Where sage2 stands

The build with the escort gated and no dead code, which is what is on disk:

| per game | no escort | **standing** | boss_full | floor |
| --- | --- | --- | --- | --- |
| gems submitted | 126 | **144** | 931 | +-15 |
| gems collected | 171 | **192** | 1,013 | |
| gold earned | 1,500 | **1,536** | 9,340 | |
| deaths | 37.2 | **37.4** | 4.9 | |
| healing done | 2,184 | **4,490** | 11,117 | |
| zero-gem maps | 11/39 | **11/39** | -- | |
| wins | 1 (0-0 tiebreak) | **0** | -- | +-1 |

Read against the floor: the escort's income gain is just outside it, its healing gain is
far outside it and is the thing actually established, and the win column is honestly zero
-- the previous "1" was the `01boss-battle` 0-0 gold tiebreak, and the yellow-brick-road
win belonged to a dead loop.

Across both sessions sage2 has gone 31 -> 144 gems a game, 4.6x, every bit of it from
banking, sustain and now party play rather than from farming or routing. It remains 0-39
against boss_full and roughly a sixth of its income.

The next piece is no longer a guess. Three things are known and unported:

1. **`BossBot`**, the controller for single-altar monolith maps (`policy.kind() == 2`).
   On `01boss-battle` sage2 deals *more* monster damage than boss_full, 73,425 to 40,715,
   dies eighty times and banks **zero** -- the one altar is gated behind the monolith and
   sage2 has no answer to that map class at all.
2. **A fuel budget that is not chaotic.** The resolution floor is a symptom: turns are
   exhausting their fuel often enough that shifting consumption by a few thousand
   instructions changes six maps. Finding and removing the turns that overrun would both
   raise income and make every future measurement mean something. This is the prerequisite
   for the portfolio search, which spends fuel deliberately.
3. **The portfolio search itself**, still the only thing that justifies C++ over the Python
   bot, and still unbuilt.

## Going after the fuel, and what was actually wrong

The hypothesis going in was that turns exhaust their budget and throw `Replan` often enough
to cause the chaos. That was wrong, and the replay bundles already said so: `Replan` is
caught in `main()` and printed as `bot error: replan`, so counting it needs no new code.
**Twelve throws across all 39 games**, 0.3 per game, on 8 of 39 maps.

So the drain was measured directly instead, with a `FuelSpan` guard round each branch of
`play_turn` and a one-off print from `load_groups`. Mean fuel per champion-turn, out of a
100,000 budget, across three of the volatile maps:

| | cost |
| --- | --- |
| `load_groups()` (one-off, on a 2x-budget first turn) | **61,000 - 77,100** |
| `escort()` -- the healer only | **23,300 - 25,000** |
| `farm()` | 11,500 - 28,600 |
| `survive_check()` | 6,700 - 10,500 |
| `heal_trip()` | 3,200 - 7,300 |
| `heal_allies()` | 280 - 3,700 |
| `bank()` | 90 - 1,500 |
| `shop()` | ~100 |
| **mean total per turn** | **28,000 - 54,000** |
| minimum fuel ever remaining | 7,989 - 27,382 |

Two things stand out. `load_groups()` spends 61-77% of a turn budget in one call -- about
four SDK calls per group, and 77,106 on the 42-group map matches ~168 calls at ~450 fuel
each almost exactly -- but it runs once per champion on a turn that gets double budget, so
it is not the ongoing problem. The ongoing problem was **`escort()` at ~24,000 fuel a turn,
a quarter of the budget, which is code written earlier in this same session.**

### Two fixes, and only one of them should have been made

**`own_slot()` cached.** It answers "which slot in the shared word is mine", which cannot
change during a match, and it made a vector-returning `champions(ally)` call every time.
`claims::claim()` calls it on nearly every turn for every champion -- a third such call per
turn on top of the ones in `snapshot()` and `escort()`, for identical data. Caching it is
provably behaviour-neutral.

**Objective persistence for the escort.** `farm()` has `target_still_good`; `escort()` had
nothing, so it re-chose a leader and re-ran its whole gate every turn. Adding persistence
cut the escort to ~18,000 fuel and dropped the near-exhaustion turn count sharply
(27/390 -> 19/395, 51/789 -> 32/777, 75/1599 -> 24/1199).

Both were then swept, and separating them mattered:

| per game | before | cache only | cache + persistence |
| --- | --- | --- | --- |
| gems submitted | 144 | **140** | 125 |
| gems collected | 192 | **183** | 160 |
| gold earned | 1,536 | **1,501** | 1,361 |
| per-map record vs previous | -- | 4 better, 5 worse, **30 same** | 14 better, 15 worse |

Persistence cost 14 gems a game. It was reverted. The reason is specific: in `farm()`
re-ranking groups is thrashing, because the groups do not move. For the escort the thing
being ranked is *which ally to stand next to*, and that genuinely changes every turn --
who is hurt, who is close, who still holds a claim. Freezing that decision saves fuel by
not making the decision the escort exists to make. **And it was a behavioural change
smuggled into a fuel fix, which is the same mistake this document already records three
times.** The right way to cut the escort's cost is to make the per-turn decision cheaper,
not to stop taking it.

### The floor is gone

The point of the exercise was never the gems. It was whether the instrument works. The
same dead loop, on either side of the fuel work:

| | gems | maps moved | wins |
| --- | --- | --- | --- |
| before the fuel work | 144 vs 156 (**+12**) | **6 of 39** | 0 vs **1** |
| standing build | 140 vs 140 (**+0**) | **0 of 39** | 0 vs 0 |

Identical decisions either side; the only difference is arithmetic nobody reads. Before,
it moved six maps and swung `01yellow-brick-road` from 310 to 1,018 gems, inventing a win.
Now it moves nothing at all. Checked that this is not an artefact of comparing one binary
with itself: the two wasm images hash differently (`240306663f74967a` against
`6b726761cd11aacb`), the dead loop is present in one source and absent from the other, and
the two manifests name different bot directories.

So **the floor for a perturbation of that size went from about +-15 gems and +-1 win to
zero**, and it took one cached integer. Income is 4 gems lower than the chaotic build's
144, inside what that build's own floor spanned (141-156).

**Read the scope of that claim carefully -- it was later shown to be too strong.** A
*larger* neutral perturbation, sized like a real optimisation rather than like a dead
loop, still swings +-22 gems and a win on this pool. See "The floor claim was too strong"
below. Fuel headroom removed the small-perturbation sensitivity; it did not make the pool
a stable instrument.

Every future sage2 change is now measurable. The neutral twin stays in the workspace
(`bots/s2_probe2`) and gets swept beside any change whose effect is under ~20 gems.

## Re-measuring the escort and the heal on a working instrument

Both had been judged against a floor that no longer exists, so both verdicts were
re-run as a 2x2 ablation on the stable build. The floor was re-checked at the most
ablated corner first -- `neither` against its own neutral twin: **0 better, 0 worse, 39
same, +0 gems.** The instrument holds still at both ends of the comparison, so every
number below is exact.

| per game | escort + heal | heal only | escort only | neither |
| --- | --- | --- | --- | --- |
| gems submitted | 140 | 139 | 117 | **140** |
| gems collected | **183** | 181 | 167 | 172 |
| gold earned | 1,501 | 1,484 | 1,352 | 1,491 |
| deaths | 38.0 | 37.4 | 38.9 | 37.9 |
| healing done | **4,270** | 2,095 | 0 | 0 |
| healing received | 27,666 | 28,459 | 25,024 | 25,358 |
| zero-gem maps | 11/39 | 12/39 | 14/39 | **10/39** |

Added to `neither`, with per-map records:

| | better | worse | same | gems |
| --- | --- | --- | --- | --- |
| escort alone (no heal) | 9 | 20 | 10 | **-23** |
| heal alone (no escort) | 15 | 14 | 10 | **-1** |
| both together | 12 | 18 | 9 | **-0** |

**The escort and the heal ability together are worth nothing.** 140 gems against 140, and
on the per-map record slightly worse -- 12 maps better, 18 worse. Removing the escort from
the standing build is 16 better, 13 worse, -1 gem. All three verdicts are the same verdict:
zero.

The earlier claim that the escort was worth +30 gems a game was an artefact of the broken
instrument. It was measured as 126 without and 144-156 with, both drawn from a
distribution that a dead loop could move by 12 gems and a win. On the fixed build both
sides sit at 140.

What the ablation does establish, and it is not nothing:

- **The mechanism works and the interaction is real.** The escort without the heal is
  *actively harmful*, -23 gems: it spends a collector to position a healer that then does
  not heal. Adding the heal back recovers all 23. So the escort genuinely does put Willow
  where it can heal -- healing done goes 0 -> 4,270, and the escort roughly doubles what
  the heal ability achieves on its own (4,270 against 2,095).
- **It converts into collection but not into banking.** Escort + heal collects 183 gems
  against neither's 172, and submits the same 140. The eleven extra gems are collected and
  then lost, which is the banking leak reappearing in a new place: a healthier team farms
  more and still dies with the bag.
- **The variance is enormous and roughly symmetric.** `01islands` 650 vs 427 and
  `01boss-battle` 188 vs 0 favour the escort; `00expanse` 481 vs 289 and
  `01yellow-brick-road` 505 vs 314 favour removing it. Nothing in the gate predicts which,
  which means the gate is not wrong so much as uninformed.

So the honest position on two sessions of work: banking (+39) and the health floor (+55)
are real and large. The heal ability is zero. The escort is zero, and cost a quarter of a
turn's fuel budget to be zero. The thing the escort was built to fix -- 60% of champion
turns spent walking -- is untouched by it.

### The escort removed

Deleted: `Bot::escort()`, `Bot::escort_work()`, `info_by_handle()` and the escort's three
cached state fields. Kept: `combat::heal_allies` (which costs ~300 fuel on the no-target
path and measured -1 gem, so effectively free), `group_cost()` (the selection loop uses
it), and the `claims` support bit (the protocol is generic and the next thing that needs
two champions on one group will want it).

Two checks on the removal, both clean:

| | better | worse | same | gems |
| --- | --- | --- | --- | --- |
| removal vs the `if (true) return false` ablation | 0 | 0 | **39** | **+0** |
| removal vs the build with the escort | 16 | 13 | 10 | **-1** |
| **floor:** removed build vs its neutral twin | 0 | 0 | **39** | **+0** |

The first row is the one that matters for correctness: deleting the code is
behaviourally identical to disabling it, so nothing else came out with it. The third
confirms the instrument still holds still on the new build.

| per game | standing build |
| --- | --- |
| gems submitted | 139 |
| gems collected | 181 |
| gold earned | 1,484 |
| deaths | 37.4 |
| healing done | 2,095 |
| zero-gem maps | 12/39 |
| wins | 1 -- and it is the `01boss-battle` 0-0 gold tiebreak again, 2,310 to 1,070, not a race won |

So sage2 stands at 139 gems a game against boss_full's 931, 0-39 on real play, with a
measurement floor of zero and three things known to be unported: `BossBot` for the
single-altar monolith maps, a cheaper selection path (farm is still 12-29k fuel a turn and
`load_groups` 61-77k), and the portfolio search.

## Boss mode, and why it is one map

First, the scope, measured before writing anything. A probe bot run for three rounds on
all 39 maps reports altar counts and monolith presence:

- **`policy.kind() == 2` matches exactly one map of 39: `01boss-battle`.**
- Fourteen more hold a monolith but have two to six altars, so an ordinary champion can
  always bank somewhere and the normal controller is right for them.
- Two have a single altar and no monolith.

Second, the mechanism, because "sage2 banks zero there" needed a cause. A distance field
from the allied spawn over three different blocker sets:

| blockers | altar at (25,20) |
| --- | --- |
| walls and holes only | **reachable, 20 tiles** |
| plus the two monoliths' tiles | **unreachable** |
| plus every camp tile | unreachable |

The map name is literal. There is no route to the only altar until a monolith dies, and a
monolith is 20,000 health, 200 strength, attack range 5 -- nothing one champion does alone.
So this is not a `bank()` bug, and boss_full fails the map too whenever it loses the race
to assemble: in a head-to-head run both teams banked **zero**, and sage2 took it on the
gold tiebreak.

### What was ported

`policy::boss_map()`, cached; `Bot::boss_farm()` replacing `farm()` on that map; static
`monolith`/`hp`/`gems`/`gold` on `GroupInfo`; and `Bot::bank_allowed()`. Two rules do the
work, both from boss.py: every champion follows the claim the first living ally published,
so the team converges instead of scattering; and the monolith is off-limits until round 650
with the party assembled and upgraded, after which it is the *only* target, so the damage
lands on one 20,000-health pool rather than being spread across thirty-one groups.

Two bugs on the way, the first of which this project has now hit three times:

1. **`strength()`, `focus()`, `health()` on an ally outside vision throw "Unit is not in
   vision" -- 8,700 throws in one game**, and sage2 earned 100 gold. boss.py uses
   `base_stats()` here for exactly that reason: a design lookup by champion type needs no
   vision. The pattern is now explicit: *any* live-unit accessor needs a vision guard, on
   allies as much as on camps.
2. **Half the turns went into `bank()`** (609 of 1,200) with `attack=0`, because a carrier
   routes toward the gated altar forever. That is what boss.py's `Progress` guard on
   `bank()` is for, which had not been ported: twelve turns with position and bag both
   unchanged means there is no route, so stop trying for eighty rounds and go and earn the
   upgrades that open it.

### Result

| per game, 39 maps | before | boss mode |
| --- | --- | --- |
| gems submitted | 139 | 139 |
| gems collected | 181 | 179 |
| gold earned | 1,484 | 1,470 |
| deaths | 37.4 | 35.4 |
| zero-gem maps | 12/39 | **10/39** |
| wins | 1 | **0** |
| **floor:** vs its neutral twin | -- | 0 better, 0 worse, **39 same** |

Three maps moved and 36 did not:

| | before | after | |
| --- | --- | --- | --- |
| `01boss-battle` | 0 | **49** | the target: sage2 banks there for the first time |
| `00fragment` | 0 | 26 | fuel side effect -- boss mode does not run here |
| `00rows` | 518 | 459 | fuel side effect |

**Net on the pool: zero.** +49 on the map it was written for, -33 from two maps that boss
mode never touches, moved because `load_groups()` now walks each group's camps and so
shifts fuel. The neutral twin shows the build is not near a boundary for a perturbation of
*that* size, but the loading change is larger than the probe, so these two are still
collateral rather than design.

And the win column went 1 to 0, which is an improvement being reported as a regression:
the old "win" was `01boss-battle` at 0-0 on the gold tiebreak. Now sage2 banks 49 there and
boss_full banks more, so it is an honest loss instead of a hollow win.

49 against boss_full's 1,033 on a map holding 1,180 gems is perhaps 5% of the way. The
diagnosis for the rest is known: champions still spend about half their turns walking to
the one far altar, and the stall signature `(position, bag)` does not fire when a carrier
oscillates near the gate rather than standing still. Closing that is more work on 1/39 of
the pool, which is why it stops here pending a decision.

## The selection cost, and the floor being wrong again

Going after `farm()` at 12-29k fuel a turn and `load_groups()` at 61-77k. The SDK is the
whole story, and reading it closely mattered more than guessing:

| call | cost |
| --- | --- |
| `camp_group::camps()` | **free** -- `noexcept`, a span over a stored vector |
| `camp::spawn_position()`, `kind()`, `is_monolith()` | **free** -- stored |
| `camp_group::gem_value()`, `gold_value()` | **free** -- `noexcept` |
| `camp_group::spawn_tiles()` | `clear()` **plus `sdk_Bitboard_Set` once per camp** |
| `bitboard::positions()` | `count()` plus `sdk_Bitboard_GetSetBits` |
| `camp::attack_range()` | `base_stats()` -- an engine design lookup, every call |
| `camp::is_visible()` + `still_there()` | three calls per camp (vision, `has_camp`, `health`) |

Four changes, all decision-neutral:

1. **`gi.tiles` from `camps()` instead of `spawn_tiles().positions()`.** A group's spawn
   tiles *are* its camps' spawn positions, and both accessors are free, where the engine
   route was about six calls per group. This is where 61-77k came from. Verified rather
   than assumed: a temporary build compared both sets on every load, **3,566 group loads
   across 39 maps, all identical.** `load_groups()` fell to 40-56k, and what remains is
   almost entirely the single `camp_groups()` call that builds the structure -- once per
   champion, on a double-budget turn, so it is left alone.
2. **The per-camp vision scan ran twice a turn** -- once to decide whether to learn a
   respawn timer, again to pick a target. Hoisted to once.
3. **The group's spawn mask cached** in `GroupInfo`, since `spawn_tiles()` is a build and
   not a read, and `farm()` plus `target_still_good()` were each asking per turn.
4. **`threat_mask` draws straight into one bitboard** rather than `mask = mask |
   around(...)`, which allocated a throwaway board, drew into it, then allocated again for
   the union. Plus camp attack range cached by kind.

Corrected instrumentation note: the first per-branch numbers put the respawn pass at
9,300-14,700, which was a measurement bug -- the `FuelSpan` was declared at function scope,
so it also counted everything after it. With correct nesting the selection loop is
**150-840** (the earlier caching had already fixed it, so the premise that selection was
expensive was wrong), the camp scan 200-1,540, the respawn pass ~1,000, and **pathfinding
is the real cost at 1,300-17,500.**

One mistake caught on the way, and it is the same mistake as always: `around()` contains a
`guard::check()`, so drawing in place silently removed the stale-plan guard from every
threat iteration. That is a correctness change smuggled into a fuel change. The check is
back, costing ~45 fuel; measured separately it moved one map and zero gems.

### The floor claim was too strong

The sweep came back at **123 gems against 139**: 4 better, 7 worse, 28 same. -16 gems
from four provably neutral changes, concentrated in three maps (00quadrants -299,
00ambush -241, 01big-world -156). The small dead-loop probe still showed 0 of 39.

So the obvious experiment: a behaviour-neutral dead loop **sized like the saving** rather
than the tiny one, spending fuel in the same two places the saving removed it.

| | gems | maps moved | wins |
| --- | --- | --- | --- |
| standing build | 123 | -- | 0 |
| **large neutral probe** | **145** | **15 of 39** | **1** |

Identical decisions on every turn. +22 gems, 15 maps moved, and `01yellow-brick-road` goes
505 to 1,012 and invents a win again. And the three maps the fuel work "broke" are exactly
the maps this probe moves the other way: 00quadrants +288, 00ambush +241, 01big-world +71.

**So "the resolution floor is zero" -- stated twice in this document and to the user -- was
wrong.** It is zero only for perturbations the size of that tiny dead loop. For a
perturbation the size of a real optimisation the floor is **about +-22 gems and +-1 win,
with 15 of 39 maps moving**, and no amount of fuel headroom removes it: a 2,000-round game
amplifies any timing difference into a different trajectory. The -16 gems is inside that
band and is therefore not a regression; it is not a measurement at all.

The fuel work is kept: decisions are provably unchanged, `load_groups()` is down from
61-77k to 40-56k, the duplicated scan and the per-turn mask builds are gone, and the
near-exhaustion turn count went from 19-32 per 400 turns to 0-12.

### What this means for measuring anything from here

The 39-map pool against one opponent cannot resolve a change worth less than ~20 gems a
game, however the fuel behaves. What *has* produced clean signal all session is never the
gem mean -- it is counts of the mechanism under test:

- banking: submitted/collected 41% -> 72%, and gems-carried-into-death 56 -> 30
- the health floor: healing received 1,350 -> 26,116, damage taken per death 1,138 -> 1,846
- the escort: healing done 2,184 -> 6,194 (and its gem effect, measured properly, was zero)
- the fuel work: `load_groups` 61-77k -> 40-56k, tight turns 19-32 -> 0-12
- the loader rewrite: 3,566 of 3,566 tile sets identical

Those are direct, they do not pass through 2,000 rounds of amplification, and every one of
them held up. The gem mean has been wrong or unresolvable every time it was used alone.
Future changes get a mechanism count, and the gem mean only as a sanity check with a
+-22 band attached.

## A wider instrument: `bench.py`

Rather than keep tuning against a number that cannot resolve what is being tuned, the
harness itself was rebuilt. Three changes to how a measurement is taken:

**More independent trajectories.** The engine is deterministic per (bot, bot, map), so
re-running gains nothing -- but every *different* pairing is its own trajectory. The four
genuinely distinct opponents in the workspace are `greatsage` (byte-identical to
`boss_full` and `bomba-rebirthed-boss`, so those three count once), `base`, `colleague` and
`boss_focus`; `starter-*` is too weak to inform anything. Four opponents over 39 maps from
**both sides** is 312 games against the old 39.

**Both sides, always.** sage2 had only ever played team A. The rules break ties in Team
B's favour, so a one-sided pool measures a bot and a seat at once. The harness reports a
by-side split so a pool bias stays visible rather than being averaged in.

**Mechanism counts, not the gem mean.** Fourteen metrics, each a per-game mean over every
opponent and side: submitted, collected, submitted-over-collected, gems lost to deaths,
gold, deaths, damage taken per death, healing received, healing done, monster damage done,
monster damage done per point taken, kills, opponent gems, win rate. These are the
quantities that gave a clean answer every time this project got something right.

**`--twin` is the part that keeps it honest.** Given a build whose *decisions* are
identical to the subject's -- a dead loop is the usual trick -- every metric is printed
with the band that neutral build moved it by, and a change inside its own band is labelled
`noise` rather than reported as a result. The band is measured per metric, not assumed,
because there is no reason for healing received and the gem mean to be equally fragile.

Side attribution is the one place a bug would silently halve the value of playing both
sides, so `read()` is self-tested against synthetic statistics covering the case that would
hide it -- the subject on team B, losing. Eleven checks, all passing.

    ./bench.py sage2 --twin sage2_twin --tag sage2_v1
    ./bench.py sage2 --tag sage2_v2 --baseline sage2_v1
    ./bench.py --compare sage2_v1 sage2_v2

### What it resolves

624 games: sage2 and its decision-identical twin, each over 4 opponents x 39 maps x 2
sides. Metrics ordered by how well they survive a neutral perturbation -- the band is how
far the twin moved each one, and nothing smaller than its band is a measurement.

| metric | value | band | band % |
| --- | --- | --- | --- |
| damage taken per death | 1,935.7 | 12.8 | **0.7%** |
| healing received | 26,979 | 198 | **0.7%** |
| submitted / collected % | 75.3 | 0.6 | **0.8%** |
| opponent gems | 929.7 | 8.5 | 0.9% |
| deaths | 35.7 | 0.4 | **1.0%** |
| monster dmg done per taken | 1.00 | 0.02 | 2.4% |
| monster damage done | 41,551 | 1,099 | 2.6% |
| healing done | 2,366 | 81 | 3.4% |
| gold earned | 1,488 | 93 | 6.3% |
| gems lost to deaths | 43.2 | 2.8 | 6.6% |
| gems collected | 174.9 | 15.9 | 9.1% |
| **gems submitted** | **131.7** | **13.0** | **9.9%** |
| kills | 0.8 | 0.1 | 18.5% |
| win rate % | 1.0 | 1.0 | **100%** |

Two things follow, and together they are the answer to why this project kept drawing wrong
conclusions.

**Widening the pool helped, but only linearly.** The same neutral perturbation that swung
the 39-map gem mean by +-22 on ~134 (16%) swings the 312-game mean by +-13 on 132 (10%).
Eight times the games bought a 1.6x improvement, about the sqrt(8) one would expect if the
trajectories are independent. Resolving a 5-gem change this way would need roughly 5,000
games. **The pool cannot be widened into a fine instrument.**

**Choosing the metric helped by an order of magnitude, for free.** Submitted-over-collected
resolves to 0.8%, deaths to 1.0%, healing received to 0.7%, damage taken per death to 0.7%
-- twelve to fourteen times finer than the gem mean on the identical games. A ratio
divides out the trajectory: if a different timing sends a champion to a different camp, it
collects and banks differently but the *fraction* it banks barely moves. The gem mean keeps
the trajectory in the numerator.

**Win rate is the worst possible metric here** -- band 1.0 on a value of 1.0, so it carries
no information at all at this strength. Every conclusion drawn from "wins" in this document
was noise, which is consistent with the two fake wins already caught.

Measured along the way: sage2 wins **3 of 312 games**, all three against `colleague`. All
four opponents bank 900-960 gems against it, so they are about equally strong from here and
`greatsage` is not a special case. The by-side split is 133 gems and 1.3% wins as team A
against 130 and 0.6% as team B -- so the pool has little side bias despite the tiebreak
favouring B, and the previous one-sided sweeps were not measuring a seat.

### The rule this project should have had from the start

Judge a change by the count of the mechanism it claims to change, and treat the gem mean as
a sanity check with a 10% band attached. Concretely, for the changes already made:

| change | its own metric | band | verdict |
| --- | --- | --- | --- |
| banking | submitted / collected | 0.8% | 41% -> 72%, overwhelming |
| health floor | healing received | 0.7% | 1,350 -> 26,116, overwhelming |
| escort | healing done | 3.4% | 2,184 -> 6,194 real, but gems zero |
| loader rewrite | tile sets identical | exact | 3,566 of 3,566 |
| fuel work | `load_groups` fuel | exact | 61-77k -> 40-56k |

Every one of those is decisive on its own metric. Not one of them was decisive on gems.

## The escort, re-judged -- and the previous verdict was wrong

The escort was removed on the strength of a 39-map measurement that read **140 gems
against 140**, reported as "worth exactly zero". It was recovered into the *current* build
(so the comparison isolates the escort rather than also undoing the loader rewrite and
boss mode) and run through the new harness: 624 games for the escort build and its twin,
against the 624 already measured for the build without it.

Bands here are the **worse of the two twins'**. Using only the subject's band flatters a
result -- a change can clear its own build's band and still sit inside the band of the
build it is compared against, which means the two are not distinguishable. `bench.py` now
takes the conservative band and prints the signal-to-band ratio rather than a bare
real/noise label, because 1.04x and 13.2x should not read the same.

| metric | no escort | escort | change | band | ratio |
| --- | --- | --- | --- | --- | --- |
| **healing done** | 2,366 | **4,148** | **+1,782** | 135 | **13.2x** |
| damage taken per death | 1,936 | 1,899 | **-37** | 12.8 | 2.9x |
| **deaths** | 35.73 | **37.01** | **+1.28** | 0.62 | 2.1x |
| monster dmg done per taken | 0.98 | 1.02 | +0.04 | 0.02 | 1.7x |
| gems collected | 174.9 | 193.2 | +18.4 | 15.9 | 1.2x |
| gems submitted | 131.7 | 145.3 | +13.6 | 13.1 | **1.0x** |
| gems lost to deaths | 43.2 | 48.0 | +4.8 | 4.7 | 1.0x |
| gold earned | 1,488 | 1,538 | +50.7 | 93.0 | 0.5x |
| submitted / collected % | 75.30 | 75.17 | -0.13 | 0.83 | 0.2x |
| healing received | 26,979 | 26,961 | -18 | 301 | 0.1x |
| win rate % | 0.96 | 0.96 | +0.00 | 0.96 | 0.0x |

**The mechanism is unambiguous and the earlier "zero" was wrong.** Healing done is
13.2x its band. Gems submitted is +13.6 rather than 0 -- the old pool's +-22 band simply
could not see it.

**But "worth +13.6 gems" is also too strong.** At 1.0x the conservative band, gems
submitted is exactly at the resolution limit even with 312 games. The harness's own first
printout called it "real" because it used only the escort twin's narrower band of 8.2; on
the honest band it is a coin flip. The defensible statement is: the escort's mechanism is
large and certain, and its effect on gems is positive-trending and still unresolved.

**And it costs deaths.** +1.28 deaths at 2.1x the band, with gems-lost-to-deaths +4.8.
That is not a side effect to wave away: the escort parks the healer next to whatever the
party is clearing.

The most interesting number is the one that did **not** move. Healing *done* rose 1,782
while healing *received* did not move at all (-18, 0.1x). Those count the same events, so
the only reading is substitution: Willow's field heals replace spawn healing the allies
would otherwise have walked home for. Total sustain is unchanged; what changes is where it
comes from. That is precisely the travel problem the escort was built for -- allies stop
making the trip -- and it shows up as +18.4 collected rather than as better survival.

Also visible only at this width: the side split moved from 136 gems as team A to 154 as
team B, so the escort is worth more from the seat that wins ties. And sage2 now takes
games off two opponents rather than one (`colleague` 2.6%, `boss_focus` 1.3%).

### What this says about the method, twice over

The removal was a mistake caused by trusting a mean inside its own noise -- the same error
this document records for the +30 that preceded it. Both readings of the escort, "+30" and
"zero", came from a pool that could not resolve either. Only the mechanism count was ever
right: healing done said the escort worked, at 2.8x on the old pool and 13.2x here, every
time it was measured.

### Seven baselines, and the resolution of the sweep itself

| per game | 1 | 2 | 3 | 4 | 5 | 6 | 7 | boss_full |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | claims | geometry | respawn | banking | floor | heal | return leg | |
| gems submitted | 31 | 14 | 40 | 78 | 133 | **136** | 91 | 931 |
| gems collected | 89 | 45 | 96 | 108 | 170 | **176** | 123 | 1,013 |
| gold earned | 863 | 479 | 910 | 1,034 | 1,487 | **1,480** | 1,036 | 9,340 |
| deaths | 46 | 45 | 53 | 52 | 38 | **37** | 41 | 4.9 |
| healing received | -- | -- | -- | 1,350 | 26,116 | **28,038** | 26,098 | 51,949 |
| zero-gem maps | 23 | 29 | 24 | 11 | 10 | **11** | 15 | -- |
| wins | 0 | 0 | 0 | 0 | 0 | **1** | 1 | -- |

Baseline 7 was reverted; re-running the restored build gave 126 gems, 1,500 gold, 37
deaths, 11 zero-gem maps.

**There is no sweep noise. The engine is deterministic.** Two sweeps of an identical build
came back byte-for-byte identical across all 39 statistics files -- same digest, same win
at the same score, 1,018 to 96 -- and `match.seed` is fixed per map. This was asserted
the other way earlier in this document, and the "+-10 gems of sweep noise" calibration
written here was wrong. It has two consequences, and they point in opposite directions:

1. Every number in this file is exact. A one-gem difference between two builds is a real
   difference, not a sampling artefact. The heal ability's +3 gems was a genuine +3, not
   "inside the noise" as recorded above.
2. Thirty-nine maps is therefore the *entire* sample, and no amount of re-running enlarges
   it. A mean over 39 fixed games hides its own distribution, so every change from here is
   judged by its **per-map record** as well as its mean.

The 136 -> 126 gap between baseline 6 and the post-revert build was consequently not noise
either: it was a real regression, because the revert was incomplete. Reverting the cost
line left `load_altars()` being called from inside `load_groups()` and `altar_dist` still
being computed per group, so the build measured after the revert was not the build measured
before the change.

The "1 win" in those columns is not a win in any useful sense and should not be read as
one. It is `01boss-battle`, where both teams submit **zero** gems for 2,000 rounds and the
match falls through the tiebreak chain gems -> gold, which sage2 takes 2,310 to 1,070. The
same map in every sweep, for the same reason. It is also the map where sage2 deals *more*
monster damage than boss_full, 73,425 against 40,715, while dying eighty times and banking
none of it: a single altar gated behind a monolith, which is the map class boss_full
answers with a separate controller (`policy.kind() == 2`, `BossBot`) and sage2 does not
answer at all.

Two sessions' worth of changes have taken sage2 from 31 to 136 gems a game, 4.4x, with no
change at all to farming, routing or target selection -- every gain came from not losing
gems already collected and not dying with them. The remaining gap to boss_full is 6.8x on
gems and 7.5x on deaths, and it is now concentrated in one thing: a champion spends 60% of
its living turns walking and 15-20% attacking.

### Every fix tonight traded one bug for another

| Change | Fixed | Broke |
| --- | --- | --- |
| claims snapshot | 38 of 39 maps were inert | -- |
| cached group geometry | 00lanes, 01boss-battle | three other maps, halved income |
| respawn memory | all of the above | -- |

The pattern is the point: each piece of the Python bot that looked like an optimisation
turns out to be load-bearing, and its absence only shows up in a full sweep. `respawns`,
`Progress`, capture handover, the cooperative rally -- these were catalogued as remaining
work hours earlier and were then rediscovered as regressions instead. greatsage's 1,443
lines encode a few hundred interacting decisions; porting the structure while dropping
the details yields a bot that looks complete and performs at a tenth.

Nothing built so far uses the 229-playouts-per-turn advantage that justifies C++. The
survival model is cheap arithmetic that would run identically in Python.

### The recurring lesson of this port

Three separate classes of bug, all of them things the Python bot already handled and I
dropped:

1. `camp_group::state()` throws without vision -- guard with a spawn-tiles/visible
   intersection. **4,726 throws in one game.**
2. `camp::health()` throws once the camp dies and leaves vision -- guard every read after
   an action with `has_camp(spawn_position())`. **43 throws.**
3. Routing onto a group's spawn tiles bails once visible, because live camps occupy them.

Most of the Python bot's 1,443 lines are this kind of accumulated edge case, not
structure. Porting the structure took hours; the edge cases are the actual asset, and
they only surface by running.

Remaining before sage2 is worth scrimmaging: objective persistence and claims, capture
handling, the cooperative rally, respawn tracking, progress guards, cross-component and
crystal routing, ward scouting, altar locks, and shop batching. That is most of what the
Python bot's 1,443 lines actually are.

**Every gate from M2 on is a scrimmage against real opponents, not local self-play.** The
22-candidate search failed because local self-play cannot measure combat: every bot in
that harness avoids fights.

**Process, non-negotiable, straight from the winners:** at least two measured iterations
per day; one knob per experiment; ablate before believing; keep the previous best as the
sparring partner and branch from it on failure. `just-woke-up` did 57 versions in 25
days and said that *was* the strategy.

### 5.1 Sequencing note

M1 and M2 are the only hard parts. M1 is self-contained and testable offline. M2 is
where the bet lives: if the global plan is not at least at parity with greedy selection,
the thesis is wrong and we stop and keep `boss_full`. That gate is deliberately early
and brutal.

---

## 6. Risks, and what would falsify this

- **The plan may lose to greedy under interference.** Static routes assume the enemy
  does not disrupt them. Mitigation: M2's gate is parity, not improvement; the executor
  re-plans locally. If parity fails, abandon.
- **Portfolio search depends on simulator fidelity** — the 2017 PGS paper's main
  finding. Mitigation: M1 gates on exact damage prediction before any search is built.
- **Eight bytes may not be enough for intel.** Mitigation: symmetry-based inference needs
  no bandwidth at all; shared bits are an enhancement, not a dependency.
- **Rewrites lose accumulated bug fixes.** The current navigation, fuel-suspension replan
  guard, and capture-handover protocol encode real lessons. Port them deliberately
  rather than rediscovering them.
- **My own track record on this game.** 13 of my 14 predictions this session were wrong.
  Every claim above is a hypothesis with a gate, not a conclusion. The only measured
  truths here are the growth table, the 14 experiment results, and the public pick rates.

### What we know versus what we are betting

**Known:** the constants are at a local optimum; Willow's scaling is last in the game;
top-5 teams run Heart of Ruin at 96%; our architecture cannot use him; a perfect combat
simulator is cheap because the game is deterministic; we have 1,018 unused draft-memory
bytes and ~1.7M unused fuel per turn.

**Bet:** that moving planning into the draft phase and spending the freed budget on
combat search and denial produces a step change rather than an increment.

---

## 7. Honest expectation

This is a 2–4 week project at two iterations a day, not a sprint fix. It should not be
started against Saturday's lock — ship `boss_full` for Sprint 2.

The realistic target is the **11 Nov UK qualifier**, where the gap is ~250 Elo rather
than ~490. "Inconceivably strong" is not something I can promise; what I can say is that
every top team's postmortem describes the same path — a clear game philosophy, relentless
measured iteration, and a handful of creative mechanics nobody else is using. The denial
economy in §4.4 is the most under-exploited thing I found in the entire rulebook, and it
is sitting in plain sight for anyone who reads that a stun cancels a tribute.

## The escort's death cost: diagnosed correctly, not fixed

(Measurement paused at 00:50 on 2026-10-22 and finished at 10:49. The subject's 312 games
survived the pause; only the twin's 312 had to be replayed.)

### The mechanism, diagnosed before changing anything

The stated premise -- that the escort parks the healer in danger -- was wrong:
the escort's +1.28 deaths are **not** the healer standing in danger. Per-champion over 312
games -- Willow +0.41, Varg +0.37, Ryth +0.32, Vendetta +0.21, Marcella -0.04 -- and
Willow takes *less* monster damage with the escort, 6,257 against 5,714. The real cause,
from branch counters over three maps:

| | no escort | escort |
| --- | --- | --- |
| `heal_trip` firings (trips home) | 202 | **179** |
| spawn-heal holds | 115 | **86** |
| reactive disengages | 709 | **465** |
| attacks | 633 | **780** |
| banks | 172 | **305** |

A field heal lifts an ally back over its withdrawal floor, so it stops going home. The
heal is worth about a tenth of maximum health; the trip home is worth all of it. The team
was trading full-health returns for middling-health uptime, which is also where the extra
gems came from.

### The fix under test (`bots/sage2_esc2`)

`combat::heal_allies` declines any ally already below its withdrawal floor (0.30, or 0.43
carrying gems) and lets it go home, topping up only champions that are staying. The floors
moved into `combat.h` so both sides share one definition. Counters over the same three
maps: trips home 179 -> **232** (above the no-escort 202), spawn holds 86 -> 104, heals
cast 27 -> 20, attacks 780 -> **850**.

### The verdict, on conservative bands

Bands are the worse of both twins'. Against the escort without the fix:

| metric | escort | + fix | change | band | ratio |
| --- | --- | --- | --- | --- | --- |
| healing done | 4,148 | 3,166 | **-982** | 135 | **7.2x** |
| healing received | 26,961 | 26,329 | -633 | 301 | 2.1x |
| damage taken per death | 1,899 | 1,883 | -15.6 | 7.8 | 2.0x |
| **deaths** | 37.01 | 36.75 | **-0.26** | 0.62 | **0.4x noise** |
| gems submitted | 145.26 | 147.12 | +1.86 | 8.25 | 0.2x |

**The fix does exactly what it was designed to do and does not fix the problem.** Healing
done falls 982 at 7.2x the band, the trips home come back on the counters (179 -> 232), and
the deaths do not follow: -0.26 of the +1.28, at 0.4x the band. The diagnosis was right
about the *mechanism* -- field heals were suppressing recall trips, which the counters show
plainly -- and wrong that reversing it would recover the deaths.

The settled position, escort-plus-fix against no escort at all:

| metric | no escort | escort + fix | change | band | ratio |
| --- | --- | --- | --- | --- | --- |
| healing done | 2,366 | 3,166 | +800 | 81 | **9.9x** |
| damage taken per death | 1,936 | 1,883 | -52.6 | 12.8 | **4.1x** |
| healing received | 26,979 | 26,329 | **-651** | 198 | **3.3x** |
| **deaths** | 35.73 | **36.75** | **+1.02** | 0.36 | **2.8x** |
| monster dmg done per taken | 0.98 | 1.03 | +0.04 | 0.02 | 1.9x |
| **gems submitted** | 131.67 | **147.12** | **+15.45** | 13.05 | **1.2x** |
| gems collected | 174.87 | 193.59 | +18.73 | 15.88 | 1.2x |
| gems lost to deaths | 43.20 | 46.48 | +3.28 | 2.83 | 1.2x |
| gold earned | 1,488 | 1,551 | +63.2 | 93.0 | 0.7x |
| **win rate %** | 0.96 | 0.96 | **+0.00** | 0.96 | **0.0x** |

Both sides of the trade are now real, and they are not equally well established: the gem
gain is +15.45 at **1.2x** the band -- only just resolved -- while the death cost is +1.02
at **2.8x**. Total sustain is *lower* than with no escort at all (healing received -651,
3.3x), which with deaths up is coherent: the team absorbs less and dies more, and pays for
it with field time that earns gems.

**And the win rate does not move at all: 0.96% either way, 0.0x its band.** That is the
metric the competition is decided on. sage2 banks 147 gems against an opponent's 925, so
16%; a 12% improvement on our own number does not come near changing an outcome.

### Decision: the escort stays out, for a different reason than before

Last time it was removed because it measured as zero, which was an artefact. It measures as
+15 gems, and it still should not go back in:

- the win rate is unmoved at 0.0x its band, and that is what games are decided on
- the death cost is better established (2.8x) than the gem gain (1.2x)
- it is ~130 lines plus state, and it costs the healer about a quarter of a turn's fuel

This is worth revisiting only if the 6x gap to boss_full closes enough for 15 gems to
matter. `bots/sage2_escort` (escort) and `bots/sage2_esc2` (escort plus the heal floor) are
kept in the workspace with their twins and their sweeps, so it need not be rebuilt.

### The heal floor on its own: tested, rejected

The heal floor is independent of the escort, so it was applied to `sage2` alone -- the
diff against the standing bot is five lines in `combat.h` plus moving the two constants
there, taken verbatim from the escort build so both experiments test the same code rather
than two re-typings of an idea.

The prediction going in was explicit: without an escort the healer has far fewer targets
in range, so if the floor matters at all it should show as a *cleaner* death reduction than
the escort's -0.26. That was wrong.

| metric | sage2 | + heal floor | change | band | ratio |
| --- | --- | --- | --- | --- | --- |
| healing done | 2,366 | 1,697 | **-669** | 81 | **8.3x** |
| healing received | 26,979 | 25,984 | **-995** | 198 | **5.0x** |
| damage taken per death | 1,936 | 1,899 | -36.4 | 12.8 | **2.8x** |
| **deaths** | 35.73 | 36.01 | **+0.28** | 0.36 | **0.8x noise** |
| gems submitted | 131.67 | 131.88 | +0.21 | 13.05 | 0.0x |
| gems collected | 174.87 | 175.27 | +0.41 | 15.88 | 0.0x |
| win rate % | 0.96 | 0.96 | +0.00 | 0.96 | 0.0x |

It heals 669 less, absorbs 995 less, dies at *lower* accumulated damage (2.8x, worse), and
buys nothing: deaths unmoved and trending the wrong way, gems unmoved to within a fifth of
a gem. **Rejected.** `sage2` was never modified -- the experiment ran as `bots/sage2_hf`.

The useful part is what it rules out. "Healing an ally below its withdrawal floor cancels a
trip home" was a real mechanism **specific to the escort's party play**, where Willow stood
beside four allies all turn and topped them up at scale; the counters showed heal_trip
firing 11% less and spawn holds 25% less there. Without the escort the healer rarely has a
hurt ally in cast range, so its heals were not cancelling withdrawals -- they were simply
sustain, and declining them removes sustain for no return. A mechanism measured inside one
configuration does not transfer to another, even though the code is identical.

### A harness bug worth fixing

The waiter shells used to block on these sweeps were written as
`until ! pgrep -f 'bench.py sage2'; do sleep; done`. The shell's own command line contains
that pattern, so `pgrep` matches the waiter itself and it never exits -- three were left
spinning and had to be killed by PID. Any future waiter needs a pattern that cannot match
itself, or should watch the output file instead.

## Where the 6x income gap actually is

Decomposed from the 624 games already on disk -- only our own side had ever been
aggregated. Per game, sage2 against the four opponents:

| | sage2 | opponents | ratio |
| --- | --- | --- | --- |
| gems submitted | 132 | 930 | 7.1x |
| gems collected | 175 | 989 | 5.7x |
| gold earned | 1,488 | 9,121 | 6.1x |
| monster damage done | 41,551 | 131,586 | 3.2x |
| **damage per gem collected** | **237.6** | **133.1** | **1.8x worse** |
| **gold per 1k monster damage** | **35.8** | **69.3** | **1.9x worse** |
| submitted / collected | 75.3% | 94.0% | |
| deaths | 36 | 6 | |
| kills / assists | 1 / 1 | 24 / 13 | 30x / 21x |
| champion damage taken | 26,902 | 9,090 | 3.0x worse |
| gold left unspent | 151 | 668 | |

**The gap is two independent problems, and they want different fixes.** Throughput: 3.2x
less camp damage dealt, which is deaths (36 at ~60 rounds of respawn is about 21% of the
team's champion-rounds) plus the 60% of living turns spent walking. Efficiency: 1.8x worse
gems *per point of damage dealt* and 1.9x worse gold. The second one is not a throughput
problem at all -- the damage is being spent on the wrong camps.

And a third thing that is neither: **24 kills against our 1**, with 3x the champion damage
taken. Enemy champions kill us two dozen times a game and we kill one of them. At 39% of
all damage we absorb, that is not a side issue.

### What sage2's scoring was missing

`sage2`'s cost was `travel * 100 / value`. The Python `strategy.choose_group`, which is the
thing achieving 133 damage per gem, scores on far more. In rough order of likely value:

1. **Clear time, `hp / dps`.** With no health term, a 20,000-health monolith and a
   120-health gem cluster look equally attractive per unit of value. This is the one the
   measurement points at directly.
2. **Half-cleared camps cost less** -- `clear *= remaining_hp / design_hp`, so a group
   someone already chewed into is cheap. sage2 always prices groups at full design health.
3. **`RewardAvailable` is free** -- Python sets `clear = 0` and collects. sage2 does not
   distinguish a ready reward from a full-health group.
4. **Varg's splash triples its effective dps** -- `damage * min(count, 3)`. Varg is the
   second draft pick and its clear speed is never priced.
5. **Gold weighted by phase** -- 1.2x before round 500, 0.25x after, against sage2's flat
   `gold / 2` all game.
6. **A risk term** from incoming damage x clear time against a health budget.
7. **Exact path distances** for the top candidates from a distance field, where sage2 uses
   Chebyshev throughout and so under-prices targets behind walls.

### Clear time: applied, with an honest split

`group_cost` now sums turns -- travel, `hp / dps`, and capture -- and divides by value, as
the Python does. One change; `gi.hp` already existed from boss mode.

| metric | before | + clear time | change | band | ratio |
| --- | --- | --- | --- | --- | --- |
| healing received | 26,979 | 28,301 | +1,322 | 198 | **6.7x** |
| damage taken per death | 1,936 | 1,991 | +55.7 | 12.8 | **4.3x** |
| monster dmg done per taken | 0.98 | 1.05 | +0.06 | 0.02 | **2.7x** |
| **gold per 1k monster damage** | 35.81 | 39.08 | **+3.27** | 1.26 | **2.6x** |
| **deaths** | 35.73 | **34.81** | **-0.92** | 0.36 | **2.5x** |
| *opponent gems* | 929.7 | *950.9* | *+21.2* | 8.5 | *2.5x* |
| **damage per gem collected** | 237.62 | **221.09** | **-16.52** | 14.02 | **1.2x** |
| gold earned | 1,488 | 1,583 | +95.1 | 93.0 | 1.0x |
| gems submitted | 131.67 | 138.40 | +6.73 | 13.05 | **0.5x noise** |
| gems collected | 174.87 | 183.22 | +8.36 | 15.88 | 0.5x noise |
| win rate % | 0.96 | 0.64 | -0.32 | 1.60 | 0.2x noise |

Six real positives, and they are the right six: the efficiency metrics the change targets
all moved, and deaths fell 0.92 at 2.5x the band. **But the objective did not move
measurably** -- gems submitted +6.73 at 0.5x the band -- and the opponents gained 21 gems
at 2.5x, which is real and probably ours: preferring cheap gem clusters leaves the big
camps uncontested. The overall gap went 7.06x to 6.87x.

Note also that the two-map smoke test showed damage-per-gem 185 -> 149, where 312 games
showed 237.6 -> 221.1. Two maps flattered it by a factor of two, exactly as every
small-sample result in this document has.

**Applied to `sage2`** (`c3c8f3a2e4ee6511`), because the cost function is more correct --
pricing clear time is not a tuning choice -- and six survival and efficiency metrics are
solidly real. The honest caveat is that the gem and win effects are unproven, and reverting
is one `group_cost` body. We are still 1.66x worse than the opponents on damage per gem,
so items 2 through 7 above are where the rest of that factor lives.

## Engine 1.0.3: nothing we measured changes, but the band estimates are shakier than claimed

The ladder runs engine **1.0.3**; every local game until now ran **1.0.2**. Upgraded the
CLI 3.0.4 -> 3.0.5 and the workspace with it, surgically -- copied the new `cambc.h`, added
the new map, bumped the pin -- rather than `cambc init` in a directory holding 54 bot
builds. Old SDK and config are in `backup-pre-1.0.3/`.

**The SDK did not change functionally.** The whole 3.0.4 -> 3.0.5 header diff is one
documentation comment about how long debug drawings persist; `imports.h` (the ABI structs)
is byte-identical, and `sage2` rebuilt to the same wasm hash `c3c8f3a2e4ee6511`. That makes
the comparison clean: identical binary, identical 39 maps, only the engine differs.

**The damage model survived intact.** sage2's built-in gate re-ran in-engine on 1.0.3:
**600 vectors, 0 mismatched, `worst_abs=0`, `worst_rel=0`**, plus 21/21 survival checks.
The model was originally fitted against 22,029 in-engine predictions and is still
bit-exact, so no damage, mitigation or emblem constant moved.

**Behaviour changed in 59 of 312 games** and was bit-identical in the other 253 -- single
games swinging as far as `01yellow-brick-road` 732 -> 182. But every aggregate is tiny:
gems submitted -1.41, deaths -0.10, damage per gem -0.27, win rate +0.00.

### The band is itself a noisy estimate -- by up to 57x

Judging that change needed a band, and there are now five independent decision-identical
twins on disk. Estimating the same band five times:

| metric | min band | max band | spread | 1.0.3 change | vs max |
| --- | --- | --- | --- | --- | --- |
| healing done | 2.81 | 160.67 | **57x** | -50.51 | 0.31x |
| monster damage done | 37.32 | 1,798 | **48x** | -370 | 0.21x |
| deaths | 0.03 | 0.62 | **24x** | -0.10 | 0.16x |
| gold earned | 6.37 | 93.00 | 15x | -7.42 | 0.08x |
| healing received | 19.54 | 300.68 | 15x | **-512.54** | **1.70x** |
| gems submitted | 1.40 | 13.05 | 9x | -1.41 | 0.11x |
| damage per gem collected | 2.04 | 14.02 | 7x | -0.27 | 0.02x |
| win rate % | 0.00 | 1.60 | -- | +0.00 | 0.00x |

**A single twin does not give a reliable band.** The same quantity, measured off five
different builds whose decisions are each unperturbed, varies by a factor of 24 for deaths
and 57 for healing done. Every "ratio" quoted earlier in this document used one or two
twins and is therefore over-precise.

That does not invalidate the big results, and it is worth being explicit about which
survive the widest band and which do not:

| conclusion | holds? |
| --- | --- |
| banking: submitted/collected 41% -> 72% | yes, overwhelming |
| health floor: healing received 1,350 -> 26,116 | yes, overwhelming |
| escort: healing done 2,184 -> 6,194 | yes, 13x under any band |
| damage model bit-exact; 3,566 tile sets identical | yes, exact, no band needed |
| clear time: deaths -0.92 | yes -- 1.5x even against the widest band of 0.62 |
| clear time: gems +6.73 | **no** -- 0.5x against the widest band |
| escort: gems +13.6 | **no** -- 1.0x, and that used only two twins |

So the pattern holds and sharpens: **mechanism counts survive; means near the band do
not.** Anything claimed between 1x and 2x in this document should be read as unproven.

### Verdict on 1.0.3

Against the widest of five band estimates, **the only metric that moves is healing
received, -513 (about 1.8%)**. Everything we acted on -- gems, deaths, damage per gem, win
rate -- is deep inside noise. **No conclusion in this document changes.** The small drop in
healing received is consistent with a tweak to spawn healing or regeneration, and is worth
remembering but not chasing.

### The new map: `00road-of-riches`

40 maps now. Swept both sides against all four opponents, 8 games:

| | |
| --- | --- |
| mean | **104 gems against 1,025** |
| record | **0-8** |
| best | 281 against `colleague` on side A |
| worst | 56 against three opponents on side A |

Worse than our pool average of 137, and every opponent reaches ~1,020 and wins on the gem
threshold by round 1,350-1,600. Three opponents produce *identical* scorelines (56-1024 on
A, 100-1012 on B), which is what the deterministic engine does when `base`, `boss_focus`
and `greatsage` draft and open the same way. The map is now in the pool, so the 39-map
baselines in this document are no longer directly comparable to future 40-map runs.

## What the top teams actually do, from their own replays

Logged in and pulled real ladder data: the full 744-team ladder, 445 ranked matches
across the top 20, and 30 downloaded match summaries from the top three
(`Intercontinental Fish`, `prism best girl`, `procless`).

**Our team is `Milk and Potatoes`, rank 157 of 744, rating 1682, 942 matches, Sprint 1
qualified.** 19W/21L over the last 40 ranked games, so the rating is stable. Rank 3 is
2154 -- a 472-point gap with 154 teams in between.

### The gap, measured against the top three rather than against local bots

| per game | top 3 | sage2 | ratio |
| --- | --- | --- | --- |
| gems submitted | 827 | 137 | 6.0x |
| gems collected | 1,158 | 182 | 6.4x |
| gold earned | 7,504 | 1,576 | 4.8x |
| **damage per gem collected** | **106.4** | **220.8** | **2.1x worse** |
| **submitted / collected %** | **71.4** | **75.4** | **we are ahead** |
| deaths | 6 | 35 | 0.2x |
| kills / assists | 9 / 17 | 1 / 1 | 12x / 17x |
| champion damage taken | 24,672 | 26,902 | **0.9x -- about equal** |
| healing received | 54,987 | 27,788 | 2.0x |
| **healing done** | **0** | **2,496** | -- |
| mean rounds to finish | 1,087 | ~1,800 | |

Four of these rewrite earlier conclusions:

1. **Banking is solved and we are ahead of the top three.** 75.4% of collected gems banked
   against their 71.4%. The whole banking thread -- the single biggest measured win of this
   project -- took us past the best teams on that axis. It is no longer a lever.
2. **Damage per gem is the biggest remaining efficiency gap, and bigger than thought:
   2.1x**, worse than the 1.8x measured against local bots.
3. **Champion damage taken is about the same as theirs.** We are not being beaten up more.
   But they convert 9 kills and 17 assists a game out of it and we convert one of each. We
   absorb a normal amount of fighting and get nothing back.
4. **The top three do no healing at all.** Healing done is exactly zero across thirty
   matches, and Willow never appears in 144 champion-games. That independently corroborates
   the escort and heal-floor measurements: the heal ability is not part of the meta.

### Draft: pick rate measured, and then measured to be the wrong signal

**CORRECTION -- the table immediately below is invalid. Keep reading.** It was computed
from the `draftPicks` field of `cambc matches list`, which does **not** identify the
champions a team fielded. Verified against an authoritative match summary for match
`4e5343c6`: the roster says our team fielded Prism, Heart of Ruin, Marcella, Vesper Vale
and Vendetta, while `matches list` reported `draftPicks` [5, 11, 6, 1, 2], which decodes to
cassi_and_issac, heart_of_ruin, tavi, vendetta, willow. Two of five overlap, by chance. Only
`roster.champions[].name` inside a downloaded summary is authoritative. The pick and
first-pick percentages below are therefore meaningless, and so is the draft order built
from them -- which is consistent with that order measuring as the worst change of the whole
project.

Pick rates over 445 ranked matches, 800 team-entries among the top 20 (INVALID, see above):

| champion | pick % | first-pick % | we ranked it |
| --- | --- | --- | --- |
| vendetta | 89 | 11 | 2nd |
| cassi_and_issac | 77 | 25 | 7th |
| marcella | 72 | 0 | 1st |
| **heart_of_ruin** | **72** | **54** | **12th (last)** |
| willow | 60 | 0 | 3rd |
| prism | 20 | 0 | 11th |
| vesper_vale | 16 | 0 | 8th |
| tavi | 13 | 9 | 6th |
| stellar | 12 | 0 | 10th |
| **varg** | **8** | 0 | **4th** |
| ren | 5 | 1 | 9th |
| **ryth** | **2** | 0 | **5th** |

The order was close to inverted at both ends. So it was rewritten by pick rate and
measured -- and **it was a disaster**:

| metric | old order | by pick rate | change | ratio |
| --- | --- | --- | --- | --- |
| gems submitted | 137.00 | **108.76** | **-28.24** | 226x |
| deaths | 34.71 | **50.79** | **+16.07** | 90x |
| damage taken per death | 1,980 | 1,470 | -509 | 107x |
| submitted / collected % | 75.37 | 66.48 | -8.89 | 23x |

Unambiguous even against the widest band measured anywhere in this document (2.2x on gems,
26x on deaths). **Pick rate measures what a strong team can use, not what this bot can
use.** The per-champion data from the top three's own games says why:

| champion | gems/game | deaths | dmg per gem | games |
| --- | --- | --- | --- | --- |
| Prism | **469** | 2.4 | **71** | 10 |
| Vesper Vale | **394** | 1.3 | 108 | 30 |
| Vendetta | 268 | 1.1 | 116 | 22 |
| Marcella | 220 | 1.1 | 103 | 18 |
| Heart of Ruin | 174 | **0.6** | 97 | 26 |
| Ryth | 146 | 1.1 | 120 | 19 |
| Issac | 64 | 2.2 | 149 | 9 |
| **Cassi** | **47** | 2.2 | **278** | 9 |

Every one of ours collects 27-49 gems and dies **7 to 8 times a game** against their 0.6
to 2.4.

`cassi_and_issac` is first-picked 25% of the time and is the *least* efficient farmer on
the board. Part of its value is mechanical and I had missed it: **it is a two-for-one**,
yielding both Cassi and Issac from a single pick, so the roster it produced fielded six
units from five picks. Strong teams take it to fight with. This bot manages one kill a
game, so a combat champion is a wasted slot however many bodies it brings.

`prism` and `vesper_vale` are the two best collectors on the ladder, at 469 and 394 gems a
game, and the old order ranked them 11th and 8th.

So a second order is under test, by farming efficiency rather than popularity: prism,
heart_of_ruin, marcella, vesper_vale, vendetta, ryth, tavi, stellar, cassi_and_issac, varg,
willow, ren. Caveat recorded in the source: samples are 9 to 30 champion-games and
champion performance is confounded with the team playing it, so this is evidence, not
proof -- but the order it replaces was never measured at all.

### The efficiency order: better locally, and the local test cannot settle it

Roster it actually fielded: Prism 22%, Heart of Ruin 22%, Marcella 22%, Vesper Vale 18%,
Vendetta 14%. No Willow, no Varg, no Cassi.

| metric | old | by pick rate | by efficiency | change vs old | widest band | ratio |
| --- | --- | --- | --- | --- | --- | --- |
| **gold earned** | 1,575 | 1,575 | **1,786** | **+210** | 93.0 | **2.3x** |
| gems submitted | 137.00 | 108.76 | 138.05 | +1.06 | 13.05 | **0.08x noise** |
| gems collected | 181.8 | 163.6 | 185.7 | +3.90 | 15.88 | 0.25x noise |
| deaths | 34.71 | 50.79 | 35.83 | +1.12 | 0.62 | 1.8x (worse) |
| **damage per gem** | 220.8 | 230.1 | 229.0 | **+8.13** | 14.02 | 0.58x (worse) |
| opponent gems | 947.7 | 942.4 | 936.7 | -10.97 | 8.52 | 1.3x |
| healing done | 2,495 | 1,828 | **0** | -2,495 | -- | Willow dropped |
| **wins** | **2 / 312** | 3 / 312 | **8 / 312** | | | |

Two things have to be said about this, and they pull against the headline.

**The premise did not transfer.** The whole point of ordering by efficiency was that these
champions show 71 to 108 damage per gem in top-three hands. In our hands damage per gem got
*worse*, 220.8 to 229.0. A champion-level statistic measured inside one bot's play does not
carry into another's -- the same lesson as the heal floor, which worked in the escort's
configuration and did nothing outside it.

**The wins are concentrated on the map we already know is a coin flip.** Six of the eight
are `01yellow-brick-road`, the map where a dead loop swung the score from 310 to 1,012 and
invented a win earlier today. The spread across opponents is genuine -- it beats all four
at least once, where the old order only ever beat `colleague` -- but 2 of 39 maps carry
every win, and one of them is the least trustworthy map in the pool.

**And the local draft is uncontested, which flatters this enormously.** All four local
opponents run the old order, so across 1,400 opponent champion-slots they took Prism,
Heart of Ruin and Vesper Vale **zero times**. On the ladder Heart of Ruin is first-picked
54% of the time. So this measurement says "these champions are better for our code when
nobody competes for them" and is silent on what we would actually get in a contested draft.

Applied to `sage2` anyway (`b2c9ff57eafbf7a4`), on two grounds that do not depend on the
local sweep: +210 gold is real at 2.3x even against the widest band, and ranking a champion
the top 20 take 2% of the time (`ryth`) fifth, and one they take 8% of the time (`varg`)
fourth, is indefensible however it measures. The honest position is that the draft is now
*less wrong*, and that only ladder games can price it.

### What is left, in order of measured size

1. **Deaths: 35 against their 6.** Unchanged by everything tried today. Their champions die
   0.6 to 2.4 times a game; every one of ours dies 7 to 8 times.
2. **Damage per gem: 229 against their 106.** Clear time helped a little and the draft made
   it marginally worse. The remaining scoring terms -- half-cleared camps priced at full
   health, `RewardAvailable` not treated as free, Varg splash, phase-weighted gold, exact
   path distances -- are all still unported.
3. **Kills 0.35 against their 9, assists 1 against 17**, while taking the *same* champion
   damage they do. We absorb a normal amount of fighting and get nothing back.
4. **They finish in 1,087 rounds; we run to 1,800.** Even when we are not losing we are not
   closing.

## Submitted to the ladder: 0-15, and what that actually taught

Bundled sage2 (14 files, 41 KB) and submitted it as version 17 at 13:18:03, queued three
unranked groups of five against `PrepaForTheWeak` (rank 158), `cheesynachos` (rank 156) and
`Intercontinental Fish` (rank 1), then restored `greatsage` as version 18 at 13:18:55.

The restore copy was verified identical before any of this -- `greatsage.zip` and a fresh
bundle of `bots/greatsage` fingerprint the same (14 files, 61,389 bytes,
`3d8df797e9b81713ff71`). **Exposure window 52 seconds, and no ranked match ran inside it** -- but the margin was far
thinner than first stated. `finishedAt` is UTC and the submission clock was local, which I
initially misread as an hour of slack. Converted properly: the window was 12:18:03 to
12:18:55 UTC, the preceding ranked batch finished at **12:11** and the next at **12:21** --
seven minutes before and two minutes after. Ranked batches fire automatically every ten
minutes or so, so this was a near miss rather than a safe procedure. The right order would
have been to queue the unranked groups against a submission that was never going to be
ranked, if the platform allows it; failing that, the restore should be scripted to run in
the same command as the submit.

Outcome: rating 1681.9 before, **1681.8 after**, rank 157 -> 158 across six further ranked
matches, all played by the restored `greatsage`. No damage.

### Result: 0-15, every loss on the gem threshold

| opponent | mean our gems | their gems |
| --- | --- | --- |
| `Intercontinental Fish` (rank 1) | 156 | 1,028 |
| `cheesynachos` (rank 156) | 444 | 1,017 |
| `PrepaForTheWeak` (rank 158) | 514 | 1,006 |

Closest: **981-1000 on `00lanes`, nineteen gems short**, and 886-1006 on `01islands`.

### The local benchmark is measuring the wrong thing

Same build, same five maps, local bots against real ladder teams:

| | local (n=40) | ladder (n=15) |
| --- | --- | --- |
| our gems submitted | 472 | 371 |
| our gems collected | 534 | 405 |
| our deaths | 22.8 | 15.3 |
| opponent gems | 919 | **1,024** |
| record | **8-32** | **0-15** |

Our own numbers barely move -- gems 472 against 371, and we actually *die less* against real
opponents. What changes is the opponent: 919 gems locally against 1,024 on the ladder, and
a record of 8-32 becoming 0-15. **`greatsage`, `base`, `colleague` and `boss_focus` are
weaker than the teams sitting either side of us on the ladder**, and every local measurement
in this document has been taken against them. A change that looks like it buys a win locally
may buy nothing against a team that reaches 1,000 gems a hundred gems sooner.

Note also that against a rank-158 team we average 514 gems and lose by 19 on our best map,
while against rank 1 we average 156. The gradient is steep and we are much closer to our
own neighbours than the 6x local gap suggested.

### Draft mechanics, now established from the roster rather than guessed

The draft **alternates and the pool is not exclusive**: our picks land at draft positions
0, 2, 4, 6, 8 and the opponent's at 1, 3, 5, 7, 9, and in that match both teams fielded
Heart of Ruin, Vesper Vale and Marcella. We got exactly our stated top five every game, in
all fifteen.

So the caveat raised earlier -- that local drafts are "uncontested" and therefore flatter
the efficiency order -- **was wrong**. We always get our preference order, locally and on
the ladder. What differs between the two is the *opponent's* roster, not ours.

### What still stands from the top-3 analysis

The per-champion and aggregate comparisons used `roster`/`champions[].name` from downloaded
summaries, which is the authoritative field, so those survive: Prism at 469 gems a game,
Cassi at 278 damage per gem, the top three never fielding Willow, their healing done of
exactly zero, deaths of 6 against our 35, and damage per gem of 106 against our 221. The
efficiency draft order was built on that data and it is the order now in `sage2`.

## `ladderbench.py`: the ladder as the benchmark

The local opponent set cannot price a change -- same build, same maps, 8-32 locally
against 0-15 on the ladder -- so measurement moved to real teams. Unranked groups play
the team's *current* submission, and ranked batches fire automatically, so this needs a
procedure rather than a command.

**Cadence, measured first.** 183 observed batches: gaps of 8 to 12 minutes, median 10,
five matches each, landing near :00/:10/:20/:30 with about two minutes of jitter.

**Four guards**, all exercised:

1. *The window.* Refuses to start unless a batch landed recently enough to leave three
   minutes of margin against the eight-minute floor. `--wait` sleeps for the next gap.
   It refused on its first invocation -- 7.9 minutes since the last batch, 0.1 of margin --
   which is almost exactly the gap the earlier manual submission landed in.
2. *The restore copy.* Bundles `bots/greatsage` fresh and fingerprints it against
   `greatsage.zip` before anything is submitted; refuses on mismatch. Verified by pointing
   the reference at `sage2.zip` and confirming the refusal.
3. *The restore itself.* Submit, queue and wait sit in a `try` with the restore in a
   `finally`. This fired for real: a 429 on the third queued group threw, and greatsage went
   back anyway.
4. *The audit.* Snapshots ranked batch times either side and says loudly if one landed
   inside the window.

**Four flaws the first run exposed, all fixed:**

- A 429 aborted the run with the test bot live and results half-collected. Now retried with
  backoff; it retried twice on the next run and succeeded.
- `--opponents 158,156,1` resolved to *different teams* an hour later -- rank 158 was
  `PrepaForTheWeak`, then `Team M^2FC`. Ranks drift, so comparisons by rank silently change
  the comparison. Added `--same-as TAG`, which pins a previous run's exact team ids.
- **Match groups snapshot the submission when queued, not when run.** Established from the
  failed run: ten games that played *after* greatsage was restored still returned 19.4
  deaths a game against greatsage's ~6. So the restore now happens immediately after
  queuing and the wait sits outside the window -- which cut it from 52 seconds to **25**.
- The CLI refuses to overwrite a bundle path, so the probe bundle is unlinked first.

### The draft order, re-decided on real opponents

15 games each, identical opponents, maps and sides:

| metric | old order | efficiency order | change |
| --- | --- | --- | --- |
| gems submitted | 394.9 | 371.3 | **-23.6** |
| gems collected | 427.8 | 405.1 | -22.7 |
| gold earned | 2,713.7 | 3,020.5 | **+306.7** |
| deaths | 16.5 | 15.3 | -1.3 |
| damage per gem | 160 | 176 | +16 (worse) |
| record | **1-14** | 0-15 | |
| per-game gems | -- | -- | **7 better, 7 worse, 1 same** |

**The local result did not replicate.** Locally the efficiency order looked clearly better
(+210 gold, 8 wins against 2); on real opponents it is a dead heat on the per-game record
and slightly *down* on gems. Only the gold gain reproduced (+307 against +210).

**Reverted.** `sage2` is back to the old draft order (`c3c8f3a2e4ee6511`). The reasoning is
not that the efficiency order is worse -- 7/7/1 across fifteen games establishes nothing
either way -- but that its justification is gone. The pick-rate half was computed from a
field that does not identify champions, and the per-champion half demonstrably did not
transfer: damage per gem got worse in both measurements, 220->229 locally and 160->176 on
the ladder. An unproven change resting on a broken rationale should not stand.

### The rating, audited rather than assumed

Rating went 1681.9 to 1662.2 and rank 157 to 179 across eight ranked matches during this
work, which looks alarming and is not caused by it. Every ranked match today was checked
against the three submission windows by creation time: **zero fell inside one.** The
12:40:11 batch, five straight losses, was created 24 seconds before the second submission.
greatsage is simply running at 12W-18L over its last 30 ranked games, against 19W-21L over
the 40 before that.

### What this harness still lacks

**A noise band.** Every local conclusion in this document is qualified by a
decision-identical twin, and the ladder harness has no equivalent: 15 games against three
opponents gives no idea how much a result moves for reasons unrelated to the change. The
next thing to run is the *same* bot twice under different tags and compare -- the ladder
version of the dead-loop probe. Until that exists, a 24-gem difference over 15 games means
nothing, including the one reported just above.

## The ladder band is 9.2 gems over 15 games, and that settles several things

The local harness needed 624 games and a decision-identical twin to reach a band of
+-13 gems. The ladder harness was being treated the same way -- 15 games assumed too
few to resolve anything -- which was wrong, and the test that shows it should have
been the first one run.

The engine is deterministic. If the opponents have not changed their submissions
between two runs, the *same* bot on the *same* pairings must return the same result.
Running `greatsage` twice against identical opponents, maps and sides:

| | gs_base | gs_repeat | change |
| --- | --- | --- | --- |
| gems submitted | 296.1 | 305.3 | +9.2 |
| record | 3-12 | 3-12 | -- |
| per-game gems | -- | -- | **1 better, 0 worse, 14 same** |

**Fourteen of fifteen games reproduced byte-identically.** The one that moved is almost
certainly an opponent updating their bot between runs, which is the only genuine source
of ladder noise there is. So the band is 9.2 gems over 15 games -- against real
opponents, for a fortieth of the games the local harness needs.

Sized against it, today's ladder results:

| result | change | ratio | verdict |
| --- | --- | --- | --- |
| champion pressure, maps we lose | +103.7 | **11.3x** | real |
| champion pressure, maps we win | +41.5 | **4.5x** | real |
| champion pressure, gold | +712 / +1,169 | 77x / 127x | real |
| efficiency draft order (reverted) | -23.6 | **2.6x** | real, and really worse |

Two conclusions follow, and one of them is a correction.

**The champion-pressure fix is established**, not promising. It is 11.3x the band on the
maps we lose and 4.5x on the maps we win, and it reproduces across two independent map
sets. The per-game split I was reading as a coin flip -- 14 better, 13 worse, 3 same
across both sets -- is nothing of the kind once the band is near zero: those small
per-game losses are *real* losses, and the large gains are real gains. It is a genuine
trade that nets strongly positive, not noise.

**The draft-order revert was right, and for the right reason after all.** I reverted it
saying "7 better, 7 worse establishes nothing either way". At 2.6x the band, -23.6 gems
was a real regression. The revert stands on evidence rather than on the broken rationale
I justified it with at the time.

**And the prediction I staked the champion-pressure test on was wrong.** I wrote before
the run: *"The mechanism metric is deaths. If deaths don't move, the fix does nothing and
the diagnosis was wrong, whatever the gems do."* Deaths moved 1.0 and 1.5 -- about 5%.
Gems moved 35% and 8%. So the fix works, and not by the mechanism I diagnosed: raising
the withdrawal threshold near enemy champions does not stop us dying, it stops us
*spending time* in fights we lose. Collected rose by almost exactly what submitted rose
(+103.9 against +103.7), and the opponent scored 76 fewer. We farm instead of brawling.
The diagnosis was wrong and the fix is right, which is worth recording as its own kind
of result.

## RETRACTION: the champion-pressure fix is not established, and the per-map table was built on noise

Earlier today this document recorded the champion-pressure fix as "established, not
promising", at 11.3x the measured band. That was wrong, and the error is worth setting
out because it is the same one the rest of the document warns about.

**The ladder band of 9.2 gems was measured against one fixed opponent set, minutes
apart.** It says how much a result moves when nothing changes. It says nothing about how
much a result moves when the *opponents* change -- and opponents on the ladder drift
constantly. Rank 143 was `Crimson Altar Keepers` in the afternoon and
`Howrah River Trading` in the evening; rank 154 went from `Mu&Hoon` to `Gilded Recallers`.

Re-run on a fresh opponent set, with per-map dispatch applied exactly as the table
prescribed:

| | never | selective | always |
| --- | --- | --- | --- |
| gems submitted | **494.3** | 380.1 | 384.3 |
| change | -- | **-114.2** | **-109.9** |
| per-game gems | -- | 3 better, 9 worse, 3 same | 2 better, 11 worse, 2 same |
| record | **5-10** | 4-11 | 4-11 |

Both arms are worse than doing nothing. Breaking the earlier result down by opponent
shows why:

| map | afternoon opponents | evening opponents |
| --- | --- | --- |
| 00swirl | Mu&Hoon **+795**, Crimson -8 | Howrah +16, Gilded **-7xx** |
| 01elk_arena | Mu&Hoon **+504**, Crimson +216 | Howrah -72, Gilded -1xx |
| 01islands | Crimson +109, Mu&Hoon +61 | Howrah **-161** |

**The +246 on 00swirl was one game against one opponent, averaged over three.** The
effect is opponent-dependent, not map-dependent, and the between-opponent variance
swamps everything else measured today.

What this does and does not invalidate:

- **The per-map dispatch machinery stands.** It is verified byte-identical to the old bot
  where no override applies and exact where one does. The mechanism is sound; the table
  it was filled with is not.
- **The champion-pressure fix must not ship.** +103.7 against one opponent set and -109.9
  against another is not an improvement, it is a coin weighted by who we draw.
- **The 9.2-gem band is still correct for what it measures** -- same bot, same opponents --
  and still useless for comparing across sessions. Any comparison must use `--same-as` to
  pin opponents, and even then it only speaks about those opponents.
- **Three games per map is not a measurement.** A ladder group gives three games per map
  per opponent; a single outlier dominates the mean. Per-map claims need either many more
  opponents or a per-opponent breakdown shown alongside the mean, which the harness now
  prints and I should have read before building a table.

The honest state of the live bot is therefore unchanged from this morning: `greatsage` as
it was, no champion pressure, no per-map overrides. Its rating slide is its own form, and
nothing measured today has earned the right to alter it.

## The unranked quota is 50 matches an hour, and it explains a null result

`cambc match-groups quota` prints the map list rather than any quota, so the
ceiling had to be discovered by hitting it:

    Your team can start 50 unranked matches an hour. (HTTP 429)

Ten groups an hour. A two-arm comparison across eight opponents is eighty matches,
so it takes about an hour and a half of wall clock rather than one sitting. The
harness now refuses to start a run that exceeds the limit instead of failing
halfway with the test bot live.

### A null result that was a rig fault

Three arms -- early gold weight 1.2, 0.3 and 0.0 -- came back identical on every
metric across forty games each. Different bundles (`3d8df797`, `1db13d3c`,
`a9e594de`), different submission versions, zero shared match ids, different
groups. The edit is real and reaches the score that picks targets:
`score = (travel + clear + capture + risk) * 100 / value`.

Identical results from different bots on a deterministic engine means the bots
were not different *in play*: all three arms played whatever was already live. A
submission is not necessarily active the moment the call returns, and groups
snapshot the submission when queued. A 25-second settle wait after submitting is
now in place, and the safety margin widened to four minutes to cover it.

**The retest could not complete** -- it queued three of eight groups and hit the
hourly limit -- so the gold-weighting question is still open. Fifteen games played
and are stored, but their summaries cannot be downloaded until the limit clears.

The rule this changes: **an identical result is now a red flag for the rig, not
evidence of a null effect.** Every arm that came back suspiciously close to its
baseline needs re-checking rather than believing.

What is not in doubt: `gs_fix` at +103.7 and `wide_fix` at +29.3 had live
submissions, because identical bots cannot produce different results here. The
eight-opponent champion-pressure matrix stands, including that 00swirl is -136
with zero of eight opponents positive where three games had read +246.

## Every gold-weight result today is void: the variants never compiled

The three gold-weight bots were created by replacing this line in `strategy.py`:

        value = objective.gems + objective.gold * (1.2 if now < 500 else 0.25)

It sits eight spaces deep inside a loop. The replacement used four. All three
variants have been syntactically broken since the moment they were created, and
every measurement taken from them is void.

**The platform rejects a submission that fails to build and keeps the previous one
active.** That single fact explains a chain of results that looked like platform
faults and were all this one bug:

- three arms returning byte-identical metrics across forty games each, with
  different bundles and different match ids -- all three played whatever was
  already live;
- the "submission propagation delay" diagnosed from it, and the 25-second settle
  wait added to fix it, which fixed nothing;
- the "matches resolve at execution, not queue time" conclusion drawn from eleven
  of fifteen games being bit-identical, which reversed an earlier conclusion drawn
  from one observation -- both were readings of the same broken-bot artefact;
- gold 0.0 and gold 0.3 playing five of five games bit-identically.

The four games that *did* differ -- the Latent Tactics group in one run -- were
played by `gs_gold000` while it happened to be the last valid submission, which is
the only reason any difference appeared at all. Even those are not a clean test of
weight 0.0, because nothing verified which bot produced them.

No ranked damage: 22-18 across the forty ranked matches in the window, rating
1659, no wipeouts. The broken bots were never active, by construction.

### Two guards, because this class of fault has now cost most of a session

1. **`ladderbench.py` parses every Python source before it submits anything** and
   refuses to upload a bot that does not compile. A broken submission is worse
   than a failed one: it silently measures the previous bot.
2. **Every bot prints an identity tag on its first turn**, `BOTTAG <name>`, which
   lands in the replay's stdout. Verified end to end: a local game now shows
   `BOTTAG gs_gold030` for team A. A run can be checked against the games it
   actually played rather than the submission it believes it made.

The gold-weight question is therefore completely open again, with zero valid games
behind it, and the earlier claim that zeroing gold "looks clearly harmful" is
withdrawn along with everything else from those runs.

## Diagnosis from event logs, and a candidate that failed its own test

### What the event logs say (390 matches, independent of any change)

Match summaries carry a per-champion event log -- deaths with the killer's context
and position, gem collections, submissions, losses, camp clears, purchases, fuel
exhaustion. Final gem totals cannot tell a bot that farms badly from one that
farms well and dies carrying the proceeds. The log can. `diagnose.py` reads it.

| per game | |
| --- | --- |
| gems collected | 427 |
| gems submitted | 367 (**86% of collected**) |
| gems lost to deaths | 43 (10%) |
| deaths | 25.2 -- **90% to enemy champions**, 10% to camps |
| deaths while carrying gems | **8%** |
| kills | about 1 |
| `fuelExhausted` | 13.3, in 336 of 390 matches |

Two long-held beliefs in this document are wrong. **Banking is finished**: 86% of
collected gems reach an altar, against the top three's 71%. And camps are not what
kills us -- enemy champions are, evenly across the game, and 92% of those deaths
happen while carrying nothing, so the cost is time rather than gems.

### The code defect

`combat.choose_enemy` accepts a target if any of these hold:

    killable or interrupt or defending or gap <= 4 or allied_power > enemy_power * 1.15

`gap <= 4` is unconditional: proximity overrides the power comparison entirely, and
the caller then *walks toward* the target to get in range. The power test only
applies beyond four tiles. That is the 22.6-deaths-for-1-kill machine.

### The candidate and its result

`gs_nochase` keeps swinging at anything already in reach, which is free, but only
closes distance when the exchange is ours -- killable this turn, interrupting a
deposit, or power ratio above 1.15, the test the code already uses past four tiles.

Ladder, 20 games each, identical opponents, maps and sides, both arms carrying an
identical `BOTTAG` so the tag is a constant rather than a confound:

| per game | baseline | no-chase | change |
| --- | --- | --- | --- |
| deaths to champions | 22.9 | **20.1** | **-2.8** |
| deaths total | 26.4 | **22.1** | **-4.3** |
| camp clears | 41.1 | 44.7 | +3.6 |
| gem pickups | 48.0 | 50.1 | +2.1 |
| gems collected | 442 | 449 | +7 |
| **gems submitted** | **372** | **365** | **-7** |
| gems lost to deaths | 57 | 64 | +7 |
| record | 4-16 | 3-17 | |
| per-game gems | -- | -- | 7 better, 10 worse, 3 same |

**The mechanism worked and the change failed.** Deaths fell 16%, champion deaths
12%, and the freed time did turn into farming -- camp clears and pickups both rose.
It bought seven more gems collected and seven fewer submitted.

Pre-registered rule, fixed before the data: ship only if gems improve, the sign
holds for at least three of four opponents, and deaths do not rise. Gems did not
improve and the sign held for one or two of four on every map. **Not shipped. The
baseline stands.**

### What the failure establishes

Dividing through: 4.3 avoided deaths bought 7 gems collected, about **1.6 gems per
death**. The wins-versus-losses comparison that motivated the work -- wins at 14
deaths and 1,023 collected, losses at 27 and 312 -- implies 55 gems per death.
**The causal effect is roughly thirty times smaller than the correlation.**

That comparison was correlational and I treated it as causal. Winning teams die
less *and* collect more because both follow from winning; cutting deaths does not
run the relationship backwards. Deaths are mostly a symptom.

So the real question is not why we die but why we collect 442 where the top three
collect 1,158, and the answer is not death time: removing a sixth of our deaths
moved collection by 1.6%.

### Caveat on this run

The candidate arm's polling loop exhausted its retries on HTTP 429 and restored the
ranked bot while its matches may still have been playing. The `BOTTAG` audit could
not run -- replay downloads were rate-limited throughout -- so which bot played
each match is unconfirmed. The arms clearly differ (deaths -4.3, distinct per-map
values), so the candidate did play, but partial contamination cannot be excluded.
The result is reported as a failed validation rather than a measured regression,
and nothing was shipped on the strength of it either way.

## The gold weight is closed out: the held-out test fails and the selection set never ran

The held-out confirmation of gold weight 0.3 played on ranks 25 and 240, neither of
which took part in selection. Ten games; one of the ten was bit-identical between
the arms, so nine carry information. On those nine: gems 370 to 336, deaths +1.2,
record 2-7 either way. Three games better, three worse, three unchanged. A 20,000
sample bootstrap over games puts the interval at -122 to +21, which includes zero,
and a single game -- `01yellow_brick_road` against Nanyang, 483 down to 122 --
accounts for more than the whole mean.

A sweep for bit-identical arms across every tag on disk then found something worse.
`gold_base`, `gold_030` and `gold_000` are mutually bit-identical across all forty
shared games, all three pairings. Those eighty matches tested nothing; they are the
builds that failed to compile, already voided above, and this is the independent
confirmation of it. The only real positive the parameter ever had was a cross-run
pairing of `gw_030` against `nc_base`: +142 over seventeen diverged games, but
assembled from two separate runs against the four opponents that selection used.

So the position is: one positive measurement against the selection opponents,
collected across runs, and one negative measurement against held-out opponents.
Nothing is shipped. The parameter is left at 1.2 and closed, because a 20-gem
question cannot be settled inside a 400-gem per-game variance without spending far
more of the 50-an-hour quota than it is worth.

## Where the collection gap actually is: 470 ladder games, by map and side

Aggregating every ladder summary on disk by (map, side) rather than by opponent
turns the gap from a single number into a structure:

    map                     sd games ourcoll theircoll  ourdeaths  theirdeaths
    00stampede               a    25     116       635       27.3         21.1
    00quadrants              a     6     174      1103       18.0          3.5
    00swirl                  b    48     252      1065       42.9         12.5
    01elk_arena              a    82     253       986       51.2         16.0
    ...
    00quadrants              b    48     912       990        7.6          4.6
    00collision              a     6     860       685        9.0         10.0

The opponents collect between 685 and 1,103 on every map in the pool. Ours runs
from 116 to 860. The maps are uniformly rich and the whole variance is ours.
`00quadrants` settles the question on its own: 174 on side a against 912 on side b,
same map, same bot, same opponents.

Splitting the four worst map-sides from the four best, 161 games against 97:

    deposits per game          3.2 against 19.8
    camp clears per game      81.8 against 32.3
    gem pickups per game      96.9 against 35.5
    gems collected             231 against  818
    deaths per game           44.8 against   7.2   (97% by champion)

We clear two and a half times as many camps for three and a half times fewer gems:
2.8 gems a clear against 25. That reads as a camp-selection failure, and it is not.
Per champion on the failing map-sides, ours each die 9.2 to 9.8 times and theirs
each 2.6 to 3.5 -- flat across all five on both teams, so neither side is
specialising roles. What separates them is output: they deal 2.1 times our total
damage and 2.9 times our damage to camps. They are simply stronger, and they clear
the same camps faster and survive doing it.

## The shop could never buy two of the seven item families

Gold, over all 470 games: we earn 4,535 and spend 94% of it; they earn 9,964 and
spend 95%. Purchase timing is indistinguishable -- median round 738 against 740.
Our discipline is fine. We do not have the gold.

Holdings tell the rest. We hold 0.00 of every Bruiser item and 0.00 of every
Treasure item, across all six variants of each, in 470 games. They hold 2.19
Bruiser Emblems of Health alone. `config.BUILDS` is three hardcoded shards, and
once `purchase_index // 5` runs off the end of that tuple the shop buys
`POWER_SHARD_OF_HEALTH` or `POWER_SHARD_OF_STRENGTH` forever. Bruiser and Treasure
were unreachable by construction, not by judgement.

Dumping the engine's own item table from inside a match -- `ItemType.info()` for
all 210 entries, recovered from `team-a.stdout` inside the replay bundle, since
`run-batch` does not surface bot stdout -- gives the design data, and the C++
header documents each passive:

    emblem (all 150 gold)   stats  passive
    POWER                       6  none
    BRUISER                     7  none            (5 primary, 1 of each other)
    TREASURE                    5  +20% gold gained
    JUNGLE                      5  30% less damage from camps
    DURABILITY                  5  10% less incoming damage
    MONSTER                     5  +10% damage to camps
    HOME                        5  recall in 3 turn ends instead of 5

Two things follow immediately. Every 150 gold the shop spent after its third emblem
bought six stat points where Bruiser buys seven, for the same price, giving up a
passive that Power does not have either. And Treasure, the only item in the game
that compounds, was unreachable -- while the measured deficit was income.

## Treasure first: +54% gold, and the mechanism is visible end to end

Four variants, each built from pristine greatsage, parsed before use and tagged so
a replay proves which arm ran. 24 local games each, eight maps against three
opponents, against a tagged-but-otherwise-pristine baseline:

    arm             gems  collect   gold  deaths  camp dmg   differ  delta
    gs_shopbase      515      584   5979    24.7     73611        -      +0
    gs_bruiser       542      637   6203    24.9     76894    16/24     +27
    gs_treasure      675      745   9213    16.1     93323    21/24    +160
    gs_shop          643      715   9102    15.0     87940    21/24    +128
    gs_shop5         618      712   8961    19.7     90578    21/24    +103

Treasure alone is the win, and every link of the predicted chain shows up as a
direct count: gold +54%, camp damage +27%, deaths 24.7 to 16.1, collection +161,
gems +160. The +54% is larger than one +20% emblem can explain, which is the
compounding -- more gold buys more Treasure across the roster, which buys more
gold. Gold lands at 9,213, against the 9,964 the ladder's stronger teams earn.

Bruiser on its own is +27 over sixteen diverged games, inside what this harness
swings on a neutral change, and adding it on top of Treasure costs 32 gems rather
than gaining. Adding all five passive families costs another 25. Neither is taken.
Only the one-line build-order change goes forward, and only to the ladder test,
because local opponents cannot reach 1,000 gems and this harness has bought a
local win that meant nothing before.

## Treasure on the ladder: the mechanism holds, the outcome does not move

Twenty games on ranks 25, 60, 120 and 240, fourteen of them diverged:

    metric              tr_base   tr_gold   change
    gold earned            3941      4523     +581   (+15%)
    gems collected          339       370      +32
    gems submitted          306       309       +3
    deaths                 26.6      28.9     +2.3
    record                 4-16      3-17

The predicted mechanism is confirmed -- more gold, more collection -- but at a
third of the local size, and none of it reaches the score. Locally the extra gold
compounded unopposed for 2,000 rounds; on the ladder the opponent reaches 1,000 by
round 1,177 and we are being out-collected 370 to 940, so a stronger champion
arrives at a game that is already lost. Not shipped: a flat gem delta with deaths
up is not a reason to change the live bot, however sound the mechanism.

## The other hardcoded table: the draft

Applying the same test -- a count that is zero for us and large for them -- to
the roster, over 470 games:

    champion        ours  theirs
    Vesper Vale       3%     71%
    Heart of Ruin     3%     70%
    Tavi / Issac      0%    ~31%
    Willow           97%     12%

`roster.DRAFT_ORDER` ranks Vesper Vale eighth and Heart of Ruin twelfth of twelve.
Both teams can field the same champion (Ryth: 75% ours, 70% theirs), so the
field's rates are its own preference and not what our picks left over.

The design data, dumped from `Champion.design()` inside a match, explains it.
Willow and Vesper Vale share strength 55 and range 3, but Vesper Vale has 1,000
health against 700 and grows 100 health and 5 strength per shard against 50 and
3. Willow has the worst growth in the roster, so every item bought for her is
worth about half. Heart of Ruin is a shield-and-dash tank with strength 30.

Local screen, 24 games an arm against the tagged baseline:

    arm               roster change                    gems  deaths  record  delta
    gs_draft_vv       Willow -> Vesper Vale             685    20.3    15-9   +170
    gs_draft_field    the field's own top five          533    22.3    9-15    +18
    gs_draft_hor      Willow -> Heart of Ruin           473    23.2    5-19    -42
    gs_draft_both     Willow, Varg -> VV, HoR           229    27.6    2-22   -287

Only the single swap wins, and it wins on 19 diverged games by +215. Dropping Varg
is catastrophic because `strategy.dps` multiplies Varg's damage by the camp count
-- the bot's camp clearing is built around that splash -- so the field's roster is
not ours to copy wholesale. It goes to the ladder alone.

## Banking threshold: the ledger is clear, the local harness cannot see it

In the 34 ladder games where we submitted under 60 while collecting 80 or more,
the ledger balances to the gem: 127 collected, 99 lost to deaths, 1 carried, and
1.0 deposits in the whole game. Five champions collecting 127 reach about 25 each,
so `BANK_GEMS = 24` means each is killed just short of it, again and again.

Locally, lowering it shows nothing: 8, 12 and 16 diverge from the baseline in only
6 to 10 of 24 games, because local opponents do not apply the pressure that kills
a carrier, and 8 is worse in eight of ten. Stacked on the draft swap, 12 matches
the swap alone (+163 against +170). This is a ladder-only question and waits its
turn behind the draft.

The full local pool (320 games an arm, four opponents, both sides) agrees with
the ladder: gold +1,414 a game with a standard error of 235, gems +17.7 with a
standard error of 21. The 24-game screen's +160 was the eight-map selection --
chosen because they were our worst maps -- overstating the effect about ninefold.
The same eight maps produced the draft swap's +170, so that number is treated as
an upper bound until the full pool and the ladder report.

## The improvement plan, sized from 510 ladder games

### Where the remaining gap is

A linear model of earned gold over 1,020 team-games (R^2 = 0.90) prices a kill at
199 gold and 1,000 camp damage at 42. On that model the 5,500-gold gap splits
almost exactly in half:

    source          ours   theirs    gap
    kills           1474     4479   +3005
    camp damage     2462     5529   +3066
    passive         1559     1642     +84

Our 22.5 deaths a game hand the opponents about 4,480 gold: nearly half their
income is our own champions. Kill participation is the same on both sides (2.65
champions per kill on us, 2.84 on them), so we are not being ganged; we take and
lose far more fights. Gems lost to deaths are equal overall (44 against 42) and
gems per deposit are equal (34.7 against 32.8), so banking is not the general
problem -- the scoring gap is collection, 428 against 954, and collection is
strength and time alive.

### Phase 0 -- in flight: Willow -> Vesper Vale

Full local pool and a ladder test with a fresh baseline and a bit-identical
contamination check against `tr_base`. Ship if ladder gems rise and the check is
clean; otherwise drop it.

### Phase 1 -- stop paying for their economy (about 3,000 gold a game)

1. Diagnose first, free: classify each of our deaths by the local strength
   balance when the fight began (allied versus enemy champions in range, their
   health and stats), from replays and champion timelines. The question is
   whether we die in fights taken at a disadvantage, or in fights that start
   even and are lost.
2. Then candidates, one per ladder test:
   - `combat.choose_enemy` accepts any target within four tiles unconditionally
     (`gap <= 4`), whatever the power ratio.
   - Retreat pressure counts camps only; enemy champions contribute nothing.
   - Carriers disengage on the same rule as everyone else.
3. Primary metric: deaths and kill/death ratio on the ladder; gems secondary.
   The no-chase test cut deaths by 4.3 and still went 4-16 to 1-19, so the fix
   has to be power-aware, not blanket avoidance.

### Phase 2 -- clear faster (the other 3,000)

- Per-champion builds from growth stats, now that the design table is known
  (Vendetta strength growth 6; Vesper Vale's build is the untuned default).
- Emblem order: Monster (+10% camp damage) against Jungle (-30% camp damage
  taken) as the first purchase.
- Retest Treasure after Phases 0 and 1. Its gold (+15% ladder, +22% full pool)
  did not convert while we were losing fights; it may once we are not.
- The fifth draft slot: Ryth against Tavi or Issac.

### Phase 3 -- banking where it actually fails

Only the catastrophic subset (99 of 127 gems lost, one deposit a game) needs it.
Make the threshold conditional on visible enemy champions rather than lowering
`BANK_GEMS` globally. Ladder-only: local opponents do not apply the pressure.

### Phase 4 -- compute, the long track

Opponents exhaust their fuel 96 turns a game to our 14: they spend their budget
and we cannot, at about 1,600 Python operations a turn. C++ has roughly 12,000
times the arithmetic headroom, and the best use for it is exactly Phase 1's
decision -- simulating an engagement before taking it. Start once the Python
heuristics plateau, porting the validated greatsage decisions into sage2 first.

### Measurement rules

- Local gate: the full 320-game pool with standard errors. Never a hand-picked
  map screen; the eight-map screen overstated Treasure about ninefold.
- The ladder decides. A two-arm test of four opponents on five maps is 40 of
  the 50 unranked matches an hour, so about one decision an hour; local work runs
  in parallel with it.
- Every arm parses, is tagged, gets a bit-identical sweep, and runs against a
  fresh baseline or a contamination check.
- Judge each change first on the count it targets, then on gems.

### Closed, not to be reopened without new evidence

Gold weight 0.3, Bruiser fallback, Heart of Ruin, copying the field's roster
wholesale, a global `BANK_GEMS` cut.

## Full pool on the draft swap: real gold, gems inside the noise

320 games an arm: gold +1,008 a game (standard error 253), monster damage +6,791,
gems +13.6 (standard error 21), win rate +2.8 points (standard error 2.8), healing
done down 12,513 as Willow leaves. The eight-map +170 overstated this one as well.
The ladder test, already queued, decides it.

## Phase 1 diagnosis: what the fights we die in look like

`analysis/fights.py` rebuilds the fight behind each of the 15,225 kills in 510
ladder games from the per-round timelines (cumulative champion damage dealt and
taken, gems carried, gold spent) and the engine's killer-and-assisters record.
Allies engaged is an upper bound; enemies engaged is exact.

The shape of the fights is the same for both teams: about 60% of victims have no
engaged ally, about 63% are outnumbered, and each side opens roughly a third of
the fights it dies in. What differs is items. When we die, the enemies involved
average +548 gold a champion over us and 70% of our deaths come a full emblem or
more behind. When they die the edge is +60.

Every fight that ended in a death, put in our frame, gives the curve the engage
decision needs (it cannot see fights that ended with nobody dead):

    our item edge   fights a game   we took the kill
    <= -450              13.3              7%
    -450..-150            4.5             19%
    -150..+150            7.4             32%
    >= +150               4.7             68%

    fights we opened, by item edge and numbers        won    a game
    <= -450        outnumbered                          1%     2.6
    <= -450        equal                                4%     1.7
    -450..-150     outnumbered                          3%     1.0
    -150..+150     outnumbered                          8%     1.6
    -150..+150     equal                               43%     0.6
    -150..+150     outnumbering                        86%     0.9
    >= +150        equal                               94%     0.5

About 6.9 fights a game are ones we open at 8% odds or worse, and another 7.7 are
ones they open on us at those odds. Each is a death worth 199 gold to them.

The code produces exactly this, in three places:

1. `combat.choose_enemy` accepts any enemy within four tiles unconditionally --
   `gap <= 4` sits beside the power test as an alternative, so proximity bypasses
   it. The power measure itself (health times strength, so items included) is
   sound and would decline most of these fights if it were consulted.
2. `bot.py` sets `retreat_at` from health and awake camps only. Enemy champions
   pressing a fight never raise it, so a champion stays in a lost fight until 30%
   health, and with every champion moving at speed 1 it cannot get out from there.
   The median fight that kills us lasts six rounds.
3. `strategy.choose_group` penalises a camp near an enemy by at most +20, on a
   cost scale in the hundreds, whatever the number of enemies. Champions farm
   beside enemy groups and are caught.

The no-chase candidate addressed one slice of the first: it stopped champions
walking toward a target but kept the `gap <= 4` accept, so they still opened on
anything in reach, and it left retreat and farming untouched. That is why deaths
moved only 4.3.

### Candidates, one ladder test each, in order

- A. Disengage when the local fight is lost: count enemy champions in reach and
  the power ratio into the retreat decision, so a champion leaves an outnumbered
  fight while it still can, not at 30% health. It covers both halves -- fights
  we open and fights opened on us -- which is why it goes first.
- B. Remove the unconditional `gap <= 4` accept, so the existing power test
  governs every engagement except killable, interrupting or defending targets.
- C. Scale the farming penalty by enemy power near the camp rather than a flat
  +20.

Judged on deaths and kill/death ratio first. The threshold for A is calibrated
locally against the in-game power ratio before it goes to the ladder.

## Candidate A: disengage from lost fights, and its calibration

`analysis/mkdisengage.py` builds the rule from pristine greatsage. Each turn,
after the low-health retreat and before capture and combat, `combat.local_power`
compares our health-times-strength within five tiles (allies at 0.75, as in
`choose_enemy`) with the enemy champions'. Below `DISENGAGE_RATIO` the champion
takes a killing blow already in reach, if there is one, then withdraws along the
existing threat-aware `nav.retreat`, and stays out until the ratio recovers by
0.2. The same function, with the threshold at zero and a print, is the logger
`gs_fightlog`, so the calibration is against exactly the number the rule reads.

160 local games, every map against the four standard opponents, about 96,000
champion-turns with an enemy champion in reach, each matched to the event log
(`analysis/calibrate.py`; bot stdout sits NUL-padded inside the replay bundle):

    ratio        turns    died in 8   kill in 8
    < 0.25      10,990       45.6%        3.0%
    0.25-0.50    9,955       27.4%        3.7%
    0.50-0.75    8,844       13.1%        5.6%
    0.75-1.00    7,947        7.1%        6.4%
    1.00-1.25    6,342        4.7%        9.2%
    >= 3.00     27,128        1.4%       41.2%

Death overtakes the kill between 0.75 and 1.00 for a champion already in a
fight, near 1.25 on the first turn of an encounter, and near 0.75-1.00 for a
carrier. A fifth of all turns near an enemy are spent below 0.5. A death costs
more than a kill earns -- 199 gold to them, plus respawn and farming time -- but
leaving forgoes kills, so the threshold is bracketed at 0.50, 0.75 and 1.00 and
the full pool chooses.

### Full pool: 0.75 cuts deaths by a third and moves gems outside the noise

320 games an arm against the tagged baseline:

    threshold   deaths          kills   gold    gems           win rate
    0.50        -5.19 (0.58)    +3.33   +750    +41.9 (19.0)   +3.8 (2.8)
    0.75        -6.43 (0.56)    +4.17   +884    +47.7 (20.2)   +4.1 (2.8)
    1.00        -4.91 (0.61)    +2.17   +422     +7.5 (19.9)   -8.1 (2.8)

At 0.75 deaths fall from 19.5 to 13.1, eleven standard errors, and gems rise by
2.4 -- the first change in this project to move gems clearly outside the full
pool's noise rather than only the mechanism it targets. Kills rise with it, so it
is not mere avoidance: a champion that leaves a lost fight is alive for a won one,
and the finishing-blow check turns some exits into kills. Opponent gems fall 52.
At 1.00 the rule is too timid -- champions quit fights they would have won and
lose farming time standing off -- and win rate drops eight points.

0.75 goes to the ladder, built both on greatsage (`gs_dis075`) and on the draft
swap (`gs_vv_dis075`), so it can follow whichever base the draft test leaves.

## The draft swap on the ladder: flat, not shipped

Twenty games on identical pairings, a fresh tagged baseline against Willow ->
Vesper Vale:

    metric              dv_base    dv_vv    change
    gems submitted        289.3    285.9     -3.4
    gems collected        319.1    338.2    +19.1
    gold earned          3427.0   3555.7   +128.7
    deaths                 24.6     23.4     -1.3
    record                 1-19     2-18
    per-game gems: 9 better, 9 worse, 2 same

The same pattern as Treasure and as its own full pool: more gold and collection,
no gems. Not shipped; disengage is tested on greatsage.

The contamination check could not run, and the reason matters for every
cross-run comparison: `--opponents 25,240,60,120` resolves ranks to whoever holds
them at launch, and the ladder had moved between the Treasure run and this one --
the four teams were different. A comparison across runs must pin opponents by team
id with `--same-as`. The disengage test does, which also makes its fresh baseline
a free contamination check: same bot, same four teams, an hour apart, so it
should come out bit-identical to `dv_base`.

## Candidate A on the ladder: deaths fall a third, and so does the farming

Twenty games, four opponents pinned by id, both arms minutes apart:

    metric              da_base    da_dis    change
    deaths                 23.6      15.8      -7.8
    record                 1-19      3-17
    opponent gems         945.6     893.4     -52.2
    gems submitted        322.4     262.6     -59.8
    gold earned          3712.7    3033.3    -679.4
    per-game gems: 7 better, 11 worse, 2 same

The mechanism holds and is stronger than locally (deaths -7.8 against -6.4). The
cost is income. Against ladder opponents the local ratio falls below 0.75 far more
often than against the local bots, so champions spend much more of the game
walking away from camps, and our gems fall about as much as theirs do. Not
shipped: the criterion was deaths down and gems not down, and gems are down. Two
extra wins in twenty games is too small to outweigh that, and twenty games
resolves neither difference.

The contamination check: the fresh baseline matched `dv_base`, two hours older,
on 15 of 20 games; 5 differed, so at least one pinned opponent resubmitted in
between. Cross-run comparisons need a same-run baseline even when the teams are
pinned; the A comparison has one.

Next for A, cheapest first: 0.50 (nearly as good locally -- deaths -5.2, gems
+41.9 -- while leaving fights far less often); disengage only when outnumbered,
not merely outmatched; and stop the farming choice from walking a disengaged
champion straight back to the camp it left.

## CLOUD: where A's ladder gems went, and a map where greatsage never moves

### The A test was clean, and its gem loss is inside its own noise

All 40 games were downloaded and their replays' `BOTTAG` lines read
(`analysis/ladder_arms.py`): every `da_base` game was played by `gs_shopbase` and
every `da_dis` game by `gs_dis075`. Nothing was contaminated.

Paired by opponent and map, the 20 gem differences run from -683 to +648. Their
mean is -59.9 with a paired standard error of 61.5, so the result is one standard
error from zero: it does not show that A costs gems, and it does not show that it
doesn't. Seven games better, eleven worse, two the same. Not shipping it was the
right call under the agreed rule; the rule was set for a test that cannot
resolve a 60-gem effect in 20 games.

    per game            da_base    da_dis    change
    deaths                 23.6      15.8      -7.8
    rounds alive         4554.8    4985.0    +430.2
    monster damage        50975     39462    -11512
    camp clears            39.3      39.4      +0.1
    deposits                9.9       8.1      -1.8
    rounds taking champion damage  278.9  289.1  +10.2
    monster damage per round alive  11.19   7.92

The mechanism is visible in the counts. Champions live 430 rounds longer and
deal 23% less monster damage, 29% less per round alive. They are taking champion
damage on as many rounds as before. A converts deaths into time spent walking
away under fire, not into time farming.

By opponent, the whole mean is one team: against Hidden Altar Keepers gems went
442 -> 136 a game (two games, 01islands -683 and 00quadrants -478, carry most of
it). Against the other three it was 251 -> 251, 303 -> 314 and 294 -> 350, with
deaths down 7 to 12 a game every time; without Hidden Altar Keepers the mean is
+22.4 over 15 games.

### 01yellow_brick_road: greatsage spends every turn's fuel and never acts

Both arms scored 0 against Quantom on `01yellow_brick_road`, with 0 deaths and 0
monster damage: the whole team stood still for the whole game. Section 4 above
recorded the same thing locally on 21 Oct and left it unexplained.

Reproduced locally (greatsage against itself, `config.DEBUG = True`): neither
team prints a single state line, and the per-turn fuel log in the replay bundle
(`team-a.fuel`, little-endian uint64 after a 13-byte header) shows why. Every
champion uses the whole 5,000,000 of its first turn and 2,500,000 of its second,
and then about 2,275,000 every turn after -- exactly the budget less
`turn.MIN_FUEL`. The turn guard is raising `Replan` every turn, before any
action. The setup it keeps abandoning is only stored on completion (`metadata`,
`altar_field`, `crystal_needed`), so it restarts from nothing each turn and never
finishes. It is opponent-dependent on the ladder (483 and 474 gems on the same
map against two other teams), which fits a setup cost that sits right at the
budget.

The C++ port (`gs_cpp`, below) finishes the same setup inside its first few
turns and wins the map 1,010 to 404 against greatsage.

### gs_cpp: greatsage, ported to C++ line for line

`ws/bots/gs_cpp` translates every greatsage module -- bot, escort, boss, combat,
navigation, strategy, teamwork, progress, policy, draft, config, turn -- keeping
its iteration orders and tie-breaks (first minimum, stable sorts) and doing its
arithmetic in double. Every absolute fuel threshold is the Python one divided by
25, the language multiplier. First games:

    00ambush            gs_cpp 1019 - 644 greatsage   (gs_cpp side A)
    00ambush            greatsage 1005 - 628 gs_cpp   (gs_cpp side B)
    01yellow-brick-road gs_cpp 1010 - 404 greatsage

No `ERROR` lines in either team's log. The 80-game parity sweep against greatsage
(both sides, all 40 maps, against a greatsage self-play baseline) is running.

## Seelie's bot, now live: what is in it and what to take

The owner submitted Seelie's `py-t04-gem-value` as the live ranked bot at about
16:41Z. Website submissions are frozen otherwise, and `ladderbench.py` now
restores `ws/bots/seelie_live`, a byte-exact copy verified against its bundle.

It is greatsage with exactly two changes:

1. `strategy.choose_group`: early gold weight 0.3 instead of 1.2 -- the change
   tested and closed earlier here (+142 in one cross-run ladder comparison,
   -34 on the held-out one).
2. `navigation.retreat`: `turn.check()` inside the threat loops, a guard for a
   dead champion, and threatening camps located at their spawn tiles rather
   than their live positions.

The crash the second change prevents is real but rare. The engine pauses a bot
that runs out of fuel mid-statement and resumes it next round inside the old
call stack, so a comprehension can check `is_visible()` in one round and query
the unit in the next. `analysis/errors.py` counts the `ERROR` lines `main.py`
prints for each lost turn: greatsage loses 3 champion-turns in 320 local games,
all at the line Seelie fixed. So that part is worth keeping because it is
correct, not because it moves the score. The spawn-tile part does change
behaviour: a camp that is chasing a champion is no longer where the retreat
plan thinks it is.

First 68 head-to-head games against greatsage: win rate 60.3% against 50.0%
(paired se 8.7), gems +43 (se 52), inside the noise.

The same screens settled two more things:

- **Candidate B is dead.** Removing the `gap <= 4` accept costs 159 gems (se
  24) and 25 points of win rate, and raises deaths by 5.5. That line is how a
  champion fights back once an enemy is adjacent; the diagnosis that called
  it a defect was wrong about it. Every B combination fails the same way.
- **Restricting disengage to outnumbered fights** keeps half the death
  reduction and none of the gem gain (+7, se 21).

What goes forward is Seelie's bot plus disengage at 0.50
(`gs_seelie_dis050`, untagged as `seelie_dis050_submit`), racing Seelie's bot
on the full pool now.

## Version 93 is live: Seelie's bot plus disengage at 0.50

Submitted at 16:47Z at the owner's request, before the local race against
Seelie's bot had finished. Its tagged twin had played 40 clean local games
(no faults, no `ERROR` lines). The upload is `ws/bots/seelie_dis050_submit`,
bundled as `seelie_dis050_submit.zip`, and `ladderbench.py` restores exactly
that. The ladder evidence for disengage so far is from 0.75 on greatsage --
deaths -7.8, gems -59.8 -- so version 93's own ranked results are the real
test.

## CLOUD: gs_cpp passes parity, and two maps where greatsage can never score

### Parity: gs_cpp plays as greatsage does

80 games against greatsage, every map from both sides, paired against greatsage's
own 80 self-play games (`analysis/paired.py gs_vs_gs cpp_vs_gs`):

    per game            greatsage   gs_cpp   change   paired se
    gems submitted          674.1    711.5    +37.4       44.1
    win rate %               50.0     52.5     +2.5        8.0
    gems collected          790.5    854.9    +64.4       48.6
    deaths                   19.2     19.4     +0.2        1.7
    kills                    16.4     16.8     +0.4        1.6

Everything is inside its error, with a slight lean to the port, which does not
livelock on 01yellow-brick-road. Two of the 80 games are bit-identical between
the arms.

### 00contest and 00stampede: the only gems need the whole team

greatsage self-play scores 0-0 for 2,000 rounds on both maps, which §4 recorded
as unexplained. Neither is fuel (median use 95k and 615k of 2.5M). Dumping every
group's rewards from inside a match:

- **00contest**: 14 groups, and the only gems are two **monoliths** (200 gems,
  300 gold, 20,000 HP each). The other twelve are gold clusters. The map has two
  altars, so `policy.kind()` is 0, and `choose_group` skips monoliths outright.
- **00stampede**: 13 groups, and all 160 gems are in one group of 6 elks, 10 gem
  clusters and 4 gold clusters. The elks hit for 360 a turn together, so the
  solo `expected_damage > hp_budget` filter rejects the group for every champion.

`gs_cpp_party` adds one rule: if no gem-bearing group can be cleared alone (no
monolith, and at most one golem's strength, 120, in total), play the map with
the party controller (`BossBot`, policy 3), gating every *heavy* objective --
monolith or more than 120 strength -- behind its readiness test, not only
monoliths. Across all 40 pool maps the rule fires on exactly 00contest and
00stampede; 01boss-battle stays policy 2. On the other 37 maps gs_cpp_party is
gs_cpp.

On the two maps, both sides, against all four standard opponents (32 games):

    gs_cpp          9 wins of 16,  1,120 gems in total
    gs_cpp_party   13 wins of 16, 11,028 gems in total

The one weakness: on 00contest as side B, against greatsage, base and
boss_focus, the party scores 0 and loses the gold tiebreak. It farms small gold
camps one at a time as a group, the five solo opponents farm in parallel and
earn eight times the gold (19,200 to 2,380), and they run the party over (96
deaths). Farming solo until ready and regrouping only for the heavy objective
would fix it; not done, to avoid tuning to one side of one map.

### Tracking the live bot: gs_cpp93

Version 93 is Seelie's bot plus disengage at 0.50, so the C++ line now has
`gs_cpp93` (gs_cpp plus Seelie's gold weight 0.3, Seelie's retreat guard with
camps at their spawn tiles, and disengage at 0.50 with the melee-only finishing
blow) and `gs_cpp93_party` (plus the party rule). Its parity sweep against
`gs_seelie_dis050` is running.

### Version 93's evidence, as of 16:58Z

Local, full pool, 320 paired games against Seelie's bot: gems +57.9 (se 19.1),
win rate +6.9 (se 3.3), deaths -4.7 (se 0.66), kills +2.4, gold +675; positive
against all four opponents; 170 games better and 113 worse (sign test p =
0.001). Disengage gains more on Seelie's base than on greatsage's (+42).

Ladder, 20 unranked games (tag `v93_live`) against the four teams, maps and
sides of `db_base` (greatsage, 16:31Z): gems 289.3 -> 352.2 (+62.9), collected
+82.4, deaths 24.6 -> 18.0, opponent gems -24.3, record 1-19 both, 9 better and
8 worse. That is the reverse of disengage at 0.75 on greatsage (gems -59.8) at
the same death reduction, but at twenty games it is a lean, not a result.

Ranked: the first batch it played (16:50Z, against slayer) went 2-3. The
rating is 1,644, rank 212, against 1,630 and rank 228 at 16:00Z.

## CLOUD: gs_cpp93 against version 93, and "fight when you cannot shed it" fails

`gs_cpp93` (the C++ port with version 93's changes) against `gs_seelie_dis050`,
every map from both sides, paired against v93's own 80 self-play games:

    per game            v93   gs_cpp93   change   paired se
    gems submitted    690.1      759.9    +69.8        40.8
    gem margin          0.0      107.9   +107.9        65.5
    win rate %         50.0       55.0     +5.0         7.1
    deaths             16.6       14.8     -1.8         1.0
    gold earned      6131.8     6486.0   +354.3       324.9

At least parity, leaning positive on every count (z 1.6 to 1.8): the Python
fuel suspensions it no longer has are the likely source.

`gs_cpp93_shed` tested the rule the ladder counts seemed to ask for: disengage
only when walking away sheds the threat (no melee enemy within two tiles, or a
dash ready), and otherwise fight on. Against gs_cpp93 on the same 80 games:

    gems -95.9 (se 37.3), deaths +3.8 (se 1.0), kills -2.1 (se 0.9), gold -747

Clearly worse. Staying in a losing melee fight kills more champions than
walking away under fire does: chasers give up or are distracted, allies
arrive, the walk ends at safety. The "rounds taking damage" count was not
evidence that leaving is useless. Rejected.

The party rule against v93 on its two maps, both sides:

    00contest   A   gs_cpp93 0-0 L      gs_cpp93_party 200-0 W
    00contest   B   gs_cpp93 0-0 L      gs_cpp93_party 600-400 W
    00stampede  A   gs_cpp93 800-0 W    gs_cpp93_party 80-240 L
    00stampede  B   gs_cpp93 0-160 L    gs_cpp93_party 946-174 W

Three wins in four against one, and with the earlier 32 games a clear net
gain. `gs_cpp93_party` is CLOUD's ladder candidate, when the freeze lifts.

### 01elk_arena: one gem group, and party play does not help locally

On the ladder (A's 40 games) we die 38.6 times a game on 01elk_arena and 33.5
on 00swirl, nearly all to champions, and the deaths cluster at the map centre.
01elk_arena has exactly one gem-bearing group -- 2 elks and 6 gem clusters in
the middle, 72 gems a capture -- and 28 gold-only groups, so both teams fight
over one objective. Across the pool, only 00stampede (1), 01elk_arena (1) and
00contest (2) have two or fewer gem groups; the next is 01hooks with 4.

`gs_cpp93_party2` extended the party rule to maps with at most two gem groups,
which adds exactly 01elk_arena. On that map, both sides, against v93,
greatsage, base, colleague and boss_focus:

    gs_cpp93_party  (solo there)   10 wins of 10, 6,948 gems, 277 deaths
    gs_cpp93_party2 (party there)   5 wins of 10, 4,752 gems, 336 deaths

Rejected. The local opponents do not reproduce the ladder's slaughter on this
map -- the solo C++ bot wins all ten -- so 01elk_arena needs ladder-strength
opponents to study, which is the opponent set LOCAL is building.

## CLOUD: gs_cpp93_party against version 93 on the full pool

The standard 320-game pool (greatsage, base, colleague, boss_focus; 40 maps;
both sides), v93's tagged twin `gs_seelie_dis050` against `gs_cpp93_party`,
paired game for game (`analysis/paired.py v93_pool cpp93p_pool`):

    per game            v93   gs_cpp93_party   change   paired se
    gems submitted     783.5        823.0       +39.5        21.0
    gems collected     898.0        945.8       +47.7        22.0
    gem margin         196.6        214.5       +18.0        35.6
    win rate %          66.2         66.6        +0.3         3.5
    deaths              13.8         13.3        -0.5         0.7
    kills               19.3         17.2        -2.2         0.8
    gold earned       7037.0       6874.2      -162.7       202.8

Gems are up against every opponent (+14 to +68) and the win rate is level.
Kills are down by 2.2 a game, which is outside its error and unexplained: the
port changes no combat decision, so it is the timing of fuel suspensions that
differs (Python suspends; C++ almost never does). The gate -- no worse than the
live bot on the pool -- is passed. Next is a ladder test, when the owner lifts
the freeze.

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
   compared with ours (LOCAL is doing this).


## The #1 team, prism best girl (rating 2,253), against us

60 of their latest ranked games (38-22) against 40 of ours (version 93 and
greatsage ladder games), from `analysis/fetch_team.py`, `study_team.py` and
`study_space.py`. Summaries have no position track, so movement is rebuilt
from per-round timelines and positioned events. Bases are located by where each
team shops (its spawn), and every event is placed on the line between them: 0
at home, 1 at the enemy base.

**Draft.** Prism (first pick, every game), Vesper Vale 55/60, Marcella 52/60,
Heart of Ruin 51/60, then Ryth or Vendetta. We field Marcella, Vendetta,
Willow, Varg and Ryth, and never Prism.

**Emblems, in true purchase order** (the summary's `itemsBought` list is in
catalogue order, not purchase order):

    Vesper Vale    Jungle:Str > Bruiser:Str > Bruiser:Hp > Durability:Hp, then Bruiser (14.3 at the end)
    Prism          Durability:Hp > Monster:Focus > Jungle:Hp > Home or Bruiser:Hp (one of each passive, then Bruiser)
    Marcella       Bruiser only: Str > Hp > Focus ... (11.1 at the end)
    Heart of Ruin  Jungle:Focus > Bruiser:Hp > Durability:Hp > Bruiser:Focus
    Ryth           Jungle:Str > Bruiser:Hp > Durability:Hp > Power:Str
    Vendetta       Jungle:Str > Bruiser:Str > Bruiser:Hp > Durability:Hp
    ours (all)     Jungle:Str > Monster:Str > Durability:Hp > Power:Hp, then Power forever

Jungle first, Durability once, Bruiser thereafter, Monster only on the focus
caster, Treasure never, Power almost never. Gold is concentrated: Vesper Vale
ends with about 14 emblems.

**Time budget, % of champion-rounds:** farming camps 16.5 against our 6.5;
fighting champions 4.6 against 7.1; dead or walking back 2.1 against 6.1.
Neither team clears many more camps (about 45 a game each), so theirs take
longer to kill -- bigger, richer camps.

**Territory.** Their camp clears sit at depth 0.33-0.44 and push outward
through the game (0.32 early, 0.38 mid, 0.45 late). Ours stay at 0.11-0.21
all game. They bank at the central altar (depth about 0.49); we bank at the
home altar (0.02), which turns every deposit into a long walk home. Their
wards are at 0.44, ours at 0.12-0.17, and we place twice as many. Their kills
land in enemy territory (57-75% past halfway). They open on their first camp
around round 90-100; we start at round 16-60 on the nearest small camp.

**Banking in two tiers.** Vesper Vale and Marcella bank 5-6 times a game at
about 45 gems. Prism is the finisher: it carries a median peak of 196 gems and
makes its big deposit about one round before the game ends. Ours bank at about
30 gems, and Willow banks almost nothing (4% of the team's gems).

**Fights.** 7.1 deaths a game against our 21.3, 9.0 kills against 5.5, with
the same kill teamwork (2.7 champions per kill against 3.0). They kill gem
carriers about 4 times a game; we do so about 0.5 times.

**Why a low-health champion fights (the owner's question).** Willow, our
lowest-health champion at 700, runs `EscortBot`, which follows a teammate and
moves towards any ally under 70% health -- that is, towards the fight that hurt
them. Every champion then attacks any enemy within four tiles
(`choose_enemy`'s `gap <= 4`), and the only retreat trigger is 30% health (43%
carrying). Nothing in the bot puts farming ahead of fighting for a hurt
champion. Removing `gap <= 4` outright was measured and fails (-159 gems): it is
also how champions fight back. The fix has to be a health gate on *opening*
fights, not on returning fire.

### Fixes from the #1 analysis, first results

- **The health gate fails.** Retreating at 60% health whenever an enemy champion
  is within five tiles cost 108 gems (paired se 21.7) and 17.5 points of win
  rate over 246 games, and raised deaths by 2.3: a hurt champion that turns to
  leave is chased down. Not used.
- **v94 zip handed to the owner** at their request (`v94_untested.zip`,
  `ws/bots/v94_submit`): live v93 plus Willow farming and travel weight 0.6.
  Only a smoke game has been played; the full-pool screens of both changes
  were still queued. If it goes live, `ladderbench.py`'s restore target
  (`seelie_dis050_submit`) must be switched to `v94_submit`.

## The teammate's Priority Experimental, head to head; v94 withdrawn

The teammate's bot is greatsage plus a stale-vision replan in `main.py`, cached
camp design stats in `strategy.py` (cheaper camp scoring) and spawn-tile threats
in retreat. Played 40 maps from both sides against each of ours:

    teammate vs v93: maps won from both sides 9, split 13, lost from both 18;
                     gems -92 a game (se 81); deaths 21.2 vs 14.1; gold 5,720 vs 6,879
    teammate vs v94: maps won from both sides 11, split 21, lost from both 8;
                     gems -42 a game (se 63); deaths 20.3 vs 15.4

**v93 is the stronger bot.** Its fixes are orthogonal to disengage, though, and
are worth folding into v93.

**v94 is withdrawn.** Willow farming instead of escorting, measured on its own
against v93 over 200 games: gems -73.9 (paired se 28.1), win rate -14.5, 124
games worse and 63 better. Her own numbers (4% of banked gems) understate what
her heals are worth to the champions she follows. The travel-weight changes and
the safer escort were never screened (paused at 0/320); the health gate failed
earlier (-108).

## Version 95 is live

Uploaded at 19:53Z at the owner's request: v93 plus the teammate's stale-vision
replan (`main.py`) and cached camp design stats (`strategy.py`), copied
verbatim. It differs from v93 only in those two files, and `main.py` is
identical to the teammate's. Three smoke games were clean. It went up before its
head-to-heads against v93 and the teammate's bot and its full-pool run had
finished; those results go here when they land. `ladderbench.py` restores
`v95_submit`.

### Version 95's tests: it is worse than v93 on the full pool

    head to head vs v93, 40 maps x 2 sides:  40 of 80 games; maps won from both sides 5, lost 5;
                                            gems +18 (se 33); deaths 16.5 vs 16.7
    head to head vs teammate's bot:         maps 11 to 12; gems +86 (se 70); deaths 14.5 vs 20.7
    full pool, paired against v93 (320):    gems -48.3 (se 15.0), win rate -10.6 (se 2.4),
                                            kills -1.3; 108 games bit-identical;
                                            results flipped 14 to a win and 48 to a loss (p < 0.001)

The pool is the larger and cleaner test, and it says the two fixes cost v93
about 48 gems and ten points of win rate. A plausible cause is the cached camp
stats: cheaper scoring lets `choose_group` exactly score more camps before its
950,000-fuel cut-off, which can favour camps that only look better. The two
fixes should be tested apart before either is kept. The recommendation to the
owner is to put v93 (`seelie_dis050_submit.zip`) back live.

v93 went back live as version 96 at 20:02Z, at the owner's request; its folder
matched the 16:47Z upload byte for byte, and `ladderbench.py` restores it again.
The two fixes are now being screened apart (`gs93_replan`, `gs93_cache`).

### The two fixes apart: the cache is the culprit, the replan never fires

    alone on v93, 320 paired games   gems            win rate   unchanged games   flips win/loss
    cached camp stats                -63.9 (14.4)     -9.7        99               16 / 47
    stale-vision replan              -18.7 (5.6)      -2.5       248                5 / 13
    both (v95)                       -48.3 (15.0)    -10.6       108               14 / 48

The cached camp stats cost v93 about 64 gems and ten points of win rate: with
cheaper scoring, `choose_group` exactly scores more camps before its fuel
cut-off, and the extra candidates lead to worse picks. Not used.

The replan handler fired zero times in 320 games, and v93 loses no turns to the
error it catches. Its -18.7 can therefore only be fuel noise -- different code,
different fuel, 72 of 320 trajectories rerouted -- inside the +-22 gems a
decision-neutral change was measured to swing earlier. It is harmless but shows
no benefit, so v93 stays as it is. On the ladder, where fuel pressure may differ,
the replan could still matter; it can be revisited with ladder evidence.

## Monoliths: 35% of the gems on the maps, and we never farmed them

**Gems per clear.** Both teams clear about 41 camps a game, but #1 picks up
24.2 gems a clear and we picked up 8.9 on the ladder. We are not losing rewards
to the enemy -- 95% of what we clear we collect, like them -- but 72% of our
ladder pickups were worth zero gems, against #1's 27%. It is map-driven: on the
five ladder-test maps 68% of v93's local pickups are zero-gem, against 26% on
the other 35 maps, and #1 manages 17% on those same five.

**Camp table.** `analysis/camptable.py` reads every map's camp groups from
inside a match (`ws/bench/camptable.json`): 836 groups, 200 of them (24%) worth
no gems, 27 monoliths. Monolith groups hold **35% of all gems on the maps**
(6,946 of 20,016), at a mean of 257 gems, 361 gold and 24,086 health each,
against 16 gems and 2,242 health for an ordinary group. On `00contest` all the
gems are in monoliths; on `00rows`, `00monolith`, `01gold_rush` and
`01starvation` 75-80%. `strategy.choose_group` and `choose_cooperative` skip
monoliths outright.

**What #1 does.** 0.70 monolith clears a game for 167 gems a game -- 19% of its
camp gems, against our 21 (3%). Three or more champions are hitting camps in
the ten rounds before a monolith falls (median 3, often 4-5), and it happens
late: median round 993, quartiles 785-1,222.

**Candidate: the raid** (`gs93_raid700`, `gs93_raid900`). Monoliths become
eligible from a set round, are costed for one plus the allies already committed
plus two assumed to join (clear time and incoming damage shared), and a claimed
raid pulls teammates in instead of steering them off. It works mechanically --
monolith clears appear -- but the first smoke game on `00contest` collected all
three rewards (600 gems) and lost all 600 to deaths with no deposit: a lone
carrier with 200 gems walks to the altar and dies. #1's Prism carries a median
peak of 196 and dies 1.4 times a game, so their carrier is protected. Screening
on the full pool will say whether the raid pays on aggregate; if it fails, the
next version needs an escorted bank after the raid.

### Game constants, read from inside a match (`ws/bots/probe_consts`)

    CAPTURE_TIME 5   RESPAWN_TIME 60   RECALL_TIME 5   SPAWN_HEALING 1.0
    SUBMIT_GEM_DURATION_MULTIPLIER 0.1   SUBMIT_GEM_BASE_DURATION 0   MINIMUM 1   SUBMIT_GEMS_RANGE 1
    KILL_GOLD 100   ASSIST_GOLD 0   PASSIVE_GOLD 0   WINNING_GEMS 1000   MAX_ROUNDS 2000
    ACTIVE_WARDS 1   WARD_COOLDOWN 10   WARD_LIFETIME -1   WARD_VISION_RADIUS 6   ALTAR_LOCK_HITS 5

- **A deposit is a channel of 0.1 rounds per gem.** 24 gems is 2.4 rounds;
  a 200-gem monolith reward is 20 rounds standing within a tile of the altar.
  That is why bigger bank loads measured worse (36: -11, 48: -22) and why the
  raid's carriers die at the altar.
- **Respawn is 60 rounds**, so each death costs a champion 60 rounds; at 14-21
  deaths a game that is 15-20% of all champion time.
- **Spawn heals 100% of max health a round**, so a recall (5 rounds) is a
  full heal.
- A kill pays 100 gold plus everything the victim carried; assists pay
  nothing; there is no passive gold. One ward at a time.

### Safe-bank candidate and its bug

`safebank80`: a carrier of 80 or more gems far from every altar recalls home
(or backs off enemies within 6) before banking. The first version recalled in
a loop -- recall, step out of spawn, recall again -- and two carriers ended a
`00rows` game holding 952 gems. Restricting it to "more than 8 tiles from every
altar" removed the loop, but on maps whose altars are all mid-map (no home
altar) the carrier is still far from every altar at spawn, so recall-home cannot
work there. #1 banks at depth about 0.5 for the same reason.

## Round results, and the baseline was inflated: winner's curse

Nine single changes on v93, 320 paired games each, judged first against v93 itself:

    bruiser +9.3 (z 0.9)   items +2.9   bank36 -11.1   bank48 -21.8   travel60 -33.2
    travel40 -42.3   escort_safe -31.4   raid700 -28.3   raid900 -7.3     (all fail)

Two decision-neutral controls showed what was wrong. The stale-vision replan
never fires, yet scored -18.7 (z -3.3) against v93. And on maps where monoliths
hold under a quarter of the gems, raid700 and raid900 -- which change no
decision there -- both scored exactly -14.3 gems and -4.7 win rate. A change that
does nothing loses 15-19 gems against v93, because v93 was itself chosen as the
best bot on this same pool: its recorded trajectories are luckier than its true
strength, and any change re-rolls them back towards the mean. Measured directly,
v93 sits +18.7 gems (z 3.3) above its own decision-identical twin.

Judged against that twin (`gs93_replan`) instead:

    candidate          gems     z     win rate   verdict
    bruiser           +28.0   +2.8      +3.8      PASS
    items             +21.6   +1.4      +1.6      PASS
    raid900           +11.4   +0.8      -2.8      fail
    bank36             +7.6   +0.6      -1.9      fail
    raid700            -9.6   -0.6      -4.7      fail
    escort_safe       -12.7   -0.9      -5.0      fail
    travel60          -14.5   -0.8      -3.4      fail
    travel40          -23.6   -1.3      -5.6      fail
    cache             -45.2   -3.1      -7.2      fail

Bruiser now carries the same curse, being the best of ten, so it is being
confirmed out of sample: a fresh re-roll of v93 (`gs93_twin2`, one decision-
neutral statement per turn) against a re-roll of Bruiser (`gs93_bruiser_rr`).

Raid900 by map type: +26.0 gems on maps where monoliths hold half or more of the
gems, -35.0 at 25-50%, and the neutral -14.3 below 25%. A raid gated on the
map's monolith share may be worth a later round.

### Bruiser fails out of sample; the instrument's real resolution

    bruiser re-roll vs fresh twin 2:   gems -3.3 (z -0.3)   win rate -0.6
    bruiser re-roll vs twin 1:         gems +2.6 (z +0.2)
    twin 2 vs twin 1:                  gems +5.9 (z +0.9)   (two unselected re-rolls of v93)
    v93 vs twin 2:                     gems +12.8 (z +1.7)  (v93 vs twin 1 was +18.7)

Bruiser's +28 against twin 1 was the winner's curse again: it was the best of
ten, so its particular realisation of the pool was the luckiest. Re-rolled, its
effect is about zero. Heal at 60% (+23.0, z 1.2 against twin 1) carries the same
risk.

So one 320-game run of a bot carries roughly 10-20 gems of trajectory luck that
the paired standard error does not capture across selection. A candidate can
only pass honestly on an arm that was not used to select it: build the change
with a fresh decision-neutral re-roll and judge it against a fresh twin with
the same re-roll. Effects under about 20 gems need several such re-rolls,
averaged, to resolve at 90%. The bruiser + heal60 combination is being judged
that way (`gs93_bh_rr` against `gs93_twin3`).

Raid900 on the ten maps where monoliths hold half the gems or more, against
unselected twins: +32.5 gems (z 0.9) against twin 1 and +25.9 (z 0.7) against
twin 2, with win rate -1.2 and -7.5. Positive on gems, but 80 games on these
high-variance maps cannot resolve it, and win rate falls: the raid trades wins
for gems. `bench.py` now takes `BENCH_MAPS` to sweep a subset, and
`analysis/subset.py` compares arms on a subset (`--mono 0.5` for these maps).

### Bruiser + heal60: consistently positive, not yet significant

    combo vs twin 1 (in sample)             +18.6 gems (z 1.0)   win +1.2   deaths -0.70
    combo re-roll vs fresh twin 3           +14.8 gems (z 0.8)   win +2.8   deaths -0.75
    combo re-roll vs twin 2                 +11.5 gems (z 0.6)   win +1.6   deaths -0.70
    twins vs twin 3                          +3.3 and -2.6 (the method now holds)
    pooled, 2 combo arms vs 3 twins          +15.2 gems (se 17.8, z 0.85); deaths -0.71 (z -1.64)

Pooling re-rolls barely shrank the error, because most of the variance is
game-to-game (each map, opponent and side reacts differently), not re-roll luck.
The pool only has 320 distinct games, so a 15-gem effect needs more distinct
games, not more re-rolls of the same ones. The combination and a twin are now
being run against four more opponents (boss_full, seelie_t04, priority_exp,
gs_dis075) for 640 distinct games (`analysis/pooled.py`).

## v97 candidate passes at 90%: Bruiser plus heal-recall at 60%

Against four independent re-rolls of v93, with no arm used to select it, over
eight opponents (the standard four plus boss_full, seelie_t04, priority_exp,
gs_dis075):

    pooled, 640 distinct games    gems +19.4 (se 12.8, z +1.51, ~93.5% one-sided)
                                  one-sided 90% lower bound +3.0; win rate +2.5 (z 1.1)
                                  deaths -1.03 a game (z -3.25)
    the four new opponents alone  gems +23.6 (se 18.4, z +1.28); win +3.1; deaths -1.34

It meets the acceptance test -- at least 90% one-sided confidence of more gems,
win rate not down -- and the gain replicates on opponents never used to choose
it. The clearest effect is deaths: about one fewer a game, at 60 rounds of
respawn each.

`ws/bots/v97_submit` (bundled as `v97.zip`, 21,381 bytes) is v93 with two
changes: the late-game shop buys Bruiser shards instead of Power, and a
champion below 60% health recalls to heal when recall is safe and it is not
standing on a camp. `main.py` is byte-identical to v93's; two smoke games were
clean. Not uploaded: the owner decides. Local results have mispredicted the
ladder before (disengage at 0.75), so ranked results after an upload are the
real test.

Version 97 went live at 23:21Z at the owner's request; its folder matched the
`v97.zip` handed over, byte for byte, and `ladderbench.py` restores it.

v97's first ladder check: five unranked games at 23:29Z against Hidden Altar
Keepers on the `db_base` maps and sides (no submission; v97 was live):

    against v93's games (16:50Z)        gems +68.6, collected +74.0, gold +1,334, deaths +0.6, 0-5 both
    against greatsage's games (16:31Z)  gems +17.2, collected +39.2, gold +1,202, deaths -6.8, 0-5 both

Games last 105-187 rounds longer before the opponent reaches 1,000. A lean in
v97's favour; five games resolve nothing, and the opponent may have resubmitted
since the afternoon.

## CLOUD: where v97's champion-turns go, and the turns fuel takes

Brief item 1. `analysis/mktimelog.py` builds a logger from any Python bot: it
labels every champion-turn with the branch of `play_turn` that ended it, and
notes whether the turn hit a camp or a champion. `analysis/timeprofile.py`
reads the labels back out of a bench folder. v97's twin (`gs93_bh`), 160 games
on all 40 maps against `gs93_bh` and `gs_strong` (tag `tl97`):

    hit a camp       8.8%     (the top five teams: 16.5-17.9%)
    hit a champion   4.6%

    travel 22.3   dead 14.9   escort 11.6   approach 11.1   bank 8.7
    combat 8.6    capture 3.8 disengage 3.6  channel 3.0     retreat 2.4
    idle 1.2      cut short by fuel 6.3

A second run with event counters (40 games, 20 maps, tag `tl97b`): 70
objective choices per 1,000 champion-turns, 17.8 of them dropped on arrival
because the camp was respawning and 1.8 because an ally held it; the travel
spent on those dropped trips is 8.7% of all champion-turns.

**Fuel is the leak a fix can remove outright.** The 6.3% sits on a few maps:

    01yellow-brick-road 100%   01the-farm 35%   01big-world 18%   01islands 15%
    00lanes 7%                 every other map: median 1.1%

`gs97_fuelprobe` records the innermost frames each time `turn.Replan` fires.
On 01big-world and 01islands it is one call: `choose_group` →
`nav.field_from` → `layers_from`, the travel field for a champion with a dash
(a walking flood plus up to eight jump layers). `gs97_fuelcost` measured each
phase of `choose_group`: one `DistanceField` flood costs about 0.8M fuel on
01big-world, a third of a Python turn; a crystal holder's two floods cost
1.0-1.2M; a dash holder's nine never finished inside one turn, so the
champion stood still and retried from scratch the next turn. The first
ranking pass costs about 30k fuel per group (1.2-1.5M for the 46 groups a
dash champion reaches on 01islands); about a third of that is the per-tile
distance loop.

On 01the-farm the stall is elsewhere. `gs97_rejprobe` tallied why the exact
pass rejects candidates: Vendetta called `choose_group` 1,597 times in 1,600
rounds, rejected 21,059 candidates as too dangerous to clear alone, and scored
none. Scoring all 28 groups exactly costs more than a turn, so `choose_group`
never returned, the rally fallback (`choose_cooperative`) never ran, and one
of three champions did nothing all game: 29% of our champion-turns there.

Two fixes, both the same choices whenever fuel is not short:

- **`fieldresume`**: the finished flood layers stay in a module global keyed
  by origin and mobility, and the next turn resumes the flood where it
  stopped. Six probe games (`frprobe`): turns lost to fuel 11-18% → 3.2% on
  01big-world, 16-18% → 1.9% on 01islands.
- **`dangerskip`**: the exact pass rejects an unseen group on its design
  values, which the first pass already has, so the first pass drops it there.
  The exact pass sees the same survivors in the same order.

With the Python port of the party rule (`party`, gs_cpp_party's rule: fires on
00contest and 00stampede), they make `gs97_fp`. The C++ candidate's +39.5 gems
against v93 came almost entirely from three maps (01yellow-brick-road +876,
00contest +775, 00stampede +497 a game; the other 37 maps net slightly
negative), and these fixes aim at the same three without leaving Python.

### The stall-only version, and what the probe games show

LOCAL's cached camp stats cost v93 64 gems by making every `choose_group` call
cheaper, so more camps were exactly scored before the 950k cut-off. An always-on
`dangerskip` would change calls the same way on every map. **`cheapretry`**
replaces it: `choose_group` marks itself stalled on entry and clears the mark
on return, so only a call that a fuel `Replan` cut short leaves it set, and only
the same champion's next call takes the cheap path (unseen groups the exact pass
would reject are dropped in the first pass; visible groups are scored on design
values instead of re-adding each live camp's health). 01yellow-brick-road needs
the second half: two groups of 30 camps cost 0.43M fuel each to re-add
(`gs97_ybrprobe`). Maps that never stall keep v97's choices.

`gs97_fp` = v97 + fieldresume + cheapretry + party + reroll. Probe games against
`gs93_bh` (v97's twin), 14 games, 0 error lines:

    map, sides A / B          v97 (logger, tl97)        gs97_fp
    01yellow-brick-road       0-0 / 0-0                 1015-212 / 887-8
    01the-farm                1060-797 / 830-1011       1051-510 / 1017-595
    01big-world               930-1001 / 1001-951       1008-955 / 1016-762
    00contest (party)         0-0 / 0-0                 800-0 / 800-600
    00stampede (party)        640-0 / 0-320             666-294 / 454-186

Turns lost to fuel on 01the-farm 35% → 1.1-1.4%, and turns hitting a camp
12.7% → 19-21%. A probe is a sample, not a test; the 640-game test follows.

### Idle champions on crystal maps

The time profile's `idle` label (no objective at all) is 21-32% of champion-turns
on 01islands and up to 13.5% on 00ambush. `gs97_idleprobe` tallied the idle
state: almost always no teleport crystal, under 50 gold, and only one or two
groups reachable on foot (00ambush: Varg idle 1,290 of 1,700 rounds next to a
single reachable group; 01islands: Willow with no reachable group at all for
1,446 turns). The shop buys a crystal first, then spends every coin on shards,
so a champion that has used its crystal cannot buy the next.

**`crystalfund`**: on a map that needs crystals, a champion holding one keeps the
next one's price, and an idle champion without one that can afford it recalls to
buy it. Four probe games (`crprobe`): idle 26-32% → 1.9% on 01islands side B,
unchanged (21%) on side A; all four games won. It acts only where
`nav.needs_crystal()`, so it is screened on those maps.

## CLOUD: Treasure first on v97, first half (brief item 2)

`gs97_treasure` (v97 + Treasure first + reroll) against the fresh twin
`gs97_rr` (v97 + reroll), 320 paired games on the standard four opponents:

    gems +15.1 (se 13.4, z 1.1)   win rate +2.8 (se 2.9)   gold earned +1,586 (z 12.8)
    kills +1.4 a game (z 3.3)     deaths -0.2              gems collected +22.9
    by opponent: base +44.5, boss_focus +25.4, greatsage +15.6, colleague -25.3

On greatsage Treasure bought gold and no gems; on v97 it leads, and the extra
gold shows up as kills. Below the 1.28 bar, so it is being extended to 640
games against the other four opponents (`treas97b` against `rr97b`).

## CLOUD: gs97_fp passes its first 320 games at z 3.6

`gs97_fp` (v97 + fieldresume + cheapretry + party + reroll) against the fresh
twin `gs97_rr` (v97 + reroll), 320 paired games on the standard four opponents:

    gems +67.5 (se 18.6, z 3.6)    win rate +10.6 (se 3.0, z 3.6)
    opponent gems -44.1 (z -2.4)   deaths -0.9    kills 0.0    gold +39
    95% bootstrap +31.1 to +104.7; 144 games better, 95 worse, 81 the same (69 bit-identical)
    results flipped: 64 to a win, 30 to a loss (p 0.001)
    by opponent: base +66.9, boss_focus +71.4, colleague +55.3, greatsage +76.2

By map group (`analysis/bymaps.py`):

    party maps (00contest, 00stampede)          16 games   +323.2 (se 146.5)
    stall maps (yellow-brick, the-farm,
      big-world, islands, lanes)                40 games   +138.0 (se 37.6, z 3.7)
    every other map                            264 games    +41.3 (se 19.5, z 2.1)

The other maps gain too. A likely reason, not yet measured: fuel cuts short
`choose_group` there less often, but when it does v97 loses that turn and
repeats the same expensive call on the next, while `gs97_fp` takes the cheap
path once and moves on. A logger run of `gs97_fp` on the full pool would show it. The second half
(`fp97b` against `rr97b`, the other four opponents) completes the 640.

`ws/bots/v98_submit` and `v98_submit.zip` (22,336 bytes) are built by
`analysis/mksubmit.py v98 bruiser+heal60+fieldresume+cheapretry+party`. They
differ from the tested arm only by the decision-neutral re-roll statement and
the BOTTAG line; `main.py` is byte-identical to v97's. Not uploaded.

### v98 game by game on the party and stall maps (first half)

Two caveats under the aggregate:

- **01yellow-brick-road:** v97 scores 0 from both sides; it "wins" every side-B
  game 0-0 on the last tiebreak (Team B). v98 averages about 440 gems there,
  wins every side-A game (607-22, 1019-0), and loses every side-B game
  (180-596, 444-449, 477-723, 183-412) with 10-17 deaths: once we farm, the
  opponent kills our carriers and banks their gems. Same win count, 4 of 8.
- **00stampede:** the party rule is mixed. Side A: v97 wins 800-0 in three of
  four (the rally fallback clears the herd), v98 loses 160-320 in three of
  four. Side B: v98 better (906-214 against 640-0). Net about -54 gems over
  eight games, inside the noise, but not the +497 the C++ port showed against
  v93. 00contest, where every gem is behind a monolith and solo play cannot
  score, gains about +575.

If stampede stays negative over 640 games, the conservative rule is to play as
a party only when every gem sits behind a monolith (00contest's shape), and
leave heavy-pack maps to v97's rally fallback.

## CLOUD: v98 passes over 640 games, z 4.55

`gs97_fp` against fresh v97 twins, pooled over all eight opponents
(`pooled.py --base rr97,rr97b --cand fp97,fp97b`):

    640 distinct games   gems +59.4 (se 13.1, z +4.55)   one-sided 90% lower bound +42.9
                         95% interval +33.8 to +84.6
                         win rate +11.4 (se 2.2, z +5.3)  deaths -0.5 (z -1.4)
    second half alone    (boss_full, seelie_t04, priority_exp, gs_dis075; never used in design)
                         gems +51.4 (se 18.4, z 2.8)  win rate +8.4 (z 2.8)
                         boss_full +76.2, seelie_t04 +62.4, priority_exp +53.9, gs_dis075 +12.9
                         62 results flipped to a win, 35 to a loss (p 0.008)
    0 error lines in 640 games.

By map group over the 640:

    stall maps (yellow-brick, the-farm, big-world, islands, lanes)   80 games  +145.3 (se 31.1, z 4.7)
    party maps (00contest, 00stampede)                               32 games  +282.4 (se 99.9, z 2.8)
    every other map                                                 528 games   +32.9 (se 13.6, z 2.4)
    00contest +587.5, 01yellow-brick-road +527.4, 00stampede -22.6

For scale, v97 passed this test at +19.4 (z 1.51). v98 meets the acceptance
test with a wide margin, and the gain replicates on the four opponents that
played no part in its design. It was not picked from several candidates by
these results, so there is no winner's curse to correct for.

**Handed to the owner, not uploaded:** `ws/bots/v98_submit`, bundled as
`v98_submit.zip` (22,336 bytes, sha256
fc1aecf2198e3ef0dd102db42e1b470c7cadac0519e171dc241f5e719ee03b20) by
`analysis/mksubmit.py v98 bruiser+heal60+fieldresume+cheapretry+party`. It is
the tested arm without the re-roll statement and BOTTAG; `main.py` is
byte-identical to v97's; eight smoke games of the untagged build were clean.
Local results have mispredicted the ladder before, so after an upload the
quick ladder check (five unranked games against a pinned `db_base` team) is
the next step.

### The pool is smaller than it looks: clustered standard errors

Three of the four default opponents (greatsage, base, boss_focus) are near
clones: on 52 of 80 map-sides they produce games with identical gem totals,
for v97 and v98 alike. The paired SE in `paired.py`/`pooled.py` counts those
copies as independent games and understates the uncertainty. `analysis/
clustered.py` averages each (map, side) over the opponents of a bench tag
first (160 clusters for 640 games), which is conservative where they differ:

    v98, 640 games     gems +59.4   plain se 13.1 (z 4.55)   clustered se 19.9 (z 2.98)
                       win  +9.5    plain se  2.1 (z 4.48)   clustered se  3.0 (z 3.19)
    first half         gems +67.5   plain z 3.63             clustered z 2.16
    second half        gems +51.4   plain z 2.80             clustered z 2.06
    Treasure on v97    gems +15.1   plain z 1.12             clustered z 0.84

(Win rate here is the official match outcome; `pooled.py` counts a win as more
gems, which gave +11.4.) v98 passes on each half alone under the clustered
error. Earlier verdicts made with the plain error, v97's z 1.51 included, are
weaker than they read; rerun them with `clustered.py` before relying on a
marginal pass.

`gs98_partymono` (party play only where every gem is behind a monolith) is
rejected: on 00stampede it lost 486 and 288 gems a game against v98 over 32
games. A logger probe showed why the comparison is so noisy: the cheap path
fired four times a game there and fuel was not short; 00stampede is all or
nothing, and small trajectory changes swing a game between 800 and 0.
v98's broader party rule stays.

## CLOUD: screens on the v98 base

Each arm is v98 + one change + reroll, judged against v98's own runs
(`fp97`, `fp97b`) with `clustered.py`, on four distinct opponents (greatsage,
colleague, seelie_t04, gs_dis075), 320 games.

**Treasure first (`t98`): +13.3 gems (clustered se 14.8, z 0.90), win rate
+0.6, gold +1,381, kills +0.5, deaths -0.4.** By opponent: seelie_t04 +40.5,
colleague +24.0, gs_dis075 +13.1, greatsage -24.4. The same small lean as on
v97 (+15.1, z 0.84 clustered): Treasure buys gold that converts weakly into
gems. Not passed; not in the candidate.

**Claim-inferred respawns (`c98`): stopped for futility at 109 of 320 games,
-38 gems (clustered z -1.1), win rate -9.3 (z -1.7), gems collected -19,
deaths +1.0.** The likely cause, not measured: the inference marks a
group respawning for its full timer whenever an ally's claim moves from it to
another group; an ally that found the group mid-timer, or left it for another
reason, makes everyone skip a camp that is already back. The wasted travel it
targets (8.7% of turns) needs real information, not inference from claims.

### v98's time profile

`gs98_timelog` (v98 + logger), 160 games on all 40 maps against greatsage and
colleague (`tl98`), beside v97's (`tl97`, against gs93_bh and gs_strong):

                     v97      v98
    hit a camp       8.8%    10.7%
    dead            14.9%    11.3%
    travel          22.3%    22.1%
    bank             8.7%    10.1%
    capture          3.8%     5.7%
    disengage        3.6%     1.8%
    cut short by fuel 6.3%    1.7%

The remaining fuel loss is on 01yellow-brick-road (11.7%), 01islands (8.4%)
and 00lanes (6.6%); the largest idle shares are on the crystal maps 01big-world
(22.8%) and 01islands (21.6%), which `crystalfund` targets. Travel is
unchanged at 22%, twice the time spent hitting camps.

**Carrier hunting (`h98`): -12.6 gems (clustered se 13.2, z -0.95), win rate
-1.9, deaths +0.4, opponent gems +12.7.** By opponent: colleague +28.2,
greatsage -17.7, gs_dis075 -26.8, seelie_t04 -34.0. Accepting fights for
carriers at 0.8 of the enemy's local strength costs more than the carried gems
pay. Not passed.

**Crystalfund (`cr98`, the 7 crystal maps, 56 games): -79.4 gems (clustered
z -1.9), win rate -8.9.** By map: 01boss-battle -363, 01fracture -204,
01shortcut -40, 00ambush -7, 01big-world -3, 01islands +1, 00quadrants +62.
The idle time it targets on 01islands and 01big-world did not turn into gems,
and keeping the next crystal's price delays shards, which costs most on
01boss-battle, where the party needs its items for the monolith. Rejected.

**Gated monolith raid (brief item 4) on the 9 monolith-heavy maps, 72 games:**

    m98   raid900 + monogate               gems +57.7 (clustered se 35.3, z +1.64)   win +1.4
    ms98  raid900 + monogate + safebank80  gems -139.4 (z -3.87)                      win -31.9

By map, m98: 01gold-rush +418, 01broken-curve +122, 00rows +118, 00monolith
+114, 01big-world +39, 01corridors +35, 01starvation -69, 00great-wall -118,
00split -138. The safe-bank recall (carriers of 80+ gems far from altars go
home first) is clearly harmful. The plain gated raid passes on its maps; these
maps swing by hundreds of gems, so it is being confirmed on an independent
re-roll pair (`gs98_mono_r2` against a fresh v98 twin `gs98_r2`, both reroll2)
before it can join the candidate.

### The raid confirms; v99 = v98 + the gated monolith raid

    re-roll 2 (gs98_mono_r2 vs fresh v98 twin gs98_r2)   gems +65.2 (clustered z 1.56)   win +2.8
    both re-rolls pooled, 144 games                     gems +61.5 (clustered se 27.1, z 2.22)   win +2.1
    twin check (gs98_r2 vs v98's own runs)               gems -1.4 (se 5.2)

The per-map pattern repeats across re-rolls (01gold-rush +418/+429, 00monolith
+114/+120, 00rows +118/+127, 01broken-curve +122/+92; 00split -138/-190,
00great-wall -118/-112, 01starvation -69/-22). The twin check shows that a
re-roll moves these games very little, so the evidence comes from the 9 maps
and 4 opponents more than from the re-rolls. Six of the nine monolith-heavy
maps gain. Over the 40-map pool that is about +14 gems a game on top of v98;
on maps where monoliths hold under half the gems the raid code makes v98's
choices exactly (the share is read once at the start; non-monolith groups keep
one raider in every formula).

`ws/bots/v99_submit`, `v99_submit.zip` (22,818 bytes, sha256
22b488edc24c85c56858f24b877511821ee384f833be3ec13e91b8e85a6b2773), built by
`analysis/mksubmit.py v99 bruiser+heal60+fieldresume+raid900+monogate+cheapretry+party`:
the tested arm `gs98_mono` minus the re-roll statement and BOTTAG; `main.py`
byte-identical to v97's; eight smoke games clean (7 wins against v97's twin).
Not uploaded.

Also run: travel weight 1.4 (`tr98`) is flat to negative so far.

**Travel weight 1.4 (`tr98`): stopped for futility at 194 of 320 games, -21
gems (clustered z -1.4), win rate -3.6.** LOCAL's 0.6 and 0.4 lost too, so the
greatsage weight of 1.0 sits at or near the optimum; the 22% of turns spent
travelling is not a weighting problem.

**A cheaper cheap path (`ch98`): -4.7 gems (clustered z -0.29), win rate -1.2,
320 games.** Box distances, six sample tiles a group and a give-up when fuel
runs low did cut fuel loss on 01yellow-brick-road in the probe (38% to 12%),
but they change nothing measurable over the pool. Not adopted.

## CLOUD: where v98 still loses, and enemy altar locks

v98's worst map over its 640 test games is **01shortcut: 0 wins of 16** (v97: 5
of 16), 422 gems against 919. Its champions spend 30% of their turns banking
(the median map: 9%). `gs98_bankprobe` counted the branches of `bank()` there:
811 bank-turns within a few tiles of an altar for 17 deposits, 679 turns with
the near altar under an **enemy altar lock**, and 608 turns 45+ tiles from any
altar goal. Both teams place a lock on every altar they pass (10 gold, five
hits to clear, and it blocks only the other team's deposits). `bank()` broke a
lock only when no altar at all was free, so with two altars our carriers
walked across the map to the free one, and back.

Other maps with high bank time in v98's profile: 00rushbait-v2 30% (a 38%-win
map for v98), 00reverse-spiral 25%, 00great-wall 22%, 01the-farm 19%.

**`lockbreak`**: a locked altar wins when its distance plus six turns of
hitting is less than the nearest free altar's; once the lock falls, our own
lock goes on in `finish_turn`. Probe, against a v99 twin logger on the same
games (2 games a map):

    01shortcut        bank 27.9% -> 23.6%   twin 266-1016, 125-1007   lockbreak 854-894, 1063-16
    00rushbait-v2     bank 20.0% -> 13.5%   twin 1011-29, 857-1025    lockbreak 1011-29, 1005-117
    00reverse-spiral  bank 13.2% -> 11.0%   both won both

Screening on v99 (`lk99` against the fresh v99 twin `r299`, 320 games).
