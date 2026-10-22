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
