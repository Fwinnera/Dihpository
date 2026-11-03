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
