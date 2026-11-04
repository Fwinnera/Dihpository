# Reinforcement learning for the Milk and Potatoes bot: what is feasible

Written 2026-11-03 at the owner's request ("a lot of the top people are using reinforcement
learning for their bots ... can you look into reinforcement learning for our bot").

## The constraints any learned policy must meet

| constraint | value | source |
|---|---|---|
| compute per champion turn (C++) | 100,000 fuel (first champion turn 2x, first draft turn 100x) | `ws/bots/*/src/turn.h`, `sdk/cpp/cambc.h` `fuel_remaining()` |
| our bot's own use of that budget | already near the limit on some turns (about 18 fuel exhaustions a game on the ladder; the dash-crossing search alone can take about 79,000) | `GROUND-UP-PLAN.md` |
| submission size | 5 MB of source (weights must be compiled in as arrays) | `cambc submissions list` `maxBytes` |
| runtime access | WebAssembly sandbox: no files, no network; 8 bytes of shared memory between champions | SDK |
| local game speed | about 18,000 games an hour on this Mac (12 cores; 172 games in about 30 s) | `ws/bench/s34_screen.log` |
| ML libraries here | none (system Python 3.9, no numpy or torch; installing them needs the owner's OK) | checked 2026-11-03 |
| simulator | the official engine binary only (`cambc run`); no fast Python model of the game | |
| real opponents | only through the platform: 50 unranked groups (250 games) an hour, playing whatever version is live | `analysis/rebuild/lab.py` |

A forward pass of a small network (say 64 inputs, 32 hidden units, 8 outputs: about 2,300
multiply-adds) costs a few thousand fuel, so inference fits. Training is the hard part: the
policy runs inside the engine, so learning means playing games, logging what happened, and
rebuilding the bot with new weights.

## Three levels, in order of what can be done soon

**1. Evolution strategies over the bot's decision parameters (days, no new libraries).**
Treat the 30-40 numbers that steer the bot as the policy: camp value weights (gold against
gems, by round and map), engage odds and range, disengage ratio, retreat health, heal and shop
thresholds, group-play rounds, collector range. A CMA-ES loop samples 16 parameter vectors,
writes 16 bot copies (`analysis/rebuild/mkparam.py` already sets constants), plays each
against a league of opponents, and moves the distribution toward the winners. At about 100
games a candidate that is roughly 10 generations an hour, 100+ overnight. This is black-box
reinforcement learning: no gradients, no network, and it works on the code we already trust.

**2. Learned components (a week).** Replace the hand-written guesses inside single decisions
with small models fitted to data: a fight-outcome model (will this engagement win, from local
health, strength, shields, stuns, numbers and distances) to drive engage / disengage /
retreat, and a camp-value model. Log features and outcomes from local games (stdout, raise
`--log-limit`), fit logistic regression or a tiny network in plain Python, compile the
weights in, then tune the rest with level 1.

**3. A full neural policy trained by self-play (weeks).** Encode the board for each champion,
choose an action space (target camp, target enemy, move direction, ability), log trajectories
from thousands of games, train with policy gradients (needs torch), export weights to C++
within the fuel budget, and train against a growing league of past versions. This is what the
strongest teams have probably done over the season; it is not reachable before the 11 Nov UK
qualifier from where we are, and it needs a faster simulator than the engine to be practical.

## The trap: learning to beat ourselves

Today's main lesson applies to any learning loop. Every local opponent is our own code or a
close relative, and changes that won 55-67% head to head locally were level on the ladder lab
(`GROUND-UP-PLAN.md`, "Toward rank 200"). A tuner that optimises against that pool will learn
to exploit our own habits. What helps:

- a **league**: past versions, Andy's bots (gs_mix_camp, gs_eq), and deliberately different
  opponents (Heart of Ruin + Marcella drafts, gem-first camp choice, aggressive divers), with
  fitness averaged across them;
- **gem margin** as fitness, not only wins (more signal per game);
- **validation on the ladder lab** before anything goes live: 100 games against the ten
  pinned teams (`lab.py`), with the current best as the reference.

## Recommendation

Start with level 1 straight after the qualifier deadline: build the tuner, run it overnight on
a league, and test its best vector on the ladder lab. If it finds gains that survive the lab,
build level 2's fight model next, since fights are where we lose most (our champions die about
twice as often as the same champions of the 1,700+ teams).

## First experiment (2026-11-03 evening): a learned danger table

`ws/bots/dzlog` (ab3 plus one log line per living turn) played 688 local games (3.2 million
champion turns); `analysis/rebuild/dzfit.py` turned them into a 720-cell table of the chance
of dying within 15 rounds, by health band, local odds (total health x total strength, ours
against theirs), enemies within 6, allies within 5 and distance from home. The table is
sharp: 3% above 75% health against 62% below 20%; 16% with one enemy near against 43% with
three; 45-76% at 35-75% health when heavily outgunned -- states where the fixed thresholds
keep fighting. **ab5 = ab4 + withdraw when the table says more than 50%**: level locally (88
of 172 against ab3, 82 against ab4) and worse in its smoke games (40 deaths on 00oasis).

Why it did not help is the useful part: the table measures danger *under the current
policy*, and most of our deaths already happen while withdrawing, so "this state is
dangerous" does not mean "withdrawing from it is safer". Deciding *what to do* needs the
outcome of each choice, which is exactly what on-policy learning (level 1's tuner, or level
3's self-play) measures and logged data cannot. The table is still worth keeping as an input
feature for a learned policy.

## Level 1, first run (2026-11-03, 18:00-21:05Z): an ES tuner over 20 constants

**What was built.** `analysis/rl/es.py` (pure Python; usage in its docstring) and
`ws/bots/es_base`: ab3_submit with five literals exposed as `config.h` constants
(`ENGAGE_RANGE` 4 and `ENGAGE_ODDS` 1.15 in `combat::choose_enemy`, `GOLD_EARLY` 1.0 and
`GOLD_LATE` 0.25 in `strategy::choose_group`, `SHIELD_HP` 0.95 in `combat::fight`). Its
release wasm is byte-identical to ab3_submit's, so it plays exactly as ab3. With the fifteen
`config.h` constants already there (`BANK_GEMS` ... `RAID_ROUND`) that is 20 numbers, each
scaled to [0, 1] over the range in `PARAMS`. A generation samples 16 vectors from a separable
CMA-ES (diagonal covariance, cumulative step-size adaptation), writes each as a fresh
`ws/bots/es_*` copy (config.h set by `mkparam.py`, deleted after its generation) and plays
them all on the same 72 games: 3 maps for every league opponent, both sides, the maps
rotating through a per-opponent shuffle of the 86. About 1,200 games and 3.5-9 minutes a
generation at 8 jobs.

**League and fitness.** The twelve opponents above: cHG_submit, rl_submit, sh_submit,
gs_mix_camp, gs_eq, b_tbd, next_trial, f_hor_h, f_tavi_n, dH_submit, sgA_submit, d1. Fitness
of a game is our submitted gems minus theirs, plus 200 when the engine outcome is ours (a
draw goes to the side that earned more gold), averaged over games. ab3 against the whole
league (`ws/bench/es_league_base`, 2,064 games): 67.3% wins, margin +210, fitness +344.2;
weakest against sh_submit (50.0%), sgA_submit (54.7%) and rl_submit (57.6%).

**Determinism and noise.** The generation-0 mean (ab3's vector rebuilt through mkparam)
reproduced all 72 of its games exactly, and 12 replays of es_base matched the sweep, so
ab3's results are read from that one sweep rather than replayed. Between two vectors on the
same game the fitness difference has a standard deviation of about 750-850 (games are
blowouts and small changes flip them): one vector against ab3 on a generation's 72 games has
a standard error of about 90, on the full league about 16-19. Candidates of one generation
share their games, so ranking them is less noisy (about 65 a candidate).

**Run r1** (`ws/bench/es/r1/`: `es.log`, `log.jsonl`, `games.jsonl`;
`es.py show --run r1`). 29 generations, 464 candidates, 33,996 games, 18:18-20:39Z; no bot
faults, no missing games.

- g00-g07, CMA-ES as designed (16 a generation, 8 selected, sigma 0.12, mean rate 1). The
  mean's own check against ab3, one generation each: 0, -24, +35, -59, -40, -28, -63, +122,
  average -7 (se 30), too noisy to steer by. Random candidates lost on average (median -32).
- g08-g28, sampling around ab3 (`--cm 0 --freeze --recentre`, sigma 0.121): the mean held at
  ab3 so that every candidate measures the neighbourhood of the live bot, which is what the
  pooled regression below reads (an OpenAI-ES style gradient estimate). A random sigma 0.12
  move of all 20 constants cost 70 on average.

**Which constants matter** (`es.py grad --run r1`: each candidate's fitness and displacement,
centred within its generation, regressed on all 20 at once; fitness per tenth of the
constant's range, residual sd 69):

    constant                  ab3   slope   se     t
    FAT_BAG                    40   +13.1   2.2  +6.0
    CARRIER_RETREAT_HEALTH   0.43   -14.5   2.9  -4.9
    DISENGAGE_RATIO           0.5   +11.9   3.0  +4.0
    GOLD_LATE                0.25   -11.5   3.2  -3.6
    ENGAGE_ODDS              1.15    -7.4   2.7  -2.8
    SHIELD_HP                0.95   +11.2   4.1  +2.7
    ENGAGE_RANGE                4    +6.3   2.4  +2.6
    RETREAT_HEALTH           0.30    -6.6   2.9  -2.2
    ROLE_NEAR                   3    +5.2   2.7  +1.9
    the other eleven                             |t| < 1.8

With a curvature term for each (`--quad`) nearly all curvatures are negative (concave), so
ab3 is close to an optimum in most directions; the strong slopes stay close to linear over
a tenth of the range. Earlier signals that faded as data came in (BANK_GEMS at t +2.3 after
9 generations, -0.7 at the end) are why the cut is |t| >= 2.5.

**Validation.** Each arm against the whole league (2,064 games, paired game by game with
`es_league_base`; `ws/bench/es_league_r1_*`) and head to head against ab3_submit (86 maps
from both sides; `ws/bench/es_r1_*_vs_ab3_submit`):

    arm    vector                                         league vs ab3      wins    h2h vs ab3_submit
    grad   ab3 + a tenth of the range along the seven    +67.3 (se 15.7)   +3.4 pt  96 of 172, +66 (se 39)
           slopes with |t| >= 2.5 (ENGAGE_RANGE rounds
           back to 4, so six constants change)
    cma    the CMA-ES mean after g07                      +45.7 (se 17.1)   +2.0 pt  94 of 172, +40 (se 42)
    grad3  the same seven, a fifth of the range           +48.7 (se 17.4)   +2.8 pt  93 of 172, +73 (se 43)

The arms are not distinguishable from each other (grad minus grad3 +18.5, se 16.2; grad
minus cma +21.5, se 17.2); the bolder step added nothing.

**es_best is the grad vector** (`ws/bots/es_best`, untagged; its wasm is byte-identical to
the validated `es_r1_grad`; rebuild with `es.py apply es_best --run r1 --which grad:2.5`):

    CARRIER_RETREAT_HEALTH 0.43 -> 0.39    DISENGAGE_RATIO 0.5 -> 0.58    FAT_BAG 40 -> 46
    ENGAGE_ODDS 1.15 -> 1.02               GOLD_LATE 0.25 -> 0.15         SHIELD_HP 0.95 -> 1.0

Every other constant is ab3's. League totals against ab3's, 2,064 games each: wins 70.7%
against 67.3%, margin +270 against +210, fitness +411.5 against +344.2, deaths 11.8 against
12.3 a game (the opponents' 16.9 against 16.5). Ahead against 11 of the 12 opponents, most
against cHG_submit (+136, se 58), sh_submit (+130; 55.8% against 50.0%) and sgA_submit (+106;
59.9% against 54.7%), least against d1 (+13); level with gs_mix_camp (-5). Head to head against
ab3_submit: 96 of 172 games, maps won from both sides 27, split 42, lost from both 17; gem
margin +66 a game (se 39). Smoke, two `cambc run --release` games against ab3_submit: exit
0, no ERROR lines, no bot faults; 00contest won 800-400 as team A, 00oasis lost 250-1,002 as
team B (37 deaths; the same map as team A was won by 1,014). 00oasis is the map to watch: in
the league es_best wins 13 of its 24 games there against ab3's 17, at 28.5 deaths a game
against 24.4.

**Reading.**

- The six changes read as one behaviour: engage at slightly worse odds, shield on any
  damage, stay longer when carrying gems, but leave a lost fight sooner; channel a bigger bag
  without the safety check; and value gold less after round 500.
- This is a local result on our own pool. The regression and the validation use the same 86
  maps and twelve opponents (different games, the same pool), and picking 7 of 20 constants
  by their t adds a little optimism. The ladder lab is the test that counts: 55-67% local wins
  were level there before (`GROUND-UP-PLAN.md`, "Toward rank 200").
- If es_best holds on the lab, the next run is the same tuner centred on es_best, with a few
  maps or opponents held out. That needs two small changes in `es.py`: es_best's values as
  the `PARAMS` defaults, and a league sweep of es_best as the base it reads (`BASE`,
  `BASE_TAG`); today both are ab3's.

## Second experiment (2026-11-03, 22:10-22:40Z): the danger response, explored on-policy

The first experiment's lesson was that deciding *what to do* in danger needs the outcome of
each choice. `analysis/rebuild/mkdr.py` MODE 1 (`ws/bots/drx` = ab3 + exploration) supplies
it: in a danger state -- the retreat rule or the disengage rule would fire, or the danger
table puts death within 15 rounds above 35% -- a champion commits for 5 rounds to a response
drawn at random (the ordinary rule; fall back to the nearest teammate above half health; stand
and fight the weakest enemy in reach) and logs the episode. 1,376 local games against eight of
our bots (`analysis/rebuild/drrun.sh`, `ws/bench/drdata`), 113,396 episodes;
`analysis/rebuild/drfit.py` scores each by what followed for that champion: gold over the next
40 rounds plus twice the gems, minus 150 for a death within 20.

    ordinary   -43.8 (se 0.5)  died 40%
    fall back  -49.6 (se 0.5)  died 43%
    fight      -66.9 (se 0.5)  died 56%

The ordinary rule is best under every trigger (retreat rule, disengage rule, table only) and
for every champion type (Ryth, Vesper Vale, Vendetta, Marcella, Varg: falling back 5-7
worse, fighting 18-24 worse). One coarse state cell of about a hundred clears two standard
errors (fight, with no enemy within 6) -- what chance alone gives. No policy bot is built.

**Reading.** Once a champion is in danger, our response is already the best of the three;
the deaths are decided before the danger state, by where and with whom a champion is caught.
With the first experiment (predicting danger does not make withdrawing safer) this closes the
moment-of-danger response as a lever. What is left for fights is upstream: positioning, group
size when a fight starts, and which camps are farmed with enemies near.

## Level 1, second run (2026-11-04, from 00:45Z): the league that predicts the lab

`analysis/rebuild/labpredict.py` found that a version's local results against gs_mix_camp
(rank correlation 0.81 with lab wins over 10 versions), b_tbd and next_trial predict the ladder
lab, while results against our own lineage do not (rl 0.15). r1's es_best gained nothing against
gs_mix_camp (-5 a game); its whole gain was against our own bots, and it lost on the lab. r2 is
the same tuner with `ES_LEAGUE=gs_mix_camp,b_tbd,next_trial` (an env override added to `es.py`),
10 maps an opponent a generation from both sides (60 games a candidate), 16 candidates, until
07:00Z. Validation before any lab slot: the mean's full sweep against the three opponents
(516 games), plus held-out f_cast_n, gs_eq and f_hor_h.
