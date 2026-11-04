# Toward the UK qualifier (10-11 Nov 2026): the plan

Owner, 2026-11-03 22:10Z: "thats international qualifiers we are uk we have till the 10th, lets
improve our bot as much as we can". The live bot is v155 (ab3, `ws/bots/ab3_submit`), rank
about 214 (rating 1,728).

## What 3 November taught us about measuring

- Local games against our own bots do not predict the ladder for anything smaller than a
  new mechanism: changes that won 55-67% head to head locally (cb, es_best) were level or
  worse on the ladder lab. The ES tuner's 2,064-game league result (70.7% against 67.3%)
  became 42 of 100 against v155's 48.
- What did carry over were mechanisms the strong teams exploit and we did not: capture
  rewards routed to Vesper Vale and Marcella (team gold +23% against teams ranked 176-228),
  and the 03homonoliths spawn attack (0 of 4 to 8 of 8).
- The ladder lab (`analysis/rebuild/lab.py`, 100 games against ten pinned teams) resolves
  about +-7 wins; gem margin paired game by game (`labmargin.py`) a little better.

**Local filter (4 Nov, `analysis/rebuild/labpredict.py`):** of our local opponents, gs_mix_camp
(rank correlation with lab wins 0.81 over 10 versions), b_tbd and next_trial predict the lab;
head to head against our own bots does not. A candidate must beat v155 clearly on the mean of
those three screens (v155 129.3 of 172, noise about +-3) before it takes a lab slot.

**Protocol for the week.** Each candidate is a mechanism, not a retune. It must be level or
better locally (no regression: `screen.sh` against v155 and the panel), then goes live for a
long window -- most of a day -- so that ranked games (about 30 an hour, 5-game batches) and
the lab (250 games an hour) give several hundred games each; keep the better of it and v155
by ranked performance and lab totals together. One live candidate at a time; the README lock
as always; re-pin after every upload.

## Workstreams, in order of the gap they close

1. **Danger response, learned on-policy** (fights: our champions die about twice as often as
   the same champions of 1,700+ teams). Predicting danger is solved (AUC 0.79 with the 2025
   simulator, a sharp table today); choosing the response is not. In danger states a local
   build tries a random response -- retreat home (today's rule), fall back to the nearest
   healthy teammate, stand and fight the weakest enemy in reach, shield and fight -- and logs
   what follows (death within 15 rounds, damage dealt and taken, kills). The best response
   per state cell becomes the policy. This is a contextual bandit: reinforcement learning on
   the decision that matters most, with the counterfactual the logged data lacked.
2. **Party maps** (11% of ranked games, 36% won against 60% elsewhere): chokepoint altars
   (01boss_battle's one open tile, 02guardians' two) need one banker holding the tile and the
   others feeding it; 00anvil and 00contest need monolith control in the opening.
3. **Opening and gem race** (00lost_world, 03membrane, 00pilgrimage): we take 43-48%
   gold-only camps before round 150 against the strong teams' 33%. Needs a local opponent that
   races gems, so the fix can be judged before it goes live.
4. **Tuner v2** (`analysis/rl/es.py`): the same ES with held-out opponents and maps, and with
   ladder-lab arms in the fitness, so it stops learning to beat our own pool.
5. **Local opponents that play like the ladder**: style bots built from our own code (early
   monolith raider `bk2_submit`, gem-first `sgA_submit`, aggressive `d1`, Heart of Ruin
   drafts), checked by whether their local verdicts match the lab's on the 17 versions with
   lab results.
